import sys, struct
sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s141/tools')
from peimg import Img
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
IB=im.imagebase
def q(rva): return struct.unpack_from('<Q', im.read(rva,8),0)[0]
def rv(rva):
    v=q(rva); return v-IB if v>IB else None
for base in (0x88e5ca8, 0x89f8b50):
    print(f"=== candidate vtable base {base:#x}")
    print(f"   [-0x08] = {q(base-8):#018x}")
    for d in (0x0,0x8,0x10,0x8C0,0x888,0x940,0xC00):
        r=rv(base+d)
        print(f"   +{d:#06x} -> {r:#09x}" if r else f"   +{d:#06x} -> {q(base+d):#018x} (not VA)")
    # backwards: where does this vtable start? scan back for non-code
    i=0
    while i<0x4000:
        v=q(base-i-8)
        r=v-IB if v>IB else 0
        if not (v>IB and 0x1000<=r<0x764a000): break
        i+=8
    print(f"   contiguous code-slot run starts {i:#x} bytes before base (i.e. at {base-i:#x})")
