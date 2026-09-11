import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone import *
from capstone.x86 import *
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
c=CFG2(im,0x035E9EC0)
print("=== rbx / rcx definitions between entry and gate 5 (0x035E9FB5) ===")
for a in sorted(x for x in c.ins if 0x035E9EC0<=x<=0x035E9FB5):
    sz,mn,ops,i=c.ins[a]
    for op in i.operands:
        if op.type==X86_OP_REG and i.reg_name(op.reg) in ('rbx','rcx') and (op.access & CS_AC_WRITE):
            print(f"   {a:#010x} {im.read(a,sz).hex():<20} {mn} {ops}")
print("\n=== L1's claim: 0x035EB569's rcx == this ===")
for a in (0x035EB554,0x035EB566,0x035EB569):
    sz,mn,ops,i=c.ins[a]; print(f"   {a:#010x} {im.read(a,sz).hex():<20} {mn} {ops}")
print("   (rbx == this, defined at 0x035E9EFD; see above)")
