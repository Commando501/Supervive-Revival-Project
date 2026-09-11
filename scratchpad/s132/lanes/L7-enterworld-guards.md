# LANE 7 — `ULokiRideableComponent::AuthPlayerEnterWorld` prologue guards, transcribed

**Method:** offline only. `dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA),
`tools/strxref/index/pdata_union.csv`, `tools/asdump/out/binds_members.csv`, capstone for every
exhaustive pass. **Zero launches, zero injections, zero `.text` writes.** Every address recomputed by
machine (`python -c`), never by hand.

---

## 0. Headline verdict (leads with grades)

1. **[M] The identity is confirmed from the `.data` record table, not assumed.**
   `.data 0x9C1E570 = {name→"AuthPlayerEnterWorld", exec thunk 0x54561D0, impl 0x55CCE70}`.
   Positive control in the same table two records later:
   `0x9C1E5B8 = {"AuthPlayerEnterWorldAttachedToRidable", 0x5456380, 0x55CD510}` — matches the
   handoff's recorded thunk/impl for the wall exactly.

2. **[M] Blocker (a) is CONFIRMED byte-for-byte.** The `PlayersInside` membership requirement is real
   and is *two* guards, not one (empty-array test, then a linear scan), and **both bails are SILENT** —
   the *first `call` instruction anywhere in the function is at `0x55CCF1A`*, strictly after every
   bail, so no log line is even possible on a bail path.

3. **[M] Blocker (b) is CONFIRMED and the "two? three?" question is settled: THREE `call 0xF7EB50`,
   at `0x55CCF22`, `0x55CD405`, `0x55CD4C7`.** Exactly **one** (`0x55CCF22`) is the round-game-mode
   getter, and it is **not gated** — the next instruction is `lea rcx,[r12+0x470]`, with no
   `test`/`jcc` on `rax`. **The other two are the payload**: called with `rcx` = that same
   (always-null) round game mode, `rdx` = PlayerState, `r8` = `&FTransform`.

4. **★★★★★ [M] VERDICT: FORECLOSED, and the foreclosing instructions are `0x55CD405` and
   `0x55CD4C7`.** `AuthPlayerEnterWorld` performs **zero writes to any actor or component transform**.
   Its two terminal actions are direct calls to the stripped fold `0xF7EB50` (`33 c0 c3`). Satisfying
   the `PlayersInside` guard with a poke would move execution past the guards and change nothing about
   where the hero is. It is **not** an alternative route to dismount/repositioning.

5. **★★ [M] It is viable-with-a-poke only as an INSTRUMENT** — past the guards the function runs to
   completion, fires the reflected `MulticastOnPlayerEnteredWorld` (REAL, impl `0x54537C0`), and on
   the `bRepositionPlayer=1` path runs a 32-iteration navmesh + trace terrain search whose failure
   branch emits a **real, unstripped** log line (`LokiRideableComponent.cpp:171`). Both are receipts
   that do not exist today.

6. **★★★★★ [M] NEW, and bigger than the lane's question: `AuthAddPlayer` and `AuthRemovePlayer` are
   STRIPPED FOLDS (`impl = 0x0F7EC20 = ret 0`)**, from the same record table. ⇒ **the only reflected
   writers of `PlayersInside` do nothing in this client**, which is *why* the array is empty and why
   no amount of legitimate driving will ever populate it. A poke is the only route, by construction.

---

## 1. Verified extent + full page-coverage check

`.pdata` rows are per-ROW; this function is **six chained rows**. I parsed the `UNWIND_INFO` flags
directly (`UNW_FLAG_CHAININFO = 0x4`) and followed each chain to its parent:

```
row 0x55cce70-0x55ccefa  unwind@0x97fc9b4  flags=0x3 (E|U handler, rva 0x751ddb8)   <- PARENT
row 0x55ccefa-0x55ccf0a  unwind@0x97fc9d0  flags=0x4  CHAINED -> 0x55cce70-0x55ccefa
row 0x55ccf0a-0x55cd07d  unwind@0x97fc9e8  flags=0x4  CHAINED -> 0x55ccefa-0x55ccf0a
row 0x55cd07d-0x55cd464  unwind@0x97fc9fc  flags=0x4  CHAINED -> 0x55cd464-0x55cd4e7
row 0x55cd464-0x55cd4e7  unwind@0x97fca34  flags=0x4  CHAINED -> 0x55ccefa-0x55ccf0a
row 0x55cd4e7-0x55cd506  unwind@0x97fca44  flags=0x4  CHAINED -> 0x55cce70-0x55ccefa
--- next function is a NEW root (flags=0x0):
row 0x55cd510-0x55cd5a5  unwind@0x97fca98  flags=0x0   = AuthPlayerEnterWorldAttachedToRidable
```

**[M] EXTENT = `0x55CCE70 .. 0x55CD506`, size `0x696` = 1686 bytes.** The last instruction is
`0x55CD505 ret`; `0x55CD506` decodes as junk (`ad c3 ec 38 …`). The first `.pdata` row's 138 bytes is
**not** the function size — citing it would have truncated the body at the very guard block this lane
exists to read.

**Coverage — the whole extent is decrypted:**
```
page 0x055CC000  present   (nonzero 3689 / 4096)
page 0x055CD000  present   (nonzero 3703 / 4096)
extent 0x696 bytes;  zero bytes inside extent = 172 of 1686  (xmm-save padding + imm zeros)
capstone linear decode: 353 instructions covering 1686 of 1686 bytes, terminating on `ret`
```
⇒ **no COVERAGE-BLOCKED region inside the function.** Every "there is no X in this function"
statement below is over fully-decrypted bytes.

### 1a. Signature — [M], two independent instruments agreeing

**(i) From the exec thunk's own call site** (uncapped read of `0x54561D0`, invocation at `0x5456357`):
```
0x5456342  mov  rdx, [rsp+0x30]        ; arg1  APlayerState*        (object, FFrame-stepped)
0x5456347  lea  r9,  [rsp+0x38]        ; arg3  &TSubclassOf<...>    <-- BY POINTER
0x545634c  mov  r8,  rsi               ; arg2  &FVector Location    <-- BY POINTER
0x545634f  mov  byte [rsp+0x20], bpl   ; arg4  bool bRepositionPlayer  (5th slot, stack)
0x5456354  mov  rcx, r14               ; this
0x5456357  call 0x55CCE70
```
**(ii) From `tools/asdump/out/binds_members.csv:44931`** (UHT-derived, wholly independent of the
disassembly):
```
ULokiRideableComponent  method 2
void AuthPlayerEnterWorld(ALokiPlayerState PlayerState, const FVector& Location,
                          TSubclassOf<UGameplayEffect> EffectWhenEnteringWorld = nullptr,
                          bool bRepositionPlayer = false)
```
The two agree on arity, order, by-reference-ness of `Location`, and the class of the effect. My
disassembly derived `UGameplayEffect` **independently**, from the literals `L"/Script/GameplayAbilities"`
and `L"GameplayEffect"` inside the `StaticClass()` accessor at `0x4445BC0` that the `IsChildOf` test
calls — so `EffectClass`'s type is measured twice by disjoint routes.

⇒ **exactly the four slots S131 bound.** Note `r9` is *always a valid pointer* (a thunk stack slot)
even when `EffectClass` is null — which is why passing `EffectClass = null` could not have faulted,
and why "no fault" was never evidence about where it bailed.
★ Also from (ii): **`bRepositionPlayer` DEFAULTS TO `false`**, i.e. the default route is the
non-reposition path at `0x55CD464`.

---

## 2. Annotated disassembly — entry through the point of no return

Bytes are as printed by the tool at the address shown; nothing is transcribed from elsewhere.

```asm
;; ================= GUARD 1 : PlayerState != nullptr =================
0x055CCE70  4885d2               test rdx, rdx                 ; rdx = arg1 = ALokiPlayerState*
0x055CCE73  0f848c060000         je   0x55CD505                ; -> the BARE `ret`; frame never built
                                                               ;    SILENT

;; ---- frame set up (5 pushes, lea rbp,[rsp-0x170], sub rsp,0x270), /GS cookie ----
0x055CCE79  55                   push rbp
0x055CCE7A  57                   push rdi
0x055CCE7B  4154                 push r12
0x055CCE7D  4155                 push r13
0x055CCE7F  4156                 push r14
0x055CCE81  488dac2490feffff     lea  rbp, [rsp - 0x170]
0x055CCE89  4881ec70020000       sub  rsp, 0x270
0x055CCE90  488b05f1d27004       mov  rax, [rip + 0x470d2f1]   ; -> 0x9CDA188  __security_cookie
0x055CCE97  4833c4               xor  rax, rsp
0x055CCE9A  488985a0000000       mov  [rbp + 0xa0], rax

;; ================= GUARD 2 : IsValid(PlayerState) =================
0x055CCEA1  8b420c               mov  eax, [rdx + 0xc]         ; UObject::ObjectFlags @ +0x0C
0x055CCEA4  4d8bf1               mov  r14, r9                  ; r14 = &EffectWhenEnteringWorld
0x055CCEA7  c1e81e               shr  eax, 0x1e                ; keep bits 30..31
0x055CCEAA  4d8be8               mov  r13, r8                  ; r13 = &Location (FVector, 3 doubles)
0x055CCEAD  f6d0                 not  al
0x055CCEAF  4c89442458           mov  [rsp + 0x58], r8
0x055CCEB4  4c8be2               mov  r12, rdx                 ; r12 = PlayerState
0x055CCEB7  488bf9               mov  rdi, rcx                 ; rdi = this (ULokiRideableComponent*)
0x055CCEBA  a801                 test al, 1                    ; passes iff bit30 of ObjectFlags == 0
0x055CCEBC  0f8425060000         je   0x55CD4E7                ; -> cookie check + epilogue.  SILENT
                                                               ; bit30 = RF_MirroredGarbage (UE5);
                                                               ; this pair IS the inline ::IsValid()

;; ================= GUARD 3 : PlayersInside is non-empty =================
0x055CCEC2  488b8920010000       mov  rcx, [rcx + 0x120]       ; PlayersInside.Data (TArray<APlayerState*>)
0x055CCEC9  48638728010000       movsxd rax, [rdi + 0x128]     ; PlayersInside.Num
0x055CCED0  488d14c1             lea  rdx, [rcx + rax*8]       ; end = Data + Num*8   (STRIDE 8)
0x055CCED4  483bca               cmp  rcx, rdx
0x055CCED7  0f840a060000         je   0x55CD4E7                ; empty -> bail.  SILENT

;; ================= GUARD 4 : PlayersInside CONTAINS this PlayerState ============
0x055CCEDD  0f1f00               nop
0x055CCEE0  4c3921               cmp  [rcx], r12               ; PlayersInside[i] == PlayerState ?
0x055CCEE3  740e                 je   0x55CCEF3                ; FOUND -> continue
0x055CCEE5  4883c108             add  rcx, 8
0x055CCEE9  483bca               cmp  rcx, rdx
0x055CCEEC  75f2                 jne  0x55CCEE0
0x055CCEEE  e9f4050000           jmp  0x55CD4E7                ; NOT FOUND -> bail.  SILENT

;; ================= POINT OF NO RETURN =================
0x055CCEF3  488b87c0000000       mov  rax, [rdi + 0xc0]        ; UActorComponent::WorldPrivate
0x055CCEFA  48899c2468020000     mov  [rsp+0x268], rbx         ; extra callee-saves (chained .pdata row)
0x055CCF02  4889b42460020000     mov  [rsp+0x260], rsi
0x055CCF0A  4c89bc2458020000     mov  [rsp+0x258], r15
0x055CCF12  4885c0               test rax, rax
0x055CCF15  7508                 jne  0x55CCF1F
0x055CCF17  488bcf               mov  rcx, rdi
0x055CCF1A  e8212dfefd           call 0x35AFC40                ; <-- FIRST CALL IN THE FUNCTION
                                                               ;     UObject::GetWorld() slow path
0x055CCF1F  488bc8               mov  rcx, rax                 ; rcx = UWorld*
0x055CCF22  e8291c9bfb           call 0x0F7EB50                ; *** STRIPPED FOLD  xor eax,eax; ret
                                                               ;     = the round-game-mode getter
0x055CCF27  498d8c2470040000     lea  rcx, [r12 + 0x470]       ; NO test/jcc on rax -> NOT GATED  [M]
0x055CCF2F  4889442450           mov  [rsp + 0x50], rax        ; stash the null RGM
0x055CCF34  488b11               mov  rdx, [rcx]               ; vptr of the sub-object at PS+0x470
0x055CCF37  488bd8               mov  rbx, rax                 ; rbx = null RGM (second copy)
0x055CCF3A  ff5210               call qword ptr [rdx + 0x10]   ; virtual slot 2 on PS+0x470  -> r15
```

**Everything past `0x55CCEF3` runs unconditionally to `MulticastOnPlayerEnteredWorld` and the
epilogue.** Verified by exhaustive capstone branch enumeration over all 1686 bytes (32 branches; the
only ones leaving the extent are the four guards):

```
=== who reaches the exits ===
  0x55cd4e7 (cookie + epilogue) <- 0x55ccebc, 0x55cced7, 0x55cceee      <-- G2, G3, G4
  0x55cd505 (bare ret)          <- 0x55cce73                            <-- G1
```

### The rest of the body (summary; all [M] unless marked)

```
0x55CCF3D..0x55CD05E   optional GameplayEffect block:
                       rsi = *r9 (EffectClass); if null -> skip to 0x55CD068
                       Cast via FStructBaseChain fast path
                         [UStruct+0x38] = StructBaseChainArray, [+0x40] = NumStructBasesInChainMinusOne
                       comparand = call 0x4445BC0 = UGameplayEffect::StaticClass()
                       0x55CCF84  call 0x106B650  <- ENGINE log, Class.h:372
                                  "Mismatch NumStructBasesInChainMinusOne: %d, ..."
                                  gated on FLogCategory@0x9E1DEA0 (Verbosity=5, CompileTime=7);
                                  only reachable if NumStructBasesInChainMinusOne < 0 (broken chain)
                       r15->vtable[0x6c8](r15, &ctx)          ; ASC MakeEffectContext/Spec  [I]
                       [UClass+0x178] = ClassDefaultObject ; 0x1225F20 = UClass::CreateDefaultObject
                       0x55CD017  call 0x4467B90              ; apply-GE (COVERAGE-BLOCKED, see 4)
                       TSharedPtr release (lock xadd on +8 / +0xC)

0x55CD068  cmp byte [rbp+0x1c0], 0        ; = the 5th arg slot = bRepositionPlayer   [M, computed:
0x55CD077  je  0x55CD464                  ;   rbp = entry_rsp-0x198, so rbp+0x1C0 = entry_rsp+0x28]

--- bRepositionPlayer == TRUE : terrain search ---------------------------------------
0x55CD0D0  call [rip+0x207f1e2] -> IAT 0x764C2B8 ; then `and eax,0x7fff`  => rand()
           random start angle; loop esi = 0,2,4,... `cmp esi,0x40; jl 0x55CD130` = 32 iterations
0x55CD1AC  call 0x5666A00 = IsValidPositionOnNavmesh    (named from .data record, see 4)
0x55CD238  call 0x5656550 = FindNearbyPointOnNavMesh    (named from .data record, see 4)
0x55CD2B9 / 0x55CD36B  call 0x56CB9F0   ; trace, tagged with FName L"PlaceOnGroundTrace"
0x55CD2E9  call 0x106B650  <- LOG (real, unstripped):
           "Could not find a valid 3D terrain location to spawn this player, this may result in
            the player respawning in an unexpected location."
           LokiRideableComponent.cpp:171 ; category FLogCategory@0x9D28CF8
0x55CD38F  call 0x10A2980 (rotation/quat helper); builds a 96-byte FTransform at [rbp+0x40]
0x55CD405  call 0x0F7EB50   *** STRIPPED FOLD ***   rcx = null RGM, rdx = PlayerState,
                                                    r8 = &FTransform, r9 = 0, [rsp+0x20] = 0
0x55CD462  jmp 0x55CD4CC

--- bRepositionPlayer == FALSE (the DEFAULT) : use the caller's Location verbatim -----
0x55CD464..0x55CD4C3  build the same 96-byte FTransform straight from *r13 (the Location arg)
0x55CD4C7  call 0x0F7EB50   *** STRIPPED FOLD ***   rcx = rbx = null RGM, same arg shape

--- common tail (both passing paths) --------------------------------------------------
0x55CD4CC  mov rdx, r12 ; mov rcx, rdi
0x55CD4D2  call 0x54537C0 = ULokiRideableComponent::MulticastOnPlayerEnteredWorld   (REAL)
0x55CD4E7  cookie check (call 0x751DEB0) ; epilogue ; 0x55CD505 ret
```

---

## 3. ORDERED guard list

| # | site | exact test | passes when | on failure | logged? |
|---|---|---|---|---|---|
| **G1** | `0x55CCE70` | `test rdx,rdx` / `je 0x55CD505` | `PlayerState != nullptr` | jumps to the **bare `ret`** — the stack frame is never even built | **SILENT** |
| **G2** | `0x55CCEA1`–`0x55CCEBC` | `eax = PS->ObjectFlags(+0x0C); eax >>= 30; not al; test al,1; je` | `ObjectFlags & (1<<30) == 0`, i.e. **`IsValid(PlayerState)`** (bit 30 = `RF_MirroredGarbage`) | `je 0x55CD4E7` (cookie + epilogue) | **SILENT** |
| **G3** | `0x55CCEC2`–`0x55CCED7` | `Data = this->PlayersInside.Data(+0x120); Num = (+0x128); cmp Data, Data+Num*8; je` | **`PlayersInside.Num() != 0`** | `je 0x55CD4E7` | **SILENT** |
| **G4** | `0x55CCEE0`–`0x55CCEEE` | linear `cmp [rcx], r12` over `[Data, Data+Num*8)`, stride 8 | **some `PlayersInside[i] == PlayerState`** | `jmp 0x55CD4E7` | **SILENT** |
| — | `0x55CCF22` | `call 0x0F7EB50` | *(no test at all)* | **not a guard** — result carried forward to `0x55CD405`/`0x55CD4C7` | n/a |

**[M] All four are silent, and provably so:** the first `call` instruction anywhere in the extent is
at `0x55CCF1A`, which is after the last bail. There is no logging point, no `ensure`, no `check`
reachable on any bail path.

**⇒ The live S131 R4 result (`no fault, NO log line, hero did not move, PlayersInsideCount 0→0`) is
fully explained by G3.** `PlayersInside` was measured live as `Data=0 Num=0 Max=0` [M, S131], so
`Data == Data+0*8` and `0x55CCED7` takes the bail. **The null is NAMED, not uninterpretable.**
⚠ Honest scope: G3 and G4 share a bail target and are both silent, so the *observed* evidence alone
cannot separate them; it is the measured `Num=0` that selects G3.

**Offset sanity — three independent confirmations inside the same class:**
`ContainsPlayer` (impl `0x55D0270`, REAL, reflected) is a **byte-for-byte twin of G3+G4** — same
`+0x120`/`+0x128`, same stride 8, returning `al`. `HasEverContainedPlayer` (impl `0x55DCAA0`, REAL)
opens with the identical two loads. `OnRep_PlayersInsideCount` (impl `0x55E0FC0`) reads `+0x11C` and
broadcasts the delegate at `+0xE0`; `CanExit` (impl `0x525C240`) reads `+0x118`.
⇒ `bCanExit@0x118 · PlayersInsideCount@0x11C · PlayersInside{Data@0x120, Num@0x128, Max@0x12C}`.
★ **Free by-product:** `OnRep_PlayersInsideCount` doing `add rcx,0xE0` then a broadcast
**independently corroborates S131 §13** that `ULokiRideableComponent+0xE0` is
`OnPlayersInsideCountChanged`, not a round-game-mode cache.

---

## 4. Full call table (uncapped — my own capstone sweep of all 1686 bytes)

26 direct calls / 5 indirect / **14 distinct direct targets**. This is not a tool with a row cap; it
is a complete enumeration of the verified extent.

| site(s) | target | grade | identity |
|---|---|---|---|
| `0x55CCF1A`, `0x55CD19C`, `0x55CD1E9`, `0x55CD223`, `0x55CD276`, `0x55CD321` | `0x35AFC40` | **REAL** (`push rbx; sub rsp,0x20; mov rcx,[rcx+0xB8] …`) | `UObject::GetWorld()` slow path |
| **`0x55CCF22`** | **`0x0F7EB50`** | **FOLD** `33 c0 c3` | round-game-mode getter → always null. **NOT gated on.** |
| `0x55CCF3A` | *indirect* `[rdx+0x10]` | — | virtual slot 2 on the sub-object at `PlayerState+0x470` (ability-system accessor, **[I]**) |
| `0x55CCF4C` | `0x4445BC0` | **REAL** | `UGameplayEffect::StaticClass()` — named [M] from its own `L"/Script/GameplayAbilities"` + `L"GameplayEffect"` |
| `0x55CCF84` | `0x106B650` | **REAL** | log dispatcher; record `0x76EC5C8` → `Class.h:372` "Mismatch NumStructBasesInChainMinusOne" (engine; unreachable in practice) |
| `0x55CCFC1` | *indirect* `[rax+0x6c8]` | — | virtual on the object returned above |
| `0x55CCFE1` | `0x1225F20` | **REAL** (`mov rax,[rcx]; jmp [rax+0x428]`) | `UClass::CreateDefaultObject` (paired with the `[UClass+0x178]` CDO read) |
| `0x55CD017` | `0x4467B90` | **COVERAGE-BLOCKED** | page `0x4467000` is **ZERO in all six dumps** (merged4/3/2, tuthero, rideable, s129). No `.data` record. Apply-GE call [I]. Not one of the five *known* folds — but its body is unread, so **not graded**. |
| `0x55CD047`, `0x55CD05B` | *indirect* `[rax]`, `[rax+8]` | — | `TSharedPtr` deleter vtable (refcount release) |
| `0x55CD0D0` | *indirect* `[rip+0x207f1e2]` → IAT `0x764C2B8` | — | CRT import; followed by `and eax,0x7fff` ⇒ `rand()` |
| `0x55CD154` | `0x751E960` | **REAL** | CRT `sincos`-class SSE routine |
| `0x55CD1AC` | `0x5666A00` | **REAL** *(record table; page undecrypted)* | `.data 0x9BE64C0 = {"IsValidPositionOnNavmesh", 0x537B450, 0x5666A00}` — impl is **not** any of the five folds |
| `0x55CD1C7`, `0x55CD256`, `0x55CD2FF` | `0x1138F20` | **REAL** | `FName::FName` (arg = `L"PlaceOnGroundTrace"`) |
| `0x55CD238` | `0x5656550` | **REAL** *(record table)* | `.data 0x9BE4978 = {"FindNearbyPointOnNavMesh", 0x5371BE0, 0x5656550}` |
| `0x55CD2B9`, `0x55CD36B` | `0x56CB9F0` | **REAL** | large trace/sweep helper (own /GS cookie), takes the trace-tag FName |
| `0x55CD2E9` | `0x106B650` | **REAL** | log; record `0x8B1CC98` → **`LokiRideableComponent.cpp:171`**, "Could not find a valid 3D terrain location to spawn this player…" |
| `0x55CD38F`, `0x55CD46F` | `0x10A2980` | **REAL** | rotation/quat helper (own /GS cookie) |
| **`0x55CD405`** | **`0x0F7EB50`** | **FOLD** | **payload, reposition path** — `(nullRGM, PlayerState, &FTransform, 0, 0)` |
| **`0x55CD4C7`** | **`0x0F7EB50`** | **FOLD** | **payload, non-reposition path** — same arg shape |
| `0x55CD4D2` | `0x54537C0` | **REAL** | `.data 0x9C1E8D0 = {"MulticastOnPlayerEnteredWorld", 0x3BCD5B0, 0x54537C0}`; body = `FindFunction` + `call [thisVtable+0x270]` (ProcessEvent) |
| `0x55CD4F1` | `0x751DEB0` | **REAL** | `__security_check_cookie` |

⚠ `0x0F7EB50` has ~27,217 call sites image-wide, so the address **identifies nothing** about which
function `0x55CD405`/`0x55CD4C7` originally were. What it establishes is only, and exactly, that they
are **stripped**.

Fold counts across the family, for the record (my own capstone sweep, per verified extent):
```
AuthPlayerEnterWorld                  [0x55cce70-0x55cd506]  0xF7EB50 x3   0xF7EC20 x0
AuthPlayerEnterWorldAttachedToRidable [0x55cd510-0x55cd7fa]  0xF7EB50 x1   0xF7EC20 x1
AuthPlayerPreSpawnOnAddToPlane        [0x55cd800-0x55cd9f0]  0xF7EB50 x1   0xF7EC20 x2
AuthPlayerDetachPlayerFromRidable     [0x55cccb0-0x55cce68]  0xF7EB50 x0   0xF7EC20 x2
```
The last row independently reproduces §14.1's correction: **detach is not fold-free — two `0xF7EC20`.**

### 4a. The whole reflected class, graded — a free by-product worth more than the lane

Sweeping the `.data` `{name, thunk, impl}` records over `0x9C1E400..0x9C1EB00` (S130's instrument; it
grades REAL/EMPTY **without** the code page being decrypted, because the fold addresses are constants):

```
AuthAddPlayer                          thunk=0x2c2ce30  impl=0x0f7ec20   *** FOLD ret 0 ***
AuthRemovePlayer                       thunk=0x2c2ce30  impl=0x0f7ec20   *** FOLD ret 0 ***
AuthSetCanJump                         thunk=0x5296f30  impl=0x0f7ec20   *** FOLD ret 0 ***
AuthPlayerEnterWorldNew                thunk=0x5456460  impl=0x0f7ec20   *** FOLD ret 0 ***
AuthPlayerEnterWorld                   thunk=0x54561d0  impl=0x55cce70   REAL
AuthPlayerEnterWorldAttachedToRidable  thunk=0x5456380  impl=0x55cd510   REAL
AuthPlayerPreSpawnOnAddToPlane         thunk=0x5456540  impl=0x55cd800   REAL
AuthPlayerDetachPlayerFromRidable      thunk=0x5456100  impl=0x55cccb0   REAL
CanExit                                thunk=0x5260ec0  impl=0x525c240   REAL
ContainsPlayer                         thunk=0x5456700  impl=0x55d0270   REAL
GetLandingTeleportLocation             thunk=0x5456c80  impl=0x55d89f0   REAL
GetRidePosition                        thunk=0x5457070  impl=0x55dab50   REAL
HasEverContainedPlayer                 thunk=0x5457280  impl=0x55dcaa0   REAL
MulticastOnPlayerEntered               thunk=0x53bd130  impl=0x5453780   REAL
MulticastOnPlayerEnteredWorld          thunk=0x3bcd5b0  impl=0x54537c0   REAL
MulticastOnPlayerExited                thunk=0x54573b0  impl=0x5453800   REAL
OnRep_bCanExit                         thunk=0x54577b0  impl=0x55e1000   REAL
OnRep_PlayersInsideCount               thunk=0x5457730  impl=0x55e0fc0   REAL
```
⚠ `AuthAddPlayer`/`AuthRemovePlayer` share thunk `0x2c2ce30`, which CLAUDE.md already records as
**23-way ICF-folded and NON-IDENTIFYING** — the *thunk* proves nothing; the **impl** is what grades.
★ `GetLandingTeleportLocation` REAL at `0x55D89F0` reproduces S131 §13's correction of FK-22 §2.5.

---

## 5. Is `PlayersInside` writable by anything in this client?

- **[M] The two reflected writers are folds** (§4a). Nothing routed through `AuthAddPlayer` will ever
  append.
- **[M] `AuthPlayerEnterWorld` itself never writes it.** Exhaustive capstone operand scan over the
  extent for displacements `0x11C/0x120/0x128/0x12C/0x130/0x138/0x13C` with a non-RIP/RSP/RBP base:
  ```
  0x55ccec2 [read] mov rcx, qword ptr [rcx + 0x120]
  0x55ccec9 [read] movsxd rax, dword ptr [rdi + 0x128]
  ```
  **Two reads, zero writes. No `Empty()`, no `RemoveAt()`, no `ResizeGrow`.**
- Same scan on the siblings: `AuthPlayerDetachPlayerFromRidable` touches only `+0x130`
  (`PlayersAttached`); `AuthPlayerEnterWorldAttachedToRidable` **writes** `+0x138` and reads `+0x130`
  (its `PlayersAttached.Add`) and never touches `+0x120`.
  ★ *This is also the positive control for the scan itself* — the same pass that reports "no writes"
  in one function reports real writes in another, so a silent-failure scanner is excluded.
- A page-aligned linear sweep of the class's whole code cluster `0x55CC000..0x55E4000` (22 of 24 pages
  decrypted; `0x55D1000` and `0x55D2000` are **ZERO = coverage-blocked**) found exactly one write to
  `+0x128` — at `0x55E3D94`, which is a **stride-24** `TArray::Add` (`[rax + rbp*3*8]`) inside
  `RequestMoveTowardAlive` (`.data 0x9BFBC70`), i.e. **a different class's array at the same offset.
  False positive, excluded.**
  ⚠ A page-aligned linear sweep can misalign, and two pages are undecrypted ⇒ this is **[I, strong],
  not [M]**: "no *decrypted* code in the cluster writes a stride-8 array at +0x120."

---

## 6. VERDICT

### FORECLOSED as a route to dismount / repositioning — [M]

**By which instructions:** `0x55CD405` (`bRepositionPlayer = true` path) and `0x55CD4C7`
(`bRepositionPlayer = false`, the default). Both are `e8 …` **direct calls to `0x0F7EB50` =
`33 c0 c3`**. They are the *only* calls on either terminal path that receive the PlayerState together
with the computed `FTransform`, and they are a member function of the round game mode invoked with a
`this` that is itself the null returned by the stripped getter at `0x55CCF22`.

Supporting facts, all [M] over fully-decrypted bytes:
- **The function contains no write to any actor or component transform.** Its only memory writes
  outside its own stack frame are the `TSharedPtr` refcount `lock xadd`s in the GameplayEffect block.
- It never touches `RootComponent` (`+0x1B0`), `USceneComponent::RelativeLocation` (`+0x158`), or
  `ComponentVelocity` (`+0x1A0`) — the offsets S131 used to observe the pod and hero.
- **Contrast in the same class, same pass:** the *attached* variant `0x55CD510` **does** write
  (`mov [rsi+0x1c10], xmm0` at `0x55CD730`, plus the `PlayersAttached` append at
  `0x55CD742`/`0x55CD767`). So the absence here is a real difference between the two functions, not a
  limitation of the scan.

⇒ **`AuthPlayerEnterWorld` is not a way round the wall and is not a second dismount primitive.** This
*confirms* the handoff's §12(b) conclusion, which was reached from "it calls the same stripped getter
un-gated". The result here is stronger and independent: **even if the getter returned a live round
game mode, the two calls that would consume it are themselves stripped.** A poke that produced a
round game mode would still change nothing.

### VIABLE-WITH-A-POKE, only as an INSTRUMENT — [I], untested

If someone wants to run the body anyway (to test whether the navmesh/terrain search works in
`LVL_Tutorial`, or to fire the multicast):

**The poke, precisely.** On the live `ULokiRideableComponent` `C`:
1. Grow the array with the game's own allocator, exactly as the wall does:
   `n = *(int32*)(C+0x128)` (= 0); `*(int32*)(C+0x128) = n+1`;
   if `n+1 > *(int32*)(C+0x12C)` then **`call 0x0F988D0(C+0x120, n)`**;
   then `*((void**)(*(void***)(C+0x120)) + n) = PlayerState`.
   ★ **`0x0F988D0` is the correct helper and this is [M], not a guess:** it is the *same* `ResizeGrow`
   instantiation the wall calls at `0x55CD75B` for `PlayersAttached`, and both arrays have **identical
   element stride 8** (`[rax + rbx*8]` in the wall's append, `[rcx + rax*8]` in G3). The 24-byte
   instantiation is a different address (`0x0F98B40`, used by `RequestMoveTowardAlive`) —
   **do not cross them.**
2. **Readback is free and reflected:** `ContainsPlayer` (thunk `0x5456700`, impl `0x55D0270`,
   `bool(APlayerState*)`) is the byte-twin of the guard just satisfied, and S131 already used it as a
   working positive control through the S55 primitive on this exact class.
3. Then S55-call `AuthPlayerEnterWorld` (thunk `0x54561D0`).

**Risk assessment — the foreign-pointer hazard does NOT arise here, and that is measured:**
- The prior session's objection was "a `TArray.Data` pointing at non-game-heap memory means any later
  `Empty()`/`RemoveAt()` frees a foreign pointer." **Using `0x0F988D0` removes the premise entirely**
  — the buffer is allocated by the game's own allocator, so any later free is a legal free. The
  reasoning the handoff applies to the `PlayersAttached` recipe transfers **because the element stride
  is identical and the helper is literally the same function**.
- Additionally, **`AuthPlayerEnterWorld` itself performs zero writes to `PlayersInside`** (§5), so the
  call under test cannot free or reallocate the buffer at all.
- **[I, strong]** nothing else in the decrypted part of the class writes that array either, and the
  only two reflected writers are folds — so the poked entry should simply persist. ⚠ Two pages of the
  class cluster are undecrypted, and non-reflected members (`BeginPlay`, `TickComponent`, `EndPlay`,
  net serializers) were not enumerated. **Do not upgrade this to [M].**
- ⚠ `PlayersInsideCount` (`+0x11C`) is a **separate replicated int32 with its own `OnRep`**; the poke
  does not update it, so the two will disagree. Harmless for this call (nothing on the path reads
  `+0x11C`), but it means a `PlayersInsideCount 0→1` readout will **not** move — do not use it as the
  receipt. Use `ContainsPlayer`.

**⚠⚠ THE ORDERING TRAP IS REAL AND IS NOW MEASURED AT THE INSTRUCTION.** S131 warned "do NOT poke
`PlayersInside` first — it makes `HasEverContainedPlayer` true, which turns the wall itself into a
SILENT no-op." Confirmed [M]:
```
HasEverContainedPlayer  impl 0x55DCAA0:
  0x55DCAA0  mov rax, [rcx + 0x120]      ; searches PlayersInside FIRST
  0x55DCAAA  movsxd r8, [rcx + 0x128]
  0x55DCAC0  cmp [rax], r9               ; == PlayerState ?
  0x55DCAC3  je  0x55DCB57               ; -> returns TRUE
  (falls through to a pointer-hash TSet lookup only if not found)

AuthPlayerEnterWorldAttachedToRidable (the wall) impl 0x55CD510:
  0x55CD54E  call 0x55DCAA0
  0x55CD553  test al, al
  0x55CD555  jne 0x55CD77B               ; SILENT bail, BEFORE the round-game-mode getter
```
⇒ **poking `PlayersInside` destroys the wall's `failed to get the round game mode` receipt**, which is
currently the project's best positive control on this surface. If both arms are wanted in one sitting,
**run the wall's arm first**, then poke, then run `AuthPlayerEnterWorld`.
★ Note this also names a guard the wall has that `AuthPlayerEnterWorld` does **not**: the two
functions are not "the same body with one difference" — the wall gates on `HasEverContainedPlayer`
and on the getter's result; ours gates on `PlayersInside` membership and on neither.

### What such a run would actually buy
- `MulticastOnPlayerEnteredWorld` fires (REAL; `FindFunction` + `ProcessEvent`) — a Blueprint-visible
  event that has never been driven on this client.
- With `bRepositionPlayer = 1`, the navmesh + `PlaceOnGroundTrace` search runs for up to 32 angles,
  and its failure emits a **real, unstripped** line at `LokiRideableComponent.cpp:171`. That is a new,
  free, per-call receipt for whether navmesh data exists around the tested point — and S131 measured
  mass navmesh generation across `LVL_Tutorial`, so a *success* (silence) would itself be informative.
  ⚠ Silence is ambiguous alone; pair it with the `ContainsPlayer` readback so "did the call even
  dispatch" stays separable from "did the search succeed".
- **It will not move the hero.** Pre-register that, so a null is not later re-read as a fresh mystery.

---

## 7. Reconciliation of the two prior offline notes

| prior claim | verdict here |
|---|---|
| "requires the PlayerState to be ALREADY IN `PlayersInside`; `0x55CCEC2 mov rcx,[rcx+0x120]`, `0x55CCEC9 movsxd rax,[rdi+0x128]`, `0x55CCED7 je <bail>`, then a linear `cmp [rcx],r12` search jmp-ing to the same bail; both bails SILENT" | **CONFIRMED byte-for-byte [M].** Every address and instruction is exactly right. Refinements only: it is **two** guards (empty test + membership), and there are **two more silent guards before them** (null, `IsValid`) that the note did not mention. |
| "`0x55CCF22 call 0xF7EB50` … does NOT gate on the result; carries the 0 forward to a virtual call through `[PlayerState+0x470]`" | **CONFIRMED [M]** for the not-gated half. ⚠ **Refined:** the null RGM is *not* what feeds the `[PS+0x470]` virtual call — that call's `this` is `PS+0x470` itself (`lea rcx,[r12+0x470]; mov rdx,[rcx]; call [rdx+0x10]`). The null is stashed in `[rsp+0x50]`/`rbx` and consumed much later, at `0x55CD405`/`0x55CD4C7`. |
| "a prior note also claims THREE `0xF7EB50` calls in it. Reconcile: two? three?" | **THREE is correct [M]**, and both readings are compatible: **one** is the getter (`0x55CCF22`), **two** are the payload (`0x55CD405`, `0x55CD4C7`). Exhaustive uncapped sweep of the verified 1686-byte extent. |
| S131: "R4 bailed at `0x55CCED7`" | **Consistent [M].** With `Num=0` the empty test fires and the membership loop is never entered. The two guards are indistinguishable *from the observed evidence* (same target, both silent); the live `Num=0` is what selects G3. |
| S131: "AuthPlayerEnterWorld is NOT a way round the wall" | **CONFIRMED, and strengthened [M].** Independently established here from the payload calls being folds — which holds even if the getter were repaired. |

---

## 8. Instrument caveats (stated, per house rules)

- `fkdis.py callxref`/`findptr` cap at 200 rows. **No count in this document relies on them**: the
  call table in §4 is my own uncapped capstone sweep of the verified extent. `findptr` was used only
  for *existence* lookups into `.data`, each of which returned a single hit whose surrounding record
  was then read directly.
- `0x4467B90`, `0x5666A00`, `0x5656550` sit on **all-zero pages in every dump on disk** (`0x4467000`
  checked in merged4/merged3/merged2/tuthero/rideable/s129). Two of the three were still graded, via
  the `.data` record table; the third has no record and stays **COVERAGE-BLOCKED, not absent**.
- The §5 region sweep is page-aligned linear decoding and can misalign; two pages in the range are
  undecrypted. Its negative is graded **[I, strong]**, never [M].
- `[PlayerState+0x470]` is called an ability-system accessor **[I]**, from call shape only (embedded
  sub-object vptr, virtual slot 2, result later receiving a `[vtbl+0x6c8]` call inside a
  GameplayEffect context). No name was recovered. Do not write it up as measured.
- The `RF_MirroredGarbage` naming of bit 30 is **[I]** (stock UE5 `EObjectFlags` numbering applied to
  a measured `ObjectFlags >> 30` test). What is **[M]** is the test itself: *bit 30 of the UObject
  flag word at `+0x0C` must be clear*. CLAUDE.md's independently-measured result that stock
  `EInternalObjectFlags` numbering is in force in this build (bit 24 `ClusterRoot` at 100.000 % over
  200,437 objects) supports the naming but is about a different flag word.
- Every rip-relative target, every rel32 target and every stack-frame offset here was computed by
  `python`/capstone. `[rbp+0x1c0] == entry_rsp+0x28 == the 5th argument slot` is the one hand-checkable
  step; it was re-derived twice (5 pushes = 0x28; `lea rbp,[rsp-0x170]`; `-0x28-0x170+0x1C0 = +0x28`)
  and it is corroborated by the UHT signature having exactly four parameters.
