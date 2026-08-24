# S140 TIER 2 — ADVERSARIAL VERIFICATION OF LANE 2 (`L2-velocity-field.md`)

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game.**
Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, RVA == file offset (re-verified below).

**Instrument provenance.** Everything below was re-derived with code written for THIS verification —
`scratchpad/s140t2/V2tools/{v2pe.py, v2dis.py, v2cfg.py}` — importing **none** of
`scratchpad/s140t2/{pe,uht,walk,xdis,census}.py`, none of `scratchpad/s140/tools/*`, and not
`tools/cfg.py`. I did not re-run any lane script. My UHT offset field was calibrated from scratch
(record + 0x32, u16) against nine offsets independently pinned by disassembly or prior live RPM.

**Reads by section:** `.text` and `.rdata` of `merged13` for everything except the
`{name,thunk,impl}` triples, which are `.data`. `merged13` is `.text`-only merged so its `.data` is
a single-seed coherent snapshot; I additionally validated the triple decoder on two known answers
before using it.

> **`.text` is 55.48 % decrypted in `merged13`. Every census below is a FLOOR.**

---

## MY CONTROLS (run before any analysis)

| control | result |
|---|---|
| PE flat (all 10 sections `VirtualAddress == PointerToRawData`) | **True** |
| ImageBase | **`0x7FF608F40000`** |
| known-DARK control `0x05A6AC40` page non-zero | **0 / 4096** PASS |
| UHT offset-field calibration, 9 independently-pinned offsets | **9 / 9 PASS** (section 1.A) |
| `.data` `{name,thunk,impl}` triple decoder, 2 known answers | **2 / 2 PASS** (`GetRecentVelocity`, `GetLokiCharacterMovement`) |
| write classification from `operands[0].type == MEM`, never `regs_access` | enforced in `v2cfg.mem_writes` |
| every function disassembled below, page non-zero | 3454-3954 / 4096 PASS |

---

## VERDICT IN ONE LINE

**L2's technical core is SOUND and I could not refute it.** Every load-bearing byte-level claim I
re-derived came back identical, and on its single biggest claim (T3) L2 **under-graded itself** — I
can upgrade that from [I] to [M]. What I did find is **one mis-citation, two headline/body grade
mismatches, one wrong count, one un-checkable attribution, an unquantified FLOOR** — plus a new
operational hazard for the S141 arm that neither L2 nor Tier 1 states.

---

## 1. CONFIRMED — re-derived independently, byte for byte

### A. UHT calibration (my own decoder; offset field at record+0x32, u16)

| name | offset expected (independently pinned) | measured |
|---|---|---|
| `Velocity` | `0xE8` (L2 + `binds_members.csv`) | **0xE8** — and of **31** `Velocity` records image-wide, exactly ONE carries it |
| `CharacterOwner` | `0x198` (Tier 1 disasm) | **0x198** (1 record) |
| `MovementMode` | `0x231` (`IsDashing 0x035E6810`) | **0x231** (1 record) |
| `Acceleration` | `0x328` (S139) | **0x328** |
| `MaxAcceleration` | `0x28C` | **0x28C** |
| `LastUpdateVelocity` | `0x378` | **0x378** (1 record) |
| `RelativeLocation` | `0x158` | **0x158** |
| `Mobility` | `0x1BB` | **0x1BB** |
| `UpdatedComponent` | `0xD0` | **0xD0** |

9 / 9. Then, from the same calibrated decoder:

* **`LastNonZeroDirection2D` — EXACTLY ONE record image-wide, `rec@0x88F2EF0`, Offset `0x12F0`.**
  L2 cited a derived file (`scratchpad/s140/tools/lokicmc_props.txt:48`); it is now derived straight
  from UHT. **[M] CONFIRMED, on a better instrument than L2 used.**
* `GravityScale` — 9 records; `rec@0x7FAF510` Offset **`0x1A0`**. **CONFIRMED.**
* `ComponentVelocity` — 2 records; `rec@0x7EDFD40` Offset **`0x1A0`**. **CONFIRMED** — two classes,
  one offset, exactly as L2 says.
* `UpdatedPrimitive@0xD8`, `PlaneConstraintNormal@0x100`, `PlaneConstraintOrigin@0x118`
  ⇒ the 24-byte-stride argument for `FVector` **CONFIRMED** from three neighbours.

### B. Vtables and the `0xA50` chain

```
ULokiCMC vtable .rdata 0x088F8570   : 449 contiguous .text-valid slots
engine CMC vtable .rdata 0x07FBED58 : 471
slots compared 449 -> Loki targets differing from engine: 69   <- L2's "69 of 449"  CONFIRMED
distinct target functions across both vtables: 454             <- L2's "454"        CONFIRMED
  disp 0x518  Loki = engine = 0x036523F0  (UpdateComponentVelocity, NOT overridden)  CONFIRMED
  disp 0x4D8  Loki = engine = 0x032C9DD0  (StopMovementImmediately, NOT overridden)  CONFIRMED
  disp 0x7B0  Loki = engine = 0x035D5D20  (CalcVelocity, NOT overridden)             CONFIRMED
  disp 0xA50  Loki = 0x0530ABF0           engine = 0x035D6790                        CONFIRMED
```

`0x0530ABF0` disassembles as `cmp byte [rcx+0x16c8],0 / je 0x530AC00 / mov byte [rcx+0x16c8],0 /
jmp 0x035D6790` — **both arms reach the tail jmp**. CONFIRMED.

`0x035D6790`: entry -> `mov rax,[rcx]` -> **`0x035D67B3 call qword [rax+0x518]`** with **no branch
of any kind between the entry and the call**. **[M] UNCONDITIONAL. CONFIRMED.**

`0x036523F0` is byte-identical to L2's listing: `movups xmm1,[rcx+0xE8]` (16 B) +
`movsd xmm0,[rcx+0xF8]` (8 B) -> `movups [rax+0x1A0]` + `movsd [rax+0x1B0]`. **24 bytes, third
component a scalar double.** CONFIRMED.

`0x032C9DD0` writes `[rcx+0xE8]` (16 B) and `[rcx+0xF8]` (8 B) from `.data 0x099C86A0` (measured 16
zero bytes) then `call [rax+0x518]`. My decoder classifies both as writes via
`operands[0].type == MEM`. CONFIRMED, including L2's capstone-rule validation.
(Minor: the function does not `ret` there — it tail-`jmp`s `[rax+0x5c0]`, consistent with stock
`ClearAccumulatedForces()`. L2's listing simply stops early; not a defect.)

`APawn::GetVelocity` at pawn vtable `.rdata 0x088E5CA8 + 0x380 = 0x03BA9300`: `[rcx+0x1B0]`
RootComponent -> `call [rax+0x4C0]` (`edx = 0`) -> `call [rax+0x520]`. CONFIRMED.

### C. `ULokiCMC::PerformMovement` and the `1e-8` gate (L2 section 3.3)

Prologue: `0x055B837E mov rsi, rcx` ⇒ **`rsi == this` [M]**; `0x055B8381 mov r15,[rcx+0x198]`
(CharacterOwner); `0x055B838D movaps xmm6,xmm1` (DeltaSeconds). Function = **322 instructions**,
span `0x55B8370..0x55B88DE`, 0 decode failures, 0 indirect jumps (matches Tier 1's 322).

Constants resolved by my own rip arithmetic:

```
0x055B879F -> rva 0x0768C4C8  f64 = 1.0                    (GetSafeNormal SquareSum==1 fast path)
0x055B87E4 -> rva 0x076A5918  f64 = 9.99999993922529e-09   (= (double)(float)1e-8)
0x055B87EE -> rva 0x099C86A0  .data, 16 zero bytes         (FVector::ZeroVector)
```

`comisd xmm1,[1e-8]; jae 0x55B880F` where `xmm1 = [rsi+0xE8]^2 + [rsi+0xF0]^2`. CONFIRMED.

★ **And I confirm the consequence L2 asserts, from the branch structure:** on the *below*-tolerance
arm `xmm2/xmm3/xmm4` and `[rsp+0x30]` are all zero, so the three `ucomisd` at
`0x055B8838 / 0x055B883E / 0x055B884A` all fall through to `je 0x55B8865` and **the write is
SKIPPED**. On the *above*-tolerance arm the normalised direction is non-zero and
`0x055B8856 movups [rsi+0x12F0]` + `0x055B885D movsd [rsi+0x1300]` **execute**.
⇒ **the sentinel converts a no-write into a write.** `2^-10` gives SizeSq `9.5367431640625e-07`
= **95.367x** the gate (L2: 95.4x). CONFIRMED.

### D. `ULokiCMC::StartNewPhysics 0x055C2430` (full, 22 instructions)

```
055C2433  test r8d, r8d / jne 0x55C2475     ; r8d = Iterations -> block runs ONLY when Iterations==0
055C2438  cmp  byte [rcx+0x16c8], r8b
055C2441  mov  byte [rcx+0x16c8], r8b       ; reset
055C2448  movups xmm0,[rcx+0xE8]
055C244F  movups [rcx+0x16b0], xmm0         ; snapshot X,Y
055C2456  movsd  xmm1,[rcx+0xF8]
055C245E  movsd  [rcx+0x16c0], xmm1         ; snapshot Z
055C2469  mov  byte [rcx+0x16c8], 1         ; set -- 0x1A after 0x55C244F, NO branch between
055C2470  jmp  0x3600990                    ; engine StartNewPhysics
```

CONFIRMED, including L2's "`0x1A` bytes with no branch between", the `Iterations == 0` framing, and
the snapshot layout `X@0x16B0 / Y@0x16B8 / Z@0x16C0` that L2 section 5.3's poke targets.

### E. `+0x16B0` writers (L2 section 4.4)

Union of BOTH CMC vtables' targets, my CFG, `operands[0].type == MEM`:

```
fn 0x55C2430  0x55C244F  W  movups [rcx+0x16b0], xmm0
fn 0x55C2430  0x55C245E  W  movsd  [rcx+0x16c0], xmm1
total 2, in exactly one function
```

**[M, FLOOR] CONFIRMED — reproduced independently on a differently-written instrument.**

### F. `GetRecentVelocity` reachability (L2 section 4.2)

```
rel32 -> 0x0530AC10 (impl)   : 0
rel32 -> 0x0530C7E0 (thunk)  : 0
rel32 -> 0x0530ABF0 (vt A50) : 0
mov <reg>, 0x16B0 sites in .text : exactly 5
   0x0530AC17 (impl)   0x0530C7F1 (thunk)   0x0559C5A5 (inlined)   <- the 3 idiom sites
   0x014B8BD2 / 0x027D5270                                        <- NOT the idiom
```

CONFIRMED. I initially read the last two as genuine `mov ebp, 0x16b0` and thought L2's dismissal
reason was wrong. **My reading was the misaligned one.** A self-consistent linear run gives
`0x014B8BD0 mov qword [rbp+0x16b0], r15` and `0x027D526E mov qword [rbp+0x16b0], rdi` — **stack
stores, exactly as L2 said.** Candidate finding withdrawn. (L2's addresses are the imm32 byte
positions, 2 bytes past the instruction starts; immaterial.)

### G. T8 / T9 exact-zero sites

All six decode as `ucomisd <zeroed xmm>, [base + 0xE8/0xF0/0xF8]`. `0x35D56E8` really does sit under
`cmp byte [rax+0x160], 3` (Role == ROLE_Authority). T9 `0x035FBF4C` compares `[rcx+0x378]`
(`LastUpdateVelocity`) against `[rcx+0xE8]` and later reads `[rcx+0xD0]` — **two independent
CMC-identifying offsets in the same function**, so T9's base is provably a CMC. CONFIRMED.

### H. Sentinel arithmetic (recomputed with a machine)

```
2^-10     bits 0x3F50000000000000  SizeSq 9.5367431640625e-07  ratio vs 1e-8 = 95.367
L2 X/Y/Z  bits 0x3E000000DEADBEEF / CAFEBABE / 5AFE7E57
          biased exp 992 (= 2^-31), ALL NORMAL (not denormal)
          |V|^2 = 6.5052e-19   |V| = 8.0655e-10   ratio vs 1e-8 = 6.505e-11  (1.537e10x BELOW)
2^-20     SizeSq 9.0949e-13     ratio vs 1e-8 = 9.09e-05                     (1.1e4x below)
```

**Every number in L2 section 5.2 reproduces.** CONFIRMED.

---

## 2. UPGRADE — L2 UNDER-GRADED ITS OWN BIGGEST CLAIM (T3)

L2 section 6 grades T3: *"[M] on the compare + the `xorps` branch; **[I]** that the tested vector is
`Velocity` after the gravity transform."* **I can make it [M].**

```
engine PhysFalling 0x035EC850 : 1482 instrs, 0 decode failures, 0 indirect jumps
0x035EC9AC  lea rsi, [rdi + 0xe8]        <- the ONLY definition of rsi in the body
0x035EE519  mov rsi, [rsp+0x918]         <- the epilogue restore, after every use
```

* `rdi` is `this` (`test byte [rdi+0x54c]`, `cmp byte [rdi+0xf50]`, and `rcx = rdi` on both transform
  calls). ⇒ **`rsi == &this->Velocity`.**
* **Dominance test** (reachability from the entry with `0x035EC9AC` removed from the graph):
  `0x035ED946` reachable-avoiding-lea = **False**; `0x035ED9BB` = **False**.
  ⇒ **`lea rsi,[rdi+0xe8]` DOMINATES both write sites. [M]**
* The tested quantity: `0x035ED961 mov r8, rsi` / `0x035ED964 lea rdx,[rbp+0x168]` /
  `0x035ED96E call 0x035F4770` ⇒ `[rbp+0x168] = f(this, Velocity)`. Then `SizeSquared2D` of that,
  `comisd` vs `rva 0x077F5180 = 0.0009999999747378752` (`(double)(float)1e-3` — **L2's `1e-3`
  CONFIRMED**), `ja` skip. On the fallthrough: zero the local's X,Y, transform back
  (`0x035ED9B3 call 0x035F4620`), and **`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3
  movsd [rsi+0x10],xmm1` write the result into `Velocity`.**

⇒ **T3 is [M] end to end: engine `PhysFalling` writes `Velocity` on the `<= 1e-3` arm, and the
brief's `2^-10` sentinel (SizeSq 9.54e-7) is 1048x under that bar.** L2's substantive point — that
"`+0xE8` no longer holds the sentinel" is an **expected** outcome of a running physics step, not an
instrument failure — **stands, and stands harder than L2 claimed.**

⚠ Note what this does NOT establish: that `0x035ED98E` is *reached* on a given frame. That is a
reachability question inside `PhysFalling` that I did not settle, and neither did L2.

---

## 3. DEFECTS FOUND IN L2

### D1 — [I] stated as fact **in the headline** (headline/body grade mismatch)

Headline #4: *"...**and causes a write** to the reflected UPROPERTY
`ULokiCMC::LastNonZeroDirection2D @ CMC+0x12F0`."* Section 3.3's own grade split says: **[I], not
[M], that the write *fires***, because the block is gated on `byte [CMC+0x1308] == 0` and that byte
has never been read. I confirm the gate: `0x055B873B cmp byte [rsi+0x1308],0` /
`0x055B8769 jne 0x55B8865`. A successor reading only the headline gets [M].
**This is the repo's own "a digest is an instrument" failure one level down.**
Restate as: *"...and, if `byte [CMC+0x1308] == 0`, causes a write..."*.

### D2 — Headline #5 overstates: an ordering ambiguity presented as a refutation

Headline #5: *"**THE TIER-1 DECISION RULE IS DEFECTIVE** ... the rule declares the successful case
VOID."* The quote is accurate (`docs/s140-tier1-cfg.md:605` verbatim) and the mechanism is [M]
(section 2 above). **But Tier 1 section 5 states THREE rules with no stated precedence**
(`:603` `+0x16B0` holds the sentinel ⇒ ran [M]; `:604` `+0x16B0` still zero **while** `+0xE8` still
holds it ⇒ did not run [M]; `:605` `+0xE8` changed ⇒ void). Under the natural reading — A first, C as
the residual — rule C bites only in the cell `(+0x16B0 == (0,0,0)) AND (+0xE8 changed)`, which **is**
genuinely ambiguous. "Declares the successful case VOID" requires reading C as **overriding** A,
which Tier 1 nowhere says.
⇒ **[M] that rule C as literally written is unsound; [I] that it would swallow a success.**
The corrected table in section 3.6 is the right deliverable; the headline should read
*under-specified and unsound as written*, not *defective*.

### D3 — MIS-CITATION: section 4.3's flag-writer list is NOT independently reproduced

Section 4.3 says: *"From Tier 1 section 4.6 (**reproduced independently below**): the **only**
writers of the flag `+0x16C8` are ..."* — and lists five. **Section 4.4 censuses displacement range
`[0x16B0, 0x16C7]`, which EXCLUDES `0x16C8`.** Nothing in L2 reproduces the flag-writer list; it is
inherited whole from Tier 1. That list is the load-bearing premise for section 4.3's
`flag == 1 <=> SNP executed 0x055C2469`, which is in turn the entire basis for "a poked snapshot is
unreadable".

**I have now reproduced it.** Within the union of both CMC vtables' closures the `this`-based
`+0x16C8` writes are exactly `0x0530AB4C`, `0x0530ABF9`, `0x055C2441`, `0x055C2469`; the ctor
`0x0559FDF4 mov byte [rdi+0x16c8], sil` I confirmed by direct disassembly (it lies outside the
vtable closure). **The list survives — but the parenthetical is false and should be struck.**

### D4 — The FLOOR caveat is generic where a number was available

Section 3.1 reports `59 functions / 362 hits / 44 both-ends`. My reproduction of the same target set
finds **454 distinct targets, of which 18 are on pages that are 0/4096 non-zero.** L2's census
therefore has a **known, countable** denominator gap of 18 functions it could not have decoded, and
reports none of it. "FLOOR" is correct but unquantified where quantifying was one line of code.

### D5 — Wrong count: T8 is 5 CMC sites, not 6 (and one row upgrades from [I] to an exclusion)

Section 5.4 says *"T8/T9 ... **6 known sites**"*; section 6 grades `0x035FC4A4` as **[I]** ("base not
proven to be a CMC"). **It is positively NOT a CMC:** the site tests `[rdi+0xE0]`, `[rdi+0xE8]`,
`[rdi+0xF0]` — three consecutive doubles starting at **`+0xE0`** — and by **L2's own section 1.4**
`+0xE0` on a movement component is the packed bitfield word, not `Velocity.X`. ⇒ exclude it.
**T8 = 4 CMC sites + T9 = 1, so 5, not 6.** (Favourable to L2's arm; reported because it is a count
L2 published.)

### D6 — Control count not stable inside one document

Headline: *"Four independent instruments, **eight** passing controls."* Section 1.3 header:
*"(**eight**, all independent of the claim)"*. The table has **NINE** rows and the closing line says
*"**9 / 9** offsets agree"*. Also one row (`LastUpdateVelocity`) bundles two distinct facts (the
offset and the 16+8 out-param width). **Quote the unit and pick a number.**

### D7 — Section 2's attribution is un-checkable and mis-scopes to the wrong document

Section 2.1 and headline #2: *"**the brief's** premise is a class mix-up"*, repeated at section 2 as
*"the brief walked into it"*. **`docs/s140-tier1-cfg.md` contains ZERO occurrences of
`ComponentVelocity` and ZERO of `0x1A0`**, and its `:805` already correctly names disp `0x518` as
`UpdateComponentVelocity`. If "the brief" is the lane-assignment prompt, that is not a repo artifact
and **no successor can check it** — while the phrasing reads as a correction to the settled Tier 1
doc, sending a reader to look for an error that is not there. Contrast headline #5, which quotes
Tier 1 by line and is correctly scoped. **Name the document, or drop the attribution and keep the
fact (`CMC+0x1A0 == GravityScale`), which is [M] and useful on its own.**

### D8 — cosmetic

Section 4.2's site addresses are 2 bytes past the real instruction starts (see 1.F). Conclusion
unaffected.

---

## 4. NEW FINDINGS (not in L2, not in Tier 1)

### N1 ★★ `+0x16B0` and `+0x16C8` are ALSO live, ACTIVELY-WRITTEN fields on `ALokiCharacter` — and two such sites sit inside the CMC vtable's own closure

Tier 1 section 4.6 records two `ALokiCharacter` sites (`0x0559EA2F`, `0x0559EA48`). **There are
more, and two of them are reached from the `ULokiCMC` vtable itself** — exactly where an analyst
censusing "CMC functions" would take them for CMC writes:

| site | containing function | base register | provenance of the base |
|---|---|---|---|
| `0x055B860B mov byte [r15+0x16c8], 0` | **`ULokiCMC::PerformMovement 0x055B8370`** | `r15` | `0x055B8381 mov r15,[rcx+0x198]` = **CharacterOwner** |
| **`0x055A6BCB movups [rsi+0x16c8], xmm0`** (16 B) | **`0x055A69F0` = ULokiCMC vtable slot 380 (disp `0xBE0`)** | `rsi` | `0x055A6B0F` / `0x055A6B91 mov rsi,[rdi+0x198]`, `rdi = rcx = this` ⇒ **CharacterOwner** |

The surrounding cluster is the same at both sites (`+0x16C8, +0x16D0, +0x16D8, +0x16E8, +0x16EC,
+0x16F8`), i.e. one `ALokiCharacter` struct that happens to begin at the same numeric offset as the
CMC's flag.

⇒ **OPERATIONAL HAZARD FOR THE S141 ARM.** The proposed probe reads — and L2 section 5.3 proposes to
**write** — `CMC+0x16B0..0x16C7` **by raw offset**. If the probe ever resolves an `ALokiCharacter*`
where it means a `ULokiCMC*`, it reads a *different field that the game writes every frame* and gets
a plausible non-zero answer; and a 24-byte write at that offset on the wrong object lands inside a
live 16-byte `movups` target. **The arm must prove its pointer is a `ULokiCMC` (e.g. that
`[p+0x198]` resolves to the character and `[p+0xD0]` to the capsule) before reading or writing
anything at `0x16B0`/`0x16C8`.** Neither L2 nor Tier 1 states this precondition.

### N2 — a same-shape UNCONDITIONAL reader of `+0x16B0`/`+0x16C0` exists, with 3 live callers — and it is NOT a CMC method (checked, cleared)

`0x055A9A30` is `movups xmm0,[rcx+0x16b0]; movsd xmm1,[rcx+0x16c0]; movups [rdx],xmm0;
movsd [rdx+0x10],xmm1; ret` — a 24-byte getter of the snapshot **with no `+0x16C8` flag test**, with
**3 rel32 callers** (`0x5504032`, `0x5508351`, `0x550CA3B`). Had `rcx` been a `ULokiCMC*`, L2
section 4.3's **[M]** *"a value poked into `+0x16B0` can never be observed by any consumer"* would be
**REFUTED**.

It is not. `0x055A9A30` has **zero stored pointers image-wide** (no vtable slot, no registration
triple; controls: `GetRecentVelocity` and `GetLokiCharacterMovement` both resolve their triples), and
all three callers first cast the object through **`0x054F8C40`** — the *same* cast helper
`ULokiCMC::PerformMovement` applies to `CharacterOwner` at `0x055B839D`. ⇒ its `this` is an
`ALokiCharacter`-family object. **Section 4.3 SURVIVES.**

⚠ But note *how* it survives: on a fact L2 never established. The [M] was one class identity away
from being wrong, and L2's stated support (an enumeration of *CMC-side writers*) does not by itself
exclude a *reader* on another class at the same offset.

### N3 — method note, demonstrated in-lane

A whole-`.text` scan for the 4-byte displacement `0x000016C8` returns **67 byte-occurrences and 48
apparent "writes"**, the great majority of them misaligned artifacts (`adc dword [rbp+0x16c8], eax`
and friends). **A displacement scan without instruction alignment is not an instrument.** It is what
made me briefly believe L2's section 4.2 was wrong (1.F) and what surfaced two candidate "extra flag
writers" that both dissolved under alignment + base-register analysis (N1). Seed from function
entries and walk, or cross-check every hit against a self-consistent linear run.

---

## 5. CHECKS I RAN THAT FOUND NOTHING (recorded so nobody repeats them)

* Did L2 classify memory writes from `regs_access` instead of `operands[0].type`? **No.**
  Section 1.2 (ii) explicitly validates the mandated rule on a known store, and section 4.4's output
  carries a W/R split consistent with operand-position classification. Section 3.1's census is
  deliberately direction-agnostic (it is a *consumer* census), which is appropriate.
* Is any control circular (selected by the property it then reports)? **No.** The nine section 1.3
  offsets come from prior sessions' disassembly / live RPM, not from the array being validated.
  Section 5.3's "`LastNonZeroDirection2D` must NOT change" control is a genuine two-sided self-check
  on the probe.
* Is any [M] resting on a fold-multiplicity-1 assumption that does not hold? **Not found.**
  `0x036523F0`, `0x032C9DD0`, `0x035D5D20` each occupy the same slot in both vtables; none matches a
  known fold constant.
* Is any [M] resting on an inference across a function boundary? **Not found in L2** — and L2 was
  careful here (section 2.2's `ComponentVelocity` cross-check is explicitly graded one-way [I]).
* Is `0x0530ABF0`'s clear conditional in a way that breaks the flag semantics? **No** — both arms of
  `je 0x530AC00` reach the tail jmp; the clear is skipped only when the flag is already 0.

---

## 6. WHAT I MEASURED vs INFERRED

| claim | grade |
|---|---|
| All section 1 items (A-H) reproduce byte-for-byte on independent code | **[M]** |
| `rsi == &Velocity` at T3, and `0x035EC9AC` **dominates** both write sites | **[M]** (upgrade of L2's [I]) |
| T3's tested quantity is `Velocity` transformed to gravity space | **[M]** (arg regs at `0x035ED961` / `0x035ED964`) |
| `0x055A6BCB` / `0x055B860B` bases are `CharacterOwner`, not the CMC | **[M]** (`[this+0x198]`, `CharacterOwner@0x198` UHT-pinned) |
| `0x055A9A30`'s `this` is an `ALokiCharacter`-family object | **[I, strong]** — from the shared cast helper `0x054F8C40` + zero stored pointers; I did NOT decode which UClass `0x052F01E0` returns |
| 18 of 454 CMC-vtable targets are on dark pages | **[M]** |
| T8 site `0x035FC4A4` is not a CMC | **[M]** (its vector starts at `+0xE0`) |
| D2 (headline #5 overstates) — that a reader would apply rule C over rule A | **[I]** — a claim about how an ambiguous three-rule table is read |
| Whether "the brief" (D7) ever contained the `+0x1A0` mix-up | **UNMEASURABLE from the repo** — not a negative |
| Every census here | **FLOOR** — `.text` is 55.48 % decrypted; a caller or consumer on a dark page is all-zero bytes |

---

## 7. FILES

`scratchpad/s140t2/V2tools/{v2pe.py, v2dis.py, v2cfg.py}` — read-only; no game process touched;
no `.text` written; zero launches.
