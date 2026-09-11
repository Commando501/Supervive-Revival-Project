# S140 — session lead's own independent reads (parallel to the six lanes)

All offline, `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, RVA == file offset (verified:
all 10 sections have `VirtualAddress == PointerToRawData`).

Instruments: `scratchpad/s140/tools/peimg.py` + `cfg.py` (recursive descent, 4-control self-test
PASSES). `CFG(0x035E9EC0)` = **1461 insns, 148 calls, 0 indirect jumps, 0 decode failures,
0 noreturn candidates** — independently reproducing S139's 1461.

---

## LF-1 [M] The sound exit set is the six. There is no backward bail — and it is not luck-dependent.

`exits_from(0x035EB13A)` over the instruction graph returns **7 edges**: the six, plus the call
node's own fallthrough `0x035EB13A -> 0x035EB140` (an artifact of admitting the target as a source).
`|R| = 1075` of 1461.

**Stronger, and this is what actually settles the "forward-only predicate" worry:** a scan of the
whole function for edges `src -> dst` with `dst <= src` finds **exactly 2 backward edges in the
entire function**, and both are *past* the call, inside the bail machinery:

    0x035EB7CA -> 0x035EB15C
    0x035EB845 -> 0x035EB197

Neither is in `R`. ⇒ **S139's forward-only predicate got the right answer, and it is now known WHY**
rather than assumed: this function is almost entirely a forward DAG.

## LF-2 [M] The call is NOT in a loop.

`pred(0x035EB13A) = {0x035EB137}` — a single predecessor. `0x035EB13A` is not reachable from
`0x035EB140`. ⇒ engine `PerformMovement` calls `StartNewPhysics` **at most once per invocation**,
which is what makes the latch interpretable.

## LF-3 [M] All six exits read directly, with semantics.

Five are in the prologue; the sixth is a re-check.

| # | address | instruction | predicate | live |
|---|---|---|---|---|
| 1 | `0x035E9F1F` | `je 0x35EB1A7` after `call [rdx+0x6B8]` on `rbx`=this | `!HasValidData()` | PASSES |
| 2 | `0x035E9F28` | `je 0x35EB1A7` after `test r13,r13` | `World == null` (`r13 = [this+0xC0]`, refetched via `call 0x35AFC40` if null) | PASSES |
| 3 | `0x035E9F97` | `je 0x35EB7CF` after `cmp byte [rbx+0x231], r15b` (`r15d` zeroed at `0x035E9F7F`) | `MovementMode == MOVE_None(0)` | PASSES (3) |
| 4 | `0x035E9FA4` | `jne 0x35EB7CF` after `cmp byte [rcx+0x1BB], 2`, `rcx = [rbx+0xD0]` | `UpdatedComponent->Mobility != Movable(2)` | PASSES (2) |
| 5 | `0x035E9FBD` | `jne 0x35EB7CF` after `call [rax+0x4C0]`, `rax = [UpdatedComponent]`, `edx = 0` | `UpdatedComponent->IsSimulatingPhysics(NAME_None)` | PASSES (bSimulatePhysics 0, WeldParent NULL) |
| 6 | `0x035EA25D` | `je 0x35EB150` after a **second** `call [rax+0x6B8]` on `rbx` | `!HasValidData()` again | same fields as #1 |

⇒ **only FIVE distinct predicates**, because #6 re-runs #1. A third `HasValidData` runs *after* the
call at `0x035EB146`.

⚠ **Correction to a CLAUDE.md line I must not repeat:** CLAUDE.md says `IsSimulatingPhysics` is
called with **`bGetWelded = TRUE`** (`0x03C9B0A0: mov r8b,1`). At exit 5 the argument register is
`edx` and it is **zero** (`0x035E9FAD mov edx, r15d`, `r15d` zeroed at `0x035E9F7F`). Different call
site, and `rdx` is the `FName BoneName` parameter, not `bGetWelded`. The S139 weld analysis was about
the `PerformMovement`-adjacent `GetBodyInstance` path, not this one.

## LF-4 [M] `HasValidData` (engine, vtable disp `0x6B8`, `0x035E64C0`, 14 insns, 0 calls) — NOT overridden by Loki.

    0x035e64c0  cmp   qword [rcx+0xd0], 0      ; UpdatedComponent
    0x035e64c8  je    0x35e64e5
    0x035e64ca  mov   rax, [rcx+0x198]         ; CharacterOwner
    0x035e64d1  test  rax, rax
    0x035e64d4  je    0x35e64e5
    0x035e64d6  mov   eax, [rax+0xc]           ; ObjectFlags
    0x035e64d9  shr   eax, 0x1e                ; >> 30
    0x035e64dc  not   al
    0x035e64de  test  al, 1                    ; !RF_Garbage
    0x035e64e0  je    0x35e64e5
    0x035e64e2  mov   al, 1 / ret
    0x035e64e5  xor   al, al / ret

All three inputs measured live and passing (UpdatedComponent non-null, CharacterOwner == pawn,
`ObjectFlags` bit 30 == 0). ⇒ **exits 1 and 6 provably pass.**

## LF-5 [M] vtable dispatch confirmed, with five passing controls.

`.rdata 0x088F8570` (ULokiCharacterMovementComponent). `.rdata` in a dumped image holds ABSOLUTE VAs;
subtract ImageBase.

| disp | -> RVA | name | control |
|---|---|---|---|
| `0x720` | `0x055C2430` | `ULokiCMC::StartNewPhysics` | **PASS** |
| `0xAA8` | `0x055B8370` | `ULokiCMC::PerformMovement` | **PASS** |
| `0x3D0` | `0x055C2B90` | `ULokiCMC::TickComponent` | **PASS** |
| `0x890` | `0x055A7680` | `ULokiCMC::ControlledCharacterMove` | **PASS** |
| `0x830` | `0x055B89F0` | `ULokiCMC::PhysFalling` | **PASS** |
| `0xA38` | `0x055A75B0` | `ULokiCMC::ConstrainInputAcceleration` | **PASS** |
| `0x6B8` | `0x035E64C0` | `HasValidData` — **engine impl, not overridden** | — |
| `0xB68` | `0x03603640` | dt-taking CMC virtual, engine impl (unnamed) | — |
| `0x610` | `0x055B1EC0` | bool CMC virtual, **Loki override** (unnamed) | — |

⚠⚠ **A category error I made and must flag:** I also printed `disp 0x4C0 -> 0x055AB8C0` from *this*
vtable. **That is wrong for exit 5.** At `0x035E9FBB` the dispatch is on `[UpdatedComponent]`, i.e.
the **UCapsuleComponent** vtable, not the CMC's. Sampling one displacement across unrelated vtables
is a trap CLAUDE.md already records. `0x055AB8C0` is NOT `IsSimulatingPhysics` and must not be cited
as such.

## LF-6 [M] The latch write is on the `Iterations == 0` path only, and `+0x16C8` is cleared-then-set.

See BRIEF item 2 for the full transcription. Consequences:
- it IS sound as "did `PerformMovement` reach `StartNewPhysics`", because `PerformMovement` passes
  `Iterations = 0` (`0x035EB129 xor r8d,r8d`);
- it is **NOT** a pure sticky latch, so whether anything else clears `+0x16C8` is a real open
  question (lane L6);
- `ULokiCMC::StartNewPhysics` **tail-jumps** (`0x055C2470 jmp 0x03600990`) into the engine impl,
  which was not previously recorded.

## LF-7 [I, strong] `[CharacterOwner+0x580]` is a 32-bit bitfield read on BOTH the engine bail path and the Loki wrapper.

`0x035EB7CF` (the target of exits 3/4/5) opens:

    mov  rcx,[rbx+0x198]        ; CharacterOwner
    mov  eax,[rcx+0x580]
    test al, 8                  ; bit 3
    jne  0x35eb839
    bt   eax, 9                 ; bit 9
    jb   0x35eb839

and `0x035EA214` also does `bt eax, 9` on it. This is the **same field** S139 flagged at Loki
`0x055B845E test byte [CharacterOwner+0x580], 8`. Never read live. Worth naming.

---

## LF-8 [M] THE FULL CALL CHAIN, hop by hop, each with a SOUND exit analysis

Every hop below was analysed with backward reachability over the instruction graph (not a
forward-address predicate), on `merged13`.

| hop | from -> to | call site | sound exits that skip it | status |
|---|---|---|---|---|
| 1 | `ULokiCMC::TickComponent 0x055C2B90` -> engine `TickComponent 0x03603780` | `0x055C2C32` (direct) | **0** | unconditional |
| 2 | engine `TickComponent 0x03603780` -> `ControlledCharacterMove` (disp `0x890`) | `0x03603B18` | 9 | all proven passed by observation (Acceleration is written) |
| 3 | `ULokiCMC::ControlledCharacterMove 0x055A7680` -> engine `ControlledCharacterMove 0x035DCD10` | `0x055A7853` (direct) | **0** | unconditional |
| 4 | engine `ControlledCharacterMove` -> `PerformMovement` (disp `0xAA8`) | `0x035DCDAC` | **1** | see LF-9 |
| 5 | `ULokiCMC::PerformMovement 0x055B8370` -> Super `0x035E9EC0` | `0x055B85C1` (direct) | lane L4 | |
| 6 | engine `PerformMovement` -> `StartNewPhysics` (disp `0x720`) | `0x035EB13A` | **6** | all measured passing (LF-3) |
| 7 | `ULokiCMC::StartNewPhysics 0x055C2430` -> latch | `0x055C2469` | on `Iterations==0` path | LF-6 |

★ **Hop 2 is the case that vindicates the sound method as a matter of principle, not luck:** three of
its nine exits are **FALLTHROUGH** edges leaving `R` (`0x0360386A`, `0x0360398A`, `0x03603A9D`), not
jump targets. A "branch target > call site" predicate is blind to those too — not only to backward
bails. (They are all downstream-proven passed here, so nothing rests on them; the point is the
method.)

## LF-9 [M] ★ There is EXACTLY ONE gate between the Acceleration write and `PerformMovement`, and it is measured passing ON THE SAME OBJECT.

Engine `ControlledCharacterMove 0x035DCD10` is 55 instructions:

    0x035dcd4e  call  [rbx+0xa38]           ; ConstrainInputAcceleration
    0x035dcd5f  call  [rbx+0xa40]           ; ScaleInputAcceleration
    0x035dcd6b  movups [rsi+0x328], xmm0    ; *** Acceleration  <- S139's signed-zero proof point
    0x035dcd7a  movsd  [rsi+0x338], xmm1    ; Acceleration.Z
    0x035dcd82  call  [rax+0x660]           ; ComputeAnalogInputModifier
    0x035dcd88  mov   rax, [rsi+0x198]      ; CharacterOwner
    0x035dcd8f  movss [rsi+0x3d0], xmm0     ; AnalogInputModifier
    0x035dcd97  movzx ecx, byte [rax+0x160] ; CharacterOwner->Role
    0x035dcd9e  cmp   cl, 3                 ; ROLE_Authority
    0x035dcda1  jne   0x35dcdb4             ; *** THE ONLY EXIT ***
    0x035dcdac  call  [rax+0xaa8]           ; PerformMovement

Sound analysis: 37 of 55 instructions can reach `0x035DCDAC`; **exactly one** edge leaves that set,
`0x035DCDA1`.

⇒ [M] the gate reads `[CharacterOwner+0x160]`, and `CharacterOwner` is `[CMC+0x198]` — **the same
pointer S139's identity control verified equals the pawn**, whose `+0x160` was measured **3**.
So this is not merely "a Role was measured 3 somewhere": the branch dereferences the object the probe
read. **Hop 4 provably passes.**

⚠ **But note what this DOES NOT prove, and S139's phrasing blurred it:** the `Acceleration` store at
`0x035DCD6B` sits **UPSTREAM** of this gate. So the signed-zero observation proves the function ran
to `0x035DCD6B` — it does **not**, by itself, prove `PerformMovement` was called. That step needs the
Role measurement, which we have. The chain holds; the support is two facts, not one.

## LF-10 — consequence: the contradiction is TIGHTER after this work, not looser.

Hops 1, 3 are unconditional [M]. Hop 2 is proven passed by observation. Hop 4 has one gate, measured
passing on the same object. Hop 6 has six exits reducing to five distinct predicates, all measured
passing, two of them (`HasValidData`) provably so from a 14-instruction fully-transcribed callee.
Hop 7's call is not in a loop and has a single predecessor.

⇒ The surviving explanations are narrow: **(a) hop 5 has a bail** (lane L4), **(b) the latch is not a
valid instrument** (lane L6), or **(c) a live measurement is of a different object or a different
moment than assumed** — including the possibility that the latch READ itself is a probe defect
(`cmc_earlyout_readout.py` already had two defects found in S139: an FNamePool block-table offset and
an `FField` name offset, each of which printed as a confident game fact).

---

## LF-11 [M] ★ HOP 5 SETTLED INDEPENDENTLY: `ULokiCMC::PerformMovement` reaches its Super UNCONDITIONALLY — and S139's two flagged branches are IRRELEVANT to it.

`CFG(0x055B8370)` = 322 insns, 29 calls, **0 indirect jumps, 0 decode failures**.
`exits_from(0x055B85C1)`: 142 of 322 instructions can reach the Super call, and **ZERO edges leave
that set**. Same sound method (backward reachability), not a forward-address predicate.

⚠⚠ **THIS CORRECTS THE S139 HANDOFF'S OWN RANKED NEXT STEP.** `docs/next-session-prompt-s140.md` and
the CLAUDE.md S139 block say:

> "★ **NEXT, and it is small:** (a) does Loki's `PerformMovement` reach its Super? two forward
> branches jump toward it — `0x055B845E test byte [CharacterOwner+0x580],8 / jne` and
> `0x055B846B mov ebp,[rsi+0x1988] / sub ebp,1 / js`; **`[CharacterOwner+0x580] & 8` is an unread
> live byte.**"

**Both branches target `0x055B85B4`**, which is **13 bytes BEFORE the Super call at `0x055B85C1`**
and falls straight into it:

    0x055b845e  test  byte [rax+0x580], 8
    0x055b8465  jne   0x55b85b4          -----+
    0x055b846b  mov   ebp, [rsi+0x1988]       |
    0x055b8471  sub   ebp, 1                  |
    0x055b8474  js    0x55b85b4          -----+
    ...  loop 0x055b84b0 .. 0x055b859e (array at [rsi+0x1980], count [rsi+0x1988], stride 0xC)
    0x055b85b4  movaps xmm1, xmm6        <----+
    0x055b85b7  mov   byte [rsi+0x1308], 0
    0x055b85be  mov   rcx, rsi
    0x055b85c1  call  0x35e9ec0                ; SUPER — reached either way

⇒ **They skip a LOOP, not the Super.** `[CharacterOwner+0x580] & 8` is worth naming for other reasons
(LF-7 — the engine's own bail block reads the same field) but **it cannot be the wall, and reading it
live would settle nothing about hop 5.** That was the S139 handoff's #1 ranked next move.

★ Incidental ladder candidate for lane L4: **`0x055B85B7 mov byte [rsi+0x1308], 0`** is the last
store before the Super call. It writes a CONSTANT ZERO, so it is USELESS as a receipt unless some
other code sets `+0x1308` to 1 — that is exactly the GOOD/WEAK/USELESS distinction L3/L4 were asked
to make.

★ Also visible: `0x055B83B5 call 0x56E7C10` with `cl = 0x78` (120) is the HitStop toggle;
`r15` is a *validated* `CharacterOwner` (zeroed at `0x055B83A6` if null or if `0x54F8C40` fails);
the `xorps xmm6,xmm6` dt-kill at `0x055B83FA` is reached only through the
`[r15+0x7F0]` IAbilitySystemInterface secondary-vtable chain — consistent with S139's refutation of
S1, and with the bot's `+0xF00` being NULL.

---

# LF-12 — WHERE THIS LEAVES THE CONTRADICTION (session lead's adjudication input)

The full chain is now verified with a sound exit analysis at every hop:

| hop | sound exits skipping the next call | status |
|---|---|---|
| 1 Loki Tick -> engine Tick | **0** | unconditional [M] |
| 2 engine Tick -> ControlledCharacterMove | 9 | all proven passed *by observation* (Acceleration is written) |
| 3 Loki CCM -> engine CCM | **0** | unconditional [M] |
| 4 engine CCM -> PerformMovement | **1** (`Role==3`) | measured passing, provably same object [M] |
| 5 Loki PerformMovement -> Super | **0** | unconditional [M] — NEW |
| 6 engine PerformMovement -> StartNewPhysics | **6** (5 distinct predicates) | all measured passing [M] |
| 7 StartNewPhysics -> latch | on `Iterations==0`, which is what hop 6 passes (`0x035EB129 xor r8d,r8d`) | [M] |

**Every hop is either unconditional or measured-passing. The contradiction is TIGHTER than S139 left
it, not looser.** The forward-only-predicate worry that motivated this session is dead: there is no
seventh exit, no backward bail, no indirect jump, no noreturn candidate, and the call is not in a loop.

⇒ **By elimination, the leading survivor is now (b): THE LATCH IS NOT A VALID INSTRUMENT** — either
something clears `CMC+0x16C8` (lane L6's crux), or the live read of it was defective. Ranked
survivors:

1. **The latch is cleared by a consumer.** `+0x16B0`/`+0x16C0`/`+0x16C8` look like a saved-state
   struct with a validity flag (Velocity snapshot + a qword + a bool). A consumer that clears the
   flag after use makes `latch == 0` the NORMAL steady state and the whole "never ran" reading
   collapses. → lane L6. **Settleable OFFLINE.**
2. **The latch READ was a probe defect.** `cmc_earlyout_readout.py` already had two defects found in
   S139 (FNamePool block-table offset; `FField` name at `+0x28` instead of `+0x20`), each of which
   printed as a confident game fact — one of them as "NO PLAYER-CONTROLLED PAWN — RUN IS VOID" on a
   healthy client. A third defect is entirely in character. → needs a live re-read with a
   second, independent instrument.
3. **A measured input differs at the moment `PerformMovement` actually runs** (e.g. `MovementMode`
   transiently `MOVE_None`). Weakest: it would have to hold on all 37 components.

⚠ Note what is NOT on this list any more: "a seventh exit". That hypothesis is **[M] refuted**.

---

# ★★★★★ LF-13 [M] — **THE LATCH IS CLEARED AT THE END OF EVERY COMPLETED `PerformMovement`. `CMC+0x16C8 == 0` IS UNINTERPRETABLE, AND "StartNewPhysics HAS NEVER RUN" WAS NEVER MEASURED.**

## The chain, every step from the bytes

**1. `ULokiCharacterMovementComponent` overrides vtable displacement `0xA50` with a 4-instruction
function whose ENTIRE non-tail body is a clear of `+0x16C8`:**

    0x0530abf0  80 b9 c8 16 00 00 00     cmp byte ptr [rcx + 0x16c8], 0
    0x0530abf7  74 07                    je  0x530ac00
    0x0530abf9  c6 81 c8 16 00 00 00     mov byte ptr [rcx + 0x16c8], 0
    0x0530ac00  e9 8b bb 2c fe           jmp 0x35d6790          ; tail-jump to the engine base impl

`rcx` is `this` (the CMC). Either it is already 0 or it is stored 0 — **the field is 0 on exit
unconditionally.** `.rdata` stored-pointer occurrences of `0x0530ABF0` image-wide: **1** ⇒ not
ICF-folded, so the address identifies this function.

**2. Engine `PerformMovement` calls displacement `0xA50` at `0x035EB569`, and it dispatches through
the LOKI vtable** (`0x035EB554 mov rax,[rbx]`, `rbx = this = the Loki CMC`):

    0x035eb554  mov    rax, [rbx]
    0x035eb557  lea    r9,  [rbp + 0x18]     ; OldVelocity
    0x035eb55b  lea    r8,  [rbp + 0xe8]     ; OldLocation
    0x035eb562  movaps xmm1, xmm11           ; DeltaSeconds
    0x035eb566  mov    rcx, rbx              ; this
    0x035eb569  call   [rax + 0xa50]

[M] vtable read: `.rdata 0x088F8570 + 0xA50` -> VA `0x7FF60E24ABF0` -> RVA **`0x0530ABF0`**.
Controls in the same read: disp `0x720`->`0x055C2430`, `0xAA8`->`0x055B8370`, `0x3D0`->`0x055C2B90`,
`0x890`->`0x055A7680`, `0x830`->`0x055B89F0`, `0xA38`->`0x055A75B0` — **6/6 PASS.**

**3. [I, strong] disp `0xA50` is `UCharacterMovementComponent::OnMovementUpdated(float DeltaSeconds,
const FVector& OldLocation, const FVector& OldVelocity)`** — the argument shape is exactly float +
two `FVector&`, the two vectors are captured EARLY (`0x035EA0FD` -> `[rbp+0x18]`,
`0x035EA113` -> `[rbp+0xe8]`, both upstream of the physics step) and passed at the END, and stock UE
calls `OnMovementUpdated` in precisely that position. Graded [I] not [M] because no symbol or literal
names it; the *behaviour* below does not depend on the name.

**4. [M] POSITION: the clear runs strictly AFTER the physics step, and NEVER on a bail path.**

    A50 call reachable after the StartNewPhysics call returns .......... True
    A50 call able to reach the StartNewPhysics call (in R) ............. False
    A50 call reachable from bail 0x035EB1A7 / 0x035EB7CF / 0x035EB150 .. False

## Therefore

| scenario | `CMC+0x16C8` as seen by an external probe between frames |
|---|---|
| `PerformMovement` bailed at one of the six exits | **0** (never set) |
| `PerformMovement` completed through `OnMovementUpdated` | **0** (set at `0x055C2469`, cleared at `0x0530ABF9`) |
| `PerformMovement` mid-flight, inside the physics step | 1 — a window of microseconds |
| `PerformMovement` completed via a post-SNP path that skips `OnMovementUpdated` | 1 (such paths exist: 221 post-SNP instructions reach the `ret` at `0x035EB1CA` while blocking the A50 node) |

⇒ **[M] `latch == 0` is the expected reading BOTH when `StartNewPhysics` never runs AND when it runs
and completes normally. The field cannot discriminate the two.** It is a transient in-progress flag,
not a sticky latch.

⚠ **What this does and does not establish.** It does **NOT** show `StartNewPhysics` runs. It shows the
observation that said it does not **carries no information**. The S139 finding
*"`ULokiCMC::StartNewPhysics 0x055C2430` HAS NEVER RUN ON EITHER COMPONENT"* — and its corollary
*"every latch `+0x16C8` = 0 across all 37 movement components"* — must be **RETRACTED to
UNINTERPRETABLE.**

★ **A coherence check that should have raised the alarm at the time:** the field read 0 on **all 37**
movement components in the world, including the player's. Under the old reading that means *nothing
in the world can simulate movement at all*. Under the new reading it means nothing whatsoever — which
is the far more likely of the two.

★ **This is the 97th instrument-artifact instance and it is textbook:** a field was named "the latch"
from the site that SETS it, without enumerating the sites that CLEAR it, and the resulting zero was
recorded as a property of the game. S139 explicitly justified it — *"on the unconditional
fall-through of the `Iterations==0` path (the `je` at `0x055C243F` skips only a redundant zero-store)
— so `+0x16C8` is a valid sticky 'ever reached' instrument"*. **The reasoning about the SETTER was
entirely correct. The error was never asking who clears it.**

## What the wall actually is now

The hard, still-valid observations from independent instruments are:

- `Acceleration @CMC+0x328` = `ControlInputVector × 50000` [M, 20 samples, ratio mean 49999.63,
  with the untreated player non-zero in 0/20 as a specificity control];
- `Velocity @CMC+0xE8` stays `(0,0,0)` [M];
- the pawn translates **0.00 uu** [M];
- `TimeSinceFallingStart @CMC+0x12B0` advances at 1.0x real time on both pawns [M].

⇒ **The question is no longer "why is the physics step never entered". It is "why does a correct
`Acceleration` produce no `Velocity`".** That relocates the investigation from
`PerformMovement`'s prologue gates to **`CalcVelocity` / `PhysFalling` (`0x055B89F0`, disp `0x830`)**
— a different function, and one nobody has read.

⚠ And note `+0x12B0` (`TimeSinceFallingStart`) advancing is now *more* interesting, not less: writer
**B** at `0x055C2483` lives in `StartNewPhysics` on the `Iterations > 0` arm behind
`cmp byte [rcx+0x231], 3` (MOVE_Falling) — i.e. on the recursive path taken from inside
`PhysFalling`. Lane L5 owns disentangling which writer is responsible.

---

## LF-14 [M] The `LogCharacterMovement` sites on the movement path — enumerated, with verbosities, and a free instrument S139 said did not exist.

⚠⚠ **FIRST, MY OWN INSTRUMENT ARTIFACT, caught and corrected in-session.** I ran a scan for
rip-relative `lea` references into `.rdata` across the movement functions and got **0 for engine
`StartNewPhysics`**, with a *passing* positive control (`"WallJumpCheck"` at `.rdata 0x08B1A198`,
1 reference, exactly as expected). I was one step from recording *"the
`is simulating physics - aborting` literal is never referenced, so S139's recommended first move is
unfounded."* **That would have been false.** UE does not `lea` the format string directly — it
`lea`s a **log-record struct** whose `+0x00` field is a POINTER to the string. My control passed
because it happened to be a direct reference; **it could not discriminate the indirect case.**
★ The rule this instantiates: *a positive control validates the mechanism it exercises, not the
question you are asking.*

**The record layout, decoded** (`.rdata`, 32 bytes): `+0x00` format-string VA · `+0x08` file-name VA ·
`+0x10` packed `(verbosity << 32) | line` · `+0x18` a per-site pointer into `.data`.

| site | record | string | verbosity | line | fires? |
|---|---|---|---|---|---|
| `0x03600A21` (engine `StartNewPhysics`) | `0x07FC0648` | `"UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is simulating physics - aborting."` | **5 = Log** | 3477 | only if `IsSimulatingPhysics()` — measured FALSE, so **never** |
| `0x03600B6C` (engine `StartNewPhysics`) | `0x07FC0740` | `"%s has unsupported movement mode %d"` | **3 = Warning** | 3510 | only on the jump-table default arm; `MovementMode 3` is in range, so **never** |
| `0x035EAFD3` (engine `PerformMovement`) | `0x07FC0548` | `"PerformMovement WorldSpaceRootMotion Translation: %s, Rotation: %s, Actor Facing: %s, Velocity: %s"` | **5 = Log** | 2919 | root-motion path only |

[M] `Loki PerformMovement`, `Loki StartNewPhysics`, `engine TickComponent`, `Loki/engine
ControlledCharacterMove` contain **zero** `.rdata` references of any kind. `Loki PhysFalling` has
exactly one, and it is the FName literal `"WallJumpCheck"`, not a log.

⇒ ★ **THERE IS NO PER-FRAME LOG RECEIPT ON THE MOVEMENT PATH.** Pinning `LogCharacterMovement`
higher will NOT produce a "the physics step ran" line. S139's recommendation —
*"Pin `LogCharacterMovement=Log` … and the whole question becomes a per-frame log line"* — is
**REFUTED as stated**: the three sites are all on arms that do not execute in this scenario.

★★ **BUT the same work yields the instrument S139 correctly said was missing.** S139 wrote:
*"`LogCharacterMovement` occurs 0 times in the whole log, so the category has NO positive control and
that zero is UNINTERPRETABLE."* **The category object is at `.data 0x9F85E68`** [M] — derived two
independent ways that agree exactly: the gate `0x036009EE cmp byte [rip+0x6985473], 5` resolves to
`0x9F85E68`, and the logger call's own `0x03600A28 lea rcx, [rip+0x6985439]` resolves to the same
`0x9F85E68`. Per CLAUDE.md's FK-11 layout, `FLogCategoryBase.Verbosity` is at **offset 0** and
`CompileTimeVerbosity` at **+3**.

⇒ **ONE read-only RPM byte read of `.data 0x9F85E68` settles the suppression question for free**:
if runtime Verbosity ≥ 5 the category is live and its silence is meaningful; if it is lower, the
silence is an artifact. **That is a positive control for a log category without needing the category
to emit** — reusable for every "category X is silent" question in this project.
⚠ Read it from a LIVE process or a single-state dump, never from `merged13`'s `.data` (spliced).

---

## LF-15 [M] The other candidate receipt is ALSO a transient — this code has NO persistent "I ran" marker by design.

`CMC+0x2E8` bit 6 (stock UE: `bMovementInProgress`) is the obvious second candidate. It is
**saved, set, and restored** inside engine `StartNewPhysics`:

    0x03600a5c  movzx ebp, byte [rbx+0x2e8]      ; SAVE
    0x03600a75  mov   byte [rbx+0x2e8], al       ; al = saved | 0x40   -> SET
    ...  switch (MovementMode) ...
    0x03600ba8  movzx eax, byte [rbx+0x2e8]
    0x03600bb7  xor   cl, bpl
    0x03600bbf  and   cl, 0x40
    0x03600bc2  xor   cl, al                     ; restore ONLY bit 6 to its saved value
    0x03600bcb  mov   byte [rbx+0x2e8], cl       ; RESTORE

Only 4 accesses to `+0x2E8` in the whole function, and they form exactly one save/set/restore triple.

⇒ ★ **Both flags a probe might reach for — `CMC+0x16C8` and `CMC+0x2E8` bit 6 — are IN-PROGRESS
flags restored before return. Neither can be sampled between frames.** That is a design pattern, not
an accident, and it means **no free sticky "the physics step ran" receipt exists in this code.**
A future instrument must be one of:
  (a) a **rate** measurement (e.g. `+0x12B0` accumulation rate — see lane L5's writer split),
  (b) an **external observable** (world position / Velocity over time) — which is what we already have
      and which says the pawn does not move, or
  (c) a **poked canary** (a live write, so not Tier 1).

## LF-16 [I, strong] The one argument for "the physics step does not run" that SURVIVES the latch's invalidation.

[M] engine `StartNewPhysics` dispatches on `MovementMode` (`[rbx+0x231]`) through an 8-entry jump
table at `.text 0x03600BF8`, bounded by `cmp esi,7 / ja 0x3600b35`:

    case 0 MOVE_None    -> 0x03600BA8 (straight to the epilogue -- does nothing)
    case 1 MOVE_Walking -> 0x03600A97      case 2 MOVE_NavWalking -> 0x03600AAE
    case 3 MOVE_Falling -> 0x03600AC5      case 4 MOVE_Swimming   -> 0x03600AF3
    case 5 MOVE_Flying  -> 0x03600ADC      case 6 MOVE_Dashing    -> 0x03600B0A
    case 7 MOVE_Custom  -> 0x03600B21

Cases 1-7 all begin `mov rax,[rbx]; mov r8d,edi; movaps xmm1,xmm6` — i.e. a virtual dispatch with
(this, dt, Iterations). ⇒ **`PhysFalling` is reachable ONLY from `StartNewPhysics`**, confirming
CLAUDE.md's note and (independently) that the table is the Loki-modified 8-entry one with
`MOVE_Dashing` at index 6.

⇒ **A pawn in `MOVE_Falling(3)` with `GravityScale 1.000` that does not fall is evidence the physics
step is not executing**, because gravity is applied inside `PhysFalling`, which only
`StartNewPhysics` dispatches. **This is an INFERENCE FROM AN ABSENCE OF MOTION, not a measurement of
the code path** — grade **[I, strong]**, never [M]. It is the honest remaining support for a
conclusion S139 stated as [M] on the strength of an invalid flag.

★ **The two claims must now be kept apart:**
  • *"`StartNewPhysics` has never run"* — **[I, strong]** from the no-gravity argument. NOT measured.
  • *"the latch proves it"* — **[M] REFUTED.** The latch proves nothing either way.

---

# LF-17 — ADJUDICATION OF LANE L6 (which reached LF-13 INDEPENDENTLY)

★★★★★ **Two fully independent derivations converged on the same mechanism.** The session lead
(LF-13) and lane L6 each found, without contact, that `ULokiCMC` overrides vtable disp `0xA50` with
`0x0530ABF0`, that its body clears `CMC+0x16C8`, and that engine `PerformMovement` calls it at
`0x035EB569` after the physics step. **That is the strongest form of confirmation available here.**

**CONFIRMED by the session lead, re-read from the bytes:**
- `0x07FBED58` = the **engine** `UCharacterMovementComponent` vtable [M] — L6 located it from scratch;
  I re-read six slots against known answers: disp `0xA50`→`0x035D6790`, `0x720`→`0x03600990`,
  `0xAA8`→`0x035E9EC0`, `0x3D0`→`0x03603780`, `0x890`→`0x035DCD10`, `0x6B8`→`0x035E64C0`.
  **6/6 PASS.** ⇒ Loki genuinely OVERRIDES disp `0xA50`; the engine's own slot is the plain base impl.
- `0x0530AAA0` = the ULokiCMC vector deleting destructor, `mov edx, 0x19D0` ⇒ **sizeof(ULokiCMC) =
  0x19D0**, which matches CLAUDE.md's independent S138 note ("a 0x19D0-byte component").

★ **L6 found something I got WRONG, and it is the practical deliverable.** I dismissed the
`+0x16B0` Velocity snapshot as a useless receipt because Velocity rests at `(0,0,0)`, so a written
snapshot is indistinguishable from a never-written one. **L6's fix: poke a SENTINEL into
`Velocity @CMC+0xE8` first.** `OnMovementUpdated` clears only the FLAG at `+0x16C8`; nothing clears
`+0x16B0`/`+0x16C0`. So:

> write `(1234.5, 6789.25, -4242.125)` to `CMC+0xE8`, wait some frames, read `CMC+0x16B0..+0x16C7`.
> **payload == sentinel ⇒ `ULokiCMC::StartNewPhysics` ran with `Iterations==0`.**
> **payload stays (0,0,0) while `+0xE8` still holds the sentinel ⇒ it did not.**

⚠ It requires an external `WriteProcessMemory`, which CLAUDE.md flags as an **unresolved hazard**
(one prior use, client died ~44 s later, n=1, heavily confounded). Pair with a matched no-write
sitting. Probe control: read back `+0xE8` after the poke; absent sentinel ⇒ run VOID.

★ **L6 also caught a second, independent reason the flag was never right, which I missed:** the latch
write at `0x055C2469` executes **BEFORE** the tail-`jmp` into the engine impl, so even catching it at
1 would prove only that the *vtable dispatch* happened — nothing about the engine's own four gates
(`MIN_TICK_TIME` `0x036009A8`, `MaxSimulationIterations` `0x036009B5`, `HasValidData` `0x036009C5`,
`IsSimulatingPhysics` `0x036009E4`).

## ⚠ ONE CLAIM OF L6's THAT I ADJUDICATE AS WRONG

L6 §7 offers a "write-free alternative": *"`LogCharacterMovement=Log` in the user `Engine.ini` turns
the engine `StartNewPhysics`'s own `IsSimulatingPhysics` abort into a per-frame log line
(`.rdata 0x07FC0670`)."*

**REFUTED (see LF-14).** That log site sits on the arm taken **only when `IsSimulatingPhysics()`
returns TRUE**, and we have measured `bSimulatePhysics == 0` with `WeldParent == NULL`, so it
**cannot fire**. It is not a per-frame line; it is a line that should never appear, and its absence
is uninterpretable. The same objection applies to S139's own recommendation, which is where L6
inherited it from. [M] the only three `LogCharacterMovement` sites on this path are the
simulating-physics abort (never), the unsupported-movement-mode Warning (never — mode 3 is in range),
and a root-motion-only Log.
★ The salvageable part: the category object is at `.data 0x9F85E68`, so **one RPM byte read gives the
positive control the category has always lacked**.
