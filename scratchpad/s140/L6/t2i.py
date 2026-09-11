import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img()
def dump(entry, lo, hi, title):
    c=CFG(im,entry,maxinsn=200000)
    print(f"\n########## {entry:#x} {title} ({len(c.insns)} insns, {min(c.insns):#x}..{max(c.insns):#x}) ##########")
    for a in sorted(x for x in c.insns if lo<=x<=hi):
        print(f"  {c.txt(a):<58} -> {[hex(s) for s in sorted(c.succ.get(a,()))]}")
    return c
c=dump(0x0559e180,0x0559e9c0,0x0559ea90,"[r14<-rcx] word write at +0x16c8")
print("\n  -- all 0x16xx-range disps in 0x0559e180 --")
for a in sorted(c.insns):
    i=c.insns[a]
    for op in i.operands:
        if op.type==X86.X86_OP_MEM and 0x1600<=op.mem.disp<0x1a00 and op.mem.base and i.reg_name(op.mem.base) not in('rsp','rip'):
            print(f"    {a:#x} {i.mnemonic} {i.op_str}")
            break
c2=dump(0x0559f580,0x0559fdb0,0x0559fe30,"[rdi<-rcx] byte write at +0x16c8")
print("\n  -- all 0x16xx/0x19xx disps in 0x0559f580 --")
for a in sorted(c2.insns):
    i=c2.insns[a]
    for op in i.operands:
        if op.type==X86.X86_OP_MEM and (0x1600<=op.mem.disp<0x1a00) and op.mem.base and i.reg_name(op.mem.base) not in('rsp','rip'):
            print(f"    {a:#x} {i.mnemonic} {i.op_str}")
            break
