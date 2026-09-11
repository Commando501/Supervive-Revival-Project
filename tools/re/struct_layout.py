# struct_layout.py — dump a UScriptStruct's field layout (name, type, ElementSize@+0x34, Offset_Internal@+0x44),
# recursing one level into nested structs/arrays. Read-only RPM.
# usage: struct_layout.py <PID> <BASE-hex> <StructName> [StructName2 ...]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); WANT=sys.argv[3:] or ["MissionProgress"]
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
    fc=p(f+0x08);
    if not looksptr(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"
def find_struct(name):
    op=p(OBJOBJECTS); numEl=u32(rpm(OBJOBJECTS,0x18) or b"\0"*0x18,0x14)
    nchunks=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nchunks):
        chunk=p(op+ci*8)
        if not looksptr(chunk): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
        for j in range(cnt):
            obj=p(chunk+j*STRIDE)
            if looksptr(obj) and oname(obj)==name and ocls(obj)=="ScriptStruct": return obj
    return 0
def dump(structObj, depth):
    ind="  "*depth
    size=u32(rpm(structObj+0x40,4) or b"\0\0\0\0",0)   # UStruct.PropertiesSize @+0x40
    sf=u32(rpm(structObj+0xB8,4) or b"\0\0\0\0",0)      # StructFlags @+0xB8
    print(f"{ind}struct {oname(structObj)} @0x{structObj:X} size={size} StructFlags=0x{sf:X}")
    f=p(structObj+0x58); i=0
    while looksptr(f) and i<40:
        ty=ftype(f); nm=oname(f); raw=rpm(f,0x60) or b"\0"*0x60
        esz=u32(raw,0x34); off=i32(raw,0x44); fl=u64(raw,0x38)
        extra=""
        if ty=="StructProperty":
            st=p(f+0x70); extra=f" -> {oname(st)}" if looksptr(st) else ""
        elif ty=="ArrayProperty":
            inn=p(f+0x78); extra=f" <inner {ftype(inn)} {(oname(p(inn+0x70)) if ftype(inn)=='StructProperty' else '')}>" if looksptr(inn) else ""
        print(f"{ind}  +0x{off:03X} {ty:20} {nm:26} size={esz}{extra}")
        f=p(f+0x18); i+=1
for w in WANT:
    s=find_struct(w)
    print(f"\n########## {w} ##########")
    if not s: print("  NOT FOUND"); continue
    dump(s,0)
