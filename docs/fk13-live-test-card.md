# FK-13 live test card — one menu launch, run top to bottom

> ## ⚠⚠ PARTIALLY SUPERSEDED — READ `docs/fk13-console-exec-settled.md` FIRST
>
> This card was written in parallel with three other S114 lanes and **could not see their
> results**. Those lanes settled offline, decisively, several questions this card was built to
> ask live. Do **not** run it as written.
>
> **Answered offline — DELETE these steps, do not spend a launch on them:**
> - **`ALLOW_CONSOLE == 0`**, three independent instruments (disassembly of
>   `UGameViewportClient::Init @0x0384FB00`; guard-exclusive `Console.cpp` literals 8/8 controls
>   vs 0/5 markers at `.rdata` 100 %; the `UEngine::Exec` literal-pool gap). Pressing `~` cannot
>   work and `ViewportConsole` **will be NULL** — so probe sections **[A]/[B]** are now
>   *confirmations of a prediction*, worth ~30 s of a launch you are taking anyway, not a test.
> - **`DebugExecBindings` are config-loaded but NEVER EVALUATED** — the `#if !UE_BUILD_SHIPPING`
>   block is absent from a 100 %-readable `.rdata` (clean literal-pool gap, 6 same-file controls
>   present) and there are **0** TArray accesses at `+0x1A8` in the PlayerInput code region
>   against a 925-access control. ⇒ **steps 7 and 8 (F9 / F6 screenshot) are DEAD. Skip them.**
> - **`-ExecCmds` does not parse** (0 wide hits vs 5 same-class switch controls that all resolve).
>   Already pre-registered as FAIL in this card; now measured. Skip.
>
> **What the launch is actually for now** — the exec surface turned out to be *alive*
> (`UE_ALLOW_EXEC_COMMANDS == 1`, **138 native `FUNC_Exec` UFunctions**,
> `UKismetSystemLibrary::ExecuteConsoleCommand` thunk `0x395D790` `BlueprintCallable`). The
> valuable live questions are now §6 of the settled doc: are `ALokiPlayerCheats` /
> `ULokiClientPlayerCheats` instantiated, is `APlayerController::CheatManager` (`+0x520`) /
> `CheatClass` (`+0x528`) non-NULL, and does `ExecuteConsoleCommand` actually execute. All three
> are **pure RPM reads or one native call**, not keypresses.
>
> Retained below because the **method** is sound and reusable: the control discipline, the
> VOID-not-FAIL rule, the focus check, the screenshot prefix split, and `console_probe.py`'s
> `[CTRL]` gate. Harvest those; ignore the step list.

**Written S114 (2026-08-12), OFFLINE. Nothing in this file has been executed against a
running game.** Every number tagged **[M]** was measured this session against
`dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (`.rdata` **100 %** readable —
the right image for string questions), the on-disk shipped exe, `schema.txt`, or the
filesystem. **[I]** is inference on top of a measurement.

**The question.** `docs/dedicated-server-stub.md:541-556` concluded *"the dev console is
fully stripped"* and that conclusion is the founding justification for this project's
injection-only architecture. `docs/config-control-plane-s101.md` §0.1 already falsified the
**config** half of it. What is still unknown is whether the console and the **exec-command
surface** actually **function**. If they do, the project gains an external control path with
no DLL, no `.text` write, and none of the anti-tamper hazard that has dominated ten sessions.

**Budget: one ordinary `-NoHook` menu launch** — the safest run this project has
(`docs/s111-nohook-control.md`: 11 launches × 320 s, **zero deaths**). No shims, no tutorial
staging, no injection.

---

## 0. TL;DR — what you are doing

| | |
|---|---|
| Sitting 1 | ONE `-NoHook` menu launch. Ten ordered steps. **~35 min** wall clock. |
| Sitting 2 | Only if sitting 1 says you need it. In-world. **~25 min**, and it costs a tutorial-route launch (~27 % of which die during staging — FK-31). |
| Deliverables | `docs/fk13-run-<date>.txt` (probe output), the screenshot-watch log, `Loki.log`. |
| Hard rule | **A step whose positive control is silent is VOID — not PASS and not FAIL.** Write VOID in the results table and move on. This project has 25 recorded instances of a blind instrument being written up as a property of the game. |

---

## 1. Read this before you design anything around the run

Four things measured offline **this session** that change what is worth testing.

### 1.1 `-ExecCmds` almost certainly does not parse in this binary [M + I]

Scanned the tutorial-hero dump (`.rdata` 100 % readable) and the on-disk shipped exe,
UTF-16LE **and** ASCII, case-insensitive, whole file:

| token | wide | ascii | |
|---|---:|---:|---|
| `ExecCmds` | **0** | 1 | the single ASCII hit is `InOutExecCmds`, a MovieRenderPipeline reflected parameter name — **not** a switch literal |
| `LogCmds` | 3 | 0 | **CONTROL +** (FK-11: all three are help text) |
| `LOG=` | 5 | 0 | **CONTROL +** |
| `ABSLOG=` | 2 | 0 | **CONTROL +** |
| `FORCELOGFLUSH` | 2 | 0 | **CONTROL +** |
| `NOCONSOLE` | 1 | 0 | **CONTROL +** |

Five same-class `FParse` switch literals resolve; `ExecCmds` does not. ⇒ **[I, strong]
`-ExecCmds=` is a dead switch**, exactly like `-LogCmds`. This **independently re-explains
S3's probe #6** (`-ExecCmds="open 127.0.0.1:7777"` never reached `UEngine::Browse`) without
needing "the console is stripped" at all — and stock UE also wraps `OPEN`/`TRAVEL` in
`#if !UE_BUILD_SHIPPING`, so S3's result has **two** sufficient explanations, neither of
which is the one S3 recorded.

⚠ Coverage caveat, stated so it is not lost: `.text` on disk is 100 % encrypted and the
tutorial-hero `.text` is 53.2 % readable. A literal living in `.text` would be missed. The
controls are the same *class* of string (`.rdata` `FParse` literals) and they all resolve,
so the instrument demonstrably sees this class — but this is **[I]**, not **[M]**.
**Step 4 tests it live anyway, because it rides along for free.**

### 1.2 `HighResShot` is PROVEN to execute in this shipping build [M]

Not inferred — **259 PNGs on disk**. `tools/sigbypass-mod/tutorial_launch.cpp:5569` runs
`RunConsole(L"HighResShot 1")` via `UKismetSystemLibrary::ExecuteConsoleCommand`, and
`%LOCALAPPDATA%\SUPERVIVE\Saved\Screenshots\WindowsClient\` holds
`HighresScreenshot00000.png … HighresScreenshot00258.png` (259 files, newest
2026-08-09 01:57:06, **every single one** carrying that prefix).

**This is why the test card binds `HighResShot`, not something clever.** The command's
viability is already established, so a null result isolates the thing under test — *does a
DebugExecBinding fire* — and cannot be blamed on the verb being stripped.

Corroboration from the image: `UGameViewportClient::Exec`'s whole verb table is present as
consecutive wide strings at RVA `0x08088B98`–`0x08088EC8` [M]:

```
FORCEFULLSCREEN  SHOW  SHOWLAYER  VIEWMODE  NEXTVIEWMODE  PREVVIEWMODE  PRECACHE
FULLSCREEN  SETRES  HighResShot  HighResShotUI  SHOT  BUGSCREENSHOTWITHHUDINFO
BUGSCREENSHOT  KILLPARTICLES  FORCESKELLOD  DISPLAY  DISPLAYALL  DISPLAYALLLOCATION
DISPLAYALLROTATION  DISPLAYCLEAR  GETALLLOCATION  GETALLROTATION  TEXTUREDEFRAG
TOGGLEMIPFADE  PAUSERENDERCLOCK  PREPHYSBONES
```

`SHOT` sits at `0x08088CB0` and its `SHOWUI` option token at `0x08089228`/`0x08089238` — i.e.
the exact command the shipped F9 binding carries is compiled in. The two output base
filenames are also both present: **`HighresScreenshot` @ `0x08244C90`** and
**`ScreenShot` @ `0x08244CB8`**.

⇒ **`shot` writes `ScreenShot#####.png` — a prefix that has NEVER appeared in that
directory.** That is the cleanest file-system discriminator available and the card is built
around it.

### 1.3 "`ShowCheats` is absent from the binary" would be an INSTRUMENT ARTIFACT [M]

Same scan, same scope, with controls chosen to be names we *know* are live because they sit
in the user's own `UserSettings.ini` right now:

| token | wide | ascii | |
|---|---:|---:|---|
| `ShowCheats` | 0 | 0 | target |
| `DevCheatToggleHUD` | 0 | 0 | target |
| `ToggleHUD` | 0 | 0 | target |
| `CheatKillMe` | **0** | **0** | **CONTROL — known live, bound to `Subtract`** |
| `CheatNextHero` | **0** | **0** | **CONTROL — known live, bound to `Period`** |
| `OpenGlobalShop` | **0** | **0** | **CONTROL — known live, bound to `V`** |
| `CheatToggleInvulnerable` | **0** | **0** | **CONTROL — known live, bound to `NumPadZero`** |
| `LokiPlayerCheats` | 3 | 5 | CONTROL + (a *class* name, which IS in the image) |

**Action names as a class are invisible to a binary string scan** — they live in Blueprint
assets, ini files and the runtime FName pool, not in the exe's string tables. So the
absence of `ShowCheats` carries **zero** information, and nobody may write it down as
evidence. (`AuthCheatGrantGold` also scores 0/0 despite FK-1 establishing it as a real
compiled script UFUNCTION — same artifact, second demonstration.)

### 1.4 `viewmode wireframe` is a VOID test by construction — do not use it [M]

This build ships **both** refusal strings from `UGameViewportClient::HandleViewModeCommand`:

* `Debug viewmodes not allowed on consoles by default.  See AllowDebugViewmodes().` @ `0x08088EF0`
* **`Debug viewmodes not allowed in Test or Shipping builds.`** @ `0x08089190`
* `This view mode is currently not supported in game.` @ `0x08089120`

A null result from Ctrl+F1 therefore cannot discriminate *"the binding did not fire"* from
*"the command was refused because this is a Shipping build"*. It is listed below only as a
**tertiary, informative-only** observation.

### 1.5 What the reflection data already says [M]

* `schema.txt:12547` — **`Console : UClass:Object (4 props)`**. The `UConsole` UCLASS **is**
  compiled in and reflected (`ConsoleTargetPlayer`, `DefaultTexture_Black`,
  `DefaultTexture_White`, `HistoryBuffer`).
* `schema.txt:17350` — `GameViewportClient.ViewportConsole ObjectProperty (UClass:Console)`.
* `schema.txt:15217-15218` — `Engine.ConsoleClass` / `Engine.ConsoleClassName`.
* `schema.txt:41090` — `PlayerInput.DebugExecBindings` is a reflected UPROPERTY.
* The literal `/Script/Engine.Console` occurs **0×** wide and **0×** ASCII in the image, which
  is *expected* — that value arrives from `Engine/Config/BaseEngine.ini:101`, not from code.

**None of that decides `ALLOW_CONSOLE`.** The UPROPERTY declarations are not macro-guarded
upstream, so their names ship either way. **Only the runtime VALUE decides**, and that is
step 3.

---

## 2. Pre-flight — no launch, ~5 min

Run in an **ELEVATED PowerShell** at `G:\git\Supervive Revival Project`.

```powershell
# 2.1  Prove the probe at least parses and its decoders work (offline, touches nothing)
python tools\re\console_probe.py --dry-run
python tools\re\console_probe.py --self-test        # expect 6/6

# 2.2  See exactly what will be written to the user Input.ini. Nothing is written yet.
.\configs\set-debug-execbindings.ps1 -WhatIf

# 2.3  Baseline the screenshot directory. WRITE THESE NUMBERS DOWN.
$SS = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Screenshots\WindowsClient"
$T0 = Get-Date
"baseline count : " + (Get-ChildItem $SS -Filter *.png).Count
"baseline newest: " + (Get-ChildItem $SS -Filter *.png | Sort-Object LastWriteTime | Select-Object -Last 1).Name
"prefixes       :"; Get-ChildItem $SS -Filter *.png | ForEach-Object { $_.Name -replace '\d+\.png$','' } | Group-Object | ForEach-Object { "  $($_.Name) x$($_.Count)" }
```

**Expected baseline (measured 2026-08-12): `count = 259`, newest `HighresScreenshot00258.png`,
one prefix only: `HighresScreenshot x259`.** If you see any `ScreenShot*.png` already
present, STOP — the discriminator in steps 4/7/8 is contaminated and must be redesigned.

```powershell
# 2.4  Write our three rows into the USER-layer Input.ini, then set it read-only.
.\configs\set-debug-execbindings.ps1
```

That writes `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Input.ini`:

```ini
[/Script/Engine.PlayerInput]
+DebugExecBindings=(Key=F6,Command="HighResShot 1")
+DebugExecBindings=(Key=F7,Command="shot showui")
+DebugExecBindings=(Key=F8,Command="HighResShot 1",Control=True)
```

⚠ **This file has never existed before in this project.** `Input` IS in the engine's config
base-name table (`merged.dump` RVA `0x076bc130`, measured S101), so the layer *should* be
read — but "should" is exactly the word this project keeps getting burned by. **Step 3
decides it, by RPM, with no keypress and no visual judgment.**

⚠ Read-only is deliberate and copies `launch-redirect.ps1:283`: the engine rewrites these
files and drops sections it does not recognise.

---

## 3. SITTING 1 — one `-NoHook` menu launch

> Steps are ordered and the order is **load-bearing**: several observations share the
> screenshot directory as their output channel and are separated by *time*, not by
> destination. Run a screenshot watcher (step 3.0) so every file is attributed by
> timestamp, and write down the wall-clock time of every keypress.

### Step 0 — start the watcher (second window, ~1 min)

Open a **second** PowerShell (does not need elevation) and leave this running for the whole
sitting. It prints every new PNG with its arrival time, which is what makes steps 4/7/8
unambiguous.

```powershell
$SS = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Screenshots\WindowsClient"
$seen = @{}; Get-ChildItem $SS -Filter *.png | ForEach-Object { $seen[$_.Name] = 1 }
"watching $SS  ($($seen.Count) files at baseline)"
while ($true) {
  Get-ChildItem $SS -Filter *.png | Where-Object { -not $seen.ContainsKey($_.Name) } | ForEach-Object {
    $seen[$_.Name] = 1
    "{0:HH:mm:ss}  NEW  {1}  ({2:N0} bytes)" -f (Get-Date), $_.Name, $_.Length
  }
  Start-Sleep -Milliseconds 500
}
```

### Step 1 — launch (~3 min to menu)

**Steam must already be running** or login dies with `Auth Failure 14005`.

```powershell
# ELEVATED PowerShell, repo root.
.\configs\launch-redirect.ps1 -NoHook -ExtraArgs '-ExecCmds=shot'
```

`& $exe` returns in ~1 s (the shipping exe detaches), so this elevated window stays free for
the probe. Wait for the main menu.

* **Variable:** the user `Input.ini` (step 2.4) **and** the `-ExecCmds` rider.
* Those two are separable because their outputs differ in **time** (`-ExecCmds` fires at
  engine init, before any human key) and in **prefix** (`shot` → `ScreenShot*`; F6/Ctrl+F8 →
  `HighresScreenshot*`). If you dislike that, drop `-ExtraArgs` and spend a second launch —
  but see §1.1: the `-ExecCmds` arm is predicted null and is riding along for free.

### Step 2 — delivery control for `-ExecCmds` (~1 min)

```powershell
Select-String -Path "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log" -Pattern 'LogInit: Command Line:' | Select-Object -First 1
```

* **POSITIVE CONTROL:** the echoed line must contain `-ExecCmds=shot`.
* **Silent / missing line ⇒ step 4 is VOID** (you cannot tell "ignored" from "never arrived").
* This proves **DELIVERY ONLY**, never effect. That distinction is FK-11's core lesson.

### Step 3 — the RPM probe (NO KEYPRESS AT ALL) (~2 min)

In the **elevated** window:

```powershell
python tools\re\console_probe.py | Tee-Object docs\fk13-run-$(Get-Date -Format yyyyMMdd-HHmmss).txt
```

Read the `[CTRL]` block **first**.

| `[CTRL]` line | if it fails |
|---|---|
| `UClass 'PlayerController'` resolves | whole probe VOID |
| `UClass 'PlayerInput'` resolves | whole probe VOID |
| `PlayerController::PlayerInput` offset resolves | sections A/C degraded |
| GUObjectArray header plausible | probe exits 3, run VOID |

Then four independent readings:

**[A] `GEngine->GameViewport->ViewportConsole`** — the direct `ALLOW_CONSOLE` oracle.
* NON-NULL ⇒ **the console object exists.** FK-13 inverted. PASS.
* NULL ⇒ consistent with `ALLOW_CONSOLE=0`, **but not decisive alone** — cross-check [B].
* Property `NOT FOUND` ⇒ VOID (the usmap says it exists, so a miss is a walk failure).

**[B] `Console` UClass / instances / `Engine::ConsoleClass` / `ConsoleClassName`.**
* A live (non-CDO) `Console` instance ⇒ same verdict as a non-null [A].
* UClass present + `ConsoleClass` non-null + **zero** instances ⇒ the class is registered and
  the ini names it, but nothing ever constructed one ⇒ **[I] `ALLOW_CONSOLE` is 0.** That
  pairing is the decisive negative, not [A] on its own.
* UClass `NOT FOUND` ⇒ VOID (`schema.txt:12547` says it is compiled in, so the scan failed).

**[C] `DebugExecBindings` — the file-was-read discriminator. This is the step that matters most.**

| reading | meaning |
|---:|---|
| `Num = 19`, and the `EXTRA` line lists `HighResShot 1` / `shot showui` | ★ **the user-layer `Input.ini` WAS READ.** New capability for the project regardless of what the keys do. Proceed to steps 7/8. |
| `Num = 16`, matching the 16 shipped rows | the user `Input.ini` was **IGNORED**. Steps 7/8 (F6/F7/Ctrl+F8) become **VOID** — skip them, they can only produce an uninterpretable null. Step 6 (F9, a *shipped* row) is still valid. |
| `Num = 0` or rows undecodable | VOID. The probe prints the stride score table; if every stride scores 0 the FKeyBind layout assumption is wrong. |
| offset prints `+0x1A8` | ★ matches `docs/session-79-moonshot-plan.md:688` exactly ⇒ every offset assumption in the probe is confirmed in one line. |

**[D] `ConsoleKeys`** — expect exactly one entry, `Tilde`. Empty would be a real finding
(both `BaseInput.ini:16` and `DefaultInput.ini:368-369` set it) and would mean no key can
ever open a console regardless of `ALLOW_CONSOLE`.

### Step 4 — `-ExecCmds` observation — BEFORE you touch the keyboard (~1 min)

Look at the **watcher window** (step 0). Has a `ScreenShot*.png` appeared since launch?

* **Variable:** the `-ExecCmds=shot` switch, and nothing else — no key has been pressed.
* **POSITIVE CONTROL:** step 2 (switch echoed in `LogInit: Command Line:`) **and** §1.2
  (`shot`/`SHOT` is compiled in; `HighResShot` from the same table is proven to run here).
* **PASS:** a `ScreenShot#####.png` exists with an mtime after launch ⇒ `-ExecCmds` parses
  and dispatches ⇒ §1.1 is wrong and the project gains a zero-injection command channel.
* **FAIL:** no new file ⇒ combined with §1.1's controlled zero-occurrence measurement,
  `-ExecCmds` is dead. Record it as **FAIL (with control)**, which is a real result.
* **VOID:** step 2's echo did not contain the switch.
* **PRE-REGISTERED PREDICTION: FAIL.** Written down before the run, per project convention.

### Step 5 — input-focus control (~30 s) — **do this before any other keypress**

Click the game window. Press `Esc`, then `Esc` again (or `Tab`) and confirm the menu visibly
reacts.

* **This is the positive control for every keypress step below.** If the menu does not react,
  the window does not have keyboard focus and **steps 6-9 are all VOID**, not FAIL.
* Note the exact clock time. Write it down.

### Step 6 — press `~` (tilde) at the menu (~1 min)

* **Variable:** one keypress.
* **POSITIVE CONTROL:** step 5.
* **PASS:** a console overlay draws. FK-13 fully inverted; stop and write it up.
* **FAIL:** nothing draws. Then **re-run the probe** (`python tools\re\console_probe.py`) and
  compare section [A]: some builds construct the console lazily, so a `ViewportConsole` that
  was NULL in step 3 and is non-null now would be a completely different finding.
* **VOID:** step 5 failed, or the key is swallowed by an IME/overlay. If you suspect
  swallowing, that is what §4's `-ini:Input:...ConsoleKeys=F8` arm is for.

### Step 7 — press `F9` — the **shipped** debug-exec row (~1 min)

`F9 → "shot showui"` is one of the 16 rows `Engine/Config/BaseInput.ini` ships and that S79
measured live. **This step is valid even if step 3 [C] read `Num = 16`.**

* **Variable:** one keypress.
* **POSITIVE CONTROLS:** step 5 (focus) **and** §1.2 (`SHOT` + `SHOWUI` are compiled in, and
  the sibling verb `HighResShot` from the same Exec table demonstrably works in this build).
* **PASS:** the watcher prints a new **`ScreenShot#####.png`** — a prefix that has never
  existed in that directory. ⇒ **`UPlayerInput::DebugExecBindings` ARE EVALUATED in this
  shipping build.** That alone is a project-changing result: it means arbitrary exec commands
  are reachable from a key, with no injection.
  ⚠ If step 4 also produced a `ScreenShot*`, attribute by the watcher's timestamp against
  your recorded press time.
* **FAIL:** no new file within ~10 s ⇒ the bindings are not evaluated (or `SHOT` specifically
  is inert — step 8's `HighResShot` row separates those two).
* **VOID:** step 5 failed.

### Step 8 — press `F6`, then `F7`, then `Ctrl+F8` — **our** rows (~2 min)

**Only run this if step 3 [C] read `Num = 19`.** If it read 16, our rows do not exist in the
array and pressing the keys can only produce an uninterpretable null.

Press one key, wait 10 s, note the time, then the next.

| key | command | expected file |
|---|---|---|
| `F6` | `HighResShot 1` | `HighresScreenshot#####.png` |
| `F7` | `shot showui` | `ScreenShot#####.png` |
| `Ctrl+F8` | `HighResShot 1` (modifier path) | `HighresScreenshot#####.png` |

* **Variable:** one keypress each, run sequentially, never together.
* **POSITIVE CONTROLS:** step 5 (focus); step 3 [C] `Num = 19` (the rows exist);
  §1.2 (`HighResShot` **proven** to run in this exact build — 259 PNGs).
* **PASS (F6):** the strongest possible single result. The verb is known-good and the row is
  known-present, so a new file can only mean *the binding fired*.
* **FAIL (F6) but PASS (step 7 F9):** our rows are present but inert while shipped rows work —
  would point at load-order/CDO-copy semantics. Unexpected; write it up carefully.
* **PASS (F6) + FAIL (F7):** bindings evaluate but the `SHOT` verb specifically is inert.
* **PASS (F6) + FAIL (Ctrl+F8):** modifier handling is the blocker, not evaluation.
* **VOID:** step 5 failed, or step 3 [C] read 16.

### Step 9 — the user-bound cheat keys, informative only (~2 min)

`RightAlt` (`ShowCheats`), `Ctrl+\` (`ToggleDebugMenu`), `Ctrl+F12` (`DevCheatToggleHUD`),
`Ctrl+H` (`ToggleHUD`). These are **ActionMappings** in the live `UserSettings.ini`, a
completely different path from DebugExecBindings — they need whatever gameplay input
component binds them.

* **AT THE MENU THERE IS NO POSITIVE CONTROL FOR THESE.** So a null here is **VOID by
  default** and must be recorded as VOID. Press them anyway (it costs 20 s) — a *positive* is
  informative, a negative is not.
* ⚠ Do **not** reach for §1.3's zero-occurrence scan as supporting evidence. It is an
  instrument artifact and proves nothing.
* The real test for these is **sitting 2**.

### Step 10 — Ctrl+F1 `viewmode wireframe`, tertiary (~30 s)

Press it, note what happens. **A null is VOID, not FAIL** — see §1.4, this build ships the
"Debug viewmodes not allowed in Test or Shipping builds." refusal at `0x08089190`.
A *visible* wireframe would be a bonus positive.

### Step 11 — shut down and collect (~3 min)

```powershell
# stop the watcher (Ctrl+C in window 2), then:
Copy-Item "$env:LOCALAPPDATA\SUPERVIVE\Saved\Logs\Loki.log" "docs\fk13-run-$(Get-Date -Format yyyyMMdd).log"
Get-ChildItem $SS -Filter *.png | Where-Object LastWriteTime -gt $T0 | Select-Object Name,Length,LastWriteTime

# revert the config change (do this even on a PASS - leave the machine clean)
.\configs\set-debug-execbindings.ps1 -Revert
```

---

## 4. SITTING 2 — only if sitting 1 leaves something open. **This is a SEPARATE launch.**

Do **not** assume sitting 1 covers these. Each needs an in-world run or a different launch
configuration, and the tutorial route costs real risk (**FK-31: ~27 % of launches die during
staging** before anything is armed).

| # | Question | Why it cannot ride on sitting 1 | Route |
|---|---|---|---|
| S2-1 | Do `ShowCheats` / `ToggleDebugMenu` / `Ctrl+F12` / `Ctrl+H` do anything? | ActionMappings need a gameplay input stack; at the menu there is no positive control at all | Tutorial world per CLAUDE.md's hands-free recipe (`forceTutorialMatch = true` → `launch-redirect.ps1 -NoHook` → `configs\fk24-stage.ps1`). Positive control: press a key you KNOW works in-world first (`W`, or `P` = `CheatRefreshSelf`) and confirm the hero reacts. |
| S2-2 | Does `-ini:Input:[/Script/Engine.PlayerInput]:+DebugExecBindings=...` work? | It is a **different mechanism** from the file layer and must not share a launch with it — FK-11 measured the two diverging for `[Core.Log]` | Own launch: `-ExtraArgs '-ini:Input:[/Script/Engine.PlayerInput]:+DebugExecBindings=(Key=F6,Command="HighResShot 1")'`, with `set-debug-execbindings.ps1 -Revert` first so the file layer is absent. Discriminator: probe [C] `Num = 17`. |
| S2-3 | Does `-ini:Input:[/Script/Engine.InputSettings]:ConsoleKeys=F8` re-key the console? | Only worth spending if step 6 failed *and* [A]/[B] say a console object exists | Own launch. Control: probe [D] must show `ConsoleKeys = F8`. |
| S2-4 | Do the `DISPLAY` / `DISPLAYALL` / `GETALL` exec verbs work? | They need a world with actors to be meaningful | In-world, driven from a DebugExecBinding — **only if step 7 or 8 PASSED**. High value: a read-only introspection surface with no shim. |

---

## 5. Decision table — what each outcome means for FK-13

| Step 3 [A]/[B] | Step 7 (F9, shipped row) | Step 8 (F6, our row) | Verdict |
|---|---|---|---|
| console object EXISTS | — | — | ★★★ **FK-13 inverted.** `ALLOW_CONSOLE` is on. Everything else is key delivery. Go straight to `~` / `ConsoleKeys` work. |
| console NULL + 0 instances + ConsoleClass null | PASS | PASS | ★★★ **The best realistic outcome.** No console UI, but **arbitrary exec commands from a key with zero injection**, and the user config layer can define them. The injection-only premise is broken. |
| console NULL + 0 instances | PASS | VOID (`Num=16`) | ★★ Bindings evaluate, but only the **shipped 16**. Still a real (small) control surface: `shot`, `PROFILEGPU`, `DumpGPU`, `ToggleDebugCamera`, `Next/PreviousDebugTarget`. Next question is how to change the shipped set (IoStore overlay, or S2-2's `-ini:` arm). |
| console NULL + 0 instances | FAIL | FAIL (`Num=19`) | ★ **Sharp, publishable negative**: the config path populates the array (Num moved 16→19, measured) but `UPlayerInput` does **not evaluate** it in shipping. FK-13's *config* half stays falsified; its *functional* half is confirmed. Injection-only stands, now for a measured reason instead of a bad string scan. |
| any | VOID (step 5 failed) | VOID | **Run is VOID.** Re-run sitting 1. Do not record anything. |
| console NULL, but probe `[CTRL]` failed | — | — | **VOID.** Fix the probe first; the RVAs may be stale. |

Independently of all of the above, **step 4 settles `-ExecCmds`** and §1.1 predicts FAIL. A
FAIL there is worth recording because it retires `launch-redirect.ps1`'s `-Open` parameter,
whose entire mechanism is `-ExecCmds`.

---

## 6. Recording rules (state these before the run, not after)

1. **VOID ≠ FAIL.** Any step whose control was silent is VOID. Write VOID.
2. **Absence in a binary scan is never evidence unless a same-class control resolved.** §1.3
   is this session's worked example.
3. **Delivery ≠ effect.** `LogInit: Command Line:` proves a switch arrived; it never proves it
   did anything.
4. **One variable per observation.** Where steps share the screenshot directory, they are
   separated by *time* and by *prefix*, and the watcher log is the evidence. If you lose the
   watcher, you lose the attribution — re-run rather than guess.
5. `Num = 16 → 19` is the file-read discriminator; the screenshots are the
   binding-evaluated discriminator. **They are different questions.** Do not merge them.

---

## 7. Honest wall-clock estimate

| | |
|---|---|
| Pre-flight (§2) | 5 min |
| Launch → menu | 3 min |
| Step 0 watcher + step 2 log check | 2 min |
| Step 3 probe (≈190k-object index + reflection walks, once) | 2-4 min |
| Steps 4-10 keypresses + observation | 8 min |
| Step 11 collect + revert | 3 min |
| Writing down results as you go | 6 min |
| **Sitting 1 total** | **~30-35 min**, one launch |
| Sitting 2 (if needed) | **~25 min per arm**, one launch each, tutorial arms carry FK-31's ~27 % staging-death risk |

---

## 8. Artifacts this card depends on

| Path | What it is | Tested? |
|---|---|---|
| `tools/re/console_probe.py` | pure-RPM probe, sections [CTRL]/[A]/[B]/[C]/[D] | `--self-test` 6/6 offline. **NEVER run against a live process.** First likely failure: not elevated → `OpenProcess` fails, exits 2 with a message. |
| `configs/set-debug-execbindings.ps1` | writes the user `Input.ini`, `-Preset Probe|Minimal|Control`, `-Revert`, `-WhatIf` | parses clean; `-WhatIf` output verified. **Never executed for real.** |
| `docs/fk13-live-test-card.md` | this file | — |

Prior art the card assumes you have read: `docs/config-control-plane-s101.md` §0.1/§4-6,
`docs/ignorance-map-s101.md` (FK-13 entry, ~line 794), `docs/dedicated-server-stub.md:500-580`,
`docs/fk6-cheat-surface-settled.md`, `docs/fk11-log-verbosity-settled.md`.
