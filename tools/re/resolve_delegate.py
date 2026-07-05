# Resolve a MulticastInlineDelegate's handlers. Given the object + delegate offset, read the invocation
# list (TArray<FScriptDelegate>; FScriptDelegate = {int32 ObjectIndex, int32 Serial, FName Fn(idx,num)} =16B)
# and resolve each handler's object (via GUObjectArray[ObjectIndex]) + class name + function name.
#   usage: resolve_delegate.py <PID> <obj-hex> <delegateOff-hex>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); OBJ=int(sys.argv[2],16); OFF=int(sys.argv[3],16)
BASE=0x7FF682A80000; NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    hd=rpm(bp+off,2)
    if not hd: return "?"
    hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
def objAt(idx):  # GUObjectArray[idx].Object
    oo=rpm(OBJOBJECTS,0x18); objects=u64(oo,0)
    cp=rpm(objects+(idx//PERCHUNK)*8,8)
    if not cp: return 0
    chunk=int.from_bytes(cp,"little")
    it=rpm(chunk+(idx%PERCHUNK)*STRIDE,8)
    return int.from_bytes(it,"little") if it else 0

d=rpm(OBJ+OFF,0x10)
data=u64(d,0); num=u32(d,8)
print(f"delegate @obj+0x{OFF:X}: Data=0x{data:X} Num={num}")
arr=rpm(data, num*16)
for i in range(num):
    oi=u32(arr,i*16); ser=u32(arr,i*16+4); fn=u32(arr,i*16+8)
    obj=objAt(oi)
    cn="?"; nm="?"
    if looksptr(obj):
        cb=rpm(obj+0x18,8); cls=int.from_bytes(cb,"little") if cb else 0
        if looksptr(cls):
            ccb=rpm(cls+0x20,4); cn=fname(int.from_bytes(ccb,"little")) if ccb else "?"
        nb=rpm(obj+0x20,4); nm=fname(int.from_bytes(nb,"little")) if nb else "?"
    print(f"  [{i}] ObjIndex={oi} obj=0x{obj:X} Class={cn} Name={nm}  Fn={fname(fn)}")
