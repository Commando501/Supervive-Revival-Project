import sys, collections
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
from cfg import CFG
im=Img()
c=CFG(im,0x035E9EC0)
SNP=0x035EB13A; A50=0x035EB569
print(f"engine PerformMovement CFG: {len(c.insns)} insns, {len(c.calls)} calls, "
      f"{len(c.indirect_jumps)} indirect jumps, {len(c.decode_failures)} decode fails")
def reach_fwd(start, stop_at_ret=True):
    R=set(); st=[start]
    while st:
        n=st.pop()
        if n in R: continue
        R.add(n)
        for s in c.succ.get(n,()): 
            if s not in R: st.append(s)
    return R
F_snp = reach_fwd(SNP)
F_a50 = reach_fwd(A50)
print(f"\nforward-reachable from StartNewPhysics call {SNP:#x}: {len(F_snp)} insns")
print(f"forward-reachable from slot-0xA50 call  {A50:#x}: {len(F_a50)} insns")
print(f"  is {A50:#x} forward-reachable from {SNP:#x}?  {A50 in F_snp}   <-- A50 AFTER StartNewPhysics")
print(f"  is {SNP:#x} forward-reachable from {A50:#x}?  {SNP in F_a50}   <-- (loop back?)")
B_a50 = c.reach_backward(A50)
print(f"  is {SNP:#x} in reach_backward({A50:#x})?  {SNP in B_a50}")
print("\n=== does EVERY path from the StartNewPhysics call reach the A50 call? ===")
# find exits: nodes reachable from SNP that terminate (ret) without passing A50
term=[]
for n in sorted(F_snp):
    i=c.insns[n]
    if i.mnemonic in ('ret','retf') :
        term.append(n)
print(f"  ret instructions forward-reachable from the SNP call: {[hex(x) for x in term]}")
# path from SNP avoiding A50 to any ret?
def reach_avoid(start, avoid):
    R=set(); st=[start]
    while st:
        n=st.pop()
        if n in R or n==avoid: continue
        R.add(n)
        for s in c.succ.get(n,()):
            if s not in R and s!=avoid: st.append(s)
    return R
RA=reach_avoid(SNP,A50)
esc=[t for t in term if t in RA]
print(f"  rets reachable from SNP WITHOUT executing the A50 call: {[hex(x) for x in esc]}")
print("\n=== region around the A50 call ===")
for a in sorted(x for x in c.insns if 0x035EB530<=x<=0x035EB5A0):
    print(f"   {c.txt(a):<56} -> {[hex(s) for s in sorted(c.succ.get(a,()))]}")
print("\n=== region around the StartNewPhysics call + the HasValidData branch ===")
for a in sorted(x for x in c.insns if 0x035EB126<=x<=0x035EB1D0):
    print(f"   {c.txt(a):<56} -> {[hex(s) for s in sorted(c.succ.get(a,()))]}")
