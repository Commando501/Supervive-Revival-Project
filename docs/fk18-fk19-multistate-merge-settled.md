# FK-18 / FK-19 — SETTLED (S121, 2026-08-14)

**FK-18** — *"`merged.dump.exe` is a merged multi-state image"* — **CONFIRMED FALSE, and harder than
the register stated: the merge was a NO-OP.**
**FK-19** — *"`mergedumps` rejects a different ImageBase, therefore `rcb` is unusable"* — **FIXED.**

All offline. Zero launches, zero injections, nothing touched the game.

**The artifact: `dumps/merged2.dump.exe`** — `.text` **16,625 / 30,281 decrypted pages (54.90 %)**
against `merged.dump.exe`'s **15,833 (52.29 %)**, a **strict superset with 0 regressions**, and with a
**coherent** `.rdata`/`.data` instead of a spliced one. `dumps/merged.dump.exe` is left untouched.
Named-import build: **`dumps/merged2.dump.iat.exe`** (1,107/1,107 slots resolved — §11).

⚠ **Every figure in §1–§10 is measured at 16,625 pages.** A live process was caught still running
later the same day and folded in (§11), taking the artifact to **16,638 / 54.95 %**. The +13 does not
change any conclusion here and the body is deliberately left at the state it was measured against.

---

## 0. The two-sentence version

The five inputs to `merged.dump.exe` were five snapshots of **one process lifetime**, and `.text`
demand-decryption is **monotone within a lifetime**, so they are strictly nested and the 5-way merge
bought **0 `.text` bytes and 0 pages**. The rule that forced them into one lifetime — *"mergedumps
rejects a different ImageBase"* — is measured false for `.text` (**0** of the image's **1,403,750**
base relocations target it), so the constraint and the strategy it disabled formed a **self-sealing
loop**: the tool's limitation was written up as a capture rule, and the capture rule guaranteed every
extra capture was worthless.

---

## 1. FK-18's core claim, sharpened

FK-18 said the seed contributed 88,854,234 bytes and the other four contributed 1,195 bytes total
(0.0013 %). True — and the reason is stronger than "the states were similar".

| | |
|---|---|
| Seed identity | **`dumps/loadout`** — nobody chose it; the alphabetical directory walk did. `merged.dump.exe` differs from it by exactly **1,195 bytes, every one in `.data`**; `.text` diff **0**, `.rdata` diff **0**. |
| Capture window | All five from **PID 4080**, 2026-07-17 **15:22:19 → 15:26:32** — a 4-minute window at the menu. |
| Nesting [M] | `menu ⊂ store ⊂ roster ⊂ missions ≡ loadout`. Pages lost at any step: **0**. `missions` and `loadout` are **byte-identical in `.text`**. |
| Marginal pages | menu 15,739 → store **+42** → roster **+50** → missions **+2** → loadout **+0**. |
| Union of the five | **15,833 pages** = `loadout` alone. **The other four are worth 0 extra pages.** |

⇒ **The published "48.05 % `.text`" is literally the `loadout` single dump.** The multi-state merge
strategy was never executed, exactly as FK-18 said — but the mechanism is *monotone decryption within
a process lifetime*, not "the states were too alike". That distinction is what makes it actionable:
**capturing N substates of one launch is worth exactly one dump, always, by construction.**

---

## 2. FK-19 — the ImageBase rule, measured

The base-relocation directory (RVA `0xA725000`, size `0x2BBF14`, 100 % readable in every dump; parsed
independently out of `menu`, `tutorial-hero` and `rcb` with byte-identical results):

```
6,671 blocks · 1,406,798 entries · 2,866,964 of 2,866,964 bytes consumed, 0 malformed
  type  0  IMAGE_REL_BASED_ABSOLUTE (padding)  :     3,048
  type 10  IMAGE_REL_BASED_DIR64               : 1,403,750
  types 1-9 : 0 each  -> every real fixup is a full 64-bit qword

DIR64 entries by target section
  .text   :         0     <-- the decisive number
  .rdata  : 1,257,732
  .data   :   146,018
  .pdata, .msvcjmc, CPADinfo, .rodata, _RDATA, .rsrc, .reloc : 0 each
  check: 1,257,732 + 146,018 = 1,403,750
```

**A `.text` rebase is not invasive — it is EMPTY.** And the empirical check agrees exactly: over **10
of 10** pairwise comparisons against `menu` (7 same-base + 3 cross-base), `.text` has **0 differing
bytes** on every page both dumps decrypted (15,199–15,739 shared pages per pair).

**Positive control (the noise floor).** `menu` vs `toggles`, same base, different processes 4 days
apart: `.text` **0** differing bytes over 14,764 shared pages. Six further same-base controls, all 0.

**Negative control (is the reloc parser real?).** 200,000 reloc-listed `.rdata` slots sampled; 149,399
hold `.text` pointers, and **149,399 of 149,399** differ by exactly the base delta, 0 exceptions. Named
instance: `.rdata 0x0764C3E8` → `.text 0xF7EC20`, FK-1's `xor eax,eax; ret` empty impl.

**The only unexplained bytes are the IAT, and they are explained.** Cross-base `.rdata` diffs outside
`0x764A000–0x764D000` = **0** in all four pairs. Inside it, 1,107 slots hold *other modules'* addresses
carrying *their* ASLR (`ntdll` delta `0x42D400000`) — and **1,107 is set-identical to `deobfimports`'
independently recorded 1107/1107**.

---

## 3. What the fix is, and why it is not "rebase then merge"

Because `.rdata`/`.data`/`.pdata` gain **+0 non-zero pages from every one of the 10 donors**, there is
nothing outside `.text` to merge. So `tools/usmapdump/mergedumps.go` now:

- merges **`.text` only**, **page-granular**, **ignoring ImageBase entirely** (a 4 KiB page is copied
  whole or not at all, so two donors can never interleave inside one page — safe *by construction*,
  not merely safe by measurement, and it survives a future game patch);
- requires an **identical section table** instead of an identical ImageBase — that is what actually
  proves two files describe the same build;
- checks every donor against the accumulator on the pages both hold and **rejects** a donor that
  disagrees (`-force` overrides). Every donor in the current corpus reports **0 (clean)**;
- picks the directory-walk seed as **the best-covered input at the corpus's most common ImageBase**
  — see §5;
- prints **both metrics** per section, labelled, so FK-3's error cannot recur silently.

`-wholeimage` restores pre-S121 semantics; `-samebaseonly` restores the old rejection. **Both rollback
paths were TESTED, not assumed** — and `-wholeimage` over the five original inputs (seed `loadout`)
reproduces `dumps/merged.dump.exe` **byte-for-byte**:

```
merged.dump.exe     sha256 9dbdb6aa5154392a4c6b42a4976c58716bb65bd6a3f837294ea15f32094aaf9a
-wholeimage rebuild sha256 9dbdb6aa5154392a4c6b42a4976c58716bb65bd6a3f837294ea15f32094aaf9a
per-input contributions: 910 + 107 + 124 + 54 = 1,195 bytes   <- the historical manifest, exactly
```

That single test does three jobs at once: it proves the rollback is real, it independently confirms
the seed was `dumps/loadout`, and it shows the historical artifact is exactly reproducible from the
new code. `-samebaseonly` correctly rejects `tutorial-hero` with the old message.

★ **A side effect worth naming: merging `.text` only makes `.data` coherent again.** The old
whole-image fill spliced writable globals from four snapshots minutes apart into the seed, so a global
read out of a merged image could be a value that never simultaneously existed — and *which* value you
got depended on the seed, i.e. on **directory-walk order** (MEASURED: **4,678** `.data` bytes change
identity from seed choice alone). `merged2`'s `.rdata`/`.data` are byte-identical to its single seed.
Verified: `merged2` vs `merged` — `.text` +2,958,085 newly filled / **0** changed; `.rdata` **0/0**;
`.data` 1,195 changed, which is exactly the old splice being **undone**.

---

## 4. The result

```
.text decrypted pages (4 KiB, non-zero == executed), out of 30,281
  merged.dump.exe   (S104, 5 menu substates, 1 lifetime)   15,833   52.29%
  merged2.dump.exe  (S121, all 11 state dumps)             16,625   54.90%    +792 pages
  non-zero .text bytes                    59,599,258 -> 62,557,343  (+2,958,085)
```

Attribution of the 792 added pages (a page can come from several donors):

| donor | covers | of which ONLY it has |
|---|---:|---:|
| tutorial-hero | 570 | **165** |
| toggles | 539 | **80** |
| rcb | 270 | **13** |
| lobby-dispatch-decrypted | 29 | **21** |
| vmbuild | 7 | **5** |
| accountpass | 1 | 0 |
| menu / store / roster / missions / loadout | 0 | 0 |

**246 pages are reachable ONLY because cross-base merging now works** (tutorial-hero 212, rcb 56,
lobby-dispatch 26 measured against the same-base union).

### Pre-registration held

Agent B computed, *before* the tool was run, that an 11-way union would give **62,557,343 non-zero
`.text` bytes / 16,625 pages**. The merge produced **62,557,343 / 16,625** — exact to the byte. Its
falsifiable sub-prediction that `menu`/`store`/`roster`/`loadout`/`accountpass` would each add **0**
also held exactly. `coverage-audit-s101.md:325`'s **+2,044,822 bytes / 49.70 %** for the same-base
subset likewise reproduced to the byte.

### The new pages are real code, with controls

Linear capstone disassembly, 200-page random samples:

| arm | bytes decoded |
|---|---|
| **treatment** — the 792 newly added pages | **83.69 %** |
| positive control — pages already in `merged` | 76.67 % |
| negative control — `.rdata` (data, not code) | 3.12 % |

The new pages decode *better* than the pages the project already trusts, and nothing like data.
Every documented RVA already covered (`ProcessInternal`, `UEngine::Exec`, the mission ingester,
`Lobby::HandleNotif`'s jump table, …) reads **unchanged**; `0x0F7EB50` is still `33 c0 c3`
(`xor eax,eax; ret`) and `0x0F7EC20` still `c2 00 00` (`ret 0`), matching FK-1 exactly.

### What it unlocked

**1,150 named symbol records** (from `tools/strxref/index/uesymbols.json`) became readable — **447 of
them only via the cross-base fix**. The names are the frontier, not the menu:

> `GetCrouchedHalfHeight` · `GetGravityDirection` · `GetMaxAcceleration` · `GetMaxBrakingDeceleration`
> · `GetMaxJumpHeight` · `GetLastUpdateVelocity` · `GetImpartedMovementBaseVelocity` ·
> `GetComponentRelativeVelocityAtTime` · `GetHealth` · `GetMaxHealth` · `GetLivingState` ·
> `IsEnemyTeam` · `GetInventory` · `GetItemFromSlot` · `CanJump`

**Character movement is one of the DARK subsystems `fk3-fk4-settled.md` §8.3 names (35.1 % lit)** and
the subject of the open S81 CMC blocker. The discarded dumps were sitting on it.

---

## 5. Seed choice is load-bearing — and it nearly bit

In `.text`-only mode the seed supplies `.rdata`, `.data` **and the output's ImageBase**. The obvious
policy — "seed from the best-covered dump" — picks `tutorial-hero` and silently moves the canonical
image to base `0x7FF6505C0000`. Several offline tools **hardcode** `IMAGEBASE = 0x7FF6AF000000`
(`tools/re/offline_xref.py:35`, `offline_disasm.py:13`, `fk13img.py:57`, `cheat_impl_census.py:323`).
Every `.text` byte would still be correct while every absolute pointer those tools read out of
`.rdata`/`.data` shifted — a failure that yields **plausible wrong RVAs, not an error**.

⇒ the seed is the best-covered input **at the corpus's plurality ImageBase**, so the canonical image
stays where the tooling already points. Recorded here because the safe-looking choice was the wrong one.

---

## 6. The `.rdata` standing rule is retracted

CLAUDE.md and `docs/fk13-console-exec-settled.md` carried: *"run every `.rdata` presence/absence claim
against `dumps/tutorial-hero/…` (`.rdata` 100.0 %), never `merged.dump.exe` alone (63.1 %)."*

**That compares two different instruments.** 100.0 % is `dumpimage`'s **readable-byte** figure; 63.1 %
is `mergedumps`' **non-zero-byte** figure. It is **FK-3 re-committed under a new section name**, three
sessions after FK-3 settled.

MEASURED: all 11 state dumps *and* `merged.dump.exe` have the **same 33 all-zero `.rdata` pages of
9,085, at the same RVAs** — symmetric difference **0**, 99.64 % readable-by-page everywhere. Direct
byte comparison, tutorial-hero vs merged: net tutorial-hero advantage **2,907 bytes of 37.2 MB
(0.0078 %) and 0 pages**, and **6,760 of the 6,761** differing positions sit at offset ≡ 2 (mod 8) —
byte 2 of an 8-byte image pointer, i.e. **relocation, not coverage**.

⚠ **FK-13's conclusions are unaffected.** Its own table records both images agreeing **8/8 controls
present, 0/5 markers present** — that agreement is the control that falsifies the rule's stated
reason, and it was printed in the same document as the rule.
⚠ `.rdata` **pointer values** genuinely do differ across bases (2,518,801 bytes merged vs
tutorial-hero). Read pointers only from an image whose base you are using.

---

## 7. Negative results worth keeping (each closes a plausible-looking lead)

- **The 378 archived crashpad `.dmp` files are NOT coverage probes.** `pdataunion.py` globs only
  `UECC-*`, which looks exactly like this project's documented crashpad blind spot — but crashpad
  minidumps carry **no stream 13 (FunctionTableStream)**: streams present are 7/15/3/24/6/4/14/16/12/5.
  Positive control: a UECC dump carries stream 13 at **6,522,212 bytes**. The technique needs a stream
  crashpad does not write. *Checked before claiming a defect.*
- **Merging gains nothing outside `.text`** — `+0` non-zero pages from every donor, every section.
- **`.pdata` is 0 non-zero pages in all 11 dumps** while every manifest reports it **100 % READABLE**.
  The readable-vs-non-zero distinction, made concrete in a single section.

### Coverage picture refreshed (read-only; nothing in `tools/strxref/index/` was rewritten)

```
merged.dump.exe   (S104, 5 menu substates)      15,833 pages   52.29%
merged2.dump.exe  (S121, all 11 image dumps)    16,625         54.90%
best single crash-era process                   18,980         62.68%
union of all crash tables (76 usable, was 70)   19,520         64.46%
GRAND union (merged2 + crash tables)            19,742         65.20%
NEVER decrypted or named by anything we hold    10,539         34.80%
```

★ **The merge did not move the frontier — it converted bounds into bytes.** GRAND union moved only
19,715 → 19,742 (+27), because ~765 of the 792 new pages were already *named* by crash unwind tables.
What changed is that we now have **bytes** for them instead of only function bounds. **3,117 pages
remain named-but-byteless.**

> ⚠⚠ **SELF-CORRECTION, same day.** The sentence that followed — *"the cheapest remaining target, and
> reachable only by executing that code"* — was wrong twice, and the decomposition matters:
> - **2,193 of the 3,117 are page-rounding**, not code. A `RUNTIME_FUNCTION` spanning a page boundary
>   marks the whole tail page as "named" even though no function BEGINS there (72.2 % adjacency vs a
>   26.8 % control). Counting *spanned* pages inflates novelty **~3.4×**, and it inflates worst
>   exactly at the decryption frontier — which is where the project reads it.
> - Of the 924 real (BEGIN) pages, **611 are reachable only by CRASHING**, not by executing game
>   code: they are named by ≥90 % of 76 crash processes *including a 30-second staging death that
>   never loaded a map*, while a healthy 108-minute live process holds **3 of 924**.
> ⇒ **The genuinely state-dependent remainder is 313 pages, not 3,117.** And the crash-path 611 are
> not a wall — they are the cheapest capture on the board (§12).

---

## 8. Method notes

1. **A tool limitation became a capture rule became a guarantee of no yield.** `mergedumps` rejected
   mismatched bases; `capture-dumps.ps1` promoted that to *"capture all states WITHOUT relaunching"*;
   one lifetime means monotone decryption means nested snapshots means zero gain. Neither half is
   detectable from inside the other. **When a workflow rule exists to satisfy a tool, check whether
   the tool is right.**
2. **FK-3 §8.0 (S104) had already measured all of this and written the prescription.** *"Fix
   `mergedumps.go` to let a different-base input contribute `.text` … Without this the plan below caps
   out at one session."* It sat unimplemented for ~17 sessions while three cross-base dumps were
   captured and discarded. **A settled doc that ends in a prescription is not settled until someone
   runs it.**
3. **Metrics are instruments.** Four distinct quantities are in play — readable bytes, non-zero bytes,
   non-zero pages, all-zero pages. Every retraction in this file is one of them quoted as another.
   Agent B's cross-check found the sharpest available statement of this: for `.text`,
   `manifest READABLE bytes == (non-zero PAGES) × 4096` with difference **0 in 11 of 11 dumps** — so
   readable ≡ non-zero-pages exactly, and non-zero-*bytes* is a strictly smaller third quantity.

---

## 9. Reproduce

```bash
tools/usmapdump/usmapdump.exe mergedumps dumps/merged2.dump.exe dumps
```

⚠ **Write `merged2`, never overwrite `dumps/merged.dump.exe`** — the `tools/strxref/index/` artifacts
were validated against it. Rollback: `-wholeimage` (pre-S121 semantics) or `-samebaseonly` (old
rejection rule).

**✅ `dumps/merged2.dump.iat.exe` is DONE** — see §11. It needed a live process, one got caught still
running, and producing it exposed two real defects that the cross-base merge had created.

---

## 10. What it bought downstream — the index rebuild (same day)

The whole `tools/strxref/` toolchain was repointed at `merged2` and rebuilt (old index preserved at
`tools/strxref/index.pre-merged2-backup/`). Pre-registered before running; scored after.

| | merged | **merged2** | delta |
|---|---:|---:|---:|
| strings total / ASCII / UTF-16 | 199,783 / 103,002 / 85,677 | **identical** | **0** ✅ control |
| vtable runs · reflection RVAs | 104,903 · 32,066 | **identical** | **0** ✅ control |
| strings with ≥1 code ref | 71,853 (36.0 %) | **73,394 (36.7 %)** | **+1,541** |
| UTF-16 referenced (full index) | 55,473 (64.7 %) | **56,809 (66.3 %)** | **+1,336** |
| function entries inferred | 250,512 | 259,632 | +9,120 |
| refs resolved | 151,366 | 155,121 | +3,755 |
| **crash-table functions with readable BYTES** | 342,763 | **356,402** | **+13,639** |
| **crash-table functions named but BYTELESS** | 39,941 | **26,302** | **−34.2 %** |
| documented ground-truth entries in decrypted pages | 36 / 42 | **41 / 42** | **+5** |

★ **The single best number is the last two rows.** §7 said the merge converts *bounds into bytes*;
in function terms that is **13,639 functions** that the crash tables could name but no image could
show a byte of, and which are now disassemblable. The five ground-truth entries that crossed over are
**tutorial plan A/D/E and input fn A/B** — i.e. exactly the open blockers.

★ **Realised yield: 1.69 newly-lit strings per new page**, the LOW half of §8.2's 0.84–3.90 band.
Mechanism, measured: frontier pages are **thinner** than covered ones — 11.52 function entries/page
vs 15.82, and 4.74 string refs/page vs 9.56. **Budget future captures on the low end of that band.**

### Two predictions missed, and one heuristic got worse

- **Function entries and refs both came in below prediction** (+9,120 vs +10,000–14,000; +3,755 vs
  +5,000–9,000) because the forecast assumed uniform per-page density. It is not uniform — see above.
- **Vtable naming went DOWN by one: 5,077 → 5,076 classes.** Bounded by diffing the indexes: LOST
  `UMovieGraphCollection`; CHANGED `UGameplayTagsDeveloperSettings` (a newly visible
  InternalConstructor candidate won and its anchor weakened from `+0` to `None`) and
  `UReplicationBridge` (`gpsc` moved 336 B, vtable unchanged). **All 5 live ground-truth classes are
  byte-identical and both self-validations pass (strxref 21/0, vtables 7/0).** None of the three is
  load-bearing here — but it is recorded rather than smoothed, because *more information made a
  shape-matching heuristic strictly worse* and that will recur as coverage grows.

### Two instrument faults found and fixed in the process

1. **strxref's self-validation reported 3 failures — none were regressions.** `PREAMBLE`'s `leas` /
   `rdata_targets` / `distinct` are `.text`-DERIVED constants from the FK-3/FK-4 round against
   `merged.dump.exe`, so they *must* rise with coverage; the validator compared them to a fixed
   literal and turned a coverage GAIN into three failures. Attributed instruction-by-instruction
   before being excused: **+10,486 LEAs = 10,485 starting inside a newly decrypted page + exactly 1
   whose `0x48` is the last byte of an old page and whose `0x8d` is the first byte of a new one**;
   **+6,757 `.rdata` targets = 6,750 from new pages + a net +7 from 9 page-STRADDLING leas** whose
   rip-displacement bytes had been in a zero page (7 gained a target, 0 lost). **0 matches lost, 0
   targets lost.** Fixed by pinning those rows per decrypted-page count
   (`PREAMBLE_TEXT_BY_PAGES`), so real drift stays detectable rather than blanket-excused.
2. **`pdataunion.py` printed "…DECRYPTED in merged.dump.exe" while measuring merged2** — a label
   broken by repointing the variable and not the message. Caught only because the number moved and
   the label did not. Now prints `os.path.basename(MERGED)`. ⚠ **Repointing a path constant is not
   the whole edit; the strings that name it are part of the instrument.**

⚠ `docs/fk3-fk4-settled.md` §2.3's "NEVER decrypted by anything we have 10,566 pages / 34.89 %" is
now **10,539 / 34.80 %**, and its images-only row moves 15,833 → 16,625. The crash-table union grew
70 → **76** usable tables, 382,282 → **382,704** functions.

---

## 11. The IAT rebuild — and two defects the cross-base merge created

A `SUPERVIVE-Win64-Shipping.exe` process was still alive when this work ran (PID 45848, base
`0x7FF7C7EF0000` — note that is a **different boot** from `merged2`'s `0x7FF6AF000000`, i.e. exactly
the capture the pre-S121 tooling would have discarded). `deobfimports` needs a live process, so it
was spent on the open item. It failed twice before it worked, and both failures are worth keeping.

### Defect 1 — `deobfimports` read IAT slot values from the DUMP, so a merged image can never resolve

MEASURED: `deobfimports <live proc> dumps/merged2.dump.exe` resolved **8 of 1,107** slots, against a
documented baseline of **1107/1107, 0 undecodable**.

**Mechanism.** `writeReconstructed` walks the IAT reading each slot's value **out of the dump file**,
then asks the resolver to emulate that value as a stub address **in the live process**. A slot's RVA
is image-relative and boot-invariant; a slot's **VALUE** is a pointer into the packer's hidden stub
region, i.e. an address from *the boot that produced the dump*. `merged2`'s `.rdata` comes from its
seed (a 2026-07-17 boot), so every value handed to the emulator pointed at nothing in today's
process, and 1,099 stubs read as "undecodable".

★ **This is a defect the FK-19 cross-base merge introduced.** Before it, every dump came from one
lifetime and the dump's slot values were always the live ones. The moment a merged image can carry
`.rdata` from an older boot, the assumption silently breaks.

**Control that settles it:** the same live process resolved **its own same-boot dump**
(`dumps/heromastery/`) **1,107 / 1,107, 0 undecodable**. Same binary, same code path, only the dump's
provenance varied.

**Fix (`deobfimports.go`, `reconstructiat.go`):** `writeReconstructedFrom` takes an optional
`slotSrc`; `deobfimports` supplies one that reads the slot qword **live** at
`liveBase + slotRVA`, falling back to the dump's value if the live read fails. `reconstructiat` keeps
the old behaviour (it serves unprotected binaries where the dump's values are the right ones).
**Result: `merged2` resolves 1,107 / 1,107, 0 undecodable → `dumps/merged2.dump.iat.exe`.**

### Defect 2 — the exports sidecar was chosen ALPHABETICALLY, and export addresses are per-boot

With defect 1 fixed the run resolved **0** slots. Cause: `findExportsSidecar` falls back to a
recursive walk that took **the first `*.exports.txt` it reached** — for `dumps/merged2.dump.exe` that
is `dumps/accountpass/`, a sidecar from **July**. Export addresses are per-boot, so nothing matched.
The failure surfaced as *"the stubs are undecodable"*, i.e. as a claim about the protector, when it
was really *"you loaded the wrong file"* — the project's signature error shape.

**Fix:** the fallback now picks the **newest** sidecar, prints which one it chose and warns that
export addresses are per-boot, and the `resolved 0` error now names boot mismatch as cause #1 with
the remedy. **Verified both ways:** with the sidecar pinned → 1,107/1,107; with it deleted, the
newest-wins fallback picks the same-boot one and still gets 1,107/1,107 while printing the warning.

### What the live capture itself was worth

`dumps/heromastery/` (that process, menu + the S120 Hero Mastery surfaces) holds **15,672 decrypted
pages** and contributes **+13 pages** over `merged2` — 26 named symbols, all UMG widget accessors and
the login/legal path (`TryLoginWithNexon`, `TryFetchLegalDocument`, `TryAcceptLegalDocument`).
`merged2` is now **16,638 / 30,281 = 54.95 %**.

★ **+13 pages is the point, not a disappointment.** It is a same-day, independent confirmation of the
capture rule this document argues for: **another menu-state dump is worth approximately nothing.**
The measured yield of a menu capture is now 13 pages; the tutorial capture was worth 570. Spend
launches on states whose code has never run.

---

## 12. What triggers decryption, and where the remaining coverage actually is

### 12.1 The decryption trigger — mechanism MEASURED, filter still OPEN

The repo carried **three mutually inconsistent statements** and none had ever been measured:
`dumpimage.go:67` "on **access**", `fk3-fk4-settled.md:137` "on **execution**", `fk10:264`
"*necessarily* … only as they **execute**". All three are the same untested inference from the
encryption model. All three are now corrected in place.

**MEASURED, live, read-only:**

| | |
|---|---|
| Dark page state | **COMMIT / `PAGE_NOACCESS` / MEM_MAPPED** — 15,672 `EXECUTE_READ` + 14,609 `NOACCESS` = **30,281**, exactly the `.text` page count. Only `.text` has NOACCESS pages. |
| Why that matters | `NOACCESS` is **not** execute-only. A read fault and an execute fault are both real faults that both dispatch to user mode. "Only as they execute" is not entailed by anything measured. |
| Granularity | **Page-granular** — 16.1 % of multi-page functions are *partially* decrypted. Whole-function and whole-module models are refuted. |
| Persistence | **Monotonic** — 0 pages reverted over 151 s. No re-encryption sweep. |
| Interception | A **`ProcessInstrumentationCallback`** (entry `runtime.dll+0x8d9040`) that rewrites the kernel return address when it equals `ntdll!KiUserExceptionDispatcher`, redirecting to `runtime.dll+0x8fa370`. **Not a VEH** and **not an ntdll patch** — both refuted. |
| External reads | **RPM on a dark page does nothing: 0 of 200**, against a **200/200** control on decrypted pages. ⇒ **no external tool can ever page these in.** |

**STILL OPEN when written; NOW STRONGLY INDICATED AS EXECUTE-ONLY — see §12.4, flown 2026-08-14.**

**The question as it stood: does a READ fault decrypt, or only an EXECUTE fault?** The discriminator sits inside a
23,826-byte control-flow-flattened function (`0x147acb3–0x14809c5`, `call X; jmp rax`); recursive
descent reached 0.5 %. The only filter readable on that path tests **`ExceptionCode` alone**
(`cmp eax, 0xC0000005`), with AV converging to the same continuation as breakpoint/single-step.

⚠⚠ **DO NOT re-run the "is there a `cmp [X+0x20], 8` test?" scan and believe its zero.** It returns
**zero in `runtime.dll` AND zero in all four control binaries** (ntdll, kernelbase, ucrtbase,
VCRUNTIME140), while the `,0` and `,1` arms of the same scanner find 12/30/34/29 hits. The `==8` arm
has **no positive control anywhere**, so its zero cannot discriminate "absent" from "encoded
differently". Anyone who skips that control will conclude "no access-type check ⇒ reads decrypt" and
build a 14,609-page plan on an uncontrolled negative.

**The pre-registered experiment** (requires injection — the RPM finding forecloses every external
route). SEH only, no C++ EH, **no `.text` write**:

1. `VirtualQuery` up `.text` for the first `PAGE_NOACCESS` page P.
2. `__try { c = *(volatile unsigned char*)P; } __except(EXCEPTION_EXECUTE_HANDLER) { took = 1; }`
3. `VirtualQuery(P)` again; log `took`, `c`, new `Protect`.

**Readout:** Protect → `PAGE_EXECUTE_READ` with `took == 0` ⇒ **READ DECRYPTS**, and one byte read
per dark page followed by one `dumpimage` takes `.text` toward ~100 % with **zero gameplay**.
`took == 1` and Protect unchanged ⇒ **EXECUTE-ONLY**, and coverage stays gated on running more code.

**Mandatory controls in the same run:** (a) the same probe on a decrypted page must succeed;
(b) on an unmapped address must fault; (c) read P's protection from a **second, external** process —
the protector zeroes the in-process TEB instrumentation fields, so in-process stealth state lies.
**Order: probe ONE page, read back, and only then loop.** Hazard: no module-image write (the measured
lethal variable), but it raises a fault inside the protector's own hooked dispatcher and `0x87c910`
range-checks `CONTEXT.Rip` — treat as possibly terminal, use a throwaway `-NoHook` launch, and keep
the OS process handle open across exit so a `0x0000DEAD` exit code is captured.

### 12.2 Where the coverage actually is — the crash path, and nobody has tried it

★★ **Capturing a process DURING crash handling is worth ~2,334 pages** — **25× a tutorial sitting and
180× the live menu process** — and it costs **zero launches**, because runs already die at a known
rate (FK-31 kills 27 % of tutorial launches).

The evidence that this is *crash*-gated rather than *state*-gated is controlled: **611 of the 924
real (BEGIN) novel pages are named by ≥90 % of 76 crash processes, including a 30-second staging
death that never loaded a map**, while the healthy 108-minute live process holds **3 of 924**.

**Recipe:** next time a run dies, `usmapdump dumpimage <faulting pid>` **before it exits**, while
CrashReportClient/crashpad still holds it. Pure RPM. Reports sit `Pending` indefinitely
(`archive-crashdumps.ps1`), so the window is not the 2 s upload attempt.
**Pre-registered prediction:** ≈**18,900** non-zero `.text` pages, contributing ≈**2,300** to a
re-merge. If it lands at ~15,700 like every other dump the crash-path hypothesis is wrong — either
result is worth the zero launches it costs.

**Ranked after that:** a long menu session ended by a clean shutdown (~250 state-dependent pages, one
launch, no shims) · an Angelscript-exercising in-world sitting (the largest *reachable* dark region:
`0x059128B0–0x05A7F070`, 32.5 % lit against a 74.3 % control immediately below it, **170 pages
nothing has ever decrypted**) · a `cheatmgr-any` sitting running all 42 real exec verbs (**no dump has
ever been taken from that state and no crash table covers it** — unknown yield, which is now the most
interesting property a candidate can have) · **a second tutorial sitting for coverage: don't**
(measured ceiling **+34 BEGIN pages**; fly those for FK-31 / simulation work instead).

**Structurally unreachable, and not a tooling problem:** BATTLE / matchmaking (`TryJoinQueue`'s impl
page has never been decrypted by *anything* on record), drop phase (four server-authority functions
are empty impls), combat/GAS (follows from the stubbed `SpawnPlayer`), replication (no server).
**Never reachable at all:** `MeshModelingTools*`, `MovieRenderPipeline*`, `OptimusCore`, `ControlRig`,
`PCG`, `InteractiveToolsFramework`, `VulkanRHI` — editor-adjacent tooling and a wrong-RHI backend in a
shipping D3D12 client, 9.7–36 % lit.

⚠ **`fk3-fk4-settled.md` §8.3's lit-rate table is a STRING lit-rate, not a map of the dark pages.**
The densest instrument available (named-class vtable slots) reaches **9.2 %** of the 13,656 dark
pages. Reading §8.3 as "the dark half is GAS + CMC + netcode" over-generalises: the *labelled* part of
the dark half is dominated by editor and unused-plugin modules no reachable state will ever run.

### 12.4 The probe was flown — two launches, and the answer is STRONGLY INDICATED, not settled

`tools/sigbypass-mod/decrypt_trigger_probe.cpp`, built `-Name decrypt_trigger_probe`, manual-mapped
into a throwaway `-NoHook` launch. Imports **KERNEL32 only**; no `VirtualAlloc`, no
`FlushInstructionCache`, no module-image write of any kind.

**Run 1 — the harness killed the experiment before it ran.** Order was control (a), control (b),
treatment, exactly as specified. Control (a) passed (read a decrypted page, byte `0x62`). Control
(b) — a **deliberate** read of an unmapped address — **killed the process**: the marker stops at
its header, `__except` never returned, and the death left **no artifact at all** (no crashpad
handoff, no `Fatal error` line, no `UECC-*` dir, no minidump).
⇒ ★ **A guaranteed-fault control must never run before the treatment in this process.** That is a
harness bug, not a property of the question, and it cost one launch.
⚠ The exit-code watcher also failed: `$p.ExitCode` returned `$null` because the .NET `Process`
object had not cached the native handle, and the formatter rendered `$null` as
**`0x00000000 "clean exit"`** — a fabricated result from a broken instrument, of exactly the kind
this project keeps recording. Fixed by touching `$p.Handle` before `WaitForExit`, plus an explicit
"UNAVAILABLE — do not read this as a clean exit" branch.

**Run 2 — reordered to (a) → TREATMENT → (b), and the treatment is decisive.**

```
census: EXECUTE_READ 15,275 pages | NOACCESS 15,006 pages          (30,281 total, as expected)
[CTRL-a lit ] rva 0x2000  EXECUTE_READ -> read SUCCEEDED, byte=0x62, protection unchanged
[TREAT dark ] rva 0x1000  ABOUT TO READ ...
              <marker ends; process dies>
EXIT pid=37972 code=-1073741819 (0xC0000005) after 49.9 s -- ACCESS VIOLATION
no crashpad handoff · no UECC dir · no minidump
```

**The exit code is the finding.** `0xC0000005` is an **unhandled access violation** — it is *not*
`0x0000DEAD`, the protector's own `NtTerminateProcess` sentinel (`runtime.dll+0x80f7f0`) that
FK-32 identified as its deliberate anti-tamper kill. So the process was **not** killed for
tampering; it died because a read fault on a dark page went **unserviced**.

That is the argument for EXECUTE-ONLY, and it does not depend on our `__except` working:
the protector's dispatcher **is** installed and intercepting `KiUserExceptionDispatcher` (measured,
§12.1); a read fault on a `PAGE_NOACCESS` `.text` page occurred; and the dispatcher did **not**
decrypt-and-resume. Had reads been a decryption trigger there would have been no unhandled AV at
all — the page would have materialised and execution continued.

**Verdict: EXECUTE-ONLY, strongly indicated. Not yet settled, because of one identified confound.**
The faulting instruction's RIP was inside our **injected module**. A dispatcher that services only
faults originating within the game image would produce this identical result regardless of whether
reads decrypt. That confound is removable and the removal is cheap:

★ **The clean follow-up: make the faulting instruction be the GAME'S OWN CODE.** Find a load gadget
in already-decrypted `.text` (`mov al,[rcx]; ret` or equivalent), point `rcx` at a dark page and
call it via the existing S55 native-call primitive. The faulting RIP is then legitimate game code
and the confound disappears entirely. If that *also* dies `0xC0000005`, EXECUTE-ONLY is settled and
the ~14,600-page lever is definitively dead. One launch.

**Also learned, and worth its own line: SEH does not protect an injected module here.**
`__except(EXCEPTION_EXECUTE_HANDLER)` did not catch either fault, in either run, even though the
manual mapper called `RtlAddFunctionTable` for the module's 0x17E-entry exception table. The
project's standing *"no C++-exception payloads"* rule therefore **extends to SEH**, and this session
already refuted its recorded mechanism (the missing function table — §11 and the `fk10` correction).
⇒ **Treat any fault raised from injected code as terminal.** Do not design a probe that relies on
catching one.

### 12.3 Tooling changes made, and the ones still worth making

**Made this session** (all verified): `-Clear` no longer deletes the dumps root (§13);
`deobfimports` sources IAT slot values live; sidecar selection is newest-wins and announced; the
merge manifest reports both metrics; `capture-dumps.ps1`'s MERGED row reports a real number.

**Still worth making, in value order:**

1. **Resolve the IAT at dump time** into a `<stem>.iatmap.txt`. `dumpimage.go:217-219` skips the
   trampoline region (`MEM_IMAGE` but owned by **none** of the 221 registered modules), which is
   exactly *why* `deobfimports` needs a live process. Fixing it makes every dump self-sufficient.
2. **Second pass over failed pages** in `dumpimage` — the dump is not atomic and decryption is
   monotone, so anything decrypted during the ~1 s window is currently lost. Free, and the recovered
   count is itself a decryption-rate instrument.
3. **Report BEGIN pages, not just spanned pages**, in `statecov.py` / `pdataunion.py`. Spanned
   inflates novelty **~3.4×**, worst exactly at the frontier where the project reads it.
4. **Capture the live dynamic function table.** The process registers all **524,439**
   `RUNTIME_FUNCTION` slots; the crash-table union has 382,704 *materialised* ones. Reading it live
   would give a coverage probe per dump with no crash required. ⚠ [I] how many are materialised live
   is **unmeasured** — do not assume +141,735.
5. `-textonly` / `-delta` output so a rolling capture through a match is affordable, plus a
   log-driven `-WatchLog` trigger. Both only matter once a match state is reachable.
6. An auto-snapshot in `fk24-stage.ps1` between the `spDone` gate and probe injection — but
   **measure the dump's wall-clock under `-SkipProbe` first**; armed windows, not launches, are the
   budget.

---

## 13. The `-Clear` trap

`capture-dumps.ps1 -Clear` did `Get-ChildItem $DumpsDir -Force | Remove-Item -Recurse -Force` over
the **whole `dumps/` root** — **16 GB across 386 entries**, including **363 `crashpad-*` archives**
(the entire FK-7 / FK-8 / FK-31 / FK-32 corpus), `merged.dump.exe`, the usmap archives and the
extractor output. `/dumps/` is gitignored: **there is no undo.** It was documented as the innocuous
*"delete everything under the dumps dir first (fresh session)"* — and this session's own doc rewrite,
*"RELAUNCH BETWEEN CAPTURES"*, made "fresh session" a phrase an operator is now **more** likely to
reach for. The hazard was raised by the change, not merely inherited by it.

Fixed: `-Clear` now deletes only directories containing a top-level `*.dump.exe`, hard-excludes
`crashpad-*` / `merged*` / `*-archive*` / `usmap-*` / `s109-*` / `extractor-out-*`, prints the exact
list and byte count, and requires typing `DELETE`. **Verified:** it offers 12 state dirs / 2.37 GB
and aborts without confirmation; all 386 entries, 363 crashpad archives and `merged.dump.exe` intact.
