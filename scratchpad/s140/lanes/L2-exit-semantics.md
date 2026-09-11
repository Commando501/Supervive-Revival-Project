# L2 — TASK A1b: WHAT DOES EACH EXIT OF ENGINE `PerformMovement` ACTUALLY TEST?

**Lane:** L2 (offline). **Image:** `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`,
`flat()==True` (all 10 sections VA==PointerToRawData, re-verified this session).
**Instruments:** shared `scratchpad/s140/tools/peimg.py` + `cfg.py` (used unmodified) plus my own
capstone scripts under `scratchpad/s140/lanes/L2work/`.
**All addresses are RVAs, machine-computed by capstone/`struct`. No hand arithmetic anywhere.**

---

## 0. CONTROLS RUN, AND WHAT THEY RETURNED

| control | expected | got | verdict |
|---|---|---|---|
| `peimg.flat()` | True | **True** | PASS (RVA==file offset) |
| `cfg.py` self-test (fold decode, HasValidData rets, exact backward-reach, dark ctrl zero) | PASS | **PASS** | PASS |
| Known-DARK control `0x5A6AC40` page_nonzero | 0 | **0** | PASS |
| `CFG(0x035E9EC0)` size | 1461 (S139) | **1461 insns, 148 calls, 0 indirect jumps, 0 decode failures, 0 noreturn candidates** | PASS — independently reproduces S139 |
| **Engine CMC vtable identification.** `.rdata 0x07FBED58` slots vs the brief's independently-derived table: `+0xAA8`, `+0x6B8`, `+0x720`, `+0x890`, `+0x4E0` | `0x035E9EC0`, `0x035E64C0`, `0x03600990`, `0x035DCD10`, `0x0364BA80` | **all five MATCH** | PASS (5/5) |
| **Loki CMC vtable identification.** `.rdata 0x088F8570` slots `+0xAA8`, `+0x720`, `+0x3D0` | `0x055B8370`, `0x055C2430`, `0x055C2B90` | **all three MATCH the brief** | PASS (3/3) |
| **Log-record decoder.** Decode `.rdata 0x07FC0648`, check line number against the independently-known `CharacterMovementComponent.cpp:3477` | line 3477 | **line 3477, format = "UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is simulating physics - aborting.", file = `C:\TheoryCraft\build-staging\Engine\Source\Runtime\Engine\Private\Components\CharacterMovementComponent.cpp`** | PASS |
| **UHT `SetBitFunc` decoder.** 11 consecutive `[rcx+0x580]` bit-setters to names | stock `ACharacter` declaration order | **11/11 resolve, order exactly matches stock UE** | PASS |
| **Register provenance.** capstone `regs_access` writer-scan for `rbx`, `rcx`, `r15`, `r13`, `r8d` over the relevant ranges | 0 writers | **0 writers in all five ranges** | PASS |

---

## 1. HEADLINE ANSWERS

**H1 [M] — the exit enumeration is COMPLETE, proved two independent ways.**
`exits_from(0x035EB13A)` over the recursive-descent CFG returns exactly **7 edges**, `|R| = 1075` of
1461: the six named exits plus the call node's own fallthrough `0x035EB13A -> 0x035EB140` (an
artifact of the target being its own source). **No backward bail exists.** The walk has **0 indirect
jumps and 0 decode failures**, so the reachability result is exact, not a floor.

**H2 [M] — exits 1-5 are DOMINATORS of the `StartNewPhysics` call; exit 6 is NOT.**
Iterative dominator analysis on the instruction graph (`|Dom(call)| = 128`, converged in 3
iterations) says every path entry->call passes through exits 1-5. There are **14 mandatory
conditional branches** on every such path; 5 of them are exits 1-5 and the other 9 have both arms in
`R`. Exit 6 (`0x035EA25D`) is **not** a dominator — it sits inside the optional root-motion block.
=> **exits 1-5 are the complete mandatory gate set, in source order.**

**H3 [M] — the third gate (`IsSimulatingPhysics`) IS ALREADY SETTLED. It passes.**
`docs/next-session-prompt-s140.md` (as quoted in CLAUDE.md) says this gate "has never been read" and
calls reading it "the whole next session". **That is superseded by the brief's own banked
measurement plus these bytes**, and no new live read is needed for the *value*:

    0x03C9B0A0 UPrimitiveComponent::IsSimulatingPhysics
        mov r9d,-1 ; mov r8b,1              <- bGetWelded = TRUE
        call [this_vt+0x810]                 = GetBodyInstance 0x03C91C60
        test rax,rax / je -> return false
        mov rcx,rax / call 0x01E2F940       <- FIRST insn: test byte [BI+0x10],1 ; je -> xor al,al; ret
        ...
    0x03C91C60 GetBodyInstance (full, 0x19 bytes):
        test r8b,r8b / je +
        mov rax,[rcx+0x5F0]  (WeldParent) / test / jne  -> welded body
        lea rax,[rcx+0x3F0]  (own BodyInstance) / ret

`WeldParent @capsule+0x5F0 == NULL` (measured, brief table) => returns `capsule+0x3F0`.
`[BodyInstance+0x10] & 1 == 0` (measured, brief table) => `0x01E2F940` returns false at its **first**
test => `IsSimulatingPhysics()` returns **false** => `jne 0x035EB7CF` **not taken** => **the gate
passes.** The determination is complete — the two later tests inside `IsSimulatingPhysics` can only
push the result further toward false.

**H4 [M] — if the call at `0x035EB13A` had executed, the latch WOULD have been written.**
`0x035EB129 = 4533c0 = xor r8d,r8d` and capstone `regs_access` finds **0 writers of r8/r8d** between
there and `0x035EB13A`. So `Iterations == 0` at the call. `[ULokiCMC vt+0x720] = 0x055C2430`, whose
`Iterations==0` arm writes `mov byte [rcx+0x16C8],1` at `0x055C2469` **before** the tail-jump to the
engine. => **latch == 0 implies `0x035EB13A` never executed.**
Bounding the dispatch: exactly **one** `.rdata` location holds the VA of `0x055B8370`, one holds
`0x055C2430`, one holds `0x055C2B90`, and all three resolve to the **same** vtable `0x088F8570` =>
there is no C++ subclass of `ULokiCharacterMovementComponent` with its own vtable in this image, so
the virtual dispatch cannot land anywhere else. **[M, bounded by a `.rdata` scan.]**

**H5 [M] — the high-value extra is a clean NEGATIVE. There is no free log receipt on any bail path.**
Forward reachability from each bail target, with every capstone RIP-relative *operand* enumerated
(never a byte-pattern scan — trap #3):

| bail target | insns forward-reachable | RIP-relative refs | calls | logger `0x106B650` reached |
|---|---|---|---|---|
| `0x035EB1A7` (epilogue) | 9 | **0** | 1 (`__security_check_cookie 0x751DEB0`) | no |
| `0x035EB7CF` (gates 3/4/5 bail) | 39 | **0** | 6 | no |
| `0x035EB150` (exit-6 bail) | 20 | **0** | 2 | no |

Depth-1 check of every bail callee (`0x035D8B70`, `0x03786FA0`, `0x037DD080`, `0x037C8250`,
`0x03536040`, `0x03603640`): **none calls the logger `0x106B650`.**
=> **The three-way OR bail at `0x035EB7CF` is silent AND undiscriminating** (three predicates, one
target, no log). Do not expect a log line to tell you which gate fired.

**H6 [M] — but there IS a log, one function downstream, and I have its category object.**
Engine `StartNewPhysics 0x03600990` carries **four** early-outs, one of which logs:

    0x036009A8  comiss xmm6, [0x076B8E74]     ; DeltaTime vs MIN_TICK_TIME 1e-6f
    0x036009AF  jb  0x03600BE6                ; EXIT-A (silent)
    0x036009B5  cmp r8d, dword [rcx+0x3E4]    ; Iterations vs MaxSimulationIterations
    0x036009BC  jge 0x03600BE6                ; EXIT-B (silent)  *** NOT IN THE BRIEF ***
    0x036009C5  call [vt+0x6B8]  HasValidData
    0x036009CD  je  0x03600BE6                ; EXIT-C (silent)
    0x036009E4  call [UpdatedComponent_vt+0x4C0] IsSimulatingPhysics
    0x036009EC  je  0x03600A57                ; -> the MovementMode switch (the good path)
    0x036009EE  cmp byte [.data 0x09F85E68], 5    ; *** LOG CATEGORY OBJECT ***
    0x036009F5  jb  0x03600BE6
    0x03600A28  lea rcx,[0x09F85E68] ; lea rdx,[0x07FC0648] ; call 0x106B650   <- UE_LOG(..., Log, ...)

=> **The `LogCharacterMovement` `FLogCategory` object is at `.data 0x09F85E68`**, threshold **>= 5
(`Log`)**. That is the exact object a live probe reads / the ini pins.
**New:** `EXIT-B` (`Iterations >= [CMC+0x3E4] MaxSimulationIterations`) is a fourth engine early-out
the brief does not list. It is downstream of the latch, so it cannot explain latch==0, but any lane
reasoning about "does StartNewPhysics do anything" needs `[CMC+0x3E4]`.
The 8-entry `MovementMode` jump table is at `0x03600BF8`, bounded by `cmp esi,7 / ja` — consistent
with this build's `MOVE_MAX == 8`.

---

## 2. THE EXIT TABLE

`rbx` = `this` (the CMC), set once at `0x035E9EFD` (`mov rbx,rcx`) and **never redefined anywhere in
the function** (capstone `regs_access` writer-scan over `[0x035E9F00, 0x035EB13B)` = **0 writers**).
`rcx` = `UpdatedComponent`, loaded at `0x035E9F2E` from `[rbx+0xD0]`, **0 writers** through
`0x035E9FB6`. => **every gate below dereferences exactly the objects the live probes read.**

### EXIT 1 — `0x035E9F1F je 0x035EB1A7`
* **raw:** `0x035E9F17 ff92b8060000` (`call [rdx+0x6b8]`); `0x035E9F1D 84c0 0f8482120000`
* **predicate:** `!HasValidData()`. `rdx = [rbx]` (CMC vtable), `rcx = rbx`.
* **virtual resolve:** `ULokiCMC vt(.rdata 0x088F8570) + 0x6B8 = 0x035E64C0`. Grade **REAL** (page
  nz=3628). Loki does **not** override it — engine vtable `0x07FBED58 + 0x6B8` is the same address.
* **`HasValidData 0x035E64C0` full body**
  (`4883b9d000000000741b488b81980100004885c0740f8b400cc1e81ef6d0a8017403b001c3`):

      cmp qword [rcx+0xD0], 0   ; UpdatedComponent
      je  -> false
      mov rax,[rcx+0x198]       ; CharacterOwner
      test rax,rax / je -> false
      mov eax,[rax+0x0C]        ; UObject::ObjectFlags
      shr eax,0x1E / not al / test al,1 / je -> false     ; bit30 RF_Garbage must be CLEAR
      mov al,1 / ret

* **fields / owning class:** `UCharacterMovementComponent::UpdatedComponent @CMC+0xD0`,
  `::CharacterOwner @CMC+0x198`, `UObject::ObjectFlags @CharacterOwner+0x0C` bit 30.
* **measured?** ALL THREE, brief table: `+0xD0` non-null CapsuleComponent, `+0x198 == pawn`,
  `RF_Garbage == 0`.
* **same object?** **YES [M]** — `rcx == rbx == this`, provenance machine-verified.
* **verdict: PASSES.** Nothing left to settle.

### EXIT 2 — `0x035E9F28 je 0x035EB1A7`
* **raw:** `0x035E9EEE 4c8ba9c0000000` (`mov r13,[rcx+0xc0]`); `0x035E9F00 4d85ed 750c`;
  `0x035E9F25 4d85ed 0f8479120000`
* **predicate:** `GetWorld() == nullptr`. `[CMC+0xC0]` is read first; **only if it is NULL** does
  `0x035E9F05 call 0x035AFC40` run (`UActorComponent::GetWorld` — reads `[this+0xB8]` Owner, flag
  test, else walks `[this+0x28]` Outer). `r13` has **0 writers** between `0x035E9F0D` and the test.
* **field:** `UActorComponent::WorldPrivate @CMC+0xC0`, 8 bytes, on the CMC itself.
* **measured?** YES — brief table `World | CMC+0xC0 | non-null`.
* **same object?** **YES [M]**. And because it is non-null, the `GetWorld()` fallback never runs, so
  the tested value **is** the measured qword.
* **verdict: PASSES.**

### EXIT 3 — `0x035E9F97 je 0x035EB7CF`
* **raw:** `0x035E9F7F 4533ff` (`xor r15d,r15d`); `0x035E9F90 4438bb31020000 0f8432180000`
* **predicate:** `MovementMode == 0` (`MOVE_None`). `r15b == 0` — `r15` has **0 writers** between the
  `xor` and the `cmp`.
* **field:** `UCharacterMovementComponent::MovementMode @CMC+0x231`, **1 byte**, on the CMC itself.
* **measured?** YES — **3** (`MOVE_Falling`) on both bot and player, same offset.
* **same object?** **YES [M]** (`rbx`).
* **verdict: PASSES.** Unaffected by this build's `MOVE_Dashing` insertion — the test is against
  literal 0, and `MOVE_None == 0` under every ordering.

### EXIT 4 — `0x035E9FA4 jne 0x035EB7CF`
* **raw:** `0x035E9F9D 80b9bb010000 02 0f8525180000`
* **predicate:** `UpdatedComponent->Mobility != 2` (`EComponentMobility::Movable`).
* **field:** `USceneComponent::Mobility @UpdatedComponent+0x1BB`, **1 byte**, on the
  **UpdatedComponent**, i.e. `[CMC+0xD0]` — **not** the CMC.
* **measured?** YES — brief table `Mobility | UpdatedComponent+0x1BB | 2`.
* **same object?** **YES [M]** — `rcx` was loaded from `[rbx+0xD0]` at `0x035E9F2E` and has 0 writers
  through this instruction.
* **verdict: PASSES.**

### EXIT 5 — `0x035E9FBD jne 0x035EB7CF`  <- the one the S140 handoff called unread
* **raw:** `0x035E9FAA 488b01 418bd7 4c897c2478`; `0x035E9FB5 ff90c0040000`;
  `0x035E9FBB 84c0 0f850c180000`
* **predicate:** `UpdatedComponent->IsSimulatingPhysics(BoneName = NAME_None)` returned **true**.
  Note `0x035E9FAD mov edx, r15d` => **arg2 (BoneName) = 0 = NAME_None**; the `bGetWelded = TRUE` the
  S139 note mentions is set **inside** the callee, not here (`0x03C9B0B8 mov r8b,1`).
* **virtual resolve:** `rax = [rcx]` where `rcx = UpdatedComponent`, so this is the
  **UpdatedComponent's** vtable at displacement `0x4C0` — **NOT the CMC's**.
  * **NEAR-MISS I CAUGHT:** my first automated pass resolved `+0x4C0` through the ULokiCMC vtable and
    produced `0x055AB8C0`, a completely unrelated function. That is CLAUDE.md's "never sample a byte
    offset across unrelated vtables" trap. The correct answer follows.
  * `.rdata` holds the VA of `UPrimitiveComponent::IsSimulatingPhysics 0x03C9B0A0` **99 times**.
  * **90** of those sit at `(vtable + 0x4C0)` of a vtable whose `+0x810` is
    `GetBodyInstance 0x03C91C60`.
  * Across those **90 vtables the number of DISTINCT `+0x4C0` values is exactly 1** — `0x03C9B0A0`.
    **Zero overrides.** (Two-sided control: the same 90 vtables agree on `+0x810` as well.)
  * Grade of `0x03C9B0A0`: **REAL** (32-byte prologue quoted above). Not any of the 5 folds, not the
    6th stub shape.
* **fields:** `UPrimitiveComponent::WeldParent @UpdatedComponent+0x5F0` (8 bytes) and
  `FBodyInstance @UpdatedComponent+0x3F0`, byte `+0x10` bit 0 (`bSimulatePhysics`).
* **measured?** YES — brief table: `WeldParent NULL`, `bSimulatePhysics 0`.
* **same object?** **YES [M]** — `bGetWelded=1` but `WeldParent == NULL`, so `GetBodyInstance`
  falls to `lea rax,[rcx+0x3f0]`, the exact `BodyInstance` the probe read.
* **verdict: PASSES [M].** `[BI+0x10] & 1 == 0` short-circuits `0x01E2F940` at its **first
  instruction** (`f6411001 / 746b` -> `0x01E2F9B7 = 32c0 4883c420 5b c3` = `xor al,al; ret`).
* **residual (small; here is the one-qword read that removes it):** I could not identify
  `UCapsuleComponent`'s vtable by name offline (`.rdata` class literals are UHT prefix-stripped and I
  found no unambiguous anchor). The 90/90 result is a strong bound but is anchored on
  `+0x810 == GetBodyInstance`; 9 of the 99 occurrences are not in such a vtable (their `+0x810` reads
  `0x0388F9E0` x5, the fold `0x00F7EB50` x3, `0x05DCCD30` x1 — most likely those 9 are not at a
  slot-`0x4C0` position at all). **To close with zero residual: one live qword read of
  `*(void**)UpdatedComponent`, subtract ImageBase, read `[vt+0x4C0]`; if it is `0x03C9B0A0`, done.**
  Also note the live reads are snapshots, not samples taken at the instant of the call.

### EXIT 6 — `0x035EA25D je 0x035EB150`  <- NOT a mandatory gate
* **raw:** `0x035EA255 ff90b8060000`; `0x035EA25B 84c0 0f84ed0e0000`
* **predicate:** `!HasValidData()` — **the same function and the same three fields as EXIT 1**
  (`[rax+0x6b8]`, `rax = [rbx]`, `rcx = rbx`).
* **structural context [M]:** only reached when
  `HasRootMotionSources() && !CharacterOwner->bClientUpdating && !CharacterOwner->bServerMoveIgnoreRootMotion`
  **and** `CharacterOwner->IsPlayingRootMotion() && CharacterOwner->GetMesh() != nullptr`, after
  `TickCharacterPose(DeltaSeconds)` (`[CMC vt+0xB68] = 0x03603640`, REAL) has run. Dominator analysis
  says it does **not** dominate the call.
  * `0x035E6470` = `HasRootMotionSources()`:
    `CurrentRootMotion(this+0xD58).HasActiveRootMotionSources() || (CharacterOwner && IsPlayingRootMotion() && GetMesh())`.
  * `0x03536040` = `ACharacter::IsPlayingRootMotion()`:
    `mov rcx,[rcx+0x450]; test; je -> false; jmp [Mesh_vt+0xBA0]` => **[M] `ACharacter::Mesh @ +0x450`.**
* **measured?** Its own three fields: YES (same as EXIT 1). Its *guard* fields:
  **`[CharacterOwner+0x580]` and the root-motion group have NOT been read live.**
* **same object?** YES [M].
* **verdict:** PASSES if EXIT 1 passed and `TickCharacterPose` did not destroy the character. Since
  the bot survives indefinitely, that is [I, strong]. **Almost certainly never even evaluated.**
* **to settle outright:** read `[CMC+0xD58..+0xD68]` (`FRootMotionSourceGroup`) and
  `[CharacterOwner+0x450]` (Mesh). One RPM pass.

---

## 3. FREE BY-PRODUCT: `ACharacter+0x580` IS FULLY NAMED [M]

The brief flags `[CharacterOwner+0x580] & 8` (at Loki `PerformMovement 0x055B845E`) as
"**an unread live byte**". It is now named, without a live read. I found the 11 consecutive UHT
`SetBitFunc` bodies for `[rcx+0x580]` in `.text` and walked back from each `.rdata` occurrence of the
function pointer to the record's `NameUTF8`:

| mask | SetBitFunc (`.text`) | record ptr (`.rdata`) | name |
|---|---|---|---|
| 0x001 | `0x0350C240` | `0x07F8F0B8` | `bIsCrouched` (RepNotify `OnRep_IsCrouched`) |
| 0x002 | `0x0350C250` | `0x07F8F0F8` | `bProxyIsJumpForceApplied` |
| 0x004 | `0x0350C260` | `0x07F8F138` | `bPressedJump` |
| **0x008** | **`0x0350C270`** (`83898005000008c3`) | `0x07F8F178` | **`bClientUpdating`** |
| 0x010 | `0x0350C300` | `0x07F8F1B8` | `bClientWasFalling` |
| 0x020 | `0x0350C310` | `0x07F8F1F8` | `bClientResimulateRootMotion` |
| 0x040 | `0x0350C320` | `0x07F8F238` | `bClientResimulateRootMotionSources` |
| 0x080 | `0x0350C330` | `0x07F8F278` | `bSimGravityDisabled` |
| 0x100 | `0x0350C340` | `0x07F8F2B8` | `bClientCheckEncroachmentOnNetUpdate` |
| **0x200** | **`0x0350C350`** (`81898005000000020000c3`) | `0x07F8F2F8` | **`bServerMoveIgnoreRootMotion`** |
| 0x400 | `0x0350C360` | `0x07F8F338` | `bWasJumping` |

**Positive control:** the order is **exactly** stock UE `Character.h`'s declaration order, 11/11, and
each SetBitFunc body is a single `or [rcx+0x580], <mask>; ret` matching its record. This is the S136
`SetBitFunc` method (correct — `FBoolPropertyParams` carries no `ByteOffset`/`ByteMask`).
=> **`test byte [CharacterOwner+0x580],8` is `bClientUpdating`; `bt eax,9` is
`bServerMoveIgnoreRootMotion`.** For a locally-simulated `ROLE_Authority` pawn both should be 0
(`bClientUpdating` is set only inside `ClientUpdatePositionAfterServerUpdate`). **[I, strong] on the
expected value; [M] on the names.**

---

## 4. OTHER `[M]` FACTS BANKED ON THE WAY

* **`.rdata 0x07FBED58` = engine `UCharacterMovementComponent` vtable** (5/5 named-slot control).
  **`.rdata 0x088F8570` = `ULokiCharacterMovementComponent` vtable** (3/3 control).
* CMC vtable slots used on the mandatory path, all graded **REAL** (none FOLD, none DARK):
  `+0x610 -> 0x055B1EC0` (Loki override; `cmp byte[rcx+0x231],7 / cmp byte[rcx+0x232],3` — an
  `IsMovingOnGround`-shaped test, and note **7 = MOVE_Custom in this build**) ·
  `+0x6F0 -> 0x035E7760` · `+0x750 -> 0x055AEB60` · `+0x808 -> 0x055A15B0` · `+0x810 -> 0x035D8B70`
  (`ClearAccumulatedForces`, zeroes `[this+0x3A0]`; **not** overridden by Loki) ·
  `+0x818 -> 0x036061D0` · `+0xB68 -> 0x03603640` (`TickCharacterPose`) · `+0x720 -> 0x055C2430`.
* `[CharacterOwner_vt + 0xA08]` at `0x035EB120` = **[I, strong]** `ACharacter::ClearJumpInput(dt)` —
  immediately followed by `mov dword [rbx+0x3DC], 0` = `NumJumpApexAttempts = 0`, the exact stock
  pairing. I did **not** identify `ACharacter`'s vtable, so I do not grade this [M].
* There is exactly **one** `[+0x720]` call in the whole 1461-instruction function, and **three**
  `[+0x6B8]` (`HasValidData`) calls: `0x035E9F17` (exit 1), `0x035EA255` (exit 6), `0x035EB146`
  (**after** the StartNewPhysics call — not an exit of interest; its fallthrough IS `0x035EB150`,
  which is why exit 6 and the post-call check share a target).
* `.rdata 0x07FC0548` is the log record for `LogRootMotion` line **2919**, verbosity **5 (Log)**,
  format `"PerformMovement WorldSpaceRootMotion Translation: %s, Rotation: %s, Actor Facing: %s, Velocity: %s"`,
  emitted at `0x035EAFDD call 0x106B650` with category object `.data 0x09F80598`
  (**merged-image `.data`** — trap #9 — it reads `Verbosity=3(Warning) Default=3
  CompileTime=7(VeryVerbose)`, i.e. **not compiled out but suppressed by default**). It is **inside
  `R`**, so it is a *positive* receipt, not a bail receipt — but it fires only with active root
  motion, which the bot does not have. **Not useful as a receipt for this bug.**
* Log-record layout (validated on the line-3477 control): `+0x00 format wchar*`, `+0x08 file wchar*`,
  `+0x10 line u32`, `+0x14 verbosity u32`, `+0x18 ptr into .data`, `+0x20 0`.

---

## 5. WHAT I COULD **NOT** ESTABLISH OFFLINE

1. **Whether engine `PerformMovement 0x035E9EC0` is entered at all.** That is L1's question (does
   Loki `PerformMovement` reach its Super at `0x055B85C1`). Nothing in my lane touches it. Given
   H1-H4, "never entered" is the only surviving explanation I can see that does not require one of
   the banked live measurements to be wrong — but **I did not test it and I am not asserting it.**
2. **The exact class of `UpdatedComponent`,** hence a zero-residual resolve of `[vt+0x4C0]`.
   One live qword read closes it (§2 EXIT 5).
3. **`[CharacterOwner+0x580]` live value** — named but not read. Needed only for exit 6 and for the
   Loki-side branch at `0x055B845E`.
4. **`HasRootMotionSources()`'s live inputs** (`CMC+0xD58` group, `CharacterOwner+0x450` Mesh) —
   would turn exit 6's "almost certainly not evaluated" from [I, strong] into [M].
5. **`[CMC+0x3E4] MaxSimulationIterations`** — a fourth engine `StartNewPhysics` early-out that is
   downstream of the latch, so irrelevant to latch==0, but unread.
6. **Whether anything else clears `CMC+0x16C8`** — explicitly assigned to lane A4; my H4 assumes it
   does not.

---

## 6. FINAL ROW-PER-EXIT SUMMARY

| # | addr | bails when | field + offset | owning object | measured? | same object? | to settle |
|---|---|---|---|---|---|---|---|
| 1 | `0x035E9F1F je 0x35EB1A7` | `!HasValidData()` = `UpdatedComponent==0 OR CharacterOwner==0 OR RF_Garbage` | `+0xD0`(8) · `+0x198`(8) · `CharOwner+0x0C` bit30 | CMC / CMC / CharacterOwner | **YES x3** | **YES [M]** | nothing — **PASSES** |
| 2 | `0x035E9F28 je 0x35EB1A7` | `GetWorld()==null` | `+0xC0`(8) | CMC | **YES** | **YES [M]** (non-null so fallback skipped) | nothing — **PASSES** |
| 3 | `0x035E9F97 je 0x35EB7CF` | `MovementMode == 0 (MOVE_None)` | `+0x231`(1) | CMC | **YES (=3)** | **YES [M]** | nothing — **PASSES** |
| 4 | `0x035E9FA4 jne 0x35EB7CF` | `Mobility != 2 (Movable)` | `+0x1BB`(1) | **UpdatedComponent** (`[CMC+0xD0]`) | **YES (=2)** | **YES [M]** | nothing — **PASSES** |
| 5 | `0x035E9FBD jne 0x35EB7CF` | `UpdatedComponent->IsSimulatingPhysics()` | `+0x5F0`(8) WeldParent · `+0x3F0+0x10` bit0 | **UpdatedComponent** / its `FBodyInstance` | **YES (NULL, 0)** | **YES [M]** | 1 qword: is `[*(void**)UpdatedComponent + 0x4C0] == 0x03C9B0A0`? — **PASSES** |
| 6 | `0x035EA25D je 0x35EB150` | `!HasValidData()` after `TickCharacterPose` | same 3 as #1 | CMC / CharacterOwner | **YES x3**; guards NOT measured | **YES [M]** | read `CMC+0xD58` group + `CharOwner+0x450` + `CharOwner+0x580` — **not a mandatory gate** |

**Bottom line.** All five mandatory gates pass on measured values, on provably the same objects, with
the enumeration proved complete by backward-reachability *and* dominators; exit 6 is off the mandatory
path; and `r8d == 0` at the call means the latch would have fired. The contradiction therefore does
**not** live inside engine `PerformMovement`. It lives upstream — in whether engine `PerformMovement`
is entered at all.

---

## 7. REPRODUCTION

Scripts (all read-only, all offline) in `scratchpad/s140/lanes/L2work/`:
`dump.py` (CFG-ordered listing) · `exits.py` (exit set) · `dom.py` (dominators) · `fwd.py` (bail-path
forward reachability + rip-refs) · `riprefs.py` · `rec.py` (log-record decoder) · `logcat.py`
(engine StartNewPhysics + log category) · `vt.py`/`vt2.py`/`vt3.py`/`vt4.py` (vtable resolution +
controls) · `bitfn.py`/`uht.py` (SetBitFunc -> name) · `prov.py` (register provenance) ·
`subcls.py` (vtable uniqueness) · `mandcalls.py` · `bailcallees.py` · `raw.py` (raw byte evidence).
