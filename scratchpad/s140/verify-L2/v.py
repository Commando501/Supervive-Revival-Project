import struct, sys
from capstone import *
from capstone.x86 import *

PATH = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
IMAGEBASE_EXPECT = 0x7FF608F40000

class Img:
    def __init__(self, path=PATH):
        self.buf = open(path,'rb').read()
        pe = struct.unpack_from('<I', self.buf, 0x3C)[0]
        assert self.buf[pe:pe+4] == b'PE\0\0'
        nsec = struct.unpack_from('<H', self.buf, pe+6)[0]
        optsz = struct.unpack_from('<H', self.buf, pe+20)[0]
        self.magic = struct.unpack_from('<H', self.buf, pe+24)[0]
        self.imagebase = struct.unpack_from('<Q', self.buf, pe+24+24)[0]
        secoff = pe+24+optsz
        self.secs=[]
        for i in range(nsec):
            o = secoff+i*40
            name = self.buf[o:o+8].rstrip(b'\0').decode('latin1')
            vsz, va, rawsz, rawptr = struct.unpack_from('<IIII', self.buf, o+8)
            self.secs.append((name, va, vsz, rawptr, rawsz))
    def flat(self):
        return all(va==rawptr for (_,va,_,rawptr,_) in self.secs)
    def sec_of(self, rva):
        for (n,va,vsz,rp,rs) in self.secs:
            if va <= rva < va+max(vsz,rs): return n
        return None
    def read(self, rva, n):
        return self.buf[rva:rva+n]
    def u64(self, rva): return struct.unpack_from('<Q', self.buf, rva)[0]
    def u32(self, rva): return struct.unpack_from('<I', self.buf, rva)[0]
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        return sum(1 for b in self.buf[p:p+0x1000] if b)

im = Img()
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail=True

def dis(rva, n=1):
    out=[]
    for i in md.disasm(im.read(rva, 16*n+16), rva):
        out.append(i)
        if len(out)>=n: break
    return out

def d1(rva):
    return dis(rva,1)[0]

def show(rva, n):
    for i in dis(rva,n):
        print("0x%08x  %-24s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
