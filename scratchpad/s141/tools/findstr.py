import sys, struct, re
sys.path.insert(0,'.')
from peimg import Img
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
im = Img(IMG); IB = im.imagebase; data = im.data
sec = {s['name']:s for s in im.sections}
def find_ascii(tok, secname='.rdata'):
    s = sec[secname]; buf = data[s['praw']:s['praw']+s['vsz']]
    pat = b'\0'+tok.encode()+b'\0'
    out=[]; i=0
    while True:
        j = buf.find(pat, i)
        if j<0: break
        out.append(s['va']+j+1); i=j+1
    return out
def refs_to(rva, secname):
    s = sec[secname]; buf = data[s['praw']:s['praw']+s['vsz']]
    va = (IB+rva).to_bytes(8,'little'); out=[]; i=0
    while True:
        j = buf.find(va,i)
        if j<0: break
        if (s['va']+j)%8==0: out.append(s['va']+j)
        i=j+1
    return out
for tok in sys.argv[1:]:
    hits = find_ascii(tok)
    print(f"=== '{tok}' .rdata ascii occurrences: {[hex(h) for h in hits]}")
    for h in hits:
        for whichsec in ('.data','.rdata'):
            for r in refs_to(h, whichsec):
                b = im.read(r-0x18, 0x40)
                qs = struct.unpack('<8Q', b)
                desc=[]
                for k,q in enumerate(qs):
                    off = (k*8)-0x18
                    if q>IB and (q-IB)<im.sizeofimage:
                        rr=q-IB; sc=im.sec_of(rr)
                        tag = sc['name'] if sc else '?'
                        if tag=='.rdata':
                            raw=im.read(rr,48); nn=raw.find(b'\0'); tag+=':'+repr(raw[:nn if nn>=0 else 20].decode('latin1','replace'))
                        desc.append(f"[{off:+#05x}] {rr:#09x} {tag}")
                    else:
                        desc.append(f"[{off:+#05x}] {q:#x}")
                print(f"   ref@{whichsec} {r:#010x}")
                for d in desc: print("       "+d)
