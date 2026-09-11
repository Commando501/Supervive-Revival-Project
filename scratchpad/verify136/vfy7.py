import ctypes
from ctypes import wintypes
PID=43456; BASE=0x7FF608F40000; NAMEPOOL=BASE+0x9D81450
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def ptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
def fname(i):
    blk=i>>16; off=(i&0xFFFF)<<1; bp=rpm(NAMEPOOL+blk*8,8)
    bp=int.from_bytes(bp,"little"); hd=int.from_bytes(rpm(bp+off,2),"little")
    ln=hd>>6; w=hd&1; s=rpm(bp+off+2,ln*(2 if w else 1))
    return "".join(chr(s[k*2]|(s[k*2+1]<<8)) for k in range(ln)) if w else s.decode("latin1","replace")
def nm(o): return fname(u32(rpm(o+0x20,4),0)) if ptr(o) else "-"
# +0x3d0 = AIControllerClass, read straight out of SpawnDefaultController's disassembly
print("=== APawn::AIControllerClass @ +0x3D0  (the offset SpawnDefaultController reads at 0x3BBF404) ===")
for lbl,o in (("bot pawn 1 ",0x1B3E6922AE0),("bot pawn 2 ",0x1B302F7D560),("player hero",0x1B399FF5580)):
    v=u64(rpm(o+0x3D0,8),0)
    print(f"  {lbl} 0x{o:X}  AIControllerClass=0x{v:X} -> {nm(v)}")
print("\n=== FINAL STABILITY RE-READ (are the results still there?) ===")
for lbl,o,off,exp in (("AIC#1.Pawn",0x1B3F58BC5E0,0x3F8,0x1B3E6922AE0),
                      ("pawn1.Controller",0x1B3E6922AE0,0x400,0x1B3F58BC5E0),
                      ("AIC#2.Pawn",0x1B3F75EAEA0,0x3F8,0x1B302F7D560),
                      ("pawn2.Controller",0x1B302F7D560,0x400,0x1B3F75EAEA0)):
    v=u64(rpm(o+off,8),0)
    print(f"  {lbl:20s} = 0x{v:X}  {'STABLE' if v==exp else '*** CHANGED ***'}")
