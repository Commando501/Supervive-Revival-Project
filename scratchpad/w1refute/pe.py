import struct,sys
class Img:
    def __init__(self,path):
        self.d=open(path,'rb').read()
        d=self.d
        pe=struct.unpack_from('<I',d,0x3c)[0]
        assert d[pe:pe+4]==b'PE\0\0'
        self.machine=struct.unpack_from('<H',d,pe+4)[0]
        nsec=struct.unpack_from('<H',d,pe+6)[0]
        optsz=struct.unpack_from('<H',d,pe+20)[0]
        opt=pe+24
        self.magic=struct.unpack_from('<H',d,opt)[0]
        self.imagebase=struct.unpack_from('<Q',d,opt+24)[0]
        self.secs=[]
        st=opt+optsz
        for i in range(nsec):
            o=st+i*40
            name=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rsz,ptr=struct.unpack_from('<IIII',d,o+8)
            self.secs.append((name,va,vsz,ptr,rsz))
    def sec_of(self,rva):
        for n,va,vsz,ptr,rsz in self.secs:
            if va<=rva<va+max(vsz,rsz): return (n,va,vsz,ptr,rsz)
        return None
    def read(self,rva,n):
        # flat dump: file offset == RVA
        return self.d[rva:rva+n]
if __name__=='__main__':
    im=Img(sys.argv[1])
    print("ImageBase 0x%X magic 0x%X machine 0x%X"%(im.imagebase,im.magic,im.machine))
    for s in im.secs: print("%-10s va=0x%08X vsz=0x%08X ptr=0x%08X rsz=0x%08X"%s)
