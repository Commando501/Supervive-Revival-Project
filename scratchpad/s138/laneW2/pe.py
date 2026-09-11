import struct, sys

class PE:
    def __init__(self, path):
        self.path = path
        self.data = open(path,'rb').read()
        d = self.data
        e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
        assert d[e_lfanew:e_lfanew+4] == b'PE\0\0'
        coff = e_lfanew+4
        self.machine, self.nsec, _, _, _, self.optsz, self.chars = struct.unpack_from('<HHIIIHH', d, coff)
        opt = coff+20
        self.magic = struct.unpack_from('<H', d, opt)[0]
        assert self.magic == 0x20b, hex(self.magic)
        self.imagebase = struct.unpack_from('<Q', d, opt+24)[0]
        self.secoff = opt + self.optsz
        self.sections = []
        for i in range(self.nsec):
            o = self.secoff + i*40
            name = d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz, va, rawsz, rawptr = struct.unpack_from('<IIII', d, o+8)
            chars = struct.unpack_from('<I', d, o+36)[0]
            self.sections.append(dict(name=name, vsz=vsz, va=va, rawsz=rawsz, rawptr=rawptr, chars=chars))
    def sec_of_rva(self, rva):
        for s in self.sections:
            if s['va'] <= rva < s['va'] + max(s['vsz'], s['rawsz']):
                return s
        return None
    def read(self, rva, n):
        # flat dump: file offset == rva
        return self.data[rva:rva+n]

if __name__ == '__main__':
    p = PE(sys.argv[1] if len(sys.argv)>1 else 'dumps/merged13.dump.exe')
    print('ImageBase 0x%X  nsec=%d  filesize=%d' % (p.imagebase, p.nsec, len(p.data)))
    for s in p.sections:
        print('%-10s va=0x%08X vsz=0x%08X rawptr=0x%08X rawsz=0x%08X chars=0x%08X' % (s['name'], s['va'], s['vsz'], s['rawptr'], s['rawsz'], s['chars']))
