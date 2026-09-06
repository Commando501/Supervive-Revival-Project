param(
    [string]$OutDir = (Join-Path $PSScriptRoot '..\build\s149-bind-contract-test'),
    [string]$ArtifactPath,
    [string]$ExpectedArtifactSha256
)

$ErrorActionPreference = 'Stop'
$shimRoot = Split-Path -Parent $PSScriptRoot
$build = Join-Path $shimRoot 'build.ps1'

function Assert-S149BindArtifactContract {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "S149 bind artifact missing: $Path"
    }
    $ascii = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($Path))
    $required = @(
        '[S149] BIND_ONLY pid=',
        'arms=0x02 forbidden=0xFD naturalInput=0 selfCal=0 ownerMode=0',
        '[S149] ---- K_BIND ONLY: WireAbilitySystem + exactly one InitAbilityActorInfo',
        '[S149] CALL_ISSUED pid=',
        'callCount=1 asc=0x%llX owner=0x%llX avatar=0x%llX persistentSetup=yes',
        '[BF] InitAbilityActorInfo returned',
        '[S149] POST_BIND pid=',
        'callCount=%u setupFaulted=%u initFaulted=%u terminalRevalidated=%u',
        'localAuthorityStable=%u',
        'pcLive=%u possessedHeroStable=%u',
        'ascStorageResolved=%u ascStorageReadable=%u ascStable=%u',
        'avatarPropertyResolved=%u avatarSlotReadable=%u',
        'avatarLive=%u avatarMatchesHero=%u',
        '[S149] POST_BIND_OWNER pid=',
        'ownerPropertyResolved=%u ownerSlotReadable=%u',
        'ownerLive=%u ownerMatchesCarrier=%u carrierPropertyResolved=%u',
        'carrierSlotReadable=%u carrierLive=%u carrierStable=%u',
        'carrierAscPropertyResolved=%u carrierAscSlotReadable=%u carrierAscStable=%u',
        '[S149] funcswap drain complete',
        '[FS] disarm: restored=',
        '[S149] CLEANUP restoreCountExact=%u repairScanComplete=%u verifyScanComplete=%u callbacksSealed=%u cleanupFaulted=%u',
        'postRestoreQuiesced=%u swapped=%lu restored=%lu residualRepaired=%lu',
        'residualRemaining=%lu postRestoreEntries=%lu entryPendingRemaining=%lu',
        'parkedRemaining=%lu activeRemaining=%lu mutationRootsRemaining=%lu',
        '[S149] callbacks SEALED; delayed prefetched thunk roots are no-dispatch',
        '[S149] terminal witness collected after sealed callback drain',
        '[S149] RESULT pid=',
        'outcome=%s issues=0x%08X',
        'funcsRestoreVerified=%s postRestoreQuiesced=%s',
        'residualRemaining=%lu postRestoreEntries=%lu',
        '[S149] setup SEH fault contained;',
        '[BF] worker done',
        'BIND_READY',
        'BIND_REFUSED'
    )
    foreach ($needle in $required) {
        if (-not $ascii.Contains($needle)) {
            throw "S149 bind artifact is missing required behavior: $needle"
        }
    }

    $forbidden = @(
        '[BF] ---- K_SPAWN:',
        '[BF] ---- K_GRANT',
        '[BF] ---- K_ACTIVATE:',
        '[BF] ---- K_WIREBOT:',
        '[BF] ---- K_DAMAGE:',
        '[BF] ---- K_ALIVE',
        '[BF] ---- K_GASATTR',
        '[S147]',
        '[S148]',
        'READY FOR INPUT',
        'SELF_DAMAGE_CALIBRATED'
    )
    foreach ($needle in $forbidden) {
        if ($ascii.Contains($needle)) {
            throw "S149 bind artifact unexpectedly contains forbidden behavior: $needle"
        }
    }
}

$artifactOnly = -not [string]::IsNullOrWhiteSpace($ArtifactPath)
if ($artifactOnly) {
    $dll = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ArtifactPath)
    if ([string]::IsNullOrWhiteSpace($ExpectedArtifactSha256) -or
        $ExpectedArtifactSha256 -notmatch '^[0-9A-Fa-f]{64}$') {
        throw 'artifact-only S149 validation requires -ExpectedArtifactSha256 with exactly 64 hex characters'
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $dll).Hash
    if ($actual -ne $ExpectedArtifactSha256.ToUpperInvariant()) {
        throw "S149 bind artifact SHA-256 mismatch: expected=$($ExpectedArtifactSha256.ToUpperInvariant()) actual=$actual path=$dll"
    }
} else {
    & $build -Name tutorial_launch -Variant botfight-bind-only -OutDir $OutDir -Toolchain clang
    if ($LASTEXITCODE -ne 0) {
        throw "S149 bind-only build failed with exit code $LASTEXITCODE"
    }
    $dll = Join-Path $OutDir 'tutorial_launch_botfight_bind_only.dll'
}

Assert-S149BindArtifactContract $dll

if (-not $artifactOnly) {
    $legacyOut = Join-Path $OutDir 'legacy-negative'
    & $build -Name tutorial_launch -Variant botfight-probe -OutDir $legacyOut -Toolchain clang
    if ($LASTEXITCODE -ne 0) {
        throw "legacy negative-control build failed with exit code $LASTEXITCODE"
    }
    $legacy = Join-Path $legacyOut 'tutorial_launch_botfight_probe.dll'
    $legacyRejected = $false
    try {
        Assert-S149BindArtifactContract $legacy
    } catch {
        if ($_.Exception.Message -notlike 'S149 bind artifact is missing required behavior:*' -and
            $_.Exception.Message -notlike 'S149 bind artifact unexpectedly contains forbidden behavior:*') {
            throw
        }
        $legacyRejected = $true
    }
    if (-not $legacyRejected) {
        throw 'legacy spawn+bind artifact unexpectedly passed the bind-only artifact contract'
    }

    $s148 = Join-Path $shimRoot `
        'build\s148-flight4-a\tutorial_launch_botfight_damage_self_cal.dll'
    $s148Expected = 'C7204964B896E376B3E0FBFBBFCD7ACC7146FFBE9D0BF320ADDDE5DF0D78421E'
    if (-not (Test-Path -LiteralPath $s148)) {
        throw "frozen S148 Flight4 negative fixture missing: $s148"
    }
    $s148Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $s148).Hash
    if ($s148Actual -ne $s148Expected) {
        throw "frozen S148 Flight4 fixture SHA-256 mismatch: expected=$s148Expected actual=$s148Actual"
    }
    $s148Rejected = $false
    try {
        Assert-S149BindArtifactContract $s148
    } catch {
        if ($_.Exception.Message -notlike 'S149 bind artifact is missing required behavior:*' -and
            $_.Exception.Message -notlike 'S149 bind artifact unexpectedly contains forbidden behavior:*') {
            throw
        }
        $s148Rejected = $true
    }
    if (-not $s148Rejected) {
        throw 'frozen unchanged S148 artifact unexpectedly passed the bind-only artifact contract'
    }
}

Write-Host 'PASS s149_bind_contract_test'
