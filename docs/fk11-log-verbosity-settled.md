# FK-11 — SETTLED: Verbose/VeryVerbose are NOT compiled out. The instrument was available all along.

**S113, 2026-08-09. Offline, read-only. Zero game launches consumed.**

FK-11 (`docs/ignorance-map-s101.md:669`) recorded the belief, from
`docs/next-session-prompt-s45.md:185-186`:

> *"Don't send `-LogCmds` expecting Verbose logs — this is a SHIPPING build; Verbose/VeryVerbose
> UE_LOG is compiled out **(confirmed)**. Use hooks/RPM, not log verbosity."*

**Verdict: FALSE.** Not "true for some categories", and **not even true for Loki code
specifically**. The cheapest instrument this project could own has been available for ~60
sessions.

⚠ **But the ignorance map's own prescribed experiment would have SILENTLY FAILED**, and would
very likely have re-entrenched the false-known. See §3 — this is the most operationally
important section of this document.

---

## 0. TL;DR

| question | answer |
|---|---|
| Is Verbose compiled out? | **No.** Global `COMPILED_IN_MINIMUM_VERBOSITY` = **`VeryVerbose` (7)**, measured three ways |
| `USE_LOGGING_IN_SHIPPING`? | **1**, measured |
| Are *Loki* categories capped? | **No. 109/109 Loki-dominant categories are `VeryVerbose`. Zero capped at `Log`** |
| How many Verbose call sites survived compilation? | **1,339 Verbose + 513 VeryVerbose**, out of 14,030 decoded `UE_LOG` sites |
| Does `-LogCmds` work? | **NO — the parse literal is absent from the binary.** FK-11's own recommended experiment |
| What DOES work? | **`[Core.Log]` via ini** — triple-confirmed present, and provably *already binding* |
| How much is silent? | **84.2 %** (760 of 903 curated categories) |
| Biggest trap | conflating **"never ran"** with **"suppressed"** — §5 |

---

## 1. The belief is false — three independent measurements

**M1 — the constructed category objects.** `dumps/merged.dump.exe` is a live snapshot, so the
static initialisers have run and each `FLogCategoryBase` holds real values. **1,018 of 1,062**
constructed objects hold `CompileTimeVerbosity = 7 (VeryVerbose)`. Because the stored byte is
already `min(COMPILED_IN_MINIMUM_VERBOSITY, per-category)`, **a single observation of 7 proves
the global minimum is 7** — it is the enum maximum.

**M2 — the call sites themselves.** **14,030 compiled-in `UE_LOG` call sites** decoded from
their `FStaticBasicLogRecord`: **1,339 at Verbose (9.54 %)** and **513 at VeryVerbose (3.66 %)**.
A global cap at `Log` would have deleted all 1,852 of them at compile time. They are present.

**M3 — runtime.** The live `Loki.log` emits genuine `Verbose` lines (§2).

**`USE_LOGGING_IN_SHIPPING = 1`, measured**: the entire `FLogSuppressionImplementation` surface
is plaintext in `.rdata` — `-LogCmds` help at `0x076B25E0`, `Log [cat] [level]` at `0x076B2470`,
the verbosity-level list at `0x076B1EE0`, `global=[default verbosity…]` at `0x076B2920`, and
`Log suppression category %s is defined multiple times with different compile time verbosity.`
at `0x076B1CC0`.

### The histogram (665 cross-validated objects)
| CompileTimeVerbosity | count |
|---|--:|
| **VeryVerbose (7)** | **651** |
| Warning (3) | 7 |
| Display (4) | 3 |
| Log (5) | 2 |
| Error (2) | 1 |
| Verbose (6) | 1 |

**≥ Verbose = 98.0 %.** Only **11** categories in the entire binary are capped below
VeryVerbose, and each is an individual Epic/plugin `DECLARE_LOG_CATEGORY_EXTERN` third argument
— `LogNiagara`=Verbose, `LogActor`=Warning — **both matching Epic's published declarations,
which is a control the method could have failed and did not.**

### ★ The Loki question, answered directly
Partitioned by the **full source path** recorded in each call site (so it needs no FName
resolution): **109/109 LOKI-dominant category objects are `CompileTimeVerbosity = VeryVerbose`.
Zero capped at `Log`.** There are **71 compiled-in Verbose/VeryVerbose call sites inside
`\Loki\Source\`**, spread across **35** Loki categories. A real example, sitting in the binary
right now, on the exact frontier the project is stuck on:

```
[%s] Spell %s ResolvingTargets - ULokiGameplaySpell::EvaluateServerSideTargeting.
        LokiGameplaySpell.cpp:2305   (Verbose)
```

### The 16 categories the project cares about
14 of 16 resolved, **every one `CompileTimeVerbosity = VeryVerbose`**:

| category | object | Default / CompileTime |
|---|---|---|
| `LogNet` | `0x09F8A490` | Warning / **VV** |
| `LogNetSubObject` | `0x09F8A2F8` | Log / **VV** |
| `LogNetPartialBunch` | `0x09F8A290` | Warning / **VV** |
| `LogAbilitySystem` | `0x09FED9F8` | Display / **VV** |
| `LogGameplayEffects` | `0x09FED9C0` | Display / **VV** |
| `LogLokiGameplaySpell` | `0x0A033D60` | **VV** |
| `LogLokiGameplaySpellReplication` | `0x0A033E30` | **VV** |
| `LogLokiAbilitySystemComponent` | `0x0A033ED0` | **VV** |
| `LogLokiDropPhase` | `0x0A035E20` | **VV** |
| `LogLokiSpawner` | `0x0A036C00` | **VV** |
| `LogLokiInventory` | `0x0A036AB0` | **VV** |
| `LogLokiGameMode` | `0x0A036AC0` | **VV** |
| `LogDamage` | `0x09FA5A78` | **VV** |
| `LogSentrySdk` | `0x09FEE530` | **VV** ← positive control |
| `LogNetSerialization` | — | **unresolved** (no decrypted ctor site, never logged) |
| `LogLokiXPManager` | — | **unresolved** (same) |

**Positive control passed exactly:** `LogSentrySdk` reads CompileTime = **VeryVerbose (7)** and
runtime `Verbosity` = **Verbose (6)**, while 541/665 others read `Log` and 32 read `Display` —
i.e. the method discriminates. Independent cross-check: log-matching vs static-init
disassembly agreed **32/34** on shared objects.

---

## 2. The runtime existence proof, with an internal control

MEASURED in the live `Loki.log`, **same session, same category, both forms**:
```
[…:053][ 0]LogSentrySdk: Sentry plugin version: 0.19.1     <- bare  = Log verbosity
[…:137][ 0]LogSentrySdk: Verbose: starting transport       <- label = Verbose verbosity
[…:615][ 0]LogSentrySdk: Verbose: request handled in 154ms
```
UE prints the verbosity name only for verbosities above `Log`; `Log` lines print bare. Because
the *same category in the same session* produces both forms, `Verbose:` cannot be message text.

Verbosity-label census of that log: **Error 100,618 · Display 575 · Warning 366 · Verbose 13 ·
VeryVerbose 0.** Across the **entire 4.10 GB / 28,684,890-line corpus** (842 logs), exactly one
category ever reached Verbose and **zero** ever reached VeryVerbose.

⚠ `VeryVerbose = 0` is **not** evidence it is compiled out — §1 M2 proves 513 VeryVerbose call
sites exist. No category is ever *set* to VeryVerbose at runtime, so nothing emits it. That
distinction — compile-time availability vs runtime suppression — **is the whole of FK-11.**

**Why `LogSentrySdk` specifically:** nothing "raised" it. `Loki/Config/DefaultEngine.ini:906`
ships `[/Script/Sentry.SentrySettings] Debug=True`, which enables sentry-native's debug logger;
the plugin maps its DEBUG level onto `UE_LOG(LogSentrySdk, Verbose, …)`. The string
`Log category %s verbosity has been raised to %s.` never appears in any log.

---

## 3. ⚠⚠ THE TRAP: FK-11's own prescribed experiment would have silently failed

The ignorance map's "cheapest experiment" was:
> *Add `-LogCmds="LogLokiGameplaySpell Verbose, LogLokiAbilitySystemComponent Verbose,
> LogGameplayEffects Verbose, LogNetSubObject VeryVerbose"` to one launch and diff the category
> set.*

**That line is wrong in three independent ways, and every one of them produces the same
symptom — an empty result — which would have been written down as "confirmed: Verbose is
compiled out."** That is exactly how this false-known was born the first time.

**(a) `-LogCmds` does not parse in this binary. [MEASURED, adjudicated]**
The byte sequence `logcmds` occurs **exactly 3 times** in the whole 178 MB image, and all three
are help text — dumped verbatim here so nobody has to re-litigate it:
```
0x076B25E0  -LogCmds="[arguments],[arguments]..."           - applies a list of console commands at boot time
0x076B26B0  -LogCmds="foo verbose, bar off"         - turns on the foo category and turns off the bar category
0x076B2860  set UE-CmdLineArgs="-LogCmds=foo verbose breakon, bar off"
```
There is **no standalone `LogCmds=` literal** for `FParse::Value` to match.
*Controls, because this is a negative:* peer switch literals of exactly this shape **do** exist
— `NOCONSOLE` `0x0769B3A0`, `LOG=` `0x0769B3D8`, `ABSLOG=` `0x0769B3E8`,
`logcategoryfiles=` `0x0769B420`, `FORCELOGFLUSH`, the `LOGTIMES` family. The on-disk exe
agrees exactly (3 hits, all help text). `.rdata` is **99.64 %** complete in the dump. Both
encodings scanned.
**The trap within the trap:** the help text is what a casual scan finds, and it reads like
proof the flag works.

**(b) The categories chosen are the worst available.** Per §5's classification, that line is
**three Class-B categories plus one Class-C** — i.e. code paths that do not execute on any
route the project can currently reach. Even with a working delivery mechanism they would emit
nothing.

**(c) `LogNetSerialization` at VeryVerbose is catastrophically spammy** (per-bit logging). It
should be struck from any candidate list.

---

## 4. What actually works — and it is already proven in this project

**The `[Core.Log]` ini path is triple-confirmed:**
1. **Present:** `Core.Log` at `0x076B1D80`, read at `.text 0x0107F937`, followed by the
   `ProcessCmdString(Name + " " + Value)` loop.
2. **Precedence, stated by the binary itself** at `0x076B1FA0`: *compiled-in → ini → command
   line*. Stage three is missing here (§3a), so **ini is the last word.**
3. ★ **Already binding, measured.** Across the 4.10 GB corpus, all 15 shipped `[Core.Log]`
   entries show **zero violations**. `LogAccelByte` and `LogOnline`, both pinned to `Warning`,
   emit **3** and **2** lines in a 14.8 MB session while unpinned peers run 244–422.
   **The project has spent ~60 sessions reading a log that was deliberately turned down.**

⚠ `LogNet = 0` lines is **not** part of that evidence and must not be cited as such — the
sampled sessions are the menu route with no net driver, so `LogNet` would be silent at any
verbosity. `LogAccelByte` carries the argument, because its subsystem demonstrably ran.

**The user-ini precedent, already working in this repo.**
`%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Engine.ini` — 148 bytes, **ReadOnly**:
```ini
[GameNetDriver StatelessConnectHandlerComponent]
CachedClientID=278            ; engine-written

[HTTP.Curl]
bVerifyPeer=false             ; ← THIS PROJECT'S OWN FIX
[SSL]
bValidateRootCertificates=false
```
Those bottom two are this project's fix for the documented *"`-ini:` is applied too late"*
problem at `configs/launch-redirect.ps1:279`. **Same file, same mechanism, already proven on
this client.** The ReadOnly attribute is the deliberate UE trick that stops the engine
rewriting the file.

### Two free instruments already in every log
- **`LogInit: Command Line:` echoes the entire command line verbatim.** Any switch we add is
  verifiable as *delivered* in one line — cleanly separating "the flag was ignored" from "the
  flag never arrived".
- **`LogConfig:` narrates config application** (`Applying CVar settings from Section […] File
  [Engine]`).

---

## 5. ★ The silence map — and the never-ran vs suppressed trap

**Compiled-in (denominator):** **936** UTF-16LE NUL-terminated `.rdata` category literals
(1,006 by substring; **903** curated after removing 33 ini/cvar keys).
⚠ **ASCII-only finds 103 tokens of which NOT ONE is a category** — an ASCII scan returns *zero*
categories, not a subset. Blind-spot ratio 9.1–9.8×.

**Ever emitted (numerator):** **842** UE-format logs, **4.10 GB**, **28,684,890 lines** (590
crashpad archives, 98 UECC, 135 docs, 16 live). 184 distinct categories emitted, but **41 come
from our own DS stub / editor-flavoured builds**, so the shipping-client numerator is **143**.

**Silence: 793/936 raw (84.7 %), 760/903 curated (84.2 %).**
FK-11's *"~825–870 of ~1,004"* is **proportion confirmed, absolute count corrected down** — its
~1,004 was the wide *substring* count. Two of its named-silent categories are wrong:
`LogLokiSpawner` emitted once, and `LogAbilitySystem` emits in 644 logs.

### ⚠ The trap that matters more than the number
**384 of 842 logs reach `LVL_Tutorial`, but not one contains combat, drop phase, bots, damage,
XP, or client replication.** For much of the map, silence carries **no information about
suppression at all**. Three classes:

- **Class A — owner provably ran, still silent ⇒ real suppression candidates:**
  `LogLokiHeroCharacter`, `LogLokiCharacter`, `LogLokiCharacterMovement`,
  `LogLokiPlayerController`, `LogGameFeatureToggles`, `LogLokiMenuActions`.
- **Class B — module loaded, path not exercised:** the GAS family.
- **Class C — never ran:** all netcode, drop phase, inventory/damage.

**Raising verbosity on Class C changes nothing.** Only Class A is a pure suppression win.

---

## 6. Ranked targets

**#0 — fly this first: `LogBlueprintLogLibrary`.** Loki's own `UBlueprintLogLibrary` exposes
**`Verbose` / `VeryVerbose` static UFunctions**, callable through the project's existing
game-thread native-call primitive, and the category **already emits** (598 logs). It proves the
whole mechanism end-to-end with **zero gameplay dependency** — no tutorial, no combat, no
netcode. The project has never had a control like this.

Then: 1 `LogLokiAbilitySystemComponent` · 2 `LogAbilitySystemComponent` *(engine — the one most
likely to actually **name** why `AvatarActor` is null)* · 3 `LogServerCoreGameManager` *(cheapest
FK-5 probe)* · 4 `LogLokiHeroCharacter` · 5 `LogLokiCharacter` · 6 `LogLokiGameplaySpell` ·
7 `LogGameFeatureToggles` · 8 `LogLokiMenuActions` · 9 `LogLokiAssetManager`/`Loader` ·
10 `LogLokiCharacterMovement` · 11 `LogLokiPlayerController` · 12 `LogGameplayEffects` ·
13 `LogLokiDropPhase`/`Spawner` · 14 `LogPlayerCheats`/`CheatManager`/`Exec` ·
15 `LogNetSubObject` *(Class C — produces nothing on the tutorial route)*.

**Spam hazards — do not raise blind:** `LogNetSerialization` *(in FK-11's own line — **strike
it**)*, `LogNetTraffic`, `LogRepTraffic`, `LogRepProperties`, `LogRepCompares`.
⚠ **Special case: `LogGameFeatureToggles` is HIGH risk despite being silent** — the same
subsystem already emits ~10⁵ lines/run through `LogTemp`, so its getter is called ~100k times.
**Raise it to `Log` first, never straight to `Verbose`.**

### Two free wins, unrelated to any experiment
- **`LogTemp` is 97.5 % of the log** (100,616 of 103,169 lines) — all of it the feature-toggle
  spam, emitted at **`Error`** under `LogTemp`, *not* under `LogGameFeatureToggles` (which is
  silent). **`LogTemp=Fatal` reclaims the entire log budget.** Note `LogTemp=Warning` will
  **not** work — the spam is at `Error`.
- **`DFLLog=Fatal`** in the shipped ini deliberately mutes a real shipped DebugFunctionLibrary
  (33 methods, 65 settings). Un-muting is one line and zero risk.

---

## 7. The Angelscript channel — hypothesis inverted

There **is** a rich script-side logging API: **20 `Log::` functions, every one with an
arbitrary-`FName`-category overload**, plus 5 `Print*`. But **the shipped scripts call it 6
times in 4,963 syscalls across 78 modules (0.12 %).**

⇒ **The Angelscript layer is silent by AUTHORSHIP, not by gating. Raising verbosity cannot make
it talk.** This specifically downgrades the drop-phase route (FK-22), which is script-implemented.
The script API also has no `Verbose` — it tops out at `Log`.

What *is* worth taking from the script layer: `UBlueprintLogLibrary` (#0 above), and
`LogBlueprintUserMessages`, already live at `Log`.

---

## 7b. ★★★ LIVE CONFIRMATION — the experiment was FLOWN, 2026-08-09

**One launch, `-NoHook`, menu route, `forceTutorialMatch = false`** (identical route to the
baseline log, so the comparison is like-for-like). Result log preserved at
`docs/fk11-live-result-20260809.log`.

### Mechanism scoreboard

| # | mechanism | category | baseline | after | Verbose | verdict |
|---|---|---|--:|--:|--:|---|
| **A** | user `Engine.ini` `[Core.Log]` | `LogAccelByte` | 3 | **52** | **46** | ✅ **WORKS** |
| **B** | `-ini:Engine:[Core.Log]:…` | `LogOnline` | 2 | 2 | **0** | ❌ **FAILED** |
| **C** | `-LogCmds="… Verbose"` | `LogAccelByteLobby` | 0 | 0 | 0 | ⚠ **inconclusive** |

**Both switches were verifiably DELIVERED** — the engine's own echo shows
`… -log -ini:Engine:[Core.Log]:LogOnline=Verbose -LogCmds="LogAccelByteLobby Verbose"`. So B and
C are failures of *effect*, not of delivery. That separation is exactly what the free
command-line-echo instrument buys.

**Mechanism B is a clean, controlled negative:** `LogOnline` did emit — two lines,
`LogOnline: Warning: STEAM: Failed to obtain steam user stats…` — so the subsystem ran and
simply stayed pinned at its shipped `Warning`. ⇒ **`-ini:` is applied too late to affect
`[Core.Log]`**, exactly as `configs/launch-redirect.ps1:279` warned for curl. **Use the user ini.**

⚠ **Mechanism C is NOT refuted by this run, and the flaw is in the experiment's design, not the
binary.** `LogAccelByteLobby` was chosen because it was silent — which means there is **no
positive control that it can emit at all**. Its zero is equally consistent with "the flag was
ignored" and "this category never logs on this route." §3a's static evidence (no parse literal,
with peer-literal controls) remains the stronger argument; this run neither confirms nor
refutes it. **A future run should drive mechanism C with a category proven to emit** — e.g.
`LogAccelByte` itself, in a run where the user ini does *not* also raise it.

### Whole-log effect

| label | baseline | after |
|---|--:|--:|
| **Verbose** | **13** | **1,018** |
| Error | 100,618 | **2** |
| Display | 575 | 431 |
| Warning | 366 | 87 |
| log size | 14.1 MB | **1.4 MB** |

**The log is now 10× SMALLER and carries 78× MORE Verbose.** `LogTemp=Fatal` removed all
100,616 feature-toggle spam lines (100,616 → **0**), confirming both that the free win works and
that `Fatal` (not `Warning`) was the required level.

### ★ What the new instrument immediately revealed

**`LogAbilitySystem`: 25 → 4,161 lines, 959 of them Verbose** — the GAS frontier, lit up on a
plain menu launch:
- **137×** `Initializing new default set for LokiAttributeSet[N]` — the attribute-set initialiser
  runs for **137 sets** at menu.
- A **per-hero data defect**, one line per hero, previously invisible:
  `FAttributeSetInitterDiscreteLevels::PreloadAttributeSetData Unable to match Attribute from
  SneakSpeedMultiplier (row: <Hero>.LokiAttributeSet.SneakSpeedMultiplier)` — for Zilla, Wukong,
  Wrestler, WhackAMole, WaveBoss, WaterGun, Wanderer, Void, TravelForm, Titan, Tau, TargetDummy,
  SupportMage, Succubus, StormAssassin, Storm, Stomper, Stalker, … i.e. **every hero**. One curve-table
  row has no matching attribute property.

**`LogAccelByte`** now traces the entire backend conversation — SDK entry points, HTTP verb, full
URL, status and request handle:
```
LogAccelByte: Verbose: AccelByte::Api::User::LoginWithOtherPlatformIdV4
LogAccelByte: Verbose: HTTP REQ POST …/iam/v4/oauth/platforms/steam/token?createHeadless=false, 000001BE05B429B0
LogAccelByte: Verbose: HTTP 200  POST …/iam/v4/oauth/platforms/steam/token?createHeadless=false, 000001BE05B429B0
LogAccelByte: Verbose: [AccelByte] Key for Cached Token can not be empty.
LogAccelByte: Verbose: AccelByte::AccelByteWebSocket::OnMessageReceived
```
Two items worth following up independently of FK-11:
- **`[AccelByte] Key for Cached Token can not be empty.`** — a real client-side diagnostic that
  has been firing invisibly on every login.
- **`AccelByteWebSocket::OnMessageReceived`** fires repeatedly ⇒ **frames ARE arriving on the
  client socket.** That bears directly on **FK-15** (*"server→client WebSocket push is measured
  non-functional"*), which was based on 5 probes of one message type. This does not refute
  FK-15, but it hands it a working instrument it never had.

### ⚠ The never-ran caveat, observed exactly as predicted
Every Class A / GAS category in the preset stayed at 0: `LogLokiHeroCharacter`,
`LogLokiCharacter`, `LogLokiCharacterMovement`, `LogLokiPlayerController`, `LogLokiMenuActions`,
`LogGameFeatureToggles`, `LogLokiAbilitySystemComponent`, `LogAbilitySystemComponent`,
`LogLokiGameplaySpell`, `LogGameplayEffects`, `DFLLog`.

**This is NOT evidence they are suppressed.** The run was `-NoHook` at the menu with **no human
input**, so no hero exists, no menu action is taken, and no spell is cast. `LogLokiMenuActions`
in particular was classified Class A on the assumption that menu navigation occurs — in a
hands-free run it does not. **Re-test the Class A set on a run where the relevant code actually
executes** (a tutorial-route launch, or a run with menu interaction).

---

## 8. The experiment — three mechanisms, three categories, one launch

The candidate mechanisms are independent, so they can be tested simultaneously **provided each
drives a different category**. All three are near-silent today and all three are exercised
during login/lobby, so any one lighting up is unmissable.

| # | mechanism | category | baseline | applied as |
|---|---|---|--:|---|
| **A** | user `Engine.ini` `[Core.Log]` (+ReadOnly) | `LogAccelByte` | 3 | append section to the user ini |
| **B** | `-ini:` command-line override | `LogOnline` | 2 | `-ini:Engine:[Core.Log]:LogOnline=Verbose` |
| **C** | `-LogCmds` | `LogAccelByteLobby` | 0 | `-LogCmds="LogAccelByteLobby Verbose"` |

Mechanism **A** is the favourite on evidence (§4). **C is predicted to be a no-op** by §3a —
including it costs nothing since it rides the same launch, and it converts a static negative
into a live measurement. If `LogAccelByteLobby` lights up, §3a is wrong and we learn it
immediately.

**Verification is free:** `LogInit: Command Line:` proves B and C were *delivered*; reading the
ini back proves A was applied.

> ### ⚠ The recording rule, stated in advance so it cannot be fudged afterwards
> If a mechanism produces nothing, that is a fact about **that mechanism**, **NOT** about
> whether Verbose is compiled in. Verbose is compiled in — 1,339 Verbose and 513 VeryVerbose
> call sites, measured (§1 M2). Writing *"`-LogCmds` did nothing ⇒ Verbose is compiled out"* is
> precisely the false-known this document closes, and precisely how it was created.

---

## 9. Corrections this pass makes to the project record

| claim | where | correction |
|---|---|---|
| "Verbose/VeryVerbose UE_LOG is compiled out (confirmed)" | `next-session-prompt-s45.md:185`, propagated to ~19 docs | **FALSE.** Global minimum = VeryVerbose; 1,852 Verbose/VeryVerbose call sites compiled in; 109/109 Loki categories at VeryVerbose |
| "(confirmed)" | same | **Attached to nothing.** `session-45-…txt` contains exactly one occurrence of `LogCmds`/`Verbose` — line 121, restating the rule. No test, no log excerpt |
| "Add `-LogCmds=…` to one launch" | FK-11 "cheapest experiment" | **Would have silently failed** — no parse literal (§3a), and 3 of its 4 categories are Class B/C (§3b). `LogNetSerialization` also catastrophically spammy (§3c) |
| "~825–870 of ~1,004 categories silent" | FK-11 "Steers" | Proportion right, count corrected: **760/903 (84.2 %)**. `LogLokiSpawner` and `LogAbilitySystem` were wrongly listed as silent |
| `0x1138F20` = `FLogCategoryBase` ctor | intra-session working note | **Wrong** — that is `FName::FName(const WIDECHAR*, EFindName)`. The ctor is **`base+0x1063710`**. They are called back-to-back once per category, which is how the mislabel survives; `r8d` at `0x1138F20` is `EFindName::FNAME_Add`, so reading verbosities there yields garbage |
| — | new | **`FLogCategoryBase` layout in this build: `Verbosity@0, DebugBreakOnLog@1, DefaultVerbosity@2, CompileTimeVerbosity@3, FName@4`.** The FName is **last**, not first; scanning FName-first under-reports 4× |
| — | new | This build passes verbosities as **`mov r8b/r9b, imm8`**, not `imm32`. A 32-bit-form scan returns **0 hits** |

### Instrument caveats to carry forward
- **47.7 % of `.text` in `merged.dump.exe` is all-zero** (demand-decrypt gap). Only 269 of
  ~1,062 static initialisers are visible, and **every `.text`-based negative is worthless** —
  all 16 target categories report `refs=0` in strxref, including `LogNet`, which certainly has
  a constructor. Route 1 (constructed objects in live writable data) has no such limitation.
  *Caught by a control that returned an impossible 0.*
- A strict regex consuming the delimiter between adjacent pooled literals undercounted the
  category census 936 → 803. *Caught in-session.*
