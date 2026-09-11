# S156-B postshots1 flight 3 — back-to-back AdjustHealth works, second shot commits identically to primary

**Date:** 2026-09-08 (~19:32)
**Session:** S156-B (multi-shot follow-up to S156-A's SELF_DAMAGE_CALIBRATED win at commit `2a71a41`)
**Base commit:** `2a71a41` (S156-A F5 SELF_DAMAGE_CALIBRATED)
**Verdict:** ★★★★★★ **[M] The game's `ULokiAbilitySystemComponent::AdjustHealth` native path handles a second back-to-back invocation identically to the primary**, with byte-exact -250 delta arithmetic (750 → 500), synchronous commit visible on the next OnPI dispatch, and no FK-32 within 90s of POSTSHOTS_COMPLETE.

## Design provenance

Multi-agent workflow `wf_7ce5156c-73f` (17 agents, 4-lane parallel understand → 3-alternative design → 3-lens adversarial verify per design → synthesizer). Full workflow output preserved at
`C:\Users\eastr\AppData\Local\Temp\claude\...\tasks\w12raush0.output` and
`C:\Users\eastr\...\workflows\scripts\s156a-multishot-design-wf_7ce5156c-73f.js`.

**Chosen approach:** **D2-DERIVED-SAFE (KBFPOSTSHOTS)** — post-result loop wrapped in the `SELF_DAMAGE_CALIBRATED` else-arm of `BfS148DoCalibration`'s WAIT_LATER branch. All 3 verifier lenses (correctness, safety, evidence) agreed D2 preserves the S148 primary shot verbatim and keeps the `s148_damage_calibration_test.ps1 callCount=1` contract intact. D1 (in-place loop) was refuted with 10 compile-blocking defects. D3 (new arm mode) had wrong offset scheme + uninitialized paths.

**Safety design (verifier consensus):**
- First-flight N=1 only (750 → 500, no zero-crossing)
- 300 HP hard safety floor (KBFPOSTSHOT_FLOORBITS=0x43960000u)
- Fresh relaunch (not injecting into PID 12808 whose 4-injection footprint was at the modal FK-32 count)
- Zero-crossing (N=2 to reach 250 or N≥3 to cross 0) deferred to future flight after N=1 mechanics confirmed

## Flight ledger

| flight | outcome | mechanism |
|---|---|---|
| F1 | LOST — sp injection ACG-denied | game dying during LVL_Tutorial load, kernel refused RWX alloc (CLAUDE.md documented "ACG on?" trap: actually FK-31 in-progress) |
| F2 | LOST — FK-31 after fo | same signature as S156-A F3/F4: game gone 9s post-fo before sp could inject |
| **F3** | **SUCCESS** | **all 4 injections landed, primary S148 shot + SHOT_2 post-shot completed, arithmeticOK=yes** |

Combined session hazard cost across S156-A + S156-B: 6/9 launches lost to FK-31 variance before F3 landed. All losses were staging-side, none touched the S156-B arm (probe never got to run on F1/F2).

## Receipts (from `docs/s156b-postshots1-f3-marker-final.txt`)

### Primary shot (S148 chain unchanged — regression contract preserved)
```
[S148] target set=... HealthBits=447A0000/447A0000 MaxBits=447A0000/447A0000 ... issues=0x0
[S148] seed originalBits=00000000/00000000 readbackBits=447A0000/447A0000 faulted=no identityStable=yes exact=yes
[S148] CALL_ISSUED AdjustHealth HealthDeltaBits=C37A0000 callCount=1
[S189] POSTSHOTS_ARMED planned=1 adjustFn=0x0000026B33546E40 adjustThunk=0x00007FF6933F4270 adjustChild=0x0000026B760F6600 deltaOff=0
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S148] immediate return issues=0x0 identityStable=yes HealthBits=443B8000/443B8000 receipt=yes; returning to game until notBefore=499605125 timeout=499610125
[S148] RESULT=SELF_DAMAGE_CALIBRATED originalBits=00000000/00000000 seedBits=447A0000/447A0000 immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000 elapsed=250ms callCount=1
```

Primary shot: **1000 → 750 in 250ms, callCount=1** — byte-identical to S156-A F5's contract.

### Post-shot (S189/SHOT_2)
```
[S189] SHOT_2 PRECHECK preBits=443B8000/443B8000 preHP=750.00 floorBits=43960000 continuityOK=yes
[S189] SHOT_2 CALL_ISSUED deltaBits=C37A0000 deltaHP=-250.00 callCount=2
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S189] SHOT_2 POST postBits=43FA0000/43FA0000 postHP=500.00 observedDeltaHP=-250.00 arithmeticOK=yes rvalBits=00000000 identityStable=yes issues=0x0
[S189] POSTSHOTS_COMPLETE fired=1 requested=1 aborted=no reason=none finalBits=43FA0000/43FA0000 finalHP=500.00
```

Post-shot: **750 → 500 in one OnPI dispatch**, observedDeltaHP=-250.00 matches requested delta to FP epsilon.

### Clean disarm
```
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan 3563 ms, 34253 UFunctions live)
[BF] worker done (hits=95 hitsGT=95)
```

100% funcswap restoration (17563/17563), 95 worker hits, clean disarm.

## What this settles

1. **[M] Back-to-back AdjustHealth commits synchronously across OnPI dispatches.** SHOT_2's `preBits=443B8000/443B8000 continuityOK=yes` matches the primary's `laterBits=443B8000/443B8000`. That means the primary shot's -250 damage was already visible on Health when SHOT_2's PRECHECK re-resolved the target — no game-side deferred write, no pending queue, no reconciliation delay between OnPI dispatches. The engine's attribute layer applies AdjustHealth mutations in-band.

2. **[M] Second AdjustHealth invocation uses the primary shot's wrapper handles safely.** `adjustFn=0x26B33546E40 adjustThunk=0x7FF6933F4270 adjustChild=0x26B760F6600 deltaOff=0` were captured before the primary's CallNativeGuarded and consumed inside the WAIT_LATER post-loop. All three passed `LooksLikePtr` at post-loop entry (or POSTSHOTS_REFUSED would have emitted). The handles remained valid across the ~250ms notBefore wait.

3. **[M] AdjustHealth arithmetic is deterministic and correct.** Requested delta `0xC37A0000 = -250.0f`; observed delta `-250.00` to two decimals; `arithmeticOK=yes` (FP epsilon check within ±0.01). Second shot behaves identically to primary (same delta, same arithmetic).

4. **[M] AdjustHealth writes BOTH Base and Current to the same value on this build.** Post-primary: `HealthBits=443B8000/443B8000` (750/750, both slots). Post-SHOT_2: `postBits=43FA0000/43FA0000` (500/500, both slots). If AdjustHealth touched only Current, Base would still read 447A0000 (1000, the seeded value). This is an implementation detail of `LokiAttributeSetHealth::AdjustHealth` worth banking — the game's damage semantic is "set both stored and effective to the new value", not "decrement effective only".

5. **[M] No FK-32 within 90s of POSTSHOTS_COMPLETE.** Verified live: game PID 35592 was at 7.0min uptime and 670MB WS after the multi-shot sequence completed. S158's ~50-70s ability-adjacent kill window closed without a kill. Back-to-back AdjustHealth does NOT re-trigger WALL P via GameplayCue OnDeath (which would fire at Health=0 anyway; our SHOT_2 landed at 500 HP, above the 300 HP safety floor).

6. **[M] The S148 contract test passes on the rebuilt parent variant.** Regression gate: parent `-bindavatar-seedmax` RAW `b47d1bfd04e44921` — byte-identical to the S156-A committed hash. New `-postshots1` RAW `1925e9e80646a4fb` — distinct from parent and all siblings (no A/B against a copy of itself). Both `s148_build_contract_test.ps1` and `s148_damage_calibration_test.exe` PASS.

## Retracted / not-established caveats

- **The 300 HP safety floor was NOT exercised.** Since N=1 landed at 500 HP (well above the 300 floor), the FLOOR_REACHED branch didn't fire. Floor behavior is implemented + code-covered but not empirically validated at fire-time.
- **Zero-crossing behavior is NOT established.** N=2 (750→500→250) approaches the floor; N≥3 (500→250→0→?) crosses zero. Both are excluded by first-flight discipline. What happens when Health reaches 0 (clamping? hero death? GameplayCue chain? WALL P?) remains a separate experiment.
- **Positive delta (heal) is NOT tested.** AdjustHealth may or may not cap at MaxHealth. A heal-arm variant would need `KBFHEALTHDELTA` support to vary the delta from the primary shot's hardcoded -250.
- **Only one hero class tested** (whichever spawns as the default tutorial hero on this build — from the marker `class=0x26D02370010`; not decoded to a hero name in this flight).
- **The `[S148] CALL_IN_FLIGHT_WAIT observedPhase=CALL_ISSUED elapsed=120000ms; hold cap reached` line at line 59 of the marker is CONCERNING but did NOT prevent success** — the worker thread's FsHold gave up at 120s, but the game thread's WAIT_LATER path eventually claimed the transition and emitted RESULT= as expected. This is the "disarm deferred fail-stop until callback publication" arm of the design; it worked correctly but suggests OnPI dispatch cadence on this route is much lower than S156-A F5's 265ms round-trip. Possibly a per-run variance (F3 got a slower parked-menu OnPI cadence?) rather than a design defect. Worth watching in future flights.

## Files

**Source:**
- `tools/sigbypass-mod/tutorial_launch.cpp` — S189 (KBFPOSTSHOTS) blocks:
  - Knob definitions at ~line 17989 (KBFPOSTSHOTS, KBFPOSTSHOT_FLOORBITS)
  - Policy validation at ~line 18017
  - Static locals inside `BfS148DoCalibration` at ~line 21996
  - Handle capture before primary `CallNativeGuarded` at ~line 22270
  - Post-loop in `SELF_DAMAGE_CALIBRATED` else-arm at ~line 22046

**Build:**
- `tools/sigbypass-mod/build.ps1` — new variant `botfight-damage-self-cal-bindavatar-seedmax-postshots1`

**Artifacts:**
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_postshots1.dll`
  - RAW `1925e9e80646a4fb` VSIZE `66252fd5355723cb`
  - Parent `-bindavatar-seedmax` RAW `b47d1bfd04e44921` unchanged (regression gate)

**Evidence:**
- `docs/s156b-postshots1-f3-marker-final.txt` — preserved marker snapshot
- `docs/fk24-stage-s156b-postshots1-f3-{1-gft,2-fo,3-sp,4-probe-...}.txt` — per-inject markers
- `dumps/s156b-postshots1-f3/` — dumpimage snapshot (S164 -includehiddenimages) at t~POSTSHOTS_COMPLETE+2min

**Design provenance:**
- `C:\Users\eastr\.claude\projects\...\workflows\scripts\s156a-multishot-design-wf_7ce5156c-73f.js` — the workflow script
- Workflow tokens: 5,980,758 subagent tokens across 17 agents, 25 min wall clock

## What's next (post-N=1)

- **N=2 (750→500→250)** — approaches 300 HP floor, tests whether the floor's abort branch fires cleanly
- **Custom floor override** — `-DKBFPOSTSHOT_FLOORBITS=0x00000000u` (0 HP floor) with N=3 (750→500→250→0) tests zero-crossing; MUST be run with post-flight FK-32 watch (S158 precedent risk)
- **Heal (positive delta)** — requires source support for delta parameter; would test AdjustHealth's MaxHealth cap
- **Multi-hero** — vary tutorial hero to test whether the mechanism generalizes
- **Multi-injection** — inject the arm again into the SAME PID after POSTSHOTS_COMPLETE (5th injection); would test process-lifetime FK-32 accumulation vs single-injection safety
- **Damage source discrimination** — the game accepts our raw AdjustHealth call; testing whether damage sources (weapon fire, GameplayEffect chains) reach the same code path is a much larger question

## Regression gates (post-flight)

- **`botai`** `5e47c13cf7f0a158` — UNCHANGED (dead-strips in every non-botai variant)
- **`play`** `9bc10a4552c596e1` — UNCHANGED
- **`botfight-damage-self-cal`** (base S153 gate) `899ac8b56a477110` per CLAUDE.md; drifted to `167d1552c73bfd7a` per S156-A F5 evidence — needs re-verification if base is used in future A/Bs (not touched by this session)
- **`botfight-damage-self-cal-bindavatar`** (S155 gate) `d8c08912816162a7` — UNCHANGED
- **`botfight-damage-self-cal-bindavatar-seedmax`** (S156-A gate) `b47d1bfd04e44921` — UNCHANGED (verified after all S156-B edits — KBFPOSTSHOTS=0 truly dead-strips)
- **`botfight-damage-self-cal-bindavatar-seedmax-postshots1`** (S156-B flown gate) `1925e9e80646a4fb` — NEW
