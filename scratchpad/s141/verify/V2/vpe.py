# V2 adversarial verifier - independent PE reader. No imports from peimg/cfg/l2pe.
import struct, sys

class VImg:
    def __init__(self, path):
        with open(path,'rb') as f: self.d = f.read()
        d = self.d
        assert d[:2]==b'MZ', "not MZ"
        e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
        assert d[e_lfanew:e_lfanew+4]==b'PE\0\0', "not PE"
        coff = e_lfanew+4
        self.machine, self.nsec, _, _, _, self.optsz, self.chars = struct.unpack_from('<HHIIIHH', d, coff)
        opt = coff+20
        self.magic = struct.unpack_from('<H', d, opt)[0]
        assert self.magic == 0x20b, "not PE32+"
        self.ImageBase = struct.unpack_from('<Q', d, opt+24)[0]
        self.SectionAlignment = struct.unpack_from('<I', d, opt+32)[0]
        self.FileAlignment    = struct.unpack_from('<I', d, opt+36)[0]
        self.SizeOfImage      = struct.unpack_from('<I', d, opt+56)[0]
        self.NumberOfRvaAndSizes = struct.unpack_from('<I', d, opt+108)[0]
        self.datadirs = []
        dd = opt+112
        for i in range(self.NumberOfRvaAndSizes):
            rva,sz = struct.unpack_from('<II', d, dd+8*i)
            self.datadirs.append((rva,sz))
        sh = opt + self.optsz
        self.sections = []
        for i in range(self.nsec):
            o = sh + 40*i
            name = d[o:o+8].rstrip(b'\0').decode('latin1')
            # IMAGE_SECTION_HEADER: Name[8], VirtualSize u32 @8, VirtualAddress u32 @12,
            #                        SizeOfRawData u32 @16, PointerToRawData u32 @20, ...
            vsize, vaddr, rawsz, praw = struct.unpack_from('<IIII', d, o+8)
            chs = struct.unpack_from('<I', d, o+36)[0]
            self.sections.append(dict(name=name, vsize=vsize, vaddr=vaddr, rawsz=rawsz, praw=praw, ch=chs))
    def flat(self):
        return all(s['vaddr']==s['praw'] for s in self.sections if s['rawsz']>0)
    def sec_of(self, rva):
        for s in self.sections:
            n = max(s['vsize'], s['rawsz'])
            if s['vaddr'] <= rva < s['vaddr']+n: return s
        return None
    def off(self, rva):
        s = self.sec_of(rva)
        if s is None: return None
        if not (s['vaddr'] <= rva < s['vaddr']+s['rawsz']): return None
        return s['praw'] + (rva - s['vaddr'])
    def read(self, rva, n):
        o = self.off(rva)
        if o is None: raise KeyError(hex(rva))
        return self.d[o:o+n]
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        b = self.read(p, 4096)
        return sum(1 for x in b if x)
