from vimg import VImg
from vcfg import G
im=VImg(); g=G(im,0x035EC850)
print("=== EXIT 1 region 0x035EC86C..0x035EC890 ===")
for a in sorted(g.I):
    if 0x035EC86C<=a<0x035EC890: print("  ",g.txt(a))
print("=== EXIT 2 region 0x035EC960..0x035EC9B4 ===")
for a in sorted(g.I):
    if 0x035EC960<=a<0x035EC9B4: print("  ",g.txt(a))
print("=== GRAVITY BLOCK 0x035ECC05..0x035ECD10 ===")
for a in sorted(g.I):
    if 0x035ECC05<=a<0x035ECD10: print("  ",g.txt(a))
print("=== xmm11 defs anywhere in fn ===")
for a in sorted(g.I):
    i=g.I[a]
    if i.op_str.startswith('xmm11,') or i.op_str.startswith('xmm11 '):
        print("  ",g.txt(a))
