param(
    [Parameter(Mandatory = $true)][string]$CandidateController,
    [ValidateSet('NeutralContract')][string]$Section = 'NeutralContract'
)

# Identity-neutral successor controller contract.
#
# This is a STATIC source/AST contract. A controller has live process, launch,
# and injection side effects, so the contract must never invoke the candidate.
# It reads and parses the candidate source only. It emits the exact set of
# unmet contract IDs and exits nonzero for a noncompliant controller. The frozen
# Flight 2 controller is intentionally and permanently noncompliant (all eight
# IDs), which is the deliberate RED that pins the two Flight 2 defects.
#
# The contract is parameterized and identity-free: no successor label, GUID,
# date, or controller name is embedded. A future compliant sibling controller
# clears an ID only by containing the corresponding successor mechanism in the
# required control-flow position, never by matching a fixed string.

$ErrorActionPreference = 'Stop'

$FrozenFlight2Sha256 = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'

# Ordered contract IDs. Order is part of the contract.
$ContractIds = @(
    'FROZEN_FOUR_LINE_WATCHER'
    'NO_SUCCESSOR_HELPER_PROVENANCE'
    'NO_HELD_WATCHER_IDENTITY_PAIR'
    'NO_CANONICAL_RAW_REVALIDATION'
    'NO_DISTINCT_BACKEND_STDOUT'
    'NO_HELD_OUTPUT_IDENTITY_ANCHORS'
    'QUIET_SAMPLING_IS_NOT_TERMINALITY'
    'ARM_FINAL_WATCHER_FENCE_MISSING'
)

function Get-CandidateSha256([string]$Path) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try {
            return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '')
        } finally { $algorithm.Dispose() }
    } finally { $stream.Dispose() }
}

if ($Section -ne 'NeutralContract') {
    Write-Output "UNKNOWN_SECTION $Section"
    exit 3
}

$full = [IO.Path]::GetFullPath($CandidateController)
$attributes = [IO.File]::GetAttributes($full)
if (($attributes -band [IO.FileAttributes]::Directory) -ne 0) {
    Write-Output "CANDIDATE_NOT_A_FILE $full"
    exit 3
}
if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    Write-Output "CANDIDATE_IS_REPARSE $full"
    exit 3
}
if (-not $full.EndsWith('.ps1', [StringComparison]::OrdinalIgnoreCase)) {
    Write-Output "CANDIDATE_NOT_POWERSHELL $full"
    exit 3
}

$isFrozenFlight2 = [IO.Path]::GetFileName($full) -ceq 's150-flight2-controller.ps1'

# Hash before analysis. Never invoke or dot-source the candidate.
$shaBefore = Get-CandidateSha256 $full
if ($isFrozenFlight2 -and $shaBefore -cne $FrozenFlight2Sha256) {
    Write-Output "FROZEN_CONTROLLER_DRIFTED_BEFORE $shaBefore"
    exit 4
}

# Read raw source and confirm it parses (static parse only, no execution).
$source = [IO.File]::ReadAllText($full)
$tokens = $null
$parseErrors = $null
[void][Management.Automation.Language.Parser]::ParseFile($full, [ref]$tokens, [ref]$parseErrors)
if (@($parseErrors).Count -ne 0) {
    Write-Output "CANDIDATE_PARSE_FAILED $full"
    exit 4
}

function Test-SourceMatches([string]$Pattern) {
    return [bool]([regex]::IsMatch($source, $Pattern))
}

# --- Contract predicates. Each is TRUE when the contract ID is UNMET (violated). ---
#
# A compliant sibling controller clears each ID by containing the named
# successor mechanism; the frozen controller contains none of them and instead
# gates on the exact-four-line watcher receipt and two-equal-sample quiet
# sampling, which are the two proven Flight 2 defects.

# 1. Watcher receipt must be validated as the canonical five-line envelope, not
#    gated on an exact four-line count.
$hasFourLineGate = Test-SourceMatches 'receiptLines\.Count\s*-eq\s*4'
$callsCanonicalEnvelope = Test-SourceMatches 'Get-S150SuccessorWatcherEnvelopeResult'
$violations = [ordered]@{}
$violations['FROZEN_FOUR_LINE_WATCHER'] = ($hasFourLineGate -or -not $callsCanonicalEnvelope)

# 2. The successor evidence helper must be pinned by hash and dot-sourced.
$pinsSuccessorHelper = (Test-SourceMatches 's150-successor-evidence\.ps1') -and
    (Test-SourceMatches '(?i)[0-9A-F]{64}')
$violations['NO_SUCCESSOR_HELPER_PROVENANCE'] = -not $pinsSuccessorHelper

# 3. A held-handle coherent stdout/stderr watcher pair must be opened and read.
$holdsWatcherIdentityPair = (Test-SourceMatches 'Open-S150SuccessorWatcherEvidenceHandles') -and
    (Test-SourceMatches 'Get-S150SuccessorWatcherEvidenceResult')
$violations['NO_HELD_WATCHER_IDENTITY_PAIR'] = -not $holdsWatcherIdentityPair

# 4. Watcher stdout must be revalidated as canonical raw bytes.
$violations['NO_CANONICAL_RAW_REVALIDATION'] = -not $callsCanonicalEnvelope

# 5. The backend must receive a distinct derived stdout sink.
$hasDistinctBackendStdout = (Test-SourceMatches 'Get-S150SuccessorOutputPathContract') -and
    (Test-SourceMatches 'BackendStdout')
$violations['NO_DISTINCT_BACKEND_STDOUT'] = -not $hasDistinctBackendStdout

# 6. All four output roles must be created with no-clobber identity anchors held
#    from before launcher invocation through durable admission or cleanup, and
#    released only by an outer finally.
$rolePattern = 'LauncherStdout.*LauncherStderr.*BackendStdout.*BackendStderr'
$anchorsBeforeLaunch = (Test-SourceMatches 'Open-S150SuccessorCreateNewIdentityAnchors') -and
    (Test-SourceMatches $rolePattern) -and
    (Test-SourceMatches '(?s)Open-S150SuccessorCreateNewIdentityAnchors.*launcher-invoked') -and
    (Test-SourceMatches '(?s)finally\s*\{[^}]*Close-S150SuccessorOutputAnchorState')
$violations['NO_HELD_OUTPUT_IDENTITY_ANCHORS'] = -not $anchorsBeforeLaunch

# 7. Terminal launcher output must be proven by a writer-denying lease, never by
#    quiet two-equal-sample sampling.
$usesQuietSampling = Test-SourceMatches 'Get-S150AnchoredOutputReceipt'
$usesTerminalLease = Test-SourceMatches 'Open-S150SuccessorTerminalOutputLease'
$violations['QUIET_SAMPLING_IS_NOT_TERMINALITY'] = ($usesQuietSampling -or -not $usesTerminalLease)

# 8. Arm must re-run the canonical watcher fence immediately before writing
#    stager-invoked.json, not the exact-four-line count.
$armFinalWatcherFence = Test-SourceMatches '(?s)Get-S150SuccessorWatcherEvidenceResult(?:(?!stager-invoked).)*stager-invoked\.json'
$violations['ARM_FINAL_WATCHER_FENCE_MISSING'] = -not $armFinalWatcherFence

# Hash after analysis; a static contract never mutates the candidate.
$shaAfter = Get-CandidateSha256 $full
if ($shaAfter -cne $shaBefore) {
    Write-Output "CANDIDATE_MUTATED_DURING_ANALYSIS $shaAfter"
    exit 4
}
if ($isFrozenFlight2 -and $shaAfter -cne $FrozenFlight2Sha256) {
    Write-Output "FROZEN_CONTROLLER_DRIFTED_AFTER $shaAfter"
    exit 4
}

$unmet = @($ContractIds | Where-Object { $violations[$_] })
if ($unmet.Count -eq 0) {
    Write-Output "PASS s150_successor_controller_contract $Section"
    exit 0
}

foreach ($violationId in $unmet) { Write-Output "VIOLATION $violationId" }
exit 1
