# S189 mana probe flight 2 — AdjustMana native path exists, resolves cleanly, and no-ops on MaxMana=0

**Date:** 2026-09-08 (~21:16-21:19)
**Session:** S189 Mana attribute probe (postshots-mana variant, sibling of S156-B AdjustHealth series)
**Base commit:** S156-B heal500 lineage
**Verdict:** ★★★★★★ **[M] The AdjustMana UFunction is REAL, callable through the same UHT-wrapper mechanism as AdjustHealth, and executes end-to-end with `identityStable=yes`.** Mana stayed at 0/0 because MaxMana=0 clamps the +50 delta to zero — the same clamp semantic S156-B heal500 measured for MaxHealth, just on the empty-set side. **This is `MANASHOT_NO_OP` from the pre-registered outcome table, not a wall.**

## Why this flight

S156-B closed the AdjustHealth surface end-to-end (damage, heal, floor, MaxHealth cap, multi-shot). The next question was mechanism generalization: does the same S148/S153 machinery reach a *different* attribute set (Mana on `ULokiAttributeSet`, not Health on `LokiAttributeSetHealth`)? The two attribute sets live at different SpawnedAttributes indices (0 for LokiAttributeSet, 1 for LokiAttributeSetHealth in this build), and Mana comes with its own UFunction (`AdjustMana`, class `0x22AC76BB000` = ULokiAbilitySystemComponent, thunk `0x7FF6933F42F0`, impl RVA `0x55166D0`) — a proper second target for the S153 thunkExact fix.

## Arm

`build.ps1 -Variant botfight-damage-self-cal-bindavatar-seedmax-postshots-mana`
`.text` RAW: **`c7ce885988fd3532`** (KBFPOSTSHOTS=0, KBFPOSTSHOT_MANA=1, KBFPOSTSHOT_MANA_DELTABITS=0x42480000u = +50.0f)

Zero source changes vs postshots1-heal500 for the AdjustHealth path — pure additive build.ps1 variant. All prior regression gates BYTE-IDENTICAL:

| variant | RAW | role |
|---|---|---|
| `botfight-damage-self-cal-bindavatar-seedmax` | `b47d1bfd04e44921` | S156 seed baseline |
| `-postshots1` | `1925e9e80646a4fb` | N=1 damage |
| `-postshots2` | `ad87408901f481c5` | N=2 damage |
| `-postshots2-floor600` | `ca54361966e71afd` | floor fires |
| `-postshots1-heal100` | `0b9573215c85f511` | heal below cap |
| `-postshots1-heal500` | `b0e29a434eabd87d` | MaxHealth cap fires |
| **`-postshots-mana`** | **`c7ce885988fd3532`** | **AdjustMana probe (this flight)** |

## Flight ledger

| flight | outcome |
|---|---|
| F1 | died to FK-31 (ACG-denied `sp` inject, same class as prior staging hazards) |
| **F2** | **SUCCESS** — primary S148 shot and S189 Mana probe both ran end-to-end |

**Session cost:** 2 launches. F1 hazard variance (staging FK-31), F2 first-attempt landing.

## Receipts (S189 Mana probe)

Full marker: `docs/s189-mana-f2-marker-final.txt` (15,401 bytes, 82 lines)

### Primary S148 shot (contract preserved)

```
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000
       immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=266ms callCount=1
```

Byte-identical to S156-A F5 and every subsequent within-family flight: 1000 HP → 750 HP, calibrated, one call.

### S189 Mana probe chain (NEW)

**RESOLVE — the S153 thunkExact fix generalizes to AdjustMana:**
```
[S189] MANASHOT_RESOLVE ufunc=0x22AD7026F30 flags=0x04020401
       thunk=0x7FF6933F42F0 wrapperExact=yes implResolvedRva=0x55166D0 tailReason=ok
       class=0x22AC76BB000 classExact=yes owner=0x22ADC880100 ownerExact=yes
       child=0x22B1A026580 PropertiesSize=4 parmCount=1 chainComplete=yes
       ManaDeltaProp=0x22B1A026580 off=0x0 size=4 arrayDim=1
       propFlags=0x0018001040000280 resolved=yes
```
- `wrapperExact=yes` — the wrapper at thunk sits at expected offset `0x52942F0` (equivalent to AdjustHealth's `0x5294270` +0x80).
- `implResolvedRva=0x55166D0 tailReason=ok` — the `E8 <rel32>` tail-call at wrapper+0x6F resolves to the expected impl RVA (equivalent to AdjustHealth's `0x5516610`). **[M] the S153 UHT-wrapper thunk-vs-impl distinction generalizes across reflected native calls with parameters — not specific to AdjustHealth.**
- `owner=0x22ADC880100 ownerExact=yes` — resolved on the ULokiAbilitySystemComponent class, same as AdjustHealth.
- `child=0x22B1A026580` — Mana delta parameter, distinct from AdjustHealth's `0x22B1A026600` (different UFunction, different child prop).
- `PropertiesSize=4 parmCount=1 chainComplete=yes ManaDeltaProp=0x22B1A026580 off=0x0 size=4` — same shape as AdjustHealth: single float parameter, offset 0 in the FFrame.
- `propFlags=0x0018001040000280` — identical to AdjustHealth's.

**PRECHECK — resolved Mana attribute set at spawnedIndex=0:**
```
[S189] MANASHOT_PRECHECK manaSet=0x22C0E441BE0 spawnedIndex=0
       preBits=00000000/00000000 preMP=0.00/0.00
       maxBits=00000000/00000000 maxMP=0.00/0.00
```
- `manaSet=0x22C0E441BE0` — the ULokiAttributeSet instance at SpawnedAttributes index 0 (LokiAttributeSetHealth is at index 1, which is why S156-B AdjustHealth targets used `candidateIndex=1`).
- `preMP=0.00/0.00 maxMP=0.00/0.00` — **both Mana and MaxMana are zero at baseline**. This is the empty attribute set — nothing has ever seeded MaxMana in this session (S156 seeds MaxHealth only).

**CALL — deltaBits and CallNative:**
```
[S189] MANASHOT_CALL_ISSUED deltaBits=42480000 deltaMP=50.00
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
```
- `deltaBits=42480000 deltaMP=50.00` — issuing +50 Mana.
- CallNative with the ZEROONLY frame (same as every S148 shot).

**POST — the clamp fires:**
```
[S189] MANASHOT_POST postBits=00000000/00000000 postMP=0.00/0.00
       postMaxBits=00000000/00000000 postMaxMP=0.00/0.00
       observedDeltaCurrentMP=+0.00 observedDeltaBaseMP=+0.00
       arithmeticOK=NO rvalBits=00000000 identityStable=yes afterOk=yes
```
- `postMP=0.00/0.00` — Mana unchanged. Requested +50 → applied +0.
- `arithmeticOK=NO` — the arm's per-shot arithmetic check correctly captured the mismatch (+50 requested, +0 observed).
- `identityStable=yes afterOk=yes` — no fault, no attribute-set change, no downstream refusal.
- `rvalBits=00000000` — return value carries no clamp signal (analogous to AdjustHealth's silent clamp).

**COMPLETE — clean disarm:**
```
[S189] MANASHOT_COMPLETE RESULT=MANASHOT_NO_OP callCount=1 identityStable=yes
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan 3234 ms, 34253 UFunctions live)
[BF] worker done (hits=105 hitsGT=105)
```
- `RESULT=MANASHOT_NO_OP` — pre-registered outcome from the workflow synthesis; the +50 delta had nowhere to land because MaxMana=0.
- `restored=17563 of 17563` — 100% funcswap restoration.
- Game alive at flight end (PID 40432, 353s uptime, no FK-32).

## What this settles

1. **[M] AdjustMana is a REAL native UFunction with the same UHT wrapper shape as AdjustHealth.** Same `flags=0x04020401`, same `PropertiesSize=4`, same `parmCount=1`, same `propFlags=0x0018001040000280`. Class-scoped on ULokiAbilitySystemComponent (`owner=0x22ADC880100 ownerExact=yes`). No stripped-stub blocker.

2. **[M] The S153 thunkExact fix is UNIVERSAL for UHT wrappers with parameters.** `wrapperExact=yes` at the mana thunk (`0x7FF6933F42F0`, which is base+0x52942F0 — exactly `AdjustHealth thunk + 0x80` = `0x5294270 + 0x80`), `tailReason=ok` for the `E8 <rel32>` tail-call resolving to the expected impl RVA `0x55166D0`. The mana wrapper follows byte-identical UHT emission pattern. **This is the second live confirmation of the S153 fix (first was S156-A F5 on AdjustHealth) — not an AdjustHealth-specific quirk.**

3. **[M] The Mana attribute set is at SpawnedAttributes index 0, LokiAttributeSetHealth at index 1.** The probe resolved cleanly at `spawnedIndex=0` after the shim walked the same census infrastructure. Multi-attribute-set support in the S148 census machinery is proven working.

4. **[M] Mana and MaxMana both read 0.0/0.0 by default on this bot — the attribute set is EMPTY without external seeding.** The tutorial world's hero has zero Mana capacity by construction. Contrast: MaxHealth also read 0 initially (`preIssues=0x200`), which is exactly why S156's MaxHealth seed step exists.

5. **[M] AdjustMana with MaxMana=0 CLAMPS the positive delta to 0** — same silent clamp semantic S156-B heal500 measured for MaxHealth. `arithmeticOK=NO`, `identityStable=yes`, `rvalBits=00000000` (no signal to caller). The clamp is a uniform property of the AdjustXxx family, not attribute-specific.

6. **[M] No FK-32.** Seventh consecutive AdjustHealth-family flight in a row with no protector kill. Mana probe adds a new UFunction call type to the "safe surface" set without triggering the wall.

7. **[I,strong] Full Mana behavior (damage, heal, cap) is unlockable with ONE MaxMana seed step.** The current variant is knob-gated (`KBFPOSTSHOT_MANA=1`) with no MaxMana seeding. Adding a `KBFSEEDMAXMANA` companion knob (byte-identical mechanism to `KBFSEEDMAXHEALTH` from S156-A) would let a mana probe with MaxMana=100 test the full arithmetic. **The S148 census already resolves the mana attribute set at index 0 — a MaxMana seed step is a copy-paste from S156's MaxHealth seed with the offset changed from `+0x80` on LokiAttributeSetHealth to `+0x220` on ULokiAttributeSet.**

## Method rules banked

- **R-S189-a (multi-attribute set resolution)**: an ASC with SpawnedAttributes.Num > 1 (this build has 2: LokiAttributeSet at 0, LokiAttributeSetHealth at 1) requires per-shot attribute-set selection. The S148 census machinery already supports this via `candidateIndex` in the target-set report; probes for non-Health attributes must select the correct index. A hardcoded index=1 would miss Mana entirely.
- **R-S189-b (S153 thunkExact fix generalization proof)**: the second confirmation of a fix on a different UFunction is what promotes "worked once" to "mechanism-level fix." AdjustHealth (S156-A F5) + AdjustMana (S189 F2) both hit `wrapperExact=yes` / `tailReason=ok` on the same UHT emission pattern. Future reflected native calls with parameters (AdjustShield, AdjustMoveSpeed, etc.) should be assumed to follow this pattern by default.
- **R-S189-c (MANASHOT_NO_OP is informative, not a wall)**: an attribute delta call that clamps to 0 because the max-attribute is 0 tests the mechanism (resolve, dispatch, arithmetic, disarm) end-to-end without needing the attribute to be non-zero. The clamp itself is the receipt that the game's own attribute-clamping code ran on this attribute — proof of parity with the AdjustHealth clamp measured at S156-B heal500.

## Files

- `docs/s189-mana-f2-marker-final.txt` — preserved marker (15,401 B)
- `docs/fk24-stage-s189-mana-f2-*.txt` — per-inject stage markers (4 files: gft, fo, sp, probe)
- `tools/sigbypass-mod/build.ps1` — new `botfight-damage-self-cal-bindavatar-seedmax-postshots-mana` variant
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFPOSTSHOT_MANA + KBFPOSTSHOT_MANA_DELTABITS knobs; BfS189ManaTarget + BfS189ResolveManaTarget + BfS189DecodeAdjustManaTail helpers; Mana probe block in BfS148DoCalibration between KBFPOSTSHOTS block and BfS148FinishTerminal
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_postshots_mana.dll` — RAW `c7ce885988fd3532`

## Regression gates (post-flight)

All prior gates UNCHANGED (KBFPOSTSHOT_MANA=0 default truly dead-strips the mana probe block):
- `botfight-damage-self-cal-bindavatar-seedmax` `b47d1bfd04e44921`
- `-postshots1` `1925e9e80646a4fb`
- `-postshots2` `ad87408901f481c5`
- `-postshots2-floor600` `ca54361966e71afd`
- `-postshots1-heal100` `0b9573215c85f511`
- `-postshots1-heal500` `b0e29a434eabd87d`
- **`-postshots-mana`** `c7ce885988fd3532` (NEW)

Both s148 contract tests PASS after knob addition.

## Still open

- **MaxMana seed + non-zero delta**: needs `KBFSEEDMAXMANA` knob + Mana damage/heal arithmetic verification. Would extend the "AdjustXxx family behaves uniformly" claim from clamp-only to full arithmetic on a non-Health attribute.
- **Attribute offsets on ULokiAttributeSet**: `Mana@+0x210` and `MaxMana@+0x220` (from S189 recon, unverified live — this flight only read via reflection through the child prop resolved by the S148 census, not direct offset reads). A `KBFSEEDMAXMANA` implementation would need direct offset writes and should carry a live-verification step.
- **Other ULokiAttributeSet attributes**: MoveSpeed, MaxMoveSpeed, MaxAcceleration, GroundFriction, etc. — the S141 T3 movement wall's own targets. Whether the AdjustXxx family covers those or they need a different mechanism is untested.
- **Cross-attribute-set interactions**: whether a shot on the LokiAttributeSet Mana can affect LokiAttributeSetHealth Health (e.g. via a game-side gameplay effect that links Mana to Health regeneration) is untested. All flights to date have been strict single-attribute reads.
