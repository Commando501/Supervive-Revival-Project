import sys, struct
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB=im.imagebase; data=im.data
sec={s['name']:s for s in im.sections}
def strat(rva):
    try:
        raw=im.read(rva,80); n=raw.find(b'\0'); return raw[:n if n>=0 else 40].decode('latin1','replace')
    except Exception: return '?'
def refs(rva):
    out=[]
    tgt=(IB+rva).to_bytes(8,'little')
    for sn in ('.rdata','.data'):
        s=sec[sn]; buf=data[s['praw']:s['praw']+s['vsz']]; i=0
        while True:
            j=buf.find(tgt,i)
            if j<0: break
            va=s['va']+j
            if va%8==0: out.append((sn,va))
            i=j+1
    return out
def find_name(tok):
    s=sec['.rdata']; buf=data[s['praw']:s['praw']+s['vsz']]
    pat=b'\0'+tok.encode()+b'\0'; res=[]; i=0
    while True:
        j=buf.find(pat,i)
        if j<0: break
        res.append(s['va']+j+1); i=j+1
    return res
def decode(rec):
    b=im.read(rec,0x40)
    namep,repp,flags = struct.unpack_from('<QQQ',b,0)
    genflags,objflags = struct.unpack_from('<II',b,0x18)
    setter,getter = struct.unpack_from('<QQ',b,0x20)
    arraydim,offset = struct.unpack_from('<HH',b,0x30)
    return dict(name=strat(namep-IB) if namep>IB else None, flags=flags, genflags=genflags,
                objflags=objflags, arraydim=arraydim, offset=offset,
                setter=hex(setter-IB) if setter>IB else hex(setter), getter=hex(getter-IB) if getter>IB else hex(getter))
for tok in sys.argv[1:]:
    for na in find_name(tok):
        print(f"### '{tok}' str@{na:#x}")
        for sn,r in refs(na):
            d=decode(r)
            if d['name']==tok:
                print(f"   rec@{sn} {r:#010x}  offset={d['offset']:#x} ({d['offset']}) arraydim={d['arraydim']} genflags={d['genflags']:#x} propflags={d['flags']:#x} setter={d['setter']} getter={d['getter']}")
            else:
                print(f"   ref@{sn} {r:#010x}  (name field decodes to {d['name']!r} -- not a FPropertyParams start)")
