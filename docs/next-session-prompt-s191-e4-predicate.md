# S191 opening prompt — E4: a PLAYER ability damages+kills a hostile bot (the predicate)

You are continuing the SUPERVIVE Revival Project. Read `CLAUDE.md`, then this. S190 achieved Track D
(a spawned enemy bot dies from the game's own AdjustHealth) and fully de-risked the last wall. Your job
is **E4**: build one arm and fly it so a PLAYER ability damages and KILLS a hostile enemy — the
acceptance predicate. Everything upstream is [M]; the plan is `docs/s190-wallp-predicate-plan.md` (read
it first — the WALL E gate + GO verdict are its UPDATE sections).

## Why this is now a build-and-fly, not a research problem

- **FK-32 is OFF the critical path [M].** The window is ~40–60s (S160); an ability body executes in
  ~56ms (S158). A landing cast kills in the same frame. Do NOT spend effort defeating FK-32 (E6, refuted
  8 ways S168–S177) — fly inside the window.
- **WALL P activation + body both WORK via NATURAL input [M]** (S158). A SHIM-originated TryActivate
  dies (0xDEAD) — NEVER use one. The shim binds+grants, aborts out of the way (SETUP_ABORT), then an
  external P/Invoke drives the cast.
- **WALL E is FAVORABLE [M]** (S190 gate): a team-100 `BP_Minion_TargetBot_TTK_C` classifies ENEMY of
  the player by RAW per-actor integer compare (never touches the stripped TeamState); no attribute-layer
  hostility gate on the decrypted damage path; the minion self-inits team 100 (no team poke).
- **The damage mechanism works on a minion [M]** (Track D: AdjustHealth kills a spawned target with a
  real ASC). The ONE unproven thing: a PLAYER ability's damage EFFECT (not a direct write) landing on a
  target's HP. E4 tests exactly that.

## The E4 arm — extend RM_BOTFIGHT (do NOT write a new mode)

RM_BOTFIGHT already has the player side: S155 bind (`KBFSELFCAL=1 KBFBINDAVATAR=1`), K_GRANT
(`BfBuildSpec`+`BfGiveAbilityNative`), and the S158 natural-input path (`KBFNATURALINPUT=1`: SETUP_ARMED
→ SETUP_ABORT → worker waits for natural input). Set `KBFABIL="Ability1"` (the hero property that reads
GS_Ronin_LightAttack1, the LMB basic — the code at `tutorial_launch.cpp:24035` already resolves abilCls
from this property). Add, behind a new `#if KBFE4` knob (default 0, no `#else`, gates byte-identical):

1. **Spawn the target** (before SETUP_ABORT): `SpawnActorCls(FindClassExact("BP_Minion_TargetBot_TTK_C"), ...)`
   at ~200uu in FRONT of the player hero (inside the 360uu/110° LMB cone; compute from the hero's
   RootComponent location + forward vector). It's a plain `ALokiMinionCharacter`, no round-mode/drop-pod
   dependency (S135–S137 precedent); self-inits team 100 in ungated BeginPlay — do NOT poke team.
2. **Seed the target ASC** (reuse the KBFTRACKD/S156 code from RM_BOTSPAWN, committed `0107910`): resolve
   its `LokiAbilitySystemComponent` (constructor-built CDO subobject) + `LokiAttributeSetHealth` by name,
   `InitAbilityActorInfo(0x447F410)`, seed Health Base/Current @ +0x70 and MaxHealth @ +0x80 (FGameplay-
   AttributeData 0x10-spaced, CurrentValue @ +0xC) to a LOW value (e.g. 100.0) so one LMB tick kills.
   Register the sets in SpawnedAttributes if needed (Track D's DxAppend step). ⚠ MaxHealth is GE-driven,
   NOT baked — seeding is REQUIRED. Read the pre-seed MaxHealth first (settles the [I] "did native
   attr-apply run on standalone").
3. **KE4DIRECTGE fallback** (separate knob): if the natural cast runs but HP doesn't move, apply a real
   damage GE by handle (`ApplyGameplayEffectSpecToTarget` with LightAttack1's damage GE spec) OR the
   S156-B AdjustHealth(-N) direct write on the seeded minion. Arm ALONGSIDE the natural cast (dual
   instrumentation), not instead of it.

## Spawn-time LIVE reads (pre-register; the offline gate's filter/inputid reader was a stub)

- player PlayerState `GetTeamId` (confirm != 100 — inferred 0/-1, never measured on the tutorial route).
- LightAttack1 InputID from the granted spec on the player ASC (only Ability3=5 is pinned; needed to bind
  the cast). The fallback needs the spec HANDLE, not the InputID.
- LightAttack1's `FGameplayTargetDataFilter` axis (EnemiesOnly vs Class) — confirm it resolves the minion.
- the minion's post-spawn/pre-seed MaxHealth; the seeded ASC AvatarActor bind confirmation.

## The flight

Stage `gft→fo→sp` (`fk24-stage.ps1 -Probe <e4.dll> -AllowStale`), forceTutorialMatch route. The arm
spawns+seeds the minion, grants+binds LightAttack1, then SETUP_ABORTs. Start the target-HP RPM watcher +
`Loki.log` tail BEFORE the cast (baseline stable = no self-decay). Then run
`scratchpad/s190/tools/send-lmb.ps1` (already built + parse-checked): a SHORT LMB tap (<240ms; default
150) fires the melee CONE, NOT the fireblast projectile (hold ≥0.24s). Watch the minion Health → 0.

### Pre-registered receipts / four separable outcomes
TARGET SPAWNED (LokiMinionCharacter +1, TargetBot_TTK, ASC non-null, in cone) · SEEDED (HealthSet 100/100
exact) · ABILITY BOUND (Items 0→1, Handle, Ability1) · BASELINE STABLE · BODY RAN (Loki.log LightAttack1
phase trace at the tap) · DAMAGE ARRIVED (target OnDamaged/DPS, player=instigator) · **PREDICATE: minion
Health seeded→0 under the player cast, TTK OnDeath fires.** Outcomes: [body ran + HP→0] = SUCCESS ·
[body ran + HP flat] = targeting filtered → fire KE4DIRECTGE (proves the real GE lands, isolates the
gate) · [by-handle GE also flat] = residual PostGameplayEffectExecute gate (0x553C200, dark — firing one
real GE demand-decrypts it) · [body did not run] = WALL P on LightAttack1 activation.

## Logistics / do-nots

- FK-31 staging death is ~27% and CLUSTERS (S190 hit 4 in a row) — budget ≥2–3 launches per armed window;
  each PID FK-32s at ~285–293s uptime regardless, so land the cast well before that.
- Session is ELEVATED already works; `launch-redirect.ps1 -NoHook` returns fast; the game FK-32s on the
  ~4th–5th injection — capture as you go.
- Regression gates (rebuild byte-identical, all E4 code behind `#if KBFE4`, no `#else`):
  `botai b620e0ff3279e673`, `play 31af7667355f39d1`, `-seedmax b47d1bfd04e44921`,
  `-postshots1 1925e9e80646a4fb`. Track-D gates `trackd-kill`/`-nonlethal` (committed `0107910`) unchanged.
- Do NOT: use a shim TryActivate (dies); poke the minion's team (self-inits 100); hold LMB ≥0.24s (fires
  the fireblast, not the cone); chase FK-32 (off critical path). Refuted list: `docs/s190-wallp-predicate-plan.md`.
- The natural cast is THE PREDICATE; the fallback is the graded consolation (proves a real GE/direct
  write reduces the minion HP), NOT the predicate itself.
