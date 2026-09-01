# S150 Successor Identity-Neutral Watcher and Output Ownership Implementation Plan

> **For Codex:** REQUIRED SUB-SKILLS: Use `superpowers:systematic-debugging` for every unexpected result, `superpowers:test-driven-development` for Tasks 2-5, `superpowers:verification-before-completion` for Tasks 6-7, and `superpowers:requesting-code-review` for Task 7. Execute this plan task-by-task. Do not skip RED evidence.

**Goal:** Repair the two terminal S150 Flight 2 trust-boundary defects offline: validate the real five-line watcher startup envelope as canonical raw bytes, and prove bounded launcher-output ownership with separate backend sinks, continuous identity anchors, and writer-denying terminal leases.

**Architecture:** Add one identity-neutral successor evidence helper. Its pure watcher renderer wraps the unchanged S149 semantic parser; its held-handle primitives provide coherent watcher snapshots and terminal launcher receipts. Modify only the controlled branch of `configs/launch-redirect.ps1` so the backend receives distinct stdout and stderr files derived from the capture-archive parent. Preserve every historical gate and ordinary launcher behavior.

**Tech stack:** Windows PowerShell 5.1, .NET `FileStream` sharing semantics, PowerShell AST contracts, a small Windows C++ process fixture, Go, clang++, existing S147-S150 test/build tooling, SHA-256 provenance.

**Approved design:** `docs/superpowers/specs/2026-08-29-s150-successor-watcher-output-ownership-design.md`, 29,410 bytes, SHA-256 `07C0CF46D123E911A779AB61A63262AA8225B07CE7AB2FDB0490D546585717C9`.

---

## Authorization boundary

This plan ends at an identity-neutral offline GO or NO-GO. It does not create or modify a successor controller, controller test tied to an identity, live label, GUID, intended date, review manifest, offline tracker, retirement namespace, dump namespace, live runtime receipt, or ledger entry. It does create only the explicitly listed identity-neutral historical-baseline and pretest-census provenance receipts. It does not invoke a production launcher, backend, game, watcher, injector, stager, `RecoverLaunch`, or `Arm`.

After this plan is GREEN and independently reviewed, write a separate late-binding plan. That later plan may bind one unused identity into a new sibling controller and may stop only at an immutable offline GO. Even that GO is not live authorization. Exactly one `RecoverLaunch -Execute` and exactly one later `Arm -Execute` require separate future user instructions with all exact hashes and receipts cited.

The user has not requested a commit. Do not stage or commit. Every former commit checkpoint is replaced by a no-commit evidence checkpoint.

## Global stop rules

- Preserve all unrelated user changes in the dirty working tree.
- Before locating code, run `codegraph explore` because `.codegraph/` exists. If it reports that no index exists, is unavailable, or is denied by the environment, do not initialize or repair it; record the exact result and use PowerShell AST and `rg`.
- Flight 2 is terminal and immutable. Never edit, copy-over, retry, relabel, or reinterpret its controller, test, manifest, tracker, design, plan, retirement namespace, dump namespace, report, audit, or consumed authorization.
- Keep `configs/s149-bind-gate.ps1`, `configs/s150-capture-generation.ps1`, and `tools/usmapdump/usmapdump.exe` byte-identical.
- Tests precede each production/helper change. A test that unexpectedly passes before its implementation is a specification failure; stop and investigate.
- Every temporary path is a unique child of `.superpowers\temp` or an exact fresh build directory listed below. Validate its resolved parent and reparse state before recursive cleanup.
- Stop immediately on a path collision, reparse component, changed frozen hash, unexpected process, changed known Go baseline, unexpected DLL digest, residual fixture process, or provenance mismatch. Never revise an expected value to fit an unexpected result.
- Do not use quietness, repeated equal samples, sleeps, or elapsed time as proof that a launcher stream is terminal. Only a successfully held `FileMode.Open/FileAccess.Read/FileShare.Read` lease proves writer absence.
- Do not add a caller-supplied backend-output parameter. The controlled launcher derives its paths independently.
- Backend logs remain mutable evidence while the backend is alive. Never label a live backend stream terminal.
- All partial identity anchors and leases are released from an outer `finally`; evidence files are not deleted by production helpers.
- No task in this plan may manipulate, stop, or inspect production processes to select a control target. The exact-name, read-only zero-process censuses below are permitted solely as offline interference guards and never authorize a stop. Process tests operate only on exact test-owned fixtures and require PID/start/path/hash identity before stopping them.
- The only external-repository access is a component-no-reparse, read-only census of the frozen controller runtime root `G:\git\Supervive Revival Project`, its `docs`, and its `docs\s149-ledgers`. Never write, create, delete, copy, stage, build, or launch anything there.

## Frozen inputs and sentinels

| Item | Size | SHA-256 |
|---|---:|---|
| Flight 2 design | 15,134 | `99AB86DB7EC6FEC240FCA4BC7F94A5012D19C49B21BEA0DAFA61BB71C6CBC584` |
| Flight 2 plan | 129,682 | `EF822CB4C3A59CBB0C6C22CCF994DD015C06D17DB0311F8910CC03945EFC3A81` |
| Flight 2 controller | 127,309 | `BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09` |
| Flight 2 controller test | 100,622 | `BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6` |
| Flight 2 review manifest | 22,045 | `83B37B42C1D07B23ECD7F019CFE5396CE4B79A98FDB6ED1967DCFF3AFE92E601` |
| Frozen S150 tracker | 49,213 | `81AA7CFFC1E981DBF1299D294E7EA37AE2BB1665CA97161A2AF1AAEA6282D077` |
| Flight 2 terminal report | 17,543 | `978AFACEAC1EDF2C8B0BFC9E24C75B126E975BEE768BB154418215D89CBB2021` |
| Flight 2 post-failure audit | 1,131 | `EA721DBA7BEAFD48411A1776EC9420199F966397589F5A761895BA8889E515FF` |
| Pre-successor launcher | 37,367 | `A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D` |
| S149 bind gate | 42,464 | `14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA` |
| S150 capture helper | 39,391 | `50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866` |
| Watcher executable | 3,988,480 | `6DAA73BF7238C0A0D91490CA10C38096F88CAA3841C333BBA89B8C55A57B2FCF` |

The preserved watcher stdout is 352 bytes, SHA-256 `CE5A4D371130F9C023BFDAD3528877E9596F246F322A0BE1356564A51EEE4461`, with LF offsets `52,123,245,290,350,351`, five nonempty lines, one final blank line, and offset `2962913`. The historical accepted S149 startup prefix is 348 bytes, SHA-256 `750F7AC145FE5916935C16212378940FE9034D2AACCAD6ABC853B38BFC24A304`.

The preserved launcher stdout is 625 bytes, SHA-256 `15E75FB1FC269F8CA3409AB8011986D6AA4E9D85F37CE5545F8A3692E47008DD`. Flight 2 incorrectly recorded its earlier 602-byte prefix, SHA-256 `BFE367469C77DE74EB2E61E7B6FC9FE6C686AF6EE9A2AC655FF9D49177DCF875`, before the backend appended `#2 GET /healthz -> 200\n`.

## File map

Create during this plan:

- `docs/s150-successor-historical-baseline.json` - durable historical freeze created before any helper or launcher edit.
- `docs/s150-successor-historical-baseline.receipt.json` - immutable baseline receipt binding the baseline hash and metadata.
- `configs/s150-successor-evidence.ps1` - identity-neutral watcher, path, anchor, coherent-snapshot, and terminal-lease primitives.
- `tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1` - pure envelope, coherent watcher stream, and combined stdout/stderr tests.
- `tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1` - path, anchor, terminal lease, partial seal, launcher source, and process matrix.
- `tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1` - parameterized future-controller contract; frozen Flight 2 must remain RED.
- `tools/sigbypass-mod/tests/fixtures/s150_output_writer_fixture.cpp` - test-owned Windows GUI writer/holder.
- `tools/sigbypass-mod/tests/fixtures/s150_output_fake_launcher.ps1` - test-only inherited, isolated, and native invocation shapes.
- `docs/s150-successor-neutral-evidence.md` - exact RED/GREEN, regression, reproducibility, provenance, no-live, and handoff evidence.
- `docs/s150-successor-neutral-offline-audit.json` - durable source/provenance/process/namespace audit used by the evidence review.
- `tools/sigbypass-mod/build/s150-successor-neutral-output-tests/pretest-process-census.receipt.json` - durable same-stream receipt for the pretest zero-process census.
- `tools/sigbypass-mod/build/s150-successor-neutral-output-tests/offline-build-inventory.json` - immutable inventory of every generated leaf included in the offline audit and preserved on any preliminary NO-GO.
- `docs/s150-successor-neutral-implementation-review.md` - independent implementation-safety review.
- `docs/s150-successor-neutral-evidence-review.md` - independent evidence/provenance review.

Modify during this plan:

- `configs/launch-redirect.ps1` - controlled branch only.

Read but never modify:

- `.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller.ps1`
- `.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller-test.ps1`
- `.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-review-manifest.json`
- `.superpowers/sdd/2026-08-27-s150-capture-generation/task-5-controller-report.md`
- `docs/superpowers/specs/2026-08-29-s150-flight2-zero-runtime-recovery-design.md`
- `docs/superpowers/plans/2026-08-29-s150-flight2-zero-runtime-recovery.md`
- `docs/s150-flight2-recoverlaunch-terminal-watcher-refusal.md`
- `docs/s150-flight2-postfailure-audit.json`
- all content below `docs/s150-retirement-s150captureflight2-20260829-192619`
- all content below `dumps/crash-s150captureflight2-20260829-192619`
- `configs/s149-bind-gate.ps1`
- `configs/s150-capture-generation.ps1`
- `tools/usmapdump/usmapdump.exe`

## Exact helper interfaces

Implement these public functions in `configs/s150-successor-evidence.ps1`. Keep the file ASCII-only and compatible with Windows PowerShell 5.1.

```text
Get-S150SuccessorWatcherEnvelopeResult `
    -Bytes ([byte[]]) `
    -ExpectedGamePid ([uint32]) `
    -ExpectedWatcherPid ([uint32]) `
    -ExpectedWatcherStartUtcTicks ([int64]) `
    -ExpectedLogCreationUtcTicks ([int64]) `
    -ActualLogCreationUtcTicks ([int64]) `
    -ActualLogLastWriteUtcTicks ([int64]) `
    -NowUtcTicks ([int64]) `
    -ExpectedLokiPath ([string]) `
    -ExpectedOutputDir ([string])
```

Return an ordered object with exactly:

```text
Valid
Reason
RawLength
RawSha256
Newline
ParsedOffset
ExpectedLogCreationUtcTicks
ActualLogCreationUtcTicks
ActualLogLastWriteUtcTicks
NowUtcTicks
S149Reason
```

Use stable first-failure reasons in this order:

```text
WATCHER_RAW_LIMIT
WATCHER_RAW_ASCII
WATCHER_RAW_FORBIDDEN_BYTE
WATCHER_RAW_SHAPE
WATCHER_OFFSET_GRAMMAR
WATCHER_OFFSET_RANGE
WATCHER_CANONICAL_MISMATCH
WATCHER_S149_REFUSAL
WATCHER_TIME_ORDER
EXACT
```

Successful `Reason`, `S149Reason`, and `Newline` are `EXACT`, `EXACT`, and `LF`. `RawSha256` is uppercase. The helper must compare canonical bytes before decoding and before calling unchanged `Get-S149WatcherReceiptResult`.

```text
Open-S150SuccessorWatcherEvidenceHandles `
    -PinnedBaseDirectory ([string]) `
    -StdoutPath ([string]) `
    -StderrPath ([string])

Get-S150SuccessorCoherentStreamSnapshot `
    -Handle ([object]) `
    -MaxBytes ([int64]) `
    [-BetweenSamples ([scriptblock])]

Get-S150SuccessorWatcherEvidenceResult `
    -Handles ([object]) `
    -ExpectedGamePid ([uint32]) `
    -ExpectedWatcherPid ([uint32]) `
    -ExpectedWatcherStartUtcTicks ([int64]) `
    -ExpectedLogCreationUtcTicks ([int64]) `
    -ActualLogCreationUtcTicks ([int64]) `
    -ActualLogLastWriteUtcTicks ([int64]) `
    -NowUtcTicks ([int64]) `
    -ExpectedLokiPath ([string]) `
    -ExpectedOutputDir ([string]) `
    [-AdmittedWatcherEvidence ([object])]

Close-S150SuccessorWatcherEvidenceHandles -Handles ([object])
```

`BetweenSamples` is a deterministic test seam. The later controller contract forbids that argument at every controller call site. The combined result contains `Valid`, `Reason`, `StdoutSnapshot`, `StderrSnapshot`, `Envelope`, and a handle-free `Admission`. The serializable admission schema is `s150-successor-watcher-admission/v1` and contains exact stdout/stderr paths, sizes, hashes, creation ticks, last-write ticks, stdout newline, parsed offset, and envelope reason.

```text
Get-S150SuccessorOutputPathContract `
    -CaptureArchiveDirectory ([string]) `
    -ExpectedRetirementDirectory ([string])

Assert-S150SuccessorControlledBackendOutputState `
    -PathContract ([object]) `
    -PinnedBaseDirectory ([string]) `
    [-RequireEmpty]

New-S150SuccessorOutputAnchorState -PathContract ([object])

Open-S150SuccessorCreateNewIdentityAnchors `
    -State ([object]) `
    -PinnedBaseDirectory ([string])

Open-S150SuccessorExistingIdentityAnchors `
    -State ([object]) `
    -Roles ([string[]]) `
    -PinnedBaseDirectory ([string])

Open-S150SuccessorTerminalOutputLease `
    -Item ([object]) `
    -MaxOutputBytes ([int64] = 33554432) `
    -TimeoutMilliseconds ([int] = 2000) `
    -RetryMilliseconds ([int] = 25) `
    [-AttemptObserver ([scriptblock])]

Confirm-S150SuccessorTerminalOutputLease `
    -Item ([object]) `
    -ExpectedReceipt ([object])

Close-S150SuccessorOutputAnchorState -State ([object])
```

The path contract returns canonical `CaptureArchiveDirectory`, `RetirementDirectory`, `LauncherStdoutPath`, `LauncherStderrPath`, `BackendStdoutPath`, and `BackendStderrPath`. Full paths compare with `OrdinalIgnoreCase`; literal leaves compare ordinally and case-sensitively. Anchor state has ordered roles `LauncherStdout`, `LauncherStderr`, `BackendStdout`, `BackendStderr`; each item contains `Role`, `Path`, `IdentityStream`, `TerminalLease`, and `TerminalReceipt`.

A terminal receipt contains exact `path`, `size`, uppercase `sha256`, `creationUtcTicks`, `lastWriteUtcTicks`, `terminal = true`, `lease = "Read/FileShare.Read"`, and `recordedUtc`. Confirmation rereads and hashes the same held stream while preserving its position. It must never call `Get-FileHash` by path. `AttemptObserver` is a deterministic test-only timing seam invoked immediately before each writer-denying open with elapsed monotonic milliseconds; the later controller contract forbids callers from supplying it. The public parameter contract is fail-closed: `1 <= MaxOutputBytes <= 33554432`, `1 <= TimeoutMilliseconds <= 2000`, and `1 <= RetryMilliseconds <= 25`. Use parameter validation and repeat the bounds inside the function before the first open so reflection/dynamic invocation cannot silently broaden them; smaller caller values may refuse earlier but can never weaken the ceiling/deadline/retry policy.

---

### Task 1: Freeze the exact historical baseline before implementation bytes change

**Files:**

- Create: `docs/s150-successor-historical-baseline.json`
- Create: `docs/s150-successor-historical-baseline.receipt.json`
- Read only: all frozen inputs, Flight 2 retirement evidence, dump directory, active source state, and `configs/launch-redirect.ps1`

**Interfaces:**

- Schema: `s150-successor-historical-baseline/v1`
- Receipt schema: `s150-successor-historical-baseline-receipt/v1`
- Status: `HISTORICAL_EVIDENCE_ONLY`
- Write semantics: CreateNew, `Flush($true)`, close, reopen read-only, size/hash/metadata receipt

- [ ] **Step 1: Prove the baseline path and every neutral implementation path are absent**

Run:

```powershell
$newPaths = @(
  'docs\s150-successor-historical-baseline.json',
  'docs\s150-successor-historical-baseline.receipt.json',
  'configs\s150-successor-evidence.ps1',
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1',
  'tools\sigbypass-mod\tests\fixtures\s150_output_writer_fixture.cpp',
  'tools\sigbypass-mod\tests\fixtures\s150_output_fake_launcher.ps1',
  'docs\s150-successor-neutral-evidence.md',
  'docs\s150-successor-neutral-offline-audit.json',
  'docs\s150-successor-neutral-implementation-review.md',
  'docs\s150-successor-neutral-evidence-review.md',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests',
  'server\build\s150-successor-neutral-backend-a',
  'server\build\s150-successor-neutral-backend-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play'
)
foreach ($path in $newPaths) {
  if (Test-Path -LiteralPath $path) { throw "Successor path is not fresh: $path" }
}
```

Expected: no output. A pre-existing path is a hard stop; do not overwrite it.

- [ ] **Step 2: Revalidate all immutable hashes, the pre-successor launcher, and exact terminal topology**

Use this exact file set and values:

```powershell
$expectedBaselineInputs = [ordered]@{
  'docs\superpowers\specs\2026-08-29-s150-flight2-zero-runtime-recovery-design.md' = '99AB86DB7EC6FEC240FCA4BC7F94A5012D19C49B21BEA0DAFA61BB71C6CBC584'
  'docs\superpowers\plans\2026-08-29-s150-flight2-zero-runtime-recovery.md' = 'EF822CB4C3A59CBB0C6C22CCF994DD015C06D17DB0311F8910CC03945EFC3A81'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1' = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller-test.ps1' = 'BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-review-manifest.json' = '83B37B42C1D07B23ECD7F019CFE5396CE4B79A98FDB6ED1967DCFF3AFE92E601'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\task-5-controller-report.md' = '81AA7CFFC1E981DBF1299D294E7EA37AE2BB1665CA97161A2AF1AAEA6282D077'
  'docs\s150-flight2-recoverlaunch-terminal-watcher-refusal.md' = '978AFACEAC1EDF2C8B0BFC9E24C75B126E975BEE768BB154418215D89CBB2021'
  'docs\s150-flight2-postfailure-audit.json' = 'EA721DBA7BEAFD48411A1776EC9420199F966397589F5A761895BA8889E515FF'
  'configs\s149-bind-gate.ps1' = '14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA'
  'configs\s150-capture-generation.ps1' = '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866'
  'tools\usmapdump\usmapdump.exe' = '6DAA73BF7238C0A0D91490CA10C38096F88CAA3841C333BBA89B8C55A57B2FCF'
  'configs\launch-redirect.ps1' = 'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D'
}
$repoRoot = (Resolve-Path '.').Path
$rootAttributes = [IO.File]::GetAttributes($repoRoot)
if (($rootAttributes -band [IO.FileAttributes]::Directory) -eq 0 -or
    ($rootAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
  throw 'Worktree root is not an ordinary pinned directory.'
}
$captureHelper = [IO.Path]::GetFullPath('configs\s150-capture-generation.ps1')
foreach ($preloadPath in @([IO.Path]::GetFullPath('configs'), $captureHelper)) {
  $attributes = [IO.File]::GetAttributes($preloadPath)
  if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Preload component is a reparse point: $preloadPath"
  }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash -cne
    '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866') {
  throw 'S150 capture helper cannot be authorized for no-reparse admission.'
}
. $captureHelper
foreach ($entry in $expectedBaselineInputs.GetEnumerator()) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath ([IO.Path]::GetFullPath($entry.Key))
  if (-not $state.Exists) { throw "Pinned input is absent before hashing: $($entry.Key)" }
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $entry.Key).Hash
  if ($actual -cne $entry.Value) { throw "Frozen hash mismatch: $($entry.Key) expected=$($entry.Value) actual=$actual" }
}
```

Require the Flight 2 retirement root `docs\s150-retirement-s150captureflight2-20260829-192619` to contain exactly these 15 recursive ordinary files and no reparse entry:

| Relative path | Size | SHA-256 |
|---|---:|---|
| `capture-archive\9135172aa73b4cc8bac2c9fcbbe93aa1-capture.log` | 81,948,076 | `A0BB12840AEDC385D00EE2986461ED0EF3A01AB9A0CA9A0B253FA0D95C9058F6` |
| `capture-archive\9135172aa73b4cc8bac2c9fcbbe93aa1-capture.log.prev` | 268,435,077 | `E96C5193B528B87D4007B95016B5A645AB7B2D58580AB9DBDEB4EA715285B304` |
| `crashwatch.stderr.log` | 0 | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| `crashwatch.stdout.log` | 352 | `CE5A4D371130F9C023BFDAD3528877E9596F246F322A0BE1356564A51EEE4461` |
| `launcher-child.json` | 2,372 | `AEAAF07755FB86DF9135CD75B654981758900481A214B7BF3C17A066F7367737` |
| `launcher-cleanup-result.json` | 910 | `05BEA16D849709B2D95EE9785DA83A94294138FB05530493BB700F1D2D18CBE2` |
| `launcher-invoked.json` | 1,170 | `15204E0FA6F52D37299BBA07A54C1299029CD88C1D9C1F9B58AC447EF53E42B9` |
| `launcher-result.json` | 2,564 | `DB882D0B9877B31EE4002F64C9F41A46830420B4EB11F39658689C7C51542DD6` |
| `launcher-result.receipt.json` | 516 | `8A68C9B9A76C17AA3890CBE4BE741C08A466F7BC4ABEC49025EE03782147879C` |
| `launcher.stderr.log` | 0 | `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855` |
| `launcher.stdout.log` | 625 | `15E75FB1FC269F8CA3409AB8011986D6AA4E9D85F37CE5545F8A3692E47008DD` |
| `prior-server.out.log` | 35,646 | `3C9CAA4DC92C48FDD4126E18D2E2C8CBC7C2A3199BE71E3385D5984A57C5E171` |
| `recoverlaunch-invoked.json` | 600 | `44D1CEDA891B3290E2D38E918978A4492C3AE91B8680591D659B34F6F8213248` |
| `recovery-handoff.json` | 6,745 | `708D724234416A2AD85856A98364C94E05B6C5719EFFEB802C8E05661827628C` |
| `stager-planonly.json` | 847 | `228CC16C0E4228CC0553F4E33F53CB9F7531D16FC319A0AA86CAB48ACC3B6A02` |

Also require:

- direct retirement entry count 14 and recursive file count 15;
- ordinary empty dump directory `dumps\crash-s150captureflight2-20260829-192619`;
- absence of `fresh-admission.json`, `stager-invoked.json`, `stager-child.json`, `stager.stdout.log`, `stager.stderr.log`, `stager-result.json`, and `stager-result.receipt.json`;
- all six audit process counts are zero and receipt PIDs 37964, 14512, and 7184 are absent in the frozen audit;
- active `server\ags.exe` is 11,051,520 bytes with hash `115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA`;
- active `docs\capture.log` is 394 bytes with hash `2AFD4C663632BD78E9ED414D98D20C26C70E544EF47A96213A38477A919D4A80`;
- `docs\capture.log.prev` is absent;
- the frozen controller runtime root `G:\git\Supervive Revival Project`, its `docs`, and `docs\s149-ledgers` are ordinary non-reparse directories; the runtime ledger has zero `*.json` entries and runtime `docs` has zero `fk24-stage-s150captureflight*` entries;
- active `docs\server.out.log` is 798 bytes with hash `EC0B90B1FE61E8ECFF0E9615BE0339A31E972032C5BBDE2F21A5D20DEB63D7B1`;
- active certificate hashes are root `CA587DE228D23041FC5927ED48DC1ECC83F9C4CB42BFC6972F8C60440B7D129C`, server certificate `01B80C9C42B31FDF5F64DDF7EEA92811B69AE076DF0D1A2D69BFE90E7E6656A2`, and server key `1773ECC40A0725441C97C192C4F53AD9F9520CA2C2FDCA642542826C093F9BFB`.

- [ ] **Step 3: Create and durably freeze the baseline**

Build one ordered JSON object containing the preceding exact paths, sizes, hashes, creation ticks, last-write ticks, directory topology, required absences, active state, Flight 2 identity, global ledger/runtime-receipt/identity-label census, and a complete Base64 raw snapshot plus encoding/newline census of the pre-edit launcher, followed by this exact terminal conclusion:

```text
RECOVERLAUNCH_WATCHER_ADMISSION_REFUSED; BACKEND_AND_GAME_BRIEFLY_LAUNCHED; NO_FRESH_ADMISSION; NO_ARM; NO_STAGER; NO_INJECTION; CLEANUP_STABLE_ZERO; FLIGHT2_TERMINAL_NO_RETRY
```

Use the validated file set to construct the object; do not type a second independent copy of measured metadata:

```powershell
function Get-S150BaselineFileRecord {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$PinnedBaseDirectory,
    [string]$RelativeTo
  )
  $full = [IO.Path]::GetFullPath($Path)
  $pathState = Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $full
  if (-not $pathState.Exists) { throw "Baseline file disappeared before hashing: $full" }
  $stream = [IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item.PSIsContainer) { throw "Baseline file record received a directory: $full" }
    $recordPath = $full
    if (-not [string]::IsNullOrWhiteSpace($RelativeTo)) {
      $base = [IO.Path]::GetFullPath($RelativeTo).TrimEnd([IO.Path]::DirectorySeparatorChar)
      if (-not $full.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Baseline file escaped its expected base: $full"
      }
      $recordPath = $full.Substring($base.Length + 1)
    }
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $sha256 = ([BitConverter]::ToString($hashAlgorithm.ComputeHash($stream))).Replace('-', '')
    } finally { $hashAlgorithm.Dispose() }
    [ordered]@{
      path = $recordPath
      size = [int64]$item.Length
      sha256 = $sha256
      creationUtcTicks = [int64]$item.CreationTimeUtc.Ticks
      lastWriteUtcTicks = [int64]$item.LastWriteTimeUtc.Ticks
      attributes = [string]$item.Attributes
    }
  } finally { $stream.Dispose() }
}

$expectedBaselineInputs = [ordered]@{
  'docs\superpowers\specs\2026-08-29-s150-flight2-zero-runtime-recovery-design.md' = '99AB86DB7EC6FEC240FCA4BC7F94A5012D19C49B21BEA0DAFA61BB71C6CBC584'
  'docs\superpowers\plans\2026-08-29-s150-flight2-zero-runtime-recovery.md' = 'EF822CB4C3A59CBB0C6C22CCF994DD015C06D17DB0311F8910CC03945EFC3A81'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1' = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller-test.ps1' = 'BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-review-manifest.json' = '83B37B42C1D07B23ECD7F019CFE5396CE4B79A98FDB6ED1967DCFF3AFE92E601'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\task-5-controller-report.md' = '81AA7CFFC1E981DBF1299D294E7EA37AE2BB1665CA97161A2AF1AAEA6282D077'
  'docs\s150-flight2-recoverlaunch-terminal-watcher-refusal.md' = '978AFACEAC1EDF2C8B0BFC9E24C75B126E975BEE768BB154418215D89CBB2021'
  'docs\s150-flight2-postfailure-audit.json' = 'EA721DBA7BEAFD48411A1776EC9420199F966397589F5A761895BA8889E515FF'
  'configs\s149-bind-gate.ps1' = '14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA'
  'configs\s150-capture-generation.ps1' = '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866'
  'tools\usmapdump\usmapdump.exe' = '6DAA73BF7238C0A0D91490CA10C38096F88CAA3841C333BBA89B8C55A57B2FCF'
  'configs\launch-redirect.ps1' = 'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D'
}
$expectedRetirementRows = @(
  'capture-archive\9135172aa73b4cc8bac2c9fcbbe93aa1-capture.log|81948076|A0BB12840AEDC385D00EE2986461ED0EF3A01AB9A0CA9A0B253FA0D95C9058F6|639233174350942752|639234740152436268|Archive',
  'capture-archive\9135172aa73b4cc8bac2c9fcbbe93aa1-capture.log.prev|268435077|E96C5193B528B87D4007B95016B5A645AB7B2D58580AB9DBDEB4EA715285B304|639233174350942752|639234717188843299|Archive',
  'crashwatch.stderr.log|0|E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855|639236573109078977|639236573109328977|Archive',
  'crashwatch.stdout.log|352|CE5A4D371130F9C023BFDAD3528877E9596F246F322A0BE1356564A51EEE4461|639236573109068977|639236573111879122|Archive',
  'launcher-child.json|2372|AEAAF07755FB86DF9135CD75B654981758900481A214B7BF3C17A066F7367737|639236572953121269|639236572953131264|Archive',
  'launcher-cleanup-result.json|910|05BEA16D849709B2D95EE9785DA83A94294138FB05530493BB700F1D2D18CBE2|639236573232579806|639236573232589816|Archive',
  'launcher-invoked.json|1170|15204E0FA6F52D37299BBA07A54C1299029CD88C1D9C1F9B58AC447EF53E42B9|639236572947906629|639236572947906629|Archive',
  'launcher-result.json|2564|DB882D0B9877B31EE4002F64C9F41A46830420B4EB11F39658689C7C51542DD6|639236573095918215|639236573095928228|Archive',
  'launcher-result.receipt.json|516|8A68C9B9A76C17AA3890CBE4BE741C08A466F7BC4ABEC49025EE03782147879C|639236573096068211|639236573096068211|Archive',
  'launcher.stderr.log|0|E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855|639236572944686271|639236572948126658|Archive',
  'launcher.stdout.log|625|15E75FB1FC269F8CA3409AB8011986D6AA4E9D85F37CE5545F8A3692E47008DD|639236572944676261|639236573108803162|Archive',
  'prior-server.out.log|35646|3C9CAA4DC92C48FDD4126E18D2E2C8CBC7C2A3199BE71E3385D5984A57C5E171|639233174349767275|639234739639823957|Archive',
  'recoverlaunch-invoked.json|600|44D1CEDA891B3290E2D38E918978A4492C3AE91B8680591D659B34F6F8213248|639236572929861492|639236572929871526|Archive',
  'recovery-handoff.json|6745|708D724234416A2AD85856A98364C94E05B6C5719EFFEB802C8E05661827628C|639236572929991494|639236572929991494|Archive',
  'stager-planonly.json|847|228CC16C0E4228CC0553F4E33F53CB9F7531D16FC319A0AA86CAB48ACC3B6A02|639236572929671485|639236572929721498|Archive'
)
$expectedActiveRows = @(
  'server\ags.exe|11051520|115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA|639233174349482602|639236573065325316|Archive',
  'docs\capture.log|394|2AFD4C663632BD78E9ED414D98D20C26C70E544EF47A96213A38477A919D4A80|639236573082625040|639236573108765574|Archive',
  'docs\server.out.log|798|EC0B90B1FE61E8ECFF0E9615BE0339A31E972032C5BBDE2F21A5D20DEB63D7B1|639233174349767275|639236573084505849|Archive',
  'certs\root.crt|1196|CA587DE228D23041FC5927ED48DC1ECC83F9C4CB42BFC6972F8C60440B7D129C|639233174351570290|639236573084485820|Archive',
  'certs\server.crt|2599|01B80C9C42B31FDF5F64DDF7EEA92811B69AE076DF0D1A2D69BFE90E7E6656A2|639233174351560289|639236573084485820|Archive',
  'certs\server.key|1679|1773ECC40A0725441C97C192C4F53AD9F9520CA2C2FDCA642542826C093F9BFB|639233174351570290|639236573084485820|Archive'
)

function Assert-S150BaselineRows {
  param(
    [Parameter(Mandatory=$true)][string[]]$Rows,
    [Parameter(Mandatory=$true)][string]$PinnedBaseDirectory,
    [string]$BaseDirectory
  )
  foreach ($row in $Rows) {
    $parts = $row.Split('|')
    if ($parts.Count -ne 6) { throw "Malformed baseline expectation row: $row" }
    $path = if ([string]::IsNullOrWhiteSpace($BaseDirectory)) { $parts[0] } else { Join-Path $BaseDirectory $parts[0] }
    $pathState = Assert-S150NoReparsePath -PinnedBaseDirectory $PinnedBaseDirectory -TargetPath $path
    if (-not $pathState.Exists) { throw "Historical baseline row disappeared before hashing: $($parts[0])" }
    $stream = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
      $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
      if ($item.PSIsContainer) { throw "Historical baseline row is not a file: $($parts[0])" }
      $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
      try {
        $actualHash = ([BitConverter]::ToString($hashAlgorithm.ComputeHash($stream))).Replace('-', '')
      } finally { $hashAlgorithm.Dispose() }
      if ([int64]$item.Length -ne [int64]$parts[1] -or
          $actualHash -cne $parts[2] -or
          [int64]$item.CreationTimeUtc.Ticks -ne [int64]$parts[3] -or
          [int64]$item.LastWriteTimeUtc.Ticks -ne [int64]$parts[4] -or
          [string]$item.Attributes -cne $parts[5]) {
        throw "Historical baseline row drifted: $($parts[0])"
      }
    } finally { $stream.Dispose() }
  }
}

$repoRoot = (Resolve-Path '.').Path
$retirement = [IO.Path]::GetFullPath('docs\s150-retirement-s150captureflight2-20260829-192619')
$dump = [IO.Path]::GetFullPath('dumps\crash-s150captureflight2-20260829-192619')
$baselineTarget = [IO.Path]::GetFullPath('docs\s150-successor-historical-baseline.json')
$baselineReceiptTarget = [IO.Path]::GetFullPath('docs\s150-successor-historical-baseline.receipt.json')
$captureHelper = [IO.Path]::GetFullPath('configs\s150-capture-generation.ps1')
$neutralPaths = @(
  'docs\s150-successor-historical-baseline.receipt.json',
  'docs\s150-successor-neutral-offline-audit.json',
  'configs\s150-successor-evidence.ps1',
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1',
  'tools\sigbypass-mod\tests\fixtures\s150_output_writer_fixture.cpp',
  'tools\sigbypass-mod\tests\fixtures\s150_output_fake_launcher.ps1',
  'docs\s150-successor-neutral-evidence.md',
  'docs\s150-successor-neutral-implementation-review.md',
  'docs\s150-successor-neutral-evidence-review.md',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests',
  'server\build\s150-successor-neutral-backend-a',
  'server\build\s150-successor-neutral-backend-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play'
)
$scopedPaths = @(
  'configs\launch-redirect.ps1',
  'docs\superpowers\specs\2026-08-29-s150-successor-watcher-output-ownership-design.md',
  'docs\superpowers\plans\2026-08-30-s150-successor-neutral-boundaries.md',
  'docs\s150-successor-historical-baseline.json'
) + $neutralPaths

# Bootstrap only the already-pinned no-reparse helper. Validate its complete path
# from the pinned worktree root before taking the hash used to authorize loading it.
$repoAttributes = [IO.File]::GetAttributes($repoRoot)
if (($repoAttributes -band [IO.FileAttributes]::Directory) -eq 0 -or
    ($repoAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
  throw 'Worktree root is not an ordinary directory.'
}
foreach ($preloadPath in @([IO.Path]::GetFullPath('configs'), $captureHelper)) {
  $attributes = [IO.File]::GetAttributes($preloadPath)
  if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Preload path is a reparse point: $preloadPath"
  }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash -cne
    '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866') {
  throw 'S150 capture helper drifted before historical baseline creation.'
}
. $captureHelper
$activePaths = @($expectedActiveRows | ForEach-Object { $_.Split('|')[0] })
$requiredAbsent = @(
  'fresh-admission.json','stager-invoked.json','stager-child.json',
  'stager.stdout.log','stager.stderr.log','stager-result.json','stager-result.receipt.json'
)
$existingTargets = @(
  $repoRoot,
  $retirement,
  $dump,
  [IO.Path]::GetFullPath('docs\superpowers\specs\2026-08-29-s150-successor-watcher-output-ownership-design.md'),
  [IO.Path]::GetFullPath('docs\superpowers\plans\2026-08-30-s150-successor-neutral-boundaries.md')
) + @($expectedBaselineInputs.Keys | ForEach-Object { [IO.Path]::GetFullPath($_) }) +
    @($activePaths | ForEach-Object { [IO.Path]::GetFullPath($_) }) +
    @($expectedRetirementRows | ForEach-Object { [IO.Path]::GetFullPath((Join-Path $retirement $_.Split('|')[0])) })
foreach ($targetPath in $existingTargets) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $targetPath
  if (-not $state.Exists) { throw "Pinned baseline path is absent before hashing: $targetPath" }
}

$neutralPathAbsences = [ordered]@{}
foreach ($path in $neutralPaths) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath ([IO.Path]::GetFullPath($path))
  $isAbsent = -not $state.Exists -and -not (Test-Path -LiteralPath $path)
  $neutralPathAbsences[$path] = $isAbsent
  if (-not $isAbsent) { throw "Neutral successor path is not fresh: $path" }
}
$baselineState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $baselineTarget
$baselineWasAbsent = -not $baselineState.Exists -and -not (Test-Path -LiteralPath $baselineTarget)
if (-not $baselineWasAbsent) { throw 'Historical baseline target is not fresh.' }
foreach ($leaf in $requiredAbsent) {
  $absentTarget = Join-Path $retirement $leaf
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $absentTarget
  if ($state.Exists -or (Test-Path -LiteralPath $absentTarget)) {
    throw "Frozen required-absence path exists: $absentTarget"
  }
}
$capturePrevState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath ([IO.Path]::GetFullPath('docs\capture.log.prev'))
if ($capturePrevState.Exists -or (Test-Path -LiteralPath 'docs\capture.log.prev')) {
  throw 'Active capture.log.prev unexpectedly exists.'
}

$scopedStatusLines = @(& git status --porcelain=v1 -uall -- @scopedPaths)
if ($LASTEXITCODE -ne 0) { throw 'Unable to record scoped dirty-tree pre-state.' }
$scopedStatusBytes = [Text.UTF8Encoding]::new($false).GetBytes(($scopedStatusLines -join "`n"))
$sha = [Security.Cryptography.SHA256]::Create()
try {
  $scopedStatusSha256 = ([BitConverter]::ToString($sha.ComputeHash($scopedStatusBytes))).Replace('-', '')
} finally { $sha.Dispose() }
foreach ($entry in $expectedBaselineInputs.GetEnumerator()) {
  $record = Get-S150BaselineFileRecord -Path $entry.Key -PinnedBaseDirectory $repoRoot
  if ([string]$record.sha256 -cne $entry.Value) {
    throw "Pinned pre-state hash drifted: $($entry.Key)"
  }
}
$pendingDirectories = [Collections.Generic.Queue[string]]::new()
$pendingDirectories.Enqueue($retirement)
$validatedRetirementFiles = [Collections.Generic.List[string]]::new()
$retirementDirectEntries = $null
while ($pendingDirectories.Count -gt 0) {
  $directory = $pendingDirectories.Dequeue()
  $children = @(Get-ChildItem -LiteralPath $directory -Force)
  if ([string]::Equals($directory, $retirement, [StringComparison]::OrdinalIgnoreCase)) {
    $retirementDirectEntries = @($children)
  }
  foreach ($child in $children) {
    $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
    if (-not $state.Exists) { throw "Retirement entry disappeared during safe walk: $($child.FullName)" }
    if ($child.PSIsContainer) {
      $pendingDirectories.Enqueue($child.FullName)
    } else {
      $validatedRetirementFiles.Add($child.FullName)
    }
  }
}
$actualRelativeFiles = @($validatedRetirementFiles | ForEach-Object {
  $_.Substring($retirement.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1)
} | Sort-Object)
$expectedRelativeFiles = @($expectedRetirementRows | ForEach-Object { $_.Split('|')[0] } | Sort-Object)
if (($actualRelativeFiles -join "`n") -cne ($expectedRelativeFiles -join "`n")) {
  throw 'Flight 2 retirement leaf set drifted before baseline creation.'
}
Assert-S150BaselineRows -Rows $expectedRetirementRows -BaseDirectory $retirement -PinnedBaseDirectory $repoRoot
Assert-S150BaselineRows -Rows $expectedActiveRows -PinnedBaseDirectory $repoRoot
$expectedRetirementNamespaces = [string[]]@(
  's150-retirement-s150captureflight1-20260827-164413',
  's150-retirement-s150captureflight2-20260829-192619'
)
$expectedDumpNamespaces = [string[]]@(
  'crash-s150captureflight1-20260827-164413',
  'crash-s150captureflight2-20260829-192619'
)
$actualRetirementNamespaces = [string[]]@(Get-ChildItem -LiteralPath 'docs' -Directory -Force |
  Where-Object { $_.Name -like 's150-retirement-*' } | ForEach-Object Name)
$actualDumpNamespaces = [string[]]@(Get-ChildItem -LiteralPath 'dumps' -Directory -Force |
  Where-Object { $_.Name -like 'crash-s150*' } | ForEach-Object Name)
foreach ($array in @($expectedRetirementNamespaces,$expectedDumpNamespaces,
    $actualRetirementNamespaces,$actualDumpNamespaces)) {
  [Array]::Sort($array, [StringComparer]::Ordinal)
}
if (($actualRetirementNamespaces -join "`n") -cne ($expectedRetirementNamespaces -join "`n") -or
    ($actualDumpNamespaces -join "`n") -cne ($expectedDumpNamespaces -join "`n")) {
  throw 'Preexisting S150 identity namespace census changed before baseline creation.'
}
foreach ($namespacePath in @(
    @($actualRetirementNamespaces | ForEach-Object { Join-Path 'docs' $_ }) +
    @($actualDumpNamespaces | ForEach-Object { Join-Path 'dumps' $_ }))) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath ([IO.Path]::GetFullPath($namespacePath))
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Identity namespace is not an ordinary directory: $namespacePath"
  }
}
$docsBase = [IO.Path]::GetFullPath('docs')
$dumpsBase = [IO.Path]::GetFullPath('dumps')
foreach ($identityBase in @($docsBase,$dumpsBase)) {
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $identityBase
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Identity-census base is not an ordinary directory: $identityBase"
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
    if (-not $state.Exists) { throw "Ledger entry disappeared during census: $($ledger.FullName)" }
    $ledgerJsonPaths.Add($ledger.FullName.Substring(
      $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/'))
  }
}
if ($ledgerJsonPaths.Count -ne 0) { throw 'Global S149 ledger JSON census is not zero.' }
$runtimeReceiptPathArray = [string[]]@($runtimeReceiptPaths)
$identityLabeledPathArray = [string[]]@($identityLabeledPaths)
$ledgerJsonPathArray = [string[]]@($ledgerJsonPaths)
foreach ($array in @($runtimeReceiptPathArray,$identityLabeledPathArray,$ledgerJsonPathArray)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
$allowedHistoricalLabelFragments = @(
  's150captureflight1-20260827-164413','s150captureflight2-20260829-192619'
)
foreach ($path in $identityLabeledPathArray) {
  if (@($allowedHistoricalLabelFragments | Where-Object { $path.Contains($_) }).Count -ne 1) {
    throw "Nonhistorical S150 identity-labeled path exists before neutral implementation: $path"
  }
}
foreach ($path in $runtimeReceiptPathArray) {
  if (-not ($path.StartsWith('docs/s150-retirement-s150captureflight1-20260827-164413/',
        [StringComparison]::Ordinal) -or
      $path.StartsWith('docs/s150-retirement-s150captureflight2-20260829-192619/',
        [StringComparison]::Ordinal))) {
    throw "Runtime receipt exists outside the two historical retirement namespaces: $path"
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
        throw 'The top-level .git traversal exclusion is not an ordinary file.'
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
        throw 'The top-level .codegraph traversal exclusion is not an ordinary directory.'
      }
      $codegraphEntries = @(Get-ChildItem -LiteralPath $child.FullName -Force)
      if ($codegraphEntries.Count -ne 1 -or $codegraphEntries[0].Name -cne '.gitignore') {
        throw 'The excluded .codegraph index does not have its exact one-file topology.'
      }
      $codegraphEntryState = Assert-S150NoReparsePath `
        -PinnedBaseDirectory $child.FullName -TargetPath $codegraphEntries[0].FullName
      if (-not $codegraphEntryState.Exists -or $codegraphEntries[0].PSIsContainer -or
          ($codegraphEntryState.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The excluded .codegraph/.gitignore entry is not an ordinary file.'
      }
      $identityControlTraversalExclusions.codegraphIndex = [ordered]@{
        path = '.codegraph'; type = 'Directory'; attributes = [string]$state.Attributes
        directEntryNames = @('.gitignore')
      }
      continue
    }
    $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $child.FullName
    if (-not $state.Exists) { throw "Identity-control census entry disappeared: $($child.FullName)" }
    $relative = $child.FullName.Substring(
      $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/')
    if ($relative -match '(?i)s150' -and $child.Name -match '(?i)(controller|manifest|tracker)') {
      $identityControlObservedPaths.Add($relative)
    }
    if ($child.PSIsContainer) { $controlQueue.Enqueue($child.FullName) }
  }
}
if ($identityControlTraversalExclusions.Count -ne 2) {
  throw 'The exact .git/.codegraph traversal exclusions were not both admitted.'
}
$neutralControllerContractTestPath =
  'tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1'
$identityControlObservedPathArray = [string[]]@($identityControlObservedPaths)
$identityControlArtifactPathArray = [string[]]@($identityControlObservedPathArray | Where-Object {
  $_ -cne $neutralControllerContractTestPath
})
foreach ($array in @($identityControlObservedPathArray,$identityControlArtifactPathArray)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
$expectedHistoricalIdentityControlArtifactPaths = [string[]]@(
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight1-controller-test.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight1-controller.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller-test.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller.ps1',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-review-manifest.json',
  '.superpowers/sdd/2026-08-27-s150-capture-generation/task-5-controller-report.md',
  'docs/s150-retirement-s150captureflight1-20260827-164413/prior-watcher-output-manifest.json'
)
[Array]::Sort($expectedHistoricalIdentityControlArtifactPaths,[StringComparer]::Ordinal)
if (($identityControlObservedPathArray -join "`n") -cne
      ($expectedHistoricalIdentityControlArtifactPaths -join "`n") -or
    ($identityControlArtifactPathArray -join "`n") -cne
    ($expectedHistoricalIdentityControlArtifactPaths -join "`n")) {
  throw 'Unexpected preexisting S150 controller, manifest, or tracker artifact exists.'
}
$runtimeRepoRoot = 'G:\git\Supervive Revival Project'
$runtimeRepoDocs = Join-Path $runtimeRepoRoot 'docs'
$runtimeRepoLedger = Join-Path $runtimeRepoDocs 's149-ledgers'
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
foreach ($array in @($runtimeRepoLedgerJsonPathArray,$runtimeRepoEvidencePathArray)) {
  [Array]::Sort($array,[StringComparer]::Ordinal)
}
if ($runtimeRepoLedgerJsonPathArray.Count -ne 0 -or $runtimeRepoEvidencePathArray.Count -ne 0) {
  throw 'Runtime-repo global ledger or S150 runtime-evidence census is not zero.'
}
$launcherSnapshotPath = [IO.Path]::GetFullPath('configs\launch-redirect.ps1')
$launcherSnapshotHandle = [IO.File]::Open(
  $launcherSnapshotPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
try {
  $launcherSnapshotMemory = [IO.MemoryStream]::new()
  try {
    $launcherSnapshotHandle.CopyTo($launcherSnapshotMemory)
    $launcherRawBytes = $launcherSnapshotMemory.ToArray()
  } finally { $launcherSnapshotMemory.Dispose() }
  $launcherSnapshotHashAlgorithm = [Security.Cryptography.SHA256]::Create()
  try {
    $launcherRawSha256 = ([BitConverter]::ToString(
      $launcherSnapshotHashAlgorithm.ComputeHash([byte[]]$launcherRawBytes))).Replace('-', '')
  } finally { $launcherSnapshotHashAlgorithm.Dispose() }
  $launcherCrlfCount = 0
  $launcherLoneLfCount = 0
  $launcherLoneCrCount = 0
  for ($index = 0; $index -lt $launcherRawBytes.Length; $index++) {
    if ($launcherRawBytes[$index] -eq 13) {
      if ($index + 1 -lt $launcherRawBytes.Length -and $launcherRawBytes[$index + 1] -eq 10) {
        $launcherCrlfCount++
        $index++
      } else { $launcherLoneCrCount++ }
    } elseif ($launcherRawBytes[$index] -eq 10) { $launcherLoneLfCount++ }
  }
  if ($launcherRawBytes.Length -ne 37367 -or
      $launcherRawSha256 -cne 'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D' -or
      $launcherRawBytes[0] -ne 0xEF -or $launcherRawBytes[1] -ne 0xBB -or $launcherRawBytes[2] -ne 0xBF -or
      $launcherCrlfCount -ne 425 -or $launcherLoneLfCount -ne 222 -or $launcherLoneCrCount -ne 0) {
    throw 'Pre-edit launcher raw-byte/encoding/newline census drifted.'
  }
  $launcherRawSnapshot = [ordered]@{
    path = $launcherSnapshotPath
    size = [int64]$launcherRawBytes.Length
    sha256 = $launcherRawSha256
    bomHex = 'EF BB BF'
    crlfCount = $launcherCrlfCount
    loneLfCount = $launcherLoneLfCount
    loneCrCount = $launcherLoneCrCount
    base64 = [Convert]::ToBase64String($launcherRawBytes)
  }
$audit = Get-Content -LiteralPath 'docs\s150-flight2-postfailure-audit.json' -Raw | ConvertFrom-Json
$auditNames = @('ags','SUPERVIVE-Win64-Shipping','usmapdump','go','inject','crashpad_handler')
foreach ($name in $auditNames) {
  if ([int]$audit.processCounts.$name -ne 0) { throw "Frozen audit is not zero for $name" }
}
if (-not [bool]$audit.allProcessesZero -or [int]$audit.dumpEntryCount -ne 0) {
  throw 'Frozen audit zero/dump conclusion drifted.'
}
$baseline = [ordered]@{
  schema = 's150-successor-historical-baseline/v1'
  status = 'HISTORICAL_EVIDENCE_ONLY'
  recordedUtc = [datetime]::UtcNow.ToString('o')
  flight2 = [ordered]@{
    label = 's150captureflight2-20260829-192619'
    generationD = '9135172a-a73b-4cc8-bac2-c9fcbbe93aa1'
    generationN = '9135172aa73b4cc8bac2c9fcbbe93aa1'
    intendedLocalDate = '2026-08-29'
  }
  neutralInputs = @(
    (Get-S150BaselineFileRecord 'docs\superpowers\specs\2026-08-29-s150-successor-watcher-output-ownership-design.md' -PinnedBaseDirectory $repoRoot),
    (Get-S150BaselineFileRecord 'docs\superpowers\plans\2026-08-30-s150-successor-neutral-boundaries.md' -PinnedBaseDirectory $repoRoot)
  )
  baselinePathWasAbsentBeforeCreate = $baselineWasAbsent
  neutralPathAbsences = $neutralPathAbsences
  scopedDirtyTreePreState = [ordered]@{
    command = 'git status --porcelain=v1 -uall --'
    paths = @($scopedPaths)
    canonicalEncoding = 'UTF-8 no BOM; LF join; no trailing LF'
    lines = @($scopedStatusLines)
    sha256 = $scopedStatusSha256
  }
  pinnedPreState = @($expectedBaselineInputs.Keys | ForEach-Object {
    Get-S150BaselineFileRecord $_ -PinnedBaseDirectory $repoRoot
  })
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
    neutralControllerContractTestPath = $neutralControllerContractTestPath
    neutralControllerContractTestPathWasAbsent = [bool]$neutralPathAbsences[
      'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1']
  }
  runtimeRepoIdentityBoundary = [ordered]@{
    root = $runtimeRepoRoot
    docs = $runtimeRepoDocs
    ledgerDirectory = $runtimeRepoLedger
    ledgerJsonPaths = @($runtimeRepoLedgerJsonPathArray)
    s150RuntimeEvidencePaths = @($runtimeRepoEvidencePathArray)
  }
  preEditLauncherRaw = $launcherRawSnapshot
  retirement = [ordered]@{
    path = $retirement
    directEntryCount = @($retirementDirectEntries).Count
    recursiveFileCount = @($validatedRetirementFiles).Count
    reparseEntryCount = 0
    files = @($validatedRetirementFiles | Sort-Object | ForEach-Object {
      Get-S150BaselineFileRecord $_ -PinnedBaseDirectory $repoRoot -RelativeTo $retirement
    })
  }
  dump = [ordered]@{
    path = $dump
    attributes = [string](Get-Item -LiteralPath $dump -Force).Attributes
    entryCount = @(Get-ChildItem -LiteralPath $dump -Force).Count
  }
  requiredAbsences = [ordered]@{}
  activeState = @($activePaths | ForEach-Object {
    Get-S150BaselineFileRecord $_ -PinnedBaseDirectory $repoRoot
  })
  capturePrevAbsent = -not (Test-Path -LiteralPath 'docs\capture.log.prev')
  terminalConclusion = 'RECOVERLAUNCH_WATCHER_ADMISSION_REFUSED; BACKEND_AND_GAME_BRIEFLY_LAUNCHED; NO_FRESH_ADMISSION; NO_ARM; NO_STAGER; NO_INJECTION; CLEANUP_STABLE_ZERO; FLIGHT2_TERMINAL_NO_RETRY'
}
foreach ($leaf in $requiredAbsent) {
  $baseline.requiredAbsences[$leaf] = -not (Test-Path -LiteralPath (Join-Path $retirement $leaf))
}
if ($baseline.neutralInputs[0].sha256 -cne '07C0CF46D123E911A779AB61A63262AA8225B07CE7AB2FDB0490D546585717C9') {
  throw 'Approved successor design drifted before baseline creation.'
}
if ($baseline.retirement.directEntryCount -ne 14 -or
    $baseline.retirement.recursiveFileCount -ne 15 -or
    $baseline.retirement.reparseEntryCount -ne 0 -or
    $baseline.dump.attributes -cne 'Directory' -or
    $baseline.dump.entryCount -ne 0 -or
    -not $baseline.baselinePathWasAbsentBeforeCreate -or
    @($baseline.neutralPathAbsences.Values | Where-Object { -not $_ }).Count -ne 0 -or
    @($baseline.requiredAbsences.Values | Where-Object { -not $_ }).Count -ne 0 -or
    -not $baseline.capturePrevAbsent) {
  throw 'Historical topology or required absence changed before baseline creation.'
}
# The same clean-shell block writes only after every preceding assertion passes.
$target = $baselineTarget
$utf8 = [Text.UTF8Encoding]::new($false)
$bytes = $utf8.GetBytes(($baseline | ConvertTo-Json -Depth 12))
$stream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
try {
  $stream.Write($bytes, 0, $bytes.Length)
  $stream.Flush($true)
} finally {
  $stream.Dispose()
}
$held = [IO.File]::Open($target, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
try {
  $memory = [IO.MemoryStream]::new()
  try {
    $held.CopyTo($memory)
    $reopenedBytes = $memory.ToArray()
  } finally { $memory.Dispose() }
  if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$bytes, [byte[]]$reopenedBytes)) {
    throw 'Historical baseline durable reopen differs from written bytes.'
  }
  $baselineHashAlgorithm = [Security.Cryptography.SHA256]::Create()
  try {
    $baselineReopenedSha256 = ([BitConverter]::ToString(
      $baselineHashAlgorithm.ComputeHash([byte[]]$reopenedBytes))).Replace('-', '')
  } finally { $baselineHashAlgorithm.Dispose() }
  $baselineReceipt = [ordered]@{
    schema = 's150-successor-historical-baseline-receipt/v1'
    baselinePath = $target
    baselineSize = [int64]$reopenedBytes.Length
    baselineSha256 = $baselineReopenedSha256
    baselineCreationUtcTicks = [IO.File]::GetCreationTimeUtc($target).Ticks
    baselineLastWriteUtcTicks = [IO.File]::GetLastWriteTimeUtc($target).Ticks
  }
  $receiptBytes = $utf8.GetBytes(($baselineReceipt | ConvertTo-Json -Depth 4))
  $receiptStream = [IO.File]::Open(
    $baselineReceiptTarget, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
  try {
    $receiptStream.Write($receiptBytes, 0, $receiptBytes.Length)
    $receiptStream.Flush($true)
  } finally { $receiptStream.Dispose() }
  $receiptReopen = [IO.File]::Open(
    $baselineReceiptTarget, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
  try {
    $receiptMemory = [IO.MemoryStream]::new()
    try {
      $receiptReopen.CopyTo($receiptMemory)
      $receiptReopenedBytes = $receiptMemory.ToArray()
    } finally { $receiptMemory.Dispose() }
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$receiptBytes, [byte[]]$receiptReopenedBytes)) {
      throw 'Historical baseline receipt durable reopen differs from written bytes.'
    }
    $receiptHashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $receiptReopenedSha256 = ([BitConverter]::ToString(
        $receiptHashAlgorithm.ComputeHash([byte[]]$receiptReopenedBytes))).Replace('-', '')
    } finally { $receiptHashAlgorithm.Dispose() }
    [pscustomobject]@{
      baselinePath = $target
      baselineSize = [int64]$reopenedBytes.Length
      baselineSha256 = $baselineReceipt.baselineSha256
      receiptPath = $baselineReceiptTarget
      receiptSize = [int64]$receiptReopenedBytes.Length
      receiptSha256 = $receiptReopenedSha256
    } | ConvertTo-Json -Compress
  } finally { $receiptReopen.Dispose() }
} finally { $held.Dispose() }
} finally { $launcherSnapshotHandle.Dispose() }
```

Expected: one receipt summary. Record it for Task 7. Do not edit either immutable file after creation.

- [ ] **Step 4: Record the no-commit baseline checkpoint**

Run `git status --porcelain=v1 -uall --` over the exact `scopedDirtyTreePreState.paths` stored in the baseline. Canonicalize it with the same UTF-8/LF/no-trailing-LF rule. Relative to `scopedDirtyTreePreState.lines`, require exactly two additional entries for the new baseline and its receipt and no other status transition; preserve every pre-existing launcher/plan state. The launcher must still hash to `A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D`. Nothing is staged or committed.

---

### Task 2: Prove the watcher contradiction RED, then implement the pure canonical envelope

**Files:**

- Create: `tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1`
- Create: `tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1`
- Create after RED: `configs/s150-successor-evidence.ps1`
- Read only: frozen Flight 2 controller, preserved watcher receipt, unchanged S149 gate

**Interfaces:**

- `s150_successor_watcher_envelope_test.ps1 -Section Pure|Snapshot|Combined|Full`
- `s150_successor_controller_contract_test.ps1 -CandidateController` accepts one concrete controller file path and `-Section NeutralContract`.

- [ ] **Step 1: Load the TDD workflow and its referenced test-quality guidance**

Read `superpowers:test-driven-development` completely in the implementation session, then read every test-quality instruction it directly references. Record the exact resources read. Do this before writing either test file.

- [ ] **Step 2: Write the pure-envelope and future-controller tests before the helper exists**

Use `$ErrorActionPreference = 'Stop'`, resolve the repository with `Join-Path $PSScriptRoot '..\..\..'`, and reuse the existing `Assert-True`, `Assert-BytesEqual`, and `Assert-Throws` style from `s150_capture_generation_test.ps1`.

The future-controller contract is parameterized and identity-free. Against frozen Flight 2 it must emit one line `VIOLATION ` followed by each of these exact unmet contract IDs in this order, then exit nonzero:

```text
FROZEN_FOUR_LINE_WATCHER
NO_SUCCESSOR_HELPER_PROVENANCE
NO_HELD_WATCHER_IDENTITY_PAIR
NO_CANONICAL_RAW_REVALIDATION
NO_DISTINCT_BACKEND_STDOUT
NO_HELD_OUTPUT_IDENTITY_ANCHORS
QUIET_SAMPLING_IS_NOT_TERMINALITY
ARM_FINAL_WATCHER_FENCE_MISSING
```

It must never invoke the candidate. Parse source only. Hash the frozen controller before and after and require `BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09` both times.

The pure test must read the exact preserved 352 bytes and define the 348-byte historical envelope literally. It must cover:

- preserved 352-byte Flight 2 envelope;
- historical 348-byte S149 envelope;
- synthetic offset zero;
- four or six nonempty lines, duplicate/reordered lines, extra/missing blank line, and truncation;
- CRLF, lone CR, BOM, NUL, non-ASCII, and missing `0A 0A`;
- offsets `-1`, `+1`, `00`, Unicode digits, overflow, missing digits, prose change, and trailing space;
- wrong game PID, Loki path, output directory, poll value, and suspension value;
- creation mismatch, stale/future generation, zero watcher identity, `now < watcherStart`, and last-write before creation.

- [ ] **Step 3: Run and preserve both decisive RED results**

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$frozen = '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1'
$before = (Get-FileHash -Algorithm SHA256 -LiteralPath $frozen).Hash

& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1' -Section Pure
if ($LASTEXITCODE -eq 0) { throw 'Watcher envelope test unexpectedly passed before helper implementation.' }

$contractOutput = @(& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1' `
  -CandidateController $frozen -Section NeutralContract 2>&1)
if ($LASTEXITCODE -eq 0) { throw 'Frozen Flight 2 unexpectedly passed the successor controller contract.' }
foreach ($id in @(
  'FROZEN_FOUR_LINE_WATCHER','NO_SUCCESSOR_HELPER_PROVENANCE',
  'NO_HELD_WATCHER_IDENTITY_PAIR','NO_CANONICAL_RAW_REVALIDATION',
  'NO_DISTINCT_BACKEND_STDOUT','NO_HELD_OUTPUT_IDENTITY_ANCHORS',
  'QUIET_SAMPLING_IS_NOT_TERMINALITY',
  'ARM_FINAL_WATCHER_FENCE_MISSING')) {
  if (($contractOutput -join "`n") -notmatch [regex]::Escape($id)) { throw "Missing frozen RED contract ID: $id" }
}
$after = (Get-FileHash -Algorithm SHA256 -LiteralPath $frozen).Hash
if ($before -cne 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09' -or $after -cne $before) {
  throw 'Frozen Flight 2 controller drifted during RED.'
}
```

Expected: helper/function absence for the pure test; exact eight contract IDs for frozen Flight 2; frozen hash unchanged. A future candidate clears `NO_HELD_OUTPUT_IDENTITY_ANCHORS` only when static control-flow checks prove all four exact output roles are created with no-clobber identity anchors before launcher invocation, retained through durable admission or cleanup, and released only by the outer `finally`.

- [ ] **Step 4: Implement only the pure renderer and validator**

The successor helper must have no load-time S149 dependency: the controlled launcher loads only the unchanged S150 capture helper before dot-sourcing it and calls only output/path APIs. Each public function checks only the dependency it actually consumes. Output/path/snapshot functions require `Assert-S150NoReparsePath` when called; watcher-envelope functions require `Get-S149WatcherReceiptResult` when called. Except for the deliberate missing-S149 isolation phase below, tests that invoke watcher APIs must hash-check and dot-source `configs/s150-capture-generation.ps1` first, hash-check and dot-source `configs/s149-bind-gate.ps1` second, then dot-source the successor helper. Output-only tests load only the pinned S150 helper and successor helper unless a case explicitly crosses into watcher validation. Require SHA-256 `50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866`, function `Assert-S150NoReparsePath`, S149 SHA-256 `14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA`, and function `Get-S149WatcherReceiptResult` before the corresponding API is used. In Task 2, the `Pure` test must first dot-source only S150 plus the new successor helper, prove helper loading succeeds without S149, and prove an attempted watcher call fails closed with exact programming error `S149 watcher parser is not loaded`; it then loads pinned S149 and proves watcher validation works. Task 4 later extends this with the output-path `LauncherLoadIsolation` section after those APIs exist. Implement the pure validator in this exact order:

1. Reject more than 4,096 bytes.
2. Compute uppercase SHA-256 over the supplied raw bytes for every result, while keeping the size limit as the first admission decision.
3. Reject bytes greater than 127, BOM, NUL, and CR.
4. Require exactly six LF bytes and terminal bytes `0A 0A`.
5. Locate the fifth line directly in bytes and require ASCII grammar `0|[1-9][0-9]{0,18}`.
6. Parse invariantly into nonnegative `Int64`; reject overflow.
7. Render the exact five lines plus blank line with `ASCIIEncoding` and LF only.
8. Require equal length and ordinal byte identity.
9. Decode only now, then call unchanged `Get-S149WatcherReceiptResult` with every supplied argument.
10. Independently require `ActualLogLastWriteUtcTicks -ge ActualLogCreationUtcTicks`.
11. Return the ordered result without throwing for an admission refusal.

The canonical rendered text is:

```text
crashwatch: pid {ExpectedGamePid} (SUPERVIVE-Win64-Shipping.exe)\n
  log     : {full ExpectedLokiPath}\n
  outDir  : {full ExpectedOutputDir}\n
  poll    : 50 ms   suspend-on-trigger: true\n
  log tail starts at offset {ParsedOffset} (older markers ignored)\n
\n
```

Do not use `Trim`, text normalization, split-and-rejoin equality, a permissive fifth-line regex over decoded text, or any new semantic parser.

- [ ] **Step 5: Run Pure GREEN and unchanged S149 regression**

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1' -Section Pure
if ($LASTEXITCODE -ne 0) { throw 'Successor pure watcher envelope test failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s149_bind_gate_test.ps1'
if ($LASTEXITCODE -ne 0) { throw 'Unchanged S149 gate regression failed.' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath 'configs\s149-bind-gate.ps1').Hash -cne `
  '14FA776F414A245A71C53657B4153B662801C3F7F3988E5ED4ED56E8F5B67CAA') {
  throw 'S149 bind gate changed.'
}
```

Expected: `PASS s150_successor_watcher_envelope_test Pure` and existing S149 PASS. The frozen future-controller contract intentionally remains RED.

- [ ] **Step 6: Record the no-commit Task 2 checkpoint**

Record RED output, GREEN output, helper/test sizes and hashes, pure result schema/reasons, frozen controller before/after hash, S149 hash, AST parse, ASCII/no-BOM check, and scoped status. Do not stage or commit.

---

### Task 3: Add held-handle coherent watcher snapshots and combined stdout/stderr admission

**Files:**

- Modify test first: `tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1`
- Modify after RED: `configs/s150-successor-evidence.ps1`

**Interfaces:**

- `Open-S150SuccessorWatcherEvidenceHandles`
- `Get-S150SuccessorCoherentStreamSnapshot`
- `Get-S150SuccessorWatcherEvidenceResult`
- `Close-S150SuccessorWatcherEvidenceHandles`

- [ ] **Step 1: Add Snapshot RED cases before snapshot functions**

Use real NTFS files. Open test writers with `FileShare.ReadWrite -bor FileShare.Delete`, write the preserved canonical bytes to stdout, durably flush, and keep both writers open. Require:

- evidence handles open read-only with `FileShare.ReadWrite` and omit delete sharing;
- the legitimate writer remains usable;
- rename, delete, and replacement fail while the evidence handle is held;
- `BetweenSamples` append changes length/hash/metadata and refuses;
- timestamp-only mutation refuses;
- more than 4,096 stdout bytes refuses before an unbounded allocation;
- partial stdout-success/stderr-open-failure disposes stdout;
- close is idempotent.

Run `-Section Snapshot`. Expected RED: snapshot functions absent.

- [ ] **Step 2: Implement the minimum held-handle snapshot path**

For each stream:

1. Reuse `Assert-S150NoReparsePath` for pinned-base and component-wise admission.
2. Require an existing ordinary leaf.
3. Open one persistent read-only `FileStream` with `FileShare.ReadWrite`, deliberately omitting delete sharing.
4. Capture path creation ticks, path last-write ticks, path length, held stream length, and exactly held length bytes.
5. Refresh metadata and require every field plus bytes-read length to remain equal.
6. Hash raw bytes from that held stream.
7. While the same identity handle remains open, acquire a second bounded sample and require equal metadata, length, and hash.
8. Preserve the handle for caller ownership; dispose every partial handle in catch/finally.

`BetweenSamples` runs only between the two samples. Do not expose a timing seam, retry, or normalization.

Run `Snapshot` again and require GREEN before adding any combined-admission case:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1' -Section Snapshot
if ($LASTEXITCODE -ne 0) { throw 'Held-handle watcher snapshot contract did not turn GREEN.' }
```

- [ ] **Step 3: Add combined stdout/stderr RED, then implement it**

Before implementing the combined function, add cases proving a stdout-only implementation would be insufficient:

- canonical stdout plus exact-empty stderr admits;
- nonempty stderr refuses;
- delayed stderr append after initial admission refuses revalidation;
- delayed stdout append refuses revalidation;
- any stdout or stderr path, creation tick, last-write tick, size, or hash mismatch refuses;
- admitted fields are compared, never silently refreshed;
- the pure envelope helper is invoked exactly once per combined check;
- returned admission is serializable and contains no live handles.

Run the new section before adding `Get-S150SuccessorWatcherEvidenceResult`:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1' -Section Combined
if ($LASTEXITCODE -eq 0) { throw 'Combined watcher admission unexpectedly passed before implementation.' }
```

Expected RED: the combined function is absent while the already-GREEN `Pure` and `Snapshot` sections remain unchanged.

Then implement `Get-S150SuccessorWatcherEvidenceResult`: take coherent stdout and stderr snapshots, require stderr size zero and empty SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`, invoke the pure helper for stdout with the caller-supplied Loki expected/actual creation and actual last-write ticks, build `s150-successor-watcher-admission/v1`, and compare every field when `AdmittedWatcherEvidence` is supplied. Never substitute watcher stdout/stderr file timestamps for the Loki generation timestamps consumed by the unchanged S149 parser.

- [ ] **Step 4: Run watcher Full GREEN and resource-leak checks**

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1' -Section Full
if ($LASTEXITCODE -ne 0) { throw 'Full successor watcher evidence test failed.' }
```

Expected: `PASS s150_successor_watcher_envelope_test Full`, all fixture files can be renamed/deleted after close, unique temp root is empty/removed, and no test-owned handle remains.

- [ ] **Step 5: Record the no-commit Task 3 checkpoint**

Record Snapshot RED, Full GREEN, exact helper/test hashes, reason coverage, handle-sharing proof, deterministic append proof, empty-stderr hash, cleanup result, AST/ASCII/no-BOM, and scoped status.

---

### Task 4: Implement output path ownership, continuous identity anchors, and terminal leases with real process tests

**Files:**

- Create test first: `tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1`
- Create fixtures first: `tools/sigbypass-mod/tests/fixtures/s150_output_writer_fixture.cpp`
- Create fixtures first: `tools/sigbypass-mod/tests/fixtures/s150_output_fake_launcher.ps1`
- Modify after RED: `configs/s150-successor-evidence.ps1`

**Interfaces:**

- Test sections: `FrozenRed`, `PathContract`, `Anchors`, `TerminalLease`, `PartialSeal`, `ProcessMatrix`, `LauncherLoadIsolation`, `LauncherSource`, `Full`
- Fixture modes: `InheritedBackend`, `IsolatedBackend`, `NativeGame`

- [ ] **Step 1: Write and compile the test-owned output fixture**

The C++ fixture is a Windows GUI process so native invocation can return while the fixture remains alive. It accepts exactly:

```text
--pid-file
--delay-ms
--hold-ms
--stdout-ascii
--stderr-ascii
```

The two payloads are base64-encoded ASCII. The fixture writes a CreateNew PID receipt containing PID, process creation ticks, executable path, and executable size; flushes it durably; delays; writes through `GetStdHandle` and `WriteFile`; flushes; and remains alive for the requested hold interval. The test independently hashes the pinned fixture executable and validates the live process path before any stop. Invalid arguments fail before the PID receipt. No production path is accepted.

The fake launcher accepts `-Mode`, `-WriterExe`, `-BackendStdoutPath`, `-BackendStderrPath`, and `-PidReceiptPath`:

- `InheritedBackend`: `Start-Process` with inherited streams.
- `IsolatedBackend`: redirects both streams to the two backend paths.
- `NativeGame`: invokes exactly `& $WriterExe @arguments`.

Compile only into the exact fresh directory:

```powershell
$clang = 'C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe'
$fixtureBuild = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests'
if (Test-Path -LiteralPath $fixtureBuild) { throw 'Output fixture build directory is not fresh.' }
[IO.Directory]::CreateDirectory((Join-Path (Resolve-Path '.').Path $fixtureBuild)) | Out-Null
& $clang -std=c++17 -O2 -Wall -Wextra -Werror -Xlinker /SUBSYSTEM:WINDOWS `
  tools\sigbypass-mod\tests\fixtures\s150_output_writer_fixture.cpp `
  -o "$fixtureBuild\s150_output_writer_fixture.exe"
if ($LASTEXITCODE -ne 0) { throw 'Output writer fixture compile failed.' }
```

If the desktop sandbox denies this exact pinned compiler before compilation, rerun the identical command with required approval. Do not substitute a compiler.

- [ ] **Step 2: Prove the inherited-writer defect and helper RED**

`FrozenRed` must reproduce the old two-sample logic with real files/processes: take two equal 50 ms samples, return an old prefix receipt, allow the descendant's delayed append, and require the recorded prefix hash to differ from the final hash. Rehash frozen Flight 2 before/after. It must also statically prove the pre-successor controlled launcher has no distinct backend stdout redirect and that controlled stderr still points at `docs/server.out.log`.

Then add failing `PathContract` cases before implementing any output-path helper.

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureBuild = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests'
$fixtureExe = "$fixtureBuild\s150_output_writer_fixture.exe"
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section FrozenRed -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Frozen inherited-writer characterization failed.' }

& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section PathContract -FixtureExe $fixtureExe
if ($LASTEXITCODE -eq 0) { throw 'PathContract unexpectedly passed before implementation.' }
```

`FrozenRed` is an expected PASS because it proves the historical defect; `PathContract` is the first expected RED. Do not add anchor or lease functions yet.

- [ ] **Step 3: Implement path contract and continuous identity anchors**

`Get-S150SuccessorOutputPathContract` must:

1. Canonicalize the archive and expected retirement paths.
2. Require archive literal leaf exactly `capture-archive`.
3. Require its canonical parent to equal the expected retirement directory with `OrdinalIgnoreCase`.
4. Derive exact sibling leaves `launcher.stdout.log`, `launcher.stderr.log`, `backend.stdout.log`, and `backend.stderr.log`.
5. Require all four strictly within the retirement directory and distinct.

Implement only `Get-S150SuccessorOutputPathContract` and `Assert-S150SuccessorControlledBackendOutputState`, then run `PathContract` GREEN. The assertion must independently recanonicalize the retirement directory, existing `capture-archive` directory, and two backend paths on every call; repeat component-wise ordinary/non-reparse admission for the pinned base, retirement directory, archive directory, and both backend leaves; require the archive leaf and parent relation to remain exact; and, with `-RequireEmpty`, require only the two backend leaves to have zero length. It must not require launcher stdout/stderr to remain empty because the controlled launcher is already writing those streams. Tests must prove nonempty launcher streams plus empty backend streams pass, while either nonempty backend stream, replaced/reparse archive, archive-parent drift, or backend replacement refuses. The assertion deliberately cannot observe or prove that another process owns identity-anchor handles; ordinary unanchored empty backend files therefore pass this state gate. Continuous four-file ownership is a separate controller-held invariant.

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section PathContract -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Output path contract did not turn GREEN.' }
```

Next add `Anchors` cases while `New-S150SuccessorOutputAnchorState`, both open functions, and the close function are all still absent, then run the watched RED:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section Anchors -FixtureExe $fixtureExe
if ($LASTEXITCODE -eq 0) { throw 'Anchors unexpectedly passed before implementation.' }
```

Implement `New-S150SuccessorOutputAnchorState` with the exact ordered four-role item schema, then implement `Open-S150SuccessorCreateNewIdentityAnchors`, `Open-S150SuccessorExistingIdentityAnchors`, and `Close-S150SuccessorOutputAnchorState`. The close operation is idempotent and disposes terminal leases before identity anchors in reverse role order.

`Open-S150SuccessorCreateNewIdentityAnchors` must prevalidate all four paths before creating the first file. For each item, repeat absence/no-reparse checks, open CreateNew `ReadWrite/FileShare.ReadWrite`, `Flush($true)`, open a persistent `Read/FileShare.ReadWrite` identity handle while the creator is still open, then close only the creator. Mutate caller-owned state immediately so an outer `finally` can dispose a partial set. Never delete evidence.

Tests require exact sibling paths, wrong leaf/case refusal, parent mismatch/escape refusal, unchanged pre-existing sentinel, all-path prevalidation before first create, real junction refusal, authorized writer coexistence, rename/delete denial during anchor, and partial-set release after close.

Also test and implement `Open-S150SuccessorExistingIdentityAnchors` for the later Arm boundary: it opens only the requested existing roles, repeats ordinary/component-no-reparse and exact-path admission, keeps earlier successful handles on caller-owned state until outer cleanup, refuses a missing/replaced role, and denies rename/delete while allowing the sharing mode required by an already held compatible terminal lease.

Run `Anchors` again and require GREEN before proceeding.

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section Anchors -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Identity-anchor contract did not turn GREEN.' }
```

- [ ] **Step 4: Implement terminal lease and same-stream receipt**

Add all `TerminalLease`, `PartialSeal`, and `ProcessMatrix` cases before either terminal-lease function exists. Run every section separately and require each watched RED; a failure in one section does not waive the other RED runs:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
foreach ($section in @('TerminalLease','PartialSeal','ProcessMatrix')) {
  & $ps -NoProfile -ExecutionPolicy Bypass -File `
    'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
    -Section $section -FixtureExe $fixtureExe
  if ($LASTEXITCODE -eq 0) { throw "$section unexpectedly passed before terminal-lease implementation." }
}
```

Then implement `Open-S150SuccessorTerminalOutputLease` and `Confirm-S150SuccessorTerminalOutputLease` to satisfy:

- closed writer permits a real `Read/FileShare.Read` lease;
- held writer refuses throughout the bounded policy; use `Diagnostics.Stopwatch` as the monotonic deadline source, check elapsed time immediately before every retry, begin no open attempt at or after 2,000 ms, and sleep no more than `Min(25, remainingMilliseconds)`;
- `AttemptObserver` receives each pre-open elapsed-millisecond value so tests prove every attempted open began before the deadline; the controller contract forbids use of this seam outside tests;
- measure a scheduler-tolerant refusal wall-time upper bound of 8,000 ms while separately requiring monotonic elapsed time to reach at least the configured 2,000 ms deadline and proving no attempt began at or after that deadline;
- every retry is the identical open; quietness never substitutes;
- default deadline exactly 2,000 ms and retry interval exactly 25 ms;
- explicit negative parameter fixtures refuse before any open for `MaxOutputBytes` values `0` and `33554433`, `TimeoutMilliseconds` values `0` and `2001`, and `RetryMilliseconds` values `0` and `26`; the test also proves accepted boundary values `1` and each maximum, and uses `AttemptObserver` to prove validation failures make zero attempts;
- stdout/stderr independence including empty stderr;
- 32 MiB ceiling refusal;
- while both terminal lease and identity anchor are held, writes, delete, and rename fail; after closing only the terminal lease, writes succeed while delete and rename remain denied by the surviving identity anchor; only after closing the identity anchor do delete and rename succeed;
- receipt and confirmation hash the same held stream and preserve its position;
- size/hash/creation/last-write drift refuses;
- close is idempotent and disposes terminal leases before identity anchors in reverse order.

Store an acquired lease immediately on the item. Keep it held even if acquisition of the next role fails.

Run `TerminalLease` again and require GREEN before using the primitive in a composed scenario.

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section TerminalLease -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Terminal lease contract did not turn GREEN.' }
```

- [ ] **Step 5: Prove partial-seal cleanup-only behavior**

The `PartialSeal` section must execute this exact sequence:

1. Close launcher stdout's writer; retain launcher stderr's writer.
2. Seal stdout successfully.
3. Fail stderr sealing and prove stdout's lease remains held.
4. Write a synthetic failed `launcher-result.json` and record its SHA-256.
5. Stop only the exact recorded fixture PID after PID/start/path/hash revalidation.
6. Prove two stable absence samples for that PID.
7. Seal stderr and reconfirm stdout.
8. Finalize backend stdout/stderr only after their exact writer stops.
9. Emit cleanup evidence distinguishing `sealedBeforeCleanup`, `sealedAfterCleanup`, `mutableWhileBackendLive`, and `cleanupOnly`.
10. Require the failed launcher-result hash to remain unchanged.

An unresolved writer is an explicit cleanup error. Never sweep by process name. Cleanup-only hashes cannot upgrade the failed launch into admission success.

Run `PartialSeal` alone and require GREEN before the broader process matrix:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section PartialSeal -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Partial-seal cleanup contract did not turn GREEN.' }
```

- [ ] **Step 6: Run the real-NTFS process matrix GREEN**

Require:

- isolated backend writes only backend stdout/stderr while both launcher leases remain terminal;
- inherited backend refuses launcher sealing;
- a non-backend inherited descendant refuses sealing;
- exact native `&` GUI invocation returns from the direct launcher while the fixture remains alive; any inherited launcher writer is an offline NO-GO;
- pre-existing and reparse paths refuse with zero child starts;
- backend streams are labelled mutable while live and cleanup-only after stop;
- every fixture process is stopped by exact identity and absent afterward;
- protected production process counts are unchanged before/after.

Run:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section ProcessMatrix -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Real-NTFS process matrix did not turn GREEN.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section Full -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Full successor output ownership test failed.' }
```

Expected: one Full PASS, zero residual fixture PIDs, and exact fixture-root cleanup.

- [ ] **Step 7: Record the no-commit Task 4 checkpoint**

Record defect reproduction, every RED/GREEN transition, fixture binary/source hashes, exact lease timings, same-stream proof, partial-seal proof, process identity/cleanup census, helper/test hashes, AST/ASCII/no-BOM, and scoped status.

---

### Task 5: Change only the controlled launcher branch to use distinct derived backend sinks

**Files:**

- Modify test first: `tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1`
- Modify after RED: `configs/launch-redirect.ps1`
- Reuse: `configs/s150-successor-evidence.ps1`

**Interfaces:**

- No new launcher parameter.
- Controlled archive input remains `S150CaptureArchiveDirectory`.
- Controlled backend paths derive from `parent(S150CaptureArchiveDirectory)`.

- [ ] **Step 1: Add `LauncherSource` RED before editing the launcher**

The static AST/source test must initially fail because controlled `ags` redirects only stderr to `$srvOut`. It must pin these unaffected source contracts:

| Contract | Expected SHA-256 |
|---|---|
| Non-controlled backend `Start-Process` AST text, current lines 384-385 | `9F997ED61406A30FE0A1D831931F4397A12DC2FBD1B1B3B44E48DB5AFEAC9551` |
| Native `& $exe @iniArgs` AST text, each occurrence | `A090D0C62C77DACAB3E7F0E4831B4F4DF05FD5B5AE0E2D4E9F5C316E79D290DB` |
| Legacy non-controlled branch, LF-normalized current lines 383-416 | `FA4FDB3D159AABE905ECB5C1ECAA46E909A250A94ED56A033B55F7EFE0492413` |
| Native launch region, LF-normalized current lines 610-617 | `3C8D6D12BED4410A07EFD926B6C0869C349152E72B25426DFDCF8D26BEF6FF60` |

The historical baseline's `preEditLauncherRaw` object is the authoritative old side of the edit. `LauncherSource` must decode its complete Base64 bytes, independently recompute the exact 37,367-byte size, `A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D` hash, `EF BB BF` BOM, 425 CRLF pairs, 222 lone LFs, and zero lone CRs, and require those values to agree with both the embedded fields and `baseline.pinnedPreState`.

Before production editing, define in the test one exact ordered raw-byte replacement map with precisely three names: `ControlledPreflight`, `ControlledBackendStart`, and `ControlledCertificateDiagnostics`. Each entry contains fixed `OldBase64` and desired `NewBase64` byte strings. Each old blob must be nonempty, occur exactly once in the embedded pre-edit bytes, and be ordered and non-overlapping. Construct the only permitted post-edit byte array by replacing those three exact old blobs with the three exact new blobs. The RED requires actual launcher bytes not yet equal that constructed target. GREEN requires ordinal equality of the entire actual raw byte array to that constructed target, not merely AST equivalence; therefore every byte outside the three reviewed replacements, including BOM, mixed line endings, comments, and the already-dirty pre-successor content, is proven unchanged. Independently derive expected post-edit CRLF/lone-LF/lone-CR counts by subtracting each old blob's census and adding its new blob's census, then require the actual whole-file census to match. The test prints each old/new blob size/hash and the hash of the concatenated canonical map for evidence.

Require zero new output parameters; require successor-helper derivation to appear only under the `S150ControlledCapture` AST branch; require the non-controlled branch never to reference successor symbols. The replacement map is immutable test expectation, not a normalization or update-to-match mechanism; if an intended edit does not fit these exact three reviewed regions, stop and revise the plan before production editing.

Before editing the launcher, also add `LauncherLoadIsolation`. It must dynamically dot-source only the pinned S150 capture helper plus the successor helper in a clean process, exercise the output-path API without S149 loaded, require the watcher API to fail closed with exact programming error `S149 watcher parser is not loaded`, then load the pinned S149 helper and prove watcher validation works. Its static half requires the controlled launcher branch to load exactly the S150 capture helper and successor helper, never S149 directly, while the non-controlled branch loads no successor helper. It also forbids the test-only parameter tokens `BetweenSamples` and `AttemptObserver` anywhere in production launcher source; the future controller contract forbids supplying either optional seam at every helper call site. This section is RED before the launcher references the successor helper.

Run both watched RED sections and rehash the launcher after each:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
foreach ($section in @('LauncherLoadIsolation','LauncherSource')) {
  & $ps -NoProfile -ExecutionPolicy Bypass -File `
    'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
    -Section $section -FixtureExe $fixtureExe
  if ($LASTEXITCODE -eq 0) { throw "$section unexpectedly passed before the controlled-launcher edit." }
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath 'configs\launch-redirect.ps1').Hash -cne
      'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D') {
    throw 'Launcher changed during RED.'
  }
}
```

`LauncherSource` must report decisive reason `CONTROLLED_BACKEND_STDOUT_NOT_DISTINCT`.

- [ ] **Step 2: Load and derive successor output paths only in controlled preflight**

Inside the existing `if ($S150ControlledCapture)` preflight, after the unchanged S150 capture helper is loaded and archive no-reparse admission succeeds:

1. Resolve `configs\s150-successor-evidence.ps1` as an ordinary non-reparse file under `configs`.
2. Dot-source it only in the controlled branch.
3. Set `$s150ExpectedRetirementDirectory` to the canonical parent of `S150CaptureArchiveDirectory`.
4. Set `$s150OutputContract = Get-S150SuccessorOutputPathContract -CaptureArchiveDirectory $S150CaptureArchiveDirectory -ExpectedRetirementDirectory $s150ExpectedRetirementDirectory`.
5. Set only `$s150BackendStdoutPath = $s150OutputContract.BackendStdoutPath` and `$s150BackendStderrPath = $s150OutputContract.BackendStderrPath` as process-redirection leaves; retain the contract object for revalidation.
6. Call `Assert-S150SuccessorControlledBackendOutputState -PathContract $s150OutputContract -PinnedBaseDirectory $s150DocsRoot -RequireEmpty` before the Go build.

The archive leaf must be exact case-sensitive `capture-archive`; the two backend leaves must already exist, be ordinary, zero-length, non-reparse, exact siblings. The controller will precreate and continuously hold their identity anchors in the later phase. The launcher cannot observe who owns an external handle, so its path-state gate is necessary but not sufficient proof of controller ownership. Only the future controller contract may claim the anchor invariant.

- [ ] **Step 3: Revalidate immediately before the controlled backend start and redirect both streams**

Inside the existing `StartBackend` scriptblock, immediately after certificate-absence validation and immediately before `Start-Process`, repeat `Assert-S150SuccessorControlledBackendOutputState -PathContract $s150OutputContract -PinnedBaseDirectory $s150DocsRoot -RequireEmpty`.

Replace only the controlled `Start-Process` statement with:

```powershell
Start-Process -FilePath $agsExe -ArgumentList $argString -WorkingDirectory $serverDir `
        -RedirectStandardOutput $s150BackendStdoutPath `
        -RedirectStandardError $s150BackendStderrPath -PassThru
```

The UTF-8/LF AST extent hash for that exact statement is `68E4EB43A7E4F4E1748488B30380B035EDBF9E24839D369AB5BB33BADD9CFDDA`.

Change controlled certificate-failure diagnostics to display both exact backend streams and name both paths in the thrown error. Do not read or write `docs/server.out.log` in controlled mode. Leave its definition and every non-controlled use unchanged.

- [ ] **Step 4: Run LauncherSource GREEN and the complete output suite**

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section LauncherLoadIsolation -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Controlled-launcher load isolation failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section LauncherSource -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Controlled-launcher source contract failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section Full -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Output ownership regression failed after launcher edit.' }
```

Require:

- exactly one controlled stdout redirect and one controlled stderr redirect;
- final path gate directly fences the controlled backend `Start-Process`;
- no successor path derivation on ordinary launch paths;
- non-controlled backend AST and region hashes unchanged;
- both native game invocation hashes and region unchanged;
- complete launcher raw bytes equal the target reconstructed from the immutable baseline plus the exact three-entry replacement map, with every outside byte and the derived mixed-newline census exact;
- no production launcher/backend/game execution.

- [ ] **Step 5: Run focused existing launcher/capture regressions**

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_capture_generation_test.ps1'
if ($LASTEXITCODE -ne 0) { throw 'Focused capture-generation regression failed.' }

$frozenSources = [ordered]@{
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1' = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller-test.ps1' = 'BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6'
}
foreach ($entry in $frozenSources.GetEnumerator()) {
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $entry.Key).Hash -cne $entry.Value) {
    throw "Frozen Flight 2 hash drifted: $($entry.Key)"
  }
  $tokens = $null
  $errors = $null
  [void][Management.Automation.Language.Parser]::ParseFile(
    [IO.Path]::GetFullPath($entry.Key), [ref]$tokens, [ref]$errors)
  if (@($errors).Count -ne 0) { throw "Frozen Flight 2 AST parse failed: $($entry.Key)" }
}
```

This is a post-flight-safe source/hash audit only. Do not execute the frozen Flight 2 test: its `Full` section asserts live-era namespace absences that are intentionally false after the terminal flight. The separate successor controller contract remains deliberately RED against the frozen controller.

- [ ] **Step 6: Record the no-commit Task 5 checkpoint**

Record LauncherSource RED/GREEN, pre/post launcher hash, all three raw replacement old/new sizes/hashes, canonical replacement-map hash, whole-file reconstructed-target equality, derived newline census, exact changed AST extents, unchanged branch hashes, helper load scope, focused regression outputs, immutable Flight 2 hashes, and scoped diff. Require `git diff --check -- configs/launch-redirect.ps1`; do not stage or commit.

---

### Task 6: Run the complete identity-neutral offline gate and reproducibility matrix

**Files:**

- Create only fresh ignored outputs in the exact directories below.
- Create: `docs/s150-successor-neutral-offline-audit.json`
- Do not edit helper, launcher, tests, frozen files, server source, DLL source, or build scripts during this task.

**Interfaces:**

- Consumes the finished identity-neutral implementation.
- Produces fresh tests, A/B binaries, digest results, provenance hashes, and process/namespace absence evidence.
- Audit schema: `s150-successor-neutral-offline-audit/v1`

- [ ] **Step 1: Run all focused Windows PowerShell 5.1 tests**

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$protectedProcessNames = @(
  'ags','SUPERVIVE-Win64-Shipping','usmapdump','go','inject','crashpad_handler',
  's150_output_writer_fixture','s147_natural_state_test','s148_damage_calibration_test',
  's149_bind_bootstrap_test'
)
$pretestProcessCensus = [ordered]@{}
foreach ($name in $protectedProcessNames) {
  $pretestProcessCensus[$name] = @(Get-Process -Name $name -ErrorAction SilentlyContinue).Count
}
if (@($pretestProcessCensus.Values | Where-Object { [int]$_ -ne 0 }).Count -ne 0) {
  throw ('Protected or fixture process exists before offline tests: ' +
    ($pretestProcessCensus | ConvertTo-Json -Compress))
}
$pretestCensusPath = [IO.Path]::GetFullPath(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.json')
$repoRoot = (Resolve-Path '.').Path
$captureHelper = [IO.Path]::GetFullPath('configs\s150-capture-generation.ps1')
foreach ($preloadPath in @($repoRoot,[IO.Path]::GetFullPath('configs'),$captureHelper)) {
  if (([IO.File]::GetAttributes($preloadPath) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Pretest census preload path is reparse: $preloadPath"
  }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash -cne
    '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866') {
  throw 'Pretest census S150 helper provenance mismatch.'
}
. $captureHelper
$pretestPathState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $pretestCensusPath
if ($pretestPathState.Exists -or (Test-Path -LiteralPath $pretestCensusPath)) {
  throw 'Pretest process census path is not fresh.'
}
$pretestCensusObject = [ordered]@{
  schema = 's150-successor-neutral-pretest-process-census/v1'
  recordedUtc = [datetime]::UtcNow.ToString('o')
  counts = $pretestProcessCensus
}
$pretestBytes = [Text.UTF8Encoding]::new($false).GetBytes(
  ($pretestCensusObject | ConvertTo-Json -Depth 4))
$pretestStream = [IO.File]::Open(
  $pretestCensusPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
try {
  $pretestStream.Write($pretestBytes,0,$pretestBytes.Length)
  $pretestStream.Flush($true)
} finally { $pretestStream.Dispose() }
$pretestLease = [IO.File]::Open(
  $pretestCensusPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
try {
  $pretestMemory = [IO.MemoryStream]::new()
  try {
    $pretestLease.CopyTo($pretestMemory)
    $pretestReopenedBytes = $pretestMemory.ToArray()
  } finally { $pretestMemory.Dispose() }
  if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$pretestBytes,[byte[]]$pretestReopenedBytes)) {
    throw 'Pretest process census durable reopen mismatch.'
  }
  $pretestHashAlgorithm = [Security.Cryptography.SHA256]::Create()
  try {
    $pretestSha256 = ([BitConverter]::ToString(
      $pretestHashAlgorithm.ComputeHash([byte[]]$pretestReopenedBytes))).Replace('-', '')
  } finally { $pretestHashAlgorithm.Dispose() }
  $pretestItem = Get-Item -LiteralPath $pretestCensusPath -Force -ErrorAction Stop
  $pretestCensusReceipt = [ordered]@{
    schema = 's150-successor-neutral-pretest-process-census-receipt/v1'
    censusPath = $pretestCensusPath
    censusSize = [int64]$pretestItem.Length
    censusSha256 = $pretestSha256
    censusCreationUtcTicks = [int64]$pretestItem.CreationTimeUtc.Ticks
    censusLastWriteUtcTicks = [int64]$pretestItem.LastWriteTimeUtc.Ticks
  }
  $pretestReceiptPath = [IO.Path]::GetFullPath(
    'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.receipt.json')
  $pretestReceiptState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $pretestReceiptPath
  if ($pretestReceiptState.Exists -or (Test-Path -LiteralPath $pretestReceiptPath)) {
    throw 'Pretest process census receipt path is not fresh.'
  }
  $pretestReceiptBytes = [Text.UTF8Encoding]::new($false).GetBytes(
    ($pretestCensusReceipt | ConvertTo-Json -Depth 4))
  $pretestReceiptStream = [IO.File]::Open(
    $pretestReceiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
  try {
    $pretestReceiptStream.Write($pretestReceiptBytes,0,$pretestReceiptBytes.Length)
    $pretestReceiptStream.Flush($true)
  } finally { $pretestReceiptStream.Dispose() }
  $pretestReceiptLease = [IO.File]::Open(
    $pretestReceiptPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $pretestReceiptMemory = [IO.MemoryStream]::new()
    try {
      $pretestReceiptLease.CopyTo($pretestReceiptMemory)
      $pretestReceiptReopenedBytes = $pretestReceiptMemory.ToArray()
    } finally { $pretestReceiptMemory.Dispose() }
    if (-not [Linq.Enumerable]::SequenceEqual(
        [byte[]]$pretestReceiptBytes,[byte[]]$pretestReceiptReopenedBytes)) {
      throw 'Pretest process census receipt durable reopen mismatch.'
    }
    $pretestReceiptHashAlgorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $pretestReceiptSha256 = ([BitConverter]::ToString(
        $pretestReceiptHashAlgorithm.ComputeHash([byte[]]$pretestReceiptReopenedBytes))).Replace('-', '')
    } finally { $pretestReceiptHashAlgorithm.Dispose() }
    'PRETEST_PROCESS_CENSUS ' + ($pretestCensusObject | ConvertTo-Json -Compress -Depth 4)
    'PRETEST_PROCESS_CENSUS_RECEIPT ' + ([ordered]@{
      receipt = $pretestCensusReceipt
      receiptPath = $pretestReceiptPath
      receiptSize = [int64]$pretestReceiptReopenedBytes.Length
      receiptSha256 = $pretestReceiptSha256
    } | ConvertTo-Json -Compress -Depth 5)
  } finally { $pretestReceiptLease.Dispose() }
} finally { $pretestLease.Dispose() }

$tests = @(
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1',
  'tools\sigbypass-mod\tests\s150_capture_generation_test.ps1',
  'tools\sigbypass-mod\tests\s149_stage_plan_test.ps1',
  'tools\sigbypass-mod\tests\s149_stager_safety_test.ps1',
  'tools\sigbypass-mod\tests\s149_bind_gate_test.ps1',
  'tools\sigbypass-mod\tests\s149_compile_policy_test.ps1',
  'tools\sigbypass-mod\tests\s149_bind_contract_test.ps1',
  'tools\sigbypass-mod\tests\s148_build_contract_test.ps1',
  'tools\sigbypass-mod\tests\s147_input_plan_test.ps1'
)
foreach ($test in $tests) {
  $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$test)
  if ($test -like '*s150_successor_watcher_envelope_test.ps1') { $arguments += @('-Section','Full') }
  if ($test -like '*s150_successor_output_ownership_test.ps1') {
    $arguments += @('-Section','Full','-FixtureExe','tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe')
  }
  & $ps @arguments
  if ($LASTEXITCODE -ne 0) { throw "Offline PowerShell gate failed: $test" }
}

$frozenSources = [ordered]@{
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1' = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'
  '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller-test.ps1' = 'BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6'
}
foreach ($entry in $frozenSources.GetEnumerator()) {
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $entry.Key).Hash -cne $entry.Value) {
    throw "Frozen Flight 2 hash drifted in full gate: $($entry.Key)"
  }
  $tokens = $null
  $errors = $null
  [void][Management.Automation.Language.Parser]::ParseFile(
    [IO.Path]::GetFullPath($entry.Key), [ref]$tokens, [ref]$errors)
  if (@($errors).Count -ne 0) { throw "Frozen Flight 2 AST parse failed in full gate: $($entry.Key)" }
}
```

Do not invoke the frozen Flight 1 or Flight 2 controller tests in this post-flight workspace. Their historical live-era absence assertions are not valid successor regressions; immutable hash/AST audits and the parameterized successor contract are the safe gates.

Run the successor controller contract separately and require the exact eight expected violations against frozen Flight 2. This expected RED is evidence, not a failure of the neutral implementation:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$frozen = '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1'
$expectedViolations = @(
  'FROZEN_FOUR_LINE_WATCHER',
  'NO_SUCCESSOR_HELPER_PROVENANCE',
  'NO_HELD_WATCHER_IDENTITY_PAIR',
  'NO_CANONICAL_RAW_REVALIDATION',
  'NO_DISTINCT_BACKEND_STDOUT',
  'NO_HELD_OUTPUT_IDENTITY_ANCHORS',
  'QUIET_SAMPLING_IS_NOT_TERMINALITY',
  'ARM_FINAL_WATCHER_FENCE_MISSING'
)
$before = (Get-FileHash -Algorithm SHA256 -LiteralPath $frozen).Hash
$contractOutput = @(& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1' `
  -CandidateController $frozen -Section NeutralContract 2>&1)
$contractExit = [int]$LASTEXITCODE
if ($contractExit -eq 0) { throw 'Frozen Flight 2 unexpectedly passed the successor controller contract.' }
$actualViolations = @([regex]::Matches(($contractOutput -join "`n"), '(?m)^VIOLATION ([A-Z0-9_]+)$') |
  ForEach-Object { $_.Groups[1].Value })
if (($actualViolations -join "`n") -cne ($expectedViolations -join "`n")) {
  throw "Frozen successor-contract census changed: $($actualViolations -join ', ')"
}
$after = (Get-FileHash -Algorithm SHA256 -LiteralPath $frozen).Hash
if ($before -cne 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09' -or $after -cne $before) {
  throw 'Frozen Flight 2 controller drifted during successor-contract RED.'
}
```

- [ ] **Step 2: Run focused Go and C++ behavior tests**

```powershell
& 'C:\Program Files\Go\bin\go.exe' test -C server ./internal/capture -run CaptureGeneration -count=1 -v
if ($LASTEXITCODE -ne 0) { throw 'Focused capture-generation tests failed.' }
& 'C:\Program Files\Go\bin\go.exe' test -C server ./internal/capture -run CaptureGeneration -count=10
if ($LASTEXITCODE -ne 0) { throw 'Repeated capture-generation tests failed.' }
& 'C:\Program Files\Go\bin\go.exe' test -C server ./internal/capture -count=1
if ($LASTEXITCODE -ne 0) { throw 'Full capture package failed.' }

$clang = 'C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe'
$behavior = 'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests'
if (Test-Path -LiteralPath $behavior) { throw 'Behavior output directory is not fresh.' }
[IO.Directory]::CreateDirectory((Join-Path (Resolve-Path '.').Path $behavior)) | Out-Null
foreach ($case in @(
  @('tools\sigbypass-mod\tests\s147_natural_state_test.cpp','s147_natural_state_test.exe','PASS s147_natural_state_test'),
  @('tools\sigbypass-mod\tests\s148_damage_calibration_test.cpp','s148_damage_calibration_test.exe','PASS s148_damage_calibration_test'),
  @('tools\sigbypass-mod\tests\s149_bind_bootstrap_test.cpp','s149_bind_bootstrap_test.exe','PASS s149_bind_bootstrap_test')
)) {
  $exe = Join-Path $behavior $case[1]
  & $clang -std=c++17 -O2 $case[0] -o $exe
  if ($LASTEXITCODE -ne 0) { throw "Compile failed: $($case[0])" }
  $output = @(& $exe 2>&1)
  if ($LASTEXITCODE -ne 0 -or ($output -join "`n") -notmatch [regex]::Escape($case[2])) {
    throw "Behavior test failed: $($case[0])"
  }
}
```

Retain and hash the three fresh ordinary executables as evidence.

- [ ] **Step 3: Record the known repository-wide Go baseline without hiding failures**

```powershell
$go = 'C:\Program Files\Go\bin\go.exe'
$expectedFailures = @(
  'TestArmQueueEmptyIsASingleVariableControl',
  'TestArmQueueRespectsQueueAllowlist',
  'TestCancelArmClearsTheMatch'
)
$fullOutput = @(& $go test -C server ./... -count=1 2>&1)
$fullExit = [int]$LASTEXITCODE
if ($fullExit -eq 0) { throw 'Repository-wide Go baseline unexpectedly became green; re-review the changed baseline.' }
$fullText = $fullOutput -join "`n"
$fullFailures = @([regex]::Matches($fullText, '(?m)^\s*--- FAIL: ([^ (\r\n]+)') |
  ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
if (($fullFailures -join "`n") -cne ($expectedFailures -join "`n")) {
  throw "Repository-wide Go failure census changed: $($fullFailures -join ', ')"
}
$failedPackages = @([regex]::Matches($fullText, '(?m)^FAIL\s+(\S+)\s') |
  ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
if ($failedPackages.Count -ne 1 -or -not $failedPackages[0].EndsWith('/internal/interactive', [StringComparison]::Ordinal)) {
  throw "Repository-wide Go failing-package census changed: $($failedPackages -join ', ')"
}

$isolatedOutput = @(& $go test -C server ./internal/interactive `
  -run '^(TestArmQueueRespectsQueueAllowlist|TestArmQueueEmptyIsASingleVariableControl|TestCancelArmClearsTheMatch)$' `
  -count=1 -v 2>&1)
$isolatedExit = [int]$LASTEXITCODE
if ($isolatedExit -eq 0) { throw 'Known isolated Go baseline unexpectedly became green.' }
$isolatedFailures = @([regex]::Matches(($isolatedOutput -join "`n"), '(?m)^\s*--- FAIL: ([^ (\r\n]+)') |
  ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique)
if (($isolatedFailures -join "`n") -cne ($expectedFailures -join "`n")) {
  throw "Isolated Go failure census changed: $($isolatedFailures -join ', ')"
}
```

Expected current baseline: nonzero only for those exact three names in `internal/interactive`, both in the full and isolated runs. Any S150/capture/new test or package failure is a hard NO-GO.

- [ ] **Step 4: Build the backend A/B into fresh directories**

Require `server\build\s150-successor-neutral-backend-a` and `server\build\s150-successor-neutral-backend-b` absent, ordinary, and non-reparse before creation. Then run:

```powershell
$backendDirectories = @(
  'server\build\s150-successor-neutral-backend-a',
  'server\build\s150-successor-neutral-backend-b'
)
foreach ($directory in $backendDirectories) {
  if (Test-Path -LiteralPath $directory) { throw "Backend build directory is not fresh: $directory" }
  [IO.Directory]::CreateDirectory((Join-Path (Resolve-Path '.').Path $directory)) | Out-Null
}
& 'C:\Program Files\Go\bin\go.exe' build -C server `
  -o (Join-Path (Resolve-Path 'server\build\s150-successor-neutral-backend-a').Path 'ags.exe') ./cmd/ags
if ($LASTEXITCODE -ne 0) { throw 'Successor neutral backend A failed.' }
& 'C:\Program Files\Go\bin\go.exe' build -C server `
  -o (Join-Path (Resolve-Path 'server\build\s150-successor-neutral-backend-b').Path 'ags.exe') ./cmd/ags
if ($LASTEXITCODE -ne 0) { throw 'Successor neutral backend B failed.' }
```

Require both files byte-identical, both 11,051,520 bytes, and both SHA-256 `115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA`. Rehash active `server\ags.exe` and require the same frozen active value.

- [ ] **Step 5: Build S149/S148 A/B and S147 regression DLLs**

Require these five paths absent, then create ordinary non-reparse directories:

```text
tools/sigbypass-mod/build/s150-successor-neutral-recovery-a
tools/sigbypass-mod/build/s150-successor-neutral-recovery-b
tools/sigbypass-mod/build/s150-successor-neutral-regression-natural
tools/sigbypass-mod/build/s150-successor-neutral-regression-botai
tools/sigbypass-mod/build/s150-successor-neutral-regression-play
```

Run:

```powershell
$root = (Resolve-Path '.').Path
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$dllDirectories = @(
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play'
)
foreach ($directory in $dllDirectories) {
  if (Test-Path -LiteralPath $directory) { throw "DLL build directory is not fresh: $directory" }
  [IO.Directory]::CreateDirectory((Join-Path $root $directory)) | Out-Null
}
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant botfight-bind-only `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'S149 A build failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant botfight-bind-only `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'S149 B build failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant botfight-damage-self-cal `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'S148 A build failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant botfight-damage-self-cal `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'S148 B build failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant botfight-castalive-dash-mana10-cdocharge1-naturalinput `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'S147 natural build failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant botai `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'Botai regression build failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File tools\sigbypass-mod\build.ps1 `
  -Name tutorial_launch -Variant play `
  -OutDir (Join-Path $root 'tools\sigbypass-mod\build\s150-successor-neutral-regression-play') -Toolchain clang
if ($LASTEXITCODE -ne 0) { throw 'Play regression build failed.' }
```

Every command must report `1 built, 0 failed` and pass imports. Require S149 A/B RAW and VSIZE equality, S148 A/B RAW and VSIZE equality, and exact regression RAW hashes:

```text
S149 RAW    f7765063941de93ab6e18ea82c848402dc3aea97cb5662187cb10ae8a08e6b22
S149 VSIZE  eb405ecda6139d9779be919b4a16abbe82940e2f9c07e0c5b8310f94446c2fba
S148 RAW    c46fb598d0850f248a72ce9c89263df5e987a3790927ca26cc679528b14086df
S148 VSIZE  91cbea32b8b2213316a98f3c6efa1320574d23f44ea689c9a3616c10d168d5ef
```

```text
natural 366e8ef09afa8cb9822b87d4dea885dbbc6356560e873779981f3e8b25861ab8
botai   5e47c13cf7f0a158f93a52c6b42360b06cf791e176cb525983202be5debdedd7
play    9bc10a4552c596e1ca2898c6a08444eae3f500f4c050f896c3a4ddc411c07fcf
```

- [ ] **Step 6: Run DLL verification and duplicate audits on all seven outputs**

Build the seven exact paths from Task 6 Step 5 and run:

```powershell
$dlls = @(
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a\tutorial_launch_botfight_bind_only.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b\tutorial_launch_botfight_bind_only.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a\tutorial_launch_botfight_damage_self_cal.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b\tutorial_launch_botfight_damage_self_cal.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural\tutorial_launch_botfight_castalive_dash_mana10_cdocharge1_naturalinput.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai\tutorial_launch_botai.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play\tutorial_launch_play.dll'
)
foreach ($dll in $dlls) {
  if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) { throw "Expected DLL is absent: $dll" }
}
$digestVerifyOutput = @(python tools\sigbypass-mod\text_digest.py --full --verify @dlls 2>&1)
$digestVerifyExit = $LASTEXITCODE
$digestDupesOutput = @(python tools\sigbypass-mod\text_digest.py --full --dupes @dlls 2>&1)
$digestDupesExit = $LASTEXITCODE
$dllVerifyOutput = @(python tools\sigbypass-mod\verify_dll.py @dlls 2>&1)
$dllVerifyExit = $LASTEXITCODE
if ($digestVerifyExit -ne 0 -or $digestDupesExit -ne 0 -or $dllVerifyExit -ne 0) {
  throw 'DLL verification command failed.'
}
$digestVerifyText = $digestVerifyOutput -join "`n"
if ($digestVerifyText -notmatch 'parsed 7 file\(s\)') { throw 'Did not parse exactly seven DLLs.' }
$expectedDigestOccurrences = [ordered]@{
  'f7765063941de93ab6e18ea82c848402dc3aea97cb5662187cb10ae8a08e6b22' = 2
  'eb405ecda6139d9779be919b4a16abbe82940e2f9c07e0c5b8310f94446c2fba' = 2
  'c46fb598d0850f248a72ce9c89263df5e987a3790927ca26cc679528b14086df' = 2
  '91cbea32b8b2213316a98f3c6efa1320574d23f44ea689c9a3616c10d168d5ef' = 2
  '366e8ef09afa8cb9822b87d4dea885dbbc6356560e873779981f3e8b25861ab8' = 1
  '5e47c13cf7f0a158f93a52c6b42360b06cf791e176cb525983202be5debdedd7' = 1
  '9bc10a4552c596e1ca2898c6a08444eae3f500f4c050f896c3a4ddc411c07fcf' = 1
}
foreach ($digest in $expectedDigestOccurrences.Keys) {
  $count = [regex]::Matches($digestVerifyText, [regex]::Escape($digest)).Count
  if ($count -ne [int]$expectedDigestOccurrences[$digest]) {
    throw "Digest occurrence mismatch: digest=$digest expected=$($expectedDigestOccurrences[$digest]) actual=$count"
  }
}
$digestDupesText = $digestDupesOutput -join "`n"
if ($digestDupesText -match '\*\*\* HAZARD \*\*\*|(?m)^\s*[0-9a-f]{16}\s+DEGENERATE ARM\s+') {
  throw 'DLL duplicate hazard reported.'
}
if ($digestDupesText -notmatch '(?m)^\s*RAW: 0 HAZARD, 0 DEGENERATE ARM,' -or
    $digestDupesText -notmatch '(?m)^\s*VIRTUALSIZE: 0 HAZARD, 0 DEGENERATE ARM,') {
  throw 'DLL duplicate summary is not zero-hazard/zero-degenerate for both recipes.'
}
if ([regex]::Matches(($dllVerifyOutput -join "`n"), '(?m)^\s*VERDICT: PASS\s*$').Count -ne 7) {
  throw 'DLL PASS census is not seven.'
}
```

Require zero RAW/VSIZE hazard and zero degenerate-arm groups. Record the exact S149/S148 A/B digests rather than assuming prior whole-file hashes remain stable.

Before the source audit, freeze the exact generated-leaf inventory used by the offline audit and preserved on any preliminary NO-GO. Every root was absent at Task 1, and every permitted leaf is produced by an exact command above. Refuse any missing/extra leaf or any descendant directory; then CreateNew, flush, held-stream reopen, byte-compare, and hash the inventory itself:

```powershell
$repoRoot = (Resolve-Path '.').Path
$captureHelper = [IO.Path]::GetFullPath('configs\s150-capture-generation.ps1')
foreach ($preloadPath in @($repoRoot,[IO.Path]::GetFullPath('configs'),$captureHelper)) {
  if (([IO.File]::GetAttributes($preloadPath) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Build-inventory preload path is reparse: $preloadPath"
  }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash -cne
    '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866') {
  throw 'Build-inventory helper provenance mismatch.'
}
. $captureHelper
$inventoryRoots = @(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests',
  'server\build\s150-successor-neutral-backend-a',
  'server\build\s150-successor-neutral-backend-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play'
)
$inventoryFiles = @(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.json',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.receipt.json',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests\s147_natural_state_test.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests\s148_damage_calibration_test.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests\s149_bind_bootstrap_test.exe',
  'server\build\s150-successor-neutral-backend-a\ags.exe',
  'server\build\s150-successor-neutral-backend-b\ags.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a\tutorial_launch_botfight_bind_only.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a\tutorial_launch_botfight_damage_self_cal.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b\tutorial_launch_botfight_bind_only.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b\tutorial_launch_botfight_damage_self_cal.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural\tutorial_launch_botfight_castalive_dash_mana10_cdocharge1_naturalinput.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai\tutorial_launch_botai.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play\tutorial_launch_play.dll'
)
function Get-S150InventoryFileRecord {
  param([Parameter(Mandatory=$true)][string]$Path)
  $full = [IO.Path]::GetFullPath($Path)
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $full
  if (-not $state.Exists) { throw "Inventory leaf is absent: $full" }
  $stream = [IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item.PSIsContainer) { throw "Inventory leaf is not a file: $full" }
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $sha256 = ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '')
    } finally { $algorithm.Dispose() }
    [ordered]@{
      path = $full.Substring($repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/')
      size = [int64]$item.Length
      sha256 = $sha256
      creationUtcTicks = [int64]$item.CreationTimeUtc.Ticks
      lastWriteUtcTicks = [int64]$item.LastWriteTimeUtc.Ticks
      attributes = [string]$item.Attributes
    }
  } finally { $stream.Dispose() }
}
$actualInventoryFiles = [Collections.Generic.List[string]]::new()
foreach ($root in $inventoryRoots) {
  $fullRoot = [IO.Path]::GetFullPath($root)
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $fullRoot
  if (-not $state.Exists -or
      ($state.Attributes -band [IO.FileAttributes]::Directory) -eq 0) {
    throw "Inventory root is not an ordinary directory: $fullRoot"
  }
  foreach ($child in @(Get-ChildItem -LiteralPath $fullRoot -Force)) {
    $childState = Assert-S150NoReparsePath -PinnedBaseDirectory $fullRoot -TargetPath $child.FullName
    if (-not $childState.Exists -or $child.PSIsContainer) {
      throw "Inventory root contains a missing or directory entry: $($child.FullName)"
    }
    $actualInventoryFiles.Add($child.FullName)
  }
}
$expectedInventoryFull = [string[]]@($inventoryFiles | ForEach-Object { [IO.Path]::GetFullPath($_) })
$actualInventoryFull = [string[]]@($actualInventoryFiles)
foreach ($array in @($expectedInventoryFull,$actualInventoryFull)) {
  [Array]::Sort($array,[StringComparer]::OrdinalIgnoreCase)
}
if (-not [string]::Equals(
    ($actualInventoryFull -join "`n"),($expectedInventoryFull -join "`n"),
    [StringComparison]::OrdinalIgnoreCase)) {
  throw 'Generated build leaf set is not the exact 15-file inventory.'
}
$inventory = [ordered]@{
  schema = 's150-successor-neutral-offline-build-inventory/v1'
  recordedUtc = [datetime]::UtcNow.ToString('o')
  roots = @($inventoryRoots | ForEach-Object { $_.Replace('\','/') })
  files = @($inventoryFiles | ForEach-Object { Get-S150InventoryFileRecord -Path $_ })
}
$inventoryPath = [IO.Path]::GetFullPath(
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\offline-build-inventory.json')
$inventoryState = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $inventoryPath
if ($inventoryState.Exists -or (Test-Path -LiteralPath $inventoryPath)) {
  throw 'Offline build inventory path is not fresh.'
}
$inventoryBytes = [Text.UTF8Encoding]::new($false).GetBytes(
  ($inventory | ConvertTo-Json -Depth 8))
$inventoryStream = [IO.File]::Open(
  $inventoryPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::Read)
try {
  $inventoryStream.Write($inventoryBytes,0,$inventoryBytes.Length)
  $inventoryStream.Flush($true)
} finally { $inventoryStream.Dispose() }
$inventoryLease = [IO.File]::Open(
  $inventoryPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
try {
  $inventoryMemory = [IO.MemoryStream]::new()
  try {
    $inventoryLease.CopyTo($inventoryMemory)
    $inventoryReopened = $inventoryMemory.ToArray()
  } finally { $inventoryMemory.Dispose() }
  if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$inventoryBytes,[byte[]]$inventoryReopened)) {
    throw 'Offline build inventory durable reopen mismatch.'
  }
  $algorithm = [Security.Cryptography.SHA256]::Create()
  try {
    $inventorySha256 = ([BitConverter]::ToString(
      $algorithm.ComputeHash([byte[]]$inventoryReopened))).Replace('-', '')
  } finally { $algorithm.Dispose() }
  [pscustomobject]@{ Path=$inventoryPath; Size=$inventoryReopened.Length; Sha256=$inventorySha256 } |
    ConvertTo-Json -Compress
} finally { $inventoryLease.Dispose() }
```

- [ ] **Step 7: Run source, provenance, and no-live audits**

Require:

- zero PowerShell AST parse errors for every created/modified `.ps1`;
- ASCII-only and no UTF-8 BOM for every new helper/test/fixture source;
- preserve the launcher's existing UTF-8 BOM bytes `EF BB BF`, existing decoded non-ASCII code-point census 8, and every unaffected source extent; do not normalize its encoding or mixed historical line endings;
- `git diff --check` for every scoped source file;
- all immutable Flight 2/report/audit hashes from Task 1 unchanged; the current launcher is intentionally different, while its pre-successor `A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D` record remains unchanged inside the historical baseline;
- historical baseline hash unchanged, including self-consistent complete pre-edit launcher Base64 bytes and raw encoding/newline census;
- S149, S150 capture helper, and watcher hashes unchanged;
- launcher diff confined to controlled preflight, controlled backend start, and controlled diagnostics by whole-file raw equality against the immutable pre-edit bytes plus the exact three-entry replacement map;
- exact non-controlled/native AST hashes unchanged;
- no successor identity exists: require worktree retirement/dump namespaces, worktree S149 ledger JSON entries, worktree runtime-receipt paths, and every worktree path containing an S150 flight label to remain byte-for-byte equal to the baseline census; run an unfiltered recursive worktree-wide S150 controller/manifest/tracker path census, excluding traversal only for the exact top-level `.git` metadata file and `.codegraph` index directory, and record the exact observed set; require it to change from the baseline's exact seven historical paths only by the planned ordinary/non-reparse `tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1`; exempt only that exact neutral test from the identity-bearing set, pin its source and canonical artifact record, and require the filtered set to remain the exact seven historical paths; separately require the frozen controller's exact runtime root `G:\git\Supervive Revival Project`, its `docs`, and `docs\s149-ledgers` to remain ordinary/non-reparse with zero ledger JSON entries and zero `fk24-stage-s150captureflight*` runtime-evidence collisions; scan all six new sources plus the modified launcher for label, UUID D, UUID N, compact/ISO intended-date, concrete ledger, runtime-receipt, and runtime-evidence paths; allow only exact historical references `s150captureflight1-20260827-164413`, `s150captureflight2-20260829-192619`, Flight 2 GUID D/N `9135172a-a73b-4cc8-bac2-c9fcbbe93aa1` / `9135172aa73b4cc8bac2c9fcbbe93aa1`, and their exact historical dates; reject any identity/date/manifest/ledger token in both production files;
- before either traversal exclusion, require `.git` to be an ordinary non-reparse file and `.codegraph` to be an ordinary non-reparse directory containing exactly one ordinary non-reparse `.gitignore` file; persist their exact types, attributes, and direct topology in the baseline and require the audit replay to match before skipping either path;
- no production launcher, backend, game, watcher, injector, stager, `RecoverLaunch`, or `Arm` invocation in command history/evidence;
- every test fixture PID absent and all unique fixture roots cleaned;
- all protected production process counts unchanged from the read-only pretest census.

Run this exact audit from a fresh Windows PowerShell 5.1 shell. It replays the baseline by record rather than trusting prose and handles untracked sources explicitly. Its default `Preview` mode writes nothing so preliminary review can still trigger corrections:

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
  $noIndexOutput = @(& git diff --no-index --check -- NUL $path 2>&1)
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
  '20260827','20260829','2026-08-27','2026-08-29'
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
foreach ($path in $identityScanPaths) {
  $full = [IO.Path]::GetFullPath($path)
  $bytes = [IO.File]::ReadAllBytes($full)
  $text = if ([string]::Equals($full,$launcherPath,[StringComparison]::OrdinalIgnoreCase)) {
    $strictUtf8.GetString($bytes,3,$bytes.Length - 3)
  } else {
    [Text.ASCIIEncoding]::new().GetString($bytes)
  }
  $identityLiterals = @([regex]::Matches($text,$identityLiteralPattern) |
    ForEach-Object Value | Sort-Object -Unique)
  foreach ($literal in $identityLiterals) {
    if ($literal -cnotin $allowedIdentityLiterals) {
      throw "Successor label/GUID-D/GUID-N/date literal detected: $literal in $path"
    }
  }
  foreach ($entry in $forbiddenConcretePathPatterns.GetEnumerator()) {
    if ([regex]::IsMatch($text,[string]$entry.Value)) {
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
$trackedDiffOutput = @(& git diff --check -- configs/launch-redirect.ps1 2>&1)
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
  schema = 's150-successor-neutral-offline-audit/v1'
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
$auditPath = [IO.Path]::GetFullPath('docs\s150-successor-neutral-offline-audit.json')
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

`productionInvocationCount = 0` is accepted only when the independent evidence reviewer also confirms the complete Task 1-7 command transcript contains no production launcher/backend/game/watcher/injector/stager/RecoverLaunch/Arm invocation. The eventual persisted audit is necessary but not sufficient for that claim.

- [ ] **Step 8: Record the no-commit Task 6 checkpoint**

Record every exact command, exit code, PASS line, known Go failure name, build path, size/hash, RAW/VSIZE digest, verifier census, frozen hash, AST/source hash, process census, and scoped status. Before freezing Task 7 evidence, obtain two non-durable preliminary reviews of implementation safety and evidence readiness. Preliminary reviewers return findings out-of-band and create neither final review file nor terminal verdict.

If either preliminary reviewer reports a Critical/Important finding, or any finding whose correction would change implementation, test, fixture, build input, generated output, baseline, plan, or receipt bytes, publish a preliminary NO-GO and end this execution. Preserve every generated output and inventory leaf exactly as evidence; do not delete, rewrite, rename, quarantine, or reuse any of them. The durable audit/evidence/final-review paths remain absent. Remediation requires a new user-approved versioned plan with fresh baseline, audit, evidence, review, and build-output paths; it may not carry any prior verdict or generated artifact forward. A non-blocking Minor observation may be recorded without mutation, but it cannot waive any acceptance criterion.

Only after both preliminary reviewers are clear, open one fresh Windows PowerShell 5.1 shell, set `$script:S150OfflineAuditMode = 'CreateNew'`, replay the exact Step 7 audit block, and require one durable `CreateNew` audit receipt. Remove the variable after the block. From this point onward no implementation, test, fixture, baseline, audit, or build-output byte may change. Do not stage or commit.

---

### Task 7: Publish neutral evidence, obtain independent reviews, and stop at the late-binding boundary

**Files:**

- Create: `docs/s150-successor-neutral-evidence.md`
- Create: `docs/s150-successor-neutral-implementation-review.md`
- Create: `docs/s150-successor-neutral-evidence-review.md`
- Do not create a controller, identity, manifest, tracker, namespace, live runtime receipt, or any additional provenance receipt.

**Interfaces:**

- Neutral status is exactly one of `IDENTITY_NEUTRAL_GO` or `IDENTITY_NEUTRAL_NO_GO`.
- Neither status authorizes live action.

- [ ] **Step 1: Write the evidence document from fresh outputs**

The evidence document must contain:

1. approved design path/size/hash;
2. this plan path/size/hash as measured at execution start;
3. historical baseline and immutable receipt paths/sizes/hashes/timestamps plus full schema/topology validation;
4. watcher and output defect RED evidence;
5. every GREEN test and exact command;
6. helper, tests, fixtures, and changed launcher sizes/hashes;
7. exact launcher AST delta and unchanged branch hashes;
8. full Go/C++/PowerShell regression results;
9. backend/DLL A/B identities, RAW/VSIZE values, and all three S147 sentinels;
10. frozen Flight 2 and unchanged-helper provenance table;
11. offline-audit and exact 15-leaf build-inventory paths/sizes/hashes/schemas plus the pretest census and its same-stream receipt paths/sizes/hashes/metadata and fixture/production pre/post zero-process census;
12. no-identity/no-live proof, including exact worktree namespace/receipt/label censuses, the eight-path observed/seven-path identity-bearing controller/manifest/tracker split with its one pinned neutral-test exemption, and the `G:\git\Supervive Revival Project` runtime-root ledger/evidence censuses;
13. all hard-stop checks and whether any fired;
14. exact `reviewState: REVIEW_PENDING` and no GO/NO-GO verdict;
15. the canonical artifact-set lines/hash and canonical scoped-source-delta lines/hash defined below.

Do not claim a live candidate exists. Do not use `OFFLINE GO`; reserve that phrase for the later identity-bound package. Immediately before creation, revalidate the ordinary non-reparse `docs` base and every component of the evidence path with the pinned S150 helper. Write the evidence once with CreateNew, `Flush($true)`, close, and hash it. From that point through handoff it is immutable; any needed correction creates a hard NO-GO for this run and requires a fresh evidence/review cycle, never an in-place post-review edit.

Use this exact artifact set. It intentionally excludes the evidence and review files themselves to avoid a self-hash cycle:

```powershell
$artifactPaths = @(
  'docs\s150-successor-historical-baseline.json',
  'docs\s150-successor-historical-baseline.receipt.json',
  'docs\s150-successor-neutral-offline-audit.json',
  'configs\s150-successor-evidence.ps1',
  'configs\launch-redirect.ps1',
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1',
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1',
  'tools\sigbypass-mod\tests\fixtures\s150_output_writer_fixture.cpp',
  'tools\sigbypass-mod\tests\fixtures\s150_output_fake_launcher.ps1',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.json',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\pretest-process-census.receipt.json',
  'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\offline-build-inventory.json',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests\s147_natural_state_test.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests\s148_damage_calibration_test.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-behavior-tests\s149_bind_bootstrap_test.exe',
  'server\build\s150-successor-neutral-backend-a\ags.exe',
  'server\build\s150-successor-neutral-backend-b\ags.exe',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a\tutorial_launch_botfight_bind_only.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b\tutorial_launch_botfight_bind_only.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-a\tutorial_launch_botfight_damage_self_cal.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-recovery-b\tutorial_launch_botfight_damage_self_cal.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-natural\tutorial_launch_botfight_castalive_dash_mana10_cdocharge1_naturalinput.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-botai\tutorial_launch_botai.dll',
  'tools\sigbypass-mod\build\s150-successor-neutral-regression-play\tutorial_launch_play.dll'
)
$sourceDeltaOld = [ordered]@{
  'docs/s150-successor-historical-baseline.json' = 'ABSENT'
  'docs/s150-successor-historical-baseline.receipt.json' = 'ABSENT'
  'configs/s150-successor-evidence.ps1' = 'ABSENT'
  'configs/launch-redirect.ps1' = 'A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D'
  'tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1' = 'ABSENT'
  'tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1' = 'ABSENT'
  'tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1' = 'ABSENT'
  'tools/sigbypass-mod/tests/fixtures/s150_output_writer_fixture.cpp' = 'ABSENT'
  'tools/sigbypass-mod/tests/fixtures/s150_output_fake_launcher.ps1' = 'ABSENT'
}

$repoRoot = (Resolve-Path '.').Path
$captureHelper = [IO.Path]::GetFullPath('configs\s150-capture-generation.ps1')
$repoAttributes = [IO.File]::GetAttributes($repoRoot)
if (($repoAttributes -band [IO.FileAttributes]::Directory) -eq 0 -or
    ($repoAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
  throw 'Canonical-set worktree root is not an ordinary directory.'
}
foreach ($preloadPath in @([IO.Path]::GetFullPath('configs'), $captureHelper)) {
  if (([IO.File]::GetAttributes($preloadPath) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "Canonical-set preload path is a reparse point: $preloadPath"
  }
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $captureHelper).Hash -cne
    '50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866') {
  throw 'Cannot authorize canonical-set no-reparse helper.'
}
. $captureHelper

function Get-S150CanonicalLinesHash {
  param([Parameter(Mandatory=$true)][string[]]$Lines)
  $ordered = [string[]]@($Lines)
  [Array]::Sort($ordered, [StringComparer]::Ordinal)
  $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($ordered -join "`n"))
  $algorithm = [Security.Cryptography.SHA256]::Create()
  try {
    $hash = ([BitConverter]::ToString($algorithm.ComputeHash($bytes))).Replace('-', '')
  } finally { $algorithm.Dispose() }
  [pscustomobject]@{ Lines=@($ordered); Sha256=$hash }
}

function Get-S150CanonicalFileRecord {
  param([Parameter(Mandatory=$true)][string]$Path)
  $full = [IO.Path]::GetFullPath($Path)
  $state = Assert-S150NoReparsePath -PinnedBaseDirectory $repoRoot -TargetPath $full
  if (-not $state.Exists) { throw "Canonical file is absent: $full" }
  $stream = [IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if ($item.PSIsContainer) { throw "Canonical path is not a file: $full" }
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
      $hash = ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '')
    } finally { $algorithm.Dispose() }
    [pscustomobject]@{ Path=$full; Size=[int64]$item.Length; Sha256=$hash }
  } finally { $stream.Dispose() }
}

$artifactLines = foreach ($path in $artifactPaths) {
  $relative = $path.Replace('\','/')
  $record = Get-S150CanonicalFileRecord -Path $path
  '{0}|{1}|{2}' -f $relative,$record.Size,$record.Sha256
}
$artifactSet = Get-S150CanonicalLinesHash -Lines @($artifactLines)

$deltaLines = foreach ($entry in $sourceDeltaOld.GetEnumerator()) {
  $record = Get-S150CanonicalFileRecord -Path $entry.Key.Replace('/','\')
  '{0}|{1}|{2}' -f $entry.Key,$entry.Value,$record.Sha256
}
$scopedSourceDelta = Get-S150CanonicalLinesHash -Lines @($deltaLines)
```

Canonical serialization is uppercase SHA-256, normalized `/` repository-relative paths, ordinal line sort, UTF-8 without BOM, LF joins, and no trailing LF. Persist every line and each resulting hash in the evidence. Independently compare every `ABSENT` old state with `baseline.neutralPathAbsences` or `baselinePathWasAbsentBeforeCreate`, and compare the launcher's old hash with `baseline.pinnedPreState`; a mismatch is a hard stop.

- [ ] **Step 2: Request an independent implementation-safety review**

Give the reviewer the approved design, this plan, scoped diff, helper/tests/fixtures, changed launcher, frozen hashes, and test outputs. Require explicit review of:

- raw-byte order and unchanged S149 call;
- first-failure reasons and timestamp ordering;
- held-handle coherent snapshots;
- exact-empty watcher stderr;
- all-path prevalidation and continuous identity-anchor handoff;
- true `Read/FileShare.Read` terminal proof;
- partial-seal retention and cleanup-only semantics;
- backend mutability classification;
- controlled-only launcher scope and unaffected ordinary launch;
- process fixture identity cleanup;
- absence of identity/live capability, including admitted and baseline-replayed `.git`/`.codegraph` exclusion types/topology, the recorded exact eight-path observed controller/manifest/tracker census, the one exact hash-pinned neutral contract-test exemption, and the unchanged seven-path identity-bearing historical set.

After independently revalidating the ordinary non-reparse `docs` base and exact absent review path, the reviewer creates `docs/s150-successor-neutral-implementation-review.md` with CreateNew, durably flushes it, and never edits it after close. It contains Critical, Important, and Minor findings. Before the terminal verdict, it must contain each of these exact, unique uppercase pin lines, populated from independently recomputed bytes:

```text
REVIEWED_PLAN_SHA256: <64 uppercase hex>
REVIEWED_BASELINE_SHA256: <64 uppercase hex>
REVIEWED_EVIDENCE_SHA256: <64 uppercase hex>
REVIEWED_ARTIFACT_SET_SHA256: <64 uppercase hex>
REVIEWED_SCOPED_DELTA_SHA256: <64 uppercase hex>
```

The exact terminal line is `IMPLEMENTATION_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0` only when clear. It occurs exactly once and is the last non-newline content. Any newly discovered Critical or Important finding at this final immutable stage publishes NO-GO and ends this execution; do not edit/delete the evidence or review path. A future user-approved remediation plan must select fresh versioned evidence/review paths and rerun the affected gates. Never carry a verdict forward across changed bytes.

- [ ] **Step 3: Request an independent evidence/provenance review**

The second reviewer independently recomputes hashes and verifies:

- historical baseline was created before implementation bytes changed;
- all baseline leaves and absences remain exact;
- the immutable offline-audit schema/hash, exact 15-leaf build inventory and no-unknown-leaf proof, pretest census receipt, posttest zero census, admitted and replayed `.git`/`.codegraph` traversal-exclusion records, worktree namespace/receipt/label censuses, exact eight observed versus seven identity-bearing controller/manifest/tracker paths with one hash-pinned neutral test exemption, frozen runtime-root ledger/evidence census, and complete transcript support its PASS/no-live claims;
- frozen Flight 2 files and namespaces remain untouched;
- RED evidence predates each corresponding implementation;
- test/build commands and results are sufficient and internally consistent;
- expected known Go failures are exact and no new failure is hidden;
- all A/B and DLL claims reproduce;
- no identity, manifest, tracker, live runtime receipt, namespace, ledger entry, or live invocation exists; the two explicitly allowed neutral provenance receipts match their pinned schemas and bytes;
- evidence document statements match files and command output.

After independently revalidating the ordinary non-reparse `docs` base and exact absent review path, the reviewer creates `docs/s150-successor-neutral-evidence-review.md` with CreateNew, durably flushes it, and never edits it after close. It contains the same five exact, unique `REVIEWED_*_SHA256` lines and independently recomputed values. It uses the exact terminal line `EVIDENCE_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0` only when clear; the line occurs exactly once and is the last non-newline content. Any newly discovered Critical or Important finding at this final immutable stage publishes NO-GO and ends this execution without editing or deleting frozen artifacts; remediation requires a future plan with fresh versioned paths.

- [ ] **Step 4: Perform final verification from a fresh shell**

Rerun the focused successor Full tests, the post-flight-safe frozen Flight 2 hash/AST audit, expected frozen successor-contract RED, hashes, AST parse, new-source ASCII/no-BOM checks, launcher BOM/non-ASCII preservation checks, `git diff --check`, process/namespace absence checks, and both cryptographically bound reviewer-verdict checks. Reopen and hash all three evidence/review documents. Use one fresh shell for the ordered blocks below.

The fresh-shell behavior/contract core is:

```powershell
$ps = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$fixtureExe = 'tools\sigbypass-mod\build\s150-successor-neutral-output-tests\s150_output_writer_fixture.exe'
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_watcher_envelope_test.ps1' -Section Full
if ($LASTEXITCODE -ne 0) { throw 'Fresh final watcher test failed.' }
& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_output_ownership_test.ps1' `
  -Section Full -FixtureExe $fixtureExe
if ($LASTEXITCODE -ne 0) { throw 'Fresh final output-ownership test failed.' }

$frozen = '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller.ps1'
$frozenTest = '.superpowers\sdd\2026-08-27-s150-capture-generation\s150-flight2-controller-test.ps1'
$frozenSources = [ordered]@{
  $frozen = 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09'
  $frozenTest = 'BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6'
}
foreach ($entry in $frozenSources.GetEnumerator()) {
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $entry.Key).Hash -cne $entry.Value) {
    throw "Frozen Flight 2 hash drifted in final verification: $($entry.Key)"
  }
  $tokens = $null
  $errors = $null
  [void][Management.Automation.Language.Parser]::ParseFile(
    [IO.Path]::GetFullPath($entry.Key), [ref]$tokens, [ref]$errors)
  if (@($errors).Count -ne 0) { throw "Frozen Flight 2 AST parse failed: $($entry.Key)" }
}

$expectedViolations = @(
  'FROZEN_FOUR_LINE_WATCHER','NO_SUCCESSOR_HELPER_PROVENANCE',
  'NO_HELD_WATCHER_IDENTITY_PAIR','NO_CANONICAL_RAW_REVALIDATION',
  'NO_DISTINCT_BACKEND_STDOUT','NO_HELD_OUTPUT_IDENTITY_ANCHORS',
  'QUIET_SAMPLING_IS_NOT_TERMINALITY',
  'ARM_FINAL_WATCHER_FENCE_MISSING'
)
$frozenBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $frozen).Hash
$contractOutput = @(& $ps -NoProfile -ExecutionPolicy Bypass -File `
  'tools\sigbypass-mod\tests\s150_successor_controller_contract_test.ps1' `
  -CandidateController $frozen -Section NeutralContract 2>&1)
if ($LASTEXITCODE -eq 0) { throw 'Frozen Flight 2 unexpectedly passed the final successor contract.' }
$actualViolations = @([regex]::Matches(($contractOutput -join "`n"), '(?m)^VIOLATION ([A-Z0-9_]+)$') |
  ForEach-Object { $_.Groups[1].Value })
if (($actualViolations -join "`n") -cne ($expectedViolations -join "`n")) {
  throw "Final frozen successor-contract census changed: $($actualViolations -join ', ')"
}
$frozenAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $frozen).Hash
if ($frozenBefore -cne 'BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09' -or
    $frozenAfter -cne $frozenBefore) { throw 'Frozen controller drifted during final verification.' }
```

Set `$script:S150OfflineAuditMode = 'ValidateExisting'`, replay the exact Task 6 Step 7 audit block in this same shell, and require its durable byte comparison to pass without writing. Remove that variable afterward. Only after those read-only checks finish, execute the exact canonical artifact-set and scoped-source-delta block from Step 1 verbatim in this same shell. This late recomputation must occur after all tests so a test-side mutation cannot retain a stale review pin. Then run:

```powershell
$finalTextPaths = @(
  'docs\superpowers\plans\2026-08-30-s150-successor-neutral-boundaries.md',
  'docs\s150-successor-historical-baseline.json',
  'docs\s150-successor-neutral-evidence.md',
  'docs\s150-successor-neutral-implementation-review.md',
  'docs\s150-successor-neutral-evidence-review.md'
)
$finalTextReads = [ordered]@{}
foreach ($path in $finalTextPaths) {
  $finalTextReads[$path] = Get-S150AuditTextRecord -Path $path
}
$planHash = [string]$finalTextReads[
  'docs\superpowers\plans\2026-08-30-s150-successor-neutral-boundaries.md'].Record.sha256
$baselineHash = [string]$finalTextReads['docs\s150-successor-historical-baseline.json'].Record.sha256
$evidenceHash = [string]$finalTextReads['docs\s150-successor-neutral-evidence.md'].Record.sha256
$evidenceText = [string]$finalTextReads['docs\s150-successor-neutral-evidence.md'].Text
if ([regex]::Matches($evidenceText, '(?m)^reviewState: REVIEW_PENDING\r?$').Count -ne 1 -or
    $evidenceText -match '(?m)^IDENTITY_NEUTRAL_(?:GO|NO_GO)\b') {
  throw 'Immutable evidence does not have the unique review-pending state.'
}
if ($null -eq $artifactSet -or $null -eq $scopedSourceDelta) {
  throw 'Canonical artifact/delta values were not recomputed in this fresh shell.'
}
$expectedPins = [ordered]@{
  'REVIEWED_PLAN_SHA256' = $planHash
  'REVIEWED_BASELINE_SHA256' = $baselineHash
  'REVIEWED_EVIDENCE_SHA256' = $evidenceHash
  'REVIEWED_ARTIFACT_SET_SHA256' = $artifactSet.Sha256
  'REVIEWED_SCOPED_DELTA_SHA256' = $scopedSourceDelta.Sha256
}
$reviewSpecs = @(
  [pscustomobject]@{
    Path = 'docs\s150-successor-neutral-implementation-review.md'
    Verdict = 'IMPLEMENTATION_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0'
  },
  [pscustomobject]@{
    Path = 'docs\s150-successor-neutral-evidence-review.md'
    Verdict = 'EVIDENCE_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0'
  }
)
foreach ($reviewSpec in $reviewSpecs) {
  $review = [string]$finalTextReads[$reviewSpec.Path].Text
  if ([regex]::Matches($review, '(?m)^REVIEWED_[A-Z_]+_SHA256:.*\r?$').Count -ne $expectedPins.Count) {
    throw "Review has an unexpected or missing pin line: $($reviewSpec.Path)"
  }
  foreach ($pin in $expectedPins.GetEnumerator()) {
    $pattern = '(?m)^' + [regex]::Escape($pin.Key) + ': ([0-9A-F]{64})\r?$'
    $matches = [regex]::Matches($review, $pattern)
    if ($matches.Count -ne 1 -or $matches[0].Groups[1].Value -cne $pin.Value) {
      throw "Review pin mismatch or duplicate: $($reviewSpec.Path) $($pin.Key)"
    }
  }
  $verdictPattern = '(?m)^' + [regex]::Escape($reviewSpec.Verdict) + '\r?$'
  $verdictKey = $reviewSpec.Verdict.Substring(0, $reviewSpec.Verdict.IndexOf(':'))
  $trimmedReview = $review.TrimEnd([char[]]"`r`n")
  $lastBreak = [Math]::Max($trimmedReview.LastIndexOf("`n"), $trimmedReview.LastIndexOf("`r"))
  $lastLine = if ($lastBreak -lt 0) { $trimmedReview } else { $trimmedReview.Substring($lastBreak + 1) }
  if ([regex]::Matches($review, '(?m)^' + [regex]::Escape($verdictKey) + ':.*\r?$').Count -ne 1 -or
      [regex]::Matches($review, $verdictPattern).Count -ne 1 -or $lastLine -cne $reviewSpec.Verdict) {
    throw "Review verdict is not unique and terminal: $($reviewSpec.Path)"
  }
}
foreach ($path in @(
  'docs\s150-successor-neutral-evidence.md',
  'docs\s150-successor-neutral-implementation-review.md',
  'docs\s150-successor-neutral-evidence-review.md'
)) {
  $record = $finalTextReads[$path].Record
  [pscustomobject]@{ Path=$path; Size=$record.size; Sha256=$record.sha256 }
}
```

Every evidence/review byte consumed above comes from the same writer-denying held stream as its size/hash/metadata record after a fresh component-no-reparse admission. Immediately after this block, with no intervening filesystem command, set `$script:S150OfflineAuditMode = 'ValidateExisting'` and replay the exact Task 6 Step 7 audit block one final time. Require its byte-identical audit comparison, final worktree ledger/runtime-receipt/identity-label census, frozen `G:\git\Supervive Revival Project` ledger/runtime-evidence census, retirement/dump namespace equality, required absences, and zero process census to pass; remove the variable. Run no further filesystem or process command before publishing Step 5 status.

Use `superpowers:verification-before-completion`; no earlier output may substitute for this fresh run.

- [ ] **Step 5: Publish the exact terminal neutral status and stop**

Publish `IDENTITY_NEUTRAL_GO` only if all tests and both reviews are GREEN with zero Critical/Important findings. Otherwise publish `IDENTITY_NEUTRAL_NO_GO` with the first decisive failure and stop.

For GO, the handoff must say:

```text
IDENTITY_NEUTRAL_GO; FLIGHT2_IMMUTABLE; NO_SUCCESSOR_IDENTITY; NO_CONTROLLER; NO_MANIFEST; NO_LIVE_ACTION
```

Then stop. Do not continue inline into identity binding.

## Required later plan, deliberately out of scope

A separate user-approved late-binding plan must:

1. Select a realistic same-day verification/review window.
2. Generate exactly one unused label, UUID D/N pair, and intended local date.
3. Collision-check every retirement, dump, receipt, runtime-evidence, and ledger path.
4. Create one new sibling controller and identity-bound controller test without modifying Flight 2.
5. Wire the reviewed neutral helper into RecoverLaunch and Arm, preserving all inherited process, provenance, cleanup, one-use, no-retry, mutation, and stager boundaries.
6. Hold watcher identity handles through admission/cleanup and both Arm checks.
7. Hold launcher terminal leases through durable admission or cleanup; reopen/hold them through Arm.
8. Make the second watcher check the final Arm admission operation immediately before CreateNew `stager-invoked.json` and exactly one stager child.
9. CreateNew an immutable review manifest that pins the historical baseline and independently enumerates every baseline leaf.
10. Pin the exact reviewed successor-helper and changed-launcher hashes in preflight, bootstrap, RecoverLaunch, and Arm; continuously hold their provenance leases across every interval in which their functions or source-derived guarantees are trusted.
11. Rerun identity-affected gates and obtain separate implementation/evidence reviews.
12. Publish an exact immutable offline GO and stop.
13. Await separate exact user authorizations for one RecoverLaunch and, after reviewed fresh admission, one Arm.

No path, label, GUID, date, hash, or controller name for that later candidate is assigned by this neutral plan.
