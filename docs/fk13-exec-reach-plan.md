# FK-13 lane 4 — if the console STRING can't reach the cheats, what can?

**Session 114, 2026-08-12. Entirely offline: zero game launches, zero injections, zero writes.**
Every claim is **[M]** measured (bytes read / tool run and output quoted) or **[I]** inferred.
Read `memory/supervive-instrument-artifact-pattern` before adding to this file.

Prerequisite reading: `docs/fk13-console-exec-settled.md` (what the exec surface IS),
`docs/s112-fk7-ab-results.md` (why `.text` writes are forbidden),
`docs/session-55-native-call-primitive.txt` + s56/s57/s58 (how a thunk is called).

---

## 0. Verdict, up front

| Question | Answer |
|---|---|
| Can a console string reach `ALokiPlayerCheats`' 25 exec verbs? | Depends on lane 1; **irrelevant to Routes A/C** |
| Does an `ALokiPlayerCheats` instance exist? | **NO — and the game's own creation path is an empty stub** [M] |
| Is that a wall? | **No.** `ALokiPlayerCheats` is an **Actor**, and `tutorial_launch.cpp` **already contains a working spawner and a wired-up `CT_SPAWNACTOR` mode for exactly this** [M] |
| Is `UCheatManager`'s payload real? | **YES — 50/50 exec thunks are real dispatch; none folds to `ret`** [M] |
| Is `CheatsEnabled` flippable without touching `.text`? | **Yes — a heap `UFunction.Func` swap**, the shipped S112 technique [M for the target, [I] for the effect] |
| Which route is cheapest? | **Route A**, because the shim already implements ~90 % of it |

★★ **The headline finding is a new one, and it re-scopes FK-6:** the shipping client does not merely
*fail to enable* the cheat objects — **the constructor calls are compiled out**, in exactly the
`WITH_SERVER_CODE`-shaped way FK-1 found for `ALokiGameMode::SpawnPlayer`. See §1.

---

## 1. ★★★ NEW MEASUREMENT — the cheat-object creation path is an EMPTY STUB

`ALokiPlayerController::AddLokiPlayerCheats` and `::FinishAddLokiPlayerCheats` are the only two
functions in the image that would create the `ALokiPlayerCheats` actor. Both register the **same**
native thunk, `.text` RVA **`0x05254180`**, whose entire body is [M]:

```
+5254180  mov  rax, qword ptr [rdx + 0x20]      ; FFrame.Code
+5254184  xor  r8d, r8d
+5254187  test rax, rax
+525418A  setne r8b
+525418E  add  r8, rax                          ; P_FINISH: Code += !!Code
+5254191  mov  qword ptr [rdx + 0x20], r8
+5254195  jmp  0xf7ec20                         ; --> 0x00F7EC20 = `ret 0`
```

`0x00F7EC20` is this image's universal folded empty stub (`c2 00 00`, the same one FK-13 §2.1 used).
Both functions declare `NumProperties = 0`, so the thunk is a complete no-param `P_FINISH` +
tail-jump — there is no elided parameter step and no other body. **The C++ member is empty.** [M]

**ICF corroboration:** `0x05254180` is the registered native pointer for **92** distinct native
UFunctions in this image [M] — the "no-param, `void`, empty body" identical-COMDAT-folding class.
That is not one suspicious symbol; it is a population.

**Independent live corroboration, 20+ runs, a different instrument:** every force-open tutorial
marker in `docs/` records

```
[CHEAT] localCheatObj=0x0(-)
```

i.e. `ALokiPlayerCheats::GetLocalLokiPlayerCheatsBP(WorldContext=PC)` returned **NULL**
(`docs/fk24-stage-*-gft.txt`, `docs/fk24-run-*.txt`), and S76 recorded the same on a *different*
route: `[CS] GetLocal -> cheatObj=0x0 cls=-` (`docs/session-76-ds-cheat-lever.md:31-35`). [M]

★ **Cross-validation of the whole offline table against a live process.** S76 also logged the thunk
pointers it resolved live:

| S76 live value | minus base `0x7FF6B54F0000` | offline table (this session) |
|---|---|---|
| `getLocalThunk=0x7FF6BA914F70` | `0x05424F70` | `GetLocalLokiPlayerCheatsBP` **`0x05424F70`** ✅ |
| `cchThunk=0x7FF6BA83BE80` | `0x0534BE80` | `CheatChangeHero` **`0x0534BE80`** ✅ |
| `schThunk=0x7FF6BA916760` | `0x05426760` | `ServerCheatChangeHero` ✅ |

Three thunks, one consistent base, exact match. **The offline `FNameNativePtrPair` recovery is
therefore validated against ground truth** — and it also proves `CheatChangeHero` is
**COVERAGE-BLOCKED, not absent**: its page is all-zero in `dumps/tutorial-hero` because it was
never executed, yet the live game resolves it fine.

### 1.1 Positive control for the "empty" verdict

The identical instrument (`FNameNativePtrPair` → thunk RVA → capstone over the cross-dump `.text`
union) finds **real, non-folded** bodies in the same class and the same `.text` neighbourhood [M]:
`EnableHotkeyCheats 0x05424670` (128 B), `GetLocalLokiPlayerCheatsBP 0x05424F70` (133 B),
`CheatSetXP 0x052FD8F0` (131 B), `SetGamepadAimSettings 0x05428180` (437 B). An uncontrolled zero
would be void; this one is not.

### 1.2 The full exec-body grading (all 138 `FUNC_Exec` natives)

Thunk shapes are distinguished, because they are **not** interchangeable:
`jmp <imm>` to `0x00F7EC20` = provably empty; `jmp [rax+D]` = **virtual dispatch, body unknown from
the thunk alone** (I nearly recorded these as "real bodies" — they are only "not proven empty").

| Owner | n | DIRECT-CALL | VIRTUAL | **EMPTY (`ret 0`)** | coverage-blocked |
|---|---:|---:|---:|---:|---:|
| `UCheatManager` | 50 | 26 | 24 | **0** | 0 |
| `ALokiPlayerCheats` | 25 | 17 | 0 | **2** | 6 |
| `ULokiClientPlayerCheats` | 5 | 5 | 0 | **0** | 0 |
| `APlayerController` | 14 | 11 | 2 | **0** | 1 |
| `AHUD` | 6 | 3 | 2 | **0** | 1 |
| `UPlayerInput` | 5 | 4 | 0 | **0** | 1 |
| `ALokiPlayerController` | 8 | 4 | 0 | **3** | 1 |
| **`ALokiCharacter`** | **10** | **0** | **0** | **8** | **2** |
| `ULokiTimelineManager` | 5 | 0 | 0 | **3** | 2 |

⚠ **Ambiguity audit (run, not assumed).** The name→thunk lookup is by ASCII name, so a name declared
on several classes could be mis-attributed. Measured: `UCheatManager` **0** ambiguous rows,
`ALokiCharacter` **0**, `ALokiPlayerController` **0**, `ALokiPlayerCheats` **1**
(`TestErrorMessage`, a genuine two-owner ICF fold with `ULokiClientPlayerCheats`),
`APlayerController` **2** (`Pause` 6 candidate thunks, `SetName` 9 — generic names registered on
many classes). **None of the load-bearing claims sits on an ambiguous row**; the `APlayerController`
row above is the only one with a soft edge, and nothing here depends on it. [M]

★ **`ALokiCharacter` is the one cheat-bearing class already on the `UPlayer::Exec` chain** (as
`PCPawn`), and **8 of its 10 exec verbs are empty bodies**: `InfiniteHealth`, `InfiniteMana`,
`InfiniteStamina`, `ResetCooldowns`, `TeleportAlly`, `TeleportEnemy`, `TeleportNear`,
`CheatExperience` — all `NumProperties = 0`, all folded to `0x05254180`. [M]
⇒ **the "free" string route is largely a decoy.** `UCheatManager` 0/50 empty is the control that
makes that a finding rather than an instrument artifact.

Also newly measured: `ALokiPlayerCheats::AreHotkeyCheatsEnabled` (`0x052FD980`) is the **same
always-false fold** as `CheatsEnabled` — `call 0x00F7EB60` = `xor al,al; ret`. Only `CheatsEnabled`
was on record. [M]

---

## 2. Decision tree from lane 1's outcome

```
lane 1: does ALokiPlayerController override ProcessConsoleExec?
│
├─ YES, forwards to LokiPlayerCheats
│     └─ still needs an INSTANCE (§1: none exists) -> you must SPAWN one anyway
│        => go to ROUTE A. The string route only saves you param marshalling.
│
└─ NO  (assume this)
      │
      ├─ Do you want ALokiPlayerCheats' 25 verbs?      -> ROUTE A  (spawn + direct Func call)
      ├─ Do you want UCheatManager's 48 verbs?         -> ROUTE B  (SpawnObject + one data write)
      └─ Do you want the BLUEPRINT cheat gates open?   -> ROUTE C  (one heap Func swap)
```

★ **Routes A and B converge.** Once an instance of either class exists, the S55 primitive calls its
UFunctions directly and **the router is irrelevant**. The string route is a convenience, not a
dependency. Route C is orthogonal and can run alongside either.

---

## 3. ROUTE A — direct `UFunction.Func` call (RECOMMENDED)

### 3.1 Does it need an instance? YES — and that is the whole cost

`UFunction::Invoke` is `Func(Context, FFrame&, Result)`. `Context` becomes `this` inside the native
body. Every `ALokiPlayerCheats` cheat dereferences `this` (e.g. `CheatAutoStrafe` writes
`AutoStrafePeriod`/`AutoStrafeSpeed`, which are UPROPERTYs at fixed offsets on the actor). **Calling
with `Context = nullptr` or with the CDO is not a shortcut — it is an access violation or a write
into the class defaults.** [I, from the S55 mechanism + the schema field list]

Exceptions, callable with **no instance** [M, `flags` column of `uht_funcflags_tuthero.csv`]:
`GetLocalLokiPlayerCheatsBP` (`Static`, call on the CDO — the shim already does exactly this) and
`UGameplayStatics`/`UKismetSystemLibrary` statics.

### 3.2 The shim already implements ~90 % of this

`tools/sigbypass-mod/tutorial_launch.cpp` contains, today [M]:

| Piece | Where |
|---|---|
| `SpawnActorCls(cls, tag)` — BeginDeferredActorSpawnFromClass + FinishSpawningActor | `:3139` |
| `g_cheatObjClass`, `g_pcCheatOff` (the PC's `LokiPlayerCheats` member offset) | `:251` |
| `CT_SPAWNACTOR` — *"spawn the LokiPlayerCheats obj ourselves, wire it to the PC, then `ServerCheatSpawnActor` on it"* | `:233,249`, implemented `:5883,5936` |
| `ResolveFuncNative(cls,"ServerCheatSpawnActor",…)` + `ParamOffset` + `DumpParams` | `:5211-5212` |
| `CallNativeGuarded` (SEH-wrapped `CallNative`) | `:881-912` |

⚠ **`CT_SPAWNACTOR` has never produced a recorded result.** Every marker in `docs/` shows the
*other* branch running (`KCHEATSPAWN` → `GetLocalLokiPlayerCheatsBP` → null → abort). So the spawner
is written but **unexercised for this class**; treat it as untested code, not as a known-good path.

### 3.3 Worked spec — `CheatTeleportLocation`

Signature [M, `tools/asdump/out/binds_members.csv`]:
`void CheatTeleportLocation(float64 X, float64 Y, float64 Z)` — `NumProperties=3`,
`StructureSize=24`, flags `Final|Exec|Native|Public|BlueprintCallable`, **no OUT params, no return**.
Registered thunk `0x05422360` (coverage-blocked in the dumps; §1 shows blocked ≠ absent).

```
1. Instance.
   a. cls = FindClassExact("LokiPlayerCheats")            // native UClass, always registered
      -- OR the class the game itself would use: ULokiGlobals.DebugGlobals(UClass) -> its CDO
         -> .LokiPlayerCheats (TSoftClassPtr<ALokiPlayerCheats>).  Prefer this: a BP subclass may
         carry defaults the native CDO lacks.  The probe (§6) reads it.
   b. obj = SpawnActorCls(cls, "LokiPlayerCheats")        // existing helper, GameplayStatics path
   c. write PC->LokiPlayerCheats = obj                    // HEAP data write, offset resolved BY NAME
                                                          // (schema: LokiPlayerController prop #2)
      and, if TryInitializeAfterController resolves, call it on obj so the actor learns its PC.

2. Resolve.
   ResolveFuncNative(ClassOf(obj), "CheatTeleportLocation", &fn,&thunk,&child);
   oX = ParamOffset(child,"X");  oY = ...;  oZ = ...;     // NEVER hardcode 0/8/16

3. Call (S55 recipe, unchanged).
   memset(pbuf,0,sizeof pbuf); memset(rbuf,0,sizeof rbuf);
   *(double*)(pbuf+oX)=x; *(double*)(pbuf+oY)=y; *(double*)(pbuf+oZ)=z;
   CallNativeGuarded(fn, thunk, child, (void*)obj, pbuf, rbuf);
   // CallNative builds the FFrame from the captured template with
   //   Node=UFunction  Object=obj  Code=NULL  Locals=pbuf   and calls thunk(obj,&frame,rbuf).

4. OUT params: NONE here, so FFrame.OutParms(+0x80) is untouched.
```

**`CheatChangeHero`** differs only in step 2-3: `NumProperties=1`, `StructureSize=16` ⇒ **one
`FString`** [M]. Build an `FString` (`TArray<TCHAR>`: `Data`, `Num`, `Max`, NUL included in `Num`)
in a buffer the shim owns and keep it alive across the call. The thunk is `0x0534BE80`, **live-
confirmed by S76** (§1). Prefer `ServerCheatChangeHero(TSubclassOf<ALokiHeroCharacter>)` —
a `UClass*` param is far cheaper to marshal than an `FString`.

### 3.4 OUT params, when you hit one

Two of the 25 carry `HasOutParms` (`AdminOnly`, `LogActorsInRadiusNear`). S58's fix is mandatory and
non-obvious: for each `CPF_OutParm` build an `FOutParmRec{Property, PropAddr=Locals+Offset(+0x44),
Next}` and set **`FFrame.OutParms @ +0x80`** to the head. Omitting it is the `__fastfail` that S52
mis-attributed to anti-tamper for six sessions (`docs/session-57-da-resolution.txt:118-138`). [M]

### 3.5 Risk

**LOW-to-MODERATE.** Zero module-image writes: an actor spawn plus one heap pointer write plus a
`Func`-thunk call — every element is in the S112-measured-safe class (heap/data writes 2/30 deaths
vs standing `.text` 10/10, Fisher p = 8e-8). The residual risk is **semantic, not protector-related**:
a cheat body may assume state the force-open world lacks (no ASC, no round phase — see
`supervive-hero-asc-exists`) and fault inside game code. Mitigate with `CallNativeGuarded` and by
starting with a read-only or self-contained verb.

⚠ Spawning an actor is itself a hazard with prior form: `KTESTACTOR` and `KSTATICTEST` both shipped
enabled and silently corrupted sessions for weeks. **Gate this behind an off-by-default `-D` and
delete the variant when it is settled.**

---

## 4. ROUTE B — manufacture the missing `UCheatManager`

### 4.1 Is the class registered and constructible? YES [M]

- `UCheatManager` resolves as an owner in the UHT class-registration table
  (`FClassRegisterCompiledInInfo`), which is what gives all 50 of its exec functions the owner name
  in `tools/re/out/uht_funcflags_tuthero.csv`. A class with a live `Z_Construct_UClass` is
  registered at startup and therefore has a CDO. [M]
- `schema.txt:10915` — `CheatManager : UClass:Object (3 props)`; `CheatManagerExtension` likewise. [M]
- `schema.txt:41023-41024` — `PlayerController` carries `CheatManager ObjectProperty` and
  `CheatClass ClassProperty` as **reflected UPROPERTYs**, so both are resolvable by name and
  writable as plain heap data. [M]

### 4.2 Is the payload real? YES, and this is the strong part [M]

**50 of 50** `UCheatManager` exec thunks are real dispatch (26 direct calls, 24 virtual); **none**
folds to `0x00F7EC20`. Against `ALokiCharacter`'s 8/10 empty in the same scan, that is a controlled
positive. Includes `Summon` (`0x035CA510`, 157 B, 1 param), `DamageTarget`, `Slomo`, `ViewActor`,
`DestroyAll`, `BugItGo`, `Fly`, `Ghost`, `God`, `Teleport`, `Walk`.

⚠ **Qualifier that matters:** `God`/`Fly`/`Teleport`/`Walk` thunks end in `jmp qword ptr [rax+0x300]`
etc. — **virtual dispatch**. The thunk proves a *call*, not a non-empty *callee*. Resolving those
vtable slots is a separate measurement nobody has done. Do not quote "48 real cheats"; quote
"50/50 thunks dispatch, 26 provably to a direct non-empty target".

### 4.3 Is it a DATA write only? Mostly — with one honest gap

- **Writing `PC->CheatManager` (+0x520) is pure heap data.** ✅
- **Constructing the object is not a `.text` write either**, and it does **not** need a raw
  `NewObject` call: **`UGameplayStatics::SpawnObject(TSubclassOf<UObject> ObjectClass, UObject* Outer)`
  is `Final|RequiredAPI|Native|Static|Public|BlueprintCallable`, thunk `0x0380FF40`, REAL, 218 B,
  `NumProperties=3 / StructureSize=24`** [M]. That is exactly the shape the S55 primitive calls
  today (`Outer = the PlayerController`). **No raw non-UFunction call is required.**
- ⚠ **`UCheatManager::InitCheatManager` is NOT a UFUNCTION** — no `FNameNativePtrPair` entry [M];
  in stock UE 5.4 it is a plain C++ virtual. Skipping it leaves `DebugCameraControllerRef` unset,
  so the DebugCamera family will not work. Everything else does not depend on it. [I]
- ⚠ `AddCheats` is dead as a shortcut: its whole body is inside `#if UE_WITH_CHEAT_MANAGER`
  (UE 5.4 `PlayerController.cpp:1107-1127`, read this session), and FK-6 measured that flag as 0.
  `EnableCheats` (`0x03C61920`, real thunk) just calls `AddCheats()` on the shipping branch, so it is
  a real function wrapping a dead one — **exactly the shape that looks like a lever and is not.**

### 4.4 What it buys, precisely

`UCheatManager::ProcessConsoleExec` runs its `CheatManagerExtensions` loop **and**
`Super::ProcessConsoleExec` (→ `CallFunctionByNameWithArguments`) **outside** the
`#if UE_WITH_CHEAT_MANAGER` block — verified against UE 5.4 `CheatManager.cpp:92-146` this session
(the `#endif` sits at ~line 133, before the loop). [M for the stock source; [I] that this build
compiled it the same way — **unverified in-binary**, see §7.]

So a populated `PC->CheatManager` gives you, *if* the string route works at all: 48 exec verbs by
name **plus** an arbitrary extension chain you control. And *regardless* of the string route it
gives you 50 UFunctions with a valid `Context` for Route A.

### 4.5 Risk

**MODERATE.** No module-image write, but you are constructing an engine object the shipping build
deliberately never constructs, on a `PlayerController` that has been running without one. `NewObject`
runs the constructor and a CDO copy; unknown Loki-side assumptions could be violated. It also adds a
live UObject to a GC graph the project has already been burned by (`supervive-gc-reachability-mechanism`)
— **hold a reference from the PC's own UPROPERTY (which is the point) so it is traversed normally;
do not poke RootSet bits (measured INERT, S110).**

---

## 5. ROUTE C — flip the gate with a heap `UFunction.Func` swap

### 5.1 The target [M]

`ULokiBlueprintLibrary::CheatsEnabled`: `NumProperties=1`, `StructureSize=1` (a `bool` return, **no
in-params**), `Static|BlueprintPure|Native`. Registered thunk **`0x051629C0`**:

```
+51629C0  push rbx ; sub rsp,0x20
+51629C6  mov  rax,[rdx+0x20] ... mov [rdx+0x20],rcx      ; P_FINISH
+51629DC  call 0xf7eb60                                   ; --> `xor al,al; ret`
+51629E1  mov  byte ptr [rbx], al                         ; *(bool*)Result = 0
+51629E8  ret
```

A replacement thunk is four instructions: do the same `P_FINISH` on `[rdx+0x20]`, then
`mov byte ptr [r8], 1; ret`. Write it into a `VirtualAlloc`'d RX page and store its address into
`UFunction.Func @ +0xE0` — **one aligned 8-byte heap store, zero module-image bytes**, identical in
kind to `FsScan`/`FsThunk` in `tutorial_launch.cpp:1372-1410`.

### 5.2 ICF: what else shares the stub — asked, measured, answered [M]

`0x051629C0` is the registered native pointer for **10** UFunctions:
`CheatsEnabled`, `DevGameModeCheatsEnabled`, `IsDebuggingMapView`, `IsEditor`, `IsNonShippingBuild`,
`IsPIECustomIDAuthEnabled`, `IsPlatformAndroid`, `IsTracing`, `IsWithEditor`, `StopTracing`.

★ That list is itself a **semantic positive control**: `IsEditor` / `IsWithEditor` /
`IsNonShippingBuild` are *known* false in a shipping build, so the fold target really is
"return false" and not a mis-read. (Likewise `0x052FD980`'s 12-way fold includes
`IsEasyAntiCheatEnabled`, which FK-10 independently established is false — EAC is absent.)

**The swap is still safe, and this is exactly why the technique matters:** a `Func` swap writes
**one UFunction object's pointer field**, so only that UFunction changes behaviour. ⚠ **Patching the
shared stub instead would flip all ten** — including `IsEditor`, which would send editor-only code
paths live in a shipping build. **Never patch the fold; always swap the pointer.**

### 5.3 What it actually unlocks — and the honest limit

Unknown, and that is the point. `CheatsEnabled` is the Blueprint-side gate (FK-13 §5); flipping it
opens whatever BP graphs test it. But **a gate on a graph that never runs changes nothing** — the
FK-11 "never-ran vs suppressed" trap, in its purest form.

★ **Route C is self-instrumenting, which makes it the best-value experiment per launch.** Make the
replacement thunk `InterlockedIncrement` a counter before returning `true`, and report it on the
`[FS]`-style heartbeat. Then one run answers *both* questions at once:

- `hits == 0` ⇒ **nothing calls `CheatsEnabled`; the gate is a decoy.** Close it, with a control.
- `hits > 0` ⇒ the gate is live, and whatever changed on screen is attributable.

Do the same to `AreHotkeyCheatsEnabled` (`0x052FD980`) in the same build — it is the same fold and
costs nothing extra.

⚠ Positive control for the swap itself: the `[FS]` machinery already prints
`*** ARMED AND LIVE: hitsGT=… ***` vs `*** THE SWAP IS A SILENT NO-OP ***`. **Reuse it.** A quiet
counter must not be readable as "nobody calls it" until the swap is proven armed.

### 5.4 Does a `Func` swap really intercept a **native static BlueprintPure**?

`UFunction::Invoke` loads `Func` and calls it; the VM reaches native functions through
`UObject::CallFunction` and `execCallMathFunction`, both of which end in `Function->Invoke(...)`.
[M that `Func` is the native entry — the S55 primitive is built on it and has worked for ~60 sessions;
**[I]** that the *game's own* BP call sites route through it.] The counter in §5.3 settles it
empirically on the first run, so the inference never needs to be trusted.

### 5.5 Risk

**LOWEST of the three.** One heap qword; no spawn, no new UObject, no module image. This is the
technique S112 shipped: heap-`Func`-swap arms measured **0/16 deaths at a matched 600 s hold**.
Reversible by writing the original pointer back (`FsScan(to, from, …)` already does this pattern).

---

## 6. The tooling: `tools/re/cheat_reach_probe.py`

Pure RPM, read-only, no injection, no `WriteProcessMemory` anywhere in the file. It imports its
reader / GUObjectArray walk / reflection walk from `console_probe.py`, so there is exactly one copy
of that code and one place for its offsets to be wrong.

| Section | Answers |
|---|---|
| `[CTRL]` | six UClasses that `schema.txt` proves are compiled in must resolve, **and** ≥1 live instance of `LokiGameInstance`/`PlayerController`/`GameViewportClient` must be found. Either failing ⇒ **VOID run**, not a negative |
| `[1]` | instance census of `LokiPlayerCheats`, `LokiPlayerCheats_AS`, `LokiClientPlayerCheats`, `CheatManager`, `CheatManagerExtension`, split CDO vs live; `--subclasses` also sweeps derived BP classes (a `BP_LokiPlayerCheats_C` instance would **not** show under the base name) |
| `[2]` | every `UPlayer::Exec` branch on the live PC: `PlayerInput`, `MyHUD`, `Pawn`, `AcknowledgedPawn`, `SpectatorPawn`, `CheatManager`, `CheatClass`, `PlayerCameraManager`, `Player`, plus Loki's `LokiPlayerCheats` slot. Offsets resolved **by name**, with the S114 literals `+0x520`/`+0x528` printed alongside and flagged on disagreement, plus a raw read at both literals as an independent cross-check |
| `[3]` | GameMode / GameState / HUD instances (the world-side branches) |
| `[4]` | `ULokiGlobals.DebugGlobals` → its CDO → `LokiPlayerCheats` `TSoftClassPtr` decoded — **which class the game itself would have spawned** (Route A step 1a) |
| `[5]` | for 11 target UFunctions, reads `UFunction.Func @ +0xE0` and compares it to the RVA measured offline this session. All-mismatch ⇒ `--base` wrong ⇒ VOID. One mismatch ⇒ a real finding |

```
python tools/re/cheat_reach_probe.py --self-test    # offline, 5/5 pass
python tools/re/cheat_reach_probe.py --dry-run      # parse/import only
python tools/re/cheat_reach_probe.py                # live, ELEVATED, read-only
```

### ⚠ It has NEVER been run against the game. Likeliest first failures, in order:

1. **Not elevated** → `OpenProcess` returns 0, exit 2. The game is launched elevated by
   `launch-redirect.ps1`; the probe must be too.
2. **Stale `RVA_NAMEPOOL` / `RVA_OBJOBJECTS`** after a game update → the header sanity gate trips and
   it exits 3 rather than printing junk.
3. **Run at the MENU instead of in a world** → section `[2]` finds no PlayerController and says VOID.
   That is the wrong game state, not a negative. Sections `[1]`, `[4]`, `[5]` still work at the menu
   — and `[1]` at the menu is the **cheapest possible test of whether `ULokiClientPlayerCheats` is
   instantiated by `LokiGameInstance`** (schema: it is prop #12 of 13).
4. **A renamed property** → that one row prints `NOT FOUND`; every other row still prints.
5. **`find_function`'s `UStruct::Children@0x50` / `UField::Next@0x30`** come from S55 and are the
   least-exercised offsets in the file; if section `[5]` reports "UFUNCTION NOT FOUND" for *every*
   row while `[CTRL]` passed, suspect these two before suspecting the game.

---

## 7. The single cheapest live experiment

**Run `cheat_reach_probe.py` against a game that is ALREADY RUNNING — at the menu is fine — before
spending a single launch on anything else.** It costs zero launches, is read-only, and is safe to run
mid-sitting. It answers, in one pass:

- is there a `ULokiClientPlayerCheats` instance? (**if yes, 5 exec verbs are callable TODAY with no
  spawn, no write, and no world** — the cheapest win on the board);
- is `PC->CheatClass` non-NULL? (if it is, Route B's object has a class to be; if NULL, Route B must
  supply `UCheatManager::StaticClass` itself);
- does `ULokiDebugGlobals.LokiPlayerCheats` name a real class? (Route A step 1a);
- do the 11 offline thunk RVAs still hold this launch? (validates every RVA in this document).

**Then**, and only then, spend one tutorial sitting on **Route C**, because it is one heap qword, it
carries its own positive control and its own hit counter, and it converts "does anything even ask
whether cheats are enabled?" from a 60-session open question into a number.

Route A is the one most likely to *do* something visible, but it costs a spawn and it exercises
`CT_SPAWNACTOR`, which has never run. Do it third, off-by-default, with `CallNativeGuarded`.

---

## 8. Risk summary

| Route | Module-image writes | Heap writes | New UObjects | Measured-safe class? | Verdict |
|---|---|---|---|---|---|
| **A** spawn + direct `Func` call | **none** | 1 pointer (`PC->LokiPlayerCheats`) | 1 Actor | yes (S112) | **LOW-MOD** — semantic risk only |
| **B** `SpawnObject` + `PC->CheatManager` | **none** | 1 pointer | 1 UObject | yes (S112) | **MOD** — constructing what shipping never constructs |
| **C** `Func` swap on `CheatsEnabled` | **none** | 1 qword | 0 | **yes, directly** (0/16 @ 600 s) | **LOWEST** |
| ~~patch the shared `0x00F7EB60` fold~~ | **`.text`** | — | — | **NO — 10/10 deaths** | ❌ **FORBIDDEN**, and it would flip `IsEditor` for 10 unrelated predicates |

The last row is the trap this document exists to close: the "obvious" fix — NOP the always-false
stub — is simultaneously the **one** action measured to be ~100 % lethal (S112, Fisher p = 8e-8)
**and** semantically wrong (ICF makes it a 10-way blast radius). The `Func` swap is strictly better
on both axes.

---

## 9. Corrections and open items

1. ⚠ **`0x05254180` is NOT `ret`.** `CLAUDE.md` and `docs/fk1-angelscript-settled.md` record
   `ALokiPlayerState::AuthSetSpawnTeamLeader 0x5254180 = ret`. Measured here, in
   `dumps/tutorial-hero` and in the cross-dump union, `0x05254180` is a **7-instruction `P_FINISH`
   exec thunk that tail-jumps to `0x00F7EC20`**, and it is the registered native pointer for **92**
   UFunctions. The *conclusion* ("empty body") is unchanged; the *byte-level description* on record
   is wrong, and it belongs to the exec **thunk**, not to the C++ member. This is the same
   RVA/thunk-vs-body confusion `docs/fk13-console-exec-settled.md` §6.1 flagged. **Not resolved here
   — flagged, with bytes.**
2. **Untested in-binary:** that *this build* compiled `UCheatManager::ProcessConsoleExec`'s
   extension loop outside the `#if` (§4.4). Stock UE 5.4 does; this image was not checked. The
   decisive test is finding that function and confirming it tail-calls
   `CallFunctionByNameWithArguments`. Attempted this session and **not achieved** — an xref of the
   `LogScriptCore` literal at `0x7739920` over the `.text` union returned **0 rip-relative matches**,
   which is uninterpretable without a control and is therefore recorded as a **failed instrument,
   not a negative**.
3. **Unmeasured:** the vtable targets of `UCheatManager`'s 24 virtual-dispatch exec thunks
   (`God`, `Fly`, `Teleport`, `Walk`, …). "50/50 thunks dispatch" is *not* "48 real cheat bodies".
4. **Six `ALokiPlayerCheats` exec thunks are coverage-blocked** (`CheatChangeHero`,
   `CheatTeleportLocation`, `CheatNoCooldowns`, `CheatMuteAudio`, `CheatSetEmote`,
   `CheatMeasureCursor`) — never executed, so never decrypted. §1 proves blocked ≠ absent for
   `CheatChangeHero` specifically (S76 resolved it live). A dump taken from a state that has run
   them would close the rest.
