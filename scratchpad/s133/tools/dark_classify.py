#!/usr/bin/env python3
"""FK-20: is the dark .text a set of NEVER-CALLED FUNCTIONS, or COLD PATHS inside
functions that already run?  Uses the 382,704-row .pdata function-extent union.

CONFOUND, NAMED UP FRONT: a 4 KiB page holds many functions, so "the page is
decrypted" proves SOME code on it ran, not that a particular function ran.
Therefore the only confound-free class is FULLY-DARK (every page of the extent is
dark => the function certainly never executed).  MIXED extents are reported
separately and are an UPPER bound on "cold path inside running code".
"""
import os, glob, csv
TEXT_RVA, TEXT_END, PAGE = 0x1000, 0x1000+0x7649000, 4096
NPAGES = 0x7649000//PAGE + (1 if 0x7649000%PAGE else 0)

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
print(f"[CTRL] union pages decrypted = {sum(union)} / {NPAGES}  ({sum(union)/NPAGES*100:.2f}%)")
print(f"[CTRL] this must equal merged6's 16694 -> {'PASS' if sum(union)==16694 else 'FAIL'}")

def pg(rva): return (rva-TEXT_RVA)//PAGE

rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    r=csv.DictReader(f)
    for d in r:
        a=int(d['begin_rva'],16); b=int(d['end_rva'],16)
        if a<TEXT_RVA or b>TEXT_END: continue
        rows.append((a,b,int(d['size'])))
print(f"[CTRL] .pdata extents inside .text: {len(rows)} of 382704 rows")
covered=bytearray(NPAGES)
for a,b,_ in rows:
    for p in range(pg(a),pg(b-1)+1):
        if 0<=p<NPAGES: covered[p]=1
print(f"[CTRL] pages touched by >=1 extent: {sum(covered)} ({sum(covered)/NPAGES*100:.2f}%)")

full_dark=mixed=full_lit=0
fd_bytes=mx_bytes=fl_bytes=0
for a,b,sz in rows:
    ps=range(pg(a),pg(b-1)+1)
    lit=sum(1 for p in ps if 0<=p<NPAGES and union[p])
    n=len(list(ps))
    if lit==0: full_dark+=1; fd_bytes+=sz
    elif lit==n: full_lit+=1; fl_bytes+=sz
    else: mixed+=1; mx_bytes+=sz
tot=full_dark+mixed+full_lit
print()
print("=== FUNCTION EXTENTS BY PAGE STATE (unit: .pdata extents, n=%d) ===" % tot)
print(f"  FULLY DARK  (certainly never executed) : {full_dark:7d} ({full_dark/tot*100:5.2f}%)  {fd_bytes/1e6:7.2f} MB of extent")
print(f"  MIXED       (spans dark + decrypted)   : {mixed:7d} ({mixed/tot*100:5.2f}%)  {mx_bytes/1e6:7.2f} MB")
print(f"  FULLY LIT                              : {full_lit:7d} ({full_lit/tot*100:5.2f}%)  {fl_bytes/1e6:7.2f} MB")

# page-level attribution
dark=[i for i in range(NPAGES) if not union[i]]
d_uncl=sum(1 for i in dark if not covered[i])
print()
print("=== DARK PAGES BY .pdata COVERAGE (unit: 4 KiB pages) ===")
print(f"  dark total                       : {len(dark)}")
print(f"  dark AND covered by an extent    : {len(dark)-d_uncl}")
print(f"  dark AND covered by NO extent    : {d_uncl}   <- data-in-text / padding / leaf fns w/o unwind")

# how isolated is a dark page? neighbours
iso=both=one=0
for i in dark:
    l = union[i-1] if i>0 else 0
    r = union[i+1] if i<NPAGES-1 else 0
    if l and r: both+=1
    elif l or r: one+=1
    else: iso+=1
print()
print("=== DARK PAGE NEIGHBOURHOOD (is dark code segregated or interleaved?) ===")
print(f"  dark page with BOTH neighbours decrypted : {both:6d} ({both/len(dark)*100:5.2f}%)  <- island inside running code")
print(f"  dark page with ONE neighbour decrypted   : {one:6d} ({one/len(dark)*100:5.2f}%)  <- edge of a dark run")
print(f"  dark page with NEITHER neighbour         : {iso:6d} ({iso/len(dark)*100:5.2f}%)  <- interior of a dark region")

# seen_in_dumps column: an independent instrument
print()
print("=== CROSS-CHECK vs pdata_union.csv 'seen_in_dumps' column (independent instrument) ===")
import collections
h=collections.Counter()
with open('tools/strxref/index/pdata_union.csv') as f:
    for d in csv.DictReader(f):
        h[int(d['seen_in_dumps'])]+=1
print("  seen_in_dumps histogram (top 10):", h.most_common(10))
