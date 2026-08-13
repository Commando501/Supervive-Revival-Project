# FK-1 — SETTLED: the Angelscript layer is large, AOT-compiled, callable, and its data is now readable

**S113, 2026-08-09. Offline + one read-only RPM probe against a live menu process. Zero launches consumed.**

FK-1 (`docs/ignorance-map-s101.md:141`) recorded, from `docs/session-74-routeB-as-native-split.md`
and frozen into commit `19db6a2`:
> *"★ THE KEY FINDING — only 18 classes are Angelscript"* … *"The native C++ deploy/round core is
> the irreducible blocker"* → **"C. Accept the ceiling."**

**Verdict: REFUTED, and the ceiling is FALSE.** But the real wall turned out to be somewhere else
entirely, and it is now named for the first time.

---

## 0. TL;DR

| question | answer |
|---|---|
| Is the AS layer thin? | **No.** 78 modules · **110 classes** · 1,463 functions · 100 % of bytecode decoded (S101 `tools/asdump`) |
| Size of S74's undercount | **9.0×** (81 ÷ 9), **not** the 4.3× the register states — see §2 |
| Is the round game mode native? | **Yes** — confirmed on declarations, 3 independent instruments, bidirectional controls |
| Is that a ceiling? | **NO.** Every member is a named UFUNCTION/UPROPERTY reachable by the S55 primitive, and **the phase lives on `ALokiGameState` with a public `AuthSetCurrentPhase` setter** |
| Is the script layer interpreted? | **No — it is AOT-transpiled to C++ and compiled into the exe** ("StaticJIT"). 1,459-row symbol table recovered |
| Is script callable? | **Yes, by the existing S55 recipe unchanged.** ⚠ `Func != ProcessInternal`, so the PI hook never fires for a script UFunction |
| Can we read AS-derived Blueprint data? | **Yes, now.** usmap supplement shipped; **263 property values newly decoded** |
| **So what is the real wall?** | ★ **Four server-authority C++ functions are EMPTY STUBS in the shipping client** — §5 |

---

## 1. The refutation (S101, recorded here because the register never caught up)

`tools/asdump/` (built S101, 33 files, 312 decompiled outputs) parsed
**1,184,817 / 1,184,817 bytes, 0 unaccounted**: 78 modules · 110 classes · 600 properties ·
1,463 functions · 36,293 instructions. Bytecode decoded **1463/1463 (100 %)**; member accesses
3,530/3,530 and call targets 5,970/5,970 resolved to names.

⚠ **The register entry is stale in a way that misleads.** Its "Cheapest experiment" still ends
*"Then decide whether an Angelscript bytecode disassembler is worth building (none exists in
`tools/`)."* It was built two sessions later. Anyone reading FK-1 today is told to decide on a
tool that already shipped.

---

## 2. The error was a NON-SEQUITUR, and the correction inherited both the fallacy and the miscount

S74's method (`session-74-routeB-as-native-split.md:12-21`):
```
:12  Distinct `*_AS` classes in the cache (18 total):
:17  **There is NO `LokiRoundGameMode_AS` / `LokiGameMode_AS` / `LokiDropInGameMode_AS` / deploy AS class.**
```

**Fault 1 — the inference is invalid regardless of the count.** The `_AS` suffix marks only script
classes that **shadow an identically-named native parent**. *"No `X_AS` exists"* therefore carries
**zero information** about whether `X` is implemented in script. A better grep would not have
saved S74.

**Fault 2 — the count was a double-count. [MEASURED]** The 18 tokens are **9 classes × 2 forms**
(bare + `__StaticType_`), with no unpaired token. So the true undercount is **81 ÷ 9 = 9.0×**, not
the **4.3×** the register states. **FK-1's own correction carried forward the miscount it was
correcting.**

**Fault 3 — the correction reused the discredited inference.** FK-1's "Surviving nuance" reads
*"There is still no `LokiRoundGameMode_AS` / `LokiDropInGameMode_AS`, **so** the BR round gamemode
may genuinely be native."* That is Fault 1 restated inside the fix.
⚠ Note `memory/supervive-angelscript-layer` is phrased **correctly** (*"no … **script class**"*).
**The two artifacts disagree in strength and the weaker one is the one steering sessions.**

⇒ Three layers: bad instrument → invalid inference → miscounted correction.

---

## 3. The round game mode — conclusion confirmed, reasoning struck, ceiling refuted

**`LokiDropInGameMode` is a referenced NATIVE base class, not a script class. [MEASURED]**
`__StaticType_ALokiDropInGameMode` = **0**; `__StaticType_AFFAGameMode` = 3. The cache record at
`0x07503a` reads `ALokiDropInGameMode · /Script/Loki.LokiDropInGameMode · __StaticType_AFFAGameMode
×2` — structurally identical to the control at `0x020452`. It sits in the **base** slot.
`binds_headers.csv:4217` → `Source/Loki/GameModes/LokiDropInGameMode.h`.

**Three independent instruments, controls run both directions** (binds header map → `Source/Loki/**.h`;
usmap supers; UTF-16 `/Script/Loki` names in the merged dump). Script classes score 0/0/0 and appear
only in the script cache; native ones score 1/1/1.

```
AGameModeBase → ALokiGameModeBase → ALokiGameMode (54 props)
                                      ├── ALokiRoundGameMode (22)  → BattleRoyale / Tutorial /
                                      │                               TowerDefense / Defusal /
                                      │                               Domination / LastMan / TugOfWar
                                      └── ALokiDropInGameMode (0)  ← sibling, NOT a round mode
```
Only **2 of 81** script-declared UClasses are game modes: `AFFAGameMode` (base DropIn) and
`ABarracudaGameMode` (base TowerDefense). There is a **third tier**: `BP_GameMode_Barracuda_C`
inherits `/Script/Angelscript.BarracudaGameMode` — **BP → Angelscript → native**.

### ★ The ceiling is FALSE
Every member of the round mode is a named UFUNCTION or UPROPERTY — `GoToPhase`, `CompleteRound`,
`RestartRound`, `SpawnPlayer`, `ShouldGameEnd` — all present as FNames in the binary and all
reachable by the existing native-call primitive. **Native ≠ unreachable.**
Decisively: **the phase is not owned by the game mode at all.** It lives on `ALokiGameState` with a
public **`AuthSetCurrentPhase`** setter, so the `EGP_Combat` gate prior work called *the* blocker
has **two** write paths.

**"DropIn" ≠ drop phase** — it is drop-in/drop-out FFA churn; `AFFAGameMode` never touches the drop
phase (joined only by `ModeSupportsDropPlane()`). **The tutorial already runs the round mode**:
`BP_LokiGameMode_Tutorial_C` is a `LokiRoundGameMode` descendant assembled from 7 BP components
(`LogLokiRoundGameMode: Setting Phase to 1` in the logs). Native `ALokiTutorialGameMode` is
vestigial — 0 props, zero references anywhere.

---

## 4. ★★ The layer is AOT-compiled C++, not an interpreter — and it is callable

**SUPERVIVE's UE-Angelscript fork does not ship an interpreted script layer.** It **AOT-transpiles
every Angelscript function to C++ and compiles it into the shipping exe** ("StaticJIT"). MEASURED:

- The transpiler's codegen templates are plaintext **UTF-16** in `.rdata` (`0x084DB000–0x084ED800`),
  including `static void %s_ParmsEntry(FScriptExecution&, void* Object, void* Parms)` (`0x084EB710`)
  and `AS_FORCE_LINK static const FStaticJITFunction %s_Register(0x%xu, &%s_VMEntry, %s,
  (asJITFunction_Raw)&%s);` (`0x084EB7E0`). ⚠ **UTF-16-only — an ASCII scan misses all of them.**
- `PrecompiledScript.Cache`'s `DataGuid` `95a76d41-99c2-a148-89f7-1e3269f88eeb` is a compile-time
  literal in `.text` at RVA `0x00F44BE0` ⇒ the transpiled code was generated from **this exact
  cache** and the runtime match check passes.
- **1463/1463** cache function Ids appear as `mov edx,imm32` in registration stubs calling
  `FStaticJITFunction::ctor` (`0x048FE510`). **Control: 0/4000 random ids.** GlobalRefs 187/187;
  control 0/4000.
- **A complete 1,459-row symbol table** was recovered: script function → raw / `_VMEntry` /
  `_ParmsEntry` RVAs. Bodies live in `.text 0x059128B0–0x05A7F070` (1.42 MB).

**Dispatch anatomy (from disassembly).** Three entry points per function; `_ParmsEntry` reads args
from a flat block using UE's `Align(off, alignof(T)); off += sizeof(T)` packing and writes the
return at `ReturnParmOffset` — **that is `ProcessEvent`'s contract and nothing else in UE has that
shape** (verified on `UBarracudaLaneComponent::SetLaneIndex` `0x059E2900` + a 2-param case). The
script corpus itself dispatches a script UFUNCTION via `FindFunctionChecked` + `ProcessEvent`.

⇒ **Callable by the existing S55 recipe unchanged** (mechanism named; the `Func` value itself is
INFERRED). **Corollary: `Func != ProcessInternal`, so the PI hook never fires for a script UFunction.**

### ⚠ Two traps this closes
- **The register's own proposed experiment is a trap.** §4.2 item 8 suggests *"print the owning
  class of every PI-dispatched UFunction for 5 s."* That returns **zero Angelscript classes in the
  world where they are perfectly callable.** Its null is uninformative and would very likely be
  filed as "we cannot observe Angelscript". **Use it only as a negative control.** *(This is the
  second time this session that the map's own prescribed experiment would have manufactured a
  false-known — the first was FK-11's `-LogCmds`.)*
- **`ALokiGameMode::SpawnPlayer` and `ULokiBotSpawnerComponent::SetSpawnableBots` are NOT
  Angelscript.** They are C++ UFunctions that script merely `CALLSYS`es. Same for
  `ULokiGameplayStatics::RespawnPlayer`.

### ★ FK-6 re-grade
`ALokiPlayerCheats_AS` is a **separate script-generated UClass** from the C++ `ALokiPlayerCheats`
that FK-6 closed on (`AddCheats = ret 0`). It carries **32 UFUNCTIONs with compiled native bodies** —
`AuthCheatGrantGold`, `AuthCheatUnlockFullArmory`, `AuthCheatExecuteUAV`, wisp spawners. `Exec == 0`
across all 500 script UFUNCTIONs (independently corroborating "console Exec = 0/500") — **the
console cannot reach them, but the thunk can.**
★★ And **a direct `Func` call bypasses `ProcessEvent`'s net routing**, so the **22 `NetServer`
script functions run locally regardless of authority.**

---

## 5. ★★★ The REAL wall, named for the first time: four server-authority functions are empty stubs

> ⚠ **S115 CORRECTION — column 2 is the exec THUNK (real code). The bytes below are the IMPL, at a
> different RVA that the original table never printed.** Re-measured in **both** dumps —
> see `docs/fk1-stub-claim-recheck.md`. **The finding STANDS**; only the address bookkeeping was
> ambiguous, and that ambiguity read as a hard measurement conflict for a full session
> (`docs/fk13-console-exec-settled.md` §6.1, now resolved). The IMPL column below is new.

Measured at byte level in `dumps/merged.dump.exe`, coverage-guarded, with controls
(`scratchpad/stub_census.py`; its resolver validated **4/4** against independently measured live
thunk addresses). ⚠ `stub_census.py` was never committed and is **gone** from the tree and from git
history; the S115 re-measurement instruments are `scratchpad/stub_recheck{,2,3,4,5,6}.py`:

| function | exec thunk (real code) | **IMPL** | impl body |
|---|---|---|---|
| `ALokiGameMode::SpawnPlayer` | `0x534C070` (478 B, 115 insn) | **`0x0F7EB50`** | **`xor eax,eax; ret`** = `return nullptr` |
| `ALokiPlayerState::AuthSetSpawnTeamLeader` | `0x5254180` ⚠ **91-way ICF, NON-IDENTIFYING** (7 insn `P_FINISH; jmp`) | **`0x0F7EC20`** | **`ret 0`** (`c2 00 00`) |
| `ALokiTeamState_TeamOnly::SetDropLeader` | `0x2C2CE30` ⚠ **23-way ICF** (133 B, 34 insn) | **`0x0F7EC20`** | **`ret 0`** |
| `ALokiDropPlane::OverridePlaneLocations` | `0x53372A0` (238 B, 53 insn) | **`0x0F7EC20`** | **`ret 0`** |

⚠ The original table's *"58 callers"* / *"4,784 callers"* counts were real census quantities but
attributed to the wrong rows. Measured S115: **58** exec thunks fold to `0x0F7EC20`, **15** to
`0x0F7EB60`, **5** to `0x0F7EB50`. The empty-impl **base rate is 1.2 % (78 / 6,669)**, so this is
informative, not ambient — which is the load-bearing part of the claim.

All four are server-authority functions — most likely **`WITH_SERVER_CODE`-stripped**. This gives
the project's long-standing "server-authoritative deploy" wall a **mechanism** instead of a
hypothesis, and explains why ~7 spawn attempts across S68/S74 failed for apparently different
reasons.

### It also closes the `AvatarActor = NULL` question
Disassembly-verified in `FFA/LokiRespawnComponent::Respawn`:
```
GetLokiGameMode → ALokiGameMode::SpawnPlayer(PS, Xf, StartSpot, bEnsure)
                → GetLokiAbilitySystem_BP() → MakeEffectContext → ApplyGameplayEffectSpecToSelf
```
The character is null-checked (`CmpPtrNull v6`); **the ASC is not.** `ABarracudaGameMode` repeats
the pattern. ⇒ the design routes the entire GAS bind through `SpawnPlayer` — **and the shipping
client does not contain it.** The tutorial route's `RM_SPAWNPOSSESS` (`SpawnDefaultPawnFor` + the
hand-built S103 carrier) is a re-implementation of `SpawnPlayer`'s insides, which is exactly why
`AvatarActor` is NULL.

**Script never binds an ASC. [MEASURED, complete enumeration]** `InitAbilityActorInfo`,
`SetAvatarActor`, `RefreshAbilityActorInfo`, `GiveAbility`, `InitStats`, `AddAttributeSetSubobject`,
`TryUpdateAbilitySystem`, `ActivateAbility`: **0 hits** across the corpus against **4 passing
positive controls**. Corroborated by `Binds.Cache` (49,288 members — the only bound avatar
*function* anywhere is the getter `GetAvatarActorFromASC`) and by the live UFunction dump
`docs/session-100-gas-api-dump.txt` (663 UFunctions across 5 relevant classes, no setter). **Zero AS
classes derive from any ability/spell/effect/attribute type** — the AS base histogram is
22×`UActorComponent`, 7×`UUserWidget`, 7×`AActor`, plus Loki natives. Abilities are not authored in
script.

### ⇒ The synthesis that matters
**The C++ authority functions are stripped; the SCRIPT authority functions are AOT-compiled into
the client and callable, and a direct thunk call bypasses net routing (§4).** So the deploy/respawn
path is not closed — it is closed *through the C++ door* and possibly open *through the script
door*: `ULokiRespawnComponent::Respawn` (`0x5A6AC40`), `ULokiPlayerRespawnComponent::AuthRequestRespawn`,
`ALokiDropShip::SpawnDropPodForTeam` (`0x597E730`), the `ALokiDropPod` steppers,
`UFFABotSpawnerComponent::BeginPlay`.

### Leader hypothesis: half confirmed, actionable half dead
`GetTeamDropLeader`'s nullptr path is **real** (`FreeNullV8 v30` explicitly nulls the return; the
second loop provably stores nothing; the consumer passes it on unchecked). **But the proposed fix
`AuthSetSpawnTeamLeader()` has no body, and neither does its fallback `SetDropLeader`.** It was also
never the binding constraint: `SpawnDropPodForTeam` bails on `TeamDropPodClass == nullptr` *before*
ever calling `GetTeamDropLeader`. **This is a live session the project would otherwise have spent.**

One genuine escape hatch: **`ALokiCharacter::SpawnAndMoveLokiCharacter_BP`** — static, takes an
explicit hero class, undocumented anywhere in `docs/`, body in a decrypt gap ⇒ **unknown, not dead.**

---

## 6. The usmap supplement — SHIPPED, with a before/after proof

**Gap confirmed with control:** across all three usmaps, **9/9 named native control classes present,
0/110 Angelscript types, 0/4 script enums.** The artifact reproduced:
`Default__BP_Barracuda_MinionWaypoint_C` decoded **0 properties** while `SCS_Node` exports in the
same package decoded 4-6.

**FK-14 resolved — which usmap the extractor actually loads:**
`tools/extractor/mappings.usmap` (1,876,427 B, md5 `3892b937…`) via `Program.cs:767-781` search
slot 2. All three files still carry their original md5.

**Naming, MEASURED:** `AssetRegistry.bin` holds 42 strings
`/Script/AngelscriptCode.ASClass'/Script/Angelscript.<Name>'` — script UClasses register in **one**
package with the `A`/`U` prefix stripped.

**Produced:** `tools/asdump/out/usmap/` — `mappings+as.usmap`, `angelscript.usmap`,
`as_schema_full.csv` (581 member rows), `as_schema.json`, `as_usmap.py`, `verify_usmap.py`.
91 entries (76 UClass + 15 UScriptStruct) + 4 enums. Merge is append-only:
**11,344/11,344 base structs and 2,226/2,226 base enums round-trip bit-identically**, order
preserved, 0 dangling refs, 0 trailing bytes, 0 name collisions.

**Before/after — 118 assets, same binary, only the usmap varies:** 92 identical (every native
control), 26 changed, **263 property values newly decoded** — 109 AS-declared (0 implausible floats)
+ **154 native properties the broken chain had been hiding**.
- `BP_AimingVisComponentV2.LaserSettings`: `{}` → the full 14-field `FAimingLaserSettings` in exact
  declaration order (`MaxDistance 1000.0`, `Brightness 1.0`), and the property *after* the array
  still decodes.
- `BP_GameMode_Barracuda`: 27 → **65** props, incl.
  `GoldBountyPerCurrentStreak [0,0,0,250,400,600,800,1000,1200,1400,2000]`, `MinionSplitXPBonuses`,
  `DragonRewards`, `MainObjectiveClass = BP_LokiTower_Nexus_C`.
- `BP_BarracudaShop.ItemLootTables` = the 9 MOBA shop loot tables. `BP_Airdoo`: 100 → 167.

### ★ A starting assumption was wrong and the experiment caught it
Four one-variable arms on the same probe: **all-members 945 values / 15 implausible; UPROPERTY-only
1048 / 6; reversed order 953 / 1374-of-1779 implausible.** `BP_AimingLaser_HuntressV2` is decisive —
UPROPERTY-only yields eight independent name↔object-class↔subobject-name agreements
(`MI_AimLaser_Desat_MidTick`, `LaserHitFlare` NiagaraComponent,
`CURVE_HERO_Huntress_Bow_EasyMode`); all-members yields `NaN` and `1.27e-313`.
⇒ **MEASURED: only `UPROPERTY()` members are reflected (470 of 581).** The reversed arm is the
positive control proving the instrument would have caught a wrong order.

**Remains:** enum underlying type UNTESTED (Int vs Byte are byte-identical because no packaged asset
overrides an AS enum property; shipped as Int, `--enum-underlying byte` flips it).
`BarracudaPhases` / `FMinionWave` have **no cooked values** — only 20 `.umap` files ship and none is
a Barracuda map, so schema is readable and data is absent: a fact about shipped content, not tooling.
⚠ Completing the chain makes pre-existing **FK-14 base-usmap defects more visible** and they must not
be misattributed to the supplement (`LokiGameState.XPRequiredToCompleteLevels` typed
`Array<ByteProperty>`; `SpawnSelectEndTime` typed Float). Root cause located:
`tools/usmapdump/usmap.go:325 writeInnerOrByte()` falls back to `ByteProperty`, and `writeUsmap()`
silently drops unknown-typed properties while re-sequencing `SchemaIdx`.

---

## 7. ⚠ LIVE MEASUREMENT — script UClasses are NOT registered at the menu

**Mine, this session. Read-only RPM against the live menu process (pid 46812, base
`0x7FF7D1330000`, `-NoHook`, 46 min uptime).** This **corrects** Track C's claim that
*"script UClasses are generated at engine init, so no tutorial sitting is needed."*

| probe | result |
|---|---|
| `LokiPlayerCheats_AS`, `BarracudaGameMode`, `LokiRespawnComponent` via `class_funcs.py` | **not found** ×3 |
| all `_AS`-suffixed UClasses in the live object array | **0** |
| 7 pure-script UClass names (`LokiGem`, `LokiDropShip`, `LokiAimingLaser`, `TemporaryFloor`, `UAVMapActor`, `LokiExoticLootComponent`, `RespawnTimerWidget`) | **0** — the 2 apparent hits are the NATIVE bases `LokiGemBase`, `LokiTemporaryFloorBase` |

**Positive controls (same tool, same call, same process):** `LokiGameMode` → 72 UFunctions,
`LokiPlayerController` → 151, `LokiPlayerCheats` → **65** (matching the recorded native figure).
**The instrument works.**

**But script ENUMS and STRUCTS *are* live** — `EBarracudaPhaseType`, `ELokiDropPodState`,
`EIsBarracuda` (Enum), `BarracudaPhase`, `GameEvent_Barracuda*`, `UIEvent_Barracuda_Shop_*`
(ScriptStruct). So the Angelscript **type system is partially registered at init: enums and structs
yes, UClasses no.**

⇒ **Consequence for the next experiment:** Track C's "nearly free, no sitting needed" callability
test **must be run during a map-loaded sitting** (the tutorial route), not at the menu. Names to
probe are in `tools/asdump/out/usmap/as_schema_full.csv`, column `ue_name` (66 AS UClasses).

---

## 8. Corrections this pass makes to the project record

| claim | where | correction |
|---|---|---|
| "only 18 classes are Angelscript" / "deploy/round is native" / "accept the ceiling" | `session-74-…md`, commit `19db6a2`, +5 docs | **REFUTED.** 110 classes; and native ≠ unreachable |
| "a 4.3× undercount" | FK-1 register | **Wrong — it is 9.0×.** The 18 tokens are 9 classes × 2 forms |
| "no `LokiRoundGameMode_AS`, **so** the mode is native" | FK-1 "Surviving nuance" | **Invalid inference** (the `_AS` suffix proves nothing). Conclusion happens to be right; reasoning struck |
| "decide whether an AS disassembler is worth building (none exists)" | FK-1 "Cheapest experiment" | **Stale** — `tools/asdump/` shipped in S101 |
| "print the owning class of every PI-dispatched UFunction for 5 s" | register §4.2 item 8 | **A TRAP** — returns 0 AS classes even when they are perfectly callable, because `Func != ProcessInternal`. Negative control only |
| "every step of the drop phase is a `BlueprintCallable` UFUNCTION" | `memory/supervive-angelscript-layer` | **False** — `InitializeDropPod` is not a UFUNCTION at all; 3 of 10 listed are not `BlueprintCallable`. The "skip the plane" two-call recipe is **not executable**. Conversely **zero `BlueprintAuthorityOnly` anywhere** — the S90 gotcha does not recur |
| fix = `AuthSetSpawnTeamLeader()` before spawning | `memory/supervive-angelscript-layer` | **Dead** — that function has **no body**, nor does `SetDropLeader`; and `SpawnDropPodForTeam` bails on `TeamDropPodClass == nullptr` first |
| "`AFFAGameMode` inherits the drop-in round-phase machine" | `docs/angelscript-layer.md` | **Wrong premise** — DropIn descends from `LokiGameMode`, not `LokiRoundGameMode`. Practical conclusion survives via the GameState |
| S74 "CallNative(SpawnPlayer) CRASHED (AV)" vs S91 "returns NULL" vs `fk3-fk4-settled.md:469` "body is `xor eax,eax; ret`" | 3 docs | **Resolved:** the `xor eax,eax; ret` reading is correct and S91's NULL is exactly what it returns. Only S74's AV is unexplained |
| "script UClasses are generated at engine init" | Track C, this session | **Corrected by live RPM (§7)** — enums/structs yes, UClasses **no**, at least at menu |
| `SneakSpeedMultiplier` "a data defect" | my own interim note | **6** attributes × **137** archetypes; **Theorycraft's own content↔code version skew** (2 deleted, 2 renamed, 2 relocated to `ULokiAttributeSetHealth`). Not ours, not a runtime failure — `DefaultSize: 56` vs 6 failures is graceful degradation |
| `Binds.Cache` is complete | implied | **Lower bound** — only 47 of 54 `ALokiGameMode` props exposed |

---

## 9. Ranked next steps

1. **★ One tutorial-route sitting, and it now tests four things at once.** Setup cost is **zero** —
   `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Engine.ini` already carries
   `[Core.Log] Preset=Gas` (written today, read-only) with all six GAS categories at Verbose.
   Collect: (a) the GAS categories on the real frontier — watch `LogAbilitySystemComponent` first,
   it is Epic's own and most likely to *name* why actor info is unbound; (b) **Track C's callability
   probe, which §7 shows needs a loaded map**; (c) `LogLokiRoundGameMode` phase transitions;
   (d) whether AS UClasses appear once the map loads. Positive control: `LogAbilitySystem` must
   still emit its cue block or the sitting is VOID.
2. **`CallBPGuarded(SpawnPlayer)`** with `CallNativeGuarded` retained as the measured control arm.
   `tutorial_launch.cpp:5615` uses the latter; `CallBPGuarded` (defined ~:933, used at 23 other
   sites) has **never** been pointed at it, and it is **self-diagnosing** — no bytecode ⇒ it prints
   `[BPC] refuse:` and returns, so the test cannot silently mislead. Writes no `.text`.
   ⚠ §5 predicts it refuses (the body is a stripped stub) — which would be a clean, informative
   close rather than a failure.
3. **Probe the script door that §5's synthesis opens:** `ULokiRespawnComponent::Respawn`,
   `ALokiDropShip::SpawnDropPodForTeam`, `UFFABotSpawnerComponent::BeginPlay` — script, AOT-compiled
   into the client, and callable with net routing bypassed.
4. **`ALokiCharacter::SpawnAndMoveLokiCharacter_BP`** — the one undocumented escape hatch; body in a
   decrypt gap, so re-dump from a map-loaded state first.
5. Re-run the extractor over all 68k assets with `mappings+as.usmap` to quantify the total gain
   (42 of 76 AS classes are referenced by packaged assets).
