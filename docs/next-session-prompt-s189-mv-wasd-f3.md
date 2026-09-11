> ⛔⛔⛔ **SUPERSEDED 2026-09-09**: F3 was flown same-session, hit BRANCH A, and the shipping arm
> was built + validated on a fresh launch. Read:
> - `docs/s189-mv-wasd-f3-THE_PLAYER_WALKED.md` — F3 result (BRANCH A, 2300 uu at 500 uu/s)
> - `docs/s189-mv-wasd-ship-f1-SHIPPING_ARM_VALIDATED.md` — shipping arm F1 (10/10 predictions hit)
> - CLAUDE.md's WALL P S156-B block for the compact chain summary.
>
> This file's AirControl-hypothesis plan is HISTORICAL and was answered in F3 (AirControl=0.015
> live, but poking it to 1.0 did NOT unlock lateral velocity — the true unlock was GravityScale→1.0
> then wait for Walking mode). The rest of this file is preserved for the record.

# Fresh session opening prompt — S189-MV-WASD Flight 3 (AirControl hypothesis)

You are continuing work on the SUPERVIVE Revival Project. Read `CLAUDE.md` in full before doing anything.

The last session (2026-09-09) flew S189-MV-WASD Flights 1 and 2b successfully and produced two [M] findings that directly refute previous project claims:

1. **F1**: `tutorial_launch.cpp:3817`'s "WASD produces ZERO ControlInputVector" is REFUTED. W (VK_W=0x57) DOES drive `ControlInputVector` — burst-read defense (3 reads × 1ms gap per sample) caught CIV=(0,-1,0) in 3/30 W-arm samples. Acceleration = (0, -50000, 0) held DURABLY for the full 3s W hold. Velocity STAYED (0,0,0). Location UNCHANGED. Read `docs/s189-mv-wasd-f1-BRANCH_B_W_DRIVES_ACCEL.md`.
2. **F2b**: S141 T3's leading hypothesis — CalcVelocity input clamp at `0x035D6511-0x035D652F` — is REFUTED. AnalogInputModifier read live at CMC+0x3D0 during the W hold = **1.0000 durably**. Means MaxInputSpeed = 500 × 1.0 = 500 ≫ 1e-4 → clamp cannot fire. Read `docs/s189-mv-wasd-f2-ANALOG_MOD_1_CLAMP_REFUTED.md`.

Commit `8706f27` (F1) + pending F2 commit on branch `dedicated-server-stub`.

## Your task this session

Fly S189-MV-WASD Flight 3 to identify and TEST the mechanism zeroing Velocity despite Acceleration=(0,-50000,0) and AnalogInputModifier=1.0. The leading hypothesis is **`UCharacterMovementComponent::AirControl`** (float32 UPROPERTY on UCMC, gates lateral velocity in MOVE_Falling by multiplication — if ≈0, WASD-in-air produces zero lateral velocity despite full input; matches our measurement exactly).

## Current live state (session close 2026-09-09 ~13:04)

- Game PID 1780 uptime ~2h50m. Verify alive: `Get-Process -Name SUPERVIVE-Win64-Shipping`.
- ags backend running.
- S189-MV wire state INTACT: hero+0xF08 = 0x19318915BC0 (spawnedSet0, holds MoveSpeed=500 etc.)
- GravityScale = 0.0f (sp LIFT step, hero hovering at Z=13240)
- MovementMode = 3 (MOVE_Falling)
- Hero addr: 0x1931C76AAC0. CMC addr: 0x193108438F0. PC addr: 0x1928CE3C4F0. Base: 0x7FF68E160000.

## Flight 3 offline pre-work (MANDATORY before any live probe)

Task: **discover the AirControl offset on this build's ULokiCMC**. Options in order of preference:

1. **Use the UHT `FPropertyParams` oracle in `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`**. Walk `UCharacterMovementComponent`'s `FClassParams::PropPointers` table (S138/S141 T3 method). Property #24 (per binds_members.csv:28428) is `AirControl`. Read its `FPropertyParamsBase.Offset` field.
2. **Consult existing offset tables** in `docs/s141-tier3-settled.md`, `docs/s140-t2-armj-THE-BOT-WALKS.md`, `scratchpad/s141/`. Grep for `AirControl` across the repo.
3. **CMC memory pattern-match**: `scratchpad/s189-mv/tools/cmc_float_scan.py` found candidates at CMC+0x0400 and +0x0424 (both read 0.05, stock UE AirControl default). Match against neighboring fields (stock UE has AirControlBoostMultiplier=2.0, AirControlBoostVelocityThreshold=25.0, FallingLateralFriction=0.0 in sequence).

⚠ Base 0x7FF68E160000 is the CORRECT one; do NOT use 0x7FF696A00000 (that was an initial error in S189-MV-WASD's original handoff — actually 0x7FF696A00000 - 0x88F8570 = 0x7FF68E107A90 ≠ base, real derivation: vtbl=0x7FF696A58570 in marker minus vtable_disp 0x88F8570 = 0x7FF68E160000).

## Ultracode

Ultracode is on. Author a design workflow for Flight 3. **Do NOT skip adversarial verification** — every F1/F2 flight caught real defects via adversarial verifiers, and the design was substantially reshaped each time.

## Fly design

Once AirControl offset is discovered, add it to `scratchpad/s189-mv/tools/motion_watch_player.py` alongside AnalogInputModifier. Fly:

1. **F3-precheck (READ-ONLY)**: run motion_watch_player with AirControl added, W-only 3s. Measure AirControl LIVE. Predict:
   - **AirControl < 0.05**: hypothesis CONFIRMED — AirControl is the block. Design F3-treatment.
   - **AirControl ≈ 1.0**: hypothesis REFUTED — block is elsewhere (PhysFalling internals, FallingLateralFriction, Loki override).

2. **F3-treatment (POKE)**: if AirControl low, poke to 1.0f via external WPM (~1-in-3.4/15min hazard per S138). Wait, then re-run W-hold. Predict:
   - Velocity grows → Location changes → **PLAYER WALKS IN AIR** (branch A on the S189-MV-WASD scale)
   - Velocity still 0 → some ANOTHER downstream mechanism (maybe FallingLateralFriction, or Loki override)

Save all evidence to `scratchpad/s189-mv/evidence/f3-*`.

## Also worth exploring in same session (if time)

- **Symmetry tests for D**: F1 showed D→0 acceleration. Test A (should be symmetric to D if MoveRight axis works, opposite sign) — if A also produces 0, MoveRight is dead entirely. If A gives +X accel, D-specific issue.
- **Direct Velocity poke**: WPM `CMC+0xE8 = (600, 0, 0)`, see if Location changes. Isolates "input path broken" from "mover itself dead" (S141 T3 flew this with player = fell 23,189 uu because Z gravity was on; test with lateral=600 to see if PhysFalling lateral integration works AT ALL).
- **GravityScale=1 → landing → Walking test**: canonical land-and-walk. Requires external WPM. Would test whether Walking mode's PhysWalking chain handles WASD (bypasses whatever PhysFalling gate is blocking us).

## Key evidence to read first

1. `CLAUDE.md` (WALL P S156-B block ends with the 3 latest S189 entries: F2b, F1, S189-MV F1).
2. `docs/s189-mv-wasd-f2-ANALOG_MOD_1_CLAMP_REFUTED.md` — the analog modifier finding + AirControl hypothesis
3. `docs/s189-mv-wasd-f1-BRANCH_B_W_DRIVES_ACCEL.md` — the W-drives-Acceleration finding + tutorial_launch.cpp:3817 refutation
4. `docs/s141-tier3-settled.md` §4 — the CalcVelocity clamp mechanism that we refuted
5. Prior session tools at `scratchpad/s189-mv/tools/*`

## Reusable rules banked (add to method-rules.md if appropriate)

- **R-S189-MV-WASD-a**: burst-read defense for consumed-per-frame fields (like ControlInputVector consumed by ConsumeMovementInputVector each tick).
- **R-S189-MV-WASD-b**: durable derivative beats race-y source (Accel is more reliable than CIV).
- **R-S189-MV-WASD-c**: SwitchToThisWindow + AttachThreadInput is THE focus-grab primitive on this workstation.
- **R-S189-MV-WASD-d**: auto-repeat at 30Hz sustains axis input for keybd_event.
- **R-S189-MV-WASD-e**: shim source comment is unverified claim, not measurement (tutorial_launch.cpp:3817).
- **R-S189-MV-WASD-f**: measure the leading hypothesis when it's cheap (one 4-byte read refuted the whole CalcVelocity clamp story).
- **R-S189-MV-WASD-g**: single-flight anomalies are not results — reproduce or discard.

## Do NOT

- Do NOT re-fly Flight 1 or 2 without the same fixes: SwitchToThisWindow+AttachThreadInput focus grab, 30Hz auto-repeat, CIV burst-read x3, F13 as negative control.
- Do NOT re-open the "keybd_event doesn't reach UE" question — F1 measured Acceleration=-50000 for the full 3s hold, proving keybd_event → WM_KEYDOWN → UE axis path is alive on this build.
- Do NOT re-open the "WASD produces ZERO CIV" claim from tutorial_launch.cpp:3817 — REFUTED by measurement.
- Do NOT re-open the "AnalogInputModifier=0 causes CalcVelocity clamp" hypothesis from S141 T3 — REFUTED by AnalogInputModifier=1.0 measurement.
- Do NOT poke GravityScale as the FIRST move — it's a Falling-arm question you should answer first. Only poke gravity if Flight 3's AirControl test is inconclusive.
- Do NOT declare the WASD input path "dead" — it demonstrably drives the game's mover to the Acceleration step.

## Session momentum

This is the FIFTH consecutive [M]-grade flight in a chain (S189 mana → S189-SEED → S189-MV → S189-MV-WASD F1 → S189-MV-WASD F2b). Each flight added a durable measurement to the movement wall. The chain is heading toward: player-hero MOVES under WASD via the stock input path with just S189-MV + one AirControl poke = a canonical playability proof.

Keep the momentum. If Flight 3 confirms AirControl, immediately design a Flight 4 that seeds `AirControlMultiplier` on ULokiAttributeSet (extend S189-MV KBFSEEDMOVEMENT) so no external WPM is needed.
