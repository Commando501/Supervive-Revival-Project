# S142 — AUDIT S140 TIER 1–3, THEN MAKE THE DOCUMENTATION TRUE

**Paste this whole file as the opening prompt of a fresh session.**

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` first (auto-loaded), then `docs/s141-tier3-settled.md`.

**This session is an AUDIT and a DOCUMENTATION PASS. It is OFFLINE. Do not launch the game, do not
inject, do not stage a world.** Everything here is re-derivable from the dumped image, the committed
evidence files, and the repo's own history.

**Use the Workflow tool with adversarial verification.** The right shape here is *lanes that try to
BREAK our own conclusions*, not lanes that summarise them. Budget ~10–14 agents. A lane that reports
"all confirmed" without having independently re-derived anything has done nothing.

⚠⚠ **THE STANDING BIAS TO FIGHT:** three consecutive sessions produced headline results
(S140 T1 "the contradiction dissolves", T2 "the bot walks", T3 "the mover runs"). **A run of wins is
exactly when a false one slips through.** Your job is to find the false one if it exists, and to say
so plainly if it does not.

---

## 0. WHAT IS BEING AUDITED

Three tiers, all completed, each of which **overturned the previous one's framing**:

| tier | headline | the claim that must survive audit |
|---|---|---|
| **T1** | the physics-step contradiction dissolves | `CMC+0x16C8` is a within-call `TOptional` flag cleared by vtable disp `0xA50` (`0x0530ABF0`) at `0x035EB569`, **not** a sticky latch ⇒ "StartNewPhysics never ran" was uninterpretable. Plus: **exactly six** exits from engine `PerformMovement` to `0x035EB13A`, CFG-exact. |
| **T2** | the bot falls, lands and walks | one `Velocity = (600,0,0)` write ⇒ terminal-velocity fall, land at `Z = 90.150`, walk capped at exactly `500.0` uu/s. Mechanism: engine `PhysFalling` zeroes `Velocity` below a `SizeSq2D` gate of `(double)(float)1e-3` at `0x035ED98E`; retrodicts 4/4 in both directions. |
| **T3** | the mover RUNS; the fixed point is 2-D | one `GravityScale = 1.0f` write and the PLAYER fell 23,189 uu **from `Velocity.Z` exactly zero** ⇒ gravity integrates from `Vz == 0`. The player's non-fall was **our own `sp` LIFT step zeroing `CMC+0x1A0`**. `Velocity.Z` is **not** zeroed by the gate. ARM L: the bot walked 13,195 uu on a horizontal kick, `AnalogInputModifier = 1`. |

---

## 1. ★ SEED — a real defect is already found. Start by confirming it, then look for its siblings.

`CLAUDE.md` **contradicts itself about `driverecompute`'s digest**:

- `:1579` and `:1779` cite **`driverecompute a2a952babfed256b`** as a regression gate.
- `:2001` says **`driverecompute a2a952babfed256b` IS NOT A VALID GATE** — and
  `docs/s140-tier2-sentinel.md` §6.5 established why.
- **Measured today:** `build/tutorial_launch_driverecompute.dll` RAW = **`4465ebc4d7168c03`**, which
  is **`gasattr-ctrl`'s** digest. `build.ps1` gives `driverecompute` `-DKBSPSARMS=0xA0` and
  `gasattr-ctrl` `-DKBSPSARMS=0x0A0` — **the same value**, so the two variants are byte-identical by
  construction. That is this repo's own documented "A/B against a copy of itself" hazard, and it now
  exists between two *named* arms.

**This is the shape you are hunting**: a correction that was *found and written down* but *not
propagated*, leaving the digest self-contradictory. **Find every other instance.**

⇒ Also decide and record: should `gasattr-ctrl` be **deleted** as a redundant duplicate of
`driverecompute`, or should one of them be given different bits? Leaving two names for one build is
how a future session flies a control that measures nothing.

---

## 2. THE AUDIT LANES

### L-A — Re-derive T1's load-bearing claims, adversarially
- Rebuild the CFG of engine `PerformMovement 0x035E9EC0` **with your own code**. Confirm or refute:
  1461 instructions, 0 indirect jumps, 0 decode failures, 6538/6538 bytes covered,
  `|reach_backward(0x035EB13A)| = 1075`, exactly **2** backward edges with neither in `R`, exactly
  **6** exit edges, and that **five of six dominate** the call.
- Re-derive the `+0x16C8` clear: is disp `0xA50` really `0x0530ABF0`, is it really called at
  `0x035EB569`, and does the `StartNewPhysics` call site really dominate that call? **If the
  dominance claim fails, T1's headline fails with it.**

### L-B — Re-derive T2's mechanism, and attack the retrodiction
- Confirm `0x035ED98E comisd` against `.rdata 0x077F5180`, and that the constant is
  `0.0009999999747378752`. Confirm `rsi = &Velocity` by dominance from `0x035EC9AC`.
- ⚠ **The retrodiction table is the strongest evidence in the whole programme *and* the easiest to
  fool yourself with.** Four rows, all consistent — but two of them (`0` and `2^-10`) are the same
  physical situation, and two (`600` and `250000`) are the same. **Is it really 4 independent
  points, or 2?** Say so honestly; the conclusion may survive at a lower strength.
- ⚠ **Reconcile T2 and T3, which SOUND contradictory:** T2 says `Velocity == 0` is a fixed point
  that "can never leave zero on its own"; T3 says gravity integrates from `Vz == 0` and *"`Velocity
  == 0` stops the mover" is dead*. **Are these compatible** (a 2-D gate on XY, with Z free), or does
  one of them need correcting? **`CLAUDE.md` still contains 3 "fixed point" phrasings — check each
  is qualified to the 2-D reading.**

### L-C — Re-derive T3's claims
- The `sp` LIFT step zeroing `GravityScale (CMC+0x1A0)`: find it in
  `tools/sigbypass-mod/tutorial_launch.cpp` and confirm the player's non-fall was self-inflicted.
  **This is a self-blame claim, which is the kind most likely to be accepted without checking.**
- `DoJump` at CMC vtable disp `0x730`, and the "whole kick chain is [M], zero folds" claim — regrade
  every callee three-state (**FOLD / REAL / DARK**), remembering the **sixth stub shape**
  (`sub rsp,0x28; call GetWorld; xor eax,eax; ret`) which grades REAL under a two-state test.
- Does S132's dismount observation still reconcile? T3 claims it does.

### L-D — Evidence-file integrity
For every load-bearing number in the T1/T2/T3 write-ups, **open the evidence file it cites and check
the number is there.** Specifically: `docs/s140-t2-f3-AFTER.txt`, `docs/s140-t2-marker-armj.txt`,
`docs/s141-t3-marker-arml.txt`, `docs/s140-t2-BASELINE.txt`, and the pre-registration files.
- Confirm each pre-registration was committed **before** its flight (check `git log` order against
  the flight's evidence timestamps) and is **unedited since**.
- ⚠ Flag any claim whose cited evidence file does not contain it. That is the failure mode that
  produced `docs/s137-external-AFTER-flight3.txt` (an evidence file destroyed by `tee`).

### L-E — Corrections: APPLIED, not just listed
T1 wrote ~20 corrections; T2 and T3 wrote more. **For each, check the target file actually changed.**
Produce a table: correction → target → applied? → if not, apply it.
⚠ This is the project's single most recurrent failure ("a digest is an instrument", S115-d).

### L-F — Stale-claim sweep
- Run `python scratchpad/s133/tools/regrade_blocked.py` (or re-derive it) against the **current**
  merged image and report every "this page is dark / coverage-blocked" claim that is now LIT.
  The recorded history is 43 stale claim-instances at S137; find today's number.
- Re-verify the coverage negative control: `ULokiRespawnComponent::Respawn 0x5A6AC40` must still be
  0/4096. **If it is lit, every "dark" grade in the last three sessions needs re-checking.**
- Confirm which merged image is current and whether `tools/strxref/strxref.py`'s default points at
  it. That default has been one generation stale twice before.

### L-G — Arms, digests and the duplicate hazard
- Digest **every** `tutorial_launch_*.dll` in `build/` with
  `python tools/sigbypass-mod/text_digest.py --dupes tools/sigbypass-mod/build`.
- Report every group of differently-named variants that share a digest, and for each say whether it
  is **explained** (identical knob values) or a **hazard** (a "control" that is a copy of its
  treatment).
- Check every digest cited in `CLAUDE.md` and `docs/s14*.md` against what the file actually is
  today. Mark any that no longer reproduce as **stale — re-record or delete**.
- ⚠ `gasattr-sentinel ce56fd715de835a1` was **overwritten in `build/` before being archived** (T2
  defect S140T2-j). Confirm whether it is recoverable from commit `3176139`, and archive it.

### L-H — What is still NOT true
Compile the honest negative list, and check nothing in the docs overstates it:
- `ServerSetHeroClass` / `SetPlayerTeam` are stripped folds; nothing has gone through `SpawnBot`.
- `LivingState` has no native writer that sets Alive.
- `ALokiBotController::Tick`'s only motion driver is a **random wander** — no targeting, no
  abilities, no combat.
- ARM G is a **process-wide CDO poke**; ARM H/J/L write live component state. **None is a shipping
  fix and none belongs in the default shim set.**
- ⚠ **ARM L's own A/B did not test what it was built for** (kick B landed on an already-walking bot,
  so it compared "vertical added to motion" not "vertical from rest"). Confirm this is recorded
  wherever the axis question is discussed, and that no doc claims the axis comparison happened.

---

## 3. DELIVERABLES

1. **`docs/s142-audit.md`** — per lane: what was re-derived, by what independent route, and the
   verdict **CONFIRMED / DOWNGRADED / REFUTED**. A confirmation you did not independently reproduce
   does not count and must not be listed.
2. **A defect table** — every contradiction, stale digest, unapplied correction and unsupported
   claim, with its fix.
3. **APPLY the fixes.** Edit `CLAUDE.md` and the `docs/` files. Do not merely list them — that is the
   failure this audit exists to catch.
4. **Reconcile the T2 "fixed point" and T3 "the mover runs" framings** into one statement that is
   true, and propagate it everywhere both appear.
5. **A one-paragraph honest status** at the top of `docs/s142-audit.md`: what this project can
   actually do today, in plain language, with no starred superlatives. If the answer is "an
   AI-controlled hero pawn walks after three artificial pokes, and it is not a bot", write that.

---

## 4. ⚠ TRAPS FOR AN AUDIT SPECIFICALLY

1. **Confirmation is not free.** Re-deriving by the *same* route the original used proves nothing.
   Use a different instrument or say you did not verify it.
2. **A census returning all-negative is more likely a broken instrument than a discovery** — a
   S140-T2 script unpacked the PE section header field order backwards and graded *everything* dark,
   including seven functions measured LIT an hour earlier. Always run a passing negative control
   beside the positives.
3. **`CMC+0x16C8` is NOT a latch.** Any doc or tool still drawing a verdict from it is a defect.
4. **`MOVE_Custom == 7` on this build** (`MOVE_Dashing` inserted at 6). Stock tables mis-decode.
5. **A `set()` collapses `-0.0` and `0.0`** — it hid an entire S139 finding.
6. **Do not cross a function boundary with an inference** — S139 read a Loki-wrapper fact as an
   engine-callee fact and had to retract.
7. **Timestamps: `Copy-Item` preserves the SOURCE mtime**, so marker-file mtimes are not a reliable
   ordering. Use `git log` for pre-registration ordering.
8. **`LogCharacterMovement` is pinned but has NO positive control on this route.** Its zero is
   evidence about nothing. Any doc citing that zero is a defect.

---

## 5. SCOPE

This session changes no game behaviour and produces no new capability. Its output is **a repo whose
documentation is true**, plus a list of what is genuinely established and what is not. If the audit
finds nothing wrong, say so — but only after having genuinely tried to break each claim, and list
what you attacked and how.
