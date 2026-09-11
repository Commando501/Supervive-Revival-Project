import struct, sys
P=r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
d=open(P,'rb').read()
print("filesize",hex(len(d)))
e_lfanew=struct.unpack_from('<I',d,0x3c)[0]
print("e_lfanew",hex(e_lfanew), d[e_lfanew:e_lfanew+4])
nsec=struct.unpack_from('<H',d,e_lfanew+6)[0]
optsz=struct.unpack_from('<H',d,e_lfanew+20)[0]
opt=e_lfanew+24
magic=struct.unpack_from('<H',d,opt)[0]
imgbase=struct.unpack_from('<Q',d,opt+24)[0]
print("magic",hex(magic),"ImageBase",hex(imgbase),"nsec",nsec,"optsz",hex(optsz))
sec=opt+optsz
flat=True
for i in range(nsec):
    o=sec+i*40
    name=d[o:o+8].rstrip(b'\0').decode()
    vs,va,rs,pr=struct.unpack_from('<IIII',d,o+8)
    ok = (va==pr)
    flat &= ok
    print(f"  {name:10} VA={va:#010x} VS={vs:#010x} PR={pr:#010x} RS={rs:#010x} flat={ok}")
print("FLAT ALL:",flat)
