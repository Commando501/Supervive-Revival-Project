import struct,sys
class PE:
    def __init__(self,path):
        self.data=open(path,'rb').read()
        d=self.data
        e_lfanew=struct.unpack_from('<I',d,0x3C)[0]
        assert d[e_lfanew:e_lfanew+4]==b'PE\0\0'
        coff=e_lfanew+4
        self.machine,self.nsec,_,_,_,optsz,_=struct.unpack_from('<HHIIIHH',d,coff)
        opt=coff+20
        self.magic=struct.unpack_from('<H',d,opt)[0]
        self.imagebase=struct.unpack_from('<Q',d,opt+24)[0]
        self.secs=[]
        so=opt+optsz
        for i in range(self.nsec):
            o=so+i*40
            name=d[o:o+8].rstrip(b'\0').decode('latin1')
            vsz,va,rawsz,rawptr=struct.unpack_from('<IIII',d,o+8)
            ch=struct.unpack_from('<I',d,o+36)[0]
            self.secs.append(dict(name=name,vsize=vsz,vaddr=va,rawsize=rawsz,rawptr=rawptr,chars=ch))
    def sec(self,name):
        for s in self.secs:
            if s['name']==name: return s
        return None
    def rva_read(self,rva,n):
        # flat dump: file offset == rva  (verified separately)
        return self.data[rva:rva+n]
if __name__=='__main__':
    p=PE(sys.argv[1] if len(sys.argv)>1 else 'dumps/merged13.dump.exe')
    print('file size',len(p.data))
    print('ImageBase 0x%X'%p.imagebase)
    for s in p.secs:
        flat = (s['rawptr']==s['vaddr'])
        print('%-10s va=0x%08X vsz=0x%08X rawptr=0x%08X rawsz=0x%08X flat=%s'%(s['name'],s['vaddr'],s['vsize'],s['rawptr'],s['rawsize'],flat))
