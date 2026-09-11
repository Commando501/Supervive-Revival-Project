<#
.SYNOPSIS
  Add our own +DebugExecBindings rows to a USER-layer Input.ini, so one keypress
  can answer FK-13: does the shipping client EVALUATE UPlayerInput::DebugExecBindings?

.DESCRIPTION
  Modelled directly on configs/set-log-verbosity.ps1 (same backup / clear-ReadOnly /
  write / re-set-ReadOnly discipline, same -Revert and -WhatIf).

  WHY THE FILE LAYER AND NOT -ini:
  FK-11 (docs/fk11-log-verbosity-settled.md) MEASURED, live, on 2026-08-09:
    * the USER ini form WORKS   (Engine.ini [Core.Log] -> LogAccelByte 3 -> 52 lines)
    * the '-ini:Engine:[Core.Log]:...' COMMAND-LINE form FAILED, with a clean control
      (the switch was verifiably DELIVERED per LogInit's command-line echo, the
      category ran, and it stayed pinned) => -ini: is applied TOO LATE for that key.
  This project already depends on the file layer for the same class of problem:
  launch-redirect.ps1:279 writes [HTTP.Curl] bVerifyPeer=false into the user
  Engine.ini precisely because -ini: lands after FCurlHttpManager::InitCurl reads it.
  So: FILE FIRST. '-ini:Input:[/Script/Engine.PlayerInput]:+DebugExecBindings=...'
  is a SEPARATE, SECOND arm (see docs/fk13-live-test-card.md step 6), never bundled
  with this one.

  WHAT IS NEW AND UNTESTED HERE:
  There is NO user Input.ini today. 'Input' IS in the engine's config base-name
  table (merged.dump RVA 0x076bc130, measured S101), so Saved/Config/WindowsClient/
  Input.ini is a layer the engine should read -- but this project has never written
  one, so "it is read" is a hypothesis, not a fact.

  THE DISCRIMINATOR (this is the point of the script):
  You must be able to tell "my file was READ" from "my file was IGNORED" *separately*
  from "the bindings were EVALUATED". Three instruments, in order of strength:

    1. ** RPM, no keypress, no visual judgment. **
       tools/re/console_probe.py section [C] prints UPlayerInput::DebugExecBindings
       Num and every decoded row. Baseline is EXACTLY 16 (Engine/Config/BaseInput.ini
       ships 16, Loki/Config/DefaultInput.ini adds/removes none, and S79 measured
       Num=16 live). If it reads 19 and lists our three commands -> THE FILE WAS READ.
       If it still reads 16 -> the file was IGNORED. Airtight either way.

    2. LogConfig narration in Loki.log. Run configs/set-log-verbosity.ps1 first with
       -Categories @{ LogConfig='Verbose' } to make the config system talk. CAVEAT:
       the Input hierarchy is loaded during FConfigCacheIni::InitializeConfigSystem,
       which may run BEFORE [Core.Log] from Engine.ini is applied -- so a silent
       LogConfig is NOT evidence the file was ignored. Instrument 1 outranks this.

    3. 'LogInit: Command Line:' echo -- only relevant to the -ini: arm, and it proves
       DELIVERY, never EFFECT. (FK-11's exact lesson.)

  WHAT THE ROWS ARE AND WHY:
    F6      -> "HighResShot 1"   The verb is MEASURED to work in THIS build: the
                                 tutorial shim drives it through ExecuteConsoleCommand
                                 (tools/sigbypass-mod/tutorial_launch.cpp:5569) and has
                                 produced 259 PNGs in Saved/Screenshots/WindowsClient/.
                                 So a null result here isolates BINDING EVALUATION and
                                 cannot be blamed on the command being stripped.
                                 Output prefix: HighresScreenshot#####.png
    F7      -> "shot showui"     The SAME command the shipped F9 row carries, on a key
                                 we own. Output prefix: ScreenShot#####.png -- a prefix
                                 that has NEVER appeared in that directory (all 259
                                 existing files are HighresScreenshot*), so it is an
                                 unambiguous, file-system-verifiable signal.
                                 Both base filenames are in the image: 'HighresScreenshot'
                                 at RVA 0x08244C90 and 'ScreenShot' at 0x08244CB8.
    Ctrl+F8 -> "HighResShot 1"   Same verb, but exercises the modifier path.

  F6/F7/F8 are UNBOUND in both the live user table (UserSettings.ini) and the shipped
  Loki/Config/DefaultInput.ini -- measured -- so none of these collide.

  ** DO NOT ADD A 'viewmode wireframe' ROW. ** This build ships the refusal string
  "Debug viewmodes not allowed in Test or Shipping builds." at RVA 0x08089190, so a
  null viewmode result cannot discriminate "binding did not fire" from "command
  refused". It is a VOID test by construction.

.PARAMETER Preset
    Probe   - the three rows above (default). This is the FK-13 experiment.
    Minimal - F6 only. One variable, if you want the absolutely smallest change.
    Control - writes the file with the [/Script/Engine.PlayerInput] section but ZERO
              added rows. Use this as the negative-control arm: the file exists and is
              read-only, yet DebugExecBindings must still read Num=16. If Num changes
              under Control, something other than our rows is moving it.

.PARAMETER Bindings
    Override the rows entirely. Array of hashtables, e.g.
      -Bindings @( @{Key='F6'; Command='HighResShot 1'}, @{Key='F7'; Command='shot showui'; Control=$true} )
    Recognised keys: Key, Command, Control, Shift, Alt, Cmd,
                     bIgnoreCtrl, bIgnoreShift, bIgnoreAlt, bIgnoreCmd, bDisabled.

.PARAMETER Revert
    Undo. Restores the newest backup if one exists; if this script created the file
    (no backup), the file is DELETED (ReadOnly cleared first).

.PARAMETER WhatIf
    Print the file that would be written. Touches nothing.

.EXAMPLE
    .\configs\set-debug-execbindings.ps1 -WhatIf
    .\configs\set-debug-execbindings.ps1
    .\configs\set-debug-execbindings.ps1 -Preset Control
    .\configs\set-debug-execbindings.ps1 -Revert
#>
[CmdletBinding()]
param(
  [ValidateSet('Probe','Minimal','Control')]
  [string]$Preset = 'Probe',
  [hashtable[]]$Bindings,
  [switch]$Revert,
  [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

$cfgDir = Join-Path $env:LOCALAPPDATA 'SUPERVIVE\Saved\Config\WindowsClient'
$ini    = Join-Path $cfgDir 'Input.ini'
$marker = '; ---- SUPERVIVE Revival / FK-13 (configs/set-debug-execbindings.ps1) ----'

if (-not (Test-Path $cfgDir)) {
  throw "Config dir not found: $cfgDir  (run the game once first)"
}

# ---------------------------------------------------------------- revert
if ($Revert) {
  $bak = Get-ChildItem "$ini.bak-*" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (Test-Path $ini) {
    $f = Get-Item $ini -Force
    if ($f.Attributes -band [IO.FileAttributes]::ReadOnly) {
      $f.Attributes = $f.Attributes -bxor [IO.FileAttributes]::ReadOnly
    }
  }
  if ($bak) {
    Copy-Item $bak.FullName $ini -Force
    (Get-Item $ini -Force).Attributes = 'ReadOnly, Archive'
    "Restored from $($bak.Name); ReadOnly re-set."
  } elseif (Test-Path $ini) {
    $head = (Get-Content $ini -TotalCount 4) -join "`n"
    if ($head -notmatch [regex]::Escape('set-debug-execbindings')) {
      throw "Input.ini exists but was NOT written by this script (no marker in the first 4 lines) and there is no backup. Refusing to delete it. Inspect it by hand: $ini"
    }
    Remove-Item $ini -Force
    "Deleted $ini (this script created it; no backup existed)."
  } else {
    "Nothing to revert: $ini does not exist and no backup was found."
  }
  return
}

# ---------------------------------------------------------------- presets
$probe = @(
  @{ Key='F6'; Command='HighResShot 1' }                      # verb PROVEN to work here
  @{ Key='F7'; Command='shot showui' }                        # same verb as the shipped F9 row
  @{ Key='F8'; Command='HighResShot 1'; Control=$true }       # modifier path
)
$minimal = @(
  @{ Key='F6'; Command='HighResShot 1' }
)
switch ($Preset) {
  'Probe'   { $rows = $probe }
  'Minimal' { $rows = $minimal }
  'Control' { $rows = @() }
}
if ($PSBoundParameters.ContainsKey('Bindings')) { $rows = $Bindings }

# ---------------------------------------------------------------- render
function Format-KeyBind([hashtable]$b) {
  if (-not $b.Key)     { throw "binding is missing Key: $($b | Out-String)" }
  if (-not $b.Command) { throw "binding is missing Command: $($b | Out-String)" }
  $parts = @("Key=$($b.Key)", "Command=`"$($b.Command)`"")
  foreach ($flag in 'Control','Shift','Alt','Cmd','bIgnoreCtrl','bIgnoreShift','bIgnoreAlt','bIgnoreCmd','bDisabled') {
    if ($b.ContainsKey($flag) -and $b[$flag]) { $parts += "$flag=True" }
  }
  '+DebugExecBindings=(' + ($parts -join ',') + ')'
}

$out = New-Object System.Collections.Generic.List[string]
$out.Add($marker)
$out.Add("; Preset=$Preset   written $(Get-Date -Format s)")
$out.Add('; FK-13: does this shipping build EVALUATE UPlayerInput::DebugExecBindings?')
$out.Add('; Baseline (unmodified) Num is EXACTLY 16 - Engine/Config/BaseInput.ini ships 16,')
$out.Add('; Loki/Config/DefaultInput.ini adds/removes none, and S79 measured Num=16 live.')
$out.Add('; Verify with:  python tools\re\console_probe.py     (section [C])')
$out.Add('; Revert with:  .\configs\set-debug-execbindings.ps1 -Revert')
$out.Add('')
$out.Add('[/Script/Engine.PlayerInput]')
if ($rows.Count -eq 0) {
  $out.Add('; Control arm: section present, ZERO rows added. DebugExecBindings must still read Num=16.')
} else {
  foreach ($b in $rows) { $out.Add((Format-KeyBind $b)) }
}
$out.Add('')
$text = ($out -join "`r`n")

$expectedNum = 16 + $rows.Count

if ($WhatIf) {
  "--- $ini (WhatIf, nothing written) ---"
  $text
  ""
  "Would add $($rows.Count) row(s). Expected live DebugExecBindings Num after launch: $expectedNum (baseline 16)."
  return
}

# ---------------------------------------------------------------- write
$existed = Test-Path $ini
if ($existed) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  Copy-Item $ini "$ini.bak-$stamp" -Force
  $f = Get-Item $ini -Force
  if ($f.Attributes -band [IO.FileAttributes]::ReadOnly) {
    $f.Attributes = $f.Attributes -bxor [IO.FileAttributes]::ReadOnly
  }
}
Set-Content -Path $ini -Value $text -Encoding utf8
# Read-only for the same reason launch-redirect.ps1:283 sets it on Engine.ini:
# the engine rewrites these files and drops sections it does not recognise.
(Get-Item $ini -Force).Attributes = 'ReadOnly, Archive'

if ($existed) { "Backed up to  : $ini.bak-$stamp" } else { "Created (did not exist before)" }
"Wrote         : $ini  (ReadOnly re-set)"
"Preset        : $Preset  ($($rows.Count) added row(s))"
foreach ($b in $rows) { "                $(Format-KeyBind $b)" }
""
"EXPECTED LIVE VALUE after launch:  DebugExecBindings Num = $expectedNum   (baseline 16)"
""
"Next, in order:"
"  1. .\configs\launch-redirect.ps1 -NoHook          # clean run, no shims"
"  2. (game at the menu) python tools\re\console_probe.py"
"       section [C] Num = $expectedNum  ->  the user Input.ini WAS READ"
"       section [C] Num = 16            ->  the user Input.ini was IGNORED  (stop here;"
"                                           the keypress test below would be VOID)"
"  3. only if Num = $expectedNum : press F6, then F7, then Ctrl+F8, and check"
"       $env:LOCALAPPDATA\SUPERVIVE\Saved\Screenshots\WindowsClient\"
"       new HighresScreenshot*.png -> F6/Ctrl+F8 fired"
"       new ScreenShot*.png        -> F7 fired   (this prefix has NEVER appeared there)"
""
"See docs\fk13-live-test-card.md for the full ordered run and the decision table."
