# S138 flight 8 — THE BOT'S AI RUNS END TO END. Only the physical displacement fails.

Written 2026-08-23. Predecessors: `docs/s138-flight7-recompute-drives-the-gate.md` (which reached
this state and lost it to FK-32 seconds later), `docs/s138-livingstate-writers-settled.md`.

---

## 0. HEADLINE

**With the gate opened legitimately by the game's own `UpdateCharacterControllable`, the
`ALokiBotController`'s wander driver RUNS, produces a fresh direction every ~2 s, and delivers it
into the pawn's movement input — and the pawn does not move one unit.**

    time      GATE Living force Blackboard      RandomMoveDirection        ControlInputVector         location
    +29.8s     1     1     0    0x2539764BC00   (0.0000,0.0000,0.0000)     (0.0000,0.0000,0.0000)     (600.0,0.0,13240.0)
    +31.3s     1     1     0    0x2539764BC00   (-0.1215,0.9926,0.0000)    (-0.1215,0.9926,0.0000)    (600.0,0.0,13240.0)
    +33.3s     1     1     0    0x2539764BC00   ( 0.1397,0.9902,0.0000)    ( 0.1397,0.9902,0.0000)    (600.0,0.0,13240.0)
    +126.4s    1     1     0    0x2539764BC00   ( 0.0079,1.0000,0.0000)    ( 0.0079,1.0000,0.0000)    (600.0,0.0,13240.0)

**194 samples over ~97 s.** The failure is now **past the motor**, in a place this project has never
looked.

---

## 1. WHAT IS MEASURED [M]

| observable | result |
|---|---|
| gate `+0x6A0` | **1**, opened by ARM F's call to `UpdateCharacterControllable` (prologue byte-matched, `faulted=0`) |
| `LivingState` | **1 (Alive)**, held for the whole window |
| `ForceCharacterNotControllable +0x602` | 0 throughout — the gate is not being forced shut |
| `Blackboard +0x4B0` | **`0x2539764BC00`, NON-NULL** — the remaining candidate precondition is satisfied |
| **`RandomMoveDirection +0x658`** | **44 distinct non-zero values over 194 samples** |
| **`ControlInputVector +0x418`** | **equal to `RandomMoveDirection` in 193 of 194 samples** |
| **pawn location** | **exactly ONE distinct value across all 194 samples** |

★★ **THE WANDER DRIVER IS GENUINELY RUNNING, and the data matches the offline transcription in
three independent ways:**
1. Every direction is a **horizontal unit vector with Z exactly `0.0000`** — precisely what S137's
   transcription of `ALokiBotController::Tick` said it produces.
2. **44 changes over 97 s ≈ one per 2.2 s**, against the transcribed **2.0 s** re-randomisation.
3. The values are unit-length and randomly oriented, i.e. a wander, not a fixed heading.

★★ **AND THE MOTOR CHAIN IS CONFIRMED IN FLIGHT.** `RandomMoveDirection` lives on the CONTROLLER
(`0x25490FEE040+0x658`) and `ControlInputVector` on the PAWN (`0x255573A8020+0x418`) — different
objects — yet they agree in **193/194** samples. That is the S138-documented chain
`[CMC vtable+0x5E0] RequestPathMove → UPawnMovementComponent::RequestPathMove →
APawn::Internal_AddMovementInput → ControlInputVector += RandomMoveDirection`
**observed working, rather than inferred from disassembly.** (The single `DIFF` sample is one read
straddling a re-randomisation — the expected artifact of sampling an unsynchronised pair.)

⇒ **Behaviour tree → blackboard → wander driver → movement input: all working.** Everything this
project has been chasing since S136 is now demonstrated live, in one client.

---

## 2. ★★ THE NEW FRONTIER, AND THE DATA ALREADY POINTS AT IT

**`ControlInputVector` is holding a steady non-zero value — and that is itself the diagnosis.**

In stock UE, `ControlInputVector` is **consumed and zeroed every movement tick** by
`APawn::ConsumeMovementInputVector`, which the character movement component calls as it applies the
input. A value that persists across many samples means **nothing is consuming it** — i.e. the
movement component is not processing input at all.

So the failure is not "the AI does not decide" and not "the input does not arrive". It is:
**the CharacterMovementComponent is not turning input into displacement.**

Named candidates, in the order they should be read (all read-only):
1. **`MovementMode`** on the pawn's `ULokiCharacterMovementComponent`. CLAUDE.md records that the
   PLAYER hero is forced to `MOVE_Flying` (`KFLYMODE=5`) precisely because the Walking-mode ground
   chain does not work on this route. A bot pawn from `SpawnAIFromClass` gets **no such treatment**,
   so `MOVE_None` or a groundless `MOVE_Walking` are both live possibilities.
2. **The pawn is at Z = 13240.** That is the `sp` LIFT position (hero lifted +1800), i.e. **~13 km
   above the island with nothing underneath**. CLAUDE.md already records that `play-atlanding`
   "moved 2,926 uu at CONSTANT Z = 13,240, i.e. 13 km IN THE AIR" *only because* `KFLYMODE`
   defaults to flying. A Walking-mode pawn there has no floor to walk on.
3. Whether the CMC is **ticking at all** (`bIsActive`, tick function registration).

⚠ **Candidate 2 is the one I would test first, and it is cheap:** the bot spawned at
`(600, 0, 13240)` — the same altitude as the player hero, which only moves because it is flying.
**This may not be a bot problem at all; it may be the staging altitude.**

---

## 3. ⚠ WHAT IS NOT SHOWN

- **That the bot would move on the ground.** Untested. §2 is a hypothesis with three named
  candidates, not a finding.
- **That any of this survives without the pokes.** The gate was opened by ARM F after an artificial
  `LivingState` poke; nothing here makes the game do this by itself. `LivingState` still has no
  writer that sets Alive, and the state-machine bridge is still the void fold.
- **`IsStunned`** — the gate's second conjunct — remains unmeasured; ARM F simply demonstrates the
  whole gate expression evaluated true, without decomposing it.
- ⛔ **Still not a working bot.** `ServerSetHeroClass` and `SetPlayerTeam` remain stripped folds; the
  bot has no hero class or team assignment. A wandering pawn is not a bot.
- The external-write question from flight 6 is untouched here (this flight used no external write —
  ARM F does its poke in-process).

---

## 4. METHOD — the ordering fix that made this possible

Flight 7 reached this exact state and **lost it**: the client died seconds after ARM F, before the
motion chain could be read. The fix was purely one of ordering:

**Start the reader BEFORE the injection.** `tools/re/motion_watch.py` polls the `GUObjectArray` until
a `LokiBotController` appears (i.e. until ARM D has run), then tight-samples the whole chain every
0.5 s with timestamps, and exits cleanly the moment the process goes away. It found the controller
at **t=+29.8 s** and captured **194 samples over 97 s** — a window flight 7 missed entirely.

★ **Reusable: when the observable is downstream of an injected arm and the client dies
unpredictably, the reader must already be running when the arm fires.** Polling after the fact
races a process with a ~4–7-injection life expectancy.

---

## 5. ARTIFACTS

| path | what |
|---|---|
| **`docs/s138-f8-motion.txt`** | **194 timestamped samples — the whole chain** |
| `docs/s138-f8-marker-armf.txt` | ARM F: signature match, call, gate 0 → 1 |
| `docs/s138-Loki-flight8.log` | client log |
| `tools/re/motion_watch.py` | the watcher; carries its own rationale and refuses on a dead client |

Arms: `driverecompute` RAW **`a2a952babfed256b`** (unchanged from flight 7);
regression gate `botai` **`5e47c13cf7f0a158`** unchanged.
Client ended in FK-32 (no crashpad, no `Fatal`) **after** the full window was captured.

---

## 6. THE CHAIN NOW

    nothing writes LivingState=Alive                                    [M, offline]
      -> poke it, then call UpdateCharacterControllable                 [M, ARM F, flight 7+8]
      -> the gate +0x6A0 opens                                          [M]
      -> Tick's wander driver runs, 44 fresh unit directions / 97 s     [M, flight 8]
      -> ControlInputVector receives them, 193/194                      [M, flight 8]
      -> ??? the movement component never consumes the input, and the pawn never moves

**Next, and it is three read-only reads:** `MovementMode` on the bot pawn's CMC, the same on the
player hero as a positive control, and the bot's Z relative to any ground. If the answer is
"Walking at 13 km with no floor", the fix is staging, not code.
