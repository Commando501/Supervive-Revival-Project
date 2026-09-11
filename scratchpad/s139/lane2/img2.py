import struct, os
IMG = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
DATA = open(IMG,'rb').read()
_pe = struct.unpack_from('<I', DATA, 0x3C)[0]
IMAGEBASE = struct.unpack_from('<Q', DATA, _pe+24+24)[0]
TEXT_LO, TEXT_HI = 0x1000, 0x1000+0x7649000
def q(rva): return struct.unpack_from('<Q', DATA, rva)[0]
def rd(rva,n): return DATA[rva:rva+n]
def vslots(vt_rva, n):
    out=[]
    for i in range(n):
        r = q(vt_rva+i*8) - IMAGEBASE
        out.append(r if TEXT_LO<=r<TEXT_HI else None)
    return out
