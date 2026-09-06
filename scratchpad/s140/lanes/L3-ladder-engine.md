# L3 — A PROGRESS LADDER FOR ENGINE `UCharacterMovementComponent::PerformMovement` (`0x035E9EC0`)

Offline only. Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, FLAT (va==praw on all
10 sections, verified by `peimg.py`). No launches, no injection, no live process touched.

---

## 0. HEADLINE

**On the S139 bot's measured state there are exactly THREE stores to CMC fields between the entry of
engine `PerformMovement` and the `StartNewPhysics` call — and only ONE of them is a usable receipt
without a poked baseline.** The rest of the pre-call store set is root-motion-conditional and is
unreachable on a pawn with no root motion.

**The best rungs are POST-call and they are free to read:**

| rank | field | offset | why |
|---|---|---|---|
| **1** | `LastUpdateRotation` | `CMC+0x340` (32 B, FQuat4d) | zero-filled default `(0,0,0,0)` is **not a valid quaternion**, so ANY non-zero value proves completion, independently of where the pawn is |
| **2** | `LastUpdateLocation` | `CMC+0x360` (24 B, FVector3d) | written only on completion; compare against `UpdatedComponent+0x220` |
| **3** | `ServerLastTransformUpdateTimeStamp` | `CMC+0x390` (float) | **sticky**; fires on the first completion; all four of its guards are measured-passing on this pawn |
| **4** | `bTeleportedSinceLastUpdate` | `CMC+0x703` (byte) | the *entry* rung; the derived complement of #2 — proves engine `PerformMovement` was ENTERED |
| **5** | `NumJumpApexAttempts` | `CMC+0x3DC` (int32) | the **last dominator before the call instruction**; USELESS unless pre-poked to a non-zero value, GOLD with one |

⇒ **`{+0x340, +0x360, +0x703}` read in one pass is a three-way bisector of the exact S140 question,
needs no poke, no injection and no `.text` write:**

* `+0x703 == 1` **and** `+0x340 == (0,0,0,0)` ⇒ **engine `PerformMovement` ENTERS every frame and
  NEVER COMPLETES.** The wall is at or below the `StartNewPhysics` call `0x035EB13A`.
* `+0x340 == the live component quat` (`UpdatedComponent+0x200`) ⇒ **it completes.** The wall is
  inside `StartNewPhysics` or below, and `+0x703` will read `0`.
* `+0x703 == 0` **and** `+0x340 == (0,0,0,0)` ⇒ engine `PerformMovement` is **not being entered at
  all** (contradicting S139 flight 3) — or the pawn is exactly at `LastUpdateLocation`; read the
  pawn location to disambiguate.

---

## 1. Instruments, and their controls

### 1.1 `this`-tracking (the thing the task demanded I show)

`scratchpad/s140/tools/thistrack.py`. A **must**-analysis over the shared `cfg.py` recursive-descent
graph. Lattice per 64-bit register / tracked stack slot: `UNKNOWN` | `('this', d)` | `('frame', d)`.
Join at CFG merge points is **intersection**, so a `this` claim requires the SAME displacement on
every predecessor path — the analysis can only **under**-report, never over-claim. Win64 volatile
registers (`rax rcx rdx r8 r9 r10 r11`) are killed at every `call`. 8/16/32-bit writes kill the
parent register rather than establishing a pointer. Fixpoint converged over all **1461** instructions.

**I did NOT assume one register for the whole function.** Result:

```
0x035e9efd  mov rbx, rcx                 -> rbx = this          (from here on)
0x035e9ff9  lea r14, [rbx + 0xd58]       -> r14 = this+0xd58    (CurrentRootMotion)
0x035ea017  lea rsi, [rbx + 0xe8]        -> rsi = this+0xe8     (Velocity)
0x035ea348  lea rdi, [rbx + 0xf50]       -> rdi = this+0xf50    (RootMotionParams)
0x035ea377  lea r8,  [rbx + 0xf60]       -> r8  = this+0xf60
0x035ea425  lea r8,  [rbx + 0xfc0]       -> r8  = this+0xfc0    (AnimRootMotionVelocity)
0x035eb505  lea r15, [rbx + 0x580]       -> r15 = this+0x580    (RequestedVelocity)
0x035eb81d  lea rcx, [rbx + 0xd58]       -> rcx = this+0xd58
0x035eb82d  lea rcx, [rbx + 0xd58]       -> rcx = this+0xd58
```

**Controls (all run, all reported):**

| # | site | expectation | result |
|---|---|---|---|
| P0 | `0x035e9eee mov r13,[rcx+0xc0]` | `rcx` is still `this` at entry | `rcx=('this',0)` **PASS** |
| P1 | `0x035e9f14 mov rcx,rbx` | `rbx` is `this` | `rbx=('this',0)` **PASS** |
| P2 | `0x035e9f17 call [rdx+0x6b8]` | `rcx` is `this` (HasValidData on self) | `rcx=('this',0)` **PASS** |
| P3 | `0x035e9fc9` (after a 2nd `mov rcx,rbx`) | `rcx` re-established | `rcx=('this',0)` **PASS** |
| **N1** | `0x035e9f35`, after `mov rcx,[rbx+0xd0]` | `rcx` must **NOT** be `this` (it is UpdatedComponent) | `rcx=None` **PASS** |
| **N2** | `0x035e9fb5 call [rax+0x4c0]` | same | `rcx=None` **PASS** |
| **N3** | `0x035e9ef5`, after `mov r13,[rcx+0xc0]` | `r13` must NOT be `this` (it is World) | `r13=None` **PASS** |
| **N4** | `0x035eb785` (tail) | `rdi`/`r14` must have been re-pointed at stack locals | `rdi=None r14=None`, `rsi=('this',232)` **PASS** |
| CALIB-a | `0x035E9F82 mov byte [rbx+0x703], al` | task-given: `rbx` is `this` | `rbx=('this',0)` **CONFIRMED** |
| CALIB-b | `0x035EB130 mov dword [rbx+0x3dc], r15d` | task-given: `rbx` is `this` | `rbx=('this',0)` **CONFIRMED** |
| frame | `lea rbp,[rsp-0x860]` then `sub rsp,0x960` | `rsp = FRAME-24-0x960 = -2424`, `rbp = -2168` | exactly that **PASS** |

N4 is the strongest one: the analysis keeps `rsi = this+0xE8` across ~1400 instructions while
correctly **killing** `rdi` and `r14` in the same region where they are re-`lea`'d to stack slots
(`0x035eb659 lea rdi,[rbp]`, `0x035eb6a6 lea r14,[rbp+0xa0]`). It is not blanket-claiming.

**Independent reproduction of two addresses from the brief:** running the same detector over
`engine ControlledCharacterMove 0x035DCD10` recovers `0x035DCD6B movups [rsi+0x328], xmm0`
(**Acceleration**) and `0x035DCD8F movss [rsi+0x3d0], xmm0` (**AnalogInputModifier**) — the exact
addresses the brief lists. That is a second, external control on the tracker.

### 1.2 ⚠ INSTRUMENT DEFECT FOUND AND WORKED AROUND — capstone 5.0.7 mislabels `movups` stores

My first store detector used a mnemonic whitelist (41 hits). My "more robust" second one used
capstone's operand `access & CS_AC_WRITE` (25 hits). **The disagreement is capstone's fault, not
mine.** Audit over every instruction in this function whose first operand is memory:

```
  call      access=0x1(READ)   n=33      <- correct
  cmp       access=0x1(READ)   n=21      <- correct
  test      access=0x1(READ)   n= 2      <- correct
  mov       access=0x2(WRITE)  n=50      <- correct
  movaps    access=0x2(WRITE)  n=18      <- correct
  movsd     access=0x2(WRITE)  n=30      <- correct
  movss     access=0x2(WRITE)  n= 1      <- correct
  movups    access=0x1(READ)   n=29      <- *** WRONG. all 29 are stores. ***
```

`movaps mem,xmm` is flagged WRITE while `movups mem,xmm` is flagged READ — same semantics, so this
is a capstone bug, and the access-flag filter **silently drops 16 real CMC-field stores** including
`LastUpdateLocation`, `LastUpdateRotation` and `LastUpdateVelocity`. Final detector =
`access&WRITE  OR  mnemonic in {movups,movdqu,movnps,movntps,movntdq}` → **41 `this`-based stores**.
Anyone re-deriving this with the "obvious" access-flag method will lose the three best rungs.

### 1.3 ⚠ MY OWN FIRST PATH-CONDITION TEST WAS WRONG, AND I FIXED IT

v1 reported a branch as a forced direction whenever exactly one of its successors was in `dom(store)`.
That is **false at a JOIN**: for `je L` where both arms converge at `L`, `L` dominates the store and
the fallthrough does not, so v1 printed `TAKEN` for a branch that constrains nothing. It over-stated
the guard chain on 12 stores (e.g. it claimed `0x035eb6c9 je TAKEN` guards the `LastUpdate*` writes;
it does not). Corrected test: **B constrains S iff B ∈ dom(S) and exactly one successor of B can
REACH S**. All path conditions below use the corrected test.

### 1.4 UHT offset oracle — offsets are `[M]`, not guessed

`scratchpad/s140/tools/uht_offset.py` + `uht_bools.py`. Locate the ASCII property-name literal,
find 8-aligned qword pointers to it, decode the `FPropertyParams` record:

```
+0x00 NameUTF8*  +0x08 RepNotify*  +0x10 PropertyFlags(u64)  +0x18 GenFlags(u32)
+0x1C ObjectFlags(u32) +0x20 Setter* +0x28 Getter* +0x30 ArrayDim(u16) +0x32 Offset(u16)
```
For **Bool** records (`GenFlags & 0x3F == 0x0C`) the layout diverges at +0x32 and there is **no
offset field** — instead `+0x34 SizeOfOuter(u32)`, `+0x38 SetBitFunc*`. Disassembling `SetBitFunc`
gives (byte offset, bit mask) directly.

**Calibration — three offsets already measured live by S139 all reproduce, plus three predictions
I made from the disassembly BEFORE querying:**

| name | oracle Offset | independent check |
|---|---|---|
| `MovementMode` | `0x231` | S139 live: `CMC+0x231` ✔ |
| `UpdatedComponent` | `0xD0` | S139 live: `CMC+0xD0` ✔ |
| `CharacterOwner` | `0x198` | S139 live: `CMC+0x198` ✔ |
| `Acceleration` | `0x328` | S139 live: `CMC+0x328` ✔ |
| `MaxAcceleration` | `0x28C`, `AnalogInputModifier` `0x3D0` | both S139-measured fields ✔ |
| `LastUpdateLocation` | `0x360` | **predicted** from `ucomisd xmm1,[rbx+0x360/0x368/0x370]` ✔ |
| `LastUpdateRotation` | `0x340` | **predicted** from the 0x340+0x350 pair ✔ |
| `LastUpdateVelocity` | `0x378` | **predicted** from the 0x378+0x388 pair ✔ |
| `RootMotionParams` | `0xF50` | **predicted** from `lea rdi,[rbx+0xf50]` ✔ |
| `AnimRootMotionVelocity` | `0xFC0` | **predicted** from `lea r8,[rbx+0xfc0]` ✔ |
| `CurrentRootMotion` | `0xD58` | **predicted** from `lea r14,[rbx+0xd58]` ✔ |
| bool `bForceNextFloorCheck` | `SetBitFunc 0x035CABE0 = 80 89 e9 02 00 00 08 c3` = `or byte [rcx+0x2e9],8; ret` | **exactly** the field engine `PerformMovement` read-modify-writes at `0x035E9FF2`/`0x035EA009` ✔ |

54/54 bool `SetBitFunc`s in the CMC record block decoded. **Negative control that the oracle is not
hallucinating:** `bTeleportedSinceLastUpdate` and `NumJumpApexAttempts` return **0 records** in the
same query that finds `bHasRequestedVelocity` and `RequestedVelocity` — i.e. they are genuinely
**not reflected**, so their names below are `[I]`, not `[M]`.

---

## 2. THE STORES — full enumeration

CFG: `entry 0x035E9EC0 → 1461 insns, 148 calls, 0 indirect jumps, 0 decode failures,
0 noreturn candidates`. `|reach_backward(0x035EB13A)| = 1075`. `|dom(call)| = 128`.
`|POST(0x035EB140)| = 358`, `|BAIL(0x035EB7CF)| = 39`. Single exit: `ret` at `0x035EB1CA`
(terminator set = `{0x35eb1ca}` exactly, so post-dominance is well-defined).

**41 `this`-based stores. 87 further memory writes have a base that is provably NOT `this`
(stack/other objects) — the `this` set is a MUST set, i.e. a floor.**

Only **THREE** stores dominate the call: `0x035E9F82` (+0x703), `0x035EA009` (+0x2E9),
`0x035EB130` (+0x3DC).

### 2.1 The five entry gates every PRE store shares

```
0x035e9f1f  je 0x35eb1a7   NOT taken   <- HasValidData()  (vt disp 0x6b8) returned true
0x035e9f28  je 0x35eb1a7   NOT taken   <- World != null
0x035e9f97  je 0x35eb7cf   NOT taken   <- MovementMode != MOVE_None   (byte [rbx+0x231])
0x035e9fa4  jne 0x35eb7cf  NOT taken   <- UpdatedComponent->Mobility == 2 (byte [rcx+0x1bb])
0x035e9fbd  jne 0x35eb7cf  NOT taken   <- UpdatedComponent->IsSimulatingPhysics() == false (vt 0x4c0)
```
All five are measured-passing on the S139 bot.

### 2.2 The stores, in path order

| # | rva | field | off | w | value written | phase | extra guard beyond §2.1 |
|---|---|---|---|---|---|---|---|
| 1 | `0x035E9F82` | `bTeleportedSinceLastUpdate` [I] | `0x703` | 1 | computed `al` = `ComponentLocation != LastUpdateLocation` | PRE **DOM** | — (only the first two of §2.1) |
| 2 | `0x035EA009` | `bForceNextFloorCheck` bit `0x08` [M] | `0x2E9` | 1 | `old \| (IsMovingOnGround() && bTeleported)` | PRE **DOM** | — |
| 3-5 | `0x035EA040/058/070` | `CurrentRootMotion.LastPreAdditiveVelocity` [M+M] | `0xD88/D90/D98` | 8 | computed | PRE | `0x035ea020 je` NOT taken → has active root-motion sources |
| 6-8 | `0x035EA1B3/1BB/1C3` | same | `0xD88/D90/D98` | 8 | computed | PRE | root motion, deeper |
| 9-18 | `0x035EA391 … 0x035EA3DA` | `RootMotionParams.{bHasRootMotion=1, RootMotionTransform, BlendWeight=1.0f}` [M] | `0xF50,0xF60-0xFB0,0xF54` | 1/16/4 | `1`, transform, `0x3f800000` | PRE | `0x035ea375 je` NOT taken → `CharacterOwner->[+0x450] != 0` (mesh) |
| 19-20 | `0x035EA43A/446` | `AnimRootMotionVelocity` [M] | `0xFC0/FD0` | 16/8 | computed | PRE | `0x035ea3e8 jbe` NOT taken |
| 21-24 | `0x035EA458/463/48B/48F` | **`Velocity`** [M] | `0xE8/F0/F8` | 16/8 | root-motion velocity | PRE | as above (+`0x035ea470 je` NOT taken) |
| 25-26 | `0x035EB10A/10D` | **`Velocity`** [M] | `0xE8/F8` | 16/8 | override root-motion velocity | PRE | `0x035ea351 jne` TAKEN, `0x035ea361 je` TAKEN, `0x035eb047 jbe` NOT taken |
| **27** | `0x035EB130` | `NumJumpApexAttempts` [I] | `0x3DC` | 4 | **constant `0`** (`r15d`, zeroed at `0x035E9F7F`) | PRE **DOM — last dominator before the call** | — |
| — | `0x035EB13A` | **`call [rax+0x720]` = `StartNewPhysics(dt, 0)`** (`ff 90 20 07 00 00`, `r8d=0` at `0x035EB129`) | | | | | |
| 28-29 | `0x035EB3A0/3A3` | `RootMotionParams.Clear()` [M] | `0xF50/F54` | 1/4 | `0`, `eax=0` | POST | anim-root-motion path only |
| 30-32 | `0x035EB520/52D/536` | `LastUpdateRequestedVelocity` [M], `bHasRequestedVelocity` bit0 [M] | `0x598/5A8`, `0x554` | 16+8, 1 | `bHasRequestedVelocity ? RequestedVelocity : Zero`; bit cleared | POST | `0x035eb14e jne` TAKEN |
| 33 | `0x035EB77D` | `ServerLastTransformUpdateTimeStamp` [M] | `0x390` | 4 f32 | `cvtpd2ps(World[+0x808])` = world time | POST | `+ 0x035eb6c9/6d2/6e3` all NOT taken |
| 34-35 | `0x035EB78D/7A2` | **`LastUpdateLocation`** [M] | `0x360` | 16+8 | live `UpdatedComponent` translation (stack copy at `[rbp]`) | POST | `0x035eb14e jne` TAKEN |
| 36-37 | `0x035EB798/7AF` | **`LastUpdateRotation`** [M] | `0x340` | 16+16 | live `UpdatedComponent` quat (stack copy at `[rbp-0x20]`) | POST | `0x035eb14e jne` TAKEN |
| 38-39 | `0x035EB7BB/7C2` | `LastUpdateVelocity` [M] | `0x378` | 16+8 | **`= Velocity`** (`rsi = this+0xE8`) | POST | `0x035eb14e jne` TAKEN |
| 40-41 | `0x035EB80F/816` | `RootMotionParams.Clear()` [M] | `0xF50/F54` | 1/4 | `0`,`0` | **BAIL** (`0x035EB7CF`) | early-bail path only |

Raw bytes for every load-bearing site (recomputed, not retyped):

```
0x035e9f82  88 83 03 07 00 00              mov byte  [rbx+0x703], al
0x035e9f44  66 0f 2e 8b 60 03 00 00        ucomisd xmm1, [rbx+0x360]
0x035e9f5f  66 0f 2e 8b 68 03 00 00        ucomisd xmm1, [rbx+0x368]
0x035e9f6f  66 0f 2e 83 70 03 00 00        ucomisd xmm0, [rbx+0x370]
0x035ea009  88 8b e9 02 00 00              mov byte  [rbx+0x2e9], cl
0x035eb130  44 89 bb dc 03 00 00           mov dword [rbx+0x3dc], r15d
0x035eb13a  ff 90 20 07 00 00              call qword [rax+0x720]
0x035eb78d  0f 11 83 60 03 00 00           movups    [rbx+0x360], xmm0
0x035eb7bb  0f 11 83 78 03 00 00           movups    [rbx+0x378], xmm0
0x035cabe0  80 89 e9 02 00 00 08 c3        or byte [rcx+0x2e9],8 ; ret   (SetBitFunc)
0x055b85c1  e8 fa 18 03 fe                 call 0x035e9ec0   (Super, brief item 1 reproduced)
```

### 2.3 The path our bot actually takes — this is the crux

`0x035EA343 call 0x37DD3E0` on `CurrentRootMotion` (`HasOverrideVelocity()`), then
`0x035EA351 jne / 0x035EA356 je 0x35EB112` — with **no root motion of any kind**, control jumps
**directly to `0x035EB112`**, i.e. straight to `ClearJumpInput` → `NumJumpApexAttempts = 0` →
`StartNewPhysics`. Everything in rows 3-26 is skipped.

⇒ **On the S139/S140 bot, the executed pre-call store sequence is exactly:**

```
0x035E9F82  +0x703  bTeleportedSinceLastUpdate = <computed>
0x035EA009  +0x2E9  bForceNextFloorCheck |= (IsMovingOnGround() && bTeleported)   <- OR of 0 in MOVE_Falling
0x035EB130  +0x3DC  NumJumpApexAttempts = 0                                       <- 0 into 0
```

**Three stores. Two of them are semantic no-ops in this state. The pre-call ladder has ONE free rung.**

### 2.4 Post-dominance — what "the call returned" buys you

`0x035EB140` (call fallthrough) → `call [rax+0x6b8]` = **`HasValidData()` again** →
`0x035EB14E jne 0x35EB1CB`. If HasValidData is false the function runs the scoped-update destructor
and returns; that is why **no store post-dominates `0x035EB140`** (the section printed empty).

But **all of rows 30-39 post-dominate `0x035EB1CB`** (verified: `0x35eb78d/798/7a2/7af/7bb/7c2/520/52d/536`
∈ pd(`0x35eb1cb`), and the only `jmp` back to the epilogue from the tail is the single
`0x035EB7CA jmp 0x35EB15C` *after* them). ⇒ **once `HasValidData()` still holds after
`StartNewPhysics`, `LastUpdateLocation` / `LastUpdateRotation` / `LastUpdateVelocity` are
GUARANTEED to be written.**

---

## 3. RANKED LADDER OF LIVE-READABLE CHECKPOINTS

Ranked by (discriminating power) × (fraction of the path proved).

### RUNG 5 (top of path) — `LastUpdateRotation` `CMC+0x340`, 32 bytes — **GOOD, no baseline needed**
*Written at `0x035EB798`+`0x035EB7AF`. Proves: entry gates + StartNewPhysics returned + HasValidData
still true — i.e. **the whole function ran**.*
`UObject` memory is zero-filled at allocation `[I, strong — engine-general]`, so the untouched value
is `(0,0,0,0)`, which is **not a unit quaternion and cannot be any real rotation**. Therefore *any*
non-zero content is proof of completion, **independent of the pawn's position or rotation**.
Strongest form, which removes even the zero-fill assumption: compare it against the live
`UpdatedComponent+0x200..0x21F` — that is literally the value this store copies (`0x035EB683
movups xmm0,[rax+0x200]` / `0x035EB68E [rax+0x210]`, `rax = [rbx+0xd0] = UpdatedComponent`).
Equal ⇒ completed this frame. **`ComponentToWorld` @ `USceneComponent+0x200` (Rotation FQuat4d 32 B)
and Translation @ `+0x220` are `[M]` from these instructions.**

### RUNG 4 — `LastUpdateLocation` `CMC+0x360`, 24 bytes — **GOOD**
*Written at `0x035EB78D`+`0x035EB7A2`. Same coverage as rung 5.*
Compare against `UpdatedComponent+0x220..0x237`. Slightly weaker than rung 5 only because a pawn at
the world origin would make `(0,0,0)` ambiguous. **Read the pawn location in the same pass.**

### RUNG 3 — `ServerLastTransformUpdateTimeStamp` `CMC+0x390`, float — **GOOD and STICKY**
*Written at `0x035EB77D`. Value = `cvtpd2ps(World[+0x808])`, a real world-time float; nothing in
this function ever clears it.*
Its four guards are ALL measured-passing or reachable on this pawn:
`r15b = (CharacterOwner != null && CharacterOwner->Role@+0x160 == 3)` — S139 measured Role **3** ⇒ 1;
`UpdatedComponent != null` — measured non-null; `GetNetMode() != 3 (NM_Client)` — S137 measured
**NM_Standalone(0)**; and "location or rotation differs from `LastUpdate*`" — TRUE on the very first
completion because `LastUpdateLocation` is still `(0,0,0)`.
⇒ **a non-zero float here is a permanent "engine PerformMovement completed at least once".**
⚠ It stops updating once the pawn is stationary and `LastUpdate*` has caught up — that is expected,
not a failure.

### RUNG 1 (bottom of path) — `bTeleportedSinceLastUpdate` `CMC+0x703`, byte — **GOOD (conditional)**
*Written at `0x035E9F82`, depth 31, DOMINATES the call. Proves: `HasValidData()` returned true and
`World != null` — i.e. **engine `PerformMovement` was ENTERED**. Nothing above the two entry gates.*
Value = `1` iff `UpdatedComponent->GetComponentLocation() != LastUpdateLocation`.
**Why it is good here:** if `PerformMovement` never completes, `LastUpdateLocation` never advances,
so this is written **1** every frame while the field's default is 0.
**Why it is conditional:** if `PerformMovement` DOES complete, this reads **0** on a stationary pawn
— which is indistinguishable from "never written". ⇒ **it is only interpretable jointly with rung 4/5.**
The pairing is what makes it a bisector (see §0).
⚠ Its NAME is `[I]` (no UHT record; from the stock-UE first line of `PerformMovement`). Its
**semantics are `[M]`** from the disassembly: three `ucomisd` against `LastUpdateLocation` (UHT-confirmed
`0x360/0x368/0x370`) of the `UpdatedComponent` `ComponentToWorld` translation, `al=0` if all equal
else `al=1`.

### RUNG 2 — `bForceNextFloorCheck` `CMC+0x2E9` bit `0x08` — **USELESS in this state**
*Written at `0x035EA009`, DOMINATES the call; would prove all five §2.1 gates passed.*
The store is `old | (IsMovingOnGround() && bTeleportedSinceLastUpdate)`. The pawn is
`MOVE_Falling(3)`, so `IsMovingOnGround()` is false and the store writes the byte back unchanged.
**Provably indistinguishable.** It would become GOOD only on a grounded pawn.
⚠ Do not "improve" it by poking the bit — the store is an OR, so a poked 1 survives regardless of
whether the store ran.

### RUNG 6 — `NumJumpApexAttempts` `CMC+0x3DC`, int32 — **USELESS bare; the BEST rung WITH a poked baseline**
*Written at `0x035EB130`, the **last dominator before the call instruction**. Reaching it proves
everything except the call itself.*
Value is constant `0` into a field whose resting value is `0`. Nothing else can move it here:
`PhysFalling` (the stock incrementer) is dispatched from inside `StartNewPhysics`, which never runs.
⇒ **flagged: REQUIRES a known non-default baseline.** Poke `CMC+0x3DC = 0xDEADBEEF` externally; if a
later read shows `0`, execution reached `0x035EB130`, i.e. **one instruction before the
`StartNewPhysics` call**. Combined with the latch `+0x16C8` still reading 0, that isolates the wall
to the call/dispatch itself or to engine `StartNewPhysics`'s own prologue.
⚠ Only ONE other writer exists on the CMC virtual surface: `0x035D31DD` inside vslot 336 (the
`SimulateMovement`-shaped function), which is a simulated-proxy path and cannot run on a Role==3 pawn.

### RUNG 7 — `LastUpdateVelocity` `CMC+0x378` — **USELESS in this state**
It copies `Velocity`, and S139 measured `Velocity == (0,0,0)`. Zeros into zeros.
Would become GOOD the moment Velocity is non-zero (i.e. it is a good *second-phase* rung).

### RUNG 8 — `LastUpdateRequestedVelocity` `CMC+0x598` / `bHasRequestedVelocity` `CMC+0x554` bit0 — **USELESS**
`bHasRequestedVelocity` is false, so `0x035EB520` writes a zero vector and `0x035EB52D` clears an
already-clear bit. Both indistinguishable from default.
⚠ **Would need a poked baseline in `+0x598` to be usable** — and unlike `+0x3DC` it has four other
writers on the virtual surface, so it is the worse choice.

### Rows 3-26 (root-motion cluster, `0xD88`, `0xF50-0xFD0`, `0xE8`) — **UNREACHABLE in this state**
Skipped wholesale by `0x035EA356 je 0x35EB112`. A null there says nothing about progress.

---

## 4. WHO ELSE WRITES THESE FIELDS (bounded sweep — a FLOOR, not a uniqueness proof)

`scratchpad/s140/tools/l3_fieldwriters.py`: recursive-descent CFG + the same `this`-tracker over
**all 413 slots of the `ULokiCharacterMovementComponent` vtable** (`.rdata 0x088F8570`).
413/413 slots resolve into `.text`; **398 analysed, 15 on DARK pages (unanalysable), 0 failures.**

**Positive control (necessary, and it changed the reading):** engine `PerformMovement` is reached from
slot 341 by a `call`, not a `jmp`, so the sweep does not cover it. Running the identical detector on
`0x035E9EC0` directly recovers all 16 watched offsets — so the sweep's zeros below are real negatives
*relative to the other 412 slots*, not detector failures.

| offset | other writers found | interpretation |
|---|---|---|
| **`0x703`** | **NONE** | `0x035E9F82` is the only writer anywhere on the CMC virtual surface |
| **`0x390`** | **NONE** | `0x035EB77D` is the only writer on the virtual surface |
| `0x340`/`0x350` | `0x035D2F16` (vslot336), `0x035FCF28` (via vslot345) | proxy / client-correction paths only |
| `0x360` | `0x035D4CDA` (vslot147 = **`ApplyWorldOffset`** — it *adds* an offset to `+0x260` and `+0x360/368/370`, i.e. world-origin rebasing), `0x035D2EFE` (vslot336), `0x035FCED4` (vslot345) | none of the three can run on a stationary Role-3 pawn in a non-shifted world |
| `0x3DC` | `0x035D31DD` (vslot336 only) | proxy path |
| `0x378`/`0x388` | vslot336, vslot345 | proxy / correction |
| `0x2E9` | 15 sites across 10 slots | heavily shared bitfield byte — another reason rung 2 is useless |
| `0x554`/`0x598`/`0x5A8` | 10 / 3 / 3 sites | shared |

**Scope limit, stated:** virtual surface + decrypted pages only. Non-virtual CMC members, free
functions and `ACharacter` code are NOT covered. Treat "NONE" as *"no writer on the class's virtual
surface"*, never as *"no writer exists"*. `[M, bounded]`.

---

## 5. BY-PRODUCTS FOR OTHER LANES (offered, not claimed as my lane's result)

1. **`0x035E9FB5 call [rax+0x4C0]` passes `edx = r15d = 0`** (`0x035E9FAD 41 8b d7`, `r15d` zeroed at
   `0x035E9F7F 45 33 ff`). For `USceneComponent::IsSimulatingPhysics(FName BoneName)` that is
   `NAME_None`. ⚠ This is **not** the `bGetWelded` argument CLAUDE.md records — that belongs to
   `GetBodyInstance(BoneName, bGetWelded)` at vtable disp `0x810` (`0x03C91C60`), a different callee.
   No contradiction; the two should not be conflated. `[M]` on the bytes, `[I]` on the parameter name.
2. **Engine `StartNewPhysics 0x03600990` SAVES AND RESTORES `bMovementInProgress`** (`+0x2E8` bit
   `0x40`): `0x03600A73 or al,0x40` / `0x03600A75 mov [rbx+0x2e8],al`, restored at
   `0x03600BB7..0x03600BCB`. It is **transient** and therefore useless as a polled receipt — but a
   sampled read of `+0x2E8 & 0x40 == 1` means "inside `StartNewPhysics` right now". `[M]`
3. **`0x035EB146 call [rax+0x6B8]` is a SECOND `HasValidData()`**, immediately after
   `StartNewPhysics` returns, and `0x035EB14E jne 0x35EB1CB` bails the whole tail if it fails. If a
   future flight ever sees `+0x16C8 == 1` but `LastUpdateRotation` still zero, **this is the gate to
   suspect.** `[M]`
4. **`USceneComponent::ComponentToWorld` layout `[M]`**: Rotation `FQuat4d` @ `+0x200` (32 B),
   Translation `FVector3d` @ `+0x220` (24 B) — read directly off `0x035EB683/68E` (rotation) and
   `0x035E9F3D/0x035E9F4C` (translation), both with `rax/rcx = [CMC+0xd0]`.
5. **A reusable offline UHT offset oracle for `UCharacterMovementComponent`** now exists:
   91 non-bool properties with exact offsets + 54 bool properties with exact (byte, mask), all
   decoded, 6 of them cross-validated against S139 live reads. Tools:
   `scratchpad/s140/tools/uht_offset.py`, `uht_bools.py`.

---

## 6. WHAT I COULD NOT ESTABLISH OFFLINE

1. **The resting value of `LastUpdateRotation`/`LastUpdateLocation` on this build.** I rely on
   "`UObject` allocations are zero-filled" `[I, strong]`. I did **not** verify that the CMC
   constructor or the CDO leaves them zero. **One live read of `CMC+0x340..0x37F` on ANY CMC in the
   world settles it** — and the brief already notes 37 CMCs exist, so a population read gives both
   the default and the treated value in one pass.
2. **Whether any non-virtual CMC method or external code writes `+0x703`, `+0x360`, `+0x340`,
   `+0x390` or `+0x3DC`.** My sweep is the virtual surface only. An exhaustive image-wide census was
   NOT run; a disp32 byte scan would desync (brief trap #3) and I declined to use one.
3. **What `0x035EB6CF test rax,rax` is testing** — I traced `rax = [rbx+0xd0] = UpdatedComponent`
   (set at `0x035EB626`), which is measured non-null, so rung 3 should pass; but I did not
   exhaustively verify no intervening write to `rax` on every path into `0x035EB6CF`.
   `[I, strong]` not `[M]`.
4. **The identity of vslot 345 (`0x055C1140` → engine `~0x035FC700`) and vslot 336 (`0x035D2E90`).**
   I characterised them by their store sets (both write the full `LastUpdate*` cluster; 336 also
   writes `+0x3DC`, `+0x328`, `+0x3D0`) and concluded "proxy / client-correction". The names
   `SimulateMovement` / a client-adjust function are `[I]`, not `[M]`.
5. **Nothing here explains WHY `StartNewPhysics` is not entered.** This lane produces the
   instrument, not the answer. If the live read comes back "`+0x703 == 1`, `LastUpdateRotation ==
   (0,0,0,0)`", the wall is provably between `0x035EB130` and the latch write at `0x055C2469`, which
   is 10 bytes of dispatch plus `ULokiCMC::StartNewPhysics`'s first three instructions — and rung 6
   (the `+0x3DC` poke) narrows it further with a single external write.

---

## 7. FILES WRITTEN

```
scratchpad/s140/tools/thistrack.py       must-analysis this-tracker (9 controls, all pass)
scratchpad/s140/tools/l3_stores.py       v1 store enumerator + dominators
scratchpad/s140/tools/l3_stores2.py      v2 (access-flag) -- KEPT because its DISAGREEMENT with v1
                                         is what exposed the capstone movups defect
scratchpad/s140/tools/l3_ladder.py       v1 ladder (its path conditions are WRONG, see 1.3)
scratchpad/s140/tools/l3_ladder2.py      final ladder: corrected path conditions + post-dominance
scratchpad/s140/tools/l3_fieldwriters.py 413-slot vtable sweep for other writers
scratchpad/s140/tools/uht_offset.py      UHT FPropertyParams offset oracle
scratchpad/s140/tools/uht_bools.py       UHT FBoolPropertyParams -> (offset, mask) via SetBitFunc
```
All read-only; none touches a live process.
