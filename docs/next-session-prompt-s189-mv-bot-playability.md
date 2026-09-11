# Fresh session opening prompt — S189-MV BOT PLAYABILITY (port the player chain to a bot)

You are continuing work on the SUPERVIVE Revival Project. Read `CLAUDE.md` in full before doing
anything.

The last session (2026-09-09) landed the PLAYER-side playability arc end-to-end:
- S189-MV F1 [M]: `hero+0xF08` wire + seed → GetMaxSpeed=500 live on KWIREGAS player
- S189-MV-WASD F1 [M]: W drives Accel=(0,-50000,0), `tutorial_launch.cpp:3817` REFUTED
- F2b [M]: AnalogInputModifier=1.0, S141 T3 CalcVelocity clamp REFUTED
- F3 [M]: **THE PLAYER WALKED** — 2300 uu at bit-exact 500 uu/s = seeded MoveSpeed cap
- SHIPPING ARM `-mv-play` [M]: `KBFPOKEGRAVITY` knob packages full chain, F1 flown 10/10 predictions

Commit chain `2d0fca6..ea1feb7` on branch `dedicated-server-stub`. Read first:
- `docs/s189-mv-wasd-ship-f1-SHIPPING_ARM_VALIDATED.md`
- `docs/s189-mv-wasd-f3-THE_PLAYER_WALKED.md`
- `docs/s189-mv-f1-MOVEMENT_UNLOCK.md`
- `CLAUDE.md`'s WALL P S156-B block (top of that section carries the compact ledger)

## Your task this session

Extend the S189-MV chain to **a bot pawn** so that a bot spawned via `SpawnAIFromClass` walks
under its own AI wander in the tutorial world — the "vs AI" half of the mission's goal.

**The strategic value**: player playability + bot playability = "player and enemy both alive in
the world" as an observable state. First real Versus AI milestone.

## Ground state going in (all [M] from prior sessions)

**PLAYER-side (proven this session, ready to use as reference):**
- S189-MV mechanism: seed 6 attrs on ULokiAttributeSet at `spawnedSet0` (ASC.SpawnedAttributes[0])
  → wire `hero+0xF08 = spawnedSet0` → GetMaxSpeed reads seeded 500.
- Playability chain: poke `CMC+0x1A0 GravityScale = 1.0f` → hero falls to tutorial floor
  Z=90.15 → MovementMode 3→1 (Walking) → WASD drives motion at 500 uu/s cap.
- Shipping arm variant `botfight-damage-self-cal-bindavatar-seedmax-mv-play` RAW `87c764b6d235b7a3`.

**BOT-side (proven in earlier sessions):**
- S135 [M]: `botspawn` variant (`build.ps1 -Variant botspawn`) calls `SpawnClassBotAtLoc` — spawns
  +1 hero at exact passed location. Confirmed via `obj_by_chain` census delta.
- S135 [M]: `SpawnBotTeamAtLoc` +3 heroes of 3 game-chosen classes.
- S136 [M]: `SpawnAIFromClass 0x4631C50` creates AI-controlled hero pawn; `SpawnDefaultController`
  builds engine `AAIController` that possesses the pawn.
- S137 [M]: `ALokiBotController` (via ARM D CDO poke on `Default__Pawn+0x3D0 = LokiBotController
  class`) with real `BrainComponent` (NodeInstances=21), `BlackboardComponent` (KeyInstances=15),
  cross-wired.
- S138 [M]: AI wander populates `ControlInputVector` at ~44 distinct horizontal unit directions
  over 97s (193/194 samples show CIV=RandomMoveDirection); `ScaleInputAcceleration` runs;
  Acceleration = input × MaxAccel.
- S140 T2 F3 [M]: BOT walked 13,187 uu at exactly 500 uu/s after ONE external velocity kick.
  Full trajectory: kick → fall → land Z=90.15 → walk on ground under AI steering.
- S141 T3 [M]: BOT vs PLAYER structural diff — `GravityScale` was `BOT=1.000 / PLAYER=0.000`
  (sp's LIFT step zeros player's; bot's inherent), so the bot did NOT need a gravity poke.

**BOT-side gap:**
- S138/S141 [M]: bot's own AI wander drives `Acceleration=50000` but `Velocity` stays 0 → bot
  doesn't move. Same Falling-with-Vz=0 fixed-point phenomenon we just diagnosed for the player.
- Bots need the same "land on walkable surface → transition to Walking mode → then Vel grows"
  path, but with either (a) bot spawns on a walkable surface directly OR (b) something triggers
  a fall so PhysFalling → PhysWalking transition happens.

## Recommended flight design (ULTRACODE workflow — full design pass)

Ultracode should be on for this — author a design workflow with 4-6 Understand agents +
adversarial verification. **The trap to avoid**: assuming the player mechanism ports directly.
It might, but the bot's spawn location + attribute-set wiring + CMC state are all distinct.

**Understand agents to spawn:**

1. **Bot spawn location + terrain check**: where does `SpawnClassBotAtLoc` place a bot? Is it on
   the tutorial floor (Z=90.15) or in the air? If on-ground, MovementMode is already 1 (Walking)
   and the whole "gravity+landing" cost is skipped. Grep S135 evidence + read `SpawnBot` disasm
   for the actual location computation. Also check whether `SpawnAIFromClass` uses the caller's
   location or a nav-mesh point.

2. **Bot ASC + attribute-set state**: does the bot have `hero+0xF08` = a valid attribute set OR
   is it NULL like the KWIREGAS player was? Read S137/S138 evidence + `docs/s137-playerstate-
   and-lokibot-settled.md`. If the bot inherits from `Default__LokiPlayerState_HeroAffiliated`
   subobjects (per S101 `coverage-audit-s101.md:283` DS route), it may already have MoveSpeed
   attributes wired.

3. **DS-hybrid ARM G recipe**: `docs/coverage-audit-s101.md:283` records the DS route borrowing
   `Default__LokiPlayerState_HeroAffiliated`'s default subobjects into the hero's
   `+0xF00/+0xF08/+0xF10` and writing the attribute block: measured `GetMaxSpeed()` 0 → 500 on
   the DS side. This is the CDO subobject borrow that S189-MV F1 said "the bot pawn (SpawnAIFrom
   Class) needs the whole DS-hybrid ARM G recipe (CDO subobject borrow); this flight's mechanism
   doesn't directly apply". Read `tools/sigbypass-mod/ds_hybrid.cpp` (functions `DoPlayable
   Setup`, `PlayableTick` — codegraph will find them). This is the BOT equivalent to S189-MV wire.

4. **Bot movement wall in Walking mode**: S140 T2 F3 proved a horizontally-kicked bot walks after
   landing. But does the bot's AI wander (native `Tick` writing `RandomMoveDirection` per S138)
   produce a HORIZONTAL kick equivalent — i.e., do the AI's `AddMovementInput` calls translate
   to velocity growth in Walking mode? Read `docs/s138-flight9-movement-not-simulating.md` +
   check whether the S140 T2 F3 bot's motion was AI-driven or purely kick-momentum.

5. **In-shim bot targeting**: the shipping arm targets `s156Pre.hero` (the player hero). Extend
   to target a bot pawn via a bot-side discovery step (walk `GUObjectArray` for a `LokiBot
   Controller`-possessed pawn OR trigger `SpawnAIFromClass` inline and use the returned pawn).
   Design a new knob `KBFBOTPLAY` that mirrors `KBFPOKEGRAVITY` but on a bot.

**Design synth**: package the port into ONE new build variant, e.g. `-mv-play-bot` or `-bot-play`,
that extends the existing shipping arm with the bot-side chain.

**Adversarial verify (2 lenses):**
- Attack the CDO-borrow assumption: does `Default__LokiPlayerState_HeroAffiliated` still have
  MoveSpeed attributes on this build? Has any prior session refuted the DS route?
- Attack the "bot walks under AI wander" assumption: is there evidence the bot's AI would drive
  motion once Velocity is non-zero, or is the AI wander just cosmetic?

## Fly design (after workflow)

1. Fresh launch (Steam running, ELEVATED PowerShell, kill any existing game + ags).
2. Full staging chain: `gft → fo → sp → <new bot-play DLL>`.
3. Verify shim marker chain: player receipts + bot receipts.
4. Optionally: fly WASD via `scratchpad/s189-mv/tools/send-wasd.ps1` on player.
5. Observe bot motion via `motion_watch_player.py` adapted for bot targeting.
6. Success criteria (per R-S189-MV-WASD-i): bot Location changes across time with `MovementMode=1`
   and peak `Velocity_2d` in [400, 530] uu/s = seeded MoveSpeed cap; ideally hero + bot both
   move in the SAME world at the same time.

## Do NOT

- Do NOT try to poke bot's GravityScale to 0 (bot already at 1.0 per S141 T3; leave alone).
- Do NOT run S138 flights again — bot walk-under-kick is [M].
- Do NOT re-run S147/S158 WALL P work — separate track, not blocking bot movement.
- Do NOT skip Understand agent #3 (DS-hybrid ARM G) — it's the KNOWN bot-side attribute recipe.
  Reusing the player-side S189-MV recipe UNMODIFIED may not port cleanly.

## Bonus: also fly the clean single-flight Walking demo if time

`docs/next-session-prompt-s189-mv-wasd-clean-demo.md` — the player-side one-flight demo that
closes an orchestration loose end (pre-warm send-wasd's Add-Type + longer probe). Cheap side quest
if flying the bot port on the same launch.

## Reusable rules already banked (see `docs/method-rules.md`)

- R-S189-MV-WASD-a..l (from prior session — see `docs/method-rules.md` §24-§28)
- Especially R-S189-MV-WASD-b (durable derivative — read Accel not CIV for consumed fields) and
  R-S189-MV-WASD-i (peak velocity = seeded value bit-exact is the discriminator)

## Session momentum

The player playability arc took 6 flights + 1 shipping arm build in ONE session. The bot arc has
even more prior [M] groundwork (S135 spawn, S136-S137 controller, S138 AI wander, S140 T2 F3
walk-under-kick). If the port is clean, this could be a 1-2 flight session to first observable
"player + walking bot in the same world" state.

The mission is Versus AI fully playable. This is the next observable step.
