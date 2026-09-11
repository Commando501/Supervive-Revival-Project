# DOC-REPAIR BRIEF — read first. OFFLINE. No launches, no injection, no live process.

Task: the S139 → S140 → S141 movement arc landed, but **some documentation did not keep up.**
You are repairing docs, not doing new RE. Do not re-derive the RE; cite it.

## CURRENT TRUTH (as of 2026-08-24, HEAD = 9c604c4). Do not contradict this.

**THE ENGINE MOVER CHAIN RUNS ON THIS CLIENT. The movement wall largely FELL.**

- **[M] THE BOT WALKS.** From one `Velocity = (600,0,0)` kick at rest it fell at terminal velocity,
  landed, and walked at **exactly 500.0 uu/s** for **13,196 uu**, steered by its own AI.
  **Reproduced in a second sitting** (S140 T2 flight 3, then S141 ARM L).
- **[M] `TickComponent → ControlledCharacterMove → PerformMovement → StartNewPhysics → PhysFalling`
  all execute.** One 4-byte `GravityScale = 1.0f` write made the PLAYER hero fall **23,189 uu** in
  10 s from `Velocity.Z == 0` ⇒ gravity integrates.
- ⛔ **"`Velocity == 0` stops the mover" is DEAD. Do not re-open it.**
- **[M] THE PLAYER'S NON-FALL WAS OURS** — `sp`'s LIFT-TO-SEE step
  (`tutorial_launch.cpp:12877-12890`) sets `GravityScale = 0`, and `CMC+0x1A0` **is** `GravityScale`
  (engine `GetGravityZ 0x035E3680 mulss xmm0,[rbx+0x1a0]`, three agreeing instruments).
- **[M] THE FIXED-POINT GATE IS 2-D.** Engine `PhysFalling`'s `SizeSq2D` gate zeroes only the
  gravity-space horizontal components (the store at `0x035ED9AC` is `movups` — 16 bytes over a
  24-byte `FVector` of doubles). Gravity is integrated BEFORE that clamp on every iteration, so the
  clamp can never suppress a fall.
- **[M] `CMC+0x3D0` is `AnalogInputModifier`**, and on a walking bot it reads **1**, so engine
  `CalcVelocity`'s `< 1e-4` ZeroVector clamp at `0x035D6511-0x035D652F` **cannot fire**.
  `MinAnalogWalkSpeed @CMC+0x290` = 0 on both pawns.
- **[M] S132's dismount was a `GravityScale` RESTORE**, not a velocity write — which is why that
  hero fell with X and Y frozen.

### THE ONE REMAINING WALL — state it precisely, do not overstate the win

**The BOT is the only thing that does not move, and it is the pawn that HAS INPUT.** Same world,
same frame, same pass, both `MOVE_Falling`, both `GravityScale 1.0`, both `GravityDirection
(0,0,-1)`, both ARM-G-treated, identity controls passing:

| | Acceleration | Velocity written | Velocity read | moved |
|---|---|---|---|---|
| **BOT** | \|50000\|, rotating (AI wander) | `(0,0,-600)` | **`(0,0,0)` at +250 ms and every sample to +10 s** | **0.000 uu ×5** |
| **PLAYER** | (0,0,0) | `(0,600,0)` | `(0, 18.99, -4000)` → … | **23,189 uu** |

**The discriminator found at S141 is the KICK AXIS**: a *horizontal* kick works (bot walks); a
*Z-only* kick reads back `(0,0,0)`. **[M] the bot's zero is not self-inflicted** — ARM H2 (the
re-write burst) was OFF, the only two `Velocity` writes are marker lines 218/219 before the armed
dump, and the restore is line 344, after all five samples.

## THE S140 TIER 1 RESULT THAT INVALIDATED AN INSTRUMENT (this is what most stale docs got wrong)

**[M] `CMC+0x16C8` IS NOT A STICKY LATCH. `latch == 0` IS UNINTERPRETABLE — it reads 0 in every
world.** `ULokiCMC` vtable disp `0xA50` = **`0x0530ABF0`**
(`80b9c816000000 / 7407 / c681c816000000 / e98bbb2cfe`) **clears** the byte, and engine
`PerformMovement` calls that slot at **`0x035EB569 ff90500a0000 call [rax+0xa50]`** with
`rcx = rbx = this` — later in the same call, on a path the `StartNewPhysics` call site **dominates**.
Derived independently three times in one session and re-verified by an adjudicator.

**The field is NAMED from its own consumer:** `.data 0x09BC9AD0 = {"GetRecentVelocity",
thunk 0x0530C7E0, impl 0x0530AC10}`, whose body is
`cmp byte [rcx+0x16c8],0 / mov eax,0x16b0 / mov r8d,0xe8 / cmove eax,r8d` ⇒ a per-frame
`TOptional<FVector>` validity flag over the Velocity snapshot at `+0x16B0`.

Also from S140 Tier 1:
- **[M] THE SIX EXITS OF ENGINE `PerformMovement` ARE COMPLETE AND EXACT** — four independently
  written CFGs: 1461 instructions, 148 calls, 0 indirect jumps, 0 decode failures, 0 coverage gaps
  (6538/6538 bytes), `|R| = 1075`, exactly 2 backward edges and **neither in `R`**. No seventh path,
  no backward bail. Five of the six DOMINATE the call; `0x035EA25D` is a redundant second
  `HasValidData`.
- **[M] `ULokiCMC::PerformMovement` reaches its Super UNCONDITIONALLY** (142/322 reach `0x055B85C1`,
  zero edges leave the set). The two branches S139 flagged as "next to read live" both target
  `0x055B85B4`, **13 bytes BEFORE** the Super call — they skip a LOOP, not the Super.
- **[M] exactly ONE gate** stands between the `Acceleration` write and `PerformMovement`:
  `0x035DCDA1 jne`, testing `CharacterOwner->Role(+0x160) == 3`, measured 3 on the provably same
  object. ⚠ The `Acceleration` store at `0x035DCD6B` is **upstream** of that gate, so the
  signed-zero proof alone does not establish `PerformMovement` was called.
- **[M] no free log receipt exists on this path** — the only three `LogCharacterMovement` sites are
  the `IsSimulatingPhysics` abort (fires only when the gate FAILS; it passes), an
  unsupported-movement-mode Warning (mode 3 is in range) and a root-motion-only Log. ★ But the
  category object is at **`.data 0x9F85E68`**, so one read-only RPM byte gives the positive control
  the category always lacked.

## SOURCE DOCS (cite, do not re-derive)

`docs/s140-tier1-cfg.md` (844 lines; §4 and §5 govern) · `docs/s140-tier2-sentinel.md` ·
`docs/s140-t2-armj-THE-BOT-WALKS.md` · `docs/s141-tier3-settled.md` (§4 and §6 govern) ·
`docs/s141-t3-arml-result.md` (§2 governs) · `docs/next-session-prompt-s142.md` (current handoff) ·
`CLAUDE.md` (already updated — its S140/S141 blocks are current; use it as the reference wording).

## RULES

- **Grade every claim** `[M]` / `[I]` / `[S]`. Never launder an `[I]` into an `[M]`.
- **Rule 9 — grep for the claim before correcting one instance of it.** A correction that fixes one
  line and leaves four is worse than none, because the four now look verified.
- ⚠⚠ **DO NOT REWRITE HISTORY.** This repo deliberately preserves dated records:
  *"Historical handoffs ... are dated archives and were deliberately NOT rewritten — editing them
  would falsify the record of what a past session was actually told."*
  ⇒ For a **handoff** (`next-session-prompt-*.md`): add a **banner at the top only**. Do not edit
  its body.
  ⇒ For a **settled/evidence doc**: add a banner at the top **and** annotate the specific false
  lines in place (that is what `docs/fk7-crash-settled.md` does). **Keep the original text visible**
  — quote it, mark it retracted, give the replacement. Never delete it.
- Distinguish **what was measured** from **what was inferred from it**. In almost every stale line
  here the *measurement* is fine (`+0x16C8` really did read 0) and only the **inference** is dead.
  Say exactly that; do not tell a future reader the measurement was wrong.
- Be surgical. Do not reflow paragraphs, do not restructure documents, do not fix typos. Minimal
  diffs, so `git diff` shows only substantive changes.
