# Find a UClass (or any UObject) by EXACT object NAME via GUObjectArray.
# Complements obj_iter.py (which matches on CLASS name / finds instances). Use this to
# get a UClass address to feed rep_expand_class.py: the UClass object's own Class is "Class".
# UObject layout (this build): Class@+0x18, Name@+0x20, InternalIndex@+0x10.
#   usage: find_uclass.py <PID> <BASE-hex> <ObjNameExact> [classFilter]
# e.g.:  find_uclass.py 27232 0x7FF6B54F0000 LokiGameState Class
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); WANT=sys.argv[3]
CLSF=sys.argv[4] if len(sys.argv)>4 else None
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
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8); r="?"
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
def clsname(cls):
    cb=rpm(cls+0x20,4); return fname(u32(cb,0)) if cb else "?"
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
print(f"ObjObjects=0x{objectsPtr:X} NumElements={numEl}")
numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8)
hits=[]
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK)
    items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if not looksptr(obj): continue
        nb=rpm(obj+0x20,4)
        if not nb: continue
        nm=fname(u32(nb,0))
        if nm==WANT:
            cb=rpm(obj+0x18,8); cls=int.from_bytes(cb,"little") if cb else 0
            cn=clsname(cls) if looksptr(cls) else "?"
            if CLSF and CLSF!=cn: continue
            hits.append((obj,cn))
print(f"found {len(hits)} object(s) named exactly '{WANT}':")
for obj,cn in hits[:30]:
    print(f"  obj=0x{obj:X}  Class={cn}")
