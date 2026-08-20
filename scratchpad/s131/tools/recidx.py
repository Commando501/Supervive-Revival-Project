#!/usr/bin/env python3
"""Build a reverse index name<-impl/thunk from the .data {name_ptr,thunk,impl} record table."""
import sys, os, struct, json, pickle
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cflow import Img, DUMPS

def build(img):
    b=img.buf
    dv=None;dsz=None;rv=None;rsz=None;tv=None;tsz=None
    for nm,va,vs,rp,rs in img.secs:
        if nm=='.data': dv,dsz=va,max(vs,rs)
        if nm=='.rdata': rv,rsz=va,max(vs,rs)
        if nm=='.text': tv,tsz=va,max(vs,rs)
    base=img.base
    byimpl={}; bythunk={}; recs=[]
    o=dv
    end=dv+dsz-0x20
    while o<end:
        n=struct.unpack_from('<Q',b,o)[0]
        if base<=n<base+len(b):
            nr=n-base
            if rv<=nr<rv+rsz:
                s=img.cstr(nr,96)
                if s and 2<=len(s)<=96 and all(c.isalnum() or c in '_' for c in s):
                    th=struct.unpack_from('<Q',b,o+8)[0]
                    im=struct.unpack_from('<Q',b,o+16)[0]
                    if base<=th<base+len(b) and base<=im<base+len(b):
                        t=th-base; i=im-base
                        if tv<=t<tv+tsz and tv<=i<tv+tsz:
                            recs.append((o-8,s,t,i))
                            byimpl.setdefault(i,[]).append(s)
                            bythunk.setdefault(t,[]).append(s)
        o+=8
    return recs, byimpl, bythunk

if __name__=='__main__':
    dump=sys.argv[1] if len(sys.argv)>1 else 'ride'
    img=Img(DUMPS.get(dump,dump))
    recs,byimpl,bythunk=build(img)
    out=os.path.join(os.path.dirname(os.path.abspath(__file__)),f'recidx_{dump}.pkl')
    pickle.dump({'recs':recs,'byimpl':byimpl,'bythunk':bythunk}, open(out,'wb'))
    print(f'dump={dump} records={len(recs)} distinct_impls={len(byimpl)} distinct_thunks={len(bythunk)} -> {out}')
