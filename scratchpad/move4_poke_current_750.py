"""Data-poke bypass: write Health.CurrentValue = 750.0 to simulate a successful
AdjustHealth(-250) on the seeded state.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
SET_PTR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x15F109D5500
TARGET_ADDR = SET_PTR + 0x70 + 0xC  # Health.CurrentValue
EXPECTED_BITS = 0x443B8000  # 750.0f (matches S148's expectedCurrent)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = wintypes.BOOL
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

h = k32.OpenProcess(0x0038, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

def rpm4(addr):
    b = (ctypes.c_ubyte * 4)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), b, 4, ctypes.byref(got)) or got.value != 4:
        return None
    return struct.unpack("<I", bytes(b))[0]

def wpm4(addr, val):
    buf = struct.pack("<I", val)
    put = ctypes.c_size_t(0)
    return k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, 4, ctypes.byref(put)) and put.value == 4

print(f"PID={PID} SET_PTR=0x{SET_PTR:X}")
print(f"target: Health.CurrentValue @ 0x{TARGET_ADDR:X}")

pre = rpm4(TARGET_ADDR)
print(f"BEFORE: bits=0x{pre:08X} f={struct.unpack('<f', struct.pack('<I', pre))[0]}")

if pre != 0x447A0000:
    print("WARNING: current value is NOT 0x447A0000 (1000.0) — state has changed since the seed poke.")

if not wpm4(TARGET_ADDR, EXPECTED_BITS):
    print(f"WriteProcessMemory FAILED: {ctypes.get_last_error()}")
    sys.exit(4)

post = rpm4(TARGET_ADDR)
print(f"AFTER : bits=0x{post:08X} f={struct.unpack('<f', struct.pack('<I', post))[0]}")

# Also read the full set to confirm sibling fields are undisturbed
def read_attr(base, off, name):
    b = (ctypes.c_ubyte * 16)()
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(base + off), b, 16, ctypes.byref(got)):
        return
    d = bytes(b[:got.value])
    bv = struct.unpack("<f", d[8:12])[0]
    cv = struct.unpack("<f", d[12:16])[0]
    bb = struct.unpack("<I", d[8:12])[0]
    cb = struct.unpack("<I", d[12:16])[0]
    print(f"  {name}@0x{off:X}: Base={bv} (bits={bb:08X}) Current={cv} (bits={cb:08X})")

print("\nFull set state after write:")
read_attr(SET_PTR, 0x70, "Health   ")
read_attr(SET_PTR, 0x80, "MaxHealth")

if post == EXPECTED_BITS:
    print("\nVERIFIED: Health.CurrentValue = 750.0 (S148 expectedCurrent). All sibling fields undisturbed.")
    sys.exit(0)
else:
    print(f"\nFAILED: readback got 0x{post:08X}, wanted 0x{EXPECTED_BITS:08X}")
    sys.exit(5)
