#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FK-22 LINE 1 part 4: name the qword referrers, dump the impl neighbourhood,
   read EServerOnlyExecPins / EClientOnlyExecPins enumerator values."""
import os, struct, sys
import capstone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade2 import Img, PD, hexs, ROOT

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
SINGLE = os.path.join(ROOT, "dumps", "tutorial-hero", "SUPERVIVE-Win64-Shipping.dump.exe")
img = Img(SINGLE)


def cstr(rva, n=64):
    if not img.sec(rva):
        return None
    b = img.read(rva, n)
    if b"\0" not in b:
        return None
    s = b.split(b"\0")[0]
    if not s or any(c < 32 or c > 126 for c in s):
        return None
    return s.decode("latin1")


def qrefs(rva):
    pat = struct.pack("<Q", img.base + rva)
    out, i = [], 0
    while True:
        i = img.buf.find(pat, i)
        if i < 0:
            break
        if i % 8 == 0 and img.sec(i):
            out.append(i)
        i += 1
    return out


print("=== impl neighbourhood 0x1311850..0x1311890 (raw) ===")
print("   " + hexs(img.read(0x1311850, 0x40)))
print("   preceding byte 0x131186F = %02x ; pdata rows: 0x1311800..0x1311866 then 0x1311890.." % img.buf[0x131186F])
print("   => 0x1311870 sits in the 0x1311866..0x1311890 gap = leaf functions with no unwind data.")
for ins in MD.disasm(img.read(0x1311866, 0x2A), 0x1311866):
    print("     %07X  %-8s %s" % (ins.address, ins.mnemonic, ins.op_str))

print("\n=== who points at the ServerOnly THUNK 0x52E12B0 (ICF fold multiplicity of the thunk) ===")
for r in qrefs(0x52E12B0):
    sec = img.sec(r)[0]
    # try {name*, thunk, impl} with the thunk at +8  => record start = r-8
    rec = r - 8
    q = struct.unpack_from("<QQQ", img.buf, rec) if rec >= 0 else (0, 0, 0)
    nm = cstr(q[0] - img.base) if q[0] > img.base else None
    print("   %-7s 0x%07X   record@0x%07X name=%-14r impl=0x%X" % (
        sec, r, rec, nm, (q[2] - img.base) if q[2] > img.base else 0))

print("\n=== who points at the ServerOnly IMPL 0x1311870 ===")
for r in qrefs(0x1311870):
    sec = img.sec(r)[0]
    rec = r - 16
    q = struct.unpack_from("<QQQ", img.buf, rec) if rec >= 0 else (0, 0, 0)
    nm = cstr(q[0] - img.base) if q[0] > img.base else None
    ctx = hexs(img.read(r - 16, 40))
    print("   %-7s 0x%07X  as-record{name=%r thunk=0x%X}  ctx=%s" % (
        sec, r, nm, (q[1] - img.base) if q[1] > img.base else 0, ctx))

print("\n=== EServerOnlyExecPins / EClientOnlyExecPins enumerator records ===")
# UHT enumerator record = { const char* Name, int64 Value }
for lbl, s in [("ServerOnly pins", "EServerOnlyExecPins::"), ("ClientOnly pins", "EClientOnlyExecPins::")]:
    print("  -- %s" % lbl)
    pat = s.encode()
    i = 0
    seen = set()
    while True:
        i = img.buf.find(pat, i)
        if i < 0:
            break
        if img.sec(i) and img.buf[i - 1] == 0:
            name = cstr(i, 96)
            if name and name not in seen:
                seen.add(name)
                # find qword pointers to this string; the enumerator record is {char*, int64}
                for r in qrefs(i):
                    v = struct.unpack_from("<q", img.buf, r + 8)[0]
                    print("     str@0x%07X %-34s record@%-9s value=%d" % (i, name, hex(r), v))
        i += 1
