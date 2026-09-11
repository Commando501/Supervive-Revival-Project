import struct
P=r'G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll'
D=open(P,'rb').read()
print("filesize", len(D), hex(len(D)))
assert D[:2]==b'MZ'
e_lfanew=struct.unpack_from('<I',D,0x3C)[0]
print("e_lfanew",hex(e_lfanew), D[e_lfanew:e_lfanew+4])
mach,nsec,tds,psym,nsym,osz,chars=struct.unpack_from('<HHIIIHH',D,e_lfanew+4)
print("machine",hex(mach),"nsec",nsec,"optsize",osz)
opt=e_lfanew+24
magic=struct.unpack_from('<H',D,opt)[0]
print("optmagic",hex(magic))
aoep=struct.unpack_from('<I',D,opt+16)[0]
imgbase=struct.unpack_from('<Q',D,opt+24)[0]
sizeofimg=struct.unpack_from('<I',D,opt+56)[0]
numrva=struct.unpack_from('<I',D,opt+108)[0]
print("AddressOfEntryPoint",hex(aoep))
print("ImageBase",hex(imgbase),"== 2**33 ?",imgbase==2**33)
print("SizeOfImage",hex(sizeofimg))
print("NumberOfRvaAndSizes",numrva)
dd=opt+112
names=["EXPORT","IMPORT","RESOURCE","EXCEPTION","SECURITY","BASERELOC","DEBUG","ARCH","GLOBALPTR","TLS","LOADCFG","BOUND","IAT","DELAY","COMDESC","RES"]
for i in range(numrva):
    r,s=struct.unpack_from('<II',D,dd+8*i)
    if r or s: print("  DD %-10s rva %08x size %08x"%(names[i],r,s))
sh=opt+osz
SEC=[]
for i in range(nsec):
    o=sh+40*i
    nm=D[o:o+8].rstrip(b'\0').decode('latin1')
    vs,va,rs,ra=struct.unpack_from('<IIII',D,o+8)
    ch=struct.unpack_from('<I',D,o+36)[0]
    SEC.append((nm,va,vs,ra,rs,ch))
    print("  SEC %-9s va %08x vs %08x ra %08x rs %08x ch %08x exec=%d"%(nm,va,vs,ra,rs,ch,bool(ch&0x20000000)))
import json
json.dump(SEC,open(r'scratchpad/s132/verify/l6/mysecs.json','w'))
