"""INDEPENDENT verifier PE harness - written from scratch, not copied."""
import struct

IMG_PATH = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"

class V:
    def __init__(self, path=IMG_PATH):
        self.path=path
        self.d=open(path,'rb').read()
        d=self.d
        pe=struct.unpack_from('<I',d,0x3C)[0]
        assert d[pe:pe+4]==b'PE\0\0'
        # COFF header: Machine(2) NumberOfSections(2) TimeDateStamp(4) PtrSymTab(4) NumSyms(4)
        # SizeOfOptionalHeader(2) Characteristics(2)
        machine, nsec, tds, psym, nsym, optsz, chars = struct.unpack_from('<HHIIIHH', d, pe+4)
        self.nsec=nsec
        opt=pe+24
        magic=struct.unpack_from('<H',d,opt)[0]
        assert magic==0x20b, hex(magic)
        # PE32+: ImageBase at opt+24 (qword); SizeOfImage at opt+56
        self.imagebase=struct.unpack_from('<Q',d,opt+24)[0]
        self.sizeofimage=struct.unpack_from('<I',d,opt+56)[0]
        self.sections=[]
        sh=opt+optsz
        for i in range(nsec):
            o=sh+i*40
            # IMAGE_SECTION_HEADER: Name[8], VirtualSize(4), VirtualAddress(4),
            #                       SizeOfRawData(4), PointerToRawData(4), ...
            name=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rawsz,praw=struct.unpack_from('<IIII',d,o+8)
            self.sections.append(dict(name=name,vsz=vsz,va=va,rawsz=rawsz,praw=praw))
    def flat(self):
        return all(s['va']==s['praw'] for s in self.sections)
    def sec(self,rva):
        for s in self.sections:
            if s['va']<=rva<s['va']+max(s['vsz'],s['rawsz']): return s
        return None
    def read(self,rva,n):
        s=self.sec(rva)
        if s is None: raise ValueError(f"rva {rva:#x} no section")
        off=s['praw']+(rva-s['va'])
        return self.d[off:off+n]
    def page_nonzero(self,rva):
        return sum(1 for x in self.read(rva & ~0xFFF, 0x1000) if x)
    def q(self,rva):  # qword
        return struct.unpack_from('<Q', self.read(rva,8), 0)[0]
    def dw(self,rva):
        return struct.unpack_from('<I', self.read(rva,4), 0)[0]
