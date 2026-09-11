# read_overlap.py — disambiguate why the WASD overlap didn't fire. Read-only RPM.
# For the active quest: its TargetTriggerBox, that box's OnActorBeginOverlap invocation-list Num (bind present?),
# the box collision component's GenerateOverlapEvents + world loc + BoxExtent, and the hero capsule's overlap flags.
#   usage: read_overlap.py <PID> <BASE-hex> <questHex> <heroHex>
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); QUEST=int(sys.argv[3],16); HERO=int(sys.argv[4],16)
NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def f64(b,o): return struct.unpack("<d",b[o:o+8])[0]
def f32(b,o): return struct.unpack("<f",b[o:o+4])[0]
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(idx):
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8)
    if not bp: return "?"
    bp=int.from_bytes(bp,"little")
    if not looksptr(bp): return "?"
    b2=rpm(bp+off,2)
    if not b2: return "?"
    hd=int.from_bytes(b2,"little"); ln=hd>>6; wide=hd&1
    if ln<=0 or ln>200: return "?"
    s=rpm(bp+off+2,ln*(2 if wide else 1))
    if not s: return "?"
    return "".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
def nameid(o):
    b=rpm(o+0x20,4); return u32(b,0) if b else 0
def clsof(o):
    b=rpm(o+0x18,8); return u64(b,0) if b else 0
def cname(o):
    c=clsof(o); return fname(nameid(c)) if looksptr(c) else "?"
def find_prop(cls,want):  # (offset, ffclass_name, bitmask) across super chain
    depth=0
    while looksptr(cls) and depth<16:
        f=rpm(cls+0x58,8); f=u64(f,0) if f else 0; n=0
        while looksptr(f) and n<600:
            if fname(nameid(f))==want:
                ob=rpm(f+0x44,4); off=u32(ob,0) if ob else None
                fcb=rpm(f+0x08,8); fc=u64(fcb,0) if fcb else 0
                fcn=fname(u32(rpm(fc+0x00,4),0)) if looksptr(fc) and rpm(fc+0x00,4) else "?"
                return off,fcn
            nx=rpm(f+0x18,8); f=u64(nx,0) if nx else 0; n+=1
        sc=rpm(cls+0x48,8); cls=u64(sc,0) if sc else 0; depth+=1
    return None,None
def getptr(obj,prop):
    off,_=find_prop(clsof(obj),prop)
    if off is None: return None,None
    v=rpm(obj+off,8); return (u64(v,0) if v else 0),off
def comp_world_loc(comp):
    off,_=find_prop(clsof(comp),"RelativeLocation")
    if off is None: off=0x158
    b=rpm(comp+off,24)
    return (f64(b,0),f64(b,8),f64(b,16)) if b else (0,0,0)

print("QUEST 0x%X %s"%(QUEST,cname(QUEST)))
box,bo=getptr(QUEST,"TargetTriggerBox")
print("  TargetTriggerBox @0x%X = 0x%X (%s)"%(bo or 0,box or 0,cname(box) if box and looksptr(box) else "-"))
if box and looksptr(box):
    # OnActorBeginOverlap multicast delegate: InvocationList TArray {ptr@+0, num@+8}
    do,_=find_prop(clsof(box),"OnActorBeginOverlap")
    if do is not None:
        b=rpm(box+do,16); ilp=u64(b,0); iln=u32(b,8)
        print("  box.OnActorBeginOverlap @0x%X InvocationList: ptr=0x%X Num=%d  <<< %s"%(do,ilp,iln,"BOUND" if iln>0 else "EMPTY (bind never ran)"))
        # dump each subscriber (Object, FunctionName) — FScriptDelegate is 0x18? {WeakObj(0x8)?, FName}
        for i in range(min(iln,6)):
            e=rpm(ilp+i*0x18,0x18)
            if e:
                subobj=u64(e,0); fn=fname(u32(e,0x10))
                print("     [%d] obj=0x%X(%s) fn=%s"%(i,subobj,cname(subobj) if looksptr(subobj) else "-",fn))
    root,_=getptr(box,"RootComponent")
    if root and looksptr(root):
        go,gm=find_prop(clsof(root),"bGenerateOverlapEvents")
        if go is None: go,gm=find_prop(clsof(root),"GenerateOverlapEvents")
        gval=rpm(root+go,1)[0] if go is not None and rpm(root+go,1) else -1
        wl=comp_world_loc(root)
        ext,_=find_prop(clsof(root),"BoxExtent")
        eb=rpm(root+ext,24) if ext is not None else None
        exv=(f64(eb,0),f64(eb,8),f64(eb,16)) if eb else None
        print("  box.Root 0x%X %s GenerateOverlapEvents=%s loc=(%.0f,%.0f,%.0f) BoxExtent=%s"%(root,cname(root),gval,wl[0],wl[1],wl[2],exv))
print("HERO 0x%X %s"%(HERO,cname(HERO)))
hroot,_=getptr(HERO,"RootComponent")
if hroot and looksptr(hroot):
    go,_=find_prop(clsof(hroot),"bGenerateOverlapEvents")
    if go is None: go,_=find_prop(clsof(hroot),"GenerateOverlapEvents")
    gval=rpm(hroot+go,1)[0] if go is not None and rpm(hroot+go,1) else -1
    wl=comp_world_loc(hroot)
    print("  hero.Root 0x%X %s GenerateOverlapEvents=%s loc=(%.0f,%.0f,%.0f)"%(hroot,cname(hroot),gval,wl[0],wl[1],wl[2]))
