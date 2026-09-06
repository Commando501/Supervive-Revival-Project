# must-analysis: is r15 provably 0 at 0x035EB130 on ALL paths?
import capstone
from capstone import CS_AC_WRITE
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS
from vthis import parent

im=VImg(); g=VCFG(im,0x035E9EC0)
TOP='T'   # unknown
def tr(ins, v):
    m=ins.mnemonic
    if m=='call':
        return v  # r15 is NON-VOLATILE in Win64 -> preserved across calls
    wrote=False
    for o in ins.operands:
        if o.type==X86_OP_REG and (o.access & CS_AC_WRITE) and parent(CS.reg_name(o.reg))=='r15':
            wrote=True
    for r in ins.regs_write:
        if parent(CS.reg_name(r))=='r15': wrote=True
    if not wrote: return v
    ops=ins.operands
    if m=='xor' and len(ops)==2 and ops[0].type==X86_OP_REG and ops[1].type==X86_OP_REG \
       and CS.reg_name(ops[0].reg)==CS.reg_name(ops[1].reg):
        return 0
    if m=='mov' and len(ops)==2 and ops[0].type==X86_OP_REG and ops[1].type==X86_OP_IMM:
        return ops[1].imm & (0xFFFFFFFF if ops[0].size==4 else 0xFFFFFFFFFFFFFFFF)
    return TOP

IN={g.entry: TOP}
work=[g.entry]
while work:
    a=work.pop()
    if a not in IN: continue
    o=tr(g.insns[a], IN[a])
    for s in g.succ.get(a,[]):
        if s not in g.insns: continue
        cur=IN.get(s,'BOT')
        new = o if cur=='BOT' else (cur if cur==o else TOP)
        if new!=cur:
            IN[s]=new; work.append(s)
print("r15 value at 0x035EB130 =", IN.get(0x035EB130))
print("r15 value at 0x035EB80F (bail RootMotionParams.Clear) =", IN.get(0x035EB80F))
print("r15 value at 0x035EA353 (cmp byte[rdi],r15b) =", IN.get(0x035EA353))
print("r15 value at 0x035E9F90 (cmp byte[rbx+0x231],r15b) =", IN.get(0x035E9F90))
print("r15 value at 0x035EA36E =", IN.get(0x035EA36E))
# and along the FAST path only: simulate 0x035EA356 -> 0x035EB112 -> 0x035EB130
print()
print("--- fast-path-only walk from entry, forcing gates pass & no root motion ---")
forced={0x035e9f03:0x35e9f11, 0x035e9f1f:0x035e9f25, 0x035e9f28:0x035e9f2e,
        0x035e9f59:0x035e9f7d, 0x035e9f97:0x035e9f9d, 0x035e9fa4:0x035e9faa,
        0x035e9fbd:0x035e9fc3, 0x035e9fe1:0x035e9ff0, 0x035ea351:0x035ea353,
        0x035ea356:0x035eb112}
a=g.entry; v=TOP; steps=0; stores=[]
while a!=0x035EB13A and steps<400:
    ins=g.insns[a]
    ops=ins.operands
    if ops and ops[0].type==X86_OP_MEM and ins.mnemonic not in ('cmp','test','call','jmp','ucomisd','comiss'):
        mb=ops[0].mem
        if mb.base and CS.reg_name(mb.base) in ('rbx',) and mb.index==0:
            stores.append((a, mb.disp, ins.mnemonic, ins.op_str))
    v=tr(ins,v)
    nxt = forced.get(a)
    if nxt is None:
        s=g.succ.get(a,[])
        if len(s)!=1: print("  AMBIGUOUS at 0x%08x %s %s -> %s"%(a,ins.mnemonic,ins.op_str,[hex(x) for x in s])); break
        nxt=s[0]
    a=nxt; steps+=1
print("  steps=%d  final pc=0x%X  r15=%s" % (steps,a,v))
print("  rbx-based stores executed on the forced fast path:")
for s in stores: print("    0x%08x +0x%X  %s %s"%(s[0],s[1],s[2],s[3]))
