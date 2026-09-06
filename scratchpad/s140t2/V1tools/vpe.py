# V1: independent PE reader, written from scratch for the adversarial verification lane.
import struct

class Img:
    def __init__(self, path):
        self.raw = open(path,'rb').read()
        d = self.raw
        e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
        assert d[e_lfanew:e_lfanew+4] == b'PE\0\0'
        coff = e_lfanew+4
        self.machine, self.nsec, _, _, _, self.optsz, _ = struct.unpack_from('<HHIIIHH', d, coff)
        opt = coff+20
        self.magic = struct.unpack_from('<H', d, opt)[0]
        assert self.magic == 0x20b, hex(self.magic)
        self.imagebase = struct.unpack_from('<Q', d, opt+24)[0]
        self.sects = []
        so = opt + self.optsz
        for i in range(self.nsec):
            name, vsz, va, rsz, ptr = struct.unpack_from('<8sIIII', d, so+i*40)
            self.sects.append((name.rstrip(b'\0').decode('latin1'), va, vsz, ptr, rsz))
        self.flat = all(va == ptr for (_,va,_,ptr,_) in self.sects)
    def sec(self, name):
        for s in self.sects:
            if s[0]==name: return s
        return None
    def read(self, rva, n):
        # flat image: rva == file offset
        return self.raw[rva:rva+n]
    def in_text(self, rva):
        _,va,vsz,_,rsz = self.sec('.text')
        return va <= rva < va+max(vsz,rsz)
