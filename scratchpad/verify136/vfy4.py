import ctypes,time
from ctypes import wintypes
PID=43456; BASE=0x7FF608F40000
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def f32(b,o):
    import struct; return struct.unpack_from("<f",b,o)[0]
def f64(b,o):
    import struct; return struct.unpack_from("<d",b,o)[0]
def ptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(i):
    if i in _nc: return _nc[i]
    blk=i>>16; off=(i&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if ptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; w=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if w else 1))
                    if s: r=("".join(chr(s[k*2]|(s[k*2+1]<<8)) for k in range(ln)) if w else s.decode("latin1","replace"))
    _nc[i]=r; return r
def nmOf(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def numOf(o):
    b=rpm(o+0x24,4); return u32(b,0) if b else -1
A1=0x1B3F58BC5E0; A2=0x1B3F75EAEA0; PAWN=0x1B3E6922AE0
for lbl,o in (("AIC#1 (the session's)",A1),("AIC#2 (NEW, appeared during my review)",A2)):
    print(f"\n=== {lbl}  0x{o:X} ===")
    hb=rpm(o,0x30)
    print(f"  ObjectFlags@0x0C=0x{u32(hb,0x0C):08X}  InternalIndex={u32(hb,0x10)}  FName.Number={numOf(o)}")
    for off,l in ((0x3F8,"Pawn"),(0x408,"Character"),(0x198,"Instigator"),(0x150,"Owner"),(0x3C0,"PlayerState"),(0x490,"PathFollowingComponent"),(0x4A8,"ActionsComp"),(0x1B0,"RootComponent")):
        v=u64(rpm(o+off,8),0)
        print(f"    +0x{off:04X} {l:24s} = 0x{v:X}"+(f"  -> {nmOf(v)}" if ptr(v) else ""))
print("\n=== the spawned PAWN, re-read NOW ===")
for off,l in ((0x400,"Controller"),(0x408,"PreviousController"),(0x150,"Owner"),(0x1B0,"RootComponent")):
    v=u64(rpm(PAWN+off,8),0); print(f"    +0x{off:04X} {l:22s} = 0x{v:X}"+(f"  -> {nmOf(v)}" if ptr(v) else ""))
root=u64(rpm(PAWN+0x1B0,8),0)
if ptr(root):
    b=rpm(root+0x158,24); print(f"    location = ({f64(b,0):.4f}, {f64(b,8):.4f}, {f64(b,16):.4f})")
