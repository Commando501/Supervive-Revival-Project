# objmodel_dump.py — dump the MissionObjectiveModel class field layout AND a set of live instances,
# annotating int/float fields so we can find the progress-bar current(=10?)/max(=20?) fields.
# Read-only RPM. usage: objmodel_dump.py <PID> <BASE-hex> <instPtrHex> [instPtrHex...]
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); INSTS=[int(x,16) for x in sys.argv[3:]]
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
def f32(b,o): return struct.unpack_from("<f",b,o)[0]
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
    fc=p(f+0x08)
    if not looksptr(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"
def find_class(name):
    op=p(OBJOBJECTS); hdr=rpm(OBJOBJECTS,0x18); numEl=u32(hdr,0x14)
    nchunks=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nchunks):
        chunk=p(op+ci*8)
        if not looksptr(chunk): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
        for j in range(cnt):
            obj=p(chunk+j*STRIDE)
            if looksptr(obj) and oname(obj)==name and "Class" in ocls(obj): return obj
    return 0

cls=find_class("MissionObjectiveModel")
print(f"MissionObjectiveModel class @0x{cls:X}  size={u32(rpm(cls+0x40,4) or b'0'*4,0)}")
print("fields (ChildProperties @+0x58, Next @+0x18):")
fields=[]
f=p(cls+0x58); i=0
while looksptr(f) and i<60:
    ty=ftype(f); nm=oname(f); raw=rpm(f,0x60) or b"\0"*0x60
    esz=u32(raw,0x34); off=i32(raw,0x44); fl=u64(raw,0x38)
    extra=""
    if ty=="StructProperty":
        st=p(f+0x70); extra=f" -> {oname(st)}"
    elif ty=="ObjectProperty":
        pc=p(f+0x70); extra=f" -> {oname(pc)}"
    fields.append((off,ty,nm,esz))
    print(f"  +0x{off:03X} {ty:20} {nm:30} size={esz}{extra}")
    f=p(f+0x18); i+=1

for inst in INSTS:
    print(f"\n=== instance @0x{inst:X} class={ocls(inst)} ===")
    raw=rpm(inst,0x100)
    if not raw: print("  unreadable"); continue
    # decode declared fields
    for off,ty,nm,esz in fields:
        if off<0 or off+8>len(raw): continue
        if ty in ("IntProperty","Int32Property"): val=f"int={i32(raw,off)}"
        elif ty in ("FloatProperty",): val=f"float={f32(raw,off):.3f}"
        elif ty in ("DoubleProperty",): val=f"double={struct.unpack_from('<d',raw,off)[0]:.3f}"
        elif ty in ("BoolProperty",): val=f"bool={raw[off]&1}"
        elif ty in ("NameProperty",): val=f"FName '{fname(u32(raw,off))}'"
        elif ty in ("ObjectProperty",): pv=u64(raw,off); val=f"ptr 0x{pv:X} ({ocls(pv) if looksptr(pv) else '-'})"
        elif ty in ("StrProperty",):
            dp=u64(raw,off); dn=u32(raw,off+8); s=""
            if looksptr(dp) and 0<dn<128:
                sb=rpm(dp,dn*2); s=sb.decode("utf-16-le","replace").rstrip("\x00") if sb else ""
            val=f"str '{s}'"
        else: val=f"u32={u32(raw,off)} u64=0x{u64(raw,off):X}"
        print(f"  +0x{off:03X} {ty:18} {nm:28} = {val}")
    # raw scan for ints/floats == 10 or 20 (the bar values)
    print("  -- raw scan for 10/20 (int & float) --")
    for o in range(0, len(raw)-4, 4):
        iv=i32(raw,o); fv=f32(raw,o)
        if iv in (10,20,1,5,3,42): print(f"    +0x{o:03X}: int={iv}")
        if abs(fv-10.0)<0.001 or abs(fv-20.0)<0.001 or abs(fv-42.0)<0.001 or abs(fv-1.0)<0.001 or abs(fv-5.0)<0.001: print(f"    +0x{o:03X}: float={fv:.3f}")
