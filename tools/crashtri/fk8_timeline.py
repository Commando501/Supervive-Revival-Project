#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk8_timeline.py -- FK-8 dimension 3: PROVENANCE AND TIMELINE.

Joins docs/fk8-crash-corpus.csv (built by tools/crashtri/fk8_corpus.py) against
this repository's history, so every crash can be attributed to the code that was
on disk when it happened.

READ-ONLY.  Touches nothing under %LOCALAPPDATA%\\SUPERVIVE\\Saved\\Crashes -- it
reads the corpus CSV, not the crash tree.  Runs `git log` / `git reflog` only.

Outputs
-------
  docs/fk8-crash-timeline.csv   one row per corpus row, with the provenance columns
  stdout                        every table quoted in docs/fk8-crash-timeline.md

Method notes that matter (read before quoting any number)
---------------------------------------------------------
* HEAD-at-crash-time is taken from `git reflog`, NOT from "latest commit whose
  date <= t".  The reflog in this repo covers 412 entries back to the initial
  commit (407 commits + 4 checkouts + 1 merge), so real HEAD movement -- including
  the 2026-06-29 checkouts between `main`, `claude/assetregistry-*` and
  `dedicated-server-stub` -- is MEASURED, not inferred from commit ordering.
* `shim_vintage` = the most recent commit touching `tools/sigbypass-mod/` at or
  before the crash.  This SYSTEMATICALLY UNDER-DATES the code by up to one commit:
  a run is executed, it produces evidence, and the evidence + the source change are
  committed AFTERWARDS.  Measured lag for the six runs whose evidence files are
  git-tracked: 3 m 47 s .. 2 h 53 m.  Treat shim_vintage as "at least this new".
* Crash times: UECC rows use `TimeOfCrash` ticks (UTC, verified against file mtime
  to <0.8 s over N=84 by fk8_corpus.py).  Crashpad rows use the __sentry-event
  timestamp.  The 8 degenerate rows have NO TimeOfCrash at all, so this tool falls
  back to the CrashContext.runtime-xml mtime and marks time_source='mtime'.
"""

import argparse, collections, csv, datetime, os, statistics, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
CORPUS = os.path.join(REPO, "docs", "fk8-crash-corpus.csv")
OUT = os.path.join(REPO, "docs", "fk8-crash-timeline.csv")

# Every crash timestamp in this corpus is UTC-05:00 local (America/Chicago, CDT).
LOCAL = datetime.timezone(datetime.timedelta(hours=-5))


def git(args):
    r = subprocess.run(["git"] + args, cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout


def gdate(s):
    return datetime.datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S %z")


def load_history():
    commits = {}
    for line in git(["log", "--date=iso", "--pretty=%h|%ad|%s", "--all"]).splitlines():
        p = line.split("|", 2)
        if len(p) == 3 and p[0] not in commits:
            commits[p[0]] = (gdate(p[1]), p[2])

    reflog = []
    for line in git(["reflog", "--date=iso", "--pretty=%h|%gd|%gs"]).splitlines():
        p = line.split("|", 2)
        if len(p) < 3:
            continue
        raw = p[1][p[1].find("{") + 1: p[1].rfind("}")]
        try:
            reflog.append((gdate(raw), p[0], p[2]))
        except ValueError:
            pass
    reflog.sort(key=lambda t: t[0])

    def path_log(path):
        out = []
        for line in git(["log", "--date=iso", "--pretty=%h|%ad|%s", "--", path]).splitlines():
            p = line.split("|", 2)
            if len(p) == 3:
                out.append((gdate(p[1]), p[0], p[2]))
        out.sort(key=lambda t: t[0])
        return out

    return commits, reflog, path_log("tools/sigbypass-mod"), \
        path_log("tools/sigbypass-mod/tutorial_launch.cpp"), path_log("server")


def last_le(seq, dt):
    best = None
    for e in seq:
        if e[0] <= dt:
            best = e
        else:
            break
    return best


def crash_time(r):
    """(datetime|None, source).  TimeOfCrash if present, else the artifact mtime."""
    s = r.get("time_of_crash_utc") or ""
    if s:
        try:
            d = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=datetime.timezone.utc)
            return d, "TimeOfCrash"
        except ValueError:
            pass
    s = r.get("xml_mtime_local") or ""
    if s:
        try:
            return datetime.datetime.fromisoformat(s).replace(tzinfo=LOCAL), "mtime"
        except ValueError:
            pass
    return None, "none"


def classify(r):
    if r["kind"] == "degenerate":
        return "degenerate"
    if r["source"] == "uecc":
        return "uecc"
    return "crashpad" if r["report_is_primary"] == "1" else "dupe"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    commits, reflog, shim, tut, srv = load_history()
    rows = list(csv.DictReader(open(a.corpus, newline="", encoding="utf-8")))

    for r in rows:
        d, src = crash_time(r)
        r["_dt"], r["_tsrc"] = d, src
        r["_loc"] = d.astimezone(LOCAL) if d else None
        r["_day"] = r["_loc"].strftime("%Y-%m-%d") if d else ""
        r["_cls"] = classify(r)
        h = last_le(reflog, d) if d else None
        sv = last_le(shim, d) if d else None
        tv = last_le(tut, d) if d else None
        sr = last_le(srv, d) if d else None
        r["_head"] = h[1] if h else ""
        r["_head_when"] = h[0].isoformat() if h else ""
        r["_head_subj"] = commits.get(h[1], (None, ""))[1] if h else ""
        r["_head_age_h"] = round((d - h[0]).total_seconds() / 3600.0, 3) if (h and d) else ""
        r["_shim"] = sv[1] if sv else ""
        r["_shim_when"] = sv[0].isoformat() if sv else ""
        r["_shim_subj"] = sv[2] if sv else ""
        r["_tut"] = tv[1] if tv else ""
        r["_srv"] = sr[1] if sr else ""

    real = [r for r in rows if r["_cls"] in ("uecc", "crashpad")]

    # ------------------------------------------------------------------ CSV
    cols = ["source", "kind", "artifact_id", "crash_guid", "report_is_primary",
            "archive_label", "crash_type", "seconds_since_start", "log_route",
            "unwind_status", "pcallstack_hash", "error_message", "assert_file",
            "assert_line", "minidump_bytes"]
    extra = ["_cls", "_day", "_tsrc", "_head", "_head_when", "_head_age_h",
             "_head_subj", "_shim", "_shim_when", "_shim_subj", "_tut", "_srv"]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["class", "day_local", "time_local", "time_source"]
                   + [c for c in cols]
                   + ["head_sha", "head_committed", "head_age_hours", "head_subject",
                      "shim_vintage", "shim_committed", "shim_subject",
                      "tutorial_launch_vintage", "server_vintage"])
        for r in sorted(rows, key=lambda x: (x["_dt"] or datetime.datetime.min.replace(
                tzinfo=datetime.timezone.utc))):
            w.writerow([r["_cls"], r["_day"],
                        r["_loc"].strftime("%Y-%m-%d %H:%M:%S") if r["_loc"] else "",
                        r["_tsrc"]]
                       + [r.get(c, "") for c in cols]
                       + [r["_head"], r["_head_when"], r["_head_age_h"], r["_head_subj"],
                          r["_shim"], r["_shim_when"], r["_shim_subj"], r["_tut"], r["_srv"]])
    if a.quiet:
        return

    P = print
    P("corpus rows      : %d" % len(rows))
    P("real deaths      : %d  (uecc %d + crashpad-primary %d)" % (
        len(real), sum(1 for r in real if r["_cls"] == "uecc"),
        sum(1 for r in real if r["_cls"] == "crashpad")))
    P("excluded         : degenerate %d, duplicate crashpad copies %d" % (
        sum(1 for r in rows if r["_cls"] == "degenerate"),
        sum(1 for r in rows if r["_cls"] == "dupe")))
    P("reflog entries   : %d  %s .. %s" % (len(reflog), reflog[0][0].date(), reflog[-1][0].date()))
    P("commits (--all)  : %d" % len(commits))
    P("wrote            : %s" % a.out)

    # --------------------------------------------------------------- per day
    P("\n=== A1. PER LOCAL DAY ===")
    cbyday = collections.Counter()
    for sha, (d, s) in commits.items():
        cbyday[d.astimezone(LOCAL).strftime("%Y-%m-%d")] += 1
    days = sorted({r["_day"] for r in rows if r["_day"]} | set(cbyday))
    P("%-12s %5s %5s %5s %6s | %7s  %-9s %s" %
      ("day", "uecc", "cpad", "degen", "DEATHS", "commits", "HEAD@EOD", "subject"))
    for d in days:
        g = [r for r in rows if r["_day"] == d]
        u = sum(1 for r in g if r["_cls"] == "uecc")
        c = sum(1 for r in g if r["_cls"] == "crashpad")
        dg = sum(1 for r in g if r["_cls"] == "degenerate")
        eod = datetime.datetime.strptime(d, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=LOCAL)
        h = last_le(reflog, eod)
        P("%-12s %5d %5d %5d %6d | %7d  %-9s %s" %
          (d, u, c, dg, u + c, cbyday.get(d, 0), h[1] if h else "-",
           (commits.get(h[1], (None, ""))[1][:56] if h else "(pre-repo)")))

    # ------------------------------------------------------------ per HEAD
    P("\n=== A2. PER HEAD COMMIT (real deaths) ===")
    byh = collections.defaultdict(list)
    for r in real:
        byh[r["_head"]].append(r)
    P("%-9s %-17s %4s  %-30s %s" % ("head", "committed", "n", "routes", "subject"))
    for sha in sorted(byh, key=lambda s: commits.get(
            s, (datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),))[0]):
        g = byh[sha]
        rt = collections.Counter(x["log_route"] or "(nolog)" for x in g)
        P("%-9s %-17s %4d  %-30s %s" % (
            sha or "(pre-repo)",
            commits[sha][0].strftime("%Y-%m-%d %H:%M") if sha in commits else "-",
            len(g), ",".join("%s:%d" % kv for kv in rt.most_common()),
            (commits[sha][1][:58] if sha in commits else "")))

    # --------------------------------------------------------- shim vintage
    P("\n=== C. PER SHIM-SOURCE VINTAGE (tools/sigbypass-mod) ===")
    sv = collections.Counter(r["_shim"] for r in real)
    P("%-9s %-17s %5s  %s" % ("vintage", "committed", "n", "subject"))
    P("%-9s %-17s %5d  %s" % ("(pre)", "-", sv.get("", 0), "before any shim source existed"))
    for (d, sha, subj) in shim:
        if sv.get(sha):
            P("%-9s %-17s %5d  %s" % (sha, d.strftime("%Y-%m-%d %H:%M"), sv[sha], subj[:62]))
    P("current shim vintage: %s (%s)  deaths under it: %d" % (
        shim[-1][1], shim[-1][0].strftime("%Y-%m-%d %H:%M"), sv.get(shim[-1][1], 0)))
    P("previous vintage    : %s (%s)  deaths under it: %d" % (
        shim[-2][1], shim[-2][0].strftime("%Y-%m-%d %H:%M"), sv.get(shim[-2][1], 0)))

    # ------------------------------------------------------------ route mix
    P("\n=== B1. ROUTE SPLIT ===")
    for name, sub in (("all real", real),
                      ("uecc", [r for r in real if r["_cls"] == "uecc"]),
                      ("crashpad", [r for r in real if r["_cls"] == "crashpad"]),
                      ("degenerate", [r for r in rows if r["_cls"] == "degenerate"])):
        c = collections.Counter(r["log_route"] or "(no log)" for r in sub)
        P("  %-11s N=%-4d %s" % (name, len(sub), dict(c.most_common())))

    P("\n=== B4. ROUTE x SecondsSinceStart bucket (real) ===")
    def bucket(r):
        try:
            s = int(r["seconds_since_start"])
        except (TypeError, ValueError):
            return "(none)"
        for hi, lbl in ((1, "0"), (60, "<60"), (120, "60-119"), (200, "120-199"),
                        (300, "200-299"), (600, "300-599")):
            if s < hi:
                return lbl
        return ">=600"
    t = collections.Counter((r["log_route"] or "(nolog)", bucket(r)) for r in real)
    bks = ["0", "<60", "60-119", "120-199", "200-299", "300-599", ">=600"]
    P("%-20s %s" % ("route", " ".join("%-9s" % b for b in bks)))
    for rt in sorted({k[0] for k in t}):
        P("%-20s %s" % (rt, " ".join("%-9d" % t[(rt, b)] for b in bks)))

    # ----------------------------------------------- tutorial timing by era
    P("\n=== C/B. TUTORIAL-ROUTE SecondsSinceStart BY BUILD ERA ===")
    def era(day):
        if day < "2026-07-13":
            return "A 2026-07-09..12"
        if day < "2026-08-01":
            return "B 2026-07-24..26"
        return "C 2026-08-03..05"
    g = collections.defaultdict(list)
    for r in real:
        if r["log_route"] == "tutorial":
            g[era(r["_day"])].append(int(r["seconds_since_start"]))
    for k in sorted(g):
        v = sorted(g[k])
        P("  %-18s n=%-3d med=%-7.1f in 173-201s: %d/%d   in 255-340s: %d/%d   %s" % (
            k, len(v), statistics.median(v),
            sum(1 for x in v if 173 <= x <= 201), len(v),
            sum(1 for x in v if 255 <= x <= 340), len(v), v))

    # ------------------------------------------------------------ degenerate
    P("\n=== D. DEGENERATE ROWS (no TimeOfCrash; time_source=mtime) ===")
    for r in sorted([x for x in rows if x["_cls"] == "degenerate"], key=lambda x: x["_dt"]):
        P("  %-50s %s  HEAD=%-9s shim=%-9s files=%s" % (
            r["artifact_id"][:50], r["_loc"].strftime("%Y-%m-%d %H:%M:%S"),
            r["_head"], r["_shim"], r["dir_files"]))


if __name__ == "__main__":
    sys.exit(main())
