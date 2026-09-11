import struct,sys
sys.path.insert(0,r"G:\git\Supervive Revival Project\scratchpad\s139\adv2")
from pe2 import data,hdr,sec_of
IB,_=hdr()
d=data()
TEXT_LO,TEXT_HI=0x1000,0x1000+0x07649000
def q(rva): return struct.unpack_from('<Q',d,rva)[0]
def torva(v):
    if v==0: return 0
    if IB<=v<IB+len(d): return v-IB
    return None
def run(vt,maxn=600):
    out=[]
    for i in range(maxn):
        v=q(vt+i*8)
        r=torva(v)
        if r is None or not (TEXT_LO<=r<TEXT_HI): break
        out.append(r)
    return out
if __name__=='__main__':
    for name,vt in [("LOKI_CMC",0x088F8570),("CMC",0x07FBED58)]:
        r=run(vt)
        print("%s vt=0x%08X raw .text-ptr run = %d qwords, ends at 0x%08X (next qword raw=%r)"%(
            name,vt,len(r),vt+len(r)*8, hex(q(vt+len(r)*8))))
