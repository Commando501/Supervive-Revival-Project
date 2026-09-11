import struct, sys
sys.path.insert(0,r"G:/git/Supervive Revival Project/scratchpad/s141/verify")
IMG = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"

class Img:
    def __init__(self, path=IMG):
        self.path=path
        self.data=open(path,'rb').read()
        d=self.data
        e=struct.unpack_from('<I',d,0x3C)[0]
        assert d[e:e+4]==b'PE\0\0'
        coff=e+4
        self.machine,self.nsec=struct.unpack_from('<HH',d,coff)
        self.optsz=struct.unpack_from('<H',d,coff+16)[0]
        opt=coff+20
        assert struct.unpack_from('<H',d,opt)[0]==0x20b
        self.imagebase=struct.unpack_from('<Q',d,opt+24)[0]
        self.sizeofimage=struct.unpack_from('<I',d,opt+56)[0]
        self.sections=[]
        sh=opt+self.optsz
        for i in range(self.nsec):
            o=sh+i*40
            name=d[o:o+8].rstrip(b'\0').decode('latin1')
            # IMAGE_SECTION_HEADER: Name[8], VirtualSize, VirtualAddress, SizeOfRawData, PointerToRawData
            vsz,va,rawsz,praw=struct.unpack_from('<IIII',d,o+8)
            self.sections.append(dict(name=name,vsz=vsz,va=va,rawsz=rawsz,praw=praw))
    def flat(self): return all(s['va']==s['praw'] for s in self.sections)
    def sec_of(self,rva):
        for s in self.sections:
            if s['va']<=rva<s['va']+max(s['vsz'],s['rawsz']): return s
        return None
    def read(self,rva,n):
        s=self.sec_of(rva)
        if s is None: raise ValueError(f"rva {rva:#x} in no section")
        off=s['praw']+(rva-s['va'])
        return self.data[off:off+n]
    def page_nonzero(self,rva):
        return sum(1 for x in self.read(rva & ~0xFFF,0x1000) if x)

im=Img()
if __name__=='__main__':
    print("ImageBase %#x  FLAT=%s  nsec=%d"%(im.imagebase,im.flat(),im.nsec))
    for s in im.sections:
        print("  %-10s va=%#010x praw=%#010x vsz=%#010x rawsz=%#010x %s"%(s['name'],s['va'],s['praw'],s['vsz'],s['rawsz'],'FLAT' if s['va']==s['praw'] else '*** NOT FLAT'))
