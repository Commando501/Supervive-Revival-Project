"""S140 offline image harness. RVA==file offset verification + capstone helpers."""
import struct, sys

DEFAULT_IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"

class Img:
    def __init__(self, path=DEFAULT_IMG):
        self.path = path
        with open(path, 'rb') as f:
            self.data = f.read()
        self._parse()

    def _parse(self):
        d = self.data
        e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
        assert d[e_lfanew:e_lfanew+4] == b'PE\0\0', "not a PE"
        coff = e_lfanew + 4
        self.machine, self.nsec, _, _, _, self.optsz, self.chars = struct.unpack_from('<HHIIIHH', d, coff)
        opt = coff + 20
        magic = struct.unpack_from('<H', d, opt)[0]
        assert magic == 0x20b, "not PE32+"
        self.imagebase = struct.unpack_from('<Q', d, opt+24)[0]
        self.sizeofimage = struct.unpack_from('<I', d, opt+56)[0]
        self.sections = []
        sh = opt + self.optsz
        for i in range(self.nsec):
            o = sh + i*40
            name = d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz, va, rawsz, praw = struct.unpack_from('<IIII', d, o+8)
            self.sections.append(dict(name=name, vsz=vsz, va=va, rawsz=rawsz, praw=praw))

    def flat(self):
        """True iff every section has VirtualAddress == PointerToRawData."""
        return all(s['va'] == s['praw'] for s in self.sections)

    def sec_of(self, rva):
        for s in self.sections:
            if s['va'] <= rva < s['va'] + max(s['vsz'], s['rawsz']):
                return s
        return None

    def read(self, rva, n):
        s = self.sec_of(rva)
        if s is None:
            raise ValueError(f"rva {rva:#x} in no section")
        off = s['praw'] + (rva - s['va'])
        return self.data[off:off+n]

    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        b = self.read(p, 0x1000)
        return sum(1 for x in b if x)

if __name__ == '__main__':
    im = Img(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMG)
    print(f"ImageBase {im.imagebase:#x}  SizeOfImage {im.sizeofimage:#x}  sections {im.nsec}")
    print(f"FLAT (va==praw for all sections): {im.flat()}")
    for s in im.sections:
        print(f"  {s['name']:10s} va={s['va']:#010x} praw={s['praw']:#010x} vsz={s['vsz']:#010x} rawsz={s['rawsz']:#010x} {'FLAT' if s['va']==s['praw'] else '*** NOT FLAT ***'}")
