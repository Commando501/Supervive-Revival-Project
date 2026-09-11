#!/usr/bin/env python3
"""FK-20: 26,054 functions were MATERIALISED (decrypted) in >=1 crash lifetime but sit on
pages DARK in all 26 dumpimage snapshots. WHICH lifetimes ran them? That names the state
worth reproducing and capturing."""
import os, sys, glob, struct, collections
sys.path.insert(0, os.path.abspath('tools/strxref'))
import mdpdata as MD
TEXT_RVA, TEXT_VSZ, PAGE = 0x1000, 0x7649000, 4096
NPAGES = TEXT_VSZ//PAGE + (1 if TEXT_VSZ%PAGE else 0)

def bitmap(path):
    bm=bytearray(NPAGES)
    with open(path,'rb') as f:
        f.seek(TEXT_RVA)
        for i in range(NPAGES):
            b=f.read(PAGE)
            if not b: break
            if b.count(0)!=len(b): bm[i]=1
    return bm
union=bytearray(NPAGES)
for p in sorted(glob.glob('dumps/*/SUPERVIVE-Win64-Shipping.dump.exe')):
    b=bitmap(p)
    for i in range(NPAGES):
        if b[i]: union[i]=1
assert sum(union)==16694, sum(union)
def dark(rva): return TEXT_RVA<=rva<TEXT_RVA+TEXT_VSZ and not union[(rva-TEXT_RVA)//PAGE]

files=[p for p in sorted(glob.glob(r'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp')) if os.path.getsize(p)>0]
rows=[]
for p in files:
    try: d=MD.sane(MD.parse_ft(p, quiet=True))
    except Exception: continue
    if not d: continue
    e=d['entries']; n=d['count']
    real=set(); darkreal=set()
    for i in range(n):
        b,en,u=struct.unpack_from('<III', e, i*12)
        if en-b>1:
            real.add(b)
            if dark(b): darkreal.add(b)
    cid=os.path.basename(os.path.dirname(p))
    mt=os.path.getmtime(p)
    rows.append((cid, mt, len(real), darkreal))

print(f"crash lifetimes with a function table: {len(rows)}")
allrare=collections.Counter()
for _,_,_,dr in rows:
    for b in dr: allrare[b]+=1
print(f"union of dark-but-materialised functions: {len(allrare)}")

import datetime
rows.sort(key=lambda r:-len(r[3]))
print()
print(f"{'crash id (16)':18s} {'date':16s} {'real fns':>9s} {'DARK-materialised':>18s}")
for cid,mt,r,dr in rows[:20]:
    print(f"{cid[13:29]:18s} {datetime.datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M'):16s} {r:9d} {len(dr):18d}")

# greedy: which minimal set of lifetimes covers the dark-materialised set?
print()
print("GREEDY: which lifetimes would have been worth a dumpimage (cover the dark-materialised set)?")
cov=set(); left=list(rows); order=[]
while left:
    best=max(left, key=lambda r: len(r[3]-cov))
    g=len(best[3]-cov)
    if g==0: break
    cov |= best[3]; order.append((best[0],best[1],g,len(cov))); left.remove(best)
for cid,mt,g,tot in order[:15]:
    print(f"  {cid[13:29]:18s} {datetime.datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M')}  +{g:6d}  -> {tot:6d}")
print(f"  ({len(order)} lifetimes needed to cover all {len(allrare)})")

# how concentrated: functions materialised in only ONE lifetime
solo=sum(1 for b,c in allrare.items() if c==1)
print(f"\ndark-materialised functions seen in exactly ONE lifetime: {solo} ({solo/len(allrare)*100:.1f}%)")
print(f"dark-materialised functions seen in >=10 lifetimes      : {sum(1 for b,c in allrare.items() if c>=10)}")
print(f"dark-materialised functions seen in ALL {len(rows)}            : {sum(1 for b,c in allrare.items() if c==len(rows))}")
