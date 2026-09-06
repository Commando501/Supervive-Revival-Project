import sys, struct, numpy as np
sys.path.insert(0, r"G:\git\Supervive Revival Project\scratchpad\fk27")
import fkdis
img=fkdis.Img(r"G:\git\Supervive Revival Project\dumps\merged4.dump.exe")
IB=img.imagebase; b=img.buf
nm,va,vs,rp,rs=[s for s in img.sections if s[0]=='.text'][0]
arr=np.frombuffer(b[rp:rp+rs], dtype=np.uint8)
# disp32 at every offset
d32=np.frombuffer(b[rp:rp+rs-3], dtype=np.uint8)  # placeholder
raw=np.frombuffer(b[rp:rp+rs], dtype=np.uint8)
n=len(raw)-4
disp=(raw[0:n].astype(np.int64) | (raw[1:n+1].astype(np.int64)<<8) | (raw[2:n+2].astype(np.int64)<<16) | (raw[3:n+3].astype(np.int64)<<24))
disp=disp.astype(np.int32).astype(np.int64)
idx=np.arange(n, dtype=np.int64)
tgt = va + idx + 4 + disp
def wstr(r,maxn=300):
    o=[];j=r
    while True:
        c=b[j]|(b[j+1]<<8)
        if c==0 or len(o)>maxn: break
        o.append(chr(c)); j+=2
    return "".join(o)
def astr(r,maxn=200):
    o=[]
    for c in b[r:r+maxn]:
        if c==0: break
        if c<32 or c>126: return None
        o.append(chr(c))
    return "".join(o)
def ptr_slots(rva):
    pat=struct.pack("<Q", IB+rva); out=[]
    for name,v,vsz,rpp,rss in img.sections:
        if name in ('.reloc','.rsrc'): continue
        blob=b[rpp:rpp+rss]; st=0
        while True:
            i=blob.find(pat,st)
            if i<0: break
            out.append((name,v+i)); st=i+1
    return out
def xref(rva):
    hits=np.nonzero(tgt==rva)[0]
    out=[]
    for i in hits:
        site=va+int(i)
        # a lea rXX,[rip+d] is 48 8d XX disp32 -> disp starts at site, insn starts site-3
        if b[site-3]==0x48 and b[site-2]==0x8d:
            out.append(("lea", site-3))
        elif b[site-3]==0x4c and b[site-2]==0x8d:
            out.append(("lea(r8+)", site-3))
        else:
            out.append(("?", site))
    return out
for s in (0x08B20D40,0x08B20490,0x08B20590,0x08B33CC0,0x08B1CF30,0x08B1CE50):
    print(f'=== W"{wstr(s)[:110]}" @0x{s:08X}')
    for name,slot in ptr_slots(s):
        extra=""
        if name=='.rdata':
            f=struct.unpack_from("<Q",b,slot+8)[0]
            ln=struct.unpack_from("<I",b,slot+0x10)[0]
            vb=struct.unpack_from("<I",b,slot+0x14)[0]
            fn=astr(f-IB) if IB<=f<IB+len(b) else None
            if fn and fn.endswith(('.cpp','.h')):
                extra=f"  RECORD file={fn.split('\\')[-1]} line={ln} verb={vb}"
        print(f"   slot {name} 0x{slot:08X}{extra}")
        if extra:
            for kind,site in xref(slot):
                print(f"        {kind} @ .text 0x{site:07X}")
    print()
