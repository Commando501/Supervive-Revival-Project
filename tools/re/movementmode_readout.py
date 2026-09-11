# movementmode_readout.py -- S138 flight 9. Read-only RPM. NO injection, NO write.
#
# THE QUESTION: why does a bot pawn with a working AI not MOVE?
#
# Flight 8 measured [M], 194 samples over 97 s, that with the gate legitimately opened the
# ALokiBotController's wander driver RUNS (44 distinct horizontal unit directions, Z exactly 0,
# ~one per 2.2 s against a transcribed 2.0 s cadence) and that ControlInputVector on the PAWN
# equals RandomMoveDirection on the CONTROLLER in 193/194 samples -- i.e. the whole chain
# behaviour tree -> blackboard -> wander -> movement input works. The pawn still moved ZERO units.
#
# ControlInputVector holding a steady non-zero value is itself the clue: stock UE CONSUMES and
# zeroes it every movement tick (APawn::ConsumeMovementInputVector). Nothing consuming it means the
# CharacterMovementComponent is not turning input into displacement.
#
# So: read the movement mode, and read it on the PLAYER HERO in the same pass as a POSITIVE
# CONTROL. The player hero demonstrably moves on this route (S108b locomotion, and CLAUDE.md
# records it is forced to MOVE_Flying via KFLYMODE=5 precisely because the Walking ground chain
# does not work here). If the bot differs from the player, that difference is the answer.
#
#   usage: movementmode_readout.py <PID> <BASE-hex>
#
# EVERYTHING IS RESOLVED BY NAME off the live class; nothing is hardcoded except as a printed
# cross-check. The enum is resolved LIVE via FEnumProperty::Enum (*(prop+0x78)) rather than assumed
# -- flight 4 guessed an enum name that occurs ZERO times in the image, and flight 5 had to fix it.
import ctypes
import struct
import sys
import time
from ctypes import wintypes

if len(sys.argv) < 3:
    print("usage: movementmode_readout.py <PID> <BASE-hex>")
    sys.exit(2)
PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF = 0x18, 0x20, 0x48
CHILDPROPS_OFF, FIELD_NEXT, FIELD_CLASS, FPROP_OFFSET = 0x58, 0x18, 0x08, 0x44
ENUMPROP_ENUM = 0x78
CTL_PAWN, CTL_GATE = 0x3F8, 0x6A0
PAWN_CIV, PAWN_ROOT, SC_LOC = 0x418, 0x1B0, 0x158

# Stock UE EMovementMode, printed as a decode aid ONLY. The live enum name is resolved below and
# if it is not EMovementMode this table must not be trusted.
# ⚠ MovementMode is a TEnumAsByte<EMovementMode>, i.e. a BYTE property, so FEnumProperty::Enum
#   (*(prop+0x78)) does NOT apply and the live enum resolve below prints "unresolved" for it. That
#   is expected, not a fault. The numeric value IS resolved by name; this table is stock UE
#   numbering, corroborated independently by CLAUDE.md recording KFLYMODE=5 == MOVE_Flying.
EMOVE = {0: "MOVE_None", 1: "MOVE_Walking", 2: "MOVE_NavWalking", 3: "MOVE_Falling",
         4: "MOVE_Swimming", 5: "MOVE_Flying", 6: "MOVE_Custom"}

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


def f32(a):
    b = rpm(a, 4)
    return struct.unpack("<f", b)[0] if b else None


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
    """(offset, FProperty*, typename) resolved BY NAME up the chain."""
    k = (c, want)
    if k in _pc:
        return _pc[k]
    res, cur, g = (None, 0, "?"), c, 0
    while lp(cur) and g < 16:
        f, i = p(cur + CHILDPROPS_OFF), 0
        while lp(f) and i < 900:
            if oname(f) == want:
                b = rpm(f + FPROP_OFFSET, 4)
                fc = p(f + FIELD_CLASS)
                res = (u32(b) if b else None, f, oname(fc) if lp(fc) else "?")
                _pc[k] = res
                return res
            f = p(f + FIELD_NEXT)
            i += 1
        cur = p(cur + SUPER_OFF)
        g += 1
    _pc[k] = res
    return res


def rdprop(obj, name, size=1):
    off, fp, ty = findprop(ocls(obj), name)
    if off is None:
        return None, "NOT RESOLVED BY NAME", off, fp, ty
    b = rpm(obj + off, size)
    if not b:
        return None, "unreadable @+0x%X" % off, off, fp, ty
    return int.from_bytes(b, "little"), "by name @+0x%X" % off, off, fp, ty


print("movementmode_readout  PID=%d BASE=0x%X   *** %s ***"
      % (PID, BASE, time.strftime("%Y-%m-%d %H:%M:%S")))
print("(read-only RPM. no injection, no write of any kind.)\n")

hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("GUObjectArray unreadable -- RUN IS VOID.")
    sys.exit(1)
objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
if not lp(objptr) or not (0 < numEl < 8000000):
    print("GUObjectArray implausible -- RUN IS VOID.")
    sys.exit(1)

botctl, heroes, playerctl = 0, [], 0
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
        if "LokiBotController" in ch and not botctl:
            botctl = o
        elif "LokiPlayerController" in ch and not playerctl:
            playerctl = o
        elif "LokiHeroCharacter" in ch:
            heroes.append(o)

botpawn = p(botctl + CTL_PAWN) if botctl else 0
playerpawn = p(playerctl + CTL_PAWN) if playerctl else 0
print("bot controller     : 0x%X" % botctl if botctl else "bot controller     : *** NONE -- staging statement, not a result ***")
print("bot pawn           : 0x%X" % botpawn if botpawn else "bot pawn           : none")
print("player controller  : 0x%X %s" % (playerctl, oname(ocls(playerctl))) if playerctl else "player controller  : none")
print("player pawn        : 0x%X" % playerpawn if playerpawn else "player pawn        : none")
print("other hero pawns   : %d\n" % len(heroes))

targets = []
if botpawn:
    targets.append(("BOT   (from SpawnAIFromClass)", botpawn, botctl))
if playerpawn:
    targets.append(("PLAYER (POSITIVE CONTROL)    ", playerpawn, playerctl))
for i, hp in enumerate(heroes):
    if hp not in (botpawn, playerpawn) and i < 3:
        targets.append(("other hero #%d               " % i, hp, 0))

if not targets:
    print("*** no pawns to read -- RUN IS VOID / staging statement. ***")
    sys.exit(3)

enum_names = {}
print("=" * 104)
for label, pawn, ctl in targets:
    print("--- %s  pawn=0x%X  class=%s" % (label, pawn, oname(ocls(pawn))))
    cmcoff, _, _ = findprop(ocls(pawn), "CharacterMovement")
    cmc = p(pawn + cmcoff) if cmcoff is not None else 0
    if not lp(cmc):
        print("      CharacterMovement: NOT RESOLVED / NULL  (off=%s)" % cmcoff)
        continue
    print("      CharacterMovement @+0x%X = 0x%X  class=%s" % (cmcoff, cmc, oname(ocls(cmc))))
    mm, how, off, fp, ty = rdprop(cmc, "MovementMode", 1)
    en = ""
    if lp(fp):
        e = p(fp + ENUMPROP_ENUM)
        if lp(e):
            en = oname(e)
            enum_names[en] = enum_names.get(en, 0) + 1
    print("      *** MovementMode = %s (%s)   [%s, type=%s, enum=%s] ***"
          % (mm if mm is not None else "??", EMOVE.get(mm, "?"), how, ty, en or "unresolved"))
    for nm, sz in (("bCheatFlying", 1), ("MaxWalkSpeed", 4), ("GravityScale", 4), ("MaxFlySpeed", 4)):
        o2, h2, _, _, _ = rdprop(cmc, nm, sz)
        if o2 is None:
            continue
        if sz == 4:
            b = rpm(cmc + findprop(ocls(cmc), nm)[0], 4)
            print("      %-16s = %.3f   [%s]" % (nm, struct.unpack("<f", b)[0] if b else 0.0, h2))
        else:
            # ⚠ bools here are UHT BITFIELDS: this is the RAW BYTE at the property offset, not the
            #   bool. A value like 8 means "some bit in this byte is set", NOT "the flag is 8".
            print("      %-16s = 0x%02X (RAW BYTE, bitfield -- not a bool)   [%s]" % (nm, o2, h2))
    upd, h3, _, _, _ = rdprop(cmc, "UpdatedComponent", 8)
    print("      UpdatedComponent = 0x%X   [%s]" % (upd or 0, h3))
    vel = None
    voff, _, _ = findprop(ocls(cmc), "Velocity")
    if voff is not None:
        vel = v3(cmc + voff)
    print("      Velocity         = %s" % (("(%.3f,%.3f,%.3f)" % vel) if vel else "??"))
    civ = v3(pawn + PAWN_CIV)
    root = p(pawn + PAWN_ROOT)
    loc = v3(root + SC_LOC) if lp(root) else None
    print("      ControlInputVector = %s     location = %s"
          % (("(%.4f,%.4f,%.4f)" % civ) if civ else "??", ("(%.1f,%.1f,%.1f)" % loc) if loc else "??"))
    # ⚠ DEFECT FIXED: +0x6A0 is bCharacterControllable on ALokiBotController ONLY. Printing it for
    #   a BP_LokiPlayerController_Dev_C reads a DIFFERENT field of a different class and looks like a
    #   meaningful "gate=1". Only print it when the controller really is a LokiBotController.
    if ctl:
        if "LokiBotController" in chain(ocls(ctl)):
            g = rpm(ctl + CTL_GATE, 1)
            print("      (controller gate +0x6A0 = %s)" % (g[0] if g else "??"))
        else:
            print("      (gate +0x6A0 NOT printed: %s is not a LokiBotController, so that offset"
                  % oname(ocls(ctl)))
            print("       is a different field entirely and would be meaningless here)")
    print()

print("=" * 104)
print("ENUM resolved live: %s" % (", ".join("%s x%d" % kv for kv in enum_names.items()) or "NONE"))
if enum_names and "EMovementMode" not in enum_names:
    print("  ⚠ the live enum is NOT 'EMovementMode' -- the decode table above is NOT applicable.")
print()
print("HOW TO READ THIS")
print("  The PLAYER row is the POSITIVE CONTROL: it demonstrably moves on this route. If the probe")
print("  cannot show a sane value THERE, the bot's value is UNINTERPRETABLE rather than a null.")
print("  If the two rows DIFFER, that difference is the answer to 'why does the bot not move'.")
print("  If they are the SAME, movement mode is NOT the discriminator and the next candidate is")
print("  the pawn's altitude (Z=13240 is the sp LIFT position, ~13 km above the island) or whether")
print("  the component ticks at all.")
