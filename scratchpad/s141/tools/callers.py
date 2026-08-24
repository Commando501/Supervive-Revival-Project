import sys, struct
sys.path.insert(0,'.')
from peimg import Img
import capstone
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase
sec={s['name']:s for s in im.sections}; TX=sec['.text']
buf = im.data[TX['praw']:TX['praw']+TX['vsz']]
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
def rel32_callers(target):
    out=[]
    # scan for e8/e9 with rel32 == target-(site+5)
    for opc,kind in ((0xE8,'call'),(0xE9,'jmp')):
        i=0
        while True:
            j = buf.find(bytes([opc]), i)
            if j<0 or j+5>len(buf): break
            site = TX['va']+j
            rel = struct.unpack_from('<i', buf, j+1)[0]
            if site+5+rel == target:
                # verify decode
                try:
                    ins = next(CS.disasm(im.read(site,8), site))
                    if ins.size==5 and ins.mnemonic in ('call','jmp'):
                        out.append((site, kind))
                except StopIteration: pass
            i=j+1
    return out
def stored_ptrs(target):
    tgt=(IB+target).to_bytes(8,'little'); out=[]
    for sn in ('.rdata','.data'):
        s=sec[sn]; b=im.data[s['praw']:s['praw']+s['vsz']]; i=0
        while True:
            j=b.find(tgt,i)
            if j<0: break
            out.append((sn, s['va']+j)); i=j+1
    return out
for a in sys.argv[1:]:
    t=int(a,16)
    c=rel32_callers(t); p=stored_ptrs(t)
    print(f"=== {t:#x}: {len(c)} rel32 call/jmp sites, {len(p)} stored pointers")
    for s,k in c: print(f"   {k} @ {s:#010x}")
    for sn,r in p[:20]: print(f"   ptr in {sn} @ {r:#010x}")
