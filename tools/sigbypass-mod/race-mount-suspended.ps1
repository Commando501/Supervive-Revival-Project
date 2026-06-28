# race-mount-suspended.ps1 -- launch the game suspended, inject mount_shim.dll,
# then resume. The shim patches FPakSignatureFile::Load, scans for the
# FPakPlatformFile singleton, then queues an APC on the game thread that
# calls Mount(singleton, modDir) to mount our patched AR.bin via a mod pak.
# AR auto-reloads via the FCoreDelegates::OnPakFileMounted2 broadcast.

$ErrorActionPreference = 'Continue'

# Kill any prior game / server.
Get-Process SUPERVIVE-Win64-Shipping,ags,go -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

# Clean marker so we start fresh.
$marker = "G:\git\Supervive Revival Project\docs\mount-shim-marker.txt"
Remove-Item $marker -ErrorAction SilentlyContinue -Force

# Prepare the mod-pak directory: a fresh subdir containing ONLY our patched pak,
# so Mount's default "*.pak" mask finds only this one file.
$modDir = "G:\git\Supervive Revival Project\tools\extractor\out\modpaks"
$srcPak = "G:\git\Supervive Revival Project\tools\extractor\out\pakchunk999-WindowsClient_P.pak"
if (-not (Test-Path $modDir)) {
  New-Item -ItemType Directory -Path $modDir -Force | Out-Null
}
# Wipe + replace so any stale .pak from prior runs is gone.
Get-ChildItem $modDir -Filter *.pak -ErrorAction SilentlyContinue | Remove-Item -Force
if (-not (Test-Path $srcPak)) {
  Write-Host "[race-mount] FATAL: source mod pak missing: $srcPak"
  return
}
Copy-Item $srcPak $modDir -Force
$copied = Get-ChildItem $modDir -Filter *.pak
Write-Host "[race-mount] mod-pak dir prepared:"
$copied | ForEach-Object { Write-Host ("  {0} ({1:N0} bytes)" -f $_.Name, $_.Length) }

# Step 1: env setup (server + hosts + cert) WITHOUT launching the game.
Write-Host "[race-mount] setting up server + redirect (NoLaunch)..."
for ($try = 1; $try -le 4; $try++) {
  Write-Host "[race-mount] setup attempt $try"
  $setup = Start-Job -Name "SETUP$try" -ScriptBlock {
    Set-Location "G:\git\Supervive Revival Project"
    & .\configs\launch-redirect.ps1 -NoLaunch *>&1
  }
  Wait-Job $setup -Timeout 30 | Out-Null
  $out = Receive-Job $setup
  Remove-Job $setup -Force
  if (Get-Process ags -ErrorAction SilentlyContinue) {
    Write-Host "[race-mount] setup succeeded on attempt $try"
    break
  }
  Write-Host "[race-mount] setup attempt $try failed (hosts-file race?)"
  Get-Process ags -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 5
}

if (-not (Get-Process ags -ErrorAction SilentlyContinue)) {
  Write-Host "[race-mount] FAILED setup after 4 attempts -- aborting"
  return
}

# Step 2: build the -ini args (same as launch-redirect.ps1) and call inject launch
$ab    = "/Script/AccelByteUe4Sdk.AccelByteSettings"
$loki  = "/Script/Loki.LokiGameProjectSettings"
$local = "http://localhost:8080"
$exe   = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
$dll   = "G:\git\Supervive Revival Project\tools\sigbypass-mod\mount_shim.dll"
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
if (-not (Test-Path $dll)) {
  Write-Host "[race-mount] FATAL: mount_shim.dll not built yet."
  Write-Host "  Build with:"
  Write-Host "    cd 'G:\git\Supervive Revival Project\tools\sigbypass-mod'"
  Write-Host "    clang++ -shared -O2 mount_shim.cpp -o mount_shim.dll -lkernel32"
  return
}
Write-Host "[race-mount] launching suspended + injecting mount_shim.dll..."
& $inject launch $exe $dll @iniArgs 2>&1 | Tee-Object -FilePath "G:\git\Supervive Revival Project\docs\inject-mount.log"

# Step 3: wait for the marker file to fill in (worker writes it as it progresses).
Write-Host ""
Write-Host "[race-mount] waiting for marker (patch + scan + APC queue happens in worker)..."
$waited = 0
while ($waited -lt 60) {
  Start-Sleep -Milliseconds 500
  $waited += 0.5
  if (Test-Path $marker) {
    $sz = (Get-Item $marker).Length
    # APC line is the last critical event — look for "APC queued" or "Mount returned".
    $content = Get-Content $marker -Raw -ErrorAction SilentlyContinue
    if ($content -match 'Mount returned' -or $content -match 'APC queued') {
      Write-Host "[race-mount] marker reached APC stage after ${waited}s ($sz bytes)"
      break
    }
  }
}

Write-Host ""
Write-Host "=== MARKER (mount_shim) ==="
if (Test-Path $marker) { Get-Content $marker } else { "(no marker)" }

# Step 4: poll for actual mount + AR reload evidence in Loki.log.
Write-Host ""
Write-Host "[race-mount] waiting an additional 45s for APC to fire on game thread..."
Start-Sleep -Seconds 45

Write-Host ""
Write-Host "=== PAK MOUNT + AR RELOAD EVIDENCE ==="
$log = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log"
if (Test-Path $log) {
  Select-String -Path $log -Pattern 'pakchunk999|Found Pak file|Mounting pak file|Couldn..t find pak signature|Failed to mount|Premade AssetRegistry|OnPakFileMounted2Time|Invalid Primary Asset' `
    -ErrorAction SilentlyContinue |
    Select-Object LineNumber, Line |
    Format-Table -Wrap -AutoSize | Out-String -Width 220
} else {
  Write-Host "(no Loki.log yet)"
}

Write-Host ""
Write-Host "=== PROCS ==="
Get-Process | Where-Object { $_.ProcessName -match 'SUPERVIVE|ags' } |
  Select-Object Id, ProcessName, @{N='CPU(s)';E={[math]::Round($_.CPU,1)}}, @{N='WS(MB)';E={[math]::Round($_.WorkingSet64/1MB)}}

Write-Host ""
Write-Host "[race-mount] done. Game is still running; open Missions modal to test."
