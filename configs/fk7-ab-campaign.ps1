<#
  fk7-ab-campaign.ps1 -- drive the S112 FK-7 A/B unattended.

  Wraps configs\fk7-ab-run.ps1 and handles the one thing a human otherwise has to babysit: the
  tutorial route only reaches an armed window on a minority of launches, so a fixed alternating
  launch schedule does NOT produce balanced arms.

  ★ ALTERNATE ON ARMED WINDOWS, NOT ON LAUNCHES.
  A launch that dies during staging, or never loads the world, never injects the probe at all --
  it is arm-NEUTRAL, and counting it against an arm would silently unbalance the comparison. So the
  campaign stays on the current arm until that arm actually yields an armed window (DIED or
  SURVIVED), then switches. That guarantees equal armed-window counts per arm, which is the
  denominator the pre-registration analyses.

  It also means a run of bad luck costs launches, never balance.

  Stop conditions: -TargetPerArm armed windows in each arm, or -MaxLaunches, whichever first.

  Usage (ELEVATED):
    .\configs\fk7-ab-campaign.ps1 -TargetPerArm 10 -MaxLaunches 60
#>
[CmdletBinding()]
param(
  [int]$TargetPerArm = 10,
  [int]$MaxLaunches  = 60,
  [int]$HoldSeconds  = 330,
  [string]$Control   = "tools\sigbypass-mod\build\tutorial_launch_play.dll",
  [string]$Treatment = "tools\sigbypass-mod\build\tutorial_launch_play_funcswap.dll",
  [string]$Prefix    = "s112",
  [string]$ControlArm   = "control",     # arm LABELS are the analysis's pooling key, so a new
  [string]$TreatmentArm = "treatment",   # experiment MUST rename them or it silently pools into
                                         # the previous one's denominator and corrupts both

  [string]$Fo        = ""                    # S112: alternate force-open DLL, applied to EVERY launch
                                             # in this campaign (it is shared staging, so it must be
                                             # constant across arms or the comparison is broken)
)

$ErrorActionPreference = 'Continue'
$repo   = Split-Path -Parent $PSScriptRoot
$csv    = Join-Path $repo 'docs\fk7-ab-results.csv'
$runner = Join-Path $PSScriptRoot 'fk7-ab-run.ps1'

function Say($m){ Write-Host ("[campaign {0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) -ForegroundColor Cyan }

# armed windows only -- STAGE_FAIL / VOID_* are not data points and must not drive the schedule
function Get-Armed([string]$arm){
  if(-not (Test-Path $csv)){ return 0 }
  return @(Import-Csv $csv | Where-Object { $_.arm -eq $arm -and ($_.outcome -eq 'DIED' -or $_.outcome -eq 'SURVIVED') }).Count
}

$arm = $ControlArm
$launch = 0
Say ("start: target {0} armed windows/arm, max {1} launches, hold {2}s" -f $TargetPerArm,$MaxLaunches,$HoldSeconds)

while($launch -lt $MaxLaunches){
  $ac = Get-Armed $ControlArm; $at = Get-Armed $TreatmentArm
  if($ac -ge $TargetPerArm -and $at -ge $TargetPerArm){ Say 'target reached in both arms'; break }
  # if one arm is already full, spend every remaining launch on the other
  if($arm -eq $ControlArm   -and $ac -ge $TargetPerArm){ $arm = $TreatmentArm }
  if($arm -eq $TreatmentArm -and $at -ge $TargetPerArm){ $arm = $ControlArm }

  $launch++
  $probe = if($arm -eq $ControlArm){ $Control } else { $Treatment }
  $tag   = if($arm -eq $ControlArm){ 'ctl' } else { 'trt' }
  $label = "{0}-{1}-{2:d2}" -f $Prefix,$tag,($launch)
  Say ("launch {0}/{1}  arm={2}  armed so far: control={3} treatment={4}" -f $launch,$MaxLaunches,$arm,$ac,$at)

  $runArgs = @{ Probe = (Join-Path $repo $probe); Arm = $arm; Label = $label; HoldSeconds = $HoldSeconds }
  if($Fo){ $runArgs['Fo'] = $Fo }
  & $runner @runArgs

  # switch arms ONLY on an armed window; a staging loss keeps us on the same arm
  $last = $null
  if(Test-Path $csv){ $last = @(Import-Csv $csv | Where-Object { $_.label -eq $label })[0] }
  if($null -ne $last -and ($last.outcome -eq 'DIED' -or $last.outcome -eq 'SURVIVED')){
    Say ("armed window recorded: {0} -> {1}; switching arm" -f $label,$last.outcome)
    $arm = if($arm -eq $ControlArm){ $TreatmentArm } else { $ControlArm }
  } else {
    $o = if($null -ne $last){ $last.outcome } else { 'unknown' }
    Say ("no armed window ({0}); staying on {1}" -f $o, $arm)
  }
  Start-Sleep -Seconds 5
}

Say 'campaign finished'
$ac = Get-Armed $ControlArm; $at = Get-Armed $TreatmentArm
Say ("final: {0} launches, armed windows control={1} treatment={2}" -f $launch,$ac,$at)
