# SUPERVIVE Revival — Method rules

**Two standing method rules that are not about any one subsystem.** They govern how a negative
result is allowed to be written down, and what to read before reaching for a debugger. Between them
they have overturned more walls in this project than any single investigation.

> **Provenance.** Migrated out of the Claude memory store into the repo on **2026-08-12**, verbatim
> apart from link rewriting. They lived outside version control for ~90 sessions, which meant the
> claims in them could not be `git blame`d, diffed or reverted — a bad property for a project whose
> entire value is its trial-and-error history and its retraction discipline.
>
> ⚠ The migration itself found a live instance of rule 9: the memory index carried
> *"31 confirmed instances"* while the memory file it indexed said **36**. Same claim, two places,
> silently diverged. The count below is taken from the table, which is the ground truth.

---

## Rule 1 — The instrument-artifact pattern

★★★ **This is the project's dominant error mode.** Read it before recording ANY negative result as
a property of the game.

**Before recording any negative result as a property of the game, ask: "is this a fact about
SUPERVIVE, or a fact about my instrument?"** Every instance below was settled in minutes once the
right question was asked — and every one had steered sessions, sometimes dozens, before that.

**36 confirmed instances**: 35 tabulated below (S115-a/b is two), plus one caught in prose before it
was ever written down (see the S114 note).

**★ S108 (2026-08-04) added three, ALL of them mine, and two were committed INSIDE the document
written to catalogue this very error mode.** The pattern is not something earlier sessions were bad
at — it is what this problem does to whoever is holding it. See
[s108-fk24-instrument-corrected.md](s108-fk24-instrument-corrected.md).

**★ S114 (2026-08-12) added six — and three of the six were caught by a control that was ALREADY IN
PLACE** (the probe's `[CTRL]` gate, the shim's Func-swap watchdog, a literal-presence check
pre-registered before the run). That is the first sitting in this record where the guardrails rather
than hindsight did the catching. A **seventh was caught before it was ever written down**: the claim
*"the cheat action names are absent from the binary"* died when four action names known to be live
right then from `UserSettings.ini` (`CheatKillMe`, `CheatNextHero`, `OpenGlobalShop`,
`CheatToggleInvulnerable`) **also scored 0/0** — the instrument cannot see action names at all.
See [fk13-console-exec-settled.md](fk13-console-exec-settled.md).

| # | Instrument | Artifact | What got recorded | Truth |
|---|---|---|---|---|
| S108-a | the probe's own positive control | `selfPhase` advances only *after* the store retires | "the watchpoint is **VOID** on the game thread" → escalate DR→page | the store never RAN; the DR fired fine (127/128 threads armed). The escalation was unfounded |
| S108-b | `vtHits` sampled at the +8 s selftest line | that line precedes `[PL] init complete` by ~40 marker lines | "VtGuard never re-runs after init" (3/3 runs) | **no post-init sample existed at all**; the same run's own dump proves the store executed later |
| S108-c | `Get-ChildItem Saved\Crashes` (and `harvest.py`) | enumerates `UECC-*` dirs only | "the force-open dies **silently, with no dump**" | Sentry crashpad writes a full minidump (43.9 MB caught live) into the **game** dir |
| **S109-a** | **a wall-clock `ls` schedule** — the artifact was a **NUMBER**, not an absence | two `ls` calls 3 min apart, with a **relaunch at 02:19:58 inside the gap** | "crashpad **uploads and deletes within ~3 minutes**" → build a filesystem watcher to win the race | there is **no retention window**; one report sat untouched **65+ min**. The 3 minutes was the *observation interval*. The fix needed no watcher at all |
| **S109-b** | the **bundled** `Loki.log` (both the UECC copy and the crashpad attachment) | it is a byte-exact **truncated PREFIX**, cut before the terminal block | "`handing control over to crashpad` is absent → the tell is wrong, change it" | present at line 52508 of the **session** log; 0/81 in crash-dir copies is **guaranteed by construction**. A false negative *manufactured by the container* |
| **S109-c** | `find … \| tail -25` (mine, caught in ~2 min) | my own output truncation | "only 24 of 87 dirs have a dump" | 81 do. **A display limit read as a corpus fact** |
| **S109-d** | `harvest.py`'s `base=0x0` column | I assumed it meant a failed dump parse | "`base=0x0` is a **parse failure**; fix the parser" | `harvest.py:27-34` **never opens a dump** — it reads `<PCallStack>`. `base=0x0` means **no SUPERVIVE frame in the callstack**, which is the *defining property* of the `runtime.dll+1` crash family. I inferred an instrument failure **without reading the instrument** |
| FK-2 | RPM property walk of `UPlayerInput` | reflection sees only UPROPERTYs | "the legacy input path doesn't exist" | the arrays carry **no UPROPERTY macro at all** in UE 5.4 — invisible to reflection, present in every build |
| FK-3 | dump coverage metric | counts non-zero BYTES | "`.rdata` is 63% readable, structural" | 99.64% readable; the "gap" is vtable null slots + string padding |
| FK-4 | string scan | ASCII-only | "the packer encrypts module strings" | ~87,851 UTF-16 strings were invisible; strings are plaintext in the dump |
| — | `_AS` suffix grep | matches only script classes shadowing a native parent | "the Angelscript layer is thin, 18 classes — accept the ceiling" | **110** classes, 78 modules; ~8× undercount that shaped ~26 sessions |
| — | my own xref query (S101) | queried a string at +88 into a longer one | "the emitting code has never run" | **4 references**, all in one live function — the code did run |
| **S111-a** | **the field itself** (`SecondsSinceStart`), N=1 crash seen twice | a genuinely *deterministic* crash reproduces at the same elapsed time | "Sentry captures at a fixed point — **always 30**" → the whole crash corpus closed for **60+ sessions** | 5 of 92. ★ The belief had a **real generator**: 3 of the 5 thirties are literally the same `FAsyncLoadingThread` crash. A reproducible signature promoted to a property of the field. This is **FK-8** |
| **S111-b** | **the CLOCK.** `SecondsSinceStart` is the *launch* clock | it contains the **operator's staging schedule**, which moved **+33.0 s** July→August | "trimodal, separated by LITERAL death-free bands" | one headline gap goes **p=0.0010 → p=0.1675** once re-anchored to `Load map complete`. The mode boundaries were partly *us* |
| **S111-c** | the route label (`log_route`) | it is a **monotone function of survival time** — a run must survive to be labelled "tutorial" | "the menu never dies late; tutorial deaths are later" | the median ladder (26<98<165<259 s) tracks how far each label *requires* a run to have gotten. Definitional, not empirical |
| **S111-d** | `MINIDUMP_THREAD.ThreadContext` for the crashed tid | that is the **dump writer's** state, not the fault's | "every crash is at one identical address" (RIP `0x7ffd3b1edc94`, **22/22**) | read the **ExceptionStream's own** `ThreadContext` (stream 6 + 160). A perfect-looking 22/22 that was pure artifact |
| **S111-e** | substring-matching `runtime` in module lists | matches `VCRUNTIME140.dll` | flipped a real `0/22` into `runtime.dll present in 22/22` | compare **exact basenames**. One substring inverted a negative |
| **S111-f** | `Saved\Logs` (a fixed-depth **rotating ring**) | it discards while you measure | a stored "~60 % of sessions retain a log" ratio | three reads gave 6/10, 7/10, 8/11 **within hours**. The ratio is *perishable* — snapshot, then report; never store it |
| **★ S113-a** | `strxref.py`, whose target is **hardcoded** (`:63 DEFAULT_DUMP = dumps\merged.dump.exe` = the **game exe**) | it structurally **cannot see `runtime.dll`**, a separate module — which appears **0 times** in either citing doc | *"The ~3–5 min `.text` integrity check — **CLEAN NEGATIVE, and it is not coverage-blocked.** No string names it"* (`fk3-fk4-settled.md:513`, `strxref-open-questions.md:321`) → **nobody looked at the protector for ~12 sessions** | the scan excluded the **only plausible home for the check**. ⚠ Note the self-inoculating phrase *"and it is not coverage-blocked"* — it was coverage-blocked in the strongest possible way, **by target selection**. Wall #7's real successor lead was found in `runtime.dll` within one offline pass ([fk10-protector-identified.md](fk10-protector-identified.md)) |
| **S113-b** | an entropy scan over **1 MiB windows** | small plaintext islands don't move a 1 MiB average | "`packer0` is encrypted, so MinHook/mbedtls strings are absent" | at **4 KB** granularity it is 1,942/1,990 encrypted **with plaintext islands** — the verbatim XXH3 `kSecret` and a byte-exact `hde64_table` were recovered from it. ★ *Track A caught this itself and refused to report the negative* — the correct move |
| **★ S113-d** | **HELP TEXT, mistaken for a feature** — a *positive* artifact, the inverse of every other row here | `-LogCmds` appears 3× in the image, **all three inside `HelpString()`**; the standalone `LogCmds=` parse literal does **not** exist (controls: `LOG=`, `ABSLOG=`, `logcategoryfiles=`, `NOCONSOLE` all present) | FK-11's prescribed "cheapest experiment" was `-LogCmds=…`. It would have emitted **nothing**, and the nothing would have been recorded as *"confirmed: Verbose is compiled out"* | the flag is unparsed; `[Core.Log]` via ini is the working path. ⚠ **A documented-looking string is not a working feature.** Grep found the docs, not the code. This nearly recreated the very false-known it was meant to kill |
| **S113-e** | an ASCII string scan for log categories | this image's category literals are **all** UTF-16LE | (FK-11's *"~1,004 categories"* lineage, and the S45-era "absent from the exe" claims) | ASCII finds **103** `Log*` tokens **of which NOT ONE is a category** — shader functions and BP node names. **Zero, not a subset.** A sharper form of FK-4: the wrong encoding does not undercount here, it returns an entirely different population |
| **S113-f** | *"(confirmed)"* written in a handoff note | the cited session contains **one** occurrence of the topic — the rule itself, restated | FK-11, for ~60 sessions | **there was never a test.** Provenance is checkable in seconds and almost never checked. ⚠ Pair with S113-a: a claim's *confidence marker* is not evidence, and neither is the phrase "not coverage-blocked" |
| **S113-c** | a size measurement that silently covered **only 4 of 11 sections** | `packer30+40+31+42` = 48,133,632 B at H 5.36–6.57 | FK-10's *"`runtime.dll` is ~48 MB at entropy 5.3–6.6, **not encrypted**"* | the file is **67,511,496 B** and 19.3 MB of it **is** encrypted. Right about the code, wrong about the file — a **subtotal reported as a total** |
| **S114-a** | `cheat_reach_probe.py` (`endswith "PlayerController"`), cross-checked against `obj_by_class.py` (substring `PlayerController`) | the live menu PC's class is **`PC_MainMenu_C`** — it neither ends with nor contains that string | *"there is **no live PlayerController at the menu**"* → the whole Route B chain looks unreachable | `PC_MainMenu_C @0x26C8A80C040`. ★ **Two instruments sharing one blind spot is not corroboration** — I used the substring tool as the "proven" cross-check for the `endswith` tool, and they fail *identically*. Only a class-**derivation** walk finds it. Committed and caught inside the same sitting; the fix is structural (`FindCheatablePC` accepts any class that *reflects* `CheatManager`+`CheatClass`, not one matching a name pattern) |
| **S114-b** | the same probe's subclass-derivation walk | it never reached Blueprint subclasses | *"`LokiGameInstance` **LIVE=0**"* — on a running game, which cannot happen | 1 live (`BP_LokiGameInstance_C`, found by `obj_by_class.py`). ★ **The probe's own `[CTRL]` gate printed `*** A CONTROL FAILED. Record this run as VOID. ***`** and saved the reading. This is rule 2 working as designed |
| **S114-c** | reading a UPROPERTY off the **CDO** | CDO fields are unset for config-populated globals | *"`LokiGlobals.DebugGlobals = NULL` ⇒ never configured"* | sibling controls `ItemGlobals` (`+0x30`) and `AbilitySystemGlobals` (`+0x40`) on that **same CDO** are also NULL on a game that demonstrably works. **CDO-NULL ≠ "absent"** — uninformative; do not cite it |
| **S114-d** | `configs/fk24-stage.ps1`'s parked gate — a **WINDOW**, not a scan | it tail-read the last **200 KB** of `capture.log`, but `/core-game/matches` is fetched **once, early** | the gate "can never pass" → the stager burned its full 420 s `WaitParkedSec` **and the launch** | attempt 1 passed **by luck** (fetch 70 KB from the end); attempt 2's identical fetch sat **1.1 MB out of window**. ★ FK-11's own verbosity win **inflated the log and broke this gate** — an instrument silently degraded by an unrelated improvement, taxing every tutorial sitting |
| **S114-e** | **`God` chosen as the verification verb** | `UCheatManager::God` emits **no log line at all** | a null would have read as *"branch 7 is dead / the install failed"* | switched to **`LogLoc`**, whose body reaches `UE_LOG(LogCheatManager, …)`, with both format literals confirmed present **before** the run (pre-registered, not post-hoc). ⚠ **A verifier with no output cannot fail visibly** — the FK-11 silent-instrument shape again |
| **S114-f** | **the shim's own "ok"** — a borrowed helper (`RunConsole`) reading globals populated by a *different* run mode | null PC ⇒ `ExecuteConsoleCommand` fell to `GEngine->Exec(nullptr, …)` and never touched a PlayerController | `[SHOT] chm-verify: console 'LogLoc' ok`, reported as a pass, while `BugItGo` stayed at **0** | ⇒ ★★ **"the call returned ok" is NEVER a success criterion; only the verb's OWN output is.** Second lesson: **check the provenance of every global a borrowed helper touches** before reusing it in a new mode |
| **★★ S115-a/b** | `.pdata` read from the PE **exception data directory**, then from the **section** | dir #3 is `rva=0,size=0` AND the `.pdata` section is **6,283,264 B, 100 % ZERO** in **both** dumps — never paged in | *"NO RUNTIME_FUNCTION covers this RVA"* for **every** function incl. known-real controls ⇒ every function is a leaf, no extents, no size grading | `.pdata` is simply **absent from the capture**; extents must come from `tools/strxref/index/pdata_union.csv` (382,282 entries, union of 68 dumps). ⚠ Any tool reading extents from the image itself is silently broken. Two of my own passes died on this before the third worked |
| **★★★ S115-c** | a stride-16 scan for `FNameNativePtrPair {const char* Name; FNativeFuncPtr Ptr;}` | `FClassFunctionLinkInfo` is `{UFunction*(*Create)(); const char* Name;}` — the **opposite field order**, so the scan **phase-shifts** onto it, pairing `Name[i]` with `Create[i+1]` | *"`ALokiGameMode::SpawnPlayer`'s registered thunk is `0x5340D90`"* — **a plausible wrong address with a plausible wrong body** (47 B, no impl call), i.e. exactly the failure mode the task was set to hunt | `0x5340D90` is `Z_Construct_UFunction_*` (lazy singleton → `ConstructUFunction @0x135F5E0`). ★ **Caught by the positive control, not by inspection**: the known-good `LocalTravel`/`ExecuteConsoleCommand` came back with the *same* spurious shape. **A systematic artifact across controls is an instrument fault, not a finding.** Discriminate by calling convention: `[rdx+0x20]`+`FFrame::Step` = exec thunk |
| **★★★ S115-d** | **`CLAUDE.md` itself — a DIGEST is an instrument** | compressing a table whose header was `\| function \| exec thunk \| body \|` dropped the "exec thunk" label and replaced it with an **equals sign** | `` `SpawnPlayer` `0x534C070` = `xor eax,eax; ret` `` — asserting bytes are AT an address they are not at. Read as a hard measurement conflict for a full session (FK-13 §6.1) | **both** underlying measurements were correct; the thunk is real code and the impl (`0x0F7EB50`) holds those exact bytes. **The false statement was manufactured in the summarisation, not the source doc.** ⇒ never print a byte string next to an address it did not come from; a thunk/body table needs the body's OWN address column. See [fk1-stub-claim-recheck.md](fk1-stub-claim-recheck.md) |
| **★★★ S115-e** | **the CORRECTION — committed by me, inside the very fix for S115-d** | I edited `CLAUDE.md` from a read taken **earlier in the session**, before `3b29842` landed a **second** four-stub block 15 lines below the first | commit `5c32a79` shipped a `CLAUDE.md` **corrected at line 291 and still saying "UNDER CHALLENGE — FLAGGED, NOT RESOLVED … do not build on either reading" at line 311.** A file arguing with itself is worse than the original error — the next reader has textual grounds for *either* belief | one `grep`, which **the user had to ask for**, found it in seconds; fixed in `5d9632c`. ⚠⚠ **This is the third time in two sessions that the doc-hygiene error recurred inside the document written to catalogue it** (cf. the S108 header note). The pattern does this to whoever is holding it. ⇒ **rule 9** |

**Why:** every one of these is a *true* observation about the instrument paired with a *false*
generalisation to the target. They are seductive because the measurement really was performed and
really did return nothing. The failure is never in the measuring — it is in the sentence written
afterward.

### How to apply

1. **Write the instrument's blind spot next to every negative result.** "No hits" means nothing without
   "scanned ASCII only, module range only, len≥6".
2. **Run a positive control.** Before trusting "X is absent," confirm the same probe FINDS something you
   know is there. `tools/re/input_watch.py` still hardcodes `+0x418/+0x430` with no positive control
   anywhere in the record — if those offsets are wrong, every "input doesn't reach the pawn" reading
   in the project is void.
3. **Question a suspiciously round or small census before believing it** — that was the shared root
   cause of the `_AS`, `.rdata` and ASCII cases.
4. **Prefer two instruments that fail differently.** FK-3 fell instantly to page-zero counting vs
   byte counting; FK-4 to UTF-16 vs ASCII.
5. **A true statement about one artifact is not a statement about a technique.** FK-4's original
   observers were RIGHT that the on-disk exe is packed (only 634 of 9,085 `.rdata` pages match the
   dump). The error was concluding that string-xref itself was defeated. Name the artifact you
   measured, every time.
6. **★ S109: an *interval* is an instrument too.** "Deleted within ~3 minutes" was never measured —
   only "present at T, absent at T+3min" was. **Never state a rate, timescale or window from two
   samples without asking what happened between them.** Something did (a relaunch).
7. **★ S109: before blaming a tool, READ the tool.** S109-d cost a wrong recommendation ("fix the
   parser") that would have destroyed a real signal. `harvest.py` is 60 lines. Reading it took
   90 seconds and inverted the conclusion.
8. **★ S109: check whether a container truncated your evidence before concluding about its
   contents.** Bundled/attached copies of logs in this project are prefixes, not the whole file.
   Diff against the authoritative source (`Saved\Logs\Loki.log`) before trusting any *absence* in
   them. The `flushing session and queue before crashpad handler` line survives the crashpad
   attachment's cut where `handing control over to crashpad` does not — useful when only the
   attachment exists, useless for the UECC copies (0/81, cut earlier still).
9. **★★ S115: GREP FOR THE CLAIM BEFORE CORRECTING ONE INSTANCE OF IT — a retraction is an
   instrument, and a partial one leaves the file arguing with itself.** Load-bearing claims in this
   project are stated **more than once** and in more than one file. Fixing the instance you happened
   to read produces a document that is corrected in one paragraph and still wrong 15 lines later,
   which is *worse* than the original: the next reader now has textual grounds for either belief.
   **Before editing:** `grep -rn` the addresses / the claim / its distinctive phrasing across
   `CLAUDE.md`, `docs/`, the ignorance map **and the tools** — a live tool can hardcode a retracted
   claim as a constant (`exec_chain_grade.py:50` carried `0x05254180: 'ret'`, i.e. **the tool used to
   check the claim had ingested the claim**). **After editing:** re-run the same grep and read every
   surviving hit, rather than assuming your edit was the only site. ⚠ **Re-read the file immediately
   before editing, not from an earlier turn** — other sessions commit to `CLAUDE.md` concurrently; the
   S115 miss was exactly this (edited from a read taken before `3b29842` landed, committed a
   self-contradicting `CLAUDE.md`, caught only by a grep the user asked for afterwards).

Also of a piece: **findings that die in commit messages get re-litigated.** `46d873a` and `b420a69`
had the input mechanism right on 2026-07-16 and were never promoted to a doc, so four later sessions
re-derived it. **Promote findings out of commit bodies into `docs/`.**

Related: [strxref-open-questions.md](strxref-open-questions.md),
[fk2-input-settled.md](fk2-input-settled.md), [fk1-angelscript-settled.md](fk1-angelscript-settled.md).

---

## Rule 2 — Read the shipped artifacts first

★★ **Before reverse-engineering anything, check whether the game already ships the answer in
plaintext.** Four multi-session walls fell to this alone.

**Before starting RE work on any SUPERVIVE subsystem, first ask: "has the game already written this
down?"** The ignorance audit (2026-07-26, [ignorance-map-s101.md](ignorance-map-s101.md)) found that
four separate multi-session walls fell not to more effort but to a **method change** — reading a
shipped artifact, changing a census key, or fixing a string encoding.

**Why:** the project's default reflex is live RPM + disassembly. That reflex is excellent and it is
why the hard problems got solved — but it means cheap plaintext sources went unread for ~100 sessions
while the same facts were re-derived expensively. Concrete cases, all verified:

- **Input.** S80-series spent multiple sessions concluding "SUPERVIVE has a CUSTOM Loki input system"
  and "what drives input is UNKNOWN." The answer is in
  `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\UserSettings.ini` — plaintext, rewritten every
  launch, section `[/Script/Loki.PlayerConfigManager]`, **186 `ActionMappings` + 16 `AxisMappings`**
  with names AND bound keys (incl. `CheatSpawnAlliedDummy`, `CheatSpawnEnemyDummy`,
  `CheatMenusPlayRespawnAnim`→NumPadOne, `AirshipBoost`→SpaceBar). `schema.txt:41004` declares the
  class. Zero repo hits before the audit.
- **Angelscript census.** Grepping the `_AS` class suffix found 9; it only matches script classes
  extending a native parent. Census by source-module path finds **78**. 4.3× undercount, and it froze
  a "the script layer is thin, deploy/round/respawn is native C++" conclusion into a commit subject.
- **String scanning.** "The packer defeats string-xref" was an ASCII-vs-UTF-16 encoding bug — the
  strings read back as plaintext from our own merged dump at the same RVAs.
- **Dump coverage.** The `.rdata` "63% structural cap" was a non-zero-byte metric artifact (only 33
  of 9,085 pages are genuinely zero).

**How to apply:** at the start of a subsystem, spend ten minutes on the free sources before touching
a debugger — `%LOCALAPPDATA%\SUPERVIVE\Saved\` (Config, **Crashes: 86 minidumps exist**, Logs),
`<GameRoot>/Loki/Config/*.ini`, `<GameRoot>/Loki/Script/*.Cache`, `Manifest_*_Win64.txt` (the debug
manifest declares `SUPERVIVE-Win64-Shipping.pdb`), `buildID` (`tlFJuYwW9-`), the 178 packed
`.uplugin`, and our own already-extracted `schema.txt`. When a census returns a suspiciously round or
small number, **question the key you grepped for before believing the number** — that is the shared
root cause of three of the four cases above.

**Corollary the audit also established:** both audits were read-only text analyses, and the static
corpus is itself ~48% missing (the packer demand-decrypts `.text` on execution). So **every "X does
not exist in the binary" conclusion is a statement about the half of the code this install has
run** — never treat it as absolute. Entering a new runtime state decrypts new code; state coverage
IS binary coverage.

Related: [coverage-audit-s101.md](coverage-audit-s101.md), and the never-bank directive in
`CLAUDE.md` ("Working style").
