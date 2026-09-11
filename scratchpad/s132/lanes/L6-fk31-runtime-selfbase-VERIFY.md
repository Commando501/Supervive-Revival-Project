# ADVERSARIAL VERIFICATION - `L6-fk31-runtime-selfbase.md`

**Method.** Every number below was re-derived from `runtime.dll` with my own PE parser and my own
scanners (`scratchpad/s132/verify/l6/v_*.py`), **not** with the lane's `rt.py` / `scan_plus1.py`,
except where I deliberately re-ran the lane's own script to test reproducibility. Every address
arithmetic was done by `python`. Zero launches, zero injections, zero `.text` writes.

Target file: `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll`
(md5 `5e73e00ab52bc8f30574d8c023a84171`, 67,511,496 B) - confirmed as the file the launcher actually
uses (`configs/launch-redirect.ps1:46` default `$GameRoot`).

---

## Verdict table

| # | Claim | Verdict |
|---|---|---|
| H1 | file identity, headers, section map, DSN at `0x7C1BEC` | **CONFIRMED** |
| H2a | `ImageBase == 0x200000000 == 2^33` | **CONFIRMED** |
| H2b | "heavy bit-33 MBA ... a constant-search **cannot be decisive** ... returns MBA noise at a rate that **swamps** any real hit" | **REFUTED** |
| H3 | "**No code** in 48,129,536 B computes `ImageBase+1` as an address; all 13 candidates refuted by their consuming instruction" | **REFUTED** |
| S3.1 | no relocated qword becomes `base+1` (2,020 DIR64 + 10 ABSOLUTE, full parse) | **CONFIRMED** |
| S3.2 | the `0x200000001` literal at `packer2 0x941900` is `__isa_available` CRT state | **CONFIRMED** |
| S3.3 | 0 of 18,580 `.pdata` entries has a field `== 0` or `== 1` | **CONFIRMED** |
| S3.4 | no MZ/PE self-locate, with the `0x0000FFFF` x123 positive control | **CONFIRMED** (and strengthened) |
| S3.5a | 10 x `movabs r64,0x200000001`; 9 consumed by `and` (mask), 1 by `add` | **CONFIRMED** |
| S3.5b | "all three `-(ImageBase+1)` sites ... **each with a `shl reg,0x21` in the immediately preceding instructions**" | **REFUTED** (false for `0x019DC131`) |
| S3.6 | 406 `+1 -> jmp reg` pairs, all `packer31`, all MBA tails; 5.1 % corroborator | **CONFIRMED** (sampled 6/6; 242/4,769 reproduced) |
| H4a | 4,769 / 18,580 functions end in `jmp <reg>`; packer1 1,111 / packer31 3,658 / packer30 0 | **CONFIRMED** |
| H4b | register split "jmp rax..rdi 4,251 / jmp r8..r15 518" | **REFUTED** (1,108 of the 4,251 carry REX.B) |
| H4c | worked example `0x0166E230`: MBA decodes to `rdi + ImageBase + 0x166AA7B`; `0x166AA7B` is an exact function start | **CONFIRMED** |
| H4d | at scale: 940 constants, 335 (35.6 %) exact starts, 353 inside, 614 (65 %), 558 (15.3 %) | **CONFIRMED** |
| H4e | negative control "940 random qwords, same test -> 0/940" | **DEGENERATE-CONTROL** (conclusion survives my replacement controls) |
| H4f | "the jump target **is** carried as `movabs reg, -(IB+RVA)`" - at population scale | **UNSUPPORTED** (168/614 same-register; [M] for 1 site, [I] for the rest) |
| H4g | "the remaining 605 decode into packer30 / packer2 / packer1 / packer0 / packer40" | **REFUTED** (85 of the 605 decode into `packer31`) |
| S4.4 | the three `-2^33` sites all compute `variable + ImageBase` | **CONFIRMED** |
| S4.5 | `packer31` constants carry no relocation entries | **CONFIRMED** |
| H5 | `[I]` mechanism class | **CONFIRMED as an [I]**, and strengthened by the H3 refutation |
| H6 | the `variable + ImageBase` idiom exists **at 3 sites** | **UNSUPPORTED** - 3 is a literal-immediate floor; at least 5, and 10 movabs sit within +4 of `-2^33` |
| H7a | `0x80F7F0` bytes; rip target `0x94A800`; vtable `0x1831C0` = 5 slots + NULL; slot 4; unique pointer; ctor `0x7F86F0`; 0 callers / 0 stored pointers | **CONFIRMED** (and the xref scan extended) |
| H7b | printed byte string `baaddead00` for `mov edx,0xdead` | **REFUTED** - the bytes there are `ba ad de 00 00` |
| H7c | "`0x80F7F0` **is** NtTerminateProcess(...)", graded **[M]** | **UNSUPPORTED at [M]** - the syscall number is runtime-computed; on disk it evaluates to `0xFFFFFFFF` |
| S5.4 | EP `0x855440 -> jmp 0x139238F`, 54,233 B, exact `.pdata` start, xmm saves, `and rsp,-0x40` | **CONFIRMED** |
| S6.1 | `.rwx` 4,096 B all-zero on disk; relocated pointer to it at `packer2 0x941908` | **CONFIRMED** |
| S6.4 | "the distance histogram **saturates** at 40 -> longer pairs exist, uncounted" | **REFUTED** (histogram decays; window 60 adds only 29) |
| S6.5 | disp32 sweep FP rate: 712 candidates / 27 real `ff 15` | **CONFIRMED** exactly |

**Confirmed: 20 distinct load-bearing claims. Refuted: 7. Unsupported: 3. Degenerate control: 1.**

---

## 1. H3 - REFUTED. `packer31 0x03C8EDF2` computes `variable + ImageBase + 1`, and the result is dereferenced

The report dismisses the three `movabs r64, 0xFFFFFFFDFFFFFFFF` sites as "`-(2^33)-1` MBA constants".
It stopped one instruction short of the result. The whole block, decoded (raw bytes
`488b8c24580100004889c848f7d04989c649c1e6214901c649b9fffffffffdffffff49ffc14c0fafc94d29f1`):

```
03c8edda  488b8c2458010000      mov    rcx, qword ptr [rsp + 0x158]
03c8ede2  4889c8                mov    rax, rcx
03c8ede5  48f7d0                not    rax                      ; rax = ~rcx
03c8ede8  4989c6                mov    r14, rax
03c8edeb  49c1e621              shl    r14, 0x21                ; << 33
03c8edef  4901c6                add    r14, rax                 ; r14 = ~rcx * (2^33 + 1)
03c8edf2  49b9fffffffffdffffff  movabs r9, 0xfffffffdffffffff
03c8edfc  49ffc1                inc    r9                       ; r9 = -2^33   (NOT -(2^33+1))
03c8edff  4c0fafc9              imul   r9, rcx                  ; r9 = -2^33 * rcx
03c8ee03  4d29f1                sub    r9, r14
```

Algebra, with `~x = -x-1`:
`-2^33*rcx - (2^33+1)*(-rcx-1) = rcx + 2^33 + 1` = **`rcx + ImageBase + 1`**.

- Verified by concrete evaluation of exactly these instructions over **2,000 random inputs**:
  `r9 == [rsp+0x158] + 0x200000001` in **2000 / 2000**.
- Instruction boundaries confirmed independently from **4 different linear start points**
  (function start `0x03C8E30A` plus three interior points): **11/11 anchors on a boundary in all four**.
- The value is **used as an address**: the only writes to `r9` after it are
  `03c8ee3b cmove r9, rax` (the other arm being `lea rax,[rsp+rax+0x300]`), and then
  **`03c8eff3 movzx r12d, byte ptr [r9]`** - a dereference.

So *"No code in 48,129,536 bytes of executable sections computes `ImageBase+1` as an address"* is
false as written. What is supported is the much narrower *"no 64-bit literal immediate equal to
+/-(ImageBase+1) survives as an operative constant"* - and even that misses this site, because the
operative constant here is `-2^33` and the `+1` is produced by the polynomial. The report's own
section 6.3 names this exact blind spot ("a 1 produced by the MBA polynomial itself") and then grades
H3 **[M]** anyway. That is a grade upgrade across an inference step, and it fired on the report's own
candidate list.

**What I am NOT claiming.** I have not shown `rcx` is the relocation delta. The surrounding
`test byte ptr [rsp+0x28],1` / `cmove <mba-result>, lea [rsp+rax+0x300]` shape is the MSVC
inline-buffer selection idiom, so the likelier reading is a **biased / obfuscated pointer**
(`stored = ptr - IB - 1`), not the FK-31 kill. Grade: the *computation* is **[M]**; its *role* is
**[S]**. But it is precisely the shape H5 predicts, and the report discarded it.

A second, smaller error in the same paragraph: S3.5 says all three sites have *"a `shl reg,0x21` in
the immediately preceding instructions"*. **False for `0x019DC131`** - the eight preceding
instructions are `not` / `and` / `imul` / `mov rcx,[rsp]` / `not rcx`, with no `shl` of any kind, and
the constant is then adjusted by **`add r9, 2`** (giving `-(2^33-1)`), not `inc`. The generalisation
was made from the two sites that were opened to the one that was not.

## 2. H2b - REFUTED. The confound is real; the conclusion drawn from it is not

`ImageBase == 2^33` is confirmed. But *"a search for the constant `ImageBase+1` cannot be decisive in
this binary - it returns MBA noise at a rate that swamps any real hit"* is contradicted by the
measured population over the same 48,129,536 bytes:

| bit-33 form | occurrences |
|---|---:|
| `movabs r64, 0x200000001` | 10 |
| `movabs r64, -(0x200000001)` | 3 |
| `movabs r64` within `+4` of `-2^33` | 10 |
| `shl r64, 0x21` (any) | **9** |

A few dozen sites, every one individually adjudicable - which is exactly what the report then did.
Nothing "swamps". And the search **was** decisive: it produced the `0x03C8EDF2` hit above, which the
adjudication then mis-scored. The defensible statement is *"each bit-33 hit needs individual
adjudication"*, not *"the method the task proposed is defeated"*.

## 3. H4e - DEGENERATE-CONTROL (the conclusion survives replacement controls)

Stated control: *"940 random qwords from the same section, same test -> 0/940."*
The test has two stages: (i) does `-imm` land in `[ImageBase, ImageBase+SizeOfImage)`, and (ii) is
the decoded RVA an exact function start. A random qword passes stage (i) with probability
`0x4066000 / 2^64`, about `3.7e-12`. I measured it: **0 of 940 random `packer31` qwords passed stage
(i) at all**, so stage (ii) was never exercised. The control returns 0 whether or not the hypothesis
is true - it tests the range filter, not the landing.

Three non-degenerate replacements against the same 940-item hit set:

| control | exact function starts |
|---|---:|
| **observed (the 940 decoded targets)** | **335 / 940 (35.6 %)** |
| uniform random RVA in the image (base rate 0.0275 %) | 0 / 940 |
| uniform random RVA within `packer31` (base rate 0.0162 %) | 0 / 940 |
| the same 940 targets shifted `+0x4` / `+0x10` / `+0x1000` | 0 / 1 / 2 of 940 |
| the same 940 targets shifted `+0x1` | 13 / 940 |

**The finding stands** - the encoding claim is real and far above chance. Only its stated control was
worthless.

## 4. H4f / H4g / H4b - three narrower corrections to an otherwise confirmed section

- **H4f (UNSUPPORTED).** "*The* jump target is carried as `movabs reg, -(ImageBase + RVA)`" is
  measured for exactly one function (`0x0166E230`; I re-verified that `r8` has **no intervening
  write** between `add r8, rax` at `0x0166E3BD` and `jmp r8` at `0x0166E509`, and that `0x166AA7B`
  is an exact `.pdata` start with the packer31 prologue). At population scale only **168 of the 614**
  in-computed-tail constants are materialised into the *same register the tail jumps through*
  (446 into a different one; chance baseline about 38). That is 4.4x enrichment - consistent with MBA
  register shuffling, but it means the constant-to-tail-target linkage is **[I]** for the population.
  What is **[M]** at scale is the weaker and still-valuable claim: *these constants are addresses of
  real functions*.
- **H4g (REFUTED).** "The remaining 605 decode into packer30 / packer2 / packer1 / packer0 /
  packer40." Measured section split of the 605 non-exact targets: `packer2` 213, `packer1` 117,
  `packer30` 112, **`packer31` 85**, `packer40` 33, `packer0` 34, `.rsrc` 1, unmapped 10.
  `packer31` is omitted from the report's list and is the 4th largest bucket.
- **H4b (REFUTED, cosmetic).** Of the 4,251 tails classed "jmp rax..rdi", **1,108 carry a `0x49`
  REX.B prefix** and are therefore `jmp r8..r15`. True split is about 3,143 / 1,626. The total 4,769
  and the section split 1,111 / 3,658 / 0 are unaffected and reproduce exactly.

## 5. H7 - two problems inside an otherwise fully reproduced section

Everything structural reproduced byte for byte: the stub at `0x80F7F0`;
`0x80F804 + 0x13AFFC = 0x94A800` (recomputed by machine); the `packer0 0x1831C0` table as 5 pointers
+ NULL with slot 4 = `0x80F7F0`; **exactly one** qword in the whole file equal to
`ImageBase + 0x80F7F0`, at RVA `0x1831E0` = that slot; the ctor at `0x7F86F0` byte-exact with
`lea rcx,[rip-0x675549]` resolving to `0x1831C0` (recomputed); **0 rel32 callers and 0 stored
pointers** to the ctor. I also extended the disp32 xref sweep to the three variants the report did
not run (disp32 followed by imm8 / imm16 / imm32) and still found **exactly one** reference - the
"sole xref" claim is stronger than reported.

**(a) REFUTED - byte-string transcription error.** The report prints

```
0080f80c  baaddead00        mov    edx, 0xdead
```

The bytes at `0x80F80C` are **`ba ad de 00 00`**. `baaddead00` is not the byte string at that
address. The mnemonic is right, so nothing downstream changes - but this is the exact failure class
`CLAUDE.md` names ("Never print a byte string next to an address it did not come from"), in a report
whose own preamble invokes that discipline.

**(b) UNSUPPORTED at [M] - the syscall identity is not established offline.**
The report grades *"`RVA 0x80F7F0` is `NtTerminateProcess([this+0x10], 0xDEAD)`"* as **[M]** and calls
it "re-verified byte-exact". The **bytes** are re-verified [M]. The **identity** is not derivable from
them: the syscall number is `ROL(0x618E77BF XOR *(dword*)0x94A800, 7) + 0x6710C747`, and the on-disk
cookie is `0x10BFA9CE`, which evaluates to **`0xFFFFFFFF`** - not a valid service number. `packer2`
is `RW`, so the cookie is patched at runtime and the number is unknowable from the file. All the
bytes support is `Nt???(HANDLE from [this+0x10], 0xDEAD)` - a shape `NtTerminateThread` shares.
The identification is inherited from `docs/fk10-protector-identified.md`, where it is likewise an
inline annotation inside a MEASURED block rather than a measurement.

Useful side effect: the `0xFFFFFFFF` result is **positive evidence for the report's other half** -
the number really is computed at runtime, which is why no syscall-number scan ever found these stubs.

## 6. S6.4 - REFUTED. The scanner's stated blind spot is over-stated, not under-stated

*"The hit-set's distance histogram is saturated at its upper edge (max observed = 40), so
longer-range pairs exist and were not counted."* Measured distance histogram of the 406 hits:

```
+22:2  +25:8  +26:1  +27:48  +28:104  +29:121  +30:56  +32:14  +33:15  +35:16  +36:14  +37:2  +38:3  +40:2
```

It **peaks at +29 and decays**; only 2 of 406 sit at the boundary. Re-running the lane's own scanner
at `W=60` moves the count **406 -> 435** (+29), confirming a decaying tail rather than truncation.

## 7. Everything else reproduced exactly

- `.pdata` loader table: 18,580 entries, `Begin` **strictly** increasing, 0 all-zero, 0 with any field
  `== 0` or `== 1`, section split `packer1` 1,774 / `packer30` 9,609 / `packer31` 7,197.
- `.reloc`: 4,268 of 4,268 bytes consumed, 2,020 DIR64 + 10 ABSOLUTE, **0** DIR64 values in
  `[IB, IB+0x1000)`, **0** equal to `IB+1`.
- `0x200000001` literal: 17 file-wide, exactly one 8-aligned in a writable section (`0x941900`),
  whose neighbour `0x941908` is a DIR64 reloc to `IB+0x7000` (`.rwx`); the surrounding
  `packer1 0x84B030..0x84B1DC` contains `cpuid` x3, `xgetbv`, and all three `GenuineIntel` dwords -
  the `__isa_available` identification holds.
- MZ / PE: `4d5a0000` **0**, `50450000` **0**, control `ffff0000` **123**. Strengthened: all **60**
  raw `4d 5a` byte pairs in exec sections sit inside `movabs` immediates (each preceded by
  `48b8` / `49b9` / ...), and `66 3d 4d 5a` and `66 81 /4|/7 ... 4d 5a` are both **0**.
- Computed tails 4,769; constants 940 / 335 / 353 / 614 / 558; MBA identity
  `(~x)*C + (C+1)*x == x - C` verified over 2,000 random `x` for the worked constant and for 50
  random `C`; `-C - ImageBase = 0x166AA7B`; `0x166AA7B` an exact `.pdata` start.
- EP `0x855440` = `e94acfb300` = `jmp 0x139238F`; exact `.pdata` start; extent
  `0x139238F..0x139F768` = **54,233 B**; saves xmm10-xmm15; `and rsp,-0x40` present x5.
- `.rwx`: 4,096 raw bytes, **all zero**. disp32 FP control: **712 candidates / 27 real `ff 15`**.

## 8. Net effect on the lane

The lane's **positive** finding (section 4, the computed-tail dispatch and its address encoding)
survives verification intact and is the durable deliverable, despite a degenerate stated control and
two enumeration slips. The lane's **negative** finding (H2b + H3, "the constant-search method is
defeated and nothing computes base+1") does not survive: the method was tractable, it was executed,
and it produced a real `variable + ImageBase + 1` computation whose result is dereferenced, at
`packer31 0x03C8EDF2`. That site is the concrete successor lead this lane actually generated.

## 9. Files

`scratchpad/s132/verify/l6/` - `v_pe.py` (independent PE parse), `v_pdata.py`, `v_tails.py`,
`v_negconst.py` (940 constants + 4 controls), `v_worked.py`, `v_ib1.py`, `v_algebra.py`
(the H3 refutation), `v_r9.py`, `v_h4.py`, `v_mz.py`, `v_reloc.py`, `v_kill.py`, `v_derived.py`,
`mysecs.json`, `myfuncs.json`, `myneg.json`, `pairs.txt`.
