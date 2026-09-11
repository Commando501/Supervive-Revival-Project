# FK-13 SETTLED — the dev console is compiled out, but the EXEC SURFACE IS ALIVE

**Session 114, 2026-08-12. Entirely offline: zero game launches, zero injections.**

Every claim is tagged **[M]** measured (bytes were read) or **[I]** inferred (reasoning on a
measurement). Read `supervive-instrument-artifact-pattern` before adding to this file.

---

## 0. Verdict

FK-13's belief was: *"Binary scan confirmed the dev console is fully stripped … all cheap external
paths are now exhausted; the remaining options require in-process code."*
(`docs/dedicated-server-stub.md:541-556`, Session 3.)

| Claim | Verdict |
|---|---|
| The dev console is gone | ✅ **TRUE** — `ALLOW_CONSOLE == 0`, three independent instruments |
| …because the config-side enable knobs were stripped | ❌ **FALSE** — all four knobs ship (S101) |
| …and S3 missed them because it scanned the packed binary | ❌ **ALSO FALSE** — see §4 |
| Keyboard-triggered exec (`DebugExecBindings`) is available | ❌ **FALSE** — config-loaded, never evaluated |
| `-ExecCmds` is a usable channel | ❌ **FALSE** — the switch does not parse |
| **"All cheap external paths are exhausted ⇒ injection only"** | ❌ **FALSE — THIS IS THE FINDING** |

**The operational conclusion is the part that was wrong.** `UE_ALLOW_EXEC_COMMANDS == 1` in this
build, **138 native UFunctions carry `FUNC_Exec`**, the whole dispatch chain is compiled, and
`UKismetSystemLibrary::ExecuteConsoleCommand` is a `BlueprintCallable` entry point reachable by the
project's existing S55 native-call primitive — **no console, no `.text` write.** The console UI was
removed; the exec *machinery* behind it was not.

---

## 1. Why FK-13 was really three questions

UnrealBuildTool exposes three **independent** shipping-hardening flags. The project treated them as
one. [M — `TargetRules.cs:1368,1374,1429`; `UEBuildTarget.cs:5064,5073,5145`, local UE 5.4 tree at
`H:\Unreal Engine\UE_5.4`]

| TargetRules flag | Emits | Stock default | This build |
|---|---|---|---|
| `bUseLoggingInShipping` | `USE_LOGGING_IN_SHIPPING` | 0 | **1** (FK-11, measured) |
| `bUseConsoleInShipping` | `ALLOW_CONSOLE_IN_SHIPPING` | 0 | **0** (§2) |
| `bUseExecCommandsInShipping` | `UE_ALLOW_EXEC_COMMANDS_IN_SHIPPING` | **1** | **1** (§3) |

Note the middle row's default is 0 and the bottom row's is **1**. Theorycraft opted *into* logging
(a non-default), left exec commands at their permissive default, and left the console off. There is
no single "hardening" switch and reasoning about one from another is invalid. [M for the flags; [I]
for the intent]

A fourth gate is **not** a target flag at all: `#if !UE_BUILD_SHIPPING`, which no `Target.cs` can
flip. That is what kills `DebugExecBindings` (§3A).

---

## 2. `ALLOW_CONSOLE == 0` — three independent instruments agree

### 2.1 Code (strongest)

`UGameViewportClient::Init` = RVA **`0x0384FB00`**, extent `0x0384FB00..0x03850212` (1,810 B, exact
`.pdata` bound), fully decrypted in **both** dumps. Identified four independent ways, not guessed:
target of `call [rax+0x2e0]` at `0x037DD881` inside `UGameEngine::Init`; correct
`Init(FWorldContext&, UGameInstance*, bool)` argument setup; references
`L"DefaultViewportMouseCaptureMode="` at `.rdata 0x08088340`; reads `UInputSettings` CDO `+0x88`. [M]

It performs the stock UE5 sequence immediately **before** and **after** the console block —
`WorldContext.AddRef(World@0x80)` at `0x0384FB2B`, `GameInstance@0x88 = OwningGameInstance` at
`0x0384FBD0` — and contains **zero** reads of `UEngine::ConsoleClass` (`+0x120`) and **zero** stores
to `UGameViewportClient::ViewportConsole` (`+0x48`). The `NewObject<UConsole>` +
`GLog->AddOutputDevice` pair is simply absent. [M]

Corroboration: three functions whose *entire body* is inside `#if ALLOW_CONSOLE` all resolve to this
image's universal folded empty stub at RVA `0x00F7EC20` (`c2 00 00` = `ret 0`; that 8-byte pointer
occurs 165,789 times image-wide) — `UGameViewportClient::SetConsoleTarget` (vtable `+0x2D0`, same in
all three viewport-client vtables) and `APlayerController::SendToConsole` (vtable `+0xD90`). [M]

### 2.2 Guard-exclusive string markers (independent method)

Single variable = guard membership. Controls and tests both drawn from **`Console.cpp`**, i.e. the
same translation unit and the same `.rdata` neighbourhood; the five test literals were verified
guard-exclusive across **24,864** UE source files before use.

| | tutorial-hero (`.rdata` 100.0% **readable**) | merged (`.rdata` **99.64% readable-by-page**; the 63.1% often cited is the non-zero-BYTE figure — not commensurable, see the retraction below) |
|---|---|---|
| Controls *outside* `#if ALLOW_CONSOLE` (`console.position.enable`, `con.MinLogVerbosity`, `[%i more matches]`, …) | **8/8 present**, `0x824CDC8`–`0x82588B0` | 8/8 |
| Markers *exclusive* to the guard (`(opens connection to localhost)`, `open 127.0.0.1`, `travel %s`, …) | **0/5** | 0/5 |

`dumps/tutorial-hero`'s `.rdata` is 37,212,160 B at **100.0% readable** per its own manifest, so
absence there is not a coverage artifact. [M]

### 2.3 Literal-pool gap in `UEngine::Exec`

The verb pool at `.rdata 0x8247718-0x8247838` is complete and in stock source order — FLUSHLOG,
GAMEVER, GAMEVERSION, STAT, STOPMOVIECAPTURE, CRACKURL, DEFER, STREAMMAP, CE, GAMMA, SCALABILITY,
DUMPTICKS, CANCELASYNCLOAD, NETPROFILE — **and the gaps are exactly the compile-guarded verbs.** [M]

### 2.4 What survives anyway

`UConsole` itself **is** fully compiled and registered: `GetPrivateStaticClass` = `0x03F00F70`,
vtable `.rdata 0x08257B10` with real bodies in `0x3F133B0..0x3F3DB70`. `UEngine::ConsoleClass` is
still resolved at startup — `UEngine::InitializeObjectReferences` (`0x03EE53FC`) runs the stock
`LoadEngineClass<UConsole>` triple at `0x03EE5606`. [M]

⇒ **The class exists and the class pointer is populated; only the viewport never constructs one.**
`GEngine->GameViewport->ViewportConsole` will be **NULL**.

### 2.5 Consequences — do not spend launches on these

- Pressing `~` cannot open a console, and **no config change alters that.**
  `config-control-plane-s101.md` §5 levers **#1 and #4 are dead**, and its probes **P1, P2, P4** are
  answered offline. ✅
- `ULokiGameViewportClient` does **not** re-add a console: its vtable differs from the base in only
  4 of 122 slots, and neither `Init` (`+0x2E0`) nor `SetConsoleTarget` (`+0x2D0`) is among them. [M]

---

## 3. The exec surface — ALIVE

### 3A. `DebugExecBindings`: config-loaded, **never evaluated** [M, decisive]

`Engine/Config/BaseInput.ini` ships exactly **16** `+DebugExecBindings`; `DefaultInput.ini`'s
`[/Script/Engine.PlayerInput]` adds and removes none; and S80i measured `DebugExecBindings @+0x1A8
Num=16` **live** (as its own positive control, `fk2-input-settled.md:477`). Exact match ⇒ the config
path works. [M]

**But nothing reads the array.** In stock UE 5.4 the entire evaluation path —
`ExecInputCommands` (PlayerInput.cpp 2189-2316), `GetBind`, `GetExecBind`, and both `InputKey` call
sites (314-326, 393-400) — is inside `#if !UE_BUILD_SHIPPING`. Measured here:

- The `PlayerInput.cpp` wide-literal pool (`.rdata 0x08258980 → 0x08258E60`) is intact and in exact
  stock source order, then ends cleanly at the next TU — **with a clean gap exactly where the
  guarded block's literals belong.** 6 same-file controls present; `NoDebugExecBindings` and
  `KEYBINDING` (the only two literals unique to that block) both **0**. [M]
- Region-scoped disassembly: **0** TArray-shaped accesses at displacement `0x1A8` anywhere in the
  PlayerInput code region, against a control of **925** TArray-shaped pairs at 89 other offsets in
  that same region. [M]

⇒ **Keyboard-triggered exec is dead. Do not spend a launch pressing F9.** (An earlier draft of this
session's reasoning proposed exactly that; it was wrong and is retracted here.)

### 3B. `-ExecCmds` does not parse [M]

**0** wide occurrences of `ExecCmds` in a 100%-readable `.rdata`, against five same-class `FParse`
switch literals that all resolve in the identical scan: `LogCmds` (3 wide, `0x76B25E2`), `LOG=` (5),
`ABSLOG=` (2), `FORCELOGFLUSH` (2), `NOCONSOLE` (1). Cross-checked against the on-disk shipped exe as
a second image; both agree. [M]

This is the **second** switch to fail this way — `-LogCmds` was found non-functional in FK-11 for a
different reason (all 3 hits are help text). Treat any UE command-line switch as unverified until a
literal is located.

⚠ It also re-explains S3 probes #6/#7: `-ExecCmds="open 127.0.0.1:7777"` failed **twice over** — the
switch does not parse, *and* `OPEN` is `#if !UE_BUILD_SHIPPING` inside `UGameEngine::Exec` (§2.3).
S3 read that null as "the console is stripped," which is a third, unrelated fact.

### 3C. `UE_ALLOW_EXEC_COMMANDS == 1` — the machinery is compiled [M]

- `UEngine::Exec` @ `0x3ED66C0`, **2,521 B real body**; plus `UGameEngine::Exec`,
  `UGameInstance::Exec`, `UGameViewportClient::Exec_Runtime` (`0x383A570` + `0x383A677`, 2,432 B).
- `FSelfRegisteringExec::StaticExec` is on the dispatch path.
- `UObject::CallFunctionByNameWithArguments` — the `FUNC_Exec` dispatcher — is compiled; all four of
  its `LogScriptCore, Verbose` literals are present and contiguous (`0x7739920`–`0x7739AE0`).
- The **IConsoleManager cvar channel** is fully compiled: `dumpcvars`, `dumpccmds`, `setcvar`,
  `unsetcvar`, `No CVar named %s`, `Error: %s is read only!` (`0x769D380`–`0x769D9E0`).
- `UGameViewportClient::Exec_Runtime`'s verb pool is complete: FORCEFULLSCREEN, SHOW, SHOWLAYER,
  VIEWMODE, PRECACHE, FULLSCREEN, SETRES, **HighResShot**, HighResShotUI, **SHOT**, BUGSCREENSHOT,
  KILLPARTICLES, DISPLAY, DISPLAYALL, … TEXTUREDEFRAG; `showui` at `0x8089238`.

### 3D. **138 native `FUNC_Exec` UFunctions** [M]

Counted from UHT's `FFunctionParams` statics (layout calibrated against 4 ground-truth functions;
the `ObjectFlags@+0x34 == 0x45` test passes on 18,325/22,028 candidates and the 3,703 rejects are
reported, not dropped):

| Class | Exec fns | | Class | Exec fns |
|---|---:|---|---|---:|
| `UCheatManager` | 48 | | `ULokiClientPlayerCheats` | 5 |
| `ALokiPlayerCheats` | 25 | | `ULokiTimelineManager` | 5 |
| `APlayerController` | 13 | | `UGameViewportClient` | 3 |
| `ALokiCharacter` | 10 | | `UHealthSnapshotBlueprintLibrary` | 3 |
| `ALokiPlayerController` | 8 | | `UGameInstance`, `UAbilitySystemGlobals`, `UAISystem` | 2 each |
| `AHUD` | 6 | | `ADebugCameraController` | 1 |
| `UPlayerInput` | 5 | | | |

★ **This does not contradict FK-6, it re-scopes it.** FK-6's *"console `Exec` = 0/500"* was measured
over the **500 Angelscript UFUNCTIONs**. It was never a statement about native ones. [M]

### 3E. ★ The reachable entry point

`UKismetSystemLibrary::ExecuteConsoleCommand` — `Z_Construct 0x38BCCB0`, flags `0x04022403`
(`BlueprintCallable|Native|Static|Public`), exec thunk **`0x395D790`** with a real body
(`.pdata 0x395D790-0x395D965`). [M]

In UE 5.4 it calls `IConsoleManager::Get().ProcessUserConsoleInput()` first, then falls back to
`TargetPC->ConsoleCommand()` / `GEngine->Exec()`. It is a static `BlueprintCallable` — **exactly the
shape the S55 native-call primitive already calls**, with no `.text` write. [M for the symbol; [I]
for "therefore the primitive can call it" — untested]

---

## 4. Corrections to prior art

1. **S3's ABSENT table is overturned for 6 of its 10 tokens** — and the *reason* recorded in S101 is
   also wrong. All six are readable in the **shipped on-disk exe with a plain ASCII search**, so
   *"S3 scanned the packed binary where `.rdata` was encrypted"* does not explain the miss. The real
   cause is unrecovered; do not propagate the packed-binary explanation. [M]
2. **Four of S3's ten tokens carry no information at all** and must come off any ABSENT list:
   `/Script/Engine.Console` is a config *value* with no reason to be in the exe; `-cheat`, `-cheats`,
   `allowcheats`, `ToggleConsole` are not UE5 identifiers; `ALLOW_CONSOLE` / `UE_ALLOW_EXEC_COMMANDS`
   are preprocessor symbols that never survive compilation. Their zeros are meaningless. [M]
3. **UHT strips the `F`/`U`/`A` prefix** for reflected names (`KeyBind`, `Console`,
   `LokiPlayerCheats`) while *keeping* it in the UTF-16 class-registration Name field. Probing
   `FKeyBind`/`UConsole` produces a false ABSENT. [M]
4. **The rule "strings cannot decide `ALLOW_CONSOLE`" needs a scope qualifier.** It is true of
   *UHT-emitted* names (which are emitted regardless of the flag) and false of *guard-exclusive
   `TEXT()` literals* (§2.2). Recording the unqualified rule would foreclose a method that works.

---

## 5. Falsified leads (recorded so nobody re-walks them)

- ❌ **Loki's data-driven debug menu.** `FLokiDebugUICommand{Kind, Tab, Label, ConsoleCommand}`,
  `EDebugMenuEntryKind{ConsoleCommand, ConsoleVariableBool}`, `ULokiDebugGlobals.DebugCommands`, and
  `ALokiPlayerController::{Show,Hide,Toggle}DebugMenu()` all exist and are reflected — and
  **`ShowDebugMenu` / `HideDebugMenu` / `ToggleDebugMenu` are empty bodies.** [M]
  `ToggleDebugMenu` being bound to `Ctrl+\` in the live `UserSettings.ini` means nothing.
- ❌ **The shipped cheat key bindings.** `ULokiBlueprintLibrary::CheatsEnabled` — the actual
  Blueprint gate behind `ShowCheats`/RightAlt — folds to `xor al,al; ret` (always false). [M]
- ❌ **`viewmode wireframe` as a probe.** This build ships the refusal string *"Debug viewmodes not
  allowed in Test or Shipping builds."* at `0x08089190`; a null is uninterpretable. [M]
- ❌ **"The cheat action names are absent from the binary."** Instrument artifact, caught by control:
  four action names *known live right now* from `UserSettings.ini` (`CheatKillMe`, `CheatNextHero`,
  `OpenGlobalShop`, `CheatToggleInvulnerable`) also score 0/0. The instrument cannot see action names
  at all. Would have been instance #26. [M]
- ❌ **`tools/extractor/out/assetregistry_namemap.txt` for input-event binders** — 0 of 191,398 rows
  contain `InpActEvt`; per-asset name tables do. Coverage-blocked, not negative. [M]

---

## 6. What is still open

1. **Are `ALokiPlayerCheats` (25 exec fns) / `ULokiClientPlayerCheats` (5) ever instantiated?**
   They are Loki-authored, *not* `UCheatManager` subclasses, so FK-6's `UE_WITH_CHEAT_MANAGER == 0`
   argument does not obviously cover them, and their thunks have real bodies
   (`CheatTeleportLocation 0x5422360`, `CheatChangeHero 0x54179B0`, `EnableHotkeyCheats 0x5424670`).
   Settle by RPM: look them up in GUObjectArray on a live process.
2. **Is `APlayerController::CheatManager` (`+0x520`) / `CheatClass` (`+0x528`) non-NULL at runtime?**
   Pure RPM read, zero risk. Non-NULL would unlock 48 more exec verbs.
3. **Does `ExecuteConsoleCommand` actually work here?** Everything in §3 is a static-image argument;
   **no exec command has ever been issued in this build.** First live test should carry
   `[Core.Log] LogScriptCore=Verbose, LogExec=Verbose, LogConsoleResponse=Verbose` (FK-11 mechanism)
   so the outcome is diagnosed rather than binary.
4. **`APlayerController::LocalTravel`** — stock body is *unguarded* and calls
   `ClientTravel(URL, TRAVEL_Relative)` when `GetNetMode()==NM_Standalone`. That is exactly what S3
   wanted from `open` and never got. Exec thunk `0x3C64600`.
5. **Which of the 138 exec functions are stubs?** Only 6 verified by disassembly; zero-parameter ones
   can be graded, parameterised ones need a bounded thunk walk `uht_funcflags.py` does not yet do.

### ✅ 6.1 An unrelated discrepancy that needs its own check — **RESOLVED S115**

> **RESOLVED 2026-08-12 — `docs/fk1-stub-claim-recheck.md`. Lane 3's measurement was CORRECT.
> So was FK-1's. They describe two different addresses.**

Lane 3 measured `ALokiGameMode::SpawnPlayer @0x534C070`, `ALokiTeamState_TeamOnly::SetDropLeader
@0x2C2CE30` and `ALokiDropPlane::OverridePlaneLocations @0x53372A0` in **two** independent dumps as
**large real functions with security cookies and parameter steps** — directly contradicting
`CLAUDE.md` and `docs/fk1-angelscript-settled.md:168-171`, which record all three as bare
`xor eax,eax; ret` / `ret` stubs ("the real wall").

~~**This is flagged, not resolved.**~~ **Resolution:** those RVAs are the `execFoo` **thunks** and
they really do hold real code (lane 3 ✓). Each thunk's **implementation target** is a folded empty
stub at an RVA FK-1's table never printed — `SpawnPlayer` → `0x0F7EB50` (`xor eax,eax; ret`), the
other three → `0x0F7EC20` (`ret 0`) — so FK-1's bytes are right too ✓. FK-1's *"the real wall"* and
its closure of `AvatarActor = NULL` **stand** (empty-impl base rate 1.2 %, 78/6,669).

⚠ The one sentence here that **falls**: *"One of the two measurements is wrong — most likely an
RVA/VA or image-base confusion on one side."* Neither is wrong, and there is **no base confusion
anywhere** — both dumps are flat and byte-identical at every address involved. The false statement
was manufactured in the `CLAUDE.md` **digest** (an `=` substituted for a dropped "exec thunk" column
header), not in either source doc. `CLAUDE.md` has since been corrected.

⚠ Also settled here: `0x5254180` is **91-way ICF-folded and NON-IDENTIFYING** — it is the shared
zero-parameter exec thunk, which is why it appears in this document family under at least seven
different function names (`docs/fk13-live-run-2026-08-12.md:18,19,27`,
`docs/fk6-cheat-impl-census.csv:119,138,166`). Always print fold multiplicity next to a folded RVA.

---

## 7. Tooling added this session

| Path | What |
|---|---|
| `tools/re/console_probe.py` | Pure-RPM live probe: `ViewportConsole`, `UConsole` instances, `ConsoleClass`, decoded `DebugExecBindings`, `ConsoleKeys`. 6/6 offline self-test; **never run live** |
| `tools/re/exec_surface_probe.py` | Exec-surface static analysis |
| `tools/re/console_census.py` + `console_tokens*.txt` | Controlled wide+ASCII multi-image census |
| `tools/re/uht_funcflags.py` + `out/uht_funcflags_tuthero.csv` | `FFunctionParams` decoder → the 138 `FUNC_Exec` table |
| `configs/set-debug-execbindings.ps1` | Writes a user-layer `Input.ini`. **Now largely moot** (§3A) — keep only as the untested probe of whether a user `Input.ini` is read at all |
| `docs/fk13-live-test-card.md` | One-sitting live card — **partially superseded**, see its banner |

⚠⚠ **RETRACTED 2026-08-14 (S121, FK-18) — the rule here used to read "always run `.rdata`
presence/absence claims against `dumps/tutorial-hero/…` (`.rdata` 100.0%), never `merged.dump.exe`
alone (63.1%)". It compares two different instruments** — 100.0% is `dumpimage`'s **readable-byte**
figure, 63.1% is `mergedumps`' **non-zero-byte** figure — i.e. it is **FK-3 re-committed**, in the
same document whose own table (§ the 8/8-controls / 0/5-markers rows above) shows **both images
agreeing**. That agreement was the control that falsified the reason, printed alongside the rule.
**MEASURED: `.rdata` completeness is identical in every image on disk** — the same **33 all-zero pages
of 9,085 at the same RVAs** in all 11 dumps and in `merged.dump.exe` (symmetric difference 0; 99.64%
readable-by-page). tutorial-hero's net advantage is **2,907 bytes of 37.2 MB (0.0078%) and 0 pages**,
and 6,760 of the 6,761 differing positions sit at offset ≡ 2 (mod 8) — **relocation, not coverage.**
⇒ **`.rdata` presence/absence is safe in ANY image.** ⚠ **Every FK-13 conclusion resting on an
`.rdata` absence stands unchanged** (`ALLOW_CONSOLE == 0`, the `Console.cpp` guard-exclusive markers,
the `UEngine::Exec` literal-pool gap) — only the stated justification was metric-confused.
★ What genuinely differs between images is **`.text`**: use `dumps/merged2.dump.exe` (16,625 decrypted
pages, 54.90%) for anything code-shaped. See `docs/fk18-fk19-multistate-merge-settled.md`.
