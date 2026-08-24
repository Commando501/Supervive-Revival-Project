import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s141/tools")
from peimg import Img
import cfg as CFGMOD, capstone
X=capstone.x86
im = Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe")
c = CFGMOD.CFG(im, 0x035EC850)
ins=c.insns
print("=== A) prologue: establish `this` register ===")
for r in sorted(ins)[:26]:
    print("   ", c.txt(r))
print("\n=== B) every LEA in the function, with its displacement ===")
for r in sorted(ins):
    i=ins[r]
    if i.mnemonic=='lea':
        print(f"   {c.txt(r)}")
print("\n=== C) every instruction whose MEM operand displacement is 0xE8/0xF0/0xF8 ===")
for r in sorted(ins):
    i=ins[r]
    for oi,op in enumerate(i.operands):
        if op.type==X.X86_OP_MEM and op.mem.disp in (0xE8,0xF0,0xF8):
            w = 'WRITE' if oi==0 else 'read '
            print(f"   {w} {c.txt(r)}   base={i.reg_name(op.mem.base) if op.mem.base else '-'} idx={i.reg_name(op.mem.index) if op.mem.index else '-'} disp={op.mem.disp:#x}")
