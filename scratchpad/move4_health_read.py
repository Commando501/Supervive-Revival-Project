"""Read the S148 health target's Health/MaxHealth BaseValue/CurrentValue from a live game process.

Read-only RPM. Uses the pointer + offsets recorded in the S148 marker to avoid re-doing
the SpawnedAttributes census.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
SET_PTR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x15F109D5500
HEALTH_OFF = 0x70
MAXHEALTH_OFF = 0x80

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

h = k32.OpenProcess(0x0410, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

def rpm(addr, n):
    buf = (ctypes.c_ubyte * n)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
    if not ok:
        return None
    return bytes(buf[:got.value])

def read_attr(base, off, name):
    # FGameplayAttributeData: +0x0 ScriptStruct*, +0x8 BaseValue float, +0xC CurrentValue float
    b = rpm(base + off, 16)
    if not b:
        print(f"  {name}@0x{off:X}: UNREADABLE")
        return
    struct_ptr = struct.unpack("<Q", b[0:8])[0]
    base_val = struct.unpack("<f", b[8:12])[0]
    curr_val = struct.unpack("<f", b[12:16])[0]
    base_bits = struct.unpack("<I", b[8:12])[0]
    curr_bits = struct.unpack("<I", b[12:16])[0]
    print(f"  {name}@0x{off:X}: struct=0x{struct_ptr:X} Base={base_val} (bits={base_bits:08X}) Current={curr_val} (bits={curr_bits:08X})")

print(f"PID={PID} SET_PTR=0x{SET_PTR:X}")
read_attr(SET_PTR, HEALTH_OFF, "Health")
read_attr(SET_PTR, MAXHEALTH_OFF, "MaxHealth")
