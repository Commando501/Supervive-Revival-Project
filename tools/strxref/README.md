# strxref — offline string census + string→code xref index

Stdlib-only Python, no live process, no injection, read-only. Operates on
`dumps/merged.dump.exe` (the flat `usmapdump dumpimage`/`mergedumps` image where
**file offset == RVA**).

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py --rebuild          # ~20 s, prints the full self-validation
python strxref.py census
python strxref.py find "<substring>" [-n N] [--regex] [--refs-only]
python strxref.py xref 0x<string_rva>
python strxref.py func 0x<code_rva>  # <-- the killer mode
python strxref.py native "<UFUNCTION name>"   # name -> exec thunk -> implementation
python strxref.py nattable 0x<slot> [--impl]  # a class's whole UFUNCTION list
python strxref.py near 0x<string_rva> [-n N]  # same-translation-unit neighbours
python strxref.py validate
```

Index lands in `index/strxref.idx` (18 MB). Load 0.03 s, every query sub-millisecond.

---

## Why this exists: FK-3 and FK-4 are both FALSE

Two CRITICAL false-knowns in `docs/ignorance-map-s101.md` had retired two static
techniques and underwrote the project's *"static analysis is packer-blocked"* posture.
Both were **measurement artifacts recorded as structural facts**. Run `--rebuild` and
the numbers print themselves.

### FK-3 — *".rdata union is capped at 63.12% and IS structural … ~13.9 MB permanently unreadable"*

**FALSE.** The claim conflates two different metrics.

| section | vsize | pages | zero pages | **non-zero bytes** | **readable pages** |
|---|---:|---:|---:|---:|---:|
| `.text`  | 124,030,976 | 30,281 | 14,448 | 48.05% | **52.29%** |
| `.rdata` | 37,212,160  | 9,085  | **33** | 63.12% | **99.64%** |
| `.data`  | 7,274,496   | 1,776  | 327    | 36.83% | 81.59% |
| `.pdata` | 6,283,264   | 1,534  | 1,534  | 0.00%  | 0.00% |
| `.reloc` | 2,867,200   | 700    | 0      | 97.42% | 100.00% |

`.rdata` is **99.64% readable** — 33 zero pages out of 9,085. The quoted "63.12%"
counts **non-zero bytes**, so vtable null slots, `nullptr` entries and inter-literal
padding read as "gaps". The "~13.9 MB permanently unreadable" is null padding.

The byte metric *is* sound for `.text` (48.05% non-zero vs 52.29% readable pages —
they agree, because demand-decrypt zeroes **whole pages**). Applying it to `.rdata`
is the error.

### FK-4 — *"the packer decrypts .rdata strings to the heap and leaves the module copy encrypted, so LEA → string xref is defeated"*

**FALSE.** The module's own `.rdata`, as read by RPM, is plaintext. All five strings
the record named as unreadable read back verbatim:

```
0x079E02D0 U 'Toc signature hash: %s'                                    xrefs=1
0x08B1C688 U 'ULokiGameFeatureToggles::Get %s called when feature …'     xrefs=4
0x08970FA0 A 'GetFeatureTogglesReady'                                    xrefs=1
0x08A56F38 A 'MulticastSetGameFeatureToggle'                             xrefs=0 (3 data pointers)
0x08077F9E U "Login: Couldn't spawn player controller of class %s"       xrefs=1
```

**Where FK-4 came from — two mechanisms, both measured:**

1. **The prior scans were ASCII-only.** `.rdata` holds **85,692 UTF-16LE strings**
   (min-len 6) that no ASCII scan can see. UTF-16 is where the interesting content is.
2. **Scanning the on-disk exe instead of the live image.** The on-disk
   `SUPERVIVE-Win64-Shipping.exe` **is** packed: only **634 of 9,085** `.rdata` pages
   (6.98%) match the dump. A static scan of the file on disk genuinely does see
   garbage. The *live/dumped* copy does not. That distinction is the whole
   false-known.

---

## The real cap — and it is not what FK-3 said

Index built against `dumps/merged2.dump.exe` since 2026-08-14 (S121). Both columns shown —
the `merged` column is the historical FK-3/FK-4 round, kept so the gain is legible.

| | merged (52.29% `.text`) | **merged2 (54.95% `.text`)** | delta |
|---|---:|---:|---:|
| ASCII, exact start | 12,857 / 103,002 = 12.5% | 13,040 / 103,002 = 12.7% | +183 |
| **UTF-16, exact start** | **42,213 / 85,677 = 49.3%** | **42,663 / 85,677 = 49.8%** | +450 |
| UTF-16, + interior + pointer-table | 55,473 = **64.7%** | **56,873 = 66.4%** | **+1,400** |
| ASCII, full index | 14,518 = 14.1% | 14,705 = 14.3% | +187 |
| strings with >=1 code ref (all enc, min_len 4) | 71,853 / 199,783 = 36.0% | **73,394 = 36.7%** | **+1,541** |
| function entries inferred | 250,512 | 259,751 | +9,239 |
| refs resolved | 151,366 | 155,121 | +3,755 |

⚠ **The string COUNTS are identical in both columns** (199,783 total; 103,002 ASCII; 85,677 UTF-16)
because `.rdata` is byte-identical between the two images. That is the control: only the
`.text`-derived rows may move. Same for the 104,903 vtable runs and the 32,066 reflection RVAs.

`.text` readable-page fraction: **54.95%** (was 52.29%). 16,638 / 30,281 decrypted pages.

★ **Realised yield: 1.69 newly-lit strings per newly-decrypted page** (1,336 UTF-16 over 792 pages)
— the LOW half of `docs/fk3-fk4-settled.md` §8.2's measured 0.84–3.90 band. Frontier pages are
thinner than average: they carry **11.52 function entries/page vs 15.82** and **4.74 string refs/page
vs 9.56** for pages already covered. Budget new captures on the low end of that band.

UTF-16 resolution tracks `.text` decryption almost exactly ⇒ **essentially every
string whose emitting code is decrypted IS successfully xref'd; the technique runs at
full efficiency.** The cap is **`.text` demand-decrypt, not `.rdata`**, and it is
**not structural** — it lifts as the game executes more code.

> **To lift it:** `usmapdump dumpimage` from a state whose code has **never executed** — a live
> match, drop phase, hero select, end-of-game. ⚠ **Menu substates are SPENT** (MEASURED 2026-08-14):
> `menu`/`store`/`roster`/`missions`/`loadout` contribute **0 new pages each**; they were five
> snapshots of one process lifetime, and `.text` decryption is monotone within a lifetime, so they
> are strictly nested. `merged.dump.exe` is byte-identical to `dumps/loadout` in `.text` and
> `.rdata`; its four extra inputs contributed 1,195 bytes, **all of them in `.data`**.
> Then `usmapdump mergedumps dumps/merged2.dump.exe dumps` (never overwrite `merged.dump.exe` — this
> index was validated against it) and `strxref.py --rebuild --dump …/merged2.dump.exe`.
> **`merged2` is at 16,625 / 30,281 pages (54.90%)** vs merged's 15,833 (52.29%);
> see `docs/fk18-fk19-multistate-merge-settled.md`.

**S102 quantified all of that — see `docs/strxref-state-coverage.md`:**

- `merged.dump.exe` *did* merge correctly; all five inputs were the same menu state 4 minutes
  apart. Re-merging everything on disk (incl. the 4 never-merged dumps) gives **+602 pages →
  54.27%**. Another menu-surface dump is worth **+0 pages, measured**.
- The crash minidumps show a crash-era process had **62.45%** of `.text` decrypted — an image
  dump from that state is worth **+3,430 pages (+13.4 MB)**, 5.7× the whole re-merge.
- ⚠ `mergedumps` **rejects different-`ImageBase` inputs, and that rejection is wrong for
  `.text`**: 0 base relocations point into `.text`, and `rcb` (different base) is
  byte-identical to `merged` on all 15,215 shared pages. Since ASLR rebases most launches,
  the current rule silently discards every cross-session capture. Fix `mergedumps.go:154`
  before planning a capture campaign.
- Marginal yield, measured on real new pages: **0.84 newly-lit strings per page** (lower
  bound, same-state family); rarefaction slope within the decrypted population: **3.90/page**
  (the right model for disjoint new subsystems).
- Darkest subsystems, by lit rate: Chaos physics 19.3%, drop/deploy 25.8%, replay 30.3%,
  beacons 30.7%, **character movement 35.1%**, **replication/netcode 35.9%**, **GAS 39.3%** —
  i.e. exactly the project's open blockers.

**A zero-xref result NEVER proves absence.** It means one of: the emitting page is not
decrypted; the string is reached through a struct base (see Limitations); or nothing
references it.

The low ASCII rate (12.5%) is not a failure either — most long ASCII runs in `.rdata`
are not code-referenced string literals (they are name tables, asset paths and data
blobs reached by index, not by `lea`).

---

## Also established

- **MSVC RTTI is STRIPPED** — zero `.?AV`/`.?AU` type descriptors in `.rdata`. A vtable
  dump gives shape and slot targets but **not class names**.
- ~~**There is no unwind table anywhere.**~~ **SUPERSEDED (S102) — the unwind table has been
  RECOVERED.** The statement about the *image* stands: live `.pdata` is 100% zero, on-disk
  `.pdata` is packer-encrypted (0 of 523,605 candidates structurally sane, Exception
  data-directory nulled). But SEH still has to work, so the packer publishes the real table
  as a **dynamic** function table — and `MiniDumpWriteDump` serialises those into
  **stream 13**. 70 of the 85 crash minidumps under
  `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` carry it (524,439 slots each, identical count).
  `pdataunion.py` unions them into **382,282 exact, non-overlapping function bounds**
  (54.7% of `.text`), verified against **13/13** project-recorded addresses as EXACT
  entries. See `docs/strxref-state-coverage.md` §4. `func` now reports EXACT bounds when
  the table covers the address, and the old inferred upper bound otherwise.
- **x64 code here is 100% RIP-relative.** Of 1,501,710 absolute qword pointers in the
  image, **not one** lies inside `.text`. There are no `mov r64,imm64` address loads, and
  32-bit absolute forms are impossible (ImageBase 0x7FF6AF000000 > 4 GB).

---

## What it indexes

**1. String census** — `.rdata`, `.data`, `_RDATA`, `.rodata`, `.rsrc`
(`.text`/`.pdata`/`.reloc` measured to carry none). Default `--min-len 4`; the
established census used 6 and is reported separately for comparison.

| section | ASCII | UTF-16 |
|---|---:|---:|
| `.rdata` | 110,577 | 87,734 |
| `.data` | 1,151 | 69 |
| `_RDATA` | 194 | 0 |
| `.rsrc` | 10 | 47 |
| `.rodata` | 0 | 1 |
| **total** | **111,932** | **87,851** |

**UTF-16 start correction (load-bearing).** A naive maximal-run scan over-extends a wide
string backwards by exactly one character whenever it is immediately preceded by an
ASCII literal — that literal's last char plus its NUL form a valid `(printable, 0x00)`
pair and get absorbed. Seen live: `'eBP_Initialize'` for `L"BP_Initialize"` (preceded by
`"BP_Deinitialize\0"`), `'p%02X '` for `L"%02X "` (preceded by `"…CompressionUtil.cpp\0"`).
A genuine wide-literal start is always preceded by `0x00`, so:

```python
while d[s-1] != 0x00:  s += 2      # converges in one step
```

Measured: 1,286 runs corrected, **+580 more strings resolve to code by exact start**.
The preamble's 41,633 UTF-16-referenced figure was itself depressed by this bug.

**Overlap rule.** UTF-16 wins: an ASCII run **fully contained** in a UTF-16 interval is
dropped; partial overlaps are kept (genuinely two data items sharing a boundary). There
are **zero** start-RVA collisions between the two sets.

**2. Xref index** — 151,366 resolved references.

Addressing forms were **measured before inclusion** (`.rdata` targets landing on a string start):

| form | matches | → `.rdata` | string hits | verdict |
|---|---:|---:|---:|---|
| `lea r64,[rip+d32]` `48/4C 8D` | 517,515 | 245,894 | **113,060** | included — 99.97% of all hits |
| `mov r64,[rip+d32]` `48/4C 8B` | 134,564 | 269 | 8 | included (near-free) |
| `cmp r64,[rip+d32]` `48/4C 3B` | 1,450 | 282 | 5 | included |
| `mov [rip+d32],r64` `48/4C 89` | 55,922 | 0 | 0 | excluded — `.rdata` is read-only |
| `call [rip+d32]` `FF 15` | 22,721 | 20,750 | 0 | excluded — that is the IAT |
| `lea r32` / `mov r32` (no REX) | 19,640 | 397 | 17 | **excluded** — +0.015% for a much higher FP rate |
| REX.B `49/4D 8D` | +7 | 0 | 0 | excluded — pure noise |
| `mov r64,imm64`, `push imm32` | — | — | 0 | impossible / measured zero |

- **Absolute qword refs**: 1,501,710 found image-wide by locating the pointer's 3 constant
  high bytes with `bytes.find` (C speed), then validating the full qword — catches
  unaligned pointers too. 242,521 of them hold a string address.
- **One level of indirection**: string ← qword slot ← `lea`/`mov` from code. Yields 20,828
  table-driven references (`ptr-tbl` kind), e.g. message tables indexed at runtime.
- **Interior references are real and are resolved.** MSVC peels the first character of a
  literal comparison — `cmp ecx,0x43` (`'C'`) / `jne` / `lea rdx,[L"CrashReportClient"+2]`.
  Measured: 5,473 interior refs, 5,308 at exactly +2. `xref` on an interior RVA reports the
  enclosing string and the offset.

**3. Function attribution** — 250,512 entry candidates from four independent signals:

| signal | count | note |
|---|---:|---|
| `E8 rel32` call targets | 107,810 | with distinct-caller multiplicity |
| absolute fn-pointers in data | 206,991 | vtables + function tables; 98.5% 16-aligned |
| post-`int3` 16-aligned starts | 6,824 | weak here — this build barely pads (only 6,910 `CC CC` runs in 124 MB; functions are packed back-to-back, the byte before an entry is most often `C3`) |
| strong-prologue sweep | 106,526 | 16-aligned + unambiguous MSVC prologue + legitimate preceding byte |

Tiers: **HIGH** 157,581 (pointed-at or multiply-called, *and* prologue, *and* 16-aligned) ·
**MED** 84,207 · **LOW** 8,724. `func_of` uses MED+ by default. Density is 1 entry per 259
bytes of decrypted `.text` — plausible for x64.

> The prologue sweep exists because measurement found real, heavily used entries no other
> signal sees: **ProcessInternal** (`base+0x13454A0`, the project's keystone hook target) is
> not an `E8` target, is in no vtable, and has no `int3` padding.

---

## Attribution accuracy — how it was measured

> ### ⚠ CORRECTED (S102): 97.2% was measured on an unrepresentative sample
>
> The 36-function ground truth below is real, but it is **biased**: 101 sessions of live RE
> recorded large, heavily-called, vtable-referenced functions — exactly what the heuristic
> finds. Scored against the **recovered unwind table** (382,282 real functions, see above):
>
> | | measured |
> |---|---|
> | recall, MED+ candidates, over 342,446 real functions with a decrypted entry page | **56.4%** |
> | `func_of` resolves to the true entry (6,000 random functions) | **56.8%** |
> | MED+ candidates that are not any known function start | 20.0% |
> | reported extent / true size | median 1.05×, p75 1.28×, **p90 7.68×, p99 64×** |
> | extents overstated by > 2× | **21.0%** |
>
> Same failure mode as FK-3/FK-4: a sound measurement on an unrepresentative sample recorded
> as a general fact. **Use `pdata_union.csv` bounds; the heuristic is the fallback for the
> 45% of `.text` no crash process ever decrypted.** Reproduce with `python pdatascore.py`.

Ground truth is **external and independent**: 42 function entries recorded across ~101
sessions of *live* RE (CLAUDE.md + `docs/`), hand-verified, never produced by this tool.

**6 of the 42 lie in pages this dump never decrypted** (all-zero 4 KB page). No detector
can find those; they are excluded from the denominator and listed explicitly, because
scoring them as attribution failures would misattribute a *coverage* limit to the
*algorithm*.

```
[GT-1] known entries self-attribute (func_of(E) == E):  35 / 36 = 97.2%
       MISS 0x57C8130 battlepass OnSuccess       -> 0x57C80F0
[GT-2] entry+8 attributes back to the entry:            35 / 36 = 97.2%
[GT-3] interior->entry: 0x57CACF5 -> 0x57CA670  OK   (documented gate, 1,669 bytes in)
[GT-5] known NON-entry 0x2976FF0 -> 0x2976F70   (reports the containing function)
[GT-4] 4 data addresses (vtable, UFunction obj, CDO, AR ptr) -> None  OK  (never invents a function)
```

**The single miss is characterised, not hand-waved:** the function at `0x57C80F0` ends
with a tail-call `E9 rel32` at `0x57C8124`, and the 7 bytes of inter-function filler
(`48 89 44 24 70 55 55`) do not end in a recognised terminator byte, so the prologue sweep
skips `0x57C8130`. A relaxed rule ("a `ret` within the previous 15 bytes") was **measured
and rejected**: +18,456 entries and it still does not catch this case.

**Deliberately NOT claimed: a false-split rate.** An earlier pass measured "candidate
entries within `E+256` of a known entry" (0.92/function) and nearly reported it as
over-splitting — but function **lengths** are unknown in this image, so a candidate 256
bytes in may simply be the next real function. That figure would have been an artifact.
Not claiming it is the whole lesson of FK-3/FK-4.

---

## Self-validation

`--rebuild` and `validate` print a comparison against the figures this tool was asked to
reproduce, plus null controls. Current state: **21 checks, 0 failed.**

Exact matches: ASCII census 103,002 · `lea` count 517,515 · `lea`→`.rdata` 245,894 ·
distinct targets 106,800 · all section metrics.

Three deltas, all reported inline as `EXPLAINED` rather than silently absorbed:

| figure | got | preamble | why |
|---|---:|---:|---|
| UTF-16 strings (len ≥ 6) | 85,677 | 85,692 | start-correction shortens 15 wide strings from 6 chars to 5, below the len ≥ 6 filter. They **are** indexed at min-len 4. Ours is correct. |
| UTF-16 referenced | 42,213 | 41,633 | +580 wide strings now match their LEA target exactly instead of at +2. Ours is correct. |
| ASCII referenced | 12,857 | 12,832 | **UNEXPLAINED** (+25, 0.19%). Inputs are byte-identical (ASCII census and LEA target set both MATCH), and this is a deterministic intersection of those two, independently reproduced by a second implementation. Treat 12,857 as corrected. |

Null controls: a >20-byte string with 0 xrefs stays at 0 · `resolve(0x10)` → −1 ·
`find('zzqqxxjjnotarealstring')` → 0 hits · `func_of(past .text)` → `None`.

The tool **fails loudly**: bad DOS/PE magic, non-AMD64 machine, non-PE32+ optional header,
a section table past EOF, `SizeOfImage` > file size, duplicate string RVAs, and — most
importantly — **any section whose `PointerToRawData != VirtualAddress`**, which is what
stops someone pointing it at the packed on-disk exe and getting plausible garbage.

---

## Worked examples

### 1. Identify an unknown function from its strings

```
$ python strxref.py func 0x536BF8E
entry   0x536A5A0   tier=HIGH   evidence=call>=2,prologue,a16,prev-term
extent  0x536A5A0 .. 0x536F3F0 (20048 bytes) -- UPPER BOUND
155 string reference(s):
  +0x21B    lea      0x08974940 A 'AuthGetMatchStartDetails'
  +0x3A3    lea      0x08975F50 A 'BranchOnFeatureToggle'
  +0x821    lea      0x08978108 A 'ExecuteUnownedGameplayCueAtLocation'
  +0xD6D    lea      0x0897BE28 A 'GetActorsInSphere'
  +0x1277   lea      0x08947110 A 'GetBiomeManager'
  … 150 more
```

A 20 KB function with no symbol becomes, in one call, obviously a **UE reflection
registrar for the gameplay blueprint-function-library class**.

### 2. Find who logs a message — and why exact bounds matter

The **heuristic** version of this example (`--heuristic`) is a good illustration of the
extent problem the recovered `.pdata` fixes:

```
$ python strxref.py func 0x55DB370 --heuristic
entry   0x55DB370   tier=HIGH   evidence=call>=2,prologue,a16
extent  0x55DB370 .. 0x55DB6C0 (848 bytes) -- UPPER BOUND
10 string reference(s):
  +0x96   ptr-tbl 0x08B1C4F0 U 'ULokiGameFeatureToggles::Get %s called on toggle with roles'
  +0x109  ptr-tbl 0x08B1C590 U 'ULokiGameFeatureToggles::Get %s called with invalid world'
  +0x1DA  ptr-tbl 0x08B1C630 U 'ULokiGameFeatureToggles::Get %s called when feature toggles were not ready'
  +0x2FE  ptr-tbl 0x08B1C410 U 'ULokiGameFeatureToggles::Get called out or range'
```

That reads like one function. The real table says otherwise — `0x55DB370` is **51 bytes**
and touches no literals; the messages belong to several *different* functions in the
`ULokiGameFeatureToggles::Get` family:

```
$ python strxref.py func 0x55DB370
extent  0x55DB370 .. 0x55DB3A3 (51 bytes) -- EXACT (minidump stream 13, 70 tables)
no string references in that range.

$ python strxref.py func 0x55DB526
entry   0x55DB526   [.pdata EXACT]   (heuristic said 0x55DB370 -- missed the entry)
extent  0x55DB526 .. 0x55DB665 (319 bytes) -- EXACT
4 string reference(s):
  +0x24   ptr-tbl 0x08B1C630 U 'ULokiGameFeatureToggles::Get %s called when feature toggles were not ready'
  ...
```

The *family* identification was right and is still useful — the strings do name the code —
but "these 10 messages come from one 848-byte function" was an artifact of an 16×-overstated
extent. Measured across 3,406 functions: **21% of heuristic extents overstate the true size
by more than 2×**, and every one of those silently attributes another function's strings.

### 3. String → code, with interior resolution

```
$ python strxref.py xref 0x08B1C688
string 0x08B1C630 U len=74 refs=4 'ULokiGameFeatureToggles::Get %s called when feature toggles were not ready'
       (query is +88 bytes into it -- interior reference)
  4 code reference(s):
    site 0x55DB54A  ptr-tbl  fn 0x55DB526 EXACT (319 B)+0x24 via slot 0x08B1C608
    site 0x55DB586  lea      fn 0x55DB526 EXACT (319 B)+0x60
    site 0x55DB5ED  ptr-tbl  fn 0x55DB526 EXACT (319 B)+0xC7 via slot 0x08B1C6C8
    site 0x55DB624  lea      fn 0x55DB526 EXACT (319 B)+0xFE
```

Note this is a **third instance of the same family of error**: the recorded probe RVA
`0x08B1C688` is 88 bytes *into* a longer string. An exact-start-only lookup reports **0
refs** and invites the conclusion "the emitting code never ran". Enclosing-string
resolution reports **4**, all in one function.

---

## `native` / `nattable` — UFUNCTION name → code (added S103)

UE5 emits **two** generated tables per class, and the layouts are opposite. The
discriminator (`_classify_slot`) was **measured**; confusing them returns a
plausible-but-wrong function address (the *next* entry's constructor).

| table | section | layout | yields |
|---|---|---|---|
| `FClassFunctionLinkInfo[]` | `.rdata` | `{ UFunction*(*Z_Construct)(); const char* Name; }` — **ptr first** | the class's full UFUNCTION list; this entry's ctor at **slot−8** |
| `FNameNativePtrPair[]` | `.data` | `{ const char* Name; FNativeFuncPtr Exec; }` — **name first** | the `execXxx` thunk at **slot+8** |

The exec thunk's last non-helper `rel32` callee is the implementation; helpers are
separated by global `E8` multiplicity (`FFrame::Step` ~12,670 callers, the exec-thunk
implementation ~1). The `.rdata` table is **99.64% readable**, so `native` locates a
function **even when the registering code page is undecrypted** — coverage blocks
*disassembling* the target, not *finding* it.

**Validated twice against independent live-RE ground truth:**

1. `native GetFeatureTogglesReady` → exec `0x5376E00` → impl `0x565E1A0` → `0x55DDA50`,
   whose body is `mov rax,[rax+0x5A0]` / `movzx eax,byte [rax+0xB3]` / `shr al,6` /
   `and al,1`. S89 established exactly that live: *bit6 of
   `[LokiGameState+0x5A0 = ServerAuthConfig +0xB3]`*.
2. `native TryUpdateAbilitySystem` → exec `0x5438C20` → tail-jmp **`0x56CE5F0`**, matching
   S102's live result recorded at `docs/coverage-audit-s101.md:232`.

Useful corollary, measured: if `native <name>` resolves to **`0x00F7EB50`** (`xor eax,eax;
ret`, 58 call sites — the COMDAT-folded `return 0`), the C++ body is an empty
`BlueprintNativeEvent` stub and the logic lives in a Blueprint override. Calling the native
thunk directly will do nothing; dispatch through `ProcessEvent` / `CallBPGuarded` instead.
That is how `ALokiGameMode::SpawnPlayer` was settled — see `docs/strxref-open-questions.md`.

`near <rva>` lists a string's `.rdata` neighbours. MSVC lays a translation unit's literals
out contiguously, so when the target has 0 xrefs (undecrypted page), a neighbour that *does*
resolve anchors you in the same source file.

## Limitations (measured, not assumed)

- **`.text` coverage is the binding constraint.** 47.7% of `.text` pages are zero in this
  dump. Fix by dumping from more game states and re-merging — see above.
- **One level of indirection only, and only at the exact slot.** UE reflection names
  (`FPropertyParamsBase`, `FClassFunctionLinkInfo`) sit inside static structs that code
  reaches by **struct base**, not by the individual slot. Measured on
  `MulticastSetGameFeatureToggle`: 3 absolute pointers reference it (1 in `.rdata`, 2 in
  `.data`), and 8–10 LEAs target the 0x200 bytes before those slots — none exactly.
  For those, use `tools/re/offline_xref.py ptr <rva>`, which scans for absolute pointers
  directly and is the right complement to this tool.
- **Byte-scan, not disassembly.** The `lea`/`E8` scanners are regex over raw bytes, so a
  small fraction of matches are immediates or displacements inside other instructions.
  This is why entries are corroborated across four signals and tiered rather than trusted.
- **Function extents are EXACT where `index/pdata_union.csv` covers the address** (382,282
  functions, 54.7% of `.text`) and an inferred upper bound elsewhere. Build/refresh the table
  with `python pdataunion.py`; check status with `python strxref.py pdata`. A gap in it means
  "never decrypted in any of the 70 crash processes", not "no function there".
- **No class names *from RTTI*.** RTTI is stripped (0 `.?AV`/`.?AU` descriptors). But
  class names ARE recoverable from UE's own `IMPLEMENT_CLASS` boilerplate -- see
  `vtables.py` below, which builds a 3,599-entry class->vtable map that way.
- **`.data` strings are runtime state.** `merged.dump.exe` unions dumps taken at different
  moments, so `.data` content may mix states. `.text`/`.rdata` are read-only and exact.


---

## Companion: `vtables.py` -- vtable census + class naming

Same dump, same index, no live process. See `docs/strxref-vtables.md` for the full
write-up and validation (7 checks, 0 failed).

```powershell
python vtables.py scan                 # ~3 s -> index/vtables.idx + validation block
python vtables.py name ALokiPlayerState
python vtables.py diff ALokiGameMode   # only the OVERRIDES + NEW virtuals vs the base
python vtables.py slotof 0x34AB870     # code RVA -> Class[slot]      (-> ULokiAssetManager[94])
python vtables.py who 0x0888CB78       # vtable RVA -> class
python vtables.py classes Loki -n 100
python vtables.py bench | reflect | stats | verify
```

Headline: **5,061 of 5,077 UCLASSes resolved to a vtable; 3,599 distinct vtables named.**
Method: `L"/Script/<Module>"` pins `UFoo::GetPrivateStaticClass`; its one class-name-shaped
wide string is the name; its LAST `.text` LEA is `InternalConstructor<UFoo>`, which
tail-jumps to the real ctor, whose first vtable LEA is the vtable. Validated against five
class/vtable pairs captured LIVE in earlier sessions (5/5) and against a 4,032-pair
inheritance-similarity control from `schema.txt` (median 97.9% shared slots).

Two corrections it produced:

* `docs/lokiassetmanager-vtable-dump.md:584` records `UMissionsModel` vtable `+0x88ADED0`;
  the correct value is **`+0x8AADED0`** (transcription typo, adjudicated three ways).
* `index/pdata_union.csv` holds **fragment** bounds, not function bounds: 147,176 of the
  382,282 ranges continue the previous one, 129,033 of those at a non-16-aligned address
  (chained `UNWIND_INFO`). Proof: `0x12BF4B0`'s raw range is 17 bytes but its own `jz`
  targets `+0x4B`. Merging unaligned continuations gives **253,249 functions**.
  `vtables.py merged_func()` does the merge; `strxref.true_func()` does not.
