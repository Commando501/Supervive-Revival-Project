<#
.SYNOPSIS
  Capture usmapdump image snapshots at multiple game states, then merge + reconstruct
  them into one named-import cold image for offline RE in Ghidra/IDA.

.DESCRIPTION
  The shipping build demand-decrypts .text pages on execution, so a single dump only
  captures the code that has RUN so far (~50% at a fresh menu). This helper snapshots the
  live game at each state you name into dumps/<state>/, then unions them (mergedumps) and
  rebuilds the import table (deobfimports - SUPERVIVE's imports are obfuscated trampolines;
  NOT VMProtect, see docs/fk10-protector-identified.md) into dumps/merged.dump.iat.exe.
  Finalize while the game is still running (deobf emulates the live stubs).

  ** ONLY A STATE THAT RUNS NEW CODE PAYS. ** MEASURED 2026-08-14 over the 11 dumps on disk
  (docs/fk18-fk19-multistate-merge-settled.md): STORE, HUNTERS roster, MISSIONS and loadout
  each contribute ZERO pages beyond dumps/menu. What actually paid, in .text pages that
  merged.dump.exe lacked: tutorial-hero 570, toggles (drop-in loading) 539, rcb 270,
  lobby-dispatch-decrypted 29, vmbuild 7, accountpass 1, and menu/store/roster/missions/
  loadout 0 each. Do not spend a capture on another menu surface.

  ** CROSS-SESSION CAPTURE IS FINE - THE OLD "ONE LIFETIME" RULE IS RETRACTED. ** This block
  used to read "HARD CONSTRAINT: every state must come from ONE game process lifetime -
  mergedumps rejects inputs with a different ImageBase ... capture all states WITHOUT
  relaunching." That is measured false: .text carries 0 of the image's 1,403,750 base
  relocations and is byte-identical across ImageBases on every shared decrypted page (0
  differing bytes, 10 of 10 pairwise comparisons). mergedumps now merges .text page-granularly
  and ignores ImageBase entirely. Worse, the old rule was self-sealing: it forced every capture
  into one process lifetime, and within one lifetime .text decryption is MONOTONE, so the
  snapshots are strictly nested and every extra one is worth exactly 0 pages. That is why the
  five inputs to merged.dump.exe bought 0 .text bytes between them.
  ==> RELAUNCH BETWEEN CAPTURES. The script still records the first dump's PID + base and
  reports base drift, because a cross-base dump contributes .text only (its .rdata/.data are
  base-dependent and are skipped, not spliced).

  ** SUPERSEDED 2026-08-20 (S133, FK-20) - READ docs/fk20-coverage-settled.md BEFORE CAPTURING. **
  The block above said "CAPTURE THE TUTORIAL WORLD - it is the highest-yield state reachable
  today ... still uncaptured and top of the list: hero select, drop phase, a LIVE MATCH,
  end-of-game." That is now measured and it is much weaker than it reads:

    * THE CAPTURE SIDE IS SATURATED. 26 images on disk; their union IS dumps/merged6.dump.exe
      (16,694 / 30,281 .text pages = 55.13%). 12 images reach that union; the other 14 are worth
      ZERO pages. tutorial-hero alone is 96.5% of it. Only 82 pages corpus-wide are unique to a
      single image.
    * THE EXCHANGE RATE IS 216 PAGES (0.71 pp of .text) FOR EVERYTHING FROM S107 TO S132 -
      LVL_Tutorial loaded, hero spawned/possessed/walking, GoToPhase driven to EGP_Combat,
      navmesh, a drop pod flying at 20,000 uu/s, the rideable wall, the dismount. And the MENU
      family contributes MORE unique pages than the tutorial family (437 vs 216).
    * 67.91% OF THE DARK SET IS UNREACHABLE BY ANY GAME STATE (9,231 of 13,592 pages, 36.06 MiB):
      UE's own Chaos ISPC collision kernels, multi-ISA-target so ~2/3 is unreachable on this CPU
      by construction; editor/authoring modules with no entry point in a packaged client (PCG,
      MeshModelingTools, Sequencer); and third-party libs (ICU 64, OpenEXR, OpenSSL, Oodle,
      libwebm, crashpad). The reachable ceiling is 4,361 pages = 32.09% of dark = 17.04 MiB, and
      that assumes a match runs every line of every gameplay module.
    * 125 CRASH LIFETIMES PLUS OUR 26 CAPTURES ONLY EVER REACHED 55.27%. The crashpad
      MemoryInfoListStream is an exact per-page decryption map (NOACCESS vs EXECUTE_READ, and
      ONLY those two values ever appear over .text). ==> the dark 45% is dark because THE GAME
      NEVER RAN IT, not because we failed to snapshot it.

  ** SO: DO NOT CAPTURE FOR COVERAGE'S OWN SAKE. DRIVE NEW CODE, THEN RE-GRADE. **
  Re-dumping an already-explored state is worth 0-5 pages. The highest-yield captures are now
  ZERO-RISK and need no relaunch or injection - see docs/fk20-coverage-settled.md section 8:
    1. party / queue / custom-game ACTION sweep (UPartyManager has 20 dark impls incl.
       TryJoinQueue 0x5875E90, the most-cited dark address in the repo)
    2. FULL-PAYLOAD /lobby notif sweep (S117's bare {"type":X} frames cannot reach a
       per-type deserializer)
    3. settings / renderer permutation sweep
  The one concentrated reachable target is the Angelscript AOT band 0x59128B0-0x5A7F070:
  239 of 366 pages dark (65.3%), 2,058 of 3,760 function slots never decrypted in 76 minidumps.
  That is FK-1's drop/pod/respawn layer and only a real match lights it.

  ** AFTER EVERY CAPTURE, RUN:  python tools/re/dump_coverage_ledger.py **
  Ten images once sat unmerged for six days because mergedumps manifests name donors by
  BASENAME only. The ledger reads bytes, not manifests, and exits 1 on an orphan.

  PREREQS: run configs/launch-redirect.ps1 first (elevated) - it lands at the main menu with
  the full shim set active. Then navigate the game and snapshot with this script from the
  SAME elevated terminal session (usmapdump needs SeDebugPrivilege to read the game). That
  is a PRIVILEGE requirement and is unrelated to the retracted ImageBase constraint above.

.PARAMETER State     Capture the live game NOW into dumps/<State>/ and exit.
.PARAMETER Finalize  Merge every dumps/*/ snapshot + reconstruct the IAT, then exit.
.PARAMETER Clear     Delete captured STATE dirs only (dirs holding a *.dump.exe), after an
                     interactive confirmation that prints the byte count. NEVER touches
                     crashpad-*, merged*, *-archive*, usmap-* or extractor-out-* - dumps/ is
                     16 GB of gitignored, irreplaceable evidence and there is no undo.
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
# merged2, NOT merged: dumps/merged.dump.exe is the historical artifact the strxref index was
# validated against, and overwriting it silently invalidates that index. merged2.dump.exe is the
# canonical cold image as of 2026-08-14 (S121) - .text 54.90% vs merged's 52.29%, strict superset.
$mergedOut   = Join-Path $DumpsDir "merged2.dump.exe"

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
  # 2026-08-14 (S121): this used to be
  #     Get-ChildItem $DumpsDir -Force | Remove-Item -Recurse -Force
  # i.e. it deleted the ENTIRE dumps root. MEASURED at the time of the fix: 16 GB across 386
  # entries, including 363 crashpad-* archives (the whole FK-7/FK-8/FK-31/FK-32 crash corpus,
  # ~44 MB minidump each), merged.dump.exe (the historical artifact the strxref index was
  # validated against), the usmap archives and the extractor output. /dumps/ is gitignored, so
  # there is NO undo. configs/archive-crashdumps.ps1 writes into this same directory on every
  # launch, so the corpus only ever grows here.
  # It now deletes ONLY captured state directories -- a dir holding a top-level *.dump.exe --
  # and never anything matching the protected patterns below.
  if (-not (Test-Path $DumpsDir)) {
    New-Item -ItemType Directory -Force -Path $DumpsDir | Out-Null
    Write-Host "Created $DumpsDir" -ForegroundColor Green
    return
  }
  $protected = @('crashpad-*', 'merged*', '*-archive*', 'usmap-*', 's109-*', 'extractor-out-*')
  $victims = Get-ChildItem -Path $DumpsDir -Directory -Force -ErrorAction SilentlyContinue | Where-Object {
    $name = $_.Name
    if ($protected | Where-Object { $name -like $_ }) { return $false }
    Test-Path (Join-Path $_.FullName '*.dump.exe')
  }
  if (-not $victims) { Write-Host "Nothing to clear (no captured state dirs)." -ForegroundColor Green; return }
  $bytes = ($victims | ForEach-Object { (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum } | Measure-Object -Sum).Sum
  Write-Host "About to delete $($victims.Count) captured state dir(s), $([math]::Round($bytes/1GB,2)) GB:" -ForegroundColor Yellow
  $victims | ForEach-Object { Write-Host "   $($_.Name)" -ForegroundColor Yellow }
  Write-Host "PROTECTED and untouched: crashpad-*, merged*, *-archive*, usmap-*, s109-*, extractor-out-*" -ForegroundColor DarkGray
  $ans = Read-Host "Type DELETE to confirm"
  if ($ans -cne 'DELETE') { Write-Host "Aborted - nothing deleted." -ForegroundColor Green; return }
  $victims | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  Write-Host "Cleared $($victims.Count) state dir(s) from $DumpsDir" -ForegroundColor Green
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
      # Relaunching between captures is now the RECOMMENDED workflow (FK-19), so this is a
      # note, not a warning. A warning that fires on the correct path trains you to ignore
      # warnings -- and the stale first-write-wins session file made it fire every time.
      Write-Host "  note: different PID than the first recorded dump ($($sess.pid) -> $gamePid) - fine, cross-session capture is supported." -ForegroundColor DarkGray
    }
    if ($info.base -and $sess.base -and ($info.base -ne $sess.base)) {
      # NOT an error since 2026-08-14 (FK-19). .text has zero base relocations and is
      # byte-identical across ImageBases, so a cross-base dump merges fine - it just
      # contributes .text only. Do NOT recapture the set in one launch; that was the old
      # advice and it is exactly what made every extra capture worthless (nested lifetimes).
      Write-Host "  note: ImageBase drift ($($sess.base) -> $($info.base)) - fine. mergedumps takes this dump's .text (base-invariant); its .rdata/.data are skipped." -ForegroundColor DarkGray
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
    # The merge manifest is "<outFile>.txt" (merged2.dump.exe.txt), NOT "*.dump.txt", so the
    # Get-DumpInfo filter used to miss it entirely and this row printed a BLANK percentage --
    # i.e. the one number the whole workflow exists to move was invisible. 2026-08-14 (S121).
    # Read the PAGES NON-ZERO column (the last "(nn.nn%)" on the .text line), because that is
    # what the per-state rows above report. The first percentage on that line is NON-ZERO BYTES
    # and is ~4 pp lower -- comparing the two would read as the merge having made things worse.
    $mergedMan = "$mergedOut.txt"
    $mtext = ""
    if (Test-Path $mergedMan) {
      foreach ($ln in (Get-Content $mergedMan)) {
        if ($ln -match '^\.text\s.*\(([\d.]+)%\)\s*$') { $mtext = $matches[1] }
      }
    }
    $mname = [System.IO.Path]::GetFileNameWithoutExtension($mergedOut) -replace '\.dump$',''
    Write-Host ("  {0,-16} .text={1,5}%  (MERGED, pages)" -f $mname, $mtext) -ForegroundColor Green
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

  # SUPERVIVE's imports are protected by a bespoke scheme (IAT points to obfuscated
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
