# S156-B postshots2-floor600 flight 1 — safety floor fires cleanly at SHOT_3, N=2 loop terminates gracefully

**Date:** 2026-09-08 (~20:16-20:20)
**Session:** S156-B postshots2-floor600 (floor-firing follow-up to postshots2 N=2 at commit `001657f`)
**Base commit:** `001657f` (S156-B postshots2 N2_BACK_TO_BACK_THREE_ADJUSTHEALTH_CALLS)
**Verdict:** ★★★★★★ **[M] The safety floor branch fires cleanly and the post-loop terminates gracefully at the right point.** SHOT_2 fired normally (750→500). SHOT_3 hit FLOOR_REACHED at PRECHECK (preHP=500 ≤ floorHP=600) — POST never emitted, no CallNativeGuarded invocation, no arithmetic. POSTSHOTS_COMPLETE emitted with `fired=1 requested=2 aborted=yes reason=floor finalHP=500.00`. Clean disarm, no FK-32.

## Delta from postshots2

Single-variable delta: `-DKBFPOSTSHOT_FLOORBITS=0x44160000u` (= 600.0f, up from the default 300.0f = 0x43960000u). N=2 unchanged. Zero source changes.

**Arms:**

| variant | RAW `.text` | role |
|---|---|---|
| `botfight-damage-self-cal-bindavatar-seedmax-postshots1` | `1925e9e80646a4fb` | N=1, floor=300 (default), floor silent |
| `botfight-damage-self-cal-bindavatar-seedmax-postshots2` | `ad87408901f481c5` | N=2, floor=300 (default), floor silent |
| **`botfight-damage-self-cal-bindavatar-seedmax-postshots2-floor600` (flown F1)** | **`ca54361966e71afd`** | **N=2, floor=600, floor fires** |

All 5 variant hashes (including parent + base) unique. Parent regression gates all held.

## Discriminator design

Floor value chosen from the range `(500, 750)` — must be > SHOT_3's pre (500) so it fires there, but < SHOT_2's pre (750) so SHOT_2 fires normally as within-run control. **600 HP** picked as a clean round value well inside the discriminator range.

The prior `postshots2` flight established that N=2 fires 3 consecutive AdjustHealth calls (primary + SHOT_2 + SHOT_3) all successfully. This flight uses the IDENTICAL code path but pushes the floor above SHOT_3's pre-value to gate that shot before it fires — a controlled negative on the SHOT_3 arithmetic path, and a controlled positive on the FLOOR_REACHED branch.

## Flight ledger

| flight | outcome |
|---|---|
| **F1** | **SUCCESS** — first try, all predictions hit exact |

**Session cost:** 1 launch. Continues the "well-designed follow-up lands first try" pattern (postshots2 F1 also succeeded first try).

## Receipts

Full marker: `docs/s156b-postshots2-floor600-f1-marker-final.txt`

### Primary S148 shot (contract preserved verbatim)
```
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000 immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=266ms callCount=1
```
Same shape as postshots1/postshots2/S156-A F5. callCount=1 pinned.

### SHOT_2 fires normally (within-run control)
```
[S189] SHOT_2 PRECHECK preBits=443B8000/443B8000 preHP=750.00 floorBits=44160000 continuityOK=yes
[S189] SHOT_2 CALL_ISSUED deltaBits=C37A0000 deltaHP=-250.00 callCount=2
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] SHOT_2 POST postBits=43FA0000/43FA0000 postHP=500.00 observedDeltaHP=-250.00 arithmeticOK=yes rvalBits=00000000 identityStable=yes issues=0x0
```
- `floorBits=44160000` decodes correctly (0x44160000 = 600.0f, floorHP=600.00 shown in SHOT_3 line)
- SHOT_2 pre=750.00 > 600 floor → PRECHECK passes → shot fires → landing at 500.00 exact
- **This is the within-run control**: the same code path that emits FLOOR_REACHED for SHOT_3 fires normally for SHOT_2 whose pre is above the floor.

### SHOT_3 FLOOR_REACHED (the target measurement)
```
[S189] SHOT_3 FLOOR_REACHED preBits=43FA0000/43FA0000 preHP=500.00 floorBits=44160000 floorHP=600.00
```
- **preHP=500.00 ≤ floorHP=600.00** → `(preCurrent & 0x80000000) || (preCurrent <= floorBits)` → the second disjunct fires
- **No SHOT_3 CALL_ISSUED, no CallNativeGuarded invocation, no arithmetic** — the loop `break`s at the floor check before any game-side call
- Floor value 600 decodes back correctly (`0x44160000` → `600.00`), confirming the `KBFPOSTSHOT_FLOORBITS` compile-time constant flows through the marker printer without corruption

### POSTSHOTS_COMPLETE terminal state
```
[S189] POSTSHOTS_COMPLETE fired=1 requested=2 aborted=yes reason=floor finalBits=43FA0000/43FA0000 finalHP=500.00
```
- `fired=1` (SHOT_2 completed) vs `requested=2` (KBFPOSTSHOTS=2) — the differential correctly counts
- `aborted=yes reason=floor` — the specific abort reason is preserved
- `finalHP=500.00` — end state is SHOT_2's post-value, NOT the 250 that N=2 without floor would reach

### Clean disarm
```
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan ... ms, 34253 UFunctions live)
[BF] worker done (hits=101 hitsGT=101)
```
100% funcswap restoration. Even after floor-abort, the arm's cleanup path is clean.

## What this settles

1. **[M] The KBFPOSTSHOT_FLOORBITS check works correctly.** `preCurrent (0x43FA0000) <= floorBits (0x44160000)` fires the FLOOR_REACHED branch as designed. Unsigned comparison of positive-normal float bit patterns is equivalent to float value comparison (IEEE 754 property) — the code takes advantage of this.

2. **[M] The floor value round-trips through the marker printer.** `KBFPOSTSHOT_FLOORBITS=0x44160000u` compile-time constant emerges as `floorHP=600.00` in the SHOT_3 FLOOR_REACHED line's `bitsToHP()` call. Two-way validation: bits→float conversion produces the same value the source `#define` intended.

3. **[M] Loop termination on floor is graceful.** The `break` exits the for-loop cleanly, control falls through to `POSTSHOTS_COMPLETE` with `aborted=yes reason=floor`, then `BfS148FinishTerminal()` runs the standard cleanup path. No fault, no stuck state, no partial-invalid write, no re-entry hazard.

4. **[M] The within-run control (SHOT_2) validates the mechanism is otherwise identical.** SHOT_2's PRECHECK/CALL_ISSUED/POST triple fires exactly as it does in postshots2 (which had no floor firing). The `floorBits=44160000` field is present in SHOT_2's PRECHECK line but the check simply passes (750 > 600); the same field appears in SHOT_3's FLOOR_REACHED line and the check fires (500 ≤ 600). One field, two check outcomes, correct in both cases.

5. **[M] Three-flight within-family series is now closed for the KBFPOSTSHOTS 0..2 range.**

   | variant | N | floor | shots fired | trajectory | aborted |
   |---|---|---|---|---|---|
   | postshots1 | 1 | 300 | 1 (SHOT_2) | 1000→750→500 | no |
   | postshots2 | 2 | 300 | 2 (SHOT_2, SHOT_3) | 1000→750→500→250 | no |
   | postshots2-floor600 | 2 | 600 | 1 (SHOT_2) | 1000→750→500 | yes reason=floor |

   Each variant differs from the last by a single-variable delta (N or floor). Every predicted receipt hit exact. Every within-run control passed. **The KBFPOSTSHOTS/KBFPOSTSHOT_FLOORBITS design is now empirically complete for its declared parameter range.**

6. **[M] No FK-32 within the post-flight window.** Game alive 6.7min post-flight (fourth AdjustHealth-family flight in a row with no delayed protector kill: S156-A F5 = 51.9min, postshots1 F3 = 30.6min, postshots2 F1 = 16.5min, postshots2-floor600 F1 = 6.7min+ ongoing).

## Method notes

- **Within-family sweeps with single-variable deltas produce the cleanest evidence.** Each flight in the postshots1 → postshots2 → postshots2-floor600 series changes ONE compile-time constant (KBFPOSTSHOTS or KBFPOSTSHOT_FLOORBITS). All other bytes identical. Comparison across the three isolates the effect of that one constant, which is why every prediction hits exact.
- **A silent guardian's fire test is a natural follow-up.** postshots1 and postshots2 both had the floor armed-but-silent. The floor600 flight exercises the branch that had only been code-covered. This is not a "different feature" — it's the same feature at a different parameter value.
- **Floor overrides via `-D` are cheaper than static_assert relaxation.** N≥3 would cross zero HP and requires the static_assert change, plus a FK-32 watch. Testing the floor by raising ITS value from below (rather than pushing N above) achieved the same "fire the safety branch" outcome with none of that risk.

## Files

- `docs/s156b-postshots2-floor600-f1-marker-final.txt` — preserved marker
- `docs/fk24-stage-s156b-postshots2-floor600-f1-*.txt` — per-inject markers
- `tools/sigbypass-mod/build.ps1` — new `botfight-damage-self-cal-bindavatar-seedmax-postshots2-floor600` variant
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_postshots2_floor600.dll` — RAW `ca54361966e71afd`

**No source code changes** vs postshots2 (commit `001657f`). Single build.ps1 variant addition.

## Regression gates

- **`botfight-damage-self-cal-bindavatar-seedmax`** RAW `b47d1bfd04e44921` — UNCHANGED
- **`botfight-damage-self-cal-bindavatar-seedmax-postshots1`** RAW `1925e9e80646a4fb` — UNCHANGED
- **`botfight-damage-self-cal-bindavatar-seedmax-postshots2`** RAW `ad87408901f481c5` — UNCHANGED
- **`botfight-damage-self-cal-bindavatar-seedmax-postshots2-floor600`** RAW `ca54361966e71afd` — NEW, flown

## Still open

- **Zero-crossing** — N≥3 blocked by static_assert. Would need explicit override + FK-32 watch.
- **Positive delta (heal)** — needs source support for a per-shot delta parameter.
- **Multi-hero** — one hero class tested.
- **Non-Health attribute mutation** — e.g. Mana, Shield — untested paths.
