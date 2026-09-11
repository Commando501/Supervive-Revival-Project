# S132 LANE 3 — Transcription of the append we are mirroring
### `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable`, impl `0x55CD510`

All work OFFLINE against `dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA).
Zero launches, zero injections. Every address recomputed with a machine (`python -c`), never by hand.

---

## 0. HEADLINE — the recipe I was handed is CORRECT, with three refinements

The recipe as handed:

```
old = [c+0x138];  [c+0x138] = old+1;
if (old+1 > [c+0x13C])  call 0xF988D0(rcx = c+0x130, edx = old);
[ [c+0x130] + old*8 ] = PS
```

**[M] VERDICT: this matches the shipped bytes instruction for instruction, in that order.** No
step is missing, no step is out of order, and the element stored is the raw `PlayerState`
pointer. Three refinements, none of which invalidates it:

| # | refinement | grade |
|---|---|---|
| R1 | The growth test is **UNSIGNED** (`cmp eax, [Max]` + `jbe` skip). The recipe's `>` is correct in effect for non-negative Num/Max, but write it as an unsigned compare. | [M] |
| R2 | `old` is read with **`movsxd`** (sign-extended i32 -> i64) and used as the 64-bit index scale; `old+1` is computed in **32 bits** (`lea eax,[rbx+1]`). | [M] |
| R3 | **The increment-before-grow is a FUNCTIONAL PRECONDITION, not a style choice.** `ResizeGrow` (`0xF988D0`) *reads `ArrayNum` back out of the struct* (`movsxd rbx,[rcx+8]`) to size the new allocation, and **`int3`-aborts if `ArrayNum < PreviousNum`**. A mirror that increments *after* the grow would allocate for `old` elements and then write `Data[old]` out of bounds. | [M] |

**Do not "clean up" the ordering.** See §5 for the `ResizeGrow` disassembly that establishes R3.

---

## 1. EXTENT + DECRYPTION — verified, and the chaining is PROVED, not assumed

### 1.1 `.pdata` rows (`tools/strxref/index/pdata_union.csv`)

```
begin_rva,end_rva,size,unwind_rva,seen_in_dumps
0x55CD510,0x55CD5A5,149,0x97FCA98,20
0x55CD5A5,0x55CD77B,470,0x97FCAB0,20
0x55CD77B,0x55CD794, 25,0x97FCAC8,20
0x55CD794,0x55CD7B2, 30,0x97FCAD8,20
0x55CD7B2,0x55CD7FA, 72,0x97FCAC8,20
```

Machine-checked: contiguous (no gaps), sizes sum to **746**, and
`0x55CD7FA - 0x55CD510 = 0x2EA = 746`. **[M] extent confirmed: 5 rows, 746 bytes.**

### 1.2 The rows are ONE function — proved from the UNWIND_INFO, not from adjacency

Rows 2-5 all carry `UNW_FLAG_CHAININFO` (0x4) and their chained parent `RUNTIME_FUNCTION`
is byte-identical in all four cases:

```
row 0x55CD510..0x55CD5A5 unwind=0x97FCA98 flags=0x0 (primary)  prolog=37 codes=9
row 0x55CD5A5..0x55CD77B unwind=0x97FCAB0 flags=0x4 CHAINED -> begin=0x55CD510 end=0x55CD5A5 unwind=0x97FCA98
row 0x55CD77B..0x55CD794 unwind=0x97FCAC8 flags=0x4 CHAINED -> begin=0x55CD510 end=0x55CD5A5 unwind=0x97FCA98
row 0x55CD794..0x55CD7B2 unwind=0x97FCAD8 flags=0x4 CHAINED -> begin=0x55CD510 end=0x55CD5A5 unwind=0x97FCA98
row 0x55CD7B2..0x55CD7FA unwind=0x97FCAC8 flags=0x4 CHAINED -> begin=0x55CD510 end=0x55CD5A5 unwind=0x97FCA98
```

**[M] All four subordinate rows chain to `0x55CD510`.** That is strictly stronger than "the rows
are adjacent" — it is the linker's own statement that they are one function entered at `0x55CD510`.

**Free cross-check that fell out of it:** row 2's unwind codes decode to
`UWOP_SAVE_XMM128 xmm6 @ +0x150` and `UWOP_SAVE_NONVOL rsi @ +0x170`, which is exactly the pair of
instructions at `0x55CD5A5` / `0x55CD5AD`. Row 1's codes decode to
`r14@+0x188, rdi@+0x180, rbx@+0x178`, matching the three home-slot spills at `0x55CD519..0x55CD528`.
The unwind data and the instruction stream agree independently.

### 1.3 Decryption

```
$ python scratchpad/fk27/fkdis.py cov 0x55CD510 746 --dump merged4
  page 0x055CD000  present
```

The whole function lives on the **single page `0x55CD000`** (`0x55CD510` and `0x55CD7F9` are both in
it). Byte-level check over the 746 bytes: **63 zero bytes, longest zero run = 3** — i.e. ordinary
`00` operand bytes, not an undecrypted region. First bytes `4885d2 0f847a020000`, last bytes
`...e818bba2fb eb81`. **[M] fully decrypted; no COVERAGE-BLOCKED region inside the function.**

---

## 2. IDENTITY AND SIGNATURE

**[M] The `.data` `{name_ptr, exec_thunk, impl}` record table names it:**

```
AuthPlayerEnterWorldAttachedToRidable   thunk=0x5456380  impl=0x55CD510
```

**[M] UHT signature** (`tools/asdump/out/binds_members.csv`, class 4540 `ULokiRideableComponent`,
method 3):

```cpp
void AuthPlayerEnterWorldAttachedToRidable(ALokiPlayerState* PlayerState,
                                           const FVector&    SpawnLocation);
```

Register mapping from the bytes — `rcx = this`, `rdx = PlayerState`, `r8 = &SpawnLocation`
(3 doubles) — matches the UHT signature exactly.

**Register roles held for the whole body** (verified exhaustively with capstone `regs_access`
over all 746 bytes; all three are Win64 **non-volatile**, so calls preserve them by contract):

| reg | written at | value | other writes |
|---|---|---|---|
| `rdi` | `0x55CD53E  mov rdi, rdx` | **the `PlayerState` pointer** | **only** the epilogue restore at `0x55CD787` |
| `r14` | `0x55CD543  mov r14, rcx` | **`this`** | **only** the epilogue restore at `0x55CD78B` |
| `rbx` | `0x55CD538  mov rbx, r8` | `&SpawnLocation` | repurposed at `0x55CD61D` and `0x55CD738`, both after its last use as `&SpawnLocation` (`0x55CD5B5`) |

=> **[M] the pointer stored into the array at `0x55CD767` is the caller's `PlayerState` argument,
verbatim — not derived, not re-fetched, not a wrapper.**

**Sibling neighbours from the same record table (free by-products):**

```
AuthPlayerDetachPlayerFromRidable  thunk=0x5456100  impl=0x55CCCB0   (REAL)
AuthPlayerPreSpawnOnAddToPlane                      impl=0x55CD800   (REAL)
AuthPlayerEnterWorld                                impl=0x55CCE70   (REAL)
AuthSetCurrentRideable             thunk=0x2C2CE30  impl=0x0F7EC20   <-- FOLD ret0, another empty stub in this class
```

---

## 3. COMPLETE ANNOTATED DISASSEMBLY

### 3.1 Prologue and the three pre-guards (`0x55CD510 .. 0x55CD55B`)

```
0x055CD510  4885d2               test rdx, rdx                       ; PlayerState == null?
0x055CD513  0f847a020000         je   0x55CD793                      ; -> BARE `ret`. Zero side effects, zero log.
0x055CD519  48895c2410           mov  [rsp+0x10], rbx                ; rbx  -> caller home slot (rdx-home)
0x055CD51E  48897c2418           mov  [rsp+0x18], rdi                ; rdi  -> caller home slot (r8-home)
0x055CD523  4c89742420           mov  [rsp+0x20], r14                ; r14  -> caller home slot (r9-home)
0x055CD528  55                   push rbp
0x055CD529  488d6c24a0           lea  rbp, [rsp-0x60]
0x055CD52E  4881ec60010000       sub  rsp, 0x160
0x055CD535  8b420c               mov  eax, [rdx+0xc]                 ; PS->ObjectFlags   (UObject+0x0C in this build)
0x055CD538  498bd8               mov  rbx, r8                        ; rbx = &SpawnLocation
0x055CD53B  c1e81e               shr  eax, 0x1e                      ; bit30 -> bit0  (RF_MirroredGarbage)
0x055CD53E  488bfa               mov  rdi, rdx                       ; *** rdi = PlayerState, for the rest of the fn ***
0x055CD541  f6d0                 not  al
0x055CD543  4c8bf1               mov  r14, rcx                       ; *** r14 = this, for the rest of the fn ***
0x055CD546  a801                 test al, 1
0x055CD548  0f842d020000         je   0x55CD77B                      ; PS is Garbage -> SILENT return (inline IsValid())
0x055CD54E  e84df50000           call 0x55DCAA0                      ; HasEverContainedPlayer(this, rdx=PS)   [REAL]
0x055CD553  84c0                 test al, al
0x055CD555  0f8520020000         jne  0x55CD77B                      ; ALREADY contained -> SILENT no-op  <<< THE ORDERING TRAP
```

**[M] `HasEverContainedPlayer` (`0x55DCAA0`) is a linear search of `PlayersInside`:**

```
0x055DCAA0  mov    rax, [rcx+0x120]        ; PlayersInside.Data
0x055DCAA7  mov    r9,  rdx                ; r9 = PS
0x055DCAAA  movsxd r8,  [rcx+0x128]        ; PlayersInside.Num
0x055DCAB4  lea    rdx, [rax + r8*8]       ; end
0x055DCAB8  cmp    rax, rdx / je ...       ; empty -> falls through to a hash lookup
0x055DCAC0  cmp    [rax], r9  / je <found>
```

=> This is the byte-level confirmation of the recorded ordering trap: **poking `PlayersInside`
(`+0x120`) before calling the wall makes `HasEverContainedPlayer` return true, and the wall then
returns SILENTLY at `0x55CD555` — no log line, no append, nothing to measure.** Confirmed as
written in `CLAUDE.md`.

### 3.2 The round-game-mode guard (`0x55CD55B .. 0x55CD58A`)

```
0x055CD55B  498b86c0000000       mov  rax, [r14+0xc0]                ; UActorComponent::WorldPrivate
0x055CD562  4885c0               test rax, rax
0x055CD565  7508                 jne  0x55CD56F
0x055CD567  498bce               mov  rcx, r14
0x055CD56A  e8d126fefd           call 0x35AFC40                      ; UActorComponent::GetWorld() slow path  [REAL]
0x055CD56F  488bc8               mov  rcx, rax                       ; rcx = UWorld*
0x055CD572  e8d9159bfb           call 0x0F7EB50                      ; *** THE STRIPPED GETTER: 33 c0 c3 -> ALWAYS 0 ***
0x055CD577  4885c0               test rax, rax
0x055CD57A  0f8432020000         je   0x55CD7B2                      ; -> "failed to get the round game mode"
0x055CD580  488bc8               mov  rcx, rax                       ; <-- THE ONLY READ OF THE RETURNED VALUE
0x055CD583  e848a8ffff           call 0x55C7DD0                      ; IsA<ALokiRoundGameMode> fast-tree  [REAL]
0x055CD588  84c0                 test al, al
0x055CD58A  0f8422020000         je   0x55CD7B2                      ; same bail
```

`0x35AFC40` reads `[this+0xB8]` (the component's Owner) and falls through to `AActor::GetWorld`.
`0x55C7DD0` is the standard UE5 `FClassBaseChain` IsA: `StaticClass()` -> `[obj+0x18]`
(`ClassPrivate`, the non-stock `classOff=0x18` this build uses) -> depth/cast-tree compare.

**[M] `0x55CD572` calls `0x0F7EB50`.** Re-read directly: `0x00F7EB50 = 33 c0 c3` =
`xor eax,eax; ret`. Confirmed against the fold table.

**Note the argument:** the stripped getter is called with the **UWorld** in `rcx`. That is the
same shape as the unstripped sibling `ULokiGameModeDropPlaneComponent` lifecycle override, which
reads `World->AuthorityGameMode` and IsA-checks it with **this same helper `0x55C7DD0`** — the
already-recorded reason the object exists and only the accessor was deleted.

### 3.3 Success path, part A — build the two teleport arguments (`0x55CD590 .. 0x55CD6FF`)

```
0x055CD590  f20f104310           movsd  xmm0, [rbx+0x10]             ; SpawnLocation.Z
0x055CD595  488bcf               mov    rcx, rdi                     ; rcx = PlayerState
0x055CD598  f20f580528ff5403     addsd  xmm0, [rip+0x354ff28]        ; -> .rdata 0x8B1D4C8 = 7500.0 (double)
0x055CD5A0  f20f104b10           movsd  xmm1, [rbx+0x10]             ; SpawnLocation.Z (raw)
0x055CD5A5  4889b42470010000     mov    [rsp+0x170], rsi             ; (start of pdata row 2)
0x055CD5AD  0f29b42450010000     movaps [rsp+0x150], xmm6
0x055CD5B5  0f1033               movups xmm6, [rbx]                  ; SpawnLocation.X, .Y
0x055CD5B8  f20f1145d8           movsd  [rbp-0x28], xmm0             ; stash Z+7500
0x055CD5BD  0f117520             movups [rbp+0x20], xmm6             ; local FVector A .X/.Y = SpawnLocation.X/.Y
0x055CD5C1  f20f114d30           movsd  [rbp+0x30], xmm1             ; local FVector A .Z    = SpawnLocation.Z  (RAW)
0x055CD5C6  e8050b0f00           call   0x56BE0D0                    ; GetLokiCharacter(PlayerState)   [REAL]
0x055CD5CB  488bf0               mov    rsi, rax                     ; *** rsi = the hero ALokiCharacter, for the rest ***
0x055CD5CE  4885c0               test   rax, rax
0x055CD5D1  0f84bd010000         je     0x55CD794                    ; -> "whithout a pre-spawned hero"  (NO append)
0x055CD5D7  488bc8               mov    rcx, rax
0x055CD5DA  e8e1b7f2ff           call   0x54F8DC0                    ; IsA<...> fast-tree on the hero  [REAL]
0x055CD5DF  84c0                 test   al, al
0x055CD5E1  0f84ad010000         je     0x55CD794                    ; same bail                        (NO append)

; ---- derive a GoalRotation from the hero's RootComponent, or ZeroRotator ----
0x055CD5E7  488b8eb0010000       mov    rcx, [rsi+0x1b0]             ; AActor::RootComponent  (+0x1B0)
0x055CD5EE  4885c9               test   rcx, rcx
0x055CD5F1  0f848d000000         je     0x55CD684                    ; null -> zero-rotator branch
0x055CD5F7  0f108100020000       movups xmm0, [rcx+0x200]
0x055CD5FE  0f108910020000       movups xmm1, [rcx+0x210]
0x055CD605  4881c1e8010000       add    rcx, 0x1e8
0x055CD60C  0f294590             movaps [rbp-0x70], xmm0
0x055CD610  0f294da0             movaps [rbp-0x60], xmm1
0x055CD614  e887c8aefc           call   0x20B9EA0                    ; lazy-init getter on RootComponent+0x1E8  [REAL]
0x055CD619  0f284d90             movaps xmm1, [rbp-0x70]
0x055CD61D  488bd8               mov    rbx, rax                     ; (rbx repurposed; &SpawnLocation no longer needed)
0x055CD620..0x055CD63F            cmpneqpd x2 / movmskpd / or / je    ; if the cached pair differs...
0x055CD641..0x055CD665            store-back + call 0x10A50C0         ; ...recompute (rotator math)  [REAL]
0x055CD66A  0f104320             movups xmm0, [rbx+0x20]
0x055CD66E  488d442470           lea    rax, [rsp+0x70]
0x055CD673  f20f104b30           movsd  xmm1, [rbx+0x30]
0x055CD678  0f11442470           movups [rsp+0x70], xmm0
0x055CD67D  f20f114d80           movsd  [rbp-0x80], xmm1
0x055CD682  eb1c                 jmp    0x55CD6A0
0x055CD684  0f10052db13f04       movups xmm0, [rip+0x43fb12d]        ; -> .data 0x99C87B8 = 0,0
0x055CD68B  488d45b0             lea    rax, [rbp-0x50]
0x055CD68F  0f1145b0             movups [rbp-0x50], xmm0
0x055CD693  f20f10052db13f04     movsd  xmm0, [rip+0x43fb12d]        ; -> .data 0x99C87C8 = 0.0
0x055CD69B  f20f1145c0           movsd  [rbp-0x40], xmm0

; ---- marshal the 13 LokiTeleportActor arguments ----
0x055CD6A0  0f1000               movups xmm0, [rax]
0x055CD6A3  4c8d45e0             lea    r8,  [rbp-0x20]              ; ARG3 = &GoalRotation
0x055CD6A7  c644246000           mov    byte [rsp+0x60], 0           ; arg13 bRequireTerrain = false
0x055CD6AC  f20f104810           movsd  xmm1, [rax+0x10]
0x055CD6B1  488d5500             lea    rdx, [rbp]                   ; ARG2 = &GoalPosition
0x055CD6B5  c644245801           mov    byte [rsp+0x58], 1           ; arg12 bEndFollowingActorOnSuccess = true
0x055CD6BA  33c0                 xor    eax, eax
0x055CD6BC  4889442450           mov    [rsp+0x50], rax              ; arg11 TeleportAbility = nullptr
0x055CD6C1  0f57db               xorps  xmm3, xmm3                   ; ARG4  MaxAdjustDistanceXY = 0.0f
0x055CD6C4  4889442448           mov    [rsp+0x48], rax              ; arg10 TeleportInstigator = nullptr
0x055CD6C9  488bce               mov    rcx, rsi                     ; ARG1 = the hero
0x055CD6CC  88442440             mov    byte [rsp+0x40], al          ; arg9  bRequireGround = FALSE (default is true)
0x055CD6D0  88442438             mov    byte [rsp+0x38], al          ; arg8  NavCheckType = None(0)
0x055CD6D4  0f2945e0             movaps [rbp-0x20], xmm0             ; GoalRotation .Pitch/.Yaw
0x055CD6D8  f20f1045d8           movsd  xmm0, [rbp-0x28]             ; Z+7500
0x055CD6DD  88442430             mov    byte [rsp+0x30], al          ; arg7  ClampToGround = 0
0x055CD6E1  f20f114510           movsd  [rbp+0x10], xmm0             ; GoalPosition.Z = SpawnLocation.Z + 7500
0x055CD6E6  f30f1005f2390d02     movss  xmm0, [rip+0x20d39f2]        ; -> .rdata 0x76A10E0 = 0.5f
0x055CD6EE  f30f11442428         movss  [rsp+0x28], xmm0             ; arg6  InitialZAdjustMultiplier = 0.5f (default)
0x055CD6F4  f30f115c2420         movss  [rsp+0x20], xmm3             ; arg5  MaxAdjustDistanceZ = 0.0f (default is 400)
0x055CD6FA  f20f114df0           movsd  [rbp-0x10], xmm1             ; GoalRotation .Roll
0x055CD6FF  0f297500             movaps [rbp], xmm6                  ; GoalPosition.X/.Y = SpawnLocation.X/.Y
```

**The 13 arguments map 1:1 onto the UHT signature** (`ULokiGameplayStatics::LokiTeleportActor`,
class 4335 method 112), which is an independent confirmation of the whole marshalling read:

```cpp
AActor* LokiTeleportActor(AActor* Actor, FVector GoalPosition, FRotator GoalRotation,
                          float MaxAdjustDistanceXY, float MaxAdjustDistanceZ = 400.0,
                          float InitialZAdjustMultiplier = 0.5,
                          ETeleportClampToGround ClampToGround = AllowToFloat,
                          ENavCheckType NavCheckType = None, bool bRequireGround = true,
                          AActor* TeleportInstigator = nullptr,
                          ULokiDisplayableAbility* TeleportAbility = nullptr,
                          bool bEndFollowingActorOnSuccess = true, bool bRequireTerrain = false);
```

Arg4 in `xmm3`, args 5..13 at `[rsp+0x20] .. [rsp+0x60]` in 8-byte slots — the last slot is
`0x20 + 8*8 = 0x60`, exactly where the final byte store lands. **[M]**

=> Semantically: the hero is teleported to **`SpawnLocation` raised 7,500 uu in Z**, with the
ground requirement switched OFF — i.e. put in the air, where the pod is.

### 3.4 Success path, part B — the four calls, then THE APPEND (`0x55CD703 .. 0x55CD76B`)

```
0x055CD703  e8e8a90900           call 0x56680F0     ; [1] LokiTeleportActor(hero, pos+7500Z, rot, ...)
0x055CD708  b201                 mov  dl, 1
0x055CD70A  488bce               mov  rcx, rsi
0x055CD70D  e83ecedcfd           call 0x339A550     ; [2] SetActorEnableCollision(hero, TRUE)
0x055CD712  488d5520             lea  rdx, [rbp+0x20]                 ; the RAW SpawnLocation copy
0x055CD716  488bce               mov  rcx, rsi
0x055CD719  e80244ffff           call 0x55C1B20     ; [3] ALokiCharacter::SpawnAndMoveLokiCharacter_MoveStep(hero, &SpawnLocation)
0x055CD71E  33d2                 xor  edx, edx
0x055CD720  488bce               mov  rcx, rsi
0x055CD723  e828cedcfd           call 0x339A550     ; [4] SetActorEnableCollision(hero, FALSE)
0x055CD728  488bce               mov  rcx, rsi
0x055CD72B  e810c620fe           call 0x37D9D40     ; [5] GetServerTime(hero)  -> float in xmm0
0x055CD730  f30f1186101c0000     movss [rsi+0x1c10], xmm0             ; [6] stamp it into hero+0x1C10

; ================== THE APPEND: PlayersAttached.Add(PlayerState) ==================
0x055CD738  49639e38010000       movsxd rbx, dword ptr [r14+0x138]    ; rbx = old = PlayersAttached.ArrayNum (i32, sign-extended)
0x055CD73F  8d4301               lea    eax, [rbx+1]                  ; eax = old+1                           (32-bit)
0x055CD742  41898638010000       mov    dword ptr [r14+0x138], eax    ; ArrayNum = old+1   <<< INCREMENT FIRST
0x055CD749  413b863c010000       cmp    eax, dword ptr [r14+0x13c]    ; cmp (old+1), ArrayMax
0x055CD750  760e                 jbe    0x55CD760                     ; UNSIGNED: skip grow if (old+1) <= Max
0x055CD752  8bd3                 mov    edx, ebx                      ; edx = PreviousNum = old
0x055CD754  498d8e30010000       lea    rcx, [r14+0x130]              ; rcx = &PlayersAttached   <<< BASE +0x130
0x055CD75B  e870b19cfb           call   0x0F988D0                     ; TArray::ResizeGrow(PreviousNum)
0x055CD760  498b8630010000       mov    rax, qword ptr [r14+0x130]    ; RELOAD Data (unconditional, post-grow)
0x055CD767  48893cd8             mov    qword ptr [rax + rbx*8], rdi  ; Data[old] = PlayerState        <<< THE STORE
; ==================================================================================

0x055CD76B  488bb42470010000     mov  rsi, [rsp+0x170]                ; epilogue-with-rsi/xmm6-restore
0x055CD773  0f28b42450010000     movaps xmm6, [rsp+0x150]
0x055CD77B  4c8d9c2460010000     lea  r11, [rsp+0x160]                ; bare epilogue
0x055CD783  498b5b18             mov  rbx, [r11+0x18]
0x055CD787  498b7b20             mov  rdi, [r11+0x20]
0x055CD78B  4d8b7328             mov  r14, [r11+0x28]
0x055CD78F  498be3               mov  rsp, r11
0x055CD792  5d                   pop  rbp
0x055CD793  c3                   ret
```

### 3.5 The two bail tails

```
; ---- BAIL A: GetLokiCharacter null / IsA failed ----
0x055CD794  803d2593a60402       cmp  byte [rip+0x4a69325], 2         ; FLogCategory @ .data 0xA036AC0 (Verbosity)
0x055CD79B  72ce                 jb   0x55CD76B
0x055CD79D  488d154cf85403       lea  rdx, [rip+0x354f84c]            ; static log record @ .rdata 0x8B1CFF0
0x055CD7A4  488d0d1593a604       lea  rcx, [rip+0x4a69315]            ; -> 0xA036AC0
0x055CD7AB  e8a0dea9fb           call 0x106B650                       ; the live logger
0x055CD7B0  ebb9                 jmp  0x55CD76B

; ---- BAIL B: THE ROUND-GAME-MODE WALL ----
0x055CD7B2  803dc786a60402       cmp  byte [rip+0x4a686c7], 2         ; FLogCategory @ .data 0xA035E80
0x055CD7B9  7213                 jb   0x55CD7CE
0x055CD7BB  488d1546f75403       lea  rdx, [rip+0x354f746]            ; static log record @ .rdata 0x8B1CF08
0x055CD7C2  488d0db786a604       lea  rcx, [rip+0x4a686b7]            ; -> 0xA035E80
0x055CD7C9  e882dea9fb           call 0x106B650                       ; the live logger  -> THE 0->2 RECEIPT
0x055CD7CE  488d155bf75403       lea  rdx, [rip+0x354f75b]            ; the raw message string @ .rdata 0x8B1CF30
0x055CD7D5  488d4c2470           lea  rcx, [rsp+0x70]
0x055CD7DA  e841f19dfb           call 0x0FAC920                       ; FString::Printf into a local
0x055CD7DF  488d4c2470           lea  rcx, [rsp+0x70]
0x055CD7E4  e837149bfb           call 0x0F7EC20                       ; *** FOLD ret0 — the message consumer is STRIPPED ***
0x055CD7E9  488b4c2470           mov  rcx, [rsp+0x70]
0x055CD7EE  4885c9               test rcx, rcx
0x055CD7F1  7488                 je   0x55CD77B
0x055CD7F3  e818bba2fb           call 0x0FF9310                       ; free the FString buffer
0x055CD7F8  eb81                 jmp  0x55CD77B
```

Decoded static log records (`{const TCHAR* Format, const ANSICHAR* File, int32 Line, ELogVerbosity}`):

| record | Format | File | Line | Verbosity |
|---|---|---|---|---|
| `.rdata 0x8B1CF08` | `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable failed to get the round game mode` | `...\Loki\Source\Loki\DropPhase\LokiRideableComponent.cpp` | **299** | 2 = Error |
| `.rdata 0x8B1CFF0` | `AuthPlayerEnterWorldAttachedToRidable: Attempting to attach ourselves to a drop pod whithout a pre-spawned hero.` (the game's own typo) | same file | **327** | 2 = Error |

**NEW AND OPERATIONALLY RELEVANT [M]: the two bails print under DIFFERENT log categories.**
Bail B uses `.data 0xA035E80`; bail A uses `.data 0xA036AC0`. `0xA035E80` has **exactly two**
`lea` xrefs in the whole image — `0x55CD7C5` (this function) and `0x55CD9AD` (inside
`AuthPlayerPreSpawnOnAddToPlane`, whose record `.rdata 0x8B1CE28` reads
`"ULokiRideableComponent::AuthPlayerPreSpawnOnAddToPlane failed to get the round game mode"`,
the exact string S131 measured going 0 -> 2). So `0xA035E80` is **`LogLokiRideable`**
[M by triangulation with that flown measurement]. `0xA036AC0` is a *different* category
(FName index `0x1A4E5` vs `0x1A4A0`) with ~20 xrefs across `LokiGameMode.cpp` / `LokiPlayerState.cpp`
sites; its **name is UNRESOLVED** — a grep of the archived log corpus for two of its other messages
returned nothing, so no live sample exists to name it from.

=> **`grep LogLokiRideable` will NOT catch the "whithout a pre-spawned hero" line. Grep the
message text, not the category.**

---

## 4. CONTROL FLOW INTO THE APPEND — exhaustive predecessor enumeration

Every internal branch target in the function and its predecessors (capstone, all 746 bytes):

```
label 0x55CD56F <- 0x55CD565:jne
label 0x55CD66A <- 0x55CD63F:je
label 0x55CD684 <- 0x55CD5F1:je
label 0x55CD6A0 <- 0x55CD682:jmp
label 0x55CD760 <- 0x55CD750:jbe            (internal to the append)
label 0x55CD76B <- 0x55CD79B:jb, 0x55CD7B0:jmp
label 0x55CD77B <- 0x55CD548:je, 0x55CD555:jne, 0x55CD7F1:je, 0x55CD7F8:jmp
label 0x55CD793 <- 0x55CD513:je
label 0x55CD794 <- 0x55CD5D1:je, 0x55CD5E1:je
label 0x55CD7B2 <- 0x55CD57A:je, 0x55CD58A:je
label 0x55CD7CE <- 0x55CD7B9:jb
```

**[M] The only branch landing inside `0x55CD738..0x55CD76B` is `0x55CD760`, which is the append's
own grow-skip.** => the append block is entered **only** by fallthrough from `0x55CD730`. There is
no path that reaches the append without first running all six success-path steps, and no path
past the round-game-mode guard that skips it.

Full exit map:

| exit | condition | side effects | log |
|---|---|---|---|
| `0x55CD793` bare `ret` | `PlayerState == null` | none | none |
| `0x55CD77B` | `PS` is Garbage | none | **none (silent)** |
| `0x55CD77B` | `HasEverContainedPlayer(this,PS)` | none | **none (silent)** <- the ordering trap |
| `0x55CD7B2` | round GM null **or** IsA fail | none | LokiRideableComponent.cpp:299, Error |
| `0x55CD794` | `GetLokiCharacter` null **or** IsA fail | none | LokiRideableComponent.cpp:327, Error |
| fallthrough | all guards pass | teleport, collision on/off, MoveStep, time stamp, **append** | none |

---

## 5. `ResizeGrow` (`0x0F988D0`) — why the ordering is mandatory

```
0x00F988D0  48895c2408    mov    [rsp+8],  rbx
0x00F988D5  4889742410    mov    [rsp+0x10], rsi
0x00F988DA  57            push   rdi
0x00F988DB  4883ec30      sub    rsp, 0x30
0x00F988DF  48635908      movsxd rbx, dword ptr [rcx+8]      ; <<< reads ArrayNum OUT OF THE STRUCT (already old+1)
0x00F988E3  8bf2          mov    esi, edx                    ; esi = PreviousNum (old)
0x00F988E5  488bf9        mov    rdi, rcx
0x00F988E8  3bda          cmp    ebx, edx
0x00F988EA  7c71          jl     0x0F9895D                   ; ArrayNum < PreviousNum -> call 0xFAAC80 ; int3   (HARD ABORT)
0x00F988EC  83790c00      cmp    dword ptr [rcx+0xc], 0      ; ArrayMax == 0 ?
0x00F988F0  b804000000    mov    eax, 4
0x00F988F5  7411          je     0x0F98908                   ;   yes -> NewMax = max(4, ArrayNum)
0x00F988F7  488d045b      lea    rax, [rbx+rbx*2]            ;   no  -> NewMax = ArrayNum + 16 + (3*ArrayNum)/8
0x00F988FB  48c1e803      shr    rax, 3
0x00F988FF  4883c010      add    rax, 0x10
0x00F98903  4803c3        add    rax, rbx
0x00F98906  eb07          jmp    0x0F9890F
0x00F98908  483bd8        cmp    rbx, rax
0x00F9890B  480f47c3      cmova  rax, rbx
0x00F9890F  488d0cc500000000  lea rcx, [rax*8]               ; bytes = NewMax * 8   <<< ELEMENT SIZE = 8
0x00F98917  ba08000000    mov    edx, 8                      ; alignment = 8
0x00F9891C  e89fef0600    call   0x0B078C0                   ; FMemory::QuantizeSize
0x00F98921  48c1e803      shr    rax, 3
0x00F98925  b9ffffff7f    mov    ecx, 0x7fffffff
0x00F9892A  3bd8          cmp    ebx, eax
0x00F9892C  c744242008..  mov    dword ptr [rsp+0x20], 8     ; stack arg: AlignmentOfElement = 8
0x00F98934  41b908000000  mov    r9d, 8                      ; NumBytesPerElement = 8
0x00F9893A  8bd6          mov    edx, esi                    ; PreviousNum
0x00F9893C  0f4fc1        cmovg  eax, ecx
0x00F9893F  488bcf        mov    rcx, rdi                    ; &Array
0x00F98942  448bc0        mov    r8d, eax                    ; NewMax
0x00F98945  89470c        mov    dword ptr [rdi+0xc], eax    ; ArrayMax = NewMax
0x00F98948  e863700100    call   0x0FAF9B0                   ; ResizeAllocation(PreviousNum, NewMax, 8, 8)
0x00F9894D..0x00F9895C   restore + ret
```

Three consequences for the arm, all **[M]**:

1. `ResizeGrow` sizes the allocation from **`ArrayNum` read out of the struct**, not from `edx`.
   `edx` is only `PreviousNum` (how many elements `ResizeAllocation` must copy). **The increment
   must already have happened.**
2. It **`int3`-aborts** when `ArrayNum < PreviousNum`. Passing a stale pair is fatal, not lossy.
3. **Element size is hard-coded 8, alignment 8** — an independent confirmation that
   `PlayersAttached` is a pointer array, matching the `qword [rax+rbx*8]` store.

It is a real function (149 B, `pdata 0x0F988D0..0x0F98965`), decrypted in all four graded images,
**not** any known fold.

---

## 6. THE ARRAY BASE IS `+0x130` — three independent confirmations

1. **Instruction operand (the request):**
   `0x055CD754  498d8e30010000  lea rcx, [r14 + 0x130]` — literally `&PlayersAttached` handed to
   `ResizeGrow`. And `0x055CD760  498b8630010000  mov rax, qword ptr [r14 + 0x130]` — the `Data`
   reload. Both use `r14`, which holds `this` (§2). **[M]**
2. **`ResizeGrow`'s internal offsets:** given `rcx = this+0x130`, it reads `[rcx+8]` as `ArrayNum`
   and `[rcx+0xC]` as `ArrayMax`. Those are exactly the `+0x138` / `+0x13C` the wall touches =>
   a self-consistent `TArray{void* Data @0; int32 Num @8; int32 Max @0xC}` at `this+0x130`. **[M]**
3. **UHT declaration order** (`binds_members.csv`, class 4540 `ULokiRideableComponent`):
   ```
   property 6  int                          PlayersInsideCount    (live @0x11C, S131)
   property 7  TArray<ALokiPlayerState*>    PlayersInside         (live @0x120, S131)
   property 8  TArray<ALokiPlayerState*>    PlayersAttached       -> next slot = 0x130
   ```
   `HasEverContainedPlayer` independently walks `[this+0x120]` / `[this+0x128]` = `PlayersInside`,
   which pins the neighbour. **[M]**

---

## 7. THE SUCCESS PATH IN ORDER, GRADED — and the append is LAST

| # | rva | call target | name | grade | source of the name |
|---|---|---|---|---|---|
| 0 | `0x55CD54E` | `0x55DCAA0` | `HasEverContainedPlayer` | **REAL** (decrypted, loop over `PlayersInside`) | `.data` record table |
| 0 | `0x55CD56A` | `0x35AFC40` | `UActorComponent::GetWorld` slow path | **REAL** | body shape [I] |
| — | `0x55CD572` | `0x0F7EB50` | *the stripped round-game-mode getter* | **FOLD** `33 c0 c3` | fold table |
| 0 | `0x55CD583` | `0x55C7DD0` | `IsA<ALokiRoundGameMode>` fast-tree | **REAL** | body shape [I] |
| — | `0x55CD5C6` | `0x56BE0D0` | `GetLokiCharacter` | **REAL** | `.data` record table |
| — | `0x55CD5DA` | `0x54F8DC0` | IsA fast-tree on the hero | **REAL** | body shape [I] |
| — | `0x55CD614` | `0x20B9EA0` | lazy-init getter on `RootComponent+0x1E8` | **REAL** | unidentified [S] |
| — | `0x55CD654` | `0x10A50C0` | rotator/quat math | **REAL** | unidentified [S] |
| **1** | `0x55CD703` | `0x56680F0` | **`ULokiGameplayStatics::LokiTeleportActor`** | **COVERAGE-BLOCKED body; NOT a known fold** | `.data` record table |
| **2** | `0x55CD70D` | `0x339A550` | **`SetActorEnableCollision(hero, TRUE)`** | **REAL** (54 B, pdata `0x339A550..0x339A586`) | `.data` record table |
| **3** | `0x55CD719` | `0x55C1B20` | **`ALokiCharacter::SpawnAndMoveLokiCharacter_MoveStep`** | **REAL** (120 B, pdata `..0x55C1B98`) | **its own error literal** (below) |
| **4** | `0x55CD723` | `0x339A550` | **`SetActorEnableCollision(hero, FALSE)`** | **REAL** | as above |
| **5** | `0x55CD72B` | `0x37D9D40` | **`GetServerTime`** | **REAL** (65 B, pdata `..0x37D9D81`) | `.data` record table |
| **6** | `0x55CD730` | — | `movss [hero+0x1C10], xmm0` — the time stamp | store | — |
| **7** | `0x55CD738` | `0x0F988D0` | **THE APPEND** (conditional `ResizeGrow`) | **REAL** | §5 |

**Answer to "does anything run before the append": ALL OF IT DOES. The append is the last thing
the function does before the epilogue.** [M] — by address ordering plus §4's predecessor
enumeration (`0x55CD738` is only reachable by fallthrough from `0x55CD730`).

**`0x55C1B20` naming is now [M], not inherited.** Its own bail prints the static record at
`.rdata 0x8B19038`:
```
fmt  = "ALokiCharacter::SpawnAndMoveLokiCharacter_MoveStep Null Character was given to move"
file = "C:\TheoryCraft\build-staging\Loki\Source\Loki\Character\LokiCharacter.cpp"
line = 5484   verbosity = 2 (Error)
```
That names the function verbatim, from a *different* instrument than the record table.
Signature from the call: `(ALokiCharacter* Character, const FVector* MoveToLocation)`, and it is
passed `[rbp+0x20]` = the **raw** `SpawnLocation` (not the +7500 version).

**`LokiTeleportActor`'s body cannot be graded from any dump on disk.** `0x5668000` is an all-zero
page in **all seven** images (`merged4`, `merged3`, `merged2`, `merged`, `tuthero`, `s129`,
`rideable`) — checked individually. **COVERAGE-BLOCKED, never ABSENT.** What *is* established: the
record table lists its `impl` as `0x56680F0`, which is not any of the five known fold constants, so
it is not one of the known stubs. Positive control for that same instrument in the same pass:
`AuthSetCurrentRideable` in the same class *does* list `impl = 0x0F7EC20` (FOLD ret0), so the table
would have shown a fold had there been one.

---

## 8. ITEM 6 — THE RAX LIVENESS RE-RUN. **I DISAGREE WITH THE STATED EVIDENCE AND AGREE WITH THE CONCLUSION.**

### 8.1 The claimed window, re-run verbatim (capstone `regs_access`, every instruction)

`0x55CD590 .. 0x55CD5CB` inclusive:

```
0x055CD590  movsd  xmm0, [rbx+0x10]
0x055CD595  mov    rcx, rdi
0x055CD598  addsd  xmm0, [rip+0x354ff28]
0x055CD5A0  movsd  xmm1, [rbx+0x10]
0x055CD5A5  mov    [rsp+0x170], rsi
0x055CD5AD  movaps [rsp+0x150], xmm6
0x055CD5B5  movups xmm6, [rbx]
0x055CD5B8  movsd  [rbp-0x28], xmm0
0x055CD5BD  movups [rbp+0x20], xmm6
0x055CD5C1  movsd  [rbp+0x30], xmm1
0x055CD5C6  call   0x56BE0D0                 WRITES-RAX (return value)
0x055CD5CB  mov    rsi, rax                  READS-RAX
-> 12 instructions.  first RAX READ = 0x55CD5CB.  first RAX WRITE = 0x55CD5C6.
```

**The literal claim is TRUE:** within `0x55CD590..0x55CD5CB` there are zero reads of RAX before the
`call` at `0x55CD5C6` redefines it.

### 8.2 ...but the window cannot support the conclusion it was cited for. **[M]**

Re-run over the **true fallthrough**, starting at the first instruction after the round-game-mode
null test:

```
0x055CD580  mov  rcx, rax          READS-RAX            <<< THE ROUND GAME MODE IS READ HERE
0x055CD583  call 0x55C7DD0         WRITES-RAX (retval)  <<< AND IS DEAD IMMEDIATELY AFTER
0x055CD588  test al, al            READS-RAX            (this is the IsA result, not the GM)
0x055CD58A  je   0x55CD7B2
0x055CD590  ... (as above)
-> first RAX READ = 0x55CD580.  first RAX WRITE = 0x55CD583.
```

Two problems with the window as stated:

* **It starts one instruction after the value's only consumer.** `0x55CD580 mov rcx, rax` reads
  the round-game-mode pointer and hands it to the `IsA` check.
* **By `0x55CD590` RAX no longer holds the round game mode at all** — the `call` at `0x55CD583`
  redefined it. The window is therefore measuring the liveness of the *`IsA` boolean*, not of the
  getter's return value. "Zero reads of RAX in `0x55CD590..`" is true of literally any value the
  getter could have returned, so it discriminates nothing.

### 8.3 The conclusion is nevertheless correct — here is evidence that does support it

Enumerate every instruction between the getter's return and the `IsA` call. There are exactly four:

```
0x055CD577  test rax, rax        (read, no copy)
0x055CD57A  je   0x55CD7B2       (no reg access)
0x055CD580  mov  rcx, rax        (the ONLY copy — into a VOLATILE register)
0x055CD583  call 0x55C7DD0       (consumes rcx; clobbers rcx and redefines rax)
```

There is **no store of RAX to memory, and no copy of RAX to any non-volatile register, anywhere in
the function** (RAX-family reads/writes enumerated over all 746 bytes). After `0x55CD583`: `rcx` is
caller-clobbered and is unconditionally rewritten at `0x55CD595 mov rcx, rdi`; `rax` is the `IsA`
boolean.

=> **[M] The round game mode's returned pointer has exactly ONE consumer — the
`IsA<ALokiRoundGameMode>` type check at `0x55CD583` — and is dead from that instruction onward. It
is a PRECONDITION, not a data dependency.** That agrees with the prior lane's conclusion, and it
matches the independent live finding that `Comp_GameMode_DropPlane_Tutorial+0xE0` holds a
`BP_LokiGameMode_Tutorial_C` that *passes* this very same helper `0x55C7DD0`.

**Method note for the register:** the previous lane's window is an instrument scoped one instruction
too late; the *result* survived only because a stronger argument happened to be available. A
liveness window whose start point sits after the redefinition it is meant to rule out is not a
measurement of the value in question. Grade the earlier statement's **evidence** as refuted, its
**conclusion** as confirmed by a different route.

---

## 9. THE CORRECTED, BYTE-EXACT RECIPE FOR THE MIRROR

```c
/* c   = ULokiRideableComponent*  (the pod's LokiRideable_GEN_VARIABLE)
   PS  = ALokiPlayerState*                                                */

int32_t old = *(int32_t*)((char*)c + 0x138);        /* movsxd — signed i32          */
*(int32_t*)((char*)c + 0x138) = old + 1;            /* INCREMENT FIRST (mandatory)  */

if ((uint32_t)(old + 1) > (uint32_t)*(int32_t*)((char*)c + 0x13C))   /* UNSIGNED     */
        ResizeGrow_0xF988D0(/*rcx*/ (char*)c + 0x130, /*edx*/ (uint32_t)old);

void** data = *(void***)((char*)c + 0x130);         /* RELOAD after the grow        */
data[(int64_t)old] = PS;                            /* qword [Data + old*8] = PS    */
```

Notes for the arm, all derived above:

* `ResizeGrow` is `void __fastcall(FScriptArray* /*rcx*/, int32 PreviousNum /*edx*/)`. It is a real
  function, **not** a `UFunction`, so the S55 native-call primitive does not apply — it must be a
  plain direct call from injected code.
* Because live RPM reads `PlayersAttached` as `Data=0 Num=0 Max=0`, the very first append **will**
  take the grow branch: `old=0`, `old+1=1 > Max=0`. So `ResizeGrow` is required, not optional.
  Under `Max == 0` it takes the `mov eax,4 / cmova` path -> `NewMax = max(4, 1) = 4` -> a 32-byte
  game-heap allocation. The buffer therefore belongs to the game's own allocator, which is exactly
  what makes a later `Empty()`/`RemoveAt()` on the detach path safe.
* **Do not touch `PlayersInside` (`+0x120`) first.** `HasEverContainedPlayer` searches it, and a hit
  turns the wall into a silent no-op at `0x55CD555` — destroying the `LokiRideableComponent.cpp:299`
  receipt. Confirmed at byte level in §3.1.
* Nothing about the append depends on the wall having run. It is a pure `TArray::Add` on a
  reflected `TArray<ALokiPlayerState*>`; the six preceding steps (teleport / collision / MoveStep /
  server-time stamp) are **not** performed by the mirror, so the hero's position and `hero+0x1C10`
  will be untouched. If `AuthPlayerDetachPlayerFromRidable` reads any of those, expect a partial
  dismount — consistent with the already-recorded §14.1 correction that the detach carries two
  `0xF7EC20` folds.

---

## 10. INSTRUMENT CAVEATS OBSERVED THIS LANE

* `fkdis.py lea <rva>` is a raw disp32 scan and **produces false positives**. Its hit at
  `0x23FE774` for `0xA036AC0` decodes to `add rbx, 7` — a coincidental byte match, not a reference.
  Treat every `lea` hit as a candidate to be disassembled, never as an xref.
* `fkdis.py callxref` and `findptr` cap at 200 rows. Neither cap was hit here
  (`callxref 0x55C1B20` returned 2 rows), so those counts are exact, not floors.
* `pdata_union.csv` has **no row** for `0x56680F0` *or* for `0x55DCAA0`. The latter is a genuine
  leaf (no stack frame, no calls on the searched path), so "no row" means "leaf or index gap",
  **not** "not a function". It is not usable as a REAL/EMPTY discriminator.
* All `.data` reads above (the zero vector at `0x99C87B8`, the two `FLogCategory` objects, the
  record table) were taken from `merged4`, whose merge is `.text`-only, so its `.data` is a single
  coherent snapshot rather than a splice. The `FLogCategory` `Verbosity` bytes read `5` (Verbose)
  because that snapshot was taken with the FK-11 `[Core.Log]` ini active — the `cmp ..., 2` gate
  would pass either way for an `Error`.
* Eyeball reading of call targets from the printed `0x7ff6...` VAs produced **five wrong RVAs**
  before I re-resolved every one with capstone (`0x55AFC40` vs the real `0x35AFC40`, etc.).
  Every RVA in this document came out of a machine.
