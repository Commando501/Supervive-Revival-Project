# S138 flight 6 — the byte pokes cleanly; the gate does not move, exactly as pre-registered

Written 2026-08-23. Pre-registrations: `docs/s138-f6-PREREGISTERED.txt` and
`docs/s138-f6b-PREREGISTERED.txt` (both UNEDITED). Predecessor:
`docs/s138-livingstate-writers-settled.md`.

---

## 0. HEADLINE

**P1 and P2 HOLD. P3 FAILED — and P3 failing is the outcome the pre-registration named in advance,
with its mechanism.**

    A  BASELINE        botLivingState=0  GATE+0x6A0=0  RandDir=(0,0,0)  CIV=(0,0,0)  loc=(600.0,0.0,13240.0)
    B  POKE  pawn+0x1090 = 1     WriteProcessMemory ok=True   READBACK=1
       B+2s  … B+10s   botLivingState=1  GATE+0x6A0=0  RandDir=(0,0,0)  CIV=(0,0,0)  loc UNCHANGED
       CONTROLS (3 unpoked hero pawns)  LivingState = 0, 0, 0  at every timepoint
    C  RESTORE pawn+0x1090 = 0   READBACK=0

| # | prediction | result |
|---|---|---|
| **P1** | the poke lands; readback == 1 | **HOLDS** — and held across all 5 samples over 10 s |
| **P2** | the 3 unpoked hero pawns stay 0 (specificity) | **HOLDS** — 0,0,0 at every timepoint |
| **P3** | `bCharacterControllable (+0x6A0)` flips 0 → 1 | **FAILED** — 0 at every timepoint |
| P4/P5 | wander direction / motor / motion | not reached (gate never opened) |
| P6 | restore returns the byte to 0 | **HOLDS** — readback 0 |

⇒ ★★ **`LivingState` is writable, the write is specific, and it is NOT sufficient.** The gate is not
recomputed from the byte.

---

## 1. WHY THIS IS A RESULT AND NOT A DISAPPOINTMENT

`docs/s138-f6-PREREGISTERED.txt` §2, written before the flight:

> **★★ P3 IS THE ONE I EXPECT TO FAIL, AND SAYING SO NOW IS THE POINT OF THIS FILE.**
> `UpdateCharacterControllable` (impl `0x5570B80`) is a REAL reflected FUNCTION, and
> `HandleLivingStateChanged` (`0x5560910`) is a REAL function whose body is `jmp 0x5570B80` — i.e.
> a DELEGATE HANDLER that calls it. That is the shape of a value **COMPUTED ON A STATE-CHANGE EVENT
> AND CACHED** at `+0x6A0`, not one recomputed every Tick. […] Poking the byte SILENTLY, without
> firing that delegate, plausibly changes nothing at `+0x6A0`.

**That is exactly what happened.** The prediction was specific, mechanistic, made in advance, and
confirmed. `+0x6A0` is a cached flag; `LivingState` is its *input*, not its *value*.

⇒ **The next lever is named and unchanged from the pre-registration (P3-ALT):** drive the recompute —
call `ALokiBotController::UpdateCharacterControllable` (impl `0x5570B80`, thunk `0x52EEDB0`) on the
live controller via the S55 direct-thunk primitive, or fire the `OnLivingStateChanged` delegate at
`hero+0xC38` that S137 measured `OnPossess` binding `HandleLivingStateChanged` onto.
**Deliberately NOT attempted in this flight**, so that the null is attributable to the missing
recompute rather than confounded with a second change.

---

## 2. ⚠⚠ MY OWN TOOL PRINTED A FALSE "YES", AND I ALMOST REPORTED IT

The verdict line read **`P3 gate +0x6A0 flipped 0 -> 1 : YES`** — while its own samples, printed
six lines above, showed `GATE+0x6A0=0` at every single timepoint.

The predicate was:

    "YES" if (a[1] == 0 and any(True for _ in [1]) and c is not None) else "see samples above"

`any(True for _ in [1])` is **always** true and `c is not None` is **always** true, so it collapsed
to `a[1] == 0` — *the baseline gate was 0* — which is the **precondition of the entire experiment**.
It therefore printed YES unconditionally, on every possible run.

★ **This is a degenerate always-true guard: the same shape as S136's constant-folded dispatch guard,
relocated from an arm into a verdict line.** It is also the third time in this session that a
self-written instrument produced a false positive (the auto-stage driver's 12 s race, the
duplicate-candidate double count, and now this).
★ **What caught it was reading the SAMPLES rather than the verdict** — precisely the rule this
project records as *"the call returned ok is never a success criterion; only the verb's own output
counts."* Had I quoted the verdict line, I would have reported the headline backwards.
**Fixed**: the verdict is now computed from the observed B-phase gate values and prints them
inline, so the number and the claim cannot diverge.

---

## 3. ⚠ THE EXTERNAL-WRITE QUESTION, FLAGGED PER PRE-REGISTRATION AND NOT RESOLVED

This was the **first time this project has written to the game from an external process** (every
prior poke came from an injected shim). The pre-registration flagged the risk in advance:

> ⚠ HONEST NOVELTY: […] "external WPM is not detected" is UNTESTED. If the client dies within
> seconds of the poke with no crashpad artifact, that is a candidate cause and must be recorded as
> such rather than filed as ordinary FK-32.

**The client died ~44 s after the poke sequence finished, with the byte already restored to 0, with
no crashpad handoff and no `Fatal`** — i.e. the FK-32 signature.

**I am recording this as UNRESOLVED, and it is confounded two ways:**
- **Base rate.** *Every* S137/S138 sitting has ended in FK-32, including many with no external write
  at all. This one died on the 4th manual-map, squarely in the recorded 4–7 range.
- **n = 1**, and the death followed the restore rather than the write.

**What would settle it:** run a matched sitting that stages and reads but performs **no write**, and
compare time-to-death. Until then, "external WPM is safe" and "external WPM killed it" are both
unsupported. ⚠ Do not quietly assume the former just because the poke worked.

★ What IS established about the mechanism: `OpenProcess(PROCESS_ALL_ACCESS)` succeeded,
`WriteProcessMemory` returned success, and the readback confirmed the byte — twice, in both
directions. **The write path itself works.**

---

## 4. FLIGHT 6b — NOT OBTAINED (not a null)

With the client apparently alive, I pre-registered a second probe (`docs/s138-f6b-PREREGISTERED.txt`)
to poke **the gate byte itself** (`controller+0x6A0 = 1`) and test the downstream half directly —
does `Tick`'s wander driver run when the flag is set, and does the pawn move?

The client died between the liveness check and the run. The probe **correctly refused**
(`OpenProcess FAILED -- RUN IS VOID`) rather than printing an artifact.

⚠ **6b is NOT OBTAINED. It is not a null and must not be cited as one.** Its pre-registration stands
unmodified and it is the cheapest next experiment — it needs a staged client with a
`LokiBotController` and about 20 seconds.
★ Its pre-registration already names the honest alternative: S137 recorded that the wander driver
gates on a **blackboard bool key** (`.data 0xA0348F0`) *in addition to* this byte, so a null there
would locate that, not refute anything.

---

## 5. WHAT IS AND IS NOT SHOWN

**Shown [M]:** `LivingState` at `hero+0x1090` is writable by a single aligned byte; the write is
specific (3 unpoked controls unmoved); it persists (10 s, 5 samples); it is reversible; and it does
**not** by itself open `bCharacterControllable`.

**Not shown, and not claimed:** that an Alive character behaves alive. That the wander driver would
run if the gate were open (that is 6b). `IsStunned` — the gate's second conjunct — remains
**unmeasured**. And `ServerSetHeroClass` / `SetPlayerTeam` are stripped folds regardless.

⛔ This is a DIAGNOSIS, not a shipping fix. It mutates live object state and must never enter the
default shim set.

---

## 6. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-f6-PREREGISTERED.txt` | P1–P6 **and P3-ALT**, written before the flight |
| `docs/s138-f6b-PREREGISTERED.txt` | the gate-poke probe, pre-registered but NOT OBTAINED |
| `docs/s138-f6-poke-DRYRUN.txt` | dry run — target + 3 controls identified, nothing written |
| **`docs/s138-f6-poke-RESULT.txt`** | **the A-B-A run** (⚠ its final verdict line is the false YES; the samples are correct) |
| `docs/s138-f6-marker-premade.txt` | ARM D's `LokiBotController` on this client |
| `docs/s138-Loki-flight6.log` | client log |
| `tools/re/livingstate_poke.py` | the arm; verdict predicate now fixed and the defect documented in-file |

★ Incidental: v3's `G3/G4 GameState candidates: 1` reproduced a **third** time.
