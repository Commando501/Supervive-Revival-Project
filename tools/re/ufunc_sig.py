# Walk a live UFunction's ChildProperties (params + locals) to recover its signature.
# Read-only RPM. This build: UStruct.ChildProperties@+0x68, FField.Next@+0x18, FField.Name@+0x20,
# FField.FlagsPrivate(EPropertyFlags)@+0x28, FField.FFieldClass*@+0x08 (its Name gives the type).
#   usage: ufunc_sig.py <PID>   (addresses of the 5 mission UFuncs are hardcoded from the harness run)
import ctypes, sys
from ctypes import wintypes
PID = int(sys.argv[1], 0)
BASE = 0x7FF682A80000
NAMEPOOL = BASE + 0x9D81450
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
def rpm(a, n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u16(b,o): return int.from_bytes(b[o:o+2],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def looksptr(v): return 0x10000<=v<0x0001000000000000 and (v&7)==0
_nc={}
def fname(idx):
    if idx in _nc: return _nc[idx]
    blk=idx>>16; off=(idx&0xFFFF)<<1
    bp=rpm(NAMEPOOL+blk*8,8); r="?"
    if bp:
        bp=int.from_bytes(bp,"little")
        if looksptr(bp):
            hd=rpm(bp+off,2)
            if hd:
                hd=int.from_bytes(hd,"little"); ln=hd>>6; wide=hd&1
                if 0<ln<200:
                    s=rpm(bp+off+2,ln*(2 if wide else 1))
                    if s: r="".join(chr(s[i*2]|(s[i*2+1]<<8)) for i in range(ln)) if wide else s.decode("latin1","replace")
    _nc[idx]=r; return r
def ffield_name(f):
    nb=rpm(f+0x20,4)
    return fname(u32(nb,0)) if nb else "?"
def ffield_type(f):
    # FField+0x08 = FFieldClass* ; FFieldClass+0x00 = FName Id (the type name e.g. StructProperty)
    fcb=rpm(f+0x08,8)
    if not fcb: return "?"
    fc=u64(fcb,0)
    if not looksptr(fc): return "?"
    nb=rpm(fc,4)
    return fname(u32(nb,0)) if nb else "?"
# EPropertyFlags CPF_Parm=0x80, CPF_OutParm=0x100, CPF_ReturnParm=0x400
def ffield_flags(f):
    fb=rpm(f+0x38,8)
    return u64(fb,0) if fb else 0
def ffield_elemsize(f):
    b=rpm(f+0x30,8)
    return u32(b,4) if b else 0

FUNCS = {
    "CreateMissionModelFromFinalProgress": 0x26A2A3448B0,
    "GetMissions":                         0x26A2A344F40,
    "GetMissionModel":                     0x26A2A344D60,
    "GetActiveMissionModel":               0x26A2A344A90,
    "OnPSMissionsUpdated":                 0x26A2A345210,
}
for name, fn in FUNCS.items():
    print(f"\n=== {name} @0x{fn:X} ===")
    hd=rpm(fn,0x90)
    if not hd: print("  (unreadable)"); continue
    children=u64(hd,0x58)       # ChildProperties (FField* head)
    print(f"  ChildProperties head=0x{children:X}")
    f=children; i=0
    while looksptr(f) and i<40:
        nm=ffield_name(f); ty=ffield_type(f); fl=ffield_flags(f); es=ffield_elemsize(f)
        tags=[]
        if fl&0x80: tags.append("Parm")
        if fl&0x100: tags.append("Out")
        if fl&0x400: tags.append("Return")
        if fl&0x400000000: tags.append("ConstРarm")
        role = " ".join(tags) if tags else "local"
        print(f"    [{i}] {ty:22} {nm:34} size={es:<4} {role}")
        nb=rpm(f+0x18,8); f=u64(nb,0) if nb else 0; i+=1
