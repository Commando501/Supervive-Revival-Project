import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase
def slots(vt_rva, n, base=0):
    out=[]
    for i in range(n):
        d=base+i*8
        v=struct.unpack_from('<Q', im.read(vt_rva+d,8),0)[0]
        out.append((d, v))
    return out
print("=== ULokiCMC vtable .rdata 0x088F8570 : displacements of interest")
for d in (0x4C0,0x4C8,0x660,0x720,0x7A0,0x7B0,0x7D0,0x830,0xA50,0xC00):
    v=struct.unpack_from('<Q', im.read(0x088F8570+d,8),0)[0]
    rva = v-IB if v>IB else v
    ok = im.sec_of(rva) is not None if v>IB else False
    print(f"  +{d:#05x} raw={v:#018x} rva={rva:#09x} in_text={'yes' if ok and rva<0x764a000 else 'NO'}")
print()
print("=== how long is the ULokiCMC vtable? scan until a non-.text-VA entry")
vt=0x088F8570
i=0
last=None
while i<0x2000:
    v=struct.unpack_from('<Q', im.read(vt+i,8),0)[0]
    rva=v-IB
    if not (v>IB and 0x1000<=rva<0x764a000):
        break
    last=i; i+=8
print(f"  first non-code slot at +{i:#x} (slot {i//8}); last code slot +{last:#x}")
print()
print("=== engine CMC vtable .rdata 0x07FBED58 : same displacements")
for d in (0x4C0,0x4C8,0x660,0x720,0x7A0,0x7B0,0x7D0,0x830,0xA50,0xC00):
    v=struct.unpack_from('<Q', im.read(0x07FBED58+d,8),0)[0]
    rva=v-IB
    ok = v>IB and 0x1000<=rva<0x764a000
    print(f"  +{d:#05x} rva={rva:#09x} {'code' if ok else '*** NOT CODE ***'}")
