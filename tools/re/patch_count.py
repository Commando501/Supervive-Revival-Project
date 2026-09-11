import ctypes, sys
from ctypes import wintypes

PID = int(sys.argv[1])
SLOT = int(sys.argv[2],16)       # UFunction Func slot (obj+0xE0)
READ = len(sys.argv)>3 and sys.argv[3]=="read"
COUNTER = int(sys.argv[4],16) if len(sys.argv)>4 else 0

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype=wintypes.HANDLE
k32.VirtualAllocEx.restype=ctypes.c_void_p
k32.VirtualAllocEx.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD,wintypes.DWORD]
h=k32.OpenProcess(0x1F0FFF,False,PID)
def rpm(a,n):
    b=(ctypes.c_ubyte*n)();r=ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(r)) or r.value!=n:return None
    return bytes(b)
def wpm(a,d):
    b=(ctypes.c_ubyte*len(d)).from_buffer_copy(d);r=ctypes.c_size_t(0)
    return k32.WriteProcessMemory(h,ctypes.c_void_p(a),b,len(d),ctypes.byref(r)) and r.value==len(d)

if READ:
    print("counter =", int.from_bytes(rpm(COUNTER,8),"little"))
    sys.exit(0)

# counter (8 bytes) at page start; stub after it
region = k32.VirtualAllocEx(h,None,0x1000,0x3000,0x40)
counter = region
stub = region + 0x40
wpm(counter, (0).to_bytes(8,"little"))
# stub: mov rax,counter ; lock inc qword[rax] ; if(r8) *(byte*)r8=1 ; ret
code = bytes([0x48,0xB8])+counter.to_bytes(8,"little")+bytes([0xF0,0x48,0xFF,0x00, 0x4D,0x85,0xC0,0x74,0x04,0x41,0xC6,0x00,0x01,0xC3])
wpm(stub, code)
cur=int.from_bytes(rpm(SLOT,8),"little")
wpm(SLOT, stub.to_bytes(8,"little"))
print(f"counter@0x{counter:X} stub@0x{stub:X} patched slot 0x{SLOT:X} (was 0x{cur:X})")
