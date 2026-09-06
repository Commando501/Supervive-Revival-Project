# S138 flight 9 — MovementMode is NOT the blocker. The movement component is not simulating at all.

Written 2026-08-23. Read-only RPM throughout except ARM F's own in-process poke.
Predecessor: `docs/s138-flight8-the-bot-thinks.md`, whose §2 hypothesis this **refutes**.

---

## 0. HEADLINE

**My leading hypothesis was wrong.** Flight 8 predicted the bot would differ from the player in
`MovementMode` — `MOVE_None`, or a groundless `MOVE_Walking`. Measured:

| | BOT (`SpawnAIFromClass`) | PLAYER (positive control) |
|---|---|---|
| CharacterMovement | `LokiCharacterMovementComponent` @ pawn+0x458 | same class |
| **MovementMode** | **3 = `MOVE_Falling`** | **3 = `MOVE_Falling`** — **IDENTICAL** |
| GravityScale | **1.000** | 0.000 (zeroed by `sp`'s LIFT step) |
| MaxWalkSpeed / MaxFlySpeed | 180 / 600 | 180 / 600 |
| UpdatedComponent | non-null | non-null |
| **Velocity** | **(0,0,0)** | (0,0,0) |
| ControlInputVector | fresh wander vector every ~2 s | (0,0,0) |
| location | frozen `(600.0, 0.0, 13240.0)` | frozen `(0.0, 0.0, 13240.0)` |

⇒ ★★ **The real finding is sharper than the hypothesis it replaces: a body in `MOVE_Falling` with
`GravityScale = 1.0` whose `Velocity` is EXACTLY zero for 8 s is not being simulated.** Gravity alone
would put a large negative number in `Velocity.Z` within a single frame.

**The character movement component is not running.** Not "in the wrong mode" — not running.

---

## 1. THE MEASUREMENT

`tools/re/movementmode_readout.py` (new), everything resolved BY NAME off the live class, with the
player hero read in the same pass as the positive control. Then an 8-sample velocity time series:

    t        BOT Velocity          PLAYER Velocity       BOT ControlInputVector    BOT loc
    +0.0s    (0.000,0.000,0.000)   (0.000,0.000,0.000)   ( 0.594, 0.805,0.000)     (600.0,0.0,13240.0)
    +2.0s    (0.000,0.000,0.000)   (0.000,0.000,0.000)   (-0.043, 0.999,0.000)     (600.0,0.0,13240.0)
    +4.0s    (0.000,0.000,0.000)   (0.000,0.000,0.000)   (-0.630,-0.777,0.000)     (600.0,0.0,13240.0)
    +6.0s    (0.000,0.000,0.000)   (0.000,0.000,0.000)   ( 0.309, 0.951,0.000)     (600.0,0.0,13240.0)

The AI keeps producing a fresh direction every ~2 s throughout — the wander driver is alive and
feeding the pawn — and the body never acquires velocity or position.

★★ **AND THE PLAYER IS IN THE SAME STATE.** `MOVE_Falling`, `Velocity` zero, frozen. It only moves
when the `play` shim is injected, and CLAUDE.md records that `play` explicitly sets **`KFLYMODE=5`
= `MOVE_Flying`** "to bypass the Walking-mode ground-mantle chain", noting the result "hovers; it
passes anywhere".
⇒ **This is a property of the force-open route, not of the bot** — exactly the same shape as the
`LivingState` result, where every character reads Dead and the bot is not specially disadvantaged.
A third-party hero pawn read the same way (`MOVE_Falling`, gravity 1.0, Velocity 0), so it is not a
two-sample coincidence.

---

## 2. ⚠ INSTRUMENT CAVEATS — three defects found and fixed, and one assumption

1. **The enum did not resolve, and that is EXPECTED, not a fault.** `MovementMode` is a
   `TEnumAsByte<EMovementMode>`, i.e. a **ByteProperty**, so `FEnumProperty::Enum` (`*(prop+0x78)`)
   does not apply to it. The *numeric* value is resolved by name at `+0x231`; the decode uses stock
   `EMovementMode` numbering, corroborated independently by CLAUDE.md recording `KFLYMODE=5 ==
   MOVE_Flying`. **Fixed:** the tool now says so instead of printing a bare "unresolved".
2. **The probe printed `(controller gate +0x6A0 = 1)` for the PLAYER controller.** `+0x6A0` is
   `bCharacterControllable` on **`ALokiBotController` only**; on a `BP_LokiPlayerController_Dev_C`
   it is a different field entirely, and the line read like a meaningful gate value. **Fixed:** the
   line is now printed only when the controller really is a `LokiBotController`, and otherwise says
   why it is being withheld. ⚠ **Disregard that line in `s138-f9-mm-BASELINE.txt`.**
3. **`bCheatFlying` was printed as a bool but is a UHT BITFIELD.** The values `8` (player) and `0`
   (bot) are RAW BYTES at the property offset, not booleans. **Fixed:** now labelled as such.
   ⚠ Do not read "player bCheatFlying = 8" as "cheat-flying is on".
4. ⚠ **The velocity time series hardcoded `Velocity` at CMC+0xE0** (stock `UMovementComponent`).
   It is corroborated — the by-name resolve in the main readout gave the same `(0,0,0)` — but the
   time series alone is a hardcoded read and should be re-done by name if it is ever load-bearing.

---

## 3. WHAT THIS REFUTES, AND WHAT IT LEAVES

**REFUTED:** flight 8 §2 candidate 1 ("`MovementMode` is `MOVE_None` or a groundless
`MOVE_Walking`"). Both pawns are `MOVE_Falling` and identical.

**WEAKENED:** flight 8 §2 candidate 2 (the Z=13240 altitude). The altitude may still matter for
*where* it would go, but it cannot explain zero velocity under gravity 1.0 — a falling body needs no
floor to accumulate downward speed.

**STANDING:** flight 8 §2 candidate 3 — **the component (or the actor) does not tick.** That is now
the leading explanation and it is consistent with every observation: no gravity integration, no
input consumption (`ControlInputVector` is never zeroed, which stock UE does every movement tick),
no position change, for both the bot and the player.

⚠ **NOT ESTABLISHED:** *why* it does not tick. Component tick registration, actor tick, world
partition cell state and a paused/idle world are all untested. I did not find `bIsActive` or the
tick-function state in the property sweep, so that read still has to be built.

---

## 4. THE NEXT EXPERIMENT — pre-registered, NOT OBTAINED

`docs/s138-f9b-PREREGISTERED.txt` was written while the client appeared alive: poke the bot's
`CMC+0x231 = 5` (`MOVE_Flying`) — one aligned DATA byte, the same class as every poke this session —
with the player's CMC left unwritten as the specificity control, and R1–R5 stated.

**The client died before it could run. 9b is NOT OBTAINED — that is not a null**, and the
pre-registration stands unmodified for the next sitting.

★ **Why it is the right next test:** `play` makes the *player* hero move on this exact route by
doing exactly this — setting `MOVE_Flying`. The bot already has what the player lacks: a live
`ControlInputVector`. If mode is the only missing piece, the bot should move.
⚠ Its pre-registration already names the honest alternative: `play` also drives input and teleports,
so matching only the mode may be insufficient, and a null would **not** show flying is irrelevant.

---

## 5. ARTIFACTS

| path | what |
|---|---|
| `tools/re/movementmode_readout.py` | the probe; three defects fixed and documented in-file |
| `docs/s138-f9-mm-BASELINE.txt` | bare staged world (player only) ⚠ its `+0x6A0` line is the fixed defect |
| **`docs/s138-f9-mm-COMPARISON.txt`** | **bot vs player vs a third hero — all `MOVE_Falling`** |
| **`docs/s138-f9-velocity.txt`** | **8-sample velocity series: zero throughout, input churning** |
| `docs/s138-f9b-PREREGISTERED.txt` | the `MOVE_Flying` poke, pre-registered, NOT OBTAINED |

---

## 6. THE CHAIN NOW

    LivingState poked Alive -> UpdateCharacterControllable -> gate opens        [M]
      -> wander driver runs, 44 directions / 97 s                                [M]
      -> ControlInputVector receives them, 193/194                               [M]
      -> MovementMode is MOVE_Falling, same as the player                        [M, this flight]
      -> Velocity stays exactly 0 under GravityScale 1.0                         [M, this flight]
      -> ??? the movement component is not simulating -- cause UNKNOWN

⛔ Unchanged: this is a diagnosis, not a bot. `ServerSetHeroClass` / `SetPlayerTeam` are still
stripped folds, and nothing here happens without the pokes.
