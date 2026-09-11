import sys
sys.path.insert(0,'.')
from peimg import Img
from cfg import CFG
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG)
entry=int(sys.argv[1],16); disps=[int(x,16) for x in sys.argv[2:]]
c=CFG(im, entry)
print(f"### {entry:#x} insns={len(c.insns)}")
for rva in sorted(c.insns):
    i=c.insns[rva]
    if not i.operands: continue
    op=i.operands[0]
    # WRITE classification: operands[0].type == MEM  (NEVER regs_access -- S140T2 defect)
    if op.type==capstone.x86.X86_OP_MEM and op.mem.disp in disps and op.mem.base!=0:
        print(f"  WRITE {rva:#010x}  {i.mnemonic} {i.op_str}")
    else:
        for o in i.operands[1:]:
            if o.type==capstone.x86.X86_OP_MEM and o.mem.disp in disps and o.mem.base!=0:
                print(f"  read  {rva:#010x}  {i.mnemonic} {i.op_str}")
