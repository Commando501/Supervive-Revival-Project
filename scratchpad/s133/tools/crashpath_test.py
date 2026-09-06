#!/usr/bin/env python3
"""HYPOTHESIS: the 18,964 functions materialised in ALL 76 crash lifetimes but dark in all
26 dumpimage snapshots are the CRASH/UNWIND path -- code that by construction only runs
while the process is dying, which `dumpimage` (run on a LIVE process) can never capture.

TEST: dumps/crash-*/ were captured by `usmapdump crashwatch` (suspend at crash, dump before
death). If the hypothesis holds, those 7 images should hold MORE of the universal-dark set
than the live-state images do. If they hold the same (zero), crashwatch suspends too early
and the hypothesis is untested, not confirmed."""
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
imgs=[q.replace(os.sep,'/') for q in sorted(glob.glob('dumps/*/SUPERVIVE-Win64-Shipping.dump.exe'))]
bms={q.split('/')[1]:bitmap(q) for q in imgs}
crashimgs=[n for n in bms if n.startswith('crash-')]
liveimgs =[n for n in bms if not n.startswith('crash-')]
def uni(ns):
    u=bytearray(NPAGES)
    for n in ns:
        b=bms[n]
        for i in range(NPAGES):
            if b[i]: u[i]=1
    return u
U_all=uni(bms); U_crash=uni(crashimgs); U_live=uni(liveimgs)
print(f"crashwatch images: {len(crashimgs)}  union pages {sum(U_crash)}")
print(f"live-state images: {len(liveimgs)}   union pages {sum(U_live)}")
print(f"all              : {len(bms)}        union pages {sum(U_all)}")
print(f"pages the crashwatch images have that the live images LACK: "
      f"{sum(1 for i in range(NPAGES) if U_crash[i] and not U_live[i])}")

files=[p for p in sorted(glob.glob(r'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp')) if os.path.getsize(p)>0]
cnt=collections.Counter(); ndump=0
for p in files:
    try: d=MD.sane(MD.parse_ft(p, quiet=True))
    except Exception: continue
    if not d: continue
    ndump+=1; e=d['entries']
    for i in range(d['count']):
        b,en,u=struct.unpack_from('<III', e, i*12)
        if en-b>1: cnt[b]+=1
universal=[b for b,c in cnt.items() if c==ndump and TEXT_RVA<=b<TEXT_RVA+TEXT_VSZ]
print(f"\nfunctions materialised in ALL {ndump} crash lifetimes: {len(universal)}")
def pgof(r): return (r-TEXT_RVA)//PAGE
u_dark_all  =[b for b in universal if not U_all[pgof(b)]]
u_dark_live =[b for b in universal if not U_live[pgof(b)]]
u_dark_crash=[b for b in universal if not U_crash[pgof(b)]]
print(f"  dark in ALL 26 images        : {len(u_dark_all)}")
print(f"  dark in the 19 LIVE images   : {len(u_dark_live)}")
print(f"  dark in the 7 CRASHWATCH imgs: {len(u_dark_crash)}")
rescued = len(u_dark_live)-len(u_dark_all)
print(f"  => crashwatch images RESCUE {rescued} of them that live images lack")
print(f"\nVERDICT: {'crashwatch DOES reach code live dumps cannot' if rescued>0 else 'crashwatch reaches NOTHING extra -> hypothesis UNTESTED by this instrument, not confirmed'}")

# where do the universal-dark functions live? bucket by 1 MB of RVA
h=collections.Counter()
for b in u_dark_all: h[(b>>20)]+=1
print("\nuniversal-dark function entries by 1 MB RVA bucket (top 15):")
for k,v in h.most_common(15): print(f"   RVA {k<<20:#010x} - {((k+1)<<20)-1:#010x} : {v:6d} functions")
