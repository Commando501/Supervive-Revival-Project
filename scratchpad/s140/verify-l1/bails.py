import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/verify-l1")
from cfg2 import CFG2
from v import im
from capstone.x86 import *

ENTRY=0x035E9EC0; CALL=0x035EB13A; RET=0x035EB1CA
c=CFG2(im, ENTRY)
R=c.reach_backward(CALL)
print("|R| =", len(R), "of", len(c.ins))
print("CALL in R:", CALL in R, " fallthrough 0x035EB140 in R:", 0x035EB140 in R)

bails=[]
for u in sorted(R):
    if u==CALL: continue
    for v in c.succ.get(u,()):
        if v not in R:
            sz,mn,ops,i = c.ins[u]
            bails.append((u,v,mn,ops,im.read(u,sz).hex()))
print("\nTRUE BAIL EDGES (u in R, u != CALL, v not in R):")
for u,v,mn,ops,hx in bails:
    print(f"  {u:#010x}  {hx:<14} {mn:<5} {ops:<12} -> {v:#x}  [{'FORWARD' if v>CALL else 'BACKWARD'}]")
print("total:", len(bails))

prior={0x035E9F1F,0x035E9F28,0x035E9F97,0x035E9FA4,0x035E9FBD,0x035EA25D}
mine={u for u,_,_,_,_ in bails}
print("\nmissed by prior (in mine not theirs):", [hex(x) for x in sorted(mine-prior)])
print("false in prior (theirs not mine)   :", [hex(x) for x in sorted(prior-mine)])

# nodes in R with no successors
ns=[a for a in R if not c.succ.get(a)]
print("nodes in R with no successors:", [hex(x) for x in ns])

# also: check every u in R for ANY successor missing (i.e. terminators)
# ret reachability
RR=c.reach_backward(RET)
print("\n|reach_backward(RET)| =", len(RR), "of", len(c.ins))
for t in (0x035EB1A7,0x035EB7CF,0x035EB150):
    print(f"  bail target {t:#x} reaches RET: {t in RR}   in ins: {t in c.ins}")

# loop check
F=c.reach_forward(c.succ[CALL])
print("\nforward from CALL successors: size", len(F), " CALL reachable from own successors:", CALL in F)

# dominators (Cooper-Harvey-Kennedy) over instruction graph
order=[]; seen=set()
def rpo(entry):
    # iterative postorder
    st=[(entry,iter(c.succ.get(entry,())))]; seen.add(entry); po=[]
    while st:
        n,it=st[-1]
        adv=False
        for s in it:
            if s not in seen:
                seen.add(s); st.append((s,iter(c.succ.get(s,())))); adv=True; break
        if not adv:
            po.append(n); st.pop()
    return po[::-1]
order=rpo(ENTRY)
idx={a:i for i,a in enumerate(order)}
idom={ENTRY:ENTRY}
changed=True
while changed:
    changed=False
    for n in order[1:]:
        newidom=None
        for p in c.pred.get(n,()):
            if p not in idx: continue
            if p in idom:
                if newidom is None: newidom=p
                else:
                    a,b=p,newidom
                    while a!=b:
                        while idx[a]>idx[b]: a=idom[a]
                        while idx[b]>idx[a]: b=idom[b]
                    newidom=a
        if newidom is not None and idom.get(n)!=newidom:
            idom[n]=newidom; changed=True
def dominates(d,n):
    x=n
    while True:
        if x==d: return True
        if x==ENTRY: return False
        nx=idom.get(x)
        if nx is None or nx==x: return False
        x=nx
print("\nDOMINANCE of each bail over CALL:")
for u,_,_,_,_ in bails:
    print(f"  {u:#x} dominates CALL: {dominates(u,CALL)}")
# mandatory spine
spine=[a for a in c.ins if dominates(a,CALL)]
print("mandatory spine size:", len(spine))
