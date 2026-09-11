# read_scale.py — read a SceneComponent's RelativeLocation/Rotation/Scale3D + an actor's, at fixed offsets.
#   usage: read_scale.py <PID> <objHex> [locOff=0x158]
# USceneComponent (this build): RelativeLocation@0x158, RelativeRotation@0x170, RelativeScale3D@0x188 (FVector3d).
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); OBJ=int(sys.argv[2],16)
LOC=int(sys.argv[3],16) if len(sys.argv)>3 else 0x158
k=ctypes.WinDLL("kernel32",use_last_error=True); k.OpenProcess.restype=wintypes.HANDLE
h=k.OpenProcess(0x1F0FFF,False,PID)
def rd(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
blob=rd(OBJ+LOC, 0x50)
if not blob:
    print("unreadable"); sys.exit(1)
loc=struct.unpack_from("<ddd",blob,0x00)
rot=struct.unpack_from("<ddd",blob,0x18)
scl=struct.unpack_from("<ddd",blob,0x30)
print("RelativeLocation = (%.1f, %.1f, %.1f)" % loc)
print("RelativeRotation = (%.1f, %.1f, %.1f)" % rot)
print("RelativeScale3D  = (%.3f, %.3f, %.3f)%s" % (scl + (("  *** ZERO/FLAT -> INVISIBLE ***" if (scl[0]==0 or scl[1]==0 or scl[2]==0) else "  (ok)"),)))
