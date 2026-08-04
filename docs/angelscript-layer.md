# The SUPERVIVE Angelscript layer — master document

**Date:** 2026-07-26 · **Build:** shipping, dated 2025-12-17 · **Status:** decompiled end-to-end.

This is the index document for the whole Angelscript surface. It says what the layer is, how good
the decompile actually is, what each of the 78 modules does, which of the project's prior
conclusions it overturns, and what to do next. Every subsystem has its own detailed report; this
document links to them and does not duplicate them.

| document | scope |
|---|---|
| `docs/angelscript-layer.md` | **this file** — master index, route implications |
| `docs/angelscript-dropphase.md` | DropShip / DropPod / DropPhase / Airship / ExoticLoot (7 modules) |
| `docs/angelscript-ffa-bots.md` | FFA deathmatch, bot roster, respawn loop (6 modules) |
| `docs/angelscript-barracuda.md` | the Barracuda MOBA mode (28 modules) |
| `docs/angelscript-core-gameplay.md` | GameState, PlayerController, HeroCharacter, cheats, status effects, aiming lasers (15 modules) |
| `docs/angelscript-systems-rest.md` | UAV, Items, Armory, Interaction, Domination, MostWanted, Minions, Vault, DayNight, UI, Content (22 modules) |
| `tools/asdump/FORMAT.md` | definitive binary format spec for all three caches |
| `tools/asdump/README.md` | tool usage, validation numbers, limitations |
| `tools/asdump/PATCH-lifter-fixes.md` | the three lifter/structurer defects, two merged, one open |
| `tools/asdump/out/` | 78 reconstructed `.as.txt` files (declarations + bodies + disassembly) |

**Nothing in this work was run.** The game was not launched, nothing was injected, and the three
cache files were opened `'rb'` only — their mtimes are still 2025-12-17. Everything below is
static analysis of shipped bytes.

---

## 1. What the Angelscript layer IS, and why it was invisible for 100 sessions

SUPERVIVE runs on a **forked Unreal Engine 5.4 that embeds UE-Angelscript** (Hazelight's
`UnrealEngine-Angelscript` plugin, itself a fork of Andreas Jönsson's AngelScript). The fork is
compiled *into the shipping executable* as an engine module — `/Script/Angelscript` — not shipped
as a plugin under `Loki/Plugins/`. On top of that runtime, Theorycraft wrote a substantial slice of
the game's gameplay logic in Angelscript rather than in C++ or Blueprint.

That layer ships as three files in `<install>/Loki/Script/`:

```
PrecompiledScript.Cache   1,184,817 B   declarations + compiled bytecode for all 78 modules
Binds.Cache               5,764,301 B   the engine<->script bind table (4,784 structs, 5,582
                                        classes, 15,327 methods, 33,961 properties)
Binds.Cache.Headers       2,050,287 B   /Script/Module.Class -> C++ header path (14,184 links)
```

Measured contents of `PrecompiledScript.Cache`:

```
78 modules · 110 script classes · 600 properties · 1,463 functions
36,293 instructions across 241,416 bytes of bytecode · 105 distinct opcodes
500 UFUNCTIONs · 4 script-declared enums
```

The class hierarchy in a shipped SUPERVIVE Blueprint runs
**`BP_HERO_Assault_C` → `BP_LokiHeroCharacter_C` → `BP_LokiHeroCharacter_Code_C` →
`/Script/Angelscript.LokiHeroCharacter_AS` → native `/Script/Loki.LokiHeroCharacter`.**
The script layer sits *between* the content and the C++, and it is where a lot of the
server-authoritative rules actually live.

### Why it stayed invisible

The project first noticed Angelscript existed in **S74** (`docs/session-74-overlay-spike-angelscript.txt`)
while tracing that exact parent chain, and immediately inventoried it in
`docs/session-74-routeB-as-native-split.md`. That inventory reached a conclusion that shaped every
session after it:

> "**only 18 classes are Angelscript**… a THIN Angelscript layer (hero, PC, GameState, day/night,
> airship, a status-effect component, 2 widgets, cheats) sitting on a NATIVE C++ core (gamemode,
> round, deploy, drop-pod, respawn, most components)."

That inventory was produced by **string-scanning the cache for names ending in `_AS`**. The `_AS`
suffix is a UE-Angelscript *naming convention* — the plugin appends it only when a script class
shadows an identically-named C++ class. It is not a marker, and most script classes do not carry it.

Measured against the parsed cache:

```
script classes total            110
  named *_AS                      9      <- what the S74 scan could see
  UObject-shaped, NOT *_AS       67      <- invisible to that scan
  (remainder: script structs + generated delegate types)
```

The 67 invisible ones include `ALokiDropShip`, `ALokiDropPod`, `ALokiDropPodLaser`,
`ALokiDropPodImpactIndicator`, `ULokiDropPhase_PlayerStateComponent`, `ULokiRespawnComponent`,
`ULokiPlayerRespawnComponent`, `UComp_PC_LokiRespawnComponent`, `AFFAGameMode`, `ABarracudaGameMode`
and 28 modules of MOBA code. **The drop-phase and respawn machinery the project has been reverse-
engineering out of packed native code since S62 was readable script the whole time.**

The scan's conclusion also carried a recommendation — "**B′. Decompile the AS anyway … low marginal
value now**" — which is why nobody went back to it for ~26 sessions. That recommendation followed
correctly from the premise. The premise was wrong.

Two secondary reasons it stayed hidden: there are no `.as` source files anywhere in the install
(only the compiled cache), and the exe is VMProtect/Themida-packed, so the *script VM* was never a
natural thing to look for while fighting the native side.

---

## 2. The tooling, and how complete the decompile honestly is

### `tools/asdump/asdump.py`

Single file, stdlib-only Python 3, ~3,560 lines, standalone, ~0.8 s for the full corpus, output
byte-identical across runs.

```bash
cd "G:/git/Supervive Revival Project/tools/asdump"
python asdump.py                      # everything -> out/modules/ + out/_index.md
python asdump.py --validate           # self-check + census only, writes nothing
python asdump.py --module DropShip    # only modules matching a substring
python asdump.py --no-asm             # skip the disassembly appendix
python asdump.py --no-usmap           # don't name enum members
```

It reads the three caches, reconstructs 78 `.as`-shaped files laid out like real source (globals,
then each class with its properties and methods nested), and appends a **fully symbol-resolved
disassembly** to every function.

The opcode table is **not** copied from upstream AngelScript — the fork differs. It was extracted
byte-exact from the game binary's own `asBCInfo[256]` (RVA `0x084A22C0`) and `asBCTypeSize[22]`
(RVA `0x084B45A0`) in `dumps/merged.dump.exe`, and independently re-derived twice with 0 mismatches
across all 213 real opcodes on name, type and `stackInc`. Two independent implementations were built
from scratch and cross-judged; the merged tool is the better of the two plus grafts.

### Validation numbers (current, after this pass's merges)

```
PrecompiledScript.Cache  1,184,817 / 1,184,817 B parsed   UNACCOUNTED 0   (100.0000%)
Binds.Cache              5,764,301 / 5,764,301 B          UNACCOUNTED 0
Binds.Cache.Headers      2,050,287 / 2,050,287 B          UNACCOUNTED 0

modules 78 (asserted) · classes 110 · properties 600 · functions 1,463

bytecode   decoded exactly              1,463 / 1,463   100.00%
           structured to pseudo-code    1,463 / 1,463   100.00%
           36,293 instructions · RET count == function count · unmodelled opcodes: NONE
symbols    type pointers                4,283 / 4,283   100%
           factory/behaviour ids          440 /   440   100%
           call + global ptr operands   5,970 / 5,970   100%
           script-call id operands        862 /   862   100%
           member accesses              3,530 / 3,530   100%  -> real property NAMES
convention independent dword-depth audit 1,458 / 1,463    99.66%
output     78 modules · 16.6k pseudo lines · 38.8k disassembly lines
           4,023 local declarations (71.6% typed) · 112 enum members named
           0 dropped calls · 19 gotos in 5 functions · 5 `<?>` markers
```

Three of those are genuinely **independent** checks, not self-consistency:

1. **Byte accounting.** There is no magic number, chunk table or offset table anywhere in
   `PrecompiledScript.Cache`. Landing exactly on EOF with zero gaps and zero overlap is only
   possible if every field's order and width is correct.
2. **The dword-depth audit** is driven by the game binary's own `stackInc` table and shares no code
   with the lifter's symbolic stack. It rose 72.6% → 99.04% → 99.66% as real model errors were
   fixed (`?&` typeid dwords, enum width, `ALLOC`, script value-type returns) — each a corrected
   defect, not a tuned threshold.
3. **Call preservation.** Every call target recovered from raw bytecode was checked for presence in
   the corresponding pseudo-source: **0 of 3,286 missing**, later re-measured at 0 of 7,491. A
   decompiler that silently drops a call is the dangerous failure mode, so it is measured.

Fail-loud was verified by corrupting a **copy** of the cache: a flipped bool canary, a bad array
count and a bad string length each abort with a byte offset and a context hexdump. The parser never
resynchronises.

### Honest grade

**Declarations: A. 100% exact, read out of the cache, not inferred.** Class names and bases; every
property with its type and full `UPROPERTY` metadata including `Replicated` /
`ReplicationCondition` / `RepNotify`; every function name, return type, parameter types **and
names**, default-argument source text, and `UFUNCTION` flags including the `UnrealName` alias. That
alone is a complete header dump of the gameplay layer and needs no bytecode at all. Where this
document or the subsystem reports quote a signature, it is exact.

**Bodies: B / B+.** All 1,463 decompile to structured pseudo-source with named calls, named members,
string/`FName`/float literals, `if`/`else`/`while`/`switch`, `break`/`continue`, typed locals and
real `return` values. Zero calls are silently dropped. What holds the grade down:

- **No local variable names, ever, and no line numbers.** The shipping cache has `DeclaredAt == 0`
  and empty `LineNumbers` / `VariableInfo` for all 1,463 functions — the plugin guards them with
  `#if !UE_BUILD_SHIPPING`. Locals render as `vN` where N is the stack slot. **Permanent.**
- **No expression folding.** Output is close to three-address form because the bytecode is
  (`v12 = a; v14 = b; v12 = v12 - v14;`). Readable but verbose. Skipped deliberately rather than
  risk reordering side effects.
- **19 `goto` lines in 5 functions**, all inside computed (`JMPP`) switch tables. Correct labels and
  bodies, just not fully nested.
- **5 `<?>` markers** where a value crosses a control-flow join; closing them needs SSA/phi.
- **2 of 31 multi-return functions** emit fewer distinct `return` expressions than the bytecode has
  paths.
- **Statement order is bytecode order**, not source order.

**⚠ The one open correctness defect, and it is the dangerous kind.** The control-flow *structurer*
can place a **shared join block inside an `else` arm** when two conditional jumps target the same
label — the classic "two guard clauses fall into common code" shape. The result reads perfectly
reasonably and means the opposite of the code. Confirmed instance:
`ALokiGem::OnComponentBeginOverlap` renders as "only unowned gems ever pay out" when the real rule
is "the owning team may not collect, everyone else may". A scan for the risk shape (*a label reached
by ≥2 conditional jumps that is not the function's final instruction*) hits **46 of 1,463 functions
(3.1%)** — enumerated in `tools/asdump/PATCH-lifter-fixes.md`. The shape is necessary, not
sufficient, so not all 46 are wrong. **Every function quoted in the five subsystem reports was
hand-checked against its disassembly; functions in `out/modules/` that no report quotes were not.**

**The residual risk that would not announce itself** is argument accounting inside the lifter's
`_do_call`. A wrong-but-plausible argument list looks fine. Four classes of that error were found
and fixed during this work (`REFCPY`/`COPY` direction, float immediates printed as raw u64, the
value-register loads, and script value-type returns); a fifth cannot be ruled out. Concretely, before
one of the fixes, `Math::Lerp(1.0, this.LaserOpacityMultWhenSpread, ramp)` printed as
`Math::Lerp(v14, n"Final Opacity", v52)` — plausible, and wrong.

> **Working rule for anyone acting on this material:** the pseudo-source is a reading aid; **the
> per-function disassembly appendix in `tools/asdump/out/modules/` is ground truth.** Every operand
> there is named, including full callee signatures. Read it before you build a shim around a
> specific function.

### Tool defects found and fixed during this pass

Five, all found by reading output against its own disassembly. All are in the canonical
`asdump.py`; `out/` has been regenerated from the merged tool.

| # | defect | scale |
|---|---|---|
| 1 | `REFCPY` printed handle assignments backwards (destination is the pointer pushed **last**) | 116 sites |
| 2 | `COPY` printed struct assignments backwards, same cause | 235 statements across **42 of 78 modules**; the tell-tale `nullptr = <expr>;` went 32 → **0** |
| 3 | 64/32-bit float immediates printed as raw integers (`CameraPickupRadius = 13830554455654793216` is `-1.0`) | ~270 tuning constants; **every number quoted in these reports depends on this fix** |
| 4 | `LoadThisR`/`LDV`/`LDG`/… did not model the VM's value register, so by-reference member arguments printed stale junk | 24 call sites + 2 functions that were returning nothing |
| 5 | Script-declared **value types** not treated as returning on the stack, shifting every parameter name by one slot | 34 of 110 script types are `asOBJ_VALUE`; 20 of the 34 stack-returning functions had mis-named parameters — the independent depth audit rose **99.04% → 99.66%** on this fix alone |

Two more, fixed earlier in the merge: `FunctionTraits` bit 0 is `asTRAIT_CONSTRUCTOR`, not `const`
(bit 2 is `const`, verified 812/813 against the file's own independent `bIsConst` field); and enums
were sized as 2 dwords instead of 1, mis-attributing parameters in 10 functions, 7 of them in
`LokiDropPod.as`.

**Not fixed:** the structurer join-block bug (§ above). That is the highest-value remaining tool
work after the usmap supplement.

---

## 3. The 78-module map

Grouped by top-level directory. `fns` counts every compiled function record including generated
constructors, `StaticClass`/factory/`Spawn` boilerplate and delegate thunks, so it overstates the
hand-written surface — badly for delegate-heavy modules.

### `Barracuda/` — 28 modules, a complete MOBA mode → `docs/angelscript-barracuda.md`

10 classes, 340 functions, ~44 KB bytecode. Two-team lane-pushing MOBA: a phase machine over
`ERoundPhase`, a 300 s day/night cycle, lane creep waves with six respawn behaviours, jungle camps
with leash-and-reset, barracks/mega-creeps, hand-placed doubly-linked minion waypoints with
navmesh projection and stuck-rescue, three targeting components (lane creeps: minion → structure →
hero; towers: prefer minions, never switch off a live target, latch 5 s onto anyone who damages an
ally), a full DOTA-style item shop with a recursive recipe graph, and a complete gold/XP economy.

Modules: `GameMode/` (3) · `GameState/` (4) · `Components/` (8) · `Spawners/` (1) · `Minion/` (5)
· `Shop/` (7).

### `Core/` — 9 modules · `Character/` — 2 · `PlayerController/` — 3 · `GameState/` — 1 → `docs/angelscript-core-gameplay.md`

- `GameState/LokiGameState.as` — `ALokiGameState_AS` is **one property** (a UAV component default
  subobject), no methods, no replicated members. A useful negative result.
- `PlayerController/LokiPlayerController.as` — a UAV component, three parameterless delegates
  (`OnSneakPressed`, `OnSneakReleased`, `OnPracticeRespawnPressed`), three `NoOp` BP hooks.
  30 of its 44 function records are generated delegate plumbing.
- **`PlayerController/LokiPlayerCheats.as`** — 31 cheat entry points (20 client + 11 `NetServer`),
  entirely disjoint from the native cheat set S74 inventoried. Includes a working spawn-and-possess
  sequence (§5).
- `PlayerController/LokiDragCameraComponent.as` — drag-to-pan camera, writes
  `ULokiCharacterSpringArmComponent.CameraManualPanOffset` directly.
- `Character/LokiHeroCharacter.as` — `Abstract`; adds `SetbReplicates(true)`, one unreliable client
  RPC, one delegate. Thin.
- `Character/LokiHeroGroundIndicator.as` — hero shadow + ring decals.
- `Core/AimingVis/` (6 modules, ~33 KB) — a 195-function client-side aiming-laser subsystem, with
  per-hero subclasses (Huntress, HookGuy, Ronin) and 19 `NetMulticast` RPCs.
- `Core/Components/LokiMajorStatusEffectComponent.as`, `Core/LokiScriptUtility.as` — small helpers.

### `GameMode/DropPhase/` — 5 modules · `Airship/` — 1 · `GameMode/` — 1 → `docs/angelscript-dropphase.md`

`ALokiDropShip`, `ALokiDropPod` (102 functions, 22.9 KB — the largest single class in the corpus),
`ULokiDropPhase_PlayerStateComponent`, `ALokiDropPodImpactIndicator`, `ALokiDropPodLaser`. Plus
`ALokiAirship_AS` (a complete vehicle-combat model: collision damage, passenger ejection, roadkill,
fuel, phased regen) and `ULokiExoticLootComponent` (day-indexed exotic loot tables).

### `FFA/` — 6 modules → `docs/angelscript-ffa-bots.md`

`AFFAGameMode : ALokiDropInGameMode` (elimination switched off, no spawn-on-login),
`UFFABotSpawnerComponent` (hardcodes ten hero `PrimaryAssetId`s), `ULokiRespawnComponent` (the
director, on the GameMode), `ULokiPlayerRespawnComponent` (the timer, on the PlayerState, the only
replicated property in the set), `UComp_PC_LokiRespawnComponent` + `URespawnTimerWidget` (client UI).

### `UAV/` — 6 · `Armory/` — 3 · `Items/` — 3 · `Interaction/` — 1 · `DayNightController/` — 1 · `Content/` — 2 · `Minions/` — 1 · `UI/` — 2 · `MostWanted/` — 1 · `Vault/` — 1 · `Domination/` — 1 → `docs/angelscript-systems-rest.md`

- **UAV** = a timed, pulsing radar *reveal* — not a vehicle, not a mode. Six modules, complete in
  script.
- **Armory / shop** = the in-match economy: three wallet currencies, item recipe/tier/shard tree,
  purchase path with a 20% discount tag, a roaming shop that rerolls once per in-game dawn.
- **Items** = gems (second currency), the team-wipe deathbox, recommended-item highlighting.
- **Interaction** = the "usable"/interact state machine.
- **Most Wanted** = a spawnable bounty target with an attached quest.
- **Vault** = a destructible-door loot container a UAV can scan.
- **Domination** = a respawn mode; only its max-min-distance spawn picker is script.
- **Minions** = waypoint patrolling AI. **DayNight** = day/night hooks + 2 multicast cheats.
- **Content** = collapsing temporary floors, spline-driven moving trains. **UI** = 2 widgets.

---

## 4. What this CHANGES

Each item names the prior claim, where it was made, and what replaced it.

### 4.1 ★ OVERTURNED — "the Angelscript layer is thin; deploy/respawn is native C++"

**Claim** (`docs/session-74-routeB-as-native-split.md`, 2026-07-12): *"only 18 classes are
Angelscript … `ALokiDropPlane`, `ALokiDropPod*`, `Comp_PC_LokiRespawnComponent`, `AuthRequestRespawn`,
`CheckSetInitialRespawn`, `GetPlayerRespawnComponent` — none carry the `_AS` suffix … the
gamemode / round / spawn-select / drop-in machinery is NATIVE C++"*, therefore
*"B′. Decompile the AS anyway … low marginal value now"* and *"C. Accept the ceiling."*

**Reality:** 110 script classes, of which 67 are UObject-shaped without the `_AS` suffix.
`ALokiDropShip`, `ALokiDropPod`, `ALokiDropPodLaser`, `ALokiDropPodImpactIndicator`,
`ULokiDropPhase_PlayerStateComponent`, `ULokiRespawnComponent`, `ULokiPlayerRespawnComponent`,
`UComp_PC_LokiRespawnComponent`, `AFFAGameMode` and `ABarracudaGameMode` are all **script, and all
now decompiled**. `AuthRequestRespawn`, `CheckSetInitialRespawn` and `GetPlayerRespawnComponent` are
specifically named in that claim and are specifically script functions whose bodies are now readable.

**What survives:** there is no `LokiRoundGameMode` / `LokiGameMode` / `LokiDropInGameMode` script
class. The *round/match* game mode itself is still native. S74's narrow structural point holds; its
scope estimate and its route recommendation do not.

### 4.2 ★ UNBLOCKED — the "DROP IN, GEAR UP… LOADING…" overlay has two named handles

**Claim** (`docs/session-89-rpc-route-readiness-shim.md`, `docs/session-90-ab-loadingscreen.md`):
S89 proved `GetFeatureTogglesReady` is bit 6 of `[LokiGameState+0x5A0 = ServerAuthConfig +0xB3]`
and built `gft_ready_fix.dll` to flip it (11/11 verified). S90's four-config A/B then showed the
overlay is *not* the toggle carrier, *not* the shim's bit and *not* the possessed-pawn type — the
overlay follows the **`OnClientGameFeatureTogglesReady` event**, which was correctly identified but
treated as an unlocated symbol.

**Now located, from `Binds.Cache`:**
- **`OnClientGameFeatureTogglesReady` is a delegate property on `ALokiPlayerController`**, sitting
  beside `OnAnyClientGameFeatureTogglesReadyOrChanged`. Its character-side handler is
  `ALokiCharacter::FeatureTogglesReadyOrChanged()`. Find the property on the local PC and broadcast
  it, or call the character handler directly — instead of chasing a bit that only flips the query.
- **`ULokiTransitionWidgetManager::ClearMatchTransition()`** — a zero-argument bound `UFUNCTION`,
  reachable statically via `ULokiTransitionWidgetManager::GetLokiTransitionWidgetManager(WorldContext)`.
  A manager class whose entire public surface is `AsyncLoadMatchTransitionWidget` /
  `ClearMatchTransition` is exactly the thing that owns `WBP_UI_MatchTransition`.
- `ALokiPlayerController::IsUIReady_BP` / `UIReadySplit(EUIReady&)` (`0 Ready`, `1 NotReady`) is a
  second, separate readiness gate worth sampling live.

**Scope this honestly:** these are **signature-level findings from the bind table, not decompiled
bodies.** `Binds.Cache` stores declarations only. But both are `UFUNCTION`s, so both are callable
through the existing `ProcessInternal` primitive, and testing them is cheap.

### 4.3 ★ UNBLOCKED — `ELokiGameFeatureToggle` is fully enumerated, all 151 entries

**Claim** (`docs/session-88-toggle-payload-fixed-offset.md`, S88–S90): the toggle carrier was swept
with `-toggleseed` values (1, 75, 151) blind, with no idea what any index meant.

**Now:** all 151 members are listed, with one hard anchor **from decompiled bytecode** —
`ULokiPlayerControllerArmoryComponent::IsArmoryEnabled()` reads index **106**, and
`ELokiGameFeatureToggle::Armory` is the 107th member, which pins the whole positional list. Directly
relevant names: `TrainingBattleRoyale` (63), `BotsKeepMatchesAlive` (96), `BRAutomaticRespawns` (91),
`BRAutomaticRespawnsSoloMode` (92), `DeathmatchNotMaxLevel` (14), `DMEconomy` (27), `Missions` (25),
`EndOfGameFlowV2` (37), `ValidateConnectionSecret` (36), `IgnoreClientVersionDangerous` (2),
`SkipCosmeticFeatureOwnershipValidation` (69), `BotSkins` (66),
`SimplifiedCosmeticsOnDedicatedServer` (8).

**Caveat, stated plainly:** the member *names* come from `mappings.usmap`, and usmap v0 stores enum
members **positionally**. Index → behaviour is a name-only inference for every entry except
`Armory`, which bytecode anchors. Also note the Angelscript layer reads exactly **one** feature
toggle in all 78 modules — the rest of the toggle consumers are native or Blueprint.

### 4.4 ★ AUGMENTED — the cheat surface is ~50% larger than inventoried, and two things about it were wrong

**Claim** (`supervive-cheat-surface-inventory`, S74, `docs/session-74-cheat-enum-dump.txt`): the
shipping build keeps its whole cheat/debug surface; `LokiPlayerCheats` has 65 UFunctions, live-
enumerated.

**Addition:** that enumeration walked the *native* `ALokiPlayerCheats` UClass.
**`ALokiPlayerCheats_AS` is a script subclass with 31 further entry points** — 20 client-side
`BlueprintCallable` and 11 `NetServer` RPCs — **none of whose names appear in that dump or anywhere
under `docs/`**. Highlights: `AuthCheatUnlockFullArmory` (`GameState.SetArmoryFullyUnlocked(true)`),
`AuthCheatGrantGold` / `AuthCheatGrantGems` (literal `"Gold"`/`"Gems"` → `GrantWalletCurrency`),
`ConsoleCommandCheatAutoJump(Period)`, `AuthCheatExecuteUAV`, four Barracuda phase/spawner/day-night
cheats. Two more live on `ALokiDayNightController_AS`: `AuthCheatNightToDay` / `AuthCheatDayToNight`,
both `NetMulticast`.

**Correction 1 — they are not console commands.** Despite every one being named
`ConsoleCommandCheatXxx`, **zero of the 500 script UFUNCTIONs carry `Exec`** (measured:
`CanOverrideEvent` 471, `BlueprintCallable` 326, `BlueprintEvent` 226, `BlueprintOverride` 106,
`NoOp` 43, `BlueprintPure` 35, `NetMulticast` 23, `Static` 22, `NetServer` 22, `ConstMethod` 19,
`BlueprintAuthorityOnly` 16, `NetClient` 3, `Unreliable` 3, **`Exec` 0**). The *native* cheats do
carry `Exec`, which is why the project could reach those. The script ones must be invoked as
UFunctions — `CallBPGuarded` (S91–93), never a console.

**Correction 2 — the local cheats object is reachable** via the native static
`ALokiPlayerCheats::GetLocalLokiPlayerCheatsBP(UObject WorldContextObject)`, which S74 already
inventoried.

### 4.5 ★ ANSWERED — S100's "the ability-system carrier is missing"

**Claim** (commit `32ad985`, S100): *"hero owns no ability system, the CARRIER is missing."*

**The script layer names where the game itself looks, twice:**
`ALokiCharacter::GetLokiAbilitySystem_BP()` → `ULokiAbilitySystemComponent@` (used by
`ULokiMajorStatusEffectComponent_AS`), and `ALokiPlayerCheats::GetAbilitySystemComponent()` → the
same type. The cheats also give a complete, decompiled apply/remove round-trip
(`MakeEffectContext` → `MakeOutgoingSpec` → `ApplyGameplayEffectSpecToSelf` →
`HasActiveGameplayEffect` / `RemoveActiveGameplayEffect`) — a working template for granting any
`UGameplayEffect` to a hero from a shim. Consistent with commit `2921ac5` (S100b) having found the
native wiring entry point; this names the accessor from the game's own code.

### 4.6 UNBLOCKED — the S93 "SpawnPlane faults on absent level markers" wall has three bypasses

**Claim** (`docs/session-93-objectives-camera-deploy.md`): DropPlane `SpawnPlane` descent faults on
absent level markers — listed as a real deploy wall.

**Three documented override paths**, all bound `UFUNCTION`s:
`ALokiDropPlane::OverridePlaneLocations(Start, End)`,
`ALokiPlayerController::ServerOverrideDropPlaneLocations(Start, End)`, and the static
`ULokiDropPhaseDebuggingTool::OverrideDropPlaneLocations(WorldContext, Start, End)`. Plus
`ULokiGameModeDropPlaneComponent` carries `bUseOverrideLocations` +
`OverrideStartAngleDeg`/`OverrideEndAngleDeg`, and `GeneratePlanePoints` takes explicit defaults
(`CircleRadius = 42000`, `Height = 21000`, `MaxEndOffsetDeg = 50`).

### 4.7 NEW HYPOTHESIS — a movement path that is not the one S81 proved stalls the game thread

**Claim** (`docs/session-81-disconnect-characterized.txt`): `MODE_PLAYABLE`'s per-frame movement
pinned the game thread inside the `CharacterMovementComponent` chain (`AddMovementInput` in 41% of
freeze samples) → 20 s block → netdriver timeout.

**`ALokiPlayerCheats_AS::TickAutoJump` drives the hero through a completely different pair of native
entry points** — `ALokiCharacter::JumpActionStart()` / `JumpActionStop()` — on a plain `Tick`, with
an explicit press/release edge and a server-time period. That is an *input-action* path, not a
movement-input path. `ConsoleCommandCheatAutoJump(float64 Period)` arms it; `Period <= 0` disarms.
**Whether it avoids the S81 stall is untested** — but it is a cheap single-variable experiment the
project did not know was available.

### 4.8 NEW LEVER — camera control without view-target surgery

**Claim** (S93): camera fixed to top-down by spawning a `CameraActor` and re-asserting the view
target.

**`ULokiCharacterSpringArmComponent.CameraManualPanOffset` (FVector, world-space) and
`.bDynamicCameraPanEnabled` (bool)** are written directly by `ULokiDragCameraComponent::Tick`,
reached via `pawn.GetComponentByClass(ULokiCharacterSpringArmComponent::StaticClass())`. A lighter
lever on the game's own camera.

### 4.9 ★ NEW — two entire game modes the project's planning did not contain

Neither **FFA** (bot deathmatch, 6 modules) nor **Barracuda** (MOBA, 28 modules) appears anywhere in
the project's route planning, memory files or session docs. Both are now fully readable. §6
reassesses them against the current route.

### 4.10 ⚠ TOOLING CORRECTION with retroactive reach — `mappings.usmap` omits the Angelscript classes

`mappings.usmap` does **not** contain the Angelscript-declared classes. `BarracudaShop`,
`BarracudaGameMode`, `BarracudaGameStateComponent` and `BarracudaMinionSpawner` are all absent, while
their C++ neighbours (`LokiTower`, `LokiTowerDefenseGameMode`, `BarracudaPhase`) are present.

**Consequence:** CUE4Parse silently drops those properties when deserializing shipped Blueprints —
dumping `BP_GameMode_Barracuda`, `BP_GameState_Barracuda` or `BP_BarracudaShop` returns CDOs with
**no serialized values**. That is a *tool limitation, not evidence that the defaults are empty.*
**Any prior conclusion drawn from an empty CDO dump of an AS-derived Blueprint should be re-checked.**
The fix is in §8 and is the single highest-leverage next step.

### 4.11 Backend scope — unchanged, and now bounded

There is **not one HTTP or AccelByte touchpoint in any of the 78 modules**. Every reward path is
`GrantWalletCurrency` / `AuthGrantExperience` on the local player state. The in-match layer needs
nothing from `ags`. That both confirms the project's existing understanding and bounds it: the
backend surface is menu/account only, and no amount of backend work will move the in-match frontier.

---

## 5. The drop-in answer

The project's highest-priority open question was: *what actually happens during the drop-in
sequence, and why does the client sit behind "DROP IN, GEAR UP… LOADING…" with the world loaded
behind it?* Full detail in `docs/angelscript-dropphase.md`.

### The sequence is script, and it is complete

```
ALokiDropShip::SpawnDropPodForTeam(TeamIndex, SpawnLocation, LandingLocation)
  ├─ LokiGameplay::SpawnPoolableActorFromClassDeferred(TeamDropPodClass, FTransform(SpawnLocation), …)
  ├─ GetTeamDropLeader(TeamIndex)                          ← the failure point, see below
  ├─ ALokiDropPod::InitializeDropPod(team, PS, LandingLocation, bIsLeader, this, nullptr)
  ├─ FinishSpawningActor(pod, transform)
  ├─ RemovePlayerFromPlane(PS)
  ├─ ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable(PS, LandingLocation)
  ├─ ULokiPlayerDropPlaneComponent::MulticastOnDropPodLaunched(pod)
  └─ ALokiServerAnalyticsManager::AddTeamDropEvent(team, LandingLocation, PS)

ALokiDropPod::StartPodGameplay()   [BlueprintCallable, idempotent via bHasStartedGameplay]
  arms four named timers -> IntroSequence 6.5 s -> Descending -> OutroSequence 1.0 s
                            -> Destroying (destroy delay 1.5 s)
```

Descent is a **time-parameterised interpolation** — velocity is recomputed each tick so the pod
lands exactly when the control window expires. Every step is a `BlueprintCallable` `UFUNCTION`, so
the sequence can be fired whole or **stepped one call at a time** (`SetDropPodState`,
`OnIntroSequenceFinished`, `OnOutroSequenceStart/Finished`, `AllowPodSteeringStarted/Ended`,
`SpawnImpactIndicator`, `SpawnLaserIndicator`, `SpawnCrewPodQueue`, `QueueCrewForPodSpawn`,
`FinishDestroyPod`). **No backend is involved at any point.**

### The overlay is not the drop script

The seven drop-phase modules contain **no widget code at all**. Nothing there draws, holds or
dismisses `WBP_UI_MatchTransition`. This closes S90's remaining ambiguity from the script side and
redirects the work to the two named handles in §4.2 — the `OnClientGameFeatureTogglesReady` delegate
property on `ALokiPlayerController`, and `ULokiTransitionWidgetManager::ClearMatchTransition()`.
(Both signature-level. Both cheap to try.)

### Four concrete failure modes, ranked

1. **No drop leader → a pilot-less pod.** `GetTeamDropLeader` returns the first player state on the
   team with `IsSpawnTeamLeader() == true`, **else nullptr**, and that goes straight into
   `InitializeDropPod` as the pilot. With no leader: `SetPilotPlayerState(nullptr)` →
   `SetOwner(nullptr)` (the pod is relevant to no connection), `bIsLocalPlayerPilot` never true (no
   camera glue, no laser, no landing radius), and `UpdateCharacterLocations()` finds no pilot — so
   **the hero is never teleported to the landing point**. The drop "half-works" in exactly the way a
   loading-screen bug looks. **Fix: call `ALokiPlayerState::AuthSetSpawnTeamLeader()` on the local
   player state before spawning the pod.**
2. **Negative/unreplicated team index → the drop silently never starts.** `LokiBeginPlay` gates on
   `ULokiTeamComponent::GetTeamIndex() >= 0`; below that, `StartPodGameplay` is deferred to
   `OnTeamIndexChanged` and never fires. Checkable live with `tools/re/obj_by_class.py`.
3. **The hero stays hidden.** Un-hiding is **client-side script**:
   `UpdateDropPhaseHiddenActors()` runs each Tick while `bIsHidingDropPhaseHiddenActors`, and once
   camera Z ≤ `DisplayDropPhaseHiddenActorsHeight` (**10000**) it calls
   `ALokiPlayerController::FinishDropPhaseHiding()` — but **only for player states the rideable
   component reports as `PlayersInside`**. A hero teleported into the world without going through
   `AuthPlayerEnterWorldAttachedToRidable` is never un-hidden. `FinishDropPhaseHiding()` is a direct
   no-argument `UFUNCTION`; a shim can call it and skip the whole chain.
4. **A plain `SpawnActor` of the pod class skips the deferred-init window** that `InitializeDropPod`
   depends on. The game uses `SpawnPoolableActorFromClassDeferred` + explicit `FinishSpawningActor`.

### Two further facts that bear on the possession wall

- **There is a drop-phase camera pawn**: `ULokiGameModeDropPlaneComponent::CameraPawnClass`
  (`TSubclassOf<APawn>`). During the drop the player is expected to possess a *camera pawn*, not the
  hero — directly relevant to S71/S90. (Property exists; its use is native and unproven here.)
- **Exiting the pod is a movement-mode handoff, not a spawn**:
  `ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod(DropPodDirection, RiderIndex = -1,
  LaunchOverrideSpeed = -1)`, with a dedicated custom movement mode. That is the function that turns
  a pod passenger into a falling, controllable hero.

### And the largest single finding about the drop

**It is optional.** `AFFAGameMode` never touches `ALokiDropShip` or `ALokiDropPod`; it spawns
straight to a ground transform via `ALokiGameMode::SpawnPlayer`. `ABarracudaGameMode` does the same
(`SpawnPlayer(ps, transform, nullptr, false)`). The drop sequence is one game mode's opening, not the
engine's only way to get a player into a world.

---

## 6. The playable-match reassessment

Three candidate routes now exist where there was one. Compared honestly.

### Route A — client-side tutorial force-open (the current route)

**State:** furthest along by a wide margin. Real tutorial gamemode + gamestate, initializer Stage 0→3
finished, world rendered, phases 1→4, hero spawn/possess/teleport, exit-to-menu, objectives
completing, the lesson chain walking (WASD → LMB → Dash → Jump), camera fixed top-down, a visible
hero mesh proven via `AddComponentByClass` (S91–93).

**Structural advantage that still stands:** S90 established that
`TrainingQuest_Basics_Base.OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`, so **only a client
running `BP_LokiGameMode_Tutorial` as authority can complete an objective.** That is a property of
the tutorial content, and nothing in the Angelscript layer changes it.

**What this work adds to Route A:** the spawn primitive `ALokiGameMode::SpawnPlayer`, reached via
`ULokiRespawnComponent::Respawn(PS)`; the wisp spawn-and-possess reference sequence; `TickAutoJump`
as an alternative movement path; `CameraManualPanOffset`; `FinishDropPhaseHiding()`;
`GetLokiAbilitySystem_BP()`; the `OnClientGameFeatureTogglesReady` delegate.

### Route B — FFA bot deathmatch (new)

**For:** six modules, one class each, all decompiled. No zone, no team elimination, no match-end
condition to satisfy, and **it never touches the drop plane or drop pod in script**. Three
already-wired native entry points reach a live, mode-registered hero:
`ULokiRespawnComponent::Respawn(PS)` (`BlueprintCallable`, AS function id 84893),
`ALokiGameMode::SpawnPlayer` directly, and `ULokiPlayerRespawnComponent::AuthRequestRespawn` — a
`NetServer` RPC with **no `NetValidate` and no server-side gate**, callable from the client. Ten
confirmed hero ids that the shipped bot code is known to work with. Bots are self-contained native
`ALokiBotController` (personality/difficulty/goal/spell); the script layer only supplies the roster.

**Against — and this is decisive for "shortest path":**
- `AFFAGameMode : ALokiDropInGameMode`, so it **inherits the same drop-in round-phase machine** the
  project is already stuck behind. Every arming path is `server && IsCombatPhase && HasCreatedPlayerStarts`,
  i.e. `ERoundPhase::EGP_Combat (7)`. FFA does **not** bypass that gate; it bypasses the pod.
- **Nothing in any of the 78 modules ever calls `TrySpawnTeam` / `SpawnBot` / `MakeNewBotController`**
  (measured corpus-wide). The bot spawn *trigger* is C++ or Blueprint and was not found.
- **`BandageItem` and `ArmorItem` are null** in the script CDO — every respawn currently calls
  `SpawnActor(nullptr, …)` twice. They live in a Blueprint subclass that was not identified.
- **No FFA map was identified.** The project's known level list contains no `LVL_FFA`, and guessing
  one from a name was explicitly declined.
- One latent trap found in the code: `GeneratePlayerStarts` returns `true` even on zero hits,
  latching `HasCreatedPlayerStarts` with an empty array → `% 0` in `GetValidPlayerStart`.

**Cheapest real prerequisite:** ≥1 actor tagged **`SafeTeamSpawnPathfindingAnchor`** in the world
(the FName is verified against the cache's own `StaticNames[58]`). The tag scan **retries every
tick**, so spawning one tagged actor into a live world satisfies it at runtime.

### Route C — Barracuda MOBA (new)

**For:** every server-authoritative rule is readable source now, not packed native code. It needs no
drop plane, no drop pod, no DropPhase — both walls that ate multiple sessions are simply not on this
path. It is listen-server-friendly in exactly the way the project already exploits (`Loki::LokiIsServer`
+ `EGP_Combat`). The loop is self-sustaining with zero backend: spawners tick, creeps path, towers
shoot, gold and XP flow. **726 Barracuda assets ship in the retail paks** —
`BP_GameMode_Barracuda`, `BP_LokiTower_Nexus`, 9 shop loot tables, 51 DOTA-derived recipe folders,
17 per-hero recommended builds, a Favela architecture kit, and 40 announcer VO events including
"citadel under attack". Five shipped cheat commands drive the whole machine. The C++ side carries 34
`Barracuda*` attributes on `ULokiAttributeSet` — nobody threads a mode through the core attribute
set for a prototype.

**Against:**
- **The map does not appear to ship.** All 17 `.utoc` directory indexes were parsed (102,511 files):
  116 named maps, 7,184 world-partition cells, **none named or foldered Barracuda**.
  `LVL_Bracket_01` and `LVL_Battlefield_TG` are unverified candidates only.
- Lanes are **not procedural** — hand-placed waypoint chains with explicit `TowardTeam0`/`TowardTeam1`
  links, hand-placed spawners with authored `FMinionWave` compositions, towers, barracks, fountains.
  Recreating that is a genuine authoring job.
- Every designer-tuned array lives in a Blueprint CDO that **currently cannot be read** (§4.10).
- The win condition and tower-destruction bookkeeping are Blueprint bytecode — a separate decompile.
- It is late-prototype code: `SplitBetweenLastHitterTeam` unimplemented, `LastHitGoldBonus` unread,
  three inverted-branch bugs, a suspect `Lerp` argument order.

### Recommendation

**Keep Route A (tutorial force-open) as the primary. Do not switch.** It is closest to a playable
result, its structural advantage (`BlueprintAuthorityOnly` objectives) is unaffected by anything
found here, and this work hands it five concrete new levers rather than a reason to restart.

**Harvest FFA rather than adopting it.** Its real value to the project is not the mode — it is
`ULokiRespawnComponent::Respawn(PS)` → `ALokiGameMode::SpawnPlayer`, the game's own "spawn a real,
mode-registered hero at a ground transform" primitive, which the tutorial route has been
approximating by hand since S68. Use it *inside* Route A. Treat "run FFA end to end" as a
second-order goal blocked on an unidentified map and an unidentified bot-spawn trigger.

**Park Barracuda until the usmap supplement lands.** It is the highest-ceiling target — a complete,
self-sustaining, backend-free game loop — but its blocker is a level-authoring problem, not a
reverse-engineering one, and its tuning data is unreadable until §8.1 is done. Reassess after that.

**Do these three first — they are cheap, and they attack the wall that is actually in front of you:**

1. Broadcast `ALokiPlayerController::OnClientGameFeatureTogglesReady` (or call
   `ALokiCharacter::FeatureTogglesReadyOrChanged()` on the local hero), and separately try
   `ULokiTransitionWidgetManager::GetLokiTransitionWidgetManager(WCO).ClearMatchTransition()`.
   Single-variable, both through the existing `ProcessInternal` primitive.
2. Call `ALokiPlayerState::AuthSetSpawnTeamLeader()` before any pod spawn, and
   `ALokiPlayerController::FinishDropPhaseHiding()` on the local PC if a hero is invisible.
3. Read `WispHeroClass` / `WispControllerClass` off the live `ALokiPlayerCheats_AS` CDO — that gives
   a hero class and an AI controller class **the game itself is willing to spawn**, with no guessing.

---

## 7. Game-design data recovered

The project previously had essentially no in-match numbers. All of the following are decoded from
constructor bit patterns or bytecode immediates — **they depend on the float-immediate fix (§2, tool
defect 3)**, without which they printed as raw u64 integers. Values that live in Blueprint CDOs are
*not* here (§8).

### Drop phase
Intro 6.5 s · steering window 5.5 s · outro 1.0 s · destroy delay 1.5 s · launch speed 2500 uu/s ·
steer budget 7500 uu over a 6.5 s window (≈1154 uu/s) · crew-pod separation 1000 uu over 1.0 s with
±22.5° fan-out · detach hold decaying 2.0 s → 0.5 s · un-hide camera height 10000 · pod-kick scatter
±150 uu · plane path defaults `CircleRadius 42000`, `Height 21000`, `MaxEndOffsetDeg 50`.

### UAV (radar reveal)
Life 11 s · initial delay 1 s · pulse period 5 s · blink 0.2 s · position inaccuracy 1500 uu
(`VRand() * RandRange(0, 1500)`) · enemy clustering radius 2000 uu · vault scan range 20000 uu ·
alert cooldown 25 s. Three pulses per UAV; each mark lasts `Period − BlinkDuration` = **4.8 s**.
Beaten by `IsInvisible() || IsInBrush()` or a team-wide `Immunity.UAV` tag (which fires a
`GameplayCue.Effect.UAVBlocked` back at the defenders). **`State.UAVUpgraded` on any living teammate
mutates the config mid-flight** to `bShowIndividuals = true, bShowTeam = true, InaccuracyDistance = 0`
— exact per-player positions.

### In-match economy
Currencies `"Gold"`, `"Gems"`, `"Shards"`. `ECurrencyGrantReason` = `Misc(0), Treasure(1),
MonsterKilled(2), DroppedByAlly(3), DroppedByEnemy(4), Refund(5)`. Item price on
`ALokiBaseItem::ShopkeeperGoldPrice`. **Armory purchase discount ×0.8** when the buyer holds
`Item.ShopDiscount.DiscountApplied` (literal `0x3FE999999999999A`). Purchase order is spawn →
inventory-add → *then* `ConsumeWalletCurrency`. Armory items have **6 star tiers (0–5)**; the
menu-side XP→star mapping thresholds are **2 and 5** (and only ever produces 0–2 — an unexplained
mismatch). The roaming shop rerolls its stock **once per in-game dawn**. Deathbox: a game-mode ratio
of the victim's gold becomes a physical item, placed by **10** navmesh attempts at **250 uu**
(1000/5000 projection, −90 uu fallback). Gems: **×2** multiplier, **400 uu** pickup radius, **75 uu**
rest height.

### FFA
Respawn timer **10 s** · `AuthGrantLevel(15)` on first spawn only · **3× bandage + 1× armor** every
spawn · `ResetAllCooldowns` every spawn · bot team indices start at **4**
(`GetNextTeamIndex → SpawnedTeamCount + 4`) · `ShouldTeamBeEliminated → false` unconditionally ·
`GracefullyShutdown("AllPlayersDisconnected", 0)` when the human count hits zero. Spawn points are
actors tagged **`SafeTeamSpawnPathfindingAnchor`**, round-robin. Ten hardcoded bot heroes:
`assault, firefox, freeze, sniper, flex, hookguy, rocketjumper, Storm, BurstCaster, BountyHunter`.

### Barracuda
Day/night cycle **300 s**, match opens at **night**. Gold is **last-hit only**; XP is **shared within
1500 uu**. Hero bounties fire on the **knock** (`ELivingState::Knocked`), not the death, with a
**30 s** per-victim anti-farm cooldown. The victim drops **20%** (`GoldLossOnDeath`) of carried gold,
split among participants within **2500 uu**. Killer gets `GoldBountyPerCurrentStreak[victimStreak]`
shutdown gold. XP = `(victimXP·0.2 + 75 + streakBonus) · mercyOrUnderdogCoeff / N`, where
`streakBonus = victimLevel · streak · 15` when streak > 2, `UnderdogHeroKillXPBonusPerLevel = 0.25`
per level when you are ≥2 levels behind, scaled by a share-back bonus when N > 1. Shop sell value
**90%**. Jungle leash **500 uu / 30 s** then teleport home. Tower rally radius **2000 uu**; tower
aggro latches **5 s** onto anyone who damages an ally. Wave spawning staggered **0.5 s per unit**.
Six creep respawn behaviours: `AlwaysSpawn, ReplaceSpawns, SkipSpawnWhenOldExists,
StartRespawnTimerAfterDeath, AliveAtNight, AliveDuringDay`. Spawner taxonomy tags:
`Static.Barracuda.Spawner.Creep` (lanes) vs `Static.Barracuda.Spawner.Neutral` (jungle).
**The 2500 uu and 1500 uu radii are hard-coded literals, not properties — no designer knob.**

### Airship (vehicle combat)
Head-on collision at angle ≤ 30°, relative speed 900→2000 mapped to 100→150 damage, front/rear
multiplier 0.1→4.0 over impact angle 0→180°, 1 s per-target cooldown. Passenger ejection above
600 uu/s relative speed, impulse 60000→600000 XY plus +6000 Z. Roadkill 500→5000 damage over
0→1000 uu/s, ×0.8 vs minions, ×1.6 vs destructibles, `Immunity.AirshipRoadkill` exemption, 0.3 s
cooldown. Fuel: `NumSecondsOfFuel` 180 s (60 s boosting), 1 s tick, applied as a `Generic.Scale`
gameplay effect. Health regen in three damage phases at 0.33 / 0.66 strength driving
`Effect.Airdoo.Damaged.Smoking` / `.onFire`, healing up to 30 HP per 1 s tick.

### Misc
Interaction: 0.2 s cooldown, 0.5 s input buffer. Temporary floors: 4 × 1.0 s cycle. Trains:
1000 uu/s. Patrol AI: 10° facing tolerance, 100 uu acceptance radius.

---

## 8. What is still not recovered, and what it would take

### 8.1 ★ Blueprint CDO values — and the fix is pure offline tooling

**The single largest remaining gap.** Enormous amounts of designer-authored data are `EditableOnDefaults`
properties whose values live in Blueprint CDOs, not in the script cache: `BarracudaPhases`,
`RespawnTimePerLevel`, `GoldBountyPerCurrentStreak`, `MercyHeroKillXPCoefficients`,
`MinionSplitXPBonuses`, `DragonRewards`, every `FMinionWave`, `MainObjectiveClass`, `ItemLootTables`,
FFA's `BandageItem` / `ArmorItem` / `OnSpawnEffect` / the concrete `URespawnTimerWidget` subclass,
`WispHeroClass` / `WispControllerClass`, the entire per-hero `LaserSettings[]` table, and every
Huntress range.

**Why they read as empty today:** `mappings.usmap` does not contain the Angelscript-declared classes
(§4.10), so CUE4Parse silently drops those properties. **This is a tool limitation, not evidence.**

**The fix:** `asdump.py` already parses the exact property list, type and order for all 110 AS
classes. **Emit those as a usmap supplement.** That would let CUE4Parse read *every* AS-derived
Blueprint CDO in the game in one stroke — unblocking Barracuda's entire tuning table, FFA's item
classes, and the drop phase's Blueprint layer simultaneously. **This is the highest-leverage next
step in the whole area, it is pure offline work, and the schema is already in hand.**

### 8.2 Permanent, at any effort

- **Local variable names, line numbers, comments, original formatting, expression nesting.** The
  plugin guards `DeclaredAt` / `LineNumbers` / `VariableInfo` with `#if !UE_BUILD_SHIPPING` and all
  1,463 functions have them empty. The data was never written. Locals are `vN` forever.

### 8.3 Out of scope for a script decompiler (each is a separate project)

- **Native C++ bodies.** `Binds.Cache` stores **declarations only**. Every claim in these reports
  about `AuthLaunchDropPodForTeam`, `ClearMatchTransition`, `FinishDropPhaseHiding`'s internals,
  `CameraPawnClass`, `AuthBeginGlideDiveFromDropPod`, `ALokiBotController`, the plane's own movement
  and the ~110 recovered native signatures is **signature-level and flagged as such**. Recovering
  bodies means native disassembly against `dumps/merged.dump.exe`.
- **Blueprint bytecode.** Every `NoOp` `BlueprintEvent` in script is a content extension point whose
  real body is Kismet in a `.uasset`: `ShouldGameEnd`, `OnAuthTowerDestroyed`, `BP_StartPodGameplay`,
  `RollNewShopItem()` (the shop's actual loot roll), `AuthSellItem_BP`, `GetArmoryEvolveChoices`,
  and dozens more. `tools/extractor/` has a `bpdump` mode with `ReadScriptData`; decompiling Kismet
  is its own project.
- **Per-item numbers.** Every item's `ShopkeeperGoldPrice`, tier costs, recipe graphs and XP-to-tier
  tables live in packed data assets. Extractor work, not script work — and gated on §8.1.

### 8.4 Specific unknowns worth naming

- **The Barracuda map.** No shipped `.umap` is named or foldered Barracuda; no world-partition cell
  set belongs to one. Settle it by dumping `LVL_Bracket_01` / `LVL_Bracket_Copy_9_26` /
  `LVL_Battlefield_TG` actor lists and grepping for `ABarracudaMinionSpawner` /
  `ABarracudaMinionWaypoint` / `BP_LokiTower`.
- **The FFA map**, and **what triggers bot spawning and how many** (`TrySpawnTeam` / `SpawnBot` /
  `MakeNewBotController` are never called from any of the 78 modules).
- **How the respawn components attach** to PlayerState / PlayerController. The
  `ALokiGameMode::Additional{Controller,PlayerState,TeamState}Components` arrays are the obvious
  mechanism, but that is inference from a bound property name.
- **Which `ERoundPhase` value opens the drop.** `EGP_SpawnSelect (4)` is the obvious candidate from
  the name; no decompiled code in the drop modules reads `ERoundPhase`, so it is a naming inference.
- **Who broadcasts the delegates** — no script module broadcasts `OnSneakPressed`,
  `OnSneakReleased`, `OnPracticeRespawnPressed` or `OnBiomeTouchUnlocked`.
- **What calls `ExecuteUAV`** — it is `BlueprintAuthorityOnly` and nothing in script calls it. The
  UAV item/ability is Blueprint.
- **`FunctionTraits` bits 5/13/18**, class `Flags`, `CodeHash`, `ShadowType`/`DerivedFrom`,
  `OldTypeId`, the 14 unbalanced value-type constructors, the exact fork revision, and `JMPP`
  lowering — all listed in `FORMAT.md`'s explicit "what is still unknown" section.
- **`ELokiUsableInteractionRepressBehavior`** and one `ECollisionChannel` ordinal (18) are not in
  `mappings.usmap` under any tried name; reported as raw integers.
- **The `Swordfish` variant.** `BP_GameMode_Barracuda_Swordfish` / `BP_GameState_Barracuda_Swordfish`
  exist alongside a family of `*_Swordfish` exotics and loot tables. Looks like a separate
  playlist/season codename. Unresolved.

### 8.5 Tool work, in priority order

1. **Emit a usmap supplement for the 110 AS classes** (§8.1). Highest leverage by a wide margin.
2. **Fix the structurer join-block bug** (§2). 46-function audit set is in
   `PATCH-lifter-fixes.md`; until then that list is where a wrong reading can hide.
3. Close the 5 `<?>` markers and the 2 residual multi-return functions (needs SSA/phi).
4. Copy propagation / expression folding for readability — deliberately skipped so far to avoid
   reordering side effects.
5. Housekeeping: `tools/asdump/out/` is **29 MB of generated output and is currently untracked and
   not git-ignored.** Decide whether to ignore it or commit it before the next `git add`.

---

## Appendix — reproducing everything in this document

```bash
cd "G:/git/Supervive Revival Project/tools/asdump"
python asdump.py --validate                 # the numbers in §2
python asdump.py                            # regenerate out/modules/ (78 files, ~0.8 s)
python asdump.py --module DropP             # one subsystem
python asdump.py --no-asm --out out_noasm   # bodies only, no disassembly appendix
python dropphase_binds.py                   # the native bind surface under the drop phase
```

Source caches (read-only, never modified — mtimes still 2025-12-17):

```
G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\PrecompiledScript.Cache
G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\Binds.Cache
G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script\Binds.Cache.Headers
```
