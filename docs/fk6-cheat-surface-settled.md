# FK-6 SETTLED — the cheat surface

**Session:** S105 · **Date:** 2026-07-27 · **Method:** offline only. No launch, no injection.
**Status:** definitive on the questions it answers; explicit about the ones it cannot answer offline.
**Supersedes:** the "★ DEFINITIVE CLOSE" block at `memory/supervive-cheat-surface-inventory.md:135-148`
(retracted in scope, upheld in its two measurements).
**Companion artifacts:** `docs/fk6-native-cheat-impl-census.md`, `docs/fk6-cheat-impl-census.csv`
(both retained — but see §8.3, twelve of their rows are now measured wrong).

> **Read this first if you are about to touch cheats, spawning, or "enemies".**
>
> **The one-line honest answer: the cheat surface is PRESENT and NOT YET PROVEN CALLABLE.**
> The Angelscript cheat family ships with real bytecode bodies (measured, exactly). No cheat from
> that family has ever been invoked, the class that owns them has never been observed alive, and
> the two enumerators that would have looked for it are structurally blind to it. "Intact bytecode"
> is not "callable", and "callable" is not "effective". Do not let those three be rounded together —
> rounding is what produced FK-6 in the first place.
>
> Also: **do not build the plan around cheats at all.** §6 shows the goals FK-6 was rated HIGH for
> — damage and abilities — are reachable on objects that already exist, with no cheat, no spawn,
> and no new class. FK-6 should be re-graded **MEDIUM**.

---

## 1. Verdict, split by surface

FK-6 bundled four different surfaces under one belief. They have four different answers.

| # | Surface | Verdict | Confidence |
|---|---|---|---|
| **A** | **Native HOTKEY dispatch** (`AreHotkeyCheatsEnabled` and the 43 `Cheat*` ActionMappings) | **CLOSED. Adjudicated already; now *strengthened* with a mechanism.** | **CERTAIN** — full chain re-disassembled this session, byte for byte |
| **B** | **Native `_Implementation` bodies** (`ALokiPlayerCheats`, 65 UFunctions) | **PARTLY DEGRADED, MOSTLY UNMEASURABLE.** 31 of 65 (48%) cannot be read offline in any dump. Of the 31 native functions that *can* be read, **at most 12 have a real body and at least 18 are degenerate**. Every interesting verb (spawn, change-hero, teleport) is in the unreadable half. | **MIXED** — see §3.2 for the per-row grading |
| **C** | **Angelscript cheat family** (`ALokiPlayerCheats_AS`, 32 UFUNCTIONs) | **OPEN AS CODE. UNPROVEN AS ANYTHING ELSE.** 51 functions / 5,472 bytes, arithmetic closing exactly on the module header, **zero empty bodies**. Never instantiated, never invoked, never observed. | **HIGH** on the code; **UNKNOWN** on reachability |
| **D** | **Console** (`+ConsoleKeys=Tilde`, `ConsoleCommandCheat*`) | **IRRELEVANT to cheats, and the FK-6 register's console claim is FALSE.** Whether the console opens is still undecidable offline — but it no longer matters here. | **CERTAIN** on the irrelevance |

### 1.1 The thing that actually closes the native route, and it is not what anyone said

Neither the belief ("bodies compiled out") nor the census rebuttals ("bodies are mostly real") is the
operative fact. **The constructors are gone and the accessors return null.** Measured, this session,
end to end:

```
APlayerController::EnableCheats  exec thunk 0x3C61920
    P_FINISH ; jmp qword ptr [rax+0xC10]                 → vtable slot 386
  slot 386  = 0x3C35480:  mov rax,[rcx] ; xor edx,edx ; jmp qword ptr [rax+0xEE8]
  slot 477  = 0x0F7EC20   in APlayerController  (vt 0x081A82F8)   =  c2 00 00  =  ret 0
  slot 477  = 0x0F7EC20   in ALokiPlayerController (vt 0x08A1AEE0) =  ret 0
```

And, independently:

```
ALokiPlayerCheats::{GetPlayerController, GetPlayerState, GetHeroCharacter, GetAbilitySystemComponent}
    all share ONE exec thunk 0x54071C0:  P_FINISH ; call 0x0F7EB50 ; mov [rbx],rax ; ret
ALokiPlayerCheats::GetLocalLokiPlayerCheatsBP  exec thunk 0x5424F70
    (WorldContext step) ; P_FINISH ; call 0x0F7EB50 ; mov [rsi],rax ; ret
  0x0F7EB50  =  33 c0 c3  =  xor eax,eax ; ret     →  hard nullptr
```

MSVC `/OPT:ICF` folds only *byte-identical* functions. Four getters returning four different members
cannot share one thunk unless all four call the same trivial implementation. That is the measurement.

**Why slot 477 is `AddCheats`, and why the empty body is diagnostic (STRONG_INFERENCE, with an
unusually tight corroboration).** Stock UE 5.4, read directly from
`H:/Unreal Engine/UE_5.4/Engine/Source/Runtime/Engine/Private/PlayerController.cpp:1129`:

```cpp
void APlayerController::EnableCheats()          // virtual, UFUNCTION(exec)
{
#if !UE_BUILD_SHIPPING
    AddCheats(true);
#else
    AddCheats();          // default bForce = false
#endif
}

void APlayerController::AddCheats(bool bForce)  // :1107
{
#if UE_WITH_CHEAT_MANAGER
    ...  CheatManager = NewObject<UCheatManager>(this, CheatClass);
         CheatManager->InitCheatManager();
#endif
}
```

The observed slot-386 body is exactly one virtual call to slot 477 with **`xor edx,edx` = `false`**.
That is the `#else` branch — the *shipping* branch — reproduced instruction for instruction. So
slot 386 is `EnableCheats`, slot 477 is `AddCheats(bool)`, and because the entire `AddCheats` body
lives inside `#if UE_WITH_CHEAT_MANAGER`, an empty `ret` body is precisely, and only, what
`UE_WITH_CHEAT_MANAGER == 0` emits.

> **`UE_WITH_CHEAT_MANAGER == 0` in this build.** `PC->CheatManager` can never become non-null by
> any in-game path. That is a **constructor** strip, not a **body** strip — which is exactly why the
> engine's own cheat bodies survived, and exactly why a shim can defeat it.

**Correction to a claim raised against this** (the evidence skeptic flagged the presence of
`CheatManager` / `CheatClass` in `mappings.usmap` as "in tension" with `UE_WITH_CHEAT_MANAGER == 0`).
There is no tension. Both UPROPERTYs are declared **unguarded** in stock UE 5.4
(`Classes/GameFramework/PlayerController.h:362,370` — no `#if` in scope), so they ship in every
configuration. Their presence is non-discriminating. *Good news anyway: the landing slot for a
shim-constructed manager exists and is reflected.*

### 1.2 Surface A — native hotkey dispatch: closed, with the mechanism

Re-verified end to end this session (all MEASURED, `dumps/` 10-dump `.text` union):

| what | address | bytes | meaning |
|---|---|---|---|
| `AreHotkeyCheatsEnabled` exec thunk | `0x52FD980` | `… P_FINISH ; call 0xF7EB60 ; mov [rbx],al ; ret` | dispatch |
| `AreHotkeyCheatsEnabled_Impl` | `0x0F7EB60` | `32 c0 c3` | `xor al,al; ret` — **always false** |
| `EnableHotkeyCheats_Impl` | `0x55D39B0` | `0f 57 c0 66 0f 2e c8 74 08 c6 81 90 03 00 00 01 c3` | **real** — writes `[this+0x390] = (Enabled != 0.0)` |
| `AdminOnly` / `HotkeyCheatsEnabledOnly` (ICF-folded) | `0x1F67DF0` | `c6 02 01 c3` | `mov byte [rdx],1 ; ret` — **always writes the `Hidden` exec pin** |

The setter is real; the getter never reads what it writes. `IsForceDisplayCharacterNameEnabled`
folds onto the *same* `xor al,al; ret` while `EnableForceDisplayCharacterName` really writes
`+0x392` — the identical pattern, twice. **Forcing the enable path is pointless.** And both
Blueprint exec-gates unconditionally take the hidden branch, so any BP graph gated on them is dead.

This is a **third and fourth** measured stub beyond S74's two, and it upholds the S79/FK-6
adjudication that rejected the input-action variant.

### 1.3 Surface D — the console: the register's own claim is false

> FK-6 register: *"If the console works, every `ConsoleCommandCheat*` above is reachable by typing,
> with no shim at all."*

**FALSE, MEASURED.** **Zero** of the **500** `UFUNCTION(...)` declarations across the entire 78-module
Angelscript layer carries the `Exec` flag. (Full flag histogram: `CanOverrideEvent` 471,
`BlueprintCallable` 326, `UnrealName` 226, `BlueprintEvent` 226, `BlueprintOverride` 106, `NoOp` 43,
`BlueprintPure` 35, `NetMulticast` 23, `Static` 22, `NetServer` 22, `ConstMethod` 19,
`BlueprintAuthorityOnly` 16, `Unreliable` 3, `NetClient` 3 — **no `Exec` token at all**.)

`ConsoleCommandCheatSpawnEnemyWisp` is declared `UFUNCTION(BlueprintCallable, CanOverrideEvent)`.
The `ConsoleCommand` prefix is a Theorycraft **naming convention**. The native
`ALokiPlayerCheats` functions *do* carry `Exec` (`CheatTeleportLocation [Exec,Native,BPCallable]`),
which is the source of the confusion.

Additionally, `ALokiPlayerCheats` is an `AActor`, so `APlayerController::ProcessConsoleExec`'s
chain (self → HUD → PlayerCameraManager → CheatManager) would never reach it even if the console
opened; and `UCheatManager::ProcessConsoleExec` is itself inside `#if UE_WITH_CHEAT_MANAGER`
(`CheatManager.cpp:94-135`), which §1.1 measures as 0.

**Consequence:** FK-13 (is the console open?) and FK-6 are **independent**. Reopening the console
buys nothing for cheats. Press `~` if it is free — it is worth having for engine `Exec` verbs
(`open`, `travel`, `stat`, `showdebug`) on the DS route — but do **not** score a console win as a
cheat-surface win.

---

## 2. What S74 measured, what it generalised, and the exact scope its evidence supports

### 2.1 S74's two measurements are CORRECT. I re-verified both from bytes.

S74 recorded `AreHotkeyCheatsEnabled_Impl @0x7FF6B646EB60` and `ServerCheatSpawnActor_Impl
@0x7FF6B646EC20` against `BASE=0x7FF6B54F0000`. Subtracting: RVA `0x0F7EB60` and `0x0F7EC20`.
In `dumps/merged.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA):

```
0x0F7EB60:  32 c0 c3            xor al,al ; ret
0x0F7EC20:  c2 00 00            ret 0
```

**S74 mis-measured nothing.** Its failure is entirely one of scope.

### 2.2 The precise scope its evidence supports

> Two `ALokiPlayerCheats` `_Implementation` bodies are empty.

That is all. It does **not** support:

- …that the other 63 `ALokiPlayerCheats` bodies are empty (31 are unreadable; of the readable
  native ones, ~12 have real bodies);
- …that "the cheat surface" is one thing (there are **six** cheat-named native UClasses plus a
  disjoint Angelscript class);
- …that `UCheatManager` is stripped (39 of its bodies are real, including `Summon`, `God`,
  `Teleport`, `DamageTarget`);
- …that "no flag, timing, marshalling, or object-spawn fix can change it" (a shim that
  *constructs* the manager is exactly such a fix — the strip is at the constructor);
- …that it "retroactively explains every no-op" (the accessors returning null explains more of
  them, and explains them better).

### 2.3 The mechanical origin of the over-claim — worth recording, because the trap will recur

S74 wrote: *"Adjacent to the `AreHotkeyCheatsEnabled` stub in the **0xF7Exxx stripped-cheat region**."*

**There is no stripped-cheat region.** MSVC `/OPT:ICF` folds every byte-identical function in the
whole binary to one address. Call-site multiplicity, from `tools/strxref/index/callmult.pkl`:

| address | body | distinct call sites |
|---|---|---|
| `0x0F7EC20` | `ret 0` | **4,784** |
| `0x0F7EB60` | `xor al,al; ret` | 192 |
| `0x0F7EB50` | `xor eax,eax; ret` | 58 |

Two cheat functions landing in that pool is **one bit of information, not sixty-five**. Adjacency
there means "both bodies are empty", never "both were stripped *together, as cheats*". Everything
trivial in the image lands there — engine, game, third-party alike.

> **Corollary that inverts a documented heuristic.** `strxref.py:1324-1326` advises ranking
> candidate implementations by rarity ("an implementation has ~1-3 callers"). For stub detection
> that rule is exactly backwards: stubs accumulate thousands of callers, real bodies have one. The
> first run of `cheat_impl_census.py` using multiplicity misclassified all 13 stubs as "INLINED".

---

## 3. The full cheat inventory — both surfaces

### 3.1 Two disjoint surfaces, zero name overlap

| | native `ALokiPlayerCheats` | script `ALokiPlayerCheats_AS` |
|---|---|---|
| origin | C++, `Z_Construct_*` at load | `Loki/Script/PrecompiledScript.Cache`, built at runtime |
| declared functions | **65** (S74's count is correct — see §3.5) | **51** functions, **32** with a `UFUNCTION` |
| bodies | machine code, subject to `WITH_CHEATS` | AS VM bytecode — **a C++ guard cannot strip it** |
| exposed to script | 47 methods + 6 properties via `Binds.Cache` | n/a |
| name overlap | **none** — set intersection is empty | |
| ever observed alive | yes (S74 GUObjectArray) | **never** |

### 3.2 Native `ALokiPlayerCheats` — 65 declared, corrected distribution

Corrected against `docs/fk6-cheat-impl-census.csv` after this session's independent re-resolution
(§8.3). Verdicts marked ✔ were re-verified by hand this session; the rest are census-provisional.

| verdict | n | what it means |
|---|---|---|
| **UNVERIFIABLE** | **31** | thunk page is all-zero in **all 10** dumps. Not "stripped" — *unread*. |
| RET_STUB | 9 | resolves to `0x0F7EC20` = `ret 0` |
| ZERO_STUB | 5 ✔ | resolves to `0x0F7EB50` = `xor eax,eax; ret` (nullptr) |
| FALSE_STUB | 2 ✔ | resolves to `0x0F7EB60` = `xor al,al; ret` |
| HARDCODED-GATE | 2 ✔ | `0x1F67DF0` = `mov byte [rdx],1; ret` — always the `Hidden` pin |
| REAL | 12 | genuine body (3 of the 12 hand-verified ✔) |
| TRIVIAL | 1 | real, 1-line (`EnableForceDisplayCharacterName` writes `+0x392`) |
| SCRIPT | 3 | thunk == `ProcessInternal 0x13454A0` → BP/script-implemented, never native |

**The honest headline:** of the **31 native functions that can be read offline**, at most **12
(39%) have a real body** and at least **18 (58%) are degenerate**. That is *closer to* S74's
direction than the census's first pass reported — and it still does not license S74's conclusion,
because the degenerate ones are overwhelmingly *getters and gates*, not the verbs.

**The verbs are all in the dark half.** Every UNVERIFIABLE row, verbatim, is the interesting list:
`ServerCheatSpawnActor`, `ServerCheatSpawnItem`, `ServerSpawnAndReplaceItem`, `CheatChangeHero`,
`ServerCheatChangeHero`, `ServerChangeHero`, `ServerNextHero`, `ServerPreviousHero`,
`CheatTeleportLocation`, `ServerTeleportLocation`, `CheatNoCooldowns`, `ServerCheatNoCooldowns`,
`ServerToggleGameplayEffect`, `CheatSetTeamEliminated`, `ClientHypeUpdated`, `ServerUpdateHype`,
`CheatSetEmote`, `CheatMuteAudio`, `CheatMeasureCursor`, `RequestGameplayTag`, `RequestStatusDump*`,
`ServerRequestStatusDump`, `ServerNote`, `SetGamepadAimSettings`, the four `ServerCheatChange*Cosmetic`,
`CheatAutoStrafeToggleDirection`, `CheatGetAllClientActorsByClassName`.

**Bounded from `.rdata` instead.** `ALokiPlayerCheats` introduces 19 virtual slots past `AActor`'s
247 (vtable `0x08A1A690`, 266 slots). Read directly:

```
[246] 0x3393550 real   [247] 0x55DF3E0 real   [248] 0x55E4500 real   [262] 0x55D0230 real
[249..261] and [263..265]  =  0x0F7EC20  (ret 0)   ← 16 slots
```

`ALokiPlayerCheats` declares exactly **19 Net UFunctions** (18 `Server*` + `ClientHypeUpdated`).
Anchor: `ServerBoostPlayer`'s thunk `0x3702560` is decrypted and ends `jmp qword ptr [rax+0x820]`
= slot 260 = `0x0F7EC20` — **measured empty**.

> **~16 of the 19 cheat RPC implementations are empty — STRONG_INFERENCE, not measurement.**
> The 19-slots-to-19-RPCs mapping is not established (slot 247 also holds the body a *non-RPC*
> thunk calls). One measured anchor, sixteen inferred. Do not let this harden. Probe P2 (§6.6)
> converts it in one run.

### 3.3 Angelscript `ALokiPlayerCheats_AS` — 51 functions, and the census closes exactly

Independently reproduced this session from the per-function disassembly appendices:

- **51 functions, 1,368 dwords = 5,472 bytes** — closing *exactly* on the module header's declared
  `5472 bytes of bytecode`. The parse is self-checking; there is no 52nd hidden cheat.
- **Zero empty bodies.** Smallest = 4 dwords (`Tick_Implementation`, which really calls
  `TickAutoJump`); largest = 138 (`ServerSpawnWispAS_Implementation`).
- Layer-wide baseline for bare-RET (≤1 dword) bodies: **46 of 1,463 (3.1%)**. This module is a
  measurable outlier *toward* having code.

**RPC/authority classification — complete.** 11 functions are `UFUNCTION(UnrealName=X,
BlueprintCallable, BlueprintEvent, NetServer)`:
`AuthCheatToggleHealthRegen`, `AuthCheatToggleManaRegen`, `AuthCheatGrantGold`,
`AuthCheatGrantGems`, `AuthCheatUnlockFullArmory`, `AuthCheatExecuteUAV`,
`AuthCheatBarracudaNextPhase`, `AuthCheatBarracudaToggleSpawnerType`,
`AuthCheatBarracudaToggleDayNightCycle`, `AuthCheatBarracudaAdvanceDayNightCycle`,
`ServerSpawnWispAS`.

- **All 11 reliable.** The dumper prints set flags from a fixed 18-bool vector that contains
  `Unreliable` (and no `NetReliable`); `Unreliable` appears 3× layer-wide, so its absence here is
  informative.
- **No `BlueprintAuthorityOnly` anywhere in the module** (16 sites exist layer-wide; none is here).
- ⚠ **`NetValidate` is zero-information.** It appears **0 times across all 500** UFUNCTIONs, so the
  dumper may not emit the token at all. *Do not* conclude "no `_Validate` gate". (The project's own
  `PartyModel.Version` lesson: absence of a token ≠ absence of a field.)
- The other 20 UFUNCTIONs (every `ConsoleCommandCheat*`, `SpawnEnemy/AllyWispAtMyLocation`, the
  movement/ability-log toggles) are plain `BlueprintCallable + CanOverrideEvent` — no net flags.
  They run wherever invoked and then fire the Server RPC.

**Cross-module sweep — the script cheat inventory is CLOSED at 43 functions in 2 files.**
`Cheat` appears in exactly 2 of 78 modules: `PlayerController/LokiPlayerCheats.as.txt` (35) and
`DayNightController/LokiDayNightController.as.txt` (8). Barracuda's 28 modules, FFA, DropPhase,
Armory, UAV and the Shop carry **no cheats of their own** — Barracuda's are reached from
`LokiPlayerCheats` via `GetBarracudaGameStateComponent()`. No further sweeping is warranted.

**Report the stub fairly: 2 of the 43 script cheats are empty.** `ALokiDayNightController_AS`'s
`AuthCheatNightToDay` / `AuthCheatDayToNight` are `NetMulticast` reliable, their `_Implementation`s
are 5 dwords that call `BP_CheatNightToDay` / `BP_CheatDayToNight`, and *those* `_Implementation`s
are `UFUNCTION(..., NoOp)` at **1 dword** = a bare RET. Inert unless a Blueprint subclass overrides
the `BP_` event. So: **41 of 43**, not "all".

**Bodies worth knowing (all MEASURED from the appendices):**

| function | dwords | what it does |
|---|---|---|
| `ServerSpawnWispAS` | 138 | see §5 |
| `AuthCheatToggleHealthRegen` / `ManaRegen` | 88 ea. | real GAS toggle: `MakeEffectContext` → `MakeOutgoingSpec(CheatDisable*RegenEffectClass)` → `ApplyGameplayEffectSpecToSelf`; `RemoveActiveGameplayEffect` on the second call |
| `AuthCheatExecuteUAV` | 48 | `GameState.UAVComponent.ExecuteUAV(FLokiUAVConfig{}, SourceLocation, TeamIndex)` |
| `AuthCheatUnlockFullArmory` | 18 | `Loki::GetLokiGameState(wc).SetArmoryFullyUnlocked(true)` |
| `AuthCheatGrantGold` / `GrantGems` | 17 ea. | `PlayerState.GrantWalletCurrency("Gold"\|"Gems", Amount, ECurrencyGrantReason::Misc)` |
| `AuthCheatBarracudaNextPhase` | 10 | `BarracudaGameStateComponent.AuthMoveToNextBarracudaPhase()` |

### 3.4 ⚠ Most of that script list is DEAD ON ARRIVAL, and this is the sharpest limit on Surface C

Every `AuthCheat*` body except three opens by calling one of the four ICF-folded accessors that
§1.1 measures as `xor eax,eax; ret`:

| script cheat | opens with | fate |
|---|---|---|
| `AuthCheatGrantGold` / `GrantGems` | `this.GetPlayerState()` → `.GrantWalletCurrency(…)` | **null deref** (no guard) |
| `AuthCheatToggleHealthRegen` / `ManaRegen` | `v = this.GetAbilitySystemComponent(); if (v == nullptr) return;` | **silent no-op** |
| `RunCommand` (⇒ every `ConsoleCommandEnable*Debug`, `EnableStuckAbilityLogs`) | `v = this.GetPlayerController(); if (v == nullptr) return;` | **silent no-op** |
| `GetMyLocation`, `TickAutoJump`, `SpawnAllyWispAtMyLocation`, the `ConsoleCommand*` wrappers | ditto | dead |

**Survivors** — the ones whose context arrives as a *parameter* or via `GetLokiGameState`:
`ServerSpawnWispAS(TeamIndex, Location)`, `AuthCheatExecuteUAV(SourceLocation, TeamIndex)`,
`AuthCheatUnlockFullArmory`, and the four `AuthCheatBarracuda*`.

> This is the single biggest correction to FK-6's *payoff* estimate. Do not budget a session on
> "wire up the cheat object and call the script cheats" — most of them cannot work no matter how
> they are reached.

### 3.5 Two counting corrections, both against the FK-6 task framing itself

**"219 native entries, not 65" is wrong.** `docs/session-74-cheat-enum-dump.txt` headers:
`[0] LokiPlayerCheats (65)` at :237, `[1] Actor (153)` at :369, `[2] Object (1)` at :677.
**219 is the inheritance chain.** Independently, the static reflection table
`FClassFunctionLinkInfo[] 0x08A106B8..0x08A10AC7` holds **65 entries**. S74's 65 was right.

**`CheatSetTeamEliminated` is NOT a script cheat.** It is a native bind —
`void CheatSetTeamEliminated(const UObject WorldContextObject, int TeamIndex, bool bEliminated)`
on the C++ class — that shipping script *calls* (`01C4 CALLSYS`, i.e. native, not `CALLINTF`).
It appears in `binds_members.csv` and in S74's 65-set. Its own `_Impl` is UNVERIFIABLE offline.

### 3.6 The other four cheat classes — one of them is the biggest thing the belief hid

| class | census | note |
|---|---|---|
| **`UCheatManager`** | **39 REAL**, 4 TRIVIAL, 3 SCRIPT, 3 RET_STUB, 1 `mov al,1;ret`, 3 INLINED, 2 SUSPECT, 3 UNVERIFIABLE | **verified real:** `God 0x35AFD70`, `Summon 0x35C2B00`, `Teleport 0x35C3E20` (union: `dumps/toggles` only), `Fly`, `Ghost`, `Walk`, `Slomo`, `DamageTarget`, `DestroyAll`, `PlayersOnly`, `EnableDebugCamera` |
| `ULokiClientPlayerCheats` | **5 REAL**, 1 SCRIPT | menu/lobby-scoped; `CheatResetClientProfile` has observable effect on *our* backend ⇒ a free validation target |
| `ULokiCharacterCheatDetectionComponent` | 18 REAL, 7 SCRIPT, 4 SUSPECT, 1 INLINED, 1 TRIVIAL | anti-cheat, not a cheat |
| `UCheatManagerExtension` / `UGameFeatureAction_AddCheats` | 2 RET_STUB / 1 SCRIPT | |

> ⚠ **Downgraded, per the evidence skeptic, and I confirm the downgrade.** An earlier claim of
> "`UCheatManager` ships 54/57 real, ZERO stubs" is **refuted by the workflow's own CSV**. That
> number was a census of **thunk** RVAs; the thunk always has code. The **implementation-level**
> number is 39, with 3 genuine `ret 0` stubs (`TestCollisionDistance`, `ToggleAILogging`,
> `ToggleDebugCamera`) and `ServerToggleAILogging` = `mov al,1; ret`. `ViewClass` / `ViewActor` /
> `ViewPlayer` are **UNVERIFIABLE**, not real.
>
> **Why `UCheatManager` survived while `AddCheats` did not** (MEASURED from the engine source):
> `CheatManager.cpp`'s `#if UE_WITH_CHEAT_MANAGER` guard spans only lines **94-135**
> (`ProcessConsoleExec`). `God()` at :275 and `Summon()` at :406 are **outside** it. The class body
> compiles in every configuration; only its *instantiation site* is guarded. The two facts are
> consistent, and together they name the exact fix: **construct the object ourselves.**
>
> `UCLASS(Blueprintable, Within=PlayerController, MinimalAPI)` — its Outer **must** be the PC.

### 3.7 The 44 script-implemented cheat-class UFunctions

44 of the 319 enumerated cheat-class UFunctions have thunk == `ProcessInternal 0x13454A0`, i.e.
they are BP/script-implemented and a `WITH_CHEATS` C++ guard could never have touched them. Three
are `LokiPlayerCheats`-declared — `AddLevelingPassive`, `ReceiveBoostPlayer`,
`ReceiveInitializeAfterController` — and `binds_members.csv` confirms all three are script-side
(`ALokiPlayerCheats::{AddLevelingPassive, BoostPlayer, InitializeAfterController}`). That is the
exact seam between the two surfaces.

### 3.8 The 43 orphaned `Cheat*` input actions — settled, positively

All 43 tokens (`CheatSpawnEnemyDummy`, `CheatSpawnDesignatedSurvivor`, `CheatToggleInvulnerable`,
`CheatKillMe`, `CheatStoreLocation`, `CheatLevelUp`, `DevCheatNoPacketsIn`, …) appear in exactly
three places: `catalog/wbp/WBP_UI_CheatKeyBindSettings.json`, `out/names_mainmenu.txt`, and
`raw/Loki/Config/DefaultInput.ini`. `strxref find` on eight of them (incl. `ShowCheats`) returns
**no match** in the image. `Comp_PlayerController_Cheats.uasset` is a 13-name stub containing two
delegate signatures, one ObjectProperty, and **no functions**.

**43/43 located, 0/43 with a dispatch target.** A shipped rebind UI over actions nothing consumes.
The input layer is a permanent dead end for cheats — and `ShowDebugMenu` / `ToggleDebugMenu`
resolve to `0x5254180` → `jmp 0xF7EC20`, so pressing RightAlt or Ctrl+`\` cannot show a menu either.

*(The 16 shipped `Cheat_Panel_*` widgets and `WBP_UI_Cheats_Root` are real Blueprint content with 29
bound button events, but they call `GetLocalLokiPlayerCheatsBP` nine times — measured null. Object
first, UI second, or not at all.)*

---

## 4. Dispatch analysis — every route, ranked, with the exact first call

Ranked by (value × probability) ÷ cost. **R0 is free and settles the technical question that
gates R1-R3.**

### R0 — Which primitive drives an Angelscript UFunction? · cost: one call · risk: none

The project's standing answer (`docs/angelscript-layer.md:396` — *"must be invoked as UFunctions —
`CallBPGuarded`"*) is an **untested inference and is probably wrong**: an Angelscript body is AS VM
bytecode in `PrecompiledScript.Cache`, not Kismet bytecode in `UFunction::Script`, so `Func` should
be an AS trampoline and `CallNativeGuarded` should be correct.

**The risk is already engineered away.** `tools/sigbypass-mod/tutorial_launch.cpp:369-390` —
`CallBPGuarded` reads `UStruct.Script.Data/Num`, and when `!snum` it **refuses and logs**:

```
[BPC] refuse: script=0x%llX num=%u propsSize=%u thunk=0x%llX
```

**First call:** on the already-live PlayerController (a `LokiPlayerController_AS` descendant —
`docs/angelscript-layer.md:52-56` records the shipped chain
`BP_HERO_Assault_C → … → /Script/Angelscript.LokiHeroCharacter_AS → /Script/Loki.LokiHeroCharacter`),
resolve any zero-arg script `_Implementation` by name and call `CallBPGuarded(func, PC, res)`.
**Its own refuse-log IS the measurement**, it is crash-free, and it prints the `thunk` you need for
the retry through `CallNativeGuarded`. Fix the doc line afterwards.

### R1 — Construct a `UCheatManager` · cost: one shim edit · value: HIGHEST native

39 real engine cheat bodies including `Summon`, `Teleport`, `God`, `DamageTarget`, `DestroyAll`,
`Slomo`, `Fly`, `PlayersOnly`. Nobody in 101 sessions has tried it, because "the cheat surface is
closed" hid it.

**Exact first call:** `CallNativeGuarded(UGameplayStatics::SpawnObject, exec thunk RVA
0x380FF40)` with `param0` = the `/Script/Engine.CheatManager` UClass (or the `ALokiPlayerController`
CDO's `CheatClass` if non-null) and `param1` = the local `ALokiPlayerController` **as Outer**
(mandatory — `UCLASS(Blueprintable, Within=PlayerController, MinimalAPI)`). MEASURED: `0x380FF40` is
a real, non-folded 2-param exec thunk — two `FFrame` param steps via `0x12F3FC0` with the standard
guarded `0x1345FB0`/`0x1345FE0` teardowns. Log the returned pointer's class name.

Then write it into `PC->CheatManager` (resolve the UPROPERTY offset by name — it *is* reflected,
§1.1) and call `UCheatManager::God` (zero params) as the one-bit check.

**`God` is verified intact, instruction for instruction.** Vtable `0x07FA7E28` slot 96 → `0x35AFD70`:

```
mov eax,[rcx+0xC] ; shr eax,4 ; test al,1 ; je …      // Outer-class fast path
mov rcx,[rcx+0x28]                                     // GetOuterAPlayerController()
mov rcx,[rcx+0x3F8]                                    // ->GetPawn()
test rcx,rcx ; je …                                    // if (Pawn != nullptr)
test byte [rcx+0x6A],4                                 // Pawn->CanBeDamaged()
```

That is stock UE 5.4 `UCheatManager::God()` (`CheatManager.cpp:275`) reproduced exactly — and it
independently confirms the Outer-must-be-the-PC requirement. If `God` no-ops, call
`InitCheatManager` first and retry: `AddCheats` normally calls it right after `NewObject`.

### R2 — The Angelscript enemy spawn · cost: medium · value: HIGHEST for "enemies" · see §5

Spawn `/Script/Angelscript.LokiPlayerCheats_AS`, write the two class pointers, call
`ServerSpawnWispAS(TeamIndex, Location)` **directly** — never the `ConsoleCommandCheat*` wrapper,
whose helpers `GetClientCursorLocation` / `GetMyLocation` / `GetPlayerState` are dead or dark.
Gated on probe P1 (§6.6) showing the class exists at all.

### R3 — `APlayerController::ConsoleCommand` for **engine** Exec verbs only

`open`, `travel`, `stat`, `showdebug`. Useful to the DS route. Reaches **no** cheat (§1.3).

### R4 — Press `~` · cost: one keypress

Free. Does not change the cheat verdict either way. Undecidable offline: `UConsole` (`0x0824C950`,
1 xref), state FName `Typing`, `Command not recognized: %s` (`0x081AEB28`, 1 xref, 591 B function),
`ConsoleHistory.ini`, `UConsoleSettings`/`ViewportConsole`/`ConsoleClass` are all present — **but
all of that ships in stock UE regardless of `ALLOW_CONSOLE`**, which guards only the construction
site in `UGameViewportClient` and leaves no string. Non-discriminating evidence; the same
"stored ≠ used" overclaim FK-2 was killed for.

### CLOSED — do not spend on these

| route | why |
|---|---|
| the input/hotkey route | 43/43 orphaned; `AreHotkeyCheatsEnabled` hard-false; the enable flag is written and never read |
| `ConsoleCommandCheat*` as console commands | `Exec` 0/500 |
| native `ShowCheats` / `ToggleDebugMenu` menu | `jmp 0xF7EC20` |
| the shipped `Cheat_Panel_*` widgets | 9× `GetLocalLokiPlayerCheatsBP`, measured null |
| every `AuthCheat*` that opens on a `Get*()` accessor | §3.4 |
| `ScanPrimaryAssetTypesFromConfig` (standing project rule) | unchanged |

---

## 5. `ServerSpawnWispAS` and the enemy question

**This is the most valuable single thread FK-6 produced, and it is also the one most at risk of
being over-sold. Confidence, plainly: the BODY is certain; the CALL is unproven; the PRODUCT is
weaker than "an enemy".**

### 5.1 The body — MEASURED, verbatim, and not guard-inverted

138 dwords / 81 instructions — the largest function in the module. I read the ground-truth
disassembly appendix, not only the pseudo-source:

```cpp
void ServerSpawnWispAS_Implementation(const int TeamIndex, const FVector& Location)
{
    v6  = SpawnActor(this.WispControllerClass, ZeroVector, ZeroRotator, NAME_None, /*deferred*/false, nullptr);
    v8  = v6.PlayerState;                      // ADDSi 960 ; RDSPtr   -- NO CmpPtrNull
    v12 = (v8 != nullptr) ? cast<ALokiPlayerState>(v8) : nullptr;
    v16 = SpawnActor(this.WispHeroClass, Location, ZeroRotator, NAME_None, /*deferred*/true, nullptr);
    v16.SetOwner(v12);
    FinishSpawningActor(v16);
    v6.Possess(v16);
    LokiTeam::SetTeamForActor(v16, TeamIndex);
    v20 = Loki::GetLokiGameState(__WorldContext);
    if (v20 != nullptr && v20.GetOrCreateTeamState(TeamIndex).GetLivingPlayers().Num() < 2)
        this.CheatSetTeamEliminated(this, TeamIndex, true);
    v16.LivingStateMachine.RequestMoveTowardDeath(FGameplayEffectContextHandle());
}
```

**Not guard-inverted** (I checked, because the decompiler's structurer is known to bury join blocks):
`RequestMoveTowardDeath` sits at join label `L01E4` (`0x0208`), **unconditional**, after both branch
merges. The `SpawnActor` deferred flags are `false` for the controller and `true` for the hero,
exactly as printed. The only native call on the main path is `LokiTeam::SetTeamForActor`
(`ULokiTeamStatics::SetTeamForActor`, **static**, `bool SetTeamForActor(AActor, const int)`,
exec thunk `0x5485920`, decrypted).

### 5.2 What a "Wisp" is — and why calling this "an enemy" without a qualifier would be false-known #6

A Wisp is SUPERVIVE's **downed/knocked soul form** of a player: allies resurrect it, enemies execute
it. Confirmed from the engine's own symbols in `dumps/merged.dump.exe`: `ALokiWispActor`,
`ALokiWispPortraitActor`, `WispExecute`, `OnWispResurrection`, `ETrainingEvent::WispResurrection`,
`State.PausedWisp`, `HasTargetWisp`, `BotWispSearchRadiusCombat/NonCombat`, `bCanSpeakAsWisp`,
`WispMeshComponent`.

So the product is a hostile, targetable, executable actor — **that arrives DOWNED, not combat-capable.**

**Everything before the last line produces a live, AI-possessed `ALokiHeroCharacter` on an arbitrary
team.** Two ways to keep it: (a) call `ServerSpawnWispAS`, then immediately
`RequestMoveTowardAlive` on the returned hero's `LivingStateMachine` (both are bound:
`ULivingStateMachine::{RequestMoveTowardDeath, RequestMoveTowardAlive, FullyDie}`); or (b) replay
the sequence with the native-call primitive and omit the last call. Both use only already-bound
functions.

### 5.3 The traps — four, and each can independently no-op or crash the call

**None of these is measured. Every agent slid from "body exists" to "spawn happens".**

1. **The class has never been observed alive.** `LokiPlayerCheats_AS` is absent from S74's
   GUObjectArray listing — but that listing is **inadmissible**: `tools/re/cheat_enum.py:175` gates
   on `if cn == "Class":`, and Angelscript UClasses live in `/Script/Angelscript` and need not be
   plain `UClass` instances (same gate in `tools/re/class_funcs.py`). *Until that gate is fixed,
   any "we enumerated it and it wasn't there" from either tool is inadmissible — potentially
   including S96's.* `tools/re/obj_by_class.py` carries **no** such gate and is the right tool.

2. **Both class pointers are default-constructed NULL and there is no null guard.** Constructor,
   from the appendix: `ADDSi 1064 → TSubclassOf<AAIController>::$beh0` and
   `ADDSi 1072 → TSubclassOf<ALokiHeroCharacter>::$beh0`. So **`WispControllerClass` = `this+0x428`,
   `WispHeroClass` = `this+0x430`**, both empty. No shipped asset subclasses `LokiPlayerCheats_AS`
   (catalog grep: `LokiPlayerController_AS` ×6, `LokiHeroCharacter_AS` ×5, `LokiGameState_AS` ×4,
   `LokiAirship_AS` ×1, `LokiWidgetHighlighterHitTestBlocker_AS` ×1, **`LokiPlayerCheats_AS` zero**),
   so nothing fills them. `v6.PlayerState` and `v16.SetOwner` are unguarded derefs — the success
   path and the access-violation path are the same call.
   **Read `obj+0x428` / `obj+0x430` before calling. Verify against `FProperty::Offset_Internal`
   live rather than trusting AS-side offsets.**

3. **The fill recipe exists in shipping script.** `UFFABotSpawnerComponent::BeginPlay_Implementation`
   (`tools/asdump/out/modules/FFA/FFABotSpawner.as.txt:126-190`, 266 dwords) does
   `ULokiAssetLoader::GetHeroAssetFromPrimaryAssetId(wc, FPrimaryAssetId("Hero:assault"), out) →
   ULokiHeroAsset.GameplayBlueprint → System::LoadClassAsset_Blocking → TSubclassOf<ALokiHeroCharacter>`,
   hardcoding ten live hero ids: `assault, firefox, freeze, sniper, flex, hookguy, rocketjumper,
   Storm, BurstCaster, BountyHunter`. That closes the null-defaults problem entirely from script.

4. **The RPC-routing worry is real for the shipped path and moot for ours.** The script's own caller
   is `__Evt_Execute(this, n"ServerSpawnWispAS")` — ProcessEvent-by-name on a `FUNC_NetServer`
   UFunction, which *does* route. But the project's primitive calls `UFunction.Func` **directly**,
   bypassing routing, **and** force-open is authority (S91-93 completed `FUNC_BlueprintAuthorityOnly`
   objectives — direct evidence, not assumption). Discharged twice over.

### 5.4 The cleaner enemy paths found while chasing this

Both are ordinary gameplay machinery, **not** `WITH_CHEATS`-guarded — the compiled-out argument does
not apply to them at all.

- **`ULokiBotSpawnerComponent`** (native, script-bound, `binds_members.csv`):
  `ALokiHeroCharacter SpawnBot(const TSubclassOf<ALokiHeroCharacter> HeroClass, const FVector Location,
  const int TeamIndex, const uint8 Difficulty = 4, AController PremadeBotController = nullptr,
  FString BotName = "")`; `bool TrySpawnTeam(const uint8 Difficulty, const FVector LocationOverride)`;
  `MakeNewBotController`; `SetSpawnableBots`; **`SetSpawnCheatsEnabled(const bool)`** — a spawn-cheat
  gate nobody has looked at. Full BT/BB/EQS content ships (`BT_HeroBots`, `AC_HeroBot`,
  `BTT_CastSpell`, `GE_{Trivial…Normal}Bot`).
  ⚠ **Downgraded per the evidence skeptic, and I confirm:** `SpawnBot`'s impl `0x556D910` is
  **all-zero in all 10 dumps** — *unclassified*, not proven real. And a bot hero is an
  `ALokiHeroCharacter`, so it inherits the missing-`HeroAffiliated`-carrier wall. **Rank third.**
- **`ALokiBattleRoyaleSpawner::SpawnSingleActor(SpawningClass, PostSpawnConfig)`** — the spawner does
  grounding, team, level override and loot for us, and `GetSpawnedChildrenLivingCharacterCount()` is
  a purpose-built one-bit verifier. ⚠ Impl `0x5611A50` is likewise **all-zero in all 10 dumps**, and
  the param is a struct by value.
  ⚠⚠ **And LVL_Tutorial contains no spawner at all** — MEASURED: `tools/extractor/out/LVL_Tutorial.json`
  has **0** hits for `Spawner`, **0** for `BiomeManager`, **0** for `Kaiju`. The 3 `Minion` / 8 `Bot`
  hits are `RecastNavMesh_UAID_…-Minion` / `-HeroBot` **agent profile names**, not actors. The
  tutorial's `BP_LokiSpawner_Basics_*` and `BP_Minion_KaijuAxeLeader_Stagger_Tutorial` are in the
  pak but live in the 68 `_Generated_` World-Partition cells, **which have never been dumped**.

---

## 6. The corrected plan to enemies / damage / abilities

### 6.1 The severity re-grade, first

FK-6 was rated **HIGH** *because it gates enemies, damage, abilities*. It does not.
`docs/tutorial-launch-marker.txt` (live, S103) records the hero with **no ability system at all**:

```
[GAS] AFTER  AbilitySystemComponentStorage @0xF00 = 0x0 (NULL)
[GAS] AFTER  IsAbilitySystemInitialized -> res=0
[GAS] GetLokiAbilitySystem_BP -> 0x0 (NULL)
[GAS] ===== RESULT: initialised 0 -> 0  *** STILL NOT INITIALISED *** =====
```

A perfect enemy spawn still yields no damage. **The cheat surface is neither necessary nor
sufficient for the stated goal.** Re-grade FK-6 **MEDIUM**.

The load-bearing idea in the whole census is not a cheat: **a minion's ability system is
self-owned**, so damage and ability-activation can be *proven* before the hero's carrier chain
closes. Evidence: `Barracuda/Spawners/BarracudaMinionSpawner.as.txt` `AuthSpawnWave()` does
`v52 = v38.GetLokiAbilitySystem_BP(); v66 = v52.MakeEffectContext();
v52.ApplyGameplayEffectToSelf(StartingEffects[i], 0, v66, false)` with **no null check on v52**;
corroborated by S100's world sweep finding 424 live non-CDO ASCs, 344 `InitAbilityActorInfo`'d, on
plain level actors in force-open with no server.

### 6.2 Rules the plan obeys

- **Single-variable changes.** No bundled steps. (Project rule; violated by the first draft.)
- **New work goes in the `sp` shim, never `play`.** `RM_PLAY` holds the `ProcessInternal` hook
  installed for 600,000 ms — by the project's own definition a permanently-installed PI hook — and
  `tutorial_launch.cpp` takes **no** `Local\SuperviveMissionsPIHook` mutex. Harmless today only
  because `-Hook <path>` injects exactly one DLL. **Add the mutex before any run that combines
  force-open with the default shim set.**
- **SEH only.** `CallNativeGuarded` / `CallBPGuarded` use `__try/__except`
  (`tutorial_launch.cpp:321-323, 379-390`), not C++ EH. Keep new code in that idiom.
- **≤60 s per run**, flush the marker per step. The 173-201 s UAF is measured; pinning it on S93's
  `CameraActor` is inference, and `sp` spawns no CameraActor — plausible, not bankable.
- **No `.text` patches.**

### 6.3 The steps

Venue: **OFF** = offline · **MENU** = plain menu, no injection · **SP** = force-open + `sp` shim.

| # | step | one-bit criterion | risk | venue |
|---|---|---|---|---|
| **O1** | Dump the 68 `_Generated_` World-Partition cells; grep `LokiSpawner`, `BP_Minion_`, `BiomeManager` | does **any** cell place a spawner or minion? | none | OFF |
| **O2** | Read a concrete ability/GE class off `BP_HERO_Ronin_C`'s CDO and the `GS_KaijuAxeLeader_*` paths | is a **named** class in hand? (step 5 is unrunnable without one) | none | OFF |
| **M1** | Fix `tools/re/cheat_enum.py:175` (`cn == "Class"` → `cn.endswith("Class")`); then at the menu: `obj_by_class.py … _AS`, and read `PC->CheatManager` | **either** any `_AS` UClass exists **or** `CheatManager` is non-null ⇒ FK-6 retains value; **both** no ⇒ close FK-6 and stop spending on it | none | MENU |
| **R0** | `CallBPGuarded` on any zero-arg script `_Implementation` of the live `LokiPlayerController_AS` | a `[BPC] refuse: … num=0` line ⇒ use `CallNativeGuarded` (the log already printed the thunk) | none | SP |
| **1** | `gas_recon.py` §B/§C on an **already-initialised world ASC** (`BP_PineTree_ScavBay_C`; 344 have Owner/Avatar set) | **is any Health attribute non-zero anywhere in this world?** decides whether "health drops" is even observable | none (RPM read) | SP |
| **2a** | Write `Health` BaseValue+CurrentValue = 1000 on that set (`FGameplayAttributeData` +0x8/+0xC) | does 1000 stick on read-back? (proves the field, not the API) | none | SP |
| **2b** | `CallNativeGuarded(ULokiAbilitySystemComponent::AdjustHealth, ctx = that ASC, float −250)` | **read-back == 750 ⇒ GOAL (b), DAMAGE, ACHIEVED** — no enemy, no spawn, no cheat | low | SP |
| **3** | **Grant only:** `BP_AuthGiveAbilityWithInputID(<O2 class>, 1, inputID, src, 0)` on that same ASC | `ActivatableAbilities` Num 0→1, read by **RPM on the array**, not a getter | medium | SP |
| **4** | **Activate, separate run, last:** `TryActivateAbilityByInputID(inputID)` | returns true **and** `GetActiveSpells()` Num > 0 ⇒ **GOAL (c)** | **highest** | SP |
| **5** | Hostile actor via the **proven** `SpawnActorCls(BP_Minion_*)`; zero `AutoPossessAI` **before** finishing the spawn; then `ULokiTeamStatics::SetTeamForActor(minion, enemyTeam)` | live actor of that class in `obj_by_class.py` **and** `IsEnemyTeam(hero, minion)` true ⇒ **GOAL (a)** | medium | SP |
| **6** | `AdjustHealth` on the **minion's own** ASC | its Health drops ⇒ first damage on a real enemy | low | SP |
| **7** | *(parallel, free)* R1: construct a `UCheatManager` and call `God` | the engine's `God mode on/off` `ClientMessage` in `Loki.log` | low | SP |

### 6.4 Why this ordering

The step that makes everything else moot — *"does a GAS mutation execute at all in this world"* — is
answerable with **zero spawns** on objects that already exist. It is now step 1-2, not step 4.
Nothing in steps 1-4 requires the hero to be visible, so `RM_PLAY` (the flakiest stage) stays out of
the measurement entirely.

### 6.5 Risk notes that the first draft got backwards

- **Step 4 (`TryActivateAbilityByInputID`) is the highest risk in the plan, not the spawn.**
  Activation instantiates a `UGameplayAbility` and runs its graph against an ASC whose `AvatarActor`
  may be null — precisely the S82 shape (force-calling something that *constructs objects* over
  unwired state). Grant and activate must be **different runs**, activate last, gated on a measured
  non-null `AvatarActor`.
- **`AdjustHealth` beats the spec route.** `void AdjustHealth(float32 HealthDelta)` — **one float**.
  `MakeOutgoingSpec` / `BP_ApplyGameplayEffectSpecToSelf` pass TSharedPtr-backed handles **by value**
  through a hand-built `FFrame` buffer. And `ULokiCharacterGlobals.AdjustHealthEffect :
  TSubclassOf<UGameplayEffect>` shows `AdjustHealth` *is* the game's own GE wrapper — do not
  hand-build a spec.
- **Step 5 must neutralise `AutoPossessAI` before `FinishSpawningActor`.** An AI-possessed character
  starts BT + navmesh queries + CMC tick — the exact per-frame-movement shape that pinned the game
  thread 20 s in S81 and dropped the connection. Its value on `BP_Minion_*` is **unmeasured**; read
  and log it.
- **Do not plan the damage demo around `AuthCheatSetHealth`.** It and `AuthCheatSetMana` live on
  `ALokiCharacter` (not any cheat-named class — so **S74's class-name filter missed them, and any
  future census must scan by FUNCTION name**) and **share one exec thunk** `0x52FD620`. Two setters
  writing two different attributes cannot legitimately share a tail dispatch. Verify before use.
- **⚠ A prohibition on the standing "do not do this" list is stale and must be corrected.**
  `docs/coverage-audit-s101.md:611` says *"Do not spawn `LokiPlayerState_HeroAffiliated`
  client-side. Live-proven instant crash, uncatchable."* That is **S80, on the DS route, direct
  spawn**. **S103 falsified it on this route**: `docs/tutorial-launch-marker.txt:33` records
  `[QST] LokiPlayerState_HeroAffiliated FinishSpawning -> res=0x20076AF12C0`, the constructor built
  the ASC, `K2_InitStats` created both attribute sets, and the run reached `[SP] done`. **Fix that
  line** — the exact generalisation FK-6 exists to stop is re-forming *inside the list we use to
  prevent it*.
- **Watch `bSkipSpawnWithArmoryOff`.** `ALokiBattleRoyaleSpawner` reflects
  `bSkipSpawnWithArmoryOff`, `bGameModeCanPreventSpawn`, `bUsedThisPhase`, `bExclusiveSpawner`,
  `bSkipSpawnIfSpawnedChildrenExist`. If a spawner has the first set and force-open's GameState has
  the Armory off, `SpawnSingleActor` silently no-ops — and the fix is
  `AuthCheatUnlockFullArmory`, one of the four script cheats that still works. Read the five
  booleans **before** concluding a spawn call failed.

### 6.6 Live probes, in priority order

| P | question | probe | one bit |
|---|---|---|---|
| **P1** | Does `LokiPlayerCheats_AS` exist live, and does *any* `_AS` UClass? | Plain menu, no injection: `python tools/re/obj_by_class.py <PID> <BASE> _AS` (no `cn == "Class"` gate) **and** the fixed `cheat_enum.py auto auto cheat` | any `_AS` UClass at all. **No `_AS` anything ⇒ the whole script surface is unreachable and FK-6 closes for a different reason.** ~2 min, gates everything |
| **P2** | Which `ALokiPlayerCheats` vtable slot is which `Server*` RPC? | For each `Server*` UFunction read `UFunction.Func @ +0xE0` and disasm ~0x100 B **live** (pages decrypt on demand); record the `jmp qword ptr [rax+disp]` displacement | any `ServerCheatSpawn*` resolving to something other than `0x0F7EC20` **reopens the native spawn route** |
| **P3** | Is `PC->CheatManager` non-null / is a `UCheatManager` in GUObjectArray? | `obj_by_class.py CheatManager`; RPM the reflected `CheatManager` member | non-null ⇒ R1 needs no construction at all |
| **P4** | `WispControllerClass` / `WispHeroClass` non-null? | RPM `obj+0x428`, `obj+0x430`; resolve each UClass name | both non-null ⇒ `ServerSpawnWispAS` is safe to fire; else use the FFA recipe (§5.3.3) |
| **P5** | Does a fresh `BP_Minion_*` return a non-null ASC? | spawn deferred → `SetTeamForActor` → finish → read the **component pointer**, not `GetLokiAbilitySystem_BP` | **the pivot of §6.3.** ⚠ `GetLokiAbilitySystem_BP` returns the storage *cache*, not the ASC — S103 shows it null while `carrier.AbilitySystemComponent@0x3E8` was `0x1FEAA34E680`. A null getter means "cache unwired", not "no ASC" |
| **P6** | Re-light the 31 dark `ALokiPlayerCheats` thunks | `usmapdump dumpimage <proc> dumps/ingame-cheats/` from the **deepest gameplay state reachable**, then re-run `cheat_impl_census.py` | UNVERIFIABLE count < 31 ⇒ coverage, not stripping, was the limit |
| **P7** | Does `~` open a console? | press it; else look for a live `UConsole` | free; **does not change the cheat verdict** |

---

## 7. What is genuinely still closed, and what is merely unread

### 7.1 CLOSED — measured, do not re-open

| thing | measurement |
|---|---|
| native hotkey dispatch | `AreHotkeyCheatsEnabled_Impl` = `xor al,al; ret`; the flag `EnableHotkeyCheats` writes at `+0x390` is never read |
| Blueprint cheat exec-gates | `AdminOnly` / `HotkeyCheatsEnabledOnly` → `mov byte [rdx],1; ret` = always the `Hidden` pin |
| `PC->CheatManager` ever becoming non-null by an in-game path | `AddCheats` (slot 477) = `ret 0` in **both** PC vtables; `UE_WITH_CHEAT_MANAGER == 0` |
| every accessor that would hand you a cheats object | 4 getters + `GetLocalLokiPlayerCheatsBP` → `xor eax,eax; ret` |
| `ConsoleCommandCheat*` as console commands | `Exec` 0 of 500 |
| the 43 `Cheat*` input actions | 43/43 located in content, 0/43 with a dispatch target |
| native `ShowDebugMenu` / `ToggleDebugMenu` | → `0x5254180` → `jmp 0xF7EC20` |
| `ServerBoostPlayer_Implementation` | vtable slot 260 = `ret 0` |
| 2 of the 43 script cheats (`BP_Cheat{Night,Day}To*`) | `UFUNCTION(…, NoOp)`, 1 dword |

### 7.2 UNREAD — not closed. The state that would decrypt it.

**31 of 65 (48%) `ALokiPlayerCheats` thunks are all-zero in all 10 dumps** — and it is exactly the
verbs (§3.2). Also dark everywhere: `ServerCheatSpawnActor` thunk `0x5426A50`, `CheatChangeHero`
`0x534BE80`, `CheatSetTeamEliminated` `0x5422250`, `ULokiBotSpawnerComponent::SpawnBot` impl
`0x556D910`, `ALokiBattleRoyaleSpawner::SpawnSingleActor` impl `0x5611A50`,
`AuthCheatSetHealth/Mana` shared thunk `0x52FD620` *(this last one is decrypted in `dumps/toggles`)*.

`.text` is demand-decrypted; a page is zero because **the code never ran in any captured state**,
not because it was stripped. **S74's `ServerCheatSpawnActor_Impl = ret` was a LIVE read and cannot be
reproduced or refuted offline today. It stands.** Do not claim the native Loki cheats are stubbed
beyond the ones listed in §7.1.

**The state that fixes it:** `usmapdump dumpimage` from a state where cheat/spawner code has RUN —
the force-open tutorial with a spawned + possessed hero, ideally after any cheat invocation. All ten
existing dumps are menu-ish. One good in-match dump re-lights the whole band. *(Note
`docs/strxref-state-coverage.md`: `mergedumps` wrongly rejects different-ImageBase inputs; `.text` is
100% RIP-relative and byte-identical across ASLR bases — **0 page conflicts** measured across all
10 dumps, including `dumps/rcb` at a different base. Fix `mergedumps.go:154` or union `.text`
directly.)*

### 7.3 UNKNOWN — no instrument has been pointed at it

- **Does `ALokiPlayerCheats_AS` ever exist at runtime?** The single most important open question on
  Surface C. Both existing enumerators are structurally blind to it (§5.3.1). Probe P1.
- **Which primitive drives an AS UFunction?** `CallBPGuarded` vs `CallNativeGuarded`. Probe R0.
- **Does a script `NetServer` UFunction execute its bytecode locally on an authority instance?**
  Two independent arguments say yes (§5.3.4); neither is a measurement.
- **Is `ALLOW_CONSOLE` compiled in?** Undecidable by any string scan — the flag guards a
  construction site and leaves no literal. Strategically demoted (§1.3).

---

## 8. Method note — how this differs from S74's error, and how not to commit its mirror image

### 8.1 S74's error, in one sentence

Two correct measurements of *implementations* were generalised to sixty-five functions, then to a
whole *class*, then to a whole *technique* ("the cheat surface as a shortcut is CLOSED"), then used
retroactively ("explains every no-op") — with the generalisation licensed by a misreading of an
ICF fold pool as a "stripped-cheat region".

### 8.2 The mirror-image error, and how close this workflow came to it

The tempting inversion was: *"219 native entries, not 65 — and 173 of them are REAL, so S74 is
refuted."* That number came from classifying **exec thunks**. An auto-generated `DECLARE_FUNCTION`
thunk **always** contains real code — it unpacks `FFrame` params — even when the
`_Implementation` it calls is `ret`. The proof is in the same data: `AreHotkeyCheatsEnabled`'s thunk
is 43 bytes of genuine instructions and the impl it calls is `xor al,al; ret`. **A thunk census says
nothing about whether bodies were stripped.** (And 219 was itself the inheritance chain, §3.5.)

Publishing "219 real cheat functions" would have been FK-6 with the sign flipped: same instrument
error, same over-generalisation, opposite conclusion, equally wrong.

### 8.3 What this session did differently — and what it found doing it

1. **Re-measured the load-bearing bytes myself** rather than citing them. Both S74 addresses, both
   ICF fold targets, the exec-gate, the hotkey setter, `God`, `Summon`, and the full
   `EnableCheats → AddCheats` virtual chain.
2. **Read the engine source the claim is about.** That is what turned "slot 477 is probably
   AddCheats" into a near-certainty: the observed `xor edx,edx` is not an anomaly, it is the
   *signature of the `#else UE_BUILD_SHIPPING` branch*. Same move that killed FK-2.
3. **Audited the audit.** I re-resolved every census row with a deliberately *different* rule and
   isolated the one subset where the answer is not a judgement call — thunks ending in an
   unambiguous tail-`jmp` out of the function. **13 such rows. The census agrees on 1 and is wrong
   on 12.** I hand-disassembled the tail targets to confirm they are not further hops
   (e.g. `ServerToggleAILogging` tail-jumps to `0x12643D0` = `mov [rip+…],rcx; ret`, a one-line
   setter, **not** the `mov al,1; ret` at `0x0B9E1F0` the census reported).
   **Three of those 12 flip a `LokiPlayerCheats` verdict from REAL to empty:**
   `CheatTravelToMainMenu`, `LogActorsAtWorldOrigin`, `TryInitializeAfterController` all share exec
   thunk `0x5254180`, which is `P_FINISH ; jmp 0xF7EC20` — `ret 0`. That is what moved the
   LokiPlayerCheats real-body count from 17 to 12 (§3.2) — **toward** S74, not away.
   > ⚠ **Do NOT extrapolate "the census is 92% wrong."** That would be the same over-generalisation
   > in a new costume. The 13 tail-jmp rows are the subset I can adjudicate; the ~160 rows resolved
   > via `call rel32` are **not** invalidated by this and my own naive rule is *worse* than the
   > census's on them (it picks FString/TArray teardown calls). The correct statement:
   > **the census's per-row verdicts are PROVISIONAL until re-audited, and its tail-jmp handling is
   > measurably broken.** `docs/fk6-cheat-impl-census.csv` is retained with that caveat attached.
4. **Reported the counter-measurement.** The fair-census stub report for the AS layer (46/1,463 =
   3.1% baseline vs 0/51 in the cheat module) is stated because it could have gone the other way.
5. **Marked every claim.** MEASURED / STRONG_INFERENCE / UNKNOWN, per claim, not per document.
6. **Named the zero-information evidence** instead of counting it: `NetValidate` absent 500/500;
   `UConsole`/`ConsoleKeys`/`Command not recognized` all ship in stock UE regardless of
   `ALLOW_CONSOLE`; `CheatManager`/`CheatClass` UPROPERTYs unguarded in stock UE. Four pieces of
   evidence that look supportive and discriminate nothing.
7. **Separated "present" from "callable" from "effective"** in the verdict itself, because that
   three-way slide is the whole shape of this false-known.

### 8.4 Three reusable rules this produced

1. **A shared exec-thunk address proves a shared implementation — never that the implementation is
   empty.** Resolve the fold target by disassembling it. (`CheatTravelToMainMenu` and
   `TryInitializeAfterController` share a thunk *and* are both empty; `AuthCheatSetHealth`/`SetMana`
   share one and are unknown.)
2. **Rarity is not a stub detector under `/OPT:ICF` — it is an anti-detector.** Stubs have thousands
   of call sites.
3. **A census filtered by CLASS name misses functions named `*Cheat*` on ordinary classes.**
   `ALokiCharacter::AuthCheatSetHealth` is the proof. Scan by function name.

---

## 9. One-paragraph answer, for the next reader

The cheat surface is **present and not yet proven callable**. The native hotkey path is closed
(measured, with a mechanism). The native `ALokiPlayerCheats` class is closed *at its accessors and
its constructor*, not at its bodies — `UE_WITH_CHEAT_MANAGER == 0`, so `AddCheats` is `ret 0` and
every getter returns `nullptr`; that is a constructor strip, which a shim defeats. About half of that
class's implementations cannot be read offline at all, and every interesting verb is in that half,
so S74's live `ServerCheatSpawnActor = ret` stands unchallenged. `UCheatManager` keeps 39 real
bodies including `Summon`, `Teleport`, `God` and `DamageTarget`, and nobody has ever tried to
construct one. The Angelscript cheat family ships 51 real bytecode bodies that no C++ guard could
strip — but most of them die on the same null accessors, the class has never been seen alive, the
console cannot reach any of them, and the survivor worth having, `ServerSpawnWispAS`, needs two
class pointers written first and then deliberately downs what it spawns. **And none of it is on the
critical path:** the hero has no ability system, a minion's is self-owned, and damage can be proven
today with one float on an ASC that already exists.
