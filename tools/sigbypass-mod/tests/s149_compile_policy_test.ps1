$ErrorActionPreference = 'Stop'

$shimRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $shimRoot 'tutorial_launch.cpp'
$cc = (Get-Command clang++.exe -ErrorAction Stop).Source

function Invoke-S149SyntaxCheck {
    param([string[]]$PolicyDefinitions)

    $compileArgs = @(
        '-fsyntax-only', '-std=c++17', '-Wall', '-Wextra', '-Wformat=2',
        '-DKRUNMODE=RM_BOTFIGHT', '-DKFRAMEINIT=1',
        '-DKFAULTINFO=1', '-DKOUTPARMRET=1', '-DKBFBINDONLY=1',
        '-DKFUNCSWAP=1'
    ) + $PolicyDefinitions + @($source)

    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& $cc @compileArgs 2>&1)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedPreference
    }
    [pscustomobject]@{
        ExitCode = $exitCode
        Text = (($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)
    }
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$valid = Invoke-S149SyntaxCheck @(
    '-DKBFARMS=0x02', '-DKBFOWNER=0', '-DKBFSELFCAL=0', '-DKBFNATURALINPUT=0'
)
Assert-True ($valid.ExitCode -eq 0) "the exact bind-only policy must compile: $($valid.Text)"
Assert-True ($valid.Text -notmatch '(?im)warning:.*format|format specifies') `
    "the warning-level compile found an S149/legacy format diagnostic: $($valid.Text)"

$broad = Invoke-S149SyntaxCheck @(
    '-DKBFARMS=0x03', '-DKBFOWNER=0', '-DKBFSELFCAL=0', '-DKBFNATURALINPUT=0'
)
Assert-True ($broad.ExitCode -ne 0 -and
    $broad.Text.Contains('S149 bind-only setup must compile exactly K_BIND: KBFARMS=0x02')) `
    'a spawn+bind artifact must fail the production compile-time policy guard'

$wrongOwner = Invoke-S149SyntaxCheck @(
    '-DKBFARMS=0x02', '-DKBFOWNER=1', '-DKBFSELFCAL=0', '-DKBFNATURALINPUT=0'
)
Assert-True ($wrongOwner.ExitCode -ne 0 -and
    $wrongOwner.Text.Contains('S149 bind-only setup must pass the exact live carrier')) `
    'a non-carrier InitAbilityActorInfo owner must fail the production compile-time policy guard'

$mixedPhase = Invoke-S149SyntaxCheck @(
    '-DKBFARMS=0x02', '-DKBFOWNER=0', '-DKBFSELFCAL=0', '-DKBFNATURALINPUT=1'
)
Assert-True ($mixedPhase.ExitCode -ne 0 -and
    $mixedPhase.Text.Contains('S149 bind-only setup must exclude S148 calibration and S147 natural input')) `
    'natural input must not compile into the isolated bind setup artifact'

Write-Host 'PASS s149_compile_policy_test'
