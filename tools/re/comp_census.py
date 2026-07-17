# comp_census.py - REFLECTION-based component census of a live UObject (read-only RPM).
#
# Why this exists (S80): the GUObjectArray "scan every object, filter class-name substring, check outer chain" pattern
# has now produced TWO false walls in this project by MISSING components that exist:
#   * CountHeroSkeletals()   -> "the hero has no SkeletalMeshComponent". The class is BP_Assault_DefaultSKMeshComponent_C
#                               and "SKMeshComponent" never matches "SkeletalMeshComponent". Invented the S79 mesh wall.
#   * S79 4e component census -> "the hero has NO USpringArmComponent". It is at +0x1990, class
#                               LokiCharacterSpringArmComponent, with TargetArmLength already 3020.
# Walking the class chain's ChildProperties and reading each ObjectProperty is EXACT: it reports what the object
# actually points at, plus the declaring class, and cannot cap out or miss on a name filter.
#
# usage: comp_census.py <PID> <BASE-hex> <OBJ-hex> [name-or-class-substr ...]
#   e.g. comp_census.py 48788 0x7FF6AF000000 0x28577E6D560 springarm camera input
import ctypes, sys
from ctypes import wintypes

PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); OBJ=int(sys.argv[3],16)
SUBS=[s.lower() for s in sys.argv[4:]]
NAMEPOOL=BASE+0x9D81450

k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
if not h: print("OpenProcess failed"); sys.exit(1)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(a):
    b=rpm(a,2); return int.from_bytes(b,"little") if b else 0
def u32(a):
    b=rpm(a,4); return int.from_bytes(b,"little") if b else 0
def u64(a):
    b=rpm(a,8); return int.from_bytes(b,"little") if b else 0
def lp(v): return 0x10000<=v<0x1000000000000 and (v&7)==0
def fname(i):
    blk=i>>16; off=(i&0xFFFF)<<1; bp=u64(NAMEPOOL+blk*8)
    if not lp(bp): return "?"
    hd=u16(bp+off); ln=hd>>6; w=hd&1
    if not(0<ln<200): return "?"
    s=rpm(bp+off+2,ln*(2 if w else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if w else s.decode("latin1","replace")
def onm(o): return fname(u32(o+0x20)) if lp(o) else "-"
def cnm(o): return onm(u64(o+0x18)) if lp(o) else "-"
def fcls(p):
    c=u64(p+0x08); return fname(u32(c+0x00)) if lp(c) else "?"   # FField->ClassPrivate@+0x08; FFieldClass::Name@+0x00
def supers(cls):
    out=[]; d=0
    while lp(cls) and d<20: out.append(onm(cls)); cls=u64(cls+0x48); d+=1
    return out

print("obj 0x%X class=%s"%(OBJ,cnm(OBJ)))
cls=u64(OBJ+0x18); d=0; rows=[]; seen=set()
while lp(cls) and d<20:
    owner=onm(cls); p=u64(cls+0x58); i=0
    while lp(p) and i<600:
        n=fname(u32(p+0x20))
        if fcls(p) in ("ObjectProperty","ObjectPtrProperty") and n not in seen:
            off=u32(p+0x44); v=u64(OBJ+off)
            if lp(v):
                cn=cnm(v); seen.add(n)
                if SUBS and not any(s in n.lower() or s in cn.lower() for s in SUBS): continue
                rows.append((off,n,v,cn,owner))
        p=u64(p+0x18); i+=1
    cls=u64(cls+0x48); d+=1
print("%d object properties resolve non-null%s\n"%(len(rows)," (filtered)" if SUBS else ""))
for off,n,v,cn,owner in sorted(rows):
    print("  %-34s @+0x%-6X 0x%-13X %-42s [decl on %s]"%(n,off,v,cn,owner))
if SUBS:
    for off,n,v,cn,owner in sorted(rows):
        print("\n  %s ancestry: %s"%(n," <- ".join(supers(u64(v+0x18)))))
