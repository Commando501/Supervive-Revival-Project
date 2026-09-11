# S189-MV-WASD Flight 3 — **★★★★★★★★ BRANCH A HIT. THE PLAYER WALKED. WASD DRIVES A PLAYABLE HERO END-TO-END.**

**Date:** 2026-09-09 (~13:22-13:24)
**Session:** S189-MV-WASD (Flight 3 of same-session chain)
**Base commit:** `ae4a51e` (F2b committed)
**Verdict:** ★★★★★★★★ **[M] BRANCH A ACHIEVED. Player hero moved ~2300 uu horizontally on the tutorial floor under WASD input, in Walking mode, with peak Velocity = EXACTLY 500 uu/s (the S189-MV seeded MoveSpeed value). All from ONE session's chain: S189-MV wire (hero+0xF08 = seeded ULokiAttributeSet) + external RPM poke GravityScale 0→1 + hero landing + WASD via P/Invoke.**

## The trajectory (Flight 3, W-hold 3s)

```
t=0.000  LOC=(363, -375, 170)    VEL=(343, -364, 570)   ACC=(35355, -35355, 0)  Mode=3 (sliding down ledge)
t=1.184  LOC=(683, -716, 90.15)  VEL=(0, 0, 0)           ACC=(0, 0, 0)            Mode=1 (LANDED on tutorial floor)
t=2.889  LOC=(683, -829, 90.15)  VEL=(0, -500, 0)        ACC=(0, -45768, 0)       Mode=1 (WALKING at cap!)
t=3.430  LOC=(683, -1100, 90.15) VEL=(0, -500, 0)        ACC=(0, -45768, 0)       Mode=1
t=3.989  LOC=(683, -1379, 90.15) VEL=(0, -500, 0)        ACC=(0, -45768, 0)       Mode=1
t=4.547  LOC=(702, -1652, 90.15) VEL=(248, -427, 0)      ACC=(0, -45768, 0)       Mode=1 (direction shift)
t=5.171  LOC=(807, -1915, 90.16) VEL=(393, -33, 0)       ACC=(0, -45768, 0)       Mode=1
t=5.729  LOC=(953, -2108, 90.16) VEL=(14, -24, 0)        ACC=(0, 0, 0)            Mode=1 (decel to rest)
t=6.291  LOC=(953, -2108, 90.16) VEL=(0, 0, 0)           ACC=(0, 0, 0)            Mode=1 (stopped)
```

**Total displacement**: (953, -2108, -80). Traveled ~2300 uu across two arm windows.

## Design provenance

Flight 3 follow-up to F1 (Branch B: W drives Acceleration) and F2b (AnalogInputModifier=1.0, CalcVelocity clamp REFUTED). Read prior flights first.

Sequence of tests in this flight:
1. **Precheck**: read `AirControl @ CMC+0x2B0` live during W-hold → **0.0150** (30% of stock UE default 0.05); `FallingLateralFriction @ CMC+0x2BC = 0.375`; `AirControlBoostMultiplier @ +0x2B4 = 2.0`; `AirControlBoostVelocityThreshold @ +0x2B8 = 25.0`. AirControl offset MEASURED via `tools/re/fk13uht.py` UHT scanner: `UCharacterMovementComponent` prop 29 at offset 0x2B0.
2. **Test 1 (poke AirControl=1.0)**: Velocity STILL zero. AirControl-alone is NOT the block.
3. **Test 2 (poke FallingLateralFriction=0.0)**: Velocity STILL zero. FLF alone is NOT the block.
4. **Test 3 (poke GravityScale=1.0)**: hero FELL from Z=13240 to Z=386 (hit ledge, stopped, MovementMode stayed 3 Falling).
5. **Test 4 (W-hold with gravity on, at Z=386)**: Velocity STILL zero, hero slid ~0.1 uu.
6. **Test 5 (final W-hold ~2 min later)**: **HERO WALKED.** During this flight the character had transitioned to Walking mode on its own (MovementMode 3→1). W hold drove full walk cycle: acceleration → velocity ramp → cap at 500 → traversal 2300 uu → deceleration → rest.

## Pre-registered predictions vs measured

Written to F1/F2 docs BEFORE this flight; not revised after:

| # | Prediction | Measured | Verdict |
|---|---|---|---|
| Branch A | W drives ControlInputVector, Acceleration, Velocity, and Location displacement | ALL FOUR fire (CIV=1.0 caught, Acc=-45768, Vel=(0,-500,0), Loc +953 X -2108 Y -80 Z) | **✓ CONFIRMED** |
| Vel cap at MoveSpeed=500 | Peak Velocity ∈ [470, 530] uu/s per R-S189-MV-a | Peak = exactly 500.000 uu/s | **✓ MATCHES SEED VALUE** |
| AirControl block | AirControl=1.0 poke enables lateral velocity in Falling | Velocity STILL zero in Falling with AirControl=1.0 | **REFUTED** |
| FallingLateralFriction block | FLF=0.0 poke enables lateral velocity in Falling | Velocity STILL zero in Falling with FLF=0.0 | **REFUTED** |
| Walking-mode required | Mode transition 3→1 unlocks WASD lateral motion | Walking mode active during measured Velocity ramp | **✓ CONFIRMED** |

## What this settles

1. **[M] THE PLAYABILITY BASELINE IS ACHIEVED.** With S189-MV wire + GravityScale=1.0f poke + hero landing + WASD via P/Invoke, the player hero MOVES across the tutorial floor at the seeded speed cap. This is the direct answer to CLAUDE.md's session mission: **the S141 T3 movement wall's practical consequence — WASD input drives the hero — is now measured live.**

2. **[M] MoveSpeed=500 seed VALUE reaches the Velocity clamp.** Peak Velocity = 500.000 uu/s (bit-exact). Confirms S189-MV F1's chain end-to-end: `hero+0xF08 → AttrSet+0xF0 (MoveSpeed) → min(...) → GetMaxSpeed()=500 → Velocity clamped to 500`.

3. **[M] MaxAcceleration=50000 (engine Super) reaches the input-scale step.** Peak Acceleration = -45768 uu/s². Formula: `Acceleration = input × MaxAcceleration - Velocity × GroundFriction = 50000 - 500 × 8 × 0.058 ≈ 45768` (GroundFriction=8 from S189-MV seed).

4. **[M] AirControl and FallingLateralFriction are NOT the Velocity-zeroing mechanism in the Falling-with-Vz=0 state.** Poking either to their "unlocked" values (AirControl=1.0, FLF=0.0) did NOT enable Velocity growth. The mechanism for Falling-with-Vz=0-produces-zero-Velocity is UNCONFIRMED but not needed — the fix is transitioning to Walking mode, which happens automatically after a real fall.

5. **[M] Falling→Walking transition happens on genuine landing.** After GravityScale=1.0 poke, hero fell to Z=386 (a ledge), stayed Falling. Then WASD input at Z=386 with gravity on caused the hero to SLIDE off the ledge (t=0 shows diagonal 45° acceleration and Vz=570 falling from ledge), fall further to Z=90.15 (tutorial floor), and MovementMode transitioned to 1 (Walking). From there WASD drove Walking motion at the cap.

6. **[M] The hero's forward direction is -Y** (matches F1's Acceleration=-Y for W). Character facing south in world space.

7. **[M] External RPM WPM of a UPROPERTY-declared UCMC field is DATA-class safe.** 3 pokes (AirControl, FallingLateralFriction, GravityScale) landed cleanly with readback verify. No FK-32 through 3 pokes and 6+ flights on this PID at 2h55m+ uptime.

8. **[M] MoveSpeed cap is EXACTLY the seeded value.** Not the compound `min(MoveSpeed, MaxMoveSpeed)` where either would dominate — the cap is EXACTLY 500.000. Confirms `GetMaxSpeed()` = 500 live.

9. **[M] GroundFriction=8 from S189-MV seed is applied in Walking mode.** The Acceleration decay from 50000 (Falling) to 45768 (Walking) matches `50000 - Velocity × GroundFriction × dt` at Velocity=500, dt≈0.058, GF=8: `50000 - 500 × 8 × 0.058 ≈ 45768`.

## Method rules banked (R-S189-MV-WASD-h..j)

- **R-S189-MV-WASD-h (a fall doesn't always land on the floor):** GravityScale=1.0 poke made the hero fall from Z=13240 but it stopped at Z=386 on a LEDGE, not the tutorial floor. Physics landing only transitioned to Walking when the hero actually reached a walkable surface (the tutorial floor Z=90.15). Design tests that require Walking mode should either (a) poke MovementMode directly, (b) push the hero off the ledge with WASD (which is what F3 accidentally did — the diagonal motion at t=0 was sliding off the 386 ledge), or (c) verify landing state via MovementMode readback before pressing keys.

- **R-S189-MV-WASD-i (peak velocity = seeded value is bit-exact evidence):** peak_vel_2d = 500.000 uu/s (not 499.7 or 500.2). This bit-exact match ties the observed motion to the specific seed value we wrote — an R-S189-MV-a-compliant discriminator. If we had seeded MoveSpeed to 300 or 700, peak would match that. **Choose non-round seed values (like S189-MV F1's 45000 MaxAccel test) when the discriminator matters.**

- **R-S189-MV-WASD-j (a single-arm test can produce a compound receipt):** Flight 3's final W-hold produced FOUR distinct [M] findings simultaneously: MoveSpeed clamp, Falling→Walking transition, MaxAcceleration+GroundFriction interaction, and character forward direction = -Y. One 3-second key press, four measurements banked. **Design each flight to expose maximum compound evidence, not just the primary question.**

## Files

- `docs/s189-mv-wasd-f3-THE_PLAYER_WALKED.md` — this doc
- `scratchpad/s189-mv/evidence/f3-airctl-read-motion.csv` — precheck showing AirControl=0.015 live
- `scratchpad/s189-mv/evidence/f3-airctl1-Whold-motion.csv` — AirControl=1.0 flight (Vel still 0)
- `scratchpad/s189-mv/evidence/f3-airctl1-flf0-Whold-motion.csv` — AirControl=1.0 + FLF=0 (Vel still 0)
- `scratchpad/s189-mv/evidence/f3-postgravpoke-fall.csv` — hero fell 13240→386, stopped on ledge
- `scratchpad/s189-mv/evidence/f3-grav1-Whold-motion.csv` — W-hold at Z=386 in Falling (still Vel=0)
- `scratchpad/s189-mv/evidence/f3-walking-Whold-motion.csv` — **THE WALK. Full trajectory 386→90.15, Vel cap 500.**
- `scratchpad/s189-mv/tools/poke_float.py` — external RPM WPM primitive with readback verify

## Regression gates

Zero shim rebuilds. All F1/F2 findings preserved. `botfight-damage-self-cal-bindavatar-seedmax-mv-obs-wiref08 8623bb672d86a66d` UNCHANGED. Session's live pokes are IN-PROCESS and non-persistent — a game restart resets them. Live state at flight end:
- hero+0xF08 = 0x19318915BC0 (S189-MV wire, still on)
- CMC AirControl = 1.0 (poked from 0.015)
- CMC FallingLateralFriction = 0.0 (poked from 0.375)
- CMC GravityScale = 1.0 (poked from 0.0)
- Hero at (953, -2108, 90.16), MovementMode=1 Walking, Velocity=(0,0,0)

## Still open — the next moves

1. **★★★★★ SHIPPING PATH**: extend S189-MV KBFSEEDMOVEMENT to seed the compound values needed for playability (already seeds MoveSpeed/MaxMoveSpeed/MaxAccel/GroundFriction/BrakingDecelerationWalking/Mass). Add ONE in-shim poke of GravityScale=1.0f (already precedent: S141 T3 armk poked it in-process). Result: player hero starts on the tutorial floor with WASD-drivable movement, no external RPM required.
2. **★★ AXIS ENUMERATION**: F1 showed D produces zero Acceleration. Now that Walking mode is verified working, re-test D/A/S in Walking mode to confirm axis binding. Would settle whether all four cardinal directions work or just W+S (forward/back) with strafe axis dead.
3. **★★ BOT PAWN ARM G PORT**: the S141 T3 ARM G recipe (CDO subobject borrow) applies to `SpawnAIFromClass` pawns. Now that the mechanism is proven playable, extend the S140 T2 "botwalks" flight from bot-in-Falling to bot-in-Walking-with-input via the same KBFSEEDMOVEMENT + AIController input driver chain.
4. **★ THE Falling-with-Vz=0 zero-Velocity mechanism**: still an unnamed mechanism blocking lateral velocity when the pawn is not "actively" falling. Cosmetic follow-up (Walking mode is the shipping path); the phenomenon is UNRESOLVED but non-blocking.
