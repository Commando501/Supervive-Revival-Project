# param_probe.py — for a target UFunction, dump its param FProperties (name, type, ElementSize@+0x34,
# candidate Offset_Internal@+0x44, PropertyFlags@+0x38) and the first bytes of its native thunk
# (UFunction.Func@+0xE0) as hex for manual disasm (to locate FFrame.PropertyChainForCompiledIn).
# Read-only RPM. usage: param_probe.py <PID> <BASE-hex> <ClassName> <FuncName>
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); CLSNAME=sys.argv[3]; FNNAME=sys.argv[4]
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
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
def fftype(f):
    fc=p(f+0x08);
    if not looksptr(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"
def find_class(name):
    op=p(OBJOBJECTS); numEl=u32(rpm(OBJOBJECTS,0x18) or b"\0"*0x18,0x14)
    nchunks=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nchunks):
        chunk=p(op+ci*8)
        if not looksptr(chunk): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
        for j in range(cnt):
            obj=p(chunk+j*STRIDE)
            if looksptr(obj) and oname(obj)==name and "Class" in ocls(obj): return obj
    return 0
cls=find_class(CLSNAME)
print(f"class {CLSNAME} @0x{cls:X}")
# find the function in Children (UField*)@+0x50, Next@+0x30
f=p(cls+0x50); fn=0; i=0
while looksptr(f) and i<600:
    if ocls(f)=="Function" and oname(f)==FNNAME: fn=f; break
    f=p(f+0x30); i+=1
if not fn: print(f"FUNC {FNNAME} NOT FOUND"); sys.exit(1)
snum=u32(rpm(fn+0x70,4) or b"\0\0\0\0",0)
thunk=p(fn+0xE0)
propsize=u32(rpm(fn+0x40,4) or b"\0\0\0\0",0)   # UStruct.PropertiesSize @+0x40 (candidate)
print(f"UFunction {FNNAME} @0x{fn:X}  Script.Num={snum}  thunk=0x{thunk:X}(rva 0x{thunk-BASE:X})  ChildProperties@0x{p(fn+0x58):X}")
print(f"candidate PropertiesSize(@+0x40)={propsize}")
print("params (walk ChildProperties@+0x58, Next@+0x18):")
pf=p(fn+0x58); k=0
while looksptr(pf) and k<40:
    nm=oname(pf); ty=fftype(pf); raw=rpm(pf,0x60) or b"\0"*0x60
    esz=u32(raw,0x34); flags=u64(raw,0x38); off44=i32(raw,0x44)
    tags=[]
    if flags&0x80: tags.append("Parm")
    if flags&0x100: tags.append("Out")
    if flags&0x400: tags.append("Return")
    if flags&0x400000000: tags.append("ConstParm")
    print(f"  [{k}] {ty:20} {nm:28} ElemSize@34={esz:<5} Off@44={off44:<5} flags=0x{flags:X} {' '.join(tags)}")
    pf=p(pf+0x18); k+=1
# thunk bytes for manual disasm
tb=rpm(thunk,0xA0)
if tb:
    print(f"\nthunk bytes @0x{thunk:X} (rva 0x{thunk-BASE:X}):")
    for row in range(0,0xA0,16):
        hexs=" ".join(f"{tb[row+c]:02X}" for c in range(16))
        print(f"  +0x{row:03X}: {hexs}")
