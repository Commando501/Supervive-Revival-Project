from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
print("=== THE CLAMP BLOCK 0x035ED960..0x035ED9E0 (from CFG map, alignment guaranteed) ===")
for a in sorted(g.I):
    if 0x035ED95E<=a<0x035ED9E0: print("  ",g.txt(a))
print()
for n in (0x035ED998,0x035ED9AC,0x035ED9B3,0x035ED9B8,0x035ED9BB,0x035ED9BE,0x035ED9C3,0x035ED9C8):
    print(f"  preds({n:#x}) = {[hex(p) for p in sorted(g.pred.get(n,()))]}")
print()
print("=== Q4 BLOCK 0x035ED8B0..0x035ED955 ===")
for a in sorted(g.I):
    if 0x035ED8B0<=a<0x035ED956: print("  ",g.txt(a))
