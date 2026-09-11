import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone.x86 import *

ENTRY=0x035E9EC0; CALL=0x035EB13A
c=CFG2(im, ENTRY); R=c.reach_backward(CALL)

# (a) independent operand scan: any call/jmp with non-immediate operand
ijmp=[]; icall=[]
for a,(sz,mn,ops,i) in sorted(c.ins.items()):
    if i.id in (X86_INS_JMP, X86_INS_CALL):
        op=i.operands[0]
        if op.type != X86_OP_IMM:
            (icall if i.id==X86_INS_CALL else ijmp).append((a,mn,ops))
print("non-immediate JMP sites:", len(ijmp), ijmp)
print("non-immediate CALL sites:", len(icall))

# (e) any memory operand with displacement 0x720, from capstone operands
d720=[]
for a,(sz,mn,ops,i) in sorted(c.ins.items()):
    for op in i.operands:
        if op.type==X86_OP_MEM and op.mem.disp==0x720:
            d720.append((a,mn,ops))
print("\ndisp 0x720 operands:", len(d720))
for x in d720: print("   ", hex(x[0]), x[1], x[2])

# direct targets in this fn, and check for 0x03600990 / 0x055C2430 anywhere as imm
direct=sorted({t for (s,t) in c.calls if t is not None})
print("\ndistinct direct call targets:", len(direct))
FOLDS={0x00F7EC20,0x00F7EB50,0x00F7EB60,0x00B9E1F0,0x00FC6CF0}
for t in direct:
    fb=im.read(t,4).hex()
    grade = 'FOLD' if t in FOLDS else ('DARK' if im.page_nonzero(t)==0 else 'REAL')
    sites=[s for (s,tt) in c.calls if tt==t]
    inR=any(s in R for s in sites)
    print(f"   {t:#010x} nz={im.page_nonzero(t):4d} {grade:4} first4={fb} sites={len(sites)} anySiteInR={inR}")
print("\n0x03600990 among direct targets:", 0x03600990 in direct)
print("0x055C2430 among direct targets:", 0x055C2430 in direct)
# any imm jmp to either
print("any jmp imm to those:", [hex(a) for a,(sz,mn,ops,i) in c.ins.items() if i.id==X86_INS_JMP and i.operands[0].type==X86_OP_IMM and i.operands[0].imm in (0x03600990,0x055C2430)])

# 0x0751DEB0 call sites & whether in R
for t in (0x0751DEB0,):
    sites=[s for (s,tt) in c.calls if tt==t]
    print(f"\n{t:#x} call sites:", [hex(s) for s in sites], "in R:", [s in R for s in sites])

# indirect call sites in R and which dominate
print("\nindirect call sites total:", len([1 for s,t in c.calls if t is None]),
      " in R:", len([s for s,t in c.calls if t is None and s in R]))
for s,t in sorted(c.calls):
    if t is None and s in R:
        print("   ", hex(s), c.ins[s][1], c.ins[s][2])
