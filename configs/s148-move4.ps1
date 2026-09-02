<#
.SYNOPSIS
  S148 Move-4 flight helper: chain S149 bind-only + S148 self-damage in one sitting.

.DESCRIPTION
  Move 4 goal: produce the first live AdjustHealth receipt on the force-open route
  (WALL E Phase 1a). S148 flight 4 refused with issues=0x3EC13F on a fresh route
  because the selected ASC read `AvatarActor@0x410 = 0x0` -- no bind step ran
  in front of it (docs/s148-self-damage-flight4.md:187-189, docs/s148-self-damage-
  flight4.md:159-162).

  This helper stages a tutorial world, injects the S149-bind-only DLL to force
  the AvatarActor bind (the S143-proven path at tutorial_launch.cpp:20041-20073),
  runs a READ-ONLY verifier to confirm the bind is live + the ASC has attribute
  sets, and only then injects the S148 self-damage DLL.

  Injection sequence (5 steps + 1 verifier):

    1. gft_ready_fix.dll                (fk24-stage.ps1 step 1)
    2. tutorial_launch_fo.dll           (fk24-stage.ps1 step 2)
    3. tutorial_launch_sp.dll           (fk24-stage.ps1 step 3)
       ^ steps 1-3 via `fk24-stage.ps1 -SkipProbe`
    4. S149 bind-only DLL               (manual inject.exe mmap)
       gate on marker: '[GAS] PLAYER-POST-BIND ... *** BOUND ***'
    5. VERIFIER: tools/re/move4_bind_verify.py <PID> --hero <hex>
       exit 0 => AvatarActor bound AND SpawnedAttributes populated
       exit 3 => bind lost
       exit 4 => bind live but no attribute sets (skip S148 to preserve draw)
    6. S148 self-damage DLL             (manual inject.exe mmap)
       gate on marker: 'RESULT=' anything

  DEPENDS ON: configs/capture-gate.ps1 (S149-fix) via -ResetCapture on
  launch-redirect.ps1. Run launch-redirect.ps1 -ResetCapture SEPARATELY (with
  Steam running) BEFORE invoking this helper -- this script does not launch the
  backend or the game.

.PARAMETER BindDll
  Path to the KBFBINDONLY=1 DLL (typically tools/sigbypass-mod/build/
  tutorial_launch_botfight_bind_only.dll).

.PARAMETER S148Dll
  Path to the S148 self-damage DLL (typically tools/sigbypass-mod/build/
  tutorial_launch_botfight_damage_self_cal.dll). Its sha256 should match the
  frozen ExpectedProbeSha256 in fk24-stage.ps1:51 -- pass -ExpectedS148Sha256
  to pin.

.PARAMETER ExpectedBindSha256
  Optional whole-file sha256 pin for the bind-only DLL. When set, the helper
  refuses to inject if the on-disk file doesn't match.

.PARAMETER ExpectedS148Sha256
  Optional whole-file sha256 pin for the S148 DLL. Match the frozen artifact
  hash: C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E.

.PARAMETER Label
  Evidence label. Used to name copied markers and captures.

.PARAMETER InjectGapSeconds
  Minimum wait between consecutive injections. Default 20 -- see CLAUDE.md
  S109 for the ~71x hazard reduction at gap >= 10 s. Do NOT go below 10.

.PARAMETER WaitBindReceiptSec
  Max wait for the S149 [GAS] PLAYER-POST-BIND marker after bind-only injection.
  Default 60.

.PARAMETER WaitS148ResultSec
  Max wait for the S148 RESULT marker after S148 injection. Default 180.
#>
param(
    [Parameter(Mandatory=$true)][string]$BindDll,
    [Parameter(Mandatory=$true)][string]$S148Dll,
    [string]$ExpectedBindSha256 = "",
    [string]$ExpectedS148Sha256 = "",
    [string]$Label = "s148-move4",
    [int]$InjectGapSeconds = 20,
    [int]$WaitBindReceiptSec = 60,
    [int]$WaitS148ResultSec = 180
)

$ErrorActionPreference = 'Stop'
$repo   = Split-Path -Parent $PSScriptRoot
$docs   = Join-Path $repo 'docs'
$marker = Join-Path $docs 'tutorial-launch-marker.txt'
$inject = Join-Path $repo 'tools\inject\inject.exe'
$verify = Join-Path $repo 'tools\re\move4_bind_verify.py'
$staker = Join-Path $PSScriptRoot 'fk24-stage.ps1'

function Say([string]$m){ Write-Host "[move4] $m" -ForegroundColor Cyan }
function SayErr([string]$m){ Write-Host "[move4] $m" -ForegroundColor Red }

# ---- Preconditions ------------------------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if(-not $isAdmin){ SayErr "elevation required (inject.exe manual-map needs it)"; exit 10 }
foreach($p in @($BindDll,$S148Dll,$inject,$verify,$staker)){
    if(-not (Test-Path -LiteralPath $p)){ SayErr "missing required file: $p"; exit 11 }
}

function AssertSha([string]$path,[string]$expected,[string]$who){
    if([string]::IsNullOrWhiteSpace($expected)){ return }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToUpperInvariant()
    $want   = $expected.ToUpperInvariant()
    if($actual -ne $want){
        SayErr "sha256 mismatch on $who : expected=$want actual=$actual path=$path"
        exit 12
    }
    Say "sha256 pin OK on $who : $actual"
}
AssertSha $BindDll $ExpectedBindSha256 "bind-only DLL"
AssertSha $S148Dll $ExpectedS148Sha256 "S148 DLL"

# Find the live game. Must be exactly one instance.
$procs = @(Get-Process SUPERVIVE-Win64-Shipping -ErrorAction SilentlyContinue)
if($procs.Count -eq 0){ SayErr "no SUPERVIVE-Win64-Shipping process; launch it with launch-redirect.ps1 -ResetCapture first"; exit 13 }
if($procs.Count -gt 1){ SayErr "multiple SUPERVIVE-Win64-Shipping processes -- refuse to guess"; exit 13 }
$gamePid = $procs[0].Id
Say "game PID=$gamePid"

# Backup marker BEFORE staging so we can compare timestamps.
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$evidenceDir = Join-Path $docs "s148-move4-$Label-$stamp"
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
Say "evidence dir: $evidenceDir"

function CopyEvidence([string]$srcName,[string]$suffix){
    $src = Join-Path $docs $srcName
    if(Test-Path -LiteralPath $src){
        $dst = Join-Path $evidenceDir "$srcName-$suffix"
        Copy-Item -LiteralPath $src $dst -Force
    }
}

# ---- Step 1-3: stage gft -> fo -> sp via fk24-stage.ps1 -SkipProbe --------------------------
Say "=== steps 1-3: staging gft -> fo -> sp (fk24-stage.ps1 -SkipProbe) ==="
& $staker -SkipProbe -Label "$Label-stage" -InjectGapSeconds $InjectGapSeconds
if($LASTEXITCODE -ne 0){
    SayErr "fk24-stage.ps1 -SkipProbe FAILED (exit $LASTEXITCODE)"
    exit 20
}
CopyEvidence 'tutorial-launch-marker.txt' 'after-stage'
Say "stage complete; game still running with tutorial world staged"

# ---- Step 4: inject the bind-only DLL --------------------------------------------------------
Say "=== step 4: waiting $InjectGapSeconds s before bind-only inject ==="
Start-Sleep -Seconds $InjectGapSeconds

# Snapshot marker length BEFORE inject so we can detect its truncation-on-inject (FK-25).
$markerLenBefore = if(Test-Path $marker){ (Get-Item $marker).Length } else { 0 }
Say "marker length before bind-only inject: $markerLenBefore bytes"

Say "=== step 4: manual-mapping bind-only DLL: $BindDll ==="
& $inject mmap $gamePid $BindDll
if($LASTEXITCODE -ne 0){ SayErr "inject.exe FAILED on bind-only (exit $LASTEXITCODE)"; exit 21 }

# Wait for the S149 bind receipt.
Say "=== step 4: waiting up to $WaitBindReceiptSec s for '[GAS] PLAYER-POST-BIND ... *** BOUND ***' ==="
$deadline = (Get-Date).AddSeconds($WaitBindReceiptSec)
$bindLine = $null
while((Get-Date) -lt $deadline){
    if(Test-Path $marker){
        $lines = Get-Content -LiteralPath $marker -ErrorAction SilentlyContinue
        foreach($ln in $lines){
            if($ln -match 'PLAYER-POST-BIND.*Avatar@0x410=(0x[0-9A-Fa-f]+).*\*\*\* BOUND \*\*\*'){
                $bindLine = $ln
                break
            }
        }
        if($bindLine){ break }
    }
    Start-Sleep -Milliseconds 500
}
if(-not $bindLine){
    SayErr "no bind receipt within $WaitBindReceiptSec s -- bind-only either refused or bindshim marker format changed"
    CopyEvidence 'tutorial-launch-marker.txt' 'bind-timeout'
    exit 22
}
$heroPtr = $Matches[1]
Say "bind receipt seen; parsed hero pointer = $heroPtr"
CopyEvidence 'tutorial-launch-marker.txt' 'after-bind'

# ---- Step 5: verifier ------------------------------------------------------------------------
Say "=== step 5: verifying bind + attribute-set state via move4_bind_verify.py ==="
$py = 'python'  # any python3 on PATH; the pre-commit hook policy applies to commits, not this
$verifyOut = Join-Path $evidenceDir "move4_bind_verify-$Label.out.txt"
& $py $verify $gamePid --hero $heroPtr *> $verifyOut
$verifyExit = $LASTEXITCODE
Say "verifier exit=$verifyExit  output -> $verifyOut"
Get-Content $verifyOut | ForEach-Object { Write-Host "  $_" }

switch($verifyExit){
    0 { Say "verifier PASS -- proceed to S148 injection" }
    3 { SayErr "verifier FAIL_BIND_LOST -- S148 would refuse; skipping S148 injection to preserve FK-32 draw"; exit 3 }
    4 { SayErr "verifier FAIL_NO_ATTRSET -- bind is live but SpawnedAttributes empty; skipping S148 to preserve draw"; exit 4 }
    5 { SayErr "verifier FAIL_NO_ASC -- something is very wrong; skipping"; exit 5 }
    6 { SayErr "verifier FAIL_HERO_MALFORMED"; exit 6 }
    9 { SayErr "verifier FAIL_INSTRUMENT -- verifier itself couldn't run; do not proceed"; exit 9 }
    default { SayErr "verifier UNKNOWN exit=$verifyExit -- refusing to proceed"; exit 30 }
}

# ---- Step 6: inject S148 self-damage DLL -----------------------------------------------------
Say "=== step 6: waiting $InjectGapSeconds s before S148 inject ==="
Start-Sleep -Seconds $InjectGapSeconds

Say "=== step 6: manual-mapping S148 DLL: $S148Dll ==="
& $inject mmap $gamePid $S148Dll
if($LASTEXITCODE -ne 0){ SayErr "inject.exe FAILED on S148 (exit $LASTEXITCODE)"; exit 31 }

# Wait for the S148 RESULT.
Say "=== step 6: waiting up to $WaitS148ResultSec s for 'RESULT=' in marker ==="
$deadline = (Get-Date).AddSeconds($WaitS148ResultSec)
$resultLine = $null
while((Get-Date) -lt $deadline){
    if(Test-Path $marker){
        $lines = Get-Content -LiteralPath $marker -ErrorAction SilentlyContinue
        foreach($ln in $lines){
            if($ln -match 'RESULT='){
                $resultLine = $ln
                break
            }
        }
        if($resultLine){ break }
    }
    Start-Sleep -Milliseconds 500
}
CopyEvidence 'tutorial-launch-marker.txt' 'after-s148'

if(-not $resultLine){
    SayErr "no RESULT= within $WaitS148ResultSec s -- process may have died or S148 hung"
    exit 32
}

Say "=== S148 RESULT ==="
Write-Host "  $resultLine" -ForegroundColor Green

if($resultLine -match 'RESULT=HEALTH_APPLIED'){
    Say "*** MOVE 4 SUCCESS: first live AdjustHealth receipt ***"
    exit 0
} elseif($resultLine -match 'RESULT=PREFLIGHT_REFUSED'){
    SayErr "S148 armed but refused; issue mask in the RESULT= line above tells you which precondition failed"
    exit 2
} else {
    SayErr "S148 unknown RESULT shape -- read the marker for the full context"
    exit 33
}
