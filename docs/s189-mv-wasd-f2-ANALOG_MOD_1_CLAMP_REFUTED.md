# S189-MV-WASD flight 2/2b — **AnalogInputModifier=1.0 during W hold; the S141 T3 CalcVelocity clamp is REFUTED as the Velocity-zeroing mechanism**

**Date:** 2026-09-09 (~13:02-13:03)
**Session:** S189-MV-WASD (follow-up to F1)
**Base commit:** `8706f27` (F1 committed)
**Verdict:** ★★★★★★ **[M] AnalogInputModifier = 1.0000 during the W-hold ARM** (CMC+0x3D0 per S141 T3 [I,strong] — offset validated live). This means `MaxInputSpeed = GetMaxSpeed() × AnalogInputModifier = 500 × 1.0 = 500 ≫ 1e-4`, so the engine `CalcVelocity` ACCELERATE-branch clamp at `0x035D6511-0x035D652F` (S141 T3's leading hypothesis for Velocity-zeroing) does NOT fire. **The Velocity block on this build is DOWNSTREAM of the CalcVelocity input clamp AND downstream of ScaleInputAcceleration.**

⚠ **F2 anomaly**: the 5-arm sequence (w,s,a,d,f13) produced ZERO on every arm including W (all 240 samples over 26s zero). But F2b (W-only, run ~1 min later on the same PID) reproduced F1's result FIRST-TRY. Root cause of the F2 anomaly is UNRESOLVED — possibly focus loss between arms or some engine-side input suppression state induced by an F1 F13 trailing effect. Do NOT read F2's zero as a Branch C result — F2b immediately refutes it.

## Flight ledger

| flight | sequence | Hold | outcome |
|---|---|---|---|
| F2 | w,s,a,d,f13 | 2500ms | **ANOMALY**: 240 samples all zero on every arm — even W (which worked in F1) |
| F2b | w only | 3000ms | **SUCCESS**: W arm reproduces F1 result exactly + adds AnalogMod=1.0 receipt |

## F2b W-only receipts

Probe start: 2026-09-09 13:03:29. WASD_START = 13:03:32.290 (probe t≈2.85).
ARM_w_START = 13:03:32.330 (probe t≈2.89). ARM_w_END = 13:03:35.343 (probe t≈5.90).

Raw samples during W-hold showing the KEY MEASUREMENT (AnalogMod=1.0 with Accel=-50000):

```
t=3.780 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=3.889 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=3.992 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=4.095 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=4.197 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=4.322 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=4.425 ACC=(0, -50000, 0)  CIVmax=1.0000  ANALOGMOD=1.0000   ← burst-read caught CIV
t=4.530 ACC=(0, -50000, 0)  CIVmax=0.0000  ANALOGMOD=1.0000
t=4.639 ACC=(0, -50000, 0)  CIVmax=1.0000  ANALOGMOD=1.0000   ← burst-read caught CIV
t=4.764 ACC=(0, -50000, 0)  CIVmax=1.0000  ANALOGMOD=1.0000   ← burst-read caught CIV
...
```

**Every single sample during the W hold reads AnalogMod = exactly 1.0000.** This holds durably like Acceleration — because ComputeAnalogInputModifier (`0x035DB6F0`, disp 0x660, NOT Loki-overridden per S141 T3) returns `|Acceleration| / GetMaxAcceleration() = 50000/50000 = 1.0` and the value persists between physics substeps.

Postflight: Velocity STILL (0,0,0), Location STILL (0,0,13240). MovementMode still 3 (Falling), GravityScale still 0.0.

## What this settles

1. **[M] The CalcVelocity clamp (S141 T3's leading hypothesis for Velocity-zeroing) is NOT firing on the S189-MV-treated player during W hold.** Live measurement: `AnalogInputModifier = 1.0`, `GetMaxSpeed() = 500` (S189-MV F1 measurement), `MaxInputSpeed = 500 × 1.0 = 500 ≫ 1e-4`. The clamp at `0x035D6511-0x035D652F` requires `|Velocity| < MaxInputSpeed × 1.01` for it to fire — even at Velocity=0, that requires MaxInputSpeed=0 which is REFUTED. Something else zeroes Velocity.

2. **[M] The AnalogInputModifier self-correction hypothesis (S141 T3 lane L6) is CONFIRMED.** L6 predicted: "once WASD ControlInputVector fires, `ScaleInputAcceleration` writes `Acceleration = input × GetMaxAcceleration()`; ratio `|Accel|/MaxAccel = 50000/50000 = 1.0`; ⇒ AnalogInputModifier self-corrects to ~1.0 on the first WASD frame". Every W-hold sample reads exactly this. The self-correction chain is real and durable.

3. **[M] The Velocity block is DOWNSTREAM of ScaleInputAcceleration AND downstream of ComputeAnalogInputModifier AND downstream of the CalcVelocity input clamp.** Candidates that survive:
   - **★ AirControl (LEADING [I,strong])**: `UCharacterMovementComponent::AirControl` is a UPROPERTY (float32) on this build (binds_members.csv:28428). Standard UE gates LATERAL input velocity during `MOVE_Falling` by multiplying by AirControl. If AirControl ≈ 0, WASD-in-Falling produces no lateral velocity despite full Acceleration. This EXACTLY matches our measurement. Also: `AirControlBoostMultiplier`, `AirControlBoostVelocityThreshold`, `FallingLateralFriction` (props 25/26/27 on UCMC). And `ULokiAttributeSet::AirControlMultiplier` is GAS-backed (binds_members.csv:39719) — if we didn't seed it in S189-MV, GetAirControlMultiplier() may return 0 and be composed against AirControl.
   - **PhysFalling's own alternate paths**: on `GravityScale=0`, PhysFalling might skip the velocity-integration substep entirely (treating it as "not really falling"). Would need to transcribe engine `PhysFalling`'s bytes to confirm.
   - **A Loki override of PhysFalling zeroing Velocity every frame**: less likely since the mechanism should propagate to bots (S140 T2 Flight 3 measured bot moving in MOVE_Falling), but not ruled out.

4. **[M] F2b W-only reproduced F1 W-arm EXACTLY.** Same Accel value, same CIV burst-hit rate, same duration. The primitive is durable across flights on the same PID.

5. **⚠ F2 5-arm anomaly**: unexplained. Not a Branch C signal — F2b immediately refuted it in the same session with the same primitive. Possible causes: (a) focus loss between arms, (b) F1's trailing F13 keyup induced some engine input-suppression state that F2 hit and cleared before F2b, (c) rapid 5-key sequence overwhelmed something. Not a productive diagnostic target compared to the AirControl hypothesis.

## Method rules banked (R-S189-MV-WASD-f..g)

- **R-S189-MV-WASD-f (measure the leading hypothesis when it's cheap):** S141 T3 named CalcVelocity's clamp as the LEADING hypothesis for Velocity-zeroing but never measured `AnalogInputModifier` live. One 4-byte RPM read added to the probe (CMC+0x3D0) settled it — REFUTED. Cost: one line of code. Value: eliminates a whole class of hypothesis in one measurement. **Any long-standing hypothesis with a measurable predicate should be measured before spawning follow-up experiments assuming it.**

- **R-S189-MV-WASD-g (single-flight anomalies are not results — reproduce or discard):** F2's all-zero-on-W would have been a critical Branch C data point if reported alone. F2b (~1 min later, W-only, same primitive, same PID) reproduced F1 exactly. **Reproduce anomalous nulls with a minimal-variable second flight before drawing conclusions.** The F2 anomaly is real (something DID cause the input path to miss) but is NOT a systematic property of the build.

## Files

- `docs/s189-mv-wasd-f2-ANALOG_MOD_1_CLAMP_REFUTED.md` — this doc
- `scratchpad/s189-mv/evidence/f2-motion.csv` + `f2-motion.stderr.txt` — anomalous 5-arm flight (240 samples, all zero)
- `scratchpad/s189-mv/evidence/f2b-Wonly-motion.csv` + `f2b-Wonly-motion.stderr.txt` — successful reproduction with AnalogMod measurement (69 samples)
- `scratchpad/s189-mv/evidence/f2-preflight.txt`, `f2-postflight.txt`, `f2b-Wonly-*.txt`

## Regression gates

Unchanged from F1. No shim rebuilds. Regression gate `botfight-damage-self-cal-bindavatar-seedmax-mv-obs-wiref08 8623bb672d86a66d` UNCHANGED.

## Actionable follow-ups (Flight 3 targets)

1. **★★★★★ MEASURE `AirControl` LIVE**: discover the offset on this build (via UPROPERTY reflection walk, or offline usmap inspection), then add to probe. Fly W-hold and read AirControl. Predictions:
   - If `AirControl < 0.05`, the input velocity is being scaled down to near-zero → this is the block. Fix: poke `AirControl = 1.0f` (or seed `AirControlMultiplier` on ULokiAttributeSet at offset TBD).
   - If `AirControl ≈ 1.0`, the block is elsewhere — look at FallingLateralFriction or Loki CMC PhysFalling override.

2. **★★ POKE GravityScale = 1.0f, wait for landing, re-run W**: canonical land-and-walk test. On Walking arm the whole PhysWalking chain runs which is unrelated to PhysFalling's AirControl gate. If W drives motion in Walking, that isolates the block to Falling-specific behavior.

3. **★ RESOLVE F2 ANOMALY**: fly F1-identical sequence (w,d,f13 3000ms 2000ms) after a minute of idle. If it works, the anomaly is transient. If it fails, characterize the trigger.

4. **★ SEED `AirControlMultiplier` on ULokiAttributeSet**: extend S189-MV KBFSEEDMOVEMENT to include AirControlMultiplier=1.0f. Would require finding its offset on the attribute set (likely +0x180 or similar based on the naming pattern).
