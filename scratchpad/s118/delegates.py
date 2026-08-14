#!/usr/bin/env python3
"""Enumerate the Lobby object's delegate slots from a `usmapdump peek` capture.

SELF-TEST FIRST (method rules 10/13): the parser must reproduce three offsets
recorded BOUND by S117 (+0x12c0 +0x12d0 +0x12e0) and two recorded UNBOUND
(+0x1510 +0x1550). If it cannot, it aborts instead of printing a result --
a broken harness must not report as a measurement.
"""
import re
import sys

LOBBY = 0x1D251AA1C80
CAP = "scratchpad/s118/lobby-object-full.txt"

# Known ground truth from docs/fk15-delegate-binding-20260813.md
KNOWN_BOUND = [0x12C0, 0x12D0, 0x12E0]
KNOWN_UNBOUND = [0x1510, 0x1550]

LINE = re.compile(r"^\s+([0-9A-F]{8,16})\s+((?:[0-9A-F]{2} )+)")


def load(path):
    mem = {}
    n = 0
    for line in open(path, encoding="utf-8", errors="replace"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        addr = int(m.group(1), 16)
        bs = bytes.fromhex(m.group(2).replace(" ", ""))
        for i, b in enumerate(bs):
            mem[addr + i] = b
        n += 1
    return mem, n


def u64(mem, a):
    try:
        return int.from_bytes(bytes(mem[a + i] for i in range(8)), "little")
    except KeyError:
        return None


def u32(mem, a):
    try:
        return int.from_bytes(bytes(mem[a + i] for i in range(4)), "little")
    except KeyError:
        return None


def is_heap(p):
    """A live heap pointer in this process sits far below the module base."""
    return p is not None and 0x1_0000_0000 < p < 0x7FF0_0000_0000


def classify(mem, off):
    a = LOBBY + off
    ptr, num, mx = u64(mem, a), u32(mem, a + 8), u32(mem, a + 0xC)
    if ptr is None or num is None:
        return None
    bound = is_heap(ptr) and num > 0
    return {"off": off, "ptr": ptr, "num": num, "tail": mx, "bound": bound}


def main():
    mem, nlines = load(CAP)
    print(f"[HARNESS] parsed {nlines} lines, {len(mem)} bytes of the Lobby object")
    if len(mem) < 0x1800:
        sys.exit(f"[ABORT] only {len(mem)} bytes captured; need >= 0x1800")

    # ---- SELF-TEST -------------------------------------------------------
    fails = []
    for off in KNOWN_BOUND:
        s = classify(mem, off)
        if not s or not s["bound"]:
            fails.append(f"+0x{off:x} should be BOUND, read {s}")
    for off in KNOWN_UNBOUND:
        s = classify(mem, off)
        if not s or s["bound"]:
            fails.append(f"+0x{off:x} should be UNBOUND, read {s}")
    if fails:
        print("[ABORT] harness self-test FAILED -- this run is VOID, not a result:")
        for f in fails:
            print("   ", f)
        sys.exit(1)
    print(f"[HARNESS] self-test PASS: {len(KNOWN_BOUND)} known-bound + "
          f"{len(KNOWN_UNBOUND)} known-unbound offsets reproduce\n")

    # ---- ENUMERATE -------------------------------------------------------
    bound, unbound = [], []
    for off in range(0x0, 0x2000, 0x10):
        s = classify(mem, off)
        if not s:
            continue
        (bound if s["bound"] else unbound).append(s)

    # A delegate slot's neighbourhood: restrict to the contiguous delegate
    # table, i.e. the span between the first and last BOUND slot, so we do not
    # count unrelated pointer members elsewhere in the object.
    print(f"ALL BOUND-SHAPED SLOTS across +0x0..+0x2000: {len(bound)}")
    print(f"{'offset':>10} {'ptr':>16} {'num':>5} {'tail(+0xC)':>12}")
    for s in bound:
        print(f"  +0x{s['off']:04x}   0x{s['ptr']:013X} {s['num']:5d}   0x{s['tail']:08X}")

    if bound:
        lo, hi = bound[0]["off"], bound[-1]["off"]
        span = [s for s in (classify(mem, o) for o in range(lo, hi + 0x10, 0x10)) if s]
        nb = sum(1 for s in span if s["bound"])
        print(f"\nDELEGATE TABLE SPAN +0x{lo:x}..+0x{hi:x}: "
              f"{len(span)} slots, {nb} bound, {len(span)-nb} unbound")
        print("\nUNBOUND offsets within that span:")
        ub = [f"+0x{s['off']:x}" for s in span if not s["bound"]]
        for i in range(0, len(ub), 10):
            print("   " + " ".join(ub[i:i + 10]))

    print("\nBOUND offset list (copy-paste):")
    print("   " + " ".join(f"+0x{s['off']:x}" for s in bound))
    print("\nDistinct 'num' values among bound slots:",
          sorted({s["num"] for s in bound}))


if __name__ == "__main__":
    main()
