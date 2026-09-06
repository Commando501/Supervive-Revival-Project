# livingstate_sweep.py -- S138. Read-only RPM. NO injection, NO .text write, NO poke.
#
# THE QUESTION: is ANY character ever marked "Alive" on the force-open tutorial route?
#
# WHY IT IS ASKED THIS WAY. S138 established [M], n=3 clients, that the ALokiBotController is inert
# BY GATE: bCharacterControllable (+0x6A0) = 0 while ForceCharacterNotControllable (+0x602) = 0, so
# nothing is forcing it and the gate's own term `(LivingState==Alive) && !IsStunned` is false.
# Flight 4 then read LivingState on the bot pawn (0) AND on the player hero as a control -- and the
# CONTROL READ 0 TOO. Under either candidate enum 0 is not "Alive":
#     EPlayerLivingState:  NoCharacter=0 Dead=1 Knocked=2 Alive=3 Count=4
#     ELivingState:        ELivingStateDead=0 ELivingStateAlive=1 ELivingStateKnocked=2 Count=3
# so the reading could not be attributed to the BOT. The right successor question is therefore not
# "why is the bot's LivingState wrong" but "does ANYTHING here read Alive?" -- because:
#     * if NOTHING does, the bot is not specially gated, the whole world is, and the [I] hypothesis
#       (nothing on the force-open route is ever marked Alive, because whatever sets LivingState
#       lives in the spawn/round flow that FK-1's stripped SpawnPlayer never runs) becomes [M];
#     * if SOMETHING does, that object IS the positive control flight 4 lacked, and the bot-vs-it
#       comparison becomes meaningful for the first time.
# Either way the sweep is decisive, which a single pair of samples was not.
#
#   usage: livingstate_sweep.py <PID> <BASE-hex>
#
# DESIGN NOTES, each earned:
#   * It sweeps EVERY LokiCharacter-chain object, not just heroes. Restricting to heroes would
#     re-create flight 4's failure -- if only heroes are ever sampled and no hero is Alive, there is
#     still no control. A creep/monster/spectator reading Alive would settle it instantly.
#   * LivingState is resolved BY NAME off each live class; the recorded +0x1090 is printed BESIDE it
#     as a cross-check so a successor can see whether the two agree, never instead of it.
#   * The ENUM TYPE is resolved LIVE via FEnumProperty::Enum at *(prop+0x78) [FK-14 measured], which
#     settles which of the two candidate enums applies -- flight 4 could not, and guessed
#     'ELokiLivingState', a name that occurs ZERO times in the image (controls: ERoundPhase 12,
#     ELokiActivityState 7). Do not re-guess it; read it.
#   * CDOs and _GEN_VARIABLE archetypes are EXCLUDED from the verdict but COUNTED and shown, because
#     a CDO's default value is itself informative about what the shipped default is.
#   * RUN-IS-VOID checks up front. S137 lost a reading to a probe that printed an artifact for a dead
#     client instead of refusing.
import ctypes
import sys
import time
from ctypes import wintypes

if len(sys.argv) < 3:
    print("usage: livingstate_sweep.py <PID> <BASE-hex>")
    sys.exit(2)
PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF = 0x18, 0x20
SUPER_OFF, CHILDPROPS_OFF, FIELD_NEXT = 0x48, 0x58, 0x18
FIELD_CLASS = 0x08
FPROP_OFFSET = 0x44
ENUMPROP_ENUM = 0x78          # FEnumProperty::Enum   [FK-14: *(+0x78)]
ENUMPROP_UNDER = 0x70         # FEnumProperty::UnderlyingProp
REC_LIVINGSTATE = 0x1090      # printed as a cross-check ONLY

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


_chain = {}


def chain(c):
    if c in _chain:
        return _chain[c]
    out, cur, g = [], c, 0
    while lp(cur) and g < 16:
        out.append(oname(cur))
        cur = p(cur + SUPER_OFF)
        g += 1
    _chain[c] = out
    return out


_prop = {}


def findprop(c, want):
    """Resolve a property BY NAME up the class chain. Returns (offset, FProperty*, typename)."""
    key = (c, want)
    if key in _prop:
        return _prop[key]
    res, cur, g = (None, 0, "?"), c, 0
    while lp(cur) and g < 16:
        f, i = p(cur + CHILDPROPS_OFF), 0
        while lp(f) and i < 900:
            if oname(f) == want:
                b = rpm(f + FPROP_OFFSET, 4)
                fc = p(f + FIELD_CLASS)
                res = (u32(b) if b else None, f, oname(fc) if lp(fc) else "?")
                _prop[key] = res
                return res
            f = p(f + FIELD_NEXT)
            i += 1
        cur = p(cur + SUPER_OFF)
        g += 1
    _prop[key] = res
    return res


print("livingstate_sweep  PID=%d BASE=0x%X   *** CENSUS TIMESTAMP %s ***"
      % (PID, BASE, time.strftime("%Y-%m-%d %H:%M:%S")))
print("(read-only RPM. no injection, no write of any kind.)\n")

hdr = rpm(OBJOBJECTS, 0x18)
if not hdr:
    print("GUObjectArray unreadable -- RUN IS VOID.")
    sys.exit(1)
objptr, numEl = u64(hdr, 0), u32(hdr, 0x14)
if not lp(objptr) or not (0 < numEl < 8000000):
    print("GUObjectArray implausible (ptr=0x%X num=%d) -- RUN IS VOID." % (objptr, numEl))
    sys.exit(1)

rows, scanned = [], 0
enum_seen = {}
for ci in range((numEl + PERCHUNK - 1) // PERCHUNK):
    chunk = p(objptr + ci * 8)
    if not lp(chunk):
        continue
    cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
    for j in range(cnt):
        o = p(chunk + j * STRIDE)
        if not lp(o):
            continue
        c = ocls(o)
        if not c:
            continue
        ch = chain(c)
        if "LokiCharacter" not in ch:
            continue
        scanned += 1
        nm = oname(o)
        kind = ("CDO" if nm.startswith("Default__")
                else "ARCHETYPE" if "_GEN_VARIABLE" in nm
                else "LIVE")
        off, fp, ty = findprop(c, "LivingState")
        val, how = None, "NOT RESOLVED BY NAME"
        if off is not None:
            b = rpm(o + off, 4)
            if b:
                val, how = u32(b), "by name @+0x%X" % off
        rec = rpm(o + REC_LIVINGSTATE, 4)
        recv = u32(rec) if rec else None
        en = ""
        if lp(fp):
            e = p(fp + ENUMPROP_ENUM)
            if lp(e):
                en = oname(e)
                enum_seen[en] = enum_seen.get(en, 0) + 1
        rows.append((kind, o, nm, ch[0], val, how, off, recv, en))

print("scanned %d LokiCharacter-chain objects (of %d slots)\n" % (scanned, numEl))

print("=" * 100)
print("THE ENUM -- resolved LIVE off FEnumProperty::Enum (*(prop+0x78)), not guessed")
print("=" * 100)
if enum_seen:
    for e, n in sorted(enum_seen.items(), key=lambda kv: -kv[1]):
        print("   %-32s  (on %d objects)" % (e, n))
    print("""
   Known value tables, read offline from the UHT {const char* Name; int64 Value} pairs:
     EPlayerLivingState:  NoCharacter=0  Dead=1  Knocked=2  Alive=3  Count=4
     ELivingState:        ELivingStateDead=0  ELivingStateAlive=1  ELivingStateKnocked=2  Count=3""")
else:
    print("   *** enum did not resolve -- the VALUES below are still readable but unnamed ***")

print("\n" + "=" * 100)
print("PER-OBJECT")
print("=" * 100)
print("%-10s %-16s %-34s %-6s %-8s %s" % ("kind", "object", "class", "value", "rec+1090", "resolve"))
for kind, o, nm, cn, val, how, off, recv, en in sorted(rows, key=lambda r: (r[0] != "LIVE", r[3])):
    agree = "" if (val is None or recv is None) else ("  AGREE" if (off == REC_LIVINGSTATE) else "  *** OFFSET DIFFERS ***")
    print("%-10s 0x%-14X %-34s %-6s %-8s %s%s"
          % (kind, o, cn[:34], ("%d" % val) if val is not None else "??",
             ("%d" % recv) if recv is not None else "??", how, agree))

live = [r for r in rows if r[0] == "LIVE" and r[4] is not None]
nonzero = [r for r in live if r[4] != 0]
print("\n" + "=" * 100)
print("VERDICT")
print("=" * 100)
print("  LIVE LokiCharacter-chain objects with a readable LivingState : %d" % len(live))
vals = {}
for r in live:
    vals[r[4]] = vals.get(r[4], 0) + 1
print("  value histogram (LIVE only)                                  : %s"
      % (", ".join("%d x%d" % (k, v) for k, v in sorted(vals.items())) or "(none)"))
print()
if not live:
    print("  *** NO LIVE OBJECT HAD A READABLE LivingState -- THIS IS AN INSTRUMENT RESULT,")
    print("      NOT A STATEMENT ABOUT THE GAME. Do not record it as 'nothing is Alive'.")
elif nonzero:
    print("  ***** AT LEAST ONE LIVE CHARACTER IS NON-ZERO -- THIS IS THE POSITIVE CONTROL *****")
    for r in nonzero:
        print("      0x%X %s -> LivingState=%d" % (r[1], r[3], r[4]))
    print("  => a non-zero reading is REACHABLE on this route, so a 0 elsewhere is a real")
    print("     statement about THAT object rather than about the instrument or the world.")
else:
    print("  ***** EVERY LIVE CHARACTER READS 0 *****")
    print("  Under BOTH candidate enums 0 is NOT 'Alive' (NoCharacter=0 / Dead=0; Alive=3 / 1).")
    print("  => NOTHING on the force-open route is marked Alive, so the bot is NOT specially")
    print("     gated -- the whole world is. That upgrades the S138 flight-4 [I] to [M] for this")
    print("     route, and it means 'why is the bot inert' was the wrong question.")
    print("  !! Scope it honestly: this is one world, one moment. It says nothing about a REAL")
    print("     match, and it does not identify what WOULD set LivingState.")
