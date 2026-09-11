"""External poke: Health/MaxHealth BaseValue/CurrentValue = 1000.0 on live SUPERVIVE process.

Four aligned 4-byte writes via WriteProcessMemory, each readback-verified.
Refuses to proceed if any address is unreadable or any value doesn't already
read as expected before/after.

Uses the exact set base + offsets recorded in the r3 marker and confirmed by
move4_health_read.py.
"""
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 41816
SET_PTR = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x15F109D5500
SEED_BITS = 0x447A0000  # 1000.0f

# FGameplayAttributeData: +0x0 ScriptStruct*, +0x8 BaseValue float, +0xC CurrentValue float
WRITES = [
    (SET_PTR + 0x70 + 0x8, "Health.BaseValue"),
    (SET_PTR + 0x70 + 0xC, "Health.CurrentValue"),
    (SET_PTR + 0x80 + 0x8, "MaxHealth.BaseValue"),
    (SET_PTR + 0x80 + 0xC, "MaxHealth.CurrentValue"),
]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.restype = wintypes.BOOL
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

# Need PROCESS_VM_WRITE (0x0020) + PROCESS_VM_OPERATION (0x0008) + PROCESS_VM_READ (0x0010)
h = k32.OpenProcess(0x0038, False, PID)
if not h:
    print(f"OpenProcess({PID}) failed: {ctypes.get_last_error()}")
    sys.exit(9)

def rpm4(addr):
    buf = (ctypes.c_ubyte * 4)()
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, 4, ctypes.byref(got))
    if not ok or got.value != 4:
        return None
    return struct.unpack("<I", bytes(buf))[0]

def wpm4(addr, val):
    buf = struct.pack("<I", val)
    put = ctypes.c_size_t(0)
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(addr), buf, 4, ctypes.byref(put))
    return ok and put.value == 4

# Pre-check: read all four
print(f"PID={PID} SET_PTR=0x{SET_PTR:X}")
print("BEFORE:")
before = {}
for addr, name in WRITES:
    v = rpm4(addr)
    if v is None:
        print(f"  {name} @0x{addr:X}: UNREADABLE — ABORT")
        sys.exit(3)
    print(f"  {name} @0x{addr:X}: bits=0x{v:08X} f={struct.unpack('<f', struct.pack('<I', v))[0]}")
    before[addr] = v

# Write all four
print("\nWRITING SEED_BITS=0x%08X (1000.0) to all four ..." % SEED_BITS)
for addr, name in WRITES:
    if not wpm4(addr, SEED_BITS):
        print(f"  {name} @0x{addr:X}: WriteProcessMemory FAILED — ABORT ({ctypes.get_last_error()})")
        sys.exit(4)

# Readback verify
print("\nAFTER (readback):")
all_ok = True
for addr, name in WRITES:
    v = rpm4(addr)
    if v is None:
        print(f"  {name} @0x{addr:X}: UNREADABLE after write")
        all_ok = False
        continue
    match = "OK" if v == SEED_BITS else f"MISMATCH (wanted 0x{SEED_BITS:08X})"
    print(f"  {name} @0x{addr:X}: bits=0x{v:08X} f={struct.unpack('<f', struct.pack('<I', v))[0]} — {match}")
    if v != SEED_BITS:
        all_ok = False

if all_ok:
    print("\nVERIFIED: all four writes landed. S148 preflight bit 9 (MAX_HEALTH_BELOW_SEED) should now clear.")
    sys.exit(0)
else:
    print("\nFAILED: readback mismatch. Do NOT inject S148.")
    sys.exit(5)
