# S132 (2026-08-20) — THE DROP-POD DISMOUNT RUNS. The hero leaves the pod and is placed on the ground.

**One line: appending the PlayerState to `PlayersAttached` with the game's own `ResizeGrow` and then
calling `AuthPlayerDetachPlayerFromRidable` teleports the hero to the pod's live position, restores its
collision, un-hides it and hands it back to the movement component — reproduced FOUR times against a
target moving at 20,000 uu/s, on ONE launch, with a within-run negative control that never moved it.**

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

## 6. WHAT IS STILL OPEN

- ⛔ **The landing-actor discrimination could not be run and is UNAVAILABLE, not negative.** The arm
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
- **This is a diagnosis, not a shipping fix.** It writes a live component's replicated array by hand
  and drives an authority-only entry point. Do not add it to the default shim set.

---

## 7. HOW IT WAS FLOWN (reproduce exactly)

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
| `dismount` | `03d807ab6d397537` | **the flown arm** (126,976 B) |
| `dismount-landstart` | rebuilt this session | KDXLANDING=2, the landing-actor discriminator (unflown as designed — see §6) |
| `dismount-readonly` | `16c00d0a16e5b496` | resolve + gates + D0c + D1 only; writes nothing |
| `dismount-appendonly` | `b3b932579a8a6c07` | append, do not call the detach |
| `dismount-podland` | `6019eb5fb1122617` | pass the pod explicitly (⚠ same 126,976 B size as `dismount`) |

**Regression gates, all MATCH after every edit:** `play` `9bc10a4552c596e1` ·
`dropplane_b1only` `5b4467b0105dec1a` · `droppod-pe-cdopoke` `249a3cd2190eb334` · and `dismount`
itself is **byte-identical to the artifact that produced all four results** after the `KDXLANDING=2`
code was added, i.e. the new path is fully dead-code-eliminated at `KDXLANDING==0`.

`VirtualAlloc`, `VirtualFree` and `FlushInstructionCache` are **absent** from `dismount`'s import
table, exactly as they are from the deployed `play` — the S112 no-`.text`-write check.
⚠ `VirtualProtect` IS present in both, including the deployed `play`, so **it does not discriminate**;
do not cite it.

---

## 8. INSTRUMENT ARTIFACTS ADDED THIS SESSION

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
