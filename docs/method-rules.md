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

**48 known instances**: 45 tabulated below (S115-a/b is two; S123 added three), plus one caught in
prose before it was ever written down (see the S114 note), plus two cited only in `CLAUDE.md` (the
"44th" and "45th") that were never tabulated here. ⚠ **See the divergence note under the table —
the tally has itself been a rule-9 instance twice now. Re-derive from the table; do not retype.**

**★★★ S118 (2026-08-13) added six, and THREE of them are mine — including one committed while
writing a rule about how to avoid the very error.** The S118 set is worth reading as a group because
it is dominated by a family this register had under-represented: **arithmetic and indexing done by
the analyst rather than by a tool** (a hand-added carry, a digit-stripped RVA, a stride that could
only see half a structure, a window with two cancelling boundary errors, and a published list ending
in `…`). Every one produced a *coherent, plausible* wrong answer rather than an obvious failure.
See [fk15-bound-delegate-map-20260813.md](fk15-bound-delegate-map-20260813.md).

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
| **★★ S118-a** | **HAND ARITHMETIC.** Adding `base + RVA` in my head, one dropped carry | read `0x7FF7D1EE**D**2D0` instead of `0x7FF7D1EE**E**2D0` — **one page low** | *"`qword[0x9FFE2D0]` points at UObjects, not the `{FString,uint8}` map"* — written up as a real anomaly, reported to the user, **and handed to a subagent as a task** | the page below happened to hold plausible UObjects (vtable, flags `0x41`, consecutive InternalIndex `0x2130..`), so the wrong read produced a *coherent* wrong story. The correct address is an ordinary TMap, `Num=33`. ⇒ **"recompute an RVA, never retype it" is NOT enough — recompute with a MACHINE.** I obeyed the rule and still failed, because the rule named the wrong instrument |
| **S118-b** | **RVA by digit-stripping** — dropping leading chars off a printed VA instead of subtracting the base | `call 0x7ff7c8e904f0` → recorded as RVA `0x8E904F0`; the real RVA is `0xFA04F0` | two "Find/hash function" RVAs, and a **captured disassembly of them** that is actually `.rdata` string-pool garbage | same root cause as S118-a. The captured file reads as a real (if odd) disassembly, so nothing announces the error |
| **★★ S118-c** | **allocation-pool ADJACENCY used as a TYPE discriminator** | `Lobby+0x1a00`'s allocation sits beside the known `+0x88`/`+0x98` FString buffers | *"`+0x1a00` is a string, not a delegate — exclude it"* → a bound delegate dropped from the table | it is a **raw-method delegate bound to Lobby itself** (`+0x18` = the Lobby address; vtable RVA `0x7696AC8`). Adjacency says nothing about type — **the vtable does.** ⚠ Committed **in the same breath as a rule about how to bound the table correctly**; rule 13's shape again |
| **★★★ S118-d** | **a 16-BYTE STRIDE over a structure with two interleaved lattices** | several members sit at offsets **≡ 8 (mod 16)** — the same alignment that puts `LbS`/`LbE` at `+0xA8`/`+0xB8` | *"16 bound, 46 unbound"* (S117) and my own first pass — the scan **structurally could not see** `+0x228` | 23 bound at 8-byte stride, and `+0x228` is **`disconnectNotif`**, a real notif delegate ⇒ **the miss changed a conclusion (6 reachable types vs 7), not just a tally.** Two independent sessions ran the same stride and neither noticed |
| **★★ S118-e** | **an ellipsis in a published list** | `docs/fk15-delegate-binding-20260813.md` printed **12 of 16** bound offsets and ended in a literal `…` | the next session joined against that list and got **2** hits | the four hidden offsets (`+0x1640/+0x1650/+0x1660/+0x1670`) are **four of the seven answers**. ⇒ **Never join against a list that ends in an ellipsis** — and never publish one; a truncation is indistinguishable from a complete set to every later reader |
| **★★★ S118-f** | **a scan WINDOW with two off-by-one boundaries — in OPPOSITE directions, which CANCELLED** | `.rdata 0x8601A20..0x8602730` **excluded** `signalingP2PNotif` (0x128 below the lower bound) and **included** `messageSessionNotif` (exactly ON the upper bound, i.e. the first string after the block) | a 33-name list that matched the known 33-case count **exactly**, so the count "corroborated" it. Shipped in `vocabulary.go`, and *"`signalingP2PNotif` is NOT one of the 33 dispatch cases"* was asserted by a **unit test** | enum 32 = `signalingP2PNotif`, enum 33 = `errorNotif`, `messageSessionNotif` absent — read live from the dispatch TMap. ⚠⚠ **Two errors summing to the right total is the hardest artifact to see: the independent count you validate against will PASS.** ⚠⚠⚠ And the file's own comment **warned about this exact failure mode** ("two mistakes produce 32 — a plausible-looking count that is wrong in both directions at once") before committing a different pair of it, while the test that would have caught it **had ingested the claim** (rule 9) |
| **★★★ S118-g** | **A PENDING QUESTION, read as a result.** Not a blind instrument — *no* instrument. The observation was never made | a two-legged claim (`→ ONLINE`, `→ OFFLINE`) where only leg 1 was confirmed; I asked the operator to confirm leg 2, was given a different task before any answer arrived, and wrote up both | *"Server-driven presence, **on command, in both directions**"* / *"`OFFLINE → ONLINE → OFFLINE`"* — **shipped in a doc, in `CLAUDE.md`, and in the commit message** (`30e44b2`) | leg 2 is **false**: `availability: offline` parses cleanly and the panel **does not change** (×2). The tell was in my own transcript — an unanswered question. ⇒ **When a claim has N legs, count the confirmations before writing "both"/"round trip". An unanswered request for confirmation is a NULL, not a pass.** ⚠ Note the seduction: leg 1 was a genuine, well-controlled success, and its momentum carried the unobserved half along with it |
| **★★★ S115-e** | **the CORRECTION — committed by me, inside the very fix for S115-d** | I edited `CLAUDE.md` from a read taken **earlier in the session**, before `3b29842` landed a **second** four-stub block 15 lines below the first | commit `5c32a79` shipped a `CLAUDE.md` **corrected at line 291 and still saying "UNDER CHALLENGE — FLAGGED, NOT RESOLVED … do not build on either reading" at line 311.** A file arguing with itself is worse than the original error — the next reader has textual grounds for *either* belief | one `grep`, which **the user had to ask for**, found it in seconds; fixed in `5d9632c`. ⚠⚠ **This is the third time in two sessions that the doc-hygiene error recurred inside the document written to catalogue it** (cf. the S108 header note). The pattern does this to whoever is holding it. ⇒ **rule 9** |

| **★★★ S123-a** | **`TSparseArray.ArrayNum` read as `Num()`** — and the wrong read is **SELF-VALIDATING** | the root-set registry's `ArrayNum` is **49,307**; `Num()` is `ArrayNum - NumFreeIndices` = **32**. `NumFreeIndices` (49,275) was in the *same hex dump I was reading* | *"the registry holds 39,263 disregard-pool objects"*, *"~4,306 members lack bit 30"*, *"the flag-is-a-mirror model is too simple"* — **all three sent to a subagent as a formal challenge to its CORRECT result** | two properties make the error pass every sanity check: the inline `FF×16` bitmap is **dead storage** once `NumBits > 128` (`0x011D4533 cmove r10, rax`), so it reads "all allocated"; and a **freed** slot satisfies every field-range test *by construction* — stale `Value`s are real former indices and the free-list link shares bytes with `HashNextId`. So "88% are live indices" and "every `HashIndex` < `HashSize`" both **passed on garbage**. ⇒ **walk the allocation bitmap; never trust the slot array.** Will recur on any `TSet` in this image |
| **★★★ S123-b** | **recording a DERIVED BOOLEAN instead of the RAW VALUE** — the instrument threw the evidence away | `rootset_census.py` stored *"does this object carry the bit `dominant_reach_bit()` currently returns"* rather than the flag word. That comparator is a **lagging majority vote (~15 s)** whose polarity **INVERTS** during a mark ramp | *"32/32 rooted vs 40/40 ordinary always carried the current value"* — and the derived metric measured **"was marked LAST"**, not "was re-marked" | at a 0.5 s sample period the same objects read **0/32** — *meeting my own pre-registered refutation criterion* — and at 0.4 s, **32/32**. The prediction failed in **both** directions. The conclusion survived only because a reviewer re-derived it from raw low nibbles (9 rotations, 32/32, 1,417 samples). ⇒ **record raw, derive afterwards** — a stored boolean cannot be re-analysed when its comparator turns out to be wrong |
| **★★ S123-c** | **a probability computed against a model the data refutes** | *"zero free slots in `[0,39295)`; P ≈ 1e-676 if the 7,282 free slots were uniform"* | offered as the primary evidence for the disregard-pool boundary, in a doc and in a report to the user | the free slots are **not** uniform — 5,705 of 7,282 form **one contiguous run starting at the boundary**. Worse, `[45000..169999]` (125,000 slots, 3.2× the prefix) **also** has zero holes and is not rooted, so the signature is not specific; and "no holes below the first hole" is **circular by definition**. The conclusion was right for entirely different reasons (`ObjFirstGCIndex` read directly). ⇒ **before quoting a p-value, state the null model out loud and check the data does not already refute it** |
| **★★ S123-d** | **a live widget instance read as a rendered one** — the ARCHETYPE trap | RPM found exactly **one** live (non-CDO) `WBP_UI_MatchHistoryEntry_C` carrying `Visibility = 4` (= rendered). It was the **widget-tree TEMPLATE**, and 4 was its *design-time* value | on the verge of being recorded as *"Career→History renders our synthetic row"* — with a screenshot not yet taken | the screen had **never been opened**: `MatchHistoryScreen` and `ProfileScreen` have **0** activations in the entire session log. The name was the tell too — the template is named `<Class>_C` while real instances drop the suffix. ⇒ **prove a screen was ever BUILT before reading any widget's state off it.** Fifth member of the class-lookup blind-spot family (`obj_by_class.py` substring · `cheat_reach_probe.py` endswith · `class_props.py` class-of-class · `bpframe_readout.py` first-match) — and the first whose defect is *staleness* rather than *selection* |
| **★★★ S123-e** | **the grep WINDOW is part of the instrument** — a NEW variant of the documented User-Agent trap | `grep -B2 -A3 match-history capture.log` paired a request with a **neighbouring request's** `User-Agent` header, because the window was narrower than one record | *"the game never refetched — the fetch was `supervive-loadout-shim`"*, i.e. the flight had failed | `-A 12` gave the true pairing: **`Loki/UE5-CL-0`**, the game, 19 s after the ags restart. ⇒ the standing rule says *filter capture.log by User-Agent* — it does **not** say *pair each request with its OWN header block*, and a narrow window violates that **while looking like compliance**. ★ Defusal worth copying: give verification requests a deliberately absurd UA (`fk21-verify-NOT-THE-GAME`) so our own traffic can never be mistaken for the client's |
| **★ S123-f** | **the VERIFYING command is an instrument too** | `grep -o '\\|'` reported **0** escaped pipes in a markdown row that has **2**; a follow-up structural checker hard-coded `pipes == 3` and flagged the **3-column** summary table as malformed | twice on the verge of *"the table I just wrote is broken"* → would have triggered a pointless corrective edit to a correct file | both were the checker's fault, caught in one step each by inspecting the raw text and by comparing against **neighbouring untouched rows** of the same table. ⇒ **when a check fails on something you just wrote, suspect the check first** — and always validate a checker against a known-good control line before believing its verdict |

**Why:** every one of these is a *true* observation about the instrument paired with a *false*
generalisation to the target. They are seductive because the measurement really was performed and
really did return nothing. The failure is never in the measuring — it is in the sentence written
afterward.

⚠⚠ **THE TALLY ITSELF HAS DIVERGED — a live instance of rule 9, in the document about rule 9.**
The header above said *"43 confirmed instances"* while `CLAUDE.md` independently cites a **"44th
instance"** (FK-17's cached banner image, S121) and a **"45th instance"** (the `claimableRewards`
non-control, S120), **neither of which is tabulated here**. Adding S123-a/b/c gives **45 tabulated
rows + 1 caught in prose + 2 cited only in `CLAUDE.md` = 48 known instances.** The count is stated
here as a range rather than silently reconciled, because picking a number would repeat the exact
error being catalogued. **If you cite a count, cite this line, and re-derive from the table.**

★ **S124 adds three more (FK-22, `docs/fk22-dropphase-reachability.md` §6, §7).** Re-derive; do not
retype the total.

| id | instrument | blind spot | false result it produced | how it fell |
|---|---|---|---|---|
| **★★★ S124-a** | a `grep` for `ERoundPhase::EGP_*` over a corpus containing **`docs/*.md` prose and `dumps/**/*.dump.exe`** | the **enum name table inside the binary** contains every member exactly once, and the docs *discuss* the phases in body text | *"all ten round phases occur — the synthesis's 193/193 `EGP_BeginInit` is refuted"*, i.e. a false **refutation** of a correct finding | restricting to `--include=*.log` and to the transition line `Setting Phase to` gave **193 occurrences, 193 of them `1 (BeginInit)`** over 564 log files. ★★ **The tell was in the numbers before any context was read: SEVEN distinct phases at EXACTLY 32 occurrences.** A suspiciously **flat distribution across categories is the signature of counting a VOCABULARY, not EVENTS** — real transitions vary. ⇒ **never census a runtime behaviour over a corpus that contains the binary declaring its vocabulary.** ⇒ **and a challenge is not exempt from controls: the refutation was more exciting than the confirmation, which is exactly why it needed the harder check first** |
| **★★★★ S124-b** | an IoStore package's `.names.txt` as a presence test for a **serialized property** | unversioned property serialization resolves names by **usmap/schema index**, so an inherited property's name need not enter the package name map | *"`TeamDropPodClass` is not set on `BP_DropPlane_Base`"* — while `bpdump @props` on that same asset shows the CDO setting it to `BP_DropPod_C`. A **false positive control** had even been built from `MaxDropPodDistance` happening to be present | **use `bpdump @props`, never a name-table grep, for "is this property set?"** Same family: the persistent `LVL_Tutorial.umap` (693 names) lacks all three drop markers while its **World Partition cells carry them** — *the persistent map alone is the wrong instrument for a WP level*, and the first marker census returned 0/3 purely because **0 of the 67 `LVL_Tutorial` cells were in the 3,100 packages it searched** (`comm -12` = 0 overlap) |
| **★★ S124-c** | `catalog/*.json` grepped for a function name, to find **call sites** | the catalog carries declarations and SuperStructs but **zero `ScriptBytecode`** — and game-mode BPs are absent from it entirely | *"only 3 assets in the whole 68,303-file catalog mention `SpawnPlane`"* | counter-control: `GoToPhase` is called **twice** and `AddPlayerToDropPlane` **once** in the Tutorial component's own ubergraph, while `grep -c` on its catalog JSON returns **0 for both**. ⚠ The calibration that blessed it counted **declaration names** — *a positive control on a different signal class than the test*, which is the pattern itself |

★ **S124 second batch (the phase-write grading, `docs/fk22-dropphase-reachability.md` §8.7).** Five
more, four of them on the thunk→impl method that this project relies on for every stub claim:

| id | instrument | blind spot | false result | how it fell |
|---|---|---|---|---|
| **★★ S124-d** | **unaligned byte-pattern scanning** for an instruction | a mid-instruction byte match **drops the REX prefix** and decodes from the wrong boundary | `0x56772d0 mov [rdi+0xA44], ah` instead of the true `0x56772CF` `44 88 a7 44 0a 00 00` = `mov byte [rdi+0xa44], r12b`. **Reproduced independently THREE times in one experiment** (one grader, both verifiers' first passes) | linear-disassemble from a known boundary. ★ **The wrong decode is PLAUSIBLE and self-validating** — same displacement, same apparent semantics, wrong source register. Same family as S115-d, but caused by a **scanner** rather than by prose compression, so the rule generalises |
| **★★ S124-e** | a **self-built registration-record table**, used to count ICF fold multiplicity | record-shape recognition **silently drops entries**, so any multiplicity read off it is a **LOWER BOUND, not a count** | a 6,307-record table read `0x5254180` = **64** and `0x2c2ce30` = **22** against true **92** / **23** (a ~30 % undercount) — **while citing those very numbers as its calibration**. A 16,269-record table read 91 vs 92 and called the match "exact" | **count qword pointers to the address image-wide** — an instrument that does not depend on recognising the record shape. Two verifiers did so independently and agreed 92 / 23. ★ This also likely reconciles the long-standing **91-vs-92 wobble** in `CLAUDE.md`: pointer SLOTS ≠ distinct registered NAMES (`AuthSetDeathCircle`'s thunk occupies 2 slots). **Do not retype either number** |
| **★ S124-f** | a blanket *"identical across all N images"* | the blanket silently covers addresses **outside** the N-image census — `OnRep_CurrentPhase_Internal` (`0x569ac50`) is decrypted in only **4 of 13** | the coverage statement did not cover the row it was attached to (the claim itself survived) | **state coverage PER ADDRESS, never as a blanket** |
| **★★ S124-g** | the **thunk→impl "last direct call"** method itself | **MSVC can inline a tiny body INTO the exec thunk** — `GetCurrentPhase`'s thunk `0x5388300` contains **zero calls of any kind** | a "last direct call" grader returns nothing and reports `UNRESOLVED`/`ELIMINATED` on a perfectly REAL 3-instruction function | ⚠ **The method now has FIVE known failure modes:** (i) vtable resolution inflating EMPTY 79→464, (ii) `ELIMINATED` on inlined members, (iii) zero pages read as EMPTY, (iv) **`__security_check_cookie` (`0x751deb0`) taken as the last direct call** — demonstrated, not assumed: without the exclusion, gold `SpawnPlayer` **mis-grades to `0x751deb0`** — and (v) the body inlined into the thunk. **Anyone re-running a thunk→impl grader in this image must carry the `__security_check_cookie` exclusion** |
| **★★★ S124-h** | a **behavioural log line** counted as evidence about STATE | the line prints its **ARGUMENT**, and is emitted **before** the guard that would make it a state transition | `"Setting Phase to %d (%s)"` counted 193/193 as `1 (BeginInit)` was read — **for a full investigation, including by the session lead** — as *"the round-phase machine never leaves BeginInit"*. It actually measures **that `GoToPhase` was only ever INVOKED with 1**: a fact about its seven CALLERS | read the emitter's disassembly before interpreting its output. ★ **The corpus did not become worthless — it changed SUBJECT**, and the new subject (the call sites) is the more actionable one. ⚠ Note the companion bound: `CurrentPhase` is **replicated**, so the net serializer writes it by computed-offset memcpy that **no literal-displacement scan can see** ⇒ the honest form is *"no compiled runtime store exists in the decrypted image"*, never *"the byte can never change"* |

★ **S124 third batch (the caller/vtable/delegate/bypass sweep, `docs/fk22-dropphase-reachability.md`
§10.7, §11).** Eleven more. Three deserve promotion to the "how to apply" rules; the rest are variants.

| id | instrument | blind spot | false result | how it fell |
|---|---|---|---|---|
| **★★★ S124-i** | a **hand-written regex character class**, used as a universal negative | `%s` renders the **scoped** enum name `ERoundPhase::EGP_ServerStartup`; `[A-Za-z]*` cannot match `:` or `_` | `grep 'Transitioning from phase \([A-Za-z]*\) to phase \([A-Za-z]*\)'` returned **0**, drafted as *"`GoToPhase` early-outs and `OnNewPhase` is never reached"* — **the exact opposite of the truth** | the bare token returns **193 occurrences across 193 files**. Self-caught. ★★ **RULE: grep the BARE TOKEN first, constrain afterwards. A zero from a hand-written regex is a statement about the regex.** |
| **★★★ S124-j** | writing down the lower-bound caveat **and then reasoning past it** | none — the caveat was correct | a line recorded *"the BP subscriber census is a LOWER BOUND, not a map"* and, **in the same report**, claimed *"BOTH shipped DropPlane subscriptions are dead code"* | **the two refuting files were named in its own corpus list and never opened.** ★★ **Stating a caveat is not honouring it.** This is the highest-frequency shape in this register that is *not* a tool defect — it is a discipline defect, and it survives adversarial review because the caveat's presence reads as rigour |
| **★★ S124-k** | an `E8`/`E9` sweep of `.text` presented as exhaustive | `merged2` `.text` is **16,638 of 30,281 pages = 54.95 %** decrypted | *"transitions 4→5, 6→7, 7→8 have NO native caller anywhere in the image"* | demonstrated **from inside the finding's own set**: `0x5614690`, one of the seven callers, is a **zero page in 15 of the 16 single-state dumps** and survives only because one state was merged. Had it not been, the whole `GoToPhase(2)` restart path reads as callerless. ⚠ Also: `0x5601020` is address-**taken** by `lea` at `0x5453AB9`, so *all call/jmp xrefs* ≠ *all references*. **ABSENT ≠ COVERAGE-BLOCKED, again** |
| **★ S124-l** | a **`.pdata`-anchored** function-start scan | blind to functions with **no `.pdata` row** | missed **`EndGlideDive` (`0x55A8580`)** — the very function it was correcting | caught only because the address was already in hand from another route. Disclosed by the finder |
| **★ S124-m** | grading REAL while coverage-blind | — | `BeginFollowingActor` listed **REAL** in the same paragraph that correctly listed its siblings coverage-blocked; its impl `0x55A33F0` is a **zero page in 18 of 18** images | apply the coverage check to every row, not to the rows you expect to fail |
| **★ S124-n** | a verdict that **contradicts the reporter's own instrument** | — | `ULokiPreloadComponent::OnRoundPhaseChanged` filed COVERAGE-BLOCKED off a zero **thunk**, while the identical `.data` triple the same agent used two claims earlier yields impl `0x56C58A0` = real bytes in 18/18 | **apply your own resolution method to your own negative before recording it** |
| **★ S124-o** | prose compression, **fourth recorded instance** | — | a summary said the phase lever *"collapses to a single `BP_AuthSetCurrentPhase(4)` call … with zero pokes"* — refuted by its own finding 13, since `0x567A160` provably does not write `+0xA44` | same shape as S115-d (`exec thunk = impl`): **a correct measurement flattened into prose that asserts more than the bytes do** |
| **★ S124-p** | a denominator corrected, then over-generalised | `.text` coverage is **not one unit** | "0/18 images" self-corrected to "0/3" (that control page is decrypted in only 3) — then applied as if uniform, while `IsGlideDiving` is non-zero in 4 and `SetPilotPlayerState` in 7 | **measure the denominator PER ADDRESS, not per region** |
| **★ S124-q** | REX-prefix drop, **fourth firing** | a mid-instruction byte match decodes from the wrong boundary | a disp-`0xA44` store reported at `0x56772D0` | linear decode gives **`0x56772CF`** (`44 88 A7 …`). Caught by the mandated boundary check — the guardrail worked |
| **★ S124-r** | fold multiplicity **omitted** beside a folded address | — | `0x330C56C` graded as the `OnNewPhase` forwarder without stating it is **fold 3** | conclusion survives (it rests on the fold-1 thunk `0x5457480`), but the rule was broken **inside the report that names the rule** |
| **★★ S124-s** | grading a not-found record as **[I]** instead of **UNRESOLVED** | — | *"`[vtable+0xB08]` is probably `OnNewPhase`, but no `.data` record names it"* — recorded [I] | the record **exists** at `0x9C1F328` and was one 12-line script away; the session lead read it and the forwarder's own bytes name the slot. ★ **A record you did not find is NOT-LOOKED-FOR. Grading it [I] understates how cheaply it settles** — [I] invites you to move on, UNRESOLVED invites you to look |

★ **Free control worth reusing, from the same work:** the two `GoToPhase` log lines gate on the **same**
verbosity byte `0xA036D00` at the same threshold, machine-verified at both sites — which is what makes
"one present, the other absent" a *discriminating* test rather than a verbosity accident.
**Before treating a log pair as a control, prove they share a gate.**

★ **S124 fourth batch — found LIVE, in the armed window (`docs/fk22-dropphase-reachability.md`
§14.4, §15).** These are the first in this register caught **by an instrument's own refusal to
guess**, rather than after publication.

| id | instrument | blind spot | false result | how it fell |
|---|---|---|---|---|
| **★★★★ S124-t** | a GameMode selector matching any derivation chain **containing** `"GameMode"`, ranked by *"`[+0x258]` points at a live UObject"* | `Comp_GameMode_*` **ActorComponents** all contain the substring, and pointer-shaped bytes at a wrong offset pass a liveness test | on the live world it **REJECTED the one true `LokiRoundGameMode` and ACCEPTED `Comp_GameMode_DeathCircle` and `Comp_GameMode_RoundReset`**. The python probe silently picked `EndOfGameModel` and reported `gm7C0 = 0` — which reads exactly like *"the initializer never finished"* and is a reading off the wrong object | ★★ **the C++ shim REFUSED to guess between two equally-qualified candidates and aborted, having armed nothing and written nothing.** Had it guessed it would have driven a DeathCircle COMPONENT as the game mode. **Fix: require the class that DECLARES the function (`LokiRoundGameMode`) — 1 of 18, unambiguous.** ⇒ **sixth member of the class-lookup blind-spot family**, and the first caught prospectively. ★ *Two independently-written probes committed the SAME substring trap*, so "a second implementation agrees" is not corroboration when both inherit the same idiom |
| **★★★ S124-u** | `Num > 0` on a multicast delegate, used as the precondition for a broadcast | `Num` proves the invocation list is **non-empty**; it says NOTHING about whether YOUR target is in it | `BP_AuthSetCurrentPhase(6)` fired into a **7**-subscriber list and produced zero effect. The pre-registered reading was *"phase 6 does not drive the drop phase"* | walking the list (`FMulticastScriptDelegate` at `GS+0x590`, `FScriptDelegate` stride 16, indices resolved through `GUObjectArray`) named all 7 objects — and the DropPlane component (`0x1B3771413C0`) **was not among them**. ⇒ the null was about **reachability, not behaviour**. ★★ **A BROADCAST'S NULL IS UNINTERPRETABLE UNTIL YOU ENUMERATE THE SUBSCRIBERS.** It is one read-only RPM and it converted a dead end into a mechanism |
| **★★★ S124-v** | a pre-registered log receipt, on a SECOND flight into the SAME process | the first flight had already produced that exact line, so the log is **append-only and pre-contaminated** | `Setting Phase to 7 (Combat)` was the registered receipt for A5 — but the S14 cascade had already emitted it, so **presence had stopped discriminating** | baseline COUNTS were recorded before injecting (`Combat`=1, `Lineup`=1, `DropPod`=3, `DropPlane`=2) and the test became *"does the count increment?"* (it did not). ★ **A receipt is only valid while its baseline is zero. Re-flying into a live process invalidates every receipt the previous flight already produced — re-baseline, or pick a receipt the earlier arm could not emit** |
| **★★ S124-w** | `build.ps1 -Variant <v>` without `-Name tutorial_launch` | the `-Variant` filter is only applied WITHIN a named shim; alone it falls through to the default set | the "rebuild" produced **11 unrelated DLLs and not the probe**, while printing **`11 built, 0 failed`** — which reads like success | caught only by diffing the artifact's `.text` sha256 afterwards. ★ **A build that SUCCEEDS is not a build of the thing you asked for. Diff `.text` after every rebuild** — the project already had "diff `.text`, never size" for A/B; this extends it to *confirming the build happened at all* |
| **★ S124-x** | `--help` on a live-RPM probe | the arg parser attached to the process before handling `--help` | printed a full readout of a process that had launched seconds earlier, every field zero | its own **positive control** caught it: `POSITIVE CONTROL VERDICT: FAIL … >> STOP. Everything below is uninterpretable.` Without that gate, `NumElements = 0` and zero GameMode candidates would have read as *"the ladder is frozen and there is no game mode"*. ★ **A probe that refuses to report when its control fails is worth more than one that reports accurately when it passes** |

★★ **The generalisable lesson of this batch: THREE separate aborts (two GameMode-selection, one
GameState-validation) each cost ~2 minutes and ZERO launches, because the probes were built to abort
loudly rather than proceed on a guess.** The `GcAlive` guard that blocked the run twice is what caught
a WRONG DOCUMENTED OFFSET (`GameMode+0x258`, refuted; the real one is `+0x418`). **Design probes to
refuse; the refusals are the cheapest measurements you will ever take.**

★ **S130 adds eight (FK-41, `docs/s130-actor-pool-gate-settled.md` §9). Re-derive the total from
the tables with `grep -cE '^\| \*\*[^|]*S[0-9]+-[a-z]+\*\*' docs/method-rules.md`; do not retype it.**
Four are tool-output blind spots on the offline RE toolchain this project now depends on daily; the
fifth is the **orchestration itself**, a new class — the harness that ran the investigation failed
silently in exactly the way a bad probe does; and the sixth (**S130-f**) is the re-derivation command
for this very tally, which under-counted by half until it was run.

| id | instrument | blind spot | false result it produced | how it fell |
|---|---|---|---|---|
| **★★★ S130-a** | `fkdis.py findptr <addr>` row count, read as a **fold multiplicity** | the helper hard-caps its result list at **200 rows** | *"`0x0B9E1F0` is a 200-way fold"* — one step from a write-up quoting a specific, wrong number as a measurement | uncapped it is **26,444**. Also measured uncapped this session: `0x0F7EC20` **165,789**, `0x0F7EB50` **27,217**, `0x12C7260` **2,823**. ⇒ **a row count from a capped listing is a FLOOR, never a count** — the same shape as `obj_by_class.py`'s 60-row cap, which this project has already recorded once |
| **★★★★ S130-b** | `strxref.py func <rva>`'s `extent … (N bytes) -- EXACT` line, read as **function size** | extents are per-**`.pdata` ROW**, and this image chains rows heavily | `SpawnPoolableActorFromClass` reports **59 B** and the pooled acquire reports **1,086 B**; their real bodies are far larger and **3,702 B** respectively — a linear sweep bounded by the reported size **misses every branch in the tail**, which is exactly where the null-return conditions live | walk `tools/strxref/index/pdata_union.csv` and union the chained rows. The word **EXACT** refers to the row, not the function. Same defect S124 hit on `GoToPhase` (`0x271` vs `0x2C0`) — **it is systemic, not incidental** |
| **★★ S130-c** | a **blank** result from `fkdis.py d <rva>` | capstone decodes nothing when `<rva>` is not an instruction boundary | reads **identically to "the page is not decrypted"** — an absence claim about coverage, manufactured from a query error (`0x56481D0` → one empty line; `0x56481D7` → 109 instructions, same page) | print the page-coverage line **and** re-anchor to a known boundary before believing a blank. A blank disassembly is a QUERY failure until proven otherwise |
| **★★★ S130-d** | the **orchestration** itself — a workflow whose synthesis prompt was built but never interpolated | the lane packet was computed into a variable and the template string never referenced it, so the synthesiser received **no lane input at all** | the final agent silently re-derived the entire subject solo; six lanes' results (3.2 M tokens) sat unread in `journal.jsonl`. It was honest — it opened with *"the six lane reports were not present in my input"* — **but a less careful agent would have written a confident synthesis of nothing** | **read the agent's provenance note, and read `journal.jsonl` before trusting a workflow's final answer.** An orchestration bug is an instrument artifact: the instrument here is the harness, and it fails silently in exactly the way a bad probe does |
| **★★ S130-e** | a UHT `FBoolPropertyParams` record read at the wrong **record** boundary | adjacent records are fixed-stride and every field decodes plausibly one record over | `bEnablePooling`'s `SetBitFunc` written up as `0x03368BE0` / `[rcx+0x2d2]` — those bytes belong to the **preceding** record (`bDebugTarget`); the true value is `0x03368BF0` / `[rcx+0x2d3]` | resolve the record by **`findptr` on its `SetBitFunc`** and require multiplicity 1. ⚠ **This is S115-d recurring** — *a byte string printed next to an address it did not come from* |
| **★★★ S130-f** | a `grep -E` counting regex containing a **multi-byte literal with a `+` quantifier** (`^\| \*\*(★+ )?S[0-9]+-[a-z]+\*\*`), written to let a future session **re-derive this very tally** | POSIX `grep` is **byte-oriented**: `★` is 3 UTF-8 bytes (`E2 98 85`), so `★+` quantifies only the **last byte**. It matches `★`, `★`, `★`… but **not** `★★★` | **33 instead of 67 — exactly the rows with zero or one star, silently dropping half the table.** It would have shipped as the project's own recommended re-derivation command, so **every future re-derivation would have reproduced the same wrong number and looked self-consistent** — the worst property a tally instrument can have | I ran the command I was about to publish, against the count I had just derived in Python (where the same regex is applied to a **decoded str**, so `★+` means one-or-more ★ and is correct). **33 ≠ 67.** Fix: `^\| \*\*[^|]*S[0-9]+-[a-z]+\*\*` — no multi-byte literal at all — which returns **67** and matches Python's result on **identical sets**, not merely an equal count. ★ **The rule: never put a multi-byte character under a quantifier in a byte-oriented regex — and always RUN an instruction you are about to publish, especially one whose whole purpose is to check a number nobody will re-check by hand.** ⚠ This project's own note *“re-derive from the table, never retype the number”* was, for one commit, pointing at a command that could not do it. |
| **★★ S130-g** | `extractor bpdump <asset> @props`, used to answer *“does this Blueprint's CDO override property X?”* | the `@props` branch sat **behind a `continue` that required the asset to have UFunction exports** (`Program.cs:1137`), although `@props` wants a UObject export and needs no UFunction at all — exactly like the `@imports` needle beside it, which was correctly exempted | on a **data-only Blueprint** (0 UFunction exports — precisely what `BP_DropPod_Tutorial` is) it printed **`No matching UFunction '@props' found`**, which reads as *“the asset has no such property”*. The load-bearing question was whether the drop pod overrides `bCanEverReplicate`; the tool's answer was indistinguishable from “no” and meant “not looked at” | the message names a **UFunction** while the query is about **properties** — a mismatch between what was asked and what the error is about. Fixed by exempting `@props` alongside `@imports`, then **validated by re-dumping `BP_LokiGameState_Tutorial` and reproducing its known `bSupportsActorPoolPriming = False` BEFORE trusting any new dump.** ★ Rule: when a tool reports a negative in terms of an object it should not have needed, suspect the gate, not the data |
| **★★★ S130-h** | the log line `LogActorPooling: Adding <Class> to list of poolable actors`, read as *“that class is loaded”* | the registration is an **AssetRegistry query against COOKED TAGS** (`bEnablePooling` is `CPF_AssetRegistrySearchable`) — it never touches a UObject, so all 176 registrations fire at the menu with **no CDO in memory** | a probe aimed at four Blueprint CDOs found **none of them**, against **10,371 live CDOs** — and had it not guarded, it would have read offset `0x6C` of a null pointer and reported **four confident zeros**, which was exactly the value that would have *refuted* the session's model. A false refutation, manufactured from a null read | the probe printed `NOT LOADED (this is NOT a zero)` instead of a number, and printed the live CDO census beside it so the absence was interpretable. Retargeting at the **native parent** CDOs (created at module init, and the exact objects whose constructors had been disassembled) gave 8/8. ★ Two rules: **“registered”, “referenced” and “loaded” are three different states — a log line about one is not evidence of another**; and **a probe must distinguish “absent” from “zero” in its OUTPUT, because at the byte level a missing object and a false flag look identical** |
| **★★★★ S132-a** | `usmapdump dumpimage <proc-name>`, used to snapshot a LIVE client mid-armed-window | the process lookup requires the **`.exe` suffix**; without it the tool prints `ERROR: process "SUPERVIVE-Win64-Shipping" not found (is the game running?)`, and given a bare **PID** it prints `module "48356" not found in PID 48356` | **both messages read as *the game is dead*** — and they arrived seconds after a data-class write into a live component, i.e. at exactly the moment a session would conclude *our poke killed the client* and write that up | `Get-Process` showed the client **alive at 650 s**, and it went on to survive another 460 s and three more injections. Retrying with `SUPERVIVE-Win64-Shipping.exe` dumped 169.9 MB normally. ★ **Rule: a tool's "process not found" is a claim about the tool's lookup, not about the process. Check `Get-Process` before believing any liveness claim an unrelated tool makes as a side effect.** ⚠ The bare-PID form is a genuine tool bug — it resolves the PID and then searches for a module of the same name |
| **★★★ S132-b** | the session lead's **own hand arithmetic**, subtracting an ImageBase from printed VAs | `0x7FF6B239A550 - 0x7FF6AF000000` was read as `0x239A550`; it is `0x339A550`. The error fires whenever the third hex digit rolls past `af`, and hit **7 of 21** call targets | every wrong RVA disassembled into **plausible mid-function garbage**, and every `.data` record-table lookup on one returned `None` — which reads exactly like *"not a reflected function"*. Four callees would have been recorded as unnameable when in fact they are `SetActorEnableCollision`, `SetPredropHidden`, `GetLokiCharacterMovement` and `MulticastOnPlayerEnteredWorld` | recomputed with `python`; all four resolved. ★★ **This project's own standing rule is *"recompute, never retype an RVA"*, and it was broken in the first ten minutes by the session that had just re-read it.** It cost nothing only because an all-`None` column is obviously wrong. ★ The SAME defect was caught the same day in a recon lane by its adversarial verifier: a printed rel32 decode (`0xFB9CB170` → "-73,895,568"; true value **-73,617,040**) whose own arithmetic gives the wrong address, under a header claiming *"every address recomputed with `python -c`; none by hand"*. **The conclusion was right and the shown work was false** — which is the more dangerous failure, because the reader checks the work |
| **★★ S132-c** | a one-line PowerShell **summary regex** wrapped round five `build.ps1` invocations | the regex did not match the tool's actual success line, while the tool's own `1 built, 0 failed` was printed verbatim two lines above | printed **`FAILED`** for five builds that all succeeded — twice, in two different sessions of the same hour | read the raw tool output beside the summary; every build had said `1 built, 0 failed`. ★ **This is S131's `pod_verdict.py` lesson recommitted on the same day it was read: an analysis one-liner is an instrument too, and a summariser that can only ever *under*-report success will be believed the first time it is wrong.** Verify a summariser against a case whose answer you already know |
| **★★★ S132-d** | an arm's own **refusal message**, conflating two different causes | `if(!a || !GcAlive(a)) Markerf("no live '%s' actor resolved")` — one message for *"the scan found nothing"* and *"the scan found one but it failed the liveness check"* | the landing-actor experiment returned that message and the natural reading was **"the class-lookup helper's substring match is broken"** — the class-lookup blind-spot family this project has recorded five times, and the fix would have been to "repair" a helper that was working perfectly | rewritten to **enumerate every candidate, print it with its class, object name, liveness and location, and report the scanned-object denominator**. It then reported `0 candidates … over 143,130 objects walked` — the actor had genuinely **streamed out** of a World Partition cell. On the next launch the same code found it (`1 candidate … over 154,919 objects walked`) and the experiment ran. ★ **Rule: a probe must never emit one message for two causes. And when a familiar-looking blind spot is suspected, MEASURE it before fixing it** — the suspicion was wrong, and "fixing" the helper would have broken a working one while leaving the real cause (cell streaming) undiscovered |
| **★★ S132-e** | the **Bash tool's heredoc**, used to feed a Python patch script that edits C++ source | it silently collapses one level of backslashes, so `"BS BS r BS BS n"` in the script text became a **real CR/LF** inside a C string literal | three `error: expected expression` compile failures, and — more insidiously — a *successful* earlier edit that split a `Markerf` format string across two source lines without anyone noticing until the compiler objected. A patch tool that corrupts the text it writes is indistinguishable from a bad patch | write patch scripts to a **file** and run the file; or build escape sequences with `chr(92)` so no literal backslash ever passes through the shell. ★ The general form: **whenever a transformation passes through more than one quoting layer, verify the OUTPUT bytes, not the input text** |


Also from S124, tool-level and worth knowing before they cost a session:
- **`extractor wherefile` clamps at `.Take(20)` BEFORE counting** (`Program.cs:840-844`) — any printed
  count of exactly 20 is saturated. Same family as `obj_by_class.py`'s cap-at-60. (A second,
  **unclamped** copy at `:809-810` means the clamp is not a file-wide property — check the subcommand.)
- **`extractor namesall` filters `.EndsWith(".uasset")`** (`Program.cs:1072`) ⇒ structurally blind to
  `.umap`. ⚠ The measurement first attached to this finding was itself false; the point stands from
  the source line alone, not from the reported run.
- **`bpdump`'s output filename is keyed ONLY on the function name, not the asset** — the collision
  fired at least three times in one investigation (`bpdump_SpawnPlane.txt` was successively the
  Tutorial, general and PvE_Holdout asset). **Verify the `# Asset:` header before reading a byte.**
- **`_ALL` / `_PROPS` are output-file SUFFIXES, not bpdump needles.** The real special needles are
  `*`, `@props`, `@imports` (`Program.cs:1136`, `:1140`, `:1350`). **`@imports` resolves class
  hierarchies and is documented nowhere else in the repo** — it is what settled FK-22's core fact.
- **The `Grep` TOOL respects `.gitignore`**, and `tools/extractor/.gitignore:9` ignores `out/` — it
  silently returned 2 of 3 known-matching files. Use bash `grep` with explicit directories there.
  (`rg` is **not installed** on this machine, so any doc citing an `rg` command was not run.)
- **`docs/game-map.md` is a 229-line category summary, not an asset listing** — it returns 0 for
  `DropPlane`, `Comp_GameMode_DropPlane` *and* `DropPod`, all of which exist. Not an existence oracle.
- **`exec_chain_grade.impl_of` resolves indirect calls through the class vtable** (`:363-369`,
  `:435-446`); grading EMPTY off that inflates the image-wide stub count **79 → 464**. Require a
  **direct** call/jmp to a fold, or a vtable read with a local identity control — the strongest form
  being *scan the whole image for the impl address; one occurrence ⇒ no derived class overrides it*.
  It also returns `ELIMINATED` for MSVC-inlined tiny members (**5 false stubs** on the drop surface).

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

10. **★★ S117: SELF-TEST THE HARNESS INSIDE THE HARNESS — a broken watcher does not report as
    broken, it reports as a RESULT.** Measuring one live change (`docs/fk15-probe2-live-result-20260813.txt`)
    produced two false readings in one sitting, in opposite directions:
    - **`rg` is NOT on PATH in the *background* shell** — it *is* in the foreground one, so the same
      command that works interactively silently fails when backgrounded. Every count came back an
      empty string, `[ "" -gt "" ]` errored to stderr (invisible among the noise), and the loop fell
      through to printing **`RESULT: HELD`** — a **false PASS that happened to agree with the
      hypothesis**, which is the hardest kind to catch.
    - **Log timestamps are UTC; `ags`/PowerShell times are local** (here UTC = local + 5 h). A
      by-minute histogram keyed on the *local* hour read a window **five hours before the change**
      and showed the old behaviour continuing — a **false FAIL**.
    ⇒ **Every harness must verify itself before its first real reading:** `command -v` each binary
    it depends on, run a **positive control** (a string you know is there) and a **negative control**
    (one you know is not), and **abort loudly on an empty or non-numeric probe** rather than
    comparing it. And **state the timezone whenever a log line is correlated with a deploy, commit
    or wall-clock event** — this project already learned the same lesson about *elapsed* time in
    FK-8 (§6 above); absolute time has the identical failure mode.
    ⚠ Note the shape: the shell that runs your check is not necessarily the shell you tested it in.

11. **★★ S117: SHOW THE NEEDLE CAN MOVE BEFORE YOU RUN THE EXPERIMENT.** A positive control on
    your *measuring* instrument is not enough — the *display path* needs one too. Testing whether
    the client applies a server-pushed loadout, the chosen observable was the menu podium's hero
    skin. The server side was flawless (push sent, client refetched, socket held) and the screen
    did not move — because the podium skin is rendered by `loadout_fix.cpp` replaying equips via
    native calls, and **no shim was injected in that session** (`GET /revival/loadout` = 0, all
    shim markers days stale). The null was **guaranteed before the experiment started**, and no
    amount of correct backend work could have changed it. Ask first: *what would have to be true
    for this indicator to change at all, and is it true right now?*
    ⚠ Compounding it: three screenshots at two different window sizes were compared by eye, and
    extra detail visible at the larger scale was reported as a garment change. **Do not argue a
    result from subtle detail across differently-scaled images** — demand a change that cannot be
    read two ways, or read the state directly (RPM) instead of looking at it.
    ★★ **AND THE COMPANION RULE, from the rerun that finally worked: when two readings of an image
    disagree, do not debate the pixels — build a REVERSIBLE change and drive it back and forth.**
    On the retest the operator read two shots as identical (watching the skin, which had genuinely
    not changed) while the podium colour had shifted. Instead of arguing, the change was reverted
    and re-pushed, producing **blue → gold → blue on command**. A round-trip under your own control
    is proof; a single before/after pair is an opinion. It also costs nothing extra — the revert was
    needed anyway.
    ★ **Choose an observable your own tooling cannot drive.** The retest also had to discard the
    obvious indicator (the hero skin) because a client-side shim polls the same data every ~175 ms
    and would have produced the "right" answer for the wrong reason. The lobby platform was chosen
    precisely because `grep -ci lobbyplatform loadout_fix.cpp` = 0. **Before trusting an indicator,
    grep for everything else that can move it.**

12. **★★ S117: AN ABSENT ERROR MESSAGE IS ONLY EVIDENCE IF YOU KNOW IT CAN BE PRINTED — and
    the cheapest check is to feed the system something impossible.** A 33-type sweep was written
    up as "all 33 routed to a **dedicated handler case**" on the strength of zero
    `Error; Detected of type notif but no specific handler case assigned` lines. That absence was
    worthless: the RE pass for this very investigation had **already recorded in writing** that
    those two error strings are not plain `UE_LOG`s — they are `Printf`'d into an FString and
    pushed through a virtual on `Lobby+0x218`, so they may never reach the log — and the claim was
    made anyway, then committed and pushed.
    **The disproof cost nothing and was accidental:** a leftover placeholder push sent the type
    `dsNotice-PLACEHOLDER`, a name absent from the binary, and it produced the *identical* trace
    including `Type: dsNotice-PLACEHOLDER`. So the line being used as the success signal is emitted
    **before** the lookup it was assumed to follow.
    ⇒ **Send the impossible input on purpose.** A bogus id, a nonexistent type, a malformed key: if
    your detector reads the same for it as for the real thing, the detector is not measuring what
    you think, and every result resting on it is void. This is the negative control applied to a
    *log line* rather than to a scan, and it takes one extra push.
    ⚠ Note the shape: the warning existed, in this session's own notes, and was not applied. Having
    the caveat written down is not the same as honouring it at the moment of writing the conclusion.

13. **★★★ S117: WRITING A METHOD RULE IS NOT APPLYING IT — the same session that added rule 10
    ("self-test the harness inside the harness") then shipped a harness with no self-test, and
    published its output as a measurement.** A `findptr` sweep over 7 candidates reported "0 aligned
    pointers [M]"; that was a **grep bug**. The tool prints hits as `    @0xADDR   bytes: …` and the
    script matched `^ +0x[0-9A-F]+`, which never matches the leading `@`. Every "no hit" was the
    parser failing silently. The false negative was committed **and pushed** as a measured result,
    complete with an inference built on top of it ("the visible copies must be transient").
    **What caught it was a positive control that cost one command:** a global at RVA `0x9FFEBD0`
    provably points at one of the very candidates being scanned — running that address through the
    harness returned "no hit" for a pointer that demonstrably exists.
    ⇒ **Before trusting any search harness, feed it something you have already proved is there.**
    Not the tool — the *harness around* the tool. The tool was correct throughout; the four lines of
    shell wrapping it were not, and only the wrapper's output was ever read.
    ⚠ This is the third self-inflicted instrument failure in one sitting (rg-absent shell, UTC-vs-
    local, this). The pattern is not ignorance of the rule. It is that harness code feels like
    plumbing rather than instrumentation, so it escapes the scrutiny applied to the measurement it
    produces. **Treat every line of glue as part of the instrument.**

14. **★★★ S123: RECORD THE RAW VALUE, DERIVE AFTERWARDS. A stored derived value cannot be
    re-analysed when its derivation turns out to be wrong.** `rootset_census.py` sampled 200k objects
    across three GC passes and stored, per object per sample, a **boolean** — "does it carry the
    currently-dominant reachability bit". The comparator was a lagging majority vote whose polarity
    inverts mid-sweep, so the whole run measured something other than what it claimed, **and the flag
    words needed to re-derive it had already been discarded.** The same run at a 0.4 s period reads
    32/32 and at 0.5 s reads 0/32.
    ⇒ Storage is cheap and re-analysis is free; a derivation baked into capture is neither.
    ⚠ This composes badly with rule 11: the derived metric *did* move, so it looked like a working
    needle. **A metric that moves is not thereby measuring the thing you named it after.**

15. **★★ S123: STATE THE NULL MODEL BEFORE QUOTING A p-VALUE, AND CHECK THE DATA HASN'T ALREADY
    REFUTED IT.** "Zero free slots in the prefix, P ≈ 1e-676 if uniform" was reported as decisive.
    The free slots are not uniform — most form one contiguous run at the boundary — so the null was
    already false, the number meaningless, and a *different* region with the same property was not
    rooted at all. The conclusion happened to be right for unrelated reasons, which is the dangerous
    case: **a correct conclusion resting on a bogus statistic will survive review and then be cited
    for the statistic.**

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
