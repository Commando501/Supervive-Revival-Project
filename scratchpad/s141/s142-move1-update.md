## 1. ★ MOVE 1 — PARTLY ANSWERED BY ARM L. The clean test is ONE INJECTION, and the arm is BUILT.

**Read `docs/s141-t3-arml-result.md` first — its §2 governs.**

**[M] ARM L (2026-08-24) answered the read that ARM K missed:** `CMC+0x3D0` **is**
`AnalogInputModifier` (by-name resolve AGREES with the offset, both pawns, every sample), and on a
**walking** bot it reads **1** — so `MaxInputSpeed = GetMaxSpeed() × 1 = 500` and engine
`CalcVelocity`'s `< 1e-4` ZeroVector clamp at `0x035D6511-0x035D652F` **cannot fire.**
⇒ **§4.1 is REFUTED for a walking bot.** `MinAnalogWalkSpeed` (`+0x290`) = 0 on both, replicating
S140 T2 flight 3.

**[M] AND THE BOT WALKS, REPRODUCIBLY.** One `Velocity = (600,0,0)` from rest: fell at terminal
velocity, landed, walked at **exactly 500.0 uu/s** (three samples on the cap), 13,196 uu, steered
by its own AI. **A horizontal kick produced the fall with no Z kick at all** — the 2-D gate of §1
working in the affirmative direction. S140 T2 flight 3 is now **reproduced in a second sitting.**

⚠⚠ **BUT THE AXIS A/B STILL HAS NOT RUN, AND THE REASON IS MY ERROR.** ARM L's kick B landed on a
bot **already walking at 500 uu/s**, so it tested "vertical added to a moving body", not "vertical
from rest". The data reaches pre-registered outcome **P2**, whose written reading ("the axis is not
the variable") **does not follow**. Filed as **S141-l**. ⇒ **§4.1b is neither confirmed nor
refuted.**

### THE CLEAN TEST — do this first, it is one injection and the arm exists

**`armk_v2` RAW `988fd61853669d5c`**, archived at `dumps/s141-arms/tutorial_launch_armk_v2.dll`.
It is `armk` (vertical `(0,0,-600)` from rest) **rebuilt to include the `AnalogInputModifier` read.**

    stage -> inject armk_v2 -> read the samples
      Velocity zeroed AND AnalogInputModifier == 0  -> §4.1 CONFIRMED, and the axis matters because
                                                       a Z-only kick leaves AnalogInputModifier 0. [M]
      Velocity zeroed AND AnalogInputModifier == 1  -> §4.1 REFUTED outright; the zeroing is
                                                       something else entirely.                   [M]
      Velocity SUSTAINED (the bot walks)            -> ARM K's freeze does not reproduce; look for
                                                       what differed between SITTINGS, not kicks.  [M]

★ **And if you want the within-sitting A/B, restore the PRECONDITION**: zero `Velocity`, let it
settle for a sample, THEN apply kick B. ARM L re-latched the start *location* and not the *velocity
state*, which is the whole subject of the hypothesis.

⚠ **The cross-sitting comparison is all that currently bears on the axis**, and it is one
uncontrolled variable away from evidence:

| | ARM K | ARM L |
|---|---|---|
| kick, from rest | **vertical** | **horizontal** |
| `AnalogInputModifier` | **NOT READ** | **1** |
| result | `(0,0,0)`, moved **0.000 uu ×5** | fell, landed, walked **13,196 uu** |
