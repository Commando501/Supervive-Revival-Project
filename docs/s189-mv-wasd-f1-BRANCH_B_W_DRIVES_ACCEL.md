# S189-MV-WASD flight 1 — **BRANCH B: W drives full Acceleration, D is dead, Velocity stays zero**

**Date:** 2026-09-09 (~12:52-12:55)
**Session:** S189-MV-WASD (successor to S189-MV F1 which unlocked the S141 T3 movement wall)
**Base commit:** `06e8c65` (S189-MV-WASD next-session prompt)
**Verdict:** ★★★★★★ **[M] BRANCH B — W (VK_W) drives `ControlInputVector`, `ScaleInputAcceleration` runs, `Acceleration = (0, -50000, 0)` holds for the full 3s W hold, but `Velocity` NEVER moves off zero and the pawn does not translate. This DIRECTLY REFUTES the pre-existing measurement in `tools/sigbypass-mod/tutorial_launch.cpp:3817` ("input_watch proved WASD produces ZERO ControlInputVector"). That measurement was an INSTRUMENT ARTIFACT — input_watch had the same ConsumeMovementInputVector race defect our burst-read defense caught: CIV IS driven but is consumed every frame, so 90% of samples land post-consume and read zero. Acceleration is the durable receipt.**

⚠ **AND D (VK_D) produces ZERO acceleration and ZERO CIV across 29 samples** — either D is not bound to MoveRight on this parked-tutorial state, or D's binding requires camera rotation the character doesn't have, or D is bound to a different subsystem. **Only the FORWARD axis (W) is confirmed live on this state**; the STRAFE axis (D) is a separate open question.

## Design provenance

Multi-agent design workflow `wf_45a88dd2-ec4` (5 Understand + 1 Design synth + 2 adversarial Verify + 1 Adjudicator, 9/9 done, 3.08M subagent tokens, ~22 min wall clock). **Both adversarial verifiers refuted the initial design and produced CRITICAL fixes that this flight PROVED WERE ESSENTIAL**:
- **V1 fix #1 (auto-repeat @30Hz)**: without 64 sustained WM_KEYDOWNs across the 3s hold, only ONE WM_KEYDOWN reaches UE and axis input would decay after one frame → Branch B or C misclassified as failure. Flight 1 emitted 64 WM_KEYDOWNs per hold and confirmed durable Acceleration.
- **V1 fix #2 (SwitchToThisWindow + AttachThreadInput)**: initial focus grab was DENIED (foreground stayed on PID 29980 Claude Code UI). The AttachThreadInput trick worked first-try.
- **V2 fix #1 (CIV burst-read x3)**: without burst-reading CIV three times per sample with ~1ms gaps, all 30 W-arm samples would have read CIV=(0,0,0). With bursts, 3/30 samples caught the -1 Y value.
- **V2 fix #2 (F13 as unbound negative control)**: replaced backquote (potentially bound to dev console). F13 produced clean zero across all fields.

## Delta from S189-MV F1 (~2h33m earlier)

Zero source code changes to the shim tree. All new tooling under `scratchpad/s189-mv/tools/`:
- `preflight_read.py` — one-shot read of hero+CMC key state (identity, wiring, GravityScale, MovementMode, Vel/Accel/CIV/Location)
- `motion_watch_player.py` — 100ms tight-sample of loc/vel/accel/CIV/mode/grav with CIV BURST-READ (3× per sample, 1ms gap) against ConsumeMovementInputVector race
- `send-wasd.ps1` — P/Invoke keybd_event WASD with 30Hz auto-repeat sustained across each hold, SwitchToThisWindow+AttachThreadInput focus-grab
- `fly-wasd.ps1` — orchestrator (preflight → probe bg → WASD → wait → postflight)

State on entry (measured live, PID 1780 uptime 2h30m):
- hero+0xF08 = spawnedSet0 = 0x19318915BC0 (S189-MV wire still live)
- GravityScale = 0.0f (sp LIFT step, never restored per S141 T3 [M])
- MovementMode = 3 (MOVE_Falling)
- Hero at (0, 0, 13240) hovering

## Flight design

Three arms in one 18s window (probe starts 2s before WASD launches):

| arm | key | VK | hold | intent |
|---|---|---|---|---|
| 1 | W | 0x57 | 3000ms | forward axis test |
| 2 | D | 0x44 | 3000ms | strafe axis test |
| 3 | F13 | 0x7C | 3000ms | unbound negative control |

Inter-arm gap: 2000ms (rest-decay control window).
Auto-repeat: 33ms (30Hz) — 64-65 KEYDOWNs emitted per hold.
Motion probe: 100ms cadence, 18s duration, 164 samples captured.
CIV burst: 3 reads per sample with 1ms gap (defeats ConsumeMovementInputVector race).

## Receipts

### Pre-flight state (identical pre/post)
```
hero+0xF08 AttrSet    = 0x19318915BC0 -- S189-MV WIRED
hero+0x1090 LivingSt  = 0
hero+0x418 CIV        = (0.000, 0.000, 0.000)
root+0x158 Location   = (0.000, 0.000, 13240.000)
cmc+0x1A0 GravityScale = 0.0000
cmc+0x231 MovementMode = 3
cmc+0xE8 Velocity      = (0.000, 0.000, 0.000)
cmc+0x328 Acceleration = (0.000, 0.000, 0.000)
```

### Focus grab (V1 fix confirmed)
```
foreground after grab: hWnd=0x001E0A22 PID=1780 focusOk=True
```
SwitchToThisWindow succeeded on first attempt.

### ARM W (t=3.66..6.74 in probe time)
```
3.723 ACC=(0,0,0)              CIV1=(0,0,0)     CIVmax=0.0000  -- pre-key
3.856 ACC=(0,-50000,0)         CIV1=(0,0,0)     CIVmax=0.0000  -- Accel LIVE, CIV missed
4.956 ACC=(0,-50000,0)         CIV1=(0,-1,0)    CIVmax=1.0000  -- burst caught it!
5.517 ACC=(0,-50000,0)         CIV2=(0,-1,0)    CIVmax=1.0000  -- burst caught it (read 2)
6.199 ACC=(0,-50000,0)         CIV1=(0,-1,0)    CIVmax=1.0000  -- burst caught it (read 1)
6.738 ACC=(0,-50000,0)         CIV=(0,0,0)      CIVmax=0.0000  -- last sample with Accel live
6.840 ACC=(0,0,0)              CIV=(0,0,0)      CIVmax=0.0000  -- ~100ms after KEYUP, decay
```

**[M] W drives `Acceleration = (0, -50000, 0)` DURABLY across the full 3s hold** (all ~30 samples in the hold window read Accel.Y = -50000, only decayed at ARM_END). **3 of 30 W-arm samples caught non-zero CIV** in the burst read — the consume race renders 90% of samples zero, but a single non-zero read PROVES CIV is being driven.

### ARM D (t=8.75..11.85)
```
29 samples in D arm window
0 samples with non-zero Acceleration, CIV, Velocity, or Location delta
```
**[M] D drives ZERO on all fields.** This is a genuine null, not a race — Acceleration is durable when it fires (W proved that), so a durable-zero Accel means the input path never reached ScaleInputAcceleration for D.

### ARM F13 (t=13.78..16.81)
```
29 samples all zero across all fields (as expected — F13 is unbound)
```
**Clean negative control — the primitive delivery mechanism is not the failure mode for D.**

### Motion probe summary
```
# SUMMARY (from 164 samples over 18.0s)
# peak_vel_2d          = 0.000 uu/s
# peak_accel_2d        = 50000.000 uu/s^2
# peak_civ_max_mag_2d  = 1.0000
# CIV ever non-zero    = YES
# MovementMode ever=1  = NO
# Location delta       = (0, 0, 0)
```

### Post-flight (identical to pre-flight, hero+F08 wiring persists)

## Pre-registered predictions vs measured

Written to this doc's header BEFORE the flight; not revised after.

| # | Prediction | Measured | Verdict |
|---|---|---|---|
| Branch A | W/D show CIV≥0.5, Accel∈[45k, 52k], Vel∈[400, 530]; F13 all zero | W caught CIV=1.0 with burst-reads, Accel=50000, but Vel=0. D all zero. F13 all zero. | **PARTIAL** — Branch A criteria met for CIV+Accel on W, but Vel stayed zero → REFUTED |
| Branch B | W/D show CIV≥0.5 but vel/loc stay zero; F13 zero | W: yes (with burst-read caveat). D: no. Vel/loc stayed zero. | **✓ FIRED for W arm** |
| Branch C | W/D/F13 all show CIV<0.01 (matches historical) | W has non-zero CIV (with burst), D has zero. Mixed. | **PARTIALLY REFUTED — W disproves it; D matches it** |

The measured result is: **W lands in Branch B (input reaches internals but Velocity zeroed downstream); D lands in Branch C (input never reaches CIV)**. Two arms, two mechanisms, one flight.

## What this settles

1. **[M] `tutorial_launch.cpp:3817` is REFUTED by evidence**. The pre-existing "input_watch proved WASD produces ZERO ControlInputVector while jump works => movement input is being ignored" statement was itself an INSTRUMENT ARTIFACT. input_watch sampled CIV without burst-defense against the ConsumeMovementInputVector race. Our burst-read (3 reads × 1ms gap per sample) caught CIV=-1 on the Y axis in 3 of 30 samples during the W hold — proving CIV IS driven. Acceleration is the durable proof: with `ScaleInputAcceleration` writing `Acceleration = input × MaxAccel = 1.0 × 50000 = 50000` per S141 T3's mechanism, the -50000 Y value we measured for the full 3s hold is direct evidence the input pipeline is alive end-to-end from keystroke to CMC.

2. **[M] The S189-MV F1 unlock (`hero+0xF08` wired + seeded ULokiAttributeSet) is what makes CIV → Accel work on the PLAYER**. The chain `CIV → AddMovementInput → Acceleration = CIV × GetMaxAcceleration()` was DEAD on the untreated player (S141 T3 [M] AnalogInputModifier=0, no attribute set). On the S189-MV-treated player, `GetMaxAcceleration()` returns 50000 (engine Super's stock CMC UPROPERTY on Falling arm), so Acceleration is computed correctly. **S189-MV directly enables this half.**

3. **[M] The Velocity block is DOWNSTREAM of Acceleration**. Acceleration = -50000 is durable but Velocity stays 0. Per S141 T3 [M], engine `CalcVelocity`'s clamp at `0x035D6511-0x035D652F` writes ZeroVector when `|Velocity| < MaxInputSpeed × 1.01` AND `MaxInputSpeed = GetMaxSpeed() × AnalogInputModifier`. On this build with GAS wiring: `GetMaxSpeed() = 500` (S189-MV), `AnalogInputModifier` should self-correct to `|Accel|/MaxAccel = 50000/50000 = 1.0` once Accel is non-zero → `MaxInputSpeed = 500 ≫ 1e-4` → clamp SHOULDN'T fire. So SOMETHING ELSE is zeroing Velocity every frame. **Candidates for follow-up flight**: (a) `PhysFalling`'s brake step when GravityScale=0, (b) Loki override of CalcVelocity or PhysFalling zeroing velocity, (c) `ConstrainInputAcceleration` reading Accel back to zero downstream, (d) AnalogInputModifier NOT self-correcting on this build. RPM read of `AnalogInputModifier` (offset TBD, per S141 T3 = CMC+0x3D0) during W hold would settle (d).

4. **[M] D (VK_D) does NOT drive input on this parked-tutorial state**. Zero across all 29 samples in the D-arm window, zero across all bursts, zero Acceleration. This is a REAL null (not a race) because W in the same session with the same primitive drove durable non-zero Acceleration. **Either**: (a) D is not bound to MoveRight on this state (possibly still menu-nav from parked-tutorial context — CLAUDE.md notes `Menu_NavRight_*` uses A/D), OR (b) D is bound to MoveRight but strafe requires camera rotation that the character doesn't have (ControlRotation.Yaw might be 0, producing zero right-vector projection), OR (c) D reaches CIV but the burst-read misses it (unlikely — W caught 3/30 samples so D at same rate should have caught something). **[I]** (b) is most likely given W-forward-works-but-strafe-doesn't is a classic "MoveRight needs `ControlRotation.RotateVector((0,1,0))` = non-zero right axis" symptom.

5. **[M] Auto-repeat @ 30Hz is REQUIRED**. Without it a 3s hold would send ONE WM_KEYDOWN and axis input would decay after one frame. With 64 KEYDOWNs across the hold, Acceleration held durably at -50000 across the whole window. V1 verifier's #1 recommendation was decisive.

6. **[M] SwitchToThisWindow + AttachThreadInput bypasses SetForegroundWindow denial**. Initial fly attempt failed with `focusOk=False` (foreground stayed on Claude Code UI PID 29980). The updated grab succeeded first-try on attempt 4. **This is now the primitive for any focus-required test on this workstation.**

7. **[M] The S189-MV wire STATE holds across 2h30m of uptime and 4 external RPMs**. Post-flight readback identical to pre-flight — `hero+0xF08 = 0x19318915BC0` still wired, no state decay.

## Method rules banked (R-S189-MV-WASD-a..e)

- **R-S189-MV-WASD-a (burst-read defense for consumed-per-frame fields):** any field that is read AND consumed on the same tick (like ControlInputVector by ConsumeMovementInputVector at CMC's 0x036037FE) requires multiple RPM reads per sample to overcome the race. Even ~1ms gaps catch the pre-consume state ~10% of samples at 60fps. A single-read probe reads zero and generalizes to "field never non-zero" — the exact defect input_watch had and this flight refuted. **Always burst-read consumed fields.**

- **R-S189-MV-WASD-b (a durable derivative is worth more than the source):** ControlInputVector is race-y (10% hit rate on bursts); Acceleration is DURABLE because it holds until the next tick that overrides it. If input drives both CIV and Accel via the same tick, Accel is the more reliable read. **Read one hop DOWNSTREAM of a consumed field for a stable receipt.**

- **R-S189-MV-WASD-c (SwitchToThisWindow + AttachThreadInput is the focus-grab primitive):** SetForegroundWindow is denied silently when the caller doesn't own foreground. `AttachThreadInput(selfTid, targetTid, true)` around `BringWindowToTop + SetForegroundWindow + ShowWindow(SW_RESTORE)` bypasses that policy. First-try success on this build. Add to any script requiring foreground of a specific window.

- **R-S189-MV-WASD-d (auto-repeat sustains axis input):** UE Enhanced Input / legacy axis mapping reads key state per-frame. A single WM_KEYDOWN drives one frame; sustained WASD requires either OS auto-repeat (physical keyboard) or synthesized KEYDOWN at ~30Hz. `keybd_event` KEYDOWN emitted every 33ms across the hold duration sustains the axis reading.

- **R-S189-MV-WASD-e (a shim source comment is an unverified claim, not a measurement):** `tutorial_launch.cpp:3817` recorded a definitive-sounding statement that was actually an instrument artifact of the tool that produced it. It was cited across sessions as a hard finding and shaped the RM_PUPPET workaround architecture. **A source comment describing prior evidence is not the evidence itself — replicate the measurement with a controlled instrument before accepting it as [M].**

## Files

- `docs/s189-mv-wasd-f1-BRANCH_B_W_DRIVES_ACCEL.md` — this doc
- `scratchpad/s189-mv/evidence/f1-motion.csv` — 164 samples with CIV bursts
- `scratchpad/s189-mv/evidence/f1-preflight.txt` / `f1-postflight.txt` — pre/post state snapshots
- `scratchpad/s189-mv/evidence/f1-wasd.log` — driver output with focus-grab + arm timings
- `scratchpad/s189-mv/evidence/f1-motion.stderr.txt` — probe summary
- `scratchpad/s189-mv/evidence/f1-SUMMARY.txt` — combined summary
- `scratchpad/s189-mv/tools/*.py, *.ps1` — flight tooling (preflight_read, motion_watch_player, send-wasd, fly-wasd)
- Workflow artifact: `.claude/projects/.../workflows/scripts/s189-mv-wasd-design-wf_45a88dd2-ec4.js`

## Regression gates

No shim rebuilds. All 8 S189-MV F1 gates + all F1 addenda-family digests should be BYTE-IDENTICAL:
- `botfight-damage-self-cal-bindavatar-seedmax-mv-obs-wiref08` `8623bb672d86a66d` — UNCHANGED (never touched in this flight; still running in-process)

## Still open — the actionable follow-ups

1. **★★★★★ WHY DOES VELOCITY STAY ZERO given Acceleration = -50000?** Next flight targets: (a) RPM-read `AnalogInputModifier @ CMC+0x3D0` during W hold to test S141 T3's clamp hypothesis; (b) poke `GravityScale=1.0f` to enable landing, wait for MovementMode 3→1 (Walking) transition, re-run W and see if Vel now grows; (c) transcribe engine `PhysFalling`'s Velocity-write behavior when Acceleration is non-zero but GravityScale=0. This is the primary WALL P/movement question.
2. **★★ WHY DOES D DRIVE NOTHING?** Test hypotheses: (a) read PC's `ControlRotation` (yaw) to check if strafe direction is degenerate; (b) test A key (should be symmetric to D — same axis, opposite sign); (c) test S key (should be symmetric to W — same axis, opposite sign). If S works but D+A don't, MoveRight axis is dead entirely and MoveForward alone is bound.
3. **★★ VELOCITY DIRECTLY POKED — INDEPENDENT MOVER TEST**: use RPM WriteProcessMemory to poke Velocity=(0,600,0) and see if hero translates. If yes, mover works and only the input→velocity conversion is broken. If no, mover itself is dead. This decouples input-path from mover-path.
4. **REFUTATION-BY-SYMMETRY**: poke hero+0xF08 back to null (as R-S166-a demands), re-fly W arm, expect Acceleration=0 (Branch C). If Acceleration STILL fires with wiring removed, S189-MV was not the causal precondition and the Branch B result is invalid.
5. **`tutorial_launch.cpp:3817` COMMENT SHOULD BE ANNOTATED/RETRACTED**: update source or add doc entry noting the comment describes a false-negative from an instrument-artifact-suffering tool.
