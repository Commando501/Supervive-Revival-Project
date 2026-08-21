# Independent .text page bitmap, different code path from lane1/bitmap.py:
# uses numpy reshape + any(axis=1) rather than per-page bytes comparison,
# and verifies section table fields explicitly.
import sys, struct, os, numpy as np

def text_sec(path):
    with open(path,'rb') as f:
        mz=f.read(0x1000)
        e=struct.unpack_from('<I',mz,0x3c)[0]
        assert mz[e:e+4]==b'PE\0\0'
        nsec=struct.unpack_from('<H',mz,e+6)[0]
        szopt=struct.unpack_from('<H',mz,e+20)[0]
        base=struct.unpack_from('<Q',mz,e+24+24)[0]
        so=e+24+szopt
        for i in range(nsec):
            s=mz[so+40*i:so+40*i+40]
            nm=s[:8].rstrip(b'\0').decode()
            vsz,rva,rawsz,rawptr=struct.unpack_from('<IIII',s,8)
            if nm=='.text':
                return base,rva,vsz,rawsz,rawptr
    raise SystemExit('no .text '+path)

def bm(path):
    base,rva,vsz,rawsz,rawptr=text_sec(path)
    n=min(vsz,rawsz)
    npg=(vsz+0xfff)//0x1000
    a=np.fromfile(path,dtype=np.uint8,count=n,offset=rawptr)
    if len(a)<npg*0x1000:
        a=np.concatenate([a,np.zeros(npg*0x1000-len(a),np.uint8)])
    pg=a[:npg*0x1000].reshape(npg,0x1000)
    return base,rva,vsz,rawsz,rawptr,npg,(pg!=0).any(axis=1)

if __name__=='__main__':
    for p in sys.argv[1:]:
        base,rva,vsz,rawsz,rawptr,npg,b=bm(p)
        print(f"{p}\tbase=0x{base:X} rva=0x{rva:X} vsz=0x{vsz:X} rawsz=0x{rawsz:X} rawptr=0x{rawptr:X} pages={npg} lit={int(b.sum())} ({100*b.sum()/npg:.4f}%) dark={npg-int(b.sum())}")
        np.save(os.path.join('scratchpad/verify', os.path.basename(os.path.dirname(p)) or os.path.basename(p))+'.npy', b)
