# Resolve the toggle-readiness D for an object whose vfn188 is the weak-object-ptr resolver (0x7FF6B887C990):
#   P=[obj+0x28]; index=[P+0x10]; B=GUObjectArray[index]; C=[B+0x258]; D=[C+0x5A0]; readiness=byte[D+0xB3] bit6.
#   usage: resolve_obj_d.py <PID> <BASE-hex> <obj-hex> [--poke]   (--poke sets bit6 on D if not-ready)
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); OBJ=int(sys.argv[3],16); POKE="--poke" in sys.argv
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wpm(a,data):
    r=ctypes.c_size_t(0); buf=(ctypes.c_ubyte*len(data))(*data)
    return bool(k32.WriteProcessMemory(h,ctypes.c_void_p(a),buf,len(data),ctypes.byref(r)) and r.value==len(data))
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def i32(a): b=rpm(a,4); return int.from_bytes(b,"little",signed=True) if b else -1
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a): b=rpm(a,8); return u64(b,0) if b else 0
def u8(a): b=rpm(a,1); return b[0] if b else -1
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
def guobj(index):
    op=p(OBJOBJECTS); chunk=p(op+(index>>16)*8)
    if not looksptr(chunk): return 0
    return p(chunk+(index&0xFFFF)*STRIDE)
P=p(OBJ+0x28); print(f"obj=0x{OBJ:X}  P=[obj+0x28]=0x{P:X}")
if not looksptr(P): print("P bad"); sys.exit(1)
idx=i32(P+0x10); print(f"weak index=[P+0x10]={idx}")
B=guobj(idx); print(f"B=GUObjectArray[{idx}]=0x{B:X} name='{oname(B)}' class='{ocls(B)}'")
if not looksptr(B): print("B bad"); sys.exit(1)
C=p(B+0x258); print(f"C=[B+0x258]=0x{C:X}")
if not looksptr(C): print("C bad"); sys.exit(1)
D=p(C+0x5A0); print(f"D=[C+0x5A0]=0x{D:X} name='{oname(D)}' class='{ocls(D)}'")
if not looksptr(D): print("D bad"); sys.exit(1)
b=u8(D+0xB3); print(f"readiness byte[D+0xB3]=0x{b:02X} bit6={(b>>6)&1}")
if POKE and not ((b>>6)&1) and b!=-1:
    ok=wpm(D+0xB3, bytes([b|0x40])); print(f"POKE bit6 -> 0x{b|0x40:02X}  ({'ok' if ok else 'FAIL'})")
