<#
.SYNOPSIS
  Read back a SUPERVIVE Loki.log and report which log categories actually emitted,
  at what verbosity - the verification half of configs/set-log-verbosity.ps1.

.DESCRIPTION
  FK-11 (docs/fk11-log-verbosity-settled.md). Baselines below were MEASURED on the
  2026-08-09 menu-route session (14.8 MB, 103,169 lines) before any change:

      LogAccelByte        3      (pinned Warning by the shipped [Core.Log])
      LogOnline           2      (pinned Warning)
      LogLokiVision       2      (pinned Warning)
      LogAccelByteLobby   0      (pinned Warning)
      LogTemp        100,616     (97.5% of the whole log - feature-toggle spam at Error)
      LogConfig         361      (unpinned, for scale)

  Verbosity labels in that baseline: Error 100,618 / Display 575 / Warning 366 /
  Verbose 13 (all LogSentrySdk) / VeryVerbose 0.

  ** THE RECORDING RULE (stated in advance, do not fudge it afterwards) **
  If a category stays silent, that is a fact about THAT CATEGORY OR THAT MECHANISM.
  It is NOT evidence that Verbose is compiled out. Verbose is compiled in - 1,339
  Verbose + 513 VeryVerbose call sites, measured. And a category can be silent simply
  because its code never ran: 384 of 842 logs reach LVL_Tutorial but NONE contains
  combat, drop phase, bots, damage, XP or client replication. Never-ran != suppressed.

.PARAMETER LogPath
  Log to inspect. Defaults to the live client log.

.PARAMETER Categories
  Categories to report. Defaults to the canaries + Class A + GAS set.

.EXAMPLE
  .\configs\check-log-verbosity.ps1
  .\configs\check-log-verbosity.ps1 -LogPath "dumps\crashpad-20260809-x\Loki.log"
#>
[CmdletBinding()]
param(
  [string]$LogPath = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log",
  [string[]]$Categories
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $LogPath)) { throw "Log not found: $LogPath" }

$baseline = @{
  'LogAccelByte'=3; 'LogOnline'=2; 'LogLokiVision'=2; 'LogAccelByteLobby'=0
  'LogTemp'=100616; 'LogConfig'=361; 'LogSentrySdk'=18   # 18 total, of which 13 are Verbose
}
if (-not $Categories) {
  $Categories = @(
    'LogAccelByte','LogOnline','LogAccelByteLobby',              # mechanism canaries A/B/C
    'LogLokiHeroCharacter','LogLokiCharacter','LogLokiCharacterMovement',
    'LogLokiPlayerController','LogLokiMenuActions','LogGameFeatureToggles',   # Class A
    'LogLokiAbilitySystemComponent','LogAbilitySystemComponent',
    'LogLokiGameplaySpell','LogGameplayEffects','LogAbilitySystem',           # GAS (Class B)
    'LogBlueprintLogLibrary','DFLLog',                                        # free instruments
    'LogTemp','LogSentrySdk','LogConfig'                                      # scale / control
  )
}

$f = Get-Item $LogPath
"Log      : $($f.FullName)"
"Size     : {0:N1} MB    Modified: {1}" -f ($f.Length/1MB), $f.LastWriteTime

# The game holds Loki.log open while running, so a plain ReadAllLines throws
# "being used by another process". Open with FileShare.ReadWrite to read it LIVE -
# reading the log mid-run is the normal case for this tool, not the exception.
$fs = [System.IO.File]::Open($LogPath, [System.IO.FileMode]::Open,
                             [System.IO.FileAccess]::Read,
                             [System.IO.FileShare]::ReadWrite)
try {
  $sr = New-Object System.IO.StreamReader($fs)
  $lines = $sr.ReadToEnd() -split "`r?`n"
} finally { if ($sr) { $sr.Dispose() }; $fs.Dispose() }
"Lines    : {0:N0}" -f $lines.Count
""

# --- did our switches actually arrive? (free positive control) -------------
$cmd = $lines | Where-Object { $_ -match 'LogInit: Command Line:' } | Select-Object -First 1
if ($cmd) {
  "--- command line as the ENGINE saw it ---"
  $cmd -replace '^.*Command Line:\s*',''
  foreach ($probe in @('-LogCmds','Core.Log')) {
    $seen = if ($cmd -match [regex]::Escape($probe)) { 'PRESENT' } else { 'absent' }
    "  {0,-12} {1}" -f $probe, $seen
  }
  ""
}

# --- verbosity-label census ------------------------------------------------
"--- verbosity labels across the whole log ---"
$labels = @{}
foreach ($l in $lines) {
  if ($l -match '\]Log[A-Za-z0-9_]*:\s+(Fatal|Error|Warning|Display|Verbose|VeryVerbose):\s') {
    $labels[$Matches[1]] = 1 + ($labels[$Matches[1]] | ForEach-Object { $_ })
  }
}
foreach ($k in 'Error','Display','Warning','Verbose','VeryVerbose','Fatal') {
  $n = if ($labels.ContainsKey($k)) { $labels[$k] } else { 0 }
  "  {0,-12} {1,8:N0}" -f $k, $n
}
""

# --- per-category ----------------------------------------------------------
"--- per-category ---"
"  'V+VV' is the count of Verbose/VeryVerbose lines: THAT is the FK-11 success signal."
""
"{0,-32} {1,8} {2,9} {3,7} {4}" -f 'category','lines','baseline','V+VV','delta'
foreach ($c in $Categories) {
  $pat = "]$c" + ":"
  $hits = @($lines | Where-Object { $_.Contains($pat) })
  $n = $hits.Count
  $esc = [regex]::Escape($c)
  $vv  = @($hits | Where-Object { $_ -match "\]$esc\:\s+(Verbose|VeryVerbose)\:\s" }).Count
  $b = if ($baseline.ContainsKey($c)) { $baseline[$c] } else { $null }
  $d = if ($null -ne $b) {
         $delta = $n - $b
         if ($delta -gt 0) { "+$delta" } elseif ($delta -lt 0) { "$delta" } else { 'same' }
       } else { '' }
  if ($vv -gt 0) { $d = "$d  <== VERBOSE FLOWING" }
  "{0,-32} {1,8:N0} {2,9} {3,7} {4}" -f $c, $n, $(if ($null -ne $b) { $b } else { '-' }), $vv, $d
}
""
"Reminder: a silent category may simply never have RUN on this route."
"That is not evidence about compile-time verbosity. See docs/fk11-log-verbosity-settled.md."
