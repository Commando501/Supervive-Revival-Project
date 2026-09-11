# S140 TIER 2 — LANE 3: THE THREE FREE READS, VERIFIED FROM THE BINARY

Offline. Zero launches, zero injection, zero live process touched.

Image: `dumps/merged13.dump.exe` (file-offset == RVA; ImageBase `0x7FF608F40000`; `.text` 55.48 %
decrypted — **every census below over `.text` is a FLOOR, not a count**).
`.rdata`/`.data`: `merged13` is a **`.text`-only** merge, so its `.rdata`/`.data` come from one seed.
All `.rdata` reads below are section-invariant across images (FK-3/FK-18: `.rdata` is not
demand-decrypted). The **one `.data` read** (§5, the log-category verbosity byte) is a MUTABLE
global and is graded accordingly.
Second image: `dumps/tutorial-hero/…dump.exe` for `tools/re/propoffset.py` (UHT oracle, `.rdata`
only; its built-in positive control was run first and PASSED 2/2).

---

## HEADLINE — THE ONE THING THAT CHANGES A PLANNED EXPERIMENT

**⚠⚠ READING `CMC+0xC0` DOES *NOT* SETTLE EXIT 2. IT IS ONE-SIDED.**

Engine `PerformMovement` does **not** load a field and test it. It emits the **inlined
`UActorComponent::GetWorld()`**: load `[this+0xC0]`, and **if that is NULL make a direct call to
`UActorComponent::GetWorld_Uncached()` (`0x035AFC40`)** and test *that* result instead.

```
0x035e9eee  4c 8b a9 c0 00 00 00   mov  r13, [rcx+0xC0]      ; WorldPrivate  (the "free read")
0x035e9ef5  44 0f 28 d9            movaps xmm11, xmm1
0x035e9ef9  4c 89 6d 90            mov  [rbp-0x70], r13
0x035e9efd  48 8b d9               mov  rbx, rcx             ; rbx = this  (Tier 1's 2-writer proof)
0x035e9f00  4d 85 ed               test r13, r13
0x035e9f03  75 0c                  jne  0x35e9f11            ; non-null -> skip the fallback
0x035e9f05  e8 36 5d fc ff         call 0x35afc40            ; <-- UActorComponent::GetWorld_Uncached
0x035e9f0a  4c 8b e8               mov  r13, rax
0x035e9f0d  48 89 45 90            mov  [rbp-0x70], rax
0x035e9f11  48 8b 13               mov  rdx, [rbx]           ; ---- EXIT 1 ----
0x035e9f14  48 8b cb               mov  rcx, rbx
0x035e9f17  ff 92 b8 06 00 00      call [rdx+0x6b8]          ; HasValidData()
0x035e9f1d  84 c0                  test al, al
0x035e9f1f  0f 84 82 12 00 00      je   0x35eb1a7            ; EXIT 1
0x035e9f25  4d 85 ed               test r13, r13             ; ---- EXIT 2 ----
0x035e9f28  0f 84 79 12 00 00      je   0x35eb1a7            ; EXIT 2
0x035e9f2e  48 8b 8b d0 00 00 00   mov  rcx, [rbx+0xD0]      ; UpdatedComponent
```

**Exact answer to the question asked:** at `0x035E9F1F..0x035E9F30` there is **no load and no call
at all** — that range is the two `je`s and one `test`. The value being tested (`r13`) was produced
**13 instructions earlier** at `0x035E9EEE` by a **direct field load**, with a **direct
(non-virtual) call fallback** at `0x035E9F05`. **It is NOT a virtual call, so there is no vtable
slot to name.** The ABI-clobber objection does not apply: `r13` is callee-saved and the only `call`
in between (`0x035E9F17`) preserves it by ABI.

**Probe rule — put this in the probe, not in a comment:**

| observed `*(u64*)(CMC+0xC0)` | verdict on exit 2 |
|---|---|
| **non-NULL** | **exit 2 PASSES — [M], settled, done.** |
| **NULL** | **UNSETTLED.** `GetWorld_Uncached()` still runs and may return non-null. Needs `+0xB8` and `+0x28` too. |

A NULL is the interesting case and it costs two more qwords (§1.3). Read all three
unconditionally — it removes the branch from the analysis.

---

## 1. `CMC+0xC0` == `UActorComponent::WorldPrivate`

### 1.1 The fallback is named, from four independent structural facts

`0x035AFC40`, transcribed to both its `ret`s:

```
0x035afc40  40 53                 push rbx
0x035afc42  48 83 ec 20           sub  rsp, 0x20
0x035afc46  48 8b d9              mov  rbx, rcx
0x035afc49  48 8b 89 b8 00 00 00  mov  rcx, [rcx+0xB8]   ; OwnerPrivate  (GetOwner())
0x035afc50  48 85 c9              test rcx, rcx
0x035afc53  74 14                 je   0x35afc69
0x035afc55  8b 41 0c              mov  eax, [rcx+0x0C]   ; ObjectFlags  (CLAUDE.md: ObjectFlags@0x0C)
0x035afc58  c1 e8 04              shr  eax, 4            ; bit 4 = 0x10 = RF_ClassDefaultObject
0x035afc5b  a8 01                 test al, 1
0x035afc5d  75 0a                 jne  0x35afc69
0x035afc5f  e8 2c cd dd ff        call 0x338c990         ; AActor::GetWorld()
0x035afc64  48 85 c0              test rax, rax
0x035afc67  75 20                 jne  0x35afc89         ; -> return it
0x035afc69  48 8b 5b 28           mov  rbx, [rbx+0x28]   ; OuterPrivate  (stock UObjectBase offset)
0x035afc6d  48 85 db              test rbx, rbx
0x035afc70  74 15                 je   0x35afc87
0x035afc72  48 8b cb              mov  rcx, rbx
0x035afc75  e8 b6 bc a7 ff        call 0x302b930         ; IsA(UWorld::StaticClass())
0x035afc7a  84 c0                 test al, al
0x035afc7c  74 09                 je   0x35afc87
0x035afc7e  48 8b c3              mov  rax, rbx          ; -> Cast<UWorld>(GetOuter())
       ...  33 c0 / c3            xor eax,eax ; ret      (both tails)
```

A line-for-line match to stock UE's `UActorComponent::GetWorld_Uncached()`: GetOwner, skip if the
owner is a CDO, `MyOwner->GetWorld()`, else `Cast<UWorld>(GetOuter())`.
**[M]** on the structure; **[I, strong]** on the *name* `GetWorld_Uncached` (no string exists; the
name comes from UE source, not from this binary).

Callee identifications, both **[M]**, both named by their own wide literals:

- `0x0302B930` calls `0x03F5CB90`, which loads `L"World"` (`.rdata 0x0825D352`) and
  `L"/Script/Engine"` ⇒ `0x03F5CB90` = **`UWorld::StaticClass()`** ⇒ `0x0302B930` is an
  `IsA<UWorld>` test. It reads `[obj+0x18]` = `ClassPrivate` — this build's non-stock `classOff =
  0x18` (CLAUDE.md), an independent corroboration that the object model is being decoded correctly.
- `0x0338C990` does the `RF_ClassDefaultObject` guard, then `GetTypedOuter<ULevel>` via
  `0x01365EE0` with `0x039B48C0` (which loads `L"Level"` + `L"/Script/Engine"` ⇒
  **`ULevel::StaticClass()`**), then `mov rax,[level+0xC8]` = `ULevel::OwningWorld`
  ⇒ **`AActor::GetWorld()`**, again a line-for-line stock match.

### 1.2 The `+0xC0` fast path is the component-generic `GetWorld` idiom — population control

Image-wide direct references to `0x035AFC40` in `.text` (**FLOOR — 55.48 % decrypted**):

```
direct CALL sites : 964
direct JMP  sites :   7      (outlined UActorComponent::GetWorld bodies)
```

Of the 964 call sites, **777 (80.6 %)** have a `mov r64,[reg+0xC0]` within the preceding 48 bytes.

**Two-sided negative control — same window, same scan code:**

| target | call sites | preceded by a `+0xC0` load |
|---|---:|---:|
| **`0x035AFC40`** (the claim) | 964 | **777 (80.6 %)** |
| `0x0302B930` (its own callee) | 38 | 3 (7.9 %) |
| `0x0338C990` = `AActor::GetWorld` | 1050 | 1 (**0.1 %**) |

The 187 non-hits are expected (load >48 B earlier, or the register already live — e.g. in
`PerformMovement` itself the gap is 23 bytes, so it counts as a hit).

**The seven tail-`jmp` sites are the decisive shape** — four of them are literally the whole
one-line body:

```
0x0344fa39  48 8b 81 c0 00 00 00   mov rax,[rcx+0xC0]
0x0344fa40  48 85 c0               test rax,rax
0x0344fa43  75 07                  jne 0x344fa4c      ; return WorldPrivate
0x0344fa45  e9 f6 01 16 00         jmp 0x35afc40      ; else GetWorld_Uncached()
0x0344fa4a  33 c0                  xor eax,eax
0x0344fa4c  c3                     ret
```

Same at `0x03797136` and `0x045D44E2`; also at `0x055A4660` and `0x055C2B70` (those two decode
mid-instruction in a naive linear sweep — the bytes are present).

**⇒ `CMC+0xC0` is `UActorComponent`'s cached `UWorld*`, on every component class, and it is the
first operand of `GetWorld()`. [M].** The *name* `WorldPrivate` is **[I, strong]** — it is not a
`UPROPERTY` (§1.4) so it has no literal anywhere.

### 1.3 What a probe must read, and what each combination means

```
w   = *(u64*)(CMC + 0xC0)              // WorldPrivate
own = *(u64*)(CMC + 0xB8)              // OwnerPrivate  (AActor*)
out = *(u64*)(CMC + 0x28)              // OuterPrivate  (UObject*)
ofl = own ? *(u32*)(own + 0x0C) : 0    // ObjectFlags; bit 0x10 = RF_ClassDefaultObject
```

- `w != 0` ⇒ **exit 2 passes [M]. Stop.**
- `w == 0 && own != 0 && !(ofl & 0x10)` ⇒ the answer is
  `GetTypedOuter<ULevel>(own)->OwningWorld` (`ULevel+0xC8`) — **not readable in one hop; report RAW
  and say UNSETTLED.**
- `w == 0` and that yields null ⇒ falls to `Cast<UWorld>(out)`.
- `w == 0 && own == 0 && out == 0` ⇒ **exit 2 FAILS [M]** — the only combination that settles it
  negatively in one pass.

Report the four raw values. **Do not report a derived boolean only** (S140 recorded defect; and
S139's `distinct Acceleration values: 1` is the same failure).

### 1.4 Honest negative, with its control

`WorldPrivate` and `OwnerPrivate` are **not reflected**: `tools/re/propoffset.py` returns **0 ASCII
literals** for either — in the *same run* where its built-in controls (`CheatManager`, `CheatClass`)
and `MaxSimulationIterations` / `MaxSimulationTimeStep` / `MaxAcceleration` / `MaxStepHeight` /
`GravityScale` all resolved. **So the UHT oracle cannot corroborate `+0xC0`; that is an instrument
limit, not a negative result.** The structural route in §1.1–§1.2 is the only one, and it suffices.

---

## 2. ENGINE `StartNewPhysics 0x03600990` — FULL TRANSCRIPTION AND EVERY EARLY-OUT

**Extent `0x03600990 .. 0x03600BF6` (615 bytes)**, followed by its 8-entry jump table at
`0x03600BF8`. Two `ret` sites (`0x03600A56`, `0x03600BF5`); no loop; **no `.pdata` row covers it**
in `tools/strxref/index/pdata_union.csv` (blind on dark pages by construction — do not build a
function filter on it).

**It names itself. [M]:** the log record at `.rdata 0x07FC0648` holds
`L"UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is simulating physics - aborting."`,
file `…\Engine\Source\Runtime\Engine\Private\Components\CharacterMovementComponent.cpp`, and
`{Line = 0x0D95 = 3477, Verbosity = 5 (Log)}`. Strongest possible identity control, and it agrees
with `CLAUDE.md` exactly.

### 2.1 The complete early-out set — FIVE exits, all forward, all to `0x03600BE6` (the epilogue)

| # | address | bytes | condition | bails when |
|---|---|---|---|---|
| **A** | `0x036009A8` / `AF` | `0f 2f 35 c5 84 0b 04` / `0f 82 31 02 00 00` | `comiss xmm6,[rip+0x40B84C5]` ; `jb` | **`DeltaTime < 1e-6f`**. The constant at `.rdata 0x076B8E74` is raw `0x358637BD` = `9.99999997e-07` = UE's `MIN_TICK_TIME` |
| **B** | `0x036009B5` / `BC` | `44 3b 81 e4 03 00 00` / `0f 8d 24 02 00 00` | `cmp r8d,[rcx+0x3E4]` ; `jge` | **`Iterations >= MaxSimulationIterations`**. On the `PerformMovement` path `Iterations == 0`, so it bails **iff `MaxSimulationIterations <= 0`** |
| **C** | `0x036009C2` / `C5` / `CD` | `48 8b 01` / `ff 90 b8 06 00 00` / `0f 84 13 02 00 00` | `call [vt+0x6B8]` = `HasValidData()` ; `je` | **`!HasValidData()`** — the **THIRD** evaluation of this predicate on the chain |
| **D** | `0x036009D3`..`0x03600A56` | `48 8b 8b d0 00 00 00` … `ff 90 c0 04 00 00` / `74 69` | `UpdatedComponent->[vt+0x4C0]()` = `IsSimulatingPhysics()` ; **`je 0x3600a57` jumps away when FALSE** | **bails when it returns TRUE** — falls through into the log block and `ret`s at `0x03600A56` |
| **E** | `0x03600A7B` / `7E` | `83 fe 07` / `0f 87 b1 00 00 00` | `cmp esi,7` ; `ja 0x3600b35` | `MovementMode > 7` — **not an exit**: takes the "unsupported movement mode" Warning path, then `SetMovementMode` via `[vt+0x670]`, and rejoins at `0x03600BA8` |

**⚠ `0x036009EE cmp byte [rip+0x6985473],5 / jb 0x3600be6` is NOT a sixth exit.** It is the
verbosity gate *inside* exit D; both arms end at `0x03600BE6`. The abort happens either way — only
the log line is conditional.

**⚠ EXIT D's `this` is `UpdatedComponent`, NOT the CMC** — `rcx` is reloaded from `[rbx+0xD0]` at
`0x036009D3`. This is the SAME predicate as engine `PerformMovement`'s exit 5, on the same object,
and Tier 1 measured it passing (`bSimulatePhysics == 0`, `WeldParent == NULL`, with
`bEnableGravity == 1` as the same-byte two-sided decode control). **⇒ exit D is already answered
[M] and needs no re-read.**

### 2.2 The dispatch (not an exit, but nobody had transcribed it)

`0x03600A84 lea rdx,[rip-0x3600a8b]` ⇒ **`rdx = ImageBase`**; then
`0x03600A8B mov ecx,[rdx + rsi*4 + 0x3600BF8]` ; `add rcx,rdx` ; `jmp rcx`.
So the 8 dwords at `.text 0x03600BF8` are **RVAs**:

| `MovementMode` | table entry | body | vtable disp |
|---|---|---|---|
| 0 `MOVE_None` | `0x03600BA8` | — | **none: jumps straight to the tail** |
| 1 `MOVE_Walking` | `0x03600A97` | `call [vt+0x970]` | `0x970` |
| 2 `MOVE_NavWalking` | `0x03600AAE` | `call [vt+0x978]` | `0x978` |
| 3 `MOVE_Falling` | `0x03600AC5` | `call [vt+0x830]` | `0x830` |
| 4 `MOVE_Swimming` | `0x03600AF3` | `call [vt+0x988]` | `0x988` |
| 5 `MOVE_Flying` | `0x03600ADC` | `call [vt+0x980]` | `0x980` |
| 6 `MOVE_Dashing` (Loki) | `0x03600B0A` | `call [vt+0xCC8]` | `0xCC8` |
| 7 `MOVE_Custom` | `0x03600B21` | `call [vt+0x990]` | `0x990` |

Each body passes `xmm1 = DeltaTime`, `r8d = Iterations`, `rcx = this`. **`cmp esi,7` bounds the
table at 8**, independently reproducing CLAUDE.md's "`MOVE_Dashing` inserted at 6, `MOVE_Custom ==
7`, `MOVE_MAX == 8`". The `Phys*` **names** are `[I, strong]` (stock enum order); the
**case-index → displacement** mapping is `[M]`.

Tail (`0x03600BA8`..): restores the `+0x2E8` bit `0x40` set at `0x03600A75`, then
`test byte [rbx+0x2EA],8` → if set, `call [vt+0x4F8]` with `rdx = [rbx+0x2F0]`
(`DeferredUpdatedMoveComponent`, UHT-confirmed at `+0x2F0`).

### 2.3 ⚠⚠ `ULokiCMC::StartNewPhysics 0x055C2430` CONTRIBUTES **ZERO** EXITS — IT TAIL-JUMPS IN, BOTH ARMS

```
0x055c2436  75 3d                    jne 0x55c2475               ; Iterations != 0
   ... Iterations == 0 arm, the snapshot:
0x055c244f  0f 11 81 b0 16 00 00     movups [rcx+0x16B0], xmm0   ; payload, from Velocity +0xE8 (16 B)
0x055c245e  f2 0f 11 89 c0 16 00 00  movsd  [rcx+0x16C0], xmm1   ; payload tail, from +0xF8 (8 B)
0x055c2469  c6 81 c8 16 00 00 01     mov byte [rcx+0x16C8], 1
0x055c2470  e9 1b e5 03 fe           jmp 0x3600990               ; ENGINE StartNewPhysics
   ... Iterations != 0 arm:
0x055c2496  e9 f5 e4 03 fe           jmp 0x3600990               ; ENGINE StartNewPhysics
```

⇒ **the five early-outs in §2.1 are the ONLY early-outs in the entire `StartNewPhysics` step. [M]**

**⚠⚠ SCOPE LIMIT ON THE S141 SENTINEL TEST THAT NOBODY HAS WRITTEN DOWN:** the payload
`+0x16B0..+0x16C7` is written **BEFORE** the jump into the engine body. A sentinel appearing there
proves **`ULokiCMC::StartNewPhysics` was ENTERED with `Iterations == 0`** — exactly what Tier 1
claims, and no more. It does **NOT** show the engine body ran, and it does **NOT** show any `Phys*`
dispatch happened: exits A–D all sit *downstream* of the payload write. Report a positive sentinel
as *"entered `ULokiCMC::StartNewPhysics`"*, never as *"the physics step ran"*. Adding the four
reads in §6 to the same probe closes exactly that gap (A/B/C are then all readable; D is already
`[M]`).

---

## 3. THE TWO VTABLE ANCHORS — RE-VERIFIED FROM A DIFFERENT DIRECTION

I did **not** re-quote Tier 1's displacement table. Independent evidence:

### 3.1 The constructor installs it. [M]

```
ULokiCMC ctor 0x0559F580:
  0x0559f592  e8 89 41 dc fb                 call 0x1363720           ; FObjectInitializer plumbing
  0x0559f59d  e8 3e fe 02 fe                 call 0x35cf3e0           ; <- UCharacterMovementComponent::ctor
  0x0559f5a2  c7 87 40 11 00 00 00 80 bb 44  mov dword [rdi+0x1140], 0x44BB8000   ; 1500.0f, a Loki field
  0x0559f5ac  48 8d 05 bd 8f 35 03           lea rax,[rip -> .rdata 0x088F8570]
  0x0559f5b3  48 89 07                       mov [rdi], rax           ; <- vptr store at object offset 0
```

Textbook derived-class emission: base ctor, own members, **then overwrite the vptr**.
⇒ `ImageBase + 0x088F8570` **is** the value a live `ULokiCMC`'s `*(void**)this` holds. **[M]**

Self-consistency: slot 0 of that table is `0x0530AAA0`, a vector-deleting destructor whose first act
is `lea rax,[→0x088F8570]; mov [rcx],rax`, plus secondary vptrs at `+0x30`, `+0x188`, `+0x190`
(three interfaces — `IRVOAvoidance` / `INetworkPrediction` / `IRootMotionMovement`, `[I]` on the
names). The engine table's slot 0 (`0x035D1320`) calls `0x035D0180`, whose first acts are
`lea rax,[→0x07FBED58]; mov [rcx],rax` **and the same three secondary vptrs at the same three
offsets**. Two classes, one interface layout — exactly what inheritance predicts.

### 3.2 The base class is named by its own literals, and the base ctor writes five stock defaults. [M]

`0x035CF3E0` — the base ctor the Loki ctor calls — writes:

```
0x035cf90c  mov dword [rbx+0x3E0], 0x3D4CCCCD   ; MaxSimulationTimeStep            = 0.05f    (stock)
0x035cf917  mov dword [rbx+0x3E4], 8            ; MaxSimulationIterations          = 8        (stock)
0x035cf921  mov dword [rbx+0x3E8], 2            ; MaxJumpApexAttemptsPerSimulation = 2        (stock)
0x035cf92b  mov dword [rbx+0x3DC], r12d         ; NumJumpApexAttempts              = 0        (see §4.1)
0x035cfa29  mov dword [r11+0x28C], 0x45000000   ; MaxAcceleration                  = 2048.0f  (stock)
0x035cfa6d  mov dword [r11+0x300], 0x42C80000   ; Mass                             = 100.0f   (stock)
```

**Five stock UE default values in one function** — an identity control independent of both UHT and
vtables. And its class-registration singleton `0x035CAF50` loads
`L"CharacterMovementComponent"` (`.rdata 0x07FAF492`) + `L"/Script/Engine"`.

### 3.3 Cross-table structure

- Image-wide **aligned `.rdata` qword** occurrences (unique — no ICF, no second table):
  `0x035E9EC0` → 1, at `ENG+0xAA8`; `0x055B8370` → 1, at `LOKI+0xAA8`;
  `0x03600990` → 1, at `ENG+0x720`; `0x055C2430` → 1, at `LOKI+0x720`.
  Four function pairs landing at two identical displacements is only possible if both bases are the
  same class's table base.
- Over the first 512 slots: **449 are `.text` pointers in both tables and 380 (84.6 %) are
  IDENTICAL** — the inheritance signature. Misaligned bases would give ~0 %.
- Loki **overrides** `0x670` SetMovementMode, `0x720` StartNewPhysics, `0x830` PhysFalling,
  `0x990` PhysCustom, `0xA50` (the `+0x16C8` clear), `0xAA8` PerformMovement.
  Loki **does NOT override** `0x4F8`, `0x6B8` HasValidData, `0x970` / `0x978` / `0x980` / `0x988`,
  and — notably — `0xCC8` **PhysDashing** (`0x035EB870`, identical in both).
  ⇒ **`MOVE_Dashing` lives in the *engine* class**, corroborating that Loki forked engine source
  rather than subclassing. Its property array (§4) carries `DashDeflectedMovementMultiplier @0xFF8`
  and `CurrentDashInstance @0x1000` for the same reason.

**⚠ WHAT I HAD TO CORRECT MID-LANE, because it will trip the next person:** a naive "walk back while
the qword is a `.text` pointer" finds a contiguous run starting at `0x088F7B58` / `0x07FBE360`,
**~320 slots before** each claimed base. Those are **adjacent, unrelated vtables** — `.rdata` packs
vtables back to back with no separator, and *both* candidates have their own `mov [this],rax`
install sites. **A contiguous-pointer run is not a vtable.** The ctor-install evidence (§3.1) is
what separates them; the run-boundary heuristic cannot.

### 3.4 EXACTLY how a probe computes the live vptr

```c
// base = the LIVE module base of SUPERVIVE-Win64-Shipping.exe in the target process.
// NEVER hardcode 0x7FF608F40000 -- that is merged13's ImageBase, not a live base.
uint64_t expect_loki   = base + 0x088F8570;   // ULokiCharacterMovementComponent
uint64_t expect_engine = base + 0x07FBED58;   // plain UCharacterMovementComponent  (the alternative)
uint64_t vptr = *(uint64_t*)CMC;              // object offset 0
```

- `vptr == expect_loki` → **ULokiCMC.** disp `0x720` → `0x055C2430`, disp `0xA50` → `0x0530ABF0`.
  `+0x16C8` / `+0x16B0` exist and are written. Every S139/S140 offset applies.
- `vptr == expect_engine` → **plain engine CMC.** disp `0x720` → `0x03600990` DIRECTLY.
  **Nothing writes `+0x16C8` or `+0x16B0`** — the sentinel test is VACUOUS on such an object, and a
  null result would be an instrument artifact, not a game fact.
- neither → a third class. **STOP**, report the raw vptr, and do not interpret the `0x16xx` family.

Both S139 flights' banked offsets (`0xD0 0xE8 0x160 0x198 0x231 0x28C 0x328 0x3D0 0x12B0`) are valid
under **either** answer, since every one is a `UCharacterMovementComponent` member (§4). Only the
`0x16xx` family is Loki-only.

---

## 4. BONUS — `+0x3E0`, `+0x3E4`, `+0x3DC`, RESOLVED

`tools/re/propoffset.py` (UHT `FPropertyParams` oracle; its own control PASSED 2/2 first):

| offset | name | UHT type | record |
|---|---|---|---|
| `0x3E0` | **`MaxSimulationTimeStep`** | Float | `.rdata 0x07FB0808` |
| `0x3E4` | **`MaxSimulationIterations`** | Int | `.rdata 0x07FB0840` |
| `0x3E8` | `MaxJumpApexAttemptsPerSimulation` | Int | (adjacent) |
| `0x3DC` | **no reflected property exists** | — | — |

**Both offsets CONFIRMED. [M]** — and the *ownership* is proven, not assumed. Both records' single
aligned `PropPointers` slots (`0x07FB1E40`, `0x07FB1E48`) lie inside **one 164-entry array
`.rdata 0x07FB1BB0..0x07FB20D0`**, whose `FClassParams` (`~0x07FB23D0`, `ClassConfigNameUTF8 =
"Engine"`) names `0x035CAF50`, which loads `L"CharacterMovementComponent"` + `L"/Script/Engine"`.

⚠ `MaxSimulationIterations` and `MaxSimulationTimeStep` each have **three** `FPropertyParams`
records image-wide (the other two at `+0x1A0`/`+0x1D0` and `+0x198`/`+0x1CC` belong to other
movement-component classes). **Do not take an offset from a name search alone — resolve which class
array the record sits in.**

**Two positive controls inside that same array**, both matching values other sessions measured
live: `CharacterOwner @0x198` (Tier 1's exit-1 input) and `MaxAcceleration @0x28C` (CLAUDE.md,
banked). Also confirmed there: `MovementMode @0x231`, `Acceleration @0x328`,
`AnalogInputModifier @0x3D0`, `Mass @0x300`, `DeferredUpdatedMoveComponent @0x2F0`. Every offset
this lane touched, from one instrument, all agreeing with live reads from other sessions.

**Defaults [M], from the ctor bytes in §3.2:** `MaxSimulationTimeStep = 0.05f`,
**`MaxSimulationIterations = 8`**, `MaxJumpApexAttemptsPerSimulation = 2`.
**`ULokiCMC`'s ctor does not override any of them** — byte-anchored scan of
`0x0559F580..0x0559FE60` for disps `0x3DC/0x3E0/0x3E4/0x3E8`: **0 hits**, in a scan that finds all
six writes in the base ctor (the passing control).
⚠ A Blueprint CMC class can still override the CDO, so **the probe must read it**; `8` is the
prediction, not the answer.
⇒ **Exit B is expected to PASS** (`0 < 8`). It bails only if something has written
`MaxSimulationIterations <= 0`. That is exactly why it is worth one dword.

### 4.1 `+0x3DC` — Tier 1's `[I]` upgraded to **[M]**: it IS `NumJumpApexAttempts`

Byte-anchored scan (anchor on the `dc 03 00 00` disp32, then decode backwards):

```
0x035ece5d  8b 9f dc 03 00 00   mov  ebx, [rdi+0x3DC]      ; the counter
0x035ece63  3b 9f e8 03 00 00   cmp  ebx, [rdi+0x3E8]      ; vs MaxJumpApexAttemptsPerSimulation
0x035ece69  0f 8d 25 07 00 00   jge  0x35ed594             ; give up on the apex
   ...
0x035ecff6  8d 43 01            lea  eax, [rbx+1]
0x035ecffc  89 87 dc 03 00 00   mov  [rdi+0x3DC], eax      ; counter++
```

Read → compare against `MaxJumpApexAttemptsPerSimulation` → increment. Stock UE's `PhysFalling`
does exactly `if (NumJumpApexAttempts < MaxJumpApexAttemptsPerSimulation) { … NumJumpApexAttempts++; }`.
And Tier 1's `0x035EB130 mov [rbx+0x3DC], r15d` with `r15d == 0` in `PerformMovement` is the
per-frame reset, also stock.
**⇒ `CMC+0x3DC = NumJumpApexAttempts`, non-reflected. [M].** Free for a probe already reading the
neighbourhood; it should read `0`.

⚠ **INSTRUMENT NOTE, and it cost me a false negative first:** a linear `capstone` sweep over
`0x035C0000..0x03660000` returned **0** instructions with disp `0x3DC` while the byte
`44 89 a3 dc 03 00 00` is plainly at `0x035CF92B`. Linear disassembly desynchronises and stays
desynchronised. **Anchor on the displacement bytes and decode backwards** — that scan returns 157
sites image-wide.

---

## 5. FREE BY-PRODUCT — THE LOG-CATEGORY GATE, AND A CORRECTION TO "UNINTERPRETABLE"

Three `LogCharacterMovement` records, decoded. Record layout:
`+0x00` format string · `+0x08` file · `+0x10 {u32 Line, u32 Verbosity}` · `+0x18` function.

| record | text | line | verbosity |
|---|---|---:|---:|
| `0x07FC0648` | `UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is simulating physics - aborting.` | 3477 | **5 = Log** |
| `0x07FC0740` | `%s has unsupported movement mode %d` | 3510 | 3 = Warning |
| `0x07FC0548` | `PerformMovement WorldSpaceRootMotion Translation: %s, …` | 2919 | 5 = Log |

All three agree with `CLAUDE.md` exactly. The category object is `.data 0x09F85E68` — both
`0x036009F5`'s `cmp byte [rip+0x6985473],5` and `0x03600A2F`'s `lea rcx,[rip+0x6985439]` resolve
there, reproducing Tier 1's two derivations.

**⚠ [I], and flagged as a `.data` read:** in merged13's `.data` seed the four bytes read
`Verbosity = 5, DebugBreakOnLog = 0, DefaultVerbosity = 5, CompileTimeVerbosity = 7`.
`DefaultVerbosity` is written once at registration so `5` is robust for it; `Verbosity` is mutable
and this is a single seeded snapshot — **read it live before leaning on it.**

**If live `Verbosity >= 5`,** then S139's *"`LogCharacterMovement` occurs 0 times, so the zero is
UNINTERPRETABLE"* is **too pessimistic**: the abort line's own gate would pass, so its absence
becomes a real negative on exit D. And the missing positive control is then **explained rather than
suspicious** — the only three sites in this area are the three above, and two of them require root
motion or an out-of-range `MovementMode`, neither of which occurs. **One read-only byte at
`.data 0x09F85E68` converts a standing "uninterpretable" into a measurement.** It is the cheapest
item on this whole list.

---

## 6. WHAT TO ADD TO ANY S141 PROBE (all read-only, all one hop)

```
CMC+0x00    u64   vptr                       expect base+0x088F8570 (ULokiCMC), else base+0x07FBED58
CMC+0x28    u64   OuterPrivate               exit-2 fallback #2
CMC+0xB8    u64   OwnerPrivate               exit-2 fallback #1
CMC+0xC0    u64   WorldPrivate               EXIT 2 -- non-null settles it; NULL does NOT
CMC+0x3DC   i32   NumJumpApexAttempts        expect 0
CMC+0x3E0   f32   MaxSimulationTimeStep      expect 0.05
CMC+0x3E4   i32   MaxSimulationIterations    expect 8    -- engine StartNewPhysics exit B
.data 0x09F85E68  u8  LogCharacterMovement.Verbosity   expect 5
```

Report RAW. `CMC+0xD0`, `+0x198`, `+0x231`, `UpdatedComponent+0x1BB`, and the capsule's `+0x3F0` /
`+0x5F0` are already `[M]` from S139 and need no re-read.

---

## 7. WHAT THIS LANE DID **NOT** ESTABLISH

- **No live value was read.** Every number here is from the image.
- `WorldPrivate` / `OwnerPrivate` / `NumJumpApexAttempts` / `GetWorld_Uncached` **names** are
  `[I, strong]` (UE source). The **offsets and the semantics** are `[M]`.
- The `Phys*` **names** behind disps `0x970/0x978/0x830/0x980/0x988/0xCC8/0x990` are `[I]` from the
  stock enum order; only case-index → displacement is `[M]`.
- The three secondary-interface names in §3.1 are `[I]`; only "three secondary vptrs at
  `+0x30/+0x188/+0x190` in both classes" is `[M]`.
- `0x035AFC40`'s 964-call-site census is a **FLOOR** — `.text` is 55.48 % decrypted. Every `.text`
  count in this file carries the same caveat.
- I did **not** re-derive Tier 1's CFG/dominance results for engine `PerformMovement`. §2 is the
  *callee*, which Tier 1 did not transcribe.
- I did not establish which class owns the adjacent vtables at `0x088F7B58` / `0x07FBE360`; only
  that they are **not** the CMC tables.
