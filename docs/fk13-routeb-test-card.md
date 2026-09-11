# FK-13 ROUTE B — live test card: install a `UCheatManager` on the live PlayerController

**Session 114 lane 4, 2026-08-12. This document was written OFFLINE — zero launches, zero
injections, zero writes to any process.** Every claim is tagged **[M]** measured (bytes read / a
tool run and its output quoted) or **[I]** inferred from a measurement.

> ### This SUPERSEDES `docs/fk13-live-test-card.md` for anything Route-B-shaped.
> That card's step list is about the console UI, `-ExecCmds` and `DebugExecBindings`, all three of
> which were settled offline afterwards (read its own SUPERSEDED banner). **Do not run its steps.**
> What is worth harvesting from it is the *method*: VOID≠FAIL, one variable per observation,
> delivery≠effect, and the screenshot-prefix discriminator. Those rules are carried forward here.

Prerequisite reading, in order: `docs/fk13-console-exec-settled.md` (what the exec surface IS) →
`docs/fk13-live-run-2026-08-12.md` (the live readings this is built on) →
`docs/fk13-exec-reach-plan.md` §4 (Route B as originally sketched) →
`docs/s112-fk7-ab-results.md` (why no module-image write is negotiable).
`memory/supervive-instrument-artifact-pattern` before you record any negative.

---

## 0. TL;DR

| | |
|---|---|
| **What the shim does** | `SpawnObject(PC->CheatClass, Outer=PC)` → store the result in the reflected `CheatManager` UPROPERTY at `PC+0x520`. **One aligned qword into a heap UObject field.** Nothing else is written. |
| **What that buys** | `UPlayer::Exec` branch 7 goes live ⇒ **42 real `UCheatManager` exec verbs** reachable by `ExecuteConsoleCommand("<verb>")`. |
| **Build** | `.\tools\sigbypass-mod\build.ps1 -Name tutorial_launch -Variant cheatmgr` (implemented, `RM_CHEATMGR=23`, `DoCheatMgr()` at `tutorial_launch.cpp:4789`). |
| **Where first** | ★ **MENU**, `-NoHook`, one launch. See §4 — but read §4.3 first, there is a build change you must make for the menu arm. |
| **Budget** | Sitting 1 (menu): ~25 min, one launch, historically **0 deaths in 11 `-NoHook` launches**. Sitting 2 (tutorial world): ~35 min, one staged launch, **FK-31 ~27 % die in staging**. |
| **Hard rule** | A step whose positive control is silent is **VOID**, not PASS and not FAIL. |
| **Pre-registered prediction** | Install **PASSES**; `LogLoc` **PASSES**; the whole thing is uneventful. Written down before the run, per project convention. |

---

## 1. What is already measured — the chain, end to end, offline

★★★ **New this lane (S114 lane 4).** Every hop from `ExecuteConsoleCommand` to a cheat body has now
been read at byte level in `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`
(ImageBase `0x7FF6505C0000`, file-offset == RVA, `.rdata`/`.data` **100 %** readable). This closes
`docs/fk13-exec-reach-plan.md` §9.2, which recorded the `ProcessConsoleExec` question as *untested
in-binary* after a failed xref attempt.

| # | Hop | Evidence | Grade |
|---|---|---|---|
| 1 | `UKismetSystemLibrary::ExecuteConsoleCommand` thunk `0x395D790` | 469 B real body; ends in `call qword ptr [rax+0xE70]` — a virtual call on the resolved PlayerController = `APlayerController::ConsoleCommand` | **[M]** body, **[I]** slot identity |
| 2 | `APlayerController::ConsoleCommand` → `Player->Exec(...)` | stock UE 5.4 `PlayerController.cpp`; and the project has driven `open LVL_Tutorial` + `HighResShot 1` through this path in 20+ runs | **[I]** strong |
| 3 | **`UPlayer::Exec` `0x3C36AA0` — all nine dispatch branches decoded** | see the table below | **[M]** |
| 4 | **branch 7 = `[PC+0x520]`, null-checked, `call [vtbl+0x288]`** | `0x3C36C3E: mov rcx,[rax+0x520]` · `0x3C36C45: test rcx,rcx; je` · `0x3C36C56: call [rax+0x288]` | **[M] decisive** |
| 5 | **`UCheatManager` vtable `.rdata 0x07FA7E28`, slot `+0x288` = `0x35B7430`** | 8 of 8 spot-checked slots match lane 3's independently-derived impl RVAs (`God +0x300`, `Slomo +0x308`, `Summon +0x338`, `BugItStringCreator +0x418`, `LogLoc +0x428`, `ToggleDebugCamera +0x380` = the fold) | **[M] decisive, 8/8** |
| 6 | `UCheatManager::ProcessConsoleExec 0x35B7430` (154 B) runs the extension loop over `[this+0x80]`/`[this+0x88]` **and then falls through** to `call 0x1343420` with a 5th stack arg `0` | disassembled in full | **[M]** |
| 7 | `0x1343420` **is** `UObject::CallFunctionByNameWithArguments` | it references all four `CallFunctionByNameWithArguments: …` literals (`0x7739920`, `0x77399B0`, `0x7739A40`, `0x7739AE0`) and gates each on `cmp byte[0x9E382E8],6` = `LogScriptCore >= Verbose` | **[M] decisive** |
| 8 | the verb's own exec thunk → its vtable impl | lane 3's grading, `tools/re/out/exec_chain_grade.txt` | **[M]** |

**`UPlayer::Exec` branch order — measured, and it matters** (`rdi`=UPlayer, `[rdi+8]`=PC,
`r13`=World, `rbx`=ExecActor):

| # | RVA of the dispatch | target |
|---:|---|---|
| 1 | `0x3C36B69` | `call 0x3F57F70` on the World (conditional) |
| 2 | `0x3C36B97` | `[PC+0x530]` PlayerInput |
| 3 | `0x3C36BB4` | the **PlayerController itself** |
| 4 | `0x3C36BD6` | ExecActor = `[PC+0x3F8]` Pawn, else `[PC+0x7D8]` SpectatorPawn |
| 5 | `0x3C36C05` | `[PC+0x468]` MyHUD |
| 6 | `0x3C36C2B` | `[World+0x250]` AuthorityGameMode |
| **7** | **`0x3C36C56`** | **`[PC+0x520]` CheatManager** ← Route B |
| 8 | `0x3C36C7A` | `[World+0x258]` GameState |
| 9 | `0x3C36CA3` | `[PC+0x470]` PlayerCameraManager |

★ **Branch 7 is SEVENTH, so a verb name that also exists on branches 1-6 would be intercepted
first. It cannot happen here: all 50 `UCheatManager` exec verb names are UNIQUE across every graded
class on the chain (0 collisions, measured over `exec_chain_grade.txt`).** [M]
And a same-named *non-exec* function on an earlier object returns `false`
(`Function not executable`), so the chain still continues. [M from the `0x1343420` literals]

★ `ALokiPlayerController::ProcessConsoleExec 0x569BE50` (branch 3) calls `Super` first, then
**null-checks `[this+0xA30]`** before forwarding — so the NULL `LokiPlayerCheats` on the way to
branch 7 is harmless. [M]

---

## 2. Risk table — every failure mode, its guard, and how the operator sees it

Legend for **Guard**: ✅ implemented in `DoCheatMgr()` today · ⚠ **GAP — close before the run** ·
◻ structural (no code needed, stated so nobody "fixes" it).

| # | Failure mode | Guard | How the operator detects it | Severity if unguarded |
|---|---|---|---|---|
| R1 | **PC not found** | ✅ `FindCheatablePC()` tries 4 class shapes and accepts only an object whose class *reflects both* `CheatManager` and `CheatClass`. This is exactly the S114 blind spot that produced a false "no PlayerController at the menu" (`PC_MainMenu_C` contains neither substring) | `[CHM] ABORT: no PlayerController reflecting CheatManager+CheatClass` | none (clean abort) |
| R2 | **Wrong object** (a component whose name contains "PlayerController" — 68 exist) | ✅ same reflection test; a component does not reflect `CheatClass` | `[CHM] cand '…' REJECTED: CheatManager@0xFFFFFFFF …` | **fatal** — a qword written into an unrelated object |
| R3 | **Stale PC pointer** (level travel between resolve and write) | ◻ resolve and write happen in the **same game-thread callback**; UE cannot destroy an actor from another thread mid-dispatch | n/a | fatal |
| R4 | **`CheatClass` NULL** | ✅ explicit `LooksLikePtr` guard before constructing | `[CHM] ABORT: CheatClass is NULL` | none |
| R5 | **`SpawnObject` returns NULL** | ✅ guard + it points the reader at `Loki.log` | `[CHM] ABORT: SpawnObject returned NULL` **plus** one of three named engine warnings — see R6 | none |
| R6 | **Wrong Outer / `Within` violation** | ◻ **`UGameplayStatics::SpawnObject` enforces `ClassWithin` ITSELF and returns nullptr** — it does not fault. Measured: the literal `UGameplayStatics::SpawnObject outer %s is not %s` is present at `.rdata 0x08078E60`, alongside `…no class specified` `0x08078D50` and `…null outer` `0x08078DE0`, emitted on `LogScript` whose **live runtime `Verbosity = 3 (Warning)`** at `.data 0x9D28BD8`, i.e. **they emit with no ini change** [M] | `Loki.log` line `LogScript: Warning: UGameplayStatics::SpawnObject outer … is not …` | fatal → downgraded to a named log line |
| R7 | **Returned object is not `UCheatManager`-derived** | ⚠ **GAP.** `DoCheatMgr` reads and *prints* `ClassOf(obj)` but stores it regardless. **Add `if(ocls != cheatCls) ABORT`** — pointer equality against the class we passed in is exact, cheap, and cannot be fooled | `[CHM] constructed 0x… class=<name>` — today you must read this by eye | **fatal on the first console command anywhere**: branch 7 does `mov rax,[rcx]; call [rax+0x288]`, so a non-CheatManager object calls whatever its slot 0x288 happens to be |
| R8 | **Torn / unaligned pointer store** | ⚠ **GAP.** `g_chmOffMgr` comes from reflection and is never checked for alignment. **Add `if(g_chmOffMgr & 7) ABORT`.** x86-64 guarantees atomicity only for naturally-aligned qword stores; branch 7 reads this field from the game thread with no lock | nothing today | **fatal, intermittent** — the worst kind |
| R9 | **Offset drift** (`CheatManager` moves off `+0x520` after a game update) | ⚠ **GAP (soft).** The offset is correctly resolved **by name**, which is right — but nothing cross-checks it against the S114 literal. **Print a WARN if `g_chmOffMgr != 0x520`**, matching `cheat_reach_probe.py` §[2]'s "print both, flag disagreement" pattern. Do NOT abort on it | `[CHM] PC=… CheatManager@0x520 CheatClass@0x528` — compare by eye | low |
| R10 | **Garbage collection takes the object** | ✅ stored into the reflected `CheatManager` UPROPERTY, so it is traversed by ordinary GC reachability — **the measured S110 lesson** (poking the RootSet bit is INERT in this build; parking in a real UPROPERTY is what worked). ⚠ **Correct the comment**: `RF_StrongRefOnFrame` is `0x01000000` and means only *"references from persistent function frames are strong"* (`ObjectMacros.h:567`) — **it creates no reference and gives no grace period** [M]. The object is unreferenced from `SpawnObject`'s return until the store. The store is in the same callback, so the window is zero — but the reason is the same-callback ordering, not the flag | `[CHM] *** INSTALLED … readback verified ***`, then re-read `PC+0x520` externally 2-3 min later (§5 step 8) | delayed fatal (dangling pointer at branch 7) |
| R11 | **Re-entrancy / double arm** | ✅ three layers: `g_inHook`, `g_done=1` after one dispatch, and an explicit idempotence read of `PC+0x520` that bails with `ALREADY INSTALLED` | `[CHM] ALREADY INSTALLED: CheatManager=0x…` | wasted object, GC churn |
| R12 | **Racing another PI-hooking shim** | ✅ `FsArm()` refuses if the `ProcessInternal` prologue is already hooked. And Route B does not hook PI at all | `[CHM] FAIL funcswap arm` | fatal |
| R13 | **A module-image write sneaks in** | ✅ **structural**: `#if KFUNCSWAP` … `#else` **refuses to build a working binary** (`return 7` with a printed reason) rather than silently falling back to `InstallHook()`'s 5-byte `.text` patch. That fallback is the construct S112 measured at **10/10 armed-window deaths vs 3/36, Fisher p = 7e-8** | `[CHM] REFUSING TO RUN with KFUNCSWAP=0` — and §3.5's artifact check | **near-certain process death** |
| R14 | **The Func-swap arms nothing** (menu) | ✅ self-reporting: `[FS] *** ZERO TARGETS SWAPPED ***` or `[FS] *** NO GAME-THREAD HITS … SILENT NO-OP ***`. ⚠ but see §4.3 — the default target is profiled from the **tutorial world**, not the menu | `[FS]` lines in the marker | **VOID run** (not a false negative — but a wasted launch) |
| R15 | **A cheat body faults on state the world lacks** | ✅ `CallNativeGuarded` (SEH `__except`) wraps every native call. ⚠ it does **not** wrap a fault that happens later, e.g. inside a verb dispatched by the game's own `ExecuteConsoleCommand` on a subsequent frame | `[CHM] … FAULTED` | crash |
| R16 | **Level travel after install** | ◻ not a crash: the new PC is constructed with `CheatManager = NULL`. It is a **capability loss**, and the shim is one-shot so it will not reinstall | `PC+0x520` reads NULL again after travel | none |
| R17 | **Mid-GC write** | ◻ impossible: UE's GC runs on the game thread, and our write *is* on the game thread inside a UFunction dispatch | n/a | fatal |
| R18 | **The marker file is truncated by a later injection** (FK-25) | ✅ `configs/fk24-stage.ps1` copies the marker off after every step; on the menu route inject nothing after the probe | missing `[CHM]` lines | lost evidence |

### 2.1 The three code changes to make before the run

They are all small, all in `DoCheatMgr()`, and each closes a gap that no external instrument can
see afterwards:

```cpp
// R9 — soft cross-check against the S114 literal (WARN, never abort: by-name is the right source)
if(g_chmOffMgr!=0x520||g_chmOffCls!=0x528)
    Markerf("[CHM] WARN: reflected offsets 0x%X/0x%X differ from the S114 literals 0x520/0x528\r\n",
            g_chmOffMgr,g_chmOffCls);

// R8 — alignment. Branch 7 reads this field from the game thread with no lock.
if(g_chmOffMgr & 7){ Markerf("[CHM] ABORT: CheatManager@0x%X is not 8-aligned; a store there is "
                             "not atomic and branch 7 could observe a torn pointer\r\n",g_chmOffMgr); return; }

// R7 — class identity. Exact, because SpawnObject constructs precisely the class we handed it.
if(ocls!=cheatCls){ Markerf("[CHM] ABORT: constructed class 0x%llX (%s) != requested 0x%llX -- NOT storing\r\n",
                            (unsigned long long)ocls,on,(unsigned long long)cheatCls); return; }
```

---

## 3. Verification design

### 3.1 The run has TWO independent halves. Grade them separately.

Merging them is how a project ends up saying "Route B failed" when in fact the object installed
perfectly and the verb was the wrong choice.

| Half | Question | Instrument | Costs |
|---|---|---|---|
| **H1 — construct + install** | is `PC+0x520` a live `UCheatManager`? | **external RPM read**, no game interaction at all | nothing |
| **H2 — the string router reaches it** | does `ExecuteConsoleCommand("<verb>")` dispatch through branch 7 and run a body? | `Loki.log`, with `LogScriptCore=Verbose` | one console command |

**H1 can PASS while H2 VOIDs, and that is still a large result** — it proves the object can be
constructed and installed, which is the part nobody has ever done in this build.

### 3.2 ★★★ The keystone instrument: `LogScriptCore=Verbose`

`UObject::CallFunctionByNameWithArguments` (`0x1343420`) carries **four** diagnostics, each gated on
`cmp byte[0x9E382E8], 6` (= `LogScriptCore >= Verbose`), whose **live runtime value is 5 (`Log`)**
and whose `CompileTimeVerbosity` is **7 (`VeryVerbose`)** — so they are compiled in and currently
switched off. Raising the category switches them on. [M, both bytes read from `.data`, which is
100 % readable in a dump taken from a real staged session]

| literal | RVA | meaning |
|---|---|---|
| `CallFunctionByNameWithArguments: Not Parsed '%s'` | `0x07739920` | arguments unparseable |
| `CallFunctionByNameWithArguments: Name not found '%s'` | `0x077399B0` | the token is not even in the FName pool |
| `CallFunctionByNameWithArguments: Function not found '%s'` | `0x07739A40` | this object has no such UFunction |
| `CallFunctionByNameWithArguments: Function not executable '%s'` | `0x07739AE0` | found it, but no `FUNC_Exec` |

**Why this is the best instrument this project has for an exec test:**

- It fires **per chain participant**, so a single bogus command produces one line for every object
  `UPlayer::Exec` visits. That gives you a **counted, external, zero-side-effect positive control
  that the router ran at all** — the exact thing every previous exec attempt lacked.
- **The single-variable design falls out of it.** Issue the same bogus verb *before* install and
  *after* install. Adding a CheatManager adds one more object to the walk, so the count must go
  **N → N+1**. Nothing else on the chain changed.
- A silent result is now interpretable: silence with a *known-good* control line = "the command
  never reached the router"; silence *without* the control = VOID.

⚠ Its own trap: `Name not found` uses `FNAME_Find`, so a token that never existed as an FName
short-circuits before `FindFunction`. Use it deliberately — see the two probes below.

### 3.3 Verb selection — evaluated, not guessed

Criteria: real body (not the `0x00F7EC20` fold, not coverage-blocked) · few/simple params · effect
observable by an instrument *outside the game* · non-destructive · safe with no world assumptions.

| verb | grade [M, lane 3] | observable? | verdict |
|---|---|---|---|
| ★ **`LogLoc`** | REAL, 307 B, vtbl `+0x428` → `0x35B3680`, **0 params** | **YES — two `LogCheatManager` lines**, see below | ★ **PRIMARY** |
| ★ `God` | REAL, 221 B, vtbl `+0x300` → `0x35AFD70`, 0 params | **YES — one bit**, `Pawn+0x6A & 4` (`bCanBeDamaged`), RPM-readable and toggleable | ★ **SECONDARY** |
| `Slomo <f>` | REAL, vtbl `+0x308` → `0x35BEC10`, 1 float | yes (`WorldSettings.TimeDilation`, and visually) but it perturbs the whole world | third |
| `Summon <cls>` | REAL, 1093 B, 1 `FString` | yes (object census) but it spawns an actor into a world we barely understand | not first |
| `DestroyAll` / `DestroyPawns` | REAL | destructive | ❌ never |
| `ToggleDebugCamera`, `ToggleAILogging`, `TestCollisionDistance` | **FOLDED-STUB → `0x00F7EC20`** | a null is meaningless | ❌ VOID by construction |
| `ViewActor` / `ViewClass` / `ViewPlayer` | **COVERAGE-BLOCKED** (page never executed) | unknown | ❌ not a test |

★★ **`LogLoc` is the right first verb, and the reason is measured.** It calls `BugItStringCreator`
through vtbl `+0x418` (`0x359EBF0`), which contains:

```
0x359EC6D  lea rdx, [0x7FA89A8]  wide = "BugItGo %f %f %f %f %f %f"
0x359ECD6  cmp byte ptr [0x9F85518], 5      <- LogCheatManager.Verbosity
0x359ECE4  jb  skip                          <- i.e. LOG IF >= Log(5)
0x359ECFA  lea rcx, [0x9F85518]              <- the category passed to the emitter
0x359ED64  lea rdx, [0x7FA89E0]  wide = "?BugLoc=%s?BugRot=%s"
```

and **`LogCheatManager`'s live runtime `Verbosity` is exactly 5 (`Log`)** at `.data 0x9F85518`
(`05 00 05 07` = Verbosity 5, DebugBreakOnLog 0, Default 5, CompileTime 7). ⇒ **`LogLoc` logs with
NO ini change at all**, it changes **no game state whatsoever**, and its output strings have never
appeared in this project's logs. [M]

⚠⚠ **`God` does NOT log, and the shim currently claims it does.**
`tutorial_launch.cpp:1374` sets `KCMVERIFYCMD` to `"God"` with the comment *"observable in Loki.log
via LogCheatManager / 'God mode'"*. **Measured: that is unfounded.** `God`'s body references the
wide literals `God mode on` (`0x7FA8390`), `God Mode off` (`0x7FA83A8`) and `No APawn* possessed`
(`0x7FA83C8`), then `call 0x3C2BF20` — a small RPC stub that loads a cached `UFunction*` from
`0x9FA7C90` and calls `ProcessEvent` (`0x1344150`). It references **no log category at all**;
`ClientMessage` routes to `TeamMessage` → the HUD, and **`MyHUD` is NULL in the tutorial world**
(measured, `fk13-live-run-2026-08-12.md` §2c). ⇒ **change `KCMVERIFYCMD`'s default to `"LogLoc"`.**
`God` stays valuable as the *second* verb precisely because it changes state, but its observable is
the `bCanBeDamaged` bit read by RPM, never a log line.

**The two probe strings, pre-registered:**

| probe | string | expected before install | expected after install |
|---|---|---|---|
| **P-CTRL** (router-ran control) | `ZZQNotAVerbQQ` | `LogScriptCore: Verbose: CallFunctionByNameWithArguments: Name not found 'ZZQNotAVerbQQ'` × **N** | × **N+1** |
| **P-VERB** (the payload) | `LogLoc` | `…Function not found 'LogLoc'` × N, and **no** `LogCheatManager:` line | **`LogCheatManager: BugItGo <x> <y> <z> <p> <y> <r>`** and `LogCheatManager: ?BugLoc=X=…?BugRot=P=…` |

`LogLoc` is a live FName (it is a registered UFunction name), so before install it yields
*Function not found*, not *Name not found* — those two lines discriminate "the object is absent"
from "the token is nonsense" for free.

### 3.4 `[Core.Log]` configuration — checked against the binary before recommending

Every candidate was verified to exist as a UTF-16LE literal in the image, with controls:

| token | wide hits | whole-token | note |
|---|---:|---:|---|
| `LogAccelByte` | 22 | 1 | **CONTROL +** (FK-11 measured live 3→52 lines) |
| `LogAbilitySystem` | 3 | 1 | **CONTROL +** (FK-11 measured live 25→4161) |
| `LogTemp`, `LogOnline`, `LogInit`, `LogLokiPlayerController` | 2/25/1/1 | 1 each | **CONTROL +** |
| `LogNotACategoryAtAll`, `LogZzzzQqqqNope` | 0 | 0 | **CONTROL −** |
| ★ `LogCheatManager` | 1 | 1 | `0x07F9BCF0` — **exists**; runtime `Verbosity=5 (Log)`, `CompileTime=7` [M] |
| ★ `LogScriptCore` | 1 | 1 | `0x07738758` — **exists**; runtime `Verbosity=5 (Log)`, `CompileTime=7` [M] |
| `LogExec` | 1 | 1 | `0x076B96E0` — exists; runtime verbosity **unmeasured** |
| `LogConsoleResponse` | 1 | 1 | `0x07696A70` — exists; runtime verbosity **unmeasured** |
| `LogPlayerController` | 3 | 1 | `0x081A2A10` — exists (the `Dump*State` verbs use it) |
| `LogScript` | — | — | the `SpawnObject` warnings; runtime `Verbosity=3 (Warning)` ⇒ **already emitting** [M] |
| `LogGameplayStatics`, `LogLokiPlayerCheats` | 0 | 0 | **do not put these in the ini — they do not exist** |

6/6 positive controls resolve and 2/2 negative controls are zero, so the instrument is not blind.
[M]

**Apply, from an elevated PowerShell:**

```powershell
.\configs\set-log-verbosity.ps1 -Preset Mechanism -Categories @{
    LogScriptCore       = 'Verbose'   # ★ THE keystone: the 4 dispatcher diagnostics
    LogCheatManager     = 'Verbose'   # already Log; Verbose costs nothing and adds BugIt* chatter
    LogExec             = 'Verbose'
    LogConsoleResponse  = 'Verbose'
    LogPlayerController = 'Verbose'
}
```

Use `-Preset Mechanism`, **not** `Gas` — `Gas` adds ~4,000 `LogAbilitySystem` lines that will bury
the four lines you are looking for. `LogTemp=Fatal` comes along free with the preset and reclaims
97.5 % of the log. Verify afterwards with `.\configs\check-log-verbosity.ps1`.

⚠ **Mechanism, not command line.** FK-11 measured (flown live, 2026-08-09) that
`-ini:Engine:[Core.Log]:…` is applied **too late** and does not bind, with a clean control — and
that `-LogCmds` does not parse at all. The user `Engine.ini` is the only path that works.
`set-log-verbosity.ps1` backs up, clears ReadOnly, merges, and re-sets ReadOnly for you.

### 3.5 Artifact verification — proving "no module-image write" from the built DLL

S112's check was *`FlushInstructionCache` / `VirtualAlloc` / `VirtualFree` are ABSENT from the
import table*. That worked there because `SafeWrite` was linker-eliminated. **It will NOT work
here**: `tutorial_launch.cpp` is one translation unit and `RM_CHEATMGR` is a mode inside it, so
`SafeWrite` and `InstallHook` remain linked for the other modes even though this mode refuses to
call them. **An import-table check would produce a false FAIL and must not be used as the gate.**

Use this instead, in order of strength:

```powershell
# 1. Standard artifact gate (no C++ EH, no CRT, DLL shape) — necessary, not sufficient
python tools\sigbypass-mod\verify_dll.py build\tutorial_launch_cheatmgr.dll

# 2. .text hash, so an A/B can never be run against a copy of itself (CLAUDE.md's rule)
python - <<'PY'
import hashlib,struct
d=open(r'build\tutorial_launch_cheatmgr.dll','rb').read()
pe=struct.unpack_from('<I',d,0x3C)[0]; n=struct.unpack_from('<H',d,pe+6)[0]
so=pe+24+struct.unpack_from('<H',d,pe+20)[0]
for i in range(n):
    b=so+i*40; nm=d[b:b+8].rstrip(b'\0').decode()
    vsz,va,rsz,raw=struct.unpack_from('<IIII',d,b+8)
    if nm=='.text': print('.text sha256', hashlib.sha256(d[raw:raw+rsz]).hexdigest()[:16], rsz,'B')
PY

# 3. THE DECISIVE ONE — the build must contain the refusal, i.e. KFUNCSWAP really is 1
python -c "d=open(r'build\tutorial_launch_cheatmgr.dll','rb').read(); \
print('REFUSAL STRING PRESENT (=> KFUNCSWAP=0 build):', b'REFUSING TO RUN with KFUNCSWAP=0' in d); \
print('HEAP-ROUTE STRING PRESENT (=> KFUNCSWAP=1 build):', b'NO .text write' in d)"
```

Check 3 is the one that matters: `[CHM] KFUNCSWAP=1: … NO .text write` is compiled in **only** on
the heap arm and `[CHM] REFUSING TO RUN…` **only** on the other, so the two are mutually exclusive
discriminators baked into the artifact. **Expected: heap-route TRUE, refusal FALSE.**

**And the run-time proof, which beats all three:** the marker must contain
`[CHM] KFUNCSWAP=1: game-thread callback via UFunction.Func (+0xE0) -- NO .text write`
and **must not** contain `FAIL InstallHook` / `FAIL PI prologue`. Those two strings only exist on
paths that write `.text`.

---

## 4. WHERE TO RUN IT FIRST

### 4.1 Recommendation: **MENU FIRST.** Agreed with the operator's lean, and here is the reasoning.

| | menu (`-NoHook`) | staged tutorial world |
|---|---|---|
| launch hazard | **0 deaths / 11 launches × 320 s** (S111 `-NoHook` control) | **FK-31: 22/82 (27 %)** die before anything is injected |
| `CheatClass` populated | ✅ **measured non-null** (`0x26B40855100`) | ✅ **measured non-null** (`0x195F72A5100`) |
| PC exists | ✅ `PC_MainMenu_C @0x26C8A80C040` | ✅ `BP_LokiPlayerController_Dev_C @0x19666190010` |
| Pawn (branch 4, and `God`'s target) | ✅ `BP_MainMenuPawn_C` | ✅ `BP_HERO_Ronin_C` |
| MyHUD (branch 5) | ✅ `BP_MainMenuHUD_C` | ❌ NULL |
| wall clock per attempt | ~4 min to menu | ~10 min of staging, ~2 in 4 launches reach the armed window |
| what it can prove | **H1 completely; H2 completely** (`LogLoc` needs only a PC + camera manager) | H1+H2, **plus** verbs that need a possessed hero |

**Both halves of Route B are fully testable at the menu.** `LogLoc` needs a PlayerController and a
PlayerCameraManager, both live at the menu; the CheatManager's `Within` class is
`APlayerController`, satisfied by `PC_MainMenu_C`. There is no reason to spend a 27 %-mortality
staged launch to learn something a free launch answers.

### 4.2 What the menu run *cannot* answer, so plan sitting 2 honestly

- Verbs that need a possessed pawn in a real world (`Teleport`, `Fly`, `Ghost`, `Walk`, `Summon`,
  `DamageTarget`).
- Whether `BP_LokiPlayerController_Dev_C`'s `ProcessConsoleExec` override (branch 3, which forwards
  to the NULL `+0xA30`) interacts badly — it is null-guarded [M], so this is a formality.
- Whether the install survives the map travel *into* the tutorial (it will not — R16; the world
  travel destroys the PC. **In sitting 2, inject the cheatmgr shim AFTER `sp` reports
  `[SP] done step=4`, never before the map load.**)

### 4.3 ⚠⚠ ONE BUILD CHANGE IS REQUIRED FOR THE MENU ARM — do not skip this

`KFSNAME` defaults to `"ReceiveTickClient"` (`tutorial_launch.cpp:1350`). That target was chosen
from a **measured settled-tutorial-world profile** (S112: 1549 hits / 90 s). **Nothing has ever
measured whether a BP UFunction named `ReceiveTickClient` is dispatched at the main menu.** If it
is not, `FsArm()` swaps a pointer nothing ever calls, `FsHold` burns `KCMHOLDMS` (120 s) and the
run is a self-reported VOID — a wasted launch, not a wrong answer, but still wasted.

**Register and use an all-functions arm for the menu:**

```powershell
# tools/sigbypass-mod/build.ps1, in the tutorial_launch $Variants map, next to 'cheatmgr':
'cheatmgr-allfns' = @('-DKRUNMODE=RM_CHEATMGR','-DKFSNAME=""')
```

`KFSNAME=""` arms every BP UFunction (~17,126 pointers) — the exact footprint S112 flew as
`play-funcswap` and measured at **0/8 deaths over a full 600 s hold**. RM_CHEATMGR disarms the
moment `g_done` is set (typically the first game-thread dispatch, well under a second), so its
exposure is orders of magnitude smaller than that. Use `cheatmgr-allfns` at the menu and plain
`cheatmgr` in the tutorial world where `ReceiveTickClient` is measured to tick.

---

## 5. SITTING 1 — the card. One `-NoHook` menu launch, run top to bottom.

Steps are ordered and the order is load-bearing. Write down the wall-clock time of every step.

### Step 0 — pre-flight (~6 min, no launch, nothing touched)

```powershell
cd "G:\git\Supervive Revival Project"

# 0.1  Close the three gaps in §2.1, then build BOTH arms.
.\tools\sigbypass-mod\build.ps1 -Name tutorial_launch -Variant cheatmgr-allfns
.\tools\sigbypass-mod\build.ps1 -Name tutorial_launch -Variant cheatmgr

# 0.2  Artifact gate (§3.5). Expect: verify_dll PASS; heap-route TRUE, refusal FALSE;
#      and the two .text hashes DIFFERENT from each other.
python tools\sigbypass-mod\verify_dll.py build\tutorial_launch_cheatmgr_allfns.dll

# 0.3  Probe self-tests, offline, touch nothing.
python tools\re\cheat_reach_probe.py --self-test
python tools\re\cheat_reach_probe.py --dry-run

# 0.4  Log config (§3.4), then show what will be written before writing it.
.\configs\set-log-verbosity.ps1 -Preset Mechanism -Categories @{LogScriptCore='Verbose';LogCheatManager='Verbose';LogExec='Verbose';LogConsoleResponse='Verbose';LogPlayerController='Verbose'} -WhatIf
.\configs\set-log-verbosity.ps1 -Preset Mechanism -Categories @{LogScriptCore='Verbose';LogCheatManager='Verbose';LogExec='Verbose';LogConsoleResponse='Verbose';LogPlayerController='Verbose'}

# 0.5  Baseline the two payload strings. BOTH MUST BE ZERO across the whole corpus,
#      or your discriminator is contaminated and must be redesigned.
Select-String -Path "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\*.log" -Pattern 'BugItGo |CallFunctionByNameWithArguments' -List
```

**GATE:** if 0.2 fails, or 0.5 finds prior hits, **STOP**. Do not launch.

### Step 1 — launch (~4 min)

**Steam must already be running**, or login dies with `Auth Failure 14005`.

```powershell
# ELEVATED PowerShell, repo root. -NoHook = the safest run this project has.
.\configs\launch-redirect.ps1 -NoHook
```

Wait for the main menu. `launch-redirect.ps1` archives any pending crashpad report before it
launches, so the previous sitting's evidence is already safe.

### Step 2 — log-mechanism positive control (~1 min) — **before anything else**

```powershell
.\configs\check-log-verbosity.ps1
```

- **PASS:** `LogAccelByte` is well above its pinned baseline of 3 lines and shows `Verbose` entries.
- **VOID for the whole sitting** if it is still at ~3: the ini did not bind, so every log-based
  reading below is uninterpretable. Fix the ini and relaunch. **Do not proceed.**

### Step 3 — BASELINE the exec chain, install nothing (~2 min)

This is the *before* half of the single-variable comparison, and it costs one console command.

```powershell
# Read the chain as shipped. Note the PID and base it prints.
python tools\re\cheat_reach_probe.py | Tee-Object docs\fk13-routeb-before-$(Get-Date -Format yyyyMMdd-HHmmss).txt
```

Read `[CTRL]` **first** — if it fails, the run is VOID and nothing below means anything.
Then record: `PC = 0x…`, `CheatManager +0x520 = NULL` (expected), `CheatClass +0x528 = <UClass ptr>`
(expected non-null).

Now issue the two probe commands **while nothing is installed**. There is no in-game console, so
this needs the shim — which is precisely why it is cheaper to take the baseline from the *log of
this same run* after install (§5 step 6 reads both halves out of one file). **If you have no way to
issue a command pre-install, skip the pre-install counts and use the "absolute" criteria in §6
instead of the delta criteria — say so in the results table.**

### Step 4 — INSTALL (~2 min). **This is the first write this project has ever made to the game.**

```powershell
.\tools\inject\inject.exe (Get-Process SUPERVIVE-Win64-Shipping).Id `
    "G:\git\Supervive Revival Project\build\tutorial_launch_cheatmgr_allfns.dll"
Get-Content docs\tutorial-launch-marker.txt -Tail 40
```

⚠ **`-Hook`-style injection silently fails ~1 in 10** (S111). Never assume "copied the file ⇒
injected". The marker naming this DLL *is* the delivery proof.

**Read the marker in this order — each line is a gate:**

| line | verdict |
|---|---|
| `[CHM] KFUNCSWAP=1: … NO .text write` | ✅ the arm is the heap route |
| `[FS] *** ARMED AND LIVE: hitsGT=… ***` | ✅ game-thread callbacks are landing |
| `[FS] *** ZERO TARGETS SWAPPED ***` or `NO GAME-THREAD HITS … SILENT NO-OP` | **VOID** — see §4.3 |
| `[CHM] PC=0x… class=… CheatManager@0x520 CheatClass@0x528` | ✅ resolution by name agrees with the literals |
| `[CHM] SpawnObject ok -> 0x…` | ✅ construction |
| `[CHM] SpawnObject FAULTED` / `returned NULL` | **FAIL** — go to §6 row F2, and grep `Loki.log` for `LogScript: Warning: UGameplayStatics::SpawnObject` which names *which* guard rejected us |
| `[CHM] constructed 0x… class=CheatManager` | ✅ class identity (R7) |
| `[CHM] *** INSTALLED: PC(0x…)->CheatManager@0x520 = 0x… -- readback verified ***` | ★ **H1 PASS** |

### Step 5 — EXTERNAL confirmation of H1 (~2 min). Independent instrument, no game interaction.

```powershell
$pid  = (Get-Process SUPERVIVE-Win64-Shipping).Id
$base = '0x' + ('{0:X}' -f (Get-Process SUPERVIVE-Win64-Shipping).MainModule.BaseAddress.ToInt64())

# Read the field the shim claims it wrote. <PC> = the address from the [CHM] line.
python tools\re\read_field.py $pid <PC-hex> 520 528

# Independent census: how many live UCheatManager instances exist now?
python tools\re\obj_by_class.py $pid $base CheatManager
```

- **PASS:** `+0x520` decodes to a UObject whose class is `CheatManager`, **and** `obj_by_class`
  reports **CDO 1 / LIVE 1** (it was CDO 1 / LIVE 0 in every prior reading — `fk13-live-run` §1).
- **FAIL:** `+0x520` reads NULL despite the marker claiming a verified readback ⇒ the object was
  collected or the write went somewhere else. **Do not issue any console command.** Go to §7.
- **VOID:** `read_field` cannot open the process (not elevated).
- **CONTROL:** `+0x528` must still decode to the same UClass it did in step 3. If both reads look
  wrong, suspect the reader, not the game.

### Step 6 — H2: drive it (~4 min). One command at a time, ~10 s apart, times written down.

Issue the commands via a second injection of the `cheatmgr-verify` arm (`KCMVERIFY=1`,
`KCMVERIFYCMD` changed to `LogLoc` per §3.3), or via whatever single-command driver lane 1 ships.
**Order is fixed: control first, payload second.**

```powershell
# 6a  P-CTRL — the router-ran control. Nonsense verb, no side effects possible.
#     (build once with -DKCMVERIFYCMD="ZZQNotAVerbQQ")
# 6b  P-VERB — LogLoc.
# then:
Select-String -Path "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log" `
  -Pattern "CallFunctionByNameWithArguments|LogCheatManager:|UGameplayStatics::SpawnObject" |
  Tee-Object docs\fk13-routeb-after-$(Get-Date -Format yyyyMMdd-HHmmss).txt
```

| observation | verdict |
|---|---|
| `LogScriptCore: Verbose: CallFunctionByNameWithArguments: Name not found 'ZZQNotAVerbQQ'` ≥ 1 | ★ **the router ran.** Every negative below is now interpretable. |
| that line absent | **EVERYTHING BELOW IS VOID.** Not FAIL. The command never reached `CallFunctionByNameWithArguments`. |
| `LogCheatManager: BugItGo <6 floats>` **and** `LogCheatManager: ?BugLoc=…?BugRot=…` | ★★★ **H2 PASS — a `UCheatManager` exec verb executed via the string router.** |
| `…Function not found 'LogLoc'` present, no `BugItGo` line | **H2 FAIL with a clean control**: the router ran, walked the chain, and the CheatManager was not on it (or was not asked). A real, publishable negative. |
| neither | VOID |

### Step 7 — `God`, the state-changing second verb (~3 min, OPTIONAL, menu only)

Only if step 6 PASSED. Read `Pawn+0x6A` before and after; bit `0x04` is `bCanBeDamaged`.

```powershell
python tools\re\read_field.py $pid <PAWN-hex> 68      # inspect the byte at +0x6A in the qword
# ... issue `God` ... then repeat. Issue `God` again to restore.
```

PASS = the bit flips. This is the only reading in the card that proves a cheat verb **mutated game
state**, and it is fully reversible.

### Step 8 — GC durability (~3 min). Do not skip; this is R10.

Wait **3 minutes** (the measured GC period is ~61.1 s — `tools/re/item_watch.py --marker` — so this
crosses at least two passes), then repeat step 5.

- **PASS:** `+0x520` still decodes to the same `CheatManager` address.
- **FAIL:** it reads NULL or a different address ⇒ the UPROPERTY parking argument is wrong for this
  object and the whole approach needs rethinking. ★ **This would be a genuinely new finding** and
  must be written up — do not paper over it by rooting harder (S110 measured RootSet poking INERT).

### Step 9 — shut down and collect (~4 min)

```powershell
Copy-Item docs\tutorial-launch-marker.txt "docs\fk13-routeb-marker-$(Get-Date -Format yyyyMMdd-HHmmss).txt"
Copy-Item "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log" "docs\fk13-routeb-run-$(Get-Date -Format yyyyMMdd).log"
# close the game normally, THEN:
.\configs\archive-crashdumps.ps1 -Label fk13-routeb-s1
.\configs\set-log-verbosity.ps1 -Revert          # leave the machine clean
```

---

## 6. Decision table

| # | H1 (install) | H2 control | H2 payload | Verdict → next action |
|---|---|---|---|---|
| **A** | PASS | fires | `BugItGo` present | ★★★ **ROUTE B WORKS.** 44 exec verbs are online with one heap qword. Write it up, update `CLAUDE.md` + `supervive-cheat-surface-inventory`, then sitting 2 in the tutorial world for the world-dependent verbs. |
| **B** | PASS | fires | `Function not found 'LogLoc'` | ★★ Install works, router works, **the CheatManager is not being asked**. Re-read `UPlayer::Exec` branch 7 against the LIVE bytes (`tools/re/disasm_live.py`) — the offline `.text` page may not be what is executing. |
| **C** | PASS | silent | — | **H2 VOID, H1 PASS.** Still a large result: the object constructs and installs. Next: prove `ExecuteConsoleCommand` reaches `UPlayer::Exec` at all by running `HighResShot 1` through the same driver — 259 prior PNGs make that a known-good positive control (`fk13-live-test-card.md` §1.2). |
| **D** | FAIL — `SpawnObject` returned NULL | — | — | Read `LogScript: Warning: UGameplayStatics::SpawnObject …` — it names which of the three guards rejected us. `outer … is not …` ⇒ the PC we picked is not a `ClassWithin` match ⇒ R2, fix `FindCheatablePC`. |
| **E** | FAIL — `SpawnObject FAULTED` | — | — | SEH caught it, nothing was written, the process is intact. Capture the marker; next attempt should resolve `SpawnObject` on the tutorial route instead (its CDO/params may differ at the menu). |
| **F** | VOID — `[FS] ZERO TARGETS` / `SILENT NO-OP` | — | — | The Func-swap never got a game-thread dispatch. **§4.3.** Rebuild with `KFSNAME=""` (menu) and retry. **Record VOID, not FAIL.** |
| **G** | VOID — `[CTRL]` failed in step 3 | — | — | Probe RVAs stale or not elevated. Fix the instrument. Record nothing about the game. |
| **H** | PASS, then step 8 FAIL | — | — | ★ New finding: the UPROPERTY parking does not hold this object. Write it up; it contradicts S110's mechanism and is worth more than Route B itself. |
| **I** | process died | — | — | §7. Classify by fault family **before** attributing it to Route B. |

---

## 7. Rollback and crash capture

**There is no "undo" to run — and that is by design.** The shim writes exactly one heap qword and
`FsDisarm()` restores the swapped `UFunction.Func` pointers. Nothing persists past process exit:
no file is modified, no module image is touched, no config is changed except the `[Core.Log]` block
(which `set-log-verbosity.ps1 -Revert` restores from its timestamped backup).

**If the process dies:**

```powershell
# 1. FIRST. Do not relaunch — the NEXT LAUNCH is what destroys the pending crashpad report (S109).
.\configs\archive-crashdumps.ps1 -Label fk13-routeb-DEATH

# 2. Preserve the marker and that run's log before anything overwrites them.
Copy-Item docs\tutorial-launch-marker.txt "docs\fk13-routeb-DEATH-marker-$(Get-Date -Format yyyyMMdd-HHmmss).txt"

# 3. Classify by FAULT FAMILY, never by elapsed time.
python tools\crashtri\mdctx.py dumps\crashpad-*-fk13-routeb-DEATH\reports\*.dmp
```

**Attribution rules, stated before the run so they cannot be chosen after it:**

- `RIP == <runtime.dll base> + 1`, EXECUTE, `ExceptionInformation[0]==8` ⇒ **the protector**, i.e.
  the `.text`-write family — which this mode does not perform. Treat it as evidence of something
  *else* in the process, not of Route B.
- Exit code `0x0000DEAD` ⇒ **FK-32**, `NtTerminateProcess(h, 0xDEAD)` at `runtime.dll` RVA
  `0x80f7f0`. Not ours (our `Stop-Process` exits `0xFFFFFFFF`, measured). Harvest it, do not chase it.
- A fault at a `.text` RVA inside `catalog_store_fix.dll` (`0x205d`) ⇒ the known primary-shim TOCTOU,
  not Route B. `-NoHook` means it should not be present at all.
- **A death with `[CHM] *** INSTALLED ***` in the marker and a wild indirect call in the dump is the
  signature R7/R8 predict.** That is the one outcome that would indict Route B directly. Say so.

**If the game hangs rather than crashes:** hold an OS handle open across the kill so the exit code
survives (S112's free instrument) — `$p = Get-Process SUPERVIVE-Win64-Shipping; $p.Kill();
$p.WaitForExit(); $p.ExitCode`.

---

## 8. ★ What we CANNOT guard against — read this before authorising the run

Stated plainly, because the operator is the one taking the risk.

1. **The constructor.** `NewObject<UCheatManager>` runs `UCheatManager`'s C++ constructor and a CDO
   property copy. We have not disassembled that constructor. It is a class the shipping build
   deliberately never constructs, so it has **zero runtime hours in this binary**. If it touches a
   subsystem that shipping stripped, it faults inside `SpawnObject` — SEH-caught by
   `CallNativeGuarded`, so *probably* survivable, but SEH cannot recover a corrupted heap.
2. **Skipping `InitCheatManager()`.** Stock `AddCheats` calls it; we do not (it is not a UFUNCTION,
   so the primitive cannot reach it without a hand-built vtable index). Stock's version broadcasts
   `OnCheatManagerCreatedDelegate` and registers an `OnEndPlay` cleanup. **We do not know whether
   Loki overrides it**, and if Loki's override initialises state its own verbs assume, some verbs
   will misbehave in ways we cannot predict. The `ToggleDebugCamera` family is already dead (folded
   stub) so the usual reason to call it does not apply.
3. **Branch 7 is now live for the WHOLE PROCESS, not just for us.** Any console command issued by
   anything — the game's own Blueprints, our force-open `open LVL_Tutorial`, `HighResShot` — will
   now walk into `UCheatManager::ProcessConsoleExec`. If our object is ever wrong or stale, the
   fault surfaces at an unrelated call site and will look like someone else's bug.
4. **The 44 "real bodies" are graded by size and dispatch shape, not by execution.** Six of the 50
   are folded or coverage-blocked and are listed. But "REAL, 221 B" is not "safe in this world".
   Every verb beyond `LogLoc` and `God` is genuinely untested here.
5. **The protector.** Everything measured says a heap-only write is in the safe class
   (S112: 2/30 vs 10/10, Fisher p = 8e-8; heap-bytecode patches 0/9). But **nobody has ever written
   to a live UObject field in this process before.** The measured-safe class covers `UFunction.Func`
   swaps and script-bytecode edits; a `TObjectPtr` field in a `UPROPERTY` is the same *kind* of
   write, and that is an **[I]**, not an **[M]**.
6. **We have never made a shim-free tutorial run**, so any tutorial-route death still has an
   unexcluded game-defect explanation. That is unchanged by this work.
7. **`FsArm()` swapping ~17,126 `Func` pointers at the menu** (§4.3) is a footprint no menu-route
   sitting has flown. S112 flew it in the tutorial world at 0/8 over 600 s; the menu is a different
   population of BP UFunctions. Our exposure is under a second, which is the mitigation, but it is
   not a measurement.

**Net honest assessment:** the *mechanism* is as well-characterised as anything this project has
attempted — nine hops, every one read at byte level, 8/8 vtable slots matching, all three
`SpawnObject` failure modes carrying named log lines. The residual risk is concentrated in (1) and
(2), i.e. in code we have not read, and it is bounded by SEH and by a `-NoHook` menu launch that
has historically never died.

---

## 9. Recording rules and artifacts

1. **VOID ≠ FAIL.** Any step whose positive control was silent is VOID. Write VOID in the table.
2. **Delivery ≠ effect.** The marker naming the DLL proves injection; it never proves the write
   landed. Step 5's external RPM read is the only thing that proves that.
3. **One variable per observation.** The pre/post `Name not found` count is the design; if you lose
   the pre-install count, use §6's absolute criteria and *say which you used*.
4. **Absence in the log is evidence only next to P-CTRL.** No `BugItGo` line with no
   `Name not found` line is VOID, not a negative.
5. **Grade H1 and H2 separately** in the write-up, always.

| artifact | path |
|---|---|
| shim source | `tools/sigbypass-mod/tutorial_launch.cpp` — `DoCheatMgr()` at `:4789`, `FindCheatablePC()` at `:4769`, `KCMVERIFYCMD` at `:1374`, `KFSNAME` at `:1350`, run-mode dispatch at `:1002` and `:6930` |
| build variants | `tools/sigbypass-mod/build.ps1` — `cheatmgr`, `cheatmgr-verify`, **add `cheatmgr-allfns` (§4.3)** |
| before/after probe output | `docs/fk13-routeb-{before,after}-<stamp>.txt` |
| marker | `docs/fk13-routeb-marker-<stamp>.txt` (copy it — FK-25: every injection truncates the live marker) |
| run log | `docs/fk13-routeb-run-<date>.log` |
| offline grading of all 50 verbs | `tools/re/out/exec_chain_grade.txt` §`UCheatManager` |
| this card's measurements | reproduce with `CG_DUMP=dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe CG_BASE=0x7FF6505C0000 python tools/re/offline_disasm.py <rva> <n>` |

### 9.1 Key RVAs, for the write-up

| symbol | RVA | grade |
|---|---|---|
| `UPlayer::Exec` | `0x3C36AA0` | 9 branches, branch 7 = `[PC+0x520]` |
| `UCheatManager` vtable | `.rdata 0x07FA7E28` | slot `+0x288` = `ProcessConsoleExec` |
| `UCheatManager::ProcessConsoleExec` | `0x35B7430` | 154 B, extensions loop + fallthrough |
| `UObject::CallFunctionByNameWithArguments` | `0x1343420` | 4 `LogScriptCore` diagnostics |
| `UCheatManager::LogLoc` | thunk `0x35C8210` → impl `0x35B3680` (vtbl `+0x428`) | REAL, 307 B, 0 params |
| `UCheatManager::BugItStringCreator` | `0x359EBF0` (vtbl `+0x418`) | holds the `BugItGo` emit |
| `UCheatManager::God` | thunk `0x35C7FD0` → impl `0x35AFD70` (vtbl `+0x300`) | REAL, 221 B, no log |
| `UGameplayStatics::SpawnObject` | thunk `0x380FF40` → impl `0x37F0710` | REAL, three named guards |
| `UKismetSystemLibrary::ExecuteConsoleCommand` | thunk `0x395D790` | REAL, 469 B |
| `LogCheatManager` `FLogCategory` | `.data 0x9F85518` | live `Verbosity=5 (Log)`, CompileTime 7 |
| `LogScriptCore` `FLogCategory` | `.data 0x9E382E8` | live `Verbosity=5 (Log)`, CompileTime 7 |
| `LogScript` `FLogCategory` | `.data 0x9D28BD8` | live `Verbosity=3 (Warning)` |
