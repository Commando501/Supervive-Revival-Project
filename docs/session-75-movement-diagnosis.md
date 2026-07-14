# Session 75 — WASD movement diagnosis (force-open tutorial hero)

> ⚠️ SUPERSEDED — read `docs/session-75-summary.md` for the corrected story. This file's core
> conclusion ("the CMC is dormant / deploy-gated") was DISPROVEN later the same session: the hero
> was simply UNDER THE MAP (bad spawn spot + the S74 lift). Teleporting it above ground makes the
> CMC fall/walk with real physics, and a velocity puppet gives working WASD movement. Kept as an
> artifact of the (wrong) mid-session hypothesis.

Goal: figure out why WASD movement doesn't work on the S74 spawned+possessed Ronin
(jump + aim DO work). Live process this session: PID 55928, base 0x7FF6B54F0000,
in the force-open LVL_Tutorial with the S74 possessed hero still present.

## TL;DR — the hypothesis in the S75 handoff was wrong; the real blocker is deeper

The handoff guessed movement is gated on the **feature-toggle / deploy locomotion flow**
(FudgeMantling / CursorCharacterAim "not ready" spam). That is NOT the direct cause.

**Ground truth (read-only RE + live reads): the hero's movement SIMULATION is dormant.**
The `LokiCharacterMovementComponent` is not ticking at all — and this is true round-wide,
for every hero, not just our possessed one. No client-side flag makes it move because the
component isn't simulating. This is the same server-authoritative **deploy wall** the whole
project keeps hitting (S66/S68/S72/S74 force-open, S70–73 DS), now pinned to the CMC level.

## What was checked (all ruled out as the cause)

Possessed hero = `0x25B8AE50040` (PC `0x25B82F8B140` → Pawn@+0x3F8). Its CMC = `0x25B80F7AAB0`.

| Signal | Offset (this build) | Value on possessed hero | Verdict |
|---|---|---|---|
| `bCharacterMovementEnabled` (LokiCharacter) | +0xB59 | **TRUE** | movement not disabled by the flag |
| `MaxWalkSpeed` (CMC) | +0x278 | **180.0** | normal, non-zero (toggles didn't zero it) |
| `Role` (Actor) | +0x160 | **3 = Authority** | correct for local movement |
| `RemoteRole` | +0x72 | 1 = SimulatedProxy | normal |
| `NetDormancy` | +0x161 | **1 = Awake** | not dormant |
| root capsule `Mobility` (SceneComp) | +0x1BB | **2 = Movable** | fine |
| CMC `bIsActive` (ActorComponent) | +0xB2 | bits set (active) | fine |
| `MovementMode` (CMC) | +0x231 | **3 = MOVE_Falling** | airborne (see lift below) |
| `GravityScale` (CMC) | +0x1A0 | 0.0 (S74 lift) | — |
| `Velocity` (MovementComponent) | +0xE8 (FVector dbl) | **(0,0,0)** | frozen |

### The decisive experiment
Poked `GravityScale` 0.0 → **1.0** on the possessed hero's CMC. Expectation if the CMC were
alive: the hero (hovering at Z≈1818 in MOVE_Falling) immediately starts falling. **Result:
nothing — Velocity stayed (0,0,0), MovementMode stayed Falling, no fall.** Gravity has no
effect ⇒ the CMC is not running its movement update. (Poke restored to 0.0 afterward.)

### Round-wide census (tools/re/hero_move_census.py)
All **12** live `BP_HERO_Ronin_C` (our possessed one + AI-bot/orphaned-shim-spawn leftovers):
Role=Authority, movement-enabled=TRUE, gravity=1.0, **11/12 in MOVE_Falling with |Vel|≈0**,
1 in MOVE_Walking with |Vel|=0. The entire round's heroes are frozen — nobody is simulating
movement. This is not specific to our shim-spawned hero; it's the un-deployed round.

## Why jump/aim "work" but WASD doesn't
- **Aim** = PlayerController tick (cursor → targeting ring), independent of the pawn's CMC.
- **Jump** was confirmed in S74 on the *grounded* hero (Z≈18) BEFORE the lift; "WASD doesn't
  work" was only ever observed AFTER the lift (airborne). So WASD was effectively tested on a
  hero whose CMC is dormant anyway. The lift (gravity off + teleport +1800) was a real confound
  layered on top of the true issue (frozen CMC).

## Movement input path (RE'd, but moot while the CMC is dormant)
- `ALokiCharacter::IsIgnoringMovementInput` exec thunk `0x7FF6BA7F1860` → impl `0x7FF6BAAA18E0`
  (checks helpers `0x7FF6BAAA2930` / `0x7FF6BAAA2890` then a component at `this+0x7F0`).
- `AuthSetMovementEnabled` (BPCallable native, thunk `0x7FF6BA7EDD60`) sets `bCharacterMovementEnabled`;
  `OnRep_CharacterMovementEnabled` (`0x7FF6BA7F2690`) applies it client-side.
- `LokiCharacterMovementComponent::UpdateFeatureToggles` (thunk `0x7FF6BA7FCC60`),
  `GetMovementInputVector` (`0x7FF6BA7FC770`) — the SUPERVIVE ground-input functions. Not reached
  while the CMC isn't ticking.

## Client-side kick — ATTEMPTED AND FAILED (definitive)

Built `RM_WAKEMOVE` into tutorial_launch.cpp (build `-DKRUNMODE=RM_WAKEMOVE`, dll
`tutorial_launch_wake.dll`). Via the native-call primitive it called, on the possessed hero's CMC:
`SetActive(true)` + `SetComponentTickEnabled(true)` + `SetActorTickEnabled(true)` (hero) +
`SetMovementMode(MOVE_Falling)` + poked `GravityScale=1.0`, then sampled Velocity/MovementMode
every ~400ms for ~3s. All four UFunction calls executed cleanly (no faults). Marker result:

```
[WM] BEFORE:  mode=3 grav=0.00 vel=(0,0,0)
[WM] sample 1..8: mode=3 grav=1.00 vel=(0,0,0)   (unchanged the whole window)
[WM] done (samples=9 called=4287 hitsGT=4287)
```

`hitsGT=4287` = the game thread ran ProcessInternal 4287 times during the window (the world is
ticking hard), yet the possessed hero's CMC produced **zero velocity** — it did not fall a single
unit with gravity on, tick enabled, component active, and a physics movement mode set. **The kick
does not reach `PerformMovement`.** So the movement update is skipped/early-returned on a condition
that only the server-authoritative **deploy** satisfies (not component activation, not tick
registration, not movement mode, not gravity — all forced, all no-ops). The game stayed stable (no
crash). This closes the client-side movement path.

## Recommended next step — the DS route
**Robust path — the DS route ([[supervive-dedicated-server-status]]):** a real server runs the
deploy/drop-in sequence that ACTIVATES hero locomotion, so movement comes for free. ds_hybrid.cpp
already carries the S74 OUT-param marshalling fix. Movement is the natural next milestone there
(S70/S73 reached spectator-in-world). The force-open route's honest ceiling is confirmed: real
gamemode inits + round advances via GoToPhase + hero spawns/possesses/aims/jumps, but locomotion
stays deploy-gated and is unreachable client-side.

## New reusable tools (this session, untracked)
- `tools/re/class_props.py` — list a UClass's FProperties (name/type/`Offset_Internal@+0x44`/flags)
  across its super chain. Complements class_funcs.py. FField: Next@+0x18, ChildProperties@+0x58.
- `tools/re/hero_move_census.py` — movement-state census across all live instances of a class
  (Role, movement-enable, CMC, MovementMode, GravityScale, |Velocity|).
