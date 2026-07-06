<#
.SYNOPSIS
  Detached secondary-shim injector for the SUPERVIVE revival launch.

  launch-redirect.ps1 injects the PRIMARY hook (catalog_store_fix.dll) at launch via
  inject watch-now — it must beat the grid Construct to open the IsCatalogDataReady gate.
  This helper injects the SECONDARY shims AFTER the primary has finished and self-unhooked,
  so two thread-suspending hook installs never race:
    - mainmenu_refresh_pi8.dll  (pick mirror + main-menu/HUNTERS refresh; hooks ProcessInternal)
    - catalog_pick_fix.dll      (IsPreviewable/IsUseable Script patches so owned clicks commit)

  Spawned detached+hidden by launch-redirect.ps1 so it outlives that script (the game exe
  detaches and the launcher exits). Both secondaries self-defer their own work until their
  target objects exist, so exact timing is not critical — we only gate on the primary's
  hook being installed+removed to avoid a concurrent SafeWrite.
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
$log     = Join-Path $Repo "docs\inject-secondaries.log"
# Injected AFTER the primary: pi8 first (installs its ProcessInternal hook), then the
# heap-only tile patcher.
$dlls = @(
  "tools\sigbypass-mod\mainmenu_refresh_pi8.dll",
  "tools\sigbypass-mod\catalog_pick_fix.dll"
)

function Log($m){ "$([DateTime]::Now.ToString('HH:mm:ss'))  $m" | Out-File -FilePath $log -Append -Encoding ascii }
"" | Out-File -FilePath $log -Encoding ascii   # truncate for this launch
Log "secondary injector started (repo=$Repo)"

if (-not (Test-Path $inject)) { Log "inject.exe not found at $inject — aborting"; return }

# 1) wait for the game process
$deadline = (Get-Date).AddSeconds($MaxWaitProcSec); $up = $false
while ((Get-Date) -lt $deadline) { if (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue) { $up = $true; break }; Start-Sleep -Seconds 1 }
if (-not $up) { Log "game process never appeared within ${MaxWaitProcSec}s — aborting"; return }
Log "game process is up"

# 2) wait for the primary hook to install AND self-unhook (marker "[unhook]") so its
#    thread-suspending SafeWrite is finished before pi8 installs its own hook. Fallback:
#    proceed after the timeout with a warning.
$deadline = (Get-Date).AddSeconds($MaxWaitUnhookSec); $ready = $false
while ((Get-Date) -lt $deadline) {
  if (Test-Path $primaryMarker) { $c = Get-Content $primaryMarker -Raw -ErrorAction SilentlyContinue; if ($c -and $c -match '\[unhook\]') { $ready = $true; break } }
  if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) { Log "game exited while waiting for primary unhook — aborting"; return }
  Start-Sleep -Milliseconds 500
}
if ($ready) { Log "primary catalog_store_fix installed+unhooked — safe to inject secondaries" }
else { Log "WARNING: primary [unhook] not seen in ${MaxWaitUnhookSec}s — injecting secondaries anyway" }

# 3) inject each secondary sequentially (gap between to avoid overlapping hook installs)
foreach ($d in $dlls) {
  if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) { Log "game exited — stopping"; return }
  $path = Join-Path $Repo $d
  if (-not (Test-Path $path)) { Log "MISSING: $path — skipping"; continue }
  Log "injecting $d ..."
  $out = & $inject mmap $name $path 2>&1
  Log ($out -join " | ")
  Start-Sleep -Seconds 3
}
Log "secondary injection complete"
