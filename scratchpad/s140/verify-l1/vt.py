import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone.x86 import *

IB=im.imagebase
VT=0x088F8570   # ULokiCharacterMovementComponent vtable per brief
def slot(vt, disp):
    q=struct.unpack_from('<Q', im.buf, vt+disp)[0]
    return q-IB
print("=== ULokiCMC vtable positive controls (brief-declared) ===")
for disp,exp,name in [(0x720,0x055C2430,'StartNewPhysics'),(0xAA8,0x055B8370,'PerformMovement'),
                      (0x3D0,0x055C2B90,'TickComponent'),(0x890,0x055A7680,'ControlledCharacterMove'),
                      (0xA38,0x055A75B0,'ConstrainInputAcceleration'),(0x830,0x055B89F0,'PhysFalling')]:
    got=slot(VT,disp)
    print(f"  disp {disp:#06x} -> {got:#010x}  exp {exp:#010x}  {'PASS' if got==exp else '**FAIL**'}  {name}")

ENTRY=0x035E9EC0; CALL=0x035EB13A
c=CFG2(im, ENTRY); R=c.reach_backward(CALL)
# dominators
import collections
def rpo(entry):
    st=[(entry,iter(c.succ.get(entry,())))]; seen={entry}; po=[]
    while st:
        n,it=st[-1]; adv=False
        for s in it:
            if s not in seen: seen.add(s); st.append((s,iter(c.succ.get(s,())))); adv=True; break
        if not adv: po.append(n); st.pop()
    return po[::-1]
order=rpo(ENTRY); idx={a:i for i,a in enumerate(order)}; idom={ENTRY:ENTRY}
ch=True
while ch:
    ch=False
    for n in order[1:]:
        ni=None
        for p in c.pred.get(n,()):
            if p not in idx or p not in idom: continue
            if ni is None: ni=p
            else:
                a,b=p,ni
                while a!=b:
                    while idx[a]>idx[b]: a=idom[a]
                    while idx[b]>idx[a]: b=idom[b]
                ni=a
        if ni is not None and idom.get(n)!=ni: idom[n]=ni; ch=True
def dom(d,n):
    x=n
    while True:
        if x==d: return True
        if x==ENTRY: return False
        nx=idom.get(x)
        if nx is None or nx==x: return False
        x=nx

print("\n=== 19 indirect call sites in R: dominance + register provenance ===")
ins=sorted(c.ins)
for s,t in sorted(c.calls):
    if t is not None or s not in R: continue
    i=c.ins[s][3]
    op=i.operands[0]
    disp=op.mem.disp; base=i.reg_name(op.mem.base)
    # walk backwards up to 10 insns for the load of base reg
    k=ins.index(s); prov=None
    for j in range(k-1,max(0,k-14),-1):
        a=ins[j]; ii=c.ins[a][3]
        if ii.id==X86_INS_MOV and ii.operands[0].type==X86_OP_REG and ii.reg_name(ii.operands[0].reg)==base:
            prov=f"{a:#x}: {ii.mnemonic} {ii.op_str}"; break
    print(f"  {s:#010x} call [{base}+{disp:#x}]  dominatesCALL={str(dom(s,CALL)):5}  base<-{prov}")
