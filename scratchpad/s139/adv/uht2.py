import sys, struct
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv")
from img import *
RD=[s for s in SECS if s[0]=='.rdata'][0]
RLO,RHI=RD[1],RD[1]+RD[4]
def cstr(rva, mx=64):
    e=DATA.find(b'\0',rva,rva+mx)
    if e<0: return None
    s=DATA[rva:e]
    try: return s.decode('ascii')
    except: return None
def ptrs_to(rva):
    pat=struct.pack('<Q', rva+IMAGEBASE); out=[]; i=RLO
    while True:
        i=DATA.find(pat,i,RHI)
        if i<0: break
        if i%8==0: out.append(i)
        i+=1
    return out
def rec_ok(r):
    # heuristic: name ptr into .rdata pointing at an ascii ident
    n=u64(r)-IMAGEBASE
    if not (RLO<=n<RHI): return None
    s=cstr(n)
    if not s or not s.replace('_','a').isalnum(): return None
    rep=u64(r+8)
    if rep!=0:
        rn=rep-IMAGEBASE
        if not (RLO<=rn<RHI): return None
    return s
def dump_array(anchor, name):
    """anchor = rva of an FPropertyParams record; expand the pointer array that references it."""
    # find the PropPointers array: qwords pointing at records
    ap=ptrs_to(anchor)
    for a in ap:
        # expand
        lo=a
        while lo-8>=RLO:
            v=u64(lo-8)-IMAGEBASE
            if not (RLO<=v<RHI) or rec_ok(v) is None: break
            lo-=8
        hi=a
        while hi+8<RHI:
            v=u64(hi+8)-IMAGEBASE
            if not (RLO<=v<RHI) or rec_ok(v) is None: break
            hi+=8
        n=(hi-lo)//8+1
        if n<5: continue
        print(f"### PropPointers array 0x{lo:08X} .. 0x{hi:08X}  ({n} entries)  [anchor {name}]")
        rows=[]
        for i in range(n):
            r=u64(lo+i*8)-IMAGEBASE
            nm=rec_ok(r); ad=u16(r+0x30); off=u16(r+0x32); gf=u32(r+0x18)
            rows.append((off,nm,ad,gf,r))
        for off,nm,ad,gf,r in rows:
            print(f"   +0x{off:04X}  {nm:<42} arrdim={ad} genflags=0x{gf:08X} rec=0x{r:08X}")
        return rows
    return None
if __name__=='__main__':
    want=sys.argv[1]
    # find the ascii name
    cands=[]
    pat=(want+'\0').encode()
    i=RLO
    while True:
        i=DATA.find(pat,i,RHI)
        if i<0: break
        if i==RLO or DATA[i-1]==0: cands.append(i)
        i+=1
    print(f"{len(cands)} ascii '{want}' candidates in .rdata")
    for c in cands:
        for r in ptrs_to(c):
            if rec_ok(r)==want:
                res=dump_array(r, want)
                if res: sys.exit(0)
