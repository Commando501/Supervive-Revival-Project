#!/usr/bin/env python3
"""Walk a function (via chained .pdata extent) and report every call target,
   flagging known stripped folds and undecrypted pages."""
import sys, os, csv, struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cflow import Img, DUMPS, md, FOLD, brtgt
import pickle

ROOT=r"G:\git\Supervive Revival Project"
rows=[(int(r['begin_rva'],16),int(r['end_rva'],16)) for r in csv.DictReader(open(ROOT+r"\tools\strxref\index\pdata_union.csv"))]
rows.sort()
IDX=pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'recidx_ride.pkl'),'rb'))
BYIMPL=IDX['byimpl']

def extent(start):
    """union of contiguous pdata rows beginning at start"""
    i=None
    for k,(b,e) in enumerate(rows):
        if b==start: i=k; break
    if i is None: return None
    end=rows[i][1]
    j=i+1
    while j<len(rows) and rows[j][0]==end:
        end=rows[j][1]; j+=1
    return start,end

def scan(img, lo, hi):
    data=img.read(lo,hi-lo)
    calls=[]
    for ins in md.disasm(data, img.base+lo):
        if ins.mnemonic in ('call','jmp'):
            t=brtgt(ins,img.base)
            if t is not None and ins.mnemonic=='call':
                calls.append((ins.address-img.base,t,'direct'))
            elif t is None and ins.mnemonic=='call':
                calls.append((ins.address-img.base,None,ins.op_str))
    return calls

if __name__=='__main__':
    img=Img(DUMPS['merged4'])
    for a in sys.argv[1:]:
        s=int(a,0)
        ex=extent(s)
        if ex is None:
            print(f"\n### 0x{s:08X}  NO .pdata row starting here (harvest gap / never-run)"); continue
        lo,hi=ex
        dark = img.zero_page(lo)
        nm=BYIMPL.get(s,[])
        print(f"\n### 0x{lo:08X}..0x{hi:08X} ({hi-lo} B) {nm}  {'PAGE-DARK' if dark else ''}")
        if dark: continue
        cs=scan(img,lo,hi)
        nf=0
        for site,t,kind in cs:
            if t is None:
                print(f"    0x{site:08X}  INDIRECT {kind}")
            else:
                f=FOLD.get(t)
                z=img.zero_page(t)
                mark = f"  <<< STRIPPED {f} >>>" if f else ("  [callee page DARK]" if z else "")
                if f: nf+=1
                print(f"    0x{site:08X}  -> 0x{t:08X} {BYIMPL.get(t,[''])[0]:<32}{mark}")
        print(f"    == stripped-fold calls in body: {nf}")
