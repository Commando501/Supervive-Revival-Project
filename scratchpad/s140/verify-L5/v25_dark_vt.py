import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); d=im.data; IB=im.imagebase
def q(r): return struct.unpack_from('<Q',d,r)[0]
def rvaof(v): return v-IB if IB<=v<IB+im.sizeofimage else None
for VT,n,label in [(0x088F8570,413,'ULokiCMC vtable (413 as brief says)'),
                   (0x088F8570,449,'ULokiCMC vtable (449 contiguous)'),
                   (0x08B17EE8,23,'SavedMove vtable')]:
    dark=[]; loki=0; eng=0
    for k in range(n):
        r=rvaof(q(VT+k*8))
        if r is None: continue
        if im.page_nonzero(r)==0: dark.append((k,r))
        if 0x5000000 <= r: loki+=1
        else: eng+=1
    print(f"{label}: slots={n} loki-range={loki} other={eng} DARK={len(dark)}")
    for k,r in dark:
        tag = 'LOKI' if r>=0x5000000 else 'engine/other'
        print(f"    slot {k:3d} -> {r:#x}  {tag}")
