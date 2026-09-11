# fly-wasd.ps1 -- S189-MV-WASD flight orchestration.
#
# Sequence:
#   t=-3s  : run preflight_read.py (snapshot state, save to evidence)
#   t=-1s  : start motion_watch_player.py in background (CSV to evidence file)
#   t=0    : run send-wasd.ps1 (focus + WASD sequence)
#   ~t=+30s: motion probe finishes
#   t=+31s : run preflight_read.py again (post-state snapshot)
#
# Params default to the F1 flight design (no gravity poke; WASD-in-air test).
#
# All evidence goes to scratchpad/s189-mv/evidence/<label>-*.txt

[CmdletBinding()]
param(
    [int]$GamePid = 1780,
    [string]$Base = '0x7FF68E160000',
    [string]$Hero = '0x1931C76AAC0',
    [string]$Cmc  = '0x193108438F0',
    [string[]]$Sequence = @('w','d','f13'),
    [int]$HoldMs = 3000,
    [int]$InterKeyMs = 2000,
    [int]$RepeatMs = 33,
    [int]$ProbeDurSec = 18,
    [string]$Label = 'f1'
)
$ErrorActionPreference = 'Stop'

$repo = 'G:\git\Supervive Revival Project'
$evDir = "$repo\scratchpad\s189-mv\evidence"
if (-not (Test-Path $evDir)) { New-Item -ItemType Directory -Force -Path $evDir | Out-Null }

$prefile  = "$evDir\$Label-preflight.txt"
$csvfile  = "$evDir\$Label-motion.csv"
$logfile  = "$evDir\$Label-motion.stderr.txt"
$wasdfile = "$evDir\$Label-wasd.log"
$postfile = "$evDir\$Label-postflight.txt"
$summary  = "$evDir\$Label-SUMMARY.txt"

Write-Host "=== S189-MV-WASD flight $Label ===" -ForegroundColor Cyan
Write-Host "PID=$GamePid Base=$Base Hero=$Hero CMC=$Cmc"
Write-Host "Sequence=$($Sequence -join ',') Hold=${HoldMs}ms Gap=${InterKeyMs}ms ProbeDur=${ProbeDurSec}s"
Write-Host ""

# 1. Preflight snapshot
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] pre-flight state..." -ForegroundColor Yellow
$out = & py "$repo\scratchpad\s189-mv\tools\preflight_read.py" $GamePid $Base $Hero $Cmc 2>&1
$out | Out-File -FilePath $prefile -Encoding utf8
$out | Write-Host
Write-Host ""

# 2. Start motion probe (background)
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] starting motion probe (bg, ${ProbeDurSec}s)..." -ForegroundColor Yellow
$probeScriptQ = '"' + "$repo\scratchpad\s189-mv\tools\motion_watch_player.py" + '"'
$probeArgs = @($probeScriptQ, $GamePid, $Hero, $Cmc, $ProbeDurSec)
$probeProc = Start-Process -FilePath 'py' -ArgumentList $probeArgs `
    -RedirectStandardOutput $csvfile -RedirectStandardError $logfile `
    -NoNewWindow -PassThru
Write-Host "  probe PID = $($probeProc.Id)  -> $csvfile"

# 3. Give the probe a moment to start (2 samples before we send input)
Start-Sleep -Seconds 2

# 4. Send WASD
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] sending WASD sequence..." -ForegroundColor Yellow
$syncFile = "$evDir\$Label-sync.txt"
if (Test-Path $syncFile) { Remove-Item $syncFile -Force }
$wasdArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    "$repo\scratchpad\s189-mv\tools\send-wasd.ps1",
    '-Sequence', ('"' + ($Sequence -join ',') + '"'),
    '-HoldMs', $HoldMs,
    '-InterKeyMs', $InterKeyMs,
    '-RepeatMs', $RepeatMs,
    '-SyncFile', $syncFile
)
$wasdOut = & powershell $wasdArgs 2>&1
$wasdOut | Out-File -FilePath $wasdfile -Encoding utf8
$wasdOut | Write-Host

# 5. Wait for probe to finish
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] waiting for probe to complete..." -ForegroundColor Yellow
$probeProc.WaitForExit()
Write-Host "  probe done"
Write-Host ""

# 6. Postflight snapshot
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] post-flight state..." -ForegroundColor Yellow
$out2 = & py "$repo\scratchpad\s189-mv\tools\preflight_read.py" $GamePid $Base $Hero $Cmc 2>&1
$out2 | Out-File -FilePath $postfile -Encoding utf8
$out2 | Write-Host
Write-Host ""

# 7. Summary
Write-Host "=== FLIGHT $Label SUMMARY ===" -ForegroundColor Cyan
$header = "S189-MV-WASD Flight $Label -- $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
"" > $summary
$header | Add-Content $summary
'' | Add-Content $summary
'--- PREFLIGHT ---' | Add-Content $summary
Get-Content $prefile | Add-Content $summary
'' | Add-Content $summary
'--- WASD LOG ---' | Add-Content $summary
Get-Content $wasdfile | Add-Content $summary
'' | Add-Content $summary
'--- MOTION STDERR (summary lines) ---' | Add-Content $summary
Get-Content $logfile | Add-Content $summary
'' | Add-Content $summary
'--- POSTFLIGHT ---' | Add-Content $summary
Get-Content $postfile | Add-Content $summary
'' | Add-Content $summary
'--- MOTION CSV (first 30 rows and last 20 rows) ---' | Add-Content $summary
$csvLines = Get-Content $csvfile
if ($csvLines.Count -gt 50) {
    $csvLines[0..29] | Add-Content $summary
    '...' | Add-Content $summary
    $csvLines[($csvLines.Count-20)..($csvLines.Count-1)] | Add-Content $summary
} else {
    $csvLines | Add-Content $summary
}

Write-Host "Summary written to $summary"
Write-Host "Full CSV: $csvfile"
