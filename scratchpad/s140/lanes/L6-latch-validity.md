# L6 / TASK A4 — IS THE `CMC+0x16C8` LATCH INSTRUMENT VALID?

**VERDICT: NO. The instrument is INVALID for an external between-frames read.**
`CMC+0x16C8` is **set at the start of the physics step and cleared at the end of the same
`PerformMovement` call**, by a Loki override of a *different* vtable slot that nobody had looked at.
`latch == 0` is the resting state of a **fully working** component. The S139 reading
*"`StartNewPhysics` has NEVER RUN on either component"* is **not supported by that measurement**.

Offline only. Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, FLAT (va==praw, 10/10
sections — re-verified). Every RVA below recomputed by machine. Scripts: `scratchpad/s140/L6/*.py`.

---

## 0. THE ANSWER IN SIX LINES [M]

```
LokiCMCvt+0x720 = 0x055C2430  ULokiCMC::StartNewPhysics
    0x055C2438  cmp byte [rcx+0x16C8], r8b     ; r8b==0  -> TOptional::Reset()
    0x055C2441  mov byte [rcx+0x16C8], r8b     ;   (only if it was set)
    0x055C2448..0x055C2466  snapshot Velocity (+0xE8/+0xF8) -> +0x16B0/+0x16C0
    0x055C2469  mov byte [rcx+0x16C8], 1       ; *** SET ***
    0x055C2470  jmp 0x03600990                 ; tail -> engine StartNewPhysics

LokiCMCvt+0xA50 = 0x0530ABF0  (Loki override; engine slot = 0x035D6790)
    0x0530ABF0  cmp byte [rcx+0x16C8], 0
    0x0530ABF7  je  0x0530AC00
    0x0530ABF9  mov byte [rcx+0x16C8], 0       ; *** CLEARED ***
    0x0530AC00  jmp 0x035D6790                 ; tail -> Super

engine PerformMovement 0x035E9EC0:
    0x035EB129  xor r8d,r8d                    ; Iterations = 0
    0x035EB13A  call [rax+0x720]               ; -> SET
      ... the whole movement body ...
    0x035EB569  call [rax+0xA50]               ; -> CLEARED
    ret
```

**Strict ordering [M]:** `0x035EB569` **is** forward-reachable from `0x035EB13A`; `0x035EB13A` is
**not** forward-reachable from `0x035EB569` (CFG over 1461 instructions, 0 indirect jumps,
0 decode failures). The **only** `ret` reachable from the StartNewPhysics call while avoiding the
slot-0xA50 call is `0x035EB1CA`, reached when `HasValidData()` (slot `0x6B8`, called at
`0x035EB146`) returns **false**.

⇒ On any normal frame the flag is 1 for the duration of the PerformMovement body and **0
everywhere else**. An asynchronous RPM sample taken between frames reads 0 whether or not
`StartNewPhysics` ran. **Zero discriminating power.**

---

## 1. TASK 4 FIRST (it is the load-bearing precondition) — VTABLE DISPATCH RE-DERIVED [M]

`.rdata` in a dumped image holds absolute VAs; ImageBase subtracted by machine.

**Positive controls (answers known in advance) — 5/5 PASS:**

| disp | raw qword | rva | expected | result |
|---|---|---|---|---|
| `0xAA8` | `0x7FF60E4F8370` | `0x055B8370` | `0x055B8370` | **PASS** ULokiCMC::PerformMovement |
| `0x3D0` | `0x7FF60E502B90` | `0x055C2B90` | `0x055C2B90` | **PASS** ULokiCMC::TickComponent |
| `0x890` | `0x7FF60E4E7680` | `0x055A7680` | `0x055A7680` | **PASS** ControlledCharacterMove |
| `0xA38` | `0x7FF60E4E75B0` | `0x055A75B0` | `0x055A75B0` | **PASS** ConstrainInputAcceleration |
| `0x830` | `0x7FF60E4F89F0` | `0x055B89F0` | `0x055B89F0` | **PASS** PhysFalling |

**THE ANSWER:** `.rdata 0x088F8570 + 0x720` = `0x00007FF60E502430` ⇒ **`0x055C2430`. PASS.**

Second, independent confirmation — the **engine** `UCharacterMovementComponent` vtable was located
from scratch (the *only* aligned `.rdata` qword equal to `IB + 0x03600990`, at `0x07FBF478`, giving
start `0x07FBED58`) and cross-checked on five more knowns:

```
EngCMCvt+0xAA8 = 0x035E9EC0 PerformMovement    PASS
EngCMCvt+0x720 = 0x03600990 StartNewPhysics    PASS
EngCMCvt+0x890 = 0x035DCD10 ControlledCharMove PASS
EngCMCvt+0x6B8 = 0x035E64C0 HasValidData       PASS
EngCMCvt+0x4E0 = 0x0364BA80 ShouldSkipUpdate   PASS
```

**[M] There is exactly ONE aligned `.rdata` qword equal to `IB+0x055C2430`, and exactly one equal
to `IB+0x055B8370`** ⇒ no C++ subclass of `ULokiCharacterMovementComponent` with its own vtable
exists in this image. So the live component's slot `0x720` **is** `0x055C2430` and its slot `0xA50`
**is** `0x0530ABF0`.

**The call site [M]** — note `xor r8d,r8d`, which independently confirms the brief's item 2:

```
0x035EB126  48 8b 03              mov rax, [rbx]        ; rbx = this (the CMC), rax = vptr
0x035EB129  45 33 c0              xor r8d, r8d          ; *** Iterations = 0 ***
0x035EB12C  41 0f 28 cb           movaps xmm1, xmm11    ; DeltaSeconds
0x035EB130  44 89 bb dc 03 00 00  mov [rbx+0x3DC], r15d
0x035EB137  48 8b cb              mov rcx, rbx
0x035EB13A  ff 90 20 07 00 00     call [rax+0x720]
```

---

## 2. TASK 1 — CENSUS OF EVERY READ/WRITE OF DISPLACEMENT `0x16C8`

### 2.1 Method (two independent instruments; both stated as FLOORS)

**Instrument #1 — superset byte generator + CFG adjudication.**
`0x16C8 > 0x7F`, so it can **never** be encoded as disp8: any `[reg+0x16C8]` (and any 32-bit
immediate `0x16C8`) must contain the bytes `c8 16 00 00`. A byte search for that pattern over
`.text` is therefore a **strict SUPERSET** of the encodings present in the bytes we hold — not a
floor at this step. It returned **67 candidate byte positions across 47 pages** in 0x7649000 bytes
of `.text`. Each candidate was mapped to its containing `pdata_union.csv` function and adjudicated
by **recursive-descent CFG + capstone operands** (never by the byte pattern), with a **linear sweep
over [begin,end) as a second opinion**. 6 candidates had no `pdata` row and were adjudicated by a
backward instruction-start probe (try starts D−1 … D−15, accept only if the decoded instruction
covers the disp bytes *and* carries the operand).

**GENERATOR POSITIVE CONTROL — 3/3:** disp-byte positions `0x055C243B`, `0x055C2444`, `0x055C246B`
(for the three mandated sites) were all **FOUND**.

**ADJUDICATION POSITIVE CONTROL — 3/3:** the CFG of `0x055C2430` returns exactly
`0x055C2438`, `0x055C2441`, `0x055C2469`. *(My first pass FAILED this control because
`pdata_union.csv` has no row covering `0x055C2430`; I did not paper over it — I built the fallback
and re-ran. That failure is itself informative: the pdata union is from 2026-08-14 and is **not** a
complete function map for merged13.)*

**Instrument #2 — vtable-driven.** CFG **every** one of the 413 `LokiCMCvt` + 413 `EngCMCvt` slot
targets (392 distinct; **375 lit**, 17 dark) and scan operands for disp `0x16C8`. Result: 9 hits in
5 functions, and **instrument#2 is a SUBSET of instrument#1 with zero contradictions**
(only-in-#1 = empty, only-in-#2 = empty once keyed by instruction address).

**FLOOR STATEMENT.** `.text` is ~55.5 % demand-decrypted. A writer on an all-zero page is invisible,
and a write through a **register-computed** address or a `memset`/whole-struct copy is invisible to
any displacement scan. See §5 for how far I can bound that.

### 2.2 Result — 63 instructions image-wide touch byte `+0x16C8` via a disp32

Full raw table in `scratchpad/s140/L6/hits.json` + `prov.json`. Base-register provenance was
resolved by walking instruction-graph predecessors to the reaching definitions.

**Cleanly eliminated by provenance (machine-derived, not asserted):**

* **35 sites are STACK, not objects** — every one has `base rbp <- lea rbp, [rsp - N]` in its
  prologue (e.g. `0x048418A0: lea rbp,[rsp-0x2D10]`), or is `[rsp+0x16C8]`.
* **Every `movups/movaps xmmword [X+0x16C8]` site is NOT a Loki CMC** — `ULokiCMC` has a *byte* at
  `+0x16C8` and 8-byte/16-byte fields at `+0x16C0`/`+0x16B0` (proved by `0x055C2430`, where `rcx` is
  unambiguously `this`); a 16-byte vector *at* `+0x16C8` is a contradicting layout. Corroborated
  independently for three of them by provenance: `0x055A6BCB` (`rsi <- [rdi+0x198]`), `0x055C0304`
  (`rbx <- [rbx+0x198]`), `0x055BE974` (called from PerformMovement `0x055B862D` with
  `rcx = CharacterOwner`).
* **`0x05292040` / `0x05513A00`** write a **dword** at `+0x16C0` where the CMC has a double ⇒
  different class.
* **`0x055B860B  mov byte [r15+0x16C8], 0`, inside `ULokiCMC::PerformMovement` — NOT the CMC. [M]**
  This one looked like the answer and is not. `r15` is defined twice in the function:
  `0x055B8381 mov r15,[rcx+0x198]` (= `CharacterOwner`; the brief's own live table gives
  `CMC+0x198 == pawn`, and engine `PerformMovement` loads `[rbx+0x198]` **21 times**) and
  `0x055B83A6 xor r15d,r15d` on the failing arm of a cast check (`0x055B839D call 0x054F8C40`).
  The write is guarded by `0x055B85C6 test r15,r15 / je`, so at `0x055B860B` `r15` is a **non-null,
  cast-checked `CharacterOwner`**. Its neighbours (`[r15+0x16CC]`, `[r15+0x16D0]`, `[r15+0x16EC]`,
  `[r15+0x16F0]` array, `[r15+0x16F8]` count) are the **character-side** layout, matching
  `0x055C0D30` (which reaches `[rbx+0x458]` = `ACharacter::CharacterMovement` and calls the same
  `0x055BE930`). Classic same-offset-different-class trap; it is not a CMC write.

**The 7 instructions that DO touch `ULokiCharacterMovementComponent + 0x16C8`:**

| rva | instruction | function | role |
|---|---|---|---|
| `0x055C2438` | `cmp byte [rcx+0x16C8], r8b` | `LokiCMCvt+0x720` StartNewPhysics | Reset() test |
| `0x055C2441` | `mov byte [rcx+0x16C8], r8b` | same | Reset() store (r8b = 0) |
| `0x055C2469` | `mov byte [rcx+0x16C8], 1` | same | **SET** |
| `0x0530AB43` | `cmp byte [rbx+0x16C8], 0` | `LokiCMCvt+0x0` **deleting destructor** | Reset() test |
| `0x0530AB4C` | `mov byte [rbx+0x16C8], 0` | same | destruction-time clear |
| `0x0530ABF0` | `cmp byte [rcx+0x16C8], 0` | `LokiCMCvt+0xA50` **override** | Reset() test |
| `0x0530ABF9` | `mov byte [rcx+0x16C8], 0` | same | ***THE PER-FRAME CLEAR*** |

Plus **one constructor**: `0x0559FDF4 mov byte [rdi+0x16C8], sil` (sil = 0) in `0x0559F580`.

**Class identification of the ctor/dtor is [M], from object size, not from a guess:** the deleting
destructor executes `0x0530ABD2 mov edx, 0x19D0` before `call 0x00F7EC20` — i.e.
`sizeof(ULokiCharacterMovementComponent) == 0x19D0`, exactly the figure the repo already records
("do NOT whole-struct diff a 0x19D0-byte component"). `0x0559F580` writes members up to **`+0x19C8`**
(< `0x19D0`, > `sizeof(ALokiCharacter)==0x1950`) and touches `+0x1988` — a CMC field that
`ULokiCMC::PerformMovement` reads via `rsi = this`. The rival candidate `0x0559E180` writes up to
`+0x1938` and touches `+0x1090` (`ALokiCharacter::LivingState`) ⇒ it is the **character**
constructor, and its `mov word [r14+0x16C8], bp` is a character-side zero-init, not a CMC write.

---

## 3. TASK 2 — WHAT `+0x16B0` / `+0x16C0` / `+0x16C8` ARE, AND THE CONSUMER

**[M] It is a `TOptional<FVector>`-shaped saved-state field, and the CMC method is named
`GetRecentVelocity`.**

* Payload `+0x16B0 .. +0x16C7` = 3 doubles (an `FVector`, LWC). Flag `+0x16C8` = 1 byte.
* `StartNewPhysics(Iterations==0)` performs `Reset()` then `Emplace(Velocity)`:
  `movups [rcx+0x16B0] <- [rcx+0xE8]`, `movsd [rcx+0x16C0] <- [rcx+0xF8]`, `byte[+0x16C8] = 1`.
  The `cmp/je/mov 0` triple at `0x055C2438` is **not a "redundant store"** — it is the standard
  `TOptional::Reset()` idiom, and the **identical three-instruction idiom appears verbatim** in the
  destructor (`0x0530AB43`) and in the slot-0xA50 override (`0x0530ABF0`).

**THE CONSUMER, and it is decisive [M].** `0x0559C560`:

```
0x0559C590  call 0x055AC8E0            ; ULokiCMC* ALokiCharacter::GetLokiCharacterMovement()
0x0559C595  test rax, rax
0x0559C598  je   0x0559C8EE            ; null -> bail
0x0559C59E  cmp byte [rax+0x16C8], 0   ; *** THE FLAG ***
0x0559C5A5  mov  ecx, 0x16B0
0x0559C5B2  mov  edx, 0xE8
0x0559C5BF  cmove ecx, edx             ; flag==0 -> use 0xE8 (Velocity); else 0x16B0
0x0559C5E2  movsd  xmm0, [rcx+rax+0x10]
0x0559C5F0  movups xmm6, [rcx+rax]
```

`0x055AC8E0` is `mov rbx,[rcx+0x458]; <IsA check 0x0554A1A0>; return rbx|null` — and the repo
already records `0x055AC8E0` as `GetLokiCharacterMovement`, so `rax` is **provably** a Loki CMC.
⇒ the field is *"the velocity at the start of this physics step, if we are inside one; otherwise the
current velocity."*

**The consumer does NOT clear the flag** — it only reads it. Three code instances of the identical
`flag ? +0x16B0 : +0xE8` selection exist: `0x0530AC10`, `0x0530C7FF`, `0x0559C59E`.

### 3.1 TASK 3 — NAMING [M for the method; "no UPROPERTY" also [M]]

`.data` `{name_ptr, exec_thunk, impl}` record:

```
.data 0x09BC9AD0 = { name -> .rdata 0x088F1FB8 "GetRecentVelocity",
                     thunk 0x0530C7E0,  impl 0x0530AC10 }
```

**POSITIVE CONTROL on the record-table instrument** — the same lookup for a name whose impl the repo
already records:

```
.data 0x09BC4B60 = { name -> "GetLokiCharacterMovement", thunk 0x05300710, impl 0x055AC8E0 }
                                                                          ^^^^^^^^^ matches repo
```

`0x0530AC10` is exactly the standalone accessor found by the census, with the MSVC ABI for
`FVector f() const` (`rcx=this`, `rdx=&ret`, `mov rax,rdx` on exit). The thunk `0x0530C7E0` contains
the third inlined copy at `0x0530C7FF`.

**[M] There is NO reflected UPROPERTY for these fields.** `tools/asdump/out/binds_members.csv` lists
**169 properties** for `ULokiCharacterMovementComponent` (index 4183) and none is a velocity
snapshot / optional; the only related entry is the **method** `FVector GetRecentVelocity() const`
(member 28). *Absence of a UPROPERTY is not absence of a field* — the field is plainly there.

⇒ Working names: `+0x16B0` RecentVelocity (payload), `+0x16C8` bRecentVelocitySet. The exact source
identifiers are **[I]**, from the accessor's name.

---

## 4. THE CLEARING PATH — WHY THE LATCH IS PER-FRAME

`LokiCMCvt+0xA50 = 0x0530ABF0` (**the only vtable in the image that references it**;
`EngCMCvt+0xA50 = 0x035D6790`, which is itself a real function —
`mov rax,[rcx]; call [rax+0x518]; mov rcx,[rbx+0x198]` — **not** a destructor).

⚠ **A linear read here is a trap I nearly fell into:** the bytes at `0x0530ABEA`
(`sub rsp,0x28; xor ebp,ebp`) sit immediately after the destructor's `ret` at `0x0530ABE9` and
decode as a plausible prologue, but the **vtable entry is `0x0530ABF0`**, six bytes later, and the
function is a prologue-less leaf that tail-jumps. Reading it from `0x0530ABEA` would have described
a function that does not exist.

**Who calls slot `0xA50`?** Superset byte scan for disp32 `0xA50` (268 candidates → 208 pdata
functions → CFG adjudication) found **29 real `call [reg+0xA50]` sites**. Cross-checked against the
per-function indirect-call disp sets:

```
ULokiCMC::TickComponent              0xA50 absent
engine CMC TickComponent             0xA50 absent
ULokiCMC::ControlledCharacterMove    0xA50 absent
engine ControlledCharacterMove       0xA50 absent
ULokiCMC::PerformMovement            0xA50 absent
engine PerformMovement               0xA50 PRESENT   <-- 0x035EB569
```

**The site [M]:**

```
0x035EB554  mov rax, [rbx]           ; rbx = this (the CMC)
0x035EB557  lea r9,  [rbp+0x18]      ; &FVector
0x035EB55B  lea r8,  [rbp+0xE8]      ; &FVector
0x035EB562  movaps xmm1, xmm11       ; DeltaSeconds
0x035EB566  mov rcx, rbx
0x035EB569  call [rax+0xA50]
```

**[I, strong] slot `0xA50` is `UCharacterMovementComponent::OnMovementUpdated(float DeltaSeconds,
const FVector& OldLocation, const FVector& OldVelocity)`** — from the
`(this, float, const FVector&, const FVector&)` signature, its position at the tail of
`PerformMovement` (followed by `SaveBaseLocation`-shaped `[rax+0x708]/[rax+0x710]` and
`[rax+0x518]`), and the callee reading `movups xmm0,[rdi]` from the `r9` vector. The name has **no
ASCII occurrence** in the image (`OnMovementUpdated`, `StartNewPhysics`, `PerformMovement` all
return 0 ASCII hits, against `GetRecentVelocity` = 1 as the passing control) — it is not AS-bound,
so no name record exists. **Nothing in this lane's verdict depends on the name; the mechanism is [M].**

**Ordering, computed on the instruction graph [M]:**

```
|forward-reachable from 0x035EB13A| = 359
|forward-reachable from 0x035EB569| = 155
0x035EB569 in fwd(0x035EB13A)  -> True     (A50 comes AFTER StartNewPhysics)
0x035EB13A in fwd(0x035EB569)  -> False    (no loop back)
rets reachable from 0x035EB13A avoiding 0x035EB569 -> [0x035EB1CA] only
```

and `0x035EB1CA` is reached solely via `0x035EB14E jne 0x035EB1CB` **not taken**, i.e.
`HasValidData()` false immediately after the physics step.

**The set is unconditional on its path [M]:** in `CFG(0x055C2430)` the flag is untouched on the
`Iterations != 0` arm — `0x055C2469` is **not** forward-reachable from the `jne`-taken edge
`0x055C2475` — and on the `Iterations == 0` arm the only branch (`je 0x055C2448`) merges before the
store. Recursive `StartNewPhysics(dt, Iterations>0)` calls from `PhysFalling`/`PhysWalking`
therefore never disturb it.

**Net semantics [M]:**

| when sampled | flag |
|---|---|
| inside `PerformMovement`, between `0x035EB13A` and `0x035EB569` | **1** |
| anywhere else (incl. between frames, which is where RPM samples) | **0** |
| after a `HasValidData()`-false abort at `0x035EB14E` | **1** (rare, pathological) |

---

## 5. HOW FAR THE CENSUS CAN BE TRUSTED (the honest floor)

* **Dark-page hole is small and named.** Of the 826 CMC vtable slot entries (392 distinct targets),
  **17 are on all-zero pages**. Of the **64 slots where Loki overrides the engine, exactly ONE is
  dark**: `disp 0xCD8 -> 0x055A2290` (engine counterpart is the `true` fold `0x00B9E1F0`, so it is a
  bool getter override — an unlikely clearer, but I cannot read it). **63/64 Loki overrides were
  CFG-scanned.**
* **Every function on the movement path is LIT** (page non-zero counts): `TickComponent` 3626/3466,
  `StartNewPhysics` 3626/3705, `ControlledCharacterMove` 3710/3767, `PerformMovement` 3578/3454,
  slot `0xA50` 3883/3567, `HasValidData` 3628, `ShouldSkipUpdate` 3685, `PhysFalling` 3578/3610.
  **Dark-page control passed:** `ULokiRespawnComponent::Respawn 0x05A6AC40` = **0/4096**.
  ⇒ **[I, strong]** a *per-frame* clearer would be on this path and would be lit; I do not believe
  one is hiding in the dark 44.5 %.
* **Genuinely not covered:** a write through a register-computed address, or a `memset` /
  whole-struct copy over the component. The 6 `imm32 == 0x16C8` sites found (`0x03E2D792` an `imul`
  stride, and five in the `0x06E8xxxx`–`0x06E92xxx` net-serialisation band) are all far outside the
  CMC and none is CMC-shaped. I found **no** such site, but I cannot prove absence.
* `pdata_union.csv` (2026-08-14) is **not** a complete function map for merged13 — it lacked rows for
  `0x055C2430`, `0x0530ABF0`, `0x0530AC10`, `0x0530C7E0`, `0x04B03CC6`. All were recovered by the
  fallback; a lane relying on it alone would silently miss them.

---

## 6. VERDICT, AND WHAT IT DOES AND DOES NOT CHANGE

**"latch == 0 proves `StartNewPhysics` never ran with Iterations==0" is UNSOUND.** [M]
There is a clearing path — `LokiCMCvt+0xA50` (`0x0530ABF0`), called at `0x035EB569` at the tail of
every engine `PerformMovement` — which makes `+0x16C8` a **within-call scratch flag**, not a latch.
An external RPM read between frames returns 0 in *both* worlds.

**Consequences that must be re-graded:**

1. **S139's "`ULokiCMC::StartNewPhysics 0x055C2430` HAS NEVER RUN on either component"** and **"all
   37 CMCs read latch 0"** — both rest on this instrument and are now **UNINTERPRETABLE, not
   negative**. So is the derived framing *"the wall is between `0x055B8414` and `0x035EB13A`"*.
2. **The brief's item 2** ("SOUND for *did PerformMovement reach StartNewPhysics*") is correct only
   for a sample taken **inside** the call; its own warning ("whether anything ELSE clears +0x16C8 is
   an OPEN question") is now answered: **yes, `LokiCMCvt+0xA50` does, every frame.**
3. **Not refuted by this lane:** `Velocity == (0,0,0)`, the pawn translating 0.00 uu, and a
   `MOVE_Falling` pawn with `GravityScale 1.0` not falling. Those are independent observations and
   still need an explanation. **I am removing evidence *against* `StartNewPhysics` running; I am not
   supplying evidence *for* it.** The honest state is *unknown*.
4. A **second**, independent reason the latch was never a good instrument: `0x055C2469` executes
   **before** the tail-jmp into engine `StartNewPhysics`, so even a flag caught at 1 would prove only
   that the *vtable dispatch* happened — nothing about the engine's `MIN_TICK_TIME` /
   `MaxSimulationIterations` / `HasValidData` / `IsSimulatingPhysics` gates at `0x036009A8`,
   `0x036009B5`, `0x036009C5`, `0x036009E4`.

---

## 7. THE READ THAT WOULD ACTUALLY SETTLE IT (offline-derived; NOT run)

Polling `+0x16C8` externally is hopeless — the 1-window is a few microseconds of a 16 ms frame.
**Use the payload instead. It is durable: `OnMovementUpdated` clears only the FLAG at `+0x16C8`;
nothing in the census writes `+0x16B0`/`+0x16C0` except the `StartNewPhysics` Emplace, the two
constructors, and unrelated classes. [M]**

**THE VELOCITY-SENTINEL TEST** — one 24-byte write, one 24-byte read, no injection, no `.text`:

1. Write a distinctive sentinel into `CMC+0xE8/+0xF0/+0xF8` (`Velocity`), e.g.
   `(1234.5, 6789.25, -4242.125)` — values no physics code would produce.
2. Wait at least a few frames.
3. Read `CMC+0x16B0 .. +0x16C7`.

* payload **== the sentinel** ⇒ **`ULokiCMC::StartNewPhysics` ran with `Iterations == 0`** [M].
* payload **stays (0,0,0)** while `+0xE8` still reads the sentinel ⇒ it did **not** run.

The test is discriminating precisely because the snapshot is taken *before* the engine's gates, and
because a resting `Velocity` of `(0,0,0)` makes the normal payload indistinguishable from
never-written — which is why the sentinel is required.
⚠ It needs an external `WriteProcessMemory`, which `CLAUDE.md` flags as an **unresolved hazard**
(one use, client died ~44 s later, n=1, confounded). Pair it with a matched no-write sitting.
⚠ Positive control for the probe itself: read back `+0xE8` after the poke; if the sentinel is not
there the run is void.

A write-free alternative with the same logic: `LogCharacterMovement=Log` in the user `Engine.ini`
turns the engine `StartNewPhysics`'s own `IsSimulatingPhysics` abort into a per-frame log line
(`.rdata 0x07FC0670`) — that is L2's lane, and it answers a neighbouring but different question.

---

## 8. ADDRESSES DETERMINED IN THIS LANE

```
0x088F8570   ULokiCharacterMovementComponent vtable          (413 slots; 64 Loki overrides)
0x07FBED58   UCharacterMovementComponent vtable  [NEW]       (located from scratch, 5 controls)
0x055C2430   LokiCMCvt+0x720  ULokiCMC::StartNewPhysics      (confirmed)
0x0530AAA0   LokiCMCvt+0x0    ULokiCMC vector deleting dtor  [NEW]  (mov edx,0x19D0)
0x0530ABF0   LokiCMCvt+0xA50  ULokiCMC::<OnMovementUpdated>  [NEW]  *** clears +0x16C8 ***
0x035D6790   EngCMCvt+0xA50   engine <OnMovementUpdated>     [NEW]
0x035EB569   engine PerformMovement's call [rax+0xA50]       [NEW]  *** the clear site ***
0x0530AC10   ULokiCMC::GetRecentVelocity  (impl)             [NEW]  name-record confirmed
0x0530C7E0   ULokiCMC::GetRecentVelocity  (exec thunk)       [NEW]  inlines accessor @0x0530C7FF
0x09BC9AD0   .data {name,thunk,impl} record for GetRecentVelocity
0x0559F580   ULokiCMC constructor (writes +0x16C8 = 0)       [NEW]
0x0559C560   a GetRecentVelocity consumer (inlined)          [NEW]
0x0559E180   ALokiCharacter constructor (NOT the CMC)        [NEW]
0x055C0D30   ALokiCharacter method writing Character+0x16C8  [NEW]
0x055BE930   ALokiCharacter helper (called from PerformMovement 0x055B862D w/ rcx=CharacterOwner)
0x054F8C40   the cast check guarding r15 in ULokiCMC::PerformMovement

ULokiCMC field map: +0x16B0 RecentVelocity (FVector, 3 doubles)
                    +0x16C8 bRecentVelocitySet (bool)
                    sizeof(ULokiCharacterMovementComponent) = 0x19D0
```
