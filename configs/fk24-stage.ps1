<#
  fk24-stage.ps1 — stage the tutorial world and inject a probe/candidate DLL into it.

  WHY THIS EXISTS (S108, 2026-08-04)
  ----------------------------------
  The S107 recipe (docs/next-session-prompt-s108.md §0) needs a HUMAN to press
  PLAY -> TUTORIALS -> BASIC TRAINING -> START before anything can be injected, because
  RM_PLAY and RM_SPAWNPOSSESS are CONTINUATION modes: they attach to an already-running
  tutorial and `return 0` before the force-open block, so `-Hook <play dll>` alone cannot work.

  The button press has exactly ONE backend effect: POST /party/parties/{id}/startSoloMode sets
  playerState.SoloMode, and handleCoreGamePlayer's gate is `forceTutorialMatch || SoloMode != ""`.
  So setting `forceTutorialMatch = true` in server/internal/interactive/interactive.go substitutes
  for the press exactly, and the client parks itself with nobody at the keyboard. That flag MUST be
  true for this script to fire — it checks, and refuses to run if the backend is not serving a match.

  ORDER IS LOAD-BEARING, and every step is gated on MEASURED evidence rather than a fixed sleep:
    1. tutorial_launch_fo.dll   force-opens LVL_Tutorial into the parked match model
    2. gft_ready_fix.dll        game-feature-toggle ready marker
    3. tutorial_launch_sp.dll   spawn + possess  (ONE-SHOT, no retry loop -- inject only once the
                                world is genuinely up, or you get [SP] gm=0x0 pc=0x0 and the run is dead)
    4. <-Probe>                 the play/probe build under test

  ⚠ docs/tutorial-launch-marker.txt is opened CREATE_ALWAYS, so EVERY injection TRUNCATES it (FK-25).
    This script copies it off after each stage into docs/fk24-stage-<Label>-<n>-<shim>.txt so no
    stage's output is lost, and that is the only reason the earlier stages' lines survive at all.

  Read-only w.r.t. the game otherwise. Run from an ELEVATED PowerShell.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Probe,       # path to the DLL under test (usually build\tutorial_launch_play*.dll)
  [string]$Label = "run",                           # tag for the copied-off marker files
  [int]$MinUptimeSec   = 110,                       # login+lobby settle before we touch anything
  [int]$WaitProcSec    = 300,                       # how long to wait for the game to appear
  [int]$WaitParkedSec  = 420,                       # how long to wait for the parked match model
  [int]$WaitWorldSec   = 180,                       # how long to wait for LVL_Tutorial after force-open
  [switch]$SkipProbe,                               # stage the world only (fo+gft+sp), inject nothing else
  [int]$InjectGapSeconds = 20,                      # S109: MINIMUM seconds between successive manual-maps.
                                                    # Evidence-gate waits count toward it, so this only
                                                    # sleeps the shortfall. 20 matches the new default in
                                                    # inject-secondaries.ps1. Pass 5 to reproduce the old
                                                    # gft->fo spacing. See docs/s109-dump-forensics.md 18-20.
  [switch]$AllowStale,                              # inject anyway when a shim's .text differs from build\
  [string]$Fo = ""                                  # S112: alternate force-open DLL (e.g. the
                                                    # `fo-nologinvt` arm, which drops the slot-285
                                                    # `.rdata` vtable write). Empty = the deployed
                                                    # tutorial_launch_fo.dll, i.e. unchanged behaviour.
)

$ErrorActionPreference = 'Stop'
$repo    = Split-Path -Parent $PSScriptRoot
$inject  = Join-Path $repo 'tools\inject\inject.exe'
$shimDir = Join-Path $repo 'tools\sigbypass-mod'
$docs    = Join-Path $repo 'docs'
$lokiLog = Join-Path $env:LOCALAPPDATA 'SUPERVIVE\Saved\Logs\Loki.log'
$marker  = Join-Path $docs 'tutorial-launch-marker.txt'
$capture = Join-Path $docs 'capture.log'

function Say($m){ Write-Host "[stage] $m" }

# ---- S111: THE DEPLOYED-vs-BUILD STALENESS GUARD -------------------------------------------------
# `build.ps1` writes to tools\sigbypass-mod\build\, but this script injects the DEPLOYED copies in
# tools\sigbypass-mod\. Those are two tiers on purpose (build output vs blessed artifact) -- but
# nothing enforced the relationship, so they drifted silently and you could BUILD A FIX, RUN THE
# STANDARD STAGING, AND TEST THE OLD BINARY.
#
# MEASURED 2026-08-05 across the 142 deployed DLLs: 64 `.text`-identical to build, 68 with no build
# counterpart at all, and 10 DRIFTED -- including `tutorial_launch_sp.dll` (root d0d3cc140c4f4286 vs
# build 4285c0dd22ae9976, i.e. missing KGASSTORAGE) and, worse, `tutorial_launch_play.dll`, whose
# deployed `.text` is a67239a0d83d9300 -- the hash CLAUDE.md identifies as `play-statictest`, the
# S108b diagnostic that faulted every run and disabled anim swapping.
#
# Compare `.text` ONLY. A whole-file compare says all three staging shims differ when two of them are
# functionally identical (the delta is PE-header/debug bytes), which is the project's standing
# "diff .text, never whole-file" rule -- here it is the difference between one real problem and three.
function Get-TextHash([string]$path){
  if(-not (Test-Path $path)){ return $null }
  $d = [IO.File]::ReadAllBytes($path)
  $pe = [BitConverter]::ToInt32($d, 0x3C)
  $ns = [BitConverter]::ToUInt16($d, $pe + 6)
  $opt= [BitConverter]::ToUInt16($d, $pe + 20)
  $off = $pe + 24 + $opt
  for($i = 0; $i -lt $ns; $i++){
    $s = $off + $i * 40
    $nm = ([Text.Encoding]::ASCII.GetString($d, $s, 8)).TrimEnd([char]0)
    if($nm -eq '.text'){
      $sz = [BitConverter]::ToInt32($d, $s + 16)
      $pr = [BitConverter]::ToInt32($d, $s + 20)
      $sha = [Security.Cryptography.SHA256]::Create()
      $h = $sha.ComputeHash($d, $pr, $sz)
      return (($h | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0,16)
    }
  }
  return $null
}
# Refuses by default: a silent wrong-binary test costs an armed window, and armed windows are the
# scarce resource here. -AllowStale overrides when the older artifact is genuinely what you want.
function Assert-Fresh([string]$dll){
  $bld = Join-Path (Split-Path -Parent $dll) ('build\' + (Split-Path -Leaf $dll))
  if(-not (Test-Path $bld)){ return }                       # historic variant, nothing to compare
  $a = Get-TextHash $dll; $b = Get-TextHash $bld
  if($null -eq $a -or $null -eq $b -or $a -eq $b){ return }
  $msg = ("STALE DEPLOYED SHIM: {0}`n" -f (Split-Path -Leaf $dll)) +
         ("           deployed .text {0}`n" -f $a) +
         ("           build\   .text {0}`n" -f $b) +
          "           build.ps1 wrote a newer binary than the one about to be injected."
  if($AllowStale){ Say "WARNING - $msg"; Say "           (-AllowStale given; injecting the deployed copy anyway)" }
  else {
    Say "ABORT - $msg"
    Say "           Fix: copy the build\ artifact over the deployed one, or pass -AllowStale,"
    Say "           or point -Probe directly at the build\ path."
    throw "stale shim: $dll"
  }
}

# Loki.log is held open by the game with a share mode we must match, so Get-Content can hard-fail
# mid-run. Read through an explicit FileShare::ReadWrite handle instead.
function Read-Locked([string]$path,[int]$tailBytes = 400000){
  if(-not (Test-Path $path)){ return '' }
  try{
    $fs = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{
      if($fs.Length -gt $tailBytes){ [void]$fs.Seek(-$tailBytes,[IO.SeekOrigin]::End) }
      $sr = New-Object IO.StreamReader($fs)
      return $sr.ReadToEnd()
    } finally { $fs.Dispose() }
  } catch { return '' }
}

function Wait-For([string]$what,[int]$timeoutSec,[scriptblock]$test){
  $t0 = Get-Date
  while(((Get-Date) - $t0).TotalSeconds -lt $timeoutSec){
    if(& $test){ Say "$what -> OK ($([int]((Get-Date)-$t0).TotalSeconds)s)"; return $true }
    # ★ S112 LIVENESS GUARD. Every gate below polls a LOG or a MARKER, and a dead process writes
    #   neither -- so when the game dies mid-staging (measured: frequently, within ~1 s of the map
    #   load) the gate cannot tell "not yet" from "never again" and burns its whole timeout. Worse,
    #   `Stage-Inject` discards inject.exe's exit code, so an injection into an exited PID logs
    #   `FAILED: OpenProcess: The parameter is incorrect.` and the run sails on to wait 120 s for a
    #   marker line nothing is alive to write. Fail fast instead; the caller's abort paths are
    #   already correct, they were just being reached three minutes late.
    if($script:gamePid -and -not (Get-Process -Id $script:gamePid -ErrorAction SilentlyContinue)){
      Say "$what -> *** GAME PROCESS GONE after $([int]((Get-Date)-$t0).TotalSeconds)s -- aborting the wait ***"
      return $false
    }
    Start-Sleep -Seconds 3
  }
  Say "$what -> *** TIMEOUT after ${timeoutSec}s ***"
  return $false
}

$foDll = if($Fo){ (Resolve-Path $Fo).Path } else { Join-Path $shimDir 'tutorial_launch_fo.dll' }
foreach($p in @($inject,$foDll,
                (Join-Path $shimDir 'gft_ready_fix.dll'),
                (Join-Path $shimDir 'tutorial_launch_sp.dll'))){
  if(-not (Test-Path $p)){ throw "missing required file: $p" }
}
if(-not $SkipProbe){
  if(-not (Test-Path $Probe)){ throw "probe DLL not found: $Probe" }
  $Probe = (Resolve-Path $Probe).Path
}

# ---- PRE-FLIGHT: the backend must actually be arming a match, or the client never parks and the
#      force-open reverts to the lobby in ~300 ms (the S63/S64 failure this whole route depends on
#      avoiding). Measure it rather than assuming the source flag was rebuilt into the binary.
Say 'pre-flight: is ags serving an armed match?'
$armed = $false
try{
  $me = (Invoke-WebRequest -Uri 'http://127.0.0.1:8080/revival/admin/state' -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue)
} catch { }
foreach($pid_ in @('9b9d2c887e2524f918e383a895f2f1c2')){
  try{
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/core-game/players/$pid_" -UseBasicParsing -TimeoutSec 5
    $j = $r.Content | ConvertFrom-Json
    Say ("  /core-game/players -> MatchID='{0}' Version={1}" -f $j.MatchID,$j.Version)
    if($j.MatchID){ $armed = $true }
  } catch { Say "  /core-game/players query failed: $($_.Exception.Message)" }
}
if(-not $armed){
  throw "ags is NOT arming a match (MatchID empty). Set forceTutorialMatch=true in server/internal/interactive/interactive.go, rebuild ags, restart it. Without this the client never parks and force-open reverts."
}

# ---- 1. the game process
Say 'waiting for game process...'
$proc = $null
if(-not (Wait-For 'game process' $WaitProcSec { $script:proc = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue | Select-Object -First 1; $null -ne $script:proc })){ exit 2 }
$script:gamePid = $proc.Id
$gamePid = $script:gamePid
$start   = $proc.StartTime
Say "game PID=$gamePid started=$start"

# ---- 2. the PARKED state. Three independent signals, all required:
#         (a) the UI is up          -> Loki.log 'TryUIReady SUCCESS'
#         (b) the match was fetched -> capture.log GET /core-game/matches AFTER this process started
#         (c) enough uptime for login+lobby to settle
$parked = Wait-For 'parked match model (uiready + match fetched + uptime)' $WaitParkedSec {
  $up = ((Get-Date) - $start).TotalSeconds
  if($up -lt $MinUptimeSec){ return $false }
  $log = Read-Locked $lokiLog
  if($log -notmatch 'TryUIReady SUCCESS'){ return $false }
  if(Test-Path $capture){
    $cap = Read-Locked $capture 200000
    if($cap -notmatch 'core-game/matches'){ return $false }
  }
  return $true
}
if(-not $parked){ Say 'proceeding anyway is NOT safe -- aborting'; exit 3 }
Say ("uptime={0}s" -f [int](((Get-Date) - $start).TotalSeconds))

# ★ MINIMUM INJECTION GAP (S109, 2026-08-05). Injecting DLLs in quick succession is what provokes
#   the protector's `runtime.dll+1` / `+0x205D` kills. MEASURED on the menu route: a 3 s gap between
#   manual-maps gave 1 death per 43 s; >=10 s gaps gave 1 per 3,054 s -- a 71x reduction, P = 8.6e-5.
#   docs/s109-dump-forensics.md sections 18-20.
#
#   This stager was NOT a uniform burst, so it needed measuring rather than assuming. Real spacing:
#       gft -> fo     ~5 s   (Stage-Inject's Sleep 2 + the Sleep 3 below)  <-- LETHAL REGIME
#       fo  -> sp     19 s   (19/19/19/19/19 across five S108 runs)        <-- already safe
#       sp  -> probe  7-17 s (17/15/17/7)                                  <-- borderline
#   ⚠ Do NOT try to re-derive those from docs/fk24-stage-*-N-*.txt mtimes: Copy-Item preserves the
#   SOURCE file's LastWriteTime, and step 1 copies a stale tutorial-launch-marker that gft never
#   writes -- which is why that delta reads as +210 s or even +41,742 s. Steps 2-4 are real.
#
#   We enforce a MINIMUM gap measured from the previous injection, so the existing evidence gates
#   (world-load, [SP] done) COUNT TOWARD IT and we only sleep the remainder. That buys the safe
#   spacing for ~15-30 s of added staging rather than ~50 s of unconditional sleeps -- which matters,
#   because the code-integrity kill lands ~285 s in and every second spent staging is armed-window
#   budget spent. The evidence gates themselves are untouched; they are load-bearing (see below).
$script:lastInjectAt = $null
function Stage-Inject([string]$dll,[int]$n,[string]$tag){
  if($null -ne $script:lastInjectAt){
    $since = [int]((Get-Date) - $script:lastInjectAt).TotalSeconds
    $need  = $InjectGapSeconds - $since
    if($need -gt 0){ Say ("    spacing: {0}s since last inject, waiting {1}s more (min gap {2}s)" -f $since,$need,$InjectGapSeconds); Start-Sleep -Seconds $need }
    else           { Say ("    spacing: {0}s since last inject, min gap {1}s already satisfied" -f $since,$InjectGapSeconds) }
  }
  Assert-Fresh $dll
  Say ">>> inject $tag"
  & $inject mmap $gamePid $dll 2>&1 | ForEach-Object { Say "    $_" }
  $script:lastInjectAt = Get-Date
  Start-Sleep -Seconds 2
  $dst = Join-Path $docs ("fk24-stage-{0}-{1}-{2}.txt" -f $Label,$n,$tag)
  if(Test-Path $marker){ Copy-Item $marker $dst -Force; Say "    marker -> $(Split-Path -Leaf $dst)" }
}

# ---- 3. gft_ready_fix FIRST, then force-open, then WAIT for the world before the one-shot spawn+possess.
#
# ★ S108 ORDER CORRECTION (MEASURED 2026-08-04, run wp2r1). The documented recipe is fo -> gft -> sp,
#   and S107 got away with it only because it injected all four back to back, so gft landed DURING the
#   5.7 s LoadMap and was resident before the tutorial GameState came up. This script originally
#   inserted a world-gate between fo and gft -- which delayed gft past LoadMap, and the run died ~60 ms
#   after "LogLokiGameMode: Display: Client is ready to play", with the log full of
#   "ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready" and NO UE crash dump
#   (Sentry's crashpad took the process, so it is invisible to the dump census -- FK-25 class).
#   gft_ready_fix re-applies its bit every ~2 s for the whole session and needs no world, so injecting
#   it BEFORE the force-open removes the race entirely rather than merely winning it by luck.
Stage-Inject (Join-Path $shimDir 'gft_ready_fix.dll') 1 'gft'
Start-Sleep -Seconds 3
Say ("force-open DLL: {0}" -f (Split-Path -Leaf $foDll))
Stage-Inject $foDll 2 'fo'

# ★ Gate on the LOAD COMPLETING, not on the string 'LVL_Tutorial' -- the force-open's own console
#   command ('open LVL_Tutorial?game=...') contains that substring and is echoed to the log, so the
#   old test passed 3 s in, before the map had loaded at all. Question the key you grepped for.
$worldUp = Wait-For 'LVL_Tutorial load complete' $WaitWorldSec {
  $log = Read-Locked $lokiLog
  $log -match 'Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial'
}
if(-not $worldUp){ Say 'no tutorial world -> injecting sp now would be a wasted one-shot. ABORTING.'; exit 4 }
Start-Sleep -Seconds 8   # let the gamemode finish init before the one-shot resolve

Stage-Inject (Join-Path $shimDir 'tutorial_launch_sp.dll') 3 'sp'

# ---- 4. the DLL under test.
#
# ★ S108 GATE (MEASURED 2026-08-04, run wp2r2). A fixed 5 s wait after `sp` is NOT enough: the probe
#   went in while spawn+possess was still running, RM_PLAY found no possessed hero, printed
#   "[PL] ResolveWakeMove failed (no possessed hero -- spawn+possess first) -> abort" and aborted
#   WITHOUT arming. RM_PLAY's resolve is one-shot, so that silently wasted the launch. Gate on sp's own
#   completion line instead. Read the marker BEFORE injecting -- the injection truncates it (FK-25).
if(-not $SkipProbe){
  $spDone = Wait-For '[SP] done step=4 (hero possessed)' 120 {
    if(-not (Test-Path $marker)){ return $false }
    $mk = Read-Locked $marker 200000
    ($mk -match '\[SP\]\s+done step=4') -and ($mk -match 'spawnedPawn=0x[0-9A-Fa-f]+')
  }
  if(-not $spDone){ Say 'spawn+possess never completed -> RM_PLAY would abort. ABORTING.'; exit 5 }
  Start-Sleep -Seconds 3
  Stage-Inject $Probe 4 ('probe-' + [IO.Path]::GetFileNameWithoutExtension($Probe))
  Say 'probe injected; armed window begins'
} else {
  Say 'SkipProbe: world staged, nothing further injected'
}
Say 'stage complete'
