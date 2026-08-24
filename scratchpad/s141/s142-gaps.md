## 8a. ⚠ WHAT TIER 3 DID **NOT** CLOSE — audited against the brief's own task list

**T3-A: COMPLETE.** `[M]`, four independent derivations, plus a live pre-registered test.
**T3-D: COMPLETE** as specified (scoped, deliberately not built).

**T3-B: SUBSTANTIALLY complete, with a named residual.** Lane L3 — the engine kick surface — died to
an API error, and an audit showed that of the brief's explicit target list the surviving lanes had
**0 mentions** of `DoJump`, `CheckJumpInput`, `CanJump`, `AddForce`, `AddRadialImpulse` and root
motion. Nine of those were then graded by hand (§5.1 above): **zero folds, every impl REAL.**
**Still ungraded: `DoJump`, `CheckJumpInput`, `LaunchCharacter`, `HasAnimRootMotion`** — no whole
ASCII name string, so they need the vtable-neighbourhood route rather than the record table.

**T3-C: HALF complete, and the missing half is a design error rather than a null.** Q1 (does the
player fall) answered decisively YES. Q2 (does the GAS port let it *sustain* velocity) is **NOT
ESTABLISHED**: the player's `Acceleration` read `(0,0,0)` at every sample because it has no input
driver at all, so its 600 → 0 decay is correct physics and discriminates nothing. Fixing it means
giving the player acceleration first (`AddMovementInput`, or an AI controller), then re-reading.

**PROCESS: the adversarial-verification layer was lost entirely** — 7 of 12 agents in the main
workflow (every verifier plus the adjudicator) and then 0 of 4 in each of two focused retries, all
to API `529 Overloaded`. Partial recovery: the dead L1 verifier's own scripts were still on disk and
re-running them confirmed §1, §3 and §4.1's attribution from independently written code, and
produced the new gravity-before-clamp ordering fact. **Every claim in this document marked "pending
verification" has had exactly one derivation and should be read as `[I]`.**

⇒ **Carried into S142** (`docs/next-session-prompt-s142.md`): the axis A/B + the
`AnalogInputModifier` read (MOVE 1/1a), the `CalcVelocity` writer table (MOVE 2), T3-C's sustaining
half (MOVE 3), the four ungraded kick targets, and re-running the four verifiers if the API is
healthy.
