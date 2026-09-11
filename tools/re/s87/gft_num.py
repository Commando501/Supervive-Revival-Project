import ctypes as C, sys
from ctypes import wintypes as W
PID = 59604
# GameFeatureToggles TArray<bool> at +0x130 on the client's LokiServerAuthConfig (S85 §11): ptr@+0x130, num@+0x138, max@+0x13C
OFF = 0x130
addrs = [0x1AFC4E153A0,0x1AFC4F3DB50,0x1B057E8CD40,0x1B083561900,0x1B083561E40,0x1B083562700,0x1B083532540,0x1B083509000,0x1B0834AE780]
k=C.windll.kernel32
k.OpenProcess.restype=W.HANDLE; k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD]
h=k.OpenProcess(0x0010,False,PID)  # PROCESS_VM_READ
if not h: print("OpenProcess failed",k.GetLastError()); sys.exit(1)
def rd(a,n):
    buf=(C.c_ubyte*n)(); got=C.c_size_t(0)
    ok=k.ReadProcessMemory(h,C.c_void_p(a),buf,n,C.byref(got))
    return bytes(buf) if ok else None
for a in addrs:
    b=rd(a+OFF,16)
    if not b: print(f"{a:#x} read fail"); continue
    ptr=int.from_bytes(b[0:8],'little'); num=int.from_bytes(b[8:12],'little',signed=True); mx=int.from_bytes(b[12:16],'little',signed=True)
    # sample first few bool bytes
    sample=""
    if 0<num<=256 and ptr:
        sb=rd(ptr,min(num,16))
        if sb: sample=" first="+ " ".join(f"{x:02x}" for x in sb)
    print(f"ServerAuthConfig {a:#x}: GameFeatureToggles ptr={ptr:#x} NUM={num} MAX={mx}{sample}")
