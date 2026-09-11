# S191 opening prompt — BUILD the E4 arm, then FLY it (the co-op-vs-AI predicate)

You are continuing the SUPERVIVE Revival Project. Read `CLAUDE.md` in full first, then this.

**Your task, in order: (1) BUILD the E4 arm, (2) FLY it.** E4 is the acceptance-predicate attempt:
a PLAYER ability that DAMAGES and KILLS a hostile enemy. S190 achieved everything upstream and
de-risked the last wall to a GO. This is now a build-and-fly, not a research problem.

Read these in order before touching code:
1. `docs/s190-wallp-predicate-plan.md` — the plan + the two UPDATE sections (WALL E gate + GO verdict). **Load-bearing.**
2. `docs/s190-trackd-bot-killed.md` — Track D: the spawn+real-ASC+seed+AdjustHealth mechanism you will reuse.
3. `docs/bot-ai-client-side-settled.md` (2026-09-09 UPDATE) — why WALL P is one wall for player and bot.
4. This file's "The build" section.

## Current state (baseline — do not re-derive)

- Branch `dedicated-server-stub`. Commits `0107910` (Track D arm), `fd13f7f` (recon), `7c803db` (plan),
  `9648ce2` (WALL E GO), `3a75699` (this handoff + driver). Working tree: the S190 docs/arm are committed;
  other modified docs (fk10/fk22/…) are pre-existing, NOT this work — leave them.
- **Regression gates (rebuild BYTE-IDENTICAL after any edit; all E4 code behind `#if KBFE4`, no `#else`):**
  `botai b620e0ff3279e673`, `play 31af7667355f39d1`,
  `botfight-damage-self-cal-bindavatar-seedmax b47d1bfd04e44921`, `-postshots1 1925e9e80646a4fb`.
  Track-D variants `trackd-kill 4f3ba0…`-family + `trackd-kill-nonlethal` (RM_BOTSPAWN, `KBFTRACKD`) committed.
- Digest: `python tools/sigbypass-mod/text_digest.py <dll>` (RAW is the gate value). `--dupes` to confirm distinctness.
- Steam + `ags` run; game is down. Session is elevated, so `launch-redirect.ps1` needs no UAC.

## Why FK-32 is NOT in your way (do not fight it)

- **[M] the FK-32 window is ~40–60s** (S160: game survived 40s post-activation; the InputReleased spam is
  bounded to ~58ms; S158's "sub-second kill" was the mischaracterization S160 corrected; S159 saw 12+s).
- **[M] a player ability body executes via NATURAL input in ~56ms** (S158). A landing damage GE lands in <100ms.
- ⇒ **A cast that lands kills the target in the same frame, ~40s before FK-32.** Do NOT spend the session
  defeating FK-32 (E6; refuted 8 ways S168–S177). Fly inside the window; capture as you go.

## Why WALL E is not in your way (do not poke teams)

- **[M] a team-100 `BP_Minion_TargetBot_TTK_C` classifies ENEMY of the player** by RAW per-actor integer
  compare (IsEnemyTeamIndex 0x56EEEC0, IsEnemyTeam 0x56EEEB0, GetTeamFromActor 0x56EC360,
  GetLocalTeamRelationship 0x5630710, GetTeamIndex 0x55AE000 — via ITeamAgentInterface::GetTeamId /
  TeamComponent[+0xE0]; NONE reads the stripped ALokiGameState::TeamStates). Minion self-inits 100 in an
  ungated BeginPlay; player defaults 0/-1; 100 != player ⇒ Enemy. **Do NOT poke the minion's team.**
- **[M] no attribute-layer hostility gate** on the decrypted real-damage path (Health PreGE slot 89
  0x553DBFC gates only on IsA<Character>/attribute/sign; parent PostGE 0x553BE20 does attribution+IsA;
  ZERO IsEnemy calls). Residual [I]: Health's slot-90 PostGE 0x553C200 is dark (never executed; firing
  one real GE demand-decrypts it) — that's the apply, not the friendly-fire location.

## The one unproven thing E4 tests

Track D proved AdjustHealth (a direct Health write) kills a spawned minion. **What has NEVER been
measured: a PLAYER ability's damage EFFECT — a real GameplayEffect through execution →
PostGameplayEffectExecute, not a direct write — landing on a target's HP.** E4 is that measurement.

## The build — extend RM_BOTFIGHT (recommended) behind a new `#if KBFE4`

RM_BOTFIGHT already owns the player side: S155 bind (`KBFSELFCAL=1 KBFBINDAVATAR=1`), K_GRANT
(`BfBuildSpec`+`BfGiveAbilityNative`), and the S158 natural-input path (`KBFNATURALINPUT=1`). Set
`KBFABIL="Ability1"` — the code at `tutorial_launch.cpp:24035` resolves `abilCls` from the hero's
`Ability1` property = **GS_Ronin_LightAttack1** (the LMB basic, a real Health-reducing GE, cone in tap mode).

**⚠ STUDY FIRST — do not blind-inject.** `DoBotFight` (`tutorial_launch.cpp:23557`–~24608) is a
~1050-line, multi-phase, state-machine function. Under `KBFNATURALINPUT=1` the K_SPAWN/K_BIND/K_GRANT
arms are `#if !KBFNATURALINPUT`-compiled-OUT and a DIFFERENT setup runs: an S147 state machine
(`g_s147State`, states `S147_SETUP_ARMED`/`S147_SETUP_ABORT_REQUESTED`, `BfS147Finalize(...)`) that
binds+grants in phase-1, then SETUP_ABORTs (releases CDO ownership + unswaps all UFunctions) and a worker
waits for natural input. **Map this control flow before injecting.** Your minion spawn+seed must run in
phase-1, BEFORE the SETUP_ABORT, so the target is standing in front of the hero when the LMB tap arrives.
The `#if KBFNATURALINPUT` blocks to read: `tutorial_launch.cpp` ~1543, ~2156, ~2181, ~2193 (worker/PI
path) and the DoBotFight branches around K_ACTIVATE (~23977 `#if !KBFNATURALINPUT`) + the S147 finalize
paths. If the integration proves too tangled, a self-contained new `RM_E4` reusing the PRIMITIVES
(`SpawnActorCls`, the Track-D seed, `BfCallInitAAI`/InitAAI 0x447F410, the bind, the grant, and the
SETUP_ABORT mechanism copied deliberately) is an acceptable fallback — but reuse beats reimplement.

Add behind `#if KBFE4` (default 0, no `#else`, gates byte-identical):
1. **Spawn the target** (phase-1, before SETUP_ABORT): `SpawnActorCls(FindClassExact("BP_Minion_TargetBot_TTK_C"), "e4-target")`
   at ~200uu in FRONT of the player hero, inside the 360uu/110° LMB cone (compute from the hero's
   RootComponent RelativeLocation + its forward vector; the hero facing is -Y per S189-BOT — verify live).
   Plain `ALokiMinionCharacter`, no round-mode/drop-pod dependency (S135–S137). Latch its pointer.
2. **Seed the target ASC** — reuse the Track-D/`KBFTRACKD` code verbatim (committed `0107910`,
   `tutorial_launch.cpp` STATION 2–4): the minion ships a constructor-built `LokiAbilitySystemComponent`
   (so NO AddComponentByClass needed, unlike the Track-D LokiBot — read `bot+0xF00`/resolve the ASC),
   resolve its `LokiAttributeSetHealth` by name, `InitAbilityActorInfo(0x447F410)`, seed Health Base/Current
   @ +0x70 and MaxHealth @ +0x80 (FGameplayAttributeData 0x10-spaced, CurrentValue @ +0xC) to a LOW value
   (e.g. 100.0), register the sets in SpawnedAttributes if not already (Track-D DxAppend step), readback
   exact. ⚠ MaxHealth is GE-driven, NOT baked — seeding is REQUIRED; read pre-seed MaxHealth first.
3. **KE4DIRECTGE fallback** (separate knob): if the natural cast runs but HP doesn't move, apply
   `GE_Ronin_LightAttack_Damage` by handle (`ApplyGameplayEffectSpecToTarget`) OR the S156-B AdjustHealth(-N)
   direct write on the seeded minion. Arm ALONGSIDE the natural cast (dual instrumentation), not instead.

Variant (add to `build.ps1`): RM_BOTFIGHT + `-DKBFSELFCAL=1 -DKBFBINDAVATAR=1 -DKBFNATURALINPUT=1
-DKBFABIL=\"Ability1\" -DKBFE4=1` (+ the seed knobs the Track-D family uses). Build, `verify_dll` PASS,
gates byte-identical, `--dupes` clean.

## Spawn-time LIVE reads (pre-register; the offline gate's filter/inputid reader was a stub)

- player PlayerState `GetTeamId` (confirm != 100 — inferred 0/-1, never measured on the tutorial route).
- LightAttack1 InputID from the granted spec on the player ASC (only Ability3=5 is pinned; the fallback
  needs the spec HANDLE, not the InputID).
- LightAttack1's `FGameplayTargetDataFilter` axis (EnemiesOnly vs Class) — confirm it resolves the minion.
- minion post-spawn/pre-seed MaxHealth; seeded ASC AvatarActor bind confirmation.

## The flight

1. Stage `gft→fo→sp` (`configs/fk24-stage.ps1 -Probe tools\sigbypass-mod\build\<e4.dll> -Label e4 -AllowStale`),
   forceTutorialMatch route (already `true` in `server/internal/interactive/interactive.go`).
2. The arm spawns+seeds the minion, grants+binds LightAttack1, SETUP_ABORTs (shim out of the way).
3. START the target-HP RPM watcher + `Loki.log` tail BEFORE the cast (baseline stable = no self-decay).
4. Run `scratchpad/s190/tools/send-lmb.ps1` (built + parse-checked): a SHORT LMB tap (`-TapMs 150`, MUST
   be <240 or it fires the ranged fireblast projectile instead of the melee cone). `-Taps 2` is safe.
5. Watch the minion Health → 0.

### Pre-registered receipts
TARGET SPAWNED (LokiMinionCharacter +1, TargetBot_TTK, ASC non-null, in cone) · SEEDED (HealthSet 100/100
exact) · ABILITY BOUND (Items 0→1, valid Handle, Ability1) · BASELINE STABLE · BODY RAN (Loki.log
LightAttack1 phase trace at the tap) · DAMAGE ARRIVED (target OnDamaged/DPS fires, player=instigator) ·
**THE PREDICATE: minion Health seeded→0 under the PLAYER cast, TTK OnDeath fires.**

### Four separable outcomes (dual instrumentation is the honesty hinge)
[body ran + HP→0 + OnDamaged] = **SUCCESS, predicate met** · [body ran + HP flat + no OnDamaged] = WALL E
targeting filter → fire KE4DIRECTGE (if it drops HP, a real GE lands and the gate is at targeting, not the
attribute layer) · [body ran + by-handle GE also flat] = residual PostGameplayEffectExecute gate (0x553C200,
dark — firing one real GE demand-decrypts it for offline re-read) · [body did NOT run] = WALL P on
LightAttack1's own activation (a different wall than targeting). Even the worst case yields a graded result.

## Logistics / do-nots

- FK-31 staging death is ~27% and CLUSTERS (S190 hit 4 in a row) — budget ≥2–3 launches per armed window.
  Each PID FK-32s at ~285–293s uptime regardless of shim activity, so land the cast well before that.
- `launch-redirect.ps1 -NoHook` returns fast (game detaches). The game FK-32s on the ~4th–5th injection.
- Do NOT: use a shim TryActivate call (enters, never returns, 0xDEAD — natural input ONLY); poke the
  minion's team (self-inits 100); send an LMB hold ≥0.24s (fires the fireblast, not the cone); chase FK-32.
- The natural cast is THE PREDICATE; the fallback is the graded consolation (proves a real GE / direct
  write reduces the minion HP), NOT the predicate itself — keep them distinct in the write-up.
- Refuted approaches (do not repeat): `docs/s190-wallp-predicate-plan.md` "Refuted" section.
- On success write `docs/s191-e4-predicate-RESULT.md` and update the CLAUDE.md S190 frontier block.
