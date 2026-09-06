# playerstate_readout.py -- S137. Read-only RPM. NO injection, NO .text write, NO poke.
#
# THE QUESTION: does an AI-controlled pawn have a PlayerState?
#
# S136 measured `controller+0x3C0` (AController::PlayerState) and `pawn+0x3D8`
# (APawn::PlayerState) both NULL on the AIController that SpawnAIFromClass creates, and settled
# WHY offline: `AAIController::PostInitializeComponents` (0x45D6D10) gates the call to
# `AController::InitPlayerState` (0x36DEE20, vtable slot 273) on `bWantsPlayerState`, and stock UE
# CLEARS that bit in the AAIController constructor.
#
# This probe is the EXTERNAL, SECOND INSTRUMENT for the in-shim readout of that experiment. The shim
# prints its own numbers; a claim in this project needs two instruments, and an in-shim number that
# no external probe reproduces is not a measurement.
#
#   usage: playerstate_readout.py <PID> <BASE-hex>
#     e.g. playerstate_readout.py 43456 0x7FF608F40000
#
# WHAT IT PRINTS, and why each line is there:
#   * a TIMESTAMP -- S136's "exactly 1 AIController" was [M] AT TIME T ONLY and read 2 later
#     because another arm flew in between. Every census here is stamped.
#   * per AIController-derived object: FName.Number (obj+0x24), which is a strictly-DECREASING
#     runtime spawn counter [M, S136] and therefore a free CREATION-ORDER oracle. InternalIndex is
#     NOT monotone (GUObjectArray reuses freed slots) -- do not use it for order.
#   * PlayerState / Pawn / Character resolved BY NAME off the live class chain, never at a
#     hardcoded offset; the recorded offset is printed BESIDE it as a cross-check so a successor can
#     see whether the two agree.
#   * bWantsPlayerState decoded from the LIVE FBoolProperty (ByteOffset/FieldMask at +0x71/+0x73),
#     because FBoolPropertyParams carries no ByteOffset/ByteMask (the S132 trap) -- plus the raw
#     dword, so the decode is auditable from the output alone.
#   * the CDO of each distinct AIControllerClass, with the same bit -- that is the thing the arm
#     pokes, and reading it externally is what separates "the poke landed" from "the poke landed and
#     propagated to the instance".
#   * the PLAYER hero's controller triple as a POSITIVE CONTROL. It is possessed by a real
#     BP_LokiPlayerController_Dev_C with a real PlayerState, so if this probe cannot see THAT, its
#     zeros on the AI controller are UNINTERPRETABLE, not nulls.
import ctypes
import sys
import time
from ctypes import wintypes

if len(sys.argv) < 3:
    print("usage: playerstate_readout.py <PID> <BASE-hex>")
    sys.exit(2)
PID = int(sys.argv[1], 0)
BASE = int(sys.argv[2], 16)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930          # FChunkedFixedUObjectArray: +0x00 Objects**, +0x14 NumElements
PERCHUNK, STRIDE = 65536, 0x18

CLASS_OFF, NAME_OFF = 0x18, 0x20       # UObjectBase in THIS build is 0x18/0x20, NOT stock 0x10/0x18
SUPER_OFF = 0x48                       # UStruct::SuperStruct
CHILDPROPS_OFF = 0x58                  # UStruct::ChildProperties
FIELD_NEXT = 0x18                      # FField::Next
FIELD_CLASS = 0x08                     # FField::ClassPrivate (FFieldClass -- its name is the type)
FPROP_OFFSET = 0x44                    # FProperty::Offset_Internal
CDO_OFF = 0x178                        # UClass::ClassDefaultObject
# FBoolProperty's four bytes, immediately after sizeof(FProperty)==0x70 (FK-14 measured 0x70, and
# that +0x70 is uniformly the derived class's first member).
BP_FIELDSIZE, BP_BYTEOFFSET, BP_BYTEMASK, BP_FIELDMASK = 0x70, 0x71, 0x72, 0x73

# The recorded values from S136, used ONLY as printed cross-checks against the by-name resolve.
REC_CTL_PLAYERSTATE = 0x3C0
REC_PAWN_PLAYERSTATE = 0x3D8
REC_PAWN_AICLASS = 0x3D0
REC_PAWN_CONTROLLER = 0x400
REC_WANTSPS_OFF = 0x488
REC_WANTSPS_MASK = 0x20

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


def u32(b, o):
    return int.from_bytes(b[o:o + 4], "little")


def i32(b, o):
    return int.from_bytes(b[o:o + 4], "little", signed=True)


def u64(b, o):
    return int.from_bytes(b[o:o + 8], "little")


def lp(v):
    return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0


def p(a):
    b = rpm(a, 8)
    return u64(b, 0) if b else 0


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
                        if w:
                            r = "".join(chr(s[k * 2] | (s[k * 2 + 1] << 8)) for k in range(ln))
                        else:
                            r = s.decode("latin1", "replace")
    _nc[i] = r
    return r


def oname(o):
    b = rpm(o + NAME_OFF, 4)
    return fname(u32(b, 0)) if b else "?"


def onumber(o):
    # FName.Number at obj+0x24. [M, S136] a strictly-DECREASING runtime spawn counter -- a free
    # creation-order oracle that obj_by_chain.objname() throws away by reading only the index.
    b = rpm(o + NAME_OFF + 4, 4)
    return u32(b, 0) if b else -1


def ocls(o):
    c = p(o + CLASS_OFF)
    return c if lp(c) else 0


def clsname(c):
    return oname(c) if lp(c) else "?"


_chain = {}


def chain(c):
    if c in _chain:
        return _chain[c]
    out, cur, g = [], c, 0
    while lp(cur) and g < 24:
        out.append(clsname(cur))
        cur = p(cur + SUPER_OFF)
        g += 1
    _chain[c] = out
    return out


def ftype(f):
    fc = p(f + FIELD_CLASS)
    if not lp(fc):
        return "?"
    b = rpm(fc, 4)
    return fname(u32(b, 0)) if b else "?"


def findprop(c, name):
    """Resolve a property BY NAME across the class chain -> (fprop, offset, typename)."""
    cur, g = c, 0
    while lp(cur) and g < 24:
        f, i = p(cur + CHILDPROPS_OFF), 0
        while lp(f) and i < 900:
            if oname(f) == name:
                b = rpm(f + FPROP_OFFSET, 4)
                return f, (i32(b, 0) if b else None), ftype(f)
            f = p(f + FIELD_NEXT)
            i += 1
        cur = p(cur + SUPER_OFF)
        g += 1
    return 0, None, ""


def readbool(obj, c, name, rec_off, rec_mask):
    """Decode a bool UPROPERTY off the LIVE FBoolProperty. Returns (printable, value or None)."""
    f, off, ty = findprop(c, name)
    if not f or off is None:
        d = rpm(obj + rec_off, 4)
        s = "%s: NOT RESOLVED BY NAME" % name
        if d:
            dw = u32(d, 0)
            s += ("   | fallback: recorded +0x%X dword=0x%08X, bit 0x%02X is %s"
                  % (rec_off, dw, rec_mask, "SET" if (dw & rec_mask) else "clear"))
            return s, bool(dw & rec_mask)
        return s + "   | fallback read at recorded offset ALSO FAILED -> UNINTERPRETABLE", None
    meta = rpm(f + BP_FIELDSIZE, 4)
    fs, bo, bm, fm = (meta[0], meta[1], meta[2], meta[3]) if meta else (0, 0, 0, 0)
    plausible = bool(ty == "BoolProperty" and meta and 1 <= fs <= 8 and bm and fm and bo <= 8)
    addr = obj + off + (bo if plausible else 0)
    raw = rpm(addr, 1)
    if not raw:
        return "%s: @+0x%X (+bo %d) UNREADABLE" % (name, off, bo), None
    val = bool(raw[0] & fm) if plausible else bool(raw[0])
    dw = rpm(obj + off, 4)
    s = ("%s = %s   [by name @+0x%X type=%s fs=%d bo=%d bm=0x%02X fm=0x%02X; byte@0x%X=0x%02X%s%s]"
         % (name, "TRUE" if val else "false", off, ty, fs, bo, bm, fm, addr, raw[0],
            "" if plausible else "  ** bool meta IMPLAUSIBLE -> decoded as raw!=0 **",
            ("; dword@+0x%X=0x%08X" % (off, u32(dw, 0))) if dw else ""))
    agree = (off == rec_off) and plausible and (fm == rec_mask)
    s += ("\n        cross-check vs recorded +0x%X bit 0x%02X: %s"
          % (rec_off, rec_mask,
             "AGREE" if agree else "** DISAGREE ** (by-name says +0x%X mask 0x%02X)" % (off, fm)))
    return s, val


def readobj(obj, c, name, rec_off):
    f, off, ty = findprop(c, name)
    if not f or off is None:
        line = "%s: NOT RESOLVED BY NAME" % name
        if rec_off is not None:
            q = p(obj + rec_off)
            line += ("   | fallback recorded +0x%X -> %s"
                     % (rec_off, ("0x%X (%s)" % (q, clsname(ocls(q)))) if lp(q) else "NULL"))
            return line, (q if lp(q) else 0)
        return line, 0
    q = p(obj + off)
    line = ("%s @+0x%X (%s) = %s"
            % (name, off, ty,
               ("0x%X '%s' class=%s" % (q, oname(q), clsname(ocls(q)))) if lp(q) else "NULL"))
    if rec_off is not None:
        line += ("   [offset %s recorded +0x%X]"
                 % ("AGREES with" if off == rec_off else "** DISAGREES with **", rec_off))
    return line, (q if lp(q) else 0)


# ---------------------------------------------------------------------- the walk
stamp = time.strftime("%Y-%m-%d %H:%M:%S")
print("playerstate_readout  PID=%d BASE=0x%X   *** CENSUS TIMESTAMP %s ***" % (PID, BASE, stamp))
print("(read-only RPM. no injection, no write of any kind.)\n")

objectsPtr = p(OBJOBJECTS)
hdr = rpm(OBJOBJECTS, 0x18)
if not hdr or not lp(objectsPtr):
    print("GUObjectArray unreadable -- RUN IS VOID.")
    sys.exit(1)
numEl = i32(hdr, 0x14)
if not (0 < numEl < 8000000):
    print("NumElements=%d implausible -- RUN IS VOID." % numEl)
    sys.exit(1)

nchunks = (numEl + PERCHUNK - 1) // PERCHUNK
chunkPtrs = rpm(objectsPtr, nchunks * 8)
if not chunkPtrs:
    print("chunk table unreadable -- RUN IS VOID.")
    sys.exit(1)

aictls, botctls, playerstates, pawns, scanned = [], [], [], [], 0
for ci in range(nchunks):
    ch = int.from_bytes(chunkPtrs[ci * 8:ci * 8 + 8], "little")
    if not lp(ch):
        continue
    cnt = min(PERCHUNK, numEl - ci * PERCHUNK)
    items = rpm(ch, cnt * STRIDE)
    if not items:
        continue
    for j in range(cnt):
        o = u64(items, j * STRIDE)
        if not lp(o):
            continue
        c = ocls(o)
        if not c:
            continue
        scanned += 1
        nm = oname(o)
        if nm.startswith("Default__") or "_GEN_VARIABLE" in nm:
            continue
        ch_ = chain(c)
        if "AIController" in ch_:
            aictls.append(o)
        # ⚠⚠ DEGENERATE-QUERY TRAP, found the hard way on 2026-08-21 with a KNOWN POSITIVE in the
        # process. `"BotController" in ch_` is an EXACT-ELEMENT test, and NO class in this
        # hierarchy is NAMED `BotController` -- the Loki class is `ALokiBotController`, UHT-stripped
        # to `LokiBotController`, and its ancestors are LokiAIController / AIController / Controller.
        # So the exact form returns 0 EVEN WHILE A LIVE LokiBotController IS POSSESSING A PAWN, and
        # it has NO POSITIVE CONTROL because the term matches nothing at all -- not even a CDO.
        # tools/re/obj_by_chain.py reproduces this exactly: `=BotController` -> "found 0 ... CDOs
        # matched and EXCLUDED: 0", while `=LokiBotController` -> "found 1". The '=' exact form that
        # obj_by_chain's own header tells you to PREFER is the wrong instrument for this question.
        if any("BotController" in a for a in ch_):
            botctls.append(o)
        if "PlayerState" in ch_:
            playerstates.append(o)
        if "Pawn" in ch_:
            pawns.append(o)

print("scanned %d live objects (%d slots, %d distinct classes)" % (scanned, numEl, len(_chain)))
print("  =AIController-chain  : %d" % len(aictls))
print("  BotController-chain  : %d   (SUBSTRING over ancestor names. An EXACT '=BotController'" % len(botctls))
print("                             test is DEGENERATE -- no class in this hierarchy is NAMED")
print("                             'BotController', so it reads 0 even with a live one, and it")
print("                             has no positive control. Use '=LokiBotController'.)")
print("  =PlayerState-chain   : %d" % len(playerstates))
print("  =Pawn-chain          : %d\n" % len(pawns))

seen_aiclasses = {}


def dump_controller(ctl, tag):
    c = ocls(ctl)
    print("--- %s: controller 0x%X '%s' number=%d class=%s"
          % (tag, ctl, oname(ctl), onumber(ctl), clsname(c)))
    print("      chain: %s" % " <- ".join(chain(c)))
    line, ps = readobj(ctl, c, "PlayerState", REC_CTL_PLAYERSTATE)
    print("      " + line)
    line, pawn = readobj(ctl, c, "Pawn", None)
    print("      " + line)
    line, _ = readobj(ctl, c, "Character", None)
    print("      " + line)
    line, _ = readbool(ctl, c, "bWantsPlayerState", REC_WANTSPS_OFF, REC_WANTSPS_MASK)
    print("      " + line)
    # S137: does this controller have a BRAIN? On a plain engine AAIController spawned with
    # BehaviorTree = null these were all measured NULL (S136). They were NEVER RE-READ on an
    # ALokiBotController, whose OnPossess (0x5565470) is where a Loki bot's Blackboard / BT /
    # Perception wiring would live -- so this is the empirical half of that question, and a NULL
    # here on a LokiBotController is a real result rather than a restatement of the S136 one.
    for comp in ("BrainComponent", "Blackboard", "BlackboardComponent",
                 "PerceptionComponent", "PathFollowingComponent",
                 "BehaviorTreeComponent", "CachedGameplayTasksComponent"):
        f, off, ty = findprop(c, comp)
        if not f:
            continue                      # not declared on this chain -- say nothing, claim nothing
        line, _ = readobj(ctl, c, comp, None)
        print("      " + line)
    # ---- S138: DOES THE BOT ACT? the three reads that separate the failure modes ----------------
    # ALokiBotController::Tick (0x556E9F0) has exactly ONE motion driver, a random wander:
    #   [MoveComp vtable+0x5E0] = slot 188 = UCharacterMovementComponent::RequestPathMove 0x35F41D0
    #     -> UPawnMovementComponent::RequestPathMove 0x3642960
    #     -> APawn::Internal_AddMovementInput 0x3BACB60
    #     -> APawn::ControlInputVector (+0x418) += RandomMoveDirection
    # It is gated on Blackboard != NULL (printed above) AND on a blackboard bool whose value is
    # mirrored at controller+0x6A0. Reading these three separates:
    #   gate FALSE                      -> inert BY GATE, not by defect
    #   gate TRUE, direction zero       -> Tick never reached the wander driver
    #   direction non-zero, input zero  -> the motor call did not land
    #   both non-zero, pawn stationary  -> the failure is PAST the motor, in the movement component
    # ⚠ The blackboard key's NAME is [I] (IsCharacterControllable of BB_HeroBots) because decoding
    #   FNameEntryId 0x0001A12C needs the live FNamePool. You do NOT need the name: +0x6A0 is the
    #   same value and is a direct read.
    if any("BotController" in a for a in chain(c)):
        b = rpm(ctl + 0x6A0, 1)
        f2 = rpm(ctl + 0x602, 1)
        print("      -- S138 motion chain (offsets from the ALokiBotController::Tick transcription) --")
        print("      bCharacterControllable +0x6A0 = %s%s"
              % (("%d" % b[0]) if b else "UNREADABLE",
                 "   <- THE GATE on the ONLY motion driver" if b else ""))
        print("      ForceCharacterNotControllable +0x602 = %s   (forces the gate FALSE)"
              % (("%d" % f2[0]) if f2 else "UNREADABLE"))
        rmd = rpm(ctl + 0x658, 24)
        if rmd:
            import struct as _s
            x, y, z = _s.unpack("<ddd", rmd)
            print("      RandomMoveDirection +0x658 = (%.4f, %.4f, %.4f)   |v|=%.4f%s"
                  % (x, y, z, (x * x + y * y + z * z) ** 0.5,
                     "   [Z is 0 by construction -- horizontal unit vector, re-randomised every 2.0 s]"
                     if abs(z) < 1e-9 else "   ** Z NON-ZERO -- unexpected, see the Tick transcription **"))
        else:
            print("      RandomMoveDirection +0x658 = UNREADABLE")
    if ps:
        psc = ocls(ps)
        print("      >> PlayerState 0x%X class=%s chain=%s" % (ps, clsname(psc), " <- ".join(chain(psc))))
    if pawn:
        pc = ocls(pawn)
        print("      >> pawn 0x%X '%s' number=%d class=%s" % (pawn, oname(pawn), onumber(pawn), clsname(pc)))
        line, pps = readobj(pawn, pc, "PlayerState", REC_PAWN_PLAYERSTATE)
        print("           " + line)
        line, pctl = readobj(pawn, pc, "Controller", REC_PAWN_CONTROLLER)
        print("           " + line)
        # S138: the motor's OUTPUT. APawn::ControlInputVector +0x418 is what
        # Internal_AddMovementInput accumulates into; non-zero means the movement input landed.
        civ = rpm(pawn + 0x418, 24)
        if civ:
            import struct as _s2
            cx, cy, cz = _s2.unpack("<ddd", civ)
            print("           ControlInputVector +0x418 = (%.4f, %.4f, %.4f)   |v|=%.4f%s"
                  % (cx, cy, cz, (cx * cx + cy * cy + cz * cz) ** 0.5,
                     "   <- the motor's OUTPUT" if (cx or cy or cz) else "   (zero)"))
        line, aic = readobj(pawn, pc, "AIControllerClass", REC_PAWN_AICLASS)
        print("           " + line)
        print("           HANDSHAKE: pawn.Controller %s this controller" % ("==" if pctl == ctl else "!="))
        print("           PLAYERSTATE MATCH: pawn.PlayerState %s controller.PlayerState%s"
              % ("==" if pps == ps else "!=", "  (both NULL)" if (not pps and not ps) else ""))
        if aic:
            seen_aiclasses[aic] = True
    print()


# The PLAYER hero's controller is the POSITIVE CONTROL: a known-good possession with a real
# PlayerState in this same build. If the reads below are blank on it too, this probe is broken and
# every zero above is UNINTERPRETABLE rather than a null.
print("=" * 100)
print("POSITIVE CONTROL -- a known-good possession (player-controlled pawn with a real PlayerState)")
print("=" * 100)
ctrl_done = 0
for pw in pawns:
    pc = ocls(pw)
    _, pctl = readobj(pw, pc, "Controller", REC_PAWN_CONTROLLER)
    if not pctl:
        continue
    if "AIController" in chain(ocls(pctl)):
        continue                      # that is the treatment, not the control
    _, pps = readobj(pw, pc, "PlayerState", REC_PAWN_PLAYERSTATE)
    if pps:
        dump_controller(pctl, "CONTROL (player)")
        ctrl_done += 1
        break
if not ctrl_done:
    print("!! NO player-controlled pawn with a PlayerState was found.")
    print("!! THE POSITIVE CONTROL FAILED -> every NULL printed below is UNINTERPRETABLE, not a null.\n")

print("=" * 100)
print("TREATMENT -- every AIController-derived object")
print("=" * 100)
if not aictls:
    print("none. (If a spawn was expected, this IS the result; if not, there is nothing to read.)")
for i, o in enumerate(aictls):
    dump_controller(o, "AIController[%d]" % i)

print("=" * 100)
print("THE CDOs -- what the arm pokes. `bWantsPlayerState` here is the CLASS DEFAULT.")
print("=" * 100)
if not seen_aiclasses:
    for o in aictls:
        seen_aiclasses[ocls(o)] = True
if not seen_aiclasses:
    print("no AIControllerClass observed -- nothing to read. NOT a statement about the CDO.")
for cls_ in seen_aiclasses:
    cdo = p(cls_ + CDO_OFF)
    nm = oname(cdo) if lp(cdo) else "?"
    print("class 0x%X %s   CDO@+0x%X = 0x%X '%s'%s"
          % (cls_, clsname(cls_), CDO_OFF, cdo, nm,
             "" if nm.startswith("Default__") else "   ** CDO name lacks Default__ -- SUSPECT **"))
    if lp(cdo):
        line, _ = readbool(cdo, cls_, "bWantsPlayerState", REC_WANTSPS_OFF, REC_WANTSPS_MASK)
        print("   " + line)
    print()
