import struct,sys
IMG="dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
IB=0x7ff608f40000
RD=(0x0764A000,0x0764A000+0x0237D000)
DA=(0x099C7000,0x099C7000+0x006F0000)
def findq(rva, lo=RD[0], hi=RD[1]):
    tgt=struct.pack("<Q", IB+rva)
    out=[];i=lo
    while True:
        j=d.find(tgt,i,hi)
        if j<0:break
        out.append(j); i=j+1
    return out
if __name__=="__main__":
    for a in sys.argv[1:]:
        r=int(a,16)
        hits=findq(r)
        print("ptr to 0x%08X : %d hits in .rdata"%(r,len(hits)))
        for h in hits[:40]: print("   at .rdata 0x%08X"%h)
