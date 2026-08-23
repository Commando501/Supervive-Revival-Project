import struct,sys
IMG=r"dumps/merged13.dump.exe"
BASE=0x7FF608F40000
D=open(IMG,'rb').read()
RD_VA=0x0764A000; RD_SZ=0x237D000
def find_ptr(rva):
    tgt=struct.pack('<Q',BASE+rva)
    res=[];i=RD_VA
    end=RD_VA+RD_SZ
    while True:
        j=D.find(tgt,i,end)
        if j<0: break
        if j%8==0: res.append(j)
        i=j+1
    return res
def q(rva): return struct.unpack_from('<Q',D,rva)[0]
def r(rva):
    v=q(rva)
    return v-BASE if v>=BASE and v<BASE+0x0A800000 else None
if __name__=='__main__':
    if sys.argv[1]=='findptr':
        for a in sys.argv[2:]:
            rva=int(a,16)
            hits=find_ptr(rva)
            print("0x%08X -> %d aligned .rdata slots: %s"%(rva,len(hits),", ".join("0x%08X"%h for h in hits[:20])))
    elif sys.argv[1]=='slots':
        st=int(sys.argv[2],16); n=int(sys.argv[3]) if len(sys.argv)>3 else 8
        for i in range(n):
            a=st+i*8
            print("  [%3d] +0x%03X  0x%08X -> %s"%(i,i*8,a, ("0x%08X"%r(a)) if r(a) is not None else hex(q(a))))
