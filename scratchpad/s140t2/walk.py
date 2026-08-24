import sys,struct; sys.path.insert(0,'G:/git/Supervive Revival Project/scratchpad/s140t2')
from uht import *
p=PE()
def okname(s):
    return s and 1<=len(s)<=64 and all(('A'<=c<='Z') or ('a'<=c<='z') or ('0'<=c<='9') or c=='_' for c in s)
def arr_for(recrva):
    out=[]
    for a in p.findptr(recrva,8):
        ent=[]
        for k in range(-400,400):
            ad=a+k*8
            try: v=p.u64(ad)
            except Exception: ent.append((ad,None)); continue
            d=None
            if p.base < v < p.base+0x0a800000:
                try:
                    d=rec(p,v-p.base)
                    if not okname(d['name']): d=None
                except Exception: d=None
            ent.append((ad,d))
        idx=[i for i,(ad,_) in enumerate(ent) if ad==a][0]
        lo=idx
        while lo-1>=0 and ent[lo-1][1]: lo-=1
        hi=idx
        while hi+1<len(ent) and ent[hi+1][1]: hi+=1
        out.append((a, ent[lo][0], [e[1] for e in ent[lo:hi+1]]))
    return out
