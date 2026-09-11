# S140 TIER 2 — does `StartNewPhysics` actually run? Build one arm, fly it once.

**Paste this whole file as the opening prompt of a fresh session.**

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` first (auto-loaded; current as of commit `fd09ba4`), then
**`docs/s140-tier1-cfg.md` — its §5 and §7 are this session's brief.**

This session is **offline prep + ONE staged flight**. Use the **Workflow tool with adversarial
verification** for the offline half (build + pre-registration review), then fly by hand. Budget
~6–9 agents. Do not fan out subagents onto the live client — one operator, one client.

---

## 0. WHERE THIS STANDS — read this before forming any hypothesis

Tier 1 (offline, 13 agents, four independently written CFGs) produced a **retraction**, not a
confirmation:

- **[M] The six exits from engine `PerformMovement 0x035E9EC0` to its single
  `call [rax+0x720]` at `0x035EB13A` are EXACT AND COMPLETE.** 1,461 instructions, 0 indirect
  jumps, 0 decode failures, 0 coverage gaps (6538/6538 bytes), 2 backward edges in the whole
  function with **neither** in the reachable set. **There is no seventh path.** Five of the six
  dominate the call; `0x035EA25D` is a redundant second `HasValidData` in the optional root-motion
  block.
- ⚠⚠ **AND IT DOES NOT MATTER, BECAUSE THE INSTRUMENT WAS INVALID.** `CMC+0x16C8` is **not** a
  sticky "StartNewPhysics ever ran" latch. It is a within-call `TOptional<FVector>` validity flag:
  `ULokiCMC::StartNewPhysics` **sets** it at `0x055C2469`, and **`ULokiCMC` vtable disp `0xA50`
  (`0x0530ABF0`) CLEARS it** when engine `PerformMovement` calls that slot at `0x035EB569` — later
  in the same call, on a path the `StartNewPhysics` call site dominates. **An off-thread reader
  sees `0` whether the physics step runs every frame or never runs at all.**

⇒ **S139's `[M]` "StartNewPhysics has never run on either component" is RETRACTED to
UNINTERPRETABLE**, along with everything derived from it (including "no StartNewPhysics ⇒ no
PhysFalling ⇒ no gravity"). **The contradiction S140 was convened to resolve does not exist.**

**What still stands, and it is a lot:**

    the AI runs -> ControlInputVector is written and CONSUMED every frame            [M]
    the whole E1..E7 tick early-out ladder is PASSED                                 [M]
    ControlledCharacterMove RUNS                                                     [M, signed zero]
    the input wall was GetMaxAcceleration() == 0, and S139 flight 4 CLOSED it:
        Acceleration / ControlInputVector = 49999.63 mean over 40 components,
        with the untreated PLAYER non-zero in 0 of 20 as a within-run control        [M]
    Velocity == (0,0,0).  Translation 0.00 uu.  Still.                               [M]

⇒ **The likeliest state of the world is now the SIMPLE one:** everything upstream runs,
`StartNewPhysics` runs every frame, and something **downstream** of it fails to turn a real
`Acceleration` into `Velocity`. **This session's job is to establish whether that is true.**

---

## 1. THE TASKS

### T2-A (offline) — build **ARM H**, the sentinel probe

**The question:** does `ULokiCMC::StartNewPhysics 0x055C2430` execute?
**The only durable readout in the whole structure** is the Velocity snapshot at `CMC+0x16B0`:
- [M] the `0xA50` override clears only the flag byte at `+0x16C8`, **never the payload**;
- [M] the payload write `0x055C244F` is on the same `Iterations == 0` path as the set, `0x1A`
  bytes before it;
- [M] a `+0x16B0` displacement census finds **exactly one** CMC-side writer — that store.

So: **write a sentinel into `Velocity (CMC+0xE8)`, wait ≥ 3 frames, read `CMC+0x16B0`.**

**THE SENTINEL IS `(0.0009765625, 0.0, 0.0)`** — `2^-10`, exactly representable, and physically
inert at ~0.001 uu/s.
⛔ **Do NOT use a large value** (an earlier lane proposed `(1234.5, 6789.25, -4242.125)`). That is
~8,000 uu/s: if the physics step *is* running it launches the pawn and perturbs the system under
test.

**Implement it IN-PROCESS as a new arm, not with external `WriteProcessMemory`.** External WPM is a
repo-recorded **unresolved hazard** (S138, n=1, confounded by a very high FK-32 base rate). An
in-process write on the game thread is the project's normal pattern and avoids the question
entirely.

ARM H shape:
- gate it on `KBSPSARMS` **bit 9 (`0x200`)**, alongside ARM G's bit 8;
- add build variant **`gasattr-sentinel`** = `gasattr` + bit 9, i.e. `-DKBSPSARMS=0x3A0`
  (`gasattr` is `0x1A0`). Keep `gasattr` itself untouched;
- resolve the bot's CMC exactly as ARM F/G do (`g_psLbCtl[1]` → `+0x3F8` → pawn → `+0x458`);
- **assert the identity controls first** (`CMC+0x198 == pawn`, `FTickFunction Target (CMC+0x68) ==
  CMC`) and REFUSE if either fails — `ALokiCharacter` has its own live byte at `+0x16C8`, and a
  probe aimed at the pawn decodes a plausible wrong value;
- **print the pre-registered decision rule BEFORE writing**, so the result cannot be reinterpreted;
- write the sentinel to `CMC+0xE8/+0xF0/+0xF8`, readback-verify, record the game-thread hit index;
- on a **later** hit (≥ 3 game-thread callbacks after the write), read back `CMC+0x16B0..+0x16C7`
  **and** `CMC+0xE8`, and print the verdict computed from the observed values.

**THE DECISION RULE — pre-register it verbatim:**

| observation | verdict |
|---|---|
| `+0x16B0` holds the sentinel | **`StartNewPhysics` RAN with `Iterations == 0`** [M] |
| `+0x16B0` still `(0,0,0)` **AND** `+0xE8` still holds the sentinel | **it did NOT run** [M] |
| `+0xE8` no longer holds the sentinel | the probe's own control failed — **the run is VOID** |

⚠⚠ **NAME THIS TRAP IN THE WRITE-UP, because a successor will find it:** S139 already banked
`R1.velsnap@0x16B0 = (0.000,0.000,0.000)` in `docs/s139-f1-BOT.txt:19` and
`s139-f1-BASELINE.txt:20`. **That reading is UNINTERPRETABLE for the same reason as the flag** —
the snapshot's source (`Velocity`) was itself `(0,0,0)` and `NewObject` zero-fills, so written and
never-written are the same bytes. **It is not a second, independent negative.** The sentinel exists
precisely to break that degeneracy.

⛔ **The write-free alternative is DEAD — foreclose it explicitly so nobody spends a flight on it.**
`GetRecentVelocity` is a reflected UFunction (thunk `0x0530C7E0`) reachable by the S55 primitive
with zero writes, but with `Velocity == (0,0,0)` **both arms of its `cmove` return `(0,0,0)`.** It
cannot discriminate.

### T2-B (same pass, free) — three reads nobody has taken

Add these to `tools/re/cmc_earlyout_readout.py`; each costs one read and each closes a real gap:

1. **`CMC+0xC0` `WorldPrivate`** — exit 2's input, **the one mandatory gate never read live**.
   ⚠ Tier 1 found that a lane recorded it `measured: YES` and **could not find the measurement** —
   an `[I]` laundered into an `[M]`. It is currently `[I, strong]`, not `[M]`.
2. **`CMC+0x3E4` `MaxSimulationIterations`** — a **FOURTH** engine-`StartNewPhysics` early-out
   present in no S139/S140 document: `0x036009B5 cmp r8d,[rcx+0x3e4]` / `0x036009BC jge`. With
   `r8d == 0` it bails iff the field is `<= 0`. (There is also a **third** `HasValidData` at
   `0x036009C5`.)
3. **The live vptr:** `*(uint64_t*)CMC` vs `ImageBase + 0x088F8570`. If the component were a plain
   engine `UCharacterMovementComponent`, disp `0x720` → `0x03600990` and **nothing would touch
   `+0x16C8` at all**. Tier 1 showed no subclass vtable exists, so the engine base is the only
   alternative — but it has never been asserted on the bot.

### T2-C (optional, and only if the injection budget allows) — the known-moving configuration

`play` is the one configuration this project records as making a hero translate (+2,945.7 uu). It
does so by writing `CMC+0xE8`/`+0x328` every game-thread hit. **Nobody has verified recently that it
still translates on this route**, and if it does, then the whole downstream chain demonstrably works
for the player and a bot/player diff becomes meaningful again.
⚠ It is the **5th or 6th** injection into the process by then — see the FK-32 budget below. Treat it
as a bonus, not a requirement, and **do not** let it cost you the T2-A result.

### T2-D (ride-along, low value — do not build on it)

Pin **`LogCharacterMovement=Log`** in the **user** `Engine.ini` via `configs/set-log-verbosity.ps1`
(FK-11's proven channel; `-LogCmds` and `-ini:` do **not** work). Engine `StartNewPhysics` logs
`.rdata 0x07FC0670` *"UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is
simulating physics - aborting."*
⚠⚠ **It is NEGATIVE-ONLY and has NO positive control.** It fires only when `IsSimulatingPhysics()`
is TRUE, which S139 measured **FALSE** (`bSimulatePhysics = 0`, `WeldParent = NULL`). **Its silence
is uninterpretable.** Do it to give the category a voice for future sessions; do not draw a
conclusion from it.

---

## 2. FLIGHT PROCEDURE

```powershell
# ELEVATED PowerShell. Steam must already be running.
cd "G:\git\Supervive Revival Project"
.\configs\s138-autostage.ps1 -MaxAttempts 5 -Label s140t2
```
Gate on **`[SP] done step=4` in `docs\tutorial-launch-marker.txt` AND a live process** — never on
the stager's own completion message (a stage script saying "done" means *it* finished injecting, not
that the payload finished working; that defect once killed three perfectly staged clients).
PID/BASE land in `docs\s138-staged-pid.txt`.

Then, into the staged client:
```
tools\inject\inject.exe mmap <PID> "G:\git\Supervive Revival Project\tools\sigbypass-mod\build\tutorial_launch_gasattr_sentinel.dll"
```
Wait for **`[BS] done`** before reading anything. Then run the extended
`tools\re\cmc_earlyout_readout.py <PID> <BASE>`.

★ **Take a BASELINE read before injecting.** It costs nothing and it gave S139 its player-side
control independent of the arm.

⚠ **FK-32 INJECTION BUDGET.** Clients die silently after roughly **4–7** manual-maps. Staging spends
**3** (`gft`/`fo`/`sp`). So: `gasattr-sentinel` is #4, `play` would be #5. **Capture every result as
you go — do not batch reads to the end.** Three S139 clients died mid-probe; each time the already-
written data survived and only the un-taken read was lost.

**Arms and gates** (verify with `python tools/sigbypass-mod/text_digest.py <dll>...` before flying):

| build | RAW digest | role |
|---|---|---|
| `gasattr` | `2fcc2536e21f18e3` | ARM D+F+G (bot + gate + GAS) |
| `gasattr-ctrl` | `4465ebc4d7168c03` | ARM G compiled out — verified DISTINCT |
| **`gasattr-sentinel`** | *(new — record it)* | ARM D+F+G+H |
| `driverecompute` | `a2a952babfed256b` | regression gate, must not move |
| `botai` | `5e47c13cf7f0a158` | regression gate, must not move |

**Both regression gates must be byte-unchanged after your edits** — every change belongs behind the
arm bit.

---

## 3. IF `StartNewPhysics` DOES RUN — where the wall actually is

Then the failure is **downstream**, and the next target is already identified:

- `ULokiCMC::PhysFalling 0x055B89F0` (vtable disp `0x830`, a verified slot). Its body opens
  `cmp byte [rcx+0x231], 7` — note **7**, because *this build inserts `MOVE_Dashing` at index 6*, so
  `MOVE_Custom == 7`. Any probe carrying stock UE's `MOVE_Custom == 6` mis-decodes by one.
- `CalcVelocity`, and `GetMaxSpeed 0x055ACB90` — the sibling of the getter that caused the input
  wall. ARM G set `MoveSpeed`/`MaxMoveSpeed` to **500**; if `GetMaxSpeed` is still returning 0
  through a different path, `CalcVelocity` clamps everything to zero and that is the whole answer.
- Rung 5 of Tier 1's ladder: poke `CMC+0x3DC` (`NumJumpApexAttempts`) to a sentinel to separate
  "engine `PerformMovement` entered **this frame**" from "entered once, long ago".

Write the offline transcription of `PhysFalling` as a Tier-3 item; do not start it this session.

---

## 4. ⚠ TRAPS — all of these have fired here

1. **A verdict line can lie.** Compute verdicts from observed data and print the data. Two probes in
   S138/S139 printed confident verdicts their own samples contradicted.
2. **`set()` collapses `-0.0` and `0.0`.** That hid the entire S139 flight-3 finding until the
   printed samples were read. **Record raw, derive after.**
3. **Do not cross a function boundary with an inference.** "`+0x12B0` advances" is a fact about the
   Loki *wrapper*, not about the engine impl — S139 read it as the latter and had to retract.
4. **`ALokiCharacter` has its own live byte at `+0x16C8`.** Assert `CMC+0x198 == pawn` before
   reading anything at that offset.
5. **The player is a CONTAMINATED control on `CMC+0xE8` and `+0x328`** if `play` is injected — it
   writes both every hit. Use it on structural fields only.
6. **`play` moving the hero never meant it walked** — `KFLYMODE=5` makes it hover.
7. **Two instruments that fail the same way are not corroboration.** Keep a second, already-trusted
   probe (`tools/re/movementmode_readout.py`) on hand — it localised two probe defects in minutes
   in S139 by being run against the same live process.
8. **`usmapdump dumpimage`'s "process not found" is ambiguous** between a wrong name and a dead
   client. Check `Get-Process` before believing either.
9. Every offline census here is a **FLOOR** — `.text` is 55.48 % decrypted and the censuses are
   blind to `memcpy`/`rep movs` and register-computed addresses.

---

## 5. DELIVERABLES

Write `docs/s140-tier2-sentinel.md`:

1. **The pre-registration**, in its own file, written and committed **before** the injection.
2. **The verdict on `StartNewPhysics`**, with the decision-rule row it landed on, and the probe's own
   control (`+0xE8`) stated either way.
3. The three free reads (`+0xC0`, `+0x3E4`, vptr), each graded.
4. **What it means for the framing**, and if the answer is "it runs", the ranked downstream targets.
5. **Corrections to `CLAUDE.md` and `docs/s139-*.md` / `docs/s140-tier1-cfg.md`** — quote the stale
   text, give the replacement, and **apply them**. This project loses corrections when the digest is
   not updated; Tier 1 wrote ~20 and applying them is why `CLAUDE.md` is currently trustworthy.
6. Record the new `gasattr-sentinel` digest and re-verify both regression gates.

**If the flight is lost to FK-31/FK-32 before the readback, say "NOT OBTAINED" and keep the
pre-registration unmodified.** That is a clean non-result and it is worth more than a reinterpreted
one — S139 flight 2 did exactly this and the pre-registration is what kept it honest.

---

## 6. SCOPE — do not overstate

⛔ **This is not a bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
(`0x556DE53 → 0xF7EB60`) are stripped folds; nothing here went through `SpawnBot`; the AI pawn's
`PlayerState`, `LokiBotController` and behaviour tree exist only because of pokes the game never
performs itself.
⛔ **ARM G is a process-wide CDO poke and a diagnosis, not a shipping fix.** ARM H adds a write to a
live component's `Velocity`. Neither belongs in the default shim set.
⛔ **The pawn still moves 0.00 uu.** Nothing in Tier 1 changed that — it changed what we know about
*why*.
