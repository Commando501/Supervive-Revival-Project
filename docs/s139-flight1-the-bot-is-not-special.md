# S139 flight 1 — the bot and the player are in the SAME state on every field. S2 is refuted.

> ## ⚠⚠⚠ PARTIALLY SUPERSEDED — READ THIS FIRST (banner added S142, 2026-08-24)
>
> **WHAT STILL STANDS:** the whole point of the document — **the bot and the player read IDENTICALLY on every structural field that was read**, which killed the "the bot is specially disadvantaged" framing and is still the reason nobody should look for a bot/player difference in the movement component. Also `Role@+0x160 == 3` on a `SpawnAIFromClass` pawn, and the identity controls.
>
> **WHAT IS DEAD:** every claim resting on `CMC+0x16C8`. **[M] that byte is NOT a latch.** `ULokiCMC`
> vtable disp `0xA50` = `0x0530ABF0` clears it, and engine `PerformMovement` calls that slot at
> `0x035EB569` — later in the same call, on a path the `StartNewPhysics` call site **dominates**. So
> it reads `0` whether the physics step runs every frame or never runs at all. It is a per-frame
> `TOptional<FVector>` validity flag over the `+0x16B0` Velocity snapshot, named from its own consumer
> `GetRecentVelocity` (`.data 0x09BC9AD0` → impl `0x0530AC10`). Those claims are **UNGRADED, not
> negative.** Read `docs/s140-tier1-cfg.md` §4.
>
> ⚠ **The MEASUREMENT was correct** — `+0x16C8` really did read `0`. Only the **inference** is dead.
> Nothing here misread a byte.
>
> **AND THE UNDERLYING QUESTION IS ANSWERED THE OTHER WAY NOW.** The engine mover chain runs on this
> client: `GravityScale = 1.0f` made the player fall 23,189 uu, and one `Velocity = (600,0,0)` kick
> made the bot fall, land and walk **13,196 uu at 500.0 uu/s**, reproduced in a second sitting. The
> remaining wall is narrower: the bot does not escape `Velocity == 0` on a *Z-only* kick, and the
> discriminator is the kick axis. See `docs/next-session-prompt-s142.md` and
> `docs/s141-tier3-settled.md`.

Written 2026-08-23. Pre-registration: `docs/s139-f1-PREREGISTERED.txt` (UNEDITED).
Probe: `tools/re/cmc_earlyout_readout.py` — **read-only RPM, no write of any kind**.
Offline basis: `docs/s139-movement-ladder.md`.

Client PID 44332, BASE `0x7FF704F00000`. Staged by `configs/s138-autostage.ps1` on **attempt 2**
(attempt 1 died in staging, FK-31, archived as `dumps/crashpad-20260823-170943-s139f1-a2`).
One injection (`driverecompute`, RAW `a2a952babfed256b`, digest verified against the recorded gate
before flight). Client died ~2 min after the last read — **every measurement was captured first.**

---

## 0. HEADLINE

**BOTH survivors are dead, and the wall is now localised to a few hundred bytes.**

1. **S2 is REFUTED** — every structural field in the tick early-out ladder reads IDENTICALLY on the
   bot and on the player (§0 table). There is no per-instance byte that differs.
2. **S1 is REFUTED** — `+0x12B0` accumulates *exactly the register* the HitStop branch would zero,
   and it advanced at 1.0× real time on both pawns (§2). **DeltaTime is real.**
3. ⇒ **`ULokiCMC::PerformMovement` RUNS with a real DeltaTime, and `ULokiCMC::StartNewPhysics` NEVER
   RUNS** (its unconditional latch reads 0 on both — polarity re-read from the bytes, §3).
   **The wall sits between them.** That also explains, with no extra assumption, why a `MOVE_Falling`
   pawn with `GravityScale 1.000` does not fall: `PhysFalling` is dispatched *from* `StartNewPhysics`.

**And the bot is not specially disadvantaged — the player is in the same state:**

| field | BOT | PLAYER | |
|---|---|---|---|
| `UpdatedComponent` +0xD0 | `0x1F2CA524180` CapsuleComponent | `0x1F262903990` CapsuleComponent | same shape |
| `Mobility` +0x1BB | **2 (Movable)** | **2 (Movable)** | same |
| `Role` +0x160 | **3 (ROLE_Authority)** | **3** | same |
| `RemoteRole` +0x72 | 1 | 1 | same |
| `Controller` +0x400 | non-null | non-null | same |
| pawn `RF_Garbage` | 0 | 0 | same |
| `MovementMode` +0x231 | **3 MOVE_Falling** | **3** | same |
| `MaxAcceleration` +0x28C | 50000 | 50000 | same |
| `bCharacterMovementEnabled` +0xB59 | 1 | 1 | same |
| `Acceleration` +0x328 | (0,0,0) | (0,0,0) | same |
| `AnalogInputModifier` +0x3D0 | 0 | 0 | same |
| **`StartNewPhysics` latch +0x16C8** | **0** | **0** | same |
| `bCanEverTick` / `TickState` / `TickInterval` | 1 / Enabled / 0 | 1 / Enabled / 0 | same |
| `Prerequisites.Num` | 1 | 1 | same |
| `InternalData` +0x60 | non-null | non-null | same |
| **`bRegistered`** | **False** | **False** | same |
| `TaskPointer` / `LastTickGameTimeSeconds` | 0 / **-1.0** | 0 / **-1.0** | same |
| `bIsActive` / `bAutoActivate` | True / True | True / True | same |
| `AttributeSetStorage` +0xF08 | **NULL** | **NULL** | same |
| `AbilitySystemComponentStorage` +0xF00 | **NULL** | **non-null** | ← **the only structural difference** |
| `ControlInputVector` +0x418 | `(0.516,0.857,0)` live | (0,0,0) | expected — only the bot has an AI driving it |

**IDENTITY CONTROLS PASSED ON BOTH SIDES** — `CMC+0x198 (CharacterOwner) == pawn` and
`FTickFunction Target == CMC`. Without those, `+0x16C8` would have been read off `ALokiCharacter`,
which has its own live byte there.

⇒ ★★★ **S2 — "a per-instance byte between `HasValidData` and `ControlledCharacterMove` differs on a
hand-spawned AI pawn" — is REFUTED.** Every byte in that ladder is the same on a pawn that the
`play` shim CAN move and on one it never touches.

---

## 1. ★★ THE THIRD TIME THE QUESTION HAS BEEN MIS-FRAMED, IN THE SAME SHAPE

    S138 LivingState : every character reads Dead -- the bot is not special
    S138 MovementMode: bot and player are BOTH MOVE_Falling -- the bot is not special
    S139 the ladder  : every structural field identical -- the bot is not special

⇒ **The question is not "why does the BOT not move". It is "why does NO character move on this
route".** `play` never fixed that; it works around it by writing `CMC+0xE8` (Velocity) and
`CMC+0x328` (Acceleration) directly every game-thread hit, and S75 recorded in the shim's own source
that *forced `AddMovementInput` produced ZERO accel/velocity* **on the player too**.

**Successors should stop looking for a bot/player difference in the movement component.** There
isn't one.

---

## 2. RANK-2: `+0x12B0` ADVANCES AT WALL-CLOCK RATE — ON BOTH

    +  2.0s   bot 35.2023   player 382.376
    +  4.1s   bot 37.2356   player 384.409
    +  6.1s   bot 39.2693   player 386.475
    +  8.2s   bot 41.3027   player 388.508
    + 10.2s   bot 43.3361   player 390.541          (+2.03 per 2.0 s on both = 1.0x real time)

Something inside the movement component is being driven with **real, non-zero time** on both pawns.

★★★★★ **AND THE BYTES CLOSE IT: `+0x12B0` ACCUMULATES EXACTLY THE REGISTER HitStop WOULD ZERO.**
Disassembled from `dumps/merged13.dump.exe` after the flight (page `0x055B8000` = 3578/4096, LIT):

    0x055B838D  movaps xmm6, xmm1                 ; xmm6 = DeltaSeconds  (MS x64 float arg #2)
    0x055B83A9  xor    edx, edx                   ; NULL context
    0x055B83B3  mov    cl, 0x78                   ; game-feature toggle 120 = HitStop
    0x055B83B5  call   0x56e7c10
    0x055B83C1  lea    rcx, [r15 + 0x7f0]         ; CharacterOwner + 0x7F0
    0x055B83CB  call   qword ptr [rax + 0x10]
    0x055B83E2  mov    rdx, qword ptr [rip + ...] ; the tag global
    0x055B83E9  lea    rcx, [rbx + 0x148]
    0x055B83F3  call   qword ptr [rax + 0x18]     ; the tag query
    0x055B83FA  xorps  xmm6, xmm6                 ; *** THE DELTATIME KILL ***
    0x055B8403  call   qword ptr [rax + 0xab0]
    0x055B8409  movaps xmm0, xmm6
    0x055B840C  addss  xmm0, dword ptr [rsi + 0x12b0]
    0x055B8414  movss  dword ptr [rsi + 0x12b0], xmm0    ; +0x12B0 += xmm6

⇒ **`+0x12B0 += DeltaSeconds`, and `DeltaSeconds` lives in the very register `0x055B83FA` zeroes.**
If HitStop had fired, the accumulate would be `+= 0` and `+0x12B0` would be FROZEN.
**It advanced at 1.0× real time, on both pawns, over 5 samples each.**

⇒ ★★★★★ **S1 — the HitStop DeltaTime kill — is REFUTED [M], on the bot AND on the player.**
And in the same stroke: **`ULokiCMC::PerformMovement` IS RUNNING**, with a real non-zero DeltaTime,
on both. (It is the writer of `+0x12B0`; the only other toucher, `StartNewPhysics`'s
`Iterations > 0` arm at `0x055C2483`, is unreachable while the latch says StartNewPhysics never ran.)

★ This is the pre-registered P5 branch *"bot dt ADVANCING ⇒ S1 DEAD; the wall is inside
StartNewPhysics/PhysFalling"*, and it arrived with a mechanism rather than an inference.

---

## 3. ⚠⚠ THE RANK-1 BISECTOR DID NOT FIRE — ITS CONTROL FAILED, AND THAT WAS PRE-REGISTERED

`docs/s139-f1-PREREGISTERED.txt` **P2**: *"CONTROL: the PLAYER's `CMC+0x16C8` reads 1. REFUTED BY: 0.
Then the bisector is UNINTERPRETABLE this sitting … I will say so and will NOT read the bot's value
as a result."*

**The player's latch read 0**, so at read time the bot's 0 was **not** admissible as a result. Two
readings were open: (a) `StartNewPhysics` genuinely never runs for either character, or (b) the latch
is never set on the normal path — an instrument artifact, because the `cmp`/`je` polarity had been
taken from a lane's summary rather than read from the bytes.

~~★★ **RESOLVED AFTER THE FLIGHT, FROM THE BYTES — (b) IS REFUTED AND THE LATCH IS A VALID INSTRUMENT:**~~
⚠⚠⚠ **HALF-RESOLVED, AND THE VERDICT IS WRONG (S142).** Reading (b) — *"the latch is never set on the
normal path"* — really was refuted, and every byte below is correct. **But refuting ONE alternative
does not validate the instrument.** A THIRD reading was never enumerated and it is the true one:
**the latch is SET and then CLEARED within the same call.** Disp `0xA50` = `0x0530ABF0` clears it;
engine `PerformMovement` calls that slot at `0x035EB569`.
⇒ ★★★ **THE METHOD LESSON: refuting one alternative is not the same as validating the instrument.**
Enumerate the ways a flag can return to 0 — including the ones your hypothesis does not mention.
⇒ ★★ **AND THIS DOCUMENT'S OWN PRE-REGISTRATION (P2, quoted immediately above) WAS RIGHT.** It said
a player latch of 0 makes the bisector uninterpretable. That verdict should have been left standing;
overriding it is what turned a void sitting into a load-bearing `[M]`. Tabulated as `S140T1-g`.

    0x055C2433  test  r8d, r8d                        ; r8d = Iterations
    0x055C2436  jne   0x55c2475                       ; Iterations != 0 -> the other arm
    0x055C2438  cmp   byte ptr [rcx+0x16c8], r8b      ; r8b == 0 on this path
    0x055C243F  je    0x55c2448                       ; latch already 0 -> skip a REDUNDANT zero-store
    0x055C2441  mov   byte ptr [rcx+0x16c8], r8b      ; (only reached when latch != 0)
    0x055C2448  movups xmm0, [rcx+0xe8]  ...          ; snapshot Velocity -> +0x16B0
    0x055C2469  mov   byte ptr [rcx+0x16c8], 1        ; *** THE LATCH -- unconditional fall-through ***
    0x055C2470  jmp   0x3600990                       ; engine StartNewPhysics

The `je` skips only a redundant zero-store; **`mov byte [rcx+0x16C8], 1` sits on the unconditional
fall-through and runs every time `StartNewPhysics` is entered with `Iterations == 0`.**

~~⇒ ★★★ **`latch == 0` on BOTH pawns is a REAL MEASUREMENT: `ULokiCMC::StartNewPhysics` has NEVER been
called on either component.** Reading (a) is correct.~~
⚠⚠ **RETRACTED (S142).** The first half is true — it IS a real measurement. The second half does not
follow, and reading (a) is **UNGRADED**, not correct. See the banner.
⇒ Combined with §2: **`PerformMovement` runs with a real DeltaTime, and `StartNewPhysics` never
runs.** The wall is between them — a far narrower statement than anything this project has had.
~~⇒ It also explains, with no extra assumption, why a `MOVE_Falling` bot with `GravityScale 1.000`
does not fall: `PhysFalling` is dispatched *from* `StartNewPhysics`, which never runs.~~
⚠⚠ **VOID (S142).** `PhysFalling` really is dispatched only from `StartNewPhysics` (case 3 of the
bounded 8-entry table at `.text 0x03600BF8`), but the "which never runs" clause is gone, so this
explains nothing. ★ And the non-fall was later explained outright: **it was OURS** — `sp`'s
LIFT-TO-SEE step (`tutorial_launch.cpp:12877-12890`) sets `GravityScale = 0` on the player, and
`CMC+0x1A0` is `GravityScale` (S141 Tier 3).

★ The pre-registration is what kept this honest. Had P2 not been written down, `bot latch == 0`
would have been read as "S2 confirmed" — and §0 shows S2 is false. The *correct* use of the byte only
became available once its polarity was read from the bytes, which is exactly what P2 demanded.

---

## 4. WHAT ELSE IS NEW

- ★ **`Role` on a `SpawnAIFromClass`-spawned bot pawn is measured for the first time: 3
  (ROLE_Authority).** Pre-registered as P6. ⇒ ladder exits E6 and E7 are both eliminated.
- ★ **`bRegistered = False`, `TaskPointer = 0`, `LastTickGameTimeSeconds = -1.0` on BOTH CMCs** —
  never readable before this session (the S138 handoff recorded this state as structurally invisible).
  ⚠ **Do NOT read it as "the component never ticks":** `ControlInputVector` is consumed per-frame and
  `+0x12B0` advances per-frame, so something drives it. Either the decode is wrong or the component
  is ticked by a route other than its own registered tick function. **Open.**
- ★ **`AttributeSetStorage` is NULL on BOTH** (pre-registered P7) ⇒ `GetMaxAcceleration` /
  `GetMaxSpeed` collapse to 0 for both. A real wall, **shared**, and therefore not the differentiator.
  ⚠ Note `MaxAcceleration` (the CMC's own UPROPERTY) reads **50000** — that is the base property, not
  what the Loki override returns. Do not read 50000 as "acceleration is available".
- ★ **The one structural asymmetry is `AbilitySystemComponentStorage`: bot NULL, player non-null**
  (`KWIREGAS` wires the player's, and nothing wires the bot's). If `[ALokiCharacter+0x7F0]` is the
  ASC, then **S1 is dead for the bot by construction** — the HitStop tag query null-checks before it
  can fire. That is a free conditional kill and the offline transcription is settling it.

---

## 5. ⚠ INSTRUMENT DEFECTS FOUND AND FIXED IN THIS FLIGHT

Both were in the new probe, both produced a reading that looked exactly like a game fact:

1. **`fname` read the FNamePool block table at `NAMEPOOL + 0x10 + 8*blk`.** The correct form is
   `NAMEPOOL + 8*blk` (`tools/re/movementmode_readout.py` has it right). Every name decoded to `?`,
   so the probe reported **"NO PLAYER-CONTROLLED PAWN — RUN IS VOID"** on a healthy client with the
   player plainly present. **That reads exactly like "the object does not exist".**
2. **`findprop` read an `FField`'s name at `+0x28`.** It is at **`+0x20`**, the same offset as a
   `UObject`'s. Every by-name property lookup failed, and the probe reported **"no
   `CharacterMovement` UPROPERTY"** — which reads exactly like "this class has no such property".

★ **What caught both in minutes: running the known-good `movementmode_readout.py` as an INSTRUMENT
CONTROL against the same live process.** It found the player immediately, which localised the fault
to my probe rather than to the game. **Keep a second, already-trusted instrument on hand.**

⚠ A third, unfixed: `tools/usmapdump/usmapdump.exe dumpimage` printed
`ERROR: process "SUPERVIVE-Win64-Shipping.exe" not found (is the game running?)` — and this time the
client really had died. CLAUDE.md records that same message as a *false* negative when the suffix is
wrong. **The message is ambiguous between two causes; check `Get-Process` before believing either
reading** (I did, and it said `CLIENT IS GONE`).

---

## 6. ARTIFACTS

| path | what |
|---|---|
| `docs/s139-f1-PREREGISTERED.txt` | P1–P7 + "things I will not claim", unmodified |
| **`docs/s139-f1-BOT.txt`** | **the two-sided read + the 10 s `+0x12B0` series** |
| `docs/s139-f1-BASELINE.txt` | player-only baseline, taken before the injection |
| `docs/s139-f1-ticksniff-bot.txt` / `-player.txt` | full FTickFunction decode, both components |
| `docs/s139-f1-marker-armf.txt` | ARM D/B/C/F receipts (`GATE+0x6A0 0 → 1`, `[BS] done`) |
| `tools/re/cmc_earlyout_readout.py` | the probe; both defects fixed and annotated in-file |
| `scratchpad/s139/ticksniff.py` | the new tick-function instrument (22 passing offline controls) |

## 7. PREDICTION SCORECARD

| # | prediction | outcome |
|---|---|---|
| P1 | identity controls pass both sides | **HELD** |
| P2 | player latch == 1 | **FAILED** → bisector not obtained, as pre-registered |
| P3 | bot CIV is a unit vector, LastCIV tracks it | **HELD** — `(0.516,0.857,0)` on both fields |
| P4 | both `MOVE_Falling` under this build's table | **HELD** |
| P5 | the verdict rule | **not reachable** (P2 failed) |
| P6 | bot `Role` == 3 | **HELD** — first ever measurement |
| P7 | `AttributeSetStorage` NULL on both, not the cause | **HELD** |

## 7b. ★★★★★ THE BAIL IS NOW NAMED TO THREE INSTRUCTIONS (offline, after the flight)

**Loki's `PerformMovement` reaches its Super unconditionally.** Independently transcribed:
`0x055B85C1 call 0x35e9ec0` is engine `UCharacterMovementComponent::PerformMovement`, and the two
forward branches (`0x055B845E jne 0x55B85B4`, `0x055B8474 js 0x55B85B4`) land at `0x055B85B4` —
**just above the Super call**, skipping only a loop. So the bail is inside the ENGINE function.

Its gate cluster, all three sharing bail target `0x035EB7CF`:

    0x035E9F17  call qword ptr [rdx+0x6b8]        ; HasValidData   -> passes (measured)
    0x035E9F25  test r13,r13 / je                 ; World == null  -> passes
    0x035E9F90  cmp  byte ptr [rbx+0x231], r15b   ; MovementMode == MOVE_None?
    0x035E9F97  je   0x35eb7cf                    ;   MEASURED 3  -> PASSES
    0x035E9F9D  cmp  byte ptr [rcx+0x1bb], 2      ; Mobility == Movable?
    0x035E9FA4  jne  0x35eb7cf                    ;   MEASURED 2  -> PASSES
    0x035E9FB5  call qword ptr [rax+0x4c0]        ; UpdatedComponent->IsSimulatingPhysics(NAME_None)
    0x035E9FBD  jne  0x35eb7cf                    ;   *** NOT MEASURED -- THE PRIME SUSPECT ***

⇒ ★ **Of the three gates that stand between the Super and `StartNewPhysics`, two are measured
passing and the third — `IsSimulatingPhysics` on the hero's capsule — has never been read.**
It is **one read** (`bSimulatePhysics` on the capsule's `FBodyInstance`) and it is the first thing
the next sitting should do.
⚠ **Hold one tension honestly:** if the capsule really is PhysX-simulating, then writing `CMC+0xE8`
should not move the hero either — yet `play` reportedly moves it "WITH collision". Either that
observation needs re-checking under this lens, or `play`'s `SetMovementMode(5)` changes the state.
**Do not resolve that tension by assumption; measure `IsSimulatingPhysics` on both pawns.**

⚠ **Correction to the S139 synthesis:** it placed the single `call [rax+0x720]` (StartNewPhysics) at
`0x035EB7FA`. A scan of `0x035E9EC0..0x035EB810` finds exactly one, at **`0x035EB13A`**. Use that.

### ⚠⚠ ADJUDICATION — a second offline lane concluded "S1 SURVIVES". It is wrong, and here is why

A follow-up transcription lane argued: the HitStop block's zeroed DeltaTime *is* the one handed to
the Super; the Super is unconditional; engine `PerformMovement` has no delta gate; and a zero delta
is fatal one level down at engine `StartNewPhysics`'s `comiss xmm6, 1e-6f; jb` (`0x036009A8`).
Its code reading is right. **Its conclusion is refuted by two facts it did not have:**

1. **`+0x12B0 += xmm6`** (`0x055B8409`–`0x055B8414`) — the accumulator takes *the same register* the
   HitStop branch zeroes. **Measured live: it advances at 1.0× real time on both pawns.** If HitStop
   had fired, the accumulate would be `+= 0` and `+0x12B0` would be frozen. ⇒ **xmm6 ≠ 0.**
2. **The latch is set BEFORE the jump to the engine.** `0x055C2469 mov byte [rcx+0x16C8],1` then
   `0x055C2470 jmp 0x3600990`. So entering `ULokiCMC::StartNewPhysics` sets the latch *regardless of
   DeltaTime* — the `MIN_TICK_TIME` bail is downstream of it. ~~**latch == 0 therefore proves
   `StartNewPhysics` was never ENTERED**~~ ⚠⚠ **RETRACTED (S142): it proves nothing, because the byte
   is cleared later in the same `PerformMovement` call.** ★ Note the *set-before-the-jmp* observation
   is still correct and still useful — it means even a latch caught at **1** would only prove the
   vtable dispatch happened, not that the engine's own four gates passed.

⇒ **S1 stays refuted.** ★ Note the shape: the offline lane was correct about every byte and wrong
about the conclusion, because the discriminating facts were *live*. Neither half was sufficient
alone.

## 8. OPEN — and the next question is now small

Both post-flight offline items are **DONE** (§2, §3): the `+0x16C8` polarity is read and the
`+0x12B0` writer is identified. What remains:

- ★★★ **ONE READ: `UpdatedComponent->IsSimulatingPhysics()` on both pawns** (§7b). It is the only
  unmeasured gate between the Super and `StartNewPhysics`, and if it is TRUE it explains every
  observable at once. Read `bSimulatePhysics` on the capsule's `FBodyInstance`, plus the vtable
  call's own answer if a call is acceptable.
  Sub-question if it is FALSE: enumerate the remaining path `0x035E9FC3 .. 0x035EB13A` for further
  bails — that is ~4.5 KB and untranscribed.
- Why `bRegistered` is False on a component that is demonstrably being driven per-frame.
- ⛔ Unchanged: **not a bot.** `ServerSetHeroClass` / `SetPlayerTeam` are still stripped folds, and
  nothing here happens without pokes the game never performs itself.
