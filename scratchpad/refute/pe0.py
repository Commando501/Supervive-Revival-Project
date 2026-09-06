import struct,sys
P=r"dumps/merged12.dump.exe"
d=open(P,'rb').read()
print("filesize",len(d))
pe=struct.unpack_from('<I',d,0x3c)[0]
print("e_lfanew",hex(pe), d[pe:pe+4])
mach=struct.unpack_from('<H',d,pe+4)[0]
nsec=struct.unpack_from('<H',d,pe+6)[0]
optsz=struct.unpack_from('<H',d,pe+20)[0]
magic=struct.unpack_from('<H',d,pe+24)[0]
print("machine",hex(mach),"nsec",nsec,"optsz",hex(optsz),"magic",hex(magic))
ib=struct.unpack_from('<Q',d,pe+24+24)[0]
print("ImageBase",hex(ib))
off=pe+24+optsz
for i in range(nsec):
    b=d[off+i*40:off+(i+1)*40]
    name=b[0:8].rstrip(b'\0').decode('latin1')
    vs,va,rs,pr=struct.unpack_from('<IIII',b,8)
    print(f"{name:10s} VS={vs:#x} VA={va:#x} RawSize={rs:#x} PtrRaw={pr:#x}")
