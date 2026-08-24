import sys, struct
sys.path.insert(0,'.')
from peimg import Img
from cfg import CFG
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im=Img(IMG); IB=im.imagebase
vt=int(sys.argv[1],16); n=int(sys.argv[2],16)
disps=[int(x,16) for x in sys.argv[3:]]
seen={}
for d in range(0,n,8):
    v=struct.unpack_from('<Q', im.read(vt+d,8),0)[0]
    if not (v>IB and v-IB<im.sizeofimage): continue
    r=v-IB
    if r in seen: continue
    seen[r]=d
    if im.page_nonzero(r)==0: continue
    try: c=CFG(im, r, maxinsn=4000)
    except Exception: continue
    hits=set()
    for rva,i in c.insns.items():
        for op in i.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.disp in disps and op.mem.base!=0:
                hits.add(op.mem.disp)
    if set(disps)<=hits:
        print(f"  disp {d:#05x} (slot {d//8}) -> {r:#09x}  insns={len(c.insns)}  HAS ALL {[hex(x) for x in disps]}")
