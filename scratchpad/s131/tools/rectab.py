# S131 lane-4: .data {?, name_ptr, exec_thunk, impl, ...} record table scanner.
# Read-only offline over the cold PE dumps (flat images: file offset == RVA).
import struct, sys, os, bisect
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
P = {'s129':   os.path.join(ROOT,'dumps','s129-poolgate','SUPERVIVE-Win64-Shipping.dump.exe'),
     'merged2':os.path.join(ROOT,'dumps','merged2.dump.exe'),
     'tuthero':os.path.join(ROOT,'dumps','tutorial-hero','SUPERVIVE-Win64-Shipping.dump.exe')}
FOLD = {0xF7EC20:'FOLD ret0(c2 00 00)', 0xF7EB50:'FOLD xor eax;ret', 0xF7EB60:'FOLD xor al;ret', 0xB9E1F0:'FOLD mov al,1;ret'}
STRIDE = 0x48
_c={}
def L(d):
    if d not in _c:
        data=open(P[d],'rb').read(); pe=struct.unpack_from('<I',data,0x3C)[0]
        base=struct.unpack_from('<Q',data,pe+0x30)[0]
        nsec=struct.unpack_from('<H',data,pe+6)[0]; opt=struct.unpack_from('<H',data,pe+0x14)[0]
        secs={}
        for i in range(nsec):
            o=pe+0x18+opt+i*40
            nm=data[o:o+8].rstrip(b'\x00').decode()
            secs[nm]=(struct.unpack_from('<I',data,o+12)[0], struct.unpack_from('<I',data,o+8)[0])
        _c[d]=(data,base,secs)
    return _c[d]
def cstr(data,rva,maxn=128):
    e=data.find(b'\x00',rva,rva+maxn)
    if e<0: return None
    s=data[rva:e]
    if not s: return None
    try: t=s.decode('ascii')
    except: return None
    return t if t.isprintable() else None
def scan(dump='s129'):
    """Return list of records: dict(rec_rva, name, name_rva, thunk, impl)."""
    data,base,secs=L(dump)
    tv,tsz=secs['.text']; rv,rsz=secs['.rdata']; dv,dsz=secs['.data']
    out=[]
    # a record starts at name_ptr-8; scan .data on 8-byte alignment
    end=dv+dsz
    o=dv - (dv%8)
    while o < end-0x20:
        n=struct.unpack_from('<Q',data,o)[0]
        if rv <= n-base < rv+rsz if base<=n<base+len(data) else False:
            nm=cstr(data,n-base)
            if nm and 2<=len(nm)<=96:
                th=struct.unpack_from('<Q',data,o+8)[0]
                im=struct.unpack_from('<Q',data,o+16)[0]
                if base<=th<base+len(data) and base<=im<base+len(data):
                    trv=th-base; irv=im-base
                    if tv<=trv<tv+tsz and tv<=irv<tv+tsz:
                        out.append(dict(rec=o-8, name=nm, name_rva=n-base, thunk=trv, impl=irv))
        o+=8
    return out
def runs(recs):
    """Group records into contiguous STRIDE runs."""
    recs=sorted(recs,key=lambda r:r['rec']); groups=[]; cur=[]
    for r in recs:
        if cur and r['rec']-cur[-1]['rec']==STRIDE: cur.append(r)
        else:
            if cur: groups.append(cur)
            cur=[r]
    if cur: groups.append(cur)
    return groups
def covered(irv, dumps=('s129','merged2','tuthero')):
    hit=[]
    for dn in dumps:
        data,base,secs=L(dn)
        pg=irv & ~0xFFF
        if any(data[pg:pg+0x1000]): hit.append(dn)
    return hit
def classify(irv):
    if irv in FOLD: return 'EMPTY', FOLD[irv]
    cov=covered(irv)
    if not cov: return 'IMPL-PAGE-DARK', 'impl page never decrypted in any of 3 images'
    data,base,secs=L(cov[0])
    return 'REAL', data[irv:irv+12].hex()
if __name__=='__main__':
    dump = sys.argv[1] if len(sys.argv)>1 else 's129'
    recs=scan(dump)
    g=runs(recs)
    print(f'dump={dump} records={len(recs)} runs={len(g)} stride={STRIDE:#x}')
    import collections
    print('run-length histogram:', sorted(collections.Counter(len(x) for x in g).items())[:20])
    print('total in runs>=2:', sum(len(x) for x in g if len(x)>=2))
