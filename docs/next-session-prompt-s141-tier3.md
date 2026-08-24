> ⚠⚠⚠ **SUPERSEDED BY S141 TIER 3 (2026-08-23/24). DO NOT WORK FROM THIS PLAN.**
> Read **`docs/s141-tier3-settled.md`** then **`docs/next-session-prompt-s142.md`**.
> What changed: **[M] the engine mover chain RUNS** — one 4-byte `GravityScale = 1.0f` write and the
> PLAYER hero fell **23,189 uu** at terminal velocity from `Velocity.Z` **exactly zero**, so gravity
> integrates from `Vz == 0` and *"`Velocity == 0` stops the mover"* is dead. **The player's non-fall
> was OUR OWN `sp` LIFT step zeroing `GravityScale` (`CMC+0x1A0`)**, which also resolves S132's
> dismount. **[M] the fixed-point gate is 2-D — `Velocity.Z` is NOT zeroed.** ⇒ the BOT is now the
> only thing that does not move, and it is the pawn **with input**. This file is kept as the dated
> record of what a past session was told; editing it would falsify that record.

# S141 / TIER 3 — the movement chain works. Make the kick NATIVE, and generalise it off the bot.

**Paste this whole file as the opening prompt of a fresh session.**

⚠⚠ **THIS SUPERSEDES `docs/next-session-prompt-s141.md`.** That file was written mid-Tier-2, before
flight 3. Its §1 is already self-marked superseded; its MOVE 1–3 are framed around questions flight 3
**answered** (the fixed point is named, the bot fell at terminal velocity, `MinAnalogWalkSpeed` was
read). Keep it as the dated record; **do not work from its plan.**

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` first (auto-loaded), then **`docs/s140-t2-armj-THE-BOT-WALKS.md` — especially §4b,
which names the mechanism** — then `docs/s140-tier1-cfg.md` §4 (why `+0x16C8` is not an instrument).

**Use the Workflow tool with adversarial verification** for the offline lanes; fly by hand.
Budget ~10–14 agents. This session is **mostly offline**, with **at most one** staged flight.

---

## 0. WHERE THIS STANDS — the wall fell, and it was one `comisd`

S140 Tier 2, flight 3: **one write of `Velocity = (600,0,0)` — once, never re-written — and the
AI-controlled hero FELL under gravity at terminal velocity (`Vz = -4000`), LANDED on the tutorial
floor at `Z = 90.150`, and WALKED with its speed capped at exactly `500.0 uu/s`** — the
`MoveSpeed`/`MaxMoveSpeed` ARM G wrote. It travelled **13,187 uu** and later walked off the island
edge under its own AI. `Z = 90.150` independently matches the ground-rest Z this repo recorded in
S132 for a dismounted hero.

**[M] THE MECHANISM, derived offline BLIND to the flights, retrodicting 4/4 in both directions:**

    engine PhysFalling zeroes Velocity below a gravity-space SizeSq2D threshold
      0x035ED98E  comisd xmm1, [rip -> .rdata 0x077F5180]   ; 0.0009999999747378752 = (double)(float)1e-3
      0x035ED996  ja  <skip>
      0x035ED998  xorps xmm0,xmm0 ... 0x035ED9BB movups [rsi],xmm0 / 0x035ED9C3 movsd [rsi+0x10],xmm1
      rsi = &Velocity  [M by dominance: the sole defining lea rsi,[rdi+0xe8] at 0x035EC9AC]

| state | `SizeSq2D` | vs gate | predicted | measured |
|---|---|---|---|---|
| ARM H sentinel `2^-10` | `9.54e-07` | 0.00095× | zeroed | zeroed in 250 ms ✓ |
| resting `(0,0,0)` | `0` | 0× | zeroed | never left `(0,0,0)` ✓ |
| ARM J sentinel `600` | `360000` | 3.6e8× | kept | walked 13,187 uu ✓ |
| walking at +10 s | `250000` | 2.5e8× | kept | still at the 500 cap ✓ |

⇒ **`Velocity == 0` is a FIXED POINT.** Zero ⇒ below the gate ⇒ written back to zero every frame ⇒
it can never leave zero on its own. **Escape needs `|V_xy| ≳ 0.0316`.**

⇒ ⛔ **"the physics does not work" is DEAD.** Falling, landing, ground movement, GAS speed clamping
and AI steering are all measured working. **The remaining problem is a KICK-OFF problem.**

⚠ **Two DISTINCT zeroing sites — do not merge them.** The bot's is the `PhysFalling` gate above.
The **player's** is the `CalcVelocity` `MaxInputSpeed` clamp, which fires because the untreated
player has `AnalogInputModifier = 0`. Each has its own measured signature.

---

## 1. THE TASKS

### T3-A — OFFLINE, FREE, ONE INSTRUCTION. Is `Velocity.Z` zeroed too?

`docs/s140-t2-armj-THE-BOT-WALKS.md` §4b grades this **`[I]`, not `[M]`**: *"The Z store takes
`xmm1`, and this document does not establish `xmm1 == 0` there."*

Settle it by reading `0x035ED998..0x035ED9C3` and tracing `xmm1`.

**Why it matters more than it looks.** If Z is zeroed too, the fixed point is **3-D**, and the
"a `MOVE_Falling` pawn with `GravityScale 1.000` that does not fall" phenomenon — unexplained since
S138 — is explained by the same instruction. It also decides **what a native kick has to look like**:
a purely-vertical impulse would be killed by a 3-D gate and survive a 2-D one. Do this first; it
conditions T3-B.

### T3-B — ★ THE CENTRAL TASK, OFFLINE. What, in the shipped game, ever kicks a hero off zero?

The escape is `|V_xy| ≳ 0.0316`. **Enumerate every native writer of `CMC+0xE8` that can clear it**,
and grade each **REAL / FOLD / DARK** *and* **reachable-on-this-route**:

- `ACharacter::LaunchCharacter`, `AddImpulse`, `AddRadialImpulse`, `AddForce`
- `ACharacter::Jump` / `DoJump` / `CheckJumpInput`
- knockback / damage-impulse paths (Loki-side)
- root motion (`HasAnimRootMotion`, `CurrentRootMotion`)
- **★★ THE DISMOUNT — and start here.** S132 measured `AuthPlayerDetachPlayerFromRidable`
  (impl `0x55CCCB0`) handing the hero back to physics: *"Before: motionless at `(0,0,13240)`. After:
  consecutive live reads 4.0 s apart give Z `-117,462.8` → `-121,560.9` with X and Y frozen — free
  fall, accelerating."* **That is a hero that ESCAPED the fixed point, measured, 8 sessions before
  anyone knew there was one.** Find out what in that path wrote a velocity, and whether it is
  reachable without the pod.
- spawn-time / `SpawnDefaultController` / possession-time impulses

**Deliverable:** a ranked table — writer, address, grade, what it needs to fire, and whether the
force-open route can reach it. **The prize is a kick the GAME performs**, so the recipe stops needing
an external `Velocity` write.

⚠ Every census here is a **FLOOR** — `.text` is 55.48 % decrypted and byte-pattern scans are blind to
`memcpy`/`rep movs` and register-computed addresses. Say so per claim.

### T3-C — ONE FLIGHT. Does the recipe generalise to the PLAYER?

The bot walks. **The player is untreated and its wall is a different site.** If ARM G (the GAS port)
plus one kick makes the **player** walk under the stock chain, then the tutorial hero becomes movable
**without `play`'s per-frame velocity puppet** — a real capability change, not just a diagnosis.

Build `gasattr-player` (or extend ARM G with a target selector) to treat the **player** hero, then
kick it. Predictions to pre-register:
- ARM G on the player should make `AnalogInputModifier` non-zero (it is computed from
  `Acceleration`/`MaxAcceleration`), which is exactly what the player's `CalcVelocity` clamp needs;
- with the kick, the player should fall/land/walk like the bot did;
- **the BOT is then the control** — treat one, not both, and say which.

⚠ **`play` must NOT be injected in this flight.** It writes `CMC+0xE8` and `+0x328` every hit and
would contaminate exactly the two fields under test.

### T3-D — OFFLINE. The shipping form.

ARM G writes into a **CDO default subobject** — process-wide, for the process lifetime, not undone.
That is fine for a diagnosis and unacceptable as a fix. Work out what a **per-instance** attribute
set would take: can the hero get its own `LokiAttributeSet` (constructed, not borrowed), and is there
a reflected route to it? Do not build it this session — scope it.

---

## 2. WHAT IS *NOT* SOLVED — keep this visible

- ⛔ **Still not a bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
  (`0x556DE53 → 0xF7EB60`) are stripped folds; nothing went through `SpawnBot`; the pawn has no hero
  class and no team.
- ⛔ **`LivingState` still has no native writer that sets Alive** — ARM F pokes it.
- ⛔ **`ALokiBotController::Tick`'s only motion driver is a RANDOM WANDER** (S137): no targeting, no
  ability use, no combat. A walking pawn is not a bot, and "the bot walks" must never be written as
  "the bot works".
- ⛔ ARM G / ARM H / ARM J are diagnoses. **None belongs in the default shim set.**

---

## 3. FLIGHT PROCEDURE AND BUDGET

```powershell
.\configs\s138-autostage.ps1 -MaxAttempts 5 -Label s141
```
Gate on **`[SP] done step=4` AND a live process** — never on the stager's completion message.
Then inject, wait for **`[BS] done`**, then read with `tools\re\cmc_earlyout_readout.py`.

⚠⚠ **FK-32 IS NOW PREDICTABLE AND TIGHT.** The `0xDEAD` series is **7 / 6 / 4 / 4 / 4 / 4**
injections at 1144 / 334 / 350 / 318 / 320 s — **three consecutive flights died on the 4th
manual-map at ~320 s.** Staging spends **3**. **You get essentially ONE injection.** Plan the flight
so the single injection carries everything, and **capture every result as you go** — nothing has been
lost to these deaths so far only because of that discipline.

**Regression gates** (verify with `python tools/sigbypass-mod/text_digest.py`, and they must not
move): `botai 5e47c13cf7f0a158` · `gasattr 2fcc2536e21f18e3` · `gasattr-ctrl 4465ebc4d7168c03` ·
`driverecompute a2a952babfed256b`.
Flown arms: `gasattr-sentinel ce56fd715de835a1` (flight 1) · `sentinel-burst 62b5423febd6f779`
(flight 2, intact in `dumps/s140-arms-t2/`) · `sentinel-big 52fceb9be6de532f` (flight 3, ARM J).
⚠ **Archive every arm before rebuilding** — flight 3's artifact was overwritten in `build/` and had
to be recovered from commit `3176139`.

---

## 4. ⚠ TRAPS — all have fired here

1. **`CMC+0x16C8` IS NOT A LATCH.** It reads 0 in every world. Any doc or tool that draws a verdict
   from it is wrong; Tier 1 §4 has the mechanism.
2. **The "inert sentinel" instinct is BACKWARDS at this gate.** `2^-10` was chosen *because* it was
   negligible — and negligible is exactly what falls under the threshold. **A smaller sentinel is
   zeroed harder.** ARM H survived only because it poisoned the payload rather than depending on the
   sentinel persisting.
3. **A verdict function inherited across a changed question is an uncalibrated instrument.** ARM H's
   verdict block printed `UNMODELLED` for the bot in flight 3 — correctly. **Read the samples.**
4. **A census returning all-negative is far more likely a broken instrument than a discovery.** A
   S140-T2 script unpacked the PE section header field order backwards and graded *everything* dark,
   including seven functions measured LIT an hour earlier. **The give-away was the contradiction with
   a prior measurement.** Always run a passing negative control (`Respawn 0x5A6AC40` is dark in every
   image) beside the positives.
5. **`MOVE_Custom == 7` on this build** — `MOVE_Dashing` is inserted at index 6. Stock tables
   mis-decode by one.
6. **The player is a CONTAMINATED control on `CMC+0xE8`/`+0x328`** whenever `play` is injected.
7. **Do not cross a function boundary with an inference** — S139 read a Loki-wrapper fact as an
   engine-callee fact and had to retract it.
8. **`LogCharacterMovement` is pinned but has NO positive control on this route.** Its silence is
   evidence about nothing. Do not cite the zero.

---

## 5. DELIVERABLES

Write `docs/s141-tier3-*.md`:

1. **T3-A**: the Z question, `[M]` either way, and what it implies for the shape of a native kick.
2. **T3-B**: the ranked native-kick table, with the dismount path resolved.
3. **T3-C**: the player flight — pre-registration committed **before** injection, and the result even
   if it is NOT OBTAINED.
4. **T3-D**: a scoped (not built) design for a per-instance attribute set.
5. **Corrections applied**, not just listed — to `CLAUDE.md`, `docs/next-session-prompt-s141.md`
   (mark it superseded at the top), and any doc still implying the physics is broken. This project
   loses corrections when the digest is not updated.

**If a task is unanswerable offline, say so and name the live read.** An honest "not established,
here are the survivors" is the correct output — S139's and S140's best artifacts both took that form.
