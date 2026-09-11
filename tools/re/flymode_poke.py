# flymode_poke.py -- S138 flight 9b. Pokes ONE aligned DATA byte, with an A-B-A and controls.
#
# WRITES: <bot CMC> + MovementMode = 5 (MOVE_Flying), then restores the original. Nothing else.
#
# WHY (docs/s138-f9b-PREREGISTERED.txt, written before the first attempt):
#   Flight 8: with the gate legitimately opened, the bot's wander driver RUNS and delivers a fresh
#   direction into ControlInputVector every ~2 s -- and the pawn never moves.
#   Flight 9: MovementMode is NOT the discriminator (bot and player are BOTH MOVE_Falling), but the
#   bot sits in MOVE_Falling with GravityScale=1.0 and Velocity EXACTLY (0,0,0) -- i.e. the movement
#   component is not simulating at all. The player is in the same state and only moves when the
#   `play` shim is injected, which CLAUDE.md records sets KFLYMODE=5 = MOVE_Flying explicitly, "to
#   bypass the Walking-mode ground-mantle chain" ("it hovers; it passes anywhere").
#   The bot already has what the player lacks: a live ControlInputVector. So if the MODE is the only
#   missing piece, setting it should make the bot move.
#
#   usage: flymode_poke.py <PID> <BASE-hex> [--dry] [watch_seconds]
#
# PRE-REGISTERED (unmodified):
#   R1 readback of the poked byte returns 5.
#   R2 the PLAYER's CMC is NOT written and must still read its original mode (specificity control).
#   R3 Velocity becomes non-zero within a few seconds.
#   R4 the pawn's LOCATION CHANGES -- first bot motion in this project.
#   R5 restoring the original mode stops it.
# HONEST ALTERNATIVES, also pre-registered:
#   * If R3/R4 fail with R1 holding, the mode is NOT the blocker either and the standing candidate
#     is that the component/actor does not TICK -- which no poke fixes.
#   * `play` does more than set the mode (it drives input and teleports), so matching only the mode
#     may be insufficient. A null here does NOT show flying is irrelevant.
#
# The verdict is computed from the OBSERVED samples. (Flight 6's tool printed a false "YES" from a
# predicate whose terms were always true; that is not repeated here.)
import ctypes
import struct
import sys
import time
from ctypes import wintypes

DRY = "--dry" in sys.argv
argv = [a for a in sys.argv if not a.startswith("--")]
if len(argv) < 3:
    print("usage: flymode_poke.py <PID> <BASE-hex> [--dry] [watch_seconds]")
    sys.exit(2)
PID = int(argv[1], 0)
BASE = int(argv[2], 16)
WATCH = float(argv[3]) if len(argv) > 3 else 25.0

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF = 0x18, 0x20, 0x48
CHILDPROPS_OFF, FIELD_NEXT, FPROP_OFFSET = 0x58, 0x18, 0x44
CTL_PAWN, CTL_GATE = 0x3F8, 0x6A0
PAWN_CIV, PAWN_ROOT, SC_LOC, PAWN_LS = 0x418, 0x1B0, 0x158, 0x1090
EMOVE = {0: "None", 1: "Walking", 2: "NavWalking", 3: "Falling", 4: "Swimming", 5: "Flying", 6: "Custom"}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)
if not h:
    print("OpenProcess(%d) failed -- err %d. RUN IS VOID." % (PID, ctypes.get_last_error()))
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def wpm(a, data):
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    r = ctypes.c_size_t(0)
    return bool(k32.WriteProcessMemory(h, ctypes.c_void_p(a), buf, len(data), ctypes.byref(r))) and r.value == len(data)


def u32(b, o=0):
    return int.from_bytes(b[o:o + 4], "little")


def u64(b, o=0):
    return int.from_bytes(b[o:o + 8], "little")


def lp(v):
    return 0x10000 < v < 0x7FFFFFFFFFFF


def p(a):
    b = rpm(a, 8)
    return u64(b) if b else 0


def v3(a):
    b = rpm(a, 24)
    return struct.unpack("<ddd", b) if b else None


def b1(a):
    b = rpm(a, 1)
    return b[0] if b else None


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
    return fname(u32(b)) if b else "?"


def ocls(o):
    c = p(o + CLASS_OFF)
    return c if lp(c) else 0


def chain(c):
    out, cur, g = [], c, 0
    while lp(cur) and g < 16:
        out.append(oname(cur))
        cur = p(cur + SUPER_OFF)
        g += 1
    return out


_pc = {}


def findprop(c, want):
    k = (c, want)
    if k in _pc:
        return _pc[k]
    res, cur, g = None, c, 0
    while lp(cur) and g < 16:
        f, i = p(cur + CHILDPROPS_OFF), 0
        while lp(f) and i < 900:
            if oname(f) == want:
                b = rpm(f + FPROP_OFFSET, 4)
                res = u32(b) if b else None
                _pc[k] = res
                return res
            f = p(f + FIELD_NEXT)
            i += 1
        cur = p(cur + SUPER_OFF)
        g += 1
    _pc[k] = res
    return res


def alive():
    return rpm(OBJOBJECTS, 0x18) is not None


print("flymode_poke  PID=%d BASE=0x%X  %s   %s"
      % (PID, BASE, "*** DRY -- NOTHING WRITTEN ***" if DRY else "*** WILL WRITE ONE BYTE ***",
         time.strftime("%Y-%m-%d %H:%M:%S")))

# ---- wait for the bot (i.e. for ARM D/F to have run)
t0 = time.time()
botctl = 0
while time.time() - t0 < 120:
    if not alive():
        print("PROCESS GONE while waiting -- NOT OBTAINED (not a null)."); sys.exit(3)
    hdr = rpm(OBJOBJECTS, 0x18)
    objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
    found = 0
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
            if "LokiBotController" in chain(ocls(o)):
                found = o
                break
        if found:
            break
    if found:
        botctl = found
        break
    time.sleep(1.0)

if not botctl:
    print("no LokiBotController appeared -- STAGING statement, not a result."); sys.exit(3)

botpawn = p(botctl + CTL_PAWN)
cmcoff = findprop(ocls(botpawn), "CharacterMovement")
botcmc = p(botpawn + cmcoff) if cmcoff is not None else 0
mmoff = findprop(ocls(botcmc), "MovementMode") if lp(botcmc) else None
if not lp(botcmc) or mmoff is None:
    print("could not resolve the bot CMC / MovementMode BY NAME -- REFUSING."); sys.exit(4)

# the PLAYER, as the untouched specificity control
plrctl = 0
hdr = rpm(OBJOBJECTS, 0x18)
objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
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
        if "LokiPlayerController" in chain(ocls(o)):
            plrctl = o
            break
    if plrctl:
        break
plrpawn = p(plrctl + CTL_PAWN) if plrctl else 0
plrcmc = p(plrpawn + cmcoff) if lp(plrpawn) else 0

root = p(botpawn + PAWN_ROOT)
print("\nbot  ctl=0x%X pawn=0x%X cmc=0x%X   MovementMode BY NAME @+0x%X" % (botctl, botpawn, botcmc, mmoff))
print("CONTROL player cmc=0x%X (NOT written)" % plrcmc)
velo = findprop(ocls(botcmc), "Velocity")
print("Velocity BY NAME @+0x%s" % ("%X" % velo if velo is not None else "?? -- REFUSING to guess"))
if velo is None:
    sys.exit(4)


def samp(tag):
    mm = b1(botcmc + mmoff)
    pm = b1(plrcmc + mmoff) if lp(plrcmc) else None
    vel = v3(botcmc + velo)
    civ = v3(botpawn + PAWN_CIV)
    loc = v3(root + SC_LOC) if lp(root) else None
    g = b1(botctl + CTL_GATE)
    print("  [%-8s] mode=%-2s(%-9s) gate=%-3s plr_mode=%-3s Vel=%-30s CIV=%-26s loc=%s"
          % (tag, mm, EMOVE.get(mm, "?"), g, pm,
             ("(%.3f,%.3f,%.3f)" % vel) if vel else "??",
             ("(%.3f,%.3f,%.3f)" % civ) if civ else "??",
             ("(%.1f,%.1f,%.1f)" % loc) if loc else "??"))
    return (mm, pm, vel, loc)


print("\n== A BASELINE ==")
a = samp("A")
orig = a[0]
plr_orig = a[1]
if DRY:
    print("\n--dry: would write 5 to 0x%X. NOTHING WRITTEN." % (botcmc + mmoff)); sys.exit(0)

print("\n== B POKE bot CMC MovementMode = 5 (MOVE_Flying) ==")
ok = wpm(botcmc + mmoff, bytes([5]))
back = b1(botcmc + mmoff)
print("  write ok=%s READBACK=%s" % (ok, back))
if not ok or back != 5:
    print("  *** R1 FAILED -- nothing downstream is interpretable. ***"); sys.exit(4)
print("  R1 HOLDS.")
samples, t1 = [], time.time()
while time.time() - t1 < WATCH:
    if not alive():
        print("  *** PROCESS GONE at +%.1fs -- samples above remain valid. ***" % (time.time() - t1)); break
    samples.append(samp("B+%.0fs" % (time.time() - t1)))
    time.sleep(1.0)

print("\n== C RESTORE MovementMode = %s ==" % orig)
if alive():
    wpm(botcmc + mmoff, bytes([orig]))
    print("  READBACK=%s" % b1(botcmc + mmoff))
    time.sleep(1.5)
    samp("C")

print("\n" + "=" * 104)
print("VERDICT  (computed from the %d observed B samples)" % len(samples))
print("=" * 104)
vels = [s[2] for s in samples if s[2]]
locs = [s[3] for s in samples if s[3]]
vel_nz = any(abs(v[0]) + abs(v[1]) + abs(v[2]) > 1e-6 for v in vels)
moved = bool(locs) and a[3] is not None and any(
    any(abs(l[i] - a[3][i]) > 1.0 for i in range(3)) for l in locs)
plr_held = all(s[1] == plr_orig for s in samples if s[1] is not None)
print("  R1 poke landed (readback==5)                : YES")
print("  R2 PLAYER mode untouched (was %s)            : %s" % (plr_orig, "YES" if plr_held else "*** NO -- RUN VOID ***"))
print("  R3 Velocity ever non-zero                   : %s" % ("YES" if vel_nz else "NO"))
print("  R4 pawn LOCATION changed (>1 uu)            : %s" % ("YES  ***** THE BOT MOVED *****" if moved else "NO"))
print()
if moved:
    print("  ***** FIRST BOT MOTION IN THIS PROJECT. Confirm with an independent read before")
    print("        claiming it, and note this required a forced MovementMode -- the game does not")
    print("        do this by itself. *****")
elif vel_nz:
    print("  Velocity moved but position did not: the body is being simulated now but something")
    print("  still pins it (collision, or a zero delta). Read Velocity magnitude and UpdatedComponent.")
else:
    print("  Mode is NOT the blocker either. Per the pre-registration this leaves the standing")
    print("  candidate: the component/actor does not TICK -- which no poke fixes. The next read is")
    print("  the component tick registration and the actor tick state, not another poke.")
