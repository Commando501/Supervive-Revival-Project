import struct, capstone
P=r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
d=open(P,'rb').read()
pe=struct.unpack_from('<I',d,0x3c)[0]
nsec=struct.unpack_from('<H',d,pe+6)[0]; opt=struct.unpack_from('<H',d,pe+20)[0]
IB=struct.unpack_from('<Q',d,pe+24+24)[0]
secs=[]
for i in range(nsec):
    o=pe+24+opt+i*40
    n=d[o:o+8].rstrip(b'\0').decode()
    vs,va,rs,pr=struct.unpack_from('<IIII',d,o+8)
    secs.append((n,va,vs,pr,rs))
print("IB=%#x"%IB); print(secs[:4])
text=[s for s in secs if s[0]=='.text'][0]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def dis(a,n=60):
    return list(md.disasm(d[a:a+n*8],a,count=n))
print("=== engine PerformMovement bail block 0x035EB7CF ===")
for i in dis(0x035EB7CF,40):
    print("%08X %-28s %s"%(i.address,i.mnemonic,i.op_str))
