<#
.SYNOPSIS
  Find a freshly-dumped Mappings.usmap and install it for the extractor.

.WHY
  Whichever dumper produces it (UE4SS DumpUSMAP keybind, Dumper-7, or
  UnrealMappingsDumper), the result is a *.usmap written somewhere near the game.
  The extractor (tools/extractor) auto-loads the FIRST *.usmap it finds in:
    - its built-exe dir (bin/Release/net9.0)
    - tools/extractor
    - tools/extractor/extractor
  This script locates the newest *.usmap, clears any stale/placeholder usmap from
  those search dirs, and copies the real one into tools/extractor/.

.USAGE
  # Auto-find the newest usmap under the usual spots and install it:
  powershell -ExecutionPolicy Bypass -File tools/usmap/get-usmap.ps1

  # Just report what's present (UE4SS.log + any usmap), don't copy:
  powershell -ExecutionPolicy Bypass -File tools/usmap/get-usmap.ps1 -Check

  # Point at a specific file:
  powershell -ExecutionPolicy Bypass -File tools/usmap/get-usmap.ps1 -Source "C:\path\Mappings.usmap"
#>
[CmdletBinding()]
param(
  [string]$Source = "",
  [string]$GameWin64 = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64",
  [string]$ExtractorRoot = "G:\git\Supervive Revival Project\tools\extractor",
  [switch]$Check
)
$ErrorActionPreference = "Stop"

# Dirs the extractor scans for *.usmap (keep in sync with Program.cs)
$searchDirs = @(
  (Join-Path $ExtractorRoot "extractor\bin\Release\net9.0"),
  $ExtractorRoot,
  (Join-Path $ExtractorRoot "extractor")
)

# --- Report current state (UE4SS.log proves UE4SS initialized; usmap proves a dump) ---
$ue4ssLog = Join-Path $GameWin64 "ue4ss\UE4SS.log"
Write-Host "[*] UE4SS.log: " -NoNewline
if (Test-Path $ue4ssLog) {
  Write-Host "PRESENT ($([math]::Round((Get-Item $ue4ssLog).Length/1KB,1)) KB) -> UE4SS initialized." -ForegroundColor Green
} else {
  Write-Host "absent -> UE4SS has not initialized (see tools/usmap/README.md)." -ForegroundColor Yellow
}

# Roots to hunt for a produced *.usmap
$hunt = @(
  $GameWin64,
  (Join-Path $GameWin64 "ue4ss"),
  (Split-Path $GameWin64),                          # Loki\Binaries
  "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE",
  "$env:LOCALAPPDATA\SUPERVIVE",
  "C:\Dumper-7",
  "$env:USERPROFILE\Desktop"
) | Where-Object { Test-Path $_ }

$found = foreach ($r in $hunt) {
  Get-ChildItem -Path $r -Recurse -Filter *.usmap -ErrorAction SilentlyContinue
}
$found = $found | Sort-Object LastWriteTime -Descending

Write-Host "[*] Candidate *.usmap files found:"
if (-not $found) { Write-Host "    (none)" -ForegroundColor Yellow }
$found | Select-Object -First 8 | ForEach-Object {
  Write-Host ("    {0,-19}  {1,8:N0} B  {2}" -f $_.LastWriteTime, $_.Length, $_.FullName)
}

if ($Check) { return }

# --- Pick the source ---
$src = $null
if ($Source) {
  if (-not (Test-Path $Source)) { throw "Source not found: $Source" }
  $src = Get-Item $Source
} elseif ($found) {
  $src = $found | Select-Object -First 1
} else {
  Write-Warning "No *.usmap to install. Produce one first (UE4SS Ctrl+NumPad6, Dumper-7, or UnrealMappingsDumper)."
  return
}

# A real usmap is far bigger than the 24-byte empty placeholder
if ($src.Length -le 64) {
  Write-Warning "Selected usmap is only $($src.Length) bytes - looks like the empty placeholder, not a real dump. Aborting."
  return
}
Write-Host "[*] Installing: $($src.FullName)  ($([math]::Round($src.Length/1KB,1)) KB)" -ForegroundColor Cyan

# --- Clear stale usmaps from every extractor search dir so the real one wins ---
foreach ($d in $searchDirs) {
  if (Test-Path $d) {
    Get-ChildItem -Path $d -Filter *.usmap -ErrorAction SilentlyContinue | ForEach-Object {
      Write-Host "    - removing stale $($_.Name) in $d"
      Remove-Item $_.FullName -Force
    }
  }
}

# --- Copy into tools/extractor/ (search index #2) ---
$dest = Join-Path $ExtractorRoot "Mappings.usmap"
Copy-Item $src.FullName $dest -Force
Write-Host "[+] Installed -> $dest" -ForegroundColor Green
Write-Host "[*] Verify with:"
Write-Host '    & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release   (from tools\extractor\extractor)'
Write-Host '    Expect: "Loaded mappings: ...Mappings.usmap" instead of "No .usmap found".'
