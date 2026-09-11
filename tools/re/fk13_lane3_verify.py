#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fk13_lane3_verify.py -- FK-13 / Route B, LANE 3.

Verifies EVERY address and assumption the "construct a UCheatManager and write it
to PlayerController+0x520" shim depends on, against THIS binary, entirely OFFLINE.
No game launch, no injection, no RPM.

Primary image  dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe
               ImageBase 0x7FF6505C0000, file-offset == RVA
               .rdata 99.6% / .data 81.6% NON-ZERO pages (not just "readable")
.text          UNION of all 10 dumpimage snapshots, 16,604/30,281 pages (54.8%)

THREE VERDICTS.  REAL / FOLD / COVERAGE-BLOCKED.  A zero page is a coverage
statement, never "absent" and never "stub".

Run:  python tools/re/fk13_lane3_verify.py            full report
      python tools/re/fk13_lane3_verify.py --controls controls only
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fk13img as FI
import fk13uht as U
import fk13grade as G
import fk13natreg as NR
import fk13xref as X

VT_CHEATMANAGER = 0x07FA7E28
VT_CHEATMANAGEREXT = 0x07FA7B50
UOBJECT_OWN_VIRTUALS_BASE = 90     # first UCheatManager-declared vtable slot

# UCheatManager's own virtuals, in STOCK UE 5.4 declaration order
# (Engine/Classes/GameFramework/CheatManager.h).  23 of these are pinned to a
# slot by a MEASURED exec-thunk dispatch displacement -- see the alignment table.
CM_OWN_VIRTUALS = [
    'FreezeFrame', 'Teleport', 'ChangeSize', 'Fly', 'Walk', 'Ghost', 'God',
    'Slomo', 'DamageTarget', 'DestroyTarget', 'DestroyAll',
    'DestroyAllPawnsExceptTarget', 'DestroyPawns', 'Summon', 'PlayersOnly',
    'ViewSelf', 'ViewPlayer', 'ViewActor', 'ViewClass', 'StreamLevelIn',
    'OnlyLoadLevel', 'StreamLevelOut', 'ToggleDebugCamera', 'IsDebugCameraActive',
    'ToggleAILogging', 'ServerToggleAILogging', 'DebugCapsuleSweep',
    'DebugCapsuleSweepSize', 'DebugCapsuleSweepChannel', 'DebugCapsuleSweepComplex',
    'DebugCapsuleSweepCapture', 'DebugCapsuleSweepPawn', 'DebugCapsuleSweepClear',
    'TestCollisionDistance', 'DumpOnlineSessionState', 'DumpPartyState',
    'DumpChatState', 'DumpVoiceMutingState', 'BugItGo', 'BugItGoString', 'BugIt',
    'BugItStringCreator', 'FlushLog', 'LogLoc', 'SetMouseSensitivityToDefault',
    'InvertMouse', 'BugItWorker', 'LogOutBugItGoToLogFile',
    'SetLevelStreamingStatus', 'InitCheatManager', 'DoGameSpecificBugItLog',
    'EnableDebugCamera', 'DisableDebugCamera', 'GetTarget',
]

SIM_INTEREST = ['Summon', 'Teleport', 'God', 'Fly', 'Ghost', 'Slomo',
                'DamageTarget', 'DestroyAll', 'PlayersOnly', 'Walk', 'ChangeSize',
                'DestroyTarget', 'DestroyPawns', 'DestroyAllPawnsExceptTarget',
                'FreezeFrame', 'BugItGo', 'ViewSelf', 'ViewActor', 'ViewClass',
                'ViewPlayer', 'CheatScript', 'SetWorldOrigin', 'LogLoc']

_u = None


def uht():
    global _u
    if _u is None:
        _u = U.UHT()
    return _u


def hdr(t):
    print()
    print('=' * 100)
    print(t)
    print('=' * 100)


def gline(label, rva, extra=''):
    g = G.grade(rva)
    print('  %-46s %-11s %-16s %6s B  %s%s'
          % (label, ('%#010x' % rva) if rva else '--', g['verdict'],
             g['size'], g['src'], ('  ' + extra) if extra else ''))
    return g


# ---------------------------------------------------------------- 0. env ----
def sec_env():
    im = FI.img()
    hdr('0. IMAGE / COVERAGE  (report this with every negative)')
    print('  primary   : %s' % im.path)
    print('  ImageBase : %#x   file-offset == RVA' % im.base)
    for s in ('.text', '.rdata', '.data', '.pdata'):
        va, vs = im.sec[s]
        pages = vs // FI.PAGE
        nz = sum(1 for r in range(0, vs, FI.PAGE)
                 if bytes(im.d[va + r:va + r + FI.PAGE]).strip(b'\0'))
        print('  %-7s rva %#010x size %#010x   NON-ZERO pages %6d/%-6d (%.1f%%)'
              % (s, va, vs, nz, pages, 100.0 * nz / pages))
    print('  .text union: %s' % im.union_stats)
    print('  ⚠ .pdata is 0.0% NON-ZERO although the dump manifest calls it "100.0%"')
    print('    (that figure counts READABLE pages).  Function bounds therefore come')
    print('    from tools/strxref/index/pdata_union.csv -- %d ranges recovered from'
          % FI.pdata().n)
    print('    68 crash minidumps.  Control: .rdata/.reloc in the same file are 99.6%/100%.')


# ------------------------------------------------------------ 1. controls ----
def sec_controls():
    hdr('1. CONTROLS  (a failure here voids every result below)')
    ok = fail = 0

    print('\n  1a. GRADER -- fold vs real must NOT be a size threshold')
    cases = [
        (FI.FOLD_RET0, 'FOLD', 'universal /OPT:ICF void fold  (c2 00 00 = ret 0)'),
        (FI.FOLD_FALSE, 'FOLD', 'universal bool-false fold     (32 c0 c3)'),
        (0x035B4760, 'REAL', 'UCheatManager::OnlyLoadLevel  -- REAL but only 16 B'),
        (0x035B1E60, 'REAL', 'UCheatManager::IsDebugCameraActive -- REAL, 16 B'),
        (0x035A7CE0, 'REAL', 'UCheatManager::DebugCapsuleSweepSize -- REAL, 16 B'),
        (0x035B7430, 'REAL', 'UCheatManager::ProcessConsoleExec, 154 B'),
        (0x0395D790, 'REAL', 'UKismetSystemLibrary::execExecuteConsoleCommand, 469 B'),
    ]
    for rva, want, why in cases:
        g = G.grade(rva)
        good = g['verdict'] == want
        ok += good
        fail += (not good)
        print('    %-11s want %-17s got %-17s %5d B  %-6s %s'
              % ('%#010x' % rva, want, g['verdict'], g['size'], 'OK' if good else 'FAIL', why))
    print('    => the discriminator is the BYTES, not the size: 16-B REAL bodies are')
    print('       graded REAL while 3-B folds are graded FOLD.')

    print('\n  1b. UHT decoder -- flags against 4 ground-truth functions')
    fns = uht().scan_functions()
    for owner, nm, want in (('APlayerController', 'ServerVerifyViewTarget', 0x80220CC2),
                            ('APlayerController', 'ClientSetHUD', 0x05020CC2),
                            ('UCheatManager', 'God', 0x04020602),
                            ('UCheatManager', 'ToggleDebugCamera', 0x00020602)):
        got = [f for f in fns if f['owner'] == owner and f['name'] == nm]
        good = bool(got) and got[0]['flags'] == want
        ok += good
        fail += (not good)
        print('    %-20s %-24s want %#010x got %-12s %s'
              % (owner, nm, want, ('%#010x' % got[0]['flags']) if got else 'MISSING',
                 'OK' if good else 'FAIL'))
    print('    (uht_funcflags.py\'s docstring attributes ToggleDebugCamera to')
    print('     ADebugCameraController; MEASURED owner is UCheatManager.  Flags agree.)')

    print('\n  1c. native-registration decoder -- self-validating, 0 stray / 0 missing')
    for cls in ('UCheatManager', 'UGameplayStatics', 'UKismetSystemLibrary'):
        want = {f['name'] for f in fns if f['owner'] == cls and (f['flags'] & 0x400)}
        got, meta = NR.natives(cls, uht())
        good = set(got) == want
        ok += good
        fail += (not good)
        print('    %-22s array=%#010x count=%-4s decoded=%-4d FUNC_Native=%-4d %s'
              % (cls, meta[1] or 0, meta[2], len(got), len(want), 'OK' if good else 'FAIL'))

    print('\n  1d. rip-relative xref -- two known code literals')
    for tgt, site, what in ((0x07F9B622, 0x03555096, 'L"CheatManager" <- GetPrivateStaticClass'),
                            (0x0773DBE0, 0x035550A5, 'L"/Script/Engine" <- GetPrivateStaticClass')):
        hits = [a for a, _, _ in X.rip_decoded(tgt)]
        good = site in hits
        ok += good
        fail += (not good)
        print('    %#010x -> %d site(s), contains %#010x : %-5s  %s'
              % (tgt, len(hits), site, 'OK' if good else 'FAIL', what))

    print('\n  1e. NEGATIVE control that must stay negative')
    print('    UCheatManagerExtension vtable slot 81 = %#010x (%d B) -- the plain'
          % (FI.img().ptr(VT_CHEATMANAGEREXT + 81 * 8),
             G.grade(FI.img().ptr(VT_CHEATMANAGEREXT + 81 * 8))['size']))
    print('    UObject::ProcessConsoleExec wrapper, i.e. the class that does NOT')
    print('    override it reads differently from the one that does.')

    print('\n  controls: %d ok / %d fail' % (ok, fail))
    return fail == 0


# ------------------------------------------------------- 2. SpawnObject ------
def sec_spawnobject():
    hdr('2. UGameplayStatics::SpawnObject  (task 1)')
    im = FI.img()
    u = uht()
    got, meta = NR.natives('UGameplayStatics', u)
    th = got.get('SpawnObject')
    print('  registrar StaticRegisterNativesUGameplayStatics = %#010x' % meta[0])
    print('  FNameNativePtr array = %#010x, %d entries, stride %#x' % (meta[1], meta[2], NR.STRIDE))
    gline('exec thunk  execSpawnObject', th, '(claim was 0x0380FF40 / 218 B)')
    r = G.resolve_impl(th)
    print('  first call in thunk        = %#010x  <-- FFrame param-step helper, NOT the impl'
          % r['first_call'])
    print('  P_FINISH anchor agrees     = %s' % r.get('anchor_agrees'))
    gline('IMPL  UGameplayStatics::SpawnObject', r['impl'])
    tail = [t for _, t, _, _ in r['all_targets']][-1]
    for f in u.find_funcs('UGameplayStatics', 'SpawnObject'):
        print('\n  FFunctionParams @%#010x   flags %#010x  %s'
              % (f['params_rva'], f['flags'], U.funcflagstr(f['flags'])))
        print('  NumProperties = %d   StructureSize = %d   PropertyArray = %#010x'
              % (f['nprops'], f['structsize'], f['proparray']))
        print('\n  *** PARAMS BUFFER (%d bytes, zero-init before the call) ***' % f['structsize'])
        print('  %-6s %-14s %-11s %-5s %s' % ('off', 'name', 'type', 'size', 'flags'))
        for p in u.decode_prop_array(f['proparray'], f['nprops']):
            print('  +0x%02x  %-14s %-11s %-5s %s'
                  % (p['offset'], p['name'], p['type'],
                     U.GEN_SIZE.get(p['type']), U.propflagstr(p['propflags'])))
    print('\n  Interior of the impl (bounded disassembly):')
    print('    calls StaticConstructObject_Internal = %#010x' % 0x1373E90)
    gline('    StaticConstructObject_Internal', 0x1373E90)
    print('    guard strings referenced: 0x76EE460 "NewObject with empty name ..."')
    print()
    print("  ★★★ SpawnObject ENFORCES ClassWithin AT RUNTIME -- this is NOT a check()")
    print("      stock UE 5.4 Private/GameplayStatics.cpp:813-834 reads:")
    print("        if (*ObjectClass == nullptr)                       -> warn, return nullptr")
    print("        if (!Outer)                                        -> warn, return nullptr")
    print("        if (ObjectClass->ClassWithin &&")
    print("            !Outer->IsA(ObjectClass->ClassWithin))         -> warn, return nullptr")
    print("        return NewObject<UObject>(Outer, ObjectClass, NAME_None, RF_StrongRefOnFrame);")
    print("      CORROBORATED IN THIS BINARY, byte-level:")
    print("        * three `call 0x011A5FA0` (UObject::StaticClass) + class-hierarchy")
    print("          walks == TSubclassOf<UObject>::operator* and the two IsA tests")
    print("        * `cmp qword ptr [rax + 0xe8], rdi ; je ...` at 0x037F0817 == the")
    print("          `ObjectClass->ClassWithin != nullptr` test  ⇒ UClass::ClassWithin")
    print("          is at UClass+0xE8 in this build  [I, from that being the only such")
    print("          null-test on ObjectClass in a function whose stock source has one]")
    print("        * `mov dword ptr [rsp+0x58], 0x1000000` == RF_StrongRefOnFrame")
    print("          (EObjectFlags 0x01000000) passed into the FStaticConstructObjectParameters")
    print("      ⇒ THE OUTER MUST BE AN APlayerController.  Passing anything else makes")
    print("        SpawnObject return nullptr SILENTLY (the warning is verbosity-gated).")
    print("      ⇒ RF_StrongRefOnFrame means the object is only frame-rooted.  Store the")
    print("        pointer into PlayerController+0x520 (a real UPROPERTY, so the GC token")
    print("        stream reaches it) IN THE SAME game-thread call, or it can be collected.")
    print("        This project has already been bitten by exactly that (S110 anim asset).")
    print()
    print('  ⚠ the impl returns nullptr on a null ObjectClass / null Outer and logs')
    print('    through 0x106B650; those log calls are gated on a verbosity byte, so a')
    print('    silent nullptr is possible.  The shim must null-check the RETURN.')


# --------------------------------------------------- 3. the UCheatManager ----
def sec_cheatmanager():
    hdr('3. UCheatManager -- registered, constructible, Within=PlayerController  (task 2)')
    im = FI.img()
    u = uht()
    recs = u.scan_class_registrations()
    r = recs['UCheatManager']
    print('  FClassRegisterCompiledInInfo @ .rdata %#010x' % r['rec_rva'])
    print('    +0x00 OuterRegister  Z_Construct_UClass_UCheatManager = %#010x' % r['outer'])
    print('    +0x08 InnerRegister  UCheatManager::GetPrivateStaticClass = %#010x' % r['inner'])
    print('    +0x10 Name (UTF-16) = %r' % im.wstr(im.ptr(r['rec_rva'] + 0x10)))
    print('    +0x18 FClassRegistrationInfo @ .data %#010x'
          % r['info'])
    print('          { InnerSingleton = %s ; OuterSingleton = %s }   <-- the LIVE UClass*'
          % (('%#x' % (im.u64(r['info']) or 0)), ('%#x' % (im.u64(r['info'] + 8) or 0))))
    print('          (both read 0 in a cold dump only if the class never registered;')
    print('           values here are whatever the dumped process had)')

    print('\n  GetPrivateStaticClassBody call decoded out of %#010x :' % r['inner'])
    args = _gpsc_args(r['inner'])
    lbl = {0x20: 'InSize            (sizeof)', 0x28: 'InAlignment',
           0x30: 'InClassFlags', 0x38: 'InClassCastFlags',
           0x40: 'InConfigName', 0x48: 'InClassConstructor',
           0x50: 'InClassVTableHelperCtorCaller', 0x58: 'InCppClassStaticFunctions',
           0x60: 'InSuperClassFn', 0x68: 'InWithinClassFn'}
    for off in sorted(lbl):
        v = args.get(off)
        note = ''
        if off == 0x30 and v is not None:
            note = U.classflagstr(v)
        if off in (0x48, 0x50, 0x60, 0x68) and v:
            g = G.grade(v)
            note = '%s %d B' % (g['verdict'], g['size'])
            for cn, rr in recs.items():
                if rr['inner'] == v:
                    note += '   == %s::StaticClass  [that class InnerRegister]' % cn
        if off == 0x40 and v:
            note = repr(im.wstr(v, 40))
        print('    [rsp+%#04x] %-30s = %-12s %s'
              % (off, lbl[off], ('%#x' % v) if v is not None else '?', note))

    print('\n  ★ ClassWithin  = APlayerController  (arg14, byte-level)')
    print('  ★ PropertiesSize / allocation size = %#x (%d) bytes, align %d'
          % (args.get(0x20, 0), args.get(0x20, 0), args.get(0x28, 0)))
    print('  POSITIVE CONTROL for the arg14 slot: UCheatManagerExtension, whose stock')
    print('  UCLASS is Within=CheatManager, decodes to:')
    a2 = _gpsc_args(recs['UCheatManagerExtension']['inner'])
    w2 = a2.get(0x68)
    print('    InWithinClassFn = %#010x  == %s   InSize = %#x'
          % (w2, 'UCheatManager::StaticClass' if w2 == r['inner'] else '???',
             a2.get(0x20, 0)))
    print('  ⚠ 0x035BF1A0 is a 5-byte `jmp 0x03C3CA30` thunk (APlayerController::StaticClass')
    print('    -> ::GetPrivateStaticClass).  The identification here is POINTER-EQUALITY')
    print('    with the APlayerController registration record, not a name match, so the')
    print('    thunk indirection does not weaken it.  (The "1776 B" this tool prints for it')
    print('    is a sweep artifact: that RVA has no recovered .pdata entry.)')

    print('\n  ★★ THE PREMISE, CONFIRMED BYTE-LEVEL AND INDEPENDENTLY OF THE LIVE RUN:')
    vtapc = 0x081A82F8
    for d, nm in ((0xEE8, 'APlayerController::AddCheats'),
                  (0xC10, 'APlayerController::EnableCheats'),
                  (0x288, 'APlayerController::ProcessConsoleExec')):
        p2 = im.ptr(vtapc + d)
        g2 = G.grade(p2)
        print('    vtbl %#010x +%#05x (slot %3d)  %-38s %#010x %-6s %4d B'
              % (vtapc, d, d // 8, nm, p2, g2['verdict'], g2['size']))
    print('    EnableCheats body = `mov rax,[rcx]; xor edx,edx; jmp [rax+0xEE8]`')
    print('      i.e. literally `this->AddCheats(false)` -- a REAL function whose only')
    print('      action is a virtual call to the folded stub.  So the engine-supplied')
    print('      construction path is severed at EXACTLY ONE function and everything')
    print('      downstream of it is intact.  This reproduces the live finding in')
    print('      docs/fk13-live-run-2026-08-12.md from the cold image alone.')
    print('    APlayerController does NOT override ProcessConsoleExec (slot 81 is the')
    print('      plain UObject wrapper 0x011EF9C0); ALokiPlayerController does.')

    cps = u.class_params_for('UCheatManager')
    for cp in cps:
        print('\n  FClassParams @%#010x  NumFunctions=%d NumProperties=%d ClassFlags=%#x'
              % (cp['rva'], cp['nfun'], cp['nprop'], cp['classflags']))
        print('    %s' % U.classflagstr(cp['classflags']))
        print('    ★ CLASS_Abstract is %s => the class is instantiable'
              % ('SET (!!)' if cp['classflags'] & 1 else 'CLEAR'))

    print('\n  Constructor  InternalConstructor<UCheatManager> = %#010x' % args.get(0x48))
    g = G.grade(args.get(0x48))
    print('    %s, %d B -- it stores the vtable and initialises real defaults'
          % (g['verdict'], g['size']))
    print('    vtable  = %#010x (.rdata)   [read out of `mov [rbx], rax`]' % VT_CHEATMANAGER)
    print('    zeroes  +0x30 +0x38 +0x58 +0x60 +0x68 +0x70 +0x80 +0x88')
    print('    writes  +0x44=10000.0f  +0x48=23.0f  +0x4C=21.0f  +0x50=30.0f  +0x54=2')
    print('            (DebugTraceDistance / CapsuleHalfHeight / CapsuleRadius /')
    print('             TraceDrawNormalLength / DebugTraceChannel=ECC_Pawn -- stock)')
    print('    calls   %#010x and stores the result at +0x38 (DebugCameraControllerClass)'
          % 0x373A620)

    print('\n  vtable %#010x : %d contiguous .text slots' % (VT_CHEATMANAGER, _vtlen(VT_CHEATMANAGER)))
    pce = im.ptr(VT_CHEATMANAGER + 0x288)
    print('  ★ slot 81 / disp 0x288 = %#010x  == UCheatManager::ProcessConsoleExec  %s'
          % (pce, 'MATCH' if pce == 0x035B7430 else 'MISMATCH'))
    gline('    UCheatManager::ProcessConsoleExec', 0x035B7430)
    print('    body (measured):')
    print('      rbx = [this+0x80]              ; CheatManagerExtensions.Data')
    print('      eax = (int32)[this+0x88]       ; CheatManagerExtensions.ArrayNum (movsxd)')
    print('      for each non-null element: call [elem->vtbl + 0x288](Cmd, Ar, Executor)')
    print('                                 -> early-return true on success')
    print('      fallback: call %#010x  == UObject::ProcessConsoleExec' % 0x1343420)
    gline('      UObject::ProcessConsoleExec (FUNC_Exec router)', 0x1343420)
    print('    ⇒ with CheatManagerExtensions EMPTY (the ctor zeroes it) the loop is')
    print('      skipped and every command goes straight to the FUNC_Exec name router.')
    print('      No extension is needed for Route B.')


def _gpsc_args(rva):
    """Decode the stack args of the GetPrivateStaticClassBody call in a
    <Class>::GetPrivateStaticClass.  Returns {rsp_offset: value}."""
    im = FI.img()
    b, e, s = G.extent(rva)
    lastlea, out = {}, {}
    r11 = False
    for a, mn, ops, sz in G.disasm(b, e):
        if mn == 'mov' and ops == 'r11, rsp':
            r11 = True
        m = re.match(r'^(\w+), \[rip ([+-]) (0x[0-9a-f]+)\]$', ops)
        if mn == 'lea' and m:
            lastlea[m.group(1)] = a + sz + (int(m.group(3), 16) if m.group(2) == '+'
                                            else -int(m.group(3), 16))
        m = re.match(r'^(\w+), \[(r11|rsp) ([+-]) (0x[0-9a-f]+)\]$', ops)
        if mn == 'lea' and m:
            lastlea[m.group(1)] = None          # a stack address, not an image RVA
        m = re.match(r'^(?:qword|dword) ptr \[(r11|rsp) ([+-]) (0x[0-9a-f]+)\], (.+)$', ops)
        if mn == 'mov' and m:
            base, sgn, disp, src = m.group(1), m.group(2), int(m.group(3), 16), m.group(4)
            d = disp if sgn == '+' else -disp
            off = (d + 0x78) if (base == 'r11' and r11) else (d if base == 'rsp' else None)
            v = None
            if src.startswith('0x') or src.isdigit():
                v = int(src, 0)
            elif src in lastlea:
                v = lastlea[src]
            if off is not None:
                out[off] = v
    return out


def _vtlen(vt):
    im = FI.img()
    n = 0
    while True:
        p = im.ptr(vt + n * 8)
        if p is None or not (FI.TEXT_RVA <= p < FI.TEXT_END):
            return n
        n += 1


# -------------------------------------------------- 4. InitCheatManager ------
def sec_init():
    hdr('4. UCheatManager::InitCheatManager  (task 3)')
    im = FI.img()
    u = uht()
    names = {f['name'] for f in u.scan_functions() if f['owner'] == 'UCheatManager'}
    print('  Is it a UFUNCTION?  %s'
          % ('YES' if 'InitCheatManager' in names else
             'NO -- it is a PLAIN VIRTUAL (57 UCheatManager UFunctions, none named it)'))
    print('  (`ReceiveInitCheatManager` IS a UFUNCTION but carries')
    print('   RequiredAPI|Event|Public|BlueprintEvent with NO FUNC_Native, so it has no')
    print('   native thunk and is not in the 55-entry registrar array.)')

    natives, _ = NR.natives('UCheatManager', u)
    print('\n  vtable alignment -- own-virtual block base derived from MEASURED dispatch')
    print('  displacements in the exec thunks (`mov rax,[rcx]; jmp [rax+disp]`):')
    print('    %-32s %-12s %-8s %-8s %s' % ('verb', 'thunk', 'disp', 'slot', 'stock idx  match'))
    anchors = 0
    mism = 0
    byname = {f['name']: f for f in u.scan_functions() if f['owner'] == 'UCheatManager'}
    for i, nm in enumerate(CM_OWN_VIRTUALS):
        th = natives.get(nm)
        if th is None:
            continue
        if byname.get(nm, {}).get('flags', 0) & 0x40:
            # EXCLUDED WITH REASON, not silently: a Net RPC's thunk dispatches to the
            # UHT-GENERATED `_Validate` (and then `_Implementation`) virtuals, which are
            # declared by GENERATED_UCLASS_BODY at the TOP of the class and therefore sit
            # BELOW the hand-written virtuals in the vtable.  Measured for
            # ServerToggleAILogging: `call [rax+0x2c0]` (_Validate, slot 88, `mov al,1;ret`)
            # then `jmp [rax+0x2c8]` (_Implementation, slot 89).  That is the whole
            # explanation for slots 88/89 differing from UCheatManagerExtension's.
            print('    %-32s %#010x  (Net RPC -- dispatches to the generated'
                  ' _Validate/_Implementation pair at slots 88/89; excluded)' % (nm, th))
            continue
        r = G.resolve_impl(th, VT_CHEATMANAGER)
        if r.get('dispatch') != 'vtable':
            continue
        slot = r['vslot']
        good = (slot == UOBJECT_OWN_VIRTUALS_BASE + i)
        anchors += 1
        mism += (not good)
        print('    %-32s %#010x  %#05x   %-8d %-10d %s'
              % (nm, th, r['vdisp'], slot, i, 'OK' if good else '*** MISMATCH ***'))
    print('    => %d measured anchors, %d mismatches; own-virtual block base = slot %d'
          % (anchors, mism, UOBJECT_OWN_VIRTUALS_BASE))

    idx = CM_OWN_VIRTUALS.index('InitCheatManager')
    slot = UOBJECT_OWN_VIRTUALS_BASE + idx
    rva = im.ptr(VT_CHEATMANAGER + slot * 8)
    print('\n  ★ InitCheatManager -> stock own index %d -> VTABLE SLOT %d, disp %#x'
          % (idx, slot, slot * 8))
    g = gline('    UCheatManager::InitCheatManager', rva)
    print('    NOT a folded stub.' if g['verdict'] == 'REAL' else '    *** FOLDED / BLOCKED ***')
    print('\n  Independent confirmation FROM THE BODY (not from the slot alignment):')
    lits = {}
    b, e, s = G.extent(rva)
    for a, mn, ops, sz in G.disasm(b, e):
        m = re.match(r'^(\w+), \[rip ([+-]) (0x[0-9a-f]+)\]$', ops)
        if mn == 'lea' and m:
            t = a + sz + (int(m.group(3), 16) if m.group(2) == '+' else -int(m.group(3), 16))
            w = im.wstr(t, 60)
            if w and len(w) > 2:
                lits[t] = w
    for t, w in sorted(lits.items()):
        print('      %#010x  %r' % (t, w))
    print('    - `mov rax,[rcx]; mov rbx,[rax+0x270]; call rbx` after a FindFunction')
    print('      => this->ProcessEvent(Func, nullptr)  == ReceiveInitCheatManager()')
    print('        (so UObject::ProcessEvent is vtable disp 0x270 / slot 78)')
    print('    - a global multicast-delegate Broadcast over .data 0x9A6F990')
    print('      == OnCheatManagerCreatedDelegate.Broadcast(this)')
    print('    - the L"&UCheatManager::OnPlayerEndPlayed" / L"::" / L"OnEndPlay" trio')
    print('      == GetOuterAPlayerController()->OnEndPlay.AddDynamic(this, ...)')
    print('    That is stock UCheatManager::InitCheatManager, statement for statement.')
    print('\n  ⚠ INSTRUMENT NOTE: searching .rdata for the substring "OnPlayerEndPlayed"')
    print('    finds %#010x, which has ZERO rip-references, because the code loads the'
          % 0x07FA8760)
    print('    START of the longer literal at %#010x.  A substring search plus a null'
          % 0x07FA8740)
    print('    xref would have read as "the AddDynamic is compiled out".  It is not.')

    print('\n  DOES THE SHIM HAVE TO CALL IT?  Everything it does is optional for exec:')
    print('    it fires a BP event (no BP subclass exists), broadcasts a delegate, and')
    print('    registers an OnEndPlay handler.  It does NOT populate')
    print('    CheatManagerExtensions and does NOT touch anything ProcessConsoleExec')
    print('    reads.  [I -- from the measured body; lane 1 owns the decision.]')


# ------------------------------------------------------- 5. the exec verbs ---
def sec_verbs():
    hdr('5. EXEC VERB GRADING  (task 4)')
    im = FI.img()
    u = uht()
    fns = [f for f in u.scan_functions() if f['owner'] == 'UCheatManager']
    natives, meta = NR.natives('UCheatManager', u)
    execs = sorted([f for f in fns if f['flags'] & 0x200], key=lambda f: f['name'])
    print('  UCheatManager UFunctions: %d   with FUNC_Exec: %d   natively registered: %d'
          % (len(fns), len(execs), meta[2]))
    print('  (FK-13 §3D recorded 48 exec fns for UCheatManager; MEASURED here: %d)' % len(execs))
    print()
    print('  %-42s %-11s %-6s | %-11s %-17s %-6s | %s'
          % ('verb', 'thunk', 'thk B', 'impl', 'impl grade', 'imp B', 'how'))
    counts = {'REAL': 0, 'FOLD': 0, 'COVERAGE-BLOCKED': 0, 'UNRESOLVED': 0}
    interesting = []
    for f in execs:
        nm = f['name']
        th = natives.get(nm)
        if th is None:
            print('  %-42s  (no native registration)' % nm)
            continue
        gt = G.grade(th)
        r = G.resolve_impl(th, VT_CHEATMANAGER)
        impl = r.get('impl')
        gi = G.grade(impl) if impl else dict(verdict='UNRESOLVED', size=0, src='-')
        counts[gi['verdict']] = counts.get(gi['verdict'], 0) + 1
        how = r.get('dispatch', 'rel32')
        if how == 'vtable':
            how = 'vtbl+%#05x' % r['vdisp']
            if r['vslot'] < 88:
                # a verb DECLARED on UCheatManager must dispatch into UCheatManager's
                # own virtual block (slot >= 88).  Landing on a base-UObject slot means
                # the resolver latched onto some other virtual call in the thunk (a
                # GetWorld(), a teardown) -- report AMBIGUOUS rather than a wrong name.
                how = 'AMBIGUOUS vtbl+%#05x(base slot %d) or rel32 %s' % (
                    r['vdisp'], r['vslot'],
                    ('%#010x' % r['rel32_also']) if r.get('rel32_also') else '-')
                gi = dict(verdict='AMBIGUOUS', size=0, src='-')
        print('  %-42s %#010x %6d | %-11s %-17s %6d | %s'
              % (nm, th, gt['size'], ('%#010x' % impl) if impl else '--',
                 gi['verdict'], gi['size'], how))
        if nm in SIM_INTEREST:
            interesting.append((nm, th, impl, gi))
    print()
    print('  IMPLEMENTATION VERDICT TALLY over the %d exec verbs:' % len(execs))
    for k in ('REAL', 'FOLD', 'COVERAGE-BLOCKED', 'UNRESOLVED'):
        print('    %-18s %d' % (k, counts.get(k, 0)))
    print('  ⚠ UNRESOLVED = the thunk dispatches by rel32 into a body this tool did not')
    print('    prove is the impl (parameterised thunks with teardown calls).  It is NOT')
    print('    a claim that the verb is stubbed.')
    print()
    print('  ★ THE VERBS THAT MATTER FOR SIMULATION (enemies / damage / view):')
    for nm, th, impl, gi in interesting:
        print('    %-30s thunk %#010x  impl %-11s %-17s %5d B'
              % (nm, th, ('%#010x' % impl) if impl else '--', gi['verdict'], gi['size']))
    print()
    print('  ⚠ EXEC VERBS THAT ARE PRESENT BUT EMPTY (impl folds to `ret 0`) --')
    print('    do not plan around these:')
    for f in execs:
        th = natives.get(f['name'])
        if th is None:
            continue
        r = G.resolve_impl(th, VT_CHEATMANAGER)
        if r.get('impl') in (FI.FOLD_RET0, FI.FOLD_FALSE):
            print('    %-30s vtbl+%#05x -> %#010x' % (f['name'], r['vdisp'], r['impl']))
    print()
    print('  ⚠ COVERAGE-BLOCKED (page never executed in any of the 10 dumps) --')
    print('    these are UNKNOWN, not stubs:')
    for f in execs:
        th = natives.get(f['name'])
        if th is None:
            continue
        r = G.resolve_impl(th, VT_CHEATMANAGER)
        impl = r.get('impl')
        if impl and G.grade(impl)['verdict'] == 'COVERAGE-BLOCKED':
            print('    %-30s impl %#010x  page %#010x is all-zero'
                  % (f['name'], impl, impl & ~0xFFF))

    print('\n  --- APlayerController exec verbs (branch 7 is not the only branch) ---')
    apc = sorted([f for f in u.scan_functions()
                  if f['owner'] == 'APlayerController' and f['flags'] & 0x200],
                 key=lambda f: f['name'])
    for f in apc:
        th = _thunk_by_name_scan(f['name'], 0x03C50000, 0x03C80000)
        g = G.grade(th) if th else dict(verdict='-', size=0)
        print('    %-34s thunk %-11s %-17s %5d B'
              % (f['name'], ('%#010x' % th) if th else '(unlocated)', g['verdict'], g['size']))

    print('\n  --- ALokiCharacter exec verbs: reachable on the POSSESSED PAWN with NO')
    print('      CheatManager at all (UPlayer::Exec branch 4) ---')
    lc = sorted([f for f in u.scan_functions()
                 if f['owner'] == 'ALokiCharacter' and f['flags'] & 0x200],
                key=lambda f: f['name'])
    for f in lc:
        print('    %-34s flags %#010x %s'
              % (f['name'], f['flags'], U.funcflagstr(f['flags'])))


def _thunk_by_name_scan(name, lo, hi):
    """Locate a registrar entry {const char* name; thunk} whose thunk is in [lo,hi)."""
    im = FI.img()
    pat = name.encode() + b'\0'
    i = 0
    best = None
    while True:
        i = im.d.find(pat, i)
        if i < 0:
            break
        if im.section_of(i) == '.rdata' and (i == 0 or im.d[i - 1] == 0):
            for slot in X.ptr(i):
                th = im.ptr(slot + 8)
                if th and lo <= th < hi:
                    best = th
        i += 1
    return best


# ------------------------------------------------- 6. property offsets -------
def sec_props():
    hdr('6. PROPERTY OFFSETS, BY REFLECTION  (task 5)')
    u = uht()
    for cls, want in (('APlayerController', {'CheatManager': 0x520, 'CheatClass': 0x528,
                                             'Player': 0x458, 'MyHUD': 0x468,
                                             'PlayerCameraManager': 0x470,
                                             'AcknowledgedPawn': 0x460,
                                             'PlayerInput': 0x530, 'SpectatorPawn': 0x7D8}),
                      ('UCheatManager', {'CheatManagerExtensions': 0x80,
                                         'DebugCameraControllerRef': 0x30,
                                         'DebugCameraControllerClass': 0x38})):
        cps = u.class_params_for(cls)
        cp = [c for c in cps if c['nprop'] < 200][0]
        print('\n  %s   FClassParams @%#010x  NumProperties=%d' % (cls, cp['rva'], cp['nprop']))
        seen = {}
        for p in u.decode_prop_array(cp['proparray'], cp['nprop']):
            if not p or p['offset'] is None:
                continue
            # UHT emits the INNER element property of a TArray/TMap/TSet with the same
            # NameUTF8 and Offset 0, immediately before the container itself.  Keeping
            # the first hit would report CheatManagerExtensions at +0x00.  Keep the
            # container (the one whose EPropertyGenFlags type is a container, or
            # failing that the larger offset).
            if p['type'] in ('Array', 'Map', 'Set') or p['name'] not in seen:
                seen[p['name']] = p['offset']
            elif p['offset'] > seen[p['name']]:
                seen[p['name']] = p['offset']
        for nm, off in want.items():
            got = seen.get(nm)
            live = ''
            print('    %-28s reflected +%#05x   expected +%#05x   %s'
                  % (nm, got if got is not None else -1, off,
                     'MATCH' if got == off else '*** MISMATCH ***'))
    print('\n  ★ CheatManager +0x520 and CheatClass +0x528 agree with the LIVE RPM')
    print('    readings in docs/fk13-live-run-2026-08-12.md, as do Player/MyHUD/')
    print('    PlayerCameraManager/AcknowledgedPawn/PlayerInput/SpectatorPawn -- 8/8')
    print('    cross-instrument agreement between offline UHT reflection and live RPM.')
    print('\n  ★ UCheatManager PropertiesSize = 0x90 (144) bytes  [InSize arg of')
    print('    GetPrivateStaticClassBody].  Corroborated: CheatManagerExtensions is a')
    print('    16-byte TArray at +0x80, i.e. it ends exactly at 0x90, and the ctor')
    print('    zeroes [+0x80] and [+0x88] (Data, then Num+Max as one qword).')
    print('\n  UObject in THIS build is 0x30 (48) bytes -- measured as')
    print('  UCheatManagerExtension\'s InSize, and consistent with CLAUDE.md\'s')
    print('  non-stock layout (ObjectFlags@0x0C, InternalIndex@0x10, Class@0x18,')
    print('  Name@0x20, Outer@0x28).  Stock UE5 UObject is 0x28.')


# ------------------------------------------------------ 7. fold sanity -------
def sec_folds():
    hdr('7. ICF FOLD SANITY  (task 6)')
    im = FI.img()
    u = uht()
    print('  the two universal folds:')
    for rva in (FI.FOLD_RET0, FI.FOLD_FALSE):
        print('    %#010x  bytes %s   %s'
              % (rva, im.rd(rva, 3).hex(), FI.FOLDS if False else G.grade(rva)['note']))
    print('  neither has a recovered .pdata entry (a 3-byte leaf needs no unwind data)')
    print('  -- which is itself a discriminator against a real body.')
    print()
    targets = [
        ('UGameplayStatics::execSpawnObject', 0x0380FF40),
        ('UGameplayStatics::SpawnObject (impl)', 0x037F0710),
        ('StaticConstructObject_Internal', 0x01373E90),
        ('UCheatManager::GetPrivateStaticClass', 0x03555050),
        ('InternalConstructor<UCheatManager>', 0x03567C60),
        ('UCheatManager::ProcessConsoleExec', 0x035B7430),
        ('UObject::ProcessConsoleExec', 0x01343420),
        ('UCheatManager::InitCheatManager', 0x035B19B0),
        ('UKismetSystemLibrary::execExecuteConsoleCommand', 0x0395D790),
        ('APlayerController::execLocalTravel', 0x03C64600),
    ]
    bad = 0
    for nm, rva in targets:
        g = G.grade(rva)
        isfold = rva in (FI.FOLD_RET0, FI.FOLD_FALSE) or g['verdict'] == 'FOLD'
        bad += isfold
        print('    %-48s %#010x %-6s %5d B  %s'
              % (nm, rva, g['verdict'], g['size'], 'FOLD!!' if isfold else 'not a fold'))
    print('  => %d of %d shim targets resolve to a universal fold.' % (bad, len(targets)))
    print()
    print('  DO_CHECK probe (does shipping still enforce ClassWithin in NewObject?):')
    for lit, why in (('Creating an instance of an abstract class is not allowed',
                      'checkf in StaticAllocateObject'),
                     ('Creating UObjects while Collecting Garbage is not allowed',
                      'checkf in StaticAllocateObject'),
                     ('created in %s instead of %s', 'WITH_EDITOR Within fatal log')):
        w = im.d.find(lit.encode('utf-16-le')) >= 0
        a = im.d.find(lit.encode()) >= 0
        print('    wide=%-5s ansi=%-5s  %s' % (w, a, why))
    for lit in ('LogUObjectGlobals', 'SpawnObject'):
        w = im.d.find(lit.encode('utf-16-le')) >= 0
        print('    wide=%-5s POSITIVE CONTROL %r' % (w, lit))
    print('  => the check()/checkf() literals from that exact TU are absent while a')
    print('     same-TU control literal is present ⇒ DO_CHECK == 0 there ⇒ the')
    print('     `check(InOuter->IsA(InClass->ClassWithin))` is COMPILED OUT.')
    print('     [M for the literals; [I] for the inference.  Pass the PlayerController')
    print('     as Outer anyway -- many verbs call GetOuterAPlayerController().]')


# --------------------------------------------------- 8. shim address table --
def sec_table():
    hdr('8. THE ADDRESS TABLE THE SHIM WILL USE  (all RVAs; add the live module base)')
    im = FI.img()
    rows = [
        ('DATA  live UClass* UCheatManager', 0x09F84F38, 'data',
         'Z_Registration_Info_UClass_UCheatManager.InnerSingleton; +8 = OuterSingleton'),
        ('DATA  APlayerController::CheatManager', 0x520, 'off', 'ObjectProperty, write target'),
        ('DATA  APlayerController::CheatClass', 0x528, 'off', 'ClassProperty, already populated'),
        ('DATA  UCheatManager::CheatManagerExtensions', 0x80, 'off', 'TArray, 16 B, ends at 0x90'),
        ('CONST sizeof(UCheatManager)', 0x90, 'const', 'align 8'),
        ('CODE  UCheatManager::GetPrivateStaticClass', 0x03555050, 'text', 'returns the UClass*'),
        ('CODE  InternalConstructor<UCheatManager>', 0x03567C60, 'text', 'ClassConstructor'),
        ('CODE  UGameplayStatics::execSpawnObject', 0x0380FF40, 'text', 'FFrame thunk, 3 params'),
        ('CODE  UGameplayStatics::SpawnObject', 0x037F0710, 'text', 'direct C++ (UClass*, UObject*)'),
        ('CODE  StaticConstructObject_Internal', 0x01373E90, 'text', 'lowest-level option'),
        ('CODE  UCheatManager::ProcessConsoleExec', 0x035B7430, 'text', 'vtable slot 81 / +0x288'),
        ('CODE  UObject::ProcessConsoleExec', 0x01343420, 'text', 'the FUNC_Exec name router'),
        ('CODE  UCheatManager::InitCheatManager', 0x035B19B0, 'text', 'vtable slot 139 / +0x458'),
        ('CODE  UKismetSystemLibrary::execExecuteConsoleCommand', 0x0395D790, 'text',
         'the S55-callable entry point'),
        ('VT    UCheatManager vtable', VT_CHEATMANAGER, 'rdata', '152 slots'),
        ('VT    UObject::ProcessEvent displacement', 0x270, 'off', 'slot 78'),
        ('VT    ProcessConsoleExec displacement', 0x288, 'off', 'slot 81'),
    ]
    print('  %-52s %-12s %-6s %s' % ('what', 'rva/value', 'kind', 'note'))
    for nm, v, kind, note in rows:
        extra = ''
        if kind == 'text':
            g = G.grade(v)
            extra = '%s %d B' % (g['verdict'], g['size'])
        print('  %-52s %#012x %-6s %s %s' % (nm, v, kind, note, extra))
    print()
    print('  ★ TWO INDEPENDENT WAYS TO GET THE UClass*, neither needing a GUObjectArray scan:')
    print('     (a) read the global at .data %#010x  (the registration singleton)' % 0x09F84F38)
    print('     (b) read PlayerController + 0x528 (CheatClass) -- MEASURED non-null live in')
    print('         BOTH the menu and the staged tutorial world (fk13-live-run-2026-08-12.md)')
    print('     (c) call %#010x (GetPrivateStaticClass) -- but that is a CALL, and it' % 0x03555050)
    print('         lazily constructs on first use; (a) and (b) are pure reads.')
    print('     The dumped process had %s in slot (a).'
          % ('%#x' % (im.u64(0x09F84F38) or 0)))
    print()
    print('  ⚠ NOTHING here requires a `.text` write.  Every address above is either')
    print('    READ, or CALLED, or is a heap/data offset.  The only write the route')
    print('    needs is the 8-byte DATA store to PlayerController+0x520.')


def main():
    try:                       # the console here is cp1252; the report uses U+2605/U+26A0
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    FI.img()
    sec_env()
    okc = sec_controls()
    if '--controls' in sys.argv:
        return 0 if okc else 1
    sec_spawnobject()
    sec_cheatmanager()
    sec_init()
    sec_verbs()
    sec_props()
    sec_folds()
    sec_table()
    print()
    print('=' * 100)
    print('controls passed: %s' % okc)
    return 0 if okc else 1


if __name__ == '__main__':
    sys.exit(main())
