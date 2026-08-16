> ⛔ **FK-7 IS CLOSED (S112, 2026-08-08).** Any statement below that FK-7 is open, unverified, or needs a reproduce-then-repair run is **HISTORICAL**. Cause = our own standing `.text` patch (10/10 died with it vs 3/36 without, p = 7e-8); fixed, shipped, deployed. The remaining tutorial failures were split out as **FK-31 / FK-32** (`docs/fk31-fk32-successors.md`). Start at `docs/s112-fk7-ab-results.md`.

# SUPERVIVE Revival — The Ignorance Map (S101, inverted audit)

**Companion to `docs/coverage-audit-s101.md`.** That document asked *"how much do we have?"*
This one asks *"what don't we know we don't know?"* — and, more dangerously, *"what do we believe
that isn't true?"*

> ### 📌 LIVE DOCUMENT — the title says S101, the content runs to S121
> Entries are updated in place with dated banners; **a banner always overrides the table beneath it.**
> The original S101 text is never deleted, because the retraction history is the value.
>
> | entry | last touched | status |
> |---|---|---|
> | FK-1, FK-2, FK-3, FK-4, FK-5, FK-6 | S104–S105 | ✅ SETTLED (each with its own `fk*-settled.md`) |
> | **FK-7** — tutorial crash | **S112** | ✅✅ **CLOSED — belief false, cause MEASURED, fix SHIPPED.** Standing `.text` patch of our own: **10/10 armed windows died with it vs 3/36 without, Fisher p = 7e-8.** Deployed default now arms on **2 heap pointers**, no module-image write; 5/6 armed windows survived 600 s, no functional regression. **Do not re-open.** `docs/s112-fk7-ab-results.md` |
> | **FK-8** — `SecondsSinceStart` | **S111** | ✅ **CLOSED with a permutation positive control.** ★ Closing it showed **≥31.6 % of the whole crash corpus is self-inflicted**, and that all 22 crashpad reports are — so the S109/S110 tutorial campaign produced **zero** FK-7 evidence. `docs/fk8-crash-timing-mined.md` |
> | **FK-9** — Sentry vs UECC dumps | **S109** | ✅ **CAPTURE SOLVED** — cleared by the *next launch*, not a timer; the "~3 min window" is retracted. Archiver shipped. |
> | **FK-13** — "the dev console is fully stripped" | **S114** | ✅ **SETTLED — outcome TRUE, every stated reason FALSE, operational conclusion FALSE.** The console really is gone (`ALLOW_CONSOLE == 0`, three independent instruments) — but FK-13 was **three independent compile flags**, not one, and `bUseExecCommandsInShipping`'s stock default is **1**. So **`UE_ALLOW_EXEC_COMMANDS == 1`**, **138 native `FUNC_Exec` UFunctions** ship, and **Route B is shipped and proven end-to-end**: a `UCheatManager` constructed into `PC+0x520` (**one heap qword, zero module-image writes**) put **42 real exec verbs** live, verified by `ExecuteConsoleCommand("LogLoc")` → `LogCheatManager: BugItGo …` against a baseline of 0. ⇒ *"all cheap external paths are exhausted; the remaining options require in-process code"* is **dead**. ⚠ Still OPEN: where `open` is dispatched, and whether the 25 `ALokiPlayerCheats` verbs are reachable by spawning the actor. `docs/fk13-console-exec-settled.md`, `docs/fk13-live-run-2026-08-12.md`, `docs/fk13-routeb-shipped.md` |
> | **FK-15** — "server→client WS push is non-functional" | **S118** | ✅✅✅ **REFUTED (S117) THEN FULLY CLOSED (S118).** Push works; the real question was *which types*. Joining all 33 jump-table cases to the live delegate table shows **only 7 of 33 have a subscriber** — **21 of the 23 bound delegates belong to ONE `USocialManager`**, so the reachable set is the friends/presence family. **All 7 flown; 6 drive VISIBLE UI changes**; `disconnectNotif` is a controlled negative. ⚠ **`dsNotif`, `matchmakingNotif` and every `party*` type are UNBOUND** — the route is closed at the client's *subscription* layer, so no payload can ever make them act. ★ The client **mutates its own social state** from a notif and only a refetch re-imposes ours ⇒ **pushed changes are transient unless the backend also serves them.** `docs/fk15-bound-delegate-map-20260813.md` |
> | **FK-18 / FK-19** — "`merged.dump.exe` is a merged multi-state image" / "a different ImageBase makes a dump unusable" | **S121** | ✅✅ **BOTH CLOSED.** FK-18 confirmed and **sharpened**: the merge was a **NO-OP** (union of its 5 inputs == the seed), because `.text` decryption is **monotone within a process lifetime**, so N substates of one launch are worth exactly one dump *by construction*. FK-19's constraint was the cause, not a coexisting fact — and it is measured false: **0 of 1,403,750 base relocations target `.text`**, which is byte-identical across ImageBases (0 differing bytes, 10/10 pairwise). The two formed a **self-sealing loop**. Fixed and executed: `mergedumps` merges `.text` page-granularly ignoring ImageBase; `dumps/merged2.dump.exe` = **16,638 / 30,281 pages (54.95 %)** vs 15,833 (52.29 %), strict superset, coherent `.data`, `-wholeimage` reproduces the historical artifact **byte-for-byte**. Downstream: **+1,400 lit strings**, **13,639 crash-table functions gained readable bytes** (byteless 39,941 → 26,302). ⚠ Successors are NOT FK-18: the **read-vs-execute decryption trigger** (worth ~14,600 pages, one injected probe) and **crash-handling capture** (~2,334 pages, zero launches, untried). `docs/fk18-fk19-multistate-merge-settled.md` |
> | **FK-24** — the `ViewTarget` writer | **S108** | **OPEN.** ★ The probe was killing the game, and its own VOID verdict was an artifact. |
> | **FK-25** — the marker file | **S108** | ⚠ **STILL UNFIXED**; cost evidence again. Cheapest unspent item in this document. |
> | **FK-26** — leftover S9x shim diagnostics | **S108** | ✅ **NEW + SETTLED.** `KSTATICTEST` was killing the hero's walk/run animation every session. |
> | **FK-31** — `fo`'s `.rdata` patch "is obsolete" | **S112** | ✅ **NEW + FALSIFIED**, and it **carries FK-7's successor problem**: the **staging hazard, 22/82 launches (27 %)**, now the dominant tutorial-route failure. `KNOLOGINVT` **must not be re-run** (4/4 died, 0/4 map loads). `docs/fk31-fk32-successors.md` |
> | **FK-32** — "the artifact-less deaths are hangs" | **S112** | ✅ **NEW + FALSIFIED.** At least some are **`0x0000DEAD` silent kills**, recovered by reading the process exit code. ⚠ N=2 — suggestive, not established. Residual **3/36**. |
> | **FK-33** — S112 instrument false-knowns (batched) | **S112** | ✅ **NEW + SETTLED.** The FK-7 "candidate" build was a commit stale; the mandated 3x `play_novtguard` control voids ~4 sittings in 5; a new crashpad dir is not a death; `fk8_classify.py` reports 1 report for 105 dirs. |
> | **FK-34** — `UECC-C13252F5` "is the last FK-7 survivor" | **S112** | ✅ **NEW + FALSIFIED.** It is the ANIM family (a shim-lifetime bug). ⇒ **zero** FK-7 death records survive a mechanism filter. |
> | **FK-35** — S118 lobby/notif false-knowns (batched) | **S118** | ✅ **NEW + ALL FOUR FALSIFIED.** (a) the shipped 33-name notif list is **wrong at the tail** — `signalingP2PNotif` IS enum 32, `messageSessionNotif` is absent, caused by **two off-by-one boundary errors that CANCELLED into a plausible 33** (and a unit test asserted the false half); (b) `entries=3` is an **allocation size**, not a subscriber count (single-cast `FDelegateBase`); (c) "16 bound, 46 unbound" — the scan **stepped 0x10 over a structure with members at ≡8 (mod 16)** and the published list was **truncated at 12 with a literal `…`**, which changed the answer from 6 reachable types to 7; (d) presence "both directions" was **published unobserved** — offline needs `activity` OMITTED, because the activity blob **overrides** availability. |
>
> | **FK-36** — S120 Hero Mastery / claim false-knowns (batched) | **S120** | ✅ **NEW + ALL SIX FALSIFIED.** Hero Mastery went from "unlooked-at" to **solved end to end, backend-only** (renders → unlocks → bars move → rewards offer → **the client AUTO-CLAIMS**). The six beliefs that had to die are below; the most expensive was **(c)** — a negative published as "controlled" that was contradicted by data already in hand. `docs/s120-hero-mastery.md` |
>
> | **FK-37** — S121 feature-toggle false-knowns (batched) | **S121** | ✅ **NEW + ALL SIX FALSIFIED.** The A-14 payload was inert for **~48 sessions** over one word (`ConfigKey` is `"enabled"`, not `"default"`), and fixing it turned on 12 gates, revealed **three endpoints the client had never been observed to call**, and produced a working LEADERBOARDS page. ★ The session also built the **readout** A-14 said it lacked, so "flag off" and "companion condition unmet" are now distinguishable. ⚠ Five of the six dead beliefs were **the session's own arithmetic and instruments**, not the game. `docs/s121-toggle-fix-confirmed.md` |
> | **FK-38** — S121 late-session RE false-knowns (batched) | **S121** | ✅ **NEW + ALL FALSIFIED, and the batch is large on purpose.** The second half of S121 was continuous live RE (regions/latency, the crash family, the MOTD chain) and produced **~16** wrong-then-corrected claims, **nearly all my own analysis rather than beliefs about the game**. Every one fell to a readout. Detail below; the two that cost the most were **measuring the wrong prompt stack** and **a 22-byte packet gate against a 30-byte reality that left five tests green and the game broken**. `docs/s121-motd-trigger.md`, `docs/s121-menu-crash-family.md` |
> | **FK-39** — S123 GC/rooting false-knowns (batched) | **S123** | ✅ **NEW + ALL FIVE FALSIFIED, zero launches.** FK-27's verdict is untouched; its *explanation* was wrong. "Root-set objects are excluded from marking" was a **pooling artifact** — ~39,275 disregard-for-GC **pool** objects (index < `ObjFirstGCIndex` = 39295, never traversed) mixed with **32 real `AddToRoot()` callers** that are marked every pass. `AddToRoot` inserts into a **`TSet<int32>` registry at `.data 0x99D3CA0`** and the flag is only a mirror, which is *why* the poke was inert. ⚠⚠ And `KGCROOT` was not harmless dead code — it **blocked its own fix** (`SetRootFlags` early-outs on `Flags & 0x4E100000`); default now 0, rollback hash-verified. `docs/fk27-successor-gc-rooting-settled.md` |
>
> **The S108 lesson, in one line:** all three of that session's tasks turned out to be about **the
> project's own instruments**, not the game — and the session then committed three *fresh* instances
> of the same error while documenting it. See `docs/method-rules.md` §1 (⚠ the old pointer here was
> `memory/supervive-instrument-artifact-pattern.md`, a store **deleted 2026-08-12** — the register
> lives in the repo now), which S108 grew from five confirmed instances to eight. It stood at 43 as
> of S118, which added seven, four of them the analyst's own arithmetic and indexing. **It stands at
> 48 as of S120**, which added five — and, notably, **four of the five were caught by the session
> itself before or shortly after publication**, three of them by a *pre-registered prediction* the
> measurement then missed. ⇒ the pattern is not becoming rarer; the **detection latency** is falling.
> ★ S120's own contribution to the method: **a "fresh" reading of an uncontrolled field is still
> uncontrolled.** Recency fixes staleness, not validity — demand a positive control for the FIELD,
> not merely a recent sample of it (FK-36c).
> **It stands at ~70 as of S121**, which added roughly sixteen more in its second half (FK-38) on top of the six — **five of them the session's own counts,
> predictions and tooling**, and all six caught within the session. Two were *carried numbers* that
> nobody re-derived (a served-key count of 17 that was never reconciled against the 21 entries
> actually on the wire; a "33 keys remain" that was really 4, with 33 being the *never-serve* count
> in a different role). One was a **prediction that ignored a rule the same session had written an
> hour earlier** (+6 instances predicted, +3 correct, because a key's second instance is the
> never-evaluating archetype). One was a probe whose `.strip()` manufactured a phantom coverage gap.
> One was `class_props.py` printing `not found (map not loaded yet?)` for a class it can **never**
> find — it demands class-of-class `== "Class"` and Blueprint classes are `BlueprintGeneratedClass`,
> making it the **third** member of the class-lookup blind-spot family after `obj_by_class.py` and
> `cheat_reach_probe.py`.
> ★ S121's contributions to the method: **(i) a knob that changes the payload at RUNTIME has no code
> edit at which to hand-bump the eTag** — `AGS_UI_TOGGLES_EXTRA` would have silently reproduced the
> stale-eTag trap the same file documents, and had to fold the extras into the eTag itself. That one
> was caught *before* it fired, so it is a near-miss rather than a 55th instance — **the first
> recorded case of the pattern being anticipated in design rather than found in evidence.**
> **(ii) Verify a new guard by REINTRODUCING the bug.** The regression test added for the
> `enabled`/`default` defect was confirmed to fail on the reverted code before being trusted.

**Method.** Eleven ignorance dimensions were probed independently, then each was handed to an
adversarial challenger who re-ran every negative search against primary artifacts and graded each
claim. **Where prober and challenger disagreed, the challenger won.** Everything a challenger marked
`ACTUALLY_KNOWN`, `NOT_AN_UNKNOWN`, or `NOT_A_REAL_QUESTION` was dropped and is listed in
§12 with the reason.

**Attrition.** ~293 probe claims were adjudicated. **37 were dropped outright (~13%).** Roughly a
further quarter were downgraded from UNKNOWN_UNKNOWN to KNOWN_UNKNOWN (the question was real but the
project had already written it down). That attrition rate is itself the headline finding about
method: *most of what looks like ignorance in a 100-session project is mis-filed knowledge, but the
residue is unusually rich — because the residue is concentrated in artifacts nobody has opened
rather than in problems nobody has solved.*

**Taxonomy used throughout:**

| Kind | Meaning | Value |
|---|---|---|
| `FALSE_KNOWN` | The project believes it, it steers decisions, and the evidence is weaker than the claim | **Highest risk** |
| `UNKNOWN_UNKNOWN` | The question has never been posed in ~100 sessions of docs, memory, code or 366 commits | **Highest value** |
| `KNOWN_UNKNOWN` | Already written down as open — recorded here only when mis-scoped or mis-prioritized | Low |

---

## 1. Executive Summary — the shape of our ignorance

### 1.1 The shape, in one paragraph

The project's ignorance is **not mostly about the game**. It is about **its own instruments, its own
artifacts, and its own record**. Of the survivors in this document, the largest single category is
*"the answer was already on disk, in plain text, in a file the project generated or the game ships,
and nobody opened it."* The second largest is *"a measurement was taken with one tool, in one
encoding, against one artifact, and the result became a structural law."* Four of the biggest walls
in the record fell in this audit to a **method change, not more effort**: changing a census key
(`_AS` suffix → source-module list), changing a string encoding (ASCII → UTF-16), changing a metric
(non-zero bytes → readable bytes), and changing a surface (native disasm → shipped script bytecode).

### 1.2 Six structural findings

1. **The project derives what the game already states.** Independently confirmed across five
   dimensions: the 149 game-feature-toggle *names* sit in our own `schema.txt`; the input binding
   table sits in a 22 KB plaintext file the client rewrites every launch; the queue list, the mode
   descriptions, the in-match currency loop and the XP categories sit in DataTables and StringTables
   we extracted weeks ago; the `Party.State` field the launch gate needs is at a known schema offset.
   *No step in the project's method asks "has the game already written this down?" before RE work
   starts.*

2. **Four fifths of the shipped content is in a chunk class no tool can read.** A first-ever `.utoc`
   census (unreadable-content challenger) found **118,436 IoStore chunks** against 107,123 enumerated
   paths: 85,508 ExportBundleData (6.23 GB — the only class the extractor reads), **16,999 BulkData
   (29.62 GB)**, and 15,912 ShaderCode (1.08 GB). The audit's "path enumeration is 100%" is true and
   should be restated as **"100% of package paths, ~90% of chunks, ~17% of content bytes."**

3. **The `.pdata` the whole binary-RE domain is missing has been on disk 86 times over.** Every
   `UEMinidump.dmp` carries a `FunctionTableStream` whose descriptor 1 is based at the exe's module
   base with **524,439 RUNTIME_FUNCTION entries** covering the entire `.text`
   (524,439 × 12 = 6,293,268 B vs `.pdata` VSize 6,283,264). On-disk `.pdata` is encrypted; in-memory
   `.pdata` is zeroed. The minidumps are the only known source, and no tool in `tools/` parses one.

4. **Two "structural caps" on static analysis were instrument bugs.** `.rdata` "capped at 63.12%,
   ~13.9 MB permanently unreadable" is a *non-zero-byte* metric artifact — only **33 of 9,085**
   4 KB `.rdata` pages in the merged dump are all-zero (0.36%), versus 42.5% for `.text`. And the
   "packer defeats static string-xref" wall dies to encoding: the strings the walls name
   (`Toc signature hash`, `GetFeatureTogglesReady`, `Couldn't spawn player`) were read back as
   **byte-identical plaintext from the project's own `merged.dump.exe` at the same RVAs** — they are
   UTF-16 and the scans were ASCII.

5. **The stated goal requires two participants and nothing in the stack can represent two.** README
   Milestone 4 is "get into a match"; the overview memory says "community-play intent." The backend
   has one party constructor (`buildSoloParty`), all three party handlers resolve the player from the
   `party-<id>` URL prefix *before* the JWT subject (so in a 2-member party every member write lands
   on the leader), the stub replicates `MaxPlayersPerTeam = 1` while the backend advertises
   `MaxTeamSize: 3`, and no second identity has ever existed. **But the distinguishing key is already
   on the wire**: the client's `platform_token` is a Steam auth-session ticket carrying
   SteamID64 `76561197981196360` at byte 12, and `handlePlatformToken` reads only the absent
   `platform_user_id` form field and discards the ticket.

6. **There is no acceptance predicate at any level.** No definition of done, no "the tutorial is
   finished when…", no shim regression harness, no visual check, no frame-time number, no per-route
   hit counter, no per-asset extraction-completeness assertion. Progress is measured in *mechanisms
   proven*, never in *outcomes achieved* — which is why the project can make continuous measurable
   progress while its distance to any user-recognisable goal is unmeasured.

### 1.3 Where the ignorance is unquantifiable

Three areas resist any coverage number and should not be given one:

- **In-match behaviour.** Every claim about drop, storm, shop, items, combat, death, respawn or
  end-of-game is inference from static assets. Zero of it has been observed. The denominator is
  unknown because we do not know what the systems are.
- **What the client sends where we cannot see.** Four independent network stacks are resident in
  one process (UE curl, the Tox plugin's own libcurl, Chromium/CEF, and `runtime.dll`'s
  mbedtls-over-WINHTTP). `capture.log` sees exactly one of them. "The client never calls X" means
  "the client never called X over the one stack we can observe."
- **Behaviour implemented in Angelscript.** No instrument in the project can observe or disassemble
  it, and 78 `.as` source modules ship. Logic implemented there reads as "native, unreconstructable"
  to every tool we own — which is precisely the error S74 made.

---

## 2. The FALSE_KNOWN Register

*The most actionable section in this document.* Each entry: the belief, where asserted, the actual
evidence, why the evidence is weaker than the claim, what it currently steers, and the cheapest
experiment that settles it.

Ordered by **(load-bearing) × (weakness of evidence)**.

---

### FK-1 — "The Angelscript layer is thin; the deploy/round/respawn core is native C++"
**Severity: CRITICAL. Found independently by 2 dimensions (player-journey, walls).**

> ## ✅ SETTLED — 2026-08-09 (S113). **Read `docs/fk1-angelscript-settled.md`; it supersedes this entry.**
> Offline + one read-only RPM probe. **Zero launches consumed. The belief is REFUTED and the
> "accept the ceiling" verdict is FALSE.**
> - **Refuted in S101** (`tools/asdump`, which this entry still says needs deciding on — it shipped):
>   78 modules · **110 classes** · 1,463 functions · **100 %** of bytecode decoded.
> - ⚠ **This entry's own numbers and reasoning are wrong.** The undercount is **9.0× (81÷9)**, not
>   4.3× — S74's "18 `_AS` classes" is **9 classes × 2 token forms**, a double-count this correction
>   inherited. And the **"Surviving nuance" reuses the discredited inference**: the `_AS` suffix marks
>   only script classes shadowing a same-named native parent, so *"no `X_AS`"* proves **nothing** about
>   X. `memory/supervive-angelscript-layer` is phrased correctly; **this register entry is not**.
> - **The round mode IS native** (3 independent instruments, bidirectional controls) — conclusion
>   confirmed, reasoning struck. `LokiDropInGameMode` is a *referenced native base*
>   (`__StaticType_` count **0**), it is **not** a round mode, and "DropIn" ≠ drop phase.
>   ★ **But that is NOT a ceiling:** every member is a named UFUNCTION/UPROPERTY reachable by the S55
>   primitive, and **the phase lives on `ALokiGameState` with a public `AuthSetCurrentPhase` setter.**
>   The tutorial **already runs** the round mode (`BP_LokiGameMode_Tutorial_C`).
> - ★★ **The script layer is AOT-transpiled to C++ and compiled into the exe** ("StaticJIT"), not
>   interpreted: 1463/1463 cache Ids appear as registration-stub immediates (control 0/4000), and a
>   **1,459-row symbol table** was recovered. **Callable by the existing S55 recipe.** ⚠ **`Func !=
>   ProcessInternal`**, so §4.2 item 8's proposed experiment ("print every PI-dispatched UFunction")
>   returns **zero AS classes even when they are perfectly callable** — **it is a trap; negative
>   control only.**
> - ★★★ **The REAL wall, named for the first time: four server-authority C++ functions are EMPTY
>   STUBS** — `ALokiGameMode::SpawnPlayer` = `xor eax,eax; ret`, `AuthSetSpawnTeamLeader` = `ret`,
>   `SetDropLeader` = `ret`, `OverridePlaneLocations` = `ret` (likely `WITH_SERVER_CODE`-stripped).
>   This closes `AvatarActor = NULL`: the design routes the GAS bind through `SpawnPlayer`, and the
>   client does not contain it. **But the SCRIPT authority functions ARE compiled in and a direct
>   thunk call bypasses net routing** — so the deploy door is shut in C++ and possibly open in script.
> - **The usmap gap is CLOSED**: supplement shipped (`tools/asdump/out/usmap/mappings+as.usmap`),
>   **263 property values newly decoded** across 26 assets, base usmap round-trips bit-identically.
>   FK-14's "which usmap does the extractor load" is resolved: `tools/extractor/mappings.usmap`.
> - ⚠ **Live RPM correction:** AS **UClasses are NOT registered at the menu** (0 of 15 sampled, with
>   3 passing native controls); AS **enums and structs are**. Callability testing needs a loaded map.

| | |
|---|---|
| **Belief** | `docs/session-74-routeB-as-native-split.md`: *"★ THE KEY FINDING — only 18 classes are Angelscript"*; *"There is NO … deploy AS class"*; *"Deploy actors are native/BP too: ALokiDropPod*, Comp_PC_LokiRespawnComponent, AuthRequestRespawn, CheckSetInitialRespawn, GetPlayerRespawnComponent — none carry the `_AS` suffix"* → *"The native C++ deploy/round core is the irreducible blocker"* → *"C. Accept the ceiling."* Echoed in `memory/supervive-dedicated-server-status.md:619-642` and frozen into the git subject **"S74 Route B: Angelscript inventory — AS layer is thin, deploy/round is native."** |
| **Actual evidence** | A grep for the `*_AS` class-name suffix. |
| **Why weaker** | The `_AS` suffix only marks script classes that **extend a same-named native parent**; classes declared purely in script never carry it. Re-measuring the *same* 1,184,817-byte `PrecompiledScript.Cache` yields **78 distinct `.as` source modules and 81 `__StaticType_` UClass tokens** — a 4.3× undercount. Present by name: `GameMode/DropPhase/{LokiDropShip, LokiDropPod, LokiDropPodLaser, LokiDropPodImpactIndicator, LokiDropPhase_PlayerStateComponent}.as`, `FFA/{FFAGameMode, FFABotSpawner, LokiRespawnComponent, LokiPlayerRespawnComponent, Comp_PC_LokiRespawnComponent}.as`, `Items/{LokiGem, LokiTeamElimBoxComponent}.as`, `Vault/VaultItemSpawner.as`, `Barracuda/**` (27 modules). `AuthRequestRespawn_Implementation` is literally in the cache. A shipped source path even carries a developer typo (`Barracuda/Shop/BarraucdaShopFilterWidget.as`), confirming these are authored sources, not generated bind stubs. |
| **Steers** | The parked DS route; the "acquire the Server binary" framing of the whole DS domain; the *"accept the ceiling"* branch; every "the deploy is unreachable" verdict downstream. |
| **Surviving nuance** | There is still no `LokiRoundGameMode_AS` / `LokiDropInGameMode_AS`, so the **BR round gamemode** may genuinely be native. The drop-phase, respawn, elim-box, exotic-loot and FFA halves of the claim are dead. |
| **Cheapest experiment** | `python -c "re.findall(rb'[ -~]{6,}', open(PrecompiledScript.Cache,'rb').read())"`; count `__StaticType_` and `.as`. **Minutes.** Then decide whether an Angelscript bytecode disassembler is worth building (none exists in `tools/`). |

---

### FK-2 — "There is no legacy input path; what drives SUPERVIVE input is genuinely UNKNOWN"
**Severity: CRITICAL. Found independently by 4 dimensions (player-journey, instrument-blindness, unasked-questions, definition-of-done).**

> ## ✅ SETTLED — S104, 2026-07-26 → **`docs/fk2-input-settled.md`** + **`docs/input-map.csv`**
> **The belief is DEAD (certain).** The engine premise is factually false — in stock UE 5.4 those
> arrays carry **no `UPROPERTY` macro at all** (not `WITH_EDITORONLY_DATA`), so they ship and are
> simply invisible to reflection. There are **0 IMC/IA assets** in 107,123 files; the game ships
> **221 legacy `+ActionMappings` + 20 `+AxisMappings`** in `Loki/Config/DefaultInput.ini` while
> setting `DefaultPlayerInputClass=EnhancedPlayerInput` — **Enhanced CLASSES, LEGACY DATA**.
> Per-player table = `ULokiPlayerConfigManager` → 186 actions + 16 axes in `UserSettings.ini`.
> Movement is an **AXIS** (`Forward`/`Right`/`Up`), which is why action-only searches missed WASD.
>
> ⚠ **Do not round this up.** The table is proven to **EXIST** and the legacy consumer API proven
> **COMPILED IN** — it is **not yet proven to DRIVE live input** (retail: PROBABLE; our force-open
> state: UNSETTLED, and never actually asked). The decisive probe is §5 Step 3 of the settled doc.
> The FK-2 steer *"WASD is PARTIAL — velocity puppet only; stock input path dead"* is retracted as
> **untested**, not inverted — see §1.4 for why inverting it would be the more expensive mistake.
>
> **★ S114 ADDENDUM — 2026-08-12: a worked example of this ⚠ 's exact hazard, on `UPlayerInput`
> itself.** → `docs/fk13-console-exec-settled.md` §3A.
> `UPlayerInput::DebugExecBindings` is **config-loaded and never evaluated.** `Engine/Config/
> BaseInput.ini` ships exactly **16** `+DebugExecBindings`, `DefaultInput.ini`'s
> `[/Script/Engine.PlayerInput]` adds and removes none, and S80i measured `@+0x1A8 **Num=16**` **live**
> as its own positive control (`fk2-input-settled.md:477`) — an exact match, so **the config path
> provably works**. And **nothing reads the array.** Measured two independent ways: the
> `PlayerInput.cpp` wide-literal pool is intact and in exact stock source order with a **clean gap
> precisely where the `#if !UE_BUILD_SHIPPING` block's literals belong** (6 same-file controls
> present; `NoDebugExecBindings` and `KEYBINDING`, the only two literals unique to that block, both
> **0**); and region-scoped disassembly finds **0** TArray-shaped accesses at displacement `0x1A8`
> anywhere in the PlayerInput code region, against a control of **925** TArray-shaped pairs at 89
> other offsets in that same region. [M]
> ⇒ **A populated, live, correctly-parsed config array on this very class can still drive nothing.**
> That is exactly why FK-2's "proven to EXIST ≠ proven to DRIVE" hedge must not be rounded up; it
> **raises** the value of §5 Step 3 rather than answering it.
> ⚠ **Do NOT transfer this negative.** `ActionMappings`/`AxisMappings` live on
> `ULokiPlayerConfigManager`, are a **different array with a different consumer**, and were not
> measured here. Generalising from one array on `UPlayerInput` to the input path is the same move
> that produced FK-2 in the first place. [I]

| | |
|---|---|
| **Belief** | `docs/session-79-moonshot-plan.md:688-690`: *"legacy `UPlayerInput::ActionMappings`/`AxisMappings` are **ABSENT from the class entirely** (UE5 moved them behind WITH_EDITORONLY_DATA → stripped from shipping). ⇒ there is no legacy input path, so SUPERVIVE MUST drive Enhanced Input from IMCs — which means the IMC assets DO exist somewhere and the searches above simply failed to find them."* Retracted twice (S80n/S80o) and closed at *"UNRESOLVED … the answer must come from a MEASUREMENT."* |
| **Actual evidence** | A live RPM property walk of `UPlayerInput` — an instrument that can only see UPROPERTYs on the class it walks. |
| **Why weaker** | The measurement is **correct about `UPlayerInput`** and generalized to the concept. The bindings live on a *different, bespoke Loki class*. `schema.txt:41004` — the project's own extracted schema — declares `PlayerConfigManager : UClass:Object (17 props)` with `ActionMappings`, `AxisMappings`, `InputConfigVersion`, `OnActionBindingUpdated`, `OnActionBindingsReset`. And `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\UserSettings.ini` (21,877 B, rewritten every launch) holds **exactly 186 `ActionMappings=` and 16 `AxisMappings=`** under `[/Script/Loki.PlayerConfigManager]`, in legacy `ActionName→Key` form, with `InputConfigVersion=13`. Named verbs include `Forward`(W/S), `Right`(A/D), `Up`(Space/LCtrl), `MouseX`/`MouseY`, `SelectDropPodDestination`, `PassDropLeader`, `Launch / Eject`, `Recall`, `Glide`, `Sprint`, `Ping`, `PlaceSpray`, `Toggle Shop`, `OpenGlobalShop`, `UseInventory1-6`, `UseUtilitySlot1-2`, `UpgradeSpell_{Main,Secondary,Ultimate,Dash,DodgeRoll}`, `UpgradeEquipment{1,2,4,5,Boots}`, `ToggleScoreboard`, `Practice_Respawn`, `SpectateTeam1..20`, `EmoteWheel01-24`. |
| **Steers** | "WASD is PARTIAL — velocity puppet only; stock input path dead." The four-times-retracted Enhanced-Input thread. Every future keyboard-driven interaction. The in-match economy entry points (shop, inventory, upgrades) that the project has no owner for. |
| **Cheapest experiment** | Read the file. **Minutes.** Then resolve `LokiPlayerConfigManager` live and confirm the array is a real runtime field. |

---

### FK-3 — "`.rdata` is capped at 63.12% and that is STRUCTURAL — it genuinely caps the vtable-dump and string-xref techniques"
**Severity: CRITICAL. Found independently by 2 dimensions (false-knowns, walls).**

> ## ✅ SETTLED — S104, 2026-07-26 → **`docs/fk3-fk4-settled.md`**
> **The belief is DEAD (certain), and this entry's diagnosis was exactly right.** Re-measured
> independently: `.rdata` = 9,085 pages, **33 all-zero → 99.64% readable**. The "63.12%" counts
> non-zero bytes; the ~13.9 MB is null padding. Corroborated three ways — the nine dump manifests
> already said `100.0% READABLE`, `.rdata` entropy is 5.2–6.0 (vs 8.00 for `.text`/`.pdata`), and
> the June **live** `ULokiAssetManager` vtable capture reproduces **8/8 slots** from the cold dump.
>
> **Both techniques are revived and were run.** String-xref: 517,515 LEAs → 106,800 distinct
> `.rdata` targets, **55,473 / 85,677 UTF-16 strings resolved (64.7%)**. Vtables: **3,599 named,
> 5,061 / 5,077 classes, 773 in `/Script/Loki`** — validated 5/5 against live-captured pairs and by
> a 4,032-pair inheritance control (median **97.9%** shared slots). Total new named code:
> **32,066 reflection RVAs + 3,599 vtables** vs a prior ~617 (**~52×**), all offline.
>
> ⚠ **Do not round this up to "there is no cap."** The real cap is **`.text` demand-decrypt,
> 52.29%**, and **34.89% of `.text` (10,566 pages, 41 MB) has never been decrypted by any process
> we hold a record of.** It is NOT structural — it is monotone in what the game executes — so it
> lifts by *capturing runtime states*, not by more offline work. Priced in §8 of the new doc.
>
> **Two clauses survive, with sharper consequences than the entry gave them.** RTTI: **0 UE classes
> carry a type descriptor** (the 691 `.?AV`/`.?AU` names in `.data` are third-party EH residue —
> the one "UObject" is `icu_64::UObject`). Its real cost is not unnameable vtables but the **loss of
> the COL separator**, so vtables pack back-to-back (`ULokiAssetManager`'s is slot 799 of a 997-slot
> run) and no run-length threshold can find one. `.pdata`: in-image copy is 1,534/1,534 zero pages —
> but **B5 was right**, and 70 crash minidumps yielded **382,282 exact bounds** (13/13 ground truth).
>
> The cheapest-experiment line was correct and cost ~20 seconds.

| | |
|---|---|
| **Belief** | `docs/coverage-audit-s101.md:284`: *"`.rdata` union is capped at 63.12% and IS structural … ~13.9 MB of vtables, RTTI and string literals are permanently unreadable by RPM, which genuinely caps the vtable-dump and string-xref techniques."* |
| **Actual evidence** | One line of `dumps/merged.dump.exe.txt` reporting `.rdata 23488254 (63.1%)`. |
| **Why weaker** | That file's own footer says *"coverage counts NON-ZERO bytes, so a genuinely-zero readable byte reads as a gap here."* Measured independently twice: **33 of 9,085** `.rdata` 4 KB pages are entirely zero (0.36%), versus **6,961 of 16,384** for `.text` (42.5%, matching its reported 48.1%). The metric is sound for `.text` and wrong for `.rdata`; the 13.9 MB is null padding and zeroed slots. Corroborating and unquoted: **all nine** `dumps/*/…dump.txt` manifests report `.rdata … (100.0%)` READABLE. |
| **Steers** | Two techniques written off as dead in the audit's binary-RE section. |
| **Cheapest experiment** | Delete the line from the audit; run `usmapdump vtscan`/`strings` against the dump you already have. **Minutes.** |

---

### FK-4 — "The packer decrypts `.rdata` strings to the heap and leaves the module copy encrypted, so rip-relative string-xref is defeated"
**Severity: CRITICAL. Cost a session (S61) and closed a technique (S42, S85).**

> ## ✅ SETTLED — S104, 2026-07-26 → **`docs/fk3-fk4-settled.md`**
> **The belief is DEAD (certain).** All five probe strings re-read as **plaintext** at their
> recorded RVAs from `dumps/merged.dump.exe` with a stdlib slice and no project tooling. The
> searches were ASCII; the strings are UTF-16. Census: **111,932 ASCII + 87,851 UTF-16** — roughly
> **44% of this binary's string data was invisible to every scan run before S102.**
>
> **The technique works, at full efficiency.** 517,515 `lea r64,[rip+d32]` in `.text` → 245,894
> target `.rdata` → 106,800 distinct targets. UTF-16 exact-start resolution **49.3%**, which tracks
> the decrypted-page fraction (**52.29%**) to ~94% — i.e. essentially every UTF-16 string whose
> emitting code is decrypted IS xref'd. With interior + pointer-table refs: **64.7%**.
>
> **FK-4's origin is now measured, not guessed** — and it had TWO causes, which is why it held:
> (1) ASCII-only scanning, and (2) the **on-disk exe genuinely IS packed** — only **634 of 9,085**
> `.rdata` pages match the dump, so anyone scanning the shipped file got garbage and was right to.
> A true statement about one artifact was generalised into a false statement about the technique.
> The scope limit in this entry stands: the dump is a strict superset; re-scan the dump in UTF-16,
> do not go get the exe.
>
> ⚠ **Two traps this retirement leaves behind, both live.** (a) **0 refs ≠ absent.** The
> `feature toggles were not ready` RVA is **88 bytes INTO** a longer string — exact-start lookup
> says 0 sites, enclosing-string lookup says **4**, all in `ULokiGameFeatureToggles::Get @
> 0x55DB370`. The brief that commissioned the settlement repeated FK-4's own error shape here.
> (b) The very next scan written after this retraction resolved 732 / 1,258 UE class names because
> it was **ASCII-only** — FK-4 again, hours later. §9 of the new doc names the pattern
> (*Artifact-as-Axiom*) and gives the three-question check.

| | |
|---|---|
| **Belief** | `docs/session-42-step5:42-49`: *"this build's packer decrypts `.rdata` strings to the HEAP on use and leaves the module `.rdata` copy encrypted, so rip-relative LEA → string xref is defeated."* `docs/session-85-netcache-chain-diff.md:253`: *"packer-encrypted … zero module-range (.rdata) hits. Same VMProtect wall as the S61 login strings."* |
| **Actual evidence** | Live-memory string searches that returned zero module-range hits. |
| **Why weaker** | **The searches were ASCII; the strings are UTF-16.** The challenger located `Toc signature hash` (RVA 0x79E02D0), `feature toggles were not ready` (0x8B1C688), `GetFeatureTogglesReady` (0x8970FA0), `MulticastSetGameFeatureToggle` (0x8A56F38) and `Couldn't spawn player` (0x8077F9E) in on-disk `.rdata` — and read the **same RVAs back as byte-identical plaintext from `dumps/merged.dump.exe`**, an artifact the project has had since 2026-07-17. Section entropy confirms: `.text` 8.00, `.pdata` 8.00, `_RDATA` 8.00, but **`.rdata` 5.2–6.0** with ~70% of pages below 6.0 bits. |
| **Steers** | The whole "static analysis is packer-blocked" posture; the abandonment of string-xref as a localisation technique. |
| **Important scope limit** | The on-disk `.rdata` is **not** a new data source — the merged dump is a strict *superset* (67,473 vs 60,735 unique ≥16-char runs; 2,283 vs 2,280 `build-staging` paths). The actionable fix is *re-run your existing scans in UTF-16*, not *go get the exe from disk*. |
| **Cheapest experiment** | Re-run any prior "string is ABSENT" claim with a wide scan. **Minutes.** |

---

### FK-5 — "The BATTLE/PRACTICE blocker is an AccelByte QoS UDP ping responder"
**Severity: CRITICAL (points the roadmap at the wrong subsystem).**

> ## ✅ SETTLED — S105, 2026-07-27 → **`docs/fk5-battle-gate-settled.md`**
> **The named blocker is DEAD (certain), and this entry's own ⚠ Trap must be RETRACTED.**
> There is no AccelByte QoS on this path at all: `QosManagerServerUrl=` empty in all 12 environments,
> and the populated machinery is Theorycraft's `ULatencyManager` driving **UE's own ICMP-module UDP
> echo** against a host **we** advertise. Decisive, at instruction level: **no `ULatencyMeasurer` has
> ever been created** (`Creating new latency measurer` = `LatencyManager.cpp:315`, verbosity
> **Display**, i.e. it prints by default — **0 hits in all 14 Loki logs**), and the UDP-echo
> implementation `0x1F8CFC0` is a **100 % zero page**. Nothing ever asked for a QoS endpoint because
> nothing ever got that far.
>
> **⚠ The Trap row below is wrong.** The `/core-game/regions` experiment was **malformed**, so its
> negative carries no information: `PingHost`/`PingPort` are `FRegionRoute` fields *inside*
> `FRegionHost.Routes`, a `TMap` we never sent — of our 8 keys exactly **one** (`Port`) matches
> `FRegionHost` — **and** `CanExclude` defaults `false`, which `0x57DE016`
> (`cmp byte [region+0x24],0; je`) uses to skip the region *before* the route loop. Zero routes ⇒
> zero measurers ⇒ nothing to ping. Of the two "untried levers": `POST /latencies` is a **party
> member-state write**, not a QoS responder; `OnClientConfigUpdated` is **falsified** as a region
> source (it reads `coregamerouting` → two float thresholds; `FClientConfiguration`'s 12 props hold
> no region container).
>
> **★ The cheapest experiment is cheaper than this entry says — it costs ZERO backend change.**
> `bots` is **already served**, is **not** in the native `IsSpecialQueue` set
> (`{practice, customgame, dropin, tutorialNew, training}`, `fn 0x5854F5F`), and is unrestricted —
> so **BOTS → FIND MATCH dispatches into the real `UPartyManager::TryJoinQueue` today**. No account
> level is needed either: `CanControlQueue` loops `GetCurrentQueues` (**×25**), never `GetQueues`
> (**×0**), and its `GetLevelGameFeatureUnlocked` takes a hardcoded `GameFeature:Ranked` feeding an
> error-string format argument.
>
> ⚠ **Do not round this up into a replacement culprit.** "Not QoS" is **not** "the regions payload is
> the gate" — regions is the `??? — ms` display pipeline, and nothing measured puts it on the BATTLE
> path. **What blocks BATTLE past the tile is genuinely UNKNOWN**: `TryJoinQueue`'s implementation
> page `0x5875000` is 100 % zero in every dump we own, so its preconditions are unreadable offline.
> One BATTLE/BOTS click commits that page and makes it disassemblable.
>
> Also corrected: `coverage-audit:572`'s *"BATTLE **and PRACTICE** are degraded [by the queue trim]"*
> is half wrong — `practice` **is** served; PRACTICE is blocked at the same `TryStartSoloMode`
> `Party.State` gate the tutorial clears with a memory poke (`FParty` property 2 = `FString State`
> ⇒ offset `0x18`, now MEASURED from `Binds.Cache`, closing S61's open item).

| | |
|---|---|
| **Belief** | `docs/coverage-audit-s101.md:149` and `:572` — *"BATTLE/PRACTICE need an AccelByte QoS UDP ping responder"*, carried as "the named upstream blocker." |
| **Actual evidence** | An inference from an absence: *"no `qos` key in ServiceHostnames; client fetches zero QoS endpoints."* Its own source (`memory/supervive-tutorial-launch-status.md:65-68`) explicitly hedged *"AccelByte QoS … **OR** the ICMP module"* — the audit dropped the OR. |
| **Why weaker** | Three new measurements point elsewhere. (a) `QosManagerServerUrl=` is **EMPTY in all 12** AccelByte environment sections of the already-extracted `tools/extractor/out/DefaultEngine.ini`. (b) AccelByte `QosManager` has **exactly one** call-site string against **77–117** latency strings. (c) The populated machinery is Theorycraft's own `Services\CoreGame\LatencyManager.cpp` (`ULatencyMeasurer`, `GetFastestRegionMeasurer`, `"setting new latency, Host: %s, Region: %s, Route: %s"`, `RegionHostList`, `POST /latencies`, `ULatencyManager::OnClientConfigUpdated`) **plus UE's own `FNetPing` / `EPingType::{ICMP,UDPQoS}` / `net.NetPingTypes` / `ServerSetPingAddress`** — the last of which is *server-driven*, i.e. answerable by our own stub. |
| **Steers** | Roadmap item 2.3 and the "half the PLAY menu" gap; makes a cheap fix look like a protocol reimplementation. |
| **⚠ Trap** | The obvious remedy is already spent: `/core-game/regions` **was** served with `PingHost: 127.0.0.1` and the client never pinged. The **untried** levers are `POST /latencies` (0 hits, never served) and `OnClientConfigUpdated` (the region list may ride `ClientConfiguration`, which we already control). |
| **Cheapest experiment** | Restore the 10 queue ids behind a served account level, click BATTLE, and read `capture.log` + `Loki.log` for what the client asks for *next*. **Hours.** If it stalls before any QoS/latency call, QoS was never the first blocker. |

---

### FK-6 — "The cheat surface is definitively closed — bodies compiled out of shipping"
**Severity: HIGH (it gates the project's #1 blind spot: enemies, damage, abilities).**
**→ RE-GRADED MEDIUM. See the banner.**

> ## ⚠ SCOPE CORRECTION — S114, 2026-08-12. **This banner GOVERNS on the two specifics named below; everything else in the S105 settlement stands unchanged.** → `docs/fk13-console-exec-settled.md` §3D, `docs/fk13-routeb-shipped.md`
>
> - ★ **The "Console" bullet's `Exec = 0 of 500` is ANGELSCRIPT-ONLY — it was never a claim about
>   native UFunctions, and the native picture is the opposite.** **138 native UFunctions carry
>   `FUNC_Exec`** across 15 classes: `UCheatManager` **48**, `ALokiPlayerCheats` **25**,
>   `APlayerController` 13, `ALokiCharacter` 10, `ALokiPlayerController` 8, `AHUD` 6,
>   `UPlayerInput` 5, `ULokiClientPlayerCheats` 5, `ULokiTimelineManager` 5, `UGameViewportClient` 3,
>   … Decoded from UHT's `FFunctionParams` statics, layout calibrated against 4 ground-truth
>   functions, with the 3,703 candidates rejected by the `ObjectFlags@+0x34 == 0x45` test **reported,
>   not dropped**. [M] ⇒ **"FK-13 and FK-6 are independent" is now FALSE**: the exec channel is
>   precisely how the `UCheatManager` surface is reached.
> - ★★★★★ **This entry's own headline gap is CLOSED — and it closed for exactly the reason this
>   banner gave.** *"Nobody has tried to construct one in 101 sessions"* was true; S114 tried, and the
>   real closure really was the **CONSTRUCTOR**, not the bodies.
>   `APlayerController::CheatManager` (`+0x520`) was NULL in every measurement this project has ever
>   taken, while `CheatClass` (`+0x528`) was **already populated with the `UCheatManager` UClass in
>   BOTH the menu and the staged tutorial world** — only `AddCheats`'s body was stripped
>   (`UE_WITH_CHEAT_MANAGER = (1 && !UE_BUILD_SHIPPING)`, a plain `#define` with **no `Target.cs`
>   escape**). The new `RM_CHEATMGR` mode builds one via `UGameplayStatics::SpawnObject(CheatClass,
>   pc)` and stores it in the reflected UPROPERTY: **one heap qword, readback-verified, ZERO
>   module-image writes.** Proven **end-to-end** — `ExecuteConsoleCommand("LogLoc")` produced
>   `LogCheatManager: BugItGo 0.000000 …` in `Loki.log` against a **measured baseline of 0**, with
>   both format literals confirmed present in the image *before* the run (a pre-registered signal,
>   not a post-hoc grep). 69 min uptime, 0 crashpad handoffs. Byte-level grade of the 48:
>   **42 REAL / 3 FOLD / 3 COVERAGE-BLOCKED / 2 UNRESOLVED.** [M]
>   ⚠ **Do not read "42" as a correction of this entry's "39 REAL bodies"** — the denominators differ
>   (S114 graded the 48 `FUNC_Exec` members; S105's 39 was a different count). The two have never
>   been reconciled and nothing turns on it.
> - ⚠ **The `ALokiPlayerCheats` half is still SHUT, and for a different reason than the native
>   hotkey closure.** `ALokiPlayerController::ProcessConsoleExec` (vtable slot 81 / disp `0x288`,
>   RVA `0x569BE50`) **does** forward to the `LokiPlayerCheats` ObjectProperty at `PC+0xA30` —
>   routing measured offline and decisive — but that field is **NULL live** (read **by name** from
>   live reflection on `BP_LokiPlayerController_Dev_C` in the staged tutorial world), and
>   `AddLokiPlayerCheats` is an **empty fold**, now confirmed **live** as well as offline. The road is
>   built; nothing was ever constructed at the end of it. **OPEN: whether spawning that actor
>   ourselves reaches those 25 verbs has not been tried.** [M for both measurements; the reach
>   question is untested]
> - ⚠ **Two live facts that stop this being over-read.** Before the install there were **zero live
>   cheat objects of any kind** — `ALokiPlayerCheats`, `ALokiPlayerCheats_AS`,
>   `ULokiClientPlayerCheats`, `UCheatManager`, `UCheatManagerExtension` all **CDO=1, LIVE=0** — and
>   `ULokiGameInstance::LokiClientPlayerCheats` (`+0x298`, offset resolved by name) is **NULL at the
>   menu**, so its 5 REAL exec bodies have no instance to run on. [M]

> ## ✅ SETTLED — S105, 2026-07-27 → **`docs/fk6-cheat-surface-settled.md`**
> **One line: the cheat surface is PRESENT and NOT YET PROVEN CALLABLE.** Split four ways, because
> FK-6 bundled four surfaces:
> - **Native HOTKEY dispatch — CLOSED (certain), and now *strengthened* with a mechanism.**
>   `EnableHotkeyCheats_Impl 0x55D39B0` really writes `[this+0x390]`; `AreHotkeyCheatsEnabled`
>   (`0x0F7EB60` = `xor al,al; ret`) never reads it. Both BP exec-gates (`0x1F67DF0` =
>   `mov byte [rdx],1; ret`) always take the `Hidden` pin. The adjudication was right.
> - **Native `_Impl` bodies — PARTLY DEGRADED, MOSTLY UNMEASURABLE.** **31 of 65 (48%)** thunk pages
>   are all-zero in **all 10** dumps — *unread*, not stripped — and it is exactly the verbs
>   (`ServerCheatSpawnActor`, `CheatChangeHero`, `CheatTeleportLocation`, …). Of the 31 readable
>   natives, ≤12 real vs ≥18 degenerate. **S74's live `ServerCheatSpawnActor = ret` stands.**
> - **Angelscript family — OPEN AS CODE, UNPROVEN AS ANYTHING ELSE.** 51 bodies / 5,472 B, closing
>   exactly on the module header, **0 empty** (vs a 3.1% layer baseline). Never instantiated, never
>   invoked; `LokiPlayerCheats_AS` has never been observed alive — and both project enumerators are
>   *structurally blind* to it (`cheat_enum.py:175` gates `cn == "Class"`). ⚠ **Most of the family is
>   dead on arrival anyway**: every `AuthCheat*` opens on one of four ICF-folded accessors measured
>   `xor eax,eax; ret`. Survivors: `ServerSpawnWispAS`, `AuthCheatExecuteUAV`,
>   `AuthCheatUnlockFullArmory`, the 4 `AuthCheatBarracuda*`.
> - **Console — this entry's own claim is FALSE.** `Exec` = **0 of 500** AS UFUNCTIONs, so
>   "if the console works, every `ConsoleCommandCheat*` is reachable by typing" cannot be true;
>   the prefix is a naming convention. FK-13 and FK-6 are **independent**.
>
> **★ The real closure is the CONSTRUCTOR, not the bodies.** `APlayerController::AddCheats` (vtable
> slot 477) is `ret 0` in both PC vtables, and the observed `xor edx,edx` at slot 386 is the
> *`#else UE_BUILD_SHIPPING` branch* of stock UE 5.4's `EnableCheats` ⇒ **`UE_WITH_CHEAT_MANAGER == 0`**.
> A constructor strip is defeatable by a shim; a body strip would not be. And the biggest thing the
> belief hid: **`UCheatManager` ships 39 REAL bodies** — `Summon`, `Teleport`, `God`, `DamageTarget`,
> `DestroyAll`, `Slomo` — because its own bodies sit *outside* that guard. Nobody has tried to
> construct one in 101 sessions.
>
> ⚠ **Do not round this up.** "Intact bytecode" ≠ "callable" ≠ "effective". And do **not** re-publish
> the "219 native entries, not 65" re-parse — 219 is the `AActor`+`UObject` inheritance chain; S74's
> 65 is correct.
>
> **Re-graded MEDIUM:** FK-6 was HIGH *because* it gates enemies/damage/abilities. It does not.
> S103 measured the hero with **no ability system at all**, so a perfect enemy spawn still yields no
> damage; and a minion's ASC is self-owned, so damage is provable **today** with one `AdjustHealth`
> float on an ASC that already exists. §6 of the settled doc has the corrected plan.
>
> **Cheapest next step (~2 min, plain menu, no injection):** fix `cheat_enum.py:175`
> (`cn == "Class"` → `cn.endswith("Class")`), then `obj_by_class.py <PID> <BASE> _AS`. No `_AS`
> UClass of any kind ⇒ the script surface is unreachable and FK-6 closes for a *different* reason.

| | |
|---|---|
| **Belief** | `memory/supervive-cheat-surface-inventory.md:135-148`: *"★ DEFINITIVE CLOSE — THE CHEAT FUNCTION BODIES ARE COMPILED OUT OF SHIPPING (S74, disasm-verified)"*, resting on exactly two addresses — `AreHotkeyCheatsEnabled_Impl` = `xor al,al; ret` and `ServerCheatSpawnActor_Impl` = `ret` — generalized to *"the cheat surface as a shortcut to a playable hero is CLOSED"* and *"retroactively explains every no-op."* |
| **Actual evidence** | Two disassembled function bodies out of 65, plus S96's measurement that no live `LokiPlayerCheats` instance exists. |
| **Why weaker** | `PrecompiledScript.Cache` ships a **disjoint second cheat surface with `_Implementation` bodies**: `AuthCheatGrantGold`, `AuthCheatGrantGems`, `AuthCheatUnlockFullArmory`, `AuthCheatToggleHealthRegen/ManaRegen`, `AuthCheatExecuteUAV`, `AuthCheatBarracudaNextPhase/ToggleSpawnerType/AdvanceDayNightCycle`, `AuthCheatDayToNight/NightToDay`, `CheatSetTeamEliminated` (145 `Cheat` strings; source `PlayerController/LokiPlayerCheats.as`), plus **14 `ConsoleCommandCheat*` registrations**. Disjointness was verified: `AuthCheatChangeCharacter`, `ServerCheatChangeHero`, `CheatChangeHero`, `AreHotkeyCheatsEnabled`, `ServerCheatSpawnActor` are all **ABSENT** from the cache. So every cheat ever fired-and-observed-no-op was a *native* one, and the entire script family is untested. A `WITH_CHEATS` C++ guard cannot strip shipped bytecode. |
| **Steers** | Hero spawn, gold/gem economy, round-phase advance, day/night — all currently attributed to "server authority." |
| **⚠ Adjudicated disagreement** | The *input-action* variant of this claim (43 `Cheat*` ActionMappings in `UserSettings.ini`, ~20 key-bound) was **rejected** by the definition-of-done challenger: `AreHotkeyCheatsEnabled_Impl = xor al,al; ret` *is* the hotkey gate, and the interesting spawn actions (`CheatSpawnEnemyDummy/AlliedDummy/DesignatedSurvivor`) have `Key=None`. The native dispatch really is closed. What survives is (a) the **script** family above, and (b) the narrow fact that ~40 of the 43 `Cheat*` action names appear in *neither* the S74 65-function set *nor* the S79 137-input-event list, so their dispatch target is genuinely unlocated. |
| **Cheapest experiment** | Grep the AS bytecode for the `AuthCheat*` function table; separately feed each of the 65 native `_Impl` addresses to `usmapdump disasm` and count real bodies vs `ret` stubs. **Hours, offline.** |

---

### FK-7 — "The tutorial route is flaky — ~2 of 3 launches die on the first shim"
**Severity: HIGH (it invites retry-until-it-works instead of a fix, and it throttles every experiment).**

> ## CLOSED 2026-08-08 (S112) — **belief FALSE, cause MEASURED, fix SHIPPED.** -> `docs/s112-fk7-ab-results.md`
>
> **Do not re-open. Do not run another FK-7 sitting.** The banners below are HISTORY; where they
> conflict with this one, this one governs.
>
> **The cause was OUR OWN standing `.text` patch**, not the game. RM_PLAY installed a 5-byte jmp at
> `ProcessInternal` and held it for the whole 600 s run (`g_done` is never set in RM_PLAY).
> Pre-registered, one-variable A/B, arms alternating on ARMED WINDOWS:
>
> | condition | armed windows | died |
> |---|---:|---:|
> | standing `.text` patch | 10 | **10 (100 %)** |
> | no module-image write (heap `UFunction.Func` swap) | 36 | **3 (8 %)** |
>
> **Fisher's exact, two-sided: p = 0.00000007.**
>
> **SHIPPED**: `KFUNCSWAP`/`KFSNAME` now DEFAULT to the heap swap; the deployed
> `tutorial_launch_play.dll` (`.text 5151621d2154e454`) arms on **2 heap pointers** and writes no
> module image. Confirmed on the documented recipe path: 5/6 armed windows survived a full **600 s**
> with **no functional regression** (`[PL] init complete` + run/idle locomotion + zero `[GCW]`).
> Rollback `-Variant play-textpatch` (`433cf7d8f6a0770f`) **is** the measured control arm.
>
> **What this closure did NOT do**, stated so it is not over-read:
> - **28/28 dumps were `OURS/protector`; ZERO game-defect dumps.** A tutorial-specific game defect is
>   **unsupported** — and **unexcludable on this route**, because a shim-free tutorial run cannot
>   exist by construction (the map only opens because `fo` force-opens it). **8 % is our floor, not
>   the game's rate.**
> - The **camera family occurred 0 times in 41 launches**, which is NOT evidence `KXFORMFIX` worked
>   (effective denominator is the 21 armed windows; P(0) ~ 0.17 at the historical ~8 % rate).
> - **FK-24 is untouched** — the writer of the `0x01` byte is still unnamed.
>
> **What remained was split out** rather than left keeping a solved item open — see **FK-31**
> (staging hazard, now the dominant tutorial-route failure) and **FK-32** (the `0x0000DEAD`
> artifact-less residual), and `docs/fk31-fk32-successors.md`.
>
> **The S108 banner below is superseded on two specifics:** its mandated 3x `play_novtguard` control
> is **unusable** (it fires on an ~8 % event — see FK-33), and its `T+220-250 s` hold revision is
> void because `SecondsSinceStart` is the LAUNCH clock (anchor to `Load map complete` instead).

> ## ⛔ VERIFICATION ATTEMPTED 2026-08-04 (S108) — **THE SITTING WAS VOID. FK-7 STILL OPEN.**
> → `docs/s108-fk7-verification-attempt.md`. **Zero reproduce-then-repair runs still exist.**
>
> The **mandatory** `play_novtguard` positive control was run and **was QUIET**: no camera-family
> crash, no `[VTG]` line, and the session ran clean **through** the historic T+173…194 s window. By
> §0's own governing rule that makes the sitting **VOID, not a pass**, so Runs 3–4 (`play`) were
> deliberately **not** run — running them would have manufactured a false pass. n=1 against a
> measured 1-in-3…1-in-2 base rate proves nothing; **≥3 controls** are needed before any `play` run
> is readable.
>
> **Three findings that change how the next sitting must be built:**
> - **★ The probe runs are NOT FK-7 evidence, in either direction.** They have their own mortality:
>   probe-carrying runs died at **50–80 s**, the probe-free control at **~290 s**. Dumps `166396E2`
>   and `FED1F952` are the *instrument* killing the host (FK-24 §2). Purge them from any FK-7 tally.
> - **⚠ The T+300 s hold target is PAST the kill horizon.** The control died at ~290 s, and §0 row 10
>   records the code-integrity kill at **~285 s**. Holding to T+300 s guarantees a death that is not
>   FK-7 and cannot be distinguished from one. **Revise the hold to T+220–250 s before executing.**
> - **`FlushAsyncLoading=5` with `LogChaosCloth=0`** — a pairing **absent from the 9-session corpus**,
>   which had `=5,=1` for all 4 crash logs and `=4,=0` for all 5 dumpless. The pairing is therefore
>   **not a law**, and any inference that used flush-count as a proxy for "the mesh build happened, so
>   the FK-7 antecedent existed" needs re-checking. `LogChaosCloth` is the better antecedent marker.
>
> **Did the vtguard prevent Family B, or was it not exercised?** Answered independently twice —
> from the dump (`docs/s108-crash-triage.md`) and from the quiet control — and the answer is
> **NOT EXERCISED**. No evidence either way. One dump could not have proven prevention regardless.
>
> Run-budget correction: only **~2 of 4** launches reach the armed window at all. Budget on
> *armed windows reached*, never on launches.

> ## ✅ SETTLED 2026-07-27 (S106) — belief CONFIRMED FALSE. Full write-up: **`docs/fk7-crash-settled.md`**
>
> The entry below is preserved as written. **Its prediction held, its diagnosis did not.**
>
> **Settled:** the crashes are deterministic. 68% of chained crashes in the 86-dump corpus are exact
> repeats of another crash (73 chained → **34 distinct chains**). All 10 crashes in the FK-7 window sit
> in a 28-second band (173–201 s) across **two** stack families, both **shim-caused**:
> - **Family A (worker):** use-after-free on a GC'd `UAnimationAsset` in
>   `FAnimSync::TickAssetPlayerInstances` — `LoadAsset_Blocking` returns a raw `UObject*` and there is
>   no `AddToRoot` anywhere in `tutorial_launch.cpp`.
> - **Family B (GameThread):** `PlayerCameraManager->ViewTarget.Target` (`APlayerCameraManager+0x420`)
>   has its **low byte overwritten with `0x01`**; the per-frame camera tick then dispatches
>   `Target->CalcCamera` through it. Target positively identified as **the shim's own spawned camera
>   actor** via the shim-private constant triple `KCAMPITCH -66.0 / -90.0 / 0.0` recovered from
>   `ViewTarget.POV.Rotation` in crash memory.
>
> **Corrections to the row below, all MEASURED:**
> - ❌ **"an ordinary null-field deref"** — WRONG for both families. Family B is a *single-byte pointer
>   corruption* (bytes 1–7 are byte-identical to the live object); Family A is a *genuine UAF* through
>   a destructed object. `rax==0` at the fault is the *consequence* of reading a vtable out of zero
>   padding, not a null field.
> - ❌ **"GameThread ×2"** — the 4 GameThread crashes are **two different bugs**: `3c5dc52` (fault
>   operand `0x700`, POV never computed) and `12c7e2d` (operand `0xFFFF…`/`0x1000040`, POV live and
>   shim-written). Pooling them hid the split.
> - ⚠ **"Cheapest experiment: one session"** — correct, and it worked. But it was **not sufficient**:
>   the corpus explains **at most half** the observed rate. 5 of 9 tutorial sessions died with **no
>   exit marker, no `ExceptionHandler`, and no dump**, 3 of them past the crash band. That second
>   failure mode remains **OPEN** and is untouched by both fixes.
> - ⚠ The `coverage-audit-s101.md` citation in the row below is **line 252**, not 230.
>
> **Fixes:** `KVTGUARD` (camera) + `KGCROOT` (anim), both **written and compiled**, **neither
> live-verified**. `KGCROOT`'s causal premise is itself unconfirmed — no GC event is observable
> anywhere (`LogGarbage` appears in **zero** log files) and the anim trigger is the shim's own
> `KAUTOWALKATMS=20000` timer. **FK-7 is at best HALF closed.**
>
> ⚠ **Three DLLs on disk are A/B traps** — see `fk7-crash-settled.md` §5.7 / Step 0 before any run.

> ## ⛔ CLOSURE DECISION 2026-07-29 (S106e): **the BELIEF is closed; the FIX is OPEN — DO NOT CLOSE FK-7.**
> Governing section: **`docs/fk7-crash-settled.md` §0** (it overrides §1.3 and §8 wherever they disagree).
> Two adversarial hunts + one hardening pass + one closure skeptic. **Zero live runs of any fix exist.**
>
> **What moved:**
> - **Blocker 2 (the 5 dumpless deaths) — REMOVED. ❌ The *"second failure mode, ~half the rate"* claim is
>   RETRACTED as a denominator error.** 3 of 5 ran **RM_SPAWNPOSSESS to completion** (recovered via
>   `git show <commit>:docs/tutorial-launch-marker.txt`), shut down 3–9 s before the commit carrying their
>   own marker; 2 died **before** the mesh-build antecedent. **Four shim-free positive controls** show the
>   same zero-exit-marker tail. **RM_PLAY's real rate is 4 launches / 4 crashes.** The integrity-check
>   confound is **refuted** as an explanation (patch uptime 60–79 s vs ~285 s kill latency; its signature is
>   a *dump* at poison RIP `0x7FF90E000001`) and re-scoped to a hazard for the T+300 s hold only.
> - **Blocker 3 (artifact footguns) — REMOVED.** 6 single-variable DLLs, **6 distinct `.text` hashes**,
>   imports KERNEL32+USER32 only, 0 C++ EH; the self-A/B pair deleted, the stale `play` regenerated, the
>   two-variable `nogcroot` fixed. `s_tries` latch **fixed** (`g_vtTries` file-scope + reset).
> - **Blocker 1 (the writer) — NARROWED, NOT REMOVED → SPLIT OUT as FK-24.** Candidate (b) (heap overrun)
>   **falsified structurally**; the `+0x3F` delta **cannot discriminate** (allocator-forced, 3/3, including
>   the clean control); candidate (a) survives **unnamed**. Needs a live DR watchpoint.
> - **★ NEW BLOCKER, and why closure is refused:** the camera bug is **CONDITIONAL** (~1-in-3 to 1-in-2 per
>   launch — ANIM sessions passed *through* the window at 194–201 s), **and the 4 camera dumps span 3 build
>   vintages, none of them the candidate's** (the sub-family split correlates perfectly with commit
>   `a8d23f2`). ⇒ it is not yet known that the candidate build reproduces FK-7 ⇒ **the `novtguard` positive
>   control is mandatory**, and a quiet run without the guard's own `[VTG] INVALID` line is **VOID, not a
>   pass.** Ordered 4-launch sitting with a stop rule: **§0.5**.
> - **Also fixed en route (root-cause-grade):** the spawn `FTransform` was truncated at `Scale3D.Z`
>   (`xfsz=0x50`), so **every** actor `SpawnActorCls` produced spawned at `(x,y,0)` — *including the camera
>   that becomes `ViewTarget.Target`* — and `BuildHeroBody`'s saved transform made **registration re-apply
>   `Scale.Z=0`**, undoing the S98 fix. Now behind `KXFORMFIX`. `KTESTACTOR` (a leftover S94 diagnostic
>   building a **second, degenerate** skeletal body) flipped to **0**.
> - **Split out:** **FK-24** (the writer + its DR-watchpoint probe) and **FK-25** (the marker file's
>   `CREATE_ALWAYS` truncation — the instrument that manufactured the Blocker-2 error).

| | |
|---|---|
| **Belief** | Phrased as a *rate* in 7 places (`coverage-audit-s101.md:230`, `next-session-prompt-s91/92/94/99`, `session-93-objectives-camera-deploy.md:131`, `tutorial-playability-plan.md:413`, `memory/supervive-tutorial-launch-status.md:904`) — always "budget retries," never a stack. |
| **Actual evidence** | Observation of a failure *rate*. No crash was ever opened. |
| **Why weaker** | The 2026-07-26 crashes produce **byte-identical SUPERVIVE RVA chains across separate launches**: GameThread `1153803 7555f4e 3c5dc52 3c5d255 3c34b22 3c596b3 39c7884 37f8b8c` (×2, both AV reading **0x700**, at 173 s and 175 s) and worker-thread `1153803 755524e 3495973 3405f13 3691a72 3691704 367b462 f84697` (×3, on two different pool threads). Identical frames across independent launches is not stochastic. Faulting addresses are 0x700 / 0x44 / 0x0 — small offsets from NULL, an ordinary null-field deref, **not** the "messy poison-jump" anti-tamper signature. |
| **Steers** | Every >3-minute in-world experiment: GAS grant, combat, lesson chain 6-30, second-map load. |
| **Cheapest experiment** | Take those 8 RVAs into `dumps/merged.dump.exe` and disassemble. **One session.** The `+0x700` offset identifies the field. |

---

### FK-8 — "`SecondsSinceStart` is always 30 (Sentry captures at a fixed point)"
**Severity: HIGH — this one line closed the richest diagnostic corpus in the project for 60+ sessions.**

> ## ✅ CLOSED — 2026-08-05 (S111), with a POSITIVE CONTROL. Full mining pass: `docs/fk8-crash-timing-mined.md`.
> **The row below is preserved. Its numbers are superseded; its diagnosis was right.**
>
> **Closed properly, not by counterexample.** "The values differ" only shows the field is not constant.
> The field is a genuine per-run elapsed measure, proven by a **permutation control**: within a sitting
> a run cannot outlast the wall-clock gap since the previous crash. Observed violations **0 / 56**;
> permuted mean **8.56** over 20,000 shuffles; **P(0) = 0/20000**. Corroborated cross-class — the log's
> own first→last span equals the reported seconds to **<1 s** in both artifact classes.
>
> **Restated on today's tree (N=92 UECC dirs, all parsed):** `==0` **15** (was 12), `13–107` **43**
> (identical set), `173–288` **20** (was 19), `654–952` **7**, `>952` **6**; **exactly-30 still 5.**
> True corpus size is **114 distinct death records** (92 UECC + 22 distinct crashpad reports — the
> crashpad class writes no XML and every prior census was blind to it), **97 timing-usable**.
>
> **★ The belief had a real generator, and that is the lesson.** 3 of the 5 thirties are the *same*
> deterministic crash (`FAsyncLoadingThread`, chain `fe1746 2b8e7c5 2b8ebe8`, fault `0x1E3010020`, all
> 2026-07-01, all menu-login). S39 saw one reproducible signature twice and generalised it into a
> property of the field. **A textbook instance of `supervive-instrument-artifact-pattern`, and the
> cheapest one in the record to have caught.**
>
> **⚠ What closing it revealed is worth more than the closure.** The corpus is **conditioned on a
> death AND on an artifact being written**, and **≥36 of 114 (31.6 %) are self-inflicted**: 24 are the
> anti-tamper protector (`RIP == runtime.dll base + 1`, EXECUTE) and up to 15 are **our own
> always-injected `catalog_store_fix.dll`** faulting at `.text` RVA `0x205d` — identified to the byte
> via a 40-byte code-window match plus exception-time registers (`Rax = SUPERVIVE+0x8831758` ==
> `kCatMgrVtRva`, `R14 = kernel32!VirtualQuery`). **All 22 crashpad reports are in those two classes,
> so the entire S109/S110 tutorial campaign produced ZERO game-attributable deaths.** Two further
> mechanisms nobody had named: **7 shutdown-path crashes** (`is_requesting_exit == true`, set-identical
> 7/7 to the `+0x107d500` cluster — verified independently in-session) and **6 GameThread hangs**
> (`is_stuck == true`). The "game-attributable" residual is ≤62 and is a *residual*, not a measurement.
>
> **Also killed here:** the "~285 s integrity kill" (it is a 240–295 s mode, median **264 s**, 4/15
> asserts) and the FK-7 **"ANIM family"** name — `0x3495973` and `0x349596d` are the **same** function
> `0x3494B40`, ~~the ~~tick task-graph dispatcher~~ [RETRACTED — it IS animation code]~~ **[RETRACTED — it IS animation code]** (`"Ticking Group [%s] GroupLeader [%d]"`), confirmed  
> ⚠ **RETRACTED 2026-08-07 — the "ANIM family" name was CORRECT.** The S111 claim that `0x3494B40` is "the tick task-graph dispatcher, not animation code" quoted 2 of its 4 literals and dropped `"[PreviousMarker %s, NextMarker %s]"` (×2), which is unambiguously **animation marker sync**; "Ticking Group/GroupLeader/Leader" are anim **sync-group** terms. S106's `FAnimSync::TickAssetPlayerInstances` stands. Only this survives: `0x3495973` and `0x349596d` are the SAME function `0x3494B40` (one member, not two). See `docs/fk7-crash-settled.md` §S111-corrections item 1.
> in-session with `tools/strxref` against an EXACT `.pdata` extent. It was never animation code.
>
> **⚠ SCOPE:** every number above describes deaths that **left an artifact**. The artifact-less class
> (§5.3 of the write-up) is real, unquantified, and perishable.
> **Corpus regenerator:** `python tools/crashtri/fk8_corpus.py` → `docs/fk8-crash-corpus.{csv,json}`.

| | |
|---|---|
| **Belief** | `docs/session-39-menu-crash.txt:82`: *"SecondsSinceStart: 30 (Sentry captures this at fixed point — always 30)."* |
| **Actual evidence** | One crash. |
| **Why weaker** | Across all 86 `CrashContext.runtime-xml`: **exactly 5 are 30.** Distribution: 0 (×12), 13–107 (×43), **173–288 (×19)**, 654–952 (×6), then 3216 / 3334 / 3983 / 8403 / 42387. The 173–201 s cluster — the deterministic crash of FK-7 — has been measurable on disk since 2026-06-25. |
| **Steers** | Nobody mined crash timing; the "~3–5 min integrity check" window has been argued about for 60 sessions against data already in hand. |
| **Cheapest experiment** | One python pass over the 86 XMLs. **Minutes.** |

---

### FK-9 — "SUPERVIVE routes crashes through Sentry; no UECC minidump is written"
**Severity: HIGH (same consequence as FK-8: it suppressed all crash forensics).**

> ## ✅ CAPTURE SOLVED — 2026-08-04 (S109). **The "~3 minute" retention window is RETRACTED.**
> Full write-up: `docs/s109-fk9-capture-durable.md`.
>
> The S108 banner below is right that crashpad writes a dump and that the census is blind to it.
> Its *timescale* is wrong, and the wrongness mattered: it made the problem look like a race and
> pointed at a filesystem watcher. **MEASURED from crashpad's own bookkeeping** (`settings.dat`
> `Settings::Data` + the `metadata` report record — 56-byte layout, pinned independently by
> `id_index = 41` == the first string's byte length): crashpad made **exactly one** upload attempt at
> **crash + 2 s**, `upload_attempts = 1`, and the report then sat **untouched for 65+ minutes**.
> Nothing can touch it in between — `crashpad_handler.exe` is a child of the game and dies with it
> (MEASURED: 0 handler processes while `ags` was still alive).
>
> ⚠ **Two hedges added after adversarial review (S109 skeptic, T5):** `state = 2 ⇒ Pending` is
> **UNVERIFIED for this build** — `Completed` is at least as likely, so do not build on the enum; and
> **"the next launch clears it" is INFERRED, not proven.** It is consistent 5-for-5 across the day's
> sessions (the only surviving report is the only one with no relaunch after it), but a delayed
> successful upload explains the four cleared reports equally well, because **the clearing event has
> never been observed in the act**. The shipped fix does not depend on the answer: the archiver is
> `Copy-Item`-only, so a wrong rule costs *yield*, never an original and never a launch.
>
> **The "~3 minutes" was the gap between the skeptic's two `ls` calls, and a relaunch (02:19:58) fell
> inside it.** The observation interval was recorded as the phenomenon's timescale — a ninth instance
> of the instrument-artifact pattern, in a new shape: the artifact was a *number*, not an absence.
>
> **Fix (shipped):** `configs/archive-crashdumps.ps1`, called by `launch-redirect.ps1` **before** the
> launch (the launch being the destroyer) and **after** the game exits. SHA-256-verified, never
> deletes the source. There is no race to win, so there is no watcher. Positive controls 7/7.
>
> ⚠ **Residual blind spot, declared:** this depends on the upload *failing*. Uploads are enabled
> (`options` bit 0 = 1) and `o566896.ingest.sentry.io` is reachable (TCP 443 → 34.160.81.0); why the
> attempt fails is **not established**. If one ever succeeds the report dies ~2 s after the crash and
> **no sweep or watcher can catch it**. The archiver therefore warns loudly when `Loki.log` shows a
> crashpad handoff but no report exists, and names the fix (hosts-block the DSN host).
>
> ⚠ **Two grep traps**, each of which silently corrupts a census: the key
> `handing control over to crashpad` is **NOT the last line** (two `LogTemp` lines follow it in the
> one death that has a preserved dump), so never classify with `tail`; and bare `crashpad` matches
> two **startup** lines present in every session including clean exits.
>
> ## ⚠ PARTLY REHABILITATED — 2026-08-04 (S108). **The refutation below over-corrected.**
> The original belief was refuted with *"86 UECC directories exist"* — true, and the refutation
> stands for the crashes that produce them. But S108 measured the other half, and the belief had a
> real kernel that the swing past it discarded:
>
> **Some crashes genuinely route through Sentry's crashpad and create NO `UECC-*` directory at all.**
> MEASURED across 5 tutorial deaths: the `Loki.log` tail ends at
> `LogSentrySdk: handing control over to crashpad` with **no `[Callstack]` frames, no
> `RequestExit` line, and nothing new under `Saved\Crashes`**. The discriminator is clean and
> **anti-correlated 6/6**: `handing control over to crashpad` ⇔ no `UECC-*` dir.
>
> **★ And crashpad DOES write a minidump — it just deletes it.** Caught live: a **43,893,392-byte**
> minidump plus its `Loki.log` sitting in the crashpad database, **gone ~3 minutes later** (uploaded,
> then purged). So *"no dump was written"* and *"no dump exists now"* are different claims, and the
> census instrument (`harvest.py` and every hand-rolled `Get-ChildItem Saved\Crashes`) can only see
> the second.
>
> **Consequence, and it is load-bearing for FK-7/FK-24:** every statement of the form *"N of 87
> dumps show X"* has a denominator that **structurally excludes this entire failure mode**. To get
> the frames from such a death you must **copy the crashpad database aside within ~60 s**. S108 lost
> one that way and has no named frames for it.
>
> This is the FK-4 shape again — a true statement about **one artifact class** (the UECC tree)
> generalised into a statement about **the technique** (crash forensics).

| | |
|---|---|
| **Belief** | `docs/session-43-scan-on-browse.txt:65` and `session-44:82` — *"SUPERVIVE routes crashes through Sentry (no UECC minidump written)."* |
| **Actual evidence** | One crash class in one window. `docs/session-45:33` **already scoped it correctly** (*"Saved\Crashes is from the DS D3D12/RHI path"*) — the over-generalized version is what propagated. |
| **Why weaker** | **86 UECC directories exist**, spanning 2026-06-25 → 2026-07-26, including 9 dated 2026-07-26 (the newest tutorial runs) and 8 inside the S43 window itself. |
| **Steers** | All crash forensics on the current route. |
| **Cheapest experiment** | `ls Saved/Crashes | wc -l`. **Seconds.** |

---

### FK-10 — "`runtime.dll` is packed" / "the packer is VMProtect/Themida"
**Severity: HIGH (every risk judgement about injection rests on the wrong product's documented behaviour).**

> ## ✅ SETTLED — 2026-08-09 (S113). **Read `docs/fk10-protector-identified.md`; it supersedes this entry.**
> Offline, read-only, **zero launches consumed**. Both halves of the belief are wrong, and the
> "cheapest experiment" below was run and over-delivered.
>
> - **The vendor name is REFUTED six independent ways.** Decisive: `runtime.dll` @ file offset
>   `0x007C1BEC` holds `/api/5710262/minidump/?sentry_client=`**`packer/3.3.1`**`&sentry_key=149a7ac2…`
>   — **the same Sentry org, project and key as the game's own DSN**, differing only in
>   `sentry_client`. A commercial packer does not embed the customer's private DSN. Also: our own
>   `deobfimports` resolves **1107/1107 stubs, 0 undecodable**, with an emulator that has **no
>   conditional branches, no `CALL`, no flags** — a virtualized VMProtect stub would resolve *zero*.
>   The internal product name is literally **"Packer"** (`Packer/1.0` User-Agent at `0x7C2F90`).
>   ⚠ **Do not substitute a second vendor name.** Correct label: *bespoke protector, self-identifies
>   as `packer/3.3.1`, vendor unidentified.*
> - **★ "`runtime.dll` is packed" is REFUTED: 46.6 MB of its code is PLAINTEXT x86-64 and is
>   disassemblable offline today** (4 controlled tests: 0.00 % invalid bytes on linear sweep vs
>   5.25 % for known-ciphertext controls; 10,824/10,824 unique 4 KiB blocks; 7,190 prologues vs 7,197
>   table functions). It is *obfuscated* (MBA), not packed. Use the loader table at RVA `0x14D8758`
>   (18,580 fns) — the `.pdata` **section** is vestigial.
> - **"~48 MB at entropy 5.3–6.6"** = an exact subtotal of the four appended sections
>   (`packer30+40+31+42` = 48,133,632 B, H 5.36–6.57). The file is **67,511,496 B** and 19.3 MB of it
>   (`packer0`, `packer1`, `.rsrc`) **is** encrypted. **"22,248-byte `.pdata`"** is the vestigial
>   table's VirtualSize.
> - **C7's "preloader.dll, ntdll-only imports" is REFUTED** — 52 imports across ntdll (43), USER32
>   (8), GDI32 (1). **C5's "not even enumerable as a module" is the wrong half** — manually mapped,
>   but `SEC_IMAGE` file-backed and therefore nameable. **C14's `.rsrc` = 9.62 MB** is
>   `.rsrc`+`.reloc`; contents now enumerated (no *plaintext* embedded PE; a driver inside 9.2 MB of
>   ciphertext is **not** excluded).
> - **Two BOM components the entry missed:** an embedded printf, and **Intel ISA-L Crypto** — a third
>   hashing engine offering **multi-buffer SHA/MD5**, which became the successor lead for Wall #7.
> - **Bonus: FK-32 CLOSED on mechanism.** `runtime.dll` RVA `0x80f7f0` =
>   `mov edx,0xDEAD; syscall` ⇒ **`NtTerminateProcess(h, 0xDEAD)`**. The protector kills the process
>   deliberately. `preloader.dll` eliminated as the killer (control-backed).

| | |
|---|---|
| **Belief** | `CLAUDE.md`: *"Its imports are VMProtect/Themida-PROTECTED."* `coverage-audit-s101.md:286` lists `runtime.dll` under *"anti-knowledge — never touched: characterized as packed but never disassembled."* |
| **Actual evidence** | A *shape* inference from the IAT stub pattern (`real = C2 ^ ROL64(C1 + M, 0x33)`) — never a vendor identification. `runtime.dll` was labelled from its name and loader position. |
| **Why weaker** | `Loki/Binaries/Win64/thirdpartylicenses.txt` (31,834 B, **0 hits repo-wide**) names the *actual* protection stack: **System Informer** (process/handle/driver enumeration), **MinHook** + **Hacker Disassembler Engine 64** (inline hooking — our own technique), **xxHash** + **constexpr-xxh3** + **Zstandard** (a named candidate for the integrity hash), **mbedtls** (its own TLS — bypasses `cacert.pem`), **tpm-tss** (TPM-backed identity), tiny-json, bscanf. `preloader.dll` is 26 KB, **Theorycraft-signed**, clang/LLD-built (`/work/preloader.pdb`), with `PACKER_CRASH_AT`, `Conflicting software detected!`, and explicit Wine/Proton refusal. `runtime.dll` self-identifies as **`packer/3.3.1`** in its Sentry client tag, has 11 sections (`packer0..packer42` + `.rwx`), **no export directory**, and ~48 MB at entropy 5.3–6.6 — *not encrypted*, including a plaintext 22,248-byte `.pdata`. |
| **Steers** | Anti-tamper strategy; interpretation of every unexplained process death; whether a technique is "safe." |
| **Note** | The operative *technical* claim (1107/1107 IAT slots resolved by `deobfimports`) is measured and correct. Only the **name** is false — but the name is what drives predictions. |
| **Cheapest experiment** | Read the licenses file and `preloader.dll`'s strings. **Minutes, offline.** |

---

### FK-11 — "Verbose/VeryVerbose are compiled out — this is a SHIPPING build"
**Severity: HIGH (it foreclosed the cheapest instrument the project could possibly own).**

> ## ✅ SETTLED — 2026-08-09 (S113). **Read `docs/fk11-log-verbosity-settled.md`; it supersedes this entry.**
> Offline, read-only, **zero launches consumed. The belief is FALSE** — not "true for some
> categories", and not even true for Loki code specifically.
> - **MEASURED three ways:** global `COMPILED_IN_MINIMUM_VERBOSITY` = **`VeryVerbose` (7)**;
>   `USE_LOGGING_IN_SHIPPING` = **1**; of **14,030** decoded `UE_LOG` call sites, **1,339 are Verbose
>   and 513 VeryVerbose** (a global cap at `Log` would have deleted all 1,852). Histogram over 665
>   cross-validated objects: **≥ Verbose = 98.0 %**; only 11 categories are capped below VeryVerbose,
>   each an individual Epic/plugin declaration matching Epic's published values (a control the method
>   could have failed).
> - ★ **109/109 Loki-dominant categories are `VeryVerbose`. Zero capped at `Log`.** 71 compiled-in
>   Verbose/VeryVerbose call sites inside `\Loki\Source\` across 35 categories.
> - ⚠⚠ **THIS ENTRY'S OWN "CHEAPEST EXPERIMENT" WOULD HAVE SILENTLY FAILED**, and the silence would
>   very likely have been recorded as *"confirmed: Verbose is compiled out"* — recreating the
>   false-known. Three independent reasons: **(a) `-LogCmds` does not parse in this binary** —
>   `logcmds` occurs 3× and all three are **help text** (`0x076B25E0`/`0x076B26B0`/`0x076B2860`), with
>   no standalone `LogCmds=` literal, while peer literals `LOG=`/`ABSLOG=`/`logcategoryfiles=`/
>   `NOCONSOLE` all exist; **(b)** 3 of its 4 named categories are Class-B/C — code paths that never
>   execute on any reachable route; **(c)** `LogNetSerialization` at VeryVerbose is catastrophically
>   spammy. **Use `[Core.Log]` via ini instead** — the binary states its precedence
>   (*compiled-in → ini → command line*) at `0x076B1FA0`, and stage three is missing, so **ini wins**.
> - ★ **The shipped `[Core.Log]` is ALREADY BINDING:** zero violations across a 4.10 GB / 28.7 M-line
>   corpus; `LogAccelByte` emits **3** lines while driving the entire backend flow. **The project has
>   been reading a log that was deliberately turned down.**
> - **"Steers" figure corrected:** silence is **760/903 (84.2 %)**, not "~825–870 of ~1,004" (that was
>   the wide *substring* count). `LogLokiSpawner` and `LogAbilitySystem` were wrongly listed as silent.
> - ⚠ **The real trap is NEVER-RAN vs SUPPRESSED**: 384 of 842 logs reach `LVL_Tutorial` but none
>   contains combat, drop phase, bots, damage, XP or replication. Only **Class A** categories (owner
>   provably ran, still silent) are pure suppression wins.
> - **Angelscript logging is silent by AUTHORSHIP, not gating** (6 calls in 4,963 syscalls, 0.12 %) —
>   raising verbosity cannot make script code talk. Downgrades FK-22.
>
> **★ S114 ADDENDUM — 2026-08-12.** Two corroborations and one **new trap shape**.
> → `docs/fk13-console-exec-settled.md` §3B, `docs/fk13-routeb-shipped.md` §6, §9.1.
> - **`-ExecCmds` is the SECOND UE command-line switch measured non-functional in this binary** —
>   **0** wide occurrences of `ExecCmds` in a **100 %-readable** `.rdata`, against five same-class
>   `FParse` switch literals that all resolve in the identical scan (`LogCmds` 3, `LOG=` 5,
>   `ABSLOG=` 2, `FORCELOGFLUSH` 2, `NOCONSOLE` 1), cross-checked against the on-disk shipped exe as
>   a second image. [M] ⇒ promote FK-11's one-off finding to a **standing rule: treat every UE
>   command-line switch as unverified until its literal is located in the image.** Note the two
>   switches fail for *different* reasons — `-LogCmds` has three hits that are all help text,
>   `-ExecCmds` has none at all — so "the string is present" is not the test either.
> - **The `-ini:`-is-applied-too-late half was independently re-confirmed** and is now the stated
>   reason a shipped shim prescribes the **USER `Engine.ini`** rather than the command line. It also
>   retires FK-13's own "cheapest experiment" — see that entry. [M]
> - ⚠ **A THIRD trap shape, beside NEVER-RAN and SUPPRESSED: SILENT BY AUTHORSHIP, at the verb
>   level.** `UCheatManager::God` **emits no log line at any verbosity**. It was the first choice for
>   verifying that the exec channel worked and would have produced an uninterpretable null — raising
>   verbosity cannot help, because there is no call site. The replacement is the pattern to copy:
>   pick a verb whose own output is a **pre-registered** literal (`LogLoc` → two
>   `UE_LOG(LogCheatManager, Log, …)` lines), confirm the format literals exist in the image
>   **before** the run, and record the **baseline count**. [M]
>   ★ Stated as a rule because it cost a false pass: **"the call returned ok" is never a success
>   criterion; only the verb's own output is.**

| | |
|---|---|
| **Belief** | `docs/next-session-prompt-s45.md:185`: *"Don't send `-LogCmds` expecting Verbose logs — this is a SHIPPING build; Verbose/VeryVerbose are compiled out."* |
| **Actual evidence** | A blanket assertion in a handoff note. `LogCmds` appears in 14–23 docs and **0 config files** — the flag has never been passed to the client, so the claim has never been exercised. |
| **Why weaker** | `Loki.log` contains `LogSentrySdk: Verbose:` lines (13 measured), proving `USE_LOGGING_IN_SHIPPING` is on and at least one category's compile-time verbosity exceeds `Log`. Stronger still: the **already-extracted** `tools/extractor/out/DefaultEngine.ini` ships a `[Core.Log]` block setting per-category verbosities (`LogNet=Warning`, `LogLokiGameplaySpellReplication=Log`, `LogLokiGameMode=Log`, `LogAccelByte=Warning`) — the exact runtime control the note declared impossible. And `Core.Log` / `LogCmds` both exist as wide strings in the merged dump. |
| **Steers** | ~825–870 of ~1,004 compiled-in log categories have never emitted a line, including `LogLokiGameplaySpell`, `LogLokiAbilitySystemComponent`, `LogGameplayEffects` (the GAS frontier), `LogNetSubObject`/`LogNetPartialBunch`/`LogNetSerialization` (the S88 subobject wall), `LogLokiDropPhase`/`LogLokiSpawner` (DropPlane), `LogLokiInventory`/`LogDamage`/`LogLokiXPManager`. |
| **Cheapest experiment** | Add `-LogCmds="LogLokiGameplaySpell Verbose, LogLokiAbilitySystemComponent Verbose, LogGameplayEffects Verbose, LogNetSubObject VeryVerbose"` to one launch and diff the category set. Fallback if the switch is filtered: append `[Core.Log]` to the user `Saved/Config/WindowsClient/Engine.ini`, which the launcher already proves is honoured. **Minutes.** |

---

### FK-12 — "Steam must be running first or login dies with Auth Failure 14005"
**Severity: MEDIUM-HIGH (it makes unattended/CI launches impossible and is N=1).**

| | |
|---|---|
| **Belief** | `docs/hero-roster-attempts.md:47`: *"Steam MUST be running first — otherwise SteamAPI init fails and login dies with Auth Failure 14005. **We lost 30 min chasing this before noticing.**"* Propagated verbatim to ~20 files and to CLAUDE.md as a gotcha to "surface." |
| **Actual evidence** | One incident, diagnosed by correlation ("before noticing"), never retested. No doc records a Steam-less launch, a second failure, or a controlled test. |
| **Why weaker** | `handlePlatformToken` never inspects or verifies the submitted platform token — it mints a JWT unconditionally. So *if* 14005 is a client-side `SteamAPI_Init` failure rather than backend validation, the requirement may be evadable. |
| **Complication** | The SteamID64 finding (§8) partly inverts the value: if the ticket is the source of a *distinct identity*, you **want** Steam running for a second client with a second account. The sharper question becomes whether a hand-forged ticket with a different SteamID64 is accepted — which our IAM, validating nothing, would trivially accept. |
| **Steers** | Unattended launches, CI-style shim regression runs, audit item 1.5. |
| **Cheapest experiment** | One launch with Steam closed; read `Loki.log`. **Minutes.** |

---

### FK-13 — "Binary scan confirmed the dev console is fully stripped"
**Severity: MEDIUM-HIGH (it is the founding justification for the injection-only architecture).**

> ## ✅ SETTLED — S114, 2026-08-12 → **`docs/fk13-console-exec-settled.md`**,
> ## **`docs/fk13-live-run-2026-08-12.md`**, **`docs/fk13-routeb-shipped.md`**
>
> **The OUTCOME was right and every REASON was wrong — and the operational conclusion is FALSE.**
>
> - ✅ **The console really is gone.** `ALLOW_CONSOLE == 0`, by three independent instruments:
>   `UGameViewportClient::Init` (RVA `0x0384FB00`, 1810 B, decrypted) writes both neighbouring stock
>   members but has **zero** reads of `UEngine::ConsoleClass` (+0x120) and **zero** stores to
>   `ViewportConsole` (+0x48); guard-exclusive `Console.cpp` literals score **8/8 controls vs 0/5
>   markers** in an image whose `.rdata` is **100 %** readable; and the `UEngine::Exec` literal pool's
>   gaps are exactly the compile-guarded verbs. ⇒ pressing `~` can **never** work and no config
>   changes that. `config-control-plane-s101.md` §5 levers #1/#4 are dead; its probes P1/P2/P4 are
>   answered offline. [M]
> - ❌ **…but NOT because the config knobs were stripped** (S101 already showed all four ship), and
>   ❌ **NOT because S3 scanned a packed binary** — S101's own explanation is also wrong: all six
>   overturned tokens are readable in the **shipped on-disk exe with a plain ASCII search**. The real
>   cause of S3's miss is unrecovered; do not propagate the packed-binary story. [M]
> - ❌❌ **"All cheap external paths are exhausted ⇒ injection only" is FALSE. This is the finding.**
>   FK-13 was **three independent compile flags**, not one (`TargetRules.cs:1368,1374,1429`):
>   `bUseLoggingInShipping` (default 0, **this build 1**), `bUseConsoleInShipping` (default 0,
>   **this build 0**), and `bUseExecCommandsInShipping` — whose stock default is **1**.
>   `UE_ALLOW_EXEC_COMMANDS == 1` here, so `UEngine::Exec` (`0x3ED66C0`, 2,521 B),
>   `CallFunctionByNameWithArguments` (`0x1343420`), `FSelfRegisteringExec` and the whole
>   IConsoleManager cvar channel are all compiled in, and **138 native UFunctions carry `FUNC_Exec`**.
>   ⚠ This **re-scopes FK-6, it does not contradict it**: FK-6's *"console Exec == 0/500"* was measured
>   over the **500 Angelscript** UFUNCTIONs and was never a claim about native ones. [M]
> - ★★★★★ **ROUTE B SHIPPED AND PROVEN END-TO-END.** `APlayerController::CheatManager` (+0x520) was
>   NULL in every measurement this project ever took, because `AddCheats` compiled out under
>   `UE_WITH_CHEAT_MANAGER = (1 && !UE_BUILD_SHIPPING)` — but `CheatClass` (+0x528) was **already
>   populated**. The new `RM_CHEATMGR` mode constructs a `UCheatManager` and stores it there:
>   **one heap qword, readback-verified, ZERO module-image writes.** Verified live by
>   `ExecuteConsoleCommand("LogLoc")` → `LogCheatManager: BugItGo 0.000000 …` in `Loki.log`
>   (baseline 0). **42 real exec verbs** now reachable. [M]
> - ✅ Also closed: the project had been driving this channel unknowingly since ~S91 — the force-open
>   shim *is* `ExecuteConsoleCommand("open LVL_Tutorial?game=…")`. S3's own goal was reachable all
>   along; the **delivery mechanism** was wrong, not the verb.
> - ❌ **DEAD, measured:** `DebugExecBindings` are config-loaded (exactly the 16 from `BaseInput.ini`)
>   but **never evaluated** (`#if !UE_BUILD_SHIPPING`; clean literal-pool gap + **0** TArray accesses at
>   `+0x1A8` in the PlayerInput region against a **925**-access control). `-ExecCmds` **does not parse**
>   (0 wide hits vs 5 same-class switch controls that all resolve) — the *second* non-functional UE
>   switch after `-LogCmds`. Loki's own debug menu is reflected but `Show/Hide/ToggleDebugMenu` are
>   **empty bodies**, and `ULokiBlueprintLibrary::CheatsEnabled` folds to `xor al,al; ret`. [M]
> - ⚠ **STILL OPEN:** `OPEN` is absent from `UEngine::Exec`'s literal pool yet `open` demonstrably
>   works, so its dispatch site is unidentified. And the 25 `ALokiPlayerCheats` verbs remain
>   unreachable — `ALokiPlayerController::ProcessConsoleExec` (`0x569BE50`) *does* forward to
>   `PC+0xA30`, but that field is NULL live and `AddLokiPlayerCheats` is an empty fold.
> - ★ **Reusable method born here:** *guard-exclusive marker strings* — `TEXT()` literals occurring
>   ONLY inside a `#if` region (verified across 24,864 UE source files), controlled by literals from
>   the **same translation unit** outside the guard. ⚠ The rule *"strings cannot decide
>   ALLOW_CONSOLE"* is true only of **UHT-emitted** names and FALSE of guard-exclusive literals —
>   recording it unqualified would foreclose a method that works.

| | |
|---|---|
| **Belief** | `docs/dedicated-server-stub.md:541-556`, with an explicit ABSENT list: `EnableCheats`, `-cheat`, `-cheats`, `ConsoleKey`, `ConsoleKeys`, `DebugExecBindings`, `ConsoleClass`, `allowcheats`, `/Script/Engine.Console`, `CheatManagerClass` → *"all cheap external paths are now exhausted; the remaining options require in-process code."* |
| **Actual evidence** | A Session-3 string scan of a binary that demand-decrypts `.text`, using a tool that had **no wide-string subcommand** (`usmapdump wstrings` was added 2026-06-28, *after* the scan). An ASCII-only scan of this image finds 94 `Log*` tokens where a wide scan finds 1,004 — a 10.7× blind spot in the exact instrument used. |
| **Why weaker** | Re-tested against `dumps/merged.dump.exe`: `ConsoleKey` ×2, `ConsoleKeys` ×1, `DebugExecBindings` ×1, `ConsoleClass` ×2, `EnableCheats` ×1 — **all five PRESENT**. (`allowcheats`, `/Script/Engine.Console`, `CheatManagerClass`, `ToggleConsole` remain 0, so the picture is mixed, not inverted.) Independent corroboration nobody joined up: `docs/session-79-moonshot-plan.md:688` measured `DebugExecBindings @+0x1A8 Num=16 **NON-empty**` live — the same symbol S3 declared absent. |
| **Steers** | The premise that in-process injection is the only control path. |
| **Cheapest experiment** | ~~Try `-ini:Engine:[/Script/Engine.PlayerInput]:+DebugExecBindings=…` on one launch.~~ ⚠⚠ **THIS PRESCRIPTION WAS WRONG TWICE AND WOULD HAVE PRODUCED A SILENT NULL RECORDED AS CONFIRMATION.** (1) `UPlayerInput` is `UCLASS(config=Input)`, so the base name is **`Input`**, not `Engine` — the section would never have been read. (2) FK-11 then MEASURED that the `-ini:` command-line form is applied **too late to bind** (it failed for `[Core.Log]` with a clean positive control, while the USER ini worked). And (3) even delivered correctly it changes nothing, because `DebugExecBindings` are **never evaluated** in this build. This is the FK-11 pattern exactly — a prescribed "cheap experiment" whose null is indistinguishable from "the feature is absent". **Superseded by the S114 work above; do not run it.** |

---

### FK-14 — "The usmap is wrong for REPLICATED CONTAINER types" (mis-scoped: it is non-deterministic across the board)
**Severity: MEDIUM-HIGH (it scopes a mitigation too narrowly).**

> ★★★★★ **SETTLED — S116, 2026-08-12/13. READ `docs/fk14-usmap-settled.md`; it governs over
> everything below.** Four parallel agents, offline + read-only RPM, zero launches.
> - ✅ **The 326 is REAL and reproduced to the digit** (326 / 219 container / 26 Loki-owned).
> - ❌ **"Non-deterministic" is REFUTED as a tool property** — three back-to-back extractions from one
>   live process are **byte-identical** [M]. Tool evolution is also excluded (the extraction path has
>   been frozen since `26c6302`, 2026-07-02, and two dumps **18 h apart from the identical binary**
>   disagree on **312**).
> - ★★ **ROOT CAUSE: a fixed offset bug.** `tools/usmapdump/extract.go:115` reads a container's inner
>   **inline at `FField+0x80`** — past the end of the object — so it captures **whatever FField the
>   allocator placed next. Adjacency is frozen within a process instance and differs across launches**,
>   which is why 3/3 runs matched and two sessions disagreed. (`ArrayProperty+0x80` is 99.8 %
>   pointer-ranged with only **39 distinct values** — it is literally the next FField's vtable.)
>   The `extract.go:164` owner guard is **inert** (`ownerHint = 0` at depth 0) *and* self-confirming.
> - ⚠⚠ **THE CORRECT OFFSETS ARE PER FAMILY — an earlier draft of this banner said `*(+0x78)` for all
>   containers and that was WRONG for 4 of 5.** Each 100 % with a **0 %** runner-up, two independent
>   instruments: `FArrayProperty::Inner` **`*(+0x78)`** · `FSetProperty::ElementProp` **`*(+0x70)`** ·
>   `FOptionalProperty::ValueProperty` **`*(+0x70)`** · `FMapProperty::KeyProp` **`*(+0x70)`** /
>   `ValueProp` **`*(+0x78)`** · `FEnumProperty::UnderlyingProp` **`*(+0x70)`** / `Enum` **`*(+0x78)`**.
>   The **96.6 % pooled figure is a MIXTURE** (Array 3,548 + Map-*value* 555 at `+0x78`; Set 142 +
>   Optional 2 + Map-*key* 555 at `+0x70`) — and a pooled calibration would clear any 90 % gate while
>   **silently making every `TMap` read its value as its key**. `sizeof(FProperty) == 0x70`; the layout
>   is essentially **stock**; the lone deviant is `FArrayProperty`'s **unidentified** 8-byte hole.
> - ★★★★★ **FIXED, VERIFIED AND SHIPPED (commit `1b6f9de`).** `extract.go` now **calibrates per family
>   per member at startup, prints the score table, and ABORTS** rather than emit a mis-typed usmap.
>   Seven defects fixed, not one (see the settlement doc §4). Pre-registered control arms, **OVERALL
>   PASS**: accuracy vs an independent oracle **29.9 % → 100.0 %**, `Map<Byte,Byte>` 555 → 0,
>   `Set<Byte>` 142 → 0, `EnumProperty` **0 → 1,813**, `ArrayDim != 1` 0 → 70; armF byte-identical
>   across 3 runs and 2 builds. ★ W78 and W70 corroborate armF **from opposite directions**
>   (Array 620/620; Map 160/160 + Set 19/19), proving **no single uniform offset can work**.
> - ★★ **Corpus regenerated** (68,490 assets, 0 errors, fixed base + AS supplement). Two findings the
>   settlement did not predict: **static arrays were truncated to element 0**, so *7 of 8 bone
>   influences per vertex were discarded in every skeletal mesh ever extracted* (`ArrayDim` hardcoded
>   to 1); and **scalar VALUES were not safe either** — 5,723 of 12,129 true scalars changed, garbage →
>   sane (`2.7e-44` denormals → real floats), because `SchemaIdx` renumbering made scalars *downstream
>   of a dropped enum* decode another property's bytes. Rollback: `dumps/extractor-out-PREFIX14/`.
> - ⚠ **OPEN — the `Name[n]` fingerprint hypothesis is FALSIFIED** by the very regeneration it was
>   pre-registered to validate: the cited worked example is unchanged and lone-`Name[n]` went **UP**
>   (5,168 → 14,441). The count was [M]; the mechanism was [I] and is now **UNKNOWN**. Do not reuse it
>   as a signal. (Repeated-`Name[n]`, i.e. genuine static arrays, went 2,305 → 798,311 — that part is
>   the fix working.)
> - ★★ **The variance was never the interesting part.** ~**70 %** of container inner types are wrong in
>   **every** usmap ever produced, deterministically; **41 %** of Array/Set inners are a fabricated
>   `ByteProperty`; **all 555 Maps + 142 Sets carry `Map<Byte,Byte>`/`Set<Byte>`**; and a *second*
>   writer defect drops **100 % of enum properties (1,840)** and renumbers **7,713** schema indices.
> - ★ **A fresh extraction is NOT better** — all five usmaps score 29.4–29.9 % against an independent
>   oracle, errors **symmetric**. Re-extracting without the fix buys nothing.
> - ⚠ **The four sizes are duplicate `AnimBlueprintGenerated*Data` records** (anim-BP residency), not
>   coverage and not randomness: all five extractions carry **11,344 unique struct names / 2,226 enums**.
> - ⚠ **Both load-bearing examples are decided, and BOTH of this entry's readings are wrong:**
>   `DefaultMappingContexts` = `TArray<FDefaultContextSetting>` (**no usmap can express it** — so
>   **S79/S80's "EMPTY" was read against a wrong inner type**), and `ScreenEffectCollections` =
>   `TArray<UMaterialParameterCollection*>` — **NOT `ELokiGameFeatureToggle`**, so **the S88 toggle wall
>   was built on a `labelPtr` hit on adjacent heap.**
> - ⚠ **This entry's `ULokiPlayerConfigManager` evidence is not in the 326**, the class is named
>   `PlayerConfigManager`, and **all four dumps read it identically** — the shift is deterministic and
>   permanent, not dump-to-dump variance.
> - ⚠ **"Nothing usmap-derived is trustworthy" is OVER-BROAD.** Struct names, property names, supers,
>   `StructProperty` type names, scalars and the 2,226-entry enum VALUE table are **0.000 % variant and
>   correct**. `endpoints.md:49`'s `CoreGamePlayer` is **4 scalars**, so row (g)'s FK-14-based doubt
>   **does not apply to it**.
> - ⚠ **Live foot-gun:** `pipeline.go:214` overwrites the canonical usmap on **every** extract from any
>   CWD — that is how it became an orphan with no recoverable schema. Backup taken; delete that write.
> - **Audit item 26 is DONE** (canonical MD5 table + consumer map, §7 of the settlement doc).
>   Two consumers load **stale** usmaps (`asdump.py`; `analyze.py`/`compare.py`), severity LOW-measured;
>   and **`mappings+as.usmap` is loaded by NOBODY** — CLAUDE.md's "the usmap gap is CLOSED" describes an
>   artifact that is built, verified, and **not wired in**.

| | |
|---|---|
| **Belief** | `CLAUDE.md:259`: *"Don't trust the extracted usmap for replicated container types — it has been wrong repeatedly. Verify struct/array shapes against live RPM."* Echoed at `coverage-audit-s101.md:459`. |
| **Actual evidence** | Repeated painful experience with replicated containers. |
| **Why weaker** | Two schema dumps of the **same unchanged 2025-12-17 exe**, one week apart, list identical type names but disagree on **326 property TYPES** — 219–228 container inner types and 111–119 enum underlying types, 26 Loki-owned, **most of them not replicated**. Worse, the failure mode is an **index shift, not noise**: `ULokiPlayerConfigManager` reads `ActionMappings=Array<InputAxisKeyMapping>` / `AxisMappings=Array<InputActionSpeechMapping>` / `SpeechMappings=Array<LokiGenericConfigGroupValues>` — each struct name exactly one slot off, carrying through. Three usmaps exist on disk with three MD5s (1,858,484 / 1,870,768 / 1,876,415 B), and **the one the extractor loads has never had its schema printed** — so all 68,301 asset dumps were decoded against a mapping nobody has inspected. Two disagreements are directly load-bearing: `EnhancedInputDeveloperSettings.DefaultMappingContexts` (`Array<Int>` vs `Array<DefaultContextSetting>` — the property S79/S80 measured as "EMPTY") and `LokiScreenEffectComponent.ScreenEffectCollections` (`Array<LokiCharacter>` vs `Array<Byte UEnum:ELokiGameFeatureToggle>` — the S88 toggle wall). |
| **Steers** | "Verify replicated containers against live RPM" is not a sufficient rule; *nothing* usmap-derived is trustworthy without a cross-check, and `docs/endpoints.md:49` still calls the usmap "ground truth" for `CoreGamePlayer`. |
| **Cheapest experiment** | Diff the two `schema.txt` files (6 lines of python); dump the schema for the third usmap; record the canonical MD5. **Hours.** |

---

### FK-15 — "Server→client WebSocket push is measured non-functional (5 negative probes)"
**Severity: MEDIUM-HIGH (it writes off the entire multi-party notification surface).**

> ✅✅ **SETTLED S117, 2026-08-13 — REFUTED BY AUDIT *AND* CONFIRMED BY DIRECT EXPERIMENT.**
> Primary evidence: `docs/fk15-ws-push-audit.md` + `docs/fk15-probe1-live-result-20260813.txt`.
> **★★★ THE CLIENT PRINTED OUR SENTINEL BACK.** One 19-byte TEXT frame on the messenger →
> `LogMessenger: Warning: Messenger recieved unexpected message: FK15-PROBE-FROM-AGS`, against a
> baseline of **0** captured immediately beforehand and **393 same-category Warnings** in the same
> log. Server→client push works and reaches the application layer. **Do not re-open.**
> ★ Bonus: **`LogJson`'s silence was NEVER-RAN, not suppressed** — it fired unprompted at `Warning`
> because nothing had ever handed it malformed JSON.
> ★★★★ **PROBE 2 ALSO SHIPPED AND CONFIRMED — the ~60 s messenger churn is FIXED.** Replying in
> **TEXT** `{"Resource":"hb","Version":0,"Payload":""}` to the client's binary `hb` took the
> watchdog from **once per ~61 s like clockwork** to **zero fires**, socket held **325 s+** (prior
> max ~61 s), delivery 1:1. ✅ **S85 checked, not assumed:** an explicit `conn.Drop()` still forces
> reconnect + resync in <6 s. ⇒ the messenger is now a **stable server→client channel**.
> ⚠⚠ Two instrument failures while measuring it, both nearly recorded as results: `rg` is absent in
> the **background** shell (→ a fall-through **false PASS**), and `Loki.log` is **UTC** while deploy
> times are **local** (→ a **false FAIL** five hours off). Self-test every harness; state the
> timezone.
> ★★★ **PROBE 3 CONFIRMED + SHIPPED — AND NOW ON BY DEFAULT (see the apply proof below):** a
> pushed version bump causes a **targeted
> refetch in 491 ms with NO teardown** — `lobby.NotifyResource(...)`, with `MarkDirty` able to use
> it instead of dropping the socket. ⚠⚠ **Version is a footgun, both modes measured:** too low →
> **silently ignored** (`partyVer` is seeded `time.Now().UnixMilli()`); too high → **unbounded
> refetch loop** (46 fetches in 4 s, cleared only by restarting `ags`). Pass the version the
> document will carry — the shipped path uses `PartyVersion()` and is correct by construction.
> ★★★★★ **AND THE APPLY IS PROVEN TOO (2026-08-13) — the flag SHIPS ON.** Controlled round-trip on
> the lobby platform: podium **BLUE → GOLD → BLUE** on command, `messenger DROP` **0** and connects
> **1** throughout. ⇒ **S85's socket drop is RETIRED** as the primary lever, and lobby.go's
> *"~1 s reconnect floor is not backend-controllable"* is obsolete — there is no reconnect now.
> ★★ **Observable selection is the transferable lesson:** the hero skin is USELESS here because
> `loadout_fix` polls its feed every ~175 ms and applies skins itself; the **lobby platform** is in
> the party doc (`loadout.go:411`) and has **zero** shim code, so it is party-doc-driven and
> shim-blind. ⚠ An earlier attempt was invalid because **no shim was injected at all**
> (`GET /revival/loadout` = 0) — the display path did not exist and its null was guaranteed.
> - ★★★ **Push WORKS, and the measurement already existed.** In the 2026-08-09 verbose run the
>   client logs `AccelByte::AccelByteWebSocket::OnMessageReceived` **exactly 4 times — 1:1 with the
>   4 frames `respondText` sends** [M]. One `/lobby` socket held **3 h 43 min**, zero closes; the
>   client asks each of its 4 requests **once** and never retries. ⇒ transport, framing, parse and
>   SDK surfacing all work. What is untested is whether an **unsolicited** frame produces a
>   **visible** effect.
> - ★★ **The 5 negatives are VOID, not weak.** All fired **2026-06-29, 41 days before FK-11's
>   verbosity fix**. Every detector was pinned to `Warning` by the shipped ini, and **2 of the 6
>   (`LogPlatformLobby`, `LogPlatformQuery`) DO NOT EXIST in the binary** — they occur nowhere in
>   this repo except the sentence asserting their silence. Across **326** archived client logs all
>   six have emitted **0 lines, ever**. The probes could exclude only a warning-level rejection.
> - ★★ **They tested 1 of 33 notif types.** The real table is contiguous at RVA
>   `0x86011D0`–`0x8602828`: **119 tokens, 43 Request / 43 Response / 32 real Notif**
>   (`server/internal/lobby/vocabulary.go`). The one type probed, `matchmakingNotif`, is the one
>   most likely to be ticket-gated.
> - ★ **And it was chosen by a wrong-token search:** the v1 name is **`dsNotif`, not `dsNotice`**,
>   and `dsNotif` **is present**. ⚠ Do not quote "10×" — 9 of those hits are inside
>   `…FriendsNotif`; standalone, `dsNotif` and `matchmakingNotif` occur **once each**.
> - ★ **The recorded blocker is obsolete:** the hero-asset gate it blames was solved **6 days after
>   the probes** (`c1eaf88`, 2026-07-05). Never re-run since.
> - ★★★ **The OTHER socket is worse than anyone thought:** `UMessengerManager::OnMessage` parses
>   **TEXT/JSON** into `FNotificationMessage{Resource,Version,Payload}`, and our **binary** `hb`
>   never reaches it — `recieved unexpected message` (a **Warning**) fired **0** times across
>   **1,419** connections in which `heartbeat not received` fired **1,418** times. A clean negative
>   with a built-in positive control. ⇒ the messenger has **never delivered one frame** to its
>   application layer, and *"a format problem, not a delivery problem"* is backwards — **delivery
>   fails first**. Fix = reply TEXT `{"Resource":"hb","Version":0,"Payload":""}`.
> - **Transport exonerated by measurement** (not by reading): frames at 1/2/60/125/126/127/**1462**/
>   65535/65536 B all arrive byte-identical, read back by an independent RFC 6455 decoder.
> - **Harness shipped:** admin-panel "WS Push" tab + `/api/ws/{sockets,preview,push,sweep,vocabulary,drop}`.
>   A probe is now a button press, and one sweep walks all 32 types in ~96 s.
> ✅✅✅ **CLOSED COMPLETELY S118, 2026-08-13 — the "open, correctly scoped" question below is
> ANSWERED. Primary evidence: `docs/fk15-bound-delegate-map-20260813.md`.**
> The old open item read *"which notif types produce a visible client effect — start with `dsNotif`"*.
> **`dsNotif` was the wrong place to start**, and the answer is now measured end-to-end:
> - **Only 7 of the 33 types can move this client**, because the other 26 broadcast into a delegate
>   with **no subscriber**. Derived by joining all 33 jump-table case bodies (`lea rdx,[rdi+<off>]`)
>   against the live bound/unbound state of `Lobby`'s delegate table. **21 of the 23 bound delegates
>   belong to ONE `USocialManager`**, which is *why* the reachable set is the friends/presence family:
>   `disconnectNotif` · `userStatusNotif` · `accept`/`request`/`unfriend`/`cancel`/`rejectFriendsNotif`.
>   ⇒ **`dsNotif`, `matchmakingNotif` and every `party*` type are UNBOUND — pushing them can never
>   have an effect in this build.** The route is closed at the client's **subscription** layer, not
>   at transport/parse/route/deserialize, all of which S117 proved working.
> - **ALL 7 WERE THEN FLOWN against the live client, and 6 produce VISIBLE UI changes** (friend
>   request card, friend added/removed, presence online/offline, `INCOMING 1→0`, `OUTGOING 1→0`).
>   `disconnectNotif` is a **controlled negative** against a matched bare-drop arm.
>   ⇒ the delegate map is **predictive on every type it named**, having been derived entirely offline.
> - ★★ **Structural finding worth more than the list: the client MUTATES ITS OWN social state from a
>   notif, and only a refetch re-imposes ours.** Shown twice in opposite directions
>   (`accept` added a friend with no `listOfFriendsRequest`; `reject` removed an outgoing request
>   **while we were still serving it**). ⇒ **pushed social changes are TRANSIENT unless the backend
>   also serves them** — build both halves.
> - ⚠ **Payload field names split and fail SILENTLY** (unknown keys are ignored):
>   `request`/`accept`/`unfriend` = `friendId`; `cancel`/`reject` = `userId`. Both confirmed on wire.
> - ⚠ **`userStatusNotif` → OFFLINE requires OMITTING `activity`** — a live activity blob overrides
>   `availability`. This was first published as a working round trip **without being observed**, then
>   retracted; the retraction is what generated the experiment that found the override rule.
> - ★ **New free instrument:** `LogJson` echoes a rejected value AND names the property + enum
>   (`Unable to import enum ELokiActivityState from string value S118PROBE for property A`) — the
>   antidote to silent unknown-key failures. **Watch it on every push.**
> - ★ **Best UI instrument on this surface: the FRIEND REQUESTS modal**, which has explicit
>   `INCOMING`/`OUTGOING` **counters** and reads out a precondition directly.
> **Still open (small):** the 16 bound delegates that no notif case broadcasts (the response /
> socket-lifecycle surface); whether `disconnectNotif`'s handler has any internal effect; and
> `messageSessionNotif`'s separate v2 handler at `.text 0x4B07E80`, unverified.

| | |
|---|---|
| **Belief** | `docs/coverage-audit-s101.md:98`. |
| **Actual evidence** | `server/internal/lobby/lobby.go:385-511` — **all five probes build only `matchmakingNotif` frames**, and each bundles 20+ speculative fields (`ip`/`port`/`Address`/`Port`/`HostName`/`ServerUrl`/`dsInfo`/`DsInfo`/…) in one frame, directly violating the project's own single-variable convention. So even the negative result is ambiguous. |
| **Why weaker** | One message type ≠ the push mechanism. The **messenger DROP** path *does* work end-to-end (S85 `enableMessengerDrop` + `lobby.MarkDirty`), proving the client acts on server-side socket events. And a *targeted* push **is** expressible today: `registerMessenger` (`lobby.go:121`) keys live connections by player id in `s.messengers` — it is only the `/lobby` socket that lacks an id association. |
| **Steers** | ~~Party invites, join notices, friend requests, kicks — every server-initiated multiplayer event.~~ ⚠ **CORRECTED S118: this over-stated the reach in one direction and under-stated it in another.** **Friend requests / presence: YES**, all 7 flown and 6 drive visible UI. **Party invites, join notices, kicks: NO** — every `party*` case broadcasts into an **UNBOUND** delegate, so no push of those types can move this build. The blocker for party is the client's *subscription* layer, not the push channel. |
| **Cheapest experiment** | ~~Push one party-invite-shaped frame (`partyGetInvitedNotice` / `UserNotification_PartyInvite`) on both sockets and watch for a toast **or a `LogJson` complaint**.~~ ⚠⚠ **THIS EXPERIMENT WAS A GUARANTEED NULL — do not fly it (S117).** `partyGetInvitedNotice` has **0 hits** in either encoding (the real lobby token is `partyGetInvitedNotif`); `UserNotification_PartyInvite` is a **client-side `UObject` built by `UUserNotificationManager` from local models, not a wire type** (invite content never crosses the socket); and **`LogJson` has emitted 0 lines in 326 client logs** so its complaint could never have appeared. **Replacement:** send the literal text `FK15-PROBE-FROM-AGS` on the **messenger** — `UMessengerManager::OnMessage` fails to parse it and logs `Messenger recieved unexpected message: <sentinel>` at **`Warning`**, visible at today's verbosity, against a **measured-zero baseline over 1,419 connections**. See `docs/fk15-ws-push-audit.md` §3.5. ✅ **FLOWN AND CONFIRMED (S117).** ✅✅ **AND SUPERSEDED (S118): no experiment is needed here any more — all 7 reachable types have been flown, 6 drive visible UI. The remaining cheap experiments are listed in the S118 "still open" note above, none of them about the push mechanism itself.** |

---

### FK-16 — "Voice is structurally blocked — Vivox validates server-side against Theorycraft's secret"
**Severity: MEDIUM. Found by 2 dimensions (multiplayer-void, original-architecture).**

| | |
|---|---|
| **Belief** | `docs/endpoints.md:44` and `coverage-audit-s101.md:104,584` — *"Blocker is structural — no fix without the real secret"* / *"Do not chase the Vivox token."* |
| **Actual evidence** | A **live measurement** (`20127: Access Token Service Unavailable`) that is correct and correctly scoped **to Vivox**. |
| **Why weaker** | The verdict is drawn one level too high. `schema.txt:70913` gives **`EVoiceProvider = {None=0, Vivox=1, Discord=2}`** — Discord is a compiled-in *alternative provider* — alongside `UVoiceProviderManager`, `UAbstractVoiceProviderRegistry`, and `Services\Voice\{AbstractVoiceProviderRegistry.h, VoiceProviderManager.cpp, VoiceRoomManager.h}`. `discord_partner_sdk.dll` ships and is **loaded in the running process** (confirmed in the module list), and the audit records the Discord client connection as LIVE. Separately, nobody has proposed the project's own standard move: **redirect the Vivox hostname into the local mux** the way 25 other services were redirected — `vivox` returns **0 hits in `configs/` and `server/`**. |
| **Steers** | An entry on the "Explicitly NOT recommended" list that may be wrong. |
| **Honest caveat** | Only `VivoxRegistry` subclasses `AbstractVoiceProviderRegistry` in the usmap, so a Discord registry UClass may not exist. The enumerator alone does not prove a working second path. |
| **Cheapest experiment** | Dump `EVoiceProvider`'s enumerators and `VoiceProviderManager`'s registry population. **Minutes, offline.** |

---

### FK-17 — "`SUPERVIVE.exe` → preloader + runtime is a CEF/Electron shell"
**Severity: MEDIUM (it points reasoning at the one binary with no CEF, and away from the one that has it).**

| | |
|---|---|
| **Belief** | `docs/findings.md:16` and `memory/supervive-revival-overview.md:21`. |
| **Actual evidence** | Inferred from filenames; never checked against the binaries. |
| **Why weaker** | `SUPERVIVE.exe` is 240,328 B, 6–7 stock PE sections, single PDB string **`BootstrapPackagedGame-Win64-Shipping.pdb`** (Epic's stock UE bootstrap launcher), with **zero** `electron`/`libcef`/`chromium` strings. `preloader.dll` and `runtime.dll` are not beside it — they are in `Loki/Binaries/Win64/`, and appear in **no shipping manifest** (i.e. delivered post-cook, on a separate path). The **actual** Chromium is UE's `WebBrowserWidget` + `Engine/Binaries/ThirdParty/CEF3/` initialising **inside the game process every launch** (`LogPluginManager: Mounting Engine plugin WebBrowserWidget`, `LogCEFBrowser: CEF GPU acceleration enabled`, `libcef.dll`+`chrome_elf.dll` in 74/86 crash module lists). |
| **Steers** | Load-order reasoning; and plausibly *why the live in-game CEF surface was never investigated* — 3-4 of the 7 never-opened menu surfaces (News/Announcements, Event Hub, Referral) may be **web pages**, which would be impersonatable from the Go backend with no shim. |
| **Scope limit** | The adjacent `findings.md:184` claim — *"its PE import table lists ONLY preloader.dll"* — is **TRUE** (verified: one import descriptor). Do not let this retraction spill onto it. |
| **Cheapest experiment** | Already done. Correct both files. **Minutes.** |

**★★★★★ CLOSED — S119, 2026-08-14. Both halves resolved, in opposite directions.**

**(a) The doc defect is fixed.** `docs/findings.md:16` now states the measured truth (stock UE
`BootstrapPackagedGame` launcher, zero CEF strings). Corrected in place with the retraction visible.

**(b) The surviving "Steers" hypothesis — *News/Event Hub/Referral may be web pages* — is REFUTED.**
Three independent instruments, each controlled:

* static asset corpus — exactly **1 of 68,303** shipped assets embeds a `WebBrowser`:
  `WBP_UI_Login_Screen_AwaitingLegal`, the AccelByte legal/ToS modal. Controls on the same
  instrument: RichTextBlock 17 files, ScrollBox 57, fabricated class 0.
* live `GUObjectArray` walk, 195,084 objects — exactly **one** `UWebBrowser`, and it is the CDO.
  Finder validated against `PC_MainMenu_C` (the class CLAUDE.md records other probes silently
  missing) plus a fabricated-name negative control.
* reflection table, 18,325 UFunctions / 11,385 classes — **no Loki-authored browser class**;
  `UWebBrowser` is stock and alone.

The `LogWebBrowser: Deleting browser for Url=.` line seen at every startup is that one vestigial
login modal, whose blueprint never assigns a URL. **We were not the reason it was blank.**
Banner clicks go to `UKismetSystemLibrary::LaunchURL` — the **OS** browser, never an in-game page.

**(c) The opportunity the row was pointing at is REAL, via a different mechanism, and is now
SHIPPED.** The News surface is the lobby banner carousel: native UMG, driven entirely by
`ClientConfiguration.BannerConfigs` — a field of the client-config document this backend already
serves and had never populated. Confirmed live: our text, our colors, our splash image, and a click
opening our own page. **No shim, no `.text` write.** Full detail in CLAUDE.md, "Before touching
anything news- / banner- / announcement- / CEF-shaped".

**(d) Two gates were found and both are HTTP-openable** —
`[7] IsMatchHistoryLoaded` (`[MatchHistoryManager+0x68] >= -1`, sentinel −2) and
`[10] bAllMissionLoaded`. Opening the second required serving
`FPlayerProgression.MissionInfo`, which **also made the missions page fully native and retired
`missions_fix.dll` from the default injection set** — removing one manual-map and one transient
`ProcessInternal` `.text` patch from every launch.

**⚠ Method note worth carrying:** the "banner rendered" detector (an HTTP fetch of the splash image)
is only valid on a cache MISS — the client caches banner images to `Saved/ImageCaches`, so after the
first render it draws with no request at all. A later zero was briefly read as a regression. And
`User-Agent` must be checked on every captured request: our own `curl` verifications land in
`capture.log` looking exactly like client traffic, which nearly produced a fabricated result.

**⚠⚠ FOLLOW-UP, 2026-08-14 — that same artifact went on to manufacture a FALSE FINDING, which is the
44th instance of the instrument-artifact pattern and the more instructive half of this row.** The
cached-image null was identified, written down as "uninterpretable"… and then reasoned from anyway a
few steps later, yielding a confident claim that the banner was **order-dependent** (that
`InitializeBanners` runs from `BP_OnActivated`, so a play screen activating before both gates open
would never re-trigger). That was never measured. Asked to *fix* it, the first step was to make the
render detectable — banner image URLs now carry `?v=<nonce>`, changing once per ags start — and the
premise immediately collapsed: on a plain default launch with `pushes=0` on both sockets, the gates
open at `00:42:43` and the client fetches the splash at `00:43:06`, **23 s later, unprompted**. The
chain self-triggers. **Nothing was broken; the "fix" was a verification.**
★ Two transferable rules: **naming an artifact does not neutralise it** — the guard has to be built,
not just noted; and **verify the premise before building the fix**, because a fix shipped here would
have been permanent complexity defending against a bug that never existed.

**⚠⚠ AND A THIRD, SAME DAY — the 45th instance, this one entirely self-inflicted and the most
embarrassing kind.** `tools/re/obj_by_class.py` prints a correct total (`found N LIVE instance(s)`)
and then a detail list **capped at 60 rows**. Counting the rows — `| grep -c "obj="` — therefore
SATURATES at 60. A class with 126 live instances read as "60", and that 60 was carried through
several turns into the conclusion that whole mission pools were being rejected
("11/11 grouped landed, 0 of 94 ungrouped"), which is FALSE: 126 of 323 land, and `HunterMissions`
lands 67/150 with no `PoolGroupId` at all. `PoolGroupId` governs UI visibility, not model
acceptance. **The instrument was never wrong — the number it printed was right every time.**
★ Rules: **parse a tool's stated total, never `wc` its output** — a truncated list is a silent
clamp; and **cross-check any object census by POINTER EQUALITY on the target UClass**, which is
name-free, immune to FName-decode failure, and is what settled this (127 objects share the
`UMissionModel` UClass pointer = 126 map values + the CDO, every map value found, zero unreadable).
The tool now prints an explicit "… N more not shown / DO NOT COUNT THESE LINES" banner.
★ Also recovered while chasing it: the `_1`/`_2`/`_3` mission suffixes are TIER VARIANTS
(`Alchemist_HealWithQ` max 10 → `_1` 7,500 → `_2` 75,000 → `_3` 300,000), and the 218 suffixed
names are exactly the 218 with no declared pool — a variant inherits its base mission's pool and
CUE4Parse omits inherited properties. **★★★★★ ANSWERED the same day: the mission name is the data asset's `InternalName` property,
not its file name.** The client registers every mission with the AssetManager under its own
`InternalName`; our catalog derived names from the DA FILENAME, so most missions named an
`FPrimaryAssetId` that does not exist and were silently dropped. **Serving `InternalName` took
uptake from 126/323 to 248/248 — set-identical, zero dropped in either direction, on a cold
client.** Established two independent ways BEFORE it was flown: a live walk of
`UAssetManager.AssetTypeMap["Mission"].AssetMap` (330 entries — every mission IS registered, so
registration was never the differentiator, only the KEY), and an offline classification of the 323
then served (TP 126, FP 0, FN 0). Both predicted 248; 248 landed.
★ It is a REGISTRY, not per-file equality: the shipped data contains a swap
(`DA_Mission_Wukong_QKnocks_2` declares `wukong_qknocks_3`, `_3` declares `wukong_qknocks_2`) —
per-file equality predicts both rejected, both were accepted. Matching is CASE-INSENSITIVE (FName,
not FString): 41 of the original 126 matched only after case folding. The 75 DAs with no
`InternalName` are exactly the `CLASS_Abstract` base templates, which is the mechanism behind the
old "bases never land (0/75)" observation.
⚠ The per-pool split that preceded this was noise: `PoolId` was separately DISPROVED as the filter
by a single-variable probe (omit it from all 323, confirm ingest via `PM+0xA0`, count unchanged).
★★ **Method note — the merge trap bit TWICE here and nearly produced two more false results.**
The ingester MERGES into the existing model rather than replacing it, so an in-place re-push can
only ever grow the count. That made the PoolId probe's "no change" weak, and it made the first
`InternalName` reading look like a perfect 248/248 when the map actually held 205 new keys plus 43
stale ones from the previous ingest — a coincidence that arrived at the right number for the wrong
reason. **Any acceptance measurement must be taken on a COLD client.**
★★★★★ **Confirmed a THIRD way, from disassembly, and it exposes the cheapest instrument on the
surface.** The ingest loop (`base+0x5700E13`, stride 0x60) calls `MakeMissionModel`
(`base+0x56F16F0`, fold 1) and drops the element at `base+0x5700E8C` when it returns nullptr; that
happens iff `UAssetManager::GetPrimaryAssetPath(id)` returns an EMPTY path inside
`AsyncLoadPrimaryAssets` (`base+0x561C6B0`, test at `base+0x561C7F4`). Pool, expiry, `BaseMission`,
`IsDebugOnly` and dedupe were each ELIMINATED from the disassembly. **And the drop is LOGGED:**
`LogLokiAssetManager: Error: Invalid asset path for Mission:<Name>` plus
`LogBaseMission: Warning: Mission object is null` — 591 = 3 x 197 lines in the broken session, the
197 names set-identical to the 197 rejected, and **0 of each after the fix** (verified first-hand).
⇒ ★ **The client had been naming every rejected id in plaintext the whole time.** The answer was
reached instead by family/pool statistics, a live AssetManager walk and an offline classifier —
all correct, none necessary. **Method rule #2 (read the shipped artifacts first) would have gone
straight to it; grep `Invalid asset path for` before inferring anything about accepted ids.** It is
a free, exact, per-id readout and it generalises to every FPrimaryAssetId the backend serves.
⚠⚠ **Correction to a long-standing repo belief:** `CreateMissionsModel` (`0x56E0600`),
`CreateMissionModelFromFinalProgress` (`0x56E0560`) and `OnPSMissionsUpdated` (`0x56F51B0`) are
**NOT on the native path** — all three are PAGE_NOACCESS (never executed) in two independent live
processes, decrypted only in `dumps/missions` where the retired shim force-called them.
`interactive.go`'s "CreateMissionModelFromFinalProgress is the factory" describes the SHIM's path.
★★ **AND THE FIX'S VISIBLE RESULT FALSIFIED ONE MORE OF MY OWN CLAIMS.** Before the screenshots I
predicted the modal would look unchanged, because the newly-accepted missions sit in pools with no
`PoolGroupId`. It went from **2 categories to 4**: ONBOARDING and SEASONAL both appeared, and both
their pools (`Onboarding`, `Tournament`) declare `PoolGroupId = None`. ⇒ **`PoolGroupId` is not a
gate on acceptance OR on visibility** — both readings were artifacts of the same filename bug,
since only the daily/weekly pools happened to hold missions whose filename matched their
`InternalName`. The category rail is driven by which pools have ACCEPTED MISSIONS. The pool's
`MetaMission` also renders now (COMPLETE ALL DAILIES 0/3, 7500 XP).
★ Worth keeping as method: a claim built on a dataset that a KNOWN BUG was filtering will look
clean and survive review. `PoolGroupId` was retracted twice — once as acceptance, once as
visibility — before the underlying defect was found. **When a bug is discovered upstream, re-derive
every conclusion drawn from the contaminated data rather than patching the wording.**

---

### FK-18 — "`merged.dump.exe` is a merged multi-state image"
**Severity: MEDIUM (every static coverage number the project quotes is a single-state number).**
★★★★★ **SETTLED 2026-08-14 (S121) — `docs/fk18-fk19-multistate-merge-settled.md`. Read that first;
the rows below are the original entry, preserved.** Confirmed and sharpened: the merge was a **NO-OP**
(union of its 5 inputs == the seed `dumps/loadout`; `.text` diff 0, `.rdata` diff 0, and the 1,195
bytes are all `.data`). **Mechanism: `.text` decryption is MONOTONE within a process lifetime**, so
the five snapshots of PID 4080 are strictly nested (`menu ⊂ store ⊂ roster ⊂ missions ≡ loadout`) and
N substates of one launch are worth exactly one dump, by construction. **Fixed and executed:**
`dumps/merged2.dump.exe` = **16,625 / 30,281 pages (54.90 %)** vs merged's 15,833 (52.29 %), strict
superset, 0 regressions, `.rdata`/`.data` coherent instead of spliced. The `.data` caveat is now
**bounded and retired** rather than documented (4,678 bytes change identity from seed choice alone;
`merged2` carries none of it).

| | |
|---|---|
| **Belief** | CLAUDE.md and `memory/supervive-image-dump-status` present `mergedumps` as the route to full `.text` and instruct *"dump from DIFFERENT game states (login, hero grid, store, missions…)"*. |
| **Actual evidence** | The merge manifest itself: the seed contributed **88,854,234 bytes** and the other four inputs contributed **910 + 107 + 124 + 54 = 1,195 bytes total** (0.0013%). All five were near-identical menu substates captured within four minutes of each other. Page-granular: 6 of 9 captured states contribute **zero** unique pages. |
| **Why weaker** | So "48.05% `.text` / 63.1% `.rdata` / 36.8% `.data`" are properties of *one menu snapshot*, and the multi-state strategy has never actually been executed. The manifest also warns — unquoted anywhere — that *"`.data` union across differently-timed dumps may mix runtime state"*, so any global read out of the merged image is a value that never simultaneously existed. |
| **Steers** | The "structural ceiling" framing; Ghidra's data model; audit item 0.2's expected gain. |
| **Note** | The audit *does* correct this at line 283 (+2,044,822 bytes from merging `toggles`/`vmbuild`/`accountpass`), so the residual false-known is the **stale guidance in CLAUDE.md and memory**, plus the never-stated `.data` caveat, plus the untried `rcb` rebase (below). |
| **Cheapest experiment** | Re-run `mergedumps` (audit 0.2). **Minutes.** |
| **★ DONE 2026-08-05 (S111)** | The multi-state strategy has now actually been executed once: `dumps/tutorial-hero/` was captured from a **staged tutorial world with the hero spawned and possessed** — 67.42% overall, `.text` **53.2%**, `.rdata`/`.data` 100%. That is the first genuinely non-menu capture state the project owns, and it is the right image for any ability-system or in-world question. ⚠ It **cannot** be merged with `merged.dump.exe`: different ImageBase (`0x7FF6505C0000` vs `0x7FF6AF000000`) and `mergedumps` rejects mismatched bases by design, so the two remain separate images rather than one better one. The residual false-known (stale multi-state guidance in CLAUDE.md/memory, the `.data` mixing caveat, the untried `rcb` rebase) is unchanged. |

---

### FK-19 — "`mergedumps` rejects a different ImageBase, therefore `rcb` is unusable"
**Severity: MEDIUM (1 MB of already-paid-for gameplay `.text` sits discarded).**
★★★★★ **SETTLED AND FIXED 2026-08-14 (S121) — `docs/fk18-fk19-multistate-merge-settled.md`.**
No rebase was needed: **`.text` carries 0 of the image's 1,403,750 base relocations** (1,257,732
`.rdata` + 146,018 `.data`), and `.text` is byte-identical across ImageBases on every shared decrypted
page — **0 differing bytes in 10 of 10 pairwise comparisons**, with a same-base noise floor of 0 and a
149,399/149,399 reloc-parser negative control. `mergedumps` now merges **`.text` only, page-granular,
ImageBase-agnostic**, gated on an identical section table plus a per-donor overlap-conflict check
(every current donor: **0, clean**). The three discarded cross-base dumps contribute **246 pages
reachable no other way**, incl. character-movement code (`GetMaxJumpHeight`, `GetGravityDirection`,
`GetMaxBrakingDeceleration`) — a subsystem §8.3 lists as DARK. ⚠ The prescription had existed since
**S104** in `fk3-fk4-settled.md` §8.0 and went unimplemented for ~17 sessions.

| | |
|---|---|
| **Belief** | `configs/capture-dumps.ps1`: *"HARD CONSTRAINT: mergedumps rejects inputs with a different ImageBase"*; `merged.dump.exe.txt`: *"not byte-mergeable."* |
| **Actual evidence** | A true statement about the *tool*, presented as a law of nature. |
| **Why weaker** | `.text` is overwhelmingly RIP-relative and the dump ships a `.reloc` section at 97.4% coverage. `dumps/rcb` (base 0x7FF79D3B0000 vs 0x7FF6AF000000, `.text` 51.1% readable) is a mechanical rebase away — a ~40-line python pass — and nobody has ever asked. |
| **Cheapest experiment** | Apply the `.reloc` delta and merge; verify by disassembling a known function at a known RVA. **Hours.** |

---

### FK-20 — "`capture-dumps.ps1`: the tutorial/match state is not captured here (that flow isn't playable yet)"
**Severity: MEDIUM (it is the standing instruction that produced 9 menu captures and 0 gameplay captures).**

| | |
|---|---|
| **Belief** | `configs/capture-dumps.ps1:24-25`, verbatim. |
| **Actual evidence** | True when written. **~35 sessions stale**: the force-open route has real gamemode+gamestate, spawn/possess/teleport, a visible and animated hero (S93/S98/S99b), and holds 10 minutes. |
| **Steers** | `dumps/` contains nine state directories, every one a menu or shim state. The single highest-yield capture available has never been taken. |
| **Cheapest experiment** | During the next force-open, run `capture-dumps.ps1 -State tutorial` from a second elevated terminal, then `-Finalize`. Same session, no extra launch. Budget from the one data point: the merely-drop-in-loading `toggles` state yielded 2.11 MB. |
| **★ DONE — captured S111, first spent S114** | The **Steers** row above is **stale**: the capture was taken in **S111** as `dumps/tutorial-hero/` (staged world, hero spawned and possessed — `.text` **53.2 %**, `.rdata`/`.data` **100 %**; recorded until now only under FK-18's ★ row). **S114 is the first session to actually spend it**, and the whole FK-13 settlement rests on it: `ALLOW_CONSOLE == 0` was decided by the **absence** of five guard-exclusive `Console.cpp` literals, and an absence is only interpretable because that image's `.rdata` is 37,212,160 B at **100.0 % readable** per its own manifest (vs **63.1 %** for `merged.dump.exe`, where the same zero would be uninterpretable). [M] ⇒ **Standing rule: run every `.rdata` presence/absence claim against `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`, never `merged.dump.exe` alone.** ⚠ The two **cannot** be merged (different ImageBase — FK-18/FK-19), so this is a *choose the right image* rule, not a coverage fix. ⚠ FK-20's underlying point **survives**: there are still **0** captures from any state past the tutorial (hero select, drop, in-match, EoG), and those remain the highest-yield uncaptured states. |

---

### FK-21 — "Career→Stats / →Ranked / →History show authentic empties"
**Severity: MEDIUM (it inflates the 24-LIVE-surfaces count).**

| | |
|---|---|
| **Belief** | `docs/endpoints.md:84` (*"Career→History (empty = correct for new account)"*) and the audit's LIVE list at :140. |
| **Actual evidence** | The reasoning "a new account correctly has no history." |
| **Why weaker** | **This account is not new.** `Saved/ImageCaches` holds 56 JPGs dated Nov 2024 – Aug 2025 (live-service era), and `UserSettings.ini` records `HasPlayedTutorial=True`, `HasSeenRankedPopup=True`, `HasSeenReturningPlayerModal=True`, plus `MailboxLastOpenedAt/ClosedAt`. A broken deserialization is observationally identical to an authentic empty, and no positive test was ever run. *Mitigating: the audit does hedge at line 100.* |
| **Cheapest experiment** | Serve one synthetic match-history row and one non-zero stat; see whether the panels render it. **Hours.** |
| **★ S119 UPDATE (2026-08-14)** | **Half-answered, and the method objection is now dead.** `GET /match-history/players/{id}` is no longer an empty catch-all — `server/internal/interactive.handleMatchHistory` serves a real `FMatchHistory{ID, Version, Matches:[]}`. The row's core complaint was that *"a broken deserialization is observationally identical to an authentic empty"*; that is no longer true, because we now have a LIVE DISCRIMINATOR: `MatchHistoryManager+0x68` reads back **our exact served `Version`**, proving the document parsed. So the current Career→History empty is MEASURED authentic rather than assumed. **Still open:** `Matches` is deliberately served EMPTY (the gate needs only `Version`, and `FMatchHistoryEntry` is a 15-field struct — two `FDateTime`, an `FPrimaryAssetId`, nested `FMatchHistoryTeamInfo`/`FLokiPlayerMatchStats`, an `ERank` enum — every one a chance to wrong-type a matched key and reject the whole document). Serving one populated row remains the experiment, and it should go in ALONE. |

---

### FK-22 — "The drop phase is FALSIFIED as reachable"
**Severity: MEDIUM (an N=1 result restated as a general falsification).**

| | |
|---|---|
| **Belief** | `docs/coverage-audit-s101.md:229`: *"Drop-in / DropPlane — **FALSIFIED as reachable** — SpawnPlane faults on absent level markers — S93."* |
| **Actual evidence** | The cited source is *narrower* and careful: `docs/session-93:34-36` says `Comp_GameMode_DropPlane_**Tutorial**.SpawnPlane` faults reading drop-path markers *"that don't exist outside the real deploy"*, and elsewhere records the call was *"fed WRONG arg types"* / *"faults on an empty param buffer"*. That is a statement about one tutorial-specific component variant on one map. |
| **Why weaker** | A general `Comp_GameMode_DropPlane` exists alongside the `_Tutorial` and `_PvE_Holdout` variants; the drop vessel itself (`GameMode/DropPhase/LokiDropShip.as`, `LokiDropPod.as`) is **Angelscript we possess** (FK-1); and `LokiDropShip` returns **0 hits** repo-wide. Only 3 of ~65-91 maps have ever been loaded. |
| **Cheapest experiment** | Read the `.as` modules for the marker/actor names they query, then check whether `LVL_Tutorial`'s dumped cells contain them. **Hours, offline.** |

---

### FK-23 — Smaller false-knowns, batched

| # | Belief | Where | Why weaker | Cost to settle |
|---|---|---|---|---|
| a | *"The full known set of queue ids is: default deathmatch practice dropin customgame bots tutorialNew training armorydeathmath tournament"* | `interactive.go:855-869` | A single-Blueprint inference labelled "full." `DT_QueueDisplayDataTable.json` (already extracted, **0 doc hits**) lists **18** rows incl. `*-ranked`, `duos-ranked`, `holiday`, `domination`, `prismabank`. Neither list is a superset — the DT lacks `tutorialNew`/`training` — so what is falsified is the word *"full."* | minutes |
| b | *"EasyAntiCheat present"* | `memory/supervive-revival-overview.md:21`, `docs/findings.md:18` | Contradicted **in the same file** at `findings.md:186` (*"Verified no EasyAntiCheat anywhere"*) and by S77's module dump. `find` over the tree returns zero EAC binaries; `SUPERVIVE.exe` requires `EasyAntiCheat_EOS_Setup.exe` and `start_protected_game.exe`, **neither of which exists in the backup**. ⚠ *Two of three challengers rated this a doc-hygiene nit, not a decision-steering belief — the real risk posture is correctly built on preloader.dll + the integrity check.* | minutes |
| c | CLAUDE.md lists extractor subcommands *"enumerate, names, namesall, dump, raw, schema, assetregistry"* | `CLAUDE.md` Tooling | ✅ **SETTLED S116 — and the correction itself was incomplete.** `Program.cs:22` accepts **TEN**: `dump names namesall schema assetregistry wherefile mkpak peekpak bpdump rawfile`. ★ **`raw` is really `rawfile`** (so the raw-file path out of IoStore **already exists** — audit items 0.4 and 1.8 assume it must be *written*, and that assumption is FALSE). **`enumerate` is not a subcommand at all** — it is the no-subcommand default mode (`Program.cs:1550`), and `out/allassets.txt` is the preserved crash log of someone typing the literal word (`Paks: enumerate` → `DirectoryNotFoundException`). `bpdump` remains undocumented outside source. **CLAUDE.md corrected in `1b6f9de`.** ⚠ Also measured: `dump` has **no `--out` and no `--usmap` override** — it writes a hardcoded absolute path and resolves the usmap ambiently by search order with no md5 logged; output is flat by basename with **586 colliding basenames** (last writer wins). | ✅ done |
| d | `coverage-audit` §3.5 + item 0.4: *"`Loki/Config/*.ini` … never read"* | audit | **Already extracted since 2026-06-27**: `tools/extractor/out/DefaultEngine.ini` (116,954 B) + `DefaultGame.ini` (27,105 B). They contain the 12-environment AccelByte matrix, the empty `QosManagerServerUrl=` (FK-5), the `[Core.Log]` block (FK-11), and `ServerDefaultMap=/Game/Loki/Maps/LVL_ServerStandby`. A roadmap item is proposing work that is complete, while the file that answers three open questions sits unread. | minutes |
| e | `loki.go:118-121` records as a measured S85 result that feature toggles come from *"no separate HTTP endpoint (client hits ONLY /configuration/{public,client} + /mailbox/config/version)"* | `server/internal/loki/loki.go` | The enumeration **omits `/core-game/matches/{id}`**, which S62 proved the client fetches and which carries `GameConfig.CVars` and `Extra.FeatureToggleOverrides`. The sweep that closed the HTTP route did not cover the HTTP route that carries the payload. S88–S90 then spent three sessions bit-splicing a replicated subobject. | hours |
| f | CLAUDE.md: *"VALIDATION PENDING (as of 2026-07-10) … the design is N-way safe **by construction**"* naming **three** PI-hookers | `CLAUDE.md:131-136` | 16 days / ~17 sessions stale, and the launch procedure immediately above it lists **six** shims. "Safe by construction" is an argument, not a measurement; it is the belief that permits the six-shim default; and S85's recorded six-shim crash plus the deterministic 173–201 s cluster are what it predicts away. | one session (audit 1.5) |
| g | `docs/endpoints.md:49`: *"usmap ground truth `CoreGamePlayer` (4 props)"* | endpoints.md | ✅ **The FK-14-based doubt is RESOLVED and does not apply here (S116).** The 326 disagreements are **exclusively** container-inner and enum-underlying types, and `CoreGamePlayer`'s four props — `ID`(str), `MatchID`(str), `Version`(int64), `CanDisassociate`(bool) — are **all scalars, with no container and no enum**. Struct names, property names, supers, `StructProperty` type names and scalar *types* measured **0.000 % variant** across every extraction ever taken. ⚠ **But the reason matters, because a stronger hazard was found:** scalar *VALUES* are only safe when nothing upstream in the same struct was dropped — `SchemaIdx` renumbering made scalars **downstream of a dropped `EnumProperty`** decode another property's bytes (5,723 of 12,129 changed on regeneration). `CoreGamePlayer` is safe because it contains **no enum to be shifted by**, not because scalars are inherently safe. The residual gap is unchanged and is *not* a usmap question: nobody has cross-checked it **live**. | hours (live check only) |
| h | *"The packed process blocks non-system DLL loads"* (why UE4SS is dead) | `docs/findings.md:191-193` | Partly obsolete: the project now manual-maps six shims into that process every launch. The live reasons UE4SS is dead are (i) no import to proxy and (ii) the C++-exception ban — not a general DLL-load block. ~~Nobody has re-tested the intermediate (manual-mapping a small no-throw console-enabler).~~ **⚠ S114 RE-SCOPES that intermediate — it is not one experiment, it is two, and only one is dead.** A ***flag-flipping* console-enabler cannot work at any injection depth**: `ALLOW_CONSOLE == 0` is a **code** strip, not a runtime gate — `UGameViewportClient::Init` (`0x0384FB00`) contains **no** `NewObject<UConsole>` and **no** store to `ViewportConsole` (`+0x48`), so `~` has nothing to open and no DLL, ini or config change alters it (FK-13). [M] What is **not** excluded is a shim that **constructs a `UConsole` itself** and installs it — the class ships **fully compiled** (`GetPrivateStaticClass 0x03F00F70`, vtable `.rdata 0x08257B10`, real bodies `0x3F133B0..0x3F3DB70`) and `UEngine::ConsoleClass` is still resolved at startup by the stock `LoadEngineClass<UConsole>` triple. [M] ⇒ that route is **open but unbuilt**, and it is a larger build than the one S114 actually shipped for less reward: **Route B** installs a `UCheatManager` into `PC+0x520` — one heap qword, zero module-image writes — and already reaches **42 real exec verbs** (`docs/fk13-routeb-shipped.md`). [I for the cost comparison] | hours |

---

### FK-24 — "The writer of the corrupt `ViewTarget.Target` byte is one of two candidates, and the `+0x3F` delta discriminates them"
**Severity: HIGH. Split out of FK-7 on 2026-07-29 (S106e) — see `docs/fk7-crash-settled.md` §0.2 / §0.6.**
**Status: the belief is DEAD; the underlying question is genuinely OPEN and needs a LIVE probe.**

> ## ⛔ RUN LIVE — 2026-08-04 (S108). **THE PROBE WAS THE PROBLEM.** → `docs/s108-fk24-instrument-corrected.md`
> **This banner GOVERNS and overrides the S107 banner below wherever they disagree.**
> The writer is **still NOT named. FK-24 stays OPEN.** What S108 established is about the instrument.
>
> **1. ❌ S107's VOID verdict is FALSIFIED, and the escalation it ordered was never warranted.**
> The line `selftest *** FAIL … the watchpoint is VOID on the game thread ***` is wrong about its own
> subject, refuted two independent ways: (a) `g_wpSelfPhase` advances only **after** the idempotent
> store retires, so `selfPhase=0` means the store **never executed** — a fact about `VtGuard`'s
> cadence, not the watchpoint; (b) dump `166396E2` shows **127 of 128 threads armed, GameThread among
> them, and the GameThread's DR FIRED** (`Dr7` == the probe's own `g_wpDr7Val`, `Dr6` = B0|B1).
> **The packer never defeated DR.** ⇒ *"escalate to `wprobe2` on a VOID verdict"* was triggered by a
> non-event, and the page build reproduced the same non-result because **it drives its selftest from
> the same `VtGuard` call site**. Escalating modes cannot fix a starved positive control.
>
> **2. ★ The probe was KILLING THE GAME, and its kill was recorded as a game crash for a session.**
> Debug registers live in the **thread** and page protection in the **address space** — neither lives
> in `g_wpArmed`. Any flag-down-but-still-armed path turned the next store to `&Target` into an
> exception `WpHandle` **declined**, and an unhandled single-step terminates the process. Dumps
> **`166396E2` (DR mode)** and **`FED1F952` (page mode)** are both **the shim self-killing**.
> ⇒ **Do not feed either to `crash_census.csv` analysis; they are instrument artifacts, not FK-7 data.**
> Corroborated live and independently: probe-carrying runs died at **50–80 s**, the probe-free
> `novtguard` control ran **~290 s**. Fixed by a terminal fallback in `WpHandle` (both modes).
>
> **3. ⚠ My own S108 conclusion `vtHits=1 ⇒ VtGuard never re-runs after init` is RETRACTED** — a
> **sampling** artifact. Every reading came from the `+8 s` selftest line, ~40 marker lines **before**
> `[PL] init complete`; there was no post-init sample in any run. The same run's own dump proves the
> store executed later, so `vtHits ≥ 2`. The derived items FK-24a/b/c are withdrawn.
>
> **4. ★ The "Steers" row below was RIGHT about the leftover diagnostics — see the new FK-26.**
> It flagged *"the three leftover S94 diagnostics (`KCHEATSPAWN`/`KSMACTOR`/`KSTATICTEST`) still ON in
> the candidate build."* `KSTATICTEST` was faulting **every run** and silently disabling the hero's
> walk/run animation. It did **not** contain the writer, but it was doing real damage.
>
> **5. Artifact hashes below are STALE.** After S108b flipped `KSTATICTEST`'s default,
> `a67239a0d83d9300` is **no longer `play`** — it is now `play-statictest`. Current: `play` =
> `ae532866e15fd8ac`, `wprobe` = `6bd374e2d81fde3d`, `wprobe2` = `20fa2a7d79bdd748`.
> The `-Hook <play dll>` run line below **cannot work at all** — `RM_PLAY` is a *continuation* mode.
> Use `configs\fk24-stage.ps1` (hands-free; see CLAUDE.md → "Tutorial sittings").
>
> **The next step is NOT a new watchpoint mode.** It is to (a) sample `vtHits`/`selfPhase` **after**
> init from the census rather than the 8 s line, and (b) get the positive control to fire at all.

> ## ★ THE PROBE IS BUILT AND READY — 2026-08-03 (S107) → **`docs/fk24-writer-probe.md`**
>
> **Read that doc before doing anything with FK-24.** It supersedes the "Cheapest experiment" cell
> below, which under-specified the mechanism in three ways that would have wasted the sitting.
>
> **Artifact:** `tools\sigbypass-mod\build\tutorial_launch_play_wprobe.dll`
> (`.text` sha256 `6da63dc0ab9fafed`; `play` stays byte-identical at `a67239a0d83d9300`, measured).
> Fallback `…_wprobe2.dll` (`0ec5a66b7028623a`), page mode — escalate to it **only on a VOID verdict**.
> Nine defects were found in review and fixed before shipping (two crash-shaped); the earlier
> `28aa024e…` / `22f37ca8…` / `0ee9f6bb…` artifacts are **superseded — do not inject them**.
>
> **Run:** elevated PowerShell, Steam first —
> `.\configs\launch-redirect.ps1 -Hook tools\sigbypass-mod\build\tutorial_launch_play_wprobe.dll`.
> **Budget ≥ 6 launches** (measured base rate 1-in-3…1-in-2 ⇒ `P(all quiet | 6) ≈ 9 %`).
> Copy `docs\tutorial-launch-marker.txt` off after **every** launch (FK-25 truncates it).
>
> **Three corrections the cell below gets wrong:**
> 1. **"armed on the game thread"** — DR0–3/DR7 are **per-thread**, and this process runs **121–140
>    threads** (MEASURED from the dumps' `ThreadList`), ~61 of them carrying game-module return
>    addresses. Arming one thread catches nothing if the writer runs elsewhere — and the evidence says
>    the write happens *outside the camera chain*. The probe enumerates and arms **every** thread and
>    re-sweeps every 250 ms; it also **re-reads `Dr7`** each sweep, which is the packer-clears-DR
>    detector. There is no thread-creation hook available (the DLL is manual-mapped **and** calls
>    `DisableThreadLibraryCalls`), so polling is structural, not a preference.
> 2. **"armed after the body build"** — `g_plBodyDone` (`tutorial_launch.cpp:3830`) is the **exit** of
>    the one-shot block whose *interior* the writer's window sits inside. The probe arms at the first
>    successful `VtResolve()` instead; `KWPARMAT=1/2` keep the later options.
> 3. **The fallback must be `PAGE_READONLY`, not `PAGE_GUARD`.** `SafeReadable` (`:321`) returns false
>    for `PAGE_GUARD`, so arming it would **silently disable `VtGuard`** — the instrument destroying the
>    `[VTG] INVALID` correlation evidence it depends on.
>
> **And the thing the cell's framing most needs:** *"one live run"* is wrong. **A quiet launch is not a
> negative.** The probe therefore carries an in-session positive control (two labelled idempotent stores
> to `&Target` from the game thread) so every launch reports whether the *instrument* worked, separately
> from whether the *bug* occurred — and every "nothing happened" line states in words whether it is a
> **VOID** or a **measurement**.

| | |
|---|---|
| **Belief** | `docs/fk7-crash-settled.md` §7 Step 3 + §8 item 1: *"`delta=+63` (`0x3F`) **and** `lowbyte=0x01` ⇒ a writer aimed at `&ViewTarget.Target`"*, and *"`+0.14 s` after a cloth sim initialising on a non-uniformly-scaled body favours the **heap-overrun** candidate substantially."* Both shipped **inside the fix's own instrumentation**, so the first verification run would have printed the "confirming" value. |
| **Actual evidence** | Two enumerated candidates and a timing coincidence. The delta was computed against the 2 dumps that captured the live camera object. |
| **Why weaker** | **The discriminator cannot fail.** `delta = (live & 0xFF) − 0x01` **whenever** byte 0 is replaced by `0x01`, and the live object's low byte is `0x40` in **3 of 3** observations — *including the clean control dump* `FF9CF623` (`0x1CB9A088D40`). Both candidates emit **literally the same 8 bytes**. Separately, the **favoured** candidate is structurally impossible: the byte sits `0x420` **inside the `APlayerCameraManager`'s own live allocation** (PCM+0x00 = its vtable, `.rdata` RVA `0x7EC5B88`; both `FTViewTarget`s located via the `FMinimalViewInfo` 90/90/512 default signature at PCM+0x460 and PCM+0xC80 in 4/4 dumps), and **a one-byte overrun writes one byte past the end of its OWN block.** A wild indexed write cannot hit the same byte of the same object across 4 launches with different heap bases. |
| **What IS measured** | A deterministic **1-byte** store of the literal **`0x01`** at a **fixed displacement from the PCM**, ~0.15 s after the body build, **outside the camera chain** (present at the top of `DoUpdateCamera` in 4/4), **conditional per launch** (~1-in-3 to 1-in-2; the clean control reached 195 s), with **zero collateral** (290 of 290 non-pointer offsets in `PCM[0x300..0x480)` byte-identical in 4/4). |
| **Steers** | Whether FK-7's camera fix is a **repair** or a **mask**; whether the hunt looks for an adjacent allocation (dead end) or for code holding the PCM pointer; and the three leftover S94 diagnostics (`KCHEATSPAWN`/`KSMACTOR`/`KSTATICTEST`) still ON in the candidate build, any of which could contain the writer. |
| **⚠ Offline is spent** | The instruction-shape scan is now **exhaustive over the decrypted half** of `.text` for every byte-width store form at `disp32==0x420` (`C6 /0` imm8, `88 /r`, `80` with /1 /4 /6 imm8, `0F 9x` setcc, ± REX): **34 sites, 8 with imm8==1**, none in camera/physics/cloth/anim code. Not a negative (`.text` 52.29% decrypted) — and the real search space is **wider** than `disp32==0x420`, since the structural finding fixes the **address**, not the encoded displacement. |
| **Cheapest experiment** | ~~A 1-byte hardware WRITE watchpoint … armed on the game thread after the body build … **one live run**.~~ **SUPERSEDED — BUILT. → `docs/fk24-writer-probe.md`.** The mechanism was right; the *scoping* was wrong in three ways (per-thread DR state vs 121–140 threads; arming at the block's exit rather than inside it; `PAGE_GUARD` silently disabling `VtGuard`) — all three corrected in the banner above. The probe ships as `tutorial_launch_play_wprobe.dll`, still **data-only** (no `.text` patch, no C++ EH — verified: zero `__CxxFrameHandler`, KERNEL32+USER32 only). Attribution is `tid → Rip → RVA → 64 live instruction bytes → containing function → **which register held the PCM**`; the DR0/DR1 pair is a **hardware** width discriminator replacing the retracted `+0x3F`, and it is validated against ground truth in-session. **Budget ≥ 6 launches, not one.** |

---

### FK-25 — "`docs/tutorial-launch-marker.txt` records what a session did"
**Severity: MEDIUM (it manufactures denominator errors). Split out of FK-7 on 2026-07-29 (S106e).**
**Status: an INSTRUMENT defect, cheap to fix, and it has already cost one multi-agent investigation.**

> ## ⚠ STILL UNFIXED, and it cost evidence again in S108 — 2026-08-04
> The shim still opens with `CREATE_ALWAYS`. S108 worked **around** it rather than fixing it:
> `configs/fk24-stage.ps1` copies the marker off after **every** injection into
> `docs/fk24-stage-<label>-<n>-<shim>.txt`. That is the only reason each stage's output survived —
> the crash-triage agent independently hit the unfixed version and recorded the missing `[VTG]`
> line as *"the single missing measurement in this triage."*
>
> ⚠ **A trap the workaround itself introduced, worth naming because it produced a false pattern:**
> the per-stage copies are taken *after each injection*, and `gft_ready_fix` writes a **different**
> marker file — so `fk24-stage-<label>-1-gft.txt` actually holds the **previous run's** tutorial
> marker. Only the `-3-sp` / `-4-probe` copies and the post-mortem `fk24-run-*.txt` are attributable
> to their own run. Comparing across the `-1-gft` files produced a clean-looking correlation that was
> partly an artifact of that off-by-one-run.
>
> **★ S108 also adds a SECOND instance of this entry's class, at a different layer — see FK-9.**
> The marker loses *what the shim did*; the crashpad purge loses *what the game did*. Both are
> "the record is destroyed shortly after the event, and the census cannot tell you it is missing."
> The fix here remains **minutes** (append + PID + wall-clock, as `docs/gft-ready-marker.txt`
> already does) and is still the cheapest unspent item in this document.

| | |
|---|---|
| **Belief** | Implicit in every session that reads the marker to learn what the shim did — and in FK-7's *"5 of 9 tutorial sessions died with no exit marker"*, which treated 9 heterogeneous sessions as **one** experiment. |
| **Actual evidence** | The marker file exists and is written on every injection. |
| **Why weaker** | `Marker()` opens with **`CREATE_ALWAYS`** (`tools/sigbypass-mod/tutorial_launch.cpp:4919`), so **every injection truncates the file.** A session's `RunMode` and compile-time flags survive **only** by the accident of someone committing the file at the right moment. Consequence, MEASURED: 3 of the 5 "unexplained" FK-7 deaths were recoverable as **RM_SPAWNPOSSESS, run to completion** (`[SP] done step=4 …`) *only* because commits `d61d325` / `f6a7985` / `6e8a7df` happened to land **+3 s / +3 s / +9 s** after each session's last log line — and **2 sessions (07-26 04:33:23, 04:36:18) are permanently mode-unattributable.** The file **is tracked in git**, so `git show <commit>:docs/tutorial-launch-marker.txt` was a per-session mode oracle for the whole route's history and was never once used. |
| **Steers** | It produced FK-7's largest scope error — *"a second failure mode is invisible to the entire investigation, ~half the observed rate"* — which was a **denominator error** conflating two shim modes, and it consumed a full adversarial hunt to undo. It will do so again for any multi-launch A/B (i.e. every FK-7 verification sitting). |
| **Cheapest experiment** | **This is a fix, not an experiment.** Append instead of truncating, with **PID + wall-clock** in the header line, or write per-PID markers (`docs/tutorial-launch-marker-<pid>.txt`). Precedent exists in the same tree: `docs/gft-ready-marker.txt` **appends** (50 injections retained). Then commit the marker after every run, as `docs/fk7-crash-settled.md` §0.5 now requires. **Minutes.** |

---

### FK-26 — "The leftover S9x diagnostics still switched ON in the shim are inert"
**Severity: HIGH. Found and settled in one sitting, 2026-08-04 (S108b) → `docs/s108b-ksmactor-bisect.md`.**
**Status: the belief is DEAD (measured). `KSTATICTEST` now defaults to 0.**

> **★ This is the entry FK-24's own "Steers" row predicted** — *"the three leftover S94 diagnostics
> (`KCHEATSPAWN`/`KSMACTOR`/`KSTATICTEST`) still ON in the candidate build"* — and nobody followed it
> up for two sessions. They were not inert. One of them was breaking a headline feature.

| | |
|---|---|
| **Belief** | Never stated, which is why it survived: diagnostics default to `1` in `tutorial_launch.cpp` and every later session reasoned about *the game's* behaviour with them running. `KSMACTOR` (`:4031`) and `KSTATICTEST` (`:4034`) both shipped ON, exactly as `KTESTACTOR` did until S106 defaulted it to 0 for building a second degenerate body. |
| **Actual evidence** | None — the flags were simply never re-examined after the question they answered was settled. |
| **Why weaker** | **MEASURED.** `KSTATICTEST` calls `BuildHeroBody(hero, StaticMeshComponent, …)` at `:4970`, and `BuildHeroBody` unconditionally drives `PlayAnimation` — **on a component that has no animation.** It faults `0xC0000005` every run. Because the fault is **SEH-caught it never crashed anything**, so it left no crash trail; instead the handler printed `anim swapping DISABLED for the rest of the session`. ⇒ **the hero's walk/run animation was dead in every session**, the run asset loaded and then never played. Single-variable bisect: the `nostatictest` arm ran `KSMACTOR`'s `[SMA]` block to completion with **zero** faults and cycled `PlayAnimation(run/idle) ok` for the life of the run. **`KSMACTOR` is EXONERATED.** The faulting object names itself: `[NULL] cls RBX=StaticMeshComponent RDI=StaticMeshComponent`. |
| **Steers** | Every visual judgement about the hero since S94 — "locomotion animation isn't wired up yet" was **false**; it was wired up and being switched off within seconds of each session start. Also every `[NULL]`-fault reading in the FK-7/FK-24 markers, which were the shim's own self-inflicted AV rather than a game fault. |
| **What it does NOT explain** | **The deaths.** Survival did not track the flags — `nodiag` (both off) died at ~130 s while `nostatictest` (one off) lived past 301 s, the *wrong* direction if `KSTATICTEST` were the killer. n=1 per arm against a 50–290 s spread. **The tutorial run still dies within ~1–5 min and the cause is unattributed.** |
| **Generalisation, and it is the real value** | This is the **second** S9x diagnostic left switched on that quietly damaged every later run. Both were found by asking *what the shim was doing*, not what the game was doing. **There is no audit anywhere in the project of which compile-time flags a shipped shim actually carries** — `KCHEATSPAWN` is still ON and unexamined. That absence is the residual UNKNOWN here. |
| **Cheapest experiment** | Already run (~2 launches). The remaining one: enumerate every `#define K*` default in `tutorial_launch.cpp` and ask, per flag, *"is this a fix or a leftover question?"* **Minutes, offline.** |

---

### FK-27 — "Poking `EInternalObjectFlags::RootSet` keeps a shim-loaded asset alive, the way `AddToRoot` does"
**Severity: HIGH. Settled 2026-08-05 (S110) → `docs/s110-item-watch-gc-mechanism.md` §4d.**
**Status: the belief is DEAD, and as of the phase-locked run it is dead in the STRONG form: the bit is INERT, not raced.**

> ★★★★★ **MECHANISM SETTLED 2026-08-15 (S123) → `docs/fk27-successor-gc-rooting-settled.md`.**
> FK-27 closed on **outcome** and never on **mechanism**; the mechanism is now known and it came with
> a working rooting recipe. **The belief stays dead — nothing below reopens it.**
> - **Two unrelated survival mechanisms were being conflated.** (a) The disregard-for-GC pool is
>   excluded **by index**: `GUObjectArray` at RVA `0x9E38920` has `ObjFirstGCIndex = 39295`, and all
>   three whole-array sweeps iterate `[ObjFirstGCIndex, NumElements)`. Nothing below 39,295 is ever
>   traversed, marked or freed. (b) Real roots live in a **`TSet<int32>` registry at `.data
>   0x99D3CA0`** that `AddToRoot` inserts into *before* it ORs bit 30; the gather `ParallelFor`s over
>   the **indices** and the mark body has no bit-30 predicate. ⇒ **the flag is a mirror, and an
>   `InterlockedOr` never enters the gather.** That is the inertness, mechanically.
> - **[M] set-identity:** the registry's 32 members are exactly the 32 high-index bit-30 objects an
>   independent 200,475-object flag census finds. Zero symmetric difference.
> - **The recipe:** `AddToRoot` `.text +0x489F9B0`, `RemoveFromRoot` `+0x48B4BD0`,
>   `void __fastcall(UObject*)`, fold multiplicity 1 — a plain direct call, no `.text` write.
>   ⚠⚠ **the old poke POISONS it** (`SetRootFlags` early-outs on `Flags & 0x4E100000`), so `KGCROOT`
>   now defaults to **0**. Untested in flight.
> - **This entry's own §"Why weaker" row remains correct.** What is corrected is one sentence in
>   S110 §4c ("root-set objects are *excluded* from marking") and the `item_watch.py` "CHIMERA"
>   docstring: `RootSet + current mark` is the **normal** state of a genuinely rooted non-permanent
>   object, not a 0.03% anomaly. S110 §3/§4d had already recorded rooted objects being re-marked, so
>   the overturn is narrow.
> - ⚠ **46th instrument-artifact instance, committed by the session that settled this:** reading a
>   `TSparseArray`'s `ArrayNum` as its member count. `Num()` is never `ArrayNum`.

| | |
|---|---|
| **Belief** | `tutorial_launch.cpp:1209` states it as the fix: *"put every UObject this shim loads … into UE's GC root set, the same thing `UObject::AddToRoot()` does — it sets `EInternalObjectFlags::RootSet` in the object's `FUObjectItem`."* Carried from S106 through S109. |
| **Actual evidence** | Stock-UE semantics, reasoned about, never tested end-to-end. S109 §24 fixed the corroboration so the poke *happened* (`rooted=5 failed=0`, every write readback-verified `00000004 → 40000004`) and retracted half the claim by outcome — the asset still died, if anything sooner — but could not say why, because `GcAlive` cannot distinguish collection from teardown. |
| **Why weaker** | **MEASURED, one armed window.** The run `AnimSequence` was rooted at `t=187.845` with a verified readback and **destroyed 251 ms later** through the complete purge pipeline — `RF_BeginDestroyed` → `RF_FinishDestroyed` → `LowLevelRename(NAME_None)` → `FreeUObjectIndex`, with the index reissued to a new object 20 s later. It carried bit 30 continuously until the free (117 ms aliasing bound), and the engine **zeroed the flag word, RootSet included**, as part of freeing it. |
| **The real cause, and it is not the rooting** | Four other objects poked *identically in the same pass* survived, including **one of the two `AnimSingleNodeInstance`s** — same class, same code path, opposite outcome. The survivors were re-marked by the traversal because they are genuinely referenced; the run anim is referenced by nothing but a C global inside the DLL, which UE cannot see. ⇒ the fix is **a real reference from a reachable UObject** (or reload-on-death), never a bigger hammer on the flag. |
| **Steers** | The whole `GcRoot` subsystem — `KGCROOT`, `KGCROOTBIT`, `KGCROOTMAXPCT`, `KGCROOTSTRICT`, the `play-strictroot` control arm — and `docs/s109-dump-forensics.md` §22's "fixes, cheapest first", whose recommended real fix (#2, "re-resolve the root bit") is now known to fix a genuine bug that was never the animation's cause. |
| **Settled by the phase-locked run** | The one thing run 1 could not separate — *inert* vs *raced a pass whose root set was already gathered* — is now closed. Only the **injection phase** was changed (`-SkipProbe`, then inject by hand at a chosen point in the GC cycle). Three armed windows give a monotone series: lead **0.15 s → destroyed**, **2.9 s → destroyed**, **33.1 s → destroyed**. In the last, the bit was readback-verified and the object sat through **six consecutive 5 s heartbeats** before the pass killed it 708 ms after the flip. A root set gathered 33 s ahead of a pass that completes inside one 250 ms sweep is not a credible reading. ⇒ **INERT.** |
| **Timing-independent corroboration** | At a single pass in run 2, **six** objects all carrying bit 30 were traversed as ordinary objects: four were re-marked and survived, two were not (`ROOTED+STALE`) and were destroyed within 3 s. The engine's own ~4,913 root-set objects carry **no** reachability bit and are never marked. A poked object never joins that set. |
| **Cheapest experiment** | Already run (3 armed windows out of 6 launches; 2 NOSTAGE, 1 VOID). What it also killed: **the load does not provoke the GC.** The staging pipeline is deterministic and the GC clock is ~61.1 s from launch, so the load phase was near-constant across runs — that, not a load-triggered collection, is why S109's deaths clustered 1.1–7.8 s after body build. |

---

### FK-28 — "The `FUObjectItem` flag word follows stock `EInternalObjectFlags`, so `Unreachable` is bit 28"
**Severity: HIGH (it made a whole subsystem unreadable). Settled 2026-08-05 (S110).**
**Status: DEAD. ⚠ This does NOT retract S109 §25 — the field OFFSETS are correct. The SEMANTICS were assumed.**

| | |
|---|---|
| **Belief** | Implicit everywhere the flag word is discussed: `tools/re/uobjitem_layout.py`'s header, `s109-dump-forensics.md` §24–§25, and this document's own FK-24 thread. S109 verified the layout (`Flags@0x08`, stride `0x18`) and confirmed bit 30 is RootSet-like and bit 25 Native-like — then extrapolated the *rest* of the stock enum from those two hits. |
| **Actual evidence** | Two bits matching stock. §25 itself flagged the anomaly and left it open: *"bit 1 is set on 81% of ordinary objects and 0% of native classes … not a value in the stock `EInternalObjectFlags`. Unexplained."* |
| **Why weaker** | **MEASURED.** Reachability in this build is **a value, not a bit**: every live object carries exactly one of bits **0, 1 or 2**, and the whole population swaps which one on each GC pass (`bit1 → bit0 → bit2 → bit1`; 232 of 256 control objects flipped inside a single 250 ms sweep). An object is unreachable when it fails to carry the **current** value. **Bit 28 was never observed set on anything.** That *is* §25's unexplained bit 1, and §24's puzzling `flags == 0x00000004` on live assets. |
| **Corollary, measured** | Rooted and marked are mutually exclusive naturally: of 22,152 sampled live objects, **4,915 rooted of which 0% carry the current flag; 17,237 unrooted of which 100% do.** Root-set objects are *excluded* from marking. So `GcRoot`'s `InterlockedOr` produces a RootSet-**and**-marked state that 0.03% of the natural population is in — the shim's rooted objects do not look like the engine's. |
| **Steers** | Any future reasoning about GC state, and it retires "we cannot see the GC" — the flip is a **free read-only GC clock**. Measured spacing at rest is **61.1 s**, matching the game's own `gc.TimeBetweenPurgingPendingKillObjects = 61.1`; the tutorial map load shows up as a purge of 125,472 objects. |
| **Generalisation** | The same error shape as FK-14 and FK-18: a *partially* verified structure treated as fully verified. Two bits were checked; twenty-nine were assumed. **When a layout is confirmed, that confirms the offsets, not the enum.** |
| **Cheapest experiment** | Already run — `tools/re/item_watch.py`, read-only, at the **menu**, no tutorial window needed. |
| **★ S123 addendum — the rotation is now explained at CODE level** | `.data 0x99D36A0 / A4 / A8` hold the **Reachable / Unreachable / MaybeUnreachable values**, rotated O(1) per pass (`0x01258F70` at pass start, `0x012398C2` / `0x01239B76` at end) — the population is never rewritten, only the three globals are. Two cold images read `(2,4,1)` and `(1,2,4)`: applying the 3-cycle twice maps one onto the other exactly. Keep mask is `0x4E100000` = `RootSet\|AsyncLoading\|Async\|Native\|LoaderImport`. ⇒ FK-28's "reachability is a value, not a bit" was right, and this is the mechanism. **And stock enum numbering IS in force after all** — bit 24 `ClusterRoot` ⟺ `ClusterRootIndex < 0` at **100.000%** over 200,437 objects (0 FP, 0 FN), which upgrades bit 30 = `RootSet` from a name-guess to a measurement. `docs/fk27-successor-gc-rooting-settled.md` |

---

### FK-29 — "A `SerialNumber` change means the slot was recycled"
**Severity: MEDIUM, but it is the sharpest illustration in the register. Settled 2026-08-05 (S110).**
**Status: DEAD in both directions. It was the HEADLINE discriminator of the experiment it was wrong about.**

| | |
|---|---|
| **Belief** | `docs/next-session-prompt-s110.md` §0, stated as the decisive test: *"**`SerialNumber` changes** ⇒ the slot was **recycled**: the object was really destroyed and the index reissued. Decisive for 'real destruction'."* |
| **Actual evidence** | Stock-UE reasoning about what serial numbers are *for*. Never checked against a live object. |
| **Why weaker** | **MEASURED, twice, in opposite directions.** (1) UE allocates serial numbers **lazily**, in `AllocateSerialNumber`, the first time anything makes an `FWeakObjectPtr` — a live, untouched control object went `0 → 3373` inside 20 s at the menu with nothing else changing. `0 → N` is *a weak pointer being taken*. (2) `FreeUObjectIndex` **clears** it — the run anim went `63939 → 0` in the same 50 ms tick as `NamePrivate → 0` and `RF_FinishDestroyed`. `N → 0` is *the object being destroyed*. **Only `N → M`, both non-zero, is a reissue.** |
| **Steers** | It cost a verdict: the first tutorial run's own log prints `SLOT RECYCLED` for the run anim when the truth was `FREED`. The line is preserved, wrong, in `docs/s110-itemwatch-tut2-20260805-142308.log`; `item_watch.py` is fixed. |
| **Generalisation, and it is the point** | Direction (1) was caught **by the decoy control on the very first smoke run**, before a second of game time was spent — the run cost nothing because the instrument watched 256 objects it had no hypothesis about. Direction (2) was caught only because the *other* signals (`RF_FinishDestroyed`, `item.Object → 0`) disagreed with it. **Redundant signals are what turn a wrong rule into a caught rule.** |
| **Cheapest experiment** | Already run. |

---

### FK-30 — "The force-open hero has NO ability system"
**Severity: HIGH — it mis-sized the whole simulation route. Settled 2026-08-05 (S111) → `docs/s111-asc-census.md`.**
**Status: the belief is DEAD. The ASC exists, is populated, and is missing ONE field.**

| | |
|---|---|
| **Belief** | Stated everywhere the simulation route is discussed: `docs/next-session-prompt-s111.md` §0 ("the hero owns no ability system"), `memory/supervive-cheat-surface-inventory` ("the hero has no ASC, so cheats gate nothing"), and the shim's own verdict line `[GAS] ===== RESULT: initialised 0 -> 0 *** STILL NOT INITIALISED *** =====`. |
| **Actual evidence** | Three reads of the **hero pawn's** `AbilitySystemComponentStorage@0xF00` / `AttributeSetStorage@0xF08` / `AttributeSetHealthStorage@0xF10`, all NULL. `gas_recon.py` prints **"NO ASC on the hero"** from the same three reads and then *skips its own sections B/C/D*, so every follow-up inherited the conclusion. |
| **Why weaker** | **Those three fields are a CACHE, and S100 had already written that down** — "the real owner is `LokiPlayerState_HeroAffiliated`, a companion ACTOR carrying AbilitySystemComponent + AttributeSet + AttributeSetHealth". The conclusion was drawn anyway, by two different tools, and never cross-checked against the object graph. |
| **MEASURED** | Sweeping every ASC object in the process instead: spawning the hero takes ASC objects **424 → 425**, initialised **344 → 345**, `LokiPlayerState_HeroAffiliated` **0 → 1**. The hero's ASC is `0x274BDE53400`, `OwnerActor` = the companion, `SpawnedAttributes` **Num=2** (`LokiAttributeSet` + `LokiAttributeSetHealth`). Carrier fully populated incl. `PlayerInventory`. |
| **⚠ PROVENANCE — corrected same day** | **Those objects are the SHIM'S**, not the game's. `EnsureHeroAffiliatedCarrier` (`tutorial_launch.cpp:4511`) *spawns* the carrier, its constructor builds the ASC, and the shim's own `K2_InitStats` calls make both attribute sets (`[GAS] HeroAffiliatedObject@0x4F8 = 0x0` before → `carrier=0x27617F91750` after, the exact address the census attributed to the game). So the corrected claim is **"the shim's S101 carrier route got further than its own verdict line reported"**, not "the game wires the hero up". I swept live objects without asking which ones my own shim had created — the artifact question has to include *"…or about my own shim?"*. **The belief FK-30 kills is still dead**: the pawn's `@0xF00` fields are a cache, the ASC does exist, and the gap is two fields — but the reason it exists is us. |
| **The real gap** | `AvatarActor` is **NULL** (every scenery ASC has `Owner == Avatar == the actor`), so the ASC is never bound to the pawn — the second half of `InitAbilityActorInfo`. And `ActivatableAbilities` **Num=0**. The *granting* API is reachable as native thunks (`BP_AuthGiveAbilityWithInputID`, `AuthGiveAbilityWithSourceObject`, `TryActivateAbilityByInputID`). |
| **⚠ The BIND is not reachable that way** | Measured live: `LokiCharacter` has **`RemoveFromAbilitySystem` and NO add**; `LokiPlayerState` has only `TryUpdateAbilitySystem` (already called twice by the shim, verdict `0 -> 0`, and its own comment says "TryUpdate is update-not-create"); `LokiPlayerState_HeroAffiliated` has **zero UFunctions**. The Angelscript bindings expose `GetAvatarActorFromASC()` and no setter. `InitAbilityActorInfo` is C++-only. Writing the reflected `AvatarActor@0x410` alone is NOT equivalent — `AbilityActorInfo` (the `TSharedPtr` abilities actually read) is not reflected. **Offline anchors, base `0x7FF6505C0000`: `RemoveFromAbilitySystem` exec thunk RVA `0x5302ED0`, `TryUpdateAbilitySystem` `0x5438C20`.** The paired Add is usually adjacent. |
| **Steers** | The size of the whole simulation route ("reconstruct the ability-system init the server-authoritative deploy performs" — `gas_probe.py`'s own case (B)); FK-6's re-grade; and the S111 brief's Task One, which asked the right question and would have got the wrong answer from the existing tools. |
| **Second belief killed in the same sweep** | *"Nothing in this world has ever run the init; we would be first."* — which this probe itself emitted **from a world that was not loaded**. With `LVL_Tutorial` up there are **344 initialised ability systems** (`BP_Brush_C` x199, pine trees x134, and `BP_CapturePoint_Tutorial_C`). A negative measured in an empty world is not a negative. |
| **Cheapest experiment** | Already run, and it needed **no armed `play` window** — `gft` + `fo` to load the world, `sp` for the contrast, then `python tools\re\asc_census.py`. Three injections. |

---

### FK-31 — "`fo`'s slot-285 `.rdata` `CustomLogin` patch is obsolete now that S107/S108 made the world load reliably"
**Severity: HIGH (leading suspect for the tutorial route's now-dominant failure, and the obvious fix for it destroys the route).**

**FALSE — MEASURED 2026-08-08 (S112).** The S111 FK-7 handoff recorded this as "worth one build". It
was built (`-Variant fo-nologinvt`, `.text b834ff93827654aa`) and flown: **4/4 launches died, 0/4
loaded the map**, every one with the exact fatal the S62 source comment predicts —
`LogSpawn: Warning: Login failed: ALokiGameMode::Login failed to Login` -> `Couldn't spawn player`.
Fisher vs the `.rdata`-present baseline (13/51): **p = 0.0026**.

=> **The patch is still load-bearing; S62's purpose stands.** => **`KNOLOGINVT` must not be re-run.**
=> And the question it was meant to answer — *is `.rdata` caught by the protector too?* — **cannot be
tested by removal at all.**

**The open problem it was meant to solve is now the biggest one on the route:** **22 of 82 launches
(27 %) die during STAGING**, before the probe DLL is injected, with only `gft_ready_fix` + `fo`
resident. `gft_ready_fix` writes no module image, so the writer is `fo`, which makes **two**
module-image writes that are confounded in every run ever flown: a transient <=8 s **`.text`**
prologue jmp and a <=25.5 s **`.rdata`** slot-285 patch. Every dumped instance is `OURS/protector`.
Next design: **patch-then-immediately-restore** (shrink the `.rdata` window without deleting the
behaviour), then a heap expression of `CustomLogin` if that fails — `FsScan`/`FsThunk` is the worked
example. Detail: `docs/fk31-fk32-successors.md`.

WARNING — **not a re-filing of FK-26.** FK-26 was "the force-open dies *with no dump*" and is
REFUTED (that was an instrument blind spot). These deaths **do** dump and are classified. Different
open question.

---

### FK-32 — "The artifact-less death class is hangs — `CrashReportClient.ini` sets `Stall.RecordDump=false`, so hangs are *configured* to leave nothing"
**Severity: MEDIUM (it explained away a whole death class with a plausible mechanism nobody had tested).**

**FALSE for at least some of them — MEASURED 2026-08-08 (S112),** using an instrument nothing in this
project had used: **hold an OS handle open across process exit and read the exit code.**

| source | exit code | how measured |
|---|---|---|
| access violation (the protector's crash kill) | `0xC0000005` | 27 deaths, all under a `.text` writer |
| **our own `Stop-Process -Force` / `.Kill()`** | **`0xFFFFFFFF`** | run as an explicit control |
| the artifact-less death | **`0x0000DEAD`** | 2 deaths, both under non-`.text` builds |

`0xDEAD` is **not ours**: it appears twice in the shim sources, both as *read* sentinels, and there is
**no `TerminateProcess`/`ExitProcess` call anywhere in them**. => Some artifact-less deaths are not
hangs — they are **deliberate silent kills**, and the exit code recovers them for free. This also
answers FK-8's own section 7.2 item 2 ("crashes or `Stop-Process`?" — **neither**).

WARNING — **N = 2. Suggestive, not established.** The instrument is now permanent in
`configs/fk7-ab-run.ps1`, so **harvest this corpus; do not spend launches on it.**
Open residual: **3/36 armed windows (8 %)** still die with no module-image write anywhere.

---

### FK-33 — Batched: four instrument/artifact false-knowns from S112
**Severity: MEDIUM-HIGH (each one silently corrupts an experiment rather than failing loudly).**

1. **"`build\tutorial_launch_play.dll` is the FK-7 candidate build."** **FALSE — it was ONE COMMIT
   STALE** (`513c6277c3ae88f3`; HEAD builds `433cf7d8f6a0770f`). The intervening commit adds
   `PopulateHeroAscCache`/`ReportAscActorInfo`, and **`KWIREGAS` defaults to `1`**, so the gap was
   **live code, not dead**. A/Bing a new arm against it would have moved **two** variables.
   => **Rebuild from HEAD before any A/B**, and diff `.text` sha256 — never file size.
2. **"The 3x `play_novtguard` positive control is the mandated gate for an FK-7 sitting."**
   **FALSE — unaffordable, and aimed at the wrong thing.** It fires only on the camera family, ~8 %
   per staged launch, so `P(all 3 quiet) ~ 0.78` — it would declare **~4 sittings in 5 VOID even when
   everything works**. Replacement that works: RM_PLAY's own `[PL] *** init complete ***`
   (`tutorial_launch.cpp:5190`) — ~100 %, **arm-symmetric**, and it catches a silent no-op in a
   non-`.text` arm, which is that arm's most likely failure mode.
3. **"A new `dumps\crashpad-*` directory is evidence of a death."** **FALSE** — a stale PENDING
   report survived **11+ launches**, contradicting `archive-crashdumps.ps1`'s own premise that the
   next launch clears the database. => **Dedupe by report uuid.** (Related: CLAUDE.md claimed the
   archiver runs pre-launch *and* post-exit; it runs **pre-launch only**.)
4. **"`tools/crashtri/fk8_classify.py` can census the UECC tree."** **FALSE** — it dedupes on
   `splitext(basename)`, which is the **constant `"UEMinidump"`** for every UECC dump, so it reports
   **1 distinct report for 105 directories**. Its protector test is fine (`endswith("runtime.dll")`).

---

### FK-34 — "`UECC-C13252F5` is the one current-era FK-7 death that survives every contamination filter"
**Severity: MEDIUM (it was the last piece of evidence that FK-7 might be a game defect).**

**FALSE — re-classified 2026-08-08 (S112).** `RIP = SUPERVIVE+0x349596D` (`call [rax+0x2F8]`), READ AV
at `0xFFFFFFFFFFFFFFFF`, worker thread, chain `349596D-3405F13-3691A72` — **squarely the ANIM family**,
which S110 measured to be a **shim-lifetime bug** (a `UAnimationAsset` the shim loaded and never kept
reachable), and it **predates `KANIMREF`**.

It passes every *signature* filter and fails a *mechanism* filter. => **Zero FK-7 death records
survive a mechanism filter.** Its "258 s" is the launch clock; anchored to map load it is
**T+88.8 s**, unremarkable.

Related correction: `0x3495973` / `0x349596d` are **one** function at `0x3494B40`, and it **is**
animation code — `strxref` returns **four** literals including `[PreviousMarker %s, NextMarker %s]`
**twice**, plus Ticking Group / GroupLeader / Leader. S111's rename to "the tick task-graph
dispatcher" quoted 2 of 4 and is **wrong**; S106's `FAnimSync::TickAssetPlayerInstances` **stands**.

---

### FK-35 — S118 lobby/notif false-knowns (batched)
**Severity: MEDIUM-HIGH. Four beliefs, each of which steered work; all four MEASURED false.**
Primary evidence: `docs/fk15-bound-delegate-map-20260813.md`.

**(a) "The 33-name notif list in `vocabulary.go` is the dispatch enum."** **FALSE at the tail.**
Read live from the `TMap<FString,uint8>` at `.data 0x9FFE2D0` — the byte `HandleNotif` actually
dispatches on — the values are a perfect permutation of 1..33 and give **enum 32 =
`signalingP2PNotif`**, **enum 33 = `errorNotif`**, with **`messageSessionNotif` absent from the v1
map entirely**. `.rdata` image order IS the enum order for 1–31; what was wrong was *which strings
belong*.
★ **Root cause is the most instructive part: TWO off-by-one window boundary errors in OPPOSITE
directions that CANCELLED into a plausible 33.** The window excluded `signalingP2PNotif` (0x128
below its lower bound) and included `messageSessionNotif` (exactly ON the upper bound); the block
also contains `partySendNotifResponse`, a Response, so it only ever held 32 real types.
⚠⚠ **Two compensating errors are the hardest artifact to catch, because the independent count you
validate against PASSES.** The file's own comment warned about this exact failure mode and then
committed a different pair of it. ⚠ **And `push_test.go` asserted the false claim** — the test that
would have caught it had ingested it (method rule 9).

**(b) "`entries=3` on a bound delegate means three subscribers."** **FALSE.** The 16-byte record is
UE's **single-cast** `FDelegateBase` `{void* Alloc; int32 DelegateSize; pad}`; `3` is an allocation
size in 16-byte units and reads identically on every bound slot. `+0xC` is padding holding stale
heap garbage (it reads `0x1D2` even when UNBOUND), which is what made it look like a `TArray`.

**(c) "16 bound, 46 unbound" (S117).** **FALSE on both counts** — the scan stepped **0x10**, but
members also sit at offsets **≡ 8 (mod 16)**. At 8-byte stride there are **23** bound slots, and one
of the missed ones (`+0x228`) is **`disconnectNotif`**, a real notif delegate ⇒ **the miss changed a
conclusion (6 reachable types vs 7), not just a tally.** Compounding it, the published list was
**truncated at 12 of 16 and ended in a literal `…`**; four of the hidden offsets are four of the
seven answers, so joining against it yields 2 hits. **Never join against an ellipsis.**

**(d) "Presence can be driven both ways by setting `availability`."** **FALSE as stated, and it was
published UNOBSERVED** (asked for confirmation, was redirected, wrote it up anyway — method-rules
S118-g). `availability: offline` **parses cleanly and does nothing** while a valid `activity` blob
is present: **the activity OVERRIDES availability** ("has an activity ⇒ render online"). Omit
`activity` and it flips. ★ The retraction is what generated the experiment that found the override
rule — **retracting beat defending.**

---

### FK-36 — S120 Hero Mastery / reward-claim false-knowns (batched)

**Status: ✅ NEW + ALL SIX FALSIFIED (S120, 2026-08-14).** Primary evidence
`docs/s120-hero-mastery.md`; live artifacts in `dumps/s120-claim-evidence/` and
`dumps/claimflow-{BEFORE,AFTER}/`. Net outcome: **Hero Mastery is solved end to end, backend-only,
no shim and no `.text` write** — it renders, unlocks, its bars move, rewards are offered, and the
client claims them by itself.

| | belief | verdict |
|---|---|---|
| **a** | *"Roughly 293 of the 323 missions we serve are Hero Mastery content"* (asserted in `CLAUDE.md`) | ❌ **225.** The 25 shipped `LokiDataAsset_HeroMastery` name exactly 225 ids (3 sets × 3 tiers × 25); **none of the 75 abstract bases is referenced by any mastery set**, so serving them did nothing for this surface. |
| **b** | *"The client re-polls `/progression/players/{id}` every ~61 s"* (asserted in `interactive.go`, and the whole bump-every-change design rests on it) | ❌ **Once per messenger connection.** MEASURED: one fetch, then nothing for 8 minutes while the served Version advanced. ★ The working lever is `POST /api/ws/drop/{handle}` — S85's socket drop **generalises to `/progression`**, refetch within ~3 s, no Version guesswork. |
| **c** | *"`claimableRewards=[]` proves the reward is not claimable"* — published as a **CONTROLLED** negative because the notif was FRESH | ❌❌ **The control was never a control.** That field is `[]` in **30 of 30** occurrences corpus-wide (account pass included) — **no known-good case exists**, so it cannot discriminate "nothing claimable" from "this payload field is never populated". Freshness fixes *staleness*, not *validity*. Counter-evidence was already in hand: the client fetched `/progression` **exactly once**, with **zero relaunches**, so the very document called "not claimable" is the one it claimed from 11 h later. |
| **d** | *"A widget must offer the claim; the mastery Claim button or the lobby multi-claim is the trigger"* | ❌ **No widget offers it — the client AUTO-CLAIMS.** Reproduced on a fresh launch with **no user interaction**: the lobby tracker activates and the POSTs follow 1.5–4 s later. `WBP_UI_LobbyRewards` — the only asset in **69,178** that can invoke the bulk claim — logged **0 activations** in both sessions where the claim fired, and `WBP_HeroMastery_Mission_v2`'s Claim button is the **mission** claim (`/mission/rewards/claim`), a different route. |
| **e** | *"Mission progress written by the match-result engine is the progress the client reads"* | ❌ **Two disjoint name spaces.** The fan-out wrote **shim-manifest** composite keys while `missionInfo` reads **catalog** ones — overlap **7 of 187**; 180 writes were unreachable. Separately `objectiveRules` was keyed by the shim's objective names too: **2 of 102** catalog objectives had a rule (`BR_Knocks`→`Knocks`, `a2winarenagames`→`A2_WinArenaGames`, …). Fixed: trackable missions **3 → 22**, objectives mapped **2 → 20**. |
| **f** | *"A rendered UI surface reflects the current model"* | ❌ **Widgets bind to a STALE model generation.** Pushing progress to an already-open page changes nothing; the ingester rebuilds the model objects on each adoption and older widgets keep pointers to the previous generation. **This mis-diagnosed two separate surfaces in one session.** Rebuild the page (hunter switch / relaunch) before reading anything off it. |

★★ **The instrument that broke the deadlock — BEFORE/AFTER DECRYPTED-IMAGE DIFF.** The native caller
of the claim builder was invisible (its page was zero in a 52 %-decrypted image). `dumpimage` before
the action and again after: `.text` decryption is **monotone within a process lifetime** (FK-18/19),
so pages zero-in-BEFORE and non-zero-in-AFTER are **exactly the code that just ran**. Here: **20
pages / 80 KB**, containing the previously-unfindable call site `0x5849A68`. Chain recovered:
`BulkClaimAllProgressionTrackRewards` (thunk `0x5268FB0` → impl `0x58267D0`) → `FindVM 0x57AB180` →
`0x57ABCC0` (walks `VM.Levels` → `TArray<FClaimableReward>`, stride 0x58) → `0x5849790` →
`0x5827DA0` (`/hero/rewards/claim` URL builder) → `0x57EC800` (POST sender).
⚠ Function starts on this build are found by locating rel32 call **targets** landing in the page —
the int3-padding scan **does not work here**.

★ **Two independent instruments agreed the flow is pure native C++**: 0 of **35,148** live
`UFunction` objects have a `Func` in any newly-decrypted page, and a full-corpus census over
**69,178** assets found the hero claim referenced by **no Blueprint at all**.

⚠ **Unit discipline, a fresh sub-instance:** that census's positive control was published as
*"`ClaimReward` 24"* with no unit — it is **9 files / 24 occurrences**, so it reads as a file count
and is off by 2.7×. Both numbers were right; the ambiguity made the control uncheckable by anyone
else, which is most of what a control is for. **State the unit.**

---

### FK-37 — S121 feature-toggle false-knowns (batched)

All six died in one session. **Five of the six were the session's own arithmetic, predictions or
tooling** — not beliefs about the game. That ratio is itself the finding.

**(a) "The payload is applied but no surface appears; cause unresolved." — FALSIFIED, and it was
ONE WORD.** S120 shipped the toggle payload, measured the client applying it four times, saw nothing
change, and correctly refused to call it a negative. The cause was `ConfigKey`: the gate widget reads
`Map_Find(entry.Config, ConfigKey)` with a CDO default of **`"enabled"`**, and this project had
written `Config["default"]` since S73. Every lookup missed; every gate fell back to its own
`IsEnabledByDefault`. **~48 sessions of inert payload.** Serving both sub-keys lit 12 gates.
★ The honesty of the S120 write-up is why this was cheap to fix: it recorded "changed no observable
surface, cause unresolved" rather than "the toggles do nothing", so nothing had to be un-learned.

**(b) "17 dark keys are served." — FALSE; it is 16.** The number was never reconciled against the
payload. 16 + the 5 original enum-vocabulary keys = **21**, which is exactly what the wire carries.
A count that no instrument ever checked, repeated across two documents.

**(c) "33 declarative keys remain unswept." — FALSE; the remainder was 4.** 33 is the
**never-serve** count (`IsEnabledByDefault=true`), the same number in a different role. The full
partition closes with no remainder: 50 = 12 served + 33 never-serve + 1 withheld + 4 candidates.
⇒ **carried numbers must be re-derived, especially when they look familiar.**

**(d) "`mastery` is a dark key." — FALSIFIED by live measurement.** 3 of its 6 widget instances read
`IsEnabledByDefault=true`: it was **always on without us**. Serving it was a no-op; serving it
`false` would have REMOVED the S120 hero-mastery surfaces. It is now in the never-serve list and
pinned by a test.

**(e) "Adding 3 keys will flip 6 instances." — WRONG; it flipped 3.** The second instance of each key
is the widget-tree **archetype**, which never evaluates. That rule had been written into
`docs/s121-toggle-fix-confirmed.md` §3b **one hour earlier by the same session**, and was not applied
to its own prediction. The direction was right and the arithmetic was wrong — record both, because a
pre-registered prediction that is half wrong is still what caught it.

**(f) `class_props.py` says `not found (map not loaded yet?)` for a class it can NEVER find.** It
locates a UClass by requiring the class-of-class to be `"Class"`; a Blueprint class's is
`BlueprintGeneratedClass`. The message invites "the map isn't loaded", which is a statement about the
*game*; the truth is a statement about the *tool*. **Third member of the class-lookup blind-spot
family** after `obj_by_class.py` (substring) and `cheat_reach_probe.py` (endswith) — and CLAUDE.md
already warned that two instruments failing the same way are not corroboration.
`tools/re/toggle_readout.py` sidesteps it entirely by resolving the class from a **live instance**.

⚠ **A near-miss worth recording as such, not as an instance.** `AGS_UI_TOGGLES_EXTRA` changes the
served payload at **runtime**, so there is no code edit at which to hand-bump the eTag — the knob
would have silently reproduced the stale-eTag-over-changed-content failure documented three
paragraphs above its own definition. It was caught in design and the eTag now folds the extras in
automatically. **This is the first recorded case of the instrument-artifact pattern being
anticipated rather than discovered in the evidence**, which is the direction the register should be
moving.

★ **Method contribution: verify a guard by reintroducing the bug.** `internal/loki` had no test file
at all, which is *why* one wrong word survived ~48 sessions. The new
`TestEveryToggleCarriesTheEnabledSubKey` was confirmed to **fail on the reverted code**, naming every
affected key, before it was trusted. A guard nobody has seen fail is not a guard.

---

### FK-38 — S121 late-session RE false-knowns (batched)

The second half of S121 was continuous live RE. It produced **~16 wrong-then-corrected claims, and
about fourteen of them were the analyst's own reasoning or tooling, not beliefs about the game.**
All were caught in-session, most within minutes, every one by a readout rather than by more thought.

**The two expensive ones**

**(a) The wrong prompt stack.** Chasing why the MOTD prompt never displayed, I measured
`MainMenu_NormalV2.PromptStack` (`WidgetList Num=0`) across several steps and built conclusions on
it. **Two `PushPrompt` implementations exist**; the call actually routes RootV2 → (inherited)
`BP_LokiHUDWidget_C` → **native `ULokiHUDLayout`** → `CommonActivatableWidgetStack_Prompts`, which
holds the widget. ⇒ **I had the address of the true target object three commits before I dumped its
properties.** Tracing call graphs substituted for dumping an object already in hand.

**(b) A green test suite over a wrong spec.** The UDP echo responder gated on UE 5.4's stock 22-byte
ping. **The shipping client sends 30.** Five tests passed — including one running the client's own
validation — while every real ping was silently dropped, because the tests built the same 22-byte
packet the gate expected. ⇒ **read the source for a protocol's SHAPE; let the wire tell you its
SIZE.** Caught only by a dropped-datagram counter added "just in case".

**The rest, compressed** — each was stated, then measured false:
`motd`'s payload is wrong · `Try Show MOTD` is never called · the widget is not presented ·
`PushPrompt` ran against a null stack · RootV2 does not implement `PushPrompt` (an asset-only
`bpdump`; it inherits it) · `Try Start Onboarding Flow` is not the caller (too strong from a partial
measurement) · the gated array is `Matches` (it is `MissionInfo.MissionData`) · `Slot == null` means
not displayed (legitimate for a container child) · the fault page is unmapped (dump *coverage*, not
mapping — the control refuted it) · zero measurers means the payload did not bind (a confounded
proxy; the struct had bound perfectly).

★★ **Two NEW failure modes this register had not recorded before:**

1. **A correctly calibrated instrument aimed at the WRONG QUESTION.** The viewport probe was
   validated to 2-of-5064 and still produced a false conclusion, because "not added directly to the
   viewport" is not "not on screen" for a container child. **Calibration makes a wrong answer feel
   earned** — arguably worse than an uncalibrated one.
2. **OVER-correction.** After several retractions I began discounting evidence that was in fact
   sound (doubting `Try_Show_MOTD_Widget`, which really was the live widget). Distrust that is
   calibrated to one's recent error rate rather than to the evidence is its own bias.

⚠ **And the repeat offenders, which is the uncomfortable part:**
- **A stale constant eTag shipped on `/core-game/regions` ONE HOUR after fixing that exact bug class
  on client-config and writing it up.** Both are content-derived now — the fix that removes the
  failure mode instead of relying on memory.
- **My own probes filtered out nulls and empty arrays TWICE**, making "empty" indistinguishable from
  "absent" — absence-is-not-evidence, inside instruments written to defeat exactly that.
- **A grep narrowed for speed** (`catalog/wbp/` only) silently narrowed the answer and missed both
  `PushPrompt` callers; the full scan finishing in the background is the only reason it was caught.
- **"Not in the asset I dumped" ⇒ "does not exist"** was warned about in one commit message and
  committed one step later.

★ The one trend worth claiming: by the end, caveats were being written **before** the measurement
rather than after — the last three claims each shipped with the control that would falsify them, and
two were duly falsified.

---

### FK-39 — S123 GC/rooting false-knowns (batched)
**Severity: HIGH (one of them silently blocked its own fix for ~17 sessions). Settled 2026-08-15
(S123) → `docs/fk27-successor-gc-rooting-settled.md`.**
**Status: all DEAD. FK-27's verdict is UNAFFECTED — these correct its *explanation*, not its outcome.**

| # | Belief | Why it was believed | What is actually true [M] |
|---|---|---|---|
| **a** | **"Root-set objects are EXCLUDED from GC marking"** — `s110-item-watch-gc-mechanism.md` §4c, from a contingency table reading `4,915 rooted / 0% marked` | the table is real and was measured over 22,152 sampled objects | **A POOLING ARTIFACT.** That bucket mixed ~39,275 **disregard-for-GC pool** objects (index < `ObjFirstGCIndex` = 39295, never traversed at all — every sweep iterates `[ObjFirstGCIndex, NumElements)`) with exactly **32 real `AddToRoot()` callers**, which are marked **every pass**. S110's "6 of 4915" *is* those 32. **Non-circular proof:** 20 live pool objects that LACK bit 30 are also never marked and never collected — a flag-driven GC would have purged them |
| **b** | **"`RootSet` + a current mark is a CHIMERA, 0.03% of the natural population"** — `item_watch.py:738`, and the instrument printed this label about the shim's own object | rarity in the pooled census | **It is the NORMAL, CONTINUOUS state of a genuinely rooted non-permanent object** (all 32, always). ⇒ the shim's poked object had the **correct flag word** the whole time, and the instrument's warning was backwards |
| **c** | **"Setting the RootSet bit is what `AddToRoot` does"** — `tutorial_launch.cpp:1218`, carried S106→S122 | stock-UE semantics, reasoned about | `AddToRoot` **inserts the `InternalIndex` into a `TSet<int32>` registry at `.data 0x99D3CA0`** (under the lock at `.data 0x9E23BF0`) and *then* ORs bit 30. The gather (`0x1259020`) `ParallelFor`s over the **registry indices**; the mark body `0x123E3B0` has **no bit-30 predicate**. **The container is the input; the flag is a mirror.** [M] registry `Num()` = **32**, *set-identical* to the 32 high-index bit-30 objects (zero symmetric difference) |
| **d** | ⚠⚠ **"`KGCROOT` is harmless dead code"** — implied by leaving it defaulted ON after S110 measured it inert | inert ⇒ assumed to be a no-op | **IT BLOCKS ITS OWN REPLACEMENT.** `SetRootFlags` (`0x129AC90`) early-outs on `if (Flags & 0x4E100000) skip the insert`, so any object the shim already OR'd looks "already a root" and a **correct** `AddToRoot` call silently skips `GRoots.Add`. Default flipped to **0** (S123); `play` `.text` `5151621d2154e454` → `9bc10a4552c596e1`, rollback `-Variant play-gcroot` **verified to reproduce the old hash exactly** |
| **e** | **"`ObjFirstGCIndex` and friends were unreachable"** — never stated, but nobody had them in ~120 sessions | — | They sit **0x10 BELOW** the constant everything anchors on. `RVA_OBJOBJECTS = 0x9E38930` (in `tutorial_launch.cpp:23`, `item_watch.py:60` and ~20 shim sources) is `FUObjectArray + 0x10`, the *inner* `ObjObjects`. `FUObjectArray` is at **`0x9E38920`**. ⇒ **a correct-but-partial anchor hid an adjacent structure for the project's whole history** |

**Generalisation, and it is the reusable part.** Three of these five are the same shape: **a category
label applied to a set containing two mechanisms.** "Rooted" meant both "permanent" and "registered",
and every statistic computed over it was a weighted average of opposite behaviours. ⇒ **before
computing a rate over a labelled population, ask whether the label is one mechanism or two** — and
split by an independent axis (here, `InternalIndex`) to find out.

**Cheapest experiment:** already run, and it cost **zero launches** — read-only RPM against a menu
process that was already up, plus offline disassembly. `tools/re/rootset_census.py`.

⚠ **Three instrument-artifact instances were committed by this session itself** (`TSparseArray.
ArrayNum` read as `Num()`; a derived boolean recorded instead of the raw flag word; a p-value against
a refuted null) — tabulated as S123-a/b/c in `docs/method-rules.md`. The first was used to formally
challenge a subagent's *correct* result.

---

## 3. The UNKNOWN_UNKNOWN Register

Questions never posed in ~100 sessions of docs, memory, tools, `CLAUDE.md` or 366 commits.
`[×N]` = independently rediscovered by N dimensions — a strong signal it matters.

### Theme A — The game already told us, in artifacts we generated

| # | Unknown | Evidence it was never asked | Cost | Value |
|---|---|---|---|---|
| A1 | **What do the 149 game-feature toggles enumerate?** `schema.txt` contains `ELokiGameFeatureToggle (151 values)` with every member named — `RecordReplays=5`, `SpectatorViewAllTeams=11`, `IgnoreClientVersionDangerous=2`, `ValidateConnectionSecret=36`, `SkipCosmeticFeatureOwnershipValidation=69`, `Missions=25`, `Armory=106`, `AutoClaimMissionRewards=102`, `TrainingBattleRoyale=63`, `BotsKeepMatchesAlive=96`, `InfiniteMana=95`, `GoldForEverything=100`, `CustomsArmoryUnlock=131`, `Season_0=88`, `EnableTalentSystem=12`, `Forges=38`, `BoatShops=24`, `QuestGivers=19` | The enum **name** has ~20 prose hits; **not one hit lists a member**. Every member name = 0 hits in prose, code, configs, memory, and 9,631 lines of commit bodies. S88–S90 drove the carrier by numeric **seed** (1, 75, 151 — 151 is out of range, MAX=150; 75 is `ClientSpellBuffering`) | **minutes** | **CRITICAL** |
| A2 | **`PartyModel+0x558+0x18` is `Party.State`** — the mode-string gate `TryStartSoloMode` bails on, currently worked around with a per-launch memory poke | Recorded as *"key not yet mapped"* in 3 places (`interactive.go:832`, `session-62:127`, `next-session-prompt-s62:123`) while `schema.txt:40988` gives `Party = ID(FString@0x00)/Version(Int64@0x10)/**State(FString@0x18)**/ClientVersion(@0x28)/IsOpen(@0x38)/FillTeam(@0x39)/OwnerID(@0x40)/DiscordJoinSecret(@0x50)` — byte-exact against S61's live layout, and `EPartyState={Default,Matchmaking,CustomGame,Unknown}` matches both compared literals | **minutes** | **CRITICAL** |
| A3 | **`Binds.Cache` is a 5.76 MB offline reflection oracle** — 10,366 reflected types (1,422 `/Script/Loki.*`), **15,068–15,209 full UFunction signatures with named/typed params and default arguments**, complete USTRUCT field lists. Verified against three known-good facts: `MulticastSetGameFeatureToggle(ELokiGameFeatureToggle,bool)`, `FParty`'s 16 fields incl. the `int64 Version` S85 fought, `UMissionsModel CreateMissionModelFromFinalProgress(const TArray<FMissionProgress>&)`. Also `FGameplayAbilitySpecHandle AuthGiveAbilityWithInputID(TSubclassOf<UGameplayAbility>, int, LokiAbilityInputID, UObject, int=0)` | `binds.cache` = 2 naming-only doc hits (S74), **0 tools**, 0 commits. No parser exists | **hours** | **CRITICAL** |
| A4 | **The game's own description of itself.** `DT_LoadingScreen_GameMode.json` names every queue in the developers' words (`default`=**Breach**, BR vs teams of 3; `deathmatch`=**Arena**, 4v4; `domination`=hold Basecamps; `prismabank`=**Prisma Party**) and `DT_LoadingScreenTips_ModeExplainer.json` states the core loop verbatim: *"Pick your drop, battle for Prisma and Coin, buy gear at Shops, and avoid the storm. Last team standing wins!"* | `ModeExplainer` / `LoadingScreenTip` / `QueueDisplayDataTable` = 0 hits. Both files have been on disk since the catalog run | **minutes** | **CRITICAL** |
| A5 | **`ELokiGameModeType` has 7 real modes** — BattleRoyale, LastMan, **Barracuda**, Tournament, **Domination**, **PrismaBank** | `ELokiGameModeType`=0, `PrismaBank`=0, `Domination`=1 (round-1 note), `Barracuda`=3 (all as a hero/queue string) | minutes | HIGH |
| A6 | **The 64 already-extracted StringTables define the whole in-match economy and match-end model** — `ST_Currencies` (Gold=Coin, Gems=Prisma, Tears=Shards, with "Collect Prisma to forge new Armory items"), `ST_Codex` (Powers/Exotics/Consumables/**Stormshifts**), `ST_XPCategories` (ROUNDS WON / MISSIONS / SURVIVAL / ROUNDS LOST / TOTAL), `ST_DeathNotification`, `ST_LeaveMatch`, `ST_OrdinalPlacements`, `ST_SetBonuses`, `ST_Squawks`, `ST_HeroMastery`, `ST_ServerLocations` | `Codex`=0, `Stormshift`=0, `SetBonus`=0, `Squawk`=0, `ST_XPCategories`=0, `OrdinalPlacement`=0. The audit scores *"String-table keys 1,780 — 100%"* — **a semantic layer marked complete on a key count** | **minutes** | HIGH |
| A7 | **113 shipped DataTables never triaged** — incl. `DT_AugmentWeightList`, `DT_AccountLevelCrowns`, `DT_GameAbilityTooltip`, `DT_GameplayEffectTooltip`, `DT_UniqueInputs`, `DT_LokiEvictionMessages`, `DT_QuestAugmentText`, and **75 per-hero Bark tables** whose *trigger* column is a free enumeration of in-match event types | `DT_`=13 prose hits, none naming any of these; `AugmentWeightList`=0, `bark`=2 incidental | hours | MEDIUM-HIGH |
| A8 | **`LokiStatusDumpSubsystem`** — a WorldSubsystem with one `OnStatusDumpRequested` multicast delegate. The game may ship the live state-dump facility the project builds ever-larger bespoke probes to replace | 1 hit, and it is the auto-generated schema line itself | hours | HIGH |
| A9 | **`LokiAutoMatchmakeComponent` + `LokiAutoJoin` + `LokiGameAutomation(Manger)`** — an `Automation/` namespace where `LokiAutoMatchmakeComponent` holds live `PartyManager` + `PartyModel` object refs plus `AutomationTickSpeed`/`MinimumSecondsReady`: a shipped component built to drive the party model into a queue unattended | 0 hits across docs, memory, CLAUDE.md, git | hours | HIGH |
| A10 | **`DemoNetDriver` / `ReplaySubsystem` / `ELocalFileReplayResult` / `LocalFileNetworkReplayStreaming` are all present** — and `RecordReplays` is toggle #5. A replay is a *fully simulated match* played back with no server and no authority problem | `DemoNetDriver`/`ReplaySubsystem`/`demorec` = 0 outside `schema.txt`; all 32–48 "replay" hits are the project's own S32 RPC self-replay harness — an unrelated homonym | hours | MEDIUM ⚠ |
| A11 | **`LokiBot*` family** — `LokiBotManager`, `LokiBotController`, `LokiBotSpawnerComponent`, `LokiBotTeamPlannerComponent`, `LokiBotDifficultyConfig`, plus `BP_Minion_TargetDummy.uasset` and `Bots/BP_BotSpawnLocation.uasset`; and `CoreGameBotConfig{BotTeams, FillPartialTeamsWithBots, BotTeamDifficulty, AllyBotDifficulty}` is a **field of the GameConfig we already serve and omit** | `LokiBotManager`/`BotSpawner`/`FillPartialTeamsWithBots` = 0 in docs, memory, server | one session | HIGH |

> ⚠ **A10 caveat:** no `.replay` file exists and no `Saved/Demos` directory exists, so playback needs a recording and a recording needs the running match that is the blocker. High ceiling, uncertain reachability.
>
> ⚠ **A3 scope limit (load-bearing):** `Binds.Cache` class member lists are the **script-visible subset**. `ULokiServerAuthConfig` lists **1** property (the toggle array is absent); `UCatalogManager` lists 3 delegates (the `+0x354` flag is absent). **USTRUCTs are complete; classes are not** — so this replaces the crash-driven *signature*-recovery loop, and does **not** replace RPM for native offsets.

### Theme B — The client writes about itself, on disk, in plain text

| # | Unknown | Evidence | Cost | Value |
|---|---|---|---|---|
| B1 | **`UserSettings.ini`** [×4] — 186 ActionMappings + 16 AxisMappings (FK-2), 43 `Cheat*`/`Dev*` actions, `HasSeenTutorial`/`HasPlayedTutorial`/`HasSeenOnboardingModal`/`HasSeenRankedPopup`, `InGameShopItemDisplayPreferencesByHunter`, `CustomGamesListDisplayFilterPreferences`, `[/Script/Loki.VivoxRegistry]`, `[/Script/Loki.MailboxModel]` | `UserSettings.ini` = **0 hits** repo-wide, 0 commits; `PlayerConfigManager` = 4 hits, all auto-generated schema | **minutes** | **CRITICAL** |
| B2 | **`GameUserSettings.ini`'s `[LokiTraining.*]` ledger** [×2] — four sections listing **24 named training skills with integer counters**, several non-zero (`TrainingSkillWASD=2`, `BP_TrainingSkill_Glide=3`, `BP_Training_Skill_Food=2`), from real 2024-11-25 live play. Also `BP_Training_Skill_UnlockAllAbility` | `GameUserSettings`/`HasPlayedTutorial` = 0 hits; the 9–10 `LokiTraining` hits are all about the runtime BP classes, never the file | **minutes** | HIGH |
| B3 | **`menu_slider_master = 0.000000`** — persisted master volume is muted, all seven other buses at 1.0. The audio device manager initialises cleanly (stock UE OPUS/OGG/ADPCM/PCM, no Wwise/FMOD in-process) | `VolumeSettings`/`menu_slider` = 0 hits. **No session in ~100 has ever recorded listening to the game**, while 8,716 audio events are indexed and 0 bytes exported | **minutes** | MEDIUM-HIGH |
| B4 | **The 86-crash corpus (2.0 GB)** [×5 — the single most independently-rediscovered artifact in this audit] — 86 × {`CrashContext.runtime-xml`, `UEMinidump.dmp` (13.7 MB), a frozen pre-crash `Loki.log`}. Verified aggregate: **23,765 exe stack frames → 512 distinct `.text` RVAs across 7 ASLR bases**, with the module base printed in the same document, against a project total of ~617 known addresses. Error histogram: 15× AV@0x0, **11× `Couldn't spawn player: ALokiGameMode::Login failed to Login`**, **6× `PlayerState is null`**, 7× `FMallocBinned2` canary. 17 fatal asserts leak `C:\TheoryCraft\build-staging\Engine\Source\…` with file+line | 5 doc hits, all single-incident from S40–S45; `CrashContext`=2–3; **0 tools parse one** | **hours** | **CRITICAL** |
| B5 | **Minidump stream 13 = the entire missing `.pdata`** — `SizeOfDescriptor=32, SizeOfFunctionEntry=12, NumberOfDescriptors=7`; descriptor 1 based at the exe module base with **524,439 RUNTIME_FUNCTION entries** spanning RVA 0x8a00→0x7649f39. On-disk `.pdata` is encrypted (entropy 8.00); in-memory `.pdata` is **all zero**. This is the only known source | `FunctionTableStream` = 0 hits; the audit states the *consequence* (blind spot #8, "no `.pdata`, so Ghidra recovers every boundary heuristically") and never asks where the data could come from | **hours** | **CRITICAL** |
| B6 | **Minidump `ModuleList`: 217 modules with FULL PATHS**, captured at crash time — the "what else is in the process" instrument the project does not have. It settled the UE4SS question in one parse (`C:\WINDOWS\SYSTEM32\dwmapi.dll`, no UE4SS.dll). Also shows **`runtime.dll` mapped TWICE** at two unrelated bases (0xff760000 and 0x7ff8f0400000) — a second body of executing code outside the whole `base+0x…` address model | No tool prints module full paths; `tools/re/dump_modules.py:18` uses a hardcoded name allow-list | **hours** | HIGH |
| B7 | **`Saved/ImageCaches/ImageCacheIndex.json`** [×3] — maps 55–56 cached JPGs to their exact live-CDN URLs, all on `content-service-jx-prod.prodcluster.awsinfra.theorycraftgames.com/content-service/assets/prod/*`. Filenames name a whole unenumerated surface: `Client_T2_{Battlepass_Season0, CosmeticsTrailer, NewSkins, WinterEvent, Roadmap, PatchNotes_Week1, SupporterPack, EarlyBird, RAF}`, `Interstitial_*`, creator cards. Our server implements `/content-service/manifest` but nothing serves the asset feed | `ImageCaches`/`content-service-jx-prod`/`Interstitial_`/`Client_T2_` = 0 hits. ⚠ Nothing newer than 2025-08-21 — this is a **historical live-service capture**, not current egress | **minutes** | MEDIUM-HIGH |
| B8 | **`Saved/Logs/AccelByteGeneralCache`** — 2,520 B, obfuscated by a +1 byte shift; decodes to `{"key":"DeviceId",…}` and `{"key":"76561197981196360",…}` — a real SteamID64-keyed credential blob from the live service | 0 hits | minutes | MEDIUM |
| B9 | **`Loki_PCD3D_SM6.upipelinecache` (4.2 MB)** — a UE PSO cache only grows when a *never-before-compiled* pipeline is encountered, making it a monotonic, machine-readable ledger of every render state this install has actually reached, with an mtime dating the last novel one. Exactly the state-novelty metric the project lacks | `upipelinecache`/`pipeline cache` = 0–1 hits | minutes | MEDIUM |
| B10 | **A second and third `Loki.log`** [×2] — `Loki/Binaries/Win64/Loki.log` (194,659 B, a real ~5-hour session with the full IoStore mount trace and per-container Toc signature hashes), plus 79–86 frozen pre-crash copies in the UECC dirs. CLAUDE.md names exactly one path and explicitly warns off one *wrong* path — it does not know these exist. UE also rotates to `Loki-backup-*.log` and prunes | 0 references to either | minutes | MEDIUM |
| B11 | **`Game.ini` `[LokiHardwareSurvey] Version=3 / Changelist=156430 / Date=…`** — the client runs a versioned hardware survey and records it; and the changelist the audit says exists "in prose in exactly two places" is here, machine-readable and game-written | `LokiHardwareSurvey` = 0 hits | minutes | LOW-MEDIUM |

### Theme C — Game-tree artifacts nobody opened

| # | Unknown | Evidence | Cost | Value |
|---|---|---|---|---|
| C1 | **`Manifest_DebugFiles_Win64.txt` declares a shipping PDB** — `Loki/Binaries/Win64/SUPERVIVE-Win64-Shipping.pdb  2025-12-12T19:54:54.727Z`, alongside `CrashReportClient.pdb`. The exe carries a valid RSDS record: pdb `SUPERVIVE-Win64-Shipping.pdb`, **GUID `BFDF6AC92124A921265B0B1B20B4E343`, age 1**. Steam titles routinely publish a separate debug depot (appid 1283700) | `RSDS`, `symbol server`, `symsrv`, `download_depot`, `Manifest_DebugFiles`, `Shipping.pdb` = **0 hits** across the repo, memory, and 366 commits | **minutes to test** | **CRITICAL** |
| C2 | **The three shipping manifests + `buildID`** [×4] — `Manifest_UFSFiles_Win64.txt` (23.8 MB, **192,647** path+ISO-timestamp lines), NonUFS (269), DebugFiles (8), `buildID = tlFJuYwW9-`. The NonUFS list also reveals `Engine/Plugins/SentrySDK/Binaries/Win64/crashpad_handler.exe`, `GfnRuntimeSdk.dll`, the CEF3 payload — and **no EAC binary** | `Manifest_UFSFiles`/`Manifest_NonUFS`/`buildID` = 0 hits, while audit item 0.8 proposes *constructing* a build fingerprint from scratch | **minutes** | HIGH |
| C3 | **56 loose, unencrypted, immediately-playable `.mp4` files (416 MB)** [×3] — `ClickTutorial/` has 35 narrated mechanic clips (Deathbox, MostWanted, Oracle, RespawnBeacon, Wisp, SoulBosses, SupplyDrop, Vaults, Basecamp, Recall, Cooking, Armor, MinionCamps, XP, LevelCap, Drop, Sneak, Glide), `InGameTutorial/` has 13 mapping 1:1 onto the lesson chain, plus `DropPhase_DropMapTransition/`, `EOG_LevelUpCeremony/`, `EOG_Placement/`, `GameFeatureUnlocks/`, `Onboarding2024.mp4` (73.5 MB) | `Movies`/`.mp4`/`ClickTutorial`/`Onboarding2024`/`SNF_Tutorial` = 0 hits. **The only footage of a real SUPERVIVE match obtainable without a server** — and the developers' own explanation of every system the project reconstructs from symbol names | **hours** | HIGH |
| C4 | **`thirdpartylicenses.txt`** [×2] — the protection layer's real bill of materials (see FK-10) | 0 hits | minutes | HIGH |
| C5 | **`runtime.dll` is a crash uploader with off-switches** [×2] — wide strings: `o566896.ingest.sentry.io`, `/api/5710262/minidump/?sentry_client=packer/3.3.1&sentry_key=149a7ac2…`, `Making a full dump!`, `PACKER_%llu_%llu.dmp`, `Uploading started…`, `Upload finished (HTTP code: %lu)`, and **`DUMPER_SKIP_UPLOAD`** / `DUMPER_KV_MAX`. It speaks mbedtls over WINHTTP, so it bypasses both the hosts redirect and `cacert.pem`; it is manually mapped, so it is not even enumerable as a module. **86 crashes have occurred.** Plausibly, full minidumps of a process containing our shims have been uploaded to a third party throughout | `DUMPER_SKIP_UPLOAD`/`PACKER_CRASH`/`SUPERVIVE_NO_SENTRY` = 0 hits; the audit noticed 2 Sentry requests and never asked what the payload is | **minutes** | HIGH |
| C6 | **`SUPERVIVE.exe`'s launch-time lever surface** — `-NoEAC`, `-NullEAC`, `-ReinstallEAC`, `-NoSentry`, `-NoPackerCrashTags`, `-SetPackerTags`, `-CustomCrashTag`, `-NoDelayCrashRegistration`, `-IncludeDumperJson`, `-NoISPC`; env vars `SUPERVIVE_NO_SENTRY`, `SUPERVIVE_NO_ISPC`, `SUPERVIVE_LOG_ID`, `SUPERVIVE_EAC_PRODUCT_IDENTIFIER`, `PACKER_CRASH_FLAGS`. `LokiGameInstance` also has a `CommandLineTokens` property — the game parses its own token set, never enumerated | `NoEAC`/`start_protected_game`/`SUPERVIVE_NO_SENTRY` = 0 hits. ⚠ *The launcher runs `SUPERVIVE-Win64-Shipping.exe` directly, so these are reachable only if the launch path changes* | minutes | MEDIUM-HIGH |
| C7 | **The anti-tamper detection taxonomy** — `preloader.dll` (26 KB, **unpacked**, ntdll-only imports) carries `Conflicting software detected!`, `PACKER_CRASH_AT`, Wine/Proton/Steam-Deck refusal, `Syscall emulation is disabled in this Wine build…`. `SUPERVIVE-Diagnoser.exe` (0 hits) adds the vendor's own words: *"Incompatible tools are running concurrently with the game"*, *"debuggers, injectors, cheats, or … virtual environments"*, **`DLL Load Failure Log (unsigned file):`**, `Last SUPERVIVE Crash Exception Code`, and a `wevtapi` Application-Error query | `Conflicting software`/`PACKER_CRASH_AT`/`Diagnoser`/`SUPERCODE`/`COMPATIBILITY_LOG` = 0 hits. ~100 sessions of unexplained deaths have **never tested deliberate termination** as the alternative to "the packer's exception handler kills the process" (N=3 canaries) | hours | HIGH |
| C8 | **`Loki/Config/BlackBox.ini`** [×2] — one of only 10 packed Loki config files, ship-dated 2025-12-12, and **`BlackBox` occurs 0 times in `dumps/merged.dump.exe` in both ASCII and UTF-16** — nothing in the unpacked game image names it. Ship-time config + no consumer in the game image is the signature of anti-tamper/telemetry configuration | 0 hits repo-wide | minutes | MEDIUM-HIGH |
| C9 | **18–19 first-party `Loki/Plugins/*`** [×2] — `LokiSocketSubsystem` (a **custom socket subsystem**, sitting under a ~20-session netcode/DS effort that assumes stock UE sockets — 1 incidental hit), **`GameFeatures/LokiWinter`** (a real shipped GameFeature plugin, unnoted through all of S88–S90's game-feature-toggle work), `GameEventRouter`, `ImageCache`, `MinimapPlugin`, `MORT`, `Agones`, `SplineArea`, `AssetsCleaner`, `ElectronicNodes`, `LowEntryExtStdLib` | `LokiSocketSubsystem`=1; `MinimapPlugin`/`MORT`/`LowEntryExtStdLib`/`AssetsCleaner`/`ElectronicNodes` = 0 | hours | HIGH |
| C10 | **The Modulate ToxMod stack** [×3] — `Loki/Plugins/Tox/` ships `libtox.dll`, `opus.dll`, `opusenc.dll`, `fvad.dll` (voice activity detection), `zlib1.dll` and **its own `libcurl.dll`**; the exe carries `ToxModManager.cpp`, `ToxVivoxConfig.cpp`, *"Hooking in Tox audio processor to Vivox audio callback"*, *"ToxMod initialized for player: %s"*, and `https://api-console.modulate.ai/SubmitUserReport` with a 9-field `CreateUserReportRequest`. A private libcurl means a private cert store — invisible to `cacert.pem` and to `capture.log` | `ToxMod` = 2 incidental log-echo hits; `modulate.ai`/`libtox`/`opusenc` = 0 | hours | MEDIUM |
| C11 | **`CrashReportClient.exe` (25.8 MB) and `EpicWebHelper.exe` as a FLIRT/signature rosetta** — unpacked, built 2025-12-12 from the same engine fork and toolchain as the game; `CrashReportClient.pdb` was built and staged | `CrashReportClient` prose hits are all about the crash pipeline; `EpicWebHelper` = 0. No signature-matching tool exists in `tools/` | hours | MEDIUM-HIGH |
| C12 | **`Binds.Cache.Headers`** [×2] — 14,072 `/Script/Module.Class` → 5,698 C++ header paths. Combined with the **2,283 `C:\TheoryCraft\build-staging\…` `__FILE__` literals** in the merged dump's plaintext `.rdata`, this is a free module partition of a binary with ~0.5% named functions. Weighted `Source/Loki/*` subsystems: Services 44, UI 16, Ability 13, GameModes 12, Projectiles 8, Character 6, Visibility 6, Replication 5, DropPhase 2 | `Binds.Cache.Headers` = 0 in tools and git; `build-staging` = 3–6 incidental crash-text quotes, never a harvest. ⚠ Only 679 RTTI type descriptors survive and **zero** contain "Loki" — the RTTI route is a dead end, worth recording so nobody spends a session on it | hours | MEDIUM-HIGH |
| C13 | **`L10N/zh` — 47 asset overrides, none of them text** — death/blood VFX (`PS_knocked`, `MI_blood_bubbles_Inst`, `NS_Minion_Kaiju_*_Death`, `PS_MeleeDeflect_Impact_Flesh`) plus hero texture chromas. Two consequences: a **path-shadowing trap for any path-based shim**, and sample-selection bias (one of the FModel Texture2D parse failures was on an L10N/zh asset) | `l10n` = **0 hits** in ~100 sessions | minutes | LOW-MEDIUM |
| C14 | **`runtime.dll`'s 9.62 MB `.rsrc` in an export-less DLL** — not icons. In anti-tamper stacks this is where an embedded `.sys` or an encrypted stage-2 lives. Pure offline file read | Section table never recorded anywhere | hours | MEDIUM |

### Theme D — The chunk census (the largest single unreadable thing we own)

| # | Unknown | Evidence | Cost | Value |
|---|---|---|---|---|
| D1 | **What chunk TYPES do the IoStore containers hold?** First-ever `.utoc` parse: **118,436 chunks** vs 107,123 enumerated paths — ExportBundleData 85,508 (6.23 GB, *the only class the extractor reads*), **BulkData 16,999 (29.62 GB)**, ShaderCode 15,908 + ShaderCodeLibrary 4 (1.08 GB), ContainerHeader 16, ScriptObjects 1. Total 36.95 GB uncompressed behind 14.3 GB of Oodle-compressed `.ucas`. **The extractor reads ~17% of content bytes** | `ubulk`, `EIoChunkType`, `ChunkType`, `ContainerHeader`, `OptionalBulkData` = 0 hits across docs, tools and memory, despite 16,999 `.ubulk` | **hours** | **CRITICAL** |
| D2 | **Where the audio lives** — 0 `.bnk`, 0 `.wem`, 0 `.pck` in a 192,647-line manifest; `WwiseAudio/` has 9,133 entries and exactly **one** `.ubulk`. Answered by D1: `pakchunk0_s15` holds a single **2,091,573,424-byte (2.09 GB) BulkData chunk** paired to a 7.9 MB ExportBundleData chunk of the same package id — a 7.9 MB uasset with a 2 GB bulk payload, i.e. the whole packaged Wwise media set | `.bnk`/`.wem`/`WwiseMultiReference`/`vgmstream` = 0 hits, despite `vgmstream-cli.exe` + 12 codec DLLs already committed in `Output/.data/` | hours | MEDIUM |
| D3 | **`pakchunk0_s15` is a special-purpose container** — 15,342 entries of which 15,280 are ShaderCode, 2 ShaderCodeLibrary, and only 4 BulkData (one being the 2.09 GB monster). Other containers each hold ~3,000–12,000 ExportBundleData + 466–3,308 BulkData. The pak layout has never been profiled | 0 hits | hours | LOW-MEDIUM |
| D4 | **The extraction pipeline has no completeness signal.** `Program.cs:833-853` runs `LoadPackage` + `GetExports()` inside one package-level try/catch and prints `OK {path} ({bytes})` whenever nothing escapes — but CUE4Parse catches per-export deserialization failures *internally* and returns a partially-populated object. No property-count assertion, no stderr capture, no non-zero exit. `Output/Logs/FModel-Log-2026-06-29.log` shows the failure class (`Failed to read FPropertyTagType StructProperty<GameplayTagContainer> CooldownTags`, `Invalid FString length '167903232'`, `FName index 1075314688, name map size 100`) | `GetExports`/`silently truncat`/`partial deserial` = 0 hits. ⚠ **Breadth is unproven** — the 54 FModel errors come from only 4 distinct assets, and ~49% of catalog JSONs with an empty `export[0]` is the *already-known* `index_catalog.go:194` `dump[0]` artifact. The unknown is the missing instrument, not a demonstrated corruption | hours | MEDIUM-HIGH |

### Theme E — Backend surface the client declares and we never modelled

| # | Unknown | Evidence | Cost | Value |
|---|---|---|---|---|
| E1 | **The end-of-game contract.** `/eog/match-details` and `/eog/real-time-analytics` verified verbatim (UTF-16) in `dumps/merged.dump.exe`. `schema.txt:15157` gives `EndOfGamePayload{MatchID, MatchDetails, PlayerMatchDetails map, TeamMatchDetails, MatchEvents}` and `:15163` gives `EndOfGamePlayerMatchDetails` with **26 typed fields** — `PlayerMatchStats`, `MissionProgress`, `XPCategories`, `Placement`, `HypeEarned`, `ArmoryRewardsEarned`, `RankedPointsOverride`, `Roles`. This **collapses four separately-tracked gaps into one contract**: missions have no gameplay hook, pass XP has no gameplay hook, Career history renders empty, EOG ceremony never opened | `/eog/`, `EndOfGamePayload`, `PlayerMatchDetails` = **0 files** across docs, tools, server, configs, CLAUDE.md, memory; `git log --grep=eog` = 0. The project built `passxp.go` and the missions engine and then had nothing to POST into them. Corroborating client-side content: **~28–30 `WBP_UI_EoG_*` widgets** and loose `EOG_Placement/`, `EOG_LevelUpCeremony/` movie dirs | **one session** | **CRITICAL** |
| E2 | **Per-match `CVars` and `FeatureToggleOverrides` on a route we already answer.** `schema.txt:13049` `CoreGameMatchGameConfig.CVars` (TMap); `:13053` `Extra.FeatureToggleOverrides` / `FeatureToggleRoles` — on `/core-game/matches/{id}`, which S62 proved the client fetches and `interactive.go:686` already serves. A backend-controlled console-variable channel into a packer-protected client would replace whole classes of native shim | Neither field is *undiscovered* (S62:56 lists `CVars(Map)`; S85:283 lists `FeatureToggleOverrides` as an open cross-check) — but nobody has ever asked what they DO, and FK-23e explains why: the sweep that "closed" the HTTP toggle route omitted this route. `git log --grep=CVars` = 0 | **hours** | **CRITICAL** |
| E3 | **`/storefront/cheats/wallet/`** — a developer **cheats wallet** route compiled into the client, 0 hits repo-wide. The project has burned enormous effort on the wallet (*"91 wallet keys tested, none moves Theorycraft Coins"*), the hero-token counter throws 3 warnings/run, and PASSES reward claiming is served as `{}` | 0 hits | hours | HIGH |
| E4 | **The `/custom/*` custom-game surface** [×3] — 10–11 routes verified in the dump (`autobalance`, `details`, `members/`, `setDescription`, `setDisabledAssets`, `setInProgress`, `setPassword`, `start`, `voiceToken`, `/party/custom/list`), backed by `PartyCustomGameListManager` + `PartyCustomGameInProgressManager` and already wired into extracted UI (`WBP_CustomGameListScreen.json` calls `GetLatencyManager`/`GetFastestRegionMeasurer`). `CoreGameMatchGameConfigExtra` (`StartingItems`, `MajorBoss`, `CirclePhasesOverride`, `DisabledHeroAbilityUpgrades`) shows the custom path can fully specify a match with **no matchmaker, no MMR, no QoS** | `custom/autobalance`, `PartyCustomGame`, `custom/setPassword` = 0 files; `git log --grep=custom-game` = 0. ⚠ *Partly known:* `customgame` is a recovered queue id (`trackb-notes.md:108`) and `EPartyState::CustomGame` is documented (`endpoints.md:48`) — what is unposed is the **strategic** question | one session | **CRITICAL** |
| E5 | **The exe route table** — 131 API-shaped **UTF-16** literals in `dumps/merged.dump.exe`, ~120 plausible Loki routes, against ~40 in `docs/endpoints.md`. The prior extraction attempts scanned ASCII and returned ~0 (same bug as FK-4) | No route table exists in `tools/` or `docs/`; audit roadmap 2.3 defers it | **minutes** | HIGH |
| E6 | **The 76-file `Loki/Source/Loki/Services/*` census** recoverable from the dump's `__FILE__` literals — Agones, Armory, Auth{Auth,Login,**ServerAuth**}, Behavior, Chat, ClientConfig, Commerce{Battlepass×4,Catalog,PlatformInventory,Storefront×2}, CoreGame{**Latency**,**ServerCoreGame**}, **EndOfGame{Manager,Model,ServerEndOfGame}**, MMR, Mailbox, Messenger, Nexon, Party{,CustomGameList,CustomGameInProgress}, PlayerStats, Progression, Referral, Social{Discord×3,Steam}, Travel, Voice. A better map of "what the real backend was" than any route list — it names the managers, their Manager+Model+**Server**Manager pairings, and which subsystems had a server-side counterpart | `ServerCoreGameManager`/`ServerEndOfGameManager`/`AgonesManager` = 0 hits | hours | HIGH |
| E7 | **`/core-game/s2s/players/`** — a server-to-server core-game route (0 hits). This is the **DS→backend** half of the match contract: what the real dedicated server was expected to report about players. S62–S90 hand-rolled the client-facing side and never asked what the server side owed the backend | 0 hits | hours | MEDIUM-HIGH |
| E8 | **`/mailbox/*` as a reward-grant channel** — `MailboxMessage{Currency,Item,Armory}Reward` at `schema.txt:28624+` carry `CurrencyCode/Amount`, `SKU`, `PrimaryAssetId+Quantity`. `loki.go:118` confirms the client **already polls** `/mailbox/config/version` at menu. An entirely separate, simpler grant path than the storefront/entitlement chain | `MailboxMessage`/`mailbox/messages` = 0 files; no handler in `server/internal/` | hours | MEDIUM |
| E9 | **The `/behavior/*` moderation service** — `/behavior/report`, `/behavior/player/`, `/behavior/players/`, source `Services\Behavior\BehaviorManager.cpp`, with `BehaviorModerationActionMessage`, `BehaviorPlayerBanDetails`, `OnModerationActionApplied`, `OnVoiceMuteCleared` | 0 files across docs/tools/server/configs/memory | hours | LOW-MEDIUM |
| E10 | **The spectator backend** — `/core-game/spectator/matches/`, `/core-game/spectator/nonproduction/matches`, `/spectate`, `MatchInfo.SpectatorConnectionSecret`, `SpectatorBeacon{Client,Host,State}`, `ESpectatorState`, `LokiSpectatorPawn`, `MaxSpectatorCount`. A spectator join is by definition **non-possessing** — the exact wall (S71) the DS route terminates on. ⚠ The S76–S78 "spectator fly-cam" was a **widget-hide trick** (`ds_hybrid.cpp kMode=MODE_SPECTATOR_CAM`), unrelated to the engine spectator system, and no doc distinguishes the two | `spectator/matches`/`nonproduction`/`SpectatorBeacon` = 0–1 incidental hits | one session | HIGH |
| E11 | **The hero-select phase.** `MatchInfo` carries `HeroSelectStartTime`, `HeroSelectSecondsLeft`, `HeroSelectDurationSeconds`, `HeroSelectFirstPickTransitionPeriodSeconds`, `HeroSelectLockedInPeriodSeconds`, plus `CoreGameParticipantModel.bLockedIn`/`PickOrder`; `ECoreGameMatchState` has 10 values (PreHeroSelect, HeroSelect, Preallocate, Allocating, AwaitingReady, InProgress, Deallocating, Closing, Unknown); a dedicated sublevel `LVL_LobbyV2_HeroSelect_Skylands` ships; every hero has a `HeroSelect_BarkAudio` table. A **backend-timed, network-free** piece of "real match" — and the natural bridge from the solved roster to a match | `HeroSelectStartTime`/`LockedInPeriodSeconds` = 0–1 hits | one session | HIGH |
| E12 | **The `Nexon` environment matrix** in the already-extracted `DefaultEngine.ini` — 12 environments incl. Nexon{Development,Staging,PreProd,Live} with live hostnames (`nexon.projectloki.theorycraftgames.com/{iam,platform,lobby,statistic,leaderboard,game-telemetry,agreement}`) and distinct ClientIds/Namespaces. Plus `CoreGameMatchDetails.NexonGameSecurityEnabled` / `NexonGameSecurityEnv` — a **per-match anti-cheat switch the backend controls** and we are choosing a value for blindly | Nobody has read the matrix | hours | MEDIUM |
| E13 | **`heartbeat.accelbyte.io/add`** — a hard-coded hostname compiled in, reachable *around* `serviceHostnames`. With Vivox, Sentry and Modulate that makes **four** unintercepted outbound destinations | Verified UTF-16 in the dump; 0 hits repo-wide. ⚠ *Subsumed by* audit blind spot #10 / roadmap 2.5 — the value is the candidate list, not the question | hours | MEDIUM |
| E14 | **The return leg.** Every discussion stops at match end. Nothing covers travel back to `LVL_LobbyV2_Persistent`, clearing `CoreGamePlayer.MatchID` so the ~17/s "do I have a match to rejoin?" poller does not re-enter, or what `CanDisassociate` gates. A backend that never clears MatchID would loop the client into a dead match — a failure mode with no owner | 0 hits | hours | MEDIUM |

### Theme F — Instruments that do not exist

| # | Missing instrument | What it would end | Cost |
|---|---|---|---|
| F1 | **The `-as-development-mode` flag.** The shipping client logs, every launch: *"Angelscript: Warning: Using fully precompiled scripts. Hot reloading is disabled for this run. / Delete PrecompiledScript.Cache or run with `-as-development-mode` flag to enable hot reload."* Present in today's live `Loki.log` and in **87 of 216** captured log files, since S53. `-as-development-mode` = **0 hits** across docs, tools, server, configs, CLAUDE.md and `git log --all`. The launcher already passes `-ini:` overrides. ⚠ No `.as` sources ship — which makes this an **authoring** entry point against the 14,072 bound classes, not a recompile; whether the script compiler is linked into shipping is genuinely open | Potentially: editing game logic in a scripting language instead of hand-writing native shims against raw offsets | **minutes to test** |
| F2 | **Is `PrecompiledScript.Cache` integrity-checked?** It is a **loose, writable file outside the paks**. S74 recorded a 16-byte content-hash header and never asked whether it is verified, who computes it, or what happens on mismatch. `Manifest_UFSFiles` carries paths+timestamps and **no hashes** | If unverified: gameplay-code injection with no DLL, no manual mapping, no VEH, no `.text` patch, no integrity dodge | hours |
| F3 | **Nothing distinguishes "the target ran and did nothing" from "we never reached the target."** No shim writes an entry-hit counter for its target UFunction; none stamps a source SHA or build time into its marker; `shim-status.ps1` reports marker existence, not surface function. That one ambiguity is the observed signature of the cheat closes, `AuthCheatChangeCharacter`, `ServerCheatSpawnActor`, the toggle carrier, several deploy attempts — **and** of a stale DLL (23 of 25 `tutorial_launch_*.dll` on disk predate their own source) and of `inject.exe` resolving by process *name*, first match. **★ S114 (2026-08-12) BUILT THE FIRST WORKING VERSION OF THIS — and paid the tuition twice in the same sitting** (`docs/fk13-routeb-shipped.md` §4, §9.1). **The failure:** a borrowed helper `RunConsole()` passed `WorldContextObject = g_wmPC ? g_wmPC : g_worldCtx` and `SpecificPlayer = 0` — **both globals are populated by *other* run modes and are zero in `RM_CHEATMGR`** — so stock `ExecuteConsoleCommand` resolved `TargetPC = nullptr` and fell through to `GEngine->Exec(nullptr, Cmd)`, never touching a PlayerController. The marker printed **`console 'LogLoc' ok`** while the effect count stayed at **0**. **The instruments that caught it:** (1) an explicit entry-hit counter on the hooked dispatch — `[FS] *** NO GAME-THREAD HITS after 8000 ms (allThreadCalls=0 swapped=2) ***`, which caught a *different* silent no-op the same day (`ReceiveTickClient` is never dispatched at the menu, so the narrow Func-swap arms and does nothing); (2) a **pre-registered output signal** — the verb's own two `LogCheatManager` format literals confirmed present in the image *before* the run, against a **measured baseline of 0**; (3) `[CTRL]` gates on the RPM probe, which declared a run VOID when its own subclass walk broke. [M] ⇒ **the pattern is copyable and should be the template**: an entry-hit counter on the dispatch, a pre-registered literal for the effect, a baseline, and a control. ⚠ It is built for **one shim family only**; everywhere else F3 stands unbuilt | The credibility of every "we called it and nothing happened" close | hours |
| F4 | **No per-route hit counter on the Go mux.** 113–115 `HandleFunc` registrations vs 40 distinct observed method+path pairs; 83 routes match nothing in any capture; **`POST /revival/missions/match-result` — the only input to the missions and pass-XP engines — appears zero times.** Also 10 observed paths have no route and fall to the catch-all | Speculative handlers are indistinguishable from working ones; every future state-entry experiment would self-report | hours (15 lines of Go) |
| F5 | **No probe prints a loaded module's FULL PATH.** `tools/re/dump_modules.py:18` uses a hardcoded name allow-list; `deobfimports` verifies against an exports sidecar keyed by module *name*, so a proxy or hijacked DLL with matching exports would verify clean | Settles the UE4SS-class question permanently; hardens the 1107/1107 import reconstruction | minutes |
| F6 | **No Angelscript disassembler, and no test of whether the PI hook even observes AS-implemented UFunctions.** `_AS`/`Angelscript` = **0 occurrences across all 63 shim sources**. CLAUDE.md's dispatch rule names exactly two kinds (BP bytecode / native). ⚠ In UnrealEngine-Angelscript, script UFunctions are registered with a VM trampoline, so the direct thunk most likely dispatches *correctly* — the "silently runs the wrong body" fear is speculation, but nothing has measured it | Whether 78 script modules are observable at all | one session |
| F7 | **No crash-corpus aggregator, no visual/regression harness, no packet/DNS instrument, ~~no page-coverage or state-novelty metric~~, no widget/view-model tree dumper.** Note the S83 keystone bug *was* a view-model map-key mismatch — precisely the defect class invisible without the last one. ★★ **The state-novelty metric NOW EXISTS (S120):** a before/after `dumpimage` diff reports exactly which `.text` pages an action decrypted (`scratchpad/diffcallers.py`, `namepages.py` — worth promoting into `tools/re/`). It answers "did this action run any code we have never seen?" quantitatively, and it named a caller no static search could find. ⚠ Still missing from this row: the crash aggregator, the visual harness, the packet instrument, and the widget/view-model dumper — and the last one is still the one that would have caught S83 | See §7 | mixed |
| F8 | **No re-sampling convention.** 78 of 87 python probes re-implement RPM; only 7 contain any sleep-loop; none records a sample count or stability. ⚠ *Downgraded:* the project documents this failure class extensively in prose (S80o's self-retraction, the CLAUDE.md UProperty warning, the never-bank directive) — the gap is that the discipline lives in prose rather than in a shared helper | The most-repeated error class in the retraction record | hours |
| F9 | **No external-knowledge lookup, ever.** `wiki`, `datamin`, `reddit`, `prior art`, `patch note`, `discord server` = 0 hits in ~100 sessions, against a game whose tuning layer the audit scores ~37% with *"not one hero's health, not one ability's damage, not one circle timing."* ⚠ A community wiki would describe the *live-service balance patch*, which may not match this 2025-12-17 build — a cross-check and a prior, not ground truth | The entire tuning/design-semantics layer; possibly mod-pak recipes and prior revival attempts | **minutes** |

### Theme G — Existential and methodological

| # | Unknown | Evidence | Cost | Value |
|---|---|---|---|---|
| G1 | **If the backup disk dies, is SUPERVIVE re-obtainable?** No `appmanifest_1283700.acf` exists in any Steam library on this machine (verified across `/g`, `/h`, and `C:/Program Files (x86)/Steam`); the game runs solely because a 9-byte `steam_appid.txt` sits beside the exe. The title is delisted. And the backup is **provably incomplete** — `SUPERVIVE.exe` requires `EasyAntiCheat/EasyAntiCheat_EOS_Setup.exe`, `start_protected_game.exe` and `BootstrapPackagedGame-Win64-Shipping.exe`, and a `find` over the entire tree returns **none of them** | `depot`, `SteamCMD`, `delisted` (1 parenthetical), `steam_appid` = ~0 hits. The audit lists "~19 GB of single-copy anchors" as a reproducibility risk and never asks whether the anchor is replaceable | hours | **CRITICAL** |
| G2 | **Is the catalog reproducible?** 68,301 files / 0.73 GB, git-ignored, produced by a pipeline with no per-asset completeness assertion, no manifest of inputs, no record of the extractor commit or usmap hash. If it is lost or found truncated, nothing on disk says how to regenerate it identically | 0 hits | minutes to record | MEDIUM-HIGH |
| G3 | **Does anything depend on wall-clock time?** `[LokiTraining.NextTime]` gates, `MailboxLastOpenedAt`, `MessageOfTheDayLastSeen`, a battlepass `Version` seeded from `time.Now().Unix()`, a season model with end dates. 185 `expire|EndDate|SeasonEnd` hits are all about fields being *served*, never about rollover. For a **preservation** project, "it worked in July" is not the goal | 0 hits on clock dependence | hours | MEDIUM |
| G4 | **Has any wall ever been re-tested by a DIFFERENT METHOD?** `independent method`, `second method`, `method diversity` = 0 hits; the only trace is the never-bank directive's *"question your own tools"* — a principle with no artifact. Every wall that has actually fallen fell to a **method change**; walls still standing were mostly re-affirmed by repeating the same measurement | The register cannot be sorted on the one axis that predicts fake walls | one session |
| G5 | **Which walls predate which capability?** No `RETRACTIONS.md`, `WALLS.md` or `SESSIONS.md` exists (audit item 1.10 proposes the first two). §6 of the audit lists only walls *already overturned*, never standing walls that predate a capability. Capabilities landed at S55, S58, S78, S91, S93, S102 — every wall asserted before each is a candidate, and today they are found only by accident (this audit found four) | Same | one session |
| G6 | **"Has the game already written this down?"** — the missing first step of the project's method. Demonstrated by at least seven cases in this document: the 149 toggle names, the input table, the tutorial ledger, the file manifests, the protection BOM, the queue table, and the gameplay-tag tree (currently reconstructed by regexing 3,252 cue assets while `DefaultGameplayTags.ini` sits in the pak) | Not a hit-count claim | minutes (one CLAUDE.md line) | HIGH |
| G7 | **Round 1 created false-knowns.** *"Angelscript — zero mentions in docs"* is false (9 doc files, one **named** `session-74-overlay-spike-angelscript.txt`). *"UE4SS is already installed"* as an unexploited asset is worse: `docs/findings.md:186-196` records that **UE4SS never loads on this exe**, and the `ue4ss/` dir + `dwmapi.dll` are dated **2026-06-25 — the project installed it itself**. Anything seeded from round 1 needs re-checking | — | minutes | HIGH |
| G8 | **The redirect's TLS trust model has never been examined, and its two mechanisms are CONFOUNDED.** Every launch applies *both*: `launch-redirect.ps1:259` appends our root CA to the game's **general** libcurl bundle (`Loki/Content/Certificates/cacert.pem` — an *issuer*, which may vouch for **any** hostname; not a per-host pin), **and** `:296-300` writes `[HTTP.Curl] bVerifyPeer=false` + `[SSL] bValidateRootCertificates=false` into the user `Engine.ini`, then sets it **read-only** so the game cannot strip it. Neither has ever been flown without the other ⇒ **which one actually makes the redirect work is UNKNOWN**, and if the CA path suffices the verification-off is gratuitous. Compounding it: `server/certs/server.key` — the **root CA private key** — was tracked from the first commit and is in the PUBLIC origin (`docs/certs-key-exposure.md`; untracked in `fabc59a`, **rotation still OPEN**), so anyone with the repo can mint a cert that every self-hoster who ran the launcher will trust, for any hostname their client contacts. ⚠ **One scope caveat and one genuine gap:** (a) the loose phrase *"install a CA … into their **trust store**"* is `.gitignore:62`'s, quoted approvingly at `certs-key-exposure.md:29-30`; the doc's **own** prose (`:24-26`) is correctly scoped to the game's bundle, and that scoping is right — this is **one application**, not the Windows store, and exploitation needs network position; (b) the doc does **not** mention `bVerifyPeer` **anywhere** (0 hits), so it never registers that the exposure is **second-order behind an override that accepts *any* cert regardless of issuer**. ⇒ **rotating the key while leaving verification off buys almost nothing**; the higher-value action is B-9 | `certs-key-exposure.md` = **0 hits in this map** before this row; the appendix below dropped *"is `bVerifyPeer=false` ours?"* as ACTUALLY_KNOWN and never asked whether it is still **necessary** | one `-NoHook` launch | MEDIUM (HIGH if this is ever redistributed) |

---

## 4. The Walls Register, Re-examined

### 4.1 ALREADY_FALSIFIED (this audit)

| Wall | Killed by |
|---|---|
| "The AS layer is thin; deploy/round is native C++" | 78 `.as` source modules vs an 18-class `_AS`-suffix census (FK-1) |
| "`.rdata` is structurally capped at 63.12%" | 33/9,085 all-zero pages (FK-3) |
| "The packer defeats static string-xref" | The strings are UTF-16 and are in our own dump at the same RVAs (FK-4) |
| "There is no legacy input path" | 186 ActionMappings in a plaintext file, on a bespoke Loki class (FK-2) |
| "The dev console is fully stripped" | 5 of 10 ABSENT-listed strings present; `DebugExecBindings Num=16` measured live (FK-13) — **SETTLED S114: the console really IS gone (`ALLOW_CONSOLE == 0`, three instruments), but every stated reason was wrong and the operational conclusion *"all cheap external paths are exhausted ⇒ injection only"* is FALSE. `UE_ALLOW_EXEC_COMMANDS == 1` (its UBT default is 1), 138 native `FUNC_Exec` UFunctions exist, and Route B now runs 42 of them live via one heap qword. `docs/fk13-console-exec-settled.md`, `docs/fk13-routeb-shipped.md`** |
| "The tutorial route is flaky (~2 of 3)" | Byte-identical RVA chains across independent launches (FK-7) — **CLOSED S112: the cause was our own standing `.text` patch (10/10 died with it vs 3/36 without, p = 7e-8); fix shipped and confirmed. The S106 "two shim-caused signatures" diagnosis was directionally right — it was ours — but the mechanism was the module-image write, not the camera/anim families. `docs/s112-fk7-ab-results.md`** |
| "`SecondsSinceStart` is always 30" | 5 of 92 UECC / 114 distinct deaths — **FK-8 CLOSED S111 with a permutation control** (0/56 violations, P<5e-5) |
| "Crashes route through Sentry; no UECC dumps" | 86 UECC dirs including 9 from the newest runs (FK-9) |
| "`runtime.dll` is packed" | **FALSE — settled S113.** 46.6 MB of **plaintext obfuscated x86-64**, disassemblable offline (linear sweep 0.00 % invalid vs 5.25 % on ciphertext controls). Only its *data*/*resources* are encrypted. Vendor name refuted 6 ways; it is a bespoke `packer/3.3.1` (FK-10 → `docs/fk10-protector-identified.md`) |
| "Verbose is compiled out of shipping" | `LogSentrySdk: Verbose:` in the live log; `[Core.Log]` in the shipped ini (FK-11) |
| "The on-disk exe is useless for RE" | `.rdata` entropy 5.2–6.0 with 2,280 source paths — *though the dump already supersets it* (FK-4) |
| "`SUPERVIVE.exe` is a CEF/Electron shell" | `BootstrapPackagedGame` PDB, zero CEF strings (FK-17) |
| "News/Event Hub/Referral may be web pages, impersonatable with no shim" | **FK-17 CLOSED S119: REFUTED as web pages** (1 `WebBrowser` in 68,303 assets, and it is the vestigial login ToS modal; 1 live `UWebBrowser` in 195,084 objects, the CDO). But the *underlying* opportunity was real via `ClientConfiguration.BannerConfigs` — the lobby news banner now renders from the backend with **zero injection** |
| "The missions page requires `missions_fix.dll`" | **FALSE as of S119.** `FPlayerProgression.MissionInfo` on `GET /progression/players/{id}` drives the native ingester end to end — DAILIES 3/3 + WEEKLIES 8/8 with real progress, XP and CLAIMED state on a clean `-NoHook` run. The shim is retired from the default set (`-WithMissionsShim` to restore) |

### 4.2 CONFIRMED (independently re-tested; still holds)

| Wall | Confirming evidence |
|---|---|
| **UE4SS never loads** | Confirmed **3× independently**: exe import directory has one descriptor (`preloader.dll`); `dwmapi` = 0 occurrences in the 178 MB merged dump; minidump ModuleList resolves dwmapi to `C:\WINDOWS\SYSTEM32`; no `UE4SS.log` anywhere; dwmapi absent from all 86 crash module lists |
| **`.pdata` is unreadable live AND encrypted on disk** | Merged dump: 1,533–1,534 of 1,534 pages all-zero. On disk: entropy 8.00, zero all-zero pages (RUNTIME_FUNCTION arrays are near-minimum entropy, so 8.00 is decisive). *But see B5 — the minidumps have it.* |
| **Vivox token is unfixable** | A live measurement (`20127: Access Token Service Unavailable`), correctly scoped to the token. *Scope is the issue, not the fact — see FK-16.* |
| **Native cheat dispatch is closed** | `AreHotkeyCheatsEnabled_Impl = xor al,al; ret`, `ServerCheatSpawnActor_Impl = ret`, disasm-verified; no live `LokiPlayerCheats` instance (S96); interesting spawn actions have `Key=None`. *The script family is a different surface — FK-6.* |
| **`BP_TrainingSkill_*` is practice-mode gated** | `bpdump @props` read `ValidStates` off serialized defaults; none lists `BP_LokiGameState_Tutorial_C`; corroborated by asset path and by a live forced-gate experiment |
| **No Server-target binary exists** | Confirmed; only the *"no server code is present"* corollary is falsified (§4.3) |
| **`OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`** | The measured basis for the tutorial-vs-DS route decision |

### 4.3 STALE — asserted before a capability existed that would now beat it

| Wall | Asserted | What changed |
|---|---|---|
| IoStore signature bypass ("the patch lands ~50 ms too late; the packer commits `.text` on demand") | 2026-07-02 | Predates the S55 native-call primitive, the S43/S77 transient-patch pattern, the S78 heap vtable swap, and `deobfimports`. The patch site is fully solved (`FPakSignatureFile::Load @ +0x2047EE0`, both callers unconditional). The 50 ms figure was measured once |
| "The packed process blocks non-system DLL loads" | 2026-06-26 | The project now manual-maps six shims per launch |
| "Only the CLIENT target shipped; no server code present" | — | `.rdata` carries Loki's **own** server managers: `Services\CoreGame\ServerCoreGameManager.cpp`, `Services\Auth\ServerAuthManager.cpp`, `Services\EndOfGame\ServerEndOfGameManager.cpp`, `Analytics\LokiServerAnalyticsManager.cpp`, `Services\Agones\AgonesManager.cpp`, plus `Runtime\Online\HTTPServer`. ⚠ *A retained `__FILE__` proves the TU linked in, not that `IsRunningDedicatedServer()`'s branches survive — but "no server code is present" is not what the artifact says* |
| Steam-must-run 14005 | ~S44 | N=1, never retested (FK-12) |
| `capture-dumps.ps1` "tutorial isn't playable yet" | ~S67 | ~35 sessions stale (FK-20) |
| CLAUDE.md PI-hook "VALIDATION PENDING (2026-07-10)" naming 3 hookers | 2026-07-10 | The default set is now **six** (FK-23f) |
| Audit item 0.4 "extract `Loki/Config/*.ini`" | S101 | Already extracted since 2026-06-27 (FK-23d) |
| README Milestone 4 "no hero" | ~S58 | Hero visible since S98; GAS gate cleared S103 |

### 4.4 UNCHALLENGED — asserted once, never re-tested by a different method

**Ranked by (how much it blocks) × (how likely it is fake):**

| Rank | Wall | Why likely fake | Cheapest test |
|---|---|---|---|
| **1** | **QoS UDP responder gates BATTLE/PRACTICE** | Inference from an absence; its own source hedged "OR the ICMP module"; `QosManagerServerUrl=` empty in all 12 environments; the populated machinery is Theorycraft's `ULatencyManager` + UE's `FNetPing` (FK-5) | Restore the queue list, click BATTLE, read the capture |
| ↳ | **✅ SETTLED S105 → `docs/fk5-battle-gate-settled.md`.** *Row preserved above; its diagnosis was right and is now measured.* No `ULatencyMeasurer` has **ever** been created (`LatencyManager.cpp:315`, verbosity **Display**, 0 hits / 14 logs) and the UDP-echo impl `0x1F8CFC0` is a **100 % zero page** — QoS was never observed to block anything. ⚠ **No replacement culprit**: `TryJoinQueue`'s page `0x5875000` is also 100 % zero, so what blocks BATTLE *past the tile* is **UNKNOWN**. ★ **The experiment is cheaper than this row says — zero backend change**: `bots` is already served and is **not** in the native `IsSpecialQueue` set, so **BOTS → FIND MATCH** enters the real `TryJoinQueue` today. No account level needed (`CanControlQueue` loops `GetCurrentQueues` ×25, `GetQueues` ×0). | **BOTS → FIND MATCH, read `capture.log` in order** |
| ~~**2**~~ | ✅ **FELL S117 — "Server→client WS push is non-functional" is REFUTED** (`docs/fk15-ws-push-audit.md`) | It was fake: push is MEASURED WORKING (4 × `OnMessageReceived` for our 4 frames); the 5 probes predate log verbosity by 41 days and 2 of their 6 detector categories **do not exist**; they tested **1 of 33** notif types, picked via a `dsNotice`/`dsNotif` typo | **DONE.** Harness shipped; probes 1-3 flown and confirmed live (sentinel echoed back; heartbeat churn fixed; targeted resync proven to refetch **and apply**). ✅✅ **AND FULLY CLOSED S118** (`docs/fk15-bound-delegate-map-20260813.md`): all 33 types swept, then the delegate table joined to the jump table — **only 7 of 33 have a subscriber**, and **all 7 were flown, 6 driving visible UI changes**. ⚠ `dsNotif` — the type this row said to push next — is **UNBOUND**; pushing it can never have an effect. The reachable set is the friends/presence family, because 21 of the 23 bound delegates belong to one `USocialManager`. |
| **3** | **The 6-shim default set crashes** | S85, never re-tested in 17 sessions. A stronger alternative cause exists: `inject-secondaries.ps1:82` gates on `'\[unhook\]'` in a marker file **nothing clears between launches**, so all five secondaries inject *during* the primary's thread-suspending SafeWrite. ⚠ Also fix `launch-redirect.ps1:95-105`, which forwards every flag across elevation **except `-NoPasses`** — any `-NoPasses` bisection silently runs *with* the passes shim | Delete markers pre-launch (or gate on mtime ≥ process start), then one validation launch |
| **4** | **DropPlane is falsified as reachable** | N=1 against a tutorial-specific variant, with the source itself recording wrong arg types (FK-22) | Read `LokiDropShip.as` for the markers it queries |
| **5** | **The S78 free-look rotation wall** | Its leading hypothesis (Enhanced Input) was retracted 2 sessions later, and its own stated remaining path — "hook the camera-update function" — is the per-frame heap vtable hook S78 shipped *in the same session* and never pointed at rotation. Untouched since 2026-07-15. ⚠ *Its hard measurement survives the retraction: no look-sensitivity field exists on the PC, and rewriting every enumerated sensitivity float had zero effect* | Intercept the camera-update slot's OUT rotation and scale it |
| **6** | **The game-feature-toggle carrier is a fixed-offset wall** | Three sessions of replication bit-splicing while an HTTP `FeatureToggleOverrides` map on a route we already serve was never tried (E2, FK-23e) | Populate `Extra.FeatureToggleOverrides` and diff the "not ready" spam |
| **7** | **The ~3–5 min code-integrity check** | The mechanism has never been located, disassembled, or its period measured; S77 reached it by elimination. ⚠ *Weaker candidate than the rest:* S43's table is a controlled A/B on the one variable that matters (patched control ~4.75 min vs identical build un-hooked stable ≥6 min), the poison-jump register signature is N=4 across ASLR bases, and this audit's own 173–201 s cluster sits **inside** the window. The operational rule ("no standing `.text` patch") remains well-supported; only the mechanism is unknown | ~~Hunt xxHash/Zstd constants in `.rdata` (FK-10 names the algorithms).~~ ⚠⚠ **THAT LEAD IS SPENT (S113, `docs/fk10-protector-identified.md` §5).** It was run with controls (49/49 planted constants recovered). xxHash IS present — full XXH3 `kSecret` at RVA `0x9c00`, routines at `0x8eb250`/`0x8d98b0`/`0x8ed920`/`0x889b20` — but the one-shot `0x8200f0` has **exactly one caller**, `0x8f9dd0`, which tests `(dword & 0xFFFFFFF0) == 0x184D2A50` ⇒ **xxHash here is Zstd's frame checksum, not the integrity hash.** ★ **SUCCESSOR LEAD, with an exact range:** SHA-256/SHA-1/MD5 tables cluster in `packer2 0x942740–0x9467e0` (two back-to-back SHA-256 IVs = lane packing), tracing to AVX2/MMX code and a 16-entry `cmovne` job ladder in a **`.pdata`-free tail at RVA `0x8ffcd4–0x93e886`, 251 KB** — **[I]** Intel ISA-L Crypto **multi-buffer** assembly (ships as `.asm`, hence no unwind records; a BOM component this map missed). **`runtime.dll` is plaintext, so this is disassemblable offline today.** ★★ **And a 16-lane page hasher RECONCILES the negative Rayleigh result below:** a periodic timer that samples a SUBSET of `.text`'s 30,281 pages per pass yields `period × Geometric(p)` detection times — aperiodic and long-tailed, exactly the measured 87–524 s spread. ⇒ the supportable claim is **not** "the check is not periodic" but **"the check does not verify all of `.text` on every pass."** ⚠ Also note this row's own scope error, now corrected: the companion "no string names it — CLEAN NEGATIVE, not coverage-blocked" (`fk3-fk4-settled.md:513`) was measured by `strxref.py`, which hardcodes the **game exe** dump; `runtime.dll` was never scanned. ⚠ **The modulo test is SPENT and NEGATIVE (S111):** Rayleigh max-over-grid 20–400 s, N=91 — best period 214.5 s, z=29.27, bootstrap **p = 0.414**; positive control fires at σ≤20 s and fails at σ=40 s, so the test had real power and found nothing. Scope: absent from the timing of deaths that **left an artifact**; blind to the artifact-less class. Also ⚠ this row's supporting "173–201 s cluster sits inside the window" is now known to be **era-B-only**, and its stack family is ~~the ~~tick task-graph dispatcher~~ [RETRACTED — it IS animation code]~~ **[RETRACTED — it IS animation code]**, not animation |
| 8 | Angelscript-implemented UFunctions dispatch correctly through the native thunk | Never measured; 0 shim mentions (F6) | Print the owning class of every PI-dispatched UFunction for 5 s |

---

## 5. Never-Entered Runtime States + the Demand-Decrypt Reframe

### 5.1 The reframe

The packer demand-decrypts `.text` on execution. **Therefore the set of never-entered game states
is exactly the set of permanently-undecryptable code.** "48% `.text` coverage" is not a dumping
problem — it is a **state-coverage** problem, and the missing half is disproportionately gameplay
code, which is exactly the code the project cannot reach.

Measured: **14,447–14,448 of 30,281** 4 KB `.text` pages (≈45.7–47.7%, ~54 MB) are zero in **every**
one of the 9 dumps. Merged coverage 48.05%. Of nine captured states, **six contribute zero unique
pages**; only `toggles` (325 pages / 1.30 MB, an in-match-adjacent state) and `rcb` (56 pages) add
anything meaningfully. **Yield tracks state novelty, not dump count** — and the guidance in CLAUDE.md
still names four menu states as examples.

A residual worth one look: **37 pages in the merged dump are covered yet still high-entropy** —
executed but not readable. If those are VM-obfuscated rather than merely undecrypted, some code is
unreadable even at 100% execution coverage. 0.12% of the section, so low priority, but it bounds the
ceiling.

### 5.2 States never entered

Verified from 216 log files (26–29 live `Saved/Logs` + 79–86 crash copies + `docs/*.log`):
**only three top-level worlds have ever loaded** — `LVL_Login` (15×), `LVL_LobbyV2_Persistent` (14×),
`LVL_Tutorial` (10×) — out of 65 unique top-level `LVL_*.umap` (7,300 `.umap` total, of which 7,184
are World-Partition `_Generated_` cells; there are **zero** `__ExternalActors__` packages, so placed
actors live in the cells).

| State | Ever entered? | What entering it would decrypt / reveal |
|---|---|---|
| Matchmaking / queue pop | **Polled, never popped.** `/party/matchmaking/info` + `/customGameModes` are fetched every ~2 s and appear in `docs/capture.log`; no queue has ever produced a match | The matchmaking client path; the QoS/latency truth (FK-5) |
| Hero select | Observed at state 0 once (S65); `tutorialMatchState` is pinned | `LVL_LobbyV2_HeroSelect_Skylands`; the ECoreGameMatchState transitions; `HeroAssetID` assignment without a shim (E11) |
| Drop / deploy | Never | `LokiDropShip`/`LokiDropPod`/`LokiDropPhase_PlayerStateComponent`; the DropPlane truth (FK-22) |
| In-match simulation | Never | Abilities, damage, items, minions, circle, HUD, minimap, killfeed, scoreboard, the in-match shop. **The largest `.text` block by far** |
| End of game | Never | The EoG contract (E1); `EOG_Placement`/`EOG_LevelUpCeremony`; XP/mission/pass ingest |
| A second NetConnection | **Never** — all ~25–42 captured DS sessions carry the *same* player id `9b9d2c88…` | Relevancy, priority, per-connection NetGUID divergence, dormancy, late-join into a populated world, class-net-cache renegotiation |
| Any non-tutorial map | Never | 62 maps incl. `Skylands_WP` (2,216 packages), `LVL_Practice` (**208 WP cells**, its own `BP_PracticeGameState_C`), `LVL_ServerStandby` (**`ServerDefaultMap` in the shipped ini**), `LVL_LobbyV2_Dev`, `LVL_Domination(_V2)`, `LVL_TugOfWar`, `LVL_Lastman`, `LVL_Payload`, `LVL_Holdout`, `LVL_GrindBallArena_01`, `LVL_Battleships`, `LVL_Bracket_01`, `LVL_Battlefield*`, `LVL_Training(_NoShark)` |
| Custom game lobby | Never | The `/custom/*` surface (E4) |
| Error / negative paths | Only accidentally | Disconnect, failed auth, malformed response, mid-match crash, rejoin, full party. ⚠ *Partly overstated — the project's entire validity model was derived from deliberately induced malformed responses; what is missing is a fault-injection tool and the reading of the 86 accidental failures* |
| Settings / options UI | Unknown (the *system* runs every launch and rewrites its inis) | Low value — the file contents (B1/B2) are the payload, not the click |

**Log-category coverage as a second state metric:** ~1,004 distinct `Log*` categories are compiled
into the image; **139–176 have ever emitted a line** across all 216 logs. ~64–75 of the silent ones
are Loki-specific and map onto every open frontier. FK-11 is what makes this a cheap, standing
novelty instrument: *diff "categories alive this run" against the 1,004 and print the newly-alive
ones* — instant free evidence that a probe actually entered a new state.

### 5.3 Which state to enter next (ranked)

1. **The tutorial, with `capture-dumps.ps1 -State tutorial`** — the highest-yield capture available,
   reachable today, costs one already-planned session (FK-20).
2. **`LVL_Practice`** — 208 WP cells, its own GameState, `practice` already a served queue, and
   `docs/tutorial-playability-plan.md:360-366` **already records** that the practice GameState is a
   valid host for the training-skill family. The project read that fact and used it only to close the
   tutorial door, never to open the practice one. (Audit roadmap 2.8 names `LVL_Training`; this is
   the better target.)
3. **FFA / Arena with bots** — the strategic consequence of FK-1 that nobody stated: `FFAGameMode.as`,
   `FFABotSpawner.as`, `LokiRespawnComponent.as`, `Comp_PC_LokiRespawnComponent.as` are **all
   Angelscript we possess**, and `deathmatch` (=Arena, 4v4) and `bots` are shipped queue ids — with
   `bots` already among the four the backend serves. No drop plane, no storm, no 60-player
   replication, no minion economy.
4. **A second NetConnection** (or a second local player via SplitScreenMod) — see §8.

---

## 6. Artifacts Nobody Has Opened

Consolidated and deduplicated. `[×N]` = independently found by N dimensions.

### 6.1 Open now (minutes, offline, high value)

| Artifact | Contents |
|---|---|
| `schema.txt` § `ELokiGameFeatureToggle` | 149 named toggles (A1) |
| `schema.txt` § `Party` @40988 | `Party.State` = the launch gate (A2) |
| `%LOCALAPPDATA%\…\WindowsClient\UserSettings.ini` [×4] | 186+16 input mappings, 43 cheat actions, FTUE flags (B1) |
| `…\WindowsClient\GameUserSettings.ini` [×2] | 24-lesson training ledger, `menu_slider_master=0` (B2, B3) |
| `Manifest_{UFSFiles,NonUFSFiles,DebugFiles}_Win64.txt` + `buildID` [×4] | 192,647-line census; **the shipping PDB** (C1, C2) |
| `Loki/Binaries/Win64/thirdpartylicenses.txt` [×2] | The real protection BOM (C4) |
| `tools/extractor/out/DefaultEngine.ini` | 12-env AccelByte matrix, empty QoS URLs, `[Core.Log]`, `ServerDefaultMap` (FK-23d) |
| `tools/extractor/out/catalog/dt/DT_{LoadingScreen_GameMode, LoadingScreenTips_ModeExplainer, QueueDisplayDataTable}.json` | The game's own mode and queue definitions (A4, FK-23a) |
| `tools/extractor/out/catalog/st/*.json` (64 files) | The in-match economy, XP categories, death/leave rules (A6) |
| `preloader.dll` strings + `SUPERVIVE-Diagnoser.exe` strings | The anti-tamper taxonomy (C7) |
| `Saved/ImageCaches/ImageCacheIndex.json` [×3] | 55 live CDN URLs + the assets (B7) |
| `docs/capture.log` entry #4 `platform_token` | The client's SteamID64, decodable at byte 12 (§8) |

### 6.2 Open now (hours, offline, high value)

| Artifact | Contents |
|---|---|
| `Saved\Crashes\` — 86 dirs, 2.0 GB [×5] | 512 RVAs / 7 bases, error histogram, 79–86 frozen pre-crash logs (B4) |
| `UEMinidump.dmp` stream 13 | The whole missing `.pdata` — 524,439 RUNTIME_FUNCTIONs (B5) |
| `UEMinidump.dmp` ModuleList | 217 modules with full paths (B6) |
| `Loki/Script/Binds.Cache` (5.76 MB) [×2] | 15,068 UFunction signatures + complete USTRUCT shapes (A3) |
| `Loki/Script/Binds.Cache.Headers` (2.05 MB) [×2] | 14,072 class → 5,698 header map (C12) |
| `Loki/Script/PrecompiledScript.Cache` (1.18 MB) [×3] | 78 `.as` modules; `AuthCheat*` bodies; the Barracuda MOBA (FK-1, FK-6) |
| `Loki/Content/Paks/*.utoc` (17 files) | The 118,436-chunk census (D1) |
| `Loki/Content/Movies/` — 56 mp4, 416 MB [×3] | The developers' own demo of every system (C3) |
| `dumps/merged.dump.exe` `.rdata` (**with a UTF-16 scan**) | ~120 route literals; 2,283 `build-staging` source paths; the 76-file Services census (E5, E6, C12) |
| `runtime.dll` section table + `.rsrc` [×2] | The uploader, the off-switches, a 9.62 MB unexplained resource blob (C5, C14) |

### 6.3 Open later / measured and closed

| Artifact | Verdict |
|---|---|
| `Saved/webcache_4430/` (CEF profile) [×4] | **Measured and closed.** Cookie jar has **0 hosts**; `Network Persistent State` lists only Chromium defaults (`themes.googleusercontent.com`, `chrome.cloudflare-dns.com`, `*.pki.goog`); `cef3.log` is 0 bytes; nothing written since 2024–2025. **Not** an unmonitored egress surface. *But CEF itself initialises every launch (FK-17) — the render-path question survives* |
| `Loki/.sentry-native/` [×3] | **Measured and closed.** `reports/` and `attachments/` are both **EMPTY**; `__sentry-event` is a msgpack scaffold with no exception, no stacktrace and no `debug_meta.images`. Do not spend a session here |
| `Loki/Binaries/_legacy_ue4ss_backup/` | Dies with UE4SS; also not on the exe's DLL search path |
| `Engine/…/icudt64l/*.res` (3,438 files) | Stock ICU locale data. Recorded so the bucket stops looking unexplored; exclude from coverage denominators |
| `Engine/Content/Slate/**/*.png|svg` (~693 of 702) | Stock UE **editor** iconography; only ~9 are Loki. Round 1's "690 PNG+SVG never exported" is ~9 useful files |
| `Output/.data/vgmstream-win.zip` | A committed audio decoder with 0 references — useful **only after** D1/D2 |
| `CrashReportClient.pak` (21.6 MB) | A free known-good control specimen for the extractor; low priority since the manifest cross-check showed enumeration is exact |

---

## 7. Instrument Blindness — what we cannot see, and what would fail silently

| # | Blind spot | The silent failure |
|---|---|---|
| 1 | **We cannot tell "this code never ran" from "this code ran silently."** The only runtime instrument is `Loki.log` at default verbosity, and one handoff line (FK-11) stopped anyone turning it up | Any subsystem that executes without logging at `Log` level is invisible; a half-working shim looks identical to one that did nothing |
| 2 | **We cannot observe a state we did not enter — permanently, for static RE too.** 45.7% of `.text` is zero in every snapshot. ★★ **PARTIALLY LIFTED (S120):** the **before/after decrypted-image diff** turns this blind spot into a *targeted* instrument — `dumpimage`, perform the action, `dumpimage` again; because `.text` decryption is **monotone within a process lifetime** (FK-18/19), pages zero-in-BEFORE and non-zero-in-AFTER are exactly the code the action ran. First use isolated a claim path to **20 pages / 80 KB** and recovered a call site that was unfindable by any static search. ⚠ Scope: it finds code that *just ran*, so it cannot reach states we still never enter, and it cannot isolate a function whose page was already decrypted by a neighbour | Every "function X does not exist" / "nothing writes `PlayerState+0x4F8`" is **unfalsifiable**; the code may live in the half we have never run. **Now falsifiable for anything we can trigger on demand** |
| 3 | **We cannot verify that a shim's target was entered** (F3) | Four+ standing walls rest on an observation the instruments cannot disambiguate — and stale DLLs and name-resolved PID injection produce the identical signature |
| 4 | **We cannot verify that a hardcoded RVA is still correct.** No shim reads back the bytes it patches; none checks a build fingerprint; 179 RVAs are valid against exactly one exe | Silent memory corruption whose symptom is an unattributed crash minutes later — indistinguishable from the postulated integrity check |
| 5 | **We cannot see our own metric failures.** `mergedumps` reports non-zero bytes; `dumpimage` reports readable bytes; the two are quoted interchangeably | Produced **both** a false structural wall (`.rdata`) and a false absence claim (`.pdata` "0 of 6,283,264 readable" — actually 100% readable and genuinely zeroed). `.data` 36.8%, `_RDATA` 61.5%, `.rodata` 31.3% are suspect for the same reason |
| 6 | **We can see one of four network stacks.** UE curl (patched `cacert.pem`) is instrumented; the Tox plugin's own libcurl, Chromium/CEF, and `runtime.dll`'s mbedtls-over-WINHTTP are not. Four hostname-addressed destinations reach around us | "The client never calls X" means "over the one stack we observe." A live third party may be receiving minidumps of our modified process |
| 7 | **We cannot observe what else is in the process.** Nothing enumerates loaded modules or asserts hook ownership; nothing checks for `Conflicting software detected!` | Deliberate anti-tamper terminations are indistinguishable from bugs — and ~100 sessions of "the packer's exception handler kills the process" rests on N=3 canaries that never tested the alternative |
| 8 | **We cannot detect a front-end regression.** 0 tracked images; no automated visual check; marker READY proves a shim *ran*. The audit concedes every "LIVE" claim is *"confirmed against the record, not against a running game"* | All 24 LIVE surfaces could have regressed and the record would look identical. ⚠ *Partly self-inflicted:* `tutorial_launch.cpp:3304` already implements a self-screenshot ("THE GAME PHOTOGRAPHS ITSELF"), and 9 PNGs sit unreferenced in `Saved/Screenshots` — the instrument exists and its output is discarded |
| 9 | **We cannot read the client's own persisted state** (B1/B2/B11) | Behaviour caused by a local flag gets attributed to a shim or the backend; the input table was hunted in live memory for sessions while sitting in plaintext |
| 10 | **We cannot distinguish a truncated asset dump from a complete one** (D4) | "This asset has no such property" may mean "the parser stopped" |
| 11 | **We cannot observe Angelscript execution at all** (F6) | Logic implemented in 78 script modules reads as "native, unreconstructable" — exactly the S74 error |
| 12 | **We cannot represent a second participant** (§8) | Every multiplayer assumption is untested *by construction* |
| 13 | **There is no acceptance test at any level** | The project can make continuous measurable progress while moving no closer to any user-recognisable goal |
| ~~14~~ | ~~**We cannot observe an `IsFeatureEnabled` result.**~~ ✅ **RESOLVED (S121).** A dark surface used to be equally consistent with "flag off" and "companion condition unmet", so every toggle question was inference. `tools/re/toggle_readout.py` reads the gate widget's own stored answer (`Is Content Enabled` @ +0x473) by read-only RPM — no injection, no `.text` write. **`IsEnabledByDefault==false AND enabled==true` is reachable by no path except our served value being read.** It immediately paid: `NeLobbyEventBtn` is measurably ON while invisible ⇒ companion condition, not a flag. ⚠ Residual blindness: it sees only the **declarative** widget family, so the 10 **bytecode** `IsFeatureEnabled` keys (`motd`, `LobbyRewards`, `ArmoryOnboarding`) still have **no readout** — and it can only see widgets whose screen has been constructed |

★ **The general lesson from #14, worth applying to the other rows:** the answer was not a debugger or
a shim — **the client was already storing the value we wanted, in a reflected property.** Before
building an instrument, check whether the thing under test persists its own answer somewhere
readable. Row 8 (front-end regression) has the same shape: the game already photographs itself and
the output is thrown away.

---

## 8. The Multiplayer Void

**The stated goal requires two participants. Nothing in the stack can represent two.**

### 8.1 The identity layer — and the key that is already on the wire

`token.UserIDFor("platform:steam")` hashes to `9b9d2c887e2524f918e383a895f2f1c2`, byte-identical to
the live player id in **every** log and in `server/state/interactive.json`. `handlePlatformToken`
keys on `r.FormValue("platform_user_id")` — which the real client never sends — and falls back to
`"platform:"+platform`.

**But the distinguishing key is on the wire already.** `docs/capture.log` entry #4
(`POST /iam/v4/oauth/platforms/steam/token`) carries a `platform_token` that is a standard Steam
auth-session ticket: `[uint32 len=0x14][8-byte gcToken][8-byte SteamID64]`, decoding to
**SteamID64 `76561197981196360`** (accountid 20930632), present twice. The backend discards it.

`platform_token`, `SteamID64`, `steam-ticket-parsing` = **0 hits** in docs, tools, or server.

> ⚠ **Scoping correction:** the collapse is *deliberate and tested* —
> `server/internal/iam/iam_identity_test.go` (`TestAuthPathsAgreeOnOneUserID`) asserts case 3 that
> *"a named username must NOT collapse to the local player id … we only canonicalize the
> unidentified fallback."* So this is a ~10-line parsing gap, **not** a missing identity layer.

### 8.2 What breaks the moment a second identity exists

| Node | State |
|---|---|
| **Party document** | `buildSoloParty` is the **only** party constructor, called from all 5 party routes and every test; emits one member with `leader:true`. No invite acceptance, no join/leave |
| **Member-write routing** | `handleSetPartyMember` (`interactive.go:970`), `handleGetPartyDetail` (`:811`) and `handleStartSoloMode` (`:838`) all resolve the player from `strings.TrimPrefix(partyId,"party-")` **before** memberId or the JWT subject. Since partyId is always `"party-"+self`, this has never differed — but with 2 members, **every member write lands on the leader**. A ~10-line reorder, far cheaper before the first test than after |
| **Authorization** | There are **no authorization checks anywhere** — handlers take the id from the URL path, not the verified JWT subject. Cross-account read/write becomes possible the instant two identities exist. ⚠ *Mitigating:* the issued JWT already carries full-admin permissions, so coarse authority was never the gate |
| **Presence** | No presence handler, store or model exists in `server/internal` (the 3 grep hits are comments). Every remote member would read as offline — degrading the avatar card, whose predicate is *"valid+online"* |
| **Friends** | ~~`lobby.go:317-332` hard-codes `friendsId: []` and returns `""` for everything else. No friend store anywhere.~~ ⚠ **UPDATED S118.** Still true that there is **no friend store** — but the three list responses are now backed by opt-in env knobs (`AGS_PROBE_FRIEND` / `_INCOMING` / `_OUTGOING`, empty by default), and the whole friends surface is **proven drivable**: all 7 subscriber-bound notif types flown, 6 with visible UI effect. ★ **The client mutates its own friends state from a notif and only a refetch re-imposes ours**, so a real friend store must serve BOTH the response (durability) and the notif (the live event). `acceptFriendsRequest` is still **unanswered** by the server — the client sends it on Accept and we drop it |
| **Version gate** | `store.partyVer` is one global counter. ⚠ *Adjudicated:* two members share **one** party document, so a shared counter is **correct**; only cross-party noise remains. Not a bug |
| **Replication** | The stub sets **no** `ReplicationDriverClassName` while the shipped client config sets `/Script/Loki.LokiReplicationGraph`, and the game declares `ReplicationGraphNode_Loki{Vision,Team,Player,RepTilDormant,ScoreboardRow}`. And the stub **replicates `MaxPlayersPerTeam = 1`** (`LokiGameStateStub.h:245`, `LokiStubGameMode.cpp:135`) while the backend advertises `MaxTeamSize: 3` to the same client — an unnoticed contradiction inside our own stack |
| **Deployment** | `ags` binds `":8080"` (all interfaces — *not* loopback-only, contra a common assumption); the loopback binding is the client-side hosts file plus cert SANs. But 0 of 135 shim DLLs are in git, there is no build script, and 956 KB of load-bearing memory is outside version control. `LAN`, `second Steam account` = 0 hits |

### 8.3 Cheapest routes to two participants (ranked)

1. **`SplitScreenMod`** — a complete second-local-player harness is **already installed and disabled**
   at `ue4ss/Mods/SplitScreenMod/Scripts/main.lua` (Ctrl+Y = `UGameplayStatics::CreatePlayer`,
   Ctrl+U = RemovePlayer, Ctrl+I = teleport). `CreatePlayer`/`SplitScreenMod` = 0 hits anywhere.
   ⚠ **Blocked by the CONFIRMED UE4SS wall** — it cannot load. Its value is now as a *reference
   implementation* for a hand-rolled `CreatePlayer` call through the existing native-call primitive,
   which is a genuinely cheap experiment on the force-open route (client is already authority).
2. **Bots** — `CoreGameBotConfig{BotTeams, FillPartialTeamsWithBots, …}` is a field of the GameConfig
   we already serve and omit; `BP_Minion_TargetDummy.uasset` and `Bots/BP_BotSpawnLocation.uasset`
   ship; bots are already observed spawning in the tutorial (`SpawnBots`, ~166 live pawns per S67).
   **No second identity, no second machine, no second Steam account.**
3. **Custom game lobby** (E4) — bypasses MMR, matchmaking, queue eligibility and region latency.
4. **A spectator connection** (E10) — weaker requirements than a player (no possession, no movement,
   arguably no reservation) while still exercising a second NetConnection and per-connection
   relevancy.
5. **Two real clients** — needs the SteamID64 fix, a second Steam account, and a survey of the
   single-instance tooling: `inject-secondaries.ps1:38` and `shim-status.ps1:78` both address the
   game by process **name**; every shim writes a fixed `docs/*-marker.txt`; the PI mutex is
   session-global; both instances share one `Saved/` tree.

### 8.4 Unposed multiplayer questions

`PartyBeacon`/`SpectatorBeacon` reservation handshake (0 hits — a stall here would look like an
unexplained travel hang); `PremadeRestrictions`/`RestrictionBreakPenalty` (may gate 2-person queueing);
`PartyMember.Latencies` + `/latencies` (may be the "??? — ms" region row, currently attributed to QoS);
team assignment (`LokiTeamComponent`/`LokiTeamState`/`LokiTeamStatics` = 0 hits, and the force-open
hero has **no team at all**, which may be why parts of the HUD never populate); the invite channel
(`DiscordJoinSecret` vs `/sendInvite` vs `/join?joinSecret=` vs an invite code — `buildSoloParty`
serves both `joinSecret` and `invitationToken` as empty placeholders); text chat as the cheapest
possible A→B proof.

---

## 9. Definition of Done + Is the Current Route on the Critical Path?

### 9.1 There is a goal name; there is no acceptance predicate

`README.md:39` lists M1–M3 complete and **"🚧 Milestone 4 — get into a match"** (with stale body text
saying "no hero" — the hero has rendered since S98 and the GAS gate cleared at S103).
`memory/supervive-revival-overview.md` says *"Open-source, **community-play intent**."*
`CLAUDE.md` says *"Current frontier = the match-setup layer."*

`milestone 4|milestone 5` = **1 hit repo-wide**. `definition of done` = 1 hit, and it is a
per-session acceptance checklist inside one handoff prompt. `minimum viable` = 0.

**What is missing is operationalization**, and it is decision-changing:

| Target | Makes IRRELEVANT | Makes MANDATORY |
|---|---|---|
| (a) Playable solo tutorial | Party/queue write surface, QoS, WS push, friends, presence, identity | Lesson chain, abilities, a combat target |
| (b) Solo sandbox in a real map | Same, plus matchmaking | World data (`.umap` cells), the BR zone, PSO/hitching, DayNight |
| (c) Offline bot match | Same | The bot system (A11), match rules, EoG |
| (d) 2-player private match | Matchmaking, QoS, MMR | **Identity (SteamID64), 2-member party, invite channel, custom games, a second NetConnection** |
| (e) Real multiplayer server | — | All of (d) + replication graph + deployment + packaging |
| (f) Live-service parity | — | Everything, plus the seasonal/time-dependence question (G3) |

Note that **"community-play intent" resolves this**: it implies (d) or (e), which means the party
write surface, identity and the second connection are on the critical path — and the tutorial route's
remaining ledger largely is not.

### 9.2 Is the client-side tutorial force-open on the critical path?

**The case FOR (honest):**
- It is the **only** route that can complete a tutorial objective at all. `OnObjectiveComplete` is
  `FUNC_BlueprintAuthorityOnly`, so a DS client structurally cannot — a *measured* basis, written
  down, with an explicit two-path fork weighed on stated grounds in `docs/session-64`. The claim that
  "the route decision has never been written down as a decision" is **false**.
- It produced genuinely transferable primitives: the native-call primitive, `CallBPGuarded`,
  `AddComponentByClass`, spawn/possess/teleport, camera control.
- It is the only place a hero has ever rendered, animated and moved.
- Its remaining blockers now have measured gates (`PlayerState+0x4F8`) and a working sibling recipe
  (the DS CDO-borrow, audit item 1.1) that nobody has ported.

**The case AGAINST (equally honest):**
- It is **single-player and standalone-authority by construction**, so it cannot be a step toward
  (d), (e) or (f) — the only targets the stated goal implies.
- Its remaining ledger (abilities, combat, enemies, items, 25 lessons) is 100% simulation work whose
  **transferability to a multiplayer target has never been argued**. That sub-question is genuinely
  unposed and is the real content of the "local maximum" worry.
- ~~It is throttled by a deterministic crash at 173–201 s (FK-7) that nobody has opened.~~
  **RESOLVED S112** — FK-7 was our own standing `.text` patch; the shipped shim removes it and runs
  hold 600 s. What still throttles the route is **FK-31**, the staging hazard (27 % of launches die
  before the probe is injected), which is a different mechanism in a different window.
- It has never been compared against **custom games**, **practice mode**, or **FFA/Arena-with-bots** —
  and no doc anywhere makes that comparison. The audit's Tier-1 list contains **no target-selection
  item at all**.

**Verdict.** The route is *correctly chosen for target (a)* and is *not* on the critical path to the
stated goal. It is not a dead end — it is a **local maximum that has never been scored against
alternatives**, because there is no target to score against. The fix is one paragraph (§10 item 1),
not a pivot.

---

## 10. The Cold-Start Shortlist — everything answerable offline, in minutes or hours, without launching the game

*Ranked by (value if answered) × (cheapness). Every item here is free.*

### Minutes each

| # | Action | Answers |
|---|---|---|
| 1 | **Write one acceptance sentence into CLAUDE.md** (ask the user; e.g. "two accounts complete one Arena match end-to-end") | §9 — unblocks all prioritization |
| 2 | `python` the `ELokiGameFeatureToggle` block out of `schema.txt` | A1 — 149 named levers; retires the seed-guessing in S88–S90 |
| 3 | Read `UserSettings.ini` + `GameUserSettings.ini` | FK-2, B1, B2, B3 — the input table, the lesson ledger, the muted master |
| 4 | Re-run the Angelscript census on `PrecompiledScript.Cache` (count `__StaticType_` + `.as`) | FK-1 — reopens the deploy/respawn/FFA layer |
| 5 | Delete the `.rdata 63.12%` line from the audit; re-run `vtscan`/`strings` **in UTF-16** against `merged.dump.exe` | FK-3, FK-4 — un-caps two techniques |
| 6 | Read `Party` @ `schema.txt:40988`; add `"state": "default"` to `buildSoloParty` | A2 — replaces a per-launch memory poke with a JSON field |
| 7 | Read `Manifest_DebugFiles_Win64.txt`; check whether Steam exposes a debug depot for appid 1283700 and whether GUID `BFDF6AC9…` resolves on a public symbol server | C1 — a PDB would collapse the weakest domain in one step |
| 8 | Extract the exe route table with a **UTF-16** scan → `docs/exe-route-table.md` | E5 — ~120 routes vs 40 |
| 9 | Read `thirdpartylicenses.txt` + `preloader.dll` + Diagnoser strings | FK-10, C7 — the real threat model |
| 10 | Read `tools/extractor/out/DefaultEngine.ini` | FK-5, FK-11, FK-23d, E12 — three open questions at once |
| 11 | Decode the SteamID64 from `platform_token` in `docs/capture.log` | §8 — turns "no identity layer" into a 10-line fix |
| 12 | Read the three party handlers; reorder to prefer the JWT subject | §8 — kills a latent 2-player data-corruption bug before it exists |
| 13 | Read `DT_{LoadingScreen_GameMode, ModeExplainer, QueueDisplayDataTable}.json` | A4, FK-23a, A5 — what the game IS, and the real queue list |
| 14 | Concatenate `catalog/st/*.json` → `docs/strings-reference.md` | A6 — the in-match economy and XP model |
| 15 | Record `buildID` + manifest hashes + `Changelist=156430` → `docs/build-fingerprint.md` | C2, audit 0.8 — cheaper than budgeted |
| 16 | Correct CLAUDE.md's extractor subcommand list; add `bpdump`/`wherefile`/`peekpak`; note there is no `raw` | FK-23c — two roadmap items are blocked on a tool that must be *written* |
| 17 | Read `Saved/ImageCaches/ImageCacheIndex.json` | B7 — 55 dead-CDN URLs + an unenumerated menu surface |
| 18 | One web search: does a SUPERVIVE wiki / datamining / modding / revival community exist? | F9 — the entire tuning layer, or a definitive negative |
| 19 | `SecondsSinceStart` histogram over the 86 XMLs; correct `session-39:82` | FK-8 |
| 20 | Read `Loki/Config/BlackBox.ini` (once a raw-extract path exists) | C8 — possibly the integrity-check config |

### Hours each

| # | Action | Answers |
|---|---|---|
| 21 | **Aggregate the 86 `CrashContext.runtime-xml`** → `(time, error, crashed thread, RVAs, base)`; cluster by `PCallStackHash`; correlate against `git log` dates | B4, FK-7, FK-9 — 512 RVAs and the deterministic crash |
| 22 | **Extract `.pdata` from minidump stream 13** and re-import into Ghidra | B5 — ends heuristic function-boundary recovery across all decrypted `.text` |
| 23 | Parse `Binds.Cache` (and `.Headers`) | A3, C12 — 15,068 signatures; a module partition of the binary |
| 24 | Parse the 17 `.utoc` chunk tables | D1, D2 — corrects "100% enumeration" to "17% of content bytes" |
| 25 | Harvest the 2,283 `build-staging` `__FILE__` literals + xref from readable `.text` | C12 — a free symbolization oracle for ~120,000 unnamed functions |
| 26 | ✅ **DONE S116** — diffed (326 reproduced to the digit), all **five** usmaps' schemas decoded, canonical MD5 table + consumer map recorded (`docs/fk14-usmap-settled.md` §7). **Superseded by the fix itself** (`1b6f9de`): the root cause was found and repaired, so the diff is now history rather than a diagnostic. ⚠ Two consumers still load **stale** usmaps by hardcoded path (`asdump.py`; `analyze.py`/`compare.py`) — was LOW severity because enum tables were byte-identical, and **that reasoning has now expired**: the fixed base contains 1,813 enum records it did not before. | FK-14 |
| 27 | Read the `/eog/`, `/custom/`, `/storefront/cheats/wallet/`, `/mailbox/` schema shapes and draft the EoG payload model | E1, E3, E4, E8 |
| 28 | Watch `ClickTutorial/SNF_Tutorial_2_Drop_*.mp4` and `DropPhase_DropMapTransition/*.mp4` | C3 — the only footage of the systems S89–S93 reconstructed blind |
| 29 | ✅ **DONE S121** — re-merged all 11 dumps; no rebase was needed (`.text` holds 0 of 1,403,750 relocs). `dumps/merged2.dump.exe`, 15,833 → **16,625** pages | FK-18, FK-19, audit 0.2 |
| 30 | Enumerate the 19 first-party `.uplugin` JSONs | C9 — `LokiSocketSubsystem`, `GameFeatures/LokiWinter` |

---

## 11. Ranked Focus Plan

*Merged with, and cross-referenced to, `coverage-audit-s101.md` §8. Ordered by
(value if answered) × (cheapness), with the challenger-adjudicated evidence.*

### Tier A — Free, offline, changes what the project does

| # | Action | Ref | Cost |
|---|---|---|---|
| A-1 | Write the acceptance predicate for "done" | §9 | minutes |
| A-2 | ✅ **HALF DONE (S120).** The 149 names are extracted to `tools/re/out/game_feature_toggle_enum.txt` (values 0–148; the declared "151 values" counts two sentinels — **state the unit**). ⚠ But A-14 showed these enum names are **not** what the UI's visibility gates read, so re-mapping S88–S90 against them is still open and is now a *gameplay*-toggle question, not a UI one | A1 | minutes |
| A-3 | Read the two client `Saved/Config` inis | B1–B3 | minutes |
| A-4 | Re-measure the Angelscript census; retract S74's generalization | FK-1 | minutes |
| A-5 | Kill the `.rdata` cap; re-scan in UTF-16 (routes, strings, vtables) | FK-3/4, E5 | minutes |
| A-6 | Serve `Party.State`; retire the per-launch poke | A2 | minutes |
| A-7 | Chase the shipping PDB (RSDS GUID + Steam depot) | C1 | minutes |
| A-8 | One web search for prior art | F9 | minutes |
| A-9 | Fix the doc defects: CLAUDE.md subcommands, EAC prose, CEF/Electron, `Loki/Config` "never read", the PI-hook staleness, README M4 | FK-17, FK-23b/c/d/f | minutes |
| A-10 | Aggregate the crash corpus | B4 | hours |
| A-11 | Recover `.pdata` from stream 13 | B5 | hours |
| A-12 | Parse `Binds.Cache` | A3 | hours |
| A-13 | The `.utoc` chunk census | D1 | hours |
| **A-14** | ✅✅ **CLOSED (S121) — THE SURFACES DID APPEAR; the S120 verdict below was one word away from working.** `ConfigKey` is **`"enabled"`**, not `"default"`, so every `Map_Find(entry.Config, ConfigKey)` had MISSED since S73 and each gate silently fell back to its own `IsEnabledByDefault`. Serving both sub-keys turned on **12 of 15** served declarative gates. ★ **The declarative vocabulary now CLOSES with no remainder: 50 = 12 served + 33 `IsEnabledByDefault=true` (NEVER SERVE) + 1 withheld (`BypassTutorialAndOnboarding`, which REMOVES a surface) + 4 candidates, all four flown.** Screenshot-confirmed surfaces: STORAGE tab, LEADERBOARDS page, DISCORD button, DEBUG BATTLEPASS rail entry, TOP UP, ARMORY progression header, and three lobby boost icons (one tooltipped `JUICED — Battlepass XP gain accelerated`). ★★ **A-14 also turned out to be an ENDPOINT-DISCOVERY instrument, not just a UI one** — enabling `leaderboards` made the client call `/player-stats/leaderboard`, `/mmr/leaderboard` and `/player-stats/players/{id}`, none of which had *ever* been seen on the wire; the first is now implemented and the page renders real rows. ★★ **The readout the S120 entry said was missing now exists** (`tools/re/toggle_readout.py`, read-only RPM, no injection): the gate widget stores its answer in `Is Content Enabled` @ +0x473, and `IsEnabledByDefault==false AND enabled==true` is reachable only via our served value. 133 live instances, both controls passing in one run. ⇒ **a dark surface is no longer ambiguous** — `NeLobbyEventBtn` is measurably ON while invisible, i.e. an unmet companion condition, not a flag problem. ★ **Config changes need NO relaunch** (measured, single-variable: `ags` restart only, 3 treatment keys flipped, all 43 controls unchanged). `docs/s121-toggle-fix-confirmed.md` | FK-36d, FK-37, A1 | **done** |
| ~~A-14 (S120 verdict)~~ | ~~✅ **DONE (S120) — vocabulary SETTLED, payload SHIPPED, surfaces did NOT appear.**~~ ★★ The headline is a correction: **we were serving the wrong vocabulary into the right map.** All five keys we shipped since S73 are `ELokiGameFeatureToggle` ENUM names (that system's readiness is round-gated, S85); the UI calls `IsFeatureEnabled(FString, bool)` with keys that are Blueprint bytecode literals **absent from the exe**. Exhaustive bpdump over all 21 calling assets: **30 call sites / 26 declared locals / 10 distinct keys** — and `bDefault` is the SECOND ARG, so `EmoteSFX`/`KillStreakAsRomanNumeral`/`voicechat` are already ON and must NEVER be sent. Now serving `motd`, `LobbyRewards`, `exchangetokens`, `ArmoryOnboarding`, `ArmoryItemProgression` (knob `AGS_UI_TOGGLES=0`). ⚠ Applied by the client 4x (eTag confirmed) on both a live re-poll and a cold relaunch, and **no new UI surface appeared** — but there is NO readout that any gate evaluated true, so this is NOT a measured negative on the toggles, only on the surfaces. `docs/s120-feature-toggles.md` | FK-36d, A1 | done |
| ~~A-14 (original)~~ | ~~**Serve the `LobbyRewards` feature toggle.**~~ `WBP_UI_LobbyRewards::ShouldShowLobbyRewards` = `IsFeatureEnabled(ClientConfigManager, "LobbyRewards") AND Rewards.Num > 0` [M, bpdump]. We serve `featureToggles` from `handleClientConfig` and send **five** toggles; `LobbyRewards` is **not among them**, and that widget has logged **0 activations ever**. One map entry may switch on a whole reward screen nobody has seen — the same shape as the FK-17 banner win. ⚠ Pair it with A-2: 149 toggle names are enumerable and we serve 5 | FK-36d, A1 | **minutes** |
| **A-15** | Promote the S120 before/after image-diff probes (`diffcallers.py`, `namepages.py`) from scratchpad into `tools/re/`. They are the only working instrument for "which code did this action run", and they currently exist only in a session temp dir | FK-36, §7.2, F7 | minutes |

### Tier B — One session, on the machine

| # | Action | Ref | Why now |
|---|---|---|---|
| B-1 | Turn the logs up (`-LogCmds`, fallback `[Core.Log]` in the user `Engine.ini`) and record the newly-alive category set | FK-11, §5.2 | The cheapest instrument the project can own; ~825 categories silent |
| B-2 | Disassemble the 8 RVAs of the deterministic tutorial crash | FK-7 | Unblocks every >3-minute experiment |
| B-3 | Fix the stale readiness gate + `-NoPasses` forwarding, then one clean 6-shim validation launch | Wall #3, audit 1.5 | Re-baselines all 6 front-end surfaces; the suspected root cause is a one-liner |
| B-4 | ~~Capture `-State tutorial` during a force-open and re-merge~~ ✅ **BOTH HALVES DONE** — capture S111 (`dumps/tutorial-hero`), **re-merge S121** (`dumps/merged2.dump.exe`, 52.29 % → **54.90 %** by page). Successor: capture **hero select / drop phase / a live match / end-of-game** — 0 captures exist from any of them | FK-20, FK-18 | The highest-yield `.text` capture available |
| B-5 | Serve `Extra.FeatureToggleOverrides` + `GameConfig.CVars` on `/core-game/matches/{id}` | E2, FK-23e, Wall #6 | A backend field vs three sessions of bit-splicing |
| B-6 | Try `-as-development-mode` (flag only, cache intact) | F1 | The game has told us 87 times |
| B-7 | Restore the queue list, click BATTLE, read what the client asks for next | FK-5, Wall #1 | Settles whether QoS is even the blocker |
| B-8 | ✅ **RESCOPED S117** — ★ send the literal text `FK15-PROBE-FROM-AGS` on the **messenger** (no ini change; baseline is a measured zero over 1,419 connections), then the TEXT heartbeat, then `dsNotif`, then sweep all 33 notif types — all one-click in the panel's WS Push tab. ⚠ `LogJson` is the WRONG detector (0 lines in 326 logs), and **`LogAccelByte` is NOT the dispatcher's category** — use `-Preset Ws`, which raises `LogAccelByteLobby` to VeryVerbose | FK-15 (`docs/fk15-ws-push-audit.md`) | ✅✅ **DONE S118 — nothing left here.** All 33 swept and dispatching; the delegate join then showed **only 7 of 33 have a subscriber**, and **all 7 flew, 6 with visible UI effect**. ⚠ `dsNotif`, named above as a target, is **UNBOUND**. Successor work is the *response* surface (a real friend store), not more pushes. |
| B-9 | Strip the `[HTTP.Curl]` / `[SSL]` override from the user `Engine.ini` (clear ReadOnly first), **keep** the CA append, one `-NoHook` menu launch — does login still reach the roster? | G8 | **Decides whether the redirect's trust model can be the CA alone.** The two mechanisms have been applied together since the redirect was built and never separated; `launch-redirect.ps1:18` reads as though the CA append was the primary and the override was added for an early-init ordering problem it documents at `:288-290`. If the CA suffices, the wider hole closes for free and key rotation starts to mean something. ⚠ **Positive control required:** the run must reach the HUNTERS roster, not merely "not crash" — a TLS failure at menu load is the `ags-cert-rebuild-gotcha` signature and is indistinguishable from several unrelated failures. ⚠ Single-variable: do **not** rotate the certs in the same launch |

### Tier C — Multi-session, real research

| # | Action | Ref |
|---|---|---|
| C-1 | Build the EoG payload model offline and drive it through the existing match-result harness | E1 |
| C-2 | Pick the playable target: **`LVL_Practice`** or **FFA/Arena-with-bots** over `LVL_Training` | §5.3 |
| C-3 | Fix the identity layer (parse SteamID64) + the member-write ordering + a 2-member party document | §8 |
| C-4 | Build the missing instruments: per-route hit counter, entry-hit counter, module-full-path probe, crash-corpus aggregator, screenshot retention | F3–F5, F7 |
| C-5 | An Angelscript disassembler (upstream UnrealEngine-Angelscript opcode table) | F6, FK-1 |
| C-6 | Write `docs/WALLS.md` mapping each wall to its assertion date, method, and the capabilities that postdate it | G4, G5 |
| C-7 | Answer G1 (is the game re-obtainable) and back up accordingly | G1 |

### Explicitly de-prioritized by this audit

- The `webcache_4430` CEF profile and `.sentry-native/reports` — **both measured empty.**
- The ICU `.res` bucket and the Slate PNG/SVG bucket — stock engine content.
- Re-litigating: UE4SS loading, `.pdata` availability *from the image*, `.umap` extraction as
  research, path-enumeration completeness, the C++-exception ban's VEH ordering
  (`AddVectoredExceptionHandler(1, …)` is already used in 11 shims), the party version counter,
  `RequiresDropLeader` (already served), `content-service` (already implemented).

---

## 12. Appendix — What the Challengers Dropped, and Why

**37 of ~293 adjudicated claims (~13%) were dropped outright.** The pattern is informative: the
single largest cause was **a fabricated or unrun negative search** — a prober asserting "0 hits"
without grepping the one document that answers it, usually `docs/findings.md` or the coverage audit
itself.

| Dimension | Dropped claim | Verdict and reason |
|---|---|---|
| player-journey | "Which journey steps have never been observed" | ACTUALLY_KNOWN — audit lines 26/203/406/412 state it; also over-claimed "ever" from 26 rolling logs |
| original-architecture | "Is the AccelByte-impersonation model right?" | Premise refuted — `DefaultEngine.ini:453` has ClientId/Namespace/BaseUrl; `findings.md:19` already records the ClientId |
| original-architecture | "`/content-service/manifest` is a per-match gate" | ACTUALLY_KNOWN — `handleContentManifest` implemented across 18 files |
| original-architecture | "Is EasyAntiCheat compiled in?" | ACTUALLY_KNOWN — `findings.md:186` verified no EAC |
| unopened-artifacts | "What is in `Loki/Config/*.ini`?" | ACTUALLY_KNOWN — audit §3.5 + item 0.4 (though the *extraction* is also already done — FK-23d) |
| unopened-artifacts | "What is in `Game.locres`?" | ACTUALLY_KNOWN — audit §3.4 + item 1.8 |
| unopened-artifacts | "Is the CDO bug the shared root cause of missing display names?" | Misquotation — the audit says "item stats," not "display names," and explicitly carves out locres |
| unopened-artifacts | "Is `ALokiPlayerCheats` Angelscript, breaking the thunk plan?" | ACTUALLY_KNOWN — `cheat_enum.py:114` decodes `FUNC_Native`; the S74 dump shows `[…,Native,BPCallable] thunk=0x…`; the names occur in `Binds.Cache` and **0×** in `PrecompiledScript.Cache` |
| unopened-artifacts | "Does `BPModLoaderMod` allow loose BP mods?" | ACTUALLY_KNOWN — UE4SS never runs |
| unopened-artifacts | "Has enumeration been validated against the manifest?" | ACTUALLY_KNOWN — the check resolves to **0 residual** (85,508 `.uexp` folded into `.ucas` + 16 `.pak`) |
| unopened-artifacts | "Is `Saved/Engine.ini bVerifyPeer=false` ours?" | ACTUALLY_KNOWN — `launch-redirect.ps1:296-300` writes it and `:187-190` strips it (line numbers drifted from the `271-284`/`167-173` recorded here at S101; re-verified against HEAD). ⚠ **The successor question was never posed.** *"Is it ours?"* was answered; **"is it still necessary?"** was not — and it is unknown, because the CA append (`:259`) and the verification-off have been applied together on every launch since the redirect was built and never independently. A dropped claim closed the file on its own follow-up. See **G8** and **B-9** |
| unopened-artifacts | "Do `_AS` classes mean the DS mirrors the wrong classes?" | Premise not established — the 18 `_AS` symbols occur **0×** in `Binds.Cache` and **0×** in `schema.txt`; S70's mirror is a live-measured success |
| unopened-artifacts | "`_legacy_ue4ss_backup` — which loads?" | Dies with UE4SS; also not on the search path |
| unopened-artifacts | "Are the 16,999 `.ubulk` / 690 PNG+SVG worth anything?" | A recorded negative result, not an unknown (and it does not address `.ubulk`, which D1 does) |
| false-knowns | "Is path enumeration really 100%?" | ACTUALLY_KNOWN — verified TRUE; a belief that survives its challenge is not a false-known |
| false-knowns | "Is `.pdata` genuinely unavailable?" | ACTUALLY_KNOWN — the belief survives (see §4.2) |
| walls | "Why has no `.umap` been dumped?" | ACTUALLY_KNOWN — audit item 2.1 already prescribes the `_Generated_` cells *and* the persistent-map caveat |
| walls | "Was a first-in-chain VEH ever tried?" | **FABRICATED** — `AddVectoredExceptionHandler(1, CrashVEH)` appears in ≥10 shipped shims |
| never-exercised | "Is the merged dump state-limited?" (×2 claims) | ACTUALLY_KNOWN — audit line 283 already measures +2,044,822 bytes and rejects the "strategy falsified" reading |
| never-exercised | "94 `LVL_*`, 3 loaded" | ACTUALLY_KNOWN — audit lines 190/386/406 |
| never-exercised | "Has matchmaking ever been entered?" | **FALSE** — `/party/matchmaking/info` + `/customGameModes` are polled every ~2 s in `docs/capture.log` |
| never-exercised | "Have the settings screens been opened?" | NOT_AN_UNKNOWN — the settings *system* runs every launch and rewrites its inis; settings is not one of the 44 enumerated surfaces |
| instrument-blindness | "Is UE4SS a confound?" (×2 claims) | ACTUALLY_KNOWN — `findings.md:188-192`; independently reconfirmed via minidump ModuleList |
| instrument-blindness | "Does `.sentry-native` hold crashes UE missed?" | **MEASURED EMPTY** — `reports/` and `attachments/` contain zero files |
| multiplayer-void | "Does the global party version break with 2 members?" | Backwards — one shared party document means one shared counter is correct |
| multiplayer-void | "Is the DropPlane wall a missing drop leader?" | ACTUALLY_KNOWN — `interactive.go:639` serves `RequiresDropLeader:false` and `:652` serves `IsDropLeader:true` |
| unreadable-content | "Why has no `.umap` been dumped?" | Duplicate of the walls drop |
| unreadable-content | "Does `Binds.Cache` declaration order give native offsets?" | Premise broken — class member lists are the script-visible subset; **every** offset cited as motivation lives in a class with an incomplete list |
| unreadable-content | "`.sentry-native`" | Measured empty |
| unreadable-content | "Do the 3,438 ICU `.res` files matter?" | NOT_A_REAL_QUESTION — the prober answers "almost certainly not" itself |
| unasked-questions | "Is UE4SS loading during measurements?" | ACTUALLY_KNOWN — same as above; the prober asserted "no launch-time check exists" without grepping `findings.md` |
| definition-of-done | "Is EAC present?" | ACTUALLY_KNOWN — measured and written down twice |
| definition-of-done | "Is `BP_TrainingSkill_*` really a dead end?" | ACTUALLY_KNOWN — measured via `bpdump @props` on `ValidStates` **and** a live forced-gate experiment. The 2026-07-24 ini timestamp offered as counter-evidence **is the footprint of that experiment** (commit b82b0e4, same date) |
| definition-of-done | "Is the cheat surface open via input actions?" | NOT_AN_UNKNOWN — `AreHotkeyCheatsEnabled_Impl = xor al,al; ret` **is** the hotkey gate; the spawn-dummy actions have `Key=None`; no `LokiPlayerCheats` instance exists |
| definition-of-done | "What does CEF render / what is in `webcache_4430`?" | **MEASURED** — 0 hosts in the cookie jar; only Chromium defaults in `Network Persistent State`; nothing written since 2024–2025 |

### Cross-dimension disagreements, adjudicated

| Question | Disagreement | Resolution |
|---|---|---|
| **EasyAntiCheat present?** | unasked-questions → FALSE_KNOWN; original-architecture and definition-of-done → ACTUALLY_KNOWN | **2 of 3 win.** Kept as FK-23b, a **doc-hygiene nit** (two stale prose lines, incl. a self-contradiction inside `findings.md`), explicitly *not* a decision-steering belief — the risk posture is correctly grounded on preloader.dll + the integrity check |
| **Cheat surface open?** | instrument-blindness → input path untested; definition-of-done → hotkey gate disasm-verified closed | **The more specific evidence wins.** Native dispatch is a CONFIRMED wall. What survives is (a) the disjoint **script** `AuthCheat*` family (FK-6) and (b) the narrow fact that ~40 of 43 `Cheat*` action names appear in neither the 65-function nor the 137-event set |
| **CEF a live egress surface?** | unasked-questions → live every launch; three others → webcache empty | **Both are true and not contradictory.** CEF initialises in-process every launch (kept, FK-17 / §6.3); the *profile* holds no game content (dropped as an egress claim). The surviving question is the **render path** for News / Event Hub / Referral |
| **Is "done" defined?** | unasked-questions → UNKNOWN_UNKNOWN; definition-of-done → KNOWN_UNKNOWN (README M4 exists) | **Merged:** a goal *name* exists and is stale; an acceptance *predicate* does not (§9) |
| **On-disk `.rdata` value** | false-knowns → critical new source; walls → the dump already supersets it | **Challenger wins.** The false-known stands; the *action* is "re-scan in UTF-16," not "go get the on-disk exe" |

### Provenance and limits

- **Inputs:** 11 independent probes, each adversarially challenged against primary artifacts
  (game tree, `%LOCALAPPDATA%\SUPERVIVE`, `dumps/`, `schema.txt`, `tools/extractor/out/`,
  the 86 crash reports, 216 log files, `server/`, `configs/`, `docs/`, `memory/`, 366 commits).
- **Rule applied:** the challenger's verdict is authoritative in every disagreement.
- **Numbers:** where two agents measured the same quantity and differed (`.rdata` zero-pages 32 vs 33;
  log categories 139 vs 176; crash RVAs 292 vs 512; `.umap` totals 94 vs 65 top-level), the larger,
  more carefully-derived measurement is quoted and the discrepancy is stated. **Treat every count in
  this document as reproducible-but-unverified-twice unless the text says otherwise.**
- **Deliberately not quantified:** in-match behaviour, unobserved egress, and Angelscript-implemented
  logic. Their denominators are unknown, so no percentage would be honest. Ordinal bands and raw
  counts are used instead.
- **This document can be wrong the same way the audit was.** Two round-1 findings were themselves
  false (G7). Apply the same rule to this file: *before acting on a "0 hits" claim here, run the grep.*
