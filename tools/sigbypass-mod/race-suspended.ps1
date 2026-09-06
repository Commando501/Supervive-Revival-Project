# race-suspended.ps1 -- launch the game suspended, inject SigBypass while paused,
# then resume. This is the only way to beat the engine's pak mount loop, which
# fires within the first few hundred milliseconds of process start.

$ErrorActionPreference = 'Continue'

Get-Process SUPERVIVE-Win64-Shipping,ags,go -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

$marker = "G:\git\Supervive Revival Project\docs\sigbypass-marker.txt"
Remove-Item $marker -ErrorAction SilentlyContinue -Force

# Step 1: do the env setup (server, hosts, cert) WITHOUT launching the game.
# launch-redirect.ps1 has a -NoLaunch flag for exactly this.
Write-Host "[race] setting up server + redirect (NoLaunch)..."
for ($try = 1; $try -le 4; $try++) {
  Write-Host "[race] setup attempt $try"
  $setup = Start-Job -Name "SETUP$try" -ScriptBlock {
    Set-Location "G:\git\Supervive Revival Project"
    & .\configs\launch-redirect.ps1 -NoLaunch *>&1
  }
  Wait-Job $setup -Timeout 30 | Out-Null
  $out = Receive-Job $setup
  Remove-Job $setup -Force
  if (Get-Process ags -ErrorAction SilentlyContinue) {
    Write-Host "[race] setup succeeded on attempt $try"
    break
  }
  Write-Host "[race] setup attempt $try failed (hosts-file race?)"
  Get-Process ags -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 5
}

if (-not (Get-Process ags -ErrorAction SilentlyContinue)) {
  Write-Host "[race] FAILED setup after 4 attempts -- aborting"
  return
}

# Step 2: build the -ini args (same as launch-redirect.ps1) and call inject launch
$ab   = "/Script/AccelByteUe4Sdk.AccelByteSettings"
$loki = "/Script/Loki.LokiGameProjectSettings"
$local = "http://localhost:8080"
$exe = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
$dll = "G:\git\Supervive Revival Project\tools\sigbypass-mod\main.dll"
$inject = "G:\git\Supervive Revival Project\tools\inject\inject.exe"
$iniArgs = @(
  "-ini:Engine:[$ab]:BaseUrl=$local",
  "-ini:Engine:[$ab]:IamServerUrl=$local/iam",
  "-ini:Engine:[$ab]:PlatformServerUrl=$local/platform",
  "-ini:Engine:[$ab]:BasicServerUrl=$local/basic",
  "-ini:Engine:[$ab]:LobbyServerUrl=ws://localhost:8080/lobby/",
  "-ini:Engine:[$loki]:ProdPostAuthURL=$local",
  "-ini:Engine:[$loki]:ProdClientConfigURL=$local",
  "-ini:Game:[$loki]:ProdPostAuthURL=$local",
  "-ini:Game:[$loki]:ProdClientConfigURL=$local",
  "-log"
)
Write-Host "[race] launching suspended + injecting SigBypass.dll..."
& $inject launch $exe $dll @iniArgs 2>&1 | Tee-Object -FilePath "G:\git\Supervive Revival Project\docs\inject-launch.log"

Write-Host ""
Write-Host "[race] waiting for marker (DLL worker thread should patch within ~1s)..."
$waited = 0
while ($waited -lt 30) {
  Start-Sleep -Milliseconds 250
  $waited += 0.25
  if (Test-Path $marker) {
    $sz = (Get-Item $marker).Length
    if ($sz -gt 400) {  # full marker file is ~700 bytes
      Write-Host "[race] full marker present after ${waited}s ($sz bytes)"
      break
    }
  }
}

Write-Host ""
Write-Host "=== MARKER ==="
if (Test-Path $marker) { Get-Content $marker } else { "(no marker)" }
Write-Host ""
Write-Host "=== PAK MOUNT RESULT ==="
$log = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"
if (Test-Path $log) {
  Select-String -Path $log -Pattern 'pakchunk999|Premade AssetRegistry|Mounted Pak file.*pakchunk0-Windows|Failed to mount' -ErrorAction SilentlyContinue | Select-Object LineNumber, Line | Format-Table -Wrap -AutoSize | Out-String -Width 220
}
Write-Host ""
Write-Host "=== PROCS ==="
Get-Process | Where-Object { $_.ProcessName -match 'SUPERVIVE|ags' } | Select-Object Id, ProcessName, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}}, @{N='WS(MB)';E={[math]::Round($_.WorkingSet64/1MB)}}
