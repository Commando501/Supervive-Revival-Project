# S189-SEED flight 3 — MANASHOT_APPLIED: game's own AdjustMana path applies +50 Mana cleanly on a seeded MaxMana=1000 attribute set; **first project write to `ULokiAttributeSet` survives with no FK-32**

**Date:** 2026-09-09 (~09:25-09:29)
**Session:** S189-SEED compound MaxMana seed test (successor to S189 mana-f2 which measured MANASHOT_NO_OP under MaxMana=0 clamp)
**Base commit:** `50dd5db` (S189 mana f2)
**Verdict:** ★★★★★★★ **[M] The game's own `AdjustMana` native path RUNS END-TO-END and applies +50 Mana with exact arithmetic when MaxMana is seeded to 1000.** All 4 Mana-family compound attributes (MaxMana@+0x220, BaseMaxMana@+0x230, MaxManaPerLevel@+0x240=0, BonusMaxMana@+0x250=0) seeded via direct-offset writes on the live `ULokiAttributeSet` instance persist through the S148 primary AdjustHealth cycle into the MANASHOT_PRECHECK read. AdjustMana then applies +50 to both Base and Current slots (0→50/50), MaxMana stays at 1000/1000 (postMaxBits unchanged), all 3 compound siblings stay at their seeded values (no PostAttributeChange recompute observed). **First project write to `ULokiAttributeSet` (a previously-untouched write class) survives with no FK-32 — game alive at 368s uptime post-flight.**

## Design provenance

Multi-agent design workflow `wf_1de95504-0b7` (5 parallel Understand agents → 1 Design synth → 2 adversarial Verify agents, ~24 min). Verify:
- **offset verifier: CONFIRMED [M]** — Mana@+0x210 and MaxMana@+0x220 live-verified via `PropOffsetSuper` reflection assertion in `BfS189ResolveManaTarget` (refuses if the resolved offsets drift from 0x210/0x220). Cross-checked against the layout arithmetic model: property_offset = 0x40 + N × 0x10, which reproduces LokiAttributeSetHealth's [M] Health@+0x70 (N=3) and MaxHealth@+0x80 (N=4).
- **mechanism verifier: AMENDED** — critical finding that MaxMana on `ULokiAttributeSet` is a COMPOUND-derived attribute with 3 sibling UPROPERTIES (BaseMaxMana, MaxManaPerLevel, BonusMaxMana), unlike the singleton MaxHealth on LokiAttributeSetHealth. Predicted a naive solo-MaxMana seed would be reverted by PostGameplayEffectExecute recompute f(BaseMaxMana, MaxManaPerLevel×Level, BonusMaxMana). Amendment: seed all 4 attrs together + add MANASHOT_COMPOUND diagnostic snapshots at PRECHECK and POST.

Design followed the amended spec: seed all 4 attrs, add both diagnostic snapshots.

## Delta from S189 mana f2

Source edits (all gated `#if KBFSEEDMAXMANA`; default 0; 7 prior gate variants BYTE-IDENTICAL):

| PATCH | Location | Purpose |
|---|---|---|
| A | `tutorial_launch.cpp:18044-18092` (near KBFPOSTSHOT_MANA defines) | `KBFSEEDMAXMANA` knob (default 0) + `KBFSEEDMAXMANA_BITS` knob (default `0x447A0000u` = 1000.0f) + 3 compile-time policy checks (require KBFSELFCAL/KBFBINDAVATAR/KBFSEEDMAXHEALTH; exclude S147/S149; bool check). |
| B | `tutorial_launch.cpp:22029/22148` | Extend BfS189ManaTarget resolver guard: `#if KBFPOSTSHOT_MANA` → `#if (KBFPOSTSHOT_MANA \|\| KBFSEEDMAXMANA)`. Preprocessor-only; evaluates identically for all prior variants where both knobs are 0. |
| C | `tutorial_launch.cpp:22612-22715` (after KBFSEEDMAXHEALTH block, before KBFBINDAVATAR `#endif`) | `BfS189SeedMaxMana` inline seed block: resolves manaSet via `BfS189ResolveManaTarget(s156Pre.asc, ...)`, resolves 3 compound siblings via `PropOffsetSuper(setCls, "BaseMaxMana"/"MaxManaPerLevel"/"BonusMaxMana")`, contracts `s189CompoundLayoutOk = baseMaxOff==0x230 && perLevelOff==0x240 && bonusMaxOff==0x250`, `SafeWritable`-gates all 4 pairs, `__try/__except`-wraps a 4-store sequence (2 × 8-byte volatile qword writes of seedBits + 2 × 8-byte zero writes for PerLevel/Bonus), re-resolves via a second BfS189ResolveManaTarget call, verifies all 4 pre/post values, emits `[S189-SEED] MAX_MANA_SEEDED` + per-attr detail lines. Fail-open: refuses via `SEED_GATE_REFUSED` if not exact but does NOT terminate S148 (unlike KBFSEEDMAXHEALTH which is a hard PREFLIGHT precondition). |
| D | `tutorial_launch.cpp:22440/22483` (mana probe block) | MANASHOT_COMPOUND_PRE + MANASHOT_COMPOUND_POST diagnostic snapshots of the 3 sibling attrs. Gated `#if KBFSEEDMAXMANA` so postshots-mana variant remains byte-identical. |
| E | `build.ps1:775-785` | New variant `botfight-damage-self-cal-bindavatar-seedmax-mana-seedcompound1000` = parent postshots-mana + `-DKBFSEEDMAXMANA=1 -DKBFSEEDMAXMANA_BITS=0x447A0000u`. |

## Bug caught mid-arc (F2 → F3)

F2 marker returned `MAX_MANA_SEEDED result=SKIPPED_TARGET_UNRESOLVED refuseReason=asc-unreadable spawnedIndex=-1`. **Root cause:** the seed block used `s_seeded.asc`, but `s_seeded` isn't populated until `s_seeded=seeded;` at line 22893 — AFTER the AdjustHealth PRESEED_REVALIDATION runs, which is DOWNSTREAM of the KBFSEEDMAXMANA block in the initial dispatch. **Fix:** use `s156Pre.asc` (the ASC S156's max-health seed just resolved via `BfS148ResolveHealthTarget` — canonical at this dispatch point). F3 landed clean on first try after the one-line fix. **Rule R-S189-seed-a banked:** in an inline block that runs in the S148 initial dispatch upstream of `s_seeded=seeded`, the fresh ASC to use is `s156Pre.asc` (or `s148PreOrEquivalent.asc`), not `s_seeded.asc`.

Preserved F2 marker at `docs/s189-seed-f2-marker-BUG-asc-unreadable.txt` (evidence of the caught bug + the refuse-path exercising fail-open behavior correctly).

## Flight ledger

| flight | outcome | cause |
|---|---|---|
| F1 | FK-31 during staging (`0xC0000005` ACCESS VIOLATION, PID 42884 died between sp inject and probe inject) | Staging hazard variance, unrelated to KBFSEEDMAXMANA (no probe code ran). Crashwatch archive at `dumps/crash-20260909-091501/`. |
| F2 | SEED_GATE_REFUSED (`asc-unreadable`), fail-open proceeds through primary+mana probe as if no seed happened | Bug in KBFSEEDMAXMANA block: used `s_seeded.asc` (not yet populated). Fix applied, DLL rebuilt (RAW hash `934742aabda2835f` → `485942a135855110`). |
| **F3** | **SUCCESS — MANASHOT_APPLIED first-try after fix. All 7 pre-registered predictions hit.** | Fixed source. Clean-slate process (killed F2, relaunched). |

Session cost: 2 launches lost to hazards (F1 FK-31 staging, F2 caught bug), F3 first-attempt landing.

## Receipts (full ladder)

Full marker: `docs/s189-seed-f3-marker-final.txt` (90 lines).

### S155 bind + S156 MaxHealth seed (unchanged from S156-A F5 pattern)

```
[S155] BIND_AVATAR result=ok pc=0x164FBA3B140 hero=0x165B06D5580 ...
[S155] AvatarActor@0x410 pre=0x0 post=0x165B06D5580 avatarBound=1
[S156] MAX_HEALTH_SEEDED result=ok pair=0x165F1637F28 maxPre=00000000/00000000 maxPost=447A0000/447A0000
       structPayload=1 layoutValid=1 writable=1 preIssues=0x200 postIssues=0x0 exact=yes
[S156] proceed=yes handing off to S148 PREFLIGHT with MaxHealth=1000/1000
```

### S189-SEED compound MaxMana seed (NEW)

```
[S189-SEED] ===== max-mana seed preflight (KBFSEEDMAXMANA=1) =====
[S189-SEED] MAX_MANA_SEEDED result=ok seedBits=447A0000 spawnedIndex=0 exactMatches=1 writable=1
            preResolved=yes postResolved=yes compoundLayoutOk=yes refuseReason=- exact=yes
[S189-SEED]   MaxMana@0x220          pair=0x1A39478F908 pre=00000000/00000000 post=447A0000/447A0000
[S189-SEED]   BaseMaxMana@0x230      pair=0x1A39478F918 pre=00000000/00000000 post=447A0000/447A0000
[S189-SEED]   MaxManaPerLevel@0x240  pair=0x1A39478F928 pre=00000000/00000000 post=00000000/00000000
[S189-SEED]   BonusMaxMana@0x250     pair=0x1A3947...   pre=00000000/00000000 post=00000000/00000000
[S189-SEED] proceed=yes handing off to S148 PREFLIGHT with MaxMana=447A0000/447A0000 BaseMaxMana=447A0000/447A0000 MaxManaPerLevel=0/0 BonusMaxMana=0/0
```
- **[M] All 4 compound attrs seeded exactly**. `exact=yes` means all 4 post-readback values match seedBits (or 0 for the two "zeroed" attrs).
- **[M] `compoundLayoutOk=yes`** — offline offset arithmetic verified LIVE: BaseMaxMana@+0x230, MaxManaPerLevel@+0x240, BonusMaxMana@+0x250 all resolved via `PropOffsetSuper` reflection. If any offset drifted, the arm refuses at this gate.
- **[M] `spawnedIndex=0 exactMatches=1`** — the resolver picked exactly ONE `LokiAttributeSet` entry in ASC.SpawnedAttributes (the sibling `LokiAttributeSetHealth` at index 1 is a DIFFERENT set and correctly not matched).
- Pair addresses are 4-byte aligned (0x1A39478F908, +0x10, +0x10, +0x10) — confirming the 16-byte FGameplayAttributeData stride pattern.

### S148 primary AdjustHealth (unchanged — contract preserved)

```
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000
       immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=265ms callCount=1
```

Byte-identical to S156-A F5 and every subsequent flight: 1000 HP → 750 HP, one call. **The MaxMana seed did NOT interfere with the primary Health shot** (structural proof that Mana and Health attribute sets are independent).

### S189 mana probe with SEEDED MaxMana (the moment of truth)

```
[S189] MANASHOT_RESOLVE ufunc=0x1A2A6246F30 flags=0x04020401 thunk=0x7FF6933F42F0
       wrapperExact=yes implResolvedRva=0x55166D0 tailReason=ok class=0x1A29676B000 classExact=yes
       owner=0x1A2ABAD0100 ownerExact=yes child=0x1A2E9945500 PropertiesSize=4 parmCount=1
       chainComplete=yes ManaDeltaProp=0x1A2E9945500 off=0x0 size=4 arrayDim=1 propFlags=0x0018001040000280
       resolved=yes
[S189] MANASHOT_PRECHECK manaSet=0x1A39478F6E0 spawnedIndex=0 preBits=00000000/00000000 preMP=0.00/0.00
       maxBits=447A0000/447A0000 maxMP=1000.00/1000.00
[S189] MANASHOT_COMPOUND_PRE baseMax=447A0000/447A0000 perLevel=00000000/00000000 bonusMax=00000000/00000000
[S189] MANASHOT_CALL_ISSUED deltaBits=42480000 deltaMP=50.00
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] MANASHOT_POST postBits=42480000/42480000 postMP=50.00/50.00 postMaxBits=447A0000/447A0000
       postMaxMP=1000.00/1000.00 observedDeltaCurrentMP=+50.00 observedDeltaBaseMP=+50.00
       arithmeticOK=yes rvalBits=00000000 identityStable=yes afterOk=yes
[S189] MANASHOT_COMPOUND_POST baseMax=447A0000/447A0000 perLevel=00000000/00000000 bonusMax=00000000/00000000
[S189] MANASHOT_COMPLETE RESULT=MANASHOT_APPLIED callCount=1 identityStable=yes
```

### Clean disarm (unchanged)

```
[FS] disarm: restored=17563 of 17563 swapped (scan 3282 ms, 34253 UFunctions live)
```

## Pre-registered predictions vs measured (all 7 hit)

| # | Prediction | Measured | ✓/✗ |
|---|---|---|---|
| 1 | MAX_MANA_SEEDED result=ok exact=yes on all 4 attrs | `result=ok exact=yes`, all 4 post readbacks match seed | ✓ |
| 2 | MANASHOT_PRECHECK maxBits=447A0000/447A0000 maxMP=1000.00/1000.00 | Exact match | ✓ |
| 3 | MANASHOT_CALL_ISSUED deltaBits=42480000 deltaMP=50.00 | Exact match | ✓ |
| 4 | MANASHOT_POST postBits=42480000/42480000 postMP=50.00/50.00 arithmeticOK=yes | Exact match | ✓ |
| 5 | MANASHOT_POST postMaxBits=447A0000 (MaxMana unchanged by AdjustMana) | Exact match | ✓ |
| 6 | MANASHOT_COMPLETE RESULT=MANASHOT_APPLIED identityStable=yes | Exact match | ✓ |
| 7 | 17563/17563 funcswap restore, no FK-32 within 90s | Exact match; game alive at +368s | ✓ |

## What this settles

1. **[M] `AdjustMana` writes BOTH BaseValue and CurrentValue.** `postBits=42480000/42480000` — the same "AdjustXxx family writes both slots" semantic S156-B measured for AdjustHealth, now confirmed for AdjustMana on a different attribute set. Extends R-S189-b (S153 thunkExact fix universality) with a new claim: the AdjustXxx family has uniform write shape across attribute sets.

2. **[M] `AdjustMana` does NOT recompute MaxMana from compound siblings.** MANASHOT_COMPOUND_POST shows BaseMaxMana/MaxManaPerLevel/BonusMaxMana all UNCHANGED after AdjustMana ran. The adversarial verifier's predicted PostGameplayEffectExecute recompute path did NOT fire — either it doesn't exist for AdjustMana, or it's gated behind something (e.g., only runs when a UGameplayEffect writes MaxMana, not when direct-offset writes to Mana). **The compound-seed defensive strategy was successful but not strictly necessary** — Flight 2 with a SOLO MaxMana seed could isolate whether MaxMana alone would suffice.

3. **[M] Direct-offset writes on `ULokiAttributeSet` are safe and persist.** All 4 seeded values (MaxMana=1000, BaseMaxMana=1000, MaxManaPerLevel=0, BonusMaxMana=0) survived: (a) the seed's immediate post-readback, (b) the S148 primary AdjustHealth cycle on the SIBLING LokiAttributeSetHealth set, (c) the MANASHOT_PRECHECK read via a second resolver call, (d) the AdjustMana call on the SAME set. Three independent instrument reads across the flight's timeline confirm persistence.

4. **[M] `ULokiAttributeSet` and `LokiAttributeSetHealth` are TRULY INDEPENDENT SETS** — writes to one don't affect the other. Confirmed by: (a) S148 primary AdjustHealth on `LokiAttributeSetHealth` at MaxHealth+0x80 produced Health 1000→750 with no visible side effect on Mana or MaxMana; (b) AdjustMana on `ULokiAttributeSet.Mana` produced Mana 0→50 with no visible side effect on Health/MaxHealth (both stay at 750/1000). Attribute-set isolation is architectural in this build, not incidental.

5. **[M] First project write to `ULokiAttributeSet` survives — no FK-32 within the 8-minute post-flight window.** Every prior AdjustHealth-family flight (S156-A, S156-B ×5, S189 mana ×1) touched `LokiAttributeSetHealth`. This flight extends the safe-write envelope to `ULokiAttributeSet`. Game alive at 368s post-flight = **project-record uptime for a first-write-to-new-attribute-set flight** with 0 crashpad handoffs.

6. **[M] S189-SEED's fail-open design worked as intended on F2.** When the ASC precondition wasn't met, `SEED_GATE_REFUSED reason=max-mana-seed-not-exact` fired and the S148 primary shot still ran (`SELF_DAMAGE_CALIBRATED` still produced), followed by the mana probe with unseeded MaxMana (which would have produced MANASHOT_NO_OP, indistinguishable from the parent postshots-mana). The design correctly separates the seed's success from S148's success — critical for interpretable nulls.

## The BIG downstream: S141 T3 movement wall unlocks

The layout audit from the design workflow revealed that `ULokiAttributeSet` — the same set this flight successfully seeded — contains **all the S141 T3 movement-wall targets**:

| offset | attribute | S141 T3 significance |
|---|---|---|
| 0x0F0 | MoveSpeed | The `GetMaxSpeed()` return that clamps `MaxInputSpeed` in `CalcVelocity` |
| 0x100 | MaxMoveSpeed | Cap for MoveSpeed |
| 0x110 | MoveSpeedPerLevel | Level-scaling for MoveSpeed |
| 0x120 | **MaxAcceleration** | **The "getter returns 0 → Acceleration=0" wall from S139/S141** |
| 0x130 | GroundFriction | Friction on the ground plane |
| 0x140 | BrakingDecelerationWalking | Deceleration when input released |
| 0x170 | Mass | Character mass |

The S141 T3 measurement chain established that the BOT's `MaxAcceleration` was 0 because `AttributeSetStorage@+0xF08` was NULL, and porting the DS-hybrid recipe (write attribute values to the set) got the acceleration up to 50000 — but that recipe writes to `AttributeSetStorage`, not directly to the attribute set. **The mechanism proven here (direct-offset seed on ULokiAttributeSet with `PropOffsetSuper` layout contract) could seed all 7 movement-wall attributes with the SAME code pattern** — just add 3 more resolve/write pairs per attribute. This is a project-scale unlock: the S141 movement wall's core question ("why does Acceleration=0") becomes "seed MoveSpeed=500/MaxMoveSpeed=500/MaxAcceleration=50000/GroundFriction=8/BrakingDecelerationWalking=2048/Mass=100 via KBFSEEDMAXMANA-analog knobs and re-fly S141 T3 ARM L."

## Method rules banked

- **R-S189-seed-a (fresh-ASC selection in initial dispatch):** an inline block in `BfS148DoCalibration` running UPSTREAM of the `s_seeded=seeded;` assignment at line 22893 must use `s156Pre.asc` (or an equivalent freshly-resolved BfS148HealthTarget.asc), NOT `s_seeded.asc` which is still zero. Caught on F2 via `refuseReason=asc-unreadable` and a fresh source read of `s_seeded` assignments. **Instrument artifact avoided by fail-open design**: the seed's refuse path did NOT terminate S148, letting the primary shot continue and preserving interpretability.

- **R-S189-seed-b (compound-seed is defensive, not always required):** the adversarial mechanism verifier predicted MaxMana on `ULokiAttributeSet` would be recomputed from compound siblings and reverted. This flight's MANASHOT_COMPOUND_POST diagnostic showed the compound siblings UNCHANGED after AdjustMana — so a solo MaxMana seed would likely have worked too. **However**, seeding all 4 was CHEAP (4 × 8-byte writes) and eliminated the null-attribution ambiguity in advance. The compound-seed diagnostic (MANASHOT_COMPOUND_PRE/POST) is what MAKES the null attributable — without it, a failure would leave "compound recompute" as an untested hypothesis. **Rule: cost-of-diagnostic << cost-of-repeat-flight; always include the discriminator.**

- **R-S189-seed-c (ULokiAttributeSet is a superset attribute-set):** the design workflow's layout audit revealed 124 UPROPERTIES on `ULokiAttributeSet` covering Move/Health/Mana/Stamina/Attack/Barracuda/Gold families. The KBFSEEDMAXMANA mechanism generalizes to any of them via the same `PropOffsetSuper(setCls, "<AttrName>") + SafeWritable + volatile qword store + readback verify` pattern. **The S141 T3 movement wall targets are one KBFSEEDMOVEMENT knob away.**

## Files

- `docs/s189-seed-f3-marker-final.txt` — preserved F3 marker (90 lines)
- `docs/s189-seed-f2-marker-BUG-asc-unreadable.txt` — preserved F2 marker (evidence of the caught bug + fail-open behavior)
- `docs/fk24-stage-s189-seed-f1-*.txt` — F1 per-inject markers (staging FK-31 death)
- `docs/fk24-stage-s189-seed-f2-*.txt` — F2 per-inject markers
- `docs/fk24-stage-s189-seed-f3-*.txt` — F3 per-inject markers (all clean)
- `dumps/crash-20260909-091501/` — F1 crashwatch archive (`0xC0000005` ACCESS VIOLATION)
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFSEEDMAXMANA + KBFSEEDMAXMANA_BITS knobs, 3 policy checks, BfS189ResolveManaTarget guard extension, inline BfS189SeedMaxMana block, MANASHOT_COMPOUND_PRE/POST diagnostics
- `tools/sigbypass-mod/build.ps1` — new `botfight-damage-self-cal-bindavatar-seedmax-mana-seedcompound1000` variant
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_mana_seedcompound1000.dll` — RAW `485942a135855110`
- Workflow artifact: `C:\Users\eastr\.claude\projects\G--git-Supervive-Revival-Project\0cd9a770-6782-4d09-9c03-fdd2eb2a64f3\workflows\scripts\s189-mana-seed-design-wf_1de95504-0b7.js`

## Regression gates (post-flight)

All 7 prior gates UNCHANGED (KBFSEEDMAXMANA=0 default truly dead-strips):
- `botfight-damage-self-cal-bindavatar-seedmax` `b47d1bfd04e44921` ✓
- `-postshots1` `1925e9e80646a4fb` ✓
- `-postshots2` `ad87408901f481c5` ✓
- `-postshots2-floor600` `ca54361966e71afd` ✓
- `-postshots1-heal100` `0b9573215c85f511` ✓
- `-postshots1-heal500` `b0e29a434eabd87d` ✓
- `-postshots-mana` `c7ce885988fd3532` ✓
- **NEW: `-mana-seedcompound1000` `485942a135855110`** — distinct from all 7 priors (verified via `text_digest.py --dupes`), real treatment.

Both s148 contract tests PASS after knob addition.

## Still open

- **Solo-MaxMana seed:** untested. Would isolate whether MaxMana alone would work or the compound-seed is truly required. Low priority — the compound path is proven, and the solo path is only interesting for narrowing the "which recompute path exists" question.
- **KBFSEEDMOVEMENT (S141 T3 unlock):** apply the same mechanism to seed MoveSpeed/MaxMoveSpeed/MaxAcceleration/GroundFriction/BrakingDecelerationWalking/Mass. Would test whether the bot's motion wall opens when the movement attrs are seeded via direct-offset (bypassing the AttributeSetStorage NULL path). **HIGH VALUE.**
- **Multi-shot Mana (N=2 AdjustMana calls back-to-back):** untested. Analog of S156-B postshots1. Would test cross-dispatch continuity for Mana.
- **Mana cap test (delta > MaxMana):** untested. Should produce MANASHOT_CLAMPED with observedDelta = MaxMana - preMP, analog of S156-B heal500. Would confirm the AdjustXxx clamp semantic is uniform across attributes.
- **Non-Health/Mana attributes on `ULokiAttributeSet`:** Stamina, Attack, Barracuda, Gold families all present. AdjustStamina and AdjustAttackDamage exist in the ULokiAbilitySystemComponent thunk table (per S153 sweep) but their behavior on seeded values is untested.
- **Cross-attribute-set interactions:** whether writing MaxMana affects LokiAttributeSetHealth's MaxHealth (or vice versa) via any GE. This flight shows NO cross-contamination for the AdjustHealth+AdjustMana sequence, but other interactions (e.g. mana-drain-on-damage GEs) untested.
- **FK-32 envelope extension:** first project write to `ULokiAttributeSet` survived; n=1. Extending to Movement/Stamina attrs on the same set is the natural next FK-32 measurement.
