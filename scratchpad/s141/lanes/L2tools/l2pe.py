# L2 independent PE reader. Written from scratch; does NOT import peimg.py.
import struct, sys

class L2Img:
    def __init__(self, path):
        with open(path,'rb') as f:
            self.buf = f.read()
        b = self.buf
        assert b[0:2] == b'MZ', "no MZ"
        e_lfanew = struct.unpack_from('<I', b, 0x3C)[0]
        assert b[e_lfanew:e_lfanew+4] == b'PE\0\0', "no PE"
        coff = e_lfanew + 4
        (self.machine, self.numsec, self.timestamp, self.ptr_symtab,
         self.numsym, self.sizeopt, self.chars) = struct.unpack_from('<HHIIIHH', b, coff)
        opt = coff + 20
        self.magic = struct.unpack_from('<H', b, opt)[0]
        assert self.magic == 0x20b, "not PE32+"
        self.imagebase = struct.unpack_from('<Q', b, opt+24)[0]
        self.sect_align = struct.unpack_from('<I', b, opt+32)[0]
        self.file_align = struct.unpack_from('<I', b, opt+36)[0]
        self.sizeofimage = struct.unpack_from('<I', b, opt+56)[0]
        # section headers
        sh = opt + self.sizeopt
        self.sections = []
        for i in range(self.numsec):
            o = sh + i*40
            name = b[o:o+8].rstrip(b'\0').decode('latin1')
            # IMAGE_SECTION_HEADER after Name[8]:
            #  DWORD VirtualSize; DWORD VirtualAddress; DWORD SizeOfRawData;
            #  DWORD PointerToRawData; DWORD PointerToRelocations;
            #  DWORD PointerToLinenumbers; WORD NumberOfRelocations;
            #  WORD NumberOfLinenumbers; DWORD Characteristics;
            vsz, va, rsz, praw, prel, plin, nrel, nlin, ch = struct.unpack_from('<IIIIIIHHI', b, o+8)
            self.sections.append(dict(name=name, vsize=vsz, va=va, rsize=rsz,
                                      praw=praw, chars=ch))
    def sect_of(self, rva):
        for s in self.sections:
            if s['va'] <= rva < s['va'] + max(s['vsize'], s['rsize']):
                return s
        return None
    def is_flat(self):
        # flat == RVA equals file offset for every section
        return all(s['va'] == s['praw'] or s['rsize']==0 for s in self.sections)
    def off(self, rva):
        s = self.sect_of(rva)
        if s is None: raise ValueError("rva 0x%X in no section" % rva)
        return s['praw'] + (rva - s['va'])
    def read(self, rva, n):
        o = self.off(rva)
        return self.buf[o:o+n]
    def page_nonzero(self, rva):
        p = rva & ~0xFFF
        d = self.read(p, 0x1000)
        return sum(1 for c in d if c)

if __name__ == '__main__':
    img = L2Img(sys.argv[1] if len(sys.argv)>1 else 'dumps/merged14.dump.exe')
    print("ImageBase 0x%X  SizeOfImage 0x%X  sections %d" % (img.imagebase, img.sizeofimage, img.numsec))
    print("FLAT (rva==fileoff):", img.is_flat())
    for s in img.sections:
        print("  %-8s va=0x%08X vsz=0x%08X praw=0x%08X rsz=0x%08X ch=0x%08X" %
              (s['name'], s['va'], s['vsize'], s['praw'], s['rsize'], s['chars']))
