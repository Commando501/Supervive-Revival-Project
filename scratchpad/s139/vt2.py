import struct
IMG=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
data=open(IMG,'rb').read()
pe=struct.unpack_from('<I',data,0x3c)[0]
IB=struct.unpack_from('<Q',data,pe+24+24)[0]
def vt(rva,n):
    return [ (struct.unpack_from('<Q',data,rva+i*8)[0] or 0) and struct.unpack_from('<Q',data,rva+i*8)[0]-IB for i in range(n)]
c=vt(0x07FBED58,420); l=vt(0x088F8570,420)
d=[i for i in range(420) if c[i]!=l[i]]
print("CMC vs LokiCMC differing slots:", len(d))
for i in d: print("  [%3d] cmc=0x%08X loki=0x%08X"%(i,c[i],l[i]))
