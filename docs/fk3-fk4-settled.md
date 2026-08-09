# FK-3 and FK-4 — SETTLED. Both false. The real cap, and what it costs.

**S104 · 2026-07-26 · 100% offline.** No game launched, no injection, no writes to `dumps/`.
Input for every measurement below: `dumps/merged.dump.exe` (178,130,944 B, ImageBase
`0x7FF6AF000000`, file offset == RVA for all 10 sections — verified).

**Supersedes:** `docs/coverage-audit-s101.md:284` (FK-3) and `docs/session-42-step5:42-49` +
`docs/session-85-netcache-chain-diff.md:253` (FK-4). Retraction banners inserted at both, and at
the FK-3 / FK-4 entries in `docs/ignorance-map-s101.md`. Nothing was deleted.

**Companion documents** (the four applications this settlement enabled):
`docs/strxref-known-addresses.md` · `docs/strxref-open-questions.md` ·
`docs/strxref-state-coverage.md` · `docs/strxref-vtables.md`.
Tooling: `tools/strxref/` · `tools/strxref/README.md`.

Every figure is tagged **MEASURED** (read out of the image) or **INFERRED** (a reading of
measured bytes). Where a number was re-measured independently *for this document*, with no
project tooling, it is marked **[re-verified]**.

---

## 1. Verdict

### 1.1 FK-3 — "`.rdata` is capped at 63.12% and that is STRUCTURAL"

> *"`.rdata` union is capped at 63.12% and IS structural … ~13.9 MB of vtables, RTTI and string
> literals are permanently unreadable by RPM, which genuinely caps the vtable-dump and
> string-xref techniques."* — `docs/coverage-audit-s101.md:284`

**FALSE.** `.rdata` is **99.64% readable**.

The claim rests on a metric that counts **non-zero bytes**. `.rdata` is full of legitimately
zero bytes — vtable null slots, string padding, alignment fill — so that metric reports a "gap"
wherever the data is legally zero. The metric that answers "can I read this?" is **whole-page
readability**, and by that metric `.rdata` is almost completely intact.

**MEASURED [re-verified]** — 40-line stdlib script, no project tooling:

```
name       vaddr             vsize   pages  zeropages   nonzero%   readable%
.text    0x00001000    124,030,976  30,281     14,448     48.05%     52.29%
.rdata   0x0764a000     37,212,160   9,085         33     63.12%     99.64%   <- FK-3
.pdata   0x0a0b7000      6,283,264   1,534      1,534      0.00%      0.00%
```

**33 of 9,085 `.rdata` pages are entirely zero. 0.36%.** The "~13.9 MB permanently unreadable"
is null padding.

Note the control in the same table: for `.text` the two metrics **agree** (48.05% vs 52.29%),
because demand-decrypt zeroes *whole pages*. The byte metric is sound for `.text` and
meaningless for `.rdata`. FK-3 applied the `.text`-shaped metric to a section it does not
describe.

**Three independent corroborations**, none using the same instrument:

1. All nine `dumps/*/…dump.txt` manifests already reported `.rdata … (100.0%) READABLE`
   (`docs/ignorance-map-s101.md`). The audit quoted the *other* line in the same file.
2. The `ULokiAssetManager` vtable captured from the **live process** on 2026-06-28
   (`docs/lokiassetmanager-vtable-dump.md`) reproduces **8/8 spot-checked slots** from the cold
   dump. So this is not an artifact of the dump being generous — `.rdata` was readable live too.
3. `.rdata` section entropy is **5.2–6.0 bits** with ~70% of pages below 6.0, against 8.00 for
   `.text`, `.pdata` and `_RDATA`. Encrypted data does not have entropy 5.2.

### 1.2 FK-4 — "the packer decrypts `.rdata` strings to the heap; string-xref is defeated"

> *"this build's packer decrypts `.rdata` strings to the HEAP on use and leaves the module
> `.rdata` copy encrypted, so rip-relative LEA → string xref is defeated."*
> — `docs/session-42-step5:42-49`, restated `docs/session-85-netcache-chain-diff.md:253`

**FALSE. The searches were ASCII; the strings are UTF-16.**

**MEASURED [re-verified]** — the five strings the record named as packer-encrypted, read raw at
their recorded RVAs with `open(...).read()` and a slice, no tooling:

```
0x079E02D0  UTF-16  'Toc signature hash: %s'
0x08B1C688  UTF-16  'feature toggles were not ready'
0x08970FA0  ASCII   'GetFeatureTogglesReady'
0x08A56F38  ASCII   'MulticastSetGameFeatureToggle'
0x08077F9E  UTF-16  "Couldn't spawn player controller of class %s"
```

Plaintext, in the module's own `.rdata`, in an artifact the project has had since 2026-07-17.

**The census the ASCII-only scans could not see (MEASURED):**

| encoding | strings in `.rdata` (len ≥ 6) | referenced from `.text` (exact-start) | rate |
|---|---:|---:|---:|
| ASCII | 103,002 | 12,857 | 12.5% |
| **UTF-16** | **85,677** | **42,213** | **49.3%** |

Image-wide, all sections, min-len 4: **111,932 ASCII + 87,851 UTF-16 = 199,783 strings.**
**Roughly 44% of this binary's string data was invisible to every scan run before this session.**

**And the xref technique works.** MEASURED: `517,515` `lea r64,[rip+disp32]` in `.text` →
`245,894` target `.rdata` → `106,800` distinct targets. Including interior references and
`.rdata` pointer-table indirection, the index resolves **55,473 of 85,677 UTF-16 strings
(64.7%)** and 14,518 of 103,002 ASCII (14.1%).

### 1.3 FK-4's origin, measured rather than guessed

Two things combined to produce it, and it is worth knowing both because each is *separately*
capable of producing a plausible false negative:

1. **ASCII-only scanning** (the dominant cause).
2. **The on-disk exe genuinely IS packed.** MEASURED: only **634 of 9,085 `.rdata` pages
   (6.98%)** of the on-disk file match the dump. Anyone who scanned `SUPERVIVE-Win64-Shipping.exe`
   on disk got garbage and was *right to*. The live/dumped copy is plaintext; the shipped file is
   not. FK-4 generalised a true statement about one artifact into a false statement about the
   technique.

⚠ **Scope limit that survives:** the on-disk exe is not a new data source. The merged dump is a
strict superset (67,473 vs 60,735 unique ≥16-char runs). The actionable correction is *re-run
your scans in UTF-16 against the dump*, not *go get the exe from disk*.

### 1.4 A fourth instance of the same error — in the brief that commissioned this document

The task preamble stated that `feature toggles were not ready` *"resolves to 0 sites purely
because its emitting code has never run."*

**MEASURED: it resolves to 4 sites.** The RVA `0x08B1C688` is **88 bytes into** a longer string
(`'ULokiGameFeatureToggles::Get %s called when feature toggles were not ready'`). An
exact-start-only lookup returns 0; enclosing-string resolution returns 4, all inside
`ULokiGameFeatureToggles::Get @ 0x55DB370`. **The code did run.**

This is recorded here, prominently, because it is the same error shape one level up: a null
result produced by the *lookup rule* was about to be attributed to the *target*. See §9.

---

## 2. The corrected cap — the honest replacement belief

**Do not read §1 as "there is no limit." There is a hard limit; it is just a different one.**

### 2.1 The cap is `.text` demand-decrypt, and it is ~52%

The packer decrypts `.text` **pages on execution**. A page whose code has never run is a 4 KiB
block of zeroes in every dump we can take. MEASURED: **15,833 of 30,281 `.text` pages (52.29%)
are decrypted** in `merged.dump.exe`; 14,448 pages (47.7%, ~56 MB) are zero.

Everything downstream inherits this:

| technique | ceiling imposed by `.text` decryption | measured performance |
|---|---|---|
| string → code xref | ~52% of emitting code exists to be found | UTF-16 exact-start **49.3%** |
| function attribution | can only attribute inside decrypted code | 95.9% of ref sites land in a known function |
| disassembling any named target | the body must be decrypted | 225 of 683 recorded addresses unreadable |

UTF-16 exact-start resolution (**49.3%**) tracks the decrypted-page fraction (**52.29%**) closely
enough that **the technique is running at ~94% of the ceiling its input allows.** INFERRED, but
tightly: essentially every UTF-16 string whose referencing code is decrypted is successfully
xref'd. The technique is not lossy; its input is incomplete.

### 2.2 The mechanism, and why it is not structural

MEASURED, from the dump audit (`docs/strxref-state-coverage.md` §1.2):

- Coverage is **monotonic within a process**: `menu ⊂ store ⊂ roster ⊂ missions = loadout`, no
  page ever lost.
- The packer does **not** re-encrypt cold pages: the PE entry-point page (`0x751EFD0`), which
  executes exactly once at process start, is still decrypted in **all 10** images. *(Hypothesis
  raised, tested, rejected — not recorded as a fact.)*
- Therefore coverage is a **monotone function of what the game has executed**. Running more code
  is the only lever, and it always helps.

**This is the same lever `docs/ignorance-map-s101.md` calls "state coverage IS binary coverage."**

### 2.3 The numbers — including the part that stays dark

MEASURED, using crash-minidump unwind tables as independent coverage probes for states we never
took an image dump from (§8):

```
merged.dump.exe (today)                     15,833 pages   52.29%
union of all 9 image dumps on disk          16,435         54.27%   (+602, free)
best single crash-era process               18,911         62.45%   (+3,430 vs merged)
union of all 70 crash tables                19,495         64.38%
GRAND union (images + crash tables)         19,715         65.11%
NEVER decrypted by anything we have         10,566         34.89%   <- 41 MB, hard floor today
```

**34.89% of `.text` — 10,566 pages, 41 MB — has never been decrypted in any process this project
has a record of.** No offline work reaches it. Only executing that code does.

And even the theoretical union of every record we hold is **65.11%**, not 100%. The cap is real,
it is large, and retracting FK-3/FK-4 does not touch it. What changed is *which* section it lives
in and *whether it can move*: `.rdata` was never the constraint, and the constraint that does
exist is **movable, monotone, and priced** (§8).

---

## 3. What is genuinely dead

Two things really are gone. Both were bundled into FK-3's sentence, which is part of why the
sentence survived — it contained true clauses.

### 3.1 RTTI — effectively stripped for every game class

**MEASURED [re-verified], and refined this session.** The prior claim was "0 `.?AV`/`.?AU` type
descriptors in `.rdata`" — correct as scoped, but MSVC actually emits `TypeDescriptor` into
`.data`, so a whole-image scan is the right test. Doing it:

```
.?AV / .?AU mangled names in the whole image : 691   (all in .data)
RTTI Complete Object Locators in .rdata      : 633
distinct leading identifiers                 : 590
names containing 'Loki'                      :   0
```

Probing the identifier set for canonical UE classes: `AActor`, `UWorld`, `UClass`,
`UActorComponent`, `APlayerController`, `UGameInstance`, `FProperty`, `UAssetManager`,
`UMissionsModel` — **all absent**. The single apparent hit, `UObject`, is
**`.?AVUObject@icu_64@@`** — ICU's `icu_64::UObject`, not Unreal's.

The 691 are C++-exception-handling remnants from statically linked third-party translation units
compiled with RTTI on: ICU, STL (`std::exception`, `basic_string`, `_Ref_count_obj`), the GTE
geometry library, libpng (`FPNGImageCRCError`), and CommonUI lambdas. UE itself is built `/GR-`.

**Corrected statement:** *RTTI is present only as third-party EH residue. **Zero** UE reflected
classes carry a type descriptor.* Operationally identical to "stripped" — 633 COLs against
104,903 `.text`-pointer runs is 0.6% — but now precise, and it explains why a naive
`.?AV` grep returns 691 and looks like RTTI survives.

**Two consequences, and the second one had never been written down:**

1. **A vtable cannot be named from RTTI.** Unavoidable. Naming had to come from elsewhere — it
   does (§7), from UE's own `IMPLEMENT_CLASS` boilerplate.
2. **★ The vtable *separator* is gone.** MSVC normally puts a COL pointer in the qword
   immediately before each vtable. That pointer targets `.rdata`, so it breaks the run of `.text`
   pointers and delimits adjacent vtables. Without it, vtables are packed **back-to-back**:
   MEASURED, the `ULokiAssetManager` vtable is **slot 799 of a single 997-slot run**. `.rdata`
   holds 933,675 `.text` pointers in 104,903 maximal runs, longest **30,247 slots**. **No
   threshold on run length can find a vtable, because a run is a chain of many.** *This* is the
   real cost of RTTI stripping — not unreadable memory.

**What stays permanently unnamed:** the 11,163 pieces in the 8–31-slot band — interfaces,
`FTickFunction`, deleters, RHI/D3D12 classes (including the S40 crash classes `0x7B9E188`,
`0x7B9DE88`). They are real C++ vtables with no UE boilerplate, so nothing names them. That is
a genuine, permanent loss.

### 3.2 `.pdata` — the module's copy is dead; the information is not

**MEASURED [re-verified]:** the in-image `.pdata` is **1,534 of 1,534 pages all zero (0.00%)**.
The on-disk copy is packer-encrypted — **0 of 523,605** candidate `RUNTIME_FUNCTION`s are
structurally sane, and the Exception data-directory is nulled.

Consequence, precisely: **the module carries no unwind table, so function bounds must be
inferred** — and inference is much worse than anyone had checked. `strxref`'s prologue-sweep
heuristic, scored against real bounds (§3.2 next paragraph) rather than against 36 hand-recorded
addresses: **56.4% recall, 56.8% correct entry, and 21% of extents overstate the true size by
more than 2× (p90 7.7×, p99 64×)**. Any pre-S102 claim resting on a heuristic function extent
should be re-checked.

**But the information survives in a different artifact.** `docs/ignorance-map-s101.md` B5 was
right: **70 of the 85 crash minidumps** under `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` carry the
real x64 unwind table in stream 13 (524,439 slots each, identical count in all 70). Unioned:
**382,282 exact, non-overlapping ranges**, 54.7% of `.text` by bytes, including **39,836
functions in pages no image dump has ever decrypted**. Ground truth: **13 of 13** addresses
recorded across ~101 sessions of live RE land as EXACT entries; the 14th (`0x587C699`) is
correctly reported as interior at +1897.

**⚠ Three caveats that must travel with that table:**

- **They are FRAGMENTS, not functions.** x64 allows one function to own several chained
  `RUNTIME_FUNCTION` records. 147,176 ranges begin exactly where the previous ends; 129,033 of
  those begin unaligned. **382,282 fragments → 253,249 functions** after merging.
  **[re-verified] live instance**, the S103 crash function:

  ```
  0x3C5DBC0 .. 0x3C5DBE3   35 B
  0x3C5DBE3 .. 0x3C5DC45   98 B
  0x3C5DC45 .. 0x3C5DC60   27 B      <- `func 0x3C5DC52` reports THIS as the entry
  0x3C5DC60 .. 0x3C5DC6B   11 B
  0x3C5DC80 .. 0x3C5DD87  263 B      <- next real (16-aligned) function
  ```
  Merged: `0x3C5DBC0..0x3C5DC6B`, 171 bytes — which is exactly the entry
  `docs/strxref-open-questions.md` §4 identified. Consumers of raw bounds must merge or say
  "fragment".
- **Bounds without bytes.** Minidumps carry no `.text` (their `MemoryList` is ~60 KB). The 39,836
  newly-bounded functions are named and sized and **unreadable**.
- **A gap is not an absence.** A missing entry means "never decrypted in these 70 processes",
  exactly like a zero-xref string. (34.5% of slots are `End == Begin + 1` placeholders; only
  3.0% of placeholder begins were ever confirmed real — measured *before* being written down.)

**Fragility:** `tools/strxref/index/` is git-ignored. `pdataunion.py` regenerates the table in
seconds **only while the 2.0 GB Crashes directory survives**. Nothing in this project has ever
depended on it, and a cleanup would delete it. Either keep it or commit `pdata_union.bin`
(4.5 MB).

---

## 4. The tooling now available

All stdlib-only, offline, read-only, standalone. `tools/strxref/README.md` documents each.

| tool | what it does | cost |
|---|---|---|
| `strxref.py` | string census (both encodings) + rip-relative xref index + function attribution; modes `find` `xref` `func` `near` `native` `nattable` `pdata` `validate` | rebuild 19.7 s → 18.2 MB index; queries sub-ms |
| `vtables.py` | vtable scan / name / diff / slotof / who / classes / reflect / verify | 3 s → 4.4 MB index |
| `uereflect.py` | recovers 32,066 UE reflection symbols from `.rdata`/`.data` tables | ~90 s |
| `harvest_addrs.py` + `name_addrs.py` | sweep the repo for recorded RVAs → `docs/symbols.csv` | seconds |
| `mdpdata.py` + `pdataunion.py` | minidump stream-13 parser → 382,282 exact bounds | seconds |
| `dumpcov.py` `dumpcov2.py` `yield.py` `subsystems.py` `statecov.py` `pagecheck.py` `pdatascore.py` | coverage audit, marginal yield, dark-subsystem census, per-RVA page probe | seconds |

**Self-validation, run for this document: `strxref.py validate` → 21 checks, 0 failed.
`vtables.py verify` → 7 checks, 0 failed.** Both reproduce their headline figures against the
image at run time; both fail loudly on bad magic, wrong machine, out-of-range section tables, and
— importantly — on any section where `PointerToRawData != VirtualAddress`, which is what stops
someone pointing the tool at the packed on-disk exe and getting plausible garbage back.

### Worked examples (verbatim, run for this document)

**`native <UFUNCTION>` — name string → exec thunk → native implementation.** This is a *new
technique*, and it is the one that most directly exploits FK-3's correction: because `.rdata` is
99.64% readable, it locates a function **even when the code that registers it sits in an
undecrypted page**.

```
$ python strxref.py native "ClearMatchTransition"
name  0x08A90088 A 'ClearMatchTransition'
  FClassFunctionLinkInfo slot 0x08A90450 -> Z_Construct_UFunction 0x548B130
  FNameNativePtrPair slot 0x09C2EF08 -> exec thunk 0x548F630
        jmp  0x588ED60  callers=1  +0x15   <== IMPLEMENTATION candidate
```

**`func <rva>` with recovered bounds:**

```
$ python strxref.py func 0x3C5DC52
query   0x3C5DC52
entry   0x3C5DC45   [.pdata EXACT]   (heuristic said 0x3C5DBC0 -- missed the entry)
extent  0x3C5DC45 .. 0x3C5DC60 (27 bytes) -- EXACT (minidump stream 13, 70 tables)
```
*(and the fragment caveat of §3.2 applies — the true function is `0x3C5DBC0..0x3C5DC6B`.)*

**`vtables.py slotof <rva>` — a bare address becomes `Class[slot]`:**

```
$ python vtables.py slotof 0x560AFE0
0x560AFE0 appears in 10 vtable(s), 10 of them named:
  slot 176  of 0x08951FA0  ALokiGameMode
  slot 176  of 0x08A94C48  ALokiTutorialGameMode
  slot 176  of 0x088B7CB0  ALokiBattleRoyaleGameMode      (+7 more gamemodes)
```
The record had this as an unnamed "tutorial launch" address. It is one virtual, slot 176, shared
by ten gamemodes — and `0x37E5C80` ("match setup") is `AGameModeBase[176]`, i.e. the **base of
the same virtual**. A shim that hardcodes `base + 0x560AFE0` can call `vtable[176]` off a live
object instead, which is what makes it survive a rebase.

**Two more, from the applications:** `func 0x536BF8E` identifies a 20 KB unknown function in one
call (entry `0x536A5A0`, 155 string refs, all UE reflection registrar names). `native
GetFeatureTogglesReady` → exec `0x5376E00` → `0x565E1A0` → `0x55DDA50`, whose body is exactly
S89's live finding: `bit6 of [GameState+0x5A0]+0xB3`.

---

## 5. The symbol table, and its validation

### 5.1 What was recovered

`.rdata` being readable means **UE's own code-generator tables survive the packer intact.**
Parsing them offline (`uereflect.py` + `vtables.py`):

| | count |
|---|---:|
| `Z_Construct_UFunction_<Class>_<Name>` stubs named | 16,998 |
| — name re-verified through the `FFunctionParams` chain | 16,996 (0 mismatches) |
| native **exec thunks** named — the exact `UFunction.Func @ +0xE0` the S55 primitive invokes | 16,214 (14,385 distinct names) |
| UE classes named | **1,258 / 1,258** |
| **distinct code RVAs named (reflection)** | **32,066** |
| named **vtables** (class → vtable) | **3,599** distinct, 5,061 / 5,077 classes resolved, **773 in `/Script/Loki`** |

Against a prior baseline of ~617 known addresses, that is a **~52× increase in named code**, and
it needs no running game.

*(Denominator correction, MEASURED: the audit's "~120,000 functions" is ~3× too small. At least
**382,282** fragments / **253,249** functions exist. 617 / 253,249 = **0.24%**, not 0.5%.)*

### 5.2 Validation — four external checks, none using the tools' own assumptions

1. **Class arity.** `ULokiAbilitySystemComponent`'s link-info run is 138 qwords = **69 entries**;
   `docs/session-100-gas-api-dump.txt`, captured live months earlier, records exactly **"69
   UFunctions"**.
2. **FunctionFlags.** vs the same live dump: **1,557 match, 0 mismatch.**
3. **Exec-thunk addresses.** vs that dump's `thunk=` column: **1,404 match, 0 mismatch**, under a
   single 64K-aligned base recovered from the data itself.
4. **Vtables, two ways.** 8/8 slots vs the June live capture; **5/5** class↔vtable pairs recorded
   live in earlier sessions; and an inheritance-similarity control over **4,032 class/base pairs
   from `schema.txt`** (which `vtables.py` otherwise never reads) — **median 97.9% shared slots,
   4,031 of 4,032 ≥ 50%**, where random pairs would share ~0%. Name agreement with `schema.txt`:
   **5,056 of 5,077 = 99.6%** (the 21 misses are all `DEPRECATED_*`).

**Free by-product:** the session-100 module base is **`0x7FF6E7D30000`** — never recorded, which
made every absolute address in `session-100-gas-api-dump.txt` unusable. All ~1,566 now convert:
`RVA = absolute − 0x7FF6E7D30000`.

### 5.3 The 683 recorded addresses — validated

Harvested from 584 files (119 MB of `docs/`, `memory/`, shim `.cpp`, probe `.py`, `CLAUDE.md`)
plus every git commit message. Output: `docs/symbols.csv`, 683 rows × 20 columns.

| verdict | n | | name check | n |
|---|---:|---|---|---:|
| `ENTRY-OK` | 226 | | `AGREES` | 67 |
| `INTERIOR` (correct for patch/gate sites) | 213 | | `NO-NAME-EVIDENCE` | 124 |
| `UNVERIFIABLE` (page all-zero in this dump) | 225 | | `DISAGREES` | 17 |
| `NOT-CODE` (`.rdata`/`.data`) | 19 | | `NO-RECORDED-NAME` | 228 |

**The record is accurate: zero confirmed bugs.** All 56 addresses checkable against the
independent symbol table match. All 17 `DISAGREES` rows were inspected by hand — every one is the
name-extractor grabbing a neighbouring token out of prose, not a record error. 352 addresses got
exact bounds; 40 previously-unnamed addresses now have a proposed name.

**Be honest about what that is:** it is a *negative* result about the records. Its value is that
it retires a suspicion, and that the instrument built to check it is the actual deliverable.

**Two record corrections (the only two):**

- `docs/lokiassetmanager-vtable-dump.md:584` — `UMissionsModel` vtable `+0x88ADED0` is a
  transcription typo for **`+0x8AADED0`**. Adjudicated three ways: the recorded address has **0**
  code references and shares **5%** of `UObject`'s first-40 slots (impossible for a UObject
  subclass); the corrected one has 2 LEAs and **97.5%**.
- `index/pdata_union.csv` holds **fragment** bounds, not function bounds (§3.2).

**⚠ ICF — an RVA is not a unique function identity.** MSVC `/OPT:ICF` folds byte-identical
functions: **469 of 15,068 exec thunks (3.1%) carry more than one name**. Three addresses in the
*active* `docs/tutorial-playability-plan.md` looked wrong and are **correct** — the recorded name
was present, just not first in the folded list. Reporting them would have caused three correct
addresses to be "fixed". `symbols.csv` marks these `EXACT-AMBIG`.

**The 225 `UNVERIFIABLE` are a coverage limit, not a defect** — 33% of the recorded set against a
47.7% image-wide zero-page rate, i.e. recorded addresses skew toward code the game actually runs,
as expected. Absence of evidence, not evidence of error. It lifts with §8.

---

## 6. Open questions — answered, and not

### 6.1 Answered

**★ The deterministic 173–201 s crash (FK-7) — SOLVED.** The ignorance map budgeted a session
for this ("take those 8 RVAs and disassemble"). It took minutes.

`func` identified the stack by strings: outermost `0x37F8820` = `UGameEngine::Tick`
(`Slow GT frame detected`, `TickRenderingTimer`, `ViewportClosed`), then camera-mode code at
`0x3C5CFC0` (`FreeCam`, `ThirdPerson`, `FirstPerson`, `Fixed`), then the faulting frame. Exact
faulting instruction (MEASURED):

```
03C5DC45  mov  rcx, qword ptr [rbx]      ; rcx = obj  (non-null: it passed test rdx,rdx earlier)
03C5DC4F  mov  rax, qword ptr [rcx]      ; rax = obj->vptr
03C5DC52  ff 90 00 07 00 00              ; call qword ptr [rax + 0x700]   <-- FAULT
```

The recorded fault address is `0x700`; the displacement is `0x700`; those are equal **only if
`rax == 0`** — which also independently confirms the frame ordering. So it is **not** a null-field
read: the object pointer is alive, its **vtable pointer is zero**. That is a **use-after-free
virtual dispatch** through slot `0x700`.

INFERRED, tightly: the function writes an `FMinimalViewInfo`-shaped result, has zero direct
`E8`/`E9` callers anywhere in `.text` (it is a vtable virtual), and its only inbound frame is
camera code ⇒ it is `APlayerCameraManager`'s view-target evaluation calling `AActor::CalcCamera`
on a dead `ViewTarget.Target`. That lands on S93's own *"spawn a `CameraActor` + re-assert the
view target"* — a force-spawned camera later collected while still the view target produces
exactly this instruction, on exactly this per-frame path, and explains determinism (GC timing)
far better than any anti-tamper theory. **FK-7 should be re-scoped: this and the ~3–5 min
integrity check are different phenomena.**

**`ALokiGameMode::SpawnPlayer` returns null (S74) — ANSWERED decisively.** Its exec thunk calls
`0x00F7EB50`, which is `xor eax,eax; ret` — the COMDAT-folded `return 0` shared by 58 sites. The
native body **is** `{ return nullptr; }`; the logic is in the Blueprint override, so the S55
direct-thunk call bypasses it *by construction*. Reusable offline check, new: **if `native <name>`
resolves to `0x00F7EB50`, the native body is empty and the logic is in Blueprint** — use
`CallBPGuarded`, not `CallNativeGuarded`.

**The S89/S90 loading-overlay wall — a better lever.** `ClearMatchTransition` impl **`0x588ED60`**,
exec **`0x548F630`**, with its precondition `[mgr+0x50] != 0` and the manager getter
(`0x589D0C0` → `[0x57ACC60()+0x38]`). That is the game's own overlay teardown, reachable by name
through the existing S55 primitive — versus S90's plan to hand-hide the widget, which cannot tell
you whether the overlay is even mounted.

**GAS wiring — and a method validation.** exec `0x5438C20` → impl `0x56CE5F0`, reproducing
S102's live result offline. `near 0x08A26E28` gave the `ALokiPlayerState` UPROPERTY block and
INFERRED `+0x4F8 = HeroAffiliatedObject`. **That inference is confirmed** — commit `cf1e0b6`
(S102b, the same day, ~7 h earlier) established it *live* by a completely independent route
(`class_props.py` reflection walk). strxref did not discover it; it **independently reproduced
it**, which makes this a third ground-truth validation of the offline route alongside
`GetFeatureTogglesReady` and `TryUpdateAbilitySystem`.

**★ `GetLifetimeReplicatedProps` is vtable slot 85**, and the strings each override touches are
that class's replicated properties in registration order. `APlayerState` → the exact 11-name
vanilla UE5.4 `DOREPLIFETIME` list. `ALokiGameStateBase` → 4, including
`ReplicatedWorldTimeSecondsDouble` (independently reproducing the S70 float-vs-Double finding).
**`ALokiGameState` → 43** — matching the 43 net props the S70 DS-stub mirror was hand-built with
over a full session. That list is now one offline command for any class, including ones the stub
has never been able to instantiate.

### 6.2 Not answered, and the state that would decrypt them

| target | address recovered | body | state that fixes it |
|---|---|---|---|
| `PollForFeatureTogglesReady` | exec `0x5302DE0` | all-zero page | in-match / drop-in / tutorial world |
| `FeatureTogglesReadyOrChanged` | exec `0x52FEF50` | all-zero page | same |
| `TryUpdateAbilitySystem` impl | `0x56CE5F0` | all-zero page | same (GAS never runs at menu) |

All three are `ALokiCharacter`/`ALokiPlayerState` members. `merged.dump.exe` is effectively a
single menu-state capture; character and ability code has simply never run. `dumpimage` from
inside the world → `mergedumps` → `--rebuild`. The addresses are already enough to call or hook.

### 6.3 The one question string-xref cannot reach at all

> ## ⚠⚠ SCOPE ERROR — CORRECTED 2026-08-09 (S113). The "clean negative" below is NOT clean.
> `tools/strxref/strxref.py:63` hardcodes `DEFAULT_DUMP = dumps\merged.dump.exe` — **the game exe.**
> `runtime.dll`, a *separate* 67.5 MB module and **the only plausible home for the check**, appears
> **0 times** in this document and was never scanned. The phrase *"and it is not coverage-blocked"*
> is exactly wrong: it was coverage-blocked in the strongest possible way, **by target selection**.
> This is the 20th recorded instance of the instrument-artifact pattern.
> **What the correct target actually contains:** `runtime.dll` is plaintext and disassemblable, and
> one offline pass found the full XXH3 `kSecret` at RVA `0x9c00`, SHA-256/SHA-1/MD5 tables at
> `packer2 0x942740–0x9467e0`, and a `.pdata`-free ISA-L multi-buffer tail at `0x8ffcd4–0x93e886`.
> ⚠ Note the xxHash there is **Zstd's frame checksum**, not the integrity hash — see
> `docs/fk10-protector-identified.md` §5. **The two SQLite/EAC false leads below still stand.**

**The ~3–5 min `.text` integrity check — clean negative, and it is not coverage-blocked.** No
string in this module names it: `tamper`, `VMProtect`, `code has been modified`, `anti-cheat` →
**zero** matches image-wide, both encodings. Two seductive false leads killed:

- `integrity_check` (`0x08D586E0`) and `IntegrityCk` (`0x08D5A9E0`) are **SQLite** — their
  neighbours are `journal_mode`, `incremental_vacuum`, `ResetSorter`, `ParseSchema`. Pragma names
  and VDBE opcodes from a statically linked SQLite.
- The **EAC path is a shutdown reactor, not a checker**: `ShowEACIntegrityViolationWidget` → exec
  `0x534BE80` → impl `0x5611090`, whose enclosing function's only string is
  `Starting shutdown for request exit: %s, %u`. It *reacts* to a verdict; it does not compute one.

INFERRED: the absence of any naming string is itself evidence. The checker is either inside the
packer's own obfuscated region (not a registered module, therefore outside `.text` and outside
every dump's section coverage) or out of process. **More `.text` coverage will not help this
one** — the statistical-modulo test on the 86 `SecondsSinceStart` values remains the right probe.

### 6.4 Where the results are thin — stated plainly

- **The 683-address audit found nothing wrong.** Valuable as reassurance and as the vehicle for
  the symbol table; thin as a finding in itself.
- **No name → C++ implementation mapping.** The `.data` record's third pointer is the
  implementation only **33.8%** of the time (measured over 2,621 samples), so nothing is claimed.
  Real call-target decoding inside each thunk is still owed.
- **Most functions reference no literals at all.** `ProcessInternal` (`0x13454A0`), `FindVM`
  (`0x57AB180`), `FPrimaryAssetId::ToString` (`0x12F4230`) touch zero. String-xref names the
  subset that *logs*; it is not a general disassembler.
- **The yield estimate has a 4.6× band** (§8) — 0.84 vs 3.90 new strings per page. Both are
  measured; they answer slightly different questions, and no tighter number is available until a
  genuinely new state is captured.
- **Vtable → class is not invertible.** 243 vtables carry >1 class (ICF); `0x076EF750` is assigned
  to 330 classes, and an earlier session independently observed 10 distinct CDOs sharing it live.

---

## 7. The vtable verdict — revived, and strong

**Revived, and stronger than the brief anticipated — but for a different reason.**

- **Is `.rdata` readable enough?** Yes. 8/8 live-captured slots reproduce from the cold dump.
  `.rdata` was never the problem.
- **Can vtables be found structurally?** **Only half way** — §3.1's separator loss. Cutting the
  104,903 runs at the 29,501 code-referenced 8-aligned LEA targets yields 119,260 pieces; naming
  concentrates entirely in the 32–511-slot band (**69.1%** of 32–127-slot pieces and **88.2%** of
  128–511-slot pieces are named UObject classes). A piece's length is an **upper bound** — the
  next cut is the next *code-referenced* start, so a vtable whose constructor page was never
  decrypted leaves no cut and its predecessor absorbs it. 89,759 pieces have unproven starts;
  `vtables.py` flags them.
- **Can they be named?** **Yes — 3,599, with class names**, from UE's `IMPLEMENT_CLASS`
  boilerplate: find `GetPrivateStaticClass` by its `L"/Script/<Module>"` + one class-name-shaped
  wide string, take its last `.text` LEA as `InternalConstructor<UFoo>`, follow **tail branches
  only** to the real constructor, take the constructor's first vtable LEA. *(Following `call`
  walks into the base constructor and assigns derived classes their base's vtable — that version
  produced 1,442 vtables instead of 3,599. "Never follow `call`" is the whole correctness
  argument.)* Parameter-insensitive across a 16× window sweep; the alternative rule degrades
  monotonically — the signature of a rule matching the codegen rather than the data.

**Both naming routes the brief proposed were measured and rejected.** (a) Naming a vtable by its
methods' strings scores **4.7% top-1** — only 168 of 35,941 sampled slot functions reference any
string, and a vtable is dominated by inherited slots. (b) Matching method count/order against
reflection **cannot** work: a UFUNCTION is a static `exec` thunk, not a virtual, and occupies no
vtable slot (r = +0.20 / +0.26 — "bigger classes are bigger"). Reflection's real value here is as
**validator and dictionary**, and in that role it is excellent.

**Why the vtable technique is less coverage-bound than string-xref:** a vtable slot yields a
**correct address even when the target's body is undecrypted**, whereas an undecrypted page
yields *no* string signal at all. MEASURED: slot targets land in decrypted `.text` 96.8% overall
(inherited 97.4%, class-own **72.2%**) against a 52.29% page baseline.

This supersedes `docs/lokiassetmanager-vtable-dump.md` **for obtaining a vtable** — that method
needed a running game and produced one vtable over a session; `vtables.py` produces 3,599 named
vtables in 3 seconds offline, reproduces that one exactly, and reproduces its hand-derived slot
94/131/132 identifications. It supersedes **nothing else** in that document: the singleton-vs-CDO
filter, the `AssetTypeMap` walk, the FName-layout proof and the scan-asymmetry investigation are
live-process work and still current. Static analysis gives you the vtable; only the running game
tells you which object is the singleton.

---

## 8. The capture plan to lift the `.text` cap

### 8.0 ⚠ PREREQUISITE — a fifth false-known, and it is load-bearing

`tools/usmapdump/mergedumps.go:154` rejects any input whose `ImageBase` differs, and
`configs/capture-dumps.ps1` elevates that to a hard constraint: *"capture all states WITHOUT
relaunching."*

**MEASURED: `.text` is completely base-independent.** The base-relocation table holds
**1,403,750 entries — 1,257,732 in `.rdata`, 146,018 in `.data`, and ZERO in `.text`.**
Empirically, `rcb` (base `0x7FF79D3B0000`) and `merged` (base `0x7FF6AF000000`) share **15,215
decrypted `.text` pages and all 15,215 are byte-identical.**

The rule is right for `.rdata`/`.data` and wrong for `.text` — and `.text` is the **only** section
that demand-decrypts, i.e. the only reason merging exists. **ASLR gives a new base most launches,
so today every cross-session capture is silently discarded.** Fix `mergedumps.go` to let a
different-base input contribute `.text` (and `.reloc`/`.rsrc`) while still skipping its
`.rdata`/`.data`, then drop the one-lifetime constraint. **Without this the plan below caps out
at one session.**

### 8.1 Free, right now, no game

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python pdataunion.py                     # 382,282 exact bounds
python strxref.py pdata                  # confirm

cd "G:\git\Supervive Revival Project"
.\tools\usmapdump\usmapdump.exe mergedumps dumps\merged2.dump.exe dumps
cd tools\strxref
python strxref.py --rebuild --dump "G:\git\Supervive Revival Project\dumps\merged2.dump.exe"
```
*(Write to `merged2` and compare — never overwrite the artifact the current index was validated
against.)* Gain: **+602 pages → 54.27%.** Real but small.

### 8.2 Expected gain per state — measured, not modelled

Crash unwind tables double as coverage probes for states we have never image-dumped. The best
crash-era process had **62.45%** of `.text` decrypted against our best 52.29%.

| # | state | expected `.text` gain | evidence |
|---|---|---|---|
| **1** | **in a live match / drop-in world** | **≥ +3,430 pages (+13.4 MB, +10.2 pp)** | crash processes *were* in that flow and reached 62.45% |
| 2 | DS stub connected + travelled (S70/S89) | large fraction of #1 | 12 crash tables cluster at 62.2–62.5%, all from that workflow |
| 3 | tutorial force-open, post hero-spawn | moderate | `toggles` alone (a probe-era menu state) was worth +539 pages |
| 4 | fresh launch → login → menu | small | coverage is monotonic; entry page already in all 10 dumps |
| 5 | another menu surface (store/roster/missions/passes) | **+0 pages, MEASURED** | greedy merge: all five gave +0 after the first |

**Do not spend another capture on a menu surface. That is measured, not opinion.**
**One in-match dump is worth 5.7× the entire re-merge of all nine existing image dumps.**

Expected new lit strings from +3,430 pages: **~2,900 (lower bound) to ~13,400 (realistic)**. The
band is honest: 0.84 strings/page is measured on *real* new pages, but all 9 image dumps are
menu states with 90–100% pairwise Jaccard, so those pages re-reference the same literals — a
lower bound. 3.90/page is the rarefaction tail slope over a random sample spanning every
subsystem that ran, which is the right model for *disjoint* new code.

### 8.3 Why those states specifically — the dark half is the frontier

Lit rate (≥1 resolved code reference) by subsystem, MEASURED:

```
DARK                              LIT
Chaos physics       19.3%         audio / Wwise       66.4%
drop / deploy       25.8%         asset / IoStore     59.0%
replay              30.3%         UI / Slate / UMG    58.4%
party beacon        30.7%         Loki frontend       48.7%
character movement  35.1%         renderer            48.0%
replication/netcode 35.9%
ability system/GAS  39.3%
```

**The dark subsystems are precisely the project's open blockers** (S71 possession, S81 CMC, S88–90
toggles, S100 GAS); the lit ones are precisely what is already solved. That is the concrete form
of *"state coverage IS binary coverage"*: the frontier is dark because the frontier's code has
never run in a process we dumped.

### 8.4 Free bonus

**Every crash is a coverage sample.** Each one writes a fresh stream-13 table. After any session
that crashes, re-run `python pdataunion.py` — seconds, monotone improvement. `statecov.py` then
tells you which *states* are worth an image dump.

---

## 9. Method note for the record — name the pattern

FK-2, FK-3 and FK-4 are **the same error, three times**. They were found by three different
dimensions of the S101 audit and written up as three unrelated false-knowns. They are not
unrelated.

### The pattern: **Artifact-as-Axiom**

> **An instrument's artifact — a null or low result produced by the measurement method — is
> recorded as a structural property of the target.**

Every one of them has the identical anatomy:

| | instrument | its blind spot | the artifact | promoted to |
|---|---|---|---|---|
| **FK-2** | live RPM property walk of `UPlayerInput` | can only see UPROPERTYs on the class it walks | 0 mappings found | *"there is no legacy input path"* |
| **FK-3** | coverage manifest counting **non-zero bytes** | legally-zero bytes read as gaps | `.rdata` "63.12%" | *"13.9 MB permanently unreadable; two techniques dead"* |
| **FK-4** | **ASCII-only** string search | UTF-16 literals are invisible | 0 module-range hits | *"the packer encrypts `.rdata`; string-xref is defeated"* |

In all three the measurement was **correct** and the *generalisation* was not. That is what makes
the pattern dangerous: there is nothing wrong to find in the evidence. FK-3's source file even
carried its own disclaimer (*"coverage counts NON-ZERO bytes"*) one line below the quoted number.

### The tell

**A negative result that is cheap to produce and expensive to disprove.** "X is absent",
"Y is unreadable", "Z is encrypted". Positive claims get challenged because someone tries to use
them; negative claims close a route and are never revisited — the route is closed, so nobody
looks.

### The three-question check, before any absence goes in the record

1. **What would this instrument show if the thing WERE present, in a form it cannot see?**
   (Different encoding, different class, different section, different metric, different artifact.)
   If the answer is "the same thing it just showed" — the result is about the instrument.
2. **Is there a second instrument that would answer the same question differently?**
   FK-3 was falsifiable by the nine dump manifests already on disk saying `100.0% READABLE`.
   FK-4 was falsifiable by re-reading the same RVAs in UTF-16.
3. **Am I recording a measurement or a law?** Write *"the ASCII scan found 0"*, not *"the strings
   are encrypted"*. The first is durable; the second is a prediction about every future scan.

### A second, adjacent shape: **Unrepresentative-Sample-as-General-Fact**

Caught twice this session, both times before it hardened:

- `strxref`'s **97.2% attribution accuracy** was measured against 36 addresses recorded over 101
  sessions of live RE — i.e. large, heavily-called, vtable-referenced functions, exactly the ones
  a prologue heuristic finds. Against 342,446 real functions it is **56.4%**. The README's own
  worked example was a casualty (`0x55DB370` is 51 bytes; the heuristic's 848-byte extent merged
  four functions and attributed all 10 messages to one). **Corrected in place.**
- A "false-split rate of 0.92 candidates/function" was computed and nearly reported — then
  dropped, because function *lengths* were unknown at the time, which would have made it an
  artifact. That is the check working.

### Instances caught early this session — the pattern is live, not historical

- The UE class-name scan resolved 732 / 1,258 classes because it was **ASCII-only**; class names
  are UTF-16. *Literally FK-4 again, five hours after retracting FK-4.*
- `FClassFunctionLinkInfo{fn,name}` vs `FNameNativePtrPair{name,fn}` are locally identical; a
  phase error produced 16,458 entries in which every name was attached to the **next** function.
  It looked perfectly plausible. Caught only by an *external* check (class arity 69).
- Three addresses in an active plan doc looked wrong; ICF folding meant **all three were
  correct**. Reporting them would have "fixed" correct records.
- A stack frame was attributed to a function whose strings are *"Your connection to the host has
  been lost"* — and a disconnect story was one keystroke away. The query address lay **past that
  function's extent bound**. Recorded as *not identified*.
- The brief for this document contained a fourth instance of FK-4's own shape (§1.4).

### The standing rule this yields

> **A zero-reference string, a missing `.pdata` entry, a class with no matching property, and a
> page of zeroes all mean the same thing: *this instrument, in this state, saw nothing.* None of
> them mean the thing is absent.**

Corollary, and the reason §8 is the most valuable section of this document: **the way to
disprove an absence in this project is almost always to change the state the game is in, not to
work harder offline.**

---

## 10. Reproduce everything here

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py --rebuild            # ~20 s -> index/strxref.idx (18.2 MB)
python strxref.py validate             # 21 checks, incl. the FK-3 section table + FK-4 probes
python vtables.py scan                 # ~3 s ; python vtables.py verify -> 7 checks
python pdataunion.py                   # 382,282 exact bounds from 70 crash minidumps
python uereflect.py                    # ~90 s -> 32,066 UE reflection symbols
python harvest_addrs.py ; python name_addrs.py   # -> docs/symbols.csv
python subsystems.py ; python statecov.py ; python yield.py
```

`index/` is git-ignored and rebuilds in minutes — **except** `pdata_union.*`, which depends on the
2.0 GB `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` directory surviving. Keep it, or commit
`pdata_union.bin`.
