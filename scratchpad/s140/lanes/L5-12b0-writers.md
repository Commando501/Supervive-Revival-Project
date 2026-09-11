# L5 / TASK A3 — COMPLETE WRITER CENSUS FOR `CMC+0x12B0`

**Image:** `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, FLAT (va==praw, all 10 sections — verified).
**Instruments:** `scratchpad/s140/tools/peimg.py` + `cfg.py` (both self-tests PASS), capstone 5.0.7,
plus a purpose-built adjudicator `scratchpad/s140/tools/adjud.py` (pdata-chain resolver + backward
local decode + linear chunk sweep). **All offline. No launch, no injection, no live process.**

---

## 0. HEADLINE

**The field is `ULokiCharacterMovementComponent::TimeSinceFallingStart`, a reflected `float`
UPROPERTY at offset `0x12B0` — [M], read from the UHT property record, not inferred.**

**There are FIVE writers, not three.** The task file's A/B/C are all confirmed; **two more writers
(D and E) and two more readers (R1, R2) were found and were not in the brief.**

| id | write site | bytes | instruction | containing function | what it writes |
|---|---|---|---|---|---|
| **A** | `0x055B8414` | `f30f1186b0120000` | `movss [rsi+0x12b0], xmm0` | `ULokiCMC::PerformMovement` `0x055B8370` (vt slot 341 / disp 0xAA8) | `+= DeltaSeconds` (0 under HitStop) |
| **B** | `0x055C248B` | `f30f1181b0120000` | `movss [rcx+0x12b0], xmm0` | `ULokiCMC::StartNewPhysics` `0x055C2430` (vt slot 228 / disp 0x720) | `+= deltaTime` |
| **C** | `0x055A74D6` | `f30f11b6b0120000` | `movss [rsi+0x12b0], xmm6` | **`FSavedMove_Loki*::CombineWith`** `0x055A7440` (SavedMove vt slot 8) | `= OldMove->[+0x67C]` |
| **D** | `0x055B7CCD` | `89abb0120000` | `mov dword [rbx+0x12b0], ebp` (ebp==0) | **`ULokiCMC::OnMovementModeChanged`** `0x055B7BF0` (vt slot 207 / disp 0x678) | **`= 0.0f`** |
| **E** | `0x055BDD22` | `8986b0120000` | `mov dword [rsi+0x12b0], eax` | **`FSavedMove_Loki*::PrepMoveFor`** `0x055BDCB0` (SavedMove vt slot 9) | `= SavedMove->[+0x67C]` |

Readers (4 sites; A and B are read-modify-write so 2 of these are their own loads):

| id | read site | bytes | instruction | containing function |
|---|---|---|---|---|
| A' | `0x055B840C` | `f30f5886b0120000` | `addss xmm0, [rsi+0x12b0]` | A's RMW load |
| B' | `0x055C2483` | `f30f5881b0120000` | `addss xmm0, [rcx+0x12b0]` | B's RMW load |
| **R1** | `0x055A56F8` | `0f2f83b0120000` | `comiss xmm0, [rbx+0x12b0]` | `0x055A56B0` — a bool predicate on `ALokiCharacter` (a *coyote-time* test) |
| **R2** | `0x055C0A50` | `8b86b0120000` | `mov eax, [rsi+0x12b0]` | **`FSavedMove_Loki*::SetInitialPosition`** `0x055C0970` (SavedMove vt slot 3) — saves it into the move |

---

## 1. METHOD (and why the previous attempt's method is not repeated)

The forbidden method (back-decode from every occurrence of the dword) was **not** used as the
decoder. It was used only as a **candidate LOCATOR**, then every candidate was adjudicated with
capstone operands by two independent decoders.

1. **Candidate locator.** Byte-scan `.text` for `b0 12 00 00`. *Every* x86 instruction whose memory
   operand carries `disp32 == 0x12B0` necessarily contains those four bytes, so this is a strict
   **superset** over decrypted `.text`. Result: **59 candidates image-wide.**
2. **Adjudicator 1 — bounded backward decode.** For each candidate `h`, try every start
   `s` in `[h-15, h)`; accept `s` iff the decoded instruction's byte range covers `[h, h+4)`. Classify
   by **capstone operand** (`X86_OP_MEM.disp == 0x12B0` vs `X86_OP_IMM == 0x12B0`), never by bytes.
3. **Adjudicator 2 — linear sweep from the containing `.pdata` chunk start** (`pdata_union.csv`).
4. **Adjudicator 3 — recursive-descent CFG** from known function entries, for functions
   `pdata_union.csv` cannot see.
5. Function entries resolved by **walking the `UNWIND_INFO` `UNW_FLAG_CHAININFO` chain** back to the
   primary `RUNTIME_FUNCTION` (not by guessing the chunk start).

**Result: 57 of 59 candidates AGREE between adjudicators 1 and 2.** The 2 disagreements are
`0x055C2483` / `0x055C248B` — writer **B** — and the reason is itself a finding (§3).

### 1.1 POSITIVE CONTROL (explicitly requested) — PASSED, but only with all three adjudicators
* **A** found: `0x055B840C` (read) + `0x055B8414` (write). PASS
* **C** found: `0x055A74D6` (write). PASS
* **B** found — **but NOT by the pdata-based sweep.** `func_entry(0x055C2483)` returns `None`:
  **`ULokiCMC::StartNewPhysics 0x055C2430` has no row in `pdata_union.csv` at all.** This is the
  documented "size-1 placeholder dropped BY CONSTRUCTION" blindness, reproduced live here.
  `CFG(im, 0x055C2430)` (123 insns, 0 decode failures) **does** find both sites:
  `addss xmm0,[rcx+0x12b0]` @ `0x055C2483`, `movss [rcx+0x12b0],xmm0` @ `0x055C248B`. PASS
  => **a pdata-anchored census alone would have missed writer B.** Stated as required.

### 1.2 The blind spots this census still has (it is a FLOOR)
* **Dark pages.** An all-zero page contains no `b0 12 00 00`, so a writer in never-executed code is
  invisible. `.text` overall: **13,481 of 30,281 pages dark (44.52 %)**. In the Loki-CMC code band
  `0x55A0000-0x55C6000`: **4 of 38 pages dark (`0x55A2000`, `0x55A3000`, `0x55BA000`, `0x55BB000`)**.
  Of the 413 `ULokiCMC` vtable slots, **15 land on dark pages, but 14 of those are un-overridden
  ENGINE implementations** (which cannot touch `+0x12B0`, see §4). **Exactly one Loki CMC virtual is
  dark and unadjudicated: slot 411, `0x055A2290`** (its engine base is the `true` fold `0x00B9E1F0`,
  so it is a bool query — a writer there is unlikely but NOT excluded).
  The **SavedMove vtable has ZERO slots on dark pages** — that class is fully adjudicated.
  Controls: known-dark `0x5A6AC40` -> `page_nonzero = 0`; known-lit `0x055B8370` -> `3578`.
* **Computed / rebased addressing.** A `lea reg,[cmc+K]` followed by `[reg + (0x12B0-K)]` would
  escape a disp32 scan. **Checked and clean:** decoded **32,559 instructions across 857 `.pdata`
  chunks** in `[0x55A0000, 0x55C6000)` and found **15** `lea` with a non-rip/rsp/rbp base and
  `0x1000 <= disp <= 0x12B0`; for each I looked for a later access at `disp == 0x12B0 - K` through the
  lea's destination register within 14 instructions — **0 hits**. All 15 are argument passing into
  `rcx`/`rdx` (and **6 of the 15 lea instances land on 4 named UPROPERTY offsets** from the §2 table:
  `OnPreTeleportMove@0x1198`, `OnEndGrind@0x1188`, `OnFloatingBehaviorChanged@0x11A8` x3,
  `CurrentGrindSpline@0x1250` — an incidental cross-check).
* **Bulk copies.** A `memcpy`/`rep movs` spanning offset `0x12B0` (object duplication, a component
  template copy) is invisible to any operand-displacement method. Not enumerated. Stated as a floor.
* **rel32 caller scans** used below are floors over 55.5 %-decrypted `.text`.

---

## 2. THE FIELD IS NAMED — [M]

* ASCII literal `TimeSinceFallingStart` occurs **exactly once** image-wide, at `.rdata 0x088F65D8`.
* Exactly **one** qword pointer to it: `.rdata 0x088F2CB0` — a UHT `FGenericPropertyParams` record.
* Exactly **one** pointer to that record: `.rdata 0x088F5AC8`, inside the `PropPointers` array
  `0x088F59E0 ... 0x088F60B8` = **219 property records**.
* Decoded record: `NameUTF8 -> "TimeSinceFallingStart"`, `PropertyFlags = 0x0010000000002000`
  (**CPF_Net (0x20) NOT set => not replicated**), `EPropertyGenFlags = 0x0A` (**Float**),
  `ArrayDim = 1`, **`Offset = 0x12B0`**.

**POSITIVE CONTROLS for the record decoder (five, all passing, three of them predicted BEFORE the
table was read):**
1. `MantleLaunchDelayRemaining` -> `Offset 0x12E8`. I had already disassembled writer A's function
   decrementing `[rsi+0x12E8]` by the same `xmm6` at `0x055B841C-0x055B843D`. PASS
2. `MiniMantleTimeRemaining` -> `Offset 0x1338`. Already seen being tested and zeroed by writer D's
   function at `0x055B7C95` / `0x055B7CB2`. PASS
3. `LastNonWalkingApex` -> `Offset 0x1168`. Already seen written from `UpdatedComponent+0x220` by
   writer D's function at `0x055B7C81` on leaving `MOVE_Walking`. PASS
4. Float records march in exact 4-byte strides (`0x122C,0x1230,0x1234,0x1238,0x123C,0x1240,0x1244,
   0x1248,0x124C`). PASS
5. Every `gen = 0x4C` (Bool) record reads `Offset = 0x0001`, i.e. garbage — exactly the documented
   "`FBoolPropertyParams` carries no ByteOffset" trap. The decoder correctly cannot decode bools,
   which is the expected negative. PASS

Neighbours that matter (same table): `WallJumpCheckTimeRemaining @ 0x162C`,
`CurrentJumpTargetXY @ 0x1678`, `MiniMantleTimeRemaining @ 0x1338`,
`MantleLaunchDelayRemaining @ 0x12E8`, `CurrentForces @ 0x16A0`, `LastAccelerationTime @ 0x16D0`.
**Note for lane A4: `+0x16C8` (the StartNewPhysics latch) is NOT a reflected UPROPERTY** — nothing in
the 219-record table sits at `0x16C8`; it is a private member in the gap between `CurrentForces`
(`0x16A0`, 16-byte TArray) and `LastAccelerationTime` (`0x16D0`).

---

## 3. WRITER-BY-WRITER

### WRITER A — `ULokiCMC::PerformMovement 0x055B8370`, site `0x055B8414`. **UNCONDITIONAL.**
```
0x055b838d  movaps xmm6, xmm1              ; xmm6 = DeltaSeconds (the float parameter)
0x055b83b5  call 0x56e7c10                 ; toggle 0x78 = 120 (HitStop), edx=0
0x055b83fa  xorps  xmm6, xmm6              ; ONLY on the HitStop-true chain
0x055b8403  call qword [rax+0xab0]         ; vt slot 342 (Loki-only; engine base is the F7EC20 fold)
0x055b8409  movaps xmm0, xmm6
0x055b840c  addss  xmm0, dword [rsi+0x12b0]
0x055b8414  movss  dword [rsi+0x12b0], xmm0
```
* **[M] The accumulate is unconditional on entry.** `CFG(0x055B8370)` = 322 insns / 29 calls /
  0 indirect jumps / 0 decode failures / 0 noreturn candidates.
  `reach_backward(0x055B840C)` = **44 instructions and CONTAINS the entry `0x055B8370`**;
  `exits_from(0x055B840C)` returns **exactly one edge, `0x055B840C -> 0x055B8414`**, which is the
  known "target included as a source" artifact. **There is no real exit** => every entry to
  `ULokiCMC::PerformMovement` reaches the accumulate. The branches at `0x055B83BF/83D4/83E0/83F8`
  only decide whether `xmm6` is zeroed, not whether the store happens.
* **[M] It is UPSTREAM of the Super.** The Super call is `0x055B85C1 = e8 fa 18 03 fe` ->
  **`0x035E9EC0`** (machine-recomputed; reproduces the session lead's item 1) and
  **`0x055B85C1` is NOT in `reach_backward(0x055B840C)`**.
* Contribution per call: `TimeSinceFallingStart += DeltaSeconds` (or `+= 0` under HitStop).

### WRITER B — `ULokiCMC::StartNewPhysics 0x055C2430`, site `0x055C248B`. **DOUBLY GUARDED.**
```
0x055c2433  test r8d, r8d                  ; Iterations
0x055c2436  jne  0x55c2475
0x055c2469  mov  byte [rcx+0x16c8], 1      ; THE LATCH -- Iterations==0 path only
0x055c2470  jmp  0x3600990                 ; tail-jump to engine StartNewPhysics
0x055c2475  jle  0x55c2493                 ; flags from `test r8d,r8d` => taken iff Iterations < 0
0x055c2477  cmp  byte [rcx+0x231], 3       ; MovementMode == MOVE_Falling
0x055c247e  jne  0x55c2493
0x055c2483  addss xmm0, dword [rcx+0x12b0] ; xmm2/xmm0 = deltaTime
0x055c248b  movss dword [rcx+0x12b0], xmm0
```
**[M] `if (Iterations > 0 && MovementMode == MOVE_Falling) TimeSinceFallingStart += deltaTime;`**
(`jle` after `test` is taken iff `ZF||SF`; `ZF=0` is already established by the `jne`, so the arm
runs only for strictly positive `Iterations`.) `Iterations > 0` means a **re-entrant** call — i.e.
`StartNewPhysics` was already entered once with `Iterations == 0`, which is the path that sets the
latch. Writer B is on a **sub-step** path only.

### WRITER C — `FSavedMove_Loki*::CombineWith 0x055A7440`, site `0x055A74D6`. **NETWORK ONLY.**
* Extent `0x055A7440 ... 0x055A75A4` (356 B, 3 chained `.pdata` rows, all chaining back to primary
  `(0x055A7440, 0x055A747B, unwind 0x0948702C)`). REAL (page nonzero 3710), not a fold, not dark.
* Signature from the code: `(rcx = this newMove, rdx = OldMove, r8 = InCharacter, r9 = PC,
  [rsp+0x80] = &OldStartLocation)` — **five arguments, all forwarded unchanged to
  `call 0x035DB4A0` (the Super) as the first instruction.**
* **[M] The Super `0x035DB4A0` IS `FSavedMove_Character::CombineWith`.** Its body reads
  `mov rsi,[r8+0x458]` (`InCharacter->CharacterMovement`), calls
  `SetWorldLocationAndRotation` through `[rsi+0xD0]` (UpdatedComponent), writes
  **`movups [rsi+0xE8], xmm0` from `[OldMove+0x70]`** = `CharMovement->Velocity = OldMove->StartVelocity`
  (**`CMC+0xE8` is the independently banked live `Velocity` offset — positive control**), then
  `[rsi+0xF8]` (Velocity.Z, LWC doubles), `SetBase` via a vtable call, then `lea rcx,[rsi+0x438]`
  (`CurrentFloor`). That is `FSavedMove_Character::CombineWith` line for line.
* **`xmm6` at the write site = `[rdi + 0x67C]` = the OLD MOVE's saved copy of `TimeSinceFallingStart`.**
  It is a **RESTORE**, not an accumulate.
* Full restore set performed by C: `CMC[0x162C] <- SM[0x678]`, **`CMC[0x12B0] <- SM[0x67C]`**,
  `CMC[0x1678] <- SM[0x680]`, `CMC[0x1630] <- SM[0x688]` (16 B), `CMC[0x1640] <- SM[0x698]` (16 B),
  `Char[0x16C8] <- SM[0x6A8]`, `Char[0x16D8] <- SM[0x6B8]`, `Char[0x16E8] <- SM[0x6C8]`,
  `Char[0x16EC] <- SM[0x6CC]`, then `call 0x2D9CBB0(&Char[0x16F0], &SM[0x6D0])`.
* Each field is fetched as `Cast<ULokiCMC>(Character->[0x458])` **guarded by `call 0x554A1A0`** — see
  §4 for why that call is the decisive type proof.

### WRITER D — `ULokiCMC::OnMovementModeChanged 0x055B7BF0`, site `0x055B7CCD`. **NEW. IT ZEROES.**
```
0x055b7c93  xor  ebp, ebp                       ; ebp = 0 for the rest of the function
0x055b7cb2  mov  dword [rbx+0x1338], ebp        ; MiniMantleTimeRemaining = 0
0x055b7cb8  cmp  byte [rbx+0x231], 3            ; MovementMode == MOVE_Falling ?
0x055b7cbf  jne  0x55b7cd5
0x055b7cc1  or   byte [rbx+0x54d], 8
0x055b7cc8  cmp  edi, 6                         ; PreviousMovementMode == MOVE_Dashing (this build!)
0x055b7ccb  je   0x55b7ce9                      ; ... then SKIP the reset
0x055b7ccd  mov  dword [rbx+0x12b0], ebp        ; *** TimeSinceFallingStart = 0.0f ***
0x055b7cd3  jmp  0x55b7ce9
0x055b7cd5  mov  dword [rbx+0x162c], 0xbf800000 ; WallJumpCheckTimeRemaining = -1.0f
0x055b7cdf  mov  dword [rbx+0x1678], 0xbf800000 ; CurrentJumpTargetXY       = -1.0f
```
**[M] `TimeSinceFallingStart` is reset to 0 on every transition INTO `MOVE_Falling`, except when the
previous mode was `MOVE_Dashing` (6)** — which in this build is the inserted custom mode. `ebp == 0`
is established by `xor ebp,ebp` at `0x055B7C93` with no intervening write on the path.

**[M] The containing function is `OnMovementModeChanged`** — vtable slot **207** (disp `0x678`) of
`ULokiCharacterMovementComponent`, whose engine base is **`0x035E9240`**. Three positive controls on
the engine base:
1. Its **first** action is `call qword [rax+0x6B8]` and it bails on false — `disp 0x6B8` is
   **`HasValidData`**, named independently in the shared brief. That is UE's literal
   `if (!HasValidData()) return;` first line.
2. Under `MovementMode == MOVE_NavWalking (2)` it does `mov qword [rdi+0xF8], 0` = `Velocity.Z = 0.f`
   (Velocity at `+0xE8`, banked live) and `mov [rdi+0x542], al` = `GroundMovementMode = MovementMode`.
3. Under `MovementMode == MOVE_Walking (1)` it sets `or byte [rdi+0x54D], 0x40` =
   `bCrouchMaintainsBaseLocation`, exactly UE's else-branch structure.

### WRITER E — `FSavedMove_Loki*::PrepMoveFor 0x055BDCB0`, site `0x055BDD22`. **NETWORK ONLY.**
* `(rcx = this SavedMove, rdx = Character)`. First act: `call 0x035F1DF0` (Super), then
  `Character->Controller (+0x400)` -> `call [vt+0x808]` with `lea rdx,[SavedMove+0x1A8]`
  (`PC->SetControlRotation(SavedControlRotation)`).
* Restores the **same field set as C**, by integer `mov` instead of `movss`:
  `CMC[0x162C] <- SM[0x678]`, **`CMC[0x12B0] <- SM[0x67C]`**, `CMC[0x1678] <- SM[0x680]`,
  `CMC[0x1630] <- SM[0x688]`, `CMC[0x1640] <- SM[0x698]`, then a guarded Character block.
* UE's own comment for this virtual is *"Called before `ClientUpdatePosition` uses this SavedMove to
  make a predictive correction"* — i.e. the **server-correction replay path**.

### READER R2 — `FSavedMove_Loki*::SetInitialPosition 0x055C0970`, site `0x055C0A50`.
The **save** direction: `SM[0x678] <- CMC[0x162C]`, **`SM[0x67C] <- CMC[0x12B0]`**,
`SM[0x680] <- CMC[0x1678]`, `SM[0x688] <- CMC[0x1630]`, `SM[0x698] <- CMC[0x1640]`, plus
`SM[0x6A8/0x6B8/0x6C8/0x6CC] <- Char[0x16C8/0x16D8/0x16E8/0x16EC]` and compressed-flag bits in
`SM[0x18]`. This is the counterpart that fills the `+0x67C` slot C and E read back.

### READER R1 — `0x055A56B0` (non-virtual, on `ALokiCharacter`). **The only gameplay consumer.**
```
rbx = Cast<ULokiCMC>(Character->[0x458])
if (!CMC->vt[0x728]())            return false;   ; slot 229 -> forwards to slot 193 (falling query)
if (Character->[0x598] != 0)      return false;
if (Character->[0x1830] > CMC->TimeSinceFallingStart)   ; 0x055A56F8 comiss
      if (CMC->vt[0x740]())       return true;   ; slot 232 (a "can move on ground"-family query)
return false;
```
A **coyote-time / grace-window** predicate: *"have I been falling for less than `Character[0x1830]`
seconds?"*. rel32 caller scan (a **FLOOR**): 2 call sites, `0x055A5CA8` (in `0x055A5BA0`) and
`0x055A65B0` (in `0x055A63C0`); both containing functions appear in three `ALokiCharacter`-family
vtables (`0x088E6610` / `0x089A7708` / `0x089F94B8`) — [I] a base + two derived classes.

---

## 4. IS THERE ANY WRITER OUTSIDE THE LOKI CMC CLASS? — NO, AND THE ARGUMENT IS STRUCTURAL

Exact partition of the 59 candidates (sums to 59 — checked):
**40** are stack/frame accesses (`[rsp+0x12B0]` / `[rbp+0x12B0]`), **2** are the *immediate* `0x12B0`
(`mov dword [rsp+0x34], 0x12b0` at `0x03D4A0DB` and `0x03D6033B`), **1** is a byte coincidence inside
a `call rel32` (`0x0715E1BB call 0x715F470`), **9** are the Loki sites above (A and B each contribute
a read and a write), and the remaining **7** belong to **other classes** and are excluded by operand
width / neighbour layout:

| site | instruction | why excluded |
|---|---|---|
| `0x020B133F` | `movups xmm0, [rdx+0x12b0]` | 16-byte read |
| `0x03A426E4` | `mov [rbx+0x12b0], esi` | inside an alternating 4/8-byte run at `0x12A0/0x12A8/0x12B0/0x12B8/0x12C0` |
| `0x03A59298` | `mov byte [rdi+r8+0x12b0], r12b` | byte, index-scaled => array |
| `0x03D431D3` / `0x03D43206` | `movss [rbx+0x12b0], xmm5` / `mov qword [rbx+0x12b0], r12` | **same function `0x03D42B90`, mutually exclusive branches**, writing a contiguous float block `0x1280/0x1290/0x12A0/0x12B0/0x12B4/0x12B8/0x12BC` — incompatible with the CMC layout |
| `0x04AF3368` / `0x04B03574` | qword write / qword read at `[rdi+0x12b0]` | 8-byte |

**The decisive structural fact — [M]:**
* `sizeof(ULokiCharacterMovementComponent)` = **`0x19D0`**, read from its class-registration
  function `0x05309300` (`mov dword [rsp+0x20], 0x19d0`), which leas the wide literals
  `LokiCharacterMovementComponent` (`.rdata 0x088F23F2`) and `/Script/Loki`.
* `sizeof(UCharacterMovementComponent)` = **`0x1130`**, read the same way from `0x035CAF50`
  (`mov dword [rsp+0x20], 0x1130`), leas `CharacterMovementComponent` + `/Script/Engine`.
* **`0x12B0 > 0x1130`** => `TimeSinceFallingStart` is entirely inside the **Loki-added** region.
  The engine base class cannot reference it, and indeed **no `disp 0x12B0` access exists anywhere in
  the engine CharacterMovementComponent code band `0x35C0000-0x3660000`** (0 of 59 candidates).

**Type proof for C / E / R1 / R2 — [M]:** every one of them fetches the object as
`Cast<ULokiCMC>(Character->[0x458])`, guarded by **`call 0x554A1A0`**. That helper's class getter is
`0x05309300`, i.e. **it is literally `IsA<ULokiCharacterMovementComponent>`**. The Character is
likewise guarded by `call 0x054F8C40`, whose getter `0x052F01E0` names **`LokiCharacter`** in
`/Script/Loki` with `sizeof 0x1950` — which matches this repo's independently recorded
`sizeof(ALokiCharacter) = 0x1950`. Two size cross-checks, both passing.

**Class identity of C / E / R2 — [M] structural:** all three sit in ONE vtable,
`.rdata 0x08B17EE8 ... 0x08B17F9F` (23 slots, mixed Loki `0x55xxxxx` overrides and engine
`0x35xxxxx` inherited entries, terminating in two `0x00F7EC20` folds). Slot order against UE's
declared `FSavedMove_Character` virtual order:

| slot | fn | UE name | evidence |
|---|---|---|---|
| 0 | `0x055A0720` | dtor | |
| 1 | `0x035D8790` | `Clear` | inherited |
| 2 | `0x035FAA90` | `SetMoveFor` | inherited |
| **3** | **`0x055C0970`** | **`SetInitialPosition`** | 2 args, saves start state — **R2** |
| 4 | `0x035E6870` | `PostUpdate` | inherited |
| 5 | `0x035E4940` | `IsImportantMove` | inherited |
| 6 | `0x055BDC00` | `GetRevertedLocation` | |
| 7 | `0x055A5540` | `CanCombineWith` | |
| **8** | **`0x055A7440`** | **`CombineWith`** | 5 args + Super body — **C** |
| **9** | **`0x055BDCB0`** | **`PrepMoveFor`** | 2 args + `SetControlRotation` — **E** |
| 10 | `0x055AA5C0` | `GetCompressedFlags` | |

The slot order and the two independently-derived body identifications (C from its Super's
`CombineWith` body; E from `PC->SetControlRotation`) **agree**. Three routes, one answer.
⚠ Caveat on the slot->name mapping: it assumes stock UE 5.x declaration order for
`FSavedMove_Character`. This is a fork (`C:\TheoryCraft\build-staging\Engine\...` paths appear in the
symbol index), so the order could in principle have been edited. That risk is what the two
independent body identifications retire; only slot 3 (`SetInitialPosition`) rests on the order plus
its save-direction body, hence [M, strong] rather than [M].

---

## 5. REACHABILITY ON *THIS* CLIENT

**[M] from the bytes** — engine `ControlledCharacterMove 0x035DCD10`:
```
0x035dcd6b  movups [rsi+0x328], xmm0        ; Acceleration = ScaleInputAcceleration(...)
0x035dcd8f  movss  [rsi+0x3d0], xmm0        ; AnalogInputModifier
0x035dcd97  movzx  ecx, byte [rax+0x160]    ; CharacterOwner->Role
0x035dcd9e  cmp    cl, 3
0x035dcda1  jne    0x35dcdb4
0x035dcdac  call   qword [rax+0xaa8]        ; -> PerformMovement          (Role == ROLE_Authority)
0x035dcdb4  cmp    cl, 2                    ; ROLE_AutonomousProxy
0x035dcdbc  call   0x35b1da0                ; GetNetMode()
0x035dcdc1  cmp    eax, 3                   ; == NM_Client
0x035dcdd6  call   qword [rax+0xb08]        ; -> ReplicateMoveToServer (vt slot 353, Loki 0x055BE9C0)
```
**Banked live measurements: `Role == 3`, and the client is `NM_Standalone`.** => the
`ReplicateMoveToServer` arm is unreachable. The `FSavedMove` objects are allocated only by
`FNetworkPredictionData_Client_Character`, reached only from `ReplicateMoveToServer` /
`ClientUpdatePosition` (an RPC-driven path, and there is no NetDriver).

=> **[I, strong] writers C and E and reader R2 CANNOT run on this client.** Grade is [I] not [M]
because I did not exhaustively enumerate every possible caller of the SavedMove vtable slots
(virtual dispatch, so no rel32 caller scan is possible). The inference rests on [M] bytes for the
gate + [M banked] Role/NetMode + UE's structural fact that SavedMoves exist only in
`ClientPredictionData`.

=> **[I, strong] writer B cannot have run**: the latch `CMC+0x16C8` is measured **0** on both pawns
and on all 37 CMCs, and the latch is written on the `Iterations == 0` path, which is the only way
into the `Iterations > 0` re-entrant calls (those originate from the `Phys*` handlers dispatched by
`StartNewPhysics` itself). Residual: an unenumerated external caller passing `Iterations > 0`.

=> **[M] writer D CAN run**, but it writes **0**, and only at a mode transition into `MOVE_Falling`.
Both pawns are already `MOVE_Falling` and stationary, so it is quiescent.

=> **[M] writer A runs every frame** on this route (`ControlledCharacterMove` provably ran — S139
flight 3's signed-zero `Acceleration`; `Role == 3` => `PerformMovement` is called; the accumulate is
unconditional inside it).

---

## 6. THE DELIVERABLE — WHAT AN ADVANCING `+0x12B0` PROVES, AND WHAT IT DOES NOT

An advancing `CMC+0x12B0` proves **exactly one thing: that `ULokiCharacterMovementComponent::
PerformMovement (0x055B8370)` was ENTERED, repeatedly, with a non-zero `DeltaSeconds` and without
the HitStop toggle firing.** The store is at instruction 44 of that function, on a path with **no
exits** from the entry, and **strictly upstream of the Super call at `0x055B85C1` -> engine
`PerformMovement 0x035E9EC0`**. It therefore says **nothing whatsoever** about: whether the Super was
reached; whether the engine `PerformMovement` got past any of its own gates; whether
`StartNewPhysics` ran; whether `Phys*` ran; whether the pawn is simulating. S139's retraction was
correct and this census makes it exact. It additionally proves, weakly, that the component was NOT
in a mode-transition into `MOVE_Falling` during the sample (writer D would have zeroed it) and that
no network correction landed (C/E would have overwritten it with an old value).

**Which writers are consistent with the S139 observation (bot 33.14 -> 43.34 over 10.2 s = 1.000x;
player 380 -> 390 = 1.000x):**
* **A — fully consistent, and it is the only one that is.** It adds exactly `DeltaSeconds` once per
  `PerformMovement` call; summed over a second that is exactly 1.0 s. A rate of **exactly** 1.0x
  wall clock is A's signature and nothing else's.
* **B — inconsistent, twice over.** It only fires on re-entrant (`Iterations > 0`) calls, whose
  `deltaTime` is a *remainder* of the frame, so B alone gives **< 1.0x**, and A+B together gives
  **> 1.0x**. Independently, the latch `+0x16C8` reads 0 on every CMC in the world, so
  `StartNewPhysics` was never entered at all.
* **C and E — inconsistent in shape.** They *assign* a previously saved value, which would show as
  step discontinuities/plateaus, not a smooth monotone ramp over 10.2 s. They are also unreachable
  (§5).
* **D — inconsistent in sign.** It writes 0.

**Can they be distinguished offline, or only live?** They already have been, and no new live read is
required:
* **A vs B is settled by data already banked** — the latch `+0x16C8 == 0` (B unreachable) plus the
  rate being exactly 1.000x (B would perturb it). The offline half of that argument is §3's proof
  that the latch sits on the `Iterations == 0` path and B on the `Iterations > 0` path.
* **A vs {C, E} is settled offline** by shape (accumulate vs assign) and by §5's reachability.
* **A vs D is settled offline** by sign.

The only thing offline reasoning cannot fully close is the residual floor of §1.2: a writer on the
one dark Loki CMC virtual `0x055A2290` (slot 411), on the 4 dark pages of the band, or through a
bulk `memcpy`. **The single live read that would close it outright** is a **write-and-watch**: poke
`CMC+0x12B0` to a distinctive value (e.g. `-12345.0f`) with an external `WriteProcessMemory`, then
sample it; if it resumes monotone accumulation from `-12345.0 + n*dt` at exactly 1.0x while
`+0x16C8` stays 0, writer A is confirmed as the sole active writer and every other candidate is
excluded in one shot. (That is a one-dword write and would need the usual A-B-A discipline; it is
**not** something this offline lane performed or is recommending as free.)

---

## 7. GRADED CLAIM LIST

| # | claim | grade | control |
|---|---|---|---|
| 1 | `CMC+0x12B0` is `ULokiCharacterMovementComponent::TimeSinceFallingStart`, reflected `float`, ArrayDim 1, **not** `CPF_Net` | **[M]** | UHT record `0x088F2CB0`; decoder validated by 5 independent offset predictions (§2) |
| 2 | Exactly **5** disp32 writers exist in decrypted `.text` (A,B,C,D,E) and **4** readers | **[M]**, and a **FLOOR** (§1.2) | 59-candidate superset scan; 57/59 two-instrument agreement; A+B+C all found (B only by CFG) |
| 3 | Writer A's accumulate is **unconditional** and **upstream of the Super** | **[M]** | `exits_from(0x055B840C)` = 0 real exits, `|R| = 44`, entry in R, `0x055B85C1` not in R; Super rel32 machine-recomputed to `0x035E9EC0` |
| 4 | Writer B fires only when `Iterations > 0 && MovementMode == MOVE_Falling` | **[M]** | disassembly; `jle` polarity derived from `test r8d,r8d` flags |
| 5 | Writer C is `FSavedMove_Character::CombineWith` (Loki override), entry `0x055A7440` | **[M, strong]** | unwind chain to primary row; Super `0x035DB4A0` body = `Velocity <- OldMove->StartVelocity` at the banked `CMC+0xE8`; SavedMove vtable **slot 8** |
| 6 | Writer C's `xmm6` = `OldMove[+0x67C]` = the saved copy of the same field | **[M]** | disassembly `movss xmm6,[rdi+0x67c]` at `0x055A74BB` |
| 7 | Writer D is `ULokiCMC::OnMovementModeChanged` and writes **0.0f** on entering `MOVE_Falling` (unless previous mode was 6/Dashing) | **[M]** | vtable slot 207; engine base `0x035E9240` opens with `HasValidData` (disp 0x6B8) and does `Velocity.Z=0` under NavWalking; `ebp==0` from `xor ebp,ebp` |
| 8 | Writer E is `FSavedMove_Character::PrepMoveFor` (Loki override) | **[M, strong]** | SavedMove vtable **slot 9**; `PC->SetControlRotation` at `[Controller vt+0x808]`; restores the same 5-field set as C |
| 9 | R2 is `SetInitialPosition` (the save direction) | **[M, strong]** | SavedMove vtable slot 3; save-direction field moves |
| 10 | No writer exists outside the Loki CMC / Loki SavedMove code | **[M]** over decrypted `.text`, **FLOOR** over dark | `sizeof(UCMC)=0x1130 < 0x12B0 < sizeof(ULokiCMC)=0x19D0`; 0 engine-band candidates; all four cast sites guarded by `IsA<ULokiCMC>` (`0x554A1A0`) |
| 11 | No rebased (`lea`-based) access to `+0x12B0` in the Loki CMC band | **[M]** | 32,559 insns / 857 chunks decoded; 15 lea candidates, 0 follow-up hits |
| 12 | C, E, R2 are unreachable on this client | **[I, strong]** | `ControlledCharacterMove` Role/NetMode gate [M from bytes] + Role 3 / NM_Standalone [M banked]. Not [M]: virtual dispatch defeats a caller enumeration |
| 13 | B has not run | **[I, strong]** | latch `+0x16C8 == 0` [M banked] + latch-on-`Iterations==0` [M offline] |
| 14 | The observed 1.0x advance is writer A | **[I, strong]** | elimination of B (rate + latch), C/E (shape + reachability), D (sign) |
| 15 | `+0x16C8` (the StartNewPhysics latch) is **not** a reflected UPROPERTY | **[M]** | absent from the 219-record `ULokiCMC` PropPointers table; gap between `CurrentForces@0x16A0` and `LastAccelerationTime@0x16D0` |
| 16 | `ULokiCMC::StartNewPhysics 0x055C2430` has **no** `pdata_union.csv` row | **[M]** | `func_entry(0x055C2483)` -> `None`; the documented size-1-placeholder blindness, reproduced |

## 8. COULD NOT ESTABLISH OFFLINE
* Whether anything writes `+0x12B0` from the **4 dark pages** of the Loki CMC band or from the single
  dark Loki CMC virtual **slot 411 = `0x055A2290`**. (A dark page is all-zero and invisible to any
  byte- or operand-based census.)
* Whether any **bulk copy** (`memcpy` / `rep movs` / component template duplication) spans `+0x12B0`.
* The exact UE names of `ULokiCMC` vtable slots 229 (`0x055B1380`, disp 0x728) and 232
  (`0x055A5120`, disp 0x740) that gate reader R1 — both are falling/ground-state bool queries [I].
* Whether writer D's 4th argument (`r9`, saved/restored around `call 0x55C2190`) is a genuine extra
  Loki parameter or dead forwarding.

## 8b. FOLD / REAL / DARK GRADE FOR EVERY FUNCTION NAMED ABOVE — [M]

| function | rva | page_nonzero | insns (CFG) | grade |
|---|---|---|---|---|
| A `ULokiCMC::PerformMovement` | `0x055B8370` | 3578 | 322 | **REAL** |
| B `ULokiCMC::StartNewPhysics` | `0x055C2430` | 3626 | 123 | **REAL** |
| C `FSavedMove_Loki*::CombineWith` | `0x055A7440` | 3710 | 77 | **REAL** |
| D `ULokiCMC::OnMovementModeChanged` | `0x055B7BF0` | 3674 | 91 | **REAL** |
| E `FSavedMove_Loki*::PrepMoveFor` | `0x055BDCB0` | 3721 | 49 | **REAL** |
| R1 coyote-time predicate | `0x055A56B0` | 3699 | 37 | **REAL** |
| R2 `FSavedMove_Loki*::SetInitialPosition` | `0x055C0970` | 3558 | 69 | **REAL** |
| C's Super `FSavedMove_Character::CombineWith` | `0x035DB4A0` | 3592 | 129 | **REAL** |
| E's Super | `0x035F1DF0` | 3556 | 184 | **REAL** |
| R2's Super | `0x035FA610` | 3646 | 233 | **REAL** |
| D's engine base `UCMC::OnMovementModeChanged` | `0x035E9240` | — | 264 | **REAL** |
| **DARK control** `ULokiRespawnComponent::Respawn` | `0x05A6AC40` | **0** | — | **DARK** (control passes) |

None matches any of the five fold addresses, and none matches the sixth stub shape
(`sub rsp,0x28; call <GetWorld>; xor eax,eax; ret`) — all carry real MSVC prologues and >=37
instructions.

## 9. ARTEFACTS
* `scratchpad/s140/tools/adjud.py` — pdata-chain resolver + adjudicators (read-only, re-runnable).
* `scratchpad/s140/tools/cand.txt` — the 59 raw candidate offsets.
* `scratchpad/s140/tools/lokicmc_props.txt` — all 219 decoded `ULokiCharacterMovementComponent`
  property records (offset, name, gen, flags), sorted by offset.
