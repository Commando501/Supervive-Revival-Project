import sys,struct
IMG=r"dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
BASE=0x7ff608f40000
RD_VA=124035072; RD_SZ=37212160
lo=BASE+int(sys.argv[1],16); hi=BASE+int(sys.argv[2],16)
for off in range(RD_VA, RD_VA+RD_SZ-8, 8):
    v=struct.unpack_from('<Q',d,off)[0]
    if lo<=v<hi:
        print("rdata 0x%08x -> rva 0x%08x"%(off, v-BASE))
