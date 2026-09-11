import struct,sys
data=open(r"dumps/merged13.dump.exe",'rb').read()
BASE=0x7FF608F40000
def q(rva): return struct.unpack_from('<Q',data,rva)[0]
def pg(rva):
    p=rva&~0xFFF; return sum(1 for x in data[p:p+0x1000] if x)
def slot(vt_rva,n):
    va=q(vt_rva+n*8); return va-BASE if va else 0
VT=0x088F8570
for n in (341,342,343,340):
    r=slot(VT,n)
    print("slot %d (+0x%X): rva 0x%08X  bytes %s  page nz %d"%(n,n*8,r,data[r:r+8].hex() if r else '-',pg(r) if r else -1))
