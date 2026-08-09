<#
  fk7-phase2.ps1 -- S112 phase 2. Two open questions, one launch each.

  Phase 1 (docs/s112-fk7-ab-results.md) settled the primary: control 10/10 dead vs treatment 2/10,
  p = 0.00071 => FK-7 is substantially our own standing `.text` patch. The completion review
  (docs/s112-fk7-fk8-completion-review.md) left exactly two things worth spending launches on, and
  they are measured on DIFFERENT parts of the same run -- so one launch answers both.

  Q1 -- THE RESIDUAL, and the untested tail.  Measured on the ARMED WINDOW.
    'play-funcswap' still died 2/10, and the leading suspect is its OWN footprint: it swaps ~17,126
    UFunction.Func pointers onto the hot path of all Blueprint execution. 'play-funcswap-one' arms
    only the UFunctions named `ReceiveTickClient` -- chosen from a MEASURED settled-world profile
    (1549 hits / 90 s = ~17/s, once per frame, exactly RM_PLAY's needed cadence).
    ⚠ The hold is ALSO longer here (600 s vs phase 1's 330 s), so this is deliberately a HARDER
    test, not a matched one: a longer hold can only RAISE a death rate. If the one-function arm
    still comes in at or below 2/10 despite 1.8x the exposure, the footprint reading is supported
    and the "proven only to 331 s" gap closes at the same time. If it comes in HIGHER, that is
    ambiguous between footprint and hold and must be reported as such.

  Q2 -- THE STAGING HAZARD.  Measured on the NON-ARMED launches.
    8 of 20 phase-1 launches that never armed DIED DURING STAGING, with only gft+fo resident and the
    probe never injected -- before RM_PLAY's patch exists. `gft_ready_fix` writes no module image, so
    the writer is `fo`, which makes TWO module-image writes that are confounded in every run ever
    flown: a transient <=8 s `.text` prologue and a <=25.5 s `.rdata` slot-285 vtable patch. S111 only
    ever measured `.text`. 'fo-nologinvt' drops the `.rdata` write and keeps the `.text` one.
    ⚠ It may break the route outright (the strict native Login can fatal). That is still a result.

  DESIGN. The fo variant ALTERNATES BY LAUNCH -- not by armed window -- because Q2's outcome is a
  per-launch staging event that occurs before arming, so every launch is a Q2 data point regardless
  of what happens afterwards. Alternating balances any drift across the sitting. The probe is held
  CONSTANT so Q1 pools across both fo arms (fo's writes are long gone by the time the probe arms:
  the `.rdata` window is <=25.5 s and the probe arms ~60 s later).

  Run from an ELEVATED PowerShell. Requires forceTutorialMatch = true.
#>
[CmdletBinding()]
param(
  [int]$Launches    = 20,
  [int]$HoldSeconds = 600,
  [string]$Probe    = "tools\sigbypass-mod\build\tutorial_launch_play_funcswap_one.dll",
  [string]$FoA      = "tools\sigbypass-mod\build\tutorial_launch_fo.dll",           # keeps the .rdata write
  [string]$FoB      = "tools\sigbypass-mod\build\tutorial_launch_fo_nologinvt.dll", # drops it
  [string]$Prefix   = "s112p2"
)

$ErrorActionPreference = 'Continue'
$repo   = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot 'fk7-ab-run.ps1'
$csv    = Join-Path $repo 'docs\fk7-ab-results.csv'

function Say($m){ Write-Host ("[phase2 {0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) -ForegroundColor Green }

Say ("start: {0} launches, hold {1}s, probe {2}" -f $Launches,$HoldSeconds,(Split-Path -Leaf $Probe))
for($i = 1; $i -le $Launches; $i++){
  $useA  = (($i % 2) -eq 1)
  $fo    = if($useA){ $FoA } else { $FoB }
  $armTag= if($useA){ 'foSTD' } else { 'foNOVT' }
  $label = "{0}-{1}-{2:d2}" -f $Prefix,$armTag,$i
  Say ("launch {0}/{1}  fo={2}" -f $i,$Launches,(Split-Path -Leaf $fo))

  & $runner -Probe (Join-Path $repo $Probe) -Arm $armTag -Label $label `
            -HoldSeconds $HoldSeconds -Fo (Join-Path $repo $fo)

  if(Test-Path $csv){
    $r = @(Import-Csv $csv | Where-Object { $_.label -eq $label })[0]
    if($r){ Say ("  -> {0} {1}" -f $r.outcome, $(if($r.died_after_arm_s){"arm+$($r.died_after_arm_s)s"}else{""})) }
  }
  Start-Sleep -Seconds 5
}
Say 'phase 2 finished'
