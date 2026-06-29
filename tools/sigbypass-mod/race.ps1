# race.ps1 -- start the SigBypass watcher + game launcher in the SAME session, wait
# for the marker file (proves DllMain ran the patch), and report pak-mount result.
#
# Sequence:
#   1. Kill stragglers (game, ags, go).
#   2. Retry the launch up to 4 times to defeat the intermittent hosts-file race.
#   3. Start the watcher BEFORE the actual game launch so it is polling for the proc.
#   4. Poll for the marker file; bail on watcher exit / marker present / 30s timeout.

$ErrorActionPreference = 'Continue'

Get-Process SUPERVIVE-Win64-Shipping,ags,go -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

$inject = "G:\git\Supervive Revival Project\tools\inject\inject.exe"
$dll = "G:\git\Supervive Revival Project\tools\sigbypass-mod\main.dll"
$watchOut = "G:\git\Supervive Revival Project\docs\watch-race.log"
$launchOut = "G:\git\Supervive Revival Project\docs\launch-race.log"
$marker = "G:\git\Supervive Revival Project\docs\sigbypass-marker.txt"
Remove-Item $watchOut, $launchOut, $marker -ErrorAction SilentlyContinue -Force

Write-Host "[race] starting watcher (watch-now -- DLL spin-waits for prologue itself)"
$watcher = Start-Job -Name 'WATCH' -ScriptBlock {
  param($inj, $d, $out)
  & $inj watch-now "SUPERVIVE-Win64-Shipping.exe" $d *>&1 | Tee-Object -FilePath $out
} -ArgumentList $inject, $dll, $watchOut
Start-Sleep -Milliseconds 200

for ($try = 1; $try -le 4; $try++) {
  Write-Host "[race] launch attempt $try"
  $launcher = Start-Job -Name "LAUNCH$try" -ScriptBlock {
    param($out)
    Set-Location "G:\git\Supervive Revival Project"
    & .\configs\launch-redirect.ps1 *>&1 | Tee-Object -FilePath $out
  } -ArgumentList $launchOut
  $waited = 0
  $alive = $false
  while ($waited -lt 25) {
    Start-Sleep -Milliseconds 500
    $waited += 0.5
    if (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue) {
      $alive = $true
      Write-Host "[race] game alive after ${waited}s"
      break
    }
  }
  if ($alive) { break }
  Write-Host "[race] launch attempt $try failed, cleaning up"
  Get-Job -Name "LAUNCH$try" | Remove-Job -Force -ErrorAction SilentlyContinue
  Get-Process ags -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 5
}

if (-not (Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)) {
  Write-Host "[race] FAILED to launch game after 4 attempts"
  Get-Job -Name 'WATCH' | Stop-Job -ErrorAction SilentlyContinue
  return
}

Write-Host "[race] waiting for marker..."
$waited = 0
while ($waited -lt 30) {
  Start-Sleep -Milliseconds 500
  $waited += 0.5
  if (Test-Path $marker) {
    Write-Host "[race] MARKER appeared after ${waited}s"
    break
  }
  $ws = (Get-Job -Name 'WATCH' -ErrorAction SilentlyContinue).State
  if ($ws -ne 'Running') {
    Write-Host "[race] watcher exited (state=$ws) at ${waited}s"
    break
  }
}

Write-Host ""
Write-Host "=== WATCHER OUTPUT ==="
if (Test-Path $watchOut) { Get-Content $watchOut } else { "(no watch log)" }
Write-Host ""
Write-Host "=== MARKER ==="
if (Test-Path $marker) { Get-Content $marker } else { "(no marker)" }
Write-Host ""
Write-Host "=== PAK MOUNT RESULT (Loki.log) ==="
$log = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"
if (Test-Path $log) {
  Select-String -Path $log -Pattern 'pakchunk999|Premade AssetRegistry|Mounted Pak file.*pakchunk0-Windows' -ErrorAction SilentlyContinue | Select-Object LineNumber, Line | Format-Table -Wrap -AutoSize | Out-String -Width 220
}
Write-Host ""
Write-Host "=== PROCESSES ==="
Get-Process | Where-Object { $_.ProcessName -match 'SUPERVIVE|ags' } | Select-Object Id, ProcessName, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}}, @{N='WS(MB)';E={[math]::Round($_.WorkingSet64/1MB)}}
