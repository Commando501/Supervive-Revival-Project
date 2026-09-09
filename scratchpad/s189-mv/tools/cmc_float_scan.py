# cmc_float_scan.py -- scan CMC memory as float32 and find small-value fields
# (AirControl default 0.05, FallingLateralFriction default 0.0, MaxWalkSpeed usually 600,
#  BrakingFriction 0.0 by default, GroundFriction 8.0, JumpZVelocity 420, etc.)
#
# usage: cmc_float_scan.py <PID> <CMC-hex>

import ctypes
import struct
import sys
from ctypes import wintypes

if len(sys.argv) < 3:
    print("usage: cmc_float_scan.py <PID> <CMC-hex>")
    sys.exit(2)

PID = int(sys.argv[1], 0)
CMC = int(sys.argv[2], 16)
SCAN_BYTES = 0x2000

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("ERR OpenProcess(%d) failed err=%d" % (PID, ctypes.get_last_error()))
    sys.exit(1)

buf = (ctypes.c_ubyte * SCAN_BYTES)()
r = ctypes.c_size_t(0)
ok = k32.ReadProcessMemory(h, ctypes.c_void_p(CMC), buf, SCAN_BYTES, ctypes.byref(r))
if not ok or r.value != SCAN_BYTES:
    print("ERR RPM failed: r=%d" % r.value)
    sys.exit(1)

data = bytes(buf)

# Scan every 4-byte aligned offset
print("Offset  Value          Notes")
print("------  -----          -----")
candidates = []
for off in range(0, SCAN_BYTES, 4):
    v = struct.unpack("<f", data[off:off+4])[0]
    # Filter to interesting small floats
    if v != v:  # NaN
        continue
    if v == 0.0:
        # Only print zeros at known offsets
        continue
    # AirControl range: [0.0, 1.5]
    if 0.001 < v < 1.5 and abs(v) > 1e-30:
        candidates.append((off, v, "small-float"))
    # Other movement values
    elif 100 < v < 3000:
        candidates.append((off, v, "medium-float"))
    elif v in (50000.0, 45000.0, 8.0, 2048.0, 500.0, 90.0, 600.0, 420.0, 384.0, 100.0):
        candidates.append((off, v, "known-value"))

# Sort by offset
for off, v, tag in candidates:
    print("+0x%04X  %-14g %s" % (off, v, tag))

# Also probe specific known offsets from S141 T3
print()
print("=== Known offsets ===")
known = [
    (0xC0, "d", "WorldPrivate ptr"),
    (0xE8, "vec3d", "Velocity"),
    (0x1A0, "f", "GravityScale"),
    (0x231, "b", "MovementMode"),
    (0x290, "f", "MinAnalogWalkSpeed"),
    (0x328, "vec3d", "Acceleration"),
    (0x3D0, "f", "AnalogInputModifier"),
    (0x3E0, "f", "MaxSimulationTimeStep"),
    (0x3E4, "i", "MaxSimulationIterations"),
]
for off, tp, name in known:
    end = off + (24 if tp == "vec3d" else (8 if tp == "d" else (4 if tp in ("f","i") else 1)))
    b = data[off:end]
    if tp == "f":
        val = "%.6f" % struct.unpack("<f", b)[0]
    elif tp == "i":
        val = str(struct.unpack("<i", b)[0])
    elif tp == "b":
        val = str(b[0])
    elif tp == "d":
        val = "0x%X" % struct.unpack("<Q", b)[0]
    elif tp == "vec3d":
        val = str(struct.unpack("<ddd", b))
    print("+0x%04X %s %s" % (off, val.ljust(30), name))
