# Derive UWidget::bIsManagedByGameViewportSubsystem (a NON-reflected bitfield) from the reflected
# bIsVolatile that immediately precedes it, then CALIBRATE before trusting it.
import ctypes,sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16)
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
def lp(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def p(a):
    b=rpm(a,8); return u64(b,0) if b else 0
_c={}
def fname(i):
    if i in _c: return _c[i]
    blk=i>>16; off=(i&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if lp(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; w=hd&1
                if 0<ln<250:
                    s=rpm(bp+off+2,ln*(2 if w else 1))
                    if s: r=("".join(chr(s[k*2]|(s[k*2+1]<<8)) for k in range(ln)) if w else s.decode("latin1","replace"))
    _c[i]=r; return r
def oname(o):
    b=rpm(o+0x20,4); return fname(u32(b,0)) if b else "?"
def ftype(f):
    fc=p(f+0x08)
    if not lp(fc): return "?"
    b=rpm(fc,4); return fname(u32(b,0)) if b else "?"

# --- find bIsVolatile on any widget class chain ---
def find_bisvolatile(cls):
    cur=cls; lvl=0
    while lp(cur) and lvl<14:
        f=p(cur+0x58); i=0
        while lp(f) and i<800:
            if oname(f)=="bIsVolatile" and ftype(f)=="BoolProperty":
                raw=rpm(f,0x80)
                return i32(raw,0x44), raw[0x71], raw[0x73]   # offset, byteOffset, fieldMask
            f=p(f+0x18); i+=1
        cur=p(cur+0x48); lvl+=1
    return None

# --- sweep all live UUserWidget-ish objects ---
hdr=rpm(OBJOBJECTS,0x18); objectsPtr=u64(hdr,0); numEl=u32(hdr,0x14)
nch=(numEl+PERCHUNK-1)//PERCHUNK; cp=rpm(objectsPtr,nch*8)
widgets=[]; cache={}
for ci in range(nch):
    ch=int.from_bytes(cp[ci*8:ci*8+8],"little")
    if not lp(ch): continue
    cnt=min(PERCHUNK,numEl-ci*PERCHUNK); items=rpm(ch,cnt*STRIDE)
    if not items: continue
    for j in range(cnt):
        o=u64(items,j*STRIDE)
        if not lp(o): continue
        c=p(o+0x18)
        if not lp(c): continue
        cn=cache.get(c)
        if cn is None: cn=oname(c); cache[c]=cn
        if cn.startswith("WBP_") or cn.endswith("UserWidget"):
            on=oname(o)
            if not on.startswith("Default__"):
                widgets.append((o,on,cn,c))
print(f"live widget-ish objects: {len(widgets)}")
if not widgets: sys.exit(0)
spec=find_bisvolatile(widgets[0][3])
if not spec: print("bIsVolatile not found"); sys.exit(1)
off,bo,fm=spec
print(f"bIsVolatile: +0x{off:X} byteOff={bo} fieldMask=0x{fm:02X}")
# the NEXT bit in declaration order is bIsManagedByGameViewportSubsystem
if fm==0x80: moff,mmask = off+bo+1, 0x01
else:        moff,mmask = off+bo,   fm<<1
print(f"=> derived bIsManagedByGameViewportSubsystem: byte +0x{moff:X} mask 0x{mmask:02X}\n")
inv=[]
for o,on,cn,c in widgets:
    b=rpm(o+moff,1)
    if b and (b[0]&mmask): inv.append((o,on,cn))
print(f"CALIBRATION -- widgets with the derived bit SET: {len(inv)} of {len(widgets)}")
for o,on,cn in inv[:15]: print(f"   0x{o:X}  {cn:44} {on[:40]}")
print()
MOTD=0x2692C618DF0
b=rpm(MOTD+moff,1)
print(f"MOTD widget 0x{MOTD:X}: bIsManagedByGameViewportSubsystem = {bool(b[0]&mmask) if b else '?'}")
