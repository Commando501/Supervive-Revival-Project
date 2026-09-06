# SUPERVIVE Angelscript — CORE GAMEPLAY layer

**Date:** 2026-07-26 · **Build:** shipping, 2025-12-17 · **Source:** `Loki/Script/PrecompiledScript.Cache`
(+ `Binds.Cache`, `Binds.Cache.Headers`), decompiled with `tools/asdump/asdump.py`.

This document covers the fifteen Angelscript modules that extend the classes this project
reverse-engineers by hand every session:

| module | source path | classes | fns | bytecode |
|---|---|---:|---:|---:|
| GameState | `GameState/LokiGameState.as` | 1 | 4 | 240 B |
| PlayerController | `PlayerController/LokiPlayerController.as` | 4 | 44 | 1,840 B |
| **PlayerCheats** | `PlayerController/LokiPlayerCheats.as` | 1 | 51 | 5,472 B |
| DragCamera | `PlayerController/LokiDragCameraComponent.as` | 1 | 13 | 3,112 B |
| HeroCharacter | `Character/LokiHeroCharacter.as` | 2 | 20 | 920 B |
| HeroGroundIndicator | `Character/LokiHeroGroundIndicator.as` | 1 | 8 | 1,120 B |
| MajorStatusEffect | `Core/Components/LokiMajorStatusEffectComponent.as` | 1 | 11 | 992 B |
| ScriptUtility | `Core/LokiScriptUtility.as` | 0 | 4 | 812 B |
| AimingVisComponent | `Core/AimingVis/LokiAimingVisComponent.as` | 2 | 89 | 11,756 B |
| AimingLaser | `Core/AimingVis/LokiAimingLaser.as` | 3 | 51 | 10,836 B |
| RangeMarker | `Core/AimingVis/LokiAimingLaserRangeMarker.as` | 1 | 11 | 1,588 B |
| SpreadLines | `Core/AimingVis/LokiAimingLaserSpreadLines.as` | 1 | 10 | 3,448 B |
| SpreadLines_HookGuy | `.../HunterSpecific/LokiAimingLaserSpreadLines_HookGuy.as` | 1 | 6 | 604 B |
| SpreadLines_Ronin | `.../HunterSpecific/LokiAimingLaserSpreadLines_Ronin.as` | 1 | 7 | 784 B |
| AimingLaser_Huntress | `.../HunterSpecific/LokiAimingLaser_Huntress.as` | 1 | 21 | 5,112 B |

(Function counts are every compiled function record in the module, including generated
delegate machinery, constructors, destructors and the three module-level `StaticClass` /
factory / `Spawn` boilerplate functions — so they overstate the hand-written surface,
especially for `LokiPlayerController.as` where 30 of 44 are delegate plumbing.)

Full reconstructed sources (declarations + decompiled bodies + per-function symbol-resolved
disassembly) are at `tools/asdump/out/modules/<dir>/<name>.as.txt`. A body-only copy without
the disassembly appendix is at `tools/asdump/out_noasm/`.

**How to regenerate:**
```
cd "G:\git\Supervive Revival Project\tools\asdump"
python asdump.py                                 # full, with disassembly -> out/
python asdump.py --no-asm --out out_noasm        # bodies only
python asdump.py --validate                      # self-check, writes nothing
```

**Reading conventions used below.** Declarations (class names, bases, property types,
`UPROPERTY`/`UFUNCTION` flags, function names, parameter names/types/defaults) are stored
verbatim in the cache and are **exact**. Bodies are decompiled from bytecode: locals are
`vN` (a shipping cache never stored local names), statements are in bytecode order, and
expressions are not folded. Where I state behaviour I have read the body; where I am
inferring from a name I say so.

---

## 0. Three corrections this decompile forces

### 0.1 ★ The Angelscript layer is NOT thin — S74's inventory was wrong by ~8×

`docs/session-74-routeB-as-native-split.md` concluded, and every session since has assumed:

> "**only 18 classes are Angelscript**… a THIN Angelscript layer (hero, PC, GameState,
> day/night, airship, a status-effect component, 2 widgets, cheats) sitting on a NATIVE
> C++ core… **There is NO** `LokiRoundGameMode_AS` / `LokiGameMode_AS` /
> `LokiDropInGameMode_AS` **or deploy AS class**… `ALokiDropPlane`, `ALokiDropPod*`,
> `Comp_PC_LokiRespawnComponent`… **none carry the `_AS` suffix**."

That inventory was produced by string-scanning the cache for names ending in `_AS`. **The
`_AS` suffix is a naming convention, not a marker** — UE-Angelscript uses it only when a
script class shadows an identically-named C++ class. Measured from the parsed cache:

```
script classes total          110
  named *_AS                    9      <- what S74 found
  UObject-shaped, NOT *_AS     67      <- what S74 missed
  (remainder = script structs and generated delegate types)
```

The 67 include, verbatim from the class table: `ALokiDropShip`, `ALokiDropPod`,
`ALokiDropPodLaser`, `ALokiDropPodImpactIndicator`, `ULokiDropPhase_PlayerStateComponent`,
`UComp_PC_LokiRespawnComponent`, `ULokiPlayerRespawnComponent`, `ULokiRespawnComponent`,
`AFFAGameMode`, `ABarracudaGameMode`, and 28 modules of Barracuda MOBA code.

So the specific claim "the drop-phase / respawn machinery is native C++, not Angelscript"
is **false** — those actors are script and are now readable. What *does* survive from S74
is narrower and still true: there is no `LokiRoundGameMode` / `LokiDropInGameMode` script
class, so the *round/match* gamemode itself remains native.

This is outside my module scope, but it is load-bearing for the project's route selection
and it came out of the same parse, so it is recorded here.

### 0.2 `ConsoleCommandCheat*` functions are **not** console commands

Every script cheat is named `ConsoleCommandCheatXxx`, which reads like an `exec`. It is
not. Measured over all **500** `UFUNCTION`s in the entire script layer:

```
CanOverrideEvent 471 · BlueprintCallable 326 · BlueprintEvent 226 · BlueprintOverride 106
NoOp 43 · BlueprintPure 35 · NetMulticast 23 · Static 22 · NetServer 22 · ConstMethod 19
BlueprintAuthorityOnly 16 · NetClient 3 · Unreliable 3 · Exec 0        <-- zero
```

**Not one script UFUNCTION carries `Exec`.** The native `ALokiPlayerCheats` functions do
(`CheatTeleportLocation [Exec,Native,BPCallable]` etc., per `docs/session-74-cheat-enum-dump.txt`),
which is why the project could reach those. The script ones are `BlueprintCallable` only —
they must be invoked as UFunctions (Blueprint, or this project's `ProcessInternal`
direct-thunk primitive), never typed into a console.

### 0.3 Tool corrections made during this pass

Three real decompiler bugs were found by checking output against its own disassembly and
fixed in `tools/asdump/asdump.py`; all validation numbers are unchanged and an independent
re-check shows **0 of 7,491 named callees dropped**. Details in `tools/asdump/README.md`.

1. **`REFCPY` printed every handle assignment backwards** (destination is the *top* of the
   stack). 116 sites corpus-wide. `ALokiAimingLaser::UpdateOwner` read `HeroOwner =
   this.OwnerHero;` when it in fact assigns `this.OwnerHero = HeroOwner;`.
2. **Float immediates printed as raw integers.** `this.CameraPickupRadius =
   13830554455654793216` is `-1.0`. ~270 tuning constants became readable — every number
   quoted in this document depends on that fix.
3. **`LoadThisR`/`LDV`/… did not model the value register**, so members passed *by
   reference* printed as stale stack junk: `Math::Lerp(this.RangeMax, this.RangeMin, t)`
   rendered as `Math::Lerp(v5, v5, v4)`.

---

## 1. `GameState/LokiGameState.as` — one class, one property

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class ALokiGameState_AS : ALokiGameState        // /Script/Loki.LokiGameState
{                                               // ../../../Loki/Source/Loki/LokiGameState.h
    UPROPERTY(BlueprintReadable, EditableOnDefaults, InstancedReference,
              meta.EditInlineDefaults=true, meta.DefaultComponent=True)
    ULokiGameStateUAVComponent@ UAVComponent;

    ALokiGameState_AS() { return; }             // ctor body is empty
}
```

That is the **entire** script extension of `LokiGameState`: a single default subobject.
No methods, no replicated properties, no overrides. The 240 bytes of bytecode are the
three boilerplate module-level functions (`StaticClass`, factory, `Spawn`) plus the empty
constructor.

**Why it matters here.** The project's `LokiGameStateStub` mirrors the *native*
`/Script/Loki.LokiGameState` with 43 net properties (S70). This says the real game's
GameState chain is `BP_LokiGameState_… : ALokiGameState_AS : ALokiGameState`, and the only
thing the script tier inserts is a `meta.DefaultComponent` — an instanced UAV component
constructed at CDO time. It carries **no `Replicated` UPROPERTY**, so it adds nothing to
the replication layout the stub has to reproduce. That is a genuinely useful negative
result: the script tier is not why the stub's GameState differs.

`ALokiPlayerCheats_AS::AuthCheatExecuteUAV_Implementation` is the only consumer in the
whole script layer — it casts the GameState to `ALokiGameState_AS` to reach `UAVComponent`.

---

## 2. `PlayerController/LokiPlayerController.as` — three delegates, three BP hooks

```angelscript
event FOnSneakPressedDelegate;                  // no parameters
event FOnSneakReleasedDelegate;                 // no parameters
event FOnPracticeRespawnPressedDelegate;        // no parameters

UCLASS(SuperIsCodeClass, Placeable)
class ALokiPlayerController_AS : ALokiPlayerController   // /Script/Loki.LokiPlayerController
{                                                        // Loki/Source/Loki/LokiPlayerController.h
    UPROPERTY(BlueprintReadable, EditableOnDefaults, InstancedReference,
              meta.EditInlineDefaults=true, meta.DefaultComponent=True)
    ULokiPlayerControllerUAVComponent@ UAVComponent;

    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    FOnSneakPressedDelegate          OnSneakPressed;
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    FOnSneakReleasedDelegate         OnSneakReleased;
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    FOnPracticeRespawnPressedDelegate OnPracticeRespawnPressed;

    UFUNCTION(BlueprintCallable, CanOverrideEvent) void ClientGliderActivated();
    UFUNCTION(BlueprintCallable, CanOverrideEvent) void ClientGliderDeactivated();
    UFUNCTION(BlueprintCallable, CanOverrideEvent) void SpectatorMapMove();

    // each forwards to a NoOp BlueprintEvent that content overrides:
    UFUNCTION(UnrealName=BP_OnClientGliderActivated,  BlueprintEvent, CanOverrideEvent, NoOp,
              meta.DisplayName=On Client Glider Activated)   protected void BP_OnClientGliderActivated_Implementation();
    UFUNCTION(UnrealName=BP_OnClientGliderDectivated, BlueprintEvent, CanOverrideEvent, NoOp,
              meta.DisplayName=On Client Glider Deactivated) protected void BP_OnClientGliderDectivated_Implementation();
    UFUNCTION(UnrealName=BP_OnSpectatorMapMove,       BlueprintEvent, CanOverrideEvent, NoOp,
              meta.DisplayName=On Spectator Map Move)        protected void BP_OnSpectatorMapMove_Implementation();
}
```

(`Dectivated` is a typo in the shipping game, preserved.)

The three `_Implementation` bodies are literally `return;` — they are `NoOp` extension
points for Blueprint. The three `ClientGlider*` / `SpectatorMapMove` entry points are
one-line forwarders. The other 35 functions in the module are the compiler-generated
delegate machinery (`Broadcast` / `AddUFunction` / `Unbind` / `UnbindObject` / `IsBound` /
`Clear` / ctor / copy-ctor / `opAssign` / dtor, ×3 delegate types).

**Not recoverable:** nothing in the script layer ever calls
`OnSneakPressed.Broadcast()`, `OnSneakReleased.Broadcast()` or
`OnPracticeRespawnPressed.Broadcast()` — I grepped all 78 modules. They are broadcast from
native C++ or Blueprint. So the *existence* and *signature* of the hooks is exact; who
fires them is not in the cache.

**Useful to the project regardless:** `OnPracticeRespawnPressed` proves a practice-mode
respawn input path exists on the PC, and `ClientGliderActivated/Deactivated` are the
glider state callbacks — both are named UFunctions that can be bound or invoked.

---

## 3. `PlayerController/LokiPlayerCheats.as` — the script cheat set ★

`ALokiPlayerCheats_AS : ALokiPlayerCheats` (`/Script/Loki.LokiPlayerCheats`,
`Loki/Source/Loki/Cheats/LokiPlayerCheats.h`).

**This is a set of cheats the project has never seen and cannot have tested.** The S74
enumeration (`docs/session-74-cheat-enum-dump.txt`) walked the *native* `UClass
LokiPlayerCheats` and found 65 UFunctions. `ALokiPlayerCheats_AS` is a **different
UClass** — a subclass — and none of its functions appear in that dump. Cross-checked two
ways: no script cheat name appears anywhere under `docs/`, and none of the 47 methods
`Binds.Cache` exposes on native `ALokiPlayerCheats` collides with a script name.

### 3.1 Properties (exact)

```angelscript
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
TSubclassOf<UGameplayEffect@>  CheatDisableHealthRegenEffectClass;
UPROPERTY(EditableOnDefaults, EditableOnInstance, Transient)
FActiveGameplayEffectHandle    CheatDisableHealthRegenEffectHandle;
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)
TSubclassOf<UGameplayEffect@>  CheatDisableManaRegenEffectClass;
UPROPERTY(EditableOnDefaults, EditableOnInstance, Transient)
FActiveGameplayEffectHandle    CheatDisableManaRegenEffectHandle;
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
float64  AutoJumpStartTime;
float64  AutoJumpPeriod;
float64  AutoJumpLastTime;
bool     AutoJumpPressed;
TSubclassOf<AAIController@>        WispControllerClass;   // <-- set in the CDO/BP
TSubclassOf<ALokiHeroCharacter@>   WispHeroClass;         // <-- set in the CDO/BP
```

`WispControllerClass` / `WispHeroClass` are **empty in the script constructor** — the
constructor only default-constructs them. Their real values live in the Blueprint CDO that
derives from `ALokiPlayerCheats_AS`, which is *not* in the script cache.

### 3.2 Client entry points — 20 functions, all `UFUNCTION(BlueprintCallable, CanOverrideEvent)`

| signature | what it does (decompiled) |
|---|---|
| `void ConsoleCommandCheatToggleHealthRegen()` | calls `AuthCheatToggleHealthRegen()` (server RPC) |
| `void ConsoleCommandCheatToggleManaRegen()` | calls `AuthCheatToggleManaRegen()` |
| `void ConsoleCommandCheatGrantGold(const int Amount)` | calls `AuthCheatGrantGold(Amount)` |
| `void ConsoleCommandCheatGrantGems(const int Amount)` | calls `AuthCheatGrantGems(Amount)` |
| `void ConsoleCommandCheatUnlockFullArmory()` | calls `AuthCheatUnlockFullArmory()` |
| `void ConsoleCommandCheatExecuteUAV()` | reads `GetPlayerState()->GetPawn()->GetActorLocation()` (falls back to `FVector::ZeroVector`) and `GetTeamIndex_BP()` (falls back to `-1`), then `AuthCheatExecuteUAV(loc, team)` |
| `void ConsoleCommandCheatExecuteUAVGlobal()` | same, but forces `TeamIndex = -1` (all teams) |
| `void ConsoleCommandCheatBarracudaNextPhase()` | calls `AuthCheatBarracudaNextPhase()` |
| `void ConsoleCommandCheatBarracudaToggleJungleSpawners()` | `AuthCheatBarracudaToggleSpawnerType(GameplayTags::Static_Barracuda_Spawner_Neutral)` |
| `void ConsoleCommandCheatBarracudaToggleLaneSpawners()` | `AuthCheatBarracudaToggleSpawnerType(GameplayTags::Static_Barracuda_Spawner_Creep)` |
| `void ConsoleCommandCheatBarracudaToggleDayNightCycle()` | `AuthCheatBarracudaToggleDayNightCycle()` |
| `void ConsoleCommandCheatBarracudaAdvanceDayNightCycle()` | `AuthCheatBarracudaAdvanceDayNightCycle()` |
| `void SpawnEnemyWispAtMyLocation()` | `ServerSpawnWispAS(GetUnusedTeamIndex(this), GetMyLocation())` |
| `void SpawnAllyWispAtMyLocation()` | `ServerSpawnWispAS(LokiTeam::GetTeamFromActor(GetPlayerState()), GetMyLocation())` |
| `void ConsoleCommandCheatSpawnEnemyWisp()` | `ServerSpawnWispAS(GetUnusedTeamIndex(this), GetClientCursorLocation() + FVector(0,0,500.0))` |
| `void ConsoleCommandCheatSpawnAllyWisp()` | same, but on the caller's own team |
| `void ConsoleCommandEnableStuckAbilityLogs()` | runs 8 console commands (§3.5) |
| `void ConsoleCommandCheatAutoJump(const float64 Period)` | `Period > 0` → `AutoJumpStartTime = Gameplay::GetServerTime(); AutoJumpPeriod = Period`. `Period <= 0` → `AutoJumpStartTime = 0` (off) |
| `void ConsoleCommandEnableMovementDebug()` | runs 5 console commands (§3.5) |
| `void ConsoleCommandDisableMovementDebug()` | runs `p.DebugLogAllMoves 0` with ServerExec |

### 3.3 Server RPCs — 11, all `UFUNCTION(..., BlueprintEvent, NetServer)`

Each is a stub that marshals arguments (`__Evt_PushArgument…` + `__Evt_Execute`) plus an
`_Implementation` that runs on the authority.

```angelscript
void AuthCheatToggleHealthRegen()
void AuthCheatToggleManaRegen()
void AuthCheatGrantGold(const int Amount)
void AuthCheatGrantGems(const int Amount)
void AuthCheatUnlockFullArmory()
void AuthCheatExecuteUAV(const FVector& SourceLocation, const int TeamIndex = -1)
void AuthCheatBarracudaNextPhase()
void AuthCheatBarracudaToggleSpawnerType(const FGameplayTag& SpawnerType)
void AuthCheatBarracudaToggleDayNightCycle()
void AuthCheatBarracudaAdvanceDayNightCycle()
void ServerSpawnWispAS(const int TeamIndex, const FVector& Location = FVector::ZeroVector)
    // meta.DisplayName = "Server Spawn Wisp (AngelScript)"
```

**`AuthCheatToggleHealthRegen_Implementation` / `AuthCheatToggleManaRegen_Implementation`**
— a complete, minimal GAS round-trip, identical in both:

```angelscript
ULokiAbilitySystemComponent asc = this.GetAbilitySystemComponent();
if (asc != nullptr && this.CheatDisableHealthRegenEffectClass.IsValid()) {
    if (asc.HasActiveGameplayEffect(this.CheatDisableHealthRegenEffectHandle)) {
        asc.RemoveActiveGameplayEffect(this.CheatDisableHealthRegenEffectHandle, -1);
    } else {
        FGameplayEffectContextHandle ctx  = asc.MakeEffectContext();
        FGameplayEffectSpecHandle    spec = asc.MakeOutgoingSpec(this.CheatDisableHealthRegenEffectClass, 0, ctx);
        this.CheatDisableHealthRegenEffectHandle = asc.ApplyGameplayEffectSpecToSelf(spec);
    }
}
```

**`AuthCheatGrantGold/Gems_Implementation`**

```angelscript
ALokiPlayerState ps = this.GetPlayerState();
ps.GrantWalletCurrency("Gold", Amount, ECurrencyGrantReason::Misc);   // literally the FString "Gold" / "Gems"
```

**`AuthCheatUnlockFullArmory_Implementation`**

```angelscript
ALokiGameState gs = Loki::GetLokiGameState(__WorldContext);
if (gs != nullptr) gs.SetArmoryFullyUnlocked(true);
```

**`AuthCheatExecuteUAV_Implementation`**

```angelscript
ALokiGameState_AS gs = cast<ALokiGameState_AS>(Loki::GetLokiGameState(__WorldContext));
if (gs == nullptr) return;
ULokiGameStateUAVComponent uav = gs.UAVComponent;
if (uav == nullptr) return;
FLokiUAVConfig cfg;                       // default-constructed
FActiveUAV     active;                    // OUT param
uav.ExecuteUAV(active, cfg, SourceLocation);
```

**`AuthCheatBarracuda*_Implementation`** — all four reach a Barracuda GameState component
through free functions declared in `Barracuda/GameState/BarracudaGameStateGlobals.as`
(`GetBarracudaGameStateComponent()`, `GetBarracudaGameMode()`):

```angelscript
// NextPhase
UBarracudaGameStateComponent c = GetBarracudaGameStateComponent();
if (c != nullptr) c.AuthMoveToNextBarracudaPhase();

// ToggleSpawnerType(Tag)  -- toggles membership in a FGameplayTagContainer
if (c.DisabledSpawnerTypes.HasTagExact(SpawnerType)) c.DisabledSpawnerTypes.RemoveTag(SpawnerType);
else                                                 c.DisabledSpawnerTypes.AddTag(SpawnerType);

// ToggleDayNightCycle
c.bDayNightTransitionEnabled = !c.bDayNightTransitionEnabled;

// AdvanceDayNightCycle
if (c != nullptr && GetBarracudaGameMode() != nullptr)
    c.NextDayNightSwapTime = GetBarracudaGameMode().GetMatchTime();
```

**`ServerSpawnWispAS_Implementation` — the spawn-and-possess recipe, in script.** This is
the single most operationally valuable body in the module:

```angelscript
AAIController ai = SpawnActor(this.WispControllerClass, FVector::ZeroVector,
                              FRotator::ZeroRotator, NAME_None, /*bDeferred*/ false, nullptr);
ALokiPlayerState ps = cast<ALokiPlayerState>(ai.PlayerState);

ALokiHeroCharacter hero = SpawnActor(this.WispHeroClass, Location, FRotator::ZeroRotator,
                                     NAME_None, /*bDeferred*/ true, nullptr);
hero.SetOwner(ps);
FinishSpawningActor(hero);
ai.Possess(hero);
LokiTeam::SetTeamForActor(hero, TeamIndex);

ALokiGameState gs = Loki::GetLokiGameState(__WorldContext);
if (gs != nullptr) {
    ALokiTeamState ts = gs.GetOrCreateTeamState(TeamIndex);
    if (ts.GetLivingPlayers().Num() < 2)
        this.CheatSetTeamEliminated(this, TeamIndex, true);
}

FGameplayEffectContextHandle ctx;
hero.LivingStateMachine.RequestMoveTowardDeath(ctx);      // <-- makes it a *wisp*
```

The last line is what makes it a "wisp" (SUPERVIVE's downed form): the hero is spawned
alive, possessed by an AI controller, put on a team, then explicitly driven toward death.
**Drop that one call and the same sequence spawns a live, AI-possessed hero.**

### 3.4 Helpers

```angelscript
UFUNCTION(UnrealName=Tick, BlueprintOverride, BlueprintEvent, CanOverrideEvent)
void Tick_Implementation(const float64 DeltaSeconds) { this.TickAutoJump(); }

void RunCommand(const FString& Command, const bool bAlsoServerExec = false)
{
    ALokiPlayerController pc = this.GetPlayerController();
    if (pc == nullptr) return;
    System::ExecuteConsoleCommand(__WorldContext, Command, pc);
    if (bAlsoServerExec)
        System::ExecuteConsoleCommand(__WorldContext, "ServerExec " + Command, pc);
}

private FVector GetMyLocation()          // PC -> GetControlledPawn() -> GetActorLocation(), else ZeroVector
void TickAutoJump()
{
    if (this.AutoJumpStartTime <= 0) return;
    ALokiHeroCharacter hero = this.GetHeroCharacter();
    if (hero == nullptr) return;
    if (this.AutoJumpPressed) { this.AutoJumpPressed = false; hero.JumpActionStop(); return; }
    float64 now = Gameplay::GetServerTime(__WorldContext);
    if (now - this.AutoJumpLastTime > this.AutoJumpPeriod) {
        this.AutoJumpLastTime = now;
        hero.JumpActionStart();
        this.AutoJumpPressed = true;
    }
}
```

### 3.5 Console command strings the cheats issue (exact literals)

`ConsoleCommandEnableStuckAbilityLogs()` — the `true` column is `bAlsoServerExec`:

```
RequestAdmin                              (client only)
Log LogAbilitySystem Verbose              + ServerExec
Log LogLokiAbilitySystemComponent Verbose + ServerExec
Log LogLokiGameplaySpell Verbose          + ServerExec
DebugLogSpellBuffering 1                  + ServerExec
ShowDebug AbilitySystem                   (client only)
AbilitySystem.Debug.NextCategory          (client only, issued twice)
```

`ConsoleCommandEnableMovementDebug()`:

```
GodMode                                   (client only)
Log LogCharacterMovement Verbose          + ServerExec
p.NetShowCorrections 1                    (client only)
p.DebugLogAllMoves 1                      + ServerExec
p.DebugLogAllMoves1D 1                    + ServerExec
```

`ConsoleCommandDisableMovementDebug()`: `p.DebugLogAllMoves 0` + ServerExec.

These are **real command names in this build**, recovered as string literals from the
bytecode: `RequestAdmin`, `GodMode`, `ServerExec <cmd>`, `DebugLogSpellBuffering`,
`ShowDebug AbilitySystem`, `AbilitySystem.Debug.NextCategory`, `p.NetShowCorrections`,
`p.DebugLogAllMoves`, `p.DebugLogAllMoves1D`.

### 3.6 Native cheat API the script calls (exact signatures from `Binds.Cache`)

Recovered from the disassembly appendix, where every operand is named:

```angelscript
ALokiHeroCharacter@         ALokiPlayerCheats::GetHeroCharacter() const
ALokiPlayerController@      ALokiPlayerCheats::GetPlayerController() const
ALokiPlayerState@           ALokiPlayerCheats::GetPlayerState() const
ULokiAbilitySystemComponent@ ALokiPlayerCheats::GetAbilitySystemComponent() const
FVector                     ALokiPlayerCheats::GetClientCursorLocation() const
int                         ALokiPlayerCheats::GetUnusedTeamIndex(const UObject@ WorldContext)
void                        ALokiPlayerCheats::CheatSetTeamEliminated(const UObject@ WorldContext, int TeamIndex, bool bEliminated)
bool                        LokiTeam::SetTeamForActor(AActor@, const int)
int                         LokiTeam::GetTeamFromActor(const AActor@)
ALokiGameState@             Loki::GetLokiGameState(UObject@)
ALokiTeamState@             ALokiGameState::GetOrCreateTeamState(int)
TArray<ALokiPlayerState@>   ALokiTeamState::GetLivingPlayers() const
void                        ALokiGameState::SetArmoryFullyUnlocked(bool)
void                        ALokiPlayerState::GrantWalletCurrency(const FString&, int, ECurrencyGrantReason)
int                         ALokiPlayerState::GetTeamIndex_BP() const
void                        ALokiCharacter::JumpActionStart()
void                        ALokiCharacter::JumpActionStop()
void                        ULivingStateMachine::RequestMoveTowardDeath(FGameplayEffectContextHandle)
void                        System::ExecuteConsoleCommand(const UObject@, const FString&, APlayerController@)
float32                     Gameplay::GetServerTime(const UObject@)
AActor@                     SpawnActor(const TSubclassOf<AActor@>&, const FVector&, const FRotator&, const FName&, bool bDeferred, ULevel@)
void                        FinishSpawningActor(AActor@)
void                        AController::Possess(APawn@)
```

---

## 4. `PlayerController/LokiDragCameraComponent.as` — drag-to-pan camera

`ULokiDragCameraComponent : UActorComponent` — a **pure client component**; its
`__InitDefaults()` sets `bExcludeFromServer = true` and
`PrimaryComponentTick.bAllowTickOnDedicatedServer = false`.

```angelscript
UPROPERTY(...) float64 MinimumDragDuration;      // __InitDefaults: 0.15
UPROPERTY(...) float64 CameraPickupRadius;       // __InitDefaults: -1.0  (disabled by default)
UPROPERTY(..., Transient) bool    bPanning;      // false
UPROPERTY(..., Transient) bool    bResetting;    // false
UPROPERTY(..., Transient) float64 TimePressed;   // 0
UPROPERTY(..., Transient) FVector CursorScreenLocationWhenPressed;
UPROPERTY(..., Transient) FVector OffsetThisPress;
UPROPERTY(..., Transient) FVector CumulativeOffset;   // reset to ZeroVector
UPROPERTY(..., Transient) FVector LastPawnLocation;
```

Functions: `NotifyInputPressed()`, `NotifyInputReleased()` (both
`UFUNCTION(BlueprintCallable, CanOverrideEvent)`), `Tick_Implementation(DeltaSeconds)`, and
three privates `GetCursorScreenLocation()`, `GetPlayerController()`, `GetLocalPawn()`.

**State machine (decompiled):**

- **`NotifyInputPressed`** — `bPanning = true; bResetting = false;
  TimePressed = Gameplay::GetServerTime(); CursorScreenLocationWhenPressed =
  GetCursorScreenLocation(); OffsetThisPress = ZeroVector;`
- **`NotifyInputReleased`** — `bPanning = false`. Computes
  `heldFor = |now - TimePressed|` and `moved = CursorScreenLocationWhenPressed.Dist2D(cursor)`.
  A press counts as a **click, not a drag**, when `heldFor < MinimumDragDuration && moved < 200.0`.
  `bResetting = ULokiGameUserSettings::GetLokiGameUserSettings().IsDragToPanCameraResetOnRelease()
  || wasClick`. Then `CumulativeOffset += OffsetThisPress; OffsetThisPress = ZeroVector`, and
  if not resetting, latches `LastPawnLocation = pawn.GetActorLocation()`.
- **`Tick_Implementation`** — bails unless PC, local pawn and
  `ULokiCharacterSpringArmComponent` (found by `GetComponentByClass`) all exist. If
  `bPanning` and the cursor reads `ZeroVector` (cursor lost), it self-releases via
  `NotifyInputReleased()`. Sets `springArm.bDynamicCameraPanEnabled = true`, then:
  - **panning**: `speed = settings.GetDragToPanCameraSpeed()`;
    `scale = inverted ? FVector(-speed,-speed,0) : FVector(speed,speed,0)`;
    `OffsetThisPress = (cursor - CursorScreenLocationWhenPressed) * scale`.
  - **resetting**: `CumulativeOffset *= FVector(0.8, 0.8, 0)` per tick; when
    `CumulativeOffset.Size2D() < 100.0` snap to `ZeroVector` and clear `bResetting`.
  - **idle with a non-zero offset** (`!CumulativeOffset.IsNearlyZero(9.999999747378752e-05)`
    — i.e. the float32 `KINDA_SMALL_NUMBER` widened to double): sets
    `springArm.bDynamicCameraPanEnabled = false`, and **counter-scrolls the offset by the
    pawn's own motion** — `delta = pawn.GetActorLocation() - LastPawnLocation`,
    `CumulativeOffset -= delta * FVector(1.0, 1.0, 0)` — so the camera stays put in world
    space while the pawn walks. If `CameraPickupRadius > 0 && CumulativeOffset.Size2D() <
    CameraPickupRadius`, it flips `bResetting = true` (the pawn "catches up" and the camera
    re-attaches).
  - Every tick, finally: `springArm.CameraManualPanOffset = CumulativeOffset + OffsetThisPress`.

**Why this matters to the project.** S93 fought the camera and settled on spawning a
`CameraActor` and re-asserting the view target. This module names the real camera control
surface: **`ULokiCharacterSpringArmComponent`** with two writable members —
`bDynamicCameraPanEnabled` (bool) and `CameraManualPanOffset` (FVector) — reachable from
the pawn via `GetComponentByClass(ULokiCharacterSpringArmComponent::StaticClass())`. That
is a world-space camera offset you can write directly, with no view-target games.

Also surfaced: `ULokiGameUserSettings::GetLokiGameUserSettings()` (a static) with
`IsDragToPanCameraInverted()`, `GetDragToPanCameraSpeed()`,
`IsDragToPanCameraResetOnRelease()`; and `APlayerController::GetPawnOrSpectator()` /
`GetMousePosition(float32& X, float32& Y)`.

---

## 5. `Character/LokiHeroCharacter.as` — thinner than the file count suggests

```angelscript
event FBiomeTouchUnlockedDelegate;     // Broadcast(ALokiBaseItem@ Item, const FText& UnlockName)

UCLASS(SuperIsCodeClass, Abstract, Placeable)
class ALokiHeroCharacter_AS : ALokiHeroCharacter        // /Script/Loki.LokiHeroCharacter
{                                        // Loki/Source/Loki/Character/Hero/LokiHeroCharacter.h
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    FBiomeTouchUnlockedDelegate OnBiomeTouchUnlocked;

    void ClientBiomeSoulAcquired(AActor@ AcquiredBy);            // stub
    UFUNCTION(UnrealName=ClientBiomeSoulAcquired, BlueprintCallable, BlueprintEvent,
              NetClient, Unreliable)
    void ClientBiomeSoulAcquired_Implementation(AActor@ AcquiredBy)
    { this.BP_OnClientBiomeSoulAcquired(AcquiredBy); }

    UFUNCTION(UnrealName=BP_OnClientBiomeSoulAcquired, BlueprintEvent, CanOverrideEvent, NoOp,
              meta.BlueprintProtected, meta.DisplayName=BP OnClientBiomeSoulAcquired)
    protected void BP_OnClientBiomeSoulAcquired_Implementation(AActor@ AcquiredBy) { return; }

    void __InitDefaults() { this.SetbReplicates(true); }
}
```

The class is **`Abstract`** — it cannot be spawned directly; the real hero classes are
Blueprints deriving from it. The only behaviour it adds is:

1. **`SetbReplicates(true)`** in `__InitDefaults` — the script tier is where the hero's
   `bReplicates` gets forced on. Relevant to the project's replication work: this runs at
   CDO construction, not at spawn.
2. **One unreliable client RPC**, `ClientBiomeSoulAcquired(AActor@ AcquiredBy)`, which
   forwards to a `NoOp` Blueprint event.
3. **One multicast delegate**, `OnBiomeTouchUnlocked(ALokiBaseItem@ Item, FText UnlockName)`.
   Nothing in the script layer broadcasts it (checked all 78 modules) — native or BP does.

The remaining 14 functions are the generated delegate machinery for
`FBiomeTouchUnlockedDelegate`.

**Honest negative result:** if you were hoping the script tier holds the hero's movement,
ability granting, mesh setup or cosmetics, it does not. All of that is native/BP. What the
script layer *does* expose about the hero is the large native API it calls into — see §11.

---

## 6. `Character/LokiHeroGroundIndicator.as` — the hero's shadow + ring decals

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class ULokiHeroGroundIndicator : ULokiHeroGroundIndicatorBase
{   // /Script/Loki.LokiHeroGroundIndicatorBase
    // Loki/Source/Loki/Character/Hero/LokiHeroGroundIndicatorBase.h
    UPROPERTY(..., meta.Category=GroundIndicator|Shadow) protected FVector  ShadowDecalSize;      // (50, 100, 100)
    UPROPERTY(..., meta.Category=GroundIndicator|Shadow) protected FRotator ShadowDecalRotation;  // (-90, 0, 0)
    UPROPERTY(..., meta.Category=GroundIndicator|Ring)   protected FVector  RingDecalSize;        // (200, 300, 300)
    UPROPERTY(..., meta.Category=GroundIndicator|Ring)   protected FRotator RingDecalRotation;    // (-90, 0, 0)

    UFUNCTION(UnrealName=CreateShadowDecal, BlueprintOverride, BlueprintEvent, CanOverrideEvent)
    void CreateShadowDecal_Implementation()
    {
        this.ShadowDecalComponent = Gameplay::SpawnDecalAtLocation(
            __WorldContext, this.ShadowDecalMaterial, this.ShadowDecalSize,
            FVector::ZeroVector, this.ShadowDecalRotation, /*LifeSpan*/ 0);
        this.ShadowDecalMID = Material::CreateDynamicMaterialInstance(
            __WorldContext, this.ShadowDecalComponent.GetDecalMaterial(),
            NAME_None, EMIDCreationFlags::None);
        this.ShadowDecalComponent.SetDecalMaterial(this.ShadowDecalMID);
    }
    // CreateRingDecal_Implementation() is the identical body against Ring*
}
```

Note this class does **not** use the `_AS` suffix even though it is a script class — one of
the 67 that S74's scan missed (§0.1).

`ShadowDecalMaterial` / `ShadowDecalComponent` / `ShadowDecalMID` (and the Ring trio) are
inherited from the **native** `ULokiHeroGroundIndicatorBase`; the script only sizes,
orients, spawns and MID-ifies them. `CreateShadowDecal` / `CreateRingDecal` are
`BlueprintOverride` — they override virtuals declared on the native base, so the base
decides *when* to call them.

Relevance to "make a hero visible": this is a decal-based ground shadow, not the hero mesh.
It does confirm the pipeline `Gameplay::SpawnDecalAtLocation` →
`Material::CreateDynamicMaterialInstance` → `SetDecalMaterial` is fully script-reachable.

---

## 7. `Core/Components/LokiMajorStatusEffectComponent.as`

```angelscript
UCLASS(SuperIsCodeClass, Placeable)
class ULokiMajorStatusEffectComponent_AS : ULokiMajorStatusEffectComponent
{   // /Script/Loki.LokiMajorStatusEffectComponent
    // Loki/Source/Loki/Character/LokiMajorStatusEffectComponent.h
    UPROPERTY(BlueprintReadable, EditableOnDefaults, EditableOnInstance)
    protected ALokiCharacter@ MyCharacter;
    UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults, EditableOnInstance)
    TMap<FGameplayTag, FActiveGameplayEffectHandle> EffectHandles;

    UFUNCTION(UnrealName=BeginPlay, BlueprintOverride, BlueprintEvent, CanOverrideEvent)
    void BeginPlay_Implementation() { this.MyCharacter = cast<ALokiCharacter>(this.GetOwner()); }

    UFUNCTION(BlueprintCallable, CanOverrideEvent)
    void SetLongestRemainingEffectHandle(const FGameplayTag& Tag)
    {
        if (!IsValid(this.MyCharacter)) return;
        ULokiAbilitySystemComponent asc = this.MyCharacter.GetLokiAbilitySystem_BP();
        if (!IsValid(asc)) return;
        FGameplayTagContainer c = GameplayTag::MakeGameplayTagContainerFromTag(Tag);
        for (FActiveGameplayEffectHandle h : asc.GetActiveEffectsWithAllOwningTags(c)) {
            float64 candidate = this.BP_EffectRemainingDuration(h);
            float64 best = 0;
            FActiveGameplayEffectHandle cur;
            if (this.EffectHandles.Find(Tag, cur)) best = this.BP_EffectRemainingDuration(cur);
            if (candidate > best) this.EffectHandles.Add(Tag, h);
        }
    }

    UFUNCTION(UnrealName=BP_EffectRemainingDuration, BlueprintEvent, CanOverrideEvent,
              meta.DisplayName=Effect Remaining Duration)
    float64 BP_EffectRemainingDuration_Implementation(const FActiveGameplayEffectHandle&) { return 0; }
}
```

Purpose: for each "major status effect" gameplay tag (stun, root, silence — the container
is a runtime input, not a literal), keep the handle of the **longest-remaining** active
effect carrying that tag, so the HUD can show one icon with one timer.
`BP_EffectRemainingDuration` returns `0` in script and is meant to be overridden in
Blueprint, so the actual duration query is not in the cache.

**The key extracted fact:** `ALokiCharacter::GetLokiAbilitySystem_BP()` →
`ULokiAbilitySystemComponent@`. That is the ability-system accessor **on the character**,
which is exactly the question `supervive-milestone`/S100 was measuring ("hero owns no
ability system, the CARRIER is missing"). Also
`ULokiAbilitySystemComponent::GetActiveEffectsWithAllOwningTags(FGameplayTagContainer)` →
`TArray<FActiveGameplayEffectHandle>` and
`GameplayTag::MakeGameplayTagContainerFromTag(FGameplayTag)`.

---

## 8. `Core/LokiScriptUtility.as` — three global helpers

Module-level statics class `Module_Core_LokiScriptUtilityStatics`. No classes.

```angelscript
FVector LinearColorToVector(const FLinearColor& Color)          // -> FVector(R, G, B); not a UFUNCTION

UFUNCTION(BlueprintCallable, BlueprintPure, CanOverrideEvent, Static)
ULokiAimingVisComponentScript@ GetOwnerAimingVisComponent(ULokiDisplayableAbility@ Ability)
{   // Ability -> GetAvatarLokiCharacterFromActorInfo() -> cast<ALokiHeroCharacter>
    // -> ULokiAimingVisComponentScript::Get(hero, NAME_None)
}

UFUNCTION(BlueprintCallable, CanOverrideEvent, Static)
float64 GetRelicCountForPlayer(ALokiCharacter@ Character)
{   // Character.GetInventoryComboItems(); count of GetPowerItem(0) and GetPowerItem(1) that are non-null
}

UFUNCTION(BlueprintCallable, CanOverrideEvent, Static)
float64 GetArmorLevelForPlayer(ALokiCharacter@ Character)
{   // Character.GetInventoryComboItems().GetArmorItem().TierNumber, else 0
}
```

Both inventory helpers return `float64` because they feed Gameplay-Effect magnitude
calculations. Surfaced native API: `ULokiDisplayableAbility::GetAvatarLokiCharacterFromActorInfo()`,
`ALokiCharacter::GetInventoryComboItems()` → `ULokiInventoryComponentComboItems` with
`GetPowerItem(int)` / `GetArmorItem()`, and `ALokiBaseItem::TierNumber`.

---

## 9. `Core/AimingVis/*` — the aiming-laser subsystem (6 modules, ~33 KB of bytecode)

The largest block in my scope, and the most complete self-contained system in the whole
script layer. It is **entirely client-side** — every substantive body opens with
`if (!Loki::LokiIsClient(__WorldContext)) return;`.

### 9.1 `ULokiAimingVisComponentScript : ULokiAimingVisComponent` — the controller

```angelscript
UPROPERTY(BlueprintReadable, EditableOnDefaults, EditableOnInstance)      ALokiCharacter@ OwnerCharacter;
UPROPERTY(..., Transient)                                                 bool bHasInitializedClient;
UPROPERTY(..., Transient)                                                 bool bHasInitializedLocalClient;
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)       bool bHeroUsesAimingLaser;   // ctor: true
UPROPERTY(EditableOnDefaults, EditableOnInstance, Transient)              ALokiAimingLaser@ ClientLaserInstance;
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)       TArray<FAimingLaserSettings> LaserSettings;
UPROPERTY(BlueprintReadable, BlueprintWritable, EditableOnDefaults)       int SpawnLaserSettingsIndex;      // ctor: 0
UPROPERTY(BlueprintReadable, EditableOnDefaults, EditableOnInstance)      int CurrentLaserSettingsIndex;
UPROPERTY(..., Replicated, ReplicationCondition=0)                        int ReplicatedLaserSettingsIndex; // ctor: -1
```

`__InitDefaults()` calls `SetbReplicates(true)`. `ReplicatedLaserSettingsIndex` is the
**only replicated property in any of my fifteen modules** (`ReplicationCondition=0` =
`COND_None`).

Lifecycle, decompiled:

- **`LokiBeginPlay_Implementation`** (`BlueprintOverride`) — `if (ReplicatedLaserSettingsIndex >= 0)
  SpawnLaserSettingsIndex = ReplicatedLaserSettingsIndex;`. This is the whole point of the
  replicated int: the server picks the laser variant, the client adopts it before spawning.
- **`InitClient_Implementation`** — client-only, once (`bHasInitializedClient`). Requires
  `ValidateOwner()`. Runs `OnShowAimingLaserChanged(); OnLimitLaserToCursorChanged();
  InitClientLaser(); OwnerCharacter.OnDestroyed.AddUFunction(this, n"OnOwnerDestroyed");
  BindHardCodedDelegates();` — the last is a **native** `ULokiAimingVisComponent` method.
- **`InitLocalClient_Implementation`** — client + `IsOwnerLocallyControlled()`, once.
  Registers two user-setting callbacks and re-runs the same init:
  ```
  UPlayerConfigManager::RegisterOnGenericPlayerConfigValueUpdated(
      __WorldContext, n"Aiming", n"UseAimingLaser",     FOnGenericPlayerConfigValueUpdated(this, n"OnShowAimingLaserChanged"));
  UPlayerConfigManager::RegisterOnGenericPlayerConfigValueUpdated(
      __WorldContext, n"Aiming", n"LimitLaserToCursor", FOnGenericPlayerConfigValueUpdated(this, n"OnLimitLaserToCursorChanged"));
  ```
- **`InitOnLocalASC_Implementation`** — binds `OwnerCharacter.OnLivingStateChanged` to
  `n"OnLivingStateChanged"`.
- **`ValidateOwner()`** — caches: `if (!IsValid(OwnerCharacter)) { OwnerCharacter =
  cast<ALokiCharacter>(GetOwner()); }` with `false` returns if either is invalid.
- **`UsesAimingLaser_Implementation()`** — `bHeroUsesAimingLaser && LaserSettings.Num() > 0
  && (UPlayerConfigManager::GetGenericPlayerConfigBoolValue(__WorldContext, n"Aiming",
  n"UseAimingLaser") || LaserSettings[CurrentLaserSettingsIndex].bUnconditionallyVisibleWhenActive)`.
- **`SpawnLaser_Implementation(const FAimingLaserSettings& Settings)`** — the interesting one:
  ```angelscript
  if (!LokiIsClient || !ValidateOwner() || !UsesAimingLaser()) return;
  if (!Settings.bUnconditionallyVisibleWhenActive && !IsOwnerLocallyControlled()) return;
  if (!Settings.LaserClass.IsValid()) return;
  if (HasValidAimingLaser()) {
      if (ClientLaserInstance.IsA(UClass(Settings.LaserClass))) return;   // already right class
      DestroyLaser();
  }
  ALokiHeroCharacter hero = cast<ALokiHeroCharacter>(OwnerCharacter);
  if (!IsValid(hero)) return;
  FVector local = hero.GetActorTransform().InverseTransformPosition(hero.GetCharacterProjectileSpawnLocation());
  FVector spawnAt = OwnerCharacter.GetActorLocation() + FVector::UpVector * local.Z;
  ALokiAimingLaser laser = SpawnActor(Settings.LaserClass, spawnAt, FRotator::ZeroRotator,
                                      NAME_None, /*bDeferred*/ false, nullptr);
  laser.SetInstigator(OwnerCharacter);
  laser.OwnerAimingVisComponent = this;
  laser.UpdateOwner(hero);
  laser.AttachToActor(OwnerCharacter, NAME_None, EAttachmentRule::SnapToTarget);
  laser.SetProjectileSpawnLocation(local.Size2D(), hero.GetCharacterProjectileTerrainHeightOffset());
  ClientLaserSetVisibility(true);
  this.ClientLaserInstance = laser;
  OnLimitLaserToCursorChanged();
  ClientLaserInstance.OnLaserSpawned();
  ```
- **`SwitchLaserSettingsInternal_Implementation(int NewIndex)`** — the settings applier.
  Guards on `LaserSettings.IsValidIndex(NewIndex)`, remembers the old index, sets
  `CurrentLaserSettingsIndex`, respawns the laser actor if the class changed, then pushes
  the whole settings struct onto the laser: limit-to-cursor override, `MaxDistance`
  (multiplied by `1 + GetBonusPrimaryAttackDistance()` when
  `bBenefitsFromBonusPrimaryAttackDistance`), laser/endpoint materials, hit-flare Niagara
  system, brightness, `bShowTraceHitFlare`, `bLimitLaserToTraceHit`, `bIgnoresHeroes`, and
  finally `ClientLaserInstance.OnLaserSettingsIndexChanged(old, NewIndex)`.
- **`OnLivingStateChangedLaser_Implementation(ELivingState NewLivingState)`** — a `JMPP`
  switch over `[ELivingStateDead .. ELivingStateKnocked]`; `Dead` → `DestroyLaser()`,
  the next state → show or spawn the laser, everything else → `ClientLaserSetVisibility(false)`.
  (Two arms render as labelled `goto`s — this is one of the 5 computed-switch sites the
  tool does not fully nest; the disassembly appendix is exact.)

**19 `NetMulticast` pass-throughs.** Each is `UFUNCTION(BlueprintCallable, BlueprintEvent,
NetMulticast, CanOverrideEvent)`, checks `LokiIsClient` + `ValidateLaser()`, then forwards
to the laser actor:

```
ClientLaserSetVisibility(bool)                     ClientLaserSetScriptOverrides(const FLaserScriptOverrides&)
ClientLaserSetProgressCurve(UCurveFloat@)          ClientLaserRestartProgressSequence(float64 Duration, bool bIsCurveNormalized)
ClientLaserResetProgress()                         ClientLaserTriggerCustomEvent(int EventNumber, float64 Value)
ClientLaserSetMaxDistance(float64)                 ClientLaserSetHueShift(float64)
ClientLaserSetLaserMaterial(UMaterialInterface@)   ClientLaserSetEndpointMaterial(UMaterialInterface@)
ClientLaserSetHitFlareNiagaraSystem(UNiagaraSystem@) ClientLaserSetBrightness(float64)
ClientLaserOverrideLimitLaserToCursor(bool)        ClientLaserClearOverrideLimitLaserToCursor()
ClientLaserSwitchSettings(int NewSettingsIndex)
ClientLaserShowRangeMarker(bool)                   ClientLaserSetRangeMarkerDistance(float64)
ClientLaserSetRangeMarkerMaterial(UMaterialInterface@)
ClientSetHeightIndicatorVisibility(bool)
```

The three `RangeMarker` ones additionally `IsA(ALokiAimingLaserRangeMarker)`-check and
downcast. `ClientLaserSwitchSettings` is the one that is not a pure pass-through — it
writes the replicated index on *both* sides before applying it on the client:

```angelscript
void ClientLaserSwitchSettings_Implementation(const int NewSettingsIndex) {
    this.ReplicatedLaserSettingsIndex = NewSettingsIndex;                 // server AND client
    if (Loki::LokiIsClient(__WorldContext))
        this.SwitchLaserSettingsInternal(this.ReplicatedLaserSettingsIndex);
}
```

**These 19 multicasts are a ready-made server→all-clients channel** — see §12.

**Height-indicator half.** `HasValidHeightIndicator()`, `DestroyHeightIndicator()`,
`OnTookDamageHeightIndicator(ALokiCharacter@ SourceCharacter, AActor@ TargetActor, float32
TotalDamage, const FLokiDamageStatistic&in, const FGameplayEffectSpec&in, const
FGameplayTagContainer&in ExecutionTags)`, `ClientSetHeightIndicatorVisibility(bool)`,
`OnShowHeightIndicatorsChanged()`, `OnOwnerDestroyed(AActor@)`. `HeightIndicator` and
`HeightIndicatorClass` are **native** properties on `ULokiAimingVisComponent`
(confirmed in `Binds.Cache`), of type `ALokiHeroHeightIndicator`.

Also declared in this module: `class FLaserScriptOverrides { bool
bOverrideDesaturationAndOpacity; bool bOverrideRangeAndAlphaStep; }` — both default `false`.

### 9.2 `ALokiAimingLaser : AActor` — the laser actor

Two value structs come first:

```angelscript
UCLASS(Placeable) class FLaserTraceResult {
    UPROPERTY() bool bDidHit;  FVector HitLocation;  float64 HitTime;
    UPROPERTY() ALokiHeroHeightIndicator@ HitHeightIndicator;
}

UCLASS(Placeable) class FAimingLaserSettings {          // ctor defaults shown
    TSubclassOf<ALokiAimingLaser@> LaserClass;
    float64 MaxDistance                          = 1000.0;
    bool    bShowTraceHitFlare                   = true;
    bool    bLimitLaserToTraceHit                = true;
    bool    bOverrideLimitLaserToCursor          = false;
    bool    bLimitLaserToCursor                  = false;
    UMaterialInterface@ LaserMaterial            = nullptr;
    UMaterialInterface@ EndpointMaterial         = nullptr;
    UNiagaraSystem@     HitFlareNiagaraSystem    = nullptr;
    bool    bOverrideBrightness                  = false;
    float64 Brightness                           = 1.0;
    bool    bUnconditionallyVisibleWhenActive    = false;
    bool    bIgnoresHeroes                       = false;
    bool    bBenefitsFromBonusPrimaryAttackDistance = true;
}
```

The actor's default subobjects (`meta.DefaultComponent=True`): `USceneComponent
RootComponent`, `UStaticMeshComponent LaserEndpoint`, `UNiagaraComponent LaserHitFlare`,
`ULokiProjectilePathComponent LaserProjectilePath`. Notable non-`UPROPERTY` state and
constructor defaults:

```
OverlapHeightIndicatorRadiusBonus = 35.0        BehindGeoDottedLinesPerMeter = 1.15
bLimitLaserToCursorUserSetting    = true        bProgressCurveIsNormalized   = true
CurrentProgressCurveDuration      = 1.0         PrimaryAttackDistance        = 0
ExecutingTag     = GameplayTags::State_Execute_Executing
BeingExecutedTag = GameplayTags::State_BeingExecuted
```

**`Tick_Implementation(float64 DeltaSeconds)`** — the per-frame pipeline:

1. `if (!Loki::LokiIsClient) return;` · `if (!ValidateOwner()) { OwnerAimingVisComponent.DestroyLaser(); return; }`
2. If `Loki::HasAnyMatchingGameplayTags(OwnerHero, ExecutionTagsContainer)` → hide
   everything and return (laser is suppressed during an execute).
3. Hide if `OwnerHero.IsHidden() || OwnerHero.HeroPredropHidden` (a native bool property —
   directly relevant to the project's pre-drop visibility work).
4. `CurrentCursorPathTime = CalculateCursorPathTime()`, `CurrentTraceHitPathTime = 1.0`,
   then `DoLaserTrace()`; if it hit and `bLimitLaserToTraceHit`, clamp to `HitTime`.
5. Height-indicator intersection bookkeeping (`UpdateLaserIntersection` /
   `EndLaserIntersection`).
6. `CurrentEndPathTime = GetLimitLaserToCursor() ? Math::Min(cursorT, hitT) : hitT`.
7. `LaserProjectilePath.bIsMidAir = OwnerHero.GetLokiCharacterMovement().IsMidAir()`;
   `LaserEndpoint.SetWorldLocation(LaserProjectilePath.GetPositionForTime(CurrentEndPathTime))`.
8. `TickLaserHitFlare(traceResult)`.
9. Unless `bOverrideDesaturationAndOpacity`: reads `Range Desat Mult` / `Range Opacity Floor`
   off the path material and writes `Script Desaturation` / `Final Opacity` onto the
   endpoint (and `Desaturate` on the Niagara flare) — or resets them to `0` / `1.0`.
10. Unless `bOverrideRangeAndAlphaStep`: writes `Alpha Step` (and `Range Step` when not
    cursor-limited) on the path material.
11. `if (UsesProgressSequence() && bProgressActive) TickProgress(DeltaSeconds);`

**`CalculateCursorPathTime()`**

```angelscript
if (IsOwnerLocallyControlled())
    t = LaserProjectilePath.GetTimeForPosition(
            Loki::GetLocalCursorLocation(__WorldContext, ELokiProjectionDistanceType::ProjectileHeight));
else
    t = 1.7976931348623157e+308;                // DBL_MAX
return Math::Min(t, 1.0);
```

**`DoLaserTrace()` → `FLaserTraceResult`** — two passes.

*Pass 1, geometry.* Walks `LaserProjectilePath.GetPathSegments(out TArray<FVector>)` pairwise
and line-traces each segment:

```angelscript
System::LineTraceMultiByProfile(__WorldContext, segStart, segEnd, n"AimingLaser",
    /*bTraceComplex*/ false, /*ActorsToIgnore*/ {OwnerHero}, EDrawDebugTrace::None,
    out hits, /*bIgnoreSelf*/ true, FLinearColor(1,0,0,1), FLinearColor(0,1,0,1), /*DrawTime*/ 5.0);
```

Per hit it skips: anything past the cursor time; anything past an earlier hit; start-penetrating
hits; actors tagged `n"DamagePassthrough"`; allies (`ALokiCharacter::IsAllyTeam(OwnerHero)`)
and, when `bIgnoresHeroes`, all characters; actors tagged `n"3DTerrain"`; components whose
collision profile is `n"ShootThrough"`; and one collision-object-type check
(`GetCollisionObjectType() != 18`, an `ECollisionChannel` ordinal the usmap does not name).

*Pass 2, hero height indicators.* Independently of geometry:

```angelscript
TArray<ALokiHeroCharacter@> nearby = ALokiHeroCharacterGrid::FindHeroCharactersInCircleBP(
        __WorldContext, OwnerHero.GetActorLocation(), MaxDistance + 250.0,
        OwnerHero.GetTeamIndex(), false);
```

For each, it projects onto the aim forward vector, computes the perpendicular distance, and
compares against a radius — `GetGliderCollisionCapsule().GetCapsuleRadius()` when
`GetLokiCharacterMovement().IsGliding()`, else `CapsuleComponent.GetCapsuleRadius() +
OverlapHeightIndicatorRadiusBonus`. On overlap it solves the chord
(`along - sqrt(r² - perp²)`), converts to path time, and records the hit only if that hero's
`ULokiAimingVisComponentScript` has a valid `HeightIndicator` whose `TargetLocPtr.IsVisible()`.

**Progress sequence** — `UsesProgressSequence()`, `SetProgressCurve(UCurveFloat@)`,
`ResetProgress()`, `RestartProgressSequence(float64 Duration, bool bIsCurveNormalized)`,
`TickProgress(float64 DeltaSeconds)`, `OnUpdateProgress(float64 ProgressValue)` (a `NoOp`
override point). Four `CustomEvent0..3(float64 Value)` `NoOp` hooks let content drive the
laser from an ability.

Setters: `SetProjectileSpawnLocation(float64 XDistance, float64 ZDistance)`,
`SetMaxDistance(float64)`, `SetHueShift(float64)`, `SetLaserMaterial`,
`SetEndpointMaterial`, `SetHitFlareNiagaraSystem`, `SetBrightness`,
`SetLimitLaserToCursorUserSetting(bool)`, `OverrideLimitLaserToCursor(bool)`,
`ClearOverrideLimitLaserToCursor()`, `SetVisibilityOnAll(bool)`,
`GetColorableMeshes()` → `TArray<UMeshComponent@>` (a `BlueprintEvent` for content),
`GetCurrentLaserSettingsIndex()`, `UpdateOwner(ALokiHeroCharacter@ HeroOwner)`.

### 9.3 `ALokiAimingLaserRangeMarker : ALokiAimingLaser`

Adds `UStaticMeshComponent RangeMarker` (`__InitDefaults`: no shadow, no overlap events,
`NoCollision`), `bShowRangeMarkerOnSpawn` (ctor `true`), `bShowRangeMarker`,
`MarkerDistance`, `bOverrideRangeMarkerDesaturationAndOpacity` (ctor `false`).

Tick: converts `MarkerDistance` to path time via
`LaserProjectilePath.GetTimeForXDistance()`, hides the marker if the laser ends before it,
otherwise positions it at `GetPositionForTime(t)` and mirrors the same
`Script Desaturation` / `Final Opacity` material logic as the parent.
API: `SetShowRangeMarker(bool)`, `SetRangeMarkerDistance(float64)`,
`SetRangeMarkerMaterial(UMaterialInterface@&inout)`.

### 9.4 `ALokiAimingLaserSpreadLines : ALokiAimingLaser` — weapon-bloom cone

Adds `LaserSpreadRoot1/2` (`USceneComponent`) each parenting a `LaserSpread1/2`
(`UStaticMeshComponent`, `meta.Attach=LaserSpreadRoot1/2`). Constructor defaults:

```
bSetSpreadAngleViaBloom = true    bInterpolateBloomValue     = true
InterpolationRampHalfLife = 0.04  NonBloomSpreadAngle        = -1.0
HideSpreadLasersAngle   = 0.05    DimSpreadLasersAngleWindow = 2.0
LaserOpacityMultWhenSpread = 0.35
```

Tick: reads `OwnerHero.GetCurrentBloomAngle()`; when it is *increasing* it eases with an
exponential half-life (`Math::Exp2(-dt / InterpolationRampHalfLife)`) and snaps when within
`0.005`; when decreasing it tracks instantly. Half the angle rotates each root
(`SetRelativeRotation(FRotator(0, ±half, 0))`), and the roots are placed at
`(cos(half)·MaxDistance, ∓sin(half)·MaxDistance, groundZ − actorZ)` where `groundZ` is
`OwnerHero.GetFeetLocation().Z + GetCharacterProjectileTerrainHeightOffset()` when mid-air,
otherwise `ALokiHeightMap::GetInstance(__WorldContext).GetHeight(out h, x, y)` +
the same offset. Below `HideSpreadLasersAngle` both meshes hide; between that and
`HideSpreadLasersAngle + DimSpreadLasersAngleWindow` the opacity ramps via
`Math::GetMappedRangeValueClamped`, and the main laser's `Final Opacity` becomes
`Math::Lerp(1.0, LaserOpacityMultWhenSpread, ramp)`.

### 9.5 Hunter-specific lasers

**`ALokiAimingLaserSpreadLines_HookGuy`** (`RangeMin = 650.0`, `RangeMax = 725.0`) — its
whole Tick is a range lerp driven by bloom, applied before the parent tick:

```angelscript
float64 t = OwnerHero.GetCurrentBloomAngle() / OwnerHero.MaxBloom;
this.MaxDistance = Math::Lerp(this.RangeMax, this.RangeMin, t) * (1 + this.PrimaryAttackDistance)
                 + this.ProjectileSourceOffsetDistanceXY;
Super::Tick(DeltaSeconds);
```

i.e. **HookGuy's hook range shrinks from 725 to 650 as his bloom maxes out**, then scales
with the primary-attack-distance bonus. (This line is one of the ones the value-register fix
in §0.3 corrected; before the fix it read `Math::Lerp(v5, v5, v4)`.)

**`ALokiAimingLaserSpreadLines_Ronin`** (`PostAttackVisDuration = 1.0`,
`PostAttackVisFadeout = 0.5`) — `CustomEvent0` (declared `meta.NoSuperCall`) sets
`VisTimeRemaining = PostAttackVisDuration`; Tick counts it down and drives both spread
meshes' `Final Opacity` at `1.0` until the last `PostAttackVisFadeout` seconds, then ramps
to `0` via `Math::GetMappedRangeValueClamped`. So Ronin's spread lines appear for 1 s after
an attack and fade over the final 0.5 s.

**`ALokiAimingLaser_Huntress : ALokiAimingLaserRangeMarker`** — the richest of the
hunter-specific lasers (21 functions, 5,112 B of bytecode — more than the shared
`SpreadLines` base). Adds `UStaticMeshComponent ProgressMarker` plus a full per-ability
settings table:

```
SettingsIndexBase = 3   SettingsIndexLMB = 0   SettingsIndexRMB = 1   SettingsIndexUlt = 2
LMBRangeMarkerDistance = 850.0
ArrowPerfectGreenChargeMin = 1.0   ArrowPerfectGreenChargeMax = 1.3   ArrowStartChargeFrac = 0.5
(ArrowRangeMinGreen / ArrowRangeMaxGreen / ArrowRangeMaxBlue / ArrowRangeMaxBluePerfect /
 ImpaleRangeMin / ImpaleRangeMax / UltArrowRangeMax are UPROPERTYs with no script default —
 set in the Blueprint CDO, which is not in the cache)
```

`OnLaserSettingsIndexChanged` dispatches to `OnSwapToLMB()` / `OnSwapToBase()` /
`OnSwapToRMB()` / `OnSwapToUlt()` and restores the original marker scales when leaving LMB.
`OnUpdateProgress` dispatches to `UpdateProgressLMB(v)` / `UpdateProgressRMB(v)` / a flat
`Range Step = 1.0` for the Ult, then positions `ProgressMarker` at
`GetPositionForTime(CurrentProgressEndTime)`. `CustomEvent0/1` toggle
`SetShowProgressMarker(false/true)`. There is also a `NoOp` `SetMaxRangeFromRMB` hook and a
`Math::IsNearlyEqual(ProgressValue, 2.0, 0.001)` comparison — a sentinel progress value.
The green/blue "perfect shot" colouring lives in `UpdateProgressLMB`.

---

## 10. What the script layer adds to the three RE'd classes — the short answer

| class | what the SCRIPT tier adds | net |
|---|---|---|
| `ALokiGameState` | one `meta.DefaultComponent` `ULokiGameStateUAVComponent@ UAVComponent`. No methods, no replicated properties. | trivial |
| `ALokiPlayerController` | one `meta.DefaultComponent` `ULokiPlayerControllerUAVComponent@ UAVComponent`; three multicast delegates (`OnSneakPressed`, `OnSneakReleased`, `OnPracticeRespawnPressed`); three BP hook pairs (glider activate/deactivate, spectator map move). No RPCs, no replicated properties. | thin |
| `ALokiHeroCharacter` | `SetbReplicates(true)` in `__InitDefaults`; one unreliable client RPC `ClientBiomeSoulAcquired(AActor@)`; one delegate `OnBiomeTouchUnlocked(ALokiBaseItem@, FText)`. Class is `Abstract`. | thin |
| `ALokiPlayerCheats` | **31 new cheat entry points** (20 client + 11 server RPCs) and 10 properties. | substantial |
| `ULokiAimingVisComponent` | a complete client aiming-laser subsystem: 195 functions across 6 modules (89 + 51 + 11 + 10 + 6 + 7 + 21), incl. **19 NetMulticast RPCs** and the only `Replicated` property in scope. | substantial |
| `ULokiMajorStatusEffectComponent` | `MyCharacter` cache + `TMap<FGameplayTag, FActiveGameplayEffectHandle> EffectHandles` + longest-duration selection. | small |
| (new classes, no native counterpart) | `ULokiDragCameraComponent`, `ULokiHeroGroundIndicator`, `ALokiAimingLaser*` family, `FAimingLaserSettings`, `FLaserTraceResult`, `FLaserScriptOverrides` | — |

**So: the GameState / PlayerController / HeroCharacter script tiers are genuinely thin, and
the project has not been missing hidden gameplay there.** The value in this scope is
(a) the cheat set, (b) the aiming-vis subsystem, and (c) the ~110 exact native signatures
the script calls into, listed next.

---

## 11. Native API surface recovered (exact signatures, from the disassembly appendix)

Every one of these is a real bound C++ function in this build, with its exact parameter
types. This is the practical payload of the decompile: the disassembly names the callee and
its full signature at every call site.

**World / global statics**
```angelscript
bool                Loki::LokiIsClient(const UObject@)
ALokiGameState@     Loki::GetLokiGameState(UObject@)
bool                Loki::HasAnyMatchingGameplayTags(const UObject@, const FGameplayTagContainer&)
FVector             Loki::GetLocalCursorLocation(UObject@, ELokiProjectionDistanceType)
bool                LokiTeam::SetTeamForActor(AActor@, const int)
int                 LokiTeam::GetTeamFromActor(const AActor@)
float32             Gameplay::GetServerTime(const UObject@)
void                System::ExecuteConsoleCommand(const UObject@, const FString&, APlayerController@)
bool                System::LineTraceMultiByProfile(const UObject@, const FVector Start, const FVector End,
                        FName ProfileName, bool bTraceComplex, const TArray<AActor@>& ActorsToIgnore,
                        EDrawDebugTrace, TArray<FHitResult>& OutHits, bool bIgnoreSelf,
                        FLinearColor TraceColor, FLinearColor TraceHitColor, float32 DrawTime)
UDecalComponent@    Gameplay::SpawnDecalAtLocation(const UObject@, UMaterialInterface@, FVector Size,
                        FVector Location, FRotator Rotation, float32 LifeSpan)
UMaterialInstanceDynamic@ Material::CreateDynamicMaterialInstance(UObject@, UMaterialInterface@,
                        FName, EMIDCreationFlags)
AActor@             SpawnActor(const TSubclassOf<AActor@>&, const FVector&, const FRotator&,
                        const FName&, bool bDeferredSpawn, ULevel@)
void                FinishSpawningActor(AActor@)
TArray<ALokiHeroCharacter@> ALokiHeroCharacterGrid::FindHeroCharactersInCircleBP(
                        UObject@ WorldContext, FVector Origin, float64 Radius, int TeamIndex, bool)
ALokiHeightMap@     ALokiHeightMap::GetInstance(const UObject@)
bool                ALokiHeightMap::GetHeight(float32& OutHeight, float32 X, float32 Y)
FGameplayTagContainer GameplayTag::MakeGameplayTagContainerFromTag(const FGameplayTag&)
```

**Character / hero**
```angelscript
ULokiAbilitySystemComponent@   ALokiCharacter::GetLokiAbilitySystem_BP() const
ULokiCharacterMovementComponent@ ALokiCharacter::GetLokiCharacterMovement() const
ULokiInventoryComponentComboItems@ ALokiCharacter::GetInventoryComboItems() const
FVector    ALokiCharacter::GetCharacterProjectileSpawnLocation() const
float64    ALokiCharacter::GetCharacterProjectileTerrainHeightOffset() const
FVector    ALokiCharacter::GetFeetLocation() const
int        ALokiCharacter::GetTeamIndex() const
bool       ALokiCharacter::IsAllyTeam(const AActor@) const
void       ALokiCharacter::JumpActionStart()
void       ALokiCharacter::JumpActionStop()
float32    ALokiHeroCharacter::GetCurrentBloomAngle() const
UCapsuleComponent@ ALokiHeroCharacter::GetGliderCollisionCapsule() const
bool       ULokiCharacterMovementComponent::IsMidAir() const
bool       ULokiCharacterMovementComponent::IsGliding() const
void       ULivingStateMachine::RequestMoveTowardDeath(FGameplayEffectContextHandle)
// members read directly by script (native UPROPERTYs):
//   ALokiHeroCharacter::MaxBloom, ::HeroPredropHidden, ::CapsuleComponent, ::LivingStateMachine,
//   ::OnLivingStateChanged (FLivingStateDelegate), AActor::OnDestroyed
```

**GAS**
```angelscript
FGameplayEffectContextHandle UAbilitySystemComponent::MakeEffectContext() const
FGameplayEffectSpecHandle    UAbilitySystemComponent::MakeOutgoingSpec(TSubclassOf<UGameplayEffect@>,
                                                                      float32 Level, FGameplayEffectContextHandle) const
FActiveGameplayEffectHandle  UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf(const FGameplayEffectSpecHandle&)
                                                     // UFunction alias: BP_ApplyGameplayEffectSpecToSelf
bool  UAbilitySystemComponent::HasActiveGameplayEffect(FActiveGameplayEffectHandle) const
bool  UAbilitySystemComponent::RemoveActiveGameplayEffect(FActiveGameplayEffectHandle, int StacksToRemove)
TArray<FActiveGameplayEffectHandle> ULokiAbilitySystemComponent::GetActiveEffectsWithAllOwningTags(FGameplayTagContainer)
ALokiCharacter@ ULokiDisplayableAbility::GetAvatarLokiCharacterFromActorInfo() const
```

**Camera / settings / player config**
```angelscript
ULokiGameUserSettings@ ULokiGameUserSettings::GetLokiGameUserSettings()
bool     ULokiGameUserSettings::IsDragToPanCameraInverted() const
float32  ULokiGameUserSettings::GetDragToPanCameraSpeed() const
bool     ULokiGameUserSettings::IsDragToPanCameraResetOnRelease() const
bool     UPlayerConfigManager::GetGenericPlayerConfigBoolValue(UObject@, FName Section, FName Key)
void     UPlayerConfigManager::RegisterOnGenericPlayerConfigValueUpdated(UObject@, FName Section, FName Key,
                                                                        FOnGenericPlayerConfigValueUpdated)
APawn@   APlayerController::GetPawnOrSpectator() const
bool     APlayerController::GetMousePosition(float32& X, float32& Y) const
// ULokiCharacterSpringArmComponent members written by script:
//   bool bDynamicCameraPanEnabled ; FVector CameraManualPanOffset
```

**Projectile path / height indicator (aiming-vis)**
```angelscript
void    ULokiProjectilePathComponent::GetPathSegments(TArray<FVector>& Out)
float32 ULokiProjectilePathComponent::GetTimeForPosition(FVector) const
float32 ULokiProjectilePathComponent::GetTimeForXDistance(float32) const
FVector ULokiProjectilePathComponent::GetPositionForTime(float32) const
UMaterialInstanceDynamic@ ULokiProjectilePathComponent::GetMaterial(int) const
void    ULokiProjectilePathComponent::SetMaterial(int, UMaterialInterface@)
void    ULokiProjectilePathComponent::SetMeshBegin(float32) / SetMeshEnd(float32)
// members: bool bIsMidAir ; float32 ProjectileHeight
void    ULokiAimingVisComponent::BindHardCodedDelegates()
void    ULokiAimingVisComponent::SetForceHeightIndicatorVisible(const bool)
void    ULokiAimingVisComponent::SetGlidingLaser(bool)
void    ULokiAimingVisComponent::OnGamepadHasCursorChanged(bool)
// members: TSubclassOf<ALokiHeroHeightIndicator> HeightIndicatorClass ; ALokiHeroHeightIndicator HeightIndicator
bool    ALokiHeroHeightIndicator::ShouldShowHeightIndicator()
void    ALokiHeroHeightIndicator::UpdateLaserIntersection(FVector)
void    ALokiHeroHeightIndicator::EndLaserIntersection()
void    ALokiHeroHeightIndicator::OnTookDamage(ALokiCharacter@, AActor@, float32,
            const FLokiDamageStatistic&, const FGameplayEffectSpec&, const FGameplayTagContainer&)
```

**Named FName / collision-profile / material-parameter literals recovered from bytecode**
```
profiles/tags : n"AimingLaser" · n"ShootThrough" · n"NoCollision"
                n"DamagePassthrough" · n"3DTerrain"
material params: n"Range Desat Mult" · n"Range Opacity Floor" · n"Script Desaturation"
                 n"Final Opacity" · n"Alpha Step" · n"Range Step" · "Desaturate" (Niagara float)
player config  : section n"Aiming", keys n"UseAimingLaser" / n"LimitLaserToCursor"
gameplay tags  : GameplayTags::State_Execute_Executing · State_BeingExecuted
                 Static_Barracuda_Spawner_Neutral · Static_Barracuda_Spawner_Creep
currencies     : "Gold" · "Gems"   (FString, passed to GrantWalletCurrency)
```

---

## 12. What this means for the project

Ordered by how directly it touches a current blocker.

### 12.1 A tested, in-game spawn-and-possess sequence — in the game's own code

`ServerSpawnWispAS_Implementation` (§3.3) is a working spawn path that the developers
shipped and used. The project has reconstructed spawn+possess by hand across S68/S71-74/S90-93;
this is the reference implementation, and it differs from what the project has been doing in
two respects worth testing:

- it spawns the hero **deferred** (`bDeferredSpawn = true`), calls `SetOwner(PlayerState)`
  *before* `FinishSpawningActor`, and only then `Possess`es;
- it assigns the team with `LokiTeam::SetTeamForActor(hero, TeamIndex)` **after** possession.

It also names the two class pointers the game itself uses (`WispHeroClass`,
`WispControllerClass`) — both `UPROPERTY`s on the `ALokiPlayerCheats_AS` CDO, so their
concrete values are readable from a live CDO at runtime even though the script cache does
not carry them. **Reading those two properties off the cheats CDO gives you a hero class and
an AI controller class the game is willing to spawn**, without guessing.

Caveat, stated plainly: the sequence ends with `RequestMoveTowardDeath`, so as-shipped it
produces a wisp, not a live hero. That the *rest* of the sequence works is inference from
the fact that a wisp has to exist as an actor first — I have not run it.

### 12.2 Movement without `AddMovementInput`

S81 characterised the tutorial disconnect: `MODE_PLAYABLE`'s per-frame movement pinned the
game thread inside the `CharacterMovementComponent` chain (`AddMovementInput` in 41% of
freeze samples) → 20 s block → netdriver timeout.

`TickAutoJump` (§3.4) drives the hero through a **completely different pair of native
entry points** — `ALokiCharacter::JumpActionStart()` / `JumpActionStop()` — on a plain
`Tick`, with an explicit press/release edge and a server-time-based period. That is an
input-action path, not a movement-input path. `ConsoleCommandCheatAutoJump(float64 Period)`
turns it on, `Period <= 0` turns it off. Whether it avoids the S81 stall is a hypothesis,
not a result — but it is a cheap, single-variable experiment that the project has not run
because it did not know these functions existed.

### 12.3 Camera control without view-target surgery

`ULokiCharacterSpringArmComponent.CameraManualPanOffset` (FVector, world-space) and
`.bDynamicCameraPanEnabled` (bool) are written directly by `ULokiDragCameraComponent::Tick`,
reached via `pawn.GetComponentByClass(ULokiCharacterSpringArmComponent::StaticClass())`.
S93 solved the camera by spawning a `CameraActor` and re-asserting the view target; this is
a lighter lever on the game's own camera.

### 12.4 The ability system's carrier is named

The S100 note recorded "hero owns no ability system, the CARRIER is missing". The script
layer answers where the game looks for it, twice:

- `ALokiCharacter::GetLokiAbilitySystem_BP()` → `ULokiAbilitySystemComponent@` (used by
  `ULokiMajorStatusEffectComponent_AS`);
- `ALokiPlayerCheats::GetAbilitySystemComponent()` → the same type, from the cheats object
  (used by the health/mana-regen cheats).

Plus a complete apply/remove round-trip (`MakeEffectContext` → `MakeOutgoingSpec` →
`ApplyGameplayEffectSpecToSelf` → `HasActiveGameplayEffect` / `RemoveActiveGameplayEffect`),
which is a working template for granting any `UGameplayEffect` to a hero from a shim.

### 12.5 Nineteen NetMulticast RPCs the backend can already reach

`ULokiAimingVisComponentScript` exposes 19 `NetMulticast` UFunctions (§9.1). Every one of
them is a server→all-clients call whose implementation is client-only and side-effect-free
outside the laser actor. For the project's dedicated-server stub work these are useful as
**low-risk multicast test targets**: they take simple parameters (`bool`, `int`, `float64`,
object handles), they no-op safely when the client has no laser, and they exercise the
multicast path without touching gameplay state.

### 12.6 Console commands that actually exist in this build

`RequestAdmin`, `GodMode`, `ServerExec <cmd>`, `p.NetShowCorrections`,
`p.DebugLogAllMoves`, `p.DebugLogAllMoves1D`, `DebugLogSpellBuffering`,
`ShowDebug AbilitySystem`, `AbilitySystem.Debug.NextCategory`, plus
`Log LogAbilitySystem|LogLokiAbilitySystemComponent|LogLokiGameplaySpell|LogCharacterMovement Verbose`
(§3.5). `RequestAdmin` and `ServerExec` together are an admin/remote-command channel; the
verbose-log set is exactly the instrumentation the developers used for stuck abilities and
movement desync, which are two of this project's recurring symptoms.

### 12.7 How to invoke any of this

All script cheats are `UFUNCTION`s on `ALokiPlayerCheats_AS`, so they are ordinary
`UFunction` entries on that UClass. The project's existing `ProcessInternal` direct-thunk
primitive (`base+0x13454A0`, `UFunction.Func @ +0xE0`; see
`docs/session-55-native-call-primitive.txt`) is exactly the right tool — these are
BP-callable script functions, not native thunks, so `CallBPGuarded` (S91-93) applies. The
local cheats object is reachable via the native static
`ALokiPlayerCheats::GetLocalLokiPlayerCheatsBP(UObject WorldContextObject)`, which the
project already inventoried in S74.

### 12.8 Route implications from §0.1

`ALokiDropShip`, `ALokiDropPod`, `ALokiDropPodLaser`, `ALokiDropPodImpactIndicator`,
`ULokiDropPhase_PlayerStateComponent`, `UComp_PC_LokiRespawnComponent`,
`ULokiPlayerRespawnComponent`, `AFFAGameMode` and 28 Barracuda modules are **script and now
readable**. S74's conclusion that the drop-phase/respawn layer is unreadable native C++ was
an artifact of a `*_AS`-suffix scan. The round gamemode is still native, so S74's *core*
conclusion survives — but "decompile the AS anyway is low marginal value" no longer follows.
Those modules are outside this document's scope and are covered by the sibling reports.

---

## 13. What I could NOT recover

Stated plainly.

1. **Local variable names, line numbers, comments, original formatting, expression
   nesting.** Never serialised — the plugin guards `DeclaredAt` / `LineNumbers` /
   `VariableInfo*` with `#if !UE_BUILD_SHIPPING`, and all 1,463 functions have them empty.
   Locals are `vN` forever.
2. **Blueprint CDO values.** Many `UPROPERTY`s that matter have no script default because
   the Blueprint sets them: `WispHeroClass`, `WispControllerClass`,
   `CheatDisableHealthRegenEffectClass`, `CheatDisableManaRegenEffectClass`,
   `LaserSettings[]` (the entire per-hero laser table), `HeightIndicatorClass`, and every
   Huntress range (`ArrowRangeMinGreen`, `ArrowRangeMaxGreen`, `ArrowRangeMaxBlue`,
   `ArrowRangeMaxBluePerfect`, `ImpaleRangeMin/Max`, `UltArrowRangeMax`). These are
   readable from a live CDO but are not in the cache.
3. **Who broadcasts the delegates.** No script module broadcasts `OnSneakPressed`,
   `OnSneakReleased`, `OnPracticeRespawnPressed` or `OnBiomeTouchUnlocked` — native or
   Blueprint does. Their existence and signatures are exact; their firing conditions are not.
4. **Every `NoOp` `BlueprintEvent` body is genuinely empty**, by design — those are content
   extension points (`BP_OnClientGliderActivated`, `BP_OnSpectatorMapMove`,
   `BP_OnClientBiomeSoulAcquired`, `CustomEvent0..3`, `OnLaserSpawned`,
   `OnLaserSettingsIndexChanged`, `OnUpdateProgress`, `SetMaxRangeFromRMB`). The Blueprint
   overrides are in the paks, not the script cache.
5. **One unnamed enum ordinal.** `DoLaserTrace` compares
   `GetCollisionObjectType() != 18`; the usmap does not name that `ECollisionChannel`
   member, so it is reported as the raw integer.
6. **Two computed-switch arms in `OnLivingStateChangedLaser`** render as labelled `goto`s
   (`L00F4` / `L011C`) rather than nested cases. The bodies and targets are correct; only
   the nesting is not. Its disassembly appendix is exact.
7. **Residual argument-accounting risk.** The decompiler's stack model can in principle
   still mis-attribute an argument without announcing it. I found and fixed three such
   classes of error during this pass (§0.3) and re-verified 0/7,491 dropped callees, but I
   cannot prove there is no fourth. **For any function you intend to act on, read its
   disassembly appendix in `tools/asdump/out/` — every operand there is named and it is
   ground truth.** Concretely: `Math::Lerp(1.0, this.LaserOpacityMultWhenSpread, ramp)` in
   `ALokiAimingLaserSpreadLines::Tick` printed as
   `Math::Lerp(v14, n"Final Opacity", v52)` before the fix — a plausible-looking wrong
   answer, which is the failure mode to watch for.
8. **I have run none of this.** Every statement above is from static analysis of the
   shipping cache. The game was not launched, nothing was injected, and the game files were
   opened read-only (`'rb'`); their mtimes are still 2025-12-17.
