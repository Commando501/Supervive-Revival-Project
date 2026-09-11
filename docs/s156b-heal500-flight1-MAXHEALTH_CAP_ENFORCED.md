# S156-B postshots1-heal500 flight 1 — MaxHealth cap silently clamps overshoot; game enforces the 1000 HP ceiling

**Date:** 2026-09-08 (~20:39-20:43)
**Session:** S156-B MaxHealth cap test (overshoot follow-up to postshots1-heal100 at commit `315f613`)
**Base commit:** `315f613` (S156-B heal100 POSITIVE_DELTA_HEAL_WORKS)
**Verdict:** ★★★★★★ **[M] The game's `AdjustHealth` native path CLAMPS silently at MaxHealth.** SHOT_2 requested +500 heal from a 750 HP baseline; game APPLIED only +250 (the exact amount needed to reach MaxHealth 1000), leaving `arithmeticOK=NO` and `postHP=1000.00`. No fault, no error state, no S148 blocker — the clamp is a silent invariant enforcement, not a rejection.

## Delta from heal100

Single build.ps1 variant addition; ZERO source changes (KBFPOSTSHOT_DELTABITS knob already exists from heal100 arc).

**Arms:**

| variant | RAW | delta | expected trajectory |
|---|---|---|---|
| `postshots1-heal100` | `0b9573215c85f511` | +100 | 750 → 850 (below cap) |
| **`postshots1-heal500` (flown F1)** | **`b0e29a434eabd87d`** | **+500** | **750 → 1250 requested / 1000 landed (cap)** |

## Flight ledger

| flight | outcome |
|---|---|
| **F1** | **SUCCESS** — first try. Fifth consecutive within-family follow-up landing first try (postshots2, floor600, heal100, heal500). |

**Session cost:** 1 launch.

## Receipts

Full marker: `docs/s156b-heal500-f1-marker-final.txt`

### Primary S148 shot (contract preserved verbatim)
```
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000
       immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=266ms callCount=1
```

### SHOT_2 heal500 with CAP FIRE
```
[S189] SHOT_2 PRECHECK preBits=443B8000/443B8000 preHP=750.00 floorBits=43960000 continuityOK=yes
[S189] SHOT_2 CALL_ISSUED deltaBits=43FA0000 deltaHP=500.00 callCount=2
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] SHOT_2 POST postBits=447A0000/447A0000 postHP=1000.00 observedDeltaHP=+250.00 arithmeticOK=NO rvalBits=00000000 identityStable=yes issues=0x0
```
- **`deltaBits=43FA0000 deltaHP=500.00`** — requested delta +500 correctly encoded and printed
- **`postHP=1000.00`** — landed at EXACTLY MaxHealth 1000, not the requested 1250
- **`observedDeltaHP=+250.00 arithmeticOK=NO`** — the game APPLIED only +250 (the exact delta needed to reach MaxHealth from the 750 pre-value), NOT the +500 requested
- **`postBits=447A0000/447A0000`** — both Base and Current clamped to MaxHealth 1000, matching the seeded `MaxHealthBits=447A0000` value exactly
- **`identityStable=yes issues=0x0`** — no fault, no attribute-set change, no S148 blocker fired
- **`rvalBits=00000000`** — return value untouched, no signal from AdjustHealth about the clamp

### POSTSHOTS_COMPLETE + clean disarm
```
[S189] POSTSHOTS_COMPLETE fired=1 requested=1 aborted=no reason=none finalBits=447A0000/447A0000 finalHP=1000.00
[FS] disarm: restored=17563 of 17563 swapped
[BF] worker done (hits=103 hitsGT=103)
```
- **`aborted=no reason=none`** — the arm's post-loop does NOT treat the clamp as a fault. The `arithmeticOK=NO` is captured in SHOT_2 POST, but does NOT set aborted or a specific reason. Loop continues cleanly.
- **`fired=1 requested=1`** — the shot DID execute and DID commit (health changed 750→1000); it's not counted as a failed shot even though the delta was clamped.
- 100% funcswap restoration.

## What this settles

1. **[M] The game clamps AdjustHealth at MaxHealth.** Requested +500 on a hero with MaxHealth=1000 and current=750 → applied only +250. Silent enforcement at exactly the invariant boundary (current ≤ MaxHealth). No overshoot, no invariant violation.

2. **[M] The clamp is silent to the caller.** No fault (`identityStable=yes`), no error bit (`issues=0x0`), no return-value signal (`rvalBits=0`). The only way to detect the clamp is to observe that `observedDeltaHP ≠ requestedDeltaHP` — which our arm's `arithmeticOK` field captures explicitly. **In production game code, a Blueprint calling AdjustHealth with a large heal delta would never know its heal was capped unless it read Health before AND after and compared to the requested delta.**

3. **[M] Both Base and Current are updated together for a capped heal too.** `postBits=447A0000/447A0000` — both slots go to 1000 exactly. Consistent with prior findings: AdjustHealth writes the two slots as a unit, not just Current.

4. **[M] The MaxHealth reference used for clamping = the value written by S156 seed.** MaxHealth was seeded to `0x447A0000 = 1000` by KBFSEEDMAXHEALTH; the clamp lands at exactly that value. This settles that the game reads MaxHealth from the same attribute-set slot S156 writes to (`+0x80 = LokiAttributeSetHealth::MaxHealth`), NOT from a hidden/cached copy that S156 didn't touch. If the game cached MaxHealth elsewhere, the clamp would land at that cached value (not the seeded 1000).

5. **[M] `arithmeticOK=NO` is a working signal.** The arm's per-shot arithmetic check correctly caught the delta mismatch (`observedDeltaHP=+250 ≠ postDeltaHP=+500`). This validates the FP-epsilon comparison logic (`observedDeltaHP > postDeltaHP-0.01 && observedDeltaHP < postDeltaHP+0.01` returned false for a ±250 mismatch). Prior flights all had `arithmeticOK=yes`; this is the first `NO` result and the arm correctly captured it.

6. **[M] The loop treats "arithmetic failed but no fault" as continue.** POSTSHOTS_COMPLETE `aborted=no reason=none` even though `arithmeticOK=NO`. This is the correct behavior for a clamp — the shot committed (Health changed), the game accepted the call, only the magnitude differed. A hypothetical N=2 heal500 arm would fire SHOT_3 next, which would see preHP=1000 (SHOT_2's clamped post), and either heal again (another clamp) or fault.

7. **[M] No FK-32.** Sixth AdjustHealth-family flight in a row with no delayed protector kill. Overshoot did NOT trigger any downstream event (e.g. "hero at full HP" cue) that could hit WALL P.

## Within-family sweep now spans damage AND heal with cap+floor coverage

| variant | delta | pre | post | observedDelta | arithmeticOK | mechanism exercised |
|---|---|---|---|---|---|---|
| `postshots1` | -250 | 750 | 500 | -250 | yes | damage below floor guard |
| `postshots2` | -250 | 750→500→250 | 250 | -250 (both shots) | yes (both) | multi-shot damage |
| `postshots2-floor600` | -250 | 500 (SHOT_3 refused) | 500 | n/a (floor) | n/a | floor guard fires |
| `postshots1-heal100` | +100 | 750 | 850 | +100 | yes | heal below cap |
| **`postshots1-heal500`** | **+500** | **750** | **1000** | **+250 (clamped)** | **NO** | **MaxHealth cap fires** |

Every within-family delta is single-variable; every predicted receipt hit exact (including the predicted possibility of "cap fires" for heal500). The KBFPOSTSHOTS / KBFPOSTSHOT_FLOORBITS / KBFPOSTSHOT_DELTABITS knob triad now has full-coverage empirical validation.

## Method notes

- **A predicted alternative outcome IS a valid A/B result.** Before flight, I explicitly wrote: "If AdjustHealth clamps: observedDelta = +250 (not +500), arithmeticOK=NO, postHP=1000. If it doesn't: observedDelta = +500, arithmeticOK=yes, postHP=1250." The actual result matched the clamp branch of that prediction. Recording BOTH branches BEFORE the flight is what turns the actual observation into a measurement, not a post-hoc rationalization.
- **The clamp behavior tells us about the game's MaxHealth INVARIANT.** The game maintains `Current ≤ MaxHealth` as a hard invariant enforced at the AdjustHealth level. This is a common GAS pattern (attribute clamping in `PreAttributeChange` or `PostAttributeChange` hooks) — and this flight confirms it works in this build for the Health/MaxHealth pair.
- **Silent-clamp semantics have implications for cheat detection.** If a cheat DLL wrote Health directly (bypassing AdjustHealth), the invariant would be violated visibly (Health > MaxHealth). Because AdjustHealth clamps silently, using it as the mutation path is more robust to anti-cheat "invariant sweeps" than direct writes.

## Files

- `docs/s156b-heal500-f1-marker-final.txt` — preserved marker
- `docs/fk24-stage-s156b-heal500-f1-*.txt` — per-inject markers
- `tools/sigbypass-mod/build.ps1` — new `botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal500` variant (single-line addition)
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_postshots1_heal500.dll` — RAW `b0e29a434eabd87d`

**No source code changes** vs heal100 (commit `315f613`). Pure build.ps1 variant addition (KBFPOSTSHOT_DELTABITS override).

## Regression gates (post-flight)

All prior gates UNCHANGED:
- `botfight-damage-self-cal-bindavatar-seedmax` `b47d1bfd04e44921`
- `botfight-damage-self-cal-bindavatar-seedmax-postshots1` `1925e9e80646a4fb`
- `botfight-damage-self-cal-bindavatar-seedmax-postshots2` `ad87408901f481c5`
- `botfight-damage-self-cal-bindavatar-seedmax-postshots2-floor600` `ca54361966e71afd`
- `botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal100` `0b9573215c85f511`
- **`botfight-damage-self-cal-bindavatar-seedmax-postshots1-heal500`** `b0e29a434eabd87d` NEW

## Still open

- **Undershoot cap (below 0 HP)** — still blocked by static_assert on KBFPOSTSHOTS ≤ 2 combined with the safety floor. Would need explicit floor override + N≥3 + FK-32 watch.
- **Mixed damage+heal in one arm** — the loop applies the SAME delta to all post-shots.
- **Non-Health attributes** — Mana, Shield, etc.
- **Multi-hero** — one hero class tested throughout.
- **Post-clamp SHOT_3 behavior** — would the second clamped call fault? Or heal to 1000 again (no-op)? Untested. A `postshots2-heal500` variant would exercise this.
