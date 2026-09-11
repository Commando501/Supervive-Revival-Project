# LANE A — BANNER AND ANNOTATE THE STALE S139 EVIDENCE DOCS

Four S139 docs still assert, as `[M]`, conclusions that S140 Tier 1 invalidated and that S140
Tier 2 / S141 Tier 3 have since overtaken. They have **no superseded banner**, so a successor
reading them cold is misled. Repair them.

## FILES YOU OWN (do not touch any other file)

1. `docs/s139-flight1-the-bot-is-not-special.md`
2. `docs/s139-flight2-gate-refuted.md`
3. `docs/s139-flight3-controlledcharactermove-runs.md`
4. `docs/s139-flight4-gas-port-works.md`
5. `docs/s139-movement-ladder.md` (already has SOME banner — check whether the specific stale lines
   are annotated; line ~170 reads "+0x16C8 is a STICKY latch, never cleared")

## KNOWN STALE LINES (a FLOOR, not a list — grep for more)

- `s139-flight2-gate-refuted.md:58` — "Every one reads +0x16C8 == 0. => ULokiCMC::StartNewPhysics has
  never run for any character in this world."
- `s139-flight2-gate-refuted.md:146` — grade-table row "ULokiCMC::StartNewPhysics has never run, for
  any of 37 components | [M] — the latch write at 0x055C2469 is on the unconditional fall-through"
- `s139-flight2-gate-refuted.md:156` — "six exits, all measured passing, and StartNewPhysics still
  never runs. One of the six readings must be measuring something other than what its branch tests."
- `s139-flight1-the-bot-is-not-special.md` around :128-:143 — a section asserting
  "(b) IS REFUTED AND THE LATCH IS A VALID INSTRUMENT". Refuting one alternative reading is NOT the
  same as validating the instrument; a THIRD reading (set AND cleared within the same call) was never
  enumerated, and it is the true one.
- `s139-flight3-controlledcharactermove-runs.md:112` — "StartNewPhysics still never runs
  (latch +0x16C8 == 0 ...)"
- `s139-flight4-gas-port-works.md:22` and `:73` — the P4 row and the "UNTOUCHED" row, both resting on
  the latch.

**Run your own grep across those five files** for: `16C8`, `never run`, `never entered`, `sticky`,
`StartNewPhysics`, `two problems`, `physics-step wall`. Report your grep output.

## WHAT TO WRITE

For each file: a banner at the very top, then in-place annotations.

The banner must say, compactly: what is superseded, by what, and where to read the current truth.
Point at `docs/s140-tier1-cfg.md` for the instrument retraction and
`docs/next-session-prompt-s142.md` + `docs/s141-tier3-settled.md` for the current state.

⚠ **The nuance that matters most, and you must get it right in every annotation:** the *measurement*
was correct — `+0x16C8` really did read 0 on all 37 components. What is dead is the *inference*
"therefore StartNewPhysics never ran". **Do not write anything that implies the probe misread the
byte.** Where a doc's own pre-registration flagged the reading as uninterpretable
(`s139-flight1` P2 does), **say that it was right and should have been left standing.**

⚠ Also flag, where relevant, that these docs' *other* results survive intact and must NOT be
discarded: flight 1's bot-vs-player structural identity, flight 3's signed-zero proof that
`ControlledCharacterMove` runs, flight 4's `Acceleration = input x 50000` with its within-run
specificity control. **A banner that reads as "this whole document is wrong" would destroy good
evidence.** Be explicit about what still stands.

## OUTPUT

Apply the edits. Then write a summary to `scratchpad/s142-docs/A-report.md` listing, per file: every
line you changed, the original text, the replacement, and your grep evidence that you found all
instances. Keep diffs minimal — no reflowing, no restructuring, no typo fixes.
