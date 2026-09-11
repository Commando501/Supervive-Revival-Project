# S140 Tier 2 follow-up: the THIRD term of lane 5's CalcVelocity clamp.
#   MaxInputSpeed = max( GetMaxSpeed() * AnalogInputModifier , GetMinAnalogSpeed() )
#   and CalcVelocity writes Velocity := (0,0,0) when MaxInputSpeed < 1.0e-4.
# AnalogInputModifier @CMC+0x3D0 is already in cmc_earlyout_readout.py and reads 1 on the
# ARM-G-treated bot / 0 on the untreated player.  GetMinAnalogSpeed() (vt disp 0x7C8 ->
# 0x035E3D20, NOT overridden) returns MinAnalogWalkSpeed @CMC+0x290 for MovementMode in
# {1,2,3} -- and this build's bot and player are both MOVE_Falling(3), which is in that set.
# NOBODY HAS EVER READ +0x290 LIVE.  Read-only RPM; no injection, no write.
#   usage: minanalog.py <PID> <BASE-hex> <BOT-CMC-hex> <PLAYER-CMC-hex>
import ctypes, struct, sys
from ctypes import wintypes

PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 0)
CMCS = [("BOT", int(sys.argv[3], 0)), ("PLAYER", int(sys.argv[4], 0))]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess failed -- RUN IS VOID"); sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def f32(a):
    b = rpm(a, 4); return struct.unpack("<f", b)[0] if b else None


def u8(a):
    b = rpm(a, 1); return b[0] if b else None


def v3(a):
    b = rpm(a, 24); return struct.unpack("<ddd", b) if b else None


FIELDS = [
    ("MinAnalogWalkSpeed@0x290", 0x290, f32),      # GetMinAnalogSpeed()'s return for modes 1/2/3
    ("MaxAcceleration@0x28C",    0x28C, f32),      # neighbour -- POSITIVE CONTROL, must read 50000
    ("MaxWalkSpeed@0x294",       0x294, f32),      # neighbourhood, for orientation only
    ("AnalogInputModifier@0x3D0", 0x3D0, f32),
    ("GravityScale@0x1A8?",      0x1A8, f32),
]
print("=" * 96)
print("S140 Tier 2 follow-up -- lane 5's CalcVelocity clamp, third term.  PID=%d BASE=0x%X" % (PID, BASE))
print("  Velocity := (0,0,0) every frame iff MaxInputSpeed < 1.0e-4")
print("  MaxInputSpeed = max( GetMaxSpeed() * AnalogInputModifier , MinAnalogWalkSpeed )")
print("=" * 96)
for tag, cmc in CMCS:
    print("--- %s  CMC=0x%X ---" % (tag, cmc))
    # identity control first: CharacterOwner must be a plausible pointer, vptr must be ULokiCMC
    vptr = struct.unpack("<Q", rpm(cmc, 8))[0] if rpm(cmc, 8) else 0
    ok = (vptr == BASE + 0x088F8570)
    print("  CONTROL vptr=0x%X  isULokiCMC=%s" % (vptr, "YES" if ok else "*** NO -- VOID ***"))
    if not ok:
        continue
    for name, off, rd in FIELDS:
        print("  %-28s = %s" % (name, rd(cmc + off)))
    print("  MovementMode@0x231           = %s   (3 = MOVE_Falling; GetMinAnalogSpeed returns"
          " MinAnalogWalkSpeed for modes 1/2/3)" % u8(cmc + 0x231))
    print("  Velocity@0xE8                = %s" % (v3(cmc + 0xE8),))
    print("  Acceleration@0x328           = %s" % (v3(cmc + 0x328),))
print()
print("READ IT AS -- and note what this can and cannot settle:")
print("  MinAnalogWalkSpeed >= 1e-4  ==> the max() cannot be below 1e-4, so lane 5's clamp CANNOT")
print("      be zeroing Velocity, and the wall is somewhere else. That REFUTES the lane's headline.")
print("  MinAnalogWalkSpeed <  1e-4  ==> the clamp fires iff GetMaxSpeed()*AnalogInputModifier is")
print("      also < 1e-4. AnalogInputModifier is measured 1 on the treated bot, so it reduces to")
print("      GetMaxSpeed(), WHICH THIS PROBE DOES NOT READ. Not settled -- name it and stop.")
print("  MaxAcceleration@0x28C must read 50000 or the offsets in this probe are wrong (control).")
