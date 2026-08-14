#!/usr/bin/env python3
"""Authoritative bound-delegate enumeration at 8-BYTE stride.

Supersedes delegates.py, which stepped 0x10 and therefore could not see any
member at an offset  ==  8 (mod 16).  That blind spot hid Lobby+0x228, which is
a REAL notif delegate (disconnectNotif) -- so the miss changed a conclusion,
not just a tally.

Structure (established S118): the 16-byte record is UE's FDelegateBase
    { void* DelegateAllocation @+0x0 ; int32 DelegateSize @+0x8 ; pad @+0xC }
i.e. a SINGLE-CAST TDelegate.  DelegateSize is an allocation size in 16-byte
units, NOT a subscriber count -- every bound slot reads 3 (a 40-byte instance).
+0xC is padding holding stale heap garbage (it reads 0x1D2 even on unbound
slots, which is why it looked like a TArray Max).

Emits CANDIDATES for live vtable confirmation: a real delegate allocation
begins with a module-address vtable pointer.
"""
import re
import sys

LOBBY = 0x1D251AA1C80
MOD_LO = 0x7FF7C7EF0000
MOD_HI = MOD_LO + 0xA9E1000
CAP = "scratchpad/s118/lobby-object-full.txt"
LINE = re.compile(r"^\s+([0-9A-F]{8,16})\s+((?:[0-9A-F]{2} )+)")

# Ground truth for the self-test.
KNOWN_BOUND = [0x12C0, 0x12D0, 0x12E0, 0x1630, 0x1670, 0x228]
KNOWN_UNBOUND = [0x1510, 0x1550, 0x11B0, 0x1308, 0x1318]


def load():
    mem = {}
    for line in open(CAP, encoding="utf-8", errors="replace"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        a = int(m.group(1), 16)
        for i, b in enumerate(bytes.fromhex(m.group(2).replace(" ", ""))):
            mem[a + i] = b
    return mem


def rd(mem, a, n):
    try:
        return int.from_bytes(bytes(mem[a + i] for i in range(n)), "little")
    except KeyError:
        return None


def slot(mem, off):
    a = LOBBY + off
    ptr, size = rd(mem, a, 8), rd(mem, a + 8, 4)
    if ptr is None or size is None:
        return None
    # A bound single-cast delegate: heap allocation + a small size in 16B units.
    bound = (0x1_0000_0000 < ptr < MOD_LO) and 1 <= size <= 8
    return {"off": off, "ptr": ptr, "size": size, "bound": bound}


def main():
    mem = load()
    fails = []
    for o in KNOWN_BOUND:
        s = slot(mem, o)
        if not s or not s["bound"]:
            fails.append(f"+0x{o:x} must be BOUND, got {s}")
    for o in KNOWN_UNBOUND:
        s = slot(mem, o)
        if not s or s["bound"]:
            fails.append(f"+0x{o:x} must be UNBOUND, got {s}")
    if fails:
        print("[ABORT] self-test FAILED -- run is VOID, not a result:")
        for f in fails:
            print("   ", f)
        sys.exit(1)
    print(f"[HARNESS] self-test PASS ({len(KNOWN_BOUND)} bound incl. the "
          f"8-mod-16 offset +0x228, {len(KNOWN_UNBOUND)} unbound)\n")

    cands = [s for o in range(0, 0x2000, 8) if (s := slot(mem, o)) and s["bound"]]

    # Overlap guard: a real 16-byte record at X makes X-8 / X+8 decode oddly.
    # Keep all, but mark ones adjacent to another candidate for scrutiny.
    offs = {c["off"] for c in cands}
    print(f"{len(cands)} bound-shaped slots at 8-byte stride "
          f"(16-byte-stride scan found only {len([c for c in cands if c['off'] % 16 == 0])})\n")
    print(f"  {'off':>8} {'allocation':>15} {'size':>4}  adj?")
    for c in cands:
        adj = "OVERLAP" if (c["off"] - 8 in offs or c["off"] + 8 in offs) else ""
        print(f"  +0x{c['off']:04x} 0x{c['ptr']:013X} {c['size']:4d}  {adj}")

    print("\n# live vtable confirmation (a delegate allocation starts with a "
          "module-address vtable):")
    for c in cands:
        print(f"0x{c['ptr']:X}", end=" ")
    print()


if __name__ == "__main__":
    main()
