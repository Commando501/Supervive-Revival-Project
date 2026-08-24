# S139 — the CharacterMovementComponent tick ladder, transcribed; four hypotheses dead; two survivors

Written 2026-08-23. **Offline: zero launches, zero injections, zero `.text` writes** for everything in
§1–§6. Six RE lanes over `dumps/merged13.dump.exe`, each followed by an adversarial verifier whose
job was to refute it, then a synthesis that re-ran five checks itself. 13 agents, ~4.7 M tokens.

> ## ⚠⚠⚠ PARTIALLY SUPERSEDED — READ THIS FIRST (banner added S142, 2026-08-24)
>
> **WHAT STILL STANDS:** the transcription itself, the four dead hypotheses, and the
> `EMovementMode` finding (`MOVE_Dashing` inserted at index 6 ⇒ `MOVE_Custom == 7`) — all
> independently reproduced.
>
> **WHAT IS DEAD:** §5's bullet *"`+0x16C8` is a STICKY latch, never cleared"* is **flatly false**,
> and everything built on the latch as a bisector with it. Disp `0xA50` = `0x0530ABF0` clears the
> byte, called from engine `PerformMovement` at `0x035EB569`. It reads `0` in every world. See
> `docs/s140-tier1-cfg.md` §4. ⚠ The *other* §5 bullet — that `+0x16C8` collides with a live byte on
> `ALokiCharacter` — is **correct and still load-bearing**; keep it.
>
> **AND THE QUESTION IS ANSWERED THE OTHER WAY:** the engine mover chain runs. One
> `Velocity = (600,0,0)` kick makes the bot fall, land and walk **13,196 uu at 500.0 uu/s**,
> reproduced twice. See `docs/next-session-prompt-s142.md`.

Predecessor: `docs/s138-flight9b-flymode-refuted.md`. Its §2 conclusion is **retracted here**.

---

## 0. HEADLINE

**The handoff's standing hypothesis — "the controller ticks; the CMC does not" — is REFUTED, and
the reason it looked true is that `ConsumeInputVector` is called BEFORE the early-outs.**

    ULokiCharacterMovementComponent::TickComponent  0x055C2B90   (Loki override, slot 122 / +0x3D0)
      -> UCharacterMovementComponent::TickComponent 0x03603780
           0x036037FE  call [vt+0x640]  ConsumeInputVector      <-- FIRST. drains pawn+0x418.
           0x0360381D  HasValidData   0x035E64C0                <-- E1
           0x03603834  ShouldSkipUpdate 0x0364BA80              <-- E2
           ... E3 .. E7 ...
           0x03603B18  call [rax+0x890]  ControlledCharacterMove <-- the only route to PerformMovement

⇒ **the input can be consumed every frame while nothing downstream ever runs.** That single ordering
fact reconciles every S138 observation at once, and it is why three sessions of hypotheses died.

**The question is now precise:** which rung between `0x03603825` and `0x03603B18` does the BOT fail?
**Answer: NOT ESTABLISHED — two survivors, and one byte splits them.** See §4.

---

## 1. ★★★ THE MEASUREMENT THAT REFUTES THE HANDOFF (free, from data already on disk)

`docs/s138-f8-motion.txt`, all 194 samples, recomputed:

    |ControlInputVector|  min 0.0000   max 1.0001   (190 non-zero)
    |ControlInputVector| > 1.05 :  0 samples
    CIV == RandomMoveDirection exactly : 193/194
    distinct RandomMoveDirection runs  : 44   over 97 s

The write is `+=` (`APawn::Internal_AddMovementInput`, S137 transcription, re-confirmed this session
from `0x03BACBD0`). An **unconsumed** `+=` predicts:

| cadence | predicted \|CIV\| after 97 s | measured |
|---|---|---|
| per-frame @60 fps | ~5820 | **1.0001** |
| per-2 s re-randomisation | ~sqrt(44) = 6.6, **and not equal to the latest direction** | **1.0001, equal** |

⇒ **something zeroes it between every write ⇒ the consume runs ⇒ `TickComponent` is entered.**
Grade **[I, strong]**, not [M] — a second consumer exists (`APawn::ConsumeMovementInputVector`
`0x03B93470`, BlueprintCallable) and an async arm at `0x036037AF` skips the consume entirely. The
live observation excludes the async arm; the bare claim does not.

⇒ **RETRACTS** `docs/s138-flight9b-flymode-refuted.md` §2 ("the controller ticks; the CMC does not")
and `docs/s138-flight9-movement-not-simulating.md` §3 ("`ControlInputVector` is never zeroed").

---

## 2. ★★ `play` IS NOT THE MOVING CONTROL THE HANDOFF ASSUMED

The S139 handoff §1 said: *"run `play`, which DOES move the player here, and diff a moving CMC
against the bot's."* Right experiment, wrong reason — and the stated reason would have contaminated
the read.

**[M, source]** `tutorial_launch.cpp:1240` calls `DoWakeMove()` only under `RM_WAKEMOVE`; `:1275`
`RM_PLAY` calls `DoPlay()`. `DoPlay`'s one-shot init is exactly: teleport (unless `KNOTELE`) /
`GravityScale=1.0` / `ResetIgnoreMoveInput(PC)` / `SetMovementMode(KFLYMODE=5)` /
`SetActorHiddenInGame(false)` / body build. **It never calls `SetActive`,
`SetComponentTickEnabled` or `SetActorTickEnabled`** — those three are `DoWakeMove`'s (`:2983`).

And `play` moves the hero by **writing `CMC+0xE8` (Velocity) and `CMC+0x328` (Acceleration) every
game-thread hit** (`DoPuppet` `:3047`, the auto-walk block `:12599`).

★ The shim's own source has recorded the matching S75 measurement all along
(`tutorial_launch.cpp:364-366`): *"the stock input->acceleration path is dead in the un-deployed
force-open (**forced AddMovementInput produced ZERO accel/velocity**), but poking the CMC velocity
moves the hero WITH collision."* — i.e. **the PLAYER has the same input failure as the bot.**

⇒ Two consequences that govern every future read here:
1. **The player is a CONTAMINATED control on `+0xE8` and `+0x328`, by construction.** Use it on
   structural fields only (Role, UpdatedComponent, Mobility, tick state, `+0x16C8`).
2. `play-atlanding` moved the player **2,926 uu at CONSTANT Z = 13,240** because `KFLYMODE=5`.
   **"the player moved" never means "the player walked on terrain".**

⚠ And the "bot frozen vs player moves" contrast successors keep inheriting is **partly false**:
`docs/s138-flight9` §0 measures the PLAYER in the identical state — `MOVE_Falling`, `Velocity`
`(0,0,0)`, frozen at `(0,0,13240)`. What the player demonstrates is exactly one thing: **a movement
step that integrates `CMC::Velocity` runs for it.**

---

## 3. THE LADDER, AND WHAT IS NOW DEAD

`ULokiCharacterMovementComponent` vtable `.rdata 0x088F8570`, **413 slots, 64 overridden**
(verified by an independent qword diff against `UCharacterMovementComponent` `0x07FBED58`).

**Overridden and load-bearing:** 122/`0x3D0` TickComponent `0x055C2B90` · 153/`0x4C8` GetMaxSpeed
`0x055ACB90` · 206/`0x670` SetMovementMode · 228/`0x720` StartNewPhysics `0x055C2430` · 250/`0x7D0`
GetMaxAcceleration `0x055AC910` · 262/`0x830` PhysFalling `0x055B89F0` · 274/`0x890`
ControlledCharacterMove `0x055A7680` · 306/`0x990` PhysCustom · 327/`0xA38`
ConstrainInputAcceleration `0x055A75B0` · 341/`0xAA8` PerformMovement `0x055B8370`.
**NOT overridden:** ShouldSkipUpdate `0x0364BA80` · RequestPathMove `0x035F41D0` · ConsumeInputVector
`0x03627B90` · ComputeAnalogInputModifier · HasValidData `0x035E64C0` · ScaleInputAcceleration.

### REFUTED — do not re-open

| # | claim | why it is dead |
|---|---|---|
| 1 | **`IsLocallyControlled` / `IsLocalController` is the blocker** | [M] `APawn::IsLocallyControlled 0x03BAD240` is slot 271 in 13 pawn vtables with no override; `AController::IsLocalController 0x036E0830` is slot 265 in 6 controller vtables **including `ALokiBotController`**; and it returns TRUE on its first branch when `GetNetMode()==0`, which this NM_Standalone client is. **Two-sided control: `ALokiPlayerController` DOES override it (`0x03C40FD0`), so the census detects overrides.** Blueprint subclasses cannot override C++ virtuals, so this generalises to `BP_HERO_*`. |
| 2 | **`bUpdateOnlyIfRendered` is asymmetric by construction** (a bot 13 km up is never rendered) | [M] the `UMovementComponent` ctor writes `0xCE` to `+0x130` (`0x0361B5D0`/`0x0361B682`); **bit `0x01` is CLEAR by default.** |
| 3 | **"`Acceleration == 0` proves `ControlledCharacterMove` never ran"** | [M] refuted twice independently: `ULokiCMC::ConstrainInputAcceleration 0x055A75B0` writes a **literal zero** on a per-character predicate; and `ScaleInputAcceleration` multiplies by `GetMaxAcceleration`, which is 0 with no attribute set. **Three lanes proposed this as THE bisector; it is not one.** |
| 4 | **"the GAS zero fully explains the frozen bot"** | [M] it is a **lateral** term — it cannot suppress gravity in `MOVE_Falling` with `GravityScale 1.000` — and the condition is **shared with the player**. |
| 5 | **"`ConsumeInputVector` is the only consumer of `pawn+0x418`"** | [M] `APawn::ConsumeMovementInputVector 0x03B93470` inlines the same copy-and-zero. |
| 6 | **"`PrimaryComponentTick` is not a UPROPERTY"** (the S138 handoff) | [M] it **IS**, at `UActorComponent+0x40`. |

---

## 4. THE TWO SURVIVORS, AND THE ONE BYTE THAT SPLITS THEM

**S1 — DeltaTime is zeroed before the engine integrates.** `ULokiCMC::TickComponent 0x055C2B90`
reads game-feature toggle **120 (HitStop)** with a **NULL context**, then queries a gameplay tag on
the character (`[char+0x7F0] -> [vt+0x10] -> [obj+0x148] -> [vt+0x18]`, tag global `0x0A038448`),
and on TRUE does `xorps xmm6,xmm6` at `0x055C2C1B` before `call 0x3603780`. **A byte-identical block
re-fires inside `ULokiCMC::PerformMovement` at `0x055B83B5`/`0x055B83FA`.**
Fits **everything**: the consume still runs (downstream), CIV never accumulates, every early-out is
passed, `PerformMovement` is entered, `StartNewPhysics` is REACHED, then the engine bails on
`MIN_TICK_TIME` (1e-6 at `0x076B8E74`) ⇒ no gravity, bit-exact frozen position, a `MOVE_Flying` poke
inert. And it is **per-character**, so it can differ bot vs player. Grade: mechanism [M], firing [S].

**S2 — an early-out between `HasValidData` (`0x03603825`) and `ControlledCharacterMove`
(`0x03603B18`).** Ladder [M]; which byte [S]. Candidates in execution order: E1/E3 `HasValidData`
(`CMC+0xD0` UpdatedComponent, `CMC+0x198` CharacterOwner, `ObjectFlags+0x0C` bit30 RF_Garbage) ·
E2 `ShouldSkipUpdate` (Mobility `+0x1BB != 2`, the render term) · E4 CheckStillInWorld ·
E5 `IsSimulatingPhysics` · E6 `Role@pawn+0x160 <= 1` · E7 the `!IsLocallyControlled` fallthrough.

### ★★★★★ THE BISECTOR: `CMC+0x16C8`

`ULokiCharacterMovementComponent::StartNewPhysics 0x055C2430`, `Iterations == 0` path:

    0x055C2438  cmp byte [rcx+0x16C8], 0   / je
    0x055C2448  snapshot Velocity (CMC+0xE8/+0xF8) -> CMC+0x16B0/+0x16C0
    0x055C2469  mov byte [rcx+0x16C8], 1          <-- THE LATCH
    0x055C2470  jmp 0x3600990  (engine StartNewPhysics)

**There is NO DeltaTime test on that path**, and the engine's `MIN_TICK_TIME` bail is *downstream*.
Cross-check: engine `PerformMovement 0x035E9EC0` has **exactly one** `call [rax+0x720]`
(StartNewPhysics), at `0x035EB7FA`, with **zero** rip-relative float compares in between.

⇒ the latch is **dt-INDEPENDENT** and says precisely *"PerformMovement reached StartNewPhysics"* —
exactly what S1 and S2 disagree about.

    bot latch == 1  +  position frozen   =>  S1   (the DeltaTime kill).  S2 ELIMINATED.
    bot latch == 0                        =>  S2   (an early-out at or above PerformMovement).

Paired with **`CMC+0x12B0`** (`TimeSinceFallingStart`, dt-DEPENDENT, `addss` at `0x055B840C`):
frozen + latch 1 ⇒ **S1 confirmed**; advancing ⇒ S1 dead and the wall is inside
`StartNewPhysics`/`PhysFalling` (S3). ⚠ `+0x12B0` **frozen is ambiguous alone** — the `addss` is
downstream of the HitStop `xorps` — which is why three lanes proposing it standalone were all wrong.

Probe: **`tools/re/cmc_earlyout_readout.py`** (read-only), pre-registration
`docs/s139-f1-PREREGISTERED.txt`.

---

## 5. ⚠ INSTRUMENT TRAPS THIS WORK ADDED

- **`CMC+0x16C8` collides with a live byte on `ALokiCharacter`.** A probe aimed at the PAWN instead
  of the COMPONENT reads a plausible, moving, WRONG value. **Assert `CMC+0x198 == pawn` first**
  (the probe does, and declares the side VOID otherwise).
- ~~**`+0x16C8` is a STICKY latch, never cleared.** `1` means "reached at some point", not "this
  frame". No per-frame rate may be built on it.~~
  ⚠⚠⚠ **THIS BULLET IS FALSE AND IT IS THE TRAP THIS SECTION EXISTS TO CATALOGUE (retracted S142).**
  `+0x16C8` **IS** cleared — once per completed `PerformMovement`, by `ULokiCMC` vtable disp `0xA50`
  = `0x0530ABF0` (`cmp byte [rcx+0x16c8],0 / je / mov byte [rcx+0x16c8],0 / jmp 0x35D6790`), called
  at `0x035EB569` on a path the `StartNewPhysics` call site dominates. It is a per-frame
  `TOptional<FVector>` validity flag over the `+0x16B0` Velocity snapshot, named from its own
  consumer `GetRecentVelocity` (`.data 0x09BC9AD0` → impl `0x0530AC10`).
  ⇒ ★★★ **The real trap, tabulated as `S140T1-a`: the field was named "a latch" from the site that
  SETS it, and nobody enumerated the sites that CLEAR it.** For any flag you intend to sample,
  **enumerate the writers of ZERO before you name it** — this codebase makes set/clear pairs inside
  one call on purpose (`CMC+0x2E8` bit 6 is save/set/restore in the same function).
- ⚠⚠ **THIS BUILD'S `EMovementMode` IS MODIFIED: `MOVE_Dashing` is inserted at index 6, so
  `MOVE_Custom == 7`, `MOVE_MAX == 8`** [M, three instruments: the `.rdata` enumerator run at
  `0x07E10660`; `StartNewPhysics`'s 8-entry jump table at `0x03600BF8` bounded by `cmp esi,7`;
  `IsDashing 0x035E6810 = cmp byte [rcx+0x231],6`]. **`tools/re/movementmode_readout.py` carries
  stock UE's table and mis-decodes Loki custom modes by one.**
- ⚠⚠ **`bCharacterControllable (+0x6A0)` is on the CONTROLLER, not the character** — `SizeOfOuter`
  `0x6A8` vs `sizeof(ALokiCharacter) 0x1950`, and its writer also touches `[this+0x4B0]` Blackboard /
  `[this+0x498]` BrainComponent. `docs/s138-flight9` §2.2 said so; **the CLAUDE.md digest dropped it**
  — the "a digest is an instrument" pattern again.
- ⚠⚠ **`tools/strxref/vtables.py` uses a cached index built on `merged2`** (ImageBase
  `0x7FF6AF000000`) while `strxref.py` defaults to `merged13` (`0x7FF608F40000`). Two images and two
  bases behind one apparent instrument. `.rdata` vtable starts are safe; **every CODE grade must be
  re-read from `merged13`**.
- **A disp32 byte-pattern scan is a FLOOR, not a census** — the lanes' own scans missed
  `mov byte [rcx+0x16C8],1` at `0x055C2469` (short encoding) and produced a phantom at `0x03D3A13A`.
- **An offset is not a field across classes.** An image-wide displacement census can never answer
  "who touches field X" — `call [reg+0x640]` returns 16 sites, several of them Wwise.

## 6. ⚠ CONTRADICTIONS CAUGHT BETWEEN LANES (worth more than the agreements)

- **Loki CMC override count: lane 6 said 3, lane 2 said 65, verifiers said 64 and 69. Truth: 64 of
  413.** 69 = the same diff run 5 slots past the class boundary. **Lane 6 built its entire argument
  and its entire live plan on functions it believed were stock engine code, and three of them —
  `ControlledCharacterMove`, `PerformMovement`, `ConstrainInputAcceleration` — are Loki overrides.**
- One verifier claimed `vtables.py` mis-attributes `UActorComponent`'s subobject vtables. **FALSE** —
  it agrees with the ctor bytes. A *fabricated* instrument defect, caught before it reached docs.
- One verifier called the HitStop toggle "readable offline, free". **Wrong**: id 120 misses the
  fast-path mask `0x22401` (bits {0,10,13,17} = ids {106,116,119,123}) and takes a slow path that
  resolves through **TLS**. Live it is one read; offline it is ambiguous.

## 7. OPEN

- **The flight has not been run** at the time of writing §1–§6. Everything above is offline.
- `ULokiCMC::PerformMovement 0x055B8370` and `PhysFalling 0x055B89F0` (a Loki override, and the leaf
  that would actually move a `MOVE_Falling` pawn) are **untranscribed**. Nobody has opened either.
- ~52 of the 64 Loki CMC overrides are ungraded. Slots 205/342/343/350/398/411 fill engine **folds**
  — extension points that do nothing in stock UE and something in Loki.
- ⛔ Unchanged: **this is not a bot.** `ServerSetHeroClass` / `SetPlayerTeam` remain stripped folds,
  and none of it happens without pokes the game never performs itself.
