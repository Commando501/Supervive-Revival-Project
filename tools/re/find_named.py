# find_named.py — find live UObjects whose OWN FName matches any of the given substrings (e.g. UFunctions).
#   usage: find_named.py <PID> <BASE-hex> <substr> [substr...]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); SUBS=[s.lower() for s in sys.argv[3:]]
OBJ=BASE+0x9E38930; NP=BASE+0x9D81450; PERCHUNK=65536; STRIDE=0x18
k=ctypes.WinDLL("kernel32",use_last_error=True); k.OpenProcess.restype=wintypes.HANDLE
h=k.OpenProcess(0x1F0FFF,False,PID)
def rd(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looks(v): return 0x10000<=v<0x1000000000000
def fn(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rd(NP+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looks(bp): return "?"
    b2=rd(bp+off,2)
    if not b2: return "?"
    hd=int.from_bytes(b2,"little"); ln=hd>>6; w=hd&1
    if ln<=0 or ln>200: return "?"
    s=rd(bp+off+2,ln*(2 if w else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if w else s.decode("latin1","replace")
def cname(o):
    c=u64(rd(o+0x18,8) or b"\0"*8,0); return fn(u32(rd(c+0x20,4) or b"\0"*4,0)) if looks(c) else "?"
op=u64(rd(OBJ,8),0); num=u32(rd(OBJ+0x14,4),0); nchunks=(num+PERCHUNK-1)//PERCHUNK
seen=set(); hits=0
for ci in range(nchunks):
    chunk=u64(rd(op+ci*8,8) or b"\0"*8,0)
    if not looks(chunk): continue
    cnt=(num-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
    for j in range(cnt):
        o=u64(rd(chunk+j*STRIDE,8) or b"\0"*8,0)
        if not looks(o): continue
        nm=fn(u32(rd(o+0x20,4) or b"\0"*4,0))
        low=nm.lower()
        for s in SUBS:
            if s in low and nm not in seen:
                seen.add(nm); print("0x%X  %-40s class=%s"%(o,nm,cname(o))); hits+=1
                break
        if hits>60: sys.exit()
