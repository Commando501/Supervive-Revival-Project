import struct, sys, os
IMG = r"G:\git\Supervive Revival Project\dumps\merged13.dump.exe"
_d = None
def data():
    global _d
    if _d is None:
        with open(IMG,'rb') as f: _d=f.read()
    return _d
def hdr():
    d=data()
    e=struct.unpack_from('<I',d,0x3c)[0]
    assert d[e:e+4]==b'PE\0\0'
    nsec=struct.unpack_from('<H',d,e+6)[0]
    optsz=struct.unpack_from('<H',d,e+20)[0]
    magic=struct.unpack_from('<H',d,e+24)[0]
    imgbase=struct.unpack_from('<Q',d,e+24+24)[0]
    secoff=e+24+optsz
    secs=[]
    for i in range(nsec):
        o=secoff+i*40
        name=d[o:o+8].rstrip(b'\0').decode('latin1')
        vs,va,rs,pr=struct.unpack_from('<IIII',d,o+8)
        secs.append((name,va,vs,rs,pr))
    return imgbase,secs
def sec_of(rva):
    _,secs=hdr()
    for n,va,vs,rs,pr in secs:
        if va<=rva<va+max(vs,rs): return n
    return None
if __name__=='__main__':
    ib,secs=hdr()
    print("ImageBase 0x%X"%ib)
    for n,va,vs,rs,pr in secs:
        print("%-10s VA=0x%08X VS=0x%08X RAW=0x%08X PTR=0x%08X  file_off==rva? %s"%(n,va,vs,rs,pr, va==pr))
    print("filesize 0x%X"%len(data()))
