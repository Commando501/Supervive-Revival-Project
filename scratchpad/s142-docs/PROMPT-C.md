# LANE C — REPO-WIDE SWEEP FOR SURVIVING STALE CLAIMS. **REPORT ONLY, EDIT NOTHING.**

Lanes A and B are repairing specific files. Your job is to find what **neither** of them covers,
across the whole repo, and to report it so the session lead can act. **You must not edit any file.**

`docs/method-rules.md` records this lesson from the arc (entry `S140T2-g`):

> ⇒ **when a claim is retracted, grep the TOOLS, not just the docs.** A retraction that does not reach
> the instrument that produced the claim has not landed.

Take that literally and apply it at repo scale.

## SWEEP FOR

1. **The invalid latch.** Any file — `.md`, `.txt`, `.py`, `.cpp`, `.ps1`, `.go` — that reads a
   verdict out of `CMC+0x16C8`, or calls it a latch / sticky / "ever reached", or infers
   "StartNewPhysics never ran" from it. **Especially TOOLS**: `tools/re/*.py`,
   `tools/sigbypass-mod/*.cpp`, `configs/*.ps1`, `scratchpad/**`. Report the file, line, exact text
   and whether it would produce a wrong answer if run today.
   ⚠ `tools/re/cmc_earlyout_readout.py` was already fixed once (per `method-rules.md:227`) —
   **verify that fix actually landed and is complete** rather than assuming it.
2. **"Velocity == 0 stops the mover"** and its relatives, anywhere.
3. **"the player does not fall" / "no character in this world moves" / "there is no moving character
   to diff against"** — all now explained (our own `GravityScale = 0`) or refuted.
4. **The S139 "next step" that was refuted**: anything still telling a reader to go read
   `[CharacterOwner+0x580] & 8`, or claiming `UpdatedComponent->IsSimulatingPhysics()` has never been
   read, or saying engine `PerformMovement` has "three gates".
5. **The dead log recommendation**: anything claiming that pinning `LogCharacterMovement` yields a
   per-frame "the physics step ran" line.
6. **Any doc that presents the movement wall as OPEN in a way the arc has closed** — but be careful:
   the wall genuinely MOVED rather than fully closing, so a doc describing the *remaining* wall (the
   bot with input not moving on a Z-only kick) is CORRECT, not stale. Do not flag those.

## METHOD

- Use `grep -rn` with **scoped paths** and check exit codes. ⚠ `CLAUDE.md` records that an unscoped
  `grep -rl` over `docs/` **TIMED OUT at 2 minutes** and its partial output was read as a negative.
  Scope your greps, and state that your sweep is a **FLOOR**.
- For every hit, decide and state: **STALE** (would mislead), **HISTORICAL-OK** (a dated record the
  repo deliberately preserves — handoffs, pre-registration files, flight logs whose banner already
  covers it), or **CORRECT** (describes the remaining wall accurately).
- Do not report a hit inside a retraction/banner block as stale — check the surrounding context.

## OUTPUT

Write `scratchpad/s142-docs/C-report.md`: a table of every hit with file:line, verbatim text,
classification, and — for STALE ones only — a concrete suggested replacement. Rank the STALE ones by
how much damage they would do to a successor. **Explicitly list which files lanes A and B are already
handling, so the lead does not double-edit.** Lane A owns `docs/s139-flight{1,2,3,4}*.md` and
`docs/s139-movement-ladder.md`; lane B owns `docs/ignorance-map-s101.md`.
