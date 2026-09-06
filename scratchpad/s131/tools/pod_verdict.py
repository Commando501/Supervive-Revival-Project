#!/usr/bin/env python3
"""
S131 -- evaluate a pod-state dump against the PRE-REGISTERED predictions.

Written BEFORE the flight landed, so the reading rule cannot be tuned to the data.
Source of the rule: scratchpad/s131/evidence/PREREG-s131-pod-functionality.md sections 2.1-2.7.

Usage:  python scratchpad/s131/tools/pod_verdict.py <marker-or-result-file> [more files...]

It parses only what the probe prints, and it deliberately reports UNINTERPRETABLE rather than
guessing whenever the probe said "NOT RESOLVED", the calibration failed, or an AS-vs-live offset
disagreed -- the whole point of those states is that they are not values.
"""
import re, sys, collections

# ---- the pre-registered expectations -------------------------------------------------------------
# (field, class default as it will PRINT, value the S131 call writes, discriminates?)
DISCRIM = [
    ("PodTeamIndex",       "-1",     "0",        True),
    ("CurrPodDestination", "(0.0, 0.0, 0.0)", "<the arm's LandingLocation>", True),
    ("bIsTeamLeaderPod",   "false",  "true",     True),
    ("LeaderPod",          "null",   "null",     False),   # the TRAP -- can only ever agree
]
# StartPodGameplay receipts: predicted UNCHANGED even on a fully successful spawn
INERT = [
    ("bHasStartedGameplay",  "false"),
    ("PodMeshComponent",     "null"),
    ("bIsLocalPlayerPilot",  "false"),
    ("bPilotHasPodControl",  "false"),
]

HDR   = re.compile(r"^\[PD\] ===== POD STATE \((.+?)\) -- (\d+) pod ACTOR\(s\), latched by the '(.+?)' census(.*?)=====")
POD   = re.compile(r"^\[PD\] pod\[(\d+)\] (0x[0-9A-Fa-f]+) '(.+?)' cls=(\S+)\s*(.*)$")
# ⚠ The probe prints the offset with `@0x%-4X`, so a short offset is followed by TWO spaces, not one.
#   The first cut of this regex had a single literal space here and matched NOTHING -- and the tool
#   then reported "UNINTERPRETABLE (nothing resolved)" for pods whose values are plainly in the log.
#   That is this project's own dominant failure mode committed inside the verdict tool: an instrument
#   blind spot presented as a result. Caught only by reading the raw marker beside the tool's output.
FIELD = re.compile(r"^\[PD\]   (\S+)\s+@0x([0-9A-Fa-f]+)\s+(\S+)\s+size=(\d+)\s+= (.*?)\s*$")
NOTRES= re.compile(r"^\[PD\]   (\S+)\s+\*\*\* NOT RESOLVED BY NAME")
LOC   = re.compile(r"^\[PD\]   location: \((.+?)\)\s+(.*)$")
CAL   = re.compile(r"^\[PD\] by-name CALIBRATION on (\S+): bCanEverReplicate -> 0x(\S+) vs \[M\] 0x(\S+) = (.+?) \| bEnablePooling -> 0x(\S+) vs \[M\] 0x(\S+) = (.+?)\s*$")
RIDE  = re.compile(r"^\[PD\] rideable-component census: (\d+) object\(s\)")
RIDEE = re.compile(r"^\[PD\]   rideable\[(\d+)\] (0x[0-9A-Fa-f]+) '(.+?)' cls=(\S+)(.*)$")
END   = re.compile(r"^\[PD\] ===== POD STATE \((.+?)\) end\. AS-vs-live offsets: (\d+) agree, (\d+) DISAGREE, (\d+) name lookups")
LAND  = re.compile(r"E1 POSITIONS USED:.*Landing=\((.+?)\)")


def parse(paths):
    dumps, cur, pod = [], None, None
    landing = None
    for p in paths:
        for raw in open(p, encoding="utf-8", errors="replace"):
            line = raw.rstrip("\r\n")
            m = LAND.search(line)
            if m: landing = m.group(1)
            m = HDR.match(line)
            if m:
                cur = {"when": m.group(1), "npods": int(m.group(2)), "latch": m.group(3),
                       "overflow": "OVERFLOW" in m.group(4), "pods": [], "cal": None,
                       "ride": None, "ride_list": [], "agree": None, "src": p}
                dumps.append(cur); pod = None; continue
            if cur is None: continue
            m = RIDE.match(line)
            if m: cur["ride"] = int(m.group(1)); continue
            m = RIDEE.match(line)
            if m: cur["ride_list"].append((m.group(2), m.group(4), "ARCHETYPE" in m.group(5))); continue
            m = CAL.match(line)
            if m: cur["cal"] = {"cls": m.group(1), "repl": m.group(4).strip(), "pool": m.group(7).strip()}; continue
            m = POD.match(line)
            if m:
                pod = {"idx": int(m.group(1)), "addr": m.group(2), "name": m.group(3),
                       "cls": m.group(4), "new": "NEW since" in m.group(5), "f": {}, "loc": None,
                       "notres": []}
                cur["pods"].append(pod); continue
            m = NOTRES.match(line)
            if m and pod is not None: pod["notres"].append(m.group(1)); continue
            m = FIELD.match(line)
            if m and pod is not None:
                pod["f"][m.group(1)] = {"off": m.group(2), "type": m.group(3),
                                        "val": m.group(5), "as": "AGREE" in m.group(5),
                                        "dis": "DISAGREE" in m.group(5)}
                continue
            m = LOC.match(line)
            if m and pod is not None: pod["loc"] = (m.group(1), m.group(2)); continue
            m = END.match(line)
            if m: cur["agree"] = (int(m.group(2)), int(m.group(3)), int(m.group(4))); pod = None; continue
    return dumps, landing


def val(pod, name):
    f = pod["f"].get(name)
    if f is None:
        return "NOT RESOLVED" if name in pod["notres"] else None
    # the printed value carries a trailing " | AS 0x... AGREE" cross-check; strip it
    return re.sub(r"\s*\|\s*AS .*$", "", f["val"]).strip()


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    dumps, landing = parse(sys.argv[1:])
    if not dumps:
        print("NO POD-STATE DUMP FOUND in the given file(s).")
        print("That is an INSTRUMENT statement, not a world statement: it means the probe never")
        print("reached PdPodDump (never armed / ladder never advanced / E1 never dispatched).")
        return 1

    print("=" * 100)
    print("S131 POD VERDICT -- evaluated against the PRE-REGISTERED rule (PREREG sections 2.1-2.7)")
    print("=" * 100)
    if landing: print("arm's LandingLocation, from its own log line: (%s)" % landing)
    print()

    void_reasons = []
    for d in dumps:
        print("-" * 100)
        print("DUMP '%s'   pods=%d   latched by census '%s'%s   [%s]" %
              (d["when"], d["npods"], d["latch"], "  ** LATCH OVERFLOWED **" if d["overflow"] else "", d["src"]))
        if d["overflow"]: void_reasons.append("latch overflow in dump '%s' -- counts are lower bounds" % d["when"])
        if d["cal"]:
            c = d["cal"]
            print("  calibration on %s: bCanEverReplicate=%s  bEnablePooling=%s" % (c["cls"], c["repl"], c["pool"]))
            if "MISMATCH" in c["repl"] or "MISMATCH" in c["pool"]:
                void_reasons.append("CALIBRATION MISMATCH in dump '%s' -- every field value is UNINTERPRETABLE" % d["when"])
        else:
            print("  calibration: not printed in this dump")
        if d["ride"] is not None:
            live = [r for r in d["ride_list"] if not r[2]]
            print("  rideable components: %d total (%d shown, %d of those NOT archetypes)" %
                  (d["ride"], len(d["ride_list"]), len(live)))
            if d["ride"] == 0:
                print("  => the rider branch is UNREACHABLE; this dump says NOTHING about the fifth wall")
        if d["agree"]:
            a, dis, nf = d["agree"]
            print("  AS-vs-live offsets: %d agree, %d DISAGREE, %d name lookups failed" % (a, dis, nf))
            if dis: void_reasons.append("%d AS/live offset DISAGREEments in dump '%s'" % (dis, d["when"]))

        for p in d["pods"]:
            init = []
            for name, dflt, written, disc in DISCRIM:
                v = val(p, name)
                if v is None:      state = "absent-from-log"
                elif v == "NOT RESOLVED": state = "NOT RESOLVED"
                elif name == "CurrPodDestination":
                    state = "DEFAULT" if v.startswith("(0.0, 0.0, 0.0)") else "WRITTEN"
                elif name == "bIsTeamLeaderPod":
                    state = "WRITTEN" if v.startswith("true") else "DEFAULT"
                elif name == "LeaderPod":
                    state = "null(both)" if v == "null" else "NON-NULL(!)"
                else:
                    state = "WRITTEN" if v == written else ("DEFAULT" if v == dflt else "OTHER:%s" % v)
                if disc: init.append(state)
                print("    pod[%d] %-20s %-14s %s" % (p["idx"], name, state, v if v is not None else ""))
            nw = sum(1 for s in init if s == "WRITTEN")
            nd = sum(1 for s in init if s == "DEFAULT")
            if nw == 3:   verdict = "InitializeDropPod RAN and its writes landed"
            elif nd == 3: verdict = "InitializeDropPod did NOT run (all three at class defaults)"
            elif nw or nd: verdict = "MIXTURE (%d written / %d default) -- read the write order" % (nw, nd)
            else:         verdict = "UNINTERPRETABLE (nothing resolved)"
            print("    pod[%d] %s  cls=%s addr=%s  ==> %s" %
                  (p["idx"], "NEW " if p["new"] else "pre-existing", p["cls"], p["addr"], verdict))
            inert = [(n, val(p, n)) for n, _ in INERT]
            print("    pod[%d] StartPodGameplay receipts: %s" %
                  (p["idx"], ", ".join("%s=%s" % (n, v) for n, v in inert)))
            if p["loc"]:
                print("    pod[%d] location (%s) %s" % (p["idx"], p["loc"][0], p["loc"][1]))
        print()

    print("=" * 100)
    if void_reasons:
        print("*** THE FOLLOWING PRE-REGISTERED VOID/CAVEAT CONDITIONS FIRED ***")
        for r in void_reasons: print("  - " + r)
    else:
        print("No pre-registered VOID condition fired.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
