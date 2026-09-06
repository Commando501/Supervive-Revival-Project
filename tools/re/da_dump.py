# da_dump.py — given a MissionModel ptr, follow MissionAsset(@0xE0) and BaseMission(@0x108), dump their
# class + fields, and drill into any Objectives array to find LokiMissionObjective definitions
# (UniqueName + target/max). Read-only RPM.
# usage: da_dump.py <PID> <BASE-hex> <MissionModelPtrHex>
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); MDL=int(sys.argv[3],16)
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

def get_class(o): return p(o+0x18)
def superclass(c): return p(c+0x40+0x00)  # UStruct.SuperStruct @+0x40? we'll walk via +0x40

def class_fields(cls):
    # walk this class AND super classes' ChildProperties
    out=[]
    seen=0
    c=cls
    while looksptr(c) and seen<12:
        f=p(c+0x58); i=0
        while looksptr(f) and i<80:
            out.append((c,f)); f=p(f+0x18); i+=1
        c=p(c+0x40)  # UStruct.SuperStruct @+0x40 (Class layout: SuperStruct at +0x40)
        seen+=1
    return out

def dump_obj(o, label, depth=0, maxdepth=2):
    ind="  "*depth
    cls=get_class(o)
    print(f"{ind}{label}: @0x{o:X} class={oname(cls)}")
    if not looksptr(cls): return
    raw=rpm(o,0x400) or b""
    fseen=set()
    # walk the whole class chain (SuperStruct @+0x48), dumping each level's ChildProperties @+0x58
    clist=[]; c=cls
    for _ in range(12):
        clist.append(c); nxt=p(c+0x48)
        if not looksptr(nxt) or nxt==c: break
        c=nxt
    for c in clist:
      print(f"{ind}  [class {oname(c)}]")
      f=p(c+0x58); i=0
      while looksptr(f) and i<80:
        ty=ftype(f); nm=oname(f); fr=rpm(f,0x80) or b"\0"*0x80
        off=i32(fr,0x44); esz=u32(fr,0x34)
        if nm in fseen: f=p(f+0x18); i+=1; continue
        fseen.add(nm)
        if off<0 or off+8>len(raw): f=p(f+0x18); i+=1; continue
        val=""
        if ty=="FloatProperty": val=f"float={f32(raw,off):.3f}"
        elif ty in ("IntProperty","Int32Property"): val=f"int={i32(raw,off)}"
        elif ty=="BoolProperty": val=f"bool={raw[off]&1}"
        elif ty=="NameProperty": val=f"FName '{fname(u32(raw,off))}'"
        elif ty=="StrProperty":
            dp=u64(raw,off); dn=u32(raw,off+8); s=""
            if looksptr(dp) and 0<dn<200:
                sb=rpm(dp,dn*2); s=sb.decode("utf-16-le","replace").rstrip("\x00") if sb else ""
            val=f"str '{s}'"
        elif ty=="TextProperty": val="<text>"
        elif ty=="ObjectProperty":
            pv=u64(raw,off); val=f"ptr 0x{pv:X} ({ocls(pv) if looksptr(pv) else '-'})"
        elif ty=="StructProperty":
            st=p(f+0x70); val=f"<struct {oname(st)}>"
        elif ty=="ArrayProperty":
            dp=u64(raw,off); dn=u32(raw,off+8); inn=p(f+0x78); it=ftype(inn)
            innerdet=it
            if it=="StructProperty": innerdet=f"struct {oname(p(inn+0x70))}"
            elif it=="ObjectProperty": innerdet=f"obj {oname(p(inn+0x70))}"
            val=f"array[{dn}] Data=0x{dp:X} <inner {innerdet}> innerSize={u32(rpm(inn,0x38) or b'0'*0x38,0x34)}"
        else: val=f"({ty}) u64=0x{u64(raw,off):X}"
        marker=""
        if "bjective" in nm or "rogress" in nm or "arget" in nm or "ax" in nm or "oal" in nm or "ount" in nm: marker="  <<<"
        print(f"{ind}  +0x{off:03X} {ty:22} {nm:28} = {val}{marker}")
        f=p(f+0x18); i+=1

ma=p(MDL+0xE0); bm=p(MDL+0x108)
print(f"MissionModel @0x{MDL:X}  MissionAsset@0xE0=0x{ma:X}  BaseMission@0x108=0x{bm:X}")
if looksptr(ma): dump_obj(ma,"MissionAsset (DA)")
print()
if looksptr(bm): dump_obj(bm,"BaseMission")
