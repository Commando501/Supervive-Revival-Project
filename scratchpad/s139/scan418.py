import sys, struct, re
IMG=r"dumps/merged13.dump.exe"
d=open(IMG,'rb').read()
# parse sections
pe=struct.unpack_from('<I',d,0x3c)[0]
nsec=struct.unpack_from('<H',d,pe+6)[0]
optsz=struct.unpack_from('<H',d,pe+20)[0]
secs=[]
for i in range(nsec):
    o=pe+24+optsz+i*40
    name=d[o:o+8].rstrip(b'\0').decode('latin1')
    vs,va,rs,pr=struct.unpack_from('<IIII',d,o+8)
    secs.append((name,va,vs,pr,rs))
for s in secs: print(s)
