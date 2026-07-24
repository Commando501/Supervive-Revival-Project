#!/usr/bin/env python3
# Build a one-pass index of ALL LEA-rip targets in a dump, then check refs to every ReadContentBlockHeader
# log string (find any that's in a decrypted/non-cold branch to anchor the function).
import struct, os, sys
os.chdir(r"G:\git\Supervive Revival Project")
LEA = {0x05,0x0D,0x15,0x1D,0x25,0x2D,0x35,0x3D}
path = sys.argv[1] if len(sys.argv)>1 else "dumps/merged.dump.iat.exe"
DATA = open(path,"rb").read()
pe = struct.unpack_from("<I", DATA, 0x3C)[0]; opt = pe+24
IB = struct.unpack_from("<Q", DATA, opt+24)[0]
print(f"{path}  IB={IB:#x} size={len(DATA):#x}")

# One pass: map target_va -> list of instr rvas
from collections import defaultdict
tmap = defaultdict(list)
n=len(DATA); j=0; cnt=0
mv=memoryview(DATA)
while j < n-7:
    if (DATA[j]==0x48 or DATA[j]==0x4C) and DATA[j+1]==0x8D and DATA[j+2] in LEA:
        d = struct.unpack_from("<i", DATA, j+3)[0]
        tv = IB + j + 7 + d
        tmap[tv].append(j); cnt+=1
    j += 1
print(f"indexed {cnt} LEA-rip instrs, {len(tmap)} distinct targets")

# ReadContentBlockHeader-only log strings (distinctive substrings). Find each, report refs.
needles = [
    "sub-object class. Actor",
    "sub-object class (SubObj",
    "stably named bit. Actor",
    "Instantiating sub-object",
    "Stably named sub-object not found",
    "not allowed to be actor type",
    "Actor component not in parent actor",
    "cannot be actor class",
    "serialize subobject's outer",
    "actor is outer bit",
    "after SerializeObject",
    "after reading actor bit",
]
for s in needles:
    i = DATA.find(s.encode("utf-16-le"))
    if i < 0:
        print(f"  '{s}': STRING ABSENT")
        continue
    va = IB+i
    refs = tmap.get(va, [])
    print(f"  '{s}': str@{va:#x}  LEA-refs={len(refs)} {[hex(IB+r) for r in refs[:4]]}")
