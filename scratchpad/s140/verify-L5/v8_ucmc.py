import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); d=im.data; IB=im.imagebase
def rvaof(va): return va-IB if IB<=va<IB+im.sizeofimage else None
def q(r): return struct.unpack_from('<Q',d,r)[0]
def cstr(r):
    e=d.find(b'\0',r); return d[r:e].decode('latin1','replace')
def findall(b):
    out=[];i=d.find(b)
    while i!=-1: out.append(i); i=d.find(b,i+1)
    return out

for probe in [b'MaxWalkSpeedCrouched\x00', b'NavMeshProjectionInterval\x00', b'bJustTeleported\x00']:
    occ=findall(probe)
    print(probe, [hex(x) for x in occ])
    for o in occ:
        ptrs=findall(struct.pack('<Q',IB+o))
        for p in ptrs:
            pp=findall(struct.pack('<Q',IB+p))
            print(f"   record {p:#x} -> referenced from {[hex(x) for x in pp]}")
            print(f"     bytes {d[p:p+0x40].hex()}")
