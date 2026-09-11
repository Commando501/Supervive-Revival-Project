# L6 / T3-D — per-instance attribute set (no CDO poke) + T3-C player-arm prep

Session S141 Tier 3, lane L6. **OFFLINE ONLY** — zero launches, zero injection, zero live-process
writes. Image `dumps/merged14.dump.exe`, ImageBase `0x7FF608F40000`, FLAT verified.
Tools: `scratchpad/s141/tools/peimg.py`, `scratchpad/s141/tools/grade.py` (written this lane),
`scratchpad/s141/tools/controls_l6.py`, `tools/strxref/strxref.py` (DEFAULT_DUMP already merged14).

---

## 0. MANDATORY CONTROLS — ALL PASS

```
IMAGE: dumps/merged14.dump.exe   ImageBase 0x7ff608f40000  FLAT=True  sections=10
[CTRL DARK] 0x5A6AC40 ULokiRespawnComponent::Respawn   page_nonzero=0/4096   PASS
[CTRL FOLD] 0x0f7ec20 exp=c20000    got=c20000    PASS
[CTRL FOLD] 0x0f7eb50 exp=33c0c3    got=33c0c3    PASS
[CTRL FOLD] 0x0f7eb60 exp=32c0c3    got=32c0c3    PASS
[CTRL FOLD] 0x0b9e1f0 exp=b001c3    got=b001c3    PASS
[CTRL FOLD] 0x0fc6cf0 exp=0f57c0c3  got=0f57c0c3  PASS
[CTRL LIT ] 0x55ac9f0 ULokiCMC +0xC00 GAS slot        page_nonzero=3729/4096 PASS
[CTRL LIT ] 0x55b89f0 ULokiCMC::PhysFalling           page_nonzero=3578/4096 PASS
[CTRL LIT ] 0x35ec850 engine PhysFalling              page_nonzero=3610/4096 PASS
[CTRL LIT ] 0x3bbd9f0 APawn::SetPlayerState           page_nonzero=3721/4096 PASS
```

**Second, unplanned instrument control (vtable read).** Reading `ULokiCMC` vtable `.rdata 0x088F8570`
(ABSOLUTE VAs, `- ImageBase` applied) reproduced **7 of 7** recorded displacements exactly:
`0x4C0 -> 0x055AB8C0` GetGravityZ · `0x660 -> 0x035DB6F0` ComputeAnalogInputModifier ·
`0x7A0 -> 0x055B6AD0` NewFallVelocity · `0x7B0 -> 0x035D5D20` CalcVelocity (not Loki-overridden) ·
`0x830 -> 0x055B89F0` PhysFalling · `0xA50 -> 0x0530ABF0` (the +0x16C8 clear) ·
`0x720 -> 0x055C2430` StartNewPhysics. That 7/7 is what licenses the two vtable-slot
**corrections** in §4.

---

# HALF A — HOW ARM G WORKS TODAY

Source: `tools/sigbypass-mod/tutorial_launch.cpp:15309-15375` (`BsPsGasAttrs`), gated by
`KBSPSARMS` bit 8 (`0x100`) at `:16171`. Provenance: `ds_hybrid.cpp:2370-2430`,
`docs/coverage-audit-s101.md:283` and `:630`.

## A.1 Which CDO's default subobjects are borrowed, and into which fields

Source object: **`Default__LokiPlayerState_HeroAffiliated`**, located by
`FindObjExact("Default__LokiPlayerState_HeroAffiliated")` (`:15319`). The arm **REFUSES** if it is
absent and explicitly **does not spawn one** — S80 live-proved that an instant client crash.

| # | read from the CDO (by name, `PropOffsetSuper(ClassOf(ha), ...)`) | written to the PAWN (by name, `PropOffsetSuper(ClassOf(pawn), ...)`) | recorded offsets |
|---|---|---|---|
| 0 | `AbilitySystemComponent` | `AbilitySystemComponentStorage` | CDO `+0x3E8` -> hero `+0xF00` |
| 1 | `AttributeSet`           | `AttributeSetStorage`           | CDO `+0x3F0` -> hero **`+0xF08`** |
| 2 | `AttributeSetHealth`     | `AttributeSetHealthStorage`     | CDO `+0x3F8` -> hero `+0xF10` |

⚠ The offsets in the right-hand column come from `ds_hybrid.cpp`'s comment block and CLAUDE.md.
**ARM G itself hardcodes none of them** — every one is resolved by name on the live class, and every
store is readback-verified (`:15343-15349`). The arm REFUSES outright if `src[1]` (the CDO's
`AttributeSet`) is NULL, because "AttributeSetStorage is the whole point of this arm" (`:15333`).

Target selection: `ctl = g_psLbCtl[1]` (the ARM D `ALokiBotController`), then
`pawn = *(uintptr_t*)(ctl + 0x3F8)` (`:15314`). Both are hard REFUSALs if unresolved.
=> **ARM G targets ONLY the bot, and only the ARM-D-produced Loki bot controller's pawn.**

## A.2 Which attributes are written, and where

`:15351-15370`. All six offsets resolved by name on `ClassOf(src[1])` — i.e. on the **CDO's
AttributeSet object's class** — and each write is readback-verified:

| attribute | value | written at |
|---|---|---|
| `MoveSpeed` | `KBSGASMOVESPEED` = **500.0f** | `AttrSet + off + 0x8` **and** `+ 0xC` |
| `MaxMoveSpeed` | 500.0f | same |
| `MaxAcceleration` | 50000.0f | same |
| `GroundFriction` | 8.0f | same |
| `BrakingDecelerationWalking` | 2048.0f | same |
| `Mass` | 100.0f | same |

`+0x8` = `FGameplayAttributeData::BaseValue`, `+0xC` = `CurrentValue`.
★ **[M] ONLY `+0xC` IS READ.** `FGameplayAttributeData::GetCurrentValue` is
**`0x01F62B10 = f30f10410c c3` = `movss xmm0,[rcx+0xC]; ret`** — two instructions, no branch.
ARM G writing both is harmless belt-and-braces; a successor writing only `+0x8` would silently
change nothing.

## A.3 WHY it is process-wide — name the object and its scope

The three **pointer** stores land on the pawn *instance* and are per-instance. The **process-wide
part is the twelve float writes**: they go into `src[1]`, which is
**`Default__LokiPlayerState_HeroAffiliated`'s `AttributeSet` DEFAULT SUBOBJECT** — a single, shared,
already-constructed `ULokiAttributeSet` living under the CDO. Scope, precisely:

1. Every actor whose `+0xF08` is aliased to that same subobject reads our numbers. (Today: only the
   pawns ARM G itself wires — so in-run the blast radius is small.)
2. **The real exposure is archetype inheritance:** a default subobject is the *archetype* for the
   corresponding subobject of any later-constructed `LokiPlayerState_HeroAffiliated`. Subobject
   construction copies from the archetype, so a legitimate carrier constructed after ARM G runs
   inherits 500/500/50000/8/2048/100.
   ⚠ This is **not** the `InitProperties` path the S137 rule refutes — see A.4.
3. Nothing is ever undone. The arm says so (`:15373`).

## A.4 Which side of the "a CDO poke does not propagate" line is ARM G on — and why it works

The S137 rule (`docs/s137-playerstate-and-lokibot-settled.md`): *a CDO poke reaches a new instance
ONLY IF THE CONSUMER READS THE CDO DIRECTLY; it does NOT propagate via `InitProperties` for a
native-owned property.*

**ARM G is on neither side of that line — it does not rely on propagation at all.** It is an
**aliasing** recipe: the arm writes the *instance's own* `+0xF08` field to point AT the CDO's
subobject, and the consumer then dereferences the instance field and lands on the object we edited.
No copy, no `InitProperties`, no archetype walk. That is exactly why it works where ARM A's
`bWantsPlayerState` CDO poke measurably did not.

And it is now confirmed from the consumer's own bytes: **`0x055AC9F0`'s first instruction is
`mov rbx, qword ptr [rcx + 0xf08]`** — a direct instance-field read (§B.1).

---

# HALF B — THE PER-INSTANCE DESIGN (scoped, NOT built)

## B.1 The finding that reshapes the design

★★★★★ **[M] THE MOVEMENT GAS GETTERS READ `hero+0xF08` DIRECTLY. THEY NEVER CONSULT THE ASC OR
`SpawnedAttributes`.**

```
0x0055AC9F0   (CHARACTER vtable disp 0xC00 -- see section 4)
  0055ac9fa  488b99080f0000   mov  rbx, qword ptr [rcx + 0xf08]   <== AttributeSetStorage
  0055aca04  4885db           test rbx, rbx
  0055aca07  0f8466010000     je   0x55acb73                      <== NULL -> bail (returns 0)
  0055aca0d  e8ce4e0000       call 0x55b18e0                      (test al,al; jne bail)  <-- UNREAD
  0055aca1a  3887590b0000     cmp  byte [rdi+0xb59], al           bCharacterMovementEnabled
  0055aca2b  488bcb           mov  rcx, rbx
  0055aca38  e8a39cf7ff       call 0x55266e0                      <== the base value
  0055aca3d  488b9ff0160000   mov  rbx, [rdi+0x16f0]              modifier TArray (stride 0x38)

0x005526_6E0  (base value)
  005526_6ee  4881c1f0000000   add  rcx, 0xf0
  005526_6f5  e816c4a3fc       call 0x1f62b10                     GetCurrentValue (+0xC)
  005526_6fa  488d8b00010000   lea  rcx, [rbx+0x100]
  005526_704  e807c4a3fc       call 0x1f62b10
  005526_709  f30f5dc6         minss xmm0, xmm6                   <== min(+0xF0, +0x100)
```

=> **the per-instance recipe does NOT need any ASC plumbing to be READ.** It needs
`hero+0xF08` to point at an object we own. That is one instance-field store.

## B.2 The ASC routes — graded

| route | RVA | grade | reflected? | notes |
|---|---|---|---|---|
| `UAbilitySystemComponent::InitStats` | **`0x04481AC0`** | **REAL** (page 3779/4096) | **YES** — reflected name is **`K2_InitStats`**, exec thunk **`0x04415DF0`** | textbook stock body: `TSubclassOf` check -> `GetOrCreateAttributeSubobject` -> `InitFromMetaDataTable` via `[vt+0x300]`. **Needs a `UDataTable` we do not have** — with `DataTable == NULL` it creates the set and writes no values. |
| `UAbilitySystemComponent::GetOrCreateAttributeSubobject` | **`0x0447D240`** | **REAL** (page 3844/4096) | **NO** (`strxref native` -> *no ASCII reflection name*) -> **raw direct call** | `void* __fastcall(ASC*, UClass** /*&TSubclassOf*/)`. Creates + registers. See B.3. |
| `UAbilitySystemComponent::GetAttributeSubobject` | **`0x044797F0`** | **REAL** (page 3864/4096) | **NO** -> raw direct call | `void* __fastcall(ASC*, UClass**)`. Linear scan of `SpawnedAttributes` with an `IsChildOf` test. Pure read — a free, zero-risk probe. |
| `AddSpawnedAttribute` | *no separate symbol* | — | NO | **INLINED** inside `0x0447D240` at `0x0447D401..0x0447D45D`. There is nothing to call. |
| `AddAttributeSetSubobject` / `AddSet<T>` / `GetAttributeSet` | — | — | NO | no reflection name; stock-UE templates/inlines. Not separately callable. |
| `UGameplayStatics::SpawnObject(ObjectClass, Outer)` | thunk resolved by name | REAL | **YES** | **already implemented and live-proven in this shim** (`tutorial_launch.cpp:5181-5206`, RM_CHEATMGR / S114). |
| `ULokiGameplayStatics::SpawnObjectFromClass(Outer, ObjectClass)` | reflected static | — | **YES** (`binds_members.csv`, `ULokiGameplayStatics` method 144) | alternative; **note the reversed argument order**. The shim resolves params by name, so this is safe either way. |

★ **[M] `SpawnedAttributes` IS at `ASC+0x168`**, `{Data +0x168, Num +0x170, Max +0x174}` —
**two disjoint functions agree**: `GetAttributeSubobject` reads `[rcx+0x168]` / `[rcx+0x170]`
(`0x0447980E`, `0x00447_9818`), and the inlined `AddSpawnedAttribute` writes through
`rdi = rbp+0x168` with `[rdi+8]`=Num, `[rdi+0xc]`=Max (`0x0447D401`, `0x0447D443`, `0x0447D446`).

★ It **is a reflected UPROPERTY** — the ANSI name `'SpawnedAttributes'` at `.rdata 0x0839BE48`
carries **2 `.rdata` data pointers** (`0x0839A990`, `0x0839A9D0`) = UHT `FPropertyParams` records,
with **0 code refs** (correct: UHT names are referenced by data, not by `lea`).
=> resolvable **by name** on the live ASC class; `0x168` is a cross-check, not a hardcode.

★ **The growth call is the one this project already flies:** `0x0447D451 call 0xF988D0` — the same
`ResizeGrow` the S132 dismount used. And `0x0447D45D or byte [rbp+0xE4],2` is the replication-dirty
mark.

## B.3 `GetOrCreateAttributeSubobject` — full semantics, and its ONE precondition

```
0447d260  4c8bb9b8000000   mov r15, [rcx+0xb8]      <== the component's OWNER ACTOR
0447d270  4d85ff           test r15,r15
0447d273  0f842e020000     je 0x447d4a7             <== NULL owner -> return nullptr, no side effect
0447d281  488b1a           mov rbx,[rdx]            <== the UClass out of the TSubclassOf
0447d287  0f8415020000     je 0x447d4a2             <== NULL class -> return nullptr
0447d28d  e8bee2faff       call 0x442b550           <== UAttributeSet::StaticClass()  (named, B.4)
   ... StructBaseChain IsChildOf test (rdi=[cls+0x40], r14=cls+0x38, cmp [child+0x38 + rdi*8], r14)
0447d318  e8d3c4ffff       call 0x44797f0           <== GetAttributeSubobject(Class): already have one?
0447d320  0f8541010000     jne 0x447d467            <== yes -> return it
0447d3b1  4c897c2438       mov [rsp+0x38], r15      <== FStaticConstructObjectParameters.Outer = owner
0447d3c1  48895c2440       mov [rsp+0x40], rbx      <== .Class = AttributeClass
0447d3d5  e8b66aeffc       call 0x1373e90           <== StaticConstructObject_Internal
0447d401..0447d45D                                   <== AddSpawnedAttribute (inlined, AddUnique)
0447d464  488bc3           mov rax, rbx             <== return the new set
```

⚠ **[M] The only precondition is `ASC + 0xB8 != NULL`.** `+0xB8` is the offset S132 independently
measured as **`UActorComponent`'s owner** (`[comp+0xB8] = BP_DropPod_Tutorial_C`), so this is
"the ASC must be a component with an owning actor". **A NULL there returns nullptr with no side
effect and no log line** — a silent null that would read exactly like a broken call.
⚠ Grade: the *offset and the bail* are [M]; the *name* `GetOwnerActor` vs `GetOwner` is
**[I, strong]** (structural match to stock UE plus the S132 `+0xB8` measurement).

⚠⚠ **THIS IS WHY R1 IS THE FALLBACK, NOT THE LEAD.** The only ASC ARM G has in hand is the CDO's
default subobject. Its `+0xB8` is unread and is plausibly NULL or the CDO carrier. The bot's own
`+0xF00` is measured NULL (no ASC at all); the player's is `KWIREGAS`'s shim-built carrier ASC.
**Read `ASC+0xB8` live before ever calling `0x447D240`.**

## B.4 `ULokiAttributeSet`'s UClass — three routes, all [M]

Named **from their own bytes** (rip-relative LEAs inside each lazy `GetPrivateStaticClass`):

| getter RVA | LEA'd name | LEA'd package | cached UClass* slot (from the getter's own `mov rax,[rip+..]`) |
|---|---|---|---|
| **`0x0052AC650`** | `U'LokiAttributeSet'` | `U'/Script/Loki'` | **`.data 0x0A018FB8`** |
| **`0x0052B8200`** | `U'LokiAttributeSetHealth'` | `U'/Script/Loki'` | **`.data 0x0A019BA0`** |
| **`0x00442B550`** | `U'AttributeSet'` | `U'/Script/GameplayAbilities'` | **`.data 0x09FEBE60`** |

★ The UHT prefix-strip trap is visible in the pointer arithmetic itself: the wide string at
`0x08890598` is `ULokiAttributeSet` and the LEA targets `0x0889059A` — it *skips the `U`*.
⚠ **Do NOT read the VALUES at those `.data` slots out of `merged14`** (spliced `.data` in a merged
image — CLAUDE.md's standing rule). The *addresses* are safe; they came from `.text`.

**Recommended class source (zero new primitives): `ClassOf(src[1])` — the class of the CDO's
own `AttributeSet` subobject, which ARM G already holds.** That is by construction the exact class
the game uses, needs no name lookup and no `.data` read. Cross-checks available:
`FindClassExact("LokiAttributeSet")` (the shim already has `FindClassExact`, `:16267`) and the live
value at `.data 0x0A018FB8`.

## B.5 `NewObject` vs `SpawnObject` — viability

Viable. The project's own rule stands and applies here: prefer **`UGameplayStatics::SpawnObject`**,
because shipping has `DO_CHECK == 0`, so `NewObject`'s `ClassWithin` assert is compiled out and a
wrong Outer would be **silent**; `SpawnObject`'s *runtime* Within test is the only one that survives
shipping. The shim already implements exactly that call (`tutorial_launch.cpp:5181-5206`), resolves
its params by name, and it is live-proven (S114 Route B).

⛔ **The S80 crash precedent does NOT transfer.** S80 crashed spawning
`ALokiPlayerState_HeroAffiliated` — an **ACTOR**, whose ASC/attribute construction derefs
server-side context. A `ULokiAttributeSet` is a plain `UObject`: no actor, no components, no
`BeginPlay`, no server context. **And the game itself constructs one at `0x0447D3D5` with an actor
as Outer.** Do not let ARM G's (correct) refusal-to-spawn comment be read as forbidding this.

★ **GC is handled without `AddToRoot`.** Whichever route creates it, the object ends up referenced
by a **real reflected `UPROPERTY`** — `SpawnedAttributes` (`ASC+0x168`) on route R1, and/or
`AttributeSetStorage` (`hero+0xF08`) on route R2 — so the GC traversal reaches it. That is the
`KANIMREF` / S123 mechanism (*be reachable by a real UPROPERTY*), not the refuted flag poke.

## B.6 THE RECIPE (design only — NOT BUILT, NOT FLOWN)

**R2 — RECOMMENDED. No ASC, no CDO write, no new native call.**

1. `cls = ClassOf(src[1])` — the class of the CDO's `AttributeSet` subobject (ARM G already reads
   `src[1]`; no new resolution). REFUSE if NULL.
2. `set = UGameplayStatics::SpawnObject(ObjectClass = cls, Outer = pawn)` via the existing
   `g_chmSo*` primitive. REFUSE on fault or NULL (S114 already prints the `LogScript` hint).
3. Store `pawn + off("AttributeSetStorage") = set` — **one aligned instance-field store**,
   readback-verified. Save the previous value (measured NULL on the bot) for restore.
4. Write the SAME six attributes into `set` (offsets by name on `cls`), `+0x8` and `+0xC`.
5. Optionally repeat 1-4 with `ClassOf(src[2])` into `AttributeSetHealthStorage` (`+0xF10`).
6. `+0xF00` (`AbilitySystemComponentStorage`): leave ARM G's borrow, or leave NULL. **The movement
   getters never read it** (B.1), so it is not required for this experiment.

**R1 — the game's own route, as a fallback / corroboration.** Raw direct call
`0x0447D240(ASC, &cls)`. Preconditions to read live and REFUSE on: `ASC != NULL`,
`*(void**)(ASC+0xB8) != NULL`. Free receipt: `*(int32*)(ASC+0x170)` (`SpawnedAttributes.Num`)
must go **+1**, and `0x044797F0(ASC,&cls)` must then return the same pointer.
⚠ NOT call-only: it constructs an object and writes `ASC+0x168/0x170/0x174` and `ASC+0xE4`.

### Risk class, side by side

| | ARM G (today) | R2 (per-instance) |
|---|---|---|
| module-image (`.text`) writes | none | none |
| PI hook | none | none |
| object construction | none | **1 plain `UObject`** (no actor) |
| instance pointer stores | 3 (on the pawn) | 1-2 (on the pawn) |
| **writes to a shared/CDO object** | **12 floats into a CDO DEFAULT SUBOBJECT — process-wide, permanent, archetype-inherited** | **0** |
| reversible | **no** (nothing is undone) | **yes** — restore `+0xF08` to its saved value; the created object then becomes garbage |
| GC | n/a (borrowed object already rooted) | reachable via the `AttributeSetStorage` UPROPERTY |

### Readback that proves it

* `pawn+0xF08` reads back the pointer `SpawnObject` returned (and it is **not** `src[1]`, i.e. not
  the CDO subobject — a two-sided control that ARM G cannot offer).
* Each of the six attributes reads back at `set + off + 0xC`.
* **Live behavioural readbacks** (C.2): `AnalogInputModifier` non-zero, `Acceleration` non-zero.
* **Two-sided specificity control, free:** leave `+0xF10` / the other pawn untreated.

---

# SECTION 4 — TWO CORRECTIONS TO `CLAUDE.md`, BOTH [M], BOTH IN-LANE

## 4.1 `GetMaxSpeed` and `GetMaxAcceleration` are **NOT** the same function

CLAUDE.md (S140 T2 / S141 blocks) states: *"`GetMaxAcceleration` (disp `0x7D0`) and `GetMaxSpeed`
(disp `0x4C8`) are **both GAS-backed through the SAME `+0xC00` slot** (`0x055AC9F0`)"*.

**[M] REFUTED as stated**, from the `ULokiCMC` vtable (7/7 recorded slots reproduced in the same read
— see section 0):

```
ULokiCMC vtable .rdata 0x088F8570 + 0x4C8 -> RVA 0x0055ACB90   GetMaxSpeed
ULokiCMC vtable .rdata 0x088F8570 + 0x7D0 -> RVA 0x0055AC910   GetMaxAcceleration
```

They are **two distinct functions**. `0x055AC9F0` is a **helper on the CHARACTER's vtable at
disp `0xC00`**, which both of them *call* — and it takes **no selector argument** and hardcodes
`+0xF0` / `+0x100`, so it cannot by itself produce two different numbers. CLAUDE.md's own open
disjunction — *"either (a) another `Velocity`-zeroing site exists, or (b) the two getters pass
DIFFERENT attribute selectors"* — resolves to **(b)**, and more strongly than (b) was framed.

⚠ SCOPE: what I refute is specifically *"both go through one shared slot function `0x055AC9F0`"*.
I did not independently re-derive the CHARACTER vtable's `+0xC00` entry; that `0x055AC9F0` sits at
character disp `0xC00` is [M] from the two `call qword [rax+0xc00]` sites inside `0x0055AC910` /
the tail-`jmp` inside `0x0055ACB90`, plus `0x055AC9F0`'s own `[rcx+0xF08]` read matching a character.

## 4.2 The measured `50000` did **NOT** come from the `MaxAcceleration` attribute ARM G wrote

`ULokiCMC::GetMaxAcceleration` `0x0055AC910`, transcribed:

```
0055ac91a  0fb68131020000  movzx eax, byte [rcx+0x231]      ; MovementMode
0055ac924  3c01            cmp al, 1                        ; MOVE_Walking?
0055ac926  7552            jne 0x55ac97a
   -- WALKING ARM --
0055ac928  488b99b8000000  mov rbx,[rcx+0xb8]               ; CharacterOwner ; NULL -> 0x55ac9bc
0055ac93b  e800c3f4ff      call 0x54f8c40                   ; IsA ; false -> 0x55ac9bc
0055ac94a  ff90000c0000    call qword [rax+0xc00]           ; = 0x055AC9F0  (speed, from +0xF08)
0055ac953  0f2ec1          ucomiss xmm0, xmm1(=0)
0055ac956  7456            je  0x55ac9ae                    ; ZERO -> return 0.0f
0055ac958  488b8b080f0000  mov rcx,[rbx+0xf08]              ; AttributeSetStorage ; NULL -> 0x55ac9bc
0055ac964  4881c120010000  add rcx, 0x120                   ; <== the MaxAcceleration ATTRIBUTE
0055ac975  e996619bfc      jmp 0x1f62b10                    ; GetCurrentValue(+0xC)
   -- NON-WALKING ARM --
0055ac97a  3c03            cmp al, 3                        ; MOVE_Falling
0055ac97e  3c06            cmp al, 6                        ; MOVE_Dashing (this build)
0055ac980  753a            jne 0x55ac9bc                    ; any other mode -> Super
0055ac9a0  ff90000c0000    call qword [rax+0xc00]           ; same speed helper
0055ac9a9  0f2ec1          ucomiss xmm0, 0
0055ac9ac  750e            jne 0x55ac9bc                    ; NON-ZERO -> Super
0055ac9ae  0f57c0          xorps xmm0,xmm0                  ; ZERO      -> return 0.0f
0055ac9bc  ...             jmp 0x35e3ad0                    ; engine Super::GetMaxAcceleration
```

★★★★★ **[M] THIS RETRODICTS S139 FLIGHTS 3 AND 4 EXACTLY — and revises the mechanism:**

* **Flight 3, untreated, `MOVE_Falling`:** `+0xF08` NULL => `0x055AC9F0` bails on its first
  instruction and returns 0 => `ucomiss ... je 0x55ac9ae` => **`return 0.0f`** =>
  `Acceleration = input x 0` = the measured **signed zero**. CONFIRMED.
* **Flight 4, treated, still `MOVE_Falling`:** `+0xF08` non-NULL => the helper returns
  `min(MoveSpeed, MaxMoveSpeed) = 500 != 0` => `jne 0x55ac9bc` => **engine
  `Super::GetMaxAcceleration()` = the CMC's own `MaxAcceleration` UPROPERTY = 50000.** CONFIRMED.

=> **On the `MOVE_Falling` arm the `MaxAcceleration` attribute at `AttrSet+0x120` is NEVER READ.**
The GAS set acted as a **GATE** ("speed is non-zero => don't return 0"), not as the source of the
number. CLAUDE.md's *"the getter returning exactly the `MaxAcceleration` we supplied"* is wrong for
that arm.

⚠⚠ **AND THE TWO HYPOTHESES ARE NUMERICALLY INDISTINGUISHABLE IN THE EXISTING RECORD** — because
CLAUDE.md's own S139 flight-1 structural table records the CMC's `MaxAcceleration` as **50000 on
both pawns, untreated**, and ARM G writes **50000** into the attribute. Same number, two sources.
★ **FREE DISCRIMINATOR, one constant:** build with `MaxAcceleration = 37000.0f` in ARM G's block.
Falling => still 50000 (Super). Walking => 37000. That also becomes a *live MovementMode readout*.
⚠ Grade: that flight 4 was on the Falling arm is **[I, strong]** (S139 flight 1 and S140 T2 flight 3
both measured `MovementMode 3` in this regime), not [M] — nobody logged the mode in flight 4 itself.
⚠ Grade: *"engine `Super::GetMaxAcceleration` `0x035E3AD0` returns the CMC's own `MaxAcceleration`
UPROPERTY"* is **[I, strong]** — stock UE plus the measured 50000 — **not [M]**; I did not
disassemble `0x035E3AD0`. One read settles it.

★ **And `GetMaxSpeed` `0x0055ACB90` corroborates the S141 `CalcVelocity`-clamp correction FROM THE
BYTES:**

```
0055acb96  80b93102000007  cmp byte [rcx+0x231], 7      ; MOVE_Custom (this build)
0055acba2  80b93202000001  cmp byte [rcx+0x232], 1      ; CustomMovementMode == 1
0055acbab  f30f100565ab2102 movss xmm0, [rip+...]       ;   -> a .rdata constant (fast path)
0055acbbe  488bb9b8000000  mov rdi,[rcx+0xb8]           ; CharacterOwner ; NULL -> 0x55acbed
0055acbcd  e86ec0f4ff      call 0x54f8c40               ; IsA ; false -> 0x55acbed
0055acbe6  48ffa0000c0000  jmp qword [rax+0xc00]        ; <== TAIL-JMP: returns min(+0xF0,+0x100)
0055acbfa  e9217003fe      jmp 0x35e3c20                ; else engine Super::GetMaxSpeed
```

On a **treated** pawn that is **500** — numerically equal to the 500.0 uu/s cap S140 T2 flight 3
measured. On an **UNTREATED** pawn (`+0xF08` NULL) it returns **0**.
=> the verifier argument that was used to "refute" the clamp (*`GetMaxSpeed` shares the `+0xC00`
slot with `GetMaxAcceleration`, which measured 50000, so `GetMaxSpeed != 0`*) fails at the root
twice: **different vtable slots**, and **the 50000 never came through `+0xC00` at all**.
That is an independent, byte-level confirmation of CLAUDE.md's own S141 [S]->[M] correction.

---

# HALF C — PREP FOR THE LIVE FLIGHT (T3-C)

## C.1 The minimal edit to point ARM G at the PLAYER

**Current target selection** — `tutorial_launch.cpp:15312-15315`:

```c
    uintptr_t ctl=g_psLbCtl[1];
    if(!LooksLikePtr(ctl)){
        Marker("[GASX] ARM G REFUSED: ARM D produced no LokiBotController. STAGING statement, not a result.\r\n"); return; }
    uintptr_t pawn=SafeReadable((void*)(ctl+0x3F8),8)?*(uintptr_t*)(ctl+0x3F8):0;
    if(!LooksLikePtr(pawn)){ Marker("[GASX] ARM G REFUSED: the controller possesses no pawn.\r\n"); return; }
```

**The player hero is already in a global and is already populated when ARM G runs.** `g_bsPlayerHero`
is set in `BsResolve` GUARD 5 (`:16278`) and in `BsResolveAI` (`:14496`) — `BsResolve` under
`#if KBSAI` is `{ BsResolveAI(hero); return; }`, so exactly one of the two always runs — and
`BsResolve(hero)` is called at `:16348`, **before** `BsPsExperiment()` at `:16398`.
ARM H already relies on exactly this (`:15878  g_shPlrPawn=g_bsPlayerHero`) and it worked in
S140 T2. **No new resolution code is needed.**

**Minimal edit — parameterise the body, add one knob:**

```c
#ifndef KBSGASTARGET
#define KBSGASTARGET 1        // bit0 = BOT (today's behaviour)   bit1 = PLAYER
#endif
static void BsPsGasAttrsOn(uintptr_t pawn, const char* who);   // = today's body from :15317 down,
                                                               //   with `pawn` a parameter
static void BsPsGasAttrs(){
#if (KBSGASTARGET & 1)
    {   uintptr_t ctl=g_psLbCtl[1];
        if(!LooksLikePtr(ctl)) Marker("[GASX] BOT arm REFUSED: ARM D produced no LokiBotController.\r\n");
        else { uintptr_t p=SafeReadable((void*)(ctl+0x3F8),8)?*(uintptr_t*)(ctl+0x3F8):0;
               if(LooksLikePtr(p)) BsPsGasAttrsOn(p,"BOT");
               else Marker("[GASX] BOT arm REFUSED: the controller possesses no pawn.\r\n"); } }
#endif
#if (KBSGASTARGET & 2)
    if(LooksLikePtr(g_bsPlayerHero)) BsPsGasAttrsOn(g_bsPlayerHero,"PLAYER");
    else Marker("[GASX] PLAYER arm REFUSED: the A0 world scan latched no player hero.\r\n");
#endif
}
```

Everything inside `BsPsGasAttrsOn` is unchanged (it already resolves every offset by name on
`ClassOf(pawn)`, so it is class-agnostic and works on `BP_HERO_Ronin_C` as-is).
★ `KBSGASTARGET=1` must reproduce today's behaviour; a `KBSGASTARGET=1` build is the
**regression gate** for the edit.

⚠⚠ **NOTE THE DELIBERATE ABSENCE OF `#else` SKIP MESSAGES.** CLAUDE.md's own S140 lesson:
an `#else` "ARM H skipped" marker line moved `gasattr 2fcc2536e21f18e3 -> 6d81e34e675f97f1`
while leaving the `.text` SIZE at 137,728 bytes. **A skip message compiled into the CONTROL builds
is not free.** Using `#if`/`#endif` with no `#else` is what keeps the `KBSGASTARGET=1` regression
gate byte-identical to `gasattr`. If you add the skip lines anyway, **re-record the digest and say
so** — do not quote the old one.

**Build line** (add to `build.ps1` beside `sentinel-big`, `:656`):

```
'gasattr-player-kick' = @('-DKRUNMODE=RM_BOTSPAWN','-DKFSNAME=\"\"','-DKFRAMEINIT=1','-DKFAULTINFO=1',
                          '-DKOUTPARMRET=1','-DKBSAI=1','-DKBSPS=1',
                          '-DKBSPSARMS=0xBA0',          # D + F + G + H + J  == sentinel-big
                          '-DKBSGASTARGET=3',           # treat BOTH pawns
                          '-DKSHSENTX=600.0','-DKSHPLRY=600.0')
```

`0xBA0` = bit5 ARM D (the Loki bot controller) + bit7 ARM F (open the `bCharacterControllable`
gate) + bit8 ARM G + bit9 ARM H (poison/sentinel + the worker-thread sampler) + bit11 ARM J (the
player's `(0, 600, 0)` kick). **ARM J is the kick, and it already exists** (`:15921-15933`) — the
only new thing is `KBSGASTARGET`.

⚠ Note what this costs: with `KBSGASTARGET=3` the **player is no longer the untreated specificity
control** for ARM G. That is the deliberate point of T3-C (it converts S140 T2's pre-registered
outcome **E** — *the two arms disagree* — into a two-treated-arms test), but say so explicitly in
the pre-registration, and keep `+0xF10` / a third object as the surviving control.

## C.2 What readback confirms the treatment landed **on the PLAYER**

In-arm, from ARM G's own prints, tagged `PLAYER`:

1. `dst AttributeSetStorage @0xF08  0 -> <ptr>  OK` — was NULL, now the borrowed set. **[M] this is
   the exact field `0x055AC9F0` reads on its first instruction**, so it is the causally right one.
2. `storages written 3/3, attributes written 6/6` — anything less prints the `INCOMPLETE ...
   UNINTERPRETABLE` banner, and it means it.

Live/behavioural, from `tools/re/cmc_earlyout_readout.py` (read-only RPM, run **after**):

3. **`AnalogInputModifier` 0 -> non-zero** on the player. Per CLAUDE.md's S141 correction this is the
   discriminator for the `CalcVelocity` `MaxInputSpeed` clamp: untreated player = 0 => clamp fires;
   treated => `MaxInputSpeed = GetMaxSpeed() x AnalogInputModifier` => 500 => clamp must not fire.
   (`GetMaxSpeed() = 500` on a treated pawn is now [M] from the bytes — section 4.2.)
4. **`Acceleration` (CMC+0x328) non-zero on the player.** Untreated it was non-zero in **0 of 20**
   samples (S139 flight 4's specificity control) — so any non-zero is a real move.
5. ★ **New, and now predicted:** the by-name offsets ARM G resolves should be
   **`MoveSpeed = 0xF0`, `MaxMoveSpeed = 0x100`, `MaxAcceleration = 0x120`** on the attribute set's
   class. Those three are **[M]** from `0x005526_6EE` / `0x0055266FA` and `0x0055AC964`. ARM G already
   prints `attr <name> @+0x<off>`. **Pre-register it: if `MoveSpeed` does not print `@+0xF0`, the
   attribute-set class is not the one the getters read and the run is VOID.** That is a free,
   two-sided identity control the arm has never had.

## C.3 THE PLAYER IS A CONTAMINATED CONTROL WHENEVER `play` IS INJECTED — CONFIRMED FROM SOURCE

**[M] Two sites, quoted verbatim:**

`tutorial_launch.cpp:3046-3047` (`DoPuppet`, runs on **every** game-thread hit under `RM_PLAY`):

```c
    V[0]=vx; V[1]=vy;   // keep V[2] (Z) so gravity + jump still work
    if(SafeReadable((void*)(g_wmCMC+0x328),24)){ double* A=(double*)(g_wmCMC+0x328); A[0]=vx*4.0; A[1]=vy*4.0; A[2]=0.0; }   // Acceleration -> facing/anim
```

(`V = (double*)(g_wmCMC+0xE8)`, `:3036`. With no key held and the window focused, `vx=vy=0` — so it
**writes zeros** to `Velocity.XY` and `Acceleration` every hit. And `:3038` writes
`V[0]=0.0; V[1]=0.0;` outright whenever the game window is not foreground.)

`tutorial_launch.cpp:12598-12599` (the self-driven auto-walk window):

```c
            V[0]=__builtin_cos(yaw)*kPupSpeed; V[1]=__builtin_sin(yaw)*kPupSpeed;   // "W" in the camera's frame
            if(SafeReadable((void*)(g_wmCMC+0x328),24)){ double* A=(double*)(g_wmCMC+0x328); A[0]=V[0]*4.0; A[1]=V[1]*4.0; A[2]=0.0; }
```

=> **`RM_PLAY` writes both `CMC+0xE8` (Velocity) and `CMC+0x328` (Acceleration) directly on the
player, every game-thread hit.** So on any sitting where `play` is resident, the player's
`Acceleration` and `Velocity` are **[M] uninterpretable** as evidence about GAS, and readbacks 3-5
above must be taken from the **structural** fields plus `AnalogInputModifier` — which `play` does
**not** write (`AnalogInputModifier` appears nowhere in `tutorial_launch.cpp`).

★ **The T3-C flight uses `RM_BOTSPAWN`, not `RM_PLAY`, so this does not bite — provided `play` is
NOT injected into that client.** Say so in the pre-registration and do not stage `play`.

## C.4 ONE INJECTION — what must be in the single arm

FK-32 kills the client on ~the **4th** manual-map at **~320-350 s** (the `0xDEAD` series is
7/6/4/4/4 injections at 1144/334/350/318 s; 4 is the modal count), and staging spends three
(`gft` -> `fo` -> `sp`). => **the lead gets essentially ONE injection.** Therefore ALL of the
following must be in that single DLL, in this order:

1. **ARM D** (`0x20`) — build the `ALokiBotController` (poke `Default__Pawn+0x3D0`, spawn, restore).
   ARM G's bot half depends on it and it must A-B-A as before.
2. **ARM F** (`0x80`) — open `bCharacterControllable` so the AI wander driver actually steers.
3. **ARM G** (`0x100`) with `KBSGASTARGET=3` — treat the **bot AND the player**, printing each
   pawn's storages, the six attribute offsets (**check `MoveSpeed @+0xF0`, C.2.5**) and readbacks,
   with a per-pawn REFUSAL rather than a silent skip.
4. **ARM H** (`0x200`) — poison `+0x16B0` on **both** components with **different** poisons (the
   two-sided addressing control that could have failed and didn't), and latch `RootComponent`
   start locations for the distance readout.
5. **ARM J** (`0x800`) — the kick: bot `Velocity = (KSHSENTX, 0, 0)`, player `Velocity =
   (0, KSHPLRY, 0)` — **different axes**, so cross-contamination is visible.
   ★ Keep both at **600.0**: S140 T2 flight 3 measured that 600 escapes the `PhysFalling` `SizeSq2D`
   gate (`3.6e8 x`) and `2^-10` does not. A smaller, "more inert" sentinel is zeroed *harder*.
6. **The sampler on the WORKER thread, after `FsDisarm()`** — `ShSampleLoop` already does this.
   ⚠⚠ **[M] `BsLadderStep` runs ON THE GAME THREAD inside `OnPI`, so any `Sleep()` in the arm stops
   the frames the test needs.** Do not move the sampling into the arm.
7. **A pre-registered disjunction, written before the flight**, over the 2x2 of
   {bot moves / doesn't} x {player moves / doesn't}. S140 T2's outcome **E** (arms disagree) is now
   *expected to disappear* — that is the whole hypothesis, so write down what each cell means first.
8. **Regression gates recomputed and quoted** with the RAW recipe
   (`tools/sigbypass-mod/text_digest.py`): `botai 5e47c13cf7f0a158`, `gasattr 2fcc2536e21f18e3`,
   `gasattr-ctrl 4465ebc4d7168c03`, plus a `KBSGASTARGET=1` build that must reproduce `gasattr`
   exactly — and **verify the new arm is not byte-identical to `sentinel-big 52fceb9be6de532f`**
   (an A/B against a copy of itself has burned a live run in this project).
   ⚠ Do **not** use `driverecompute a2a952babfed256b` as a gate — CLAUDE.md records it as invalid
   (it and `gasattr-ctrl` are given the SAME `-DKBSPSARMS=0xA0`).
9. **Capture as you go.** Both S140 T2 clients died of FK-32 and lost nothing because every result
   was captured as produced.

⚠ **What is NOT in this arm, deliberately:** the per-instance recipe of B.6. It is scoped, not
built, and mixing an untested construction into the one available injection would confound the
player-kick result. **Fly T3-C with ARM G as-is; build R2 afterwards as the shipping-safety
replacement**, whose whole value is removing a permanent CDO mutation, not changing the physics.

---

# SECTION 5 — NOT ESTABLISHED

| open item | the exact read that settles it |
|---|---|
| `ASC+0xB8`'s reflected NAME (`OwnerActor` vs `UActorComponent::OwnerPrivate`) | walk the live `UAbilitySystemComponent` UClass property list for a UObject property at `0xB8`; or `PropOffsetSuper(ClassOf(asc),"OwnerActor")` on a live ASC |
| whether the CDO's `AbilitySystemComponent` subobject has a non-NULL `+0xB8` | one read-only RPM read of `*(void**)(src[0]+0xB8)` — **gates route R1 entirely** |
| whether `MoveSpeed/MaxMoveSpeed/MaxAcceleration` really sit at `+0xF0/+0x100/+0x120` on `ULokiAttributeSet` | ARM G already prints `attr <name> @+0x<off>` — compare to the prediction in C.2.5 |
| what `0x0055B18E0` (the second guard in `0x055AC9F0`, `test al,al; jne bail`) tests | ~20 instructions; disassemble it. **It can veto the whole GAS path and is currently unread** |
| what engine `Super::GetMaxAcceleration` `0x035E3AD0` reads | one disassembly; expected to be the CMC's own `MaxAcceleration` UPROPERTY — that is the **assumed** source of the 50000 in 4.2 and it is **[I, strong], not [M]** |
| whether S139 flight 4's pawn was in `MOVE_Falling` at the moment `Acceleration` was sampled | log `MovementMode` beside `Acceleration` in T3-C; or fly the `MaxAcceleration = 37000` discriminator |
| whether route R2's `SpawnObject` passes `UAttributeSet`'s `ClassWithin` with a pawn Outer | the call itself — S114's primitive already prints the `LogScript` refusal on failure |
| whether anything ELSE reads `hero+0xF00` and would be confused by a `+0xF08` set absent from that ASC's `SpawnedAttributes` | census `[reg+0xf00]` reads in `.text`; not attempted this lane |
| the `.rdata` constant `GetMaxSpeed` returns on its `MOVE_Custom(7) + CustomMode 1` fast path | read the 4 bytes at `0x0055ACBAB`'s rip target |

# SECTION 6 — INSTRUMENT NOTES / FLOORS

* Every enumeration here is over a **~55.5%-decrypted `.text`** and is a **FLOOR**, never a count.
  The specific negatives that carry that caveat: *"`AddSpawnedAttribute` / `GetOrCreateAttributeSubobject`
  / `GetAttributeSubobject` / `GetAttributeSet` have no reflection name"* — that one is safe, because
  reflection names live in `.rdata` (99.64% readable) and `strxref native` searches `.rdata`, not `.text`.
* `binds_members.csv` is the **Angelscript** binding table. Absence from it is suggestive, not proof
  of non-reflection. Every "reflected: NO" above is backed by `strxref native` (`.rdata`), not by it.
* `strxref.py` `DEFAULT_DUMP` **is** `merged14` in this tree (`strxref.py:91`) — verified before use,
  because CLAUDE.md records a recurring stale-default defect on exactly this line.
* All `.data` slot ADDRESSES in B.4 were derived from `.text` instructions. **Their VALUES must not
  be read out of a merged image** (spliced `.data`).
* capstone `regs_access` mis-reports `movups` stores as reads (S140T2-h). This lane classified nothing
  from `regs_access`; every write cited was read off the mnemonic and a memory destination operand in
  the printed disassembly.
* The `0x442b550` / `[cls+0x38]` / `[cls+0x40]` block that appears three times in this lane's listings
  is **UE's `FStructBaseChain` `IsChildOfUsingStructArray`** (the `TSubclassOf` conversion check),
  not an unidentified guard. It passes for any real `UAttributeSet` subclass.
