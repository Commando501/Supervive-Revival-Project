# launch-recon.ps1 — launch the NORMAL redirected SUPERVIVE client (no dedicated-server
# stub, no injection of its own). This is the "recon" client the hero-roster work uses:
# same AccelByte/Loki -ini URL overrides as launch-redirect.ps1, pointed at the local ags
# backend on :8080. Session 45 recreated this from launch-redirect.ps1 (the standalone
# launch-recon.bat referenced by earlier docs was never committed).
#
# PRECONDITIONS (all already set up by a prior launch-redirect.ps1 run):
#   - Steam is running and logged in (else SteamAPI init -> Auth Failure 14005).
#   - hosts file has the two "# SUPERVIVE-REVIVAL" 127.0.0.1 entries.
#   - Loki\Content\Certificates\cacert.pem has our root appended.
#   - user Engine.ini has [HTTP.Curl] bVerifyPeer=false / [SSL] bValidateRootCertificates=false.
#   - ags is running on :8080 (rebuilt from HEAD so the content-manifest fix is live:
#     GET /content-service/manifest/x?nonEnabledOnly=true -> "Heroes":{}).
#
# To capture the hero-content-load crash, start the gated early injector BEFORE this:
#   tools\inject\inject.exe watch SUPERVIVE-Win64-Shipping.exe `
#       tools\sigbypass-mod\scan_on_enum_veh.dll 0x3EC57D0 40555356574154415541564157
# then run this script. The crash callstack lands in docs\veh-crash-marker.txt.
#
# No elevation needed (this only launches the client; it does not touch hosts/certs).
param(
  [string]$GameRoot = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE"
)
$ErrorActionPreference = "Stop"
$exe = Join-Path $GameRoot "Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
if (-not (Test-Path $exe)) { throw "Shipping exe not found: $exe" }

$ab    = "/Script/AccelByteUe4Sdk.AccelByteSettings"
$loki  = "/Script/Loki.LokiGameProjectSettings"
$local = "http://localhost:8080"
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
Write-Host "Launching recon client (PostAuth -> $local, no stub)..." -ForegroundColor Cyan
& $exe @iniArgs
