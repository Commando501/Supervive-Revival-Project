import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace')
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img(); c=CFG(im,0x035E9EC0)
E=0x035E9EC0; T=0x035EB13A
nodes=sorted(c.insns)
N=set(nodes)
# iterative dominators
D={n:(set([E]) if n==E else set(N)) for n in nodes}
changed=True; it=0
while changed:
    changed=False; it+=1
    for n in nodes:
        if n==E: continue
        ps=[p for p in c.pred.get(n,()) if p in N]
        if not ps: 
            new={n}
        else:
            new=set(N)
            for p in ps: new &= D[p]
            new |= {n}
        if new!=D[n]:
            D[n]=new; changed=True
print("dominator iterations:",it)
dt=D[T]
print(f"|Dom(call)| = {len(dt)}")
EXITS=[0x035E9F1F,0x035E9F28,0x035E9F97,0x035E9FA4,0x035E9FBD,0x035EA25D]
for e in EXITS:
    i=c.insns[e]
    print(f"  {e:#010x} {i.mnemonic:5s} {i.op_str:<14s} dominates-call={e in dt}")
# how many branch instructions dominate the call (i.e., mandatory decision points)
import capstone
COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}
mand=[n for n in sorted(dt) if c.insns[n].mnemonic in COND]
print(f"\nMANDATORY conditional branches on every path entry->call: {len(mand)}")
for n in mand:
    i=c.insns[n]
    tgt=i.operands[0].imm
    inR=None
    print(f"  {n:#010x} {i.mnemonic:5s} -> {tgt:#010x}")
