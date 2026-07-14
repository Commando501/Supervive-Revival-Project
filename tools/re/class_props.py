# List a UCLASS's FProperties (name, type, Offset_Internal, flags) across its SUPER chain.
# Complements class_funcs.py (which lists UFunctions). Use to find a member offset by name.
#   usage: class_props.py <PID> <BASE-hex> <ClassName> [nameSubstrFilter]
# Offsets (this build): UObject Class@+0x18 Name@+0x20; UStruct SuperStruct@+0x48 ChildProperties@+0x58;
#   FField Next@+0x18 Class(FFieldClass*)@+0x08 Name@+0x20; FProperty ElementSize@+0x34 Flags@+0x38 Offset@+0x44.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CLSNAME=sys.argv[3]
FILT=sys.argv[4].lower() if len(sys.argv)>4 else None
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(b,o): return int.from_bytes(b[o:o+4],"little",signed=True)
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
def ftype(f):
    fc=p(f+0x08)
    if not looksptr(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"
# find the UClass object named CLSNAME (own Class == "Class")
hdr=rpm(OBJOBJECTS,0x18)
if not hdr: print("bad OBJOBJECTS/base"); sys.exit(1)
objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14); numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8); root=0
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if not looksptr(obj): continue
        if oname(obj)==CLSNAME and ocls(obj)=="Class": root=obj; break
    if root: break
if not root: print(f"UClass '{CLSNAME}' not found (map not loaded yet?)"); sys.exit(1)
print(f"UClass {CLSNAME} @0x{root:X}")
cls=root; level=0
while looksptr(cls) and level<12:
    cn=oname(cls); props=[]
    f=p(cls+0x58); i=0
    while looksptr(f) and i<600:
        ty=ftype(f); nm=oname(f); raw=rpm(f,0x60) or b"\0"*0x60
        esz=u32(raw,0x34); off=i32(raw,0x44); fl=u64(raw,0x38)
        if FILT is None or FILT in nm.lower(): props.append((off,ty,nm,esz,fl))
        f=p(f+0x18); i+=1
    print(f"\n=== [{level}] {cn}  ({len(props)} prop{'s' if FILT is None else ' matching \"'+FILT+'\"'}) ===")
    for off,ty,nm,esz,fl in sorted(props,key=lambda x:x[0]):
        print(f"   +0x{off:04X} {ty:20} {nm:40} size={esz} flags=0x{fl:016X}")
    cls=p(cls+0x48); level+=1
