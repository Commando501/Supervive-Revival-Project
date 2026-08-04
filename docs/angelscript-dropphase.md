# The drop-in sequence, decompiled — SUPERVIVE's Angelscript drop phase

**Date:** 2026-07-26 · **Source:** `Loki/Script/PrecompiledScript.Cache` (shipping build 2025-12-17),
decompiled with `tools/asdump/asdump.py`; native surface from `Loki/Script/Binds.Cache` +
`Binds.Cache.Headers`; enum members from `mappings.usmap`.

**Modules covered (7 of the 78):**

| module | source path | classes | fns | bytecode |
|---|---|--:|--:|--:|
| `GameMode.DropPhase.LokiDropPod` | `GameMode/DropPhase/LokiDropPod.as` | 6 | 102 | 22,884 B |
| `GameMode.DropPhase.LokiDropPhase_PlayerStateComponent` | `GameMode/DropPhase/LokiDropPhase_PlayerStateComponent.as` | 1 | 34 | 6,760 B |
| `GameMode.DropPhase.LokiDropShip` | `GameMode/DropPhase/LokiDropShip.as` | 1 | 6 | 1,352 B |
| `GameMode.DropPhase.LokiDropPodImpactIndicator` | `GameMode/DropPhase/LokiDropPodImpactIndicator.as` | 1 | 15 | 816 B |
| `GameMode.DropPhase.LokiDropPodLaser` | `GameMode/DropPhase/LokiDropPodLaser.as` | 1 | 5 | 308 B |
| `Airship.LokiAirship` | `Airship/LokiAirship.as` | 1 | 17 | 8,636 B |
| `GameMode.LokiGameMode_ExoticLootComponent` | `GameMode/LokiGameMode_ExoticLootComponent.as` | 2 | 14 | 1,760 B |

Reproduce with `python tools/asdump/asdump.py --module DropP` etc.; per-module output lands in
`tools/asdump/out/modules/…`. Native bind dumps in this doc came from
`python tools/asdump/dropphase_binds.py` (new, added by this session).

---

## 0. How to read the decompiled output (two rendering quirks, both proven)

Everything below was cross-checked against the **disassembly appendix**, which is ground truth.
Two things in the pseudo-source read backwards or thin, and you must know them or you will
mis-read the drop logic:

**(a) Handle/member assignments print with the operands swapped.** `REFCPY` takes
*(value, destination)*; the lifter prints `dest = value` in source order, i.e. reversed.

```
pseudo:   this = this.PodStateEvent.DropPod;            // WRONG WAY ROUND
bytecode: PshVPtr this ; PshVPtr this ; ADDSi .PodStateEvent ; ADDSi .DropPod ; REFCPY
real:     PodStateEvent.DropPod = this;
```
Same for `ParentPod = this.LeaderPod` (really `this.LeaderPod = ParentPod`),
`DropPod = this.OwningDropPod` (really `this.OwningDropPod = DropPod`),
`v8 = this.PodMeshComponent` (really `this.PodMeshComponent = USkeletalMeshComponent::Get(this)`),
`nullptr = this.ImpactIndicator` (really `this.ImpactIndicator = nullptr`).

**(b) A handful of ternaries lose one arm** and print as an empty `if (…) { }`. Two occur in these
modules and both are resolved here from the bytecode:

```
UpdatePodMovement    : SteerDistance = bIsTeamLeaderPod ? MaxSteerDistance : MaxNonLeaderSteerDistance
UpdateGroundLaserAtLocation : BoneName = SourceDropPod.bIsCrewPod ? CrewPodBoneName : LeaderPodBoneName
```
(the second resolves one of the corpus's five `<?>` placeholders —
`CrewPodBoneName = "singleBody_01_m_jnt"`, `LeaderPodBoneName = "body_01_m_jnt"`).

A third: `ALokiDropPod::IsPlayerStatePilot` prints `return v2` on its null branch; the bytecode is
`SetV4 v3,0 ; JMP → RET`, i.e. **`return false`**.

Local names and line numbers do not exist in a shipping cache (`DeclaredAt == 0`,
`LineNumbers == []` for all 1,463 functions), so locals are `vN`.

---

## 1. What each module is

- **`LokiDropShip.as`** — the *drop plane* the whole team rides. Script subclass of the **native**
  `ALokiDropPlane`. It owns exactly one job: turn "team N wants to drop at P" into a spawned,
  initialised, crewed leader pod. 1 property, 2 real methods.
- **`LokiDropPod.as`** — the pod itself and the entire descent state machine: intro → descend →
  outro → destroy, crew-pod spawning, crew-pod detach from the leader pod, steering, camera glue,
  the impact indicator, the ground laser, landing teleport, and the drop-phase actor-hiding release.
  This is the heart of the sequence (102 functions, 22.8 KB of bytecode).
- **`LokiDropPhase_PlayerStateComponent.as`** — the **client-side input/controls** layer, a script
  subclass of the native `ULokiPlayerDropPlaneComponent`, attached to each `ALokiPlayerState`. Owns
  the "hold a direction to detach from the leader" mechanic, the drop-location cursor, and the two
  server RPCs the client sends during the drop.
- **`LokiDropPodImpactIndicator.as`** — the replicated ground marker that shows where a pod will
  land, plus its landing-radius ring.
- **`LokiDropPodLaser.as`** — the beam from pod to target point (local, pilot-only).
- **`LokiAirship.as`** — *not* part of the drop phase. It is the in-match rideable **airship**
  ("Airdoo"): collision damage, roadkill, boop impulses, fuel burn, and health regeneration phases.
  Included here because it was in the same work batch.
- **`LokiGameMode_ExoticLootComponent.as`** — also not drop phase: per-day exotic loot generation on
  the game mode, seeded from the game state's random stream.

---

## 2. The drop-phase class reference

### 2.1 `ALokiDropShip : ALokiDropPlane`  *(→ `/Script/Loki.LokiDropPlane`, `Loki/Source/Loki/DropPhase/LokiDropPlane.h`)*

```angelscript
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
protected TSubclassOf<ALokiDropPod@> TeamDropPodClass;          // = nullptr by default

UFUNCTION(BlueprintCallable, CanOverrideEvent)
protected bool SpawnDropPodForTeam(const int TeamIndex, const FVector& SpawnLocation,
                                   const FVector& LandingLocation);
ALokiPlayerState@ GetTeamDropLeader(const int TeamIndex);        // plain script method (CALLINTF-able)
```

`SpawnDropPodForTeam` (server) — verbatim behaviour:

```
if (TeamDropPodClass == nullptr) return false;
pod = LokiGameplay::SpawnPoolableActorFromClassDeferred(
          __WorldContext, TeamDropPodClass, FTransform(SpawnLocation),
          nullptr, nullptr,
          ESpawnActorCollisionHandlingMethod::Undefined,
          ESpawnActorScaleMethod::MultiplyWithRoot);
if (pod == nullptr) return false;
leaderPS = GetTeamDropLeader(TeamIndex);
pod.InitializeDropPod(TeamIndex, leaderPS, LandingLocation, /*bIsTeamLeader=*/true, this, nullptr);
FinishSpawningActor(pod, FTransform(SpawnLocation));
RemovePlayerFromPlane(leaderPS);                                  // native ALokiDropPlane
if (ULokiRideableComponent::Get(pod) != null)
    rideable.AuthPlayerEnterWorldAttachedToRidable(leaderPS, LandingLocation);
if (leaderPS != null && ULokiPlayerDropPlaneComponent::Get(leaderPS) != null)
    planeComp.MulticastOnDropPodLaunched(pod);                    // ← the client hand-off
ALokiServerAnalyticsManager::GetFromContext(...)?.AddTeamDropEvent(TeamIndex, LandingLocation, leaderPS);
return true;
```

`GetTeamDropLeader` — `LokiGameplay::GetPlayerStatesOnTeam(TeamIndex)`, returns the **first**
player state with `IsSpawnTeamLeader() == true`, otherwise **nullptr**. (There is a second loop over
the same array testing `!IsSpectator() && IsSpawnTeamLeader()`, but every path through its body
jumps to the loop tail without storing anything — it is dead code in the shipped bytecode. The
function's fall-through return is an uninitialised handle, i.e. null.)

### 2.2 `ALokiDropPod : ALokiDropPodBase`  *(→ `/Script/Loki.LokiDropPodBase`, `…/DropPhase/LokiDropPodBase.h`)*

**Tunables (defaults from the constructor, doubles decoded from their bit patterns):**

| property | default | meaning |
|---|--:|---|
| `InitialDropPodSpeed` | 2500 | launch speed along (destination − start) |
| `IntroSequenceTotalTime` | **6.5 s** | intro timer → `OnIntroSequenceFinished` |
| `TotalTimeForPodControls` | **5.5 s** | steering window → `OnOutroSequenceStart` |
| `OutroSequenceTotalTime` | **1.0 s** | outro → `OnOutroSequenceFinished` |
| `TotalPodDestructionDelayTime` | **1.5 s** | destroy delay → `FinishDestroyPod` |
| `OutroDistance` | 4000 | *declared, never read in script* |
| `PodDetachTotalTime` | 1.0 s | crew-pod separation animation length |
| `PodDetachTotalDistance` | 1000 | lateral separation distance |
| `MaxSteerDistance` / `MaxNonLeaderSteerDistance` | 7500 / 7500 | steer budget (leader / crew) |
| `IndicatorInterpSpeed` | 2.0 | *declared, never read in script* |
| `DisplayDropPhaseHiddenActorsHeight` | **10000** | camera Z at which hidden actors are revealed |
| `bIsCrewPod` | false | picks which mesh bone the laser anchors to |
| `CrewPodBoneName` / `LeaderPodBoneName` | `singleBody_01_m_jnt` / `body_01_m_jnt` | |
| `DetachingFromLeaderPodStartTime` | −1.0 | −1 = "not detaching" sentinel |

**Replicated state** (`Replicated, ReplicationCondition=0` = `COND_None`):

| property | type | RepNotify |
|---|---|---|
| `bIsTeamLeaderPod` | bool | |
| `PodTeamIndex` | int | |
| `ImpactIndicator` | `ALokiDropPodImpactIndicator@` | |
| `CurrPodDestination` | FVector | |
| `AttachedCrewPods` | `TArray<ALokiDropPod@>` | |
| `LeaderPod` | `ALokiDropPod@` | **`OnRep_LeaderPod`** |
| `DetachingCrewPods` | `TArray<ALokiDropPod@>` | |
| `PodDetachData` | `FLokiPodDetachData` | **`OnRep_PodDetachData`** |
| `PodStateEvent` | `FGameEvent_OnDropPodStateChanged_PlayerState` | **`OnRep_PodStateEvent`** |
| `CrewDetachEvent` | `FGameEvent_CrewDropPodDetach_PlayerState` | **`OnRep_CrewDetachEvent`** |
| `LeaderDetachEvent` | `FGameEvent_LeaderDropPodDetach_PlayerState` | **`OnRep_LeaderDetachEvent`** |
| `CurrentInputDirection` | `ELokiMovementInputDirection` | |

Plus the inherited **native** `ALokiDropPodBase::PilotPlayerState` (`SetPilotPlayerState` /
`GetPilotPlayerState`, replication notify `OnPilotPlayerStateReplicated` which the script overrides).

**Client-only / transient (NOT replicated):** `bPilotHasPodControl`, `bIsLocalPlayerPilot`,
`GroundLaserIndicator`, `bSteeringEnabled`, `SteeringStartTime`, `bHasStartedGameplay`,
`AllDetachedCrewPods`, `bIsHidingDropPhaseHiddenActors` (init **true**), `bPodIsDestroying`,
`LastInputDirection`, `bReadyForOutro`, `PodMeshComponent`, the three `bRetry*CameraGlue` flags,
`PlayersToSpawnCrewPodFor`.

**Script events (multicast delegates):** `FOnPodOutroStarted OnPodOutroStarted`,
`FOnLeaderPodHasCrewPodDetached OnLeaderPodHasCrewPodDetached`,
`FOnCrewPodHasDetached OnCrewPodDetached`, `FOnPodMoveDirectionChanged OnPodMoveDirectionChanged`
(the latter three carry `(ELokiMovementInputDirection, const FVector&)`).

**Function list, exact signatures** (UFunction alias in brackets where it differs):

```
void  LokiBeginPlay_Implementation()                       [UFunction LokiBeginPlay]
void  LokiEndPlay_Implementation()                         [UFunction LokiEndPlay]
void  Tick_Implementation(const float64 DeltaSeconds)      [UFunction Tick]
void  OnPilotPlayerStateReplicated_Implementation()        [UFunction OnPilotPlayerStateReplicated]
void  InitializeDropPod(const int TeamIndex, ALokiPlayerState@ PlayerState,
                        const FVector& LandingLocation, const bool bIsTeamLeader,
                        ALokiDropShip@ DropShip, ALokiDropPod@ ParentPod)
void  StartPodGameplay()                                   UFUNCTION(BlueprintCallable)
void  BP_StartPodGameplay() / _Implementation              (BP hook, DisplayName=OnStartPodGameplay)
void  OnPodTeamIndexChanged(AActor@ ChangedActor, const int OldTeamIndex, const int NewTeamIndex)
void  PreparePodForAttach()                                protected
void  PreparePodForDetach()                                protected
void  OnRep_LeaderPod()
bool  IsPlayerStateAssociated(APlayerState@ InPlayerState)
void  SetDropPodState(const ELokiDropPodState NewPodState) protected
void  KickPlayersFromPod()                                 protected
void  StartPodMovement()                                   protected
void  StartDestroyPod()                                    protected
void  TransitionCameraToLeaderPod() / ToCrewPod() / ToPlayer()
void  FinishDestroyPod()
void  BP_OnPrematurePodDestruction() / _Implementation     (BP hook)
void  UpdateDropPhaseHiddenActors()                        protected
void  OnRep_PodStateEvent()                                protected
void  SetCrewPodDetachState(const ELokiCrewPodDetachState NewDetachState,
                            const float64 InputPercent = 0.0f,
                            const ELokiMovementInputDirection DetachDirection = None,
                            const FVector& VectorDirection = FVector::ZeroVector)
void  OnRep_CrewDetachEvent()                              protected
void  SetLeaderPodDetachState(const ELokiLeaderPodDetachState NewDetachState,
                              const ELokiMovementInputDirection DetachDirection = None,
                              const FVector& Direction = FVector::ZeroVector)
void  OnRep_LeaderDetachEvent()                            protected
void  OnDropPodHit(UPrimitiveComponent@ HitComponent, AActor@ OtherActor,
                   UPrimitiveComponent@ OtherComp, const FVector& NormalImpulse,
                   const FHitResult&in Hit)                protected
void  DetachPodFromLeader(const ELokiMovementInputDirection MoveDirection)
FVector ConvertDirectionToVector(const ELokiMovementInputDirection Direction)   protected
void  StartDetachingPodFromLeader(const ELokiMovementInputDirection MoveDirection)   protected
void  InitializeDetachingPodFromLeader()                   protected
void  OnRep_PodDetachData()                                protected
void  FinishDetachingPodFromLeader()                       protected
void  UpdateDetachingPodFromLeader()                       protected
bool  IsPlayerStatePilot(ALokiPlayerState@ PlayerState)
void  QueueCrewForPodSpawn(ALokiDropShip@ DropShip)        protected
void  SpawnCrewPodQueue()                                  protected
ALokiDropPod@ SpawnCrewPod(ALokiPlayerState@ PlayerState)  protected
void  OnIntroSequenceFinished()                            protected
void  OnOutroSequenceStart()                               protected
void  OnOutroSequenceFinished()                            protected
void  AllowPodSteeringStarted() / AllowPodSteeringEnded()  protected
void  SpawnImpactIndicator(const int TeamIndex)            protected
void  SpawnLaserIndicator(const int TeamIndex)             protected
void  DestroyImpactIndicator() / DestroyLaserIndicator()   protected
void  UpdateGroundLaserAtLocation(const FVector& Destination, ALokiDropPod@ SourceDropPod)
void  UpdateAttachedPodLaserIndicator()                    protected
void  BroadcastDirectionEvent(const ELokiMovementInputDirection InputDirection,
                              const FVector& Direction)    protected
void  SetCharacterLanding(ALokiCharacter@ TargetCharacter, const FVector& TargetPosition)  protected
void  UpdateCharacterLocations()                           protected
void  UpdatePodMovement(const ELokiMovementInputDirection MoveDirection,
                        const float64 DeltaSeconds = 0.0f)
```

`FLokiPodDetachData` (script UCLASS/struct, replicated as a whole):
`FVector PodDetachDirection, PodDetachStartLocation, LeaderDetachStartLocation;
ELokiCrewPodDetachState CrewDetachState; ELokiMovementInputDirection MoveDirection;`

### 2.3 `ULokiDropPhase_PlayerStateComponent : ULokiPlayerDropPlaneComponent`

*(→ `/Script/Loki.LokiPlayerDropPlaneComponent`, `Loki/Source/Loki/Player/LokiPlayerDropPlaneComponent.h`)*

**It declares ZERO `UPROPERTY`s** — every member below is script-only, unreplicated, invisible to
Blueprint and to the network. Client authority for the detach mechanic lives entirely here and is
mirrored to the server by two RPCs.

| member | default | note |
|---|--:|---|
| `MaxHeightRange` | 20000 | declared; unused in script |
| `MinimumTargetLocationMovementSpeed` / `Maximum…` | 300 / 900 | declared; unused in script |
| `PodDetachFromLeaderMinTime` / `MaxTime` | **0.5 / 2.0 s** | detach hold-time window |
| `bDropPhaseControlsDisabled` | false | set from the active `ALokiGameAugment` |
| `bCanSelectDropLocation` | false | |
| `NetworkUpdateFrequencey` | 0.05 | declared; unused in script |
| `BufferedDestinationDelta`, `TargetMovespeedDelta` | — | declared; unused in script |
| `DropPodActor` | — | script mirror of the pod (distinct from the **native** `DropPod`) |
| `PodSteeringEventListenerHanddle` | — | game-event listener handle (sic, typo in source) |
| `bPodSteeringEnabled` / `bPodDetachingEnabled` | false/false | |
| `bIgnoreInput` | **true** | cleared once the pod starts (or after the detach-arm timer) |
| `bAlwaysUpdateNetwork` | true | |
| `INVALID_MOVEMENT_VALUE` | **−1000.0** | sentinel for "no axis input this frame" |
| `MovementForwardValue` / `MovementRightValue` | INVALID | |
| `CurrMoveDirection` | None | |
| `CrewPodDetachStartTime` | 0 | |
| `bPodIsAttachedToLeader` | **true** | |
| `DetachInputStartTime` / `CurrTotalTimeForDetach` | −1 / −1 | |

Functions:

```
void OnSelectDropLocationStarted_Implementation()          [UnrealName=OnSelectDropLocationStarted]
void OnSelectDropLocationEnded_Implementation()            [UnrealName=OnSelectDropLocationEnded]
void OnEventRouterReady_Implementation(UGameEventRouterComponent@ Router)
void OnDropPodStarted_Implementation(AActor@ PodActor)     [UnrealName=OnDropPodStarted]
void OnDropPodEnded_Implementation()                       [UnrealName=OnDropPodEnded]
void OnDropPodStartedWithPilot()                           UFUNCTION(BlueprintCallable)
float64 GetInputTimeForDetach()                            protected
void OnAllowPodDetach()                                    UFUNCTION(BlueprintCallable)  ← timer target
void OnPodSteeringEnabled(const FGameEvent_PodSteeringEnabled& Event,
                          const EGameEventStatefulEventType EventType)
void OnGameAugmentSet(const FGameEvent_GameAugmentSet& Event,
                      const EGameEventStatefulEventType EventType)
void TryStartSteering()
void Tick_Implementation(const float64 DeltaSeconds)
void OnForwardMovementInput_Implementation(const float64 ForwardValue)
void OnRightMovementInput_Implementation(const float64 RightValue)
bool IsLocalClient()
void UpdateDropLocationCursor()                            private
void ProcessMovement()                                     private
bool UpdatePodControl(const ELokiMovementInputDirection MoveDirection)          protected
ELokiMovementInputDirection CalculateDetachDirection(const float64 ForwardMovementValue,
                                                     const float64 RightMovementValue)  protected
void DetachPodFromLeader(const ELokiMovementInputDirection MoveDirection)       protected
void ServerDetachPodFromLeader(…) / _Implementation        UFUNCTION(NetServer)   ← RPC
bool HasDropPodControl() const                             protected
void UpdatePodMovement(const ELokiMovementInputDirection MoveDirection)         protected
void ServerUpdatePodMovement(…) / _Implementation          UFUNCTION(NetServer)   ← RPC
void __InitDefaults()      // sets PrimaryComponentTick.bStartWithTickEnabled = false
```

### 2.4 `ALokiDropPodImpactIndicator : ALokiActor` and `ALokiDropPodLaser : ALokiActor`

Indicator: `ALokiDropPod@ OwningDropPod` (**Replicated**, RepNotify `OnRep_OwningDropPod`),
`ALokiPlayerState@ OwningPlayerState` (**Replicated**), `float64 LandingRadius`,
`bool bIsIndicatorInitialized`.
`BeginPlay → CheckIndicatorReady()`; `CheckIndicatorReady` sets `bIsIndicatorInitialized = true` the
moment `OwningDropPod != nullptr` (so on the client it flips inside `OnRep_OwningDropPod`, which
then also fires the BP event `OnDropPodReplicated`). `IsIndicatorReadyToDisplay()` is the BP-facing
query the widget/material reads. `Tick` (server only) destroys the indicator when
`IsValid(OwningDropPod)` goes false. `SetLandingRangeRadius(Radius)` writes `LandingRadius` and
fires the BP event `OnLandingRadiusChanged` when it changes.
`InitializeIndicator(DropPod)` sets `OwningDropPod = DropPod`,
`OwningPlayerState = DropPod.GetPilotPlayerState()`, then `SetOwner(OwningPlayerState)`.

Laser: `ALokiDropPod@ OwningDropPod` (Replicated), and `InitializeIndicator(DropPod)` →
`OwningDropPod = DropPod; SetOwner(DropPod.GetPilotPlayerState())`. Everything else about the laser
(scale, rotation) is driven from the pod's `UpdateGroundLaserAtLocation`.

---

## 3. The reconstructed state machine

### 3.1 Enums (members recovered from `mappings.usmap`; the raw ordinals are in the disassembly)

```
ELokiDropPodState        0 None · 1 IntroSequence · 2 Attached · 3 Descending · 4 OutroSequence · 5 Destroying
ELokiCrewPodDetachState  0 None · 1 Attached · 2 Detachable · 3 DetachInputStarted · 4 DetachInputStopped
                         5 DetachInputContinue · 6 StartDetaching · 7 FinishDetaching
ELokiLeaderPodDetachState 0 None · 1 StartDetaching · 2 AdditionalStartDetaching
                         3 OneOfManyPodsFinishedDetaching · 4 AllDetachingPodsFinished
ELokiMovementInputDirection 0 None · 1 Up · 2 UpRight · 3 Right · 4 DownRight · 5 Down · 6 DownLeft · 7 Left · 8 UpLeft
EPlayerDropState         0 PrePlane · 1 InPlane · 2 InDropPod · 3 DropConcluded         (native, ALokiDropPlane)
EDropHidingStatus        0 Hiding · 1 FinishRequested · 2 Finished                       (native)
ERoundPhase              0 EGP_ServerStartup · 1 EGP_BeginInit · 2 EGP_Pre · 3 EGP_FinishInit
                         4 EGP_SpawnSelect · 5 EGP_SpawnReveal · 6 EGP_Lineup · 7 EGP_Combat
                         8 EGP_Post · 9 EGP_Shutdown
```

### 3.2 End-to-end sequence

Steps marked **[native]** are C++ (declaration proven from `Binds.Cache`, body not available);
**[script]** steps are decompiled here.

```
 1 [native]  ALokiRoundGameMode::GoToPhase(EGP_SpawnSelect)  (ModeSupportsDropPlane() gate)
 2 [native]  ULokiGameModeDropPlaneComponent::SpawnPlane()  -> ALokiDropPlane (a BP of ALokiDropShip)
            component props: LokiDropPlane, PlayerStatePlaneComponentClass (= our script component),
            CameraPawnClass, bUseOverrideLocations / OverrideStartAngleDeg / OverrideEndAngleDeg
            GeneratePlanePoints(OutStart, OutEnd, CircleRadius=42000, Height=21000, MaxEndOffsetDeg=50)
 3 [native]  ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane(PS)
            -> ULokiPlayerDropPlaneComponent::AuthEnterDropPlane(Plane) -> ALokiDropPlane::AddPlayerToPlane(PS)
            (plane's own ULokiRideableComponent::AuthAddPlayer / AuthPlayerPreSpawnOnAddToPlane)
 4 [native]  ALokiDropPlane::AuthStart(StartTime); UpdatePlaneMovementAndCheckDone() each tick
 5 [native]  ULokiPlayerDropPlaneComponent::OnSelectDropLocationStarted()   (BlueprintEvent)
   [script]  -> bCanSelectDropLocation = true; SetComponentTickEnabled(true)
 6 [script]  Tick -> UpdateDropLocationCursor(): ALokiHeightMap::GetInstance(), cursor via
            ALokiPlayerController::GetCursorLocation(Default) -> Gameplay::DeprojectScreenToWorld
            -> heightmap GetTerrainPercentInRadius(hit, 1000) / IsTerrainInRadius(hit, 1000, 0.5f)
            (the script computes the validity numbers; the ring widget consumes them)
 7 [native]  SetDropPodDestination(Location) -> ServerSetDropPodDestination(Destination)
            TryLaunchDropPod() / ServerLaunchDropPod()  (CanLaunchDropPod(), IsValidDropPodDestination,
            IsWithinMaxDropPodDistance, IsReadyToSetDropPodDestination)
 8 [native]  ALokiDropPlane::AuthLaunchDropPodForTeam(FDropPodParams{Destination, RemainingDropDelay,
            TeamIndex}, bValidateLocation)  ->  BP_AuthLaunchDropPodForTeam (BlueprintEvent)
 9 [script]  ALokiDropShip::SpawnDropPodForTeam(TeamIndex, SpawnLocation, LandingLocation)   §2.1
            -> InitializeDropPod(...) -> rideable.AuthPlayerEnterWorldAttachedToRidable(leader, landing)
            -> RemovePlayerFromPlane(leader)
            -> ULokiPlayerDropPlaneComponent::MulticastOnDropPodLaunched(pod)      ← reaches the CLIENT
10 [script]  InitializeDropPod: CurrPodDestination = LandingLocation; SetPilotPlayerState(PS);
            bIsTeamLeaderPod = true; PodTeamIndex = TeamIndex; LeaderPod = ParentPod(null for leader);
            SetOwner(PilotPlayerState);  if leader -> QueueCrewForPodSpawn(DropShip)
11 [script]  QueueCrewForPodSpawn: every PS on the team with !IsSpawnTeamLeader() is queued and
            RemovePlayerFromPlane'd; SpawnCrewPodQueue() -> SpawnCrewPod(PS) per player:
            spawn CrewDropPodClass at (CurrPodDestination.XY, leaderPod.Z),
            InitializeDropPod(team, PS, CurrPodDestination, bIsTeamLeader=false, null, this),
            AuthPlayerEnterWorldAttachedToRidable(PS, dest), MulticastOnDropPodLaunched(crewPod),
            leader.AttachedCrewPods.Add(crewPod)
12 [script]  pod LokiBeginPlay (BOTH sides):
              server: LokiTeam::SetTeamForActor(this, PodTeamIndex)
              if (ULokiTeamComponent::Get(this).GetTeamIndex() >= 0) StartPodGameplay()
              else                                    TeamComp.OnTeamIndexChanged += OnPodTeamIndexChanged
                                                       (which calls StartPodGameplay when it goes >= 0)
13 [script]  StartPodGameplay()  — the real client-side start:
              guard bHasStartedGameplay
              client: bIsLocalPlayerPilot = (GetPilotPlayerState() == Loki::GetLocalLokiPlayerState())
                      if local pilot -> ULokiTrainingManager::SetActive(false)
              PodMeshComponent = USkeletalMeshComponent::Get(this)
              UProjectileMovementComponent::Get(this).Deactivate()
              server && leader -> SpawnImpactIndicator(LokiTeam::GetTeamFromActor(this))
              UCapsuleComponent::Get(this).OnComponentHit += OnDropPodHit
              client && GetLocalTeamIndex() != PodTeamIndex -> SetActorHiddenInGame(true)
              SetTimer(this, "OnIntroSequenceFinished", 6.5s)
              SetDropPodState(IntroSequence)
              !leader -> PreparePodForAttach(); SetCrewPodDetachState(Attached)
              BP_StartPodGameplay()          (BP hook "OnStartPodGameplay")
14 [script]  OnIntroSequenceFinished() @ +6.5s
              leader&&server: ImpactIndicator.SetActorHiddenInGame(false)
              local pilot (either branch): SpawnLaserIndicator(team)
              state = Descending, EXCEPT (!leader && CrewDetachEvent.DetachState != FinishDetaching) -> Attached
              AllowPodSteeringStarted()  -> leader: bPilotHasPodControl = true; bSteeringEnabled = true;
                                            SteeringStartTime = now; StartPlayerPodSteering() [native]
              client && GetLocalTeamIndex() != PodTeamIndex -> SetActorHiddenInGame(false)
              SetTimer(this, "OnOutroSequenceStart", TotalTimeForPodControls = 5.5s)
15 [script]  SetDropPodState(Descending) -> StartPodMovement():
              dir = normalize(CurrPodDestination - ActorLocation)
              ProjectileMovement.Activate(); Velocity = dir * InitialDropPodSpeed (2500)
             SetDropPodState always (server only) fills PodStateEvent{DropPod=this, DropPodState,
             PodPilot=GetPilotPlayerState(), bIsLeaderPod} and calls
             LokiDropPhase::BroadcastDropPodStateChangeEvent(this, PodStateEvent);
             the client replays the identical broadcast from OnRep_PodStateEvent.
16 [script]  Tick (both sides, gated on bHasStartedGameplay):
              client seeing an ENEMY pod -> SetActorTickEnabled(false) and stop
              if (DetachingFromLeaderPodStartTime > 0 && DetachState in {StartDetaching, FinishDetaching})
                   UpdateDetachingPodFromLeader()
              if (bIsHidingDropPhaseHiddenActors) UpdateDropPhaseHiddenActors()
              UpdatePodMovement(CurrentInputDirection, DeltaSeconds)
              UpdateCharacterLocations()
              UpdateAttachedPodLaserIndicator()
17 [script]  OnOutroSequenceStart() @ +12.0s: bReadyForOutro = true; state = OutroSequence;
              OnPodOutroStarted.Broadcast(); DestroyLaserIndicator();
              SetTimer("OnOutroSequenceFinished", 1.0s)
18 [script]  UpdateCharacterLocations() (runs only while state == OutroSequence):
              landing = rideable.GetLandingTeleportLocation(pilotCharacter, landingActor)
              landingActor = this, or LeaderPod when this is a crew pod still associated with it
              SetCharacterLanding(char, landing): teleport to landing + GetDropAboveAmount() [native]
                                                  then SetActorLocation(landing, bSweep=true)
              …repeated for every AttachedCrewPods pilot
19 [script]  OnOutroSequenceFinished() @ +13.0s -> AllowPodSteeringEnded() (bPilotHasPodControl=false,
              StopPlayerPodSteering() [native]) -> StartDestroyPod()
20 [script]  StartDestroyPod(): bPodIsDestroying = true; SetActorHiddenInGame(true);
              ProjectileMovement.StopMovementImmediately();
              premature = (PodStateEvent.DropPodState != OutroSequence)
              server -> DestroyImpactIndicator(); DestroyLaserIndicator(); KickPlayersFromPod();
              state = Destroying; TransitionCameraToPlayer();
              SetTimer("FinishDestroyPod", 1.5s);  if premature -> BP_OnPrematurePodDestruction()
21 [script]  KickPlayersFromPod() (server): for each rideable.PlayersInside —
              if in PlayersAttached -> AuthPlayerDetachPlayerFromRidable(PS, landingActor)
              else -> AuthPlayerEnterWorld(PS, ActorLocation + RandRange(-150,150) on X and Y, Z = 0,
                                           effect = null, bReposition = false)
                      then AuthPlayerDetachPlayerFromRidable(PS, landingActor)
22 [script]  FinishDestroyPod() -> DestroyActor()
```

`OnDropPodHit` (capsule hit) short-circuits straight to `StartDestroyPod()` at any point — that is
how a pod that reaches the ground early ends.

### 3.3 Steering / movement (`ALokiDropPod::UpdatePodMovement`)

```
bail if bPodIsDestroying or no ProjectileMovementComponent
bail unless state ∈ {Descending, OutroSequence}
hasControl = bPilotHasPodControl && state ∈ {Descending, OutroSequence}
window     = TotalTimeForPodControls + OutroSequenceTotalTime          // 5.5 + 1.0 = 6.5 s
dirVec     = ConvertDirectionToVector(MoveDirection)
hasControl && MoveDirection != LastInputDirection -> LastInputDirection = MoveDirection;
                                                     BroadcastDirectionEvent(LastInputDirection, dirVec)
!hasControl && state == OutroSequence && LastInputDirection != None -> LastInputDirection = None;
                                                     BroadcastDirectionEvent(None, ZeroVector)
steerDist  = bIsTeamLeaderPod ? MaxSteerDistance : MaxNonLeaderSteerDistance      // 7500
if (hasControl && MoveDirection != None)
     CurrPodDestination += dirVec * (steerDist / window) * DeltaSeconds           // ≈1154 uu/s
// snap the destination to the ground
z = CurrPodDestination.Z
if (!ALokiHeightMap::GetInstance().GetHeight(z, CurrPodDestination.X, CurrPodDestination.Y))
     LokiProjection::SimpleProjectToGround(CurrPodDestination, out hit, 1000.0f, z + 2000.0f, this)
        -> z = hit.Z
CurrPodDestination.Z = z
target   = CurrPodDestination + UCapsuleComponent::Get(this).GetScaledCapsuleHalfHeight()
remaining= window - (WorldTime - SteeringStartTime)
Velocity = normalize(target - ActorLocation) * (Distance(target, ActorLocation) / remaining)
ImpactIndicator?.SetActorLocation(CurrPodDestination)
   + if local pilot: ImpactIndicator.SetLandingRangeRadius((steerDist / window) * remaining)
UpdateGroundLaserAtLocation(CurrPodDestination, this)
```

So the descent is a *time-parameterised interpolation*, not a physics fall: the pod's velocity is
recomputed every tick so that it arrives exactly when the 6.5 s control window elapses. The impact
indicator's ring radius is the *remaining steerable distance*, which is why it shrinks as you fall.

Direction encoding, both halves (`CalculateDetachDirection` in the component and
`ConvertDirectionToVector` on the pod) — note **Up = −Y**, i.e. screen-space top-down:

| forward | right | enum | vector (pre-normalise) |
|---|---|---|---|
| >0 | ==0 | 1 `Up` | (0, −1, 0) |
| >0 | >0 | 2 `UpRight` | (+0.5, −0.5, 0) |
| >0 | <0 | 8 `UpLeft` | (−0.5, −0.5, 0) |
| ==0 | >0 | 3 `Right` | (+1, 0, 0) |
| ==0 | <0 | 7 `Left` | (−1, 0, 0) |
| <0 | ==0 | 5 `Down` | (0, +1, 0) |
| <0 | >0 | 4 `DownRight` | (+0.5, +0.5, 0) |
| <0 | <0 | 6 `DownLeft` | (−0.5, +0.5, 0) |

### 3.4 The crew-pod detach sub-machine (the "hold a direction to break away" mechanic)

Client, in `ULokiDropPhase_PlayerStateComponent`:

```
OnDropPodStarted_Implementation(PodActor):
    DropPodActor = cast<ALokiDropPod>(PodActor)
    not local client -> return
    if (DropPodActor.GetPilotPlayerState() == null) SetTimerForNextTick("OnDropPodStartedWithPilot")
    else OnDropPodStartedWithPilot()

OnDropPodStartedWithPilot():
    if (!DropPodActor.bIsTeamLeaderPod && DropPodActor.bIsLocalPlayerPilot)
        // arm the detach exactly PodDetachFromLeaderMaxTime before the pod separation would run out
        delay = DropPodActor.IntroSequenceTotalTime      // 6.5
              - DropPodActor.PodDetachTotalTime          // 1.0
              - PodDetachFromLeaderMaxTime               // 2.0     => 3.5 s
        SetTimer(this, "OnAllowPodDetach", delay)
    else bIgnoreInput = false

OnAllowPodDetach():                                       // ← +3.5 s after the pod starts
    pod = cast<ALokiDropPod>(this.DropPod)                // NATIVE DropPod property
    bPodDetachingEnabled = true; bIgnoreInput = false
    DetachInputStartTime = WorldTime
    pod.SetCrewPodDetachState(Detachable, 0, None, ZeroVector)

OnPodSteeringEnabled(Event, EventType):                   // FGameEvent_PodSteeringEnabled
    bail if !IsLocalClient() || bDropPhaseControlsDisabled
    EventType == Cleared -> bPodSteeringEnabled = false; bPodDetachingEnabled = false; return
    bPodSteeringEnabled = true; bPodDetachingEnabled = true
    bPodIsAttachedToLeader = bPodIsAttachedToLeader && !(ownerPlayerState.IsSpawnTeamLeader())
    TryStartSteering()

OnForwardMovementInput / OnRightMovementInput -> store axis -> ProcessMovement()
ProcessMovement():
    bail if bDropPhaseControlsDisabled || bIgnoreInput
    bail if either axis is still INVALID_MOVEMENT_VALUE (-1000)   // waits for BOTH axes
    dir = CalculateDetachDirection(fwd, right)
    if (UpdatePodControl(dir) && !bPodIsAttachedToLeader) UpdatePodMovement(dir)
    reset both axes to INVALID

UpdatePodControl(dir):
    !bPodIsAttachedToLeader -> return HasDropPodControl()
    pod = cast<ALokiDropPod>(this.DropPod); null -> false
    dir == None:
        if (CrewPodDetachStartTime > 0) { CrewPodDetachStartTime = 0;
             pod.SetCrewPodDetachState(DetachInputStopped, 0, None, ZeroVector) }
        return false
    else:
        if (CrewPodDetachStartTime <= 0) { CrewPodDetachStartTime = WorldTime;
             pod.SetCrewPodDetachState(DetachInputStarted, 0, None, ZeroVector);
             CurrTotalTimeForDetach = GetInputTimeForDetach() }
        pct = (WorldTime - CrewPodDetachStartTime) / CurrTotalTimeForDetach
        pct >= 1 -> DetachPodFromLeader(dir); TryStartSteering(); return HasDropPodControl()
        else     -> pod.SetCrewPodDetachState(DetachInputContinue, pct, dir, ZeroVector); return false

GetInputTimeForDetach():        // the hold shrinks as the window closes
    elapsed = WorldTime - DetachInputStartTime
    elapsed >= PodDetachFromLeaderMaxTime (2.0) -> PodDetachFromLeaderMinTime (0.5)
    else -> Max(PodDetachFromLeaderMaxTime - elapsed, PodDetachFromLeaderMinTime)

DetachPodFromLeader(dir):
    bail if !bPodDetachingEnabled
    bPodIsAttachedToLeader = false
    pod.DetachPodFromLeader(dir)               // local, immediate
    ServerDetachPodFromLeader(dir)             // NetServer RPC — server does the same

HasDropPodControl() const:
    bPodSteeringEnabled && !bPodIsAttachedToLeader && DropPodActor.IsPlayerStatePilot(ownerPS)

UpdatePodMovement(dir):        // steering, once detached
    if (dir != CurrMoveDirection) {
        DropPodActor.CurrentInputDirection = dir      // replicated property, written client-side
        ServerUpdatePodMovement(dir)                  // NetServer RPC — authoritative copy
        CurrMoveDirection = dir }
```

Server/pod side, `ALokiDropPod::StartDetachingPodFromLeader(dir)` (server only):

```
// fan out pods that chose the same direction: first gets +22.5°, later ones -22.5°
yaw = 0; for (p in LeaderPod.AllDetachedCrewPods) if (p.PodDetachData.MoveDirection == dir)
            yaw = (yaw == 0) ? 22.5 : -22.5
LeaderPod.DetachingCrewPods.AddUnique(this); LeaderPod.AllDetachedCrewPods.AddUnique(this)
v = normalize(ConvertDirectionToVector(dir)).RotateAngleAxis(yaw, (0,0,-1))
start = LeaderPod.ActorLocation
PodDetachData = { PodDetachStartLocation: start, LeaderDetachStartLocation: start,
                  PodDetachDirection: v, MoveDirection: dir }      // ← replicated, RepNotify
SetActorLocation(start); SetActorRotation(LeaderPod.ActorRotation)
InitializeDetachingPodFromLeader()
SpawnImpactIndicator(LokiTeam::GetTeamFromActor(this))
```

`OnRep_PodDetachData` on the client mirrors that: if `DetachingFromLeaderPodStartTime <= 0` and
`CrewDetachEvent.DetachState != FinishDetaching`, it teleports to `PodDetachStartLocation`, copies
the leader's rotation, and calls `InitializeDetachingPodFromLeader()`.

`InitializeDetachingPodFromLeader()` records `DetachingFromLeaderPodStartTime = WorldTime`, sets
`SetCrewPodDetachState(StartDetaching, pct, dir, PodDetachDirection)`, and — on the **server**, or
on a client whose `LeaderPod` handle is null — also drives the leader's state
(`SetLeaderPodDetachState(DetachingCrewPods.Num() == 1 ? StartDetaching : AdditionalStartDetaching, …)`)
and broadcasts `OnCrewPodDetached` and `LeaderPod.OnLeaderPodHasCrewPodDetached`. Then
`PreparePodForDetach()` re-activates the pod mesh, unhides the actor and glues the local camera to
the crew pod.

`UpdateDetachingPodFromLeader()` (every tick while detaching) interpolates over `PodDetachTotalTime`
(1 s): the pod's world position tracks the leader plus `PodDetachDirection * PodDetachTotalDistance
* alpha` (1000 uu), while its *destination* moves out by half that; the destination Z is re-snapped
to the height map, and at `alpha >= 1` it sets `DetachingFromLeaderPodStartTime = -1` and calls
`FinishDetachingPodFromLeader()` → removes itself from `LeaderPod.DetachingCrewPods` and
`AttachedCrewPods`, unhides its impact indicator and re-enables collision (server),
`bPilotHasPodControl = true`, `SetCrewPodDetachState(FinishDetaching, …)`,
`LeaderPod.SetLeaderPodDetachState(remaining > 0 ? OneOfManyPodsFinishedDetaching :
AllDetachingPodsFinished)`, and finally `SetDropPodState(Descending)` — which is what starts its own
`StartPodMovement()`.

### 3.5 The replication contract of the four "event" structs

`SetCrewPodDetachState` has a **side-exclusion gate** that is easy to misread. Written out:

```
isClient  = Loki::LokiIsClient()
isInputSt = NewDetachState ∈ {DetachInputStarted, DetachInputStopped, DetachInputContinue, Detachable}
bail if ( isInputSt && !isClient ) || ( !isInputSt && isClient )
```
i.e. **the four input/arming states are client-authored only, and every other state
(Attached / StartDetaching / FinishDetaching) is server-authored only.** After the gate it fills
`CrewDetachEvent{DetachingCrewPod = this, LeaderPod, DetachState, PodPilot, InputProgressPercent,
InputDirection, Direction}` and calls `LokiDropPhase::BroadcastDropPodCrewDetachEvent`. Because
`CrewDetachEvent` is a replicated property with `OnRep_CrewDetachEvent`, the server-authored half
reaches other clients purely as a property replication that re-broadcasts the same game event; the
client-authored half is **local only** (no RPC carries it) and exists to drive local UI/VFX
(`WBP_UI_DropPodControls`) while you hold the key.

`SetLeaderPodDetachState` has no such gate but is only ever called from server-side paths.

---

## 4. Replicated vs local — the exact list

**Server → client, as actor property replication:**

- `ALokiDropPodBase::PilotPlayerState` [native] → notify `OnPilotPlayerStateReplicated` → script
  recomputes `bIsLocalPlayerPilot` and retries any deferred camera glue.
- `ALokiDropPod`: `bIsTeamLeaderPod`, `PodTeamIndex`, `ImpactIndicator`, `CurrPodDestination`,
  `AttachedCrewPods`, `LeaderPod`→`OnRep_LeaderPod`, `DetachingCrewPods`,
  `PodDetachData`→`OnRep_PodDetachData`, `PodStateEvent`→`OnRep_PodStateEvent`,
  `CrewDetachEvent`→`OnRep_CrewDetachEvent`, `LeaderDetachEvent`→`OnRep_LeaderDetachEvent`,
  `CurrentInputDirection`.
- `ALokiDropPodImpactIndicator`: `OwningDropPod`→`OnRep_OwningDropPod`, `OwningPlayerState`.
- `ALokiDropPodLaser`: `OwningDropPod`.
- The pod's `ULokiTeamComponent` team index (native) — **load-bearing, see §6**.

**Client → server, as RPCs (only two, both on the player-state component):**

```
UFUNCTION(NetServer) void ServerDetachPodFromLeader(const ELokiMovementInputDirection MoveDirection)
UFUNCTION(NetServer) void ServerUpdatePodMovement (const ELokiMovementInputDirection MoveDirection)
```
plus the native `ServerSetDropPodDestination(const FVector&)`, `ServerLaunchDropPod()`,
`ServerPassDropLeader()` on the same component and
`ALokiPlayerController::ServerOverrideDropPlaneLocations(FVector, FVector)`.

**Multicast:** `ULokiPlayerDropPlaneComponent::MulticastOnDropPodLaunched(AActor NewDropPod)` [native]
— fired by the script at pod spawn; this is the one message that tells every client "your pod
exists". Also `ULokiRideableComponent::MulticastOnPlayerEntered / MulticastOnPlayerEnteredWorld /
MulticastOnPlayerExited`.

**Purely local (never leaves the machine that computed it):** everything in
`ULokiDropPhase_PlayerStateComponent` (it declares no `UPROPERTY` at all), plus the pod's
`bIsLocalPlayerPilot`, `bPilotHasPodControl`, `bSteeringEnabled`, `SteeringStartTime`,
`bHasStartedGameplay`, `GroundLaserIndicator`, `bIsHidingDropPhaseHiddenActors`, `LastInputDirection`.

---

## 5. The native surface the script sits on (recovered from `Binds.Cache`)

The script layer is the **leaf**, not the driver. Nothing outside these seven modules references the
drop phase — all 78 script modules were grepped. The rest is C++, and these are its exact
declarations (names, params, defaults are verbatim from the bind table; bodies are not available):

```
ALokiDropPlane                      /Script/Loki.LokiDropPlane
  props  FOnPlaneStarted OnPlaneStarted; FOnReachedEnd OnReachedEnd;
         ULokiRideableComponent RideableComponent; TArray<FDropPodParams> QueuedDropPodParams;
         FVector StartLocation, EndLocation; float32 MaxDropPodDistance, MaxGroundHitNormalAngle,
         StartTimeSecs, Speed, HeightMapRadiusCheck; TArray<UPhysicalMaterial> DisallowedPhysicalMaterials
  fns    void AuthStart(float32 StartTime)
         void AuthLaunchDropPodForTeam(FDropPodParams DropPodParams, bool bValidateLocation)
         void BP_AuthLaunchDropPodForTeam(FDropPodParams DropPodParams)
         void AddPlayerToPlane(ALokiPlayerState) / RemovePlayerFromPlane(ALokiPlayerState)
         bool IsPlayerInPlane(…) / HasEverContainedPlayer(…)
         EPlayerDropState GetPlayerDropState(ALokiPlayerState) const
         bool IsReadyToSetDropPodDestination()
         bool IsValidDropPodDestination(const FVector&, const bool bIgnoreDistanceToPlaneCheck)
         bool IsWithinMaxDropPodDistance(const FVector&)
         void IsWithinDropPlanePath(const FVector&, bool& bIsInPath, bool& bIsValidTerrain)
         void GetDropPosition(FVector& Out) const
         void GetDropZoneBorders(FVector&, FVector&, FVector&, FVector&)
         void OverridePlaneLocations(FVector Start, FVector End)
         void OnTeamDropped(FVector Destination, int TeamIndex)
         bool UpdatePlaneMovementAndCheckDone();  bool CanJump() const;  void SetCanJump(bool)
         UMapIconComponent GetDropPlaneMapIcon();  void OnRep_StartLocation() / OnRep_EndLocation()
  FDropPodParams { FVector Destination; float32 RemainingDropDelay; int TeamIndex; }

ALokiDropPodBase                    /Script/Loki.LokiDropPodBase
  ALokiPlayerState PilotPlayerState (UProperty)
  float32 GetDropAboveAmount();  void SetPilotPlayerState(ALokiPlayerState)
  void OnPilotPlayerStateReplicated();  void StartPlayerPodSteering() / StopPlayerPodSteering()

ULokiPlayerDropPlaneComponent       /Script/Loki.LokiPlayerDropPlaneComponent
  props  bool bDropLocationSelected; ULokiRideableComponent CurrentRideableObject;
         FOnCurrentRideableObjectChanged OnCurrentRideableObjectChanged;
         TArray<float32> ValidDropPodLocationSearchRadiuses;
         ALokiDropPlane DropPlane;  AActor DropPod
  fns    void AuthEnterDropPlane(ALokiDropPlane Plane)
         bool CanLaunchDropPod() const;  bool TryLaunchDropPod();  void ServerLaunchDropPod()
         void SetDropPodDestination(const FVector&);  void ServerSetDropPodDestination(const FVector&)
         bool GetSelectedDropPodDestination(FVector&) const;  void ClearSelectedDropPodDestination()
         bool FindValidDropLocationInRadius(const FVector& Origin, float32 MaxDist, FVector& Result)
         void ServerPassDropLeader();  bool GetDropComplete()
         void MulticastOnDropPodLaunched(AActor NewDropPod)
         void OnDropPodLaunched(AActor NewDropPod)          [UFunction BP_OnDropPodLaunched]
         void OnDropPodStarted(AActor PodActor) / OnDropPodEnded()
         void OnSelectDropLocationStarted() / OnSelectDropLocationEnded()
         void OnForwardMovementInput(float32) / OnRightMovementInput(float32)
         void OnEventRouterReady(UGameEventRouterComponent Router)

ULokiGameModeDropPlaneComponent     /Script/Loki.LokiGameModeDropPlaneComponent
  props  ALokiRoundGameMode LokiGameMode;  ALokiDropPlane LokiDropPlane;
         TSubclassOf<ULokiPlayerDropPlaneComponent> PlayerStatePlaneComponentClass;
         TSubclassOf<APawn> CameraPawnClass;
         bool bUseOverrideLocations; float32 OverrideStartAngleDeg, OverrideEndAngleDeg;
         FOnPlaneDropLocationsChanged OnPlaneDropLocationChanged
  fns    ALokiDropPlane SpawnPlane();  void SetDropPlane(ALokiDropPlane)
         void AddPlayerToDropPlane(ALokiPlayerState) const
         void GeneratePlanePoints(FVector& OutStart, FVector& OutEnd, float32 CircleRadius = 42000,
                                  float32 Height = 21000, float32 MaxEndOffsetDeg = 50) const

ULokiRideableComponent              /Script/Loki.LokiRideableComponent
  props  bool bCanExit; int PlayersInsideCount; TArray<ALokiPlayerState> PlayersInside, PlayersAttached;
         TSet<ALokiPlayerState> PlayersThatExited; TSubclassOf<UGameplayEffect> InsideEffect; …
  fns    void AuthAddPlayer / AuthRemovePlayer(ALokiPlayerState)
         void AuthPlayerPreSpawnOnAddToPlane(ALokiPlayerState)
         void AuthPlayerEnterWorld(ALokiPlayerState, const FVector&, TSubclassOf<UGameplayEffect> = nullptr,
                                   bool bRepositionPlayer = false)
         void AuthPlayerEnterWorldAttachedToRidable(ALokiPlayerState, const FVector& SpawnLocation)
         void AuthPlayerEnterWorldNew(ALokiPlayerState, const FVector&)
         void AuthPlayerDetachPlayerFromRidable(ALokiPlayerState, const AActor LandingLocationActor)
         FVector GetLandingTeleportLocation(const ALokiCharacter, const AActor LandingLocationActor)
         void GetRidePosition(FVector&) const;  void AuthSetCanJump(bool);  bool CanExit() const

ULokiDropPhaseLibrary               /Script/Loki.LokiDropPhaseLibrary   (all static)
  void BroadcastDropPodStateChangeEvent (ALokiDropPodBase, const FGameEvent_OnDropPodStateChanged_PlayerState&)
  void BroadcastDropPodCrewDetachEvent  (ALokiDropPodBase, const FGameEvent_CrewDropPodDetach_PlayerState&)
  void BroadcastDropPodLeaderDetachEvent(ALokiDropPodBase, const FGameEvent_LeaderDropPodDetach_PlayerState&)
  void BroadcastDropPodDirectionChangeEvent(ALokiDropPodBase, const FGameEvent_PodMoveDirectionChanged_PlayerState&)

ALokiPlayerController               /Script/Loki.LokiPlayerController
  props  FOnClientGameFeatureTogglesReady OnClientGameFeatureTogglesReady;
         FOnAnyClientGameFeatureTogglesReadyOrChanged OnAnyClientGameFeatureTogglesReadyOrChanged;
         FIsInDropPodChanged OnIsInDropPod;  FOnParachuteEnded OnDropPodEnded;
         FOnPlaneDropComponent OnPlaneDropComponent;  float64 HideDuringDropHeight
  fns    void DropPlaneComponentSetup();  void FinishDropPhaseHiding()
         void HideActorUntilDropIsCloseToGround(AActor TargetActor)
         void ServerOverrideDropPlaneLocations(FVector Start, FVector End)
         bool IsUIReady_BP(UObject = __WorldContext);  void UIReadySplit(UObject, EUIReady& OutputExecs)

ALokiPlayerState  : void AuthSetSpawnTeamLeader();  bool IsSpawnTeamLeader() const;
                    void ServerSetReadyToPlay();  void HandleSpawnLocationRequest(FVector, bool bIsFromLeader);
                    FVector DesiredSpawnLocation;  FOnIsDropLeaderChanged OnIsDropLeaderChanged
ALokiTeamState_TeamOnly : ALokiPlayerState GetDropLeader() const; void SetDropLeader(ALokiPlayerState)
UCoreGameManager  : bool TryPassDropLeader(FOnOperationComplete OnComplete = …)
ALokiHeroCharacter: bool HeroPredropHidden;  void OnRep_HeroPredropHidden()  [UFunction BP_OnRep_…]
ULokiCharacterMovementComponent :
      void AuthBeginGlideDiveFromDropPod(const FVector& DropPodDirection, int RiderIndex = -1,
                                         float32 LaunchOverrideSpeed = -1.0)
      void AuthBeginGlideDive();  void EndGlideDive();  uint8 GetDropPlaneCustomMovementMode()   [static]
      + GlideDivePodLaunchSpeed / GlideDivePodDeflectionAngleMin|Max / GlideDivePodYawAngleRandom /
        GlideDiveDistanceMin|Max / GlideDiveDurationTimeout / GlideDiveTransitionCurve …
ULokiTransitionWidgetManager        /Script/Loki.LokiTransitionWidgetManager
      ULokiTransitionWidgetManager GetLokiTransitionWidgetManager(UObject = __WorldContext)  [static]
      void AsyncLoadMatchTransitionWidget();  void ClearMatchTransition()
ALokiRoundGameMode : bool ModeSupportsDropPlane(); void GoToPhase(ERoundPhase); float32 GetLineupPhaseDuration()
ALokiGameState     : void AuthSetCurrentPhase(ERoundPhase); ERoundPhase GetCurrentPhase() const; void OnRep_CurrentPhase()
```

---

## 6. What this means for the project

### 6.1 The overlay ("DROP IN, GEAR UP… LOADING…") is not gated by the drop-phase script

S89 left the client sitting behind the match-transition overlay with the *whole drop-in world loaded
behind it*. Nothing in the decompiled drop-phase script draws, holds, or dismisses that overlay —
the seven modules contain no widget code at all. Two concrete, named native handles do exist:

1. **`ULokiTransitionWidgetManager::ClearMatchTransition()`**, reachable statically via
   `ULokiTransitionWidgetManager::GetLokiTransitionWidgetManager(WorldContext)`. Both are bound
   `UFUNCTION`s, so both are callable with the existing game-thread native-call primitive
   (`ProcessInternal` @ `base+0x13454A0` → `UFunction.Func`). *This is a name-and-signature finding —
   I have no body for it — but a manager class whose entire public surface is
   `AsyncLoadMatchTransitionWidget` / `ClearMatchTransition` is exactly the thing that owns
   `WBP_UI_MatchTransition`.* Trying this is cheap and directly targets the S90 wall.
2. **`ALokiPlayerController::OnClientGameFeatureTogglesReady`** — S89/S90 correctly identified the
   *event* as the gate but treated it as an unlocated symbol. It is a **delegate property on
   `ALokiPlayerController`**, confirmed in `Binds.Cache`, sitting next to
   `OnAnyClientGameFeatureTogglesReadyOrChanged`. Its handler on the character side is
   `ALokiCharacter::FeatureTogglesReadyOrChanged()`. So the shim work is: find that property on the
   local PC and broadcast it (or call `ALokiCharacter::FeatureTogglesReadyOrChanged` directly on the
   local hero), instead of chasing the readiness *bit* that only flips the query.
   `ALokiPlayerController::IsUIReady_BP` / `UIReadySplit(EUIReady&)` (`0 Ready`, `1 NotReady`) is a
   second, separate readiness gate worth reading live.

### 6.2 The drop phase is fully drivable without any of the backend

Every step from "plane exists" to "hero on the ground" is a `UFUNCTION` on an actor in the level.
A minimal force-open path, in call order, all script or bound-native and therefore callable through
the existing primitive:

```
ALokiPlayerState::AuthSetSpawnTeamLeader()                    // ← REQUIRED, see 6.3
ULokiGameModeDropPlaneComponent::SpawnPlane()                 // or SetDropPlane(existing)
ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane(PS)
ALokiDropPlane::AuthStart(StartTime)
ALokiDropShip::SpawnDropPodForTeam(TeamIndex, SpawnLocation, LandingLocation)   ← script, does everything
      // internally: spawn pod, InitializeDropPod, FinishSpawningActor,
      //             AuthPlayerEnterWorldAttachedToRidable, RemovePlayerFromPlane,
      //             MulticastOnDropPodLaunched, QueueCrewForPodSpawn
```
or, skipping the plane entirely,
```
ALokiDropPod::InitializeDropPod(team, PS, LandingLocation, true, nullptr, nullptr)
ALokiDropPod::StartPodGameplay()                              // UFUNCTION(BlueprintCallable)
```
`StartPodGameplay` is `BlueprintCallable` and idempotent (`bHasStartedGameplay` guard). It arms all
four timers by name, so from that single call the pod runs the whole 6.5 + 5.5 + 1.0 + 1.5 s
sequence on its own. `SetDropPodState`, `OnIntroSequenceFinished`, `OnOutroSequenceStart`,
`OnOutroSequenceFinished`, `AllowPodSteeringStarted/Ended`, `SpawnImpactIndicator`,
`SpawnLaserIndicator`, `FinishDestroyPod`, `SpawnCrewPodQueue`, `QueueCrewForPodSpawn` are all
`UFUNCTION(BlueprintCallable)` too — the sequence can be *stepped manually* one call at a time.

### 6.3 The single most likely private-server failure mode, and it is one function call

`ALokiDropShip::GetTeamDropLeader(TeamIndex)` returns the first player state on the team with
`IsSpawnTeamLeader() == true`, **else nullptr**, and `SpawnDropPodForTeam` passes that straight into
`InitializeDropPod` as the pilot. With no drop leader:

- `SetPilotPlayerState(nullptr)` → `SetOwner(nullptr)` → the pod is owned by nobody, so it is not
  relevant/prioritised for the owning connection;
- client-side `bIsLocalPlayerPilot` is never true → **no camera glue, no laser indicator, no landing
  radius, no `ULokiTrainingManager::SetActive(false)`**;
- `UpdateCharacterLocations()` finds no pilot character → **the hero is never teleported to the
  landing point**;
- `KickPlayersFromPod()` still runs, but `AuthPlayerDetachPlayerFromRidable` has nothing to release.

The drop leader is set by **`ALokiPlayerState::AuthSetSpawnTeamLeader()`** (server), mirrored on
`ALokiTeamState_TeamOnly::SetDropLeader/GetDropLeader` and passed around by
`ULokiPlayerDropPlaneComponent::ServerPassDropLeader()` / `UCoreGameManager::TryPassDropLeader`.
If the revival's game mode never elects one, the drop visually "half-works" in exactly the way a
loading-screen bug looks. **Call `AuthSetSpawnTeamLeader()` on the local player state before
spawning the pod.**

### 6.4 Why the world/hero is invisible during a drop, and what un-hides it

The hero is *deliberately* hidden for the whole descent: `ALokiHeroCharacter::HeroPredropHidden`
(replicated, `OnRep_HeroPredropHidden`), `ALokiPlayerController::HideActorUntilDropIsCloseToGround`,
`HideDuringDropHeight`, `EDropHidingStatus{Hiding, FinishRequested, Finished}`. The release is
**client-side and lives in the decompiled script**:

```
ALokiDropPod::UpdateDropPhaseHiddenActors()      // called every Tick while bIsHidingDropPhaseHiddenActors
    client only
    camZ = UCameraComponent::Get(this).GetWorldLocation().Z
    if (camZ <= DisplayDropPhaseHiddenActorsHeight /* 10000 */) {
        bIsHidingDropPhaseHiddenActors = false
        for (PS in ULokiRideableComponent::Get(this).PlayersInside)
            cast<ALokiPlayerController>(PS.GetPlayerController())?.FinishDropPhaseHiding()
    }
```

Three ways this never fires, all of which look like "the game is stuck":
`bHasStartedGameplay` false (the `Tick` early-outs), the pod having no `UCameraComponent`, or the
pod never descending below Z = 10000. And it only ever runs for players the **rideable component**
says are `PlayersInside` — so a hero that was teleported into the world without going through
`AuthPlayerEnterWorldAttachedToRidable` is never un-hidden. **`ALokiPlayerController::FinishDropPhaseHiding()`
is a direct, no-argument `UFUNCTION`** — a shim can call it on the local PC and skip the whole chain.

### 6.5 Other immediately usable facts

- **The plane's path does not need level markers.** `ULokiGameModeDropPlaneComponent` carries
  `bUseOverrideLocations` + `OverrideStartAngleDeg/EndAngleDeg`, `GeneratePlanePoints` takes an
  explicit `CircleRadius = 42000, Height = 21000, MaxEndOffsetDeg = 50`, and there are three separate
  override entry points: `ALokiDropPlane::OverridePlaneLocations(Start, End)`,
  `ALokiPlayerController::ServerOverrideDropPlaneLocations(Start, End)` and the static
  `ULokiDropPhaseDebuggingTool::OverrideDropPlaneLocations(WorldContext, Start, End)`. The S93
  "SpawnPlane faults on absent level markers" wall has a documented bypass.
- **The script component must be wired in.** `ULokiGameModeDropPlaneComponent::PlayerStatePlaneComponentClass`
  is what attaches `ULokiDropPhase_PlayerStateComponent` to each player state. If that class is unset
  (or the tutorial's `Comp_GameMode_DropPlane_Tutorial_C` sets something else), none of the client
  drop controls exist, regardless of what the pod does.
- **There is a drop-phase camera pawn.** `ULokiGameModeDropPlaneComponent::CameraPawnClass`
  (`TSubclassOf<APawn>`). During the drop the player is expected to possess a *camera pawn*, not the
  hero — relevant to the long-running possession wall (S71/S90). (Property exists; its use is native
  and unproven here.)
- **The hero's exit from the pod is a movement-mode handoff**, not a spawn:
  `ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod(DropPodDirection, RiderIndex = -1,
  LaunchOverrideSpeed = -1)`, with a dedicated custom movement mode
  (`GetDropPlaneCustomMovementMode()`). That is the function that turns a pod passenger into a
  falling, controllable hero.
- **A pod is a pooled actor.** `LokiGameplay::SpawnPoolableActorFromClassDeferred` + explicit
  `FinishSpawningActor` — a shim that plain-`SpawnActor`s a pod class skips the deferred-init window
  that `InitializeDropPod` relies on.
- **The impact indicator, laser and pod all key off `LokiTeam`**: `SetTeamForActor`,
  `GetTeamFromActor`, and `ULokiTeamComponent::GetTeamIndex() >= 0` is the gate in `LokiBeginPlay`.
  On a client whose pod arrives with an unreplicated/negative team index, `StartPodGameplay` is
  deferred to `OnTeamIndexChanged` and **the entire drop silently never starts**. This is a
  first-class thing to check with `tools/re/obj_by_class.py` on any stuck client.
- **Tuning numbers for a reimplementation** (all decoded from the constructor bit patterns):
  intro 6.5 s, controls 5.5 s, outro 1.0 s, destroy delay 1.5 s, launch speed 2500 uu/s, steer budget
  7500 uu over a 6.5 s window (≈1154 uu/s), crew-pod separation 1000 uu over 1.0 s with ±22.5° fan-out,
  detach hold 2.0 s decaying to 0.5 s, un-hide height 10000, pod-kick scatter ±150 uu.

### 6.6 The two non-drop modules

- **`ALokiAirship_AS`** (abstract, extends native `ALokiAirship`) is a complete vehicle-combat model:
  head-on collision damage (angle ≤ 30°, relative speed 900→2000 mapped to 100→150 damage, front/rear
  multiplier 0.1→4.0 by impact angle over 0→180°, 1 s per-target cooldown), passenger ejection above
  600 uu/s relative speed (impulse 60000→600000 XY, +6000 Z), roadkill (500→5000 damage over 0→1000
  uu/s, ×0.8 vs minions, ×1.6 vs destructibles, `Immunity.AirshipRoadkill` tag exemption, 0.3 s
  cooldown, ally- and self-follow-checked), fuel burn (`NumSecondsOfFuel` 180 s, 60 s boosting,
  1 s tick, applied as a `Generic.Scale`-tagged gameplay effect), and health regen in three damage
  phases at 0.33 / 0.66 strength driving `Effect.Airdoo.Damaged.Smoking` / `.onFire` tags, healing up
  to 30 HP per 1 s tick. All server-authoritative.
- **`ULokiExoticLootComponent`** — on `BeginPlay` (server) it grabs
  `ALokiGameState::GetRandomStream(NonDeterministic)` and pre-generates, for each key in
  `TMap<int /*day*/, TSubclassOf<ULokiLootTable>> DayToLootTable`, a shuffled list of exotics
  (`ULokiLootTable::GenerateFromClassWithStream(table, RandomSeed, Num)`).
  `GetOneExoticForCurrentDay()` (BlueprintAuthorityOnly) pops index 0 for
  `ALokiGameState::GetCurrentDay()`, regenerating the day's list if it has run dry. Day/night cycle
  drives the exotic drops.

---

## 7. What I could NOT recover

- **Local variable names and line numbers.** Not in a shipping cache at any effort
  (`DeclaredAt == 0`, `LineNumbers == []` for all 1,463 functions). Locals are `vN`.
- **The bodies of every native function in §5.** `Binds.Cache` stores declarations only. Everything
  I say about `AuthLaunchDropPodForTeam`, `MulticastOnDropPodLaunched → OnDropPodStarted`,
  `ClearMatchTransition`, `CameraPawnClass`, `AuthBeginGlideDiveFromDropPod`,
  `FinishDropPhaseHiding`'s internals, and the plane's own movement is **signature-level inference**,
  explicitly flagged as such above. The script side is decompiled; the native side is named.
- **The Blueprint layer.** `BP_StartPodGameplay`, `BP_OnPrematurePodDestruction`,
  `OnDropPodReplicated`, `OnLandingRadiusChanged` are `NoOp` script stubs whose real bodies live in
  BP assets, as does `BP_AuthLaunchDropPodForTeam` (which is what actually calls
  `SpawnDropPodForTeam`). The exact BP that subclasses `ALokiDropShip` was not identified — the
  project's asset catalog has no `DropShip`/`DropPod` entries under those names, though the live
  client has been observed loading `Comp_GameMode_DropPlane_Tutorial_C`,
  `WBP_UI_DropPodControls`, `WBP_UI_DropPodIndicator_Animated` and `WBP_UI_DropPlane_SpinningDonut`.
- **Which `ERoundPhase` value actually opens the drop.** `EGP_SpawnSelect` (4) is the obvious
  candidate from the name and from `GetLineupPhaseDuration` / `EGP_Lineup` sitting after it, but no
  decompiled code in these modules reads `ERoundPhase`, so this is a naming inference only.
- **`GetTeamDropLeader`'s second loop.** Its body compiles to condition tests with no stores, so I
  can state what the shipped code *does* (nothing) but not what the author intended.
- **`FGameEvent_PodSteeringEnabled`'s payload** — the struct is bound but carries no properties, so
  it is a pure signal; what native code broadcasts it (presumably `StartPlayerPodSteering`) is not
  visible.
- **What `UpdateDropLocationCursor` was *for*.** The function itself is fully decoded and it is
  **dead code in the shipped build**: it deprojects the cursor, calls
  `GetTerrainPercentInRadius(worldPos, 1000.0)` and `IsTerrainInRadius(worldPos, 1000.0, 0.5f)`,
  stores both results into locals (`v62`, `v9`) and returns — the last two instructions are
  `CpyRtoV4 v9 ; RET 2`, with no store to any member and no further call. So the validity numbers the
  drop-location ring shows must come from the native side
  (`ALokiDropPlane::IsValidDropPodDestination` / `IsWithinDropPlanePath` /
  `ULokiPlayerDropPlaneComponent::FindValidDropLocationInRadius`), not from this tick. What the
  script *intended* to do with them is not recoverable.
