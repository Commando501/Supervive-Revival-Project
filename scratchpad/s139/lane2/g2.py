import sys; sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\lane2")
from img2 import vslots
from grade import extent
L=vslots(0x088F8570,413); C=vslots(0x07FBED58,413)
P=vslots(0x07FE2A10,204); N=vslots(0x07FDB188,197); M=vslots(0x07FD7568,184)
def find(rva):
    out=[]
    for nm,v in (("LokiCMC",L),("CMC",C),("PawnMC",P),("NavMC",N),("MC",M)):
        for i,a in enumerate(v):
            if a is None: continue
            ex=extent(a)
            if a==rva or (ex and ex[0]<=rva<ex[1]):
                out.append("%s slot %d disp 0x%X (fnstart 0x%07X)"%(nm,i,i*8,a))
    return out
for a in sys.argv[1:]:
    r=int(a,16); print("0x%07X ->"%r, find(r) or "NOT A VTABLE SLOT BODY")
