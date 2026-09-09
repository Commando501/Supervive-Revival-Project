# The bot's combat AI is ENTIRELY CLIENT-SIDE — settled 2026-09-09 (S189-BOT follow-up)

**Question that prompted this:** is there bot logic in our game files that would properly handle
gameplay, or was the bot AI all server-side (and therefore absent/stripped from the standalone client
we run)?

**Answer [M]:** the bot's decision-making — behaviour tree, blackboard, services, tasks, EQS queries,
difficulty tuning, and the native controller helpers those nodes call — is **all shipped in the client
and runs there.** It was NOT built server-side-only. What the standalone client lacks is the
server-**authority** runtime the AI's *actions and perception* route through, which is the same
FK-1 / WALL E / WALL P wall that blocks the player. **⇒ "AI that properly plays" needs NO bot logic
authored or recovered; it needs the two walls the Versus-AI mission already tracks.**

## Evidence

### 1. The full bot AI ships as Blueprint assets in our IoStore

`Loki/Content/Loki/Characters/AI/Bots/` (from `tools/extractor/out/allfiles.txt`), all `.uasset`
(client-executable Blueprint, not native-stripped):

| asset | role |
|---|---|
| `BT_HeroBots` | **the behaviour tree** (`ULokiCharacterGlobals.HeroBotBehaviorTree @+0x240` — what `RunBehaviorTree` is handed, S137) |
| `BB_HeroBots` | **the blackboard** — a COMBAT schema (see keys below) |
| `BTService_PickSpell` | choose which spell to cast |
| `BTService_ApplyAimError` | aim with difficulty-scaled error |
| `BTService_UpdateTargetCombatDistance` / `BTService_UpdateTargetLocationFromGoal` / `BTService_UpdateTrainDanger` | maintain combat range / goal position / hazard awareness |
| `BTT_CastSpell` | **cast a spell at the target** |
| `BTT_Dodge` | dodge |
| `BTT_InitiateMoveTo` / `BTT_FindSafeLocationFromTrain` | move to target / flee a hazard |
| `BTT_ClearFocusInfo` / `BTT_ClearTeamPlannerGoal` | reset focus / team-planner goal |
| `EQC_TargetEnemyContext` / `EQS_FindCombatPosition_Bot` | **Environment Query System: target context + choose where to stand in a fight** |
| `AC_HeroBot` | the bot actor component (`ULokiCharacterGlobals.HeroBotComponent @+0x248`) |
| `BP_BotSpawnLocation` / `BP_NavAbyss` | spawn markers / nav volume |
| `Effects/GE_TrivialBot` … `GE_NormalBot` (+ `GE_Easy75Bot`, `GE_Easy84Bot`) | difficulty tiers as GameplayEffects |

### 2. The blackboard is a fighting AI's working memory, not a wander stub

`BB_HeroBots` keys (extracted, `tools/extractor/out/BB_HeroBots.names.txt`, 15 keys — 5 bool + 10 typed):
`TargetEnemy`, `TargetEnemy_LastSeen`, `AggressionState`, `MaxCombatDistance`, `TargetCombatDistance`,
`CurrentSpell`, `BotGoalType`, `TargetLocation`, `SelfActor`, `NextUpdateGoalTime`, plus the bools
`MoveOverride`, `ForceMoveOverride`, `HasTargetWisp`, `HasTrainDanger`, `IsCharacterControllable`.
**`TargetEnemy` + `TargetEnemy_LastSeen` + `AggressionState` + `MaxCombatDistance` + `CurrentSpell` is
exactly the memory a combat AI uses to pick a target, track it, close to a fighting range, and cast.**

### 3. It runs on our standalone client (S137 flight 4, live [M])

`ALokiBotController::OnPossess` (`0x5565470`) reached `RunBehaviorTree(Cfg->[0x240])` and built:
- `BrainComponent (+0x498) = BehaviorTreeComponent` with **`NodeInstances = 21`** (a real tree, not
  defaulted — `DefaultBehaviorTreeAsset = NULL`),
- `Blackboard (+0x4B0) = BlackboardComponent` with `BlackboardAsset = a real BlackboardData`, **15 keys**,
  cross-wired to the controller. Read `docs/s137-playerstate-and-lokibot-settled.md` §7b.

### 4. The controller's native helpers are REAL, not stripped

S153 native-UFunction sweep (`scratchpad/s153_native_ufunction_sweep_v2.csv`): **26 / 26 enumerated
`ALokiBotController` functions grade REAL** — `GenerateAimError`, `GetUsableSpells`, `GetExactSpell`,
`TryToDash`, `GetTargetJumpLocation`, `GetLMBMaxRange`, `GetBotTargetingRangeMultiplier`,
`GetPersonalGoal`, `IsWithinXYDistanceSqOfPlayerHero`, `IsPlayerSeenLocation`, `IsSeenByPlayers`,
`HandleLivingStateChanged`, `UpdateCharacterControllable`, `SendBotEmote`, … The tree's nodes and the
helpers they call are present.

## What IS server-authority-stripped (the same walls the player hits)

The bot doesn't fight on this client not because its brain is missing but because three effectors/inputs
its outputs depend on are the project's known stripped-authority walls:

1. **Enemy perception** — `ALokiMinionCharacter::AuthUpdateEnemyList`, `AuthUpdateNearbyVisibleEnemies`,
   `AuthAnyVisibleEnemyHeroCharactersInRange` are all stripped folds (`tail-jmp 0xF7EC20` void_ret /
   `0xF7EB60` LokiIsServer-FALSE; S153). These are what populate the blackboard's `TargetEnemy`. Gutted →
   `TargetEnemy` stays empty. ⚠ NOTE: the CLIENT-side targeting helpers (`IsWithinXYDistanceSqOfPlayerHero`,
   `IsPlayerSeenLocation`, `GetExactSpell`) are REAL, so a *client* perception path may exist; the
   stripped ones are specifically the server-authority enemy-list maintenance. Untested which the BT uses.
2. **Teams / hostility (WALL E)** — `ALokiGameState::SetPlayerTeam` + `GetOrCreateTeamState` are stripped
   (`GetOrCreateTeamState` returns nullptr unconditionally, [M]); `SetNumTeams` is a void fold. No team
   state can exist → nothing is hostile → there is no enemy to perceive in the first place.
3. **Ability activation (WALL P)** — even the player's own ability body doesn't durably execute on this
   standalone client (S158 got the MiniDash body to run via natural input, then a silent FK-32 protector
   kill). `BTT_CastSpell` would hit the same wall.

## What we observed this session, and why

S189-BOT measured the bot running its native `Tick`'s **random wander** (the fallback when the tree has no
goal/target). In the tutorial world there is no hostile target (no teams), so `BT_HeroBots` never engages
combat — the wander is all that ran. That is consistent with, not contradictory to, "the combat AI is
present": the tree needs a populated `TargetEnemy` to leave the wander/idle branch.

## Implication for the mission (grade the claims honestly)

- **[M]** The bot's combat AI (BT + blackboard + services + tasks + EQS + difficulty GEs + 26 real native
  helpers) is client-side and instantiates live on our client. Not server-side-only.
- **[I, strong] (NOT measured in combat):** given a valid hostile `TargetEnemy` and a working
  ability-execution path, the shipped `BT_HeroBots` would drive real combat with no new AI authored. We
  have never watched the tree run a combat cycle — no target ever existed, and S137 recorded no
  `LogBehaviorTree` positive control — so this is an inference from the asset structure + real helpers.
- ⇒ The acceptance-predicate stretch "the bot fights back" is now a **two-walls problem (E hostility + P
  cast), not an AI-authoring problem.** Everything the bot needs to think is already in `/Bots/`.

## Files / how to reproduce

- Asset list: `grep -i "Characters/AI/Bots/" tools/extractor/out/allfiles.txt`
- Blackboard keys: `tools/extractor/out/BB_HeroBots.names.txt` (+ `.json`)
- Controller REAL/STRIPPED: `grep "^ALokiBotController," scratchpad/s153_native_ufunction_sweep_v2.csv`
- Perception stripping: `grep -i "AuthUpdateEnemyList\|AuthAnyVisibleEnemy" scratchpad/s153_native_ufunction_sweep_v2.csv`
- Live BT instantiation: `docs/s137-playerstate-and-lokibot-settled.md` §7b (NodeInstances=21, 15 keys)
- Config CDO (`ULokiCharacterGlobals`, `HeroBotBehaviorTree @+0x240`): same doc, §config CDO
- ★ **Never dumped: `BT_HeroBots.uasset` itself.** A `bpdump`/`rawfile` extract of `BT_HeroBots` and its
  `BTService_*`/`BTT_*` nodes would show exactly which node classes are Blueprint vs native and which
  native leaves they call — the one offline step that would upgrade the [I,strong] to a mapped tree.
