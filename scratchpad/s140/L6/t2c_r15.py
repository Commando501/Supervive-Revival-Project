import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img(); p=CFG(im,0x055B8370)
print("=== ULokiCMC::PerformMovement prologue 0x055B8370..0x055B83C0 ===")
for a in sorted(x for x in p.insns if 0x055B8370 <= x <= 0x055B83C0):
    print("  ",p.txt(a), " succ=",[hex(s) for s in sorted(p.succ.get(a,()))])
print()
print("Does the r15-zeroing site 0x055b83a6 dominate/precede the clear? paths:")
print("  reach_backward(0x055b860b) contains 0x055b83a6 ?",0x055b83a6 in p.reach_backward(0x055b860b))
print("  reach_backward(0x055b860b) contains 0x055b8381 ?",0x055b8381 in p.reach_backward(0x055b860b))
print()
print("=== independent check that CMC+0x198 is a UObject* (CharacterOwner): engine PerformMovement uses of [this+0x198] ===")
e=CFG(im,0x035E9EC0)
import capstone
X86=capstone.x86
n=0
for a in sorted(e.insns):
    i=e.insns[a]
    for op in i.operands:
        if op.type==X86.X86_OP_MEM and op.mem.disp==0x198 and i.reg_name(op.mem.base)=='rbx':
            print("  ",e.txt(a)); n+=1
            break
print(f"  ({n} loads of [rbx+0x198] in engine PerformMovement; rbx = this)")
