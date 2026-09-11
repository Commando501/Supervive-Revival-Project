# Dump world locations of live actors whose class name contains a substring. Read-only RPM.
#   usage: actor_locs.py <PID> <BASE-hex> <ClassNameSubstr> [maxN]
# Offsets (this build): Actor RootComponent@+0x1B0; SceneComponent RelativeLocation(FVector dbl)@+0x158; Class@+0x18 Name@+0x20.
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); WANT=sys.argv[3]; MAXN=int(sys.argv[4]) if len(sys.argv)>4 else 60
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
def dbl(a): b=rpm(a,8); return struct.unpack("<d",b)[0] if b else None
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
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14); numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8); found=0
print(f"{'obj':>14} {'X':>9} {'Y':>9} {'Z':>9}  class / name")
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o=u64(items,j*STRIDE)
        if not looksptr(o): continue
        cn=ocls(o)
        if WANT not in cn: continue
        nm=oname(o)
        if nm.startswith("Default__"): continue
        root=p(o+0x1B0)
        x=y=z=None
        if looksptr(root): x=dbl(root+0x158); y=dbl(root+0x158+8); z=dbl(root+0x158+16)
        xs=f"{x:.0f}" if x is not None else "-"; ys=f"{y:.0f}" if y is not None else "-"; zs=f"{z:.1f}" if z is not None else "-"
        print(f"0x{o:012X} {xs:>9} {ys:>9} {zs:>9}  {cn} / {nm}")
        found+=1
        if found>=MAXN: break
    if found>=MAXN: break
print(f"\n{found} live actor(s) of class containing '{WANT}'")
