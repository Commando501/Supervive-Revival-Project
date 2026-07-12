# List UObject instances whose CLASS name contains a substring, via GUObjectArray.
#   usage: obj_by_class.py <PID> <BASE-hex> <ClassNameSubstr>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); WANT=sys.argv[3]
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
_cn={}
def clsname(cls):
    if cls in _cn: return _cn[cls]
    cb=rpm(cls+0x20,4); r=fname(u32(cb,0)) if cb else "?"; _cn[cls]=r; return r
hdr=rpm(OBJOBJECTS,0x18)
if not hdr: print("failed to read OBJOBJECTS (bad base?)"); sys.exit(1)
objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
print(f"NumElements={numEl}")
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
        cb=rpm(obj+0x18,8)
        if not cb: continue
        cls=int.from_bytes(cb,"little")
        if not looksptr(cls): continue
        cn=clsname(cls)
        if WANT.lower() in cn.lower():
            nb=rpm(obj+0x20,4); nm=fname(u32(nb,0)) if nb else "?"
            if nm.startswith("Default__"): continue   # skip CDOs — LIVE instances only
            hits.append((obj,cn,nm))
print(f"found {len(hits)} LIVE (non-CDO) instance(s) whose class contains '{WANT}':")
for obj,cn,nm in hits[:60]:
    print(f"  obj=0x{obj:X}  Class={cn}  Name={nm}")
