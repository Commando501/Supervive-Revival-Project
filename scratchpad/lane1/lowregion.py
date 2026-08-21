import pickle, collections, re, sys, statistics, bisect
sys.path.insert(0,'tools/strxref')
import strxref as SX
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
idx=SX.Index.load('tools/strxref/index/strxref.idx'); d=idx._dump()
PATH=re.compile(r"([A-Za-z0-9_\-\/:]*[\/])?([A-Za-z0-9_\-]+\.(?:cpp|c|h|inl|cc|asm))\s*$", re.I)
# 1) strings referenced BY lit code in each 1MB band of the low region
band=collections.defaultdict(collections.Counter)
for site,si in zip(idx.rf_site, idx.rf_str):
    band[(site-TEXT)//0x100000][si]+=1
# 2) median string rva per band -> the .rdata window parallel to that band
print("LOW .text REGION 0x0001000-0x0F01000 (below the first UE module vtable label at 0x0F7E000)")
print(f"{'band':>21} {'dark':>5} {'litpg':>6} {'refs':>6} {'median .rdata':>14}")
for b in range(16):
    p0=b*256; p1=min(NP,p0+256)
    dk=sum(1 for p in range(p0,p1) if bm[p]==0)
    lit=(p1-p0)-dk
    c=band.get(b,collections.Counter())
    rv=[idx.s_rva[si] for si in c]
    med=hex(int(statistics.median(rv))) if rv else '-'
    print(f"0x{TEXT+p0*0x1000:07X}-0x{TEXT+p1*0x1000:07X} {dk:5d} {lit:6d} {sum(c.values()):6d} {med:>14}")
    files=collections.Counter(); msgs=[]
    for si,n in c.most_common(500):
        t=idx.text_of(si,d)
        m=PATH.search(t)
        if m and ' ' not in t.strip(): files[t.strip()[-60:]]+=1
        elif 8<=len(t)<=60: msgs.append(t)
    if files: print("      FILES:", " | ".join(k for k,_ in files.most_common(6)))
    if msgs:  print("      STR:  ", " | ".join(repr(x) for x in msgs[:8]))
