# poke_scale.py — write a SceneComponent's RelativeScale3D (offset 0x188 in this build) and read it back.
#   usage: poke_scale.py <PID> <compHex> [x y z]
import ctypes, sys, struct
from ctypes import wintypes
PID=int(sys.argv[1],0); OBJ=int(sys.argv[2],16)
X,Y,Z = (float(sys.argv[3]),float(sys.argv[4]),float(sys.argv[5])) if len(sys.argv)>5 else (1.0,1.0,1.0)
SCALE_OFF=0x188
k=ctypes.WinDLL("kernel32",use_last_error=True); k.OpenProcess.restype=wintypes.HANDLE
h=k.OpenProcess(0x1F0FFF,False,PID)
def rd(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not a or not k.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def wr(a,data):
    r=ctypes.c_size_t(0)
    buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    return bool(k.WriteProcessMemory(h,ctypes.c_void_p(a),buf,len(data),ctypes.byref(r))) and r.value==len(data)
before=rd(OBJ+SCALE_OFF,24)
print("before RelativeScale3D = (%.3f, %.3f, %.3f)" % struct.unpack("<ddd",before))
ok=wr(OBJ+SCALE_OFF, struct.pack("<ddd",X,Y,Z))
after=rd(OBJ+SCALE_OFF,24)
print("write ok=%s" % ok)
print("after  RelativeScale3D = (%.3f, %.3f, %.3f)" % struct.unpack("<ddd",after))
