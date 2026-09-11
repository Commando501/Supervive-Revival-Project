# Independent minimal PE reader for merged13. Written for the V3 verifier lane.
import struct, sys, os
IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"

class Img:
    def __init__(self, path=IMG):
        self.buf = open(path,'rb').read()
        b = self.buf
        e_lfanew = struct.unpack_from('<I', b, 0x3C)[0]
        assert b[e_lfanew:e_lfanew+4] == b'PE\0\0'
        coff = e_lfanew+4
        nsec = struct.unpack_from('<H', b, coff+2)[0]
        sizeopt = struct.unpack_from('<H', b, coff+16)[0]
        opt = coff+20
        magic = struct.unpack_from('<H', b, opt)[0]
        assert magic == 0x20b
        self.imagebase = struct.unpack_from('<Q', b, opt+24)[0]
        self.secs = []
        so = opt + sizeopt
        for i in range(nsec):
            o = so + i*40
            name = b[o:o+8].rstrip(b'\0').decode('latin1')
            vsize, vaddr, rawsize, rawptr = struct.unpack_from('<IIII', b, o+8)
            self.secs.append((name, vaddr, vsize, rawptr, rawsize))
    def sec(self, name):
        for s in self.secs:
            if s[0]==name: return s
        return None
    # file-offset == RVA in this dump; verify
    def rd(self, rva, n):
        return self.buf[rva:rva+n]
    def u8(self,rva): return self.buf[rva]
    def u32(self,rva): return struct.unpack_from('<I', self.buf, rva)[0]
    def i32(self,rva): return struct.unpack_from('<i', self.buf, rva)[0]
    def u64(self,rva): return struct.unpack_from('<Q', self.buf, rva)[0]
    def f32(self,rva): return struct.unpack_from('<f', self.buf, rva)[0]
    def va2rva(self, va): return va - self.imagebase
    def rva2va(self, rva): return rva + self.imagebase

if __name__ == '__main__':
    im = Img()
    print("ImageBase 0x%X" % im.imagebase)
    for s in im.secs:
        print("%-10s vaddr=0x%08X vsize=0x%08X rawptr=0x%08X rawsize=0x%08X  fo==rva? %s" % (s[0],s[1],s[2],s[3],s[4], s[1]==s[3]))
