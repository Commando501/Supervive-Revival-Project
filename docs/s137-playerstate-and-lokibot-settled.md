# S137 (2026-08-21) — THE AI PAWN GETS A PLAYERSTATE, AND A **LOKI BOT CONTROLLER** EXISTS

**One line: the handoff's proposed fix — a `bWantsPlayerState` CDO poke — is MEASURED REFUTED, and
two other routes flown in the same window worked instead: `AController::InitPlayerState` called
directly gives the AI controller a real `BP_LokiPlayerState_C`, `APawn::SetPlayerState` links the
pawn, and one pointer on the engine `APawn` CDO makes `SpawnDefaultController` build an
`ALokiBotController` — the first `BotController`-derived object in this project's history.**

Three injections into ONE client, one staged tutorial world, no relaunch between them. Zero `.text`
writes, zero PI hooks. Client died at the end by protector kill (`0x0000DEAD`, FK-32) **after every
result was captured** — see §8.

---

## ⚠⚠ CORRECTIONS BLOCK — THIS GOVERNS THE REST OF THE FILE

**C1. THE HANDOFF'S HEADLINE ARM IS REFUTED, NOT CONFIRMED.**
`docs/next-session-prompt-s137.md` §1.2 proposed *"poke `CDO(<pawn's AIControllerClass>) + 0x488 |=
0x20` before spawning"* and called it "one aligned CDO write … the same risk class as S130's
`bCanEverReplicate`". **It does not work.** The poke lands on the CDO (readback OK, dword delta
exactly `0x20`) and the spawned controller still reads the bit **CLEAR**. Measured with a within-run
control: two spawns, milliseconds apart, same world, same instrument, the CDO bit the only
difference. See §3.

**C2. THE HANDOFF SAYS "THE BLOCKER" (SINGULAR). THERE ARE THREE GATES — AND ONE WAS LOST IN
COMPRESSION, NOT NEVER FOUND.** `AAIController::PostInitializeComponents` is stock UE's
`if (bWantsPlayerState && !IsPendingKillPending() && GetNetMode() != NM_Client)`.
⚠⚠ **CORRECTION TO MY OWN FIRST DRAFT OF THIS BLOCK**, caught by an adversarial pass: I wrote
*"Gates 2 and 3 were never recorded."* **That is false for gate 3.**
`docs/s136-ai-controller-settled.md:524` records it verbatim —
`0x45D6D36  call 0x338E750 ; cmp eax,3 ; je   ; != NM_Client` — inside that very listing.
What is true, and is the more useful finding:
  * **gate 2** (`ObjectFlags(+0x0C)>>30`, `RF_Garbage`, `0x45D6D27`–`0x45D6D31`) appears in **neither**
    the S136 settled doc nor the S137 handoff — genuinely never recorded;
  * **gate 3 was recorded in the settled doc and DROPPED when it was compressed into
    `docs/next-session-prompt-s137.md`**, whose listing jumps straight from `0x45D6D25` to `0x45D6D46`.
⇒ **the digest is the instrument that lost it.** That is this project's own "a digest is an
instrument" pattern (S115-d), operating one level down: settled doc → handoff. A successor reading
only the handoff — which is what a handoff is FOR — could not have known to check either gate.
Both are read out by the arm. See §2.

**C3. "gates 2 and 3 are already known to hold" WAS [I], NOT [M] — and S137 UPGRADES ONE OF THEM.**
An adversarial pass caught this: the project's existing netmode measurement is
`APawn::SpawnDefaultController`'s early-out, which calls `GetNetMode()` **on the PAWN**; gate 3 calls
it **on the CONTROLLER**. Different object. **S137 settles it anyway from a different direction:**
`AController::InitPlayerState`'s own first branch is the same `GetNetMode() != NM_Client` guard on
the CONTROLLER, and ARM B ran to completion three times ⇒ **[M] `GetNetMode() != NM_Client` on a
controller.** Gate 2 was read out live and printed `passes` on every spawn.

**C4. `obj_by_chain =BotController` IS A DEGENERATE QUERY AND IT READS 0 EVEN WITH A LIVE BOT.**
No class in this hierarchy is *named* `BotController` — the Loki class is `ALokiBotController`
(UHT-stripped to `LokiBotController`) and its ancestors are `LokiAIController` / `AIController` /
`Controller`. Measured live, with a `LokiBotController` possessing a pawn in that very process:
`=BotController` → **`found 0`, and `CDOs matched and EXCLUDED: 0`** — i.e. it had **no positive
control either**. `=LokiBotController` → `found 1`. The `'='` exact form that `obj_by_chain.py`'s own
header tells you to PREFER is the wrong instrument for this question.
⇒ **CLAUDE.md records `[M] obj_by_chain BotController = 0 LIVE (the CDO is present as a passing
search-term control)`.** The *conclusion* was right for S136 — no bot controller existed then — but
in the `=BotController` form the stated positive control cannot have passed. Re-derive before
re-quoting. My own `playerstate_readout.py` shipped the same defect and has been fixed.

**C5. THE `62 vs 69` FOLD-SLOT "DISCREPANCY" IS NOT A DISCREPANCY.** A lane reported CLAUDE.md's
*"AController's own vtable: 62 of 289 fold slots"* as failing to reproduce (it measured 69). The
adversarial pass resolved it with one line of arithmetic: the per-fold breakdown is
void(`0xF7EC20`)=42, false(`0xF7EB60`)=17, true(`0xB9E1F0`)=7, null(`0xF7EB50`)=3, 0.0f=0.
**42+17+3 = 62 under the FOUR-fold set; +7 = 69 under the FIVE-fold set.** Both numbers are correct;
they differ only in whether `0xB9E1F0` counts. **Quote the fold set with the number.**

**C6. AN EVIDENCE FILE WAS DESTROYED BY MY OWN CARELESSNESS.** `docs/s137-external-AFTER-flight3.txt`
was clobbered by re-running the probe with `| tee` after the client had died, overwriting the real
capture with `RUN IS VOID`. It has been rewritten as a clearly-labelled transcript reconstruction.
**Do not `tee` over an evidence file.** The headline does not rest on it — the in-shim marker and the
independent `obj_by_chain` run both stand.

**C7. `TerminateProcess` / `ExitProcess` ARE IN EVERY SHIM'S IMPORT TABLE.** CLAUDE.md supports
"`0xDEAD` is not ours" with *"no `TerminateProcess`/`ExitProcess` in any shim source"*. True of the
SOURCE (0 occurrences), but **both names are present in the import table of every `tutorial_launch`
DLL**, including the long-flown `play` and `dismount`. They come from the clang/link.exe scaffolding.
The conclusion is unaffected — and is strengthened, since arms that never produced `0xDEAD` carry
them too — but a successor re-deriving it from the binary will find them and must not be misled.

---

## 0. WHAT WAS FLOWN

| flight | arm | `.text` RAW | result |
|---|---|---|---|
| 1 | `botps` | `445fb5ce5b902bc3` | ARM A **REFUTED**; ARM B **WORKED** |
| 2 | `botps-link` | `e287d7ae8c5f4814` | ARM B reproduced; ARM C **WORKED** — pawn side linked |
| 3 | `lokibot` | `3119d75ae2ca1859` | ARM D **WORKED** — A-B-A; a `LokiBotController` possesses a hero |

Regression gate `botai` = **`5e47c13cf7f0a158`**, unchanged across all three source patches (every
edit sits behind `#if KBSPS`). All five/six arms carry **distinct** digests — none is a degenerate
control arm byte-identical to its treatment, a hazard this repo has recorded three times.

**Pre-flight static check (the S135→S136 lesson).** Every arm was byte-scanned for the long banner
strings that exist only inside the branches it should contain, with a positive control in every row
and the *old* single-spawn path required ABSENT. 10/10 then 8/8 rows matched. `verify_dll.py`: PASS;
`WriteProcessMemory` / `FlushInstructionCache` / `VirtualAlloc` all ABSENT. (`VirtualProtect` IS
imported — other run modes in the same TU use it — so the S112 import-absence signature is
suggestive here, not proof; the no-`.text`-write property rests on the source path.)

---

## 1. THE GATE, RE-DERIVED INDEPENDENTLY

From `dumps/merged12.dump.exe` (ImageBase `0x7FF6AF000000`, file offset == RVA):

```
AAIController::PostInitializeComponents  0x45D6D10   REAL, 264 B, 0x45D6D10..0x45D6E18
  0x45D6D19  e8 e2 c2 10 ff             call 0x36E3000    Super::PostInitializeComponents
  0x45D6D1E  f6 83 88 04 00 00 20       test byte [rbx+0x488],0x20   <- bWantsPlayerState
  0x45D6D25  74 25                      je   0x45D6D4C    <== GATE 1
  0x45D6D27  8b 43 0c / c1 e8 1e / f6 d0 / a8 01
  0x45D6D31  74 19                      je   0x45D6D4C    <== GATE 2  !IsPendingKillPending()
  0x45D6D36  e8 15 7a db fe             call 0x338E750    AActor::GetNetMode
  0x45D6D3B  83 f8 03 / 74 0c           je   0x45D6D4C    <== GATE 3  bail if NM_Client(3)
  0x45D6D40  48 8b 03 / 48 8b cb
  0x45D6D46  ff 90 88 08 00 00          call [rax+0x888]  InitPlayerState, slot 0x888/8 = 273
  0x45D6D4C  48 83 bb 98 04 00 00 00    cmp [rbx+0x498],0 <- the je TARGET is the BrainComponent test
```
GATE 2 reads `ObjectFlags` (+0x0C **in this build**) `>> 30`; bit 30 is `RF_Garbage`. The `je` target
is the BrainComponent test, so **the skipped block is the InitPlayerState call and nothing else.**

**The bit is named, not guessed** [M]: the one UHT `FBoolPropertyParams` record whose type-func slot
points at `0x45CFA10` sits at `.rdata 0x842D210` and carries NameUTF8 **`bWantsPlayerState`**; it is
slot 5 of the 15-entry PropPointers array owned by the `FClassParams` whose `ClassNoRegisterFunc`
names `AAIController` in `/Script/AIModule`. PropertyFlags `0x0010000000000005`
(`CPF_Edit|CPF_BlueprintVisible|CPF_NativeAccessSpecifierPublic`). Setter bytes:
`0x45CFA10 = 83 89 88 04 00 00 20 c3`, control `0x45CFA20` writing `0x40` at the same offset.
`+0x488` is inside **AAIController's** own layout (`sizeof(AController)=0x450`,
`sizeof(AAIController)=0x4E0`).

⚠ **A SECOND READER of bit 0x20 exists at `0x45D5E55`** (inside function `0x45D5DD0`), found by
adversarial review and **not** in the handoff. Moot for S137 because ARM A was abandoned, but any
future arm that sets this bit is moving **two** behaviours.

---

## 2. THE OFFSETS — ALL EIGHT, TWO INSTRUMENTS EACH, CROSS-IMAGE CONTROL

`AController::PlayerState +0x3C0` · `APawn::PlayerState +0x3D8` · `APawn::AIControllerClass +0x3D0` ·
`UClass::ClassDefaultObject +0x178` · `AGameModeBase::PlayerStateClass +0x3E0` ·
`UWorld::AuthorityGameMode +0x250` (control `UWorld::GameState +0x258`) · `APawn::Controller +0x400` ·
`AAIController` bitfield dword `+0x488`, `bWantsPlayerState` mask `0x20`.

An adversarial re-derivation with an independently written PE reader + UHT walker **could not refute
any of the eight**, and every value reproduced bit-identically in a second image at a different
ImageBase. **The arm resolves all of them BY NAME at runtime anyway and prints the recorded value
beside each as a cross-check** — every line in every flight marker reads `[offset AGREES]`.

★ **`UWorld::AuthorityGameMode @ +0x250` gets a third independent confirmation here**, from inside
`AController::InitPlayerState` itself (`0x36DEE77 mov rsi,[rax+0x250]`), with `GameState @ +0x258` as
the in-function control (`0x36DEE83`).

---

## 3. ARM A — THE HANDOFF'S FIX. **REFUTED.**

Flight 1, within-run, single-variable: spawn #1 with the CDO bit CLEAR, poke, spawn #2 with it SET.

```
[PS] CDO bWantsPlayerState (L1 baseline) = clear
[PS] POKE SET   CDO=0x173B3C8D0B0 byte@+0x488: 0x4A -> 0x6A (wanted 0x6A)  READBACK OK
[PS]      dword@+0x488: 0x0000004A -> 0x0000006A   (delta 0x00000020 -- expect exactly bit 0x20)
[PS] TREATMENT   ctl.bWantsPlayerState (L2) = clear   [dword@+0x488=0x0000004A]
[PS] TREATMENT   ctl.PlayerState       (L3) = 0x0   NULL
```
The poke landed and moved exactly one bit. **The spawned instance still reads `0x4A`.**

★★ **AND AN OFFLINE LANE PREDICTED THIS BEFORE THE FLIGHT, WITH THE MECHANISM.** The ORDER is fine
and measured — `StaticConstructObject_Internal` calls the class constructor at `0x13740CD` and the
`~FObjectInitializer` (the only route to `PostConstructInit` → `FObjectInitializer::InitProperties`)
8 bytes later at `0x13740D5`, so a CDO→instance copy really does run after the ctor. **The CONTENT is
wrong:** when the archetype IS the class's CDO — exactly the case for `SpawnDefaultController`, which
passes no SpawnParameters Template — `InitProperties` branches at `0x1368231` into the
**PostConstructLink** chain only, and `UStruct::Link` (`0x1226C80`) only puts a property into
PostConstructLink if it is **NOT owned by a native/intrinsic class**. `bWantsPlayerState` is owned by
`AAIController`, which is native. **There is no bulk memcpy of the CDO onto a new instance anywhere on
the allocation path.**

⇒ **The prediction and the measurement agree. This is a reusable rule, not a one-off:**
> **A CDO poke reaches a new instance only if the CONSUMER reads the CDO directly. It does NOT
> propagate through `InitProperties` for a property owned by a native class.**

⚠ **S130's `bCanEverReplicate` precedent never established otherwise** — its consumer read the CDO
*directly* (`cmp byte [CDO+0x6C],0`). The handoff generalised that precedent to a case it does not
cover. **§5 is the same idea applied correctly, and it works.**

---

## 4. ARM B — DIRECT `InitPlayerState`. **WORKS. Reproduced 3×.**

[M] re-derived here: `AController::InitPlayerState` (`0x36DEE20`, REAL, 778 B, all callees REAL, zero
folds) **does not test `bWantsPlayerState`** — zero references to `[reg+0x488]` in its 180
instructions. Its own guards are only `GetNetMode() != NM_Client` and `GetWorld() != null`, then
`[World+0x250] AuthorityGameMode` with a `[World+0x258] GameState → GetDefaultGameMode()` **fallback**,
then `SpawnInfo.ObjectFlags |= RF_Transient` (`0x36DEED3 or dword [rsp+0x84],0x40`).

Dispatched **through the vtable** and **refused unless `[[ctl]+0x888]` resolves to RVA `0x36DEE20`** —
not ceremony: [M] `ALokiPlayerController`'s slot 273 is the void fold, so "slot 273" is not
universally real.

```
[PS] ARM B: vtable=0x7FF7C0DD1398  slot[+0x888]=0x7FF7BC07EE20  rva=0x36DEE20  (expected 0x36DEE20)
[PS] ARM-B  ctl.PlayerState (L3) @0x3C0 = 0x1756C561120  *** NON-NULL ***
[PS] ARM-B    >> PlayerState 0x1756C561120 'BP_LokiPlayerState_C'
[PS] ARM-B       chain=BP_LokiPlayerState_C<-LokiPlayerState<-PlayerState<-Info<-LokiActor<-Actor<-Object  alive=1
```
A **real `BP_LokiPlayerState_C`**, not a bare engine `APlayerState`.
★ **PlayerArray registration is automatic** — `APlayerState::PostInitializeComponents` calls
`AGameStateBase::AddPlayerState`. Nothing extra is needed.
⚠ Risk class: **NOT call-only.** It does a `SpawnActor` (RF_Transient) and writes `controller+0x3C0`.

---

## 5. ARM C — LINK THE PAWN. **WORKS.**

ARM B leaves `pawn+0x3D8` NULL, **and that is correct, not a bug**: on the possession path the
controller→pawn copy is `APawn::SetPlayerState` **inlined into `APawn::PossessedBy`**
(`0x3BB1C64` reads `[Controller+0x3C0]`, `0x3BB1CD5` writes `[pawn+0x3D8]`), and possession has
already happened. Nothing re-runs it. **This was PRE-REGISTERED as ARM B's signature and it held.**

`APawn::SetPlayerState` `0x3BBD9F0` is REAL, 210 B, **NON-VIRTUAL**, `void __fastcall(APawn*,
APlayerState*)` — so there is no vtable slot to validate against, and the arm substitutes a
**16-byte prologue signature check** and refuses on mismatch.

```
[PS] ARM C: target=0x7FF7BC55D9F0 rva=0x3BBD9F0 prologue=48 89 5C 24 08 ... 57 -> SIGNATURE MATCHES
[PS] ARM-C  pawn.PlayerState (L4) @0x3D8 = 0x1751AA18890  *** NON-NULL ***
[PS] ARM-C  ctl.PlayerState  (L3) @0x3C0 = 0x1751AA18890  *** NON-NULL ***
```
External instrument: `HANDSHAKE: pawn.Controller == this controller` /
`PLAYERSTATE MATCH: pawn.PlayerState == controller.PlayerState` — **the identical shape the player's
own possession prints in the same output**, which is the positive control for the whole readout.

---

## 6. ★★★★★ ARM D — A **LOKI BOT CONTROLLER**, VIA ONE POINTER

`APawn::SpawnDefaultController` hands `SpawnActor` the **pawn instance's** `AIControllerClass` read
from `[pawn+0x3D0]` at the call site [M]. And `APawn::APawn` writes that field from a CDO it reads
**by hand**:
```
0x3B80A08  lea rsi,[rdi+0x3d0]      rsi = &pawn->AIControllerClass
0x3B80BD3  call 0x3BA4CE0           a lazy StaticClass() singleton
0x3B80BF3  mov rbx,[rbx+0x178]      rbx = ThatClass->ClassDefaultObject
0x3B80C0D  mov rax,[rbx+0x3d0]      <-- reads AIControllerClass OFF THE CDO
0x3B80C14  mov [rsi],rax
```
**Which CDO, measured live before the arm was built:** `Default__Pawn+0x3D0` = `0x173B5191280`
`'AIController'` — exactly the UClass every spawned pawn was observed carrying.

⇒ **This is the S130 shape (consumer reads the CDO directly), not the ARM-A shape.** Same idea,
opposite outcome, and *the difference is who reads the CDO.*

**A-B-A, three spawns, and the third is what makes the restore a measurement:**
```
ARM D A-baseline   pawn.AIControllerClass=0x173B5191280 'AIController'
                   controller class='AIController'        BotController-chain=no
                   chain=AIController<-Controller<-LokiActor<-Actor<-Object
ARM D B-treatment  pawn.AIControllerClass=0x173B8595100 'LokiBotController'
                   controller class='LokiBotController'   BotController-chain=*** YES ***
                   chain=LokiBotController<-LokiAIController<-AIController<-Controller<-LokiActor<-Actor<-Object
ARM D C-reversal   pawn.AIControllerClass=0x173B5191280 'AIController'
                   controller class='AIController'        BotController-chain=no
spawns=3 pokeOK=1 restoreOK=1
```
**All six pre-registered predictions (D1–D6) hit.** Then ARM B + ARM C ran **on the bot controller**:
`ctl.PlayerState = 0x173B8D90010 'BP_LokiPlayerState_C'`, `pawn.PlayerState` the same pointer.

**Independent external confirmation** (`obj_by_chain.py`, separately written, run as its own command):
```
found 1 LIVE (non-CDO) instance whose CLASS CHAIN contains '=LokiBotController':
  obj=0x17443C931A0  Class=LokiBotController  Name=LokiBotController  Outer=PersistentLevel
```
**the same pointer the shim reported.** Two independently written instruments, one object.

⚠ **SCOPE: this pokes the ENGINE `APawn` CDO**, so while it stands every newly constructed pawn
process-wide inherits it. The window is poke → one spawn → restore, and spawn C is the check that the
window really closed. **Not a shipping fix.**
⚠ **STILL NOT A COMPLETE BOT.** `ServerSetHeroClass` / `SetPlayerTeam` remain stripped folds
(`0x556DE43 → 0xF7EC20`, `0x556DE53 → 0xF7EB60`), and nothing here went through `SpawnBot`. What
exists is *an `ALokiBotController` possessing a hero pawn, with a PlayerState on both sides.*

---

## 7. ★★★★ FREE BY-PRODUCTS

**(a) DRIVING THE PATH DECRYPTED THE LOKI BOT CODE — the S118 steerable-decryption method.**
| function | merged12 | after S137 | |
|---|---|---|---|
| `ALokiBotController::OnPossess 0x5565470` | 0/4096 | **3782/4096** | ★ DARK → LIT |
| `ALokiBotController::Tick 0x556E9F0` | 0/4096 | **3509/4096** | ★ DARK → LIT |
| `ALokiBotController::OnUnPossess 0x55667F0` | 0/4096 | 0/4096 | never unpossessed — correct negative |
| ctor `0x554B430` / `InitPlayerState` / `SetPlayerState` | lit | lit | controls, unchanged |

`OnPossess` was named by an offline lane as *"the natural home of the Blackboard / BehaviorTree /
Perception wiring that separates an AI-controlled pawn from a Loki bot"* and flagged
**COVERAGE-BLOCKED with no way to read it**. It is now readable offline, forever.
`Tick` being lit means **the bot controller was actually ticking.**
Banked: `dumps/s137-lokibot/` and merged to **`dumps/merged13.dump.exe`**.
⚠ **QUOTE THE RIGHT DELTA.** `mergedumps` reported taking **44 pages from donors**; the honest
number against the previous canonical image is **+28 pages** (verified strict superset vs
`merged12`: pages lost **0**, gained **28**, byte conflicts on shared pages **0**;
16,772 → **16,800 / 30,281 = 55.48 %**). The two numbers measure different things and only the
second is a coverage claim.

**(b) ★★★★★ THE NETMODE QUESTION IS ANSWERED, AND IT WAS IN EVERY LOG ALL ALONG.**
The repo records this open item twice (`CLAUDE.md`, `docs/fk22-dropphase-reachability.md`):
*"`!= NM_Client` is MEASURED; WHICH mode it is (Standalone 0 / ListenServer 2) is NOT … One read
settles it, and if it is Standalone then engine-level `HasAuthority()` plausibly passes."*

```
LogWorldPartition: UWorldPartition::Initialize Context : World NetMode = Standalone,
    IsServer = 0, IsDedicatedServer = 0, ...
```
**`NM_Standalone`.** The client says so about itself, so the User-Agent-style attribution trap cannot
apply — and the same line is in `docs/Loki-s124-phaseladder-SUCCESS.log`, `Loki-s125-b1only.log` and
`Loki-s127-routeE.log`. **It has been sitting in every log this project ever took.** A textbook
method-rule-#2 instance ("read the shipped artifacts first").
Corroborating, both [M]: `AActor::AActor` writes `ROLE_Authority(3)` to `+0x160`
(`0x338E38B c6 83 60 01 00 00 03`), and this session's own staging log printed
`PlayerState Role@0x160=3 RemoteRole@0x72=1` and `hero Role@0x160=3`.
⇒ **engine-level `HasAuthority()` passes on this client.** `IsServer = 0` is *consistent* — stock
`UWorldPartition::IsServer()` is true only for Dedicated/ListenServer.
⚠ **Do NOT over-read it.** FK-1's four empty impls and the `ULokiBlueprintLibrary` exec-pin gates
(`0x1311870 = C6 02 00 C3`) never consult UE's netmode, so **those walls do not move.** What it
settles is that the walls are *Loki's own authority stubs*, not UE refusing authority to a client.

---

## 8. HEALTH, AND HOW THE CLIENT DIED

Alive and clean throughout all three flights: **0 `Fatal`, 0 crashpad handoffs**, and **0
`InitPlayerState` error lines** (the "PlayerStateClass … is null" receipt never fired — it succeeded
cleanly). Uptime at the last successful external read: 1,079 s.

It then died **~8 s after that read**, with everything captured:
```
MISSED: process exited before any crash marker was seen.
  exit code 57005 (0x0000DEAD) — PROTECTOR NtTerminateProcess(0xDEAD) — anti-tamper kill (FK-32)
  elapsed 1144.4s
```
No artifact of any kind — the FK-32 signature. That was the **6th** manual-map into that process
(gft, fo, sp, botps, botps-link, lokibot), at **1144 s**.

**FLIGHT 4 (§7b) then died the same way at the 4th manual-map, at 334 s.**

⚠⚠ **SELF-CORRECTION, made the same session.** On flight 3's death alone I wrote *"repeated
injection into one process appears to accumulate FK-32 risk"* (citing S132's kill on its 7th
injection). **Flight 4 refutes that phrasing**: fewer injections (4 vs 6) and less than a third the
elapsed time (334 s vs 1144 s). Across the three recorded `0xDEAD` kills the injection counts are
**7 (S132) / 6 / 4** and the elapsed times are unrelated — **there is no dose-response, so
"accumulates" is unsupported.** What all three DO share is that they were multi-injection
tutorial-route sittings. Grade it **[I, weak]** and keep harvesting the free exit code rather than
spending launches on it.

---

## 7b. ★★★★★ FLIGHT 4 — ARM D REPRODUCED IN A FRESH CLIENT, AND **THE LOKI BOT HAS A BRAIN**

A second launch, a second staged world, the fixed arm (`f8ab43b040ea8a12` — the two §9 defects
below repaired). **ARM D reproduced end to end**: different process, different ASLR, different
pointers, same A-B-A, `pokeOK=1 restoreOK=1`, `LokiBotController<-LokiAIController<-AIController<-…`
on the treatment and plain `AIController` on both baseline and reversal.

★★★★★ **AND THE QUESTION THE OFFLINE LANES WERE SENT TO ANSWER WAS SETTLED EMPIRICALLY FIRST — WITH
A TWO-SIDED WITHIN-RUN CONTROL.** Read externally (`playerstate_readout.py`, read-only RPM):

| field | ctrl A (`AIController`) | **treatment (`LokiBotController`)** | ctrl C (`AIController`) |
|---|---|---|---|
| `BrainComponent` +0x498 | **NULL** | **`BTComponent` (`BehaviorTreeComponent`)** | **NULL** |
| `Blackboard` +0x4B0 | **NULL** | **`BlackboardComponent`** | **NULL** |
| `PerceptionComponent` +0x4A0 | NULL | NULL | NULL |
| `PathFollowingComponent` +0x490 | present | present | present |
| `CachedGameplayTasksComponent` +0x4B8 | present | present | present |

The two plain controllers were spawned **by the same code, milliseconds either side of the
treatment, into the same world**. They have no brain. The Loki one does — **and we passed
`BehaviorTree = null`**, so `ALokiBotController` built it itself. The last two rows are the
shared-baseline control proving the probe reads these fields correctly and the difference is
specific to Brain/Blackboard.

**And the brain is populated, not a husk:**
```
BehaviorTreeComponent 0x2CCEB38EF80
   +0x0148 NodeInstances            = Num=21          <- a real tree is INSTANTIATED
   +0x02A0 DefaultBehaviorTreeAsset = NULL            <- so it was started, not defaulted
   +0x00D8 BlackboardComp           = the BlackboardComponent
   +0x00E0 AIOwner                  = the LokiBotController
BlackboardComponent   0x2CB5E44D200
   +0x00E0 BlackboardAsset          = 0x2CB76559D00 (BlackboardData)
   +0x0108 KeyInstances             = Num=15
```
⇒ **[M] `ALokiBotController` instantiates a real behaviour tree (21 nodes) and a real blackboard
(15 keys), cross-wired to itself. Its AI machinery is NOT gutted.**

⚠⚠ **WHAT THIS DOES NOT SHOW: that the bot ACTS.** 21 instantiated nodes and a live blackboard mean
the tree was built; they do not mean it is executing usefully, and **nothing here measured
movement**. `LogBehaviorTree`/`LogAIModule` occur **0** times — ⚠ **with NO POSITIVE CONTROL**, so
that zero is **UNINTERPRETABLE**, not evidence either way. The movement read was attempted and
**failed for an instrument reason, not a game reason**: the client had already been killed
(FK-32, §8) and the scratch probe reported `UNREADABLE` **because it had no RUN-IS-VOID check** —
exactly the artifact `playerstate_readout.py` guards against and this throwaway did not.
**Movement is the pre-registered first item for S138.**

---

## 7c. THE OFFLINE FOLLOW-UP — AND A LANE THE LIVE DATA REFUTED

Eight more agents (4 read + 4 adversarial) transcribed the newly-lit code. **64 CONFIRMED /
25 DOWNGRADE / 10 REFUTED.**

### `ALokiBotController::OnPossess` (`0x5565470`) — 2,222 B, vtable slot 269, **NOT gutted**
27 distinct direct call targets: **26 REAL, 1 DARK (`0x4467B90`), ZERO stripped folds.** On
possession it chains Super, requires the pawn to be `ALokiHeroCharacter`, fetches a process-wide
bot-config CDO, `AddComponentByClass`es a configured component onto the pawn, **calls
`RunBehaviorTree(Cfg->[0x240])` through vtable disp `0x940`**, binds two of its own UFUNCTIONs onto
pawn delegates (`hero+0xC38` `HandleLivingStateChanged`, `hero+0xDF8` `UpdateCharacterControllable`),
applies every `UGameplayEffect` in `Cfg->[0x320]` to the hero's ASC (`hero+0xF00`) and
`GiveInstanceOfAbility`s three ability classes. **It reads NO difficulty, team index or hero class** —
everything bot-specific comes from one global config CDO.

★★ **A BRANCH THAT IS DEAD ONLY BECAUSE OF OUR ORDERING:** it broadcasts a multicast delegate at
`ALokiPlayerState+0x5B0` with the hero **only if PlayerState is non-null**. In S137 the PlayerState
is installed by ARM B *after* possession, so that branch never ran. **Giving the controller a
PlayerState BEFORE it possesses would light it up** — a concrete, cheap S138 experiment.

### ⚠⚠ TWO OF MY OWN LANES CONTRADICTED EACH OTHER, AND THE LIVE MEASUREMENT SETTLED IT
**W2 concluded** that `OnPossess` *"calls neither `RunBehaviorTree` (0x3316AF0) nor `UseBlackboard`"*
and therefore that the S137 bot *"was ticking with a NULL Blackboard"*, which would have made its
whole tick analysis a statement about a crippled bot. **It is REFUTED three ways:**
1. **The bytes** — re-read personally: `0x55655E4 mov rdx,[rbx+0x240]` / `test` / `je` /
   `0x55655F0 mov rax,[r15]` / `mov rcx,r15` / **`0x55655F6 call qword [rax+0x940]`**. The call is
   **INDIRECT through the vtable**; W2 searched for a *direct* call to `0x3316AF0` and for direct
   writes to `+0x498`/`+0x4B0` inside `OnPossess`. Both are structurally invisible: the dispatch is
   indirect and the component creation happens in the **callee**. A scan blind by construction.
2. **The adversarial pass** caught it unprompted: *"THE NEGATIVE HAS NO POSITIVE CONTROL THAT COULD
   HAVE FIRED, AND THE THING IT DECLARES ABSENT IS PRESENT"* — and noted `0x3316AF0` is not
   `RunBehaviorTree`'s body at all but a 4-way ICF-folded virtual-dispatch shim.
3. **§7b's live measurement** — `BrainComponent = BTComponent`, `Blackboard = BlackboardComponent`,
   21 node instances, 15 blackboard keys.
⇒ **the live read is what makes this decisive.** ★ And the naming closes from both ends: the callee
at disp `0x940` (`0x45D79F0`) loads the wide literal **`BTComponent`**, and the live component is
**literally named `BTComponent`**. Offline literal and live object name, two instruments.
⚠ The W1 refuter separately DOWNGRADED W1's *stated* naming chain for disp `0x940` — it leaned on
that folded shim, and **a folded RVA names nothing**. The conclusion stands on the callee's literals
plus the live names; the evidence chain W1 printed was weaker than its grade.

### `ALokiBotController::Tick` (`0x556E9F0`) — REAL, 1,261 B, slot 170, zero folds
Per frame: a jump cooldown, an input-lock bail, then six throttled checks (glide, hazard-GE jump,
broken path, death-circle safety, stuck) and **one motion driver — a RANDOM WANDER** that calls one
virtual on the pawn's movement component with a cached `RandomMoveDirection`. **No targeting, no
ability use, no combat.** ⚠ The wander and stuck checks gate on `Blackboard != NULL` **and** on a
blackboard bool key (`.data 0xA0348F0`, the `bCharacterControllable`-family key set by
`UpdateCharacterControllable` `0x5570B80`). Since the Blackboard **is** present (§7b), the surviving
question is that bool — **which is exactly what the movement read in S138 measures.**

### `SpawnBot` — spec confirmed, with corrections
`0x556D910`, 1,544 B, REAL. **43 call instructions = 39 direct + 4 indirect; 28 distinct direct
targets; 25 REAL, 2 FOLD, 1 DARK** (the lane said 39/25/22 — corrected by its refuter).
Call it as the **raw impl**, 7 native args
(`comp, &heroClassCell, locXYZ, teamIndex, difficulty, premadeController, &botNameFString`), stack
args at `[rsp+0x20/0x28/0x30]`; it **returns the spawned `ALokiHeroCharacter*` directly**, so the
`CreatedBot` out-param trap does not apply to a direct call.
⚠⚠ **`BotName` must be a ZEROED 16-byte FString** — `SpawnBot` fills it and **frees it with the
game's `FMemory::Free` (`0xFF9310`) on BOTH exit paths**, so a shim-CRT-allocated buffer there is
heap corruption.
⚠⚠ **RISK CLASS IS *NOT* CALL-ONLY — the lane claimed it and its refuter REFUTED it**: an exhaustive
operand scan finds **7 non-stack writes across FOUR objects**. Treat it as a state-mutating call.
★ The premade short-circuit is confirmed from the bytes: `0x556DA4F mov rax,[rsp+0x70]` /
`0x556DAA1 test rax,rax` / `0x556DAA4 jne 0x556DB32` jumps over `0x556DAAA..0x556DB30`, whose only
memory writes are three stores to SpawnBot's own stack frame — i.e. **`MakeNewBotController` is
never called.**

### The authority lane — the honest payoff is a NEGATIVE, and that is worth having
`NM_Standalone` re-confirmed independently (the refuter found the log line itself);
`AActor::HasAuthority` is an 11-byte real body (`cmp byte [rcx+0x160],3; sete al; ret`), and with the
live `Role@0x160 == 3` it returns TRUE. **But:** a sweep of `SpawnBot`, `MakeNewBotController`, all
three `LokiRideable` `Auth*` entry points, `OnPossess` and `Tick` finds **not one** that reads `Role`
or calls `GetNetMode`. They die on Loki's own hardcoded stubs and on the folds. ⇒ **this moves no
wall on the current frontier**, exactly as §7b(b) said. ⚠ And *"`0xF7EB60` IS `LokiIsServer`"* is
**[I, strong], not [M]** — that fold has 106,924 stored-pointer occurrences and **a folded RVA names
nothing**.

---

## 7d. THE OFFLINE DE-RISK PASS (41 CONFIRMED / 17 DOWNGRADE / 5 REFUTED)

### The bot's ONE motor output is named end to end
`[ULokiCharacterMovementComponent vtable + 0x5E0]` is **slot 188 =
`UCharacterMovementComponent::RequestPathMove(const FVector&)` at `0x35F41D0`**, inherited
**unmodified** — Loki does not override it. It tail-calls `UPawnMovementComponent::RequestPathMove`
(`0x3642960`) → `APawn::Internal_AddMovementInput` (`0x3BACB60`) → **`APawn::ControlInputVector
(+0x418) += RandomMoveDirection`**.
The argument is `ALokiBotController::RandomMoveDirection` at **`+0x658`** (name *and* offset from the
UHT property record): a horizontal unit vector, re-randomised every **2.0 s**, with **Z exactly 0** —
which is why `RequestPathMove`'s `IsMovingOnGround()||IsFalling()` sub-gate is skipped entirely.
⇒ **The cleanest movement readout is not "sample the location twice".** Read
`pawn ControlInputVector +0x418` and `controller RandomMoveDirection +0x658`. A non-zero
`RandomMoveDirection` with a zero `ControlInputVector` localises the failure *at* the motor call; both
non-zero with a stationary pawn localises it *past* the motor, in the movement component.

**The gate on that motor** is a Bool blackboard key, [I, very strong] `IsCharacterControllable` of
`BB_HeroBots` — ⚠ **not [M]: decoding `FNameEntryId 0x0001A12C` needs the live FNamePool**, which is
heap-resident and absent from every module dump by construction. It is written only by
`ALokiBotController::UpdateCharacterControllable` (`0x5570B80`) as
`bCharacterControllable (+0x6A0) = (GetLivingState(pawn) == Alive) && !IsStunned(pawn)`, forced FALSE
when `ForceCharacterNotControllable (+0x602)` is set. **`+0x6A0` is therefore a direct live read that
needs no FName decode at all.**

### The bot-config CDO is named: `ULokiCharacterGlobals`
`/Script/Loki.LokiCharacterGlobals`, SizeOf **0x458**, reached as
`CDO( CDO( UWorld[+0x2D0] → ULokiGameInstance[+0x1D8 GlobalsClass] )[+0x38 CharacterGlobals] )`.
All four transcribed offsets re-derived independently and now **named**:

| offset | name | type |
|---|---|---|
| `0x240` | `HeroBotBehaviorTree` | `UBehaviorTree*` — what `RunBehaviorTree` is handed |
| `0x248` | `HeroBotComponent` | `TSubclassOf<UActorComponent>` — **the lane's own missed fifth read** |
| `0x2B0` / `0x2B8` / `0x2C0` | `HeroBotJumpSpell` / `HeroBotGlideSpell` / `HeroBotRelocateSpell` | `TSubclassOf<ULokiGameplaySpell>` |
| `0x320` | `BotCheatEffects` | `TArray<TSubclassOf<UGameplayEffect>>` |

OnPossess reads **nothing else** off it — no difficulty, playstyle, team or hero class, and not even
`HeroBotEmoteControlPassive` (`0x2C8`).
⚠ The lane named the accessor `GetFromContextObject` at `0x55A95A0`; its refuter **REFUTED** that —
the registered impl is **`0x55AB810`**. The class identity, SizeOf and both `.rdata` addresses were
independently confirmed.

★★ **AND THIS SHARPENS §7a's "no GameplayEffects" finding into two testable candidates.** The field is
`BotCheatEffects` — plausibly empty by default. But a second candidate is now on the table and is
arguably likelier here: **neither `ALokiCharacter`'s nor `ALokiHeroCharacter`'s constructor contains a
single instruction with displacement `0xF00`**, so the ASC at `hero+0xF00`
(`AbilitySystemComponentStorage`) is **not a constructor default subobject** — it is written by
runtime code. Our bot pawn came from `SpawnAIFromClass`, **not** from the shim's `WireAbilitySystem`
(which is what wrote `+0xF00` on the *player* hero, per the staging log), so **the bot's ASC was very
likely NULL**. Two read-only RPM reads discriminate: `hero+0xF00` and `Cfg+0x320` `ArrayNum`.

### The authority "hazard" is a clean negative — and it contains a correction that matters more
Re-derived: **145** `cmp byte [reg+0x160],3` sites, **32** authority-taken. ⚠ Both prior counts
(14, then 21/23) are REFUTED, and the lane's own "17 enabling" partition was refuted for not summing.
⚠⚠ **"Branch taken when authority" is NOT "client-only arm", and the flagship counter-example is
`AController::Possess`** — see §7e. **No presentation path we depend on was found to be at risk.**

---

## 7e. TWO CONTROLS WE BROKE, AND A POLARITY CORRECTION

**⚠⚠★ WE KILLED ONE OF THE REPO'S OWN NEGATIVE CONTROLS.**
`docs/fk22-dropphase-reachability.md` designated `ALokiGameState::AuthSetDeathCircle` impl
`0x55653E0` as FK-22's **coverage negative control** ("0/4096 non-zero in 13/13 images"). It shares
`.text` page `0x5565000` with `ALokiBotController::OnPossess` `0x5565470` — **0xB0 bytes away** — so
**this session's own bot flight decrypted it as a side effect.** It now reads **3,782/4,096** with a
real `jmp 0x338C990` at its entry, having been 0/4096 in `merged2`, `merged10` AND `merged12`.
**Nothing about the drop path changed; a neighbour ran.**
⇒ **A coverage negative control is only valid until something on its PAGE runs.** Choose one with no
plausible neighbour, re-verify before each use, and state the image.
✅ Verified still-dark in `merged13` (2026-08-21): `ULokiRespawnComponent::Respawn 0x5A6AC40`.
⚠ A second control was independently dead: `docs/fk-playability-audit-s134.md` offers `0x5A6AC40`
**or** `0x556D910`, and `0x556D910` (SpawnBot) has been LIT since `merged12`. Both annotated in place.
⚠ Grade: page-lit means **READABLE OFFLINE**, not **EXECUTED** — a 4 KiB page census cannot say which
function on the page ran.

**THE STALE-CLAIM SWEEP: 43 instances / 15 files / 14 RVAs** (unit: file:line × RVA pairs),
reproduced row-for-row by an adversarial pass. ⚠ **The shape is the opposite of S133's: only 3 first
went stale in `merged13`; 29 have been stale since `merged10`.** The problem is not missing captures
— `regrade_blocked.py` has been emitting these for sessions and nobody edits them. **Four sat in
`CLAUDE.md` itself, two contradicting the same file elsewhere**; all four now annotated in place.
⚠ The sweep is a **FLOOR**: 294 of 431 keyword lines carry no same-line address and were never graded.
⚠ A lane claimed three were "never flagged by any prior audit" — **REFUTED**, the S133 tool emits all
three verbatim.

**⚠⚠ THE POLARITY CORRECTION, derived independently twice (session lead + a lane):**
```
AController::Possess 0x36E2B60
  0x36E2B86  test byte [rcx+0x448], 4    ; bCanPossessWithoutAuthority
  0x36E2B93  jne 0x36E2E13               ;   -> PROCEED
  0x36E2B99  cmp  byte [rcx+0x160], 3    ; Role == ROLE_Authority?
  0x36E2BA0  je   0x36E2E13              ;   -> PROCEED
  0x36E2BA6  ...fallthrough = the FMessageLog warning
  0x36E2E13  mov rsi,[rcx+0x3F8] (Pawn) ... call [rax+0x868]   ; slot 269 = OnPossess
```
A lane described `0x36E2BA0` as where Possess "refuses". **It is the jump to SUCCESS.** This is stock
`if (!bCanPossessWithoutAuthority && !HasAuthority()) return;`.
⇒ **"branch taken when authority" ≠ "client-only arm"** — semantics require reading the branch
TARGET, not the condition.
⇒ ★ **And it retires a pre-flight question outright:** our `LokiBotController` demonstrably reached
`OnPossess` (it has a `BTComponent`), so that gate **passed** on it — **[M] by consequence**, not
something to read before the next flight. **Authority is exactly why S137's possession works.**
★ It also independently confirms `OnPossess` is vtable slot 269 (disp `0x868`), from a third site.

---

## 9. WHAT IS NOW BUILDABLE (for the successor)

The concrete route to a *real* Loki bot, with every precondition now met or measured:
1. **`ALokiBotController` is intact and instantiable** — registered, non-abstract, `sizeof 0x6A8`,
   ctor `0x554B430` REAL 577 B, and its entire four-deep construction chain has **zero folds and zero
   dark callees** across 26 callees. Its UClass and CDO were read **live** in the tutorial world
   (`0x173B8595100` / `0x173B3D21B00`), which answers an open question a lane raised.
2. **We can now make one, possess a hero with it, and give it a PlayerState** — §6.
3. **`SpawnBot`'s `PremadeBotController` parameter short-circuits `MakeNewBotController` entirely** —
   so FK-22's stripped getter is never reached — **and `SpawnBot` consumes the premade controller's
   PlayerState from `+0x3C0`**, which is exactly the field ARM B fills.
⇒ The next arm is `SpawnBot(..., PremadeBotController = ours, ...)` via the S55 direct thunk. A
follow-up workflow is transcribing `OnPossess`, `Tick`, and the full `SpawnBot` gate list from
`merged13` to spec it.

---

## 10. ARTIFACTS

| path | what |
|---|---|
| `docs/s137-PREREGISTERED.txt` | flights 1–2 predictions, written before injection |
| `docs/s137-ARMD-PREREGISTERED.txt` | ARM D predictions, written before injection |
| `docs/s137-marker-flight1-botps.txt` | ARM A refuted / ARM B worked |
| `docs/s137-marker-flight2-botps-link.txt` | ARM C worked |
| `docs/s137-marker-flight3-lokibot.txt` | ARM D — the A-B-A |
| `docs/s137-external-BASELINE.txt` | external probe before any injection (positive control passing) |
| `docs/s137-external-AFTER-flight1.txt` / `-flight2.txt` | external confirmations |
| `docs/s137-external-AFTER-flight3.txt` | ⚠ transcript reconstruction — see C6 |
| `docs/s137-marker-after-sp.txt` | the staging ladder |
| `docs/s137-marker-flight4-lokibot.txt` | flight 4 — ARM D reproduced in a fresh client |
| `docs/s137-external-flight4-components.txt` | **the two-sided component control** (§7b) |
| `docs/s137-botmove.txt` | ⚠ a VOID run, preserved as an instrument-artifact instance — NOT a negative |
| `dumps/s137-lokibot/` | the capture that decrypted the bot code |
| `dumps/merged13.dump.exe` | new canonical merge — 16,800/30,281 pages (55.48 %), strict superset of `merged12` (0 lost / +28 / 0 conflicts) |
| `dumps/s137-arms/` | all arms archived (`build/` is gitignored). ⚠ **The FLOWN `lokibot` is `3119d75ae2ca1859`**; `tutorial_launch_lokibot_v2_defectfix.dll` (`f8ab43b040ea8a12`) is a LATER rebuild carrying the two §9 defect fixes and **was never flown**. `text_digest.py --dupes` over the directory: **0 duplicate groups** |
| `tools/re/playerstate_readout.py` | the external instrument (new) |
| `docs/capture.log.pre-s137` | capture.log backed up before the `ags` restart |
