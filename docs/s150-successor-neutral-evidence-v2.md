# S150 successor-neutral v2 - offline evidence

reviewState: REVIEW_PENDING

This document records the offline execution of the v2 remediation plan
`docs/superpowers/plans/2026-08-31-s150-successor-neutral-boundaries-v2.md`. It states no GO/NO-GO
verdict; that is decided by the two independent reviews plus final verification. No live action was
taken. All hashes are uppercase SHA-256.

## 1. What v2 corrected (verification tooling only)

The v1 run reached a preserved NO-GO because its offline-audit identity-literal scan rejected
pre-existing, non-successor dated comments in `configs/launch-redirect.ps1`
(`2026-06-29`, `2026-08-04`, `2026-08-05`, `2026-08-14`) that the LauncherSource gate requires be
retained - an internal contradiction. v2 changes ONLY the audit verification tooling:

1. Launcher identity/forbidden-path scan is now introduced-only (current literals/matches minus the
   pinned pre-edit launcher's); the six new sources are still scanned in full.
2. `$allowedIdentityLiterals` gains `20260826` / `2026-08-26` - the S149 historical flight date that
   legitimately appears in the watcher test's SHA-pinned historical-receipt reconstruction. No source
   byte changes.
3. Step 3 failing-package parse changed from a greedy regex to a tab split.
4. The audit's two `git diff --check` calls pass `-c core.safecrlf=false` (suppresses the benign
   `LF will be replaced by CRLF` advisory that PS 5.1 turns into a terminating error; autocrlf stays
   true so the launcher whitespace check still exits 0).

No source, build input, or substrate byte changed.

## 2. Frozen inputs (unchanged; re-verified at execution start)

| input | size | sha256 |
|---|---|---|
| v1 plan `docs/superpowers/plans/2026-08-30-s150-successor-neutral-boundaries.md` | 209086 | `8B886E59DAF0D99D...` (full re-verified `8B886E59...874FE`) |
| v2 plan `docs/superpowers/plans/2026-08-31-s150-successor-neutral-boundaries-v2.md` | 62012 | `46FD39871D08C516B55361FC2CCC351AE3CE284C35284140B91155DD21CA51A2` |
| design `docs/superpowers/specs/2026-08-29-s150-successor-watcher-output-ownership-design.md` | 29410 | `07C0CF46D123E911...` |
| historical baseline `docs/s150-successor-historical-baseline.json` | 90523 | `BC4C2E1906CE03C04DA10C86BA85F2533DB3DEF6486AF55C0418E93215C1925D` |
| baseline receipt `docs/s150-successor-historical-baseline.receipt.json` | 439 | `57668C75C23448165FA5963C7D12F512C9D37C5DC976D391757FAA1EF2D03D47` |
| Flight 2 controller `.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller.ps1` | - | `BA6DE0EC5E63CF5064B254EB4BE008986746B377434D391295A8E22D3664BC09` |
| Flight 2 controller test `.superpowers/sdd/2026-08-27-s150-capture-generation/s150-flight2-controller-test.ps1` | - | `BE7E6BF6C1085F3F8863ADD31334C34F68E8740DC26FDC606A05A2D0BEE1EAD6` |
| capture helper `configs/s150-capture-generation.ps1` | - | `50EE8181516D5EBA5698B50FD16942A75A4856FE5DC98F7DDD2275767B181866` |

The v1 historical baseline is the immutable substrate: it is the only surviving record of the
pre-edit launcher (`A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D`, 37367 bytes,
BOM `EF BB BF`, 425 CRLF + 222 LF). Its `pinnedPreState` launcher record equals that value and its
`baselinePathWasAbsentBeforeCreate` = True; every `ABSENT` scoped-delta old state matches
`neutralPathAbsences` or `baselinePathWasAbsentBeforeCreate` (cross-check PASS).

## 3. Corrected offline audit (durable v2 artifact)

- Path `docs/s150-successor-neutral-offline-audit-v2.json`, size 23747, sha256
  `D3A38C7DEFB88E77A89C7769F370F3594C08AB81B54BD46D7F2034F6C06BB1AA`, schema
  `s150-successor-neutral-offline-audit/v2`.
- Written once with `CreateNew`, `Flush($true)`, durable held-stream reopen + byte-compare + hash.
- Records `status = PASS`, `successorIdentityCreated = $false`, `productionInvocationCount = 0`,
  `liveAuthorization = $false`.
- Preview (writes nothing) reproduced the same 23747-byte audit object (hash differs only by the
  embedded `recordedUtc`); the durable CreateNew value is above.

### Corrected identity-scan result (introduced-only launcher)

- Pre-edit launcher identity literals = `{2026-06-29, 2026-08-04, 2026-08-05, 2026-08-14}`.
- Current launcher (`8B01999B64C843C51336F8CDC99A0A3CB953837A289092981EA415CC0FF8A24C`, 38916 bytes)
  identity literals = the same four. Current MINUS pre-edit = EMPTY. The S150 edit introduced no
  identity literal, and no forbidden-path category matches either launcher.
- Negative controls (pre-registered, re-verified by the implementation-safety reviewer): a new flight
  label `s150captureflight3-20270115-101010`, a new GUID, a new date `2027-03-09`, and a new-source
  GUID are each caught (introduced/non-allowed), so the corrected scan is not vacuously passing.

## 4. Launcher edit (three reviewed regions; unchanged branches)

Whole-file replacement map (pre-edit -> current), verified byte-exact by the LauncherSource gate:

| region | oldLen | newLen | oldSha | newSha |
|---|---|---|---|---|
| ControlledPreflight | 124 | 1279 | `81D08B14...` | `E6E9C2F1751C53657BFC101DA73470DF8BB9F967F29D21D56E3B0057000A58BC` |
| ControlledBackendStart | 219 | 437 | `A04B8C10...` | `A87AB8A7CC07727CFFC9579B547F79651A2F5790B6485291A47B7157639D9DCA` |
| ControlledCertificateDiagnostics | 353 | 529 | `E7BD3069...` | `9B1F34EC595E0EA8CC8A09C7CA8221342BDC8CFC3795282490DA95D8D3CFDCC2` |

Canonical replacement-map hash `24AD481B09BC5D6F075AEFA7D380DDA821A3E6D34AAB93F5CAEF8C8190C49EA5`.
LauncherLoadIsolation and LauncherSource both PASS. The launcher retains its UTF-8 BOM `EF BB BF`
and its decoded non-ASCII code-point census of 8. `git -c core.safecrlf=false diff --check` on the
launcher exits 0 with no whitespace defect. The added lines use only `$s150*` variables/functions and
the literal `s150-successor-evidence.ps1`; no date, GUID, or flight-label literal is added.

## 5. Sources (helper, tests, fixtures, launcher)

| path | size | sha256 |
|---|---|---|
| configs/s150-successor-evidence.ps1 | 28494 | `D9AA3C2ED0EC28E2A3465B29281FFE9CED47567CF114AF345459E80C4E917635` |
| tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1 | 28589 | `34FB06EC34C714B7578B750CBC8209CCDA2E0CEA932E5C405D442FAE75C6C77D` |
| tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1 | 61809 | `D7E69AA65D61694536281C4B860F1B728072D1BD0E37C728313F87D565D89AB0` |
| tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1 | 7007 | `BFF7F84034827007F0E227346F823F6E545D64185E755A1CB714E185A8303DF5` |
| tools/sigbypass-mod/tests/fixtures/s150_output_writer_fixture.cpp | 7766 | `1D58CA16705BA5622C755DB4B3076E0D355077F4A22F2D306C8566CCF5710606` |
| tools/sigbypass-mod/tests/fixtures/s150_output_fake_launcher.ps1 | 2141 | `665A237B785EB42A4B2B358285F3FAB006744AF060A12E0D6EE93A9B4BD57070` |
| configs/launch-redirect.ps1 | 38916 | `8B01999B64C843C51336F8CDC99A0A3CB953837A289092981EA415CC0FF8A24C` |

The controller-contract test's output format was corrected during v1 execution to emit one
`VIOLATION <ID>` line per violation (the plan parses `(?m)^VIOLATION ([A-Z0-9_]+)$`); its bytes are
not pinned by the baseline (it is recorded only as `neutralControllerContractTestPathWasAbsent=True`).

## 6. GREEN gates (exact commands + results)

- **Ten PowerShell 5.1 tests** (watcher `-Section Full`; output `-Section Full -FixtureExe <fixture>`;
  `s150_capture_generation`, `s149_stage_plan`, `s149_stager_safety`, `s149_bind_gate`,
  `s149_compile_policy`, `s149_bind_contract`, `s148_build_contract`, `s147_input_plan`): 10/10 exit 0.
- **Successor controller contract** (`-CandidateController <frozen Flight 2> -Section NeutralContract`):
  RED, exit 1, exactly 8 lines matching `^VIOLATION [A-Z0-9_]+$` in order: FROZEN_FOUR_LINE_WATCHER,
  NO_SUCCESSOR_HELPER_PROVENANCE, NO_HELD_WATCHER_IDENTITY_PAIR, NO_CANONICAL_RAW_REVALIDATION,
  NO_DISTINCT_BACKEND_STDOUT, NO_HELD_OUTPUT_IDENTITY_ANCHORS, QUIET_SAMPLING_IS_NOT_TERMINALITY,
  ARM_FINAL_WATCHER_FENCE_MISSING. Frozen Flight 2 hash `BA6DE0EC...` and AST unchanged before/after.
- **Go behavior**: `go test -C server ./internal/capture -run CaptureGeneration -count=1` ok;
  `... -count=10` ok; full `./internal/capture` ok. Go `go1.26.4 windows/amd64`.
- **C++ behavior**: `s147_natural_state_test.exe`, `s148_damage_calibration_test.exe`,
  `s149_bind_bootstrap_test.exe` each print `PASS s14x_...` (compiled `clang++ -std=c++17 -O2`,
  clang 21.1.6).
- **Repository-wide Go baseline (corrected tab-split parse)**: `go test -C server ./... -count=1`
  exits 1; the only `--- FAIL:` names are `TestArmQueueEmptyIsASingleVariableControl`,
  `TestArmQueueRespectsQueueAllowlist`, `TestCancelArmClearsTheMatch`; the only failing package
  (parsed by tab split) is `supervive-revival/server/internal/interactive`; 8 packages `ok`, three
  `[no test files]`. No S150/capture/new-test failure.

## 7. Reused build outputs (byte-verified in v1; re-validated in place)

- Backend A `server/build/s150-successor-neutral-backend-a/ags.exe` and B `-backend-b/ags.exe`:
  byte-identical, 11051520 bytes, sha256
  `115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA`, equal to active `server/ags.exe`.
- Seven DLLs `text_digest.py --full --verify`: `parsed 7 file(s)`; RAW/VSIZE `.text` occurrences
  S149 RAW `f7765063...`x2, S149 VSIZE `eb405ecd...`x2, S148 RAW `c46fb598...`x2, S148 VSIZE
  `91cbea32...`x2, natural `366e8ef0...`x1, botai `5e47c13c...`x1, play `9bc10a45...`x1. `--dupes`:
  RAW 0 HAZARD/0 DEGENERATE, VIRTUALSIZE 0 HAZARD/0 DEGENERATE. `verify_dll.py`: 7 `VERDICT: PASS`.
  (The two recovery-a/recovery-b DLL copies are whole-file distinct by PE-header timestamp but
  `.text`-identical; byte-identity is asserted only for `ags.exe`.)
- Three behavior exes: s147 140288 / `E5DF2F73...`, s148 155136 / `A0932D42...`,
  s149 147456 / `AC337B58...`.

## 8. Provenance receipts, inventory, census

- Offline build inventory `tools/sigbypass-mod/build/s150-successor-neutral-output-tests/offline-build-inventory.json`,
  8285 bytes, `76AAC08CE896CA53B8128EA20025343D5C3B7492057DCEB8CD1C29D767DB700D` (exact 15-leaf set,
  schema `s150-successor-neutral-offline-build-inventory/v1`).
- Pretest process census `.../pretest-process-census.json` 601 / `DB40A4F0...`; receipt
  `.../pretest-process-census.receipt.json` 486 / `3A0721B4...` (schema
  `s150-successor-neutral-pretest-process-census[-receipt]/v1`); all ten protected counts recorded 0.
- Fixture exe `.../s150_output_writer_fixture.exe` 129536 / `7A1B559B...`.
- Posttest process census (audit): all ten protected/fixture process names 0.

## 9. No-identity / no-live proof

- The corrected audit re-asserts: no successor retirement/dump namespace beyond the two historical
  ones (`s150captureflight1-20260827-164413`, `s150captureflight2-20260829-192619`); no worktree S149
  ledger JSON, runtime-receipt, or S150 flight-label path beyond the baseline census; the whole-worktree
  S150 controller/manifest/tracker path census equals the seven historical identity-bearing paths plus
  the one exempt neutral test `tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1`;
  the `.git`/`.codegraph` traversal exclusions match the baseline topology; and the frozen runtime root
  `G:\git\Supervive Revival Project` (its `docs`, `docs\s149-ledgers`) has zero ledger JSON and zero
  `fk24-stage-s150captureflight*` runtime evidence.
- No production launcher/backend/game/watcher/injector/stager/`RecoverLaunch`/`Arm` invocation
  occurred; the audit's only external calls are two read-only `git diff --check` and two static
  launcher test sections. `OFFLINE GO` is not used and no live authorization exists.

## 10. Hard-stop checks

Every hard-stop check ran and NONE fired: frozen-input hashes held; all fresh v2 output paths were
absent before their gate; no reparse point or unexpected process; the scoped-delta old-state
cross-check passed; the corrected audit substrate/census/inventory/LauncherSource checks passed; the
posttest process census was zero.

## 11. Preliminary review findings (non-blocking)

Two independent read-only preliminary reviewers reported: implementation-safety
`CRITICAL=0 IMPORTANT=0 MINOR=2`; evidence/provenance `CRITICAL=0 IMPORTANT=0 MINOR=0`. The two MINOR
observations are informational and require no mutation: (a) the introduced-only scan is a whole-file
set/boolean, so it cannot flag a successor-semantic reuse of a string already present verbatim in the
pre-edit launcher - compensated by the LauncherSource AST-hash gate that constrains the launcher to
pre-edit + the reviewed three-region map, and not triggered by the actual edit (introduced set empty);
(b) allow-list entries are bare literals permitted anywhere, the same coarseness already accepted for
the S150 flight dates, and empirically `20260826`/`2026-08-26` occur among the new sources only in the
watcher test's SHA-pinned S149 receipt path. Neither waives any acceptance criterion.

## 12. Canonical artifact set

Serialization: uppercase SHA-256, `/`-normalized repo-relative paths, ordinal line sort, UTF-8
without BOM, LF joins, no trailing LF. It excludes the evidence and review files.

```
configs/launch-redirect.ps1|38916|8B01999B64C843C51336F8CDC99A0A3CB953837A289092981EA415CC0FF8A24C
configs/s150-successor-evidence.ps1|28494|D9AA3C2ED0EC28E2A3465B29281FFE9CED47567CF114AF345459E80C4E917635
docs/s150-successor-historical-baseline.json|90523|BC4C2E1906CE03C04DA10C86BA85F2533DB3DEF6486AF55C0418E93215C1925D
docs/s150-successor-historical-baseline.receipt.json|439|57668C75C23448165FA5963C7D12F512C9D37C5DC976D391757FAA1EF2D03D47
docs/s150-successor-neutral-offline-audit-v2.json|23747|D3A38C7DEFB88E77A89C7769F370F3594C08AB81B54BD46D7F2034F6C06BB1AA
server/build/s150-successor-neutral-backend-a/ags.exe|11051520|115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA
server/build/s150-successor-neutral-backend-b/ags.exe|11051520|115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA
tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests/s147_natural_state_test.exe|140288|E5DF2F733B61F4968DBD301BE003F64484F2CE4418B85F2E0CE81CA5B50A4F94
tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests/s148_damage_calibration_test.exe|155136|A0932D42CD173C0FD9B1FC8DD1AACD2D6A9576A362A912349F5686D5404F747D
tools/sigbypass-mod/build/s150-successor-neutral-behavior-tests/s149_bind_bootstrap_test.exe|147456|AC337B588980E7004858AB157B3CF34F3856097E7338795A31C143F4A9DA9183
tools/sigbypass-mod/build/s150-successor-neutral-output-tests/offline-build-inventory.json|8285|76AAC08CE896CA53B8128EA20025343D5C3B7492057DCEB8CD1C29D767DB700D
tools/sigbypass-mod/build/s150-successor-neutral-output-tests/pretest-process-census.json|601|DB40A4F0E4324300ECF2B8602C61067AAC79C4B5F1551AF44ED2B95422BBD213
tools/sigbypass-mod/build/s150-successor-neutral-output-tests/pretest-process-census.receipt.json|486|3A0721B438DA256B2ED166D7A0E96BA039571C84B2BF7FFD141BD91B342F33BC
tools/sigbypass-mod/build/s150-successor-neutral-output-tests/s150_output_writer_fixture.exe|129536|7A1B559BCA20696CDE6CF67E54072CCDE1B2931B89A6624F2FEEFC10B4BD3978
tools/sigbypass-mod/build/s150-successor-neutral-recovery-a/tutorial_launch_botfight_bind_only.dll|225280|ADEA0C34396A10EBC746806EE88C40DBCCF8CCB481BFD2F0DAB61DD6C70D5B45
tools/sigbypass-mod/build/s150-successor-neutral-recovery-a/tutorial_launch_botfight_damage_self_cal.dll|221696|3373C88608088702FC65DB7B30B6BA1C9716D5597A36FFA7C2964C28CA5A0F64
tools/sigbypass-mod/build/s150-successor-neutral-recovery-b/tutorial_launch_botfight_bind_only.dll|225280|4A2B1FA0F9902BA269D68042D874655216629DF967569683865285F29B5B0EAF
tools/sigbypass-mod/build/s150-successor-neutral-recovery-b/tutorial_launch_botfight_damage_self_cal.dll|221696|F0D44E1F8AC0CC513BE26775A554CCFA058DAB726CCCFF886E8A28269B11FFD7
tools/sigbypass-mod/build/s150-successor-neutral-regression-botai/tutorial_launch_botai.dll|176128|74A0431098AF1066663ACA23B822A7F086AAF925E60E735AC56E3BEB38D1723E
tools/sigbypass-mod/build/s150-successor-neutral-regression-natural/tutorial_launch_botfight_castalive_dash_mana10_cdocharge1_naturalinput.dll|262144|09F0FAAC5929CAA094F39D2C77FB131CF74F6819D0C5CC3E2E60BDB9AC4BB434
tools/sigbypass-mod/build/s150-successor-neutral-regression-play/tutorial_launch_play.dll|238080|57EA5AE9506B68A1FD50B0F7B79D92120FA34810C5713AB3105BAD78586E2003
tools/sigbypass-mod/tests/fixtures/s150_output_fake_launcher.ps1|2141|665A237B785EB42A4B2B358285F3FAB006744AF060A12E0D6EE93A9B4BD57070
tools/sigbypass-mod/tests/fixtures/s150_output_writer_fixture.cpp|7766|1D58CA16705BA5622C755DB4B3076E0D355077F4A22F2D306C8566CCF5710606
tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1|7007|BFF7F84034827007F0E227346F823F6E545D64185E755A1CB714E185A8303DF5
tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1|61809|D7E69AA65D61694536281C4B860F1B728072D1BD0E37C728313F87D565D89AB0
tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1|28589|34FB06EC34C714B7578B750CBC8209CCDA2E0CEA932E5C405D442FAE75C6C77D
```

ARTIFACT_SET_SHA256 = `DEC884A5B1FB7B21C41B8E4A4C72B51DC82B882EDD951A9C4233ADB309A8001B`

## 13. Canonical scoped source delta

```
configs/launch-redirect.ps1|A07631BB953E2D3187126BA11B179A2461A1493213DAD46645E50B02CA8E7B2D|8B01999B64C843C51336F8CDC99A0A3CB953837A289092981EA415CC0FF8A24C
configs/s150-successor-evidence.ps1|ABSENT|D9AA3C2ED0EC28E2A3465B29281FFE9CED47567CF114AF345459E80C4E917635
docs/s150-successor-historical-baseline.json|ABSENT|BC4C2E1906CE03C04DA10C86BA85F2533DB3DEF6486AF55C0418E93215C1925D
docs/s150-successor-historical-baseline.receipt.json|ABSENT|57668C75C23448165FA5963C7D12F512C9D37C5DC976D391757FAA1EF2D03D47
tools/sigbypass-mod/tests/fixtures/s150_output_fake_launcher.ps1|ABSENT|665A237B785EB42A4B2B358285F3FAB006744AF060A12E0D6EE93A9B4BD57070
tools/sigbypass-mod/tests/fixtures/s150_output_writer_fixture.cpp|ABSENT|1D58CA16705BA5622C755DB4B3076E0D355077F4A22F2D306C8566CCF5710606
tools/sigbypass-mod/tests/s150_successor_controller_contract_test.ps1|ABSENT|BFF7F84034827007F0E227346F823F6E545D64185E755A1CB714E185A8303DF5
tools/sigbypass-mod/tests/s150_successor_output_ownership_test.ps1|ABSENT|D7E69AA65D61694536281C4B860F1B728072D1BD0E37C728313F87D565D89AB0
tools/sigbypass-mod/tests/s150_successor_watcher_envelope_test.ps1|ABSENT|34FB06EC34C714B7578B750CBC8209CCDA2E0CEA932E5C405D442FAE75C6C77D
```

SCOPED_DELTA_SHA256 = `75CAF397C8BCC10968E387A05FF8DE5F45BB22F5D9DC0371C2A6DA8AB2FA23D6`

Every `ABSENT` old state matches `baseline.neutralPathAbsences` (or, for the baseline itself,
`baselinePathWasAbsentBeforeCreate = True`); the launcher old hash equals `baseline.pinnedPreState`.
This document is immutable from creation; any needed correction requires a fresh evidence/review cycle.
