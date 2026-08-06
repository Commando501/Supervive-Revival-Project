#!/usr/bin/env python
"""fk8_classify.py -- classify a crash dump into the known SELF-INFLICTED families.

    python fk8_classify.py <dump.dmp|archive-dir> [...]
    python fk8_classify.py dumps/crashpad-*            # globs fine

WHY THIS EXISTS.  docs/fk8-crash-timing-mined.md established that >=36 of the project's 114
recorded deaths are self-inflicted, in two families that are trivially separable from the
exception record alone -- and that the project had been attributing them to injection spacing
and to FK-7 instead.  The write-up's own recommendation is: classify by `RIP & 0xFFFF` BEFORE
attributing any death to anything.  This is that check, as a tool.

THE DISCRIMINATORS (all MEASURED, docs/fk8-crash-timing-mined.md §3.1):

  family A -- the anti-tamper PROTECTOR's poison jump
      RIP == accessed address == <runtime.dll base> + 1
      ExceptionInformation[0] == 8   (EXECUTE -- a DEP fault on a read-only image page)
      RIP inside no registered module
      Corpus examples: 0x7FF90E000001, 0x7FF8F0400001, 0x7FFB9EE00001, 0x7FFDF4200001
      !! CLAUDE.md's "poison RIP 0x7FF90E000001" is ONE BOOT's instance of a general
         <base>+1 signature.  Match the SHAPE, never the literal address.

  family B -- OUR OWN catalog_store_fix.dll heap scan (fixed 2026-08-05, S111)
      RIP & 0xFFFF == 0x205d         (that DLL's .text RVA of FindCatalogManagers_first)
      ExceptionInformation[0] == 0   (READ)
      RIP - 0x205d is 64 KB-aligned, in a region belonging to no registered module
      !! The 0x205d offset is specific to the PRE-FIX build (.text sha 4c9f1604, 86528 B).
         The fixed build is 202a6c7d / 87040 B, so a post-fix scan fault would land at a
         DIFFERENT offset.  A "no 0x205d" result on a post-fix dump is therefore weaker
         evidence than it looks -- also check whether RIP lands in ANY unregistered region
         with a READ fault, which is what `shape=scan-like` below reports.

CAVEAT, and it is the one that matters: this reads the EXCEPTION STREAM's own ThreadContext
(stream 6 + 160), NOT MINIDUMP_THREAD.ThreadContext for the crashed tid.  Reading the latter
yields the DUMP WRITER's state and manufactures "every crash is at one identical address"
(22/22) -- one of the three parser traps this corpus pass caught.  mdexc.Lean does it right;
do not swap it for a hand-rolled reader.

Stdlib only.  READ-ONLY on every path it touches.
"""
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mdexc import summarize  # noqa: E402

ACCESS = {0: "READ", 1: "WRITE", 8: "EXECUTE"}


def classify(path):
    r = summarize(path)
    if not r or not r.get("ok"):
        return {"dump": path, "family": "UNREADABLE", "why": (r or {}).get("err", "?")}
    rip = r.get("rip") or 0
    addr = r.get("exc_addr") or 0
    parms = r.get("exc_parms") or []
    acc = parms[0] if parms else None
    low16 = rip & 0xFFFF
    in_mod = bool(r.get("rip_mod"))

    fam, why = "UNCLASSIFIED", []
    if low16 == 0x0001 and acc == 8 and rip == addr and not in_mod:
        fam = "A-protector"
        why.append("RIP==accessed==base+1, EXECUTE, no module")
    elif low16 == 0x205D and acc == 0:
        fam = "B-catalog_store_fix(PRE-FIX)"
        why.append("RIP&0xFFFF==0x205d, READ")
    else:
        if acc == 0 and not in_mod:
            fam = "shape=scan-like(UNREGISTERED REGION, READ)"
            why.append("READ fault outside every registered module -- treat as possible shim scan")
        elif in_mod:
            fam = "in-module:%s" % r.get("rip_mod")
        why.append("low16=0x%04X acc=%s" % (low16, ACCESS.get(acc, acc)))
    return {
        "dump": path, "family": fam, "rip": rip, "addr": addr,
        "acc": ACCESS.get(acc, acc), "low16": low16,
        "rip_mod": r.get("rip_mod") or "-", "why": "; ".join(why),
    }


def expand(args, dedupe=True):
    """Collect .dmp paths.

    ⚠ DEDUPE BY REPORT UUID BY DEFAULT, and do not turn it off casually.
    `configs/archive-crashdumps.ps1` snapshots the whole crashpad database BOTH before a launch
    AND after the game exits, so a single death is normally archived 2+ times under different
    `crashpad-<stamp>-<label>` directories (docs/fk8-crash-timing-mined.md §1.1: 45 archives held
    47 .dmp files but only 22 DISTINCT reports; one uuid appeared in 4 archives).  Counting
    archives, or counting .dmp files, inflates the death count.  Caught doing exactly that during
    the S111 run series -- 3 files, 2 real deaths.  The uuid IS the report identity.
    """
    out = []
    for a in args:
        for p in (glob.glob(a) or [a]):
            if os.path.isdir(p):
                out += sorted(glob.glob(os.path.join(p, "**", "*.dmp"), recursive=True))
            elif p.lower().endswith(".dmp"):
                out.append(p)
    if not dedupe:
        return out
    seen, uniq, dropped = set(), [], 0
    for p in out:
        uuid = os.path.splitext(os.path.basename(p))[0]
        if uuid in seen:
            dropped += 1
            continue
        seen.add(uuid)
        uniq.append(p)
    if dropped:
        print("[dedupe] %d duplicate archive copies dropped; %d distinct report uuid(s)\n"
              % (dropped, len(uniq)))
    return uniq


if __name__ == "__main__":
    paths = expand(sys.argv[1:])
    if not paths:
        print(__doc__)
        sys.exit(2)
    tally = {}
    for p in paths:
        c = classify(p)
        tally[c["family"]] = tally.get(c["family"], 0) + 1
        print("%-52s %-32s RIP=0x%X acc=%s low16=0x%04X mod=%s"
              % (os.path.basename(os.path.dirname(os.path.dirname(p))) or os.path.basename(p),
                 c["family"], c.get("rip", 0), c.get("acc"), c.get("low16", 0), c.get("rip_mod")))
    print("\n-- tally --")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print("  %-40s %d" % (k, v))
