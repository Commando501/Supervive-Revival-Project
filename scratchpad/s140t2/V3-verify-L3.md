# S140 TIER 2 — ADVERSARIAL VERIFICATION OF LANE 3 (`L3-free-reads.md`)

Offline. Zero launches, zero injection, zero live process. Image `dumps/merged13.dump.exe`
(my own PE reader re-derived `ImageBase = 0x7FF608F40000` and `file-offset == RVA` for all 10
sections). **`.text` is 55.48 % decrypted — every `.text` census below is a FLOOR** (and a naive
rel32 byte scan also carries FALSE POSITIVES, a direction L3 did not state).

Method: I wrote my own PE reader (`scratchpad/s140t2/V3/vpe.py`) and my own **recursive-descent**
CFG walker (`scratchpad/s140t2/V3/vcfg.py`). I did **not** run any L3 script, did not import
`scratchpad/s140t2/pe.py` / `l3dis.py`, and did not use `tools/re/propoffset.py` (I decoded the
UHT records by hand). Memory-write classification is from `operands[0].type == X86_OP_MEM`, never
from `regs_access` (S140 recorded defect).

**Bottom line: L3's substance is unusually solid — 14 load-bearing claims reproduced, several
byte-exact. But it contains ONE flatly refuted [M]-shaped negative, one internal count
contradiction that propagates into its own conclusion, one incomplete-window negative, one
over-graded name, one circular payoff in section 5, and one completeness gap in the single
transcription its headline scope-limit depends on.**

---

## 1. REFUTED

### R1 — REFUTED: "no `.pdata` row covers it in `tools/strxref/index/pdata_union.csv`" (section 2, of engine `StartNewPhysics 0x03600990`)

`pdata_union.csv` contains **three chained rows** covering it, `seen_in_dumps = 76` each:

```
0x03600990 .. 0x03600A57   size=199   seen_in=76
0x03600A57 .. 0x03600BD3   size=380   seen_in=76
0x03600BD3 .. 0x03600C18   size=69    seen_in=76
```

Union `0x03600990..0x03600C18` — my measured body end `0x03600BF6`, plus 2 bytes of padding, plus
the 32-byte jump table. **The row set independently CONFIRMS L3's own extent measurement**, so
checking it would have gained the lane a free second instrument instead of costing it a false
negative.

**Provenance is identifiable and is this project's second-named failure mode.**
`docs/s140-tier1-cfg.md:772` states the true fact: *"`pdata_union.csv` has NO row covering
`0x055C2430`, `0x0530ABF0`, `0x0530AC10`, `0x0530C7E0`"* — the **Loki** functions. I confirm
`0x055C2430` -> NO ROW (nearest row starts `0x055C24A0`). **L3 carried the Tier-1 claim forward
onto a different function and did not re-derive it.**
Controls (same query, same file, same code): `0x035AFC40` -> row `0x35AFC40..0x35AFC8F` (exactly my
measured 79-byte extent); `0x035E9EC0` -> row `0x35E9EC0..0x35E9F35`. The instrument works.
L3's *general* caveat ("blind on dark pages by construction; do not build a function filter on
it") remains correct and is untouched by this.

### R2 — REFUTED: section 2.1's header "FIVE exits, all forward, all to `0x03600BE6` (the epilogue)" is wrong twice, and the wrong count propagates into section 2.3's conclusion

**(a) Count.** L3's own table body labels row **E** *"not an exit"*, so the table describes **FOUR**
early-out conditions (A `DeltaTime < MIN_TICK_TIME`, B `Iterations >= MaxSimulationIterations`,
C `!HasValidData()`, D `IsSimulatingPhysics()`). The header says five; section 2.3 then concludes
*"the **five** early-outs in 2.1 are the ONLY early-outs in the entire StartNewPhysics step.
**[M]**"* — an [M] carrying a count its own table contradicts. Tier 1's independent framing ("a
**FOURTH** early-out nobody had", `s140-tier1-cfg.md:621`) implies 4, agreeing with the table.

**(b) "all to `0x03600BE6`".** Measured terminations (my recursive descent: 144 instructions,
**614/614 bytes covered, 0 gaps, 0 decode failures, 0 backward branches**):

```
-> 0x03600BE6 : 0x036009AF(A)  0x036009BC(B)  0x036009CD(C)
                0x036009F5 (verbosity gate, inside D)
                0x03600A3C (null-FString guard, inside D)
                0x03600BD1 (normal tail, not an exit)
ret           : 0x03600A56   <-- exit D's LOGGING path, its own duplicated epilogue
ret           : 0x03600BF5   <-- normal return
```

**Exit D does not reach `0x03600BE6` when it logs.** L3 states both readings inside one section
(its D row says *"rets at 0x03600A56"*; the note under it says *"both arms end at 0x03600BE6"*).
Only the first is true.
"all forward" IS correct — I measure **zero backward branches** in the whole function.
"615 bytes" is 614 (`0x03600BF6 - 0x03600990 = 0x266`).

---

## 2. DOWNGRADES (claim survives, grade or support does not)

### D1 — section 2.1 "exit D is already answered [M] and needs no re-read" is [I, strong], not [M]
The *structural* half reproduces perfectly and I confirm it independently: both call sites are
`mov rcx,[rbx+0xD0]` -> `call [rax+0x4C0]` with the second argument zeroed —
`0x036009D3/DA/E4` (`xor edx,edx`) vs `0x035E9F2E` + `0x035E9FAD` (`mov edx,r15d`) — **same
displacement, same object, same argument. [M].**
What is *not* [M] is "it passes": that rests on a **live read taken in a different sitting**
(S139 flight 3, `bSimulatePhysics == 0` on the hero capsule). A mutable field measured once is not
a permanent property, and the S141 probe targets a **bot**. Correct form: "measured passing on the
hero capsule in S139-f3; structurally identical predicate [M]; still passing = [I, strong]".

### D2 — section 1.1 grades the callee NAMES [M]; only one of the two earns it
`0x0302B930` -> calls `0x03F5CB90`, which I confirm `lea`s `L"World"` (`.rdata 0x0825D352`) and
`L"/Script/Engine"` (`0x0773DBE0`) — literal-anchored, fine as [M].
`0x0338C990` = `AActor::GetWorld` has **no literal anywhere**; it is a stock-UE shape match. I
confirm the shape (`RF_ClassDefaultObject` test on `[rcx+0xC]` bit 4, `OuterPrivate` at `+0x28`, a
`GUObjectArray`-indexed outer chain). That is **[I, strong]**, the same grade section 7 assigns to
`GetWorld_Uncached` — sections 1.1 and 7 disagree with each other.
Same for section 4.1's *"`CMC+0x3DC = NumJumpApexAttempts` [M]"*: the **semantics** are [M] (I
confirm `0x035ECE5D mov ebx,[rdi+0x3DC]` -> `cmp ebx,[rdi+0x3E8]` -> `jge`, `0x035ECFFC
mov [rdi+0x3DC], eax` with `eax = rbx+1`, and the reset `0x035EB130 mov [rbx+0x3DC], r15d`); the
**name** is [I, strong]. Section 7 again silently corrects section 4, so a reader of section 4
alone is misinformed.

### D3 — section 4's Loki-ctor negative was taken over a window that does not cover the function
L3: *"byte-anchored scan of `0x0559F580..0x0559FE60`: 0 hits"*. My recursive descent measures
`ULokiCMC::ctor` as `0x0559F580..0x055A0008` (**327 instructions, 2,696 bytes, single ret at
`0x055A0007`**) — L3's window is **0x1A8 = 424 bytes (15.7 %) short**.
**The conclusion survives**: re-scanning the FULL extent for disps `0x3DC/0x3E0/0x3E4/0x3E8` gives
**0 raw byte occurrences**, with the base-ctor range as a passing 4-of-4 positive control. But the
stated support only covered the function by accident.
My *first* scan reproduced only 4 of L3's 6 base-ctor writes because my backward-decode window
started 2 bytes too far back (`c7 83 <disp32>` needs back = 2). Fixed; all six then confirmed —
recorded because it is the same class of instrument defect L3 flags in its own section 4.1 note.

### D4 — section 5's payoff is CIRCULAR against the question under investigation
L3: *"If live Verbosity >= 5 ... its absence becomes a real negative on exit D."*
It does not. Absence of the abort line is a disjunction: (i) exit D reached and
`IsSimulatingPhysics()` returned false, **or (ii) the function was never reached at all** — and
(ii) is precisely the open question (section 2.3's whole scope-limit exists because entry is
unproven). Removing the verbosity branch does not remove (ii). Honest form: *conditional on the
S141 sentinel showing `ULokiCMC::StartNewPhysics` was entered*, a live `Verbosity >= 5` converts
the log's silence into a real negative on exit D. The `.data` read itself is correctly graded [I]
and correctly flagged as a mutable global.

### D5 — section 1.2's control number "1 (0.1 %)" is implementation-dependent; only the conclusion is robust
My independent scan, same 48-byte window, `REX.W 8B /r` with `disp32 == 0xC0` incl. SIB forms:

| target | calls | jmps | with `+0xC0` load |
|---|---:|---:|---:|
| `0x035AFC40` (the claim) | **964** (L3: 964) | **7** (L3: 7) | **780 = 80.9 %** (L3: 777 = 80.6 %) |
| `0x0302B930` (control) | **38** (L3: 38) | 0 | **3 = 7.9 %** (L3: 3 = 7.9 %) |
| `0x0338C990` (control) | **1050** (L3: 1050) | 10 | **7 = 0.7 %** (L3: **1 = 0.1 %**) |

Call/jmp counts reproduce **exactly**; the two-sided control **passes decisively either way**
(80.9 % vs 0.7 %). But 1 vs 7 is a 7x spread from a pattern-matching detail, so quote that control
qualitatively, not as "0.1 %". 0 of the 964 sites lie on an all-zero page.

---

## 3. INCOMPLETE — a gap in the one transcription the headline scope-limit rests on

### G1 — section 2.3's `ULokiCMC::StartNewPhysics 0x055C2430` listing elides a `+0x12B0` accumulator on the very arm it prints as a bare jmp
My CFG-sound decode (21 instructions, 0 rets, 2 tail-jmps, 0 gaps):

```
0x055c2475  7e 1c                     jle  0x55c2493
0x055c2477  80 b9 31 02 00 00 03      cmp  byte [rcx+0x231], 3        ; MovementMode == MOVE_Falling
0x055c247e  75 13                     jne  0x55c2493
0x055c2480  0f 28 c2                  movaps xmm0, xmm2               ; xmm2 = DeltaTime
0x055c2483  f3 0f 58 81 b0 12 00 00   addss  xmm0, [rcx+0x12b0]
0x055c248b  f3 0f 11 81 b0 12 00 00   movss  [rcx+0x12b0], xmm0       ; <-- SECOND accumulator
0x055c2493  0f 28 ca                  movaps xmm1, xmm2
0x055c2496  e9 f5 e4 03 fe            jmp  0x3600990
```

**This is NOT a new finding — `docs/s140-tier1-cfg.md:351` already tabulates it as writer B**, and
`:353` tabulates writer D `0x055B7CCD` (`ULokiCMC::OnMovementModeChanged`, writes 0). I re-derived
A/B/D independently (writer A `0x055B8414` inside `ULokiCMC::PerformMovement`, from a
322-instruction CFG of `0x055B8370`; writer D from a 91-instruction CFG of `0x055B7BF0`), all
classified by `operands[0].type == MEM`. What IS a defect is that L3 transcribed this exact
function *in full*, in the section whose stated purpose is to bound what a `+0x16B0` observation
proves, and printed the arm as `... e9 f5 e4 03 fe jmp` with the accumulator inside the ellipsis.
A reader who takes section 2.3 as the authoritative transcription (which is how it is written)
loses writer B.
Also elided: `0x055C2438..0x055C2441` **clears** `+0x16C8` before setting it — a third writer of
that byte. Harmless to the "latch is invalid" conclusion, but it is not in the listing either.

### G2 — minor incompletenesses
- Section 1.2 lists 5 of the **7** tail-jmp bodies; the two omitted are `0x0379717A` and
  `0x04403805`. All 7 verified to carry a `+0xC0` test in the immediately preceding bytes (the last
  two use `cmp qword [rbx+0xC0], 0`, not "decode mid-instruction" as L3 explains it).
- Section 5's record layout claims `+0x18` = function; it is **NULL in all three** records, and
  `+0x08` (file) is **ANSI**, not wide — it decodes to
  `C:\TheoryCraft\build-staging\Engine\Source\Runtime\Engine\Private\Components\CharacterMovementComponent.cpp`
  for all three.
- Section 5 cites the verbosity gate at `0x036009F5`; the `cmp` is at **`0x036009EE`**
  (`0x036009F5` is the next-instruction anchor for the rip-relative arithmetic). Section 2.1 is
  right and section 5 is not.

---

## 4. CONFIRMED — reproduced with my own code, several byte-exact

1. **The headline is CORRECT and it is the most valuable thing in the report.** `0x035E9EEE
   mov r13,[rcx+0xC0]` / `test r13,r13` / `jne` / `call 0x035AFC40` / `mov r13,rax`, then exit 1
   `call [rdx+0x6B8]` and exit 2 `test r13,r13; je 0x35EB1A7` — **byte-for-byte identical to L3's
   listing.** Exit 2 tests `WorldPrivate` **or** the fallback's return, so **a non-null `+0xC0`
   settles exit 2 and a NULL does not**. One [I, strong] caveat L3 does not state: the probe reads
   at time T, the gate runs at T'; `WorldPrivate` is a mutable field.
2. `0x035AFC40` transcription: **byte-exact**, 28 instructions, extent `0x035AFC40..0x035AFC8F`
   (79 bytes), 2 rets, 2 calls. A line-for-line stock `GetWorld_Uncached`.
3. Engine `StartNewPhysics 0x03600990` **names itself**: `.rdata 0x07FC0648` -> the abort string,
   `CharacterMovementComponent.cpp`, `Line = 3477`, `Verbosity = 5`. Companions `0x07FC0740`
   (3510, Warning 3) and `0x07FC0548` (2919, Log 5) confirmed.
4. MIN_TICK_TIME: the `comiss` operand resolves to `.rdata 0x076B8E74`, raw `0x358637BD` =
   `9.999999975e-07`. Exact match.
5. Jump table at `.text 0x03600BF8`: `rdx = ImageBase` (`lea rdx,[rip-0x3600A8B]` -> 0), entries are
   RVAs, `cmp esi,7` bounds it at 8, and **entries [8] and [9] are `0xCCCCCCCC` padding** (an extra
   confirmation L3 did not take). All eight case->displacement mappings confirmed:
   `0->tail, 1->0x970, 2->0x978, 3->0x830, 4->0x988, 5->0x980, 6->0xCC8, 7->0x990`.
6. **`ULokiCMC::StartNewPhysics` contributes ZERO exits** — 21 instructions, **0 rets**, two tail
   `jmp 0x3600990`. CONFIRMED.
7. **Sentinel scope limit CONFIRMED and correct**: `movups xmm0,[rcx+0xE8]` /
   `movups [rcx+0x16B0],xmm0` / `movsd xmm1,[rcx+0xF8]` / `movsd [rcx+0x16C0],xmm1` /
   `mov byte [rcx+0x16C8],1` all sit **before** `jmp 0x3600990`. A sentinel in `+0x16B0` proves
   only *entry with `Iterations == 0`*, never that the engine body or any `Phys*` ran.
8. **ULokiCMC ctor installs the vptr**: `0x0559F580` -> `call 0x1363720` -> `call 0x35CF3E0` ->
   `mov [rdi+0x1140], 0x44BB8000` (=1500.0f) -> `lea rax,[rip+0x3358FBD]` (-> **0x088F8570**) ->
   `mov [rdi], rax`. Byte-exact; the rip arithmetic re-checked by machine.
9. **Vtable anchors, aligned-qword uniqueness**: `0x035E9EC0` ->1 at `ENG+0xAA8`; `0x055B8370` ->1
   at `LOKI+0xAA8`; `0x03600990` ->1 at `ENG+0x720`; `0x055C2430` ->1 at `LOKI+0x720`.
   `ENG = 0x07FBED58` independently confirmed by `0x035D0180`'s own `lea` / `mov [rcx],rax`.
10. **449 both-`.text` / 380 identical (84.6 %)** in the first 512 slots — **exact match**. Override
    set exact: **overridden** `0x670 0x720 0x830 0x990 0xA50 0xAA8`; **not overridden** `0x4F8
    0x6B8 0x970 0x978 0x980 0x988 0xCC8`. (I also produced the full 69-slot Loki override list.)
    I **RAN the misalignment control L3 only asserted**, and it PASSES: shifting the LOKI base by
    +/-8/16/24 gives **4.0-5.4 %** identity vs **84.6 %** at 0. (L3 said "~0 %"; it is ~5 %, and the
    discrimination is still overwhelming.) A control that could have failed and did not.
11. **Secondary vptrs at `+0x30`, `+0x188`, `+0x190`** in both classes — confirmed from
    `0x035D0180` (`0x07FBFA40 / 0x07FBFA80 / 0x07FBFB08`) and `0x0530AAA0` (`0x088F9258 /
    0x088F9298 / ...`).
12. **All six base-ctor default writes** confirmed after fixing my own scan: `0x035CF90C
    [+0x3E0]=0.05f`, `0x035CF917 [+0x3E4]=8`, `0x035CF921 [+0x3E8]=2`, `0x035CF92B [+0x3DC]=r12d`,
    `0x035CFA29 [+0x28C]=2048.0f`, `0x035CFA6D [+0x300]=100.0f`. `0x035CAF50` `lea`s
    `L"CharacterMovementComponent"` + `L"/Script/Engine"`.
13. **UHT records decoded by hand**: `.rdata 0x07FB0808` name `MaxSimulationTimeStep`, ArrayDim 1,
    **Offset 0x3E0**; `.rdata 0x07FB0840` name `MaxSimulationIterations`, ArrayDim 1, **Offset
    0x3E4**; `0x07FB0878` `MaxJumpApexAttemptsPerSimulation` **Offset 0x3E8**.
    **L3's most valuable caveat reproduces exactly**: each of the two names has **three** records
    image-wide — `MaxSimulationTimeStep` at Offsets `0x3E0 / 0x198 / 0x1CC` and
    `MaxSimulationIterations` at `0x3E4 / 0x1A0 / 0x1D0`. Do not take an offset from a name search.
14. `.data 0x09F85E68` (both rip-relative anchors resolve there): bytes `05 00 05 07` =>
    `Verbosity=5, DebugBreakOnLog=0, DefaultVerbosity=5, CompileTimeVerbosity=7`. Correctly graded
    [I] by L3 (single `.data` seed, mutable global).

---

## 5. CONTROL AUDIT (the specific question asked)

| L3 negative / control | could it have failed? | circular? | verdict |
|---|---|---|---|
| `+0xC0` census vs `0x0302B930` and `0x0338C990` | **yes** — a GetWorld sibling could have shown the same idiom | **no** — controls chosen as callee/sibling, not by the `+0xC0` property | **VALID**, reproduced |
| "misaligned vtable bases would give ~0 %" | asserted, **not run** by L3 | no | **I ran it: PASSES** (4-5 % vs 84.6 %) |
| section 1.4: `propoffset.py` finds 0 literals for `WorldPrivate`/`OwnerPrivate` while `CheatManager` / `MaxAcceleration` / ... resolve | **yes** | no | **VALID**, and correctly labelled an instrument limit rather than a negative result |
| section 4: "Loki ctor overrides none of `0x3DC/3E0/3E4/3E8`", control = base ctor finds all six | **yes** | no | control valid; **window 424 B short** (D3). Conclusion holds on the full extent |
| section 5: "the abort line's absence becomes a real negative on exit D" | — | **YES — circular** | **D4**: does not exclude "never reached", which is the question |
| section 2: "no `.pdata` row covers it" | had no control at all | — | **R1: REFUTED** |

**Units check (asked for explicitly):** L3 quotes 964/7 as *call sites / jmp sites*, 449/380 as
*vtable slots*, records vs strings correctly separated, 614 as *bytes*, and it states the `.text`
FLOOR caveat in section 7. The two unit-ish defects are "FIVE exits" vs 4 (**conditions**, R2a)
and "615 bytes" vs 614.

**capstone `regs_access` defect:** L3 performs no write census of its own, so the recorded defect
is not triggered by it. I applied the `operands[0].type == MEM` rule throughout. Worth recording:
my byte-anchored backward decode independently produced mis-decoded `adc` / `sub` forms at
`0x055B8416` / `0x055C248D` that a naive reader would take as real instructions — the CFG-sound
decodes are `0x055B8414 movss` and `0x055C248B movss`.

---

## 6. WHAT I DID NOT CHECK
- Tier 1's CFG / dominance results for engine `PerformMovement` (out of scope for this lane).
- Whether `0x03600990`'s three `.pdata` rows are the *complete* chain in a live process (they are a
  union over 76 dumps; `pdata_union.csv` is itself a floor on dark pages).
- Any live value. Everything here is from the image.
- The identity of the adjacent vtables at `0x088F7B58` / `0x07FBE360` (L3 also left this open).
