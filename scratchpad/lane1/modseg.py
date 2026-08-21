import pickle, collections, bisect
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
nm=pickle.load(open('scratchpad/lane1/namemap.pkl','rb')); mods=nm['mod']
# per-RVA single module label only when unambiguous
pts=[]
for r,ms in mods.items():
    if len(ms)==1: pts.append((r,ms[0]))
pts.sort()
print("unambiguous module-labelled .text RVAs:",len(pts))
# how contiguous? measure per-page dominant module and run lengths
perpage=collections.defaultdict(collections.Counter)
for r,m in pts: perpage[(r-TEXT)//0x1000][m]+=1
dom={p:c.most_common(1)[0][0] for p,c in perpage.items()}
purity=[c.most_common(1)[0][1]/sum(c.values()) for c in perpage.values()]
print(f"pages with a module label: {len(dom)} ; mean per-page dominant-module purity {sum(purity)/len(purity):.3f}")
ps=sorted(dom)
runs=[]; i=0
while i<len(ps):
    j=i
    while j+1<len(ps) and dom[ps[j+1]]==dom[ps[i]] and ps[j+1]-ps[j]<=8: j+=1
    runs.append((ps[i],ps[j],dom[ps[i]],j-i+1)); i=j+1
runs.sort(key=lambda r:-(r[1]-r[0]))
print(f"module segments (same module, gaps<=8 pages): {len(runs)}")
print("top 25 segments by page span:")
for a,b,m,n in runs[:25]:
    span=b-a+1
    dk=sum(1 for p in range(a,b+1) if bm[p]==0)
    print(f"  0x{TEXT+a*0x1000:07X}-0x{TEXT+(b+1)*0x1000:07X} span={span:5d}pg labelled={n:5d} dark={dk:5d} ({100.0*dk/span:5.1f}%)  {m}")
pickle.dump({'dom':dom,'segs':runs},open('scratchpad/lane1/modseg.pkl','wb'))
