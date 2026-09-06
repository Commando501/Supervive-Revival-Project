# SUPERVIVE Angelscript — the long tail: UAV, Items, Armory, Domination, MostWanted, Minions, Vault, Interaction, DayNight, UI, Content

Decompiled 2026-07-26 from `Loki/Script/PrecompiledScript.Cache` (SHIPPING build dated
2025-12-17) with `tools/asdump/asdump.py`. Format spec: `tools/asdump/FORMAT.md`.
Scope: **22 of the 78 script modules / 443 of the 1,463 script functions.**

| dir | modules | classes | functions |
|---|---:|---:|---:|
| `UAV/` | 6 | 8 | 80 |
| `Items/` | 3 | 3 | 48 |
| `Armory/` | 3 | 2 (+1 statics module) | 63 |
| `Interaction/` | 1 | 5 | 72 |
| `DayNightController/` | 1 | 5 | 57 |
| `Content/` | 2 | 5 | 71 |
| `Minions/` | 1 | 1 | 22 |
| `UI/` | 2 | 2 | 12 |
| `MostWanted/` | 1 | 1 | 9 |
| `Vault/` | 1 | 1 | 8 |
| `Domination/` | 1 | 0 | 1 |

**How to read the evidence claims in this document.** Everything stated as a *number*,
*field*, *signature* or *control-flow shape* was read out of the bytecode or the
verbatim declaration records and is reproducible from the files above. Where I am
inferring from a name, or from a C++/Blueprint boundary the script cannot see, the
sentence says so explicitly. Enum **member names** come from
`tools/usmapdump/mappings.usmap` (the project's own usmap, generated from the game
exe) — the script cache only stores the integer; the pairing of integer→enum type
comes from the cache's own parameter type records.

> ### ⚠ Three decompiler defects found while writing this — read §13 first
> Two are lifter bugs (assignment direction; hidden-return-pointer slot) and are fixed in
> `tools/asdump/asdump_patched.py` with patches written up in
> `tools/asdump/PATCH-lifter-fixes.md`. The third is a control-flow structuring bug that
> can **silently invert the meaning of a guard clause** in up to 46 functions, and is not
> fixed. All three affect every module in the corpus, not just these 22.
> Read [§13](#13-three-decompiler-defects-found-during-this-work) before trusting any body
> text in `tools/asdump/out/modules/` that this document does not quote. Everything quoted
> below is from the corrected run and was hand-checked against the disassembly.

---

## 1. UAV — the radar / reveal system

**Six modules, this is a complete, self-contained gameplay system written entirely in
Angelscript.** A "UAV" is a timed, pulsing *reveal* placed at a world location. It is
SUPERVIVE's radar ping — not a vehicle, not a mode. Server-authoritative; the client only
draws icons.

### 1.1 `UAV/UAVStructs.as` — the config record

```
UCLASS(Placeable, meta.IsBlueprintBase=true, meta.Blueprintable=true)
class FLokiUAVConfig                                   // value type (script struct)
{
    float64 Duration;              // = 11.0
    float64 InitialDelay;          // =  1.0
    float64 Period;                // =  5.0
    float64 BlinkDuration;         // =  0.2
    bool    bShowIndividuals;      // = false
    bool    bShowTeam;             // = false
    float64 InaccuracyDistance;    // = 1500.0
    bool    bRevealVaults;         // = true
    float64 Radius;                // =  0.0   (0 ⇒ unlimited, see below)
    bool    bShowCharacters;       // = false
    bool    bLocalRadar;           // = false

    bool IsInfiniteDuration() const;        // return Duration <= 0
}
```

**Every default above is a literal in the constructor's bytecode**
(`SetV8 v2 0x4026000000000000` → `11.0`, etc.). All eleven are `BlueprintReadable /
BlueprintWritable / EditableOnDefaults / EditableOnInstance`, so shipped UAV items
override them per-asset — these are the *code* defaults, not necessarily any live item's
values.

```
class FActiveUAV                                       // value type (script struct)
{
    bool             bValid;          // = false
    int              ID;              // = 0
    FLokiUAVConfig   Config;
    float64          StartTime;       // = 0.0
    int              TeamIndex;       // = 1        (literally 1 — see note)
    AUAVAudioPlayer@ AudioActor;      // = nullptr
    FVector          SourceLocation;  // = ZeroVector
    int              PulseCount;      // = 0
    int              PlayersDetected; // = 0

    bool    ShouldPulse(const float64 CurrentServerTime) const;
    float64 GetPulseLifespan() const;
    FVector ObfuscateLocation(const FVector& Location) const;
    void    Cleanup();
}

class FUAVCharacterGrouping { TArray<ALokiCharacter@> Characters; }
```

The three core formulas, verbatim from bytecode:

```
ShouldPulse(t)       :  t > StartTime + Config.InitialDelay + PulseCount * Config.Period
GetPulseLifespan()   :  Config.Period - Config.BlinkDuration          // 5.0 - 0.2 = 4.8 s
ObfuscateLocation(L) :  L + Math::VRand() * Math::RandRange(0, Config.InaccuracyDistance)
```

So with stock numbers a UAV **pulses at t+1s, t+6s, t+11s** (3 pulses in an 11 s life),
each pulse's mark lasts **4.8 s** (so the blip visibly blinks off for 0.2 s before the next
pulse), and each revealed position is scattered by a **uniformly random 0–1500 uu offset
in a random 3-D direction**. `Duration <= 0` means the UAV never expires.

> Note on `TeamIndex = 1`: the constructor really emits `SetV4 v1 1`, not `-1`. It is
> overwritten by `ExecuteUAV` before the struct is ever used, so it has no gameplay
> effect; I record it because it is what the bytes say.

### 1.2 `UAV/LokiGameStateUAVComponent.as` — the server-side driver

`ULokiGameStateUAVComponent : UActorComponent`, `bExcludeFromClient = true`,
ticks only while UAVs are active.

```
protected float64 PlayerGroupingDistance;              // = 2000.0   (__InitDefaults)
protected float64 VaultVisionDistance;                 // = 20000.0  (__InitDefaults)
TSubclassOf<AUAVAudioPlayer@>  GlobalAudioActorClass;
protected TSubclassOf<UGameplayEffect@> MarkedTeamGameplayEffectClass;
protected TSubclassOf<UGameplayEffect@> MarkedIndividualGameplayEffectClass;
protected FGameplayTag UAVBlockedGameplayCueTag;       // = GameplayCue.Effect.UAVBlocked
private   FGameplayTag DataTag;                        // = Data
private   FGameplayTag UAVImmunityTag;                 // = Immunity.UAV
private   FGameplayTag UAVUpgradedTag;                 // = State.UAVUpgraded
private   TArray<FActiveUAV>            ActiveUAVs;
private   TArray<AVaultItemSpawner@>    AllVaultItemSpawners;
private   int NextUAVID;                               // = 0
```

Full function list (28; the five `StaticClass/Get/GetOrCreate/Create/ctor` boilerplate
entries omitted):

| signature | UFUNCTION |
|---|---|
| `void Tick_Implementation(const float64 DeltaSeconds)` | BlueprintOverride |
| `void BeginPlay_Implementation()` | BlueprintOverride |
| `FActiveUAV ExecuteUAV(const FLokiUAVConfig& Config, const FVector& SourceLocation, const int TeamIndex = -1)` | BlueprintCallable, **BlueprintAuthorityOnly** |
| `void CancelOngoingUAVs(const int TeamIndex = -1)` | BlueprintCallable, BlueprintAuthorityOnly |
| `private void PulseUAV(FActiveUAV&inout UAV)` | — |
| `private bool ShouldUpgradeUAV(const int TeamIndex)` | — |
| `private void RevealVaultContents(const FActiveUAV& UAV)` | — |
| `private void PulseTeam(const FActiveUAV& UAV, ALokiTeamState@ TeamState)` | — |
| `private TArray<FUAVCharacterGrouping> MakeCharacterGroupings(TSet<ALokiCharacter@>&inout RemainingCharacters)` | — |
| `private FUAVCharacterGrouping GetLargestCharacterGrouping(const TSet<ALokiCharacter@>& Characters)` | — |
| `private bool IsCharacterUAVImmune(ALokiCharacter@ LokiCharacter)` | — |
| `private void GenerateFuzzyLocation(const FActiveUAV& UAV, const FVector& Location, const int PlayerCount, const int TeamIndex, const float64 TeamLevel, const TArray<TSubclassOf<ALokiCharacter@>>& CharacterClasses, const float64 AverageRelicCount, const float64 AverageArmorLevel)` | — |
| `private void PulseIndividual(const FActiveUAV& UAV, ALokiPlayerState@ PlayerState)` | — |
| `private bool IsValidUAVTarget(const FActiveUAV& UAV, ALokiPlayerState@ PlayerState)` | — |
| `private bool IsTeamUAVImmune(ALokiTeamState@ TeamState)` | — |
| `private void NotifyTeamBlockedUAV(ALokiTeamState@ TeamState)` | — |
| `private void CleanupUAV(FActiveUAV&inout UAV)` | — |
| `private TArray<ULokiTeamVaultDataComponent@> GetAllTeamVaultDataComponents()` | — |
| `private void OnVaultDestroyed(AActor@ DestroyedActor)` | BlueprintCallable |
| `private void OnVaultDoorDestroyed(AActor@ DestroyedActor)` | BlueprintCallable |
| `void __InitDefaults()` | — |

**`ExecuteUAV` (the entry point), corrected decompile:**

```cpp
FActiveUAV ExecuteUAV(const FLokiUAVConfig& Config, const FVector& SourceLocation,
                      const int TeamIndex = -1)
{
    v68.FActiveUAV();
    v68.bValid = true;
    v68.ID     = this.NextUAVID;   this.NextUAVID++;
    v68.Config = Config;
    v68.StartTime      = float64(Gameplay::GetServerTime(__WorldContext));
    v68.TeamIndex      = TeamIndex;
    v68.SourceLocation = SourceLocation;
    if (this.GlobalAudioActorClass != nullptr) {
        v78 = SpawnActor(this.GlobalAudioActorClass, SourceLocation, FRotator::ZeroRotator,
                         NAME_None, false, nullptr);
        if (v78 != nullptr) { v78.ActiveUAVCopy = v68;  v68.AudioActor = v78; }
    }
    this.ActiveUAVs.Add(v68);
    this.SetComponentTickEnabled(true);
    return v68;
}
```

`TeamIndex == -1` means "global UAV — reveal everyone to everyone". A `TeamIndex >= 0`
UAV is owned by that team: it skips its own team when scanning, and (per `PulseUAV`) is
suppressed entirely once `ALokiGameMode::IsTeamEliminated(TeamIndex)` is true.

**`PulseUAV` — the per-pulse state machine** (server, once per `Period`):

1. Bail if the `ALokiGameState` is invalid. If team-owned, bail if the owning team is
   eliminated.
2. `UAV.PulseCount++`.
3. **Upgrade check** — `ShouldUpgradeUAV(TeamIndex)`: if *any* living player on the owning
   team has the gameplay tag **`State.UAVUpgraded`** on its ASC, the config is mutated
   *in place* for this and all later pulses to `bShowIndividuals = true`,
   `bShowTeam = true`, `InaccuracyDistance = 0.0`. That is the exact mechanical value of
   the upgrade: **perfect positions, per-player instead of per-blob, and enemy team
   identity revealed.**
4. For every other team's `ALokiTeamState`:
   - `IsTeamUAVImmune` — if *any* living player has **`Immunity.UAV`**, the whole team is
     skipped and `NotifyTeamBlockedUAV` fires the `GameplayCue.Effect.UAVBlocked` cue on
     each of that team's players (so the defenders get feedback that they blocked it).
   - else if `Config.bShowIndividuals`: collect each living player that passes
     `IsValidUAVTarget`.
   - else: `PulseTeam` (blob mode).
5. If `bShowIndividuals`, set `UAV.PlayersDetected = <count>` and `PulseIndividual` each.
6. If `Config.bRevealVaults`, `RevealVaultContents`.
7. If `Config.bLocalRadar` **and** `PlayersDetected == 0` **and** the UAV is team-owned,
   RPC `ClientNotifyLocalRadarEmpty()` to every living owner-team player.

**Immunity is per-character, not just per-team** — `IsCharacterUAVImmune(c)` returns
`c.IsInvisible() || c.IsInBrush()`. Being in brush hides you from a UAV.

**`PulseTeam` — blob mode.** Gathers the team's living characters filtered by
`Config.Radius > 0 ? SourceLocation.Dist2D(c) <= Radius : true` and not UAV-immune, applies
`MarkedTeamGameplayEffectClass` to each with the `Data` set-by-caller magnitude set to
`GetPulseLifespan()`, then **clusters** them with `MakeCharacterGroupings` and emits one
fuzzy blip per cluster carrying the cluster's *averages*:

```
Location        = mean of member ActorLocations
TeamLevel       = mean of member GetLevel()
AverageRelicCount = mean of GetRelicCountForPlayer(c)      // Core/LokiScriptUtility.as
AverageArmorLevel = mean of GetArmorLevelForPlayer(c)      // Core/LokiScriptUtility.as
PlayerCount     = cluster size
```

The clustering is a greedy max-cover: `GetLargestCharacterGrouping` picks, over all
remaining characters `c`, the set of remaining characters within
**`PlayerGroupingDistance = 2000.0` uu** of `c` (3-D `GetDistanceTo`), keeps the largest
such set, and `MakeCharacterGroupings` repeats until the set is empty. So a UAV blip on the
minimap represents "a knot of enemies within 20 m of each other", and the count/level/relic/armor
numbers on it are that knot's averages.

**`PulseIndividual`** does the same for one player: `MarkedIndividualGameplayEffectClass`
with lifespan magnitude, then one blip with `PlayerCount = 1` and that player's real level,
relic count and armor level.

**`GenerateFuzzyLocation`** builds the replicated payload
`FLokiFuzzyPlayerLocationItem` and pushes it into every recipient's
`ULokiFuzzyPlayerLocationComponent`:

```
Source     = ELokiFuzzyLocationSource::UAV (1)
Location   = UAV.ObfuscateLocation(Location)                       // ± InaccuracyDistance
PlayerCount, CharacterClasses (only if Config.bShowCharacters)
ExpiryTime = float32(ServerTime + UAV.GetPulseLifespan())
TeamIndex  = Config.bShowTeam ? <the revealed team> : -1
AverageLevel, AverageRelicCount, AverageArmorLevel  (float32)
if (Config.bLocalRadar) { UAVID = UAV.ID; TotalPlayerCount = UAV.PlayersDetected; }
```

Recipients: if the UAV is team-owned, only that team's
`ALokiTeamState_TeamOnly::GetFuzzyPlayerLocationComponentByTeamIndex`; if global
(`TeamIndex < 0`), every team **except** the one being revealed.

**Vault reveal.** `BeginPlay` (server only) collects every `AVaultItemSpawner` in the level
and binds `OnDestroyed` on both the spawner and its `GetDoor()` destructible.
`RevealVaultContents` then, for each recipient team, walks every vault spawner whose door
is destroyed-or-absent and whose 2-D distance to **any living member of that team** is
`<= VaultVisionDistance = 20000.0` uu, and pushes an `FLokiTeamVaultDataItem`
`{Vault, SourceUAVID, ID, Location, ItemClasses = Vault.GetItemsForUAV()}` into that team's
`ULokiTeamVaultDataComponent`. `CleanupUAV` removes every entry tagged with the expiring
UAV's ID. So **a UAV shows you what's inside already-opened vaults within 200 m of your
team.**

**`Tick_Implementation`** pulses any due UAV, collects the indices of expired ones
(`!IsInfiniteDuration() && StartTime + Duration < now`), cleans and `RemoveAtSwap`es them
back-to-front, and disables its own tick when `ActiveUAVs` is empty.

> One decompiled statement inside that expiry loop reads `v11 = v16.Config.Duration;
> v23 = v11;` where the source clearly intended `ExpiredIndices[i]`. The disassembly shows
> the loop is index-driven and correct; this is a lifter slot-reuse artifact, not game
> behaviour. Flagging it rather than papering over it.

### 1.3 `UAV/LokiPlayerControllerUAVComponent.as` — the client side

```
TSubclassOf<AUAVMapActor@>          UAVMapActorClass;          // errors loudly if unset
TSubclassOf<AUAVVaultContentActor@> UAVVaultContentActorClass; // errors loudly if unset
float64 UAVActivatedEventNotifyCooldown;   // = 25.0
private float64 LastEventNotifyTime;       // = 0.0
private int     LastRadarID;               // = -1
private TArray<FLokiFuzzyPlayerLocationItem> LocalRadarPlayers;
private ALokiPlayerState@ LastRadarPlayer;
```

`BeginPlay` (client only) registers for `FGameEvent_FuzzyPlayerLocation_Add` →
`OnLocationAdded` and `FGameEvent_TeamVaultData_Add` → `OnVaultDataAdded`, and
`Log::Error`s a full sentence if either actor class is unset (the literal strings are in
the const pool: *"…doesn't have UAVMapActorClass set on instance. This is required to show
UAV Map Icons"*).

`OnLocationAdded` ignores anything whose `Source != 1` (i.e. non-UAV fuzzy locations), then
splits two ways:

- **`UAVID == -1` (normal UAV blip):** spawn a `UAVMapActorClass` at `Item.Location` and
  `Init(Item)`. Then, at most once every **25 s**
  (`ServerTime > LastEventNotifyTime + UAVActivatedEventNotifyCooldown`), fire
  `ULokiFuzzyPlayerLocationComponent::BroadcastUAVActivatedEvent(this)` — the "a UAV just
  went up" alert, rate-limited so a stack of UAVs doesn't spam it.
- **`UAVID != -1` (Local Radar):** accumulate items into `LocalRadarPlayers`, resetting the
  buffer whenever `UAVID` changes. Once `LocalRadarPlayers.Num() == Item.TotalPlayerCount`
  (the whole sweep has arrived), convert to `TArray<FLokiLocalRadarEntry>
  {TeamIndex, Location, CharacterClass = CharacterClasses[0], PlayerLevel = AverageLevel}`
  and broadcast `FGameEvent_FuzzyPlayerLocation_LocalRadar`. This is a **batched, all-at-once
  UI reveal** rather than trickled blips.

`AuthNotifyLocalRadarTeammates(Instigator)` (server) walks the instigator's team and
`ClientNotifyLocalRadarInstigator(Instigator)` each — an unreliable client RPC that just
stores `LastRadarPlayer`. `ClientNotifyLocalRadarEmpty()` is the "radar found nothing" RPC.

> The `LocalRadar` path is gated at the feature level by `ELokiGameFeatureToggle::LocalRadarEnabled`
> (**index 145**) — that pairing is from the toggle enum's names, not from this script; the script
> itself only checks `Config.bLocalRadar`.

### 1.4 `UAVMapActor`, `UAVVaultContentActor`, `UAVAudioPlayer`

- **`AUAVMapActor : AActor`** — `Abstract`, non-replicated, client-only visual.
  `int MyItemID`. `Init(Item)` stores `Item.ID`, subscribes to
  `FGameEvent_FuzzyPlayerLocation_Update`/`_Remove`, and calls the BP event
  `ClientUpdateIcon(Item)`; destroys itself if `Item.ID < 0` or there is no event router.
  `OnUpdate` moves the actor and re-fires `ClientUpdateIcon`; `OnRemove` destroys it.
  Everything visual is the Blueprint's job (`ClientUpdateIcon_Implementation` is `NoOp`).
- **`AUAVVaultContentActor : AActor`** — same lifecycle, keyed on
  `VaultDataItem.ID`, exposes `FLokiTeamVaultDataItem VaultDataItem` with
  `meta.ExposeOnSpawn`, BP event `VaultDataItemUpdated()`.
- **`AUAVAudioPlayer : AActor`** — replicated, `bAlwaysRelevant = true`,
  `LokiReplicationStrategy.CustomReplicationStrategy = true`,
  `NetDormancy = DORM_Initial`. Its single property is
  `FActiveUAV ActiveUAVCopy` (Replicated, RepNotify → `OnRep_ActiveUAVCopy`, a `NoOp` BP
  event). **This is how the UAV's existence and config reach clients at all**: the server
  spawns one always-relevant dormant actor per UAV whose replicated payload *is* the whole
  `FActiveUAV`, and the Blueprint plays the ping SFX off the RepNotify.

### 1.5 Answer: what *is* a UAV?

A **timed area radar ping**, spawned by an item/ability (the script never spawns one itself
— `ExecuteUAV` is `BlueprintAuthorityOnly` and is called from outside the script layer).
It reveals enemies as deliberately-inaccurate blobs, upgrades to precise per-player reveals
if the owner has `State.UAVUpgraded`, is defeated by invisibility, brush, or an
`Immunity.UAV` team-wide effect, and doubles as a **vault-contents scanner**. The
`bLocalRadar` variant is a one-shot sweep whose results appear all at once.
Corroborating toggle names in the game's own enum: `BonfireUAVs` (98),
`BRAutomaticUAVOnAudioInFog` (94), `SpawnVisionOnHeroDeath` (137), `LocalRadarEnabled` (145).

---

## 2. Armory + shop — **the in-match economy, in numbers**

This is the answer to "does the project have any economy data": **yes, now it does.**

### 2.1 The currencies

Three named wallet currencies are referenced by string from script, and
`ALokiPlayerState` (bound C++, from `Binds.Cache`) exposes the whole wallet API:

```
int  GetWalletGold();      int GetWalletGems();     int GetWalletShards();
int  GetWalletCurrencyAmount(const FString& CurrencyName);
void GrantWalletCurrency (const FString& CurrencyName, int Amount,
                          ECurrencyGrantReason Reason = ECurrencyGrantReason::Misc);
bool ConsumeWalletCurrency(const FString& CurrencyName, int Amount, bool bIsPurchase = false);
void GrantGold(int GoldAmount, ECurrencyGrantReason Reason = ECurrencyGrantReason::Misc);
void GrantGoldForKill();   void RecordGoldSpent(int Amount);
int  GetGoldScore();  int GetTotalEarnedGold();  int GetTotalSpentGold();
void DropGems(const FVector& SpawnLocation, ALokiPlayerState KillerPlayerState);
TArray<FWalletCurrencySpecification> Wallet;
int GoldPerKill;   int GemsLostOnDeath;   int GoldLostOnDeath;
```

`ECurrencyGrantReason` = `Misc(0), Treasure(1), MonsterKilled(2), DroppedByAlly(3),
DroppedByEnemy(4), Refund(5), Count(6)`.

Item price lives on the item CDO: **`ALokiBaseItem::ShopkeeperGoldPrice` (int)**, alongside
`int GetGoldValue()`, `int GetTotalCostForItem(TSubclassOf<ALokiBaseItem>)`,
`void GetTotalRecipeCost(FLokiItemRecipe, int& TotalGold, TArray<...>& TotalItems)`,
`int GetRecipeCostForInventory(...)`, `int TierNumber`, `int MaxTier`,
`int MaxShardUpgradeTier`, `int EvolutionTier`, `bool bTierAddsGoldValue`,
`int GetXpToTier(int Tier)`. **So the game has a full LoL-style component/recipe item tree
with gold costs, tiers and shard upgrades** — the script layer buys from it, and the
per-item numbers live in the packed data assets, not in script.

### 2.2 `Armory/LokiPlayerControllerArmoryComponent.as` — the Armory shop

`ULokiPlayerControllerArmoryComponent : ULokiPlayerControllerArmoryComponentBase`
(C++ base at `Loki/Source/Loki/Armory/LokiPlayerControllerArmoryComponent.h`).

```
const FName RelicSlotName;    // = "Utility"
const FName PerkSlotName;     // = "MinorUtility"
const FName BootsSlotName;    // = "Boots"
bool bLoadComplete;           // = false
TArray<FString> PurchasedKits;
TArray<UClass@>  LoadedClasses;              (Transient)
FPlayerArmory    DefaultArmory;
ULoadAssetHandle@ Handle;
TArray<TSubclassOf<AActor@>> DisabledItems;        (Replicated)
TArray<FPrimaryAssetId>      DisabledItemAssetIDs; (Replicated)
FGameEventListenerHandle     OnPlayerInitializedHandle;
```

Functions (38 total; boilerplate omitted):

```
bool IsArmoryEnabled()                                              BlueprintPure
TArray<FArmoryShopItem> GetArmoryItemsForShop()                     BlueprintPure
TArray<FArmoryShopItem> GetArmoryTrinkets()                         BlueprintPure  [returns empty]
void ServerSwapSlotAndBuyKit  (const FArmoryShopItem&, const TSubclassOf<ALokiBaseItem@>&, const int)   NetServer
void ServerSellSlotAndBuyItem (const FArmoryShopItem&, const TSubclassOf<ALokiBaseItem@>&, const int)   NetServer
void ServerBuyItem            (const FArmoryShopItem&)                                                 NetServer
void AuthBuyItem              (const FArmoryShopItem& Item)         BlueprintAuthorityOnly
bool AuthSellItemAtSlot (const FName& SlotName, const int SlotIndex) BlueprintAuthorityOnly
bool AuthDropPowerAtSlot(const FName& SlotName, const int SlotIndex) BlueprintAuthorityOnly
bool AuthSellItem_BP(ALokiBaseItem@ Item)                            BlueprintEvent  [default false]
bool ShouldShopSellItem_BP(const TSubclassOf<ALokiBaseItem@>&, AActor@ SourceShopkeep)  [default true]
bool CanBuyItem(const FArmoryShopItem& Item)
int  GetStarCountForItem(const TSubclassOf<ALokiBaseItem@>& ItemClass)
TArray<TSubclassOf<ALokiBaseItem@>> GetArmoryEvolveChoices(ALokiBaseItem@, const int)  [returns empty]
TSubclassOf<ALokiBaseItem@> GetClassFromPrimaryAssetId(const FPrimaryAssetId& Asset)
bool GetIsPrototypeItem(const FPrimaryAssetId& Asset)
bool IsAssetEnabled  (const TSubclassOf<AActor@>& ItemClass)
bool IsAssetIDEnabled(const FPrimaryAssetId& ItemAssetID)
private void OnPlayerInitialized(...)   private void AsyncLoadArmory_Implementation()
private void OnAssetLoadComplete()      private void OnClassLoadComplete(UClass@)
private ALokiPlayerState@ GetPlayerState()
void BeginPlay_Implementation()   void EndPlay_Implementation(const EEndPlayReason)   void __InitDefaults()
```

**`IsArmoryEnabled()` is the only game-feature-toggle read in the entire 78-module
Angelscript layer** (verified by grep over all modules):

```cpp
bool IsArmoryEnabled() {
    if (LokiGameplay::GetFeatureTogglesReady(__WorldContext))
        return LokiGameplay::GetFeatureToggleValue(__WorldContext,
                                                   ELokiGameFeatureToggle::Armory);   // = 106
    return false;
}
```

`AuthSellItemAtSlot`, `AuthDropPowerAtSlot` and `AuthBuyItem` all early-out on it, so with
toggle 106 off the whole Armory is inert.

**The purchase transaction (`AuthBuyItem`) — server-authoritative, decompiled:**

```cpp
if (!IsArmoryEnabled())                     return;
ALokiPlayerState ps = GetPlayerState();  if (ps == nullptr) return;
if (!CanBuyItem(Item))                      return;
int price = Item.Price;
UAbilitySystemComponent asc = AbilitySystem::GetAbilitySystemComponent(ps);
if (asc != nullptr && asc.HasMatchingGameplayTag(GameplayTags::Item_ShopDiscount_DiscountApplied))
    price = int(float64(price) * 0.8);                 // <-- 20 % discount, literal 0x3FE999999999999A
if (ps.GetWalletGold() < price)             return;
ULokiInventoryComponentComboItems inv = ps.GetInventory();  if (inv == nullptr) return;
ALokiBaseItem it = SpawnActor(Item.ItemClass, ZeroVector, ZeroRotator, NAME_None,
                              /*bDeferred*/ true, nullptr);
it.StarCount = GetStarCountForItem(Item.ItemClass);
FinishSpawningActor(it);
if (!inv.TryAddToInventory(it, ELokiAddToInventoryReason::FromGround, NAME_None, -1, true, false)) {
    it.DestroyActor();
} else {
    ps.ConsumeWalletCurrency("Gold", price, /*bIsPurchase*/ false);
    <broadcast FGameEvent_OnItemPurchase_PlayerState{Item=it, GoldCost=price, PlayerState=ps}>
    Log::Log("AuthBuyItem - Sent Purchase Event");
    <ALokiServerAnalyticsManager::AddItemPurchaseEvent(FAnalyticsItemPurchaseEvent{
        Game_Id = LokiAnalytics::GetMatchId(), Player_Id = ps.PlatformPlayerID,
        Item_Id = System::GetClassDisplayName(Item.ItemClass),
        Remaining_Gold = ps.GetWalletCurrencyAmount("Gold"), Cost = price,
        Game_Time = Gameplay::GetServerTime(), Source = EStoreType::Armory (3),
        StarLevel = Item.StarCount + 1 })>
}
```

**Concrete economy facts extracted:**

| fact | value | evidence |
|---|---|---|
| shop discount effect | price × **0.8** (20 % off), integer-truncated | `SetV8 0x3FE999999999999A` + `MULd` + `dTOi` |
| discount trigger | gameplay tag `Item.ShopDiscount.DiscountApplied` on the buyer's ASC | `HasMatchingGameplayTag` |
| price source | `ALokiBaseItem::ShopkeeperGoldPrice` on the CDO | `GetArmoryItemsForShop` |
| currency string | literal `"Gold"` | const pool |
| purchase is atomic | inventory-add first, gold consumed only on success | control flow |
| analytics store id | `EStoreType::Armory = 3` (shopkeeper path uses `None = 0`) | `SetV4 v78 3` / `v80 0` |
| armory star ↔ display | wire `StarLevel` = `StarCount + 1`; `FGameArmoryItem.StarLevel` is 1-based, `FArmoryShopItem.StarCount` is 0-based | `v12 = v40.StarLevel; v12 = v12 - 1` |

**Slot → shop category mapping** (`GetArmoryItemsForShop`, and `EArmoryShopItemType`
from the usmap):

| item's `GetSlotName()` | `FArmoryShopItem.ItemType` |
|---|---|
| `"Boots"` | `EArmoryShopItemType::Boot` (3) |
| `"MinorUtility"` (the *Perk* slot) | `EArmoryShopItemType::Power` (1) |
| `"Utility"` (the *Relic* slot) or `"Inventory"` | `EArmoryShopItemType::Equipment` (2) |
| anything else | `None` (0) |

The list is then sorted by the native `LokiGameplay::SortArmoryItems`.

**`CanBuyItem`** rejects items whose asset id or class is disabled, requires the item to be
present in `GetArmory().ItemsCollection`, and — uniquely for the **Perk** (`MinorUtility`)
slot — rejects a purchase if the player already `HasItemByClass` (no duplicate perks).

**Swap-buy flows.** `ServerSwapSlotAndBuyKit` = `AuthDropPowerAtSlot(slot, idx)` then
`AuthBuyItem`; `ServerSellSlotAndBuyItem` = `AuthSellItemAtSlot(slot, idx)` then
`AuthBuyItem`. Dropping uses `ELokiRemoveFromInventoryReason::Dropped (2)`.
**Selling is not implemented in script** — `AuthSellItem_BP_Implementation` returns `false`;
the real sell logic is Blueprint.

**Armory asset lifecycle.** On the `FGameEvent_GameReady_Controller` event the component
(a) calls the inherited `ShouldUnlockFullArmory()`/`UnlockFullArmory()`, (b) async-loads
every `FGameArmoryItem.PrimaryAssetId` through `ULokiAssetManager::AsyncLoadPrimaryAssets`,
(c) on completion resolves each id to a `ULokiDataAsset_Power`→`.Power` or
`ULokiDataAsset_Equipment`→`.Equipment` soft class and `LoadAsync`es it, and (d) **on the
server only**, records ids/classes that `LokiGameplay::IsAssetIDEnabled` /
`IsAssetEnabled` reject into the two *replicated* `Disabled*` arrays, turning
`SetIsReplicated(true)` on when it needs to send them. Clients then answer
`IsAssetEnabled` locally from those arrays. `RemoveSeasonContentFromFullArmory()` runs if
`bFullyUnlockedArmory` (inherited).

### 2.3 `Armory/LokiArmoryGlobals.as` — the star/tier meta-progression

Module-level statics (`Module_Armory_LokiArmoryGlobalsStatics`), 6 functions:

```
TArray<FString> GetPerTierPowerDescription(const TSubclassOf<ALokiBaseItem@>& ItemClass)
bool  IsItemSpellDescription(ALokiBaseItem@ Item, const int StarCount)
TSubclassOf<UGameplayEffect@> GetUniqueEffectForStar(const TSubclassOf<ALokiBaseItem@>&, const int StarCount)
FText GetArmoryUniqueEffectTextForItem     (ALokiBaseItem@ Item, const FText& InactiveWarningFmt, const FText& LevelUpText)
FText GetArmoryUniqueEffectTextForItemClass(const TSubclassOf<ALokiBaseItem@>&, const FText&, const FText&)
bool  HasEffectsIgnoredInConciseTooltip(const TArray<FLokiArmoryUniqueEffect>& UniqueEffects)
```

Backing data (bound struct, from `Binds.Cache`):

```
FLokiArmoryUniqueEffect { int StarRequirement; int TierRequirement;
                          TSubclassOf<UGameplayEffect> EffectClass;
                          bool bIsItemSpell; bool bIncludeInConciseTooltip; }
```

`GetPerTierPowerDescription` **pre-sizes its output to exactly 6 entries** (`while (v19 < 6)`)
and indexes by `StarRequirement`, so **an Armory item has 6 star tiers, 0–5**.

Out of a match (`!Loki::IsInGameWorld`), the star level is derived from equipment XP in
`UPlayerArmoryModel.InventoryEquipment`:

```
XP <  2  ->  star 0
XP <  5  ->  star 1
else     ->  star 2
```

Those two thresholds (**2 and 5**) are literal `CMPIi` immediates. Note the mismatch: the
description table allows 0–5, but the menu-side XP→star mapping only ever produces 0–2.
I cannot tell from script whether higher stars are unreachable or come from another path.

In-match the same function takes the `ULokiPlayerControllerArmoryComponent` route and asks
the item CDO `HasArmoryTierForUniqueEffectAtIndex(0)` / `MeetsRequirementsForUniqueEffectAtIndex(0)`
/ `HasArmoryStarsForUniqueEffectAtIndex(0)`, formatting either the plain description, a
"level up to unlock" text, or an "inactive" warning.

### 2.4 `Armory/LokiPlayerControllerShopSkylandsComponent.as` — the roaming shop

`ULokiPlayerControllerShopSkylandsComponent : UActorComponent`.

```
FLokiShopInventory SaleItem;                 (Replicated, RepNotify -> OnRep_SaleItem)
TSubclassOf<ULokiLootTable@> ShopSaleTable;  // = nullptr
bool bPlayAnimation;                         // = false (Transient)
```

`FLokiShopInventory` (bound) = `{ TSubclassOf<ALokiBaseItem> ItemClass; int Quantity;
int PriceOverride; EShopItemSource ShopItemSource; bool bPrototype; }`, and
`EShopItemSource` = `None, Shopkeeper, Armory, ShopSale, ArmorySale, EvilShopkeep,
RoguelikeChoice`.

**Pricing rule:** `price = (Item.PriceOverride < 0) ? Item.ItemClass.GetDefaultObject().ShopkeeperGoldPrice
: Item.PriceOverride`. So `PriceOverride < 0` means "use the item's list price"; a
non-negative override is the sale price. The purchase then mirrors `AuthBuyItem` exactly
except **there is no discount-tag check** and the analytics `Source` is
`EStoreType::None (0)`.

**Refresh cadence — this is a real design finding.** `OnDayNightChanged` rerolls the sale
item when:

```
(Event.CurrDayNightState == LDNS_Day && Event.PrevDayNightState == LDNS_Night)
||
(Event.DaysEncountered == 1 && Event.NightsEncountered == 0)      // the very first day
```

i.e. **the shop's featured item rotates once per in-game dawn**, plus one initial roll on
match start (also driven by `OnPlayerInitialized`, server only). `OnRep_SaleItem` sets
`bPlayAnimation = true` so the UI plays a "new stock" flourish; `MarkAnimationPlayed()`
clears it.

**`RollNewShopItem()` is empty in script** — 1 dword of bytecode, just `RET`. The
`ShopSaleTable` (`ULokiLootTable`) is declared but never read from script. The actual roll
is Blueprint/C++. Related toggle names: `BaseCampShopRefreshHourly` (109),
`BaseCampShopRefreshDaily` (110), `BoatShops` (24), `RemoteStore` (138),
`OnDeathStore` (139), `ArenaRemoteStore` (141).

---

## 3. `Items/LokiGem.as` — gems (the second in-match currency)

`ALokiGem : ALokiGemBase` (`Loki/Source/Loki/Items/LokiGemBase.h`), poolable pickup.

```
int   GemCount;            // = 0     (per-gem value; set by whatever spawns it)
int   BonusGemMultiplier;  // = 2
FGameplayTag GemVacuumTag;
bool  bIsVaultItem;        // = false
float32 HeightToStop;      // = 0
bool  bIsMoving;           // = false (Replicated, RepNotify -> OnRep_IsMoving)
float32 NoPickupTime;      // = 0
USceneComponent@ RootSceneComponent;  USphereComponent@ SphereCollision;
UVisibilityReceiver@ VisibilityReceiver;  UProjectileMovementComponent@ ProjMovementComp;
```

Module statics: `FVector GetGemStartingLocationInDirection(const FVector& Origin, const FVector& Direction)`,
`FVector GetGemRandomStartingLocation(const FVector& Origin)`,
`ALokiGem@ SpawnExtraGemWithTeam(const TSubclassOf<ALokiGem@>&, const FVector& SpawnLocation, const int TeamIndex)`.
Methods: `LokiBeginPlay_Implementation`, `EnableGemCollision`, `LokiEndPlay_Implementation`,
`Tick_Implementation`, `OnComponentBeginOverlap(...)`, `TossInDirection(const FVector& Direction,
const float64 Length, const float64 DirectionVariance)`, `Toss()`, `SetToHeightMapLevel()`,
`OnRep_IsMoving()`, `__InitDefaults()`.

**Pickup rule (`OnComponentBeginOverlap`)** — reconstructed from the jump table, **not**
from the tool's if/else rendering (see the warning below):

```cpp
if (bIsVaultItem)                                             return;   // vault gems aren't walk-pickup
ALokiHeroCharacter h = cast<ALokiHeroCharacter>(OtherActor);
if (h == nullptr || !h.IsAlive())                             return;
ALokiPlayerState ps = cast<ALokiPlayerState>(h.PlayerState);
if (ps == nullptr)                                            return;
if (this.TeamIndex != -2 && this.TeamIndex == ps.GetTeamIndex_BP())
                                                              return;   // the OWNING team may not collect
UAbilitySystemComponent asc = AbilitySystem::GetAbilitySystemComponent(ps);
if (asc == nullptr)                                           return;
int amount = asc.HasMatchingGameplayTag(GameplayTags::State_GemMultiplier)
             ? GemCount * BonusGemMultiplier                            // x2
             : GemCount;
ps.GrantWalletCurrency("Gems", amount, ECurrencyGrantReason::Misc);
asc.ExecuteGameplayCue_BP(GemVacuumTag, {Location = GetActorLocation()}, false);
DestroyActor();
```

`TeamIndex == -2` is the sentinel for **unowned** — anyone may pick it up. Any other value
marks the gem as belonging to a team, and **only that team is blocked**; everyone else
collects normally. Combined with the bound `ALokiPlayerState::DropGems(const FVector&
SpawnLocation, ALokiPlayerState KillerPlayerState)` and `GemsLostOnDeath`, this is the
"you drop gems on death and your own team can't just scoop them back up" rule.

> ⚠ **Do not read this function's pickup rule off the shipped pseudo-source.** The tool
> renders the two guard branches as a single `if (TeamIndex != -2) { … } else { <grant> }`,
> which reads as though only unowned gems ever pay out. The bytecode says otherwise: at
> `0x010C` `CMPIi v13,-2` / `JZ → L0154` and at `0x013C` `CMPi v13,v14` / `JNZ → L0154`
> both jump **to the same shared grant block**, i.e. two early-outs into common code, not an
> if/else. I made this mistake first and caught it only by hand-decoding; it is a good
> example of the residual risk called out in §15.

**Numbers:**

| thing | value |
|---|---|
| gem multiplier tag | `State.GemMultiplier` → **×2** (`BonusGemMultiplier`) |
| currency string | `"Gems"` |
| pickup sphere radius | **400.0** uu (`SetSphereRadius(0x43C80000)`), object type `ECC_GameTraceChannel4` |
| resting height | heightmap Z **+ 75.0** (`SetToHeightMapLevel`) |
| toss stop height | heightmap Z **+ 35.0** (`TossInDirection`) |
| toss elevation angle | random **55.0°–75.0°** |
| toss yaw spread | uniform in ±`DirectionVariance / 2` |
| `Toss()` defaults | direction `(1,0,0)`, length **RandRange(100, 500)** (int), variance **360.0°** |
| spawn scatter | `GetGemStartingLocationInDirection` offsets by `RandRange(0, 150.0)` along the normalized 2-D direction |
| projectile movement | `MaxSpeed 1000.0`, `MaxSimulationIterations 1`, `MaxSimulationTimeStep 0.5` |
| pooling | `bEnablePooling = true`, `PoolPrimeSize = 100` |
| replication | `NetDormancy = DORM_Awake`, `LokiReplicationStrategy.bVision = true`, `bDistanceBased = false` |

`NoPickupTime > 0` disables the sphere and re-enables it via
`System::SetTimer(this, n"EnableGemCollision", NoPickupTime, ...)` — the anti-instant-vacuum
window. `Tick` stops the projectile and clears `bIsMoving`/`SetReplicateMovement(false)`
once `GetActorLocation().Z <= HeightToStop`, and clients mirror the stop through
`OnRep_IsMoving`.

---

## 4. `Items/LokiTeamElimBoxComponent.as` — the team-wipe deathbox

`ULokiTeamElimBoxComponent : UActorComponent` (`bExcludeFromClient = true`).

```
TArray<FName> InventorySlots;              // which slots transfer
TSubclassOf<ALokiSearchableBox@> TeamElimBoxClass;
TSubclassOf<ALokiBaseItem@>      GoldDropClass;
TArray<FName> T0SlotsToDestroy;            // slots whose Tier-0 items are destroyed, not dropped
int MinimumInsuredGoldValue;               // = 0   (declared; never read in script)
TMap<int, ALokiSearchableBox@> TeamIndexToBoxMap;   // declared; never read in script
TArray<ALokiPlayerState@> PlayersQueue;            // declared; never read in script
private FTimerHandle UpdateTimerHandle;            // declared; never read in script
```

```
AActor@ DropWipedTeamInventories(AActor@ LastVictimActor, APawn@ WipeInstigator, const int TeamIndex)
FVector FindLocationForBox(const FVector& Origin, AActor@ KilledCharacter)
void TransferInventoryItems(ALokiPlayerState@, ULokiInventoryComponentBase@ Destination, TArray<ALokiBaseItem@>&inout OutDeniedItems)
void TransferKilledPlayerGold(ALokiHeroCharacter@ KilledCharacter, ULokiInventoryComponentBase@ BoxInventory)
bool ShouldTransferItem(ALokiBaseItem@, ALokiPlayerState@)                 BlueprintEvent [default true]
void PostTransferToTeamElimBox(ULokiInventoryComponentBase@, const TArray<ALokiBaseItem@>& DeniedItems)  BlueprintEvent [NoOp]
```

**Placement (`DropWipedTeamInventories`)** — this is the "where does the loot box land"
algorithm:

1. Start at the last victim's location. **Abyss rescue:** if
   `ALokiHeightMap::IsAbyss(loc, true)`, substitute the *killer's*
   `ULokiCharacterMovementComponent.LastWalkingLocation` (or the victim's if the killer
   isn't a hero) — so a team wiped over the void still drops a reachable box.
2. Try `LokiProjection::SimpleProjectToUnobstructedTerrain(ctx, loc, out, **1000.0**,
   **5000.0**, victim, false, 0, **10**, "")` and `ALokiBaseItem::IsValidItemLocation`.
3. Failing that, `FindLocationForBox`: up to **10** attempts of
   `UNavigationSystemV1::GetRandomLocationInNavigableRadius(origin, out, **250.0**, ...)`
   each re-validated by the same terrain projection; if all 10 fail, fall back to the
   origin with **Z − 90.0**.
4. `SpawnActorFromClass(ctx, TeamElimBoxClass, <location>, FRotator(), null,
   ESpawnActorCollisionHandlingMethod::AlwaysSpawn, null)`, then for every
   `ALokiPlayerState` on the team `TransferInventoryItems`, then `TransferKilledPlayerGold`,
   then the BP hook `PostTransferToTeamElimBox`.

> **Apparent bug in the shipped script, reported as written.** Both branches of the
> location decision assign into local slot **22** (`v22 = v40` on the projection-success
> path at `0x02FC`, `v22 = v16` from `FindLocationForBox` at `0x0330`), but the
> `SpawnActorFromClass` call at `0x0388` pushes slot **40** — the *projection output
> temp* — as its `FVector Location` argument (`0x036C PSF v40`). On the success path the
> two are equal so it makes no difference; on the fallback path the box would spawn at the
> failed projection's output rather than at the navmesh location that was just computed,
> and the `FindLocationForBox` result is discarded. The operand slots are unambiguous in
> the disassembly and both `opAssign` calls have their `this` on top of the stack, so this
> is not the lhs/rhs inversion of §13.1. I cannot rule out that the *pattern* is intended
> (e.g. the native projection leaves a usable value in its out-param on failure), so I
> state the operands rather than assert a defect. If deathbox placement ever looks wrong
> in a revived build, start here.

**Item filter (`TransferInventoryItems`)**, in order — an item is transferred only if:
`IsValid`; *(always)* `PlayerState.AddItemToElimInventorySnapShot(item)`;
`item.bDropOnTeamElimination`; `!item.bStarterItem`;
`InventorySlots.Contains(item.GetSlotName())`;
**not** (`T0SlotsToDestroy.Contains(slot)` **and** `item.TierNumber == 0`);
and the BP hook `ShouldTransferItem` returns true (otherwise it lands in `OutDeniedItems`).
Before transfer, `item.PlayerStateDupeArray` is cleared if non-empty (so dupe-upgrade
provenance doesn't survive into the box).

**Gold (`TransferKilledPlayerGold`)** — the concrete death-tax formula:

```cpp
if (!GetLokiGameMode().bDropCurrencyOnPlayerDeath)   return;
int gold = ps.GetWalletGold();  if (gold <= 0)       return;
int amount = Math::RoundToInt(GameMode.GetGoldDeathboxTransferRatio() * float32(gold));
ALokiBaseItem drop = SpawnActor(GoldDropClass, ..., /*bDeferred*/ false, ...);
drop.DroppedAsCurrency(ps, amount);                        // UFunction ReceiveDroppedAsCurrency
BoxInventory.TryAddToInventory(drop, ELokiAddToInventoryReason::Created, NAME_None, -1, true, false);
ps.ConsumeWalletCurrency("Gold", amount, false);
```

`GetGoldDeathboxTransferRatio()` is a C++/BP getter (`ALokiGameMode`), so the *ratio* is not
in script — but the *shape* is: a configurable fraction of the wiped player's gold becomes a
physical gold item inside the box and is deducted from the wallet. `ALokiGameMode` also
exposes `bUsesDeathboxes`, `GoldScale`, `GetGoldScaleMultiplier()`;
`ALokiPlayerState` exposes `GoldLostOnDeath` and `GemsLostOnDeath`.

---

## 5. `Items/LokiItemVisualsComponent.as` — recommended / preferred item highlighting

Client-only (`Loki::LokiIsClient` gate; every accessor returns `false` on the server).
Two memoizing maps keyed on `Item.BaseClass`:

```
private TMap<TSubclassOf<ALokiBaseItem@>, bool> RecommendedItems;
private TMap<TSubclassOf<ALokiBaseItem@>, bool> PreferredItems;

bool IsRecommendedItem(ALokiBaseItem@ Item)      BlueprintPure
bool EvaluateItemRecommended(const TSubclassOf<ALokiBaseItem@>& ItemClass)
bool IsPreferredItem(ALokiBaseItem@ Item)        BlueprintPure
bool EvaluateItemPreferred(ALokiBaseItem@ Item)
private void OnInventoryItemAdded  (const FGameEvent_OnInventoryItemAdded_PlayerState&, const ALokiPlayerState@)
private void OnInventoryItemRemoved(const FGameEvent_OnInventoryItemRemoved_PlayerState&, const ALokiPlayerState@)
```

- **Recommended** = the class is in the local hero's
  `DefaultRecommendedLoadout.GetDefaultObject().ItemClasses`. **Every hero ships a
  recommended build list** (`ALokiLoadout.ItemClasses`).
- **Preferred** = any of the item's `InventoryEffects` modifies any attribute in the local
  hero's `RelevantEquipmentAttributes`, tested with
  `UAbilitySystemComponent::GetEffectModifierValueAtLevel(effect, attr, 0, ...)`. So
  "preferred" means *this item's stats are stats my hero actually scales with* — computed,
  not authored.
- Both return `true` when there is no local character yet (so the UI doesn't grey
  everything out during load) and cache the result forever after.
- Inventory add/remove events call `DirtyDupeVisuals()` on **every actor of the item's
  `BaseClass` in the world** when `bAllowUpgradesFromDupes` — the "you now hold a duplicate,
  restyle the pickup glow" refresh.

---

## 6. `Interaction/LokiInteractionPlayerComponent.as` — the "usable" / interact system

The largest module here (72 functions, ~4.7 KB of bytecode). Client-side driver for
everything you press the interact key on. `ULokiInteractionPlayerComponent :
ULokiPlayerInteractionComponent` (`Loki/Source/Loki/Player/LokiPlayerInteractionComponent.h`).

Helper value type:

```
class FLokiUsableData {
    AActor@ Actor;  UPrimitiveComponent@ OverlapComponent;  ULokiUsableComponent@ UsableComponent;
    FLokiUsableData();
    FLokiUsableData(AActor@, UPrimitiveComponent@, ULokiUsableComponent@);
    bool Equals(const FLokiUsableData&) const;      // Actor == && OverlapComponent ==
    bool NotEquals(const FLokiUsableData&) const;
    void SetData(AActor@, UPrimitiveComponent@, ULokiUsableComponent@);
    void Clear();
}
```

Three script delegates: `FOnInteractionUsableChangedDelegate(AActor@ UsableActor,
UPrimitiveComponent@ UsableActorOverlapComponent)`, `FOnInteractionPressedDelegate(AActor@)`,
`FOnInteractionReleasedDelegate(AActor@)`.

State:

```
protected ALokiPlayerController@  CachedLokiPC;
protected ALokiHeroCharacter@     CachedLokiCharacter;
protected ULokiAbilitySystemComponent@ CachedLokiAbilitySystem;
protected ULokiHeroUsableComponent@    UsableDetectionComponent;
protected FLokiUsableData ActiveUsable, SelectedUsable, HoveredUsable, FocusedUsable;
protected TArray<AActor@> UsableList;
protected bool    bInteractionInputPressed;
protected float64 InteractionCooldownStartTime;
protected float64 MinInteractionCooldownTime;            // = 0.2
protected bool    bInputHoldInteractionCanProcess;
protected bool    bCanProcessBufferedInteraction;
protected float64 ProcessInteractionBufferStartTime;     // = -1.0
const     float64 MaxProcessBufferedInteractionTime;     // = 0.5
protected bool    bHoveredComponentIsValid;
const     bool    bIsSupportingCooldownBuffering;        // = true
UAkAudioEvent@ UsableNotFoundAudio;
```

Component functions:

```
void BeginPlay_Implementation()                void Tick_Implementation(const float64 DeltaSeconds)
void OnTest(const FGameEvent_SpellOutcome_PlayerState&, const ALokiPlayerState@)   [dead: empty loop body]
void AddUsable(AActor@ InUsable)               void RemoveUsable(AActor@ InUsable)
void ProcessInteractionInputPressed()          void ProcessInteractionInputReleased()
void CancelUsableIfActive(AActor@ InUsableActor)   bool RequestCancelActiveUsable()
bool IsActorFocusedUsable(AActor@ InActor)
protected void OnPlayerInitialized(const FGameEvent_GameReady_Controller&, const EGameEventStatefulEventType, const AController@)
protected void OnSpawnedCharacterChangedCalled(const ALokiCharacter@ NewCharacter)
protected void ClearUsables()
protected FLokiUsableData CancelActiveUsable(const ELokiUsableInteractionEndResult ResultType)
protected bool ShouldCancelActiveUsableInteraction()
protected void OnLivingStateChangedCalled(const ELivingState, ALokiCharacter@)
protected void OnAbilitySystemInitializedCalled(ULokiAbilitySystemComponent@)
protected void OnGameplaySpellAddedCalled(UGameplayAbility@ Ability, UObject@ SourceObject)
protected void ProcessInteractionSelection()   protected void UpdateSelectedUsable()
protected bool IsInUsableList(AActor@)         void ProcessActiveInteraction()
protected void ActivateUsable(const FLokiUsableData& InUsable)
protected bool InteractionsAreOnCooldown() const   protected void ResetInteractionsCooldown()
protected void StartProcessInteractionBuffer()     protected void StopProcessInteractionBuffer()
protected bool CanProcessBufferedInteraction()
void TryProcessingBufferedInput(ULokiUsableComponent@ UsableComp)
```

### The state machine

**Four slots, in priority order.** `HoveredUsable` (what the mouse is over),
`SelectedUsable` (what would be used if you pressed now), `FocusedUsable` (what the prompt
UI is showing), `ActiveUsable` (what is mid-interaction).

`ProcessInteractionSelection()` (client only) runs on every tick with hovering enabled and
on every `AddUsable`/`RemoveUsable`/living-state change:

```
if (!alive)                        -> CancelActiveUsable(InstigatorLivingStateChange); UpdateSelectedUsable(); return
SelectedUsable.Clear()
if (HoveredUsable.Actor is in UsableList && HoveredUsable.UsableComponent.CanBeUsed(me))
        SelectedUsable = HoveredUsable                      // mouse-over wins
else    SelectedUsable.Actor = ULokiUsableComponent::GetHighestPriorityUsable(me, UsableList)
SelectedUsable.OverlapComponent =
        UsableDetectionComponent.GetClosestOverlappingComponentWithTags(SelectedUsable.Actor)
UpdateSelectedUsable()
```

`UpdateSelectedUsable()` reconciles `FocusedUsable` with `SelectedUsable`, calls
`Unfocus()`/`Focus(OverlapComponent)` on the components, asks
`GetPrompt(character, overlapComponent)` for the prompt text, `SetInteractionUIPrompt`s it
and broadcasts `OnInteractionUsableChanged`. **Failure prompts:** if nothing is focusable but
`UsableList` is non-empty, it takes `UsableList[0]`, asks `GetFailurePrompt(...)`, and if
non-empty focuses *that* — this is how you get "you need a key" style messaging on something
you cannot actually use.

**Press path (`ProcessInteractionInputPressed` → `ProcessActiveInteraction`):**

```cpp
if (InteractionsAreOnCooldown()) { if (bIsSupportingCooldownBuffering) StartProcessInteractionBuffer(); return; }
ResetInteractionsCooldown();
bInteractionInputPressed = true;
ELokiUsableInteractionEndResult reason = RepressInterrupted (4);
bool repressRestart = false;
if (ActiveUsable.UsableComponent != nullptr && ActiveUsable.UsableComponent.IsUsableInteracting(me)) {
    auto behavior = ActiveUsable.UsableComponent.GetActiveInteractionRepressBehavior(me);
    if (int(behavior) == 0)                 return;              // 0: ignore the re-press entirely
    repressRestart = (int(behavior) == 2);
    reason = repressRestart ? RepressRestart (5) : RepressStopped (6);
}
FLokiUsableData cancelled = CancelActiveUsable(reason);
if (SelectedUsable.Actor == nullptr) {
    if (CachedLokiCharacter != nullptr && !CachedLokiCharacter.HeroPredropHidden)
        LokiAudio::PostEventActor(ctx, UsableNotFoundAudio, CachedLokiCharacter);   // the "nope" click
    StartProcessInteractionBuffer();
} else if (SelectedUsable.NotEquals(cancelled) || repressRestart) {
    ActivateUsable(SelectedUsable);              // -> ActiveUsable = SelectedUsable; StartInteraction(...)
}
OnInteractionPressed.Broadcast(ActiveUsable.Actor);
```

**Release path:** if `bInteractionInputPressed`, clear it, broadcast `OnInteractionReleased`,
and — **only if the hero does not have the `State.Knocked` tag** — call
`ActiveUsable.UsableComponent.UpdateInteraction(character, ELokiUsableInteractionInputType::OnRelease)`.
(A knocked player's release does not complete a hold-interaction.)

**Cooldown + input buffering — concrete timings:**

| knob | value | meaning |
|---|---|---|
| `MinInteractionCooldownTime` | **0.2 s** | minimum gap between two accepted interact presses |
| `MaxProcessBufferedInteractionTime` | **0.5 s** | how long a press pressed *during* cooldown / on nothing stays queued |
| `bIsSupportingCooldownBuffering` | `true` | buffering is on by default |

Both windows use `GetWorld().GetTimeSeconds()`. Every tick,
`TryProcessingBufferedInput(ActiveUsable.UsableComponent)` re-fires
`ProcessActiveInteraction()` when either (a) the usable does **not** require an input hold
and the buffer is still inside its 0.5 s window, or (b) the usable **does** require a hold,
the key is still down, and `bInputHoldInteractionCanProcess` is set. That is a real
quality-of-life feature: **press interact up to 0.5 s early and it still lands.**

**Cancellation** (`CancelActiveUsable`) bails on server, on missing actor/component/character,
and if the component reports `IsInteractionEnding`. Otherwise it calls
`StopInteraction(character, ELokiUsableActionNetworkType::ClientOnly, ResultType)`,
`CachedLokiPC.ForceCloseUI()`, clears `ActiveUsable`, and returns the cancelled data.
Callers and their reasons:

| caller | `ELokiUsableInteractionEndResult` |
|---|---|
| `RemoveUsable` (usable left range) | `UsableRemoved (10)` |
| `CancelUsableIfActive`, `RequestCancelActiveUsable` | `Interrupted (3)` |
| `ProcessInteractionSelection` (died/knocked), `OnSpawnedCharacterChangedCalled` | `InstigatorLivingStateChange (8)` |
| re-press | `RepressInterrupted (4)` / `RepressRestart (5)` / `RepressStopped (6)` |

`OnGameplaySpellAddedCalled` forwards the current press state into a newly granted
`ULokiGameplayUsableSpell` via `InitializeLocalSpellInput(bInteractionInputPressed)` — so an
ability granted *by* the thing you are holding down inherits "the key is already down".

---

## 7. `MostWanted/LokiGameStateMostWantedComponent.as` — the bounty system

Tiny but decisive. `ULokiGameStateMostWantedComponent : UActorComponent`, replicated, no tick.

```
int MostWantedCount;         (Replicated)   // = 0
int ActiveMostWantedCount;   (Replicated)   // = 0

void BeginPlay_Implementation()                          // server only: subscribe FGameEvent_MostWanted
void HandleMostWantedEvent(const FGameEvent_MostWanted& Event, const AActor@& Context)
void __InitDefaults()
```

`FGameEvent_MostWanted` carries a single field `EMostWantedState State`, and the usmap gives
its members. The handler is a 5-way `JMPP` jump table over `int(Event.State)`, range-checked with
`CMPIi 4 / JP` and `CMPIi 0 / JS` and falling through to a bare
`asBC_ThrowException` (operand 0) if the value is out of range. Decompiled and named:

| `EMostWantedState` | value | effect |
|---|---|---|
| `None` | 0 | no-op |
| `Spawn` | 1 | `MostWantedCount++` |
| `Destroy` | 2 | `MostWantedCount = Math::Max(0, MostWantedCount - 1)` |
| `StartQuest` | 3 | `ActiveMostWantedCount++` |
| `EndQuest` | 4 | `ActiveMostWantedCount = Math::Max(0, ActiveMostWantedCount - 1)` |

**So "Most Wanted" is a spawnable bounty-target system with an associated quest.** Two
distinct counters, replicated to all clients: how many bounty targets exist in the world
(`Spawn`/`Destroy`), and how many bounty *quests* are currently being pursued
(`StartQuest`/`EndQuest`). The script layer only keeps the scoreboard; who spawns a Most
Wanted, what the reward is, and what the quest asks for are all outside Angelscript.
(The names `QuestGivers` (19), `TalentQuests` (16), `QuestsBeginner` (85),
`QuestsExperienced` (86) appear in the feature-toggle enum; I have no bytecode linking any
of them to this component.)

---

## 8. `Domination/LokiDominationUtilities.as` — a named mode, one function of it

The entire module is one static:

```
UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, CanOverrideEvent, Static)
ALokiPlayerStart@ GetDominationSpawnForPlayer(ALokiPlayerState@ PlayerState)
```

Algorithm, verbatim:

1. `GetAllActorsOfClass(ALokiPlayerStart)`.
2. Keep only starts whose `PlayerStartTag == n"Domination"` — **Domination maps mark their
   spawn points with the literal tag `"Domination"`.**
3. For each such start, compute the 2-D distance to the nearest **living enemy** hero
   (`GetTeamIndex_BP() != mine`, `IsValid(GetLokiCharacter())`), seeded at the sentinel
   `999999.0`.
4. Pick the start that **maximises** that minimum distance (classic max-min "safest spawn").
5. If none qualified, pick a uniformly random `ALokiPlayerStart`
   (`Math::RandRange(0, Num-1)`).

**So Domination is a respawn-based, team-vs-team mode.** That is not an inference from the
directory name: the function is `BlueprintAuthorityOnly`, takes a `PlayerState`, and exists
purely to answer "where do I put this player back". Everything else about the mode —
capture points, scoring, timers — is C++/Blueprint; the feature-toggle enum contains
`RespawnOnCapturePoints` (90), which is consistent, but I have no bytecode tying it to this
module.

---

## 9. `Vault/VaultItemSpawner.as` — vaults

An **abstract, Blueprint-implementable** actor with a two-function contract:

```
UCLASS(SuperIsCodeClass, Abstract, Placeable, meta.IsBlueprintBase=true, meta.Blueprintable=true)
class AVaultItemSpawner : AActor
{
    TArray<TSubclassOf<ALokiBaseItem@>> GetItemsForUAV();   // BlueprintEvent, default: empty
    ALokiDestructible@                  GetDoor();          // BlueprintEvent, default: null
}
```

That is the whole module. Its meaning comes from its only consumer, the UAV component
(§1.2): **a vault is a level-placed loot container guarded by an `ALokiDestructible` door;
its contents can be *scanned* by a UAV once the door is destroyed, out to 20 000 uu from a
teammate, and the scan result is replicated per-team through
`ULokiTeamVaultDataComponent` as `FLokiTeamVaultDataItem`.** When the door or the vault is
destroyed, `OnVaultDoorDestroyed`/`OnVaultDestroyed` purge the team vault data.
`ALokiSearchableBox` (the deathbox class) is a *different* type, so vaults and deathboxes
are separate systems. Feature toggle `VaultsV3` (42) exists.

---

## 10. `Minions/LokiNodePathingComponent.as` — waypoint patrolling AI

Generic "walk a loop of level-placed nodes" component for AI characters. Not
Barracuda-specific (that mode has its own `BarracudaMinionWaypoint*` modules).

```
TArray<AActor@> PathNodeActors;      // authored per-instance
float64 RotationPrecision;           // = 10.0  (degrees)
TArray<AActor@> CurrNodeActorList;   // the shuffled queue
ALokiCharacter@ OwningCharacter;  AAIController@ OwningAIController;
AActor@ LastPathingActor;         AActor@ RotateToActor;
```

```
void LokiBeginPlay_Implementation()   void Tick_Implementation(const float64 DeltaSeconds)
void InitializeAIController()         void SetPathNodes(TArray<AActor@>&inout PathActors)
void OnControllerChanged(APawn@, AController@ Old, AController@ New)
void OnAIControllerInitialized()      void StartMoving()
void BuildNodeActorList()             void OnMoveCompleted(const FAIRequestID&, const EPathFollowingResult)
void StartRotatingToActor(AActor@)    void UpdateRotationToActor(const float64 DeltaSeconds)
void OnFinishedRotatingToActor()      bool MoveToActor(AActor@ LocationActor)
AActor@ FindClosestPathingActor()     AActor@ FindRandomPathingActor(TArray<AActor@>&inout IgnoreActors)
```

Server-only. Cycle:

```
LokiBeginPlay -> InitializeAIController  (or wait on ReceiveControllerChangedDelegate)
             -> OnAIControllerInitialized: bind ReceiveMoveCompleted, SetTimerForNextTick("StartMoving")
StartMoving  -> LastPathingActor = FindClosestPathingActor(); StartRotatingToActor(it); OwningCharacter.SetIdle(false)
StartRotatingToActor(a) -> RotateToActor = a; OwningAIController.SetFocus(a)
Tick -> UpdateRotationToActor(dt):
        angle = RadiansToDegrees(Acos(Forward.CosineAngle2D(normalize(target - me))))
        (angle forced to 1.0 rad-cos when either vector IsNearlyZero(1e-4))
        if (angle < RotationPrecision /*10 deg*/) { RotateToActor = nullptr; OnFinishedRotatingToActor(); }
OnFinishedRotatingToActor -> MoveToActor(LastPathingActor)
MoveToActor(a) -> OwningAIController.MoveToActor(a, AcceptanceRadius = 100.0,
                     bStopOnOverlap = true, bUsePathfinding = true, bCanStrafe = false,
                     FilterClass = null, bAllowPartialPath = true)
                  returns true iff result == 2
OnMoveCompleted -> if queue empty, BuildNodeActorList();
                   LastPathingActor = CurrNodeActorList[0]; RemoveAt(0); StartRotatingToActor(it)
BuildNodeActorList -> a random permutation of PathNodeActors that never repeats the
                      node just visited (seeded with LastPathingActor in the ignore set)
```

**Numbers: turn tolerance 10.0°, move acceptance radius 100.0 uu.** The AI *turns to face*
the next node before it starts walking — that is why patrolling minions pivot in place.

---

## 11. `DayNightController/LokiDayNightController.as` — day/night hooks

`ALokiDayNightController_AS : ALokiDayNightController`
(`Loki/Source/Loki/World/LokiDayNightController.h`), replicated. The script half is a thin
delegate/cheat surface; the cycle itself is C++.

Four script delegate types (each generating ~11 boilerplate functions — that is where 57 of
this module's functions go):

```
FTimelineChangedDelegate      OnTimelineChanged;       Broadcast(const float64 SimpleTrack, const float64 RampTrack)
FDayNightStateChangedDelegate OnDayNightStateChanged;  Broadcast(const ELokiDayNightState Current, const ELokiDayNightState Next)
FDayBeginDelegate             OnDayBegin;              Broadcast()
FDayEndDelegate               OnDayEnd;                Broadcast()
```

Real functions:

```
bool IsCharacterInShadow(ALokiCharacter@ Character) const     BlueprintPure -> BP_IsCharacterInShadow
void AuthCheatNightToDay(const float64 Time)                  NetMulticast  -> BP_CheatNightToDay
void AuthCheatDayToNight(const float64 Time)                  NetMulticast  -> BP_CheatDayToNight
protected bool BP_IsCharacterInShadow(ALokiCharacter@) const  BlueprintEvent [default false]
protected void BP_CheatNightToDay(const float64 Time)         BlueprintEvent [NoOp]
protected void BP_CheatDayToNight(const float64 Time)         BlueprintEvent [NoOp]
```

**`AuthCheatNightToDay` / `AuthCheatDayToNight` are `NetMulticast` UFUNCTIONs taking a
transition time** — i.e. shipped, callable day/night cheats that replicate to all clients.
That adds two entries to the project's cheat-surface inventory.

`ELokiDayNightState` = `LDNS_Day(0), LDNS_Night(1), LDNS_EndGame(2)`, and
`FGameEvent_DayNightChanged` carries
`{CurrDayNightState, PrevDayNightState, NextDayNightState, LastStateChangeServerTime,
StateLifetime, TotalDays, TotalNights, DaysEncountered, NightsEncountered}`. That struct is
what the shop-refresh rule in §2.4 reads, and `IsCharacterInShadow` is what night-time
stealth mechanics query.

---

## 12. `UI/` and `Content/`

### 12.1 `UI/Character/LokiOffscreenTeamIndicatorWidget.as`

`ULokiOffscreenTeamIndicatorWidget_AS : ULokiOffscreenTeamIndicatorWidget`. The
"teammate is off-screen that way" arrow.

```
private const FText Meters;      // = FText::FromString("m")
private const FText Kilometers;  // = FText::FromString("km")

protected void GetHeroLocations(FVector&out LocalPlayerLocation, FVector&out AllyLocation, bool&out bLocationsValid)
protected void CalculateImageAngle(const FVector& LocalPlayerLocation, const FVector& AllyLocation, float32&out ImageAngle) const
protected void CalculateAnchors(const FVector& LocalPlayerLocation, const FVector& AllyLocation,
                                const float64 InsetMultiplier, FVector2D&out Anchors) const
```

`ImageAngle = FRotator::MakeFromX(Ally - Me).Yaw`.
`Anchors = normalize(FVector2D(Me.X - Ally.X, Me.Y - Ally.Y)) * (InsetMultiplier * -0.5) + (0.5, 0.5)`
— i.e. a unit direction mapped into UMG anchor space centred on `(0.5, 0.5)` with the inset
controlling how far toward the screen edge the arrow sits. The `"m"`/`"km"` unit strings
confirm distances are surfaced to the player in metres.

### 12.2 `UI/LokiWidgetHighlighterHitTestBlocker.as`

`ULokiWidgetHighlighterHitTestBlocker_AS : UUserWidget` — the tutorial/onboarding
"spotlight" that blocks clicks everywhere except one widget.

```
UWidget@ TargetWidget;
UOverlay@ TopBlocker, LeftBlocker, BottomBlocker, RightBlocker;   (meta.BindWidget)
bool bHideBasedOnActivatableParent;

void SetTargetWidget(UWidget@ Target, const bool bShouldHideBasedOnActivatableParent = false)
void Tick_Implementation(const FGeometry& MyGeometry, const float64 DeltaTime)
```

Per tick it takes the target's cached geometry in absolute space, converts to viewport-local
by subtracting the viewport widget's absolute position and dividing by
`WidgetLayout::GetViewportScale`, and sizes the four overlays to the leftover margins
(`(pos.X, 0)`, `(0, pos.Y)`, `(viewport - (pos+size)).X`, `.Y`). It collapses all four to
zero when the viewport or scale is degenerate, the target is invisible or zero-sized, or
(when `bHideBasedOnActivatableParent`) the target's nearest `UCommonActivatableWidget`
ancestor — found via `ULokiUIUtilities::FindParentWidgetOfAnyType` — is not activated.

### 12.3 `Content/TemporaryFloor.as` — collapsing platforms

`ATemporaryFloor : ALokiTemporaryFloorBase`
(`Loki/Source/Loki/Character/LokiTemporaryFloorBase.h`). One of only **four
script-declared enums in the entire cache**:

```
enum ETemporaryFloorState { Alive = 0, Triggered = 1, Fading = 2, Dead = 3, Respawning = 4, Max = 5 }
```

```
protected USceneComponent@ RootSceneComponent;  protected UStaticMeshComponent@ StaticMeshComponent;
protected UBoxComponent@ BackupMantleCollision; protected bool bGenerateBackupMantleCollision; // = true
protected UStaticMesh@ StaticMesh;
float64 DefaultTriggeredDuration;   // = 1.0
float64 DefaultFadingDuration;      // = 1.0
float64 DefaultDeadDuration;        // = 1.0
float64 DefaultRespawningDuration;  // = 1.0
protected TMap<ETemporaryFloorState, UAkAudioEvent@> StateAudioEvents;
protected bool bShowDebug;                                   // = false
private ETemporaryFloorState LocalState;                     // = Alive
private float64 LastTriggerTime;      (Replicated, RepNotify -> OnRep_LastTriggerTime)  // = -1.0
private float64 LastHeightMapDirtyTime;                      // = -1.0
private TMap<ETemporaryFloorState, float64> StateToCumulativeDurationMap;  (Transient)
private FTimerHandle NextUpdateTimerHandle;
```

**Mechanism — one replicated float drives everything.** The server writes
`LastTriggerTime = ServerTime` when a `ALokiCharacter` steps on it
(`Script_BeginCharacterBase` from the C++ base, or an `OnComponentHit` on either the mesh
or the backup mantle box), and wakes the actor from `DORM_DormantAll`. Clients recompute
their own state from `Loki::GetServerTimeSince(LastTriggerTime)` against
`StateToCumulativeDurationMap`, which `BeginPlay` fills as a prefix sum:

```
Triggered  -> 0
Fading     -> GetTriggeredDuration()
Dead       -> + GetFadingDuration()
Respawning -> + GetDeadDuration()
Alive      -> + GetRespawningDuration()          (the wrap point)
```

All four getters are `BlueprintEvent`s defaulting to the corresponding `Default*Duration`
(**1.0 s each**, so the stock cycle is trigger → 1 s → fade → 1 s → dead → 1 s → respawn →
1 s → alive = a **4-second** round trip). `UpdateLocalState()` re-arms
`System::SetTimer(this, n"UpdateLocalState", <remaining>)` for the next boundary, or
`SetTimerForNextTick` when already past it. `NewLocalState()` toggles collision
(`QueryAndPhysics` when not `Dead`, `NoCollision` when `Dead`) on both the mesh and the
mantle box, mirrors it to `SetHiddenInGame`, calls `DirtyHeightMap()` when collision
changed, plays `StateAudioEvents[state]` at the actor location on clients, and on the server
returns to `DORM_DormantAll` + `ForceNetUpdate()` once back to `Alive`. Per-phase visuals
are the four `ClientTick*(PhaseTime)` BP events plus `BP_NewLocalState`.

`ConstructionScript` sets the mesh, offsets it by `-Bounds.Max.Z` so the top face is at the
actor origin, and — when `bGenerateBackupMantleCollision` — builds a box of half-height
**3000.0 / 2 = 1500.0** under the platform so mantling still works while the mesh is hidden.
`__InitDefaults` sets `NetUpdateFrequency = MinNetUpdateFrequency = 0.25` Hz (one update
every 4 s — it only ever needs to send the one float).

`DirtyHeightMap()` calls `ALokiHeightMap::Dirty(worldLocation, boundsExtents)`, which is how
the floor's disappearance propagates into the height map that gems, deathboxes and abyss
checks all consult.

### 12.4 `Content/Train/TrainMovableBaseComponent.as` — moving platforms on a spline

Four classes:

```
UCLASS(SuperIsCodeClass, Abstract, ...) class UTrainAnchor : USceneComponent { }   // bHiddenInGame = true
UCLASS(...) class UBackTrainAnchor  : UTrainAnchor { }
UCLASS(...) class UFrontTrainAnchor : UTrainAnchor { }
UCLASS(SuperIsCodeClass, Abstract, ...) class UTrainMovableBaseComponent : UMovableBaseComponent
{
    float64 InitialOffset;   (Replicated)
    float64 Speed;           (Replicated)   // = 1000.0  (__InitDefaults)
    USplineComponent@ TrackSpline;          (Transient)

    float64 GetLength() const;                                       // Front.X - Back.X (relative)
    bool GetRootTransformAtTime_Implementation(const float64 Timestamp, FTransform&inout OutTransform) const;
    bool GetRootVelocityAtTime_Implementation(const float64 Timestamp, FVector&inout OutVelocity) const;
    private float64 GetDistanceAlongSpline(const float64 Timestamp, const float64 OffsetDistance = 0) const;
    bool GetBackAnchorLocation(FVector&inout OutBackLocation) const;
}
```

This overrides UE's `UMovableBaseComponent` so that riders' movement is resolved
**analytically from a timestamp** rather than from replicated actor transforms — the
standard fix for smooth moving platforms in a networked game.
`GetRootTransformAtTime` samples the spline at the front anchor's distance and again at
`front - GetLength()`, builds `FRotator::MakeFromX(front - back)` so the carriage faces
along the track, and composes with the front anchor's inverse relative transform. Speed
**1000.0 uu/s** replicated, with a replicated `InitialOffset` phase so multiple carriages
can share one spline. Falls back to the owner's actor transform when the spline is missing
or zero-length.

---

## 13. Three decompiler defects found during this work

The first two are in the *lifter*, the third in the control-flow structurer. All three were
found by hand-checking the disassembly against the AngelScript VM, and the first two are
corroborated by the tool's own **independent** stack-depth audit.

Written up with patches at **`tools/asdump/PATCH-lifter-fixes.md`**, and applied in
**`tools/asdump/asdump_patched.py`** — the shared `asdump.py` rebased onto its current
version with the two lifter fixes and nothing else. Fold them into `asdump.py` and delete
the fork. I did not edit the shared tool directly because it was being rewritten
concurrently while I worked (its output was regenerated mid-read, twice).

While I worked, **another party independently fixed the `REFCPY` half of defect 1 upstream**
with the same reasoning. The `COPY` half and defect 2 are still present in
`tools/asdump/asdump.py` as of 19:17.

### 13.1 `COPY` and `REFCPY` print their assignments **backwards** — 235 statements, 42 of 78 modules

`op_COPY` / `op_REFCPY` do `rhs = self.pop(); lhs = self.pop()`. In AngelScript's VM the
**destination is the pointer pushed LAST** (`asBC_REFCPY`: `void **d = *(l_sp); l_sp += PTR;
void *s = *(l_sp);`). Proof from the file itself — `FLokiUsableData`'s default constructor:

```
0000  PshNull
0004  PshVPtr   this
0008  ADDSi     0 134230883      ; .Actor
0010  REFCPY
```

which is unambiguously `this.Actor = nullptr`, and which the shipped tool renders as
`nullptr = this.Actor;`. The tell-tale `nullptr = <expr>;` appears **32 times** in
`out/modules/`; the total number of inverted statements is **235 across 42 modules**
(measured by diffing the shipped output against the fixed run).

Fix (2 lines): swap the two pops in both handlers. `op_COPY` must still push the
destination (AngelScript leaves the lvalue on the stack).

Impact on readability is severe where it matters most — e.g. in
`ULokiInteractionPlayerComponent::ActivateUsable` the shipped output says
`this.SelectedUsable = this.ActiveUsable;` when the code does the opposite, and in
`ULokiNodePathingComponent::OnMoveCompleted` it says
`this.CurrNodeActorList[0] = this.LastPathingActor;` when the code reads the queue head.

### 13.2 Script-declared **structs** are not treated as returning on the stack — parameter names shift by one slot

`returns_on_stack()` contains `if n in cache.script_enums or n in cache.script_classes:
return False`. But 34 of the 110 script-declared types are AngelScript **value types**
(`asOBJ_VALUE`) — every `F…` struct and every script delegate — and a value-type return
takes the hidden return pointer, pushing every declared parameter one slot (2 dwords)
further down.

Discriminator, read straight out of the cache's own `BehaviorRefs` (the 7 slots are
`factory, listFactory, copyfactory, construct, copyconstruct, destruct, copy`):

```
value type  <=>  BehaviorRefs[3] (construct) != 0  AND  BehaviorRefs[0] (factory) == 0
```

Measured: `FActiveUAV`, `FLokiUAVConfig`, `FUAVCharacterGrouping`, `FLokiUsableData`,
`FLokiPodDetachData`, `FMinionWave`, … 34 types classify this way; every `U…`/`A…` script
class has a factory and does not.

**Independent corroboration:** the tool's own dword-depth audit — which shares no code with
the lifter — improves from **1449/1463 (99.04 %) to 1458/1463 (99.66 %)** with this fix
alone (residual unbalanced: `FLaserTraceResult`, `FAimingLaserSettings`,
`UpdateGroundLaserAtLocation`, and `FLokiUsableData`'s two constructors). Concretely,
`ULokiGameStateUAVComponent::ExecuteUAV` goes from

```
v68.Config = SourceLocation;   v68.TeamIndex = arg_m8;   v68.SourceLocation = TeamIndex;
```

to the obviously-correct

```
v68.Config = Config;           v68.TeamIndex = TeamIndex; v68.SourceLocation = SourceLocation;
```

and `ULokiInteractionPlayerComponent::CancelActiveUsable` stops attaching its `ResultType`
parameter to the hidden return temp (which also unlocked the `ELokiUsableInteractionEndResult::*`
member names in §6). Affected here: `ExecuteUAV`, `GetLargestCharacterGrouping`,
`MakeCharacterGroupings`, `CancelActiveUsable`, plus `FLokiUsableData`'s constructors.

### 13.3 The structurer can put a **shared join block inside the `else` arm** — not fixed

Not a lifter bug but a *control-flow reconstruction* bug, and the one most likely to make a
reader draw a wrong conclusion, because the output looks completely reasonable.

When two conditional jumps target the **same** label — the classic "two guard clauses fall
into common code" shape — the structurer sometimes emits an `if / else` whose `else` arm
contains the *join* block, so the code after the guards appears to run only on one path.

Confirmed instance, `ALokiGem::OnComponentBeginOverlap`. Bytecode:

```
010C  CMPIi  v13 -2
0114  JZ            -> L0154        ; TeamIndex == -2   -> join
013C  CMPi   v13 v14
0144  JNZ           -> L0154        ; TeamIndex != mine -> join
014C  JMP           -> L029C        ; else return
L0154: <grant currency, cue, destroy>
```

Rendered as `if (v13 != -2) { if (v13 == v14) return; } else { <grant …> }` — which reads
as "only unowned gems ever pay out", the opposite of the real rule (§3).

**Scale of the risk shape:** a scan for *"a label reached by two or more conditional jumps
and which is not the function's final instruction"* finds it in **46 of 1,463 functions
(3.1 %)**, 17 of them in the 22 modules covered here:
`GetArmoryUniqueEffectTextForItemClass`, `OnAssetLoadComplete`, `CanBuyItem`,
`GetDominationSpawnForPlayer`, `Tick_Implementation` /
`OnSpawnedCharacterChangedCalled` / `UpdateSelectedUsable` / `ProcessActiveInteraction`
(Interaction), `OnComponentBeginOverlap` (Gem), `DropWipedTeamInventories` /
`FindLocationForBox` (TeamElimBox), `MoveToActor` / `FindClosestPathingActor` (NodePathing),
`HandleMostWantedEvent`, and `PulseUAV` / `PulseIndividual` / `IsValidUAVTarget` (UAV).
Not every one of those is mis-rendered — the shape is necessary, not sufficient — but
`PulseIndividual` and `IsValidUAVTarget` are (their `Radius` guard body lands in the `else`
the same way). **Every such function in this document was hand-checked against its
disassembly before anything was written about it.**

Suggested fix for whoever owns the tool: when the two arms of a conditional both reach a
common successor, emit the successor *after* the `if`, not inside either arm. Until then,
that 46-function list is the audit set.

---

## 14. What this means for the project

**1. The project now has in-match economy data where it had none.**
Currencies `"Gold"`, `"Gems"`, `"Shards"` with the exact `ALokiPlayerState` wallet API
(`GetWalletGold/Gems/Shards`, `GrantWalletCurrency`, `ConsumeWalletCurrency`,
`GetTotalEarnedGold`, `GetTotalSpentGold`); prices on `ALokiBaseItem::ShopkeeperGoldPrice`;
a full recipe/tier/shard item tree (`GetTotalRecipeCost`, `GetRecipeCostForInventory`,
`TierNumber`, `MaxTier`, `MaxShardUpgradeTier`, `GetXpToTier`); the **20 % shop discount**
constant and the tag that triggers it; the **once-per-in-game-dawn** shop reroll rule; the
gold-to-deathbox transfer path. If the backend ever needs to serve or validate in-match
economy state, this is the shape of it. Two of the analytics events the dead backend used to
receive (`FAnalyticsItemPurchaseEvent`, `FGameEvent_OnItemPurchase_PlayerState`) are now
fully field-typed.

**2. `ELokiGameFeatureToggle` is fully enumerated — all 151 entries.** This is the single
most reusable artifact from this pass for the project's *existing* blocked work. Sessions
S88–S90 fought the game-feature-toggle carrier (`docs/session-88-toggle-payload-fixed-offset.md`,
`docs/session-89-rpc-route-readiness-shim.md`) sweeping `-toggleseed` values without knowing
what any index meant. The names come from `tools/usmapdump/mappings.usmap`, and the
Angelscript layer supplies one hard anchor: `IsArmoryEnabled()` reads index **106**, and
`ELokiGameFeatureToggle::Armory` is the 107th member. Directly relevant to the tutorial /
match-launch frontier: `TrainingBattleRoyale` (63), `BotsKeepMatchesAlive` (96),
`BRAutomaticRespawns` (91), `BRAutomaticRespawnsSoloMode` (92), `DeathmatchNotMaxLevel` (14),
`DMEconomy` (27), `Missions` (25), `EndOfGameFlowV2` (37), `ValidateConnectionSecret` (36),
`IgnoreClientVersionDangerous` (2), `SkipCosmeticFeatureOwnershipValidation` (69),
`BotSkins` (66), `SimplifiedCosmeticsOnDedicatedServer` (8). The last four are of obvious
interest to a revival project. **Caveat: the pairing of toggle index → behaviour is from the
enum name only, except for `Armory`.**

**3. Four previously-unidentified systems are now identified, from code:**
UAV = a radar/reveal ping (not a vehicle, not a mode);
Most Wanted = a spawnable bounty target with an associated quest, two replicated counters;
Vault = a destructible-door loot container that a UAV can scan;
Domination = a respawn-based team mode whose spawn points carry the literal
`PlayerStartTag == "Domination"` and whose respawn picker is max-min-distance-from-enemies.

**4. Two more shipped cheats for the cheat-surface inventory
(`supervive-cheat-surface-inventory`):** `ALokiDayNightController_AS::AuthCheatNightToDay(float64 Time)`
and `AuthCheatDayToNight(float64 Time)`, both `NetMulticast` UFUNCTIONs. Reachable through
the existing game-thread native-call primitive
(`docs/session-55-native-call-primitive.txt`).

**5. Concrete tunables for a private-server build.** UAV: 11 s / 1 s / 5 s / 0.2 s /
1500 uu / 2000 uu grouping / 20000 uu vault vision / 25 s alert cooldown.
Interaction: 0.2 s cooldown, 0.5 s input buffer. Gems: ×2 multiplier, 400 uu pickup radius,
75 uu rest height. Temporary floors: 4×1.0 s cycle. Trains: 1000 uu/s. Patrol AI: 10°
facing tolerance, 100 uu acceptance radius. Deathbox: 10 placement attempts, 250 uu nav
radius, 1000/5000 projection, −90 uu fallback. Armory: 6 star tiers, XP thresholds 2 and 5.

**6. Three decompiler defects found; two fixed** (§13) — 235 statements across 42 of 78
modules were printed with their assignment direction reversed; value-type-returning script
functions had every parameter name shifted (independent depth audit 99.04 % → **99.66 %**
with the fix in); and the control-flow structurer can hide a shared join block inside an
`else` arm, which silently inverts a guard's meaning in up to **46 functions**. All three
affect every module in the corpus, not just these 22, so **the other agents' outputs are
affected too**. The first two have a ready patch; the third has a 46-function audit list.

---

## 15. What I could not recover — plainly

- **No local variable names, no line numbers, anywhere.** `DeclaredAt == 0` and
  `LineNumbers == []` for all 1,463 functions because the plugin guards both with
  `#if !UE_BUILD_SHIPPING`. Locals are `vN` forever. This is not a tooling limit; the data
  was never written.
- **Blueprint and C++ bodies.** A large fraction of these modules is a *contract*: `NoOp`
  `BlueprintEvent` bodies whose real implementation is in a `.uasset` or in `Loki/Source/`.
  Specifically unrecoverable from script: `RollNewShopItem()` (1 dword — the shop's actual
  loot roll), `AuthSellItem_BP` (sell prices/refund rate), `GetArmoryEvolveChoices` and
  `GetArmoryTrinkets` (both return empty in script — either unimplemented or BP-overridden),
  `AVaultItemSpawner::GetItemsForUAV`/`GetDoor`, every `ClientTick*`/`BP_NewLocalState` on
  `ATemporaryFloor`, `BP_IsCharacterInShadow`, and `ALokiGameGmode::GetGoldDeathboxTransferRatio()`.
- **Per-item numbers.** The economy's *shape* is in script; the *values* — every item's
  `ShopkeeperGoldPrice`, tier costs, recipe graphs, XP-to-tier tables, UAV item configs —
  live in packed data assets. Recovering them is an extractor job
  (`tools/extractor/`), not a script job.
- **What actually calls `ExecuteUAV`.** It is `BlueprintAuthorityOnly` and nothing in the
  78 script modules calls it. The UAV item/ability lives in Blueprint.
- **What spawns a Most Wanted, and what the bounty pays.** The script component only counts.
- **Domination's rules.** Only the respawn picker is script. Capture points, scoring and
  win conditions are elsewhere.
- **`ELokiUsableInteractionRepressBehavior`** — the enum behind
  `GetActiveInteractionRepressBehavior` is not in `mappings.usmap` under any name I tried, so
  its members stay as the integers 0 / 2 / *other* in §6. Their *meanings* are nonetheless
  pinned by the branch that consumes them.
- **`ELokiFuzzyLocationSource` beyond `UAV`.** The enum has exactly `Invalid(0), UAV(1)`, so
  fuzzy locations currently have only one producer.
- **Dead/vestigial declarations, reported not explained:** `ULokiTeamElimBoxComponent`'s
  `MinimumInsuredGoldValue`, `TeamIndexToBoxMap`, `PlayersQueue`, `UpdateTimerHandle` are
  declared and never read by any script function; `ULokiPlayerControllerShopSkylandsComponent::ShopSaleTable`
  likewise; `ULokiInteractionPlayerComponent::OnTest` has an iteration whose body is empty.
  They may be consumed from C++/BP — a script-only view cannot tell.
- **The `TMap<enum, …>` key literals** in `ATemporaryFloor::BeginPlay` still print as
  `true`/`false`/`2`/`3`/`4` rather than `ETemporaryFloorState::…`, because the enum-naming
  pass only fires when a callee's parameter type names the enum, and `TMap::Add`'s key type
  is a template subtype. The values are correct; only the rendering is bare.
- **Residual lifter artifacts I chose to flag rather than hide:** the expired-UAV index
  expression in `Tick_Implementation` (§1.2), the deathbox spawn-location operand (§4), and
  a handful of `return <wrong local>` renderings in multi-exit functions where the
  disassembly is unambiguous. For any function where the exact behaviour is load-bearing,
  the per-function disassembly appendix in the module `.txt` is the ground truth — and
  after §13.3, that is not a formality. I got `ALokiGem::OnComponentBeginOverlap` wrong on
  the first pass by trusting the pseudo-source, and only caught it by hand-decoding the
  jump table. Anything in this document that is stated as a rule was checked that way;
  anything in `out/modules/` that is *not* quoted here has not been.
