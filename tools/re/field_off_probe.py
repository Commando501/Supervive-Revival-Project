# Find FArrayProperty.Inner and FStructProperty.Struct offsets by dumping raw FField bytes
# and locating known target pointers. usage: field_off_probe.py <PID> <BASE-hex>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); NAMEPOOL=BASE+0x9D81450
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
def fldname(f):
    nb=rpm(f+0x20,4); return fname(u32(nb,0)) if nb else "?"
def fldtype(f):
    fcb=rpm(f+0x08,8); fc=u64(fcb,0) if fcb else 0
    if not looksptr(fc): return "?"
    tnb=rpm(fc+0x00,4); return fname(u32(tnb,0)) if tnb else "?"

MP=0x1F047F4AB60           # FMissionProgress UScriptStruct
child=u64(rpm(MP,0x60),0x58)
# walk to find AssetId (StructProperty) and ObjectiveProgress (ArrayProperty)
f=child; fields=[]
while looksptr(f) and len(fields)<12:
    fields.append((f, fldname(f), fldtype(f)))
    f=u64(rpm(f+0x18,8),0)
for f,nm,tp in fields:
    print(f"field {nm:<20} type={tp:<18} @0x{f:X}")
    if tp in ("StructProperty","ArrayProperty"):
        raw=rpm(f,0x80)
        for off in range(0x28,0x80,8):
            v=u64(raw,off)
            if looksptr(v):
                # what does it point to? a UScriptStruct (name) or an FField (name via +0x20)
                tgtnm=""
                tn=rpm(v+0x20,4)
                if tn:
                    nm2=fname(u32(tn,0))
                    if nm2 and nm2!="?": tgtnm=f" -> name@+0x20={nm2!r}"
                print(f"    +0x{off:02X} = 0x{v:X}{tgtnm}")
