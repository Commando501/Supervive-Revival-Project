# S150 successor-neutral boundaries — v2 remediation (audit-tooling correction)

Status: OFFLINE remediation plan. Supersedes the verification tooling of
`docs/superpowers/plans/2026-08-30-s150-successor-neutral-boundaries.md` (v1) **only** in the
offline-audit identity scan and two Minor verification defects. It authorizes **no** identity
binding, production launch, `RecoverLaunch`, `Arm`, staging, injection, or any live action.

## 0. Why v2 exists

The v1 plan was executed through Task 6 Step 6 with every gate GREEN (helper, tests, byte-exact
launcher edit, backend A/B `115D0999…`, all seven DLL RAW/VSIZE digests, inventory). It then reached
a **preserved NO-GO** at Task 6 Step 7 because the v1 offline-audit identity-literal scan is
**internally contradictory** with the v1 LauncherSource gate:

- The v1 audit scans the **whole** `configs/launch-redirect.ps1` and allows only the two S150 flight
  dates. But `launch-redirect.ps1` is a large existing operational script whose **unmodified**
  content carries pre-existing, non-successor dated comments — `2026-06-29`, `2026-08-04`,
  `2026-08-05`, `2026-08-14` (lines 564/650/85/70). These dates are present verbatim in the immutable
  pre-edit launcher (`A07631BB…`) recorded in the v1 historical baseline, so they are **not**
  introduced by the S150 edit.
- The v1 LauncherSource gate requires the launcher to equal *pre-edit bytes + exactly the reviewed
  three-region replacement map* — i.e. it **requires those dated comments be retained**.

So the exact launcher that must pass LauncherSource necessarily fails the v1 audit. Resolving it
requires editing the frozen v1 plan or the launcher outside the authorized three-region map — both
prohibited — hence the NO-GO. The v1 artifacts are preserved unchanged as evidence.

## 1. What v2 corrects (verification tooling only — no source, build input, or substrate changes)

1. **Launcher identity scan → introduced-only.** The successor-neutrality question is only *"did the
   S150 edit introduce a new identity?"* For the launcher, v2 flags a literal (or forbidden path) only
   if it is present in the **current** launcher and **absent** from the pinned **pre-edit** launcher
   (`$decodedPreEditLauncher`, the immutable baseline snapshot already validated earlier in the audit).
   The six new sources are still scanned in full.
2. **Allow-list extended by the one legitimate historical date the new sources carry.** The watcher
   test reconstructs a genuine historical **S149** 348-byte watcher receipt, asserted against a pinned
   SHA (`750F7AC1…`) and an exact 348-byte length; its embedded path
   `crash-s149-bind-flight1-20260826-0305` contains the S149 flight date `20260826`. That is a real
   historical (non-successor) reference, so `20260826`/`2026-08-26` are added to
   `$allowedIdentityLiterals`. **No source byte changes** (editing the test would break its pinned
   historical-receipt SHA).
3. **Minor — Step 3 failing-package parse.** The v1 `^FAIL\s+(\S+)\s` regex is eaten by the standard
   bare-`FAIL` summary line that precedes `FAIL<TAB>pkg`; v2 parses the package with a tab split.
4. **Minor — audit git calls.** On this machine `core.autocrlf=true` and `core.safecrlf` is unset, so
   git emits an `LF will be replaced by CRLF` advisory that PS 5.1 turns into a terminating
   `NativeCommandError` under `2>&1 + EAP=Stop`. v2 runs the audit's two `git diff --check` commands
   with `-c core.safecrlf=false` (autocrlf still true, so the launcher check stays exit 0 / no
   whitespace defect). This suppresses only the advisory; the whitespace-check semantics are unchanged.

Nothing else in v1 changes. In particular the design
(`docs/superpowers/specs/2026-08-29-s150-successor-watcher-output-ownership-design.md`), the helper,
the six new sources, the launcher edit, and every v1 build output are unchanged.

## 2. Corrected scan — validated, with negative controls

The introduced-only launcher scan plus the extended allow-list was validated against the real files
before this plan was written:

- **Real state → 0 violations.** New sources: 0. Launcher: pre-edit literal set `{2026-06-29,
  2026-08-04, 2026-08-05, 2026-08-14}` equals the current literal set (the edit introduced none), so
  the introduced set is **empty**.
- **Negative controls all caught** (a genuinely new identity is not silently accepted): injecting a new
  flight label `s150captureflight3-20270115-101010`, a new GUID `11112222-…-666677778888`, a new
  non-historical date `2027-03-09`, or a new-source GUID `99998888-…` each produced exactly one flagged
  introduced/non-allowed literal.

## 3. Inputs, reuse, and fresh v2 paths

**Frozen read-only inputs (unchanged; hashes must hold before the audit runs):**

| input | SHA-256 |
|---|---|
| v1 plan `docs/superpowers/plans/2026-08-30-s150-successor-neutral-boundaries.md` | `8B886E59…` |
| design `…/specs/2026-08-29-s150-successor-watcher-output-ownership-design.md` | `07C0CF46…` |
| v1 historical baseline `docs/s150-successor-historical-baseline.json` | `BC4C2E19…` |
| v1 baseline receipt `docs/s150-successor-historical-baseline.receipt.json` | `57668C75…` |
| Flight 2 controller `.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller.ps1` | `BA6DE0EC…` |
| Flight 2 controller test `…/s150-flight2-controller-test.ps1` | `BE7E6BF6…` |
| S149 helper `configs/s149-bind-gate.ps1`, capture helper `configs/s150-capture-generation.ps1` (`50EE8181…`), `tools/usmapdump/usmapdump.exe` | per v1 baseline |

The **v1 historical baseline is the immutable substrate** for v2. It is the only surviving record of
the pre-edit launcher (`A07631BB…`); the working launcher is the edited `8B01999B…`, so a fresh
baseline cannot recapture the pre-edit state. The v2 audit reads the pre-edit launcher and every
substrate pin from the v1 baseline and re-asserts they have not drifted.

**Reused build outputs (byte-verified in the v1 run; re-hashed as v2 evidence, not regenerated):**
the pretest process census + receipt, `offline-build-inventory.json`, backend A/B (`ags.exe`,
`115D0999…`), the seven DLLs (S149 RAW `f7765063…`/VSIZE `eb405ecd…`; S148 RAW `c46fb598…`/VSIZE
`91cbea32…`; natural `366e8ef0…`; botai `5e47c13c…`; play `9bc10a45…`), and the three behavior exes —
all at their v1 paths under `tools/sigbypass-mod/build/s150-successor-neutral-*` and
`server/build/s150-successor-neutral-backend-*`. No source or build input changed, so these are
byte-identical to a fresh build; the v2 audit re-validates them in place.

**Fresh v2 output paths (must be absent before their gate; never reuse a v1 path):**

- `docs/s150-successor-neutral-offline-audit-v2.json` (audit, schema `s150-successor-neutral-offline-audit/v2`)
- `docs/s150-successor-neutral-evidence-v2.md`
- `docs/s150-successor-neutral-implementation-review-v2.md`
- `docs/s150-successor-neutral-evidence-review-v2.md`

## 4. The corrected offline-audit block

This is the v1 Task 6 Step 7 audit block with exactly the four changes in §1 (introduced-only launcher
identity + forbidden-path scan, `20260826`/`2026-08-26` added to `$allowedIdentityLiterals`,
`-c core.safecrlf=false` on both `git diff --check` calls, and the v2 audit output path + `/v2`
schema). Its default `Preview` mode writes nothing; `CreateNew` writes the durable v2 audit once;
`ValidateExisting` re-derives and byte-compares without writing.

```powershell
$ErrorActionPreference = 'Stop'
if (-not (Get-Variable -Name S150OfflineAuditMode -Scope Script -ErrorAction SilentlyContinue)) {
  $script:S150OfflineAuditMode = 'Preview'
}
if ($script:S150OfflineAuditMode -cnotin @('Preview','CreateNew','ValidateExisting')) {
  throw "Invalid S150 offline-audit mode: $script:S150OfflineAuditMode"
}
$repoRoot = (Resolve-Path '.').Path
$captureHelper = [IO.Path]::GetFullPath('configs\s150-capture-generation.ps1')
$rootAttributes = [IO.File]::GetAttributes($repoRoot)
if (($rootAttributes -band [IO.FileAttributes]::Directory) -eq 0 -or
    ($rootAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
  throw 'Offline-audit worktree root is not ordinary.'
}
foreach ($preloadPath in @([IO.Path]::GetFullPath('configs'),$captureHelper)) {
  if (([IO.File]::GetAttributes($preloadPath) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Offline-audit preload path is reparse: $preloadPath"
  }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash -cne
    '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866') {
  throw 'Offline-audit S150 helper provenance mismatch.'
}
. $captureHelper

function Get-S150AuditFileRecord {
  param([Parameter(Mandatory=$true)][string]$Path)
  $full = [IO.Path]::GetFullPath($Path)
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $full
  if (-not $state.Exists) { throw "Audit file is absent: $full" }
  $stream = [IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item.PSIsContainer) { throw "Audit expected a file: $full" }
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $sha256 = ([BitConverter]::ToString($hashAlgorithm.ComputeHash($stream))).Replace('-', '')
    } finally { $hashAlgorithm.Dispose() }
    [ordered]@{
      path = $full
      size = [int64]$item.Length
      sha256 = $sha256
      creationUtcTicks = [int64]$item.CreationTimeUtc.Ticks
      lastWriteUtcTicks = [int64]$item.LastWriteTimeUtc.Ticks
      attributes = [string]$item.Attributes
    }
  } finally { $stream.Dispose() }
}

function Get-S150AuditTextRecord {
  param([Parameter(Mandatory=$true)][string]$Path)
  $full = [IO.Path]::GetFullPath($Path)
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $full
  if (-not $state.Exists) { throw "Audit text record is absent: $full" }
  $stream = [IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item.PSIsContainer) { throw "Audit text record expected a file: $full" }
    $memory = [IO.MemoryStream]::new()
    try {
      $stream.CopyTo($memory)
      $bytes = $memory.ToArray()
    } finally { $memory.Dispose() }
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $sha256 = ([BitConverter]::ToString($hashAlgorithm.ComputeHash([byte[]]$bytes))).Replace('-', '')
    } finally { $hashAlgorithm.Dispose() }
    [pscustomobject]@{
      Text = [Text.UTF8Encoding]::new($false,$true).GetString($bytes)
      Record = [ordered]@{
        path = $full
        size = [int64]$item.Length
        sha256 = $sha256
        creationUtcTicks = [int64]$item.CreationTimeUtc.Ticks
        lastWriteUtcTicks = [int64]$item.LastWriteTimeUtc.Ticks
        attributes = [string]$item.Attributes
      }
    }
  } finally { $stream.Dispose() }
}

function Assert-S150AuditFileRecord {
  param([Parameter(Mandatory=$true)]$Record,[string]$RelativeBase)
  $path = [string]$Record.path
  if (-not [string]::IsNullOrWhiteSpace($RelativeBase)) { $path = Join-Path $RelativeBase $path }
  $actual = Get-S150AuditFileRecord -Path $path
  if ([int64]$actual.size -ne [int64]$Record.size -or
      [string]$actual.sha256 -cne [string]$Record.sha256 -or
      [int64]$actual.creationUtcTicks -ne [int64]$Record.creationUtcTicks -or
      [int64]$actual.lastWriteUtcTicks -ne [int64]$Record.lastWriteUtcTicks -or
      [string]$actual.attributes -cne [string]$Record.attributes) {
    throw "Historical record drifted: $path"
  }
}

$baselinePath = [IO.Path]::GetFullPath('docs\s150-successor-historical-baseline.json')
$baselineReceiptPath = [IO.Path]::GetFullPath('docs\s150-successor-historical-baseline.receipt.json')
$null = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $baselinePath
$null = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $baselineReceiptPath
$baselineReceiptRead = Get-S150AuditTextRecord -Path $baselineReceiptPath
$baselineReceipt = $baselineReceiptRead.Text | ConvertFrom-Json
if ([string]$baselineReceipt.schema -cne 's150-successor-historical-baseline-receipt/v1' -or
    -not [string]::Equals([string]$baselineReceipt.baselinePath,$baselinePath,[StringComparison]::OrdinalIgnoreCase)) {
  throw 'Historical baseline receipt schema/path mismatch.'
}
$baselineRead = Get-S150AuditTextRecord -Path $baselinePath
$baselineHash = [string]$baselineRead.Record.sha256
if ([int64]$baselineRead.Record.size -ne [int64]$baselineReceipt.baselineSize -or
    $baselineHash -cne [string]$baselineReceipt.baselineSha256 -or
    [int64]$baselineRead.Record.creationUtcTicks -ne [int64]$baselineReceipt.baselineCreationUtcTicks -or
    [int64]$baselineRead.Record.lastWriteUtcTicks -ne [int64]$baselineReceipt.baselineLastWriteUtcTicks) {
  throw 'Historical baseline no longer matches its immutable receipt.'
}
$baseline = $baselineRead.Text | ConvertFrom-Json
if ([string]$baseline.schema -cne 's150-successor-historical-baseline/v1' -or
    [string]$baseline.status -cne 'HISTORICAL_EVIDENCE_ONLY' -or
    [string]$baseline.terminalConclusion -cne
      'RECOVERLAUNCH_WATCHER_ADMISSION_REFUSED; BACKEND_AND_GAME_BRIEFLY_LAUNCHED; NO_FRESH_ADMISSION; NO_ARM; NO_STAGER; NO_INJECTION; CLEANUP_STABLE_ZERO; FLIGHT2_TERMINAL_NO_RETRY') {
  throw 'Historical baseline schema/status/conclusion mismatch.'
}
foreach ($record in @($baseline.neutralInputs)) { Assert-S150AuditFileRecord -Record $record }
$launcherPath = [IO.Path]::GetFullPath('configs\launch-redirect.ps1')
$preLauncherRecords = @($baseline.pinnedPreState | Where-Object {
  [string]::Equals([string]$_.path,$launcherPath,[StringComparison]::OrdinalIgnoreCase)
})
if ($preLauncherRecords.Count -ne 1 -or
    [int64]$preLauncherRecords[0].size -ne 37367 -or
    [string]$preLauncherRecords[0].sha256 -cne
      'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D') {
  throw 'Pre-successor launcher record changed inside the baseline.'
}
$preEditLauncherRaw = $baseline.preEditLauncherRaw
try { $decodedPreEditLauncher = [Convert]::FromBase64String([string]$preEditLauncherRaw.base64) }
catch { throw 'Embedded pre-edit launcher Base64 is malformed.' }
$decodedLauncherHashAlgorithm = [Security.Cryptography.SHA256]::Create()
try {
  $decodedLauncherHash = ([BitConverter]::ToString(
    $decodedLauncherHashAlgorithm.ComputeHash([byte[]]$decodedPreEditLauncher))).Replace('-', '')
} finally { $decodedLauncherHashAlgorithm.Dispose() }
$decodedCrlfCount = 0
$decodedLoneLfCount = 0
$decodedLoneCrCount = 0
for ($index = 0; $index -lt $decodedPreEditLauncher.Length; $index++) {
  if ($decodedPreEditLauncher[$index] -eq 13) {
    if ($index + 1 -lt $decodedPreEditLauncher.Length -and $decodedPreEditLauncher[$index + 1] -eq 10) {
      $decodedCrlfCount++
      $index++
    } else { $decodedLoneCrCount++ }
  } elseif ($decodedPreEditLauncher[$index] -eq 10) { $decodedLoneLfCount++ }
}
if ([string]$preEditLauncherRaw.path -cne $launcherPath -or
    [int64]$preEditLauncherRaw.size -ne 37367 -or $decodedPreEditLauncher.Length -ne 37367 -or
    [string]$preEditLauncherRaw.sha256 -cne $decodedLauncherHash -or
    $decodedLauncherHash -cne 'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D' -or
    [string]$preEditLauncherRaw.bomHex -cne 'EF BB BF' -or
    $decodedPreEditLauncher[0] -ne 0xEF -or $decodedPreEditLauncher[1] -ne 0xBB -or
    $decodedPreEditLauncher[2] -ne 0xBF -or
    [int]$preEditLauncherRaw.crlfCount -ne 425 -or $decodedCrlfCount -ne 425 -or
    [int]$preEditLauncherRaw.loneLfCount -ne 222 -or $decodedLoneLfCount -ne 222 -or
    [int]$preEditLauncherRaw.loneCrCount -ne 0 -or $decodedLoneCrCount -ne 0 -or
    [Convert]::ToBase64String($decodedPreEditLauncher) -cne [string]$preEditLauncherRaw.base64) {
  throw 'Embedded pre-edit launcher raw snapshot is not self-consistent.'
}
foreach ($record in @($baseline.pinnedPreState | Where-Object {
    -not [string]::Equals([string]$_.path,$launcherPath,[StringComparison]::OrdinalIgnoreCase)
  })) { Assert-S150AuditFileRecord -Record $record }
foreach ($record in @($baseline.activeState)) { Assert-S150AuditFileRecord -Record $record }

$retirement = [IO.Path]::GetFullPath([string]$baseline.retirement.path)
$retirementState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $retirement
if (-not $retirementState.Exists -or
    ($retirementState.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
  throw 'Frozen retirement root is not an ordinary directory.'
}
$pending = [Collections.Generic.Queue[string]]::new()
$pending.Enqueue($retirement)
$actualRetirementFiles = [Collections.Generic.List[string]]::new()
$directCount = -1
while ($pending.Count -gt 0) {
  $directory = $pending.Dequeue()
  $children = @(Get-ChildItem -LiteralPath $directory -Force)
  if ([string]::Equals($directory,$retirement,[StringComparison]::OrdinalIgnoreCase)) {
    $directCount = $children.Count
  }
  foreach ($child in $children) {
    $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
    if (-not $state.Exists) { throw "Retirement entry disappeared: $($child.FullName)" }
    if ($child.PSIsContainer) { $pending.Enqueue($child.FullName) }
    else { $actualRetirementFiles.Add($child.FullName) }
  }
}
$expectedRetirementRelative = [string[]]@($baseline.retirement.files | ForEach-Object { [string]$_.path })
$actualRetirementRelative = [string[]]@($actualRetirementFiles | ForEach-Object {
  $_.Substring($retirement.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1)
})
[Array]::Sort($expectedRetirementRelative,[StringComparer]::Ordinal)
[Array]::Sort($actualRetirementRelative,[StringComparer]::Ordinal)
if ($directCount -ne [int]$baseline.retirement.directEntryCount -or
    $actualRetirementFiles.Count -ne [int]$baseline.retirement.recursiveFileCount -or
    ($actualRetirementRelative -join "`n") -cne ($expectedRetirementRelative -join "`n")) {
  throw 'Frozen retirement topology changed.'
}
foreach ($record in @($baseline.retirement.files)) {
  Assert-S150AuditFileRecord -Record $record -RelativeBase $retirement
}
$dumpPath = [IO.Path]::GetFullPath([string]$baseline.dump.path)
$dumpState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $dumpPath
if (-not $dumpState.Exists -or [string]$dumpState.Attributes -cne 'Directory' -or
    @(Get-ChildItem -LiteralPath $dumpPath -Force).Count -ne [int]$baseline.dump.entryCount) {
  throw 'Frozen dump topology changed.'
}
foreach ($property in @($baseline.requiredAbsences.PSObject.Properties)) {
  $absencePath = Join-Path $retirement $property.Name
  $absenceState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $absencePath
  if (-not [bool]$property.Value -or $absenceState.Exists -or (Test-Path -LiteralPath $absencePath)) {
    throw "Frozen required absence changed: $($property.Name)"
  }
}
$capturePrevPath = [IO.Path]::GetFullPath('docs\capture.log.prev')
$capturePrevState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $capturePrevPath
if (-not [bool]$baseline.capturePrevAbsent -or $capturePrevState.Exists -or
    (Test-Path -LiteralPath $capturePrevPath)) {
  throw 'Active capture.log.prev absence changed.'
}

$docsBase = [IO.Path]::GetFullPath('docs')
$dumpsBase = [IO.Path]::GetFullPath('dumps')
foreach ($identityBase in @($docsBase,$dumpsBase)) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $identityBase
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Identity-census base is not ordinary before namespace enumeration: $identityBase"
  }
}
$expectedRetirementNamespaces = [string[]]@($baseline.preexistingIdentityNamespaces.retirementDirectories)
$expectedDumpNamespaces = [string[]]@($baseline.preexistingIdentityNamespaces.dumpDirectories)
$actualRetirementNamespaces = [string[]]@(Get-ChildItem -LiteralPath 'docs' -Directory -Force |
  Where-Object { $_.Name -like 's150-retirement-*' } | ForEach-Object Name)
$actualDumpNamespaces = [string[]]@(Get-ChildItem -LiteralPath 'dumps' -Directory -Force |
  Where-Object { $_.Name -like 'crash-s150*' } | ForEach-Object Name)
foreach ($array in @($expectedRetirementNamespaces,$expectedDumpNamespaces,
    $actualRetirementNamespaces,$actualDumpNamespaces)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if (($actualRetirementNamespaces -join "`n") -cne ($expectedRetirementNamespaces -join "`n") -or
    ($actualDumpNamespaces -join "`n") -cne ($expectedDumpNamespaces -join "`n")) {
  throw 'A successor retirement or dump identity namespace appeared.'
}
foreach ($namespacePath in @(
    @($actualRetirementNamespaces | ForEach-Object { Join-Path 'docs' $_ }) +
    @($actualDumpNamespaces | ForEach-Object { Join-Path 'dumps' $_ }))) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath ([IO.Path]::GetFullPath($namespacePath))
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Identity namespace is not ordinary during offline audit: $namespacePath"
  }
}

$docsBase = [IO.Path]::GetFullPath('docs')
$dumpsBase = [IO.Path]::GetFullPath('dumps')
foreach ($identityBase in @($docsBase,$dumpsBase)) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $identityBase
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Identity-census base is not ordinary during offline audit: $identityBase"
  }
}
$runtimeReceiptLeaves = [string[]]@(
  'recoverlaunch-invoked.json','recovery-handoff.json','launcher-invoked.json',
  'launcher-child.json','launcher.stdout.log','launcher.stderr.log',
  'launcher-result.json','launcher-result.receipt.json','launcher-cleanup-result.json',
  'fresh-admission.json','crashwatch.stdout.log','crashwatch.stderr.log',
  'stager-invoked.json','stager-child.json','stager.stdout.log','stager.stderr.log',
  'stager-result.json','stager-result.receipt.json'
)
$runtimeReceiptPaths = [Collections.Generic.List[string]]::new()
$identityLabeledPaths = [Collections.Generic.List[string]]::new()
foreach ($identityBase in @($docsBase,$dumpsBase)) {
  $identityQueue = [Collections.Generic.Queue[string]]::new()
  $identityQueue.Enqueue($identityBase)
  while ($identityQueue.Count -gt 0) {
    $identityDirectory = $identityQueue.Dequeue()
    foreach ($child in @(Get-ChildItem -LiteralPath $identityDirectory -Force)) {
      $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
      if (-not $state.Exists) { throw "Identity-census entry disappeared: $($child.FullName)" }
      $relative = $child.FullName.Substring($repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/')
      if ($relative -match '(?i)s150captureflight') { $identityLabeledPaths.Add($relative) }
      if ($child.PSIsContainer) {
        $identityQueue.Enqueue($child.FullName)
      } elseif ($runtimeReceiptLeaves -ccontains $child.Name) {
        $runtimeReceiptPaths.Add($relative)
      }
    }
  }
}
$ledgerDirectory = [IO.Path]::GetFullPath('docs\s149-ledgers')
$ledgerDirectoryState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $ledgerDirectory
$ledgerJsonPaths = [Collections.Generic.List[string]]::new()
if ($ledgerDirectoryState.Exists) {
  if (($ledgerDirectoryState.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw 'Global ledger path exists but is not an ordinary directory.'
  }
  foreach ($ledger in @(Get-ChildItem -LiteralPath $ledgerDirectory -Filter '*.json' -Force)) {
    $state = Assert-S150NoReparsePath -PinnedBaseDirectory $ledgerDirectory -TargetPath $ledger.FullName
    if (-not $state.Exists) { throw "Ledger entry disappeared during audit census: $($ledger.FullName)" }
    $ledgerJsonPaths.Add($ledger.FullName.Substring(
      $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/'))
  }
}
$identityControlObservedPaths = [Collections.Generic.List[string]]::new()
$identityControlTraversalExclusions = [ordered]@{}
$controlQueue = [Collections.Generic.Queue[string]]::new()
$controlQueue.Enqueue($repoRoot)
while ($controlQueue.Count -gt 0) {
  $controlDirectory = $controlQueue.Dequeue()
  foreach ($child in @(Get-ChildItem -LiteralPath $controlDirectory -Force)) {
    if ($controlDirectory -ceq $repoRoot -and $child.Name -ceq '.git') {
      $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
      if (-not $state.Exists -or
          ($state.Attributes -band [IO.FileAttributes]::Directory) -ne 0 -or
          ($state.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The top-level .git audit exclusion is not an ordinary file.'
      }
      $identityControlTraversalExclusions.gitMetadata = [ordered]@{
        path = '.git'; type = 'File'; attributes = [string]$state.Attributes
      }
      continue
    }
    if ($controlDirectory -ceq $repoRoot -and $child.Name -ceq '.codegraph') {
      $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
      if (-not $state.Exists -or
          ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0 -or
          ($state.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The top-level .codegraph audit exclusion is not an ordinary directory.'
      }
      $codegraphEntries = @(Get-ChildItem -LiteralPath $child.FullName -Force)
      if ($codegraphEntries.Count -ne 1 -or $codegraphEntries[0].Name -cne '.gitignore') {
        throw 'The excluded .codegraph index changed from its exact one-file topology.'
      }
      $codegraphEntryState = Assert-S150NoReparsePath `
        -PinnedBaseDirectory $child.FullName -TargetPath $codegraphEntries[0].FullName
      if (-not $codegraphEntryState.Exists -or $codegraphEntries[0].PSIsContainer -or
          ($codegraphEntryState.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The excluded .codegraph/.gitignore audit entry is not an ordinary file.'
      }
      $identityControlTraversalExclusions.codegraphIndex = [ordered]@{
        path = '.codegraph'; type = 'Directory'; attributes = [string]$state.Attributes
        directEntryNames = @('.gitignore')
      }
      continue
    }
    $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
    if (-not $state.Exists) { throw "Identity-control audit entry disappeared: $($child.FullName)" }
    $relative = $child.FullName.Substring(
      $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/')
    if ($relative -match '(?i)s150' -and $child.Name -match '(?i)(controller|manifest|tracker)') {
      $identityControlObservedPaths.Add($relative)
    }
    if ($child.PSIsContainer) { $controlQueue.Enqueue($child.FullName) }
  }
}
if ($identityControlTraversalExclusions.Count -ne 2) {
  throw 'The exact .git/.codegraph audit exclusions were not both admitted.'
}
$baselineTraversalExclusions = $baseline.preexistingIdentityArtifacts.identityControlTraversalExclusions
if ([string]$baselineTraversalExclusions.gitMetadata.path -cne '.git' -or
    [string]$baselineTraversalExclusions.gitMetadata.type -cne 'File' -or
    [string]$baselineTraversalExclusions.gitMetadata.attributes -cne
      [string]$identityControlTraversalExclusions.gitMetadata.attributes -or
    [string]$baselineTraversalExclusions.codegraphIndex.path -cne '.codegraph' -or
    [string]$baselineTraversalExclusions.codegraphIndex.type -cne 'Directory' -or
    [string]$baselineTraversalExclusions.codegraphIndex.attributes -cne
      [string]$identityControlTraversalExclusions.codegraphIndex.attributes -or
    (@($baselineTraversalExclusions.codegraphIndex.directEntryNames) -join "`n") -cne '.gitignore') {
  throw 'The admitted .git/.codegraph traversal exclusions changed from the baseline.'
}
$neutralControllerContractTestPath =
  'tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1'
$identityControlObservedPathArray = [string[]]@($identityControlObservedPaths)
$identityControlArtifactPathArray = [string[]]@($identityControlObservedPathArray | Where-Object {
  $_ -cne $neutralControllerContractTestPath
})
$expectedHistoricalIdentityControlArtifactPaths = [string[]]@(
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight1-controller-test.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight1-controller.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller-test.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-review-manifest.json',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/task-5-controller-report.md',
  'docs/s150-retirement-s150captureflight1-20260827-164413/prior-watcher-output-manifest.json'
)
$expectedObservedIdentityControlPaths = [string[]]@(
  @($expectedHistoricalIdentityControlArtifactPaths) + @($neutralControllerContractTestPath))
$baselineIdentityControlObservedPaths = [string[]]@(
  $baseline.preexistingIdentityArtifacts.identityControlObservedPaths)
$baselineIdentityControlArtifactPaths = [string[]]@(
  $baseline.preexistingIdentityArtifacts.identityControlArtifactPaths)
foreach ($array in @($identityControlObservedPathArray,$identityControlArtifactPathArray,
    $expectedHistoricalIdentityControlArtifactPaths,$expectedObservedIdentityControlPaths,
    $baselineIdentityControlObservedPaths,$baselineIdentityControlArtifactPaths)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if ([string]$baseline.preexistingIdentityArtifacts.neutralControllerContractTestPath -cne
      $neutralControllerContractTestPath -or
    -not [bool]$baseline.preexistingIdentityArtifacts.neutralControllerContractTestPathWasAbsent -or
    ($baselineIdentityControlObservedPaths -join "`n") -cne
      ($expectedHistoricalIdentityControlArtifactPaths -join "`n") -or
    ($identityControlObservedPathArray -join "`n") -cne
      ($expectedObservedIdentityControlPaths -join "`n") -or
    ($identityControlArtifactPathArray -join "`n") -cne
      ($expectedHistoricalIdentityControlArtifactPaths -join "`n") -or
    ($identityControlArtifactPathArray -join "`n") -cne
      ($baselineIdentityControlArtifactPaths -join "`n")) {
  throw 'The observed or identity-bearing S150 controller/manifest/tracker path census changed.'
}
$runtimeReceiptPathArray = [string[]]@($runtimeReceiptPaths)
$identityLabeledPathArray = [string[]]@($identityLabeledPaths)
$ledgerJsonPathArray = [string[]]@($ledgerJsonPaths)
foreach ($array in @($runtimeReceiptPathArray,$identityLabeledPathArray,$ledgerJsonPathArray)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
$expectedRuntimeReceipts = [string[]]@($baseline.preexistingIdentityArtifacts.runtimeReceiptPaths)
$expectedIdentityLabeledPaths = [string[]]@($baseline.preexistingIdentityArtifacts.identityLabeledPaths)
$expectedLedgerJsonPaths = [string[]]@($baseline.preexistingIdentityArtifacts.ledgerJsonPaths)
foreach ($array in @($expectedRuntimeReceipts,$expectedIdentityLabeledPaths,$expectedLedgerJsonPaths)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if ([bool]$ledgerDirectoryState.Exists -ne [bool]$baseline.preexistingIdentityArtifacts.ledgerDirectoryExists -or
    $ledgerDirectory -cne [string]$baseline.preexistingIdentityArtifacts.ledgerDirectoryPath -or
    ($ledgerJsonPathArray -join "`n") -cne ($expectedLedgerJsonPaths -join "`n") -or
    ($runtimeReceiptPathArray -join "`n") -cne ($expectedRuntimeReceipts -join "`n") -or
    ($identityLabeledPathArray -join "`n") -cne ($expectedIdentityLabeledPaths -join "`n")) {
  throw 'Global ledger, runtime-receipt, or identity-labeled path census changed.'
}
$runtimeRepoRoot = [string]$baseline.runtimeRepoIdentityBoundary.root
$runtimeRepoDocs = [string]$baseline.runtimeRepoIdentityBoundary.docs
$runtimeRepoLedger = [string]$baseline.runtimeRepoIdentityBoundary.ledgerDirectory
if ($runtimeRepoRoot -cne 'G:\git\Supervive Revival Project' -or
    $runtimeRepoDocs -cne 'G:\git\Supervive Revival Project\docs' -or
    $runtimeRepoLedger -cne 'G:\git\Supervive Revival Project\docs\s149-ledgers') {
  throw 'Runtime-repo identity-boundary paths changed inside the baseline.'
}
foreach ($runtimeComponent in @('G:\','G:\git',$runtimeRepoRoot,$runtimeRepoDocs,$runtimeRepoLedger)) {
  $runtimeAttributes = [IO.File]::GetAttributes($runtimeComponent)
  if (($runtimeAttributes -band [IO.FileAttributes]::Directory) -eq 0 -or
      ($runtimeAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Runtime-repo census component is not an ordinary directory: $runtimeComponent"
  }
}
$runtimeRepoLedgerJsonPaths = [Collections.Generic.List[string]]::new()
foreach ($ledger in @(Get-ChildItem -LiteralPath $runtimeRepoLedger -Filter '*.json' -Force)) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $runtimeRepoRoot -TargetPath $ledger.FullName
  if (-not $state.Exists) { throw "Runtime-repo ledger entry disappeared: $($ledger.FullName)" }
  $runtimeRepoLedgerJsonPaths.Add($ledger.FullName.Substring(
    $runtimeRepoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/'))
}
$runtimeRepoEvidencePaths = [Collections.Generic.List[string]]::new()
foreach ($entry in @(Get-ChildItem -LiteralPath $runtimeRepoDocs -Filter 'fk24-stage-s150captureflight*' -Force)) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $runtimeRepoRoot -TargetPath $entry.FullName
  if (-not $state.Exists) { throw "Runtime-repo evidence entry disappeared: $($entry.FullName)" }
  $runtimeRepoEvidencePaths.Add($entry.FullName.Substring(
    $runtimeRepoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/'))
}
$runtimeRepoLedgerJsonPathArray = [string[]]@($runtimeRepoLedgerJsonPaths)
$runtimeRepoEvidencePathArray = [string[]]@($runtimeRepoEvidencePaths)
$expectedRuntimeRepoLedgers = [string[]]@($baseline.runtimeRepoIdentityBoundary.ledgerJsonPaths)
$expectedRuntimeRepoEvidence = [string[]]@($baseline.runtimeRepoIdentityBoundary.s150RuntimeEvidencePaths)
foreach ($array in @($runtimeRepoLedgerJsonPathArray,$runtimeRepoEvidencePathArray,
    $expectedRuntimeRepoLedgers,$expectedRuntimeRepoEvidence)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if (($runtimeRepoLedgerJsonPathArray -join "`n") -cne ($expectedRuntimeRepoLedgers -join "`n") -or
    ($runtimeRepoEvidencePathArray -join "`n") -cne ($expectedRuntimeRepoEvidence -join "`n") -or
    $runtimeRepoLedgerJsonPathArray.Count -ne 0 -or $runtimeRepoEvidencePathArray.Count -ne 0) {
  throw 'Runtime-repo global ledger or S150 runtime-evidence boundary changed.'
}

$newSourcePaths = @(
  'configs\s150-successor-evidence.ps1',
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1',
  'tools\sigbypass-mod\tests\fixtures\s150_output_writer_fixture.cpp',
  'tools\sigbypass-mod\tests\fixtures\s150_output_fake_launcher.ps1'
)
$powerShellPaths = @($newSourcePaths | Where-Object { $_.EndsWith('.ps1',[StringComparison]::OrdinalIgnoreCase) }) +
  @('configs\launch-redirect.ps1')
foreach ($path in $newSourcePaths) {
  $bytes = [IO.File]::ReadAllBytes([IO.Path]::GetFullPath($path))
  if (@($bytes | Where-Object { $_ -gt 127 }).Count -ne 0 -or
      ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)) {
    throw "New source is not ASCII/no-BOM: $path"
  }
  $asciiText = [Text.ASCIIEncoding]::new().GetString($bytes)
  if ([regex]::IsMatch($asciiText,'(?m)[ \t]+(?=\r?$)')) { throw "Trailing whitespace in new source: $path" }
  $noIndexOutput = @(& git -c core.safecrlf=false diff --no-index --check -- NUL $path 2>&1)
  $noIndexExit = [int]$LASTEXITCODE
  if ($noIndexExit -notin @(0,1) -or
      ($noIndexOutput -join "`n") -match 'trailing whitespace|space before tab|new blank line at EOF') {
    throw "Untracked source diff check failed: $path"
  }
}
foreach ($path in $powerShellPaths) {
  $tokens = $null
  $errors = $null
  [void][Management.Automation.Language.Parser]::ParseFile(
    [IO.Path]::GetFullPath($path),[ref]$tokens,[ref]$errors)
  if (@($errors).Count -ne 0) { throw "PowerShell AST parse failed: $path" }
}
$launcherBytes = [IO.File]::ReadAllBytes($launcherPath)
if ($launcherBytes.Length -lt 3 -or $launcherBytes[0] -ne 0xEF -or
    $launcherBytes[1] -ne 0xBB -or $launcherBytes[2] -ne 0xBF) {
  throw 'Launcher UTF-8 BOM was not preserved.'
}
$strictUtf8 = [Text.UTF8Encoding]::new($true,$true)
$launcherText = $strictUtf8.GetString($launcherBytes,3,$launcherBytes.Length - 3)
if (@($launcherText.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count -ne 8) {
  throw 'Launcher non-ASCII code-point census changed.'
}
$identityScanPaths = @($newSourcePaths) + @('configs\launch-redirect.ps1')
$allowedIdentityLiterals = @(
  's150captureflight1-20260827-164413','s150captureflight2-20260829-192619',
  '9135172a-a73b-4cc8-bac2-c9fcbbe93aa1','9135172aa73b4cc8bac2c9fcbbe93aa1',
  '20260827','20260829','2026-08-27','2026-08-29',
  '20260826','2026-08-26'
)
$identityLiteralPattern = '(?i)s150captureflight[0-9]+-[0-9]{8}-[0-9]{6}|' +
  '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|' +
  '(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])|' +
  '(?<![0-9])20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])(?![0-9])|' +
  '(?<![0-9])20[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])(?![0-9])'
$forbiddenConcretePathPatterns = [ordered]@{
  'global-ledger-entry' = '(?i)(?:[a-z]:[\\/]|docs[\\/])s149-ledgers[\\/][^''"`\r\n]+\.json'
  'live-runtime-receipt' = '(?i)(?:[a-z]:[\\/]|(?:docs|dumps)[\\/])[^''"`\r\n]*(?:recoverlaunch-invoked|recovery-handoff|launcher-invoked|launcher-child|launcher-result|launcher-cleanup-result|fresh-admission|stager-invoked|stager-child|stager-result)(?:\.receipt)?\.json'
  'live-runtime-evidence' = '(?i)(?:[a-z]:[\\/]|docs[\\/])fk24-stage-s150captureflight[^''"`\r\n]*'
}
# v2 remediation: the launcher is an existing operational file whose unmodified content
# carries pre-existing, non-successor historical date comments. The successor-neutrality
# question is only "did the S150 edit INTRODUCE a new identity", so the launcher is scanned
# for literals/forbidden-paths that are present now but ABSENT from the pinned pre-edit
# launcher; new sources continue to be scanned in full. The pre-edit launcher is the
# immutable baseline snapshot ($decodedPreEditLauncher) validated earlier in this block.
$preEditLauncherText = $strictUtf8.GetString(
  $decodedPreEditLauncher, 3, $decodedPreEditLauncher.Length - 3)
$preEditLauncherLiterals = @([regex]::Matches($preEditLauncherText,$identityLiteralPattern) |
  ForEach-Object Value | Sort-Object -Unique)
foreach ($path in $identityScanPaths) {
  $full = [IO.Path]::GetFullPath($path)
  $isLauncher = [string]::Equals($full,$launcherPath,[StringComparison]::OrdinalIgnoreCase)
  $bytes = [IO.File]::ReadAllBytes($full)
  $text = if ($isLauncher) {
    $strictUtf8.GetString($bytes,3,$bytes.Length - 3)
  } else {
    [Text.ASCIIEncoding]::new().GetString($bytes)
  }
  $identityLiterals = @([regex]::Matches($text,$identityLiteralPattern) |
    ForEach-Object Value | Sort-Object -Unique)
  if ($isLauncher) {
    $identityLiterals = @($identityLiterals | Where-Object { $_ -cnotin $preEditLauncherLiterals })
  }
  foreach ($literal in $identityLiterals) {
    if ($literal -cnotin $allowedIdentityLiterals) {
      throw "Successor label/GUID-D/GUID-N/date literal detected: $literal in $path"
    }
  }
  foreach ($entry in $forbiddenConcretePathPatterns.GetEnumerator()) {
    $matchesNow = [regex]::IsMatch($text,[string]$entry.Value)
    $introduced = if ($isLauncher) {
      $matchesNow -and -not [regex]::IsMatch($preEditLauncherText,[string]$entry.Value)
    } else { $matchesNow }
    if ($introduced) {
      throw "Concrete $($entry.Key) path detected in identity-neutral source: $path"
    }
  }
}
foreach ($productionPath in @('configs\s150-successor-evidence.ps1','configs\launch-redirect.ps1')) {
  $productionBytes = [IO.File]::ReadAllBytes([IO.Path]::GetFullPath($productionPath))
  $productionText = if ($productionPath -ceq 'configs\launch-redirect.ps1') {
    $strictUtf8.GetString($productionBytes,3,$productionBytes.Length - 3)
  } else { [Text.ASCIIEncoding]::new().GetString($productionBytes) }
  if ([regex]::IsMatch($productionText,
      '(?i)\b(?:FlightLabel|FlightGuidD|FlightGuidN|GenerationD|GenerationN|IntendedLocalDate|ReviewManifestPath|FlightLedgerPath)\b')) {
    throw "Identity/date/manifest/ledger binding detected in neutral production source: $productionPath"
  }
}
$trackedDiffOutput = @(& git -c core.safecrlf=false diff --check -- configs/launch-redirect.ps1 2>&1)
if ($LASTEXITCODE -ne 0) { throw "Tracked launcher diff check failed: $($trackedDiffOutput -join ' | ')" }
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
foreach ($section in @('LauncherLoadIsolation','LauncherSource')) {
  & $ps -NoProfile -ExecutionPolicy Bypass -File `
    'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
    -Section $section -FixtureExe $fixtureExe
  if ($LASTEXITCODE -ne 0) { throw "Final static launcher audit failed: $section" }
}

$pretestCensusPath = [IO.Path]::GetFullPath(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.json')
$pretestReceiptPath = [IO.Path]::GetFullPath(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.receipt.json')
$pretestCensusRead = Get-S150AuditTextRecord -Path $pretestCensusPath
$pretestReceiptRead = Get-S150AuditTextRecord -Path $pretestReceiptPath
$pretestCensusRecord = $pretestCensusRead.Record
$pretestReceiptRecord = $pretestReceiptRead.Record
$pretestCensus = $pretestCensusRead.Text | ConvertFrom-Json
$pretestReceipt = $pretestReceiptRead.Text | ConvertFrom-Json
$protectedProcessNames = @(
  'ags','SUPERVIVE-Win64-Shipping','usmapdump','go','inject','crashpad_handler',
  's150_output_writer_fixture','s147_natural_state_test','s148_damage_calibration_test',
  's149_bind_bootstrap_test'
)
if ([string]$pretestCensus.schema -cne 's150-successor-neutral-pretest-process-census/v1') {
  throw 'Pretest process census schema mismatch.'
}
if ([string]$pretestReceipt.schema -cne 's150-successor-neutral-pretest-process-census-receipt/v1' -or
    -not [string]::Equals([string]$pretestReceipt.censusPath,$pretestCensusPath,
      [StringComparison]::OrdinalIgnoreCase) -or
    [int64]$pretestReceipt.censusSize -ne [int64]$pretestCensusRecord.size -or
    [string]$pretestReceipt.censusSha256 -cne [string]$pretestCensusRecord.sha256 -or
    [int64]$pretestReceipt.censusCreationUtcTicks -ne [int64]$pretestCensusRecord.creationUtcTicks -or
    [int64]$pretestReceipt.censusLastWriteUtcTicks -ne [int64]$pretestCensusRecord.lastWriteUtcTicks) {
  throw 'Pretest process census no longer matches its durable receipt.'
}
$inventoryPath = [IO.Path]::GetFullPath(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\offline-build-inventory.json')
$inventoryRead = Get-S150AuditTextRecord -Path $inventoryPath
$inventory = $inventoryRead.Text | ConvertFrom-Json
$expectedInventoryRoots = @(
  'tools/sigbypass-mod/build/s150-successor-neutral-output-tests',
  'tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests',
  'server/build/s150-successor-neutral-backend-a',
  'server/build/s150-successor-neutral-backend-b',
  'tools/sigbypass-mod/build/s150-successor-neutral-recovery-a',
  'tools/sigbypass-mod/build/s150-successor-neutral-recovery-b',
  'tools/sigbypass-mod/build/s150-successor-neutral-regression-natural',
  'tools/sigbypass-mod/build/s150-successor-neutral-regression-botai',
  'tools/sigbypass-mod/build/s150-successor-neutral-regression-play'
)
$expectedInventoryFiles = @(
  'tools/sigbypass-mod/build/s150-successor-neutral-output-tests/s150_output_writer_fixture.exe',
  'tools/sigbypass-mod/build/s150-successor-neutral-output-tests/pretest-process-census.json',
  'tools/sigbypass-mod/build/s150-successor-neutral-output-tests/pretest-process-census.receipt.json',
  'tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests/s147_natural_state_test.exe',
  'tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests/s148_damage_calibration_test.exe',
  'tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests/s149_bind_bootstrap_test.exe',
  'server/build/s150-successor-neutral-backend-a/ags.exe',
  'server/build/s150-successor-neutral-backend-b/ags.exe',
  'tools/sigbypass-mod/build/s150-successor-neutral-recovery-a/tutorial_launch_botfight_bind_only.dll',
  'tools/sigbypass-mod/build/s150-successor-neutral-recovery-a/tutorial_launch_botfight_damage_self_cal.dll',
  'tools/sigbypass-mod/build/s150-successor-neutral-recovery-b/tutorial_launch_botfight_bind_only.dll',
  'tools/sigbypass-mod/build/s150-successor-neutral-recovery-b/tutorial_launch_botfight_damage_self_cal.dll',
  'tools/sigbypass-mod/build/s150-successor-neutral-regression-natural/tutorial_launch_botfight_castalive_dash_mana10_cdocharge1_naturalinput.dll',
  'tools/sigbypass-mod/build/s150-successor-neutral-regression-botai/tutorial_launch_botai.dll',
  'tools/sigbypass-mod/build/s150-successor-neutral-regression-play/tutorial_launch_play.dll'
)
$actualInventoryRoots = [string[]]@($inventory.roots | ForEach-Object { [string]$_ })
$actualInventoryFiles = [string[]]@($inventory.files | ForEach-Object { [string]$_.path })
$expectedInventoryRootArray = [string[]]@($expectedInventoryRoots)
$expectedInventoryFileArray = [string[]]@($expectedInventoryFiles)
foreach ($array in @($actualInventoryRoots,$actualInventoryFiles,
    $expectedInventoryRootArray,$expectedInventoryFileArray)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if ([string]$inventory.schema -cne 's150-successor-neutral-offline-build-inventory/v1' -or
    ($actualInventoryRoots -join "`n") -cne ($expectedInventoryRootArray -join "`n") -or
    ($actualInventoryFiles -join "`n") -cne ($expectedInventoryFileArray -join "`n")) {
  throw 'Offline build inventory schema/root/file set changed.'
}
foreach ($record in @($inventory.files)) { Assert-S150AuditFileRecord -Record $record }
$actualBuildLeaves = [Collections.Generic.List[string]]::new()
foreach ($root in $expectedInventoryRoots) {
  $fullRoot = [IO.Path]::GetFullPath($root.Replace('/','\'))
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $fullRoot
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Audited build-inventory root is not ordinary: $fullRoot"
  }
  foreach ($child in @(Get-ChildItem -LiteralPath $fullRoot -Force)) {
    $childState = Assert-S150NoReparsePath -PinnedBaseDirectory $fullRoot -TargetPath $child.FullName
    if (-not $childState.Exists -or $child.PSIsContainer) {
      throw "Audited build-inventory root contains a missing or directory entry: $($child.FullName)"
    }
    $actualBuildLeaves.Add($child.FullName.Substring(
      $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/'))
  }
}
$expectedBuildLeaves = [string[]]@($expectedInventoryFiles + @(
  'tools/sigbypass-mod/build/s150-successor-neutral-output-tests/offline-build-inventory.json'))
$actualBuildLeafArray = [string[]]@($actualBuildLeaves)
foreach ($array in @($expectedBuildLeaves,$actualBuildLeafArray)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if (($actualBuildLeafArray -join "`n") -cne ($expectedBuildLeaves -join "`n")) {
  throw 'Generated build roots contain an unowned or missing leaf.'
}
$posttestProcessCensus = [ordered]@{}
foreach ($name in $protectedProcessNames) {
  if ([int]$pretestCensus.counts.$name -ne 0) { throw "Pretest census was nonzero for $name" }
  $posttestProcessCensus[$name] = @(Get-Process -Name $name -ErrorAction SilentlyContinue).Count
  if ([int]$posttestProcessCensus[$name] -ne 0) { throw "Posttest census is nonzero for $name" }
}
$newSourceRecords = @($newSourcePaths | ForEach-Object { Get-S150AuditFileRecord -Path $_ })
$neutralControllerContractTestFullPath = [IO.Path]::GetFullPath(
  $neutralControllerContractTestPath.Replace('/','\'))
$neutralControllerContractTestRecords = @($newSourceRecords | Where-Object {
  [string]::Equals([string]$_.path,$neutralControllerContractTestFullPath,
    [StringComparison]::OrdinalIgnoreCase)
})
if ($neutralControllerContractTestRecords.Count -ne 1) {
  throw 'Neutral controller-contract test is not uniquely pinned by the new-source record set.'
}
$neutralControllerContractTestRecord = $neutralControllerContractTestRecords[0]

$audit = [ordered]@{
  schema = 's150-successor-neutral-offline-audit/v2'
  status = 'PASS'
  recordedUtc = [datetime]::UtcNow.ToString('o')
  baseline = [ordered]@{
    path = $baselinePath
    sha256 = $baselineHash
    receipt = $baselineReceiptRead.Record
  }
  validatedHistoricalRecordCounts = [ordered]@{
    neutralInputs = @($baseline.neutralInputs).Count
    pinnedPreState = @($baseline.pinnedPreState).Count
    activeState = @($baseline.activeState).Count
    retirementFiles = @($baseline.retirement.files).Count
  }
  preexistingIdentityNamespaces = [ordered]@{
    retirementDirectories = @($actualRetirementNamespaces)
    dumpDirectories = @($actualDumpNamespaces)
  }
  preexistingIdentityArtifacts = [ordered]@{
    ledgerDirectoryPath = $ledgerDirectory
    ledgerDirectoryExists = [bool]$ledgerDirectoryState.Exists
    ledgerJsonPaths = @($ledgerJsonPathArray)
    runtimeReceiptPaths = @($runtimeReceiptPathArray)
    identityLabeledPaths = @($identityLabeledPathArray)
    identityControlTraversalExclusions = $identityControlTraversalExclusions
    identityControlObservedPaths = @($identityControlObservedPathArray)
    identityControlArtifactPaths = @($identityControlArtifactPathArray)
    neutralControllerContractTestExemption = [ordered]@{
      path = $neutralControllerContractTestPath
      record = $neutralControllerContractTestRecord
      includedInNewSourceRecords = $true
      includedInCanonicalArtifactSet = $true
    }
  }
  runtimeRepoIdentityBoundary = [ordered]@{
    root = $runtimeRepoRoot
    docs = $runtimeRepoDocs
    ledgerDirectory = $runtimeRepoLedger
    ledgerJsonPaths = @($runtimeRepoLedgerJsonPathArray)
    s150RuntimeEvidencePaths = @($runtimeRepoEvidencePathArray)
  }
  newSourceRecords = @($newSourceRecords)
  launcher = [ordered]@{
    record = Get-S150AuditFileRecord -Path $launcherPath
    bom = 'EF BB BF'
    nonAsciiCodePointCount = 8
    loadIsolation = 'PASS'
    sourceContract = 'PASS'
  }
  processCensus = [ordered]@{
    pretest = $pretestCensusRecord
    pretestReceipt = $pretestReceiptRecord
    requiredPretestCounts = $pretestCensus.counts
    posttestCounts = $posttestProcessCensus
  }
  buildInventory = $inventoryRead.Record
  productionInvocationCount = 0
  successorIdentityCreated = $false
  liveAuthorization = $false
}
$auditPath = [IO.Path]::GetFullPath('docs\s150-successor-neutral-offline-audit-v2.json')
$auditEncoding = [Text.UTF8Encoding]::new($false)
$auditPathState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $auditPath
if ($script:S150OfflineAuditMode -ceq 'CreateNew') {
  if ($auditPathState.Exists -or (Test-Path -LiteralPath $auditPath)) {
    throw 'Offline audit path is not fresh.'
  }
  $auditBytes = $auditEncoding.GetBytes(($audit | ConvertTo-Json -Depth 12))
  $auditStream = [IO.File]::Open(
    $auditPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try {
    $auditStream.Write($auditBytes,0,$auditBytes.Length)
    $auditStream.Flush($true)
  } finally { $auditStream.Dispose() }
  $auditReopenState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $auditPath
  if (-not $auditReopenState.Exists) { throw 'Offline audit disappeared before durable reopen.' }
  $auditLease = [IO.File]::Open(
    $auditPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $auditMemory = [IO.MemoryStream]::new()
    try {
      $auditLease.CopyTo($auditMemory)
      $auditReopened = $auditMemory.ToArray()
    } finally { $auditMemory.Dispose() }
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$auditBytes,[byte[]]$auditReopened)) {
      throw 'Offline audit durable reopen mismatch.'
    }
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $auditOutputHash = ([BitConverter]::ToString(
        $algorithm.ComputeHash([byte[]]$auditReopened))).Replace('-', '')
    } finally { $algorithm.Dispose() }
    $auditOutputPath = $auditPath
  } finally { $auditLease.Dispose() }
} elseif ($script:S150OfflineAuditMode -ceq 'ValidateExisting') {
  if (-not $auditPathState.Exists -or -not (Test-Path -LiteralPath $auditPath -PathType Leaf)) {
    throw 'Offline audit is absent during ValidateExisting.'
  }
  $auditLease = [IO.File]::Open(
    $auditPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $auditMemory = [IO.MemoryStream]::new()
    try {
      $auditLease.CopyTo($auditMemory)
      $auditReopened = $auditMemory.ToArray()
    } finally { $auditMemory.Dispose() }
    $existingAuditText = [Text.UTF8Encoding]::new($false,$true).GetString($auditReopened)
    $existingAudit = $existingAuditText | ConvertFrom-Json
    $audit.recordedUtc = [string]$existingAudit.recordedUtc
    $auditBytes = $auditEncoding.GetBytes(($audit | ConvertTo-Json -Depth 12))
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$auditBytes,[byte[]]$auditReopened)) {
      throw 'Existing offline audit no longer matches fresh recomputation.'
    }
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $auditOutputHash = ([BitConverter]::ToString(
        $algorithm.ComputeHash([byte[]]$auditReopened))).Replace('-', '')
    } finally { $algorithm.Dispose() }
    $auditOutputPath = $auditPath
  } finally { $auditLease.Dispose() }
} else {
  if ($auditPathState.Exists -or (Test-Path -LiteralPath $auditPath)) {
    throw 'Preview requires the offline audit path to remain absent.'
  }
  $auditBytes = $auditEncoding.GetBytes(($audit | ConvertTo-Json -Depth 12))
  $algorithm = [Security.Cryptography.SHA256]::Create()
  try {
    $auditOutputHash = ([BitConverter]::ToString($algorithm.ComputeHash($auditBytes))).Replace('-', '')
  } finally { $algorithm.Dispose() }
  $auditReopened = $auditBytes
  $auditOutputPath = '<PREVIEW-NOT-WRITTEN>'
}
[pscustomobject]@{
  Mode=$script:S150OfflineAuditMode
  Path=$auditOutputPath
  Size=[int64]$auditReopened.Length
  Sha256=$auditOutputHash
} | ConvertTo-Json -Compress
```

## 5. v2 gate procedure

Run each from a fresh Windows PowerShell 5.1 shell with the worktree as the working directory. Any
frozen-input hash mismatch, unexpected process, reparse point, or a fresh v2 output path that is not
absent is an immediate fail-closed stop.

1. **Frozen substrate** — confirm the v1 plan/design/baseline/receipt/Flight 2/helper hashes above.
   Confirm all four fresh v2 output paths absent, ordinary, non-reparse.
2. **Successor tests still GREEN** — the ten focused PS 5.1 tests (watcher `Full`, output `Full`, the
   S149/S148/S147 suites) all exit 0; the successor controller contract against frozen Flight 2 is the
   expected RED with exactly the eight violations `FROZEN_FOUR_LINE_WATCHER`,
   `NO_SUCCESSOR_HELPER_PROVENANCE`, `NO_HELD_WATCHER_IDENTITY_PAIR`, `NO_CANONICAL_RAW_REVALIDATION`,
   `NO_DISTINCT_BACKEND_STDOUT`, `NO_HELD_OUTPUT_IDENTITY_ANCHORS`, `QUIET_SAMPLING_IS_NOT_TERMINALITY`,
   `ARM_FINAL_WATCHER_FENCE_MISSING`; frozen Flight 2 hash/AST unchanged before and after.
3. **Go/C++ behavior** — `go test ./internal/capture` (`-v`, `-count=10`, full) all `ok`; the three
   C++ behavior exes print their `PASS s14x_…` sentinels.
4. **Repository-wide Go baseline (corrected parse)** — `go test ./... -count=1` fails on exactly the
   three known `internal/interactive` tests (`TestArmQueueEmptyIsASingleVariableControl`,
   `TestArmQueueRespectsQueueAllowlist`, `TestCancelArmClearsTheMatch`) and no other test or package;
   the failing package is parsed by tab split (`($line -split "\t")[1]`), and the isolated run
   reproduces the same three names.
5. **Reused build outputs re-validated in place** — re-hash backend A/B (both `115D0999…`, 11,051,520
   B, byte-identical, and equal to active `server/ags.exe`); `text_digest.py --full --verify`/`--dupes`
   over the seven DLLs reproduces the pinned RAW/VSIZE occurrence census with zero hazard/degenerate;
   `verify_dll.py` reports seven `VERDICT: PASS`; the pretest census + receipt and the fifteen-leaf
   inventory match their recorded sizes/hashes.
6. **Corrected audit — Preview** — run §4 in `Preview`; require zero identity violations, all substrate
   / census / inventory / LauncherLoadIsolation / LauncherSource checks pass, posttest process census
   zero, and `<PREVIEW-NOT-WRITTEN>`.
7. **Two preliminary reviews** — obtain non-durable implementation-safety and evidence-readiness
   reviews. Any Critical/Important finding, or any finding whose correction would change an
   implementation/test/fixture/build-input/output/baseline/plan byte, is a preliminary NO-GO that ends
   this execution with every generated output preserved and the durable audit/evidence/review paths
   absent.
8. **Corrected audit — CreateNew** — only after both preliminary reviews are clear, run §4 once in
   `CreateNew`; require one durable `docs/s150-successor-neutral-offline-audit-v2.json` with a durable
   held-stream reopen/byte-compare/hash.

## 6. Evidence, independent reviews, terminal

- **Evidence** `docs/s150-successor-neutral-evidence-v2.md` records: the corrected-defect statement;
  the frozen v1 plan/design/baseline/receipt paths+sizes+hashes; the corrected audit path/size/hash and
  full schema; the RED evidence and every GREEN gate with exact commands; helper/tests/fixtures/launcher
  sizes+hashes; the launcher AST delta and unchanged-branch hashes; full Go/C++/PS regression; the
  reused backend/DLL identities and RAW/VSIZE; the frozen Flight 2 and unchanged-helper provenance; the
  offline-audit-v2 + fifteen-leaf inventory + pretest census/receipt + posttest zero census; the
  no-identity/no-live proof including the introduced-only launcher scan result and the worktree
  namespace/receipt/label censuses and the `G:\git\Supervive Revival Project` runtime-root boundary; the
  hard-stop checks and whether any fired; an exact `reviewState: REVIEW_PENDING` and no GO/NO-GO verdict;
  and the canonical artifact-set and scoped-source-delta lines and hashes. It is written once with
  `CreateNew`, flushed, and immutable thereafter. `OFFLINE GO` is not used.
- **Canonical artifact set** (uppercase SHA-256, `/`-normalized repo-relative paths, ordinal line sort,
  UTF-8 no-BOM, LF joins, no trailing LF), excluding the evidence and review files themselves: the two
  baseline files, `offline-audit-v2.json`, the helper, the launcher, the three successor test files, the
  two fixtures, the fixture exe, the pretest census + receipt, the inventory, the three behavior exes,
  the two backend `ags.exe`, and the seven DLLs. **Scoped source delta**: the same v1 old→new source map
  (five `ABSENT` new sources plus the launcher `A07631BB…`→current).
- **Two independent reviews** — `docs/s150-successor-neutral-implementation-review-v2.md` and
  `…-evidence-review-v2.md`. Each independently recomputes hashes, contains the five exact unique pin
  lines `REVIEWED_PLAN_SHA256` / `REVIEWED_BASELINE_SHA256` / `REVIEWED_EVIDENCE_SHA256` /
  `REVIEWED_ARTIFACT_SET_SHA256` / `REVIEWED_SCOPED_DELTA_SHA256`, and ends with its exact terminal
  verdict line (`IMPLEMENTATION_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0` /
  `EVIDENCE_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0`) only when clear. `REVIEWED_PLAN_SHA256` pins
  this v2 plan.
- **Final verification** — a fresh shell reruns the focused Full tests, the frozen Flight 2 hash/AST
  audit, the expected successor-contract RED, the corrected audit in `ValidateExisting` (byte-identical,
  no write), the canonical artifact-set/scoped-delta recomputation, and both cryptographically bound
  reviewer verdicts, then reopens and hashes all three evidence/review documents.
- **Terminal** — publish `IDENTITY_NEUTRAL_GO` only if every gate and both reviews are GREEN with zero
  Critical/Important findings; otherwise `IDENTITY_NEUTRAL_NO_GO` with the first decisive failure.
  Neither status authorizes live action. On GO:
  `IDENTITY_NEUTRAL_GO; FLIGHT2_IMMUTABLE; NO_SUCCESSOR_IDENTITY; NO_CONTROLLER; NO_MANIFEST; NO_LIVE_ACTION`.

## 7. Boundaries (unchanged from v1)

No identity binding, successor label/UUID/date/controller/manifest/tracker, production
launcher/backend/game/watcher/injector/stager, `RecoverLaunch`, `Arm`, `-Execute`, elevation for
runtime work, historical/receipt PIDs, or `Stop-Process`/`taskkill` on production processes. Read-only
exact-name zero censuses are interference guards only. Flight 2 is terminal and immutable. The frozen
runtime repository `G:\git\Supervive Revival Project` is never written, staged, or committed. No commit
is made unless the user explicitly asks. A future user-approved **late-binding** plan (out of scope
here) remains required to assign any successor label/GUID/date and to wire the reviewed helper into
`RecoverLaunch`/`Arm`.
