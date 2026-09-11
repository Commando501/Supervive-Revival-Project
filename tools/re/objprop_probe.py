# Find the Missions array's Inner ObjectProperty and its PropertyClass. usage: <PID> <BASE> <ClassObj>
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
    hd=rpm(bp+off,2)
    if not hd: return "?"
    hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
def fldname(f): b=rpm(f+0x20,4); return fname(u32(b,0)) if b else "?"
def fldtype(f):
    fc=p(f+0x08); b=rpm(fc+0,4) if looksptr(fc) else None
    return fname(u32(b,0)) if b else "?"
def objname(o): b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
# class ChildProperties head; find Missions (field 0)
c=p(ROOT+0x58); i=0
while looksptr(c) and i<10:
    nm=fldname(c)
    if nm=="Missions":
        print(f"Missions ArrayProperty @0x{c:X}  type={fldtype(c)}")
        inner=p(c+0x78)
        print(f"  Inner @0x{inner:X}  name={fldname(inner)} type={fldtype(inner)}")
        # dump inner raw 0x28..0x90 to find PropertyClass (a UClass ptr)
        raw=rpm(inner,0x90)
        for off in range(0x28,0x90,8):
            v=u64(raw,off)
            if looksptr(v):
                nn=objname(v)
                extra=f" -> UObject name={nn!r}" if nn and nn!="?" else ""
                print(f"    inner+0x{off:02X} = 0x{v:X}{extra}")
        break
    c=p(c+0x18); i+=1
