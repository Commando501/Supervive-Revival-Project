# FK-8 — the crash corpus, mined. Timing, clusters, provenance, and the crashpad class.

**Date of analysis:** 2026-08-05. **Repo HEAD at write time:** `027a19e`.
**Method:** four independent mining passes (timing / clusters / provenance / crashpad-class), each
re-derived from raw artifacts by an adversarial verifier that wrote its own parsers, plus a
completeness critic that went looking for what all five missed. **100 % offline** — no launch, no
injection, no backend. The crash tree
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes` was opened `rb` only; `find -newermt`
confirms 0 files written, moved or modified.

**Merge rule applied throughout: where a verifier refuted or weakened a claim, the verifier's number
is the one carried below.** Claims that were weakened in review are marked
**⚠ WEAKENED IN REVIEW** and the original form is quoted so the change is auditable.
Every claim is tagged **MEASURED** / **INFERRED** / **SPECULATIVE** and carries an N.
Every negative carries a scope; there are no bare absences in this file.

---

## 0. The verdict

**FK-8 is CLOSED with a positive control, and closing it immediately falsified more of the record
than it confirmed.** `SecondsSinceStart` is a genuine per-run elapsed-wall-clock measure — proven not
by "the values differ" but by a permutation control: within a sitting a run cannot outlast the
wall-clock gap since the previous crash, and observed violations are **0 / 56**, against a permuted
mean of **8.56** over 20,000 shuffles (P(0) = 0/20000). The corpus that line closed for 60+ sessions
is bigger than anyone thought (**114 distinct death records**, not 86/87/92) and **worth much less
than its size suggests**: at least **36 of the 114 (31.6 %) are self-inflicted** — the anti-tamper
protector killing the process (`runtime.dll+1`) or our own always-injected `catalog_store_fix.dll`
heap scan faulting on a decommitted page (`+0x205d`, identified to a byte). **All 22 crashpad reports
are in those two classes; the entire S109/S110 tutorial campaign produced zero game-attributable
deaths.** What changed about what the project believes, in order of cost:

1. **The FK-7 "ANIM family" is not animation code.** `0x3495973` and `0x349596d` — carried in
   `docs/fk7-crash-settled.md` as two separate members of the FK-7 signature — resolve to the **same
   4,336-byte function at `0x3494B40`**, whose string literals are `"Ticking Group [%s] GroupLeader
   [%d]"` and `"Invalid position from Leader %d. Trying next leader"`. It is the **tick task-graph
   dispatcher**, matching its `Foreground Worker #0` crashed thread. The family name and the
   two-member split are both wrong.
2. **The "~285 s code-integrity kill" is a 240–295 s mode with median 264 s, only 4 of 15 members are
   ≥283 s, and 4 of 15 are asserts** (which are not anti-tamper kills). The operational advice
   (hold T+220–250 s, not T+300 s) survives, but **the number it is derived from moves one-for-one
   with `-InjectGapSeconds`** and is not a property of the game.
3. **The whole timing analysis is expressed in the wrong clock.** `SecondsSinceStart` is the *launch*
   clock and contains the operator's staging schedule, which measurably moved +33.0 s between the
   July and August batches. Re-anchored to `Load map complete .../LVL_Tutorial`, one headline gap
   loses significance entirely (p 0.0010 → 0.1675) while the era split *survives* — and the two
   verifiers who computed that re-anchoring **disagree** (§7.1).
4. **Seven deaths counted as game bugs are shutdown-path crashes** (`is_requesting_exit == true`,
   identical 7/7 to the `+0x107d500` "lobby worker" cluster), and **six more are hangs**
   (`is_stuck == true`, `StuckThreadId == GameThread`). Neither column was read by any pass; the
   word "hang" appears in none of the four dimension write-ups.
5. **Nobody built an exposure denominator, and one is sitting on disk.**
   `docs/gft-ready-marker.txt` is append-mode and holds **80 `injected; base=` records** = 80 staged
   tutorial launches, against ~29 non-contaminated tutorial-route deaths. "FK-7 is deterministic" does
   not survive that ratio.
6. **The `-InjectGapSeconds` hazard table in `CLAUDE.md` — the belief that sets the current 20 s
   default and costs 15–29 s of every staged run — was never tested against fault family, and does
   not survive it.** The two deaths in the 30 s row (`knee-g30-2`, `knee-g30-3`) are **both**
   `catalog_store_fix`'s launch-time heap scan, which the *primary* injector fires and which
   `-InjectGapSeconds` does not touch.

---

## 1. The corpus

### 1.1 What it is and its true N

| layer | count | note |
|---:|---:|---|
| `UECC-*` directories in `Saved\Crashes` | **92** | enumerated, not globbed |
| — degenerate (zero-byte `UEMinidump.dmp`) | 8 | three agreeing signals: zero-byte dmp / no `TimeOfCrash` / no `Modules`; set equality **True** |
| — "real" UECC deaths | **84** | |
| — of the 84, timing-usable (`SecondsSinceStart > 0`) | 77 | the 15 `os-only` rows are exactly the 15 with `PCallStackHash == SHA1("")`; set equality **True** |
| `dumps/crashpad-*` archives | **45** (46 with `dumps/s109-sentry-20260804-1410/`) | the glob misses one full DB snapshot |
| — `.dmp` files inside them | 47 (48) | the archiver snapshots before **and** after each launch |
| — **distinct report uuids** | **22** | also 22 distinct by first-1 MB sha256, so dedup is not a filename artifact |
| — timing-usable | 20 | two rows carry `Seconds Since Start = 0` |
| **Distinct death records** | **114** | 92 + 22 |
| **Analysable** | **106** | 114 − 8 degenerate; independently reproduces 84 + 22 |
| **Combined timing-usable** | **97** | 77 + 20 |

**MEASURED.** All layers reproduced by at least two independently-written parsers (regex-over-raw-XML
vs `ElementTree`; hand-rolled MessagePack decoder vs library; a minidump reader written from the MS
spec vs `tools/crashtri/mdctx.py`).

### 1.2 What it excludes — state this every time

- **Every death that left no artifact.** The corpus is conditioned on death *and* on a record being
  written. §5.3 shows that class is large and was never sampled.
- **Every run that did not die.** No exposure denominator exists in the corpus (§7.2).
- **The 8 degenerate rows** — but see the ⚠ below: excluding them is **not** neutral.
- **25 duplicate crashpad archive copies** (47 files → 22 reports).
- **Operator-killed runs.** `configs/phase0-server.ps1:~79-86` does `Stop-Process -Force` under
  `-KillClient`, producing a signature indistinguishable from a silent crash.

⚠ **The "degenerate" exclusion is not random — it is a family filter.** **MEASURED:** all 7
non-`_0000` zero-byte-dump rows (`064CE137`, `62C094F1`, `63AD699C`, `83E3410A`, `858B6F07`,
`EBFECFE7`, `4875FA89`) carry a complete, parseable `<PCallStack>` that resolves to the protector
families of §3.1 — 3 family A and 4 family B, zero exceptions. They also carry the **full 847-char
command line** (§4.4). Dropping them deflates the packer census by 7 (24 % of it) and inflates every
game-side family's share. The honest corpus is **113 deaths, of which 7 are unroutable** — not 106.

### 1.3 How to regenerate

```
python tools/crashtri/fk8_corpus.py      # 114-row corpus -> docs/fk8-crash-corpus.{csv,json}
python tools/crashtri/fk8_timing.py      # histogram, modes, Rayleigh test
python tools/crashtri/fk8_timeline.py    # git reflog join, eras, route x era
python tools/crashtri/mdexc.py <dmp>     # exception record; USE THE EXCEPTION STREAM'S CONTEXT
```

⚠ **Three parser traps that each manufactured a false result during this pass:**

| trap | wrong result it produces | fix |
|---|---|---|
| Reading `MINIDUMP_THREAD.ThreadContext` for the crashed tid | "every crash is at one identical address" (RIP `0x7ffd3b1edc94`, `[rsp]` = KERNELBASE+0x462DE in **22/22** crashpad dumps) — that is the *dump writer's* state | read the **ExceptionStream's own** `ThreadContext`, stream 6 offset 160 |
| Substring-matching `runtime` in module lists | `runtime.dll present in 22/22 crashpad dumps` — it matches `VCRUNTIME140.dll` | compare exact basenames |
| Using the corpus's `fault_address` column for chainless rows | every `+0x205d` / `+1` test silently fails — the column is regexed from `<ErrorMessage>` and **disagrees with the dump for every family-B row** (`4BC8B969`: XML `0x1EE1B420000` vs dump RIP `0x1ED96B0205D`) | walk the dump |

Plus two documented gotchas that survived scrutiny: `CrashReporterMessage` really does appear twice
in every XML (one self-closing + one paired — a paired-only regex sees one, which is the reader's
artifact, not the corpus's), and `Copy-Item` preserving `LastWriteTime` still poisons any attempt to
re-derive `fk24-stage.ps1` step spacing from `docs/fk24-stage-*` mtimes.

---

## 2. Timing

### 2.1 FK-8 itself — CLOSED, with a positive control

**MEASURED (N=56 consecutive within-sitting pairs; 20,000 permutations).** Observed violations of
"a run cannot outlast the gap since the previous crash": **0**. Permuted mean **8.56**.
P(0 violations) = **0/20000**. Two independent corroborations: `secs − log_span_s` has median
**−0.3 s** (UECC, N=77, range −18.5…+124.9) and **+6.7 s** (crashpad, N=20, range −5.1…+115.1); and
the log's last timestamp tracks the crash time to ~1 s on every row.

**MEASURED (N=97, both classes).** `SecondsSinceStart` (UECC) and `Seconds Since Start` (crashpad)
are the **same clock**: log first-to-last span equals reported seconds to <1 s in both classes
(`A15041E9` 3334.3 vs 3334; `838C7D98` 259.3 vs 259; `41cdafa3` 491.2 vs 491; `c9a85003` 282.8 vs
283). ⚠ This equivalence is **structurally unfalsifiable as constructed** — the two classes are
disjoint at the process level (§5.2), so no case exists where both describe the same run.

**MEASURED.** `SecondsSinceStart` counts from **process start**, which precedes the log's first line
by a variable **0–125 s**. Hand-verified: `crashpad-20260805-025508-tutr1` secs 267 − log span 171.9
= 95.1 s. Partial explanation found: log-start → first `LVL_Login` load itself varies 0–124.6 s
(N=120, median 7.0), so much of the slop is **post**-log-open work, not the protector's unpack.

**MEASURED (N=92, the original audit's own denominator).** Restating the FK-8 bins on today's tree:
`==0` → **15** (was 12); `13–107` → **43** (identical set); `173–288` → **20** (was 19); `654–952` →
**7** (was 6); `>952` → **6** (was 5); **exactly-30 → still 5**. And the 30 s belief had a real
generator: 3 of the 5 thirties are the *same crash* (`FAsyncLoadingThread`, chain
`fe1746 2b8e7c5 2b8ebe8`, fault `0x1E3010020`, all 2026-07-01, all `menu-login`) — a reproducible
signature over-generalised into a property of the field. **That is a textbook instance of the
project's dominant error mode, and the cheapest one to have caught.**

### 2.2 The histogram, and why the "modes" are partly the operator

**MEASURED (N=97 combined, sorted).** Three literal death-free bands: **(107,156) w=49 s**,
**(201,240) w=39 s**, **(295,336) w=41 s**. Modes:

| mode | range | N | median | composition |
|---|---:|---:|---:|---|
| M1 | 13–107 s | 51 | 31 | menu-login 30, tutorial-attempted 11, menu-lobby 8 |
| M2 | 156–201 s | 13 | 194 | route=tutorial 12 of 13 |
| M3 | 240–295 s | 15 | 264 | tutorial 8 + tutorial-attempted 5 + menu-lobby 2; **Crash 11 / Assert 4** |
| M4 | 336–952 s | 12 | 656.5 | |
| M5 | 2550–42387 s | 6 | 3658.5 | |

⚠ **WEAKENED IN REVIEW.** Original claim: *"trimodal, separated by LITERAL death-free bands — not by
binning choices."* The bands are real and reproduce byte-for-byte; the **causal reading does not**.

- **MEASURED:** tutorial map-load *completion* moved from median **124.1 s** after process start
  (July batch, n=11) to **157.1 s** (August batch, n=9) — **+33.0 s**, matching `CLAUDE.md`'s own
  documented shift from ~T+145 s to ~T+175 s caused by the 20 s injection-gap enforcement.
- **MEASURED:** re-expressed in the map-load clock, the tutorial max gap in the comparable region
  falls from **57.0 s (uniform-null p = 0.0010)** to **27.9 s (p = 0.1675)** — not significant.
- **MEASURED:** the null model the original pass said it had not fitted, fitted. For the 28 values in
  [156,295]: naive uniform p = **0.0029**; one median per sitting (n=12) p = **0.0164**. So the band
  is not chance *in the launch clock* — and the cause that can be measured is the schedule.
- **MEASURED effective N:** M2's 13 deaths come from 5 sittings, **9 of them from one day**
  (2026-07-26) in 2 sittings; M3's 15 come from 9 sittings, **7 inside a single 2 h sitting** on
  2026-08-05. At the sitting level the whole 156–295 s window is **12 points, not 28**.

**Verdict carried:** the modes are a picture of two experiment configurations at least as much as of
a game timescale.

### 2.3 The four load-bearing claim verdicts

| # | claim as the project states it | verdict | the number that replaces it |
|---|---|---|---|
| **B1** | "the code-integrity kill lands at ~285 s" | **⚠ WEAKENED (twice)** | A **240–295 s mode, N=15, median 264**. Only **4/15** are ≥283 s. Composition **Crash 11 / Assert 4** — verified by decoding all 22 crashpad `__sentry-event` msgpack blobs (`Crash Type='Crash'`, `IsAssert='false'`, 22/22) plus 5 Crash + 4 Assert on the UECC side. UECC-only the mode is 240–288 s N=9, so **the 295 s right edge is crashpad-defined and not testable from `Saved\Crashes` alone**. No stack family in M3 repeats more than 3×. |
| **B2** | "~25 % of deaths are 'late'" | **CONFIRMED, and unmoved by the crashpad class** | 18/77 = 23 % (UECC) vs 24/97 = 25 % (combined). |
| **B3** | FK-7 "dies at T+173–201 s", a 28-second band | **CONFIRMED in its original scope; ⚠ WEAKENED as a general rule, and the "generalisation failure" is itself mostly a clock artifact** | In-scope (UECC, 2026-07-24…26) exactly **N=10**: 173,175,185,194,194,194,195,195,196,201 — reproduced exactly, chains byte-for-byte. The reported "same family 57 s past the edge" (194 s on 07-26 vs 258 s on 08-05) is **15.7 s** in the map-load clock, not 64.0 s — 48.3 s (75 %) is the staging offset. **The family is far MORE time-locked than the original pass concluded.** The corpus-wide "widening to 45 s" rests on two crashpad rows (156 s, 160 s) that are not structurally comparable — 156 s never completed a tutorial map load at all, and 160 s died **0.1 s after** the load, whereas every real FK-7 death is 52–74 s after it. Drop those two and the band is **unchanged at 173–201 s**. ⚠ Separately: 9 of the 10 in-scope deaths are one 2 h 55 m sitting, so effective N ≈ 2 configurations, not 10 trials. |
| **B4** | "the tutorial run dies within ~1–5 min" | **⚠ WEAKENED** | Contamination: 2 of the published 31 tutorial-route deaths are `UECC-166396E2` (2550 s) and `UECC-FED1F952` (572 s) — the two dumps `CLAUDE.md` names as the FK-24 probe self-killing, with an explicit instruction not to feed them to census analysis. Cleaned: **N=29, median 258 s, ≤300 s = 22/29 = 75.9 %** (not 71.0 %). **The hold trade-off survives: 220 s → 250 s costs 0 percentage points** (48.3 % at both); 250 s → 300 s costs ~+26. ⚠ And the route contrast that dresses this up ("the menu NEVER dies late", menu-login N=30 median 26 s max 56 s) is **definitionally forced**: `log_route` is the last completed map load, so it is a monotone function of survival. **MEASURED:** the client leaves `LVL_Login` after a median **9.3 s** (N=102, max 30.3, 95 % ≤20 s), and `LVL_Login` loads a median 7.0 s after log start. A run *cannot be* `menu-login` and long-lived; a late menu death is relabelled `menu-lobby`, which duly holds the whole idle tail to 42,387 s. |

### 2.4 The strongest result in the pass

**★★ MEASURED (N=76 UECC rows carrying a game RVA chain). Stack family and timing mode are
ORTHOGONAL.** One deterministic assert family spans **64×**; another chain spans **169×**:

```
3ee9cf5 3ec5faf 3efb466   n=17   13,30,33,33,45,49,53,55,90,107,184,264,277,288,654,810,834
107d500 122642f 12204d5   n=7    251,259,663,952,3216,8403,42387
fe0148  ff933e  32bcbee   n=6    14,14,15,15,16,28
fe1746  2b8e7c5 2b8ebe8   n=4    30,30,30,45
3495973 3405f13 3691a72   n=3    195,195,201
```

**Every inference of the form "it died at ~T, therefore mechanism X" is unsound.** Timing modes are
not mechanism labels. (Crashpad rows carry no parsed chain, so this is UECC-only.)

### 2.5 Negatives, each with its scope

- **NO periodic kill is detectable.** Rayleigh max-over-grid, periods 20–400 s at 0.5 s, on N=91
  (secs ≤1000): best 214.5 s, z = **29.27**; kernel-smoothed bootstrap null (2000 draws, bw 12 s)
  p95 = 37.6, p99 = 42.4 → **global p = 0.414**. Tutorial-only (N=29) p = 0.65. **Positive control:**
  a synthetic true 285 s period is recovered at p = 0.000 (σ=10 s) and p = 0.037 (σ=20 s) but **NOT**
  at σ=40 s (p = 0.40). *Scope:* absent **from the timing of deaths that left a crash artifact**, for
  periods with jitter ≲20 s. Structurally blind to deaths that leave nothing — which §5.3 shows is a
  large class. **This closes `ignorance-map-s101.md:1142`'s "cheapest experiment" as negative, with
  that caveat.**
- **NO Crash-vs-Assert timing difference.** Crash N=53 median 84 s vs Assert N=24 median 51 s,
  Mann-Whitney z=1.19 p=0.235. *Scope:* UECC timing-usable rows.
- **NO `exception_code` signal** beyond the (null) Crash/Assert split. *Scope:* the UECC XML class.
- **`thread_count`, `xml_module_count`, `app_has_focus`, `md_module_count`, `pcallstack_ngame`,
  `num_cores` are NOT real correlates** — every significant marginal ρ collapses within route
  (median is 54 threads / 21 modules in *every* route; within tutorial routes
  ρ(secs, xml_module_count) = exactly 0.000). *Scope:* N=77 UECC.
- **NO build-to-build timing comparison from the XML:** `EngineVersion`/`BuildVersion` are constant
  (`5.4.3-0+UE5` / `UE5-CL-0`) in all 92. *Scope:* the `<BuildVersion>` XML field only — see §4.4,
  the real build id **is** in the UECC class.
- **NO OOM:** `bIsOOM=0`, `OOMAllocationSize=0` in all 92. *Scope:* that artifact class, and
  `mem_*` is sampled only on the 24 Assert rows, so this is not "no run ever OOMed".

### 2.6 One free discriminator, and one selection effect

**★ MEASURED (N=17, within one deterministic assert family).** A **~3.5 GB resident-memory step**
separates runs perfectly at 150 s: the 10 rows <150 s are 5290–6101 MB `mem_used_physical`; the 7
rows ≥150 s are 1892–2327 MB — **zero overlap**. ρ(secs, used) = −0.638 (p=0.011); ρ(secs, peak) =
+0.464, i.e. the peak was reached and ~3.5 GB released. *Scope:* `mem_*` is populated in **exactly**
the 24 `CrashType=Assert` rows and is 0 in all 68 `Crash` rows (set equality **True**), and 0 % of
crashpad — so the discriminator exists on **26 % of the UECC class**. **INFERRED (untested):** that
this step is the tutorial map load's ~125,000-object GC purge (`docs/s110-item-watch-gc-mechanism.md`).

**MEASURED (45 sittings from 106 events at a 1 h gap; stable at 30 min/2 h).** First-of-sitting
N=39 median 87 s, ≥400 s in 11 (28 %); later N=58 median 95.5 s, ≥400 s in 6 (10 %). Mann-Whitney on
medians **z = 0.699, p = 0.485** (no difference); Fisher exact on the ≥400 s tail **p = 0.0305**.
**INFERRED:** that tail difference is a selection effect on the operator, not degradation of the
game. **The real planning line is relaunch overhead: median 333 s (q25 138, q75 787, N=58).**

---

## 3. Clusters, and the real denominator

### 3.1 The two self-inflicted classes

**★ MEASURED — family A: the protector's poison jump.** Fault PC == accessed address ==
`<runtime.dll image base> + 1`, `ExceptionInformation[0] == 8` (EXECUTE) — a DEP fault on a
`PAGE_READONLY` image page. Confirmed across three ASLR boot sessions by joining on the boot
fingerprint (ntdll base → runtime base), and **the UECC XML `<CallStack>` names it outright**:
frame 0 reads `runtime_7ff8f0400000` / `runtime`. `[rsp]` = `KERNEL32+0x17374`
(`BaseThreadInitThunk`) byte-identical in 16/16 crashpad members; **0 game pointers in the first 4 KB
of the faulting stack**; **0/18 crashed on the GameThread** — the crashing thread is a raw
`CreateThread` and genuinely unnamed.

**★ MEASURED — family B: our own shim.** Fault RIP `& 0xFFFF == 0x205d`, `RIP − 0x205d` 64 KB-aligned,
`ExceptionInformation[0] == 0` (READ), 10 of 11 accessed addresses page-aligned, in a region
belonging to no registered module. **Identified to the byte:** a 40-byte code window read out of
`UECC-4BC8B969`'s `Memory64List` matches **exactly one** DLL in `tools/sigbypass-mod/build/` —
`catalog_store_fix.dll` `.text` at **RVA 0x205d**. Exception-time registers corroborate:
`Rax = SUPERVIVE+0x8831758` (== `kCatMgrVtRva`, `catalog_store_fix.cpp:39`), `[rsp+0x108]` the same
reloaded vtable pointer, `R12` = the accessed address, `R15` = the scan end bound,
`R14 = kernel32+0x1c4e0` = **`VirtualQuery`** (resolved against the export table), and
`mov r8d, 0x30` = `sizeof(MEMORY_BASIC_INFORMATION)`. That is `FindCatalogManagers_first`
(`catalog_store_fix.cpp:204-222`, `kMapOff = 0x60`) beyond reasonable doubt. **`SafeReadable` is only
consulted AFTER a vtable match, so the scan itself is unguarded — this is a concrete, fixable TOCTOU
defect in the project's primary, always-injected shim.** `catalog_ready_fix.dll` contains only the
*preceding* window at RVA 0x1ff6 (its fault would read `…0x2036`); `catalog_purchasable_fix.dll`
contains neither — so the original open question "which of the three is it?" is **answered**.

**★★ MEASURED — the two families are one phenomenon.** All 15 UECC rows with
`PCallStackHash == SHA1("")` root in `KERNEL32+0x17374`. Their 2-frame stacks are
`[protector or shim PC] → BaseThreadInitThunk`, with UE mis-attributing the PC to the nearest
preceding module. So "os-only unwind", "family A" and "family B" are not three findings but **one: a
freshly-created unnamed thread whose entire call stack is one frame plus the thread entry thunk.**
The A/B split is what that thread *does*, not a difference in kind.

**★ A second, orthogonal discriminator the corpus does not carry:** UE's `PCallStack` frame-0 module.
Scan-shaped rows are **`mdnsNSP`** (Bonjour) in 9/9; poison-shaped rows are **`ntdll`** in 5/5. That
promotes the 4 dumpless "speculative" scan rows to near-attributed, and it works on rows with no dump.

### 3.2 The census, corrected upward

⚠ **WEAKENED IN REVIEW, then corrected UPWARD by the critic.** The clusters pass reported
**29 of 106 (27.4 %)**; the crashpad pass reported the same; both inherited the corpus's exclusion of
the degenerate rows. Resolving `base+offset` to an absolute PC from the surviving `<PCallStack>` of
those rows adds **7 more** (`064CE137`, `62C094F1`, `63AD699C` → family A; `4875FA89`, `83E3410A`,
`858B6F07`, `EBFECFE7` → family B). Two of the family-A rows sit at the **exact** `runtime.dll` base
`0x7ff8f0400000` that a dump-bearing row confirms independently.

| class | count | of 114 |
|---|---:|---:|
| protector poison (`runtime.dll+1`) | 21 + 3 degenerate = **24** | 21.1 % |
| our `catalog_store_fix` heap scan (`+0x205d`) | 11 + 4 degenerate\* = **11 MEASURED, up to 15** | 9.6–13.2 % |
| FK-24 probe self-kill (`166396E2`, `FED1F952`) | **2** | 1.8 % |
| unattributable (`_0000`) | 1 | |
| **self-inflicted, total** | **36 of 114 = 31.6 %** | |
| residual, "game-attributable" | **75** | 65.8 % |

\* the 4 degenerate family-B rows are attributed by PC-suffix from `PCallStack` and by the `mdnsNSP`
frame-0 signal, not by a dump — **INFERRED**, high confidence.

⚠ **"75 game-attributable" is a RESIDUAL, not a measurement.** It is 114 minus everything positively
attributed. Nothing established that any of the 75 is a game defect, and §3.4 immediately removes 13
more from it. This supersedes S109's "corrected denominators 85 / 79 / 74", which covered UECC only
and predates 4 directories; and `docs/s109-dump-forensics.md` §11's **"A + B = 11 of 87 (12.6 %)"** is
stale in numerator *and* denominator — the correct UECC-only figure is **15 of 92 (16.3 %), 13
attributed, 2 unresolvable**, and S109's own §11 census was taken **before** its §12–14 experiments,
three of which produced new census rows.

### 3.3 The crashpad class holds no game bugs at all

**★★ MEASURED (N=22 distinct reports, 100 % coverage).** **16 family A + 6 family B = 22.** Zero
game-attributable deaths in the entire crashpad class. That includes every death of the S109/S110
tutorial campaign — `tut1-DEATH`, `tut3-NOSTAGE`, `tut4-DEATH`, `tuta1-DEATH`, `tuta3-DEATH`,
`tutr1-DEATH`, `tutr3-DEATH`, `s110itemwatch`, `phase2-nostage`, `phase2b-void`, `animref-SUCCESS`,
`knee-g30-2/3-DEATH`. **The S109/S110 campaign produced no evidence about FK-7.**

⚠ **WEAKENED IN REVIEW:** the clusters pass split the 14 never-documented reports as "11 protector +
3 scan"; the correct split is **12 + 2** (the unlabelled `crashpad-20260805-030027`, uuid `45b740e8`,
secs 160, is a poison kill). Its own verifier's count of the mention probe stands: **8 of 22 crashpad
and 36 of 91 GUID-bearing UECC directories are named anywhere in `docs/` + `memory/` + `CLAUDE.md`**
(pre-session prose corpus, 574 files / 125.2 MB, **excluding this session's own `fk8-*` outputs** —
with them present the same probe returns 22/22 and 91/91, so the statistic self-erases the moment
this file lands; see §8).

### 3.4 Two failure modes nobody named — and they eat the residual

**★★ MEASURED (N=92 UECC). HANGS.** `is_stuck == true` in **6 rows**, each with
`Misc.StuckThreadId == the GameThread id` — UE's `FThreadHeartBeat` detector, i.e. **the GameThread
stopped ticking before the fault**: `3051E59B` (240 s, tutorial-attempted), `7C51644F` (22 s,
menu-login), `838C7D98` (259 s, tutorial), `C82D6169` (184 s, tutorial, Assert), `DC4A30AB` (659 s,
tutorial), `EF11C5B3` (45 s, tutorial-attempted). **Four are tutorial-route, and `C82D6169` is
precisely the row the provenance pass used as "era A's only in-window death."** The word *hang*
appears in none of the four dimension write-ups. Any timing or family statistic that pools hangs with
instantaneous faults is pooling two mechanisms.

**★★ MEASURED (N=92 UECC). SHUTDOWN-PATH CRASHES.** `is_requesting_exit == true` in **exactly 7
rows**, and that set is **identical 7/7 both ways** to the `+0x107d500` "lobby worker null deref"
cluster (chain `107d500 122642f 12204d5`, `Foreground Worker #0/#1`, secs 251/259/663/952/3216/8403/
42387). **The engine was already tearing down.** This is "the game AVs on quit", which also explains
the otherwise absurd 11.8 h "survival". The clusters pass nominated this as one of "the two largest
game clusters never opened" and left it inside the 75-death residual.

**Consequence: the residual is at most 75 − 7 − 6 = 62, and nobody has recomputed it.**

### 3.5 The other large cluster, and what it actually is

⚠ **WEAKENED IN REVIEW.** "The 17-record `Couldn't spawn player` assert" is **one assert site, not one
failure mode**: 11 read `Couldn't spawn player: ALokiGameMode::Login failed to Login` and 6 read
`Couldn't spawn player: PlayerState is null`. GameThread 17/17, 16/17 route=tutorial-attempted,
2026-07-09…11, secs 13–834 median **90** (the stage-1 brief's "median 107" is the 10th of 17 values,
not the 9th).

**★ NEW — symbolised, in under two minutes, offline.** `tools/strxref` (`python strxref.py func
0x<rva>`) resolves any crash RVA to an exact `.pdata` extent plus that function's string literals:

| chain head | function | literals | reading |
|---|---|---|---|
| `0x3ee9cf5` | `0x3EE97A9` | `"Couldn't spawn player: %s"`, `"LoadMap: failed to Listen(%s)"`, `"Took %f seconds to LoadMap(%s)"` | **`UEngine::LoadMap`** — *positive control:* it agrees with the row's own assert file |
| `0x3495973` **and** `0x349596d` | **the same** `0x3494B40` (4,336 B) | `"Ticking Group [%s] GroupLeader [%d]"`, `"Invalid position from Leader %d. Trying next leader"` | **the tick task-graph dispatcher** — matching its `Foreground Worker #0` crashed thread |

**The FK-7 "ANIM family" was never in animation code, and `3495973`/`349596d` are one family, not
two.** All four passes listed "symbolise the clusters" as an open question rather than running it.

### 3.6 Cluster-key negatives, scoped

- **`PCallStackHash` has never been used by any project tool.** Over N=92 it is a *strict refinement*
  of `harvest.py`'s chain-3 key where the unwinder worked (35 hashes vs 34 families on the 76
  unwind-ok rows; hashes spanning >1 family = **0**; exactly one family splits). But **both keys are
  blind exactly where the non-game deaths live** — the 16 no-game-frame rows collapse to 1 bucket
  under `harvest` and 2 under the hash while containing ≥3 unrelated mechanisms. And the hash is
  *coarser* than `ErrorMessage` for asserts (`D5ABA8A5` n=17 holds both messages of §3.5).
  ⚠ `DA39A3EE…` n=15 is **SHA-1 of the empty string** — a degenerate hash, not a stack cluster; it
  must be excluded from any cluster table. **Correct composite key:** `assert_file:line` for asserts,
  `PCallStackHash` where game frames exist, the minidump exception record where they don't.
- **`runtime.dll` is absent from all 22 crashpad module lists** (exact-basename test, loaded *and*
  unloaded) while present in **84/84** UECC `ModuleListStream`s — and **81 of those 84 list it TWICE,
  at two different bases** (e.g. `0xff760000` **and** `0x7ff8f0400000`; the confirmed family-A fault
  is the second of those +1). ⚠ **The stated mechanism is REFUTED:** a loader-based module list *does*
  see `runtime.dll`, so it is not manually mapped and **cannot serve as a positive control for the
  manual-mapping blind spot that hides our shims** — that inference currently has **no** positive
  control. The 0/22 needs a different explanation (crashpad's out-of-process snapshot vs UE's
  in-process writer, or PEB-unlink timing) and is unexplained.
- **No shim DLL appears in any of the 114 minidump module lists.** *Scope:* the minidump module-list
  artifact class only — `tools/inject` manual-maps, so shims are never loader-registered. Every
  attribution above rests on faulting code, never on shim presence in a record.
- **No bracketed shim marker tag** (`[SP] [PL] [FO] [ANIM] [VTG] [GCW] [GFT] [KANIMREF] [MISS] [BP]`)
  appears in **any** of the 177 `Loki*.log` files scanned (85 UECC + 92 under `dumps/`), with an
  overlap-safe streaming scanner. *Scope:* the log artifact class only — `Marker()` writes
  `docs/<shim>-marker.txt` via `CreateFileA` and has **no path into UE's log**. **Positive control
  fires** on `docs/fk24-run-nostatictest1.txt` with `{PL:25, ANIM:12, VTG:1, GCW:1}`. **Absent marker
  ≠ shim absent** — this is ignorance-map gap F3, live.
- **`__sentry-breadcrumb1/2` are 0 bytes in ~180/180 files** across all archives; the only breadcrumbs
  in that class are inside `__sentry-event`'s array and are exclusively `PostLoadMapWithWorld`
  transitions. **`crashpad_info`'s `simple_annotations` is `size 0, rva 0` in 22/22** — no crashpad
  key/value annotations exist in this build's integration. **`RHI.Breadcrumbs/DRED/Aftermath` are the
  literal string `false` in 84/84 UECC XMLs** — configuration flags, not data; actual breadcrumb data
  is 12 `Breadcrumbs_RHIThread_*.txt` files in 10 directories, all menu-route, ≤4 lines each,
  **contents never read**.
- **The `<Registers>` element inside the XML's per-thread blocks is present 4,880 times and empty
  4,880 times.** *Scope:* the XML class — register state is in the minidump `ThreadListStream`.
- **`BPScriptStack` is `None` in 70/70 non-empty values** — no Blueprint VM frame in any UECC death.

### 3.7 Per-thread stacks: a whole axis, unmined

**MEASURED (N=84 real UECC deaths, derived twice by independent routes — minidump `ThreadNames`
keyed on the exception stream's tid, and the XML's `IsCrashed` flag — with **0** tid disagreements):**

```
GameThread 46 | RHIThread 9 | Foreground Worker #1 8 | unnamed 7 | FAsyncLoadingThread 5
Foreground Worker #0 4 | Background Worker #5 2 | RenderThread 0 1 | Background Worker #10 1
HttpManagerThread 1
```

**38 of 84 crashed off the GameThread** — refined: the 7 "unnamed" are **exactly** the 7 packer rows,
so the *game-code* off-GameThread population is **31 of 77**. **8 of 20 tutorial-route UECC deaths are
off-GameThread**, so "the tutorial death is a GameThread event" is unsupported for 40 % of them. The
XML holds **4,818 non-empty per-thread callstacks** with module+RVA frames that no project tool has
ever read. ⚠ And crashpad dumps **name 73–91 threads each** (of 121–158) — *more* than UECC's 44–81 —
so "crashpad names only one thread" is **REFUTED**; per-thread attribution is fully available there
and unused.

---

## 4. Provenance

### 4.1 Three eras, and the FK-7 window belongs to exactly one

**MEASURED (N=31 tutorial-route deaths; reproduced exactly by two independent parser stacks).**

| era | dates | N | median | in 173–201 s | in 255–340 s |
|---|---|---:|---:|---:|---:|
| A | 2026-07-09…12 | 7 | 259 s | **1/7**† | — |
| B | 2026-07-24…26 | 10 | 194 s | **10/10** | **0/10** |
| C | 2026-08-03…05 | 14 | 292.5 s | **0/14** | 8/14 |

† `C82D6169` (184 s) is `CrashType=Assert` **and** `is_stuck=true`; restricted to non-assert AVs era A
is **0/6**.

**★ The disjointness SURVIVES re-zeroing the clock** — the experiment three of the four passes listed
as the one that would decide whether FK-7 stopped reproducing, done offline for free. Re-anchored to
each death's own `Load map complete .../LVL_Tutorial`: era B in-tutorial survival =
**49.5, 52.0, 54.0, 67.3, 68.4, 70.1, 72.3, 72.8, 72.9, 73.5 s** (all ten inside a 24-second band);
era C = **94.4 … 2440.6 s**. `min(C) = 94.4 > max(B) = 73.5`. Force-open time itself moved from
~115–125 s (era B) to 37–220 s (era C), confirming clock-zero really changed — **and the gap is not
explained by it.**

⚠ **This CONTRADICTS §2.3's B3 finding** that the same chain's shift is only 15.7 s in the map-load
clock (73.1 s → 88.8 s), which would put that era-C member *below* era C's stated minimum of 94.4 s.
Two verifiers measured the same quantity for the same crash and disagree. **Open — see §7.1.**

⚠ **Correction to the original pass:** **three** era-C tutorial deaths predate `fk24-stage.ps1`
(`ed252c4`, 2026-08-04 14:20:48), not two — `41cdafa3` at 14:10:26, T+491 s, was missed. Direction
strengthens the claim.

⚠ **Effective N warning:** 9 of era B's 10 fall inside a single 2 h 55 m sitting on 2026-07-26
(01:44–04:39). Era B is ~2 independent configurations, not 10 trials.

### 4.2 What code produced the corpus

**MEASURED.** `HEAD`-at-crash-time is derived from `git reflog` (414 entries reaching the initial
commit `d172bae`, nothing expired), **not** from commit ordering — HEAD really moved (main →
`claude/assetregistry-…` on 06-28 01:31, back and forth 06-29, → `dedicated-server-stub` 06-29 14:59,
an `ours` merge 07-10 21:05), so a naive "last commit ≤ crash time" join would have **mis-assigned 9
deaths**. 106 deaths spread over **51 distinct HEAD commits**; the largest bucket (`b1731ed`, n=15) is
a **dwell artifact** — HEAD sat there 17 h 41 m. One death (`F86B2A5B`) predates the initial commit by
47 s and correctly carries an empty `head_sha`.

⚠ **WEAKENED IN REVIEW.** Original: *"exactly one death was produced by the shim source that is
current today; 105 of 106 were not."* True of **`tutorial_launch.cpp` only**, and vacuous for the 47
menu-route deaths where it was never injected. The other seven shim sources have not changed for
weeks (`catalog_store_fix.cpp` `c1eaf88` 07-05, `catalog_pick_fix.cpp` 07-06, `mainmenu_refresh_pi8`
07-08, `missions_fix` 07-10, `loadout_fix` 07-19, `battlepass_adopt_fix` 07-19, `gft_ready_fix`
07-24): **36 of 106 deaths post-date all seven**, so for those 36 every shim except
`tutorial_launch.cpp` is byte-identical to today's. ⚠ **And by its own rule the count is now zero** —
HEAD has moved seven commits past `a827ef9` to `027a19e` (S111 / FK-30, `docs/s111-asc-census.md`),
which no pass read.

**MEASURED — shim-vintage attribution is INFERRED and bounded, and gap F3 is why.**
`tools/sigbypass-mod/build/` is git-ignored (`tools/sigbypass-mod/.gitignore:12`, **not** root
`.gitignore:12`), and `git log --all --diff-filter=A -- 'tools/sigbypass-mod/build/*'` returns
nothing: **no built shim DLL exists anywhere in history.** 19 of 20 `tutorial_launch_*.dll` on disk
predate the current source commit. Measured commit lag for the 6 runs with a tracked evidence file:
3 m 47 s … 2 h 54 m — which measures **when evidence was committed, not when a DLL was built.**
⚠ HEAD bounds *committed* source only; the tree is dirty right now, including
`server/internal/interactive/interactive.go`, the file holding `forceTutorialMatch` — the switch that
decides whether a run is a tutorial run at all.

### 4.3 Route mix turns over twice; no cluster is one build

**MEASURED.** Route × era: 06-25…07-07 = menu-lobby 12 / menu-login 25 / tutorial **0**;
07-08…07-19 = tutorial 7 + tutorial-attempted 16-18 + unknown 5; 07-21…07-26 = tutorial **10**, nothing
else; 08-03…08-05 = tutorial 14 / menu-login 6 / menu-lobby 2 / attempted 2 / unknown 3.
Vintage spans: all real deaths **51 HEADs / 24 shim vintages**; route=tutorial 17 HEADs / 12 vintages;
the 4 FK-7 camera dumps 3 HEADs / 3 vintages (independently **confirming**
`fk7-crash-settled.md` §0.2a — though the two `12c7e2d` dumps are themselves a week and 4 commits
apart, so "the split correlates perfectly with build vintage" is true but weak: many boundaries would
separate that cohort). Cluster `D5ABA8A5` n=17 spans 3 vintages over 2.6 days; `50A9FDF3` n=7 spans
**23.2 days** (not 25). 22 distinct calendar days; the three heaviest (08-05 n=15, 07-10 n=12, 06-30
n=11) are **35.8 %** of the corpus.

⚠ **Route label `tutorial-attempted` is key-sensitive.** `fk8_corpus.py`'s `route_label()` falls
through on a bare `LVL_Tutorial` substring appearing anywhere in a multi-hundred-MB log; requiring the
echoed force-open URL moves 2 rows to `menu-lobby`. `tutorial` and `menu-login` are robust (last-map
based); **any count of `tutorial-attempted` must state the key used.**

⚠ **The "both self-inflicted classes appear only after 2026-07-03" temporal claim is WEAKENED.**
Stated as 0/34 pre vs 29/72 post — but **the crashpad class does not exist before 2026-08-04** and is
100 % self-inflicted by construction, supplying 16 of the 18 post-cut poison and 6 of the 11 post-cut
scan rows. Within the only class present in **both** eras (UECC): **0/34 vs 7/50, Fisher two-sided
p = 0.038.** Real, but an order of magnitude weaker than it reads. Mild supporting control the
original missed: 4 of the 34 pre-cut runs *did* reach ≥285 s, so pre-era exposure to the kill window
existed and produced no poison kill.

### 4.4 Build provenance — the "only crashpad has it" claim is REFUTED

⚠ **REFUTED IN REVIEW.** Original: *"Only the crashpad artifact class carries real game-build
provenance; the UECC class strips it."* That is a **single field's** blind spot reported as a property
of the **artifact class** — the exact error this project documents.

- **MEASURED:** `release2.4.live-156430-shipping` appears in **77 of 85** UECC `Loki.log` files
  (streaming regex over 997 MB), and no other build id appears anywhere in the corpus. It is missing
  only from the XML `<BuildVersion>` element (placeholder `UE5-CL-0`, 91/92).
- **MEASURED:** the real command line is `CommandLineRemoved` in the XML — but the **minidump user
  stream `0x10000`** (266,240 B of UTF-16LE `<FGenericCrashContext>`) is present in **84/84** UECC
  dumps and carries the **real 847–906-char command line in 84/84**. SHA-1 clustering gives exactly
  **3 variants**: 79× the baseline launch-redirect set; 4× with ` 127.0.0.1:7777` (the DS-join runs
  `7AE9830F`, `A84A3CA0`, `CD25F035`, `D06CC55E` — tagging 4 deaths to
  `supervive-dedicated-server-status`); 1× with ` -ExecCmds="net.IgnoreNetworkChecksumMismatch 1"`
  (`F42EF322`). **Additionally, 7 UECC XMLs carry the full line on disk** — and they are precisely the
  7 discarded degenerate rows. *The class that was thrown away is the class that kept the provenance.*
- **The conclusion survives and strengthens:** the game binary is **constant across the whole 42-day
  corpus**, so no era difference is a game-version effect — now supported by 99 artifacts, not 43.
- ⚠ **But the command line is worth less than claimed:** SHA-1 over all 22 crashpad command lines
  yields exactly **one** distinct value. `-NoMissions` / `-NoPasses` / `-Hook` are launcher-side and
  **never reach the game's argv**, so it cannot discriminate shim configurations.
- ⚠ **Denominator slip in the original:** "43 crashpad rows" counts `.dmp` copies, not deaths (22).

### 4.5 The `_0000` collision bucket

⚠ **WEAKENED IN REVIEW** from MEASURED to **INFERRED**. Every *measurement* reproduces:
`CrashContext.runtime-xml` + `UEMinidump.dmp` created 2026-06-28 15:41:08, **last written 2026-06-29
18:45:55** (27 h later); `Loki.log` last written 2026-06-28 17:37:09; 18 live thread records; unique
`ExecutionGuid 2728BF64…`; `CrashGUID` empty; `ProcessId 0`; AV reading image base + `0x3EC57D0`; a
509-byte log ending at `Mounting pak file pakchunk0_s9-WindowsClient.pak`; and it is the **only** one
of 92 with no `CrashReportClient.ini`. But "≥2 distinct process deaths" is an **inference from NTFS
CreationTime semantics** with an untested single-event alternative (one crash whose
`CrashReportClient` stalled 27 h). This matters beyond the row itself: it is the **only** counterexample
to "the crash tree only grows", which §6 uses to date the S108 assert count.

**Rules regardless:** `_0000` is 1 row representing ≥1 and plausibly ≥2 events; **never join fields
across its XML and its log**; it has no `TimeOfCrash` at all.

---

## 5. The crashpad class, and the invisible third class

### 5.1 What crashpad captures

**MEASURED (N=22).** All 22 are protector control-flow (§3.3). `MemoryInfoList` resolves the family-A
target to `state=COMMIT, Type=IMAGE, AllocationProtect=EXECUTE_WRITECOPY, Protect=READONLY`, in no
loaded or unloaded module. **Neither class is a superset of the other:** `ProcessVmCounters` (22) and
`SystemMemoryInfo` (21) are in 84/84 UECC and 0/22 crashpad; `MemoryInfoList` (16) and
`UnloadedModuleList` (14) are in 22/22 crashpad and 0/84 UECC. `MemoryInfoList` gives the packer's
full VAD map **offline** — 44,543 regions in one dump.

**MEASURED.** `ARCHIVE-INFO.txt`'s `trigger : … (pre-launch sweep)` is a **bare string literal** at
`configs/archive-crashdumps.ps1:221` with no branch — it is **not** evidence of how the archiver was
invoked. `archive_trigger` must be dropped as a discriminator. Archive-per-report: 1×1, 18×2, 2×3,
1×4; **45/45 archives contain ≥1 report**, so the anticipated "empty sweep" class is currently empty.

**MEASURED.** The Sentry project is alive and the DSN key valid: the session **envelope** POST to
`o566896.ingest.sentry.io/api/5710262/envelope/` returns `HTTP/1.1 200 OK`. `settings.dat`
`options=0x1` (uploads enabled) in 45/45; `upload_attempts=1` at crash+~2 s in 22/22. *Scope:* the
`/envelope/` endpoint only — `/api/5710262/minidump/` was **not** tested. ⚠ **This raises the residual
risk in `s109-fk9-capture-durable.md` §5: archiving works only while the minidump upload fails, and
the envelope upload demonstrably succeeds.**

### 5.2 The two classes are disjoint — but the discriminator is NOT known

**MEASURED.** Disjoint by two independent keys: 0 of 22 crashpad Crash-GUIDs match any UECC directory
(positive control: the same key self-joins UECC **92/92**); and joining on minidump MiscInfo
`(ProcessId, ProcessCreateTime)` gives 84 UECC process instances, 22 crashpad, **overlap 0**, with
granularity controls passing both ways. Log keys: `Sentry HandleBeforeCrash Begin` **0/85 UECC vs
22/22 crashpad**; positive control `Sentry initialization completed` fires **77/85 UECC** — Sentry was
armed and the death still went to CrashReportClient. Interleaved on the same day and route.

⚠ **WEAKENED IN REVIEW — the routing rule is REFUTED.** The claim "0/22 crashpad are Asserts, 0/22
fault inside the .exe, 22/22 fault on an unnamed thread ⇒ a perfect discriminator" fails: **7 UECC
deaths satisfy all three** (2 family A, 5 family B — non-assert, out-of-exe, unnamed thread) and went
to CrashReportClient anyway. The cleanest case: `UECC-4BC8B969` (family B, pid 37620, created
23:17:12) and crashpad `590cfd83` (family B, pid 18000, created 23:19:15) — consecutive launches ~1
minute apart, **identical fault family, opposite handlers**. ⚠ Also confounded: crashpad spans only
28 h (2026-08-04 19:10 → 08-05 23:19) while UECC spans 41 days with **81 of 84 preceding that window
entirely**; the overlap sample that could break the confound is **n = 3**. **What routes a death is
open, and more open than any pass stated.**

**Consolation: the pooling bias people feared is not there.** **MEASURED:** tutorial-route UECC
median **198 s**; excluding packer families from both classes leaves the same **198 s** (the 7 UECC
packer rows are all non-tutorial at 6–58 s). ⚠ Partly circular — if all 22 crashpad are packer, the
exclusion deletes the crashpad class by construction, so this is a restatement of §3.3, not an
independent second measurement.

### 5.3 The invisible third class — real, unquantified, and perishable

**★★★ This is the biggest hole in the pass, and it is the one nobody instrumented.**

`tools/crashtri/fk8_corpus.py` contains **zero** references to
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs`. Every corpus row comes from the UECC tree or
`dumps/crashpad-*` — i.e. **the corpus is conditioned on a crash artifact existing.**

**MEASURED, at three different instants, by three different readers — and the number moved every
time:**

| read | files present | with a Sentry handoff | artifact-less |
|---|---:|---:|---:|
| crashpad pass | 10 | 4 | **6 (60 %)** |
| its verifier | 10 (**one cited file already gone; two new ones rotated in**) | 3 | **7 (70 %)** |
| completeness critic | 11 | 3 | **8 (73 %)** |

⚠ **REFUTED as a citable constant.** `Saved\Logs` is a **fixed-depth rotating ring**; any ratio
computed over it is a property of *when you looked*. This is the same shape as the retracted
"~3-minute crashpad window" — an observation interval recorded as the phenomenon's timescale.
**Never store this number; snapshot the directory instead.**

**What survives, and it is large:** **MEASURED (critic's read, N=11)** — 7 of the 8 artifact-less
sessions reached `Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial` and ran **341, 374, 395,
414, 344, 423 and 301 s** by their own first/last log timestamps. **Those runs routinely crossed both
the "~1–5 min" band and the "~285 s kill".** None of the 10–11 carries a single exit marker
(positive control: `Loki_2.log`, a clean quit, ends `LogExit: Exiting.` + `Log file closed`, 8
matches); one ends mid-token (`…][553]L`).

**Whether they are crashes or kills is UNDETERMINED** — `configs/phase0-server.ps1:~79-86` force-kills
the client under `-KillClient` with an identical signature. ⚠ **Two prior project claims of an
invisible death class are already retracted** (`fk7-crash-settled.md` §4.4's "5 dumpless deaths",
retracted S106e; FK-26, refuted by `s108-fk24-instrument-corrected.md` R2), so the best-supported
figure before this pass was **zero confirmed artifact-less deaths.**

**★ And the project's own config supplies a mechanism nobody read.** **MEASURED:** every
`UECC-*/CrashReportClient.ini` is byte-identical (1 distinct SHA-1 over 91 files) and contains
**`Stall.RecordDump=false`** / `Ensure.RecordDump=true` / `CrashConfigPurgeDays=2`. **A stall/hang is
configured NOT to produce a dump.** Combined with the 6 `is_stuck` rows (§3.4) that is a named,
documented route to a termination that leaves nothing — far better than an unbounded 0–70 %.
`fk8_corpus.py` never opens the file; it only lists the name in `dir_files`.

**★ Fresh evidence that arrived after every pass finished.** **MEASURED:** the S111 sitting that moved
HEAD to `027a19e` (~64 minutes, `docs/s111-asc-census.md`) produced **four process lifetimes and zero
new crash artifacts** — the crash tree is still 92 directories and `dumps/crashpad-*` still 45.

---

## 6. Corrections to the record

Every line below is falsified or made stale by this pass. **None was edited by this pass** — the main
session applies them.

| file:line | current text (abridged) | correction |
|---|---|---|
| `docs/session-39-menu-crash.txt:82` | `SecondsSinceStart: 30 ❌ RETRACTED 2026-08-05` | Retraction is correct but bare. Point it at this file and state the closure: FK-8 is **CLOSED with a permutation positive control** (0/56 violations, permuted mean 8.56, P<5e-5), not merely by a counterexample. Note the belief had a real generator — 3 of the 5 thirties are one deterministic `FAsyncLoadingThread` signature. |
| `docs/ignorance-map-s101.md:478-488` (FK-8 entry) | "Across all 86 XMLs: exactly 5 are 30. Distribution: 0 (×12), 13–107 (×43), 173–288 (×19), 654–952 (×6)…" | Denominator is now **92 UECC / 114 distinct deaths / 97 timing-usable**. Restated bins: `==0` **15**, `13–107` **43**, `173–288` **20**, `654–952` **7**, `>952` **6**, exactly-30 still 5. Mark **CLOSED** with the positive control. Add: "the corpus is conditioned on an artifact existing; ≥31.6 % of it is self-inflicted." |
| `docs/ignorance-map-s101.md:1098` | `\| "SecondsSinceStart is always 30" \| 5 of 86 (FK-8) \|` | → `5 of 92 UECC / 114 distinct deaths (FK-8, CLOSED with a permutation control)`. |
| `docs/ignorance-map-s101.md:1142` (row 7, "~3–5 min integrity check") | cheapest experiment: "statistical modulo test on the 86 `SecondsSinceStart` values" | **DONE and NEGATIVE.** Rayleigh max-over-grid 20–400 s, N=91: best 214.5 s z=29.27, bootstrap **p = 0.414**; positive control fires at σ≤20 s, fails at σ=40 s. Scope: absent from the timing of deaths that left an artifact; **blind to the artifact-less class of §5.3**. Also note the row's supporting "173–201 s cluster sits inside the window" is now era-B-only and its family is the tick task-graph dispatcher, not animation. |
| `CLAUDE.md:99` | "Hold to **T+220–250 s, NOT T+300 s** — the code-integrity kill lands at ~285 s." | Keep the hold (it is confirmed: 220→250 costs 0 pp, 250→300 costs ~+26 pp). Replace the mechanism number: **a 240–295 s mode, N=15, median 264 s, only 4/15 ≥283 s, 4/15 asserts.** Add the durable form: **"hold ≲50 s past `Load map complete …/LVL_Tutorial`"** — invariant to staging, whereas `T+250 s` silently breaks when `-InjectGapSeconds` changes. |
| `CLAUDE.md:213-214` | "…the probe now arms around T+175 s… the T+220–250 s hold still fits" | Same substitution; note explicitly that both numbers are **staging-schedule-relative** (measured +33.0 s July→August). |
| `CLAUDE.md` (the `-InjectGapSeconds` hazard table, ~§Launch) | "3 s gap → 3 deaths… 71× lower hazard at ≥10 s, P=8.6e-5" | **Add a caveat, do not delete.** The outcome variable was never split by fault family. Both deaths in the 30 s row (`knee-g30-2`, `knee-g30-3`) are `catalog_store_fix`'s launch-time heap scan (`+0x205d`), which the **primary** injector fires and `-InjectGapSeconds` does not touch; `sub-NoMissions-1/-2` and `sub-NoPasses-2` are the same. Mark the table **UNDER RE-EXAMINATION**. |
| `docs/s108-crash-triage.md:355` | "including 24 `Fatal error: Couldn't spawn player` reports" | **17**, not 24. 24 is *all* asserts = 17 `UnrealEngine.cpp:15551` + 7 `MallocBinned2.cpp:1322`. Verified by two independent readers incl. a raw-bytes/UTF-16 encoding-agnostic search. The argument the count supports (the 7-frame boot tail is not family evidence) is unaffected. |
| `docs/fk7-crash-settled.md:402-417` | the 10-crash 173–201 s table, "CAMERA family" / "**ANIM family**" | Band reproduces exactly **in scope**. Two corrections: (1) **"ANIM family" is a misnomer** — `0x3495973` and `0x349596d` are the *same* function `0x3494B40`, the **tick task-graph dispatcher** (`"Ticking Group [%s] GroupLeader [%d]"`), matching its `Foreground Worker #0` thread; they are one family, not two. (2) 9 of the 10 rows are a single 2 h 55 m sitting — effective N ≈ 2 configurations. |
| `docs/fk7-crash-settled.md:717` | "worker `107d500` ×7" listed as a long-standing unrelated family | **All 7 are shutdown-path crashes** — `is_requesting_exit == true`, set-identical 7/7. The engine was tearing down. Explains the 11.8 h "survival". Remove from any game-bug denominator. |
| `docs/fk7-crash-settled.md:1170` | one-bit stop rule: "dies at T+173–201 s with fault RVA `3c5dc52` or `12c7e2d`" | Any stop rule of the form "died outside 173–201 s ⇒ not FK-7" is **unsound in the launch clock** (the window is era-B-specific and moves with staging). Restate the window in the map-load clock: era-B FK-7 deaths are **49.5–73.5 s after `Load map complete …/LVL_Tutorial`**. |
| `docs/fk7-crash-settled.md` §4.4 | "SecondsSinceStart is usable — FK-8 corrected" | Still right; upgrade to the permutation control and add the cross-class clock control (log span == reported secs to <1 s in both classes). |
| `docs/fk24-writer-probe.md:348` (row 10) | "a ~285 s observed kill latency… shorten the hold to ~T+220 s" | Same 240–295 s / median 264 restatement; add that the detector for this row should be the **fault family** (`RIP == runtime.dll base + 1`, EXECUTE), not the time. |
| `docs/next-session-prompt-s109.md:135-136` | "the integrity kill lands at ~285 s" | Same restatement. |
| `docs/s109-dump-forensics.md` §11 | "**A + B = 11 of 87 census rows (12.6 %)**" | Stale in numerator **and** denominator. UECC-only: **15 of 92 (16.3 %), 13 attributed, 2 unresolvable.** Corpus-wide: **36 of 114 (31.6 %)** including 24 family A and up to 15 family B. Also: family B has 3 further **MEASURED** members — `4BC8B969` (RIP `0x1ED96B0205D`), `6D587A6F` (`0x1B5528B205D`), and shape-only `4875FA89` — **all of which fired during S109's own §12–14 experiments**, so §11's census predates its own treatments and every "N of 87" in that document is stale by construction. |
| `docs/s109-dump-forensics.md` §11 (family B identity) | "6 crashes executing at `<64 KB-aligned base> + 0x205D` in memory that is not mapped at all" | **It is our own `catalog_store_fix.dll` at RVA `0x205d`** — `FindCatalogManagers_first`, `catalog_store_fix.cpp:204-222`. Identified by a 40-byte code-window match plus exception-time registers (`Rax = SUPERVIVE+0x8831758 == kCatMgrVtRva`, `R14 = kernel32!VirtualQuery`). It is a READ fault (`ExceptionInformation[0]==0`), not an execute fault. |
| `docs/s109-fk9-capture-durable.md` §5 | "why today's upload attempt failed is NOT established"; residual risk noted | Narrow it: the Sentry project is **alive** and the DSN key **valid** — the `/envelope/` POST returns HTTP 200. So "dead project / revoked key" is excluded and the residual risk is **higher** than stated: archiving works only while the **`/minidump/`** endpoint keeps failing, and that endpoint was not tested. Recommend enabling the `o566896.ingest.sentry.io` hosts-block named there. |
| `docs/fk8-crash-corpus.csv` (row `UECC-Windows-166396E2…`) | `fault_address = 0x80000004` | Wrong quantity — that is the **exception code** (`SINGLE_STEP`, `NumberParameters = 0`; a single-step has no accessed address). The `last-hex-in-ErrorMessage` regex captured the code. This is the **only** disagreement in 84 dumps (83/84 agree exactly), so the extractor is otherwise sound. |
| `docs/fk8-crash-corpus.csv` / `.json` (schema) | `is_stuck`, `stuck_thread_id`, `is_requesting_exit` extracted, never used | Document them as **load-bearing**: `is_stuck` = 6 GameThread hangs (4 tutorial-route); `is_requesting_exit` = 7 shutdown-path crashes == the whole `107d500` cluster. Also flag `fault_address` as unusable for chainless rows, and note `route_label()`'s bare-substring fallthrough for `tutorial-attempted`. |
| `docs/fk8-timing-analysis.md` §A.1 + the trimodality claim | "trimodal, separated by LITERAL death-free bands — not by binning choices" | **WEAKENED.** Bands reproduce; the (201,240) wall is largely the staging schedule (map-load completion moved +33.0 s July→August). In the map-load clock the comparable gap is **27.9 s, p = 0.1675** (from 57.0 s, p = 0.0010). Add the sitting-level effective N (M2 = 5 sittings, 9 from one day; M3 = 9 sittings, 7 from one 2 h block). Also fix even-N medians (M4 = 656.5 not 659; M5 = 3658.5 not 3983 — 9 % off). Remove `166396E2` and `FED1F952` from the tutorial N. |
| `docs/fk8-crash-clusters.md` | crashpad split "11 protector + 3 scan"; poison median 275 s; open question "which catalog shim?" | → **12 + 2** among the 14 unmentioned, and **16 + 6 overall — all 22 crashpad reports are self-inflicted.** Poison median is **265 s** (n=14 non-zero) / 261 (n=16), not 275. The shim is **`catalog_store_fix.dll`** — question closed. Also: distinct frame-0 sites = 32 not 31; same-boot UECC dumps listing `runtime.dll` at `0x7ffd3b400000` = 5 not 4; fault `0x1E3010020` appears in 5 of 6 `fe1746` rows not 4. |
| `docs/fk8-crashpad-class.md` (the `runtime.dll` negative) | "`runtime.dll` absent from crashpad module lists **because minidump module lists are loader-based and cannot see a manually mapped image** — a positive control for the shim blind spot" | **Mechanism REFUTED.** `runtime.dll` is present in **84/84 UECC** `ModuleListStream`s and **mapped at two bases in 81 of them**. It is loader-registered, so it is not manually mapped and **cannot control for the manual-mapping blind spot** — that inference has no positive control. The 0/22 is real and **unexplained**. |
| `docs/fk8-crashpad-class.md` (§ open question 8) | "crashpad dumps carry a zero-length thread name for all but one thread, blocking per-thread attribution" | **REFUTED.** Crashpad dumps name **73–91 threads** each (of 121–158), *more* than UECC (44–81). The crashing thread's name is empty because that thread is genuinely unnamed — a real signal, not a capture artifact. |
| `docs/fk8-crashpad-class.md` ("6 of 10 retained session logs…~60 %") | a stored ratio | **Not citable.** Three reads gave 6/10, 7/10, 8/11 within hours; `Saved\Logs` is a fixed-depth rotating ring. Replace with: "snapshot the directory, then report; the ratio is perishable." Add the `Stall.RecordDump=false` mechanism. |
| `docs/fk8-crash-timeline.md` ("only crashpad carries build provenance") | "`BuildVersion` is `UE5-CL-0` in all 91 UECC rows… only the crashpad class carries `release2.4.live-156430-shipping`" | **REFUTED as an artifact-class claim.** The build id is in **77 of 85 UECC `Loki.log`s**; the real command line is in **84/84 UECC minidumps** (user stream `0x10000`) and in **7 UECC XMLs on disk** (`CommandLineRemoved` is 84/92, not 92/92). The *conclusion* strengthens: the game binary is constant across the 42-day corpus, now on 99 artifacts. Also: "43 crashpad rows" counts `.dmp` copies; there are 22 deaths. Also: archive census is **46 dirs / 48 `.dmp`** — a `crashpad-*` glob misses `dumps/s109-sentry-20260804-1410/`. |
| `memory/supervive-crashpad-capture-runtime-family` | the runtime.dll+1 family, N=1 preserved dump | **N=24** (21 with an addressable PC + 3 degenerate). `CLAUDE.md`'s "poison RIP `0x7FF90E000001`" is **one boot's instance** of a general `<protector base>+1` signature. Add: **all 22 crashpad reports are self-inflicted (16 poison + 6 our own shim)** and the S109/S110 campaign produced no FK-7 evidence. Add the routing refutation (§5.2). |
| `memory/supervive-tutorial-crash-fk7` | "deterministic, not flaky"; "the run dies within ~1–5 min and the cause is not attributed" | For the 14 recorded crashpad tutorial deaths **the cause IS attributed and it is not FK-7**. "Deterministic" is unsupported against ≥80 staged tutorial launches in `docs/gft-ready-marker.txt` vs ~29 clean tutorial-route deaths. Add that the FK-7 stack family is the **tick task-graph dispatcher**, not animation. |
| `memory/supervive-instrument-artifact-pattern` | 5–9 confirmed instances | Add: (a) FK-8 itself — a real 30 s signature over-generalised; (b) `runtime.dll` absent from crashpad module lists; (c) the launch clock containing the operator's staging schedule; (d) `log_route` being a monotone function of survival time; (e) the `Saved\Logs` rotating ring producing three different "artifact-less %" in hours; (f) reading the wrong `ThreadContext` manufacturing "every crash is at one address"; (g) a substring `runtime` match inverting a negative. |
| `memory/supervive-passes…` / `supervive-hero-roster-blocker` (`catalog_store_fix` entries) | shim described as safe/durable | Add the defect: `FindCatalogManagers_first` scans without guarding — `SafeReadable` is consulted only **after** a vtable match — and it has killed the process **at least 11 times** at 15–45 s on menu routes. |

---

## 7. Still open, cheapest experiment first

### 7.1 The one contradiction this pass could not adjudicate

**Two verifiers re-anchored the same deaths to the tutorial map load and disagree.** §2.3/B3 reports
chain `349596d 3405f13 3691a72` at **73.1 s** (07-26) → **88.8 s** (08-05), a 15.7 s shift, and
concludes M2/M3 are "largely one mechanism at two staging phases." §4.1 reports era B in-tutorial
survival **49.5–73.5 s** vs era C **94.4–2440.6 s**, disjoint — which excludes 88.8 s.
**Cheapest resolution (minutes, offline):** both anchors are `Load map complete` lines; recompute for
the two named rows (`UECC-063228F6`, `UECC-C13252F5`) printing the exact matched log line and its
timestamp, and check whether one reader anchored on load *start* vs *complete*, or included the
`?game=` force-open echo. **Until resolved, do not cite either re-anchored number.**

### 7.2 Ranked open items

| # | question | cheapest experiment | cost |
|---|---|---|---|
| 1 | **What is the exposure denominator?** | Count `injected; base=` records in `docs/gft-ready-marker.txt` (append-mode, **80 today**) + its 7 git revisions + `docs/inject-secondaries.log` history; divide deaths by launches per era. Side result already measured: the EXE base is **per-boot, not per-process** (6 distinct bases over 80 injections), so `base` is a boot key. | ~20 min, offline |
| 2 | **Are the artifact-less terminations crashes or `Stop-Process`?** | Snapshot `Saved\Logs\Loki*.log` into the repo **now** (it rotates), then add an `operator-initiated kill at <UTC>` line before every `Stop-Process -Force` in `phase0-server.ps1` / `fk24-stage.ps1`. | ~10 min + 1 line each |
| 3 | **Does the `-InjectGapSeconds` result survive splitting by fault family?** | Classify the 3 s-row deaths the way the 30 s row was classified (`RIP & 0xFFFF`); re-fit. | ~15 min |
| 4 | **Does guarding the catalog scan remove the 15–45 s menu-route death class?** ✅ **FIXED 2026-08-05, ⚠ NOT LIVE-VERIFIED.** Both scans in `catalog_store_fix.cpp` moved onto a `ReadProcessMemory`-backed `SafeCopy` (kernel-mode probe ⇒ cannot raise). ⚠ **SEH was REJECTED, and the row's own suggestion to use it was the trap** — the packer's VECTORED handler runs before any SEH frame handler. Offline control `tools/sigbypass-mod/tests/scan_race_test.cpp`: old arm segfaults **3/3**, new arm survives **3/3** and still finds in the no-race control; cost ~1.2×. New `.text` sha256 `202a6c7d…` (was `4c9f1604…`). ⚠ `catalog_ready_fix.cpp` (2 sites) + `catalog_purchasable_fix.cpp` (1) still carry it; both banner-warned, neither injected by default. **▶ RUN 1 FLOWN 2026-08-05 (`docs/s111-scanfix-run1.md`): fixed build confirmed live via the new `scan=SAFECOPY-S111` marker stamp; functional control PASSED (CatalogManager found, map Num=1004, 1,339 entries poked, `jz=1/1`, unhook=1); NO `0x205d` fault; cleared the whole 15–45 s band. The process still died at ~106 s of family A (`RIP==accessed==0x7FFD3B400001`, low16 `0x0001`, EXECUTE) — categorically not the scan. ⚠ N=1, no base rate: DO NOT record the 11-death family as closed.** | **remaining: 3–5 more launches** against the 11-death baseline |
| 5 | **Which of A/B/C actually fires the protector kill** — the self-restoring `.text` jz-NOP, the manual-mapped images, or the PI prologue writes? | A `-NoHook` run held past 300 s. **The corpus contains no such run**, so this negative has never had a control. | one sitting |
| 6 | **Re-cut every statistic with the three new columns** — drop `is_requesting_exit` (7), split out `is_stuck` (6), drop the 2 FK-24 self-kills. | columns already in `docs/fk8-crash-corpus.csv`; no new parsing | minutes |
| 7 | **Symbolise the rest.** `python tools/strxref/strxref.py func 0x<rva>` over all ~32 frame-0 sites and ~35 chain heads. Positive control already passes. | | <10 min |
| 8 | **Test FK-24 at corpus scale.** Locate `APlayerCameraManager` by vtable RVA `0x7EC5B88` in the `Memory64` stream of all 84 UECC dumps, read `+0x420`, cross-tab against route / `is_stuck` / family. FK-24 has only ever been measured at n=4. | ~1 h |
| 9 | **Unwind the 17-row `LoadMap` assert cluster** (GameThread 17/17, 16/17 tutorial-attempted) — the force-open failure mode, never opened. ⚠ Treat as **two** messages, not one mechanism. | ~1 h |
| 10 | **Index `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`** (captured **in-world** 2026-08-05 19:13 — the first such image the project has) with strxref **standalone**; `mergedumps` will reject it against the July `merged.dump.exe` (different boot ⇒ different ImageBase). Several `func` queries currently return "body in a non-decrypted page". | ~20 s per rebuild |
| 11 | **Why does the pre-log startup interval vary 0–125 s?** | correlate against first-of-sitting (cold paging) using the existing corpus | minutes |
| 12 | **Why does `0x900000000` appear as the fault address across three unrelated clusters** (`fe24ee`, `fe1746`, `207d11d`)? A shared poison/sentinel constant is a strong lead, remarked nowhere. | strxref + dump read |
| 13 | **Can `deobfimports` be re-hosted on the 22 archived crashpad `MemoryInfoList` snapshots** (44,543 regions, full VAD map with protections, offline)? That would make packer analysis reproducible without a live launch. | unknown |
| 14 | **Is `/api/5710262/minidump/` also returning 200?** If it ever does, the archiver silently starts losing dumps. | hosts-block is the mitigation |
| 15 | **How many deaths does `_0000` really represent?** ≥1 MEASURED, ≥2 INFERRED, unbounded above. It is the only counterexample to "the crash tree only grows." | |
| 16 | **What routes a death to crashpad vs CrashReportClient?** Now *more* open (§5.2): 7 UECC rows satisfy every proposed crashpad correlate. Read the two handlers' registration order. | |

---

## 8. Method notes — what this pass itself got wrong

This project's rule is that a session documenting the instrument-artifact pattern usually commits
fresh instances of it. This one did. Named, with mechanism:

1. **★★★ The clock is the instrument.** Every mode boundary here is in `SecondsSinceStart`, the
   *launch* clock, which contains the operator's staging schedule — measurably +33.0 s July→August.
   The analysis never subtracted it. One headline gap goes from p=0.0010 to p=0.1675 when it is.
2. **★★ `log_route` is a monotone function of survival time**, so every "route X dies later than route
   Y" statement is partly definitional. The route-median ladder (26 s < 98 s < 165 s < 259 s) closely
   tracks how far each label *requires* a run to have gotten. "The menu never dies late" is a property
   of the label.
3. **★★ Effective N is far below the quoted N.** M2 = 5 sittings (9 of 13 from one day); M3 = 9
   sittings (7 of 15 from one 2 h block); era B = 9 of 10 from one 2 h 55 m sitting. Independence was
   assumed everywhere and holds nowhere.
4. **★ Contamination the project's own rules forbid.** `166396E2` and `FED1F952` — the FK-24 probe
   self-kills that `CLAUDE.md` explicitly says not to feed to census analysis — were inside the
   published tutorial N=31. Mechanism: the corpus has no "was this our own probe" column.
5. **★ Excluding the degenerate rows is a family filter, not a neutral cleanup.** All 7 non-`_0000`
   zero-byte rows are protector-family deaths that carry a parseable `PCallStack` **and** the real
   command line. "No minidump" was treated as "no evidence" and undercounted the packer census by 24 %.
6. **★ The mention statistic is self-erasing.** "14 of 22 crashpad reports are named nowhere" is only
   reproducible against the **pre-session** prose corpus (574 files / 125.2 MB, excluding `fk8-*`).
   Once this file lands, the same probe returns 22/22. **The claim is stamped with its corpus above;
   a future re-run will otherwise read as "everything was already known."**
7. **★ Three parser traps each manufactured a confident false result** before being caught: the wrong
   `ThreadContext` ("every crash is at one identical address", 22/22), a substring `runtime` match
   (flipping a 0/22 to 22/22), and the CSV `fault_address` column (which disagrees with the dump for
   every family-B row). §1.3 carries them.
8. **★ A negative I nearly recorded as a fact about the game:** `"Fatal error:"` fires on exactly the
   24 UECC Assert logs (a valid positive control **in that class**) and on **0/45** crashpad
   attachment logs — which would have read as "crashpad captures no asserts." The crashpad log copy is
   simply **cut before the assert marker is written**; the msgpack `Crash Info` field is the right
   instrument and it confirms the composition. The right conclusion needed a *different* instrument,
   not a bigger sample.
9. **Circularity flagged, not hidden:** "excluding packer families from both classes leaves the
   UECC-only tutorial median" is entailed by "all 22 crashpad are packer". It is one measurement
   presented as two.
10. **A residual is not a measurement.** "75 game-attributable" is arithmetic on what was positively
    attributed elsewhere; §3.4 removed 13 more within the same pass, and a fourth self-inflicted
    mechanism would move it again without any presented evidence changing.
11. **Cosmetic but propagating:** even-N medians were taken as the upper order statistic rather than
    the mean of the two middle values (M5 is off by 9 %).
12. **Denominator drift is real and undocumented:** the corpus grew twice mid-session (44→45 archives;
    the 45th appeared while a dimension was running), and `Saved\Logs` rotated between two reads.
13. **★★★ FOUND AFTER THE PASS CLOSED, in this pass's OWN new instrument — a positive control run
    against the wrong artifact class.** The corpus carries 11 shim-attribution columns
    (`mk_SP`, `mk_PL`, `mk_ANIM`, `mk_FO`, `mk_VTG`, `mk_GCW`, `mk_GFT`, `mk_KANIMREF`, `mk_MISS`,
    `mk_BP`, `marker_tags_found`). **All of them are 0 on all 139 rows, and they are structurally
    incapable of being anything else.** MEASURED: `Marker()` in `tools/sigbypass-mod/tutorial_launch.cpp:319`
    writes to `kMarkerPath` — a `docs/*-marker.txt` file — and **never to `Loki.log`**; a direct grep
    of a tutorial-route crash's `Loki.log` for `[SP]` / `[PL]` / `[ANIM]` / `[FO]` returns **0/0/0/0**.
    The stage-1 positive control *did* fire ({PL:25, ANIM:12, VTG:1, GCW:1}) — but it was run against
    `docs/fk24-run-nostatictest1.txt`, **a marker file**, not against a `Loki.log`. It therefore
    validated the detector's *regex* and not the detector's *applicability to its actual input*.
    ⚠ **Consequence: "no shim markers in 130 crash logs" must NEVER be read as "no shim was present."**
    Shim presence is not observable from `Loki.log` at all; the route labels (`log_route`, derived from
    map loads) are unaffected and remain valid. **Rule this yields: a positive control must be run on
    the same artifact class as the real input, or it controls for nothing.**
    **Every N in this file is stamped 2026-08-05 and must be re-derived, not cited, later.**
