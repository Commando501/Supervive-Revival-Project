import sys, struct
sys.path.insert(0, r"G:/git/Supervive Revival Project/scratchpad/s140/tools")
from peimg import Img
im=Img(); IB=im.imagebase
LOKI_VT=0x088F8570; ENG_VT=0x07fbed58
def slot(vt,d):
    q=struct.unpack_from('<Q',im.read(vt+d,8),0)[0]
    return q,(q-IB if IB<=q<IB+im.sizeofimage else None)
print("=== slot 0xA50 on both CMC vtables ===")
for name,vt in (("LokiCMC",LOKI_VT),("EngCMC",ENG_VT)):
    q,r=slot(vt,0xA50); print(f"  {name} +0xA50 -> {r:#010x}" if r else f"  {name} +0xA50 -> raw {q:#x}")
print("\n=== which LokiCMC slots differ from EngCMC (i.e. Loki overrides), 413 slots ===")
ov=[]
for d in range(0,413*8,8):
    ql,rl=slot(LOKI_VT,d); qe,re=slot(ENG_VT,d)
    if ql!=qe: ov.append((d,rl,re))
print(f"  {len(ov)} overridden slots")
band=[(d,rl,re) for d,rl,re in ov if rl and 0x0530A000<=rl<0x0530D000]
print(f"  overrides landing in the 0x530Axxx-0x530Cxxx band: {len(band)}")
for d,rl,re in band: print(f"    disp {d:#06x}  Loki={rl:#010x}  Eng={re:#010x}")
print("\n=== ALL vtables (any .rdata aligned qword) pointing into [0x530ABA0,0x530AC40) or 0x530C7xx ===")
rd=[s for s in im.sections if s['name']=='.rdata'][0]
RD=im.data[rd['praw']:rd['praw']+rd['rawsz']]
for lo,hi,lbl in ((0x0530ABA0,0x0530AC40,'Reset+tailjmp / accessor region'),(0x0530C780,0x0530C830,'0x530c7ff region')):
    found=[]
    for tgt in range(lo,hi):
        tb=struct.pack('<Q',IB+tgt); off=RD.find(tb)
        while off!=-1:
            if off%8==0: found.append((tgt, rd['va']+off))
            off=RD.find(tb,off+1)
    print(f"  {lbl}: {len(found)} vtable-ish refs")
    for t,p in found:
        tags=[]
        if 0<=p-LOKI_VT<413*8: tags.append(f"LokiCMCvt+{p-LOKI_VT:#x}")
        if 0<=p-ENG_VT<520*8: tags.append(f"EngCMCvt+{p-ENG_VT:#x}")
        print(f"     target {t:#x} referenced at .rdata {p:#x} {tags}")
