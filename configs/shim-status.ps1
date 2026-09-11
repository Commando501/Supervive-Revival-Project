<#
.SYNOPSIS
  Read-only readiness dashboard for the injected revival shims. The launcher fires the injectors
  detached and then blocks on the game, so there's no consolidated "did every shim activate?" view —
  this fills that gap. Run it in a SECOND terminal during/after a launch.

.DESCRIPTION
  Each shim truncates its own docs/*-marker.txt at startup and writes progress + heartbeat lines. This
  reads those markers and classifies each shim:
    READY    - a success token is present (hook built / swapped / patched / unhooked)
    FAILED   - a "FAIL" token is present
    running  - marker exists + is being written, but no success token yet
    stale    - marker exists but hasn't been touched recently (leftover from a PREVIOUS launch; the
               shim was NOT injected this session)
    absent   - no marker at all
  Marker age (seconds since last write) is shown because the markers persist across launches — a fresh
  age (heartbeats tick every few seconds) is the liveness signal that the shim is active THIS launch.

  Purely observational (no injection, no game control). Safe to run anytime.

.PARAMETER Watch      Refresh every -IntervalSec seconds until Ctrl+C (live dashboard).
.PARAMETER IntervalSec Refresh cadence for -Watch (default 2).
.PARAMETER StaleSec   Age (s) beyond which a marker is treated as leftover from a prior launch (default 45).

.EXAMPLE  .\configs\shim-status.ps1
.EXAMPLE  .\configs\shim-status.ps1 -Watch
#>
param(
  [string]$Repo = (Split-Path -Parent $PSScriptRoot),
  [switch]$Watch,
  [int]$IntervalSec = 2,
  [int]$StaleSec = 45
)

# Each shim: display name, marker file (docs\<file>), a READY regex, and a FAILED regex. The default
# launch set is the four secondaries + the primary. Tokens are drawn from the shims' own marker output.
$shims = @(
  @{ Name = "catalog_store_fix (store+roster)"; Marker = "catalog-store-fix-marker.txt"; Ready = '\[unhook\]|unhook=1'; Fail = '\bFAIL\b' }
  @{ Name = "catalog_pick_fix  (pick-commit)";  Marker = "catalog-pick-fix-marker.txt";  Ready = 'patched';           Fail = '\bFAIL\b' }
  @{ Name = "mainmenu_refresh_pi8 (refresh)";   Marker = "mainmenu-refresh-pi8-marker.txt"; Ready = 'hook built|\[armed\]|\[CALLED\]'; Fail = '\bFAIL\b' }
  @{ Name = "loadout_fix (customization)";      Marker = "loadout-fix-marker.txt";       Ready = 'Refresh fired|cust=1|mm=1'; Fail = '\bFAIL\b' }
  @{ Name = "missions_fix (missions page)";     Marker = "missions-fix-marker.txt";      Ready = 'swapped|apply#';    Fail = '\[2\] FAIL|apply FAILED' }
)

# Get-ShimState classifies a shim. $gameStart (nullable DateTime) anchors "this launch": a marker last
# written AT/AFTER the game started belongs to this launch (so a shim that succeeded then went quiet is
# still READY, not "stale"); a marker written before it is a leftover. When the game isn't running or its
# start time is inaccessible (elevated process, non-elevated caller), fall back to the -StaleSec age gate.
function Get-ShimState($shim, $gameStart) {
  $path = Join-Path $Repo "docs\$($shim.Marker)"
  if (-not (Test-Path $path)) {
    return [pscustomobject]@{ Name=$shim.Name; State="absent"; Age=$null; Last="(no marker)" }
  }
  $item = Get-Item $path
  $ageSec = [int]((Get-Date) - $item.LastWriteTime).TotalSeconds
  $text = Get-Content $path -Raw -ErrorAction SilentlyContinue
  $lines = @(Get-Content $path -ErrorAction SilentlyContinue | Where-Object { $_ -match '\S' })
  $last = if ($lines.Count) { $lines[-1].Trim() } else { "(empty)" }

  # Does this marker belong to the current launch?
  if ($null -ne $gameStart) { $thisLaunch = ($item.LastWriteTime -ge $gameStart) }
  else                      { $thisLaunch = ($ageSec -le $StaleSec) }   # no anchor -> age heuristic

  if (-not $thisLaunch) {
    $state = "leftover"   # marker is from a previous launch; this shim was not injected this session
  } elseif ($text -and ($text -match $shim.Fail)) {
    $state = "FAILED"
  } elseif ($text -and ($text -match $shim.Ready)) {
    $state = "READY"
  } else {
    $state = "running"
  }

  [pscustomobject]@{ Name=$shim.Name; State=$state; Age=$ageSec; Last=$last }
}

function Show-Once {
  $gameProc = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue
  $gameUp = [bool]$gameProc
  $agsUp  = [bool](Get-Process ags -ErrorAction SilentlyContinue)
  # Anchor "this launch" to the game's start time when we can read it (may throw for an elevated
  # process from a non-elevated shell — then $gameStart stays null and Get-ShimState uses the age gate).
  $gameStart = $null
  if ($gameProc) { try { $gameStart = ($gameProc | Select-Object -First 1).StartTime } catch { $gameStart = $null } }
  Write-Host ""
  Write-Host ("SUPERVIVE Revival - shim readiness  ({0})" -f (Get-Date -Format "HH:mm:ss")) -ForegroundColor White
  $anchor = if ($null -ne $gameStart) { "game up since {0}" -f $gameStart.ToString("HH:mm:ss") } elseif ($gameUp) { "game up (start time unreadable - using age gate)" } else { "game not running" }
  Write-Host ("  {0}    ags: {1}" -f $anchor, $(if($agsUp){"RUNNING"}else{"not running"})) -ForegroundColor DarkGray
  Write-Host ("  {0,-34} {1,-9} {2,7}   {3}" -f "shim","state","age(s)","last marker line") -ForegroundColor DarkGray
  foreach ($sh in $shims) {
    $r = Get-ShimState $sh $gameStart
    $color = switch ($r.State) {
      "READY"    { "Green" }
      "running"  { "Yellow" }
      "FAILED"   { "Red" }
      "leftover" { "DarkGray" }
      default    { "DarkGray" }
    }
    $age = if ($null -eq $r.Age) { "-" } else { $r.Age }
    $lastTrim = if ($r.Last.Length -gt 66) { $r.Last.Substring(0,63) + "..." } else { $r.Last }
    Write-Host ("  {0,-34} {1,-9} {2,7}   {3}" -f $sh.Name, $r.State, $age, $lastTrim) -ForegroundColor $color
  }
  if (-not $gameUp) {
    Write-Host "  (game not running - every row is a leftover marker from a previous launch)" -ForegroundColor DarkGray
  }
}

if ($Watch) {
  try { while ($true) { Clear-Host; Show-Once; Write-Host "`n  -Watch: refreshing every ${IntervalSec}s (Ctrl+C to stop)" -ForegroundColor DarkGray; Start-Sleep -Seconds $IntervalSec } }
  catch [System.Management.Automation.PipelineStoppedException] { }
} else {
  Show-Once
}
