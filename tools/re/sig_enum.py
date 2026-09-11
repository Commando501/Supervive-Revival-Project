# sig_enum.py — find target UClasses by name in the live GUObjectArray and dump each UFunction's
# signature (params + return, with CPF flags) so the ingestion-call param shapes are explicit.
# Read-only RPM. usage: sig_enum.py <PID> <BASE-hex> [ClassName ...]
# Offsets (this build): GUObjectArray@BASE+0x9E38930 (objectsPtr@+0, numEl@+0x14), item stride 0x18.
#   UObject Class@+0x18 Name@+0x20.  UClass.Children(UField*)@+0x50, UField.Next@+0x30.
#   UStruct.ChildProperties(FField*)@+0x58, Script.Num@+0x70.
#   FField: FFieldClass@+0x08, Next@+0x18, Name@+0x20, Flags(EPropertyFlags u64)@+0x38.
#   FStructProperty.Struct@+0x70, FObjectProperty.PropertyClass@+0x70, FArrayProperty.Inner@+0x78.
import ctypes, sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16)
TARGETS=sys.argv[3:] or ["ProgressionManager","MissionsModel","LokiPlayerState_Missions"]
NAMEPOOL=BASE+0x9D81450; OBJOBJECTS=BASE+0x9E38930
PERCHUNK=65536; STRIDE=0x18
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
def oname(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ocls(o):
    c=p(o+0x18); return oname(c) if looksptr(c) else "?"
def ffname(f):
    b=rpm(f+0x20,4); return fname(u32(b,0)) if b else "?"
def fftype(f):
    fc=p(f+0x08)
    if not looksptr(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"
def ffflags(f):
    b=rpm(f+0x38,8); return u64(b,0) if b else 0
def inner_desc(f,ty):
    # enrich container/struct/object property types with their inner/target
    try:
        if ty in ("StructProperty",):
            st=p(f+0x70); return f"struct {oname(st)}" if looksptr(st) else "struct ?"
        if ty in ("ObjectProperty","ClassProperty","WeakObjectProperty","SoftObjectProperty"):
            pc=p(f+0x70); return f"{oname(pc)}*" if looksptr(pc) else "obj ?"
        if ty=="ArrayProperty":
            inn=p(f+0x78)
            if looksptr(inn):
                ity=fftype(inn); return f"TArray<{inner_desc(inn,ity) or ity}>"
            return "TArray<?>"
    except Exception: pass
    return None
def find_class(name):
    op=p(OBJOBJECTS); numEl=u32(rpm(OBJOBJECTS,0x18) or b"\0"*0x18,0x14)
    if not looksptr(op) or numEl<=0 or numEl>8000000: return 0
    nchunks=(numEl+PERCHUNK-1)//PERCHUNK
    for ci in range(nchunks):
        chunk=p(op+ci*8)
        if not looksptr(chunk): continue
        cnt=(numEl-ci*PERCHUNK) if ci==nchunks-1 else PERCHUNK
        for j in range(cnt):
            obj=p(chunk+j*STRIDE)
            if not looksptr(obj): continue
            if oname(obj)==name and "Class" in ocls(obj):
                return obj
    return 0
CPF={0x80:"Parm",0x100:"Out",0x400:"Return",0x10:"ConstParm?",0x400000000:"ConstParm",0x1000000:"RepNotify?"}
for tname in TARGETS:
    cls=find_class(tname)
    print(f"\n########## {tname}  (UClass @0x{cls:X}) ##########")
    if not cls: print("  NOT FOUND"); continue
    ch=p(cls+0x50); f=ch; i=0
    while looksptr(f) and i<600:
        if ocls(f)=="Function":
            fn=f; nm=oname(fn); snum=u32(rpm(fn+0x70,4) or b"\0\0\0\0",0)
            kind="BP" if snum>0 else "native"
            params=[]; pf=p(fn+0x58); k=0
            while looksptr(pf) and k<40:
                ty=fftype(pf); nmp=ffname(pf); fl=ffflags(pf)
                if fl&0x80:  # CPF_Parm only (skip pure locals)
                    tags=[CPF[m] for m in (0x400,0x100) if fl&m]
                    desc=inner_desc(pf,ty) or ty
                    role="RET" if fl&0x400 else ("OUT" if fl&0x100 else "in")
                    params.append(f"{role}:{nmp}:{desc}")
                nb=rpm(pf+0x18,8); pf=u64(nb,0) if nb else 0; k+=1
            sig=", ".join(params) if params else "(void)"
            print(f"  {kind:6} {nm:40} {sig}")
        nb=rpm(f+0x30,8); f=u64(nb,0) if nb else 0; i+=1
