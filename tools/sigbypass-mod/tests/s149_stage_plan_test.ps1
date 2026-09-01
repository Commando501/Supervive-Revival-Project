$ErrorActionPreference = 'Stop'

$stage = Join-Path $PSScriptRoot '..\..\..\configs\fk24-stage.ps1'
$gateModule = Join-Path $PSScriptRoot '..\..\..\configs\s149-bind-gate.ps1'
$worktree = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$powerShell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$powerShellSha256 = '9785001B0DCF755EDDB8AF294A373C0B87B2498660F724E76C4D53F9C217C7A3'
$stageSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $stage).Hash
$gateSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $gateModule).Hash
$s149ContractSha256 = '900BBD4256940F769B406B9AC21AA4DE21A644E191E16C148BCA509C4BBF6619'
$s148ContractSha256 = '62744FE30DD5A849B20361C5C0A15B72E7879BB67FA1BED90B93FA94A99D4FBB'
. $gateModule

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$raw = & $powerShell -NoProfile -ExecutionPolicy Bypass -File $stage `
    -Probe 'frozen-s148.dll' -BindOnly 'bind-only.dll' -PlanOnly `
    -ExpectedControllerWorktree $worktree -ExpectedStagerSha256 $stageSha256 `
    -ExpectedS149GateSha256 $gateSha256 -ExpectedPowerShellPath $powerShell `
    -ExpectedPowerShellSha256 $powerShellSha256 `
    -ExpectedS149ContractSha256 $s149ContractSha256 `
    -ExpectedS148ContractSha256 $s148ContractSha256 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "bind-mode plan failed with exit code $LASTEXITCODE`: $($raw -join [Environment]::NewLine)"
}
$plan = ($raw -join [Environment]::NewLine) | ConvertFrom-Json
$injects = @($plan.steps | Where-Object kind -eq 'inject')
Assert-True ($plan.mode -eq 'bind-then-s148') 'the opt-in plan must identify the bind-then-S148 mode'
Assert-True ($injects.Count -eq 5) 'the controlled route must contain exactly five injections'
Assert-True (($injects.name -join ',') -eq 'gft,fo,sp,bind-only,s148') `
    'the controlled route must preserve exact gft -> fo -> sp -> bind-only -> S148 order'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'gate' -and $_.name -eq 'bind-ready' }).Count -eq 1) `
    'the plan must contain exactly one bind-ready admission gate'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'ledger' -and $_.name -eq 's148-attempt' }).Count -eq 1) `
    'the plan must record exactly one durable S148 attempt before injection'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'gate' -and $_.name -eq 'backend-identity' }).Count -eq 1) `
    'the plan must bind the capture generation to one exact backend process'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'gate' -and $_.name -eq 'watcher-bound' }).Count -eq 1) `
    'the plan must prove one 50 ms crashwatch is attached to the exact game PID'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'gate' -and $_.name -eq 'one-arm-ledger-empty' }).Count -eq 1) `
    'the controlled route must refuse an existing same-PID/start ledger before its first map'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'archive' -and $_.name -eq 'sp-ready' }).Count -eq 1) `
    'the completed spawn/possess marker must be archived before bind truncates it'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'archive' -and $_.name -eq 'bind-ready' }).Count -eq 1) `
    'the completed bind marker must be archived before S148 truncates it'
Assert-True (@($plan.steps | Where-Object { $_.kind -eq 'gate' -and $_.name -eq 's148-terminal' }).Count -eq 1) `
    'the plan must archive one terminal S148 generation without a retry branch'

$stageSource = Get-Content -LiteralPath $stage -Raw
foreach($bootstrapParameter in @('ExpectedControllerWorktree','ExpectedStagerSha256','ExpectedS149GateSha256',
    'ExpectedPowerShellPath','ExpectedPowerShellSha256','ExpectedS149ContractSha256','ExpectedS148ContractSha256')){
    Assert-True ($stageSource.Contains("[string]`$$bootstrapParameter")) `
        "controlled stager must require bootstrap parameter $bootstrapParameter"
}
$bootstrapGate = $stageSource.IndexOf('Assert-S149StagerBootstrap', [StringComparison]::Ordinal)
$gateLoad = $stageSource.IndexOf(". `$s149Gate", [StringComparison]::Ordinal)
Assert-True ($bootstrapGate -ge 0 -and $gateLoad -gt $bootstrapGate) `
    'stager self/gate/contract/PowerShell bootstrap provenance must pass before gate execution'
$captureDefault = "Join-Path `$repo 'docs\capture.log'"
Assert-True ($stageSource.Contains('[string]$CapturePath') -and
    $stageSource.Contains($captureDefault) -and
    -not $stageSource.Contains("Join-Path `$runtimeDocs 'capture.log'") -and
    $stageSource.Contains('bind mode pins -CapturePath to the current worktree backend generation')) `
    'RuntimeRepo may select the hard-coded marker/tool tree but must not silently redirect current-backend capture evidence'
Assert-True ($stageSource.Contains("'G:\git\Supervive Revival Project'") -and
    $stageSource.Contains('bind mode requires explicit -RuntimeRepo') -and
    $stageSource.Contains("Join-Path `$runtimeDocs 's149-ledgers'")) `
    'bind mode must pin the hard-coded runtime tree and keep the one-arm ledger outside caller-selectable evidence storage'
Assert-True ($stageSource.Contains('Assert-S149WatcherIdentity') -and
    $stageSource.Contains('Get-S149WatcherReceiptResult') -and
    $stageSource.Contains('6DAA73BF7238C0A0D91490CA10C38096F88CAA3841C333BBA89B8C55A57B2FCF')) `
    'live admission must enforce the exact worktree crashwatch artifact and attachment receipt'
Assert-True ($stageSource.Contains('Get-S149LokiEvidenceResult') -and
    $stageSource.Contains('Get-S149CaptureEvidenceResult') -and
    -not $stageSource.Contains('Test-S149EvidenceFileFreshness')) `
    'parked-state admission must parse timestamps on matching lines rather than trusting whole-file mtime'
Assert-True ($stageSource.Contains('[Diagnostics.Stopwatch]::GetTimestamp()') -and
    $stageSource.Contains('Get-S149RemainingGapMilliseconds')) `
    'bind-mode spacing must use a monotonic timestamp source'
$gateSource = Get-Content -LiteralPath $gateModule -Raw
Assert-True ($gateSource.Contains('$stream.Flush($true)') -and
    $gateSource.Contains('[IO.FileMode]::CreateNew')) `
    'the authoritative one-arm ledger must be CreateNew and flushed through the OS boundary'
$bindGateCondition = $stageSource.LastIndexOf('if($BindOnly', $gateLoad, [StringComparison]::Ordinal)
Assert-True ($gateLoad -gt 0 -and $bindGateCondition -ge 0) `
    'legacy staging must not gain an unconditional S149 module dependency'
$stageInjectStart = $stageSource.IndexOf('function Stage-Inject', [StringComparison]::Ordinal)
$s148Invoke = $stageSource.IndexOf('Stage-Inject $Probe 5', [StringComparison]::Ordinal)
$s148Ledger = $stageSource.IndexOf('New-S149AttemptLedger', $s148Invoke, [StringComparison]::Ordinal)
Assert-True ($stageInjectStart -ge 0 -and $s148Invoke -ge 0 -and $s148Ledger -gt $s148Invoke) `
    'the durable S148 ledger must be created by the final pre-map callback, after Stage-Inject spacing'
$firstMap = $stageSource.IndexOf('Stage-Inject $gftDll 1', [StringComparison]::Ordinal)
$earlyLedgerGate = $stageSource.IndexOf('Get-S149LedgerAdmissionResult', [StringComparison]::Ordinal)
Assert-True ($earlyLedgerGate -ge 0 -and $firstMap -gt $earlyLedgerGate) `
    'the canonical ledger nonexistence check must execute before the first map'
$mapCall = '$mapLines = @(& $inject mmap $gamePid $dll 2>&1)'
Assert-True ([regex]::IsMatch($stageSource,
    'Assert-S149TargetMapIdentity\r?\n\s+foreach\(\$locked in \$lockedArtifacts\)\{[\s\S]*?' +
    'Assert-S149MapPathProvenance[\s\S]*?' + [regex]::Escape($mapCall))) `
    'exact target identity and held-byte path provenance must form the final boundary before mmap'
Assert-True ($stageSource.Contains('Get-S149MarkerGenerationResult') -and
    $stageSource.Contains('Get-S149StageMarkerGeneration 3') -and
    $stageSource.Contains('Get-S149StageMarkerGeneration 4') -and
    $stageSource.Contains('Get-S149StageMarkerGeneration 5')) `
    'SP, bind, and frozen S148 admission must each require post-map marker generation change'
$lockedOpen = $stageSource.IndexOf('Open-S149LockedArtifact', $stageInjectStart, [StringComparison]::Ordinal)
$finalTarget = if($lockedOpen -ge 0){
    $stageSource.IndexOf('Assert-S149TargetMapIdentity', $lockedOpen, [StringComparison]::Ordinal)
}else{-1}
$lockedMap = if($finalTarget -ge 0){
    $stageSource.IndexOf($mapCall, $finalTarget, [StringComparison]::Ordinal)
}else{-1}
$lockedDispose = if($lockedMap -ge 0){
    $stageSource.IndexOf('.Stream.Dispose()', $lockedMap, [StringComparison]::Ordinal)
}else{-1}
Assert-True ($lockedOpen -gt $stageInjectStart -and $finalTarget -gt $lockedOpen -and
    $lockedMap -gt $finalTarget -and $lockedDispose -gt $lockedMap) `
    'final injector/DLL stream locks must span exact hashing, target identity, and mmap completion'
$lockedWindow = if($lockedOpen -ge 0 -and $lockedMap -gt $lockedOpen){
    $stageSource.Substring($lockedOpen,$lockedMap-$lockedOpen)
}else{''}
Assert-True (-not $lockedWindow.Contains('Get-FileHash')) `
    'the final locked artifact window must not reopen either mutable artifact by path'
Assert-True ($stageSource.Contains('$mk = $spGeneration.Text') -and
    $stageSource.Contains('$text = $bindGeneration.Text') -and
    $stageSource.Contains('$text = $s148Generation.Text') -and
    $stageSource.Contains('Write-S149ImmutableSnapshot')) `
    'admission and immutable archives must consume the same accepted atomic marker snapshot'

$frequency = 10000000L
$gap = Get-S149RemainingGapMilliseconds `
    -LastTimestamp 1000000000L -NowTimestamp 1195000000L `
    -Frequency $frequency -MinimumSeconds 20
Assert-True ($gap -eq 500) 'a 19.5-second gap must still require exactly 500 ms'
$completeGap = Get-S149RemainingGapMilliseconds `
    -LastTimestamp 1000000000L -NowTimestamp 1200000000L `
    -Frequency $frequency -MinimumSeconds 20
Assert-True ($completeGap -eq 0) 'an exact 20-second gap must require no further wait'

$savedPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$tooShort = & $powerShell -NoProfile -ExecutionPolicy Bypass -File $stage `
    -Probe 'frozen-s148.dll' -BindOnly 'bind-only.dll' -PlanOnly -InjectGapSeconds 19 `
    -ExpectedControllerWorktree $worktree -ExpectedStagerSha256 $stageSha256 `
    -ExpectedS149GateSha256 $gateSha256 -ExpectedPowerShellPath $powerShell `
    -ExpectedPowerShellSha256 $powerShellSha256 `
    -ExpectedS149ContractSha256 $s149ContractSha256 `
    -ExpectedS148ContractSha256 $s148ContractSha256 2>&1
$tooShortExit = $LASTEXITCODE
$ErrorActionPreference = $savedPreference
Assert-True ($tooShortExit -ne 0) 'bind mode must refuse an injection gap below 20 seconds'

Write-Host 'PASS s149_stage_plan_test'
