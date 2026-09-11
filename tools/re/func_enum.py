# Enumerate a UClass's UFunctions and flag BP-callable (Script.Num>0) vs native (0).
# usage: func_enum.py <PID> <BASE-hex> <ClassObj-hex>
# Offsets (this build): UClass.Children(UField*)@+0x50, UField.Next@+0x30, Name@+0x20, Class@+0x18,
#                       UStruct.Script(TArray) Data@+0x68 Num@+0x70.  Walks super chain too.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); ROOT=int(sys.argv[3],16); NAMEPOOL=BASE+0x9D81450
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
def oname(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o):
    c=p(o+0x18); return oname(c) if looksptr(c) else "?"
def clsname(cls):
    return oname(cls)
# walk super chain, enumerate each level's Children UFunctions
cls=ROOT; level=0
seen=set()
while looksptr(cls) and level<8:
    print(f"=== [{level}] class {clsname(cls)} @0x{cls:X} ===")
    ch=p(cls+0x50)  # Children (UField*)
    f=ch; i=0
    while looksptr(f) and i<400:
        if f in seen: break
        seen.add(f)
        if ocls(f)=="Function":
            nm=oname(f)
            scriptnum=u32(rpm(f+0x70,4) or b'\0\0\0\0',0)
            kind="BP(bytecode)" if scriptnum>0 else "native"
            print(f"    {nm:44} Script.Num={scriptnum:<5} {kind}")
        nb=rpm(f+0x30,8); f=u64(nb,0) if nb else 0; i+=1
    # super: UStruct.SuperStruct — for a UClass, super @ +0x48? try +0x48 then +0x40
    sup=p(cls+0x48)
    if not looksptr(sup): sup=p(cls+0x40)
    cls=sup; level+=1
