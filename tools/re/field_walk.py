# Walk a UStruct/UScriptStruct's ChildProperties, printing each field's name, type, and
# EPropertyFlags — specifically CPF_RepSkip (0x80000000) which RepLayout EXCLUDES from a
# replicated struct's cmd stream. usage: field_walk.py <PID> <BASE-hex> <StructObjAddr-hex>
# This build: ChildProperties@+0x58, FField.Next@+0x18, Name@+0x20, FFieldClass@+0x08, Flags@+0x38.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); OBJ=int(sys.argv[3],16)
NAMEPOOL=BASE+0x9D81450
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
CPF_Net=0x20; CPF_RepSkip=0x80000000; CPF_RepNotify=0x100000000
hd=rpm(OBJ,0x60)
child=u64(hd,0x58)
print(f"struct @0x{OBJ:X}  ChildProperties head=0x{child:X}")
f=child; i=0
while looksptr(f) and i<40:
    nb=rpm(f+0x20,4); nm=fname(u32(nb,0)) if nb else "?"
    fcb=rpm(f+0x08,8); fc=u64(fcb,0) if fcb else 0
    tnb=rpm(fc+0x00,4) if looksptr(fc) else None
    tn=fname(u32(tnb,0)) if tnb else "?"
    flb=rpm(f+0x38,8); fl=u64(flb,0) if flb else 0
    tags=[]
    if fl&CPF_RepSkip: tags.append("REPSKIP(NotReplicated)")
    if fl&CPF_Net: tags.append("Net")
    if fl&CPF_RepNotify: tags.append("RepNotify")
    print(f"  [{i}] {nm:<24} {tn:<22} flags=0x{fl:016X}  {' '.join(tags)}")
    nb=rpm(f+0x18,8); f=u64(nb,0) if nb else 0; i+=1
