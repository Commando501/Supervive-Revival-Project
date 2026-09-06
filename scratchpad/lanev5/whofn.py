import sys, capstone, subprocess, struct
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM, X86_OP_REG
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def vt_install(b, n=0x120):
    """find lea rX,[rip+d] followed by mov [rcx/rdi/rbx/rsi],rX"""
    ins=list(md.disasm(data[b:b+n], b))
    pend={}
    out=[]
    for z in ins:
        if z.mnemonic=='lea' and z.operands[0].type==X86_OP_REG and z.operands[1].mem.base==capstone.x86.X86_REG_RIP:
            pend[z.reg_name(z.operands[0].reg)] = z.address+z.size+z.operands[1].mem.disp
        elif z.mnemonic=='mov' and z.operands[0].type==X86_OP_MEM and z.operands[0].mem.disp==0 and z.operands[1].type==X86_OP_REG:
            r=z.reg_name(z.operands[1].reg)
            if r in pend: out.append((z.address, pend[r]))
    return out
for a in sys.argv[1:]:
    b=int(a,16)
    print("fn 0x%08X vtable installs: %s"%(b, ['@0x%X -> vt 0x%X'%(x,y) for x,y in vt_install(b)]))
