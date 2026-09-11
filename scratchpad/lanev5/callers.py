import sys, struct, csv, bisect
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
data=load(); IB,secs=pehdr(data)
tx=[s for s in secs if s['name']=='.text'][0]; TB,TE=tx['vaddr'],tx['vaddr']+tx['vsize']
prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f): prows.append((int(x['begin_rva'],16),int(x['end_rva'],16)))
prows.sort(); pbeg=[a for a,_ in prows]
def ext(r):
    i=bisect.bisect_right(pbeg,r)-1
    if i<0: return None
    b,e=prows[i]
    if not(b<=r<e): return None
    j=i
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    return prows[j][0]
def lit(r):
    p=r&~0xFFF; return any(data[p:p+0x1000])
for a in sys.argv[1:]:
    t=int(a,16); out=[]
    for p in range(TB, TE-5):
        b=data[p]
        if b!=0xE8 and b!=0xE9: continue
        if not lit(p): continue
        d=struct.unpack_from('<i',data,p+1)[0]
        if p+5+d==t: out.append((p,'call' if b==0xE8 else 'jmp'))
    print("targets of 0x%X: %d rel32 site(s) in LIT .text"%(t,len(out)))
    for p,k in out[:25]:
        print("   %s from 0x%08X (fn 0x%s)"%(k,p, ('%X'%ext(p)) if ext(p) else 'NO-PDATA'))
