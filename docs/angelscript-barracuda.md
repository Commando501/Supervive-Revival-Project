# Barracuda — the hidden MOBA mode (Angelscript decompile)

**Date:** 2026-07-26 · **Build:** shipping 2025-12-17 · **Source:**
`Loki/Script/PrecompiledScript.Cache` decompiled by `tools/asdump/asdump.py`
(spec: `tools/asdump/FORMAT.md`), cross-checked against `Binds.Cache`,
`mappings.usmap`, the shipped IoStore directory index, and CUE4Parse asset dumps.

Everything below is grounded in bytes. Where I am inferring from a *name* rather
than from decompiled code, the line says **[name-only]**. Where the decompiler
mis-rendered something and I corrected it from the raw disassembly, the line says
**[corrected from disasm]** and gives the instruction addresses.

---

## 0. The one-paragraph answer

**Barracuda is a complete, two-team, lane-pushing MOBA built inside SUPERVIVE.**
Not a prototype folder, not a name — 28 Angelscript modules (10 classes,
~44 KB of bytecode, 340 functions) implement lane creep waves, jungle camps with
leash-and-reset, towers with their own aggro table, a day/night cycle that gates
spawners, per-team shutdown/assist gold, mercy-and-underdog XP scaling, a
death-timer curve, and a full DOTA-style item shop with a recursive recipe graph
and a UI tree. The Angelscript layer is only half of it: the C++ side carries a
whole second attribute system (`BarracudaStrength/Agility/Intelligence`, armour,
penetration, crit, attack speed, per-level scaling — 34 attributes on
`ULokiAttributeSet`), a `ALokiTowerDefenseGameMode` base with a
`MainObjectiveClass`, and `ALokiTower`. And **726 Barracuda content assets ship
in the retail paks**, including `BP_GameMode_Barracuda`, `BP_LokiTower_Nexus`,
9 shop loot tables, 51 item recipe folders, 17 per-hero recommended build
loadouts, tower meshes, and announcer VO for "citadel under attack".

The mode is finished enough to have shipped VO. What I could **not** find is the
map (§9).

---

## 1. Module census

All 28 modules, exactly as they appear in the cache. `fns` = functions emitted
(includes compiler-generated ctors/`StaticClass`/`Spawn`/`Get`/delegate thunks);
`bc` = bytes of bytecode.

| # | Module (`Barracuda/…`) | Classes | fns | bc |
|---|---|---|---:|---:|
| 1 | `GameMode/BarracudaGameMode.as` | `ABarracudaGameMode` | 32 | 8128 |
| 2 | `GameMode/BarracudaPlayerSpawnerComponent.as` | `UBarracudaPlayerSpawnerComponent` | 11 | 1760 |
| 3 | `GameMode/BarracudaRallyMinionsComponent.as` | `UBarracudaRallyMinionsComponent` | 10 | 1316 |
| 4 | `GameState/BarracudaGameStateComponent.as` | `UBarracudaGameStateComponent`, `FOnDragonKillsUpdated`, `FOnTeamKillsUpdated` | 43 | 4216 |
| 5 | `GameState/BarracudaGameStateGlobals.as` | *(5 free functions)* | 5 | 624 |
| 6 | `GameState/BarracudaTeamState.as` | `ABarracudaTeamState` | 6 | 424 |
| 7 | `GameState/BarracudaTeamState_TeamOnly.as` | `ABarracudaTeamState_TeamOnly` | 9 | 624 |
| 8 | `Components/BarracudaLaneComponent.as` | `UBarracudaLaneComponent`, `FOnLaneIndexUpdated` | 20 | 996 |
| 9 | `Components/BarracudaStructureComponent.as` | `UBarracudaStructureComponent` | 9 | 540 |
| 10 | `Components/BarracudaPlayerStateComponent.as` | `UBarracudaPlayerStateComponent`, `FNextRespawnTimeChanged` | 26 | 1516 |
| 11 | `Components/BarracudaMinionTargetingComponent.as` | `UBarracudaMinionTargetingComponent` *(abstract)* | 13 | 1416 |
| 12 | `Components/BarracudaLaneCreepTargetingComponent.as` | `UBarracudaLaneCreepTargetingComponent` | 7 | 976 |
| 13 | `Components/BarracudaJungleCreepTargetingComponent.as` | `UBarracudaJungleCreepTargetingComponent` | 7 | 936 |
| 14 | `Components/BarracudaTowerTargetingComponent.as` | `UBarracudaTowerTargetingComponent` | 8 | 1364 |
| 15 | `Components/BarracudaJungleCreepComponent.as` | `UBarracudaJungleCreepComponent` | 8 | 844 |
| 16 | `Spawners/BarracudaMinionSpawner.as` | `FGametimeToLevel`, `FMinionWaveEntry`, `FMinionWave`, `ABarracudaMinionSpawner` | 34 | 10236 |
| 17 | `Minion/BarracudaLaneMinionConfig.as` | `FBarracudaLaneMinionConfig` | 1 | 124 |
| 18 | `Minion/BarracudaMinionRewardComponent.as` | `UBarracudaMinionRewardComponent` | 11 | 1040 |
| 19 | `Minion/Waypoints/BarracudaMinionWaypoint.as` | `ABarracudaMinionWaypoint` | 8 | 908 |
| 20 | `Minion/Waypoints/BarracudaMinionWaypointFollowerComponent.as` | `UBarracudaMinionWaypointFollowerComponent` | 15 | 3580 |
| 21 | `Minion/Waypoints/BTService_UpdateMinionWaypoint.as` | `UBTService_BarracudaUpdateMinionWaypoint` | 6 | 352 |
| 22 | `Shop/BarracudaShop.as` | `UBarracudaShopItemGraphNode`, `FBarracudaShopPurchasePlan`, `ABarracudaShop` | 34 | 6788 |
| 23 | `Shop/BarracudaShopPlayerControllerComponent.as` | `UBarracudaShopPlayerControllerComponent` | 13 | 1416 |
| 24 | `Shop/BarracudaShopItemListWidget.as` | `UBarracudaShopItemListWidget` | 15 | 2280 |
| 25 | `Shop/BarracudaShopItemTreeWidget.as` | `UBarracudaShopItemTreeWidget` | 10 | 956 |
| 26 | `Shop/BarracudaShopItemTreeNodeWidget.as` | `UBarracudaShopItemTreeNodeWidget` | 12 | 2088 |
| 27 | `Shop/BarracudaShopItemWidget.as` | `UBarracudaShopItemWidget` | 9 | 1540 |
| 28 | `Shop/BarraucdaShopFilterWidget.as` *(sic — typo shipped)* | `FBarracudaShopTagFilter`, `UBarraucdaShopFilterWidget` | 6 | 292 |

Enums declared in script: `EBarracudaRespawnBehaviorType` (6),
`EBarracudaMinionGoldRewardMethod` (2), `EBarracudaShopValueType` (4).

---

## 2. The class graph and its native anchors

```
ALokiGameMode  (C++)
 └ ALokiTowerDefenseGameMode  (C++, /Script/Loki)  ← property: TSubclassOf<AActor> MainObjectiveClass
    └ ABarracudaGameMode  (Angelscript)
         ├ UBarracudaRallyMinionsComponent      (DefaultComponent)
         └ UBarracudaPlayerSpawnerComponent     (DefaultComponent)

ALokiGameState (C++)
 └ + UBarracudaGameStateComponent   (Angelscript, replicated, added by BP_GameState_Barracuda)
     └ owns ABarracudaShop, TSet<AActor> Structures, TSet<ABarracudaMinionWaypoint>,
            TArray<FBarracudaPhase> BarracudaPhases

ALokiTeamState (C++)          → ABarracudaTeamState  (AS)
ALokiTeamState_TeamOnly (C++) → ABarracudaTeamState_TeamOnly (AS)   ← client-visible spawn timers
ALokiPlayerState (C++)         + UBarracudaPlayerStateComponent (AS, replicated respawn clock)

ALokiActor (C++) → ABarracudaMinionSpawner (AS)
AActor    (C++) → ABarracudaMinionWaypoint (AS), ABarracudaShop (AS)

ULokiMinionTargetingComponent (C++)
 └ UBarracudaMinionTargetingComponent (AS, abstract)
    ├ UBarracudaLaneCreepTargetingComponent
    ├ UBarracudaJungleCreepTargetingComponent
    └ UBarracudaTowerTargetingComponent
```

**Native types Barracuda depends on** (from `Binds.Cache`, i.e. compiled C++, not
script):

| Type | Members that matter |
|---|---|
| `ALokiTowerDefenseGameMode` | `TSubclassOf<AActor> MainObjectiveClass` — the win condition object |
| `ALokiTower` | `TimeBetweenAttacks`, `TimeForFirstAttack`, `TeamIndex`, `TowerRange`, `TimeBetweenEnemyListUpdates`, `ClientAimingSpeed`; events `ReceiveAttack`, `ReceiveEnemyListChanged`, `ReceiveTargetChanged`, `ReceiveClientAimingVectorChanged`; `AuthGetCharactersInRange()` |
| `FBarracudaPhase` | `EBarracudaPhaseType Type`, `float32 Duration` |
| `EBarracudaPhaseType` | `Invalid=0, Pregame=1, Main=2` (from usmap) |
| `FGameEvent_BarracudaPhaseChanged` | `PreviousPhaseType`, `CurrentPhaseType` |
| `FGameEvent_BarracudaTowerDestroyed` | `ALokiTower DestroyedTower` |
| `FGameEvent_BarracudaRespawnTimeChanged_PlayerState` | `ALokiPlayerState PlayerState` |
| `ALokiBarracudaLoadout` | `StartingItems`, `EarlyGameItems`, `MidGameItems`, `LateGameItems`, `LuxuryItems`, `Consumables` |
| `ALokiHeroCharacter` | `TSoftClassPtr<ALokiBarracudaLoadout> BarracudaRecommendedLoadout` |
| `ALokiGameState` | `IsBarracudaBP()`, `IsBarracudaSplit()`, `IsBarracudaSplitSilent()` → `EIsBarracuda{Barracuda,NotBarracuda}` |
| `ULokiAttributeSet` | **34** `Barracuda*` `FGameplayAttributeData` fields (§8) |
| `UGameplayEffect` | `bool bSkipInBarracuda` |
| `FLokiGameplayAbilityLevelingInformation` | `bool bIsHiddenInBarracuda` |
| `ULokiCharacterGlobals` | `BarracudaMaxHealthPerPoint`, `…HealthRegenPerPoint`, `…ManaRegenPerPoint`, `…MaxManaPerPoint`, `…MaxAttackSpeedPerPoint`, `…MoveSpeedPerPoint`, `…PhysicalArmorPerPoint`, `…MagicArmorPerPoint`, `BarracudaStrength/Intelligence/AgilityCharacterTag`, `UCurveTable BarracudaDashScaling` |
| MMCs | `ULokiMMC_BarracudaStrength`, `…Agility`, `…Intelligence`, `…PrimaryAttackSpeed` |

That table is the strongest single piece of evidence that Barracuda was a
first-class mode: **the shipping game's core attribute set, ability metadata,
gameplay-effect struct and hero asset all carry Barracuda-specific fields.** You
do not thread a mode through `ULokiAttributeSet` for a game jam.

---

## 3. Match structure — phases, day/night, win condition

### 3.1 Phase machine (`UBarracudaGameStateComponent`)

Barracuda runs a *second* phase timeline on top of the engine's `ERoundPhase`.

```
UPROPERTY(EditableOnDefaults)      TArray<FBarracudaPhase> BarracudaPhases;  // {Type, Duration}
UPROPERTY(Replicated, RepNotify)   int    CurrentPhaseIndex;                 // OnRep_CurrentPhaseIndex
UPROPERTY(Replicated)              float64 CurrentPhaseStartTime;
```

`Tick_Implementation` (server only):

```
if (!LokiIsServer) return;
if (BarracudaPhases.IsValidIndex(CurrentPhaseIndex + 1)) {
    p = BarracudaPhases[CurrentPhaseIndex];
    if (p.Duration > 0 && ServerTime - CurrentPhaseStartTime > p.Duration)
        AuthMoveToNextBarracudaPhase();
}
```

`AuthMoveToNextBarracudaPhase()` records the *outgoing* phase type, increments the
index, stamps `CurrentPhaseStartTime = ServerTime`, then
`EmitPhaseChangedEvent(previousType)`, which broadcasts
`FGameEvent_BarracudaPhaseChanged{Previous, Current}` on the **global** game-event
router. `OnRep_CurrentPhaseIndex` re-emits the same event client-side, so every
listener (game mode, every spawner) is phase-aware on both ends.

Free helpers in `BarracudaGameStateGlobals.as`:
`GetBarracudaGameStateComponent()`, `GetCurrentBarracudaPhase()`,
`GetCurrentBarracudaPhaseType()`, `GetCurrentBarracudaPhaseTime()`,
`GetCurrentBarracudaPhaseTimeReminaing()` *(sic)*.

### 3.2 Day / night

```
ABarracudaGameMode:
  float64 DayNightDuration = 300.0        // 5 real minutes per half-cycle
  bool    bIsDay           = false
  float32 MatchStartTime   = 999999.0     // "not started" sentinel
UBarracudaGameStateComponent:
  float64 NextDayNightSwapTime      = 60.0
  bool    bDayNightTransitionEnabled = true   (replicated NextDayNightSwapTime)
```

- On `FGameEvent_BarracudaPhaseChanged` with `CurrentPhaseType == Main (2)`:
  `OnNewDay()`, and `NextDayNightSwapTime = ServerTime + 60`.
- `Tick` → `HandleDayNight()`: once `HasBarracudaMatchStarted()`
  (`ServerTime >= MatchStartTime`) and `bDayNightTransitionEnabled`, when
  `GetMatchTime() >= NextDayNightSwapTime`, flip `bIsDay`, fire
  `OnNewDay()`/`OnNewNight()` (BlueprintEvents, empty in script — the BP paints
  the sky), and `NextDayNightSwapTime += DayNightDuration`.
- `OnNewPhase_Implementation(NextPhase, LastPhase)`: entering `ERoundPhase::EGP_Combat`
  forces `bIsDay = false` and fires `OnNewNight()` — **the match opens at night.**

Note the unit mismatch: the initial swap time is set from `ServerTime + 60`, but
`HandleDayNight` compares it against `GetMatchTime()` (`ServerTime - MatchStartTime`).
This is in the shipped bytecode; I am not smoothing it over.

### 3.3 Win condition

Not in Angelscript. `ABarracudaGameMode` extends `ALokiTowerDefenseGameMode`,
whose only reflected property is `TSubclassOf<AActor> MainObjectiveClass`, and
`BP_GameMode_Barracuda` overrides a Blueprint function literally named
`ShouldGameEnd` (plus `WillInterceptEliminatedTeam`). `BP_GameState_Barracuda`
overrides `OnAuthTowerDestroyed`, `GetDeadTowers`,
`OnGameEvent_BarracudaTowerDestroyed`, `FireStartingHorn`, `MultiHorn`.
The shipped asset `BP_LokiTower_Nexus.uasset` sits next to `BP_LokiTower.uasset`
in `GameModes/Barracuda/Minions/Towers/`, and the announcer VO includes
`vo_announcer_computer_barracuda_citadel_underattack`.

⇒ **Win condition = destroy the enemy Nexus/Citadel**, evaluated in Blueprint
bytecode I did not decompile. This is an inference from class names + BP function
names + shipped VO, not from decompiled logic. **[name-only, but triangulated]**

Script *does* own the tower-first-blood flag:

```
bool TowerKilled_Implementation(ALokiTower@ TargetTower) {
    bool wasFirst = !bAnyTowersKilled;   // returns true only for the first tower ever
    bAnyTowersKilled = true;
    return wasFirst;
}
```

---

## 4. Lanes, waypoints and creep pathing

### 4.1 `UBarracudaLaneComponent` — the lane tag

```
UPROPERTY(EditableOnDefaults, EditableOnInstance) int LaneIndex;      // default -1
UPROPERTY(...)                FOnLaneIndexUpdated OnLaneIndexUpdated; // (comp, old, new)
bool HasLaneIndex()                       { return LaneIndex != -1; }
void SetLaneIndex(int NewValue)  [BlueprintAuthorityOnly]
__InitDefaults: LaneIndex = -1; bReplicates = false; bExcludeFromClient = true;
```

Server-only, non-replicated. A spawner, a waypoint, a barracks and a creep all
carry one; matching `LaneIndex` is what binds them together.

### 4.2 `ABarracudaMinionWaypoint` — a doubly-linked lane path

```
int                       InitialLaneIndex;        // default -1
ABarracudaMinionWaypoint@ WaypointTowardTeam0;
ABarracudaMinionWaypoint@ WaypointTowardTeam1;
UBoxComponent@            TriggerComponent;        // root, extent 200³, profile "Trigger"
UBarracudaLaneComponent@  LaneComponent;
__InitDefaults: bReplicates=false; SetActorHiddenInGame(true); bNetLoadOnClient=false;
```

`LokiBeginPlay`: pushes `InitialLaneIndex` into the lane component, binds
`TriggerComponent.OnComponentBeginOverlap → HandleTriggerOverlap`, and registers
itself in `GameStateComponent.MinionWaypoints`.

```
GetNextWaypoint(Actor) = (TeamOf(Actor) == 0) ? WaypointTowardTeam1 : WaypointTowardTeam0;
```

So each waypoint is a node in a **bidirectional chain**: team 0 walks the
`…TowardTeam1` links, team 1 walks the `…TowardTeam0` links. One placed chain
serves both lanes' directions.

### 4.3 `UBarracudaMinionWaypointFollowerComponent`

```
float64 LastWaypointTime, LastCombatTime, TimeFirstArrivedAtCachedLocation;
FVector CachedLocation;
ABarracudaMinionWaypoint@ CurrentWaypoint, LastWaypoint;
bool    bDrawDebug = false;
float64 DebugDrawPathDurationWarningThreshold = 30.0;
float64 DebugDrawPathDurationErrorThreshold   = 90.0;
__InitDefaults: bReplicates=false; ComponentTickEnabled=true; bExcludeFromClient=true;
```

`GetInitialWaypoint()` — the spawn-side terminus lookup:

```
lane = LaneComponent(Owner).LaneIndex;
isTeam0 = (TeamOf(Owner) == 0);
foreach wp in GameStateComponent.MinionWaypoints:
    if (LaneComponent(wp).LaneIndex != lane) continue;
    if ( isTeam0 && wp.WaypointTowardTeam0 == nullptr) return wp;   // team-0 end of chain
    if (!isTeam0 && wp.WaypointTowardTeam1 == nullptr) return wp;   // team-1 end of chain
```

i.e. a creep starts at the node with **no further link toward its own base** and
then walks outward. `ReachedWaypoint(wp)` **[corrected from disasm, `0x2de8a`
+0x02C…+0x08C]**: the decompiler printed the two `REFCPY` assignments backwards;
the bytecode is

```
if (CurrentWaypoint == wp) {
    LastWaypoint    = CurrentWaypoint;
    CurrentWaypoint = wp.GetNextWaypoint(GetOwner());
}
```

`GetTargetLocationForCurrentWaypoint()` projects the waypoint's actor location
onto the navmesh (`UNavigationSystemV1::ProjectPointToNavigation`) and falls back
to the raw location.

`IsStuck()`:

```
stalledLongEnough = (ServerTime - TimeFirstArrivedAtCachedLocation) > 5.0
offNavmesh        = LokiCharacterMovement.CurrentFloor.bWalkableFloor == false
if (stalledLongEnough && offNavmesh)                     return true;
if ((ServerTime - LastCombatTime) < 5.0)                 return false;   // fighting is not stuck
return stalledLongEnough;
```

`TryRescue()` teleports the creep to `LastWaypoint`'s location (or, failing that,
the current waypoint target). `Tick` refreshes `LastCombatTime` whenever the
owner has `State.Combat.InCombat`, tracks `CachedLocation`, and when
`bDrawDebug` draws a green→yellow(>30 s)→red(>90 s) path line plus a red capsule
(radius 500, half-height 100) for the error case.

### 4.4 `UBTService_BarracudaUpdateMinionWaypoint`

A behaviour-tree service (`UBTService_BlueprintBase`, `Interval = 0.01`,
`RandomDeviation = 0`) whose `TickAI` writes
`GetTargetLocationForCurrentWaypoint()` into the blackboard vector key
`WaypointLocationKey`. Shipped BTs `BT_LaneMinion_Barracuda.uasset` and
`BT_JungleMinion_Barracuda.uasset` consume it. **[asset names only]**

---

## 5. Creep waves — `ABarracudaMinionSpawner` (the largest module, 10 236 B)

### 5.1 Data model

```
UCLASS(Placeable, Blueprintable) class ABarracudaMinionSpawner : ALokiActor

struct FMinionWaveEntry { TSubclassOf<ALokiMinionCharacter@> MinionClass;
                          int Count; int MinimumMatchTime; }
struct FMinionWave      { TArray<FMinionWaveEntry> Entries; }
struct FGametimeToLevel { float64 Gametime; int Level; }

enum EBarracudaRespawnBehaviorType {
    AlwaysSpawn = 0,                 // fixed clock, spawn every SpawnPeriod
    ReplaceSpawns = 1,               // clear old wave, then spawn
    SkipSpawnWhenOldExists = 2,      // don't spawn while any minion still alive
    StartRespawnTimerAfterDeath = 3, // timer starts only once the camp is empty
    AliveAtNight = 4,                // day/night driven, not clock driven
    AliveDuringDay = 5,
}
```

Properties (with `__InitDefaults` values where set):

| Property | Default | Notes |
|---|---|---|
| `int InitialTeam` | `0` | replicated; pushed to `ULokiTeamComponent` on BeginPlay |
| `float64 SpawnPeriod` | `30.0` | seconds between waves |
| `EBarracudaPhaseType MinimumBarracudaPhaseType` | `Invalid (0)` | gate: spawn loop won't arm below this phase |
| `float64 InitialSpawnDelay` | `0` | edit-gated off for the day/night respawn types |
| `bool bStaggerSpawn` | `false` | spawn one unit every 0.5 s instead of all at once |
| `bool bSpawnAtAveragePlayerLevel` | `false` | |
| `TArray<FGametimeToLevel> LevelThresholdsByGametime` | — | creep level ramp |
| `EBarracudaRespawnBehaviorType RespawnType` | `AlwaysSpawn (0)` | replicated |
| `FMinionWave Wave` | — | the wave composition |
| `bool bShowTimer` | `true` | map-icon countdown |
| `bool bTimerRequiresVision` | `true` | jungle camps only show a timer if you have vision |
| `bool bSpawnLoopHasStarted` | `false` | replicated |
| `float64 NextSpawnTime` | `-1.0` | private; `-1` = "no timer" |
| `bool bHasLivingMinion` | `false` | |
| `TArray<TSubclassOf<UGameplayEffect@>> StartingEffects` | — | applied to every spawn |
| `TSubclassOf<UGameplayEffect@> BarracksDownEffect` | — | mega-creep buff |
| `TSubclassOf<AActor@> BarracksClass` | — | the barracks actor to look for |
| Components | `UCapsuleComponent CapsuleCollision` (h 145, r 50, profile `Trigger`), `ULokiTeamComponent`, `UBarracudaLaneComponent`, `UMapIconComponent`, `UVisibilityReceiver`, plus `UAkAudioEvent SpawnAudioEvent` and `FGameplayTag SpawnPilotVO` | |
| Replication | `bReplicates`, `bAlwaysRelevant`, `DORM_Awake`, `LokiReplicationStrategy.CustomReplicationStrategy = true`, `bDistanceBased = false` | |

### 5.2 Arming the loop — `AuthTryEnablingSpawnLoop()`

```
if (bSpawnLoopHasStarted) return;
if (GameState == null) return;
if (GameState.GetCurrentPhase() != ERoundPhase::EGP_Combat /*7*/) return;
if (GetCurrentBarracudaPhaseType() < MinimumBarracudaPhaseType) return;
bSpawnLoopHasStarted = true;
SpawnLoopStartTime   = ServerTime;
if (IsClockBasedSpawning())  AuthSetNextSpawnTime(SpawnLoopStartTime + InitialSpawnDelay);
else                         AuthCheckDayNightSpawn();
GrantTimerToAllTeams();
```

Called from `LokiBeginPlay`, from `OnRoundPhaseChanged`, and from
`FGameEvent_BarracudaPhaseChanged`. `IsClockBasedSpawning()` is
`RespawnType != AliveAtNight && RespawnType != AliveDuringDay`.

### 5.3 The spawn tick

```
Tick (server):
  if (!IsSpawningAllowed()) return;
  AuthCleanMinionReferences();          // drop dead refs; clear bHasLivingMinion if empty
  AuthTryUpdatingNextSpawnTime();       // StartRespawnTimerAfterDeath: arm ServerTime+SpawnPeriod once empty
  if (AuthShouldSpawnWave()) {
      if (RespawnType == ReplaceSpawns) AuthCleanupMinions();
      AuthSpawnWave();
      if (RespawnType == StartRespawnTimerAfterDeath) AuthSetNextSpawnTime(-1.0);
      else                                            AuthSetNextSpawnTime(NextSpawnTime + SpawnPeriod);
  }

IsSpawningAllowed():
  bSpawnLoopHasStarted
  && GameState.GetCurrentPhase() == EGP_Combat
  && !Loki::HasAnyMatchingGameplayTags(this, GameStateComponent.DisabledSpawnerTypes)

AuthShouldSpawnWave():
  HasNextRespawnTime()               // NextSpawnTime >= 0
  && ServerTime >= NextSpawnTime
  && !(RespawnType == SkipSpawnWhenOldExists && !MinionInstances.IsEmpty())
```

`AuthCheckDayNightSpawn()` handles the two non-clock modes: `AliveAtNight` spawns
when `GameState.DayNightState == LDNS_Night (1)` and calls `AuthCleanupMinions()`
otherwise; `AliveDuringDay` mirrors it on `LDNS_Day (0)`.

### 5.4 Spawning a wave

`AuthSpawnWave()` (non-staggered): for each `FMinionWaveEntry` with a non-null
class and `Count > 0`, spawn `Count` deferred actors at the spawner's location;
for each spawn — if the spawner has a lane index, get-or-**create** a
`UBarracudaLaneComponent` on the creep and copy the lane index; set the team;
`FinishSpawningActor`; apply every `StartingEffects` entry through
`ULokiAbilitySystemComponent::ApplyGameplayEffectToSelf`; set the team **again**;
`SetMinionLevel`; push into `MinionInstances`; set `bHasLivingMinion = true`.
Finally, if anything spawned, `PlaySpawnAudioEvent()` (Wwise event + pilot VO).

> Two real bugs are visible in the shipped bytecode and I am reporting them as
> found: (a) the `StartingEffects` loop is indexed by the *outer* per-unit counter
> `v27` while iterating `v49` (`ApplyGameplayEffectToSelf(this.StartingEffects[v27], …)`
> at `AuthSpawnWave`), so a spawner with >1 starting effect applies the wrong
> element; (b) the same loop in `StaggerSpawn` is correct (`StartingEffects[v25]`).

`BeginStaggerSpawn()` flattens the wave into `WaveBuffer` (honouring each entry's
`MinimumMatchTime` against `ServerTime`), zeroes `CurrentWaveBufferIndex`, and
calls `StaggerSpawn()`, which spawns one unit, increments the index and
re-arms itself with `System::SetTimer(this, n"StaggerSpawn", 0.5, …)`.

`StaggerSpawn` additionally implements **barracks / mega-creeps**: if both
`BarracksDownEffect` and `BarracksClass` are set, it scans all actors of
`BarracksClass`, looks for one whose `UBarracudaLaneComponent.LaneIndex` matches
the spawner's, and if **none is found** applies `BarracksDownEffect` to the
spawned creep. Destroy a lane's barracks → that lane's creeps get buffed. Classic.

### 5.5 Creep levelling — `SetMinionLevel(Minion)`

```
if (bSpawnAtAveragePlayerLevel) {
    sum = 0; n = 0;
    for (team = 0; team <= 1; team++)                         // hard-coded 2 teams
        foreach ps in GetPlayerStatesOnTeam(team) { sum += ps.GetPlayerLevel(); n++; }
    Minion.AuthGrantLevel( Max(1, RoundToInt(sum / n)) );
} else {
    elapsed = GameState.GetServerWorldTimeSeconds() - GameState.GameStartWorldTime;
    best = -1;
    foreach t in LevelThresholdsByGametime
        if (elapsed > t.Gametime && t.Level > best) best = t.Level;
    if (best > 0) Minion.AuthGrantLevel(best);
}
```

`for (team = 0; team <= 1; …)` is the clearest single proof in the whole corpus
that **Barracuda is exactly two teams.**

### 5.6 Client-side spawn timers

The server calls `GrantTimerToTeam(teamIndex)` → `ABarracudaTeamState_TeamOnly
::SetSpawnerSpawnTime(this, NextSpawnTime)`, which multicasts
`NetMulticastSpawnerNextSpawnTime` into a per-team
`TMap<ABarracudaMinionSpawner@, float64> SpawnerToSpawnTime`. Because
`ALokiTeamState_TeamOnly` is only replicated to its own team, **each team sees only
the camp timers it has earned.** `bTimerRequiresVision` routes the grant through
`UVisibilityReceiver.OnVisibilityEvaluated → HandleVisibilityEvaluated`, which
grants the timer only to teams that currently have vision of the camp. The client
reads it back in `ClientGetMapIconState(out bShowLivingIcon, out SecondsRemaining)`,
which special-cases the two day/night respawn types by returning
`GameStateComponent.SecondsUntilNextDayNightSwap()` instead of a spawn clock.

That is a jungle-timer HUD, fully implemented, vision-gated, and per-team. It is
the single most "shipped product" detail in the mode.

---

## 6. Targeting — creeps, jungle, towers

### 6.1 Base: `UBarracudaMinionTargetingComponent` (abstract)

```
ALokiCharacter@ HighPriorityEnemyCharacter;
AActor@         CurrentTargetEnemy;
float64         ReleaseHighPriorityEnemyTime = -1.0;
float64         HighPriorityEnemyMemory      =  5.0;
__InitDefaults: bExcludeFromClient = true;  HighPriorityEnemyCharacter = nullptr;
```

`NotifyEnemyHeroHitAlliedHero(EnemyCharacter)` — if the enemy is already on the
minion's enemy list **and** (no high-priority target, or it is that same enemy),
set `ReleaseHighPriorityEnemyTime = ServerTime + HighPriorityEnemyMemory (5 s)`
and latch `HighPriorityEnemyCharacter = EnemyCharacter`
**[corrected from disasm — the lifter printed the `REFCPY` operands reversed]**.

`UpdateTargetEnemy_Implementation()` (override of the native
`ULokiMinionTargetingComponent` hook) just calls the subclass's
`UpdateCurrentTargetEnemy()` and returns `CurrentTargetEnemy`.
`IsActorInEnemyList()` walks `ALokiMinionCharacter::GetEnemyList()`
(`TArray<FMinionEnemyListEntry>`). `DrawTargetingDebug()` draws a red line to the
target clamped to `AggroRange`.

### 6.2 Lane creeps — `UBarracudaLaneCreepTargetingComponent`

`UpdateCurrentTargetEnemy_Implementation` (verified opcode-by-opcode at cache
offset `0x14957`):

```
owner = cast<ALokiMinionCharacter>(GetOwner());
if (!owner) { CurrentTargetEnemy = nullptr; return; }

// aggro latch: keep the hero who hit an ally, for 5 s
if (IsAlive(HighPriorityEnemyCharacter) && ServerTime < ReleaseHighPriorityEnemyTime) {
    CurrentTargetEnemy = HighPriorityEnemyCharacter; return;
}
HighPriorityEnemyCharacter = nullptr;
CurrentTargetEnemy         = nullptr;
loc = owner.GetActorLocation();

CurrentTargetEnemy = owner.GetClosestEnemyOnList(loc, ELokiMinionEnemyFilter::Minion  /*5*/, true,  false);
if (CurrentTargetEnemy) return;
CurrentTargetEnemy = owner.GetClosestEnemyOnList(loc, ELokiMinionEnemyFilter::Destructible /*6*/, true, false);
if (CurrentTargetEnemy) return;
CurrentTargetEnemy = owner.GetClosestEnemyOnList(loc, ELokiMinionEnemyFilter::Hero   /*4*/, true,  false);
```

**Creeps > structures > heroes.** Textbook lane-creep priority.

### 6.3 Jungle creeps — `UBarracudaJungleCreepTargetingComponent`

Identical latch, but the fallback chain does **not** early-out between
`Destructible` and `Hero` (both assignments run; the last non-null wins), and the
two bool arguments differ per call. Same three filters in the same order.

### 6.4 Towers — `UBarracudaTowerTargetingComponent`

```
if (IsAlive(HighPriorityEnemyCharacter) && IsActorInEnemyList(HighPriorityEnemyCharacter)) {
    CurrentTargetEnemy = HighPriorityEnemyCharacter; return;   // sticky
}
HighPriorityEnemyCharacter = nullptr;
if (IsAlive(CurrentTargetEnemy) && IsActorInEnemyList(CurrentTargetEnemy)) return;  // keep current
CurrentTargetEnemy = FindClosestEnemyByClass(owner, ALokiMinionCharacter::StaticClass());
if (CurrentTargetEnemy) return;
CurrentTargetEnemy = FindClosestEnemyByClass(owner, ALokiHeroCharacter::StaticClass());
if (CurrentTargetEnemy) return;
CurrentTargetEnemy = nullptr;
```

with `FindClosestEnemyByClass` doing a `DistSquared2D` min-scan over the enemy
list filtered by `IsA(ClassFilter)`. **Towers prefer minions over heroes and never
switch off a valid target** — i.e. tower aggro only changes when the current
target dies or leaves range, exactly the DOTA/LoL rule. The "hero hit an ally"
latch is the tower-dives-you rule; `UBarracudaRallyMinionsComponent` (§6.5) is
what feeds it.

### 6.5 `UBarracudaRallyMinionsComponent` (on the game mode)

```
float64 RallyAggroRange = 2000.0;
LokiBeginPlay: register for FGameEvent_OnDamaged_Character → OnCharacterDamaged
OnCharacterDamaged(Event, ContextCharacter):
    victim   = cast<ALokiHeroCharacter>(ContextCharacter);
    attacker = cast<ALokiHeroCharacter>(Event.DamageStatistic.SourceCharacter);
    if (victim && attacker && LokiTeam::IsEnemyTeam(victim, attacker))
        RallyAlliedMinionsForHelp(victim, attacker);

RallyAlliedMinionsForHelp(Victim, Attacker):
    foreach c in TeamStateOf(Victim).GetCachedCharacters():
        m = cast<ALokiMinionCharacter>(c);  if (!m) continue;
        p = m.GetActorLocation();
        if (DistSq2D(Victim, p)   > RallyAggroRange²) continue;
        if (DistSq2D(Attacker, p) > RallyAggroRange²) continue;
        UBarracudaMinionTargetingComponent::Get(c)?.NotifyEnemyHeroHitAlliedHero(Attacker);
```

Hero-on-hero damage rallies every friendly minion **and tower** within 2000 uu of
*both* participants onto the attacker, for 5 s. This is the mode's tower-dive
punishment, and it is complete.

### 6.6 Jungle leash — `UBarracudaJungleCreepComponent`

```
float64 StuckDetectionTime  = 30.0;
float64 UnstuckTeleportTime;         // absolute deadline
Tick (server):
  m = cast<ALokiMinionCharacter>(GetOwner());
  if (m.HasBlackboardTargetEnemy() || Dist2D(m.location, m.GetSpawnLocation()) < 500.0) {
      UnstuckTeleportTime = ServerTime + StuckDetectionTime;    // reset the deadline
      return;
  }
  if (ServerTime > UnstuckTeleportTime)
      m.Teleport(m.GetSpawnLocation(), m.GetActorRotation());   // hard reset the camp
```

Camp leash: 500 uu radius, 30 s grace, then teleport home.

---

## 7. Economy — gold, XP, bounties, respawn

### 7.1 `ABarracudaGameMode` economy properties

| Property | Default | Meaning |
|---|---|---|
| `float32 GoldLossOnDeath` | `0.2` | fraction of carried gold dropped |
| `TArray<int> GoldBountyPerCurrentStreak` | — | shutdown gold, indexed by victim's streak |
| `TArray<float32> MinionSplitXPBonuses` | — | XP multiplier bonus for sharing a kill |
| `TArray<float32> MercyHeroKillXPCoefficients` | — | XP reduction when you outlevel the victim |
| `float32 UnderdogHeroKillXPBonusPerLevel` | `0.25` | XP bonus when you underlevel the victim |
| `float64 KnockXPCooldownTime` | `30.0` | per-victim anti-double-pay window |
| `TMap<ALokiPlayerState@, float64> LastKnockedTimeTable` | — | the cooldown table |
| `TArray<TSubclassOf<UGameplayEffect@>> DragonRewards` | — | stacking dragon buffs |
| `int NumDragonsKilled` | `0` | |
| `FGameplayTag DragonKilledPilotVO`, `MomentumBossKilledPilotVO`, `TSubclassOf<UGameplayEffect@> MomentumBuffEffect` | — | |

### 7.2 Hero kills — `OnPlayerKilled(FPlayerKillEventData)`

Verified instruction-by-instruction at cache offset `0x1c891` (725 dwords).
**Two decompiler mis-renders corrected here** (the `TMap::opIndex` read at
`+0x098` and the two `TArray::opIndex` reads at `+0x0858` / `+0x09E4` were printed
as the wrong member names):

```
if (KillData.EventResult != ELivingState::ELivingStateKnocked /*2*/) return;   // fires on KNOCK
if (LastKnockedTimeTable.Contains(Victim)
    && ServerTime < LastKnockedTimeTable[Victim] + KnockXPCooldownTime /*30s*/) return;
LastKnockedTimeTable.Add(Victim, ServerTime);

victimHero  = Victim.GetLokiCharacter() as ALokiHeroCharacter;
victimLevel = RoundToInt(victimHero.GetLevel());
killerTeam  = TeamOf(KillData.Killer);

// 1. victim drops 20 % of carried gold
droppedGold = RoundToInt(Victim.GetWalletCurrencyAmount("Gold") * GoldLossOnDeath);
Victim.ConsumeWalletCurrency("Gold", droppedGold);

// 2. participant set
nearby       = GetPlayerStatesForRewardsInRadius(victimLoc, 2500.0, killerTeam, KillData.Killer);
creditors    = KillData.AssistPlayerStats + Killer;
participants = unique(nearby ∪ creditors);

foreach P in participants {
    gold = 0; xp = 0;
    if (creditors.Contains(P))
        gold += droppedGold / participants.Num();                       // integer division
    if (P == Killer && Victim.GetCurrentKillStreak() > 0)
        gold += GoldBountyPerCurrentStreak[ Min(Num-1, Victim.GetCurrentKillStreak()) ];  // shutdown

    if (participants.Contains(P)) {
        base  = victimHero.GetExperience() * 0.2 + 75.0;
        coeff = 1.0;
        levelDiff = P.GetPlayerLevel() - victimHero.GetCharacterLevel();
        if (levelDiff > 0 && MercyHeroKillXPCoefficients.Num() > 0)
            coeff = MercyHeroKillXPCoefficients[ Min(Num-1, levelDiff) ];       // you're ahead → less
        else if (levelDiff <= -2)
            coeff = 1.0 + UnderdogHeroKillXPBonusPerLevel * Abs(levelDiff);     // you're behind → more

        streakBonus = (Victim.GetCurrentKillStreak() > 2)
                    ? victimLevel * Victim.GetCurrentKillStreak() * 15 : 0;
        xp = (base + streakBonus) * coeff / participants.Num();
        if (participants.Num() > 1)
            xp *= 1.0 + MinionSplitXPBonuses[ Min(Num-1, participants.Num()) ]; // share-back
        xp = RoundToInt(xp);
    }

    P.GrantWalletCurrency("Gold", gold, ECurrencyGrantReason::DroppedByEnemy);
    P.GetLokiCharacter()?.AuthGrantExperience(xp, true);
    if (gold > 0 || xp > 0) OnBountyGivenToPlayer(victimLoc, P, gold, reason, xp);  // BP VFX hook
}
```

The `EventResult == Knocked` gate is a genuinely SUPERVIVE-specific design
decision: because SUPERVIVE knocks before it kills, the bounty pays on the
**knock**, with a 30 s per-victim cooldown so a repeatedly-knocked player can't be
farmed.

`GetPlayerStatesForRewardsInRadius(Location, Radius, TargetTeam, Killer)` does a
`System::SphereOverlapActors` for `ALokiHeroCharacter`, keeps actors whose team
matches, and maps them to player states. **The 2500 uu here and the 1500 uu in
§7.3 are hard-coded literals in bytecode, not properties** — no designer knob.

### 7.3 Minion / creep kills — `OnActorKilled_BP(VictimActor, Killer)`

```
rewardComp = UBarracudaMinionRewardComponent::Get(VictimActor);
if (rewardComp) {
    goldBounty = rewardComp.GetGoldBounty(Killer);
    xpBounty   = rewardComp.GetXPBounty(Killer);
    team       = TeamOf(Killer.GetPawn());
    share      = GetPlayerStatesForRewardsInRadius(victimLoc, 1500.0, team, Killer);
    n          = share.Num();
    foreach P in share {
        gold = 0;
        if (P == KillerPlayerState) {                       // LAST HIT gets the gold
            gold = goldBounty;
            if (VictimActor.IsA(ALokiMinionCharacter))
                if (ASC(P).HasTagAttribute(Attribute.MinionGoldMultiplier))
                    gold = FloorToInt(ASC(P).GetTagAttributeMin(Attribute.MinionGoldMultiplier) * gold);
            P.GrantWalletCurrency("Gold", gold, ECurrencyGrantReason::MonsterKilled);
        }
        xp = RoundToInt(xpBounty * (1.0 / n));              // XP is SHARED by proximity
        if (n > 1) xp += RoundToInt(xp * (1.0 + MinionSplitXPBonuses[Min(Num-1, n)]));
        P.GetLokiCharacter()?.AuthGrantExperience(xp, true);
        if (gold > 0 || xp > 0) OnBountyGivenToPlayer(victimLoc, P, gold, reason, xp);
    }
}
if (KillerPlayerState && Loki::HasMatchingGameplayTag(VictimActor, Barracuda.Minion.GrantsDragonBuff))
    OnDragonKilled(KillerPlayerState);
if (KillerPlayerState && Loki::HasMatchingGameplayTag(VictimActor, Barracuda.Minion.GrantsMomentumBuff))
    OnMomentumBossKilled(KillerPlayerState);
```

**Gold is last-hit-only; XP is shared within 1500 uu.** That is the canonical MOBA
laning rule, implemented exactly.

`UBarracudaMinionRewardComponent` is the per-creep reward carrier:

```
EBarracudaMinionGoldRewardMethod GoldRewardMethod = LastHitterOnly (0);
bool bGrantLoot = true;
int  LastHitGoldBonus = 0;
void DisableAllRewards()          { bGrantLoot = false; }     // called when a wave is culled
int  GetGoldBounty(Controller)    { m.GetRewardsForLevel(RoundToInt(m.GetLevel()), out FMinionRewards r); return r.Gold; }
int  GetXPBounty(Controller)      { …same… return r.XP; }
int  GetLastHitGoldBounty(Ctrl)   { …same… return r.Gold; }   // identical to GetGoldBounty; LastHitGoldBonus is UNUSED
```

`FMinionRewards { int XP; int Gold; TArray<TSubclassOf<ULokiLootTable>> Loot; }` is
native, filled by `ALokiMinionCharacter::GetRewardsForLevel(int, out)`. Note that
neither `GoldRewardMethod` nor `LastHitGoldBonus` is read anywhere in the script
layer — `SplitBetweenLastHitterTeam` is declared but **not implemented**. That is
the clearest piece of *unfinished* work in the mode.

### 7.4 Objective buffs

```
OnDragonKilled(KillerPlayerState):
    gsc.NumDragonsKilled++;                                  // replicated, RepNotify → OnDragonKillsUpdated
    idx = Min(gsc.NumDragonsKilled, DragonRewards.Num() - 1);
    if (idx >= 0) ApplyEffectToTeam(KillerPlayerState.GetTeamIndex_BP(), DragonRewards[idx]);
    if (DragonKilledPilotVO.IsValid()) gsc.AuthPlayPilotVOForAll(DragonKilledPilotVO);

OnMomentumBossKilled(KillerPlayerState):
    if (MomentumBossKilledPilotVO.IsValid()) gsc.AuthPlayPilotVOForAll(MomentumBossKilledPilotVO);
    // NOTE: MomentumBuffEffect is declared but NEVER applied in script — BP-side only.

ApplyEffectToTeam(TeamIndex, EffectClass):
    foreach ps in LokiGameplay::GetPlayerStatesOnTeam(TeamIndex)
        ASC(ps).ApplyGameplayEffectToSelf(EffectClass, 0, ASC(ps).MakeEffectContext(), false);
```

Stacking dragon stacks that buff the whole team, indexed by dragon count. The
shipped assets confirm the pieces: `Core/DragonBuffs/` (6 files),
`MomentumBuff/` (8 files incl. `GE_Barracuda_MomentumBuff_Grant`),
`Core/GankBuffs/` (3 files), `Minions/Baron/` (multi-phase armoured boss with
orb-fire and wide-laser abilities), `Minions/Megaboar/`, `Minions/Bomber/`.
**[asset names only]**

### 7.5 Team kill score

`UpdateTeamKills()` sums `GetKills()` over `GetPlayerStatesOnTeam(0)` and
`(1)` into a replicated `TArray<int> TeamKillScores` (RepNotify →
`FOnTeamKillsUpdated.Broadcast`). Again hard-coded to teams 0 and 1.

### 7.6 Respawn — `UBarracudaPlayerSpawnerComponent`

```
TArray<float64> RespawnTimePerLevel;                  // the death-timer curve
float64 MatchTimeRespawnCeiling = 1800.0;             // 30 minutes
float64 MatchRespawnTimeFactor  = 0.2;
__InitDefaults: bReplicates=false; bExcludeFromClient=true; ComponentTickEnabled=true;
```

`CalculateDeathTimer(PlayerState)` (verified at cache offset `0x20f34`):

```
if (RespawnTimePerLevel.Num() > 0) {
    base = RespawnTimePerLevel[ Min(Num-1, PlayerState.GetPlayerLevel()) ];
    t    = GetCurrentBarracudaPhaseTime() / MatchTimeRespawnCeiling;
    return base * (1.0 + Math::Lerp(t, 0.0, MatchRespawnTimeFactor));
} else {
    return PlayerState.GetPlayerLevel() * 5;          // fallback: 5 s per level
}
```

⚠ The `Lerp` argument order is what the bytecode pushes (params in reverse push
order — verified against `GetClosestEnemyOnList`, whose signature is known). With
`FMath::Lerp(A,B,Alpha) = A + Alpha*(B-A)` that evaluates to `t*(1-0.2) = 0.8·t`,
so the timer grows to **1.8×** at the 30-minute ceiling. It reads like the author
meant `Lerp(0, MatchRespawnTimeFactor, t)` (→ `1 + 0.2·t`, a 1.2× ceiling). I am
reporting the compiled behaviour and flagging the discrepancy rather than
"fixing" it.

`TryRespawningPlayers()` (per tick, server):

```
if (GameState.GetCurrentPhase() != EGP_Combat) return;
gm = cast<ABarracudaGameMode>(GetOwner());
foreach ps in GameState.GetLokiPlayerStates() {
    c = UBarracudaPlayerStateComponent::Get(ps);   if (!c) continue;
    if (ps.GetLokiCharacter() && !it.IsDead()) { c.SetNextRespawnTime(-1.0); continue; }
    if (c.HasNextRespawnTime() && c.GetNextRespawnTime() < ServerTime) {
        xf = FTransform();
        struct = GameStateComponent.GetRespawnStructure(TeamOf(ps));   // §8.1
        if (struct) xf.SetLocation(struct.GetActorLocation());
        c.ClearNextRespawnTime();
        gm.SpawnPlayer(ps, xf, nullptr, false);
    } else if (!c.HasNextRespawnTime()) {
        c.SetNextRespawnTime(ServerTime + CalculateDeathTimer(ps));
    }
}
```

`UBarracudaPlayerStateComponent` replicates the private `InternalNextRespawnTime`
(`-1` sentinel) with `OnRep_NextRespawnTime`, exposes
`GetRespawnTimeRemaining()` / `GetRespawnTimeRemainingForDisplay()` (rounded, min 1)
for the HUD, fires `FNextRespawnTimeChanged` and broadcasts
`FGameEvent_BarracudaRespawnTimeChanged_PlayerState` on the global router.

---

## 8. Structures, bases and the shop

### 8.1 `UBarracudaStructureComponent`

```
bool bAttackable      = false;
bool bRespawnLocation = false;
LokiBeginPlay: GameStateComponent.Structures.Add(GetOwner());
LokiEndPlay:   GameStateComponent.Structures.Remove(GetOwner());
```

Anything with this component registers itself in the game state's structure set.
`UBarracudaGameStateComponent::GetRespawnStructure(TeamIndex)`
(`BlueprintAuthorityOnly`) scans that set for a structure with
`bRespawnLocation == true` on the matching team and returns it — **that is the
fountain**, and it is what `TryRespawningPlayers` teleports you to.

### 8.2 The item shop — `ABarracudaShop`

```
UCLASS(Blueprintable) class ABarracudaShop : AActor
  float64 SellValueCoefficient = 0.9;                               // sell for 90 %
  TArray<TSubclassOf<ULokiLootTableFull@>> ItemLootTables;          // the catalogue
  TMap<TSubclassOf<ALokiBaseItem@>, UBarracudaShopItemGraphNode@> ItemGraphNodes;
  FString  ClientNameFilterString;   TArray<FGameplayTag> ClientTagFilters;
  TSubclassOf<ALokiBaseItem@> ClientCurrentFocus;
  TArray<TSubclassOf<AActor@>> AllItems;   bool bDebugLogGraph = true;
  __InitDefaults: bAlwaysRelevant, bReplicates, CustomReplicationStrategy, !bDistanceBased

class UBarracudaShopItemGraphNode : UObject {
  TSubclassOf<ALokiBaseItem@> Item;   int RecipeCost;   int TotalCost;
  TArray<UBarracudaShopItemGraphNode@> Inputs;          // what it's built FROM
  TSet<UBarracudaShopItemGraphNode@>   Outputs;         // what it builds INTO
  bool bHasTotalCost;
}
struct FBarracudaShopPurchasePlan { int Gold; TSet<ALokiBaseItem@> ItemsToConsume; }
```

It is spawned lazily by the game state:

```
UBarracudaGameStateComponent::LokiBeginPlay (server):
    if (!Shop && ShopClass != nullptr) { GetOwner().FlushNetDormancy(); Shop = SpawnActor(ShopClass, …); }
    TeamKillScores.Add(0); TeamKillScores.Add(0);       // again: exactly two teams
    GameState.OnPlayerKilled.AddUFunction(this, n"OnPlayerKilled");
__InitDefaults: ShopClass = ABarracudaShop::StaticClass();  bReplicates = true;
```

**Graph construction** (`BuildGraph`, run in `LokiBeginPlay` on both server and
client): for every `ULokiLootTableFull` in `ItemLootTables`, walk
`GuaranteedItems`, resolve each `ItemClassToSpawn` soft class with
`System::LoadClassAsset_Blocking`, cast the CDO to `ALokiBaseItem`, and
`GetOrCreateItemGraphNode(cls)`. For each node, iterate the item's
`ShopRecipe.ComponentItems` (native `FLokiItemRecipe`) and wire
`node.Inputs += child; child.Outputs += node`.

**Cost roll-up** (`CalculateItemTotalCost`, recursive, memoised on `bHasTotalCost`):

```
Node.TotalCost += Node.RecipeCost;                 // RecipeCost = CDO.GetGoldValue()
foreach in in Node.Inputs { CalculateItemTotalCost(in); Node.TotalCost += in.TotalCost; }
Node.bHasTotalCost = true;
```

That is a component-tree item build system: leaf items have a gold value, combined
items add a recipe cost on top of the sum of their parts. `GetItemSellValue` =
`FloorToInt(TotalCost * 0.9)`. `GetIncrementalCost` defers to the native
`ALokiBaseItem::GetRecipeCostForLocalPlayerBP` (what you still owe given what you
already carry).

**Buying** (`AuthBuyItem`, `BlueprintAuthorityOnly`):

```
plan.Gold = ALokiBaseItem::GetRecipeCostForInventory(inv, ItemClass, out plan.ItemsToConsume);
if (PlayerState.GetWalletGold() >= plan.Gold) ExecutePurchasePlan(plan, PlayerState, ItemClass);

ExecutePurchasePlan:
    slot = ItemClass.CDO.GetSlotName();
    if (inv.GetEmptySlotsByName(slot) == 0) {
        // no free slot: only proceed if a consumed component frees one
        if (count of plan.ItemsToConsume with matching slot == 0) return;
    } else {
        PlayerState.ConsumeWalletCurrency("Gold", plan.Gold);
        foreach it in plan.ItemsToConsume  inv.TryRemoveFromInventory(it, Destroyed);
        newItem = SpawnActor(ItemClass, …);
        inv.TryAddToInventory(newItem, ELokiAddToInventoryReason::Created, NAME_None, -1, true, false);
    }
```

> Reported as found: the slot check inverts. When there **is** no free slot the
> code only validates and then falls out; when there **is** a free slot it takes
> the `else` and buys. The "free a slot by consuming a component" path therefore
> never actually completes the purchase.

**Selling** (`AuthSellItem`): validates the item is in *this* player's inventory,
removes + destroys it, and refunds `GetItemSellValue(cls)` with
`ECurrencyGrantReason::Refund`.

### 8.3 Shop network path and the in-base gate

`UBarracudaShopPlayerControllerComponent` (on the player controller):

```
LokiBeginPlay (client): register on the *UI* event router for
    FUIEvent_Barracuda_Shop_BuyItem  → ClientOnBuyItem  → ServerBuyItem(RPC)
    FUIEvent_Barracuda_Shop_SellItem → ClientOnSellItem → ServerSellItem(RPC)

ServerBuyItem_Implementation  [NetServer]:
    inBase = ASC(ps).HasMatchingGameplayTag(GameMode.Barracuda.InBase);
    isDead = ASC(ps).HasMatchingGameplayTag(State.Dead);
    if (isDead) Shop.AuthBuyItem(ps, ItemToBuy);      // dead players may buy
    else if (!inBase) return;                          // living players must be in base
ServerSellItem_Implementation [NetServer]:
    if (!inBase) return;  Shop.AuthSellItem(ps, Item);
```

**Buy/sell requires the `GameMode.Barracuda.InBase` gameplay tag** — you shop at
the fountain — and dead players are allowed to buy (so your gold isn't stranded
during a long death timer). That is a deliberate, shipped design rule.

> Reported as found: the `ServerBuyItem` branch structure is inverted relative to
> the obvious intent — it buys on `isDead` and merely early-outs on `!inBase`,
> so a **living player in base never reaches `AuthBuyItem`**.

### 8.4 Shop UI (4 widget classes, all Angelscript)

- `UBarracudaShopItemListWidget` — on `Construct`, registers for
  `FUIEvent_Barracuda_Shop_ToggleVisibility` and `…FilterUpdated`. `UpdateVisuals`
  clears the container, walks `Shop.ItemGraphNodes`, keeps nodes passing
  `DoesItemPassFilter`, sorts by `TotalCost` **descending** via an O(n²)
  selection sort (`SortItemNodesByTotalCost` — repeatedly picks the max and
  `RemoveAtSwap`s it), then `AddItemToContainer` per node and
  `EventFinishedAddingItems()`. The three container ops are `NoOp` BlueprintEvents
  — the BP owns the actual panel.
  `DoesItemPassFilter(Shop, Node)`: text filter matches the item's
  `GetPlayerFacingName()` **or** any `ShopMetaData.MetaTags` entry
  (`ESearchCase::IgnoreCase`); then `Loki::HasAllMatchingGameplayTags(cdo,
  ClientTagFilters)`.
- `UBarracudaShopItemTreeWidget` — `RootNode` (`meta.BindWidget`) +
  `TSet<ALokiBaseItem@> ItemsToPotentiallyMarkAsOwned`. On `Construct` registers
  for `…FocusItem` and `FUIEvent_ItemEnteredOrExitedInventory`.
  `UpdateVisualsInternal` refills the owned set from the local player's inventory
  (`GetAllValidItems`) and calls `RootNode.SetItem(ItemClass)`.
- `UBarracudaShopItemTreeNodeWidget` — one recipe-tree node. Binds
  `ChildContainer`, `ItemName`, `OwnedIndicator`, `ShopItemWidget`.
  `UpdateRootNode` clears children and, for each entry of
  `CDO.ShopRecipe.ComponentItems`, calls the BlueprintEvent
  `CreateInputItemWidget(cls, previewInputCount, depth-1)` and adds it —
  **recursive recipe tree rendering**. Design-time preview knobs
  `DesignTimePrviewInputCount` *(sic)* `= 2`, `DesignTimePreviewDepthCount = 2`.
  `UpdateOwnership` marks a node owned by consuming one matching entry out of the
  tree's `ItemsToPotentiallyMarkAsOwned` set (so two copies of the same component
  light up two nodes, not one twice).
- `UBarracudaShopItemWidget` — `EBarracudaShopValueType ValueType
  {TotalCost, RecipeCost, SellValue, IncrementalCost}` drives `GetValue()` through a
  4-way jump table. `OnMouseButtonDown`: left click → broadcast
  `FUIEvent_Barracuda_Shop_FocusItem`; right click on a *class* entry → `…BuyItem`;
  right click on an *instance* (your own item) → `…SellItem`.
- `UBarraucdaShopFilterWidget` *(typo shipped in both file and class name)* —
  `TArray<FBarracudaShopTagFilter{ FText Label; FGameplayTag Tag; FGameplayTag
  RecommendedHeroTag; }>`. Data only; no logic in script.

### 8.5 What the shop is stocked with (shipped assets — **[name-only]**)

Nine loot tables under `GameModes/Barracuda/Shopkeepers/LootTables/`:
`LT_Barracuda_ShopWares_{StarterItems, Strength, Agility, Intelligence, Armor,
Movement, Equipment, Consumables, Special}`.

51 recipe folders under `GameModes/Barracuda/Items/BarracudaItem/` — the naming is
unmistakably DOTA-derived:

> `AGIMultiplier, AgiGiantSlayer, AgiMana, AgilityOmnivamp, AntiDashArmor,
> AntihealCaster, ArchmageStaff, Armor, ArmorDesolator, AttackSpeedAgi, BKB, Base,
> BattlemageItem, Bloodthirster, BonusHealthToHealing, CombatResourceStatBall,
> CritStick, DashCDRMinor, Early, FrozenBow, HealingAmp, HeartOfTarrasque,
> HoverWings, IntelligenceArmor, IntelligenceCDR, JumppadActive, JunglerAssist,
> KnightShield, LMBAmp_Medium, LMBRangeBonus, ManaAuraRing, ManaForHPItem,
> ManaHealthRegen, ManaStone, MercyArmor, Movement, PawnPiercer,
> PercentDamageWeapon, RecommendedLoadouts, Refresher, RingOfHealth, ShadowBlade,
> Sheen, StartingFarmEquipment, StrIntShield, Strength, SuperCritStick,
> SupportWardItem, TimeStopper, Ward, WeakToMagic`

Plus consumables/actives: `BP_ITEM_{Bandage_HQ, BlinkDagger, EtherealSmoke, Flash,
ManaPotion, ScanGrenade, ThornArmor}_Barracuda`, `BP_ITEM_Ward_Inventory`,
`BP_ITEM_Ward_Utility`, and `BP_ITEM_Equipment_*_Swordfish` variants.

**17 per-hero recommended builds** ship as
`BP_BarracudaLoadout_{Beebo, Bishop, Brall, Celeste, Crysta, Elluna, Felix, Ghost,
Jin, Kingpin, Myth, Oath, Saros, Shiv, Shrike, Void, Zeph}` (+ `_Base`), each an
`ALokiBarracudaLoadout` with Starting/Early/Mid/Late/Luxury/Consumable lists, and
`ALokiHeroCharacter` has a `BarracudaRecommendedLoadout` soft pointer to it.

---

## 9. Is it runnable? Honest assessment

### What ships (verified from the IoStore directory index — 726 Barracuda paths)

| Piece | Evidence |
|---|---|
| Game mode / game state | `Core/GameModes/Barracuda/BP_GameMode_Barracuda.uasset`, `BP_GameState_Barracuda.uasset` (+ `_Swordfish` variants), `BP_LokiGameMode_Dev_Barracuda_Code.uasset` |
| Player controller | `BP_BarracudaPlayerController.uasset` |
| Towers | `Minions/Towers/BP_LokiTower.uasset`, **`BP_LokiTower_Nexus.uasset`**, `BP_BARRACUDA_TowerProjectile`, `GE_TowerDamage`, `GIE_TowerHomingMissle`, `WBP_UI_Tower`, tower meshes in Fey and Tech variants |
| Lane creeps | `Minions/Lane/BP_Minion_Barracuda_{LaneBase, Melee, Backline, Backline_v2}`, single-shot ability + projectile + GE + cue + curve table |
| Jungle / bosses | `BP_Minion_Barracuda_{Jungle_Hard, SmallCamp}`, `Baron/BP_Minion_ArmoredBoss_Multiphase_Barracuda` (+ orb-fire, wide-laser, attack swapper), `Megaboar/BP_Charger_Boss_Barracuda`, `Bomber/BP_Minion_BomberBoss_Barracuda`, KaijuBrute + TownGuard anim sets |
| AI | `BT_LaneMinion_Barracuda`, `BT_JungleMinion_Barracuda`, 4 BT tasks, 2 decorators, 2 services |
| Waypoints | `BP_Barracuda_MinionWaypoint.uasset` |
| Shop | `Shop/BP_BarracudaShop.uasset`, 13 `WBP_UI_Barracuda_Shop_*` widgets (incl. `RecipeTree`, `RecipeTreeBranch`, `RecipeTreeNode`, `ItemBuildsInto`, `RecommendedItems`, `CurrentInventory`), 9 loot tables, `Struct_BarracudaItemtoCost` |
| Items | 51 recipe folders, ~10 active/consumable item BPs |
| Attributes | `CT_LokiBarracuda{Character, Item, Ability, GemaplaySystems}Attributes`, `CT_BarracudaDashScaling`, `GE_Barracuda_DynamicCharAttributes`, `GE_Barracuda_BaseModifiers`, 4 MMC classes |
| HUD | `WBP_UI_BarracudaCombatRoot`, `…Minimap`, `…AbilityStat`, `…KeyBindSettings`, `WBP_Barracuda_DragonStatus(Container)`, `WBP_UI_Playerboard_BarracudaHeader`, `WBP_UI_AIHealthBar_Barracuda`, `BPFL_UI_Barracuda` |
| Audio / VO | 6 tower SFX, 5 lane-creep SFX, 4 kaiju SFX, 2 item SFX, and **40 announcer VO events** under `vo_announcer_barracuda` including `…citadel_underattack`, `…match_start`, `…tower_destroy_ally`, `…tower_destroy_enemy`, `…tower_underatack` *(sic)* |
| Level art | `World/Architecture/Barracuda/{Favela_Kit (99 assets), Pillar, Walls, Attachments}`, `World/Ground/Barracuda/Cement`, `World/Skirts/Barracuda`, `World/Decals/Barracuda` (28), 8 `BPP_LI_BC_Favela_Building_*` packed level blueprints |
| Cheats | `ULokiPlayerCheats` (Angelscript) ships 5 Barracuda console commands (§9.2) |

### What is missing: **the map**

I parsed the directory index of all 17 `.utoc` containers (102 511 files) and
listed every `.umap`. There are 116 named maps and 7 184 world-partition cells.
**None of them is named Barracuda, and no `_Generated_` world-partition cell set
belongs to a Barracuda map.** The shipped map list is: SkylandsBreach, Skylands_WP,
Training, Bracket ×2, LVL_Lastman, Practice, Prismafalls, Domination ×2,
Beastfalls, BeastHaven, Battleships, Payload, Tutorial, Holdout, PrismaBank ×2,
GrindBallArena, TugOfWar ×3, Battlefield ×12 (no cells), Lobby/LobbyV2, Login,
ServerStandby, Workbench_Wall.

The two `LVL_Bracket_*` maps (255 and 239 world-partition cells) are the only
unexplained large levels, and `LVL_Battlefield_TG` is suggestive given the
Barracuda `TownGuard` asset family — but **I did not verify either**, and I am not
going to assert it. Reading a `.umap`'s actor list would settle it (see §11).

So: **the systems ship, the content ships, the map does not appear to.** Whether
Theorycraft stripped the level from the cook or the mode lived on a
server-side-only level, I can't tell from these files.

### 9.1 Would it run?

Mechanically, most of the mode is server-authoritative Angelscript that is already
loaded and registered every time the game boots (the script caches are read at
startup regardless of mode). The mode needs, at minimum:

1. A level containing: two `bRespawnLocation` structures, one
   `ABarracudaMinionSpawner` per creep camp/lane with a populated `FMinionWave`,
   a chain of `ABarracudaMinionWaypoint`s per lane wired `TowardTeam0/1`, towers,
   and a Nexus.
2. `BP_GameState_Barracuda` with a populated `BarracudaPhases` array (else
   `AuthMoveToNextBarracudaPhase` never advances past `Invalid`, and every
   spawner's `MinimumBarracudaPhaseType` gate holds).
3. The round phase to reach `ERoundPhase::EGP_Combat (7)` — the same gate the
   project already drives for the tutorial.

Points 1 and 3 are exactly the walls the project already knows. **Point 1 is the
hard one and it is a level-authoring problem, not a reverse-engineering one** —
and §9.2 says you may not even need a hand-built level to see the systems move.

### 9.2 The cheat surface (from `PlayerController/LokiPlayerCheats.as` — decompiled)

`ULokiPlayerCheats` ships five Barracuda console commands, all
`NetServer` BlueprintEvents, all callable through the project's existing
native-call primitive:

| Command | Implementation |
|---|---|
| `ConsoleCommandCheatBarracudaNextPhase` | `GetBarracudaGameStateComponent().AuthMoveToNextBarracudaPhase()` |
| `ConsoleCommandCheatBarracudaToggleJungleSpawners` | toggles `Static.Barracuda.Spawner.Neutral` in `DisabledSpawnerTypes` |
| `ConsoleCommandCheatBarracudaToggleLaneSpawners` | toggles `Static.Barracuda.Spawner.Creep` in `DisabledSpawnerTypes` |
| `ConsoleCommandCheatBarracudaToggleDayNightCycle` | flips `bDayNightTransitionEnabled` |
| `ConsoleCommandCheatBarracudaAdvanceDayNightCycle` | `NextDayNightSwapTime = GameMode.GetMatchTime()` (forces an immediate swap) |

The two spawner tags also tell us the taxonomy the level used:
**`Static.Barracuda.Spawner.Creep`** (lanes) vs
**`Static.Barracuda.Spawner.Neutral`** (jungle).

---

## 10. Should this be the revival target instead of BR?

Honestly: **it is the second-best target, and it is a much better target than the
drop-in BR sequence for demonstrating *gameplay*.** The argument, with the
caveats:

**For Barracuda**
- Every server-authoritative rule is *readable source* now, not native code
  behind anti-tamper. Waves, aggro, gold, XP, respawn, shop — all decompiled above.
- It needs **no drop-plane, no drop-pod, no DropPhase**. The two walls that have
  eaten multiple sessions (`SpawnPlane` descent faults on absent level markers,
  the "DROP IN GEAR UP LOADING" overlay) are simply not on this path. Barracuda
  spawns you at a structure via `ABarracudaGameMode::SpawnPlayer(ps, transform,
  nullptr, false)` — a plain transform spawn.
- It is **listen-server-friendly in exactly the way the project already knows how
  to exploit**: everything is gated on `Loki::LokiIsServer` + `EGP_Combat`, which
  is the same gate the S91–S93 tutorial force-open already drives.
- The economy/AI loop is self-sustaining: spawners tick, creeps path, towers
  shoot, gold and XP flow — with no backend involvement at all.
- 726 content assets ship. Nothing has to be authored except the level.

**Against Barracuda**
- **The map is the blocker, and it is a bigger blocker than it looks.** Lanes are
  not procedural: they are hand-placed `ABarracudaMinionWaypoint` chains with
  explicit `TowardTeam0/TowardTeam1` links, hand-placed spawners with authored
  `FMinionWave` compositions and `LevelThresholdsByGametime` curves, hand-placed
  towers, barracks and fountains. Recreating that means spawning and wiring dozens
  of actors at runtime — the project *can* do this (S90/S93 proved arbitrary
  level-actor spawn + `AddComponentByClass` work), but it is a genuine authoring
  job, not a one-shim fix.
- `BarracudaPhases`, `RespawnTimePerLevel`, `GoldBountyPerCurrentStreak`,
  `MercyHeroKillXPCoefficients`, `MinionSplitXPBonuses`, `DragonRewards` and every
  `FMinionWave` are all `EditableOnDefaults` arrays that live in **Blueprint CDOs
  and level instances**, not in script. §11 explains why I couldn't read them.
- The win condition and tower-destruction bookkeeping are in Blueprint bytecode
  (`ShouldGameEnd`, `OnAuthTowerDestroyed`, `GetDeadTowers`), which is a separate
  decompile.
- Some of it is genuinely unfinished (`SplitBetweenLastHitterTeam` unimplemented,
  `LastHitGoldBonus` unread, `MomentumBuffEffect` unapplied, the three
  inverted-branch bugs in §5.4/§8.2/§8.3, the `Lerp` argument order in §7.6, the
  day/night unit mismatch in §3.2). This is late-stage-prototype code, not
  ship-hardened code.

**My recommendation**: keep FFA (`FFA/FFAGameMode.as` + `FFABotSpawner`, which
hardcodes ten hero PrimaryAssetIds and needs no level authoring) as the *fastest*
path to a playable match, and treat Barracuda as the *highest-ceiling* path —
the one that yields a real, complete, self-sustaining game loop if someone is
willing to build or find the level. They are not in competition: FFA proves the
match pipeline, Barracuda is what you point it at afterwards.

---

## 11. What I could NOT recover

Stated plainly.

1. **The map.** No shipped `.umap` is named or foldered as Barracuda; no
   world-partition cell set belongs to one. `LVL_Bracket_01` /
   `LVL_Bracket_Copy_9_26` / `LVL_Battlefield_TG` are unverified candidates only.
2. **Every designer-tuned number that lives in a Blueprint CDO.** This includes
   `BarracudaPhases` (so I know the phase machine but not the phase *timeline*),
   `RespawnTimePerLevel`, `GoldBountyPerCurrentStreak`,
   `MercyHeroKillXPCoefficients`, `MinionSplitXPBonuses`, `DragonRewards`,
   `MainObjectiveClass`, `ItemLootTables`, and every `FMinionWave` / camp
   composition. **Root cause, and it is actionable:** `mappings.usmap` does **not
   contain the Angelscript-declared classes** — `BarracudaShop`,
   `BarracudaGameMode`, `BarracudaGameStateComponent` and
   `BarracudaMinionSpawner` are all absent (`LokiTower`,
   `LokiTowerDefenseGameMode` and `BarracudaPhase`, being C++, *are* present). So
   CUE4Parse silently drops those properties when deserializing the shipped BPs:
   dumping `BP_GameMode_Barracuda`, `BP_GameState_Barracuda` and
   `BP_BarracudaShop` returns CDOs with no serialized values. That is a **tool
   limitation, not evidence that the defaults are empty.** Fix: emit a usmap
   supplement for the AS classes from `Binds.Cache` + `PrecompiledScript.Cache`
   (asdump already has the exact schema — see §12).
3. **Blueprint bytecode.** `ShouldGameEnd`, `WillInterceptEliminatedTeam`,
   `OnAuthTowerDestroyed`, `GetDeadTowers`, `ApplyPassivesToHero`,
   `HandleOnActorKilled`, `FireStartingHorn`, `MultiHorn`, `BP_OnNewPhase`, and
   every `_Implementation` marked `NoOp` in script (`OnNewDay`, `OnNewNight`,
   `OnBountyGivenToPlayer`, `TowerGoldRewardVisual`, `ClearItemContainer`,
   `AddItemToContainer`, `EventFinishedAddingItems`, `UpdateVisuals`,
   `CreateInputItemWidget`, `UpdateCurrentTargetEnemy` on the abstract base) are
   Blueprint-side. The extractor has a `bpdump` mode with `ReadScriptData`
   enabled; decompiling Kismet is a separate project.
4. **Local variable names and line numbers.** Not serialized in a shipping cache
   (documented in `FORMAT.md`); every local reads as `vN`.
5. **The `Swordfish` variant's purpose.** `BP_GameMode_Barracuda_Swordfish` /
   `BP_GameState_Barracuda_Swordfish` exist alongside a family of
   `*_Swordfish` exotics and loot tables. Swordfish looks like a separate
   playlist/season codename that also had a Barracuda configuration. Unresolved.
6. **Whether the mode was ever public.** Nothing in these files dates or gates it.
7. **`FBarracudaLaneMinionConfig`** (`GenericDamage`, `AdditionalTowerDamage`,
   `ProjectileMaxDistance`, `ProjectileInitialSpeed`, `ProjectileHomingAcceleration`,
   all defaulting to 0) is declared but **never referenced anywhere in the 78
   script modules** — it is consumed by a Blueprint or C++ I did not trace.

### Decompiler artifacts I corrected (so nobody re-derives them wrongly)

The merged `asdump.py` renders `REFCPY` (object-reference assignment) with its
operands **reversed** in the pseudo-source. Every line in the output that reads
`nullptr = this.Foo;` is really `this.Foo = nullptr;`, and `v10 = this.Bar;`
immediately after a call is really `this.Bar = <call result>;`. Verified against
the disassembly appendix in three separate functions. It also mis-names the
member behind `TMap::opIndex` / `TArray::opIndex` reads (§7.2). **The
disassembly appendix is ground truth; the pseudo-source is a reading aid.**

---

## 12. Concrete follow-ups this unlocks

1. **Generate a usmap supplement for the Angelscript classes.** `asdump.py`
   already parses the exact property list, type and order for all 110 AS classes.
   Emitting those as extra usmap entries would let CUE4Parse read *every*
   AS-derived Blueprint CDO in the game — which immediately yields §11.2 (all the
   Barracuda tuning data) and would likely also help the DropPhase/FFA work. This
   is the single highest-leverage next step and it is pure offline tooling.
2. **Settle the map question** by dumping `LVL_Bracket_01` /
   `LVL_Battlefield_TG` actor lists with the existing extractor and grepping for
   `ABarracudaMinionSpawner` / `ABarracudaMinionWaypoint` / `BP_LokiTower`.
3. **Runtime probe, no level required.** With a live server-authority session,
   `GetBarracudaGameStateComponent()` and `GetBarracudaGameMode()` are plain
   static Angelscript functions reachable through the existing native-call
   primitive; the five cheat commands in §9.2 then drive the phase machine and
   the spawner tags directly. Spawning one `ABarracudaMinionSpawner` with a
   one-entry `FMinionWave` and two `ABarracudaMinionWaypoint`s wired to each other
   is enough to observe the whole creep loop.
4. **Backend note:** Barracuda needs **nothing** from `ags`. There is not a single
   HTTP/AccelByte touchpoint in any of the 28 modules. Every reward path is
   `GrantWalletCurrency` / `AuthGrantExperience` on the local player state.

---

## Appendix A — full declaration index

Every class, its members, and every function signature. Signatures are **exact**
(stored verbatim in the cache); `[BP]` marks a `BlueprintEvent` whose body is
`NoOp` in script.

### `ABarracudaGameMode : ALokiTowerDefenseGameMode`
Props: `UBarracudaRallyMinionsComponent@ RallyMinionsComponent`,
`UBarracudaPlayerSpawnerComponent@ BarracudaPlayerSpawnerComponent`,
`float32 MatchStartTime`, `float32 GoldLossOnDeath`, `TArray<int> GoldBountyPerCurrentStreak`,
`float64 DayNightDuration`, `bool bIsDay`, `TArray<float32> MinionSplitXPBonuses`,
`TArray<float32> MercyHeroKillXPCoefficients`, `float32 UnderdogHeroKillXPBonusPerLevel`,
`bool bAnyTowersKilled`, `TArray<TSubclassOf<UGameplayEffect@>> DragonRewards`,
`int NumDragonsKilled`, `TMap<ALokiPlayerState@, float64> LastKnockedTimeTable`,
`float64 KnockXPCooldownTime`, `FGameplayTag DragonKilledPilotVO`,
`FGameplayTag MomentumBossKilledPilotVO`, `TSubclassOf<UGameplayEffect@> MomentumBuffEffect`
```
static ABarracudaGameMode@ GetBarracudaGameMode()
UBarracudaGameStateComponent@ GetGameStateComponent() const
void BeginPlay_Implementation()
void AuthHandleBarracudaPhaseChanged(const FGameEvent_BarracudaPhaseChanged&, const AActor@)
void Tick_Implementation(const float64 DeltaSeconds)
void OnNewPhase_Implementation(const ERoundPhase NextPhase, const ERoundPhase LastPhase)
void AugmentCharacterLoadoutItems_Implementation(TArray<FStartupItemSpec>&inout)   [BP, empty]
bool HasBarracudaMatchStarted()
float64 GetMatchTime()
void OnPlayerKilled(const FPlayerKillEventData& KillData)
void OnBountyGivenToPlayer(const FVector&, ALokiPlayerState@, const int, const ECurrencyGrantReason, const int)  [BP]
void OnActorKilled_BP_Implementation(AActor@ VictimActor, AController@ Killer)
TArray<ALokiPlayerState@> GetPlayerStatesForRewardsInRadius(const FVector&, const float32, const int, AActor@)
void OnNewDay()   [BP] ; void OnNewNight()   [BP]
void HandleDayNight()
bool TowerKilled(ALokiTower@ TargetTower)   /  bool TowerKilled_Implementation(ALokiTower@)
void OnMomentumBossKilled(ALokiPlayerState@) ; void OnDragonKilled(ALokiPlayerState@)
void ApplyEffectToTeam(const int TeamIndex, const TSubclassOf<UGameplayEffect@>&)
void TowerGoldRewardVisual(ALokiTower@, ALokiPlayerState@, const int)   [BP]
```

### `UBarracudaGameStateComponent : UActorComponent`
Props: `float64 NextDayNightSwapTime` *(Replicated)*, `bool bDayNightTransitionEnabled`,
`TSet<AActor@> Structures`, `TSet<ABarracudaMinionWaypoint@> MinionWaypoints`,
`TSubclassOf<ABarracudaShop@> ShopClass`, `ABarracudaShop@ Shop` *(Replicated)*,
`FGameplayTagContainer DisabledSpawnerTypes`, `TArray<FBarracudaPhase> BarracudaPhases`,
`int CurrentPhaseIndex` *(Rep, RepNotify)*, `float64 CurrentPhaseStartTime` *(Rep)*,
`TArray<int> TeamKillScores` *(Rep, RepNotify)*, `FOnTeamKillsUpdated OnTeamKillsUpdated`,
`int NumDragonsKilled` *(Rep, RepNotify)*, `FOnDragonKillsUpdated OnDragonKillsUpdated`
```
void OnRep_OnTeamKillsUpdated() ; void OnRep_DragonKillsUpdated()
void LokiBeginPlay_Implementation()
void OnPlayerKilled(const FPlayerKillEventData&) ; void UpdateTeamKills()
void Tick_Implementation(const float64 DeltaSeconds)
void AuthMoveToNextBarracudaPhase()                      [BlueprintAuthorityOnly]
void OnRep_CurrentPhaseIndex(const int PreviousPhaseIndex)
private void EmitPhaseChangedEvent(const EBarracudaPhaseType PreviousPhaseType)
AActor@ GetRespawnStructure(const int TeamIndex)         [BlueprintAuthorityOnly, Pure]
float64 SecondsUntilNextDayNightSwap() const
void AuthPlayPilotVOForAll(const FGameplayTag&)          [NetServer]
void MultiPlayPilotVO(const FGameplayTag&)               [NetMulticast]
```
Delegates: `FOnTeamKillsUpdated.Broadcast(const TArray<int>& KillScores)`,
`FOnDragonKillsUpdated.Broadcast(const int NumDragons)`.

### `BarracudaGameStateGlobals.as` (free, all `Static` + `Pure`)
```
UBarracudaGameStateComponent@ GetBarracudaGameStateComponent()
FBarracudaPhase              GetCurrentBarracudaPhase()
EBarracudaPhaseType          GetCurrentBarracudaPhaseType()
float64                      GetCurrentBarracudaPhaseTime()
float64                      GetCurrentBarracudaPhaseTimeReminaing()      // sic
```

### `ABarracudaTeamState : ALokiTeamState`
No props. `__InitDefaults: TeamStateTeamOnlyClass = ABarracudaTeamState_TeamOnly::StaticClass()`.
Free: `static ABarracudaTeamState@ GetBarracudaTeamState(const int TeamIndex)`.

### `ABarracudaTeamState_TeamOnly : ALokiTeamState_TeamOnly`
`TMap<ABarracudaMinionSpawner@, float64> SpawnerToSpawnTime`
```
void SetSpawnerSpawnTime(ABarracudaMinionSpawner@, const float64 NextSpawnTime)
private void NetMulticastSpawnerNextSpawnTime(ABarracudaMinionSpawner@, const float64)   [NetMulticast]
static ABarracudaTeamState_TeamOnly@ GetBarracudaTeamStateTeamOnly(const int TeamIndex)
```

### `UBarracudaPlayerSpawnerComponent : UActorComponent`
`TArray<float64> RespawnTimePerLevel`, `float64 MatchTimeRespawnCeiling`, `float64 MatchRespawnTimeFactor`
```
void Tick_Implementation(const float64) ; float64 CalculateDeathTimer(ALokiPlayerState@)
private void TryRespawningPlayers()
```

### `UBarracudaRallyMinionsComponent : UActorComponent`
`float64 RallyAggroRange`
```
void LokiBeginPlay_Implementation()
private void OnCharacterDamaged(const FGameEvent_OnDamaged_Character&, const ALokiCharacter@)
private void RallyAlliedMinionsForHelp(ALokiHeroCharacter@ Victim, ALokiHeroCharacter@ Attacker)
```

### `UBarracudaPlayerStateComponent : UActorComponent`
`private float64 InternalNextRespawnTime` *(Rep, RepNotify)*, `FNextRespawnTimeChanged OnNextRespawnTimeChanged`
```
bool HasNextRespawnTime() const ; void ClearNextRespawnTime()
void SetNextRespawnTime(const float64) ; float64 GetNextRespawnTime()
float64 GetRespawnTimeRemaining() ; int GetRespawnTimeRemainingForDisplay()
private void NextRespawnTimeChanged() ; private void OnRep_NextRespawnTime()
```

### `UBarracudaLaneComponent : UActorComponent`
`int LaneIndex`, `FOnLaneIndexUpdated OnLaneIndexUpdated`
```
bool HasLaneIndex() ; void SetLaneIndex(const int NewValue)   [BlueprintAuthorityOnly]
FOnLaneIndexUpdated.Broadcast(UBarracudaLaneComponent@, const int OldIndex, const int NewIndex)
```

### `UBarracudaStructureComponent : UActorComponent`
`bool bAttackable`, `bool bRespawnLocation`; `LokiBeginPlay_Implementation()`, `LokiEndPlay_Implementation()`

### `UBarracudaMinionTargetingComponent : ULokiMinionTargetingComponent` *(Abstract)*
`ALokiCharacter@ HighPriorityEnemyCharacter`, `AActor@ CurrentTargetEnemy`,
`float64 ReleaseHighPriorityEnemyTime`, `float64 HighPriorityEnemyMemory`
```
void NotifyEnemyHeroHitAlliedHero(ALokiCharacter@ EnemyCharacter)
AActor@ UpdateTargetEnemy_Implementation()
void UpdateCurrentTargetEnemy()   [BP, overridden by the three subclasses]
void DrawTargetingDebug() const ; bool IsActorInEnemyList(AActor@ TargetActor) const
```
Subclasses: `UBarracudaLaneCreepTargetingComponent`,
`UBarracudaJungleCreepTargetingComponent`, `UBarracudaTowerTargetingComponent`
(+ `AActor@ FindClosestEnemyByClass(ALokiMinionCharacter@ Minion, UClass@ ClassFilter)`).

### `UBarracudaJungleCreepComponent : UActorComponent`
`float64 UnstuckTeleportTime`, `float64 StuckDetectionTime`; `Tick_Implementation(const float64)`

### `ABarracudaMinionSpawner : ALokiActor`
Full property table in §5.1.
```
void LokiBeginPlay_Implementation()
void ClientGetMapIconState(bool&out bShowLivingIcon, float64&out SecondsRemaining)
void AuthSetNextSpawnTime(const float64 NewTime)
void AuthOnNewRoundPhase(const ERoundPhase NewPhase)
void AuthHandleBarracudaPhaseChanged(const FGameEvent_BarracudaPhaseChanged&, const AActor@)
private void AuthTryEnablingSpawnLoop()
void AuthOnNewDayNightState(const ELokiDayNightState NewState, const ELokiDayNightState OldState)
void Tick_Implementation(const float64 DeltaSeconds)
private bool IsSpawningAllowed() ; bool HasNextRespawnTime() const
void AuthSpawnWave()                                    [BlueprintAuthorityOnly]
void SetMinionLevel(ALokiCharacter@ Minion)
void BeginStaggerSpawn() ; void StaggerSpawn()
void AuthCleanupMinions() ; void AuthCleanMinionReferences()
bool AuthShouldSpawnWave() ; void AuthTryUpdatingNextSpawnTime()
bool IsClockBasedSpawning() ; void AuthCheckDayNightSpawn()
private void HandleVisibilityEvaluated(UVisibilityReceiver@, const TArray<int>&in TeamsIndicesWithVision)
private void GrantTimerToTeam(const int TeamIndex) ; private void GrantTimerToAllTeams()
void PlaySpawnAudioEvent()
```

### `ABarracudaMinionWaypoint : AActor`
`int InitialLaneIndex`, `ABarracudaMinionWaypoint@ WaypointTowardTeam0`,
`ABarracudaMinionWaypoint@ WaypointTowardTeam1`, `UBoxComponent@ TriggerComponent`,
`UBarracudaLaneComponent@ LaneComponent`
```
void LokiBeginPlay_Implementation()
void HandleTriggerOverlap(UPrimitiveComponent@, AActor@, UPrimitiveComponent@, const int, const bool, const FHitResult&in)
ABarracudaMinionWaypoint@ GetNextWaypoint(AActor@ Actor)
```

### `UBarracudaMinionWaypointFollowerComponent : UActorComponent`
Props in §4.3.
```
void LokiBeginPlay_Implementation() ; void Tick_Implementation(const float64)
bool HasCurrentWaypoint() ; FVector GetTargetLocationForCurrentWaypoint()
void ReachedWaypoint(ABarracudaMinionWaypoint@ Waypoint)
ABarracudaMinionWaypoint@ GetInitialWaypoint()
bool IsStuck() ; void TryRescue()
```

### `UBTService_BarracudaUpdateMinionWaypoint : UBTService_BlueprintBase`
`FBlackboardKeySelector WaypointLocationKey`;
`void TickAI_Implementation(AAIController@, APawn@, const float64 DeltaSeconds)`

### `UBarracudaMinionRewardComponent : UActorComponent`
`EBarracudaMinionGoldRewardMethod GoldRewardMethod`, `bool bGrantLoot`, `int LastHitGoldBonus`
```
void DisableAllRewards()
int GetGoldBounty(AController@ KillerController)
int GetXPBounty(AController@ KillerController)
int GetLastHitGoldBounty(AController@ KillerController)
```

### `FBarracudaLaneMinionConfig` *(struct, unreferenced)*
`float64 GenericDamage, AdditionalTowerDamage, ProjectileMaxDistance, ProjectileInitialSpeed, ProjectileHomingAcceleration`

### `ABarracudaShop : AActor` + `UBarracudaShopItemGraphNode` + `FBarracudaShopPurchasePlan`
Props in §8.2.
```
void LokiBeginPlay_Implementation()
int GetItemTotalCost(const TSubclassOf<ALokiBaseItem@>&)
int GetItemSellValue(const TSubclassOf<ALokiBaseItem@>&)
int GetIncrementalCost(const TSubclassOf<ALokiBaseItem@>&)
void AuthBuyItem(ALokiPlayerState@, const TSubclassOf<ALokiBaseItem@>&)     [BlueprintAuthorityOnly]
void AuthSellItem(ALokiPlayerState@, ALokiBaseItem@)                        [BlueprintAuthorityOnly]
TArray<TSubclassOf<ALokiBaseItem@>> GetOutputItems(const TSubclassOf<ALokiBaseItem@>&)
TArray<TSubclassOf<AActor@>> GetAllShopItems()
void BuildGraph() ; void CalculateTotalCostsForAllItems()
void CalculateItemTotalCost(UBarracudaShopItemGraphNode@ Node)
UBarracudaShopItemGraphNode@ GetOrCreateItemGraphNode(const TSubclassOf<ALokiBaseItem@>&)
void DebugLogGraph() ; void DebugPrintNode(UBarracudaShopItemGraphNode@, const FString& Indentation)
void BroadcastFilterUpdated()
void OnFilterByName(...)   void OnResetFilters(...)   void OnFilterToggleTag(...)   void OnFocusItem(...)
void TryGeneratePurchasePlan(FBarracudaShopPurchasePlan&inout, ULokiInventoryComponentComboItems@, const TSubclassOf<ALokiBaseItem@>&)
void ExecutePurchasePlan(const FBarracudaShopPurchasePlan&in, ALokiPlayerState@, const TSubclassOf<ALokiBaseItem@>&)
static ABarracudaShop@ GetBarracudaShop()
```

### `UBarracudaShopPlayerControllerComponent : UActorComponent`
```
void LokiBeginPlay_Implementation()
void ClientOnBuyItem(const FUIEvent_Barracuda_Shop_BuyItem&, const AActor@)
void ServerBuyItem(const TSubclassOf<ALokiBaseItem@>&)                       [NetServer]
void ClientOnSellItem(const FUIEvent_Barracuda_Shop_SellItem&, const AActor@)
void ServerSellItem(ALokiBaseItem@)                                          [NetServer]
```

### Shop widgets
```
UBarracudaShopItemListWidget : UUserWidget
    void ClearItemContainer() [BP] ; void AddItemToContainer(const TSubclassOf<ALokiBaseItem@>&) [BP]
    void EventFinishedAddingItems() [BP] ; void Construct_Implementation() ; void UpdateVisuals()
    TArray<UBarracudaShopItemGraphNode@> SortItemNodesByTotalCost(const TArray<UBarracudaShopItemGraphNode@>&)
    bool DoesItemPassFilter(ABarracudaShop@ Shop, UBarracudaShopItemGraphNode@ ItemNode)
    void OnToggleVisibility(...) ; void OnFilterUpdated(...)

UBarracudaShopItemTreeWidget : UUserWidget
    UBarracudaShopItemTreeNodeWidget@ RootNode  [BindWidget]
    TSet<ALokiBaseItem@> ItemsToPotentiallyMarkAsOwned
    void PreConstruct_Implementation(const bool IsDesignTime) ; void Construct_Implementation()
    void HandleFocusItem(...) ; void HandleItemEnteredOrExitedInventory(...)
    void UpdateVisuals() ; void UpdateVisualsInternal(const TSubclassOf<ALokiBaseItem@>&)

UBarracudaShopItemTreeNodeWidget : UUserWidget
    UPanelWidget@ ChildContainer ; UTextBlock@ ItemName ; UOverlay@ OwnedIndicator
    UBarracudaShopItemWidget@ ShopItemWidget ; int DesignTimePrviewInputCount (sic)
    int DesignTimePreviewDepthCount ; bool bDesignTimePreviewOwned
    TSubclassOf<ALokiBaseItem@> ItemClass ; UBarracudaShopItemTreeWidget@ Tree
    UBarracudaShopItemTreeNodeWidget@ CreateInputItemWidget(const TSubclassOf<ALokiBaseItem@>&, const int, const int) [BP]
    void PreConstruct_Implementation(const bool) ; void Construct_Implementation()
    void UpdateVisuals(const bool bDesignTime = false)
    void UpdateName(const bool) ; void UpdateRootNode(const bool) ; void UpdateOwnership(const bool)
    void SetItem(const TSubclassOf<ALokiBaseItem@>& InItemClass)

UBarracudaShopItemWidget : UUserWidget
    EBarracudaShopValueType ValueType ; ALokiBaseItem@ RepresentedItem
    void UpdateVisuals() [BP]
    FEventReply OnMouseButtonDown_Implementation(const FGeometry&, const FPointerEvent&)
    void SetRepresentedItem(ALokiBaseItem@ Item) ; int GetValue()

UBarraucdaShopFilterWidget : UUserWidget                                   // sic
    TArray<FBarracudaShopTagFilter> TagFilters
struct FBarracudaShopTagFilter { FText Label; FGameplayTag Tag; FGameplayTag RecommendedHeroTag; }
```

---

## Appendix B — every Barracuda gameplay tag referenced in script

| Tag | Used by |
|---|---|
| `Barracuda.Minion.GrantsDragonBuff` | `ABarracudaGameMode::OnActorKilled_BP` → `OnDragonKilled` |
| `Barracuda.Minion.GrantsMomentumBuff` | `ABarracudaGameMode::OnActorKilled_BP` → `OnMomentumBossKilled` |
| `GameMode.Barracuda.InBase` | shop buy/sell gate |
| `Static.Barracuda.Spawner.Neutral` | jungle-spawner cheat toggle |
| `Static.Barracuda.Spawner.Creep` | lane-spawner cheat toggle |
| `Attribute.MinionGoldMultiplier` | creep-gold multiplier (jungler item) |
| `State.Combat.InCombat` | waypoint follower's stuck detection |
| `State.Dead` | shop buy gate (dead players may buy) |

---

## Appendix C — reproduce this

```bash
cd "G:/git/Supervive Revival Project/tools/asdump"
python asdump.py --module Barracuda        # -> out/modules/Barracuda/**.as.txt
```

Each output file is pseudo-source followed by a per-function disassembly appendix
in which every operand is symbol-resolved. **When the two disagree, the appendix
wins** (§11). Cache offsets cited in this document (`0x1c891`, `0x14957`,
`0x2de8a`, `0x20f34`) are the byte offsets of those functions' bytecode inside
`PrecompiledScript.Cache` and are printed in the appendix headers.

Asset-side evidence was gathered by parsing the `.utoc` directory indexes
directly (mount point + directory tree + file entries + string table, per
`FIoStoreTocHeader` v6, containers unencrypted with flags `Compressed|Signed|Indexed`)
and with `tools/extractor/extractor/bin/Release/net9.0/extractor.exe`
(`wherefile`, `dump`). No game file was opened for writing.
