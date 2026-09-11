<#
  fk7-ab-run.ps1 -- ONE armed window of the FK-7 A/B, end to end, hands-free.

  WHY THIS EXISTS (S112, 2026-08-07)
  ----------------------------------
  S111 measured that a STANDING `.text` write is what makes the anti-tamper protector kill the
  process (patch standing 11/12 vs no patch 0/5, p = 0.00097), and that a PERMANENT patch to heap
  bytecode is free (0/9). `tutorial_launch.cpp:6511-6513` (RM_PLAY) installs a 5-byte `.text` patch
  at ProcessInternal and holds it for 600 s -- `g_done` is never set in RM_PLAY -- so EVERY FK-7
  sitting ever run carried the ~88%-lethal condition for its entire duration, and the 600 s window
  brackets the whole observed FK-7 death spread (87-524 s).

  => This script runs ONE armed window with ONE variable changed: whether a standing `.text` patch
     is present. Everything else -- staging, gaps, hold, teardown, archiving -- is identical.

  THE FOUR RULES THIS SCRIPT ENCODES (each cost a real launch in a prior session)
  ------------------------------------------------------------------------------
  1. DELETE docs\tutorial-launch-marker.txt BEFORE staging. fk24-stage.ps1's `[SP] done step=4`
     gate reads that file and `Stage-Inject` never checks inject.exe's exit code -- so a FAILED sp
     injection leaves the stale marker in place, satisfies the gate instantly, and arms the probe
     with no possessed hero. Silent, and it wastes the launch.
  2. A QUIET CONTROL IS VOID, NOT A PASS. The mandated `play_novtguard` control fires only on the
     camera family (~8% per staged launch), so a 3x control gate would declare ~4 sittings in 5 VOID
     even when everything works. REPLACED here with a control that fires ~100% when the shim armed:
     RM_PLAY's own `[PL] *** init complete: body=...; camera + WASD active ***` (tutorial_launch.cpp
     :5190). It is arm-symmetric -- it detects a silent no-op in the treatment arm too, which is the
     single most likely way a non-`.text` callback mechanism fails.
  3. VERIFY INJECTION POSITIVELY, EVERY RUN. `-Hook` silently fails ~1 in 10. Rule 2's marker line IS
     the shim's own stamp; the stage transcript is kept as corroboration.
  4. ANCHOR TO THE MAP LOAD, NOT T+<n>. `SecondsSinceStart` is the LAUNCH clock and carries the
     operator's staging schedule (drifted +33.0 s July->August). This script's hold is measured from
     PROBE INJECTION, which is staging-invariant by construction, and it also records the
     `Load map complete .../LVL_Tutorial` timestamp so runs stay comparable across sessions.

  OUTCOMES (the `outcome` column of the CSV)
  ------------------------------------------
    DIED        -- process gone before the hold expired. `died_after_arm_s` is the datum.
    SURVIVED    -- reached the full hold with the shim armed. A clean negative.
    VOID_ARM    -- probe injected but `[PL] init complete` never appeared => shim never armed.
                   NOT a survival. Excluded from the denominator.
    VOID_DIED_PREARM -- died before arming. Excluded; it is a staging death, not an armed-window one.
    STAGE_FAIL  -- fk24-stage.ps1 aborted (exit 2/3/4/5). Costs a launch, yields no data point.

  Read the CSV, never the archive folder names: archive-crashdumps.ps1 snapshots the whole crashpad
  DB BEFORE a launch under the UPCOMING run's label, so archive labels are not authoritative.

  Run from an ELEVATED PowerShell. One call = one launch = at most one data point.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Probe,           # DLL under test (use the build\ path)
  [Parameter(Mandatory=$true)][string]$Arm,             # 'control' | 'treatment' | free text
  [Parameter(Mandatory=$true)][string]$Label,           # unique per run, e.g. s112-ctl-01
  [int]$HoldSeconds  = 320,                             # measured from PROBE INJECTION. 320 matches
                                                        # the S111 protocol exactly, so the 88%
                                                        # standing-`.text` figure is directly comparable.
  [int]$ArmWaitSec   = 120,                             # how long to wait for [PL] init complete
  [string]$GameRoot  = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE",
  [string]$OutCsv    = "",                              # default: docs\fk7-ab-results.csv
  [string]$Fo        = "",                              # S112: alternate force-open DLL for the
                                                        # `.rdata`-window arm. Recorded in the CSV so a
                                                        # run's staging config is never inferred later.
  [switch]$KeepAlive                                    # don't kill the game on a survival (debugging)
)

$ErrorActionPreference = 'Continue'
$repo    = Split-Path -Parent $PSScriptRoot
$docs    = Join-Path $repo 'docs'
$marker  = Join-Path $docs 'tutorial-launch-marker.txt'
$lokiLog = Join-Path $env:LOCALAPPDATA 'SUPERVIVE\Saved\Logs\Loki.log'
$crashes = Join-Path $env:LOCALAPPDATA 'SUPERVIVE\Saved\Crashes'
$reports = Join-Path $GameRoot 'Loki\.sentry-native\reports'
if(-not $OutCsv){ $OutCsv = Join-Path $docs 'fk7-ab-results.csv' }
$runDir  = Join-Path $docs ("fk7ab\" + $Label)
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Say($m){ Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) }

# Loki.log is held open by the game with a share mode Get-Content does not match.
function Read-Locked([string]$path,[int]$tailBytes = 600000){
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

# `.text` sha256 -- the ONLY safe way to tell two shim builds apart. Variants have shipped with
# identical whole-file AND `.text` SIZES while differing in hash; size comparison is not evidence.
function Get-TextHash([string]$path){
  if(-not (Test-Path $path)){ return 'missing' }
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
      $h  = [Security.Cryptography.SHA256]::Create().ComputeHash($d, $pr, $sz)
      return (($h | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0,16)
    }
  }
  return 'no.text'
}

function Write-Result($row){
  $exists = Test-Path $OutCsv
  $obj = New-Object psobject -Property $row
  $cols = @('label','arm','outcome','died_after_arm_s','hold_s','probe','probe_text_sha','game_pid',
            'aslr_base','launch_utc','arm_utc','end_utc','map_load_line','stage_exit','armed',
            'probe_receipt','gft_records','exit_code','fo_dll','new_uecc','new_crashpad','note')
  $obj = $obj | Select-Object $cols
  if($exists){ $obj | Export-Csv -Path $OutCsv -NoTypeInformation -Append }
  else       { $obj | Export-Csv -Path $OutCsv -NoTypeInformation }
  Say ("RESULT {0} arm={1} outcome={2} died_after_arm_s={3}" -f $row.label,$row.arm,$row.outcome,$row.died_after_arm_s)
}

# ---------------------------------------------------------------------------------------------
Say ("=== {0}  arm={1}  probe={2}" -f $Label,$Arm,(Split-Path -Leaf $Probe))
if(-not (Test-Path $Probe)){ throw "probe not found: $Probe" }
$Probe = (Resolve-Path $Probe).Path
$probeSha = Get-TextHash $Probe
Say ("probe .text sha256[0:16] = {0}" -f $probeSha)

$row = @{ label=$Label; arm=$Arm; outcome='UNKNOWN'; died_after_arm_s=''; hold_s=$HoldSeconds;
          probe=(Split-Path -Leaf $Probe); probe_text_sha=$probeSha; game_pid=''; aslr_base='';
          launch_utc=''; arm_utc=''; end_utc=''; map_load_line=''; stage_exit=''; armed='no';
          probe_receipt=''; gft_records=''; exit_code=''; fo_dll=$(if($Fo){Split-Path -Leaf $Fo}else{'tutorial_launch_fo.dll'}); new_uecc=''; new_crashpad=''; note='' }

# gft_ready_fix appends (FILE_APPEND_DATA/OPEN_ALWAYS) rather than truncating, so this file is the
# campaign's cumulative exposure denominator: one `injected; base=0x…` record per staged force-open.
$gftMarker = Join-Path $docs 'gft-ready-marker.txt'
function Get-GftCount(){
  if(-not (Test-Path $gftMarker)){ return 0 }
  return @([regex]::Matches((Read-Locked $gftMarker 400000), 'injected; base=0x[0-9A-Fa-f]+')).Count
}

# ---- 0. Steam must be up or login dies with Auth Failure 14005 (SteamAPI init fails).
if(-not (Get-Process steam -ErrorAction SilentlyContinue)){
  $row.outcome='STAGE_FAIL'; $row.note='Steam not running'; Write-Result $row; throw "Steam is not running."
}

# ---- 1. clear a stale game process from a prior run (see rule 1 -- stale state is the enemy here)
$old = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue
if($old){ Say "killing leftover game PID $($old.Id)"; $old | Stop-Process -Force; Start-Sleep -Seconds 6 }

# ---- 2. RULE 1: the stale-marker footgun.
if(Test-Path $marker){ Remove-Item $marker -Force; Say 'removed stale docs\tutorial-launch-marker.txt' }

# ---- 3. baseline the death artifacts so anything new is unambiguously THIS run's
$ueccBefore = @()
if(Test-Path $crashes){ $ueccBefore = @(Get-ChildItem $crashes -Directory -Filter 'UECC-*' -EA SilentlyContinue | Select-Object -Expand Name) }
$cpBefore = @()
if(Test-Path $reports){ $cpBefore = @(Get-ChildItem $reports -File -EA SilentlyContinue | Select-Object -Expand Name) }
$gftBefore = Get-GftCount
Say ("baseline: {0} UECC dirs, {1} crashpad reports, {2} gft exposure records" -f $ueccBefore.Count, $cpBefore.Count, $gftBefore)

# ---- 4. launch. -NoHook => the ONLY injections this sitting are gft / fo / sp / probe.
#         (launch-redirect archives the crashpad DB pre-launch under a default label -- that sweep
#          belongs to the PREVIOUS death, which is exactly why archive labels are not authoritative.)
$row.launch_utc = (Get-Date).ToUniversalTime().ToString('o')
Say 'launching (-NoHook)...'
& (Join-Path $PSScriptRoot 'launch-redirect.ps1') -GameRoot $GameRoot -NoHook *>&1 |
    Tee-Object -FilePath (Join-Path $runDir 'launch.log') | Out-Null

# ★ Grab the exit-code handle NOW, not after staging. MEASURED this session: this game dies in two
# distinguishable ways, and the exit code is the only cheap discriminator --
#   0xC0000005 = access violation, unhandled exception, leaves a crashpad minidump; and
#   0x0000DEAD = a deliberate silent TerminateProcess sentinel that leaves NO artifact at all
#                (not ours: there is no TerminateProcess/ExitProcess anywhere in the shim sources).
# Most launches die DURING STAGING, before the old acquisition point, so those deaths were blind.
# A handle held open while the process lives is what keeps the code readable after it exits.
$early = $null; $earlyProc = $null
for($w = 0; $w -lt 60; $w++){
  $earlyProc = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue | Select-Object -First 1
  if($earlyProc){ try { $early = $earlyProc.Handle } catch { }; break }
  Start-Sleep -Seconds 1
}

# ---- 5. stage the world + inject the probe under test
#
# ★ FORCE-OPEN RETRY (S112, added after run s112-ctl-01 and BEFORE any armed window existed, so it
#   amends the protocol rather than reacting to a result). MEASURED on that run: `fo` installed its PI
#   hook, got `[4] TIMEOUT no game-thread PI in 8s (hitsGT=0)`, never issued the console command, and
#   no world ever loaded. That is a mechanism for FK-26 ("force-open dies silently ~2 of 3 launches"):
#   `fo` gets ONE 8 s window to catch a game-thread Blueprint dispatch, and it either wins that race
#   or the launch is spent. Retrying costs ~70 s; a fresh launch costs ~390 s.
#
# ⚠ The guard matters. Re-running the stager against an ALREADY-STAGED live process is unsafe: its
#   world gate matches on the tail of Loki.log, so it would pass instantly on the PREVIOUS attempt's
#   `Load map complete` line and send the one-shot `sp` in blind. So retry ONLY while that line is
#   ABSENT -- which is exactly the state a force-open failure leaves behind, and is checked here
#   rather than assumed. Once the world is up we never retry.
#
# `-WaitWorldSec 45` because a working force-open loads the map in ~5.7 s and the whole point of the
# 180 s default was to tolerate a slow load, not a dead one. Retries are applied IDENTICALLY in both
# arms and the attempt count is recorded, so the shared staging exposure stays balanced.
$stageLog  = Join-Path $runDir 'stage.log'
$maxAttempts = 3
$stageExit = -1
$attempts = 0
for($att = 1; $att -le $maxAttempts; $att++){
  $attempts = $att
  Say ("staging attempt {0}/{1} (gft -> fo -> sp -> probe)..." -f $att, $maxAttempts)
  $stageArgs = @{ Probe = $Probe; Label = $Label; WaitWorldSec = 45 }
  if($Fo){ $stageArgs['Fo'] = $Fo }
  & (Join-Path $PSScriptRoot 'fk24-stage.ps1') @stageArgs *>&1 |
      Tee-Object -FilePath ("{0}.{1}" -f $stageLog, $att)
  $stageExit = $LASTEXITCODE
  $attTxt = Get-Content ("{0}.{1}" -f $stageLog, $att) -Raw -EA SilentlyContinue
  if($attTxt -match 'stage complete'){ break }
  if(-not (Get-Process SUPERVIVE-Win64-Shipping -EA SilentlyContinue)){ Say 'game is gone; not retrying'; break }
  # the guard: only retry while the world genuinely never came up
  if((Read-Locked $lokiLog 1500000) -match 'Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial'){
    Say 'world DID load -- refusing to re-run the stager against a staged process (one-shot sp)'; break
  }
  if($att -lt $maxAttempts){ Say 'force-open lost its 8 s race; retrying'; Start-Sleep -Seconds 20 }
}
$row.stage_exit = ("{0}/att{1}" -f $stageExit, $attempts)
Get-Content ("{0}.*" -f $stageLog) -EA SilentlyContinue | Set-Content $stageLog -EA SilentlyContinue
$armAt = Get-Date                      # T_arm: probe injection + ~3 s, identical in both arms
$row.arm_utc = $armAt.ToUniversalTime().ToString('o')

$proc = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue | Select-Object -First 1
if($proc){ $row.game_pid = $proc.Id }
# ★ Hold an OS handle open while the process is alive so its EXIT CODE survives the exit. This is the
# cheapest discriminator we have between the two ways this game dies, and nothing in the project
# records it today: an unhandled exception exits with the status code (0xC0000005 &c) and normally
# leaves a crashpad minidump, whereas an external TerminateProcess exits with the killer's chosen
# code and leaves NO artifact at all. Without this, the artifact-less deaths (the FK-25 class) are
# indistinguishable from "crashpad did not get around to writing the report", and we would be
# reasoning about the difference from an absence.
$hProc = $null
if($proc){ try { $hProc = $proc.Handle } catch { } }

$stageTxt = ''
if(Test-Path $stageLog){ $stageTxt = Get-Content $stageLog -Raw }

# ---- CORROBORATING RECEIPT (recording only -- the gate is still `[PL] init complete`).
# `Worker()` truncates the marker with CREATE_ALWAYS as its FIRST statement (tutorial_launch.cpp
# :6278), so the probe's own stage-4 snapshot starting fresh -- and no longer carrying sp's
# `[SP] done step=4` -- is proof the probe DLL was actually LOADED AND RAN DllMain->Worker.
# That matters because `Stage-Inject` discards inject.exe's exit code AND its
# `OK: manual-map complete` line, and the injector silently fails ~1 in 10. Note
# `docs\inject-watch.out.log` is NOT usable here: it is written only by launch-redirect's -Hook
# watcher, which a -NoHook tutorial launch never runs.
$probeSnap = Get-ChildItem $docs -Filter ("fk24-stage-{0}-4-probe-*.txt" -f $Label) -EA SilentlyContinue | Select-Object -First 1
if($probeSnap){
  $ps = Get-Content $probeSnap.FullName -Raw
  if($ps -match '^\s*\[0\] tutorial_launch' -and $ps -notmatch '\[SP\]\s+done step=4'){ $row.probe_receipt='truncated-ok' }
  elseif($ps -match '\[SP\]\s+done step=4'){ $row.probe_receipt='STALE-no-truncate' }
  else { $row.probe_receipt='unclear' }
} else { $row.probe_receipt='no-snapshot' }
$gftAfter = Get-GftCount
$row.gft_records = ("{0}->{1}" -f $gftBefore, $gftAfter)
# the ASLR base belongs to gft's own append-only marker, not the stage transcript
$gftTxt = Read-Locked $gftMarker 400000
$gm = [regex]::Matches($gftTxt, 'injected; base=(0x[0-9A-Fa-f]+)')
if($gm.Count -gt 0){ $row.aslr_base = $gm[$gm.Count-1].Groups[1].Value }
Say ("receipt: probe={0}  gft records {1}" -f $row.probe_receipt, $row.gft_records)
if($stageTxt -notmatch 'stage complete'){
  # Separate the two ways staging loses a launch. They are NOT the same event and pooling them
  # would hide a real hazard: STAGE_DEATH is the game dying with only gft+fo resident (measured
  # repeatedly right around the map load, and classified OURS/protector), which is a property of
  # the SHARED staging and therefore arm-neutral; STAGE_FAIL is the force-open simply losing its
  # 8 s race with no death at all. Both cost a launch; only one is a death.
  if(-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)){
    $row.outcome='STAGE_DEATH'
    $row.note=("game died during staging, before the probe was injected (stage exit {0})" -f $stageExit)
    Say "game died DURING STAGING -> STAGE_DEATH (arm-neutral: probe never injected)"
    Start-Sleep -Seconds 15   # let crashpad finish the ~44 MB write before we archive
    if($earlyProc){ try { $earlyProc.Refresh() } catch { }; try { $row.exit_code = ('0x{0:X8}' -f $earlyProc.ExitCode) } catch { $row.exit_code='unavailable' } }
    Say ("staging death exit code = {0}" -f $row.exit_code)
  } else {
    $row.outcome='STAGE_FAIL'
    $row.note=("fk24-stage aborted, game still alive (exit {0})" -f $stageExit)
    Say "stage did not complete, game alive -> STAGE_FAIL"
  }
  if($proc){ $proc | Stop-Process -Force }
  Start-Sleep -Seconds 4
  & (Join-Path $PSScriptRoot 'archive-crashdumps.ps1') -GameRoot $GameRoot -Label $Label -Quiet
  if(Test-Path $lokiLog){ Copy-Item $lokiLog (Join-Path $runDir 'Loki.log') -Force -EA SilentlyContinue }
  $row.end_utc = (Get-Date).ToUniversalTime().ToString('o')
  Write-Result $row
  exit 10
}

# ---- 6. RULE 2 + 3: the arm-symmetric positive control. `[PL] *** init complete ***` fires ~100%
#         when RM_PLAY armed, in EITHER arm. Absent => the shim never armed => VOID, not a pass.
Say ("waiting up to {0}s for the positive control: [PL] init complete ..." -f $ArmWaitSec)
$armed = $false; $preArmDeath = $false
$t0 = Get-Date
while(((Get-Date) - $t0).TotalSeconds -lt $ArmWaitSec){
  if(-not (Get-Process -Id $row.game_pid -ErrorAction SilentlyContinue)){ $preArmDeath = $true; break }
  $mk = Read-Locked $marker 400000
  if($mk -match '\[PL\] \*\*\* init complete'){ $armed = $true; break }
  Start-Sleep -Seconds 2
}
if($armed){ $row.armed='yes'; Say ("POSITIVE CONTROL FIRED at +{0}s" -f [int]((Get-Date)-$t0).TotalSeconds) }

if($preArmDeath){
  $row.outcome='VOID_DIED_PREARM'
  $row.died_after_arm_s = [int]((Get-Date) - $armAt).TotalSeconds
  $row.note='died before the positive control fired -- staging death, not an armed window'
  Say 'game died BEFORE arming -> VOID_DIED_PREARM'
} elseif(-not $armed){
  $row.outcome='VOID_ARM'
  $row.note=("no [PL] init complete within {0}s -- shim never armed" -f $ArmWaitSec)
  Say 'positive control QUIET -> VOID (not a pass)'
} else {
  # ---- 7. the armed hold. Poll only; never touch the game.
  Say ("armed hold: {0}s from probe injection" -f $HoldSeconds)
  $died = $false
  while(((Get-Date) - $armAt).TotalSeconds -lt $HoldSeconds){
    if(-not (Get-Process -Id $row.game_pid -ErrorAction SilentlyContinue)){ $died = $true; break }
    Start-Sleep -Seconds 2
  }
  $elapsed = [int]((Get-Date) - $armAt).TotalSeconds
  $row.died_after_arm_s = $elapsed
  if($died){
    $row.outcome='DIED'
    # crashpad_handler writes the ~44 MB minidump AFTER the faulting process is already gone, so
    # archiving the instant the PID disappears races it and silently loses the report -- which then
    # reads as "an artifact-less death", a completely different fault class. Wait for the write.
    Say ("*** DIED at arm+{0}s *** -- waiting 15s for crashpad to finish writing" -f $elapsed)
    Start-Sleep -Seconds 15
    if($proc){ try { $proc.Refresh() } catch { }; try { $row.exit_code = ('0x{0:X8}' -f $proc.ExitCode) } catch { } }
    if(-not $row.exit_code -and $earlyProc){ try { $earlyProc.Refresh() } catch { }; try { $row.exit_code = ('0x{0:X8}' -f $earlyProc.ExitCode) } catch { $row.exit_code='unavailable' } }
    Say ("exit code = {0}" -f $row.exit_code)
  }
  else { $row.outcome='SURVIVED'; Say ("survived the full {0}s hold" -f $HoldSeconds) }
}

# ---- 8. teardown + artifact capture, in the order that preserves evidence
#         (copy the log BEFORE the next launch: UE rotates Loki.log at game startup, so right now it
#          is still THIS run's, untruncated -- which is also why the pre-launch sweep is correct.)
if(Test-Path $marker){ Copy-Item $marker (Join-Path $runDir 'tutorial-launch-marker.txt') -Force -EA SilentlyContinue }
Get-ChildItem $docs -Filter ("fk24-stage-{0}-*.txt" -f $Label) -EA SilentlyContinue |
    ForEach-Object { Copy-Item $_.FullName $runDir -Force -EA SilentlyContinue }
$alive = Get-Process -Id $row.game_pid -ErrorAction SilentlyContinue
if($alive -and -not $KeepAlive){ Say "killing game PID $($row.game_pid)"; $alive | Stop-Process -Force; Start-Sleep -Seconds 6 }
if(Test-Path $lokiLog){ Copy-Item $lokiLog (Join-Path $runDir 'Loki.log') -Force -EA SilentlyContinue }

# the staging-invariant anchor
$log = Read-Locked $lokiLog 1500000
$mm = [regex]::Match($log, '.*Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial.*')
if($mm.Success){ $row.map_load_line = $mm.Value.Trim() }

# ---- 9. archive THIS run's death under THIS run's label, by hand, before any further launch
& (Join-Path $PSScriptRoot 'archive-crashdumps.ps1') -GameRoot $GameRoot -Label $Label -Quiet

$ueccAfter = @()
if(Test-Path $crashes){ $ueccAfter = @(Get-ChildItem $crashes -Directory -Filter 'UECC-*' -EA SilentlyContinue | Select-Object -Expand Name) }
$row.new_uecc = ((Compare-Object $ueccBefore $ueccAfter -PassThru | Where-Object { $ueccAfter -contains $_ }) -join ';')
$fullLog = Read-Locked $lokiLog 40000000
if($fullLog -match 'handing control over to crashpad'){ $row.new_crashpad = 'yes' } else { $row.new_crashpad = 'no' }

$row.end_utc = (Get-Date).ToUniversalTime().ToString('o')
Write-Result $row
Say ("artifacts -> {0}" -f $runDir)
