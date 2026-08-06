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
    'catalog_store_fix' = @{
        'noscan' = @('-DKNOSCAN=1')
        # S111 arm E1/E2/E3 bisect. Each is noscan (= arm E) MINUS one behaviour, so each is a
        # one-variable step down from arm E. CONTROLS ONLY — none of these is a candidate.
        'noscan-noveh'  = @('-DKNOSCAN=1','-DKNOVEH=1')   # E1: no SnapshotModules + no VEH
        'noscan-noslot' = @('-DKNOSCAN=1','-DKNOSLOT=1')  # E2: no BuildStub + no slot-110 vtable write
        'noscan-nojz'   = @('-DKNOSCAN=1','-DKNOJZ=1')    # E3: no .text jz-NOP
    }
    'tutorial_launch' = @{
        # RunMode switch, tutorial_launch.cpp:93. Default when KRUNMODE is unset is RM_CHEATSPAWN.
        'fo'         = @('-DKRUNMODE=RM_FORCEOPEN')
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
        'play-novtguard'  = @('-DKRUNMODE=RM_PLAY','-DKVTGUARD=0')               # -1 dim: view-target guard OFF
        'play-nogcroot'   = @('-DKRUNMODE=RM_PLAY','-DKGCROOT=0')                # -1 dim: GC-root guard OFF
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
