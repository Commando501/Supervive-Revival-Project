import sys,csv,pickle,bisect,struct
sys.path.insert(0,'scratchpad/s137-w3')
from img import Img
im=Img('dumps/merged13.dump.exe'); b=im.b
rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    r=csv.reader(f); next(r)
    for x in r: rows.append((int(x[0],16),int(x[1],16)))
rows.sort()
begins=[x[0] for x in rows]
# chain: map begin->chained function start
chain={}
prev_end=None; cur=None
for bgn,end in rows:
    if prev_end is not None and bgn==prev_end:
        chain[bgn]=cur
    else:
        cur=bgn; chain[bgn]=bgn
    prev_end=end
recs=pickle.load(open('scratchpad/s137-w3/recs.pkl','rb'))
implmap={}
for off,nm,thunk,impl in recs:
    implmap.setdefault(impl,set()).add(nm)
thunkmap={}
for off,nm,thunk,impl in recs:
    thunkmap.setdefault(thunk,set()).add(nm)
def attribute(site):
    i=bisect.bisect_right(begins,site)-1
    if i<0: return None,None
    bgn,end=rows[i]
    if not (bgn<=site<end): return ('OUTSIDE',None)
    f=chain.get(bgn,bgn)
    nm=implmap.get(f)
    return (f, sorted(nm) if nm else None)
if __name__=='__main__':
    sites=[int(l,16) for l in open(sys.argv[1]) if l.startswith('0x')]
    named=0
    out=[]
    for s in sites:
        f,nm=attribute(s)
        out.append((s,f,nm))
        if nm: named+=1
    print('sites',len(sites),'attributed-to-reflected-impl',named)
    for s,f,nm in out:
        print(hex(s), hex(f) if isinstance(f,int) else f, ','.join(nm) if nm else '')
