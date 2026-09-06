# LANE L4 — `ULokiCMC::PerformMovement 0x055B8370`: progress ladder, and does it really reach its Super?

Image: `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, FLAT (`va == praw` for all 10 sections,
re-verified this session). Offline only: no launch, no injection, no live process touched.
Instruments: shared `scratchpad/s140/tools/peimg.py` + `cfg.py` (self-test **PASS**), plus my own
UHT-record decoder and two sweeps described below.

**Headline:** the Super call is unconditional — confirmed independently and much more strongly than
S139 stated. The two branches S139 flagged as "next to read live" **do not gate it, and reading them
answers nothing.** And a by-product answers lane A4's open question and, if it holds up,
**invalidates the evidence behind S139's "`StartNewPhysics` has never run"** — see §5.

---

## 0. Instrument controls (all run this session, results stated)

| control | expected | got |
|---|---|---|
| `cfg.py` self-test (fold 2-insn / HasValidData rets / exact backward-reach / dark ctrl zero) | PASS | **PASS** |
| `peimg.py` FLAT check | True | **True** |
| DARK control `0x5A6AC40` page non-zero | 0/4096 | **0/4096** |
| page `0x055B8000` (target fn) | lit | **3578/4096** |
| ULokiCMC vtable `.rdata 0x088F8570` — 8 known disps re-read from merged13 | brief's addresses | **8/8 exact** (`0x3D0→0x55C2B90`, `0xAA8→0x55B8370`, `0x720→0x55C2430`, `0x890→0x55A7680`, `0xA38→0x55A75B0`, `0x830→0x55B89F0`, `0x6B8→0x35E64C0`, `0x4E0→0x364BA80`) |
| UHT bool-record decoder positive control | CLAUDE.md S136: `bWantsPlayerState` SetBitFunc `0x45CFA10 = or dword [rcx+0x488],0x20; ret` | **exact match**, and its recorded adjacent-bit control `0x45CFA20` → `…,0x40` also matches |
| store detector must find the capstone-blind `movups` | `0x055B8856` found | **found** |
| store detector must reject loads | `0x055B841C`, `0x055B840C`, `0x055B8424` | **all correctly excluded** |

**Every rel32 in this document was recomputed with a machine.** Sample:
`0x055B85C1 = e8 fa 18 03 fe`, disp `-33351430` → **`0x035E9EC0`** (reproduces the session lead's item 1).

### ⚠ INSTRUMENT DEFECT FOUND — affects any S140 lane hunting stores
**capstone 5.0.7 reports the store form of `movups`/`movaps` with operand-0 access = READ (1), not
WRITE (2).** Raw evidence:

```
0x55b8856 movups xmmword ptr [rsi + 0x12f0], xmm2 -> op0 type=MEM access=1 (READ)
0x55b885d movsd  qword  ptr [rsi + 0x1300], xmm0  -> op0 type=MEM access=2 (WRITE)
0x55c244f movups xmmword ptr [rcx + 0x16b0], xmm0 -> op0 type=MEM access=1 (READ)
```
Any lane filtering on `op.access & CS_AC_WRITE` is **blind to `movups`/`movaps` stores** — including
`StartNewPhysics`'s own 16-byte velocity-snapshot store at `0x055C244F` and the 24-byte FVector store
at `0x055B8856`. Fix used here: fall back to "operand 0 is MEM and mnemonic starts with `mov` with 2
operands", plus an RMW list. Controls above.

### ⚠ SECOND INSTRUMENT DEFECT — I built a bad scan, caught it, and discarded it
A raw-byte scan for the 4-byte little-endian displacement followed by back-decoding **desynced**,
exactly as BRIEF trap #3 predicts. From *inside its own output*: it emitted
`0x055B88CF adc dword ptr [rsi+0x16d0], eax` where the real instruction is
`0x055B88CD movss dword ptr [rsi+0x16d0], xmm0`, and `0x055C2442 mov byte [rcx+0x16c8], al` where the
real one is `0x055C2441 … , r8b`. It **also produced false negatives** (missed `0x0530AB4C` entirely,
because my acceptance test `insn_end == disp_off+4` is wrong for any instruction with a trailing
immediate). **That scan's output is discarded and is not used anywhere below.** It is replaced by two
sound CFG-rooted sweeps (§5.3).

---

## 1. PART 1 — IS THE SUPER CALL UNCONDITIONAL? **YES. [M]**

### 1.1 The CFG is byte-complete — the strongest control available offline
`CFG(im, 0x055B8370)`: **322 instructions, 29 calls, 0 indirect jumps, 0 decode failures,
0 noreturn candidates.**

`.pdata` (`tools/strxref/index/pdata_union.csv`) gives a contiguous chain of 8 rows for this function:

```
0x055B8370–0x055B8379 | 0x055B8379–0x055B847A | 0x055B847A–0x055B85B4 | 0x055B85B4–0x055B85D5
0x055B85D5–0x055B86F5 | 0x055B86F5–0x055B876F | 0x055B876F–0x055B888B | 0x055B888B–0x055B88DE
```
⇒ extent `0x055B8370 .. 0x055B88DE`, **1390 bytes**. Next unrelated row begins `0x055B88E0`.

Byte-coverage audit of my CFG against that extent:

```
bytes covered by CFG: 1390 / 1390
overlaps (byte decoded twice): 0
GAPS (undecoded byte runs): (none)
```

**Zero gaps, zero overlaps, exact extent match.** There is no unreached island and no misaligned
decode. **[M]** This is far stronger than "the CFG found 322 instructions".

### 1.2 Backward reachability — the sound exit set
```
total insns forward-reachable from entry : 322
|R| = insns that CAN reach 0x055B85C1    : 142
|F - R|                                   : 180
entry (0x055B8370) in R                   : True

exits_from(0x055B85C1):
    0x055b85c1  call 0x35e9ec0 -> 0x55b85c6     <-- the TARGET'S OWN FALLTHROUGH (artifact)
```
**Exactly one edge, and it is the artifact.** No edge leaves `R` anywhere else, so all 180 nodes of
`F\R` are downstream of the call.

Additionally: **the function contains exactly ONE `ret`, at `0x055B88DD`, and it is NOT in `R`.**
`rets in R: []`. There is no early-return path.

⇒ **[M] Every path from `0x055B8370` reaches `0x055B85C1`. The Super call is unconditional.**
Derived by backward reachability, not a forward-address predicate, so it is not blind to backward
bails (brief trap #2).

### 1.3 The residual floor, stated honestly
The only way the Super could still not be reached is if a call inside `R` never returns. There are 17
calls in `R`, four of them indirect: `[rax+0x10]` (`0x055B83CB`), `[rax+0x18]` (`0x055B83F3`),
`[rax+0xAB0]` (`0x055B8403`), `[r9+0x270]` (`0x055B854C`, = `UObject::ProcessEvent`, slot 78).

Two facts bound this to near-zero:
1. The banked live measurement "`CMC+0x12B0` advances at 1.0× real time" is a store at **`0x055B8414`**,
   downstream of all three early indirect calls. So in the live process everything up to `0x055B8403`
   provably returns. **[M, from banked live data + this disassembly]**
2. On the path taken when **either** branch in §1.4 fires there are **ZERO calls at all** between
   `0x055B8414` and `0x055B85C1`. Path: `0x055B8414 → 0x055B841C..0x055B8438 → 0x055B8442 →
   0x055B845E → 0x055B85B4 → 0x055B85B7 → 0x055B85BE → 0x055B85C1`.

⇒ **On the live bot, the step from "the `+0x12B0` store executed" to "the Super call executed" is
call-free and branch-free.**

### 1.4 THE TWO BRANCHES S139 FLAGGED **DO NOT GATE THE SUPER CALL** [M]

```
0x055b8442  48 8b 86 98 01 00 00        mov  rax, [rsi + 0x198]        ; rsi = this ; +0x198 = CharacterOwner
0x055b8449/51/59                        (three stack saves: rbp, rdi, r14 — rax untouched)
0x055b845e  f6 80 80 05 00 00 08        test byte [rax + 0x580], 8
0x055b8465  0f 85 49 01 00 00           jne  0x55b85b4                 ; ---> the SUPER CALL'S OWN BLOCK
0x055b846b  8b ae 88 19 00 00           mov  ebp, [rsi + 0x1988]
0x055b8471  83 ed 01                    sub  ebp, 1
0x055b8474  0f 88 3a 01 00 00           js   0x55b85b4                 ; ---> the SUPER CALL'S OWN BLOCK
...
0x055b85b4  0f 28 ce                    movaps xmm1, xmm6
0x055b85b7  c6 86 08 13 00 00 00        mov  byte [rsi + 0x1308], 0
0x055b85be  48 8b ce                    mov  rcx, rsi
0x055b85c1  e8 fa 18 03 fe              call 0x35e9ec0                 ; SUPER
```

Machine-computed graph facts:
```
pred(0x055B85C1) = {0x55b85be}
pred(0x055B85B4) = {0x55b8465, 0x55b8474, 0x55b85ac}     <-- BOTH branches are predecessors
succ(0x055B85B4) = {0x55b85b7}
instructions SKIPPED when either branch is taken : 78, range 0x55b846b..0x55b85ac
is the Super call in the skipped set?             : False
Super reachable from 0x55b8370 / 845e / 8465 / 846b / 8474 / 85b4 : True / True / True / True / True / True
```

⇒ **[M] Both branches jump *into the Super call's own basic block*. They skip only a 78-instruction
loop. Neither can prevent the Super call.** S139 listed them as "the next thing to read live";
**that ranking is wrong — a live read of either field answers nothing about §1.**

#### Field A — `test byte [CharacterOwner + 0x580], 8` = **`ACharacter::bClientUpdating`** [M]
Named from the UHT `FBoolPropertyParams` table. Record layout established from a **passing positive
control** (CLAUDE.md's S136 `bWantsPlayerState`), then applied:
`Name @ rec+0x00`, `PropertyFlags @ +0x10`, `{ArrayDim u16, ElementSize u16, SizeOfOuter u16} @ +0x30`,
`SetBitFunc @ +0x38`.

```
CONTROL rec 0x842d210: 'bWantsPlayerState'                     SizeOfOuter=0x4e0 SetBitFunc=0x45cfa10
                        83 89 88 04 00 00 20 c3  or dword [rcx+0x488], 0x20 ; ret   <-- matches CLAUDE.md exactly
CONTROL rec 0x842d250: 'bSetControlRotationFromPawnOrientation' SetBitFunc=0x45cfa20
                        83 89 88 04 00 00 40 c3  or dword [rcx+0x488], 0x40 ; ret   <-- CLAUDE.md's adjacent-bit control

TARGET  rec 0x7f8f140: 'bClientUpdating'             SizeOfOuter=0x7f0 SetBitFunc=0x350c270
                        83 89 80 05 00 00 08 c3  or dword [rcx+0x580], 0x08 ; ret
        rec 0x7f8f180: 'bClientWasFalling'           SizeOfOuter=0x7f0 SetBitFunc=0x350c300
                        83 89 80 05 00 00 10 c3  or dword [rcx+0x580], 0x10 ; ret
        rec 0x7f8f1c0: 'bClientResimulateRootMotion' SizeOfOuter=0x7f0 SetBitFunc=0x350c310
                        83 89 80 05 00 00 20 c3  or dword [rcx+0x580], 0x20 ; ret
```
`or dword [rcx+0x580],8; ret` occurs **exactly once** image-wide (`0x350C270`). Three consecutive bits
`0x08/0x10/0x20` at the same offset with `SizeOfOuter = 0x7F0`, in **stock UE5 `ACharacter.h`
declaration order** — an unforced corroboration.

⇒ **field A is `ACharacter+0x580` bit `0x08` = `bClientUpdating`** — true only while a client is
replaying saved moves. Semantics: *skip the timer loop during a client move replay*. Nothing to do
with whether movement simulates.

#### Field B — `[CMC + 0x1988]` = the `Num` of a `TArray` at `CMC+0x1980` ([M] structure, [I] name)
The loop body (`0x055B847A..0x055B85AC`) walks it with **stride 12**
(`movsxd rax,ebp; lea r13,[rax+rax*2]; shl r13,2`, and `sub r13,0xC` per iteration), reads
`int32 @elem+0` and passes `&elem+4` to `0x0137DE80` (an `FWeakObjectPtr::Get`-shaped call), then
`0x0322E260(latentMgr, obj, uuid, &out)` → a struct with `float @+8` (decremented by `dt`),
`FName @+0xC`, `int32 @+0x14` (`== -1` test), `FWeakObjectPtr @+0x18`, `byte @+0x20` — and finally
`call qword ptr [r9 + 0x270]` = **`UObject::ProcessEvent` (vtable disp 0x270 = slot 78)**.
That is a latent-action resume. `binds_members.csv` lists
`ULokiCharacterMovementComponent::MovementDelay(float32 Duration, FLatentActionInfo LatentInfo)`.
Independent corroboration: the `ULokiCMC` destructor (`0x0530AAA0`) frees `[this+0x1980]` with the
game's `FMemory::Free 0x00FF9310`, i.e. `+0x1980` really is a heap `TArray::Data`.

⇒ **`CMC+0x1980` = `TArray<{int32 UUID, FWeakObjectPtr CallbackTarget}>` of pending `MovementDelay`
latent actions; `+0x1988` = its `Num`; `+0x198C` = `Max`.** On an idle bot `Num == 0`, so
`sub ebp,1` → `-1` → **`js` is taken** and the loop never runs. Live prediction: `[CMC+0x1988] == 0`.

---

## 2. PART 2 — THE LADDER

All memory stores in the function, detected with the corrected detector (§0), classified by
`DOM` = *this instruction dominates `0x055B85C1`*, i.e. it executes on **every** path from entry to
the Super call (entry-rooted iterative dominators over the instruction graph). Stack (`[rsp+…]`)
stores suppressed. **`rsi` is `this` for the whole body** — written at exactly two sites,
`0x055B837E mov rsi,rcx` and `0x055B88DC pop rsi`. **`r15 = [this+0x198]` (CharacterOwner) or NULL**
— written at `0x055B8381`, `0x055B83A6 (xor r15d,r15d)` and `0x055B8747 (restore)` only.

| addr | store | phase | DOM | owner | value written |
|---|---|---|---|---|---|
| `0x055B8414` | `movss [rsi+0x12B0], xmm0` | PRE | **DOM** | **CMC** | `+= DeltaSeconds` |
| `0x055B8430` | `movss [rsi+0x12E8], xmm0` | PRE | no | CMC | `-= dt`, only while `> 0` |
| `0x055B850C` | `movss [rax+8], xmm0` | PRE | no | latent action | timer countdown |
| `0x055B853B` | `mov byte [rbx+0x20], 1` | PRE | no | latent action | flag |
| `0x055B857F` | `dec dword [r14+8]` | PRE | no | `CMC+0x1988` | array `Num--` |
| `0x055B85B7` | `mov byte [rsi+0x1308], 0` | PRE | **DOM** | **CMC** | **0** |
| `0x055B85FD` | `movss [r15+0x16EC], xmm1` | POST | – | **Character** | `+= dt` |
| `0x055B860B` | `mov byte [r15+0x16C8], 0` | POST | – | **Character** | 0 — ⚠ DECOY, see §5.4 |
| `0x055B861F` | `movss [r15+0x16D0], xmm1` | POST | – | **Character** | `+= dt` |
| `0x055B865C` | `movss [rbx+rax+0x30], xmm0` | POST | – | Character array elem | `+= dt` |
| `0x055B8694` | `dec dword [rdi+8]` | POST | – | `Character+0x16F8` | array `Num--` |
| `0x055B876F` | `mov qword [rsi+0x1310], 0` | POST | – | CMC | **0** |
| `0x055B8856` | `movups [rsi+0x12F0], xmm2` | POST | – | CMC | normalized velocity X,Y |
| `0x055B885D` | `movsd [rsi+0x1300], xmm0` | POST | – | CMC | normalized velocity Z |
| `0x055B88CD` | `movss [rsi+0x16D0], xmm0` | POST | – | **CMC** | **`(float)World->TimeSeconds`** |

There are **no CMC stores between entry and `0x055B840C`** other than the two listed.

### 2.1 Discriminating power, per candidate

| receipt | separates | grade | why |
|---|---|---|---|
| **`CMC+0x12B0`** (already in use) | **(a) entered AND (b) past the HitStop region** | GOOD | The accumulated value is `xmm6`, which the HitStop branch at `0x055B83FA` zeroes. Advancing ⇒ entered **and** HitStop did not fire. Frozen while ticking ⇒ either not entered or HitStop fired. |
| `CMC+0x12E8` | nothing | USELESS | conditional countdown; `0` at rest, never written when `0`. |
| loop stores (`0x055B850C/853B/857F`) | nothing | USELESS | the loop is skipped whenever `[CMC+0x1988] == 0`, which is the resting state. |
| `CMC+0x1308` | nothing | **USELESS — and a trap** | It is `DOM` and sits 10 bytes before the call, so it *looks* like a perfect "reached the call" latch. **It writes 0, and 0 is the rest value.** A live read of 0 cannot distinguish "reached the call" from "never ran". (It is read back at `0x055B873B`; a *different* function, `0x055BEDB0`, sets it to 1 — so its role is "something requested a skip during PerformMovement".) |
| `CMC+0x1310` | nothing | USELESS | writes 0. |
| `CMC+0x12F0` (24-byte FVector) | nothing **in the measured state** | USELESS HERE | The store is skipped when `Velocity == (0,0,0)` (§2.4), and Velocity is measured `(0,0,0)`. It preserves the last non-zero direction. |
| **`CMC+0x16D0`** | **(d′) the Super call RETURNED** | ★★★ **GOOD, and it is armed by the S139 flight-4 treatment** | see §2.2 |

### 2.2 ★ THE RECEIPT: `CMC+0x16D0 = (float)World->TimeSeconds`

```
0x055b8865  movsd  xmm0, [rsi + 0x328]           ; Acceleration.X (double)
0x055b886d  movsd  xmm1, [0x0769E440]            ; 0x7FFFFFFFFFFFFFFF  = abs mask
0x055b8875  movsd  xmm2, [0x076B49E8]            ; 9.999999747378752e-05 = KINDA_SMALL_NUMBER
0x055b887d  andps  xmm0, xmm1
0x055b8880  comisd xmm0, xmm2
0x055b8889  ja     0x55b88ad                     ; |X| > 1e-4  -> store
0x055b888b  movsd  xmm0, [rsi + 0x330]  ...  ja  0x55b88ad     ; |Y| > 1e-4 -> store
0x055b889c  movsd  xmm0, [rsi + 0x338]  ...
0x055b88ab  jbe    0x55b88d5                     ; all three <= 1e-4 -> SKIP
0x055b88ad  mov rax,[rsi+0xc0] / test / jne / mov rcx,rsi / call 0x35afc40    ; World, with GetWorld() fallback
0x055b88c1  f2 0f 10 80 08 08 00 00   movsd    xmm0, [rax + 0x808]
0x055b88c9  66 0f 5a c0               cvtpd2ps xmm0, xmm0
0x055b88cd  f3 0f 11 86 d0 16 00 00   movss    [rsi + 0x16d0], xmm0
```

`World + 0x808` is **`UWorld::TimeSeconds`** — [M], with three sibling positive controls, each a
separate reflected function naming its own offset:

```
UGameplayStatics::GetTimeSeconds          0x37DB150 -> movsd xmm0, [World + 0x808]
UGameplayStatics::GetUnpausedTimeSeconds  0x37DB250 -> movsd xmm0, [World + 0x810]
UGameplayStatics::GetRealTimeSeconds      0x37D9840 -> movsd xmm0, [World + 0x818]
UGameplayStatics::GetAudioTimeSeconds     0x37D6600 -> movsd xmm0, [World + 0x820]
```
(Stock UE5 declaration order, 8-byte doubles, consecutive.)

Properties that make this the right receipt:
1. **It is a TIMESTAMP, not a boolean.** A probe can compare it against the live `World->TimeSeconds`
   and say *when* it last fired, not merely whether. Immune to the "0 at rest" failure that kills
   `+0x1308` and `+0x1310`.
2. **[M] every post-Super path reaches its guard block.** `exits_from(0x055B8865)` returns exactly one
   edge — its own fallthrough. There is no early `ret` anywhere after the Super (the function's single
   `ret` is at `0x055B88DD`).
3. **Its guard is `!Acceleration.IsNearlyZero(1e-4)`, which the S139 flight-4 treatment satisfies by
   ~8 orders of magnitude** (`Acceleration = input × 50000`, |input| ≈ 1) — and which the *untreated*
   player fails (measured non-zero in 0 of 20 samples). So the receipt is **armed on the treated bot
   and silent on the untreated player in the same pass** — a free within-run specificity control.
4. **Attribution:** among **335 unique `ULokiCMC` vtable implementations** swept with a full CFG each
   (15 on dark pages, 0 CFG failures), the only store to displacement `0x16D0` with a base provably
   equal to `this` is `0x055B88CD`. The scoped `.pdata` sweep (§5.3; 15,702 CFG roots, 931,960
   distinct instructions) adds no CMC-`this` writer either. **Bounded, not absolute** — see §5.3/§6.

### 2.3 What each rung buys — including a plain negative

- **(a) entered** and **(b) past HitStop** → `CMC+0x12B0` advancing. *Already measured.*
- **(c) reached the Super call** → **no separate receipt is needed, and none exists.** §1 proves
  (a) ⇒ (c) **structurally**: the call is unconditional, and on the branch-taken path the step from
  the `+0x12B0` store to the call is call-free and branch-free. Building a receipt for (c) is wasted
  work.
- **(d) the engine impl was entered** → `CMC+0x16D0` tracking `World->TimeSeconds` proves control
  passed **through and back over** the call site, hence the callee was entered and returned.
  `0x035E9EC0` is real code (1461 instructions), not a fold, so "entered" is not vacuous.

**PLAIN NEGATIVE, as requested: no store in this function separates (c) from (d).** Every store is
either strictly before the call (so it cannot see the callee) or strictly after it (so it requires
the callee to have *returned*). There is no instrumentation point *inside* the call. The best
available is `+0x16D0`, which gives "(d) entered **and returned**" — strictly stronger than (d), but
not decomposable into "entered but bailed early" vs "entered and ran to the end" **from this function
alone**. §5.5 offers a one-byte experiment that does decompose it.

### 2.4 The normalized-velocity block (why `CMC+0x12F0` is useless right now)
```
0x055b877d  movsd xmm6,[rsi+0xf0]   ; Velocity.Y      (independently re-confirms Velocity @ CMC+0xE8)
0x055b8785  movsd xmm4,[rsi+0xe8]   ; Velocity.X
   X*X + Y*Y == 1.0 ? -> pass through ;  < 1e-8 -> substitute (0,0,0)/1.0 ; else normalize by sqrt
0x055b8838  ucomisd xmm4,0 / jne store ; ucomisd xmm3,0 / jne store ; ucomisd Z,0 / je 0x55b8865 (SKIP)
0x055b8856  movups [rsi+0x12f0], xmm2 ;  0x055b885d movsd [rsi+0x1300], xmm0
```
With `Velocity == (0,0,0)` all three `ucomisd`s are equal ⇒ `je 0x055B8865` ⇒ **the store is skipped**
and `CMC+0x12F0` retains its previous value. Confirms the field is a *last non-zero movement
direction*, and confirms it is not usable as a "did this run" receipt in the current dead state.

---

## 3. PART 3 — AFTER THE SUPER RETURNS (`0x055B85C6` onward)

Five blocks. `r15` = the type-checked `CharacterOwner` (or NULL); `rsi` = the CMC.

**B1 `0x055B85C6..0x055B862D` — character timer bank, guarded on `r15 != NULL`.**
Calls `[CharacterOwner vtable + 0xC00]` (float return, saved in `xmm8`), then
`[r15+0x16EC] += dt` (unconditional in this block), and if `[r15+0x16CC] > 0`:
**`mov byte [r15+0x16C8], 0`**, `[r15+0x16D0] += dt`, and when `[r15+0x16D0] >= [r15+0x16CC]`
→ `call 0x055BE930(r15)`. ⚠ These are **Character** fields at offsets that collide with the CMC's —
see §5.4.

**B2 `0x055B8632..0x055B86AA` — a reverse loop over the `TArray` at `Character+0x16F0`
(`Num @ +0x16F8`, stride 0x38).** Each element: `[elem+0x30] += dt`; when `[elem+8] <= [elem+0x30]`
and `[elem+8] > 0`, the element is removed (`memmove 0x0752A65E`, `dec [rdi+8]`, `call 0x01743F40`).
A second per-character expiry bank.

**B3 `0x055B86AC..0x055B86E2` — before/after diff of `[vtable+0xC00]`.** Calls it again, computes
`|before − after|` and, if `> 1e-8`, calls `0x052F5D90(r15+0x1700, before, after)` — a change
broadcast on a delegate-shaped field at `Character+0x1700`.

**B4 `0x055B86E3..0x055B8736`.** `call 0x055B1580(r15)` → bool; if **false**, `GetWorld()` →
`0x055F96C0(World)` → if non-null, `0x0560CE30(that, World, r15)`. A world-subsystem notification
about the character.

**B5 `0x055B873B..0x055B88DD` — the CMC tail.** `if ([rsi+0x1308] == 0)` → clear `[rsi+0x1310]`,
compute and conditionally store the normalized velocity (§2.4). Then, unconditionally, the
`CMC+0x16D0` timestamp block (§2.2). Then epilogue.

**Readout surfaces added by Part 3:** the only *CMC*-owned ones are `+0x1310` (writes 0, useless),
`+0x12F0`/`+0x1300` (useless while Velocity is zero), and **`+0x16D0` (the receipt)**. B1–B4 write
only **Character** state.

---

## 4. Free corroborations of already-banked offsets (all [M], all from this function's own bytes)

| offset | banked as | corroborated here by |
|---|---|---|
| `CMC+0x198` | CharacterOwner | `0x055B8381` + the `0x54F8C40` type check; same pattern in `GetMovementTimestamp 0x055ACE80` |
| `CMC+0xC0` | World | `0x055B84B0`, `0x055B88AD` with the `0x035AFC40` GetWorld fallback — the identical idiom engine `PerformMovement` uses at `0x035E9EEE` |
| `CMC+0xE8` | Velocity (FVector, 3 doubles) | `0x055B8785/877D` read X@0xE8, Y@0xF0, Z@0xF8; and `GetRecentVelocity` (§5.3) reads 0x10+0x8 = 24 bytes from `+0xE8` |
| `CMC+0x328` | Acceleration (FVector, 3 doubles) | `0x055B8865/888B/889C` read X@0x328, Y@0x330, Z@0x338 |

---

## 5. ★★★★★ BY-PRODUCT: `CMC+0x16C8` IS CLEARED BEFORE ENGINE `PerformMovement` RETURNS

This answers the question the BRIEF assigns to **lane A4** ("whether anything ELSE clears `+0x16C8`
is an OPEN question"). I found it while auditing my own store list, and it is the most consequential
thing in this lane.

### 5.1 The clear [M]
`ULokiCMC` vtable displacement **`0xA50`** → `0x0530ABF0`, a 4-instruction pre-thunk
(raw bytes verified: `80 b9 c8 16 00 00 00 74 07 c6 81 c8 16 00 00 00 e9 8b bb 2c fe`):

```
0x0530abf0  cmp byte ptr [rcx + 0x16c8], 0
0x0530abf7  je  0x530ac00
0x0530abf9  mov byte ptr [rcx + 0x16c8], 0        ; *** CLEARS THE LATCH ***
0x0530ac00  jmp 0x35d6790                          ; rel32 -30622837, machine-recomputed
```
`rcx` is `this` at function entry and is not reassigned before the store. Either way the byte is 0
on exit. `0x035D6790` is an engine function that calls `[this vtable + 0x518]` and then, if
`CharacterOwner != NULL`, broadcasts through `CharacterOwner + 0x5E8` via `0x0352A490`.

### 5.2 Engine `PerformMovement` calls that slot, downstream of `StartNewPhysics` [M]
```
0x035e9efd  48 8b d9                  mov rbx, rcx          ; rbx = this, ONLY write of rbx besides the pop
...
0x035eb13a  ff 90 20 07 00 00         call [rax + 0x720]    ; StartNewPhysics  (the S139 call site)
...
0x035eb554  48 8b 03                  mov rax, [rbx]
0x035eb557  4c 8d 4d 18               lea r9,  [rbp + 0x18]     ; OldVelocity  (rbp = frame ptr)
0x035eb55b  4c 8d 85 e8 00 00 00      lea r8,  [rbp + 0xe8]     ; OldLocation
0x035eb562  41 0f 28 cb               movaps xmm1, xmm11        ; DeltaSeconds
0x035eb566  48 8b cb                  mov rcx, rbx              ; rcx = THIS (the CMC)
0x035eb569  ff 90 50 0a 00 00         call [rax + 0xa50]        ; <-- the clearing override
```
Machine graph facts over `CFG(0x035E9EC0)` (1461 insns, 148 calls, 0 indirect jumps, 0 decode failures):
```
0x035EB569 forward-reachable from 0x035EB13A : True
0x035EB13A forward-reachable from 0x035EB569 : False
nodes that can reach 0x035EB569 but not 0x035EB13A : 202   (so it also runs when StartNewPhysics is skipped)
exits_from(0x035EB569) : 0x35e9f1f->0x35eb1a7, 0x35e9f28->0x35eb1a7, 0x35e9f97->0x35eb7cf,
                         0x35e9fa4->0x35eb7cf, 0x35e9fbd->0x35eb7cf, 0x35ea25d->0x35eb150,
                         0x35eb14e->0x35eb150, and its own fallthrough
```
As a cross-check of the session lead's preview, my independent `exits_from(0x035EB13A)` reproduced
**7 edges, |R| = 1075**, set-identical to the preview, **with no backward bail.**

### 5.3 Consequence ([M] mechanism; the *name* `CallMovementUpdateDelegate` is [I, strong])
**`CMC+0x16C8` is set to 1 by `ULokiCMC::StartNewPhysics 0x055C2469` and cleared to 0 by the
`0xA50` override, later in the same engine `PerformMovement` call.**

⇒ ★ **A live read of `CMC+0x16C8` from outside the game thread reads 0 *even on a component whose
`StartNewPhysics` runs perfectly every frame*.** The set/clear window is a fraction of one tick.

⇒ ⚠⚠ **The S139 headline "`ULokiCMC::StartNewPhysics 0x055C2430` HAS NEVER RUN ON EITHER COMPONENT",
which rests on `CMC+0x16C8 == 0` (bot, player, and all 37 CMCs), IS NOT SUPPORTED BY THAT
MEASUREMENT.** The BRIEF's item-2 caveat ("cleared-then-set within that call") describes
`StartNewPhysics`'s own redundant clear at `0x055C2441`; the clear reported here is a **different
function, later in the call**, and it is what destroys the latch's stickiness.

**Scope this correctly.** This refutes the *evidence*, not necessarily the *conclusion* — the pawn
still measurably does not move and `Velocity` is `(0,0,0)`. But the latch can no longer be cited.

Grading split, deliberately:
- **[M]**: `0x0530ABF9` clears `[rcx+0x16C8]`; `0x0530ABF0` is at ULokiCMC vtable disp `0xA50`;
  engine `PerformMovement` calls disp `0xA50` at `0x035EB569` with `rcx = rbx = this`; that site is
  forward-reachable from the `StartNewPhysics` call site and not vice versa.
- **[I, strong]** the *name* `UCharacterMovementComponent::CallMovementUpdateDelegate` — from the
  argument shape `(this, float dt, FVector* OldLocation, FVector* OldVelocity)`, the `[vt+0x518]`
  call (`OnMovementUpdated`), the broadcast through `CharacterOwner+0x5E8`, and its position at the
  end of `PerformMovement`. MSVC RTTI is stripped; nothing names it directly.

**Independent confirmation of what the field MEANS** — reflected getter
`ULokiCMC::GetRecentVelocity`, resolved through the `.data {name, thunk, impl}` triple table
(`rec 0x9BC9AD0` → thunk `0x530C7E0`, impl **`0x530AC10`**), transcribed in full:
```
0x0530ac10  cmp byte [rcx + 0x16c8], 0
0x0530ac17  mov eax, 0x16b0
0x0530ac1c  mov r8d, 0xe8
0x0530ac22  cmove eax, r8d
0x0530ac26  movups xmm0, [rax + rcx]        ; 16 bytes
0x0530ac2a  movsd  xmm1, [rax + rcx + 0x10] ;  8 bytes   => a 24-byte FVector
0x0530ac33/36  store to the out-param
```
⇒ `GetRecentVelocity() = (+0x16C8 ? FVector@CMC+0x16B0 : Velocity@CMC+0xE8)`. So `+0x16C8` is the
"the `+0x16B0` velocity snapshot is valid **for this frame**" flag — a per-frame flag, **by design
not a persistent latch**. Sibling control from the same table: `GetMovementTimestamp` → impl
`0x055ACE80` (reads `HasValidData` via `[vt+0x6B8]`, then `[CMC+0x810]->[+0x1C]`, the network move
timestamp — **not** `+0x16D0`).

**Sweeps used, and their blind spots (stated, because they are complementary):**
1. **ULokiCMC vtable sweep** — `.rdata 0x088F8570`, 413 slots, **all 413 resolve into `.text`**,
   **335 unique impls**, full CFG each, 15 dark, 0 failures.
2. **Scoped `.pdata` sweep** — every row-begin in `[0x05300000,0x055D0000] ∪ [0x035C0000,0x03670000]`:
   20,049 rows → **15,702 CFG roots walked, 931,960 distinct instructions, 2 dark, 6 failures.**

⚠ **Sweep 2 is structurally blind to leaf functions with no unwind data.** Verified directly:
`0x0530ABF0` (the clearing override), `0x0530AC10` (`GetRecentVelocity`) and — critically —
**`ULokiCMC::StartNewPhysics 0x055C2430` itself have NO `.pdata` row.** Only the vtable sweep found
them. Same defect class CLAUDE.md records for `APawn::SpawnDefaultController 0x3BBF3C0`.
**Neither sweep alone is adequate; use the union.**

### 5.4 ⚠⚠ OFFSET COLLISION — `+0x16C8` and `+0x16D0` EXIST ON *BOTH* THE CMC AND THE CHARACTER
This nearly produced a false finding in my own output and it will bite anyone scanning by
displacement. Two *unrelated* field clusters share these offsets:

| offset | on the **CMC** | on the **Character** |
|---|---|---|
| `+0x16B0 .. +0x16C7` | 24-byte `RecentVelocity` snapshot (written by `StartNewPhysics`) | – |
| `+0x16C8` | 1-byte "snapshot valid" flag | part of a 16-byte block (`movups`) |
| `+0x16CC` | – | a float threshold |
| `+0x16D0` | **the `TimeSeconds` receipt** | a float accumulator compared against `+0x16CC` |
| `+0x16D8` | – | 16-byte block / object ptr |
| `+0x16EC` | – | a float accumulator |
| `+0x16F0/+0x16F8` | – | `TArray` Data/Num, stride 0x38 |

Inside `ULokiCMC::PerformMovement` itself, `0x055B860B mov byte [r15+0x16C8], 0` and
`0x055B861F movss [r15+0x16D0], xmm1` are **Character** writes — `r15 = [this+0x198]`. A base-register
name is not provenance. Similarly `0x055A6BCB movups [rsi+0x16C8], xmm0` in `0x055A69F0` looks like a
16-byte CMC store, but `rsi` there is loaded at `0x055A6B91` as `mov rsi,[rdi+0x198]` and type-checked
by the same `0x54F8C40` — it is the Character. Same for `0x055A7562`, `0x055BDD6C`, `0x055BE974`,
`0x055C0DA9`, `0x055C0DB7`, and the `+0x16D0` read at `0x055ACB32` (whose `this` reads
`[rcx+0xF08] = AttributeSetStorage`, a **character** field per CLAUDE.md).

**Writers of `+0x16C8` with `this` provably the CMC** (union of both sweeps):

| addr | function | grade |
|---|---|---|
| `0x055C2441`, `0x055C2469` | `ULokiCMC::StartNewPhysics` (vtable disp `0x720`); `rcx` = `this` at instruction 1 | **[M]** |
| `0x0530ABF9` | the `0xA50` override — **the clear** | **[M]** |
| `0x0530AB4C` | the `ULokiCMC` destructor (vtable disp `0x00`); `rbx = rcx` set at `0x0530AAB1` | **[M]** |
| `0x0559EA48` | a constructor-shaped bulk init that also writes `+0x16B0`/`+0x16C0` (the same snapshot cluster) | **[I, strong]** = the `ULokiCMC` ctor |

`0x05513C05`/`0x05513C0C` write `+0x16C8`/`+0x16D0` as qwords in a bulk zero-init; the owning class
was **not determined** — its neighbouring layout (`+0x16A4 = 0x80`, `+0x16A8 = -1`, `+0x16B8`) does
not match the CMC cluster, so [S] it is a third class. Stated, not glossed.

### 5.5 ★ A ONE-BYTE LIVE EXPERIMENT THAT FALLS OUT OF THIS
Because the `0xA50` clear is the *only* thing that zeroes `CMC+0x16C8` on a live component in steady
state:

> **Write `CMC+0x16C8 = 1` from outside. Sample it over the next few frames.**
> - reads **0** → engine `PerformMovement` reached `0x035EB569` ⇒ it ran essentially to completion
>   (so the wall is *inside* `StartNewPhysics`, or `StartNewPhysics` returned without doing work);
> - stays **1** → engine `PerformMovement` bailed at one of the exits before `0x035EB569`
>   (`0x035EB1A7`, `0x035EB7CF`, `0x035EB150`) **or never ran at all.**

This is the (c)-vs-(d) decomposition Part 2 says no *store* provides. It is one aligned byte — the
same byte the game itself writes twice per tick — and it is readback-verifiable. Pair it with
`CMC+0x16D0` ("the Super returned") and `CMC+0x12B0` ("Loki `PerformMovement` entered with dt > 0")
for a three-rung ladder covering (a)…(d).
⚠ It is a WRITE, not a pure read; CLAUDE.md records external `WriteProcessMemory` as an unresolved
hazard (S138, n=1, confounded). Flag it as such.

---

## 6. What I could NOT establish offline

1. **The field name of `CMC+0x16D0`.** It is not a reflected getter's backing field
   (`GetMovementTimestamp` reads `[CMC+0x810]->[+0x1C]` instead), and I did not build a generic UHT
   *offset* decoder for non-bool properties. Its **semantics** are [M] (`= (float)World->TimeSeconds`,
   written iff `!Acceleration.IsNearlyZero(1e-4)`), which is what the receipt needs.
2. **Whether any non-virtual, out-of-scope, non-`.pdata` function writes `CMC+0x16D0`.** Both sweeps
   are FLOORS. A live probe can nonetheless attribute by *value*: the field should equal the current
   `World->TimeSeconds` to within one tick if `0x055B88CD` wrote it.
3. **The literal symbol name `CallMovementUpdateDelegate`** — [I, strong], §5.3. The mechanism is [M]
   and does not depend on the name.
4. **The resting value of `CMC+0x16D0` before it is ever written.** `0x0559EA48`'s constructor block
   zeroes `+0x16C8`/`+0x16CA`, but I did not prove it zeroes `+0x16D0` (`0x05513C0C` does, on an
   undetermined class). *Live read that settles it:* sample `CMC+0x16D0` on an **untreated** component
   (Acceleration ≈ 0) — it must be `0.0` or a stale old timestamp — and on the treated bot it must
   track `World->TimeSeconds`. That two-sided read is its own control.
5. **Whether `ACharacter::bClientUpdating` is 0 live** — irrelevant to §1 (both branch outcomes reach
   the Super), but one read if anyone wants the exact path.

---

## 7. Addresses determined in this lane

```
ULokiCMC::PerformMovement          0x055B8370 .. 0x055B88DE  (1390 B, 322 insns, byte-complete)
   Super call                      0x055B85C1  e8 fa 18 03 fe -> 0x035E9EC0        [M]
   Super call's basic block        0x055B85B4 (preds: 0x055B8465, 0x055B8474, 0x055B85AC)
   +0x12B0 accumulate / store      0x055B840C / 0x055B8414   (DOM)
   +0x12E8 countdown store         0x055B8430   (conditional)
   +0x1308 clear                   0x055B85B7   (DOM, writes 0 -> useless as a receipt)
   MovementDelay loop              0x055B847A .. 0x055B85AC  (78 insns, skipped when Num==0)
   ** THE RECEIPT **               0x055B88CD  movss [CMC+0x16D0], (float)World->TimeSeconds
   receipt guard block             0x055B8865 (reached on EVERY post-Super path)
   normalized-velocity store       0x055B8856 / 0x055B885D  (skipped when Velocity == 0)

ACharacter::bClientUpdating        ACharacter+0x580 mask 0x08; SetBitFunc 0x0350C270; SizeOfOuter 0x7F0
ACharacter::bClientWasFalling      +0x580 mask 0x10; SetBitFunc 0x0350C300
ACharacter::bClientResimulateRootMotion +0x580 mask 0x20; SetBitFunc 0x0350C310
UHT FBoolPropertyParams layout     Name@+0x00, PropertyFlags@+0x10, {ArrayDim,ElemSize,SizeOfOuter}@+0x30, SetBitFunc@+0x38

CMC+0x1980/0x1988/0x198C           TArray<{int32 UUID, FWeakObjectPtr}> pending MovementDelay latent actions
CMC+0x16B0..+0x16C7                RecentVelocity snapshot (FVector, 3 doubles)
CMC+0x16C8                         "snapshot valid" flag  -- SET 0x055C2469, CLEARED 0x0530ABF9
CMC+0x16D0                         float, = (float)World->TimeSeconds when |Acceleration| > 1e-4

ULokiCMC vtable disp 0xA50         0x0530ABF0 (pre-thunk, clears +0x16C8) -> tail-jmp 0x035D6790
ULokiCMC vtable disp 0x00 (dtor)   0x0530AAA0  (frees +0x1980/+0x1970/+0x1960/+0x1878/+0x1850/
                                                +0x16A0/+0x12B8/+0x11A8/+0x1198/+0x1188 via FMemory::Free 0x00FF9310)
ULokiCMC::GetRecentVelocity        thunk 0x0530C7E0, impl 0x0530AC10   (.data rec 0x9BC9AD0)
ULokiCMC::GetMovementTimestamp     thunk 0x0530C7B0, impl 0x055ACE80   (.data rec 0x9BC9A40)
engine PerformMovement -> disp 0xA50  call site 0x035EB569  (ff 90 50 0a 00 00), rcx = rbx = this
engine PerformMovement  rbx = this   set at 0x035E9EFD (only write besides the pop at 0x035EB1C8)

UWorld::TimeSeconds          +0x808  (UGameplayStatics::GetTimeSeconds 0x37DB150)
UWorld::UnpausedTimeSeconds  +0x810  (0x37DB250)
UWorld::RealTimeSeconds      +0x818  (0x37D9840)
UWorld::AudioTimeSeconds     +0x820  (0x37D6600)
abs mask (double) 0x0769E440 = 0x7FFFFFFFFFFFFFFF ; KINDA_SMALL_NUMBER 0x076B49E8 = 9.999999747378752e-05
```
