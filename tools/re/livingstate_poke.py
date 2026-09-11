# livingstate_poke.py -- S138. ONE aligned DATA byte on a live UObject, plus an A-B-A readout.
#
# WRITES. This is the only tool in tools/re/ that is not read-only. It writes exactly one byte:
#     <bot pawn> + 0x1090 = 1   (ELivingStateAlive)
# and writes it back to 0 at the end. Nothing else is ever written.
#
# WHY, in one line: S138 established [M] that NOTHING in the decrypted image ever writes
# LivingState=Alive (the only two native writers both store 0; the state-machine->character bridge
# ALokiCharacter::OnLivingStateMachineStateChanged is the void fold 0x0F7EC20; the reflected writer
# is replication and this client has no NetDriver). So the value is stuck at Dead, and
# ALokiBotController's only motion driver is gated on `(LivingState==Alive) && !IsStunned`.
#
# RISK CLASS: DATA poke -- 0 deaths / 22 armed windows in this project's own records, versus 7/8
# for a standing .text patch. Nothing in the module image is touched.
#
# ⚠ PRE-REGISTERED EXPECTATION (docs/s138-f6-PREREGISTERED.txt): the gate at controller+0x6A0 is
#   likely a CACHED value recomputed by ALokiBotController::UpdateCharacterControllable (0x5570B80)
#   on the OnLivingStateChanged delegate, NOT re-derived every Tick. So poking the byte alone may
#   change nothing at +0x6A0. That would locate the next lever, not refute the LivingState result.
#
#   usage: livingstate_poke.py <PID> <BASE-hex> [--dry]
#          --dry  = do every read and print the plan, write NOTHING.
#
# CONTROLS BUILT IN, because a poke with no control is a story:
#   * SPECIFICITY: the PLAYER hero is deliberately NOT poked and is sampled throughout. If its
#     LivingState moves, the write went somewhere unintended and the run is VOID.
#   * READBACK: every write is read back before anything downstream is believed.
#   * A-B-A: poke -> sample -> RESTORE -> sample. The restore is what makes it a measurement.
#   * RUN-IS-VOID: refuses on a dead client rather than printing an artifact.
import ctypes
import sys
import time
from ctypes import wintypes

DRY = "--dry" in sys.argv
argv = [a for a in sys.argv if not a.startswith("--")]
if len(argv) < 3:
    print("usage: livingstate_poke.py <PID> <BASE-hex> [--dry]")
    sys.exit(2)
PID = int(argv[1], 0)
BASE = int(argv[2], 16)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20
SUPER_OFF, CHILDPROPS_OFF, FIELD_NEXT = 0x48, 0x58, 0x18
FPROP_OFFSET = 0x44

LIVINGSTATE = 0x1090      # ALokiCharacter::LivingState (uint8)  [M]
CTL_PAWN = 0x3F8          # AController::Pawn
CTL_CONTROLLABLE = 0x6A0  # ALokiBotController::bCharacterControllable  <- THE GATE
CTL_FORCEOFF = 0x602      # ForceCharacterNotControllable
CTL_RANDDIR = 0x658       # RandomMoveDirection (double[3])
PAWN_CIV = 0x418          # APawn::ControlInputVector (double[3])
PAWN_ROOT = 0x1B0         # AActor::RootComponent
SCENE_RELLOC = 0x158      # USceneComponent::RelativeLocation (double[3])

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
    ok = k32.WriteProcessMemory(h, ctypes.c_void_p(a), buf, len(data), ctypes.byref(r))
    return bool(ok) and r.value == len(data)


def u32(b, o=0):
    return int.from_bytes(b[o:o + 4], "little")


def u64(b, o=0):
    return int.from_bytes(b[o:o + 8], "little")


def lp(v):
    return 0x10000 < v < 0x7FFFFFFFFFFF


def p(a):
    b = rpm(a, 8)
    return u64(b) if b else 0


def vec3(a):
    b = rpm(a, 24)
    if not b:
        return None
    import struct
    return struct.unpack("<ddd", b)


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


print("livingstate_poke  PID=%d BASE=0x%X  %s   %s"
      % (PID, BASE, "*** DRY RUN -- NOTHING WILL BE WRITTEN ***" if DRY else "*** WILL WRITE ONE BYTE ***",
         time.strftime("%Y-%m-%d %H:%M:%S")))

hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("GUObjectArray unreadable -- RUN IS VOID.")
    sys.exit(1)
objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
if not lp(objptr) or not (0 < numEl < 8000000):
    print("GUObjectArray implausible -- RUN IS VOID.")
    sys.exit(1)

bots, heroes = [], []
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
        c = ocls(o)
        if not c:
            continue
        ch = chain(c)
        if "LokiBotController" in ch:
            bots.append((o, ch[0]))
        elif "LokiHeroCharacter" in ch:
            heroes.append((o, ch[0]))

print("\nLokiBotController-chain objects : %d" % len(bots))
print("LokiHeroCharacter-chain objects : %d" % len(heroes))
if not bots:
    print("\n*** NO LokiBotController -- there is no +0x6A0 gate to read. STAGING STATEMENT,")
    print("    NOT A RESULT. (Did ARM D run? inject tutorial_launch_spawnbot_premade.dll first.)")
    sys.exit(3)

ctl = bots[0][0]
botpawn = p(ctl + CTL_PAWN)
if not lp(botpawn):
    print("\n*** the LokiBotController possesses no pawn -- nothing to poke. VOID.")
    sys.exit(3)
others = [o for o, _ in heroes if o != botpawn]
print("\nTARGET   bot controller 0x%X  ->  pawn 0x%X '%s'" % (ctl, botpawn, oname(botpawn)))
print("CONTROLS %d other hero pawn(s), NONE of which will be written: %s"
      % (len(others), ", ".join("0x%X" % o for o in others[:6])))


def sample(tag):
    ls = rpm(botpawn + LIVINGSTATE, 1)
    gate = rpm(ctl + CTL_CONTROLLABLE, 1)
    forceoff = rpm(ctl + CTL_FORCEOFF, 1)
    rd = vec3(ctl + CTL_RANDDIR)
    civ = vec3(botpawn + PAWN_CIV)
    root = p(botpawn + PAWN_ROOT)
    loc = vec3(root + SCENE_RELLOC) if lp(root) else None
    ctrl_ls = [(o, rpm(o + LIVINGSTATE, 1)) for o in others]
    print("  [%-9s] botLivingState=%-4s  GATE+0x6A0=%-4s  force+0x602=%-4s"
          % (tag, ls[0] if ls else "??", gate[0] if gate else "??", forceoff[0] if forceoff else "??"))
    print("              RandomMoveDir=%s   ControlInputVector=%s"
          % (("(%.3f,%.3f,%.3f)" % rd) if rd else "??", ("(%.3f,%.3f,%.3f)" % civ) if civ else "??"))
    print("              pawn loc=%s" % (("(%.1f,%.1f,%.1f)" % loc) if loc else "??"))
    print("              CONTROL other heroes LivingState=%s"
          % (", ".join(("%d" % v[0]) if v else "??" for _, v in ctrl_ls) or "(none)"))
    return (ls[0] if ls else None, gate[0] if gate else None, rd, civ, loc,
            [v[0] if v else None for _, v in ctrl_ls])


print("\n" + "=" * 96)
print("A -- BASELINE (before any write)")
print("=" * 96)
a = sample("A")

if DRY:
    print("\n--dry given: would write 1 to 0x%X (pawn+0x1090). NOTHING WRITTEN. Exiting."
          % (botpawn + LIVINGSTATE))
    sys.exit(0)

print("\n" + "=" * 96)
print("B -- POKE  botPawn+0x1090 = 1 (ELivingStateAlive)   [ONE BYTE]")
print("=" * 96)
ok = wpm(botpawn + LIVINGSTATE, bytes([1]))
back = rpm(botpawn + LIVINGSTATE, 1)
print("  WriteProcessMemory ok=%s   READBACK=%s" % (ok, back[0] if back else "??"))
if not ok or not back or back[0] != 1:
    print("  *** P1 FAILED -- the write did not land. NOTHING DOWNSTREAM IS INTERPRETABLE. ***")
    sys.exit(4)
print("  P1 HOLDS.")
bsamples = []
for i in range(5):
    time.sleep(2.0)
    bsamples.append(sample("B+%ds" % ((i + 1) * 2)))

print("\n" + "=" * 96)
print("C -- RESTORE  botPawn+0x1090 = 0   (this is what makes it a measurement)")
print("=" * 96)
ok2 = wpm(botpawn + LIVINGSTATE, bytes([0]))
back2 = rpm(botpawn + LIVINGSTATE, 1)
print("  WriteProcessMemory ok=%s   READBACK=%s" % (ok2, back2[0] if back2 else "??"))
time.sleep(2.0)
c = sample("C")

print("\n" + "=" * 96)
print("VERDICT")
print("=" * 96)
print("  P1 poke landed (readback==1)            : YES")
ctrl_ok = all(v == 0 for v in c[5] if v is not None)
print("  P2 control heroes still 0 (specificity) : %s" % ("YES" if ctrl_ok else "*** NO -- RUN VOID ***"))
# ⚠⚠ DEFECT FIXED 2026-08-23, AND IT PRINTED A FALSE "YES" ON ITS FIRST AND ONLY RUN.
# The old predicate was `a[1] == 0 and any(True for _ in [1]) and c is not None` -- the second term
# is ALWAYS true and the third is ALWAYS true, so it collapsed to "the BASELINE gate was 0", which
# is the precondition of the whole experiment. It therefore printed YES unconditionally, including
# on a run whose own samples showed GATE=0 at every timepoint. A degenerate always-true guard: the
# same shape as S136's constant-folded dispatch guard, in a verdict line rather than in an arm.
# It was caught by READING THE SAMPLES rather than the verdict -- which is exactly why this project
# records "the call returned ok is never a success criterion".
# Now: the verdict is computed from the OBSERVED B-phase samples and nothing else.
gate_vals = [s[1] for s in bsamples if s[1] is not None]
p3 = any(v == 1 for v in gate_vals)
print("  P3 gate +0x6A0 flipped 0 -> 1           : %s   (observed B-phase values: %s)"
      % ("YES" if p3 else "NO", ", ".join(str(v) for v in gate_vals) or "none readable"))
if not p3:
    print("      -> this is the PRE-REGISTERED expected outcome (P3-ALT), not a surprise.")
print()
print("  Read the B+ samples above for P3/P4/P5. If GATE stayed 0 while P1 and P2 held, that is the")
print("  PRE-REGISTERED expected outcome (docs/s138-f6-PREREGISTERED.txt P3-ALT): +0x6A0 is a CACHED")
print("  value recomputed by ALokiBotController::UpdateCharacterControllable (impl 0x5570B80) on the")
print("  OnLivingStateChanged delegate (hero+0xC38), not re-derived per Tick. The named next lever is")
print("  to DRIVE that recompute -- NOT evidence against the LivingState result.")
if not ctrl_ok:
    print("\n  *** A CONTROL HERO'S LivingState MOVED. The write went somewhere unintended.")
    print("      TREAT THE WHOLE RUN AS VOID. ***")
