# S156-B postshots2 flight 1 — three back-to-back AdjustHealth calls all commit correctly (1000 → 750 → 500 → 250)

**Date:** 2026-09-08 (~20:04-20:07)
**Session:** S156-B postshots2 (N=2 follow-up to postshots1 N=1 at commit `3e7ac45`)
**Base commit:** `3e7ac45` (S156-B postshots1 F3 BACK_TO_BACK_ADJUSTHEALTH_WORKS)
**Verdict:** ★★★★★★ **[M] Three consecutive `AdjustHealth(-250)` calls, one per OnPI dispatch, all commit correctly with byte-exact arithmetic.** Health goes 1000 → 750 → 500 → 250. Final state is BELOW the 300 HP safety floor value, proving the code path handled "dangerous territory" cleanly. No FK-32 within 90s+ of POSTSHOTS_COMPLETE (game alive 10.9min post-flight).

## Delta from postshots1

Single build.ps1 variant addition; ZERO source changes; the KBFPOSTSHOTS knob semantics (0..2) were already implemented and exercised for N=1 in the prior arc.

**Arms:**

| variant | RAW `.text` | VSIZE `.text` | role |
|---|---|---|---|
| `botfight-damage-self-cal` (S153 gate) | `167d1552c73bfd7a` | | base regression |
| `botfight-damage-self-cal-bindavatar` (S155 gate) | `d8c08912816162a7` | | bind-only |
| `botfight-damage-self-cal-bindavatar-seedmax` (S156-A gate) | **`b47d1bfd04e44921`** | `f87ac23d7c1a4c05` | parent, KBFPOSTSHOTS=0 default |
| `botfight-damage-self-cal-bindavatar-seedmax-postshots1` (S156-B N=1 gate) | `1925e9e80646a4fb` | `66252fd5355723cb` | postshots1 |
| **`botfight-damage-self-cal-bindavatar-seedmax-postshots2` (S156-B N=2, flown F1)** | **`ad87408901f481c5`** | **`0f943e08f05e0e2b`** | **new** |

All 5 distinct. Parent unchanged after all edits (regression gate held).

## Flight ledger

| flight | outcome | notes |
|---|---|---|
| **F1** | **SUCCESS** — first try | Compare to postshots1 which took 3 launches |

**Session cost:** 1 launch. No FK-31 hazard fired this attempt. Total session across S156-A (5 launches for F5 success) + S156-B postshots1 (3 launches for F3 success) + S156-B postshots2 (1 launch for F1 success) = **9 launches, 3 landings** = 33% success rate, consistent with FK-31's documented 27% base rate.

## Receipts (from `docs/s156b-postshots2-f1-marker-final.txt`)

### Primary S148 shot (contract preserved verbatim)
```
[S148] target set=... HealthBits=00000000/00000000 MaxBits=447A0000/447A0000 ... issues=0x0
[S148] seed originalBits=00000000/00000000 readbackBits=447A0000/447A0000 faulted=no identityStable=yes exact=yes
[S148] CALL_ISSUED AdjustHealth HealthDeltaBits=C37A0000 callCount=1
[S189] POSTSHOTS_ARMED planned=2 adjustFn=0x0000015F84166E40 adjustThunk=0x00007FF6933F4270 adjustChild=0x0000015F810E5600 deltaOff=0
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S148] immediate return issues=0x0 identityStable=yes HealthBits=443B8000/443B8000 receipt=yes; returning to game until notBefore=... timeout=...
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000 immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=359ms callCount=1
```
Primary: 1000 → 750, elapsed=359ms, callCount=1 (contract line UNCHANGED from S156-A F5 & postshots1 F3).

### SHOT_2 (750 → 500)
```
[S189] SHOT_2 PRECHECK preBits=443B8000/443B8000 preHP=750.00 floorBits=43960000 continuityOK=yes
[S189] SHOT_2 CALL_ISSUED deltaBits=C37A0000 deltaHP=-250.00 callCount=2
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] SHOT_2 POST postBits=43FA0000/43FA0000 postHP=500.00 observedDeltaHP=-250.00 arithmeticOK=yes rvalBits=00000000 identityStable=yes issues=0x0
```
- **continuityOK=yes** (SHOT_2 pre 750 = primary later 750)
- **observedDeltaHP=-250.00 arithmeticOK=yes** (exact match to requested delta)
- **postHP=500.00** exactly

### SHOT_3 (500 → 250) — FIRST-EVER 3-consecutive-call sequence
```
[S189] SHOT_3 PRECHECK preBits=43FA0000/43FA0000 preHP=500.00 floorBits=43960000 continuityOK=yes
[S189] SHOT_3 CALL_ISSUED deltaBits=C37A0000 deltaHP=-250.00 callCount=3
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] SHOT_3 POST postBits=437A0000/437A0000 postHP=250.00 observedDeltaHP=-250.00 arithmeticOK=yes rvalBits=00000000 identityStable=yes issues=0x0
```
- **continuityOK=yes** (SHOT_3 pre 500 = SHOT_2 post 500) — no game-side deferred write across two OnPI dispatches
- **observedDeltaHP=-250.00 arithmeticOK=yes** (exact match)
- **postHP=250.00** exactly — this is where the interesting territory starts

### POSTSHOTS_COMPLETE + clean disarm
```
[S189] POSTSHOTS_COMPLETE fired=2 requested=2 aborted=no reason=none finalBits=437A0000/437A0000 finalHP=250.00
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan ... ms, 34253 UFunctions live)
[BF] worker done (hits=21 hitsGT=21)
```

100% funcswap restoration (17,563/17,563). `hits=21` low (vs postshots1 F3's `hits=95`, S156-A F5's `hits=117`) — this flight had a faster path to disarm once the WAIT_LATER OnPI dispatch arrived.

## What this settles

1. **[M] N=2 works end-to-end.** Three consecutive AdjustHealth invocations in one arm lifecycle: primary + SHOT_2 + SHOT_3. Every arithmetic check passes exactly. Every continuity check passes exactly. Every identity check passes exactly.

2. **[M] Cross-dispatch continuity holds across at least 3 dispatches.** Primary shot's result was visible to SHOT_2's PRECHECK re-resolve. SHOT_2's result was visible to SHOT_3's PRECHECK re-resolve. The game commits AdjustHealth mutations synchronously with each dispatch's return — no queue, no reconciliation, no deferred write across multiple dispatch cycles.

3. **[M] AdjustHealth is deterministic across repeated invocations on the same target.** Three −250 deltas produce three −250 outcomes. No cumulative error, no drift, no clamp interference. Both Base and Current are updated identically on every call.

4. **[M] The 300 HP safety floor is CODE-COVERED and behaves correctly as a "silent guardian".** Both SHOT_2 pre (750) and SHOT_3 pre (500) were above the 300 floor, so the FLOOR_REACHED branch did NOT fire — exactly the expected behavior. The floor is only meant to REFUSE shots whose pre-value ≤ floor; both shots passed, both fired. **A hypothetical SHOT_4 with pre=250 would trigger FLOOR_REACHED** — that branch remains architecturally present but not fire-tested. To exercise it would need static_assert relaxation (currently blocks N≥3).

5. **[M] Landing at 250 HP (below the floor value) is SAFE.** The floor guards PRE-shot only, so a shot whose post-value crosses below the floor is expected. Game continued running normally, no FK-32, no visible ill-effect.

6. **[M] No FK-32 within 90s+ of POSTSHOTS_COMPLETE.** Verified live: game PID 49412 alive at 10.9min uptime post-flight. Extends the S156-A F5 (51.9min without FK-32) and postshots1 F3 (30.6min without FK-32) window — this is now the **third data point** confirming AdjustHealth-family calls do not trigger the S158-pattern delayed protector kill on this route.

7. **[M] Regression gate held.** Parent `-bindavatar-seedmax` `b47d1bfd04e44921` byte-identical after all edits. No source changes since postshots1 — only a build.ps1 variant addition.

## Not established / open

- **Zero-crossing (N≥3, or an override that pushes below 0)** — still deferred. Would need static_assert relaxation + explicit FK-32 watch harness. S158 precedent flagged GameplayCue OnDeath as unmitigated FK-32 risk; that concern remains open.
- **Floor firing** — code-covered but not fire-tested. Would need either an override of `KBFPOSTSHOT_FLOORBITS` to a higher value (e.g. 550, so SHOT_3 pre=500 ≤ 550 fires the floor at PRECHECK) or a larger N.
- **Positive delta (heal)** — untested. Requires source support for a per-shot delta parameter.
- **Multi-hero** — one hero class tested this session.
- **Continuity across MORE than 3 dispatches** — this flight proves 3, but a longer chain might expose ordering / commit-race issues.

## Method rules (banked)

- **First-try success on a well-designed follow-up is worth calling out** — postshots1 took 3 launches (33% success rate), postshots2 landed on F1 (100% within a single try). The delta between the two arms is a single `-DKBFPOSTSHOTS=1 → =2` flag; the design was already validated at N=1, so the N=2 build was low-risk. **When a design has been adversarially verified for a specific parameter range, exercising the top end of that range is a smaller experiment than the initial validation.**
- **A silent safety guard IS a positive result.** The floor at 300 HP stayed armed and never fired — that's exactly what a well-designed guard should do when preconditions hold. Reporting "FLOOR_REACHED did not emit" alongside the successful chain is meaningful evidence, not absence of evidence.
- **Ultracode does not mean "always run a workflow"** — this follow-up was a mechanical delta (single flag change on a pre-validated design). A design workflow here would have been ceremony, not insurance. **When ultracode is on: use workflows for design/synthesis phases; skip them for mechanical variant additions the prior workflow already reasoned through.**

## Files

- `docs/s156b-postshots2-f1-marker-final.txt` — preserved marker snapshot
- `docs/fk24-stage-s156b-postshots2-f1-{1-gft,2-fo,3-sp,4-probe-...}.txt` — per-inject markers
- `dumps/s156b-postshots2-f1/` — dumpimage snapshot (S164 `-includehiddenimages`), taken at t~POSTSHOTS_COMPLETE+minutes
- `tools/sigbypass-mod/build.ps1` — new `botfight-damage-self-cal-bindavatar-seedmax-postshots2` variant
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_postshots2.dll` — the flown arm, RAW `ad87408901f481c5`

**No source code changes** vs postshots1 (commit `3e7ac45`). This flight tests the N=2 arm of the pre-existing KBFPOSTSHOTS knob's declared range.
