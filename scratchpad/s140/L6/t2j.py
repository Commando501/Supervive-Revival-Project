import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img(); IB=im.imagebase
def maxoff(entry, reg):
    c=CFG(im,entry,maxinsn=200000); mx=0; touch=set()
    for a in c.insns:
        i=c.insns[a]
        for op in i.operands:
            if op.type==X86.X86_OP_MEM and op.mem.base and i.reg_name(op.mem.base)==reg:
                mx=max(mx,op.mem.disp); touch.add(op.mem.disp)
    return mx, touch
print("=== CLASS DISCRIMINATOR: max member offset written, vs sizeof ===")
print("   sizeof(ULokiCharacterMovementComponent) = 0x19D0  [M: dtor 0x530abd2 'mov edx,0x19d0']")
print("   sizeof(ALokiCharacter)                  = 0x1950  [repo CLAUDE.md]")
for e,r,lbl in [(0x0559f580,'rdi','cand CMC ctor'),(0x0559e180,'r14','cand Character ctor'),
                (0x055c0d30,'rbx','cand Character method'),(0x0530aaa0,'rbx','KNOWN ULokiCMC dtor')]:
    mx,t=maxoff(e,r)
    print(f"  {e:#010x} base={r:<4} max member disp = {mx:#x}   0x1090(LivingState) touched={0x1090 in t}  0x1988 touched={0x1988 in t}  {lbl}")

print("\n=== unresolved sites: disassemble their containing code ===")
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
for start,n,lbl in [(0x0530abea,0x60,"after ULokiCMC dtor"),(0x0530c7d0,0x70,"0x530c7ff region"),
                    (0x04b03c90,0x50,"0x4b03cc6 region")]:
    print(f"\n--- {lbl}: linear from {start:#x} ---")
    for i in CS.disasm(im.read(start,n), start):
        print(f"  {i.address:#010x}  {i.bytes.hex(' '):<24} {i.mnemonic} {i.op_str}")
