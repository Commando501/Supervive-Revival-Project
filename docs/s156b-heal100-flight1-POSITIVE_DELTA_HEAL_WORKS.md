# S156-B postshots1-heal100 flight 1 — positive delta (heal) accepted by AdjustHealth; 750 → 850 exact

**Date:** 2026-09-08 (~20:28-20:32)
**Session:** S156-B heal test (positive-delta follow-up to postshots2-floor600 at commit `d55e999`)
**Base commit:** `d55e999` (S156-B postshots2-floor600 FLOOR_FIRES_AS_DESIGNED)
**Verdict:** ★★★★★★ **[M] The game's `AdjustHealth` native path accepts positive-valued deltas and applies them correctly.** SHOT_2 with delta=+100.0f healed the hero from 750 → 850 HP, byte-exact arithmetic, no cap interaction (finalHP well below MaxHealth=1000). No FK-32.

## Delta from postshots1

Two edits vs the postshots1 baseline:
1. **`tools/sigbypass-mod/tutorial_launch.cpp`** — added `KBFPOSTSHOT_DELTABITS` knob (default `0xC37A0000u` = -250.0f, preserving prior behavior byte-for-byte), and replaced the hardcoded `postDeltaBits=0xC37A0000u` const with `postDeltaBits=(uint32_t)KBFPOSTSHOT_DELTABITS`
2. **`tools/sigbypass-mod/build.ps1`** — new variant `botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal100` overriding `-DKBFPOSTSHOT_DELTABITS=0x42C80000u` (= +100.0f)

**Critical regression property:** because `KBFPOSTSHOT_DELTABITS` defaults to the exact bits the old hardcoded const held, all 4 prior variants rebuild BYTE-IDENTICAL to their committed digests:

| variant | RAW | status |
|---|---|---|
| `botfight-damage-self-cal-bindavatar-seedmax` | `b47d1bfd04e44921` | UNCHANGED ✓ |
| `botfight-damage-self-cal-bindavatar-seedmax-postshots1` | `1925e9e80646a4fb` | UNCHANGED ✓ |
| `botfight-damage-self-cal-bindavatar-seedmax-postshots2` | `ad87408901f481c5` | UNCHANGED ✓ |
| `botfight-damage-self-cal-bindavatar-seedmax-postshots2-floor600` | `ca54361966e71afd` | UNCHANGED ✓ |
| **`botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal100`** | **`0b9573215c85f511`** | **NEW, flown F1** |

Both `s148_build_contract_test.ps1` and `s148_damage_calibration_test.exe` PASS.

## Flight ledger

| flight | outcome |
|---|---|
| **F1** | **SUCCESS** — first try, all predictions hit exact |

**Session cost:** 1 launch. Fourth consecutive first-try success on well-designed within-family follow-ups (postshots2 F1, floor600 F1, heal100 F1; postshots1 F3 needed 3 launches due to FK-31 variance).

## Receipts

Full marker: `docs/s156b-heal100-f1-marker-final.txt`

### Primary S148 shot (contract preserved verbatim)
```
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000
       immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=266ms callCount=1
```
Same shape as every prior S156-A/S156-B flight. Primary shot is -250 damage (1000→750) — the S148 arm's own hardcoded value at `tutorial_launch.cpp:22077` (the primary shot's delta is UNRELATED to KBFPOSTSHOT_DELTABITS which only affects the post-loop).

### SHOT_2 heal (750 → 850)
```
[S189] SHOT_2 PRECHECK preBits=443B8000/443B8000 preHP=750.00 floorBits=43960000 continuityOK=yes
[S189] SHOT_2 CALL_ISSUED deltaBits=42C80000 deltaHP=100.00 callCount=2
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] SHOT_2 POST postBits=44548000/44548000 postHP=850.00 observedDeltaHP=+100.00 arithmeticOK=yes rvalBits=00000000 identityStable=yes issues=0x0
```
- **`deltaBits=42C80000 deltaHP=100.00`** — positive delta printed correctly (marker format handles positive AND negative float bits)
- **`observedDeltaHP=+100.00 arithmeticOK=yes`** — exact positive arithmetic, matches requested delta
- **`postBits=44548000 postHP=850.00`** — 750 + 100 = 850, well below MaxHealth 1000
- **`floorBits=43960000`** (300) — floor still present but never checked-against for a heal since positive delta cannot cross downward; the check is `preCurrent <= floorBits`, and preCurrent=750 > 300 passes as usual
- **`identityStable=yes issues=0x0`** — ASC pointer unchanged across the operation, no new S148 blockers detected

### POSTSHOTS_COMPLETE + clean disarm
```
[S189] POSTSHOTS_COMPLETE fired=1 requested=1 aborted=no reason=none finalBits=44548000/44548000 finalHP=850.00
[FS] disarm: restored=17563 of 17563 swapped
[BF] worker done (hits=104 hitsGT=104)
```

100% funcswap restoration. `hits=104` normal cadence.

## What this settles

1. **[M] Positive delta to AdjustHealth works.** `+100.0f` was accepted, applied, and readback-confirmed to exact arithmetic. No sign-check rejection, no absolute-value coercion, no zero-clamp on positive input.

2. **[M] AdjustHealth is polarity-symmetric within the tested range.** Same wrapper + same handles + same OnPI dispatch path — only sign of delta differs vs prior flights. Both directions produce byte-exact arithmetic. Suggests AdjustHealth internally does something like `NewHealth = CurrentHealth + Delta` without a directional branch.

3. **[M] AdjustHealth writes BOTH Base and Current for a heal too.** Prior flights showed both slots go to the same value on damage; this flight shows the same for heal (`postBits=44548000/44548000` — both slots = 850).

4. **[M] KBFPOSTSHOT_DELTABITS knob is byte-additive to the arm design.** Adding the knob with default = prior hardcoded value produced zero drift on any of the 4 prior gate variants. The knob composes cleanly with the existing KBFPOSTSHOTS + KBFPOSTSHOT_FLOORBITS knobs.

5. **[M] No FK-32 within post-flight window.** Fifth AdjustHealth-family flight in a row with no delayed protector kill.

6. **[M] The heal test does NOT touch cap behavior.** Final HP=850 is 150 below MaxHealth 1000. Whether AdjustHealth clamps at MaxHealth remains OPEN — would need an overshoot variant (e.g. `+500` on a 750-HP hero would probe 750+500=1250 vs MaxHealth 1000).

## Method notes

- **Same-signature float negation is a free A/B**. The `-250 → +100` change here is just flipping the sign bit and adjusting magnitude, all in the compile-time `#define`. If the game rejected positive deltas via NaN, sign check, or MSVC exception, we'd see either FAULTED, arithmeticOK=NO, or a null delta. None of those happened.
- **Round-trip float printing under mixed sign works correctly.** The `bitsToHP` helper (which does `memcpy(&f,&b,4)` to bit-cast uint32→float) produced `+100.00` for `0x42C80000` and would produce `-100.00` for `0xC2C80000`. The marker printer handles both signs correctly with `%+.2f`.

## Files

- `docs/s156b-heal100-f1-marker-final.txt` — preserved marker
- `docs/fk24-stage-s156b-heal100-f1-*.txt` — per-inject markers
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFPOSTSHOT_DELTABITS knob + call-site substitution
- `tools/sigbypass-mod/build.ps1` — `botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal100` variant
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_postshots1_heal100.dll` — RAW `0b9573215c85f511`

## Still open

- **MaxHealth cap** — untested. Would need overshoot delta (e.g. `+500` on 750-HP hero) or seed Health to near-max before applying positive delta.
- **Zero-crossing** — still blocked by static_assert on KBFPOSTSHOTS ≤ 2 (unrelated to heal test).
- **Fractional deltas** — nothing tested a delta like `+37.5`, though the knob is 32-bit float bits so it would trivially work.
- **Mixed damage+heal within one arm** — the loop applies the SAME delta to all post-shots; a variant with per-shot delta customization would test this.
- **Non-Health attributes** — Mana, Shield, etc. untested.
- **Multi-hero** — one hero class tested throughout this arc.
