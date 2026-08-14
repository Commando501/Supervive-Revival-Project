# Dump an FString[] table out of live memory.  usage: fstr_table.py PID BASE RVA COUNT
import ctypes,sys
from ctypes import wintypes
PID=int(sys.argv[1],0); BASE=int(sys.argv[2],16); RVA=int(sys.argv[3],16); N=int(sys.argv[4])
k32=ctypes.WinDLL("kernel32",use_last_error=True); k32.OpenProcess.restype=wintypes.HANDLE
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)(); r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n: return None
    return bytes(b)
def u64(b,o): return int.from_bytes(b[o:o+8],"little")
def u32(b,o): return int.from_bytes(b[o:o+4],"little")
blk=rpm(BASE+RVA,N*16)
if not blk: sys.exit("read failed")
for i in range(N):
    p,num,mx=u64(blk,i*16),u32(blk,i*16+8),u32(blk,i*16+12)
    s=""
    if p and 0<num<256:
        d=rpm(p,num*2)
        if d: s="".join(chr(d[j*2]|(d[j*2+1]<<8)) for j in range(num)).rstrip("\x00")
    print(f"  [{i:2d}] +0x{RVA+i*16:X}  ptr=0x{p:X} num={num} max={mx}  {s!r}")
