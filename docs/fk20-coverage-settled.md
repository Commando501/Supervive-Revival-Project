# FK-20 — dump coverage: the capture side is saturated, the SPEND side has never been run

**Session 133, 2026-08-20. Offline. Zero launches, zero injections, zero `.text` writes.**
Everything below is measured from artifacts already on disk with read-only tooling under
`scratchpad/s133/tools/`; evidence under `scratchpad/s133/evidence/`.

---

## 0. Headline

FK-20 was recorded as *"the standing instruction that produced 9 menu captures and 0 gameplay
captures"*, with the residual prescription *"capture hero select / drop / a live match / EoG."*

**That framing is half right and it hid the bigger defect.**

- ★ **The CAPTURE side is saturated.** Ten `dumpimage` images had accumulated on disk unmerged.
  Folding all ten in moved `.text` coverage by **+5 pages** — `merged5` 16,689 → **`merged6`
  16,694 of 30,281 pages (55.13 %)**. Measured, and the union of all 26 images independently
  equals merged6 exactly, so two instruments agree.
- ★★ **12 of the 26 images carry the entire union; the other 14 are worth ZERO pages.** One image
  (`tutorial-hero`) carries **96.5 %** of it by itself. Only **82 pages** in the whole corpus are
  unique to a single image.
- ★★★★★ **The real defect is that coverage is EARNED AND NEVER SPENT.** **31 lines across
  `CLAUDE.md` and `docs/` assert that a page is undecrypted / coverage-blocked / "100 % zero in
  every dump" for an address that is READABLE in `merged6` today.** Two of those unblock named,
  currently-open project tasks — and one of them has been readable for five days.
- ⇒ **Restate FK-20 as: _the project captures coverage and never re-grades the claims that were
  blocked on it._** The prescription is not "capture more"; it is **"drive new code, then
  re-grade"**, and the re-grade half has literally never been run.

---

## 1. The corpus, measured (`scratchpad/s133/tools/page_matrix.py`)

A `.text` page at RVA *R* is decrypted in a snapshot iff the 4096 bytes at file offset *R* are not
all zero. **Positive control, printed by the tool:** the PE section header is parsed and asserts
`.text` VRVA `0x1000` == RawPtr `0x1000` (file offset == RVA) and VSize `0x7649000`, so
`NPAGES = 30281`. Both PASS.

| | pages | % of `.text` |
|---|---:|---:|
| best single image — `dumps/tutorial-hero` | 16,112 | 53.21 % |
| union of all 26 images == `dumps/merged6.dump.exe` | **16,694** | **55.13 %** |
| dark in every image ever taken | **13,587** | 44.87 % (55.7 MB) |
| present in all 26 images | 9,757 | 32.22 % |

**Greedy incremental cover** — 12 images reach the union, 14 add nothing:

```
 1. tutorial-hero            +16112  -> 16112 (53.21%)
 2. loadout                  +  291  -> 16403 (54.17%)
 3. toggles                  +  181  -> 16584 (54.77%)
 4. s132-landstart-live      +   65  -> 16649 (54.98%)
 5. lobby-dispatch-decrypted +   13  -> 16662 (55.02%)
 6. rcb                      +   13  -> 16675 (55.07%)
 7. heromastery              +    6  -> 16681 (55.09%)
 8. vmbuild                  +    5  -> 16686 (55.10%)
 9. claimflow-AFTER          +    3  -> 16689 (55.11%)
10. s131-rideable-live       +    2  -> 16691 (55.12%)
11. crash-20260819-200129    +    2  -> 16693 (55.13%)
12. s132-dismount-live       +    1  -> 16694 (55.13%)
13..26 (menu, store, roster, missions, accountpass, s129-poolgate,
        s131-droppod-live, claimflow-BEFORE, 6x crash-*)   +0 each
```

⚠⚠ **Greedy order is order-dependent and is NOT a per-state value.** The order-independent
measure is **leave-one-out**: pages lost from the union if an image were deleted. Only **8** of 26
images are irreplaceable at all, for **82 pages** between them —
`toggles 42 · rcb 13 · lobby-dispatch-decrypted 10 · vmbuild 5 · heromastery 4 ·
s132-landstart-live 4 · claimflow-AFTER 3 · s132-dismount-live 1`.

★ **An image's own coverage % does not predict its contribution.** `toggles` is the
*lowest*-coverage non-outlier image on disk (50.61 %) and holds the *most* unique pages (42).
`missions`/`roster`/`store`/`menu` sit at 52 % and are each worth **0**. **What pays is being a
DIFFERENT state, not being a bigger snapshot.**

---

## 2. Where the dark 44.87 % actually is — and why most of it is unreachable in principle

Two independent attributions agree, and the module-level one supersedes my first cut.

**2a. Coarse zone split** (`dark_shape.py`) — `.text` has three regions with different character:

| zone | RVA | pages | dark | dark MB | share of dark |
|---|---|---:|---:|---:|---:|
| **A** pre-engine | `0x1000`–`0xFFFFFF` | 4,095 | **3,622 (88.4 %)** | 14.8 | 26.7 % |
| **B** engine + core game | `0x1000000`–`0x4CFFFFF` | 15,616 | 3,977 (25.5 %) | 16.3 | 29.3 % |
| **C** Loki + Angelscript + tail | `0x4D00000`–`0x7649FFF` | 10,570 | 5,988 (56.7 %) | 24.5 | 44.1 % |

⚠ **My first reading — "zone C is the FK-20 target" — OVER-ATTRIBUTES.** Zone C also contains
MeshModelingTools (`0x4CE7000`), PCG (`0x668D000`), ControlRig/Sequencer (`0x5D1D000`), OpenEXR
(`0x6D83000`), libwebm (`0x73C6000`) and the ICU/OpenSSL/Oodle third-party tail. A per-module
attribution is required and was built.

**2b. Module attribution [M page counts, I bucketing]** — module segmentation from 5,060 class
vtables expanded out of `.rdata`, mean per-page dominant-module purity **0.991**:

| dark pg | %dark | share | bucket |
|---:|---:|---:|---|
| **3,613** | 92.2 % | 26.6 % | **U1** `RVA<0xF7E000` — **UE's own Chaos ISPC kernels** (**25 fns/MB** vs 6,126 next door), libpas, libpng, zlib, NVAPI |
| **2,357** | 66.3 % | 17.3 % | **R0 editor/authoring-only** — MeshModelingTools, ModelingComponents, GeometryScripting, **PCG (673)**, Sequencer, MovieRenderPipeline |
| 1,873 | 43.0 % | 13.8 % | **U2** non-UObject engine C++ — Chaos, RHI/D3D, Renderer, Slate internals, the AngelScript VM |
| 1,845 | 63.4 % | 13.6 % | **U3** third-party tail — **ICU 64** (2,743 RTTI slots), OpenEXR, SubstanceAir, crashpad, OpenSSL, Oodle, libwebm |
| 1,416 | 39.4 % | 10.4 % | **R1** runtime, not on this route — BuildPatchServices, media, CEF, HMD, ControlRig, LevelSequence |
| **1,397** | 27.5 % | **10.3 %** | **R2 gameplay / net / AI — the only bucket a real match can reach.** Loki 412 · Niagara 398 · AIModule 89 · OnlineSubsystemUtils 76 · IrisCore 74 · GameplayAbilities 66 · ReplicationGraph 26 · NavigationSystem 21 |
| 1,091 | 15.9 % | 8.0 % | **R3** shared engine/UI/core — Engine 803, Slate 63, CommonUI 37, UMG 25 |

★★★★★ **67.91 % of the dark set (9,231 of 13,592 pages = 36.06 MiB) is U1+R0+U3+R1: SIMD ISA
variants the CPU will never select, editor modules with no entry point in a packaged client, and
third-party libraries. NO game state decrypts any of it — not hero select, not a live match, not
end-of-game.** The reachable ceiling is R2 plus a share of R3/U2, **4,361 pages = 32.09 % of dark
= 17.04 MiB**, and that assumes a match executes *every line* of every gameplay/net/AI module.
⚠⚠ **An earlier draft said "73.4 %, 9,984 pages, 39.0 MiB" — an ARITHMETIC ERROR that flattered the
conclusion, caught by adversarial verification.** `3613+2357+1845+1416 = 9231`, and the two shares as
first stated summed to **105.54 %**, which is impossible. **9,231 + 4,361 = 13,592 exactly.**
★ *Two complementary shares that fail to sum to 100 % is a free self-check — run it.*

⚠⚠ **QUOTE THE UNIT.** In *functions* rather than pages the split inverts: U1 is 26.6 % of dark
pages but **0.4 %** of dark functions (giant kernels, almost no unwind records), while R2 is 10.3 %
of pages but **16.7 %** of functions.

★★ **U1 ("Region A", `0x1000`–`0xB89000`, 2,808 dark pages = 20.7 % of all dark) IS UE CODE, and it
is NAMED [M].** A draft called it *"not UE code at all"* with *"no ISPC-specific string found"*; both
are false from the same bytes. **`ispc` occurs 16× ASCII in `merged6`**, in four byte-identical copies
of one string block (`.rdata 0x7808790 / 0x7808A30 / 0x7808E60 / 0x7809190`) reading
`Runtime/Experimental/Chaos/Private/Chaos/PerParticlePBDCollisionConstraint.ispc:331:2: Assertion
failed:` — verified here at `0x78087B9` — and Region A's own lit code `lea`s to them. ⇒ **it is
Chaos's ISPC-compiled collision kernels, multi-ISA-target, of which the runtime selects one copy**;
the rest is unreachable *on this CPU by construction*, not by game state. Grade **[M]**, not [I].
⚠ The false null came from `strxref.idx`, which was built on `dumps/s129-poolgate` — an image that
lights only **50 of Region A's 144** lit pages, with all five ISPC-referencing sites among the dark
ones. **A string index built on ONE image is a floor, and "verified exhaustively" against it is not.**

**2c. The one concentrated, reachable target: the Angelscript AOT layer.**
`0x59128B0`–`0x5A7F070` — **239 of 366 pages dark (65.3 %)**, and **2,058 of its 3,760
`RUNTIME_FUNCTION` slots have never decrypted in 76 crash minidumps (54.7 %)**. Measured twice by
different instruments. That band is the drop / pod / respawn / bot layer FK-1 identified, and it is
where a real match would actually pay.

**2d. The corollary that should change daily practice.** Offline RE on this image is **not "45 %
blind"**. In *functions*: **~9.4 % blind on shared engine/UI/core, 20.9 % blind on gameplay/net/AI,
54.7 % blind on Angelscript.** ★ **Quote the per-subsystem number; the image-wide 45 % is dominated
by code no state can reach and understates the blindness where it matters.**

**2e. Shape.** 13,587 dark pages in **2,323 runs, mean 5.8 pages**; 1,016 are isolated single pages,
but **73.3 % of dark pages have neither neighbour decrypted**, so the set is regional rather than
branch-scattered. Largest run `0x50D000`–`0x8A0FFF`, 916 pages / 3.6 MB — and it is in U1.
★ **12,831 dark pages (94.4 %) carry no reflected UFunction at all**; only 109 carry a Loki/GAS
impl. **The reflected-ANCHOR ceiling image-wide is ≤ 394 dark pages = 1.30 % of `.text`** (= 2.90 %
of the DARK set — ⚠ an earlier draft of this line quoted 2.9 % against the wrong denominator).
⚠⚠ **BUT DO NOT READ THAT AS A CEILING ON WHAT DRIVING REFLECTED CODE DECRYPTS — that is a category
error, refuted by this project's own last four captures.** A reflected call decrypts its
**non-reflected callees**, and measured against `merged2`, **≈86 % of every page decrypted since S121
carries no reflected function at all**: `s131-droppod-live` 43 new pages / 6 with an impl ·
`s131-rideable-live` 45 / 7 · `s132-dismount-live` 44 / 6 · `s132-landstart-live` 48 / 8 ·
`merged6 ∖ merged2` 56 / 8. **394 bounds the pages that HOST a reflected impl, nothing more.**

---

## 2f. The exchange rate, measured

Partitioning the 26 images by era: MENU-era (13 images) union **16,476** pages · TUTORIAL-WORLD (6)
**16,255** · CRASH-era (7) **15,818** · all 26 **16,694**.

★★ **`tutorial-world \ menu` = 216 pages = 0.71 percentage points of `.text`. That is the ENTIRE
measured `.text` value of everything from S107 to S132** — `LVL_Tutorial` loaded, hero spawned,
possessed and walking with real locomotion, the `GoToPhase` ladder driven to `EGP_Combat`, navmesh
generation, a drop pod spawned and flying at 20,000 uu/s, the rideable wall driven twice, the hero
dismounted and standing on real terrain. Module split of those 216: Loki 58 · unattributed 41 ·
NavigationSystem 41 · Sentry 19 · Engine 10 · Niagara 9 · GameplayAbilities 7. The whole programme
bought **+24 Angelscript pages** and left 239 dark.

⚠ And the MENU family contributes *more* unique pages than the tutorial family (`menu \ tutorial`
= 437 vs 216) — the opposite of the standing assumption that the tutorial world is the high-yield
state.

**An independent instrument saturates the same way:** greedy over the 76 crash-minidump function
tables gives best single dump 370,359 functions (70.62 %) against a union of 382,704 (72.97 %), and
**64 of 76 dumps contribute ZERO new functions.**

---

## 3. Two candidate sources of coverage, both FORECLOSED — measured, with positive controls

### 3.1 Sentry crashpad minidumps: **0 bytes of the game image**, n = 396, mechanism named [M]
`dumps/crashpad-*/reports/*.dmp` (~41 MB each, ~30 on disk). Stream census: `SystemInfo, MiscInfo,
ThreadList, ProcessVmCounters, Exception, ModuleList, UnloadedModuleList, 0x43500001,
MemoryInfoList, HandleData, MemoryList`. **No `Memory64List`.** `MemoryList` = 695 descriptors /
38.7 MB, of which **0 bytes** fall inside the SUPERVIVE image; the content is 4 × 8 MB thread
stacks plus ~690 small ones.

★ **Census over ALL 396 `.dmp` files on disk (124 distinct crashes, 10.57 GiB):** 10.49 GiB of
captured memory, **96.6 % of it thread stacks, 0 bytes inside the game image**, 280,685 ranges
scanned, `Memory64ListStream` present in **0 / 394**.
**DISCRIMINATING control:** the same parse finds **66,980 B of in-module bytes — 170 B per dump, all
`ntdll.dll` — in 394/394**. The attribution path is exercised and returns non-zero for another
module in the same pass, so the game-image zero is a fact about the dumps.
★★ **AND THE MECHANISM IS NAMED [M]: the minidump header `Flags = 0x0` = `MiniDumpNormal`.** No
`MiniDumpWithFullMemory`, no `MiniDumpWithIndirectlyReferencedMemory`. **Sentry's handler will never
capture image bytes until that configuration changes** — this is not a property of the crash.

### 3.2 UE crash minidumps (`Saved\Crashes\UECC-*`): **`.rdata` only** [M]
108 dirs, 98 non-empty, parsed with `scratchpad/s133/tools/uecc_sections.py`. Every one *does*
carry image memory — but by section it is:

```
.rdata   520,866,532 bytes   (5,314,962 per dump, essentially constant)
.text         13,824 bytes   (across all 98 dumps, touching 33 pages)
.reloc         4,096 bytes
```

⇒ **worthless for `.text` coverage.** Positive control: the same parser attributes 5.3 MB to
`SUPERVIVE-Win64-Shipping.exe`, 313 KB to `runtime.dll` and 1.8 KB to `ntdll.dll` in a single
dump, so it can see image bytes when they exist.

★ **Two by-products worth keeping, both new:**
- **UECC minidumps LIST `runtime.dll` in their ModuleList** (217–222 modules) and capture
  **1.57 MB** of it. `CLAUDE.md` records *"[M] `runtime.dll` has NO module entry in ANY crashpad
  minidump (0 of 14)"* — that is true of the **Sentry crashpad** corpus and **does not
  generalise**. The UECC corpus gives `runtime.dll`'s base across ~98 process lifetimes offline,
  which is directly the instrument FK-31's per-boot kill-address claim needs.
- UECC stream 13 is a **per-function decryption oracle** (see §4).

### 3.3 `crashwatch` images add essentially nothing [M]
The 7 `dumps/crash-*/` images were captured by `usmapdump crashwatch` (suspend at crash, dump
before death). Union of those 7 = 15,818 pages; union of the 19 live-state images = 16,692.
**The crashwatch images hold exactly 2 pages the live images lack.**
★ **And the null is interpretable because the same instrument resolves 876 pages the other way**
(`pages ONLY in non-crash images = 876`, `pages ONLY in crash images = 2`). So this is a controlled
negative, not a silent instrument. ⚠ Neither of those 2 pages (`0x44FB000`, `0x4503000`) is uniquely
held — 5 of the 7 crash images carry both; a greedy/marginal table makes the alphabetically-first one
look load-bearing and it is not.
⇒ **Whatever runs during a death is not reaching a `crashwatch` snapshot, and "a crash-era image
holds more decrypted `.text`" is refuted** — the best crash image is 15,695 pages (51.83 %), *below*
the best healthy single image (`tutorial-hero`, 16,112 / 53.21 %).

---

## 4. The function-table oracle, and one claim it REFUTES about itself

`tools/strxref/mdpdata.py` reads MINIDUMP stream 13 — the packer's lazily-materialised
`RUNTIME_FUNCTION` table. A slot with `EndAddress == BeginAddress + 1` is a **placeholder** for a
function the packer had not materialised in that process. 76 UECC dumps carry a usable table;
every table has exactly **524,439 slots**.

| | |
|---|---|
| real (materialised) functions, union of 76 lifetimes | **382,704** |
| real functions, per dump | min 155,722 · median 352,395 · max 370,359 |
| functions materialised in ≥1 lifetime whose entry page is **dark in all 26 images** | **26,054** |

⚠⚠ **A tempting reading is REFUTED by its own control.** The placeholders carry a
`BeginAddress`, so it looks as though the table hands us the entry RVA of *every* function in the
image — a complete function map of a packed binary, free. **It does not:** the union of distinct
`BeginAddress` values across the 76 dumps is **737,978**, which exceeds the 524,439 slots, so
**placeholder begin addresses are not stable across processes and must not be treated as function
starts.** Only the *real* entries are sound — which is exactly the subset `pdataunion.py` already
keeps.

⚠⚠ **And the 26,054 is not a missed gameplay state.** **18,964 of them (72.8 %) are
materialised in ALL 76 lifetimes** — and 18,128 of those (95.6 %) live in the single 4 MB window
`0xC00000`–`0xFFFFFF`, i.e. inside dark **zone A**. They are universal startup-era code, not
gameplay. The hypothesis that they are the crash/unwind path is **UNTESTED, not confirmed**: the
instrument that would test it (the 7 `crashwatch` images) rescues **0** of them (§3.3).

★ **A quantified confound worth carrying:** 567,802 function entries sit on pages our images
decrypted, but only 356,650 of those were ever materialised. **At most 63 % of the functions on a
"decrypted" page actually ran.** Page coverage systematically overstates code coverage — so
"55.13 %" is a ceiling, not an estimate.

---

## 4b. ★★★★★ The decisive number: 125 crash lifetimes only ever reached 55.27 %

A better instrument than the function table exists in the same files and nobody had read it. The
`MemoryInfoListStream` is the full `VirtualQueryEx` map at death, and on this build a `.text` page is
`PAGE_NOACCESS` if never decrypted and `PAGE_EXECUTE_READ` if decrypted.

**Controls, all 394/394:** `.text` regions tile `[base+0x1000, +0x764A000)` exactly · page count is
exactly 30,281 · `.rdata` ≥ 99 % readable. **And only TWO protection values ever appear over
`.text`: `NOACCESS` 6,757,306 + `EXECUTE_READ` 5,173,408 = 11,930,714 = 394 × 30,281 page-observations
exactly** — an offline replication of S121's live finding.

| | pages | % |
|---|---:|---:|
| decrypted per distinct crash | min 9,759 · median 15,433 · max 16,214 | |
| **union over all 125 crash lifetimes** | **16,434** | 54.27 % |
| our 26-image union (`merged6`) | 16,694 | 55.13 % |
| **the two combined — the CEILING of everything ever observed** | **16,735** | **55.27 %** |

⚠⚠ **QUOTE THE UNIT ON 55.27 %: it is "pages KNOWN TO HAVE BEEN DECRYPTED at some moment", not
"pages we hold BYTES for".** The 41 crash-only pages exist **nowhere as bytes** — minidump memory
inside the game image is **0 in 124/124**, no report has a `Memory64ListStream`, and the shadow-exe
and `runtime.dll` allocations carry 0 captured bytes too. **For offline RE the byte figure is
`merged6`'s 16,694 = 55.13 %.**

★★★★★ **125 crash lifetimes plus 26 captures, across every state this project has ever reached,
total 55.27 % of `.text`. The dark 45 % is dark because THE GAME NEVER RAN IT** — not because we
failed to snapshot it. Only **41 pages** were ever decrypted at a crash and are zero in `merged6`
(167,936 B; 39 of the 41 coexist in one ordinary crash, and one `dumpimage` during a normal
tutorial-era sitting should capture them).

★★ **CROSS-INSTRUMENT VALIDATION, and it is the strongest control in this document.** Pairing each
`dumpimage` snapshot against a crash minidump from the *same* process ImageBase compares byte content
against page protections — two completely different measurements of "is this page decrypted":

```
game base            dumpimage non-zero pages    minidump EXECUTE_READ pages
0x7FF630E90000               15,382                      15,382
0x7FF7A5A20000               15,695                      15,695
0x7FF7C4050000               15,461                      15,461
0x7FF7B86D0000       15,467 / 15,382             15,467 / 15,384  (+2)
0x7FF7BFF50000        9,759 / 15,350              9,759 / 15,352  (+2)
```
**5 exact equalities, 2 at +2, never fewer** — and +2 is the direction monotone decryption predicts
(the minidump is taken later than the snapshot). The page-bitmap method used throughout this document
is therefore validated against an independent instrument.

⚠⚠ **A pre-registered prediction on disk LOOKS refuted here, and the grade is NOT supportable —
this is the document's own near-miss.** `CRASHWATCH-INFO.txt` predicts *"~18,900 non-zero `.text`
pages"*, and the 7 crash-era images read **9,759–15,695**. But (a) **those are two different
instruments** — 18,911/18,980 in `strxref-state-coverage.md` §5 and `fk3-fk4-settled.md` §2.3 convert
crash-minidump *unwind-table entries* to the pages they span (**pages-NAMED**), while 9,759–15,695 is
**pages-NON-ZERO**, and `fk18-fk19` §4 already measures the gap at **3,117 pages named-but-byteless**;
(b) the "best crash image" (`crash-20260820-142858`) is the **T+141 s FK-31 staging death that the
repo already flags as UNMATCHED and explicitly does not score**; (c) **no matched control exists.**
⇒ **Grade it [I], not [M].** The two captures that could partly score it — `crash-20260819-181559`
(T+4826 s, 15,382 pages) and `crash-20260819-200129` (T+3322 s, 15,467) — are long-lived processes
free of the short-lifetime confound, and they do point the same way.
⚠ **And "crash-era capture is worth 2 pages" is CONFOUNDED WITH ROUTE:** 6 of the 7 crash images are
tutorial-route processes, i.e. differenced against an already-saturated tutorial corpus. **No
crashwatch capture exists from a driven MENU session**, so the 2 is a statement about
crash-on-the-tutorial-route, not about crash-era capture in general.

★ **`merged6` is a strict superset of every `.text`-bearing artifact on disk** — 32 sources diffed at
page granularity, **ADDS = 0**. That includes `tools/re/.exec_surface_cache/text_union.bin`
(124,030,976 B, exactly `.text` size, never merged and never examined: 16,604 pages, adds 0).

---

## 5. ★★★★★ The real finding: 31 coverage-blindness claims are stale

`scratchpad/s133/tools/regrade_blocked.py` finds every line in `CLAUDE.md` + `docs/*.md` that
asserts coverage blindness *and* names a `.text` RVA ≥ 16 MB, then grades that RVA against
`merged6`. **Positive control printed by the tool:** it must return `LIT` for `ProcessInternal
0x13454A0` and `DARK` for `TryJoinQueue 0x5875E90` — both PASS.

```
lines asserting coverage-blindness with a >=16MB .text RVA : 47
  now STALE (>=1 named address is READABLE in merged6)     : 31
  still accurate (all named addresses still dark)          : 16
```

Full list: `scratchpad/s133/evidence/dark_cited_functions.txt`. The two that matter most:

### 5.1 ★★★★★ `0x1F8CFC0` — and the bigger error underneath it

`docs/fk5-battle-gate-settled.md:664` states, graded `[M]`:
> `0x1F8CFC0` is an all-zero page, so **the packet format is unreadable offline**

and its §6.4 plan builds a verbatim-echo + hexdump responder specifically to recover the format
empirically. The same claim is repeated at `fk5-battle-gate-settled.md:58,180,190,444,915`,
`fk5-latency-subsystem-re.md:278,497`, `coverage-audit-s101.md:185,677`,
`ignorance-map-s101.md:377,2270`.

**(a) `0x1F8CFC0` is now readable [M].** Dark in `merged2`, LIT in `merged6`. Real prologue
`48 89 5c 24 20 55 56 57 48 81 ec 90 00 00 00 …`.
**Attribution [M]:** dark in every image dated before 2026-08-15, lit in **all 8** images dated
2026-08-15 or later (`crash-20260815-200514`, `s129-poolgate`, all S131/S132), while its caller
`ULatencyMeasurer::PingHost 0x57CB950` is lit in 25/26. **2026-08-15 is S121 — the session that
fixed the regions payload and created the first `ULatencyMeasurer` this project has ever had.**
Driving that path decrypted this function, the images were captured, and nothing re-graded the doc.

**(b) ⚠⚠ BUT THE CLAIM WAS ALREADY FALSE WHEN IT WAS WRITTEN, AND NOT BECAUSE OF COVERAGE.**
`0x1F8CFC0` is a ~300-byte **wrapper**. Disassembled, it reads `[Ping] StackSize` from the ini
(wide literals `"StackSize"` `0x79C6C58` / `"Ping"` `0x79C6C70`), clamps it to
`[0x8000, 0x200000]`, builds the thread name from the ANSI literal **`"LokiPing"` at `0x79C6E80`**
— exactly the string FK-5 flagged `[SI]` — allocates an 0x80-byte object and tail-calls the real
worker at **`0x1F8BE90`**.

**`0x1F8BE90` is LIT in `dumps/merged.dump.exe`, in `merged2`, in `menu`, in `tutorial-hero` — in
every image this project has ever taken.** [M]

⇒ **The packet-building code was never dark. FK-5 pinned an `[M]` coverage-blindness verdict to a
thread-spawning wrapper one call above the code it was reasoning about.** That is the same failure
already in the register at `fk22-dropphase-reachability.md:675` —
*"`ULokiPreloadComponent::OnRoundPhaseChanged` was filed COVERAGE-BLOCKED on a zero **thunk**, while
the impl was decrypted"* — recommitted in a different file.
★ **Rule: before recording "this page is dark, therefore X is unreadable", check the callee.** A
zero wrapper says nothing about the function it calls.

⇒ **CLAUDE.md's open task — *"Next task: a UDP echo responder on `PingHost:PingPort`"* — does not
need to discover the format from the first datagram. It can be read offline today from `0x1F8BE90`
and its siblings `0x1F8BB50` / `0x1F8B870` / `0x1F8B4F0`, all LIT.** Not done here; it is FK-5 work,
and it is now unblocked.

### 5.2 ★★ `0x5456C80` — `GetLandingTeleportLocation` thunk — IS READABLE
`fk22-dropphase-reachability.md:598,662` file it **COVERAGE-BLOCKED**, thunk "zero in 18/18".
Dark in `merged2`, LIT from `s131-rideable-live` onward. Likewise **page `0x5456000` — the whole
`AuthPlayer*` family that FK-22 §2.5 filed as 16 COVERAGE-BLOCKED `(class,func)` keys — now reads
3,860 / 4,096 nonzero.** `CLAUDE.md` already says re-running that grading is *"free, offline and
unstarted"*; it is now also **unblocked**.

### 5.3 Claims that were stale BEFORE this session
`0x56CE5F0` (`TryUpdateAbilitySystem` impl, `fk3-fk4-settled.md:529` "all-zero page") and
`0x5302DE0` (`PollForFeatureTogglesReady`, :527) are **lit in `merged2` too**. So ~29 of the 31 did
not need today's merge at all — they only needed someone to look. **That is the FK-20 defect in its
purest form.**

### 5.4 Still genuinely dark, and each names its own experiment
`0x5875E90` `TryJoinQueue` (page `0x5875000`) · `0x5A6AC40` `ULokiRespawnComponent::Respawn` ·
`0x560EE70` BR phase-4 body · `0x52FEF50` `FeatureTogglesReadyOrChanged` · `0x5442960`
`ULokiPreloadComponent::OnRoundPhaseChanged` thunk · `0x55A34E0` · 30 more.

★ **`TryJoinQueue` is the most-cited dark address in the repo (11 citations) and its experiment is
already written down and already cheap.** `ignorance-map-s101.md:2270`: *"`bots` is already served
and is not in the native `IsSpecialQueue` set, so **BOTS → FIND MATCH** enters the real
`TryJoinQueue` today."* S122 then made FIND MATCH work end to end (`setTargetQueues` handler +
`AGS_QUEUE_UNLOCK`). **One menu launch, no injection, no staging, no crash risk.**

---

## 6. What FK-20's own entry gets wrong

- ⚠ Its ★ row says *"The two **cannot** be merged (different ImageBase — FK-18/FK-19)"*.
  **Refuted by S121** (`docs/fk18-fk19-multistate-merge-settled.md`): `.text` carries 0 of
  1,403,750 base relocations, `mergedumps` has been ImageBase-agnostic since 2026-08-14, and
  `merged6` contains `tutorial-hero` (base `0x7FF6505C0000`) merged with a seed at
  `0x7FF6AF000000`.
- ⚠ Its ★ row states a *"Standing rule: run every `.rdata` presence/absence claim against
  `dumps/tutorial-hero/…`, never `merged.dump.exe` alone"*, justified by "100.0 % readable vs
  63.1 %". **Those are two different instruments** (readable-byte vs non-zero-byte) and `CLAUDE.md`
  already carries the retraction. The rule should be deleted, not qualified.
- ⚠ Its **Belief** row quotes `configs/capture-dumps.ps1:24-25` as saying the tutorial flow
  *"isn't playable yet"*. **That text no longer exists** — the header was rewritten in S121 and now
  reads *"CAPTURE THE TUTORIAL WORLD — it is the highest-yield state reachable today."*

---

## 7. Method notes earned here

- ★★ **An analysis filter can be degenerate by construction.** A first cut of the doc-address audit
  filtered cited addresses through membership in `pdata_union.csv`'s `BeginAddress` set, and
  reported *"1 dark of 520"*. That set is built **only from materialised functions**, so the filter
  could admit nothing dark. **Caught by its own positive control:** the known-dark `0x5A6AC40` came
  back `is-a-function=False` and was silently dropped. Rebuilt with a decryption-independent
  filter, the answer is **36 of 1,111**.
- ★★ **A merge manifest that names donors by BASENAME cannot be audited.** `merged2.dump.exe.txt`
  lists `SUPERVIVE-Win64-Shipping.dump.exe` twelve times. There is no way to tell from any manifest
  which state dirs are already folded in — which is precisely how ten images sat unmerged for six
  days. Print the parent directory.
- ★ **Coverage % of a snapshot does not predict its value** (§1). Rank captures by *state novelty*,
  never by their own percentage.
- ★ **Page coverage overstates code coverage by up to ~37 %** (§4). Quote the unit.

---

## 8. What to actually do — ranked, and the top three are zero-risk

Anchor counts are [M] from a join of the 16,277-record UFunction census against the merged6 page
bitmap; page estimates are [I], calibrated on the only three per-driver measurements that exist
(bare 33-type lobby sweep = 21 unique pages · one whole new menu session = 80 · first tutorial
world = 165) → roughly **0.6–3 new pages per anchor function driven**.
⚠ **The reflected-anchor page ceiling for drivers 1–12 combined is 29 dark pages** (exact
enumeration: 57 impls / 23 dark pages; most generous superset 73 / 29). **The estimates above exceed
that on purpose — most of what a driver decrypts is its non-reflected callees**, which is measured
(§2e) and is where the real yield is. Do not read the estimates as reflected-anchor counts.

| # | driver | dark anchors [M] | est. new pages [I] | cost | risk |
|---|---|---|---:|---|---|
| **1** | **Party / queue / custom-game ACTION sweep.** Unlock all 10 queues (`AGS_QUEUE_UNLOCK`, `AGS_QUEUE_IDS`), then click every tile, FIND MATCH, READY, FILL, invites, and create/configure/start a CUSTOM GAME | **`UPartyManager` 20 dark impls at `0x5873280`–`0x5879EE0`** — including **`TryJoinQueue 0x5875E90`** — ⚠ that RVA span covers 7 pages of which only **4 are dark** | 25–60 | `ags` restart + operator clicks. **No relaunch, no injection** | ~0 — the A-B-A was already flown in S122 |
| **2** | **FULL-PAYLOAD `/lobby` notif sweep.** S117 pushed bare `{"type":X}` frames, which **cannot** reach a per-type deserializer; push each of the 33 with a plausible field set | 33 case bodies + 33 `JsonObjectStringToUStruct` import paths | 20–45 | one admin POST loop, ~2 min | ~0 |
| **3** | **Settings + renderer permutation sweep.** Every quality preset, resolution, fullscreen mode, vsync/AA/shadows, APPLY; language; voice reset | the non-reflected RHI/shader-permutation path, which the census cannot see and which is a large share of the 12,831 non-reflected dark pages | 20–80 (wide) | pure operator UI | ~0 |
| 4 | Serve `/referral/player/{id}` + `/points` — the last two unserved endpoints with real UI | a screen never built in any dumped process | 10–30 | one Go handler | low |
| 5 | Friends flow both directions; lobby chat; titles/callsign; store BUY + STORAGE | `USocialManager` 3 · `UChatManager` 7 · `UPersonalizationManager` 2 · `UStorefrontManager` 2 | 20–60 total | clicks | ~0 |
| 6 | `[ConsoleVariables]` in the user `Engine.ini` — same file and mechanism FK-11 proved for `[Core.Log]` | non-reflected RHI/audio; census-invisible | unknown | ini edit | ~0. ⚠ **[I] — never flown. Prove it with one cvar + a `LogConfig` receipt first** |
| 7 | Replay / `DemoNetDriver` (`ULokiBlueprintLibrary` has **7** dark replay impls, ⚠ all on ONE page `0x563E000`, so the *reflected-anchor* yield is **1 page** and the 100+ belongs to the non-reflected net stack — state them separately; `demorec`/`demoplay` are exec verbs and FK-13 shipped a working `ExecuteConsoleCommand` + real `UCheatManager`) | replay + the **entire net-serialization stack**, which has never run in this project | 100+ | needs the S55 primitive ⇒ a shim | **MEDIUM** — use the S112 heap-`Func`-swap form (0/16 at 600 s), never a standing `.text` patch |
| 8 | More tutorial staging with the existing S131/S132 arms | already-driven code | **≈0** — the whole tutorial programme is 216 pages [M] | 1 launch | **HIGH** (FK-31 ~25 % staging death) |
| 9 | Combat / abilities / drop phase | 109 Loki+GAS + up to 239 Angelscript dark pages | 150–350 | **BLOCKED** by FK-1's four empty server-authority stubs | — |

★ **`TryJoinQueue` is the most-cited dark address in the repo (11 citations) and it sits inside
driver #1.** `ignorance-map-s101.md:2270` already wrote the experiment down: *"`bots` is already
served and is not in the native `IsSpecialQueue` set, so **BOTS → FIND MATCH** enters the real
`TryJoinQueue` today."* S122 then made FIND MATCH work end to end.

⚠ **Retire crash-era capture as a decryption strategy** — the 7 `crashwatch` images are worth
**2 pages** over the live-state images, and all 7 are *below* the best healthy single image.

⚠ **Re-dumping an already-explored state is worth 0–5 pages** [M]. Dump only after driving
something new.

---

## 9. ★★★★★ THE BIGGEST BY-PRODUCT: `dumpimage` HAS BEEN DISCARDING THE PROTECTOR, 52 TIMES

This is not an FK-20 result — it belongs to FK-10 / FK-31 — but it was found by auditing FK-20's
instrument and it is the highest-value thing in this document.

**`tools/usmapdump/dumpimage.go:239-240`:**
```go
case rg.typ != memPrivate:
    dumped = "(skip: " + regionKind + " — other module)" // other DLLs / mapped, not our unpacked code
```
**Every `MEM_IMAGE` executable region is skipped by design**, and the comment states the false
premise: a **manually mapped, module-list-hidden** `MEM_IMAGE` region is not "another DLL" — it is
**the protector**. S131 measured `runtime.dll` as exactly that: `MEM_IMAGE`, `AllocationBase ==` the
kill address & `~0xFFF`, with **no `ModuleList` entry**.

**[M] The protector's 4-region executable signature, recovered from crashpad `MemoryInfoList`:**
```
+0x0000000 0x0007000 READONLY       <- MZ/PE headers   (the kill target is base+1)
+0x0007000 0x0001000 EXECUTE_READ
+0x0008000 0x07C7000 READONLY       <- packer0 (94.8 % encrypted ON DISK per FK-10)
+0x07CF000 0x0170000 EXECUTE_READ   <- contains FK-10's kill primitive RVA 0x80F7F0
+0x1520000 0x2A49000 EXECUTE_READ   <- 44.3 MB main code body
                     total 0x4066000 = 67,526,656 B;  executable 48,136,192 B (45.9 MB)
```
`SizeOfImage 0x4066000` matches S131 exactly and matches `runtime.dll` on disk (67,511,496 B,
`ImageBase 0x200000000`, 11 sections). ⚠ Executable content is **48,136,192 B = 45.90 MiB**; a draft
said this "matches FK-10's 46.6 MB" — **it does not match in either unit** (FK-10's 46.6 MB is its
own approximate figure). Do not manufacture agreement across units.

**That signature is present in 26/26 `dumpimage` manifests, TWICE each = 52 mappings, every one
marked `(skip: Image — other module)`.** Verified directly from the manifests here: they list
`0xFF767000 0x1000 Image` and `0xFFF2F000 0x170000 Image` — which are **exactly** LOW`+0x7000` and
LOW`+0x7CF000` of the predicted map. (5,910 `skip: Image` lines total across the 26.)

★★★ **AND IT CORROBORATES FK-31 FROM A NEW INSTRUMENT.** The manifests' HIGH bases group by era:

| era | HIGH base | dumps | LOW base |
|---|---|---:|---|
| Jul (accountpass, loadout, menu, missions, rcb, roster, store, toggles, vmbuild) | `0x7FF90E000000` | 9 | `0xFF760000` |
| Aug 04–09 (tutorial-hero) | `0x7FFD3B400000` | 1 | `0xFF760000` |
| Aug 13–16 (claimflow ×2, heromastery, lobby-dispatch, crash-20260815-* ×2) | `0x7FFA42600000` | 6 | `0xFF760000` |
| Aug 19–20 (s129/s131/s132 ×5, crash-2026081920-* ×5) | `0x7FFB57400000` | 10 | `0xFF760000` |

(9 + 1 + 6 + 10 = **26**. ⚠ A draft printed 9/1/5/9 = 24 ≠ 26 — **a table that partitions a corpus
must sum to it; check it.**)

**The three later HIGH bases are exactly S131's three FK-31 constant kill addresses minus 1** —
offline, from a different instrument — **plus a FOURTH era base (`0x7FF90E000000`) that S131's
minidump-only corpus could not see.**
★★ **`runtime.dll` is mapped TWICE and the LOW base is INVARIANT — `0xFF760000` in 26/26 manifests
and 123/124 distinct crashes.** ⚠⚠ **NOT NEW — a draft called this and the shadow-exe mapping below
"never recorded anywhere in this project", and both are in `docs/s109-dump-forensics.md` §5
(2026-08-04/05)**, which already tabulates all three hidden images with the same LOW/HIGH
`EXECUTE_WRITECOPY` vs `EXECUTE_READ` distinction, and `docs/s109-skeptic-review.md:60-70`
re-verified it against UE's own `<CallStack>`. **What IS new is only that the `dumpimage` MANIFESTS
carry it too, 52 times, each marked skipped.** ★ *Grep the repo before writing "NEW".* The LOW copy shows
`+0x7000 EXECUTE_WRITECOPY` and one undifferentiated `WRITECOPY`; the HIGH copy shows `EXECUTE_READ`
and *split* `READWRITE`/`WRITECOPY` ⇒ **[I, strong] the HIGH mapping is the one executing and
writing, the LOW one is a pristine second view** — consistent with the kill jumping to HIGH+1.

⚠ **[M] 48,136,192 B (45.90 MiB) of protector executable content sat readable under
`ReadProcessMemory` in every capture this project ever took, and `dumpimage` wrote none of it.**
⚠⚠ A draft said **96.3 MB** by summing both mappings — that **double-counts**: they are two
`SEC_IMAGE` views of the *same* 67,511,496-byte file, and the only observed differentiation between
the views is **57,344 B** (`.rwx` at `+0x7000` and `packer2` at `+0x93F000`). **Two views of one file
are one file's worth of bytes.**

**PROPOSED PATCH — NOT APPLIED** (it changes capture behaviour and adds ~96 MB per dump to a
`dumps/` tree that is already 16 GB, so it should be the operator's call, and it is worth a flag):
```go
case rg.typ != memPrivate && moduleAt(pid, rg.allocBase) != "":
    dumped = "(skip: " + regionKind + " — " + moduleAt(pid, rg.allocBase) + ")"
case rg.typ != memPrivate:
    // MEM_IMAGE with NO ModuleList entry == manually mapped. This is the protector. DUMP IT.
```
Pure RPM, no injection, no `.text` write. It yields a **live-based `runtime.dll`** and — because
FK-10 measured `packer0` as **94.8 % encrypted on disk** — plausibly **plaintext `packer0`**, which
is where the kill-primitive vtable (`packer0 RVA 0x1831C0`) and its installer (`RVA 0x7F86F0`) live.
That is exactly what FK-10's Wall #7 has been hunting. Grade: readability **[M]**; plaintext-ness
**[S]**, untested.

★ **A third hidden mapping — recorded in `docs/s109-dump-forensics.md` §5 but never acted on, and it
is a lottery ticket.** In **all** minidumps
there is exactly one `MEM_IMAGE` allocation of `0xA9E1000` — **the game's own `SizeOfImage`** —
`READONLY`, a **single** region (no per-section protections), at a heap address, **124** distinct
bases (one per crash). **0 bytes of it were ever captured.** Control: **P2 = 0/394 — the game's real module
is `MEM_MAPPED`, not `MEM_IMAGE`**, so this is a *second, hidden* view of the exe.
**[I, strong]** its shape is a `SEC_IMAGE` / raw section view ⇒ probably the **encrypted on-disk**
bytes. **[S]** it could instead be the **plaintext master the fault handler decrypts from** — in
which case **one read-only RPM read yields 100 % of `.text` in one shot** and this entire document's
subject evaporates. **Cost to settle: one `VirtualQueryEx` + one 4 KB read at that base and at
`+0x751EFD0` (the OEP), compared against the on-disk exe and `merged6`. Not settleable offline.**

---

## 10. Standing process fix

`tools/re/dump_coverage_ledger.py` (new). It reads **bytes, not manifests**: an image is an ORPHAN
iff it holds ≥1 decrypted page the reference merge lacks. Exit code 1 on orphans, so it can gate a
workflow. It prints its own `file offset == RVA` control, and it was validated in both directions —
**0 orphans against `merged6`; 6 orphans against `merged5`**, the known-unmerged set.
⚠ It also prints the warning that the per-image "not in ref" column is **not additive** (those six
columns sum to 13 while the real union gain is 5).

Run it after every capture, and before trusting any "this page is dark" claim.
