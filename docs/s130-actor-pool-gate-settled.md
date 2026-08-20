# S130 — THE ACTOR-POOL GATE IS NAMED, AND THE ACTOR POOL IS **NOT** FK-22's BLOCKER

> ★★★★★ **UPDATE, SAME DAY — §11 SETTLES C7 OFFLINE AND IT IS THE ANSWER.**
> The pooled spawn returns NULL because **`AActor::bCanEverReplicate` is `true` on the drop pod's
> CDO** and the acquire refuses any replicating class (`C7 @ 0x564820C`). `AActor`'s C++ ctor sets
> that byte to 1 (`0x03371841`), neither Blueprint overrides it, and `SpawnDropPodForTeam` bails on
> the null **with no fallback** — which is exactly S127's bail 2. **§8's Phase A4 was pre-registered
> as a live read and did not need one.**
> ✅✅ **AND §12 THEN FLEW THE ONE READ THAT WAS LEFT: the RUNTIME CDO byte EQUALS the cooked class
> default — 8/8 pre-registered predictions, two-sided controls on two offsets, one clean MENU launch,
> read-only RPM. C7 FIRES, and the last [I] in the chain is now [M].**
> Read §11 then §12; §4's C7 row is superseded by them.

**Date:** 2026-08-19/20. **Offline: zero launches, zero injections, zero `.text` writes.**
Images: `dumps/s129-poolgate/SUPERVIVE-Win64-Shipping.dump.exe` (ImageBase `0x7FF7B86D0000`, `.text`
52.9 % decrypted), cross-checked against `dumps/merged2.dump.exe` and `dumps/tutorial-hero/`, plus the
already-extracted asset corpus in `tools/extractor/out/`.

Method: one session-lead thread + six parallel decode lanes, **each adversarially verified by an
independent agent that re-ran the commands rather than checking the quotes.** Verifier scorecard:
11/16, 10/13, 12/22 (9 downgrades, **1 REFUTED**), 13/16, 8/9, 7/13 (5 downgrades, **1 REFUTED**).
Raw lane + verdict JSON preserved in `scratchpad/s130/lanes/`; the session-lead thread in
`scratchpad/s130/session-lead-thread.md`.

---

## 0. VERDICT

1. ★★★★★ **THE GATE IS NAMED [M]: `ALokiGameState::bSupportsActorPoolPriming`, a plain
   `UPROPERTY(EditDefaultsOnly, AdvancedDisplay) bool` at `ALokiGameState + 0x898`.**
   `ULokiActorPoolManager` vtable slot 90 (disp `0x2D0`) returns
   `Cast<ALokiGameState>(GetWorld()->GameState)->bSupportsActorPoolPriming`.
2. ★★★★★ **AND THE CAUSE IS IN THE SHIPPED ASSET, NOT IN CODE [M]: the C++ constructor sets it
   `true`, and `BP_LokiGameState_Tutorial`'s own class default serializes it `False`.**
   The tutorial world runs `BP_LokiGameState_Tutorial_C` (S124, live). That is, exactly and
   sufficiently, why `PrimePools : Feature is not enabled, skipping.` prints.
3. ⚠⚠⚠ **THE HEADLINE CORRECTION — S128's §23.3 suspicion is REFUTED. A disabled / unprimed actor
   pool CANNOT produce the observed NULL [M].** The pooled acquire looks the class up with a
   **`TMap::FindOrAdd`** (which is never null), and on a pool miss takes an **explicitly shipped
   fallback** — `.rdata 0x08B06440 U 'Failed to find an actor in the pool for %s, spawning a new
   instance from scratch.'` — and calls a normal `UWorld::SpawnActor`.
   ⇒ **"the actor pool is the wall" is FALSE. FK-22's blocker chain must be re-pointed.**
4. **The pooled spawn never consults the gate [M]**, established three times by disjoint methods
   (session lead: capstone scan of 8 chained extents; lane: byte-regex over full `.pdata` extents;
   verifier: independent capstone decode). The gate is called at **exactly one address image-wide in
   this family**: `0x33560C5`, inside `PrimePools`.
5. **The hand-spawn bypass hits a FIFTH, previously unrecorded wall [M]** —
   `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` (impl `0x55CD510`) is a real body
   that **always** takes its failure branch.
6. **There is no injection-free ini fix [M].** `ActorPoolManagerPrimingConfig` is a **USTRUCT with
   zero reflected properties and no UHT consumer**; neither pool-manager class is a config class; and
   **0 of `ALokiGameState`'s 155 reflected properties carry `CPF_Config`.**

---

## 1. THE GATE — every link measured

```
ULokiActorPoolManager::vtable[90]   (rva 0x56363F0, 93 B, fold multiplicity 1)

  call 0x0B9E1F0            ; Super::  -> `mov al,1; ret`   [!] a 26,444-way fold: NON-IDENTIFYING.
  test al,al / je FAIL      ;           the *engine vtable slot* is a return-true stub [M];
                            ;           the ADDRESS names nothing.
  mov rcx,rbx / call 0x12C7260      ; slot 49 = GetWorld  [!] 2,823 pointer occurrences: a shared thunk
  test rax,rax / je FAIL
  lea rbx,[rax+0x258]               ; &UWorld::GameState
  cmp qword ptr [rbx],0 / je FAIL
  call 0x5380690                    ; ALokiGameState::GetPrivateStaticClass  [M]
  mov rdx,rax / mov rcx,rbx / call 0x12C7DD0   ; IsA / class-chain walk
  test al,al / je FAIL
  mov rax,[rbx] / test rax,rax / je FAIL
  movzx eax, byte ptr [rax + 0x898] ; bytes 0F B6 80 98 08 00 00 -- NO mask, the whole byte
  ret
FAIL: xor al,al / ret
```

**Callee identifications, each measured:**
* `0x5380690` = `ALokiGameState::GetPrivateStaticClass` — `strxref func` shows the
  `GetPrivateStaticClassBody` literal triple `'ALokiGameState'` / `'/Script/Loki'` / `'Game'`, and
  `vtables.py name ALokiGameState` independently reports `gpsc 0x5380690`.
* `0x12C7DD0` = an `IsA`: `mov rbx,[rcx]` → `mov rbx,[rbx+0x18]` (this build's measured `classOff`)
  → `FStructBaseChain` walk on `[UClass+0x38]` / `[UClass+0x40]`.
* ★ **`UWorld + 0x258` = `UWorld::GameState` [M], from a third unrelated function.**
  `UGameplayStatics::GetGameState` (exec thunk `0x38047F0`) ends:
  `call 0x3EDBE70` (`UEngine::GetWorldFromContextObject`) → `mov rax,[rax+0x258]` → store to the
  return slot.
* A **fourth** site uses the identical `ALokiGameState::StaticClass` + `IsA` + `[+0x258]` idiom at
  `0x5608F9C` — the same compiler idiom, **not** byte-identical (a verifier correction to the
  original wording).

**The property, named two independent ways [M]:**
* **UHT record.** `FBoolPropertyParams` at `.rdata 0x08983A50`: `NameUTF8 → 0x08986178
  'bSupportsActorPoolPriming'`, `RepNotifyFunc = 0`, `PropertyFlags = 0x0010040000010001`,
  `SizeOfOuter = 0xB20`. Its **`SetBitFunc` is `.text 0x053800D0` = `C6 81 98 08 00 00 01 C3` =
  `mov byte ptr [rcx+0x898], 1; ret`** — **fold multiplicity 1**, byte-identical in all three images.
* **Ownership.** The record has exactly one qword pointer to it: `PropPointers` slot
  `.rdata 0x08984AF0`, **index 106 of the 155-entry array at `0x089847A0`**, owned by the
  `FClassParams` at `0x08985450`. Corroborated by three offsets in that same array matching
  previously-measured project facts: `CurrentPhase @ 0xA44`, `MatchStartDetails @ 0x738`.
* **It is the ONLY bool UPROPERTY at offset `0x898` image-wide** — a sweep of all **13,156** Bool
  records (unit: UHT records), 0 coverage-blocked, 0 unrecognised.
* ★ **Decoder control:** `mov` vs `or` in `SetBitFunc` partitions **exactly** on the `0x40` gen-flag
  bit — 2,791 `or` (bitfield bools) == 2,791 records without `0x40`; 10,310 `mov` + 55 null == 10,365
  records with it. **Zero disagreement**, so the bool decoder is calibrated, not assumed.

**Flags [M]:** `0x0010040000010001` = `Edit | DisableEditOnInstance | AdvancedDisplay |
NativeAccessSpecifierPublic`, **no unknown bits** ⇒ `UPROPERTY(EditDefaultsOnly, AdvancedDisplay)`.
`CPF_Config` (0x4000) **clear**, `CPF_Net` (0x20) **clear**, `BlueprintVisible` **clear**.
⇒ no ini route, no replication route, no Blueprint accessor.

---

## 2. WHY THE GATE READS FALSE — it is a shipped Blueprint class default

| fact | evidence | grade |
|---|---|---|
| C++ ctor sets it **TRUE** | `.text 0x05676F10  c6 87 98 08 00 00 01  mov byte ptr [rdi+0x898], 1`, inside the same chained ctor function as CLAUDE.md's already-measured `0x056772CF mov byte [rdi+0xa44], r12b` (`CurrentPhase = 0`); no branch spans it | **[M]** |
| `BP_LokiGameState_Tutorial` overrides it **False** | `tools/extractor/out/bpdump_BP_LokiGameState_Tutorial_PROPS.txt:52` → `- bSupportsActorPoolPriming (BoolProperty) = False (BoolProperty)` | **[M]** |
| the tutorial world uses that class | S124 measured the live GameState as `BP_LokiGameState_Tutorial_C` | **[M, prior]** |

★ **Family control across all six GameState Blueprints [M]** — three override it and **every override
is `False`** (`_Tutorial`, `_PvE_Holdout`, `_FFA`); three do not serialize the key at all and
therefore inherit the native `true` (`BP_LokiGameState`, `BP_LokiGameStateRounds`, `_Battlefield`).
Their PROPS dumps are populated (136 / 69 / 138 lines), so those absences are a real
inherit-the-default, **not** an empty-dump artifact.
★ A BP CDO serializes **deltas against its archetype**, so the mere *presence* of the override is
independent corroboration that the native default is `true`.

⇒ ★★ **the pool is off in the tutorial BY DESIGN, in data, and it is off in exactly the three
non-BR modes.** That is a coherent shipping decision — not a bug, and not something we caused.

---

## 3. THE CORRECTION THAT MATTERS: AN UNPRIMED POOL CANNOT RETURN NULL

`docs/fk22-dropphase-reachability.md` §23.3 recorded, correctly graded **[I]**:

> *"that `PrimePools : Feature is not enabled` is WHY … the log line and the null are consistent and
> no other cause is in evidence"*

**That inference is now REFUTED at the mechanism [M].**

* **The pool lookup cannot fail.** `0x334E7A0` (283 B, `.pdata` EXACT) is a **`TMap::FindOrAdd`**: it
  has exactly **one** `ret` (`0x334E8BA`) and every path returns `MapData + idx*0x28 + 8`; on a miss
  it calls `0x334E5D0` to **insert first**. It is never null.
* **A pool miss has a shipped fallback.** `0x56482F0 cmp dword ptr [rax+8], r14d / jle 0x5648353`
  skips the reuse loop when `Num <= 0`; control reaches `0x5648D27`, whose block formats
  **`.rdata 0x08B06440 U 'Failed to find an actor in the pool for %s, spawning a new instance from
  scratch.'`** (4 code refs; the one in this chain is `site 0x5648D48` in `fn 0x5648CDC`, a chained
  `.pdata` row of `0x5648050`) and **falls through** to `0x5648D83`.
* **The fallback spawns normally.** `0x5648D83 mov rax,[rsi] / mov rcx,rsi / call qword ptr
  [rax+0x188]` (slot 49 = `GetWorld`) → `0x5648E48 call 0x39C3DB0` = `UWorld::SpawnActor`
  (independently attributed by `strxref func` via ten literals) → the actor is returned.

⇒ **"priming never ran" is not a null-producing condition anywhere on this path.**

⚠ **And the message can never be observed, so its absence proves nothing.** The emit call at
`0x5648D6F` targets the universal fold `0x00F7EC20` (`c2 00 00` = `ret 0`, **4,972 direct call sites**
image-wide) — the log is **stripped**. Consistent with **0 occurrences across the 69-file log corpus**
(unit: log files). ⇒ do **not** read that silence as "the fallback was not taken."

---

## 4. WHAT *CAN* RETURN NULL — the complete enumeration

Chain [M]: `SpawnPoolableActorFromClass` exec thunk `0x537EEE0` → impl **`0x566FF50`** → `0x5647F00`
→ acquire **`0x5648050`** (real extent `0x5648050..0x5648EC6` = **3,702 B** over 3 chained `.pdata`
rows — the "1,086 B" its first row reports is *not* the function size).
`…Deferred` thunk `0x537F1A0` → impl **`0x5670090`** → calls `0x5648050` **directly** (no `0x5647F00`).
Both are entries [150] and [151] of a 159-entry `FClassFunctionLinkInfo` table at
`0x08978D98..0x08979787`; they are **static helpers taking a WorldContextObject** [M], not pool-manager
members. (The owning class name was never read — calling it "a Loki BlueprintFunctionLibrary" is [I].)

**Outer preconditions (both impls; the ordinary spawn path has NONE of them) [M]:**
`O6` `GetWorldFromContextObject(ctx,1) == null` · `O7` `World->GameState == null` ·
`O8` `!GameState->IsA(ALokiGameState)` · `O9` `GameState == null`.
★ **DIFFERENTIAL CONTROL [M]:** the ordinary `SpawnActorFromClass` impl `0x566EB70` makes **zero**
calls to `ALokiGameState::StaticClass` and has **zero** `lea [+0x258]`; both pooled impls have
**exactly one of each**. *That is the precise extra precondition the pooled path adds.*

**Acquire NULL conditions — exactly nine edges to the null epilogue `0x5648EA1` [M]:**

| # | site | condition | live status |
|---|---|---|---|
| C1 | `0x56480B8` | `Class == null` | excluded — P3 spawned it |
| C2 | `0x56480C6` | `AActor::StaticClass() == null` | [I] unreachable |
| C3/C4 | `0x56480FE` / `0x564810C` | `!Class->IsChildOf(AActor)` | excluded |
| C5 | `0x5648119` | `Class == null` re-read | excluded |
| C6 | `0x564817A` | `test byte [Class+0xdc],1` — [I] `CLASS_Abstract` | excluded by control (the ordinary path also rejects abstract) |
| **C7** | `0x5648210` | **`CDO->bCanEverReplicate != 0`** | ✅ **SETTLED — THIS IS THE NULL (§11).** `AActor+0x6C` = `bCanEverReplicate` [M]; `AActor`'s ctor sets it **1** at `0x03371841` [M]; neither Blueprint overrides it [M]; cooked effective value `true` [M]. ⚠ [M] for the COOKED value, [I, strong] for the RUNTIME CDO byte — see §11.5 |
| **C8** | `0x5648D97` | **`PoolMgr->GetWorld() == null`** | **LIVE CANDIDATE** |
| **C9** | `0x5648E6F` | **`UWorld::SpawnActor` returned null, OR was never invoked because `rbx == 0` at `0x5648E34`** (verifier correction) | **LIVE CANDIDATE** |

⚠ **A NOT-null branch worth knowing:** `0x5648216 cmp byte ptr [CDO+0x2d3], 0 / je 0x5648D83` — the
per-class "poolable" byte sends you to the **fresh-spawn fallback**, not to null. So a class that is
not registered poolable still spawns. (`+0x2D3` as "the poolable flag" is **[I]** — an unnamed CDO
byte. And `0x5648E71`, which reads `+0x2D3`/`+0x2D8` on the *spawned* actor and stores a derived bool
at `+0x374`, is **not** a CDO-consistency check; both its branches return the actor.)
⚠ **The failed-cast paths at `0x5648170` / `0x5648204` set `rax = 0` and then dereference
`[rax+0xdc]` / `[rax+0x6c]` — they would FAULT, not return null.**

★ **THE FREE PER-ATTEMPT RECEIPT, previously unused.** The non-deferred wrapper logs on NULL:
`.rdata 0x08B06390 U 'Failed to spawn actor of type %s.'` (exactly 2 code refs, both `ptr-tbl` — a
reference class a byte scan cannot see). It fired **exactly twice** in the S128 flight
(`docs/Loki-s128-poolspawn.log`, 02:00:41 and 02:02:10), naming `BP_DropPod_Tutorial_C`.
⇒ **[M] O6–O9 all PASSED in the live staged tutorial world** — the warning is emitted strictly
downstream of them. The NULL came from inside the acquire, i.e. **C7, C8 or C9**.
⇒ [I, strong] **the DEFERRED arm's null is SILENT** (its impl calls the acquire directly, bypassing
the warning site) — consistent with 2 warnings ~89 s apart, i.e. **one per injection, not two**.
**Do not read "no warning" as evidence about a deferred attempt.**
⇒ ★ **Grep `Failed to spawn actor of type` before any further inference about this path.** The
`PrimePools : Feature is not enabled` line occurs 68 times across 69 log files — ambient startup
noise. This one is attributable per attempt.

★ **S128's collision-confound elimination STANDS [M].** The probe's `ixColl` slot really was bound:
the result files print `Collision=2 (declared enum 'ESpawnActorCollisionHandlingMethod')` with
`NumParms=8`, the enum name read **live off the FProperty**. (A lane's inferred 7-argument signature
omitting a collision parameter is **[I] and wrong**; the live UHT read wins.)

---

## 5. REPAIR CLASSES, RANKED

| # | class | verdict |
|---|---|---|
| 1 | **ini / config, no injection** | **DEAD [M].** `CPF_Config` clear on the property; **0 of 155** `ALokiGameState` properties are config; `ActorPoolManagerPrimingConfig` is a USTRUCT with **zero** reflected properties, `PropertyArray = NULL`, `NumProperties = 0`, `SizeOf = 0xA8`, and **no** UHT consumer anywhere; neither pool-manager UCLASS carries `CLASS_Config` / `CLASS_DefaultConfig`; `PrimePools` reads no config literal. `Pooling.PrimingFrameBudget` exists as a string but **both its strings read `refs=0`** ⇒ that a working cvar exists is **[S]**, and it is pacing-only regardless. ★ **Independent corroboration from a completely different instrument (S101, `docs/config-control-plane-s101.md` §5):** `DefaultActorPoolManager.ini` is listed under `[Staging] +AllowedConfigFiles` but is **absent from the shipped 64-file config manifest** [M]. ⚠ That is corroboration, **not proof** — an ini being unshipped says nothing about whether a property is config-backed; the decisive evidence is `CPF_Config` clear on the property itself. Two unrelated instruments agreeing is what makes this row safe to act on. |
| 2 | **DATA poke `GameState+0x898 = 1` + direct call `PrimePools`** | **The correct way to turn the pool ON** — but see #4. Safest measured write class (nothing 0/22 · bytecode 0/9 vs transient `.text` 4/12 · standing `.text` 7/8). |
| 3 | **`PrimePools` alone** | Insufficient — the gate is *inside* the callee (`0x33560C5` precedes every functional block; the false arm is `0x33560EF jmp 0x33564E5`, straight to the epilogue). |
| 4 | **…AND NONE OF IT IS KNOWN TO FIX FK-22** | Because of §3. Enabling the pool is now a clean, cheap, well-understood experiment about a shipped design decision — it is **no longer the identified cause** of the drop-pod NULL. |

**Free handles [M]:** `GameState+0x428` = the cached `UActorPoolManager*` (lazy getter `0x3840490`;
the `+0x428` load is at `+0x1D`, after a stack frame and security cookie — the getter does **not**
begin with that load); `GameState+0x430` = its class, validated against
`UActorPoolManager::GetPrivateStaticClass` (`0x32A8570`). One RPM read; no call needed.
⚠ The getter's result is passed to the acquire **without a null check**, so a failure there faults
rather than returning NULL.

---

## 6. THE BYPASS — a FIFTH wall, previously unrecorded

`ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` (impl **`0x55CD510`**) is **REAL and
substantial, and can never complete [M]**: at `0x55CD572` it makes a direct rel32 call to
`0xF7EB50` (`33 c0 c3` = `xor eax,eax; ret`), then bails on the zero into a
*"…failed to get the round game mode"* log. Its dead tail `[0x55CD580, 0x55CD7FA)` has **zero**
external rel32 entries in s129, merged2 **and** tutorial-hero.
The same wall hits `AuthPlayerPreSpawnOnAddToPlane` (`0x55CD800`); `AuthPlayerEnterWorldNew` is an
outright empty fold. Only `AuthPlayerEnterWorld` (`0x55CCE70`) and
`AuthPlayerDetachPlayerFromRidable` (`0x55CCCB0`) survive without a round-game-mode hard bail.

⇒ **hand-spawning a pod gets a pod into the world and no rider.** Worth doing only as a *diagnostic*.

★★★★★ **AND THE LANE BUILT A NEW GENERAL INSTRUMENT WORTH MORE THAN THE FINDING: the `.data`
`{name_ptr, exec_thunk, impl}` record table routes AROUND coverage-blocked `.text` pages.** Because
the four fold addresses are known constants, the record's third field yields a REAL / EMPTY verdict
**without needing the code page decrypted.** FK-22 §2.5 classified **16 of 100** `(class, func)` keys
as COVERAGE-BLOCKED; this shows that verdict is an instrument limit for at least 6 of them (the five
`AuthPlayer*` entry points plus `GetLandingTeleportLocation`, all on page `0x5456000`).
**Re-running it over all 100 keys is free, offline, and unstarted.**
⚠ Validated in both directions on gold values (4/4 FK-1 stub records, 2 thunk-tail derivations, S124's
2 phase records reproduce byte-identically) — **but its negative control is degenerate**: Angelscript
names have **zero byte occurrences** in the image (measured: `SpawnDropPodForTeam`, `StartPodGameplay`,
`InitializeDropPod`, `GetPilotPlayerState` all ascii=0 utf16=0 in all three images, against controls
`AuthPlayerEnterWorldAttachedToRidable` ascii=1/utf16=2 and `GoToPhase` ascii=1). So "AS functions
have no record" is a fact about **name storage**, not about the record table. It remains a usable
discriminator; state it that way.

⚠ **REFUTED sub-claim (verifier):** *"`AuthSetSpawnTeamLeader` only feeds
`ALokiDropShip::GetTeamDropLeader`"* is false — `IsSpawnTeamLeader` has **three** Angelscript readers
(`LokiDropShip.as:306`, `LokiDropPod.as:3752`, `LokiDropPhase_PlayerStateComponent`), one of them
(`QueueCrewForPodSpawn`) on the leader-pod path being replicated. The "bypass avoids FK-1's stubs"
conclusion survives **only under `bIsTeamLeaderPod == false`**, which must be stated, because the route
as transcribed from `SpawnDropPodForTeam` passes `true`.
⚠ This is the **incomplete-enumeration failure mode FK-22 already recorded against a previous agent on
this exact function family** — it recurred, and only adversarial verification caught it.

---

## 7. `PrimePools` — graded

`0x3356000 .. 0x3356503` (1,284 B), **one `ret`**, all **38** branches internal — fully accounted for.

* **Not reflected [M]** (`strxref native "PrimePools"` → no ASCII reflection name) and **in no vtable
  or function-pointer table** ⇒ the only route is a **raw direct call** with a valid `this`.
* **One caller [M]:** `0x567AA50`, inside `fn 0x567A1B0` (3,919 B) carrying the literal
  `'ALokiGameState::BeginPlay'` — and `vtables.py name ALokiGameState` puts `0x567A1B0` at **slot
  119**, which CLAUDE.md independently records as `AActor` slot 119 / disp `0x3B8` = `BeginPlay`.
  ⇒ priming is designed to run **once**, from the GameState's `BeginPlay`, and **has already run and
  taken the skip branch** before any shim is injected.
* **ZERO module-image writes [M]**, verified mechanically: not one rip-relative memory *destination*
  in all 1,284 bytes, and no `VirtualProtect` shape. Non-stack writes are heap `UObject` fields
  `this+0x88, +0xD8, +0xE8, +0xE9` plus heap-buffer stores at
  `0x3356338 / 3E8 / 3F0 / 402 / 405 / 411 / 44E`. It reads **no** authority / role / NetMode state.
* **A PRE-gate block runs even when the gate is false** — it re-seeds `this->PoolableActorClasses`
  (`+0x88`) from the CDO.
* **TRUE path:** re-entrancy flag → optional slow AssetRegistry scan → analytics virtual (slot 91) →
  per-class filter loop (slot 93) → `UAssetManager::LoadAssetList` **async** load.
* ⚠ **`param2` (rdx) is dereferenced** and must be a readable buffer (demonstrated reach `+0xA1`;
  "≥0xA8" is [I]). It is consumed **only** by slot 91. On the *engine base* class slot 91 is the
  `ret 0` fold, so the fault risk applies only when the Loki override dispatches.
* ⚠ **The `Feature is not enabled` line cannot be silenced or amplified by `[Core.Log]`** — its
  `FLogCategoryBase` at `.data 0x9F7EDB8` reads `04 00 04 04`, i.e. `CompileTimeVerbosity = Display`
  (the name `LogActorPooling` is [I]; the neighbouring category at `0x9F7EDD0` reads `05 00 05 05` as
  a layout control).
* **Per-class priming filter vocabulary [M]:** `bCanPrimeOnClient` / `bCanPrimeOnServer` /
  `bCanPrimeInArena` / `bCanPrimeInBattleRoyale` (each `refs=1`, sites `0x0F124E6`–`0x0F12546`).
  ⚠ That these feed **slot 93** is **[I]** — no measured link exists.
* ⚠ *"The ActorPoolManager.cpp translation unit is fully enumerated by its string band"* is **[I] and
  weak** — string adjacency is not a TU boundary, and the file-path literal has zero code xrefs, so
  string-less functions in the TU are invisible. The fill/acquire split is supported instead by the
  acquire living at `0x5648050` in the **Loki** range.

---

## 8. PRE-REGISTERED EXPERIMENT (written before it runs)

**Phase A — read-only RPM on an already-staged tutorial world. Zero risk. Run first; it can falsify
the model at zero cost.** In order, read:

| # | read | pre-registered prediction |
|---|---|---|
| A1 | `World+0x258`, and that object's UClass name at `+0x18` | `BP_LokiGameState_Tutorial_C` |
| A2 | `byte [GS+0x898]` | **`0`** |
| A3 | `qword [GS+0x428]`, `[GS+0x430]` | non-null; class is `UActorPoolManager`-derived |
| A4 | `CDO(BP_DropPod_Tutorial_C) + 0x6C` | **`0`** — if NON-ZERO, **C7 alone is the entire NULL and pooling is irrelevant** |
| A5 | `CDO(BP_DropPod_Tutorial_C) + 0x2D3` | either; zero does **not** cause NULL |
| A6 | `[PoolMgr + 0x38]` TMap element count | `0` |

★ **A2 == 1 falsifies §1–§2 outright** (the FALSE would then come from a null / `IsA` leg, and the
Blueprint-override story is wrong). ★ **A4 != 0 falsifies §5's whole premise** and redirects the
repair to a CDO byte with nothing to do with pooling. **In either case, do not fly Phase B.**

**Phase B — the flight. Single variable: one byte. Arms A → B → A (temporal reversal).**
* **Arm A (control):** direct call `PrimePools` at `0x3356000`, `rcx = *(GS+0x428)`, `rdx` = a valid
  zeroed buffer of ≥0xA8 bytes. Nothing else.
* **Arm B (treatment):** write `byte [GS+0x898] = 1`, **readback-verify it reads 1**, then the
  *identical* call. Same process, same pointers, same arming mechanism.

**Arming class:** heap `UFunction.Func` swap (`RM_PHASELADDER` pattern). **Never `RM_GOTOPHASE` /
`InstallHook()`** — that is the standing `ProcessInternal` `.text` patch measured 10/10 vs 3/36.

**Positive control — free and built in.** `PrimePools` logs before it decides, so a reachable call
**cannot** be silent. ⚠⚠ **Baseline-count first: the string is already in the log from `BeginPlay`,
so PRESENCE does not discriminate — only the COUNT does.** A silent Arm A ⇒ the call never landed ⇒
**the sitting is VOID and nothing else may be interpreted.**

**PASS (Arm B):** the skip-line count does **not** increase; instead `%d actor classes found for
priming.` and/or `%d actor classes passed filtering for this match and will be loaded.` appear with
`%d > 0`; and after ≥5 s (**priming is ASYNC** — the string says *will be loaded*) `[PoolMgr+0x38]`
element count is **> 0**.
**FAIL (Arm B):** the skip line increments **with `[GS+0x898]` reading 1 on readback** ⇒ `+0x258` is
not the object slot 90 reads, or the `IsA` fails, or `+0x898` is not the field. All three are
checkable in the same RPM pass.

**Phase C — the question that actually matters for FK-22.** With the pool primed, call
`SpawnPoolableActorFromClass(BP_DropPod_Tutorial_C)`. **§3 predicts it makes NO difference**, because
an empty pool already falls back to a normal spawn. If it *does* now return an actor, §3 is wrong and
the fallback has a precondition not yet read. Either way the NULL's true cause is C7 / C8 / C9, and
**Phase A settles C7 before a single launch is spent.**

---

## 9. INSTRUMENT ARTIFACTS CAUGHT THIS SESSION

1. ★★ **`fkdis.py findptr` caps its output at 200 rows.** A row count from it is a **floor, never a
   count**. It first produced "`0x0B9E1F0` is a 200-way fold"; uncapped it is **26,444**.
   Uncapped multiplicities measured this session: `0x0F7EC20` **165,789**, `0x0F7EB50` **27,217**,
   `0x12C7260` **2,823**.
2. **`fkdis.py d <rva>` returns a BLANK result when `<rva>` is not an instruction boundary**
   (`0x56481D0` → one empty line; `0x56481D7` → 109 instructions). **A blank disassembly reads
   exactly like "page not decrypted" and is not.**
3. ⚠⚠ **`strxref.py func` extents are per-`.pdata` ROW, not per function.**
   `SpawnPoolableActorFromClass` reports "59 bytes"; the acquire reports "1,086 B" and is **3,702 B**.
   The chaining S124 hit on `GoToPhase` is **systemic**. **Never take a function size from that line.**
4. **The tool told an agent its own entry was wrong and it nearly ignored it** —
   `func 0x5676F10` prints `entry 0x5676AC3 [.pdata EXACT] (heuristic said 0x5676AA0 -- missed the
   entry)`, and the **heuristic** value was the correct one; sweeping from the "EXACT" value desynced
   the whole constructor. **Read the caveat line, not just the number.**
5. **Naming a folded stub after one caller.** "The base returns true" is a statement about **engine
   vtable slot 90 of `0x07DE3618`**, never about the address `0x0B9E1F0`.
6. **An offset identifies nothing on its own.** Six `mov byte [reg+0x898], 1` sites exist image-wide;
   four belong to unrelated classes. The link to `bSupportsActorPoolPriming` is the UHT
   **`SetBitFunc` pointer**, and only that.
7. **An off-by-one-RECORD read.** `bEnablePooling`'s `SetBitFunc` is `0x03368BF0`
   (`mov byte [rcx+0x2d3],1`), not the neighbouring record's `0x03368BE0` / `[rcx+0x2d2]`.
   **This is exactly S115-d — a byte string printed next to an address it did not come from.**
8. **Subtracting `ImageBase` from a value that is already an RVA** (these dumps are flat:
   file offset == RVA) produced negative RVAs — caught only because the sign was absurd.
9. **A missing key in a `bpdump …_PROPS.txt` is only interpretable after checking the dump is
   populated.** 69–193 lines each here, so the three absences are real inherits.
10. **A hand-computed rip-relative `lea` target fed to `strxref near` returned neighbours and read
    like "the string is absent"** — the decisive fallback string only appeared on a direct hexdump.
    *Recompute with a machine; suspect the query before the coverage.*
11. **Code-band adjacency is not identity.** `0x3355FC0` / `0x334E7A0` sit beside `PrimePools` and
    are an atomic flag op and a generic `TSet` find. (`0x3355FC0` is also only a MED-tier heuristic
    entry with **no `.pdata` row** — even its start is unproven.)
12. ⚠⚠ **THE ORCHESTRATION ITSELF WAS THE INSTRUMENT: the synthesis prompt never interpolated the
    lane packet**, so the synthesiser silently re-derived everything solo and opened its report with
    *"the six lane reports were not present in my input."* It was honest and it was right to say so —
    but a less careful agent would have written a confident synthesis of nothing, and the six lanes'
    results (3.2 M tokens of work) would have been lost in `journal.jsonl` unread.
    **An orchestration bug is an instrument artifact. Read the agent's provenance note, and read the
    journal before trusting a workflow's final answer.**

---

## 10. OPEN

1. ✅ **C7 is settled offline (§11).** ⚠ C8 and C9 are now **untested rather than excluded** — C7
   returns first, so nothing downstream of it has ever been reached.
   ★ **The one remaining read: `byte[CDO(BP_GemV2_C)+0x6C]` on any live client** — it discriminates
   "the cooked value IS the runtime value" from "something clears it at class load" (§11.5).
2. ✅ **ANSWERED — `AActor` CDO `+0x6C` is `bCanEverReplicate`, and C7 fires. See §11.**
   (Item 9 below records the abandoned FIRST attempt; §11 is the one that worked, by walking
   `AActor`'s own `PropPointers` array with per-type decoding instead of scanning globally.)
3. **Is `this` in `0x5648050` really a `ULokiActorPoolManager`?** Strong circumstantial evidence
   (a `TMap` at `this+0x38`, slot-49 `GetWorld`, the same TU as the ActorPool strings) — **[I]; its
   class was never read.** One RPM read.
4. **`this->byte@0xE9`** (`0x5648353 jne` → skip the miss counter, straight to fresh spawn) — looks
   like a runtime "pooling suspended" flag; changes nothing about NULL.
5. **Three sibling pooled-spawn helpers** (`0x55EE1BE`, `0x5618E5E`, `0x56D4F4E`, each ~497 B, each
   referencing the same fallback string at `+0x6C`). If `SpawnDropPodForTeam` inlines one, it
   inherits the identical fallback-not-null behaviour — **confirm this before assuming FK-22's
   blocker is anywhere near pooling.**
6. **Why do exactly `_Tutorial`, `_PvE_Holdout` and `_FFA` disable priming?** A design question whose
   answer may say what the pool is *for*.
7. **`DeferActorPoolClassLoading`** (bool UPROPERTY, record `0x0887A9A0`, pflags
   `0x0010000000000000` = NativeAccessSpecifierPublic only ⇒ no Edit, no Config, C++-set) —
   unexplored.
8. **Re-run the `.data` record instrument over all 100 keys of FK-22 §2.5** — free, offline, and it
   should collapse the COVERAGE-BLOCKED bucket to near zero.

9. ⚠ **ATTEMPTED AND ABANDONED THIS SESSION — naming `AActor+0x6C` offline.** The technique that
   named the gate (UHT record → `SetBitFunc` → offset) **does not transfer**, and the reason is worth
   knowing: `boolscan.py --off 0x6c` returns **11** bool records, but a bool record's `SetBitFunc`
   displacement is an offset **within its own outer struct**, not within `AActor` — so none of them is
   evidence about `AActor+0x6C`. Falling back to the generic decoder is worse: `propscan.py --off 0x6c`
   returns **69** hits and is **demonstrably misaligned** (it prints `MaxDepenetrationVelocity` as
   `gen=Bool` and `AutoCompleteCVarColor` as `InlineMulticastDelegate`), because `FPropertyParams` has
   **variant per-type layouts** and the generic reader takes `Offset` from a field that a bool record
   uses for `SetBitFunc`. ⇒ **doing this properly needs a per-class walk of `AActor`'s `PropPointers`
   array with correct per-type record decoding**, which is real work and exactly the shape that
   produces a confident wrong answer if rushed. **One read-only RPM read of the live CDO settles it
   instead.** ✅ **AND THEN THE OFFLINE ROUTE WAS RE-ATTEMPTED AND IT WORKED — see §11.**
   The guidance in this item was right and was followed to the letter: the per-type decode was
   fixed (pick the class first, walk ITS `PropPointers` array) and validated on three gold values
   (`bAlwaysRelevant`/`bHidden` `0x68`, `bEnablePooling` `0x2D3`) before the answer was read off.
   ★ **The lesson is not “the offline route is dead” but “a global scan cannot answer a
   class-scoped question”** — tool: `scratchpad/s130/tools/classprops_uht.py`.

---

## 11. C7 IS SETTLED — OFFLINE, WITH NO LAUNCH. THE NULL IS `bCanEverReplicate`.

**Date:** 2026-08-20, same session. §8 pre-registered C7 as a live RPM read (Phase A4); it turned out
to be answerable entirely offline. **Zero launches, zero injections, zero `.text` writes.**

### 11.1 The answer

```
C7  @ .text 0x0564820C   44 38 70 6c        cmp byte ptr [rax + 0x6c], r14b   (r14b = 0)
    @ .text 0x05648210   0f 85 8b 0c 00 00  jne 0x5648EA1                     (the NULL epilogue)
                                            0x5648210 + 6 + 0xC8B = 0x5648EA1  [M, arithmetic]

    rax   = UClass[0x178]                = ClassDefaultObject
    +0x6C = AActor::bCanEverReplicate
```

⇒ **`SpawnPoolableActorFromClass{,Deferred}` refuses any class whose CDO can ever replicate.**
⇒ **`BP_DropPod_Tutorial_C` has `bCanEverReplicate = 1`, so the call returns NULL deterministically —
on any machine, in any world, primed or unprimed.** That is the whole of FK-22's bail 2.

### 11.2 Every link, and how it was measured

| link | evidence | grade |
|---|---|---|
| `UClass + 0x178` = `ClassDefaultObject` | `UGameplayStatics::GetClassDefaultObject` impl `0x589BB40`: `mov rbx,[rcx]` → `cmp qword [rbx+0x178],0` → `jne` return it, else create then `mov rax,[rbx+0x178]; ret`. **An entirely independent function from the acquire.** | **[M]** |
| `AActor + 0x6C` = `bCanEverReplicate` | walked **`AActor`'s own 114-entry `PropPointers` array** (`FClassParams 0x07F227E0`, array `0x07F21540`), decoding each record by its **variant** layout — 114/114 decoded. Owner pinned: the array's `ClassNoRegisterFunc` is `0x2BE1050` = `jmp 0x338BD10`, and `0x338BD10`'s own literals are `'AActor'` / `'/Script/Engine'` / `'Engine'` | **[M]** |
| …with three positive controls | `bAlwaysRelevant`→`0x68` PASS · `bHidden`→`0x68` PASS · `bEnablePooling`→`0x2D3` PASS | **[M]** |
| …and an independent second instrument | `tools/asdump/out/binds_members.csv:21044` — `class,288,AActor,/Script/Engine.Actor,property,20,bool bCanEverReplicate` | **[M]** |
| the C++ default is **TRUE** | `AActor::AActor` = **`0x3371800`** (723 B), reached as `InClassConstructor` = `0x33703A0` (stack arg `[rsp+0x48]` of `GetPrivateStaticClassBody`) → tail-jmp. At **`0x03371841`: `mov byte ptr [rdi + 0x6c], 1`** — the only store to `+0x6C` in the whole ctor | **[M]** |
| neither Blueprint overrides it | `bpdump BP_DropPod_Tutorial @props` (83 lines, 23 exports — a **populated** dump, so the absence is a real inherit) and `bpdump DropPod/BP_DropPod.uasset @props`: the CDO overrides only `MaxSteerDistance` / `MaxNonLeaderSteerDistance` | **[M]** |
| the cooked **effective** value is `true` | AssetRegistry tag on `BP_DropPod_Tutorial`: `bCanEverReplicate = true`, `bEnablePooling = True` | **[M]** |
| the chain | `BP_DropPod_Tutorial_C` → `BP_DropPod_C` → `/Script/Angelscript.LokiDropPod`; `NativeParentClass = /Script/AngelscriptCode.ASClass'/Script/Angelscript.LokiDropPod'` | **[M]** |
| `bCanEverReplicate` is never assigned in Angelscript | a full sweep of `tools/asdump/out` finds it **only** as a `binds_members.csv` declaration; the only pooling-flag assignment anywhere in script is `LokiGem.as:1129 this.bEnablePooling = true` | **[M]** |

### 11.3 ★★ THE CONTROL THAT BROKE THE FIRST READING — and then confirmed it

The moment `bCanEverReplicate = true` came back for the drop pod, the obvious move was to publish
"C7 fires, done." **A control killed it:** `BP_GemV2` — a class the log shows being registered as
poolable, and the one class Angelscript explicitly opts into pooling — **also has
`bCanEverReplicate = true`.** If C7 were as read, gems could not be pooled either, which would make
the whole pooling subsystem inert. That is a far stronger claim than the evidence supported.

The joint distribution over the cooked registry settled it (unit: Blueprint assets, 36,625 scanned):

| `bEnablePooling` | `bCanEverReplicate` | count |
|---|---|---|
| false | *absent* | 5,362 |
| **true** | **true** | **96** |
| **true** | **false** | **80** |
| false | true | 23 |

⇒ **80 classes carry exactly the combination C7 requires**, so the gate is real and *satisfiable*,
not a universal killer. And the 80 are semantically coherent: **every one sampled is a cosmetic
projectile visual** — `BP_Assault_AssaultRifle_ProjectileCosmetics`,
`BP_Freeze_IceDart_ProjectileCosmetics_*`, `BP_Flex_Blaster_ProjectileCosmetics_*`, … — i.e. exactly
the client-side, non-replicated actors a pool is for. `ALokiHeroHeightIndicator`'s C++ ctor
independently shows the same pattern: `mov byte [rbx+0x6c], dl` (dl = 0) **and**
`mov byte [rbx+0x2d3], 1` — *clear replicate, set pooling*, in one constructor.

⇒ **the pooled-spawn API is for non-replicated cosmetics, and a drop pod is not a legal argument to it.**

### 11.4 And the caller bails on the null with no fallback — bail 2, fully explained

`tools/asdump/out/a/GameMode.DropPhase.LokiDropShip.as.txt:153`, inside `SpawnDropPodForTeam`:

```
v6 = LokiGameplay::SpawnPoolableActorFromClassDeferred(__WorldContext, this.TeamDropPodClass, v32, null, null, false, true);
if (v6 != null) {
    ... GetTeamDropLeader / InitializeDropPod / FinishSpawningActor / AddPlayerToPlane ...
}
```

Everything the drop depends on is inside `if (v6 != null)`. There is **no else**. `TeamDropPodClass`
is `BP_DropPod_C` (`Default__BP_DropPlane_Base_C`, [M] prior), which is replicated.
⇒ **C7 → NULL → the whole body is skipped → `SpawnDropPodForTeam` returns false.** That is precisely
S127's measured bail 2, and it is now explained end to end without any reference to the actor pool.

⚠ **`LokiGem.as:181` has the identical shape** (`if (v30 != null) {...} else {}` — an *empty* else),
so this is **not drop-pod-specific**. Which raises a real question, stated rather than resolved:
**§11.5.**

### 11.5 ⚠ WHAT THIS DOES *NOT* ESTABLISH — the open question it creates

If the cooked value equals the runtime CDO byte, then **gems fail this gate too**, and the pooled
spawn path is inert for every replicated class in this build. The game shipped and presumably
worked, so one of these is true and **none of them is measured**:

1. the runtime CDO byte differs from the cooked class default (something clears it during class
   loading / `PostInitProperties`) — plausible and **completely untested**;
2. gems and pods genuinely never spawn through this path in real matches, and some other route does
   the work;
3. the path really is broken for replicated actors in this build.

★ **One read settles it, and it is the cheapest thing on the board:** on any live client with a
world, read `byte[CDO(BP_GemV2_C) + 0x6C]`. If it reads **1**, the cooked value is the runtime value
and (2)/(3) are the live options. If it reads **0**, hypothesis (1) is right and the *cooked* value
is not what C7 sees — in which case the drop pod's runtime byte must be read too, and C7 may not
fire after all.
✅ **THE READ WAS FLOWN — SEE §12.** `Default__BP_GemV2_C + 0x6C` reads **1** live, so hypothesis (1)
is **REFUTED**; the runtime byte IS the cooked default, and C7 fires. ⚠ The remaining question is now
(2) vs (3), and §12.5 narrows it: the gem call site is `SpawnExtraGemWithTeam`, an *extra*-gem
spawner — **but whether the game's primary gem path uses it is UNESTABLISHED.**

### 11.6 The repair this implies — and it is one byte, on the safest write class

If the runtime read confirms `1`, the lever is **`CDO(BP_DropPod_Tutorial_C) + 0x6C = 0`**: a single
aligned byte on a **class default object**, this project's safest measured write class (nothing 0/22
· bytecode 0/9 vs transient `.text` 4/12 · standing `.text` 7/8), with a free readback. Then dispatch
`SpawnDropPodForTeam` by the existing Route E (ProcessEvent slot 78).
⚠ It changes a **class default**, so it affects every drop pod for the process lifetime and may
break the pod's replication — which is exactly why it belongs in an A→B→A arm with the census as the
readout, not in the default shim set.
⚠ And it is **upstream of nothing else that was blocking**: C8/C9 have never been reached, so they
remain untested rather than excluded.

### 11.7 An instrument defect found and fixed in the shared toolchain

`extractor bpdump <asset> @props` was **gated behind the asset having UFunction exports**
(`Program.cs:1137`, `if (ufuncs.Count == 0 && !wantImports) continue;`). A **data-only Blueprint** —
which is exactly what `BP_DropPod_Tutorial` is (0 UFunction exports) — fell through that `continue`,
and the command printed **`No matching UFunction '@props' found`**, which reads exactly like *"the
asset has no such property"* and is not. `@props` wants a UObject export, not a UFunction, precisely
like `@imports` next to it. **Fixed**; validated by re-dumping `BP_LokiGameState_Tutorial` first and
reproducing its known `bSupportsActorPoolPriming = False` before trusting the new dumps.

---

## 12. FLOWN — THE RUNTIME CDO **EQUALS** THE COOKED DEFAULT. C7 FIRES. [I, strong] → [M]

**Date:** 2026-08-20. **One clean `-NoHook` MENU launch, read-only RPM, zero injection, zero writes,
zero `.text` touched, no tutorial staging.** PID 17736, base `0x7FF7C4050000`, 190,085 UObjects,
**10,371 CDOs** live. Probe: `tools/re/cdo_flag_readout.py` (predictions written into the file
*before* the first run). Raw output: `scratchpad/s130/evidence/cdo_flag_readout-s130-live.txt`.

### 12.1 The result — 8/8 pre-registered predictions passed, 0 failures

| object | `+0x6C` `bCanEverReplicate` | predicted | `+0x2D3` `bEnablePooling` |
|---|---|---|---|
| `Default__Actor` | **1** | 1 ✅ | **0** |
| `Default__LokiDropPodBase` | **1** | 1 ✅ | 1 |
| `Default__LokiDropPod` | **1** | 1 ✅ | 1 |
| `Default__BP_DropPod_C` | **1** | 1 ✅ | 1 ✅ |
| `Default__LokiGem` | **1** | 1 ✅ | 1 ✅ |
| `Default__BP_GemV2_C` | **1** | 1 ✅ | 1 ✅ |
| `Default__LokiHeroHeightIndicator` | **0** | 0 ✅ | 1 ✅ |
| `Default__BP_HeroHeightIndicator_C` | **0** | 0 ✅ | 1 ✅ |
| `Default__BP_DropPod_Tutorial_C` | *not loaded* | — | — |

⇒ **THE RUNTIME CDO BYTE IS THE COOKED CLASS DEFAULT.** §11.5's hypothesis (1) — *"something clears
the byte at class load / `PostInitProperties`"* — is **REFUTED**.
⇒ **C7 fires on the drop pod. The pooled spawn's NULL is fully explained, and every link is now [M].**

### 12.2 The controls, and why they carry the result

* ★★ **Two-sided on `+0x6C`.** Six objects read **1**, two read **0**, split **exactly** along the
  cooked value. The probe's own instrument check prints *"targets differ ([0, 1]) — the probe
  discriminates"*; had everything read the same it would have declared the run **VOID**.
* ★★ **`Default__Actor + 0x6C = 1` is the disassembly and the live process meeting on one byte** —
  `AActor::AActor` `0x03371841 mov byte ptr [rdi+0x6c], 1` predicted it, and the running game confirms it.
* ★★ **A SECOND two-sided control appeared that was NOT predicted:** `Default__Actor + 0x2D3 = **0**`
  while every poolable class reads **1**. That independently confirms `+0x2D3` is `bEnablePooling`
  (off on the root, opted into per class) — a control on the *other* offset, from the same read.
* ★ **The cooked↔runtime mapping is validated 3/3 on loadable classes, in BOTH polarities**
  (`BP_GemV2_C` true→1, `BP_DropPod_C` true→1, `BP_HeroHeightIndicator_C` false→0).

### 12.3 ⚠ The leaf class was NOT read directly, and here is exactly how strong the claim is

`Default__BP_DropPod_Tutorial_C` **is not loaded at the menu**, so its byte was not read.
The claim that it is `1` rests on:
(a) **all three of its ancestors read 1 live** — `LokiDropPodBase`, `LokiDropPod`, `BP_DropPod_C`
    (its direct parent, [M] `SuperStruct -> BP_DropPod_C`);
(b) **[M] it overrides neither flag** (`bpdump @props`, a populated 83-line / 23-export dump);
(c) ★★ **[M] the cooked→runtime mapping is validated 30/30 — 16 cooked-true and 14 cooked-false,
    both polarities, ZERO disagreements**, over every live CDO joinable against a cooked tag
    (, one GUObjectArray walk, 10,025 CDOs scanned;
    evidence ). Its cooked value is `true`.
    ⚠ The tool refuses to call a one-sided sample discriminating — it prints an explicit
    *ONE-SIDED SAMPLE … treat as inconclusive* guard, which did not fire here.
⇒ **[M] for the ancestors and the mapping; the leaf itself is one inheritance hop of inference.**
Staging a tutorial world would close it outright and is the only thing that would.

### 12.4 ★ A finding that fell out of the failed first attempt

The first probe run found **none** of the four Blueprint CDOs, while 10,371 CDOs were live.
⇒ **`LogActorPooling: Adding <X> to list of poolable actors` does NOT load the class.** It is an
**AssetRegistry query** (`bEnablePooling` is `CPF_AssetRegistrySearchable`), so all 176 registrations
happen at the menu against *cooked tags*, with no CDO in memory.
⚠ **"Registered as poolable" is therefore NOT evidence that a class is loaded** — a distinction that
would silently corrupt any census keyed on those log lines. The probe reported `NOT LOADED (this is
NOT a zero)` rather than reading offset `0x6C` of a null, which is the only reason this surfaced as a
finding instead of as four confident zeros.
★ `BP_GemV2_C`, `BP_DropPod_C` and `BP_HeroHeightIndicator_C` **are** loaded at the menu — so the
registration and the load are independent, and which classes happen to be loaded is not predictable
from the pooling log.

### 12.5 ⚠ And the §11.5 puzzle is now sharper, not solved

`Default__BP_GemV2_C + 0x6C = 1` **at runtime**, so `SpawnPoolableActorFromClassDeferred` returns
NULL for gems too — hypothesis (1) is dead, leaving (2) *"gems/pods never use this path in real
matches"* and (3) *"the path is inert for replicated actors in this build"*.
★ **One fact narrows it:** the gem call site is `LokiGem.as:168 SpawnExtraGemWithTeam` — an
***extra***-gem spawner, not demonstrably the primary gem drop. ⚠ **Whether the game's main gem path
uses this function is UNESTABLISHED** — I did not survey the other gem spawn routes, and the name is
suggestive, not evidence. Do not upgrade that hunch without the survey.
⇒ For FK-22 it does not matter: the drop pod's only route **is** `SpawnDropPodForTeam`, which calls
the pooled deferred spawn and bails on the null with no else. That is settled either way.

### 12.6 What this changes for the repair

The one-byte lever from §11.6 is now backed by a measurement rather than an inference:
**poke `CDO(BP_DropPod_Tutorial_C) + 0x6C = 0`** (or, since the leaf may not be loaded when the shim
runs, **`CDO(BP_DropPod_C) + 0x6C = 0`** — measured live at `0x241BA0290E0` this run, ASLR-dependent,
re-derive per launch), then dispatch `SpawnDropPodForTeam` via Route E.
⚠ Unchanged: it mutates a **class default**, and **C8/C9 have still never been reached.**

---

## 13. FLOWN — THE POKE WORKS, AND THE DROP POD SPAWNS. FK-22's BAIL 2 IS FIXED.

**Date:** 2026-08-20. One staged tutorial world, PID 20024, base `0x7FF7C4050000`.
**Zero `.text` writes. The only write in the entire experiment is ONE BYTE per CDO on the heap.**
Pre-registered in `scratchpad/s130/evidence/PREREG-cdopoke-flight.md` (with two amendments, all
written **before** the flights they describe). Raw markers:
`RESULT-poolspawn-cdopoke-s130.txt`, `RESULT-routeE-after-poke-s130.txt`.

### 13.1 The headline

| | S128 / S127 (byte = 1) | S130 after the poke (byte = 0) |
|---|---|---|
| `SpawnPoolableActorFromClassDeferred` | **NULL**, `dP1 = +0` | **live `BP_DropPod_Tutorial_C`** `0x1D1FFDDE830`, **`dP1 = +1`** |
| `SpawnPoolableActorFromClass` | **NULL**, `dP2 = +0` | **live `BP_DropPod_Tutorial_C`** `0x1D1A5DA7910`, **`dP2 = +2`** |
| `SpawnDropPodForTeam` (Route E) | returned **`false`**, DropPod **`+0`** (S127) | returned **`true`**, DropPod **`+2`** |

```
poolspawn:  bucket    BEFORE afterP1 afterP2 afterP3   AFTER     dP1     dP2     dP3
            DropPod        2       3       5       7       7      +1      +2      +2

route E:    bucket      BEFORE   afterC1    AFTER   delta
            DropPod          7         0        9      +2
```

⇒ **C7 was the whole of FK-22's bail 2, and clearing `AActor::bCanEverReplicate` on the drop-pod CDOs
fixes it.** The pooled spawn produces real actors and `SpawnDropPodForTeam` now succeeds.

### 13.2 The poke itself [M]

Baseline read, in a staged world, from the same probe run:
```
Default__BP_DropPod_Tutorial_C  @0x1D1957E90E0  bCanEverReplicate=1  bEnablePooling=1
Default__BP_DropPod_C           @0x1D1FF33F020  bCanEverReplicate=1  bEnablePooling=1
Default__LokiDropPod            @0x1D04B1BB4F0  bCanEverReplicate=1  bEnablePooling=1
Default__Actor                  @0x1D04AE8E4F0  bCanEverReplicate=1  bEnablePooling=0
```
★★ **THIS CLOSES §12.3's LAST INFERENCE.** `Default__BP_DropPod_Tutorial_C` — the leaf, which is **not
loaded at the menu** and could previously only be inferred from its ancestors — **reads 1, measured
directly.** Exactly as predicted. Every link in FK-22's chain is now [M] with nothing inferred.
★ And `Default__Actor + 0x2D3 = 0` while all three pod CDOs read 1 reproduces the unpredicted
two-sided control from the menu run, in a different process.

Then: `poke summary: 3 written, 3 readback-verified`, `1 -> 0` on all three pod CDOs,
`Default__Actor` **untouched at 1** (the root control held).
★★ **The poke persisted across TWO further DLL injections** — the Route E arm, injected later and
built with `KPDCDOPOKE=0`, read all three pods back as **0** and `Default__Actor` as **1**. A class
default really does stay poked for the process lifetime, and the root control was never collaterally
written.

### 13.3 ⚠ What is attributable, and what the probe refuses to grade

The probe emits **two** verdicts and they are about different things. Quote both:

* `VERDICT: control AGREED, so C1 (status -1, DropPod delta +2) is attributable to
  SpawnDropPodForTeam.`
* `*** E-VERDICT: E1 RAN BUT IS NOT ATTRIBUTABLE. E0/E0b passed on the SAFE-INVOKE exit, but E0c --
  the only control for the [UFunctionVtable+0x378] marshaller, which is the branch E1 takes -- is
  INCONCLUSIVE (no candidate) … Record E1 (fault=0, return-slot written=1, DropPod delta +2) as
  UNATTRIBUTABLE, not as a game statement. ***`

⚠ **The E-VERDICT is about the DISPATCH MECHANISM, not about whether pods appeared.** E0c is
*unsatisfiable* on this class chain (S127 measured: of 206 UFunctions, exactly 1 takes the
alt-dispatch exit and it is not blind-callable), so "wait for E0c" waits for something that cannot
happen. **Respect it: do not write "Route E is proven to marshal correctly."**

★★ **But the claim that matters survives it, because it is a DIFFERENCE, not an absolute.** S127 ran
**the same E1 dispatch, on the same function, with the same unsatisfiable E0c caveat**, and measured
`false` / `+0`. This run measured `true` / `+2`. **The mechanism-grading limitation is identical in
both arms, so it cancels in the differential.** What changed between them is one byte.
⇒ **[M] the CHANGE is attributable to `bCanEverReplicate`**, even though the absolute grade of the
ProcessEvent marshaller path remains ungraded — and that was already true before this session.

★ The `poolspawn` arm carries no such caveat at all: it is a **native static** called through the S55
direct-`Func` thunk, its `P0c` control was a **STRONG PASS** (0.00 uu on a non-zero reference,
|ref|=8377), and its `0xA5` sentinel confirmed `RESULT_DECL OVERWRITTEN` — so a real return was
written and it decoded as a live `BP_DropPod_Tutorial_C`. **That arm alone settles C7.**

### 13.4 ★★ The pool is STILL DISABLED — which re-confirms §25 from the other direction

Nothing in this experiment touched `bSupportsActorPoolPriming`; `PrimePools` was never called and the
actor pool remained off for the whole run. **The pooled spawn produced actors anyway.** The probe's
own verdict line, written back in S128 before C7 was known, says it plainly:

> *"SpawnPoolableActorFromClassDeferred RETURNED A LIVE ACTOR … with the pool feature disabled.
> ⇒ THE FIRST LINK OF THE [I] CHAIN IS REFUTED: the helper does NOT require the pool, 'PrimePools is
> not enabled' does NOT explain S127's bail 2, and the disabled pool is a RED HERRING."*

⇒ §25's offline refutation of the pool hypothesis is now **independently confirmed live**.
⚠ Note the probe's wording predates C7 and therefore does not name the real cause; it is right about
what it denies and silent about what replaces it.

### 13.5 ⚠ What this does NOT establish

1. **That the spawned pods are functional.** The census counts objects. Nothing here shows a pod
   flies, carries a player, or lands. **C8/C9 were never reached before and are still unexercised as
   failure paths** — they simply did not fire.
2. **That this is the right FIX rather than the right DIAGNOSIS.** Clearing `bCanEverReplicate` on a
   class default is a *probe*, not a shipping change: it mutates a class default for the process
   lifetime and may well break the pod's replication, which is the thing the flag exists to declare.
   ⇒ **Do not add this to the default shim set.**
3. **That the shipped game works this way.** The 96 cooked-`true` poolable classes include gems; on
   the shipped values their pooled spawns would return NULL too. §12.5's question — whether the
   primary gem path uses `SpawnExtraGemWithTeam` — is still unanswered and still needs an offline
   survey, not a client.
4. **A within-session A→B→A.** The control is **cross-session** (S128/S127 on different clients).
   The arms are the same probe modulo one byte and the differential is clean, but a same-process
   reversal was not run: once the CDOs are poked the process is committed, so the control needs its
   own launch. `poolspawn-cdoctrl` (`.text 4e9c12ae866f5359`) exists and is byte-for-byte the S128
   experiment plus a read-only print — **fly it to convert the cross-session control into a
   within-session one.**

### 13.6 Cost, honestly

Four launches for one armed result. Attempt 1 died 9 s after `fo` (FK-31). Attempts 2 and 3 staged,
armed, and died **silently at the same ladder position** before the CDO arm — the artifact-less class,
no dump, no handoff. Attempt 4 succeeded and ran to completion, then absorbed **two further manual-map
injections** (`dropplane_b1only` to create the `LokiDropShip` precondition, then the Route E arm)
without dying.
★ **The S127 cross-check is what turned attempt 3's failure into progress:** its successful Route E
flight reads `DropShip=1` because it injected `dropplane_b1only` first. Mine read `DropShip=0`. **I
had omitted a precondition, and re-reading the prior flight's own census is what surfaced it** — not
more launches.
⚠ **And the better response was to stop needing the precondition:** `RM_POOLSPAWN` tests C7 with no
ship, no plane and no ProcessEvent. The cheapest experiment was available the whole time.
⚠ `PdCdoFlags`' single GUObjectArray pass still costs **~2,000–2,300 ms on the game thread** (measured
and printed). That is a real hitch; it ran twice per arm. Budget for it, or move the read off-thread.

### 13.7 ⚠⚠ ADDENDUM — the armed-window death rate this session was 3 of 3, not 3 of 36

Attempt 4 **also died artifact-less** — no crashpad report, no handoff — but only **after running every
arm to completion and writing the full result to disk**. Nothing was lost; the pods it created were
gone before they could be inspected, which is the one thing that was.

Session tally, by **armed window** (the unit that matters, not launches):

| attempt | staged? | armed? | outcome |
|---|---|---|---|
| 1 | ❌ died 9 s after `fo` | — | FK-31 staging hazard |
| 2 | ✅ | ✅ | died **silently mid-ladder**, before the CDO arm — no dump |
| 3 | ✅ | ✅ | died **silently mid-ladder**, same position — no dump |
| 4 | ✅ | ✅ | **completed every arm**, absorbed 2 further manual-maps, then died silently — no dump |

**3 of 3 armed windows ended in artifact-less deaths.** `CLAUDE.md` records that class at **3/36
(≈8 %)** of armed windows. Three for three against an 8 % base rate is p ≈ 0.0005 if the recorded rate
still applies.

⚠⚠ **n = 3. This is SUGGESTIVE, NOT ESTABLISHED**, and I am deliberately not naming a mechanism:
* the three are **not homogeneous** — 2 and 3 died before their arms ran, 4 died after everything;
* attempt 4 had absorbed **two extra manual-maps** (`dropplane_b1only`, then the Route E arm) that
  2 and 3 did not, so it is not the same exposure;
* the ~2,000–2,300 ms game-thread stall the CDO walk introduces **cannot** explain 2 or 3, because
  the arm never ran in either.
* and the recorded 3/36 comes from a different shim family (`play`), so the base rate may simply not
  transfer to the `droppod`/`poolspawn` family at all.

⇒ **What to do with this: budget the drop-pod route at roughly ONE armed window per result and expect
the client not to survive it.** Write results to disk as they are produced — attempt 4 is the case
that proves the point: it delivered everything and then died, and only the fact that the marker is
flushed continuously made that a full success rather than a total loss.
⇒ **And take any read you want off the live process IMMEDIATELY.** The pods existed for minutes and
the chance to inspect them is gone. `docs/next-session-prompt-s131.md` §1 asks exactly the questions
that window could have answered for free.
