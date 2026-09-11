import struct, sys, os
DUMPS = {
    "merged2": r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe",
    "tuthero": r"G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
    "merged":  r"G:\git\Supervive Revival Project\dumps\merged.dump.exe",
    "s129":    r"G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe",
    "merged3": r"G:\git\Supervive Revival Project\dumps\merged3.dump.exe",
    "merged4": r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe",
    "rideable": r"G:\git\Supervive Revival Project\dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe",
}
class Img:
    def __init__(self, path):
        self.path=path
        self.buf=open(path,'rb').read()
        b=self.buf
        e=struct.unpack_from("<I",b,0x3C)[0]
        assert b[e:e+4]==b"PE\0\0"
        coff=e+4; nsec=struct.unpack_from("<H",b,coff+2)[0]; szopt=struct.unpack_from("<H",b,coff+16)[0]
        opt=coff+20
        self.imagebase=struct.unpack_from("<Q",b,opt+24)[0]
        self.sections=[]
        sh=opt+szopt
        for i in range(nsec):
            o=sh+i*40
            name=b[o:o+8].rstrip(b"\0").decode('latin1')
            vsize,vaddr,rawsize,rawptr=struct.unpack_from("<IIII",b,o+8)
            self.sections.append((name,vaddr,vsize,rawptr,rawsize))
    def sec_of(self,rva):
        for s in self.sections:
            if s[1]<=rva<s[1]+max(s[2],s[4]): return s
        return None
    def off(self,rva):
        s=self.sec_of(rva)
        return None if not s else s[3]+(rva-s[1])
    def read(self,rva,n):
        o=self.off(rva)
        return None if o is None else self.buf[o:o+n]
def load(n): return Img(DUMPS[n])
