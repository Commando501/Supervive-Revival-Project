import ctypes,sys
from ctypes import wintypes
from collections import Counter
PID=43456; BASE=0x7FF608F40000
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
def ptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(i):
    if i in _nc: return _nc[i]
    blk=i>>16; off=(i&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if ptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; w=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if w else 1))
                    if s: r=("".join(chr(s[k*2]|(s[k*2+1]<<8)) for k in range(ln)) if w else s.decode("latin1","replace"))
    _nc[i]=r; return r
def nm_full(o):
    b=rpm(o+0x20,8)
    if not b: return "?"
    n=fname(u32(b,0)); num=u32(b,4)
    return f"{n}"+("" if num==0 else f"_{num-1}")+f"   [ComparisonIndex={u32(b,0)} Number={num}]"
def clsof(o):
    b=rpm(o+0x18,8); return u64(b,0) if b else 0
def chain(c):
    out=[];d=0
    while ptr(c) and d<24:
        b=rpm(c+0x20,4); out.append(fname(u32(b,0)) if b else "?")
        b=rpm(c+0x48,8); c=u64(b,0) if b else 0; d+=1
    return out
AI=0x1B3F58BC5E0; PAWN=0x1B3E6922AE0; PLAYERHERO=0x1B399FF5580
for lbl,o in (("AIController",AI),("spawned pawn",PAWN),("player hero",PLAYERHERO)):
    b=rpm(o,0x18)
    print(f"\n=== {lbl} 0x{o:X} ===")
    print(f"  vtable        = 0x{u64(b,0):X}   (module? {'YES base+0x%X'%(u64(b,0)-BASE) if BASE<=u64(b,0)<BASE+0x0B000000 else 'NO -- heap'})")
    print(f"  ObjectFlags   @+0x0C = 0x{u32(b,0x0C):08X}")
    print(f"  InternalIndex @+0x10 = {u32(b,0x10)}")
    print(f"  FULL NAME     = {nm_full(o)}")
    print(f"  chain         = {' <- '.join(chain(clsof(o)))}")
print("\n=== POSSESSION FINGERPRINT (raw qwords, my own reads) ===")
for off,lbl in ((0x3F8,"AIC+0x3F8 Pawn"),(0x408,"AIC+0x408 Character"),(0x198,"AIC+0x198 Instigator"),
                (0x150,"AIC+0x150 Owner"),(0x3C0,"AIC+0x3C0 PlayerState"),(0x490,"AIC+0x490 PathFollowingComponent"),
                (0x4A8,"AIC+0x4A8 ActionsComp")):
    v=u64(rpm(AI+off,8),0); print(f"  {lbl:44s} = 0x{v:X}"+(f"  -> {fname(u32(rpm(v+0x20,4),0))}" if ptr(v) else ""))
print()
for off,lbl in ((0x400,"PAWN+0x400 Controller"),(0x408,"PAWN+0x408 PreviousController"),
                (0x150,"PAWN+0x150 Owner"),(0x3D8,"PAWN+0x3D8 PlayerState"),(0x198,"PAWN+0x198 Instigator")):
    v=u64(rpm(PAWN+off,8),0); print(f"  {lbl:44s} = 0x{v:X}"+(f"  -> {fname(u32(rpm(v+0x20,4),0))}" if ptr(v) else ""))
print("\n=== CONTROL: same offsets on the PLAYER hero (never touched by our call) ===")
for off,lbl in ((0x400,"PLAYERHERO+0x400 Controller"),(0x408,"PLAYERHERO+0x408 PreviousController"),
                (0x150,"PLAYERHERO+0x150 Owner"),(0x3D8,"PLAYERHERO+0x3D8 PlayerState")):
    v=u64(rpm(PLAYERHERO+off,8),0); print(f"  {lbl:44s} = 0x{v:X}"+(f"  -> {fname(u32(rpm(v+0x20,4),0))}" if ptr(v) else ""))
