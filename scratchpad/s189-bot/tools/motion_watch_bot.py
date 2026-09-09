# motion_watch_bot.py -- S189-BOT. Read-only RPM. Tight-sample an AI-controlled bot pawn.
#
# Auto-discovers the bot: polls GUObjectArray until a live LokiBotController exists (i.e. until
# ARM D has spawned the treatment bot), takes controller+0x3F8 = pawn, pawn+0x458 = CMC (validated
# by CMC+0x198 CharacterOwner == pawn, the same CONTROL1 the shim's ShResolveCmc uses), then samples
# every 100 ms exactly like scratchpad/s189-mv/tools/motion_watch_player.py, PLUS the bot-only
# chain fields (controller gate +0x6A0, RandomMoveDirection +0x658, LivingState +0x1090).
#
# Start it BEFORE the probe is injected (it waits for the bot); it exits cleanly when the process
# dies, saying so, so the samples already printed remain valid.
#
# usage: motion_watch_bot.py <PID> <BASE-hex> [duration-seconds] [--pawn <hex> --cmc <hex>]
#   --pawn/--cmc skip discovery and sample a given pawn (e.g. the PLAYER hero, for a 2nd instance).
#
# Offsets [M] (S137/S138/S141/S189-MV): CTL_PAWN 0x3F8, CTL_GATE 0x6A0, CTL_RAND 0x658,
#   PAWN_ROOT 0x1B0, PAWN_CIV 0x418, PAWN_F08 0xF08, PAWN_LS 0x1090, PAWN_CMC 0x458, SC_LOC 0x158,
#   CMC_VEL 0xE8, CMC_GRAV 0x1A0, CMC_MODE 0x231, CMC_ACCEL 0x328, CMC_ANALOGMOD 0x3D0,
#   CMC_OWNER 0x198, CMC_TSFS 0x12B0.
import ctypes
import math
import struct
import sys
import time
from ctypes import wintypes

args = [a for a in sys.argv[1:]]
opt_pawn = 0
opt_cmc = 0
if "--pawn" in args:
    i = args.index("--pawn"); opt_pawn = int(args[i + 1], 16); del args[i:i + 2]
if "--cmc" in args:
    i = args.index("--cmc"); opt_cmc = int(args[i + 1], 16); del args[i:i + 2]
if len(args) < 2:
    print("usage: motion_watch_bot.py <PID> <BASE-hex> [duration-seconds] [--pawn <hex> --cmc <hex>]", file=sys.stderr)
    sys.exit(2)
PID = int(args[0], 0)
BASE = int(args[1], 16)
DUR = float(args[2]) if len(args) > 2 else 120.0
SAMPLE_MS = 100
BURST_GAP_MS = 1

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF = 0x18, 0x20, 0x48

CTL_PAWN, CTL_GATE, CTL_RAND = 0x3F8, 0x6A0, 0x658
PAWN_ROOT, PAWN_CIV, PAWN_F08, PAWN_LS, PAWN_CMC = 0x1B0, 0x418, 0xF08, 0x1090, 0x458
SC_LOC = 0x158
CMC_VEL, CMC_GRAV, CMC_MODE, CMC_ACCEL, CMC_ANALOGMOD, CMC_OWNER, CMC_TSFS = 0xE8, 0x1A0, 0x231, 0x328, 0x3D0, 0x198, 0x12B0

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("ERR OpenProcess(%d) failed err=%d -- RUN IS VOID" % (PID, ctypes.get_last_error()), file=sys.stderr)
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32b(b, o=0):
    return int.from_bytes(b[o:o + 4], "little")


def u64b(b, o=0):
    return int.from_bytes(b[o:o + 8], "little")


def lp(v):
    return 0x10000 < v < 0x7FFFFFFFFFFF


def p(a):
    b = rpm(a, 8)
    return u64b(b) if b else 0


def u8(a):
    b = rpm(a, 1)
    return b[0] if b else None


def f32(a):
    b = rpm(a, 4)
    return struct.unpack("<f", b)[0] if b else None


def vec3d(a):
    b = rpm(a, 24)
    return struct.unpack("<ddd", b) if b else None


_nc = {}


def fname(i):
    if i in _nc:
        return _nc[i]
    blk, off = i >> 16, (i & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk * 8, 8)
    r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if lp(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little")
                ln, w = hd >> 6, hd & 1
                if 0 < ln < 250:
                    s = rpm(bp + off + 2, ln * (2 if w else 1))
                    if s:
                        r = ("".join(chr(s[k * 2] | (s[k * 2 + 1] << 8)) for k in range(ln))
                             if w else s.decode("latin1", "replace"))
    _nc[i] = r
    return r


def oname(o):
    b = rpm(o + NAME_OFF, 4)
    return fname(u32b(b)) if b else "?"


def alive():
    return rpm(OBJOBJECTS, 0x18) is not None


def find_bot_controllers():
    """One GUObjectArray pass. Returns every live LokiBotController-chain object (not CDO)."""
    out = []
    hdr = rpm(OBJOBJECTS, 0x18)
    if not hdr:
        return out
    objptr, numEl = u64b(hdr, 0), u32b(hdr, 0x14)
    if not lp(objptr) or not (0 < numEl < 8000000):
        return out
    for ci in range((numEl + PERCHUNK - 1) // PERCHUNK):
        chunk = p(objptr + ci * 8)
        if not lp(chunk):
            continue
        for j in range(min(PERCHUNK, numEl - ci * PERCHUNK)):
            o = p(chunk + j * STRIDE)
            if not lp(o):
                continue
            nm = oname(o)
            if nm.startswith("Default__") or "_GEN_VARIABLE" in nm:
                continue
            c = p(o + CLASS_OFF)
            cur, g = c, 0
            while lp(cur) and g < 16:
                if oname(cur) == "LokiBotController":
                    out.append(o)
                    break
                cur = p(cur + SUPER_OFF)
                g += 1
    return out


def mag2d(v):
    return math.hypot(v[0], v[1]) if v else 0.0


t0 = time.time()
ctl = 0
pawn = opt_pawn
if not pawn:
    print("# motion_watch_bot PID=%d BASE=0x%X waiting for a live LokiBotController (ARM D)..." % (PID, BASE), file=sys.stderr)
    while time.time() - t0 < DUR:
        if not alive():
            print("# *** PROCESS GONE while waiting for the bot -- NOT OBTAINED (not a null) ***", file=sys.stderr)
            sys.exit(3)
        ctls = find_bot_controllers()
        if ctls:
            ctl = ctls[-1]
            pawn = p(ctl + CTL_PAWN)
            if len(ctls) > 1:
                print("# NOTE: %d LokiBotControllers live; using the last one found 0x%X" % (len(ctls), ctl), file=sys.stderr)
            if lp(pawn):
                break
        time.sleep(1.0)
    if not lp(pawn):
        print("# *** no LokiBotController with a pawn within %.0fs -- STAGING statement, not a result ***" % DUR, file=sys.stderr)
        sys.exit(3)

cmc = opt_cmc or p(pawn + PAWN_CMC)
root = p(pawn + PAWN_ROOT)
owner = p(cmc + CMC_OWNER) if lp(cmc) else 0
cmc_ok = (owner == pawn)
print("# motion_watch_bot ctl=0x%X pawn=0x%X (%s) cmc=0x%X root=0x%X CONTROL1 CharacterOwner==pawn -> %s  found at t=+%.1fs"
      % (ctl, pawn, oname(pawn), cmc, root, "PASS" if cmc_ok else "*** FAIL (CMC not validated; velocity columns UNTRUSTED) ***",
         time.time() - t0), file=sys.stderr)
if not lp(root):
    print("# ERR root component unreadable -- RUN IS VOID for location", file=sys.stderr)

print("t_sec,t_wall,LocX,LocY,LocZ,VelX,VelY,VelZ,Vel2D,AccX,AccY,AccZ,Acc2D,CIVmaxMag2D,Mode,GravScale,AnalogMod,TSFS,Gate,Living,F08,RandX,RandY")
burst_gap = BURST_GAP_MS / 1000.0
first_loc = None
last_loc = None
peak_vel_2d = 0.0
peak_vel_2d_walking = 0.0
mode_ever_1 = False
n = 0
n_mode1 = 0
n_vel_gt400_mode1 = 0
dir_changes = 0
last_dir = None
si = 0
while time.time() - t0 < DUR:
    ts = time.time() - t0
    if si % 20 == 0 and not alive():
        print("# process died at t=+%.1fs -- samples above still stand" % ts, file=sys.stderr)
        break
    si += 1
    loc = vec3d(root + SC_LOC) if lp(root) else None
    vel = vec3d(cmc + CMC_VEL)
    acc = vec3d(cmc + CMC_ACCEL)
    civ1 = vec3d(pawn + PAWN_CIV); time.sleep(burst_gap)
    civ2 = vec3d(pawn + PAWN_CIV); time.sleep(burst_gap)
    civ3 = vec3d(pawn + PAWN_CIV)
    civm = max(mag2d(c) for c in (civ1, civ2, civ3))
    mode = u8(cmc + CMC_MODE)
    grav = f32(cmc + CMC_GRAV)
    amod = f32(cmc + CMC_ANALOGMOD)
    tsfs = f32(cmc + CMC_TSFS)
    gate = u8(ctl + CTL_GATE) if ctl else None
    living = u8(pawn + PAWN_LS)
    f08 = p(pawn + PAWN_F08)
    rnd = vec3d(ctl + CTL_RAND) if ctl else None
    v2 = mag2d(vel)
    a2 = mag2d(acc)
    if loc:
        if first_loc is None:
            first_loc = loc
        last_loc = loc
    if v2 > peak_vel_2d:
        peak_vel_2d = v2
    if mode == 1:
        mode_ever_1 = True
        n_mode1 += 1
        if v2 > peak_vel_2d_walking:
            peak_vel_2d_walking = v2
        if v2 > 400.0:
            n_vel_gt400_mode1 += 1
    if acc and a2 > 1000.0:
        d = (acc[0] / a2, acc[1] / a2)
        if last_dir is not None and (d[0] * last_dir[0] + d[1] * last_dir[1]) < 0.9:
            dir_changes += 1
        last_dir = d

    def fv(v):
        return "%.3f,%.3f,%.3f" % v if v else ",,"

    def ff(v):
        return "%.4f" % v if v is not None else ""
    print("%.3f,%.3f,%s,%s,%.3f,%s,%.1f,%.4f,%s,%s,%s,%s,%s,%s,%s,%s" % (
        ts, time.time(), fv(loc), fv(vel), v2, fv(acc), a2, civm,
        mode if mode is not None else "", ff(grav), ff(amod), ff(tsfs),
        gate if gate is not None else "", living if living is not None else "",
        "0x%X" % f08, ("%.3f" % rnd[0]) if rnd else "", ("%.3f" % rnd[1]) if rnd else ""))
    sys.stdout.flush()
    n += 1
    rem = SAMPLE_MS / 1000.0 - 2 * burst_gap
    if rem > 0:
        time.sleep(rem)

print(file=sys.stderr)
print("# SUMMARY (%d samples over %.1fs)" % (n, time.time() - t0), file=sys.stderr)
if first_loc and last_loc:
    dx, dy, dz = (last_loc[i] - first_loc[i] for i in range(3))
    print("# first_loc = (%.3f, %.3f, %.3f)" % first_loc, file=sys.stderr)
    print("# last_loc  = (%.3f, %.3f, %.3f)" % last_loc, file=sys.stderr)
    print("# delta     = (%.3f, %.3f, %.3f)  horiz=%.1f uu" % (dx, dy, dz, math.hypot(dx, dy)), file=sys.stderr)
print("# peak_vel_2d (any mode)   = %.3f uu/s" % peak_vel_2d, file=sys.stderr)
print("# peak_vel_2d (Mode==1)    = %.3f uu/s" % peak_vel_2d_walking, file=sys.stderr)
print("# samples Mode==1          = %d   (of which |V2D|>400: %d)" % (n_mode1, n_vel_gt400_mode1), file=sys.stderr)
print("# Acceleration direction changes (>~25 deg between consecutive samples with |Acc|>1000) = %d" % dir_changes, file=sys.stderr)
print("# R-S189-MV-WASD-i: peak_vel_2d == seeded MoveSpeed bit-exact is THE discriminator; direction changes + |Acc|~50000 rotating = AI steering", file=sys.stderr)
