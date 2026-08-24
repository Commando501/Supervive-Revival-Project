import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img(); d=im.data; IB=im.imagebase
def dis(rva,n):
    for i in CS.disasm(im.read(rva,n),rva):
        print(f"  {i.address:#010x} {i.bytes.hex():24s} {i.mnemonic} {i.op_str}")
print("=== C  0x055A7440 .. 0x055A7500 ===")
dis(0x055A7440, 0xC8)
print()
print("=== SavedMove vtable at .rdata 0x08B17EE8 ===")
def q(r): return struct.unpack_from('<Q',d,r)[0]
def rvaof(v): return v-IB if IB<=v<IB+im.sizeofimage else None
for k in range(-3, 26):
    va=q(0x08B17EE8+k*8); r=rvaof(va)
    print(f"  slot {k:3d}  @{0x08B17EE8+k*8:#x}  VA {va:#018x} -> RVA {('%#x'%r) if r is not None else 'NOT-IMAGE'}")
