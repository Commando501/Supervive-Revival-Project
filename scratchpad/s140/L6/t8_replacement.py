"""Look for a DURABLE member write that happens only AFTER the StartNewPhysics call,
i.e. a replacement for the (invalid) latch."""
import sys
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
import capstone
X86=capstone.x86
im=Img(); c=CFG(im,0x035E9EC0)
SNP=0x035EB13A
# instructions strictly after SNP (forward-reachable) and NOT backward-reachable from SNP
def fwd(s):
    R=set(); st=[s]
    while st:
        n=st.pop()
        if n in R: continue
        R.add(n); st.extend(x for x in c.succ.get(n,()) if x not in R)
    return R
F=fwd(0x035EB140)               # the instruction AFTER the SNP call
B=c.reach_backward(SNP)
after_only = F - B
print(f"insns strictly after the StartNewPhysics call (not also before it): {len(after_only)}")
stores={}
for a in sorted(after_only):
    i=c.insns[a]
    if len(i.operands)<1: continue
    op=i.operands[0]
    if op.type==X86.X86_OP_MEM and op.mem.base and i.reg_name(op.mem.base)=='rbx' and i.mnemonic in ('mov','movsd','movss','movups','movaps','or','and','xor','add','inc'):
        stores.setdefault(op.mem.disp,[]).append((a,i.mnemonic+' '+i.op_str))
print(f"distinct CMC member offsets STORED only after the SNP call: {len(stores)}")
for d in sorted(stores):
    print(f"  +{d:#06x}:")
    for a,t in stores[d][:3]: print(f"      {a:#010x} {t}")
