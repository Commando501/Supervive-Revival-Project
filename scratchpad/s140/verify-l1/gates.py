import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
def d(a,n,label=""):
    print(f"--- {label} {a:#x} ---")
    for i in md.disasm(im.read(a,n),a):
        print(f"  {i.address:#010x} {im.read(i.address,i.size).hex():<22} {i.mnemonic} {i.op_str}")
d(0x035E9EE0,0x50,"engine PerformMovement prologue/gates1-2")
d(0x035E9F8A,0x40,"gates 3-5")
print()
d(0x035E64C0,0x28,"HasValidData")
print()
d(0x03C9B0A0,0x58,"IsSimulatingPhysics (disp 0x4C0)")
print()
d(0x01E2F940,0x14,"first predicate 0x01E2F940")
print()
d(0x035EB110,0x40,"the call region")
print()
d(0x035EB560,0x18,"LF-13 site 0x035EB569")
