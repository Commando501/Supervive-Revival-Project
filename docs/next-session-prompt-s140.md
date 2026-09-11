# NEXT SESSION (S140) — the input wall is named; port the fix the repo already proved

**One line: the INPUT wall is NAMED — `GetMaxAcceleration()` returns 0, proved by a SIGNED ZERO
(`Acceleration` carries `ControlInputVector`'s sign in 22/22 samples) — and this repo has a
LIVE-PROVEN fix for it that was never ported (`ds_hybrid.cpp:2370-2430`). Port it, and read the
`StartNewPhysics` latch in the SAME pass, because a zero acceleration does not explain the absent
GRAVITY.**

⚠⚠ **A CONTRADICTION I PUBLISHED MID-SESSION IS DISSOLVED — and the error is worth carrying.**
`docs/s139-flight2-gate-refuted.md` §5 says six exits are all measured passing yet the call never
happens, and calls that "a real contradiction". **It is not.** `+0x12B0` is accumulated at
`0x055B840C`, which is **UPSTREAM of the Super call at `0x055B85C1`** — so *"`+0x12B0` advances"*
proves only that **LOKI's** `PerformMovement` ran with dt > 0. It says **nothing** about whether the
engine's `PerformMovement` got anywhere. I read a fact about the wrapper as a fact about the callee.
⇒ **The engine's `PerformMovement` may well be bailing at one of its own gates after all**, and
`latch 0 + dt advancing` is a fully-explained third survivor, not a paradox. **Fix that section
before building on it.**

⚠⚠ **THREE EARLIER FRAMINGS OF THIS FILE ARE SUPERSEDED — each was tested, each fell.**
(1) *"one read: is the capsule simulating physics?"* → taken: **`bSimulatePhysics = 0`, gate PASSES**.
(2) *"the weld, because `IsSimulatingPhysics` uses `bGetWelded = true`"* → taken:
**`WeldParent @capsule+0x5F0 = NULL`** ⇒ `GetBodyInstance` returns the capsule's own body ⇒
**REFUTED**. (3) *"pin `LogCharacterMovement` and read the abort string"* → still worth doing, but
demoted to §0a: flight 3 answered the bigger question without it.

Written 2026-08-23 at the end of S139. Read `docs/s139-flight1-the-bot-is-not-special.md` first
(its §7b is the target and its §7b adjudication block governs), then `docs/s139-movement-ladder.md`.

**STATE AT HANDOFF:** flight-2 client PID 35608 was still ALIVE at write-up (no injection was made
that flight). The flight-1 client died after 2 injections (FK-32 class), all data captured first.

---

## A. THE CHAIN AS IT NOW STANDS — after three flights

    the AI runs: behaviour tree -> blackboard -> wander -> RequestPathMove          [M, S138]
      -> pawn ControlInputVector += direction                                      [M, S138]
      -> ConsumeInputVector at 0x036037FE drains it EVERY FRAME                    [M, S139-f1]
         (|CIV| never exceeds 1.0001 over 194 samples despite "+=" semantics)
         ** it is called BEFORE both early-outs, so consumption != simulation **
      -> the whole E1..E7 early-out ladder is PASSED                               [M, S139-f1/f3]
         (every structural field identical bot vs player; Role 3; Mobility Movable)
      -> ControlledCharacterMove RUNS                                              [M, S139-f3]
         (Acceleration@+0x328 carries ControlInputVector's SIGN in 22/22 samples =
          a signed zero = input x 0. A never-written field cannot track a sign.)
      -> *** Acceleration = input * GetMaxAcceleration() == 0 ***                  [M, S139-f3]
         THE INPUT WALL, and the repo has a live-proven fix (section 0).
      -> ULokiCMC::PerformMovement runs                                            [M, S139-f1]
         (+0x12B0 += xmm6 at 0x055B840C -- but that is UPSTREAM of the Super, so it
          says nothing about how far the ENGINE impl gets. See the retraction above.)
      -> it reaches its Super UNCONDITIONALLY at 0x055B85C1 -> engine 0x035E9EC0   [M, S139-f1]
      -> ??? ULokiCMC::StartNewPhysics is NEVER ENTERED                            [M, S139-f1/f2]
         (latch +0x16C8 == 0 on the bot, the player, and ALL 37 components in the
          world; the latch write at 0x055C2469 is on the unconditional fall-through)
      -> no StartNewPhysics => no PhysFalling => no gravity.
         *** STILL UNEXPLAINED. A zero Acceleration does NOT stop gravity. ***

---

## 0. ★★★★★ START HERE — PORT THE GAS RECIPE THE REPO ALREADY LIVE-PROVED

**S139 flight 3 named the input wall: `GetMaxAcceleration()` returns 0.** `Acceleration @CMC+0x328`
carries `ControlInputVector`'s **SIGN** in 22/22 samples (44 sign bits) — a signed zero, i.e.
`input × 0`. A never-written field is `+0.0` forever and cannot track a sign ⇒ the
`ScaleInputAcceleration` store **executed every frame** ⇒ **`ControlledCharacterMove` RUNS and the
whole tick ladder is PASSED. S2 is refuted.** Read `docs/s139-flight3-controlledcharactermove-runs.md`.

★★★ **THE FIX IS ALREADY IN THIS REPO, LIVE-PROVEN, AND WAS NEVER PORTED.**
`docs/coverage-audit-s101.md:283` (≈38 sessions old): the DS route borrowed
`Default__LokiPlayerState_HeroAffiliated`'s default subobjects into the hero's
`+0xF00/+0xF08/+0xF10` and wrote the attribute block — **measured `GetMaxSpeed()` 0 → 500,
`GetMaxAcceleration()` 0 → 50000, and the hero physically translated via the stock engine chain.**
`:630` ranks porting it *"Single highest-value experiment available"*. Code:
**`tools/sigbypass-mod/ds_hybrid.cpp:2370-2430`**.

- ⛔ **DO NOT SPAWN `LokiPlayerState_HeroAffiliated`** — S80 live-proved an instant client crash.
  Use the **CDO's default subobjects**, which are already constructed.
- ⚠⚠ **A PARTIAL PORT FAILS and the source says so from experience:** wiring `AttributeSetStorage`
  makes the Loki CMC read **every** movement value from attributes instead of its base UPROPERTYs,
  so a set with only `MoveSpeed` gives `MaxAcceleration = 0` and still no movement (observed).
  Write the whole block — `MoveSpeed`, `MaxMoveSpeed`, `MaxAcceleration` 50000, `GroundFriction` 8,
  `BrakingDecelerationWalking` 2048, `Mass` 100 — at `FGameplayAttributeData` `+0x8` **and** `+0xC`.
- ★ `tutorial_launch`'s `KWIREGAS` **deliberately writes only `+0xF00`** (`tutorial_launch.cpp:11899`),
  which is exactly the gap; every staged marker has printed `AttributeSetStorage @0xF08 = 0x0`.
- ⚠ It writes a **CDO default subobject** — process-wide scope. A diagnosis, not a shipping fix.

⚠⚠ **READ THE LATCH `+0x16C8` IN THE SAME PASS.** A zero `Acceleration` does **not** stop gravity,
and `StartNewPhysics` still never runs (latch 0 on all 37 components). The input wall and the
physics-step wall may be one problem or two — **flying the port with the latch read settles it in
one sitting.** Do not assume the port fixes both.

⚠ **First, re-run `docs/s139-f3-signedzero.txt`** (30 s): it is the bit-level confirm of the signed
zero and it did **not** obtain — the client died and the probe correctly self-voided.

## 0a. ★★ FALLBACK / CONFIRMATION — TURN THE PHYSICS-STEP QUESTION INTO A LOG LINE

**Engine `UCharacterMovementComponent::StartNewPhysics 0x03600990` has its OWN `IsSimulatingPhysics`
gate, and it LOGS when it fires:**

    0x036009D3  mov  rcx, [rbx+0xd0]        ; UpdatedComponent
    0x036009E4  call qword ptr [rax+0x4c0]  ; IsSimulatingPhysics
    0x036009EC  je   0x3600a57              ; proceed
                                            ; fall-through -> verbosity gate -> LOG -> RETURN

String: `.rdata 0x07FC0670` — *"UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s)
is simulating physics - aborting."*, `CharacterMovementComponent.cpp:3477`, **verbosity threshold
5 = `Log`** (so it prints at default verbosity *if the category is not pinned down*).

⚠⚠ **I GREPPED FOR IT AND GOT ZERO — AND THAT ZERO IS UNINTERPRETABLE.** `LogCharacterMovement`
occurs **0 times** in the whole 898 KB `Loki.log`, so **the category has no positive control** and
the absence says nothing. This is the project's own Class-A-vs-never-ran trap.

★ **THE CHEAP FIX, AND IT IS THE BEST NEXT MOVE IN THE WHOLE SESSION:** FK-11 established that
`[Core.Log]` in the **user** `Engine.ini` binds (and that `-LogCmds` and `-ini:` do **not**). Run
`configs\set-log-verbosity.ps1` to pin **`LogCharacterMovement=Log`** (Verbose is unnecessary —
threshold 5 is `Log`), relaunch, stage, and read. Then:
- the abort line **present** ⇒ that gate fires after all, despite `bSimulatePhysics = 0` and a
  NULL `WeldParent` — which would be a genuine surprise and worth every minute;
- the abort line **absent, with the category now emitting other lines as the positive control**
  ⇒ that gate is genuinely passing and the bail is elsewhere.
**Either way it is a per-frame, per-object receipt for free, and it replaces the entire read plan
below.** ⚠ Establish the positive control first — a silent category proves nothing.

## 0b. ⛔ THE WELD QUESTION — ASKED AND ANSWERED: `WeldParent @capsule+0x5F0 = NULL`. REFUTED.

Kept as the record of how it was settled, not as a task.

    0x035E9FB5  call qword ptr [rax+0x4c0]     ; on the CAPSULE's vtable
    0x03C9B0A0  ...  mov r9d, 0xFFFFFFFF       ; Index = -1
                     mov r8b, 1                ; *** bGetWelded = TRUE ***
                     call qword ptr [rax+0x810]  ; GetBodyInstance(BoneName, bGetWelded, Index)

With welding on, `GetBodyInstance` can return **another component's** `FBodyInstance`. So the
measured `this->BodyInstance.bSimulatePhysics == 0` does **not** settle what the call returns — the
measured input and the tested condition are provably different objects. That is exactly the shape a
false "this gate passes" takes, and it is the only one of the six with that property.

**Do this first, and it is mostly OFFLINE:** transcribe `0x03C9B0A0` and its `[vt+0x810]` callee,
then one read of the capsule's weld state (`BodyInstance.WeldParent` / the returned body's
`bSimulatePhysics`). `tools/re/cmc_earlyout_readout.py` already resolves `BodyInstance @+0x3F0` and
decodes its bitfields from the live `FBoolProperty`.

**The banked five** (do not re-measure): `HasValidData` inputs, World, `MovementMode` 3,
`Mobility` 2, and `bSimulatePhysics` 0 on the capsule itself — all read live with controls.

## B. Reference — the six exits, CFG-verified

Engine `UCharacterMovementComponent::PerformMovement 0x035E9EC0`. **A recursive-descent CFG walk
(1,461 reachable instructions; one `ret`; no indirect jumps) proves EXACTLY SIX branches before the
call can skip it.** ⚠ A linear sweep of the same range decoded only 1,074 instructions — it missed
~390 and is NOT a sound instrument here, though it happened to get this region right.

    0x035E9F17  call qword ptr [rdx+0x6b8]        ; HasValidData          -> PASSES (measured)
    0x035E9F25  test r13,r13 / je                 ; World == null         -> PASSES
    0x035E9F90  cmp  byte ptr [rbx+0x231], r15b   ; MovementMode==MOVE_None?
    0x035E9F97  je   0x35eb7cf                    ;   MEASURED 3  -> PASSES
    0x035E9F9D  cmp  byte ptr [rcx+0x1bb], 2      ; Mobility==Movable?
    0x035E9FA4  jne  0x35eb7cf                    ;   MEASURED 2  -> PASSES
    0x035E9FB5  call qword ptr [rax+0x4c0]        ; UpdatedComponent->IsSimulatingPhysics(NAME_None)
    0x035E9FBD  jne  0x35eb7cf                    ;   capsule bSimulatePhysics = 0 -> PASSES
                                                  ;   *** but bGetWelded=true -- see 0b ***
    0x035EA255  call qword ptr [rax+0x6b8]        ; HasValidData AGAIN
    0x035EA25D  je   0x35eb150                    ;   its 3 inputs measured good -> PASSES

(`rcx` = `UpdatedComponent`, loaded at `0x035E9F2E mov rcx,[rbx+0xd0]`; `rax` = its vtable.)

⚠ The single `call [rax+0x720]` (StartNewPhysics) is at **`0x035EB13A`** — **not** `0x035EB7FA`,
which the S139 synthesis recorded and which a CFG walk of the whole function does not find.

★ **Population control, already banked:** a walk of all 192,369 live objects found **37** movement
components. **Every one reads `+0x16C8 == 0`**, and **exactly one is doing anything at all** (the
player hero: `TimeSinceFallingStart 364.712`, `MovementMode 3`; the other 36 are pooled/unpossessed
with `MovementMode 0` and `TimeSinceFallingStart 0.000`). ⇒ **there is no moving character anywhere
in this world to use as a control** — do not design another "diff against a working one" experiment.

⚠⚠ **ONE TENSION TO CARRY, NOT TO RESOLVE BY ASSUMPTION.** If the capsule (or a weld parent) really
is PhysX-simulating, writing `CMC+0xE8` should not move the hero either — yet `play` reportedly moves
it "WITH collision" (`tools/sigbypass-mod/tutorial_launch.cpp:365`). Either that observation needs
re-checking under this lens, or `play`'s `SetMovementMode(5)` changes the state. **Measure; do not
argue.**

---

## C. ⚠⚠ WHAT IS REFUTED — DO NOT RE-OPEN ANY OF THESE

| # | claim | why it is dead |
|---|---|---|
| 1 | **"the controller ticks; the CMC does not"** (the S139 handoff's standing hypothesis) | [M] `ControlInputVector` never exceeds **1.0001** across all 194 samples of `docs/s138-f8-motion.txt` despite `+=` semantics. Unconsumed, it would reach ~5820 (per-frame) or ~6.6 (per-2 s, and not equal the latest direction). It is drained every frame. ★ The reconciliation: `ConsumeInputVector` runs at `0x036037FE`, **before** both early-outs — consumption does not imply simulation. |
| 2 | **S1 — the HitStop DeltaTime kill** | [M] `+0x12B0 += xmm6` (`0x055B8409`–`0x055B8414`), and `xmm6` is exactly the register `0x055B83FA xorps` would zero. It advances at **1.0× real time on both pawns**. Also: the `StartNewPhysics` latch is set *before* the jump to the engine, so `latch == 0` proves it was never entered — the `MIN_TICK_TIME` bail is unreachable as an explanation. ⚠ A second S139 offline lane concluded "S1 SURVIVES"; its bytes are right and its conclusion is wrong. See `docs/s139-flight1...md` §7b. |
| 3 | **S2 — a per-instance early-out byte differing on the bot** | [M] every structural field reads IDENTICALLY bot vs player: `UpdatedComponent`, `Mobility` 2, `Role` **3**, `RemoteRole` 1, `Controller`, `RF_Garbage` 0, `MovementMode` 3, `MaxAcceleration` 50000, tick state, `bIsActive`, `AttributeSetStorage` NULL. |
| 4 | **`IsLocallyControlled` / `IsLocalController`** | [M] no override in 13 pawn / 6 controller vtables (incl. `ALokiBotController`); returns TRUE unconditionally at `GetNetMode()==0`. Two-sided control: `ALokiPlayerController` DOES override it, so the census detects overrides. |
| 5 | **`bUpdateOnlyIfRendered` "asymmetric by construction"** | [M] the `UMovementComponent` ctor writes `0xCE` to `+0x130`; bit `0x01` is CLEAR. |
| 6 | **"`Acceleration == 0` proves `ControlledCharacterMove` never ran"** | [M] three independent zero-writers. Only *non-zero and collinear* is informative. |
| 7 | **"the GAS zero explains the frozen bot"** | [M] lateral only — it cannot suppress gravity — and `AttributeSetStorage` is NULL on the **player too**. |
| 8 | **"`play` is a moving control / a tick fix"** | [M, source] `RM_PLAY` → `DoPlay()` (`:1275`) never calls `SetActive`/`SetComponentTickEnabled`/`SetActorTickEnabled` (those are `DoWakeMove`'s, `RM_WAKEMOVE` only). It writes `CMC+0xE8`/`+0x328` directly. **The player is a CONTAMINATED control on exactly those two fields.** |

★★★ **AND THE FRAMING, WHICH HAS NOW BEEN WRONG THREE TIMES IN THE SAME SHAPE:**
S138 `LivingState` (every character Dead) · S138 `MovementMode` (both Falling) · S139 the whole
ladder (identical). **It is not "why does the BOT not move" — it is "why does NO character move on
this route".** Stop looking for a bot/player difference in the movement component.

---

## D. FLIGHT PROCEDURE (unchanged, and it works)

```powershell
# ELEVATED PowerShell. Steam must already be running.
cd "G:\git\Supervive Revival Project"
.\configs\s138-autostage.ps1 -MaxAttempts 5 -Label s140
```
Staged on **attempt 2** in S139 (attempt 1 died FK-31 in staging — the documented ~27 %). It writes
PID/BASE to `docs\s138-staged-pid.txt`; gate on `[SP] done step=4` in the marker **plus** a live
process, never on the script's own completion message.

Then, into the staged client:
```
tools\inject\inject.exe mmap <PID> "G:\git\Supervive Revival Project\tools\sigbypass-mod\build\tutorial_launch_driverecompute.dll"
```
Wait for `[BS] done` in `docs\tutorial-launch-marker.txt` before reading anything.
Then `python tools\re\cmc_earlyout_readout.py <PID> <BASE> --watch 10`.

★ **Take the BASELINE read before injecting.** It costs nothing and it gave S139 the player-side
control independent of the arm.

**Arms** (RAW digests, all verified against their recorded gates on 2026-08-23):
`driverecompute` **`a2a952babfed256b`** · `botai` **`5e47c13cf7f0a158`** (regression gate) ·
`play` **`9bc10a4552c596e1`**. Verify with `python tools/sigbypass-mod/text_digest.py <dll>...`.

---

## E. ⚠ TRAPS

1. ⚠⚠ **Two probe defects in S139 each read exactly like a game fact.** `fname` read the FNamePool
   block table at `NAMEPOOL + 0x10 + 8*blk` (correct: **`NAMEPOOL + 8*blk`**) ⇒ every name decoded
   `?` ⇒ **"NO PLAYER-CONTROLLED PAWN — RUN IS VOID"** on a healthy client. `findprop` read an
   `FField`'s name at `+0x28` (correct: **`+0x20`**) ⇒ **"no `CharacterMovement` UPROPERTY"**.
   ★ **Both were localised in minutes by running the known-good `tools/re/movementmode_readout.py`
   against the same live process as an INSTRUMENT CONTROL. Keep a second trusted instrument.**
2. ⚠⚠ **`ALokiCharacter` has its own live byte at `+0x16C8`** — proved in flight:
   `0x055B860B mov byte [r15+0x16c8], 0` where `r15` is the **CharacterOwner**. A probe aimed at the
   PAWN instead of the COMPONENT decodes a plausible wrong value. **Assert `CMC+0x198 == pawn`
   first** (the probe does, and voids the side otherwise).
3. ⚠ **`+0x16C8` is a STICKY "ever reached" latch, never cleared.** No per-frame rate from it.
4. ⚠⚠ **This build's `EMovementMode` inserts `MOVE_Dashing` at index 6**, so `MOVE_Custom == 7`.
   `tools/re/movementmode_readout.py` still carries the stock table and mis-decodes by one.
5. ⚠ **`bCharacterControllable +0x6A0` is on the CONTROLLER, not the character.**
6. ⚠ **`tools/strxref/vtables.py` uses a cached index built on `merged2`** while `strxref.py`
   defaults to `merged13`, and the two have different ImageBases. `.rdata` vtable starts are safe;
   re-read every CODE grade from `merged13`.
7. ⚠ **`usmapdump dumpimage`'s "process not found" is ambiguous** between a wrong name suffix and a
   genuinely dead client. **Check `Get-Process` before believing either reading.**
8. ⚠ **Expect FK-32.** S139's client died after 2 injections. **Capture every result as you go.**

---

## F. ARTIFACTS

| path | what |
|---|---|
| **`docs/s139-flight1-the-bot-is-not-special.md`** | **the flight; §7b is the target, §7b's adjudication governs** |
| `docs/s139-movement-ladder.md` | the offline transcription: the ladder, the refutations, the traps |
| `docs/s139-f1-PREREGISTERED.txt` | P1–P7, unmodified — P2 is why the bisector was not over-read |
| `docs/s139-f1-BOT.txt` / `-BASELINE.txt` | the two-sided reads + the `+0x12B0` series |
| `docs/s139-f1-ticksniff-bot.txt` / `-player.txt` | full `FTickFunction` decode, both components |
| `tools/re/cmc_earlyout_readout.py` | the probe; both defects fixed and annotated in-file |
| `scratchpad/s139/ticksniff.py` | new instrument; `PrimaryComponentTick` IS a UPROPERTY at `+0x40` |

## G. SCOPE — say it correctly

⛔ **There is no working bot, and none of this is a shipping fix.** `ServerSetHeroClass`
(`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam` (`0x556DE53 → 0xF7EB60`) are stripped folds; the bot has
no hero class and no team. Everything above needs pokes the game never performs itself — `LivingState`
still has no writer that sets Alive.

Say: *"an `ALokiBotController` possesses a hero pawn, has a PlayerState, runs its behaviour tree and
produces movement input — and no character on this route reaches `StartNewPhysics`, so nothing
moves."* Never *"the bot works."*
