import sys
sys.path.insert(0,'.')
from peimg import Img
from cfg import CFG
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG)
entry=int(sys.argv[1],16); dominator=int(sys.argv[2],16); target=int(sys.argv[3],16)
c=CFG(im, entry)
def fwd(start, banned):
    S=set(); st=[start]
    while st:
        n=st.pop()
        if n in S or n==banned: continue
        S.add(n)
        for d in c.succ.get(n,()): 
            if d not in S: st.append(d)
    return S
base = fwd(entry, None)
print(f"fn {entry:#x} insns={len(c.insns)}  forward-reachable from entry: {len(base)}")
print(f"target {target:#x} reachable normally: {target in base}")
cut = fwd(entry, dominator)
print(f"with node {dominator:#x} REMOVED, target reachable: {target in cut}")
print(f"=> {dominator:#x} DOMINATES {target:#x}: {target not in cut}")
# also: does dominator dominate every ret?
rets=[r for r,i in c.insns.items() if i.mnemonic=='ret']
print(f"rets in fn: {len(rets)}; rets still reachable with node removed: {sum(1 for r in rets if r in cut)}")
