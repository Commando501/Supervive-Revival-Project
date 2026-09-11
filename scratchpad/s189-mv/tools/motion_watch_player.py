# motion_watch_player.py -- S189-MV-WASD. Read-only RPM. Tight-sample the PLAYER hero
# with CIV BURST-READ defense (per V2 verifier: ControlInputVector is consumed each
# frame by ConsumeMovementInputVector; a single RPM sample can land post-consume and
# read 0 during active input. Solution: burst-read CIV 3x per sample and take the
# max magnitude).
#
# usage: motion_watch_player.py <PID> <HERO-hex> <CMC-hex> [duration-seconds]

import ctypes
import math
import struct
import sys
import time
from ctypes import wintypes

if len(sys.argv) < 4:
    print("usage: motion_watch_player.py <PID> <HERO-hex> <CMC-hex> [duration-seconds]", file=sys.stderr)
    sys.exit(2)

PID = int(sys.argv[1], 0)
HERO = int(sys.argv[2], 16)
CMC = int(sys.argv[3], 16)
DUR = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
SAMPLE_MS = 100
BURST_GAP_MS = 1

# offsets [M]
HERO_ROOT = 0x1B0
HERO_CIV = 0x418
SC_LOC = 0x158
CMC_VEL = 0xE8
CMC_GRAV = 0x1A0
CMC_MODE = 0x231
CMC_ACCEL = 0x328
CMC_ANALOGMOD = 0x3D0  # AnalogInputModifier per S141 T3 [I,strong]
CMC_AIRCTL = 0x2B0  # AirControl [M] UHT prop 29 on UCMC (Falling lateral velocity gate)
CMC_AIRCTLBOOST = 0x2B4  # AirControlBoostMultiplier
CMC_AIRCTLTHR = 0x2B8  # AirControlBoostVelocityThreshold
CMC_FALLLATFR = 0x2BC  # FallingLateralFriction

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("ERR OpenProcess(%d) failed err=%d" % (PID, ctypes.get_last_error()), file=sys.stderr)
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


def u64(a):
    b = rpm(a, 8)
    return int.from_bytes(b, "little") if b else None


def f32(a):
    b = rpm(a, 4)
    return struct.unpack("<f", b)[0] if b else None


def vec3d(a):
    b = rpm(a, 24)
    return struct.unpack("<ddd", b) if b else None


def mag2d(v):
    return math.hypot(v[0], v[1]) if v else None


# Resolve root once (RootComponent is stable while pawn exists).
root = u64(HERO + HERO_ROOT)
if not root:
    print("ERR could not read hero+0x1B0 (RootComponent)", file=sys.stderr)
    sys.exit(3)

print("# motion_watch_player  PID=%d  HERO=0x%X  CMC=0x%X  root=0x%X  duration=%.0fs  cadence=%dms  burst_gap=%dms"
      % (PID, HERO, CMC, root, DUR, SAMPLE_MS, BURST_GAP_MS), file=sys.stderr)
print("# start=%s" % time.strftime("%Y-%m-%d %H:%M:%S"), file=sys.stderr)
print("# NOTE: CIV columns are burst-read x3 per sample (V2 verifier fix for ConsumeMovementInputVector race)", file=sys.stderr)

# CSV header
print("t_sec,t_wall,LocX,LocY,LocZ,VelX,VelY,VelZ,AccX,AccY,AccZ,CIV1x,CIV1y,CIV1z,CIV2x,CIV2y,CIV2z,CIV3x,CIV3y,CIV3z,CIVmaxMag2D,Mode,GravScale,AnalogMod,AirCtl,AirCtlBoost,AirCtlThr,FallLatFr")

t0 = time.time()
first_loc = None
last_loc = None
mode_ever_1 = False
civ_ever_nonzero = False
moved_axes = [False, False, False]
peak_vel_2d = 0.0
peak_accel_2d = 0.0
peak_civ_max = 0.0
n = 0
alive_check_every = 20
sample_i = 0
burst_gap = BURST_GAP_MS / 1000.0

while time.time() - t0 < DUR:
    ts = time.time() - t0
    ts_wall = time.time()
    if sample_i % alive_check_every == 0:
        if u64(HERO + 0x18) is None:
            print("# process died at t=+%.1fs" % ts, file=sys.stderr)
            break
    sample_i += 1

    loc = vec3d(root + SC_LOC)
    vel = vec3d(CMC + CMC_VEL)
    acc = vec3d(CMC + CMC_ACCEL)
    # CIV burst: 3 reads with ~1ms gap between them
    civ1 = vec3d(HERO + HERO_CIV)
    time.sleep(burst_gap)
    civ2 = vec3d(HERO + HERO_CIV)
    time.sleep(burst_gap)
    civ3 = vec3d(HERO + HERO_CIV)

    mode = u8(CMC + CMC_MODE)
    grav = f32(CMC + CMC_GRAV)
    amod = f32(CMC + CMC_ANALOGMOD)
    ac = f32(CMC + CMC_AIRCTL)
    acb = f32(CMC + CMC_AIRCTLBOOST)
    acthr = f32(CMC + CMC_AIRCTLTHR)
    flf = f32(CMC + CMC_FALLLATFR)

    civ_max_mag = 0.0
    for c in (civ1, civ2, civ3):
        if c:
            m = math.hypot(c[0], c[1])
            if m > civ_max_mag:
                civ_max_mag = m
    if civ_max_mag > 1e-6:
        civ_ever_nonzero = True
    if civ_max_mag > peak_civ_max:
        peak_civ_max = civ_max_mag

    if loc:
        if first_loc is None:
            first_loc = loc
        else:
            for i in range(3):
                if abs(loc[i] - first_loc[i]) > 1.0:
                    moved_axes[i] = True
        last_loc = loc

    if vel:
        m = math.hypot(vel[0], vel[1])
        if m > peak_vel_2d:
            peak_vel_2d = m
    if acc:
        m = math.hypot(acc[0], acc[1])
        if m > peak_accel_2d:
            peak_accel_2d = m
    if mode == 1:
        mode_ever_1 = True

    def fv(v):
        return "%.3f,%.3f,%.3f" % v if v else ",,"

    def ff(v):
        return "%.4f" % v if v is not None else ""
    print("%.3f,%.3f,%s,%s,%s,%s,%s,%s,%.4f,%s,%s,%s,%s,%s,%s,%s" % (
        ts, ts_wall,
        fv(loc), fv(vel), fv(acc),
        fv(civ1), fv(civ2), fv(civ3),
        civ_max_mag,
        mode if mode is not None else "",
        ff(grav), ff(amod), ff(ac), ff(acb), ff(acthr), ff(flf),
    ))
    sys.stdout.flush()
    n += 1
    # Compensate for burst time in main sleep
    remaining = (SAMPLE_MS / 1000.0) - (2 * burst_gap)
    if remaining > 0:
        time.sleep(remaining)

print(file=sys.stderr)
print("# SUMMARY (from %d samples over %.1fs)" % (n, time.time() - t0), file=sys.stderr)
if first_loc and last_loc:
    dx = last_loc[0] - first_loc[0]
    dy = last_loc[1] - first_loc[1]
    dz = last_loc[2] - first_loc[2]
    print("# first_loc = (%.3f, %.3f, %.3f)" % first_loc, file=sys.stderr)
    print("# last_loc  = (%.3f, %.3f, %.3f)" % last_loc, file=sys.stderr)
    print("# delta     = (%.3f, %.3f, %.3f)" % (dx, dy, dz), file=sys.stderr)
    print("# moved_axes X=%s Y=%s Z=%s" % tuple("YES" if m else "no" for m in moved_axes), file=sys.stderr)
    print("# peak_vel_2d          = %.3f uu/s" % peak_vel_2d, file=sys.stderr)
    print("# peak_accel_2d        = %.3f uu/s^2" % peak_accel_2d, file=sys.stderr)
    print("# peak_civ_max_mag_2d  = %.4f" % peak_civ_max, file=sys.stderr)
    print("# CIV ever non-zero    = %s" % ("YES" if civ_ever_nonzero else "NO"), file=sys.stderr)
    print("# MovementMode ever=1  = %s" % ("YES" if mode_ever_1 else "NO"), file=sys.stderr)
else:
    print("# NO LOCATION SAMPLES OBTAINED", file=sys.stderr)
