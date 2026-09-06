# strxref state coverage — quantifying the real cap on static analysis, and how to lift it

**Session S102 · 2026-07-26 · offline only (no game launched, no injection, dumps read-only)**

Companion to `docs/coverage-audit-s101.md` and `docs/ignorance-map-s101.md`.
Tooling: `tools/strxref/` (`strxref.py` + the analysis scripts added here).

Every figure below is **MEASURED** unless explicitly labelled INFERRED or ESTIMATE.
FK-3 and FK-4 both exist because a measurement artifact got recorded as a structural
fact; two more of the same family are corrected here, and one candidate claim was
measured, falsified, and dropped rather than written down.

---

## 0. Headline

> ## ★ UPDATED 2026-08-14 (S121) — the re-merge in row 2 has been EXECUTED
> `dumps/merged2.dump.exe` is the canonical cold image: **16,625 / 30,281 pages = 54.90 %**, and the
> strxref index is rebuilt against it. Two dumps captured after this file was written are included
> (`tutorial-hero` 16,112 / 53.21 % — the best single image on disk; `lobby-dispatch-decrypted`
> 15,381 / 50.79 %), and cross-base inputs now merge (FK-19). Crash-table corpus grew 70 → **76**
> usable tables, union 382,282 → **382,704** functions. See
> `docs/fk18-fk19-multistate-merge-settled.md`.

| | before | after this session | **after S121** |
|---|---|---|---|
| best `.text` page coverage | 52.29% (`merged.dump.exe`) | 52.29% *(unchanged — see §1)* | **54.90 %** (`merged2.dump.exe`) |
| `.text` coverage a re-merge of everything on disk would give | — | **54.27%** (+602 pages, +2.35 MB) | **executed: 54.90 %** (+792 pages) |
| `.text` coverage a dump from a *crash-era* state would give | — | **62.45%** (+3,430 pages, +13.4 MB) — measured, not guessed | **62.68 %** (best of 76 tables) — still uncaptured |
| function bounds | 0 known; every extent heuristic | **382,282 EXACT bounds** recovered offline | **382,704** |
| known code addresses / functions | 617 / "~120,000" (0.5%) | 617 / **≥382,282** = **0.16%** — the denominator was ~3× too small | — |
| **crash-table functions with readable BYTES** | — | 342,763 | **356,402** (+13,639) |
| **crash-table functions named but BYTELESS** | — | 39,941 | **26,302** (−34.2 %) |

**The single most valuable result: the missing `.pdata` is recovered.** 70 of the 85 crash
minidumps carry the real x64 unwind table in stream 13. Unioned, they give **382,282 exact,
non-overlapping function bounds** covering 54.7% of `.text` — including **39,836 functions in
pages no image dump has ever decrypted**. `docs/ignorance-map-s101.md` B5 predicted this;
it is now verified, extracted, and wired into `strxref.py`.

---

## 1. `dumps/` audit — the merge is not broken, it had nothing to merge

### 1.1 What exists

| dir | date | PID | ImageBase | `.text` pages | % |
|---|---|---|---|---|---|
| `menu` | 07-17 15:22 | 4080 | `0x7FF6AF000000` | 15,739 | 51.98% |
| `store` | 07-17 15:23 | 4080 | `0x7FF6AF000000` | 15,781 | 52.12% |
| `roster` | 07-17 15:25 | 4080 | `0x7FF6AF000000` | 15,831 | 52.28% |
| `missions` | 07-17 15:25 | 4080 | `0x7FF6AF000000` | 15,833 | 52.29% |
| `loadout` | 07-17 15:26 | 4080 | `0x7FF6AF000000` | 15,833 | 52.29% |
| `accountpass` | 07-18 17:39 | 77272 | `0x7FF6AF000000` | 15,395 | 50.84% |
| `vmbuild` | 07-18 21:31 | 70728 | `0x7FF6AF000000` | 15,406 | 50.88% |
| `toggles` | 07-21 02:27 | 27900 | `0x7FF6AF000000` | 15,324 | 50.61% |
| `rcb` | 07-23 00:47 | 52104 | **`0x7FF79D3B0000`** | 15,485 | 51.14% |
| `tutorial-hero` | 08-05 19:13 | 38064 | **`0x7FF6505C0000`** | **16,112** | **53.21%** |
| `lobby-dispatch-decrypted` | 08-13 16:13 | 29856 | **`0x7FF7C7EF0000`** | 15,381 | 50.79% |
| **`merged.dump.exe`** | 07-17 15:46 | — | `0x7FF6AF000000` | **15,833** | **52.29%** |
| **`merged2.dump.exe`** | 08-14 03:32 | — | `0x7FF6AF000000` | **16,625** | **54.90%** |

⚠ The last three rows post-date this file. `tutorial-hero` is the **best single image on disk** and
was excluded from every merge until S121 purely because of its ImageBase (FK-19). Union of all 11 =
**16,625 pages**; the five 07-17 rows are strictly nested and jointly add **0** over `missions`.

(page = 4 KiB; "covered" = not entirely zero. For read-only `.text` in a flat `dumpimage`
image this is an exact proxy for "decrypted" — a genuinely all-zero 4 KiB code page does
not occur. It is **not** a valid proxy for `.rdata`/`.data`; that conflation is FK-3.)

### 1.2 Is `merged.dump.exe` actually a merge?

**Yes — and it is also exactly equal to one input.** Measured:

```
merged page-set == loadout page-set      : True
merged page-set == union of the 5 inputs : True
pages in menu/store/roster/missions/loadout NOT in merged : 0, 0, 0, 0, 0
```

`usmapdump mergedumps` worked correctly. The manifest's "910 / 107 / 124 / 54 bytes
contributed" is not a bug: **all five inputs came from the same process (PID 4080) over a
4-minute window at the same menu**, so four of them had literally nothing new. Pairwise
Jaccard among those five is 99.4–100%.

*(The ignorance map's read — "the merge is broken, four inputs contributed 1,195 bytes" —
is half right: the number is right, the diagnosis is not. Nothing to fix in the tool.)*

Coverage is also **monotonic within a process**: `menu ⊂ store ⊂ roster ⊂ missions =
loadout`, no page ever lost. Corollary, tested directly: the PE entry point page
(`0x751EFD0`), which executes exactly once at process start, is **still decrypted in all
10 images**. So the packer does **not** re-encrypt cold pages, and dump timing within a
session does not matter. (Hypothesis raised, measured, rejected — not recorded as fact.)

### 1.3 What was never merged in — and what it is worth

Four dumps postdate the 15:46 merge and are absent from it:

```
pages present in <dump> but NOT in merged.dump.exe
  accountpass    1
  vmbuild        7
  toggles      539      <- 2.11 MB
  rcb          270      <- 1.05 MB
```

Greedy incremental merge order:

```
1. +missions   15,833   -> 52.29%
2. +toggles      +539   -> 54.07%
3. +rcb           +56   -> 54.25%
4. +vmbuild        +7   -> 54.27%
5..9 menu/store/roster/loadout/accountpass  +0
```

**A correct re-merge gains +602 pages (+2.35 MB, +1.98 pp).** Real but small.

### 1.4 ⚠ `mergedumps` rejects `rcb` — and the rejection is over-strict (FALSE-KNOWN #5)

`tools/usmapdump/mergedumps.go:154` skips any input whose `ImageBase` differs, with the
manifest note *"its relocated `.text` bytes are incompatible"*. `configs/capture-dumps.ps1`
elevates this to a **HARD CONSTRAINT: "every state must come from ONE game process
lifetime … capture all states WITHOUT relaunching."**

**Measured: `.text` is completely base-independent.**

1. Base-relocation table, parsed from the image: **1,403,750 entries — 1,257,732 in
   `.rdata`, 146,018 in `.data`, and ZERO in `.text`.**
2. Empirical: `rcb` (base `0x7FF79D3B0000`) vs `merged` (base `0x7FF6AF000000`) share
   **15,215 decrypted `.text` pages and all 15,215 are byte-identical. 0 differ.**

So the constraint is right for `.rdata`/`.data` and wrong for `.text` — and `.text` is the
**only** section that demand-decrypts, i.e. the only one merging exists to fix.

**Fix:** in `mergedumps.go`, allow a different-base input to contribute `.text` (and
`.reloc`/`.rsrc`, which are also base-invariant) while still skipping its `.rdata`/`.data`.
Then drop the "one process lifetime" constraint from `capture-dumps.ps1`.

> ## ✅ DONE 2026-08-14 (S121) — `docs/fk18-fk19-multistate-merge-settled.md`
> **Every integer in §1.4 reproduced independently** (1,403,750 / 1,257,732 / 146,018 / **0**;
> rcb-vs-merged 15,215 shared pages, 0 differing) and the fix is implemented: `mergedumps` merges
> **`.text` only, page-granular, ImageBase-agnostic**, gated on an identical section table plus a
> per-donor overlap-conflict check. `capture-dumps.ps1`'s one-lifetime constraint is dropped and its
> base-drift warning downgraded to a note. Result: `dumps/merged2.dump.exe`, **16,625 / 30,281 pages
> (54.90 %)** vs merged's 15,833 (52.29 %). Rollbacks: `-wholeimage`, `-samebaseonly`.
> ★ §1.4 also **under-stated its own case**: the one-lifetime rule was not merely wasteful, it was
> **self-sealing** — within one lifetime `.text` decryption is monotone, so the snapshots are
> strictly nested and every capture after the first is worth **exactly 0 pages**. That is why the
> five inputs to `merged.dump.exe` bought 0 `.text` bytes between them.
> ⚠ Two dumps have been captured since this file was written and are now in the merge:
> `tutorial-hero` (2026-08-05, base `0x7FF6505C0000`, **16,112 pages / 53.21 %** — the best single
> image on disk) and `lobby-dispatch-decrypted` (2026-08-13, base `0x7FF7C7EF0000`, 15,381 / 50.79 %).
> The "+602 pages" figure at §1.3 was for the 9-dump corpus; with 11 it is **+792**.

This matters far beyond `rcb`: **ASLR gives a new base most launches**, so under the current
rule every future capture from a different session is silently discarded. It is the failure
mode that would quietly cap the entire capture plan below.

---

## 2. What the dark half is — which subsystems we cannot see

Census: 111,932 ASCII + 87,851 UTF-16 strings. Lit = ≥1 resolved code reference.

```
ASCII : 15,183 / 111,932 lit (13.6%)
UTF-16: 56,670 /  87,851 lit (64.5%)
```

UTF-16 lit rate by string length — longer strings are darker, because long strings are
error/verbose paths that only rare code emits:

```
  4-7 chars  59.1%     32-63    60.1%
  8-15       67.4%     64-127   48.1%
 16-31       72.6%    128+      32.7%
```

### 2.1 Lit rate by subsystem (`tools/strxref/subsystems.py`)

Each family is a set of substrings that occur only in that subsystem's messages; a string
is counted once, for the first family it matches. Raw counts shown so the rate is auditable.

| subsystem | lit | dark | total | **lit %** |
|---|---:|---:|---:|---:|
| physics / collision (Chaos) | 184 | 769 | 953 | **19.3%** |
| drop / deploy | 31 | 89 | 120 | **25.8%** |
| replay / demo | 60 | 138 | 198 | 30.3% |
| party beacon / matchmaking | 67 | 151 | 218 | 30.7% |
| **character movement / CMC** | 106 | 196 | 302 | **35.1%** |
| **replication / netcode** | 230 | 411 | 641 | **35.9%** |
| navigation / AI | 169 | 273 | 442 | 38.2% |
| **ability system / GAS** | 458 | 708 | 1,166 | **39.3%** |
| Loki gameplay (game-specific) | 145 | 194 | 339 | 42.8% |
| animation | 328 | 433 | 761 | 43.1% |
| renderer | 1,398 | 1,516 | 2,914 | 48.0% |
| Loki menu / frontend | 110 | 116 | 226 | 48.7% |
| UI / Slate / UMG | 170 | 121 | 291 | 58.4% |
| asset / IoStore / cooking | 237 | 165 | 402 | 59.0% |
| audio / Wwise | 811 | 410 | 1,221 | 66.4% |

**The dark subsystems are precisely the project's open blockers**: Chaos physics, drop/deploy
(`VisibleInDropPlane`, `SetVisibleInDropPlane`), character movement (`ServerMove`,
`ClientAckGoodMove` — the S71 possession wall and the S81 CMC-blocking investigation),
replication (`GameNetDriver`, `PendingNetDriver`, `BeaconNetDriver`), and GAS (S100's
"hero owns no ability system"). The subsystems that are *lit* are the ones already solved:
audio, assets, UMG, frontend.

This is the concrete form of "state coverage IS binary coverage": **the frontier is dark
because the frontier's code has never run in a process we dumped.**

Also measured, by `Class::` prefix (dark / lit):
`HairStrands` 85/21 · `FHttpNetworkReplayStreamer` 77/20 · `UActorChannel` 34/9 ·
`FReplicationReader` 20/3 · `ReplicationFiltering` 16/0 · `UPartyBeaconState` 13/1 ·
`UDemoNetDriver` 12/5 · `APartyBeaconHost` 9/0 · `FNetworkObjectList` 6/0 ·
`UAbilitySystemComponent` 6/1.

### 2.2 Two large dark populations that are *not* subsystem signal

- **Console variables.** The most common leading tokens among dark strings are `r.` (2,736
  dark / 382 lit), `p.` (696/74), `net.` (185/13), `au.` (147/9), `fx.` (246/5), `wp.`
  (62/0), `np2.` (64/1), plus help-text openers `Whether` (382/11), `If` (329/16),
  `Enables` (107/2), `Minimum` (47/0). Cvar names and help strings dominate the dark set.
  Spot-checked: `r.SceneCulling` has 0 refs in `merged.dump.exe` and **gains one from the
  `toggles` dump's extra pages** — so its registering code exists and simply had not run in
  the menu process.
- **`__FILE__` paths.** 2,455 source-path strings, 2,376 distinct files, only 484 lit. Lit
  files are the ones that actually asserted or logged in our sessions (`SceneVisibility.cpp`,
  `ShadowSetup.cpp`, `RenderGraphBuilder.cpp`, `GameFeaturePluginStateMachine.cpp`,
  `LokiServerAnalyticsManager.cpp`). These are `check()`/`ensure()` strings — a great
  subsystem label, and 80% of them are dark.

---

## 3. How much a richer state is worth — two measurements plus one bound

### 3.1 Measured marginal yield of real new pages

Scanning **only** the `.text` pages that `toggles`/`rcb`/`vmbuild`/`accountpass` have and
`merged` lacks, and resolving their `lea`s against the existing census:

```
toggles      539 extra pages   4,750 lea->.rdata   853 strings hit   461 NEWLY LIT
rcb          270 extra pages   2,913 lea->.rdata   391 strings hit   210 NEWLY LIT
vmbuild        7 extra pages      44               15                 8
accountpass    1 extra page      24               13                 7
UNION        602 extra pages                                        508 NEWLY LIT
  => 0.84 newly-lit strings per new .text page  (216 per MB)
```

What lit up is exactly what you would want: `ServerMove`, `ClientAckGoodMove`,
`ServerUpdateCamera`, `FBitArchive::SerializeBitsWithOffset`, `r.SceneCulling`,
`UpdateSceneCaptureContent_RenderThread`, `FilmGrain`/`MipGen`/`SSS::Visualizer` post-process
passes, `=== FDebug::DumpStackTrace(): ===`.

### 3.2 Rarefaction over the pages we do have

Randomly subsampling the 15,833 decrypted pages and counting distinct strings referenced:

```
 5% of pages ->  4,643 strings      60% ->  46,700
10%          ->  8,611              70% ->  53,274
20%          -> 17,187              80% ->  59,502
30%          -> 24,942              90% ->  65,461
40%          -> 32,910             100% ->  71,853
```

The curve is still essentially linear at 100% — **nowhere near saturation.** Tail slope over
the last 20%: **3.90 new strings per page.**

### 3.3 The bound, stated honestly

Two rates, 4.6× apart, and the difference is meaningful:

- **0.84 strings/page** is measured on *real* new pages — but all 9 image dumps are
  menu/lobby states with 90–100% pairwise Jaccard, so those extra pages are marginal
  extensions of already-covered code that re-references the same literals. This is a
  **lower bound**.
- **3.90 strings/page** is measured on a random sample of pages spanning every subsystem
  that ran, so it is the right model for **disjoint** new code — which is what a match state
  brings. This is the realistic figure for genuinely new subsystems, and an **upper bound**
  overall.

Linear extrapolation of the rarefaction slope to 100% `.text`: **+56,363 strings → 128,216
lit (64% of census)**. Labelled ESTIMATE, and it assumes the dark half has the same
reference density as the decrypted half — untested, because those pages are zeros.

---

## 4. ★ The `.pdata` is recovered — 382,282 exact function bounds

`docs/ignorance-map-s101.md` B5 claimed the missing unwind table survives in minidump
stream 13. **Verified.** `tools/strxref/mdpdata.py` parses it; `pdataunion.py` unions it.

### 4.1 Verification

`%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` — **85** dirs (not 86), of which **70** carry a
usable table; 10 have a truncated stream 13 and 5 are not valid minidumps.

Stream 13 header: `SizeOfHeader=24 SizeOfDescriptor=32 SizeOfNativeDescriptor=136
SizeOfFunctionEntry=12 NumberOfDescriptors=10`. Descriptor **[1]** is the game exe:
`base=0x7FF6E7D30000, 524,439 entries, RVA 0x8A00 … 0x7649F39` — the entire `.text`
(`0x1000 … 0x764A000`). **All 70 tables report exactly 524,439 entries.**

Structural checks on one table: **0** entries outside `.text`, **0** with `End ≤ Begin`,
**0** out-of-order or overlapping. Entry first-bytes are textbook MSVC x64 prologues
(`48 89 5C 24` 26.9%, `48 83 EC 28` 14.8%, `40 53 48 83` 8.2%).

**Ground truth: 13 of 13** function addresses recorded across ~101 sessions of live RE are
**EXACT entries**, with sizes:

```
0x12F4230 FPrimaryAssetId::ToString      86 B      0x57C8130 battlepass OnSuccess        9 B
0x13454A0 ProcessInternal               241 B      0x57CA670 seasonal VM builder        71 B
0x536A5A0 BP-func-library registrar     158 B      0x57DF4B0 tier populate           1,869 B
0x55DB370 ULokiGameFeatureToggles::Get   51 B      0x585A570 progression ingester      45 B
0x5794480 CheckAccountPassChanges        83 B      0x587BE90 UPartyModel::SetParty    129 B
0x57AB180 FindVM                        416 B      0x751EFD0 entry point               18 B
0x57BB560 VM builder Init               406 B
```

The 14th, `0x587C699` (`OnPersonalizationLoadoutChanged`), is a documented *interior* call
site and is correctly reported as `inside 0x587BF30..0x587C880 (+1897)`.

### 4.2 The table is materialised LAZILY — which is why it can be unioned

Two crash tables with identical entry counts nevertheless differ: **27,939 differing
`BeginAddress`, 29,627 differing `EndAddress`, 0 differing `UnwindInfoAddress`.** Cause,
measured:

- **34.5% of slots (181,109) have `End == Begin + 1`** — placeholders.
- Placeholders lie on a decrypted page only **12.9%** of the time; real (`size > 1`) entries
  do **93.7%** of the time.
- The placeholder count varies **155,497 … 181,109** across dumps, and real-entry byte
  coverage varies **59.2 … 65.2 MB**.
- **0 of 50,000 sampled placeholders falls inside a real entry.**

⇒ The packer fills the table in step with demand-decrypt. Each crash's table is a snapshot
of *that process's* execution coverage — so real entries from different processes union
exactly like `.text` pages do.

**Falsified before it was written down:** the tempting next claim, "a placeholder `Begin` is
still a real function start, so we know all 524,439 starts", is **false** — only **3.0%**
(8,638 of 283,581) of placeholder begins were ever confirmed as a real entry, and the 70
tables contain **657,225** distinct begin values against a 524,439-slot array, so the array
size is not the function inventory. Only `size > 1` entries are trusted.

### 4.3 The union

```
70 tables -> 382,282 distinct real functions, 0 overlapping
  bytes covered                          67,849,419  (54.7% of .text VSize)
  best single table                      369,193     union gain +13,089 (+3.5%)
  present in all 70 tables               241,643
  present in exactly one                 1,460       <- state-specific code
  entry page decrypted in merged.dump    342,446
  entry page NEVER decrypted anywhere    39,836      <- named, sized, bytes unavailable
  function size: median 76 B, p90 359 B, max 143,329 B
```

Outputs: `tools/strxref/index/pdata_union.csv` and `pdata_union.bin` (4,587,384 B,
Ghidra/IDA-importable RUNTIME_FUNCTION array).

⚠ `tools/strxref/index/` is **git-ignored**. The table regenerates in seconds
(`python pdataunion.py`) **as long as the crash minidumps still exist** — 2.0 GB under
`%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` that nothing in this project has ever depended on
and that a cleanup would delete. If those go, so does the table. Either keep the Crashes
directory, or copy `pdata_union.bin` (4.5 MB) somewhere tracked.

### 4.4 What it corrects, immediately

`strxref.py`'s heuristic attribution, scored against the recovered table instead of the
42-address sample (recall measured only on functions whose entry page is decrypted, so this
measures the *algorithm*, not coverage):

| | measured |
|---|---|
| README claim (36-entry ground truth) | 97.2% self-attribution |
| **recall, MED+ candidates, 342,446 real visible functions** | **56.4%** |
| recall on functions ≥ 64 B | 56.7% |
| MED+ candidates that are not any known function start | 20.0% |
| `func_of` resolves to the true entry | **56.8%** (6,000 random functions) |
| reported extent / true size | median 1.05×, p75 1.28×, **p90 7.68×, p99 64×** |
| extents overstated by > 2× | **21.0%** |

The 97.2% figure was not wrong, it was **unrepresentative**: 101 sessions of live RE
naturally recorded large, heavily-called, vtable-referenced functions — exactly the ones the
heuristic finds. On the real population it is a coin flip, and one function in five gets
another function's strings attributed to it. *This is the same failure mode as FK-3/FK-4:
a sound measurement on an unrepresentative sample, recorded as a general fact.*

**95.9%** of the 151,366 string-reference sites fall inside a known function's true bounds,
across **60,941 distinct functions**.

### 4.5 Wired in

`strxref.py` now loads `index/pdata_union.csv` when present:

```
python strxref.py pdata              # status
python strxref.py func 0x536BF8E     # EXACT bounds
python strxref.py func 0x… --heuristic   # old inferred bounds, for comparison
```

`func` and `xref` report `[.pdata EXACT]` and flag when the heuristic disagreed. Absent the
CSV everything falls back to the old behaviour, so the tool still stands alone.
`strxref.py validate` still passes: **21 checks, 0 failed.**

---

## 5. Ranking runtime states — measured, using the crash tables as coverage probes

A crash table's real entries mark code the packer had decrypted **in that process**. Convert
each to the 4 KiB pages it spans and compare against our image dumps. The crashes come from
the DS / tutorial / deploy sessions of the last weeks — states we have **never** taken an
image dump from.

```
merged.dump.exe decrypted .text pages     15,833   52.29%
union of all 9 IMAGE dumps                16,435   54.27%

best crash-era process (EE95146A…)        18,911   62.45%    +3,430 pages vs merged
next 11 crash processes                ~18,8xx   ~62.2-62.4%  +3,26x..+3,43x
worst crash process (61C55551…)           12,176   40.21%    +1,848

UNION of all 70 crash tables              19,495   64.38%    +3,862 pages (+15.1 MB)
GRAND union (images + crash tables)       19,715   65.11%
still never seen by anything              10,566   34.89%
```

**A single image dump taken from the state those crashes represent would add ~3,430 pages
(+13.4 MB, +10.2 pp) — 5.7× the entire gain from re-merging all nine existing image dumps.**
This is a measurement of real processes, not a model.

Expected new lit strings from +3,430 pages: **~2,900 (lower bound, §3.3 rate) to ~13,400
(realistic for disjoint subsystems)**.

Ranking, most to least valuable:

| # | state | why | expected `.text` gain | evidence |
|---|---|---|---|---|
| 1 | **in a live match / drop-in world** | gameplay, combat, GAS, CMC, Chaos, replication never run at menu; these are exactly the dark families in §2.1 | ≥ +3,400 pages, plausibly more | crash tables reach 62.45%; the crash processes were *in* that flow |
| 2 | **DS stub connected + travelled (S70/S89 state)** | netcode/replication/beacon paths; where the current blockers live | large fraction of #1 | 12 crash tables cluster at 62.2–62.5%, all from that workflow |
| 3 | **tutorial force-open, post hero-spawn** | animation, skeletal mesh, camera, quest/objective code | moderate | `toggles` alone (a probe-era menu) was worth +539 pages |
| 4 | **first launch → login → menu (fresh process)** | re-captures startup/init that a long session has moved past | small (monotonic, already covered) | entry-point page decrypted in all 10 dumps |
| 5 | another menu-surface dump (store / roster / missions / passes) | **worth ~0** | **+0 pages, measured** | greedy merge: all five gave +0 after the first |

**Do not spend another capture on a menu surface.** That is measured, not opinion.

---

## 6. Capture plan

### 6.1 Prerequisite (do this first — it is what makes the rest work)

Patch `tools/usmapdump/mergedumps.go:154` to allow a different-`ImageBase` input to
contribute `.text` (base-invariant: 0 relocations, 15,215/15,215 pages byte-identical) while
still skipping its `.rdata`/`.data` (1,403,750 relocations live there). Then remove the
"capture all states WITHOUT relaunching" constraint from `configs/capture-dumps.ps1`.

Without this, every capture from a new launch is discarded and the plan below caps out at
one session.

### 6.2 Immediate, free, no game needed

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python pdataunion.py                  # 382,282 exact bounds -> index/pdata_union.{csv,bin}
python strxref.py pdata               # confirm
```

Then re-merge what is already on disk (+602 pages, +1.98 pp):

```powershell
cd "G:\git\Supervive Revival Project"
.\tools\usmapdump\usmapdump.exe mergedumps dumps\merged2.dump.exe dumps
# with the §6.1 patch this also folds in dumps\rcb (different base)
cd tools\strxref
python strxref.py --rebuild --dump "G:\git\Supervive Revival Project\dumps\merged2.dump.exe"
```

*(Write to `merged2.dump.exe` first and compare — never overwrite the artifact the current
index was validated against.)*

### 6.3 The capture that actually matters

Requires an elevated PowerShell, Steam running, and the game reaching the target state.

```powershell
# terminal 1 — elevated
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1

# terminal 2 — SAME elevated session, once the state is reached
.\configs\capture-dumps.ps1 -State match           # or -State dropin / -State ds-joined
.\configs\capture-dumps.ps1 -State tutorial-hero   # a second state, same launch, is free
.\configs\capture-dumps.ps1 -Finalize              # mergedumps + deobfimports (game must still be running)
```

Order, with the reason each is on the list:

1. **`-State ds-joined`** — DS stub connected, client travelled into the world (S70/S89 is
   already reproducible). Highest ratio of new code to effort.
2. **`-State dropin`** — the "DROP IN GEAR UP LOADING" state from S89/S90. Loads the full
   drop-in world (`LokiPlayerController` + ~60 components, `Comp_GameMode_DropPlane_Tutorial`),
   so the drop/deploy family (25.8% lit) and much of replication should decrypt.
3. **`-State tutorial-hero`** — S93 force-open with the hero spawned/possessed/visible.
   Animation and skeletal-mesh paths.
4. **`-State match`** — if a real match ever becomes reachable, this supersedes all of the
   above.

Then rebuild the index and re-run the dark-subsystem table:

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py --rebuild
python subsystems.py        # the §2.1 table -- watch CMC / replication / GAS move
python yield.py             # measured marginal yield of the new pages
```

### 6.4 Free bonus: every crash is a coverage sample

Each crash writes a fresh stream-13 table. **After any session that crashes, re-run
`python pdataunion.py`** — it is a few seconds and monotonically improves the bounds. The
`.text` pages a crash reveals also tell you which *states* are worth an image dump
(`python statecov.py`).

---

## 7. `.pdata` sanity check — resolved

| claim | verdict |
|---|---|
| live `.text`-adjacent `.pdata` is 100% zero (1,534/1,534 pages) | **TRUE** — confirmed |
| on-disk `.pdata` is packer-encrypted | **TRUE** — confirmed by prior work |
| the real table survives in minidump stream 13, 524,439 `RUNTIME_FUNCTION`s | **TRUE — verified, extracted, 70 independent confirmations** |
| "86 crash minidumps" | **85 dirs**; 70 usable, 10 truncated, 5 invalid |
| "yields exact function bounds for the whole image" | **PARTLY.** Exact for **382,282** functions (54.7% of `.text` bytes). The rest were never decrypted in any of the 70 processes, so their entries are placeholders. More crashes → more bounds. |

Extractor: `tools/strxref/mdpdata.py` (`info` / `verify` / `export` / `csv` / `survey`) and
`tools/strxref/pdataunion.py`. Pure stdlib, offline, read-only.

---

## 8. What remains blocked, and why

1. **34.89% of `.text` (10,566 pages, 41 MB) has never been decrypted by any process we have
   a record of** — no image dump, no crash table. Only running that code lifts it. Nothing
   offline can.
2. **The 39,836 functions we now have exact bounds for but no bytes for.** Named and sized,
   unreadable. Minidumps do not carry `.text` (their `MemoryList` is ~60 KB). An image dump
   from a matching state is the only way to get the bytes.
3. **RTTI is stripped** (0 `.?AV`/`.?AU` descriptors) — vtables give shape and slot targets,
   never class names. Unchanged.
4. **`.data` in `merged.dump.exe` mixes runtime state** across dumps taken minutes apart.
   `.text`/`.rdata` are read-only and exact; treat `.data` findings as provisional.
5. **One level of indirection only.** UE reflection names sit in static structs reached by
   struct *base*; `tools/re/offline_xref.py ptr` remains the complement.
6. **A `.pdata` gap is not proof of absence** — it means "never decrypted in these 70
   processes", exactly like a zero-xref string.

---

## 9. Files

| path | what |
|---|---|
| `tools/strxref/strxref.py` | now loads the recovered `.pdata`; new `pdata` subcommand; `func --heuristic` |
| `tools/strxref/mdpdata.py` | minidump stream-13 parser / verifier / exporter |
| `tools/strxref/pdataunion.py` | unions 70 crash tables → `index/pdata_union.{csv,bin}` |
| `tools/strxref/pdatadiff.py` | proves the table is lazily materialised |
| `tools/strxref/pdatascore.py` | scores heuristic attribution against the real table |
| `tools/strxref/dumpcov.py` | page-coverage auditor; `reloc` and `cmptext` modes |
| `tools/strxref/dumpcov2.py` | union / novelty / greedy-merge analysis over the 9 dumps |
| `tools/strxref/yield.py` | measured marginal yield + rarefaction extrapolation |
| `tools/strxref/subsystems.py` | lit/dark rate per subsystem (§2.1) |
| `tools/strxref/statecov.py` | crash tables as runtime-state coverage probes (§5) |
| `tools/strxref/pagecheck.py` | per-RVA page-decryption probe across all dumps |
| `tools/strxref/index/pdata_union.csv` | **382,282 exact function bounds** |
| `tools/strxref/index/pdata_union.bin` | same, as a RUNTIME_FUNCTION array for Ghidra/IDA |

---

## 10. Corrections to the record

| # | claim | status |
|---|---|---|
| FK-3 | `.rdata` union capped at 63.12%, structural, 13.9 MB unreadable | **FALSE** (prior work) — `.rdata` is 99.64% readable by page |
| FK-4 | packer decrypts `.rdata` strings to the heap, LEA→string xref defeated | **FALSE** (prior work) — the scans were ASCII-only and/or against the packed on-disk exe |
| new | `merged.dump.exe` is not really a merge / the merge is broken | **FALSE** — it merged correctly; four of five inputs were the same menu state, 4 minutes apart |
| **new** | `mergedumps` must reject different-`ImageBase` dumps because `.text` is relocated | **FALSE** — 0 relocations in `.text`; 15,215/15,215 shared pages byte-identical across bases. Costs us every cross-session capture. |
| **new** | `strxref` function attribution is 97.2% accurate | **UNREPRESENTATIVE** — 56.4% recall / 56.8% correct on 342,446 real functions; 21% of extents overstated >2×. Superseded by the recovered table. |
| new | the binary domain knows 617 of ~120,000 functions (0.5%) | **denominator ~3× too small** — ≥382,282 functions verified; 617/382,282 = **0.16%** |
| new | the packer re-encrypts cold pages, so dump timing matters | **FALSE** — measured and rejected; the entry-point page is decrypted in all 10 images and coverage is monotonic within a session |
| new | a placeholder `Begin` in the crash table is still a real function start | **FALSE** — only 3.0% confirmed. Measured *before* being written down. |
