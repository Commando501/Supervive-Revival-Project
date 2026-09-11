# List ALL UFunctions of a UCLASS across its SUPER chain (not just net fns, unlike netfields_dump.py).
# Use to find a phase-advance / round-control function on the native LokiRoundGameMode chain.
#   usage: class_funcs.py <PID> <BASE-hex> <ClassName> [nameSubstrFilter]
# e.g.:  class_funcs.py 57360 0x7FF6B54F0000 LokiRoundGameMode Phase
# Offsets (this build): UObject Class@+0x18 Name@+0x20; UStruct SuperStruct@+0x48 Children(UField*)@+0x50;
#                       UField.Next@+0x30; UFunction.FunctionFlags@+0xB8; Func(native thunk)@+0xE0.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CLSNAME=sys.argv[3]
FILT=sys.argv[4].lower() if len(sys.argv)>4 else None
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
def p(a): b=rpm(a,8); return u64(b,0) if b else 0
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
def oname(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o):
    c=p(o+0x18); return oname(c) if looksptr(c) else "?"

# find the UClass object named CLSNAME (its own Class == "Class")
hdr=rpm(OBJOBJECTS,0x18)
if not hdr: print("bad OBJOBJECTS/base"); sys.exit(1)
objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
numChunks=(numEl+PERCHUNK-1)//PERCHUNK
chunkPtrs=rpm(objectsPtr,numChunks*8)
root=0
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK)
    items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if not looksptr(obj): continue
        if oname(obj)==CLSNAME and ocls(obj)=="Class":
            root=obj; break
    if root: break
if not root: print(f"UClass '{CLSNAME}' not found (map not loaded yet?)"); sys.exit(1)
print(f"UClass {CLSNAME} @0x{root:X}")

FUNC_Native=0x400; FUNC_Net=0x40; FUNC_BlueprintCallable=0x04000000; FUNC_Event=0x00040000
def flagstr(fl):
    d=[]
    if fl&FUNC_Native: d.append("Native")
    if fl&FUNC_Net: d.append("Net")
    if fl&FUNC_BlueprintCallable: d.append("BPCallable")
    if fl&FUNC_Event: d.append("Event")
    return ",".join(d)

# walk super chain, list UFunction children per level
cls=root; level=0
while looksptr(cls) and level<12:
    cn=oname(cls)
    funcs=[]
    ch=p(cls+0x50); f=ch; i=0
    while looksptr(f) and i<800:
        if ocls(f)=="Function":
            nm=oname(f); fl=u32(rpm(f+0xB8,4) or b'\0\0\0\0',0); thunk=p(f+0xE0)
            if FILT is None or FILT in nm.lower():
                funcs.append((nm,fl,f,thunk))
        nb=rpm(f+0x30,8); f=u64(nb,0) if nb else 0; i+=1
    print(f"\n=== [{level}] {cn}  ({len(funcs)} UFunction{'s' if FILT is None else ' matching \"'+FILT+'\"'}) ===")
    for nm,fl,addr,thunk in sorted(funcs,key=lambda x:x[0].lower()):
        print(f"   {nm:46} flags=0x{fl:08X} [{flagstr(fl)}]  ufunc=0x{addr:X} thunk=0x{thunk:X}")
    cls=p(cls+0x48); level+=1
