#!/usr/bin/env python3
"""FK-20: shape of the dark .text set, + order-independent per-image value."""
import os, glob, struct
TEXT_RVA, TEXT_VSZ, PAGE = 0x1000, 0x7649000, 4096
NPAGES = (TEXT_VSZ + PAGE - 1)//PAGE

def bitmap(path):
    bm = bytearray(NPAGES)
    with open(path,'rb') as f:
        f.seek(TEXT_RVA)
        for i in range(NPAGES):
            b=f.read(PAGE)
            if not b: break
            if b.count(0)!=len(b): bm[i]=1
    return bm

imgs=[q.replace(os.sep,'/') for q in sorted(glob.glob('dumps/*/SUPERVIVE-Win64-Shipping.dump.exe'))]
names=[q.split('/')[1] for q in imgs]
bms={n:bitmap(p) for p,n in zip(imgs,names)}
union=bytearray(NPAGES)
for n in names:
    b=bms[n]
    for i in range(NPAGES):
        if b[i]: union[i]=1

th=bms['tutorial-hero']
print("=== ORDER-INDEPENDENT VALUE: pages an image has that tutorial-hero (the best single image) lacks ===")
rows=[]
for n in names:
    if n=='tutorial-hero': continue
    b=bms[n]
    rows.append((n, sum(1 for i in range(NPAGES) if b[i] and not th[i])))
for n,c in sorted(rows,key=lambda kv:-kv[1]):
    print(f"  {n:38s} {c:5d}")
print()
print("=== LEAVE-ONE-OUT: pages LOST from the union if this image were deleted ===")
for n in names:
    others=bytearray(NPAGES)
    for m in names:
        if m==n: continue
        b=bms[m]
        for i in range(NPAGES):
            if b[i]: others[i]=1
    lost=sum(1 for i in range(NPAGES) if union[i] and not others[i])
    if lost: print(f"  {n:38s} {lost:5d} pages would be lost")
print()
dark=[i for i in range(NPAGES) if not union[i]]
print(f"=== DARK SET: {len(dark)} pages = {len(dark)*PAGE/1e6:.1f} MB ({len(dark)/NPAGES*100:.2f}%) ===")
runs=[]; s=dark[0]; prev=dark[0]
for i in dark[1:]:
    if i!=prev+1: runs.append((s,prev)); s=i
    prev=i
runs.append((s,prev))
runs.sort(key=lambda r:-(r[1]-r[0]+1))
print(f"contiguous dark runs: {len(runs)}   (mean {len(dark)/len(runs):.1f} pages/run)")
tot=0
print("top 25 runs:")
for a,b in runs[:25]:
    n=b-a+1; tot+=n
    print(f"   RVA {TEXT_RVA+a*PAGE:#010x} .. {TEXT_RVA+(b+1)*PAGE-1:#010x}  {n:5d} pages  {n*PAGE/1024:8.0f} KB")
print(f"top-25 runs cover {tot} of {len(dark)} dark pages ({tot/len(dark)*100:.1f}%)")
import collections
h=collections.Counter()
for a,b in runs:
    n=b-a+1
    k = 1 if n==1 else 2 if n<=4 else 3 if n<=16 else 4 if n<=64 else 5 if n<=256 else 6
    h[k]+= n
lbl={1:'1 page',2:'2-4',3:'5-16',4:'17-64',5:'65-256',6:'>256'}
print("dark pages by run length:")
for k in sorted(h): print(f"   {lbl[k]:>8s}: {h[k]:6d} pages")
