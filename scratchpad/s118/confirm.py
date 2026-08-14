#!/usr/bin/env python3
"""Confirm which candidate slots are REAL delegate instances, live.

Discriminator: a TDelegate allocation begins with a module-address vtable
pointer. An FString buffer begins with UTF-16 text; an overlap/misaligned read
begins with whatever. This is the test that separates them -- allocation-pool
adjacency does NOT (that inference produced a false "it's a string" call on
Lobby+0x1a00, which is really a raw-method delegate bound to Lobby itself).

Controls run BEFORE any real reading (method rules 10/13):
  positive  0x1D21663F430  Lobby+0x12c0's allocation -- a known delegate
  negative  0x1D20C44E140  the "LbS" FString buffer  -- known NOT a delegate
"""
import re
import subprocess
import sys

U = "./tools/usmapdump/usmapdump.exe"
P = "SUPERVIVE-Win64-Shipping.exe"
MOD_LO = 0x7FF7C7EF0000
MOD_HI = MOD_LO + 0xA9E1000
LINE = re.compile(r"^\s+([0-9A-F]{8,16})\s+((?:[0-9A-F]{2} )+)")


def first_qwords(addr, n=4):
    out = subprocess.run([U, "peek", P, hex(addr), str(n * 8)],
                         capture_output=True, text=True, timeout=60).stdout
    mem = {}
    for line in out.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        a = int(m.group(1), 16)
        for i, b in enumerate(bytes.fromhex(m.group(2).replace(" ", ""))):
            mem[a + i] = b
    qs = []
    for k in range(n):
        try:
            qs.append(int.from_bytes(
                bytes(mem[addr + k * 8 + i] for i in range(8)), "little"))
        except KeyError:
            qs.append(None)
    return qs


def is_delegate(addr):
    q = first_qwords(addr)
    return (q[0] is not None and MOD_LO <= q[0] < MOD_HI), q


def main():
    ok, q = is_delegate(0x1D21663F430)
    if not ok:
        sys.exit(f"[ABORT] positive control failed: 0x1D21663F430 -> {q}")
    bad, q2 = is_delegate(0x1D20C44E140)
    if bad:
        sys.exit(f"[ABORT] negative control failed: LbS buffer read as "
                 f"delegate -> {q2}")
    print("[HARNESS] controls PASS (known delegate accepted, "
          "known FString buffer rejected)\n")

    cands = [int(x, 16) for x in sys.argv[1:]]
    print(f"{'allocation':>15}  verdict     vtable            boundObj(+0x18)")
    real = []
    for a in cands:
        ok, q = is_delegate(a)
        vt = f"0x{q[0]:X}" if q[0] else "-"
        rva = f" (rva 0x{q[0]-MOD_LO:X})" if ok else ""
        obj = f"0x{q[3]:X}" if q[3] else "-"
        print(f"0x{a:013X}  {'DELEGATE' if ok else 'not-a-deleg'}  {vt}{rva}  {obj}")
        if ok:
            real.append(a)
    print(f"\n{len(real)} of {len(cands)} candidates are real delegate instances")


if __name__ == "__main__":
    main()
