# Resolve the containing function of an arbitrary .text address, using
#  (1) every aligned .rdata/_RDATA/.data qword that points into .text  (vtables/fn tables)
#  (2) every direct `e8 rel32` call target found by a byte scan of .text  (a FLOOR: only lit pages)
# containing function ~= greatest known entry <= addr.
import sys, os, struct, pickle
sys.path.insert(0, os.path.dirname(__file__))
from pe import load
pe = load()
CACHE = os.path.join(os.path.dirname(__file__), 'entries.pkl')

def build():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE,'rb'))
    TEXT=[s for s in pe.sections if s['name']=='.text'][0]
    T0,T1 = TEXT['rva'], TEXT['rva']+TEXT['vsize']
    IB = pe.imagebase
    ents=set()
    ptr_src={}
    for sn in ('.rdata','.data','_RDATA','.rodata'):
        S=[s for s in pe.sections if s['name']==sn]
        if not S: continue
        S=S[0]
        base=S['rva']; end=base+S['rawsize']
        b=pe.buf
        for off in range(base, end-8, 8):
            q=struct.unpack_from('<Q', b, off)[0]
            if q==0: continue
            r=q-IB
            if T0<=r<T1:
                ents.add(r); ptr_src.setdefault(r,off)
    # direct call targets
    b=pe.buf; start=T0
    while True:
        p=b.find(b'\xe8', start, T1-5)
        if p<0: break
        start=p+1
        rel=struct.unpack_from('<i', b, p+1)[0]
        t=p+5+rel
        if T0<=t<T1 and b[t]!=0:
            ents.add(t)
    ents=sorted(ents)
    pickle.dump((ents,ptr_src), open(CACHE,'wb'))
    return ents,ptr_src

import bisect
_E=None; _P=None
def owner(addr, maxback=0x6000):
    global _E,_P
    if _E is None: _E,_P = build()
    i=bisect.bisect_right(_E, addr)-1
    if i<0: return None
    e=_E[i]
    if addr-e > maxback: return None
    return e

def is_vtable_ptr(rva):
    global _E,_P
    if _E is None: _E,_P = build()
    return _P.get(rva)
