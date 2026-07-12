# S73: generate the C++ UFUNCTION declarations + empty _Implementation bodies for the mirror's
# ALokiPlayerController, matching the live client's LokiPlayerController own net functions (names +
# direction + reliability) so the stub's NetFields index space aligns with the client's.
#   usage: gen_lokipc_rpcs.py <PID> <BASE-hex>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
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
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    b2=rpm(bp+off,2)
    if not b2: return "?"
    hd=int.from_bytes(b2,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
def oname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o): c=p(o+0x18); return oname(c) if looksptr(c) else "?"
# resolve LokiPlayerController UClass by name
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
numChunks=(numEl+PERCHUNK-1)//PERCHUNK; chunkPtrs=rpm(objectsPtr,numChunks*8)
ROOT=0
for ci in range(numChunks):
    chunk=int.from_bytes(chunkPtrs[ci*8:ci*8+8],"little")
    if not looksptr(chunk): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(chunk,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        obj=u64(items,j*STRIDE)
        if not looksptr(obj): continue
        nb=rpm(obj+0x20,4)
        if nb and fname(u32(nb,0))=="LokiPlayerController" and ocls(obj)=="Class":
            ROOT=obj; break
    if ROOT: break
assert ROOT, "LokiPlayerController class not found"
FUNC_Net=0x40; FUNC_NetReliable=0x80; FUNC_NetMulticast=0x4000; FUNC_NetServer=0x200000; FUNC_NetClient=0x1000000
ch=p(ROOT+0x50); f=ch; i=0; fns=[]
while looksptr(f) and i<600:
    if ocls(f)=="Function":
        fl=u32(rpm(f+0xB8,4) or b'\0\0\0\0',0)
        if (fl & FUNC_Net) and not looksptr(p(f+0x48)):   # own (non-override) net fn
            nm=oname(f)
            if fl & FUNC_NetServer: d="Server"
            elif fl & FUNC_NetClient: d="Client"
            elif fl & FUNC_NetMulticast: d="NetMulticast"
            else: d="Client"
            rel="Reliable" if (fl & FUNC_NetReliable) else "Unreliable"
            fns.append((nm,d,rel))
    nb=rpm(f+0x30,8); f=u64(nb,0) if nb else 0; i+=1
fns.sort(key=lambda x:x[0].lower())
print(f"// {len(fns)} own net functions on LokiPlayerController (captured live S73)")
print("// ===== HEADER: UFUNCTION declarations (paste into ALokiPlayerController public:) =====")
for nm,d,rel in fns:
    print(f"\tUFUNCTION({d}, {rel}) void {nm}();")
print("// ===== CPP: empty _Implementation bodies (paste into LokiPlayerControllerStub.cpp) =====")
for nm,d,rel in fns:
    print(f"void ALokiPlayerController::{nm}_Implementation() {{}}")
