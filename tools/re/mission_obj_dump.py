# mission_obj_dump.py — dump a live MissionModel's Objectives (MapProperty @+0x68) to find where the
# progress-bar values (current/max) live. Also decodes the MissionModel class's Objectives MapProperty
# layout (KeyProp/ValueProp/FScriptMapLayout) so the map can be iterated precisely.
# Read-only RPM. usage: mission_obj_dump.py <PID> <BASE-hex> [maxModels]
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); MAXM=int(sys.argv[3]) if len(sys.argv)>3 else 3
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
PM_MM=0x3B8; MM_MISSIONS=0x30; MDL_ID=0x30; MDL_XP=0x60; MDL_OBJ=0x68
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
def f32(b,o):
    import struct
    return struct.unpack_from("<f",b,o)[0]
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
def find_obj(name, clsfilter=None, skip_default=True):
    op=p(OBJOBJECTS); hdr=rpm(OBJOBJECTS,0x18); numEl=u32(hdr,0x14)
    nchunks=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nchunks):
        chunk=p(op+ci*8)
        if not looksptr(chunk): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
        for j in range(cnt):
            obj=p(chunk+j*STRIDE)
            if not looksptr(obj): continue
            if oname(obj)==name and (clsfilter is None or clsfilter in ocls(obj)):
                if skip_default and oname(obj).startswith("Default__"): continue
                return obj
    return 0
def find_class(name):
    return find_obj(name, "Class", skip_default=False)
def find_live_by_class(clsname):
    op=p(OBJOBJECTS); hdr=rpm(OBJOBJECTS,0x18); numEl=u32(hdr,0x14)
    nchunks=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nchunks):
        chunk=p(op+ci*8)
        if not looksptr(chunk): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
        for j in range(cnt):
            obj=p(chunk+j*STRIDE)
            if not looksptr(obj): continue
            if ocls(obj)==clsname and not oname(obj).startswith("Default__"):
                return obj
    return 0

def child_prop(cls, propname):
    f=p(cls+0x58); i=0
    while looksptr(f) and i<80:
        if oname(f)==propname: return f
        f=p(f+0x18); i+=1
    return 0

def hexrow(b,base,o,n=16):
    hexs=" ".join(f"{b[o+c]:02X}" for c in range(n))
    ascii="".join(chr(b[o+c]) if 32<=b[o+c]<127 else "." for c in range(n))
    return f"  +0x{o:03X} (0x{base+o:X}): {hexs}  {ascii}"

print(f"# base=0x{BASE:X} PID={PID}")
# --- MapProperty layout decode ---
mmc=find_class("MissionModel")
print(f"MissionModel class @0x{mmc:X}")
objp=child_prop(mmc,"Objectives")
print(f"Objectives prop @0x{objp:X} type={ftype(objp)}")
if objp:
    raw=rpm(objp,0xB0) or b"\0"*0xB0
    print(f"  Offset_Internal@+0x44 = 0x{i32(raw,0x44):X}")
    # dump raw bytes of the MapProperty to eyeball KeyProp/ValueProp/layout
    for o in range(0x60,0xB0,16):
        print(hexrow(raw,objp,o))
    # typical FMapProperty (5.4): KeyProp@+0x78, ValueProp@+0x80 (guess; verify via ftype)
    for cand in (0x70,0x78,0x80,0x88):
        pv=u64(raw,cand)
        if looksptr(pv):
            print(f"  [+0x{cand:X}] ptr 0x{pv:X} name={oname(pv)} type={ftype(pv)} elemSize={u32(rpm(pv,0x38) or b'0'*0x38,0x34)}")

# --- live model ---
pm=find_live_by_class("ProgressionManager")
print(f"\nProgressionManager @0x{pm:X}")
mm=p(pm+PM_MM)
print(f"MissionsModel @0x{mm:X} class={ocls(mm)}")
# Missions map @+0x30 : TMap<FString, MissionModel*>
mapData=p(mm+MM_MISSIONS); mapNum=u32(rpm(mm+MM_MISSIONS,0x10) or b"\0"*0x10,8); mapMax=u32(rpm(mm+MM_MISSIONS,0x10) or b"\0"*0x10,0xC)
print(f"Missions map: Data=0x{mapData:X} Num={mapNum} Max={mapMax}")

# The MissionModel pointers: iterate the set element buffer. We don't yet know stride; try to grab
# pointers heuristically by scanning the Data buffer for values whose ocls=='MissionModel'.
models=[]
if looksptr(mapData):
    scan=rpm(mapData, min(mapMax if mapMax>0 else mapNum, 400)*0x20 + 0x40)
    if scan:
        for o in range(0, len(scan)-8, 8):
            v=u64(scan,o)
            if looksptr(v) and ocls(v)=="MissionModel" and v not in models:
                models.append(v)
print(f"found {len(models)} MissionModel ptrs (heuristic)")

for mi,mdl in enumerate(models[:MAXM]):
    idp=p(mdl+MDL_ID); idn=u32(rpm(mdl+MDL_ID,0x10) or b"\0"*0x10,8)
    idstr=""
    if looksptr(idp):
        raw=rpm(idp, min(idn*2,128) if idn else 64)
        if raw: idstr=raw.decode("utf-16-le","replace").rstrip("\x00")
    xp=u32(rpm(mdl+MDL_XP,4) or b"\0\0\0\0",0)
    print(f"\n=== MissionModel[{mi}] @0x{mdl:X} ID='{idstr}' XPReward={xp} ===")
    # Objectives map header @+0x68
    oh=rpm(mdl+MDL_OBJ,0x10) or b"\0"*0x10
    od=u64(oh,0); on=u32(oh,8); om=u32(oh,0xC)
    print(f"Objectives map: Data=0x{od:X} Num={on} Max={om}")
    if looksptr(od) and 0<on<64:
        buf=rpm(od, (om if om>0 else on)*0x60 + 0x80)
        if buf:
            print(f"Objectives Data buffer hexdump ({len(buf)} bytes):")
            for o in range(0, len(buf), 16):
                row=hexrow(buf,od,o)
                # annotate: FName candidates + ptr + float
                notes=[]
                for c in (0,8):
                    if o+c+4<=len(buf):
                        nid=u32(buf,o+c); nm=fname(nid)
                        if nm and nm!="?" and not nm.startswith("?") and len(nm)>2: notes.append(f"@+{c}:FName '{nm}'")
                for c in range(0,16,8):
                    if o+c+8<=len(buf):
                        v=u64(buf,o+c)
                        if looksptr(v):
                            cn=ocls(v)
                            notes.append(f"@+{c}:ptr->{cn if cn!='?' else hex(v)}")
                print(row + ("   " + " ".join(notes) if notes else ""))
