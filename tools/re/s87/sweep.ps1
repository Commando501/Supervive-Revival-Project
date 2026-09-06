$ErrorActionPreference = 'SilentlyContinue'
$stubExe = 'H:\Unreal Engine\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$uproj   = 'G:\git\Supervive Revival Project\unreal-stub\Loki.uproject'
$clog    = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
$results = 'C:\Temp\sweep-results.txt'
"=== S87 bit-injection sweep $(Get-Date) ===" | Out-File $results
$Ns = @(8,9,10,11,12,13)
foreach ($N in $Ns) {
  Get-Process UnrealEditor-Cmd,SUPERVIVE-Win64-Shipping -EA SilentlyContinue | Stop-Process -Force
  Start-Sleep 3
  $slog = "C:\Temp\DsSweep_$N.log"
  Remove-Item $slog -EA SilentlyContinue
  Start-Process $stubExe -ArgumentList "`"$uproj`"","/Engine/Maps/Entry?listen","-game","-server","-Port=7777","-nullrhi","-NoSplash","-Unattended","-injectbits=$N","-injectpattern=0","-abslog=$slog" -WindowStyle Hidden
  $bound=$false; for($i=0;$i -lt 20;$i++){ Start-Sleep 2; if(Get-NetUDPEndpoint -LocalPort 7777){$bound=$true;break} }
  if(-not $bound){ "N=$N : STUB DID NOT BIND" | Out-File -Append $results; continue }
  Start-Sleep 2
  Set-Location 'G:\git\Supervive Revival Project'
  & .\configs\launch-redirect.ps1 -NoHook *> "C:\Temp\sweep_launch_$N.log"
  # wait for the stub SPLICE line (replication happened), then grab the client error
  $spliced=$false
  for($t=0;$t -lt 12;$t++){
    Start-Sleep 15
    if(Select-String -Path $slog -Pattern "SPLICE \(S87\)" -EA SilentlyContinue){ $spliced=$true; break }
  }
  Start-Sleep 6
  $spline = (Select-String -Path $slog -Pattern "SPLICE \(S87\)" | Select-Object -Last 1).Line -replace '^\[[^]]*\]\[[^]]*\]',''
  $err = (Select-String -Path $clog -Pattern "sub-object class|terminator handle|Invalid replicated field|ReceiveProperties FAILED" | Select-Object -Last 1).Line -replace '^\[[^]]*\]\[[^]]*\]',''
  $entering = if(Select-String -Path $clog -Pattern "Entering game state LokiGameState"){"ENTERED-GAMESTATE"}else{"no-gamestate"}
  $notready = (Select-String -Path $clog -Pattern "feature toggles were not ready" -AllMatches | Measure-Object).Count
  "N=$N spliced=$spliced $entering notready=$notready | ERR: $err" | Out-File -Append $results
  "  splice: $spline" | Out-File -Append $results
}
Get-Process UnrealEditor-Cmd,SUPERVIVE-Win64-Shipping -EA SilentlyContinue | Stop-Process -Force
"=== sweep done ===" | Out-File -Append $results
