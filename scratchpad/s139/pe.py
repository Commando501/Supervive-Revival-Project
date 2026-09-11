import struct, sys, os
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..","..","dumps","merged13.dump.exe")
IMG = os.path.abspath(IMG)
DATA = open(IMG,'rb').read()
def pe_info():
    e_lfanew = struct.unpack_from('<I', DATA, 0x3C)[0]
    assert DATA[e_lfanew:e_lfanew+4]==b'PE\0\0'
    fh = e_lfanew+4
    nsec = struct.unpack_from('<H', DATA, fh+2)[0]
    optsz = struct.unpack_from('<H', DATA, fh+16)[0]
    opt = fh+20
    magic = struct.unpack_from('<H', DATA, opt)[0]
    imgbase = struct.unpack_from('<Q', DATA, opt+24)[0]
    secs=[]
    so = opt+optsz
    for i in range(nsec):
        b = so+i*40
        name = DATA[b:b+8].rstrip(b'\0').decode()
        vsz, va, rawsz, rawptr = struct.unpack_from('<IIII', DATA, b+8)
        secs.append((name, va, vsz, rawptr, rawsz))
    return imgbase, secs
IMAGEBASE, SECS = pe_info()
def sec_of(rva):
    for n,va,vsz,rp,rs in SECS:
        if va <= rva < va+max(vsz,rs): return n
    return None
def rd(rva, n):
    return DATA[rva:rva+n]
def q(rva):
    return struct.unpack_from('<Q', DATA, rva)[0]
def va2rva(va):
    return va - IMAGEBASE
if __name__=='__main__':
    print(hex(IMAGEBASE))
    for s in SECS: print(s[0], hex(s[1]), hex(s[2]), hex(s[3]), hex(s[4]))
