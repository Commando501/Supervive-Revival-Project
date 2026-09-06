<#
.SYNOPSIS
  Raise (or restore) UE log-category verbosity for the SUPERVIVE client via the
  user Engine.ini [Core.Log] section.

.DESCRIPTION
  FK-11 (docs/fk11-log-verbosity-settled.md) established, offline and with controls:

    * Verbose/VeryVerbose are NOT compiled out. Global COMPILED_IN_MINIMUM_VERBOSITY
      is VeryVerbose(7); 1,339 Verbose + 513 VeryVerbose UE_LOG call sites survived
      compilation; 109/109 Loki-dominant categories are CompileTimeVerbosity=VeryVerbose.
    * -LogCmds DOES NOT PARSE in this binary. All three `logcmds` occurrences in the
      178 MB image are HELP TEXT; there is no standalone `LogCmds=` literal for
      FParse::Value. Do not rely on it.
    * [Core.Log] via ini IS the working path, and is already binding: across a
      4.10 GB / 28.7M-line log corpus the 15 shipped entries show ZERO violations.
      The binary states its own precedence at 0x076B1FA0: compiled-in -> ini -> cmdline.

  This script edits the USER ini, which is the layer this project already uses for the
  same class of problem (it holds our [HTTP.Curl] bVerifyPeer=false fix, added because
  -ini: is applied too late for curl init - see launch-redirect.ps1:279).

  The file is normally ReadOnly, deliberately: that stops the engine rewriting it (the
  engine owns CachedClientID in the same file). This script clears ReadOnly, merges the
  [Core.Log] block, and re-sets ReadOnly.

  ALWAYS takes a timestamped backup first. -Revert restores the newest backup.

.PARAMETER Preset
  Which category set to apply.
    Mechanism  - minimal: just the LogAccelByte canary. Proves the ini path works.
    ClassA     - Mechanism + the six categories whose owners provably run today.
    Gas        - ClassA + the ability-system family.
    Ws         - Mechanism + the server->client WebSocket push detectors (FK-15).
                 Standalone: does NOT include ClassA. See docs/fk15-ws-push-audit.md.
  Default: ClassA.

.PARAMETER Categories
  Extra/override entries, e.g. -Categories @{ LogLokiSpawner='Verbose' }.
  Merged on top of the preset.

.PARAMETER NoFreeWins
  Skip LogTemp=Fatal and DFLLog=Log (see below). Off by default, i.e. free wins ARE applied.

.PARAMETER Revert
  Restore the most recent backup and exit.

.PARAMETER WhatIf
  Print the resulting file without writing anything.

.EXAMPLE
  .\configs\set-log-verbosity.ps1 -Preset Mechanism -WhatIf
  .\configs\set-log-verbosity.ps1 -Preset ClassA
  .\configs\set-log-verbosity.ps1 -Revert
#>
[CmdletBinding()]
param(
  [ValidateSet('Mechanism','ClassA','Gas','Ws')]
  [string]$Preset = 'ClassA',
  [hashtable]$Categories,
  [switch]$NoFreeWins,
  [switch]$Revert,
  [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$ini = Join-Path $env:LOCALAPPDATA 'SUPERVIVE\Saved\Config\WindowsClient\Engine.ini'
if (-not (Test-Path $ini)) { throw "User Engine.ini not found: $ini" }

# ---------------------------------------------------------------- revert
if ($Revert) {
  $bak = Get-ChildItem "$ini.bak-*" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $bak) { throw "No backup found matching $ini.bak-*" }
  $f = Get-Item $ini -Force
  if ($f.Attributes -band [IO.FileAttributes]::ReadOnly) { $f.Attributes = $f.Attributes -bxor [IO.FileAttributes]::ReadOnly }
  Copy-Item $bak.FullName $ini -Force
  (Get-Item $ini -Force).Attributes = 'ReadOnly, Archive'
  "Restored from $($bak.Name); ReadOnly re-set."
  return
}

# ---------------------------------------------------------------- presets
# Class A = owner provably ran in the existing corpus AND still silent => real
#           suppression wins. Class B (GAS) may still be silent because the code
#           path never executes - that is NOT evidence of suppression.
$mechanism = [ordered]@{
  'LogAccelByte' = 'Verbose'          # canary: pinned Warning, baseline 3 lines, runs every launch
}
$classA = [ordered]@{
  'LogLokiHeroCharacter'      = 'Verbose'
  'LogLokiCharacter'          = 'Verbose'
  'LogLokiCharacterMovement'  = 'Verbose'
  'LogLokiPlayerController'   = 'Verbose'
  'LogLokiMenuActions'        = 'Verbose'
  'LogGameFeatureToggles'     = 'Log'   # NOT Verbose: same subsystem already emits ~1e5 lines/run via LogTemp
}
# Ws = the FK-15 server->client push experiment (S117, docs/fk15-ws-push-audit.md).
# ⚠ Category names matter more than usual here. The five 2026-06-29 push probes cited six
# detectors; FOUR have never emitted a line across 326 archived client logs, and TWO of them
# (LogPlatformLobby, LogPlatformQuery) DO NOT EXIST in the binary at all -- they appear nowhere
# in this repo except the sentence asserting their silence. Do not re-add them.
# LogAccelByte is the load-bearing one: it owns
#   LogAccelByte: Verbose: AccelByte::AccelByteWebSocket::OnMessageReceived
# which is the ONLY direct receipt that an inbound frame reached the client's SDK, and it is the
# free pre-registered positive control (our own 4 solicited responses must produce 4 receipts
# before any probe frame is sent).
#
# ★★ LogAccelByte IS NOT A SUBSTITUTE FOR LogAccelByteLobby -- MEASURED, and this is the
# single most important line in this preset. In docs/fk11-live-result-20260809.log, flown with
# LogAccelByte=Verbose, there are 52 `LogAccelByte:` lines INCLUDING 4x OnMessageReceived (so
# frames were provably arriving and being processed) and ZERO `LogAccelByteLobby:` lines and
# ZERO Lobby.cpp format strings (`Type: %s`, `JSON Version: %s`, `Sending request: %s`).
# The lobby dispatcher logs to its own category, whose live state reads Verbosity=Warning(3),
# CompileTimeVerbosity=VeryVerbose(7) at .data 0x9FFE2A0 -- i.e. fully compiled in, just muted.
# `Type: %s` (site .text 0x04B0B12B) needs VeryVerbose and prints the type of EVERY frame the
# client routes, which is the direct read on whether a pushed frame reached the dispatcher.
$ws = [ordered]@{
  'LogAccelByte'                   = 'Verbose'     # OnMessageReceived -- receipt + positive control
  'LogAccelByteLobby'              = 'VeryVerbose' # THE dispatcher. `Type: %s` needs VeryVerbose
  'LogAccelByteNotificationBuffer' = 'VeryVerbose' # sequenceID/dedup gate (the REAL precondition)
  'LogAccelByteMessagingSystem'    = 'Verbose'
  'LogAccelByteWebsocket'          = 'Verbose'
  'LogNet'                         = 'Verbose'     # a NetConnection attempt is the dsNotif win
  'LogMessenger'                   = 'Verbose'     # the OTHER socket; already emits => a control
}
$gas = [ordered]@{
  'LogLokiAbilitySystemComponent' = 'Verbose'
  'LogAbilitySystemComponent'     = 'Verbose'   # engine - most likely to NAME why AvatarActor is null
  'LogLokiGameplaySpell'          = 'Verbose'
  'LogGameplayEffects'            = 'Verbose'
  'LogAbilitySystem'              = 'Verbose'
}
# Free wins, unrelated to any experiment:
#   LogTemp is 97.5% of the log (100,616 of 103,169 lines) - the feature-toggle spam,
#   emitted at Error under LogTemp (NOT under LogGameFeatureToggles, which is silent).
#   Fatal is required; Warning will NOT suppress it because the spam is at Error.
#   DFLLog=Fatal in the shipped ini mutes a real 33-method DebugFunctionLibrary.
$freeWins = [ordered]@{ 'LogTemp' = 'Fatal'; 'DFLLog' = 'Log' }

$want = [ordered]@{}
foreach ($k in $mechanism.Keys) { $want[$k] = $mechanism[$k] }
if ($Preset -in 'ClassA','Gas') { foreach ($k in $classA.Keys) { $want[$k] = $classA[$k] } }
if ($Preset -eq 'Ws')           { foreach ($k in $ws.Keys)     { $want[$k] = $ws[$k] } }
if ($Preset -eq 'Gas')          { foreach ($k in $gas.Keys)    { $want[$k] = $gas[$k] } }
if (-not $NoFreeWins)           { foreach ($k in $freeWins.Keys) { $want[$k] = $freeWins[$k] } }
if ($Categories) { foreach ($k in $Categories.Keys) { $want[$k] = $Categories[$k] } }

# ------------------------------------------------- rebuild file, [Core.Log] replaced
$lines = Get-Content $ini
$out = New-Object System.Collections.Generic.List[string]
$inCoreLog = $false
foreach ($line in $lines) {
  if ($line -match '^\s*\[(.+)\]\s*$') {
    $inCoreLog = ($Matches[1] -eq 'Core.Log')
    if ($inCoreLog) { continue }        # drop the old section header; we re-emit below
  }
  if (-not $inCoreLog) { $out.Add($line) }
}
while ($out.Count -gt 0 -and [string]::IsNullOrWhiteSpace($out[$out.Count-1])) { $out.RemoveAt($out.Count-1) }
$out.Add('')
$out.Add('[Core.Log]')
$out.Add('; Added by configs/set-log-verbosity.ps1 - see docs/fk11-log-verbosity-settled.md')
$out.Add("; Preset=$Preset")
foreach ($k in $want.Keys) { $out.Add("$k=$($want[$k])") }
$out.Add('')
$text = ($out -join "`r`n")

if ($WhatIf) { "--- $ini (WhatIf, nothing written) ---"; $text; return }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Copy-Item $ini "$ini.bak-$stamp" -Force
$f = Get-Item $ini -Force
if ($f.Attributes -band [IO.FileAttributes]::ReadOnly) { $f.Attributes = $f.Attributes -bxor [IO.FileAttributes]::ReadOnly }
Set-Content -Path $ini -Value $text -Encoding utf8
(Get-Item $ini -Force).Attributes = 'ReadOnly, Archive'

"Backed up to  : $ini.bak-$stamp"
"Wrote         : $ini  (ReadOnly re-set)"
"Preset        : $Preset  ($($want.Count) entries)"
""
"Next: launch normally, then verify with"
"  .\configs\check-log-verbosity.ps1"
