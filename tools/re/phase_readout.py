# phase_readout.py -- read the LIVE round-phase machine. PURE READ-ONLY RPM. ARM A0 of FK-22.
#
#   usage: phase_readout.py [PID] [BASE-hex] [--gamemode 0xADDR] [--dump]
#          (PID and BASE are AUTO-DETECTED from SUPERVIVE-Win64-Shipping.exe if omitted)
#
# ==================================================================================================
# WHY (FK-22 sec.8-sec.12, docs/fk22-dropphase-reachability.md -- all offsets below are [M] from that doc)
# ==================================================================================================
# The SUPERVIVE round-phase ladder is frozen at EGP_BeginInit(1) in 193/193 corpus logs. Two NATIVE
# gates are ALREADY RUNNING and each is one condition short:
#
#   1->2  fn 0x560AF10 : MatchStartDetails non-empty (FString @ GameState+0x738; the gate is
#                        `cmp dword [rax+8],1; jle bail`, so it needs Num > 1 -- FString Num COUNTS
#                        THE NUL, so Num>1 means at least one real character)
#                        AND CurrentPhase(GameState+0xA44) == 1
#                        AND qword[GameMode+0x790] == 0        (then it writes byte[GameMode+0x7B0]=1)
#   3->4  Tick 0x5613200, RUNS EVERY FRAME : byte[GameMode+0x7C0] == 4  (the FLokiGameModeInitializer
#                        stage -- ALREADY TRUE in real runs, 189-193 corpus confirmations)
#                        AND CurrentPhase == 3
#
# So the single byte at GameState+0xA44 is the whole difference between a frozen ladder and a
# running one. THIS PROBE READS IT, plus every other term of both gates, plus the one number that
# decides whether arm A5 (BP_AuthSetCurrentPhase) can do anything at all: the subscriber count of
# OnRoundPhaseChanged.
#
# THIS FILE WRITES NOTHING. The process handle is opened with PROCESS_VM_READ|QUERY_INFORMATION
# only -- WriteProcessMemory cannot succeed through it even if a future edit tried.
#
# ==================================================================================================
# LAYOUT [M]  (source: FK-22 sec.9.1 / sec.10.3 / sec.11, each pinned by disassembly)
# ==================================================================================================
#   GameMode  -> GameState                : [GameMode+0x258]   (the offset OnNewPhase itself uses at
#                                            0x5608FB8; ALSO cross-checked here BY REFLECTION NAME)
#   GameState.CurrentPhase        +0xA44  uint8   (GetCurrentPhase impl = `movzx eax,[rcx+0xA44]; ret`)
#   GameState.OnRoundPhaseChanged +0x590  FNewRoundPhase -- a DYNAMIC MULTICAST:
#                                            +0x590 FScriptDelegate* Data
#                                            +0x598 int32 Num          <-- the number arm A5 needs
#                                            +0x59C int32 Max
#                                         (BP_AuthSetCurrentPhase impl = `add rcx,0x590; jmp 0x442B4C0`;
#                                          0x1342340 reads Num at [rcx+8], walks at STRIDE 16 and
#                                          dispatches `call [r9+0x270]` = ProcessEvent. The broadcast
#                                          is a HARD NO-OP when Num <= 0.)
#   GameState.MatchStartDetails   +0x738  FString {Data@+0x00, Num@+0x08, Max@+0x0C}
#                                         (+0x748 is a TArray the same writer copies into)
#   GameMode  +0x790  qword  (1->2 gate: must be 0)
#   GameMode  +0x7B0  byte   (1->2 gate WRITES 1 here -- a 1 means that gate already fired)
#   GameMode  +0x7C0  byte   (FLokiGameModeInitializer stage; 3->4 gate needs == 4)
#
#   ERoundPhase [M, read out of the 10-dword table at .text 0x56012B8]:
#     0 ServerStartup  1 BeginInit  2 Pre  3 FinishInit  4 SpawnSelect
#     5 SpawnReveal    6 Lineup     7 Combat  8 Post     9 Shutdown
#
# ==================================================================================================
# HOW THIS PROBE TRIES NOT TO BE ANOTHER INSTRUMENT ARTIFACT
# ==================================================================================================
# 1. ★ THE CLASS-LOOKUP BLIND-SPOT FAMILY HAS FIVE KNOWN MEMBERS -- obj_by_class.py (substring),
#    cheat_reach_probe.py (endswith), class_props.py (class-of-class=="Class" fails on a
#    BlueprintGeneratedClass), bpframe_readout.py (TAKES THE FIRST MATCH when 3 objects share a
#    class), and the widget-archetype trap. The shared defect is "take the first match"; the shared
#    fix is "enumerate and show your work". So this probe ENUMERATES EVERY object whose CLASS
#    DERIVATION CHAIN reaches a *GameMode / *GameState / World class, prints all of them with their
#    full chain and a CDO/archetype tag, and prints the per-candidate GameState link for each. It
#    matches on the SUPER CHAIN, not on the leaf name, so BP_LokiGameMode_Tutorial_C is found
#    without knowing its name.
# 2. ★ THE +0x258 HOP IS VALIDATED SIX WAYS, not trusted, and the list here is the list the code
#    actually runs (an earlier draft's header named five checks that were not the five implemented):
#      (a) the pointer is sane;
#      (b) it is present in the live GUObjectArray -- POINTER EQUALITY, name-free;
#      (c) its vtable is inside the main module;
#      (d) its UClass chain reaches a *GameState;
#      (e) the GameMode class's OWN reflected `GameState` UPROPERTY declares +0x258;
#      (f) it equals some UWorld's reflected `GameState` -- docs/fk22:629's own prescribed
#          derivation, so this is the check that would catch a stale GameMode from a prior world.
#    (a)-(d) are CORE and decide `gs_valid`; (e)/(f) are corroboration and are reported separately
#    because they can be legitimately absent. Every check is PRINTED, pass / fail / ABSENT --
#    and an ABSENT check is never rendered as a passing one.
# 3. ★ MANDATORY POSITIVE CONTROL, printed before anything else: FUObjectArray's disregard-for-GC
#    header at BASE+0x9E38920 (MaxObjectsNotConsideredByGC == 45000 [M], FK-27 successor / S123),
#    plus a live FName decode and the root-registry receipt. If those fail, an all-zero phase
#    readout means WRONG PROCESS / WRONG BASE, not "the ladder is frozen". Without this, a bad
#    attach is indistinguishable from the very result we are looking for.
# 4. ★ REFLECTION CROSS-CHECK of the hardcoded offsets: CurrentPhase / MatchStartDetails /
#    OnRoundPhaseChanged are ALSO resolved by walking the live UClass property chain, and EVERY
#    match is printed. This matters specifically here: FK-22 sec.9.1 records that TWO FPropertyParams
#    records name "CurrentPhase" (0xF48 and 0xA44), so a name-based resolve is AMBIGUOUS on its own
#    and the disassembly (`movzx eax,[rcx+0xA44]`) is what disambiguates. This probe therefore uses
#    0xA44 as primary and prints the reflection answer BESIDE it rather than instead of it.
# 5. ★ THE DELEGATE IS READ BOTH WAYS AND THE READING IS ARGUED FROM THE BYTES. FK-15 established
#    that a SINGLE-CAST FDelegateBase is {void* Alloc; int32 DelegateSize; pad} and that "entries=3"
#    was NEVER a subscriber count. FK-22 sec.10.3 establishes that THIS one is a dynamic multicast
#    (TArray<FScriptDelegate>, stride 16). Both decodes are printed side by side, and the multicast
#    reading is CORROBORATED LIVE by walking the entries and requiring each FScriptDelegate.Object
#    to be a real enumerated UObject with a decodable FunctionName. If that walk fails, the count is
#    reported AMBIGUOUS -- because arm A5 hangs on this number and an ambiguous read must not be
#    laundered into a decision.
#
# ==================================================================================================
# BLIND SPOTS OF THIS PROBE (also re-printed at the end of every run)
# ==================================================================================================
#  * It is a SNAPSHOT. Num == 0 now does not mean nothing ever subscribes; the tutorial mode binds
#    OnRoundPhaseChanged inside ReceiveBeginPlay behind ULokiBlueprintLibrary::ServerOnly. Re-run it
#    at the moment you intend to call, not once at staging.
#  * NO GAMEMODE FOUND is a statement about STAGING, never about the phase machine. At the main menu
#    there is no round GameMode at all, and a zero-filled report there means nothing.
#  * The gate conditions are transcribed from offline disassembly of a 54.95 %-decrypted image. This
#    probe can prove a condition is UNMET; it cannot prove the gate list is complete.
#  * GameMode +0x790 / +0x7B0 / +0x7C0 are almost certainly NOT reflected UPROPERTYs; the reverse
#    lookup printed for them will usually be empty and that is expected, not a failure.
#  * The FLokiGameModeInitializer stage NAMES (Starting/Priming/MemoryReport/WaitingForClientsReady/
#    Finished) are [I], inferred from log ORDER. Only the number matters to the gate: it needs 4.
import ctypes
import sys
from ctypes import wintypes

# ---- stdout hardening. NOT cosmetic. ------------------------------------------------------------
# FName and FString content is arbitrary UTF-16 read out of the game, and a redirected stdout on
# Windows defaults to cp1252 -- printing one non-cp1252 character there raises UnicodeEncodeError
# and kills the run PART-WAY THROUGH THE REPORT, which during an armed window costs the window.
# MEASURED: an earlier draft of this file died exactly that way the first time its output was piped.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROCNAME = "SUPERVIVE-Win64-Shipping.exe"

# ---- this build's constants (tutorial_launch.cpp:23-25, docs/fk27-successor-gc-rooting-settled.md)
RVA_NAMEPOOL = 0x9D81450
RVA_OBJOBJECTS = 0x9E38930          # FUObjectArray + 0x10 == the inner ObjObjects
RVA_FUOBJECTARRAY = 0x9E38920       # the OUTER array; the disregard fields live here
RVA_ROOT_ARRAYNUM = 0x99D3CA8       # root registry TSparseArray ArrayNum
RVA_ROOT_FREEIDX = 0x99D3CD4        # ... NumFreeIndices ; Num() = ArrayNum - NumFreeIndices
PERCHUNK = 65536
STRIDE = 0x18                       # FUObjectItem

# ---- object/field layout for THIS build (docs/findings.md: nameOff=0x20, classOff=0x18) ----------
OFF_OBJ_CLASS = 0x18
OFF_OBJ_NAME = 0x20
OFF_STRUCT_SUPER = 0x48
OFF_STRUCT_CHILDPROPS = 0x58
OFF_FIELD_NEXT = 0x18
OFF_PROP_OFFSET = 0x44

# ---- the FK-22 offsets under test ---------------------------------------------------------------
GM_TO_GS = 0x258
GS_CURRENTPHASE = 0xA44
GS_DELEGATE = 0x590
GS_MATCHSTART = 0x738
GM_790 = 0x790
GM_7B0 = 0x7B0
GM_7C0 = 0x7C0

EROUNDPHASE = ["ServerStartup", "BeginInit", "Pre", "FinishInit", "SpawnSelect",
               "SpawnReveal", "Lineup", "Combat", "Post", "Shutdown"]
# [I] from log ORDER only -- the gate cares about the NUMBER 4, not the name.
INITIALIZER_STAGE = ["Starting?", "Priming?", "MemoryReport?", "WaitingForClientsReady?", "Finished?"]

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
READ_ONLY_ACCESS = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION   # <-- deliberately NOT 0x1F0FFF

# ==================================================================================================
# argv
# ==================================================================================================
args = sys.argv[1:]
DUMP = "--dump" in args         # extra raw hex windows around each field
GM_OVERRIDE = None
if "--gamemode" in args:
    # Guarded: a typo on the documented AMBIGUOUS-recovery path must not produce a bare traceback
    # with no `summary: status=` line, which is what an operator (and any harness) parses.
    i = args.index("--gamemode")
    if i + 1 >= len(args):
        print("--gamemode needs a hex address, e.g. --gamemode 0x1234ABCD")
        print("summary: status=BAD-ARGS")
        sys.exit(1)
    try:
        GM_OVERRIDE = int(args[i + 1], 16)
    except ValueError:
        print(f"--gamemode: {args[i + 1]!r} is not a hex address")
        print("summary: status=BAD-ARGS")
        sys.exit(1)
    if GM_OVERRIDE <= 0:
        print("--gamemode: address must be non-zero")
        print("summary: status=BAD-ARGS")
        sys.exit(1)
    del args[i:i + 2]
args = [a for a in args if not a.startswith("--")]
try:
    ARG_PID = int(args[0], 0) if len(args) > 0 else None
    ARG_BASE = int(args[1], 16) if len(args) > 1 else None
except ValueError:
    print("usage: phase_readout.py [PID] [BASE-hex] [--gamemode 0xADDR] [--dump]")
    print("summary: status=BAD-ARGS")
    sys.exit(1)

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wintypes.BOOL
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE


class PE32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


class ME32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]


def autodetect_pid():
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if snap == wintypes.HANDLE(-1).value:
        return None
    e = PE32W()
    e.dwSize = ctypes.sizeof(PE32W)
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    found = None
    while ok:
        if e.szExeFile == PROCNAME:
            found = e.th32ProcessID
            break
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return found


def autodetect_module(pid):
    snap = k32.CreateToolhelp32Snapshot(0x18, pid)
    if snap == wintypes.HANDLE(-1).value:
        return None, None
    e = ME32W()
    e.dwSize = ctypes.sizeof(ME32W)
    ok = k32.Module32FirstW(snap, ctypes.byref(e))
    base = size = None
    while ok:
        if e.szModule == PROCNAME:
            base = ctypes.cast(e.modBaseAddr, ctypes.c_void_p).value
            size = e.modBaseSize
            break
        ok = k32.Module32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return base, size


PID = ARG_PID if ARG_PID is not None else autodetect_pid()
if not PID:
    print(f"could not find '{PROCNAME}' -- is the game running?")
    print("summary: status=NO-PROCESS")
    sys.exit(1)

_base, _size = autodetect_module(PID)
BASE = ARG_BASE if ARG_BASE is not None else _base
MODSIZE = _size if _size else 0x0B000000    # the span tutorial_launch.cpp's GcAlive() uses
if not BASE:
    print("could not resolve the module base -- pass it explicitly (arg 2)")
    print("summary: status=NO-BASE")
    sys.exit(1)

h = k32.OpenProcess(READ_ONLY_ACCESS, False, PID)
if not h:
    print(f"OpenProcess(PROCESS_VM_READ|QUERY_INFORMATION) failed err={ctypes.get_last_error()} "
          f"-- run elevated")
    print("summary: status=NO-HANDLE")
    sys.exit(1)

NAMEPOOL = BASE + RVA_NAMEPOOL
OBJOBJECTS = BASE + RVA_OBJOBJECTS
FUOBJARR = BASE + RVA_FUOBJECTARRAY


# ==================================================================================================
# read-only primitives
# ==================================================================================================
def rpm(a, n):
    b = (ctypes.c_ubyte * n)()
    r = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(a), b, n, ctypes.byref(r)) or r.value != n:
        return None
    return bytes(b)


def u32(b, o): return int.from_bytes(b[o:o + 4], "little")
def i32(b, o): return int.from_bytes(b[o:o + 4], "little", signed=True)
def u64(b, o): return int.from_bytes(b[o:o + 8], "little")
def lp(v): return 0x10000 <= v < 0x0001000000000000 and (v & 7) == 0


def p(a):
    b = rpm(a, 8)
    return u64(b, 0) if b else 0


def hexdump(b):
    return " ".join(f"{x:02X}" for x in b) if b else "<UNREADABLE>"


_nc = {}


def fname(i):
    if i in _nc:
        return _nc[i]
    blk = i >> 16
    off = (i & 0xFFFF) << 1
    bp = rpm(NAMEPOOL + blk * 8, 8)
    r = "?"
    if bp:
        bp = int.from_bytes(bp, "little")
        if lp(bp):
            hd = rpm(bp + off, 2)
            if hd:
                hd = int.from_bytes(hd, "little")
                ln = hd >> 6
                w = hd & 1
                if 0 < ln < 250:
                    s = rpm(bp + off + 2, ln * (2 if w else 1))
                    if s:
                        r = ("".join(chr(s[k * 2] | (s[k * 2 + 1] << 8)) for k in range(ln))
                             if w else s.decode("latin1", "replace"))
    _nc[i] = r
    return r


def oname(o):
    b = rpm(o + OFF_OBJ_NAME, 4)
    return fname(u32(b, 0)) if b else "?"


def ftype(f):
    fc = p(f + 0x08)
    if not lp(fc):
        return "?"
    b = rpm(fc, 4)
    return fname(u32(b, 0)) if b else "?"


def fstring(a):
    """FString {void* Data; int32 Num; int32 Max}. Returns (text, data, num, max, raw16)."""
    b = rpm(a, 16)
    if not b:
        return (None, 0, None, None, None)
    d = u64(b, 0)
    n = i32(b, 8)
    m = i32(b, 12)
    if n <= 0 or not lp(d) or n > 8192:
        return ("", d, n, m, b)
    s = rpm(d, n * 2)
    if not s:
        return (None, d, n, m, b)
    txt = "".join(chr(s[i * 2] | (s[i * 2 + 1] << 8)) for i in range(n)).rstrip("\x00")
    return (txt, d, n, m, b)


def props_of(struct_ptr, limit=2000):
    """[(name, type, offset)] over the WHOLE super chain."""
    out = []
    cur = struct_ptr
    lvl = 0
    while lp(cur) and lvl < 16:
        f = p(cur + OFF_STRUCT_CHILDPROPS)
        i = 0
        while lp(f) and i < limit:
            raw = rpm(f, 0x80)
            if not raw:
                break
            out.append((oname(f), ftype(f), i32(raw, OFF_PROP_OFFSET), oname(cur)))
            f = p(f + OFF_FIELD_NEXT)
            i += 1
        cur = p(cur + OFF_STRUCT_SUPER)
        lvl += 1
    return out


_chain = {}


def chain_of(cls):
    """['BP_LokiGameMode_Tutorial_C', 'LokiTutorialGameMode', ...] -- cached per UClass pointer."""
    if cls in _chain:
        return _chain[cls]
    out = []
    cur = cls
    lvl = 0
    while lp(cur) and lvl < 16:
        out.append(oname(cur))
        cur = p(cur + OFF_STRUCT_SUPER)
        lvl += 1
    _chain[cls] = out
    return out


def in_module(v):
    return BASE <= v < BASE + MODSIZE


def is_archetype(nm):
    return nm.startswith("Default__") or "GEN_VARIABLE" in nm


# ==================================================================================================
# 0. POSITIVE CONTROL -- MANDATORY. Printed FIRST so nothing below can be read without it.
# ==================================================================================================
print("=" * 96)
print(f"phase_readout -- PURE READ-ONLY RPM (no writes; handle = VM_READ|QUERY_INFORMATION only)")
print(f"pid={PID}  base=0x{BASE:X}  modsize=0x{MODSIZE:X}")
print("=" * 96)
print("\n[PC] POSITIVE CONTROL -- these must pass, or an empty phase readout below means")
print("[PC] WRONG PROCESS / WRONG BASE rather than 'the ladder is frozen'.")
print("[PC] (part 1 here; the FName check and the VERDICT come right after the sweep.)")

pc_fail = []
pc_warn = []

dg = rpm(FUOBJARR, 0x28)
if not dg:
    print(f"[PC]   FUObjectArray @ base+0x{RVA_FUOBJECTARRAY:X} : UNREADABLE")
    pc_fail.append("fuobjectarray-unreadable")
    objectsPtr = numEl = 0
else:
    firstGC = i32(dg, 0x00)
    lastNonGC = i32(dg, 0x04)
    maxNoGC = i32(dg, 0x08)
    openDis = i32(dg, 0x0C)
    # ⚠⚠ OFFSET DISCIPLINE, and this exact line shipped WRONG once (S124 review, BLOCKER).
    # The inner FChunkedFixedUObjectArray `ObjObjects` starts at FUObjectArray+0x10, so relative to
    # the OUTER array its fields are:  Objects @ +0x10 (== RVA_OBJOBJECTS+0x00)
    #                                  NumElements @ +0x24 (== RVA_OBJOBJECTS+0x14)
    # Every sibling probe reads them at RVA_OBJOBJECTS+0x00 / +0x14 (item_watch.py:209-212,
    # bpframe_all.py:105, regions_readout.py, class_props.py). An earlier draft of this file read
    # NumElements at OUTER+0x14 -- which is the HIGH DWORD of the Objects pointer -- and therefore
    # swept only the first ~466 slots of ~200,000, i.e. the disregard-for-GC bootstrap objects, and
    # reported "NO LIVE GameMode" on a perfectly staged world. Do not "simplify" these two lines.
    objectsPtr = u64(dg, 0x10)
    numEl = u32(dg, 0x24)
    print(f"[PC]   raw base+0x{RVA_FUOBJECTARRAY:X} : {hexdump(dg)}")
    print(f"[PC]   MaxObjectsNotConsideredByGC = {maxNoGC:<8} expect 45000   "
          f"{'PASS' if maxNoGC == 45000 else 'FAIL'}   <- the hard control (a config constant)")
    if maxNoGC != 45000:
        pc_fail.append(f"maxNoGC={maxNoGC}")
    print(f"[PC]   ObjFirstGCIndex             = {firstGC:<8} expect ~39295  "
          f"{'ok' if firstGC == 39295 else 'DIFFERS (soft -- pool size can move)'}")
    print(f"[PC]   ObjLastNonGCIndex           = {lastNonGC:<8} expect ~39294  "
          f"{'ok' if lastNonGC == 39294 else 'DIFFERS (soft)'}")
    print(f"[PC]   OpenForDisregardForGC       = {openDis:<8} expect 0")
    print(f"[PC]   ObjObjects.Objects          = 0x{objectsPtr:X}  (FUObjArr+0x10)   "
          f"NumElements = {numEl}  (FUObjArr+0x24)")
    if not lp(objectsPtr):
        pc_fail.append("objects-ptr-not-a-pointer")
    # TWO BANDS, and the split is deliberate.
    #  * IMPOSSIBLE  -> hard FAIL. item_watch.py:213 hard-fails the same way. A NumElements outside
    #    (0, 8_000_000) means the field itself was read from the wrong place, which is precisely the
    #    defect this file shipped once, so the instrument that detects it must not be advisory.
    #  * merely LOW  -> warning. A count below ~10k on a running game is a statement about TIMING
    #    (attached mid-startup), not about process identity; the discriminating controls are
    #    MaxObjectsNotConsideredByGC == 45000 plus a decodable FName pool.
    if not (0 < numEl < 8_000_000):
        pc_fail.append(f"NumElements={numEl} (impossible -- wrong offset or wrong base)")
        print(f"[PC]   !! NumElements={numEl} is IMPOSSIBLE -> FAIL. Expected the field at "
              f"FUObjArr+0x24; a value like a pointer's high dword means the read is misaligned.")
    elif numEl < 10000:
        pc_warn.append(f"NumElements={numEl}")
        print(f"[PC]   !! NumElements={numEl} is far below the ~200k a running game shows "
              f"-- WARNING only (attached mid-startup?), not a FAIL.")

ra = rpm(BASE + RVA_ROOT_ARRAYNUM, 4)
rf = rpm(BASE + RVA_ROOT_FREEIDX, 4)
if ra and rf:
    rootnum = i32(ra, 0) - i32(rf, 0)
    print(f"[PC]   root registry Num (ArrayNum-NumFreeIndices) = {rootnum}   "
          f"(S123 measured 32 at the menu; informational, NOT asserted)")
else:
    pc_warn.append("root-registry-unreadable")


# ==================================================================================================
# 1. ONE SWEEP of GUObjectArray. Collect the pointer set + every *GameMode / *GameState / World.
# ==================================================================================================
objset = set()
gm_cands = []
gs_cands = []
world_cands = []
clscache = {}

if objectsPtr and numEl:
    nch = (numEl + PERCHUNK - 1) // PERCHUNK
    cp = rpm(objectsPtr, nch * 8) or b""
    scanned = 0
    for ci in range(nch):
        if (ci + 1) * 8 > len(cp):
            break
        ch = int.from_bytes(cp[ci * 8:ci * 8 + 8], "little")
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
            objset.add(o)
            scanned += 1
            hdr = rpm(o + OFF_OBJ_CLASS, 12)      # class @+0x18, name index @+0x20
            if not hdr:
                continue
            c = u64(hdr, 0)
            if not lp(c):
                continue
            cn = clscache.get(c)
            if cn is None:
                cn = chain_of(c)
                clscache[c] = cn
            # PERF: the object's own FName is decoded ONLY for a candidate. Decoding it for all
            # ~200k objects costs up to 3 extra RPMs per distinct name and pushed the sweep into
            # minutes -- and this probe's whole instruction is "re-run it IMMEDIATELY BEFORE the
            # call you intend to make", inside an armed window with ~110 s of usable margin.
            hitgm = any("GameMode" in x for x in cn)
            hitgs = any("GameState" in x for x in cn)
            hitw = bool(cn) and cn[0] == "World"
            if not (hitgm or hitgs or hitw):
                continue
            nm = fname(u32(hdr, 8))
            if hitgm:
                gm_cands.append((o, nm, c, cn))
            if hitgs:
                gs_cands.append((o, nm, c, cn))
            if hitw:
                world_cands.append((o, nm, c, cn))
    print(f"\n[SWEEP] {scanned} live objects  |  *GameMode chain: {len(gm_cands)}  "
          f"*GameState chain: {len(gs_cands)}  World: {len(world_cands)}")
    print("\n[PC] POSITIVE CONTROL (part 2 -- needs the sweep):")
    if _nc:
        sample = next((v for v in _nc.values() if v not in ("?", "")), None)
        print(f"[PC]   FName pool decodes (sample: {sample!r})   "
              f"{'PASS' if sample else 'FAIL'}")
        if not sample:
            pc_fail.append("fname-pool-dead")

PC_VERDICT = "PASS" if not pc_fail else "FAIL"
print(f"[PC]   POSITIVE CONTROL VERDICT: {PC_VERDICT}" + (f"  ({', '.join(pc_fail)})" if pc_fail else ""))
if pc_warn:
    print(f"[PC]   warnings (not failures): {', '.join(pc_warn)}")
if pc_fail:
    print("[PC]   >> STOP. Everything below is uninterpretable. Fix the attach first.")


# ==================================================================================================
# 2. ENUMERATE EVERY GameMode CANDIDATE -- never 'take the first match'.
# ==================================================================================================
def show_cands(title, cands, link_off=None):
    print(f"\n=== {title} ({len(cands)}) ===")
    if not cands:
        print("   (none)")
        return
    for o, nm, c, cn in cands:
        tag = "ARCHETYPE" if is_archetype(nm) else "instance "
        extra = ""
        if link_off is not None:
            lv = p(o + link_off)
            extra = f"  [+0x{link_off:X}]=0x{lv:X}"
            if lv:
                extra += (" IN-OBJARRAY" if lv in objset else " not-in-objarray")
        print(f"   0x{o:X}  {tag}  {nm[:52]:52}")
        print(f"        chain: {' <- '.join(cn)}{extra}")


show_cands("GameMode candidates (matched on the CLASS DERIVATION CHAIN, not the leaf name)",
           gm_cands, GM_TO_GS)
show_cands("GameState candidates (independent -- used to cross-check the +0x258 hop)", gs_cands)

# ---- pick one, and SAY WHY -----------------------------------------------------------------------
GM = None
gm_why = ""
# gm_pick is the MACHINE-READABLE form of the selection quality and it goes in the summary line.
# The enumeration above "shows its work" -- but a summary that omits the disqualifier while the
# tool's own instruction is "parse the summary, never count the rows" re-introduces the exact
# class-lookup blind spot at the reporting layer. unique > override > unlinked > AMBIGUOUS/WEAK.
gm_pick = "none"
gm_live = [t for t in gm_cands if not is_archetype(t[1])]
if GM_OVERRIDE is not None:
    GM = GM_OVERRIDE
    gm_why = "--gamemode override (operator-supplied; the auto-selection was NOT used)"
    gm_pick = "override"
else:
    linked = [t for t in gm_live if p(t[0] + GM_TO_GS) in objset and p(t[0] + GM_TO_GS)]
    if len(linked) == 1:
        GM, gm_why = linked[0][0], "the only non-archetype *GameMode whose [+0x258] is a live UObject"
        gm_pick = "unique"
    elif len(linked) > 1:
        GM, gm_why = linked[0][0], (f"FIRST of {len(linked)} equally-qualified candidates "
                                    f"-- !! AMBIGUOUS, re-run with --gamemode on each")
        gm_pick = "AMBIGUOUS"
    elif len(gm_live) == 1:
        GM, gm_why = gm_live[0][0], "the only non-archetype *GameMode (but its [+0x258] did NOT validate)"
        gm_pick = "unlinked"
    elif gm_live:
        GM, gm_why = gm_live[0][0], (f"FIRST of {len(gm_live)} non-archetypes, none with a valid "
                                     f"[+0x258] -- !! WEAK")
        gm_pick = "WEAK"

if GM is None:
    print("\n>> NO LIVE GameMode.")
    print(">> This is a statement about STAGING, not about the phase machine. At the main menu there")
    print(">> is no round GameMode at all. Stage LVL_Tutorial (configs/fk24-stage.ps1) and re-run.")
    print(">> BEFORE believing it: check the [PC] block above passed and that [SWEEP] scanned ~200k")
    print(">> objects. A truncated sweep produces this same message on a perfectly staged world.")
    print(f"summary: status=NO-GAMEMODE pc={PC_VERDICT} pid={PID} base=0x{BASE:X} "
          f"swept={len(objset)} gamemode_cands={len(gm_cands)} gm_pick=none")
    sys.exit(2)

GMCLS = p(GM + OFF_OBJ_CLASS)
print(f"\n>> CHOSEN GameMode = 0x{GM:X}  {oname(GM)}  class={oname(GMCLS)}")
print(f">> selection reason: {gm_why}")


# ==================================================================================================
# 3. DERIVE + VALIDATE the GameState. Five independent checks, all printed.
# ==================================================================================================
print(f"\n=== GameState derivation: [GameMode+0x{GM_TO_GS:X}] -- VALIDATED, not trusted ===")
raw258 = rpm(GM + GM_TO_GS, 8)
GS = u64(raw258, 0) if raw258 else 0
print(f"   raw  = {hexdump(raw258)}   -> 0x{GS:X}")

checks = []
if not GS or not lp(GS):
    checks.append(("(a) pointer sane", False, f"0x{GS:X}"))
    GS = 0
else:
    checks.append(("(a) pointer sane", True, f"0x{GS:X}"))
    checks.append(("(b) present in live GUObjectArray (name-free pointer equality)",
                   GS in objset, "yes" if GS in objset else "NO"))
    vt = p(GS)
    checks.append(("(c) vtable inside the main module", in_module(vt), f"0x{vt:X}"))
    gscls = p(GS + OFF_OBJ_CLASS)
    gschain = chain_of(gscls) if lp(gscls) else []
    okcls = any("GameState" in x for x in gschain)
    checks.append(("(d) class chain reaches a *GameState", okcls,
                   " <- ".join(gschain) if gschain else "unresolved"))

# (e) does the GameMode's OWN reflected `GameState` UPROPERTY declare 0x258?
gmprops = props_of(GMCLS) if lp(GMCLS) else []
gs_prop_offs = [(o, owner, ty) for (nm, ty, o, owner) in gmprops if nm == "GameState"]
if gs_prop_offs:
    hit = any(o == GM_TO_GS for o, _, _ in gs_prop_offs)
    checks.append((f"(e) GameMode's reflected `GameState` UPROPERTY == +0x{GM_TO_GS:X}", hit,
                   ", ".join(f"+0x{o:X} ({ty} on {owner})" for o, owner, ty in gs_prop_offs)))
else:
    checks.append((f"(e) GameMode's reflected `GameState` UPROPERTY == +0x{GM_TO_GS:X}", None,
                   "property not found in the class chain (offset stays [M]-from-disassembly only)"))

# (f) cross-check against every UWorld's own reflected AuthorityGameMode / GameState.
# ⚠ This is the single most informative check available -- docs/fk22:629 prescribes
# `GameMode from World->AuthorityGameMode` as THE derivation -- so its result is APPENDED TO
# `checks`, not merely decorated into a print. An earlier draft printed it as a tag that affected
# nothing, and printed NOTHING AT ALL when world_cands was empty, so an absent World read exactly
# like a World that agreed. A null must never be indistinguishable from a pass.
world_agm_hits = []
world_gs_hits = []
if not world_cands:
    print("   (no UWorld found in the sweep -- the World cross-check could NOT be performed;")
    print("    this is an ABSENT check, not a passing one)")
for wo, wnm, wc, _wcn in world_cands:
    wp = {nm: off for (nm, ty, off, owner) in props_of(wc)}
    agm = p(wo + wp["AuthorityGameMode"]) if "AuthorityGameMode" in wp else None
    wgs = p(wo + wp["GameState"]) if "GameState" in wp else None
    bits = []
    if agm:
        world_agm_hits.append(agm)
        bits.append(f"AuthorityGameMode=0x{agm:X}{' ==CHOSEN' if agm == GM else ''}")
    if wgs:
        world_gs_hits.append(wgs)
        bits.append(f"GameState=0x{wgs:X}{' ==DERIVED' if wgs == GS else ''}")
    print(f"   world 0x{wo:X} {wnm[:30]:30} " + ("  ".join(bits) if bits else "(no reflected links)"))

if world_gs_hits:
    checks.append(("(f) == some UWorld's reflected `GameState` (docs/fk22:629's own derivation)",
                   GS in world_gs_hits,
                   ", ".join(f"0x{x:X}" for x in world_gs_hits)))
else:
    checks.append(("(f) == some UWorld's reflected `GameState` (docs/fk22:629's own derivation)",
                   None, "NO UWorld with a reflected GameState -- check ABSENT, not passed"))

# The GameMode pick gets the same treatment: if a World names an AuthorityGameMode and it is not
# the one we chose, say so loudly. This is what would catch a stale GameMode from a prior world.
if world_agm_hits and GM not in world_agm_hits:
    print(f"   !! WARNING: no UWorld's AuthorityGameMode equals the CHOSEN GameMode 0x{GM:X}.")
    print(f"   !! Worlds name: {', '.join('0x%X' % x for x in world_agm_hits)}")
    print("   !! docs/fk22:629 derives the GameMode from World->AuthorityGameMode. Prefer one of")
    print("   !! those addresses: re-run with --gamemode <that address>.")
    if gm_pick not in ("override",):
        gm_pick = "AMBIGUOUS"

for label, ok, detail in checks:
    mark = "PASS" if ok is True else ("FAIL" if ok is False else "n/a ")
    print(f"   [{mark}] {label:62} {detail}")

# gs_valid is decided by the four CORE checks (a)-(d) only: (e) and (f) are corroboration and are
# legitimately absent on some class layouts, so letting them veto would produce a false UNTRUSTED.
# They are still printed, still in the summary, and (f) disagreeing raises the AMBIGUOUS flag above.
CORE = 4
gs_valid = bool(GS) and all(c[1] is not False for c in checks[:CORE])
if not gs_valid:
    print("   >> GameState link did NOT validate. Treat every GameState read below as UNTRUSTED.")


# ==================================================================================================
# 4. REFLECTION CROSS-CHECK of the three hardcoded GameState offsets.
# ==================================================================================================
print("\n=== reflection cross-check (the hardcoded offsets are [M] from disassembly; this is a"
      " SECOND, independent opinion) ===")
gsprops = props_of(p(GS + OFF_OBJ_CLASS)) if gs_valid else []
for want, hard in (("CurrentPhase", GS_CURRENTPHASE),
                   ("OnRoundPhaseChanged", GS_DELEGATE),
                   ("MatchStartDetails", GS_MATCHSTART)):
    hits = [(o, ty, owner) for (nm, ty, o, owner) in gsprops if nm == want]
    if not hits:
        print(f"   {want:20} hardcoded +0x{hard:03X}  reflection: NOT FOUND "
              f"(not fatal -- the offset is pinned by disassembly)")
        continue
    agree = any(o == hard for o, _, _ in hits)
    print(f"   {want:20} hardcoded +0x{hard:03X}  reflection: "
          + ", ".join(f"+0x{o:X} ({ty} on {owner})" for o, ty, owner in hits)
          + ("   AGREE" if agree else "   !! DISAGREE"))
    if want == "CurrentPhase" and len(hits) > 1:
        print("      !! MORE THAN ONE match -- FK-22 sec.9.1 records TWO FPropertyParams records naming")
        print("        `CurrentPhase` (0xF48 and 0xA44). Reflection ALONE is ambiguous here; the")
        print("        disassembly `movzx eax,[rcx+0xA44]; ret` is what disambiguates. Using 0xA44.")

# reverse lookup for the three GameMode bytes (expected empty -- they are native, not UPROPERTYs)
print("   -- GameMode reverse lookup (a reflected property AT these offsets, if any):")
for off in (GM_790, GM_7B0, GM_7C0):
    hits = [f"{nm} ({ty}, on {owner})" for (nm, ty, o, owner) in gmprops if o == off]
    print(f"      +0x{off:03X}: " + (", ".join(hits) if hits else
                                     "(none -- expected; these are native fields, not UPROPERTYs)"))


# ==================================================================================================
# 5. THE READS
# ==================================================================================================
print("\n" + "=" * 96)
print("READS  (raw hex first, decoded second -- never a decoded value on its own)")
print("=" * 96)

# ---- CurrentPhase --------------------------------------------------------------------------------
phase = None
if gs_valid:
    b = rpm(GS + GS_CURRENTPHASE, 8)
    if b:
        phase = b[0]
        pn = EROUNDPHASE[phase] if phase < len(EROUNDPHASE) else "OUT-OF-RANGE"
        print(f"\nGameState+0x{GS_CURRENTPHASE:X}  CurrentPhase")
        print(f"   raw(8) = {hexdump(b)}")
        print(f"   uint8  = {phase}  =  EGP_{pn}")
    else:
        print(f"\nGameState+0x{GS_CURRENTPHASE:X}  CurrentPhase : UNREADABLE")
else:
    print(f"\nGameState+0x{GS_CURRENTPHASE:X}  CurrentPhase : SKIPPED (GameState invalid)")

# ---- OnRoundPhaseChanged -- BOTH readings, then decide from the bytes -----------------------------
del_num = None
del_verdict = "UNREADABLE"
# del_state is what arm A5 is gated on, and it is deliberately TRI-STATE. "Num>0" alone is NOT
# enough to license the arm: if the invocation list does not walk, the number is an artifact and a
# silent A5 would be UNINTERPRETABLE rather than negative -- which is the exact failure this
# project has recorded 40+ times. Only "validated" licenses A5.
del_state = "unreadable"
print(f"\nGameState+0x{GS_DELEGATE:X}  OnRoundPhaseChanged  <-- THIS NUMBER DECIDES WHETHER ARM A5 RUNS")
draw = rpm(GS + GS_DELEGATE, 16) if gs_valid else None
if not gs_valid:
    # SKIPPED != UNREADABLE. "UNREADABLE" says the address was bad; "SKIPPED" says we never looked.
    # Conflating them sends the operator hunting the delegate offset when the real fault is upstream
    # in the GameState derivation -- root-cause misattribution, which is what this file's own header
    # warns about. The CurrentPhase and MatchStartDetails branches already say SKIPPED; this one did
    # not, and it is the field arm A5 hangs on.
    print("   SKIPPED (GameState invalid -- the read was never ATTEMPTED; this is not a failed read)")
    del_verdict = "SKIPPED (GameState invalid)"
    del_state = "skipped"
elif not draw:
    print("   raw(16) = <UNREADABLE>")
else:
    print(f"   raw(16) = {hexdump(draw)}")
    d_data = u64(draw, 0)
    d_num = i32(draw, 8)
    d_max = i32(draw, 12)
    print(f"   reading A -- DYNAMIC MULTICAST (TArray<FScriptDelegate>, stride 16) [FK-22 sec.10.3, M]:")
    print(f"                Data=0x{d_data:X}   Num={d_num}   Max={d_max}")
    print(f"   reading B -- SINGLE-CAST FDelegateBase {{void* Alloc; int32 DelegateSize; pad}} [FK-15]:")
    print(f"                Alloc=0x{d_data:X}   DelegateSize={d_num}   pad=0x{d_max & 0xFFFFFFFF:08X}")
    print("   WHICH I BELIEVE: reading A (multicast). Reason, from the DISASSEMBLY not the bytes:")
    print("     BP_AuthSetCurrentPhase impl 0x567A160 = `add rcx,0x590; jmp 0x442B4C0`, and 0x1342340")
    print("     reads Num at [rcx+8], `test edi,edi; jle <return>`, then walks [rcx] at STRIDE 16 and")
    print("     issues `call [r9+0x270]` (ProcessEvent) per entry. FK-15's 'entries=3' single-cast")
    print("     trap does NOT apply: that was an ALLOCATION SIZE on a different delegate family.")
    # live corroboration: walk the entries
    if d_num > 0 and lp(d_data) and d_num < 4096:
        good = 0
        WALKCAP = 16
        walked = min(d_num, WALKCAP)
        print(f"   entry walk (live corroboration of reading A) -- walking {walked} of {d_num}:")
        for i in range(walked):
            e = rpm(d_data + i * 16, 16)
            if not e:
                print(f"      [{i}] <UNREADABLE>")
                continue
            obj = u64(e, 0)
            fn = fname(u32(e, 8))
            live = obj in objset
            if live and fn not in ("?", ""):
                good += 1
            print(f"      [{i}] Object=0x{obj:X} {'IN-OBJARRAY' if live else 'NOT-IN-OBJARRAY'} "
                  f"({oname(obj) if live else '-'})  FunctionName={fn!r}")
        del_num = d_num
        if good == walked:
            del_state = "validated"
            # ⚠ Quote the UNIT and the DENOMINATOR. The walk is capped at WALKCAP, so with Num > 16
            # this claims only what it checked. An earlier draft said "every entry validated" while
            # having checked 16 of N -- over-claiming on exactly the number that licenses arm A5.
            if d_num > walked:
                del_verdict = (f"MULTICAST, Num={d_num}; {good} of the first {walked} entries "
                               f"validated (walk capped at {WALKCAP}; the rest were NOT checked)")
            else:
                del_verdict = f"MULTICAST, {d_num} REAL SUBSCRIBER(S) (all {walked} entries validated)"
        elif good:
            del_state = "ambiguous"
            del_verdict = f"AMBIGUOUS -- only {good}/{walked} walked entries validated (Num={d_num})"
        else:
            del_state = "ambiguous"
            del_verdict = "AMBIGUOUS -- Num>0 but NO entry validated; do NOT read this as subscribers"
    elif d_num == 0:
        del_num = 0
        del_state = "empty"
        del_verdict = "EMPTY (Num==0) -- a broadcast here is a HARD NO-OP"
    else:
        del_num = d_num
        del_state = "ambiguous"
        del_verdict = f"AMBIGUOUS -- Num={d_num} with Data=0x{d_data:X} (implausible)"
    print(f"   VERDICT: {del_verdict}")

# ---- MatchStartDetails ---------------------------------------------------------------------------
ms_num = None
print(f"\nGameState+0x{GS_MATCHSTART:X}  MatchStartDetails (FString)")
if gs_valid:
    txt, dptr, n, mx, rawfs = fstring(GS + GS_MATCHSTART)
    print(f"   raw(16) = {hexdump(rawfs)}")
    if rawfs is None:
        print("   <UNREADABLE>")
    else:
        ms_num = n
        print(f"   Data=0x{dptr:X}  Num={n}  Max={mx}")
        print(f"   string  = {txt!r}" if n and n > 0 else "   string  = <empty>")
        print("   NOTE: the 1->2 gate is `cmp dword [rax+8],1; jle bail`, i.e. it needs Num > 1.")
        print("         FString Num COUNTS THE NUL, so Num>1 <=> at least one real character.")
    tn = rpm(GS + GS_MATCHSTART + 0x10, 16)
    if tn:
        print(f"   (+0x748 companion TArray: Data=0x{u64(tn,0):X} Num={i32(tn,8)} Max={i32(tn,12)}"
              f" -- the same writer copies into it; informational)")
else:
    print("   SKIPPED (GameState invalid)")

# ---- the three GameMode fields --------------------------------------------------------------------
print(f"\nGameMode+0x{GM_790:X} / +0x{GM_7B0:X} / +0x{GM_7C0:X}")
b790 = rpm(GM + GM_790, 8)
v790 = u64(b790, 0) if b790 else None
print(f"   +0x790 raw(8) = {hexdump(b790)}   qword = "
      + (f"0x{v790:X}" if v790 is not None else "UNREADABLE")
      + "   (1->2 gate: `cmp qword [rbx+0x790],0; jne bail` -> must be 0)")
b7b0 = rpm(GM + GM_7B0, 8)
v7b0 = b7b0[0] if b7b0 else None
print(f"   +0x7B0 raw(8) = {hexdump(b7b0)}   uint8 = {v7b0}"
      + "   (the 1->2 gate WRITES 1 here; a 1 means that gate already fired)")
b7c0 = rpm(GM + GM_7C0, 8)
v7c0 = b7c0[0] if b7c0 else None
sname = INITIALIZER_STAGE[v7c0] if (v7c0 is not None and v7c0 < len(INITIALIZER_STAGE)) else "?"
print(f"   +0x7C0 raw(8) = {hexdump(b7c0)}   uint8 = {v7c0}  ~ {sname} [I: names from log ORDER only]"
      + "   (3->4 gate needs == 4)")

if DUMP:
    for lbl, a, n in (("GameMode+0x780", GM + 0x780, 0x60), ("GameState+0x580", GS + 0x580, 0x40),
                      ("GameState+0x730", GS + 0x730, 0x40), ("GameState+0xA40", GS + 0xA40, 0x20)):
        blk = rpm(a, n)
        print(f"\n   [dump] {lbl}:")
        for i in range(0, n, 16):
            print(f"      +{i:03X}  {hexdump(blk[i:i+16]) if blk else '<UNREADABLE>'}")


# ==================================================================================================
# 6. GATE VERDICT -- the operator must not have to do arithmetic.
# ==================================================================================================
def cond(label, ok):
    return f"      [{'MET      ' if ok is True else ('UNMET    ' if ok is False else 'UNREADABLE')}] {label}"


print("\n" + "=" * 96)
print("GATE VERDICT")
print("=" * 96)

g12 = []
g12.append(("MatchStartDetails.Num > 1  (non-empty)",
            None if ms_num is None else ms_num > 1, f"Num={ms_num}"))
g12.append(("CurrentPhase == 1 (EGP_BeginInit)",
            None if phase is None else phase == 1, f"phase={phase}"))
g12.append(("qword[GameMode+0x790] == 0",
            None if v790 is None else v790 == 0, f"0x{v790:X}" if v790 is not None else "-"))
print("\n  GATE 1->2   fn 0x560AF10  (runs on the phase-change path; calls GoToPhase(2))")
for lbl, ok, det in g12:
    print(cond(f"{lbl:44} {det}", ok))
v12 = ("OPEN" if all(c[1] is True for c in g12)
       else ("UNREADABLE" if any(c[1] is None for c in g12) else "BLOCKED"))
print(f"      => GATE 1->2 : {v12}")

g34 = []
g34.append(("byte[GameMode+0x7C0] == 4 (initializer Finished)",
            None if v7c0 is None else v7c0 == 4, f"={v7c0}"))
g34.append(("CurrentPhase == 3 (EGP_FinishInit)",
            None if phase is None else phase == 3, f"phase={phase}"))
print("\n  GATE 3->4   Tick 0x5613200  (RUNS EVERY FRAME; calls GoToPhase(4))")
for lbl, ok, det in g34:
    print(cond(f"{lbl:44} {det}", ok))
v34 = ("OPEN" if all(c[1] is True for c in g34)
       else ("UNREADABLE" if any(c[1] is None for c in g34) else "BLOCKED"))
print(f"      => GATE 3->4 : {v34}")
if v34 == "BLOCKED" and v7c0 == 4 and phase is not None and phase != 3:
    print("      >> The initializer half is ALREADY SATISFIED. The ONLY unmet term is the phase byte.")
    print("      >> That is exactly the FK-22 sec.11 prediction: poking GameState+0xA44 = 3 should make")
    print("      >> this already-running Tick fire GoToPhase(4) BY ITSELF (arm A4).")

if del_state == "validated" and del_num:
    a5 = "YES"
elif del_state == "empty":
    a5 = "NO"
else:
    a5 = "AMBIGUOUS"
print(f"\n  ARM A5 (BP_AuthSetCurrentPhase) RUNNABLE: {a5}   [delegate: {del_verdict}]")
if a5 != "YES":
    print("      >> DO NOT RUN A5. A broadcast into an empty -- or merely UNVALIDATED -- invocation")
    print("      >> list is a hard no-op, so silence would be UNINTERPRETABLE, not a negative result.")
    print("      >> AMBIGUOUS is not a weak NO: it means this probe could not read the list, so fix")
    print("      >> the read (or re-run once the world has settled) before spending the arm.")


# ==================================================================================================
# 7. BLIND SPOTS + parse-friendly summary
# ==================================================================================================
print("\n" + "-" * 96)
print("WARNINGS -- this probe's own blind spots")
print("-" * 96)
print(" * SNAPSHOT ONLY. delegate Num==0 now does not mean nothing ever subscribes -- the tutorial")
print("   mode binds OnRoundPhaseChanged inside ReceiveBeginPlay behind ULokiBlueprintLibrary::")
print("   ServerOnly. Re-run this IMMEDIATELY BEFORE the call you intend to make, not once at staging.")
print(" * 'NO GAMEMODE' is a statement about STAGING, never about the phase machine.")
print(" * The gate terms are transcribed from offline disassembly of a 54.95 %-decrypted image. This")
print("   probe can show a term is UNMET; it cannot show the term list is COMPLETE.")
print(" * CurrentPhase is a REPLICATED property. A value can in principle be written by the net")
print("   serializer via computed-offset memcpy, which no literal-displacement scan can see.")
print(" * The +0x7C0 stage NAMES are [I] from log order; only the NUMBER (4) is load-bearing.")
print(" * Parse the `summary:` line below. NEVER count the rows above.")
print(" * `status=OK` means the probe RAN, not that the reading is good. The disqualifiers are")
print("   `pc=` (FAIL => everything is uninterpretable) and `gm_pick=` (AMBIGUOUS/WEAK => the")
print("   GameMode was a first-of-several guess). Gate on all three, never on status alone.")

# STATUS CARRIES THE DISQUALIFIERS. `status=OK pc=FAIL` was previously printable, and the file's own
# instruction is "parse the summary, never count the rows" -- so a summary that omits a stated STOP
# condition is the instrument carrying the defect it exists to detect.
STATUS = "OK"
if pc_fail:
    STATUS = "PC-FAIL"
elif gm_pick in ("AMBIGUOUS", "WEAK"):
    STATUS = "AMBIGUOUS-GAMEMODE"
elif not gs_valid:
    STATUS = "GAMESTATE-UNTRUSTED"

print(f"\nsummary: status={STATUS} pc={PC_VERDICT} pid={PID} base=0x{BASE:X} swept={len(objset)} "
      f"gamemode=0x{GM:X} gm_pick={gm_pick} gamemode_cands={len(gm_cands)} "
      f"gamemode_live_cands={len(gm_live)} gamestate=0x{GS:X} "
      f"gs_valid={'yes' if gs_valid else 'no'} "
      f"phase={phase}({EROUNDPHASE[phase] if phase is not None and phase < len(EROUNDPHASE) else '?'}) "
      f"delegate_num={del_num} delegate_verdict=\"{del_verdict}\" "
      f"matchstart_num={ms_num} gm790={('0x%X' % v790) if v790 is not None else None} "
      f"gm7B0={v7b0} gm7C0={v7c0} gate12={v12} gate34={v34} a5_runnable={a5}")
