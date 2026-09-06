# V2 adversarial verifier - PE reader written from scratch for this verification.
import struct, sys

class Img:
    def __init__(self, path):
        self.buf = open(path,'rb').read()
        b = self.buf
        e_lfanew = struct.unpack_from('<I', b, 0x3C)[0]
        assert b[e_lfanew:e_lfanew+4] == b'PE\0\0', "not PE"
        coff = e_lfanew+4
        self.nsec = struct.unpack_from('<H', b, coff+2)[0]
        sz_opt = struct.unpack_from('<H', b, coff+16)[0]
        opt = coff+20
        self.magic = struct.unpack_from('<H', b, opt)[0]
        assert self.magic == 0x20b, "not PE32+"
        self.imagebase = struct.unpack_from('<Q', b, opt+24)[0]
        self.sections = []
        so = opt + sz_opt
        for i in range(self.nsec):
            o = so + i*40
            name = b[o:o+8].rstrip(b'\0').decode('latin1')
            vsz, va, rsz, ptr = struct.unpack_from('<IIII', b, o+8)
            self.sections.append((name, va, vsz, ptr, rsz))
    def flat(self):
        return all(va == ptr for (_,va,_,ptr,_) in self.sections)
    def sec_of(self, rva):
        for (n,va,vsz,ptr,rsz) in self.sections:
            if va <= rva < va+max(vsz,rsz): return n
        return None
    def rd(self, rva, n):
        # flat image: file offset == rva
        return self.buf[rva:rva+n]
    def u8(self,r): return self.buf[r]
    def u16(self,r): return struct.unpack_from('<H',self.buf,r)[0]
    def u32(self,r): return struct.unpack_from('<I',self.buf,r)[0]
    def u64(self,r): return struct.unpack_from('<Q',self.buf,r)[0]
    def i32(self,r): return struct.unpack_from('<i',self.buf,r)[0]
    def f32(self,r): return struct.unpack_from('<f',self.buf,r)[0]
    def f64(self,r): return struct.unpack_from('<d',self.buf,r)[0]
    def va2rva(self, va):
        return va - self.imagebase
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        return sum(1 for c in self.buf[p:p+4096] if c)
    def cstr(self, rva, maxlen=256):
        end = self.buf.find(b'\0', rva, rva+maxlen)
        if end < 0: return None
        return self.buf[rva:end].decode('latin1')
