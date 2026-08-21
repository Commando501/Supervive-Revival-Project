import struct, re, collections, pickle
IB=0x7FF6AF000000
img=open('dumps/merged5.dump.exe','rb').read()
SZ=0xA9E1000
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000; TEND=TEXT+NP*0x1000
# 1) TypeDescriptor names
tds={}
for m in re.finditer(rb'\.\?A[VUW][\x20-\x7e]{1,250}?@@\x00', img):
    nstart=m.start()
    td=nstart-16
    if td<0: continue
    # pVFTable must be a pointer (type_info vftable) or 0
    p=struct.unpack_from('<Q',img,td)[0]
    if p and not (IB<=p<IB+SZ): continue
    tds[td]=m.group(0)[:-1].decode('ascii','replace')
print("TypeDescriptors found:",len(tds))
# 2) COLs in .rdata/.data
RD=0x764A000; RDE=RD+0x237D000; DA=0x99C7000; DAE=DA+0x6F0000
cols={}
for base,end in ((RD,RDE),(DA,DAE)):
    for off in range(base, end-24, 4):
        sig,offs,cd,ptd,pcd,pself=struct.unpack_from('<6I',img,off)
        if sig!=1 or pself!=off: continue
        if ptd not in tds: continue
        cols[off]=tds[ptd]
print("RTTI Complete Object Locators:",len(cols))
# 3) vtables: find qword == IB+col_rva
colset={IB+c:c for c in cols}
vt={}
for base,end in ((RD,RDE),(DA,DAE)):
    for off in range(base, end-8, 8):
        q=struct.unpack_from('<Q',img,off)[0]
        c=colset.get(q)
        if c is None: continue
        vt[off+8]=cols[c]
print("vtables located via COL:",len(vt))
# 4) expand
named=collections.defaultdict(set)
nslot=0
for v,cname in vt.items():
    off=v
    for k in range(4096):
        if off+8> len(img): break
        q=struct.unpack_from('<Q',img,off)[0]
        if not (IB+TEXT<=q<IB+TEND): break
        named[q-IB].add(cname); nslot+=1; off+=8
print("vtable slot targets in .text:",nslot," distinct RVAs:",len(named))
dk=sum(1 for r in named if bm[(r-TEXT)//0x1000]==0)
print(f"  on DARK pages: {dk} ({100.0*dk/len(named):.2f}%)")
pickle.dump({k:list(v) for k,v in named.items()},open('scratchpad/lane1/rtti.pkl','wb'))
# page coverage
pgs=collections.defaultdict(collections.Counter)
for r,cs in named.items():
    for c in cs: pgs[(r-TEXT)//0x1000][c]+=1
dpg=[i for i in range(NP) if bm[i]==0]
print(f"DARK pages named by RTTI: {sum(1 for i in dpg if i in pgs)} / {len(dpg)} ({100.0*sum(1 for i in dpg if i in pgs)/len(dpg):.2f}%)")
pickle.dump({k:dict(v) for k,v in pgs.items()},open('scratchpad/lane1/rttipg.pkl','wb'))
