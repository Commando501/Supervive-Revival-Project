# probe_comp.py — inspect an added SkeletalMeshComponent's render/attach state. Read-only RPM.
#   usage: probe_comp.py <PID> <BASE-hex> <compHex> [heroHex]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); COMP=int(sys.argv[3],16)
HERO=int(sys.argv[4],16) if len(sys.argv)>4 else 0
NP=BASE+0x9D81450
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
def clsof(o):
    b=rd(o+0x18,8); return u64(b,0) if b else 0
def cname(o):
    c=clsof(o)
    if not looks(c): return "?"
    nb=rd(c+0x20,4)
    return fn(u32(nb,0)) if nb else "?"
def findprop(cls,want):
    d=0
    while looks(cls) and d<20:
        f=u64(rd(cls+0x58,8) or b"\0"*8,0); n=0
        while looks(f) and n<1200:
            nb=rd(f+0x20,4)
            if nb and fn(u32(nb,0))==want:
                ob=rd(f+0x44,4); return u32(ob,0) if ob else None
            f=u64(rd(f+0x18,8) or b"\0"*8,0); n+=1
        cls=u64(rd(cls+0x48,8) or b"\0"*8,0); d+=1
    return None
def gp(o,name):
    off=findprop(clsof(o),name)
    if off is None: return None,None
    return u64(rd(o+off,8) or b"\0"*8,0),off
def gbyte(o,name):
    off=findprop(clsof(o),name)
    if off is None: return None,None
    return (rd(o+off,1) or b"\0")[0],off
def gvec(o,name):
    off=findprop(clsof(o),name)
    if off is None: return None,None
    b=rd(o+off,24)
    if not b: return None,off
    import struct
    return struct.unpack("<ddd",b),off
print("COMP 0x%X (%s)"%(COMP,cname(COMP)))
for f in ("SkeletalMeshAsset","SkeletalMesh"):
    v,o=gp(COMP,f)
    if o is not None: print("  %s @0x%X = 0x%X (%s)"%(f,o,v or 0,cname(v) if v and looks(v) else "-- NONE --"))
for f in ("AttachParent",):
    v,o=gp(COMP,f)
    if o is not None: print("  %s @0x%X = 0x%X (%s)%s"%(f,o,v or 0,cname(v) if v and looks(v) else "-",("  == HERO-root? " if v and HERO else "")))
rl,o=gvec(COMP,"RelativeLocation")
if o is not None: print("  RelativeLocation @0x%X = %s"%(o,rl))
# component world location often at CompToWorld/ComponentToWorld translation; try common bitfield bytes
for f in ("bVisible","bHiddenInGame","bHidden","bAutoActivate","Visibility"):
    v,o=gbyte(COMP,f)
    if o is not None: print("  %s @0x%X = %d"%(f,o,v))
# raw scan: read a window of the component to eyeball flags near the SceneComponent bitfield block
if HERO:
    print("HERO 0x%X (%s)"%(HERO,cname(HERO)))
    rc,o=gp(HERO,"RootComponent")
    if o is not None: print("  RootComponent @0x%X = 0x%X (%s)"%(o,rc or 0,cname(rc) if rc and looks(rc) else "-"))
