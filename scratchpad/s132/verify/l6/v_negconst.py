import struct,json,bisect,random
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
F=json.load(open(r'scratchpad/s132/verify/l6/myfuncs.json'))
IB=0x200000000; SOI=0x4066000
BEG=[f[0] for f in F]; STARTS=set(BEG)
def func_of(rva):
    i=bisect.bisect_right(BEG,rva)-1
    if i<0: return None
    b,e,u=F[i]
    return (b,e) if b<=rva<e else None
EXEC=[(nm,va,vs,ra,rs) for nm,va,vs,ra,rs,ch in SEC if ch&0x20000000]
hits=[]
allmovabs=0
for nm,va,vs,ra,rs in EXEC:
    b=D[ra:ra+rs]
    n=len(b)
    for i in range(n-9):
        if b[i] in (0x48,0x49) and 0xB8<=b[i+1]<=0xBF:
            imm=struct.unpack_from('<Q',b,i+2)[0]
            allmovabs+=1
            neg=(-imm)&0xFFFFFFFFFFFFFFFF
            if IB<=neg<IB+SOI:
                hits.append((nm,va+i,imm,neg-IB))
print("total movabs r64,imm64 candidate encodings in exec sections:",allmovabs)
print("of those, -imm in [ImageBase, ImageBase+SizeOfImage):",len(hits))
from collections import Counter
print("by section:",dict(Counter(h[0] for h in hits)))
exact=sum(1 for h in hits if h[3] in STARTS)
inside=sum(1 for h in hits if func_of(h[3]))
print("target == EXACT .pdata function start: %d / %d (%.1f%%)"%(exact,len(hits),100*exact/len(hits)))
print("target inside some function range:      %d / %d"%(inside,len(hits)))
# section distribution of DECODED targets
print("decoded-target sections:",dict(Counter(
    next((nm for nm,va,vs,ra,rs in [(s[0],s[1],s[2],s[3],s[4]) for s in SEC] if va<=h[3]<va+max(vs,rs)),'?') for h in hits)))
json.dump(hits,open(r'scratchpad/s132/verify/l6/myneg.json','w'))

# ---- CONTROLS ----
random.seed(1234)
# (a) the report's stated control: 940 RANDOM QWORDS from the same section, same test
#     -> re-create: sample random 8-byte reads from packer31 and apply the SAME full test
n=len(hits)
def sample_random_qwords(k):
    nm,va,vs,ra,rs=[e for e in EXEC if e[0]=='packer31'][0]
    out=[]
    for _ in range(k):
        o=random.randrange(ra,ra+rs-8)
        out.append(struct.unpack_from('<Q',D,o)[0])
    return out
rq=sample_random_qwords(n)
inrange=sum(1 for q in rq if IB<=((-q)&0xFFFFFFFFFFFFFFFF)<IB+SOI)
c_exact=sum(1 for q in rq if ((-q)&0xFFFFFFFFFFFFFFFF)-IB in STARTS)
print("\nCONTROL A (report's, as worded): 940 random qwords -> pass range filter: %d ; exact fn start: %d"%(inrange,c_exact))
# (b) NON-DEGENERATE control: random RVAs uniformly in the image, how many are exact fn starts?
k=len(hits); c=0
for _ in range(k):
    r=random.randrange(0,SOI)
    if r in STARTS: c+=1
print("CONTROL B (uniform random RVA in image): exact fn start %d / %d  (base rate %.4f%%)"%(c,k,100*len(STARTS)/SOI))
# (c) sharper control: random RVA restricted to packer31 (where all 940 targets live?)
p31=[e for e in SEC if e[0]=='packer31'][0]
lo,hi=p31[1],p31[1]+p31[2]
c=0
for _ in range(k):
    r=random.randrange(lo,hi)
    if r in STARTS: c+=1
p31starts=sum(1 for s in STARTS if lo<=s<hi)
print("CONTROL C (uniform random RVA within packer31): %d / %d  (base rate %.4f%%)"%(c,k,100*p31starts/(hi-lo)))
# (d) shifted-immediate control: take the same 940 imm64 and add a fixed nonzero delta, re-test
for delta in (1,4,0x10,0x1000):
    c=sum(1 for h in hits if ((h[3]+delta)&0xFFFFFFFF) in STARTS)
    print("CONTROL D (target RVA + 0x%x): exact fn start %d / %d"%(delta,c,len(hits)))
