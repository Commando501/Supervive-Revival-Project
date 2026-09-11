#!/usr/bin/env python
# =============================================================================
# cheat_reach_probe.py -- FK-13 lane 4: if a CONSOLE STRING cannot reach the
#                         cheat verbs, WHAT CAN?  Answer the runtime half.
#
# PURE RPM. Read-only. No injection, no .text write, no thread suspend, no
# WriteProcessMemory anywhere in this file. It imports its reader / GUObjectArray
# walker / reflection walker from console_probe.py (same directory) so there is
# exactly ONE copy of that code and one place for its offsets to be wrong.
#
# -----------------------------------------------------------------------------
# WHY THIS EXISTS
#
# `UPlayer::Exec` (UE 5.4 Player.cpp:95-155, read from the local engine tree)
# offers a fixed dispatch chain, and every branch is a POINTER that is either
# populated at runtime or is not:
#
#     PlayerController->PlayerInput ->ProcessConsoleExec
#     ExecActor (== the PlayerController itself)
#     PCPawn (== PlayerController->GetPawnOrSpectator())
#     PlayerController->MyHUD
#     World->GetAuthGameMode()
#     PlayerController->CheatManager          <-- 48 exec verbs hang off this
#     World->GetGameState()
#     PlayerController->PlayerCameraManager
#
# `ALokiPlayerCheats` is an ACTOR and is on NONE of those branches, so its 25
# exec verbs are unreachable by string unless ALokiPlayerController overrides
# ProcessConsoleExec (lane 1) or it is registered as a CheatManagerExtension.
#
# BUT the project's S55 native-call primitive calls a UFunction's `Func` thunk
# (+0xE0) DIRECTLY and does not care about the router at all.  For that route the
# only question is: DOES AN INSTANCE EXIST TO CALL IT ON?  That is what this
# probe measures, plus every chain pointer above, in one pass.
#
# -----------------------------------------------------------------------------
# WHAT IT ANSWERS (each section independent; one failing does not void the rest)
#
#   [1] INSTANCE CENSUS.  Does any ALokiPlayerCheats / ALokiPlayerCheats_AS /
#       ULokiClientPlayerCheats / UCheatManager / UCheatManagerExtension object
#       exist in GUObjectArray, and is it a CDO or a live instance?
#       -> decides Route A ("call the thunk directly") and Route B ("manufacture
#          a UCheatManager") without any writes.
#
#   [2] THE UPlayer::Exec CHAIN, POINTER BY POINTER, on the live PlayerController:
#       CheatManager(+0x520) CheatClass(+0x528) PlayerInput MyHUD Pawn
#       AcknowledgedPawn SpectatorPawn PlayerCameraManager Player,
#       plus Loki's own `LokiPlayerController.LokiPlayerCheats` ObjectProperty.
#       Offsets are resolved BY NAME from live reflection; the two literal
#       offsets measured in S114 (+0x520/+0x528) are printed beside the
#       by-name result as a cross-check, never instead of it.
#
#   [3] WORLD BRANCHES: AuthorityGameMode / GameState instances.
#
#   [4] ULokiGlobals -> DebugGlobals(UClass) -> its CDO -> `LokiPlayerCheats`
#       SoftClassProperty: WHICH class the game itself would have spawned.
#       If that soft path is empty, nothing was ever going to spawn one.
#
#   [5] ROUTE-A / ROUTE-C TARGET UFUNCTIONS: locate each UFunction object, print
#       `UFunction.Func` (+0xE0) and check it against the RVA measured OFFLINE
#       this session.  A match re-validates the whole offline table for THIS
#       launch; a mismatch means the offline table is stale and Route C's swap
#       would target the wrong thing.
#
# -----------------------------------------------------------------------------
# OFFLINE MEASUREMENTS THIS PROBE IS DESIGNED TO CONFIRM OR REFUTE (S114 lane 4,
# dumps/tutorial-hero, base 0x7FF6505C0000, .text union across all dumps):
#
#   ALokiPlayerController::AddLokiPlayerCheats  exec thunk 0x05254180
#   ALokiPlayerController::FinishAddLokiPlayerCheats  exec thunk 0x05254180
#       both = `P_FINISH; jmp 0x00F7EC20` where 0x00F7EC20 is `ret 0`
#       => the game's own path for creating the cheat actor IS AN EMPTY BODY.
#       CORROBORATED LIVE, 20+ tutorial runs: `[CHEAT] localCheatObj=0x0(-)`
#       (GetLocalLokiPlayerCheatsBP returned NULL every time).
#   ULokiBlueprintLibrary::CheatsEnabled       thunk 0x051629C0 -> call 0x00F7EB60
#   ALokiPlayerCheats::AreHotkeyCheatsEnabled  thunk 0x052FD980 -> call 0x00F7EB60
#       0x00F7EB60 = `xor al,al; ret`  => BOTH gates are hard-wired false.
#   UCheatManager: 50/50 FUNC_Exec thunks are REAL bodies (none folded).
#   ALokiCharacter: 8 of its 10 FUNC_Exec thunks fold to `ret 0` (all 0 params).
#
# -----------------------------------------------------------------------------
# !!! UNTESTED AGAINST A LIVE PROCESS !!!
# Written offline in a session forbidden to launch the game. `--self-test` is
# the only part that has ever executed. Most likely first failure modes, IN ORDER:
#   1. NOT ELEVATED -> OpenProcess returns 0. Exits 2 and says so. The game is
#      launched elevated by launch-redirect.ps1, so the probe must be too.
#   2. RVA_NAMEPOOL / RVA_OBJOBJECTS stale after a game update -> the header
#      sanity gate trips and the probe exits 3 rather than printing junk.
#   3. Run AT THE MENU rather than in a world -> section [2] finds no
#      PlayerController and reports VOID. That is not a negative result about
#      the chain; it means the wrong game state was sampled. Sections [1] and
#      [4] still work at the menu and [1] at the menu is the CHEAPEST test of
#      whether ULokiClientPlayerCheats is instantiated by the GameInstance.
#   4. A property this build renamed -> that ONE lookup says NOT FOUND and its
#      row degrades; every other row still prints.
#   5. `--check-thunks` needs --base to be the REAL module base; if a caller
#      passes a stale --base the Func comparison will mismatch for EVERY target,
#      which is reported as "base is probably wrong", not as a finding.
#
# usage:
#   python tools/re/cheat_reach_probe.py                  # auto-detect PID+base
#   python tools/re/cheat_reach_probe.py --pid 1234 --base 0x7FF6505C0000
#   python tools/re/cheat_reach_probe.py --self-test      # offline, no process
#   python tools/re/cheat_reach_probe.py --dry-run        # parse/import check
# =============================================================================
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_probe import (            # noqa: E402  (path juggling above)
    UE, ProcReader, BufReader, looks_ptr, find_pid, find_module_base, PROC_NAME,
    O_OBJ_CLASS, O_OBJ_NAME, O_STRUCT_SUPER,
)

# UFunction.Func -- the S55 native-call primitive's whole basis (CLAUDE.md).
O_UFUNC_FUNC = 0xE0
# S114 lane 4, measured on this build's PlayerController (task brief).
LIT_CHEATMANAGER = 0x520
LIT_CHEATCLASS = 0x528

# ---------------------------------------------------------------------------
# The offline table. Each row: (class, function, expected .text RVA of Func,
# what it was measured to BE).  `Func` for a NATIVE UFunction is the exec thunk.
# Everything here was read out of dumps/tutorial-hero + the cross-dump .text
# union this session; the probe's job is to confirm it survives a real launch.
# ---------------------------------------------------------------------------
THUNKS = [
    ("LokiBlueprintLibrary", "CheatsEnabled",            0x051629C0,
     "-> call 0x00F7EB60 (xor al,al; ret) = ALWAYS FALSE. Route C target."),
    ("LokiPlayerCheats",     "AreHotkeyCheatsEnabled",   0x052FD980,
     "-> call 0x00F7EB60 = ALWAYS FALSE (same fold; NOT previously recorded)."),
    ("LokiPlayerCheats",     "EnableHotkeyCheats",       0x05424670,
     "REAL body, 128 B. 1 param (double Enabled)."),
    ("LokiPlayerCheats",     "GetLocalLokiPlayerCheatsBP", 0x05424F70,
     "REAL body, 133 B. Static, 2 props (WorldContext + return)."),
    ("LokiPlayerController", "AddLokiPlayerCheats",      0x05254180,
     "P_FINISH; jmp 0x00F7EC20 (ret 0) = EMPTY. The creation path is stripped."),
    ("LokiPlayerController", "FinishAddLokiPlayerCheats", 0x05254180,
     "same folded thunk as AddLokiPlayerCheats = EMPTY."),
    ("KismetSystemLibrary",  "ExecuteConsoleCommand",    0x0395D790,
     "REAL body, 469 B. The BlueprintCallable string entry point."),
    ("PlayerController",     "LocalTravel",              0x03C64600,
     "REAL body, 157 B."),
    ("CheatManager",         "God",                      0x035C7FD0,
     "REAL. Positive control: UCheatManager's 50/50 exec thunks are real."),
    ("CheatManager",         "Summon",                   0x035CA510,
     "REAL, 157 B, 1 param. Positive control."),
    ("LokiCharacter",        "InfiniteHealth",           0x05254180,
     "folded to ret 0 = EMPTY (8 of ALokiCharacter's 10 exec fns are)."),
]

# Classes whose instance count decides Routes A and B.
CENSUS = [
    ("LokiPlayerCheats",       "Route A target: 25 exec verbs, ACTOR, not on the exec chain"),
    ("LokiPlayerCheats_AS",    "the Angelscript-generated sibling UClass (FK-1)"),
    ("LokiClientPlayerCheats", "5 exec verbs, UObject, held by LokiGameInstance -> may exist AT THE MENU"),
    ("CheatManager",           "Route B: 48 exec verbs + the CheatManagerExtensions chain"),
    ("CheatManagerExtension",  "what a CheatManagerExtensions entry would be"),
]
# Classes that MUST have live instances if the census instrument works at all.
# These are the census's positive control -- without them a zero above is void.
CENSUS_CONTROL = ["LokiGameInstance", "PlayerController", "GameViewportClient"]

# The UPlayer::Exec chain, as named UPROPERTYs on the PlayerController.
CHAIN_PROPS = [
    ("PlayerInput",         "UPlayer::Exec branch 2 -- PlayerInput->ProcessConsoleExec (5 exec fns)"),
    ("MyHUD",               "UPlayer::Exec branch 5 -- AHUD has 6 exec fns"),
    ("Pawn",                "GetPawnOrSpectator() primary -- ALokiCharacter has 10 exec fns (8 EMPTY)"),
    ("AcknowledgedPawn",    "cross-check on Pawn"),
    ("SpectatorPawn",       "GetPawnOrSpectator() fallback when Pawn is null"),
    ("CheatManager",        "UPlayer::Exec branch 7 -- THE Route B slot (literal +0x520)"),
    ("CheatClass",          "AddCheats() needs this non-null; literal +0x528"),
    ("PlayerCameraManager", "UPlayer::Exec branch 9"),
    ("Player",              "the ULocalPlayer whose ::Exec IS the chain"),
    ("LokiPlayerCheats",    "Loki's OWN slot for the cheat actor -- set by AddLokiPlayerCheats, which is EMPTY"),
]


# =============================================================================
# helpers layered on console_probe's UE
# =============================================================================
def class_of_name(ue, obj):
    return ue.clsname_of(ue.r.u64(obj + O_OBJ_CLASS)) if looks_ptr(obj) else "-"


_DERIVES = {}     # (classPtr, base_name) -> bool, computed once per distinct class


def derives_from(ue, cls, base_name):
    """True if UClass `cls` is, or descends from, the class named `base_name`.
    Memoised per (class, base) so a full-index sweep costs one super-chain walk
    per DISTINCT class, not per object."""
    key = (cls, base_name)
    hit = _DERIVES.get(key)
    if hit is None:
        hit = any(ue.oname(c) == base_name for c in ue.super_chain(cls))
        _DERIVES[key] = hit
    return hit


def census(ue, class_name, exact=False):
    """Return (cdos, live) lists of (addr, objname, clsname) for objects whose
    class DERIVES from `class_name` -- or is EXACTLY it when exact=True.
    Uses the one-pass index, so this is free.

    ---------------------------------------------------------------------------
    S114 BUGFIX (live run 2026-08-12, docs/fk13-live-run-2026-08-12.md).
    This used to match the class name EXACTLY. That made it structurally blind
    to every Blueprint subclass, and it reported

        live instances of LokiGameInstance : 0

    against a RUNNING GAME whose one live GameInstance is `BP_LokiGameInstance_C`
    (found at 0x26C4ED1B040 by tools/re/obj_by_class.py, which matches on a class
    -name SUBSTRING and so was never fooled). A UE process cannot run without a
    GameInstance, so that zero was self-evidently an instrument artifact rather
    than a fact about the game -- the project's #1 recorded failure mode.

    The [CTRL] gate did its job: it saw every control read zero and declared the
    run VOID instead of letting section [1]'s zeros be written up as "no cheat
    objects exist". Keep that gate. The `--subclasses` flag did NOT fix this;
    it only added a separate sweep for three cheat classes and left the gate
    broken. Derivation is now the DEFAULT for every census.
    ---------------------------------------------------------------------------
    """
    cdos, live = [], []
    for o, cls, nidx in ue.build_index():
        if exact:
            if ue.clsname_of(cls) != class_name:
                continue
        elif not derives_from(ue, cls, class_name):
            continue
        nm = ue.fname(nidx)
        (cdos if nm.startswith("Default__") else live).append(
            (o, nm, ue.clsname_of(cls)))
    return cdos, live


def subclass_census(ue, base_name):
    """Objects whose class DERIVES from `base_name` (BP subclasses count).
    Walks the super chain of each distinct class exactly once."""
    derives = {}          # class ptr -> bool, computed once per distinct class
    out = []
    for o, cls, nidx in ue.build_index():
        hit = derives.get(cls)
        if hit is None:
            hit = any(ue.oname(c) == base_name for c in ue.super_chain(cls))
            derives[cls] = hit
        if hit:
            out.append((o, ue.clsname_of(cls), ue.fname(nidx)))
    return out


def find_function(ue, class_name, func_name):
    """The UFunction object `func_name` declared on class `class_name` (walking
    the super chain), returned as (addr, declaringClassName) or (0, '')."""
    cls = ue.find_uclass(class_name)
    if not cls:
        return 0, ""
    for c in ue.super_chain(cls):
        f = ue.r.u64(c + 0x50)            # UStruct::Children (UField*), CLAUDE.md
        i = 0
        while looks_ptr(f) and i < 4096:
            if ue.fname(ue.r.u32(f + O_OBJ_NAME)) == func_name:
                return f, ue.oname(c)
            f = ue.r.u64(f + 0x30)        # UField::Next, s55
            i += 1
    return 0, ""


def soft_path(ue, addr):
    """FSoftObjectPath = FTopLevelAssetPath{FName PackageName; FName AssetName}
    then FString SubPathString.  Returns a printable string."""
    pkg, pi, _ = ue.fname_at(addr)
    asset, ai, _ = ue.fname_at(addr + 8)
    sub, _p, _n, _m = ue.fstring(addr + 16)
    if pi == 0 and ai == 0:
        return "<EMPTY>"
    return "%s.%s%s" % (pkg, asset, ("::" + sub) if sub else "")


# =============================================================================
# --self-test : drive the NEW decoders against a synthetic address space
# =============================================================================
def build_synthetic():
    base = 0x140000000
    blocks = {}

    # ---- name pool -------------------------------------------------------
    poolblk = 0x50000000
    pool = bytearray(0x1000)
    names = {}

    def add_name(off, s):
        pool[off:off + 2] = ((len(s) << 6) | 0).to_bytes(2, "little")
        pool[off + 2:off + 2 + len(s)] = s.encode("latin1")
        names[s] = off >> 1

    add_name(0x10, "LokiPlayerCheats")
    add_name(0x40, "Default__LokiPlayerCheats")
    add_name(0x80, "BP_LokiPlayerCheats_C")
    add_name(0xC0, "CheatsEnabled")
    add_name(0x100, "Game")
    add_name(0x130, "DA_Cheats")
    blocks[poolblk] = bytes(pool)
    from console_probe import RVA_NAMEPOOL
    blocks[base + RVA_NAMEPOOL] = poolblk.to_bytes(8, "little")

    # ---- a UFunction at 0x70000000 with Func @+0xE0 ----------------------
    fn = 0x70000000
    blob = bytearray(0x100)
    blob[O_OBJ_NAME:O_OBJ_NAME + 4] = names["CheatsEnabled"].to_bytes(4, "little")
    blob[O_UFUNC_FUNC:O_UFUNC_FUNC + 8] = (base + 0x051629C0).to_bytes(8, "little")
    blocks[fn] = bytes(blob)

    # ---- an FSoftObjectPath at 0x71000000 --------------------------------
    sp = 0x71000000
    s = "Blueprints"
    strp = 0x71001000
    blocks[strp] = s.encode("utf-16-le")
    b = bytearray(0x20)
    b[0:4] = names["Game"].to_bytes(4, "little")
    b[8:12] = names["BP_LokiPlayerCheats_C"].to_bytes(4, "little")
    b[16:24] = strp.to_bytes(8, "little")
    b[24:28] = len(s).to_bytes(4, "little")
    b[28:32] = len(s).to_bytes(4, "little")
    blocks[sp] = bytes(b)

    # ---- an EMPTY FSoftObjectPath at 0x72000000 --------------------------
    blocks[0x72000000] = bytes(0x20)

    return BufReader(blocks), base, fn, sp


def self_test():
    print("=== cheat_reach_probe.py --self-test  (offline; no process touched) ===")
    rdr, base, fn, sp = build_synthetic()
    ue = UE(rdr, base)
    fails = 0

    v = ue.fname(ue.r.u32(fn + O_OBJ_NAME))
    ok = (v == "CheatsEnabled")
    print("  [%s] UFunction name        -> %r" % ("ok " if ok else "FAIL", v))
    fails += 0 if ok else 1

    f = ue.r.u64(fn + O_UFUNC_FUNC)
    ok = (f - base == 0x051629C0)
    print("  [%s] UFunction.Func@+0xE0  -> 0x%X  (rva 0x%08X, expect 0x051629C0)"
          % ("ok " if ok else "FAIL", f, f - base))
    fails += 0 if ok else 1

    v = soft_path(ue, sp)
    ok = (v == "Game.BP_LokiPlayerCheats_C::Blueprints")
    print("  [%s] soft_path populated   -> %r" % ("ok " if ok else "FAIL", v))
    fails += 0 if ok else 1

    v = soft_path(ue, 0x72000000)
    ok = (v == "<EMPTY>")
    print("  [%s] soft_path empty       -> %r   <-- NEGATIVE control: an all-zero"
          % ("ok " if ok else "FAIL", v))
    print("        path must read as <EMPTY>, never as a plausible asset name.")
    fails += 0 if ok else 1

    ok = looks_ptr(0x7FF6505C0000) and not looks_ptr(0) and not looks_ptr(0x7FF6505C0001)
    print("  [%s] looks_ptr sanity" % ("ok " if ok else "FAIL"))
    fails += 0 if ok else 1

    print("")
    print("  %d/5 decoder checks passed." % (5 - fails))
    print("  NOTE: this validates the NEW decoders ONLY. The GUObjectArray walk, the")
    print("  reflection walk, the UField::Next chain and every RVA are UNTESTED --")
    print("  they have never been run against the game. Run console_probe.py")
    print("  --self-test too; it covers the shared decoders.")
    return 0 if fails == 0 else 1


# =============================================================================
def main():
    ap = argparse.ArgumentParser(
        description="FK-13 lane 4: cheat-surface REACHABILITY probe (pure RPM, read-only).")
    ap.add_argument("--pid", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--subclasses", action="store_true",
                    help="also census BP SUBCLASSES of the cheat classes (slower)")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.dry_run:
        print("=== cheat_reach_probe.py --dry-run ===")
        print("  python            : %s" % sys.version.split()[0])
        print("  console_probe     : imported ok (UE, ProcReader, BufReader)")
        print("  UFunction.Func    : +0x%02X" % O_UFUNC_FUNC)
        print("  literal offsets   : CheatManager +0x%X  CheatClass +0x%X"
              % (LIT_CHEATMANAGER, LIT_CHEATCLASS))
        print("  census classes    : %s" % ", ".join(c for c, _ in CENSUS))
        print("  census control    : %s" % ", ".join(CENSUS_CONTROL))
        print("  thunk table rows  : %d" % len(THUNKS))
        print("  parse OK. Nothing was read from any process.")
        return 0

    pid = args.pid
    if not pid:
        hits = find_pid()
        if not hits:
            print("FAIL: no process named %s. Is the game running?" % PROC_NAME)
            return 2
        pid = hits[0]
        if len(hits) > 1:
            print("WARN: %d instances; using %d. Pass --pid to choose." % (len(hits), pid))
    base = args.base or find_module_base(pid)
    if not base:
        print("FAIL: could not resolve the module base for PID %d. Pass --base." % pid)
        return 2
    rdr = ProcReader(pid)
    if not rdr.h:
        print("FAIL: OpenProcess(%d) failed, GetLastError=%d." % (pid, rdr.err))
        print("      The game runs ELEVATED. Run this probe from an ELEVATED shell.")
        return 2
    ue = UE(rdr, base)

    print("=" * 78)
    print("FK-13 lane 4 -- CHEAT-SURFACE REACHABILITY  (pure RPM, read-only)")
    print("=" * 78)
    print("  PID / base       : %d / 0x%X" % (pid, base))
    objects, num = ue.obj_array_header()
    print("  ObjObjects       : 0x%X  NumElements=%d" % (objects, num))
    if not looks_ptr(objects) or not (0 < num < 8000000):
        print("")
        print("  >>> GUObjectArray header implausible -> RVAs stale or --base wrong.")
        print("      EVERYTHING BELOW WOULD BE GARBAGE. This is a VOID run, not a")
        print("      negative result.")
        return 3
    print("")
    print("  building the object index (ONE pass) ...")
    ue.build_index(progress=print)

    # ------------------------------------------------------------ controls
    print("")
    print("-" * 78)
    print("[CTRL] instrument positive controls -- if these fail the run is VOID")
    print("-" * 78)
    ctrl_ok = True
    for cn in ("PlayerController", "PlayerInput", "CheatManager", "LokiPlayerCheats",
               "LokiClientPlayerCheats", "Function"):
        c = ue.find_uclass(cn)
        print("  UClass %-24s : %s" % (cn, ("0x%X" % c) if c else "NOT FOUND  <== broken"))
        # schema.txt proves all six are compiled in and reflected, so NOT FOUND
        # here can only be a scan failure.
        if not c:
            ctrl_ok = False
    live_ctrl = 0
    for cn in CENSUS_CONTROL:
        _cdo, live = census(ue, cn)
        print("  live instances of %-22s: %d" % (cn, len(live)))
        live_ctrl += len(live)
    if live_ctrl == 0:
        ctrl_ok = False
        print("  >>> the census found ZERO live instances of ANY control class.")
        print("      Section [1]'s zeros below are COVERAGE-BLOCKED, not ABSENT.")
    if not ctrl_ok:
        print("")
        print("  *** A CONTROL FAILED. Record this run as VOID. ***")

    # ------------------------------------------------------------------ [1]
    print("")
    print("-" * 78)
    print("[1] INSTANCE CENSUS -- does anything exist to call a thunk ON?")
    print("-" * 78)
    for cn, why in CENSUS:
        cdos, live = census(ue, cn)
        print("  %-24s CDO=%d  LIVE=%d      (%s)" % (cn, len(cdos), len(live), why))
        for o, nm, cls in (cdos + live)[:8]:
            print("        0x%X  class=%s  %s%s"
                  % (o, cls, nm, "   <== LIVE" if not nm.startswith("Default__") else ""))
    if args.subclasses:
        print("")
        print("  BP SUBCLASS sweep (an instance of BP_LokiPlayerCheats_C would not")
        print("  show above, because its CLASS name is not 'LokiPlayerCheats'):")
        for base_cn in ("LokiPlayerCheats", "CheatManager", "CheatManagerExtension"):
            hits = subclass_census(ue, base_cn)
            print("    derived from %-22s: %d objects" % (base_cn, len(hits)))
            for o, cn, nm in hits[:8]:
                print("        0x%X  class=%s  name=%s" % (o, cn, nm))
    print("")
    print("  INTERPRETATION (offline evidence, S114 lane 4):")
    print("    ALokiPlayerController::AddLokiPlayerCheats's exec thunk 0x05254180 is")
    print("    `P_FINISH; jmp 0x00F7EC20` and 0x00F7EC20 is `ret 0` -- the game's own")
    print("    creation path is an EMPTY BODY -- and 20+ live tutorial runs recorded")
    print("    `[CHEAT] localCheatObj=0x0(-)`. So LIVE=0 for LokiPlayerCheats is the")
    print("    EXPECTED result and confirms it. LIVE>0 would REFUTE the offline read")
    print("    and is the more interesting outcome -- report it loudly.")

    # ------------------------------------------------------------------ [2]
    print("")
    print("-" * 78)
    print("[2] THE UPlayer::Exec CHAIN on the live PlayerController")
    print("-" * 78)
    # S114 FIX: was `cn.endswith("PlayerController")`, which cannot match
    # `BP_LokiPlayerController_C` -- precisely the class the tutorial world
    # spawns. Derivation-based now, so any subclass counts. Components such as
    # Comp_PlayerController_Cheats_C do NOT derive from APlayerController and
    # are correctly excluded (at the menu, all 69 "PlayerController"-named live
    # objects were components; see docs/fk13-live-run-2026-08-12.md).
    pcs = [(o, cls, nm) for (o, nm, cls) in census(ue, "PlayerController")[1]][:4]
    if not pcs:
        print("  >>> no live PlayerController. Section [2] is VOID.")
        print("      At the MENU this is EXPECTED -- re-run inside the tutorial world.")
    for pc, cn, nm in pcs:
        print("")
        print("  --- PlayerController 0x%X  class=%s  name=%s ---" % (pc, cn, nm))
        for pname, why in CHAIN_PROPS:
            r = ue.prop_on_obj(pc, pname)
            if not r:
                print("    %-20s : PROPERTY NOT FOUND (walk failure or renamed -> VOID row)"
                      % pname)
                continue
            off, ty, esz, decl, _pa = r
            v = ue.r.u64(pc + off)
            tail = ""
            if pname == "CheatManager" and off != LIT_CHEATMANAGER:
                tail = "  !! by-name +0x%X != S114 literal +0x%X" % (off, LIT_CHEATMANAGER)
            if pname == "CheatClass" and off != LIT_CHEATCLASS:
                tail = "  !! by-name +0x%X != S114 literal +0x%X" % (off, LIT_CHEATCLASS)
            print("    %-20s +0x%-4X [%-16s on %-22s] -> 0x%-14X %s%s"
                  % (pname, off, ty, decl, v,
                     ("class=" + class_of_name(ue, v)) if looks_ptr(v) else "(NULL)", tail))
            print("        %s" % why)
        # the two literal offsets, read RAW, as an independent cross-check
        print("    RAW +0x%X (CheatManager literal) = 0x%X" % (LIT_CHEATMANAGER, ue.r.u64(pc + LIT_CHEATMANAGER)))
        print("    RAW +0x%X (CheatClass   literal) = 0x%X" % (LIT_CHEATCLASS, ue.r.u64(pc + LIT_CHEATCLASS)))

    # ------------------------------------------------------------------ [3]
    print("")
    print("-" * 78)
    print("[3] WORLD BRANCHES of the chain -- GameMode / GameState")
    print("-" * 78)
    for pred, label in ((lambda cn, nm: cn.endswith("GameMode") or "GameMode" in cn, "GameMode"),
                        (lambda cn, nm: cn.endswith("GameState") or "GameState" in cn, "GameState"),
                        (lambda cn, nm: cn.endswith("HUD"), "HUD")):
        hits = ue.find_instances(pred, limit=4)
        if hits:
            for o, cn, nm in hits:
                print("  %-10s 0x%X  class=%s  name=%s" % (label, o, cn, nm))
        else:
            print("  %-10s none live" % label)

    # ------------------------------------------------------------------ [4]
    print("")
    print("-" * 78)
    print("[4] ULokiGlobals -> DebugGlobals -> CDO.LokiPlayerCheats (soft class)")
    print("-" * 78)
    gcdo, gname = ue.find_cdo("LokiGlobals")
    if not gcdo:
        g = ue.find_instances(lambda cn, nm: cn.endswith("LokiGlobals"), limit=2, skip_cdo=False)
        gcdo, gname = (g[0][0], g[0][2]) if g else (0, "")
    if not gcdo:
        print("  >>> no LokiGlobals object. Section VOID.")
    else:
        print("  LokiGlobals object   : 0x%X  %s" % (gcdo, gname))
        r = ue.prop_on_obj(gcdo, "DebugGlobals")
        if not r:
            print("  DebugGlobals         : PROPERTY NOT FOUND (schema.txt says it exists"
                  " on LokiGlobals -> walk failure, VOID)")
        else:
            off, ty, esz, decl, _pa = r
            dg = ue.r.u64(gcdo + off)
            print("  DebugGlobals @+0x%X [%s] -> 0x%X  %s"
                  % (off, ty, dg, ("(UClass '%s')" % ue.oname(dg)) if looks_ptr(dg) else "(NULL)"))
            if looks_ptr(dg):
                # the value is a UClass*; its CDO carries the defaults
                dcdo = 0
                want = "Default__" + ue.oname(dg)
                for o, cls, nidx in ue.build_index():
                    if ue.fname(nidx) == want:
                        dcdo = o
                        break
                print("  DebugGlobals CDO     : 0x%X  (%s)" % (dcdo, want))
                if dcdo:
                    r2 = ue.prop_on_obj(dcdo, "LokiPlayerCheats")
                    if not r2:
                        print("  .LokiPlayerCheats    : PROPERTY NOT FOUND -> VOID row")
                    else:
                        o2, t2, e2, d2, _p2 = r2
                        print("  .LokiPlayerCheats @+0x%X [%s] = %s"
                              % (o2, t2, soft_path(ue, dcdo + o2)))
                        print("      <EMPTY> means the game never had a class to spawn, so")
                        print("      AddLokiPlayerCheats being empty is not the only reason")
                        print("      no instance exists. A real path means the CLASS is")
                        print("      available for OUR SpawnActorCls to use (Route A).")

    # ------------------------------------------------------------------ [5]
    print("")
    print("-" * 78)
    print("[5] TARGET UFunctions -- does UFunction.Func (+0xE0) match the offline RVA?")
    print("-" * 78)
    print("  A mismatch on EVERY row means --base is wrong (or the game updated) and")
    print("  the offline thunk table is unusable for a Func swap. A mismatch on ONE")
    print("  row is a real finding about that function.")
    print("")
    match = miss = absent = 0
    for cls, fname_, rva, note in THUNKS:
        fobj, decl = find_function(ue, cls, fname_)
        if not fobj:
            print("  %-22s %-28s UFUNCTION NOT FOUND" % (cls, fname_))
            absent += 1
            continue
        fptr = ue.r.u64(fobj + O_UFUNC_FUNC)
        got = fptr - base
        ok = (got == rva)
        match += 1 if ok else 0
        miss += 0 if ok else 1
        print("  %-22s %-28s UFunction=0x%X  Func=0x%X  rva=0x%08X  expect 0x%08X  %s"
              % (cls, fname_, fobj, fptr, got, rva, "MATCH" if ok else "**MISMATCH**"))
        print("        decl on %-20s  %s" % (decl, note))
    print("")
    print("  thunk table: %d match, %d mismatch, %d UFunction not found" % (match, miss, absent))
    if miss and not match:
        print("  >>> EVERY row mismatched -> --base is probably wrong. VOID, not a finding.")

    print("")
    print("-" * 78)
    print("RPM stats: %d reads, %d failed." % (rdr.reads, rdr.fails))
    print("A NULL/zero above is only a finding if [CTRL] passed. If a control failed,")
    print("record the run as VOID, not as evidence.")
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
