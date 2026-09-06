"""Independent PE reader for merged14 - written from scratch, NOT peimg.py."""
import struct
PATH = r"G:/git/Supervive Revival Project/dumps/merged14.dump.exe"
class VImg:
    def __init__(self, path=PATH):
        self.path=path
        self.d=open(path,'rb').read()
        d=self.d
        lf=struct.unpack_from('<I',d,0x3C)[0]
        assert d[lf:lf+4]==b'PE\0\0'
        coff=lf+4
        mach,nsec=struct.unpack_from('<HH',d,coff)
        optsz=struct.unpack_from('<H',d,coff+16)[0]
        opt=coff+20
        magic=struct.unpack_from('<H',d,opt)[0]
        assert magic==0x20b, hex(magic)
        self.imagebase=struct.unpack_from('<Q',d,opt+24)[0]
        self.secs=[]
        sh=opt+optsz
        for i in range(nsec):
            o=sh+i*40
            nm=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rawsz,praw=struct.unpack_from('<IIII',d,o+8)
            self.secs.append((nm,va,vsz,praw,rawsz))
    def off(self,rva):
        for nm,va,vsz,praw,rawsz in self.secs:
            if va<=rva<va+max(vsz,rawsz):
                return praw+(rva-va)
        raise ValueError(hex(rva))
    def read(self,rva,n): 
        o=self.off(rva); return self.d[o:o+n]
    def pnz(self,rva):
        p=rva&~0xFFF
        return sum(1 for x in self.read(p,0x1000) if x)
if __name__=='__main__':
    im=VImg()
    print("ImageBase",hex(im.imagebase))
    flat=all(va==praw for nm,va,vsz,praw,rawsz in im.secs)
    print("sections",len(im.secs),"FLAT(va==praw all):",flat)
    for nm,va,vsz,praw,rawsz in im.secs:
        print(f"  {nm:10s} va={va:#010x} praw={praw:#010x} vsz={vsz:#010x} raw={rawsz:#010x} {'FLAT' if va==praw else '***NOTFLAT***'}")
