# S138 flight 7 — the recompute OPENS THE GATE; the gate alone does NOT produce motion

Written 2026-08-23. Pre-registration: `docs/s138-f7-PREREGISTERED.txt` (UNEDITED).
Predecessors: `docs/s138-flight6-livingstate-poke.md`, `docs/s138-livingstate-writers-settled.md`.

---

## 0. HEADLINE — two results, one positive and one negative, both pre-registered

**ARM F: F1–F5 ALL HIT. The game's own function opened the gate.**

    [PS] ARM F BEFORE: ctl=0x25A9B02C870 pawn=0x259D2A50040  LivingState=0  GATE+0x6A0=0  force+0x602=0
    [PS] ARM F: poked pawn+0x1090 = 1 (Alive)  READBACK=1
    [PS] ARM F: target=0x7FF6D5500B80 rva=0x5570B80
                prologue=40 57 48 83 EC 20 80 B9 02 06 00 00 00 48 8B F9
                -> SIGNATURE MATCHES UpdateCharacterControllable
    [PS] ARM F AFTER (faulted=0): LivingState=1  GATE+0x6A0=1  (was 0)

**6b: Q1 HOLDS, Q2–Q4 FAIL. Forcing the gate does NOT make the bot move.**

    B POKE controller+0x6A0 = 1    READBACK=1
      B+2s … B+12s   GATE=1  RandDir=(0,0,0)  CIV=(0,0,0)  loc=(600.0,0.0,13240.0)  UNCHANGED
    C RESTORE = 0                  GATE=0

⇒ **The `LivingState → UpdateCharacterControllable → bCharacterControllable` chain is now
demonstrated end to end through the game's own logic** — not by forcing the flag.
⇒ **And the gate is necessary but NOT sufficient for motion.** There is a further precondition.

---

## 1. ARM F — the recompute works [M]

| # | prediction | result |
|---|---|---|
| F1 | ARM D produces a `LokiBotController` | **HIT** |
| F2 | input poke `pawn+0x1090 = 1` lands | **HIT** — READBACK=1 |
| F3 | the 16-byte prologue at `0x5570B80` matches the offline transcription | **HIT** — byte-exact |
| F4 | the call does not fault | **HIT** — `faulted=0` |
| **F5** | **the gate opens, `+0x6A0` 0 → 1** | **HIT** |

★ **This is the causal link flight 6 could not make.** Flight 6 showed that poking `LivingState`
alone leaves the gate at 0, and pre-registered the reason: `+0x6A0` is a **cached** flag recomputed
on a state-change event. Flight 7 supplies the missing event — and the gate moves. The prediction,
its mechanism, and its remedy were all written down before either flight.

★ **F3 matters more than it looks.** The arm REFUSES unless the bytes at `0x5570B80` are the
function transcribed offline, so `faulted=0` plus a gate change cannot be a call into something
else. `force+0x602 = 0` at entry was also read and printed **before** the call — which matters
because the transcribed prologue shows that on the force branch the function *stores 0* into the
gate, and a 0 afterwards would then have been expected and uninterpretable. It was 0, so that
branch was not taken.

★ **CONTROL, and it is a real one:** `driverecompute-ctrl` (ARM F compiled out, `KBSPSARMS=0x20`)
was injected FIRST into this same client. It printed `ARM F SKIPPED by KBSPSARMS bit7`, produced a
`LokiBotController`, and the gate read **0** — confirmed independently by the external dry run
(`GATE+0x6A0=0 force+0x602=0`). So the gate does not open by itself, and the treatment/control pair
differ in exactly one compiled-out arm. Static two-sided check before the flight: 6/6 rows, the
ARM F banner / signature gate / call present ONLY in the treatment.

---

## 2. 6b — the gate is NOT sufficient [M]

Poked `controller+0x6A0 = 1` externally, on the control-arm client, and held it for **12 s** across
6 samples:

| # | prediction | result |
|---|---|---|
| Q1 | readback returns 1 | **HIT** |
| Q2 | `RandomMoveDirection (+0x658)` becomes a non-zero unit vector within ~2 s | **FAILED** — stayed (0,0,0) |
| Q3 | `ControlInputVector (+0x418)` becomes non-zero | **FAILED** |
| Q4 | the pawn's location changes | **FAILED** — `(600.0, 0.0, 13240.0)` throughout |
| Q5 | restore stops it | **HIT** |

★★ **A FREE SECOND RESULT: the gate STAYED 1 for 12 s and was never recomputed back to 0.** The
pre-registration named this exact observable — *"if `+0x6A0` reads back 1 and then returns to 0
WITHOUT me restoring it, that proves `UpdateCharacterControllable` is actively running"*. It did
**not** return to 0. ⇒ **the recompute is NOT running on a tick or timer**, which independently
confirms the cached-flag model that flight 6 predicted and ARM F exercised.

⇒ The wander driver has a **further precondition beyond the gate**. The pre-registration named the
candidate in advance: S137 recorded that the driver also gates on a **blackboard bool key**
(`.data 0xA0348F0`), and `UpdateCharacterControllable`'s own prologue dereferences the Blackboard at
`+0x4B0`. **This is a located next step, not a refutation of anything.**

⚠ **6b and ARM F did NOT reach the same state, and the difference is the open question.**
6b had `gate=1` with `LivingState=0` (forced flag, Dead character). ARM F reached `gate=1` with
`LivingState=1` — set legitimately by the game. **Motion was never observed from THAT state**,
because the client died first. So "the gate is insufficient" is measured *for the forced-flag,
Dead-character case*; whether the fully-legitimate state produces motion is **still open**.

---

## 3. ⚠ WHAT IS NOT ESTABLISHED, AND ONE INSTRUMENT CAVEAT

⚠⚠ **`[BS] done` IS ABSENT from the ARM F marker.** The client died during the post-call `A2`
census. This project's own rule is *"wait for `[BS] done` before reading the marker"*, so I have to
be exact about what that does and does not touch:
- **Unaffected:** ARM F's own lines are sequential, self-contained direct reads printed as they
  happened — BEFORE, the poke readback, the signature match, the call, and the AFTER pair. The
  AFTER line carries `faulted=0` and both gate values.
- **Lost:** the A2 census and the final summary (`dCtl`/`dHero`/`called=`). Those are not ARM F's
  readout, and I make no claim from them.
⇒ **F1–F5 stand; nothing that depends on the summary is claimed.**

**Not shown:** that a bot with a legitimately-opened gate moves. That `IsStunned` — the gate's
second conjunct — is false (still never measured; no such property surfaced). That any of this makes
a functional bot: `ServerSetHeroClass` and `SetPlayerTeam` remain stripped folds.

⚠ **The external-write question from flight 6 is STILL unresolved and this sitting cannot settle
it** — it mixed an external WPM (6b) with two shim injections, and died on the 5th manual-map with
the FK-32 signature (no crashpad, no `Fatal`). Confounded, as before.

---

## 4. THE CHAIN AS IT NOW STANDS

    nothing writes LivingState=Alive        [M, offline: 2 native writers, both store 0]
      -> every character reads Dead          [M, live, 6/6 + 30 CDOs]
      -> UpdateCharacterControllable, given Alive, SETS the gate     [M, ARM F, this flight]
      -> but a set gate alone does NOT drive motion                  [M, 6b, this flight]
      -> ??? further precondition: the blackboard bool at .data 0xA0348F0 / Blackboard +0x4B0

Every link is now measured except the last, which is named and unmeasured.

**Cheapest next flight, and it is one injection:** run `driverecompute` and then **immediately read
the motion chain externally** (`+0x658`, `pawn+0x418`, location) from the legitimately-opened state,
before the client dies. That is the observation flight 7 missed by seconds. If it is still inert,
read the Blackboard bool at `controller+0x4B0` and settle the last link.

---

## 5. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-f7-PREREGISTERED.txt` | 6b's Q1–Q5 and ARM F's F1–F5, with the honest alternatives, written before the flight |
| **`docs/s138-f7-marker-armf.txt`** | **ARM F: the signature match, the call, and the gate 0 → 1** |
| `docs/s138-f7-marker-ctrl.txt` | the control arm — `ARM F SKIPPED`, gate stays 0 |
| `docs/s138-f7-6b-gatepoke.txt` | 6b: gate forced to 1 for 12 s, no motion |
| `docs/s138-f7-6b-DRYRUN.txt` | the control-arm baseline (`GATE=0 force=0`) |
| `docs/s138-Loki-flight7.log` | client log |
| `dumps/s138-arms-armf/` | the three arms, archived |

**Arms** (RAW): `driverecompute` **`a2a952babfed256b`** · `driverecompute-ctrl`
**`2a91f0aa7f3d521b`** · regression gate `botai` **`5e47c13cf7f0a158` UNCHANGED**.
`verify_dll` PASS on both; `WriteProcessMemory`/`FlushInstructionCache`/`VirtualAlloc` absent.

⛔ ARM F writes `+0x6A0` and touches the Blackboard — **not call-only**, a DIAGNOSIS, and it must
never enter the default shim set.
