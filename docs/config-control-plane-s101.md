# The client config surface as a control plane (S101, 2026-07-26)

Offline/static only. No game launch, no injection. Every claim below is tagged
**[M]** measured (I read the bytes) or **[I]** inferred (reasoning on top of a
measurement). This file exists because the project has twice recorded an
inference as a measurement; the tags are load-bearing.

Read-only sources used:
- `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Config\WindowsClient\{UserSettings,GameUserSettings,Engine,Game}.ini`
- `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Manifest_UFSFiles_Win64.txt`
- `tools/extractor/out/raw/**` (pulled from the pak with the new `rawfile` subcommand)
- `dumps/merged.dump.exe` (unpacked cold image; file-offset == RVA)

---

## 0. Headline — three project beliefs change

### 0.1 FK-13 "every config-side console enable knob is gone" — **FALSE** [M]

`docs/dedicated-server-stub.md:541-556` (S3) concluded *"The Console UObject class
is in the binary (so the runtime supports it) but every config-side enable knob is
gone."* All four knobs are present, and the game **explicitly re-affirms the
console key**:

| Knob | Where | Value |
|---|---|---|
| `ConsoleClassName` | `raw/Engine/Config/BaseEngine.ini:101` | `/Script/Engine.Console` |
| `+ConsoleKeys` | `raw/Engine/Config/BaseInput.ini:16` | `Tilde` |
| `-ConsoleKeys` / `+ConsoleKeys` | `raw/Loki/Config/DefaultInput.ini:368-369` | `Tilde` |
| `[/Script/Engine.Console]`, `[/Script/EngineSettings.ConsoleSettings]` | `raw/Engine/Config/BaseInput.ini:51,54` | present, populated |

`DefaultInput.ini`'s `-ConsoleKeys=Tilde` **followed by** `+ConsoleKeys=Tilde` is
UE's idempotent remove-then-add idiom. Theorycraft did not delete the console key —
they wrote a line whose effect is *"ConsoleKeys is exactly [Tilde]"*. [M]

Why S3 was wrong: it scanned the **packed** binary, where `.text`/`.rdata` are
still encrypted. Re-run against `dumps/merged.dump.exe` (unpacked): `ConsoleKey`
×2 (`0x8197148`, `0x8253e90`), `ConsoleKeys` ×1 (`0x8253e90`), `ConsoleClass` ×2
(`0x7e03770`, `0x7e03780`), `EnableCheats` ×1 (`0x8197908`). [M] This independently
reproduces the ignorance map's own re-test — same counts, same conclusion.

`0x08253d08-0x08253e90` is the `UInputSettings` UHT property-name block, intact and
in stock order: `…DefaultViewportMouseCaptureMode, DefaultViewportMouseLockMode,
FOVScale, DoubleClickTime, ActionMappings, AxisMappings, SpeechMappings,
DefaultPlayerInputClass, DefaultInputComponentClass, DefaultTouchInterface,
ConsoleKeys`. [M]

**What is still NOT established:** whether the console can actually open. The
config layer is clean; the remaining gate is the compile-time `ALLOW_CONSOLE`
flag, which no string scan can decide (the reflection names are emitted whether or
not `UGameViewportClient` constructs the console). [I] That is a live probe — see
§5. Do not upgrade this to "the console works" without it.

### 0.2 FK-2 — the input mechanism is fully documented in a file the game ships [M]

`raw/Loki/Config/DefaultInput.ini` (39,692 B, never previously extracted) has
exactly two sections:

```
[/Script/Engine.PlayerInput]
GamepadAltKey=Gamepad_FaceButton_Top
GamepadShiftKey=Gamepad_LeftShoulder

[/Script/Engine.InputSettings]
… 221 × +ActionMappings=(ActionName=…, bShift, bCtrl, bAlt, bCmd, Key)
…  20 × +AxisMappings=(AxisName=…, Scale, Key)
DefaultPlayerInputClass=/Script/EnhancedInput.EnhancedPlayerInput
DefaultInputComponentClass=/Script/EnhancedInput.EnhancedInputComponent
```

So SUPERVIVE runs the **Enhanced Input classes driven by legacy, name-based
Action/Axis mappings**. Both halves of the four-times-retracted thread were half
right: the Enhanced Input *classes* are real (which is why `UPlayerInput` walks
looked odd), and there are no IMCs to find (which is why every IMC search came up
empty) — because the bindings never went through mapping contexts at all. [M]

Two parallel tables exist, and the user one wins:

| | shipped `DefaultInput.ini` `[/Script/Engine.InputSettings]` | user `UserSettings.ini` `[/Script/Loki.PlayerConfigManager]` |
|---|---|---|
| ActionMappings | 221 | 186 (135 bound / 51 `Key=None`) |
| AxisMappings | 20 | 16 |
| `Toggle Shop` | `P` | `G` |
| `PTTCoreGame` | `Y` | `Z` |
| gamepad duplicates | yes | dropped |

The divergences are the proof of precedence: the shipped file cannot be what the
running client uses. [M→I] `bControllersEnabled=False` in `GameUserSettings.ini`
explains the dropped gamepad rows. [I]

Corroboration for the usmap warning in the task brief: the compiled
`UInputSettings` name block orders `ActionMappings, AxisMappings, SpeechMappings`
exactly as stock UE does, and `PlayerConfigManager` mirrors those three names.
The usmap's one-slot struct-type shift is a usmap bug, not a real layout. [M for
the ordering; I for "therefore PlayerConfigManager uses the stock element types"]

### 0.3 There is no loose ini to edit in the game install [M]

`<install>` has **no** `Loki/Config` and **no** `Engine/Config` directory. All 64
`.ini` files listed in `Manifest_UFSFiles_Win64.txt` live inside the pak/IoStore.
The only writable config surface is `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\`.
Changing a *shipped* default requires an IoStore mod-pak overlay — the same wall
`docs/trackb-assetregistry-route.md` documents. [M]

---

## 1. Inventory — `UserSettings.ini` (22,099 B, rewritten every launch)

Three sections. 202 mapping lines + 14 scalar/struct keys.

### `[/Script/Loki.PlayerConfigManager]`

| Key | Class | Note |
|---|---|---|
| `HasSeenTutorial=True` | **feature gate** | tutorial route |
| `HasPlayedTutorial=True` | **feature gate** | tutorial route |
| `HasSeenOnboardingModal=True` | UI state | |
| `HasSeenRankedPopup=True` | UI state | |
| `bJumpGlideV2Updated=True` | input migration | one-shot rebind migration flag |
| `InputConfigVersion=13` | input migration | bumping the game's own value would force a re-seed from `DefaultInput.ini` [I] |
| 186 × `ActionMappings=` | input binding | 135 bound, 51 `Key=None` |
| 16 × `AxisMappings=` | input binding | movement is here, not in actions |
| `GenericPlayerConfigGroups=` | gameplay pref + **diagnostics** | see below |
| `InGameShopItemDisplayPreferences=()` | UI state | empty |
| `InGameShopItemDisplayPreferencesByHunter=()` | UI state | empty |
| `CustomGamesListDisplayFilterPreferences=()` | UI state | empty |

Movement axes (the reason an action-only search missed WASD):

```
Forward  W:+1  S:-1  Up:+1  Down:-1        Right  D:+1  A:-1  Right:+1  Left:-1
Up       SpaceBar:+1  LeftControl:-1       MouseX/MouseY  AimForwardAlt/AimRightAlt: Gamepad_LeftY/X
```

Cheat/debug actions present in the **user's live** binding table — 38 `Cheat*`
(20 bound), 4 `DevCheat*` (all bound), plus:

```
ShowCheats        = RightAlt          ToggleDebugMenu   = Ctrl+Backslash
DevCheatToggleHUD = Ctrl+F12          ToggleHUD         = Ctrl+H
CheatToggleInfiniteHealthAndMana = O  CheatToggleNoCooldowns = L
CheatRefreshCooldowns = K             CheatRefreshSelf  = P
CheatNextHero = Period                CheatPreviousHero = Comma
CheatTeleportCursor = ThumbMouseButton  CheatToggleInvulnerable = NumPadZero
CheatRespawnSelf = NumPadFive         CheatKillMe = Subtract
CheatStoreLocation = Ctrl+C           CheatReturnToStoredLocation = Ctrl+V
CheatToggleKillDamage = Add           CheatTakeDamage = NumPadEight
CheatMenusPlayRespawnAnim/LockinAnim/FinisherAnim = NumPad1/2/3
CheatMenusNextPage = Add              CheatMenusLastPage = Subtract
DevCheatNoPacketsIn/Out/InOrOut = 8 / 9 / 0
CheatSpawnAlliedDummy, CheatSpawnEnemyDummy, CheatSpawnDesignatedSurvivor = unbound
```

Economy / in-match entry points the project has no owner for:
`Toggle Shop`=G, `OpenGlobalShop`=V, `UseInventory1-6`=1-6, `UseUtilitySlot1/2`=F/G,
`UpgradeEquipment1/2/Boots`=Ctrl+1/2/3, `UpgradeEquipment4/5`=Alt+4/5,
`UpgradeSpell_{Main,Secondary,Ultimate,Dash,DodgeRoll}`=Shift+gamepad. [M]

`GenericPlayerConfigGroups` — 8 groups:
`Aiming`(3 bools) · `Cursor`(Scale=2.0 + 8 bools) · `Learning`(4) ·
`TutorialViewed`(`Controls=True`) · **`Stats`(10 graph toggles)** ·
`OnboardingSwitches`(4) · `HUD`(1).

The `Stats` group is a built-in perf/net overlay: `ClientFPS_GraphEnabled`,
`ServerFPS_GraphEnabled`, `GameThreadMs`, `RenderThreadMs`, `RHIThreadMs`,
`GPUMs`, **`RTTMs`**, **`JitterMs`**, **`InPacketLossPercent`**,
**`OutPacketLossPercent`**. Currently only ClientFPS + ServerFPS are `True`. [M]

### `[/Script/Loki.VivoxRegistry]` — `bVivoxEnabled=True`, `bConfigIsMute=False`
### `[/Script/Loki.MailboxModel]` — `MailboxLastOpenedAt` / `MailboxLastClosedAt` (ISO-8601) — **cached backend state** [M]

---

## 2. Inventory — the three siblings

### `Engine.ini` (148 B) — 100 % project-owned, plus one engine field

```ini
[GameNetDriver StatelessConnectHandlerComponent]
CachedClientID=278                 ; engine-written, persists across launches
[HTTP.Curl]
bVerifyPeer=false                  ; written by launch-redirect.ps1:280
[SSL]
bValidateRootCertificates=false    ; written by launch-redirect.ps1:280
```

`CachedClientID` is UE's stateless-connect handshake identity, cached to disk —
DS-route relevant. [M]

### `Game.ini` (85 B) — `[LokiHardwareSurvey] Version=3, Changelist=156430, Date=2026-06-26T01:22:41.436Z`

`Changelist=156430` is the build changelist. [M]

### `GameUserSettings.ini` (6,505 B) — 7 sections

**Four `[LokiTraining.*]` sections** — `Completed`, `Displayed`, `Closed`,
`NextTime`, each with the **same 22 training-skill keys**. Persistence is declared
by the game itself in `raw/Loki/Config/DefaultGame.ini` `[SectionsToSave]`
(`LokiTraining.Closed/Displayed/Completed/NextTime` + `LokiHardwareSurvey`). [M]

```
TrainingSkillWASD          Completed=2  Displayed=0  NextTime=2024-11-25T20:51:01Z
BP_TrainingSkill_Glide     Completed=3  Displayed=3
BP_Training_Skill_Food     Completed=2  Displayed=1
BP_Training_Skill_LevelAbilityTwice  Completed=0  Displayed=4
BP_Training_Skill_UnlockAllAbility   Completed=0  Displayed=0
TrainingSkill_SpikeIniitial  Completed=1  NextTime=2026-07-24T02:48:19Z  ← touched by this project's own runs
… 22 keys total
```

⚠ **Scope warning.** These key names are the `BP_TrainingSkill_*` /
`BP_Training_Skill_*` family, which `supervive-tutorial-launch-status` records as
the **PRACTICE-mode** system whose `ValidStates` exclude the tutorial — an
explicit DEAD END for the tutorial lesson chain. So this is a live, writable gate
on the *practice-mode nag overlay*, not on `TrainingQuest_Basics_*`. Do not
re-open the dead end on the strength of this file. [M for the names; the dead-end
finding is prior art]

**`[/Script/Loki.LokiGameUserSettings]`** — 84 keys. `Version=5`. Notables:

| Key | Value | Class |
|---|---|---|
| `bControllersEnabled` | `False` | input |
| `DashInputMode` / `EXDashInputMode` | `WASDEnhanceWithCursor` | input |
| `bCursorCharacterAimV2` | `False` | input |
| `bInvertViewPitch`, `MouseSensitivity`, `MouseSensitivityADS` | | input |
| `PlayerName` | `DEFAULT CAT` | **identity, cached client-side** |
| `MessageOfTheDayLastSeen` | *(empty)* | **cached backend state** |
| `IncompatibleSoftwareLastSeen` | *(empty)* | cached (Nahimic/Malwarebytes dialog) |
| `VoiceSettingsConfirmedV2` | `True` | UI state |
| `bRecommendedItemsEnabled` | `True` | gameplay pref |
| `bHideNonPartyPlayerNamesEnabled` | `False` | gameplay pref |
| `DefaultFieldOfView` | `18` | camera |
| `CameraPreset` / `CameraV2Preset` | `StandardDynamicCamera` / `DynamicStabilized` | camera |
| `ShowFPS` | `False` | diagnostics |
| `FrameRateGame/Menu/Background` | `240 / 144 / 30` | perf |
| `bLumenEnabled` | `True` | render |
| `VolumeSettings` | struct, `Version=1` | audio |

Also `[ScalabilityGroups]` (9 × `sg.*=3`) and
`[/Script/Engine.GameUserSettings] bUseDesiredScreenHeight=False`. [M]

---

## 3. The shipped defaults — what actually matters (first read, 2026-07-26)

`DefaultEngine.ini` (116,954 B, 60 sections) / `DefaultGame.ini` (27,105 B, 26
sections). The 2026-06-27 extraction is byte-identical to a fresh `rawfile` pull
(`diff` clean), so it was complete — just unread. [M]

**Also newly extracted and previously unseen:** `DefaultInput.ini` (39,692 B),
`DefaultGameUserSettings.ini`, `DefaultGameplayTags.ini` (744 KB),
`DefaultDeviceProfiles.ini` (1.53 MB), `DefaultHardware.ini`, `DefaultNiagara.ini`,
`BlackBox.ini`, `Windows/WindowsEngine.ini`, plus `Engine/Config/BaseEngine.ini`
and `BaseInput.ini`. All under `tools/extractor/out/raw/`. [M]

### `[/Script/EngineSettings.GameMapsSettings]` — 34 `+GameModeClassAliases`

```
GameDefaultMap   = /Game/Loki/Maps/LVL_Login.LVL_Login
ServerDefaultMap = /Game/Loki/Maps/LVL_ServerStandby.LVL_ServerStandby
TransitionMap    = None
GameInstanceClass= /Game/Loki/Core/GameModes/BP_LokiGameInstance.BP_LokiGameInstance_C
GlobalDefaultGameMode = /Script/Engine.GameModeBase
```

Aliases (usable as `?game=<Alias>` in a travel URL) [M for the list; [I] for
"?game= resolves them" — that is stock UE `GameModeClassAliases` semantics]:

`TutorialGameMode` → `BP_LokiGameMode_Tutorial_C` · `TutorialMode` →
`BP_GameMode_BasicTraining_C` · `TrainingMode` → `BP_PracticeGameMode_Training_C` ·
`PracticeMode` · `DevMode` · `ArtPreviewMode` · `PlaytestGameMode` ·
`SkylandsBRGameMode` / `_Duos` / `_Solos` / `_Bots` / `_Breach` / `_OldBR` ·
`FastProgressionBreachBRGameMode` · `BRQuickGameMode` · `TurboBR` · `LastManGameMode` ·
`FreeForAll` / `FreeForAllOldBR` · `Holdout` · `Battlefield` · `Domination` ·
`Tournament` · `Soccervive` · `SiegeBeast` · `PrismaBank` / `PrismaBag` ·
`Barracuda` / `Swordfish`.

`TutorialGameMode` is exactly the class the force-open route already drives. [M]

### `[/Script/Engine.Engine]`
`GameEngine=/Script/Loki.LokiGameEngine` · `GameViewportClientClassName=/Script/Loki.LokiGameViewportClient`
· `AssetManagerClassName=/Script/Loki.LokiAssetManager` ·
`GameUserSettingsClassName=/Script/Loki.LokiGameUserSettings` · `MaximumLoopIterationCount=1500000`.
Note: **no `ConsoleClassName` override**, so `BaseEngine.ini`'s
`/Script/Engine.Console` stands. [M]

### `[Core.Log]` — 15 categories, **not one is Verbose**
```
LogNet=Warning   LogAccelByte=Warning   LogAccelByteLobby=Warning   LogOnline=Warning
LogLokiGameplaySpellReplication=Log   LogLokiGliding=Log   LogLokiGameMode=Log
LogLokiFogOfWarMeshComponents=Warning  LogLokiVision=Warning  LogVisionGranter=Log
LogNavigationDirtyArea=Log  LogNgsClientMonitor=Log  LogNgsServerMonitor=Log
LogShaderPipelineCacheTools=Error   DFLLog=Fatal
```
`DFLLog=Fatal` silences the `DebugFunctionLibrary` plugin, which also ships a
runtime settings section (`[/Script/DebugFunctionLibrary.DebugFunctionLibrarySettings]`
with `bLogErrorWithNoDebugProperties`, `bAutomaticallyAddDebugPropertiesToBlueprints`). [M]

### AccelByte — 13 environment blocks
Base + `DevelopmentNX`, `TCNexonDevelopment`, `TCProduction`, `TCProductionNX`,
`TCPreProd`, `TCPreProdNX`, `Partner`, `NexonDevelopment`, `NexonStaging`,
`NexonPreProd`, `NexonProduction`.
`ClientId=ba8fb59a34bb481abca08c46ba488025` (identical in every block),
`ClientSecret=` empty, `Namespace=loki`, `PublisherNamespace=theorycraft`,
`RedirectURI="http://127.0.0.1"`.
`TCProduction` base = `https://accounts.projectloki.theorycraftgames.com`.

**`QosManagerServerUrl=` is EMPTY in all 13 blocks** — the client was never
configured to do QoS/latency probing, so the backend never needs to serve it. [M]
Also empty everywhere: `NonApiBaseUrl`, `CloudSaveServerUrl`,
`AchievementServerUrl`, `SessionBrowserServerUrl`, `AppId`.

### Networking (DS-route relevant)
```
[/Script/OnlineSubsystemUtils.IpNetDriver]
ReplicationDriverClassName=/Script/Loki.LokiReplicationGraph
InitialConnectTimeout=30.0   ConnectionTimeout=15.0
TimeoutMultiplierForUnoptimizedBuilds=6
[/Script/Engine.Player]        ConfiguredInternetSpeed=500000  ConfiguredLanSpeed=500000
[/Script/Engine.GameSession]   MaxPlayers=64
[/Script/Engine.GameNetworkManager]  ClientNetSendMoveDeltaTime=0.0333 …
[ConsoleVariables]  p.NetPackedMovementMaxBits=4800  net.AllowAsyncLoading=1
                    net.MaxRPCPerNetUpdate=10  net.DelayUnmappedRPCs=1
[SystemSettings]    net.IpConnectionUseSendTasks=1
```
`ConnectionTimeout=15.0` is the number S81's 20 s game-thread block blew through. [M]

### `[OnlineSubsystemSteam]`
`SteamDevAppId=1283700` · `bRelaunchInSteam=false` · `bUseSteamNetworking=false` ·
`bAllowP2PPacketRelay=false` · `bInitServerOnClient=false`. [M]

### Telemetry endpoints still baked in (all dead; the client may still dial them)
Sentry `Dsn="https://149a7ac2a7914150b87ce714fd4d6444@o566896.ingest.sentry.io/5710262"`
(with `Debug=True`, `InitAutomatically=True`) · BlackBox SDK `APIKey`/`Namespace=theorycraft`
· `MarketingAnalyticsURL="https://sdk.gamerebellion.com/api/attributions/conversion/"`
· ClientConfigService: 9 named env URLs under `*.theorycraftgames.com` / `*.nexon.com`. [M]

### Misc worth knowing
`[Staging] +AllowedConfigFiles=Loki/Config/DefaultActorPoolManager.ini` and
`DefaultNiagara.ini` (only the latter is actually in the pak — `DefaultActorPoolManager.ini`
is listed as allowed but **absent** from the 64-file manifest) [M] ·
`ShippingPatchVersion=(VersionName="2.4")` · `MoviePlayer` 3 startup movies,
`bMoviesAreSkippable=True` · `[Kismet] ScriptStackOnWarnings=True` ·
`ValidateLinkedLibraries` warns on Nahimic + Malwarebytes · `MaxPlayers=64` ·
`[MemReportFullCommands] +Cmd=obj list class=BlueprintGeneratedClass -alphasort`.

---

## 4. The control question

### 4.1 Two mechanisms

**(A) `-ini:<BaseName>:[Section]:Key=Value`** — `launch-redirect.ps1:297-311` already
uses it for `Engine` and `Game`, and the entire login redirect depends on it, so the
mechanism is proven working in this build. [M, by 101 sessions of use]

The engine's canonical config base-name table is at RVA `0x076bc130` in
`dumps/merged.dump.exe` [M]:

```
Engine   Game   Input   DeviceProfiles   GameUserSettings
Scalability   RuntimeOptions   InstallBundle   Hardware   GameplayTags
```

- **`Input` IS in the table** → `-ini:Input:[/Script/Engine.InputSettings]:…` is a
  candidate for `ConsoleKeys` and for rebinding. [I]
- **`UserSettings` is NOT in the table** → the input *bindings* the client actually
  uses probably cannot be reached this way. [I — needs the A/B in §5]

Known timing caveat, already paid for once: `-ini:` lands too late for very-early
init. `launch-redirect.ps1:270-272` records that `FCurlHttpManager::InitCurl` reads
`bVerifyPeer` before the override applies, which is why that one setting had to move
to the file layer. Anything read during early engine init needs mechanism (B). [M]

**(B) Write the user file, then set it read-only.** Proven at
`launch-redirect.ps1:273-287`: the launcher appends `[HTTP.Curl]`/`[SSL]` to
`Saved\Config\WindowsClient\Engine.ini` and then sets `IsReadOnly = $true`, with the
comment *"Make read-only so the game can't strip our section before curl init reads
it."* So the game **does** rewrite these files and **does** drop unknown sections —
and read-only defeats it. That is the general recipe for every user-layer lever
below. [M]

### 4.2 Precedence (highest wins)
`-ini:` command line → `Saved/Config/WindowsClient/<X>.ini` → `Loki/Config/Default<X>.ini`
→ `Engine/Config/Base<X>.ini`. [I — standard UE, consistent with every observation here]

### 4.3 Is anything here cheaper than a shim the project already runs?
Honest answer: **no, not for the shipped shims.** Roster/store/cosmetics, missions,
passes, and loadout all hinge on in-memory object state (`CatMgr+0x354`, VM map keys,
`ProgMgr.MissionsModel`) with no config key behind them. Nothing in §1-3 touches
them. The config plane's value is **new capability the project never had** (§5), not
replacement of existing shims.

---

## 5. Levers, ranked

| # | Lever | Where | Cost | Value |
|---|---|---|---|---|
| 1 | **Press `~`** — every console config knob is shipped and set | free | trivial | If `ALLOW_CONSOLE` is on, `open 127.0.0.1:7777`, `?game=TutorialGameMode`, cheats, `ShowDebug` — the whole S3 wishlist. Binary outcome. |
| 2 | **Press `RightAlt` (`ShowCheats`) / `Ctrl+\` (`ToggleDebugMenu`) / `Ctrl+F12`** in a match | user `UserSettings.ini`, already bound | trivial | A cheat/debug UI reachable with **no shim and no console**. These are live user bindings, not stripped names. |
| 3 | **`Stats` perf/net overlay** → set `RTTMs_GraphEnabled`, `JitterMs_GraphEnabled`, `In/OutPacketLossPercent_GraphEnabled` = `True` in `GenericPlayerConfigGroups` | user file + read-only | low | Live RTT / jitter / packet-loss graphs. Directly aimed at the S81 disconnect work, which currently has no in-client instrumentation. |
| 4 | **`-ini:Input:[/Script/Engine.InputSettings]:ConsoleKeys=…`** | command line | low | Confirms `Input` reachability *and* re-keys the console off `~` if `~` is swallowed by IME/overlay. Also the diagnostic for lever 1's failure mode. |
| 5 | **Log verbosity** — `-ini:Engine:[Core.Log]:LogNet=Verbose` or `-LogCmds="LogNet Verbose"` (`-LogCmds=` string measured at `0x76b25e0`) | command line | low | FK-11 says Verbose is not compiled out. All 15 shipped categories sit at Warning/Log — the project has been reading a deliberately quiet log for 101 sessions. |
| 6 | **`+GameModeClassAliases`** — 34 short names incl. `TutorialGameMode`, `PracticeMode`, `FreeForAll`, `Domination`, `Holdout` | naming, not a write | none | Short `?game=` tokens for the force-open / travel route; also a complete inventory of shipped modes. |
| 7 | `[LokiTraining.*]` in `GameUserSettings.ini` — 22 skills × Completed/Displayed/Closed/NextTime | user file + read-only | low | Re-arms the **practice-mode** coaching overlay. ⚠ explicitly *not* the tutorial lesson chain (prior art: dead end). |
| 8 | `HasSeenTutorial` / `HasPlayedTutorial` / `HasSeenOnboardingModal` / `HasSeenRankedPopup` / `TutorialViewed.Controls` | user file + read-only | low | First-run flow gates. Cheap way to see whether the client has an onboarding path we've never rendered. |
| 9 | `InputConfigVersion=13` — lower it | user file + read-only | low | Should force the client to re-seed bindings from `DefaultInput.ini`. Best available handle on the binding pipeline without a shim. [I] |
| 10 | `MessageOfTheDayLastSeen` (empty) | user file | low | Cached-backend-state dedupe key. If the backend ever serves an MOTD, this is what suppresses it. |
| 11 | `bControllersEnabled`, `DashInputMode`/`EXDashInputMode`, `bCursorCharacterAimV2`, `bInvertViewPitch` | user file + read-only | low | Input-behaviour knobs adjacent to the WASD work. |
| 12 | `CachedClientID=278` in `Engine.ini` | user file | low | Stateless-connect handshake identity, persisted. Worth knowing for the DS route. |

**Dead ends, recorded so nobody re-walks them:** no loose ini in the install (§0.3);
`QosManagerServerUrl` empty in all 13 AccelByte blocks so QoS never needs serving;
`DefaultActorPoolManager.ini` is `[Staging]`-allowed but not actually shipped.
★ **S130 (2026-08-20) turned that dead end into a confirmed one from the other side:** the actor-pool feature is gated by `ALokiGameState::bSupportsActorPoolPriming` (a `bool` at `+0x898`) whose `CPF_Config` bit is **clear**, and **0 of that class's 155 reflected properties carry `CPF_Config`** — so even a shipped `DefaultActorPoolManager.ini` would have had nothing to bind. ⇒ **there is no ini route to actor pooling, measured two independent ways.** `docs/s130-actor-pool-gate-settled.md` §5.

---

## 6. Live probes required (nothing here is decidable offline)

Each is single-variable, per the project's probe convention.

| # | Question | Exact probe | Expected / decisive signal |
|---|---|---|---|
| P1 | Is `ALLOW_CONSOLE` compiled in? | Launch normally, press `~` at the menu and again in a match. | Console overlay draws → FK-13 fully inverted. Nothing → the gate is the compile flag, config is exonerated. |
| P2 | Same, without relying on the keypress | RPM: read `GEngine->GameViewport->ViewportConsole` (`UGameViewportClient` UPROPERTY, name string at `0x807df80`) and check for non-null; also look up `/Script/Engine.Console` in GUObjectArray via `tools/re/find_uclass.py`. | Non-null → console exists, key handling is the only issue. Null → `ALLOW_CONSOLE=0`, close it for good. |
| P3 | Does `ShowCheats` do anything? | In a force-open tutorial match, press `RightAlt`, then `Ctrl+\`, then `Ctrl+F12`. Screenshot each. | Any overlay → a shim-free debug surface. |
| P4 | Does `-ini:` reach `Input`? | `-ini:Input:[/Script/Engine.InputSettings]:ConsoleKeys=F8` then press `F8`. | F8 opens (or `~` stops opening) → `Input` reachable. |
| P5 | Does `-ini:` reach `UserSettings`? | `-ini:UserSettings:[/Script/Loki.PlayerConfigManager]:HasSeenTutorial=False` then RPM-read the flag on `PlayerConfigManager`. | Flag reads False → the whole 186-mapping table is command-line addressable. |
| P6 | Is Verbose really not compiled out? (FK-11) | `-LogCmds="LogNet Verbose"`, single variable, then grep `Loki.log` for `LogNet: Verbose:`. | Any Verbose line → confirmed, and every future net investigation gets much better data. |
| P7 | Do the `Stats` graphs render? | Set the four net toggles True in `GenericPlayerConfigGroups`, mark the file read-only, launch. | Graphs appear → free live netcode instrumentation. |
| P8 | Does lowering `InputConfigVersion` re-seed bindings? | Set `InputConfigVersion=1`, read-only, launch, then diff the rewritten `UserSettings.ini`. | 186 → 221 mappings, `Toggle Shop` back to `P` → the re-seed path is confirmed and controllable. |

⚠ Every user-file probe must set the file **read-only afterwards** or the game
strips it on write — the lesson `launch-redirect.ps1:283-284` already paid for.
⚠ `UserSettings.ini` is under a read-only constraint for this session; P5/P7/P8
need the user's go-ahead to write, and a backup copy first.

---

## 7. Tooling added

`tools/extractor/extractor/Program.cs` — `rawfile <pathNeedle>…` (added this
session by a sibling agent; extended use here). Copies non-`.uasset` files out of
the pak byte-for-byte to `tools/extractor/out/raw/<pak-relative-path>`. Every
prior subcommand went through the UAsset/usmap path, which is why 64 shipped
`.ini` files had gone unread for 101 sessions.

```
dotnet run -c Release -- rawfile "Loki/Config/" "Engine/Config/BaseInput.ini"
```
