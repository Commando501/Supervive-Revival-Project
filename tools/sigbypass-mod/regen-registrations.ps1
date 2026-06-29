# regen-registrations.ps1 — regenerate registration_shim.cpp's kRegistrations
# table with FName indices CURRENT for the running game session.
#
# Why: FName ComparisonIndex values are NOT stable across launches for
# cooked asset names (only block-1 engine-init names are stable). The
# baked indices in the shim source go stale immediately on relaunch.
#
# This script:
#   1. Runs usmapdump nameid for all 48 needed strings (16 names + 16 paths
#      + 16 _C class names) against the live process.
#   2. Parses the output into name→id mapping.
#   3. Patches the registration_shim.cpp kRegistrations table in place.
#   4. Rebuilds the DLL.
#
# Run from elevated PowerShell with the game running:
#   .\tools\sigbypass-mod\regen-registrations.ps1
# Then inject:
#   .\tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe `
#     .\tools\sigbypass-mod\registration_shim.dll

$ErrorActionPreference = 'Stop'
# Don't let native-exe stderr (progress lines) be treated as terminating errors.
# usmapdump writes scan-progress to stderr — that's not an error condition.
$PSNativeCommandUseErrorActionPreference = $false

$repoRoot = "G:\git\Supervive Revival Project"
$usmapdump = "$repoRoot\tools\usmapdump\usmapdump.exe"
$shimCpp = "$repoRoot\tools\sigbypass-mod\registration_shim.cpp"

# The 16 LokiDataAsset_MissionPool entries we register. Source: extractor
# catalog (da_index.csv filtered to LokiDataAsset_MissionPool).
$names = @(
  "DA_MissionPoolArmoryOnboarding",
  "DA_MissionPoolDailyChallenge",
  "DA_MissionPoolDailyChallenge_Planbee",
  "DA_MissionPoolDailyEasy",
  "DA_MissionPoolDailyEasy_Planbee",
  "DA_MissionPoolDailyPCB",
  "DA_MissionPoolDailyPCB_Armory",
  "DA_MissionPoolHunterMissions",
  "DA_MissionPoolOnboarding",
  "DA_MissionPoolOnboardingPlanbee",
  "DA_MissionPoolTutorialMaps",
  "DA_MissionPoolWeekly",
  "DA_MissionPoolWeeklyChallenge",
  "DA_MissionPoolWeeklyChallenge_Planbee",
  "DA_MissionPoolWeekly_Planbee",
  "DA_MissionPool_Tournament"
)
$pathPrefix = "/Game/Loki/Core/Missions/Pools/"
$paths = $names | ForEach-Object {
  if ($_ -eq "DA_MissionPool_Tournament") {
    "$pathPrefix" + "ArmorySeasonal/Tournament/" + $_
  } else {
    $pathPrefix + $_
  }
}
$cnames = $names | ForEach-Object { "$($_)_C" }

# Build needle list for nameid (exact-match prefix `=`, comma-separated).
$allNeedles = @($names + $paths + $cnames | ForEach-Object { "=$_" }) -join ','

Write-Host "[regen] Running usmapdump nameid for $($names.Count * 3) needles..."
# Capture both streams to a temp file (PowerShell terminates on native stderr
# even with -ErrorAction; redirect at the shell level instead).
$tmpOut = "$env:TEMP\nameid_out_$([System.IO.Path]::GetRandomFileName()).txt"
& cmd /c "`"$usmapdump`" nameid SUPERVIVE-Win64-Shipping.exe `"$allNeedles`" 3 > `"$tmpOut`" 2>&1"
if ($LASTEXITCODE -ne 0) {
  Write-Host "[regen] usmapdump failed with exit $LASTEXITCODE"
  Get-Content $tmpOut | Write-Host
  Remove-Item $tmpOut -Force -ErrorAction SilentlyContinue
  exit 1
}
$nameidOut = Get-Content $tmpOut -Raw
Remove-Item $tmpOut -Force -ErrorAction SilentlyContinue

# Parse "[=NAME] block=X off=Y id=0xZZZZZZZZ" lines into a hashtable.
# When the same name appears multiple times (cooker may re-emit identical
# strings in separate blocks), keep the FIRST hit — its FName id is what
# AssetManager-registered code path uses.
$idMap = @{}
foreach ($line in ($nameidOut -split "`n")) {
  if ($line -match '^\s*\[=([^\]]+)\]\s+block=\d+\s+off=0x[0-9A-Fa-f]+\s+id=(0x[0-9A-Fa-f]+)') {
    $needle = $matches[1]
    $id = $matches[2]
    if (-not $idMap.ContainsKey($needle)) {
      $idMap[$needle] = $id
    }
  }
}

Write-Host "[regen] Parsed $($idMap.Count) unique FName ids"

# Verify we got all 48.
$missing = @()
foreach ($n in @($names + $paths + $cnames)) {
  if (-not $idMap.ContainsKey($n)) { $missing += $n }
}
if ($missing.Count -gt 0) {
  Write-Host "[regen] MISSING $($missing.Count) needle(s):"
  $missing | ForEach-Object { Write-Host "  - $_" }
  exit 1
}

# Generate the kRegistrations table source. Each line:
#   {"DA_X", primaryAssetNameId, packageNameId, classNameId},
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("static const RegEntry kRegistrations[] = {")
for ($i = 0; $i -lt $names.Count; $i++) {
  $n = $names[$i]
  $p = $paths[$i]
  $c = $cnames[$i]
  $line = "    {{`"{0}`",{1,-43} {2,-12}, {3,-12}, {4,-12}}}," -f `
    $n, "", $idMap[$n], $idMap[$p], $idMap[$c]
  # Easier: just format directly
  $line = "    {`"$n`", $($idMap[$n]), $($idMap[$p]), $($idMap[$c])},"
  [void]$sb.AppendLine($line)
}
[void]$sb.AppendLine("};")
$newTable = $sb.ToString()

# Patch registration_shim.cpp: replace the existing kRegistrations table.
# Markers: "static const RegEntry kRegistrations[] = {" ... "};"
$shimSrc = Get-Content $shimCpp -Raw
$pattern = '(?ms)static const RegEntry kRegistrations\[\] = \{.*?^\};'
if ($shimSrc -notmatch $pattern) {
  Write-Host "[regen] FAIL: couldn't find kRegistrations table in shim source"
  exit 1
}
$shimSrcNew = $shimSrc -replace $pattern, ($newTable.TrimEnd())
Set-Content -Path $shimCpp -Value $shimSrcNew -Encoding ascii -NoNewline

Write-Host "[regen] Patched $shimCpp"

# Rebuild.
Write-Host "[regen] Rebuilding registration_shim.dll..."
Push-Location "$repoRoot\tools\sigbypass-mod"
try {
  $buildOut = & clang++ -shared -O2 registration_shim.cpp -o registration_shim.dll -lkernel32 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[regen] BUILD FAILED:"
    Write-Host $buildOut
    exit 1
  }
} finally {
  Pop-Location
}

Write-Host "[regen] DONE. Re-inject with:"
Write-Host "  .\tools\inject\inject.exe mmap SUPERVIVE-Win64-Shipping.exe .\tools\sigbypass-mod\registration_shim.dll"
