# S150 successor-neutral v2 - evidence/provenance review

Independent evidence/provenance review of the v2 remediation for `docs/superpowers/plans/2026-08-31-s150-successor-neutral-boundaries-v2.md`. All hashes below were independently recomputed in the worktree and matched. No file other than this review was written.

## Findings

S150 successor-neutral v2 -- independent evidence/provenance review (FINAL)
Scope: read-only recomputation and falsification of the frozen v2 offline remediation.
Worktree: C:\Users\eastr\.codex\worktrees\78d0\Supervive Revival Project (G:\... never touched).

AREA 1 -- Frozen inputs unchanged: PASS
  plan boundaries 2026-08-30...boundaries.md    = 8b886e59... (starts 8B886E59) MATCH
  design 2026-08-29...watcher-output-ownership-design.md = 07c0cf46... (starts 07C0CF46) MATCH
    (note: two 2026-08-29 *design.md exist; the referenced one is the successor-watcher-output-ownership
     design at 07C0CF46; the zero-runtime-recovery-design.md is a different, non-referenced file 99ab86db..)
  baseline s150-successor-historical-baseline.json = bc4c2e19...15c1925d FULL MATCH
  baseline receipt .receipt.json                = 57668c75... (starts 57668C75) MATCH
  flight2 controller s150-flight2-controller.ps1 = ba6de0ec...3664bc09 FULL MATCH
  controller-test s150-flight2-controller-test.ps1 = be7e6bf6... (starts BE7E6BF6) MATCH

AREA 2 -- Reused build outputs: PASS
  server/build/...backend-a/ags.exe, ...backend-b/ags.exe, server/ags.exe:
    all three size=11051520 and sha256=115D0999C247DFD3FC107FBB9BEE2F8C130FC0D5EC00AB01FC3D1AB106A895DA (byte-identical).
  text_digest.py --full --verify (7 dlls): "parsed 7 file(s)". RAW/VSIZE occurrences observed:
    RAW f7765063 x2, VSIZE eb405ecd x2, RAW c46fb598 x2, VSIZE 91cbea32 x2,
    RAW 366e8ef0 x1, RAW 5e47c13c x1, RAW 9bc10a45 x1 -- all as specified.
  text_digest.py --dupes: RAW 0 HAZARD/0 DEGENERATE ARM; VIRTUALSIZE 0 HAZARD/0 DEGENERATE ARM.
  verify_dll.py: exactly 7 "VERDICT: PASS"; all report no C++ exception machinery, no CRT import.
  Observation (not a finding): recovery-a and recovery-b dll full-file sha256 differ (build metadata),
    but their .text RAW/VSIZE digests are pairwise identical -- the reuse claim rests on .text, which holds.
    All 7 dll full-file sha256s (incl. recovery-b 4a2b1fa0.. and f0d44e1f..) appear in the evidence doc.

AREA 3 -- Go baseline (corrected): PASS
  go test -C server ./... -count=1 -> exit nonzero (EXIT=1).
  Exactly 3 "--- FAIL:" names: TestArmQueueRespectsQueueAllowlist, TestArmQueueEmptyIsASingleVariableControl,
    TestCancelArmClearsTheMatch. Parsed FAIL<tab>pkg entries: count=1, only supervive-revival/server/internal/interactive.
  Every other package ok or [no test files]. No hidden/new failure.

AREA 4 -- Contract RED: PASS
  s150_successor_controller_contract_test.ps1 -CandidateController <flight2-controller> -Section NeutralContract
    -> exit 1, exactly 8 ^VIOLATION [A-Z0-9_]+$ lines, in order:
    FROZEN_FOUR_LINE_WATCHER, NO_SUCCESSOR_HELPER_PROVENANCE, NO_HELD_WATCHER_IDENTITY_PAIR,
    NO_CANONICAL_RAW_REVALIDATION, NO_DISTINCT_BACKEND_STDOUT, NO_HELD_OUTPUT_IDENTITY_ANCHORS,
    QUIET_SAMPLING_IS_NOT_TERMINALITY, ARM_FINAL_WATCHER_FENCE_MISSING.

AREA 5 -- Audit-v2 + inventory + census: PASS
  audit-v2 json: size=23747, sha256=D3A38C7DEFB88E77A89C7769F370F3594C08AB81B54BD46D7F2034F6C06BB1AA;
    schema="s150-successor-neutral-offline-audit/v2", status="PASS",
    successorIdentityCreated=false, productionInvocationCount=0, liveAuthorization=false.
  offline-build-inventory.json: size=8285, sha256=76AAC08C..., files array len=15.
  pretest-process-census.json: size=601, sha256=DB40A4F0E4324300ECF2B8602C61067AAC79C4B5F1551AF44ED2B95422BBD213;
    receipt (size=486, sha256=3A0721B438DA256B2ED166D7A0E96BA039571C84B2BF7FFD141BD91B342F33BC)
    attests censusSize=601 and censusSha256=DB40A4F0... -- receipt matches census. All census counts = 0.

AREA 6 -- No identity/live: PASS
  Namespaces: only historical S150 capture-generation SDD dir 2026-08-27; dump dirs are the two
    historical S150 captures (20260827, 20260829) plus the pre-existing S149 historical (20260826,
    explicitly the S149 flight date per evidence). No NEW successor retirement/dump namespace created.
  No worktree S149 ledger JSON / runtime-receipt / new S150 flight-label path (find returned nothing).
  Frozen census counts 0 for ags, SUPERVIVE-Win64-Shipping, usmapdump, go, inject, crashpad_handler,
    s150_output_writer_fixture, s147/s148/s149 test fixtures.
  Live falsification: Get-Process for all game/injection/fixture binaries returns 0 each.

AREA 7 -- Evidence internal consistency: PASS
  docs/s150-successor-neutral-evidence-v2.md: exactly one "reviewState: REVIEW_PENDING" line;
    zero lines beginning IDENTITY_NEUTRAL_GO / IDENTITY_NEUTRAL_NO_GO.
  Evidence recomputed sha256 = ef8f1a5f1c94153fb2e6951371eafbc06eae69a29b62f17f06fa34a0c518682b.
  Evidence cites the same 3 failing test names, the only failing package (interactive), and all 8
    contract violations (one each); all enumerated hashes/claims match this reviewer's recomputation.

Writer pin pre-check (read-only): all five pins recompute and match the writer's embedded literals --
  PLAN 46FD3987 (v2 plan), BASELINE BC4C2E19, EVIDENCE EF8F1A5F, ARTIFACT_SET DEC884A5, SCOPED_DELTA 75CAF397.

Result: zero Critical, zero Important, zero Minor issues. All seven review areas independently reproduced.

## Cryptographic pins (independently recomputed)

REVIEWED_PLAN_SHA256: 46FD39871D08C516B55361FC2CCC351AE3CE284C35284140B91155DD21CA51A2
REVIEWED_BASELINE_SHA256: BC4C2E1906CE03C04DA10C86BA85F2533DB3DEF6486AF55C0418E93215C1925D
REVIEWED_EVIDENCE_SHA256: EF8F1A5F1C94153FB2E6951371EAFBC06EAE69A29B62F17F06FA34A0C518682B
REVIEWED_ARTIFACT_SET_SHA256: DEC884A5B1FB7B21C41B8E4A4C72B51DC82B882EDD951A9C4233ADB309A8001B
REVIEWED_SCOPED_DELTA_SHA256: 75CAF397C8BCC10968E387A05FF8DE5F45BB22F5D9DC0371C2A6DA8AB2FA23D6

EVIDENCE_REVIEW_VERDICT: GO; CRITICAL=0; IMPORTANT=0