# S140 TIER 2 — LANE 1: ADVERSARIAL RE-DERIVATION OF THE SENTINEL MECHANISM

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game process.**
Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, RVA == file offset (verified, see C0).
All tooling written from scratch for this lane in `scratchpad/s140t2/L1tools/`
(`pe.py`, `cfg.py`, `dispcensus.py`, `disamb.py`, `realentry.py`, `funcres.py`) — a **sixth**
independent instrument, importing neither `tools/cfg.py` nor `scratchpad/s140/*`.
Full raw data: `scratchpad/s140t2/L1-raw-hitlists.txt` (578 lines).

---

## VERDICT UP FRONT

| Tier 1 claim | lane 1 verdict |
|---|---|
| **(a)** the `Iterations==0` snapshot block in `ULokiCMC::StartNewPhysics` | **CONFIRMED byte-exact — every listed instruction is correct.** But the listing is **INCOMPLETE**: it omits `0x055C2466 movaps xmm1,xmm2`, and it never disassembles the `Iterations != 0` path, which contains a **second, previously unrecorded `+0x12B0` accumulator**. |
| **(b)** `Iterations == 0` at the call site | **CONFIRMED, and now on stronger evidence than Tier 1 had.** Tier 1's support ("zero r8 writers, zero calls between") is *insufficient on its own*; I closed the gap with a predecessor census and a node-removal dominance test. |
| **(c)** "the ONLY CMC-side writer of `+0x16B0` is `0x055C244F`" | **CONFIRMED in substance, WRONG in detail — and the error is favourable.** There are **TWO** CMC-side payload writers (`0x055C244F` X/Y **and** `0x055C245E` Z), both inside `StartNewPhysics`, both on the `Iterations==0` path. Image-wide census over all decrypted `.text`: **83 writes to `+0x16B0..+0x16C7`; exactly 2 are on a `ULokiCMC`.** |

### THE FINDING THAT MATTERS MOST — IT IS NOT ABOUT (a), (b) OR (c)

**Tier 1 section 5's third decision clause is BACKWARDS and would discard a correct positive
result.** It reads:

> `+0xE8` no longer holds the sentinel ⇒ the probe's own control failed; the run is void.

**[M] `ULokiCMC::PhysFalling` (`0x055B89F0`) writes `Velocity` seven times, and it is dispatched
BY `StartNewPhysics` ITSELF, downstream of the snapshot, in the same call.** So under the
hypothesis the experiment is designed to confirm — *StartNewPhysics runs* — `+0xE8` **not** holding
the sentinel a few frames later is the **EXPECTED** observation, not an instrument failure.
Applying the rule as written voids the run precisely when the answer is YES. See section 4.

---

## C0. MY OWN CONTROLS (run before any analysis, my own code)

| control | result |
|---|---|
| PE flat (all 10 sections `VirtualAddress == PointerToRawData`) | **True** |
| ImageBase from optional header | **`0x7FF608F40000`** |
| `.text` pages non-zero | **16800 / 30281 = 55.48 %** (matches the brief exactly) |
| Known-DARK control `ULokiRespawnComponent::Respawn 0x5A6AC40` page | **0 / 4096** PASS |
| Five fold constants byte-exact (`c20000`/`33c0c3`/`32c0c3`/`b001c3`/`0f57c0c3`) | **5 / 5 PASS** |
| `ULokiCMC` vtable `.rdata 0x088F8570`, 5 known displacements | **5 / 5 PASS** |
| engine `UCMC` vtable `.rdata 0x07FBED58`, 3 known displacements (two-sided) | **3 / 3 PASS** |
| every function under analysis LIT (page non-zero 3129–3883) | **7 / 7 PASS** |
| `real_entry()` recovers the known owner of 3 known interior addresses | **3 / 3 PASS** |
| `.pdata` in this dump | **all zero in the first 1 MB** — pdata-seeded resolution unusable, as the brief warns |

**Independent CFG reproduction of engine `PerformMovement 0x035E9EC0`:** 1461 instructions,
**0 decode failures, span 6538 / covered 6538 / gaps 0**, 148 calls (115 direct / 33 indirect),
**0 indirect jumps**, **1 `ret` at `0x035EB1CA`**. Identical to Tier 1's four instruments.

---

## 1. CLAIM (a) — `ULokiCMC::StartNewPhysics 0x055C2430`

### 1.1 Byte-exact disassembly, full function

The function is **`0x055C2430 .. 0x055C249B`, 107 bytes** (a new frame `push r14` begins at
`0x055C249B`; there is no int3 padding, consistent with this build).

```
RAW BYTES 0x055C2430..0x055C2480
0x55C2430  0f 28 d1 45 85 c0 75 3d 44 38 81 c8 16 00 00 74
0x55C2440  07 44 88 81 c8 16 00 00 0f 10 81 e8 00 00 00 0f
0x55C2450  11 81 b0 16 00 00 f2 0f 10 89 f8 00 00 00 f2 0f
0x55C2460  11 89 c0 16 00 00 0f 28 ca c6 81 c8 16 00 00 01
0x55C2470  e9 1b e5 03 fe 7e 1c 80 b9 31 02 00 00 03 75 13
```

```
0x55c2430  0f28d1                   movaps  xmm2, xmm1                    ; save arg2 (DeltaTime)
0x55c2433  4585c0                   test    r8d, r8d                      ; r8d = Iterations
0x55c2436  753d                     jne     0x55c2475                     ; -> Iterations != 0 path
0x55c2438  443881c8160000           cmp     byte [rcx+0x16c8], r8b        ; flag vs 0
0x55c243f  7407                     je      0x55c2448
0x55c2441  448881c8160000           mov     byte [rcx+0x16c8], r8b        ; TOptional::Reset()  (CONDITIONAL)
0x55c2448  0f1081e8000000           movups  xmm0, [rcx+0xe8]              ; Velocity.X,.Y
0x55c244f  0f1181b0160000           movups  [rcx+0x16b0], xmm0            ; *** PAYLOAD WRITE (X,Y) ***
0x55c2456  f20f1089f8000000         movsd   xmm1, [rcx+0xf8]              ; Velocity.Z
0x55c245e  f20f1189c0160000         movsd   [rcx+0x16c0], xmm1            ; *** PAYLOAD WRITE (Z)  ***
0x55c2466  0f28ca                   movaps  xmm1, xmm2                    ; <== OMITTED BY TIER 1 sec 4.2
0x55c2469  c681c816000001           mov     byte [rcx+0x16c8], 1          ; *** SET ***
0x55c2470  e91be503fe               jmp     0x3600990                     ; tail -> engine SNP
0x55c2475  7e1c                     jle     0x55c2493                     ; Iterations < 0
0x55c2477  80b93102000003           cmp     byte [rcx+0x231], 3           ; MovementMode == MOVE_Falling
0x55c247e  7513                     jne     0x55c2493
0x55c2480  0f28c2                   movaps  xmm0, xmm2
0x55c2483  f30f5881b0120000         addss   xmm0, dword [rcx+0x12b0]      ; *** +0x12B0 accumulate ***
0x55c248b  f30f1181b0120000         movss   dword [rcx+0x12b0], xmm0
0x55c2493  0f28ca                   movaps  xmm1, xmm2
0x55c2496  e9f5e403fe               jmp     0x3600990                     ; tail -> engine SNP
```

### 1.2 What is CONFIRMED

- **[M] Every one of the six instructions Tier 1 section 4.2 lists is byte-exact correct** at the
  address it gives. No refutation.
- **[M] The payload write is reachable ONLY when `Iterations == 0`** — `test r8d,r8d / jne` skips
  the entire block. Claim (a)'s scoping is right.
- **[M] Every path through this function tail-jumps to engine `StartNewPhysics 0x3600990`.**
  Two `jmp 0x3600990`, no `ret`, no path that skips the engine body.
- **[M] The layout is a `TOptional<FVector>`**: payload `+0x16B0`(X) `+0x16B8`(Y) `+0x16C0`(Z),
  24 bytes, flag at `+0x16C8`. This corroborates Tier 1 section 4.5's naming from an independent
  direction (the write widths: `movups` 16 B + `movsd` 8 B).
- **[M] The `Reset()` at `0x055C2441` is CONDITIONAL, but the payload write at `0x055C244F` is
  UNCONDITIONAL on this path.** Good for the sentinel: prior flag state cannot suppress the snapshot.

### 1.3 Two DEFECTS in Tier 1's section 4.2 listing (neither changes its conclusion)

1. **It omits `0x055C2466 0f 28 ca movaps xmm1, xmm2`** — the restore of the `DeltaTime`
   argument clobbered by the `movsd` at `0x055C2456`. Tier 1's listing jumps
   `0x055C245E` to `0x055C2469`. Cosmetic here, but it is presented as a complete instruction
   listing and is not one.
2. **It never disassembles the `Iterations != 0` path, which contains a SECOND `+0x12B0`
   accumulator** — `0x055C2483 addss xmm0,[rcx+0x12b0]` / `0x055C248B movss [rcx+0x12b0],xmm0`,
   gated on `Iterations > 0 && MovementMode == 3 (MOVE_Falling)`.
   **This is not recorded anywhere in `CLAUDE.md` or Tier 1**, both of which attribute the
   measured 1.0x-real-time advance of `+0x12B0` solely to `0x055B840C` in
   `ULokiCMC::PerformMovement`.
   **[I], NOT [M]:** if this second site also fired every frame, `+0x12B0` would advance faster
   than 1.0x real time; it does not, which is *consistent with* the recursive-iteration path not
   being taken. **That is an inference from a live measurement I did not take — do not upgrade it.**
   It matters because `+0x12B0` is a load-bearing instrument in the S139 record.

---

## 2. CLAIM (b) — `Iterations == 0` at `0x035EB13A`

### 2.1 Byte-exact disassembly

```
RAW BYTES 0x035EB120..0x035EB150
0x35EB120  ff 90 08 0a 00 00 48 8b 03 45 33 c0 41 0f 28 cb
0x35EB130  44 89 bb dc 03 00 00 48 8b cb ff 90 20 07 00 00
0x35EB140  48 8b 03 48 8b cb ff 90 b8 06 00 00 84 c0 75 7b
```

```
0x35eb120  ff90080a0000     call  qword [rax+0xa08]
0x35eb126  488b03           mov   rax, [rbx]                 ; rbx = this (CMC)
0x35eb129  4533c0           xor   r8d, r8d                   ; *** Iterations = 0 ***
0x35eb12c  410f28cb         movaps xmm1, xmm11               ; DeltaTime
0x35eb130  4489bbdc030000   mov   dword [rbx+0x3dc], r15d    ; NumJumpApexAttempts
0x35eb137  488bcb           mov   rcx, rbx
0x35eb13a  ff9020070000     call  qword [rax+0x720]          ; *** StartNewPhysics ***
0x35eb140  488b03           mov   rax, [rbx]
0x35eb143  488bcb           mov   rcx, rbx
0x35eb146  ff90b8060000     call  qword [rax+0x6b8]          ; HasValidData() #2
0x35eb14c  84c0             test  al, al
0x35eb14e  757b             jne   0x35eb1cb
```

### 2.2 CONFIRMED — and Tier 1's argument was insufficient as stated

Tier 1's support is *"there are **zero r8 writers and zero calls** between `0x035EB129` and
`0x035EB13A`"*. Both halves are true (I reproduce them), but **they do not establish the claim on
their own**: a branch landing at `0x035EB12C`, `0x035EB130` or `0x035EB137` from elsewhere in the
function would reach the call with `r8d` holding something else, and no amount of "no writers
between" excludes that. Tier 1 did not test it. I did.

**TEST 1 — predecessor census (every in-edge, from the full 1461-instruction CFG):**

```
0x35EB129  preds: ['0x35EB126(fall)']      <- exactly one, linear
0x35EB12C  preds: ['0x35EB129(fall)']      <- exactly one, linear
0x35EB130  preds: ['0x35EB12C(fall)']      <- exactly one, linear
0x35EB137  preds: ['0x35EB130(fall)']      <- exactly one, linear
0x35EB13A  preds: ['0x35EB137(fall)']      <- exactly one, linear
```
**[M] No branch anywhere in the function targets the interior of the sequence.**

**TEST 2 — dominance by node removal (a different algorithm from TEST 1):**
```
call reachable from entry normally         : True
call reachable with 0x35EB129 BANNED       : False
=> xor r8d,r8d DOMINATES the call          : True
```

**TEST 3 — every `r8`-family writer in the whole function: 100 sites, RAW list emitted.**
The two nearest to the call are `0x035EAFD0 mov r8,r12` and `0x035EB05A mov r8,[rbx+0x198]`
(both **before** the xor) and `0x035EB2CA lea r8,[rbp-0x20]` (**after** the call).
**Strictly between `0x035EB129` and `0x035EB13A`: ZERO.**

Therefore **[M] `Iterations == 0` at the call site.** Claim (b) survives, on evidence Tier 1 did
not have.

**Instrument caveat (mine):** my write-classifier flags `test r8d,r8d` as a destination write
because `operands[0].type == REG`. `test` does not write. The `regs_access` written-set correctly
returns empty for those, and none of them lies in the region, so the conclusion is unaffected —
but the mandated `operands[0]` rule **over-reports for `cmp` and `test`**, and I excluded those two
mnemonics explicitly everywhere below. That exclusion is itself a judgement, stated here.

---

## 3. CLAIM (c) — THE `+0x16B0` WRITER CENSUS (image-wide)

### 3.1 Method

Scan all of `.text` for the disp32 encodings of `0x16B0..0x16CF` (**disp8 cannot encode a value
> 0x7F, so disp32 is the only encoding — no coverage gap from that direction**), attempt an
instruction decode at every start 1..15 bytes back, keep decodes whose MEM operand carries the
displacement. Disambiguate overlapping decodes by **linear-sweep voting** from 15 different
back-offsets. Classify writes by **`operands[0].type == MEM`** (never `regs_access` — the recorded
S140 capstone defect), then exclude `cmp`/`test`. Resolve the containing function by taking the
**earliest entry candidate whose recursive-descent CFG actually covers the write address**
(3/3 controls pass).

**FLOOR CAVEAT, stated as required: only 16800 / 30281 = 55.48 % of `.text` pages are decrypted
in `merged13`. Every count below is a FLOOR. A writer sitting on a dark page is invisible to this
census BY CONSTRUCTION.** Dark pages are all-zero so they cannot contain the byte pattern; this is
self-filtering, not self-correcting.

### 3.2 RAW RESULT (before any classification)

```
disp32 candidates in [0x16B0,0x16CF] over all .text : 487 distinct instruction addresses
  confirmed real (linear-sweep vote > 0, == cluster max) : 253
  UNRESOLVED (no back-offset sweep ever landed on them)  :   4
  classified WRITE (operands[0].type == MEM)             : 142
  classified READ / other                                : 111
```
Full 487-row raw list: `scratchpad/s140t2/L1-raw-hitlists.txt`.

Restricting to the **payload range `+0x16B0..+0x16C7`** and excluding `cmp`/`test`:

```
TRUE writes to +0x16B0..+0x16C7, all decrypted .text : 83
  across 29 distinct containing functions
  base-register distribution: rbp 63, rbx 30, rcx 14, rdi 13, rsp 12, r14 5, rsi 3, rax 1, r15 1
```

### 3.3 CLASSIFICATION — which of the 83 are on a `ULokiCMC`

Three independent discriminators, all applied.

**(i) vtable membership of the containing function.** Of the 21 owner functions, **exactly one**
has its pointer in the `ULokiCMC` vtable:

```
0x55C2430  ptr-refs=1  0x088F8C90 = ULokiCMC VT + 0x720   *** ULokiCMC::StartNewPhysics ***
0x146DAD0  ptr-refs=0   NONE          0x3A42D80  ptr-refs=0   NONE
0x47E5170  ptr-refs=1   0x084B53F0    0x4AF2200  ptr-refs=0   NONE
0x5292040  ptr-refs=0   NONE          0x6E68CB0  ptr-refs=0   NONE
0x6E6A720  ptr-refs=15  0x0926F860…   0x559E180  ptr-refs=0   NONE
0x3D234C0  ptr-refs=0   NONE          + 5 more, all NONE
```

**(ii) base-register provenance** (recursive-descent over each containing function):

| owner | base-reg definition | class of write |
|---|---|---|
| `0x1265DF0`, `0x127BAB0`, `0x128E530` | `sub rsp, rax` (dynamic alloca) | **stack local** |
| `0x14B7F60` | `lea rbp, [rsp-0x9698]` | **stack local** (38 KB frame) |
| `0x14CAB40` | `lea rbp, [rsp-0x43738]` | **stack local** (276 KB frame) |
| `0x27D48A0` | `lea rbp, [rsp-0x2310]` | **stack local** |
| `0x146DAD0` | `mov rbp, rcx` | `this` of some class |
| `0x3A42D80`, `0x4AF2200` | `mov rdi, rcx` | `this` of some class |
| `0x47E5170`, `0x5292040`, `0x6E68CB0`, `0x6E6A720` | `mov rbx, rcx` | `this` of some class |
| **`0x559E180`** | `mov r14, rcx` | **`ALokiCharacter`** — see (iii) |
| **`0x55C2430`** | `rcx` = `this` directly | **`ULokiCMC`** |

**(iii) vtable INSTALL — this settles the `0x559E180` / `0x559F580` question Tier 1 section 4.6
adjudicated:**

```
fn 0x559E180 : 0x559E1DC lea rax,[rip -> .rdata 0x088E5CA8]   *** the pawn/character VTABLE ***
fn 0x559F580 : 0x559F5AC lea rax,[rip -> .rdata 0x088F8570]   *** the ULokiCMC VTABLE ***
fn 0x530A898 : 0x530AAAA lea rax,[rip -> .rdata 0x088F8570]  +  0x530ABD2 mov edx,0x19D0  (sizeof)
```
**[M] Tier 1 section 4.6 is CORRECT and I reproduce it independently.** `0x0559EA2F` and
`0x0559EA3F` write an `ALokiCharacter`, not a CMC. `0x0559F580` **is** the `ULokiCMC` constructor.
`sizeof(ULokiCMC) == 0x19D0` confirmed from the destructor's `operator delete` size.

**(iv) caller analysis (an `e8 rel32` scan; a FLOOR):** for all 21 owners,
**`inULokiCMCvtable = 0`** — *none* of them is called from any `ULokiCMC` vtable function.
`0x55C2430` itself has **0 direct callers**, consistent with vtable-only dispatch and with Tier 1's
"1 pointer image-wide at `LokiVT+0x720`".

### 3.4 VERDICT ON (c)

**[M, floor-bounded] Of 83 confirmed writes to `+0x16B0..+0x16C7` across all decrypted `.text`,
exactly TWO are on a `ULokiCMC`: `0x055C244F` and `0x055C245E`, both inside
`ULokiCMC::StartNewPhysics`, both on the `Iterations == 0` path.**

**Tier 1 sections 4.6 and 5 both say "the only CMC-side writer of `+0x16B0` is `0x055C244F`". That
is incomplete — `0x055C245E` writes the Z component at `+0x16C0`, which is inside the payload the
sentinel test reads.** The error is favourable (the second writer is in the same block, same path,
same source) but a successor reading section 5 and then dumping `+0x16B0..+0x16C7` would find a
writer the digest does not list, and would have to re-derive this.

**Residual, honestly stated:** "not in the `ULokiCMC` vtable and not called from one" does **not
logically exclude** a non-virtual `ULokiCMC` member function among the other 19 owners. What
excludes them in practice is (ii) — 7 are provably stack frames, and the remaining `this`-based
ones live in unrelated code regions with unrelated vtables. **Grade the exclusion [M] for the 7
stack cases and [I, strong] for the rest.** Tier 1 graded the whole thing [M].

### 3.5 CROSS-CHECK — Tier 1's section 4.6 FLAG (`+0x16C8`) table is a strict SUBSET

I censused `+0x16C8` the same way: **35 confirmed writes image-wide.**

- **All 5 of Tier 1's rows reproduce exactly** (`0x055C2441`, `0x055C2469`, `0x0530ABF9`,
  `0x0530AB4C`, `0x0559FDF4`) — **zero false rows in Tier 1's table.**
- **30 rows Tier 1 does not list.** Six are in the Loki CMC/character neighbourhood:
  `0x055A6BCB` (fn `0x055A69F0`), `0x055A7562` (fn `0x055A7440`), `0x055B860B`
  (fn `0x055B8370` = `ULokiCMC::PerformMovement`), `0x055BDD6C`, `0x055BE974`, `0x055C0DA9`,
  plus `0x0559EA48` (fn `0x0559E180`, the `ALokiCharacter` ctor).
- Tier 1 *did* discuss `0x055B860B`, `0x055A6BCB` and `0x055C0DA9` in prose and correctly
  dismissed them as non-CMC bases; it just did not put them in the table. **Its "complete CMC-side
  writer set" heading over-claims — the table is the CMC-side subset, not the write set.**
- **None of the 30 touches the payload.** They are all at `+0x16C8` or above. Several are
  `movups [reg+0x16c8], xmm0`, i.e. **16-byte** stores covering `+0x16C8..+0x16D7` — which on a
  `ULokiCMC` would clobber the flag *and* `+0x16D0`. That is another reason the **payload**, not
  the flag, is the right readout.

---

## 4. THE VELOCITY HAZARD — AND IT INVALIDATES TIER 1'S THIRD DECISION CLAUSE

### 4.1 The census

Same method, disp `+0xE8..+0xFF` (again disp32-only: `0xE8` as a signed byte is `-24`, so the
`+0xE8` displacement cannot be encoded as disp8).

```
candidate instruction addresses, whole .text      : 87,029
confirmed real (vote > 0)                          : 44,462
confirmed WRITES (operands[0]==MEM, cmp/test out)  : 18,044
```
`+0xE8` is an extremely common structure offset, so an image-wide list is not the instrument.
I narrowed to the **CMC scope**: `ULokiCMC` vtable slots (358 lit) union engine `UCMC` vtable slots
(368 lit) = 439 level-0 functions, union their 511 direct callees = **913 functions**.

```
writes to +0xE8..+0xFF inside CMC scope : 199
  in a ULokiCMC vtable function          : 120
  in an engine UCMC vtable function      : 144
```
Narrowing again to functions reachable from the **movement roots** (`engine/Loki PerformMovement`,
`engine/Loki StartNewPhysics`, `engine TickComponent`, `ULokiCMC::PhysFalling`) within 3
direct-call levels — 311 functions — and dropping `rsp`-based (definitionally stack) writes:
**34 writes.**

### 4.2 The one that matters

```
depth 0  fn 0x55B89F0  ULokiCMC::PhysFalling   writes=7
     0x55B8F2E f20f1183f8000000  movsd   qword ptr [rbx + 0xf8], xmm0
     0x55B8FBE 0f118be8000000    movups  xmmword ptr [rbx + 0xe8], xmm1
     0x55B8FC5 f20f1193f8000000  movsd   qword ptr [rbx + 0xf8], xmm2
     0x55B9032 0f118be8000000    movups  xmmword ptr [rbx + 0xe8], xmm1
     0x55B9039 f20f1193f8000000  movsd   qword ptr [rbx + 0xf8], xmm2
     0x55B9052 0f118be8000000    movups  xmmword ptr [rbx + 0xe8], xmm1
     0x55B9059 f20f1193f8000000  movsd   qword ptr [rbx + 0xf8], xmm2
```
**[M] `rbx` in `ULokiCMC::PhysFalling` has exactly two definitions: `0x055B8A28 mov rbx, rcx`
(= `this`) and `0x055B909E mov rbx,[r11+0x38]` (a restore).** Therefore these are writes to
**`ULokiCMC::Velocity`** — the `movups`+`movsd` pair is the same 16+8 FVector shape as the snapshot.

Separately: **engine `PerformMovement` does NOT write Velocity.** Its two `+0xE8`/`+0xF8` writes
(`0x035EA113`, `0x035EA11E`) are `rbp`-based, and `rbp` in that function is
`0x035E9EC5 lea rbp,[rsp-0x860]` — a **stack frame pointer**. Its `this` is `rbx`
(`0x035E9EFD mov rbx,rcx`). So those are stack locals, not Velocity. [M]

**[M] `PhysFalling` is dispatched by `StartNewPhysics` itself.** Read from the jump table:

```
engine StartNewPhysics 8-entry table at .text 0x03600BF8 (dword RVAs)
  case 0 MOVE_None          @0x3600BA8 : (no vcall)
  case 1 MOVE_Walking       @0x3600A97 : disp 0x970 -> 0x35EF960
  case 2 MOVE_NavWalking    @0x3600AAE : disp 0x978 -> 0x35EEA50
  case 3 MOVE_Falling       @0x3600AC5 : disp 0x830 -> LokiVT 0x55B89F0  *** ULokiCMC::PhysFalling ***
  case 4 MOVE_Swimming      @0x3600AF3 : disp 0x988 -> 0x35EF1D0
  case 5 MOVE_Flying        @0x3600ADC : disp 0x980 -> 0x35EE5A0
  case 6 MOVE_Dashing(Loki) @0x3600B0A : disp 0xCC8 -> 0x35EB870
  case 7 MOVE_Custom        @0x3600B21 : disp 0x990 -> LokiVT 0x55B88E0
```
This independently reproduces `CLAUDE.md`'s recorded S139 finding that this build inserts
`MOVE_Dashing` at index 6 (case 6 -> disp `0xCC8`, case 7 -> `PhysCustom` disp `0x990`) — a passing
positive control on my whole jump-table read.

**And the pawn's `MovementMode` is measured `3 = MOVE_Falling` (S139, both bot and player).**

### 4.3 The consequence

Ordering within one frame, all [M] from the bytes:

```
ULokiCMC::StartNewPhysics  0x055C244F/5E  ->  snapshot Velocity into +0x16B0..+0x16C7
      tail jmp 0x3600990
engine StartNewPhysics     case 3          ->  disp 0x830
ULokiCMC::PhysFalling      0x055B8FBE etc. ->  WRITES Velocity at +0xE8/+0xF8
```

So if `StartNewPhysics` runs:
- `+0x16B0` **holds the sentinel** (the positive result)
- `+0xE8` has been **overwritten by `PhysFalling`** — and Tier 1's rule then says *"the probe's
  own control failed; the run is void."*

**The rule as written voids the run in exactly the case where the answer is YES.**

**Grade carefully.** That `PhysFalling` *writes* Velocity is **[M]**. That it *will* write it on
this particular pawn on the frame in question is **[I]** — the writes sit behind branches I did not
prove are taken, and if `StartNewPhysics` does **not** run then `PhysFalling` does not run either
and `+0xE8` keeps the sentinel. The asymmetry is the whole problem: **the third clause is only
harmless under the hypothesis it is meant to test being FALSE.**

### 4.4 Recommended fix to the experiment (cheap, no extra flight)

Split the control in time:

1. Poke `CMC+0xE8/F0/F8` with the sentinel, then **read `+0xE8` back IMMEDIATELY** (same
   `ReadProcessMemory`, before yielding). *This* is the "did my write land" control.
2. Wait at least 3 frames. Read `+0x16B0..+0x16C7` **and** `+0xE8` and **record both raw**.
3. Decision table:

| `+0x16B0` | `+0xE8` (late) | conclusion |
|---|---|---|
| sentinel | anything | **`ULokiCMC::StartNewPhysics` ran with `Iterations == 0`** [M] |
| `(0,0,0)` | still sentinel | **it did not run** [M] (nothing consumed Velocity either) |
| `(0,0,0)` | changed | **UNINTERPRETABLE** — something wrote Velocity without the snapshot running; report raw, do not force a verdict |
| anything | step-1 readback failed | run void (probe fault) |

Row 3 is a real fourth outcome that Tier 1's three-way rule collapses into "void".

Also worth pre-registering: `+0x16B0` may hold a *stale* sentinel from an earlier frame — the
payload is durable and nothing clears it. **Zero `+0x16B0..+0x16C7` first, then poke `+0xE8`,**
so a hit is attributable to a snapshot taken after the poke.

---

## 5. TASK 5 — OTHER WRITERS / BULK WRITES

### 5.1 Is `+0x16B0` ever written with something other than Velocity?

**[M, within the census's reach] No.** The only two CMC-side writers both source directly from
`Velocity`: `0x055C2448 movups xmm0,[rcx+0xe8]` feeding `0x055C244F`, and
`0x055C2456 movsd xmm1,[rcx+0xf8]` feeding `0x055C245E`. There is no other value on that path.
The `ULokiCMC` constructor `0x0559F580` writes the **flag** (`0x0559FDF4`) but **does not
initialise the payload** — consistent with `TOptional` semantics.

### 5.2 memcpy / rep-movs shaped bulk writes

Scanned all 439 `ULokiCMC` + engine-`UCMC` vtable functions:

```
rep / movs-family instructions            : 0
size immediates >= 0x16C8 into r8/r8d     : 0
top r8 size immediates in scope           : 1 (x38), 248 (x29), 255, 240, 16
```

**THIS CANNOT BE SETTLED OFFLINE, AND HERE IS THE BOUND.** The census is blind to:
- a `memcpy(dst, src, N)` whose **size is a register**, not an immediate;
- a copy whose **destination is a computed pointer** (`lea rax,[rcx+0x1600]` then `mov [rax+0xb0]`)
  — a two-instruction form no single-displacement scan can see;
- an **indexed** addressing form (`[rcx+rax*1+disp]`) where the effective offset is only
  `0x16B0` at runtime;
- anything on the **44.52 % of `.text` that is not decrypted**;
- the whole **Angelscript AOT band**, which this census does not treat specially.

**[I, moderate] a bulk write is unlikely** — `+0x16B0` is not a reflected UPROPERTY (Tier 1
section 4.5, which I did not re-derive), so neither UE property serialization nor the net
serializer has a reason to address it, and `sizeof(ULokiCMC)` = `0x19D0` appears only in the
destructor's `operator delete`. **That is an argument, not a measurement. Do not record it as [M].**

**The sentinel test is itself the cheapest way to close this**: step 1's immediate readback plus
a second read a few frames later, with the payload pre-zeroed, distinguishes "nothing writes it"
from "something else writes it" directly, on the live object.

---

## 6. SUMMARY OF DELTAS TO TIER 1

| # | item | grade |
|---|---|---|
| 1 | section 4.2 listing **omits `0x055C2466 movaps xmm1,xmm2`** | [M] cosmetic |
| 2 | section 4.2 never shows the `Iterations != 0` path; it contains a **second `+0x12B0` accumulator** at `0x055C2483/8B`, recorded nowhere in the repo | [M] that it exists; [I] that it never fires |
| 3 | (b)'s stated support ("no r8 writers, no calls between") is **insufficient**; closed here by predecessor census + node-removal dominance | [M] |
| 4 | sections 4.6/5 "the only CMC-side writer of `+0x16B0` is `0x055C244F`" — **there are two**, `0x055C245E` writes Z at `+0x16C0` | [M] |
| 5 | section 4.6's "complete CMC-side writer set" for `+0x16C8` — **5 rows all correct, but 30 more writers exist image-wide**; the table is the CMC-side subset, not the write set | [M] |
| 6 | section 4.6's `0x0559E180` vs `0x0559F580` adjudication — **independently reproduced from the vtable installs** | [M] confirmed |
| 7 | **section 5's third decision clause is backwards**; `ULokiCMC::PhysFalling` writes Velocity downstream of the snapshot, dispatched by `StartNewPhysics` case 3 on the pawn's measured `MOVE_Falling` | [M] that it writes; [I] that it fires |
| 8 | Whole-function CFG of engine `PerformMovement` reproduced exactly (1461 / 0 / 6538 / 6538 / 0 / 148 / 0 / 1) | [M] confirmed, 6th instrument |

**Nothing in Tier 1's headline is refuted.** The latch retraction stands; claims (a), (b), (c) all
survive. What changes is (i) two incomplete listings, (ii) one insufficient argument now made
sufficient, and (iii) **one decision rule that would have thrown away the answer.**
