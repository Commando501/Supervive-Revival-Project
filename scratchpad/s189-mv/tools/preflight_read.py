# preflight_read.py -- S189-MV-WASD pre-flight state check. Read-only RPM.
#
# Reads the player hero's key state:
#   hero +0x1B0  RootComponent (USceneComponent*)
#     +0x158     RelativeLocation (FVector = 3x double)
#   hero +0x418  ControlInputVector (FVector = 3x double)  -- S138
#   hero +0xF00  ASC storage
#   hero +0xF08  AttributeSet storage (S189-MV wire target)
#   hero +0x1090 LivingState (byte)
#   CMC (discovered via hero +0x??? CharacterMovement UPROPERTY) +0xE8  Velocity
#   CMC +0x328   Acceleration
#   CMC +0x231   MovementMode (byte)
#   CMC +0x1A0   GravityScale (float)
#   CMC +0xC0    WorldPrivate
#
# usage: preflight_read.py <PID> <BASE-hex> <HERO-hex> [CMC-hex]
#
# If CMC not passed, we read it from a discovered UPROPERTY. But easier: pass it
# explicitly since we know 0x193108438F0 from the S189-MV marker.

import ctypes
import struct
import sys
from ctypes import wintypes

if len(sys.argv) < 4:
    print("usage: preflight_read.py <PID> <BASE-hex> <HERO-hex> [CMC-hex]")
    sys.exit(2)

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
HERO = int(sys.argv[3], 16)
CMC = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0

# offsets [M] per CLAUDE.md / S138 / S141 T3 / S189-MV
HERO_ROOT = 0x1B0
HERO_CIV = 0x418
HERO_ASC = 0xF00
HERO_F08 = 0xF08
HERO_LS = 0x1090
SC_LOC = 0x158
CMC_WORLD = 0xC0
CMC_VEL = 0xE8
CMC_GRAV = 0x1A0
CMC_MODE = 0x231
CMC_ACCEL = 0x328

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("ERR OpenProcess(%d) failed err=%d" % (PID, ctypes.get_last_error()))
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u8(a):
    b = rpm(a, 1)
    return b[0] if b else None


def u32(a):
    b = rpm(a, 4)
    return int.from_bytes(b, "little") if b else None


def u64(a):
    b = rpm(a, 8)
    return int.from_bytes(b, "little") if b else None


def f32(a):
    b = rpm(a, 4)
    return struct.unpack("<f", b)[0] if b else None


def vec3d(a):
    """FVector as 3x double, UE5.4."""
    b = rpm(a, 24)
    return struct.unpack("<ddd", b) if b else None


def fmt_vec(v):
    return "(%.3f, %.3f, %.3f)" % v if v else "??"


print("=== PRE-FLIGHT S189-MV-WASD ===")
print("PID=%d BASE=0x%X HERO=0x%X CMC=0x%X" % (PID, BASE, HERO, CMC))
print()

# HERO validity check
hero_class = u64(HERO + 0x18)
print("hero+0x18 (class)     = 0x%X %s" % (hero_class or 0, "OK" if hero_class else "-- READ FAILED"))

# HERO fields
root = u64(HERO + HERO_ROOT)
asc = u64(HERO + HERO_ASC)
attrset = u64(HERO + HERO_F08)
ls = u8(HERO + HERO_LS)
civ = vec3d(HERO + HERO_CIV)

print("hero+0x1B0 RootComp   = 0x%X" % (root or 0))
print("hero+0xF00 ASC        = 0x%X %s" % (asc or 0, "-- WIRED (KWIREGAS)" if asc else "-- NULL"))
print("hero+0xF08 AttrSet    = 0x%X %s" % (attrset or 0, "-- S189-MV WIRED" if attrset else "-- NULL (S189-MV wire missing!)"))
print("hero+0x1090 LivingSt  = %s" % ls)
print("hero+0x418 ControlInputVector = %s" % fmt_vec(civ))

# LOCATION
if root:
    loc = vec3d(root + SC_LOC)
    print("root+0x158 Location   = %s" % fmt_vec(loc))

print()

# CMC fields
if CMC:
    cmc_class = u64(CMC + 0x18)
    world = u64(CMC + CMC_WORLD)
    grav = f32(CMC + CMC_GRAV)
    mode = u8(CMC + CMC_MODE)
    vel = vec3d(CMC + CMC_VEL)
    accel = vec3d(CMC + CMC_ACCEL)

    print("cmc+0x18 (class)     = 0x%X" % (cmc_class or 0))
    print("cmc+0xC0 World       = 0x%X" % (world or 0))
    print("cmc+0x1A0 GravityScale = %s" % (("%.4f" % grav) if grav is not None else "??"))
    print("cmc+0x231 MovementMode = %s (0=None 1=Walking 3=Falling 5=Flying)" % mode)
    print("cmc+0xE8 Velocity     = %s" % fmt_vec(vel))
    print("cmc+0x328 Acceleration= %s" % fmt_vec(accel))
else:
    print("(CMC not passed; skipping CMC fields)")

print()
print("=== END PRE-FLIGHT ===")
