# S88 toggle-PAYLOAD sweep: fix -injectbits=11, vary -toggleseed / -postbits / -paybits, run ONE full DS
# cycle, and capture the client outcome + the stub's spliced ServerAuthConfig content block.
# Usage (elevated PS, Steam running):  .\tools\re\s87\sweep_seed.ps1 -Seed 151 -PostBits 8
# ROBUSTNESS: the client Loki.log persists between launches, so we DELETE it each cycle and gate every
# outcome on THIS cycle's stub SPLICE line (fresh per cycle) — otherwise the poll breaks on a STALE
# field-12 error from the previous cycle before the new game even connects (the S88 stale-log bug).
param([int]$Seed = 151, [int]$InjectBits = 11, [int]$PollSeconds = 210,
      [int]$PayBits = 0, [int]$PayAt = 25, [int]$PayPat = 0,
      [int]$PostBits = 0, [int]$PostPat = 0)
$ErrorActionPreference = 'SilentlyContinue'
$repo  = 'G:\git\Supervive Revival Project'
$stub  = 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$uproj = "$repo\unreal-stub\Loki.uproject"
$clog  = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
$slog  = "C:\Temp\DsSeed_$Seed.log"
$tag   = "s${Seed}_p${PostBits}_pay${PayBits}"
$carc  = "C:\Temp\Client_$tag.log"
$errPat = 'sub-object class|Sub-object cannot|Invalid replicated field|terminator handle|ReadFieldHeaderAndPayload: Error|ReadContentBlockPayload FAILED|ReadContentBlockHeader FAILED|ReceiveProperties FAILED|Replicator.ReceivedBunch failed'

Get-Process UnrealEditor-Cmd,SUPERVIVE-Win64-Shipping -EA SilentlyContinue | Stop-Process -Force
Start-Sleep 3
Remove-Item $slog -EA SilentlyContinue
Remove-Item $clog -Force -EA SilentlyContinue      # kill the stale client log so the poll can't read the prior cycle's error
Start-Process $stub -ArgumentList "`"$uproj`"","/Engine/Maps/Entry?listen","-game","-server","-Port=7777","-nullrhi","-NoSplash","-Unattended","-injectbits=$InjectBits","-toggleseed=$Seed","-paybits=$PayBits","-payat=$PayAt","-paypat=$PayPat","-postbits=$PostBits","-postpat=$PostPat","-abslog=$slog" -WindowStyle Hidden
$bound=$false; for($i=0;$i -lt 30;$i++){ Start-Sleep 2; if(Get-NetUDPEndpoint -LocalPort 7777 -EA SilentlyContinue){$bound=$true;break} }
if(-not $bound){ "SEED=$Seed POST=$PostBits : STUB DID NOT BIND"; return }
Start-Sleep 3

Set-Location $repo
& .\configs\launch-redirect.ps1 -NoHook *> "C:\Temp\launch_$tag.log"

$deadline=(Get-Date).AddSeconds($PollSeconds)
$sawAlive=$false
while((Get-Date) -lt $deadline){
  Start-Sleep 12
  $proc  = Get-Process SUPERVIVE-Win64-Shipping -EA SilentlyContinue
  $alive = [bool]$proc
  if($alive){ $sawAlive=$true }
  $splice= [bool](Select-String -Path $slog -Pattern 'SPLICE \(S8' -EA SilentlyContinue)   # THIS cycle's replication
  $enter = [bool](Select-String -Path $clog -Pattern 'Entering game state LokiGameState' -EA SilentlyContinue)
  $err   = [bool](Select-String -Path $clog -Pattern $errPat -EA SilentlyContinue)
  $t = if($proc){ [int]((Get-Date)-$proc.StartTime).TotalSeconds } else { -1 }
  if($splice -and $err){ break }                     # replicated then desynced (fail) — gated on THIS cycle's splice
  if($splice -and $enter -and $t -gt 75){ break }    # replicated + entered + stable (hold)
  if($sawAlive -and -not $alive){ break }            # game died after being alive (crash/drop)
}

# ---- capture ----
if(Test-Path $clog){ Copy-Item $clog $carc -Force }
$spliceLine = (Select-String -Path $slog -Pattern 'SPLICE \(S8' | Select-Object -Last 1).Line -replace '^\[[^]]*\]\[[^]]*\]',''
$blockLine  = (Select-String -Path $slog -Pattern 'SPLICED BLOCK'   | Select-Object -Last 1).Line -replace '^\[[^]]*\]\[[^]]*\]',''
$errs = Select-String -Path $clog -Pattern $errPat -EA SilentlyContinue
$errCount = ($errs|Measure-Object).Count
$field = ((Select-String -Path $clog -Pattern 'Invalid replicated field (\d+)' -AllMatches -EA SilentlyContinue | ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value }) | Select-Object -Unique) -join ','
$outField = ((Select-String -Path $clog -Pattern 'OutField: (\w+)' -AllMatches -EA SilentlyContinue | ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value }) | Select-Object -Unique) -join ','
$firstErr = (($errs | Select-Object -First 1).Line -replace '^\[[^]]*\]','').Trim()
$enterLine = (Select-String -Path $clog -Pattern 'Entering game state LokiGameState' | Select-Object -Last 1).Line -replace '^\[[^]]*\]\[[^]]*\]',''
$entered = [bool]$enterLine
$notready = (Select-String -Path $clog -Pattern 'feature toggles were not ready' -EA SilentlyContinue|Measure-Object).Count
$aliveNow = [bool](Get-Process SUPERVIVE-Win64-Shipping -EA SilentlyContinue)
$spliced  = [bool]$spliceLine

$summary = @()
$summary += "============= SEED=$Seed injectbits=$InjectBits postbits=$PostBits paybits=$PayBits payat=$PayAt ============="
$summary += "SPLICE : $spliceLine"
$summary += "BLOCK  : $blockLine"
$summary += "ENTER  : $enterLine"
$summary += "spliced=$spliced errCount=$errCount invalidField=[$field] outField=[$outField] entered=$entered notready=$notready aliveNow=$aliveNow"
$summary += "FIRSTERR: $firstErr"
if($errCount -gt 0){ $errs|Select-Object -First 3|ForEach-Object{ $summary += '   '+($_.Line -replace '^\[[^]]*\]\[[^]]*\]','') } }
$summary += "HOLD=$($aliveNow -and $entered -and $errCount -eq 0)"
$summary += "==============================================================================="
$summary | Tee-Object -FilePath 'C:\Temp\SweepResults.txt' -Append
