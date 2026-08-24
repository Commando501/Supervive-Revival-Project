import sys, json, struct
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"); IB=im.imagebase
TX=[s for s in im.sections if s['name']=='.text'][0]; tlo=TX['va']; praw=TX['praw']; data=im.data
RD=[s for s in im.sections if s['name']=='.rdata'][0]
md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64); md.detail=True
vt=json.load(open('cmc_vtables.json')); L=vt['loki']; E=vt['eng']
ext=json.load(open('extents.json')); S=ext['starts']; EN=ext['ends']
import bisect
def extent(r):
    k=bisect.bisect_right(S,r)-1
    return (S[k],EN[k]) if k>=0 and S[k]<=r<EN[k] else (None,None)

def wstr(rva,maxn=200):
    try: b=im.read(rva,maxn*2)
    except: return None
    out=[]
    for i in range(0,len(b),2):
        c=b[i]|(b[i+1]<<8)
        if c==0: break
        if c<32 or c>126: return None
        out.append(chr(c))
    return ''.join(out) if len(out)>=4 else None
def astr(rva,maxn=200):
    try: b=im.read(rva,maxn)
    except: return None
    n=b.find(b'\0')
    if n<4: return None
    s=b[:n]
    try: t=s.decode('ascii')
    except: return None
    return t if all(32<=ord(c)<127 for c in t) else None

d=json.load(open('cmc_tiers3.json'))
rows=d['A']
print(f"TIER A: {len(rows)} CMC-vtable functions that write [this+0xE8/F0/F8]\n")
for fb,m,obj,why in sorted(rows):
    ldisp=[i*8 for i,v in enumerate(L) if v==fb]
    edisp=[i*8 for i,v in enumerate(E) if v==fb]
    fe=m['end']
    s,e=extent(fb); fe = e if e else fe
    strs=[]
    for i in md.disasm(data[praw+(fb-tlo):praw+(fe-tlo)], fb):
        for op in i.operands:
            if op.type==cs.x86.X86_OP_MEM and op.mem.base==cs.x86.X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                if RD['va']<=t<RD['va']+RD['vsz']:
                    for cand in (t,):
                        w=wstr(cand) or astr(cand)
                        if not w:
                            try:
                                p=struct.unpack('<Q',im.read(cand,8))[0]
                                if p>IB:
                                    r2=p-IB
                                    if RD['va']<=r2<RD['va']+RD['vsz']: w=wstr(r2) or astr(r2)
                            except: pass
                        if w and len(w)>5 and w not in strs: strs.append(w)
    grade='REAL'
    b0=im.read(fb,4).hex()
    if b0.startswith(('c20000','33c0c3','32c0c3','b001c3')) or b0=='0f57c0c3': grade='FOLD'
    if im.page_nonzero(fb)==0: grade='DARK'
    print(f"FN {fb:#09x}-{fe:#x} sz={fe-fb:#x} grade={grade} lokiDisp={[hex(x) for x in ldisp]} engDisp={[hex(x) for x in edisp]} stores={len(obj)}")
    for s_ in strs[:6]: print(f"      str: {s_[:110]!r}")
