# motion_watch.py -- S138 flight 8. Read-only RPM. Watches the bot motion chain CONTINUOUSLY.
#
# WHY THIS EXISTS. Flight 7's ARM F opened the gate legitimately (LivingState=Alive ->
# UpdateCharacterControllable -> bCharacterControllable 0->1) and the client died SECONDS LATER,
# before the motion chain could be read from that state. The observation was missed by seconds.
#
# The fix is ordering: start the reader BEFORE the injection. This tool
#   1. polls the GUObjectArray until a LokiBotController appears (i.e. until ARM D has run),
#   2. then TIGHT-SAMPLES the whole motion chain every ~0.5 s and prints each sample with a
#      timestamp, so the post-ARM-F window is captured even if the process dies moments later,
#   3. exits cleanly the instant the process goes away, saying so, rather than printing an artifact.
#
# THE CHAIN, all read-only (offsets [M], S137/S138):
#   controller +0x6A0  bCharacterControllable       <- THE GATE (ARM F sets this)
#   controller +0x602  ForceCharacterNotControllable
#   controller +0x658  RandomMoveDirection          <- re-randomised every 2.0 s by Tick's wander
#   controller +0x4B0  Blackboard                   <- the NAMED remaining candidate precondition
#   pawn       +0x1090 LivingState (ELivingState: Dead=0 Alive=1 Knocked=2)
#   pawn       +0x418  ControlInputVector           <- the motor's OUTPUT
#   pawn ->RootComponent(+0x1B0) +0x158 RelativeLocation   <- does it actually MOVE?
#
#   usage: motion_watch.py <PID> <BASE-hex> [seconds]      (default 90)
#
# ⚠ A sample where the gate is 0 says nothing about motion -- the gate is a precondition. Read the
#   GATE column first, then the rest. And a still location while the gate is 0 is EXPECTED.
import ctypes
import struct
import sys
import time
from ctypes import wintypes

if len(sys.argv) < 3:
    print("usage: motion_watch.py <PID> <BASE-hex> [seconds]")
    sys.exit(2)
PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)
DUR = float(sys.argv[3]) if len(sys.argv) > 3 else 90.0

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF = 0x18, 0x20, 0x48

CTL_PAWN, CTL_FORCE, CTL_BB, CTL_RAND, CTL_GATE = 0x3F8, 0x602, 0x4B0, 0x658, 0x6A0
PAWN_LS, PAWN_CIV, PAWN_ROOT, SC_LOC = 0x1090, 0x418, 0x1B0, 0x158

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


def alive():
    return rpm(OBJOBJECTS, 0x18) is not None


def find_bot():
    """One GUObjectArray pass. Returns the first LokiBotController-chain object, or 0."""
    hdr = rpm(OBJOBJECTS, 0x18)
    if not hdr:
        return 0
    objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
    if not lp(objptr) or not (0 < numEl < 8000000):
        return 0
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
                    return o
                cur = p(cur + SUPER_OFF)
                g += 1
    return 0


print("motion_watch  PID=%d BASE=0x%X  duration=%.0fs   %s"
      % (PID, BASE, DUR, time.strftime("%Y-%m-%d %H:%M:%S")))
print("waiting for a LokiBotController to appear (i.e. for ARM D to run)...")

t0 = time.time()
ctl = 0
while time.time() - t0 < DUR:
    if not alive():
        print("\n*** PROCESS GONE while waiting for the controller -- NOT OBTAINED (not a null). ***")
        sys.exit(3)
    ctl = find_bot()
    if ctl:
        break
    time.sleep(1.0)

if not ctl:
    print("\n*** no LokiBotController appeared within %.0fs -- STAGING statement, not a result. ***" % DUR)
    sys.exit(3)

pawn = p(ctl + CTL_PAWN)
root = p(pawn + PAWN_ROOT) if lp(pawn) else 0
print("FOUND controller 0x%X  pawn 0x%X  root 0x%X   (t=+%.1fs)\n" % (ctl, pawn, root, time.time() - t0))
print("%-12s %-5s %-6s %-5s %-11s %-28s %-28s %s"
      % ("time", "GATE", "Living", "force", "Blackboard", "RandomMoveDirection", "ControlInputVector", "location"))

first_loc, moved, gate_ever, rand_ever, civ_ever = None, False, False, False, False
n = 0
while time.time() - t0 < DUR:
    if not alive():
        print("\n*** PROCESS GONE at t=+%.1fs -- samples above are still valid. ***" % (time.time() - t0))
        break
    g, ls, f = b1(ctl + CTL_GATE), b1(pawn + PAWN_LS), b1(ctl + CTL_FORCE)
    bb = p(ctl + CTL_BB)
    rd, civ = v3(ctl + CTL_RAND), v3(pawn + PAWN_CIV)
    loc = v3(root + SC_LOC) if lp(root) else None
    if g == 1:
        gate_ever = True
    if rd and (abs(rd[0]) + abs(rd[1]) + abs(rd[2])) > 1e-9:
        rand_ever = True
    if civ and (abs(civ[0]) + abs(civ[1]) + abs(civ[2])) > 1e-9:
        civ_ever = True
    if loc:
        if first_loc is None:
            first_loc = loc
        elif any(abs(loc[i] - first_loc[i]) > 1.0 for i in range(3)):
            moved = True
    print("%-12s %-5s %-6s %-5s 0x%-9X %-28s %-28s %s"
          % ("+%.1fs" % (time.time() - t0),
             g if g is not None else "??", ls if ls is not None else "??",
             f if f is not None else "??", bb,
             ("(%.4f,%.4f,%.4f)" % rd) if rd else "??",
             ("(%.4f,%.4f,%.4f)" % civ) if civ else "??",
             ("(%.1f,%.1f,%.1f)" % loc) if loc else "??"))
    n += 1
    time.sleep(0.5)

print("\n" + "=" * 100)
print("VERDICT   (computed from the OBSERVED samples above, %d of them)" % n)
print("=" * 100)
print("  gate +0x6A0 was 1 at some point        : %s" % ("YES" if gate_ever else "NO"))
print("  RandomMoveDirection ever non-zero      : %s" % ("YES" if rand_ever else "NO"))
print("  ControlInputVector ever non-zero       : %s" % ("YES" if civ_ever else "NO"))
print("  pawn LOCATION changed (>1 uu)          : %s" % ("YES  *** THE BOT MOVED ***" if moved else "NO"))
print()
if not gate_ever:
    print("  !! The gate was NEVER 1 in any sample, so nothing below it is interpretable.")
    print("     Either ARM F did not run, or it ran outside this window.")
elif moved:
    print("  ***** FIRST BOT MOTION IN THIS PROJECT, from a LEGITIMATELY OPENED GATE. *****")
elif rand_ever:
    print("  The wander driver RAN (RandomMoveDirection is non-zero) but the pawn did not move:")
    print("  the failure is now PAST the motor -- movement component, navmesh, or collision.")
else:
    print("  Gate open, but the wander driver never produced a direction. The named remaining")
    print("  candidate is the BLACKBOARD BOOL (S137: .data 0xA0348F0); the Blackboard pointer is")
    print("  printed above so a NULL there is visible rather than inferred.")
