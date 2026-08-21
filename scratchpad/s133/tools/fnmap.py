#!/usr/bin/env python3
"""FK-20: build the COMPLETE function map from the packer's dynamic RUNTIME_FUNCTION
table, INCLUDING the placeholders that pdataunion.py discards.

A slot with EndAddress == BeginAddress+1 is a function the packer had NOT materialised
(decrypted) in that process. BeginAddress is still valid. So the table gives the entry
RVA of EVERY function in the image, decrypted or not -- a complete function map of a
packed binary, for free.

Then: how many functions live in the pages that are dark in ALL 26 dumpimage snapshots?
"""
import os, sys, glob, struct, collections
sys.path.insert(0, os.path.abspath('tools/strxref'))
import mdpdata as MD

TEXT_RVA, TEXT_VSZ, PAGE = 0x1000, 0x7649000, 4096
NPAGES = TEXT_VSZ//PAGE + (1 if TEXT_VSZ%PAGE else 0)

files=[p for p in sorted(glob.glob(r'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\UECC-*\UEMinidump.dmp')) if os.path.getsize(p)>0]
print(f"UECC dumps: {len(files)}")

allbegin=set(); real=collections.Counter(); slots=None; ok=0
percount=[]
for p in files:
    try: d=MD.sane(MD.parse_ft(p, quiet=True))
    except Exception: continue
    if not d: continue
    ok+=1; e=d['entries']; n=d['count']
    if slots is None: slots=n
    r=0
    for i in range(n):
        b,en,u = struct.unpack_from('<III', e, i*12)
        allbegin.add(b)
        if en-b>1: real[b]+=1; r+=1
    percount.append(r)
print(f"[CTRL] dumps with a usable function table: {ok}")
print(f"[CTRL] slots per table: {slots}  (constant across dumps: {'yes' if slots else 'n/a'})")
print(f"[CTRL] distinct BeginAddress values across all dumps: {len(allbegin)}")
print(f"        -> equals slot count? {'PASS' if len(allbegin)==slots else 'NO ('+str(len(allbegin))+' vs '+str(slots)+')'}")
print(f"[CTRL] real (materialised) functions per dump: min {min(percount)}  max {max(percount)}  median {sorted(percount)[len(percount)//2]}")
print(f"UNION of materialised functions across {ok} dumps: {len(real)}")
print(f"NEVER materialised in ANY of {ok} dumps: {len(allbegin)-len(real)}")
print(f"  => function-level coverage of the crash corpus: {len(real)/len(allbegin)*100:.2f}%")

# our image union bitmap
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
union=bytearray(NPAGES)
for p in imgs:
    b=bitmap(p)
    for i in range(NPAGES): 
        if b[i]: union[i]=1
print(f"\n[CTRL] dumpimage union decrypted pages: {sum(union)} (must be 16694: {'PASS' if sum(union)==16694 else 'FAIL'})")

intext=[b for b in allbegin if TEXT_RVA<=b<TEXT_RVA+TEXT_VSZ]
print(f"\n=== FUNCTION MAP vs OUR IMAGE CORPUS (unit: functions) ===")
print(f"functions with entry inside .text: {len(intext)} of {len(allbegin)}")
lit=sum(1 for b in intext if union[(b-TEXT_RVA)//PAGE])
print(f"  entry on a page our images DECRYPTED : {lit:7d} ({lit/len(intext)*100:5.2f}%)")
print(f"  entry on a page DARK in all 26 images: {len(intext)-lit:7d} ({(len(intext)-lit)/len(intext)*100:5.2f}%)")

r_lit = sum(1 for b in real if TEXT_RVA<=b<TEXT_RVA+TEXT_VSZ and union[(b-TEXT_RVA)//PAGE])
r_dark= sum(1 for b in real if TEXT_RVA<=b<TEXT_RVA+TEXT_VSZ and not union[(b-TEXT_RVA)//PAGE])
print(f"\nOf the {len(real)} functions the packer MATERIALISED in >=1 crash lifetime:")
print(f"  we HAVE the bytes (entry page decrypted in our images) : {r_lit:7d}")
print(f"  we LACK the bytes (entry page dark in all 26 images)   : {r_dark:7d}   <- executed somewhere, never captured")

nev = [b for b in intext if b not in real]
nev_lit = sum(1 for b in nev if union[(b-TEXT_RVA)//PAGE])
print(f"\nOf the {len(nev)} functions NEVER materialised in any crash lifetime:")
print(f"  entry page decrypted in our images anyway: {nev_lit:7d}  <- our captures reached code the crashes never did")
print(f"  entry page dark in our images too        : {len(nev)-nev_lit:7d}  <- dark in BOTH corpora")

with open('scratchpad/s133/evidence/fnmap_dark_entries.txt','w') as f:
    for b in sorted(b for b in intext if not union[(b-TEXT_RVA)//PAGE]):
        f.write(f"{b:#010x}\n")
print("\nwrote scratchpad/s133/evidence/fnmap_dark_entries.txt")
