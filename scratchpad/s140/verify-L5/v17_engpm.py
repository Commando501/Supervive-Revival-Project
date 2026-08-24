import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
CS=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); CS.detail=True
im=Img()
c=CFG(im,0x035E9EC0)
print(f"engine PerformMovement: insns={len(c.insns)} calls={len(c.calls)} indirect={len(c.indirect_jumps)} fail={len(c.decode_failures)} noret={len(c.noreturn_candidates)}")
for a in (0x035EB13A, 0x035EB569):
    print(f"  {a:#x} in CFG: {a in c.insns}  ->  {c.txt(a) if a in c.insns else ''}")
# forward reachability
def fwd(cfg, s, banned=()):
    seen=set(); st=[s]
    while st:
        n=st.pop()
        if n in seen or n in banned: continue
        seen.add(n)
        for x in cfg.succ.get(n,()): st.append(x)
    return seen
Fe = fwd(c, 0x035E9EC0)
print("  0x035EB569 reachable from entry:", 0x035EB569 in Fe)
Fsnp = fwd(c, 0x035EB13A)
print("  0x035EB569 reachable FROM the StartNewPhysics call node:", 0x035EB569 in Fsnp)
Fban = fwd(c, 0x035E9EC0, banned={0x035EB13A})
print("  0x035EB569 reachable from entry WITHOUT passing 0x035EB13A:", 0x035EB569 in Fban, " (False => SNP call dominates it)")
# predecessors chain to find rax provenance
print("  preds of 0x035EB569:", [hex(p) for p in c.pred.get(0x035EB569,())])
# walk back linearly along single-pred chain printing insns
n=0x035EB569; chain=[]
for _ in range(25):
    ps=list(c.pred.get(n,()))
    if len(ps)!=1: break
    n=ps[0]; chain.append(n)
for n in reversed(chain):
    print("   ", c.txt(n))
print("   *", c.txt(0x035EB569))
