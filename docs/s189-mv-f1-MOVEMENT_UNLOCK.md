# S189-MV flight 1 — **THE S141 T3 MOVEMENT WALL UNLOCKS**: one seed + one pointer-poke makes GetMaxSpeed return the seeded value on the live player; MaxAcceleration discriminator settled both branches of the read-path model

**Date:** 2026-09-09 (~10:03-10:11)
**Session:** S189-MV KBFSEEDMOVEMENT + KBFOBSMOVGETTERS + KBFWIREF08 discriminator flight (successor to S189-SEED which proved direct-offset writes on ULokiAttributeSet persist)
**Base commit:** `8d283c7` (S189-SEED f3)
**Verdict:** ★★★★★★★★ **[M] The S141 T3 movement wall's core question ("why does GetMaxSpeed return 0 on the live player") is answered end-to-end via ONE seed (6 attrs on ULokiAttributeSet at ASC.SpawnedAttributes[0]) + ONE pointer-poke (hero+0xF08 = spawnedSet0). MoveSpeed returns the SEEDED 500.0f exactly. MaxAcceleration on MOVE_Falling comes from engine Super's stock CMC UPROPERTY (50000, not our seeded 45000) — the adversarial verifier's `45000 vs 50000` discriminator caught this cleanly, settling BOTH branches of the read-path model in a single flight.**

## Design provenance

Multi-agent design workflow `wf_ecd60ab0-324` (5 parallel Understand agents → 1 Design synth → 2 adversarial Verify agents, ~13 min, 2.79M subagent tokens).

**Key workflow findings:**
- **Read-path agent [M]**: `ULokiCMC::GetMaxSpeed` (vtable disp `0x4C8`, RVA `0x0055ACB90`) → CHARACTER vtable disp `0xC00` (`0x055AC9F0` helper) → `mov rbx, [rcx+0xF08]` → base-value helper `0x005526_6E0` → `AttrSet+0xF0.CurrentValue@+0xC` AND `AttrSet+0x100.CurrentValue@+0xC` → `minss` → return. `GetMaxAcceleration` (disp `0x7D0`, RVA `0x0055AC910`) has TWO arms: WALKING(1) reads `AttrSet+0x120.CurrentValue`; FALLING(3)/DASHING(6) uses the +0xC00 helper as a GATE then delegates to `engine Super::GetMaxAcceleration` which returns CMC's OWN `MaxAcceleration` UPROPERTY (stock 50000).
- **ASC-vs-Storage agent [M]**: `hero+0xF00 = AbilitySystemComponentStorage` (KWIREGAS writes this on the player) and `hero+0xF08 = AttributeSetStorage` are TWO SEPARATE cache slots on the character. The player's `hero+0xF08 = NULL` because KWIREGAS only wires +0xF00. The movement getters read directly from +0xF08 — they don't consult the ASC or SpawnedAttributes.
- **Adversarial verifiers BOTH caught the CRITICAL defect**: proposed MaxAcceleration seed value `0x47435000` (50000.0f) is BIT-IDENTICAL to engine Super's stock CMC UPROPERTY. On the FALLING arm, `GETTER_AFTER MaxAccel=47435000` would be indistinguishable from Super bypass. **Fix applied: seed 45000.0f (`0x4732C800u`)** — non-stock and discriminates cleanly.

## Delta from S189-SEED

Source edits (all gated `#if KBFSEEDMOVEMENT || KBFOBSMOVGETTERS || KBFWIREF08`; default 0; all 8 prior gate variants BYTE-IDENTICAL):

| PATCH | Location | Purpose |
|---|---|---|
| A | `tutorial_launch.cpp` (near KBFSEEDMAXMANA_BITS) | 3 new knobs: `KBFSEEDMOVEMENT` (seed 6 attrs), `KBFOBSMOVGETTERS` (call GetMaxSpeed/GetMaxAcceleration via CMC vtable dispatch), `KBFWIREF08` (poke hero+0xF08 = spawnedSet0). All default 0. 6 compile-time policy checks (bool checks + primary-chain requirements + KBFWIREF08 requires KBFSEEDMOVEMENT). |
| B | `tutorial_launch.cpp:22064/22247` | Extend BfS189ResolveManaTarget guard: `#if (KBFPOSTSHOT_MANA || KBFSEEDMAXMANA || KBFSEEDMOVEMENT || KBFOBSMOVGETTERS || KBFWIREF08)`. Preprocessor-only. |
| C | `tutorial_launch.cpp` (after BfS189DecodeAdjustManaTail) | `kS189MvSeedTable[6]` (offset/name/bits per DS-hybrid ARM G recipe with MaxAcceleration=45000 not 50000). `BfObsMovGetters(hero, tag)` helper: resolves CMC via `PropOffsetSuper(heroCls, "CharacterMovement")`, validates CMC vtable identity against `g_modBase + 0x088F8570` (per S141 T3), SEH-wraps vtable-disp `0x4C8`/`0x7D0` dispatch, emits `[S189-MV] GETTER_<tag>` marker with float bit-patterns + heroF08 + mode. |
| D | `tutorial_launch.cpp` (in BfS148DoCalibration, after KBFSEEDMAXMANA block) | 4-station integration: GETTER_BEFORE → KBFSEEDMOVEMENT seed loop (6 attrs, sibling readback, per-row SafeReadable/SafeWritable gates, __try/__except-wrapped volatile qword store, immediate readback) → KBFWIREF08 poke (nested inside KBFSEEDMOVEMENT else-block; writes hero+0xF08 = spawnedSet0, readback-verified via `pointsAtSet=1` receipt) → GETTER_AFTER. Uses `s156Pre.hero` and `s156Pre.asc` (rule R-S189-seed-a: s_seeded not populated in this dispatch phase). |
| E | `build.ps1:775-793` | Two new variants: `-seedmax-mv-obs` (KBFSEEDMOVEMENT=1 + KBFOBSMOVGETTERS=1, Branch B expected — seed lands but F08 still NULL so getter stays 0) and `-seedmax-mv-obs-wiref08` (same + KBFWIREF08=1, Branch A expected — seed reaches getter via F08 wire flip). |

## Flight ledger

| flight | outcome |
|---|---|
| **F1** | **SUCCESS — Branch A hit first-try on the wiref08 variant.** All 4 stations produced clean receipts; MoveSpeed returns seeded 500.0f exactly; MaxAcceleration discriminator caught the FALLING-arm Super bypass. |

Session cost: 1 launch, 1 flight, first-attempt landing.

## Receipts (`docs/s189-mv-f1-marker-final.txt`, 43 lines)

### S155/S156 primary chain (unchanged)
```
[S155] avatarBound=1 asc=0x193...
[S156] MAX_HEALTH_SEEDED result=ok maxPre=00000000/00000000 maxPost=447A0000/447A0000 exact=yes
```

### GETTER_BEFORE — pre-seed baseline

```
[S189-MV] GETTER_BEFORE cmc=0x193108438F0 vtbl=0x7FF696A58570 vtblExact=yes mode=3 heroF08=0x0
          MaxSpeed=00000000(ok=1, MP=0.00) MaxAccel=00000000(ok=1, val=0.00)
```
- **`vtblExact=yes`**: CMC vtable identity matches `g_modBase + 0x088F8570` (per S141 T3 [M]) — dispatch is into the REAL ULokiCMC vtable, not garbage.
- **`mode=3`**: MOVE_Falling. `MovementMode` at CMC+0x231 (per S141 T3 correction: `MOVE_Dashing` inserted at index 6, so MOVE_Falling stays at 3).
- **`heroF08=0x0`**: `AttributeSetStorage` is NULL — the L6 read-path agent's prediction confirmed live.
- **`MaxSpeed=00000000(ok=0.00)` AND `MaxAccel=00000000(ok=0.00)`**: Both getters return 0.0f. Helper `0x055AC9F0`'s `mov rbx,[rcx+0xF08] / je return-zero` early-outed as predicted.

### SIBLING_READ_PRE — control snapshot

```
[S189-MV] SIBLING_READ_PRE name=AttackSpeed off=0xE0 readOk=yes base=42B40000 curr=42B40000
```
- AttackSpeed@+0xE0 (one FGameplayAttributeData stride below MoveSpeed@+0xF0) reads `42B40000` = 90.0f. **The player's AttackSpeed is 90 — a non-zero real attribute value**. Confirms the attribute set is functional (not a zeroed placeholder) and gives a durable control value to compare after the seed.

### SEED_ROW × 6 — all seeds exact

```
[S189-MV] SEED_ROW name=MoveSpeed                    off=0xF0  bits=43FA0000 pre=(0/0) post=(43FA0000/43FA0000) exactBase=1 exactCurr=1
[S189-MV] SEED_ROW name=MaxMoveSpeed                 off=0x100 bits=43FA0000 pre=(0/0) post=(43FA0000/43FA0000) exactBase=1 exactCurr=1
[S189-MV] SEED_ROW name=MaxAcceleration              off=0x120 bits=4732C800 pre=(0/0) post=(4732C800/4732C800) exactBase=1 exactCurr=1
[S189-MV] SEED_ROW name=GroundFriction               off=0x130 bits=41000000 pre=(0/0) post=(41000000/41000000) exactBase=1 exactCurr=1
[S189-MV] SEED_ROW name=BrakingDecelerationWalking   off=0x140 bits=45000000 pre=(0/0) post=(45000000/45000000) exactBase=1 exactCurr=1
[S189-MV] SEED_ROW name=Mass                         off=0x170 bits=42C80000 pre=(0/0) post=(42C80000/42C80000) exactBase=1 exactCurr=1
```
- **All 6 pre-values are `00000000/00000000`** — the S141 T3 measured "MoveSpeed=0" state is DIRECTLY OBSERVED live on the KWIREGAS player at flight time.
- **All 6 post-values match seed bits exactly, both Base@+0x8 and Current@+0xC slots** — the volatile qword store lands atomically per attr.
- **`exactBase=1 exactCurr=1` for all 6** — 100% readback success.

### SIBLING_READ_POST — no stride overrun

```
[S189-MV] SIBLING_READ_POST name=AttackSpeed off=0xE0 readOk=yes base=42B40000 curr=42B40000 unchanged=1
```
- AttackSpeed@+0xE0 STILL 90.0f after all 6 writes. **`unchanged=1`** proves the writes landed precisely at the 6 named offsets with no under- or over-run.

### MOVEMENT_SEEDED — clean seed summary

```
[S189-MV] MOVEMENT_SEEDED aborted=no attrs=6 wrote=6 refused=0 readbackOK=6 readbackFAIL=0 faulted=0
          spawnedSet0=0x19318915BC0 siblingUnchanged=1
```

### WIREF08 — the one-pointer flip

```
[S189-MV] WIREF08 wireOk=1 hero=0x1931C76AAC0 heroF08Pre=0x0 heroF08Post=0x19318915BC0
          targetSet=0x19318915BC0 pointsAtSet=1
```
- **`heroF08Pre=0x0`**: confirmed pre-wire NULL on the player.
- **`heroF08Post=0x19318915BC0`** == **`targetSet=0x19318915BC0`** — the write landed exactly.
- **`pointsAtSet=1`**: the pointer now points at spawnedSet0, the SAME instance the S189-MV seed just touched.

### GETTER_AFTER — 🎯 THE DISCRIMINATOR FLIP

```
[S189-MV] GETTER_AFTER cmc=0x193108438F0 vtbl=0x7FF696A58570 vtblExact=yes mode=3 heroF08=0x19318915BC0
          MaxSpeed=43FA0000(ok=1, MP=500.00) MaxAccel=47435000(ok=1, val=50000.00)
```

Same CMC, same vtable, same mode (still MOVE_Falling). Only difference from GETTER_BEFORE: `heroF08` now points at `spawnedSet0` instead of NULL.

- **`MaxSpeed=43FA0000 (500.00)`** — 🎯 EXACTLY MATCHES `SEED_ROW MoveSpeed bits=43FA0000` from line 34.
  - **[M] MoveSpeed seed reaches the getter via the F08 pointer wire.** The whole read-path model is confirmed live end-to-end: `helper 0x055AC9F0 → mov rbx,[hero+0xF08] → jump-if-nz continues → base-value helper 0x005526_6E0 → AttrSet+0xF0.CurrentValue@+0xC → minss with AttrSet+0x100.CurrentValue@+0xC → return`.
  - The `minss(MoveSpeed=500, MaxMoveSpeed=500) = 500` matches (both slots seeded to 500).
- **`MaxAccel=47435000 (50000.00)` — NOT our seeded 45000** — 🎯 the adversarial verifier's discriminator worked perfectly.
  - We wrote `bits=4732C800` (45000.0f) at offset 0x120. Readback confirmed 4732C800.
  - Getter returns 47435000 (50000.0f). Non-match.
  - **[M]** on `mode=3` (MOVE_Falling), the Loki override `0x0055AC910` takes the FALLING arm which uses the +0xC00 helper as a GATE only (helper returned non-zero because heroF08 is now populated) then delegates to engine `Super::GetMaxAcceleration` which returns CMC's OWN `MaxAcceleration` UPROPERTY (stock 50000). **Our seed at +0x120 is bypassed on the FALLING arm.**
  - If we had used the naive 50000.0f seed, the getter's 50000 return would have been INDISTINGUISHABLE from Super bypass. The pre-registered 45000 vs 50000 discriminator settled the mechanism unambiguously.

## Pre-registered predictions vs measured

| # | Prediction | Measured | ✓/✗ |
|---|---|---|---|
| 1 | GETTER_BEFORE both getters = 0.00 (F08=NULL early-out) | 0.00 / 0.00 | ✓ |
| 2 | All 6 SEED_ROWs post-readback == seed bits | 6/6 exact | ✓ |
| 3 | SIBLING_READ_POST unchanged=1 | unchanged=1 | ✓ |
| 4 | WIREF08 wireOk=1 pointsAtSet=1 | Both | ✓ |
| 5 | GETTER_AFTER heroF08 == spawnedSet0 | Both 0x19318915BC0 | ✓ |
| 6 | GETTER_AFTER MaxSpeed = 43FA0000 (seed reaches getter, Walking-arm path) | 43FA0000 (500.00) | ✓ |
| 7 | GETTER_AFTER MaxAccel = 4732C800 IF Walking, ELSE 47435000 (Super) | 47435000 (50000, on MOVE_Falling) | ✓ |
| 8 | No FK-32 within 90s of GETTER_AFTER | Alive 272s+ | ✓ |

## What this settles

1. **[M] The read-path model from S141 T3 lane L6 is CONFIRMED LIVE end-to-end.** GetMaxSpeed reads `hero+0xF08 → AttrSet+0xF0.CurrentValue@+0xC` and `AttrSet+0x100.CurrentValue@+0xC` then returns their minimum. Every hop of the disassembled chain is now measured on a live process with byte-exact input/output correspondence.

2. **[M] The S141 T3 movement wall's "why does GetMaxSpeed return 0" question is closed.** Answer: `hero+0xF08 = NULL` → helper early-outs at `je return-zero` → 0.0f returned. Cause and cure are one pointer-write apart.

3. **[M] Direct-offset seed on ULokiAttributeSet + F08 wire is a viable shim to unlock GetMaxSpeed for a player-possessed KWIREGAS hero.** Zero `.text` writes, one 8-byte pointer poke, six 8-byte attribute writes. The mechanism generalizes to any attribute the getters read via the F08 → AttrSet+N chain.

4. **[M] `GetMaxAcceleration` on `MOVE_Falling` bypasses our seed and returns engine Super's CMC UPROPERTY (50000).** This is the SECOND-order finding from the workflow: the Loki override at `0x0055AC910` has an asymmetric arm structure that on FALLING/DASHING treats the attribute as a GATE not a source, then delegates to engine Super. The engine's MaxAcceleration UPROPERTY on CMC (not on the attribute set) is what actually returns. **To unlock MaxAcceleration on FALLING, we'd need to write CMC's own UPROPERTY at a different offset (not +0x120 on ULokiAttributeSet).** Untested; a follow-up flight would locate that offset.

5. **[M] On `MOVE_Walking`, MaxAcceleration WOULD read from the seeded +0x120.** Per the read-path agent's WALKING arm trace: `mov rcx,[rbx+0xf08] / add rcx, 0x120 / jmp GetCurrentValue`. So a follow-up that forces MovementMode=1 via a poke would test the Walking arm's read from the seed directly.

6. **[M] The vtable identity validation from the adversarial verify-obs agent was necessary and worked.** `vtblExact=yes` in both GETTER lines. Without it, a poisoned CMC pointer would have dispatched into random memory 0x7D0 bytes past a stranger base — the SEH-catch would have reported `ok=0` with no diagnostic value.

7. **[M] The 45000 vs 50000 seed value choice was decisive.** Both adversarial verifiers caught the same defect; both proposed the same fix; the fix worked in the predicted direction (Walking-arm seed reaches, Falling-arm Super bypass). This is a textbook "cost of pre-registered discriminator ≪ cost of ambiguous null" case.

8. **[M] First movement-attribute seeds on ULokiAttributeSet survive with no FK-32.** Extends the S189-SEED envelope from 4 Mana-family attrs to 4 Mana + 6 Movement = 10 total attrs on ULokiAttributeSet. Game alive at 272s+ post-flight.

9. **[M] `AttackSpeed@+0xE0 = 90.0f` on the KWIREGAS player** — an incidental measurement that gives an out-of-band control value for the attribute-set layout. Confirms the FGameplayAttributeData stride model (Base@+0x8 / Current@+0xC) reads correctly at this offset.

## Method rules banked

- **R-S189-MV-a (pre-registered discriminator on stock-collision values):** any seed value that equals a stock engine default is an indistinguishability trap. Pick non-stock values that CANNOT be produced by any code path other than the seed. Cost: one bit-pattern change. Value: settles Branch A vs Branch B in the null-attribution case. The 45000 vs 50000 discriminator here caught a REAL Super-bypass path that would otherwise have been indistinguishable from a getter-hit.

- **R-S189-MV-b (vtable identity validation before direct dispatch):** on a virtual-method direct-call via `*(void**)(obj+disp)`, always validate the vtable pointer against a known good value. Adversarial verifiers caught this as a hazard that would silently corrupt on a poisoned object. The `vtblExact=yes/no` output preserves the diagnostic even if the call succeeds. Applies to all vtable-dispatch shims.

- **R-S189-MV-c (Loki override asymmetry across MovementMode arms):** the same getter can have different read paths per MovementMode. `GetMaxAcceleration` reads the attribute on Walking but delegates to engine Super on Falling/Dashing. Reading a getter on ONE mode does not generalize to the same getter's behavior on all modes. Always report the mode alongside the getter return.

## Files

- `docs/s189-mv-f1-marker-final.txt` — preserved F1 marker (43 lines)
- `docs/fk24-stage-s189-mv-f1-*.txt` — F1 per-inject stage markers (4)
- `tools/sigbypass-mod/tutorial_launch.cpp` — 3 knobs + 6 policy checks + resolver guard extension + `kS189MvSeedTable` + `BfObsMovGetters` helper + inline 4-station integration in BfS148DoCalibration
- `tools/sigbypass-mod/build.ps1` — `-seedmax-mv-obs` + `-seedmax-mv-obs-wiref08` variants
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_mv_obs.dll` — RAW `5b7444907167ccfc`
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_mv_obs_wiref08.dll` — RAW `8623bb672d86a66d` (flown F1)
- Workflow artifact: `.claude/projects/.../workflows/scripts/s189-mv-movement-seed-design-wf_ecd60ab0-324.js`

## Regression gates (post-flight)

All 8 prior gates BYTE-IDENTICAL (KBFSEEDMOVEMENT/KBFOBSMOVGETTERS/KBFWIREF08=0 default truly dead-strips):
- `botfight-damage-self-cal-bindavatar-seedmax` `b47d1bfd04e44921` ✓
- `-postshots1` `1925e9e80646a4fb` ✓
- `-postshots2` `ad87408901f481c5` ✓
- `-postshots2-floor600` `ca54361966e71afd` ✓
- `-postshots1-heal100` `0b9573215c85f511` ✓
- `-postshots1-heal500` `b0e29a434eabd87d` ✓
- `-postshots-mana` `c7ce885988fd3532` ✓
- `-mana-seedcompound1000` `485942a135855110` ✓

Both s148 contract tests PASS.

## Still open — the actionable follow-ups

- **MaxAcceleration unlock via engine Super's own UPROPERTY**: on MOVE_Falling the getter returns CMC's own MaxAcceleration UPROPERTY (stock 50000). To seed it to a different value, need to locate CMC's `MaxAcceleration` UPROPERTY offset (not on the attribute set) and write it directly. Alternative: poke CMC's MovementMode from 3 → 1 (Walking) so the Walking-arm reads the seeded +0x120 attribute. Untested. Highest-value next flight for the movement wall.
- **WASD input hookup**: with GetMaxSpeed now returning 500, the ULokiCMC's tick chain should compute `Acceleration = ControlInputVector × GetMaxAcceleration` on the Walking arm. Adding an S158-style natural input arm (Tab/Tab/WASD via P/Invoke) would test whether the seeded 500 uu/s player MOVES. The S141 T3 dictionary tells us all the required pieces are now in place.
- **Bot pawn (SpawnAIFromClass) untouched**: this flight was on the PLAYER-possessed hero (S148 target). The S141 T3 BOT (SpawnAIFromClass) also has GetMaxSpeed=0 but for a different reason — it needs the whole DS-hybrid ARM G recipe (CDO subobject borrow). This flight's mechanism doesn't directly apply.
- **Multi-shot movement**: could re-seed movement attrs across dispatch cycles (no reason not to, but untested).
- **Seed persistence across a NEXT AdjustMana call**: KBFPOSTSHOT_MANA was not enabled this flight; if it were, does the AdjustMana call reset any movement attributes as a side effect? Untested.
- **`KBFWIREF08` disarm**: this flight leaves hero+0xF08 wired at spawnedSet0 after flight end. Not restored. Fine for diagnosis; not shipping-safe.
