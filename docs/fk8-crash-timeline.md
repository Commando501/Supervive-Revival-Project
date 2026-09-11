# FK-8 · Dimension 3 — PROVENANCE AND TIMELINE

**Date:** 2026-08-05 · **Scope:** 100 % offline. Nothing was launched, injected or started.
Nothing under `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` was written — this pass reads
`docs/fk8-crash-corpus.csv`, plus a handful of hand re-reads of individual crash directories
opened `rb` / read-only.

**Inputs**
* `docs/fk8-crash-corpus.csv` (139 rows: 92 UECC + 47 crashpad `.dmp`), built this session by
  `tools/crashtri/fk8_corpus.py`.
* `git log --all` / `git reflog` in `G:\git\Supervive Revival Project`.

**Tool (re-runnable):** `tools/crashtri/fk8_timeline.py`
**Joined per-crash output:** `docs/fk8-crash-timeline.csv` (one row per corpus row, with
`head_sha`, `head_committed`, `head_age_hours`, `shim_vintage`, `tutorial_launch_vintage`,
`server_vintage`, `time_source`).

Every claim is tagged **MEASURED** or **INFERRED**. Every negative names the artifact class it is
scoped to.

---

## ★ HEADLINE

**MEASURED — the FK-7 "deterministic T+173–201 s tutorial death" is a property of ONE build era,
2026-07-24…26, and it has not been observed since.** Splitting the 31 tutorial-route deaths by build
era gives three *non-overlapping* `SecondsSinceStart` distributions:

| era | shim-source vintages spanned | n | median | in **173–201 s** | in **255–340 s** | values |
|---|---|---:|---:|---:|---:|---|
| **A** 2026-07-09…12 | `473b3f9` `a91a61c` `fb04117` `0bde7ea` | 7 | 259 | **1/7** | 1/7 | 60, 84, 184, 259, 659, 677, 3334 |
| **B** 2026-07-24…26 | `cbfb752` `ee17f37` `a8d23f2` | 10 | 194 | **10/10** | 0/10 | 173, 175, 185, 194, 194, 194, 195, 195, 196, 201 |
| **C** 2026-08-03…05 | `6e8a7df` `9eddbcd` `7ef26c0` `b012c32` `1f5778b` `969acef` | 14 | 292.5 | **0/14** | **8/14** | 160, 258, 259, 263, 267, 283, 290, 295, 336, 432, 491, 524, 572, 2550 |

Era B is 10 for 10 inside the historic FK-7 window and 0 for 10 outside it. Era C is 0 for 14 inside
it. **Zero of the 14 tutorial deaths recorded since the S108 fixes landed sit in the window the whole
FK-7 investigation is about.**

⚠ **A confound is present and I could not resolve it from the corpus.** `configs/fk24-stage.ps1` —
which moves clock-zero by arming the probe ~T+145–175 s instead of at launch — was **added
2026-08-04 14:20:48** (`ed252c4`), i.e. *inside* era C. S108 §6 already flagged exactly this
("`SecondsSinceStart` and time-since-body-build nearly coincide" only when the shim is injected at
launch). So the shift is **at least partly a clock-zero artifact and must not be read as "the crash
moved."** What survives the confound: the **two era-C deaths that predate the staging tool**
(`166396E2` 2026-08-03 22:49, T+2550 s; `FED1F952` 2026-08-04 01:57, T+572 s) are also outside
173–201 s. n=2 — suggestive, not decisive.

---

## Method — and why it is stronger than "latest commit before the crash"

**MEASURED.** HEAD-at-crash-time comes from **`git reflog`**, not from commit ordering. The reflog in
this repo holds **413 entries covering all 408 commits + 4 checkouts + 1 merge, back to the initial
commit `d172bae` (2026-06-25 22:42:53)** — nothing has expired. That matters because HEAD really did
move between branches inside the crash window:

```
2026-06-28 01:31  checkout main -> claude/assetregistry-primary-assets-w7pljz
2026-06-29 14:30  checkout claude/... -> main
2026-06-29 14:32  checkout main -> claude/...  (and back, 14:32:54)
2026-06-29 14:59  checkout main -> dedicated-server-stub     <- and it stayed there
2026-07-10 21:05  merge origin/main into dedicated-server-stub ('ours')
```

A naive "last commit whose date ≤ t on the current branch" would have mis-assigned every crash on
2026-06-28 and 2026-06-29 — 9 real deaths — to commits that were not checked out at the time.

**Three limits on the attribution, stated up front:**

1. **INFERRED, not MEASURED — commit time is an UPPER bound on when code ran, not the time it ran.**
   Runs happen, then the evidence and the source change get committed. Measured lag for the six runs
   whose evidence files are git-tracked (found via `git log -S<label> -- docs`):

   | run label | crash (local) | evidence committed in | lag |
   |---|---|---|---:|
   | `animref-SUCCESS` | 2026-08-05 18:19:43 | `a827ef9` 18:23:30 | **3 m 47 s** |
   | `sub-NoMissions-1` | 2026-08-04 23:03:16 | `faee0a8` 23:19:31 | 16 m |
   | `knee-g30-2` | 2026-08-05 01:09:17 | `69fc275` 01:18:29 | 9 m |
   | `tut1` / `tut4` / `tut3-NOSTAGE` | 2026-08-05 01:45–02:06 | `86ae8f4` 02:09:27 | 3–24 m |
   | `s110itemwatch` | 2026-08-05 14:28:09 | `fde4915` 17:21:59 | **2 h 54 m** |

   So `shim_vintage` in the CSV means **"at least this new"** — read it as a lower bound.

2. **INFERRED — the DLL that was injected is not guaranteed to match the committed source.**
   `tools/sigbypass-mod/build/` is **git-ignored** (`tools/sigbypass-mod/.gitignore:12`), so no built
   artifact is in history. **MEASURED right now: 19 of the 20 `tutorial_launch_*.dll` on disk have an
   mtime older than the current `tutorial_launch.cpp` commit** (`a827ef9`, 2026-08-05 18:23:30).
   This is **ignorance-map gap F3** (`docs/ignorance-map-s101.md:1063`) measured live: *"none stamps a
   source SHA or build time into its marker … 23 of 25 `tutorial_launch_*.dll` on disk predate their
   own source."* The ratio has moved (19/20 today) but the gap is unchanged.

3. **MEASURED — the corpus and the repo are both LIVE.** The repo gained 1 commit (407 → 408) while
   this pass was being written. Re-run `fk8_timeline.py`; do not cite a stored count, including the
   ones on this page.

---

## A. THE TIMELINE

### A.0 Denominators (carried from the corpus, re-verified here)

| class | n | what it is |
|---|---:|---|
| **UECC real deaths** | **84** | 92 directories − 8 `kind=degenerate` |
| **crashpad real deaths** | **22** | 47 `.dmp` files → 22 distinct report uuids (`report_is_primary==1`) |
| **TOTAL real deaths** | **106** | the two sources are disjoint: 0 of 22 crashpad Crash-GUIDs has a UECC directory |
| excluded: degenerate | 8 | truncated `CrashContext` writer — real deaths, unusable records (see §D) |
| excluded: duplicate crashpad copies | 25 | the archiver snapshots the DB before *and* after each launch |

**MEASURED — 1 of the 106 deaths predates the git repository entirely.**
`UECC-Windows-F86B2A5B…` fired at **2026-06-25 22:42:06.779**, **47 seconds before** the initial
commit `d172bae` (22:42:53). Its `head_sha` is empty and that is correct, not a join failure.

### A.1 Deaths per local day, against commits made that day

`degen` are counted separately (their timestamp is an mtime, not a `TimeOfCrash`).
`HEAD@EOD` = the commit that was checked out at 23:59:59 local that day.

| day | uecc | cpad | degen | **DEATHS** | commits | HEAD@EOD | subject |
|---|---:|---:|---:|---:|---:|---|---|
| 2026-06-25 | 1 | 0 | 0 | **1** | 3 | `a48396f` | Update TLS certificates, enhance API endpoints |
| 2026-06-26 | 1 | 0 | 1 | **1** | 4 | `01f35dd` | Update TLS certificates, enhance command-line tools |
| 2026-06-27 | 3 | 0 | 0 | **3** | 3 | `52d40b0` | Native shim toolkit: read-only RE primitives + manual-map |
| 2026-06-28 | 3 | 0 | 0 | **3** | 43 | `f32b990` | Route 2: scan virtual slot 131 found |
| 2026-06-29 | 6 | 0 | 1 | **6** | 59 | `62128de` | Update certificates, marker, and server logs |
| 2026-06-30 | 11 | 0 | 0 | **11** | 17 | `130a82e` | Session 22 close: SUPERVIVE engine mods CONFIRMED |
| 2026-07-01 | 8 | 0 | 0 | **8** | 35 | `761005c` | Update UStruct schema; modify LokiNetDriver |
| 2026-07-02 | 1 | 0 | 0 | **1** | 21 | `e84aaca` | Session 43: scan_on_browse payload |
| 2026-07-03 | 1 | 0 | 0 | **1** | 27 | `37b1ab0` | Session 47: SOLVED — ALL HUNTERS roster renders |
| 2026-07-04 | 0 | 0 | 0 | 0 | 19 | `906b594` | tools: resolve_delegate.py |
| 2026-07-05 | 0 | 0 | 0 | 0 | 12 | `c1eaf88` | store: BUNDLES + SKINS render |
| 2026-07-06 | 0 | 0 | 0 | 0 | 10 | `d7f04df` | Session 53: DS menu-load crash SOLVED |
| 2026-07-07 | 2 | 0 | 0 | **2** | 10 | `ded62e2` | Session 54: add Session-55 handoff prompt |
| 2026-07-08 | 1 | 0 | 1 | **1** | 13 | `77ae61d` | S59: docs — wiring real match progress |
| 2026-07-09 | 3 | 0 | 1 | **3** | 1 | `ccdb847` | S59: update documentation and functionality |
| **2026-07-10** | **12** | 0 | 3 | **12** | 3 | `b1731ed` | Merge origin/main into dedicated-server-stub |
| 2026-07-11 | 9 | 0 | 0 | **9** | 1 | `a91a61c` | Update certificates and enhance documentation |
| 2026-07-12 | 3 | 0 | 0 | **3** | 7 | `19db6a2` | S74 Route B: Angelscript inventory |
| 2026-07-14…16 | 0 | 0 | 0 | 0 | 50 | — | (three days, 50 commits, zero deaths) |
| 2026-07-17 | 1 | 0 | 0 | **1** | 10 | `3d872e1` | usmapdump: deobfimports |
| 2026-07-19 | 3 | 0 | 0 | **3** | 2 | `cbfb752` | Update certificates and logs |
| 2026-07-21 | 0 | 0 | 0 | 0 | 1 | `928cad7` | S85: AVATAR/CALLSIGN customization online |
| 2026-07-22 | 0 | 0 | 0 | 0 | 2 | `97606c2` | docs: S87 next-session handoff prompt |
| 2026-07-24 | 1 | 0 | 0 | **1** | 4 | `2c09557` | S97: decisive render test |
| 2026-07-26 | 9 | 0 | 0 | **9** | 9 | `6e8a7df` | S103: spawn + populate + HeroAffiliated carrier |
| 2026-08-03 | 1 | 0 | 0 | **1** | 7 | `87c1e97` | docs: S108 handoff |
| **2026-08-04** | 3 | 8 | 1 | **11** | 18 | `faee0a8` | docs: S109 — subtractive sweep |
| **2026-08-05** | 1 | 14 | 0 | **15** | 17 | `08d43b8` | gas: RETRACT the provenance in FK-30 |

**MEASURED — deaths are concentrated in 22 of the 42 calendar days, and the three biggest days
(07-10: 12, 08-05: 15, 06-30: 11) are 36 % of the whole corpus.** There is **no correlation between
commit volume and deaths**: 2026-07-16 has 34 commits and 0 deaths; 2026-07-11 has 1 commit and 9
deaths. Commits measure *writing*, deaths measure *launching* — this is expected and is stated only
so nobody reads the commit column as exposure.

### A.2 Deaths per HEAD commit

**MEASURED — 106 deaths spread across 51 distinct HEAD commits (+1 pre-repo).** Median 1 death per
commit-neighbourhood. The concentrated neighbourhoods:

| head | committed | n | routes | subject |
|---|---|---:|---|---|
| `b1731ed` | 2026-07-10 21:05 | **15** | tutorial-attempted 13, menu-lobby 1, tutorial 1 | Merge origin/main into dedicated-server-stub |
| `ee17f37` | 2026-07-26 01:14 | **5** | tutorial 5 | S99: weapon question settled; idle-animation fix built |
| `7b9a5a5` | 2026-08-04 22:44 | **5** | menu-login 3, unknown 1, menu-lobby 1 | S109 — pi8 alone: 6 runs, 0 deaths |
| `77ae61d` | 2026-07-08 20:02 | 4 | tutorial-attempted 3, unknown 1 | S59 docs |
| `a91a61c` | 2026-07-11 14:46 | 4 | tutorial 3, tutorial-attempted 1 | Update certificates + injection docs |
| `130a82e`, `393e864` | 2026-06-30 | 3, 3 | menu-login | Session 18 / 22 close |
| `da84b63`, `af8f54b`, `e6ad28e`, `1f5778b`, `bc305bd` | — | 3 each | mixed | S109/S110 work |
| 43 further commits | — | 1–2 each | | |

`b1731ed` (the merge) is the single largest bucket and it is an artifact of the *reflog*, not of the
merge: HEAD sat on that commit for 17 h 41 m (2026-07-10 21:05 → 2026-07-11 14:46) across the two
heaviest tutorial-attempt sittings. **`head_age_hours` is in the CSV precisely so this can be seen.**

### A.3 Deaths per shim-source vintage (`tools/sigbypass-mod`)

This is the axis that actually matters for "what code produced this crash".

| vintage | committed | deaths | subject |
|---|---|---:|---|
| (pre) | — | 5 | before any shim source existed |
| `ce2898d` | 2026-06-28 17:31 | 2 | Option-1 shim: mount_shim.cpp |
| `4a9a98b` | 2026-06-28 21:31 | 1 | registration_shim |
| `cf72ebb` | 2026-06-29 19:08 | 6 | browse_hook v10 |
| **`2467513`** | 2026-06-30 00:01 | **20** | Session 9 close: client UDP reaches stub server |
| `c43f07c` | 2026-07-03 19:46 | 1 | Session 46 fix attempt #1 |
| `d7f04df` | 2026-07-06 23:41 | 2 | Session 53: DS menu-load crash SOLVED |
| `929d0d3` | 2026-07-08 19:31 | 4 | S59: harden missions_fix load-wait |
| `ccdb847` | 2026-07-09 03:22 | 2 | S59 front-end (**adds `tutorial_launch.cpp`**) |
| **`473b3f9`** | 2026-07-10 20:44 | **15** | S61: missions + secondary shim injection |
| `a91a61c` | 2026-07-11 14:46 | 4 | injection docs |
| `fb04117` / `0bde7ea` | 2026-07-12 | 2 / 1 | S74 B2 |
| `a8c3b74` | 2026-07-17 03:10 | 1 | Widget census + 48-slot CAP |
| `bc305bd` | 2026-07-19 02:13 | 3 | S83-84 PASSES |
| `cbfb752` | 2026-07-19 21:48 | 1 | certificates and logs |
| `ee17f37` | 2026-07-26 01:14 | 5 | S99 idle-animation fix |
| `a8d23f2` | 2026-07-26 02:27 | 4 | S99b idle animation VERIFIED |
| `6e8a7df` | 2026-07-26 15:25 | 1 | S103 HeroAffiliated carrier |
| `9eddbcd` | 2026-08-03 22:59 | 2 | **FK-7 crash fixes + FK-24 watchpoint probe + build system** |
| `7ef26c0` | 2026-08-04 14:20 | 3 | KSTATICTEST off by default |
| **`b012c32`** | 2026-08-04 19:39 | **14** | noop-canary: manual-mapping exonerated |
| `1f5778b` | 2026-08-05 02:36 | 3 | anim: moving the walk inside the asset's lifetime |
| `969acef` | 2026-08-05 03:08 | 4 | gc: fix the root-bit corroboration |
| **`a827ef9`** | 2026-08-05 18:23 | **0** | **anim: FIXED — KANIMREF** ← *see §C for the correction* |
| **`2690822`** | 2026-08-05 18:28 | **0** | build: delete play-earlywalk ← **current** |

**MEASURED — 24 distinct shim-source vintages produced the 106 deaths. Only 3 vintages account for
49 of them (46 %).**

---

## B. ROUTE LABELS

Derived by `fk8_corpus.py` from each crash's own `Loki.log`: `Load map complete …LVL_Tutorial` →
`tutorial`; the force-open URL `?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial` without a
completed tutorial map load → `tutorial-attempted`; last map `LVL_Login` / `LVL_LobbyV2_Persistent` →
`menu-login` / `menu-lobby`; a log too short to name any map → `unknown`.

### B.1 The split

| route | all real (106) | UECC (84) | crashpad (22) |
|---|---:|---:|---:|
| **tutorial** (world loaded) | **31** | 20 | 11 |
| **tutorial-attempted** (force-open issued, world never completed) | **20** | 18 | 2 |
| **menu-login** | **31** | 25 | 6 |
| **menu-lobby** | **16** | 14 | 2 |
| **unknown** (log too short to name a map) | **8** | 7 | 1 |

**Menu-route (no world load) = 47 + 8 unknown; tutorial-route (world actually loaded) = 31;
force-open attempted but no world = 20.**

### B.2 The rows with no log — and what that costs

⚠ **The brief's "8 UECC rows lack `Loki.log`" is wrong twice, and both errors are instrument
artifacts.** MEASURED:

* **7** UECC directories contain no log file at all. They are **exactly** the 7 non-`_0000`
  degenerate rows, each holding `{CrashContext.runtime-xml, CrashReportClient.ini, UEMinidump.dmp(0 B)}`.
* An 8th, `UECC-Windows-F86B2A5B…`, carries **`Loki_2.log` (565,566 B)**. Any census with a hard-coded
  `Loki.log` filename drops it. Glob `Loki*.log`.
* `_0000` — which *is* degenerate — **does** carry a `Loki.log`, but only 509 bytes / 7 lines (§D).

**What the 7 cost, scoped precisely:** for those 7 rows there is **no route label, no map history, no
timestamp fingerprint, and no `Load map complete` evidence** — and they are also the 7 rows with a
zero-byte minidump and no `TimeOfCrash`, so their *only* absolute timestamp is a file mtime.
They are **6.6 % of the 106 real deaths** and are excluded from every route table above.
Note what they are **not**: they are not "not crashes" — each has a distinct `ExecutionGuid`, a real
`ErrorMessage`, and 43–62 live thread records (§D).

### B.3 ⚠ Marker tags: the F3 ambiguity, and why route labels do **not** rest on them

**MEASURED — all ten bracketed shim marker tags (`[SP] [PL] [FO] [ANIM] [VTG] [GCW] [GFT]
[KANIMREF] [MISS] [BP]`) appear in 0 of 139 corpus rows' logs (130 logs, 1,119 MB).** The detector's
**positive control fires**: run against `docs/fk24-run-nostatictest1.txt` it returns
`{PL:25, ANIM:12, VTG:1, GCW:1}`.

**The zero is a property of the instrument, not of the runs.** Every shim's `Marker()` writes to
`docs/<shim>-marker.txt` via `CreateFileA` — it never calls `UE_LOG`, so shim output can never reach
`Loki.log`.

**This is ignorance-map gap F3** (`docs/ignorance-map-s101.md:1063`): *"Nothing distinguishes 'the
target ran and did nothing' from 'we never reached the target.'"* Applied here, the absence of a
marker tag in a log means **(a) the shim was not present, (b) the shim was present and never reached
its print, or (c) — and in this corpus it is always (c) — the print never had a path into this
artifact class.** These are not collapsible and I have not collapsed them.

**Consequence, and it is the reason the route axis is usable at all:** route labels are derived from
**UE's own log lines**, not from shim markers. The force-open signature
`?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial` is echoed by the engine's console handler
and fires in **61 of 139 rows** (35/84 real UECC, 25/45 crashpad session logs). That is a MEASURED
proxy for "our force-open ran"; it is **not** a proxy for "which DLL was injected" and must not be
used as one.

### B.4 Route × timing mode

`SecondsSinceStart` buckets, 106 real deaths:

| route | 0 | <60 | 60–119 | 120–199 | 200–299 | 300–599 | ≥600 |
|---|---:|---:|---:|---:|---:|---:|---:|
| menu-login | 1 | **30** | 0 | 0 | 0 | 0 | 0 |
| menu-lobby | 0 | 6 | 2 | 0 | 2 | 0 | **6** |
| tutorial | 0 | 0 | 2 | **11** | 9 | 5 | 4 |
| tutorial-attempted | 0 | 8 | 3 | 1 | 5 | 0 | 3 |
| unknown | **8** | 0 | 0 | 0 | 0 | 0 | 0 |

Three modes are visible and they are **route-specific, MEASURED**:

1. **menu-login is a startup mode.** 30 of 31 die under 60 s. These are the S109 sub-arm experiments
   plus the June login-flow work.
2. **`unknown` is entirely `SecondsSinceStart == 0`** — and all 8 are the chainless protector
   families. MEASURED for the 7 UECC ones (`unwind_status='os-only'`, `PCallStackHash == sha1("")`,
   zero SUPERVIVE frames); the 8th is the crashpad row `3e17e732` (`shimrun2-DEATH`), which S109 §12
   walked and identified as Family A (`rip = 0x7FFD3B400001`). ⚠ Their 0 is **uninformative**:
   S109 §6b measured two members of that family reading 0 while actually being 2.9 s in.
3. **tutorial is the only route with mass above 120 s**, and it is bimodal by era (see the headline).

### B.5 Route × crash type — a clean 1:1

| route | Crash | Assert |
|---|---:|---:|
| menu-lobby | 16 | 0 |
| menu-login | 25 | 6 |
| tutorial | 30 | 1 |
| **tutorial-attempted** | 3 | **17** |
| unknown | 8 | 0 |

**MEASURED — all 17 `Fatal error: … Couldn't spawn player` asserts (`UnrealEngine.cpp:15551`) are on
the `tutorial-attempted` route**, dated 2026-07-09…11, under 3 shim vintages (`929d0d3`, `473b3f9`,
`a91a61c`). The other assert family is `MallocBinned2.cpp:1322` (n=7, 2026-06-29…07-17, menu-login +
one tutorial-attempted). Those two families are the **entire** assert population (17 + 7 = 24).

### B.6 Route × build era

| era | menu-lobby | menu-login | tutorial | tutorial-attempted | unknown |
|---|---:|---:|---:|---:|---:|
| 2026-06-25…07-07 (pre-tutorial) | 12 | 25 | 0 | 0 | 0 |
| 2026-07-08…07-19 | 2 | 0 | 7 | 18 | 5 |
| 2026-07-21…07-26 | 0 | 0 | 10 | 0 | 0 |
| 2026-08-03…08-05 | 2 | 6 | 14 | 2 | 3 |

**MEASURED — the route mix turns over completely twice.** The corpus is *not* one population sampled
over six weeks; it is four different experiments. Pooling it is the denominator error the project has
already been burned by twice.

---

## C. THE SHIM-VINTAGE QUESTION

### C.1 Verifying the prior claim

`docs/fk7-crash-settled.md` §0.2a: *"the four camera dumps come from three build vintages, none of
them the candidate's."* **Independently re-derived here from the reflog + `git log -- tools/sigbypass-mod`:
CONFIRMED.**

| dump | sub-family | crash (local) | `secs` | HEAD at crash | shim vintage |
|---|---|---|---:|---|---|
| `B61ED1A7` | `12c7e2d` | 2026-07-24 14:45:34 | 194 | `97606c2` | **`cbfb752`** (07-19 21:48) |
| `AABE886D` | `12c7e2d` | 2026-07-26 01:44:54 | 185 | `ee17f37` | **`ee17f37`** (07-26 01:14) |
| `BE345EC2` | `3c5dc52` | 2026-07-26 04:29:11 | 175 | `2921ac5` | **`a8d23f2`** (07-26 02:27) |
| `7E6FDF97` | `3c5dc52` | 2026-07-26 04:39:24 | 173 | `2921ac5` | **`a8d23f2`** (07-26 02:27) |

3 distinct shim vintages, 3 distinct HEADs, **none of them current**. The `12c7e2d` / `3c5dc52` split
does fall on the `a8d23f2` boundary exactly as claimed.

**One refinement the prior doc does not make:** the two `12c7e2d` dumps are themselves **a week and
four shim commits apart** (`cbfb752` 07-19 vs `ee17f37` 07-26). The "before `a8d23f2`" cohort is not
one build either, so *"the split correlates perfectly with build vintage"* is true but weak — many
boundaries would separate 07-24/07-26-01:44 from 07-26-04:29.

### C.2 Vintage span of every major cluster

| cluster | n | distinct HEADs | distinct **shim vintages** | date span | any from the current vintage? |
|---|---:|---:|---:|---|---|
| ALL real deaths | 106 | 51 | **24** | 06-25 → 08-05 | see C.3 |
| route=tutorial | 31 | 17 | **12** | 07-11 → 08-05 | see C.3 |
| route=tutorial-attempted | 20 | 6 | **6** | 07-09 → 08-05 | no |
| route=menu-login | 31 | 21 | **4** | 06-29 → 08-05 | no |
| route=menu-lobby | 16 | 14 | **10** | 06-25 → 08-04 | no |
| assert `Couldn't spawn player` | 17 | 3 | **3** | 07-09 → 07-11 | no |
| assert `MallocBinned2` | 7 | 5 | **2** | 06-29 → 07-17 | no |
| chainless protector (`unwind=os-only`) | 7 | 5 | **5** | 07-08 → 08-04 | no |
| crashpad class | 22 | 11 | **5** | 08-04 → 08-05 | no |
| FK-7 camera dumps | 4 | 3 | **3** | 07-24 → 07-26 | **no** |
| `pcallstack` cluster `D5ABA8A5…` (largest, n=17) | 17 | 3 | **3** | 07-09 → 07-11 | no |
| `pcallstack` cluster `50A9FDF3…` (n=7) | 7 | 6 | **3** | 06-25 → 07-19 | no |
| `pcallstack` cluster `B3106F52…` (n=5) | 5 | 3 | **1** | 06-29 (one day) | no |

**MEASURED — the biggest clusters are mostly 1–3 vintages wide but *far* apart in time.** The n=7
`50A9FDF3` menu-lobby cluster spans **25 days and 3 vintages**; the n=17 assert cluster is tight
(3 days, 3 vintages). Nothing in this table is one build.

### C.3 Is *any* evidence about today's code?

**Answered two ways, because the naive answer is misleading.**

**Naive (what `shim_vintage` says): 0 of 106.** The current shim vintage `2690822` (2026-08-05 18:28)
and its predecessor `a827ef9` (18:23) have **zero** deaths under them by the `last commit ≤ crash
time` rule.

**Corrected (INFERRED, and this is the one to use): exactly 1 of 106.** The most recent death —
crashpad report `2432183f…`, 2026-08-05 **18:19:43**, `LVL_Tutorial`, **T+336 s**, archive label
`animref-SUCCESS` — is the run whose evidence files (`docs/fk24-stage-animref-1..4`,
`docs/s110-itemwatch-animref-20260805-181429.*`, `docs/tutorial-launch-marker.txt`) were committed
**3 m 47 s later, in `a827ef9` — the KANIMREF commit itself**. MEASURED via `git show --stat a827ef9`.
And `2690822`, the only shim commit after it, touches **`build.ps1` only, not `tutorial_launch.cpp`**
(MEASURED, `git show --stat`). So:

> **The current `play` DLL's source has produced exactly ONE crash in this corpus, and it is a
> T+336 s tutorial death that the project currently reads as a SUCCESS run.**

**Everything else — 105 of 106 — was produced by shim source that no longer exists.** In particular:

* **All 4 FK-7 camera dumps** are from `cbfb752` / `ee17f37` / `a8d23f2` — **≥6 shim commits and
  10 days behind current**, and behind `9eddbcd` (2026-08-03), *the commit that contains the FK-7
  fixes those dumps motivated*. The prior doc's "not yet known that the candidate build reproduces
  FK-7 at all" is, on this timeline, **still exactly true** — and the era table in the headline
  says the *era* has not reproduced it in 14 tutorial deaths.
* **The two largest single-vintage clusters** (`2467513` n=20, `473b3f9` n=15) are **36 and 26 days
  old** and both are pre-tutorial menu/DS-era work.
* **The 14 deaths under `b012c32`** (2026-08-04 19:39 → 08-05 02:36) are the S109 subtractive-sweep
  and injection-gap experiments — the newest large cluster, and already 2 shim vintages stale.

⚠ **Scope.** "Produced by shim source that no longer exists" is a statement about
`tools/sigbypass-mod`. **The game binary is constant across the whole corpus** — MEASURED:
`GameName = UE-Loki` in 137/139 (2 empty), and the engine version is one value under two spellings,
`5.4.3-0+UE5` in all 91 non-degenerate UECC rows and `5.4.3-0` in all 45 crashpad rows. Nothing here
says the *game* changed.

⚠ **And a second instrument split worth recording:** `BuildVersion` reads the placeholder `UE5-CL-0`
in 91 UECC rows but the **real** `release2.4.live-156430-shipping` in 43 crashpad rows. Same pattern
as the command line (`CommandLineRemoved` in UECC, the full ~847-char line in crashpad):
**only the crashpad class carries genuine build provenance.** A census over `UECC-*` alone cannot see
the game build at all.

---

## D. THE `_0000` DIRECTORY

**Short answer: it is a real crash record, and simultaneously a corpus artifact — `_0000` is a
COLLISION BUCKET that at least two, probably three, different process deaths have written into.**

### D.1 What is on disk (MEASURED, read-only)

```
C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes\_0000\
  CrashContext.runtime-xml   14,714 B   created 2026-06-28 15:41:08   modified 2026-06-29 18:45:55
  Loki.log                      509 B   created 2026-06-28 15:41:08   modified 2026-06-28 17:37:09
  UEMinidump.dmp                  0 B   created 2026-06-28 15:41:08   modified 2026-06-29 18:45:55
```

**It is structurally unique in the whole tree.** File-set census over all 92 UECC directories:

| n | file set |
|---:|---|
| 73 | xml · ini · Loki.log · dmp |
| 8 | + `Breadcrumbs_RHIThread_0.txt` |
| 7 | xml · **ini** · dmp *(the other 7 degenerates — no log)* |
| 2 | + two RHI breadcrumb files |
| 1 | xml · ini · **Loki_2.log** · dmp |
| **1** | **xml · Loki.log · dmp — `_0000`, and it is the ONLY directory with no `CrashReportClient.ini`** |

### D.2 When — and why "when" has more than one answer

**MEASURED — the three files were CREATED at one instant (2026-06-28 15:41:08) and LAST WRITTEN at
two further, widely separated instants.** On NTFS, `CreationTime` is not updated by rewriting an
existing file, and the tunneling cache that could restore it expires in ~15 s — 27 hours apart it
cannot apply. **So the XML now on disk was written on 2026-06-29 18:45:55 into a file created on
2026-06-28 15:41:08. That is ≥2 distinct events sharing one path.** The `Loki.log`'s third distinct
mtime (2026-06-28 17:37:09) indicates a third, but is weaker evidence — a file copy can carry the
source's mtime.

Neither of those instants coincides with any other crash: the nearest real deaths are
2026-06-28 17:55:25 (18 min after the log write) and 2026-06-29 19:16:09 (30 min after the XML
write). So `_0000` is not a side-effect written during some other crash's report — it is its own
event, repeatedly.

### D.3 What the XML says

```
CrashGUID           _0000                    <- empty; the folder name IS the degenerate GUID
ExecutionGuid       2728BF6448AA96BB5BB607A99217B254   (unique across all 92 — not a duplicate row)
CrashType           Crash    IsEnsure false  IsAssert false
ErrorMessage        Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x00007ff6823657d0
ProcessId           0        SecondsSinceStart 0
PlatformName / EngineVersion / BuildVersion / CommandLine / BaseDir / MachineId / LoginId  ALL EMPTY
Misc.NumberOfCores  0        CPUVendor/CPUBrand/GPUBrand EMPTY
MemoryStats.TotalPhysical 51481124864   TotalVirtual 71839100928   PageSize 4096   <- POPULATED
PCallStack          Unknown 0x0 + 2c5d0641c47  /  KERNEL32 + 17374
PCallStackHash      DA39A3EE5E6B4B0D3255BFEF95601890AFD80709   (= sha1(""))
Threads             18 total, ALL with IsCrashed=false
                    GameThread(32420) · 16× FChunkCacheWorker · FHeartBeatThread
GameThread stack    VCRUNTIME140+128cb, then SUPERVIVE +f83091 +f9adf7 +f8286a +f9b129
                    +4035e87 +403210a +402fec1 +40300da +4030f6c +4039696 +751ef62, KERNEL32
```

And the 509-byte `Loki.log`, in full — 7 lines, **none of them timestamped**, i.e. before `GLog` has
its prefix writer:

```
Initializing PakPlatformFile
Reading toc: ../../../Loki/Content/Paks/global.utoc
Toc signature hash: 6709D97A0C606F95DA1A17081E4BBB2079C25138
Mounting container '.../global.utoc' in location slot 0
Initialized I/O dispatcher file backend. Mounted the global container
Found Pak file .../pakchunk0_s9-WindowsClient.pak attempting to mount.
Mounting pak file .../pakchunk0_s9-WindowsClient.pak.
```

### D.4 Verdict

**Real crash? YES — INFERRED, high confidence.** It has a unique `ExecutionGuid`, a concrete
`EXCEPTION_ACCESS_VIOLATION`, a plausible fault target (`0x7FF6823657D0` = the SUPERVIVE image base
`0x7FF67E4A0000` + **`0x3EC57D0`**, i.e. a read of an address inside the game's own image — the shape
of a demand-decrypt page fault in this protected build), real memory totals, and 18 live thread
records. The crash-reporter did not fabricate that.

**Artifact? ALSO YES, and this is the operationally important half.**
The identity half of `FGenericCrashContext`'s cached session state was never populated —
`ProcessId 0`, `PlatformName`/`EngineVersion`/`CommandLine`/`MachineId` all empty, only 18 threads
(the other degenerates have 43–62) — because the process died during **pak mounting**, before that
initialisation. `CrashGUID` therefore came out empty, the folder name degenerated to `_0000`, **and
that name is not unique**, so every subsequent early-startup death of the same shape lands in the same
folder and overwrites it.

⇒ **Three rules for the census:**
1. `_0000` is **one row representing ≥2 events**. Counting it as one death undercounts; counting
   it as one *sample* mixes runs.
2. Its `Loki.log` and its `CrashContext.runtime-xml` **may not describe the same run** (their mtimes
   are 27 h apart). Never join fields across them within this row.
3. Its `time_of_crash` does not exist. This tool substitutes the XML mtime and marks
   `time_source='mtime'`; the crash-reporter never wrote a `TimeOfCrash`.

**Not the same thing as the other 7 degenerates.** Those have `ini` and no log, 43–62 threads,
distinct GUIDs, and normal-looking identity blocks — they are ordinary deaths whose *minidump* write
failed. `_0000` is the only pre-identity one.

⚠ **This is a fresh instance of the project's dominant error mode** (`supervive-instrument-artifact-pattern`):
a directory name collision in the crash reporter presenting as a single crash record.

---

## E. CONTRADICTIONS WITH `s109-dump-forensics.md` AND `s108-crash-triage.md`

Checked every dated / counted claim I could reach from the corpus. Five findings.

### E.1 ★ CONTRADICTION — S108 §3.2's "24 `Couldn't spawn player` reports" is wrong; it is 17

> S108 §3.2: *"They appear in **40 of the 87 dumps**, including **24** `Fatal error: Couldn't spawn
> player` reports that have nothing to do with either family."*

**MEASURED, N=92 UECC:** `Couldn't spawn player` appears in **17**. `CrashType=Assert` totals **24**,
and it decomposes as **17 `UnrealEngine.cpp:15551` (Couldn't spawn player) + 7
`MallocBinned2.cpp:1322`** — two disjoint families. S108 appears to have taken the assert count and
labelled it with one family's name.

**The direction rules out a corpus-growth explanation:** the tree only ever grows (87 → 92
directories since S108), so the count at S108 was ≤ 17. The 24 was wrong when written.

**Consequence:** the argument S108 §3.2 makes (*the 7-frame boot tail is not family evidence*) is
**unaffected** — it is the *label* that is wrong, not the conclusion.

### E.2 ★ CONTRADICTION IN SCOPE — S109 §11's Family B is now **9**, not 6, and the corpus grew inside S109's own session

S109 §11 lists Family B (`<64 KB-aligned base> + 0x205D`) as 6: `298DDD37 · 83E3410A · 858B6F07 ·
8C3ECC71 · B84A0661 · EBFECFE7`, and family A as 5, "**11 of 87 census rows = 12.6 %**".

**MEASURED — there are now three further rows with the identical corpus signature**
(`PCallStackHash == sha1("")`, `SecondsSinceStart == 0`, empty SUPERVIVE chain, `CallStack` naming
only `kernel32;ntdll`, page-aligned read fault address, `route=unknown`):

| GUID | crash (local) | dmp | modules | `CallStack` | fault addr |
|---|---|---:|---:|---|---|
| `4BC8B969` | 2026-08-04 18:18:10 | 13,410,758 | 202 | `kernel32;ntdll` | `0x1EE1B420000` |
| `6D587A6F` | 2026-08-04 22:57:14 | 13,168,769 | 105 | `kernel32;ntdll` | `0x1B508660000` |
| `4875FA89` | 2026-08-04 23:05:01 *(mtime)* | **0 B** | — | (empty) | `0x14AE5DDE000` |

The first two have real minidumps and the exact `kernel32;ntdll` CallStack shape of the three walked
Family-B members. **INFERRED (moderate)** — not MEASURED: I did not walk their minidumps, so the
`+0x205D` PC is unverified. `4875FA89` is shape-only (zero-byte dump). ⇒ **A+B is now 11→14 known,
i.e. ~13 % of 106 rather than 12.6 % of 87 — the *fraction* held, the *members* did not.**

**And the timing is the point:** `4BC8B969` fired at **18:18:10**, inside S109 §12's own
18:17–18:20 shim-discriminator window; `6D587A6F`/`4875FA89` fired inside §14's 22:57–23:11
`sub-NoMissions` window. **S109's §11 census was taken before the experiments §12–§14 ran, and was
never re-taken afterwards.** Its "7 zero-byte dumps on disk" is now 8 (`4875FA89` is the 8th) — a
live-corpus increment, not an error, but it means **every "N of 87" in S109 is stale by construction.**

### E.3 CONFIRMED — S109 §6's Family A table, exactly

Every row re-derived independently:

| GUID | S109 says | corpus says | dmp bytes | `CallStack` |
|---|---|---|---:|---|
| `064CE137` | 2026-06-26 01:24, secs 0, `…9ee00001` | 2026-06-26 01:24:50 (mtime), 0, `0x00007ffb9ee00001` | **0** | (empty) |
| `63AD699C` | 2026-07-08 22:05, secs 0 | 2026-07-08 22:05:26 (mtime), 0, `0x00007ff8f0400001` | **0** | (empty) |
| `62C094F1` | 2026-07-09 02:00, secs 0 | 2026-07-09 02:00:50 (mtime), 0, `0x00007ff8f0400001` | **0** | (empty) |
| `61C55551` | 2026-07-10 16:28, secs 0 | 2026-07-10 16:28:13, 0, `0x00007ff8f0400001` | 13,631,799 | **`runtime_7ff8f0400000;kernel32;ntdll`** |
| `A55704B3` | 2026-07-19 03:40, secs 0 | 2026-07-19 03:40:10, 0, `0x00007ff90e000001` | 13,264,110 | **`runtime;kernel32;ntdll`** |

**Detector positive control:** the `callstack_has_runtime` flag fires on 6 corpus rows total, so it is
capable of firing; the 2 named above are among them.

**Provenance added, which S109 did not have:** the five span **5 HEAD commits and 5 shim vintages**
(`(pre)`→`929d0d3`→`ccdb847`→`bc305bd`), 24 days. Not one build.

### E.4 CONFIRMED and DATED — S109's own retraction about `tutorial_launch.cpp`

S109 §6b retracts *"weeks before the tutorial route existed"* on the grounds that
`tutorial_launch.cpp` predates two family members. **MEASURED:** the file was **added in `ccdb847`,
2026-07-09 03:22:54**. So it postdates `63AD699C` (07-08 22:05) and `62C094F1` (07-09 02:00) by
5.3 h / 1.4 h, and predates `61C55551` (07-10) and `A55704B3` (07-19). **S109's retraction is
correct in every detail.**

One caveat S109 does not state: a commit date is an **upper** bound on when code existed. Given the
3 m 47 s … 2 h 54 m commit lags measured in §Method, `62C094F1` at 1 h 22 m before the commit is
**inside** the lag envelope — so "the tutorial shim did not exist yet" is not safe for that one.
`63AD699C` at 5.3 h before is outside every measured lag.

### E.5 CONFIRMED — S108 §3.3's 6-dump cluster, and S108 §3.1's "1 of 87"

All six re-found with matching `SecondsSinceStart` (`471B4885` 60 · `10CF9C87` 84 · `838C7D98` 259 ·
`DC4A30AB` 659 · `E7323D14` 677 · `A15041E9` 3334), **all route=tutorial**. **Provenance added:** they
span **2026-07-11 17:39 → 07-12 12:39**, **4 HEAD commits**, **4 shim vintages** (`a91a61c`,
`fb04117`, `0bde7ea`). The triaged dump `166396E2` itself is **2026-08-03 22:49:21, T+2550 s, shim
vintage `6e8a7df` (07-26)** — 22 days newer than the cluster it matches. S108 §3.3's inference
(*"this 23-frame tail is how the hook gets called, a signature of the instrument's entry point"*) is
**strengthened** by that: the tail survives 4 shim vintages and a 22-day gap, which a *bug* signature
would not be expected to.

`STATUS_SINGLE_STEP` (`0x80000004`) is still **1 of 92** (S108 said 1 of 87) — the FK-24 probe
self-kill, and still the only one.

### E.6 No contradiction, but a correction to the brief itself

The task brief and several docs describe `Modules` as whitespace-joined and the crash tree as holding
87/88 records. Both have moved: `Modules` is **newline**-delimited (game paths contain spaces) and the
tree is **92** directories with **45** crashpad archives. `fk8_corpus.py` handles both; anything
quoting a stored count is stale.

---

## Reproduce

```powershell
cd "G:\git\Supervive Revival Project"
python tools\crashtri\fk8_corpus.py            # rebuild docs/fk8-crash-corpus.csv (17 s; --no-logs = 0.6 s)
python tools\crashtri\fk8_timeline.py          # rebuild docs/fk8-crash-timeline.csv + print every table above
```

`fk8_timeline.py` runs `git log`/`git reflog` and reads the corpus CSV. It opens nothing under
`Saved\Crashes`. The hand re-derivations in §D used `Get-Item`/`Get-ChildItem` and `cat` on
`_0000` only.

## Open questions this pass could not close

1. **Which DLL was actually injected on any given run.** Gap **F3**. `tools/sigbypass-mod/build/` is
   git-ignored; no marker stamps a source SHA or build time. The cheapest possible fix is one line in
   `Marker()`: print `__DATE__ " " __TIME__` and a `-DKSRCSHA=` passed by `build.ps1`. Every
   provenance claim in this document is INFERRED until that exists.
2. **Whether the era-B → era-C timing shift survives re-zeroing the clock.** Needs
   `time since [PL] init complete`, which lives in `docs/tutorial-launch-marker.txt` — truncated on
   every injection (FK-25), but `git show <commit>:docs/tutorial-launch-marker.txt` recovers the
   committed snapshots. Not attempted here.
3. **How many events `_0000` really represents.** ≥2 MEASURED, ≥3 INFERRED, unbounded above.
4. **Whether `4BC8B969` / `6D587A6F` are really Family B.** Walk their minidumps with `mdctx.py` and
   check `rip & 0xFFFF == 0x205D`. ~10 minutes, offline.
