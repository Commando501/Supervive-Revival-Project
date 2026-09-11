import sys; sys.path.insert(0,'scratchpad/s141/verify/V2')
from vpe import VImg; from vcfg import *
from capstone.x86 import *
I=VImg('dumps/merged14.dump.exe')
ins,succ,und,ind=cfg(I,0x035EC850); P=preds(succ)
print("=== ALL definitions of r13 in engine PhysFalling ===")
defs=[]
for a in sorted(ins):
    i=ins[a]
    for r in i.regs_access()[1]:
        if i.reg_name(r) in ('r13','r13d','r13w','r13b'):
            defs.append(a); break
for a in defs: print("   %08x %-20s %-8s %s" % (a,ins[a].bytes.hex(),ins[a].mnemonic,ins[a].op_str))
print()
print("=== is xmm14 the saved OldVelocity.Z? all xmm14 defs ===")
for a in sorted(ins):
    i=ins[a]
    if 'xmm14' in i.op_str and i.operands and i.operands[0].type==X86_OP_REG and i.reg_name(i.operands[0].reg)=='xmm14':
        print("   %08x %-8s %s" % (a,i.mnemonic,i.op_str))
print()
print("=== the CalcVelocity call sites in this fn: call [rax+0x7b0] ===")
for a in sorted(ins):
    i=ins[a]
    if i.id==X86_INS_CALL and i.operands[0].type==X86_OP_MEM and i.operands[0].mem.disp==0x7b0:
        print("   %08x call %s" % (a,i.op_str))
print()
print("=== context of 0x035ecfe2 (the one with NO following call) ===")
for x in sorted(ins):
    if 0x035ecfe2-0x08<=x<=0x035ecfe2+0x60:
        i=ins[x]; print("   %08x %-20s %-8s %s" % (x,i.bytes.hex(),i.mnemonic,i.op_str))
