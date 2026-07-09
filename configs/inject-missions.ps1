<#
.SYNOPSIS
  Detached injector for the durable Missions shim (Option 2, 2d).

  launch-redirect.ps1 -Missions injects the PRIMARY hook (catalog_store_fix.dll) at launch, then spawns
  THIS script to inject missions_fix.dll AFTER the primary has installed + self-unhooked, so two
  thread-suspending hook installs never race. missions_fix.dll is the SOLE ProcessInternal-hooking shim in
  this mode (the pick/refresh secondary mainmenu_refresh_pi8 also hooks ProcessInternal, so it is NOT
  injected in -Missions mode — the two PI-hookers cannot coexist).

  missions_fix self-defers its own work until ProgMgr / MissionsModel + the native funcs resolve (menu
  load), so exact timing is not critical; we only gate on the primary's hook being installed+removed.

  Spawned detached+hidden by launch-redirect.ps1 so it outlives that script.
#>
param(
  [string]$Repo = (Split-Path -Parent $PSScriptRoot),
  [int]$MaxWaitProcSec = 150,
  [int]$MaxWaitUnhookSec = 120
)
$ErrorActionPreference = "SilentlyContinue"
$name    = "SUPERVIVE-Win64-Shipping.exe"
$inject  = Join-Path $Repo "tools\inject\inject.exe"
$primaryMarker = Join-Path $Repo "docs\catalog-store-fix-marker.txt"
$log     = Join-Path $Repo "docs\inject-missions.log"
# missions_fix + the pick/refresh + pick-commit secondaries. missions_fix and mainmenu_refresh_pi8 BOTH hook
# ProcessInternal but coordinate via a shared named mutex ("Local\SuperviveMissionsPIHook"), so they coexist.
# catalog_pick_fix only does Script patches (no PI hook), so it's independent. Inject pi8 first so it captures
# the original prologue before missions_fix does its first apply.
$dlls = @(
  "tools\sigbypass-mod\mainmenu_refresh_pi8.dll",
  "tools\sigbypass-mod\catalog_pick_fix.dll",
  "tools\sigbypass-mod\missions_fix.dll"
)

function Log($m){ "$([DateTime]::Now.ToString('HH:mm:ss'))  $m" | Out-File -FilePath $log -Append -Encoding ascii }
"" | Out-File -FilePath $log -Encoding ascii   # truncate for this launch
Log "missions injector started (repo=$Repo)"

if (-not (Test-Path $inject)) { Log "inject.exe not found at $inject - aborting"; return }

# 1) wait for the game process
$deadline = (Get-Date).AddSeconds($MaxWaitProcSec); $up = $false
while ((Get-Date) -lt $deadline) { if (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue) { $up = $true; break }; Start-Sleep -Seconds 1 }
if (-not $up) { Log "game process never appeared within ${MaxWaitProcSec}s - aborting"; return }
Log "game process is up"

# 2) wait for the primary hook to install AND self-unhook (marker "[unhook]") so its thread-suspending
#    SafeWrite is finished before missions_fix installs its own hook. Fallback: proceed after timeout.
$deadline = (Get-Date).AddSeconds($MaxWaitUnhookSec); $ready = $false
while ((Get-Date) -lt $deadline) {
  if (Test-Path $primaryMarker) { $c = Get-Content $primaryMarker -Raw -ErrorAction SilentlyContinue; if ($c -and $c -match '\[unhook\]') { $ready = $true; break } }
  if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) { Log "game exited while waiting for primary unhook - aborting"; return }
  Start-Sleep -Milliseconds 500
}
if ($ready) { Log "primary catalog_store_fix installed+unhooked - safe to inject missions_fix" }
else { Log "WARNING: primary [unhook] not seen in ${MaxWaitUnhookSec}s - injecting missions_fix anyway" }

# 3) inject each shim sequentially (gap between to avoid overlapping hook installs; the mutex also guards)
foreach ($d in $dlls) {
  if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) { Log "game exited - stopping"; return }
  $path = Join-Path $Repo $d
  if (-not (Test-Path $path)) { Log "MISSING: $path - skipping"; continue }
  Log "injecting $d ..."
  $out = & $inject mmap $name $path 2>&1
  Log ($out -join " | ")
  Start-Sleep -Seconds 3
}
Log "injection complete (missions_fix polls ags; pi8 pick/refresh + catalog_pick_fix active)"
