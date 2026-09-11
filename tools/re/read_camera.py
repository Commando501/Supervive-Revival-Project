# read_camera.py — dump the live camera state: PC->PlayerCameraManager view target + cached POV, and the hero's
# Camera component + spring-arm (TargetArmLength / rotation / distance fields). Read-only RPM.
#   usage: read_camera.py <PID> <BASE-hex> <pcHex> <heroHex>
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); PC=int(sys.argv[3],16); HERO=int(sys.argv[4],16)
NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def f32(b,o): return struct.unpack("<f",b[o:o+4])[0]
def f64(b,o): return struct.unpack("<d",b[o:o+8])[0]
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
def nameid(o): b=rpm(o+0x20,4); return u32(b,0) if b else 0
def clsof(o): b=rpm(o+0x18,8); return u64(b,0) if b else 0
def cname(o): c=clsof(o); return fname(nameid(c)) if looksptr(c) else "?"
def find_prop(cls,want):
    depth=0
    while looksptr(cls) and depth<16:
        f=rpm(cls+0x58,8); f=u64(f,0) if f else 0; n=0
        while looksptr(f) and n<700:
            if fname(nameid(f))==want:
                ob=rpm(f+0x44,4); fcb=rpm(f+0x08,8); fc=u64(fcb,0) if fcb else 0
                fcn=fname(u32(rpm(fc+0x00,4),0)) if looksptr(fc) and rpm(fc+0x00,4) else "?"
                return (u32(ob,0) if ob else None), fcn
            nx=rpm(f+0x18,8); f=u64(nx,0) if nx else 0; n+=1
        sc=rpm(cls+0x48,8); cls=u64(sc,0) if sc else 0; depth+=1
    return None,None
def getp(obj,prop):
    off,_=find_prop(clsof(obj),prop)
    if off is None: return None,None
    v=rpm(obj+off,8); return (u64(v,0) if v else 0),off

# PlayerCameraManager
pcm,pcmo=getp(PC,"PlayerCameraManager")
print("PC 0x%X PlayerCameraManager @0x%X = 0x%X (%s)"%(PC,pcmo or 0,pcm or 0,cname(pcm) if pcm and looksptr(pcm) else "-"))
if pcm and looksptr(pcm):
    vt,vto=getp(pcm,"ViewTarget")   # FTViewTarget struct starts here: Target(obj)@+0
    # ViewTarget is a struct; its Target is the first ptr
    if vto is not None:
        tb=rpm(pcm+vto,8); tgt=u64(tb,0) if tb else 0
        print("  ViewTarget.Target @0x%X = 0x%X (%s)"%(vto,tgt,cname(tgt) if looksptr(tgt) else "-"))
    # CameraCachePrivate: FCameraCacheEntry {double TimeStamp; FMinimalViewInfo POV}. POV.Location@+8 (FVector dbl), Rotation@+0x20 (FRotator dbl), FOV@+0x38 (float)
    cc,cco=getp(pcm,"CameraCachePrivate")
    off,_=find_prop(clsof(pcm),"CameraCachePrivate")
    if off is not None:
        b=rpm(pcm+off,0x60)
        if b:
            lx,ly,lz=f64(b,8),f64(b,16),f64(b,24); print("  POV.Location=(%.0f,%.0f,%.0f)"%(lx,ly,lz))
            rp,ry,rr=f64(b,0x20),f64(b,0x28),f64(b,0x30); print("  POV.Rotation(P,Y,R)=(%.1f,%.1f,%.1f)"%(rp,ry,rr))
            print("  POV.FOV=%.1f"%f32(b,0x38))
# hero location
hl,_=getp(HERO,"RootComponent")
def comploc(c):
    off,_=find_prop(clsof(c),"RelativeLocation");  b=rpm(c+(off if off else 0x158),24); return (f64(b,0),f64(b,8),f64(b,16)) if b else (0,0,0)
if hl and looksptr(hl):
    print("HERO 0x%X loc=(%.0f,%.0f,%.0f)"%(HERO,*comploc(hl)))
# hero Camera component + attach parent (spring arm) + arm length / distance fields
cam,camo=getp(HERO,"Camera")
print("HERO.Camera @0x%X = 0x%X (%s)"%(camo or 0,cam or 0,cname(cam) if cam and looksptr(cam) else "-"))
if cam and looksptr(cam):
    ap,_=getp(cam,"AttachParent"); print("  Camera.AttachParent = 0x%X (%s)"%(ap or 0,cname(ap) if ap and looksptr(ap) else "-"))
    for parent in [cam, ap]:
        if not (parent and looksptr(parent)): continue
        for fld in ("TargetArmLength","SocketOffset","TargetOffset","CameraDistance","Distance","Zoom","FieldOfView"):
            off,fc=find_prop(clsof(parent),fld)
            if off is not None:
                b=rpm(parent+off,8); print("    %s.%s @0x%X = %.2f (%s)"%(cname(parent),fld,off,f32(b,0) if b else 0,fc))
