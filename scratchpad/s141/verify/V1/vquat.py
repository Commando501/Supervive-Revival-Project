from vimg import VImg
from vcfg import G
im=VImg()
for e,nm in [(0x035F4770,'helper B (world->gravity?)'),(0x035F4620,'helper A (gravity->world?)')]:
    g=G(im,e)
    print(f"=== {nm} {e:#x}: {len(g.I)} insns, {len(g.calls)} calls, {len(g.ijmp)} ijmp ===")
    for a in sorted(g.I): print("  ",g.txt(a))
    print()
