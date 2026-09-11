# poke_float.py -- external WriteProcessMemory poke of a single float32, with readback verify.
# ⚠ External RPM WPM has a ~1-in-3.4-per-15min hazard per S138. Use sparingly.
#
# usage: poke_float.py <PID> <ABS-ADDR-hex> <FLOAT-VALUE> [--dry]

import ctypes
import struct
import sys
from ctypes import wintypes

if len(sys.argv) < 4:
    print("usage: poke_float.py <PID> <ABS-ADDR-hex> <FLOAT-VALUE> [--dry]")
    sys.exit(2)

PID = int(sys.argv[1], 0)
ADDR = int(sys.argv[2], 16)
VAL = float(sys.argv[3])
DRY = ("--dry" in sys.argv)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
# Need VM_WRITE + VM_OPERATION for WPM
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("ERR OpenProcess(%d) failed err=%d" % (PID, ctypes.get_last_error()))
    sys.exit(1)

# Read current
b = (ctypes.c_ubyte * 4)()
r = ctypes.c_size_t(0)
if not k32.ReadProcessMemory(h, ctypes.c_void_p(ADDR), b, 4, ctypes.byref(r)) or r.value != 4:
    print("ERR RPM read failed")
    sys.exit(3)
cur = struct.unpack("<f", bytes(b))[0]
cur_bits = int.from_bytes(bytes(b), "little")
new_bits = int.from_bytes(struct.pack("<f", VAL), "little")
print(f"BEFORE  addr=0x{ADDR:X}  current={cur:.6f} (bits=0x{cur_bits:08X})  target={VAL:.6f} (bits=0x{new_bits:08X})")

if DRY:
    print("DRY-RUN: skipping write")
    sys.exit(0)

# WriteProcessMemory
newb = struct.pack("<f", VAL)
buf = (ctypes.c_ubyte * 4).from_buffer_copy(newb)
w = ctypes.c_size_t(0)
if not k32.WriteProcessMemory(h, ctypes.c_void_p(ADDR), buf, 4, ctypes.byref(w)) or w.value != 4:
    print("ERR WPM failed err=%d" % ctypes.get_last_error())
    sys.exit(4)
print(f"WROTE   {w.value} bytes")

# Readback
if not k32.ReadProcessMemory(h, ctypes.c_void_p(ADDR), b, 4, ctypes.byref(r)) or r.value != 4:
    print("ERR RPM readback failed")
    sys.exit(5)
back = struct.unpack("<f", bytes(b))[0]
back_bits = int.from_bytes(bytes(b), "little")
print(f"AFTER   readback={back:.6f} (bits=0x{back_bits:08X})")
if back_bits == new_bits:
    print("PASS: readback matches target")
else:
    print("FAIL: readback MISMATCH")
    sys.exit(6)
