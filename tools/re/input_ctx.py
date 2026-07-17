# input_ctx.py - is an Enhanced Input MAPPING CONTEXT applied? Read-only RPM.
# Route: LocalPlayer -> PlayerController(+0x38) -> PlayerInput (reflection) -> AppliedInputContexts (TMap).
# TMap<K,V> layout: TMap{TSet{TSparseArray{TArray{Data*@+0x00, Num@+0x08, Max@+0x0C}, ...}}} -> element buffer at +0x00.
import ctypes, sys
from ctypes import wintypes
PID=48788; BASE=0x7FF6AF000000; NAMEPOOL=BASE+0x9D81450
OBJOBJECTS=BASE+0x9E38930; PERCHUNK=65536; STRIDE=0x18
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
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
_nc={}
def fname(i):
    if i in _nc: return _nc[i]
    blk=i>>16; off=(i&0xFFFF)<<1; bp=u64(NAMEPOOL+blk*8); r="?"
    if lp(bp):
        hd=u16(bp+off); ln=hd>>6; w=hd&1
        if 0<ln<200:
            s=rpm(bp+off+2,ln*(2 if w else 1))
            if s: r=("".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if w else s.decode("latin1","replace"))
    _nc[i]=r; return r
def onm(o): return fname(u32(o+0x20)) if lp(o) else "-"
def cnm(o): return onm(u64(o+0x18)) if lp(o) else "-"
def fcls(p):
    c=u64(p+0x08); return fname(u32(c+0x00)) if lp(c) else "?"
def prop(obj,name):
    c=u64(obj+0x18); d=0
    while lp(c) and d<20:
        p=u64(c+0x58); i=0
        while lp(p) and i<600:
            if fname(u32(p+0x20))==name: return u32(p+0x44),fcls(p)
            p=u64(p+0x18); i+=1
        c=u64(c+0x48); d+=1
    return None,None
def each(cb):
    op=u64(OBJOBJECTS); num=u32(OBJOBJECTS+0x14)
    if not lp(op) or not(0<num<8000000): return
    for ci in range((num+PERCHUNK-1)//PERCHUNK):
        ch=u64(op+ci*8)
        if not lp(ch): continue
        cnt=min(PERCHUNK,num-ci*PERCHUNK)
        for j in range(cnt):
            o=u64(ch+j*STRIDE)
            if lp(o) and cb(o): return

# 1) the Enhanced Input subsystem + player input objects that actually exist
print("=== live Enhanced Input objects (GUObjectArray) ===")
hits=[]
def scan(o):
    cn=cnm(o)
    if cn and ("EnhancedInput" in cn or "EnhancedPlayerInput" in cn or cn=="InputMappingContext"):
        nm=onm(o)
        if not nm.startswith("Default__"): hits.append((cn,nm,o))
    return False
each(scan)
for cn,nm,o in sorted(hits)[:14]:
    print("  %-42s %-40s 0x%X"%(cn,nm[:40],o))
imc=[x for x in hits if x[0]=="InputMappingContext"]
print("  ... %d total; InputMappingContext assets loaded: %d"%(len(hits),len(imc)))

# 2) LocalPlayer -> PC -> PlayerInput -> AppliedInputContexts
L=0
def findL(o):
    global L
    if cnm(o)=="LocalPlayer" and not onm(o).startswith("Default__"): L=o; return True
    return False
each(findL)
pc=u64(L+0x38) if L else 0
print("\n=== route ===")
print("  LocalPlayer 0x%X -> PlayerController 0x%X (%s)"%(L,pc,cnm(pc)))
po,_=prop(pc,"PlayerInput"); pi=u64(pc+po) if po is not None else 0
print("  PC->PlayerInput @+0x%s = 0x%X  class=%s"%(("%X"%po) if po is not None else "?",pi,cnm(pi)))
if not lp(pi): print("  << PlayerInput is NULL -- no Enhanced Input at all"); sys.exit(0)
ao,ac=prop(pi,"AppliedInputContexts")
print("  PlayerInput->AppliedInputContexts @+0x%s [%s]"%(("%X"%ao) if ao is not None else "?",ac))
if ao is None: print("  << property not found"); sys.exit(0)
m=pi+ao
data=u64(m+0x00); num=u32(m+0x08); mx=u32(m+0x0C)
print("     TMap sparse-array: Data=0x%X Num=%d Max=%d"%(data,num,mx))
if not lp(data) or num<=0:
    print("\n  *** AppliedInputContexts is EMPTY -> NO MAPPING CONTEXT APPLIED ***")
else:
    print("\n  *** %d entry slot(s) -- scanning element buffer for InputMappingContext ptrs ***"%num)
    buf=rpm(data,min(num*32+64,4096))
    found=0
    if buf:
        for off in range(0,len(buf)-8,4):
            q=int.from_bytes(buf[off:off+8],"little")
            if lp(q) and cnm(q)=="InputMappingContext":
                print("     +0x%-4X -> %-44s (priority-ish next dword: %d)"%(off,onm(q),int.from_bytes(buf[off+8:off+12],"little")))
                found+=1
    if not found: print("     (no InputMappingContext ptr resolved in the buffer)")
