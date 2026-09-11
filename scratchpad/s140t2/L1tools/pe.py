# L1 independent PE reader for merged13.dump.exe (flat dump: RVA == file offset).
# Written from scratch for S140 Tier 2 lane 1. Imports nothing from tools/ or scratchpad/s140.
import struct, sys, os

class PE:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.buf = f.read()
        b = self.buf
        assert b[:2] == b'MZ', 'not MZ'
        e_lfanew = struct.unpack_from('<I', b, 0x3C)[0]
        assert b[e_lfanew:e_lfanew+4] == b'PE\0\0', 'not PE'
        coff = e_lfanew + 4
        (self.machine, self.nsec, self.timestamp, self.symptr, self.nsym,
         self.optsize, self.chars) = struct.unpack_from('<HHIIIHH', b, coff)
        opt = coff + 20
        self.magic = struct.unpack_from('<H', b, opt)[0]
        assert self.magic == 0x20b, 'not PE32+'
        self.imagebase = struct.unpack_from('<Q', b, opt + 24)[0]
        self.sizeofimage = struct.unpack_from('<I', b, opt + 56)[0]
        self.ndd = struct.unpack_from('<I', b, opt + 108)[0]
        self.datadirs = []
        dd = opt + 112
        for i in range(self.ndd):
            va, sz = struct.unpack_from('<II', b, dd + 8*i)
            self.datadirs.append((va, sz))
        self.sections = []
        st = opt + self.optsize
        for i in range(self.nsec):
            o = st + 40*i
            name = b[o:o+8].rstrip(b'\0').decode('latin1')
            vsz, va, rsz, rptr = struct.unpack_from('<IIII', b, o+8)
            chars = struct.unpack_from('<I', b, o+36)[0]
            self.sections.append(dict(name=name, vsize=vsz, rva=va, rawsize=rsz,
                                      rawptr=rptr, chars=chars))
        self.flat = all(s['rva'] == s['rawptr'] for s in self.sections)

    def sec_of(self, rva):
        for s in self.sections:
            if s['rva'] <= rva < s['rva'] + max(s['vsize'], s['rawsize']):
                return s
        return None

    def read(self, rva, n):
        # flat dump: file offset == rva
        return self.buf[rva:rva+n]

    def u8(self, rva):  return self.buf[rva]
    def u32(self, rva): return struct.unpack_from('<I', self.buf, rva)[0]
    def u64(self, rva): return struct.unpack_from('<Q', self.buf, rva)[0]

    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        return sum(1 for c in self.buf[p:p+4096] if c)

DUMP = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'dumps', 'merged13.dump.exe')
def load():
    return PE(os.path.abspath(DUMP))

if __name__ == '__main__':
    pe = load()
    print('flat:', pe.flat)
    print('imagebase: 0x%X' % pe.imagebase)
    print('sizeofimage: 0x%X' % pe.sizeofimage)
    for s in pe.sections:
        print('  %-8s rva=0x%08X vsz=0x%08X rawptr=0x%08X rawsz=0x%08X chars=0x%08X' %
              (s['name'], s['rva'], s['vsize'], s['rawptr'], s['rawsize'], s['chars']))
