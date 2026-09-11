# SUPERVIVE Angelscript — FFA deathmatch, bot spawning, and the respawn loop

**Source:** `Loki/Script/PrecompiledScript.Cache` (shipping build 2025-12-17), decompiled with
`tools/asdump/asdump.py`. Six modules, one class each, **45,987 bytes of cache records
holding 89 functions and 13,668 dwords (54,672 bytes) of bytecode** — all 89 decoded exactly.

| module | source path | class | bytecode | CodeHash |
|---|---|---|---:|---|
| `FFA.FFAGameMode` | `FFA/FFAGameMode.as` | `AFFAGameMode : ALokiDropInGameMode` | 2,252 dw | `0x9b846b6d930fd55a` |
| `FFA.FFABotSpawner` | `FFA/FFABotSpawner.as` | `UFFABotSpawnerComponent : ULokiBotSpawnerComponent` | 1,404 dw | `0xcc7a2d0d39e56da7` |
| `FFA.LokiRespawnComponent` | `FFA/LokiRespawnComponent.as` | `ULokiRespawnComponent : UActorComponent` | 5,036 dw | `0xd4a34842cc2151a5` |
| `FFA.LokiPlayerRespawnComponent` | `FFA/LokiPlayerRespawnComponent.as` | `ULokiPlayerRespawnComponent : UActorComponent` | 3,632 dw | `0x60cfeda953b114f5` |
| `FFA.Comp_PC_LokiRespawnComponent` | `FFA/Comp_PC_LokiRespawnComponent.as` | `UComp_PC_LokiRespawnComponent : UActorComponent` | 624 dw | `0xc51b35bc22acc54c` |
| `FFA.RespawnTimerWidget` | `FFA/RespawnTimerWidget.as` | `URespawnTimerWidget : UUserWidget` (Abstract) | 720 dw | `0x70bbe64c7cc6ad33` |

Full per-function output (pseudo-code + fully symbol-resolved disassembly) is in
`tools/asdump/out/modules/FFA/*.as.txt`. **Where this document and that output disagree, the
disassembly appendix wins** — three places below are hand-corrected against it and are called out.

Every declaration here (class, base, property, type, `UPROPERTY`/`UFUNCTION` flags, parameter
names, replication flags) is **stored verbatim in the cache and is exact**. Bodies are decompiled;
local names were never serialised in a shipping build, so locals read as `vN`.

---

## 0. The short version

* **FFA is a respawn deathmatch layered on the drop-in game mode.** `AFFAGameMode` derives from
  `ALokiDropInGameMode`, so it inherits the whole BR-style round-phase machine, but it overrides
  `ShouldTeamBeEliminated` to **`return false` unconditionally** — no team is ever eliminated, so
  the BR win condition is switched off.
* **The mode does not spawn anyone on login.** `HandleStartingNewPlayer` and `OnPostLogin` are
  declared as **empty overrides**. All spawning goes through the respawn components.
* **The respawn director lives on the GameMode** (`ULokiRespawnComponent`), the **timer lives on
  each PlayerState** (`ULokiPlayerRespawnComponent`, the only replicated state in the whole set),
  and the **UI lives on the PlayerController** (`UComp_PC_LokiRespawnComponent` → `URespawnTimerWidget`).
* **Spawn points are actors tagged `SafeTeamSpawnPathfindingAnchor`**, gathered at runtime by tag.
  That FName literal is verified independently against the cache's own `StaticNames[58]`.
* **The bot spawner supplies a roster, not a spawn.** `UFFABotSpawnerComponent::BeginPlay`
  hard-codes **ten hero `FPrimaryAssetId`s**, resolves each to a `TSubclassOf<ALokiHeroCharacter>`,
  and hands the list to the native `SetSpawnableBots`. **No script in any of the 78 modules ever
  calls `TrySpawnTeam`, `SpawnBot` or `MakeNewBotController`** (measured across the whole corpus) —
  the actual spawn trigger is C++ or Blueprint.
* **A client can force its own respawn.** `ULokiPlayerRespawnComponent::AuthRequestRespawn` is a
  `NetServer` RPC with no `NetValidate` and no server-side rate gate.

---

## 1. Wiring — who owns what

Nothing in the script attaches these components; each attachment below is **proven by the code that
reads it back**, not assumed.

```
ALokiGameState  ──OnPlayerKilled──────────────┐        (delegate FPlayerKillEventSignature)
                ──OnRoundPhaseChanged─────┐   │        (delegate FNewRoundPhase)
                                          │   │
AFFAGameMode (: ALokiDropInGameMode)       │   │
  ├── ULokiRespawnComponent   ◄────────────┼───┘   the respawn DIRECTOR
  │      • Starts[]  (tag-scanned)         │       server-only in practice: the GameMode
  │      • NonSpawningBotStates            │       does not exist on clients
  │      • OnPlayerStartsCreated (FOnUpdated)
  │      └─ binds GameMode.OnPlayerLogout ─┼──► its own OnLogout
  └── UFFABotSpawnerComponent (: ULokiBotSpawnerComponent)
         • AvailableBots[10 FPrimaryAssetId] → SetSpawnableBots(native)

ALokiPlayerState                           │
  └── ULokiPlayerRespawnComponent  ◄───────┘   the per-player TIMER
         • RespawnTime  ── REPLICATED, RepNotify OnRep_RespawnTime ──► client
         • LocalRespawnTime  (ticked down on both sides)
         • OnRespawnTimeUpdated (FOnUpdated)
         • AuthRequestRespawn()  ◄── NetServer RPC ◄──┐
                                                      │
ALokiPlayerController                                 │
  └── UComp_PC_LokiRespawnComponent  (client only)    │
         └─ CreateWidget(RespawnTimerWidget) ──► URespawnTimerWidget (Abstract)
                • PSC → the local PlayerState's ULokiPlayerRespawnComponent
                • OnRequestRespawn() ─────────────────┘
```

Proof of each attachment, from the decompiled bodies:

| component | owner | evidence |
|---|---|---|
| `ULokiRespawnComponent` | the **GameMode** | `ULokiPlayerRespawnComponent::CheckSetInitialRespawn` and `::Respawn` both do `Loki::GetLokiGameMode(...).GetComponentByClass(ULokiRespawnComponent::StaticClass())` |
| `ULokiPlayerRespawnComponent` | the **PlayerState** | its `BeginPlay` / `OnPlayerDisconnected` / `Respawn` all do `GetOwner()` → `cast<ALokiPlayerState@>` |
| `UComp_PC_LokiRespawnComponent` | the **PlayerController** | its `BeginPlay` does `GetOwner()` → `cast<ALokiPlayerController@>` |
| `UFFABotSpawnerComponent` | *not determined from script* | reads `this.SpawnedTeamCount` (inherited from `ULokiBotSpawnerComponent`) and nothing that identifies its owner |

**Inference, labelled as such:** `ALokiGameMode` exposes bound `UPROPERTY`s
`AdditionalControllerComponents`, `AdditionalPlayerStateComponents` and
`AdditionalTeamStateComponents`, all `TArray<TSubclassOf<UActorComponent>>`. Those are the obvious
mechanism by which `ULokiPlayerRespawnComponent` and `UComp_PC_LokiRespawnComponent` get attached,
and the `Comp_PC_` name prefix matches the project's already-observed `Comp_GameMode_DropPlane_Tutorial`
convention. **No script confirms this** — it is a data/Blueprint decision that lives outside the caches.

---

## 2. `FFA/FFAGameMode.as` — the mode

### Declaration (exact)

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class AFFAGameMode : ALokiDropInGameMode
// unreal base : /Script/Loki.LokiDropInGameMode
// C++ header  : ../../../Loki/Source/Loki/GameModes/LokiDropInGameMode.h
{
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance, Transient)
    int LevelToGrant;                                        // = 15 in __InitDefaults

    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TSubclassOf<ALokiBaseItem@> BandageItem;                 // NULL in the script CDO

    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TSubclassOf<ALokiBaseItem@> ArmorItem;                   // NULL in the script CDO

    UPROPERTY(BlueprintReadable, EditableOnDefaults, EditableOnInstance)
    TSet<ALokiPlayerState@> InitializedPlayerStates;

    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TSet<ALokiPlayerController@> ConnectedPlayerControllers;  // constructed, NEVER used in script
}
```

Functions (17 in the module; 3 are the generated module-level `AFFAGameMode()` /
`StaticClass()` / `Spawn(...)` helpers):

| signature | `UFUNCTION` | overrides |
|---|---|---|
| `bool ShouldTeamBeEliminated_Implementation(const int TeamIndex)` | BlueprintOverride, BlueprintEvent, CanOverrideEvent | `ALokiGameMode::ShouldTeamBeEliminated` |
| `void OnPlayerSpawned_BP_Implementation(ALokiCharacter@ Character, ALokiPlayerState@ PlayerState)` | BlueprintOverride, BlueprintEvent, CanOverrideEvent | `ALokiGameMode::OnPlayerSpawned_BP` |
| `void InitPlayer(ALokiPlayerState@ PlayerState)` | *(event dispatcher)* | — |
| `void InitPlayer_Implementation(ALokiPlayerState@)` | BlueprintEvent, CanOverrideEvent, **NoOp** | — (empty; for a BP subclass) |
| `void OnPostLogin_Implementation(APlayerController@ NewPlayer)` | BlueprintOverride, BlueprintEvent, CanOverrideEvent, **NoOp** | `AGameModeBase::OnPostLogin` (UFunction `K2_PostLogin`) |
| `void OnLogout_Implementation(AController@ ExistingController)` | BlueprintOverride, BlueprintEvent, CanOverrideEvent | `AGameModeBase::OnLogout` (UFunction `K2_OnLogout`) |
| `void OnCharacterRespawned(ALokiCharacter@)` / `_Implementation` | BlueprintEvent, CanOverrideEvent | — |
| `void ResetArmor(ALokiCharacter@ Character)` | *(plain script method)* | — |
| `void AddBandages(ALokiCharacter@ Character)` | *(plain script method)* | — |
| `void HandleStartingNewPlayer_Implementation(APlayerController@ NewPlayer)` | BlueprintOverride, BlueprintEvent, CanOverrideEvent, **NoOp** | `AGameModeBase::HandleStartingNewPlayer` |
| `void __InitDefaults()` | — | CDO initialiser |

> `NoOp` here is the compiler's marker for an **empty body**; each of those functions is literally
> one `RET` instruction. The parent UFunction names in the right-hand column come from `Binds.Cache`
> (`OnLogout ↔ K2_OnLogout`, `OnPostLogin ↔ K2_PostLogin`). ⚠ The cache stores this script class's
> own `UnrealFunctionName` as the bare `OnLogout` / `OnPostLogin`; **which of the two names the
> generated UFunction on `AFFAGameMode` actually carries is not decidable from these files.** A
> native shim should check both. The same trap applies across all six modules: `Binds.Cache` maps
> the script names `BeginPlay → ReceiveBeginPlay`, `Tick → ReceiveTick` (on both `AActor` and
> `UActorComponent`), and `GetActorLocation → K2_GetActorLocation`, `DestroyActor → K2_DestroyActor`,
> `ApplyGameplayEffectSpecToSelf → BP_ApplyGameplayEffectSpecToSelf`. Only `UUserWidget::Tick` and
> `UUserWidget::Construct` keep their bare names.

### How it starts and runs

**There is no `BeginPlay` on `AFFAGameMode`.** Match startup — round phases, login, the drop-in
sequence — is entirely inherited C++ (`ALokiDropInGameMode` → `ALokiGameMode`), which the script
only hooks. The five hooks it installs are the whole mode:

**1. The match cannot end by team elimination.**

```angelscript
bool ShouldTeamBeEliminated_Implementation(const int TeamIndex) { return false; }
// bytecode: SetV1 v1 0 ; CpyVtoR4 v1 ; RET 3    — a constant, TeamIndex is never read
```

**2. Nobody is spawned on login.**

```angelscript
void OnPostLogin_Implementation(APlayerController@ NewPlayer)            { }   // RET 4
void HandleStartingNewPlayer_Implementation(APlayerController@ NewPlayer){ }   // RET 4
```

*Engine-semantics inference (labelled):* stock `AGameModeBase::HandleStartingNewPlayer_Implementation`
calls `RestartPlayer(NewPlayer)`. An empty override therefore **suppresses auto-spawn-on-login**,
which is consistent with the rest of the design — the initial spawn arrives ~10 s later via
`ULokiPlayerRespawnComponent::CheckSetInitialRespawn`.

**3. Every spawn (first or later) runs the loadout reset; the first also grants level 15.**

```angelscript
void OnPlayerSpawned_BP_Implementation(ALokiCharacter@ Character, ALokiPlayerState@ PlayerState)
{
    this.OnCharacterRespawned(Character);                 // BP event -> _Implementation below
    if (this.InitializedPlayerStates.Contains(PlayerState))
        return;
    Character.AuthGrantLevel(this.LevelToGrant);          // LevelToGrant = 15
    this.InitializedPlayerStates.Add(PlayerState);
    this.InitPlayer(PlayerState);                         // BP event; empty in script
}

void OnCharacterRespawned_Implementation(ALokiCharacter@ Character)
{
    Character.ResetAllCooldowns();
    this.AddBandages(Character);
    this.ResetArmor(Character);
}
```

**4. The per-respawn loadout.** Both helpers use `ULokiInventoryComponentBase`
(`bool TryAddToInventory(ALokiBaseItem, ELokiAddToInventoryReason Reason, FName SlotName = NAME_None,
int SlotIndex = -1, bool bCheckSpace = true, bool bDestroyDisplacedItems = false)`).

```angelscript
void AddBandages(ALokiCharacter@ Character)
{
    auto Inv = ULokiInventoryComponentBase::GetInventoryComponent(Character);
    auto All = Inv.GetAllItemsAndSlots();                       // TArray<FLokiInventoryItemAndSlot>
    TSet<FName> Cats;  Cats.Add(n"Health");  Cats.Add(n"Consumable");
    for (auto& E : All)
        if (Cats.Contains(E.SlotCategory))
            Inv.TryRemoveFromInventory(E.ItemActor, ELokiRemoveFromInventoryReason::Destroyed);

    for (int i = 0; i < 3; i++) {                               // CMPIi v52 3 ; JS -> loop
        auto Item = SpawnActor(this.BandageItem, FVector::ZeroVector, FRotator::ZeroRotator,
                               NAME_None, /*bDeferred*/false, /*Level*/nullptr);
        Inv.TryAddToInventory(Item, ELokiAddToInventoryReason::Initial, NAME_None, -1,
                              /*bCheckSpace*/true, /*bDestroyDisplaced*/false);
    }
}

void ResetArmor(ALokiCharacter@ Character)
{
    auto Inv = ULokiInventoryComponentBase::GetInventoryComponent(Character);
    for (auto& E : Inv.GetAllItemsAndSlots())
        if (FName(E.SlotCategory) == n"Shield")
            Inv.TryRemoveFromInventory(E.ItemActor, ELokiRemoveFromInventoryReason::Destroyed);

    auto Item = SpawnActor(this.ArmorItem, FVector::ZeroVector, FRotator::ZeroRotator,
                           NAME_None, false, nullptr);
    Inv.TryAddToInventory(Item, ELokiAddToInventoryReason::Initial, NAME_None, -1, true, false);
}
```

> **Corrected against the disassembly.** `asdump` originally printed `return;` *before* the
> `TryAddToInventory` line in `ResetArmor`. The bytecode is unambiguous —
> `CALLSYS SpawnActor` → `STOREOBJ v34` → `PshVPtr v34` → `PshVPtr v4` →
> `CALLSYS TryAddToInventory` → `RET 4` — so the add executes. This was a real lifter bug
> (a void `RET` emitted before the pending call statement was flushed); **I fixed it in
> `asdump.py`**, see §9. Exactly 2 sites corpus-wide were affected, this and one in
> `Barracuda/GameState/BarracudaGameStateComponent.as`.

The `n"Health"`, `n"Consumable"`, `n"Shield"` FName literals are `StaticNames[51]`, `[52]`, `[50]`
in the cache's own literal pool — verified independently of the lifter.

**5. The mode shuts itself down when the last human leaves.**

```angelscript
void OnLogout_Implementation(AController@ ExistingController)
{
    auto GS = Loki::GetLokiGameState(__WorldContext);
    int LiveHumans = 0;
    for (auto PS : GS.GetLokiPlayerStates())
        if (!PS.IsABot() && !this.DisconnectedPlayerStates.Contains(PS.PlatformPlayerID))
            LiveHumans++;

    if (LiveHumans == 0)
        this.GracefullyShutdown("AllPlayersDisconnected", /*ReturnCode*/0);

    auto PS = cast<ALokiPlayerState@>(ExistingController.PlayerState);
    if (PS != nullptr && !PS.IsABot()) {
        this.DisconnectedPlayerStates.Remove(PS.PlatformPlayerID);
        PS.DestroyActor();                       // UFunction K2_DestroyActor
    }
}
```

`DisconnectedPlayerStates` is `TMap<FString, ALokiPlayerState@>` at offset **+1424** on
`ALokiGameMode`; `PlatformPlayerID` is `FString` at **+2240** on `ALokiPlayerState`. Note the
ordering: the count runs **before** the leaving PlayerState is destroyed, so the departing player
may still be counted in `LiveHumans` on this pass. **FFA does not reserve a reconnect slot** — the
human's PlayerState is destroyed outright.

### Dead in script

`ConnectedPlayerControllers` is constructed in the constructor and destructed in the destructor
and is **never read or written anywhere else in the corpus**. It is `BlueprintReadable/Writable`,
so a Blueprint subclass may use it.

---

## 3. `FFA/FFABotSpawner.as` — what the bots actually are

### Declaration (exact)

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class UFFABotSpawnerComponent : ULokiBotSpawnerComponent
// unreal base : /Script/Loki.LokiBotSpawnerComponent
// C++ header  : ../../../Loki/Source/Loki/AI/Bots/LokiBotSpawnerComponent.h
{
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TArray<FPrimaryAssetId> AvailableBots;
}
```

Two functions of substance:

```angelscript
UFUNCTION(UnrealName=BeginPlay, BlueprintOverride, BlueprintEvent, CanOverrideEvent)
void BeginPlay_Implementation()
{
    this.AvailableBots.Add(FPrimaryAssetId("Hero:assault"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:firefox"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:freeze"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:sniper"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:flex"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:hookguy"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:rocketjumper"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:Storm"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:BurstCaster"));
    this.AvailableBots.Add(FPrimaryAssetId("Hero:BountyHunter"));

    TArray<TSubclassOf<ALokiHeroCharacter@>> Viable;
    for (auto Id : this.AvailableBots) {
        ELokiAssetLookupExecPins Execs = /*true==*/ ELokiAssetLookupExecPins(1);
        auto HeroAsset = ULokiAssetLoader::GetHeroAssetFromPrimaryAssetId(__WorldContext, Id, Execs);
        if (int(Execs) != ELokiAssetLookupExecPins::LookupFailed) {            // != 1
            UClass Cls = System::LoadClassAsset_Blocking(HeroAsset.GameplayBlueprint);
            TSubclassOf<ALokiHeroCharacter@> Sub = Cls;
            if (Sub.IsValid())
                Viable.Add(Sub);
        }
    }
    this.SetSpawnableBots(Viable);        // native ULokiBotSpawnerComponent::SetSpawnableBots
}

UFUNCTION(UnrealName=GetNextTeamIndex, BlueprintOverride, BlueprintEvent, CanOverrideEvent, ConstMethod)
int GetNextTeamIndex_Implementation() const { return this.SpawnedTeamCount + 4; }
// bytecode: LoadThisR 212 (.SpawnedTeamCount) ; RDR4 v1 ; ADDIi v2 v1 4 ; RET 2
```

### Answering the question directly

**What does it spawn?** *Nothing.* This component only supplies a roster and a team-numbering
policy. The spawning primitives all live on the native base and are — measured across **all 78
modules** — never called from Angelscript:

```
ULokiBotSpawnerComponent   (/Script/Loki.LokiBotSpawnerComponent)
  int  SpawnedTeamCount                                              <- property, read by FFA
  bool TrySpawnTeam(const uint8 Difficulty, const FVector LocationOverride = FVector())
  ALokiHeroCharacter SpawnBot(const TSubclassOf<ALokiHeroCharacter> HeroClass,
                              const FVector Location, const int TeamIndex,
                              const uint8 Difficulty = 4,
                              AController PremadeBotController = nullptr,
                              FString BotName = "")
  AController MakeNewBotController(TSubclassOf<ALokiHeroCharacter> HeroClass,
                                   const FString BotName, const int64 TeamIndex,
                                   bool bIsAnonymous = false)
  void SetSpawnableBots(const TArray<TSubclassOf<ALokiHeroCharacter>>& ViableBots)   <- FFA calls this
  TArray<TSubclassOf<ALokiHeroCharacter>>& GetSpawnableBots()
  uint8 GetDifficulty(uint8 IntValue) const
  void SetSpawnCheatsEnabled(const bool Enabled)
  int  GetNextTeamIndex() const                                       <- FFA overrides this
```

**How many?** Not decidable from script. The roster is 10 heroes; the count of bots spawned is
whatever the native `TrySpawnTeam` caller decides. `GetNextTeamIndex → SpawnedTeamCount + 4` means
**bot teams are numbered from 4 upward** (team 4, 5, 6, …), i.e. teams 0–3 are reserved for humans —
consistent with `ALokiGameMode::NumTeams` / `MaxPlayersPerTeam` being data-driven.

**From what class/asset?** `FPrimaryAssetId("Hero:<id>")` → `ULokiAssetLoader::GetHeroAssetFromPrimaryAssetId`
→ `ULokiHeroAsset::GameplayBlueprint` (`TSoftClassPtr<ALokiHeroCharacter>`) → `LoadClassAsset_Blocking`.
So the bot pawn class is the hero's **gameplay Blueprint**, loaded synchronously through the
AssetManager at `BeginPlay`. All ten of these ids already appear in this project's own backend
(`server/internal/menu`, `server/internal/interactive`) in exactly the `Hero:<id>` form.

**What drives the bots?** `MakeNewBotController` returns an `AController`; the bound bot controller
is `ALokiBotController` (`Loki/Source/Loki/AI/Bots/LokiBotController.h`) and it is **native, not a
Blueprint behaviour tree** — its script-visible surface is a personality/goal/spell system:

```
ALokiBotController : FString PersonalityID ; AActor CurrentSpellTarget ;
                     float32 CombatMaxGlideHeight / GlideCombatRange ;
                     uint8 GetDifficulty() ; FLokiBotTeamGoal GetPersonalGoal() ;
                     TArray<FLokiBotSpell> GetUsableSpells() ; FVector GetCurrentDestination() ;
                     GenerateAimError() / RemoveAimError() / TryToDash() / SendBotEmote(...) ;
                     bool IsHeroBotCompInitialized() ; bool IsSeenByPlayers() ;
supporting structs: FLokiBotDifficultyConfig, FLokiBotPersonalityConfig, FLokiBotPlaystyle,
                    FLokiBotTeamGoal, FLokiBotEnemy, FLokiBotSpell, FCoreGameBotConfig
also bound: ULokiBotManager (static Get), ULokiBotPositionComponent,
            ULokiBotTeamPlannerComponent, ALokiBotSpawnLocation, UBotIgnorable
```

**Statement of confidence:** the roster, the asset resolution path, the difficulty default (`4`) and
the team numbering are decompiled facts. The AI *behaviour* is C++ and is **not** in these caches —
the class inventory above is a name-level census from `Binds.Cache`, and I am labelling it as such.

### One thing to watch

`BeginPlay` **appends** the ten ids; it never calls `Reset()`/`Empty()` on `AvailableBots`. If a
Blueprint subclass pre-populates the array in the editor, those entries survive and the ten are
added on top (duplicates included). Also note the inconsistent casing in the literals —
`Hero:Storm`, `Hero:BurstCaster`, `Hero:BountyHunter` are capitalised while the other seven are
lowercase.

---

## 4. `FFA/LokiRespawnComponent.as` — the respawn director (on the GameMode)

### Declaration (exact)

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class ULokiRespawnComponent : UActorComponent
{
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TArray<FVector> Starts;                       // filled by tag scan
    UPROPERTY(...) int              StartIndex;   // round-robin cursor for GetValidPlayerStart
    UPROPERTY(...) TSubclassOf<AActor@> BarrierActor;              // NEVER used in script
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
                   TSubclassOf<UGameplayEffect@> OnSpawnEffect;    // NULL in the script CDO
    UPROPERTY(...) TSet<ALokiPlayerState@> NonSpawningBotStates;   // "parked" bots
    UPROPERTY(...) int      HumansBeforeBotDespawn;   // = 3
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
                   float64  SpawnRadius;             // = 3000.0   (0x40a7700000000000)
    UPROPERTY(...) int      SpawnIndex;               // = 0   cursor for FindFurthestPlayerStart
    UPROPERTY(...) bool     HasCreatedPlayerStarts;   // = false
    UPROPERTY(BlueprintReadable, EditableOnDefaults, EditableOnInstance)
                   FOnUpdated OnPlayerStartsCreated;
}
// __InitDefaults(): SetComponentTickEnabled(true).   NOT replicated (no SetbReplicates).
```

### Spawn-point discovery

```angelscript
void Tick_Implementation(const float64 DeltaSeconds)
{
    if (!this.HasCreatedPlayerStarts && this.GeneratePlayerStarts()) {
        this.HasCreatedPlayerStarts = true;
        this.OnPlayerStartsCreated.Broadcast();
    }
}

UFUNCTION(UnrealName=GeneratePlayerStarts, BlueprintEvent, CanOverrideEvent)
bool GeneratePlayerStarts_Implementation()
{
    TArray<AActor@> Found;
    GetAllActorsOfClassWithTag(n"SafeTeamSpawnPathfindingAnchor", Found);   // AActor deduced via ?&
    for (auto A : Found)
        if (A != nullptr)
            this.Starts.Add(A.GetActorLocation());       // UFunction K2_GetActorLocation
    this.StartIndex = Math::RandRange(0, this.Starts.Num() - 1);
    return true;                                          // SetV1 v19 1 — UNCONDITIONAL
}
```

> ⚠ **This is the first thing that will break a standalone run.** `GeneratePlayerStarts` returns
> `true` even when the tag scan finds **zero** actors, so `HasCreatedPlayerStarts` latches true on
> the very first tick with an empty `Starts` array. Downstream, `GetValidPlayerStart_Implementation`
> computes `(StartIndex + 1) % Starts.Num()` — an integer modulo by zero — and
> `Math::RandRange(0, -1)` runs here too. **A level with at least one `SafeTeamSpawnPathfindingAnchor`-tagged
> actor is a hard prerequisite.** The bound signature is
> `UGameplayStatics::GetAllActorsOfClassWithTag(WorldContextObject, ActorClass, Tag, OutActors)`;
> the script sees the plugin's `?&`-templated wrapper, and the element type of the `TArray<AActor@>`
> destination makes the class filter `AActor` — i.e. *any* actor carrying the tag.

### Kill handling and the bot population control

```angelscript
void BeginPlay_Implementation()
{
    Loki::GetLokiGameState(__WorldContext).OnPlayerKilled.AddUFunction(this, n"OnPlayerKilled");
    Loki::GetLokiGameMode (__WorldContext).OnPlayerLogout.AddUFunction(this, n"OnLogout");
}

UFUNCTION(BlueprintCallable, CanOverrideEvent)
void OnPlayerKilled(const FPlayerKillEventData& Data)
{
    auto Victim = Data.VictimPlayerState;
    if (Victim == nullptr) return;

    bool bRespawnIt = !this.NonSpawningBotStates.Contains(Victim)
                   && (!Victim.IsABot() || this.ShouldSpawnBot());

    if (bRespawnIt) {
        auto PRC = this.GetPlayerRespawnComponent(Victim);
        if (Victim.GetOwner() != nullptr && PRC != nullptr)
            PRC.ScheduleRespawn();
        return;
    }
    Log::Log("[" + this.GetOwner().GetName() + "] Adding bot (" + Victim.PlatformPlayerID
             + ") to non-spawning list");
    this.NonSpawningBotStates.Add(Victim);       // park the bot: it will not come back
}

bool ShouldSpawnBot()
{
    auto GS = Loki::GetLokiGameState(__WorldContext);
    auto GM = Loki::GetLokiGameMode (__WorldContext);
    int Humans = 0;
    for (auto PS : GS.GetLokiPlayerStates())
        if (!PS.IsABot() && !GM.DisconnectedPlayerStates.Contains(PS.PlatformPlayerID))
            Humans++;
    return (Humans - this.HumansBeforeBotDespawn) <= this.NonSpawningBotStates.Num();
}
```

**The population rule, in words.** With `HumansBeforeBotDespawn = 3`: a killed bot respawns while
`Humans − 3 ≤ parkedBots`. At 0–3 humans the left side is ≤ 0 so bots *always* come back. As humans
join beyond 3, each extra human requires one more bot to already be parked before another bot is
allowed to respawn — so the bot count bleeds off one per kill as the lobby fills. When a human
leaves, the reverse happens:

```angelscript
UFUNCTION(BlueprintCallable, CanOverrideEvent)
void OnLogout(AController@ ExitingController)
{
    ALokiPlayerState@ Revive = nullptr;
    if (this.ShouldSpawnBot())
        for (auto PS : this.NonSpawningBotStates) { Revive = PS; break; }   // take the first

    if (Revive != nullptr) {
        this.NonSpawningBotStates.Remove(Revive);
        Log::Log("[" + this.GetOwner().GetName() + "] Removing bot from non-spawning list");
        this.Respawn(Revive);
    }
}
```

`ExitingController` is never read — the handler only cares that *someone* left.

### The actual spawn

```angelscript
UFUNCTION(BlueprintCallable, CanOverrideEvent)
void Respawn(ALokiPlayerState@ PS)
{
    if (!this.HasCreatedPlayerStarts) return;

    auto C = PS.GetLokiCharacter();
    if (C != nullptr && C.GetLivingState() == ELivingState::ELivingStateAlive) return;   // == 1

    auto GM = Loki::GetLokiGameMode(__WorldContext);
    FTransform Xf = this.GetValidPlayerStart(PS);
    C = GM.SpawnPlayer(PS, Xf, /*StartSpot*/nullptr, /*bEnsurePositionIsValid*/false);
    if (C == nullptr) return;

    if (this.OnSpawnEffect != nullptr) {
        auto ASC  = C.GetLokiAbilitySystem_BP();
        auto Ctx  = ASC.MakeEffectContext();
        auto Spec = ASC.MakeOutgoingSpec(this.OnSpawnEffect, /*Level*/0, Ctx);
        ASC.ApplyGameplayEffectSpecToSelf(Spec);      // UFunction BP_ApplyGameplayEffectSpecToSelf
    }
}

UFUNCTION(UnrealName=GetValidPlayerStart, BlueprintEvent, CanOverrideEvent)
FTransform GetValidPlayerStart_Implementation(ALokiPlayerState@ PS)
{
    this.StartIndex = (this.StartIndex + 1) % this.Starts.Num();
    return FTransform(this.Starts[this.StartIndex]);       // PS is IGNORED
}
```

`ALokiGameMode::SpawnPlayer(ALokiPlayerState, const FTransform&, AActor StartSpot = nullptr,
bool bEnsurePositionIsValid = false)` is the single native entry point through which every FFA
spawn passes.

> **Corrected against the disassembly.** `asdump` was mis-naming the parameter slot of any function
> that returns a **value type**, because the hidden by-value return pointer occupies a slot the
> parameter walk did not skip. `GetValidPlayerStart`, `GetValidPlayerStart_Implementation` and
> `GetRandomPointInCircle` in this module all printed `PS`/`Radius` on the return temp and their
> real parameter as `arg_m4`. **I fixed this in `asdump.py`** (§9); the return temp now prints as
> `__ret`, so `__ret = FTransform(v28);` is the by-value `return`.

### The better spawn selector — present but unused

```angelscript
UFUNCTION(BlueprintCallable, CanOverrideEvent)
FVector FindFurthestPlayerStart()     // 368 dwords / 207 instructions — the largest fn in the set
{
    if (this.Starts.Num() == 0) {
        Log::Warning("[" + this.GetOwner().GetName() + "] No player starts found");
        return FVector::ZeroVector;
    }
    TArray<FVector> Living;                                  // locations of all living players
    for (auto PS : Loki::GetLokiGameState(__WorldContext).GetLokiPlayerStates()) {
        auto C = PS.GetLokiCharacter();
        if (C != nullptr && C.IsAlive())
            Living.Add(C.GetActorLocation());
    }
    if (Living.Num() == 0) {                                 // nobody alive -> plain round robin
        this.SpawnIndex = (this.SpawnIndex + 1) % this.Starts.Num();
        return this.Starts[this.SpawnIndex];
    }
    FVector  Best     = this.Starts[0];
    float64  BestDist = 0.0;
    for (int i = -this.SpawnIndex; i + this.SpawnIndex < this.Starts.Num(); i++) {
        FVector Cand   = this.Starts[(this.Starts.Num() + i) % this.Starts.Num()];
        float64 MinDist = 0.0;
        for (auto P : Living) {                              // min distance to any living player
            float64 D = (Cand - P).Size();
            if (D < MinDist || MinDist == 0.0) MinDist = D;
        }
        if (MinDist > BestDist) { BestDist = MinDist; Best = Cand; }
        if (MinDist > this.SpawnRadius) {                    // 3000 uu — good enough, take it
            this.SpawnIndex = (this.SpawnIndex + 1) % this.Starts.Num();
            return Cand;
        }
    }
    return Best;
}
```

`FindFurthestPlayerStart` is **never called from any of the 78 script modules**. `Respawn` uses the
naive round-robin `GetValidPlayerStart` instead. Either a Blueprint/C++ caller uses it, or it is
dead. Same for `FVector2D GetRandomPointInCircle(const float64 Radius)`
(`Math::RandPointInCircle(float32(Radius))`, `BlueprintPure`) and the property `BarrierActor`.

---

## 5. `FFA/LokiPlayerRespawnComponent.as` — the per-player timer (on the PlayerState)

### Declaration (exact) — note the replication

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class ULokiPlayerRespawnComponent : UActorComponent
{
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance,
              Replicated, ReplicationCondition=0 /*COND_None*/, RepNotify,
              meta.ReplicatedUsing=OnRep_RespawnTime)
    float64 RespawnTime;                            // = -1.0

    UPROPERTY(...) ALokiPlayerController@ LocalPC;  // NEVER touched anywhere in script
    UPROPERTY(...) float64 LocalRespawnTime;        // = -1.0   (ticked down on BOTH sides)
    UPROPERTY(...) FOnUpdated OnRespawnTimeUpdated;
    UPROPERTY(...) float64 InitialSpawnDelay;       // = 10.0
    UPROPERTY(...) float64 SpawnDelay;              // = 10.0
    UPROPERTY(...) bool    IsCombatPhase;           // = false
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
                   bool    bOnlyScheduleRespawnsDuringCombatPhase;   // = false
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
                   bool    bStartTimerOnlyOnKill;                    // = false
}
// __InitDefaults(): SetbReplicates(true) ; SetComponentTickEnabled(true).
```

**`RespawnTime` is the only replicated property in the entire FFA set.** Everything else is either
server-side (the GameMode's director) or client-local (the widget).

### Arming — server only

```angelscript
void BeginPlay_Implementation()
{
    if (Loki::LokiIsClient(__WorldContext)) return;                    // hard client bail

    auto PS = cast<ALokiPlayerState@>(this.GetOwner());
    if (PS != nullptr) PS.OnDisconnected.AddUFunction(this, n"OnPlayerDisconnected");

    auto GS = Loki::GetLokiGameState(__WorldContext);
    if (GS != nullptr) {
        if (int(GS.GetCurrentPhase()) == ERoundPhase::EGP_Combat)      // == 7
            this.OnRoundPhaseChanged(ERoundPhase::EGP_Combat);         // already in combat
        else
            GS.OnRoundPhaseChanged.AddUFunction(this, n"OnRoundPhaseChanged");
    }

    auto RC = cast<ULokiRespawnComponent@>(Loki::GetLokiGameMode(__WorldContext)
                    .GetComponentByClass(ULokiRespawnComponent::StaticClass()));
    if (RC != nullptr) {
        if (RC.HasCreatedPlayerStarts) this.OnPlayerStartsCreated();
        else RC.OnPlayerStartsCreated.AddUFunction(this, n"OnPlayerStartsCreated");
    }
    this.CheckSetInitialRespawn();
}

void OnRoundPhaseChanged(const ERoundPhase NewPhase)
{
    if (int(NewPhase) != ERoundPhase::EGP_Combat) return;
    this.IsCombatPhase = true;
    this.CheckSetInitialRespawn();
    Loki::GetLokiGameState(__WorldContext).OnRoundPhaseChanged.Unbind(this, n"OnRoundPhaseChanged");
}

void CheckSetInitialRespawn()
{
    if (!Loki::LokiIsServer(__WorldContext)) return;
    if (!this.IsCombatPhase)                return;

    auto RC = cast<ULokiRespawnComponent@>(Loki::GetLokiGameMode(__WorldContext)
                    .GetComponentByClass(ULokiRespawnComponent::StaticClass()));
    if (RC == nullptr || !RC.HasCreatedPlayerStarts) return;
    if (!this.ShouldScheduleRespawn())               return;

    this.SetRespawnTime(this.InitialSpawnDelay);      // 10 s
}
```

**This is the join gate.** `CheckSetInitialRespawn` is called from three places (`BeginPlay`,
`OnRoundPhaseChanged`, `OnPlayerStartsCreated`) and every one of them requires **all three** of:
server + `ERoundPhase::EGP_Combat` + the director's `HasCreatedPlayerStarts`. Whichever arrives last
fires the initial 10-second spawn.

### Countdown and respawn

```angelscript
void Tick_Implementation(const float64 DeltaSeconds)
{
    if (this.LocalRespawnTime > 0) {
        this.LocalRespawnTime -= DeltaSeconds;                          // ticks on BOTH sides
        if (Loki::LokiIsServer(__WorldContext) && this.LocalRespawnTime <= 0) {
            this.Respawn();
            this.RespawnTime      = 0;
            this.LocalRespawnTime = 0;
        }
    }
}

void SetRespawnTime(const float64 Time)
{
    if (Loki::LokiIsServer(__WorldContext)) {
        this.RespawnTime      = Time;          // replicated -> OnRep on the client
        this.LocalRespawnTime = Time;
    }
    this.OnRespawnTimeUpdated.Broadcast();
}

UFUNCTION(BlueprintCallable, CanOverrideEvent)
void OnRep_RespawnTime()
{
    this.LocalRespawnTime = this.RespawnTime;   // client seeds its own countdown
    this.OnRespawnTimeUpdated.Broadcast();
}

void Respawn()
{
    this.RespawnTime = 0;
    auto PS = cast<ALokiPlayerState@>(this.GetOwner());
    if (PS != nullptr && PS.bDisconnected) return;

    auto RC = cast<ULokiRespawnComponent@>(Loki::GetLokiGameMode(__WorldContext)
                    .GetComponentByClass(ULokiRespawnComponent::StaticClass()));
    if (RC != nullptr)
        RC.Respawn(cast<ALokiPlayerState@>(this.GetOwner()));
}
```

The client runs the same `LocalRespawnTime -= DeltaSeconds` for a smooth on-screen countdown but
the `Respawn()` branch is server-gated, so the client's copy is display only.

### Gating and the one inbound RPC

```angelscript
UFUNCTION(BlueprintCallable, CanOverrideEvent)
bool ShouldScheduleRespawn()
{
    if (this.bOnlyScheduleRespawnsDuringCombatPhase) {
        auto GS = Loki::GetLokiGameState(__WorldContext);
        if (IsValid(GS) && int(GS.GetCurrentPhase()) != ERoundPhase::EGP_Combat)
            return false;
    }
    auto PS = cast<ALokiPlayerState@>(this.GetOwner());
    if (IsValid(PS)) {
        auto C = PS.GetLokiCharacter();
        if (!IsValid(C)) return true;                                   // never spawned yet
        if (!this.bStartTimerOnlyOnKill
            || int(C.GetLivingState()) == ELivingState::ELivingStateDead)   // == 0
            return true;
    }
    return false;
}

UFUNCTION(BlueprintCallable, CanOverrideEvent)
void ScheduleRespawn()
{
    if (this.ShouldScheduleRespawn())
        this.SetRespawnTime(this.GetSpawnDelay());      // BP event; _Implementation -> SpawnDelay (10 s)
}

UFUNCTION(BlueprintCallable, CanOverrideEvent)
void OnPlayerDisconnected()
{
    auto PS = cast<ALokiPlayerState@>(this.GetOwner());
    if (PS == nullptr) return;
    auto C = PS.GetLokiCharacter();
    if (!PS.bDisconnected
        && (C == nullptr || int(C.GetLivingState()) != ELivingState::ELivingStateAlive))
        this.ScheduleRespawn();
}

UFUNCTION(UnrealName=AuthRequestRespawn, BlueprintCallable, BlueprintEvent, NetServer)
void AuthRequestRespawn_Implementation() { this.Respawn(); }
```

> ⚠ **`AuthRequestRespawn` is a client→server RPC with no validation and no timer check.** It is
> `NetServer` **without** `NetValidate` and **without** `Unreliable`, and its body goes straight to
> `Respawn()`. The only guards that survive are inside the director's `Respawn(PS)` — you must not
> already be alive, and player starts must exist. So a dead client can respawn *immediately*,
> skipping the 10-second wait entirely.

`bool IsRespawnTimeSet() { return this.RespawnTime > 0; }` exists and is never called.
`LocalPC` is declared and never touched.

---

## 6. `FFA/Comp_PC_LokiRespawnComponent.as` + `FFA/RespawnTimerWidget.as` — the client UI

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class UComp_PC_LokiRespawnComponent : UActorComponent
{
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TSubclassOf<UUserWidget@> RespawnTimerWidget;        // NULL in the script CDO
}
// __InitDefaults(): SetbReplicates(true).    (no tick)

void BeginPlay_Implementation()
{
    if (!Loki::LokiIsClient(__WorldContext)) return;
    auto PC = cast<ALokiPlayerController@>(this.GetOwner());
    if (PC != nullptr && this.RespawnTimerWidget != nullptr) {
        auto W = WidgetBlueprint::CreateWidget(__WorldContext, this.RespawnTimerWidget, PC);
        W.AddToViewport(0);
    }
}
```

```angelscript
UCLASS(SuperIsCodeClass, Abstract, Placeable)
class URespawnTimerWidget : UUserWidget
{
    UPROPERTY(...) ULokiPlayerRespawnComponent@ PSC;

    void Construct_Implementation() {                          // UFunction Construct
        FOnPlayerStateAssigned D;
        D.BindUFunction(this, n"OnPlayerStateAssigned");
        Loki::TryGetLocalLokiPlayerState(__WorldContext, D);   // async; fires when the PS arrives
    }

    UFUNCTION(BlueprintCallable, CanOverrideEvent)
    void OnPlayerStateAssigned(ALokiPlayerState@ PlayerState) {
        this.PSC = cast<ULokiPlayerRespawnComponent@>(
                       PlayerState.GetComponentByClass(ULokiPlayerRespawnComponent::StaticClass()));
        if (this.PSC != nullptr)
            this.PSC.OnRespawnTimeUpdated.AddUFunction(this, n"OnRespawnTimeUpdated");
    }

    void Tick_Implementation(const FGeometry& MyGeometry, const float64 InDeltaTime) {
        if (this.PSC != nullptr) this.UpdateTimerText(this.PSC.LocalRespawnTime);
    }
    UFUNCTION(BlueprintCallable, CanOverrideEvent)
    void OnRespawnTimeUpdated() {
        if (this.PSC != nullptr) this.UpdateTimerText(this.PSC.LocalRespawnTime);
    }
    UFUNCTION(UnrealName=UpdateTimerText, BlueprintEvent, CanOverrideEvent, NoOp)
    void UpdateTimerText_Implementation(const float64 TimeUntilRespawn) { }   // BP subclass draws it

    UFUNCTION(BlueprintCallable, CanOverrideEvent)
    void OnRequestRespawn() {                       // the "respawn now" button
        if (this.PSC != nullptr) this.PSC.AuthRequestRespawn();
    }
}
```

The class is **`Abstract`**, so a Blueprint subclass is mandatory — the C++/script side draws
nothing. `OnRequestRespawn` is the UI hook onto the unvalidated `NetServer` RPC.

---

## 7. End-to-end state machines

### Match lifecycle

```
[C++ ALokiDropInGameMode / ALokiGameMode drives ERoundPhase]
  EGP_ServerStartup(0) → BeginInit(1) → Pre(2) → FinishInit(3) → SpawnSelect(4)
                       → SpawnReveal(5) → Lineup(6) → **EGP_Combat(7)** → Post(8) → Shutdown(9)

first Tick of ULokiRespawnComponent (on the GameMode)
  └─ GeneratePlayerStarts(): tag-scan "SafeTeamSpawnPathfindingAnchor" → Starts[]
     HasCreatedPlayerStarts = true ; OnPlayerStartsCreated.Broadcast()

per player, ULokiPlayerRespawnComponent::BeginPlay (server only)
  └─ waits on: EGP_Combat  AND  HasCreatedPlayerStarts
     └─ CheckSetInitialRespawn() → SetRespawnTime(InitialSpawnDelay = 10 s)

login:  OnPostLogin = {} ,  HandleStartingNewPlayer = {}          ← NO spawn on login
logout: AFFAGameMode::OnLogout   → 0 live humans ⇒ GracefullyShutdown("AllPlayersDisconnected", 0)
                                 → destroy the departing human's PlayerState
        ULokiRespawnComponent::OnLogout → un-park one bot and respawn it (if allowed)
end:    ShouldTeamBeEliminated ≡ false ⇒ never ends by elimination
```

### Respawn loop

```
 kill ──► ALokiGameState.OnPlayerKilled ──► ULokiRespawnComponent::OnPlayerKilled
            │
            ├─ human, or bot allowed by ShouldSpawnBot()
            │     └─► victim's ULokiPlayerRespawnComponent.ScheduleRespawn()
            │            └─ ShouldScheduleRespawn()? → SetRespawnTime(GetSpawnDelay() = 10 s)
            │                 server: RespawnTime = LocalRespawnTime = 10   [REPLICATED]
            │                 both:   OnRespawnTimeUpdated.Broadcast()
            │                                     │
            │      client ◄── OnRep_RespawnTime ──┤   LocalRespawnTime = RespawnTime
            │      widget ◄── OnRespawnTimeUpdated / Tick ──► UpdateTimerText(LocalRespawnTime)
            │
            │      Tick (both sides): LocalRespawnTime -= DeltaSeconds
            │      Tick (server only, on reaching <= 0):
            │         ULokiPlayerRespawnComponent::Respawn()
            │            └─ not bDisconnected
            │               └─► ULokiRespawnComponent::Respawn(PS)
            │                     ├─ requires HasCreatedPlayerStarts
            │                     ├─ bails if the character is already ELivingStateAlive
            │                     ├─ Xf = GetValidPlayerStart(PS)      (round-robin over Starts[])
            │                     ├─ C  = ALokiGameMode::SpawnPlayer(PS, Xf, null, false)
            │                     └─ if OnSpawnEffect: ASC.ApplyGameplayEffectSpecToSelf(spec)
            │                            │
            │                            └─► ALokiGameMode fires OnPlayerSpawned_BP
            │                                  └─ AFFAGameMode: OnCharacterRespawned →
            │                                       ResetAllCooldowns + 3× Bandage + 1× Armor
            │                                     first time only: AuthGrantLevel(15) + InitPlayer
            │
            └─ bot NOT allowed → park it in NonSpawningBotStates  (log line, never respawns
                                 until a human leaves and OnLogout un-parks it)

 shortcut: widget "respawn now" → OnRequestRespawn → AuthRequestRespawn [NetServer]
           → ULokiPlayerRespawnComponent::Respawn() — skips the timer entirely
```

---

## 8. Running FFA standalone — every prerequisite visible in the script

### Hard requirements (each one is read by decompiled code)

1. **A level with ≥ 1 actor tagged `SafeTeamSpawnPathfindingAnchor`.** These are the *only* spawn
   points. Zero of them ⇒ `Starts` is empty ⇒ `GetValidPlayerStart` does `% 0`.
2. **`ALokiGameState` must exist** — `Loki::GetLokiGameState` is dereferenced without a null check
   in `ULokiRespawnComponent::BeginPlay` and `ShouldSpawnBot`.
3. **`ALokiGameMode` must exist and must carry a `ULokiRespawnComponent`.** Three separate call
   sites do `GetLokiGameMode(...).GetComponentByClass(ULokiRespawnComponent::StaticClass())`.
   *(Because the GameMode does not exist on clients, this component is inherently server-only.)*
4. **Every `ALokiPlayerState` must carry a `ULokiPlayerRespawnComponent`** — the director looks it
   up per victim (`GetPlayerRespawnComponent`) and the widget looks it up on the local PS.
5. **Round phase must reach `ERoundPhase::EGP_Combat` (7).** Until then `IsCombatPhase` stays false
   and the initial respawn is never armed. `AFFAGameMode` inherits `ALokiDropInGameMode`, so this
   is *the same drop-in phase machine* the project is already stuck behind at
   "DROP IN GEAR UP LOADING". FFA does not bypass it — but see §9 for the shortcut it does open.
6. **`AFFAGameMode.BandageItem` and `.ArmorItem` must be set** in a Blueprint subclass. The script
   CDO leaves both null and `__InitDefaults` only sets `LevelToGrant = 15`, so every respawn
   currently calls `SpawnActor(nullptr, …)` twice.
7. **For bots:** the ten `Hero:*` primary assets must resolve through `ULokiAssetLoader`
   (i.e. the AssetManager must have the `Hero` primary asset type scanned) and each
   `ULokiHeroAsset.GameplayBlueprint` must load synchronously. This is exactly the
   `LokiAssetManager` territory the project already knows.
8. **Something outside Angelscript must call `TrySpawnTeam` / `SpawnBot`.** Not present in any of
   the 78 modules.

### Soft / cosmetic

9. `UComp_PC_LokiRespawnComponent.RespawnTimerWidget` must be set, and a **non-abstract Blueprint
   subclass of `URespawnTimerWidget`** must exist (the base is `Abstract` and `UpdateTimerText`
   is empty).
10. `ULokiRespawnComponent.OnSpawnEffect` (spawn protection?) is null by default — optional.
11. `AFFAGameMode::InitPlayer` is an empty BP event; a subclass may implement it.

### Server-authority-only surface (flagged)

| item | gate |
|---|---|
| `ULokiPlayerRespawnComponent::BeginPlay` | returns immediately if `LokiIsClient` |
| `CheckSetInitialRespawn` | `if (!LokiIsServer) return;` |
| `SetRespawnTime` | only *writes* on server; broadcasts on both |
| `Tick_Implementation` → `Respawn()` | `LokiIsServer && LocalRespawnTime <= 0` |
| `ULokiRespawnComponent` (whole class) | lives on the GameMode ⇒ server-only by construction; **not** `bReplicates` |
| `ALokiGameMode::SpawnPlayer`, `GracefullyShutdown` | native, server |
| `ALokiCharacter::AuthGrantLevel`, `ApplyGameplayEffectSpecToSelf` | native, server (the `Auth` prefix is the codebase's own convention) |
| `RespawnTime` | the **only** replicated property; `COND_None`, RepNotify `OnRep_RespawnTime` |
| `AuthRequestRespawn` | the **only** client→server path; `NetServer`, **no** `NetValidate` |
| `UComp_PC_LokiRespawnComponent::BeginPlay` | `if (!LokiIsClient) return;` — client-only |

---

## 9. What this means for the project

**1. There is a second, much smaller playable mode than the BR, and its whole logic layer is now
readable.** Six modules, one class each, no zone, no drop plane usage in script, no team
elimination, no match-end condition to satisfy. Compared to the BR drop-in path this is a very
short runway.

**2. A concrete new lever for forcing a playable spawn.** The project's tutorial route currently
force-opens a game mode and hand-builds a hero. FFA exposes three *native, already-wired* entry
points that do the same job through the game's own code path, all reachable from the existing
game-thread native-call primitive:

* `ULokiRespawnComponent::Respawn(ALokiPlayerState@)` — `UFUNCTION(BlueprintCallable)`, UFunction
  name `Respawn`, AngelScript function id **84893** (the operand of the `CALLINTF` its own callers
  use). It does `GetValidPlayerStart` → `ALokiGameMode::SpawnPlayer` → GameplayEffect: one call
  spawns a player at a valid start.
* `ULokiPlayerRespawnComponent::AuthRequestRespawn` — a `NetServer` RPC **with no validation**,
  callable from the client side, that reaches the same place.
* `ALokiGameMode::SpawnPlayer(PlayerState, FTransform, StartSpot, bEnsurePositionIsValid)` — the
  native function both of the above funnel into. This is the "spawn a real, mode-registered hero"
  primitive the DS/tutorial work has been approximating.

**3. The drop-pod path is optional.** FFA never touches `ALokiDropShip` / `ALokiDropPod`. It
spawns straight to a ground transform via `SpawnPlayer`. If a revival can get the round phase to
`EGP_Combat` and put one tagged anchor in the world, it gets a spawned, levelled, equipped hero
without the drop sequence that S89/S90 stalled on.

**4. `EGP_Combat` is the single gate to attack.** Every arming path in the timer component is
`server && IsCombatPhase && HasCreatedPlayerStarts`. `ERoundPhase` is a plain replicated enum on
`ALokiGameState` with `GetCurrentPhase()` bound — a far smaller target than the game-feature-toggle
carrier of S88/S89.

**5. A greppable content hook.** `SafeTeamSpawnPathfindingAnchor` is a level actor **tag**, not an
asset name. Any packaged level whose actors carry it can host FFA. That is a cheap next probe
against the extracted level assets, and it is also trivially satisfiable at runtime — the tag scan
runs every tick until it succeeds, so spawning one tagged actor into a live world is enough.

**6. Ten confirmed internal hero ids.** `assault, firefox, freeze, sniper, flex, hookguy,
rocketjumper, Storm, BurstCaster, BountyHunter` — all ten already appear in this project's backend
in exactly the `Hero:<id>` `FPrimaryAssetId` form, so this is an independent cross-check of the
roster naming, and it names the exact heroes the shipped bot code is known to work with.

**7. Bots are native and self-contained.** `ALokiBotController` with personality/difficulty/goal/
spell selection is C++; the only thing the game needs from the script layer is
`SetSpawnableBots(list)`. If a revival can call `ULokiBotSpawnerComponent::TrySpawnTeam(Difficulty)`
once, the AI runs itself.

**8. Tool fixes that benefit every other module.** Working these six files turned up two real
decompiler defects, both now fixed in the shared `tools/asdump/asdump.py`:

* **Hidden by-value return pointer not skipped in the parameter walk.** `param_offsets` started at
  `-2` for methods and ignored `DoesReturnOnStack()`, so for any function returning a value type
  the hidden return temp wore `param0`'s name and the real `param0` printed as `arg_mN`. Measured:
  **34** functions return on the stack corpus-wide, **20** of them take parameters — all 20 were
  mis-named. Non-FFA example: `LokiScriptUtility::LinearColorToVector` read `arg_m2.B` instead of
  `Color.B`. Fixed; the hidden slot now prints as `__ret`. `FORMAT.md` §3 updated.
* **Void `RET` emitted before a pending call statement.** `op_RET` returned early for void
  functions without flushing `pending`, and `run_block` flushed at end-of-block, so the call landed
  *after* `return;`. 2 sites corpus-wide, one of them `AFFAGameMode::ResetArmor`. Fixed.

Both were verified by re-running: byte accounting still 100.0000% (0 unaccounted), 1,463/1,463
streams decoded, 3,530/3,530 member accesses resolved, and the independent dword-depth audit
unchanged at 1,449/1,463 (99.04%). A third fix (`op_REFCPY` operand order — `this.PSC = v8`, not
`v8 = this.PSC`) landed concurrently from another worker on the same tool and also affects
`RespawnTimerWidget.as`.

---

## 10. What I could NOT recover

Stated plainly.

* **Local variable names and line numbers.** Never serialised in a shipping build
  (`DeclaredAt == 0`, empty `LineNumbers`/`VariableInfo` for all 1,463 functions). Locals are `vN`.
  This is permanent.
* **What triggers bot spawning, and how many bots.** `TrySpawnTeam` / `SpawnBot` /
  `MakeNewBotController` are never called from Angelscript. The caller is C++ or Blueprint and is
  not in these files.
* **Where `UFFABotSpawnerComponent` is attached.** Nothing in the script identifies its owner.
* **How the respawn components get attached to PlayerState / PlayerController.** The
  `ALokiGameMode::Additional*Components` arrays are the obvious mechanism but that is inference
  from a bound property name, not decompiled fact.
* **Bot AI behaviour.** `ALokiBotController` is native; the §3 listing is a name-level census from
  `Binds.Cache`, explicitly not a decompile.
* **The FFA map, GameMode Blueprint, `BandageItem`, `ArmorItem`, `OnSpawnEffect`, `BarrierActor`,
  and the concrete `URespawnTimerWidget` subclass.** All are `TSubclassOf` properties left null in
  the script CDO; their values live in packaged Blueprint/asset data, not in these caches. The
  project's known level list (`LVL_Battlefield`, `LVL_Lastman`, `LVL_Domination`, `LVL_Holdout`,
  `LVL_TugOfWar`, …) contains no `LVL_FFA`; **I did not determine which level, if any, hosts FFA**,
  and I am not going to guess from a name.
* **Which UFunction name the generated overrides carry** on the script class —
  `OnLogout` (as stored in the cache) or `K2_OnLogout` (the parent's bound UFunction name). A shim
  should probe both.
* **`FunctionTraits` bits 5/13/18** — all six FFA classes' methods carry `0x20` (bit 5); meaning
  undecoded, reported raw, matching `FORMAT.md` §5.
* **Residual decompiler risk.** Per the tool's own honesty note, the thing most likely to be wrong
  is argument accounting inside `_do_call`; a wrong-but-plausible argument list would not announce
  itself. For the functions that matter here I read the disassembly appendix directly, which is how
  the two corrections in §2 and §4 were found. Anyone acting on a specific call should do the same —
  every operand in `tools/asdump/out/modules/FFA/*.as.txt` is named.
