# S191 E4 Option F — TryActivateAbilityBySourceObject probe arm (BUILT + PRE-FLIGHT, 2026-09-10)

★★★★★ **THIRD activation surface after ByClass (S147 LETHAL) and ByInputID (E4A F1 non-lethal
clean-false). Built + gate-verified + offline-recon'd; UNFLOWN.** Design provenance: multi-agent
workflow `wf_8ab1b821-d54` (8 agents / 4 phases: 4× Understand → Design → 2× adversarial Verify →
Adjudicate; 2.9M subagent tokens, 10min wall clock).

## Why Option F

After E4B refuted the InputID-aware grant (`BP_AuthGiveAbilityWithInputID` impl at RVA
`0x13D4E60` = 9-byte stripped stub, `docs/s191-e4b-RESULT.md`), the InputID→spec map cannot be
populated through the reflected grant surface. Two paths remain to a shim-driven `TryActivate`:

- **Option F: TryActivateAbilityBySourceObject** — matches on `spec.SourceObject` which our
  K_GRANT sets = hero (S191 F3 measured). Wrapper @ base+`0x5297230` (S153 REAL,
  `binds_members.csv:39453`).
- Option E: populate the InputID→spec map by direct offset write (needs offline read of
  `GetAbilityByInputID` impl @ `0x5295330` to identify the map field).

F is cheaper (1 S55 call, one probe run) and BYPASSES the InputID map problem entirely, so it goes
first.

## Signature [M]

`binds_members.csv:39453` (verbatim):

    class,4079,ULokiAbilitySystemComponent,TryActivateAbilityBySourceObject,
        params: SourceObject:UObject*@0x00 (8) |
                bAllowRemoteActivation:bool@0x08 (1, default=true) |
                AbilityClass:TSubclassOf<UGameplayAbility>@0x10 (8, default=nullptr) |
                ReturnValue:bool@0x18 (1)

Total parm size 0x19 bytes (padded to 0x20). Cross-checked against S153 native-UFunction sweep CSV
(`scratchpad/s153_native_ufunction_sweep_v2.csv:10154`) — REAL grade, thunk resolves to
`0x5297230` exactly.

## Offline recon result (mandatory pre-build step, executed)

    python tools/strxref/strxref.py --dump dumps/merged14.dump.exe func 0x5297230

Result: 301 bytes, entry `0x5297230`, `.pdata` EXACT, evidence=`fnptr,prologue,a16`. Full
disassembly shows tail structure:

    0x529734A: call 0x5544FB0   ← delegates to intermediate wrapper
    0x529734F: mov  [r14], al    ← store retBool
    0x529735C: ret

One level deeper: `0x5544FB0` → `0x44280E0`. **NOT `0x4480B30`** (InternalTryActivateAbility, the
ByClass downstream S146 localized WALL P into). ⇒ **BySourceObject reaches activation via a
DIFFERENT downstream than ByClass.** Per the workflow discriminator:

- **HIT on `0x4480B30`** (never observed): grade upgrades to **[M] LIKELY LETHAL**.
- **MISS** (what we got): grade stays **[I]**, Outcome C (E4F succeeds) prior rises to ~30%,
  flight is maximally discriminative.

**⇒ WALL-P LIKELIHOOD IS LOWER THAN THE ORIGINAL [I,strong] PRIOR.** The generalization from S147's
MiniDash ByClass measurement to LMB Selector BySourceObject is via shared eventual downstream, not
via shared immediate call graph. Flight is worth doing before any further Option E work.

## Adjudicated design

Full spec in the workflow's transcript (`~/.claude/…/subagents/workflows/wf_8ab1b821-d54/journal.jsonl`).
Key refutations applied during adjudication:

- **C-1 (VALID)**: WALL-P grade downgraded [I,strong] → [I]. MiniDash class ≠ LMB Selector class;
  lethality generalization is downstream-shared not measured on this ability.
- **C-2 (VALID)**: Pre-build strxref recon (executed, MISS) upgrades or downgrades the grade
  before committing to a launch. Applied.
- **S-1/S-2/S-3 (all VALID)**: E4F must be MUTUALLY EXCLUSIVE with KE4DIRECTGE + KBFE4A + KBFE4B
  via source-level `#error` guards. Each attribution-mixer would drop the minion HP or fault
  BEFORE E4F's pre/post read, destroying attribution. **Enforced by 3 explicit #error guards.**
- **S-5 (already in design)**: SEH does NOT catch FK-32 (FK-10/S131 kill is not a synchronous
  exception). Pre-call marker written BEFORE `CallNativeGuarded` so a 0xDEAD flight preserves
  attribution. **Enforced by ordering.**

## Files (this session)

- `tools/sigbypass-mod/tutorial_launch.cpp` — 3 additions, all behind `#if KBFE4F`:
  - Knob definition `#ifndef KBFE4F / #define KBFE4F 0` at ~line 18457 (before KBFE4A knob)
  - 12 policy `#error` guards at ~line 18604 (after KBFE4B guards)
  - `#if KBFE4F` code block at ~line 24256 (after KBFE4A close, before `result="TARGET_READY"`)
- `tools/sigbypass-mod/build.ps1` — `e4-f` variant at line ~873 (after `e4-b2`)

**KBFE4F=0 truly dead-strips** — verified: all 7 regression `.text` RAW digests BYTE-IDENTICAL
after the edits vs pre-edit HEAD build.

## Gates

Post-build measurement (`python tools/sigbypass-mod/text_digest.py`):

| variant       | RAW               | note                        |
|---------------|-------------------|-----------------------------|
| botai         | b620e0ff3279e673  | UNCHANGED (regression)      |
| play          | 31af7667355f39d1  | UNCHANGED (regression)      |
| e4            | 69197ce6e9e38dda  | UNCHANGED                   |
| e4-a          | 2d7efa4cde249f2e  | UNCHANGED                   |
| e4-b          | 39f1ae3c41fbc1ad  | UNCHANGED                   |
| e4-b2         | 5827bc3863157d25  | UNCHANGED                   |
| e4-directge   | 404ad6c7cdf44a8c  | UNCHANGED (⚠ pre-existing drift from `docs/s191-e4-flight3-RESULT.md`'s recorded `377f263062790979`; NOT caused by E4F, present at 0801154 HEAD pre-E4F rebuild) |
| **e4-f**      | **1f51942a2b8d164a** | **NEW, DISTINCT**        |

`verify_dll.py` VERDICT PASS on `tutorial_launch_e4_f.dll` (229,888 bytes, KERNEL32-only, no C++
exception machinery, no CRT). `--dupes` clean for e4-f (2 pre-existing HAZARD groups flagged —
`play_nopimutex ≡ play_strictroot` since S112 and `s148_damage_calibration_test ≡ .final` since
S148 — neither involves e4-f).

## Flight expectations — 6-outcome discriminator table

| Outcome | faulted | retBool | elapsedMs | dHP | Interpretation | Prior |
|---|---|---|---|---|---|---|
| **A** | (no result line) | — | — | — | WALL-P kill. Process exits 0xDEAD 50-70s post-CALL_ISSUE. Pre-call marker is the receipt. UPGRADES grade to [M]. | ~30-40% |
| **B** | YES | 255 | any | 0 | SEH-caught fault. Localized to E4F (bad param packing or stale AbilityClass). Re-fly after checking ParamOffset. | ~5% |
| **C** | no | 1 | any | <0 | **E4F PREDICATE MET.** Direct callable damage path works. Full E4 predicate met via direct call, no OS input needed. Adapt into BTT_CastSpell replacement to unlock bot-side too. | ~25-35% |
| **D** | no | 1 | any | 0 | Cast fired but no damage this frame. Try Sleep(50) pre-postHP, or LMB selector needs targeting data. | ~10% |
| **E-fast** | no | 0 | <100 | 0 | **STRUCTURAL FINDING**: pre-downstream early-out, BySourceObject-analogue of R-S191-h. New WALL-P escape hatch. Grade as POSITIVE. | ~10-15% |
| **E-slow** | no | 0 | >100 | 0 | Downstream gate refused. Reconcile against K_GRANT marker's spec.SourceObject. | ~5% |

⚠ **Every outcome (A through E) is INFORMATIVE — E4F is a maximally-discriminative single-call
probe.** Outcome A preserves attribution via the pre-call marker (0xDEAD is not SEH-catchable
per FK-10/S131 but the marker line lands BEFORE the fatal call).

## Flight recipe

    # 1. Stage tutorial world normally: gft → fo → sp
    # 2. Inject e4-f DLL as the probe (RM_BOTFIGHT with KBFE4=1 + KBFE4F=1)
    # 3. Read docs/tutorial-launch-marker.txt for the [E4F] pre-activate + E4F_CALL_ISSUE
    #    + E4F_RESULT chain.
    # 4. If Outcome A: crashwatch.log will show 0xDEAD exit ~50-70s after CALL_ISSUE. Pre-call
    #    marker is the receipt.

Log tag: `[E4F]`. All 3 marker lines are prefixed with `[E4F]` for easy grep.

## Rules banked (design-derived — will be updated on flight)

- **R-S191-m [pending flight]**: `TryActivateAbilityBySourceObject` @ `0x5297230` reaches
  activation via `0x5544FB0` → `0x44280E0`, a DIFFERENT downstream than `TryActivateAbilityByClass`
  → `0x4480B30`. Offline recon MISS on the shared-downstream discriminator downgrades the WALL-P
  lethality prior from [I,strong] to [I].
- **R-S191-n [methodology]**: A three-surface activation family (ByClass / ByInputID / BySourceObject)
  requires independent flights because each has a distinct wrapper, distinct downstream, and
  distinct WALL-P grade. Do NOT co-fire them in one arm — attribution collapses. E4F's 3 mutex
  `#error` guards (KBFE4F incompatible with KBFE4A/KBFE4B/KE4DIRECTGE) encode this at source.
- **R-S191-o [pre-flight discipline]**: `strxref func <impl_rva>` before spending a launch on any
  reflected activation call is a 30-second, zero-launch grade adjustment that can shift the
  lethality prior by 10-20%. Do this for every future WALL-P-family probe target.
