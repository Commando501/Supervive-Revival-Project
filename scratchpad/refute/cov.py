import struct
P=r"dumps/merged12.dump.exe"
d=open(P,'rb').read()
TEXT_VA=0x1000; TEXT_SZ=0x7649000; TEXT_RAW=0x1000
npg=TEXT_SZ//0x1000
lit=0
litset=bytearray(npg)
for i in range(npg):
    off=TEXT_RAW+i*0x1000
    if d[off:off+0x1000].count(0)!=0x1000:
        lit+=1; litset[i]=1
print("text pages",npg,"lit",lit,"pct",round(100*lit/npg,2))
open("scratchpad/refute/litpages.bin","wb").write(bytes(litset))
