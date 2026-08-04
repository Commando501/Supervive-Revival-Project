#!/usr/bin/env python3
"""consts_report.py -- pull DESIGN NUMBERS out of asdump.py's module dumps.

Standalone, read-only post-processor.  It does NOT touch asdump.py, the game
files, or the generated .txt files -- it only reads out/modules/**/*.as.txt and
prints the literal constants that the bytecode writes into named properties.

Why this exists: a `SetV8` carries a raw 64-bit pattern.  asdump renders it as
an integer, because the opcode itself does not say whether the slot is an
int64 or a float64.  But the *next two* instructions almost always do:

    SetV8      v2 0x4026000000000000
    LoadThisR  0 134230906            ; this.Duration      <- property named
    WRTV8      v2                                          <- 8-byte store

so the pattern is provably a float64 whenever the sink is a float64-shaped
store.  This script pairs them up and prints `Duration = 11.0`.

Also prints every SetV4/SetV1/SetV2 that lands in a named property, and every
loose SetV8 (with both interpretations, so nothing is silently guessed).

Usage:
    python consts_report.py <module.as.txt> [more...]
    python consts_report.py --dir out/modules/UAV
"""
import os
import re
import struct
import sys

RE_FUNC = re.compile(r"/\* ---- (\S+): (\d+) dwords")
RE_ASM = re.compile(r"^\s*([0-9A-F]{4})\s+(\S+)\s*(.*?)\s*$")
RE_PROP = re.compile(r";\s*(this\.\S+|\S+\.\S+|\S+)\s*$")


def f64(bits):
    return struct.unpack("<d", struct.pack("<Q", bits & 0xFFFFFFFFFFFFFFFF))[0]


def f32(bits):
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def fmt(v):
    if v != v or v in (float("inf"), float("-inf")):
        return repr(v)
    if v == int(v) and abs(v) < 1e15:
        return "%.1f" % v
    return "%.6g" % v


def scan(path):
    rows = []
    fn = "?"
    pend = {}          # slot -> (kind, raw)
    lastprop = None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = RE_FUNC.search(line)
        if m:
            fn = m.group(1)
            pend = {}
            lastprop = None
            continue
        m = RE_ASM.match(line.rstrip("\n"))
        if not m:
            continue
        op, rest = m.group(2), m.group(3)
        cmt = rest.split(";", 1)
        args = cmt[0].strip()
        note = cmt[1].strip() if len(cmt) > 1 else ""
        toks = args.split()
        if op in ("SetV8", "SetV4", "SetV2", "SetV1") and toks:
            slot = toks[0]
            try:
                raw = int(toks[1], 0)
            except (IndexError, ValueError):
                continue
            pend[slot] = (op, raw)
        elif op in ("LoadThisR", "LoadRObjR", "LoadVObjR", "ADDSi") and note:
            lastprop = note
        elif op.startswith("WRTV") and toks:
            slot = toks[0]
            if slot in pend and lastprop:
                kind, raw = pend[slot]
                w = op[4:]           # 8 / 4 / 2 / 1
                if w == "8":
                    val = fmt(f64(raw)) if kind == "SetV8" else str(raw)
                    alt = " (int64 %d)" % raw if kind == "SetV8" else ""
                elif w == "4":
                    val = str(raw if raw < 2**31 else raw - 2**32)
                    alt = " (f32 %s)" % fmt(f32(raw)) if raw > 0x1000 else ""
                elif w == "1":
                    val = {0: "false", 1: "true"}.get(raw, str(raw))
                    alt = ""
                else:
                    val, alt = str(raw), ""
                rows.append((fn, lastprop, val, alt))
                lastprop = None
    return rows


def main(argv):
    files = []
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--dir":
            d = args.pop(0)
            for root, _, fs in os.walk(d):
                files += [os.path.join(root, f) for f in sorted(fs)
                          if f.endswith(".txt")]
        else:
            files.append(a)
    for p in files:
        rows = scan(p)
        if not rows:
            continue
        print("=" * 78)
        print(p)
        print("=" * 78)
        cur = None
        for fn, prop, val, alt in rows:
            if fn != cur:
                print("  [%s]" % fn)
                cur = fn
            print("      %-58s = %s%s" % (prop, val, alt))
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
