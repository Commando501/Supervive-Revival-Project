#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harvest_addrs.py -- sweep the whole project for recorded SUPERVIVE code addresses.

Sources swept (all read-only):
    docs/**                                  (md / txt / log / any text)
    tools/sigbypass-mod/*.cpp *.h            (the shims that HARDCODE these offsets)
    tools/re/*.py                            (RPM probes)
    CLAUDE.md
    memory/*.md                              (user's project memory)
    git log (all commit messages, full body)

Emits a JSON list of {rva, contexts:[{file,line,text,name_hint}], ...}.

Two harvest patterns, both deliberately conservative:

  A. ANCHORED   `base+0x...`, `g_base + 0x...`, `module+0x...`, `imagebase+0x...`
     -- unambiguous: the record itself says "this is a module RVA".
  B. BARE       a bare 0x hex literal whose VALUE lands in .text [0x1000,0x764A000)
     AND has >= 6 hex digits.  6 digits => >= 0x100000 (1 MB), which is past every
     plausible struct offset / size constant in this project.  Bare literals below
     that are NOT harvested: they would be dominated by field offsets (+0x354,
     +0x3B8, +0x568 ...) and would poison the table.

Both are recorded with their `kind` so downstream can weight them differently.
No inference here -- this file only collects what is WRITTEN DOWN.
"""

import json
import os
import re
import subprocess
import sys

ROOT = r"G:\git\Supervive Revival Project"
MEMDIR = r"C:\Users\eastr\.claude\projects\G--git-Supervive-Revival-Project\memory"

TEXT_LO, TEXT_HI = 0x1000, 0x764A000          # .text, from the dump's section table

ANCHORED = re.compile(
    r"(?:\b(?:g_)?(?:base|Base|BASE|imagebase|ImageBase|modbase|ModBase|module|Module|mod|"
    r"kBase|pBase|hMod|hModule|main_base|game_base|exe|Exe)\b\s*[+]\s*)0x([0-9A-Fa-f]{4,9})")
BARE = re.compile(r"(?<![0-9A-Fa-fx])0x([0-9A-Fa-f]{6,8})\b")

BARE_MIN = 0x100000     # 1 MB.  Below this a bare literal is overwhelmingly an FName
                        # index / UFunction flag word / size, not a recorded RVA.
                        # NOTE this is a HARVEST filter, not a claim that no function
                        # lives below 1 MB -- .text starts at 0x1000.  It only means
                        # this project has never WRITTEN DOWN one that low.

# A literal introduced by one of these keys is a value, not an address.  Measured
# against the actual corpus: 'flags=0x00020401' (UFunction flags), 'kType_Hero =
# 0x0001A568' (FName index), 'ufunc=/thunk=' (absolute, different base).
REJECT_KEY = re.compile(
    r"(?:\b(?:flags?|hash|checksum|crc|guid|uuid|size|sizeof|len|length|mask|index|idx|"
    r"count|num|version|seed|colou?r|time|port|magic|tag|token|key|value|val|type|"
    r"ufunc|thunk|obj|objp|cdo|pak|toc|chunk|entry_?id|netguid|classid|typeid|"
    r"k[A-Z][A-Za-z_]*(?:Type|Id|Flags|Hash|Index|Size))\b\s*[:=]?\s*$)",
    re.I)

# Positive signal that the record MEANS a code address.
LABEL_KEY = re.compile(
    r"(?:\b(?:rva|va|addr|address|fn|func|function|sub|entry|thunkrva|call|jmp|hook|"
    r"target|slot|vtbl|vtable|offset|off|at|@|code)\b\W{0,4}$)", re.I)

# tokens that are never a symbol name
STOP = set("""the a an and or of to in on at for with from by is are was were be been it its
this that these those we our they their you your he she his her as if then than so but not
no yes all any some each one two three four five six seven eight nine ten first second third
new old real true false null none void int char bool byte word dword qword float double
size len length count num number index idx offset addr address rva va ptr pointer ref refs
value val data code text func fn function call calls called caller callee return returns
line lines file files doc docs note notes see read write set get put post http https www com
session sessions s1 s2 s3 step steps fix fixed fixes bug bugs work works working test tests
tested ok good bad wrong right left up down top bottom high low mid live dead open close
found find finds hook hooks hooked shim shims dll exe game client server backend menu
TODO FIXME NOTE WARN XXX HACK""".split())

EXTS = {".md", ".txt", ".log", ".cpp", ".h", ".hpp", ".c", ".py", ".ps1", ".go", ".json", ".csv"}

# This tool's OWN outputs live under docs/.  Sweeping them feeds the harvest its
# own results (683 -> 905 addresses on the second run, all of the growth being
# echo).  Exclude them explicitly.
SELF_OUTPUT = {"docs/symbols.csv", "docs/strxref-known-addresses.md"}

# identifiers that look like a symbol: CamelCase, snake_case_with_caps, or A::B
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}(?:::[A-Za-z_][A-Za-z0-9_]*)*")


def name_hints(ctx):
    """Pull plausible symbol names out of a context window.

    Heuristic and reported as such: a hint is a token that looks like a C++/UE
    identifier (contains an interior capital or '::' or a leading 'k'/'U'/'A'/'F'
    prefix) and is not an English stopword.  Downstream RANKS these; nothing here
    is treated as fact.
    """
    out = []
    for m in IDENT.finditer(ctx):
        t = m.group(0)
        if t.lower() in STOP:
            continue
        if len(t) < 4:
            continue
        # 'x587BE90' -- the tail of the hex literal itself.  The first version of
        # this harvest recorded those AS the function name for ~200 addresses.
        if re.fullmatch(r"[xX][0-9A-Fa-f]{4,}", t) or re.fullmatch(r"[0-9A-Fa-f]{4,}", t):
            continue
        has_inner_cap = any(c.isupper() for c in t[1:])
        if "::" in t or has_inner_cap:
            out.append(t)
    return out


def sweep_text(path, rel, blob, acc):
    for lineno, line in enumerate(blob.splitlines(), 1):
        if "0x" not in line:
            continue
        ltext = line.strip()[:400]
        seen_spans = []
        for m in ANCHORED.finditer(line):
            v = int(m.group(1), 16)
            seen_spans.append(m.span(1))
            record(acc, v, rel, lineno, ltext, line, m.start(), "anchored")
        for m in BARE.finditer(line):
            if any(a <= m.start(1) < b for a, b in seen_spans):
                continue
            v = int(m.group(1), 16)
            if not (BARE_MIN <= v < TEXT_HI):
                continue
            pre = line[max(0, m.start() - 40): m.start()]
            if REJECT_KEY.search(pre):
                continue
            kind = "labeled" if LABEL_KEY.search(pre) else "bare"
            record(acc, v, rel, lineno, ltext, line, m.start(), kind)


def record(acc, v, rel, lineno, ltext, line, pos, kind):
    ctx = line[max(0, pos - 160): pos + 160]
    e = acc.setdefault(v, {"rva": v, "kind": set(), "ctx": []})
    e["kind"].add(kind)
    if len(e["ctx"]) < 24:
        e["ctx"].append({"file": rel, "line": lineno, "text": ltext,
                         "hints": name_hints(ctx), "kind": kind})


def main():
    acc = {}
    files = []

    for base, sub in ((os.path.join(ROOT, "docs"), "docs"),
                      (os.path.join(ROOT, "tools", "sigbypass-mod"), "tools/sigbypass-mod"),
                      (os.path.join(ROOT, "tools", "re"), "tools/re"),
                      (os.path.join(ROOT, "tools", "inject"), "tools/inject"),
                      (os.path.join(ROOT, "configs"), "configs"),
                      (MEMDIR, "memory")):
        if not os.path.isdir(base):
            continue
        for dp, _dn, fn in os.walk(base):
            for f in fn:
                if os.path.splitext(f)[1].lower() not in EXTS:
                    continue
                p = os.path.join(dp, f)
                rel = sub + "/" + os.path.relpath(p, base).replace("\\", "/")
                if rel in SELF_OUTPUT:
                    continue
                files.append((p, rel))

    for extra in ("CLAUDE.md",):
        p = os.path.join(ROOT, extra)
        if os.path.exists(p):
            files.append((p, extra))

    nbytes = 0
    for p, rel in files:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                blob = fh.read()
        except OSError:
            continue
        nbytes += len(blob)
        sweep_text(p, rel, blob, acc)

    # git log -- all commit messages
    try:
        out = subprocess.run(["git", "-C", ROOT, "log", "--format=%H%n%B%n---GITSEP---"],
                             capture_output=True, text=True, timeout=180, encoding="utf-8",
                             errors="replace")
        sweep_text(None, "git-log", out.stdout, acc)
    except Exception as ex:                                    # noqa: BLE001
        print("git log sweep failed: %s" % ex, file=sys.stderr)

    res = []
    for v, e in sorted(acc.items()):
        e["kind"] = sorted(e["kind"])
        e["nsrc"] = len({(c["file"], c["line"]) for c in e["ctx"]})
        res.append(e)

    outp = os.path.join(ROOT, "tools", "strxref", "index", "harvest.json")
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)

    intext = sum(1 for e in res if TEXT_LO <= e["rva"] < TEXT_HI)
    print("files swept        : %d  (%.1f MB)" % (len(files), nbytes / 1e6))
    print("distinct addresses : %d" % len(res))
    for k in ("anchored", "labeled", "bare"):
        print("  %-14s   : %d" % (k, sum(1 for e in res if k in e["kind"])))
    print("  in shim source   : %d" % sum(
        1 for e in res if any(c["file"].startswith(("tools/sigbypass-mod", "tools/re"))
                              for c in e["ctx"])))
    print("  land in .text    : %d" % intext)
    print("  outside .text    : %d" % (len(res) - intext))
    print("-> %s" % outp)


if __name__ == "__main__":
    main()
