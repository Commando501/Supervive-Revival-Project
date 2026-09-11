# S138 flight 9b — MovementMode is not the blocker either, and a flight-9 offset was wrong

Written 2026-08-23. Pre-registration: `docs/s138-f9b-PREREGISTERED.txt` (UNEDITED, written before
the first attempt and unchanged for this one). Predecessor:
`docs/s138-flight9-movement-not-simulating.md`.

---

## 0. HEADLINE

**R1 and R2 hold. R3 and R4 fail. Forcing `MOVE_Flying` does not make the bot move.**

    A BASELINE   mode=3 (Falling)  gate=1  plr_mode=3  Vel=(0,0,0)  CIV=(0.959,-0.284,0)  loc=(600.0,0.0,13240.0)
    B POKE  bot CMC MovementMode = 5      READBACK=5
      B+0s … B+24s   mode=5 (Flying)  gate=1  plr_mode=3  Vel=(0,0,0)  loc UNCHANGED
                     CIV churning: (-0.844,-0.536,0) (-0.980,0.200,0) (0.320,0.948,0) (0.998,-0.059,0) …
    C RESTORE = 3                          READBACK=3

| # | prediction | result |
|---|---|---|
| **R1** | poke lands, readback == 5 | **HOLDS** — held across all 25 samples / 25 s |
| **R2** | PLAYER's CMC untouched, still mode 3 | **HOLDS** — `plr_mode=3` at every timepoint |
| **R3** | Velocity becomes non-zero | **FAILED** — `(0,0,0)` throughout |
| **R4** | pawn location changes | **FAILED** — frozen at `(600.0, 0.0, 13240.0)` |
| R5 | restore stops it | **HOLDS** — readback 3 |

★ Throughout the whole 25 s the AI kept producing a fresh wander direction every ~2 s
(`ControlInputVector` visibly churning). **The bot is thinking the entire time and not moving.**

⇒ Per the pre-registration's own honest alternative: **the mode is NOT the blocker either.** The
standing candidate is that the movement component does not TICK — and **no poke fixes that.**

---

## 1. ⚠⚠ A CORRECTION TO FLIGHT 9 — MY VELOCITY OFFSET WAS WRONG

This flight resolved `Velocity` **BY NAME at `CMC+0xE8`**.
Flight 9's quick velocity time series **hardcoded `+0xE0`** (stock `UMovementComponent::Velocity`).
**Those are different fields. The flight-9 time series was reading the wrong offset.**

★ The flight-9 write-up flagged exactly this risk in advance:
> ⚠ *The velocity time series hardcoded `Velocity` at CMC+0xE0 … the time series alone is a
> hardcoded read and should be re-done by name if it is ever load-bearing.*

**It has now been re-done by name, over 25 samples, and the finding is unchanged: `Velocity` is
`(0,0,0)`.** So flight 9's *conclusion* survives — it also rested on the main readout's by-name
single read, which was correct — but its **8-sample time series should not be cited**, and
`docs/s138-f9-velocity.txt` carries a wrong-offset column.
⇒ ★ The general rule this re-confirms: **a hardcoded offset that "agrees" with a by-name read is not
corroboration if both can read zero.** Resolve by name, or state the read as unverified.

---

## 2. THE COMPONENT IS ACTIVE — so "deactivated" is refuted too

Read on BOTH components in the same pass:

| | BOT CMC | PLAYER CMC |
|---|---|---|
| `bIsActive` | **True** | **True** |
| `bAutoActivate` | **True** | **True** |
| `bTickBeforeOwner` | True | True |

So the component is not deactivated, on either pawn. That removes the simplest form of the
"doesn't tick" hypothesis.

★★ **AND THE SHAPE OF THE REMAINING PROBLEM IS NOW PRECISE.**
`ALokiBotController::Tick` **is running** — `RandomMoveDirection` re-randomises every ~2 s, which
only Tick does. So the **controller ticks**. But `ControlInputVector` is **never consumed**, and
stock UE zeroes it inside `UCharacterMovementComponent::TickComponent` every movement tick.

⇒ **The controller ticks; the character movement component does not.** That is a far narrower
statement than "the world is not simulating", and it is what the next work should target.

⚠ **NOT ESTABLISHED:** why. `PrimaryComponentTick` is an `FTickFunction` **struct member, not a
UPROPERTY**, so none of the reflection-based probes in `tools/re/` can see its `bRegistered` /
`bCanEverTick` / `TickGroup`. That read has to be built from an offline offset first — it is not a
gap in the evidence so much as a gap in the instrument.

---

## 3. WHAT IS NOW REFUTED, IN ORDER

Three successive hypotheses for "why does the bot not move", each killed by measurement:

1. ~~`LivingState` / the gate~~ — flights 6–8: the gate opens legitimately and the AI runs.
2. ~~`MovementMode` is wrong (`MOVE_None` / groundless `MOVE_Walking`)~~ — flight 9: bot and player
   are **both** `MOVE_Falling`.
3. ~~Forcing `MOVE_Flying` (what `play` does for the player)~~ — **this flight**: no effect.
4. ~~The component is deactivated~~ — this flight: `bIsActive = True` on both.

**Standing:** the movement component's tick is not running. Untested, and currently unreadable with
the existing tools.

⚠ Note what this does *not* say. `play` demonstrably moves the PLAYER hero on this route, so the
CMC clearly *can* simulate here. The difference between "player under `play`" and "bot under ARM F"
is therefore the thing to isolate — and `play` does more than set a mode: it drives input from the
game thread each tick and teleports first. **Matching only the mode was never expected to be
sufficient, and the pre-registration said so.**

---

## 4. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-f9b-PREREGISTERED.txt` | R1–R5 and the honest alternatives, unmodified |
| **`docs/s138-f9b-flymode.txt`** | **the A-B-A: 25 samples at `MOVE_Flying`, zero velocity, frozen** |
| `docs/s138-f9b-marker-armf.txt` | ARM F on this client (gate 0 → 1) |
| `docs/s138-Loki-flight9b.log` | client log |
| `tools/re/flymode_poke.py` | the arm; verdict computed from observed samples, refuses on a dead client |

⚠ `docs/s138-f9-velocity.txt` (flight 9) contains a **wrong-offset** Velocity column — see §1.

Client was still alive at write-up. Arms unchanged: `driverecompute` RAW `a2a952babfed256b`;
regression gate `botai` `5e47c13cf7f0a158`.

---

## 5. NEXT

**Not another poke.** The next step is a read, and it needs an instrument that does not exist yet:
the offset of `UActorComponent::PrimaryComponentTick` and a decode of its `FTickFunction`
(`bRegistered`, `bCanEverTick`, `TickGroup`, `bTickEvenWhenPaused`), read on the bot CMC **and** on
the player CMC as the control. That is offline work on the dumped image, then one cheap live read.

★ The single most informative comparison available: run `play` (which moves the player) and read the
player CMC's tick state **while it is actually moving**, against the bot's. That gives a known-good
positive control for whatever field turns out to matter — the control every previous "why doesn't it
move" hypothesis has lacked.
