# find_func.py — scan GUObjectArray for UFunction objects whose name contains any given substring;
# print name, outer (owning class), and BP/native (Script.Num@+0x70). Read-only RPM.
# usage: find_func.py <PID> <BASE-hex> <substr> [substr2 ...]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); SUBS=[s.lower() for s in sys.argv[3:]] or ["scan","registerprimary","primaryasset","mission"]
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a): b=rpm(a,8); return u64(b,0) if b else 0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if wide else 1))
                    if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace"))
    _nc[idx]=r; return r
def oname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o): c=p(o+0x18); return oname(c) if looksptr(c) else "?"
def outer(o): return p(o+0x28)
op=p(OBJOBJECTS); numEl=u32(rpm(OBJOBJECTS,0x18) or b"\0"*0x18,0x14)
nchunks=(numEl+PERCHUNK-1)//PERCHUNK
seen=set()
for ci in range(nchunks):
    chunk=p(op+ci*8)
    if not looksptr(chunk): continue
    cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
    items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if not looksptr(obj): continue
        if ocls(obj)!="Function": continue
        nm=oname(obj); low=nm.lower()
        if any(s in low for s in SUBS):
            ou=outer(obj); ocn=oname(ou) if looksptr(ou) else "?"
            snum=u32(rpm(obj+0x70,4) or b"\0\0\0\0",0)
            key=(ocn,nm)
            if key in seen: continue
            seen.add(key)
            print(f"{('BP' if snum>0 else 'native'):7} {ocn:34}::{nm}")
print(f"[{len(seen)} matches]")
