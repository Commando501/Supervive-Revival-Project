# S140 TIER 1 — SOUND CFG ANALYSIS OF THE PHYSICS-STEP WALL

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game.**
Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, RVA == file offset.
Six analysis lanes + six adversarial verifiers, then adjudicated against the bytes with a
**from-scratch** PE reader and recursive-descent CFG (`scratchpad/s140/syn/adj.py` … `adj9.py` — a
third instrument, importing neither `scratchpad/s140/tools/peimg.py` nor `tools/cfg.py`).

---

## HEADLINE, BEFORE ANYTHING ELSE

**The six exits survive, exactly and completely. And it does not matter, because the instrument
that produced the question is invalid.**

`CMC+0x16C8` is **not** a sticky "StartNewPhysics ever reached" latch. It is a within-call
`TOptional<FVector>` validity flag: `ULokiCMC::StartNewPhysics` **sets** it at `0x055C2469`, and
**`ULokiCMC` vtable slot disp `0xA50` (`0x0530ABF0`) clears it** when engine `PerformMovement`
calls that slot at `0x035EB569` — **later in the same call, on a path the StartNewPhysics call
site dominates.** An off-thread reader therefore sees `0` between frames whether the physics step
runs perfectly every frame or never runs at all.

⇒ **S139's [M] "`ULokiCMC::StartNewPhysics 0x055C2430` HAS NEVER RUN ON EITHER COMPONENT" must be
retracted to UNINTERPRETABLE**, together with everything derived from it. **The contradiction
S140 was convened to resolve does not exist.**

### Adjudicator's controls (run before any analysis, my own code)

| control | result |
|---|---|
| PE flat (all 10 sections `VirtualAddress == PointerToRawData`) | **True** |
| ImageBase from optional header | **`0x7FF608F40000`** |
| Known-DARK control `0x5A6AC40` page non-zero bytes | **0 / 4096** PASS |
| Five fold constants byte-exact (`c20000` / `33c0c3` / `32c0c3` / `b001c3` / `0f57c0c3`) | **5/5 PASS** |
| ULokiCMC vtable `.rdata 0x088F8570`, 8 known displacements | **8/8 PASS** |
| Engine CMC vtable `.rdata 0x07FBED58`, 6 known displacements | **6/6 PASS** |
| every function under analysis LIT (page non-zero 3454–3883) | PASS |

---

## 1. A1 — THE SOUND EXIT SET

### 1.1 The CFG, measured three times

| quantity | L1 | L2/L3/L4 | **adjudicator** |
|---|---|---|---|
| instructions | 1461 | 1461 | **1461** |
| calls (115 direct sites / 31 distinct targets / 33 indirect) | yes | yes | **yes** |
| **indirect jumps** | 0 | 0 | **0** |
| decode failures | 0 | 0 | **0** |
| `ret` instructions | 1 (`0x035EB1CA`) | 1 | **1** |
| span / covered / gaps | 6538 / 6538 / **0** | yes | **6538 / 6538 / 0** |
| `\|reach_backward(0x035EB13A)\|` | 1075 | 1075 | **1075** |

**[M] Zero indirect jumps and zero decode failures ⇒ the reachability result is EXACT, not a
floor.** Zero uncovered bytes in the whole 6538-byte span ⇒ no undecoded island where a missed
edge could hide.

### 1.2 The exit set

Edges `u → v` with `u ∈ R`, `u` not a `call`, `v ∉ R`, `v ≠ u`:

```
0x035e9f1f  0f 84 82 12 00 00   je  0x35eb1a7   FORWARD
0x035e9f28  0f 84 79 12 00 00   je  0x35eb1a7   FORWARD
0x035e9f97  0f 84 32 18 00 00   je  0x35eb7cf   FORWARD
0x035e9fa4  0f 85 25 18 00 00   jne 0x35eb7cf   FORWARD
0x035e9fbd  0f 85 0c 18 00 00   jne 0x35eb7cf   FORWARD
0x035ea25d  0f 84 ed 0e 00 00   je  0x35eb150   FORWARD
                                          total: 6
```

**[M] THE SIX SURVIVES, EXACTLY. Nothing added, nothing subtracted, and none of the six is a false
exit.** Supporting facts, all re-derived by me:

- **Nodes in `R` with no successors: ZERO.** (An unlisted "exit" could otherwise hide as a
  dead-ended node.)
- **Backward edges in the entire function: exactly 2** — `0x035EB845 → 0x035EB197` and
  `0x035EB7CA → 0x035EB15C` — and **neither is in `R`**. ⇒ **there is no backward bail.**
  The `target > call` predicate S139 flagged as "structurally blind to backward bails" happened to
  be correct here. That is now **measured**, not assumed. [M]
- The lead's 7th edge `0x035EB13A → 0x035EB140` is confirmed an artifact of admitting the call
  node's own fallthrough: `0x035EB140 ∉ R`. [M]
- **`0x035EB13A` is not in a loop** — it is not reachable from `0x035EB140`. At most one
  `StartNewPhysics` call per `PerformMovement`. [M]

### 1.3 Dominance — **only FIVE of the six are mandatory**

Computed by **node removal** (ban the node, ask whether the call is still reachable from the entry)
— a different algorithm from L1's and L3's iterative dominators, and it agrees with both:

```
gate 0x035e9f1f dominates the SNP call: True
gate 0x035e9f28 dominates the SNP call: True
gate 0x035e9f97 dominates the SNP call: True
gate 0x035e9fa4 dominates the SNP call: True
gate 0x035e9fbd dominates the SNP call: True
gate 0x035ea25d dominates the SNP call: FALSE
```

**[M]** Exit 6 sits inside the root-motion block and is optional; it is also *redundant* — its
predicate is the same `HasValidData()` that exit 1 already dominates. `|Dom(call)| = 128`
instructions (L1, L3, verifiers all agree).

### 1.4 Noreturn and loops

- **31/31 distinct direct call targets in the function are REAL (0 FOLD, 0 DARK) and every one
  contains a `ret`.** [M — L1, reproduced by its verifier.] `0x037E6B70` (0 rets) adjudicated by
  reading it: `0x037E81AF 48 ff 60 38 jmp [rax+0x38]` after `mov rsp,r11 / pop rbp` is a tail
  call, not a noreturn. `0x0751DEB0` is `__security_check_cookie` and its only site
  (`0x035EB1B1`) is not in `R`.
- **19 indirect call sites lie in `R`. L1 graded 11 of them and left 7 ungraded while writing
  `[M]`.** Its verifier closed them (all REAL, all return: `0x03603DF0`, `0x035E64C0`,
  `0x035D5620`, `0x035DCB00`, `0x055B1740`, and `[rcx+0x878]` resolving to a single target
  `0x03BAD240` across all 13 pawn-family vtables). **Verifier right, lane over-graded.** With that
  closed the claim is **[M, bounded]** — bounded only on a C++ throw, which a CFG cannot see and
  which is independently improbable here (the main image has an empty exception directory; the
  process survives).
- **No loop.** [M]

### 1.5 Per-exit table

`rbx = this` is exhaustive, not asserted: over all 1461 instructions there are exactly **two**
writers of `rbx` — `0x035E9EFD 48 8b d9 mov rbx,rcx` and the epilogue `0x035EB1C8 pop rbx`. [M]
`rcx = [rbx+0xD0]` at `0x035E9F2E`, and between there and `0x035E9FB5` there are **zero `rcx`
writers and zero `call` instructions** (so the ABI-clobber objection does not apply). [M]

| # | address | bails when | field @ offset, owning class | measured live? | provably same object? |
|---|---|---|---|---|---|
| 1 | `0x035E9F1F` | `!HasValidData()` | `UpdatedComponent @CMC+0xD0`; `CharacterOwner @CMC+0x198`; `RF_Garbage` = `CharacterOwner+0x0C` bit 30 | **YES** x3 (`s139-f1-BOT.txt` R4 / R4.byname / R4 RF_Garbage) | **YES [M]** |
| 2 | `0x035E9F28` | `GetWorld() == NULL` | `WorldPrivate @CMC+0xC0` | **NO — NEVER READ** (see §1.6) | YES [M] (structure) |
| 3 | `0x035E9F97` | `MovementMode == 0` | `MovementMode @CMC+0x231` | **YES** = 3 | **YES [M]** |
| 4 | `0x035E9FA4` | `Mobility != 2` | `Mobility @UpdatedComponent+0x1BB` | **YES** = 2 | **YES [M]** |
| 5 | `0x035E9FBD` | `IsSimulatingPhysics()` | `WeldParent @capsule+0x5F0`; `bSimulatePhysics = capsule+0x3F0+0x10` bit 0 | **YES** (NULL, 0 — S139 flight 3, with `bEnableGravity`=1 as the same-byte two-sided control) | **YES [M]** |
| 6 | `0x035EA25D` | `!HasValidData()` after `TickCharacterPose` | same three as #1 | YES x3; its *guards* not measured | YES [M]; **not a dominator** |

`HasValidData 0x035E64C0` transcribed in full (14 instructions, byte-exact):

```
4883b9d000000000  cmp qword [rcx+0xd0],0     ; UpdatedComponent
741b              je  0x35e64e5
488b8198010000    mov rax,[rcx+0x198]        ; CharacterOwner
4885c0            test rax,rax
740f              je  0x35e64e5
8b400c            mov eax,[rax+0xc]          ; ObjectFlags
c1e81e            shr eax,0x1e               ; bit 30 = RF_Garbage
f6d0 a801 7403    not al / test al,1 / je 0x35e64e5
b001 c3           mov al,1 ; ret
0x35e64e5: 32c0 c3   xor al,al ; ret
```

Exit 5's chain closed end to end, byte by byte:
`0x03C9B0B8 41 b0 01 mov r8b,1` (**`bGetWelded = TRUE`, set inside the callee, not at the call
site**) → `0x03C9B0BE ff 90 10 08 00 00 call [rax+0x810]` = `GetBodyInstance 0x03C91C60`
(`4584c0 740c 488b81f0050000 4885c0 7507 488d81f0030000 c3` — with `WeldParent == NULL` measured,
it returns `capsule+0x3F0`, the capsule's own `FBodyInstance`) → `0x01E2F946 f6 41 10 01
test byte [rcx+0x10],1` → `je 0x01E2F9B7` = `32 c0 … c3` = **returns false**. ⇒ the `jne` is not
taken. **The gate genuinely passes, and the tested byte is literally the byte the probe read.**

**⚠ ADJUDICATION — L2's "zero overrides" control for exit 5 was CIRCULAR and its verifier was
right.** L2 selected 90 `.rdata` vtables *because* they contain `0x03C9B0A0` at `+0x4C0`, then
reported that all 90 contain `0x03C9B0A0` at `+0x4C0`. A class that overrides
`IsSimulatingPhysics` cannot appear in that set by construction. I ran the non-circular inversion —
anchor on `GetBodyInstance 0x03C91C60` at `+0x810`, then *read* `+0x4C0`:

```
GetBodyInstance aligned .rdata occurrences: 90
distinct [vt+0x4C0] values over those:      {0x3c9b0a0: 90}
```

**Conclusion stands, on evidence that can fail.** Residual: a class overriding *both* is invisible
to both anchors.

### 1.6 ⚠ NEW — exit 2's input has NEVER been read live, and three documents imply it has

`CMC+0xC0 WorldPrivate` does **not** appear in `docs/s139-f1-BOT.txt`, `-BASELINE.txt`,
`-f2-BASELINE.txt` or any other S139 evidence file. The complete measured-field inventory across
all S139 flights is: `0x16C8, 0x16B0, 0x12B0, 0x418, 0x430, 0xD0, 0x1BB, 0x160, 0x72, 0x400,
0x2E9&4, 0x328, 0x3D0, 0x28C, 0xF00, 0xF08, 0xB59, 0x4B, 0x4A&2, 0x60, 0x231, 0xE8` plus the
capsule's `0x5F0` / `0x3F0` from flight 3. **`0xC0` is absent.**

L2's exit table records exit 2 as `measured: YES` — **that is wrong, and I could not find the
measurement it refers to.** It does not change the verdict (a null `WorldPrivate` on a component
whose `TickComponent` is demonstrably running is close to impossible), but it is an **[I]
laundered into an [M]** and it belongs on the fix list. Grade exit 2 **[I, strong]**, not `[M]`.

---

## 2. A2 — THE RANKED PROGRESS LADDER

### 2.1 Engine `PerformMovement 0x035E9EC0`

**[M] Only THREE stores to CMC fields dominate the `StartNewPhysics` call** (node-removal, mine;
matches L3's iterative dominators):

```
0x035e9f82  88 83 03 07 00 00        mov byte  [rbx+0x703], al       ; bTeleportedSinceLastUpdate [I]
0x035ea009  88 8b e9 02 00 00        mov byte  [rbx+0x2e9], cl       ; bForceNextFloorCheck bit 0x08 [M]
0x035eb130  44 89 bb dc 03 00 00     mov dword [rbx+0x3dc], r15d     ; NumJumpApexAttempts [I], r15d==0
```

Everything else pre-call is root-motion-gated and skipped wholesale by `0x035EA356 je 0x35EB112`.

Post-call rungs (all `rbx = this`, byte-exact):

```
0x035eb77d  f3 0f 11 83 90 03 00 00  movss  [rbx+0x390], xmm0   ServerLastTransformUpdateTimeStamp
0x035eb78d  0f 11 83 60 03 00 00     movups [rbx+0x360], xmm0   LastUpdateLocation
0x035eb798  0f 11 83 40 03 00 00     movups [rbx+0x340], xmm0   LastUpdateRotation (FQuat4d)
0x035eb7bb  0f 11 83 78 03 00 00     movups [rbx+0x378], xmm0   LastUpdateVelocity
```

All offsets [M] from the `UCharacterMovementComponent` UHT `PropPointers` table (L3 predicted six
of them from the disassembly *before* querying the table, and all six matched — a real
pre-registration).

**Post-dominance, my own run** (L3's prose and its address list disagreed; the address list was
right, and its verifier's D7 correction is upheld):

```
0x35eb520/52d/536/78d/798/7a2/7af/7bb/7c2  postdom(0x35EB1CB) = True
0x35eb77d                                   postdom(0x35EB1CB) = FALSE
every one of them                           postdom(0x35EB140) = False
```

Nothing post-dominates `0x035EB140` because of the seventh bail (§4.4).

| rank | field | offset / width | discriminating power | required baseline |
|---|---|---|---|---|
| 1 | **`LastUpdateRotation`** | `0x340`, 32 B | **WEAK — see the R1 correction below**; proves "completed **at least once**, at an unknown time" | **poked sentinel** |
| 2 | `LastUpdateLocation` | `0x360`, 24 B | WEAK, same reason | poked sentinel |
| 3 | `ServerLastTransformUpdateTimeStamp` | `0x390`, f32 | WEAK, same reason; also **does not post-dominate** | poked sentinel |
| 4 | `bTeleportedSinceLastUpdate` | `0x703`, 1 B | **USELESS on a stationary pawn** — it is `ComponentLocation != LastUpdateLocation`, so it reads **0** exactly when the pawn is not moving | — |
| 5 | `NumJumpApexAttempts` | `0x3DC`, 4 B | **USELESS bare** (writes const 0 into 0); **BEST poke target** — 1 other writer, proxy-only | poke `0xDEADBEEF`, re-read |
| 6 | `bForceNextFloorCheck` bit `0x08` | `0x2E9` | **USELESS** — the store is `old \| (IsMovingOnGround && bTeleported)`; an OR preserves a poked 1 either way; byte shared with 15 sites / 10 vtable slots | — |
| 7 | `LastUpdateVelocity` | `0x378` | USELESS **now** (copies `Velocity` = `(0,0,0)`); becomes usable once Velocity != 0 | — |
| 8 | `LastUpdateRequestedVelocity` / `bHasRequestedVelocity` | `0x598` / `0x554` bit 0 | USELESS (writes zero vector; clears an already-clear bit); 4 other writers | — |
| — | root-motion rows (`0xD88`, `0xF50`, `0xFC0`, `0xE8/F0/F8`) | | **UNREACHABLE in this state** — a null says nothing | — |

**⚠⚠ THE R1 CORRECTION — L3's headline bisector is UNSOUND, and its verifier was right.**
L3 offered a three-way, baseline-free bisector whose branch 2 read *"`+0x340` == the live component
quat ⇒ it COMPLETES."* **It does not.** I confirmed from the CFG that `+0x340`, `+0x360` and
`+0x390` are each written **exactly once** in the whole function and **never cleared**, and they
are written **to the component's current transform**. On a pawn that has not moved since *some
earlier* completion, a value written at spawn is **bit-identical** to one written this frame.
Worse, branch 1 inherits the flaw: if `PerformMovement` completed once and then stopped, then
`LastUpdateLocation == ComponentLocation`, so `al = 0` at `0x035E9F79` and **`+0x703` reads 0** —
the bisector falls through to branch 2 and reports **"it COMPLETES"**, the opposite of the truth.

⇒ **On a stationary pawn, no baseline-free rung in this function separates "completes every frame"
from "completed once and never again."** The ladder is usable **only with an externally poked
sentinel**, and `+0x3DC` is the right target.

### 2.2 `ULokiCMC::PerformMovement 0x055B8370`

**[M] The Super call is UNCONDITIONAL.** My CFG: 322 insns / 29 calls / 0 indirect jumps / 0 decode
failures / 1 `ret` (`0x055B88DD`); coverage 1390/1390 bytes, 0 gaps.
`|reach_backward(0x055B85C1)| = 142`, **entry ∈ R**, **exits = [] (empty)**, **rets in R = []**,
and `0x055B85C1` **dominates** the sole `ret`. There is no early return.
`0x055B85C1 = e8 fa 18 03 fe`, rel32 `-33351430` → **`0x035E9EC0`** (machine-recomputed).

**[M] The two branches S139 nominated as "the next thing to read live" DO NOT GATE THE SUPER.**

```
0x055b845e  f6 80 80 05 00 00 08   test byte [rax+0x580], 8      ; ACharacter::bClientUpdating [M]
0x055b8465  0f 85 49 01 00 00      jne  0x55b85b4
0x055b846b  8b ae 88 19 00 00      mov  ebp,[rsi+0x1988]         ; TArray::Num @CMC+0x1980
0x055b8474  0f 88 3a 01 00 00      js   0x55b85b4
...
0x055b85b4  0f 28 ce               movaps xmm1,xmm6
0x055b85b7  c6 86 08 13 00 00 00   mov byte [rsi+0x1308], 0
0x055b85c1  e8 fa 18 03 fe         call 0x35e9ec0                 <-- THE SUPER
```

**Both branches jump INTO the Super call's own basic block.** They skip a 78-instruction latent-
action loop and nothing else. `0x055B85C1` is reachable from `0x055B85B4`: **True**.
`bClientUpdating` named [M] from its UHT `SetBitFunc` `0x0350C270 = 83 89 80 05 00 00 08 c3`, one
image-wide occurrence, `SizeOfOuter 0x7F0`, adjacent bits in stock `ACharacter.h` order.

**⇒ Reading either field answers nothing about whether the Super ran. S139's ranking is refuted
twice over.**

| rank | field | offset | power | baseline |
|---|---|---|---|---|
| 1 | **`+0x16D0`** (float, `= (float)World->TimeSeconds`) | `0x16D0` | **GOOD** — the only real post-Super receipt in this function | none, if compared to live `World->TimeSeconds` |
| 2 | `+0x12B0` `TimeSinceFallingStart` | `0x12B0` | GOOD but **pre-Super** — see §3 | already in use |
| — | `+0x1308` (`0x055B85B7`, 10 bytes before the Super, dominates) | `0x1308` | **USELESS AND A TRAP** — it writes **0**, the rest value | — |
| — | `+0x12E8`, `+0x1310`, the 3 loop stores | | USELESS (conditional and/or write 0) | — |
| — | `+0x12F0` / `+0x1300` (24 B) | | USELESS in this state — skipped when `Velocity == (0,0,0)` | — |

The receipt, byte-exact and with its guard:

```
0x055b8865  f2 0f 10 86 28 03 00 00  movsd  xmm0,[rsi+0x328]      ; Acceleration.X
0x055b886d  f2 0f 10 0d cb 5b 0e 02  movsd  xmm1,[rip+...]        ; 0x0769E440 = 0x7fffffffffffffff (abs mask)
0x055b8875  f2 0f 10 15 6b c1 0f 02  movsd  xmm2,[rip+...]        ; 0x076B49E8 = 9.999999747378752e-05
0x055b887d  0f 54 c1                 andps  xmm0,xmm1
0x055b8880  66 0f 2f c2              comisd xmm0,xmm2
0x055b8889  77 22                    ja     0x55b88ad             ; |Accel.X| > 1e-4 -> WRITE
0x055b888b  ... [rsi+0x330] ...      ja     0x55b88ad             ; |Accel.Y| > 1e-4 -> WRITE
0x055b88bc  e8 7f 73 ff fd           call   0x35afc40             ; GetWorld
0x055b88c1  f2 0f 10 80 08 08 00 00  movsd  xmm0,[rax+0x808]      ; UWorld::TimeSeconds  [M by name]
0x055b88c9  66 0f 5a c0              cvtpd2ps xmm0,xmm0
0x055b88cd  f3 0f 11 86 d0 16 00 00  movss  [rsi+0x16d0],xmm0     ; *** THE RECEIPT ***
0x055b88dd  c3                       ret
```

`UWorld::TimeSeconds @+0x808` is **[M] by name**, not by sibling analogy: the `.data`
`{name, thunk, impl}` triples give `GetTimeSeconds → 0x37DB150 (+0x808)`,
`GetUnpausedTimeSeconds → 0x37DB250 (+0x810)`, `GetRealTimeSeconds → 0x37D9840 (+0x818)`,
`GetAudioTimeSeconds → 0x37D6600 (+0x820)`.

My CFG: `Super dominates 0x055B88CD: True`; `reach_backward(0x055B88CD)` has exactly two exit
edges, both the Acceleration guard. ⇒ **`+0x16D0` tracking `World->TimeSeconds` proves the Super
was CALLED AND RETURNED, on a component whose `Acceleration` is non-zero.**

**⚠ SCOPE, and L4 over-claimed here.** The untreated player's silence on `+0x16D0` is **not** a
"free within-run specificity control" for the receipt's semantics — it is consistent both with
"the Super did not return" and with "`|Acceleration| <= 1e-4`". **The receipt is unusable on any
untreated component**, i.e. on the player and on all 37 CMCs. It works **only on a GAS-treated
bot**, which S139 flight 4 showed reaches `Acceleration = input x 50000`. Verifier D3 upheld.

**⚠ No store in either function separates "the Super was entered" from "the Super bailed early".**
Every store is strictly upstream of the call (blind to the callee) or strictly downstream
(requires the callee to have *returned*). That decomposition needs §5's poke.

---

## 3. A3 — THE `+0x12B0` WRITER SET

**[M] The field is `ULokiCharacterMovementComponent::TimeSinceFallingStart`, a reflected `float`
UPROPERTY at offset `0x12B0`, not `CPF_Net`.** Read from the UHT record, not inferred: ASCII
`TimeSinceFallingStart` occurs **exactly once** in `.rdata` (`0x088F65D8`); exactly one aligned
pointer to it (`0x088F2CB0`); that record reads

```
0x088f2cb0:  d8 65 83 11 f6 7f 00 00   NameUTF8 -> 0x7ff6118365d8 = RVA 0x088F65D8
             00 00 00 00 00 00 00 00
             00 20 00 00 00 00 10 00   PropertyFlags = 0x0010000000002000  (CPF_Net 0x20 CLEAR)
             0a 00 00 00 45 00 00 00   gen 0x0A = Float
             ...
             01 00 b0 12 00 00 00 00   ArrayDim = 1,  Offset = 0x12B0
```

My independent displacement census over `.text` returns **59 byte candidates** for `b0 12 00 00`
(L5: 59) and **exactly 9 instructions in the Loki-CMC band** — 5 writers + 4 readers:

| id | site | bytes | instruction | containing function | writes | grade |
|---|---|---|---|---|---|---|
| **A** | `0x055B8414` | `f30f1186b0120000` | `movss [rsi+0x12b0],xmm0` | `ULokiCMC::PerformMovement 0x055B8370` (vt disp `0xAA8`) | `+= DeltaSeconds` | **[M] runs every frame** |
| **B** | `0x055C248B` | `f30f1181b0120000` | `movss [rcx+0x12b0],xmm0` | `ULokiCMC::StartNewPhysics 0x055C2430` (disp `0x720`) | `+= deltaTime`, only when `Iterations > 0 && MovementMode == 3` | **[I, strong] has not fired** |
| **C** | `0x055A74D6` | `f30f11b6b0120000` | `movss [rsi+0x12b0],xmm6` | `FSavedMove_Loki*::CombineWith 0x055A7440` (SavedMove vt slot 8) | `= OldMove[+0x67C]` (restore) | **[I, strong] unreachable** at `Role == 3` |
| **D** | `0x055B7CCD` | `89abb0120000` | `mov [rbx+0x12b0],ebp` (`ebp = 0`) | `ULokiCMC::OnMovementModeChanged 0x055B7BF0` (disp `0x678`) | **`= 0.0f`** on entering `MOVE_Falling` | **[M] can run, writes 0** |
| **E** | `0x055BDD22` | `8986b0120000` | `mov [rsi+0x12b0],eax` | `FSavedMove_Loki*::PrepMoveFor 0x055BDCB0` (slot 9) | `= SavedMove[+0x67C]` | **[I, strong] unreachable** |

Readers: `0x055B840C` and `0x055C2483` (A's and B's own RMW loads), `0x055A56F8`
(`comiss xmm0,[rbx+0x12b0]` — a coyote-time predicate), `0x055C0A50`
(`FSavedMove_Loki*::SetInitialPosition`, the save direction).

`ebp == 0` at writer D is not an assertion: `0x055B7C93 xor ebp,ebp` is a **graph dominator** of
`0x055B7CCD` (banning it disconnects the entry). [M]

Reachability of C/E: engine `ControlledCharacterMove 0x035DCD10` reads `Role @+0x160`, and at
`Role == 3` (measured) `0x035DCDB2 jmp 0x35DCDDC` **unconditionally skips** the entire
`AutonomousProxy` / `GetNetMode` / `ReplicateMoveToServer` block. [M from bytes; the [I] is only
that virtual dispatch defeats an exhaustive caller enumeration.]

### 3.1 What an advancing `+0x12B0` DOES prove

**Exactly one thing: `ULokiCMC::PerformMovement (0x055B8370)` was entered repeatedly with a
non-zero DeltaSeconds and without HitStop firing.** The store is instruction 44, on a path from
the entry with **no exit at all**, **strictly upstream of the Super at `0x055B85C1`**.

It additionally proves, weakly: no `MOVE_Falling` transition occurred during the sample (D would
have zeroed it), and no network correction landed (C/E would have assigned a saved value).

### 3.2 What it does NOT prove — and one sentence in L5 that must be deleted

It says **nothing** about whether the Super was reached, how far engine `PerformMovement` got,
whether `StartNewPhysics` ran, or whether the pawn simulates. S139's own retraction
(`docs/s139-flight2-gate-refuted.md` §3) already said this and it stands.

**⚠ L5's §6 contains the sentence *"the latch `+0x16C8` reads 0 on every CMC in the world, so
`StartNewPhysics` was never entered at all."* DELETE IT.** Its verifier was right on both counts:
(a) §4 below kills the inference outright; (b) L5 cited `latch == 0 [M banked]` from
`docs/s139-f1-BOT.txt` — a file whose own verdict line, eleven lines below the number, reads

> `!! CONTROL FAILED: the PLAYER's latch reads 0, expected 1. … THE BISECTOR IS UNINTERPRETABLE
> THIS SITTING.`

**A sample cited past its own verdict.** Rare failure mode, worth recording alongside the
"verdict contradicted by its samples" one.

**The 1.0x rate survives, with the correct scope.** Bot `33.1357 → 43.3361` over 10.2 s = 1.00004x;
player `380.343 → 390.541` = 0.99980x. That bounds any writer-B contribution to **< 5e-5 s over
10.2 s** — so **writer B did not fire**. But `Iterations == 0` on the `PerformMovement` call path
never reaches `0x055C2483` at all, **so the rate does not exclude `StartNewPhysics` running.**
Quote the numbers, not "exactly 1.0x".

---

## 4. A4 — LATCH VALIDITY: **`latch == 0 ⇒ StartNewPhysics never ran` IS NOT SOUND**

### 4.1 The vtable disp-`0x720` re-derivation, with controls

```
.rdata 0x088F8570 (ULokiCMC vtable)              .rdata 0x07FBED58 (engine UCMC vtable)
  +0xAA8 -> 0x00007ff60e4f8370 = 0x055B8370 PASS   +0xAA8 -> 0x035E9EC0 PASS
  +0x720 -> 0x00007ff60e502430 = 0x055C2430 PASS   +0x720 -> 0x03600990 PASS
  +0x3D0 -> 0x055C2B90 PASS                        +0x890 -> 0x035DCD10 PASS
  +0x890 -> 0x055A7680 PASS                        +0x6B8 -> 0x035E64C0 PASS
  +0xA38 -> 0x055A75B0 PASS                        +0x4E0 -> 0x0364BA80 PASS
  +0x830 -> 0x055B89F0 PASS                        +0xA50 -> 0x035D6790 PASS
  +0x6B8 -> 0x035E64C0 PASS
  +0xA50 -> 0x00007ff60e24abf0 = 0x0530ABF0     <-- THE ANSWER
```

**14 positive controls, 14 PASS**, across two vtables — including a two-sided control the lanes
mostly missed: the **engine sibling vtable carries the engine bodies at the same displacements**,
which is far stronger than one-sided agreement.

**No subclass vtable exists.** Aligned 8-byte pointers to each function, image-wide:

```
0x055C2430 (LokiSNP)  : 1  at 0x088F8C90 = LokiVT + 0x720
0x0530ABF0 (A50 clr)  : 1  at 0x088F8FC0 = LokiVT + 0xA50
0x055B8370 (LokiPM)   : 1  at 0x088F9018 = LokiVT + 0xAA8
0x03600990 (engSNP)   : 1  at 0x07FBF478 = EngVT  + 0x720
0x035E9EC0 (engPM)    : 1  at 0x07FBF800 = EngVT  + 0xAA8
```

⇒ no ICF folding, and no C++ subclass of `ULokiCMC` with its own vtable. [M]

### 4.2 The set

```
0x055c2430  0f28d1                   movaps xmm2, xmm1
0x055c2433  4585c0                   test   r8d, r8d              ; r8d = Iterations
0x055c2436  753d                     jne    0x55c2475
0x055c2438  443881c8160000           cmp    byte [rcx+0x16c8], r8b
0x055c243f  7407                     je     0x55c2448
0x055c2441  448881c8160000           mov    byte [rcx+0x16c8], r8b   ; TOptional::Reset()
0x055c2448  0f1081e8000000           movups xmm0, [rcx+0xe8]         ; Velocity
0x055c244f  0f1181b0160000           movups [rcx+0x16b0], xmm0       ; Emplace()
0x055c2456  f20f1089f8000000         movsd  xmm1, [rcx+0xf8]
0x055c245e  f20f1189c0160000         movsd  [rcx+0x16c0], xmm1
0x055c2469  c681c816000001           mov    byte [rcx+0x16c8], 1     ; *** SET ***
0x055c2470  e91be503fe               jmp    0x3600990                ; tail -> engine
```

`Iterations == 0` at the call is **[M], not assumed** — `0x035EB129 45 33 c0 xor r8d,r8d`, and
between there and `0x035EB13A` there are **zero r8 writers and zero calls**. (Neither the brief
nor three of the lanes stated this; it is the premise the whole latch story rests on.)

### 4.3 The clear — LF-13, re-derived independently

```
0x0530abf0  80b9c816000000   cmp  byte [rcx+0x16c8], 0
0x0530abf7  7407             je   0x530ac00
0x0530abf9  c681c816000000   mov  byte [rcx+0x16c8], 0     ; *** CLEARED ***
0x0530ac00  e98bbb2cfe       jmp  0x35d6790                ; tail -> Super (= EngVT+0xA50) [M]

engine PerformMovement:
0x035eb554  488b03           mov  rax,[rbx]                ; rbx = this (only 2 rbx writers, both accounted)
0x035eb566  488bcb           mov  rcx,rbx
0x035eb569  ff90500a0000     call [rax+0xa50]              ; -> 0x0530ABF0
```

My CFG, all five results:

```
SNP call DOMINATES the A50 call : True        (ban 0x035EB13A -> A50 unreachable from entry)
A50 dominates SNP               : False
A50 in fwd(SNP)                 : True        SNP in fwd(A50): False
A50 reachable from bail 0x035EB1A7 / 0x035EB7CF / 0x035EB150 : False / False / False
A50 postdominates 0x035EB1CB    : True        (ban it -> the ret is unreachable from 0x035EB1CB)
```

⇒ **[M] The flag is set by `StartNewPhysics` and cleared later in the SAME engine
`PerformMovement` call, and on the normal continue path the clear is UNAVOIDABLE.** An external
reader polling between frames observes `0` in **both** worlds.

**⚠ ADJUDICATION — L4's parenthetical is REFUTED and its verifier was right.** L4 wrote
*"nodes that can reach `0x035EB569` but not `0x035EB13A`: 202 (so it also runs when
StartNewPhysics is skipped)"*. The 202 are simply the nodes *between* the two calls; they cannot
reach the earlier one because there is no back edge. The set difference cannot support that
inference, and node-removal refutes it directly. **The truth is favourable: set and clear are
strictly paired.**

### 4.4 ⚠ THE SEVENTH BAIL — the one path that leaves the flag at 1

`reach_backward(0x035EB569)` has **seven** exit edges: the six, **plus**

```
0x035eb140  488b03           mov  rax,[rbx]
0x035eb146  ff90b8060000     call [rax+0x6b8]        ; HasValidData(), a SECOND time
0x035eb14c  84c0             test al,al
0x035eb14e  757b             jne  0x35eb1cb          ; continue
            (fallthrough)  -> 0x035EB150 = BAIL, and A50 is NOT reachable from it
```

This edge is **downstream of the set**, is not in `reach_backward(0x035EB13A)`, and appears in
**none** of: S139's six, the session lead's preview, L1, L2, L3, L6. Found by L4's verifier and by
L6 independently. It is the only way `+0x16C8` survives a frame at `1`, and it belongs in any
interpretation table.

### 4.5 The field's real semantics — from its own consumers

Naming is **[M]**: `.data 0x09BC9AD0 = { name → "GetRecentVelocity", thunk 0x0530C7E0,
impl 0x0530AC10 }`, with the passing control `.data 0x09BC4B60 = { "GetLokiCharacterMovement",
0x05300710, impl 0x055AC8E0 }` (the impl matching the address already recorded in the repo).

```
0x0530ac10  80b9c816000000   cmp   byte [rcx+0x16c8], 0
0x0530ac17  b8b0160000       mov   eax, 0x16b0            ; the snapshot
0x0530ac1c  41b8e8000000     mov   r8d, 0xe8              ; Velocity
0x0530ac22  410f44c0         cmove eax, r8d               ; flag==0 -> Velocity ; flag!=0 -> snapshot
0x0530ac26  0f100408         movups xmm0,[rax+rcx]
```

Same idiom at `0x0530C7FF` (the UHT exec thunk, i.e. the reflected surface) and `0x0559C59E`.
⇒ **[M] `CMC+0x16C8` is a per-frame `TOptional<FVector>` validity flag over the pre-step Velocity
snapshot at `+0x16B0`. It is an in-progress flag by its own readers, not a sticky latch.**
It is **not a reflected UPROPERTY** (absent from the 219-record `ULokiCMC` `PropPointers` table;
it sits between `CurrentForces@0x16A0` and `LastAccelerationTime@0x16D0`). [M]

### 4.6 The complete CMC-side writer set

**⚠ Two lanes disagreed about a constructor and I settled it from the vtable install.** L4 graded
`0x0559EA48` as *"ctor-shaped … [I, strong] the `ULokiCMC` ctor"*; L6 named `0x0559F580`. **L4 was
wrong; L6 and L4's verifier were right:**

```
fn 0x0559E180: 0x0559e1dc lea rax,[rip -> .rdata 0x088E5CA8] ; 0x0559e1e6 mov [r14], rax
               vt 0x088E5CA8 + 0x8C0 -> 0x03BBF3C0 = APawn::SpawnDefaultController   <-- A PAWN VTABLE
               vt 0x088E5CA8 + 0xC00 -> 0x055AC9F0
fn 0x0559F580: 0x0559f5ac lea rax,[rip -> .rdata 0x088F8570] ; mov [rdi], rax        <-- THE ULokiCMC VTABLE
```

⇒ `0x0559EA48` (`mov word [r14+0x16c8], bp`) and `0x0559EA2F` (`movups [r14+0x16b0], xmm0`) are
**`ALokiCharacter`** writes. This matters: it means **nothing writes `CMC+0x16B0` except
`0x055C244F` inside `StartNewPhysics`**, which is what makes the *payload* a usable receipt (§5).

| site | instruction | owner | role |
|---|---|---|---|
| `0x055C2441` | `mov byte [rcx+0x16c8], r8b` (0) | CMC | `TOptional::Reset()` inside SNP |
| `0x055C2469` | `mov byte [rcx+0x16c8], 1` | CMC | **the set** |
| `0x0530ABF9` | `mov byte [rcx+0x16c8], 0` | CMC | **the per-frame clear** (vt disp `0xA50`) |
| `0x0530AB4C` | `mov byte [rbx+0x16c8], 0` | CMC | destructor (vt slot 0; `mov edx,0x19D0` = `sizeof`) |
| `0x0559FDF4` | `mov byte [rdi+0x16c8], sil` | CMC | **constructor** (`0x0559F580`, installs `0x088F8570`) |

**⚠⚠ THE OFFSET COLLISION IS REAL AND IT NEARLY CAUGHT TWO LANES.** `+0x16C8` and `+0x16D0` exist
on **both** `ULokiCMC` **and** `ALokiCharacter`. `0x055B860B mov byte [r15+0x16c8], 0` sits
*inside* `ULokiCMC::PerformMovement` and looks like a third clearer. It is not: `r15` has exactly
two writers in that function — `0x055B8381 4c 8b b9 98 01 00 00 mov r15,[rcx+0x198]`
(`CharacterOwner`) and `0x055B83A6 xor r15d,r15d`. Same for `0x055A6BCB` (whose *containing
function is itself a `ULokiCMC` vtable slot*, disp `0xBE0`) and `0x055C0DA9`.
**A base-register name is not provenance.** Resolve every hit.

### 4.7 Verdict

**`latch == 0` proves NOTHING. The inference is UNSOUND.** [M]
Reading `0` is the expected steady-state observation under all three of:
never ran · bailed at one of the six · ran to completion and was cleared.
Only the seventh bail (§4.4) leaves it at `1`.

---

## 5. WHAT THIS MEANS FOR THE CONTRADICTION

## **THE CONTRADICTION DISSOLVES. There was no seventh exit — there was an invalid instrument.**

S139 recorded: *"six engine exits, all measured passing, and `StartNewPhysics` still never runs …
Something bails for a reason none of the six accounts for, or a seventh path exists."* Both horns
are dead:

- **The six is complete and exact** (§1) — 0 indirect jumps, 0 decode failures, 0 coverage gaps,
  0 backward bails, 0 dead-ended nodes in `R`. There is no seventh path.
- **All five *mandatory* gates pass, on provably the same objects the probes read** (§1.5), with
  exit 2's input the one genuine unmeasured term.
- **And "`StartNewPhysics` never runs" was never measured.** The one observation supporting it —
  `+0x16C8 == 0` — reads 0 in both worlds, and the evidence file that produced it declared itself
  uninterpretable at the time.

⇒ **The most likely state of the world is now the simple one: `ULokiCMC::PerformMovement` runs,
reaches its Super unconditionally, engine `PerformMovement` passes all five gates, and
`StartNewPhysics` runs every frame — and something DOWNSTREAM of it fails to produce Velocity.**
The measurements that remain solid say exactly this: `Acceleration = ControlInputVector x 50000`
(S139 flight 4, 20 samples, ratio mean 49999.63, with the untreated player non-zero in 0 of 20),
`Velocity == (0,0,0)`, translation `0.00 uu`.

### The single best next move

**Poke `CMC+0x16B0..0x16C7` (the Velocity snapshot) with a sentinel and re-read it a few frames
later.** This is the one durable readout in the whole structure:

- **[M] the payload is durable.** The A50 override clears only the flag byte, never the payload. My
  own independent `+0x16B0` displacement census confirms the **only** CMC-side writer is
  `0x055C244F` inside `StartNewPhysics` (§4.6 removes the false second one).
- **[M] the payload write is on the same `Iterations == 0` path as the set**, 0x1A bytes before it.
- **Decision rule:** write `(0.0009765625, 0, 0)` (exactly representable, physically inert) to
  `CMC+0xE8/F0/F8`. Wait >= 3 frames.
  - `+0x16B0` holds the sentinel ⇒ **`StartNewPhysics` ran with `Iterations == 0`** [M].
  - `+0x16B0` still `(0,0,0)` **while `+0xE8` still holds the sentinel** ⇒ it did not run [M].
  - `+0xE8` no longer holds the sentinel ⇒ the probe's own control failed; the run is void.
- ⚠ **Do not use `(1234.5, 6789.25, -4242.125)`** as L6 proposed — that is ~8,000 uu/s; if the
  physics step *is* running it launches the pawn and perturbs the system under test.
- ⚠ **The write-free alternative is DEAD and should be foreclosed explicitly:** `GetRecentVelocity`
  is a reflected UFunction (thunk `0x0530C7E0`), so the S55 primitive could call it with zero
  writes — but with `Velocity == (0,0,0)` **both arms of its `cmove` return `(0,0,0)`.** It cannot
  discriminate. Nobody should spend a flight on it.
- ⚠ **External `WriteProcessMemory` is a repo-recorded UNRESOLVED hazard** (S138, n=1, confounded
  by a very high FK-32 base rate). Pair with a matched no-write sitting.

### Ranked alternatives, if the poke is refused

| # | move | cost | what it settles |
|---|---|---|---|
| 2 | **Pin `LogCharacterMovement = Log` in the USER `Engine.ini`** and watch for `.rdata 0x07FC0670` *"UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is simulating physics - aborting."* | zero-risk, no injection, FK-11's proven channel | ⚠ **negative-only.** It fires only if `IsSimulatingPhysics()` is TRUE, which S139 measured FALSE. **Its silence is uninterpretable and it has no positive control.** Do it for the category, do not build on it. |
| 3 | Poke `CMC+0x3DC` (`NumJumpApexAttempts`) to `0xDEADBEEF`, re-read | one dword | separates "engine `PerformMovement` entered this frame" from "entered once, long ago" — ladder rung §2.1 rank 5 |
| 4 | Read `CMC+0xC0` (`WorldPrivate`) and `CMC+0x3E4` (`MaxSimulationIterations`) | free, add to any probe | closes exit 2's unmeasured term; `+0x3E4 <= 0` is a **fourth engine-`StartNewPhysics` early-out nobody had** (§7) |
| 5 | Move the investigation downstream to `PhysFalling` / `CalcVelocity` | offline, next session | if the poke shows `StartNewPhysics` runs, this is where the wall actually is. `ULokiCMC` vt disp `0x830 → 0x055B89F0` is a verified slot and its body opens `cmp byte [rcx+0x231], 7` |

---

## 6. CORRECTIONS TO `CLAUDE.md` AND `docs/s139-*.md`

### 6.1 `CLAUDE.md` ~line 1624 — the primary retraction

**STALE (verbatim):**
> ★★★★★ **[M] AND `ULokiCMC::StartNewPhysics 0x055C2430` HAS NEVER RUN ON EITHER COMPONENT.** Its
> latch is `0x055C2469 mov byte [rcx+0x16C8],1`, on the **unconditional fall-through** of the
> `Iterations==0` path (the `je` at `0x055C243F` skips only a redundant zero-store) — so `+0x16C8`
> is a valid sticky "ever reached" instrument, and it reads **0** on both.

**REPLACEMENT:**
> ⚠⚠⚠ **RETRACTED (S140, 2026-08-23) — `+0x16C8` IS NOT A STICKY LATCH AND `latch == 0` IS
> UNINTERPRETABLE.** [M] `ULokiCMC` vtable disp `0xA50` = **`0x0530ABF0`**
> (`80b9c816000000 / 7407 / c681c816000000 / e98bbb2cfe`) **CLEARS** the byte, and engine
> `PerformMovement` calls that slot at `0x035EB569 ff90500a0000 call [rax+0xa50]` with
> `rcx = rbx = this` — **later in the same call, on a path the `StartNewPhysics` call site
> DOMINATES**, and the clear POST-DOMINATES `0x035EB1CB`. ⇒ an off-thread read sees `0` whether
> the step runs every frame or never. **[M] The field is a per-frame `TOptional<FVector>` validity
> flag over the Velocity snapshot at `+0x16B0`** — read out by `ULokiCMC::GetRecentVelocity`
> (`.data 0x09BC9AD0 → impl 0x0530AC10`): `cmp byte [rcx+0x16c8],0 / mov eax,0x16b0 /
> mov r8d,0xe8 / cmove eax,r8d`. ★ **The DURABLE readout is the PAYLOAD `+0x16B0`, whose only
> CMC-side writer is `0x055C244F` inside `StartNewPhysics`.** ⚠ Only the **seventh bail**
> `0x035EB14E jne 0x35EB1CB` (a SECOND `HasValidData` at `0x035EB146`, fallthrough to
> `0x035EB150`) leaves the byte at 1. Read `docs/s140-tier1-cfg.md` §4.

### 6.2 `CLAUDE.md` ~line 1632 — the derived gravity claim

**STALE:** *"It also explains with no extra assumption why a `MOVE_Falling` pawn with
`GravityScale 1.000` does not fall: **`PhysFalling` is dispatched FROM `StartNewPhysics`.**"*
**REPLACEMENT:** ⚠ **VOID (S140)** — it rested on the latch. `PhysFalling` really is dispatched
from `StartNewPhysics`, but nothing shows `StartNewPhysics` does not run.

### 6.3 `CLAUDE.md` ~line 1656 — the population control

**STALE:** *"★ **POPULATION CONTROL: 37 movement components live, EVERY latch `+0x16C8` = 0, and
exactly ONE is doing anything at all.** ⇒ **there is no moving character anywhere in this world to
diff against.**"*
**REPLACEMENT:** ⚠ **The latch half is VOID (S140): 37/37 zeros is equally expected under both
readings, so it never discriminated.** What survives is the *other* column of the same sweep —
36 of 37 read `TimeSinceFallingStart 0.000` and `MovementMode 0 (MOVE_None)`, i.e. pooled and
inert. "No moving character to diff against" stands on that, not on the latch.

### 6.4 `CLAUDE.md` ~line 1719 and ~line 1732 — the contradiction and the residual

**STALE (1719):** *"yet `StartNewPhysics` is never entered while all six enumerated exits read
passing. **Something bails for a reason none of the six accounts for**, or a seventh path exists
that the CFG walk's `target > call` predicate cannot see"*

**STALE (1732):** *"⚠⚠ **RESIDUAL, AND DO NOT ASSUME THE PORT CLOSES IT: `StartNewPhysics` is
STILL never entered** (latch 0 on the bot, the player, and **all 37** movement components …)"*

**REPLACEMENT for both:**
> ⚠⚠⚠ **THE CONTRADICTION DISSOLVED (S140).** [M] **The six is COMPLETE and EXACT** — an
> independent recursive-descent CFG over 1461 instructions finds **0 indirect jumps, 0 decode
> failures, 0 coverage gaps (6538/6538 bytes), exactly 2 backward edges and NEITHER in `R`, and
> 0 dead-ended nodes in `R`.** There is no seventh path and no backward bail. **Five of the six
> DOMINATE the call; `0x035EA25D` does not.** What was wrong was the instrument, not the
> enumeration — see the retraction above. **"`StartNewPhysics` is never entered" is now UNGRADED,
> not `[M]`.**

### 6.5 `CLAUDE.md` ~line 1527 — the instrument description that started it

**STALE:** *"led by **`CMC+0x16C8`** — `ULokiCMC::StartNewPhysics`'s **dt-INDEPENDENT**
"PerformMovement reached me" latch (`mov byte [rcx+0x16C8],1` at `0x055C2469`, no DeltaTime test
above it; the engine's MIN_TICK_TIME bail is downstream) … `1` + frozen ⇒ the DeltaTime kill;
`0` ⇒ an early-out at or above `PerformMovement`."*
**REPLACEMENT:** ⚠ **The `0` branch is FALSE (S140): `0` is the resting value in every world.**
The `1` branch is still sound — a sampled `1` means "inside `PerformMovement` right now, past
`StartNewPhysics`" — but polling for it is hopeless. **Use the payload `+0x16B0` with a poked
sentinel instead.**

### 6.6 `CLAUDE.md` ~line 4205 — the S140 handoff pointer, wrong in two ways

**STALE:** *"the third — **`UpdatedComponent->IsSimulatingPhysics()` at `0x035E9FB5`/
`jne 0x035EB7CF`** — has never been read. **That one read is the whole next session.**"*
**REPLACEMENT:** ⚠ **Wrong twice.** (a) It **has** been read — S139 flight 3 measured
`WeldParent @capsule+0x5F0 == NULL` and `bSimulatePhysics == 0` (with `bEnableGravity == 1` as the
same-byte two-sided control), and `docs/next-session-prompt-s140.md` §0b itself says *"ASKED AND
ANSWERED … REFUTED"*. S140 closed the chain to the byte:
`0x03C9B0B8 mov r8b,1 → call [vt+0x810] GetBodyInstance 0x03C91C60 → 0x01E2F946
test byte [rcx+0x10],1 → je 0x01E2F9B7 = xor al,al; ret`. **The gate passes.**
(b) It says *"three gates"*; the measured count is **five mandatory plus a non-mandatory sixth**.
This is a digest-is-an-instrument instance: the settled S139 docs were right and the digest line
was stale.

### 6.7 `docs/s139-flight2-gate-refuted.md` — three lines

- `:58` *"**Every one reads `+0x16C8 == 0`.** ⇒ `ULokiCMC::StartNewPhysics` has never run for any
  character in this world."* → **retract the `⇒`**; keep the measurement.
- `:146` grade row *"`ULokiCMC::StartNewPhysics` has never run, for any of 37 components |
  **[M]** — the latch write at `0x055C2469` is on the unconditional fall-through"* →
  **`[M]` → UNGRADED (instrument invalid).** The *write* really is on the unconditional
  fall-through; that was never the problem. The problem is the clear, which was never sought.
- `:156` *"**six exits, all measured passing, and `StartNewPhysics` still never runs.** One of the
  six readings must be measuring something other than what its branch tests."* → **REFUTED.** The
  six readings are fine (bar exit 2, unmeasured); the *seventh* reading — the latch — was the bad
  one. Add a banner.

### 6.8 `docs/s139-flight1-the-bot-is-not-special.md` `:128–:135`

**STALE:** *"★★ **RESOLVED AFTER THE FLIGHT, FROM THE BYTES — (b) IS REFUTED AND THE LATCH IS A
VALID INSTRUMENT**"*
**REPLACEMENT:** ⚠ **HALF-RESOLVED, AND THE VERDICT IS WRONG (S140).** Reading (b) was stated as
*"the latch is never set on the normal path"* and correctly refuted from `0x055C2433`–`0x055C2469`.
But refuting (b) does not establish validity — **a third reading was never enumerated: the latch is
set AND CLEARED within the same call.** That is the true one. ★ **The method lesson: refuting one
alternative is not the same as validating the instrument.** The file's own pre-registration (*"the
player's latch reads 0 ⇒ the bisector is UNINTERPRETABLE"*) was correct and should have been left
standing.

### 6.9 `docs/next-session-prompt-s140.md` `:243` and `:189`

- `:243` *"⚠ **`+0x16C8` is a STICKY "ever reached" latch, never cleared.** No per-frame rate from
  it."* → **FALSE. It is cleared, once per completed `PerformMovement`, at `0x0530ABF9` via
  `ULokiCMC` vtable disp `0xA50`.**
- `:189` *"the `StartNewPhysics` latch is set *before* the jump to the engine, so `latch == 0`
  proves it was never entered"* → **the first clause is true, the inference is false.**

### 6.10 Claims in the BRIEF itself that turned out wrong

Of the five pre-fan-out verified items, **items 1, 4 and 5 are confirmed byte-exact** (I re-derived
all three) and **item 3 is confirmed and was correctly labelled a preview**. Two problems:

- **Item 2's closing sentence is REFUTED:** *"It is therefore SOUND for 'did PerformMovement reach
  StartNewPhysics'."* It is not sound — and the very next sentence flags the clearer as an open
  question assigned to lane A4. **The brief graded a conclusion `SOUND` while simultaneously
  recording that its precondition was unchecked.** Same shape as the error it was investigating.
- The brief's key-address block lists `ShouldSkipUpdate 0x0364BA80 (disp 0x4E0)` among engine
  `PerformMovement`'s addresses. **It has ZERO call sites in that function** — a reader will look
  for it as an exit and not find one.
- The brief's `.rdata 0x07FC0670` and L2's `0x07FC0648` are **both right and not in conflict**:
  `u64(0x07FC0648) − ImageBase == 0x07FC0670`, i.e. the `FLogRecord` at `0x648` points at the wide
  format string at `0x670` (verified: *"UCharacterMovementComponent::StartNewPhysics:
  UpdateComponent (%s) is simulating physics - aborting."*). Worth one line so nobody "corrects" it.

### 6.11 Instrument defects found this session — all reproduce, all worth recording

1. **★★ capstone 5.0.7 reports `movups`/`movaps` STORE operand-0 access as `READ (1)`, not
   `WRITE (2)`.** Reproduced independently by two lanes and their verifiers, numerically to the
   unit: over engine `PerformMovement`, `mov` 50 / `movaps` 18 / `movsd` 30 / `movss` 1 all
   correctly WRITE, **`movups` 29 all WRONG**. An `access & CS_AC_WRITE` filter silently drops
   **16 real CMC-field stores including `LastUpdateLocation`, `LastUpdateRotation` and
   `LastUpdateVelocity`** — and also `StartNewPhysics`'s own `0x055C244F movups [rcx+0x16b0]`,
   which is the payload receipt this session now recommends. **Any lane filtering on
   `CS_AC_WRITE` in this project is blind to `movups`.** Fix: `access & WRITE OR mnemonic ∈
   {movups, movdqu, movnps, movntps, movntdq}`.
2. **`tools/strxref/index/pdata_union.csv` has NO row covering `0x055C2430`, `0x0530ABF0`,
   `0x0530AC10`, `0x0530C7E0`.** A pdata-anchored census alone **misses the `+0x12B0` writer B and
   the entire clear function.** This is the recorded size-1-placeholder blindness, reproduced live
   twice. Use the union of a pdata sweep and a **vtable** sweep.
3. **A raw-byte disp32 back-decode scan DESYNCS.** L4 reproduced trap #3 verbatim (emitting
   `0x055B88CF adc …` for the real `0x055B88CD movss …`) and correctly discarded it; a verifier hit
   the same class dropping a REX.B (`0x055B860C` for the real `0x055B860B`). **Multi-alignment
   probing plus operand adjudication is mandatory.**
4. **A "control" selected by the property it tests is not a control** — L2's exit-5 override check
   (§1.5). The inversion passes; publish the inversion.
5. **`obj+0x16C8` and `obj+0x16D0` exist on both `ULokiCMC` and `ALokiCharacter`.** Any
   displacement scan mixes two unrelated fields. **Resolve base-register provenance on every hit.**
6. **A sample can be cited past its own verdict** (§3.2). `docs/s139-f1-BOT.txt` prints
   `THE BISECTOR IS UNINTERPRETABLE THIS SITTING` eleven lines below the number that was later
   quoted as `[M] banked`. New variant of the "read the samples, not the verdict" rule: **read the
   verdict too, and check it says what you are about to claim.**

---

## 7. OPEN / NOT ESTABLISHED OFFLINE

Ranked by value. Every item names the exact live read.

| # | question | why it matters | the read | cost |
|---|---|---|---|---|
| 1 | **Does `StartNewPhysics` actually run?** | The entire S140/S139 framing. Offline work can only remove the evidence against; it supplies none for. | Poke `CMC+0xE8/F0/F8` = `(0.0009765625, 0, 0)`; wait >= 3 frames; read `CMC+0x16B0..0x16C7` and re-read `+0xE8` as the probe's own control. §5. | 1 WPM + 2 reads |
| 2 | **`CMC+0xC0 WorldPrivate`** | Exit 2's input, the ONE mandatory gate never read (§1.6). Three documents imply it was. | one qword | free — add to any probe |
| 3 | **`CMC+0x3E4 MaxSimulationIterations`** | A **FOURTH** engine-`StartNewPhysics` early-out present in no S140 document: `0x036009B5 44 3b 81 e4 03 00 00 cmp r8d,[rcx+0x3e4] / 0x036009BC 0f 8d 24 02 00 00 jge`. With `r8d == 0` it bails iff the field is `<= 0`. There is also a **THIRD** `HasValidData` at `0x036009C5`. | one dword | free |
| 4 | **Is the live component's vptr `ImageBase + 0x088F8570`?** | If it were a plain engine `UCharacterMovementComponent`, disp `0x720` → `0x03600990` and nothing would touch `+0x16C8` at all. §4.1 shows **no subclass vtable exists**, so the only live alternative is the engine base. Every banked S139 offset is valid on either class. | `*(uint64_t*)CMC` vs `ImageBase + 0x088F8570` | one qword |
| 5 | Does engine `PerformMovement` **reach its tail**, per frame? | Decomposes "the Super was entered" vs "it bailed early". No store answers it (§2.2). | Poke `CMC+0x3DC = 0xDEADBEEF`; re-read. Rung 5. | 1 WPM |
| 6 | Exit 6's guard inputs (`CMC+0xD58..0xD68`, `CharacterOwner+0x450`, `+0x580`) | Would move exit 6 from `[I, strong]` to `[M]`. | 5 fields | free — **and moot**, exit 6 is not a dominator |
| 7 | Whether a non-virtual / out-of-scope function writes `+0x12B0`, `+0x16C8` or `+0x16D0` | All censuses here are **FLOORS** — virtual surface + LIT pages only, blind to `memcpy`/`rep movs` and to register-computed addresses. | not settleable offline; live attribution by VALUE (`+0x16D0` must equal `World->TimeSeconds` within a tick) | — |
| 8 | Does any indirect spine callee **throw**? | CFG-undecidable. Excluded `[I, strong]`: empty exception directory on the main image; the process survives. | — | not settleable |
| 9 | Names for `0x055B1EC0` / `0x055AEB60` / `0x055A15B0` / `0x03603640` / `0x035E7760` / `0x035D8B70` / `0x036061D0`, and for vtable disp `0xA50` | None is a gate. `0xA50` is **`CallMovementUpdateDelegate`** [I, strong] — its callee `0x035D6790` calls disp `0x518` (`UpdateComponentVelocity`) then broadcasts on `CharacterOwner + 0x5E8`, which the UHT table gives as `OnCharacterMovementUpdated`. ⚠ **NOT** `OnMovementUpdated` — that is the adjacent slot `0xA48`, which holds the fold `0x00F7EC20`. | — | offline, low value |
| 10 | `LastUpdate*` resting values on this build | Made largely moot by §2.1's R1 correction, which does not depend on the default. | one 64-byte read across the 37 live CMCs | free |

### One thing the whole session missed and should not have

**S139 already banked the payload reading and nobody looked.** `tools/re/cmc_earlyout_readout.py`
reads `"cmc.velsnap": 0x16B0`, and the evidence carries it:

```
docs/s139-f1-BOT.txt:19        R1.velsnap@0x16B0 | (0.000,0.000,0.000) | (0.000,0.000,0.000)
docs/s139-f1-BASELINE.txt:20   R1.velsnap@0x16B0 | None                | (0.000,0.000,0.000)
```

**It is uninterpretable for the same reason as the flag** — the snapshot source `Velocity @+0xE8`
was itself `(0,0,0)`, and `NewObject` zero-fills, so the never-written and the written states are
the same bytes. **That is exactly why §5 insists on a sentinel.** It must be named explicitly,
because a successor will find that line and may read it as a *second, independent* negative.
It is not one.

---

## 8. SCOPE DISCIPLINE — what this is not

- **This is not a bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
  (`0x556DE53 → 0xF7EB60`) remain stripped folds; nothing here went through `SpawnBot`; the AI
  pawn's `PlayerState`, `LokiBotController` and `BehaviorTreeComponent` all exist only because of
  pokes the game never performs itself.
- **The GAS attribute port is a process-wide CDO poke and a diagnosis, not a shipping fix.** It
  borrows `Default__LokiPlayerState_HeroAffiliated`'s default subobjects into a live pawn's
  `+0xF00/+0xF08/+0xF10`. It affects every object constructed from that CDO for the process
  lifetime.
- **Nothing in this document was flown.** Every claim is offline static analysis over
  `dumps/merged13.dump.exe`, plus S139's already-banked live reads, plus corrections to how those
  reads should be interpreted. **The pawn still moves 0.00 uu.**
- Every count here is a count over what is **decrypted**: `.text` is 16,800 / 30,281 pages
  = **55.48 %**. Where a census could hide a writer on a dark page, it is labelled a FLOOR.

**Files:** `scratchpad/s140/syn/adj.py` … `adj9.py` (adjudicator's independent harness, read-only,
offline). Lane reports: `scratchpad/s140/lanes/L1-cfg-exits.md`, `L2-exit-semantics.md`,
`L3-ladder-engine.md`, `L4-ladder-loki.md`, `L5-12b0-writers.md`, `L6-latch-validity.md`.
