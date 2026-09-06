import pickle, struct, collections, sys
d=pickle.load(open('tools/strxref/index/vtables.idx','rb'))
classes=d['classes']; runs=d['runs']
IB=d['imagebase']
img=open('dumps/merged5.dump.exe','rb').read()
# sections
secs=d['sections']
print("sections:",[(s[0],hex(s[1]),hex(s[2])) for s in secs])
TEXT=0x1000; TEXTV=0x7649000; TEND=TEXT+TEXTV
RD=0x764A000; RDV=0x237D000
runmap={r[0]:r[1] for r in runs}
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm)
def pgdark(r): 
    if not(TEXT<=r<TEND): return None
    return bm[(r-TEXT)//0x1000]==0
percls=collections.defaultdict(lambda:[set(),set()])   # class -> (dark rvas, lit rvas)
permod=collections.defaultdict(lambda:[set(),set()])
nvt=0; nslots=0; badvt=0
for cname,info in classes.items():
    v=info.get('vtable')
    if not v: continue
    cnt=runmap.get(v)
    if not cnt: badvt+=1; continue
    nvt+=1
    off=v  # file offset == rva
    mods=info.get('modules') or ('?',)
    for k in range(cnt):
        q=struct.unpack_from('<Q',img,off+8*k)[0]
        if q<IB or q>=IB+0xA9E1000: continue
        rva=q-IB
        st=pgdark(rva)
        if st is None: continue
        nslots+=1
        percls[cname][0 if st else 1].add(rva)
        for m in mods: permod[m][0 if st else 1].add(rva)
print(f"classes with a resolvable vtable run: {nvt} (unresolvable {badvt}); .text slot targets read: {nslots}")
allrva=set()
darkrva=set()
for c,(dk,lt) in percls.items():
    allrva|=dk|lt; darkrva|=dk
print(f"distinct .text RVAs named by vtable expansion: {len(allrva)}  of which on DARK pages: {len(darkrva)} ({100.0*len(darkrva)/len(allrva):.2f}%)")
print()
print("=== per-UE-MODULE vtable-target darkness (distinct .text RVAs) ===")
rows=[]
for m,(dk,lt) in permod.items():
    dkn=len(dk-lt); ltn=len(lt)
    rows.append((len(dk),len(lt),m))
rows.sort(key=lambda r:-r[0])
print(f"{'dark':>6} {'lit':>6} {'%dark':>6}  module")
for dk,lt,m in rows[:45]:
    tot=dk+lt
    print(f"{dk:6d} {lt:6d} {100.0*dk/tot:5.1f}%  {m}")
pickle.dump({'percls':{k:(list(v[0]),list(v[1])) for k,v in percls.items()},
             'permod':{k:(list(v[0]),list(v[1])) for k,v in permod.items()}},
            open('scratchpad/lane1/vtexp.pkl','wb'))
