import sys, glob, struct, os, collections
sys.path.insert(0,'tools/strxref')
import mdpdata as MD
dumps=sorted(glob.glob(r"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp"))
sets={}
for p in dumps:
    try: d=MD.sane(MD.parse_ft(p,quiet=True))
    except Exception: continue
    if not d or d['count']!=524439: continue
    e=d['entries']
    s=set()
    for i in range(524439):
        b,en,u=struct.unpack_from('<III',e,i*12)
        if en-b>1: s.add(i)
    sets[os.path.basename(os.path.dirname(p))[-12:]]=s
print("tables:",len(sets))
szs=sorted(len(v) for v in sets.values())
print(f"per-dump REAL (decrypted) function count: min {szs[0]} median {szs[len(szs)//2]} max {szs[-1]}  of 524439 slots")
cur=set(); order=[]; rem=dict(sets)
while rem:
    k=max(rem,key=lambda k: len(rem[k]-cur))
    g=len(rem[k]-cur); cur|=rem[k]; order.append((k,g,len(cur))); del rem[k]
print("\nGREEDY marginal yield over 76 crash minidump function tables:")
print(f"{'#':>3} {'dump':>12} {'new fns':>8} {'cumulative':>10} {'cum%':>7}")
for i,(k,g,c) in enumerate(order,1):
    if i<=15 or g>0:
        print(f"{i:3d} {k:>12} {g:8d} {c:10d} {100.0*c/524439:6.2f}%")
z=sum(1 for k,g,c in order if g==0)
print(f"... {z} of {len(order)} dumps contribute ZERO new functions")
print(f"UNION: {len(cur)} / 524439 = {100.0*len(cur)/524439:.2f}%   NEVER-DECRYPTED: {524439-len(cur)} ({100.0*(524439-len(cur))/524439:.2f}%)")
