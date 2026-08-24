from vimg import VImg
from vcfg import G
im=VImg()
# Re-root the CFG at the loop head to test the "second iteration" claim
g=G(im,0x035EC967)
D=g.doms()
COND={'jo','jno','jb','jae','je','jne','jbe','ja','js','jns','jp','jnp','jl','jge','jle','jg'}
t=0x035ECCFB
if t not in D: print("gravity write NOT reachable from loop head 0x35EC967"); raise SystemExit
R=g.back(t)
print(f"Re-rooted at LOOP HEAD 0x035EC967: {len(g.I)} insns reachable")
print(f"conditional branches dominating the gravity write {t:#x} on a SECOND iteration:")
for d in sorted(D[t]):
    if g.I[d].mnemonic not in COND: continue
    kind='RECONVERGING' if all(s in R for s in g.succ[d]) else '*** TRUE EXIT ***'
    print(f"   {g.txt(d):58s} {kind}")
print()
print("Is the SizeSq2D clamp write 0x035ED9BB dominated by the gravity write? ",
      0x035ECCFB in D.get(0x035ED9BB,set()))
print("Is the gravity write dominated by the clamp write? ",
      0x035ED9BB in D.get(0x035ECCFB,set()))
