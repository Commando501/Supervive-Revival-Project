import ctypes as C, sys
from ctypes import wintypes as W
PID = 59604
addrs = [0x1AFC4E153A0,0x1AFC4F3DB50,0x1B057E8CD40,0x1B083561900,0x1B083561E40,0x1B083562700,0x1B083532540,0x1B083509000,0x1B0834AE780]
k=C.windll.kernel32
k.OpenProcess.restype=W.HANDLE; k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD]
h=k.OpenProcess(0x0010,False,PID)
if not h: print("OpenProcess failed",k.GetLastError()); sys.exit(1)
def rd(a,n):
    buf=(C.c_ubyte*n)(); got=C.c_size_t(0)
    ok=k.ReadProcessMemory(h,C.c_void_p(a),buf,n,C.byref(got))
    return bytes(buf) if ok else None
def valid_ptr(p): return 0x10000 < p < 0x7FFFFFFFFFFF
for a in addrs:
    mem=rd(a,0x220)
    if not mem: print(f"{a:#x} read fail"); continue
    hits=[]
    for off in range(0,0x210,8):
        ptr=int.from_bytes(mem[off:off+8],'little')
        num=int.from_bytes(mem[off+8:off+12],'little',signed=True)
        mx =int.from_bytes(mem[off+12:off+16],'little',signed=True)
        if valid_ptr(ptr) and 1<=num<=256 and mx>=num and mx<=512:
            hits.append((off,ptr,num,mx))
    print(f"ServerAuthConfig {a:#x}: TArray-like candidates:")
    for off,ptr,num,mx in hits:
        print(f"   +{off:#05x}: ptr={ptr:#x} num={num} max={mx}")
    if not hits: print("   (none)")
