# FK-2 SETTLED — the input path

**Session:** S104 · **Date:** 2026-07-26 · **Status of this document:** definitive; supersedes
`docs/session-79-moonshot-plan.md:688-690` and every S80 entry about Enhanced Input.
**Companion artifact:** `docs/input-map.csv` (202 rows — all 186 ActionMappings + 16 AxisMappings).

> **Read this first if you are about to touch input.** The four-times-retracted thread is closed.
> Do not re-open the Enhanced Input / IMC hypothesis. Do not re-run a `UPlayerInput` property walk.
> The specific things that are *still* unknown are in §8, and they are narrow.

---

## 1. Verdict

### 1.1 The three questions, answered separately

FK-2 bundled three questions. They have three different answers and conflating them is what kept
the thread alive for four retractions.

| # | Question | Verdict | Confidence |
|---|---|---|---|
| **A** | Is FK-2's *belief* true — "no legacy input path exists, therefore SUPERVIVE must drive Enhanced Input from IMCs"? | **DEAD. Retracted in full.** | **CERTAIN** — three independent measurements, one of them a direct read of the engine source the claim was about |
| **B** | Does the legacy mapping table *drive* input in the **retail** game? | **PROBABLE — not proven.** The table is proven to EXIST, in two layers, and the whole legacy consumer API is proven COMPILED IN. **Zero runtime dispatch measurements exist.** | **HIGH** (see §1.3 for the load-bearing argument, and why it is still an inference) |
| **C** | Does it drive input in **our force-open tutorial state**? | **UNSETTLED — and never actually asked.** The project's only measurement here says it does not, and that measurement is confounded and taken with an uncalibrated instrument. | **UNKNOWN** |

**The one-line honest statement:**
> The mapping table is proven to EXIST and the legacy consumer API is proven PRESENT — but the table
> is **not yet proven to DRIVE live input**, in retail or in force-open. §5 Step 3 is the probe that
> converts B from PROBABLE to MEASURED; §5 Step 4 is the one that answers C.

### 1.2 What FK-2 got wrong, precisely

The belief (`docs/session-79-moonshot-plan.md:688-690`, commit `88a89b9`, 2026-07-16):

> *"legacy `UPlayerInput::ActionMappings`/`AxisMappings` are **ABSENT from the class entirely** (UE5
> moved them behind `WITH_EDITORONLY_DATA` → stripped from shipping) ⇒ there is no legacy input path,
> so SUPERVIVE MUST drive Enhanced Input from IMCs — which means the IMC assets DO exist somewhere
> and the searches above simply failed to find them."*

It has three parts. One is right, two are wrong, and the wrong ones were never checked.

1. **The OBSERVATION is CORRECT** and doubly confirmed. `UPlayerInput` in this build reflects exactly
   6 UPROPERTYs and none is a mapping array. Confirmed by the S80i live RPM walk *and*, independently,
   by the project's own offline usmap: `schema.txt:41089`
   → `PlayerInput : UClass:Object (6 props)` = `DebugExecBindings`, `InvertedAxis`,
   `GamepadAltKey`, `GamepadCtrlKey`, `GamepadShiftKey`, `GamepadCmdKey`.
   **Nobody mis-measured.** Two instruments agreed.

2. **The EXPLANATION is FALSE — and it is false about *stock UE*, not just about SUPERVIVE.**
   In UE 5.4, `UPlayerInput::AxisConfig` / `ActionMappings` / `AxisMappings` carry **no `UPROPERTY`
   macro at all**. They are plain public C++ members, present in every build including Shipping.
   `WITH_EDITORONLY_DATA` does not appear anywhere in the file.
   *Re-verified this session by direct read of the local engine tree:*
   `H:/Unreal Engine/UE_5.4/Engine/Source/Runtime/Engine/Classes/GameFramework/PlayerInput.h:439-446`;
   `grep -c UPROPERTY` over the class body (from L408) = **2** (`DebugExecBindings` L436,
   `InvertedAxis` L449); `grep -c WITH_EDITORONLY_DATA` over the whole file = **0**.
   > The inference chain was rotten at its **first link**, before the RPM walk was ever involved.
   > "UE5 moved them behind `WITH_EDITORONLY_DATA`" was never true of any UE version, so
   > "therefore SUPERVIVE MUST use IMCs" never followed. That is why four sessions of IMC hunting
   > found nothing — there was nothing to find.

3. **The CONCLUSION is FALSE and INVERTED.** SUPERVIVE runs legacy name-based Action/Axis mappings.
   They ship in the pak (221 + 20), they are mirrored per-player to disk (186 + 16), and the game
   *forked the engine's legacy chord evaluator* to make its own shipped gamepad chords work (§1.3).

### 1.3 Why B is PROBABLE and not merely "the data exists"

Three measured facts, plus one argument that carries the weight.

**(a) The data exists in two layers — measured, re-counted this session.**
- Shipped: `tools/extractor/out/raw/Loki/Config/DefaultInput.ini`, 39,692 B, exactly two sections
  (`[/Script/Engine.PlayerInput]`, `[/Script/Engine.InputSettings]`),
  **221 `+ActionMappings=`** and **20 `+AxisMappings=`** in stock legacy struct form.
- Per-player: `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\UserSettings.ini`, 22,099 B,
  section `[/Script/Loki.PlayerConfigManager]`, **186 `ActionMappings=`**, **16 `AxisMappings=`**,
  **0 `SpeechMappings=`**, `InputConfigVersion=13`, 51 actions + 2 axes unbound (`Key=None`).

**(b) Zero Enhanced Input assets exist — by complete enumeration, not failed search.**
`grep -cE "/IMC_|/IA_" tools/extractor/out/allfiles.txt` → **0** over 107,123 shipped file paths.
The only `EnhancedInput` hits are three engine-plugin scaffolding files (`.uplugin`, two `.ini`).
*Caveat, stated honestly:* IMCs can be built at runtime with `NewObject` and no asset, so this is
necessary but not sufficient. The falsifier that closes it is S80g's live measurement of empty
`AppliedInputContexts` on all three `EnhancedPlayerInput` objects — which was taken at the **menu**,
so it is state-limited.

**(c) The legacy consumer API is compiled in and reflected.**
The Angelscript bind table exposes **13 methods whose target class is `UPlayerInput`** —
`AddActionMapping`, `AddAxisMapping`, `RemoveActionMapping`, `RemoveAxisMapping`,
`ForceRebuildingKeyMaps`, `GetKeysForAction`, `GetKeysForAxis`, `GetEngineDefinedActionMappings`,
`GetEngineDefinedAxisMappings`, `InvertAxis`, `Get/SetMouseSensitivity*`
(`tools/asdump/out/binds_members.csv:37658-37670`, all `static_in_unreal=1`, `as_class_name=UPlayerInput`).
The mixin library itself is a **real reflected UClass in the shipping usmap**:
`schema.txt:41096` `PlayerInputScriptMixinLibrary : UClass:Object (0 props)`; sibling
`InputComponentScriptMixinLibrary` at `schema.txt:20841` binds `BindAction`/`BindAxis`/`BindKey`/`BindChord`.
`UInputComponent` is stock and still carries its legacy cache (`schema.txt:20839-20840`,
1 UPROPERTY = `CachedKeyToActionInfo`, whose struct holds a `TWeakObjectPtr<UPlayerInput>`).

**(d) — THE LOAD-BEARING ARGUMENT — SUPERVIVE forked the *legacy chord evaluator*.**
`Loki/Config/DefaultInput.ini` ships **11 gameplay ActionMappings with `bShift=True` *and* a Gamepad
key** (verified this session by direct grep of the shipped ini):

```
Ability4                Shift+Gamepad_RightShoulder        UpgradeSpell_Dash       Shift+Gamepad_DPad_Left
CancelTargetAlt         Shift+Gamepad_FaceButton_Right     UpgradeSpell_DodgeRoll  Shift+Gamepad_DPad_Right
ConfirmTargetAlt        Shift+Gamepad_RightTrigger         UpgradeSpell_Main       Shift+Gamepad_FaceButton_Top
OpenGlobalShop          Shift+Gamepad_Special_Right        UpgradeSpell_Secondary  Shift+Gamepad_DPad_Up
UseUtilitySlot1         Shift+Gamepad_LeftTrigger          UpgradeSpell_Ultimate   Shift+Gamepad_DPad_Down
UseUtilitySlot2         Shift+Gamepad_RightTrigger
```

`bShift` is a field of the **legacy** `FInputActionKeyMapping`. It is evaluated in exactly one place
in the engine: `UPlayerInput::GetChordsForKeyMapping` (`PlayerInput.cpp:884-888`), which sits *inside*
legacy `ProcessInputStack` dispatch. Stock `UPlayerInput::IsShiftPressed()` (`PlayerInput.cpp:2115-2118`)
reads **only** `EKeys::LeftShift || EKeys::RightShift` — so on a gamepad **all 11 of those mappings are
dead in stock UE**. SUPERVIVE added `GamepadShiftKey` / `GamepadAltKey` / `GamepadCtrlKey` /
`GamepadCmdKey` as `UPROPERTY(config) FKey` on `UPlayerInput` (present at `schema.txt:41092-41095`;
**0 occurrences in the entire UE 5.4 source tree**, re-verified by grep this session) and ships
`GamepadShiftKey=Gamepad_LeftShoulder` in `[/Script/Engine.PlayerInput]`.

> **You do not fork the modifier evaluator of a dispatch path you don't run.**

Corroborating from the live user table: the five `UpgradeSpell_*` verbs are bound **only** to
Shift+Gamepad chords, and `SpectateTeam11-20` use Shift+digit keyboard chords — both families depend
on the same legacy chord machinery.

This is the strongest argument available, and it is still an **INFERENCE**. It is not a measurement
of dispatch.

### 1.4 The single most dangerous remaining assumption

> **That evidence about the *retail* game's input path is evidence about the *force-open* state's
> input path.**

Everything in §1.3 is about a game that shipped and unquestionably had working input. The project
does not run that game. It runs a force-opened tutorial with no deploy, a NULL GAS carrier, and a
hand-built possession. In *that* state the project's own instrument recorded zero.

If this document's retraction were written as *"the stock input path is alive, retire the puppet"*,
the next session would delete a working workaround, find WASD dead, and re-open the input thread for
a fifth time — while the actual blocker (GAS / possession / deploy) sat untouched. **It is not
written that way, and it must not be summarised that way.**

Runner-up hazard: every un-reflected offset and function body in the model below is *stock-source
reasoning applied to a class this same investigation proved is forked* (3 UPROPERTY markers removed,
4 `Gamepad*Key` properties added). That produces confident, specific, **wrong** offsets — FK-2's
failure mode wearing a different hat. Never take a `UPlayerInput` offset from UE 5.4 source; derive
it from disassembly or from an exact-count match (§5 Step 2).

---

## 2. The corrected mechanism, hop by hop

Every hop is marked. `MEASURED` = an instrument produced the number. `INFERRED` = follows from stock
UE source plus something measured here. `UNKNOWN` = nobody has looked.

```
 [H1] OS key  ──▶ [H2] UPlayerInput  ──▶ [H3] key maps  ──▶ [H5] UInputComponent  ──▶ [H6] handler
                        ▲                     ▲
                        │                     │
              [H4] ULokiPlayerConfigManager (186 + 16, from UserSettings.ini)   ◀── THE ONE UNMEASURED HOP
```

### H1 — OS key/mouse → `UPlayerInput::InputKey` → `KeyStateMap`
`INFERRED` (stock UE flow). Nothing in this build contradicts it; nothing here measured it.
Consequence worth recording: nothing in that chain distinguishes a `SendInput`-injected key from a
physical one, which is why synthetic input buys **zero** capability (§5, dropped items).

### H2 — `APlayerController::TickPlayerInput` → `PlayerInput->ProcessInputStack(...)`
`MEASURED` (which class) + `MEASURED` (that Enhanced delegates to legacy).

- The PlayerInput object's class comes from `UInputSettings::DefaultPlayerInputClass`, and the shipped
  ini pins it: `DefaultInput.ini:365-366`
  → `DefaultPlayerInputClass=/Script/EnhancedInput.EnhancedPlayerInput`,
  `DefaultInputComponentClass=/Script/EnhancedInput.EnhancedInputComponent`.
  `schema.txt:15536` `EnhancedPlayerInput : UClass:PlayerInput (7 props)`; **no `ULokiPlayerInput`
  exists** and no other `UClass:PlayerInput` subclass appears in the file.
- **`UEnhancedPlayerInput::ProcessInputStack` is a one-line pass-through.** Verified this session by
  direct read: `H:/Unreal Engine/UE_5.4/Engine/Plugins/EnhancedInput/Source/EnhancedInput/Private/EnhancedPlayerInput.cpp:752-755` —
  the entire body is `Super::ProcessInputStack(InputComponentStack, DeltaTime, bGamePaused);`.
  > This closes probe 1's open question **offline**. It was filed as needing a live vtable dump. It did not.
- The Enhanced half is **INERT**: `AppliedInputContexts` empty on all 3 objects,
  `EnhancedActionMappings` empty, 0 IMC assets, 0/14,921 BP functions call `AddMappingContext`,
  `UEnhancedInputDeveloperSettings.DefaultMappingContexts` Num=0, and `AddMappingContext`'s page has
  never demand-decrypted (S80g/h/o — commits `a07ea24`, `848a077`, `c161552`). `MEASURED`, at the menu.

> **This is the sentence that reconciles all four retractions:**
> **SUPERVIVE uses Enhanced Input CLASSES with 100% LEGACY DATA.** Seeing the class name
> `EnhancedPlayerInput` is not evidence of Enhanced Input usage. That trap cost four retractions.

### H3 — Key-map build: instance arrays → `ActionKeyMap` / `AxisKeyMap`
`INFERRED` for this build; `MEASURED` from stock source that the build reads **only** the instance
arrays. Two facts here matter and one of them **corrects a claim in the probe packet**.

- `UPlayerInput::PostInitProperties()` → `ForceRebuildingKeyMaps(true)` (`PlayerInput.cpp:107-111`).
  With `bRestoreDefaults=true` (`:770-788`) it copies `UInputSettings`' `AxisConfig` /
  `AxisMappings` / `ActionMappings` **into the instance's own arrays**, then appends SpeechMappings
  as synthesised action mappings. **So every `UPlayerInput` instance is seeded from `UInputSettings`
  at construction.**
- `ConditionalBuildKeyMappings_Internal` (`:811-874`) builds `ActionKeyMap` / `AxisKeyMap` from
  **`ActionMappings` + `EngineDefinedActionMappings`** and **`AxisMappings` + `EngineDefinedAxisMappings`**
  — the *instance* arrays only. It never re-reads `UInputSettings`.

> ⚠ **CORRECTION to the probe packet.** Probe 1's H3 stated that `ForceRebuildingKeyMaps` rebuilds
> "from `UInputSettings`' mappings **PLUS** `UPlayerInput`'s own". That is **FALSE**. The consequence
> is operational: **writing `UInputSettings::ActionMappings` at runtime does nothing** until
> `ForceRebuildingKeyMaps(true)` runs on each `UPlayerInput` instance. This kills the "global sink"
> half of probe 1's H4 as a *live write* target.

### H4 — ★ THE ONE UNMEASURED HOP ★ — how the user's 186/16 reach the key maps
`UNKNOWN`.

`ULokiPlayerConfigManager` (`/Script/Loki.PlayerConfigManager`, `UCLASS(config=UserSettings)`) holds
the user's table. Reflected, per `schema.txt:40990` (17 props):
`InputConfigVersion` (Int64), `ActionMappings`, `AxisMappings`, `SpeechMappings`,
`GenericPlayerConfigGroups`, `CachedVolumeLevels`, `HasSeenTutorial`/`HasPlayedTutorial`/
`HasSeenOnboardingModal`/`HasSeenRankedPopup`, `bJumpGlideV2Updated`, plus the three delegates
`OnActionBindingUpdated` / `OnActionBindingsReset` / `OnDoubleBindingCleared`.
Offsets from the shipping reflection statics (`dumps/merged.dump.exe`, FClassParams @RVA 0x8ACE3D0,
`ClassConfigNameUTF8 → "UserSettings"`): `InputConfigVersion @0x1B0`, `ActionMappings @0x1B8`,
`AxisMappings @0x1C8`, `SpeechMappings @0x1D8`, `GenericPlayerConfigGroups @0x1E8`, all `CPF_Config`.
*(These offsets are from the probe packet and are **not** independently re-verified here — §5 Step 2
validates them by exact-count match before anything depends on them.)*

Something must move that table into the key maps. Three live candidates, all consistent with
everything measured:

| | Candidate | Test |
|---|---|---|
| (a) | Push into `UPlayerInput::ActionMappings`/`AxisMappings` (via `AddActionMapping`/`AddAxisMapping`) then `ForceRebuildingKeyMaps(false)` — per-player | §5 Step 3 returns the user's keys |
| (b) | Push into `UInputSettings` then per-instance rebuild — global | §5 Step 3 returns keys, and Step 2 finds 186/16 on the `UInputSettings` CDO |
| (c) | No push at all — a Loki override of the virtual `GetKeysForAction`/`GetKeysForAxis` reading the config manager directly | §5 Step 3 returns keys but Step 2 finds 186/16 *only* on the config manager |

**§5 Step 3 makes H4 largely moot for exploitation:** `GetKeysForAxis` reads the *merged product*
(`ActionKeyMap`/`AxisKeyMap`), which is the same table `ProcessInputStack` dispatches from. If it
returns the user's keys, the pipeline is closed regardless of which array was written.

*Why the two layers differ at all:* the shipped table has 221/20; the user's has 186/16. The 20→16
axis delta is exactly the four gamepad-stick entries, and `GameUserSettings.ini:90` has
`bControllersEnabled=False`. Two keys diverge outright (`Toggle Shop` shipped `P` → user `G`;
`PTTCoreGame` shipped `Y` → user `Z`) — so **the user layer wins**. `MEASURED`.

### H5 — `UInputComponent` → legacy `ActionBindings` / `AxisBindings`
`MEASURED` (structure) / `UNKNOWN` (populated at runtime in our state).
`schema.txt:20839-20840`: `InputComponent : UClass:ActorComponent (1 props)`, sole UPROPERTY
`CachedKeyToActionInfo`, whose struct (`schema.txt:9952-9953`) holds `PlayerInput WeakObjectProperty
(UClass:PlayerInput)`. That struct exists *only* to cache legacy `FInputActionBinding`s by `FKey` for
`UPlayerInput::ProcessInputStack`. The binding arrays themselves are plain C++ TArrays —
**reflection is blind to them**, which is exactly the S80n/S80o lesson.

### H6a — MOVEMENT (axis)
`MEASURED` (that it is axis-based) / `UNKNOWN` (which function is bound).

The axes are `Forward` (W:+1 S:−1 Up:+1 Down:−1), `Right` (D:+1 A:−1 Right:+1 Left:−1),
`Up` (SpaceBar:+1 LeftControl:−1), `MouseX`, `MouseY`, `AimForward`/`AimRight` (Key=None),
`AimForwardAlt`=Gamepad_LeftY, `AimRightAlt`=Gamepad_LeftX. **This is why an action-only search
missed WASD.**

> ### ⚠ DOWNGRADED — `MoveForward` / `MoveRight` are **NOT** the movement entry points
>
> Probes 1 and 2 both asserted, as `MEASURED`, that `ALokiPlayerController::MoveForward(float)` /
> `MoveRight(float)` at `base+0x54259E0` / `base+0x5425A60` are the hero movement handlers and that
> the velocity puppet can be retired in their favour. **The mechanism skeptic wins; this is
> downgraded to REFUTED-CONTESTED and must not be acted on.**
>
> Commit `349c250` disassembled the function: *"`LokiPlayerController::MoveForward` is NOT hero
> movement. Disasm shows it is the SPECTATOR/free-cam path — at `base+0x569A1B1` it does
> `cmp [this+0x3F8],0 / jne <epilogue>`, i.e. it RETURNS when the PC HAS a pawn, and its movement
> branch drives the PlayerCameraManager at `[this+0x470]`. That is why an earlier 'HERO MOVED' was a
> false positive (it moved a DefaultPawn spectator)."*
>
> The commit chain was also read backwards: `b420a69` only *proposed* the movetest, `69f7f1c`
> **voided** its result ("moved the FRESH session's stock DefaultPawn… proves nothing"), and
> `349c250` refuted the semantics. And the name match was never valid evidence in the first place —
> **the axes are called `Forward`/`Right`, not `MoveForward`/`MoveRight`**, in both ini layers.
> *(Marked CONTESTED rather than closed because `[this+0x3F8]` = "has a pawn" is itself an
> attribution, not a reflected name.)*

Zero of the 78 decompiled Angelscript modules mention `MoveForward`/`MoveRight`/`AddMovementInput`/
`BindAxis`/`BindAction`, and zero BP `InpAxisEvt_*` nodes exist. Movement input is **100% native C++**.
`MEASURED`. The actual bound handler is `UNKNOWN` and is a live read (§8).

### H6b — ACTIONS: two dispatch routes
`MEASURED`.

**Route 1 — Blueprint legacy input events.** 39 `InpActEvt_<Name>_K2Node_InputActionEvent` UFunctions
on `BP_LokiPlayerController_C` (re-counted this session in
`tools/extractor/out/BP_LokiPlayerController.uasset.names.txt` → **39**), plus 25 on
`BP_LokiSpectator_C`, 24 on `Comp_PlayerController_Emotes_C`, 6 on `BP_LokiPlayerController_Code_C`,
3 on `Comp_PlayerController_AllyCamera`, 1 on `BP_LokiHeroCharacter_Code`. `K2Node_InputActionEvent`
**is** the legacy FName action node.

**Route 2 — one native GAS enum binding, in `LokiCharacter.cpp`.** Its literal pool holds
`/Script/Loki.LokiAbilityInputID` immediately followed by `CancelTarget`, `ConfirmTarget`,
`CancelTargetAlt`, `ConfirmTargetAlt` — the argument set of
`FGameplayAbilityInputBinds(ConfirmTargetCommand, CancelTargetCommand, EnumName)` handed to
`UAbilitySystemComponent::BindAbilityActivationToInputComponent`, which iterates the UEnum and binds
one action per enumerator with the ordinal as payload. **That single call binds ~30 names at once.**

The bridge between the two naming worlds is
`UPlayerConfigManager::AbilityIDToActionName(LokiAbilityInputID) -> FName`
(`binds_members.csv:46097`). It is **not** the identity and **not** `FName::NameToDisplayString`:
the enum has `ToggleShop`/`SpectateNextPlayer` while the ini has `"Toggle Shop"`/`"Spectate Next Player"`
*with spaces*, yet `UseInventory1` is verbatim in both. Call it; do not assume it. `STRONG_INFERENCE`.

---

## 3. The complete input map

Machine-readable: **`docs/input-map.csv`** — 202 rows, columns
`kind, name, key, shift, ctrl, alt, cmd, scale, group, ability_input_id, bound, shipped_diff`.
Generated read-only from `UserSettings.ini` and cross-checked against the shipped `DefaultInput.ini`.

**Totals:** 186 actions (135 bound / 51 unbound) + 16 axes (14 bound / 2 unbound) = 202.
**Divergences vs shipped:** 2 (`Toggle Shop` G←P, `PTTCoreGame` Z←Y).
**Rows carrying a `LokiAbilityInputID`:** 27.

### 3.1 AXES — all 16 (this is where movement lives)

| Axis | Scale | Key | Group |
|---|---|---|---|
| `Forward` | **+1** | W | movement |
| `Forward` | **+1** | Up | movement |
| `Forward` | **−1** | S | movement |
| `Forward` | **−1** | Down | movement |
| `Right` | **+1** | D | movement |
| `Right` | **+1** | Right | movement |
| `Right` | **−1** | A | movement |
| `Right` | **−1** | Left | movement |
| `Up` | **+1** | SpaceBar | movement |
| `Up` | **−1** | LeftControl | movement |
| `MouseX` | +1 | MouseX | aim |
| `MouseY` | +1 | MouseY | aim |
| `AimForward` | +1 | *(None)* | aim |
| `AimRight` | +1 | *(None)* | aim |
| `AimForwardAlt` | +1 | Gamepad_LeftY | aim |
| `AimRightAlt` | +1 | Gamepad_LeftX | aim |

### 3.2 COMBAT — 18 rows (17 bound), `id` = LokiAbilityInputID ordinal

| Action | Key | id |
|---|---|---|
| `Ability1` | LeftMouseButton | 3 |
| `Ability2` | RightMouseButton | 4 |
| `Ability3` | LeftShift | 5 |
| `Ability4` | R | 6 |
| `ConfirmTarget` | LeftMouseButton | 1 |
| `CancelTarget` | RightMouseButton | 2 |
| `ConfirmTargetAlt` | **Shift+**Gamepad_RightTrigger | — |
| `CancelTargetAlt` | **Shift+**Gamepad_FaceButton_Right | — |
| `DodgeRoll` | Q | 15 |
| `OptionalAbility` | Q | 12 |
| `Glide` | SpaceBar | 11 |
| `Jump` | SpaceBar | 8 |
| `Sprint` | LeftControl | 9 |
| `Sprint` | ThumbMouseButton | 9 |
| `Use` | E | 13 |
| `Recall` | B | 17 |
| `LevelAbilityModifier` | LeftAlt | — |
| `Freelook` | *(None)* | 14 |

### 3.3 ECONOMY — 20 rows, all bound *(the surface the project has "no owner for")*

| Action | Key | id |
|---|---|---|
| `Toggle Shop` | **G** | 20 |
| `OpenGlobalShop` | **V** | — |
| `UseInventory1`…`6` | One … Six | 25…30 |
| `UseUtilitySlot1` | F | 23 |
| `UseUtilitySlot2` | G | 24 |
| `UpgradeEquipment1` | **Ctrl+**One | — |
| `UpgradeEquipment2` | **Ctrl+**Two | — |
| `UpgradeEquipmentBoots` | **Ctrl+**Three | — |
| `UpgradeEquipment4` | **Alt+**Four | — |
| `UpgradeEquipment5` | **Alt+**Five | — |
| `UpgradeSpell_Main` | **Shift+**Gamepad_FaceButton_Top | — |
| `UpgradeSpell_Secondary` | **Shift+**Gamepad_DPad_Up | — |
| `UpgradeSpell_Ultimate` | **Shift+**Gamepad_DPad_Down | — |
| `UpgradeSpell_Dash` | **Shift+**Gamepad_DPad_Left | — |
| `UpgradeSpell_DodgeRoll` | **Shift+**Gamepad_DPad_Right | — |

> Note `Toggle Shop` and `UseUtilitySlot2` are both **G** — a live double-bind, governed by
> `FLokiUniqueInputActionRule` rows in `DT_UniqueInputs.uasset`.
> Note also the five `UpgradeSpell_*` have **no keyboard binding at all** in the live user table —
> only Shift+Gamepad chords, with `bControllersEnabled=False`. The keyboard route for spell upgrades
> is almost certainly `LevelAbilityModifier`(LeftAlt) held with an ability key. `INFERRED`.

### 3.4 UI — 9, all bound

| Action | Key |  | Action | Key |
|---|---|---|---|---|
| `Toggle Map` | M | | `ToggleScoreboard` | CapsLock |
| `Toggle Map` | Tab | | `ToggleAbilityOverlay` | F1 |
| `Toggle Settings Menu` | Escape | | `ToggleHUD` | **Ctrl+**H |
| `DetailedTooltips` | LeftAlt | | `ZoomMapIn` / `ZoomMapOut` | Equals / Hyphen |

### 3.5 COMMS — 9 (8 bound)

`CommsYes`=X · `CommsNo`=C · `Ping`=MiddleMouseButton · `OpenChat`=Enter · `PTTCoreGame`=Z ·
`PTTParty`=P · `ToggleMute`=**Ctrl+**X · `UI_SOCIAL_TOGGLE`=F · **unbound:** `ShowVOPlayer`

### 3.6 CAMERA — 14 (7 bound)

`ZoomCameraIn`=MouseScrollUp · `ZoomCameraOut`=MouseScrollDown · `SmartZoom`=F2 ·
`AllyCamera2/3/4`=F2/F3/F4 · `MinimapCameraPanModifierKey`=LeftAlt
**unbound (7):** `AdjustCameraOffset`, `CameraHoldToLockRotation`, `CameraLockToCursor`,
`CameraSetRotation`, `DragPanCamera`, `Reset Free Camera`, `Switch Camera Mode`

### 3.7 DROP — 3, all bound · PRACTICE — 2, all bound

`SelectDropPodDestination`=LeftMouseButton · `Launch / Eject`=LeftMouseButton · `PassDropLeader`=Z
`Practice_Respawn`=N · `LookAtCapturePoint`=E (id 21)

### 3.8 MENU-NAV — 9, all bound *(CommonUI family)*

`Menu_NavBack`=BackSpace · `Menu_NavLeft_Top`=Q · `Menu_NavRight_Top`=E · `Menu_NavLeft_Sub`=A ·
`Menu_NavRight_Sub`=D · `Menu_NavLeft_Bottom`=Z · `Menu_NavRight_Bottom`=C ·
`Menu_SelectMainOption`=SpaceBar · `Menu_SelectOption1`=S

### 3.9 AIRSHIP — 5, all bound *(bound NATIVELY; `BP_Airdoo` has zero `InpActEvt_*`)*

`AirshipBoost`=SpaceBar · `AirshipForward`=LeftMouseButton · `AirshipReverse`=RightMouseButton ·
`AirshipTurnSpeedBoost`=LeftShift · `AirshipTurretFire`=LeftMouseButton
*(steering reuses the shared `Forward`/`Right` axes — which is why every steering RPC carries a
`bool bIsWASD` discriminator)*

### 3.10 SPECTATE — 26, all bound

`Spectate Next Player`=N (id 18) · `SpectatePlayer1-4`=Z/X/C/V · `SpectateTeam1-10`=One…Zero ·
`SpectateTeam11-20`=**Shift+**One…**Shift+**Zero · `SpectatorShowAllDetails`=LeftAlt

### 3.11 EMOTE — 27 (3 bound)

`EmoteMenu`=T · `EmoteCheer`=LeftMouseButton (id 19) · `PlaceSpray`=Z
**unbound:** `EmoteWheel01` … `EmoteWheel24` (all 24)

### 3.12 CHEAT / DEV — 44 (26 bound)

| Action | Key | | Action | Key |
|---|---|---|---|---|
| `ShowCheats` | **RightAlt** | | `CheatToggleInvulnerable` | NumPadZero |
| `ToggleDebugMenu` | **Ctrl+**Backslash | | `CheatToggleInfiniteHealthAndMana` | O |
| `CheatKillMe` | Subtract | | `CheatToggleNoCooldowns` | L |
| `CheatRespawnSelf` / `CheatStunMe` | NumPadFive | | `CheatToggleKillDamage` | Add |
| `CheatTakeDamage` | NumPadEight | | `CheatRefreshCooldowns` | K |
| `CheatNextHero` / `CheatPreviousHero` | Period / Comma | | `CheatRefreshSelf` | P |
| `CheatTeleportCursor` | ThumbMouseButton | | `CheatStoreLocation` | **Ctrl+**C |
| `CheatMenusNextPage` / `LastPage` | Add / Subtract | | `CheatReturnToStoredLocation` | **Ctrl+**V |
| `CheatMenusPlayRespawnAnim` | NumPadOne | | `DevCheatToggleHUD` | **Ctrl+**F12 |
| `CheatMenusPlayLockinAnim` | NumPadTwo | | `DevCheatNoPacketsIn` | Eight |
| `CheatMenusPlayFinisherAnim` | NumPadThree | | `DevCheatNoPacketsOut` | Nine |
| | | | `DevCheatNoPacketsInOrOut` | Zero |

**unbound (18):** `CheatSpawnAlliedDummy`, `CheatSpawnEnemyDummy`, `CheatSpawnDesignatedSurvivor`,
`CheatLevelUp`, `CheatUpgradePowersToMax`, `CheatBoopSelf`, `CheatForceKillCursor`,
`CheatItemCleanup`, `CheatMoveFixedCamera`, `CheatRotateFixedCamera`, `CheatToggleFixedCamera`,
`CheatToggleCCImmune`, `CheatToggleFloaty`, `CheatToggleHealthRegen`, `CheatToggleIncorporeal`,
`CheatToggleManaRegen`, `CheatToggleMinionIgnore`, `CheatToggleTimeline`

> ⚠ Of 38 `Cheat*` + 4 `DevCheat*` names, exactly **one** (`CheatTeleportCursor`) exact-matches one of
> the 65 native `ALokiPlayerCheats` UFunctions, and two (`CheatToggleHealthRegen`,
> `CheatToggleManaRegen`) match Angelscript console commands — **and both of those are `Key=None`**.
> `Comp_PlayerController_Cheats.uasset` has **no** `InpActEvt_*`. Treat the cheat hotkeys as
> declared-but-orphaned in shipping data and reach cheats through
> `GetLocalLokiPlayerCheatsBP` + native call, not through input.

---

## 4. What S79/S80 actually measured, and the procedural miss

**Be fair in the retraction: nobody mis-measured, and the answer was found twice and then lost.**

### 4.1 The measurements were sound

| Session | Instrument | Measured | Concluded | Verdict |
|---|---|---|---|---|
| S80g | live class-substring scan | 3 `EnhancedPlayerInput` objects, `AppliedInputContexts` all empty | "shortcut dead" | **correct measurement** of an inert subsystem |
| S80i (`88a89b9`) | live RPM property walk of `UPlayerInput` (positive control: `DebugExecBindings @+0x1A8 Num=16`) | 6 props, no mapping arrays | **"there is no legacy input path"** | measurement correct; **generalisation is the error** |
| S80n (`56a0cf1`) | TArray-shape byte scan | a `{ptr,int32,int32}`-shaped triple on the hero's input component | "the hero HAS bindings" | **self-retracted** in `848a077` — a shape is not a field |
| S80q (`46d873a`) | `find_func.py`, needle `inputaction` | 137 UFunctions; 39 on `BP_LokiPlayerController_C` | **"legacy FName events"** | ✅ **CORRECT — the mechanism, found and under-credited** |
| — (`b420a69`) | self-review | *"Every one of those is a DISCRETE ACTION… In UE legacy input, WASD movement is an AXIS… a different binding path I never searched."* | — | ✅ **CORRECT — and it lives only in a commit message** |

### 4.2 The four procedural misses

**(M1) A class-scoped instrument was used to falsify a concept.** A property walk of `UPlayerInput`
can only ever answer *"is this a UPROPERTY on `UPlayerInput`?"*. It was read as *"does the legacy
input path exist in this game?"*. **Rule:** write the finding as *"not a UPROPERTY on class X"* — never
as *"absent from the build"*.
S80n stated exactly this rule (*"reflection CANNOT see these… that silence must not be read as 'no
bindings'"*) **the same day, ~6 sub-steps later**, and it was never applied backwards to S80i.
**Rule:** when you write a new "my instrument cannot see X" rule, immediately grep the session's own
doc for prior claims of the form "X is absent".

**(M2) Every needle was pre-committed to the hypothesis.** Complete needle inventory across the
thread: class substrings `InputMappingContext`, `PlayerInput`, and `input_ctx.py`'s hardcoded filter
(`tools/re/input_ctx.py:60`: `"EnhancedInput" in cn or "EnhancedPlayerInput" in cn or cn=="InputMappingContext"`);
FNamePool needles `MappingContext`, `IMC`, `InputAction`; `find_func.py` needles `inputaction`, then
`inpaxisevt|axisevt|moveforward|moveright`; a BP-bytecode scan for callee `AddMappingContext`;
extractor `IMC_`/`InputMappingContext`/`MappingContext`; exe `strings IMC_` + `wstrings MappingContext`.
**Never a bare `Input`. Never `Config`. Never `ActionMapping` or `AxisMapping`.** The search could
only confirm or deny the IMC hypothesis — never replace it.
**Rule:** before hunting a specific asset/class, enumerate the whole namespace once with the broadest
needle you can afford.

**(M3) The winning needle was written down and then not run.** S80m step 1 lists
`nameid … InputAction / IA_ / InputConfig / Keybind / LokiInput`
(`docs/session-79-moonshot-plan.md:832`). S80p executed **only** `InputAction`. `InputConfig` would
have hit `InputConfigVersion` — a reflected UPROPERTY on `PlayerConfigManager`.
**Rule:** when a plan lists N needles, run N, or record which you dropped and why. A dropped needle
looks identical to a needle that returned nothing.

**(M4) — the big one — TWO CORRECT CORRECTIONS DIED IN GIT.** `46d873a` (mechanism found) and
`b420a69` (axis miss named) both landed on 2026-07-16. Neither was ever written into
`docs/session-79-moonshot-plan.md` — whose last input entry is S80u at line 1094 — and
`grep -rn "WASD is an AXIS" docs/ memory/` returns **0 hits**. The doc that carries FK-2 still opens
with the false sentence, so every subsequent reader hit the false sentence first.
**Rule:** a retraction must be written INTO the doc that carries the belief, at the line that carries
it. An ignorance-map entry is a pointer, not a fix. *(This document's §5 Step 0 discharges that.)*

**(M5) The thread stopped by GOAL SUBSTITUTION, not by hitting a wall.** Two commits after
`b420a69` named the gap, the immediate objective (a moving hero) was reached by bypassing input
entirely — `69f7f1c` (movetest voided) → `349c250` (root cause = NULL GAS AttributeSet) → `5b13f81`
(hero moves via 8 attribute writes) → `6a7bbda` (`MODE_PLAYABLE`: `GetAsyncKeyState` → `AddMovementInput`).
Nothing refuted the input thread; it was made *locally unnecessary*.
**Rule:** when a question is abandoned because a workaround landed, record **"SUPERSEDED, not
answered"** — never let it settle as "UNRESOLVED".

### 4.3 Two sibling artifacts that must be corrected alongside FK-2

**(i) `46d873a`'s "native `LokiPlayerController` — ABSENT ENTIRELY: ZERO input events" is a
TAUTOLOGY OF THE INSTRUMENT.** `tools/re/find_func.py:47` is `if ocls(obj)!="Function": continue` —
it enumerates UFunctions only. Native `BindAxis`/`BindAction` take **raw C++ member pointers**
(`UE_5.4/.../Components/InputComponent.h:873,909`) and create no UFunction; and `K2Node_*` UFunctions
can exist only on Blueprint classes by construction. So the tally could not have found native
bindings even if they were there — and they are: the `LokiPlayerController.cpp` literal pool holds
`AimForward` / `AimRight` / `AimForwardAlt` / `AimRightAlt` / `Recall` / `Sneak` at
`dumps/merged.dump.exe` RVA 0x8B2FA30-0x8B2FA74, four of six being verbatim ini AxisNames.
> **S80r's "the two halves of a playable hero live on DIFFERENT PlayerControllers" theory, and the
> S80s-u `SetPlayer` hunt (4 candidates, 4 refuted, 0 called), both inherit this artifact.
> Do not re-open them on that basis.**

**(ii) `dumps/merged.dump.exe` was never actually merged.** Manifest re-read this session
(`dumps/merged.dump.exe.txt`): seed contributes **88,854,234 B**; the other four inputs contribute
**910 + 107 + 124 + 54 = 1,195 B** total. `.text` 48.1% non-zero, `.pdata` **0.0%**.
> **"Not found in the dump" is never evidence of absence.** Every pre-`dumpimage` string-absence
> conclusion in this project is void and must be re-run.

**(iii) The usmap struct-type shift, stated precisely (corroborates FK-14).** Verified twice this
session on classes whose stock layout is known:

> **The displayed inner/struct-type annotation for property *N* is actually property *N+1*'s type.**
> The outer property class (`ArrayProperty` / `StructProperty` / `Int64Property`) is correct.

`PlayerInput`: `DebugExecBindings` (really `TArray<FKeyBind>`) prints `ArrayProperty<NameProperty>`
= `InvertedAxis`'s real inner; `InvertedAxis` (really `TArray<FName>`) prints
`ArrayProperty<StructProperty UStruct:Key>` = `GamepadAltKey`'s real type.
`InputSettings`: `AxisConfig` prints `PerPlatformSettings` = the next property's type;
`ActionMappings` prints `InputAxisKeyMapping` = `AxisMappings`'s; `AxisMappings` prints
`InputActionSpeechMapping` = `SpeechMappings`'s; `SpeechMappings` prints `SoftClassProperty` =
`DefaultPlayerInputClass`'s. Same on `PlayerConfigManager`.
**Correction source:** `tools/asdump/out/binds_members.csv` is derived from `Binds.Cache` by a
different path and gives the true types (`:46144-46146` → `TArray<FInputActionKeyMapping>
ActionMappings`, `TArray<FInputAxisKeyMapping> AxisMappings`, `TArray<FInputActionSpeechMapping>
SpeechMappings`). Use it wherever FK-14 bites. **Never take an array STRIDE from the usmap.**

---

## 5. The exploitation plan

Ordered by cost. Each step is **one variable** and yields **one bit**. Steps 0-2 need no injection.
Step 3 is the decisive one. Step 5 is gated on someone else's unfinished work.

> **HARD CONSTRAINTS, restated because two of them are currently mis-stated in the project record:**
> - ⚠ **`tutorial_launch.dll` does NOT take the shared PI mutex.** `grep -n 'CreateMutex|SuperviveMissionsPIHook|WaitForSingleObject' tools/sigbypass-mod/tutorial_launch.cpp`
>   → **zero hits**, verified this session. It is safe only because the force-open route runs it alone
>   via `-Hook <path>`. **Either add the mutex or write "run alone, no secondaries" as an explicit
>   precondition on every step below.** Do not leave it implicit.
> - No permanent `.text` patch (the 3-5 min integrity check). All hooks transient: install → one
>   game-thread call → uninstall. `tutorial_launch.cpp:4291-4433` already does this; inherit it.
> - No C++ exceptions in the payload. Use SEH (`__try/__except`), as the file already does.
> - Returned `TArray`s from `CallNative` are written into `g_rbuf` and **never freed**. Fine for a
>   handful of probe calls; **never put a `Get*Mappings` call inside a per-frame hook.**
> - S81's 20 s CMC game-thread stall is a **DS-route** hazard. It does not apply to a read-only probe,
>   and force-open standalone has no netdriver to time out. Re-assert it only when someone actually
>   proposes per-frame `AddMovementInput` in place of the puppet.

### Step 0 — Retract in place *(offline, minutes, zero risk)*

Write the correction **INTO** `docs/session-79-moonshot-plan.md` at line 688 — not only into
`docs/ignorance-map-s101.md` §FK-2 — so the false sentence is never read alone. Amend
`docs/coverage-audit-s101.md:218` from *"WASD PARTIAL — velocity puppet only; stock input path dead"*
to *"stock input path **UNTESTED with a validated instrument**; 186 actions + 16 axes exist on disk"*.
Correct the two sibling artifacts in §4.3.

> **One bit:** line 688 no longer reads as a live belief when read alone.
> *This is the highest-value action in the plan. M4 is the failure mode that kept FK-2 alive; a
> retraction that repeats it accomplishes nothing.*

### Step 1 — Offline action→owner sweep *(offline, ~1 h runtime, zero risk)*

`extractor names <pkg>` over every `BP_*` / `Comp_*` / `WBP_*` package; grep `InpActEvt_`. Produce
one table: action name → owning asset → UFunction name. 98 of ~192 are already attributed
(§2 H6b); this closes the rest.

> **One bit:** `Toggle Shop`, `OpenGlobalShop` and `UseInventory1` each have a named owning UFunction.
> *This is the step that actually discharges FK-2's listed steer about unowned economy entry points.*

### Step 2 — Main-menu, read-only RPM, no injection *(minutes, zero risk)*

`tools/re/find_uclass.py PlayerConfigManager` → `obj_by_class.py` → `class_props.py`. Read
`ActionMappings` / `AxisMappings` `{Data,Num,Max}` **at walker-resolved offsets** (both are reflected
UPROPERTYs — do not hardcode 0x1B8/0x1C8, let the walker prove them). Same pass: resolve
`ControlInputVector` / `LastControlInputVector` offsets from the reflected chain
(`schema.txt:40220-40221`) and compare against `input_watch.py`'s hardcoded `+0x418` / `+0x430`.

> **One bit A:** `ActionMappings.Num == 186 && AxisMappings.Num == 16`.
> **Refuse any TArray-shaped match that does not hit those exact counts** — the exact-count rule is
> what makes this immune to the S80n shape-is-not-a-field error.
> **One bit B:** resolved offsets == `0x418` / `0x430`, yes or no. If **no**, `input_watch.py` is
> patched and **every prior "input does not reach the pawn" reading is void**, full stop.

*Context for bit B:* the DS route's equivalent probe (`ds_hybrid.cpp:2552`) resolves those offsets
**by reflection** (`PropOffsetOnClass(ClassOf(hero),"ControlInputVector")`) rather than hardcoding
them, and got non-zero readings. So the concept has a positive control; the literal constant in
`input_watch.py` does not.

### Step 3 — ★ THE DECISIVE PROBE ★ — does the table *dispatch*? *(main menu, one small shim)*

Call the mixin-library statics on the live `PlayerController->PlayerInput`, **at the MAIN MENU**, via
the existing `ProcessInternal` direct-thunk primitive.

**Why this and not a bigger scan:** an offset scan answers *where the data is stored*. This answers
*whether the data is the dispatch table*. `GetKeysForAxis` calls `ConditionalBuildKeyMappings()` and
reads `AxisKeyMap` — **shared code with `ProcessInputStack`**, verified in source
(`PlayerInput.cpp:2163-2187`). It needs no offsets, no strides, no disassembly. It runs at the menu
with no force-open, no GAS dependency, and no injection risk beyond the primitive itself. And it
makes **H4 moot**: the key map is the merged product, so it does not matter which array Loki wrote.

Three calls in one pass:
1. `GetKeysForAxis("Forward")` — **expect 4** entries (W, S, Up, Down).
2. `GetKeysForAction("Ability1")` — **expect LeftMouseButton** (the action and axis maps build
   independently, so both halves must be tested).
3. `GetKeysForAxis("NotAnAxis")` — **must return 0.** ★ **This is the null control**, and it is not
   optional: without it a non-empty result is uninterpretable. Its absence is precisely what made the
   S80n false positive possible.

> **One bit:** both real queries non-empty **and** the null control empty.
> - **Both non-empty + null empty** → the legacy tables ARE the live dispatch source. §1 verdict **B
>   is upgraded PROBABLE → MEASURED**, and the remaining question collapses to the force-open state
>   alone.
> - **Both empty (null control also empty)** → the arrays are a settings store and dispatch is
>   elsewhere. The FK-2 retraction still stands, but §2's model is **void** and must be rebuilt.
> - **Axis empty, action non-empty (or vice versa)** → a partial fork, and you know exactly which
>   builder was edited.

**Two caveats to record before running.** (i) Verify the real param layout with
`tools/re/ufunc_params.py` first — the CSV declaration hides the implicit object arg
(`static_in_unreal=1`, so the `UPlayerInput*` is arg 0). (ii) The return is `const TArray&` — use the
OUT-param path RE'd in S58. Minor artifact: the call itself would build the maps if unbuilt, but stock
`ProcessInputStack` builds them every frame the PC ticks, so at menu time they are already built.
Class existence is **confirmed**, not assumed: `schema.txt:41096`
`PlayerInputScriptMixinLibrary : UClass:Object (0 props)`.

### Step 4 — The positive control S75 never had *(force-open, ONE added `if` block)*

In `RM_WAKEMOVE` **only**: immediately after the existing
`CallNativeGuarded(g_amiFn, …)` — **same game-thread hit**, before the next tick can consume — read
`hero + <offset resolved in Step 2>` and log it. Nothing else changes. Build `-DKNOMOVE` / puppet off.

**Why this is necessary:** S75's two measurements **never co-occurred**. `input_watch.py` sampled
Ctrl/LastCtrl externally at 4 Hz while a human held WASD with **no forced call**; separately,
`RM_WAKEMOVE`'s 6,706 forced `AddMovementInput(+X, bForce=true)` calls logged through `WmSampleLine`
(`tutorial_launch.cpp:665-674`) — which samples **pos / mode / gravity / velocity and never reads
`ControlInputVector` at all**. The forced call and the Ctrl sample have never been in the same
experiment in force-open.

> **One bit:** `|ControlInputVector| > 0` in the same hit as a forced `AddMovementInput(+X, bForce=true)`.
> **Non-zero** → the instrument is valid, S75's negative stands, and *"the stock axis path does not
> deliver in force-open"* becomes a real measurement for the first time.
> **Zero** → the instrument is broken and the entire "stock input path dead" record collapses.
> Either answer is decisive; neither can crash (one guarded read after an already-guarded call).

> ### ⚠ Why probe 4's "S75 is confounded, the GAS clamp explains it" is only ¼ true
> Probe 4 argued that with `AttributeSetStorage` NULL, `GetMaxAcceleration()==0` so
> `Acceleration = MaxAcceleration × input = 0`, therefore all four of S75's zeros are explained.
> **Commit `349c250` — probe 4's own citation — measured, with the SAME NULL:**
> `ControlInputVector=(4,0,0)`, `LastControlInputVector=(8,0,0)`,
> `CMC Acceleration=(50000,0,0)` *== MaxAcceleration, full forward*, and **only** `Velocity` clamped.
> The clamp is on `GetMaxSpeed`, **not** `GetMaxAcceleration`.
> **The GAS clamp explains ONE of S75's four zeros. The other three stand unexplained.**
> Probe 4's secondary aliasing argument is also half-wrong: `ControlInputVector` is consumed per
> tick, but `LastControlInputVector` exists precisely to survive that, and both read zero.
> **The mechanism skeptic wins here; this stays downgraded.**

### Step 5 — Verbs, by DIRECT CALL, not by input *(separate session, separate mode each)*

**5a.** `CallBPGuarded` on one `InpActEvt_*` UFunction from Step 1. Start with `ToggleScoreboard` or
`Toggle Map` — pure UI, no economy state, no GAS.
> **One bit:** the widget appears.

**5b. BLOCKED until GAS lands.** Before any `TryActivateAbilityByInputID`, read
`GetAvatarActorFromASC()` and require `== hero`.
> **One bit:** avatar == hero. Only then fire, in its own mode, with **no grant call in the same build**.

*Why blocked:* HEAD is `6e8a7df` "S103: … GATE 1 cleared" and `hero+0xF00/0xF08/0xF10` are still NULL.
A `false` return from `TryActivateAbilityByInputID(3)` today is consistent with **five** distinct
causes (no ability granted / ASC avatar ≠ hero / wrong ASC resolved / `FUNC_BlueprintAuthorityOnly` /
wrong ordinal). That is uninterpretable by construction and violates the project's own
single-variable convention on the exact frontier S101-S103 are still chasing.

### Explicitly DROPPED, and why

| Dropped | Reason |
|---|---|
| **Retiring the velocity puppet in favour of `MoveForward`/`MoveRight`** | `MoveForward` is the spectator/free-cam path (`349c250`), and it is the weakest item in the probe packet. The puppet works and holds 10 min. |
| The `Forward`/`Right` `BindAxis`-target disassembly hunt | Gated behind a Step-4 zero, and the pages are in the ~52% of `.text` that has never demand-decrypted. |
| `SendInput` synthetic keys | Buys **zero** capability — it lands where a real keypress already lands, and `6a7bbda` proved real keys reach a shim (720 inputs). Keep only as a way to remove the human from the measurement loop. |
| Writing `UInputSettings::ActionMappings` at runtime | **Inert** without a per-instance `ForceRebuildingKeyMaps(true)` — see §2 H3. |
| Runtime `SetActionInput` / `RestoreDefaultBindings` / `InputConfigVersion` downgrade / `-ini:UserSettings` | All write to `UserSettings.ini`, **read-only this round**; needs explicit user approval and a backup. |

---

## 6. What this unlocks beyond movement

**Movement was never the prize.** The velocity puppet already moves the hero, and 0 of the 186 actions
are reachable through it. The prize is the **action surface**, and it has **two** direct-call routes
that bypass the input stack entirely — which is why Step 5 outranks any input driver.

### 6.1 GAS half — ~30 verbs, one native call each

`ULokiAbilitySystemComponent::TryActivateAbilityByInputID(LokiAbilityInputID) -> bool`
(`binds_members.csv:39452`, `[Native, BPCallable]`, one enum-byte param, bool return — an ideal
one-bit oracle). Live-inventoried in `docs/session-100-gas-api-dump.txt` alongside
`GetAbilityByInputID`, `GetInputIdOfAbility`, `GetAbilityClassForInputID`, `TryEndAbilityByInputID`,
`LevelUpAbilityByInputID`, `IsPrimaryAbilityInstanceActiveByInputID`,
and `BP_AuthGiveAbilityWithInputID`.

> ⚠ **Gotcha that will cost an iteration:** the grant function's *script* name is
> `AuthGiveAbilityWithInputID` but its **unreal_name is `BP_AuthGiveAbilityWithInputID`**
> (`binds_members.csv:39408`). `ResolveFuncSuper` on the script name silently fails.

Reachable ordinals (§3 and `schema.txt:70157-70189`): `Ability1-4`=3-6, `Jump`=8, `Sprint`=9,
`Glide`=11, `Use`=13, `DodgeRoll`=15, `Recall`=17, `Spectate Next Player`=18, `EmoteCheer`=19,
**`Toggle Shop`=20**, `LookAtCapturePoint`=21, `UseActiveItem`=22, `UseUtilitySlot1/2`=23/24,
**`UseInventory1-6`=25-30**.

### 6.2 Blueprint half — ~98 named verbs, one `CallBPGuarded` each

The `InpActEvt_<Name>_K2Node_InputActionEvent` UFunctions are **real UFunctions with real names**
(39 on `BP_LokiPlayerController_C` alone). Calling
`InpActEvt_ToggleShop_K2Node_InputActionEvent_N` **is** pressing G, minus the entire input stack.
The project has had `CallBPGuarded` since S91.

### 6.3 The economy surface finally has owners

FK-2's steer listed *"the in-match economy entry points (shop, inventory, upgrades) that the project
has no owner for."* They have owners — a fleet of ~60 PlayerController components under
`Loki/Content/Loki/Core/Player/Controller/Components/`: `Comp_PlayerController_Shop_PowersAndPassives`,
`_CraftingShop`, `_QueuedShopItems`, `_InvOps`, `_CurrencyRequest`, `_Armory`, `_Forge`,
`_ShopkeeperInteract`, `_Shop_HeroSwap`, `_PerkPreSelect`, `_Abilities`, `_Pings`, `_Recall`,
`_Scoreboard`, `_Map`, `_MinimapTeleport`, `_QuickComms`, `_Emotes`, `_Cheats`, … — fed by exactly
the actions in §3.3. `MEASURED` (`tools/extractor/out/allfiles.txt`).

### 6.4 Angelscript entry points, ready-made

The script layer is strictly a **callee**, never a binder — which is why cross-referencing all 193
action names against the 10,720-row AS string-literal pool returned **0 exact hits**. That emptiness
is itself the finding. But it hands over free levers:
- `ULokiInteractionPlayerComponent::ProcessInteractionInputPressed/Released` ≡ pressing **E**
- `ULokiDragCameraComponent::NotifyInputPressed/NotifyInputReleased` ≡ **DragPanCamera**
- `ALokiPlayerController_AS::OnPracticeRespawnPressed` (+0xFD0) `.Broadcast()` ≡ pressing **N**;
  also `OnSneakPressed` (+0xFB0) / `OnSneakReleased` (+0xFC0)

*(`Sneak` appears as a native `LokiPlayerController.cpp` literal but has **no** ini action — the ini
has `Sprint`. Matching orphan on both sides.)*

### 6.5 Cheats — reachable, but NOT through input

See the §3.12 warning. 37 of 38 cheat hotkeys are orphaned in shipping data. The one live path is
`ShowCheats`(RightAlt) → cheat-menu visibility, gated by `ALokiPlayerCheats::AreHotkeyCheatsEnabled()`
/ `EnableHotkeyCheats` — worth exactly one probe to confirm the orphan finding rather than assume it.
Everything else goes through `GetLocalLokiPlayerCheatsBP` + native call (65 UFunctions,
`docs/session-74-cheat-enum-dump.txt`).

---

## 7. The config surface as a control plane

Found while settling FK-2; recorded here so it is not re-derived. Detail: `docs/config-control-plane-s101.md`.

**Two write mechanisms.** (A) `-ini:<BaseName>:[Section]:Key=Value` on the command line — already
load-bearing for the login redirect (`configs/launch-redirect.ps1:297-311`). The engine's canonical
config base-name table is at `dumps/merged.dump.exe` RVA 0x076BC130:
`Engine, Game, Input, DeviceProfiles, GameUserSettings, Scalability, RuntimeOptions, InstallBundle,
Hardware, GameplayTags`. **`Input` is in it. `UserSettings` is NOT** — so the live binding table may
need a file write. (B) Write the user file then set it **read-only** — proven at
`launch-redirect.ps1:273-287` (the game rewrites these files every launch and strips unknown
sections; read-only defeats it). Precedence: command line > `Saved/Config` > `Loki/Config/Default*.ini`
> `Engine/Config/Base*.ini`.

**Levers found (all MEASURED at the config layer):**

| Lever | Where | What it might buy |
|---|---|---|
| **`ConsoleKeys=Tilde` SHIPS** | `DefaultInput.ini:368-369` — `-ConsoleKeys=Tilde` **then** `+ConsoleKeys=Tilde` (UE's idempotent remove-then-add: Theorycraft **pinned** it, did not delete it). Plus `BaseEngine.ini:101 ConsoleClassName=/Script/Engine.Console` and `BaseInput.ini:16,51,54`. | **FK-13's "every config-side console knob is gone" is measurably FALSE.** The only remaining gate is the compile-time `ALLOW_CONSOLE` flag — which no string scan can decide. Cost to test: **press `~`**. If it opens, `open 127.0.0.1:7777` and `?game=TutorialGameMode` become one keypress. |
| Log verbosity | `DefaultEngine.ini:790-806` — 15 categories, **none Verbose**; `LogNet`/`LogOnline`/`LogAccelByte`/`LogAccelByteLobby` all `Warning`, `DFLLog=Fatal`. `-LogCmds=` present in the image (UTF-16 @0x76B25E0). | The project has read a deliberately quiet `Loki.log` for 101 sessions. `-LogCmds="LogNet Verbose"` is one flag. |
| Netcode instrumentation | `UserSettings.ini:210` `GenericPlayerConfigGroups` → `Stats` group: `RTTMs_`, `JitterMs_`, `InPacketLossPercent_`, `OutPacketLossPercent_GraphEnabled` all **False**; only ClientFPS/ServerFPS True. | Free in-client RTT/jitter/loss graphs — exactly what the S81 disconnect work had to infer from outside the process. **Requires writing `UserSettings.ini` → needs user approval.** |
| `ConnectionTimeout=15.0` | `DefaultEngine.ini:368-372` (`IpNetDriver`; `InitialConnectTimeout=30.0`, `ReplicationDriverClassName=/Script/Loki.LokiReplicationGraph`) | The config **names the number** S81's ~20 s CMC stall blew through. `-ini:Engine:…:ConnectionTimeout=120` is a clean single-variable test. |
| 34 `+GameModeClassAliases` | `DefaultEngine.ini:123-168` incl. `TutorialGameMode` → `BP_LokiGameMode_Tutorial_C`; `GameDefaultMap=LVL_Login` | Short `?game=<Alias>` tokens for every shipped mode, ready if the console or a travel URL opens. |
| `QosManagerServerUrl=` **empty in all 13 AccelByte env blocks** | `tools/extractor/out/DefaultEngine.ini:468…743` | The backend never has to implement QoS/latency endpoints. Removes a whole speculative category permanently. |
| No loose `.ini` in the install | all 64 shipped `.ini` are inside the pak; only writable surface is `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\` (4 files) + `-ini:` | Rules out editing shipped defaults without an IoStore mod-pak overlay. |

---

## 8. What remains genuinely unknown — and the exact probe for each

| # | Unknown | Exact probe | Decides |
|---|---|---|---|
| **U1** | **Do the mapping tables DRIVE dispatch?** (§1 verdict B — the whole difference between PROBABLE and MEASURED) | **§5 Step 3.** `GetKeysForAxis("Forward")`, `GetKeysForAction("Ability1")`, `GetKeysForAxis("NotAnAxis")` on the live `PlayerInput`, at the main menu, via the ProcessInternal primitive. Verify param layout with `ufunc_params.py` first; OUT-param path from S58. | Both real non-empty + null empty ⇒ **B becomes MEASURED**. |
| **U2** | **Does the legacy axis path deliver in FORCE-OPEN?** (§1 verdict C) | **§5 Step 4.** One guarded read of `ControlInputVector` in the same game-thread hit as the existing forced `AddMovementInput`, offsets from Step 2. | The first honest measurement of C. |
| **U3** | H4 — which sink receives the config manager's 186/16 (`UPlayerInput` / `UInputSettings` / a virtual `GetKeysFor*` override) | §5 Step 2's exact-count scan across all three objects. **Refuse any TArray shape that is not exactly 186 or 16.** | Mechanism completeness. **Moot for exploitation if Step 3 passes.** |
| **U4** | Which UFunction (or raw member pointer) is bound to `Forward`/`Right`? | Only if U2 reads zero. Walk `PC->InputComponent`; the binding arrays are plain C++ TArrays, so this is **disassembly of `BindAxis`**, not reflection. **Do not infer a TArray from a `{ptr,i32,i32}` byte shape** (the S80n error). | Whether a UFunction handler exists to call directly. |
| **U5** | Are the hero's `FGameplayAbilitySpec.InputID`s populated? | Walk `ActivatableAbilities.Items` on the ASC; cross-check with `GetInputIdOfAbility`. Blocked on S102/S103. | If all −1, input can never activate abilities and `TryActivateAbilityByInputID` is mandatory. |
| **U6** | Does the ASC's `ActorInfo.AvatarActor == hero`? | `GetAvatarActorFromASC()` on the S103 carrier's ASC. **There is no BlueprintCallable `InitAbilityActorInfo` in this build** — if wrong, the fix is `BP_OnRep_PlayerState` / `OnLocalASCInitialized`, not a direct init. | **Crash gate for §5 Step 5b.** Do not fire abilities before this reads true. |
| **U7** | Is `TryActivateAbilityByInputID` `FUNC_BlueprintAuthorityOnly` or `FUNC_Net`? | `tools/re/ufunc_params.py` → read `FunctionFlags`. | Force-open is standalone authority so it should pass; the DS-route client never could. |
| **U8** | Is `ALLOW_CONSOLE` compiled in? | Press `~` at the menu and in a force-open match. Measurement alternative: read `GEngine->GameViewport->ViewportConsole` for non-null and look up `/Script/Engine.Console` via `find_uclass.py`. | **FK-13.** Cheapest high-value probe in the project. |
| **U9** | Do `ShowCheats`(RightAlt) / `ToggleDebugMenu`(Ctrl+\\) / `DevCheatToggleHUD`(Ctrl+F12) do anything? | Press them in a force-open match. Zero setup. | A shim-free debug surface, or confirmation of the §3.12 orphan finding. |
| **U10** | Does `-ini:` reach `UserSettings`? (it is **not** in the canonical base-name table) | `-ini:UserSettings:[/Script/Loki.PlayerConfigManager]:HasSeenTutorial=False`, then RPM-read the live value. | Whether the 186-entry table is command-line controllable or needs the read-only-file dance. |
| **U11** | What does `AbilityIDToActionName` actually do? (not identity, not `NameToDisplayString`) | Call it live for all 32 enum values. | Required for any ability-slot → key mapping. |
| **U12** | What gates `InputConfigVersion=13`? Does lowering it force a re-seed from `DefaultInput.ini`? | Set `InputConfigVersion=1`, read-only the file, relaunch, diff. **Requires user approval — write to `UserSettings.ini`.** | 186→221 and `Toggle Shop` P←G would confirm the cheapest lever on the whole input layer. |
| **U13** | Is the removal of the three `UPROPERTY` markers on `UPlayerInput` a UE 5.4 stock change or a TheoryCraft fork edit? | Compare against a vanilla 5.4 usmap. | Does not affect the model (the C++ members are proven present either way) but it bounds **how much stock-UE reasoning can be trusted anywhere in this build** — see §1.4. |
| **U14** | `GenericPlayerConfigGroups` (@0x1E8) — a second config surface the AS layer reads (`LokiAimingVisComponent` queries `Aiming`/`UseAimingLaser`/`LimitLaserToCursor`) | Read it live; it is a reflected MapProperty. | May hold gameplay-relevant toggles nobody has mapped. |
| **U15** | Bare `EmoteWheel` is compiled in but `EmoteWheel01..24` are not — composed at runtime or purely config? | Read the config manager's `ActionMappings` live rather than string-hunting. | Only loose end in the offline chain. Low stakes. |

---

## Appendix A — Method rules earned here

1. **A class-scoped instrument cannot falsify a concept.** Write *"not a UPROPERTY on class X"*, never
   *"absent from the build"*.
2. **Absence of a `UPROPERTY` ≠ absence of a field.** The entire legacy input pipeline
   (`ActionMappings`, `AxisMappings`, `AxisConfig`, `ActionKeyMap`, `AxisKeyMap`, `bKeyMapsBuilt`,
   `UInputComponent::AxisBindings`) is un-reflected in **stock** UE.
3. **Enumerate the namespace once with the broadest needle before hunting a specific asset.**
4. **Run every needle a plan lists, or record which you dropped.**
5. **A retraction goes INTO the doc that carries the belief, at the line that carries it.**
6. **When a question is abandoned because a workaround landed, write "SUPERSEDED, not answered".**
7. **When you write a new "my instrument cannot see X" rule, sweep backwards for prior "X is absent" claims.**
8. **Every negative needs a null control.** A non-empty result without one is uninterpretable
   (S80n); an empty result without one is unfalsifiable.
9. **"Not found in `dumps/merged.dump.exe`" is never evidence of absence** — `.text` is 48.1%
   decrypted and the merge is one dump + 1,195 bytes.
10. **Never take an offset or an array stride from the usmap or from stock UE source for a class this
    build forked.** Derive it from disassembly or prove it by exact-count match.
11. **Step 0 before Step 1.** `grep schema.txt` for the property name costs seconds; the answer to
    FK-2 was in a committed repo file 15 days before the thread that failed to find it.
