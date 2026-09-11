import pickle, struct, collections, bisect, array
img=open('dumps/merged5.dump.exe','rb').read()
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm)
TEXT=0x1000; TEND=TEXT+NP*0x1000
def pgof(r): return (r-TEXT)//0x1000
ft=pickle.load(open('scratchpad/lane1/ft.pkl','rb'))
BEG,END,PHB=ft['BEG'],ft['END'],ft['PHB']
N=len(BEG)
# real extents sorted
ext=[(BEG[i],END[i]) for i in range(N) if END[i]]
ext.sort()
estart=[e[0] for e in ext]
def enclosing(r):
    i=bisect.bisect_right(estart,r)-1
    if i<0: return None
    b,e=ext[i]
    return b if b<=r<e else None
nm=pickle.load(open('scratchpad/lane1/namemap.pkl','rb'))
names=nm['names']; mods=nm['mod']
# scan lit pages for rel32 calls/jmps landing in dark pages
edges=collections.defaultdict(collections.Counter)   # dark page -> Counter(caller function rva)
ncall=0
for p in range(NP):
    if bm[p]==0: continue
    base=TEXT+p*0x1000
    off=base
    chunk=img[off:off+0x1000+8]
    for k in range(len(chunk)-5):
        op=chunk[k]
        if op!=0xE8 and op!=0xE9: continue
        rel=struct.unpack_from('<i',chunk,k+1)[0]
        src=base+k
        tgt=src+5+rel
        if not (TEXT<=tgt<TEND): continue
        tp=pgof(tgt)
        if bm[tp]!=0: continue
        f=enclosing(src)
        edges[tp][f if f is not None else -1]+=1
        ncall+=1
print(f"rel32 call/jmp edges from LIT pages into DARK pages: {ncall}; distinct dark pages targeted: {len(edges)}")
pickle.dump({k:dict(v) for k,v in edges.items()},open('scratchpad/lane1/edges.pkl','wb'))
dpg=[i for i in range(NP) if bm[i]==0]
print(f"DARK pages reached by >=1 lit rel32 edge: {sum(1 for i in dpg if i in edges)} / {len(dpg)} ({100.0*sum(1 for i in dpg if i in edges)/len(dpg):.2f}%)")
# how many of those callers are NAMED
namedc=0; totc=0
for tp,c in edges.items():
    for f in c:
        totc+=1
        if f in names: namedc+=1
print(f"caller function starts: {totc} (with dups across pages); named {namedc}")
