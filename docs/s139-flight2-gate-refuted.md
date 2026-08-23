# S139 flight 2 — the prime suspect is refuted, and my own enumeration was unsound

Written 2026-08-23. Read-only RPM throughout; **no injection at all** this flight (the question was
answerable from the player alone). Client PID 35608, BASE `0x7FF704F00000`, staged on attempt 1.
Predecessor: `docs/s139-flight1-the-bot-is-not-special.md`.

---

## 0. HEADLINE

**`bSimulatePhysics = 0`. The gate I named as the prime suspect PASSES. And a population control
shows `StartNewPhysics` has never run for ANY of the 37 movement components in the world.**

Then, while writing it up, I found the flaw in my own §7b argument: **the "exactly 6 branches skip
the call" enumeration came from a LINEAR disassembly sweep over a 4.6 KB function, and a linear
sweep over x86 with inline jump tables is not a sound CFG.** So the contradiction below is not a
contradiction in the game — it is the expected result of an unsound enumeration.

---

## 1. THE READ [M]

    R6.BodyInstance.off              @+0x3F0
    R6.bSimulatePhysics              0        byte@+0x10 mask 0x01
    R6.bEnableGravity                1        byte@+0x10 mask 0x04
    R6.bNotifyRigidBodyCollision     0        byte@+0x12B mask 0x08

★ **The decode carries its own positive control:** `bSimulatePhysics` and `bEnableGravity` live in
the **same byte** under different masks and read **0 and 1**. A decode that could not discriminate
would return them equal. (`FBoolPropertyParams` carries no ByteOffset/ByteMask — the S132 trap — so
these come from the LIVE `FBoolProperty` at `+0x70..+0x73`.)

⇒ `UpdatedComponent->IsSimulatingPhysics()` returns FALSE ⇒ **gate 3 (`0x035E9FBD jne`) PASSES.**

### Everything else re-measured live, on the same client

| gate | address | input | verdict |
|---|---|---|---|
| HasValidData #1 | `0x035E9F1F` | `UpdatedComponent` `0x26E95CB11E0`, `CharacterOwner` `0x26E90802AE0`, RF_Garbage 0 | PASSES |
| World null | `0x035E9F28` | `CMC+0xC0 = 0x26E65E86B40` | PASSES |
| MovementMode == MOVE_None | `0x035E9F97` | **3** | PASSES |
| Mobility != Movable | `0x035E9FA4` | **2** | PASSES |
| IsSimulatingPhysics | `0x035E9FBD` | **bSimulatePhysics 0** | **PASSES** |

**And the vtable was verified LIVE against every offline address** — `[vt+0x720]` → rva `0x55C2430`
(StartNewPhysics), `[vt+0xAA8]` → `0x55B8370` (PerformMovement), `[vt+0x3D0]` → `0x55C2B90`
(TickComponent), `[vt+0x890]` → `0x55A7680` (ControlledCharacterMove); CMC vtable rva `0x88F8570`.
**4/4 agree with the offline diff.**
**And `TimeSinceFallingStart` resolves BY NAME to `+0x12B0`** on the live class (it had only been
hardcoded before) — so the "DeltaTime is real" result of flight 1 stands on a by-name read.

---

## 2. ★★ THE POPULATION CONTROL — 37 components, every latch 0

A walk of all 192,369 live objects found **37** `*CharacterMovement*` components.

- **Every one reads `+0x16C8 == 0`.** ⇒ `ULokiCMC::StartNewPhysics` has never run for any character
  in this world.
- **Exactly ONE is doing anything at all**: our player hero's (`0x26EC6750010`,
  `TimeSinceFallingStart 364.712`, `MovementMode 3`). The other 36 read `TimeSinceFallingStart 0.000`
  and `MovementMode 0 (MOVE_None)` — pooled/unpossessed, inert.

⇒ ★ **There is no moving character anywhere in this world to use as a control.** That is worth
knowing before anyone designs another "diff against a working one" experiment.

---

## 3. ⚠⚠ THE SELF-CORRECTION — my §7b enumeration is NOT sound

`docs/s139-flight1-the-bot-is-not-special.md` §7b said the bail is one of **exactly 6** branches, and
this flight measured 5 of them passing, leaving one (`0x035EA25D`, a second `HasValidData`) whose
three inputs are *also* measured good. That is a flat contradiction — and the resolution is a defect
in my instrument, not a fact about the game:

**The enumeration came from `capstone` disassembling `0x035E9EC0..0x035EB13A` LINEARLY** — 1,074
instructions across ~4.6 KB. x86-64 is variable-length, and a function that size in UE certainly
carries **inline jump tables and alignment padding**. A linear sweep desynchronises on those and
emits garbage instructions, so it can silently **miss real branches**.

★ **I had already seen this failure in the same session and did not connect it:** disassembling
`ULokiCMC::PerformMovement` from `0x055B85A0` produced the single bogus instruction `or al, 0xff`,
because that address is mid-instruction.

⇒ I downgraded "exactly 6 skip-branches" from [M] to [S] on that basis — **and then ran the CFG walk,
which VINDICATED it.**

### ★ The CFG walk (recursive descent from the entry, branch targets followed)

    CFG-reachable instructions : 1461      (the linear sweep had claimed 1074 -- it missed ~390)
    call 0x035EB13A reachable  : True
    branches skipping the call : 56 total, of which the ones BEFORE the call are
                                 EXACTLY the same six: 0x035E9F1F, 0x035E9F28, 0x035E9F97,
                                 0x035E9FA4, 0x035E9FBD, 0x035EA25D
    other exits                : one ret, at 0x035EB1CA.  NO indirect jumps.

The other 50 skip-branches are all at addresses **after** `0x035EB13A`, i.e. downstream of the call.

⇒ **The linear sweep was genuinely unsound (390 instructions missed) and happened to be right about
the region that matters.** Both halves belong in the record: the instrument was bad, and the answer
survives a good instrument. **Restore the enumeration to [M] — by CFG walk, not by linear sweep.**

⇒ ⚠⚠ **THEREFORE THE CONTRADICTION IS REAL, NOT AN ARTIFACT:** all six exits have their inputs
measured passing, and `StartNewPhysics` still never runs.

### ⚠⚠⚠ RETRACTED, SAME DAY — THERE IS NO CONTRADICTION. I MISREAD A WRAPPER FACT AS A CALLEE FACT.

`+0x12B0` is accumulated at **`0x055B840C`**, which is **UPSTREAM of the Super call at
`0x055B85C1`**. So *"`+0x12B0` advances at real time"* establishes only that **`ULokiCMC::
PerformMovement` ran with dt > 0** — it establishes **nothing** about whether the *engine's*
`PerformMovement` reached anything. My §0/§4 leg "engine `PerformMovement` is entered and all six of
its exits pass" was never supported by that measurement.

⇒ **`latch 0` + `dt advancing` is a fully consistent THIRD SURVIVOR**, not a paradox: Loki's
`PerformMovement` runs, calls the Super, and the ENGINE bails at one of its own gates to
`0x035EB7CF` — a block that writes no Velocity and no transform.

★★ And a further gate exists that this document never had: **engine `StartNewPhysics 0x03600990`
carries its OWN `IsSimulatingPhysics` test** (`0x036009D3` / `0x036009E4` / `0x036009EC`) which
**logs** *"…UpdateComponent (%s) is simulating physics - aborting."* (`.rdata 0x07FC0670`,
`CharacterMovementComponent.cpp:3477`, threshold 5 = `Log`). ⚠ Grepped: **0 occurrences — and
`LogCharacterMovement` occurs 0 times in the whole log, so there is NO positive control and that
zero is UNINTERPRETABLE.** Pinning the category is S140's first move (`docs/next-session-prompt-s140.md`
§0a).

★ **Why this matters beyond the fact:** the retraction was produced by an adversarial lane that had
the same bytes I did and read the *ordering* I skipped. **The measurement was right; the inference
crossed a function boundary.** Both halves of §3 above now carry the same lesson from opposite
directions — an unsound instrument that got the right answer, and a sound measurement that carried a
wrong inference.

⚠ Related caveat found the same way: I tried live **page protection** (`VirtualQueryEx`) as an
"has this function executed?" test, exploiting the protector's decrypt-on-execute. All 14 probed
addresses read `EXECUTE_READ`. **That instrument is too coarse here** — page granularity is 4 KiB and
`StartNewPhysics 0x055C2430` shares page `0x55C2000` with `TickComponent 0x055C2B90`, which certainly
runs; `PhysFalling 0x055B89F0` shares `0x55B8000` with `PerformMovement`. **It is a floor, not a
discriminator.** It would still be decisive for a function that is alone on its page.

---

## 4. WHAT STANDS, AND AT WHAT GRADE

| claim | grade |
|---|---|
| `ULokiCMC::PerformMovement` runs with a real, non-zero DeltaTime | **[M]** — `TimeSinceFallingStart` (by-name `+0x12B0`) advances at 1.0× real time; it accumulates `xmm6`, the register HitStop would zero |
| `ULokiCMC::StartNewPhysics` has never run, for any of 37 components | **[M]** — the latch write at `0x055C2469` is on the unconditional fall-through |
| The five named gates all pass | **[M]** — each input read live, `bSimulatePhysics` with a same-byte two-sided control |
| Loki's `PerformMovement` reaches its Super unconditionally | **[M, bounded]** — 0 rets before `0x055B85C1` and the only skip-branch is after it, over a **144-instruction** linear sweep (short enough that desync is unlikely, but it is the same instrument) |
| **"Exactly 6 branches skip `StartNewPhysics`"** | **[S] — RETRACTED from [M]**, see §3 |

---

## 5. NEXT — a real contradiction, and the two candidates that survive it

The CFG walk is done (§3) and it made the contradiction sharper rather than dissolving it:
**six exits, all measured passing, and `StartNewPhysics` still never runs.** One of the six readings
must be measuring something other than what its branch tests. Ranked:

1. ★★★ **Gate #5 — `IsSimulatingPhysics` may be answering about a WELD PARENT, not this capsule.**
   `[capsule vt+0x4C0] = 0x03C9B0A0` opens
   `mov r9d,0xFFFFFFFF; mov r8b,1; call [rax+0x810]` — i.e. `GetBodyInstance(BoneName, **bGetWelded =
   true**, Index = -1)`. With welding on, that can return **a different component's** `FBodyInstance`.
   So `this->BodyInstance.bSimulatePhysics == 0` does **not** settle what the call returns.
   **Test:** read the weld parent / call the vtable function, or read `BodyInstance.WeldParent`.
   This is the only candidate where a measured input and the tested condition are provably
   *different objects*, which is exactly the shape a false "passes" takes.
2. ★ **Gate #6 — `HasValidData` #2 (`0x035EA255`).** Its three inputs (`CMC+0xD0`, `CMC+0x198`,
   `CharacterOwner ObjectFlags` bit30) are stable fields measured good, so this requires something to
   null one **transiently, mid-tick**, between `0x035E9F17` and `0x035EA255`. Possible, unevidenced.
3. ⚠ **Or `+0x12B0` is not written by `PerformMovement`** and the "PerformMovement runs" leg is
   wrong. **I could not settle this**: a disp32 byte-pattern scan for writers of `[reg+0x12B0]`
   produced obvious desync garbage (`adc byte ptr [rbp+0x12b0]`) and **failed to find the two
   instructions I already know exist** at `0x055B840C`/`0x055B8414`. That scan is unusable — the
   repo's own "a disp32 scan is a FLOOR, not a census" rule. A CFG-based writer census is needed.

⚠ **Do not spend another flight on gates 1–4.** They are banked, live, with controls.
★ Candidate 1 is answerable **offline** (transcribe `0x03C9B0A0` and the `[vt+0x810]` callee) and
then with **one read** of the weld state.

## 6. ARTIFACTS

| path | what |
|---|---|
| `docs/s139-f2-BASELINE.txt` | the full ranked read incl. `R6.*` |
| `tools/re/cmc_earlyout_readout.py` | now decodes `FBodyInstance` bitfields from the live `FBoolProperty` |

Client PID 35608 was still alive at write-up; no injection was performed this flight.
