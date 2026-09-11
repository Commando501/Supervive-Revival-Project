import sys, json, struct, bisect
sys.path.insert(0,'.')
from peimg import Img
import capstone as cs
im=Img(r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"); IB=im.imagebase
RD=[s for s in im.sections if s['name']=='.rdata'][0]
md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64); md.detail=True
vt=json.load(open('cmc_vtables2.json')); L=vt['loki']; E=vt['eng']
ext=json.load(open('extents.json')); S=ext['starts']; EN=ext['ends']
d3=json.load(open('stores_v3.json'))
velfns={}
for h in d3['hits']:
    if h['base'] in ('rsp',): continue
    velfns.setdefault(h['fn'],[]).append(h)
FOLD={0x0F7EC20:'VOID ret0',0x0F7EB50:'nullptr/false',0x0F7EB60:'false',0x0B9E1F0:'true',0x0FC6CF0:'0.0f'}
def extent(r):
    k=bisect.bisect_right(S,r)-1
    return (S[k],EN[k]) if k>=0 and S[k]<=r<EN[k] else (r,r+0x40)
def grade(r):
    if r==0: return "NULL-SLOT"
    if r in FOLD: return 'FOLD('+FOLD[r]+')'
    if im.page_nonzero(r)==0: return 'DARK'
    return 'REAL'
def strs(fb):
    s,e=extent(fb); out=[]
    if e-s>0x8000: e=s+0x8000
    for i in md.disasm(im.read(s,e-s), s):
        for op in i.operands:
            if op.type==cs.x86.X86_OP_MEM and op.mem.base==cs.x86.X86_REG_RIP:
                t=i.address+i.size+op.mem.disp
                if RD['va']<=t<RD['va']+RD['vsz']:
                    try: b=im.read(t,240)
                    except: continue
                    for cand in (b,):
                        # utf16
                        o=[]
                        for k in range(0,200,2):
                            c=cand[k]|(cand[k+1]<<8)
                            if c==0: break
                            if c<32 or c>126: o=[]; break
                            o.append(chr(c))
                        if len(o)>=6:
                            v=''.join(o)
                            if v not in out: out.append(v)
                        n=cand.find(b'\0')
                        if 6<=n<200:
                            try: v=cand[:n].decode('ascii')
                            except: v=None
                            if v and all(32<=ord(c)<127 for c in v) and v not in out: out.append(v)
    return out[:4]
n=min(len(L),len(E))
ov=[(i*8,L[i],E[i]) for i in range(n) if L[i]!=E[i]]
print(f"ULokiCMC OVERRIDES vs engine UCharacterMovementComponent: {len(ov)} of {n} common slots")
print(f"(loki table {len(L)} slots, engine table {len(E)} slots)\n")
print(f"{'disp':>7} {'slot':>4}  {'LOKI impl':>10} {'grade':<18} {'ENGINE impl':>11}  VELWRITE  strings")
rows=[]
for disp,l,e in ov:
    lf,_=extent(l)
    vw = 'VEL!' if lf in velfns else ''
    g=grade(l)
    ss=strs(l) if g=='REAL' else []
    rows.append(dict(disp=disp,slot=disp//8,loki=l,eng=e,grade=g,vel=bool(vw),strs=ss))
    print(f"{disp:#7x} {disp//8:>4}  {l:#10x} {g:<18} {e:#11x}  {vw:<8}  {'; '.join(x[:60] for x in ss[:2])}")
json.dump(rows, open('loki_overrides.json','w'))
