#!/usr/bin/env python3
"""S132 lane-B helpers: fast rip-relative / rel32 / qword xrefs over a cold PE dump.
Flat images: file offset == RVA. Read-only.
"""
import sys, struct, numpy as np

DUMPS = {
 "merged4": r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe",
 "merged3": r"G:\git\Supervive Revival Project\dumps\merged3.dump.exe",
 "merged2": r"G:\git\Supervive Revival Project\dumps\merged2.dump.exe",
 "tuthero": r"G:\git\Supervive Revival Project\dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe",
 "s129":    r"G:\git\Supervive Revival Project\dumps\s129-poolgate\SUPERVIVE-Win64-Shipping.dump.exe",
 "rideable":r"G:\git\Supervive Revival Project\dumps\s131-rideable-live\SUPERVIVE-Win64-Shipping.dump.exe",
 "droppod": r"G:\git\Supervive Revival Project\dumps\s131-droppod-live\SUPERVIVE-Win64-Shipping.dump.exe",
}

class Img:
    def __init__(self, path):
        self.path=path
        self.buf=open(path,'rb').read()
        b=self.buf
        pe=struct.unpack_from('<I',b,0x3C)[0]
        nsec=struct.unpack_from('<H',b,pe+6)[0]
        szopt=struct.unpack_from('<H',b,pe+0x14)[0]
        opt=pe+0x18
        self.imagebase=struct.unpack_from('<Q',b,opt+24)[0]
        self.sections={}
        sh=opt+szopt
        for i in range(nsec):
            o=sh+i*40
            nm=b[o:o+8].rstrip(b'\0').decode('latin1')
            vs,va,rs,rp=struct.unpack_from('<IIII',b,o+8)
            self.sections[nm]=(va,vs,rp,rs)
        self.arr=np.frombuffer(self.buf,dtype=np.uint8)
    def sec(self,n): return self.sections[n]
    def read(self,rva,n): return self.buf[rva:rva+n]
    def rel32_disp_array(self, secname='.text'):
        va,vs,rp,rs=self.sections[secname]
        # int32 view at every byte offset
        return va,rs
    def riprel(self, target_rva, secname='.text'):
        """Return list of disp32 FIELD rvas D such that D+4+disp == target."""
        va,vs,rp,rs=self.sections[secname]
        n=rs-4
        seg=self.arr[va:va+rs]
        d=np.frombuffer(seg.tobytes(), dtype='<i4', count=0) # placeholder
        # build unaligned int32 by combining shifted views
        b0=seg[0:n].astype(np.int64)
        b1=seg[1:n+1].astype(np.int64)
        b2=seg[2:n+2].astype(np.int64)
        b3=seg[3:n+3].astype(np.int64)
        disp=(b0 | (b1<<8) | (b2<<16) | (b3<<24))
        disp=np.where(disp>=0x80000000, disp-0x100000000, disp)
        idx=np.arange(n,dtype=np.int64)+va
        hit=np.nonzero(idx+4+disp==target_rva)[0]
        return [int(idx[i]) for i in hit]
    def rel32call(self, target_rva, secname='.text'):
        """E8/E9 sites whose target == target_rva."""
        va,vs,rp,rs=self.sections[secname]
        n=rs-5
        seg=self.arr[va:va+rs]
        op=seg[0:n]
        b0=seg[1:n+1].astype(np.int64); b1=seg[2:n+2].astype(np.int64)
        b2=seg[3:n+3].astype(np.int64); b3=seg[4:n+4].astype(np.int64)
        disp=(b0 | (b1<<8) | (b2<<16) | (b3<<24))
        disp=np.where(disp>=0x80000000, disp-0x100000000, disp)
        idx=np.arange(n,dtype=np.int64)+va
        tgt=idx+5+disp
        m=((op==0xE8)|(op==0xE9)) & (tgt==target_rva)
        hit=np.nonzero(m)[0]
        return [(int(idx[i]), 'call' if seg[i]==0xE8 else 'jmp') for i in hit]
    def findq(self, val, secs=None):
        out=[]
        pat=struct.pack('<Q',val)
        for nm,(va,vs,rp,rs) in self.sections.items():
            if secs and nm not in secs: continue
            if nm in ('.reloc','.rsrc'): continue
            st=va
            end=va+rs
            while True:
                i=self.buf.find(pat,st,end)
                if i<0: break
                out.append((nm,i)); st=i+1
        return out

def load(n): return Img(DUMPS.get(n,n))

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('cmd'); ap.add_argument('rva'); ap.add_argument('--dump',default='merged4')
    ap.add_argument('--sec',default='.text')
    a=ap.parse_args()
    img=load(a.dump); r=int(a.rva,0)
    if r>=img.imagebase: r-=img.imagebase
    if a.cmd=='riprel':
        h=img.riprel(r,a.sec); print(f"{len(h)} riprel disp32 fields -> 0x{r:08X}")
        for x in h: print(f"  disp32@0x{x:08X}  insn_end=0x{x+4:08X}")
    elif a.cmd=='call':
        h=img.rel32call(r,a.sec); print(f"{len(h)} rel32 sites -> 0x{r:08X}")
        for x,k in h: print(f"  {k} @0x{x:08X}")
    elif a.cmd=='findq':
        h=img.findq(r+img.imagebase); print(f"{len(h)} qwords == VA 0x{r+img.imagebase:X}")
        for nm,x in h: print(f"  {nm} 0x{x:08X}")
