## LANE 3 — MOVEMENT DRIVER, TICK GATE, STATE, AND THE PRE-REGISTERED PREDICTION

All addresses below are RVAs in `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (ImageBase `0x7FF6505C0000`, file-offset == RVA). All AS line numbers are `tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt`.

---

### 0. CALIBRATION FIRST — Angelscript `ADDSi`/`LoadThisR` operands ARE byte offsets from the object pointer [M]

Two independent controls, both against UHT `FPropertyParams` records decoded by `scratchpad/s130/tools/propscan.py`:

| AS bytecode | UHT record | agreement |
|---|---|---|
| `ADDSi 1632 ; .OnComponentHit` on `UCapsuleComponent` (line 1057) | `0x07EBF650 OnComponentHit off=0x660` = **1632**, **1 hit image-wide** | exact |
| `ADDSi 232 ; .Velocity` on `UProjectileMovementComponent` (line 1725) | `0x07FC7A90 Velocity off=0xE8` = **232**, the only `Velocity` at 0xE8 of 31 records named `Velocity` | exact |

⇒ every offset I quote from the AS listing is a real byte offset on the live object. `LeaderPod` (a UPROPERTY, +1200) sits between `SteeringStartTime` (+1192, no UPROPERTY) and `bHasStartedGameplay` (+1208, no UPROPERTY), so reflected and non-reflected script members share one offset space [M]. Non-UPROPERTY members are RPM-readable but **not** reflection-resolvable by name — the probe must hardcode them.

---

### 1. WHAT MOVES A DROP POD

**The driver is `UProjectileMovementComponent`, and it is turned on in exactly one place.** [M]

```
StartPodGameplay()                        (line 896)
  ├ bHasStartedGameplay(+1208) = 1
  ├ PodMeshComponent(+1592) = USkeletalMeshComponent::Get(this)
  ├ UProjectileMovementComponent::Get(this).Deactivate()      <-- turns movement OFF
  ├ UCapsuleComponent::Get(this).OnComponentHit += OnDropPodHit
  ├ SetTimer(this,"OnIntroSequenceFinished", IntroSequenceTotalTime=6.5s, one-shot)
  ├ SetDropPodState(IntroSequence=1)          -> NOT Descending, so no movement
  ├ if (!bIsTeamLeaderPod) { PreparePodForAttach(); SetCrewPodDetachState(Attached); }
  └ BP_StartPodGameplay()                     (BP event; BP_DropPod_C implements it)

OnIntroSequenceFinished()                 (line 4046, fires 6.5 s later)
  ├ v7 = 3 (Descending); if (!bIsTeamLeaderPod && CrewDetachEvent.DetachState != FinishDetaching(7)) v7 = 2 (Attached)
  ├ SetDropPodState(v7)
  └ AllowPodSteeringStarted(); SetTimer("OnOutroSequenceStart", 5.5s)

SetDropPodState(N)                        (line 1420)
  └ if (N == Descending(3)) StartPodMovement();       <-- THE ONLY GATE

StartPodMovement()                        (line 1703)
  ├ dir = normalize(CurrPodDestination(+1144) - GetActorLocation())
  ├ UProjectileMovementComponent::Get(this).Activate(false)   <-- turns movement ON
  └ PMC.Velocity(+0xE8) = dir * InitialDropPodSpeed(+992)
```

Cooked PMC archetype (`bpdump BP_DropPod @props`, `ProjectileMovement_GEN_VARIABLE`): `InitialSpeed=20000`, `MaxSpeed=20000`, **`ProjectileGravityScale=0`** [M]. `InitialDropPodSpeed` = **2500.0** (AS ctor `SetV8 v2 0x40a3880000000000`, not overridden by either BP CDO) [M].

⇒ once started, the pod travels in a **straight line at a constant 2500 uu/s**, no gravity, no drag.

**★ The per-tick re-steer (`Tick` → `UpdatePodMovement`, line 5299) CANNOT run in this build.** It early-returns unless `PodStateEvent.DropPodState ∈ {3,4}`, and `SetDropPodState` writes that byte **only after** `if (LokiIsClient(...)) return;`. See §1a. So `PodStateEvent.DropPodState` (+1344) stays **0 (None)** forever and the velocity set by `StartPodMovement` is never overwritten. [M]

#### 1a. ★★★★★ THE LOAD-BEARING DISCOVERY: `LokiIsServer` IS A COMPILED `return false` AND `LokiIsClient` A COMPILED `return true` [M]

`scratchpad/s130/tools/recs.py` (name → `.data {name_ptr, exec_thunk, impl}` record → bytes at impl):

```
ULokiBlueprintLibrary::LokiIsServer   rec=0x9bba7d8 thunk=0x52e7150 impl=0x0F7EB60  bytes=32 c0 c3   (xor al,al; ret)  -> ALWAYS FALSE
ULokiBlueprintLibrary::LokiIsClient   rec=0x9bba790 thunk=0x52e64a0 impl=0x0B9E1F0  bytes=b0 01 c3   (mov al,1; ret)   -> ALWAYS TRUE
```
present in all three images (`s129`, `merged2`, `tuthero`). Same `WITH_SERVER_CODE`-stripped family as FK-1's four stubs and S124's `GoToPhase` phase write. The lookup is name → address → bytes, so the fold-multiplicity caveat (an address cannot *name* a function) does not apply.

Consequences that change every downstream reading:

| site | with IsServer=false / IsClient=true |
|---|---|
| `LokiBeginPlay` line 511 | `LokiTeam::SetTeamForActor(this, PodTeamIndex)` **never runs** |
| `SetDropPodState` line 1431 | `PodStateEvent.DropPodState` **never written** ⇒ `UpdatePodMovement` is permanently dead |
| `StartPodGameplay` line 926 | the `!IsServer` block runs: `bIsLocalPlayerPilot = (PilotPS == LocalPS)` |
| `StartPodGameplay` line 945 | `SpawnImpactIndicator` **never runs** (matches S130: no `GIE_DropPod_Impact_*` in the after-E1 census) |
| `SetCrewPodDetachState(Attached)` line 2389 | **early-returns on a client** — no attach, no move [M, traced through the boolean chain] |
| `PreparePodForAttach` line 1209 | mesh Deactivate + `SetActorHiddenInGame(true)`; the `SetActorEnableCollision(false)` is server-gated |

---

### 2. IS `StartPodGameplay` ON THE `SpawnDropPodForTeam` PATH?

**Indirectly yes — via `FinishSpawningActor` → BeginPlay → `LokiBeginPlay` — and it is conditional.** [M for the structure, [I] for the condition]

`LokiDropShip.as:153` `SpawnDropPodForTeam`, in order: `SpawnPoolableActorFromClassDeferred` → `GetTeamDropLeader(TeamIndex)` → `InitializeDropPod(TeamIndex, PS, LandingLocation, bIsTeamLeader=**true**, DropShip=this, ParentPod=null)` → **`FinishSpawningActor(pod, xform)`** → `RemovePlayerFromPlane` → `AuthPlayerEnterWorldAttachedToRidable` (FK-22 §25's fifth wall) → …

`InitializeDropPod` (line 843) writes `CurrPodDestination(+1144)=LandingLocation`, `bIsTeamLeaderPod(+1117)=1`, `PodTeamIndex(+1120)=TeamIndex`, `LeaderPod(+1200)=null`, `SetOwner(PilotPS)`, then `QueueCrewForPodSpawn(DropShip)`.
`FinishSpawningActor` → `AActor::PostActorConstruction` → `RegisterAllComponents` + `DispatchBeginPlay`.

**Complete caller list for `StartPodGameplay` — exactly TWO, both in `LokiDropPod.as` [M]:** the `CALLINTF 84970` opcode occurs **2 times** across the whole `tools/asdump/out/**/*.as.txt` corpus (unit: bytecode call sites).

1. `LokiBeginPlay_Implementation` line 517, gated on `ULokiTeamComponent::Get(this).GetTeamIndex() >= 0`
2. `OnPodTeamIndexChanged` line 1166, gated on `OldTeamIndex < 0 && NewTeamIndex >= 0` (bound as the else-branch of #1)

Blueprint callers: **none found**, but this is **COVERAGE-BLOCKED, not ABSENT** — `tools/extractor/out` on this machine holds **1,711 files**, not the 69k catalog, so the two hits (`BP_DropPod.json`, both for `BP_StartPodGameplay`, the *event*, not the callable) are a lower bound. `BP_DropPod_C` **does** implement `BP_StartPodGameplay` and `BP_LokiEndPlay` as Blueprint events [M, bpdump export list].

**⚠ THE UNRESOLVED LINK, and it is the whole question.** Because `LokiIsServer()==false`, `SetTeamForActor` never runs, so the pod's team index at BeginPlay is `ULokiTeamComponent`'s **CDO default**, which I could not settle offline. What I did settle [M]: the class is `ULokiTeamComponent`, `sizeof == 0xE8` (from the `GetPrivateStaticClassBody` `InSize` immediate at `.text 0x05471585`, `mov dword [rsp+0x20], 0xE8`), and its three properties are `OnTeamIndexChanged @0xD0`, **`TeamIndex @0xE0` (int32)**, `ReplicatedTeamIndex @0xE4` (int32, `Net|RepNotify=OnRep_TeamIndex`) — recovered via `propowner.py 0x08A76130` → `FClassParams 0x08A763A0`, `NumProperties=3`, then decoding the `PropPointers` array at `0x08A761B0`. Attempts to isolate the ctor's initializer failed: the `.text` scan for `mov [reg+0xE0], imm` returns 230+ sites and the `lea` arguments of the class-registration function fold to other registration thunks.

[I, moderate] `TeamIndex` defaults to **-1**, because `LokiBeginPlay`'s else-branch (subscribe to `OnTeamIndexChanged` and wait) is dead code if the default is ≥ 0, and the pod's own `PodTeamIndex` defaults to -1 [M, ctor `SetV4 v4 -1`].
If that is right, **`StartPodGameplay` never runs on any of the four pods on the client route**, `bHasStartedGameplay` reads 0 everywhere, and nothing ever moves.
If it is wrong (default 0), `StartPodGameplay` runs on **every pod whose components got registered**, and only the E1 pod can reach `Descending`.

**⇒ This is the single one-byte question S131 should buy, and `bHasStartedGameplay` answers it.** Free extra read: `TeamComponent+0xE0` on each pod, reachable from `AActor::InstanceComponents`/the BP variable, or just note it.

Secondary [I, strong] but structural: `LokiBeginPlay` is an AS override of a C++ event. The exact standalone name `LokiBeginPlay\0` has **0 occurrences** in the image; the two ASCII hits are substrings of `BP_LokiBeginPlay` (UHT record `0x7f21958`, thunk `0x33673b0`, no native impl ⇒ BlueprintImplementableEvent) and `BlueprintLokiBeginPlay`. AS names are absent from the exe by construction (S130), so this is consistent with the AS override being real, but the dispatch site in `ALokiActor::BeginPlay` was not located. Positive control that the mechanism is live: `BP_DropPod_C` ships its own `BP_LokiEndPlay` graph, i.e. the shipped content relies on this event family firing.

---

### 3. TICK — DEFAULTS, AND THE EXACT BYTE TO READ

`Tick_Implementation` (line 584) **first statement**: `if (!bHasStartedGameplay) return;` [M]. So actor tick is necessary but not sufficient, and `bHasStartedGameplay` is the cheaper read.

Offsets for a direct probe read [M]:

| what | offset | how derived |
|---|---|---|
| `AActor::PrimaryActorTick` | **+0x38** | `propscan --name PrimaryActorTick`, 1 hit image-wide |
| `FTickFunction` flags byte | struct **+0x0A** | `boolscan` disassembled `SetBitFunc` |
| ⇒ `bCanEverTick` | **AActor+0x42, mask 0x02** | `SetBitFunc 0x032BB180 = or byte [rcx+0xa], 2` |
| ⇒ `bStartWithTickEnabled` | **AActor+0x42, mask 0x04** | `SetBitFunc 0x032BB190 = or byte [rcx+0xa], 4` |
| `bTickEvenWhenPaused` / `bAllowTickOnDedicatedServer` | +0x42 masks 0x01 / 0x08 | same, `0x032BB170` / `0x032BB1A0` |

**Neither `BP_DropPod_C` nor `BP_DropPod_Tutorial_C` serializes `PrimaryActorTick`** [M — full CDO blocks are 8 and 2 properties respectively], so the effective value is `ALokiDropPodBase`'s C++ ctor plus whatever AngelscriptUE's codegen does when a script class declares a `Tick` override. **I could not settle that offline — grade [S], do not assume either way.** `USkeletalMesh_GEN_VARIABLE` *does* serialize a `PrimaryComponentTick` override, so the asset pipeline clearly can carry these; the actor's is simply absent.

**Nothing in `LokiDropPod.as` ever enables actor tick** — the only `SetActorTickEnabled` call in the file passes **`false`** (line 621, the enemy-pilot branch). ⇒ if `bStartWithTickEnabled` is 0, `Tick` never runs for the lifetime of the pod and there is no code path that would fix it. [M for the file, unit: 1 of 1 call sites]

⚠ **Trap for reading S130's own log:** `[FS] hot[00] hits=1 BP_LokiPlayerController_C::ReceiveTick` is a census of **Blueprint bytecode** UFunctions dispatched through `ProcessInternal`. Angelscript UFunctions do not go through `ProcessInternal` (FK-1). The absence of a pod `Tick` from that list is **uninterpretable**, not negative.

---

### 4. `ELokiDropPodState` — VALUES, AND THE STATE A FRESHLY-INITIALIZED POD IS IN

Decoded from the UHT `FEnumeratorParam` table (16-byte `{const char* Name; int64 Value}` records at `.rdata 0x8933870`–`0x89338C0`, name strings at `0x89338D0`+):

| value | name | [M] |
|---|---|---|
| 0 | `None` | |
| 1 | `IntroSequence` | set by `StartPodGameplay` |
| 2 | `Attached` | crew-pod branch of `OnIntroSequenceFinished` |
| 3 | **`Descending`** | **the only value that calls `StartPodMovement`** |
| 4 | `OutroSequence` | |
| 5 | `Destroying` | |

Cross-check: the bytecode uses `SetV1 v29 1` for IntroSequence, `CMPIi v1 3` for Descending, `SetV1 v8 5` for Destroying — all consistent.

Also decoded [M]: `ELokiCrewPodDetachState` = None 0, **Attached 1**, Detachable 2, DetachInputStarted 3, DetachInputStopped 4, DetachInputContinue 5, StartDetaching 6, FinishDetaching 7. `ELokiMovementInputDirection` = None 0, Up 1, UpRight 2, Right 3, DownRight 4, Down 5, DownLeft 6, Left 7, UpLeft 8. `ELokiLeaderPodDetachState` = None 0, StartDetaching 1, AdditionalStartDetaching 2, OneOfManyPodsFinishedDetaching 3, AllDetachingPodsFinished 4.

**There is no `CurrPodState` member.** The state lives at **`PodStateEvent.DropPodState`, pod +1328 +16 = +1344 (0x540), 1 byte** [M]. `PodStateEvent` is `FGameEvent_OnDropPodStateChanged_PlayerState`; the member offsets inside it are `DropPod@+8`, `DropPodState@+16`, `PodPilot@+24`, `bIsLeaderPod@+32` [M, from the `ADDSi` pairs].

**A pod that was `InitializeDropPod`-ed but never `StartPodGameplay`-ed reads `DropPodState = 0 (None)`.**
**A pod that HAS run `StartPodGameplay` on this client route ALSO reads 0** — because `SetDropPodState` never writes the byte on a client (§1a). ⇒ **`DropPodState` is NOT a usable readout in this build; it is 0 under every branch. Use `bHasStartedGameplay` instead.** Recording a 0 there as "the pod never started" would be an instrument artifact.

---

### 5. FIELD OFFSET TABLE FOR THE PROBE (all [M] from AS bytecode, calibrated in §0)

On the pod actor (`BP_DropPod_Tutorial_C`, offsets inherited unchanged from `/Script/Angelscript.LokiDropPod`):

| field | dec | hex | type | ctor default |
|---|---|---|---|---|
| `InitialDropPodSpeed` | 992 | 0x3E0 | double | 2500.0 |
| `IntroSequenceTotalTime` | 1000 | 0x3E8 | double | 6.5 |
| `TotalTimeForPodControls` | 1008 | 0x3F0 | double | 5.5 |
| `OutroSequenceTotalTime` | 1016 | 0x3F8 | double | 1.0 |
| `TotalPodDestructionDelayTime` | 1024 | 0x400 | double | 1.5 |
| `DetachingFromLeaderPodStartTime` | 1080 | 0x438 | double | -1.0 |
| **`bPilotHasPodControl`** | 1116 | 0x45C | bool | 0 |
| **`bIsTeamLeaderPod`** | 1117 | 0x45D | bool | 0 |
| **`PodTeamIndex`** | 1120 | 0x460 | int32 | **-1** |
| **`bIsLocalPlayerPilot`** | 1124 | 0x464 | bool | 0 |
| `ImpactIndicator` | 1128 | 0x468 | ptr | null |
| **`CurrPodDestination`** | 1144 | 0x478 | FVector (3×double) | (0,0,0) |
| `AttachedCrewPods` | 1168 | 0x490 | TArray | empty |
| `bSteeringEnabled` | 1184 | 0x4A0 | bool | 0 |
| `SteeringStartTime` | 1192 | 0x4A8 | double | 0 |
| `LeaderPod` | 1200 | 0x4B0 | ptr | null |
| ★ **`bHasStartedGameplay`** | **1208** | **0x4B8** | bool | **0** |
| `PodStateEvent.DropPodState` | 1344 | 0x540 | uint8 | 0 |
| `CrewDetachEvent.DetachState` | 1392 | 0x570 | uint8 | 0 |
| `bIsHidingDropPhaseHiddenActors` | 1520 | 0x5F0 | bool | **1** |
| `bPodIsDestroying` | 1521 | 0x5F1 | bool | 0 |
| `CurrentInputDirection` / `LastInputDirection` | 1522 / 1523 | 0x5F2/3 | uint8 | 0 |
| `bReadyForOutro` | 1524 | 0x5F4 | bool | 0 |
| `PodMeshComponent` | 1592 | 0x638 | ptr | null until `StartPodGameplay` |

★ **`bHasStartedGameplay` has exactly FOUR bytecode accesses corpus-wide [M]** (grep `1208 134230872`): ctor writes 0; `Tick` reads; `StartPodGameplay` reads then writes 1. **`StartPodGameplay` is its only writer-of-1, and it is not a UPROPERTY, so no Blueprint or replication path can set it.** That makes it an exact, non-confoundable receipt.

Engine-side, for the location reads [M]:

| what | offset | how derived |
|---|---|---|
| `AActor::RootComponent` | +0x1B0 | `propscan --name RootComponent`, 1 hit |
| `USceneComponent::RelativeLocation` | +0x158 | `propscan`, the `Net|RepNotify=OnRep_Transform` record |
| `USceneComponent::ComponentVelocity` | +0x1A0 | `propscan`, 1 plausible hit |
| `UMovementComponent::Velocity` | +0xE8 | §0 |
| `AActor::bCanEverReplicate` | +0x6C bit0 | S130 |
| `AActor::bActorEnableCollision` | +0x6E bit4 | `SetBitFunc 0x03368B30`, fold=1 |
| `AActor::bEnablePooling` | +0x2D3 bit0 | `SetBitFunc 0x03368BF0`, fold=1 |

`ComponentVelocity` is a free second witness: `UMovementComponent::UpdateComponentVelocity()` copies `Velocity` into the updated component, so a descending pod reads non-zero there **and** non-zero at `PMC+0xE8`.

**The pod's RootComponent is the `Capsule` (`UCapsuleComponent`, `InternalVariableName = Capsule`, `SCS_Node_5`)** — the only scene-component root node in `SimpleConstructionScript_0.RootNodes` (the other three are `ProjectileMovement`, `LokiTeam`, and `SCS_Node_13`) [M, bpdump]. Half-height 468.38, radius 250.19.

---

### 6. THE THREE PRE-EXISTING PODS ARE **NOT** THREE OF A KIND — this is the most important correction in this lane

The brief describes them as "raw `SpawnPoolableActorFromClassDeferred`, NO `InitializeDropPod`". That is true of **one** of the three. From `scratchpad/s130/evidence/RESULT-poolspawn-cdopoke-s130.txt` [M]:

| pod (S130 addresses; ASLR, re-derive) | how spawned | `FinishSpawning`? | anim instance appeared? |
|---|---|---|---|
| `0x1D1FFDDE830` (P1) | `SpawnPoolableActorFromClassDeferred` | **NO** | **no** — after-P1 shows 1 new object only |
| `0x1D1A5DA7910` (P2) | `SpawnPoolableActorFromClass` (non-deferred) | yes, internally | **yes** — `ABP_DropPod_C 0x1D1824B0DC0` |
| `0x1D1956C0200` (P3) | `BeginDeferredActorSpawnFromClass` + `FinishSpawningActor` | **yes** | **yes** — `ABP_DropPod_C 0x1D1A5C0B380` |
| `0x1D015C87910` (E1) | `SpawnDropPodForTeam` (deferred + `InitializeDropPod` + `FinishSpawningActor`) | yes | **yes** — `ABP_DropPod_C 0x1D1A4DA2740` |

The appearance of an `ABP_DropPod_C` AnimInstance is a **free registration receipt**: `USkeletalMeshComponent::InitAnim` only runs on component registration. **P1 never got `PostActorConstruction`**, so it has no registered components, no registered tick function, no `BeginPlay`. P2/P3/E1 did.

All three poolspawn pods were spawned at the `TrainingStart`-tagged PlayerStart `(-3206.4, 5070.5, 100.0)`; the **E1 pod was spawned at `(-3206.4, 5070.5, 20100.0)`** with `CurrPodDestination = (-3206.4, 5070.5, 100.0)`, `TeamIndex = 0`, `bIsTeamLeader = true`. ⇒ **z ≈ 20100 uniquely identifies the E1 pod** without needing to trust an address.

**Would any mechanism move the three? No — and for each there are two independent reasons.** [M except where marked]

- **P1**: (a) components never registered ⇒ the PMC has no `UpdatedComponent`, its tick function was never registered, and `AActor::Tick` was never registered either; (b) `bHasStartedGameplay = 0` with no path to set it (`BeginPlay` never dispatched).
- **P2, P3**: (a) `bIsTeamLeaderPod = 0` (ctor default; `InitializeDropPod` never called) ⇒ **even if `StartPodGameplay` runs, `OnIntroSequenceFinished` selects `Attached (2)`, not `Descending (3)`, so `StartPodMovement` is never reached**; (b) `CurrPodDestination = (0,0,0)`, so the movement they cannot start would have no meaningful target anyway.
- **All three**: `ProjectileGravityScale = 0`, `Velocity` initialised to zero (PMC `InitializeComponent` only rescales a *non-zero* velocity), no server, `bReplicateMovement` inert with no net driver, and `SetCrewPodDetachState(Attached)` early-returns on a client.

⇒ **the three are a genuine within-run stationary control under BOTH branches of the §2 uncertainty, and E1 moving is therefore attributable.**
⚠ One visible side effect if `StartPodGameplay` *does* run on P2/P3: `PreparePodForAttach()` calls `SetActorHiddenInGame(true)` — they vanish visually while staying at the same coordinates. Location is unaffected.

---

### 7. PRE-REGISTERED PREDICTIONS

Notation: **T0 = the moment the E1 `SpawnDropPodForTeam` call returns**. Two branches, distinguished by one byte.

#### Branch A — `bHasStartedGameplay(E1) == 1` (team index ≥ 0 at BeginPlay)

| field | prediction | grade | because |
|---|---|---|---|
| E1 `bHasStartedGameplay` +0x4B8 | **1** | [M] given branch | its only writer is `StartPodGameplay` |
| E1 `bIsTeamLeaderPod` +0x45D | **1** | [M] | `InitializeDropPod(..., bIsTeamLeader=true, ...)`, hardcoded at `LokiDropShip.as` bytecode `0x0108 SetV1 v3 1` |
| E1 `PodTeamIndex` +0x460 | **0** | [M] | E1 passed `TeamIndex=0` |
| E1 `CurrPodDestination` +0x478 | **(-3206.4, 5070.5, 100.0)** | [M] | written by `InitializeDropPod` from the Landing arg |
| E1 `PodStateEvent.DropPodState` +0x540 | **0** | [M] | client never writes it (§1a) — **0 here is NOT evidence of anything** |
| E1 `bIsLocalPlayerPilot` +0x464 | **0** | [I, strong] | `GetTeamDropLeader` needs `IsSpawnTeamLeader()`, whose only setter `AuthSetSpawnTeamLeader` is an FK-1 empty stub ⇒ `PilotPlayerState == null ≠ LocalPS` |
| E1 `bPilotHasPodControl` +0x45C | **0 → 1 at T0+6.5 s** | [M] | `AllowPodSteeringStarted` sets it for leader pods |
| E1 `bSteeringEnabled` +0x4A0 / `SteeringStartTime` +0x4A8 | **0/0 → 1/`World.TimeSeconds` at T0+6.5 s** | [M] | same function |
| E1 `PodMeshComponent` +0x638 | **non-null** | [M] | `StartPodGameplay` assigns it |
| **E1 location** | **z = 20100 until T0+6.5 s, then falling at exactly 2500 uu/s straight down; x,y constant** | [M] | `StartPodMovement`, gravity 0, `UpdatePodMovement` dead |
| E1 `PMC+0xE8 Velocity` / root `+0x1A0 ComponentVelocity` | **(0,0,0) → (0,0,-2500)** at T0+6.5 s | [M] | |
| **E1 ground contact** | **T0 + 6.5 + 20000/2500 = T0 + 14.5 s** (earlier if terrain is above z=100) | [M] arithmetic, [I] on terrain height |
| **E1 disappears from the census** | **~1.5 s after contact, ≈ T0+16 s** | [M] | `OnDropPodHit → StartDestroyPod` (hide + `StopMovementImmediately` + `SetDropPodState(5)`) → 1.5 s timer → `FinishDestroyPod → DestroyActor()` |

**Recommended sample times and predicted z (branch A): T0+1 s → 20100 · T0+8 s → 16350 · T0+12 s → 6350.** Add a 4th read at T0+20 s expecting the actor to be **gone**; that is the cleanest possible "the pod was functional" receipt and it costs nothing.

| the three poolspawn pods, branch A | prediction | grade |
|---|---|---|
| `bHasStartedGameplay` | P1 **0**; P2/P3 **1** | [M] — P1's components never registered so BeginPlay cannot have run |
| `bIsTeamLeaderPod` / `PodTeamIndex` / `CurrPodDestination` | **0 / -1 / (0,0,0)** on all three | [M] ctor defaults, `InitializeDropPod` never called |
| **location, all three samples** | **(-3206.4, 5070.5, 100.0), identical to 0.00 uu across all three reads** | [M] |
| `PMC Velocity` | **(0,0,0)** on all three | [M] |
| still present at T0+20 s | **yes, all three** | [M] |

#### Branch B — `bHasStartedGameplay(E1) == 0` (team index < 0, my [I] favourite)

Every pod, including E1: `bHasStartedGameplay = 0`, `bPilotHasPodControl = 0`, `bSteeringEnabled = 0`, `PodMeshComponent = null`, `PMC Velocity = (0,0,0)`, **location identical across all three samples**, E1 parked at z = 20100 indefinitely, nothing destroyed. E1 still reads `bIsTeamLeaderPod = 1`, `PodTeamIndex = 0`, `CurrPodDestination = (-3206.4, 5070.5, 100.0)` — those are written by `InitializeDropPod`, which runs regardless.

**In branch B, "the pod does not move" has a NAMED reason: `LokiBeginPlay`'s team gate was not satisfied, so `StartPodGameplay` never ran.** That is a specific, testable, one-more-poke finding (`TeamComponent+0xE0 = 0`, or call the reflected `OnPodTeamIndexChanged(pod, -1, 0)`), not a dead end.

#### Instrument warnings the probe must carry

- ⚠ **P1's location read may be unreadable or (0,0,0).** Its components were never registered, so `RootComponent` may be null and `K2_GetActorLocation` may return the origin. S130's own probe printed `loc=UNREADABLE(0,0,0)` for `LokiHeroCharacterGrid` and `proxy(root)=null` for the P3 FinishSpawning. **`(0,0,0)` on P1 is an instrument condition, not a position.** Read `AActor+0x1B0` first and report "root=null" explicitly rather than a coordinate.
- ⚠ **Reuse S130's P0c pattern for every location read**: `K2_GetActorLocation` via the S55 direct thunk **cross-checked against a pure-RPM read of `RootComponent+0x158`**, and require agreement to ~0 uu on a non-zero reference. S130's P0c scored `0.00 uu on |ref|=8377`.
- ⚠ **Do not read `PodStateEvent.DropPodState` as a state machine.** It is 0 under every branch in this build.
- ⚠ **`AttachedCrewPods` (+0x490) will be empty even in branch A** — `QueueCrewForPodSpawn`/`SpawnCrewPodQueue` depend on the drop-plane's player list, which is empty here.
- ⚠ Precondition inherited from S130/S127: the E1 arm needs `DropShip = 1`, i.e. `dropplane_b1only` injected **before** the Route E probe. S130's Route E BEFORE census reads `DropPlane=4 DropPod=7 DropShip=1` against the poolspawn arm's `DropPlane=3 DropPod=2 DropShip=0`, i.e. the poolspawn arm ran first in the **same** process and the plane was injected between. The "three pods already exist" framing only holds if S131 reproduces that ordering.

---

### 8. WHICH FALSIFICATIONS ARE INTERESTING

**INTERESTING — a real statement about the game:**
- E1 `bHasStartedGameplay == 1` **but the pod never moves** after T0+6.5 s (velocity stays 0, or velocity non-zero but location frozen). That would mean the timer never fired, or the PMC's `UpdatedComponent` is null / non-Movable, or actor tick is off in a way that also kills component tick. It localises the wall to the movement component rather than to the gameplay start.
- E1 moves at a speed **other than 2500 uu/s**, or on a non-straight path. That would falsify §1a (`UpdatePodMovement` is dead) — i.e. `PodStateEvent.DropPodState` got written, which would mean `LokiIsClient` is not what the bytes say. **This would be the biggest result in the lane**, because it reopens the entire server-stripping model.
- **Any** of P1/P2/P3 moves. Under both branches nothing can move them; movement would mean an unenumerated driver exists (pooling reactivation, replication, a BP tick body). Highest-value falsification available.
- E1 disappears from the census without the descent being observed — pod destroyed by something else.
- E1 `bIsLocalPlayerPilot == 1`. That would mean `GetTeamDropLeader` returned the local PlayerState, which contradicts FK-1's `AuthSetSpawnTeamLeader` stub and would open the rider path.
- P2/P3 `bHasStartedGameplay == 1` while E1's is **0**. Structurally impossible under the model (E1 has strictly more preconditions satisfied) — would mean I mis-read `LokiBeginPlay`'s gate.

**NOT INTERESTING — most likely a mis-read offset or an instrument condition:**
- Any field reading obvious garbage (a `bool` that is neither 0 nor 1; `CurrPodDestination` not equal to the landing location on E1, which `InitializeDropPod` writes unconditionally before `FinishSpawningActor`). Treat `CurrPodDestination == (-3206.4, 5070.5, 100.0)` on E1 and `(0,0,0)` on the other three as the **offset calibration check** — if that fails, stop and re-derive, do not report anything else from the block.
- `PodStateEvent.DropPodState == 0` anywhere (predicted under every branch).
- P1 location reading `(0,0,0)` or unreadable (see §7 warnings).
- All four `bCanEverTick` bits reading the same value — that is expected, they share a class chain; it is informative only in comparison with a known-ticking actor such as the hero, which the probe should sample as a positive control.
- `bHasStartedGameplay == 0` on **all four** — that is branch B, a predicted outcome with a named cause, not a null result.

---

### 9. RESIDUAL SIDE EFFECT WORTH KNOWING BEFORE ARMING

If branch A holds, `Tick` runs on the E1 pod and, because `bIsHidingDropPhaseHiddenActors` defaults to **1** (+0x5F0), it calls `UpdateDropPhaseHiddenActors()` **every frame** for the pod's whole life. I did not read that function's body. It is named as an actor-hiding sweep and could touch unrelated world actors. If S131 wants to be conservative, poke `pod+0x5F0 = 0` immediately after the E1 call — one aligned byte on an instance (not a CDO), readback-verifiable, and it removes the only unbounded per-frame work the pod does. It does **not** affect movement (`UpdatePodMovement` is called separately in `Tick`, and is dead anyway).