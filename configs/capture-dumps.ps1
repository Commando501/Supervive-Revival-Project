<#
.SYNOPSIS
  Capture usmapdump image snapshots at multiple game states, then merge + reconstruct
  them into one named-import cold image for offline RE in Ghidra/IDA.

.DESCRIPTION
  The shipping build demand-decrypts .text pages on execution, so a single dump only
  captures the code that has RUN so far (~50% at a fresh menu). Different states run
  different code - opening the STORE, browsing the HUNTERS roster, MISSIONS, loadout each
  decrypt their shim's native-call code. This helper snapshots the live game at each state
  you name into dumps/<state>/, then unions them (mergedumps) and rebuilds the import table
  (deobfimports - SUPERVIVE's imports are VMProtect-protected trampolines) into
  dumps/merged.dump.iat.exe. Finalize while the game is still running (deobf emulates the
  live stubs).

  HARD CONSTRAINT: every state must come from ONE game process lifetime - mergedumps rejects
  inputs with a different ImageBase, and each launch gets a new ASLR base. So capture all
  states WITHOUT relaunching. This script records the first dump's PID + base and warns if a
  later dump drifts (i.e. the game was relaunched - those dumps won't merge).

  PREREQS: run configs/launch-redirect.ps1 first (elevated) - it lands at the main menu with
  the full shim set active. Then navigate the game and snapshot with this script from the
  SAME elevated terminal session (usmapdump needs SeDebugPrivilege to read the game).
  The tutorial/match state is not captured here (that flow isn't playable yet); this is the
  menu-with-shims capture. Gameplay .text stays a gap until the match flow works.

.PARAMETER State     Capture the live game NOW into dumps/<State>/ and exit.
.PARAMETER Finalize  Merge every dumps/*/ snapshot + reconstruct the IAT, then exit.
.PARAMETER Clear     Delete everything under the dumps dir first (fresh session).
.PARAMETER List      Show captured states + coverage and exit.
.PARAMETER DumpsDir  Output root (default <repo>/dumps).
.PARAMETER Proc      Target process (default SUPERVIVE-Win64-Shipping.exe).

.EXAMPLE  .\capture-dumps.ps1                 # interactive: name a state to dump, 'done' to finalize
.EXAMPLE  .\capture-dumps.ps1 -State menu     # snapshot the current state into dumps/menu/
.EXAMPLE  .\capture-dumps.ps1 -Finalize       # merge all states + reconstruct imports
.EXAMPLE  .\capture-dumps.ps1 -Clear          # wipe dumps/, then drop into interactive capture
#>
param(
  [string]$State = "",
  [switch]$Finalize,
  [switch]$Clear,
  [switch]$List,
  [string]$DumpsDir = "",
  [string]$Proc = "SUPERVIVE-Win64-Shipping.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $DumpsDir) { $DumpsDir = Join-Path $repoRoot "dumps" }
$usmap    = Join-Path $repoRoot "tools\usmapdump\usmapdump.exe"
$procName = [System.IO.Path]::GetFileNameWithoutExtension($Proc)
$sessionFile = Join-Path $DumpsDir ".capture-session.txt"
$mergedOut   = Join-Path $DumpsDir "merged.dump.exe"

# ---- preflight ----
if (-not (Test-Path $usmap)) {
  Write-Host "usmapdump.exe not found at $usmap" -ForegroundColor Red
  Write-Host "Build it:  & `"$env:ProgramFiles\Go\bin\go.exe`" build -trimpath -C `"$repoRoot\tools\usmapdump`" -o usmapdump.exe ." -ForegroundColor Yellow
  exit 1
}
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
  Write-Warning "Not elevated - usmapdump can't read the elevated game process (OpenProcess will fail)."
  Write-Warning "  Run this in the same ADMIN terminal you launched the game from."
}

# ---- helpers ----
function Get-GamePid {
  $p = Get-Process -Name $procName -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($p) { return $p.Id }
  return 0
}

# Parse base + .text coverage% out of a state's dumpimage manifest.
function Get-DumpInfo($stateDir) {
  $info = [ordered]@{ base = ""; text = "" }
  $man = Get-ChildItem -Path $stateDir -Filter *.dump.txt -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($man) {
    foreach ($ln in (Get-Content $man.FullName)) {
      if ($ln -match '^base\s*:\s*(0x[0-9A-Fa-f]+)') { $info.base = $matches[1] }
      if ($ln -match '^\.text\s.*\(([\d.]+)%\)')      { $info.text = $matches[1] }
    }
  }
  return $info
}

function Read-Session {
  $s = [ordered]@{ pid = ""; base = "" }
  if (Test-Path $sessionFile) {
    foreach ($ln in (Get-Content $sessionFile)) {
      if ($ln -match '^pid=(.+)$')  { $s.pid  = $matches[1] }
      if ($ln -match '^base=(.+)$') { $s.base = $matches[1] }
    }
  }
  return $s
}
function Write-Session($gamePid, $base) {
  Set-Content -Path $sessionFile -Value @("pid=$gamePid", "base=$base") -Encoding ascii
}

# ---- actions ----
function Clear-Dumps {
  if (Test-Path $DumpsDir) {
    Get-ChildItem -Path $DumpsDir -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  }
  New-Item -ItemType Directory -Force -Path $DumpsDir | Out-Null
  Write-Host "Cleared $DumpsDir" -ForegroundColor Green
}

function Invoke-Dump($stateName) {
  $stateName = ($stateName -replace '[^\w.-]', '_').Trim('_')
  if (-not $stateName) { Write-Host "  (empty state name - skipped)" -ForegroundColor Yellow; return }

  $gamePid = Get-GamePid
  if ($gamePid -eq 0) {
    Write-Host "Game process '$Proc' not running - launch it (configs\launch-redirect.ps1) and navigate to the state first." -ForegroundColor Red
    return
  }
  New-Item -ItemType Directory -Force -Path $DumpsDir | Out-Null
  $outDir = Join-Path $DumpsDir $stateName

  Write-Host ""
  Write-Host "Capturing '$stateName' (PID $gamePid) -> $outDir" -ForegroundColor Cyan
  & $usmap dumpimage $Proc $outDir
  if ($LASTEXITCODE -ne 0) { Write-Host "  dumpimage FAILED (exit $LASTEXITCODE)" -ForegroundColor Red; return }

  $info = Get-DumpInfo $outDir
  # Session base/PID consistency - all merge inputs must share one ASLR base (one launch).
  $sess = Read-Session
  if (-not $sess.base) {
    Write-Session $gamePid $info.base
  } else {
    if ($sess.pid -ne "$gamePid") {
      Write-Warning "Game PID changed ($($sess.pid) -> $gamePid): the game was RELAUNCHED mid-capture."
    }
    if ($info.base -and $sess.base -and ($info.base -ne $sess.base)) {
      Write-Warning "ImageBase drift ($($sess.base) -> $($info.base)): this state will NOT merge with the earlier ones."
      Write-Warning "  Recapture the whole set in ONE launch: .\capture-dumps.ps1 -Clear  then re-dump each state."
    }
  }
  Write-Host ("  OK  '{0}'  .text={1}%  base={2}" -f $stateName, $info.text, $info.base) -ForegroundColor Green
}

function Show-List {
  Write-Host ""
  Write-Host "Captured states in $DumpsDir :" -ForegroundColor Cyan
  $dirs = Get-ChildItem -Path $DumpsDir -Directory -ErrorAction SilentlyContinue
  if (-not $dirs) { Write-Host "  (none yet)" -ForegroundColor DarkGray; return }
  foreach ($d in $dirs) {
    $has = Get-ChildItem -Path $d.FullName -Filter *.dump.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $has) { continue }
    $info = Get-DumpInfo $d.FullName
    Write-Host ("  {0,-16} .text={1,5}%  base={2}" -f $d.Name, $info.text, $info.base)
  }
  if (Test-Path $mergedOut) {
    $mi = Get-DumpInfo $DumpsDir
    Write-Host ("  {0,-16} .text={1,5}%  (MERGED)" -f "merged", $mi.text) -ForegroundColor Green
  }
}

function Invoke-Finalize {
  $states = @(Get-ChildItem -Path $DumpsDir -Directory -ErrorAction SilentlyContinue |
             Where-Object { Get-ChildItem -Path $_.FullName -Filter *.dump.exe -ErrorAction SilentlyContinue })
  if ($states.Count -eq 0) {
    Write-Host "No captured states under $DumpsDir - nothing to finalize." -ForegroundColor Red
    return
  }
  Write-Host ""
  Write-Host "Finalizing $($states.Count) state(s): $($states.Name -join ', ')" -ForegroundColor Cyan

  Write-Host "-- mergedumps --" -ForegroundColor DarkGray
  & $usmap mergedumps $mergedOut $DumpsDir
  if ($LASTEXITCODE -ne 0) { Write-Host "mergedumps FAILED (exit $LASTEXITCODE)" -ForegroundColor Red; return }

  # SUPERVIVE's imports are VMProtect/Themida-protected (IAT points to obfuscated
  # trampolines), so use `deobfimports` which emulates each stub against the LIVE process.
  # Falls back to `reconstructiat` (direct) only for unprotected targets.
  $alive = Get-Process -Name $procName -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($alive) {
    Write-Host "-- deobfimports (live emulate, PID $($alive.Id)) --" -ForegroundColor DarkGray
    & $usmap deobfimports $Proc $mergedOut
    if ($LASTEXITCODE -ne 0) { Write-Host "deobfimports FAILED (exit $LASTEXITCODE)" -ForegroundColor Red; return }
  } else {
    Write-Host "Game not running - import stubs need the LIVE process to deobfuscate." -ForegroundColor Yellow
    Write-Host "Merged dump is written WITHOUT named imports. To name them: relaunch the game," -ForegroundColor Yellow
    Write-Host "reach any state, then run  .\capture-dumps.ps1 -Finalize  again." -ForegroundColor Yellow
    Write-Host "(Trying reconstructiat for any unprotected slots...)" -ForegroundColor DarkGray
    & $usmap reconstructiat $mergedOut
  }

  # mergedOut "merged.dump.exe" -> reconstructiat writes "merged.dump.iat.exe"
  $iat = ($mergedOut -replace '\.exe$', '') + ".iat.exe"
  Write-Host ""
  Write-Host "DONE. Load in Ghidra/IDA:  $iat" -ForegroundColor Green
  Show-List
}

function Invoke-Interactive {
  Write-Host ""
  Write-Host "Interactive capture. Navigate the game to a state, then type a name to snapshot it." -ForegroundColor Cyan
  Write-Host "Commands: <name>=dump that state | list | done=merge+reconstruct | quit=exit" -ForegroundColor DarkGray
  while ($true) {
    $ans = Read-Host "state"
    if ($null -eq $ans) { break }
    $ans = $ans.Trim()
    switch -Regex ($ans) {
      '^(done|finalize|f)$' { Invoke-Finalize; return }
      '^(quit|exit|q)$'     { Write-Host "Exited without finalizing (states are kept; run -Finalize later)." -ForegroundColor Yellow; return }
      '^(list|ls|l)$'       { Show-List }
      '^\s*$'               { }
      default               { Invoke-Dump $ans; Show-List }
    }
  }
}

# ---- dispatch ----
if ($Clear)    { Clear-Dumps }
if ($List)     { Show-List; return }
if ($State)    { Invoke-Dump $State }
if ($Finalize) { Invoke-Finalize }
if (-not $State -and -not $Finalize -and -not $List) { Invoke-Interactive }
