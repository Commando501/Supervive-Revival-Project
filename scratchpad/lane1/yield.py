import glob, os, struct, sys
sys.path.insert(0,'scratchpad/lane1')
from bitmap import textbitmap
paths=sorted(glob.glob('dumps/*/SUPERVIVE-Win64-Shipping.dump.exe'))
bms={}
for p in paths:
    ib,t,npg,bm=textbitmap(p)
    bms[os.path.basename(os.path.dirname(p))]=bytes(bm)
    print(f"{os.path.basename(os.path.dirname(p)):28s} nonzero={sum(bm):6d} ({100.0*sum(bm)/npg:5.2f}%)")
import pickle
pickle.dump(bms,open('scratchpad/lane1/bms.pkl','wb'))
NP=len(next(iter(bms.values())))
print("\npages:",NP)
# greedy maximal-coverage ordering
sets={k:set(i for i in range(NP) if v[i]) for k,v in bms.items()}
cur=set(); order=[]
rem=dict(sets)
while rem:
    k=max(rem, key=lambda k: len(rem[k]-cur))
    g=len(rem[k]-cur); cur|=rem[k]; order.append((k,g,len(cur))); del rem[k]
print("\nGREEDY marginal-yield order (each image's NEW pages given all previous):")
print(f"{'#':>3} {'image':28s} {'new':>6} {'cumulative':>10} {'cum%':>7}")
for i,(k,g,c) in enumerate(order,1):
    print(f"{i:3d} {k:28s} {g:6d} {c:10d} {100.0*c/NP:6.2f}%")
u=len(cur)
print(f"\nUNION of all {len(sets)} dumpimage snapshots: {u} pages ({100.0*u/NP:.2f}%)  dark {NP-u}")
m5=open('dumps/merged5.dump.exe.textbm','rb').read()
m5s=set(i for i in range(NP) if m5[i])
print(f"merged5: {len(m5s)}  union-not-in-merged5: {len(cur-m5s)}  merged5-not-in-union: {len(m5s-cur)}")
m6=open('dumps/merged6.dump.exe.textbm','rb').read()
m6s=set(i for i in range(NP) if m6[i])
print(f"merged6: {len(m6s)}  union-not-in-merged6: {len(cur-m6s)}  merged6-not-in-union: {len(m6s-cur)}")
