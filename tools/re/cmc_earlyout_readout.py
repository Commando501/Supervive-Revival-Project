# cmc_earlyout_readout.py -- S139. Read-only RPM. NO injection, NO write, NO native call.
#
# THE QUESTION: the bot's CharacterMovementComponent tick IS entered, but the pawn never moves.
# Which rung of the ladder does the BOT fail that the PLAYER passes?
#
# This probe implements the S139 offline synthesis's ranked read plan (6 RE lanes + 6 adversarial
# verifiers over dumps/merged13.dump.exe).  That synthesis deliberately did NOT name a single cause
# -- it left TWO survivors and one byte that splits them:
#
#   S1  DeltaTime is zeroed before the engine integrates (ULokiCMC's "HitStop" branch:
#       TickComponent 0x055C2B90 `xorps xmm6,xmm6` at 0x055C2C1B, and a second identical site
#       inside ULokiCMC::PerformMovement at 0x055B83FA).  Everything downstream still RUNS -- the
#       consume, the early-outs, Acceleration, PerformMovement, even StartNewPhysics -- and the
#       engine then bails on MIN_TICK_TIME (1e-6).  Predicts: no gravity, bit-exact frozen position,
#       a MOVE_Flying poke inert.  Fits every S138 observation.
#   S2  An early-out between HasValidData (0x03603825) and ControlledCharacterMove (0x03603B18).
#
#   THE BISECTOR -- rank 1 -- is CMC+0x16C8.
#       ULokiCharacterMovementComponent::StartNewPhysics 0x055C2430, Iterations==0 path:
#           0x055C2438  cmp byte [rcx+0x16C8], 0   / je
#           0x055C2448  snapshot Velocity (CMC+0xE8/+0xF8) -> CMC+0x16B0/+0x16C0
#           0x055C2469  mov byte [rcx+0x16C8], 1        <-- the latch
#           0x055C2470  jmp 0x3600990 (engine StartNewPhysics)
#       There is NO DeltaTime test on that path, and the engine's MIN_TICK_TIME bail is DOWNSTREAM.
#       => the latch is dt-INDEPENDENT: it says "PerformMovement reached StartNewPhysics", which is
#          exactly the thing S1 and S2 disagree about.
#         1 + position frozen  => S1 (the DeltaTime kill)
#         0                    => S2 (an early-out at or above PerformMovement); reads 4/5 localise it
#
# ⚠⚠ MANDATORY IDENTITY CONTROLS, because this probe can silently read the wrong object:
#   * ALokiCharacter has its OWN live byte at +0x16C8.  A probe aimed at the PAWN instead of the
#     COMPONENT decodes to a plausible, moving, WRONG value.  So: assert CMC+0x198 == pawn.
#   * FTickFunction::Target (CMC+0x68) must equal the CMC pointer -- a free self-validating check.
#   Both are asserted before any verdict is printed; a failure prints RUN IS VOID.
#
# ⚠⚠ THE PLAYER IS A CONTAMINATED CONTROL ON EXACTLY TWO FIELDS.  The `play` shim writes CMC+0xE8
#   (Velocity) and CMC+0x328 (Acceleration) every game-thread hit (tutorial_launch.cpp:3047, :12599).
#   Use the player as a control on STRUCTURAL fields (Role, UpdatedComponent, Mobility, tick state,
#   +0x16C8) and NEVER on those two.  Also: `play-atlanding` moved the player 2,926 uu at CONSTANT
#   Z=13,240 -- it HOVERS (KFLYMODE=5).  "the player moved" never means "the player walked".
#
# ⚠ Acceleration == (0,0,0) is UNINTERPRETABLE and must not be read as a negative.  Three writers
#   produce it: ControlledCharacterMove never running; ULokiCMC::ConstrainInputAcceleration
#   0x055A75B0 storing a literal zero on a per-character predicate; and ScaleInputAcceleration
#   multiplying by GetMaxAcceleration, which is 0 when the GAS attribute set is missing.
#   Only "non-zero AND collinear with the wander direction" is informative.
#
#   usage: cmc_earlyout_readout.py <PID> <BASE-hex> [--watch SECONDS]
import ctypes
import struct
import sys
import time
from ctypes import wintypes

argv, WATCH = [], 0.0
i = 0
_a = sys.argv[1:]
while i < len(_a):
    if _a[i] == "--watch":
        WATCH = float(_a[i + 1]); i += 2
    else:
        argv.append(_a[i]); i += 1
if len(argv) < 2:
    print("usage: cmc_earlyout_readout.py <PID> <BASE-hex> [--watch SECONDS]")
    sys.exit(2)
PID, BASE = int(argv[0], 0), int(argv[1], 16)

NAMEPOOL = BASE + 0x9D81450
OBJOBJECTS = BASE + 0x9E38930
PERCHUNK, STRIDE = 65536, 0x18
CLASS_OFF, NAME_OFF, SUPER_OFF, FLAGS_OFF = 0x18, 0x20, 0x48, 0x0C
CHILDPROPS_OFF, FIELD_NEXT, FPROP_OFFSET = 0x58, 0x18, 0x44

# ⚠⚠ THIS BUILD'S EMovementMode IS MODIFIED -- MOVE_Dashing is INSERTED at index 6, so MOVE_Custom
#   is 7 and MOVE_MAX is 8.  [M, S139, three instruments: the .rdata enumerator run at 0x07E10660;
#   StartNewPhysics's 8-entry jump table at 0x03600BF8 bounded by `cmp esi,7`, case 6 -> disp 0xCC8
#   (PhysDashing) and case 7 -> disp 0x990 (PhysCustom); and IsDashing 0x035E6810 =
#   `cmp byte [rcx+0x231],6`.]  A probe carrying stock UE's MOVE_Custom==6 mis-decodes by one.
EMOVE = {0: "MOVE_None", 1: "MOVE_Walking", 2: "MOVE_NavWalking", 3: "MOVE_Falling",
         4: "MOVE_Swimming", 5: "MOVE_Flying", 6: "MOVE_Dashing(LOKI)", 7: "MOVE_Custom", 8: "MOVE_MAX"}
EROLE = {0: "ROLE_None", 1: "ROLE_SimulatedProxy", 2: "ROLE_AutonomousProxy", 3: "ROLE_Authority"}
EMOB = {0: "Static", 1: "Stationary", 2: "Movable"}

# Non-reflected members: authority is the disassembly cited beside each.  Everything else is by name.
O = {
    "cmc.latch":      0x16C8,   # ULokiCMC::StartNewPhysics 0x055C2469 `mov byte [rcx+0x16C8],1`
    "cmc.velsnap":    0x16B0,   # 0x055C2448, FVector snapshot of Velocity at that moment
    "cmc.tsfall":     0x12B0,   # TimeSinceFallingStart; ULokiCMC::PerformMovement 0x055B840C addss
    "cmc.charowner":  0x198,    # HasValidData 0x035E64C0 `mov rax,[rcx+0x198]`
    "cmc.updated":    0xD0,     # HasValidData `cmp qword [rcx+0xD0],0`
    "cmc.tickTarget": 0x68,     # FTickFunction::Target  (PrimaryComponentTick at UActorComponent+0x40)
    "cmc.tickGroup":  0x48, "cmc.tickFlags": 0x4A, "cmc.tickState": 0x4B, "cmc.tickInternal": 0x60,
    "cmc.velocity":   0xE8, "cmc.accel": 0x328, "cmc.analog": 0x3D0, "cmc.maxaccel": 0x28C,
    "cmc.mode":       0x231, "cmc.runphysnoctl": 0x2E9,   # bit 0x04
    "pawn.civ":       0x418, "pawn.lastciv": 0x430,       # APawn::Internal_ConsumeMovementInputVector 0x03BACBD0
    "pawn.role":      0x160, "pawn.remoterole": 0x72, "pawn.controller": 0x400,
    "pawn.root":      0x1B0,
    "scene.mobility": 0x1BB,   # ShouldSkipUpdate 0x0364BA99 `cmp byte [rax+0x1BB],2`
    "scene.relloc":   0x158,
    "char.ascstore":  0xF00, "char.attrstore": 0xF08, "char.movEnabled": 0xB59,
    "ctl.pawn":       0x3F8, "ctl.gate": 0x6A0,   # +0x6A0 is on the CONTROLLER, not the character
    "ctl.randomdir":  0x658,
    # ---- S140 Tier 2 additions ----
    "cmc.world":      0xC0,     # UActorComponent::WorldPrivate -- engine PerformMovement exit 2
                                #   input, NEVER read live by anyone before S140 (Tier 1 1.6)
    "cmc.minanalog":  0x290,    # MinAnalogWalkSpeed -- GetMinAnalogSpeed() (vt disp 0x7C8 ->
                                #   0x035E3D20, NOT overridden) returns it for MovementMode in
                                #   {1,2,3}, and both pawns are MOVE_Falling(3). It is the THIRD
                                #   term of CalcVelocity's clamp:  Velocity := (0,0,0) every frame
                                #   iff max(GetMaxSpeed()*AnalogInputModifier, MinAnalogWalkSpeed)
                                #   < 1.0e-4  (0x035D64F2 comisd / 0x035D6520 movups [rbx+0xe8]).
                                #   *** NEVER READ LIVE -- S140 Tier 2 flight 2 died first. ***
    "cmc.jumpapex":   0x3DC,    # NumJumpApexAttempts
    "cmc.maxsimstep": 0x3E0,    # MaxSimulationTimeStep
    "cmc.maxsimiter": 0x3E4,    # MaxSimulationIterations -- engine StartNewPhysics 0x036009B5
                                #   cmp r8d,[rcx+0x3e4] / jge is a FOURTH early-out, in no S139 doc
}

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
h = k32.OpenProcess(0x1F0FFF, False, PID)


def _liveness(handle):
    """P9 (S140 T2 adjudication): OpenProcess SUCCEEDS on a dead process whose handle is still
    open, so every read then returns None and the probe prints a table of Nones that reads exactly
    like a game fact. Check GetExitCodeProcess: STILL_ACTIVE == 259. Name FK-32 on 0x0000DEAD."""
    code = wintypes.DWORD(0)
    if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
        return "UNKNOWN (GetExitCodeProcess failed)"
    if code.value == 259:
        return None
    if code.value == 0x0000DEAD:
        return ("DEAD, exit 0x0000DEAD == FK-32, the protector NtTerminateProcess kill. "
                "No artifact is produced by that class.")
    return "DEAD, exit code %d (0x%08X)" % (code.value, code.value)
if not h:
    print("OpenProcess(%d) failed -- err %d. RUN IS VOID." % (PID, ctypes.get_last_error()))
    sys.exit(1)


def rpm(a, n):
    b = (ctypes.c_ubyte * n)(); r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u8(a):
    b = rpm(a, 1); return b[0] if b else None


def u32(a):
    b = rpm(a, 4); return struct.unpack("<I", b)[0] if b else None


def u64(a):
    b = rpm(a, 8); return struct.unpack("<Q", b)[0] if b else None


def f32(a):
    b = rpm(a, 4); return struct.unpack("<f", b)[0] if b else None


def v3(a):
    b = rpm(a, 24); return struct.unpack("<ddd", b) if b else None


def lp(v):
    return bool(v) and 0x10000 < v < 0x7FFFFFFFFFFF and (v & 7) == 0


def p(a):
    v = u64(a); return v if v and lp(v) else 0


def fname(idx):
    # ⚠ THE BLOCK TABLE IS AT NAMEPOOL + 8*blk -- NOT NAMEPOOL + 0x10 + 8*blk.  The wrong form
    #   decodes EVERY name to "?", which reads exactly like "no such object exists" and cost this
    #   session one probe run.  tools/re/movementmode_readout.py has the correct form; copy it.
    if idx is None: return "?"
    blk, off = idx >> 16, idx & 0xFFFF
    bp = u64(NAMEPOOL + 8 * blk)
    if not bp: return "?"
    hd = rpm(bp + 2 * off, 2)
    if not hd: return "?"
    hv = struct.unpack("<H", hd)[0]; ln, wide = hv >> 6, hv & 1
    if ln == 0 or ln > 255: return "?"
    raw = rpm(bp + 2 * off + 2, ln * (2 if wide else 1))
    if not raw: return "?"
    try: return raw.decode("utf-16-le" if wide else "ascii", "replace")
    except Exception: return "?"


def oname(o): return fname(u32(o + NAME_OFF)) if lp(o) else "-"
def ocls(o):  return p(o + CLASS_OFF) if lp(o) else 0


def chain(c):
    out, seen = [], set()
    while lp(c) and c not in seen and len(out) < 12:
        seen.add(c); out.append(oname(c)); c = p(c + SUPER_OFF)
    return out


def findprop(cls, want):
    c, seen, wl = cls, set(), want.lower()
    while lp(c) and c not in seen:
        seen.add(c)
        f, g = p(c + CHILDPROPS_OFF), 0
        while lp(f) and g < 4000:
            g += 1
            # ⚠ An FField's FName is at +0x20, the SAME offset as a UObject's -- not +0x28.
            #   The wrong offset makes every by-name property lookup fail, which reads as
            #   "this class has no such property" and is not.
            if fname(u32(f + NAME_OFF)).lower() == wl:
                return u32(f + FPROP_OFFSET)
            f = p(f + FIELD_NEXT)
        c = p(c + SUPER_OFF)
    return None


def byname(obj, name, hard):
    """Resolve by name; return (offset, agrees_with_hardcoded)."""
    o = findprop(ocls(obj), name)
    if o is None: return hard, "NO-UPROP(using hardcoded)"
    return o, ("agrees" if o == hard else "*** DISAGREES with hardcoded 0x%X ***" % hard)


def findprop_raw(cls, want):
    """Like findprop but returns the FProperty* itself, so bitfields can be decoded."""
    c, seen, wl = cls, set(), want.lower()
    while lp(c) and c not in seen:
        seen.add(c)
        f, g = p(c + CHILDPROPS_OFF), 0
        while lp(f) and g < 4000:
            g += 1
            if fname(u32(f + NAME_OFF)).lower() == wl:
                return f
            f = p(f + FIELD_NEXT)
        c = p(c + SUPER_OFF)
    return 0


def read_bool_uprop(obj, cls, name):
    """Decode a UHT BITFIELD bool by reading the LIVE FBoolProperty.

    ⚠ FBoolPropertyParams (the .rdata record) carries NO ByteOffset/ByteMask -- the engine derives
      them by calling the record's SetBitFunc on a zeroed buffer.  That is the repo's documented S132
      trap.  The only sound offline-free route is the LIVE FBoolProperty object, whose
      FieldSize/ByteOffset/ByteMask/FieldMask sit at +0x70..+0x73.
    Returns (value, "how") or (None, why).
    """
    fp = findprop_raw(cls, name)
    if not lp(fp):
        return None, "no UPROPERTY '%s'" % name
    base = u32(fp + FPROP_OFFSET)
    bo = u8(fp + 0x71)
    bm = u8(fp + 0x72)
    if base is None or bo is None or bm is None:
        return None, "FBoolProperty unreadable"
    b = u8(obj + base + bo)
    if b is None:
        return None, "byte @+0x%X unreadable" % (base + bo)
    return (1 if (b & bm) else 0), "byte@+0x%X mask 0x%02X raw 0x%02X" % (base + bo, bm, b)


def objects():
    arr, num = p(OBJOBJECTS), u32(OBJOBJECTS + 0x14)
    if not lp(arr) or not num or num > 4000000: return
    for i2 in range(num):
        ch = p(arr + 8 * (i2 // PERCHUNK))
        if not lp(ch): continue
        o = u64(ch + STRIDE * (i2 % PERCHUNK))
        if o and lp(o): yield o


def find_actors():
    bot = botc = plr = plrc = None
    for o in objects():
        c = ocls(o)
        if not c: continue
        nm = oname(o)
        if nm.startswith("Default__"): continue
        ch = chain(c)
        # ⚠ Match "LokiPlayerController", the form tools/re/movementmode_readout.py proves works on
        #   this build; accept a bare "PlayerController" too, but never a SUBSTRING match (the repo's
        #   documented class-lookup blind spot -- obj_by_class.py's substring form silently picks the
        #   wrong object, and PC_MainMenu_C is the standing counter-example).
        if "LokiBotController" in ch:
            if lp(p(o + O["ctl.pawn"])): botc = o
        elif ("LokiPlayerController" in ch or "PlayerController" in ch):
            if lp(p(o + O["ctl.pawn"])): plrc = o
    if botc: bot = p(botc + O["ctl.pawn"])
    if plrc: plr = p(plrc + O["ctl.pawn"])
    return bot, botc, plr, plrc


def read_side(pawn, ctl, tag):
    r = {"tag": tag, "pawn": pawn, "ctl": ctl, "void": None}
    if not lp(pawn):
        r["void"] = "no pawn"; return r
    r["pawn.class"] = oname(ocls(pawn))
    r["ctl.class"] = oname(ocls(ctl)) if lp(ctl) else "-"
    cmcoff = findprop(ocls(pawn), "CharacterMovement")
    if cmcoff is None:
        r["void"] = "no CharacterMovement UPROPERTY"; return r
    cmc = p(pawn + cmcoff)
    r["cmc"], r["cmc.off"] = cmc, cmcoff
    if not lp(cmc):
        r["void"] = "CharacterMovement is NULL"; return r
    r["cmc.class"] = oname(ocls(cmc))

    # ---- MANDATORY IDENTITY CONTROLS (before any verdict) ----
    co = p(cmc + O["cmc.charowner"])
    r["CTRL.CharacterOwner==pawn"] = (co == pawn)
    r["cmc.CharacterOwner"] = co
    tt = p(cmc + O["cmc.tickTarget"])
    r["CTRL.tickTarget==cmc"] = (tt == cmc)
    r["cmc.tickTarget"] = tt
    if not r["CTRL.CharacterOwner==pawn"]:
        r["void"] = ("IDENTITY CONTROL FAILED: CMC+0x198 (0x%X) != pawn (0x%X). "
                     "Probably reading the PAWN not the COMPONENT -- ALokiCharacter has its own "
                     "live byte at +0x16C8. RUN IS VOID for this side." % (co, pawn))
        return r

    # ---- RANK 1: the bisector ----
    r["R1.latch@0x16C8"] = u8(cmc + O["cmc.latch"])
    r["R1.velsnap@0x16B0"] = v3(cmc + O["cmc.velsnap"])
    # ---- RANK 2: the DeltaTime receipt ----
    r["R2.TimeSinceFallingStart@0x12B0"] = f32(cmc + O["cmc.tsfall"])
    # ---- RANK 3: the premise (consume ran) ----
    r["R3.ControlInputVector@0x418"] = v3(pawn + O["pawn.civ"])
    r["R3.LastControlInputVector@0x430"] = v3(pawn + O["pawn.lastciv"])
    # ---- RANK 4: HasValidData / ShouldSkipUpdate terms ----
    uo, ua = byname(cmc, "UpdatedComponent", O["cmc.updated"])
    upd = p(cmc + uo)
    r["R4.UpdatedComponent"] = upd
    r["R4.UpdatedComponent.byname"] = "@0x%X %s" % (uo, ua)
    fl = u32(pawn + FLAGS_OFF)
    r["R4.pawn RF_Garbage(bit30)"] = ((fl >> 30) & 1) if fl is not None else None
    if lp(upd):
        r["R4.UpdatedComponent.class"] = oname(ocls(upd))
        r["R4.Mobility@0x1BB"] = u8(upd + O["scene.mobility"])
        # ---- ★ THE ONE UNMEASURED ENGINE GATE ----
        # engine UCharacterMovementComponent::PerformMovement 0x035E9EC0:
        #   0x035E9FB5 call [UpdatedComponent_vtable + 0x4C0]   ; IsSimulatingPhysics(NAME_None)
        #   0x035E9FBD jne 0x035EB7CF                           ; BAIL -> StartNewPhysics never runs
        # Its two sibling gates (MovementMode +0x231 != MOVE_None, Mobility +0x1BB == Movable) are
        # already measured PASSING on both pawns, so this is the last one standing.
        ucls = ocls(upd)
        bi = findprop(ucls, "BodyInstance")
        r["R6.BodyInstance.off"] = ("@+0x%X" % bi) if bi is not None else "NOT RESOLVED"
        if bi is not None:
            bistruct = findprop_raw(ucls, "BodyInstance")
            inner = p(bistruct + 0x70) if lp(bistruct) else 0   # FStructProperty::Struct
            for nm in ("bSimulatePhysics", "bEnableGravity", "bNotifyRigidBodyCollision"):
                if lp(inner):
                    v, how = read_bool_uprop(upd + bi, inner, nm)
                else:
                    v, how = None, "inner UScriptStruct unresolved"
                r["R6." + nm] = v
                r["R6." + nm + ".how"] = how
    # ---- RANK 5: role / controller ----
    r["R5.Role@0x160"] = u8(pawn + O["pawn.role"])
    r["R5.RemoteRole@0x72"] = u8(pawn + O["pawn.remoterole"])
    r["R5.Controller@0x400"] = p(pawn + O["pawn.controller"])
    b = u8(cmc + O["cmc.runphysnoctl"])
    r["R5.bRunPhysicsWithNoController(0x2E9&4)"] = (None if b is None else (b & 4) >> 2)
    # ---- RANK 7: acceleration (POSITIVE ARM ONLY) ----
    r["R7.Acceleration@0x328"] = v3(cmc + O["cmc.accel"])
    r["R7.AnalogInputModifier@0x3D0"] = f32(cmc + O["cmc.analog"])
    r["R7.MaxAcceleration@0x28C"] = f32(cmc + O["cmc.maxaccel"])
    # ---- RANK 8: GAS gates ----
    r["R8.AbilitySystemComponentStorage@0xF00"] = p(pawn + O["char.ascstore"])
    r["R8.AttributeSetStorage@0xF08"] = p(pawn + O["char.attrstore"])
    r["R8.bCharacterMovementEnabled@0xB59"] = u8(pawn + O["char.movEnabled"])
    # ---- RANK 10: tick function state ----
    r["R10.TickState@0x4B"] = u8(cmc + O["cmc.tickState"])
    tf = u8(cmc + O["cmc.tickFlags"])
    r["R10.bCanEverTick(0x4A&2)"] = (None if tf is None else (tf & 2) >> 1)
    idp = p(cmc + O["cmc.tickInternal"])
    r["R10.InternalData@0x60"] = idp
    r["R10.bRegistered(*InternalData bit0)"] = ((u32(idp) or 0) & 1) if lp(idp) else "InternalData NULL => NEVER REGISTERED"
    # misc
    # ---- S140 Tier 2: RAW FIRST. A formatted double print hides a signed zero, and that exact
    #      defect cost S139 flight 3 its finding for an hour. Record bytes; derive afterwards.
    r["S140.payload@0x16B0 RAW"] = hex24(cmc + O["cmc.velsnap"])
    r["S140.Velocity@0xE8 RAW"] = hex24(cmc + O["cmc.velocity"])
    r["S140.WorldPrivate@0xC0"] = p(cmc + O["cmc.world"])
    r["S140.MinAnalogWalkSpeed@0x290"] = f32(cmc + O["cmc.minanalog"])
    r["S140.NumJumpApexAttempts@0x3DC"] = u32(cmc + O["cmc.jumpapex"])
    r["S140.MaxSimulationTimeStep@0x3E0"] = f32(cmc + O["cmc.maxsimstep"])
    r["S140.MaxSimulationIterations@0x3E4"] = u32(cmc + O["cmc.maxsimiter"])
    r["S140.vptr"] = p(cmc)
    r["S140.vptr is ULokiCMC"] = (r["S140.vptr"] == BASE + 0x088F8570)
    r["S140.vptr is engine UCMC"] = (r["S140.vptr"] == BASE + 0x07FBED58)
    r["MovementMode@0x231"] = u8(cmc + O["cmc.mode"])
    r["Velocity@0xE8 (CONTAMINATED on player)"] = v3(cmc + O["cmc.velocity"])
    root = p(pawn + O["pawn.root"])
    r["location"] = v3(root + O["scene.relloc"]) if lp(root) else None
    if lp(ctl) and "LokiBotController" in chain(ocls(ctl)):
        r["ctl.gate@0x6A0(CONTROLLER)"] = u8(ctl + O["ctl.gate"])
        r["ctl.RandomMoveDirection@0x658"] = v3(ctl + O["ctl.randomdir"])
    return r


# ---- S140 Tier 2: the payload-poison / sentinel vocabulary. These MUST match tutorial_launch.cpp
#      ARM H (kShBotPoison / kShPlrPoison / kShSentinel) or the recogniser is silently useless.
SENT_BOT_POISON = (-9876.5, -8765.25, -7654.125)
SENT_PLR_POISON = (-1234.5, -2345.25, -3456.125)
SENT_VALUE      = (0.0009765625, 0.0, 0.0)
ZERO3           = (0.0, 0.0, 0.0)


def hex24(a):
    b = rpm(a, 24)
    if not b:
        return "<unreadable>"
    return "|".join(b[i:i + 8].hex().upper() for i in range(0, 24, 8))


def fmt(v):
    if v is None: return "None"
    if isinstance(v, bool): return "YES" if v else "*** NO ***"
    if isinstance(v, tuple): return "(%.3f,%.3f,%.3f)" % v
    if isinstance(v, float): return "%.6g" % v
    if isinstance(v, int): return ("0x%X" % v) if v > 0xFFFF else str(v)
    return str(v)


def main():
    dead = _liveness(h)
    if dead:
        print("!! PROCESS IS NOT RUNNING -- %s" % dead)
        print("!! RUN IS VOID. Every read below would be None and would read like a game fact.")
        return
    mz = rpm(BASE, 2)
    if mz != b"MZ":
        print("!! NO MZ AT BASE=0x%X (read %r) -- the BASE argument is wrong, or the module moved."
              % (BASE, mz))
        print("!! RUN IS VOID -- an image-relative check (the vptr test) cannot mean anything.")
        return
    bot, botc, plr, plrc = find_actors()
    print("=" * 118)
    print("cmc_earlyout_readout (S139 ranked plan)   PID=%d BASE=0x%X   %s"
          % (PID, BASE, time.strftime("%Y-%m-%d %H:%M:%S")))
    print("  bot pawn=0x%X ctl=0x%X | player pawn=0x%X ctl=0x%X" % (bot or 0, botc or 0, plr or 0, plrc or 0))
    print("=" * 118)
    if not lp(plr):
        # P1 (S140 T2 adjudication): this used to `return`, DISCARDING THE ENTIRE BOT RESULT when
        # the player was not found. The player is a CONTROL, not a precondition -- losing it
        # weakens the reading, it does not void the treatment. Warn loudly and continue.
        print("!! NO PLAYER-CONTROLLED PAWN -- the two-sided control is MISSING and every")
        print("!! player column below is meaningless. The BOT reading still stands on its own")
        print("!! internal controls; say so explicitly in any write-up.")
    A = read_side(bot, botc, "BOT") if lp(bot) else {"tag": "BOT", "void": "no bot (inject the arm first)"}
    B = read_side(plr, plrc, "PLAYER")
    for r in (A, B):
        if r.get("void"):
            print("  [%s] VOID: %s" % (r["tag"], r["void"]))
    keys = [k for k in A if k not in ("tag", "void")]
    for k in B:
        if k not in keys and k not in ("tag", "void"): keys.append(k)
    print("%-46s | %-27s | %-27s" % ("field", "BOT", "PLAYER (control)"))
    print("-" * 118)
    for k in keys:
        print("%-46s | %-27s | %-27s" % (k, fmt(A.get(k))[:27], fmt(B.get(k))[:27]))
    print("-" * 118)
    for side, r in (("bot", A), ("plr", B)):
        mm, rl, mb = r.get("MovementMode@0x231"), r.get("R5.Role@0x160"), r.get("R4.Mobility@0x1BB")
        print("  %s: MovementMode=%s  Role=%s  Mobility=%s"
              % (side, EMOVE.get(mm, mm), EROLE.get(rl, rl), EMOB.get(mb, mb)))

    print()
    print("### RANK-1 -- RETRACTED (S140 Tier 1). THE LATCH IS NOT AN INSTRUMENT. ###")
    print("  CMC+0x16C8 is NOT a sticky latch. It is a per-frame TOptional<FVector> validity flag: SET by")
    print("  ULokiCMC::StartNewPhysics at 0x055C2469 and CLEARED later in the SAME engine PerformMovement")
    print("  call by ULokiCMC vtable disp 0xA50 (0x0530ABF0), on a path the StartNewPhysics call site")
    print("  DOMINATES. An off-thread reader sees 0 whether the step runs every frame or never runs at")
    print("  all. Named from its own consumer GetRecentVelocity (.data 0x09BC9AD0 -> impl 0x0530AC10).")
    print("  See docs/s140-tier1-cfg.md 4.2-4.7.")
    print("  ==> latch == 0 proves NOTHING. The S139 verdict this probe used to print here rested on it")
    print("      and is WITHDRAWN. Raw values only:")
    print("      bot latch=%s   player latch=%s   (0 is expected in EVERY world)"
          % (fmt(A.get("R1.latch@0x16C8")), fmt(B.get("R1.latch@0x16C8"))))
    print()
    print("### S140 TIER 2 -- THE PAYLOAD RECOGNISER (the durable receipt) ###")
    print("  The PAYLOAD at CMC+0x16B0 IS durable: disp 0xA50 clears only the flag byte, and the only")
    print("  CMC-side writer of the payload is 0x055C244F inside StartNewPhysics. ARM H")
    print("  (build.ps1 -Variant gasattr-sentinel) POISONS it first, so never-written and written-with-")
    print("  zeros are DIFFERENT BYTES -- the degeneracy docs/s140-tier1-cfg.md 7 warns about.")
    for side, r, own, other in (("BOT", A, SENT_BOT_POISON, SENT_PLR_POISON),
                                ("PLAYER", B, SENT_PLR_POISON, SENT_BOT_POISON)):
        pay = r.get("R1.velsnap@0x16B0")
        vel = r.get("Velocity@0xE8 (CONTAMINATED on player)")
        if pay is None:
            print("  %-7s payload UNREADABLE -- no result." % side)
            continue
        if pay == other:
            v = "*** VOID: holds the OTHER object poison -> the CMC resolution is WRONG ***"
        elif pay == SENT_VALUE:
            v = "***** StartNewPhysics RAN -- payload holds the SENTINEL from Velocity *****"
        elif pay == own:
            v = "***** StartNewPhysics did NOT run since the poison was written *****"
        elif pay == ZERO3:
            v = ("payload is EXACT ZERO. If ARM H poisoned this object -> StartNewPhysics RAN"
                 " and snapshotted a zero Velocity. If ARM H did NOT run -> UNINTERPRETABLE:"
                 " a never-written buffer is also zero. CHECK THE MARKER FOR [SNP] FIRST.")
        else:
            v = "UNMODELLED value -- report the raw hex, do not interpret."
        print("  %-7s payload  = %-28s RAW %s" % (side, fmt(pay), r.get("S140.payload@0x16B0 RAW")))
        print("  %-7s Velocity = %-28s RAW %s" % (side, fmt(vel), r.get("S140.Velocity@0xE8 RAW")))
        print("  %-7s -> %s" % (side, v))
    print()
    print("### S140 TIER 2 -- THE THREE FREE READS (Tier 1 7, ranks 2/3/4; never taken live) ###")
    for side, r in (("BOT", A), ("PLAYER", B)):
        wp = r.get("S140.WorldPrivate@0xC0")
        msi = r.get("S140.MaxSimulationIterations@0x3E4")
        print("  %-7s WorldPrivate@0xC0 = %-20s -> %s" % (side, fmt(wp),
              "non-null; engine PerformMovement exit 2 input is satisfied"
              if (wp and wp > 0x10000) else
              "UNDECIDED -- NOT a bail. A null WorldPrivate falls to a DIRECT call 0x035AFC40 "
              "which reads OwnerPrivate@+0xB8 and OuterPrivate@+0x28; exit 2 tests WorldPrivate "
              "OR that fallback. Read those two before concluding anything."))
        _c = r.get("cmc")
        if not (wp and wp > 0x10000) and lp(_c):
            print("  %-7s   OwnerPrivate@0xB8 = %s   OuterPrivate@0x28 = %s"
                  % (side, fmt(p(_c + 0xB8)), fmt(p(_c + 0x28))))
        print("  %-7s MaxSimulationIterations@0x3E4 = %-6s -> %s" % (side, fmt(msi),
              "> 0; the 4th engine-StartNewPhysics early-out 0x036009B5 does NOT bail"
              if (isinstance(msi, int) and 0 < msi < 1000)
              else "*** <=0 or implausible -- READ THE RAW VALUE ***"))
        mas = r.get("S140.MinAnalogWalkSpeed@0x290")
        print("  %-7s MinAnalogWalkSpeed@0x290 = %-12s -> %s" % (side, fmt(mas),
              "*** >= 1e-4: the max() CANNOT fall below 1e-4, so CalcVelocity's clamp is NOT what"
              " zeroes Velocity -- the wall is elsewhere ***" if (isinstance(mas, float) and mas >= 1e-4)
              else "< 1e-4: the clamp fires iff GetMaxSpeed()*AnalogInputModifier is also < 1e-4."
                   " THIS PROBE DOES NOT READ GetMaxSpeed(). Not settled -- say so."))
        print("  %-7s MaxSimulationTimeStep@0x3E0 = %-10s NumJumpApexAttempts@0x3DC = %s"
              % (side, fmt(r.get("S140.MaxSimulationTimeStep@0x3E0")),
                 fmt(r.get("S140.NumJumpApexAttempts@0x3DC"))))
        print("  %-7s vptr = %-20s isULokiCMC=%s isEngineUCMC=%s"
              % (side, fmt(r.get("S140.vptr")), fmt(r.get("S140.vptr is ULokiCMC")),
                 fmt(r.get("S140.vptr is engine UCMC"))))
        if not r.get("S140.vptr is ULokiCMC"):
            print("  %-7s !! NOT the ULokiCMC vtable. If it is the ENGINE UCMC then disp 0x720" % side)
            print("  %-7s    is 0x03600990 and NOTHING touches +0x16C8/+0x16B0 -- TEST VOID." % side)
    print()
    print("  ⚠ Acceleration == 0 is UNINTERPRETABLE (3 independent zero-writers). Only non-zero AND")
    print("    collinear with RandomMoveDirection is informative.")
    print("  ⚠ Velocity/Acceleration on the PLAYER are CONTAMINATED if `play` is injected.")

    if WATCH > 0:
        print()
        print("### RANK-2: is TimeSinceFallingStart advancing? (%.0fs) ###" % WATCH)
        t0 = time.time()
        a0, b0 = A.get("R2.TimeSinceFallingStart@0x12B0"), B.get("R2.TimeSinceFallingStart@0x12B0")
        la0, lb0 = A.get("location"), B.get("location")
        while time.time() - t0 < WATCH:
            time.sleep(2.0)
            A2 = read_side(bot, botc, "BOT") if lp(bot) else {}
            B2 = read_side(plr, plrc, "PLAYER")
            a1, b1 = A2.get("R2.TimeSinceFallingStart@0x12B0"), B2.get("R2.TimeSinceFallingStart@0x12B0")
            la, lb = A2.get("location"), B2.get("location")
            dm = (lambda x, y: (sum((i - j) ** 2 for i, j in zip(x, y)) ** 0.5) if (x and y) else -1)
            print("  +%5.1fs  bot dt=%-12s moved=%8.2f | plr dt=%-12s moved=%8.2f"
                  % (time.time() - t0, fmt(a1), dm(la, la0), fmt(b1), dm(lb, lb0)))
        print()
        print("  READ IT AS: bot dt FROZEN + latch 1  => S1 CONFIRMED (entered with DeltaTime==0).")
        print("              bot dt ADVANCING         => S1 DEAD; the wall is inside StartNewPhysics/PhysFalling.")
        print("              bot dt FROZEN + latch 0  => AMBIGUOUS BY DESIGN -- use R4/R5, not this.")


main()
