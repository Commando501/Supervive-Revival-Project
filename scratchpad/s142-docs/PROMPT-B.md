# LANE B — BRING `docs/ignorance-map-s101.md` BACK INTO LOCKSTEP

`CLAUDE.md` describes this file as **"the living index: the FALSE_KNOWN register, the walls register,
instrument blindness, and the ranked focus plan. Kept in lockstep with this file."**

**It is not in lockstep.** [M] it was last touched at commit `7f7f3e2` (S138) and contains **ZERO**
mentions of S139, S140 or S141. It has therefore missed the entire movement arc — three walls
falling, one instrument being invalidated, and a large set of beliefs being retracted.

## FILE YOU OWN

`docs/ignorance-map-s101.md` — and ONLY this file.

## WHAT TO DO

1. **Read the file first** and understand its existing structure and conventions — the FALSE_KNOWN
   register format, the walls register, how rows are graded and dated. **Match them exactly.** Do not
   invent a new format and do not restructure the document.
2. **Audit it against the arc.** For every existing row that the S139–S141 work has settled, refuted,
   or moved: update it in place, in the file's own idiom, with the session number and a pointer to
   the settling doc. Preserve the original claim text where the file's convention is to preserve it
   (this repo's value is its retraction history).
3. **Add the new entries the arc created.** At minimum — and check each against the sources rather
   than taking my word:
   - **FALSE_KNOWN:** `CMC+0x16C8` was believed to be a sticky "ever reached" latch. It is not; it
     reads 0 in every world. Everything inferred from it is UNGRADED, not negative.
   - **FALSE_KNOWN:** "the player does not fall" — that was **ours**, `sp`'s LIFT-TO-SEE step setting
     `GravityScale = 0`.
   - **FALSE_KNOWN:** "`Velocity == 0` stops the mover" — DEAD.
   - **WALL FELL:** the engine mover chain runs; the bot walks 13,196 uu at 500 uu/s, reproduced.
   - **WALL MOVED:** the one pawn that does not move is the one with input; the discriminator is the
     kick AXIS.
   - **INSTRUMENT BLINDNESS:** capstone 5.0.7 reports `movups` stores as reads via `regs_access`;
     `pdata_union.csv` has no row for `0x055C2430`; a rip-relative `lea` scan cannot see UE log
     strings (they are reached through a record struct).
4. **Re-rank the focus plan** if the file has one, so it reflects that the movement wall has largely
   fallen and what the live question now is.
5. ⚠ If any existing row is now simply WRONG rather than superseded, say so explicitly with the
   session that killed it. If a row is unaffected, **leave it completely alone.**

## RULES

- Do NOT rewrite the document's history. Annotate and add; preserve original claim text per the
  file's own convention.
- Grade everything `[M]` / `[I]` / `[S]`.
- **Rule 9:** grep the file for every instance of a belief before correcting one.
- Cite the settling doc for every change.
- Minimal diffs. No reflowing, no restructuring, no typo fixes.

## OUTPUT

Apply the edits. Then write `scratchpad/s142-docs/B-report.md`: what you changed and why, what you
deliberately left alone, and anything you could not resolve from the sources.
