import capstone
from capstone import CS_AC_WRITE
from capstone.x86 import *
from vimg import VImg
from vcfg import VCFG, CS
from vthis import analyse, GPRS, parent

im=VImg(); g=VCFG(im,0x035E9EC0)
CALL=0x035EB13A
R=g.reach_backward(CALL)
dom=g.dominators(); pdom,exits=g.postdominators()

print("=== LF-13 cross-check: the disp 0xA50 call at 0x035EB569 ===")
print("  0x035EB569 in insns:", 0x035EB569 in g.insns, "->", g.insns[0x035EB569].mnemonic, g.insns[0x035EB569].op_str)
print("  in reach_backward(StartNewPhysics call)?", 0x035EB569 in R, "  (expect False = post-call only)")
fwd1CB=g.reach_forward(0x035EB1CB)
print("  in reach_forward(0x35EB1CB)?", 0x035EB569 in fwd1CB)
print("  post-dominates 0x35EB1CB?", 0x035EB569 in pdom.get(0x035EB1CB,set()))
# reachable from the three bail blocks?
for bail in (0x035EB1A7,0x035EB7CF,0x035EB150):
    f=g.reach_forward(bail)
    print("  reachable from bail 0x%X ? %s" % (bail, 0x035EB569 in f))

print("\n=== r15 liveness between 0x035E9F7F (xor r15d,r15d) and 0x035EB130 ===")
# any write to r15 on any path from 0x035E9F7F to 0x035EB130?
fwd=g.reach_forward(0x035E9F7F); bwd=g.reach_backward(0x035EB130)
between = (fwd & bwd) - {0x035E9F7F, 0x035EB130}
writers=[]
for a in sorted(between):
    ins=g.insns[a]
    hit=False
    for o in ins.operands:
        if o.type==X86_OP_REG and (o.access & CS_AC_WRITE) and parent(CS.reg_name(o.reg))=='r15': hit=True
    for r in ins.regs_write:
        if parent(CS.reg_name(r))=='r15': hit=True
    if ins.mnemonic=='call': hit=hit  # r15 is nonvolatile in Win64 -> calls preserve it
    if hit: writers.append((a,ins))
print("  nodes strictly between: %d ; r15 writers found: %d" % (len(between), len(writers)))
for a,ins in writers: print("    0x%08x %s %s"%(a,ins.mnemonic,ins.op_str))

print("\n=== dominator chain: stores + call, in dom order ===")
dc=dom[CALL]
for a in (0x035E9F82,0x035EA009,0x035EB130,CALL):
    print("  0x%08x in dom(call)=%s  |dom(a)|=%d" % (a, a in dc, len(dom[a])))
# is 0x035EB130 the LAST dominator instruction before the call?
cands=[a for a in dc if a<CALL]
print("  max dominator address below the call = 0x%X" % max(cands))
print("  instruction at that address:", g.insns[max(cands)].mnemonic, g.insns[max(cands)].op_str)
# 0x035EB137 mov rcx,rbx is between; is it a dominator too?
print("  0x035EB137 in dom(call)?", 0x035EB137 in dc)

print("\n=== which stores lie in reach_forward(0x35EB112) i.e. the no-root-motion fast path ===")
f112=g.reach_forward(0x035EB112)
print("  |reach_forward(0x35EB112)| =", len(f112))
for a in (0x035E9F82,0x035EA009,0x035EB130,0x035EB10A,0x035EA458):
    print("   store 0x%08x in it? %s" % (a, a in f112))

print("\n=== does anything in engine PerformMovement touch +0x16C8 ? ===")
hits=[]
for a,ins in sorted(g.insns.items()):
    for o in ins.operands:
        if o.type==X86_OP_MEM and o.mem.disp==0x16C8:
            hits.append((a,ins))
print("  disp==0x16C8 operands in this function:", len(hits))
for a,ins in hits: print("   0x%08x %s %s"%(a,ins.mnemonic,ins.op_str))
