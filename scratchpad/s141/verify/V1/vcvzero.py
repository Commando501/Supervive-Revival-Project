from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035D5D20)
lo,hi=0x035d64c0,0x035d6540
for a in sorted(g.I):
    if lo<=a<hi: print("  ",g.txt(a))
print("\npreds(0x035d6511) =", [hex(p) for p in sorted(g.pred.get(0x035d6511,()))])
print("preds(0x035d6520) =", [hex(p) for p in sorted(g.pred.get(0x035d6520,()))])
