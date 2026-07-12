# S73: dump a UCLASS's OWN net functions (the NetFields set that FClassNetCache indexes) so the
# stub's LokiPlayerController mirror can reproduce the client's RPC index space.
# SetUpRuntimeReplicationData adds functions with (FunctionFlags & FUNC_Net) && !GetSuperFunction(),
# then name-sorts them (FNameLexicalLess). We reproduce that: own Children UFunctions, FUNC_Net set,
# SuperStruct(@+0x48) null (not an override), sorted by name (case-insensitive lexical).
#   usage: netfields_dump.py <PID> <BASE-hex> <ClassObj-hex>
# Offsets (this build): UClass.Children(UField*)@+0x50, UField.Next@+0x30, Name@+0x20, Class@+0x18,
#                       UStruct.SuperStruct@+0x48, UFunction.FunctionFlags@+0xB0.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); ROOT=int(sys.argv[3],16); NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
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
def oname(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o):
    c=p(o+0x18); return oname(c) if looksptr(c) else "?"

FUNC_Net=0x40; FUNC_NetReliable=0x80; FUNC_Native=0x400
FUNC_NetResponse=0x1000; FUNC_NetMulticast=0x4000; FUNC_NetServer=0x200000; FUNC_NetClient=0x1000000

def netdir(fl):
    d=[]
    if fl&FUNC_NetServer: d.append("Server")
    if fl&FUNC_NetClient: d.append("Client")
    if fl&FUNC_NetMulticast: d.append("Multicast")
    if fl&FUNC_NetReliable: d.append("Reliable")
    if fl&FUNC_Native: d.append("Native")
    return ",".join(d) if d else "?"

print(f"=== class {oname(ROOT)} @0x{ROOT:X} — OWN net functions (FUNC_Net, non-override) ===")
ch=p(ROOT+0x50); f=ch; i=0; nets=[]
while looksptr(f) and i<600:
    if ocls(f)=="Function":
        fl=u32(rpm(f+0xB8,4) or b'\0\0\0\0',0)
        if fl & FUNC_Net:
            sup=p(f+0x48)           # SuperStruct: non-null => override of a base net fn (excluded from this level)
            override = looksptr(sup)
            nets.append((oname(f), fl, override, f))
    nb=rpm(f+0x30,8); f=u64(nb,0) if nb else 0; i+=1
# NetFields = FUNC_Net + NOT override, name-sorted (case-insensitive lexical)
own=[x for x in nets if not x[2]]
own.sort(key=lambda x: x[0].lower())
print(f"  own net functions (in NetFields, name-sorted): {len(own)}")
for idx,(nm,fl,ov,addr) in enumerate(own):
    print(f"   [{idx:3}] {nm:44} flags=0x{fl:08X}  [{netdir(fl)}]")
ovr=[x for x in nets if x[2]]
if ovr:
    print(f"  (overrides of base net fns, NOT in this level's NetFields): {len(ovr)}")
    for nm,fl,ov,addr in sorted(ovr,key=lambda x:x[0].lower()):
        print(f"        {nm:44} flags=0x{fl:08X}  [{netdir(fl)}]")
