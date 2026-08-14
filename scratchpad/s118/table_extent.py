#!/usr/bin/env python3
"""Print the Lobby delegate table slot-by-slot and derive its extent.

A delegate slot is 16 bytes {void* Data; int32 Num; int32 tail}.
  bound   = heap Data + Num > 0     (every bound one observed has Num == 3)
  unbound = Data == 0 and Num == 0

The table's extent is derived, not assumed: it is the maximal contiguous run of
slots that are ALL either bound-shaped or all-zero, anchored on the known
delegate offsets. Anything that is neither shape terminates the run.
"""
import sys
sys.path.insert(0, "scratchpad/s118")
from delegates import load, u64, u32, is_heap, LOBBY, CAP  # noqa: E402

ANCHORS = [0x11B0, 0x12C0, 0x1510, 0x1550, 0x1670]  # known delegate offsets


def shape(mem, off):
    a = LOBBY + off
    ptr, num, tail = u64(mem, a), u32(mem, a + 8), u32(mem, a + 0xC)
    if ptr is None:
        return None, None
    if ptr == 0 and num == 0:
        return "UNBOUND", (ptr, num, tail)
    if is_heap(ptr) and num > 0:
        return "BOUND", (ptr, num, tail)
    return "OTHER", (ptr, num, tail)


def main():
    mem, _ = load(CAP)

    for a in ANCHORS:
        k, v = shape(mem, a)
        if k is None or k == "OTHER":
            sys.exit(f"[ABORT] anchor +0x{a:x} is not delegate-shaped ({k}) -> harness void")
    print(f"[HARNESS] all {len(ANCHORS)} known delegate anchors are delegate-shaped\n")

    # Grow a run outward from the anchors until a non-delegate shape appears.
    lo = min(ANCHORS)
    while lo - 0x10 >= 0 and shape(mem, lo - 0x10)[0] in ("BOUND", "UNBOUND"):
        lo -= 0x10
    hi = max(ANCHORS)
    while hi + 0x10 < 0x2000 and shape(mem, hi + 0x10)[0] in ("BOUND", "UNBOUND"):
        hi += 0x10

    slots = [(o, *shape(mem, o)) for o in range(lo, hi + 0x10, 0x10)]
    nb = sum(1 for _, k, _ in slots if k == "BOUND")
    nu = sum(1 for _, k, _ in slots if k == "UNBOUND")

    print(f"DELEGATE TABLE (derived): +0x{lo:x} .. +0x{hi:x}")
    print(f"  {len(slots)} slots  =  {nb} BOUND  +  {nu} UNBOUND")
    print(f"  byte span 0x{hi - lo + 0x10:x}\n")

    print(f"  {'off':>8}  {'state':<8} {'ptr':>15}  {'num':>4}  tail")
    for off, k, v in slots:
        ptr, num, tail = v
        mark = " <<<" if k == "BOUND" else ""
        print(f"  +0x{off:04x}  {k:<8} 0x{ptr:013X}  {num:4d}  0x{tail:08X}{mark}")

    ptrs = sorted(v[0] for _, k, v in slots if k == "BOUND")
    print(f"\nBOUND invocation-list pointers span 0x{ptrs[0]:X} .. 0x{ptrs[-1]:X}"
          f"  (range 0x{ptrs[-1]-ptrs[0]:X} -- one allocation pool)")
    print("BOUND offsets:", " ".join(f"+0x{o:x}" for o, k, _ in slots if k == "BOUND"))


if __name__ == "__main__":
    main()
