# ADVERSARIAL VERIFICATION of `scratchpad/s132/lanes/L2-resizegrow-abi.md`

Offline only. `dumps/merged4.dump.exe`, ImageBase `0x7FF6AF000000`, file offset == RVA.
Every address recomputed with `python -c` / `struct.unpack` / capstone. Zero launches.
Independent scanners written from scratch (NOT `fkdis callxref` / `findptr`, both of which cap at 200 rows).

**Headline: the report's operational conclusion survives. Its evidence does not, in four places.**
The bytes, the signature, the growth math and the "the reallocator is not stripped" result all reproduce
exactly. But two [M]-graded numbers in §7 are wrong or coverage-contaminated, one [M] TLS claim is refuted
by a node in the report's *own* call graph, one [M] consequence claim (`no crash dump`) is
COVERAGE-BLOCKED, and one worked calculation printed as machine-checked is arithmetically false.

---

## Score

| verdict | n |
|---|---|
| CONFIRMED | **20** |
| REFUTED | **4** |
| UNSUPPORTED (true or unknown, but not established by the evidence given) | **6** |
| DEGENERATE-CONTROL | 0 |

---

## A. CONFIRMED

**A1. The 149 bytes of `0x00F988D0`.** Re-disassembled; byte-for-byte identical to the report's §1
listing, including every displacement. CONFIRMED.

**A2. Extent = 149 B, unchained.** `pdata_union.csv` single row `0x00F988D0..0x00F98965`,
`seen_in_dumps 76`; previous row ends `0x00F988C3`, next row begins `0x00F98970`. `0x00F98965` is not the
start of any row. CONFIRMED.

**A3. Byte-identity across images.** I scanned **all 27** `*.dump.exe` under `dumps/` (23 single-state +
`merged`, `merged2`, `merged3`, `merged4`): **27/27 byte-identical, 0 differing, 0 zero.** Stronger than
the report's 26. CONFIRMED.

**A4. The report's coverage negative control is real and NOT degenerate.**
`0x055CD738` reads page-`ZERO` in `dumps/merged.dump.exe` and `present` in `merged2` / `merged3` /
`merged4` / `tuthero`. The detector fires, and it fires on a page central to this very analysis.
CONFIRMED.

**A5. Signature `void __fastcall(TArray* rcx, int32 OldNum edx)`; `{Data@0, Num@8, Max@0xC}`; 8-byte
element, 8-byte alignment.** Re-derived. Independent corroboration the report did not use: the
**adjacent sibling at `0x00F98970`** is the same function for a **0x18-byte** element — identical
prologue and identical slack formula, but `lea rcx,[rax+rax*2]; shl rcx,3` (×24), `mov r9d,0x18`, and a
`0xAAAAAAAAAAAAAAAB` magic-divide by 24 instead of `shr rax,3`. It is a per-element-size family, and
`0x00F988D0` is the 8-byte member. CONFIRMED.

**A6. Frame arithmetic / nonvolatile preservation.** entry `rsp=R`; `push rdi` + `sub rsp,0x30` ⇒
`rsp=R-0x38`; `[rsp+0x40]=R+8` (the RBX spill slot) and `[rsp+0x48]=R+0x10` (RSI) — machine-checked, both
`True`. `pop rdi` restores RDI. capstone written-register set over the 149 bytes is
`{rax,rbx,rcx,rdi,rsi,rsp,r8d,r9d,rflags}`: RBP and R12–R15 are never touched. CONFIRMED.

**A7. True inputs are `rcx` and `edx` only.** RBX/RSI/RDI are read *only* by the three spill instructions
at `0xF988D0/D5/DA` and are redefined at `0xF988DF/E3/E5`. CONFIRMED.

**A8. `TSizedHeapAllocator<32>`.** `0x00FAF9F4 mov ecx,0x20`; descriptor `0x0768B770` → fmt `0x0768B790`
= `"Trying to resize TSizedHeapAllocator<%d> to an invalid size of %lld with element size %I64u"`, file
`...\Containers\ContainerAllocationPolicies.cpp`, line **14**. CONFIRMED.

**A9. The guard.** `0x00F988E8 cmp ebx,edx` / `0x00F988EA jl 0x00F9895D` — signed 32-bit, equality
passes. CONFIRMED.

**A10. `[[noreturn]]` shape of both fatal handlers.** `0x00FAAC80..0x00FAACA2` ends `ebfe = jmp $` at
`0x00FAACA0`; `0x00FAAD40..0x00FAAD64` ends `ebfe` at `0x00FAAD62`; both callers emit `int3`
(`0x00F98964`, `0x00FAFA01`). CONFIRMED.

**A11. And "Fatal" is *measurable* — better evidence than the report gave.** The report asserted Fatal
from the noreturn shape plus known UE source. It is actually readable off the log-site descriptor, which
carries the verbosity at `+0x14`: `*(u32)(0x0768B848+0x14) == 1` and `*(u32)(0x0768B770+0x14) == 1`, and
`ELogVerbosity::Fatal == 1`. CONFIRMED, and upgraded from the report's inference to a measurement.

**A12. `OnInvalidArrayNum` descriptor.** `0x00FAAC8E lea rdx,[rip+0x66E0BBA]` → **`0x0768B848`** and
`0x00FAAC95 lea rcx,[rip+0x8D7E3DB]` → **`0x09D29070`**, both recomputed from the *next-instruction*
address. `[0x768B848+0] -> 0x768B870` = UTF-16 `"Trying to resize TArray to an invalid size of %llu"`;
`+8 -> 0x768B8E0` = the ANSI path; `+0x10` = line **8**. `FLogCategory@0x09D29070` reads
`05 00 05 07 e9 08 00 00` = `{Verbosity=5, DebugBreakOnLog=0, DefaultVerbosity=5,
CompileTimeVerbosity=7, FName=0x8E9}` — exactly as reported. CONFIRMED.

**A13. `OldNum` is dead past the guard.** `ResizeAllocation`'s incoming `rdx` is never read on any of its
three paths: the `Data==null && NewNum==0` early-out (`0xFAF9C4 → 0xFAF9EB`) never touches it; the live
path overwrites it at `0xFAF9D7 movsxd rdx,r8d`; the fatal path at `0xFAF9F1`. CONFIRMED — and this is
the report's best original result.

**A14. Growth math, both orderings.** Simulated: `Num=1,Max=0,OldNum=0` and `Num=0,Max=0,OldNum=0` both
give `cmova` NOT taken (1 and 0 are not *above* 4) ⇒ `Grow=4`, `rcx=32`, `QuantizeSize(32,8)`, `cmovg`
NOT taken, `ArrayMax=4`, `ResizeAllocation(...,NewMax=4,BPE=8,Align=8)` ⇒ `imul` ⇒ **32 bytes**,
`FMemory::Realloc(nullptr,32,8)`. **Bit-identical for `Num` 0 or 1.** CONFIRMED.

**A15. 5th-argument slot.** Caller writes `[rsp+0x20]=8` at `0xF9892C`; callee reads `[rsp+0x50]` at
`0xFAF9DA`. Machine-checked: caller_rsp+0x20 == R'+0x28 == callee `[rsp+0x50]`. CONFIRMED.

**A16. `GMalloc` RVA and value; the chain is REAL.** Three independent rip-relative loads (`0x010078C6`,
`0x01007F05`, `0x01007F19`) all recompute to **`0x09D49180`**; `*(u64)0x09D49180 = 0x1FC1C1486A0` in
`merged4`. Virtual slots `+0x50` (index 10, QuantizeSize) and `+0x38` (index 7, Realloc). The
`FMallocBinned2` string is present at `0x076A0AD0`. No hop equals any of the five known folds.
**This is V3, the lane's actual deliverable, and it holds.** CONFIRMED.

**A17. `0x010078C0` has no `.pdata` row, and that is correct.** The gap is `0x010078AB..0x010078E0`; the
body is 29 B, has no `push`, no `sub rsp`, no nonvolatile save, and tail-`jmp`s — a Win64 leaf, which
needs no unwind data. CONFIRMED.

**A18. Naive rel32 census.** My own uncapped whole-`.text` scan (VA `0x1000`, VS `0x7649000`, read from
the section table): **4,363 hits = 4,362 `E8` + 1 `E9`.** Exact reproduction. CONFIRMED.

**A19. Nothing stores the address — with the positive control the report omitted.** Uncapped unaligned
scan of all 178,130,944 bytes for `0x7FF6AFF988D0`: **0 hits.** Controls in the same pass: fold
`0xF7EC20` → **165,789**, exec thunk `0x5254180` → **92**, `0x055CD510` → **1**. The scanner is not
broken. CONFIRMED.

**A20. The spot-checked "unverifiable" site `0x011EA2A2`** reproduces exactly as printed, and it genuinely
has no containing `pdata_union` row. CONFIRMED.

---

## B. REFUTED

### B1. REFUTED — "NOT a boundary (false positive): 1 (`0x00E4A03F`)"

`0x00E4A03F` is a **genuine call site**; the report's own coverage rule was not applied to it.

```
0x00E4A02F  8d 4f 01        lea ecx,[rdi+1]
0x00E4A032  3b 48 0c        cmp ecx,[rax+0xC]        ; vs Max
0x00E4A035  89 48 08        mov [rax+8],ecx          ; Num = OldNum+1
0x00E4A038  76 0a           jbe 0x00E4A044           ; fits -> skip growth
0x00E4A03A  8b d7           mov edx,edi              ; OldNum
0x00E4A03C  48 8b c8        mov rcx,rax              ; &TArray
0x00E4A03F  e8 8c e8 14 00  call  ->  0x00E4A044 + 0x14E88C = 0x00F988D0
```

The `jbe` at `0x00E4A038` targets **`0x00E4A044`** — exactly the instruction after the 5-byte call. That
self-consistency cannot arise by chance, and it is the identical idiom to the game's own site at
`0x055CD738`.

**Root cause of the misclassification, measured:** the containing row is `0x00E49F80..0x00E4A08E`, and
**page `0x00E49000` is ALL-ZERO (undecrypted) in `merged4`**. The row therefore *begins* inside 128 bytes
of zeros; linear disassembly from the row start decodes `add byte ptr [rax], al` ×64 and desyncs
(`0x00E4A000 sbb cl,al`; `0x00E4A002 call 0x74E64811`). **A coverage artifact recorded as a property of
the code** — the pattern `docs/method-rules.md` §1 exists to catch.

### B2. REFUTED — "across ≥ 3,292 distinct functions"

Wrong unit **and** wrong direction. 3,292 is the count of distinct containing **`.pdata` rows**, and a
function spans several chained rows, so rows *over*-count functions. Collapsing chains (walk back while
`rows[i-1].end == rows[i].begin`):

```
distinct containing ROWS : 3292
distinct chain HEADS     : 3087
of those rows, non-head  : 2006      <- 61% of the rows are mid-function starts
```

**Correct statement: ≤ 3,087 distinct functions.** 3,292 is a ceiling on the function count, never a
floor. (It also means the boundary check disassembled from a mid-function address in 2,006 of 3,292
cases — see U2.)

### B3. REFUTED — the printed rel32 decode at `0x055CD75B`

The report prints:

> `rel32 = 0xFB9CB170 (-73,895,568)` … `0x55CD75B + 5 + (-73895568) = 0x00F988D0` ✔ CONFIRMED

`0xFB9CB170` as int32 is **-73,617,040**, not -73,895,568 (the two differ by 278,528). Feeding the
printed decimal back through the printed equation gives **`0x00F548D0`**, not `0x00F988D0`.

**The conclusion is nevertheless correct** — unpacking the real bytes gives -73,617,040 and
`0x055CD760 - 73,617,040 = 0x00F988D0` ✔ (V7 CONFIRMED). But the *shown work* is false, and it falsifies
the report's own header claim *"Every address recomputed with `python -c` / capstone; none by hand."*
No machine prints -73,895,568 for `0xFB9CB170`.

### B4. REFUTED — V6 as stated: "No TLS, no segment-prefixed access"

`0x00FF93C0` — the lazy `GMalloc` creator, which is **a node in the report's own enumerated call graph**
(`0x1007EF0 -> {0xFF93C0, GMalloc vtable}`) — takes a TLS access on its second instruction:

```
0x00FF93CD  65 48 8b 04 25 58 00 00 00   mov rax, qword ptr gs:[0x58]
```

My capstone segment-operand census: `ResizeGrow` 0, `QuantizeSize` 0, `ResizeAllocation` 0,
`FMemory::Realloc` 0, `OnInvalidArrayNum` 0, `0xFAAD40` 0, logger `0x0106B5F0` 0 —
**`0x00FF93C0`: 1 (`gs`)**. §8's table row is correctly *scoped* ("across all four functions");
**V6 drops the scope**, and the unscoped sentence is false. Harmless in practice (`0xFF93C0` runs only if
`GMalloc` is null, and TLS is not by itself a hazard for a `ProcessInternal` / `Func`-swap hook) — but it
is an [M] claim stated wider than its evidence.

---

## C. UNSUPPORTED (true, or unknown — but not established by the evidence given)

### U1. "no crash dump … not catchable by SEH" (part of V4, graded [M]) — COVERAGE-BLOCKED

`OnInvalidArrayNum` calls the logger `0x0106B5F0`, whose **first callee is `call 0x010A9B70` at
`0x0106B636`** — and page **`0x010A9000` is ALL-ZERO in `merged4`, `merged3`, `merged2`, `merged` and
`tuthero`** (positive controls in the same pass: `0x010A8000` present, `0x010AA000` present,
`0x0106B000` present). What a `Fatal` record does before the logger returns is therefore **not observable
in any image on disk**.

This matters: UE's `Fatal` verbosity normally routes into the crash handler, and this title ships
crashpad (`CLAUDE.md`: *"handing control over to crashpad"*), so "no dump" is the *opposite* of the
default expectation. The `jmp $` and the `[[noreturn]]` shape are CONFIRMED (A10, A11); "**no** dump,
**not** SEH-catchable" is an unmeasured consequence over a dark page.
**Restate as:** *tripping the guard emits a Fatal log record and, if the logger returns, spins forever.*

### U2. "verified instruction boundary: 4,256" as a floor — contaminated; the guarded floor is 4,185

I reproduced 4,256 / 1 FP / 106 unverifiable / 3,292 rows **exactly** with the report's method. But
re-running the identical classification while excluding any hit whose containing row spans an all-zero
page:

```
hits in FULLY-DECRYPTED rows                       : 4185
hits whose row spans an ALL-ZERO page (unreliable) :   72
hits with NO pdata row                             :  106   (all on decrypted pages)
```

So 71 of the 4,256 "verified" and the 1 "false positive" are all decided by disassembling through
undecrypted bytes. **The coverage-clean floor is 4,185, not 4,256.**

Second, independent stress on the same number: re-verifying from **chain heads** (the true function
entry) instead of row starts gives **4,251 verified and 6 rejects** — a *different* set of 5 sites, and
all 6 rejects show the same perfect `cmp / jbe / mov edx / lea rcx / call` idiom on inspection. **The
exact count is method-dependent; only the order of magnitude is safe.** V2's *conclusion* (generic, not
the `PlayersAttached` instantiation) is CONFIRMED and is not weakened by any of this.

### U3. "Coverage discipline: every page reads `present`" — scoped far narrower than it reads

True for the four chain functions. **Not** applied to the 3,292 rows disassembled in §7 (72 hits sit in
rows spanning zero pages — U2/B1), and **not** applied to the fatal-log subtree (U1). As written it reads
as a whole-report guarantee, and the two places it was not applied are exactly where the report's numbers
break.

### U4. "The complete call graph … no UObject, no UFunction, no ProcessEvent, no script VM, no reflection, no GC entry point **anywhere**" [M]

It is a three-level enumeration with **four unexplored leaves**: `0xFAAC80`'s subtree (which reaches the
dark page at `0x010A9B70`), `0xFAAD40`'s subtree (same logger), `0xFF93C0`'s body, and the **indirect**
`GMalloc->Realloc` vtable target, which is a heap object and is in no dump at all. "Complete" and
"anywhere" are transitive-closure words the evidence does not reach.
**The operational conclusion still holds** for the success path — `ResizeGrow → QuantizeSize /
ResizeAllocation → FMemory::Realloc → GMalloc->Realloc` contains no reflection entry point — but the
grade should be [M] for the enumerated path and [I] for the closure.

### U5. "it is `ResizeGrow`" graded [M]

Naming a C++ member from matched arithmetic is an inference; nothing in the image carries the symbol.
[I, strong] is the right grade. The *semantics* (V1's operational content — what it reads, writes and
computes) are [M], and they are what the arm needs. Same for `QuantizeSize` / `ResizeAllocation` /
`FMemory::Realloc`: named from shape plus two shipped fatal strings, which is good evidence but is still
inference.

### U6. Two assertions that are true but were asserted, not shown

- **"the 11 bytes … are inter-function padding, not code … a decoy."** No evidence was given, and the
  bytes are *not* the `cc` / `nop` shape real MSVC padding takes, so it is not self-evident. I supplied
  the missing evidence: **0 rel32 `E8`/`E9` anywhere in `.text` target any of `0x00F98965..0x00F9896F`,
  and 0 stored qwords point at them.** Now CONFIRMED.
- **"`PlayersAttached` is `this+0x130` … derived here from a completely independent direction."** The
  *layout* (base / Num / Max / stride 8) is independent; the **name** is taken from `CLAUDE.md`, so it is
  the same claim, not a second witness. An actual independent witness exists and was not cited:
  `tools/asdump/out/binds_members.csv` lists `ULokiRideableComponent` properties **6 `PlayersInsideCount`,
  7 `TArray<ALokiPlayerState> PlayersInside`, 8 `TArray<ALokiPlayerState> PlayersAttached`** — which, with
  `PlayersInside @ +0x120` and a 16-byte `TArray` header, lands `PlayersAttached` at **`+0x130`**. With
  that added, the identification is CONFIRMED.

---

## D. Minor

- The fatal file string is **`ContainerHelpers.cpp`**, not `ContainersHelpers.cpp` as the report writes
  twice. `0x0768B8E0` reads
  `C:\TheoryCraft\build-staging\Engine\Source\Runtime\Core\Private\Containers\ContainerHelpers.cpp`.
- "puts it in this project's 0/22 hazard bucket alongside every other data poke" — in `CLAUDE.md`'s ladder
  the **0/22** arm is labelled **"nothing"** (no write of any kind). A call that allocates from `GMalloc`
  and mutates a reflected `UPROPERTY` `TArray` that GC and replication traverse is an *analogy* to that
  bucket, not a measurement in it. (The report handles the real consequence correctly by publishing `Num`
  last.)
- "Clobbers … exactly the Win64 volatile set, nothing outside the ABI" is an ABI *assumption* past the
  `GMalloc->Realloc` virtual call, whose target is not in any image.

---

## E. What I could not shake

The lane's deliverable — **V3, "the reallocator is not stripped, and a hand-built direct call is the right
primitive"** — reproduces completely, independently, and by a different route. Signature, layout, element
size, the guard polarity, the dead `OldNum`, the growth arithmetic in both orderings, the `GMalloc`
triple-load, the two virtual slots, the zero-stored-pointers result and the `0x055CD75B` target all
survive re-derivation. The C++ in §9 is correct as written, including the deferred `Num` publish and the
re-read of `Data`. **No load-bearing defect was found in the recommended call.**
