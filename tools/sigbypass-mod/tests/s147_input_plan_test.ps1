[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$helperPath = Join-Path $PSScriptRoot '..\..\..\configs\s147-natural-input.ps1'
$helperSource = Get-Content -LiteralPath $helperPath -Raw

$tokens = $null
$parseErrors = $null
$helperAst = [System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path $helperPath).Path, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) {
    throw "S147 helper parse failed: $($parseErrors.Message -join '; ')"
}
$reservedPidVariables = @($helperAst.FindAll({
    param($node)
    $node -is [System.Management.Automation.Language.VariableExpressionAst] -and
        $node.VariablePath.UserPath -ieq 'pid'
}, $true))
if ($reservedPidVariables.Count -ne 0) {
    $locations = $reservedPidVariables | ForEach-Object { $_.Extent.StartLineNumber }
    throw "S147 helper must not assign or bind PowerShell's read-only PID variable (lines: $($locations -join ', '))."
}

# Regression: the live native marker is CRLF-terminated. Execute the helper's real matcher
# definitions so an LF-only end anchor cannot silently reject an exact bound marker line.
$boundPatternFunction = $helperAst.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'New-S147BoundMarkerPattern'
}, $true)
if ($null -eq $boundPatternFunction) {
    throw 'S147 helper is missing New-S147BoundMarkerPattern.'
}
. ([scriptblock]::Create($boundPatternFunction.Extent.Text))

$nodeCountFunction = $helperAst.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'Get-S147NodeCount'
}, $true)
if ($null -eq $nodeCountFunction) {
    throw 'S147 helper is missing Get-S147NodeCount.'
}
. ([scriptblock]::Create($nodeCountFunction.Extent.Text))
$crlfMarker = "[S147][BP] Toggle Map pid=4308 run=000010D4008D696A count=1 qpc=92699068874`r`n"
$crlfCount = Get-S147NodeCount -Content $crlfMarker -NodeName 'Toggle Map' `
    -BoundPid 4308 -Run '000010D4008D696A'
if ($crlfCount -ne 1) {
    throw "S147 helper must count an exact CRLF-terminated receipt; got $crlfCount."
}
$lfMarker = "[S147][BP] Toggle Map pid=4308 run=000010D4008D696A count=1 qpc=92699068874`n"
$lfCount = Get-S147NodeCount -Content $lfMarker -NodeName 'Toggle Map' `
    -BoundPid 4308 -Run '000010D4008D696A'
if ($lfCount -ne 1) {
    throw "S147 helper must count an exact LF-terminated receipt; got $lfCount."
}
$extendedNodeMarker = "[S147][BP] Toggle Map-Other pid=4308 run=000010D4008D696A count=1`r`n"
$extendedNodeCount = Get-S147NodeCount -Content $extendedNodeMarker -NodeName 'Toggle Map' `
    -BoundPid 4308 -Run '000010D4008D696A'
if ($extendedNodeCount -ne 0) {
    throw "S147 helper must reject a longer node name sharing the requested prefix; got $extendedNodeCount."
}
$terminalPattern = New-S147BoundMarkerPattern -LinePrefix '[S147] RESULT' `
    -BoundPid 4308 -Run '000010D4008D696A'
$terminalMarker = "[S147] RESULT pid=4308 run=000010D4008D696A reason=SUCCESS`r`n"
if ([Regex]::Matches($terminalMarker, $terminalPattern).Count -ne 1) {
    throw 'S147 helper must match an exact CRLF-terminated terminal result.'
}
$foreignTerminalMarker = "[S147] RESULT pid=4309 run=000010D4008D696A reason=SUCCESS`r`n"
if ([Regex]::Matches($foreignTerminalMarker, $terminalPattern).Count -ne 0) {
    throw 'S147 helper terminal matcher must reject a result from another PID.'
}

$foregroundResolver = $helperAst.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'Resolve-S147OwnedForegroundWindow'
}, $true)
if ($null -eq $foregroundResolver) {
    throw 'S147 helper is missing Resolve-S147OwnedForegroundWindow.'
}
. ([scriptblock]::Create($foregroundResolver.Extent.Text))
$ownedAlternateWindow = Resolve-S147OwnedForegroundWindow `
    -ForegroundWindow ([IntPtr]0xA0B70) -ForegroundPid 29920 -ExpectedPid 29920
if ($ownedAlternateWindow -ne [IntPtr]0xA0B70) {
    throw 'S147 helper must accept a non-main foreground HWND owned by the exact bound PID.'
}
if ((Resolve-S147OwnedForegroundWindow -ForegroundWindow ([IntPtr]0xA0B70) `
        -ForegroundPid 29921 -ExpectedPid 29920) -ne [IntPtr]::Zero) {
    throw 'S147 helper must reject a foreground HWND owned by any other PID.'
}
if ((Resolve-S147OwnedForegroundWindow -ForegroundWindow ([IntPtr]::Zero) `
        -ForegroundPid 29920 -ExpectedPid 29920) -ne [IntPtr]::Zero) {
    throw 'S147 helper must reject a null foreground HWND even when the PID value matches.'
}

foreach ($needle in @(
    '[int]$TerminalTimeoutSeconds = 40',
    "Get-Process -Id `$ready.Pid",
    'Get-Process -Id $ExpectedPid',
    "-cne `$ExpectedProcessName",
    'pid=<decimal> run=<16 hex>',
    '-EmergencyRelease',
    '$markerBaseline = Read-S147Marker',
    '$content.StartsWith($BaselineContent, [StringComparison]::Ordinal)',
    '-ExpectedPid and -ExpectedRun must be supplied together.'
)) {
    if (-not $helperSource.Contains($needle)) {
        throw "S147 helper hardening contract missing: $needle"
    }
}

$powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
$childOutput = @(& $powershell -NoProfile -ExecutionPolicy Bypass -File $helperPath -PlanOnly -ShiftHoldMs 350 2>&1)
$childExitCode = $LASTEXITCODE
if ($childExitCode -ne 0) {
    throw "S147 helper fresh-process plan failed with exit code ${childExitCode}: $($childOutput -join [Environment]::NewLine)"
}
$json = $childOutput -join [Environment]::NewLine

$missingMarker = Join-Path ([System.IO.Path]::GetTempPath()) `
    ("s147-input-plan-test-{0}.txt" -f [Guid]::NewGuid().ToString('N'))
$savedErrorActionPreference = $ErrorActionPreference
try {
    # These child runs are expected to write a terminating error to stderr. Capture that stderr as
    # test data without letting Windows PowerShell promote NativeCommandError in the parent.
    $ErrorActionPreference = 'Continue'
    $attachOutput = @(& $powershell -NoProfile -ExecutionPolicy Bypass -File $helperPath `
        -MarkerPath $missingMarker -ReadyTimeoutSeconds 1 `
        -ExpectedPid 1 -ExpectedRun '0000000000000000' 2>&1)
    $attachExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedErrorActionPreference
}
$attachText = $attachOutput -join [Environment]::NewLine
if ($attachExitCode -eq 0 -or $attachText -notlike '*Timed out waiting for a current S147 READY marker*') {
    throw "S147 helper explicit attach-mode binding failed before the expected no-input READY timeout: $attachText"
}

$readyMarker = Join-Path ([System.IO.Path]::GetTempPath()) `
    ("s147-input-plan-ready-{0}.txt" -f [Guid]::NewGuid().ToString('N'))
$syntheticRun = '1111111111111111'
try {
    Set-Content -LiteralPath $readyMarker -Encoding Ascii `
        -Value "[S147] READY FOR INPUT pid=$PID run=$syntheticRun"
    try {
        $ErrorActionPreference = 'Continue'
        $readyOutput = @(& $powershell -NoProfile -ExecutionPolicy Bypass -File $helperPath `
            -MarkerPath $readyMarker -ReadyTimeoutSeconds 1 `
            -ExpectedPid $PID -ExpectedRun $syntheticRun 2>&1)
        $readyExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    $readyText = $readyOutput -join [Environment]::NewLine
    if ($readyExitCode -eq 0 -or $readyText -notlike '*Stale/mismatched S147 READY marker*') {
        throw "S147 helper did not parse and safely reject a live non-game PID/run binding: $readyText"
    }
} finally {
    Remove-Item -LiteralPath $readyMarker -Force -ErrorAction SilentlyContinue
}

$plan = $json | ConvertFrom-Json
$expected = @(
    'WaitReady:',
    'FocusProcess:SUPERVIVE-Win64-Shipping',
    'KeyDown:Tab',
    'KeyUp:Tab',
    'WaitNodeCount:Toggle Map',
    'KeyDown:Tab',
    'KeyUp:Tab',
    'WaitNodeCount:Toggle Map',
    'KeyDown:LeftShift',
    'Delay:350',
    'KeyUp:LeftShift',
    'WaitTerminal:'
)

$actual = @($plan | ForEach-Object { '{0}:{1}' -f $_.Kind, $_.Value })
if ($actual.Count -ne $expected.Count) {
    throw "Expected $($expected.Count) actions, got $($actual.Count): $($actual -join ', ')"
}
for ($i = 0; $i -lt $expected.Count; $i++) {
    if ($actual[$i] -cne $expected[$i]) {
        throw "Action $i mismatch: expected '$($expected[$i])', got '$($actual[$i])'"
    }
}

Write-Output 'PASS s147_input_plan_test'
