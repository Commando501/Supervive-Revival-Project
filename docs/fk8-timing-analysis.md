# FK-8 Dimension 1 — CRASH TIMING

**Date:** 2026-08-05 · **Scope:** 100% offline. No launch, no injection, no backend. Crash tree opened `rb` only.
**Inputs:** `docs/fk8-crash-corpus.json` (built by `tools/crashtri/fk8_corpus.py`)
**Re-derivation:** `python tools/crashtri/fk8_timing.py [--section V|A|B|C|D]` — every number below is printed by that script, stdlib only, deterministic.

> **What this document is.** FK-8 was the false-known `docs/session-39-menu-crash.txt:82`
> — *"SecondsSinceStart: 30 (Sentry captures this at fixed point — always 30)"* — which
> closed the project's richest diagnostic corpus for 60+ sessions. A prior audit already
> falsified it (5 of 86 are 30). This document is **the mining that the false belief prevented.**
> It is not another falsification pass.

---

## 0. DENOMINATORS (state these before quoting anything)

| set | N | what it excludes |
|---|---:|---|
| UECC directories on disk | **92** | nothing — enumerated, not globbed |
| − `kind='degenerate'` (CrashContext writer never finished; 3 agreeing signals) | −8 → **84** | the 8 unfinished contexts |
| − non-degenerate `unwind_status='os-only'` (SecondsSinceStart == 0) | −7 → **77** | 7 **startup** deaths (see V1) |
| crashpad reports | 47 `.dmp` across 45 archives → **22 distinct** (`report_is_primary==1`) | 25 duplicate archive copies |
| − crashpad rows with `Seconds Since Start == 0` | −2 → **20** | 2 whose Sentry field never sampled (their logs span 8.0 s / 16.7 s) |
| **COMBINED timing-usable** | **97** | — |
| **COMBINED wall-clock-usable** (has `TimeOfCrash`, used for §C) | **106** | the 8 degenerate |

⚠ **The two sources are disjoint twice over.**
(a) *Mechanically* — 0 of 22 crashpad Crash-GUIDs have a UECC directory (control: the same key self-joins the UECC set 92/92).
(b) **In TIME** — UECC spans 2026-06-26 → 2026-08-05 (41 days, 84 deaths); **crashpad spans only 2026-08-04 → 2026-08-05** (2 days, 22 deaths), because the archiver is that young. So any statement about June/July is *UECC-only*, and 2026-08-05 is *crashpad-dominated*. Do not read a mode's source split as a mechanism.

---

## V. VALIDITY CONTROLS — these gate every number below

**V1 — the 7 dropped `os-only` rows are STARTUP deaths, not hidden late kills.**
MEASURED, from each one's own `Loki.log`: span **1.0–5.4 s**, 594–865 lines, **0 map loads**, `log_route=unknown`.
Dropping them therefore does **not** censor the late tail. (This matters: had they been late deaths with a suppressed timestamp, every "no deaths after X" claim below would be void.)

**V2 — `SecondsSinceStart` counts from PROCESS start, not from log open, and not from map load.**
`secs − log_span_s`: UECC N=77 median **−0.3 s** (range −18.5 … +124.9); crashpad N=20 median **+6.7 s** (range −5.1 … +115.1). The log's *last* timestamp tracks the crash to ~1 s in every row; the residual is **pre-log startup**, which varies 0–125 s run to run (verified by hand: `crashpad-…-tutr1-DEATH` says `Log file open, 08/05/26 02:52:02` = 95 s after its own zero point). *`INFERRED`: the variable part is the protector's unpack/decrypt + cold-vs-warm image paging. Not resolved here.*
**Operational consequence:** a live sitting timed from "I pressed launch" is on the same clock as `SecondsSinceStart`, ±0–125 s of startup slop. Timing from "map loaded" is **not**.

**V3 — CONSISTENCY POSITIVE CONTROL (this is what kills FK-8 outright).**
Within a sitting, a run cannot have lasted longer than the wall-clock gap since the previous crash.
Observed violations: **0 / 58**. Randomly re-pairing the *same* 58 durations against the *same* 58 gaps: mean **8.9** violations, **P(0 violations) < 5e-5** (20,000 permutations).
⇒ `SecondsSinceStart` is a genuine, per-run, elapsed-wall-clock measure. A "fixed capture point" field cannot produce this.

**V4 — PERIODICITY DETECTOR POSITIVE CONTROL.** Synthetic sample, N=91, true period 285 s:
σ=10 s jitter → recovers 283.0 s, global p<0.001 (**FIRES**); σ=20 s → 283.0 s, p=0.025 (**FIRES**); σ=40 s → p=0.273 (**does not fire**).
⇒ The negative in §B1 is scoped to **periods with jitter ≲20 s**. A 285 s check with ±40 s of scheduling slop would be invisible at this N. Say so whenever quoting it.

---

## A. THE DISTRIBUTION

### A.1 Histogram — 15 s bins, 0–345 s (combined, N=97; 80 of 97 fall here)

| bin (s) | n | uecc | crashpad | |
|---:|---:|---:|---:|:---|
| 0–14 | 3 | 3 | 0 | `###` |
| 15–29 | 17 | 14 | 3 | `#################` |
| 30–44 | 15 | 12 | 3 | `###############` |
| 45–59 | 9 | 8 | 1 | `#########` |
| 60–74 | 2 | 2 | 0 | `##` |
| 75–89 | 3 | 2 | 1 | `###` |
| 90–104 | 1 | 1 | 0 | `#` |
| 105–119 | 1 | 1 | 0 | `#` |
| **120–134** | **0** | 0 | 0 | |
| **135–149** | **0** | 0 | 0 | |
| 150–164 | 2 | 0 | 2 | `##` |
| 165–179 | 2 | 2 | 0 | `##` |
| 180–194 | 5 | 5 | 0 | `#####` |
| 195–209 | 4 | 4 | 0 | `####` |
| **210–224** | **0** | 0 | 0 | |
| **225–239** | **0** | 0 | 0 | |
| 240–254 | 2 | 2 | 0 | `##` |
| 255–269 | 7 | 4 | 3 | `#######` |
| 270–284 | 3 | 2 | 1 | `###` |
| 285–299 | 3 | 1 | 2 | `###` |
| **300–314** | **0** | 0 | 0 | |
| **315–329** | **0** | 0 | 0 | |
| 330–344 | 1 | 0 | 1 | `#` |

### A.2 Coarse bins, whole range

| bin (s) | n | uecc | cp | | | bin (s) | n | uecc | cp |
|---:|---:|---:|---:|:---|---|---:|---:|---:|---:|
| 0–14 | 3 | 3 | 0 | `###` | | 300–359 | 1 | 0 | 1 |
| 15–29 | 17 | 14 | 3 | `#################` | | 360–599 | 4 | 1 | 3 |
| 30–59 | 24 | 20 | 4 | `########################` | | 600–899 | 6 | 6 | 0 |
| 60–119 | 7 | 6 | 1 | `#######` | | 900–1799 | 1 | 1 | 0 |
| 120–179 | 4 | 2 | 2 | `####` | | 1800–3599 | 3 | 3 | 0 |
| 180–239 | 9 | 9 | 0 | `#########` | | ≥3600 | 3 | 3 | 0 |
| 240–299 | 15 | 9 | 6 | `###############` | | | | | |

### A.3 Every value, sorted (N=97)

```
    13     14     14     15     15     15     16     16     17     17     18     21
    22     24     24     25     25     28     29     29     30     30     30     30
    30     31     32     33     33     33     34     34     41     43     43     45
    45     45     46     49     51     53     55     56     60     71     80     84
    87     90    107    156    160    173    175    184    185    194    194    194
   195    195    196    201    240    251    258    259    259    259    263    264
   267    277    278    283    288    290    295    336    432    491    524    572
   654    659    663    677    810    834    952   2550   3216   3334   3983   8403
 42387
```

### A.4 ★ The empty bands — the strongest structural result here

Sorted, the combined N=97 contains **no death at all** in:

| empty band | width |
|---|---:|
| (107, 156) | 49 s |
| **(201, 240)** | **39 s** |
| **(295, 336)** | **41 s** |
| (336, 432) | 96 s |
| (432, 491) | 59 s |
| (491, 524) | 33 s |
| (524, 572) | 48 s |
| (572, 654) | 82 s |

The distribution below ~350 s is **cleanly trimodal**, and the bands are not artefacts of binning — they are literal gaps in the sorted list. `MEASURED`.

### A.5 Mode table

| mode | N | range | median | source | crash_type | route | dominant stack families | notes |
|---|---:|---|---:|---|---|---|---|---|
| **M0 startup** | 7 (+8 degenerate) | ~1–5 s (from log span; `secs` field reads 0) | — | uecc 7 | Crash 7 | `unknown` 7 (0 map loads) | frame0 = `ntdll`/`mdnsNSP`, 2 name `runtime` | The documented protector-kill family. **Excluded from all `secs` statistics.** |
| **M1 fast** | 51 | 13–107 | 31 | uecc 43 / cp 8 | Crash 35, Assert 16 | menu-login 30, tutorial-attempted 11, menu-lobby 8, tutorial 2 | `3ee9cf5 3ec5faf 3efb466` ×10 (assert `UnrealEngine.cpp:15551`), `fe0148 ff933e 32bcbee` ×6 (assert `MallocBinned2.cpp:1322`), `fe1746 2b8e7c5 2b8ebe8` ×4, `207d11d 29d7a26 2aef45d` ×4 | GameThread 27, RHIThread 9, FAsyncLoadingThread 5. **This is the menu mode.** |
| **M2 ~3 min** | 13 | 156–201 | 194 | uecc 11 / cp 2 | Crash 12, Assert 1 | **tutorial 12**, tutorial-attempted 1 | ANIM `3495973/349596d/34713aa …` (5), CAMERA `3c5dc52…`/`12c7e2d…` (4) | The FK-7 mode. **12 of 13 are route=tutorial.** Fault addresses `0x700`, `0x44`, `0xffff…ffff`, and 3 heap pointers. |
| **M3 ~4–5 min** | 15 | 240–295 | 264 | uecc 9 / cp 6 | Crash 11, Assert 4 | tutorial 8, tutorial-attempted 5, menu-lobby 2 | `3ee9cf5 3ec5faf 3efb466` ×3, `107d500 122642f 12204d5` ×2, rest singletons | **13 of 15 are tutorial-shaped.** No dominant family — this mode is *heterogeneous*. |
| **M4 tail** | 12 | 336–952 | 659 | uecc 8 / cp 4 | Crash 9, Assert 3 | tutorial 7, tutorial-attempted 3, menu-lobby 2 | `3ee9cf5…` ×3, `107d500…` ×2 | Same families as M1/M3 at 6–20× the uptime. |
| **M5 long** | 6 | 2550–42387 | 3983 | uecc 6 / cp 0 | Crash 6 | menu-lobby 4, tutorial 2 | `107d500 122642f 12204d5` ×3 | Idle/abandoned sessions. `42387 s` = 11.8 h. |

### A.6 ★★ Stack family does **not** determine timing (and vice versa)

The single most load-bearing negative in this analysis. Repeat-chain groups with their `secs`:

| 3-frame chain | n | `secs` values | spread |
|---|---:|---|---:|
| `3ee9cf5 3ec5faf 3efb466` (assert `UnrealEngine.cpp:15551`, "Couldn't spawn player") | 17 | 13, 30, 33, 33, 45, 49, 53, 55, 90, 107, **184, 264, 277, 288, 654, 810, 834** | **64×** |
| `107d500 122642f 12204d5` | 7 | 251, 259, 663, 952, 3216, 8403, 42387 | **169×** |
| `fe0148 ff933e 32bcbee` (assert `MallocBinned2.cpp:1322`) | 6 | 14, 14, 15, 15, 16, 28 | 2.0× |
| `fe1746 2b8e7c5 2b8ebe8` | 4 | **30, 30, 30**, 45 | 1.5× |
| `207d11d 29d7a26 2aef45d` | 4 | 18, 24, 33, 46 | 2.6× |
| `3495973 3405f13 3691a72` (ANIM) | 3 | 195, 195, 201 | 1.03× |
| `349596d 3405f13 3691a72` (ANIM) | 2 | **194, 258** | 1.33× |

⇒ **Some mechanisms are time-locked and some are not.** A timing mode is *not* a mechanism, and a mechanism does *not* imply a timing mode. Reasoning "it died at ~195 s, so it's FK-7" is **not supported**; reasoning "FK-7 always lands at 173–201 s" is **falsified** by `349596d…` at 258 s.

### A.7 Where the "always 30" belief came from — it was a real signature, over-generalised

The five `secs == 30` rows in today's 92:

| when | type | thread | chain3 | fault | route |
|---|---|---|---|---|---|
| 2026-07-01T02:15:42 | Crash | FAsyncLoadingThread | `fe1746 2b8e7c5 2b8ebe8` | `0x00000001e3010020` | menu-login |
| 2026-07-01T02:33:11 | Crash | FAsyncLoadingThread | `fe1746 2b8e7c5 2b8ebe8` | `0x00000001e3010020` | menu-login |
| 2026-07-01T07:25:05 | Crash | FAsyncLoadingThread | `fe1746 2b8e7c5 2b8ebe8` | `0x00000001e3010020` | menu-login |
| 2026-07-01T20:10:10 | Crash | RHIThread | `2976ff0 2984f45 2983c27` | `0x00007ff68a55b368` | menu-login |
| 2026-07-11T02:47:43 | Assert | GameThread | `3ee9cf5 3ec5faf 3efb466` | — | tutorial-attempted |

Three of the five are the **same crash** — same thread, same chain, same fault address, same day — a genuinely reproducible 30 s signature (its family also has a 4th member at 45 s). The other two are coincidence.
**This is the instrument-artifact pattern in its purest form:** a true fact about *one crash family on one day* was written down as a property of *the field*, and that closed the corpus for 60 sessions. `MEASURED`.

### A.8 The FK-8 audit's own bins, restated against today's 92

| bin | audit (N=86) | today (N=92, all dirs) |
|---|---:|---:|
| `== 0` | 12 | **15** |
| 13–107 | 43 | **43** (identical set) |
| 173–288 | 19 | **20** |
| 289–653 | — | **1** (572) |
| 654–952 | 6 | **7** |
| > 952 | 5 (3216/3334/3983/8403/42387) | **6** (+2550) |
| **exactly 30** | **5** | **5** |

The audit's shape holds. Its `173–288 (×19)` bin is the thing this document splits: it is **two modes with a 39 s hole in it**, not one population.

---

## B. THE FOUR LOAD-BEARING CLAIMS

### B1 — "The code-integrity kill lands at ~285 s" → **WEAKENED (and made more precise)**

`CLAUDE.md` uses this to cap live tutorial sittings at T+220–250 s.

* There **is** a mode near there, but its centre is **264 s, not 285 s**: M3 = **240–295 s, N=15, median 264**, walled by two empty bands, (201,240) and (295,336). `MEASURED`.
* Only **4 of 15** M3 members are ≥283 s. 285 s is the mode's *upper shoulder*, not its centre.
* **The mode is not one mechanism.** Composition: Crash 11 / Assert 4; routes tutorial 8, tutorial-attempted 5, menu-lobby 2; no stack family appears more than 3×; 4 of the 15 are asserts with named source lines (`UnrealEngine.cpp:15551` ×3, `MallocBinned2.cpp:1322` ×1) — asserts are *not* anti-tamper kills. So M3 cannot be "the integrity check" wholesale.
* **No periodicity.** Rayleigh test over periods 20–400 s (0.5 s grid) on the N=91 deaths ≤1000 s: best period 214.5 s, z=29.27, but the kernel-smoothed bootstrap null puts the 95th percentile of max-z at 38.1 → **global p = 0.44**. Tutorial-only (N=29): best 400.0 s, z=7.76, **p = 0.65**. `MEASURED`. Detector positive control in V4.
  ⚠ **Scope:** absent *from the timing of deaths that produced a crash artifact*, and only for jitter ≲20 s. Silent deaths (FK-25/FK-26 — force-open dies with no dump ~2 of 3 launches) are **structurally invisible to this test**. If the integrity kill is usually silent, this negative says nothing about it.
* **The actual latest-safe hold the data supports.** The widest death-free band before M3 is **(201, 240) s** across all routes, and **(201, 258) s** on the tutorial route alone.
  ⇒ **All-routes latest-safe ≈ T+235 s. Tutorial-route latest-safe ≈ T+255 s.**
  Extending a hold from 220 s → 250 s costs **zero** additional tutorial-death probability (both are 45.2%). Extending 250 s → 300 s costs **+25.8 points** (45.2% → 71.0%).
  ⇒ **CLAUDE.md's "T+220–250 s" is confirmed, and its upper bound is free — always take the 250.**
* On S111's *"285 is too pessimistic, budget ~330 s"*: **half right.** 9 of 31 tutorial deaths (**29%**) are >295 s, so 285 s is certainly not a wall. But 300–329 s is the far side of M3, not clear air *before* it — a 330 s hold passes through a mode holding **8 of 31 = 26%** of all tutorial deaths. Both statements are true of different questions; keep them apart.

### B2 — "A ~3–5 min code-integrity check kills the process if a `.text` patch is left in place" → **WEAKENED as a timing claim**

* Is there a 180–300 s population? **Yes: 24 of 97 = 25%.** `MEASURED`.
* Is it distinguishable from other modes? **Yes — and that is the problem: it is TWO modes, not one.** 180–209 s holds 9, **210–239 s holds 0**, 240–299 s holds 15. The "~3–5 min window" straddles a 39 s hole and glues together M2 (tutorial-route, 12/13, ANIM+CAMERA families, N=13) and M3 (heterogeneous, includes 4 asserts, N=15). Treating them as one population is exactly what has fuelled 60 sessions of argument.
* The operational rule ("no standing `.text` patch") rests on S43's controlled A/B, which this corpus neither supports nor contradicts — **UNTESTABLE from this corpus** as a *causal* claim, because the corpus records no patch state. Only the timing half is testable, and the timing half says "two modes, no period."

### B3 — "All 10 crashes in the FK-7 window sit in a 28-second band (173–201 s)" → **CONFIRMED in its original scope; the BAND DOES NOT GENERALISE**

* **In its stated scope (UECC, 2026-07-24 → 07-26): exactly N=10, values 173, 175, 185, 194, 194, 194, 195, 195, 196, 201 — a 28 s band. Reproduced exactly.** `MEASURED`.
* **Corpus-wide the mode is wider: 156–201 s, N=13** (a 45 s band) once the two crashpad deaths at 156 s and 160 s are admitted — and those are *2026-08-05*, i.e. a class that did not exist when the claim was written. Route composition of 150–210 s: **tutorial 12, tutorial-attempted 1**.
* **★ It is one band in time but not one mechanism, and the mechanism escapes the band.** The two FK-7 stack families across the *whole* corpus:
  * ANIM (`3495973` / `349596d` / `34713aa` first frame): 194, 195, 195, 196, 201 (all 2026-07-26) **and 258 s on 2026-08-05**.
  * CAMERA (`3c5dc52` / `12c7e2d` first frame): 173, 175, 185 (2026-07-26), 194 (2026-07-24). Never seen since.
  ⇒ The ANIM family produced a death **57 s past the band's upper edge**. "FK-7 is a 173–201 s phenomenon" is **falsified**; "FK-7 was a 173–201 s phenomenon *on 2026-07-24…26*" survives. Any stop-rule that treats "died outside 173–201 s ⇒ not FK-7" is unsound.

### B4 — "The tutorial run dies within ~1–5 min" → **CONFIRMED, with shape**

Tutorial-route deaths (combined, N=31): `60 84 160 173 175 184 185 194 194 194 195 195 196 201 258 259 259 263 267 283 290 295 336 432 491 524 572 659 677 2550 3334`

* **22 of 31 (71%) fall in 60–300 s.** Median **259 s**, q25 194, q75 336. `MEASURED`.
* Shape is **bimodal inside the "1–5 min" claim** (M2 at 156–201, M3 at 240–295) with a 57 s hole between them, plus a 6.5% early shoulder (60, 84) and a 29% tail beyond 300 s.
* Empirical CDF of tutorial deaths (see caveat below):

| hold to | deaths ≤ T | % |
|---:|---:|---:|
| 120 s | 2/31 | 6.5% |
| 175 s | 5/31 | 16.1% |
| 200 s | 13/31 | 41.9% |
| **220 s** | 14/31 | **45.2%** |
| **250 s** | 14/31 | **45.2%** |
| 285 s | 20/31 | 64.5% |
| 300 s | 22/31 | 71.0% |
| 330 s | 22/31 | 71.0% |
| 500 s | 25/31 | 80.6% |

* Route contrast (combined): `menu-login` N=30 median **26 s** (max 56 — *the menu never dies late*); `menu-lobby` N=16 median 165 s (bimodal: 8 fast, 8 ≥251 s incl. the whole idle tail); `tutorial-attempted` N=20 median 98 s; `tutorial` N=31 median 259 s.

> ⚠ **CAVEAT — this is not a survival curve.** It is the distribution of **death times among runs that died AND left an artifact**. Runs that were killed by the operator, ran clean, or died silently (FK-26) are absent. `P(die before T)` is **not** recoverable from it; `P(die before T | this run will produce a crash artifact)` is. Every % in the table above carries that conditional.

### B5 — Which of B1–B4 are testable from UECC alone?

| claim | UECC-only verdict | changes with crashpad? |
|---|---|---|
| B1 ~285 s | mode = **240–288 s, N=9** | **YES** — crashpad adds 6 (259, 263, 267, 283, 290, 295) and pushes the right edge 288→295. The `(295,336)` wall is *crashpad-defined*. |
| B2 180–300 s population | **18 of 77 = 23%** | marginal (24/97 = 25%) |
| B3 173–201 s band | **CONFIRMED, N=10** — this claim is natively UECC | **YES** — crashpad adds 156 and 160, widening the mode to 45 s |
| B4 tutorial 1–5 min | N=20, median 195 s | **YES** — crashpad adds 11 tutorial deaths, all ≥156 s, moving the median 195→259 s |

⇒ **Three of four are materially changed by the crashpad class.** Any timing claim built on `Saved\Crashes` alone before 2026-08-04 was working with the *tail* of the tutorial distribution truncated.

---

## C. TIME-OF-DAY / SESSION STRUCTURE

**Clustering** uses all **106** wall-clock-usable deaths (incl. those with unusable `secs`).

| gap threshold | sittings | size histogram |
|---:|---:|---|
| 1800 s | 53 | 1×34, 2×7, 3×5, 4×2, 5×2, 6×1, 9×1, 10×1 |
| **3600 s (adopted)** | **45** | 1×26, 2×5, 3×4, 4×4, 5×3, 6×1, 10×1, 11×1 |
| 7200 s | 37 | 1×18, 2×7, 3×3, 4×3, 5×1, 6×2, 9×1, 10×1, 17×1 |

There is **no natural threshold** — the inter-crash gap distribution is continuous (34 gaps <600 s, 19 at 600–1800 s, 8 at 1800–3600 s, 8 at 1–2 h, 26 at 2–24 h, 10 >24 h). 3600 s is a judgement call; conclusions below are stable across all three.

**45 sittings for 106 crashes = 2.36 crashes/sitting**, but the distribution is heavy-tailed: **26 sittings are singletons**, and two sittings account for 21 of the 106 — `2026-07-11 02:05` (n=10, 83 min, all `tutorial-attempted`, all the "Couldn't spawn player" assert) and `2026-08-05 06:09` (n=11, 116 min, 8 `tutorial`).

**Full sitting table** is printed by `fk8_timing.py --section C`. Highlights:

```
2026-07-11 02:05  n=10 dur= 83min  90,107,45,834,49,30,33,654,33,264   <- ONE assert family, 30..834 s
2026-07-26 06:44  n=5  dur= 40min  185,195,196,194,201                 <- the FK-7 band, one sitting
2026-07-26 09:09  n=4  dur= 30min  195,194,175,173                     <- the FK-7 band, next sitting
2026-08-05 06:09  n=11 dur=116min  17,34,524,156,259,295,258,263,267,160,283
```

**Is the FIRST crash of a sitting timed differently from later ones?**

| | N | median | ≥400 s |
|---|---:|---:|---:|
| first-of-sitting | 39 | 87 s | 11 (28%) |
| later-in-sitting | 58 | 96 s | 6 (10%) |

* **Central tendency: NO difference.** Mann-Whitney z = 0.70, **p = 0.485**.
* **Tail: YES, a difference.** First-of-sitting is ~2.8× more likely to be a long (≥400 s) survival. **Fisher exact p = 0.0305.** `MEASURED`.
* `INFERRED` explanation: the first run of a sitting is the exploratory one that gets left alone; later runs are shorter iteration cycles, and the operator kills them (killed runs leave no artifact, so they are absent). **This is a selection effect on the operator, not a property of the game** — do not read it as "the game degrades across a sitting."

**Relaunch overhead.** Between consecutive crashes in a sitting, `gap − run duration` = **median 333 s** (q25 138 s, q75 787 s, min 13 s, max 3078 s). N=58. So a crash-to-crash cycle costs ~5.5 min of non-run time, which is the real budget line for planning a multi-run sitting.

**Coverage warning.** Per-day crash counts: `06-30`×11, `07-01`×13, `07-11`×19, `07-26`×9, `08-05`×21 (19 crashpad + 2 UECC). Five days hold **73 of 106 = 69%** of the corpus. **The corpus is a record of five intense debugging days, not of typical play.**

---

## D. WHAT `SecondsSinceStart` CORRELATES WITH

Marginal Spearman ρ against `SecondsSinceStart`, UECC timing-usable N=77 (`mem_*` only exist on the 24 `Assert` rows):

| field | N | ρ | p | verdict |
|---|---:|---:|---:|---|
| `log_bytes` | 77 | **+0.874** | <1e-4 | **POSITIVE CONTROL — trivially expected.** Longer run ⇒ bigger log. Proves the correlation machinery and the duration semantics. |
| `log_lines` | 77 | +0.845 | <1e-4 | same |
| `mem_peak_used_physical` | 24 | +0.725 | 5e-4 | **CONFOUNDED** — see below |
| `mem_used_virtual` | 24 | +0.599 | 4e-3 | confounded (same split) |
| `mem_avail_physical` | 24 | +0.512 | 0.014 | confounded |
| `mem_used_physical` | 24 | **−0.446** | 0.032 | **REAL — see D.2** |
| `xml_module_count` | 77 | −0.378 | 1e-3 | **ARTEFACT** — median is 21 in *every* route; within tutorial routes ρ = **0.000** |
| `thread_count` | 77 | −0.339 | 3e-3 | **ARTEFACT** — median is 54 in *every* route; within tutorial routes ρ = −0.255, p=0.12 |
| `minidump_bytes` | 77 | −0.266 | 0.020 | artefact of the same route split (ρ = −0.097 within tutorial) |
| `log_loadmap_count` | 77 | +0.213 | 0.063 | not significant |
| `pcallstack_nframes` | 77 | +0.175 | 0.128 | not significant marginally; +0.407 (p=0.013) within tutorial routes — **WEAK, unexplained** |
| `pcallstack_ngame` | 77 | +0.151 | 0.188 | **not found** |
| `md_module_count` | 77 | −0.012 | 0.92 | **not found** |
| `num_cores` | 77 | 0.000 | 1.00 | **not found** (single machine — constant) |

**Categorical, looked for and NOT found:**
* `crash_type`: Crash N=53 median 84 s vs Assert N=24 median 51 s — **Mann-Whitney z=1.19, p=0.235. No difference.**
* `exception_code`: 52 `EXCEPTION_ACCESS_VIOLATION` (median 82 s), 24 blank (= the asserts), 1 `0x80000004`. **No signal beyond the Crash/Assert split, which itself is null.**
* `app_has_focus`: marginal medians 54 s (focus) vs 184 s (no focus) look striking, but **within route they collapse** — tutorial: 198 s focused vs 194 s unfocused. **Pure route confound. Not found.**
* `callstack_has_runtime` (the protector family): N=4 among timing-usable, median 43 s vs 80 s. **N too small; UNTESTABLE.** Note the *real* protector family lives in M0, where `secs` is unusable.
* `build_version` / `engine_version`: constant across all 92. **No build-to-build timing comparison is possible from this corpus.**

### D.2 ★ The one real mechanical correlate: a ~3.5 GB resident-memory step between 107 s and 184 s

Restricting to **one deterministic assert family** (`UnrealEngine.cpp:15551`, "Couldn't spawn player", N=17, `secs` 13–834 s) removes the route/family confound entirely. Within it:

| | N | `mem_used_physical` range |
|---|---:|---|
| `secs` < 150 s | 10 | **5290 – 6101 MB** |
| `secs` ≥ 150 s | 7 | **1892 – 2327 MB** |

**Zero overlap.** ρ = −0.638, p = 0.011. Meanwhile `mem_peak_used_physical` stays ~5.5 GB in both halves (ρ = +0.464, p = 0.064) — i.e. the peak was reached, then ~3.5 GB was *released*. `MEASURED`.

`INFERRED`: this is the large GC purge that accompanies the tutorial map load (S110 measured a purge of ~125,000 objects around it). If so, **`mem_used_physical` in a crash XML is a free, log-free discriminator for "did this run get past the big purge?"** — usable on any `Assert`-class crash.
⚠ **Scope:** `mem_*` is populated in **exactly** the 24 `CrashType=Assert` rows and is 0 in all 68 `CrashType=Crash` rows (the two sets are identical, not merely equal in size). A 0 there means *"this crash path never sampled memory"*, not *"the game used no memory"*. So this discriminator is available on ~26% of the UECC class and **0%** of the crashpad class.

---

## E. WHAT TO CHANGE, AND WHAT NOT TO

**Change:**
1. `CLAUDE.md` "hold to T+220–250 s, the kill lands at ~285 s" → **keep the hold, always take the 250** (220→250 is free: 45.2% both). Replace "~285 s" with **"a 240–295 s mode, median 264 s, walled by death-free bands at (201,240) and (295,336)"**.
2. Stop calling 180–300 s "the ~3–5 min integrity window". It is **two modes with a 39 s hole**, and the later one contains four *asserts*.
3. Stop treating "died at 173–201 s" as an FK-7 identifier. The ANIM family reappeared at **258 s**.
4. Any pre-2026-08-04 timing conclusion drawn from `Saved\Crashes` alone should be re-checked: the crashpad class changes 3 of the 4 headline claims.

**Do NOT change:**
* The "no standing `.text` patch" rule. This corpus records no patch state and cannot test it; it only says the *timing* is not periodic.
* Anything based on the mode structure being causal. **A1: stack family and timing mode are orthogonal** (one assert family spans 13–834 s).

**Open questions this analysis cannot answer:**
* What the 39 s hole at (201,240) means. A death-free band that wide in a 97-sample is unlikely by chance but this analysis did not test it against a null.
* Whether the integrity kill is silent. If it is, the periodicity negative is vacuous for it, and the right instrument is **launch-count minus artifact-count**, which nothing in this corpus records.
* Why pre-log startup varies 0–125 s (V2). It sets the slop on every live sitting clock.

---

## F. RE-DERIVATION

```bash
# rebuild the corpus (reads the crash tree rb-only; ~17 s, or 0.6 s with --no-logs)
python tools/crashtri/fk8_corpus.py

# every number in this document
python tools/crashtri/fk8_timing.py              # V, A, B, C, D
python tools/crashtri/fk8_timing.py --section B  # just the four verdicts
```

`fk8_timing.py` is stdlib-only, deterministic (all RNG seeded), read-only, and re-states its own denominators at the top of section V. If a number here disagrees with the script, **the script is right** — the corpus is live and has grown mid-session before.
