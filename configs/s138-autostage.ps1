<#
  s138-autostage.ps1 -- launch/settle/arm/stage the tutorial world, retrying across FK-31 deaths.

  WHY: FK-31 kills ~27% of launches during staging (only gft+fo resident, before the probe).
  Driving that by hand is one round-trip per attempt for an outcome that is pure coin-flip.
  This loops the DOCUMENTED procedure unchanged -- it does not weaken any gate:

    1. archive any pending crash dump   (the NEXT launch clears crashpad, so this must go first)
    2. launch-redirect.ps1 -NoHook      (with the armqueue env knobs)
    3. settle gate: uptime >= MinUptime AND TryUIReady SUCCESS AND LobbyV2_Persistent
    4. POST joinQueue, wait for a non-empty MatchID
    5. fk24-stage.ps1 -SkipProbe        (gft -> fo -> sp)
    6. success == '[SP] done step=4' in docs/tutorial-launch-marker.txt AND the process alive

  It injects NO probe. Staging and the injection decision stay decoupled, exactly as the
  S138 procedure requires -- you inject by hand afterwards into the staged client.

  Read-only w.r.t. the game. Run from an ELEVATED PowerShell.
#>
[CmdletBinding()]
param(
  [int]$MaxAttempts  = 6,
  [int]$MinUptimeSec = 125,
  [int]$SettleTimeoutSec = 420,
  [int]$ArmTimeoutSec    = 150,
  [string]$Label     = "s138auto",
  [string]$PlayerId  = "9b9d2c887e2524f918e383a895f2f1c2"
)
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$log  = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"
function Say($m){ Write-Host "[auto] $m" -ForegroundColor Cyan }

for($attempt=1; $attempt -le $MaxAttempts; $attempt++){
  Say "================ ATTEMPT $attempt / $MaxAttempts ================"

  # 1. archive whatever the previous death left; the next launch would clear it
  & "$repo\configs\archive-crashdumps.ps1" -Label "$Label-a$attempt" 2>&1 |
      Select-String -Pattern 'archived to|no pending' | ForEach-Object { Say $_.ToString().Trim() }

  # 2. launch
  Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue | ForEach-Object {
      Say "a stale client (PID $($_.Id)) is running; leaving it alone and aborting"; exit 9 }
  $env:AGS_ARM_QUEUE='arm'; $env:AGS_ARM_QUEUE_DELAY='8s'; $env:AGS_ARM_QUEUE_QUEUES='bots'
  Say "launching..."
  & "$repo\configs\launch-redirect.ps1" -NoHook 2>&1 | Out-Null

  $proc = $null
  for($i=0;$i -lt 60 -and -not $proc;$i++){
      $proc = Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue | Select-Object -First 1
      if(-not $proc){ Start-Sleep -Seconds 2 } }
  if(-not $proc){ Say "no game process appeared; retrying"; continue }
  $gamePid = $proc.Id
  $base = "0x{0:X}" -f $proc.MainModule.BaseAddress.ToInt64()
  Say "PID=$gamePid BASE=$base started=$($proc.StartTime)"

  # 3. settle gate
  $settled = $false
  while($true){
    if(-not (Get-Process -Id $gamePid -ErrorAction SilentlyContinue)){ Say "DIED during settle"; break }
    $up = [int]((Get-Date) - $proc.StartTime).TotalSeconds
    if($up -gt $SettleTimeoutSec){ Say "settle TIMEOUT at ${up}s"; break }
    $ui=0; $lob=0
    try{
      $fs = New-Object IO.FileStream($log,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
      $sr = New-Object IO.StreamReader($fs)
      $txt = $sr.ReadToEnd(); $sr.Close(); $fs.Close()
      $ui  = ([regex]::Matches($txt,'TryUIReady SUCCESS')).Count
      $lob = ([regex]::Matches($txt,'LobbyV2_Persistent')).Count
    } catch { }
    if($up -ge $MinUptimeSec -and $ui -ge 1 -and $lob -ge 1){
        Say "SETTLE PASSED up=${up}s ui=$ui lob=$lob"; $settled=$true; break }
    Start-Sleep -Seconds 5
  }
  if(-not $settled){ Stop-Process -Id $gamePid -Force -ErrorAction SilentlyContinue; continue }

  # 4. arm the queue
  try{
    $r = Invoke-WebRequest -Method POST -TimeoutSec 10 -UseBasicParsing `
         -Headers @{ 'User-Agent' = 's138auto-arm-NOT-THE-GAME' } `
         -Uri "http://127.0.0.1:8080/party/parties/party-$PlayerId/joinQueue"
    Say "joinQueue -> $($r.StatusCode)"
  } catch { Say "joinQueue failed: $($_.Exception.Message)" }

  $armed=$false; $t0=Get-Date
  while(((Get-Date)-$t0).TotalSeconds -lt $ArmTimeoutSec){
    if(-not (Get-Process -Id $gamePid -ErrorAction SilentlyContinue)){ Say "DIED during arm"; break }
    try{
      $j = (Invoke-WebRequest -TimeoutSec 5 -UseBasicParsing `
            -Headers @{ 'User-Agent' = 's138auto-verify-NOT-THE-GAME' } `
            -Uri "http://127.0.0.1:8080/core-game/players/$PlayerId").Content | ConvertFrom-Json
      if($j.MatchID){ Say "ARMED MatchID=$($j.MatchID)"; $armed=$true; break }
    } catch { }
    Start-Sleep -Seconds 4
  }
  if(-not $armed){ Stop-Process -Id $gamePid -Force -ErrorAction SilentlyContinue; continue }

  # 5. stage
  Say "staging (gft -> fo -> sp)..."
  & "$repo\configs\fk24-stage.ps1" -Probe "$repo\tools\sigbypass-mod\build\tutorial_launch_botspawn.dll" `
      -Label "$Label-a$attempt" -AllowStale -SkipProbe 2>&1 |
      Select-String -Pattern 'inject |LVL_Tutorial load|done step|ABORTING|stage complete|GAME PROCESS GONE' |
      ForEach-Object { Say $_.ToString().Trim() }

  # 6. verdict
  # ⚠⚠ DEFECT FIXED 2026-08-23, AND IT COST THREE LAUNCHES. This used to test the marker for
  #    'done step=4' IMMEDIATELY after fk24-stage.ps1 returned. But 'stage complete' is printed when
  #    the stager has finished INJECTING sp -- sp then does its spawn+possess work asynchronously and
  #    writes 'done step=4' some seconds LATER. So the check raced, read a marker holding only the
  #    injection header, declared "did not stage", and then Stop-Process'd a client that had staged
  #    PERFECTLY. Three consecutive launches were destroyed that way and very nearly recorded as a
  #    fourth consecutive FK-31 death -- i.e. an instrument fault about to be written down as a
  #    property of the game, which is this project's single most-repeated error.
  #    Now: POLL for the marker, and never kill a client until it is CONFIRMED not staged.
  $marker = "$repo\docs\tutorial-launch-marker.txt"
  $ok = $false
  $t1 = Get-Date
  while(((Get-Date)-$t1).TotalSeconds -lt 180){
    if(-not (Get-Process -Id $gamePid -ErrorAction SilentlyContinue)){ Say "client died while waiting for [SP] done"; break }
    if((Test-Path $marker)){
      try{
        $fs2 = New-Object IO.FileStream($marker,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
        $sr2 = New-Object IO.StreamReader($fs2); $mtxt = $sr2.ReadToEnd(); $sr2.Close(); $fs2.Close()
        if($mtxt -match 'done step=4'){ $ok = $true; Say "[SP] done step=4 observed after $([int]((Get-Date)-$t1).TotalSeconds)s"; break }
      } catch { }
    }
    Start-Sleep -Seconds 3
  }
  if(-not $ok -and (Get-Process -Id $gamePid -ErrorAction SilentlyContinue)){
    Say "180s elapsed with no 'done step=4' though the client is ALIVE -- leaving it running rather"
    Say "than killing it; inspect docs/tutorial-launch-marker.txt by hand."
    "$gamePid $base" | Set-Content -Encoding ascii "$repo\docs\s138-staged-pid.txt"
    exit 2
  }
  if($ok){
    Say "***** STAGED OK on attempt $attempt *****"
    Say "PID=$gamePid  BASE=$base"
    "$gamePid $base" | Set-Content -Encoding ascii "$repo\docs\s138-staged-pid.txt"
    exit 0
  }
  Say "attempt $attempt did not stage; cycling"
  Stop-Process -Id $gamePid -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 3
}
Say "exhausted $MaxAttempts attempts without staging"
exit 1
