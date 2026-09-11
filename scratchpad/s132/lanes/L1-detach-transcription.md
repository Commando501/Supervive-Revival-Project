# S132 LANE 1 — full transcription of `ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable`

**All offline. Zero launches, zero injections, zero `.text` writes.**
Canonical image `dumps/merged4.dump.exe` (ImageBase `0x7FF6AF000000`, flat: file offset == RVA).
Every address in this document was computed by a machine (`python`/`capstone`), never by hand.

---

## 0. HEADLINE CLAIMS, WITH GRADES

| # | claim | grade |
|---|---|---|
| H1 | Extent is **`0x55CCCB0 .. 0x55CCE68` = 440 bytes / 104 instructions**, spanning **9 chained `.pdata` rows**, all rooted at the primary UNWIND_INFO `0x97FCAF0`. | **[M]** |
| H2 | The whole extent lies in **one page, `0x055CC000`, which is decrypted** (63 zero bytes total, longest zero run **4**). No coverage hole anywhere in the function. | **[M]** |
| H3 | **Exactly TWO calls to the `0xF7EC20` fold, at `0x55CCD5B` and `0x55CCE4E`, and ZERO calls to `0xF7EB50`.** Verified by an **uncapped** byte-level rel32 scan over the whole extent — the prior session's claim is CONFIRMED in both halves. | **[M]** |
| H4 | **Neither fold's return value is tested.** Fold #1 is followed by `mov r8d,1` (eax dead); fold #2 is followed by the epilogue of a `void` function. **No branch depends on either.** ⇒ the partiality of the dismount is *missing side effects*, not *skipped branches*. | **[M]** |
| H5 | ⚠ **`0xF7EC20` is `c2 00 00` = `ret imm16 0`, i.e. a VOID no-op — it does NOT zero `eax`.** The repo's shorthand "ret 0" reads as "returns zero" and that is wrong. Irrelevant here (H4) but it will bite a future grader. | **[M]** |
| H6 | **The "only real gate is PlayersAttached non-empty" claim is TOO WEAK — there are EIGHT gates and FOUR of them can abort the dismount.** In particular there is a **`GetLokiCharacter() != null`** gate and an **`IsA<ALokiHeroCharacter>`** gate; if either fails the function still does the array removal and fold #2 but performs **none** of the hero work (no teleport, no un-hide, no collision, no gravity). See §4. | **[M]** |
| H7 | **There is NO `bCanExit` test, NO `PlayersInside` test, NO `HasEverContainedPlayer` test, NO round-game-mode call, NO `IsA` check on the component, and NO authority/NetMode read anywhere in the body.** `bCanExit(+0x118)`, `PlayersInsideCount(+0x11C)`, `PlayersInside(+0x120/+0x128)`, `PlayersThatExited(+0x140)` and even `PlayersAttached.Max(+0x13C)` are **never touched**. | **[M]** |
| H8 | **EVERY bail is SILENT.** The body contains **no** call to the logger `0x106B650` and **no** FString-build/emit/free triad (`0xFAC920` / `0xF7EC20`-emit / `0xFF9310`). A null result localises only by RPM readout, never by a log line. | **[M]** |
| H9 | Signature is **`void ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable(ALokiPlayerState* PlayerState /*rdx*/, const AActor* LandingLocationActor /*r8*/)`**, `this` in rcx. Two params, 16-byte parms struct (`PlayerState@0x0`, `LandingLocationActor@0x8`). | **[M]** |
| H10 | **`LandingLocationActor == nullptr` is a SUPPORTED input**: at `0x55CCCE5` a null third argument is replaced by **`this->GetOwner()`** (`UActorComponent::OwnerPrivate @ +0xB8`). For a pod's own rideable component that IS the pod — i.e. **passing `nullptr` reproduces what the game itself passes** in the normal (leader-pod) case. | **[M]** |
| H11 | The function has **exactly one game caller**: `ALokiDropPod::KickPlayersFromPod` (Angelscript, AOT body at `.text 0x596A190`). Its whole body is behind `if (LokiIsClient) return;` and `LokiIsClient` is hardcoded TRUE on this client ⇒ **the game can never call this itself**, so every observable is at baseline 0. | **[M]** |
| H12 | The function writes **eight** distinct pieces of state (§6). The **primary receipt is a hero TELEPORT** (`SetActorLocation` to `GetLandingTeleportLocation(...)`, which is REAL, 963 B, 0 folds, fully decrypted). The **cleanest binary receipt is `ULokiPlayerDropPlaneComponent::bDropComplete @ +0xD0` going 0 → 1.** | **[M]** |
| H13 | ⚠⚠ **CRASH HAZARD, not previously recorded: `0x5586530` (the vision-granter refresh, called unconditionally on the hero) dereferences `hero+0x460`, `hero+0x1978` and `hero+0x1980` with NO null checks.** If `PracticallyTouchingVisionGranter` or `PeripheralVisionGranter` is null on the staged tutorial hero, the arm faults. **Read all three with RPM before arming.** | **[M]** |
| H14 | ⚠ `FUNC_BlueprintAuthorityOnly` **is set** (`flags 0x04020405`). The **exec thunk `0x5456100` contains no authority check at all** — it is a plain `P_GET_OBJECT ×2; P_FINISH; call impl`. And the **impl `0x55CCCB0` is a plain 3-arg `__fastcall`**, so the arm may call it *directly* with no FFrame, no ProcessEvent and no marshaller — which sidesteps the standing **E0c marshaller-control gap** entirely. | **[M]** |
| H15 | The `TArray::Remove` helper `0x11F3860` writes **only `Num`**. It does **not** touch `Data` or `Max`, does **not** free, does **not** realloc, and with `Num==1` + a match it does not even call `memmove`. ⇒ a poked `PlayersAttached` buffer is **not** freed by this function. | **[M]** |

---

## 1. VERIFIED EXTENT AND COVERAGE

### 1.1 `.pdata` rows (from `tools/strxref/index/pdata_union.csv`)

The dumps' own `.pdata` section is zeroed, so the union index is the instrument. Nine consecutive rows:

```
begin      end        size  unwind      seen_in_dumps
0x55CCCB0  0x55CCCDB    43  0x97FCAF0   39     <-- PRIMARY (flags=0x0)
0x55CCCDB  0x55CCD07    44  0x97FCAFC   39
0x55CCD07  0x55CCD2D    38  0x97FCB10   39
0x55CCD2D  0x55CCD56    41  0x97FCB24   39
0x55CCD56  0x55CCE1C   198  0x97FCB38   39
0x55CCE1C  0x55CCE49    45  0x97FCB4C   39
0x55CCE49  0x55CCE5B    18  0x97FCB5C   39
0x55CCE5B  0x55CCE60     5  0x97FCB6C   39
0x55CCE60  0x55CCE68     8  0x97FCB7C   39
                       ---
                       440
```

### 1.2 Chain verified from the UNWIND_INFO structures themselves — not assumed [M]

Decoding `UNWIND_INFO{ Version:3|Flags:5, SizeOfProlog, CountOfCodes, Frame }` plus the trailing
`RUNTIME_FUNCTION` when `UNW_FLAG_CHAININFO (0x4)` is set (codes occupy `((Count+1)&~1)*2` bytes):

```
0x55CCCB0-0x55CCCDB u=0x97FCAF0 flags=0x0 prolog=21 ncodes=3   PRIMARY
0x55CCCDB-0x55CCD07 u=0x97FCAFC flags=0x4 CHAIN-> 0x55CCCB0-0x55CCCDB u=0x97FCAF0
0x55CCD07-0x55CCD2D u=0x97FCB10 flags=0x4 CHAIN-> 0x55CCCDB-0x55CCD07 u=0x97FCAFC
0x55CCD2D-0x55CCD56 u=0x97FCB24 flags=0x4 CHAIN-> 0x55CCD07-0x55CCD2D u=0x97FCB10
0x55CCD56-0x55CCE1C u=0x97FCB38 flags=0x4 CHAIN-> 0x55CCD2D-0x55CCD56 u=0x97FCB24
0x55CCE1C-0x55CCE49 u=0x97FCB4C flags=0x4 CHAIN-> 0x55CCD2D-0x55CCD56 u=0x97FCB24
0x55CCE49-0x55CCE5B u=0x97FCB5C flags=0x4 CHAIN-> 0x55CCD07-0x55CCD2D u=0x97FCB10
0x55CCE5B-0x55CCE60 u=0x97FCB6C flags=0x4 CHAIN-> 0x55CCCDB-0x55CCD07 u=0x97FCAFC
0x55CCE60-0x55CCE68 u=0x97FCB7C flags=0x4 CHAIN-> 0x55CCCB0-0x55CCCDB u=0x97FCAF0
```

**Boundary controls (both directions):**
* the row **before** (`0x55CCC66-0x55CCC74`) chains to `0x55CCB80` — a *different* function, so the
  chain does not extend backwards;
* the row **after** (`0x55CCE70-0x55CCEFA`, `flags=0x3`) is a **PRIMARY** — it is
  `AuthPlayerEnterWorld` — so the chain does not extend forwards;
* `0x55CCE68..0x55CCE70` (8 bytes, `ba 01 00 00 00 57 57 57`) is inter-function padding, outside the extent.

### 1.3 Coverage — the whole function is in ONE decrypted page

```
$ python scratchpad/fk27/fkdis.py cov 0x55CCCB0 440 --dump merged4
  page 0x055CC000  present
```
`0x55CCCB0 .. 0x55CCE68` sits entirely inside `[0x055CC000, 0x055CD000)`. **No page in the extent is
zero.** Byte census over the 440 bytes: **63 zero bytes, longest zero run 4** — normal
displacement/immediate padding inside real instructions, not a decryption hole. The linear sweep
decodes cleanly end-to-end with no data-in-code and terminates on a `ret` at `0x55CCE67`.

Cross-instrument confirmation: `scratchpad/s131/lane-d-empty-impl-census.tsv:11084` independently
records this function as `REAL 0x55cccb0`, fold multiplicity **1**, with first bytes
`4885d20f84ae01000048895424105541` — byte-identical to my disassembly's first 16 bytes.

---

## 2. COMPLETE ANNOTATED DISASSEMBLY (all 104 instructions)

Produced by `scratchpad/s132/lanes/_gen_listing.py` (capstone), also saved verbatim to
`scratchpad/s132/lanes/_listing.txt`. **Validated: 104 annotation keys, 104 instructions, 0 keys off
an instruction boundary, 0 unannotated instructions** — so no annotation was silently dropped.

```
0x55CCCB0  48 85 d2                           test     rdx, rdx                           ; GATE 1a: PlayerState (arg2) != nullptr?
0x55CCCB3  0f 84 ae 01 00 00                  je       0x55cce67                          ;   -> SILENT return (no prologue executed at all)
0x55CCCB9  48 89 54 24 10                     mov      qword ptr [rsp + 0x10], rdx        ; home-slot spill: [entry_rsp+0x10] = PlayerState  (== [rsp+0x88] after prologue)
0x55CCCBE  55                                 push     rbp                                ; prologue
0x55CCCBF  41 57                              push     r15                                ; prologue
0x55CCCC1  48 83 ec 68                        sub      rsp, 0x68                          ; prologue: frame = 0x78 total (2 pushes + 0x68)
0x55CCCC5  8b 42 0c                           mov      eax, dword ptr [rdx + 0xc]         ; eax = PlayerState->ObjectFlags   (UObject::ObjectFlags @ +0x0C in this build)
0x55CCCC8  4d 8b f8                           mov      r15, r8                            ; r15 = LandingLocationActor (arg3)
0x55CCCCB  c1 e8 1e                           shr      eax, 0x1e                          ; isolate bits 30..31
0x55CCCCE  48 8b e9                           mov      rbp, rcx                           ; rbp = this  (ULokiRideableComponent*)
0x55CCCD1  f6 d0                              not      al
0x55CCCD3  a8 01                              test     al, 1                              ; GATE 1b: RF_MirroredGarbage (bit 30) must be CLEAR  ==  ::IsValid(PlayerState)
0x55CCCD5  0f 84 85 01 00 00                  je       0x55cce60                          ;   -> SILENT return
0x55CCCDB  48 89 74 24 60                     mov      qword ptr [rsp + 0x60], rsi        ; spill rsi (never actually used in the body - dead save/restore pair)
0x55CCCE0  4d 85 c0                           test     r8, r8                             ; is LandingLocationActor null?
0x55CCCE3  75 07                              jne      0x55cccec                          ;   no -> keep it
0x55CCCE5  4c 8b b9 b8 00 00 00               mov      r15, qword ptr [rcx + 0xb8]        ;   yes -> r15 = this->GetOwner()   [UActorComponent::OwnerPrivate @ +0xB8, proven by UActorComponent::GetOwner impl 0x3215D20]
0x55CCCEC  48 8b 89 30 01 00 00               mov      rcx, qword ptr [rcx + 0x130]       ; rcx = this->PlayersAttached.Data   (+0x130)
0x55CCCF3  48 63 85 38 01 00 00               movsxd   rax, dword ptr [rbp + 0x138]       ; rax = this->PlayersAttached.Num    (+0x138)
0x55CCCFA  48 8d 14 c1                        lea      rdx, [rcx + rax*8]                 ; rdx = Data + Num*8  (one-past-end)
0x55CCCFE  48 3b ca                           cmp      rcx, rdx                           ; GATE 2: PlayersAttached must be NON-EMPTY
0x55CCD01  0f 84 54 01 00 00                  je       0x55cce5b                          ;   -> SILENT return   *** THIS IS THE GATE THE ARM MUST DEFEAT ***
0x55CCD07  48 89 9c 24 80 00 00 00            mov      qword ptr [rsp + 0x80], rbx        ; spill rbx
0x55CCD0F  48 8b 9c 24 88 00 00 00            mov      rbx, qword ptr [rsp + 0x88]        ; rbx = PlayerState (reload from its home slot)
0x55CCD17  48 39 19                           cmp      qword ptr [rcx], rbx               ; linear search: *it == PlayerState ?
0x55CCD1A  74 0e                              je       0x55ccd2a                          ;   found
0x55CCD1C  48 83 c1 08                        add      rcx, 8                             ; ++it
0x55CCD20  48 3b ca                           cmp      rcx, rdx
0x55CCD23  75 f2                              jne      0x55ccd17                          ; loop
0x55CCD25  e9 29 01 00 00                     jmp      0x55cce53                          ; GATE 3: NOT FOUND -> jump to epilogue.  SILENT.  No Remove, no fold#2, nothing.
0x55CCD2A  48 8b cb                           mov      rcx, rbx                           ; rcx = PlayerState
0x55CCD2D  48 89 7c 24 58                     mov      qword ptr [rsp + 0x58], rdi        ; spill rdi
0x55CCD32  e8 99 13 0f 00                     call     0x56be0d0                          ; rax = ALokiPlayerState::GetLokiCharacter()      [record: thunk 0x54373A0 -> impl 0x56BE0D0]
0x55CCD37  48 8b f8                           mov      rdi, rax                           ; rdi = the character
0x55CCD3A  48 85 c0                           test     rax, rax                           ; GATE 4: character must be non-null
0x55CCD3D  0f 84 e0 00 00 00                  je       0x55cce23                          ;   -> skip ALL hero work, but still Remove + fold#2
0x55CCD43  48 8b c8                           mov      rcx, rax
0x55CCD46  e8 75 c0 f2 ff                     call     0x54f8dc0                          ; al = IsA<ALokiHeroCharacter>(character)   [0x54F8DC0 = inlined FStructBaseChain::IsDerivedFrom against LokiHeroCharacter::GetPrivateStaticClass 0x5395720]
0x55CCD4B  84 c0                              test     al, al
0x55CCD4D  0f 84 d0 00 00 00                  je       0x55cce23                          ; GATE 5: must be an ALokiHeroCharacter -> else skip ALL hero work (still Remove + fold#2)
0x55CCD53  48 8b cf                           mov      rcx, rdi                           ; rcx = hero
0x55CCD56  4c 89 74 24 50                     mov      qword ptr [rsp + 0x50], r14        ; spill r14
0x55CCD5B  e8 c0 1e 9b fb                     call     0xf7ec20                           ; ### FOLD #1 ###  hero->UNNAMED()  -- STRIPPED (0xF7EC20 = `ret 0`, i.e. a void no-op). 1 arg (this). Return value NOT tested.
0x55CCD60  41 b8 01 00 00 00                  mov      r8d, 1                             ; r8d = 1  (EFindName::FNAME_Add)
0x55CCD66  48 8d 15 83 e8 54 03               lea      rdx, [rip + 0x354e883]             ; rdx = ANSI literal "MinionIgnore" @ .rdata 0x8B1B5F0
0x55CCD6D  48 8d 8c 24 98 00 00 00            lea      rcx, [rsp + 0x98]                  ; rcx = &local FName (reuses the r9 home slot at [rsp+0x98])
0x55CCD75  e8 56 c0 b6 fb                     call     0x1138dd0                          ; FName::FName(&tmp, "MinionIgnore", FNAME_Add)   [0x1138DD0, ANSICHAR overload]
0x55CCD7A  48 8d 8f f0 01 00 00               lea      rcx, [rdi + 0x1f0]                 ; rcx = &hero->Tags   (AActor::Tags @ +0x1F0, TArray<FName>)
0x55CCD81  48 8d 94 24 98 00 00 00            lea      rdx, [rsp + 0x98]                  ; rdx = &tmp FName
0x55CCD89  e8 82 2b b3 fb                     call     0x10ff910                          ; ### WRITE ###  hero->Tags.Remove(FName("MinionIgnore"))   [0x10FF910 = TArray<FName>::Remove run-compaction; writes Tags.Num]
0x55CCD8E  b2 01                              mov      dl, 1                              ; dl = true
0x55CCD90  48 8b cf                           mov      rcx, rdi                           ; rcx = hero
0x55CCD93  e8 b8 d7 dc fd                     call     0x339a550                          ; ### WRITE ###  hero->SetActorEnableCollision(true)   [AActor, impl 0x339A550]
0x55CCD98  33 d2                              xor      edx, edx                           ; edx = false
0x55CCD9A  48 8b cf                           mov      rcx, rdi                           ; rcx = hero
0x55CCD9D  e8 9e c2 fc ff                     call     0x5599040                          ; ### WRITE ###  hero->SetPredropHidden(false)  [ALokiHeroCharacter, impl 0x5599040; writes byte hero+0x1BE8 then refreshes visibility; EARLY-OUTS if already false]
0x55CCDA2  48 8b cf                           mov      rcx, rdi                           ; rcx = hero
0x55CCDA5  e8 86 97 fb ff                     call     0x5586530                          ; ### WRITE ###  hero->UNNAMED_UpdateVisionGranters()  [0x5586530]:  PracticallyTouchingVisionGranter(+0x1978)->ViewDistance(+0xE8) = GetScaledCapsuleRadius() + PracticallyTouchingVisionRadiusOffset(+0x196C);  PeripheralVisionGranter(+0x1980)->ViewDistance = PeripheralVisionRadius(+0x1970);  then tail-jmp [hero_vtable+0xC68]
0x55CCDAA  48 8b cf                           mov      rcx, rdi                           ; rcx = hero
0x55CCDAD  e8 2e fb fd ff                     call     0x55ac8e0                          ; rax = hero->GetLokiCharacterMovement()   [ALokiCharacter, impl 0x55AC8E0]
0x55CCDB2  4c 8b f0                           mov      r14, rax                           ; r14 = movement component
0x55CCDB5  48 85 c0                           test     rax, rax
0x55CCDB8  74 1a                              je       0x55ccdd4                          ; GATE 6: movement component non-null -> else skip the next two writes
0x55CCDBA  4c 8b 00                           mov      r8, qword ptr [rax]                ; r8 = mc->vtable
0x55CCDBD  b2 01                              mov      dl, 1                              ; dl = true
0x55CCDBF  48 8b c8                           mov      rcx, rax                           ; rcx = mc
0x55CCDC2  41 ff 90 e0 03 00 00               call     qword ptr [r8 + 0x3e0]             ; ### WRITE ###  mc->SetComponentTickEnabled(true)   [vtable disp 0x3E0; identified from UActorComponent::SetComponentTickEnabled whose registered impl 0x3599B24 IS `mov rax,[rcx]; jmp [rax+0x3E0]`. 3-way ICF fold - the other two are ULokiAttributeSet::OnRep_Glide and UCheatManager::DumpOnlineSessionState, neither of which a movement component IS-A]
0x55CCDC9  41 c7 86 a0 01 00 00 00 00 80 3f   mov      dword ptr [r14 + 0x1a0], 0x3f800000 ; ### WRITE ###  mc->GravityScale = 1.0f   [UCharacterMovementComponent::GravityScale @ +0x1A0]
0x55CCDD4  4d 8b cf                           mov      r9, r15                            ; r9 = LandingLocationActor
0x55CCDD7  48 8d 54 24 30                     lea      rdx, [rsp + 0x30]                  ; rdx = &out FVector (hidden return pointer, [rsp+0x30])
0x55CCDDC  4c 8b c7                           mov      r8, rdi                            ; r8 = hero
0x55CCDDF  48 8b cd                           mov      rcx, rbp                           ; rcx = this
0x55CCDE2  e8 09 bc 00 00                     call     0x55d89f0                          ; loc = this->GetLandingTeleportLocation(hero, LandingLocationActor)  [ULokiRideableComponent, impl 0x55D89F0, 963 B chained, 0 folds, fully decrypted]
0x55CCDE7  45 33 c9                           xor      r9d, r9d                           ; r9 = OutSweepHitResult = nullptr
0x55CCDEA  c6 44 24 20 00                     mov      byte ptr [rsp + 0x20], 0           ; [rsp+0x20] = Teleport = ETeleportType::None
0x55CCDEF  45 33 c0                           xor      r8d, r8d                           ; r8b = bSweep = false
0x55CCDF2  48 8d 54 24 30                     lea      rdx, [rsp + 0x30]                  ; rdx = &loc
0x55CCDF7  48 8b cf                           mov      rcx, rdi                           ; rcx = hero
0x55CCDFA  e8 a1 d9 dc fd                     call     0x339a7a0                          ; ### WRITE ###  hero->SetActorLocation(loc, bSweep=false, nullptr, ETeleportType::None)   [AActor, 0x339A7A0; moves RootComponent (+0x1B0) by delta from ComponentToWorld.Translation (+0x220)]
0x55CCDFF  48 8b d3                           mov      rdx, rbx                           ; rdx = PlayerState
0x55CCE02  48 8b cd                           mov      rcx, rbp                           ; rcx = this
0x55CCE05  e8 b6 69 e8 ff                     call     0x54537c0                          ; ### RPC ###  this->MulticastOnPlayerEnteredWorld(PlayerState)  [ULokiRideableComponent, impl 0x54537C0 = the UHT RPC-send stub: FindFunction + ProcessEvent via vtable+0x270]
0x55CCE0A  48 8b cb                           mov      rcx, rbx                           ; rcx = PlayerState
0x55CCE0D  e8 6e a0 ff ff                     call     0x55c6e80                          ; rax = PlayerState->GetComponentByClass(ULokiPlayerDropPlaneComponent::StaticClass())  [0x55C6E80; virtual [PS_vtable+0x760]; class accessor 0x5429740]
0x55CCE12  4c 8b 74 24 50                     mov      r14, qword ptr [rsp + 0x50]        ; restore r14
0x55CCE17  48 85 c0                           test     rax, rax                           ; GATE 7: component found?
0x55CCE1A  74 07                              je       0x55cce23                          ;   -> skip
0x55CCE1C  c6 80 d0 00 00 00 01               mov      byte ptr [rax + 0xd0], 1           ; ### WRITE ###  dropPlaneComp->bDropComplete = true   [ULokiPlayerDropPlaneComponent, property index 0, @ +0xD0]
0x55CCE23  48 8d 94 24 88 00 00 00            lea      rdx, [rsp + 0x88]                  ; rdx = &PlayerState (its home slot, read-only to the callee)
0x55CCE2B  48 8d 8d 30 01 00 00               lea      rcx, [rbp + 0x130]                 ; rcx = &this->PlayersAttached  (+0x130)
0x55CCE32  e8 29 6a c2 fb                     call     0x11f3860                          ; ### WRITE ###  this->PlayersAttached.Remove(PlayerState)  [0x11F3860 = TArray<T*>::Remove run-compaction. Writes ONLY Num (+0x138). Does NOT touch Data(+0x130) or Max(+0x13C); does NOT free or realloc; with Num==1 and a match it does not even call memmove]
0x55CCE37  48 8b 8c 24 88 00 00 00            mov      rcx, qword ptr [rsp + 0x88]        ; rcx = PlayerState
0x55CCE3F  48 8b 7c 24 58                     mov      rdi, qword ptr [rsp + 0x58]        ; restore rdi
0x55CCE44  48 85 c9                           test     rcx, rcx                           ; GATE 8: PlayerState non-null (redundant re-check)
0x55CCE47  74 0a                              je       0x55cce53                          ;   -> skip fold #2
0x55CCE49  45 33 c0                           xor      r8d, r8d                           ; r8 = nullptr
0x55CCE4C  b2 03                              mov      dl, 3                              ; dl = 3
0x55CCE4E  e8 cd 1d 9b fb                     call     0xf7ec20                           ; ### FOLD #2 ###  PlayerState->UNNAMED(3, nullptr)  -- STRIPPED (0xF7EC20 = `ret 0`). Return value NOT tested (function is void).  [I] most likely Auth*BattleRoyalePlayerPhase(EBattleRoyalePlayerPhase::Combat==3, nullptr) - see report S7
0x55CCE53  48 8b 9c 24 80 00 00 00            mov      rbx, qword ptr [rsp + 0x80]        ; epilogue (restore rbx) - GATE 3 lands here
0x55CCE5B  48 8b 74 24 60                     mov      rsi, qword ptr [rsp + 0x60]        ; epilogue (restore rsi) - GATE 2 lands here
0x55CCE60  48 83 c4 68                        add      rsp, 0x68                          ; epilogue - GATE 1b lands here
0x55CCE64  41 5f                              pop      r15
0x55CCE66  5d                                 pop      rbp
0x55CCE67  c3                                 ret                                         ; return - GATE 1a lands here

; 104 instructions, 0x55CCCB0..0x55CCE68 (440 bytes)
```

---

## 3. COMPLETE CALL TABLE

### 3.1 Method

Two independent passes, both over the exact extent `0x55CCCB0..0x55CCE68`:
1. capstone decode, collecting every `call`/`jmp`;
2. an **UNCAPPED raw byte scan** of every offset for `E8`/`E9` with a machine-computed rel32 target,
   cross-checked against instruction boundaries.

The raw scan found **16 candidate `E8`/`E9` bytes**; 15 are instruction-aligned (14 `call` + 1 `jmp`)
and exactly **one** (`0x55CCCD0`) is an operand byte, correctly rejected. There is additionally **one
indirect call**. Nothing is capped; these are counts, not floors.

### 3.2 The table

| site | target | first bytes of target | grade | identity |
|---|---|---|---|---|
| `0x55CCD32` | `0x56BE0D0` | `40 53 48 83 ec 20 48 8b` | **REAL** | `ALokiPlayerState::GetLokiCharacter` (record: thunk `0x54373A0` → impl `0x56BE0D0`). Body: `rbx=[PS+0x430]; if(!rbx) return 0; return IsA<ALokiCharacter>(rbx)?rbx:0` |
| `0x55CCD46` | `0x54F8DC0` | `48 89 5c 24 08 48 89 74` | **REAL** | inlined `IsA<ALokiHeroCharacter>` — `FStructBaseChain::IsDerivedFrom` against `LokiHeroCharacter::GetPrivateStaticClass` (`0x5395720`; class-name wide string `LokiHeroCharacter` @ `0x899A832`) |
| **`0x55CCD5B`** | **`0x00F7EC20`** | **`c2 00 00`** | **FOLD** | stripped void stub (`ret 0`). 165,789 call sites ⇒ **non-identifying**. See §7. |
| `0x55CCD75` | `0x1138DD0` | `48 89 5c 24 08 57 48 83` | **REAL** | `FName::FName(FName* out, const ANSICHAR* name, EFindName)` — scans a **single-byte** NUL-terminated string (`cmp byte [rdx+r9],0`) |
| `0x55CCD89` | `0x10FF910` | `40 57 41 54 41 55 48 83` | **REAL** | `TArray<FName>::Remove(const FName&)` — run-compaction + `memmove(0x752A65E)`, writes `Num` at `[array+8]`, returns removed count |
| `0x55CCD93` | `0x339A550` | `4c 8b dc 55 48 81 ec 10` | **REAL** | `AActor::SetActorEnableCollision(bool)` (record thunk `0x33AC820`; corroborated by `docs/fk6-cheat-impl-census.csv:300` — 484 B, REAL) |
| `0x55CCD9D` | `0x5599040` | `40 53 48 83 ec 20 48 8b` | **REAL** | `ALokiHeroCharacter::SetPredropHidden(bool)` (thunk `0x539E670`; also `lane-d-empty-impl-census.tsv:1933` REAL) |
| `0x55CCDA5` | `0x5586530` | `48 83 ec 48 48 8b 81 60` | **REAL** | *unnamed, not reflected* — vision-granter refresh, see §6 W4 |
| `0x55CCDAD` | `0x55AC8E0` | `40 53 48 83 ec 20 48 8b` | **REAL** | `ALokiCharacter::GetLokiCharacterMovement` (thunk `0x5300710`; `lane-d-empty-impl-census.tsv:1453` REAL) |
| `0x55CCDC2` | **indirect** `[r8+0x3E0]` | — | **REAL (virtual)** | `UActorComponent::SetComponentTickEnabled(bool)` — see §3.3 |
| `0x55CCDE2` | `0x55D89F0` | `40 55 53 56 57 41 57 48` | **REAL** | `ULokiRideableComponent::GetLandingTeleportLocation` (thunk `0x5456C80`). **963 B over 6 chained rows `0x55D89F0..0x55D8DB3`, all pages decrypted, ZERO fold calls.** Calls a terrain service (`GetInstance`/`GetHeight`/`IsAbyss`) and world traces. |
| `0x55CCDFA` | `0x339A7A0` | `40 53 48 81 ec 70 01 00` | **REAL** | `AActor::SetActorLocation(const FVector&, bool bSweep, FHitResult*, ETeleportType)` — reads `RootComponent(+0x1B0)` and `ComponentToWorld.Translation(+0x220)`, converts absolute → delta, moves the root |
| `0x55CCE05` | `0x54537C0` | `48 89 5c 24 10 57 48 83` | **REAL** | `ULokiRideableComponent::MulticastOnPlayerEnteredWorld(ALokiPlayerState*)` — the UHT RPC-send stub (`FindFunction` `0x1344150` on cached `.data 0xA02A9F8`, then `ProcessEvent` via `[vtable+0x270]`) |
| `0x55CCE0D` | `0x55C6E80` | `48 89 5c 24 10 57 48 83` | **REAL** | `AActor::GetComponentByClass(ULokiPlayerDropPlaneComponent::StaticClass())` — virtual `[PS_vtable+0x760]`; class accessor `0x5429740`, name string `LokiPlayerDropPlaneComponent` @ `0x8A1C2AA` |
| `0x55CCE32` | `0x11F3860` | `48 89 54 24 10 48 89 4c` | **REAL** | `TArray<T*>::Remove(const T&)` — same algorithm as `0x10FF910` at 8-byte stride; **writes only `Num`** |
| **`0x55CCE4E`** | **`0x00F7EC20`** | **`c2 00 00`** | **FOLD** | stripped void stub. See §7. |

**`0x55CCD25` is the only intra-function `E9`** — `jmp 0x55CCE53`, the "not found in `PlayersAttached`" bail.

**Fold tally, uncapped and machine-counted: `0xF7EC20` → 2 · `0xF7EB50` → 0 · `0xF7EB60` → 0 ·
`0xB9E1F0` → 0 · `0xFC6CF0` → 0.** Both halves of the prior session's claim reproduce exactly.

**Negative control for the "no `0xF7EB50`" half:** the immediately following function
`AuthPlayerEnterWorld` (`0x55CCE70`) **does** contain one, at `0x55CCF22` (`call 0x00F7EB50`, the
stripped round-game-mode getter). Same instrument, same image, same page — so a zero here is a real
zero, not a scanner that cannot see them.

### 3.3 The indirect call, resolved [M]

```
0x55CCDBA  4c 8b 00                    mov  r8, [rax]         ; r8 = movementcomp->vtable
0x55CCDBD  b2 01                       mov  dl, 1
0x55CCDBF  48 8b c8                    mov  rcx, rax
0x55CCDC2  41 ff 90 e0 03 00 00        call qword ptr [r8 + 0x3e0]
```
`UActorComponent::SetComponentTickEnabled`'s **registered impl is `0x3599B24`, and the bytes at
`0x3599B24` are `48 8b 01 ff a0 e0 03 00 00` = `mov rax,[rcx]; jmp qword ptr [rax+0x3E0]`** — UHT
registered a virtual-dispatch thunk, which pins the displacement.

⚠ **`0x3599B24` is a 3-way ICF fold** — the same bytes also serve `ULokiAttributeSet::OnRep_Glide`
(thunk `0x52B5C40`) and `UCheatManager::DumpOnlineSessionState` (thunk `0x35C7600`). It is
disambiguated by the receiver's class: the receiver is the return of
`ALokiCharacter::GetLokiCharacterMovement`, which **is-a `UActorComponent`** and is **not** a
`ULokiAttributeSet` (whose `Glide` property lives at `+0x330`) nor a `UCheatManager`.
⇒ **`[vtable+0x3E0]` = `SetComponentTickEnabled(bool)`, called with `true`.**

---

## 4. EVERY GATE / EARLY-OUT, IN ORDER

**All eight are silent** (H8). "Aborts the dismount" = the hero work does not happen.

| # | site | exact test | passes when | on failure | silent? |
|---|---|---|---|---|---|
| **1a** | `0x55CCCB0` `test rdx,rdx` / `je 0x55CCE67` | `PlayerState != nullptr` | arg2 non-null | `ret` **before the prologue even runs** | SILENT |
| **1b** | `0x55CCCC5..0x55CCCD5` `mov eax,[rdx+0xC]; shr eax,30; not al; test al,1; je 0x55CCE60` | bit 30 of `UObject::ObjectFlags` (**`RF_MirroredGarbage`**) is CLEAR — the inlined `::IsValid(PlayerState)` | PlayerState not garbage / pending-kill | `ret` | SILENT |
| **—** | `0x55CCCE0` `test r8,r8` / `jne` | *not a gate*: `LandingLocationActor == nullptr` → substitute `this->GetOwner()` (`+0xB8`) | always | n/a | n/a |
| **2** | `0x55CCCEC..0x55CCD01` `rcx=[this+0x130]; rax=[this+0x138]; rdx=rcx+rax*8; cmp rcx,rdx; je 0x55CCE5B` | **`PlayersAttached.Num != 0`** | the array is non-empty | `ret` | SILENT |
| **3** | `0x55CCD17..0x55CCD25` linear scan `cmp [it], PlayerState` … `jmp 0x55CCE53` | **`PlayersAttached` CONTAINS the exact pointer** (pointer identity, not `IsA`) | the element is present | `ret`, **skipping the Remove and fold #2 as well** | SILENT |
| **4** | `0x55CCD3A` `test rax,rax` / `je 0x55CCE23` | `PlayerState->GetLokiCharacter() != nullptr` (reads `[PS+0x430]`, then `IsA<ALokiCharacter>`) | the PS owns a live LokiCharacter | jumps **past all hero work** to the array Remove | SILENT |
| **5** | `0x55CCD4B..0x55CCD4D` `test al,al` / `je 0x55CCE23` | **`IsA<ALokiHeroCharacter>(character)`** | the pawn is a hero | jumps **past all hero work** to the array Remove | SILENT |
| **6** | `0x55CCDB5..0x55CCDB8` `test rax,rax` / `je 0x55CCDD4` | `GetLokiCharacterMovement() != nullptr` | movement comp exists | skips `SetComponentTickEnabled(true)` and `GravityScale=1.0f` only | SILENT |
| **7** | `0x55CCE17..0x55CCE1A` `test rax,rax` / `je 0x55CCE23` | the PlayerState HAS a `ULokiPlayerDropPlaneComponent` | component found | skips `bDropComplete = true` only | SILENT |
| **8** | `0x55CCE44..0x55CCE47` `test rcx,rcx` / `je 0x55CCE53` | `PlayerState != nullptr` (redundant re-read of the home slot) | always, given 1a | skips fold #2 | SILENT |

### 4.1 Verdict on the key claim

> *"its only real gate is that `PlayersAttached` (+0x130 Data / +0x138 Num / +0x13C Max) be non-empty"*

**PARTIALLY TRUE, and dangerously incomplete.**

* ✅ **`+0x13C Max` is never read** — only `Data(+0x130)` and `Num(+0x138)`.
* ✅ Non-emptiness is indeed the gate that decides whether the function does *anything at all*.
* ❌ **Non-emptiness is not sufficient** — gate 3 additionally requires the array to contain the
  **exact pointer** you pass.
* ❌ **Two further gates (4 and 5) can silently reduce the call to "remove one array element and call a
  stripped stub."** They are what would make a flown arm read as "nothing happened" even though the
  array moved. Both are pre-readable by RPM before arming (§8.1).
* ✅ Confirmed absent, exhaustively over all 104 instructions: **no `bCanExit`(+0x118) read, no
  `PlayersInside`(+0x120/+0x128) read, no `PlayersInsideCount`(+0x11C) read, no
  `HasEverContainedPlayer` call, no `ContainsPlayer` call, no round-game-mode call (`0xF7EB50` count
  = 0), no `HasAuthority`/role/NetMode read, no `IsA` check on `this`.**

### 4.2 ⚠ A hazard the gate structure creates

Gate 2 compares `Data` against `Data + Num*8`. If an arm pokes `Num = 1` while leaving `Data = 0`,
the comparison is `0 != 8` — **gate 2 PASSES and the loop dereferences address 0**. The arm must
supply a real buffer, which is exactly why the recorded recipe reaches for the game's own
`ResizeGrow 0xF988D0`.

---

## 5. EXACT SIGNATURE

```c
void ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable(
        /* rcx */ ULokiRideableComponent* this,
        /* rdx */ ALokiPlayerState*       PlayerState,
        /* r8  */ const AActor*           LandingLocationActor);   // nullptr allowed -> this->GetOwner()
```

Cross-checks, five independent instruments, all agreeing:

1. **UHT / Angelscript binding table** — `tools/asdump/out/binds_members.csv:44930`:
   `class,4540,ULokiRideableComponent,/Script/Loki.LokiRideableComponent,method,1,`
   **`"void AuthPlayerDetachPlayerFromRidable(ALokiPlayerState PlayerState,const AActor LandingLocationActor)"`**
2. **`.data` `{name_ptr, exec_thunk, impl}` record** — `rec=0x9C1E520`, name
   `AuthPlayerDetachPlayerFromRidable`, **thunk `0x5456100`, impl `0x55CCCB0`**. Both are **fold
   multiplicity 1** (a full-image record sweep finds exactly one record with that thunk and exactly one
   with that impl) ⇒ the addresses are identifying.
3. **UHT `FPropertyParams` for the parms struct** — two records: `PlayerState @ off 0x0`
   (`pflags 0x10000000000080` = `Parm|NativeAccessSpecifierPublic`) and `LandingLocationActor @ off 0x8`
   (`pflags 0x1010000000000082` = `ConstParm|Parm|…`). ⇒ **16-byte parms struct.**
4. **The exec thunk itself** — `0x5456100` is a textbook `P_GET_OBJECT`/`P_GET_OBJECT`/`P_FINISH`
   sequence (two `FFrame::Step`-family calls at `0x5456133`/`0x5456172` writing `[rsp+0x48]` and
   `[rsp+0x38]`, `P_FINISH` at `0x54561AD`) followed by
   `mov rcx,rsi; mov rdx,[rsp+0x48]; mov r8,[rsp+0x38]; call 0x55CCCB0` at `0x54561B4`.
   **No authority check, no guard, no marshalling beyond the two object fetches.**
5. **The Angelscript call site** pushes, in reverse order, `v4`(LandingLocationActor),
   `v32`(PlayerState), `v12`(this) — matching r8 / rdx / rcx exactly.

**UFunction flags [M]** (`tools/re/out/uht_funcflags_tuthero.csv:12567`):
`0x04020405 = Final | BlueprintAuthorityOnly | Native | Public | BlueprintCallable`,
`params_rva 0x09C1E0A0`, `outer 0x05451250`.

⚠ **`FUNC_BlueprintAuthorityOnly` is set.** The thunk does not enforce it and the impl obviously
cannot; whatever check exists lives in `ProcessEvent`. ⇒ **call the thunk via the S55 primitive, or
call `0x55CCCB0` directly as a plain `__fastcall(this, PS, land)`. Do not route it through
`ProcessEvent`.** Direct-impl calling also removes the arm's dependence on the unsatisfiable **E0c**
marshaller control that has capped attribution for the last two sessions.

---

## 6. WHAT IT WRITES — complete enumeration

Ordered as executed. "target" = which object.

| # | site | target | write | value |
|---|---|---|---|---|
| **W1** | `0x55CCD5B` | **hero** | *(stripped)* fold #1 — **writes nothing** | — |
| **W2** | `0x55CCD89` | **hero** | `AActor::Tags` (`TArray<FName> @ +0x1F0`) — `Remove(FName("MinionIgnore"))`; writes `Tags.Num @ +0x1F8`, possibly `memmove`s the buffer | element removed |
| **W3a** | `0x55CCD93` | **hero** | `AActor::SetActorEnableCollision(true)` — engine call; walks the component tree setting collision enabled and re-registers | `true` |
| **W3b** | `0x55CCD9D` | **hero** | `ALokiHeroCharacter::SetPredropHidden(false)` — writes **`byte hero+0x1BE8`**, then `0x1E3CCD0(this->[+0x30], 0x28)` and tail-jumps `0x5592C70` (a visibility refresh). ⚠ **early-outs (`cmp [rcx+0x1BE8], dl; je ret`) if the value is already `false`** | `false` |
| **W4** | `0x55CCDA5` | **hero → 2 vision granters** | unnamed `0x5586530`: <br>`[hero+0x1978]->ViewDistance(+0xE8) = (float)min(Capsule.ComponentToWorld.Scale3D.X, .Y) * Capsule.CapsuleRadius(+0x6C4) + hero->PracticallyTouchingVisionRadiusOffset(+0x196C)` <br>`[hero+0x1980]->ViewDistance(+0xE8) = hero->PeripheralVisionRadius(+0x1970)` <br>then tail-jmp `[hero_vtable+0xC68]` | recomputed radii |
| **W5a** | `0x55CCDC2` | **movement comp** | `UActorComponent::SetComponentTickEnabled(true)` (virtual `+0x3E0`) | `true` |
| **W5b** | `0x55CCDC9` | **movement comp** | `UCharacterMovementComponent::GravityScale @ +0x1A0` = `0x3F800000` | **`1.0f`** |
| **W6** | `0x55CCDFA` | **hero** | `AActor::SetActorLocation(loc, bSweep=false, OutHit=nullptr, Teleport=None)` — moves `RootComponent(+0x1B0)`; `loc` = `GetLandingTeleportLocation(hero, LandingLocationActor)` | a computed landing point |
| **W7** | `0x55CCE05` | **this (RPC)** | `MulticastOnPlayerEnteredWorld(PlayerState)` — `Final\|Net\|NetReliable\|Native\|Event\|NetMulticast\|Private`; goes through `ProcessEvent` | — |
| **W8** | `0x55CCE1C` | **`ULokiPlayerDropPlaneComponent` on the PlayerState** | `bDropComplete @ +0xD0` = `1` | **`true`** |
| **W9** | `0x55CCE32` | **this** | `PlayersAttached.Num @ +0x138` (via `TArray::Remove`). **`Data(+0x130)` and `Max(+0x13C)` untouched; no free, no realloc** | `Num - 1` |
| **W10** | `0x55CCE4E` | **PlayerState** | *(stripped)* fold #2 — **writes nothing** | — |

### 6.1 Offset provenance (every one measured, none assumed)

| offset | member | how |
|---|---|---|
| `UObject +0x0C` | `ObjectFlags` | this build's recorded layout; bit 30 = `RF_MirroredGarbage` |
| `UActorComponent +0xB8` | `OwnerPrivate` | `UActorComponent::GetOwner` impl `0x3215D20` = `mov rax,[rcx+0xB8]; ret` |
| `AActor +0x150` | `Owner` | `AActor::GetOwner` impl `0x20B9E90` = `mov rax,[rcx+0x150]; ret` (control) |
| `AActor +0x1B0` | `RootComponent` | read by `0x339A7A0` and by `K2_SetActorLocation` `0x3390990` |
| `AActor +0x1F0` | `Tags` | UHT `FPropertyParams` `0x07F209C8` — the **unique** hit for name `Tags` at off `0x1F0`; owner `FClassParams 0x07F227E0`, **NumProperties = 114** = AActor's array (the same one S130 walked) |
| `USceneComponent +0x200/+0x220/+0x240` | `ComponentToWorld` {Rotation, Translation, Scale3D} | read by `0x339A7A0` (translation) and `0x5586530` (scale) |
| `UCapsuleComponent +0x6C4` | `CapsuleRadius` | UHT record `0x07FB7F70`, owner resolved to `CapsuleComponent (/Script/Engine)` |
| `ACharacter +0x460` | `CapsuleComponent` | UHT record `0x07F8ED90`, owner `Character (/Script/Engine)`, idx 2 of 45 |
| `UCharacterMovementComponent +0x1A0` | `GravityScale` | UHT record `0x07FAF510`, owner `CharacterMovementComponent (/Script/Engine)`, idx 1 of 164 |
| `ALokiHeroCharacter +0x196C/+0x1970/+0x1978/+0x1980` | `PracticallyTouchingVisionRadiusOffset` / `PeripheralVisionRadius` / `PracticallyTouchingVisionGranter` / `PeripheralVisionGranter` | four contiguous UHT records `0x0899A8D0 / 908 / 940 / 980`, immediately after the `LokiHeroCharacter` class-name string at `0x899A832` |
| `AVisionGranter +0xE8` | `ViewDistance` | UHT record `0x08AF96F0`, owner resolved to `VisionGranter (/Script/Loki)`, idx 9 of 31 |
| `ALokiPlayerState +0x430` | the pawn | `GetLokiCharacter` impl `0x56BE0D0` |
| `ALokiPlayerState +0xEA8` | `BattleRoyalePlayerPhase` | UHT record `0x08A25F50` (`repnotify=OnRep_BattleRoyalePlayerPhase`) **and** `GetBattleRoyalePlayerPhase` impl `0x54333A0` = `movzx eax, byte [rcx+0xEA8]; ret` |
| `ULokiPlayerDropPlaneComponent +0xD0` | `bDropComplete` | `boolscan` `SetBitFunc` = `mov byte [rcx+0xD0],1`, record `0x08A1C2F0`; **`propowner` puts it at index 0 of the 8-property array whose `FClassParams` ctor is `0x5429740` — the very accessor the code calls at `0x55CCE0D`**; the usmap independently lists `bDropComplete` first among that class's properties |
| `ULokiRideableComponent +0x118/+0x11C/+0x120/+0x130/+0x140` | `bCanExit` / `PlayersInsideCount` / `PlayersInside` / `PlayersAttached` / `PlayersThatExited` | `propscan` + `propowner`; **positive control: `+0x11C`, `+0x120`, `+0x130` reproduce the live-measured values already recorded in `CLAUDE.md`**, and the **Angelscript bytecode oracle independently prints `ADDSi 288 → .PlayersInside` and `ADDSi 304 → .PlayersAttached`** = `0x120` / `0x130` |

---

## 7. THE TWO FOLD CALLS

`0x00F7EC20` is **`c2 00 00` = `ret imm16 0`** — a *void* no-op. It does **not** set `eax`. With
**165,789** direct call sites image-wide, the address identifies nothing by itself.

### 7.1 FOLD #1 — `0x55CCD5B`

```
0x55CCD53  48 8b cf              mov  rcx, rdi          ; rdi = the ALokiHeroCharacter
0x55CCD56  4c 89 74 24 50        mov  [rsp+0x50], r14   ; unrelated spill
0x55CCD5B  e8 c0 1e 9b fb        call 0xf7ec20
0x55CCD60  41 b8 01 00 00 00     mov  r8d, 1            ; <-- eax is DEAD here
```
* **Receiver: the hero character.** Only `rcx` is set ⇒ a **0-parameter** member function.
* **Position:** immediately after the `IsA<ALokiHeroCharacter>` gate and immediately before the
  un-ride sequence (`Tags.Remove("MinionIgnore")` → collision → un-hide → vision → gravity → teleport).
* **Return value: NOT tested.** No branch follows and nothing reads `eax`. **[M]**
* **Identity: UNKNOWN.** A sweep of every reflected record whose impl is one of the five folds and
  whose owning class is `AActor` / `ALokiCharacter` / `ALokiHeroCharacter` / `ALokiPlayerState` /
  `ALokiPlayerState_Missions` returned **81 records** (5 of them on `ALokiHeroCharacter`:
  `AddRevivingEffectV2`, `AddStompingEffectV2`, `PulseBloom`, `SetLevelingPassiveChoice`,
  `UpdateLoSVisibilityStatCounters`) and **none** fits a 0-argument un-ride step at this position.
  ⇒ most likely a **non-reflected C++ method**; record it as *an unnamed stripped hero-side `void()`
  method*. **[M] that it is stripped; identity [S].**
* **Work skipped by it: only its own side effect.** No branch, no data flow.

### 7.2 FOLD #2 — `0x55CCE4E`

```
0x55CCE37  48 8b 8c 24 88 00 00 00   mov  rcx, [rsp+0x88]   ; = the PlayerState (its home slot)
0x55CCE44  48 85 c9                  test rcx, rcx
0x55CCE47  74 0a                     je   0x55CCE53
0x55CCE49  45 33 c0                  xor  r8d, r8d          ; arg3 = nullptr
0x55CCE4C  b2 03                     mov  dl, 3             ; arg2 = 3  (a BYTE / enum)
0x55CCE4E  e8 cd 1d 9b fb            call 0xf7ec20
0x55CCE53  ...epilogue...            ; void function -> eax irrelevant
```
* **Receiver: the PlayerState.** Two explicit args: a byte `3` and a null pointer. (`[rsp+0x88]` is
  untouched by the preceding `TArray::Remove`, which takes it as a read-only `const T&`.)
* **Return value: NOT tested.** **[M]**
* **Identity: [I], strongly constrained but NOT measured.** Best candidate:
  **`ALokiPlayerState::Auth*BattleRoyalePlayerPhase(EBattleRoyalePlayerPhase::Combat, nullptr)`.**
  Supporting evidence:
  1. **[M] `EBattleRoyalePlayerPhase::Combat == 3`** — read from the UHT `FEnumeratorParam` array at
     `.rdata 0x08A2C9E0`: five contiguous 16-byte `{const char* name, int64 value}` records giving
     `None 0 · Pregame 1 · Dropping 2 · Combat 3 · PostGame 4`. Positive control: values are 0..4 in
     declaration order with no gaps, so the stride/decode is right.
  2. **[M] `ALokiPlayerState` owns exactly one such byte** — `BattleRoyalePlayerPhase @ +0xEA8`,
     `Net|RepNotify`, with a getter (`0x54333A0`) and an `OnRep_`, and **no reflected setter anywhere
     in the record table**.
  3. **[M, bounded] no compiled writer of `[PS+0xEA8]` exists in the decrypted `.text`** — an exhaustive
     scan of all 86 occurrences of the displacement bytes `a8 0e 00 00` in `.text` finds 34 stores, and
     every one is either a `dword` store or a stack-frame (`rbp`/`rsp`) store; **zero
     `mov byte ptr [reg+0xEA8], <enum>`**. ⚠ Bounded: `.text` in `merged4` is **55.09 % decrypted**
     (16,683 of 30,281 pages), and the property is replicated, so the net serializer writes it by
     computed offset. Supporting, not decisive.
  4. Semantics: "the player has left the pod and is now in the world" ⇒ phase `Combat` is exactly
     right, and it is the last statement of the function.
  * **⚠ Explicitly NOT [M]:** there is no sibling to triangulate with. An **uncapped** `.text` scan for
    `{xor r8d,r8d ; mov dl,imm8 ; call 0xF7EC20}` in either operand order found **exactly one site in
    the entire image — this one.**
* **Work skipped by it: only its own side effect.**

### 7.3 ⚠ CORRECTION to `CLAUDE.md` §14.1

The recorded guidance reads:
> *"Expect a PARTIAL dismount, and read any null as locating one of those two."*

The first half stands; **the second half is wrong as an inference rule.** Neither fold's result is
tested, so **neither fold can produce a null on any observable this function has.** A null localises
to one of the **eight gates in §4** (or to a caller-side error), *never* to a fold. Reading a null as
"it hit one of the two folds" would be an instrument artifact: the folds are invisible to every
observable in §6.

---

## 8. PRE-REGISTERED PREDICTION TABLE

**Arm as specified:** append ONE live `ALokiPlayerState*` to `this->PlayersAttached` (real buffer via
the game's own `ResizeGrow 0xF988D0`; `Data` non-null, `Num = 1`), then call
`AuthPlayerDetachPlayerFromRidable(PlayerState, nullptr)` — recommended route: a **direct
`__fastcall` to the impl `0x55CCCB0`** with `rcx = the component`, `rdx = the PlayerState`, `r8 = 0`.

### 8.1 Preconditions to READ (read-only RPM) BEFORE arming — each maps to a gate

| read | gate it decides | required value |
|---|---|---|
| `PlayerState->ObjectFlags` (`+0x0C`) bit 30 | 1b | **0** |
| `PlayerState + 0x430` | 4 | **non-null** |
| that pawn's UClass chain contains `ALokiHeroCharacter` | 5 | **yes** — else no hero work at all |
| `hero + 0x460` (CapsuleComponent) | W4 crash | **non-null** |
| `hero + 0x1978`, `hero + 0x1980` (vision granters) | W4 crash | **non-null** — ⚠ **unguarded deref, H13** |
| `PlayersAttached.Data (+0x130)` after the poke | §4.2 hazard | **non-null** |
| `mc->GravityScale (+0x1A0)`, hero world location, `bDropComplete` | receipts | record the before-values |

### 8.2 Predicted observable consequences, ranked by confidence

| rank | prediction | confidence | how to read it |
|---|---|---|---|
| 1 | **`PlayersAttached.Num (+0x138)` goes `1 → 0`.** `Data` and `Max` **unchanged**; no free, no realloc, no `memmove` (traced: with `Num==1` and a match, `0x11F3860` takes the no-memmove path and returns 1). | **very high [M]** — deterministic given gates 1–3 | RPM read of `+0x130/+0x138/+0x13C` before and after |
| 2 | **The hero TELEPORTS** to `GetLandingTeleportLocation(hero, pod)`. Loudest signal; the primary receipt. | **high** — the callee is REAL, 963 B, fold-free, fully decrypted; the mover is plain `AActor::SetActorLocation` | RPM `hero->RootComponent(+0x1B0)->ComponentToWorld.Translation(+0x220)`, or `RelativeLocation(+0x158)` |
| 3 | **`ULokiPlayerDropPlaneComponent::bDropComplete (+0xD0)` on the PlayerState goes `0 → 1`.** Cleanest binary receipt in the function. | **high, CONDITIONAL on gate 7** — the PS must actually own that component | one-byte RPM read after resolving the component |
| 4 | `mc->GravityScale (+0x1A0)` reads exactly **`1.0f`** afterwards, and `mc` is tick-enabled. | **high**, but likely a **no-op** — a normally-spawned hero already has `1.0`. Record the *before* value; if it was already 1.0 this is uninterpretable, not negative. | RPM float read |
| 5 | `hero->Tags (+0x1F0)` no longer contains `MinionIgnore` (and `Tags.Num` may drop by 1). | **medium** — only moves if the tag was there, which it will not be on a hero that never rode | RPM walk of the `TArray<FName>` |
| 6 | `hero+0x1978->ViewDistance(+0xE8)` and `hero+0x1980->ViewDistance(+0xE8)` are recomputed. | **medium** — will run, but the recomputed values may equal the existing ones | RPM float reads before/after |
| 7 | `MulticastOnPlayerEnteredWorld` executes its local `_Implementation` (no net driver ⇒ `FunctionCallspace::Local`). Possible knock-on UI/log/delegate activity. | **medium [I]** — standard UE semantics, not measured here | watch `Loki.log` for anything new; do **not** treat silence as negative |
| 8 | `hero->[+0x1BE8]` (predrop-hidden) → `false`. | **low** — `SetPredropHidden` **early-outs when the value already equals the argument**; on a normally-spawned hero it is already `false`, so this is a guaranteed no-op | RPM byte read |
| 9 | `PlayerState->BattleRoyalePlayerPhase (+0xEA8)` **does NOT change** — the setter is stripped. | **high [M-mechanism]** | RPM byte read; **an unchanged byte here is the EXPECTED result, not a failure** |
| 10 | **No new log line of any kind is attributable to this function.** | **high [M]** — no logger call in the body | do not build a grep-based receipt for this call |

### 8.3 What a NULL localises to

| observation | localises to | next read |
|---|---|---|
| `PlayersAttached.Num` still `1` | gate **1a** (PS null), **1b** (PS garbage), **2** (`Num` read as 0 at call time) or **3** (the element in the array is not the pointer you passed) — **or the call never dispatched** | re-read `Num` and `Data[0]` immediately before the call; compare `Data[0]` to the PS pointer bit-for-bit |
| `Num` went to `0` **but the hero did not move** | gate **4** (`[PS+0x430]` null) or gate **5** (pawn is not an `ALokiHeroCharacter`) — the *silent partial* outcomes | both are pre-readable (§8.1); if they were pre-checked and passed, escalate to "`GetLandingTeleportLocation` returned the hero's current position" |
| hero moved, `bDropComplete` unchanged | gate **7** only — the PlayerState has no `ULokiPlayerDropPlaneComponent`. **Not a failure of the dismount** | enumerate the PS's `OwnedComponents` |
| hero moved a tiny/zero distance | `GetLandingTeleportLocation` resolved to (approximately) where the hero already is | call `GetLandingTeleportLocation` **alone** first — it is `Final\|Native\|Public\|HasDefaults\|BlueprintCallable`, **not** `BlueprintAuthorityOnly` |
| **process death** | most likely **W4** — `0x5586530` dereferences `hero+0x460`, `hero+0x1978`, `hero+0x1980` with **no null checks**; second most likely the poked `PlayersAttached.Data` | pre-read all four pointers (§8.1). This is the single biggest risk in the arm. |
| nothing at all, no fault, no receipt | the call did not dispatch (wrong `this`, wrong primitive), **or** `ProcessEvent` refused it on `FUNC_BlueprintAuthorityOnly` | use the **direct impl call**, which has no such check by construction |

### 8.4 Two design notes the transcription hands the arm for free

* **`LandingLocationActor = nullptr` is not a compromise.** It resolves to `this->GetOwner()`, and the
  game's own caller passes the pod actor, which for the pod's own rideable component **is**
  `GetOwner()`. Passing `nullptr` therefore reproduces the shipped behaviour in the ordinary case.
  (The one exception is `KickPlayersFromPod`'s crew branch, which substitutes `LeaderPod` —
  irrelevant to a single-pod arm.)
* **⚠ ORDERING, confirmed from the game's own caller:** `ALokiDropPod::KickPlayersFromPod` iterates
  `PlayersInside` and calls detach directly only when `PlayersAttached.Contains(PS)`; when the PS is
  *not* attached it calls `AuthPlayerEnterWorld` **first** and detach second. Since
  `AuthPlayerEnterWorld` gates on `PlayersInside` and hits the stripped round-game-mode getter at
  `0x55CCF22`, the **attached-only** path is the one worth flying — and it is exactly the arm as
  specified. This corroborates `CLAUDE.md`'s existing warning **not** to poke `PlayersInside`.

---

## 9. THE SINGLE GAME CALLER (context, all [M])

An **uncapped** full-`.text` rel32 scan finds:
* `impl 0x55CCCB0` — **2** sites: `0x54561B4` (the exec thunk's own tail call) and **`0x596A190`**;
* `thunk 0x5456100` — **0** sites (the same shape S131 recorded for the mount function).

`0x596A190` is inside the Angelscript AOT range. The Angelscript listing identifies it:
`tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt`, **`ALokiDropPod::KickPlayersFromPod`**, two
`CALLSYS` sites at bytecode offsets `0x01D8` and `0x02EC`:

```
0x01B0  ADDSi  304 ...  ; .PlayersAttached      (= 0x130, independent confirmation)
0x01B8  CALLSYS TArray<ALokiPlayerState@>::Contains
0x01C4  JLowZ  8 -> L01EC
0x01CC  PshVPtr v4        ; LandingLocationActor
0x01D0  PshVPtr v32       ; PlayerState
0x01D4  PshVPtr v12       ; this (the rideable component)
0x01D8  CALLSYS ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable
```

and the whole body is behind

```
0x0000  PshGPtr __WorldContext
0x000C  CALLSYS LokiIsClient
0x0018  JLowZ 2 -> L0028
0x0020  JMP  192 -> L0328     ; <-- immediate return
```

`Loki::LokiIsClient` impl `0x00B9E1F0` = `mov al,1; ret` (hardcoded TRUE on this client)
⇒ **`KickPlayersFromPod` returns immediately, always. The game never calls detach.**
Everything in §8.2 therefore has a **verified baseline of zero**.

---

## 10. INSTRUMENT NOTES / CAVEATS

* **Capped tools were avoided.** `fkdis callxref` / `findptr` cap at 200 rows; every caller/xref count
  here comes from my own uncapped scan and is a **count**, not a floor. Where a number is bounded I say
  so (`.text` is 55.09 % decrypted, so "no other call site exists" claims are bounded to the decrypted
  image — §7.2 item 3 is the only place I lean on one, and it is graded accordingly).
* **`propscan.py` is a reconstructed tool** (see `scratchpad/s130/tools/README.md`). I used it only for
  `off=` and `name=`, never its `gen=` type label, which that README documents as misaligned for this
  build. **Positive control:** it independently reproduces `PlayersInsideCount @0x11C`,
  `PlayersInside @0x120` and `PlayersAttached @0x130` — three values `CLAUDE.md` records as measured
  live on the running client — before I trusted any new offset from it.
* **The class-identification method used for `0x54F8DC0` was controlled.** The same recipe (find the
  `GetPrivateStaticClass` callee, read its `rdx` wide-string argument) applied to the *sibling* helper
  `0x54F8C40` — reached from `GetLokiCharacter`, where the answer must be the base class — returns
  **`LokiCharacter`**, not `LokiHeroCharacter`. Different input, correct different answer.
* **The `0x3E0` vtable resolution is fold-disambiguated, not fold-blind** — the multiplicity (3) and
  the other two owners are printed, and rejected on the class hierarchy rather than ignored.
* **Two of my own near-misses, recorded:** (a) I first mis-parsed the UNWIND_INFO code-array size and
  got garbage chain targets — caught because the "chain" pointed at addresses like `0xCCB0000C`, which
  are not `.text`; (b) I initially read `0x76EC5C8` as a format string and got `'???'` — it is a
  *pointer* to the string at `0x76EC5F0`. Both were caught by looking at the raw bytes instead of the
  decoded value.

### Artefacts written
* `scratchpad/s132/lanes/_listing.txt` — the machine-generated annotated listing (also inlined in §2)
* `scratchpad/s132/lanes/_gen_listing.py` — the generator (annotation coverage self-check: 104/104)
* `scratchpad/s132/lanes/_owner.py` — UHT record → owning-UClass-name resolver used throughout §6.1
* `scratchpad/s132/lanes/allprops_merged4.pkl` — cached sweep of 89,212 `F*PropertyParams` records
