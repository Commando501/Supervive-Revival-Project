import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img()

print("=== CFG(ULokiCMC::StartNewPhysics 0x055C2430) -- POSITIVE CONTROL RESTORATION ===")
c=CFG(im,0x055C2430)
hits=[]
for a in sorted(c.insns):
    i=c.insns[a]
    for op in i.operands:
        if (op.type==X86.X86_OP_MEM and op.mem.disp==0x16C8) or (op.type==X86.X86_OP_IMM and op.imm==0x16C8):
            hits.append(a); break
print(f"  {len(c.insns)} insns, {len(c.calls)} calls, {len(c.indirect_jumps)} indirect jumps, {len(c.decode_failures)} decode fails")
for a in hits: print("   ",c.txt(a))
for want in (0x055C2438,0x055C2441,0x055C2469):
    print(f"  CTRL {want:#x}: {'FOUND' if want in hits else '*** MISSING ***'}")

print()
print("=== CFG(ULokiCMC::PerformMovement 0x055B8370) ===")
p=CFG(im,0x055B8370)
print(f"  {len(p.insns)} insns, {len(p.calls)} calls, {len(p.indirect_jumps)} indirect, {len(p.decode_failures)} decode fails, noreturn={p.noreturn_candidates}")
ph=[]
for a in sorted(p.insns):
    i=p.insns[a]
    for op in i.operands:
        if (op.type==X86.X86_OP_MEM and op.mem.disp in (0x16C8,0x16B0,0x16C0)) or (op.type==X86.X86_OP_IMM and op.imm==0x16C8):
            ph.append((a,op.mem.disp if op.type==X86.X86_OP_MEM else 0x16C8)); break
print(f"  hits on 0x16B0/0x16C0/0x16C8 inside PerformMovement CFG: {len(ph)}")
for a,d in ph: print(f"    disp {d:#x}   {p.txt(a)}")
print(f"  addr range explored: {min(p.insns):#x} .. {max(p.insns):#x}")
print(f"  is 0x055B860B in the CFG? {0x055B860B in p.insns}")
print(f"  is 0x055B85C1 (Super call) in the CFG? {0x055B85C1 in p.insns}  -> {p.txt(0x055B85C1) if 0x055B85C1 in p.insns else ''}")
