import struct, sys, functools

class Img:
    def __init__(self, path):
        self.path=path
        self.b=open(path,'rb').read()
        e_lfanew=struct.unpack_from('<I', self.b, 0x3c)[0]
        assert self.b[e_lfanew:e_lfanew+4]==b'PE\0\0', "not PE"
        coff=e_lfanew+4
        nsec=struct.unpack_from('<H', self.b, coff+2)[0]
        optsz=struct.unpack_from('<H', self.b, coff+16)[0]
        opt=coff+20
        magic=struct.unpack_from('<H', self.b, opt)[0]
        assert magic==0x20b
        self.imagebase=struct.unpack_from('<Q', self.b, opt+24)[0]
        self.secs=[]
        so=opt+optsz
        for i in range(nsec):
            o=so+i*40
            name=self.b[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rawsz,rawptr=struct.unpack_from('<IIII', self.b, o+8)
            self.secs.append((name,va,vsz,rawptr,rawsz))
    def sec(self,name):
        for s in self.secs:
            if s[0]==name: return s
        return None
    def text(self):
        return self.sec('.text')
    def page_nonzero(self, rva):
        """count non-zero bytes in the 4096 page containing rva (file offset == rva)"""
        p=rva & ~0xFFF
        chunk=self.b[p:p+4096]
        if len(chunk)<4096: return None
        return sum(1 for c in chunk if c)
    def bytes_at(self, rva, n):
        return self.b[rva:rva+n]
    def text_page_census(self):
        n,va,vsz,rawptr,rawsz=self.text()
        assert va==rawptr, (va,rawptr)
        npages=rawsz//4096
        lit=0
        for i in range(npages):
            off=rawptr+i*4096
            if any(self.b[off:off+4096]):
                lit+=1
        return lit,npages

if __name__=='__main__':
    for p in sys.argv[1:]:
        im=Img(p)
        print(p, hex(im.imagebase), im.text())
