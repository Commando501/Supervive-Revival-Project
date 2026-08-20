#!/usr/bin/env python3
"""Grade call targets: bytes + fold match + coverage across every image on disk."""
import sys, os, struct, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cflow import Img, DUMPS, md, FOLD, annot, brtgt

ROOT = r"G:\git\Supervive Revival Project"
IMGS = {}
for k,v in DUMPS.items():
    if os.path.exists(v): IMGS[k]=v
# add every state dump
for p in glob.glob(ROOT+r"\dumps\*\SUPERVIVE-Win64-Shipping.dump.exe"):
    k=os.path.basename(os.path.dirname(p))
    if k not in IMGS: IMGS[k]=p

_loaded={}
def get(k):
    if k not in _loaded: _loaded[k]=Img(IMGS[k])
    return _loaded[k]

FOLDB = {0xF7EC20:b'\xc2\x00\x00', 0xF7EB50:b'\x33\xc0\xc3', 0xF7EB60:b'\x32\xc0\xc3', 0xB9E1F0:b'\xb0\x01\xc3'}

def grade(rva, order=None):
    order = order or ["merged4","merged3","merged2","ride","pod","tuthero"]
    order = [o for o in order if o in IMGS] + [k for k in IMGS if k not in (order or [])]
    best=None; cov={}
    for k in order:
        try: im=get(k)
        except Exception: continue
        z = im.zero_page(rva)
        cov[k] = 'ZERO' if z else 'present'
        if not z and best is None:
            best=(k, im.read(rva,24))
    return best, cov

def firstins(b, base_rva):
    out=[]
    for ins in md.disasm(b, 0x7FF6AF000000+base_rva):
        out.append(f"{ins.mnemonic} {ins.op_str}")
        if len(out)>=4: break
    return "; ".join(out)

if __name__=="__main__":
    for a in sys.argv[1:]:
        rva=int(a,0)
        best,cov = grade(rva)
        fold = FOLD.get(rva)
        if best is None:
            print(f"0x{rva:08X}  COVERAGE-BLOCKED in ALL {len(cov)} images")
        else:
            k,b = best
            isfold = ""
            for fa,fb in FOLDB.items():
                if b[:len(fb)]==fb: isfold=f"  <<FOLD {FOLD[fa]} bytes>>"
            print(f"0x{rva:08X}  [{k}] {b[:12].hex()}  {firstins(b,rva)}{isfold}")
        pres=[k for k,v in cov.items() if v=='present']
        print(f"            coverage: {len(pres)}/{len(cov)} images present" + ("" if len(pres)==len(cov) else f"  ZERO in: {[k for k,v in cov.items() if v=='ZERO']}"))
