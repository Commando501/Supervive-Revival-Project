# S132 — `ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable` transcribed and NAMED

**Session lead's independent reading, written BEFORE the recon lanes reported, so it can be diffed
against them.** Offline only: `dumps/merged4.dump.exe`, ImageBase `0x7FF6AF000000`, file offset == RVA.
Zero launches, zero injections, zero `.text` writes.

## 0. Extent and coverage [M]

`tools/strxref/index/pdata_union.csv`, 9 chained rows:
`0x55CCCB0 -> CCDB -> CD07 -> CD2D -> CD56 -> CE1C -> CE49 -> CE5B -> CE60 -> ends 0x55CCE68`
=> **440 bytes (0x1B8)**, matching the handoff. `fkdis cov` reports page `0x055CC000` **present**
(decrypted) — nothing here is coverage-blocked.

## 1. FIRST, A CORRECTION I MADE TO MYSELF

I initially subtracted the image base **by hand** and got 7 of 21 call targets wrong
(`0x7FF6B239A550` read as `0x239A550`; correct is `0x339A550`) — the error appears whenever the third
hex digit rolls past `af`. Every wrong RVA disassembled into *plausible mid-function garbage* and every
record-table lookup on one returned `None`, which reads exactly like "not a reflected function".
**Recomputed with a machine; all 21 targets below are machine-derived.**
This is the project's standing rule *"recompute, never retype an RVA"* — broken in the first ten
minutes. It cost nothing only because the record-table lookup returned an obviously-wrong all-`None`
column that did not match the disassembly's shape.

## 2. THE NAMED BODY [M]

Names come from the `.data` `{name_ptr, exec_thunk, impl}` record table
(`scratchpad/s131/tools/rectab.py`), read from **two independent single-state dumps** (`s129`,
`tuthero`) which agree on every row. Positive control: the function's own impl `0x55CCCB0` resolves to
`AuthPlayerDetachPlayerFromRidable`.

Signature [M, UHT oracle `tools/asdump/out/binds_members.csv`]:

```
void AuthPlayerDetachPlayerFromRidable(ALokiPlayerState PlayerState, const AActor LandingLocationActor)
```

=> `rcx=this, rdx=PlayerState, r8=LandingLocationActor`. Exec thunk `0x5456100`, fold multiplicity 1.

```
0x55CCCB0  test rdx,rdx / je ret            GATE 1  PlayerState != null            SILENT
0x55CCCC5  eax=[PS+0xC]>>30; not; test 1    GATE 2  PS not garbage (ObjectFlags)   SILENT
0x55CCCE0  if (r8 == null) r8 = [this+0xB8]         LandingActor defaults to the component's owner
0x55CCCEC  rcx=[this+0x130]  Data                   * PlayersAttached.Data  @ +0x130
0x55CCCF3  rax=[this+0x138]  Num                    * PlayersAttached.Num   @ +0x138
0x55CCCFA  rdx = Data + Num*8                       * element size 8 (TArray<ALokiPlayerState*>)
0x55CCCFE  cmp rcx,rdx / je                 GATE 3  PlayersAttached NON-EMPTY      SILENT
0x55CCD17  linear scan for PS; not found -> GATE 4  PS PRESENT in PlayersAttached  SILENT
0x55CCD32  rdi = PS->GetLokiCharacter()             [M] record table
0x55CCD3A  test rax / je 0x55CCE23          GATE 5  hero != null  -> jump to the REMOVE tail
0x55CCD46  al = IsA(hero, ALokiHeroCharacter)       [M] see section 3
0x55CCD4D  test al / je 0x55CCE23           GATE 6  hero IS a LokiHeroCharacter -> else REMOVE tail
0x55CCD5B  call 0x0F7EC20 (hero)            FOLD 1 -- STRIPPED, void, return NOT tested
0x55CCD75  FName tmp("MinionIgnore")                .rdata 0x8B1B5F0
0x55CCD89  call 0x10FF910(&hero[+0x1F0], &tmp)      TArray<FName> op on AActor::Tags
0x55CCD93  hero->SetActorEnableCollision(true)      [M] 0x339A550
0x55CCD9D  hero->SetPredropHidden(false)            [M] 0x5599040 -- writes byte hero+0x1BE8
0x55CCDA5  call 0x5586530(hero)                     REAL, unnamed (reads hero+0x460 -> capsule math)
0x55CCDAD  mv = hero->GetLokiCharacterMovement()    [M] 0x55AC8E0 (reads hero+0x458)
0x55CCDC2    if (mv) mv->vtbl[+0x3E0](true)
0x55CCDC9            *(float*)(mv+0x1A0) = 1.0f
0x55CCDE2  this->GetLandingTeleportLocation(&outLoc, hero, LandingActor)  [M] 0x55D89F0 REAL 963 B
0x55CCDFA  hero->SetActorLocation(&outLoc, false, nullptr, ETeleportType::None)   *** THE TELEPORT
0x55CCE05  this->MulticastOnPlayerEnteredWorld(PS)  [M] 0x54537C0
0x55CCE0D  o = call 0x55C6E80(PS); if (o) o->[0xD0] = 1
0x55CCE23  PlayersAttached.Remove(PS)               0x11F3860, on &this[+0x130]   * runs on EVERY
                                                     path past GATE 4, incl. the GATE 5/6 skips
0x55CCE4E  if (PS) call 0x0F7EC20(PS, 3, 0)  FOLD 2 -- STRIPPED, void
0x55CCE67  ret
```

### 2.1 THE HEADLINE: THE DISMOUNT IS ALL-REAL

`SetActorEnableCollision`, `SetPredropHidden(false)`, `GetLokiCharacterMovement`,
`GetLandingTeleportLocation` and `SetActorLocation` are **every one a real body**. The two `0xF7EC20`
folds are **void side effects whose returns are never tested**, so neither gates the teleport.
The handoff's "expect a PARTIAL dismount" is **too pessimistic**: the partiality is confined to two
unnamed void state-changes, one on the hero and one on the PlayerState.

`0x339A7A0` is not in the record table (it is a plain engine method, not a UFunction), but its
prologue is `push rbx; sub rsp,0x170; mov rcx,[rcx+0x1B0]; test rcx,rcx; je bail` — it reads
`AActor::RootComponent` at `+0x1B0` [M, CLAUDE.md] and bails if null, and the call site passes
`(actor, &FVector, r8d=0, r9d=0, [rsp+0x20]=0)`. That is `AActor::SetActorLocation(const FVector&,
bool bSweep, FHitResult*, ETeleportType)` exactly. It sits `0x250` bytes from the confirmed
`SetActorEnableCollision` in the same translation unit. Grade **[I, strong]**, not [M] — the name is
inferred from shape and neighbourhood, not read from a table.

## 3. The `IsA` gate, settled [M]

`0x54F8DC0` is `IsChildOfUsingStructArray`: it calls `0x5395720` (a cached `StaticClass()` getter that
ignores `rcx`), reads `hero->ClassPrivate` at `[hero+0x18]`, then
`Parent.NumStructBasesInChainMinusOne <= Child.Num && Child.StructBaseChainArray[N] == &Parent`
with `FStructBaseChain` at `UClass+0x38` (`Array@+0x38`, `Num@+0x40`). The class-name literal reached
from `0x5395720` is **`LokiHeroCharacter`** (UTF-16 at `.rdata 0x899A832`).
=> **GATE 6 is `hero->IsA(ALokiHeroCharacter)`**. The staged tutorial hero is `BP_HERO_Ronin_C`, so it
should pass — but it is a real gate and the arm must read it out, not assume it.

## 4. THE OBVIOUS SHORTCUT IS DEAD — `AuthAddPlayer` IS A STRIPPED STUB [M, strong]

`ULokiRideableComponent` declares `void AuthAddPlayer(ALokiPlayerState)` (member index 0). If it were
real it would replace the entire hand-built `ResizeGrow` append. It is not:

| rideable method | exec thunk | impl | verdict |
|---|---|---|---|
| `AuthAddPlayer` | `0x2C2CE30` (23-way ICF) | **`0x0F7EC20`** | **EMPTY** |
| `AuthRemovePlayer` | `0x2C2CE30` | **`0x0F7EC20`** | **EMPTY** |
| `AuthSetCanJump` | `0x5296F30` | **`0x0F7EC20`** | **EMPTY** |
| `AuthPlayerEnterWorldNew` | `0x5456460` | **`0x0F7EC20`** | EMPTY (already known) |
| `AuthPlayerDetachPlayerFromRidable` | `0x5456100` | `0x55CCCB0` | REAL |
| `AuthPlayerEnterWorld` | `0x54561D0` | `0x55CCE70` | REAL |
| `AuthPlayerEnterWorldAttachedToRidable` | `0x5456380` | `0x55CD510` | REAL |
| `AuthPlayerPreSpawnOnAddToPlane` | `0x5456540` | `0x55CD800` | REAL |
| `ContainsPlayer` | `0x5456700` | `0x55D0270` | REAL |
| `GetLandingTeleportLocation` | `0x5456C80` | `0x55D89F0` | REAL |
| `HasEverContainedPlayer` | `0x5457280` | `0x55DCAA0` | REAL |
| `GetRidePosition` | `0x5457070` | `0x55DAB50` | REAL |

=> **the rideable's empty-stub count is 4, not 1** — every one an `Auth*` mutator, which is exactly the
`Auth*`-enriched pattern S131's census measured (42.4 % vs 8.30 %, p = 1.6e-28).

The record table has **no class column**, so the `AuthAddPlayer` / `AuthRemovePlayer` rows are matched
by NAME. Both names occur **exactly once** in the whole 16,277-record table and
`ULokiRideableComponent` is the only class in `binds_members.csv` declaring either, so the attribution
is [M, strong] rather than [M]. Structural corroboration: the rideable exec thunks are emitted
**alphabetically** in one contiguous UHT block (`0x5455F40 AddGameplayEffect` ...
`0x5457940 SetPlayerDisassociationFromPhase`), and `AuthAddPlayer` would sort at ~`0x5456050` — where
the bytes are real code, not a thunk. Its thunk is absent from the block **because it was ICF-folded
onto the shared one-object-param stub `0x2C2CE30`**, which is what a stripped impl does.

## 5. `ContainsPlayer` READS THE WRONG ARRAY — DO NOT USE IT AS THE APPEND RECEIPT [M]

```
0x55D0270  mov rax,[rcx+0x120]      ; PlayersInside.Data
0x55D0277  movsxd rcx,[rcx+0x128]   ; PlayersInside.Num
```

It scans **`PlayersInside` (+0x120)**, not `PlayersAttached` (+0x130). So after the append it still
reads **false**, and that false is EXPECTED, not a failure. It remains a valid *dispatch* positive
control and nothing more. Reading it as the receipt would have manufactured a false negative — the
project's dominant failure mode, avoided here only by disassembling the control before trusting it.

## 6. THE FREE, LOG-FREE, THREE-WAY RECEIPT

`PlayersAttached.Remove(PS)` at `0x55CCE23` executes on **every path that passes GATE 4**, including
the two paths that skip the whole hero body. Therefore, reading `Num` at `+0x138` after the call:

| `Num` after | meaning |
|---|---|
| stays **1** | body bailed at GATE 1/2/3/4 -> the append did not take, or the PS failed its validity test |
| drops to **0** | **the body definitively ran past GATE 4** |
| 0 **and** the hero moved | full dismount |
| 0 **and** the hero did not move | GATE 5 or GATE 6 failed (no hero, or not an `ALokiHeroCharacter`) |

That is an unambiguous discriminator that owes nothing to a log line, on a function with **zero log
strings in its extent**.
Secondary physical receipts, all RPM-readable: the hero's `RelativeLocation`; `hero+0x1BE8`
(`bPredropHidden`, written by `SetPredropHidden`, which early-outs when already equal — so an
unchanged value there is uninterpretable, not negative); `AActor::Tags` at `hero+0x1F0`.

## 7. THE APPEND, VERIFIED AGAINST THE WALL'S OWN BYTES [M]

`AuthPlayerEnterWorldAttachedToRidable`'s tail, `0x55CD738..0x55CD76A`:

```
0x55CD738  movsxd rbx,[r14+0x138]        ; old = Num
0x55CD73F  lea    eax,[rbx+1]
0x55CD742  mov    [r14+0x138], eax       ; Num = old+1        <- INCREMENT FIRST
0x55CD749  cmp    eax,[r14+0x13c]        ; (old+1) vs Max
0x55CD750  jbe    0x55CD760              ; unsigned <= -> skip grow
0x55CD752  mov    edx, ebx               ; OldNum = old
0x55CD754  lea    rcx,[r14+0x130]        ; &PlayersAttached
0x55CD75B  call   0x00F988D0             ; ResizeGrow
0x55CD760  mov    rax,[r14+0x130]        ; RE-READ Data after the grow
0x55CD767  mov    [rax+rbx*8], rdi       ; Data[old] = PlayerState
```

=> the handoff's recipe is **correct as written**, and the growth test is `jbe` (unsigned) on `(old+1)`
vs `Max`. `0x55CD75B`'s rel32 decodes to `0x00F988D0` — the same function, same array, same element
type, so **the ABI and element size are correct by construction**.

`0x00F988D0` is `TArray::ResizeGrow(SizeType OldNum)` with element size and alignment **8**, both
appearing as literal `8`s (`0x00F98917 lea rcx,[rax*8]`, `0x00F98934 mov r9d,8`,
`0x00F9892C mov [rsp+0x20],8`). It reads `Num` from `[rcx+8]`, and `cmp ebx,edx; jl 0x00F9895D` (an
`int3`-terminated abort) means **`Num` must already be `>= OldNum` when it is called** — i.e. the
increment genuinely must happen first. With `Max==0, Num==1, OldNum==0` it takes the `Max==0` branch
(`eax=4`), `cmova` does not fire because `1 > 4` is false, so `NewMax = 4` -> 32 bytes.
MEASURED live in S131: `PlayersAttached` reads `Data=0 Num=0 Max=0`, so the grow WILL be taken.

## 8. The wall's own success tail, for comparison [M]

```
0x55CD703  LokiTeleportActor(...)                    [M] record table
0x55CD70D  hero->SetActorEnableCollision(true)       [M] 0x339A550
0x55CD719  SpawnAndMoveLokiCharacter_MoveStep(hero, &vec)
0x55CD723  hero->SetActorEnableCollision(false)      [M] -- riding, so collision OFF
0x55CD72B  xmm0 = GetServerTime()                    [M] 0x37D9D40
0x55CD730  *(float*)(hero+0x1C10) = xmm0
0x55CD738  PlayersAttached.Add(PS)                   (section 7)
```

The wall turns collision OFF at the end (a rider inside a pod); the detach turns it back ON. The two
functions are a matched pair, which is corroboration that `0x339A550` is `SetActorEnableCollision` in
both places.
