# L2 independent PE reader (written from scratch for this lane)
import struct
IMG = r"G:/git/Supervive Revival Project/dumps/merged13.dump.exe"
class PE:
    def __init__(self, path=IMG):
        self.path=path
        self.d=open(path,'rb').read()
        d=self.d
        nt=struct.unpack_from('<I',d,0x3C)[0]
        assert d[nt:nt+4]==b'PE\0\0'
        coff=nt+4
        self.nsec=struct.unpack_from('<H',d,coff+2)[0]
        optsz=struct.unpack_from('<H',d,coff+16)[0]
        opt=coff+20
        assert struct.unpack_from('<H',d,opt)[0]==0x20b
        self.base=struct.unpack_from('<Q',d,opt+24)[0]
        self.sec=[]
        sh=opt+optsz
        for i in range(self.nsec):
            o=sh+i*40
            nm=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rawsz,praw=struct.unpack_from('<IIII',d,o+8)
            self.sec.append((nm,va,vsz,praw,rawsz))
    def flat(self): return all(va==praw for _,va,_,praw,_ in self.sec)
    def secof(self,rva):
        for s in self.sec:
            nm,va,vsz,praw,rawsz=s
            if va<=rva<va+max(vsz,rawsz): return s
        return None
    def rd(self,rva,n):
        s=self.secof(rva)
        if s is None: raise ValueError(hex(rva))
        nm,va,vsz,praw,rawsz=s
        off=praw+(rva-va)
        return self.d[off:off+n]
    def u8(self,r): return self.rd(r,1)[0]
    def u16(self,r): return struct.unpack('<H',self.rd(r,2))[0]
    def u32(self,r): return struct.unpack('<I',self.rd(r,4))[0]
    def u64(self,r): return struct.unpack('<Q',self.rd(r,8))[0]
    def va2rva(self,va): return va-self.base
    def cstr(self,rva,maxn=256):
        b=self.rd(rva,maxn); i=b.find(b'\0')
        return b[:i].decode('latin1',errors='replace') if i>=0 else b.decode('latin1',errors='replace')
    def pagenz(self,rva):
        p=rva&~0xFFF
        return sum(1 for x in self.rd(p,0x1000) if x)
    def findall(self,pat,secname=None):
        out=[]
        for nm,va,vsz,praw,rawsz in self.sec:
            if secname and nm!=secname: continue
            blob=self.d[praw:praw+rawsz]
            i=0
            while True:
                j=blob.find(pat,i)
                if j<0: break
                out.append(va+j); i=j+1
        return out
    def findptr(self,rva,align=8,secname=None):
        pat=struct.pack('<Q',self.base+rva)
        return [a for a in self.findall(pat,secname) if a%align==0]
