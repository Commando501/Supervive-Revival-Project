import struct,json,bisect
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
SEC=json.load(open(r'scratchpad/s132/verify/l6/mysecs.json'))
IB=0x200000000
def r2f(rva):
    for nm,va,vs,ra,rs,ch in SEC:
        if va<=rva<va+max(vs,rs):
            o=ra+(rva-va)
            if o<len(D): return o,nm
    return None,None
T=0x14D8758; SZ=0x366F0
print("entries =",SZ/12, "exact int?", SZ%12==0, "->", SZ//12)
fo,sec=r2f(T); print("table at file off",hex(fo),"in section",sec)
N=SZ//12
F=[]
for i in range(N):
    b,e,u=struct.unpack_from('<III',D,fo+12*i)
    F.append((b,e,u))
print("parsed",len(F))
# monotone?
mono=all(F[i][0]<=F[i+1][0] for i in range(len(F)-1))
strict=all(F[i][0]<F[i+1][0] for i in range(len(F)-1))
print("Begin non-decreasing:",mono," strictly increasing:",strict)
# zero/one fields
z=[ (i,f) for i,f in enumerate(F) if 0 in f or 1 in f]
print("entries with any field ==0 or ==1:",len(z), z[:5])
allzero=[f for f in F if f==(0,0,0)]
print("all-zero entries:",len(allzero))
# begin<end?
bad=[f for f in F if not (f[0]<f[1])]
print("entries with Begin>=End:",len(bad))
# section distribution of Begin
from collections import Counter
c=Counter()
for b,e,u in F:
    _,nm=r2f(b); c[nm]+=1
print("Begin section distribution:",dict(c))
json.dump(F,open(r'scratchpad/s132/verify/l6/myfuncs.json','w'))
