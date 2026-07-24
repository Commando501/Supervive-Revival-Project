#!/usr/bin/env python3
import struct, sys
from collections import defaultdict
path = sys.argv[1]
DATA = open(path,"rb").read()
pe = struct.unpack_from("<I", DATA, 0x3C)[0]; opt = pe+24
IB = struct.unpack_from("<Q", DATA, opt+24)[0]
LEA = {0x05,0x0D,0x15,0x1D,0x25,0x2D,0x35,0x3D}
print(f"{path} IB={IB:#x}")

# index LEA rip targets once
tmap = defaultdict(list); n=len(DATA); j=0
while j < n-7:
    if (DATA[j]==0x48 or DATA[j]==0x4C) and DATA[j+1]==0x8D and DATA[j+2] in LEA:
        d = struct.unpack_from("<i", DATA, j+3)[0]
        tmap[IB+j+7+d].append(j)
    j += 1
print(f"indexed {sum(len(v) for v in tmap.values())} LEA, {len(tmap)} targets")

def check(label, s):
    i = DATA.find(s.encode("utf-16-le"))
    if i < 0: print(f"  [{label}] '{s}': ABSENT"); return
    va = IB+i
    direct = tmap.get(va, [])
    # pointer-slot: find 8-byte value == va, then LEA refs to the slot
    ptr_refs = []
    k=0
    while True:
        k = DATA.find(struct.pack("<Q", va), k)
        if k<0: break
        slot_va = IB+k
        for r in tmap.get(slot_va, []): ptr_refs.append((k,r))
        k += 8
    print(f"  [{label}] '{s}' @{va:#x}: directLEA={len(direct)} {[hex(IB+r) for r in direct[:3]]}  ptrSlotLEA={len(ptr_refs)} {[(hex(IB+s2),hex(IB+r)) for s2,r in ptr_refs[:3]]}")

# validation: strings that DEFINITELY ran this session
check("VAL-ran", "Entering game state")
check("VAL-ran", "Bringing World")
check("VAL-ran", "TravelCompleted")
# target: RCB strings
check("RCB", "sub-object class. Actor")
check("RCB", "stably named bit. Actor")
check("RCB", "Instantiating sub-object")
