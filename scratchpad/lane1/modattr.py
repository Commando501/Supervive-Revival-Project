import pickle, collections, bisect
bm=open('dumps/merged5.dump.exe.textbm','rb').read(); NP=len(bm); TEXT=0x1000
ms=pickle.load(open('scratchpad/lane1/modseg.pkl','rb')); dom=ms['dom']
ps=sorted(dom)
print(f"labelled pages: {len(ps)}  first 0x{TEXT+ps[0]*0x1000:07X}  last 0x{TEXT+ps[-1]*0x1000:07X}")
MAXD=48
assign={}; amb=0; far=0
for p in range(NP):
    if p in dom: assign[p]=dom[p]; continue
    i=bisect.bisect_left(ps,p)
    lo=ps[i-1] if i>0 else None
    hi=ps[i] if i<len(ps) else None
    dl=p-lo if lo is not None else 10**9
    dh=hi-p if hi is not None else 10**9
    if min(dl,dh)>MAXD: far+=1; continue
    if lo is not None and hi is not None and dom[lo]==dom[hi]: assign[p]=dom[lo]
    else:
        assign[p]=dom[lo] if dl<=dh else dom[hi]; amb+=1
print(f"pages attributed: {len(assign)} ; boundary-ambiguous {amb} ; unattributed (>{MAXD}pg from any label) {far}")
tot=collections.Counter(); dk=collections.Counter()
for p,m in assign.items():
    tot[m]+=1
    if bm[p]==0: dk[m]+=1
UNA=[p for p in range(NP) if p not in assign]
unad=sum(1 for p in UNA if bm[p]==0)
print(f"UNATTRIBUTED region: {len(UNA)} pages, dark {unad} ({100.0*unad/len(UNA):.1f}%)  = {100.0*unad/13592:.1f}% of ALL dark pages")
print()
print("=== PER-MODULE .text pages (attributed by nearest module label, purity 99.1%) ===")
print(f"{'dark':>6} {'total':>6} {'%dark':>6} {'darkKB':>8}  module")
rows=sorted(tot.items(), key=lambda kv:-dk[kv[0]])
sd=0
for m,t in rows[:60]:
    print(f"{dk[m]:6d} {t:6d} {100.0*dk[m]/t:5.1f}% {dk[m]*4:8d}  {m}")
print()
print("sum of dark across all attributed modules:",sum(dk.values()))
pickle.dump({'assign':assign,'tot':dict(tot),'dark':dict(dk)},open('scratchpad/lane1/modattr.pkl','wb'))
