# S132 (2026-08-20) — THE DROP-POD DISMOUNT RUNS. The hero leaves the pod and is placed on the ground.

**One line: appending the PlayerState to `PlayersAttached` with the game's own `ResizeGrow` and then
calling `AuthPlayerDetachPlayerFromRidable` takes the hero out of the pod, un-hides it, restores its
collision and movement, and places it at a chosen landing actor on real terrain, where it stands —
**five calls across two launches**, four of them against a target moving at 20,000 uu/s, each preceded
by a within-run negative control that never moved it.**

★ **Flight 1 (§1) established that it RUNS. Flight 2 (§6) established that it is USABLE**: with a
`LokiPlayerStart` passed as `LandingLocationActor` — 1.49 million uu from the pod at that instant —
the hero landed at the PlayerStart, settled onto the floor, and held position bit-for-bit for 9 s.

Risk class **DATA**: two aligned `TArray`-header writes plus one element store, inside the game's own
allocation. **Zero `.text` writes, zero PI hooks, zero CDO pokes.** One launch, one armed window,
client alive throughout (>1,110 s) with 0 crashpad handoffs and 0 `Fatal`.

Evidence: `scratchpad/s132/evidence/` (markers 4–9, the pre-flight capture.log, this session's dumps).
Offline recon + adversarial verification: `scratchpad/s132/lanes/`.

---

## 1. THE RESULT

| run | `LandingLocationActor` passed | hero X after | Y | Z | `PlayersAttached.Num` |
|---:|---|---:|---:|---:|---|
| baseline | — | 0.0 | 0.0 | 13240.0 | 0 |
| **1** | `nullptr` → detach substitutes `[comp+0xB8]` | **1,453,041.8** | 5070.476806195347 | 250.0 | 0 → 1 → **0** |
| **2** | `nullptr` | **4,859,800.1** | 5070.4768061953482 | 250.0 | 0 → 1 → **0** |
| **3** | the pod, EXPLICIT | **11,648,502.8** | 5070.5 | 250.0 | 0 → 1 → **0** |
| **4** | the pod, EXPLICIT | **14,428,083.3** | 5070.5 | 250.0 | 0 → 1 → **0** |

**The negative control ran before every one of the four** — the same detach, on the same component,
through the same primitive, with `PlayersAttached` EMPTY — and the hero did not move any of the four
times. The pre-registration was written into the shim's own output before the call:

```
[DX] --- D1 (NEGATIVE CONTROL ...): PRE-REGISTERED PREDICTION: nothing happens -- GATE 3 bails at
     0x55CCD01, the hero does not move, Num stays 0. If the hero DOES move here, the array is not the
     gate and the whole S131 model is wrong -- which would be the biggest result of the session. ---
[DX] D1 RESULT: hero moved=no (as predicted)  (before=(0.0,0.0,13240.0) after=(0.0,0.0,13240.0))
```

### 1.1 The landing point is a PAYLOAD FINGERPRINT [M]

The pod flies at its cooked `InitialSpeed` in +X and its Y and Z are exactly constant (S131). Live RPM
during the armed window:

```
pod  ComponentVelocity = (20000.0, 0.0, 0.0)     measured speed 19,996.8 and 19,999.1 uu/s
pod  Y (17 sig figs)   = 5070.4768061953482
hero Y after run 2     = 5070.4768061953482      p1[1] == h1[1]  ->  True
```

- **Run 2's hero Y is BIT-IDENTICAL to the pod's**, verified by a `==` on the raw doubles in a live
  read, not by a formatted print. Run 1's is **1 ULP below it**. Runs 3–4 agree to the marker's
  printed precision.
- The four landing X values are **1.45 M → 4.86 M → 11.65 M → 14.43 M**, i.e. the target moved
  **12.98 million uu across the four calls**, and each landing matches the pod's X at *its own* call
  time (back-computed at 20,000 uu/s: 230.7 s and 60.4 s before one reference read, for runs 1 and 2).
- Z is **250.0** every time — the ground plane under the pod's flight line, while the pod itself is at
  Z = 20,100.

⇒ **No static explanation survives.** The hero is being placed where `GetLandingTeleportLocation`
computed, from the pod's live transform, at the moment of each call.

### 1.2 The hero is handed back to physics [M]

Before the dismount the hero sat motionless at `(0, 0, 13240)` — parked by `sp`, not simulating. After
it, consecutive live reads 4.0 s apart give `Z = -117,462.8` then `-121,560.9` while X and Y are
**frozen and identical**: it is in free fall, accelerating, with no lateral drift.

⇒ `SetActorEnableCollision(true)`, `SetPredropHidden(false)` and the `GetLokiCharacterMovement`
restore (`vt[+0x3E0](true)`, `[mv+0x1A0] = 1.0f`) all took effect. **Measured, not inferred.**
⚠ It falls because the pod had flown 1.45 M uu off the tutorial island by then and there is no ground
under the landing point — a consequence of *when* we called, not a defect in the dismount.

---

## 2. THE FUNCTION, TRANSCRIBED AND NAMED

`ULokiRideableComponent::AuthPlayerDetachPlayerFromRidable`, impl `0x55CCCB0`, exec thunk `0x5456100`,
**440 bytes over 9 chained `.pdata` rows** (`0x55CCCB0 … 0x55CCE68`), page `0x055CC000` decrypted.
Signature [M, UHT oracle `tools/asdump/out/binds_members.csv`]:

```
void AuthPlayerDetachPlayerFromRidable(ALokiPlayerState PlayerState, const AActor LandingLocationActor)
```

Every name below comes from the `.data` `{name_ptr, exec_thunk, impl}` record table read in **two
independent single-state dumps** (`s129`, `tuthero`) that agree on every row; the function's own impl
resolving to its own name is the positive control.

```
0x55CCCB0  test rdx,rdx / je ret            GATE 1  PlayerState != null                 SILENT
0x55CCCC5  [PS+0xC]>>30, not, test 1        GATE 2  PS not garbage (ObjectFlags)         SILENT
0x55CCCE0  if (arg2 == null) arg2 = [this+0xB8]      LandingActor defaults to the owner
0x55CCCEC  Data=[this+0x130] Num=[this+0x138]        PlayersAttached, element size 8
0x55CCCFE  cmp Data, Data+Num*8 / je        GATE 3  PlayersAttached NON-EMPTY            SILENT
0x55CCD17  linear scan for PS               GATE 4  PS PRESENT in PlayersAttached        SILENT
0x55CCD32  hero = PS->GetLokiCharacter()                                   [M] record table
0x55CCD3A  test / je 0x55CCE23              GATE 5  hero != null      -> REMOVE-only tail
0x55CCD46  IsChildOf(hero, LokiHeroCharacter)                             [M] see §2.1
0x55CCD4D  test / je 0x55CCE23              GATE 6  hero IS a LokiHeroCharacter -> REMOVE-only
0x55CCD5B  call 0x0F7EC20 (hero)            FOLD 1 -- stripped, void, return NEVER tested
0x55CCD75  FName("MinionIgnore")  -> op on AActor::Tags at hero+0x1F0     .rdata 0x8B1B5F0
0x55CCD93  hero->SetActorEnableCollision(true)                            [M] 0x339A550
0x55CCD9D  hero->SetPredropHidden(false)                                  [M] 0x5599040, byte hero+0x1BE8
0x55CCDA5  call 0x5586530(hero)                                           REAL, unnamed
0x55CCDAD  mv = hero->GetLokiCharacterMovement()                          [M] 0x55AC8E0
0x55CCDC2    if (mv) { mv->vt[+0x3E0](true); *(float*)(mv+0x1A0) = 1.0f }
0x55CCDE2  this->GetLandingTeleportLocation(&out, hero, LandingActor)     [M] 0x55D89F0, REAL, 963 B
0x55CCDFA  hero->SetActorLocation(&out, false, nullptr, None)             *** THE TELEPORT ***
0x55CCE05  this->MulticastOnPlayerEnteredWorld(PS)                        [M] 0x54537C0
0x55CCE0D  o = call 0x55C6E80(PS); if (o) o->[0xD0] = 1
0x55CCE23  PlayersAttached.Remove(PS)       <- runs on EVERY path past GATE 4
0x55CCE4E  if (PS) call 0x0F7EC20(PS, 3, 0) FOLD 2 -- stripped, void
0x55CCE67  ret
```

### 2.1 THE HANDOFF'S "expect a PARTIAL dismount" WAS TOO PESSIMISTIC

The teleport, the un-hide, the collision restore and the movement restore are **every one a real
body**. The two `0xF7EC20` folds are void side effects whose returns are **never tested**, so neither
gates anything. The partiality is confined to two unnamed void state-changes, one on the hero and one
on the PlayerState — and the flight shows the hero is fully physical afterwards regardless.

`0x54F8DC0` is `IsChildOfUsingStructArray`: a cached `StaticClass()` getter (`0x5395720`, ignores
`rcx`), `hero->ClassPrivate` at `[hero+0x18]`, then `FStructBaseChain` at `UClass+0x38`
(`Array@+0x38`, `Num@+0x40`). The class-name literal it reaches is **`LokiHeroCharacter`** (UTF-16 at
`.rdata 0x899A832`) ⇒ **GATE 6 is `hero->IsA(ALokiHeroCharacter)`**.

`0x339A7A0` is not in the record table (it is a plain engine method, not a UFunction). Its prologue is
`push rbx; sub rsp,0x170; mov rcx,[rcx+0x1B0]; test rcx,rcx; je bail` — it reads
`AActor::RootComponent` at `+0x1B0` and bails if null — and the call site passes
`(actor, &FVector, r8d=0, r9d=0, [rsp+0x20]=0)`, exactly
`AActor::SetActorLocation(const FVector&, bool, FHitResult*, ETeleportType)`. It sits `0x250` bytes
from the confirmed `SetActorEnableCollision` in the same TU. **Grade [I, strong]** — the name is
inferred from shape and neighbourhood, not read from a table. *The flight's outcome does not depend on
the name being right; the hero moved either way.*

---

## 3. THE OBVIOUS SHORTCUT IS DEAD — AND IT WAS CHECKED, NOT ASSUMED [M, strong]

`ULokiRideableComponent` declares `void AuthAddPlayer(ALokiPlayerState)` as member index 0. If it were
real it would replace the entire hand-built append. It is not:

| rideable method | exec thunk | impl | verdict |
|---|---|---|---|
| `AuthAddPlayer` | `0x2C2CE30` (23-way ICF) | **`0x0F7EC20`** | **EMPTY** |
| `AuthRemovePlayer` | `0x2C2CE30` | **`0x0F7EC20`** | **EMPTY** |
| `AuthSetCanJump` | `0x5296F30` | **`0x0F7EC20`** | **EMPTY** |
| `AuthPlayerEnterWorldNew` | `0x5456460` | **`0x0F7EC20`** | EMPTY (already known) |
| `AuthPlayerDetachPlayerFromRidable` | `0x5456100` | `0x55CCCB0` | REAL |
| `AuthPlayerEnterWorld` | `0x54561D0` | `0x55CCE70` | REAL |
| `AuthPlayerEnterWorldAttachedToRidable` | `0x5456380` | `0x55CD510` | REAL (always-fail) |
| `AuthPlayerPreSpawnOnAddToPlane` | `0x5456540` | `0x55CD800` | REAL |
| `ContainsPlayer` | `0x5456700` | `0x55D0270` | REAL |
| `GetLandingTeleportLocation` | `0x5456C80` | `0x55D89F0` | REAL |
| `HasEverContainedPlayer` | `0x5457280` | `0x55DCAA0` | REAL |
| `GetRidePosition` | `0x5457070` | `0x55DAB50` | REAL |

⇒ **the component's empty-stub count is 4, not 1** — every one an `Auth*` mutator, exactly the
`Auth*`-enriched pattern S131's 16,277-record census measured (42.4 % vs 8.30 %, Fisher p = 1.6e-28).
Found independently by the session lead and by recon lane 7.

⚠ Grade: the record table has **no class column**, so the `AuthAddPlayer` / `AuthRemovePlayer` rows are
matched by NAME. Each name occurs **exactly once** in the whole table and `ULokiRideableComponent` is
the only class in `binds_members.csv` declaring either, so this is [M, strong] rather than [M].
Structural corroboration: the rideable exec thunks are emitted **alphabetically** in one contiguous UHT
block (`0x5455F40 AddGameplayEffect` … `0x5457940 SetPlayerDisassociationFromPhase`), and
`AuthAddPlayer` would sort at ~`0x5456050` — where the bytes are real code, not a thunk. Its thunk is
absent from the block **because it was ICF-folded onto the shared one-object-param stub `0x2C2CE30`**,
which is what a stripped impl does.

⇒ **The only reflected writers of `PlayersInside` and `PlayersAttached` do nothing in this client.**
That is *why* both arrays read `Data=0 Num=0 Max=0` in a fully staged world, and why a data poke is
the only route by construction.

---

## 4. THE APPEND, AND WHY THE ABI IS CORRECT BY CONSTRUCTION

Mirrors the wall's own tail at `0x55CD738..0x55CD76A`, instruction for instruction:

```
0x55CD738  movsxd rbx,[r14+0x138]        ; old = Num
0x55CD73F  lea    eax,[rbx+1]
0x55CD742  mov    [r14+0x138], eax       ; Num = old+1        <- INCREMENT FIRST (mirror the game)
0x55CD749  cmp    eax,[r14+0x13c]        ; UNSIGNED (old+1) vs Max
0x55CD750  jbe    0x55CD760              ; <= -> skip the grow
0x55CD752  mov    edx, ebx ; lea rcx,[r14+0x130] ; call 0x00F988D0
0x55CD760  mov    rax,[r14+0x130]        ; RE-READ Data -- it moved
0x55CD767  mov    [rax+rbx*8], rdi       ; Data[old] = PlayerState
```

`0x00F988D0` is `TArray::ResizeGrow(int32 OldNum)` specialised for an **8-byte element with 8-byte
alignment** — both appear as literal `8`s (`0x00F98917 lea rcx,[rax*8]`, `0x00F98934 mov r9d,8`,
`0x00F9892C mov [rsp+0x20],8`) — matching `TArray<ALokiPlayerState*>`. It is the **same function the
wall itself calls on the same array**, so element size and ABI are correct by construction; the buffer
comes from `GMalloc`, which removes the foreign-pointer hazard a hand-supplied buffer would carry.

**Predicted offline, then measured in flight:** with `Data=0 Num=0 Max=0` the `Max==0` branch gives
`eax=4`, `cmova` does not fire (`1 > 4` is false), so `NewMax = 4` and 32 bytes are requested.

```
[DX] append: BEFORE Data=0x0 Num=0 Max=0 ; appending PS=0x24289B3EEF0 at index 0
[DX] append: (old+1)=1 > Max=0 -> calling the GAME'S OWN ResizeGrow at base+0xF988D0(arr=…, OldNum=0)
[DX] append: AFTER Data=0x242177D49E0 Num=1 Max=4 ; readback [0]=0x24289B3EEF0  -> READBACK OK
```

★ On runs 2–4 the log reads **`Max already covers it -> no ResizeGrow needed`** — the buffer run 1
allocated is still live and reused. That is an incidental confirmation that the allocation is the
game's own and persists across the detach's `Remove`.

⚠ **Recon lane 2 and recon lane 3 disagreed on the ordering** — lane 2 proposed deferring the `Num`
publish until after the grow; lane 3 graded increment-before-grow a *functional* precondition [M]. The
adversarial verifier **refuted lane 3's [M]**, and independently so did the session lead: `ResizeGrow`
allocates `max(4, ArrayNum)` or `ArrayNum + 16 + 3*ArrayNum/8`, never exactly `ArrayNum`, so the
+16 slack covers either order. **Both orders work; the shim mirrors the game's, which is what makes
"correct by construction" the argument rather than an assumption.**

---

## 5. THE RECEIPTS, AND ONE TRAP THAT WOULD HAVE MANUFACTURED A FALSE NEGATIVE

### 5.1 `PlayersAttached.Num` is a free, log-free, three-way discriminator [M]

`PlayersAttached.Remove(PS)` at `0x55CCE23` executes on **every path that passes GATE 4**, including
the two that skip the whole hero body. So:

| `Num` after | meaning |
|---|---|
| stays 1 | bailed at GATE 1/2/3/4 |
| drops to 0 | the body **definitively** ran past GATE 4 |
| 0 **and** the hero moved | full dismount |
| 0 **and** the hero did not move | GATE 5 or 6 failed — both are read out BEFORE the call |

Observed **1 → 0 in all four runs**, with GATE 5 and GATE 6 both measured PASS beforehand.

### 5.2 ⚠⚠ `ContainsPlayer` READS THE WRONG ARRAY — do NOT use it as the append receipt [M]

```
0x55D0270  mov rax,[rcx+0x120]      ; PlayersInside.Data
0x55D0277  movsxd rcx,[rcx+0x128]   ; PlayersInside.Num
```

It scans **`PlayersInside` (+0x120)**, not `PlayersAttached` (+0x130). After a correct append it still
reads **false**, and that false is EXPECTED. Reading it as the receipt would have produced a textbook
false negative on a working append. It was disassembled *before* being trusted, and the shim turned
the fact into a **pre-registered prediction** instead — `D2c ContainsPlayer(after append -- MUST still
be false)` — which then confirmed the append had not landed in the wrong array.

### 5.3 The detach is SILENT, and that was predicted from the bytes

**0 log strings in the whole 440-byte extent.** `Loki.log` after four dismounts contains **0**
occurrences of `AuthPlayerDetachPlayerFromRidable`, **0** `failed to get the round game mode`
(we never called the wall), **0** `handing control over to crashpad`, **0** `Fatal`, and 7 `Error`s —
all `LogLibrary: failed to load avatar` / `LogTexture: non-streamed mips`, all at startup line numbers,
none from any arm.
⚠ Honest framing: `LogLokiRideable` occurs **0** times in the whole session, so the log has **no
positive control for that category** here. The silence is *predicted by the disassembly* and *consistent
with* the log; the log alone cannot discriminate "silent" from "suppressed". The disassembly is the
evidence.

### 5.4 A bonus [M] that fell out of the arm design

Runs 1–2 passed `nullptr` (so the detach substituted `[comp+0xB8]` itself at `0x55CCCE5`); runs 3–4
passed the pod **explicitly**. All four behaved identically, and the arm printed
`[comp+0xB8] … = 0x2429580C870 cls=BP_DropPod_Tutorial_C`.
⇒ **`UActorComponent`'s owner really is at `+0xB8`, and the detach's own null-substitution works.**

---

## 6. FLIGHT 2 — ★★★★★ THE LANDING ACTOR IS CONSUMED, AND THE DISMOUNT IS *USABLE*

**Second launch, staged the same way, `dismount-landstart` (`KDXLANDING=2`) injected right after
Route E while the tutorial-start cell was still resident.** The arm enumerated its candidates and
printed the prediction BEFORE the call:

```
[DX] land-cand[0] 0x1651B35D6F0 cls=BP_LokiPlayerStart_C obj=BP_LokiPlayerStart_C_UAID_709CD165B93A7B4E02
                  alive=1 loc=(-3206.4, 5070.5, 100.0)
[DX] land-scan: 1 candidate(s) matching {LokiPlayerStart,PlayerStart,TrainingStart}, 1 GC-alive,
                over 154,919 objects walked
[DX] PRE-REGISTERED PREDICTION: if GetLandingTeleportLocation consumes its LandingLocationActor
     argument, the hero lands NEAR THAT ACTOR, not at the flying pod ... Both are results.
```

At the moment of the call the two hypotheses were **1,488,146 uu apart**:

```
[DX] baseline POD  0x1658781B890 loc=(1428272.5, 5070.5, 20100.0)
[DX] baseline LAND 0x1651B35D6F0 cls=BP_LokiPlayerStart_C loc=(-3206.4, 5070.5, 100.0)
[DX] baseline HERO 'BP_HERO_Ronin_C'  loc=(0.0, 0.0, 13240.0)
[DX] D1 RESULT: hero moved=no (as predicted)          <- the negative control, a fifth time
[DX] D3 ... LandingLocationActor slot[1]@0x8=0x1651B35D6F0 (BP_LokiPlayerStart_C)
[DX] after D3 POD  loc=(1484940.3, 5070.5, 20100.0)
[DX] after D3 HERO loc=(-3206.4, 5070.5, 138.0)
```

⇒ **[M] `GetLandingTeleportLocation` CONSUMES its `LandingLocationActor` argument.** The hero landed
at the PlayerStart, not at the pod — the two were not confusable.

### 6.1 [M] AND THE HERO STAYS THERE — IT IS STANDING ON GROUND

Live RPM, four samples 3 s apart while the pod kept flying:

```
t      hero                                    pod X
+ 0s   (   -3206.4,   5070.5,     90.15)      2,861,188.0
+ 3s   (   -3206.4,   5070.5,     90.15)      2,921,192.2
+ 6s   (   -3206.4,   5070.5,     90.15)      2,981,192.8
+ 9s   (   -3206.4,   5070.5,     90.15)      3,041,193.5

PlayerStart = (-3206.4, 5070.4768061953482, 100.0)
hero        = (-3206.4, 5070.4768061953473,  90.2)
dX = 0.00 uu    dY = 1 ULP    dZ = -9.85 uu
```

The hero settled from the teleport target Z = 138.0 to **Z = 90.15 and stopped** — a capsule dropping
a few uu onto the floor and resting — then held that position **bit-for-bit across 9 s** while the pod
travelled another 180,000 uu. Contrast flight 1, where the same hero fell through
`-117,462 → -121,560` in 4 s because the landing point was over open air.

⇒ **The dismount is not merely "it runs". The hero exits the pod, is un-hidden, gets its collision and
movement back, is placed at a chosen point on real terrain, and stands there.**

★ Method note worth keeping: the discriminator only exists because the arm printed **the pod's live
position beside the hero's in every state sample**. Flight 1 needed an external RPM read to establish
the same thing after the fact. **When the reference is moving, print the reference.**

⚠ What is still unmeasured: the landing point comes from `GetLandingTeleportLocation`, which is 963
bytes and was not transcribed. *That it consumes the actor* is measured; *how* it derives Z (the
-9.85 uu rest offset is the hero's own capsule settling, not necessarily the function's output) is not.

## 6a. THE DISMOUNTED HERO RUNS — and the obvious reading of that is WRONG

With the flight-2 client still up at 1,168 s and the hero standing at the PlayerStart,
`tutorial_launch_play.dll` (the deployed, regression-gated arm, `.text 9bc10a4552c596e1`) was
injected onto it:

```
[PL] teleport hero -> ground (-65,-1770,393)          <-- RM_PLAY's OWN hardcoded teleport
[PL] *** init complete: body=BUILT; camera + WASD active ***
[ANIM] self-driven walk START (so the run anim can be captured with no human at the keyboard)
[ANIM] PlayAnimation(run, loop) ok
```

RPM sampling then found the hero at `(2880.7, -1770.0, 441.2)` — **+2,945.7 uu in +X from `play`'s
own teleport target** — then stationary once the auto-walk window closed.

**✅ [M] A hero that has been through the full dismount is not left in a broken state.** `play`
initialises on it, builds the body, takes the camera, and the hero **runs with real locomotion
animation**. The dismount costs nothing downstream.

**❌ IT DOES NOT SHOW PLAYABILITY AT THE LANDING POINT, and that was my first reading of it.**
`RM_PLAY`'s first act is a hardcoded ground-teleport to
`(KGROUNDX, KGROUNDY, KGROUNDZ) = (-65, -1770, 393)` — S75's known-solid tutorial ground
(`tutorial_launch.cpp:4822-4830`, applied at `:12315`). **It moved the hero off the landing point
before anything else happened.** The experiment that would answer the real question needs a `play`
variant whose teleport is suppressed or retargeted, plus a never-dismounted control — specified in
`docs/next-session-prompt-s133.md` §1, which is written to stop a successor repeating the misread.
⚠ The `[GCW] anim swapping DISABLED` line that follows is the S110 idle-anim GC behaviour
(`KANIMREF` parks the RUN anim, not the idle one) — pre-existing and unrelated to the dismount.

---

## 6a-2. THREE MORE FLIGHTS: A THIRD DISMOUNT, A MEASURED ARM DEFECT, AND A CONTROL THAT KILLED MY OWN EXPERIMENT

Three further launches were spent trying to answer *"is the hero playable AT the landing point?"*.
**The question is still open** — but the attempts produced four results worth more than a rushed answer.

### 6a-2.1 A THIRD DISMOUNT, reproduced [M]
Flight 3 staged cleanly and `dismount-landstart` landed the hero at `(-3206.4, 5070.5, 138.0)` — the
PlayerStart again — with the pod at `X = 1,256,845` at that instant. **Three landings on three
launches**, plus the four calls of flight 1.

### 6a-2.2 ★★★★★ THE CONTROL KILLED THE EXPERIMENT I HAD JUST BUILT
`play-atlanding` = `play` + `-DKNOTELE=1` (a knob that **already existed**; no new code was needed).
It was flown as the **control**, on a hero that had NOT been dismounted:

```
  +  0s  (      0.0,      0.0,   13240.0)      <- KNOTELE=1 works: sp's parked spot, no teleport
  +  6s  (    827.5,      0.0,   13240.0)  MOVED
  +  8s  (   2000.0,      0.0,   13240.0)  MOVED
  + 10s  (   2926.0,      0.0,   13240.0)  MOVED
  + 12s..+30s  unchanged                        <- the 5 s auto-walk window closed
```

**The hero travelled 2,926 uu at CONSTANT Z = 13,240 — in mid-air, with nothing underneath it.**
That is a **hover**, because `KFLYMODE` defaults to **5 = MOVE_Flying**
(`tutorial_launch.cpp:4906-4909`, chosen in S75/S81 precisely to bypass the Walking-mode ground-mantle
chain).

⇒ **`play-atlanding` PASSES 13,240 uu in the air. It is a DEGENERATE control for "is the landing
point playable" — it would have passed anywhere, and I had built it as arm A.** The control caught
that before the arm was ever read as a positive.
⇒ **Only `play-atlanding-walk` (`-DKFLYMODE=1`, MOVE_Walking) can answer the question.**
★ A second corroboration: flight 2's plain-`play` run moved **+2,945.7 uu** and this one **+2,926 uu**
— the distance is a property of the auto-walk driver (~585 uu/s for 5 s), **not of the terrain**.

### 6a-2.3 [M] AN ARM DEFECT, MEASURED — the "REMOVE-only tail" fallback FAULTS
On flight 5 the PlayerState↔hero association had not formed: **both** candidates returned null from
`GetLokiCharacter`, so `GATE5 = 0, GATE6 = 0`. The arm printed that, then **proceeded with cand[0]
anyway**, on the reasoning that the detach would take its REMOVE-only tail and still prove GATE 3+4.
**It did not.** The call faulted:

```
[FLT] CallNative faulted: code=0xC0000005 READ addr=0xFFFFFFFFFFFFFFFF rip=... rva=0x54F8C57
```

`0x54F8C57` is inside the same routine that faulted when the arm probed the bogus PlayerState directly
in flight 1 — i.e. **`GetLokiCharacter` FAULTS on a template PlayerState rather than returning null**,
so GATE 5 is not a clean early-out for a bad argument. **The fallback reasoning was wrong and the
measurement says so.** Fix: when no candidate passes GATE 5, **REFUSE to call**.
★ **The safety design held**: the fault was SEH-caught, the client survived (428 s), and **`D5`
detected the entry the aborted call had left in `PlayersAttached` and removed it** —
`"Num is 1 but was 0 before this arm ... it is removed here"`. The arm cleaned up after its own fault.

### 6a-2.4 Two deaths, both in known classes, neither caused by the dismount
- Flight 3 died during `play-atlanding`'s init with exit code **`0x0000DEAD`** — the protector's own
  `NtTerminateProcess(0xDEAD)` (**FK-32**, mechanism closed by FK-10 at `runtime.dll` RVA `0x80f7f0`).
  It was the **7th injection** into that process. The sitting is **VOID for the playability question,
  not negative** — no `[PL] init complete` was ever printed.
- Flight 4 died during staging with `0xC0000005`, only `gft`+`fo` resident — the **FK-31 staging
  hazard**, this project's dominant tutorial-route failure (~27 %). ★ `crashwatch` DID catch it and
  the launcher archived a 41 MB crashpad minidump to `dumps/crashpad-20260820-143225`.
  ⚠ Its `dump.exe` reads **`.text` 51.8 %** against a healthy **53.0 %**, which looks like a
  refutation of the pre-registered *"a crash-era image holds MORE decrypted `.text`"* prediction —
  **but the comparison is NOT matched**: the crash dump died at 141 s having exercised far less game
  code than a client that had run the whole dismount chain. **It does not test that hypothesis.**

---

## 6b. WHAT THE OFFLINE LANES ADDED, INCLUDING ONE CORRECTION TO THIS DOCUMENT

Seven offline recon lanes ran in parallel with the flights, each adversarially verified by an
independent agent that re-ran the commands rather than checking the prose
(`scratchpad/s132/lanes/`). They agree with the session lead's independent transcription on every
load-bearing claim. Five things they added:

1. ⚠⚠ **CORRECTION TO THIS DOCUMENT AND TO THE FIRST COMMIT MESSAGE: `PlayersAttached` is NOT
   replicated.** [M, lane 4, two disjoint instruments] It carries no `CPF_Net`. The first write-up
   called it "a live component's *replicated* array"; that is wrong, and the correction makes the
   write **safer** than described, not riskier — there is no RepNotify or dirty-marking to skip.
   The rest of the caution stands: it is still a live component's state and an authority-only entry
   point, so it stays a diagnosis rather than a shipping shim.
2. ★★ **`0xF7EC20` is `c2 00 00` = `ret imm16 0` — a VOID no-op. It does NOT zero `eax`.**
   [M, lane 1] The repo's long-standing shorthand *"ret 0"* reads as *"returns zero"*, which is a
   different claim. It is irrelevant here (neither fold's return is tested) but it will mislead a
   future grader reading the fold table.
3. ★★★ **The game cannot produce a dismount on its own ⇒ every observable this arm reads is at
   a structural baseline of 0**, so nothing measured here can be background activity. The detach's
   caller is `ALokiDropPod::KickPlayersFromPod`, whose entire body sits behind
   `if (LokiIsClient) return;` with `LokiIsClient` hardcoded TRUE on this client.
   ⚠⚠ **Grade [M, bounded], not [M].** Lane 1 stated *"exactly ONE game caller"* as [M] and its
   own adversarial verifier **REFUTED that**: `KickPlayersFromPod`'s bytecode carries **TWO**
   `CALLSYS AuthPlayerDetachPlayerFromRidable` sites (`0x01D8`, `0x02EC`) and the uncapped rel32 scan
   found only the second — because the first sits in an AOT body on page `0x5969000`, which is
   **all-zero in 30 of 30 same-size images on disk**.
   ★★ **The general rule, demonstrated from INSIDE the result: a rel32 scan over a 55 %-decrypted
   `.text` is a FLOOR, always** — and it cannot see a reflected/Blueprint caller at all, since that
   route reaches the thunk through `UFunction.Func` at runtime.
   ★ **What actually carries the baseline claim** (added by the verifier, not the lane): a
   full-image qword scan finds **exactly one** stored pointer to the impl and one to the thunk, ruling
   out statically-stored indirect calls; and a corpus grep for the name over the shipped assets returns
   **zero** files **with a passing positive control** (`BulkClaimAllProgressionTrackRewards` →
   `WBP_UI_LobbyRewards`). Both bytecode sites are inside the same dead function, so the conclusion
   stands — only its support changed.
4. ★ **`TArray::Remove` (`0x11F3860`) writes ONLY `Num`** [M, lane 1] — it does not touch `Data`
   or `Max`, does not free and does not realloc. That is the mechanism behind the flight observation
   that runs 2–4 printed `Max already covers it -> no ResizeGrow needed`: the run-1 buffer survives
   the detach untouched. It also means **a poked buffer is never freed by this function.**
5. ⚠ **A crash hazard that did not fire, and is still worth recording** [M, lane 1]: `0x5586530`
   — called unconditionally on the hero — dereferences `hero+0x460`, `hero+0x1978` and
   `hero+0x1980` with **no null checks**. It survived all five calls on the staged `BP_HERO_Ronin_C`,
   so it is empirically safe on that hero; a differently-configured hero could fault. Read the three
   pointers before arming if the hero is not the standard staged one.

★ Lane 4 also confirmed, by two disjoint instruments each, every offset the arm uses:
`PlayersInsideCount @0x11C` · `PlayersInside @0x120` · `PlayersAttached @0x130/0x138/0x13C` ·
`bCanExit @0x118` · `OnPlayersInsideCountChanged @0xE0` · inner type = `ObjectProperty`, pointer
size 8 (four independent routes) · and `AActor::bHidden` → offset `0x68` mask `0x80`,
`bAlwaysRelevant` → offset `0x68` mask `0x08`, **exactly** as the handoff predicted.
⚠ But lane 4 also refutes the handoff's *implementation* of that control: **`FBoolPropertyParams`
carries no `ByteOffset`/`ByteMask`/`FieldMask` fields at all** — the engine derives them at runtime
by calling the record's `SetBitFunc` on a zeroed buffer. A decoder written against the assumed field
list would read padding. The shim reads **live `FBoolProperty` objects** (`+0x70..+0x73`), which is
the correct route, so the control is buildable — just not from the `.rdata` records.
⚠ And `ALokiDropPod::LokiRideable @0x6C8` is a **Blueprint-generated component property**, neither
UHT nor Angelscript, so **no offline instrument can produce its offset** — it must be resolved by
name on the live class, which is what the arm does.

---

## 7. WHAT IS STILL OPEN

- ✅ **CLOSED BY FLIGHT 2 (§6): `GetLandingTeleportLocation` DOES consume its
  `LandingLocationActor` argument, and the hero lands on real terrain and stays there.** The
  flight-1 attempt is preserved below because the *way* it failed is the useful part.
- ⚠ **Flight 1: the discrimination could not be run and was UNAVAILABLE, not negative.** The arm
  was built to pass a `LokiPlayerStart` actor instead of the pod, to test whether
  `GetLandingTeleportLocation` actually consumes its `LandingLocationActor` argument. By the time it
  flew, an enumerating scan reported **`0 candidates matching {LokiPlayerStart, PlayerStart,
  TrainingStart}, 0 GC-alive, over 143,130 objects walked`** — the tutorial-start cell had streamed out
  (the `dropplane_b1only` marker scan *had* found `BP_LokiPlayerStart_C_UAID_709CD165B93A7B4E02` at
  uptime ~250 s). **The arm refused to substitute silently and said so.** Re-run it EARLY in the next
  armed window, before the pod flies the origin cell out of memory.
  ★ **The natural better experiment: call the detach IMMEDIATELY after Route E**, while the pod is
  still over the island — then the hero should land on real terrain and stay there.
- The two `0xF7EC20` folds (one on the hero right after the `IsA` gate, one on the PlayerState with
  `dl=3`) are **unnamed**. `0xF7EC20` has ~165,789 call sites, so the address identifies nothing.
- `0x5586530(hero)` is REAL and unnamed (reads `hero+0x460`, then a `minsd`/`cvtsd2ss` on a vector at
  `+0x240` — capsule-ish geometry).
- `AuthPlayerEnterWorld` (`0x55CCE70`) is **FORECLOSED** as an alternative route — recon lane 7 [M]:
  its two terminal actions are direct calls to the stripped `0xF7EB50`, and it performs **zero writes
  to any actor or component transform**. Satisfying its `PlayersInside` guard with a poke would move
  execution past the guards and change nothing about where the hero is.
- **This is a diagnosis, not a shipping fix.** It writes a live component's state array by hand
  and drives an authority-only entry point. Do not add it to the default shim set.

---

## 8. HOW IT WAS FLOWN (reproduce exactly)

```
forceTutorialMatch = true ; go build -C server -o ags.exe ./cmd/ags     (set back to false after)
.\configs\launch-redirect.ps1 -NoHook
.\configs\fk24-stage.ps1 -Probe "tools\sigbypass-mod\build\tutorial_launch_dropplane_b1only.dll" -Label s132 -AllowStale
tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_droppod_pe_cdopoke.dll
tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_dismount.dll
```

⚠ `-AllowStale` is required (the deployed staging pair `fo fa184b20934cc4b0` / `sp 4285c0dd22ae9976`
in `tools/sigbypass-mod/` is intentionally older than `build/`).
⚠ The stager's `-Probe` path must be `tools\sigbypass-mod\build\…`, not `build\…`.

**Staging worked on launch 1**: world loaded 9 s after `fo`, `[SP] done step=4` 12 s after `sp`,
`DropShip 0 → 1`, `DropPod 2 → 4`, `SpawnDropPodForTeam` returned **true**. One launch, one armed
window, four dismounts.

### Builds (`.text` sha256 — diff the hash, never the size)

| variant | `.text` | note |
|---|---|---|
| `dismount` | `53483e6181bb3583` | **at HEAD** (127,488 B) |
| `dismount` | `03d807ab6d397537` | **THE FLIGHT-1 ARTIFACT** (126,976 B) — the four runs in §1. Reproduce from commit `c2cdc56`; the only difference is the pod/landing-actor lines §6 added to `DxState`. |
| `dismount-landstart` | `0d5fa554edac53c5` | **THE FLIGHT-2 ARTIFACT** (129,024 B) — `KDXLANDING=2`, §6 |
| `dismount-readonly` | `16c00d0a16e5b496` | resolve + gates + D0c + D1 only; writes nothing |
| `dismount-appendonly` | `b3b932579a8a6c07` | append, do not call the detach |
| `dismount-podland` | `6019eb5fb1122617` | pass the pod explicitly |

⚠ `dismount` and `dismount-podland` shared a `.text` **size** of 126,976 B before the §6 edit —
**diff the hash, never the size** (the S131 lesson; the `dismount-readonly` / `-appendonly` hashes
above predate the same edit and will move on a rebuild, which is why the two FLOWN artifacts are
pinned to a commit rather than to "whatever `build/` holds").

**Regression gates, re-verified after EVERY edit including the §6 one:** `play` `9bc10a4552c596e1` ·
`dropplane_b1only` `5b4467b0105dec1a` · `droppod-pe-cdopoke` `249a3cd2190eb334` — all three MATCH.
★ And at commit `c2cdc56` `dismount` was **byte-identical to the artifact that produced all four
flight-1 results even after the `KDXLANDING=2` code was added**, i.e. that path is fully
dead-code-eliminated at `KDXLANDING==0`. The later `DxState` print is what moved it.

`VirtualAlloc`, `VirtualFree` and `FlushInstructionCache` are **absent** from `dismount`'s import
table, exactly as they are from the deployed `play` — the S112 no-`.text`-write check.
⚠ `VirtualProtect` IS present in both, including the deployed `play`, so **it does not discriminate**;
do not cite it.

---

## 9. INSTRUMENT ARTIFACTS ADDED THIS SESSION

1. ⚠⚠ **`usmapdump dumpimage` printed `ERROR: process "SUPERVIVE-Win64-Shipping" not found (is the
   game running?)` while the client was demonstrably alive at 650 s.** It needs the **`.exe` suffix**.
   Given a bare PID it instead prints `module "48356" not found in PID 48356`. Both messages read as
   *the game is dead*. **Check `Get-Process` before believing either.**
2. ⚠ **The session lead subtracted the image base BY HAND** and got 7 of 21 call targets wrong (the
   error appears whenever the third hex digit rolls past `af`: `0x7FF6B239A550` read as `0x239A550`,
   correct `0x339A550`). Every wrong RVA disassembled into *plausible mid-function garbage* and every
   record-table lookup on one returned `None` — which reads exactly like "not a reflected function".
   The project's own rule *"recompute, never retype an RVA"* was broken in the first ten minutes. It
   cost nothing only because the lookup returned an obviously-wrong all-`None` column.
   ★ **A verifier caught recon lane 3 doing the same thing** — it printed a rel32 decode
   (`0xFB9CB170` → "-73,895,568"; the true value is -73,617,040) whose arithmetic gives the wrong
   address, under a header claiming every address was machine-computed. The conclusion was right and
   the shown work was false.
3. ⚠ **A one-line PowerShell summary regex printed `ERROR` for five builds that all succeeded**
   (`1 built, 0 failed` in each). An analysis one-liner is an instrument too — the S131 `pod_verdict.py`
   lesson, recommitted the same day it was read.
4. ⚠ **The first landing-actor arm conflated "no such actor" with "found one but it failed
   `GcAlive`"** in a single message. Rewritten to enumerate and print candidates with a scanned-object
   denominator — which is what turned an ambiguous null into the clean, quantified negative in §6.
   ★ The suspicion that `FindInstByClass`'s substring match was at fault (the recorded class-lookup
   blind-spot family) was **WRONG**: the enumerating version confirmed the actor is genuinely absent.
   Checking beat "fixing" a helper that was working.
5. ⚠ **The Bash-tool heredoc silently collapses one level of backslashes**, so `"\\r\\n"` inside a
   Python patch script became a REAL CR/LF inside a C string literal three times, producing
   `error: expected expression`. Write patch scripts to a FILE and run the file.
