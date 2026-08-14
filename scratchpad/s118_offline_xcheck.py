#!/usr/bin/env python3
"""
S118 offline cross-check of the HandleNotif jump table.

Independent of usmapdump: reads the decrypted dump (file-offset == RVA) and
finds the delegate / descriptor / helper operands by BYTE PATTERN, not by
running the same disassembler the live pass used. Two instruments that fail
differently (method rule 1, "how to apply" #4).

HARNESS SELF-TEST (rule 10/13): must reproduce the three live-verified rows
  idx  8 -> Lobby+0x11b0, desc 0x9FFE810
  idx 19 -> Lobby+0x1510, desc 0x9FFE860
  idx 23 -> Lobby+0x1550, desc 0x9FFE6F0
...or it aborts instead of printing a table.
"""
import struct, sys

DUMP = r"G:\git\Supervive Revival Project\dumps\lobby-dispatch-decrypted\SUPERVIVE-Win64-Shipping.dump.exe"
TABLE_RVA = 0x4B04978
DEFAULT_CASE = 0x4B048F9
N = 33

blob = open(DUMP, "rb").read()


def u32(rva):
    return struct.unpack_from("<I", blob, rva)[0]


def i32(rva):
    return struct.unpack_from("<i", blob, rva)[0]


# ---- the table itself -------------------------------------------------
targets = [u32(TABLE_RVA + 4 * i) for i in range(N)]

# extents: each case runs to the next case start in ADDRESS order
bounds = sorted(set(targets)) + [DEFAULT_CASE]
extent = {}
for a in sorted(set(targets)):
    extent[a] = bounds[bounds.index(a) + 1]


def scan(start, end):
    """Byte-pattern scan of one case body. Returns dict of findings."""
    out = {"deleg_lea": [], "deleg_cmp": [], "deleg_mov": [], "desc": [],
           "calls": [], "riprel_rdx": []}
    p = start
    while p < end - 6:
        b = blob[p:p + 3]
        if b == b"\x48\x8d\x97":                      # lea rdx,[rdi+disp32]
            out["deleg_lea"].append(u32(p + 3)); p += 7; continue
        if b == b"\x44\x39\xaf":                      # cmp dword [rdi+disp32], r13d
            out["deleg_cmp"].append(u32(p + 3)); p += 7; continue
        if b == b"\x48\x8b\x8f":                      # mov rcx,[rdi+disp32]
            out["deleg_mov"].append(u32(p + 3)); p += 7; continue
        if b == b"\x48\x8d\x8f":                      # lea rcx,[rdi+disp32]
            out["deleg_mov"].append(u32(p + 3)); p += 7; continue
        if b == b"\x48\x8d\x0d":                      # lea rcx,[rip+disp32]
            out["desc"].append(p + 7 + i32(p + 3)); p += 7; continue
        if b == b"\x48\x8d\x15":                      # lea rdx,[rip+disp32]  <-- the junk-row shape
            out["riprel_rdx"].append(p + 7 + i32(p + 3)); p += 7; continue
        if blob[p] == 0xE8:                           # call rel32
            out["calls"].append(p + 5 + i32(p + 1)); p += 5; continue
        p += 1
    return out


rows = []
for idx, t in enumerate(targets):
    f = scan(t, extent[t])
    rows.append((idx, t, f))

# ---- SELF-TEST --------------------------------------------------------
expect = {8: (0x11B0, 0x9FFE810), 19: (0x1510, 0x9FFE860), 23: (0x1550, 0x9FFE6F0)}
ok = True
for i, (off, desc) in expect.items():
    f = rows[i][2]
    got_off = f["deleg_lea"][0] if f["deleg_lea"] else None
    got_desc = f["desc"][0] if f["desc"] else None
    good = (got_off == off and got_desc == desc)
    print("SELFTEST idx %-2d expect Lobby+0x%-6x desc 0x%-8X  got Lobby+%s desc %s  %s"
          % (i, off, desc,
             ("0x%x" % got_off) if got_off is not None else "NONE",
             ("0x%X" % got_desc) if got_desc is not None else "NONE",
             "PASS" if good else "FAIL"))
    ok &= good
print("table: %d entries, %d into .text-range, %d == default, %d distinct"
      % (N, sum(1 for t in targets if 0x1000 <= t < 0x764C000),
         sum(1 for t in targets if t == DEFAULT_CASE), len(set(targets))))
if not ok:
    sys.exit("HARNESS SELF-TEST FAILED - not emitting a table")
print("SELF-TEST PASSED\n")

print("idx | body      | lea rdx,[rdi+X] | cmp [rdi+X+8] | mov/lea rcx,[rdi+X] | desc      | riprel-rdx (NOT an offset)")
for idx, t, f in rows:
    print("%3d | 0x%07X | %-15s | %-13s | %-19s | %-9s | %s" % (
        idx, t,
        ",".join("0x%x" % x for x in f["deleg_lea"]) or "-",
        ",".join("0x%x" % x for x in f["deleg_cmp"]) or "-",
        ",".join("0x%x" % x for x in f["deleg_mov"]) or "-",
        ",".join("0x%X" % x for x in f["desc"]) or "-",
        ",".join("0x%X" % x for x in f["riprel_rdx"]) or "-"))
