import sys; sys.path.insert(0,r'scratchpad/s140/verify-L4')
from vimg import *
import struct, capstone
X=capstone.x86
im=Img(); buf=im.buf; IB=0x7FF608F40000
VT=0x088F8570; NSLOT=413
impls=set(); dark=0
for k in range(NSLOT):
    va=struct.unpack_from('<Q',buf,VT+8*k)[0]
    r=va-IB
    if im.secof(r)!='.text': continue
    if im.page_nonzero(r)==0: dark+=1; continue
    impls.add(r)
print('unique lit impls in vtable:', len(impls), ' dark slots:', dark)
# CFG each, find stores/reads to disp in the interesting set, and track whether base reg == 'this'(rcx at entry)
INTEREST={0x16C8,0x16D0}
found=[]
fails=0; total_insns=0
for f in sorted(impls):
    try:
        c=CFG(im,f)
    except Exception as e:
        fails+=1; continue
    total_insns+=len(c.insns)
    # naive this-tracking: registers that hold rcx-at-entry
    thisregs={'rcx'}
    # forward linear over sorted addresses is unsound for this; do a simple def-chain on straight mov reg,rcx / mov reg, thisreg
    for a in sorted(c.insns):
        i=c.insns[a]
        if i.mnemonic=='mov' and len(i.operands)==2 and i.operands[0].type==X.X86_OP_REG and i.operands[1].type==X.X86_OP_REG:
            src=i.reg_name(i.operands[1].reg); dst=i.reg_name(i.operands[0].reg)
            if src in thisregs: thisregs.add(dst)
        # any other write to a thisreg removes it
        elif i.operands and i.operands[0].type==X.X86_OP_REG:
            dst=i.reg_name(i.operands[0].reg)
            if dst in thisregs and dst!='rcx': thisregs.discard(dst)
    for a in sorted(c.insns):
        i=c.insns[a]
        for op in i.operands:
            if op.type==X.X86_OP_MEM and op.mem.disp in INTEREST and op.mem.base:
                base=i.reg_name(op.mem.base)
                found.append((f,a,hex(op.mem.disp),base,base in thisregs,i.mnemonic+' '+i.op_str))
print('CFG failures:',fails,' total distinct insns walked:',total_insns)
print()
print('%-12s %-12s %-8s %-6s %-6s %s' % ('fn','addr','disp','base','this?','insn'))
for f,a,d,base,ist,s in found:
    print('0x%08X   0x%08X  %-8s %-6s %-6s %s' % (f,a,d,base,ist,s))
