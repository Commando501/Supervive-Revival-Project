import sys, struct
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
data=load(); IB,secs=pehdr(data)
rd=[s for s in secs if s['name']=='.rdata'][0]
RB,RE=rd['vaddr'], rd['vaddr']+rd['vsize']
def u64(a): return struct.unpack_from('<Q',data,a)[0]
def isascii_id(a, maxlen=64):
    if not (0<a<len(data)): return None
    out=bytearray()
    for i in range(maxlen):
        c=data[a+i]
        if c==0: break
        if c<0x20 or c>0x7e: return None
        out.append(c)
    else:
        return None
    if len(out)<2: return None
    s=out.decode()
    if not (s[0].isalpha() or s[0]=='_'): return None
    return s
def findq(val, lo, hi):
    pat=struct.pack('<Q',val); pos=lo; out=[]
    while True:
        p=data.find(pat,pos,hi)
        if p<0: break
        if p%8==0: out.append(p)
        pos=p+1
    return out
for arg in sys.argv[1:]:
    fn=int(arg,16)
    va=IB+fn
    sites=findq(va, RB, RE)
    print("=== SetBitFunc 0x%08X (VA 0x%X): %d 8-aligned .rdata pointers ===" % (fn, va, len(sites)))
    for s in sites:
        print("  record region around .rdata 0x%08X:" % s)
        for off in range(-0x50, 0x20, 8):
            a=s+off
            v=u64(a)
            nm=None
            if IB<v<IB+0xB000000:
                nm=isascii_id(v-IB)
            print("    %+04d 0x%08X = 0x%016X %s" % (off, a, v, ("-> '%s'"%nm) if nm else ""))
