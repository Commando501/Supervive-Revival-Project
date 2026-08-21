import sys, struct, json, os
def sections(path):
    f=open(path,'rb')
    mz=f.read(0x400)
    e_lfanew=struct.unpack_from('<I',mz,0x3c)[0]
    f.seek(e_lfanew); sig=f.read(4)
    assert sig==b'PE\0\0', sig
    fh=f.read(20)
    nsec, szopt = struct.unpack_from('<H',fh,2)[0], struct.unpack_from('<H',fh,16)[0]
    opt=f.read(szopt)
    imgbase=struct.unpack_from('<Q',opt,24)[0]
    secs=[]
    for i in range(nsec):
        s=f.read(40)
        name=s[:8].rstrip(b'\0').decode()
        vsz,vaddr,rawsz,rawptr=struct.unpack_from('<IIII',s,8)
        secs.append(dict(name=name,vsize=vsz,rva=vaddr,rawsize=rawsz,rawptr=rawptr))
    return f,imgbase,secs

def textbitmap(path):
    f,imgbase,secs=sections(path)
    t=[s for s in secs if s['name']=='.text'][0]
    npages=(t['vsize']+0xfff)//0x1000
    f.seek(t['rawptr'])
    data=f.read(t['rawsize'])
    zero=b'\0'*0x1000
    bm=bytearray(npages)
    for p in range(npages):
        off=p*0x1000
        chunk=data[off:off+0x1000]
        if len(chunk)<0x1000: chunk=chunk+b'\0'*(0x1000-len(chunk))
        bm[p]= 0 if chunk==zero else 1
    return imgbase,t,npages,bm

if __name__=='__main__':
    for path in sys.argv[1:]:
        imgbase,t,npages,bm=textbitmap(path)
        nz=sum(bm)
        print(f"{os.path.basename(path)}: base=0x{imgbase:X} .text rva=0x{t['rva']:X} vsize=0x{t['vsize']:X} rawptr=0x{t['rawptr']:X} rawsize=0x{t['rawsize']:X} pages={npages} nonzero={nz} ({100.0*nz/npages:.2f}%) dark={npages-nz}")
        out=path+'.textbm'
        open(out,'wb').write(bytes(bm))
