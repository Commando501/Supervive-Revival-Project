# S190 — WALL P attack plan + the E4 predicate flight (2026-09-09)

The acceptance predicate: **a PLAYER ability that DAMAGES and KILLS a hostile enemy.** After Track D
(a bot dies from the game's own AdjustHealth) and the bot-cast recon (bot & player both cast via
`TryActivateAbilityByClass`), WALL P is the last wall. This plan (two adversarially-verified workflows,
zero-launch) decomposes it and gives the concrete flight.

## WALL P is THREE separable mechanisms — only one is on the predicate critical path

1. **Activation entry — WORKS via NATURAL input [M].** S147: a valid MiniDash natural-input activation
   commits real GAS state (ActiveCount 0→1, Mana 10→0). A SHIM-originated `TryActivateAbilityByClass`/
   native-handle call enters, never returns, then `0xDEAD` (S145/S146; the valid-handle-vs-INDEX_NONE A/B
   proves entry/ABI/dispatch are NOT the trigger — the shim-originated valid-handle downstream branch is).
   ⇒ **Use natural input; never a shim TryActivate call.**
2. **Ability body execution — WORKS via natural input [M].** S158 drove MiniDash's full phase machine
   (Warmup→Channeling→Invoke→Pre/Post Dash Start) in 56ms on one frame after a SETUP_ABORT released the
   shim's CDO ownership. The shim's own observation apparatus was what suppressed the body in S146/S147.
3. **Durable survival — FK-32 protector, undefeated (8 candidates refuted S168–S177).** BUT: **[M] the
   FK-32 window is ~40–60s** (S160: game survived 40s post-activation; the InputReleased spam is bounded
   to ~58ms and harmless; S158's "sub-second kill" was the mischaracterization S160 corrected; S159 saw
   12+s). An ability body executes in ~56ms and a damage effect, if it lands, lands in <100ms.
   ⇒ **FK-32 is OFF the predicate critical path.** Defeating it is needed only for a REPEATABLE Versus-AI
   loop, which the predicate explicitly does not require. Do NOT spend the predicate push on FK-32.

**⇒ The only unproven thing for the predicate: a PLAYER ability's damage EFFECT landing on a target's HP
(never measured — MiniDash is a dash), and whether hostility/team gates it (WALL E).**

## The E4 flight design — a player LMB kills a target dummy inside the window

- **Target: `BP_Minion_TargetBot_TTK_C`** (practice-range TTK bot). The game's own "designed to be killed
  by the player" target: passive (`AggroRange=0`, `bAddToEnemyListOnDamage=False` — won't fight back or
  trigger FK-32), inherits `BP_Minion_C`'s `MinionTeamID=100`/`OriginalTeamIndex=-10` (the AI-minion
  faction players damage in normal play), ships a **constructor-built** `LokiAbilitySystemComponent` +
  `BaseSet` + `HealthSet`, and is instrumented to DIE (`OnDeathTime`/`OnFirstDamageTime`/`OnDeath` =
  free receipts). Plain `LokiMinionCharacter`, so `SpawnActor` works on the tutorial route (S135–S137).
  It is a MINION-category actor, so an ability filtering on `ETargetClassCategory` (MinionCharacterOnly/
  All) can select it on the CLASS axis, sidestepping the hero ally/enemy affiliation gate. ⚠ MaxHealth is
  GE-driven (`AttributesKey=PracticeRangeTargetDummy`), NOT baked — its ASC must be InitAAI'd + SEEDED
  (S156 compound seed) to a LOW value (e.g. 100) so one LMB tap kills. ⚠ SECONDARY `BP_Minion_TargetDummy_C`
  self-heals (`GE_Shared_FullHeal_Inf`) — usable for "HP drops" but not "kill" unless that GE is stripped.
- **Ability: `GS_Ronin_LightAttack1`** (LMB basic, slot `Ability1`). Free (no mana), a single LMB TAP,
  lands a REAL Health-reducing GE (`GE_Ronin_LightAttack_Damage`, INSTANT, through the execution→
  `PostGameplayEffectExecute` pipeline — NOT AdjustHealth, NOT a self-modifier). 360uu/110° melee CONE,
  NOT a skillshot in tap mode. ⚠⚠ `bIsPressOrHold=True, HoldMinimumDuration=0.24` — a hold ≥0.24s fires a
  RANGED FIREBLAST PROJECTILE instead; the driver MUST send a **short LMB down/up (<0.24s)**.

## WALL E verdict: [unknown] — the load-bearing uncertainty; the fallback keeps E4 productive anyway

- GE APPLICATION itself is not team-gated [I-strong] (no ApplicationRequirements team check); the team
  check lives in the CALLER / TARGET ACQUISITION [M]. The natural LMB cast relies on the ability's own
  `FLokiGameplayTargetDataFilterNew` (ETargetAlly {All/AlliesOnly/EnemiesOnly} × ETargetClassCategory).
- A MINION target MAY be selected on the MinionCharacterOnly class axis (why practice dummies are
  shootable) regardless of ally/enemy resolution — the whole reason to use a minion, not a hero bot.
  Unproven: (a) the filter GS_Ronin_LightAttack1 actually uses; (b) whether `MinionTeamID=100` resolves
  HOSTILE on the standalone client (team-STATE is stripped); (c) a residual gate at
  `ULokiAttributeSetHealth::PostGameplayEffectExecute` (the Damage-meta→Health path a real GE takes but
  AdjustHealth bypasses — S156-B does NOT cover it).
- **FALLBACK (build behind knob `KE4DIRECTGE`):** if the body runs but HP does not move (targeting
  filtered the target), `ApplyGameplayEffectSpecToTarget(GE_Ronin_LightAttack_Damage)` on the target ASC
  by handle (S142 approach) — proves a REAL damage GE (not AdjustHealth) reduces the target's HP and
  isolates the attribute-layer gate from the targeting gate. Keeps the launch productive under negative WALL E.

## OFFLINE GATE — do BEFORE the launch (turns WALL E [I]→[M], prevents a false-negative flight)

1. Disassemble `ULokiTeamStatics::IsEnemyTeam` / `GetLocalTeamRelationship`: team-100 minion vs player =
   Enemy / Neutral / Invalid on the standalone client?
2. Disassemble `ULokiAttributeSetHealth::PostGameplayEffectExecute`: friendly-fire/neutral suppression on
   the real Damage-meta→Health path?
3. Read `GS_Ronin_LightAttack1`'s MeleeHit / `GetDefaultMeleeTargetingParams` filter: `ETargetAlly` +
   `ETargetClassCategory` (does it select a minion?).
4. Read the numeric `LokiAbilityInputID` for `Ability1` (LMB) — only Ability3=5 is pinned; needed to bind.
5. Confirm the seed approach (seed a LOW MaxHealth via S156) vs any baked HP.
6. Confirm whether `ALokiMinionCharacter::BeginPlay` self-inits team-100 + attributes or needs poking
   (S152/S153 stripped `Auth*` folds).

## E4 flight steps (reuse proven [M] machinery)

stage (gft→fo→sp) → SpawnActor `BP_Minion_TargetBot_TTK_C` ~200uu in front of the hero (inside the cone) →
seed its ASC (InitAAI + S156 compound seed MaxHealth+Health=100) → grant+bind `GS_Ronin_LightAttack1` on
the PLAYER at Ability1 (S143/S144/S145) → SETUP_ABORT (release CDO, unswap; NO shim TryActivate) → start
the target-HP RPM watcher + Loki.log tail (baseline stable) → P/Invoke a SHORT LMB tap (<0.24s) → watch
target Health → 0. Fallback arm (KE4DIRECTGE) on hand.

### Receipts (pre-registered)
TARGET SPAWNED (LokiMinionCharacter +1, TargetBot_TTK, ASC non-null, in cone) · TARGET SEEDED (HealthSet
100/100 exact) · ABILITY BOUND (Items 0→1, Handle, Ability1) · PRE-CAST BASELINE STABLE (no self-decay) ·
BODY RAN (Loki.log LightAttack1 phase trace at the tap) · DAMAGE ARRIVED (target OnDamaged/DPS fires,
player = instigator) · **THE PREDICATE: target Health seeded→0 under the player cast, TTK OnDeath fires.**

### Four separable outcomes (the design's honesty hinge)
[body ran + HP→0 + OnDamaged] = SUCCESS · [body ran + HP flat + no OnDamaged] = WALL E targeting filter →
fire the by-handle GE fallback · [body ran + by-handle GE also flat] = residual PostGameplayEffectExecute
gate (real, unanticipated) · [body did not run] = WALL P on LightAttack1's own activation.

### Refuted — do NOT repeat
shim-originated TryActivate (dies+0xDEAD) · `.text`-patching runtime.dll 0x80F7F0 (FK-31) · packer2 syscall
poke as FK-32 defeat (held stable, FK-32 fired anyway) · VEH intercept (callback never invoked) · thread
suspension as an FK-32 defeat (defeats FK-31 only) · ARM-G borrowed CDO ASC for GAS apply (empty
SpawnedAttributes + null AbilityActorInfo) · RM_BOTFIGHT `botfight-kill 0x31` · hand-injected teams
(SetPlayerTeam/GetOrCreateTeamState are stripped folds). E6 (FK-32 attack) is DEPRIORITIZED off the
predicate critical path.
