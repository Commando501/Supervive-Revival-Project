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

# PowerShell 7's Standard native argument mode removes the literal quotes from registry entries such
# as -DKFSNAME=\"\" before clang sees them, turning an intended empty C string into an empty macro and
# breaking otherwise reproducible builds. Legacy mode preserves the argv shape used by Windows
# PowerShell 5.1. This assignment is script-scoped and has no effect on the caller after the script.
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandArgumentPassing = 'Legacy'
}

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
        # ★ S179 -- name the F10 bail predicate. F10 (2026-09-04) produced a 3-line fo marker
        #   ([0] started + [0] command, then nothing) with the game process alive for 298 s,
        #   zero Windows Application error events, and zero crashpad archives across the F10 window.
        #   Direct source-read refuted every CFG-walk candidate (RANK1/2/3 in wf_7f899fdc-61d). The
        #   3-line marker is consistent with fo entering the 120 s Resolve() polling loop and being
        #   terminated before either the success emit (24631) or the timeout emit (24630). This
        #   variant adds per-gate + per-Resolve-iter markers so a re-fly says which field cannot
        #   resolve at the menu OR at which gate fo actually died.
        #   ★ Byte-identical to `fo` when KFOVERBOSE=0 (default); flip only in the -verbose build.
        #   ⚠ Do not fly this as `-Hook` in a default sitting: the marker file will grow with per-iter
        #    lines and the point is diagnostic, not shippable.
        # S180 Rank 1 (docs/s180-fk32-post-defeat-analysis-settled.md): 60 s wait post-InstallHook
        # to test H4d (8s window too short for game-thread PI dispatch after S177 F9). If
        # hitsGT>0 with time-to-first-hit in [8s,60s] -> H4d confirmed, H1/H2/H3/H4c moot for
        # this phenotype. If hitsGT=0 at 60s -> halt is durable >60s, promoting the other four
        # candidates. See §"Ranked S181 flights" in the settled doc.
        'fo-verbose' = @('-DKRUNMODE=RM_FORCEOPEN','-DKFOVERBOSE=1','-DKFOWAITMS=60000')  # +1 dim: per-gate + per-Resolve-iter Marker + 60s wait
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
        #   ★★★★★ S150-drop PHASE-A: the CLEAN drop-phase REACT arm. B0 + B3a + B4 + B0c
        #     (0x01|0x04|0x10|0x20 = 0x35) -- calls ONLY `OnRoundPhaseChanged` (no spaces, ubergraph 1403,
        #     the DROP reaction) with NewPhase=6 (EGP_Lineup, KDPPHASE default), NOT the spaces-variant
        #     `On Round Phase Changed` (ubergraph 545 = the GoToPhase LADDER, which is NOT the plane).
        #     `dropplane-handler` (0x3D) confounds the two by running BOTH; this isolates the correct one.
        #     No SpawnPlane (B1), so the census delta is attributable to the react handler alone; if the
        #     handler internally spawns/flies the plane it shows in the AFTER census. Pairs with the
        #     external reader tools/re/drop_ride_readout.py. Risk class: CALL-ONLY, no .text write.
        #     See docs/drop-sequence-status-s150.md §6.5 (offline pre-flight L2). Diff the .text HASH.
        'dropplane-react'     = @('-DKRUNMODE=RM_DROPPLANE','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKDPARMS=0x35')
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
        # ★★★★★ S150-drop RM_MOUNT -- PUT THE RIDER INTO THE POD + co-move it + optional descent.
        #   Sibling of RM_DISMOUNT: the game's own mount (AuthPlayerEnterWorldAttachedToRidable 0x55CD510)
        #   is unreachable (stripped round-game-mode getter), but its success body is just a PlayersAttached
        #   append + a one-time reposition -- both replicable. The S150 pre-flight MEASURED that a
        #   poke-appended rider does NOT co-move the flying pod, so a real ride needs THIS arm's per-hit
        #   reposition (POLL). Risk class DATA (one PlayersAttached append via the game's OWN ResizeGrow)
        #   + CALL-ONLY (MoveStep 0x55C1B20, SetPredropHidden, SetActorEnableCollision, StartPodGameplay
        #   via ProcessEvent slot 78). NO .text write, NO PI hook, NO CDO poke. PRESUPPOSES an initialised
        #   flying pod -- stage a droppod/poolspawn injection FIRST (e.g. gft -> fo -> sp ->
        #   droppod-pe-cdopoke -> this). See docs/drop-sequence-status-s150.md §6.5.
        #   KMTARMS bits: 0x01 APPEND | 0x02 UNHIDE | 0x04 POSITION-ONCE | 0x08 POLL(ride) | 0x10 PHASE-B(descend)
        #   ⚠ R3 is the decisive receipt (external RPM: hero X vs pod X). mount-ride = treatment;
        #     mount-noride = the poke-only control that MUST show a frozen rider. Diff the .text HASH.
        'mount'               = @('-DKRUNMODE=RM_MOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')                                 # recon only (KMTARMS=0): resolve pod/comp/PS/hero, read arrays, no writes
        'mount-append'        = @('-DKRUNMODE=RM_MOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKMTARMS=0x01')                # append PS -> PlayersAttached only
        'mount-noride'        = @('-DKRUNMODE=RM_MOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKMTARMS=0x07')                # append+unhide+position, NO poll -> POKE-ONLY CONTROL (frozen rider)
        'mount-ride'          = @('-DKRUNMODE=RM_MOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKMTARMS=0x0F')                # append+unhide+position+POLL -> the RIDE TREATMENT
        'mount-descend'       = @('-DKRUNMODE=RM_MOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKMTARMS=0x1F')                # ride + StartPodGameplay (descent)
        'mount-phaseb'        = @('-DKRUNMODE=RM_MOUNT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKMTARMS=0x10')                # StartPodGameplay only (descent test, no mount)
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
        # ---- S143 RM_BOTFIGHT: the MINIMUM BOT-FIGHT LOOP (docs/coop-vs-ai-roadmap-s142.md) --------
        # ONE source arm (DoBotFight), read-only recon always, each destructive step gated by a KBFARMS
        # bit: bit0 spawn, bit1 bind (WireAbilitySystem+InitAbilityActorInfo), bit2 grant, bit3 activate,
        # bit4 damage, bit5 wirebot. Fly the escalation ACROSS SITTINGS (FK-32 ~1 injection/staging),
        # no source edit. All are the no-.text-write funcswap route (refuse under KFUNCSWAP=0).
        # Knobs: -DKBFOWNER (InitAbilityActorInfo owner 0=carrier/1=PS/2=hero) -DKBFDMG -DKBFDMGTGT
        #        -DKBFABIL (Ability1/2/3/AbilityDodgeRoll) -DKBFHERO.
        # SITTING 1 -- pure read-only recon (zero risk): resolution, player ASC/AvatarActor state,
        #   player team index, hero ability classes, baseline census. Confirms the arm reads correctly.
        'botfight'            = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1')
        # SITTING 2 (recommended first REAL flight) -- the two DECISION-CRITICAL de-risks in one
        #   injection (independent subsystems, each with its own readout): K_SPAWN reads the bot's team
        #   vs the player's (is an enemy bot hostile client-side at all?), K_BIND runs the never-called
        #   InitAbilityActorInfo AvatarActor bind (WALL P). 0x03 = spawn|bind.
        'botfight-probe'      = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x03')
        # S149 isolated persistent bootstrap for unchanged S148: unique-owner selection, the existing
        # WireAbilitySystem path, exactly one guarded InitAbilityActorInfo call, strict post-bind
        # identity/property witness, then callback drain + Func restoration before BIND_READY.
        # Compile-time policy and artifact contracts forbid every other KBF arm, natural input, and S148.
        'botfight-bind-only'  = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x02','-DKBFBINDONLY=1','-DKBFOWNER=0','-DKBFSELFCAL=0','-DKBFNATURALINPUT=0')
        # SITTING 3 -- WALL P full: bind -> grant Ability1 -> activate (player casts). 0x0E.
        'botfight-cast'       = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x0E')
        # S144 -- ACTIVATE ONLY (0x08): no re-bind, no re-grant. Retained as a diagnostic for a process where
        #   the ability is already granted+committed; combined arms now verify the exact durable spec later.
        'botfight-activate'   = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x08')
        # S144 -- ALIVE + ACTIVATE (0x48): poke hero LivingState=Alive, then TryActivate. For a process where the
        #   ability is ALREADY granted; tests whether LivingState=Dead was THE activation blocker (single variable).
        'botfight-alivecast'  = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x48')
        # S145 -- full WALL P: bind->grant->alive->GAS attributes->later-callback verified activation (0xCE).
        'botfight-castalive'  = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE')
        # S145 controlled follow-up: identical 0xCE path, only Ability1/LMB -> Ability3/MiniDash changes.
        'botfight-castalive-dash' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"')
        # S145 charge-gate intervention: same direct MiniDash path, one verified runtime charge immediately before activation.
        'botfight-castalive-dash-charge1' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1')
        # S145 diagnostic after charge1 remained false: same charge treatment, then exact virtual cooldown/cost census.
        'botfight-castalive-dash-gates' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1')
        # S145 one-variable cost treatment: prove cooldown/cost 1/0, seed only registered Mana 0/0->10/10,
        # re-run the identical exact-instance gates, and activate only if the treatment flips them to 1/1.
        'botfight-castalive-dash-mana10' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10')
        # S145 matched no-activation control after two gates-open attempts ended at 0xDEAD: call the full
        # MiniDash CanActivateAbility virtual after 1/0->1/1, but compile out TryActivateAbilityByClass.
        'botfight-castalive-dash-mana10-canactivate' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=1')
        # S145 no-activation decomposition: call base CanActivate with a failure-tag output, then isolate
        # the remaining tag/K2/Loki gate. KBFCANACT stays truthy, so every TryActivate path is compiled out.
        'botfight-castalive-dash-mana10-candecomp' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=2')
        # S145 one-variable matched causal treatment: the engine's receiver is the MiniDash CDO,
        # so temporarily seed only its CurrentCharges 0->1, run no-activation eligibility queries,
        # then restore the shared CDO field to 0 before returning.
        'botfight-castalive-dash-mana10-candecomp-cdocharge1' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=2','-DKBFCDOCHARGES=1')
        # S147 activation-provenance arm: grant MiniDash with its canonical Ability3 InputID=5,
        # open the exact S145 CDO/base/full eligibility profile, then return through ProcessInternal.
        # The worker waits for a distinct later game-thread dispatch before printing READY, observes
        # the real Ability3 input path with raw samples, restores the shared CDO, and disarms. No
        # reflected ByClass, native handle wrapper, InternalTry, or InternalDo activation call.
        'botfight-castalive-dash-mana10-cdocharge1-naturalinput' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=2','-DKBFCDOCHARGES=1','-DKBFINPUTID=5','-DKBFNATURALINPUT=1','-DKBFNATURALMS=30000','-DKBFNATURALPRESETUPMS=60000')
        # ═════════════════════════════════════════════════════════════════════════════════════
        # ★★★★★ S147 MOVE 3 -- KBFBINDCENSUS: instrumented re-fly of flight 5.
        #   Same S147 CDO / gate / activation profile as the -naturalinput line above; the ONLY
        #   delta is -DKBFBINDCENSUS=1, which adds READ-ONLY sampling of the PlayerController's
        #   InputComponent -> ActionBindings TArray + FsDisarm phase-transition heartbeat.
        #   ZERO new activation calls, ZERO module-image writes. See the KBFBINDCENSUS block at
        #   the top of tutorial_launch.cpp and docs/s147-move3-flight1-PREREGISTERED.txt.
        #
        #   ⚠ Per-entry name matching ("Ability3", "Toggle Map") is compiled OUT until BOTH
        #     KBFBINDCENSUS_AB_OFF and KBFBINDCENSUS_STRIDE/NAMEOFF are pinned via -D. Set them
        #     once derived from live disassembly of UInputComponent::AddActionBinding. Without
        #     them the census still emits [BIND] metadata (ic non-null, TArray num/max shape).
        # ═════════════════════════════════════════════════════════════════════════════════════
        # AB_OFF = 0xd0 is [M] from offline disassembly of UInputComponent's InternalConstructor
        # at RVA 0x3616740: `mov qword ptr [rbx + 0xd0], rax` zero-init of ActionBindings.Data
        # (adversarially verified against merged14.dump.exe bytes; positive control at the
        # 4-qword thinner ctor 0x3616e30 confirms ActionBindings + AxisBindings are the FIRST
        # TWO TArrays in the class layout). Same value in stock UE 5.4 (0xa0..0x100 range).
        # STRIDE + NAMEOFF are not offline-derivable (FInputActionUnifiedDelegate size dominates
        # and isn't reflected); left unpinned so per-entry name matching stays compiled OUT and
        # the census emits only TArray metadata (num/max shape) -- which is enough for the H2a
        # discriminator (PAWN Num > 0 AND PC Num == 0 => BP never wired).
        'botfight-castalive-dash-mana10-cdocharge1-naturalinput-bindcensus' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=2','-DKBFCDOCHARGES=1','-DKBFINPUTID=5','-DKBFNATURALINPUT=1','-DKBFNATURALMS=30000','-DKBFNATURALPRESETUPMS=60000','-DKBFBINDCENSUS=1','-DKBFBINDCENSUS_AB_OFF=0xd0')
        # S146 first all-gates-open activation crossing: direct native handle-level TryActivateAbility,
        # only when Role==Authority and ActorInfo::IsLocallyControlled==true; allowRemote=false.
        # Reflected TryActivateAbilityByClass remains compiled out.
        'botfight-castalive-dash-mana10-cdocharge1-handleactivate' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=2','-DKBFCDOCHARGES=1','-DKBFHANDLEACT=1')
        # S146 localization control: identical state and native wrapper call, but pass the canonical
        # invalid FGameplayAbilitySpecHandle INDEX_NONE (-1), proven absent from the live Items census.
        'botfight-castalive-dash-mana10-cdocharge1-handlemiss' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xCE','-DKBFABIL=\"Ability3\"','-DKBFCHARGES=1','-DKBFGATES=1','-DKBFMANA=10','-DKBFCANACT=2','-DKBFCDOCHARGES=1','-DKBFHANDLEACT=1','-DKBFHANDLEMISS=1')
        # S148A isolated damage calibration: require the possessed hero's live Health set to have one
        # globally unique registration on its selected ASC, seed exact Health 1000/1000, call
        # AdjustHealth(-250) once, and require immediate plus distinct >=250 ms later Current=750
        # receipts. Exact reflected-property provenance; no legacy KBF arm.
        'botfight-damage-self-cal' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1')
        # S155 (2026-09-08): base self-cal + explicit AvatarActor bind BEFORE PREFLIGHT. Single
        # variable vs base (adds -DKBFBINDAVATAR=1). Same flags otherwise -- KBFARMS stays 0x00,
        # KBFSELFCAL stays 1, KBFOWNER defaults to 0 (carrier). S154 flight 2 REFUSED with
        # avatarBound=0 despite sp.dll's WireAbilitySystem running; this arm calls
        # InitAbilityActorInfo(asc,carrier,hero) at BfS148DoCalibration entry so PREFLIGHT can
        # finally reach the S153 AdjustHealth thunkExact path.
        'botfight-damage-self-cal-bindavatar' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1')
        # S156 (2026-09-08): S155 bind + explicit MaxHealth seed BEFORE PREFLIGHT. Single variable
        # vs -bindavatar (adds -DKBFSEEDMAXHEALTH=1). S155 flight 2 cleared 14 of 14 pre-existing
        # sub-blockers and refused with issues=0x200 (S148_ISSUE_MAX_HEALTH_BELOW_SEED alone); this
        # arm seeds target.maxHealthOff+0x8 pair to 0x447A0000/0x447A0000 with the same 8-byte
        # volatile write pattern the Health seed uses, so PREFLIGHT can reach CALL_ISSUED
        # AdjustHealth and finally exercise the S153 thunkExact fix live. Keep -bindavatar UNCHANGED
        # as the controlled negative -- attribution of any S156 null falls on the seed alone.
        'botfight-damage-self-cal-bindavatar-seedmax' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1')

        # S156-B (2026-09-08, marker tag [S189]): S156 bind+seedmax + N=1 additional back-to-back
        # AdjustHealth(-250) shot after the primary S148 cycle emits RESULT=SELF_DAMAGE_CALIBRATED.
        # Single-variable delta vs -bindavatar-seedmax (adds -DKBFPOSTSHOTS=1). First-flight
        # discipline: N=1 tests back-to-back dispatch mechanics on the same OnPI callback ONLY
        # (750->500, does NOT cross zero HP). Zero-crossing is a SEPARATE experiment (would need
        # -DKBFPOSTSHOTS=2 to reach 250 with the 300 HP safety floor still guarding, or an explicit
        # -DKBFPOSTSHOT_FLOORBITS override to fall below that -- neither should be flown until this
        # N=1 variant confirms mechanics + no FK-32). Primary shot's [S148] CALL_ISSUED / immediate
        # / RESULT= bytes and callCount=1 pinned record are UNCHANGED. Post-loop evidence lives
        # under distinct [S189] prefix so s148_damage_calibration_test.ps1 grep on [S148]
        # callCount=1 stays intact. Keep -bindavatar-seedmax UNCHANGED as controlled negative.
        'botfight-damage-self-cal-bindavatar-seedmax-postshots1' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=1')

        # S156-B N=2 (2026-09-08, marker tag [S189]): same as -postshots1 but requests 2 additional
        # AdjustHealth calls. Trajectory: primary 1000->750, SHOT_2 750->500, SHOT_3 500->250.
        # 300 HP safety floor is ABOVE post-SHOT_3 (250) but BELOW both pre-shot checks (750, 500),
        # so the floor stays armed but should not fire — a "floor armed but silent" outcome is the
        # correct success path here. Firing the floor would only happen if SHOT_2 landed unexpectedly
        # below 300 HP or if the primary shot's arithmetic diverged. static_assert(KBFPOSTSHOTS <= 2)
        # blocks N=3+ which would cross 0 HP and risk silent FK-32 via GameplayCue OnDeath (S158
        # precedent). Keep -postshots1 UNCHANGED as within-family controlled comparison
        # (N=1 vs N=2 differ in exactly the number of post-shots).
        'botfight-damage-self-cal-bindavatar-seedmax-postshots2' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=2')

        # S156-B N=2 floor-firing test (2026-09-08, marker tag [S189]): same as -postshots2 but
        # overrides KBFPOSTSHOT_FLOORBITS to 0x44160000u = 600.0f. Trajectory: primary 1000->750
        # (unchanged), SHOT_2 pre=750 > 600 -> fires normally 750->500, SHOT_3 pre=500 <= 600 ->
        # FLOOR_REACHED emits at PRECHECK -> POSTSHOTS_COMPLETE fired=1 requested=2 aborted=yes
        # reason=floor. Discriminator: floor in (500, 750] triggers on SHOT_3 only, preserving
        # SHOT_2's normal mechanics as within-run control. Purpose: code-cover + fire-test the
        # KBFPOSTSHOT_FLOORBITS branch that was armed-but-silent in -postshots1 and -postshots2.
        # Keep -postshots2 UNCHANGED as within-family controlled comparison (floor-silent).
        'botfight-damage-self-cal-bindavatar-seedmax-postshots2-floor600' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=2','-DKBFPOSTSHOT_FLOORBITS=0x44160000u')

        # S156-B heal test (2026-09-08, marker tag [S189]): N=1 post-shot with a POSITIVE delta of
        # +100.0f (0x42C80000u), replacing the default -250.0f. Trajectory: primary 1000->750
        # (unchanged), SHOT_2 pre=750 + 100 -> post=850. Well below MaxHealth 1000, so no cap
        # interaction — this is a clean "does positive delta work at all" test. observedDeltaHP
        # should be +100.00 exact, arithmeticOK=yes. Floor gate is armed at default 300 (pre 750
        # is above floor, so shot fires). Keeps -postshots1 as within-family control (same N=1
        # and floor, only delta sign flipped). A future overshoot/cap test would use +500 or
        # higher to push above MaxHealth.
        'botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal100' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=1','-DKBFPOSTSHOT_DELTABITS=0x42C80000u')

        # S156-B MaxHealth cap test (2026-09-08, marker tag [S189]): N=1 post-shot with +500.0f
        # (0x43FA0000u), overshoots MaxHealth. Trajectory: primary 1000->750 (unchanged), SHOT_2
        # pre=750 + 500 = 1250 requested. Two possible outcomes: (A) game clamps at MaxHealth 1000
        # -> observedDeltaHP=+250 NOT +500, arithmeticOK=NO, postHP=1000; (B) no clamp -> postHP=1250
        # (invariant violation), observedDeltaHP=+500 arithmeticOK=yes. Both outcomes measure
        # something specific about the game's health invariant enforcement. Floor at default 300
        # (pre 750 > 300, shot fires). Keeps -postshots1-heal100 as within-family control (same N=1
        # + positive delta; only magnitude and cap-crossing differ).
        'botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal500' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=1','-DKBFPOSTSHOT_DELTABITS=0x43FA0000u')

        # S189 Mana probe (2026-09-08, marker tag [S189] MANASHOT_*): after S148 primary AdjustHealth
        # completes (1000->750), fire ONE AdjustMana call on s_seeded.asc's LokiAttributeSet.Mana with
        # +50.0f delta (KBFPOSTSHOT_MANA_DELTABITS=0x42480000u default). KBFPOSTSHOTS=0 keeps the Health
        # post-loop stripped so this variant tests Mana in isolation. Expected outcomes: (a) if MaxMana
        # is 0 (likely on this NM_Standalone client with no server-authored GameState), AdjustMana runs
        # cleanly but Mana stays at 0 due to PreAttributeChange clamp -> MANASHOT_NO_OP; (b) if AdjustMana
        # writes bypass the clamp, Mana goes 0->50 -> MANASHOT_APPLIED; (c) if AdjustMana is stripped
        # (fold), MANASHOT_ADJUST_UNRESOLVED with the specific fold RVA in tailReason. Any outcome is
        # informative. Keeps parent -bindavatar-seedmax UNCHANGED as the byte-identical baseline.
        'botfight-damage-self-cal-bindavatar-seedmax-postshots-mana' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=0','-DKBFPOSTSHOT_MANA=1','-DKBFPOSTSHOT_MANA_DELTABITS=0x42480000u')
        # S189-SEED flight (2026-09-08, marker tag [S189-SEED] MAX_MANA_SEEDED + [S189] MANASHOT_APPLIED expected):
        # seed MaxMana=1000.0f (0x447A0000u -- S148_HEALTH_SEED_BITS parity) PLUS the 3 Mana-family compound
        # siblings BaseMaxMana=1000/MaxManaPerLevel=0/BonusMaxMana=0 BEFORE the KBFPOSTSHOT_MANA probe fires
        # its +50.0f AdjustMana call. Adversarial-verifier amendment vs a naive MaxMana-only seed: MaxMana on
        # ULokiAttributeSet is a COMPOUND-derived attribute (4 sibling UPROPERTIES per S189-seed workflow),
        # unlike MaxHealth on singleton LokiAttributeSetHealth. Seeding all 4 defeats any PostGameplayEffect
        # Execute recompute f(BaseMaxMana, MaxManaPerLevel*Level, BonusMaxMana). Single-variable delta vs the
        # parent -postshots-mana (adds -DKBFSEEDMAXMANA=1, seed value pinned). Trajectory: MaxMana 0/0 ->
        # seeded 1000/1000; Mana pre 0/0; +50 delta -> MANASHOT_APPLIED postMP=50/50 arithmeticOK=yes (was
        # MANASHOT_NO_OP on the parent because MaxMana=0). Keeps parent -postshots-mana UNCHANGED as the
        # byte-identical baseline; the MANASHOT_COMPOUND_PRE/POST diagnostic lines are only emitted under
        # KBFSEEDMAXMANA=1 so they cannot affect the parent's .text hash.
        'botfight-damage-self-cal-bindavatar-seedmax-mana-seedcompound1000' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=0','-DKBFPOSTSHOT_MANA=1','-DKBFPOSTSHOT_MANA_DELTABITS=0x42480000u','-DKBFSEEDMAXMANA=1','-DKBFSEEDMAXMANA_BITS=0x447A0000u')
        # S189-MV Flight 1 baseline: seed 6 movement attrs on ULokiAttributeSet + read GetMaxSpeed/
        # GetMaxAcceleration via CMC vtable dispatch BEFORE and AFTER the seed. Per S189-MV workflow
        # read-path agent [M]: getter reads from hero+0xF08 (NOT ASC.SpawnedAttributes[0]), and
        # hero+0xF08 = NULL on the KWIREGAS-wired player. EXPECTED OUTCOME: Branch B --
        # MOVEMENT_SEEDED exact readback on all 6 attrs, GETTER_BEFORE=0/0, GETTER_AFTER=0/0 (getter
        # can't see our seed). Confirms L6 read-path model live. Sets up the wiref08 variant as
        # the discriminator flip.
        'botfight-damage-self-cal-bindavatar-seedmax-mv-obs' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=0','-DKBFSEEDMOVEMENT=1','-DKBFOBSMOVGETTERS=1')
        # S189-MV Flight 2 discriminator flip: seed + wire hero+0xF08=spawnedSet0. If the L6 read-
        # path model is [M] and one pointer-write unlocks the movement wall, GETTER_AFTER should
        # return the SEEDED values (MaxSpeed=43FA0000 = 500.0f, MaxAccel=4732C800 = 45000.0f). If
        # BOTH getters return the seeded values, the S141 T3 movement wall's core question ("why
        # does Acceleration=0 -- the getter returns 0") is answered end-to-end via a single poke.
        # MaxAcceleration seed = 45000.0f (0x4732C800) not 50000.0f: per S189-MV workflow verifiers,
        # 50000 collides with engine Super's stock CMC UPROPERTY return on MOVE_Falling, making
        # Branch A indistinguishable from Super bypass. 45000 is non-stock and discriminates cleanly.
        'botfight-damage-self-cal-bindavatar-seedmax-mv-obs-wiref08' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=0','-DKBFSEEDMOVEMENT=1','-DKBFOBSMOVGETTERS=1','-DKBFWIREF08=1')
        # S189-MV-WASD F3 [M] SHIPPING ARM: full playability chain in one injection. Adds
        # KBFPOKEGRAVITY=1 on top of the -mv-obs-wiref08 variant so the KWIREGAS PLAYER falls
        # to the tutorial floor (Z=13240 -> Z=90.15), MovementMode transitions 3->1 Walking,
        # and WASD via natural input drives the mover at 500 uu/s cap = seeded MoveSpeed.
        # Zero .text write, one additional aligned 4-byte DATA write to CMC+GravityScale
        # (readback-verified in the [S189-MV] POKEGRAVITY marker line). F3 walking-Whold
        # 2026-09-09 measured 2300 uu horizontal displacement in ~3s. All prior gates
        # BYTE-IDENTICAL (KBFPOKEGRAVITY=0 defaults to dead-strip).
        'botfight-damage-self-cal-bindavatar-seedmax-mv-play' = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x00','-DKBFSELFCAL=1','-DKBFBINDAVATAR=1','-DKBFSEEDMAXHEALTH=1','-DKBFPOSTSHOTS=0','-DKBFSEEDMOVEMENT=1','-DKBFOBSMOVGETTERS=1','-DKBFWIREF08=1','-DKBFPOKEGRAVITY=1')
        # SITTING 4 -- WALL E full: spawn -> wire the bot's ASC -> AdjustHealth to KILL it. 0x31.
        'botfight-kill'       = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x31','-DKBFDMGTGT=1')
        # SITTING 5 -- the whole minimum loop attempt in one injection (all six steps). 0x3F.
        'botfight-full'       = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0x3F','-DKBFDMGTGT=1')

        # ---- S191 E4 PREDICATE (2026-09-10): a PLAYER ability kills a hostile target minion. ----
        # KBFARMS=0xC6 = K_BIND(0x02)+K_GRANT(0x04)+K_ALIVE(0x40)+K_GASATTR(0x80); NO K_ACTIVATE(0x08)
        # (a shim TryActivate dies+0xDEAD -- the NATURAL LMB casts), NO K_SPAWN/DAMAGE/WIREBOT (E4
        # spawns+seeds its OWN target via BfE4SpawnSeedTarget). KBFABIL="Ability1" (GS_Ronin_LightAttack1,
        # the LMB basic). KBFINPUTID=3 (LokiAbilityInputID::Ability1 -- [I,strong]: Ability3=5 [M] under
        # the standard None/Confirm/Cancel prefix => Ability1=3; verify live or via the fallback).
        # KBFNATURALINPUT=0: E4 gets out of the way via g_done+FsDisarm, not the S147 observation
        # machinery. FLIGHT: stage gft->fo->sp->this DLL; wait for [E4] E4_COMPLETE + [FS] disarm; then
        # scratchpad/s190/tools/send-lmb.ps1 (short <240ms tap = melee cone); watch minion Health -> 0.
        'e4'                  = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1')
        # E4 with the graded-consolation fallback armed: ALSO fires AdjustHealth(-250) on the seeded
        # minion (proves a direct write reduces its HP; NOT the natural-cast predicate). A real treatment
        # pair vs 'e4' -- KE4DIRECTGE moves the digest ('--dupes' clean).
        'e4-directge'         = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKE4DIRECTGE=1')
        # S191 E4 OPTION A: after K_GRANT + spawn+seed, call ASC.TryActivateAbilityByInputID(Ability1=3)
        # via the S55 primitive. Tests whether GAS's InputID→spec map is populated by our plain-GiveAbility
        # K_GRANT. Impl @ base+0x52971A0, S153 REAL. Ret=false => R-S191-h confirmed (Option B needed); ret=
        # true + HP drop => Option A wins (natural-cast half unlocked via direct callable). Fault/0xDEAD =>
        # WALL P proper on the InputID path. Also pre-reads GetAbilityByInputID(3) independently.
        # KE4DIRECTGE deliberately OFF so a minion HP drop is attributable to the real cast, not the fallback.
        'e4-a'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4A=1')
        # S191 E4 OPTION B (flown 2026-09-10, SUPERSEDED by `docs/s191-e4b-RESULT.md`):
        # after K_GRANT (plain GiveAbility populates Items but NOT the InputID→spec map, per R-S191-h1
        # [M] from E4A flight 1), ADDITIONALLY call the InputID-aware BP_AuthGiveAbilityWithInputID
        # via S55 (wrapper @ base+0x5294B50 — S153 graded REAL byte-verified prologue). Then re-fire
        # E4A's probe: if GetAbilityByInputID(3) returns non-null AND TryActivateAbilityByInputID(3)
        # returns true + drops minion HP, natural-cast half of E4 unlocked via a direct shim call.
        # ⇒ REFUTED [M, S191, `docs/s191-e4b-RESULT.md`]: retHandle=0 (INDEX_NONE), Items pre==post.
        # Wrapper at 0x5294B50 tail-calls impl at 0x13D4E60, which is a 9-BYTE STRIPPED STUB
        # (`c702ffffffff 488bc2 c3` = write 0xFFFFFFFF to outHandle, return outHandle*). New FK-1
        # register entry (R-S191-l); S153's sweep missed it because it grades WRAPPERS not IMPLS.
        # DO NOT re-flight expecting duplicate-detection or an unmet precondition to be the block.
        'e4-b'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4A=1','-DKBFE4B=1')
        # S191 E4 OPTION B2 (flown 2026-09-10, SUPERSEDED by `docs/s191-e4b-RESULT.md`):
        # same as e4-b but with K_GRANT (KBFARMS 0x04) DROPPED so BP_AuthGiveAbilityWithInputID is
        # the sole grant. Original hypothesis: E4B flight 1's refusal (retHandle=0, dItems=+0) was
        # UE detecting a duplicate-CDO grant against the K_GRANT-registered spec — with Items=0
        # pre-E4B the InputID-aware grant should succeed.
        # ⇒ REFUTED [M]: retHandle=0, dItems=+0 IDENTICAL to e4-b with Items pre=0. NOT duplicate
        # detection. Impl at 0x13D4E60 is a stripped stub that returns INDEX_NONE unconditionally
        # regardless of caller state. KBFARMS=0xC2 = K_BIND(0x02) + K_ALIVE(0x40) + K_GASATTR(0x80).
        'e4-b2'               = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC2','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4A=1','-DKBFE4B=1')
        # S191 E4 OPTION F: after K_GRANT + spawn+seed, call ULokiAbilitySystemComponent::
        # TryActivateAbilityBySourceObject(hero, true, hero.Ability1_UClass) via S55. Impl @
        # base+0x5297230 (S153 REAL). Third activation surface after ByClass (S147: lethal 0xDEAD on
        # MiniDash) and ByInputID (E4A F1: clean-false, InputID map empty). BySourceObject BYPASSES
        # the InputID map (R-S191-h escape hatch does NOT apply) and matches on spec.SourceObject =
        # hero (S191 F3 measured) so resolution is guaranteed. WALL-P grade [I] LIKELY LETHAL —
        # offline recon shows impl tail-calls 0x5544FB0 -> 0x44280E0 (a DIFFERENT downstream from
        # ByClass's 0x4480B30 InternalTryActivateAbility, so shared-downstream lethality is weakened
        # for this path). Pre-call marker preserves attribution if 0xDEAD fires. KBFARMS=0xC6
        # (K_BIND+K_GRANT+K_ALIVE+K_GASATTR, NO K_ACTIVATE). Mutually exclusive with KBFE4A/KBFE4B/
        # KE4DIRECTGE via #error guards so attribution is safe-by-construction against config
        # mistakes. Log tag: [E4F].
        'e4-f'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4F=1')
        # S191 E4 OPTION C: after K_GRANT + spawn+seed, call Comp_PlayerController_Abilities.
        # HandleAbilityActivation(byte AbilityID=3) via CallBPGuarded — the game's OWN BP dispatcher
        # that natural LMB flows through. Fourth activation surface after ByClass (S147: lethal
        # 0xDEAD on MiniDash), ByInputID (E4A F1: clean-false, InputID map empty), BySourceObject
        # (E4F F1: clean-false-FAST + 'invalid Handle' witness). HandleAbilityActivation is BP-
        # authored (no reflected native thunk), so uses CallBPGuarded not S55. PRE-FLIGHT BPDUMP
        # GATE PASSED [M, 2026-09-10]: HandleAbilityActivation dispatches to ubergraph entry 591;
        # entry-591 flow's CodeOffset jump targets are {576,722,838,1154} — NEITHER covers the two
        # TryActivateAbilityByClass sites (statements 2171/2472, S147 lethal). Those ByClass sites
        # dispatch from unrelated custom events on the same component. WALL-P grade [I] LIKELY
        # NON-LETHAL. Pre-call marker preserves attribution if 0xDEAD fires. Mutually exclusive
        # with KE4DIRECTGE/KBFE4A/KBFE4B/KBFE4F via #error guards. Even in the likely CLEAN-REFUSE
        # outcome, banks: BP-dispatcher shim-invocability [M receipt] + component resolution shape
        # (SCS UPROPERTY with _GEN_VARIABLE fallback) + coverage decryption for merged14 progression.
        # Log tag: [E4C].
        # KOUTPARMRET=1 (as with e4/e4-a/e4-b/e4-b2/e4-f/e4-directge) so if HandleAbilityActivation
        # has FUNC_HasOutParms(0x400000), CallBPGuarded's BuildOutParms includes CPF_ReturnParm-
        # flagged params (addressing docs/drop-sequence-status-s150.md §6.9 defect). If the
        # E4C_pre-flight marker shows HasOutParms=YES, this is the correct path; if =no, KOUTPARMRET
        # is a no-op for this arm.
        'e4-c'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4C=1')

        # e4-e-readonly (S191 E4 OPTION E, 2026-09-10, tag [E4E]): direct-offset poke of the K_GRANT'd
        # spec's NonReplicatedInstances TArray at spec+0x80/+0x88/+0x8C to unblock the 3-gate filter
        # at RVA 0x44C28E0 that GetAbilityByInputID (vtable slot 245 [+0x7A8] = iterator 0x4476F10)
        # calls after finding the matching spec on InputID==3. Design provenance: multi-agent
        # workflow adjudicated spec (16 refutations all VALID + adopted). The gate model derived
        # from workflow disasm + byte-verified from merged14 offline recon: (a) spec.Ability@+0x10
        # != NULL (K_GRANT sets), (b) [spec.Ability+0xEE] == 1 InstancedPerActor, (c) NonRep.Num@+0x88
        # > 0. Gate (c) is the block: K_GRANT populates Items but leaves NonRep empty. The poke:
        # Data <- (spec+0x10) (the spec's OWN Ability-field address on the game heap, R14 safety-
        # critical -- NEVER shim-static memory), Num <- 1, Max <- 1. Includes A->B->A restore so
        # disarm leaves the ASC in pre-poke state. Readback via GetAbilityByInputID(3) settles the
        # gate model: if post-poke returns spec.Ability, gate model is CONFIRMED [M] live.
        # TryActivateAbilityByInputID impl 0x5544F70 uses the SAME vtable slot 245 = SAME iterator
        # = SAME gate, so an unblocked gate for GetByInputID also unblocks TryByInputID's spec
        # resolution -- but the ACTIVATION call is COMPILE-GUARDED out (KBFE4E_ACTIVATE=0 default)
        # because 0x5544F70's tail-call target 0x5531920 is on a PAGE_NOACCESS in merged14 and
        # cannot be offline-verified to diverge from S147 lethal InternalTryActivateAbility
        # 0x4480B30. Write class = DATA on the K_GRANT'd spec (aligned qword + two aligned dwords),
        # readback-verified before and after. Mutually exclusive with KE4DIRECTGE/KBFE4A/KBFE4B/
        # KBFE4C/KBFE4F via #error guards. Log tag: [E4E].
        'e4-e-readonly'       = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4E=1')

        # e4-k (S191 E4 OPTION K, 2026-09-10, tag [E4K]): the MINIMAL live probe. Just calls
        # ASC.GetAbilityByInputID(3) via S55 with ZERO pokes and reads gate inputs before + after
        # the call to detect any mid-call mutation. Decisive test of the workflow adjudicator's
        # (wf_7e83ab1b) mechanism model: byte-verified 3-gate model predicts return = NonRep.Data[0]
        # or Rep.Data[0] given the current spec state; if runtime matches prediction, E4E's null
        # was a state-timing artifact (state at readback time differed from live-observed state);
        # if runtime returns NULL despite [+0xEE]==1 stable pre AND post, Gate 2 mid-call fail is
        # the leading hypothesis and KBFE4H (extended three-timestamp instrumented variant) is
        # the next arm. Class: CALL-ONLY read-only (only writes are shim-local g_pbuf + param).
        # Mutually exclusive with every other E4 activation surface via #error guards.
        'e4-k'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4K=1')

        # e4-m (S191 E4 OPTION M, 2026-09-10, tag [E4M]): raw-native-call discriminator for E4K's null.
        # Calls GetAbilityByInputID impl DIRECTLY (ImageBase+0x5526210) via a __fastcall function
        # pointer, bypassing the entire S55 CallNativeGuarded/FFrame framework. If E4M returns
        # non-null while E4K returned NULL on the same state, S55 has a defect specific to this
        # UFunction shape (UObject* return marshaling). If E4M ALSO returns NULL, S55 is exonerated
        # and the runtime genuinely returns NULL despite byte model predicting non-null. Class:
        # CALL-ONLY read-only.
        'e4-m'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4M=1')

        # e4-n (S191 E4 OPTION N, 2026-09-10, tag [E4N]): raw-native ACTIVATION discriminator + potential
        # E4 predicate resolver. E4M proved raw-native GetByInputID works when S55 lies. E4N tests the
        # activation twin: raw-native TryActivateAbilityByInputID(3) via ImageBase+0x5544F70. WALL-P
        # risk downgraded per pre-flight recon: (impl 0x5544F70 tail-JMPs 0x5531920) AND (0x5531920 is
        # NOW LIT in merged16) AND (0x5531920's disasm has ZERO reach to S147 lethal 0x4480B30 in its
        # first 240 bytes) AND (0x4480000 is STILL DARK in the live process). Signature: bool
        # __fastcall(ULokiAbilitySystemComponent*, uint8_t). If returns true AND minion HP drops,
        # E4 predicate MET. If FK-32, we've measured lethality via this new surface. Requires
        # KE4DIRECTGE=0 to keep HP attribution clean. Class: CALL-ONLY + one activation call.
        'e4-n'                = @('-DKRUNMODE=RM_BOTFIGHT','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBFARMS=0xC6','-DKBFABIL=\"Ability1\"','-DKBFINPUTID=3','-DKBFE4=1','-DKBFE4N=1')

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
        # ---- S137: THE bWantsPlayerState EXPERIMENT ---------------------------------------------
        # S136 left the AI-controlled pawn with PlayerState NULL on BOTH sides. The cause is one bit:
        #   AAIController::PostInitializeComponents 0x45D6D10
        #     0x45D6D1E  test byte [rbx+0x488],0x20   <- bWantsPlayerState
        #     0x45D6D25  je 0x45D6D4C                 <== GATE 1 (there are THREE; see the source)
        #     0x45D6D46  call [rax+0x888]             <- AController::InitPlayerState, slot 273
        # `botps` flies BOTH routes to it in ONE window, with a WITHIN-RUN control:
        #   spawn #1 (bit clear)  ->  poke CDO(AIControllerClass) bit  ->  spawn #2  ->  restore
        #   ->  ARM B: call InitPlayerState DIRECTLY on controller #1 (which needs no poke, because
        #       [M] InitPlayerState does not test the bit -- only GetNetMode()!=NM_Client + GetWorld()).
        # PRE-REGISTERED DISCRIMINATOR: ARM A gives ctl.PlayerState AND pawn.PlayerState non-null;
        # ARM B gives ctl.PlayerState non-null with pawn.PlayerState STILL NULL. Different signatures.
        # Risk: ARM A is one readback-verified, A-B-A-restored byte on a CDO (the S130 class).
        # ARM B is NOT call-only (SpawnActor + a write to controller+0x3C0). No .text write in either.
        'botps'               = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1')
        # READ-ONLY: spawn ONE AI pawn and read out L2/L3/L4 + all three gates + the precondition.
        # WRITES NOTHING. This is the clean re-measurement of the S136 baseline, and it is what makes
        # a later non-null attributable -- run it first if there is any doubt the world is staged.
        'botps-readonly'      = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x01')
        # ARM A ALONE (control spawn + poke + treatment spawn + restore; no direct call). Use this to
        # attribute a PlayerState to the CDO poke with nothing else in the window.
        'botps-arma'          = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x07')
        # ARM B ALONE (control spawn + direct InitPlayerState; the CDO is never touched). Use this if
        # ARM A's null needs separating from "InitPlayerState itself cannot succeed on this client".
        'botps-armb'          = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x09')
        # S137 FLIGHT 2, and this is the SHIPPING SHAPE of the experiment. Flight 1 REFUTED ARM A
        # (the CDO poke does not reach the instance -- UStruct::Link never puts a NATIVE class's
        # property into PostConstructLink, so FObjectInitializer::InitProperties never copies it),
        # so there is no reason to fly the poke again. This is spawn -> ARM B -> ARM C:
        #   bit0 spawn one AI pawn   bit3 direct InitPlayerState   bit4 APawn::SetPlayerState
        # It leaves BOTH sides of the AI pawn linked, the shape the player's own possession has.
        'botps-link'          = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x19')
        # Everything, including the now-refuted ARM A. Kept so the refutation is re-runnable.
        'botps-full'          = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x1F')
        # S137 ARM D -- the LOKI bot controller, via ONE pointer on the ENGINE APawn CDO.
        # A-B-A with THREE spawns: baseline -> poke -> treatment -> restore -> reversal. The third
        # spawn is what makes the restore a measurement rather than a promise.
        # bit0 off (ARM D does its own spawns), bit5 on.
        'lokibot'             = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x20')
        # ---- S138 ARM E: SpawnBot with a PREMADE controller -------------------------------------
        # The Loki bot pipeline has always died at SpawnBot -> MakeNewBotController -> the stripped
        # getter 0x55636BB. [M] a NON-NULL PremadeBotController short-circuits BEFORE that call
        # (0x556DA4F/0x556DAA1/0x556DAA4), so the getter is never reached. ARM D manufactures the
        # argument (an ALokiBotController possessing a hero) and ARM B gives it the PlayerState that
        # SpawnBot consumes from +0x3C0.  bit5 ARM D + bit6 ARM E.
        # ⚠ NOT call-only: 7 non-stack writes across FOUR objects. Six pre-flight gates read and
        #   REFUSE rather than guess. Two pre-registered page receipts: 0x5556D50 and 0x55667F0,
        #   both DARK in every image -- dumpimage after the flight either way.
        'spawnbot-premade'    = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x60')
        # S138 flight 7 -- ARM D (make the LokiBotController) + ARM F (drive the gate recompute).
        # NO ARM E: flight 6 already settled that SpawnBot's premade path runs, and leaving it out
        # keeps ARM F's result attributable to the recompute rather than to a second world change.
        # ⚠⚠ audit-S142 HAZARD: KBSPSARMS 0xA0 == gasattr-ctrl's 0x0A0, so 'driverecompute' now builds
        #    BYTE-IDENTICAL to 'gasattr-ctrl' (both 4465ebc4d7168c03). It is a DEAD S138 NAME -- do NOT
        #    A/B it against gasattr-ctrl (that would be a copy-against-itself, a burned run), and do NOT
        #    cite its recorded gate a2a952babfed256b as reproducible: that flown artifact is preserved
        #    ONLY in dumps/s140-arms-pre/ and no longer rebuilds. Use gasattr-ctrl as the canonical
        #    ARM-D+F control. (text_digest.py --dupes flags this pair.)
        'driverecompute'      = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0xA0')
        # READ-ONLY control for ARM F: ARM D runs, ARM F is compiled OUT (bit7 clear), so the gate
        # must NOT move. It converts an ARM F null from 'something is broken' into 'the call did
        # nothing'.  (== lokibot's flags; kept as a NAMED control so the intent is explicit.)
        'driverecompute-ctrl' = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x20')
        # S139 flight 4 -- ARM G: port the DS route's GAS recipe (ds_hybrid.cpp:2370-2430) onto the BOT.
        #   gasattr      = ARM D (make the LokiBotController) + ARM F (open the gate) + ARM G (the GAS block)
        #   gasattr-ctrl = the SAME arms with ARM G compiled out -- the single-variable control.
        # The PLAYER hero is deliberately untreated in both, as the within-run specificity control.
        'gasattr'             = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x1A0')
        'gasattr-ctrl'        = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x0A0')
        # S140 Tier 2 -- ARM H: the payload-poison / sentinel test. Does ULokiCMC::StartNewPhysics
        #   0x055C2430 actually execute? S139's answer rested on CMC+0x16C8, which S140 Tier 1
        #   showed is NOT a latch (cleared every frame by vtable disp 0xA50), so it reads 0 in
        #   every world and settles nothing. ARM H poisons the DURABLE payload at +0x16B0 instead.
        #   = gasattr (D+F+G) + bit9. ARM G stays IN so the bot's Acceleration is still non-zero;
        #   the question is what the movement chain does with it.
        'gasattr-sentinel'    = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x3A0')
        # ARM H with the GAS port compiled OUT: separates 'StartNewPhysics runs' from 'it runs
        # only because ARM G gave the bot a non-zero Acceleration'. Single variable vs the above.
        'sentinel-nogas'      = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x2A0')
        # ARM H2 -- the fast burst. Re-writes the Velocity sentinel every ~2 ms and watches the
        #   payload, to discriminate 'StartNewPhysics copied Velocity into +0x16B0' from 'some
        #   other routine zeroed both'. = gasattr-sentinel + bit10.
        'sentinel-burst'      = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x7A0')
        # ARM J -- THE FIXED-POINT TEST (S140 Tier 2 follow-up). ARM H's 2^-10 sentinel was chosen
        #   to be INERT; a verifier then showed a small non-zero Velocity can CONVERT A NO-WRITE
        #   INTO A WRITE, so what ARM H measured about Velocity may be its own artifact. ARM J
        #   writes a LARGE velocity ONCE (600 uu/s), on DIFFERENT AXES for bot and player, and
        #   watches whether it persists and whether the pawn TRANSLATES. It PERTURBS BY DESIGN --
        #   that is the point, and it is the opposite of ARM H. bit9 (H) + bit11 (J), NO bit10.
        'sentinel-big'        = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0xBA0','-DKSHSENTX=600.0','-DKSHPLRY=600.0')
        # ---- S141 TIER 3 ----------------------------------------------------------------------
        # ARM K -- TWO CLEAN ARMS IN ONE INJECTION, on DIFFERENT PAWNS and DIFFERENT AXES.
        #   BOT    : Velocity = (0, 0, -600.0).  A purely VERTICAL kick -- SizeSq2D == 0, i.e.
        #            maximally BELOW engine PhysFalling's 2-D gate at 0x035ED98E. S141 established
        #            offline [M] that the zeroing store there is `movups`, 16 BYTES over a 24-byte
        #            FVector-of-doubles, so the gravity-space Z SURVIVES. This tests that LIVE.
        #   PLAYER : ARM K1 (the same three GAS storages) + ARM K2 (GravityScale 0 -> 1.0, undoing
        #            `sp`'s own LIFT step) + ARM J's +Y 600 kick. Z answers "does gravity
        #            integrate", Y answers "does the CalcVelocity clamp still damp it" -- separate
        #            components, separately readable.
        # bits: 0x20 D | 0x80 F | 0x100 G | 0x200 H | 0x800 J | 0x1000 K2  = 0x1BA0
        'armk'                = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x1BA0','-DKSHSENTX=0.0','-DKSHSENTZ=-600.0','-DKSHPLRY=600.0','-DKSHPLRGRAV=1.0','-DKBSGASPLAYER=1')
        # ARM K CONTROL: identical except the BOT gets NO vertical kick (KSHSENTZ stays 0.0) and
        # the player gets NO GravityScale write (bit12 clear) and NO ARM K1. i.e. it is S140's
        # `sentinel-big` shape with a zero bot sentinel -- the arm that changes nothing new.
        'armk-ctrl'           = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0xBA0','-DKSHSENTX=0.0','-DKSHSENTZ=0.0','-DKSHPLRY=600.0')
        # ARM L -- THE AXIS A/B. One bot, one sitting, one variable: the kick AXIS.
        #   kick A HORIZONTAL (600,0,0) at t=0, observed by samples 0..2
        #   kick B VERTICAL   (0,0,-600) written by the sampler after sample 2, observed by 3..4
        # S140 T2 flight 3 sustained 500 on a horizontal kick; S141 ARM K zeroed on a vertical one.
        # This holds world/treatment/acceleration/object-age fixed and moves ONLY the axis.
        # Also reads AnalogInputModifier BY NAME -- the field ARM K's free-read list missed.
        # bits: 0x20 D | 0x80 F | 0x100 G | 0x200 H | 0x800 J | 0x1000 K2 | 0x2000 L = 0x3BA0
        'axisab'              = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x3BA0','-DKSHSENTX=600.0','-DKSHSENTZ=0.0','-DKSHAXBZ=-600.0','-DKSHPLRY=600.0','-DKSHPLRGRAV=1.0','-DKBSGASPLAYER=1')
        # ARM L control: identical, but kick B is the SAME axis as kick A (horizontal), so a
        # difference between samples 0..2 and 3..4 cannot be attributed to the axis.
        'axisab-ctrl'         = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x3BA0','-DKSHSENTX=600.0','-DKSHSENTZ=0.0','-DKSHAXBZ=0.0','-DKSHPLRY=600.0','-DKSHPLRGRAV=1.0','-DKBSGASPLAYER=1')
        # ==== S189-BOT (2026-09-09) -- floor-spawn ONE Loki bot on the tutorial floor and let its OWN AI
        #   wander drive it with NO velocity kick; the player is wired +0xF08-only to the shared CDO
        #   attribute set + GravityScale 0->1 (K2). Design: workflow wf_9b8a8446-b39 (6 Understand +
        #   1 Design + 3 adversarial Verify + 1 Adjudicate). Every new knob defaults to the FLOWN
        #   behaviour, so botai/gasattr/gasattr-ctrl/play/-mv-play/-seedmax must rebuild BYTE-IDENTICAL
        #   to the 2026-09-09 re-baseline (scratchpad/s189-bot/evidence/00-before-state-digests.txt);
        #   axisab/armk/sentinel-* MOVE (the K1 mask `if` + sampler statics live in their compiled block).
        # bits: 0x20 D | 0x80 F | 0x100 G | 0x200 H (poison + worker sampler; ZERO bot sentinel)
        #       | 0x1000 K2 | 0x4000 M (velocity-gated fallback kick from the sampler) = 0x53A0.
        #   NO 0x800 (ARM J with KSHPLRY=0 would ZERO a walking player's Velocity), NO 0x2000 (ARM L).
        #   Seed 487.0f (0x43F38000) is NON-STOCK (R-S189-MV-a): a bot cap in the 487 band cannot be a
        #   stock 500/600. MaxAcceleration stays 50000 == engine Super and is NOT a discriminator.
        'botplay-floor'       = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x53A0','-DKSHSENTX=0.0','-DKSHSENTZ=0.0','-DKSHPLRGRAV=1.0','-DKBSGASPLAYER=1','-DKBSGASPLAYERMASK=0x2','-DKBSGASMOVESPEED=487.0f','-DKBSLBSKIPCTRL=1','-DKBSAIFLOOR=1','-DKBSAILOC_X=1356.0','-DKBSAILOC_Y=-409.0','-DKBSAILOC_Z=90.15','-DKSHSAMPLEN=40','-DKSHSAMPLEMS=1000','-DKSHFALLBACKAT=8','-DKSHFALLBACKMAXV=5.0','-DKSHFALLBACKX=600.0','-DKBSGETTERRCPT=1')
        # PRIMARY FLIGHT VARIANT = botplay-floor + ARM J (0x800) with a 1 uu/s -Y PLAYER seed. A player at
        #   EXACT rest hovers after GravityScale 0->1 for an unknown-trigger, variable time (ship-f1: the
        #   fall began ~115 s after the poke; F3: <=45 s) and the armed window is only ~150 s; a horizontal
        #   velocity breaks the rest fixed point immediately (S141 T3 armk/axisab [M] at 600 uu/s). 1 uu/s
        #   is 487x below the cap and cannot masquerade as walking (control C1: no player write >= 2 uu/s).
        'botplay-floor-tinykick' = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x5BA0','-DKSHSENTX=0.0','-DKSHSENTZ=0.0','-DKSHPLRY=-1.0','-DKSHPLRGRAV=1.0','-DKBSGASPLAYER=1','-DKBSGASPLAYERMASK=0x2','-DKBSGASMOVESPEED=487.0f','-DKBSLBSKIPCTRL=1','-DKBSAIFLOOR=1','-DKBSAILOC_X=1356.0','-DKBSAILOC_Y=-409.0','-DKBSAILOC_Z=90.15','-DKSHSAMPLEN=40','-DKSHSAMPLEMS=1000','-DKSHFALLBACKAT=8','-DKSHFALLBACKMAXV=5.0','-DKSHFALLBACKX=600.0','-DKBSGETTERRCPT=1')
        # AI-ATTRIBUTION CONTROL: identical to botplay-floor but ARM F (0x80) compiled out, so the wander
        #   gate stays closed. Prediction: the bot does NOT translate before the fallback; after the kick
        #   an undriven Walking pawn STOPS within ~0.3 s (BrakingDecelerationWalking 2048), one heading
        #   only. bits 0x5320.
        'botplay-floor-noai'  = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x5320','-DKSHSENTX=0.0','-DKSHSENTZ=0.0','-DKSHPLRGRAV=1.0','-DKBSGASPLAYER=1','-DKBSGASPLAYERMASK=0x2','-DKBSGASMOVESPEED=487.0f','-DKBSLBSKIPCTRL=1','-DKBSAIFLOOR=1','-DKBSAILOC_X=1356.0','-DKBSAILOC_Y=-409.0','-DKBSAILOC_Z=90.15','-DKSHSAMPLEN=40','-DKSHSAMPLEMS=1000','-DKSHFALLBACKAT=8','-DKSHFALLBACKMAXV=5.0','-DKSHFALLBACKX=600.0','-DKBSGETTERRCPT=1')
        # PLAN B: the bot-only floor arm as a 5TH manual-map AFTER the flown -mv-play (player chain
        #   untouched: KBSGASPLAYER=0, no K2, no J). Disjoint sets: player 500 (own spawnedSet0) vs bot
        #   487 (CDO set). bits 0x20|0x80|0x100|0x200|0x4000 = 0x43A0.
        'botplay-floor-5th'   = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x43A0','-DKSHSENTX=0.0','-DKSHSENTZ=0.0','-DKBSGASMOVESPEED=487.0f','-DKBSLBSKIPCTRL=1','-DKBSAIFLOOR=1','-DKBSAILOC_X=1356.0','-DKBSAILOC_Y=-409.0','-DKBSAILOC_Z=90.15','-DKSHSAMPLEN=40','-DKSHSAMPLEMS=1000','-DKSHFALLBACKAT=8','-DKSHFALLBACKMAXV=5.0','-DKSHFALLBACKX=600.0','-DKBSGETTERRCPT=1')
        # ZERO-NEW-LOGIC contingency (design A: the S140 sentinel-big shape minus the player kick, with the
        #   487 seed). Air spawn, three ARM-D spawns, 600 uu/s bot kick at arm time.
        'botwalk'             = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x3A0','-DKSHSENTX=600.0','-DKSHSENTZ=0.0','-DKBSGASMOVESPEED=487.0f')
        # ===== S190 TRACK D: spawn a floor bot -> seed its Health -> AdjustHealth it to 0 = KILL. =====
        # KBSPSARMS=0x120 = ARM D (0x20: floor-spawned, LokiBotController-possessed, PlayerState-
        # provisioned bot in g_psLbPawn[1]) + ARM G (0x100: borrow the CDO's ASC/AttributeSet/
        # AttributeSetHealth into bot+0xF00/+0xF08/+0xF10 -- the [M] S139 bot-GAS wiring; WireAbilitySystem
        # canNOT be used, S190 F1 measured it fail at carrier-spawn). KBSLBSKIPCTRL=1 spawns ONLY the
        # treatment. No ARM H, no KSHSAMPLEN sampling, so KBFTRACKD's seed+kill fires promptly (minimal
        # FK-32 surface). KBFTRACKD reads bot+0xF00 (ASC) + bot+0xF10 (Health set), seeds Health+MaxHealth
        # =1000/1000, and calls the S156-B VALIDATED AdjustHealth on the BOT's own ASC (bypasses WALL E).
        # FLY -nonlethal FIRST (delta -250 -> 750, no zero-cross), then -kill (delta -5000 -> 0) under crashwatch.
        'trackd-kill'         = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x20','-DKBSLBSKIPCTRL=1','-DKBSAIFLOOR=1','-DKBSAILOC_X=1356.0','-DKBSAILOC_Y=-409.0','-DKBSAILOC_Z=90.15','-DKBFTRACKD=1','-DKBFTRACKD_DELTABITS=0xC59C4000u')
        # WITHIN-FAMILY controlled comparison: identical to trackd-kill except delta -250 (0xC37A0000u)
        # lands the bot at 750/750 with NO zero-cross -- validates provision+borrow+seed+validated-resolve+
        # arithmetic before the lethal build risks the OnDeath chain.
        'trackd-kill-nonlethal' = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x20','-DKBSLBSKIPCTRL=1','-DKBSAIFLOOR=1','-DKBSAILOC_X=1356.0','-DKBSAILOC_Y=-409.0','-DKBSAILOC_Z=90.15','-DKBFTRACKD=1','-DKBFTRACKD_DELTABITS=0xC37A0000u')
        # READ-ONLY control: runs ARM D + every ARM E pre-flight gate and then makes NO SpawnBot
        # call (bit6 clear). Any world change under THIS build would mean the gates are not read-only.
        'spawnbot-readonly'   = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1','-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1','-DKBSPSARMS=0x60','-DKBSSBCALL=0')
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
