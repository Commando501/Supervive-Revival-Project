import struct, sys

class Img:
    def __init__(self, path):
        self.path = path
        self.b = open(path,'rb').read()
        pe = struct.unpack_from('<I', self.b, 0x3c)[0]
        assert self.b[pe:pe+4] == b'PE\0\0'
        nsec = struct.unpack_from('<H', self.b, pe+6)[0]
        optsz = struct.unpack_from('<H', self.b, pe+20)[0]
        opt = pe+24
        self.magic = struct.unpack_from('<H', self.b, opt)[0]
        self.imagebase = struct.unpack_from('<Q', self.b, opt+24)[0]
        self.sections = []
        so = opt+optsz
        for i in range(nsec):
            o = so + i*40
            name = self.b[o:o+8].rstrip(b'\0').decode('ascii','replace')
            vsz, va, rawsz, raw = struct.unpack_from('<IIII', self.b, o+8)
            self.sections.append((name, va, vsz, raw, rawsz))
    def sec(self, rva):
        for s in self.sections:
            if s[1] <= rva < s[1]+max(s[2],s[4]):
                return s
        return None
    def read(self, rva, n):
        # flat dump: file offset == rva
        return self.b[rva:rva+n]
    def u64(self, rva): return struct.unpack_from('<Q', self.b, rva)[0]
    def u32(self, rva): return struct.unpack_from('<I', self.b, rva)[0]
    def va2rva(self, va): return va - self.imagebase
    def rva2va(self, rva): return rva + self.imagebase

def find_all(b, pat, start=0, end=None):
    out=[]; i=start
    end = len(b) if end is None else end
    while True:
        j = b.find(pat, i, end)
        if j < 0: break
        out.append(j); i = j+1
    return out
