import struct, sys
P={'s129':r'G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe',
   'merged2':r'G:\git\Supervive Revival Project\dumps\merged2.dump.exe',
   'tuthero':r'G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe'}
_c={}
def L(d):
    if d not in _c:
        data=open(P[d],'rb').read(); pe=struct.unpack_from('<I',data,0x3C)[0]
        _c[d]=(data,struct.unpack_from('<Q',data,pe+0x30)[0])
    return _c[d]
FOLD={0xF7EC20:'FOLD ret0',0xF7EB50:'FOLD xor eax;ret',0xF7EB60:'FOLD xor al;ret',0xB9E1F0:'FOLD mov al,1;ret'}
def find(name, d='s129'):
    data,base=L(d)
    tgt=name.encode()+b'\x00'
    out=[]
    i=0
    while True:
        i=data.find(tgt,i)
        if i<0: break
        # must be an exact ASCII string start (preceded by NUL)
        if i>0 and data[i-1]==0:
            nptr=struct.pack('<Q',base+i)
            j=0
            while True:
                j=data.find(nptr,j)
                if j<0: break
                th=struct.unpack_from('<Q',data,j+8)[0]
                im=struct.unpack_from('<Q',data,j+0x10)[0]
                if base < th < base+0x8000000 and base < im < base+0x8000000:
                    out.append((i,j,th-base,im-base))
                j+=1
        i+=1
    return out
if __name__=='__main__':
    for n in sys.argv[1:]:
        r=find(n)
        if not r: print(f'{n:44s} NO RECORD'); continue
        for (s,rec,th,im) in r:
            cov=[d for d in P if any(L(d)[0][im&~0xFFF:(im&~0xFFF)+0x1000])]
            data,_=L(cov[0]) if cov else (None,None)
            b=data[im:im+10].hex() if cov else ''
            print(f'{n:44s} rec={rec:#x} thunk={th:#x} impl={im:#x} {FOLD.get(im,""):18s} implcov={cov} bytes={b}')