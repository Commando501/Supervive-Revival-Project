# S140 TIER 1 — offline CFG work on the physics-step wall. NO LAUNCHES.

**Paste this whole file as the opening prompt of a fresh session.**

---

You are continuing the SUPERVIVE revival project at `G:\git\Supervive Revival Project`.
Read `CLAUDE.md` first — it is auto-loaded and its S139 block is current as of commit `fc7ee50`.

**This session is OFFLINE. Do not launch the game. Do not inject anything. Do not stage a tutorial
world.** Everything below is static analysis of a dumped PE image plus reading source already in the
repo. If you find yourself wanting a live read, write it down as a Tier-2 item and move on.

**Use the Workflow tool with adversarial verification** — fan the three tasks out as parallel lanes,
each followed by a verifier whose job is to refute it, then a synthesis that adjudicates. That
structure has caught four wrong headlines in this project in the last two sessions, including two of
mine. Budget ~9–13 agents.

---

## 0. WHERE THIS STANDS (all [M] unless marked)

An AI-controlled hero pawn ("the bot") exists in a staged tutorial world. Its behaviour tree runs,
its wander driver produces a fresh horizontal unit vector every ~2 s, and that reaches the pawn's
`ControlInputVector`. S139 established, across four flights:

    ConsumeInputVector at 0x036037FE drains ControlInputVector EVERY FRAME
      -- and it is called BEFORE both early-outs, so consumption != simulation
    the whole E1..E7 tick early-out ladder is PASSED
    ControlledCharacterMove RUNS
      [proof: Acceleration @CMC+0x328 carried ControlInputVector's SIGN in 22/22 samples --
       a signed zero, i.e. input x 0. A never-written field is +0.0 forever and cannot track a sign.]
    the input wall was GetMaxAcceleration() == 0 (GAS-backed getter, AttributeSetStorage NULL)
      -- CLOSED at flight 4 by porting ds_hybrid.cpp:2370-2430 onto the bot:
         MEASURED Acceleration / ControlInputVector = 49999.63 mean over 40 components,
         with the untreated PLAYER at 0/20 non-zero as a within-run specificity control.
    *** AND YET: ULokiCMC::StartNewPhysics is NEVER ENTERED ***
      latch CMC+0x16C8 == 0 on the bot, on the player, and on ALL 37 movement components
      in the world (of which exactly ONE is doing anything at all).
      Velocity stays (0,0,0). The pawn moves 0.00 uu. No gravity, at 13 km with nothing beneath it.

**THE CONTRADICTION THIS SESSION MUST ATTACK.** A written `Acceleration` proves
`ControlledCharacterMove` ran. It calls `PerformMovement` at `0x035DCDAC` whenever
`Role == ROLE_Authority` (measured **3**). `ULokiCMC::PerformMovement 0x055B8370` reaches its Super
**unconditionally** (0 rets before `0x055B85C1`; the only skip-branch is *after* the call). So engine
`PerformMovement 0x035E9EC0` is entered. A CFG walk found **exactly six** branches that skip its
single `call [rax+0x720]` at `0x035EB13A`, and **all six have their inputs measured passing.**

Either one of the six is measuring something other than what its branch tests, **or the enumeration
is incomplete** — and I know its predicate was flawed. That is task A1.

---

## 1. THE THREE TASKS

### A1 — ★ RE-ENUMERATE THE EXITS WITH A SOUND CFG ANALYSIS

**The defect:** my enumeration collected branches whose `target > 0x035EB13A`. **That predicate is
structurally blind to a BACKWARD bail** — a jump to a *lower* address into a block that then exits —
and it is the weakest link in the whole "six exits" claim.

**The correct instrument: backward reachability from the call node.**
1. Build the CFG of `0x035E9EC0` by recursive descent (I measured **1,461** reachable instructions;
   a linear sweep decodes only **1,074** and is unsound here).
2. Compute the set `R` of basic blocks that **can reach** `0x035EB13A`.
3. Every edge from a block in `R` to a block **not** in `R` is a bail. That is the true exit set.
4. Compare against my six: `0x035E9F1F`, `0x035E9F28`, `0x035E9F97`, `0x035E9FA4`, `0x035E9FBD`,
   `0x035EA25D`. **Report any I missed, and any of mine that is not a real exit.**

Also handle, and say explicitly how you handled each:
- **indirect jumps / jump tables** (my walk found none in this function — verify that, don't assume);
- **calls that may not return** (a `call` to a noreturn helper is an exit my walk treats as
  fallthrough);
- the single `ret` at `0x035EB1CA` and every path that reaches it;
- whether any of the six is *unreachable* given the others (i.e. dominated), which would change
  which measurements matter.

**Deliverable:** the exit set with, for each, the address, the condition, the exact field + offset +
owning class it tests, and whether that field has already been measured (see §3).

---

### A2 — BUILD A PROGRESS LADDER OUT OF WRITE-RECEIPTS

Right now the only live receipt for "how far did engine `PerformMovement` get" is the
`StartNewPhysics` latch, which is all-or-nothing. **Find intermediate ones.**

Enumerate every **store to a CMC field** (`[rbx+disp]` where `rbx` is the `this` pointer) on the path
from `0x035E9EC0` to `0x035EB13A`, and for each report:
- address, offset, width, and the value written (constant? computed? from which source?);
- **whether it can discriminate**: a store of a constant `0` into a field that is already `0` is
  useless as a receipt. **Say so per field** rather than listing them all as instruments;
- whether it is unconditional on the path, or inside a branch (and which).

Two I already noticed, as starting points and calibration:
- `0x035E9F82  mov byte [rbx+0x703], al`  — early, after HasValidData + the World test, before the
  three gates. `al` is a computed bool from the preceding `ucomisd` chain.
- `0x035EB130  mov dword [rbx+0x3dc], r15d` — immediately before the call, with `r15d == 0`.

**Do the same for `ULokiCMC::PerformMovement 0x055B8370`** between the `+0x12B0` accumulate at
`0x055B840C` and the Super call at `0x055B85C1`, so a future flight can tell "Loki's wrapper ran" from
"the engine impl was entered" — a distinction I got wrong once this session (see §4).

**Deliverable:** a ranked table of live-readable checkpoints, each with its offset, what reaching it
proves, and its discriminating power. Flag any that require a known non-default baseline.

---

### A3 — CLOSE THE `+0x12B0` WRITER QUESTION

`CMC+0x12B0` is `TimeSinceFallingStart` (confirmed by name on a live class). I used "it advances at
wall-clock rate" as evidence that `PerformMovement` runs — **and had to retract the inference**,
because the accumulate at `0x055B840C` is *upstream* of the Super call, so it says nothing about the
engine impl. Three writers are believed to exist:

| address | context | status |
|---|---|---|
| `0x055B840C` / `0x055B8414` | `ULokiCMC::PerformMovement`, `addss` then `movss`, using `xmm6` = DeltaSeconds | confirmed by me |
| `0x055C2483` / `0x055C248B` | `ULokiCMC::StartNewPhysics`, `Iterations > 0` arm, behind `cmp byte [rcx+0x231],3` | reported by a verifier, **re-derive it** |
| `0x055A74D6` | "client-correction bulk float restore" | **reported, unverified — settle it** |

⚠ **My byte-pattern scan for these was garbage** — it back-decoded from every occurrence of the dword
`0x000012B0`, produced obvious desync artifacts (`adc byte ptr [rbp+0x12b0]`), and **failed to find
the two instructions I already knew existed.** Do not repeat that method. Use a CFG-based scan over
decoded instructions with the displacement taken from capstone's operand, not from a byte search.

**Deliverable:** the complete writer set for `+0x12B0` **within the Loki CMC class**, each graded,
plus a plain statement of what an advancing `+0x12B0` does and does not prove.

---

## 2. TOOLING AND CONVENTIONS

**Image:** `dumps/merged13.dump.exe` — ImageBase `0x7FF608F40000`, **RVA == file offset** (all ten
sections have `VirtualAddress == PointerToRawData`; verify it yourself once). `.text` is ~55.5 %
demand-decrypted; **an all-zero page is DARK = never executed, which is NOT "absent" and NOT
"stripped"**. Grade three-state **FOLD / REAL / DARK**.

**Fold (stripped-stub) addresses** — an impl equal to one of these is an empty stub:

    0x00F7EC20  c2 00 00     ret 0   (VOID no-op; does NOT zero eax)
    0x00F7EB50  33 c0 c3     null/0
    0x00F7EB60  32 c0 c3     false
    0x00B9E1F0  b0 01 c3     true
    0x00FC6CF0  0f 57 c0 c3  0.0f

⚠ A **sixth** shape defeats a two-state test: `sub rsp,0x28; call <GetWorld>; xor eax,eax; ret`.
It grades REAL under a naive test and is not DARK either. **Only reading instructions is reliable.**
⚠ **A folded RVA names nothing** — `0xF7EC20` has ~165,789 references.

**Tools:** python 3.13 with **capstone 5.0.7** installed (write your own harness — fastest route);
`tools/strxref/strxref.py` (`find` / `xref` / `func`, defaults to `merged13`);
`tools/strxref/vtables.py` ⚠ **its cached index is built on `merged2`, a different image with a
different ImageBase** — `.rdata` vtable starts are safe, but **re-read every CODE grade from
`merged13`**. Scratch under `scratchpad/s140/`.

**Grades:** `[M]` measured with a stated control · `[I]` inferred (say from what, how strongly) ·
`[S]` speculation. **An `[I]` stated as `[M]` is the most costly error class in this project.**
Every claim needs a **positive control** — something you know the answer to, through the same tool,
coming back right. Report the control and its result beside the finding.

---

## 3. THE MEASUREMENTS ALREADY BANKED — do not re-derive, do not contradict silently

Live, with identity controls passing (`CMC+0x198 == pawn`, `FTickFunction Target == CMC`):

| field | offset | bot | player |
|---|---|---|---|
| `UpdatedComponent` | `CMC+0xD0` | non-null CapsuleComponent | same |
| `World` | `CMC+0xC0` | non-null | non-null |
| `CharacterOwner` | `CMC+0x198` | == pawn | == pawn |
| `MovementMode` | `CMC+0x231` | **3** (MOVE_Falling) | **3** |
| `Mobility` | `UpdatedComponent+0x1BB` | **2** (Movable) | **2** |
| `WeldParent` | `UpdatedComponent+0x5F0` | **NULL** | — |
| `bSimulatePhysics` | `BodyInstance(+0x3F0)+0x10` mask `0x01` | **0** | — |
| `Role` / `RemoteRole` | pawn `+0x160` / `+0x72` | **3** / 1 | 3 / 1 |
| `Controller` | pawn `+0x400` | non-null | non-null |
| `RF_Garbage` | pawn `ObjectFlags+0x0C` bit 30 | 0 | 0 |
| **latch** | `CMC+0x16C8` | **0** | **0** (and 0 on all 37) |
| `Velocity` | `CMC+0xE8` | (0,0,0) | (0,0,0) |
| tick state | `PrimaryComponentTick` @ `+0x40` | `bCanEverTick` 1, TickState Enabled, `bRegistered` **False**, `TaskPointer` 0, `LastTickGameTimeSeconds` **-1.0** | identical |

⚠ **`bRegistered False` on a component that is demonstrably being driven is unexplained** and is a
legitimate thing to think about, but it is **not** this session's task.

**Key addresses** (all RVAs):

    engine  PerformMovement            0x035E9EC0   its StartNewPhysics call 0x035EB13A   ret 0x035EB1CA
            gates 3/4/5 bail to        0x035EB7CF
            HasValidData               0x035E64C0   (vtable disp 0x6B8)
            ShouldSkipUpdate           0x0364BA80   (disp 0x4E0)
            ControlledCharacterMove    0x035DCD10   writes Accel 0x035DCD6B, Analog 0x035DCD8F,
                                                    calls PerformMovement 0x035DCDAC (guarded cmp cl,3)
            StartNewPhysics            0x03600990   MIN_TICK_TIME comiss 0x036009A8 vs 1e-6f @0x076B8E74
                                                    own IsSimulatingPhysics gate 0x036009D3/E4/EC,
                                                    logs .rdata 0x07FC0670 (CharacterMovementComponent.cpp:3477)
    Loki    TickComponent              0x055C2B90   (disp 0x3D0)
            PerformMovement            0x055B8370   (disp 0xAA8)  Super call 0x055B85C1
            StartNewPhysics            0x055C2430   (disp 0x720)  latch write 0x055C2469
            ControlledCharacterMove    0x055A7680   (disp 0x890)
            ConstrainInputAcceleration 0x055A75B0   (disp 0xA38)  IsStunned predicate 0x055B2930
            PhysFalling                0x055B89F0   (disp 0x830)
            GetMaxAcceleration         0x055AC910   GetMaxSpeed 0x055ACB90
    primitive  IsSimulatingPhysics     via disp 0x4C0    GetBodyInstance via disp 0x810 (= 0x03C91C60)

`ULokiCharacterMovementComponent` vtable `.rdata 0x088F8570`, **413 slots, 64 overridden**.

---

## 4. ⚠ TRAPS — every one of these has fired in this project, most of them on me

1. **A linear disassembly sweep is not a CFG.** Over engine `PerformMovement` it decodes **1,074**
   instructions where recursive descent finds **1,461**. It got the exit set right by luck.
2. **`target > call` is blind to backward bails.** This is the whole premise of A1.
3. **A disp32 byte-pattern scan is a FLOOR, not a census** — and it desyncs. Mine emitted
   `adc byte ptr [rbp+0x12b0]` and missed two instructions I already knew existed.
4. **A rel32 caller scan over a 55 %-decrypted `.text` is always a floor.** "Exactly one caller" is
   never a count.
5. **A `set()` collapses `-0.0` and `0.0`.** My probe printed `distinct Acceleration values: 1` and
   hid the entire flight-3 finding; the *printed samples* carried it. **Record raw, derive after.**
6. **A verdict line can lie.** Two S138/S139 probes printed confident verdicts contradicted by their
   own samples. Compute verdicts from observed data and print the data.
7. **Do not cross a function boundary with an inference.** I read "`+0x12B0` advances" (a fact about
   the Loki *wrapper*) as "the engine impl runs" and had to retract it. A3 exists because of this.
8. **`.rdata` class literals are UHT prefix-stripped** — the bytes say `LokiHeroCharacter`, not
   `ALokiHeroCharacter`. Searching the prefixed form gives a false ABSENT.
9. **Recompute every RVA with a machine.** Hand arithmetic has produced a false finding here before.
10. **Never read a mutable global out of a MERGED image's `.data`** without saying so — `merged13`
    splices `.data` from differently-timed snapshots.

---

## 5. DELIVERABLES

Write to `docs/s140-tier1-cfg.md`:

1. **A1** — the sound exit set, diffed against my six, with each exit's tested field and whether it
   is already measured. **State plainly whether the "six" survives.**
2. **A2** — the ranked progress-ladder table, with per-field discriminating power.
3. **A3** — the `+0x12B0` writer set, and what an advancing value does/does not prove.
4. **A short "what this means for the contradiction" section**: given A1, is the contradiction real,
   or was there a seventh exit all along? If it survives, name the two or three best remaining
   explanations and what would test each.
5. **Any corrections to `CLAUDE.md` or `docs/s139-*.md`**, quoting the stale text and giving the
   replacement. This project loses corrections when digests are not updated — propagate them.

**If a task turns out to be unanswerable offline, say so and say what live read would answer it.**
An honest "not established, here are the survivors" is the correct output when that is the truth —
S139's synthesis did exactly that and it was the most useful artifact of the session.

## 6. SCOPE — do not overstate

⛔ **This is not a bot.** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
(`0x556DE53 → 0xF7EB60`) are stripped folds; the bot has no hero class and no team. The GAS fix that
closed the input wall is a **CDO poke — process-wide, not undone, a diagnosis and not a shipping
fix.** Nothing in this session changes any of that.
