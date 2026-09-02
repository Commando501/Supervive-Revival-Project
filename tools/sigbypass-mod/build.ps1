# build.ps1 -- reproducible builds for the SUPERVIVE Revival native shims.
#
# S106 (2026-07-27). Before this the directory had 63 .cpp shims, 141 built .dll files, no build
# script and no .dll in git -- nothing in the default injection set was reproducible from a clean clone.
#
#   .\build.ps1                          # build the default injection set  -> build\
#   .\build.ps1 -Name tutorial_launch    # one shim, all its registered variants
#   .\build.ps1 -Name tutorial_launch -Variant play-vtguard
#   .\build.ps1 -All                     # every .cpp in the directory
#   .\build.ps1 -Verify                  # build, then diff each result against the committed .dll
#   .\build.ps1 -Name missions_fix -InPlace   # write beside the sources (where the injectors load from)
#   .\build.ps1 -List                    # show the registry
#
# ---------------------------------------------------------------------------------------------------
# TOOLCHAIN (MEASURED S106, re-derived from the artifacts -- not inherited from any prior note)
#
#   The committed DLLs were built with clang++, NOT MSVC cl.exe. Evidence:
#     * every shim's own header comment reads
#         "Build: clang++ -shared -O2 <f>.cpp -o <f>.dll -lkernel32"
#     * rebuilding with clang++ 21.1.6 reproduces the committed catalog_store_fix / catalog_pick_fix /
#       mainmenu_refresh_pi8 / battlepass_adopt_fix / loadout_fix / missions_fix / gft_ready_fix
#       byte-for-byte EXCEPT 3 bytes of PE TimeDateStamp (and its mirror in the debug directory).
#     * the DLLs carry a Rich header (so an MSVC link.exe linked them) reporting linker 14.42 =
#       VS2022 17.12. clang's MSVC driver invokes the detected link.exe rather than lld-link, which is
#       exactly how a clang-compiled object lands in a link.exe-produced image.
#
#   MSVC cl.exe IS usable as a fallback for MOST shims (measured: catalog_store_fix, missions_fix,
#   loadout_fix, battlepass_adopt_fix, gft_ready_fix all compile clean under /LD /MT /O2), but it
#   CANNOT build two files, and one of them is the active-route shim:
#     * tutorial_launch.cpp - uses __builtin_sqrt / __builtin_cos / __builtin_sin  (error C3861)
#     * browse_hook.cpp     - uses __attribute__((ms_abi))                         (error C2143)
#   So clang is the DEFAULT and the reference; -Toolchain msvc is a documented fallback only.
#
# ---------------------------------------------------------------------------------------------------
# HARD CONSTRAINTS ENFORCED HERE (CLAUDE.md "What NOT to do" -- every produced DLL is gated)
#
#   1. NO C++ EXCEPTION MACHINERY. The packer's vectored exception filter kills the process on any
#      C++ throw/unwind (three canary variants were tested; all died). Output is scanned for
#      __CxxFrameHandler3 / _CxxThrowException. Verified this gate does NOT false-positive: all six
#      known-good, live-proven DLLs pass it.
#   2. NO DYNAMIC CRT. An injected payload must not depend on vcruntime140.dll / msvcp140.dll /
#      api-ms-win-crt-*.dll. The import table is parsed and checked against a system-DLL allowlist.
#      (clang defaults to the static CRT on windows-msvc; MSVC needs the explicit /MT passed below.)
#   3. Everything a shim references must resolve at BUILD time -- see the link-library note.
#
# ---------------------------------------------------------------------------------------------------
# LINK LIBRARIES -- why there is no per-shim library table
#
#   MEASURED: passing an unused import library changes nothing. Building gft_ready_fix with
#   -lkernel32 -luser32 -lwininet -ladvapi32 -lshell32 produced a DLL of IDENTICAL size importing
#   ONLY KERNEL32.dll -- the linker emits an import stub only for a symbol actually referenced.
#   So every shim links the same system set. That is not laziness, it kills a real bug class: the
#   per-file "Build:" comments are WRONG for several shims (tutorial_launch's says -lkernel32 only,
#   but RM_PLAY / RM_PUPPET reference GetAsyncKeyState / GetForegroundWindow / FindWindowA and fail
#   with LNK2019 without user32 -- measured both ways). A universal set means a new shim can call any
#   Win32 API without anyone having to remember to update a table.

[CmdletBinding()]
param(
    [string]   $Name,
    [string]   $Variant,
    [switch]   $All,
    [switch]   $List,
    [switch]   $Verify,
    [switch]   $InPlace,
    [string]   $OutDir,
    [ValidateSet('auto','clang','msvc')]
    [string]   $Toolchain = 'auto',
    [string]   $Clang,
    [switch]   $VsEnv,
    [switch]   $KeepIntermediates
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

# ⚠⚠ S125 GUARD. `-Variant X` WITHOUT `-Name` used to be SILENTLY IGNORED: the script fell through to
#    the default injection set, built 11 shims and printed "11 built, 0 failed" -- which reads exactly
#    like success, and the only way to notice was to diff a `.text` hash afterwards. CLAUDE.md records
#    this as a trap; a trap that is cheaper to remove than to document is a defect, so it now refuses.
if ($Variant -and -not $Name -and -not $All) {
    throw "-Variant '$Variant' requires -Name (e.g. -Name tutorial_launch -Variant $Variant). Without -Name this used to silently build the DEFAULT SET and report success."
}

# Default output is build\ so a build NEVER clobbers a committed / known-good .dll by accident.
# -InPlace writes beside the sources (where launch-redirect.ps1 + inject-secondaries.ps1 load them).
if (-not $OutDir) {
    if ($InPlace) { $OutDir = $root } else { $OutDir = Join-Path $root 'build' }
}

# --- system import libraries linked into every shim (measured: unused ones cost nothing) ------------
$SysLibs = @('kernel32','user32','wininet','advapi32','shell32','ws2_32')

# --- import-table allowlist. Anything outside this, or matching $BannedImports, fails the build. ----
$AllowedImports = @('kernel32.dll','user32.dll','wininet.dll','advapi32.dll','shell32.dll','ws2_32.dll',
                    'ole32.dll','oleaut32.dll','gdi32.dll','psapi.dll','shlwapi.dll','version.dll',
                    'winmm.dll','dbghelp.dll','ntdll.dll','crypt32.dll')
$BannedImports  = @('vcruntime','msvcp','msvcr','api-ms-win-crt','ucrtbase')

# --- shims cl.exe provably cannot compile (measured S106) -------------------------------------------
$MsvcIncompatible = @{
    'tutorial_launch' = '__builtin_sqrt / __builtin_cos / __builtin_sin (error C3861)'
    'browse_hook'     = '__attribute__((ms_abi)) function-pointer typedef (error C2143)'
}

# --- variants: suffix -> extra -D flags. Only shims with a compile-time mode switch need an entry;
#     every other .cpp builds as a single plain <name>.dll with no registry entry at all. ------------
$Variants = @{
    # catalog_store_fix: ARM-C CONTROL ONLY (S111). Disables the memory scan entirely to test whether
    # the SafeCopy/ReadProcessMemory scan is what drives the protector (runtime.dll+1) deaths that ran
    # 11/30 vs 5/30 in the 60-launch A/B (p=0.072). ⚠ NOT A CANDIDATE — with the scan off the shim
    # cannot find the CatalogManager, so the roster/store never populate and the jz self-restore never
    # fires. Never inject this for anything but the control arm, and never hold it long.
    # catalog_store_fix. ★ KNOJZ now DEFAULTS TO 1, so the PLAIN build has NO .text patch — that is
    # the shipping build (S111: the jz-NOP was the protector trigger, 11/12 vs 0/5, p=0.00097, and the
    # [+0x354] DATA poke alone renders the roster, screenshot-verified). Every entry below is a CONTROL
    # or a ROLLBACK, never a candidate. ⚠ The KNOSCAN arms pin KNOJZ=0 on purpose: arms C/E/E1/E2 were
    # flown WITH the patch, and dropping that pin would silently change what those names mean AND make
    # 'noscan' byte-identical to 'noscan-nojz'.
    'catalog_store_fix' = @{
        ''              = @()                                             # ★ SHIPPING: scan on, NO .text patch
        'jzpatch'       = @('-DKNOJZ=0')                                  # ROLLBACK: old .text jz-NOP behaviour
        'noscan'        = @('-DKNOSCAN=1','-DKNOJZ=0')                    # arm C / arm E: no scan, patch ON
        'noscan-noveh'  = @('-DKNOSCAN=1','-DKNOJZ=0','-DKNOVEH=1')       # arm E1: - VEH
        'noscan-noslot' = @('-DKNOSCAN=1','-DKNOJZ=0','-DKNOSLOT=1')      # arm E2: - BuildStub + slot-110
        'noscan-nojz'   = @('-DKNOSCAN=1')                                # arm E3: no scan AND no patch
    }
    'tutorial_launch' = @{
        # RunMode switch, tutorial_launch.cpp:93. Default when KRUNMODE is unset is RM_CHEATSPAWN.
        'fo'         = @('-DKRUNMODE=RM_FORCEOPEN')
        # ★ S112 -- the missing arm of the module-image question. S112 measured 8 of 20 non-arming
        #   launches DYING DURING STAGING with only gft+fo resident (probe never injected, so RM_PLAY's
        #   standing .text patch cannot explain them); every such death that dumped was OURS/protector.
        #   `fo` makes TWO module-image writes and they are confounded in every run ever flown: a
        #   TRANSIENT <=8 s `.text` prologue jmp, and a <=25.5 s `.rdata` slot-285 CustomLogin patch.
        #   S111 only ever measured `.text`; "`.rdata` is caught too" is an S61-era INFERENCE.
        #   This drops the `.rdata` write and keeps the `.text` one => one variable.
        #   ⚠ May break the route (the strict native Login can fatal). All three outcomes inform --
        #   see the rationale block at the InstallCustomLogin call site in tutorial_launch.cpp.
        'fo-nologinvt' = @('-DKRUNMODE=RM_FORCEOPEN','-DKNOLOGINVT=1')            # -1 dim: no .rdata vtable write
        'sp'         = @('-DKRUNMODE=RM_SPAWNPOSSESS')
        # ★ S111 — control arm for the ability-system GATE fix (KGASSTORAGE, default ON in 'sp').
        #   The fix writes the carrier's ASC into the hero's AbilitySystemComponentStorage@0xF00,
        #   because the hero-side getter the wiring reads is literally `mov rax,[rcx+0x710]; ret` on
        #   that field, and it returning NULL is what makes TryUpdateAbilitySystem's sibling bail.
        #   With KGASSTORAGE=0 expect the S111 baseline exactly: PS+0x650 populated, PS+0x658 NULL,
        #   ASC.AvatarActor NULL. See docs/s111-asc-census.md §11.
        'sp-nostorage' = @('-DKRUNMODE=RM_SPAWNPOSSESS','-DKGASSTORAGE=0')
        'cheatspawn' = @('-DKRUNMODE=RM_CHEATSPAWN')
        'makemesh'   = @('-DKRUNMODE=RM_MAKEMESH')
        'topdowncam' = @('-DKRUNMODE=RM_TOPDOWNCAM')
        'drivechain' = @('-DKRUNMODE=RM_DRIVECHAIN')
        'puppet'     = @('-DKRUNMODE=RM_PUPPET')
        # ------------------------------------------------------------------------------------------
        # FK-7 A/B SET (rebuilt S106d, 2026-07-29). KGCROOT / KVTGUARD / KPIMUTEX / KXFORMFIX all
        # default to 1 in the source (tutorial_launch.cpp: KPIMUTEX, KGCROOT, KVTGUARD, KXFORMFIX),
        # and KTESTACTOR now defaults to 0, so the un-suffixed 'play' build is THE CANDIDATE:
        # every guard on, both cause fixes applied, no leftover diagnostic body.
        #
        # ★ EVERY CONTROL BELOW DIFFERS FROM 'play' IN EXACTLY ONE DIMENSION. That is the whole point
        #   of this table -- three earlier artifacts violated it and would have wasted a live run:
        #     * 'play-gcroot' / 'play-vtguard' carried IDENTICAL flags to 'play' and to each other, so
        #       A/B-ing them compared a DLL with itself (measured: 2,048 differing bytes, ENTIRELY the
        #       embedded export filename; same size, same 442 .pdata entries, same string counts).
        #       REMOVED -- use 'play'.
        #     * 'play-nogcroot' flipped KGCROOT *and* KPIMUTEX = a TWO-variable control. FIXED.
        #     * a plain 'tutorial_launch_play.dll' from 2026-07-26 sat beside them with 0 '[VTG]'
        #       strings (the pre-fix build, most obvious name). DELETED from the source dir; this
        #       registry regenerates it correctly.
        'play'            = @('-DKRUNMODE=RM_PLAY')                              # ★ CANDIDATE: all fixes on
        # ★★★ S114 "ROUTE B" (docs/fk13-console-exec-settled.md, docs/fk13-live-run-2026-08-12.md).
        #   Constructs a UCheatManager with the live PlayerController as Outer and stores it in the
        #   reflected `CheatManager` UPROPERTY (+0x520), which the shipping build never does because
        #   `AddCheats` compiled out under `UE_WITH_CHEAT_MANAGER = (1 && !UE_BUILD_SHIPPING)`. The
        #   class was never stripped: `CheatClass` (+0x528) is populated in BOTH the menu and the
        #   staged tutorial world (MEASURED). Installing it puts UCheatManager's 42 real exec verbs on
        #   `UPlayer::Exec` branch 7, reachable by ExecuteConsoleCommand.
        #   Writes: ONE aligned qword into a heap UObject field, readback-verified. NO module image.
        #   One-shot (sets g_done), so the Func-swap is restored promptly -- a far smaller exposure
        #   window than RM_PLAY's 600 s hold.
        'cheatmgr'        = @('-DKRUNMODE=RM_CHEATMGR')
        #   ★ MEASURED 2026-08-12, menu route: 'cheatmgr' arms on KFSNAME="ReceiveTickClient" and that
        #   function is NOT DISPATCHED AT THE MENU -- the shim's own watchdog printed
        #   "NO GAME-THREAD HITS after 8000 ms (allThreadCalls=0 swapped=2)" and DoCheatMgr never ran.
        #   ReceiveTickClient was profiled in a SETTLED TUTORIAL WORLD (S112), so it is the right target
        #   in-world and the wrong one at the menu. 'cheatmgr-any' swaps EVERY BP UFunction instead, so
        #   it catches whatever the menu actually ticks. Footprint is ~17k pointers rather than 2, which
        #   S112 measured at 0/8 deaths over 600 s holds -- and this mode is one-shot, so its window is
        #   seconds, not minutes. Use 'cheatmgr' in-world, 'cheatmgr-any' at the menu.
        'cheatmgr-any'    = @('-DKRUNMODE=RM_CHEATMGR','-DKFSNAME=\"\"')
        #   +1 dim: also EXECUTES a verb in-shim as a positive control. Separate variant because it
        #   changes game state, which installing does not. Diff the .text sha256 against 'cheatmgr'.
        'cheatmgr-verify' = @('-DKRUNMODE=RM_CHEATMGR','-DKCMVERIFY=1')
        #   The MENU-route verify build: wide swap (menu never dispatches ReceiveTickClient) + execute
        #   KCMVERIFYCMD. Default verb is LogLoc, whose UCheatManager body reaches
        #   BugItStringCreator -> UE_LOG(LogCheatManager, Log, "BugItGo %f ...") -- so success is the
        #   literal "BugItGo" appearing in Loki.log. All three literals were confirmed present in the
        #   shipped image before this variant was flown (wide=1 each, against 3 present controls).
        #   ⚠ NOT "God": measured to emit no log line at all, i.e. a silent instrument.
        'cheatmgr-any-verify' = @('-DKRUNMODE=RM_CHEATMGR','-DKFSNAME=\"\"','-DKCMVERIFY=1')
        # ★★★★★ S124 RM_PHASELADDER (24) -- FK-22 arms A0'..A5 on the round-phase ladder.
        #   docs/fk22-dropphase-reachability.md §8-§12. A NEW enum value: RM_GOTOPHASE (2) is untouched
        #   because it arms with InstallHook() (a standing ProcessInternal .text patch, S112-measured
        #   10/10 lethal) and several docs reference its behaviour by name.
        #   Arming is the heap UFunction.Func (+0xE0) swap, inherited from RM_PLAY -- ZERO module-image
        #   writes; with KFUNCSWAP=0 the mode REFUSES to run rather than falling back to the .text hook.
        #   Effects: two GoToPhase calls, one BP_AuthSetCurrentPhase call, and ONE BYTE of heap data
        #   (GameState+0xA44), poked to 3 and back to 4, readback-verified both ways.
        #   ⚠ Inject into the STAGED TUTORIAL WORLD (gft -> fo -> sp -> this). The default KFSNAME is
        #     ReceiveTickClient, which is MEASURED not dispatched at the menu; the mode aborts by name
        #     at the menu anyway (no live GameMode_Tutorial).
        'phaseladder'          = @('-DKRUNMODE=RM_PHASELADDER')                            # ★ CANDIDATE: the full A0'..A5 ladder
        #   +1 dim: swap every BP UFunction instead of just ReceiveTickClient. Use if the shim's own
        #   8 s verdict line reads "NO GAME-THREAD HITS ... THE SWAP IS A SILENT NO-OP".
        'phaseladder-any'      = @('-DKRUNMODE=RM_PHASELADDER','-DKFSNAME=\"\"')
        #   -1 dim: A0' ONLY. Pure RPM -- zero UFunction calls, zero writes of any kind. This is the
        #   safety build and the staging positive control: if it does not print a live GameState and a
        #   plausible baseline, the sitting is wrong and no other arm is worth spending.
        'phaseladder-readonly' = @('-DKRUNMODE=RM_PHASELADDER','-DKPLARMS=0x01')
        #   -1 dim: A0'..A3 (both GoToPhase calls + the readback) but NO A4 poke and NO A5 broadcast,
        #   i.e. the call-only half with no data write at all. Run this first if the poke is unwanted.
        'phaseladder-nopoke'   = @('-DKRUNMODE=RM_PHASELADDER','-DKPLARMS=0x0F')
        #   ★ S124 SECOND FLIGHT: A0' + A5 ONLY (0x01|0x20). A1/A2 are already PROVEN live (the round
        #   self-drove to EGP_Combat, docs/fk22 §14) so re-running them only burns the window and
        #   contaminates receipts; A3/A4 are dropped to keep this SINGLE-VARIABLE -- the one question
        #   is whether a BROADCAST alone drives the DropPlane handler, whose gate reads the ARGUMENT
        #   (`NotEqual_ByteByte(NewPhase,6)`), not the stored byte. KFSNAME="" because the first
        #   flight's ladder STARVED after A2 when ReceiveTickClient stopped being dispatched.
        'phaseladder-a5'       = @('-DKRUNMODE=RM_PHASELADDER','-DKFSNAME=\"\"','-DKPLARMS=0x21')
        # ══════════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S125 RM_DROPPLANE (enum 25) — FK-22 arms B0..B4 ON THE DROPPLANE COMPONENT.
        #   Same safety shape as phaseladder: heap UFunction.Func swap only, ZERO module-image writes,
        #   and with KFUNCSWAP=0 the mode REFUSES to run rather than falling back to InstallHook().
        #   This one pokes NOTHING at all -- its only effects are UFunction calls.
        #   ⚠ KFSNAME="" on EVERY variant: S124's first flight STARVED after two arms when
        #     ReceiveTickClient stopped being dispatched; KFSNAME="" gave 508 game-thread hits.
        #   ⚠ KFAULTINFO=1 on EVERY variant, INCLUDING the reproduction arm -- the A/B is void unless
        #     both arms report faults identically. That is the whole reason S93's `FAULTED` could not
        #     be interpreted.
        #   ⚠ It SPAWNS A REAL ACTOR into a live world and does not undo it. Recovery = restart the client.
        #
        #   DEFAULT = KFRAMEINIT=1 (ZEROONLY), NOT the flown KFRAMEINIT=2. Deliberate: level 1 writes
        #   zeroes ONLY and strictly inside the [M]-bracketed 0x48..0x80 window, while level 2 also
        #   writes FF_CURNATIVEFN=0x90, which the source itself flags as "the weakest offset here"
        #   (it is PAST the last verified field). In an arm where A FAULT IS THE THING UNDER TEST, the
        #   default must make the fewest unverified assumptions, so a fault is attributable to
        #   SpawnPlane and not to our frame preparation. 'dropplane-s80frame' is one flag away.
        'dropplane'           = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1')
        #   -1 dim: B0 + B4 ONLY (0x01|0x10). ZERO UFunction calls, zero writes, nothing spawned.
        #   This is the staging positive control AND the census's own null-delta control: if it reports
        #   a non-zero delta the instrument is noisy and no other variant's delta means anything.
        #   FLY THIS FIRST.
        'dropplane-readonly'  = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKDPARMS=0x11')
        #   ★ THE S93 REPRODUCTION / CONFOUND A/B (this is the '-oldframe' arm; ONE name, ONE artifact,
        #     because two names for one binary is how an A/B gets run against a copy of itself).
        #     B0 + B0c(control) + B1 + B4 = 0x01|0x20|0x02|0x10 = 0x33, on the UNFIXED primitive --
        #     everything else held constant.
        #     If B1 faults here and NOT in 'dropplane-b1only', S93's FAULTED was the FFrame confound:
        #     [I] -> [M]. ⚠ THE CONTROL BIT 0x20 IS MANDATORY IN BOTH ARMS. B0c is GetAutoDropLocation,
        #     0 push / 0 pop, so it cannot be affected by the flow-stack window; if it faults in either
        #     arm, THAT arm is void and B1 says nothing.
        'dropplane-s93frame'  = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=0','-DKFAULTINFO=1','-DKDPARMS=0x33')
        #   ★ THE MATCHED FIXED ARM FOR THE ABOVE. Identical KDPARMS (0x33), identical everything, with
        #     KFRAMEINIT=1 as the ONLY variable. Use THIS against 'dropplane-s93frame', not the plain
        #     'dropplane' build -- 'dropplane' is 0x3F (it also runs B3a/B3b), so a bottom-line delta
        #     table from it is a 4-call run being compared with a 2-call run. Only B0c/B1 status and the
        #     after-B1 mini-census are comparable across those two; here EVERYTHING is.
        'dropplane-b1only'    = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKDPARMS=0x33')
        #   -1 dim: B0 + B3a + B3b + B4 (0x01|0x04|0x08|0x10). The handler question with NOTHING spawned,
        #   so its census delta is attributable to the handler alone. In the default build B3 runs AFTER
        #   B1 and is therefore confounded by it -- THIS is the arm that answers "subscribed but inert?".
        'dropplane-handler'   = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKDPARMS=0x3D')
        #   +1 dim on the frame fix: the ds_hybrid.cpp:2151 recipe (FlowStack empty + Max=8,
        #   PreviousFrame=0, CurrentNativeFunction=0) -- the only form of this fix that has ever run in
        #   this game. Use it if 'dropplane' faults, to separate "SpawnPlane really faults" from
        #   "zeroing alone was not enough frame preparation".
        'dropplane-s80frame'  = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=2','-DKFAULTINFO=1','-DKDPARMS=0x33')
        # ══════════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S126 RM_DROPPOD (enum 26) — ROUTE C: SpawnDropPodForTeam on the live LokiDropShip.
        #   Same safety shape as dropplane/phaseladder: heap UFunction.Func swap ONLY, ZERO
        #   module-image writes, ZERO memory pokes, and with KFUNCSWAP=0 the mode REFUSES to run rather
        #   than falling back to InstallHook(). Its only effects are UFunction calls.
        #   ⚠ KFSNAME="" on EVERY variant: S124's first flight STARVED after two arms when
        #     ReceiveTickClient stopped being dispatched; KFSNAME="" gave 508 game-thread hits.
        #   ⚠ KFRAMEINIT=1 + KFAULTINFO=1 on EVERY variant, matching the S125 arm that produced the
        #     measurement this route is built on. A fault must be attributable or it is S93 again.
        #   ⚠ It SPAWNS REAL ACTORS into a live world and does not undo it. Recovery = restart the client.
        #
        #   WHY THIS ROUTE: SpawnDropPodForTeam takes its positions AS PARAMETERS, queries NO markers
        #   (FK-22 §3, [M]: exactly two bail points) and needs NO round phase. S125's B1 left a live
        #   BP_DropPlane_Straight_Tutorial_C -- chain ... <- LokiDropShip -- so the receiver exists.
        #   The measured marker failure (PlaneStartPoint=0 PlaneEndPoint=0 over 2,881 actors) is
        #   IRRELEVANT here.
        #
        #   -1 dim: C0 + C4 ONLY (0x01|0x10). ZERO UFunction calls, zero writes, nothing spawned. The
        #   staging positive control AND the census's own null-delta control. FLY THIS FIRST -- if it
        #   reports a non-zero DropPod delta the instrument is noisy and no other variant means anything.
        #   ★★ S126 FINALIZER: KPDARMS bit6 = the GetTeamDropLeader probe, which is a REAL UFunction
        #      call and used to run UNGATED. This arm (0x11) now genuinely makes zero calls, which is
        #      what build.ps1 and the shim's own marker both already claimed.
        #   ★★ AND EVERY droppod VARIANT NOW CARRIES -DKOUTPARMRET=1. C3's pre-spawn calls SpawnPlane
        #      through the BP path, and BuildOutParms excluding CPF_ReturnParm is the MEASURED cause of
        #      S125's 0xC0000005 at rva 0x13495DD. Without it the default candidate deliberately
        #      reproduces a game-thread AV and then runs C0c and C1 on that same thread. For the three
        #      NATIVE callees in this mode (SpawnDropPodForTeam, K2_GetActorLocation, GetTeamDropLeader)
        #      the extra FOutParmRec is inert -- an exec thunk reads its return through RESULT_DECL and
        #      never walks OutParms -- so this is a fix for C3 and a no-op for C0c/C1/C2b.
        'droppod-readonly'    = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0x11','-DKPDPRESPAWN=0')
        #   ★ THE CANDIDATE. Full ladder 0x7F = C0 + C1 + C2(mini-census) + C3(pre-spawn if needed) + C4 +
        #   C0c(control) + C2b(GetTeamDropLeader probe).
        #   + C4. C3 only fires when NO live ship exists, and it moves the DropPlane/DropShip rows, never
        #   the DropPod row that answers Route C.
        'droppod'             = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')
        #   -1 dim: NEVER pre-spawn. If no LokiDropShip actor is live the mode reports Route C
        #   NOT-APPLICABLE and makes no calls at all. Use this when the sitting must contain exactly one
        #   variable, or when S125's half-constructed plane is known to still be resident.
        'droppod-noprespawn'  = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0x77','-DKPDPRESPAWN=0')
        #   +1 dim: disambiguation arm. If 'droppod' printed ">1 live LokiDropShip actors ... REFUSING",
        #   this takes the HIGHEST InternalIndex (the most recently created) by a STATED rule. Prefer
        #   -DKPDSHIPCLASS="<exact class FName>" when the enumeration names the one you want.
        'droppod-newest'      = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDSHIPPICK=1')
        # ═══════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S126 ROUTE E -- DISPATCH SpawnDropPodForTeam THROUGH ProcessEvent (KPDARMS bits 7-8).
        #   WHY: Route C resolved everything and then could not call -- the live UFunction's
        #   `Func` (+0xE0) READ BACK 0x0 while K2_GetActorLocation on the SAME object read a real thunk
        #   and dispatched. FK-1 §4 names the successor (`_ParmsEntry` implements ProcessEvent's flat-params
        #   contract; the script corpus itself dispatches script UFUNCTIONs via FindFunctionChecked +
        #   ProcessEvent) and FK-1's own "callable by the S55 recipe unchanged" carries the parenthetical
        #   "(mechanism named; the `Func` value itself is INFERRED)" -- i.e. FK-1 flagged the exact thing
        #   S126 measured false. These arms are that successor, not a correction of FK-1.
        #
        #   ⚠⚠ ProcessEvent is NOT automatically a Func-free route, and the shim GRADES the live
        #   UFunction before calling. Offline, from dumps/merged2.dump.exe, all [M]:
        #     * ProcessEvent's normal path ends at UFunction::Invoke (rva 0x1225F30) whose last act is
        #       `call qword ptr [r14+0xE0]` with NO null test -> a null Func is `call [0]`.
        #     * but at rva 0x1344EB4 ProcessEvent tests FunctionFlags bit 0x10 and, when set, dispatches
        #       `call [UFunctionVtable+0x378](Fn,Obj,Parms)` and never reads Func. Bit 0x10 is UNUSED in
        #       stock EFunctionFlags. [I, strong] that is this build's AOT-script entry.
        #     * third exit: Func==0, bit 0x10 clear, (flags&0x410)==0 and Script.Num==0 -> the reject gate
        #       returns at once. Safe, and a GUARANTEED no-op.
        #   The shim prints which of the four it sees and REFUSES the WILL-FAULT combination by default.
        #   A refusal is a RESULT (the offline grade confirmed on the live object), not a failure.
        #
        #   ⚠ The vtable displacement is 0x270 (SLOT 78), resolved from the SHIP's OWN vtable at runtime;
        #   nothing is hardcoded. docs/next-session-prompt-s80.md's "base+0x12C5A10, vtable slot 56" is
        #   disp 0x1C0 and is not ProcessEvent -- the shim prints that slot's occupant beside the real one
        #   and never calls it. Override with -DKPDPEDISP=0x<disp> if a future build moves it.
        #
        #   ⚠ Same safety shape as every other droppod arm: heap UFunction.Func swap ONLY (KFSNAME=""),
        #   ZERO module-image writes, ZERO memory pokes, and KFUNCSWAP=0 makes the mode REFUSE rather than
        #   fall back to InstallHook(). Verify with verify_dll.py: FlushInstructionCache / VirtualAlloc /
        #   VirtualFree must be ABSENT from the import table (positive control: tutorial_launch_fo.dll has
        #   all three PRESENT).
        #
        #   -1 dim: THE STAGING CHECK AND THE ROUTE'S OWN POSITIVE CONTROL. 0xB9 = C0 census + C3
        #   pre-spawn-if-needed + C0c + E0 + C4. It makes NO script call at all: it answers only
        #   "can ProcessEvent dispatch a known-good NATIVE UFunction in this build, on this object, with
        #   the return marshalled into the params block". FLY THIS FIRST -- if E0 cannot reach STRONG
        #   PASS, a null from E1 is uninterpretable and the sitting is void for Route E.
        #   ★★ It REQUIRES A NON-ZERO REFERENCE. S126's C0c "AGREED" at (0,0,0) because the ship was
        #      S125's half-constructed plane; two zeros agree perfectly and prove nothing. E0 prints
        #      `WEAK CONTROL (origin)` in that case and re-runs the same route on the hero / TrainingStart
        #      marker so the ROUTE still gets a real positive.
        'droppod-pe-ctrl'     = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0xB9')
        #   ★ THE CANDIDATE. 0x1FF = the full C ladder (C0/C1/C2/C2b/C3/C4/C0c) PLUS E0 + E1. C1 is kept
        #   deliberately: with Func==0 it prints "has no Func thunk -> NOT CALLED" in the same run, which
        #   is the two routes' shared control and pins the premise on THIS process rather than on a
        #   remembered measurement from PID 138796.
        'droppod-pe'          = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0x1FF')
        # ★★★★★ S130 — C7: THE bCanEverReplicate CDO GATE. The pooled acquire refuses any class
        #   whose CDO can replicate (`cmp byte [CDO+0x6C],0 ; jne -> NULL` at .text 0x0564820C), and
        #   BP_DropPod_C's CDO reads 1 -- MEASURED live, 8/8 predictions, cooked->runtime mapping 30/30.
        #   That is why SpawnDropPodForTeam returns false: LokiDropShip.as:153 wraps its whole body in
        #   `if (spawn != null)` with NO else.  These two arms differ in ONE BYTE and nothing else.
        #   ⚠ Both arms READ and PRINT the flags at step 3 and again before E1 -- so the CONTROL arm
        #     is NOT "do nothing": it closes S130's last inference by reading
        #     Default__BP_DropPod_Tutorial_C in a STAGED world, where (unlike the menu) it is loaded.
        #   ⚠ The poke mutates a CLASS DEFAULT for the process lifetime and may break the pod's
        #     replication. It is a HEAP byte: no VirtualProtect, no SafeWrite, no module image touched.
        'droppod-pe-cdoctrl'  = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0x1FF','-DKPDCDOPOKE=0')
        'droppod-pe-cdopoke'  = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0x1FF','-DKPDCDOPOKE=1')
        #   +1 dim, DELIBERATE ESCALATION. Calls through ProcessEvent even when the live grade says
        #   WILL-FAULT (`call [0]` inside UFunction::Invoke). Use ONLY after 'droppod-pe' has printed the
        #   WILL-FAULT refusal, and only if the AV itself is wanted as evidence: the fault address should
        #   read 0x0 with rip inside rva 0x1225F30. It spends the game thread.
        'droppod-pe-force'    = @('-DKRUNMODE=RM_DROPPOD','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDARMS=0x1FF','-DKPDPEFORCE=1')
        # ══════════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S126 RM_DROPMARKERS (enum 27) — ROUTE D: MAKE THE TWO PLANE MARKERS RESIDENT, THEN
        #   CALL SpawnPlane BEHIND A RESIDENCY GATE. Same safety shape as dropplane/droppod: heap
        #   UFunction.Func swap only, and with KFUNCSWAP=0 the mode REFUSES rather than falling back to
        #   InstallHook(). The ONLY memory written is TWO 4-byte FName ids inside an already-allocated,
        #   engine-owned `AActor.Tags` buffer -- readback-verified and RESTORED on every exit path
        #   including the SEH fault path. No allocation, no Num/Max change, no module image.
        #
        #   ⚠⚠ READ THIS BEFORE PICKING A VARIANT. S125's `SpawnPlane FAULTED` was NOT the missing
        #   markers. The fault is `execLocalOutVariable` at rva 0x13495DD dereferencing a NULL
        #   `FFrame.OutParms`, because `BuildOutParms` excluded CPF_ReturnParm and `SpawnPlane`'s ONLY
        #   CPF_Parm is its `ReturnValue`. `UObject::ProcessEvent` DOES include the return param
        #   (its loop tests `(flags & CPF_Parm) == CPF_Parm`), and the same S125 run SPAWNED A REAL
        #   PLANE before dying -- i.e. execution had already passed all three GetAllActorsWithTag +
        #   Array_Get(...,0) sites. => the empty marker arrays produced (0,0,0) COORDINATES, not a
        #   crash. KOUTPARMRET=1 is the fix and it is a `#if`, defaulting to 0, so every existing
        #   artifact's `.text` is unchanged.
        #
        #   FLY IN THIS ORDER. Each step turns ONE variable.
        #   1) 'dropmarkers-readonly'  -- ZERO WRITES and no SpawnPlane. (It is NOT call-free: GATE-2
        #      calls UGameplayStatics::GetAllActorsWithTag, which is a read-only query but IS a call --
        #      say what it does, not what sounds cleaner.) Proves staging, proves the two FName
        #      instruments agree, proves the negative control fails to resolve, and reports the live
        #      GetAllActorsWithTag counts for all three tags. If this does not print AGREE for both
        #      markers, STOP -- everything downstream writes a guessed FName otherwise.
        'dropmarkers-readonly' = @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXARMS=0x23')
        #   2) 'dropmarkers-gateonly'  -- write the two tags, run BOTH gates, RESTORE, and never call
        #      SpawnPlane. This is the arm that measures the MECHANISM on its own: a 0 -> 1 transition
        #      on GetAllActorsWithTag for both markers, with TrainingStart pinned as the in-run control.
        #      It leaves the world exactly as it found it.
        'dropmarkers-gateonly' = @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXARMS=0x27')
        #   3) 'dropmarkers-outparm'  ⚠⚠ THIS ARM SETS KDMFORCE=1 AND THEREFORE CALLS SpawnPlane WITH
        #      THE RESIDENCY GATE FAILED. That is deliberate and it is the point of the arm, but the
        #      variant NAME does not say so -- read this line before flying it.
        #      -- THE SINGLE-VARIABLE FAULT FIX, WITH NO MARKER WRITE AT ALL
        #      (KDXARMS clears bit2, so the gate FAILS by construction and D4 is skipped)... which is
        #      useless on its own, so this arm sets KDMFORCE=1 deliberately: call SpawnPlane with the
        #      markers still ABSENT and only KOUTPARMRET changed from the S125 flight. PREDICTION: no
        #      fault, a non-null plane, and its location (0,0,0). That prediction is what separates
        #      "the OutParms defect was the crash" from "the markers were the crash".
        'dropmarkers-outparm'  = @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXARMS=0x3B','-DKDMFORCE=1')
        #   4) 'dropmarkers'          -- THE HEADLINE ARM. Markers resident + OutParms fixed + the gate
        #      enforced. PREDICTION: no fault, a non-null BP_DropPlane_Straight_Tutorial_C, and a plane
        #      location that matches victim[0] rather than (0,0,0).
        'dropmarkers'          = @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')
        #   5) 'dropmarkers-s125repro' -- THE CONTROLLED REPRODUCTION. Identical to (4) except
        #      KOUTPARMRET=0. PREDICTION: faults at rva 0x13495DD, addr=0x0, AFTER spawning a plane --
        #      i.e. the markers being resident does NOT prevent the fault, which is the claim.
        #      ⚠ Fly this ONLY after (4); it spawns a second plane into the same world.
        'dropmarkers-s125repro'= @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=0')
        #   +1 dim: keep the tags written (no restore). Only for chaining another probe that needs the
        #   markers resident; it CONTAMINATES anything that reads Tags afterwards, so it is not a default.
        'dropmarkers-norestore'= @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDMRESTORE=0')
        #   -1 dim: drop GATE-2 (the GetAllActorsWithTag probe) and gate on the READBACK alone. Use only
        #   if GATE-2 itself faults; the gate is materially weaker and the mode says so in the marker.
        'dropmarkers-nogat'    = @('-DKRUNMODE=RM_DROPMARKERS','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDMGAT=0')
        # ══════════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S128 RM_POOLSPAWN (enum 28) — ROUTE F: DOES `SpawnPoolableActorFromClassDeferred`
        #   ACTUALLY REQUIRE THE ACTOR POOL?
        #
        #   WHY: S127 measured that `SpawnDropPodForTeam` RAN (the 0xA5 return sentinel was overwritten,
        #   readSlots=3, offsets agreed with the FProperty chain) and RETURNED **false**, DropPod delta
        #   +0. Bail 1 (`TeamDropPodClass == nullptr`) is [M] EXCLUDED -- the field re-read AFTER the call
        #   still held BP_DropPod_Tutorial_C -- so by elimination it is bail 2, the null from
        #   `LokiGameplay::SpawnPoolableActorFromClassDeferred`. The session log names a suspect
        #   (`UActorPoolManager::PrimePools : Feature is not enabled, skipping.`) but **that chain is [I]
        #   AND UNPROVEN AT ITS FIRST LINK**: nobody has shown the helper NEEDS the pool. A sane helper
        #   falls back to a normal SpawnActor when pooling is off, in which case the disabled pool is a
        #   red herring. These arms settle that one link and nothing else.
        #
        #   ⚠ THE TARGET IS A NATIVE STATIC on `ULokiGameplayStatics` (a UBlueprintFunctionLibrary), so
        #   its "object" is the CLASS DEFAULT OBJECT and it should carry a non-null `Func` -- unlike
        #   S127's Angelscript UFunction, whose Func read 0x0 and closed Route C. The shim GRADES the
        #   live UFunction (native thunk / ProcessInternal / universal fold / null) and dispatches on what
        #   it READ, printing which and why. It never assumes.
        #   ⚠⚠ THE TWO METHODS DECLARE Owner/Instigator IN DIFFERENT POSITIONS, so every slot is bound
        #   BY NAME from the live FProperty chain, PER FUNCTION, with NO positional fallback.
        #   ⚠ The FTransform slot is zeroed and written AT THE SIZE THE FProperty DECLARES -- never a
        #   hardcoded 0x50 (the S93/S106d truncation that clipped Scale3D.Z on every actor this project
        #   ever spawned).
        #   ★ Both the params ReturnValue slot and RESULT_DECL are pre-filled with 0xA5, so "nothing
        #   wrote a return" is distinguishable from "wrote null" -- the distinction that carried S127.
        #
        #   Same safety shape as every dropplane/droppod arm: heap `UFunction.Func` swap ONLY
        #   (KFSNAME=""), ZERO module-image writes, ZERO memory pokes, and with KFUNCSWAP=0 the mode
        #   REFUSES rather than falling back to InstallHook(). Verify with verify_dll.py:
        #   FlushInstructionCache / VirtualAlloc / VirtualFree must be ABSENT from the import table
        #   (positive control: tutorial_launch_fo.dll has all three PRESENT).
        #
        #   -1 dim: ZERO UFunction calls. P0 resolve + BEFORE census + P4 AFTER census, nothing else.
        #   The staging positive control AND the census's own null-delta control. FLY THIS FIRST -- if it
        #   reports a non-zero DropPod delta the instrument is noisy and no other variant means anything.
        'poolspawn-readonly'  = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPARMS=0x81')
        #   -1 dim: adds ONLY the P0c primitive control (K2_GetActorLocation cross-checked against RPM).
        #   It answers "can this shim dispatch a known-good native UFunction on this thread, on a
        #   NON-ORIGIN actor, and marshal a struct return" and NOTHING about the pool. Fly it if a
        #   previous sitting's P0c did not reach STRONG PASS.
        'poolspawn-ctrl'      = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPARMS=0x181')
        #   ★ THE HEADLINE, ALONE. P0 + P0c + P1(Deferred) + after-P1 census + P4. No sibling, no
        #   reference spawn -- so the DropPod delta, if any, belongs to the deferred pooled spawn and to
        #   nothing else. Use when the sitting must contain exactly one payload call.
        'poolspawn-deferred'  = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPARMS=0x187')
        #   +1 dim: the NON-deferred sibling alone (P2). Its whole job is to localise a P1 null to the
        #   DEFERRED path; flown separately when P1 and P2 must not share a sitting.
        'poolspawn-nondef'    = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPARMS=0x199')
        #   +1 dim: the NON-POOLED REFERENCE alone (P3). Establishes that BP_DropPod_Tutorial_C is
        #   spawnable in this world at all. ⚠ WITHOUT THIS ESTABLISHED, a null from P1 could just mean
        #   "this class cannot spawn here" and the pool would be exonerated -- or blamed -- wrongly.
        'poolspawn-ref'       = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPARMS=0x1E1')
        #   ★ THE CANDIDATE. The full pre-registered ladder 0x1FF = P0 + P0c + P1 + P2 + P3 + all three
        #   mini-censuses + P4. P3 runs LAST so it cannot contaminate P1/P2's deltas, and each stage has
        #   its own census column so the three are separable in one sitting.
        'poolspawn'           = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')
        # ★★★★★ S130 — THE C7 TEST, AND IT IS THE CHEAPEST ONE AVAILABLE.
        #   S128 flew `poolspawn` and measured P1 and P2 both returning NULL on BP_DropPod_Tutorial_C
        #   while the ordinary path (P3) spawned the same class fine.  S130 then MEASURED why: the
        #   acquire does `cmp byte [CDO+0x6C],0 ; jne -> return NULL` and +0x6C is
        #   AActor::bCanEverReplicate, which reads 1 on the whole drop-pod chain.
        #   These two arms are the SAME probe as S128 with ONE BYTE different.
        #   ⚠ Prefer this over the droppod Route-E arms for testing C7: it calls the pooled spawn
        #     DIRECTLY, so it needs no live LokiDropShip, no pre-spawned plane and no ProcessEvent
        #     marshalling -- three preconditions that are irrelevant to the question being asked.
        #   ⚠ `poolspawn-cdoctrl` is byte-for-byte the S128 experiment plus a read-only CDO print, so
        #     it is a genuine reproduction arm, not just a control.
        # ★★★★★ S131 RM_RIDEABLE (enum 29) -- THE FIFTH WALL, CALLED DIRECTLY.
        #   S131's Route-E flight handed AuthPlayerEnterWorldAttachedToRidable a NULL PlayerState, so
        #   impl 0x55CD510 returned at instruction #1 (`test rdx,rdx; je`) and its SILENCE said nothing
        #   about the wall. The obvious fix -- poke [TeamState+0x688] so GetTeamDropLeader returns
        #   non-null -- is BLOCKED at its precondition: MEASURED zero live TeamState actors in the
        #   staged tutorial world. So this mode resolves BOTH arguments live, BY NAME, and calls the
        #   wall directly: the pod's own `LokiRideable` component and the live BP_LokiPlayerState_C.
        #   ⇒ the Loki.log line `... failed to get the round game mode` becomes INTERPRETABLE for the
        #   first time. Present => the fifth wall is CONFIRMED [M]. Absent => it bailed EARLIER, which
        #   is a statement about our PlayerState and NOT about the wall -- and the arm reads those
        #   preconditions out itself so the two are separable.
        #   Requires a staged world that ALREADY contains an INITIALISED pod (PodTeamIndex == 0):
        #     gft -> fo -> sp -> dropplane_b1only -> droppod-pe-cdopoke -> THIS.
        #   Heap-only: two direct UFunction.Func calls + guarded reads. NO .text write, NO poke.
        'rideable'            = @('-DKRUNMODE=RM_RIDEABLE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')
        # Control arm: resolve + the R0c ContainsPlayer control + the precondition readout, and then
        # DO NOT call the wall. Its ContainsPlayer value is the before-reading the real arm needs, and
        # a non-zero effect from THIS build would mean the readout itself is not read-only.
        'rideable-readonly'   = @('-DKRUNMODE=RM_RIDEABLE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKRDARMS=0x0D')
        # ★★★★★ S132 RM_DISMOUNT -- GET THE HERO OUT OF THE POD.
        #   Appends the PlayerState to the rideable component's PlayersAttached with the GAME'S OWN
        #   ResizeGrow (0x00F988D0 -- the exact function the wall's own tail calls at 0x55CD75B), then
        #   calls AuthPlayerDetachPlayerFromRidable (impl 0x55CCCB0, thunk 0x5456100) through the S55
        #   direct UFunction.Func thunk. Risk class DATA: two aligned TArray-header writes plus one
        #   element store inside the game's own allocation. NO .text write, NO PI hook, NO CDO poke.
        #   Same staging as `rideable`: gft -> fo -> sp -> dropplane_b1only -> droppod-pe-cdopoke -> this.
        #   KDXARMS bits: 0 D0c ContainsPlayer dispatch control | 1 D1 pre-append NEGATIVE control |
        #                 2 D2 the append | 3 D3 the detach | 4 D4 second cycle | 5 D5 restore on bail
        'dismount'            = @('-DKRUNMODE=RM_DISMOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')
        # ★★★★★ S135 RM_BOTSPAWN -- bots on the TUTORIAL route. CALL-ONLY: no module-image write,
        #   no data poke, no PI hook; REFUSES under KFUNCSWAP=0. Staging: gft -> fo -> sp -> this
        #   (NO pod, NO plane -- this is not the drop chain).
        #   [M] Comp_BP_BotSpawner_C rides on BP_LokiGameMode_Tutorial and has ZERO
        #   ServerOnly/HasAuthority/SpawnPlayer occurrences (control: 8 in the gamemode's ubergraph),
        #   so it is free of BOTH the FK-42 exec-pin gates and FK-1's stripped SpawnPlayer.
        #   ⚠ THE VERDICT IS THE GUObjectArray CENSUS DELTA, never the CreatedBot out-param (that
        #     comes from a team scan a SUCCESSFUL spawn can also fail).
        #   Knobs: -DKBSTEAM (default -1 = opposite the player) -DKBSHERO -DKBSDIFF -DKBSLEVEL
        #          -DKBSOFFSET -DKBSARMS -DKBSFUNC -DKBSNUM -DKBSAI
        'botspawn'            = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')

        #   READ-ONLY CONTROL: every guard + both censuses, CALL bit cleared. Its census delta MUST
        #   be zero; it converts a null in the real arm from 'something is broken' into 'the call
        #   specifically did nothing'.
        'botspawn-readonly'   = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSARMS=0x0B')

        #   SpawnBotTeamAtLoc -- a WHOLE ENEMY TEAM in one call. The hero-class guard is SKIPPED
        #   (not failed): this entry point has no HeroClassToSpawn and picks from the roster itself
        #   via GetSpawnableBots -> Array_NRandom (measured live: Num=13 Max=16).
        #   FLOWN S135: +3 heroes of 3 GAME-CHOSEN classes, CreatedBotTeam.Num=3.
        'botteam'             = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSFUNC=\"SpawnBotTeamAtLoc\"','-DKBSNUM=3')

        # ★★★★★ S135c THE CONTROLLER ROUTE (BUILT, UNFLOWN). The component route spawns PAWNS but
        #   never a CONTROLLER: MakeNewBotController 0x5563660 bails on a stripped F(UWorld*)->nullptr
        #   at 0x55636BB, so the REAL AController::Possess 0x36E2B60 is skipped at 0x556DD37.
        #   This arm uses a DIFFERENT, INTACT entry point instead of trying to satisfy the stub:
        #   UAIBlueprintHelperLibrary::SpawnAIFromClass 0x4631C50 -- REAL, 2133 B, 0 fold calls,
        #   native + STATIC => S55 direct thunk with context = the CDO.
        #   ★ READ ONE NUMBER: the BotController/AIController census delta (P1).
        #   ★ And take a dumpimage EITHER WAY: P4 = APawn::SpawnDefaultController 0x3BBF3C0 going
        #     DARK -> DECRYPTED is a free permanent offline receipt, independent of any census.
        'botai'               = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1')
        # READ-ONLY control arm: resolve, read out all six gates, run the D0c dispatch control and the
        # D1 pre-append negative control -- and then WRITE NOTHING and call no detach on a non-empty
        # array. Any physical change from THIS build would mean the readout is not read-only.
        'dismount-readonly'   = @('-DKRUNMODE=RM_DISMOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXARMS=0x03')
        # Append but DO NOT call the detach: isolates "can we write the array at all" from "does the
        # detach then run". Use only if the full arm's append readback fails and needs localising.
        'dismount-appendonly' = @('-DKRUNMODE=RM_DISMOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXARMS=0x27')
        # Pass the POD explicitly as LandingLocationActor instead of letting the detach substitute
        # [comp+0xB8]. Use if the default lands the hero somewhere uninterpretable.
        'dismount-podland'    = @('-DKRUNMODE=RM_DISMOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXLANDING=1')
        # THE DISCRIMINATING ARM: pass a LokiPlayerStart actor as LandingLocationActor instead of the
        # pod. S132's first two flights landed the hero at the FLYING pod's live X/Y (Y bit-identical to
        # the pod's over 17 significant figures) at Z=250 -- over open air, so it fell. This arm asks
        # whether GetLandingTeleportLocation actually CONSUMES that argument. Lands-at-PlayerStart =>
        # yes, and the dismount can put the hero on real ground. Lands-at-pod => the argument is ignored
        # and the landing point is a property of the component. The prediction is printed BEFORE the call.
        # ★★★★★ ANSWERED -- IT CONSUMES IT (S132 flights 2 and 3, artifact .text 0d5fa554edac53c5).
        #   With a LokiPlayerStart 1,488,146 uu from the pod at that instant, the hero landed AT THE
        #   PLAYERSTART -- (-3206.4, 5070.5, 138.0), settling to Z = 90.15 and holding position
        #   BIT-FOR-BIT across 9 s while the pod flew another 180,000 uu. Flight 3 reproduced it.
        #   ⇒ [M] GetLandingTeleportLocation (0x55D89F0, REAL, 963 B) consumes LandingLocationActor,
        #     and the dismount puts the hero on real ground -- un-hidden, collided, gravity-affected.
        #   ⇒ THIS IS NOW THE ARM TO FLY for any run whose point is a USABLE deploy. Plain `dismount`
        #     (KDXLANDING=0) becomes the pod-relative CONTROL, not the default of choice.
        'dismount-landstart'  = @('-DKRUNMODE=RM_DISMOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDXLANDING=2')
        # S132 -> S133: DOES THE HERO LOCOMOTE *AT THE POINT THE DISMOUNT LANDED IT*?
        #   RM_PLAY's FIRST act is a hardcoded ground-teleport to (KGROUNDX,KGROUNDY,KGROUNDZ) =
        #   (-65,-1770,393) -- S75's known-solid ground. S132 injected plain `play` onto a dismounted
        #   hero and it ran, but the teleport had already MOVED IT OFF the landing point, so that run
        #   is evidence about the hero's STATE, not about the deploy LOCATION. KNOTELE=1 already
        #   exists and skips the teleport entirely -- no new code was needed.
        #   `play` itself is UNTOUCHED: it is the hard regression gate (.text 9bc10a4552c596e1).
        #
        #   -atlanding : KNOTELE=1, everything else default. KFLYMODE stays 5 (MOVE_Flying), so the
        #                hero HOVERS and is driven by XY velocity. Isolates exactly one variable --
        #                the teleport -- against the arm whose behaviour is already established.
        #   ⚠⚠ SUPERSEDED AS THE FIRST ARM TO FLY (S132) -- IT IS DEGENERATE FOR THE QUESTION IT WAS
        #      BUILT FOR. With KFLYMODE=5 the hero hovers, so "it moved" cannot distinguish ground
        #      locomotion from flight: MEASURED, a flying-mode RM_PLAY hero moved 2,926 uu at CONSTANT
        #      Z = 13,240 -- 13 km through mid-air, which is a PASS under any movement test and says
        #      nothing about whether the landing point is standable. Only `play-atlanding-walk`
        #      (KFLYMODE=1) can answer it.
        #      ⚠ S132's one attempt at this arm ALSO died: a 0x0000DEAD protector kill (FK-32) during
        #      init, on the 7th injection into one process. That sitting is VOID for the playability
        #      question, NOT a negative result. Keep -atlanding only as the flight-mode control.
        'play-atlanding'      = @('-DKRUNMODE=RM_PLAY','-DKNOTELE=1')
        #   -atlanding-walk : KNOTELE=1 AND KFLYMODE=1 (MOVE_Walking). THIS is the one that tests
        #                real ground locomotion at the deploy point. WARNING: Walking mode has a
        #                recorded history of 'FudgeMantling toggles not ready' spam and movement
        #                crashes on cell-streaming (S75/S81), which is WHY the default is Flying.
        #                Fly -atlanding first; treat a death here as the known mode hazard, not as a
        #                statement about the landing point.
        #   ⚠ AMENDED (S132): "fly -atlanding first" no longer buys a result -- see the DEGENERATE
        #     note above; flying-mode movement is not evidence about standable ground. Fly it only if
        #     you want the flight-mode control in the same sitting. THIS arm is the one that answers
        #     the open question, and the question IS still open: whether the hero is PLAYABLE at the
        #     point the dismount landed it has never been measured. Stage it on a `dismount-landstart`
        #     hero (real ground at the PlayerStart), not on a pod-relative one over open air.
        'play-atlanding-walk' = @('-DKRUNMODE=RM_PLAY','-DKNOTELE=1','-DKFLYMODE=1')
        # ════════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S150-drop RM_DROPLANDPLAY -- THE DROP-LAND-PLAY COMBINED ARM.
        #
        # ONE injection composes what has been four sequential injections since flight 4b
        # (dropplane_b1only -> droppod-pe-cdopoke -> dismount-landstart -> play-atlanding-walk).
        # A state machine across game-thread hits dispatches to each phase's existing Do* function
        # verbatim; each phase's terminal case (formerly g_done=1) advances g_dlpPhase instead.
        # Reduces total per-flight injections from 7 to 4 (gft, fo, sp, dlp) -- FK-31 sitting-loss
        # budget goes ~54% -> ~19% on an independent binomial with historical ~27% per-window rate.
        #
        # SAME BEHAVIOUR AS THE FOUR SEPARATE ARMS -- knobs mirror them, one-for-one:
        #   * KDPARMS=0x33          matches dropplane_b1only  (DP: B0+B1+B0c+B4, KFRAMEINIT=1)
        #   * KPDARMS=0x1FF         matches droppod-pe-cdopoke (PD: full C ladder + E0 + E1)
        #     KPDCDOPOKE=1            (PD: poke CDO(BP_DropPod_C)+0x6C=0, S130 C7 bypass)
        #   * KDXLANDING=2          matches dismount-landstart (DX: pass LokiPlayerStart, S132 §14)
        #   * KNOTELE=1 KFLYMODE=1  matches play-atlanding-walk (PL: skip teleport, Walking mode)
        # (Shared KFSNAME="" / KFRAMEINIT=1 / KFAULTINFO=1 / KOUTPARMRET=1 are already common to
        #  every one of the four.)
        #
        # ⚠ REGRESSION GATES (verified byte-identical after this edit -- check with
        #   text_digest.py --dupes and by diffing each recorded sha256):
        #     botai 5e47c13cf7f0a158 · play 9bc10a4552c596e1 · dropplane_b1only dcb19157cf45f9aa ·
        #     droppod-pe-cdopoke 283c1692a2135680 · dismount 0fe6d7ae1f26e16b ·
        #     dismount-landstart 62f257c191027ee3 · mount-ride 9b7f88af3210c438 ·
        #     mount-descend c26e8831f45d7548 · mount-phaseb d69642beacc5e7a8
        #   All KISDLP-guarded additions are `#if KISDLP ... #endif`, and every non-DLP variant
        #   is compiled with the default KISDLP=0 (KISDLP is undefined at their build line and
        #   the source's `#ifndef KISDLP #define KISDLP 0 #endif` sets it), so the preprocessor
        #   strips every DLP addition and the compiler sees the pre-edit source. Verify at build.
        #
        # ⚠ DIAGNOSTIC arm; NOT SHIPPING. Do NOT add to the default injection set (leave
        #   launch-redirect.ps1 alone). Same staging as the four separate arms:
        #     gft -> fo -> sp -> this
        # See docs/next-session-prompt-s150-drop-dlp.md and docs/drop-sequence-status-s150.md §6.16.
        # ════════════════════════════════════════════════════════════════════════════════════════
        'droplandplay'        = @('-DKRUNMODE=RM_DROPLANDPLAY','-DKISDLP=1','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKDPARMS=0x33','-DKPDARMS=0x1FF','-DKPDCDOPOKE=1','-DKDXLANDING=2','-DKNOTELE=1','-DKFLYMODE=1')

        'poolspawn-cdoctrl'   = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDCDOPOKE=0')
        'poolspawn-cdopoke'   = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKPDCDOPOKE=1')
        #   +1 dim, THE CONFOUND-REMOVAL ARM. `SpawnActorCls` (P3) hardcodes CollisionHandlingOverride=2
        #   (AdjustIfPossibleButAlwaysSpawn) and is shared code compiled into `play`, so it is NOT edited;
        #   P1/P2 pass the functions' declared default 0 (Undefined). If the full ladder shows P1/P2 null
        #   and P3 spawning, RE-FLY THIS BEFORE BLAMING THE POOL -- it makes P1/P2 pass 2 as well, so
        #   collision handling stops being a difference between the arms.
        'poolspawn-collmatch' = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPCOLLISION=2')
        #   +1 dim: WorldContextObject = the DropPlane COMPONENT instead of the GameMode. Only useful if
        #   the GameMode enumeration comes back ambiguous or the component is the only live candidate.
        #   ⚠⚠ ON THIS VARIANT P3's WorldContextObject DIFFERS FROM P1/P2's BY CONSTRUCTION: `SpawnActorCls`
        #   always passes its own `g_gm2` (a GameMode) and cannot be edited (shared code compiled into
        #   `play`). The shim MEASURES and PRINTS the comparison, and every verdict that leans on P3
        #   carries a QUALIFIED marker here -- so a P1-null/P3-spawns reading off THIS variant is a
        #   two-variable comparison, not a one-variable one. Prefer the default (KSPWCO=0) for the
        #   headline; use this one only to answer "does the component work as a WCO at all".
        'poolspawn-compwco'   = @('-DKRUNMODE=RM_POOLSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKSPWCO=2')
        # ══════════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S125 KFRAMEINIT — the FFrame A/B arms (tutorial_launch.cpp, the KFRAMEINIT block).
        #   `OnPI` snapshots a LIVE FFrame and CallNative/CallBPGuarded overwrite only ~9 fields, so the
        #   window `0x48..0x80` (stock UE5: FlowStack + PreviousFrame) is inherited from a foreign,
        #   already-returned frame. A callee that pushes/pops the execution flow stack therefore pops a
        #   STALE offset. That is the confound under FK-22's founding `SpawnPlane FAULTED` — SpawnPlane
        #   is 3 push / 2 pop and BOTH functions S93 compared against it are 0/0.
        #
        #   KFRAMEINIT: 0 = UNFIXED (historical, and THE S93 REPRODUCTION ARM) | 1 = ZEROONLY
        #   (memset 0x48..0x80; fewest assumptions) | 2 = S80 (the ds_hybrid.cpp:2151 recipe, the only
        #   form of this fix that has ever run in this game). KFAULTINFO=1 makes a fault attributable
        #   (code/access/addr/rip/rva) instead of a bare bool, and MUST be on in BOTH arms or the
        #   reproduction arm's fault is exactly as uninterpretable as the measurement being retested.
        #
        #   ⚠⚠ THESE THREE ARE A COMPILE/VERIFY PROOF THAT BOTH PATHS BUILD, NOT THE FK-22 FLIGHT.
        #   RM_PHASELADDER is used only because it is heap-armed (FsArm) and therefore safe to have on
        #   disk. The real arms belong on the new DropPlane mode.
        #   ⛔ DO NOT register the arms on RM_DROPIN (20) even though it IS the S93 mode. It arms with
        #      InstallHook() -- a standing ProcessInternal `.text` patch held up to 40 s, i.e. the
        #      construct S112 measured at 10/10 armed windows dead vs 3/36 (Fisher p = 0.00000008).
        #      Re-flying S93's own mode to correct S93's confound would re-commit a worse one.
        'phaseladder-frames80'    = @('-DKRUNMODE=RM_PHASELADDER','-DKFRAMEINIT=2','-DKFAULTINFO=1')
        'phaseladder-framezero'   = @('-DKRUNMODE=RM_PHASELADDER','-DKFRAMEINIT=1','-DKFAULTINFO=1')
        'phaseladder-frameunfix'  = @('-DKRUNMODE=RM_PHASELADDER','-DKFRAMEINIT=0','-DKFAULTINFO=1')
        # ★★ S112 SHIPPED: 'play' now defaults to KFUNCSWAP=1 + KFSNAME="ReceiveTickClient", i.e. the
        #   hook is a 2-pointer HEAP write and the module image is never touched. 'play-textpatch' is
        #   the ROLLBACK, and it is also the A/B's measured control arm (10/10 armed windows died),
        #   so rolling back is a known quantity rather than an untested path.
        'play-textpatch'  = @('-DKRUNMODE=RM_PLAY','-DKFUNCSWAP=0')               # -1 dim: the OLD standing .text hook
        # ------------------------------------------------------------------------------------------
        # ★★★ S112 (2026-08-07) — THE .text-FREE ARM.  Read the KFUNCSWAP block in tutorial_launch.cpp.
        #   RM_PLAY's InstallHook() writes a 5-byte jmp into ProcessInternal (module .text) and holds it
        #   for the WHOLE 600 s sitting, because RM_PLAY never sets g_done.  S111 measured that a
        #   STANDING .text write is the protector-kill trigger: 7/8 deaths at a 320 s hold vs 0/22 for
        #   nothing injected and 0/9 for a PERMANENT heap-bytecode patch (p=0.00041).  So every FK-7
        #   tutorial run ever made held the ~88 %-lethal condition for its entire duration.
        #
        #   'play-funcswap' takes the same game-thread callbacks by overwriting UFunction.Func (+0xE0)
        #   -- a HEAP field whose value for a BP UFunction already IS &ProcessInternal -- on every BP
        #   UFunction found by one GUObjectArray walk, and passing through to the real dispatcher.
        #   +1 dim from 'play': identical behaviour, zero module-image bytes written.
        #   ⚠ VERIFY THE ARM IN-RUN, do not assume it: the marker prints, within ~8 s,
        #       [FS] *** ARMED AND LIVE: hitsGT=... (~N game-thread dispatches/s) ***      <- good
        #       [FS] *** NO GAME-THREAD HITS after ... THE SWAP IS A SILENT NO-OP ***      <- fall back
        #   plus an [FS] hot[] table naming the busiest UFunctions, so a follow-up build can narrow to
        #   -DKFSNAME="<name>" and swap one pointer instead of thousands.
        #
        #   'play-hold300' is the DOCUMENTED FALLBACK if funcswap is not viable: it keeps the .text
        #   hook but parameterises the hold (KPLAYHOLDMS) down to 300 s.  Strictly worse -- it only
        #   shortens the exposure, it does not remove it -- but it is one token and it moves the
        #   variable.  ⚠ Do NOT duty-cycle install/uninstall instead: S111 varied patch DURATION, not
        #   the NUMBER of write events, so trading one long window for many short ones is speculative.
        #   Both are -1/+1 dim from 'play' in exactly one dimension each, per the rule above.
        'play-funcswap'   = @('-DKRUNMODE=RM_PLAY','-DKFSNAME=\"\"')                # +1 dim: swap ALL ~17,126 BP UFunctions
        'play-hold300'    = @('-DKRUNMODE=RM_PLAY','-DKPLAYHOLDMS=300000')       # -1 dim: same .text hook, 300 s not 600 s
        # ★ S112 completion-review follow-ups. 'play-funcswap' swaps ~17,126 UFunction.Func pointers,
        #   which is a large novel surface and the leading suspect for its OWN 2/10 residual. These two
        #   shrink and then isolate it:
        #     * -profile widens the attribution window from 4 s (world-load, everything hits=1 and
        #       useless) to 90 s so the hot[] table names functions from a SETTLED world;
        #     * -one arms exactly ONE UFunction -- a ~17,000x smaller footprint -- and holds the full
        #       600 s, which also finally covers the historical 87-524 s FK-7 death spread.
        #   Fill in KFSNAME from a -profile run's hot[00] BEFORE building -one.
        'play-funcswap-profile' = @('-DKRUNMODE=RM_PLAY','-DKFUNCSWAP=1','-DKFSPROFILEMS=90000','-DKFSHOTN=64')
        # ✝ 'play-funcswap-600' REMOVED -- KPLAYHOLDMS already defaults to 600000, so it duplicated 'play'.
        # ★ S112 -- the completion review's highest-value arm. KFSNAME matches the UFunction's OWN
        #   FName (FsScan -> NameIs), so this arms only the UFunctions called `ReceiveTickClient`
        #   instead of all 17,126 BP UFunctions -- a ~4-order-of-magnitude smaller footprint, which is
        #   the leading suspect for 'play-funcswap's own 2/10 residual.
        #   Target chosen from a MEASURED settled-world profile (`play-funcswap-profile`, run
        #   s112p-prof-02): BP_LokiHeroCharacter_C::ReceiveTickClient, 1549 hits / 90 s = ~17/s, i.e.
        #   once per frame -- exactly the cadence RM_PLAY's camera re-assert / WASD / VtGuard need.
        #   The 4 s window used before this profiled only the WORLD LOAD, where everything reads hits=1
        #   and every candidate is useless; widening it to 90 s is what made this selectable.
        #   KPLAYHOLDMS already defaults to 600000, so this also holds the full 600 s and finally
        #   covers the historical 87-524 s FK-7 death spread.
        # ✝ 'play-funcswap-one' REMOVED 2026-08-08 -- with KFUNCSWAP/KFSNAME now defaulting to its
        #   exact flags it would be BYTE-IDENTICAL to 'play'. CLAUDE.md's rule: when a -D default
        #   changes, DELETE the redundant variant rather than leave a second name for one artifact.
        # ------------------------------------------------------------------------------------------
        'play-novtguard'  = @('-DKRUNMODE=RM_PLAY','-DKVTGUARD=0')               # -1 dim: view-target guard OFF
        # S123: KGCROOT's DEFAULT FLIPPED TO 0 (the poke is measured inert AND it blocks a correct
        #   AddToRoot -- see docs/fk27-successor-gc-rooting-settled.md). So 'play-nogcroot' became a
        #   byte-identical duplicate of 'play' (both .text 9bc10a4552c596e1, VERIFIED) and is REMOVED
        #   per this repo's own rule about not leaving same-flag duplicates around to be A/B'd against
        #   themselves. Its inverse is now the meaningful control and the rollback:
        'play-gcroot'     = @('-DKRUNMODE=RM_PLAY','-DKGCROOT=1')                # +1 dim: the retired inert RootSet poke, for A/B
        'play-nopimutex'  = @('-DKRUNMODE=RM_PLAY','-DKPIMUTEX=0')               # -1 dim: PI-hook mutex OFF
        'play-noxformfix' = @('-DKRUNMODE=RM_PLAY','-DKXFORMFIX=0')              # -1 dim: spawn-FTransform fix OFF
        'play-testactor'  = @('-DKRUNMODE=RM_PLAY','-DKTESTACTOR=1')             # +1 dim: 2nd skeletal body BACK ON
        # ✝ 'play-earlywalk' (-DKAUTOWALKATMS=4000) — REMOVED S110 (2026-08-05). It existed only to
        #   RACE the collection: with the run AnimSequence being GC'd 2-8 s after body build, moving the
        #   self-driven walk from t+20 s to t+4 s put the idle<->run swap inside the asset's lifetime.
        #   It did its job (S109 §23, 3/3 vs 0/3) and proved the causal chain, but it was always a
        #   DIAGNOSTIC, and it cost the three idle screenshots the 20 s was protecting.
        #   S110 removed the reason for it: KANIMREF parks the asset in a reachable UPROPERTY, so it
        #   survives GC entirely and the swap fires at the DEFAULT KAUTOWALKATMS=20000 (measured: two
        #   GC passes survived, 4 swaps, zero [GCW] lines). Racing a collection that no longer happens
        #   is not a control, it is a second artifact to confuse with 'play' -- and this pair was the
        #   worst offender for that: byte-identical whole-file AND .text SIZES, separable only by hash.
        #   Per CLAUDE.md's rule, delete rather than leave a near-identical DLL lying around.
        #   To resurrect the behaviour for a one-off: -DKAUTOWALKATMS=<ms> still works, no variant needed.
        #   History: docs/s109-dump-forensics.md §23, docs/s110-item-watch-gc-mechanism.md §4e.
        # ★ S109 (2026-08-05) — control for the root-bit fix. -1 dim: restores the pre-S109
        #   AND(rooted)&~OR(unrooted) corroboration, which MEASURED 3/3 refused the correct bit
        #   ("cand=02000000 expect=40000000 -> REFUSING to poke flags") because ordinary rooted
        #   objects contaminated the OR. Expect: strict => rooted=0 failed=5, assets GC'd ~7-10 s.
        'play-strictroot' = @('-DKRUNMODE=RM_PLAY','-DKGCROOTSTRICT=1')          # -1 dim: old root-bit test
        # ★ S110 (2026-08-05) — control for the REFERENCE fix (KANIMREF, on by default in 'play').
        #   The fix parks the run AnimSequence in the body component's unused
        #   AnimationData.AnimToPlay UPROPERTY so UE's traversal can reach it. Rooting was measured
        #   INERT (bit 30 verified set 33.1 s before a pass; destroyed at that pass anyway -- three
        #   armed windows, only the injection phase varied). See docs/s110-item-watch-gc-mechanism.md.
        #   Expect with KANIMREF=0: the run anim goes ROOTED+STALE at the next reachability flip and is
        #   destroyed within ~1 s, exactly as in the S110 runs. With it on: re-marked, and it survives.
        #   Read the verdict with `python tools\re\item_watch.py --marker`.
        'play-noanimref'  = @('-DKRUNMODE=RM_PLAY','-DKANIMREF=0')               # -1 dim: no UPROPERTY reference
        # ------------------------------------------------------------------------------------------
        # ★ S108b — THE LEFTOVER-DIAGNOSTIC BISECT. KSMACTOR (:4031) and KSTATICTEST (:4034) are S95
        #   spawn-vs-component discriminators that still default to 1, exactly as KTESTACTOR did until
        #   S106 defaulted it to 0 for causing a second degenerate body. They are NOT fixes: they spawn
        #   a StaticMeshActor and build a bare StaticMeshComponent on the hero purely to answer a
        #   rendering question that is long since answered.
        #   MEASURED 2026-08-04: in the two markers copied AFTER death, the SEH-caught
        #   `[ANIM] PlayAnimation(...) FAULTED` appears iff the [SMT] KSTATICTEST block ran (1/1 vs 0/1),
        #   and in `fk24-stage-testact1` the faulting registers name the class outright:
        #   `[NULL] cls RBX=StaticMeshComponent RDI=StaticMeshComponent`. Mechanism is plain in the
        #   source: KSTATICTEST calls BuildHeroBody(hero, StaticMeshComponent, ...) at :4970, and
        #   BuildHeroBody unconditionally drives PlayAnimation -- on a component that has no animation.
        #   Run 'play-nodiag' FIRST (the disjunction: cheap, high information); bisect with the two
        #   single-variable arms only if it survives.
        #   ★ RESOLVED S108b: KSTATICTEST now DEFAULTS TO 0 in the source, so 'play' itself carries the
        #   fix and `play-nostatictest` is GONE -- it would now be byte-identical to 'play', which is
        #   exactly the footgun this table warns about above (identical DLLs A/B'd against each other,
        #   wasting a live run). The control is inverted instead, mirroring 'play-testactor'.
        #   'play-nodiag' is ALSO gone: with KSTATICTEST defaulting to 0 it collapses onto
        #   'play-nosmactor' (both would be RM_PLAY + KSMACTOR=0), i.e. the identical-DLL footgun again.
        #   Two flags, two registered variants, no duplicates.
        'play-statictest'  = @('-DKRUNMODE=RM_PLAY','-DKSTATICTEST=1')                 # +1 dim: the S95 [SMT] discriminator BACK ON
        'play-nosmactor'   = @('-DKRUNMODE=RM_PLAY','-DKSMACTOR=0')                    # -1 dim: [SMA] StaticMeshActor spawn
        'topdowncam-novtguard' = @('-DKRUNMODE=RM_TOPDOWNCAM','-DKVTGUARD=0')
        # ------------------------------------------------------------------------------------------
        # ★ FK-24 WATCHPOINT PROBE (S107, tutorial_launch.cpp: KWPROBE).  These are DIAGNOSTIC builds,
        #   not candidates -- the one-variable-from-'play' discipline above governs the A/B CONTROLS;
        #   these two add an instrument on top of 'play' and are +1 dim from it and from each other.
        #   KWPROBE defaults to 0 in the source, so 'play' itself is byte-unchanged by their existence.
        #     wprobe  = KWPROBE 1  PRIMARY  : DR0/DR1 hardware 1-byte write watchpoint, swept over all threads
        #     wprobe2 = KWPROBE 2  FALLBACK : PAGE_READONLY process-wide write trap on the page holding &Target
        #   Run wprobe first; escalate to wprobe2 ONLY on a VOID verdict (selftest FAIL / dr7 readback zero),
        #   never on a clean negative -- MEASURED base rate is 1-in-3..1-in-2, so quiet runs are expected.
        #   KVTGUARD stays ON in both: the guard repairs the pointer AFTER the write, so the session survives
        #   the corruption and keeps logging, and the watchpoint catches the store either way.
        'play-wprobe'     = @('-DKRUNMODE=RM_PLAY','-DKWPROBE=1')                # +1 dim: DR watchpoint
        'play-wprobe2'    = @('-DKRUNMODE=RM_PLAY','-DKWPROBE=2')                # +1 dim: page write-trap
        # Reproduces the cohort that actually crashed (the 4 camera dumps predate KXFORMFIX entirely), so it
        # maximises P(the write happens). Run only after play-wprobe has produced instrument-valid launches.
        'play-wprobe-noxformfix' = @('-DKRUNMODE=RM_PLAY','-DKWPROBE=1','-DKXFORMFIX=0')
        # ★ S107b — VINTAGE-MATCHED probe.  The crash dumps identify the view target by
        #   POV.Rotation == (-66,-90,0):  KCAMPITCH=-66 is the SOURCE default, but KPUPYAW=-90 is NOT
        #   (source default 0.0) -- it came from the S99 build flags (docs/next-session-prompt-s99.md:156).
        #   So the crashing vintage was NEITHER the pure source-default build NOR the pure S99 build.
        #   This variant reproduces the observed POV exactly, and the probe LOGS the live POV so the
        #   match is VERIFIED IN-RUN rather than assumed.  Use this one to hunt the writer.
        'play-wprobe-v66' = @('-DKRUNMODE=RM_PLAY','-DKWPROBE=1','-DKPUPYAW=-90')
        # ★ S108 — the page-mode twin of play-wprobe-v66. Same vintage-matched POV, but the process-wide
        #   PAGE_READONLY trap instead of per-thread DRs, so the packer's DR polling (MEASURED in S107:
        #   "W2: 1 thread(s) had our Dr7 bits CLEARED BY SOMETHING ELSE") cannot open a coverage hole.
        #   Still +1 dim from play-wprobe2, exactly as v66 is +1 dim from wprobe.
        'play-wprobe2-v66' = @('-DKRUNMODE=RM_PLAY','-DKWPROBE=2','-DKPUPYAW=-90')
    }
    'gft_ready_fix' = @{
        ''           = @()
        'fillvalues' = @('-DFILL_VALUES')    # also fill GameFeatureToggles@+0x130; off by default
    }
    'ds_hybrid' = @{
        # Mode enum, ds_hybrid.cpp:99. Default when KMODE is unset is MODE_SPECTATOR_CAM, so the
        # plain build and 'spectator' are the same binary (measured: 2 bytes differ = PE timestamp).
        ''          = @()
        'spectator' = @('-DKMODE=MODE_SPECTATOR_CAM')   # same build as the plain ds_hybrid.dll
        'freecam'   = @('-DKMODE=MODE_FREECAM')
        'spawnhero' = @('-DKMODE=MODE_SPAWN_HERO')
        'deploy'    = @('-DKMODE=MODE_DEPLOY')
    }
}

# --- the set launch-redirect.ps1 + inject-secondaries.ps1 actually inject (verified against both) ---
#     catalog_store_fix is the primary (injected at launch); the rest are the secondary set.
$DefaultSet = @('catalog_store_fix','mainmenu_refresh_pi8','catalog_pick_fix',
                'loadout_fix','missions_fix','battlepass_adopt_fix')

# ====================================================================================================
# toolchain discovery
# ====================================================================================================

function Find-Clang {
    if ($Clang) {
        if (-not (Test-Path $Clang)) { throw "clang++ not found at $Clang" }
        return $Clang
    }
    $c = Get-Command clang++ -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    # The toolchain that built every committed DLL on this machine ships inside the Swift toolchain.
    $cands = @(
        "$env:LOCALAPPDATA\Programs\Swift\Toolchains\*\usr\bin\clang++.exe",
        "$env:ProgramFiles\LLVM\bin\clang++.exe",
        "${env:ProgramFiles(x86)}\LLVM\bin\clang++.exe",
        "$env:ProgramFiles\*\Microsoft Visual Studio\*\*\VC\Tools\Llvm\x64\bin\clang++.exe",
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\*\*\VC\Tools\Llvm\x64\bin\clang++.exe"
    )
    foreach ($p in $cands) {
        $hit = Get-ChildItem $p -ErrorAction SilentlyContinue |
               Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Find-VsInstall {
    # vswhere first (the supported way), then the known install paths on this machine.
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $p = & $vswhere -latest -products * `
                        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
                        -property installationPath 2>$null
        if ($p) { return ($p | Select-Object -First 1) }
    }
    foreach ($f in @("$env:ProgramFiles\Tools\Microsoft Visual Studio\2022\Enterprise",
                     "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2019\BuildTools",
                     "$env:ProgramFiles\Microsoft Visual Studio\2022\Community")) {
        if (Test-Path (Join-Path $f 'VC\Auxiliary\Build\vcvars64.bat')) { return $f }
    }
    return $null
}

function Import-VsEnv([string]$vsPath) {
    # Run vcvars64.bat in a child cmd and pull the resulting environment back in. clang's MSVC driver
    # honours INCLUDE / LIB, so this serves both toolchains.
    $bat = Join-Path $vsPath 'VC\Auxiliary\Build\vcvars64.bat'
    if (-not (Test-Path $bat)) { throw "vcvars64.bat not found under $vsPath" }
    $out = & cmd.exe /c "`"$bat`" >nul 2>&1 && set" 2>$null
    $n = 0
    foreach ($line in $out) {
        if ($line -match '^([^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
            $n++
        }
    }
    if ($n -eq 0) { throw "vcvars64.bat produced no environment (path: $bat)" }
    return $n
}

# ====================================================================================================
# PE inspection -- the constraint gates read the real image, they do not trust the compiler
# ====================================================================================================

function Convert-RvaToOffset($secs, $rva) {
    foreach ($s in $secs) {
        $span = [Math]::Max($s[1], $s[3])
        if ($rva -ge $s[0] -and $rva -lt ($s[0] + $span)) { return $s[2] + ($rva - $s[0]) }
    }
    return -1
}

function Get-PeInfo([string]$path) {
    $b = [System.IO.File]::ReadAllBytes($path)
    if ($b.Length -lt 0x40 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) { throw "not a PE file" }
    $pe = [BitConverter]::ToInt32($b, 0x3c)
    if ([BitConverter]::ToUInt32($b, $pe) -ne 0x00004550) { throw "bad PE signature" }
    $nsec  = [BitConverter]::ToUInt16($b, $pe + 6)
    $optsz = [BitConverter]::ToUInt16($b, $pe + 20)
    $opt   = $pe + 24
    $magic = [BitConverter]::ToUInt16($b, $opt)
    if ($magic -eq 0x20b) { $ddoff = $opt + 112 } else { $ddoff = $opt + 96 }
    $expRva = [BitConverter]::ToUInt32($b, $ddoff)
    $impRva = [BitConverter]::ToUInt32($b, $ddoff + 8)

    $secs = @()
    $so = $opt + $optsz
    for ($i = 0; $i -lt $nsec; $i++) {
        $o = $so + $i * 40
        $secs += ,@([BitConverter]::ToUInt32($b, $o + 12),
                    [BitConverter]::ToUInt32($b, $o + 8),
                    [BitConverter]::ToUInt32($b, $o + 20),
                    [BitConverter]::ToUInt32($b, $o + 16))
    }

    $imports = @()
    if ($impRva -ne 0) {
        $off = Convert-RvaToOffset $secs $impRva
        while ($off -ge 0 -and ($off + 20) -le $b.Length) {
            $nameRva = [BitConverter]::ToUInt32($b, $off + 12)
            if ($nameRva -eq 0) { break }
            $no = Convert-RvaToOffset $secs $nameRva
            if ($no -lt 0) { break }
            $end = $no
            while ($end -lt $b.Length -and $b[$end] -ne 0) { $end++ }
            $imports += [System.Text.Encoding]::ASCII.GetString($b, $no, $end - $no)
            $off += 20
        }
    }
    return [pscustomobject]@{
        Size       = $b.Length
        Imports    = $imports
        HasExports = ($expRva -ne 0)
        Linker     = ("{0}.{1:D2}" -f $b[$opt + 2], $b[$opt + 3])
        EntryPoint = [BitConverter]::ToUInt32($b, $opt + 16)
    }
}

function Test-ShimBinary([string]$path) {
    # Returns the list of constraint violations; empty means the DLL is safe to inject.
    $bad = @()
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $text  = [System.Text.Encoding]::ASCII.GetString($bytes)
    # Symbol list matches verify_dll.py. Validated against all seven known-good, live-proven DLLs:
    # none contains any of these, so the gate does not false-positive.
    foreach ($sym in '__CxxFrameHandler3', '__CxxFrameHandler4', '_CxxThrowException',
                     '__std_terminate', '_Unwind_Resume') {
        if ($text.Contains($sym)) { $bad += "C++ exception machinery: $sym" }
    }
    $info = Get-PeInfo $path
    if ($info.EntryPoint -eq 0) { $bad += 'no entry point (DllMain would never run)' }
    foreach ($imp in $info.Imports) {
        $low = $imp.ToLowerInvariant()
        $isBanned = $false
        foreach ($p in $BannedImports) { if ($low.StartsWith($p)) { $isBanned = $true } }
        if ($isBanned) {
            $bad += "dynamic CRT dependency: $imp"
        }
        elseif ($AllowedImports -notcontains $low) {
            $bad += "unexpected import: $imp (add it to AllowedImports if intended)"
        }
    }
    return ,$bad
}

# ====================================================================================================
# build
# ====================================================================================================

function Get-VariantMap([string]$shim) {
    if ($Variants.ContainsKey($shim)) { return $Variants[$shim] }
    return @{ '' = @() }
}

function Build-One([string]$shim, [string]$variant) {
    $defs   = (Get-VariantMap $shim)[$variant]
    $suffix = ''
    if ($variant) { $suffix = '_' + ($variant -replace '-', '_') }
    $label  = "{0}{1}.dll" -f $shim, $suffix
    $out    = Join-Path $OutDir $label
    $src    = Join-Path $root ("{0}.cpp" -f $shim)

    Write-Host ("  {0,-40} " -f $label) -NoNewline
    if (-not (Test-Path $src)) {
        Write-Host "SKIP (no $shim.cpp)" -ForegroundColor DarkGray
        return $null
    }

    if ($script:useMsvc -and $MsvcIncompatible.ContainsKey($shim)) {
        Write-Host "UNSUPPORTED under MSVC" -ForegroundColor Yellow
        Write-Host ("      " + $MsvcIncompatible[$shim]) -ForegroundColor DarkYellow
        Write-Host  "      build this shim with clang (-Toolchain clang)." -ForegroundColor DarkYellow
        return @{ ok = $false; reason = 'msvc-incompatible' }
    }

    if (Test-Path $out) { Remove-Item $out -Force }

    if ($script:useMsvc) {
        # /LD = build a DLL   /MT = STATIC CRT (constraint 2; MSVC would otherwise pick /MD)
        # no /EH switch = no C++ exception machinery emitted (constraint 1)
        $obj  = Join-Path $OutDir ("{0}{1}.obj" -f $shim, $suffix)
        $cargs = @('/nologo','/LD','/MT','/O2','/W0','/D_CRT_SECURE_NO_WARNINGS','/GS-')
        foreach ($d in $defs) { $cargs += ($d -replace '^-D', '/D') }
        $cargs += @($src, "/Fo:$obj", '/link', "/OUT:$out", '/DLL')
        foreach ($l in $SysLibs) { $cargs += ('{0}.lib' -f $l) }
        $log = & cl.exe @cargs 2>&1
    } else {
        $cargs = @('-shared','-O2','-w')
        foreach ($d in $defs) { $cargs += $d }
        $cargs += @($src, '-o', $out)
        foreach ($l in $SysLibs) { $cargs += ('-l{0}' -f $l) }
        $log = & $script:cc @cargs 2>&1
    }

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $out)) {
        Write-Host "FAILED" -ForegroundColor Red
        $log | Where-Object { $_ -match 'error|LNK\d|unresolved' } | Select-Object -First 10 |
            ForEach-Object { Write-Host ("      " + $_) -ForegroundColor DarkRed }
        return @{ ok = $false; reason = 'compile' }
    }

    $bad = Test-ShimBinary $out
    if ($bad.Count -gt 0) {
        Write-Host "REJECTED" -ForegroundColor Red
        foreach ($x in $bad) { Write-Host ("      " + $x) -ForegroundColor Red }
        Write-Host "      an injected payload must be exception-free and static-CRT - see BUILD.md" -ForegroundColor DarkRed
        Remove-Item $out -Force
        return @{ ok = $false; reason = 'constraint' }
    }

    $info = Get-PeInfo $out
    Write-Host ("ok {0,9:N0} bytes  [{1}]" -f $info.Size, ($info.Imports -join ' ')) -ForegroundColor Green

    if ($Verify -and ($OutDir -ne $root)) {
        $committed = Join-Path $root $label
        if (Test-Path $committed) {
            $a = [System.IO.File]::ReadAllBytes($committed)
            $bb = [System.IO.File]::ReadAllBytes($out)
            if ($a.Length -ne $bb.Length) {
                Write-Host ("      verify: SIZE DIFFERS vs committed ({0:N0} vs {1:N0})" -f $a.Length, $bb.Length) -ForegroundColor Yellow
            } else {
                $diff = 0
                for ($i = 0; $i -lt $a.Length; $i++) { if ($a[$i] -ne $bb[$i]) { $diff++ } }
                if ($diff -le 8) {
                    Write-Host ("      verify: REPRODUCES committed .dll ({0} bytes differ = PE timestamp)" -f $diff) -ForegroundColor Green
                } else {
                    Write-Host ("      verify: same size, {0} bytes differ" -f $diff) -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "      verify: no committed .dll to compare against" -ForegroundColor DarkGray
        }
    }

    if (-not $KeepIntermediates) {
        foreach ($ext in '.exp', '.lib', '.obj') {
            $p = [IO.Path]::ChangeExtension($out, $ext)
            if (Test-Path $p) { Remove-Item $p -Force }
        }
    }
    return @{ ok = $true }
}

# ====================================================================================================
# main
# ====================================================================================================

$AllShims = @(Get-ChildItem (Join-Path $root '*.cpp') | ForEach-Object { $_.BaseName } | Sort-Object)

if ($List) {
    Write-Host "shims in $root ($($AllShims.Count) .cpp files)`n"
    foreach ($s in $AllShims) {
        $vm = Get-VariantMap $s
        $vs = (($vm.Keys | Sort-Object) | ForEach-Object { if ($_) { $_ } else { '(plain)' } }) -join ', '
        $flag = ''
        if ($MsvcIncompatible.ContainsKey($s)) { $flag = '   [clang only]' }
        $mark = '  '
        if ($DefaultSet -contains $s) { $mark = '* ' }
        Write-Host ("{0}{1,-32} {2}{3}" -f $mark, $s, $vs, $flag)
    }
    Write-Host "`n* = default injection set (launch-redirect.ps1 + inject-secondaries.ps1):"
    Write-Host "  $($DefaultSet -join ', ')"
    Write-Host "`nevery shim links: $($SysLibs -join ', ')"
    return
}

# --- pick and set up the toolchain ---
$script:useMsvc = ($Toolchain -eq 'msvc')
$script:cc = $null

if (-not $script:useMsvc) {
    $script:cc = Find-Clang
    if (-not $script:cc) {
        if ($Toolchain -eq 'clang') {
            throw "clang++ not found. Install LLVM or pass -Clang <path>. (-Toolchain msvc builds all but: $($MsvcIncompatible.Keys -join ', '))"
        }
        Write-Host "clang++ not found - falling back to MSVC." -ForegroundColor Yellow
        $script:useMsvc = $true
    }
}

$vsPath = Find-VsInstall
if ($script:useMsvc) {
    if (-not $vsPath) { throw "no Visual Studio with the C++ toolset found (vswhere and known paths both empty)." }
    $n = Import-VsEnv $vsPath
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) { throw "cl.exe still not on PATH after vcvars64 ($vsPath)" }
    Write-Host "toolchain: MSVC cl.exe" -ForegroundColor Yellow
    Write-Host "           $vsPath ($n env vars imported)"
    Write-Host "           NOTE: clang is the reference toolchain; MSVC output is NOT byte-identical to" -ForegroundColor DarkYellow
    Write-Host "           the committed DLLs, and cannot build: $($MsvcIncompatible.Keys -join ', ')" -ForegroundColor DarkYellow
} else {
    # clang auto-detects the VS install for headers/libs, and THAT auto-detection is what reproduces
    # the committed DLLs -- so do not override INCLUDE/LIB unless the caller explicitly asks (-VsEnv).
    if ($VsEnv) {
        if (-not $vsPath) { throw "-VsEnv given but no Visual Studio found." }
        $null = Import-VsEnv $vsPath
        Write-Host "toolchain: clang++   (INCLUDE/LIB forced from $vsPath)"
    } else {
        Write-Host "toolchain: clang++"
    }
    Write-Host "           $($script:cc)"
    $ver = (& $script:cc --version 2>&1 | Select-Object -First 1)
    Write-Host "           $ver"
}
Write-Host "outdir   : $OutDir"
if ($OutDir -eq $root) {
    Write-Host "           IN-PLACE - this overwrites the DLLs the injectors load." -ForegroundColor Yellow
}
Write-Host ""

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# --- resolve targets ---
$targets = @()
if ($Name) {
    if ($AllShims -notcontains $Name) { throw "unknown shim '$Name' (no $Name.cpp). Run -List." }
    $vm = Get-VariantMap $Name
    if ($Variant) {
        if (-not $vm.ContainsKey($Variant)) { throw "unknown variant '$Variant' for $Name. Run -List." }
        $targets += ,@($Name, $Variant)
    } else {
        foreach ($v in ($vm.Keys | Sort-Object)) { $targets += ,@($Name, $v) }
    }
}
elseif ($All) {
    foreach ($s in $AllShims) {
        foreach ($v in ((Get-VariantMap $s).Keys | Sort-Object)) { $targets += ,@($s, $v) }
    }
}
else {
    foreach ($s in $DefaultSet) {
        foreach ($v in ((Get-VariantMap $s).Keys | Sort-Object)) { $targets += ,@($s, $v) }
    }
}

$okN = 0; $failN = 0; $failed = @()
foreach ($t in $targets) {
    $r = Build-One $t[0] $t[1]
    if ($null -eq $r) { continue }
    if ($r.ok) {
        $okN++
    } else {
        $failN++
        if ($t[1]) { $failed += ("{0}/{1}" -f $t[0], $t[1]) } else { $failed += $t[0] }
    }
}

Write-Host ""
if ($failN) {
    Write-Host ("{0} built, {1} failed" -f $okN, $failN) -ForegroundColor Red
    Write-Host ("failed: {0}" -f ($failed -join ', ')) -ForegroundColor Red
    exit 1
} else {
    Write-Host ("{0} built, 0 failed" -f $okN) -ForegroundColor Green
}
