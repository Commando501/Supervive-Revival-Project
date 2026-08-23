import struct, sys
IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
D = open(IMG,'rb').read()
e_lfanew = struct.unpack_from('<I', D, 0x3c)[0]
assert D[e_lfanew:e_lfanew+4]==b'PE\0\0'
mach, nsec = struct.unpack_from('<HH', D, e_lfanew+4)
sizeopt = struct.unpack_from('<H', D, e_lfanew+20)[0]
opt = e_lfanew+24
magic = struct.unpack_from('<H', D, opt)[0]
imgbase = struct.unpack_from('<Q', D, opt+24)[0]
print("machine %04x nsec %d optmagic %04x ImageBase 0x%X" % (mach,nsec,magic,imgbase))
sectab = opt + sizeopt
SEC=[]
for i in range(nsec):
    o = sectab+i*40
    name = D[o:o+8].rstrip(b'\0').decode('latin1')
    vsz, va, rawsz, rawptr = struct.unpack_from('<IIII', D, o+8)
    ch = struct.unpack_from('<I', D, o+36)[0]
    SEC.append((name,va,vsz,rawptr,rawsz,ch))
    print("  %-8s VA %08X VSz %08X Raw %08X RawSz %08X Ch %08X" % (name,va,vsz,rawptr,rawsz,ch))
