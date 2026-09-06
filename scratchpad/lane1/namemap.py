import pickle, struct, collections, csv, json, bisect, sys
IB=0x7FF6AF000000
img=open('dumps/merged5.dump.exe','rb').read()
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm)
TEXT=0x1000; TEND=TEXT+NP*0x1000
def pg(r): return (r-TEXT)//0x1000 if TEXT<=r<TEND else None

names=collections.defaultdict(set)   # rva -> set of labels
mod_of=collections.defaultdict(set)  # rva -> modules

# ---- 1. lane-d census (native UFunction impls) ----
n1=0
for r in csv.DictReader(open('scratchpad/s131/lane-d-empty-impl-census.tsv',encoding='utf-8',errors='replace'),delimiter='\t'):
    try: rva=int(r['impl_rva'],16)
    except: continue
    if pg(rva) is None: continue
    names[rva].add(('UFUNC', r['class'], r['func'])); n1+=1
print("census impl labels:",n1)

# ---- 2. vtable expansion, bisect over runs ----
d=pickle.load(open('tools/strxref/index/vtables.idx','rb'))
classes=d['classes']; runs=sorted(d['runs'])
rstarts=[r[0] for r in runs]
n2=0; nres=0
for cname,info in classes.items():
    v=info.get('vtable')
    if not v: continue
    i=bisect.bisect_right(rstarts,v)-1
    if i<0: continue
    st,cnt=runs[i]
    if not (st<=v<st+8*cnt): continue
    avail=cnt-(v-st)//8
    nres+=1
    mods=info.get('modules') or ()
    for k in range(avail):
        q=struct.unpack_from('<Q',img,v+8*k)[0]
        if q<IB or q>=IB+0xA9E1000: continue
        rva=q-IB
        if pg(rva) is None: continue
        names[rva].add(('VT',cname,'')); n2+=1
        for m in mods: mod_of[rva].add(m)
print("vtable classes resolved:",nres,"of",len(classes)," vt labels:",n2)

# ---- 3. uesymbols (Z_Construct_UFunction stubs + exec thunks) ----
u=json.load(open('tools/strxref/index/uesymbols.json'))['symbols']
n3=0
for k,v in u.items():
    rva=int(k,16)
    if pg(rva) is None: continue
    nm=(v.get('names') or [''])[0]
    names[rva].add(('ZC' if v['kind']=='Z_Construct_UFunction' else 'THUNK', v.get('class',''), nm)); n3+=1
    sec=v.get('secondary')
    if sec:
        try:
            r2=int(sec,16)
            if pg(r2) is not None:
                names[r2].add(('IMPL', v.get('class',''), nm))
        except: pass
print("uesymbols labels:",n3)
pickle.dump({'names':{k:list(v) for k,v in names.items()},'mod':{k:list(v) for k,v in mod_of.items()}},
            open('scratchpad/lane1/namemap.pkl','wb'))
print("distinct named .text RVAs:",len(names))
dk=sum(1 for r in names if bm[pg(r)]==0)
print(f"  on DARK pages: {dk} ({100.0*dk/len(names):.2f}%)")
# page coverage by names
pgn=collections.defaultdict(set)
for r,v in names.items(): pgn[pg(r)] |= set(x[1] for x in v if x[1])
dpg=[i for i in range(NP) if bm[i]==0]
print(f"DARK pages with >=1 named symbol: {sum(1 for i in dpg if i in pgn)} / {len(dpg)} ({100.0*sum(1 for i in dpg if i in pgn)/len(dpg):.2f}%)")
lpg=[i for i in range(NP) if bm[i]==1]
print(f"LIT  pages with >=1 named symbol: {sum(1 for i in lpg if i in pgn)} / {len(lpg)} ({100.0*sum(1 for i in lpg if i in pgn)/len(lpg):.2f}%)")
