$ErrorActionPreference = 'Stop'

$gateModule = Join-Path $PSScriptRoot '..\..\..\configs\s149-bind-gate.ps1'
$stage = Join-Path $PSScriptRoot '..\..\..\configs\fk24-stage.ps1'
. $gateModule

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$stageSource = [IO.File]::ReadAllText($stage)
foreach($bootstrapParameter in @('ExpectedControllerWorktree','ExpectedStagerSha256','ExpectedS149GateSha256',
    'ExpectedPowerShellPath','ExpectedPowerShellSha256','ExpectedS149ContractSha256','ExpectedS148ContractSha256')){
    Assert-True ($stageSource.Contains("[string]`$$bootstrapParameter")) `
        "stager bootstrap must expose $bootstrapParameter"
}
$bootstrapIndex = $stageSource.IndexOf('Assert-S149StagerBootstrap', [StringComparison]::Ordinal)
$gateLoadIndex = $stageSource.IndexOf(". `$s149Gate", [StringComparison]::Ordinal)
Assert-True ($bootstrapIndex -ge 0 -and $gateLoadIndex -gt $bootstrapIndex) `
    'bootstrap provenance must refuse before any sentinel gate can execute'
Assert-True ($stageSource.Contains('& $script:verifiedPowerShellPath -NoProfile')) `
    'artifact contracts must run only through the exact bootstrap-bound PowerShell executable'
Assert-True ($stageSource.Contains('Confirm-S149StagerContractPin')) `
    'PowerShell, contract, and artifact provenance must be revalidated immediately after each contract child'
$stageInjectSource = $stageSource.Substring($stageSource.IndexOf('function Stage-Inject', [StringComparison]::Ordinal))
Assert-True (([regex]::Matches($stageInjectSource, 'Assert-S149MapPathProvenance')).Count -ge 2) `
    'each bind-mode map must no-reparse/hash injector and DLL at lock and immediately before mmap'

# Execute a copied stager in a test-owned tree with a sentinel gate. A bad gate
# bootstrap hash must terminate before dot-sourcing that gate, even though the
# copied stager itself, both contract leaves, and the exact host PowerShell pin
# are otherwise correct.
$bootstrapRoot = Join-Path ([IO.Path]::GetTempPath()) ('s149-bootstrap-' + [guid]::NewGuid().ToString('N'))
$bootstrapConfigs = Join-Path $bootstrapRoot 'configs'
$bootstrapTests = Join-Path $bootstrapRoot 'tools\sigbypass-mod\tests'
$bootstrapSentinel = Join-Path $bootstrapRoot 'gate-executed.txt'
try {
    [IO.Directory]::CreateDirectory($bootstrapConfigs) | Out-Null
    [IO.Directory]::CreateDirectory($bootstrapTests) | Out-Null
    $bootstrapStage = Join-Path $bootstrapConfigs 'fk24-stage.ps1'
    $bootstrapGate = Join-Path $bootstrapConfigs 's149-bind-gate.ps1'
    $bootstrapS149Contract = Join-Path $bootstrapTests 's149_bind_contract_test.ps1'
    $bootstrapS148Contract = Join-Path $bootstrapTests 's148_build_contract_test.ps1'
    [IO.File]::Copy($stage, $bootstrapStage)
    $escapedSentinel = $bootstrapSentinel.Replace("'", "''")
    [IO.File]::WriteAllText($bootstrapGate,
        "[IO.File]::WriteAllText('$escapedSentinel','EXECUTED')`r`n",
        [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($bootstrapS149Contract, '', [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($bootstrapS148Contract, '', [Text.UTF8Encoding]::new($false))
    $bootstrapPowerShell = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    $bootstrapPowerShellHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $bootstrapPowerShell).Hash
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $bootstrapOutput = @(& $bootstrapPowerShell -NoProfile -ExecutionPolicy Bypass -File $bootstrapStage `
            -Probe 'probe.dll' -BindOnly 'bind.dll' -PlanOnly `
            -ExpectedControllerWorktree $bootstrapRoot `
            -ExpectedStagerSha256 ((Get-FileHash -Algorithm SHA256 -LiteralPath $bootstrapStage).Hash) `
            -ExpectedS149GateSha256 ('0' * 64) `
            -ExpectedPowerShellPath $bootstrapPowerShell `
            -ExpectedPowerShellSha256 $bootstrapPowerShellHash `
            -ExpectedS149ContractSha256 ((Get-FileHash -Algorithm SHA256 -LiteralPath $bootstrapS149Contract).Hash) `
            -ExpectedS148ContractSha256 ((Get-FileHash -Algorithm SHA256 -LiteralPath $bootstrapS148Contract).Hash) 2>&1)
        $bootstrapExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    Assert-True ($bootstrapExit -ne 0) 'mismatched bootstrap gate hash must refuse the copied stager'
    Assert-True (-not [IO.File]::Exists($bootstrapSentinel)) `
        "mismatched bootstrap executed the sentinel gate: $($bootstrapOutput -join ' | ')"
} finally {
    if ([IO.Directory]::Exists($bootstrapRoot)) { [IO.Directory]::Delete($bootstrapRoot, $true) }
}

# Break caught: a time-only request line from the prior day must not alias the
# current game's local time merely because the backend/capture stayed up >24 h.
$backendStartUtc = [datetime]'2026-08-25T05:03:50Z'
$gameStartUtc = [datetime]'2026-08-26T05:03:57.7589713Z'
$nowUtc = [datetime]'2026-08-26T05:05:00Z'
$dayOldAlias = '#37 00:04:10.468  GET /core-game/matches/stale-prior-day'
$captureAlias = Get-S149CaptureEvidenceResult -Text $dayOldAlias `
    -Needle 'core-game/matches' -CaptureCreationUtc $backendStartUtc.AddMilliseconds(25) `
    -BackendStartUtc $backendStartUtc -NotBeforeUtc $gameStartUtc -NowUtc $nowUtc `
    -LocalUtcOffsetMinutes -300
Assert-True (-not $captureAlias.Valid -and $captureAlias.Reason -eq 'CAPTURE_DATE_BOUNDARY') `
    'a time-only capture line must refuse when the exact backend generation crossed a local date boundary'

# Break caught: command validation must compare argv tokens, not substrings
# ("-poll 500" contains the unsafe substring "-poll 50").
$watcherExe = 'C:\worktree\tools\usmapdump\usmapdump.exe'
$watcherOut = 'C:\worktree\dumps\crash-s149'
$lokiPath = 'C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log'
$exactCommand = '"C:\worktree\tools\usmapdump\usmapdump.exe" crashwatch SUPERVIVE-Win64-Shipping.exe ' +
    '"C:\worktree\dumps\crash-s149" -log ' +
    '"C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log" -poll 50'
$exactCommandGate = Get-S149WatcherCommandResult -CommandLine $exactCommand `
    -ExpectedExecutablePath $watcherExe -ExpectedGameName 'SUPERVIVE-Win64-Shipping.exe' `
    -ExpectedOutputDir $watcherOut -ExpectedLokiPath $lokiPath
Assert-True $exactCommandGate.Valid 'the exact eight-token crashwatch command must pass'
$slowCommandGate = Get-S149WatcherCommandResult `
    -CommandLine ($exactCommand.Substring(0,$exactCommand.Length - 2) + '500') `
    -ExpectedExecutablePath $watcherExe -ExpectedGameName 'SUPERVIVE-Win64-Shipping.exe' `
    -ExpectedOutputDir $watcherOut -ExpectedLokiPath $lokiPath
Assert-True (-not $slowCommandGate.Valid -and $slowCommandGate.Reason -eq 'WATCHER_COMMAND_TOKENS') `
    'the tokenized command gate must reject 500 ms rather than matching the 50 ms prefix'

# Break caught: a receipt from a prior watcher/log generation must not bridge a
# new PID/start identity. Creation and write times are exact full UTC ticks.
$watcherStartUtc = [datetime]'2026-08-26T05:03:58Z'
$watcherLog = @'
crashwatch: pid 4242 (SUPERVIVE-Win64-Shipping.exe)
  log     : C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log
  outDir  : C:\worktree\dumps\crash-s149
  poll    : 50 ms   suspend-on-trigger: true
'@
$watcherReceipt = Get-S149WatcherReceiptResult -Text $watcherLog `
    -ExpectedGamePid 4242 -ExpectedWatcherPid 5050 `
    -ExpectedWatcherStartUtcTicks $watcherStartUtc.Ticks `
    -ExpectedLogCreationUtcTicks $watcherStartUtc.AddMilliseconds(-50).Ticks `
    -ActualLogCreationUtcTicks $watcherStartUtc.AddMilliseconds(-50).Ticks `
    -ActualLogLastWriteUtcTicks $watcherStartUtc.AddMilliseconds(50).Ticks `
    -NowUtcTicks $watcherStartUtc.AddSeconds(1).Ticks `
    -ExpectedLokiPath $lokiPath -ExpectedOutputDir $watcherOut
Assert-True $watcherReceipt.Valid 'one receipt in the exact watcher/log generation must pass'
$staleWatcherReceipt = Get-S149WatcherReceiptResult -Text $watcherLog `
    -ExpectedGamePid 4242 -ExpectedWatcherPid 5050 `
    -ExpectedWatcherStartUtcTicks $watcherStartUtc.Ticks `
    -ExpectedLogCreationUtcTicks $watcherStartUtc.AddDays(-1).Ticks `
    -ActualLogCreationUtcTicks $watcherStartUtc.AddDays(-1).Ticks `
    -ActualLogLastWriteUtcTicks $watcherStartUtc.AddDays(-1).AddSeconds(1).Ticks `
    -NowUtcTicks $watcherStartUtc.AddSeconds(1).Ticks `
    -ExpectedLokiPath $lokiPath -ExpectedOutputDir $watcherOut
Assert-True (-not $staleWatcherReceipt.Valid -and $staleWatcherReceipt.Reason -eq 'WATCHER_LOG_GENERATION') `
    'a stale receipt file must not bridge the exact current watcher PID/start identity'

# Break caught: marker text/hash/mtime must come from one writer-exclusive file
# handle. Parsing a second reopen can mix two generations; overlap is transient.
Assert-True ($null -ne (Get-Command Get-S149StableFileSnapshot -ErrorAction SilentlyContinue)) `
    'the stager must expose a stable atomic marker snapshot helper'
$atomicMarkerPath = Join-Path $PSScriptRoot ('.s149-marker-' + [IO.Path]::GetRandomFileName() + '.txt')
try {
    [IO.File]::WriteAllBytes($atomicMarkerPath,[Text.Encoding]::UTF8.GetBytes('abc'))
    $atomicMarker = Get-S149StableFileSnapshot -Path $atomicMarkerPath -MaxBytes 100
    Assert-True ($atomicMarker.Valid -and $atomicMarker.Exists -and $atomicMarker.Text -ceq 'abc' -and
        $atomicMarker.Sha256 -eq 'BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD' -and
        $atomicMarker.Bytes.Length -eq 3) `
        'one stable handle must return the exact marker bytes/text/hash/mtime snapshot'

    $writer = [IO.File]::Open($atomicMarkerPath,[IO.FileMode]::Open,
        [IO.FileAccess]::ReadWrite,[IO.FileShare]::ReadWrite)
    try {
        $overlap = Get-S149StableFileSnapshot -Path $atomicMarkerPath -MaxBytes 100
        Assert-True (-not $overlap.Valid -and $overlap.Reason -eq 'SNAPSHOT_BUSY') `
            'an overlapping writer must keep the marker snapshot transient rather than admit mixed evidence'
    } finally { $writer.Dispose() }
} finally {
    if (Test-Path -LiteralPath $atomicMarkerPath) { Remove-Item -LiteralPath $atomicMarkerPath -Force }
}

# Break caught: SP/bind/S148 gates must return and parse this exact accepted
# snapshot, rather than reopening the mutable marker path after validation.
$beforeHash = 'A' * 64
$afterHash = 'B' * 64
$mapTicks = ([datetime]'2026-08-26T05:04:10Z').Ticks
$currentTicks = ([datetime]'2026-08-26T05:04:11Z').Ticks
$currentBytes = [Text.Encoding]::UTF8.GetBytes('exact-current-generation')
$currentSnapshot = [pscustomobject]@{
    Valid=$true; Reason='STABLE'; Exists=$true; Bytes=$currentBytes
    Text='exact-current-generation'; Sha256=$afterHash
    LastWriteUtcTicks=$currentTicks; Length=$currentBytes.Length
}
$changedGeneration = Get-S149MarkerGenerationResult `
    -BeforeExists $true -BeforeSha256 $beforeHash -CurrentSnapshot $currentSnapshot `
    -MapNotBeforeUtcTicks $mapTicks -GameStartUtcTicks $gameStartUtc.Ticks `
    -NowUtcTicks ([datetime]'2026-08-26T05:04:12Z').Ticks
Assert-True ($changedGeneration.Valid -and $changedGeneration.Text -ceq 'exact-current-generation' -and
    $changedGeneration.Sha256 -eq $afterHash -and $changedGeneration.Bytes.Length -eq $currentBytes.Length) `
    'generation admission must return the exact already-validated bytes/text/hash for parsing and archival'
$sameSnapshot = [pscustomobject]@{
    Valid=$true; Reason='STABLE'; Exists=$true; Bytes=$currentBytes
    Text='exact-current-generation'; Sha256=$beforeHash
    LastWriteUtcTicks=$currentTicks; Length=$currentBytes.Length
}
$staleGeneration = Get-S149MarkerGenerationResult `
    -BeforeExists $true -BeforeSha256 $beforeHash -CurrentSnapshot $sameSnapshot `
    -MapNotBeforeUtcTicks $mapTicks -GameStartUtcTicks $gameStartUtc.Ticks `
    -NowUtcTicks ([datetime]'2026-08-26T05:04:12Z').Ticks
Assert-True (-not $staleGeneration.Valid -and $staleGeneration.Reason -eq 'MARKER_CONTENT_UNCHANGED') `
    'preexisting complete marker content must never satisfy a post-map gate'

$s148Terminal = @'
[S148] PREFLIGHT_REFUSED RESULT=PREFLIGHT_REFUSED issues=0x00000001; no Health write and no AdjustHealth call
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=10 of 10 swapped (scan 1 ms, 10 UFunctions live)
[BF] worker done (hits=1 hitsGT=1)
'@
$staleS148 = Get-S148TerminalGateResult -Text $s148Terminal -HostGenerationValid $false
Assert-True (-not $staleS148.Complete -and $staleS148.Reason -eq 'HOST_GENERATION') `
    'the frozen S148 parser must require host evidence tying this marker generation to its exact map/current game'

# Break caught: the canonical same-PID/start ledger must be checked before the
# first map, and crossing CreateNew must set terminal-attempt state even if a
# later write/flush/callback operation throws.
$ledgerAdmission = Get-S149LedgerAdmissionResult -LedgerExists $false
Assert-True $ledgerAdmission.Valid 'an absent canonical ledger may enter staging'
$existingLedgerAdmission = Get-S149LedgerAdmissionResult -LedgerExists $true
Assert-True (-not $existingLedgerAdmission.Valid -and $existingLedgerAdmission.Reason -eq 'LEDGER_ALREADY_EXISTS') `
    'an existing same-PID/start ledger must refuse before any map'

$throwingLedgerPath = Join-Path $PSScriptRoot ('.s149-ledger-boundary-' + [IO.Path]::GetRandomFileName() + '.json')
$script:attemptBoundaryCrossed = $false
$threwAfterCreate = $false
try {
    try {
        [void](New-S149AttemptLedger -Path $throwingLedgerPath -GamePid 4242 `
            -StartTicks 638602272000000000 `
            -S148Sha256 'C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E' `
            -OnCreateNew { $script:attemptBoundaryCrossed = $true; throw 'simulated post-CreateNew failure' })
    } catch {
        $threwAfterCreate = $_.Exception.Message.Contains('simulated post-CreateNew failure')
    }
    Assert-True ($threwAfterCreate -and $script:attemptBoundaryCrossed -and
        (Test-Path -LiteralPath $throwingLedgerPath)) `
        'CreateNew must durably forbid retry and publish attempted state before any later ledger operation'
} finally {
    if (Test-Path -LiteralPath $throwingLedgerPath) {
        Remove-Item -LiteralPath $throwingLedgerPath -Force
    }
}

# Break caught: final artifact hashes must be computed from read handles that
# deny write/delete replacement and stay open across the child mmap operation.
$lockedArtifactPath = Join-Path $PSScriptRoot ('.s149-artifact-' + [IO.Path]::GetRandomFileName() + '.bin')
$replacementPath = Join-Path $PSScriptRoot ('.s149-replacement-' + [IO.Path]::GetRandomFileName() + '.bin')
try {
    [IO.File]::WriteAllBytes($lockedArtifactPath,[Text.Encoding]::ASCII.GetBytes('abc'))
    [IO.File]::WriteAllBytes($replacementPath,[Text.Encoding]::ASCII.GetBytes('replacement'))
    $lockedArtifact = Open-S149LockedArtifact -Path $lockedArtifactPath
    try {
        Assert-True ($lockedArtifact.Sha256 -eq
            'BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD') `
            'the final artifact pin must be the exact hash computed from the held read stream'

        $writeBlocked=$false
        try {
            $writeAttempt=[IO.File]::Open($lockedArtifactPath,[IO.FileMode]::Open,
                [IO.FileAccess]::Write,[IO.FileShare]::ReadWrite)
            $writeAttempt.Dispose()
        } catch [IO.IOException] { $writeBlocked=$true }
        Assert-True $writeBlocked 'the held artifact stream must deny write replacement'

        $renameBlocked=$false
        try {
            Move-Item -LiteralPath $replacementPath -Destination $lockedArtifactPath -Force -ErrorAction Stop
        } catch [IO.IOException] { $renameBlocked=$true }
        Assert-True $renameBlocked 'the held artifact stream must deny delete/rename replacement'

        $secondReader=[IO.File]::Open($lockedArtifactPath,[IO.FileMode]::Open,
            [IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
        $secondReader.Dispose()
    } finally { $lockedArtifact.Stream.Dispose() }
} finally {
    if (Test-Path -LiteralPath $lockedArtifactPath) { Remove-Item -LiteralPath $lockedArtifactPath -Force }
    if (Test-Path -LiteralPath $replacementPath) { Remove-Item -LiteralPath $replacementPath -Force }
}

Write-Host 'PASS s149_stager_safety_test'
