# S140 TIER 2 — ADJUDICATION

**Role:** adjudicator over 6 lanes + 6 adversarial verifiers.
**Method:** every disputed load-bearing claim below was **re-derived by me from
`dumps/merged13.dump.exe`** with a from-scratch PE reader + capstone recursive-descent CFG
(`scratchpad/s140t2/ADJ/adj.py`), importing nothing from any lane. Where I did not re-derive
something myself it is labelled **[inherited]** and graded accordingly.

**My controls (all PASS):** PE flat `True`; `ImageBase 0x7FF608F40000`; DARK control
`ULokiRespawnComponent::Respawn 0x5A6AC40` page = **0/4096 non-zero**; every function touched below
sits on a page with 3454–3883/4096 non-zero bytes; **18/18 vtable displacements** read two-sided
across `ULokiCMC .rdata 0x088F8570` and engine `UCMC .rdata 0x07FBED58` (6 identical = passing
negative controls, 12 differing = passing positives); **4/4 unique-pointer** censuses
(`0x055C2430→0x088F8C90`, `0x0530ABF0→0x088F8FC0`, `0x055B8370→0x088F9018`,
`0x055B89F0→0x088F8DA0`) — exactly one aligned qword each, at vtable base + expected disp.

**FLOOR CAVEAT, stated once and in force everywhere:** `.text` in `merged13` is
**16,800 / 30,281 pages = 55.48 %** decrypted. Every census below is a **FLOOR**, never a count.
Writes are classified from `operands[0].type == MEM`, never from `regs_access`.

---

## 1. HEADLINE

> ★★★★★ **THE SHIPPED EXPERIMENT — "poke `Velocity`, wait ≥3 frames, read `+0x16B0`"
> (Tier 1 §5, `CLAUDE.md`'s S141 line) — HAS A FALSE-NEGATIVE MODE IN EXACTLY THE WORLD WHERE
> THE ANSWER IS YES. Two independent mechanisms, both [M], both measured by me.**

**(a) The payload is REFRESHED EVERY FRAME. "Durable against the CLEAR" is not "durable".**
[M, mine] Engine `PerformMovement 0x035E9EC0` contains **exactly ONE** `call qword [rax+0x720]`
(at `0x035EB13A`) and **exactly ONE** `call qword [rax+0xa50]` (at `0x035EB569`) over its full
1461-instruction CFG (148 calls, 0 indirect jumps, 0 decode failures). In
`ULokiCMC::StartNewPhysics 0x055C2430` the payload write at `0x055C244F` is **unconditional on the
`Iterations == 0` path** — both arms of the `je 0x55c2448` converge at `0x055C2448`, and the write
is straight-line to the flag set at `0x055C2469` with no branch between.
⇒ `CMC+0x16B0` always holds **the most recent frame's pre-step Velocity**, never the first one taken.

**(b) Engine `PhysFalling` ZEROES `Velocity`, and every physically-inert sentinel satisfies its
threshold.** [M, mine] `0x035ED98E comisd xmm1, [rip→.rdata 0x077F5180]` where that constant is
**`0.0009999999747378752` = (double)(float)1e-3**; `0x035ED996 ja` skips, so the fall-through
`0x035ED998 xorps xmm0,xmm0 … 0x035ED9BB movups [rsi],xmm0 / 0x035ED9C3 movsd [rsi+0x10],xmm1`
**writes Velocity**. `rsi = &Velocity` is [M]: the **only** defining `lea rsi,[rdi+0xe8]` in the body
is `0x035EC9AC` (the other `rsi` def, `0x035EE519`, is the epilogue restore), and node-removal shows
it **DOMINATES both writes** (`reachable avoiding the lea = False` for both).
⇒ a sentinel of `2^-10` gives SizeSq `9.54e-07`, **1048× below** the gate ⇒ **zeroed**. A smaller,
"more inert" sentinel is zeroed *harder*. **The sentinel erases itself precisely when the physics
step runs**, and the payload then re-snapshots the zero on the next frame.

**⇒ THE FIX, and the flight must adopt it: POISON THE PAYLOAD, and add a second,
DISPATCH-INDEPENDENT receipt.**

> ★★★★★ **NEW, from me, and it is the biggest single addition of this pass:
> `0x035EB130 mov dword [rbx+0x3dc], r15d` DOMINATES the `call [rax+0x720]`.**
> [M] Predecessor census over my own CFG: `0x035EB126 / 129 / 12C / 130 / 137 / 13A` each have
> **exactly ONE in-edge**, the linear fallthrough. Node removal: the call is
> **not reachable with `0x035EB130` banned** (`False`), while `0x035EB130` **is** reachable with the
> call banned (`True`). So the store is one instruction upstream of, and strictly dominates, the
> dispatch.
> ⇒ **Poke `CMC+0x3DC` with a distinctive value. If it is reset, engine `PerformMovement` reached
> the basic block that contains the `StartNewPhysics` call — proven WITHOUT relying on the vtable
> dispatch, the object's vptr, or anything inside `ULokiCMC`.** This is the one control that
> separates "the six exits bailed" from "the call happened and did not write our payload".
> **Safe:** `+0x3DC` (`NumJumpApexAttempts`) is read in exactly one reachable place —
> `0x035ECE5D mov ebx,[rdi+0x3dc] / 0x035ECE63 cmp ebx,[rdi+0x3e8] / jge` inside engine
> `PhysFalling`, written back at `0x035ECFFC` — which is **downstream of `StartNewPhysics`**, so the
> poked value is live only in the world where nothing runs. Use a **large positive** poke
> (`0x7FFFFFF0`) so that if it *does* survive into `PhysFalling` the `jge` takes the *restrictive*
> arm. A negative poke (`0xDEADBEEF` = −559038737) takes the permissive arm — do not use it.

---

## 2. THE SENTINEL MECHANISM, SETTLED

### 2.1 Is `+0x16B0` a valid receipt for "`ULokiCMC::StartNewPhysics` ran"?

**YES — but only under a POISON design, and only for a narrower proposition than Tier 1 states.**

Full transcription, re-read by me byte for byte (`0x055C2430..0x055C249B`):

```
0x055C2430 0f28d1             movaps xmm2, xmm1                       ; save DeltaTime
0x055C2433 4585c0             test   r8d, r8d                         ; Iterations
0x055C2436 753d               jne    0x55c2475
0x055C2438 443881c8160000     cmp    byte [rcx+0x16c8], r8b
0x055C243F 7407               je     0x55c2448                        ; <- both arms converge
0x055C2441 448881c8160000     mov    byte [rcx+0x16c8], r8b           ; conditional CLEAR
0x055C2448 0f1081e8000000     movups xmm0, [rcx+0xe8]                 ; Velocity.XY
0x055C244F 0f1181b0160000     movups [rcx+0x16b0], xmm0               ; PAYLOAD write  #1
0x055C2456 f20f1089f8000000   movsd  xmm1, [rcx+0xf8]                 ; Velocity.Z
0x055C245E f20f1189c0160000   movsd  [rcx+0x16c0], xmm1               ; PAYLOAD write  #2
0x055C2466 0f28ca             movaps xmm1, xmm2                       ; restore DeltaTime
0x055C2469 c681c816000001     mov    byte [rcx+0x16c8], 1             ; flag SET
0x055C2470 e91be503fe         jmp    0x3600990                        ; tail -> engine SNP
0x055C2475 7e1c               jle    0x55c2493                        ; ZF=0 from the test => jle <=> r8d<0
0x055C2477 80b93102000003     cmp    byte [rcx+0x231], 3              ; MOVE_Falling
0x055C247E 7513               jne    0x55c2493
0x055C2480 0f28c2             movaps xmm0, xmm2
0x055C2483 f30f5881b0120000   addss  xmm0, [rcx+0x12b0]               ; SECOND +0x12B0 accumulator
0x055C248B f30f1181b0120000   movss  [rcx+0x12b0], xmm0
0x055C2493 0f28ca             movaps xmm1, xmm2
0x055C2496 e9f5e403fe         jmp    0x3600990
```

**Adjudications:**
- **L1's two alleged Tier 1 listing defects are BOTH REAL** [M, mine]. `0x055C2466 movaps xmm1,xmm2`
  is absent from Tier 1 §4.2, and the `Iterations != 0` arm carries a **second `+0x12B0`
  accumulator** (`0x055C2483/8B`) that no repo document records. V1 confirmed both; I confirm both.
  ⚠ Consequence for `+0x12B0`: it is written by **two** sites, not one. As a witness it still says
  "`ULokiCMC::StartNewPhysics` or `ULokiCMC::PerformMovement` ran with dt>0"; that is enough for its
  use as a liveness witness (§5) and not enough to name a function.
- **L1's `jle` label ("Iterations < 0") is CORRECT** — `jne` does not touch flags, so ZF=0 carries
  from `test r8d,r8d` and `jle ⟺ SF≠OF ⟺ r8d < 0`.
- **The payload write DOMINATES the flag set** [M] — straight line, no branch between `0x055C244F`
  and `0x055C2469`.

**What a payload hit proves, exactly:** `ULokiCMC::StartNewPhysics` was **ENTERED with
`Iterations == 0`**. **It does NOT prove the engine physics step ran.** All four engine gates sit
**downstream** of the payload write (`0x036009A8 comiss dt, 9.999999974752427e-07` /
`0x036009B5 cmp r8d,[rcx+0x3e4] / jge` / `0x036009C5 call [rax+0x6b8]` third `HasValidData` /
`0x036009E4 call [UpdatedComponent_vt+0x4c0]` `IsSimulatingPhysics`), plus the `cmp esi,7 / ja`
mode bound. **Tier 1 §5 row 1 says "StartNewPhysics ran" without naming which function — that is the
same cross-function over-read S139 already retracted once for `+0x12B0`. Scope it.**

### 2.2 THE COMPLETE WRITER SET (FLOOR: 55.48 %)

| # | site | object | what it writes | grade |
|---|---|---|---|---|
| W1 | `0x055C244F movups [rcx+0x16b0],xmm0` | **ULokiCMC** | payload X,Y | **[M, mine]** |
| W2 | `0x055C245E movsd [rcx+0x16c0],xmm1` | **ULokiCMC** | payload Z | **[M, mine]** |
| F1 | `0x055C2441 mov byte [rcx+0x16c8],r8b` | ULokiCMC | flag CLEAR (conditional) | **[M, mine]** |
| F2 | `0x055C2469 mov byte [rcx+0x16c8],1` | ULokiCMC | flag SET | **[M, mine]** |
| F3 | `0x0530ABF9 mov byte [rcx+0x16c8],0` | ULokiCMC (vt disp `0xA50`) | flag CLEAR per frame | **[M, mine]** |
| F4 | ctor `0x0559FDF4` | ULokiCMC | flag init | [inherited L3/V4] |
| **X1** | `0x0559EA2F` / `0x0559EA3F` | **ALokiCharacter** | *its own* `+0x16B0` field | [inherited, L1+V1 agree; ctor-vtable adjudicated] |
| **X2** | `0x055B860B mov byte [r15+0x16c8],0` | **ALokiCharacter** | *its own* `+0x16C8` byte | **[M, mine]** |
| **X3** | `0x055A6BCB movups [rsi+0x16c8],xmm0` (16 B) | ALokiCharacter | — | [inherited V2] |

**W1 and W2 are the ONLY two CMC-side payload writers** — L1, V1, L2 and V2 all agree, by four
independently written censuses. Grade: **[M] for the two positives; [I, strong] for the
exclusion of every other writer** (the census is blind to the dark 44.52 %, to computed-pointer
forms, to indexed addressing, and to register-sized `memcpy`). **Tier 1 graded the whole thing [M];
that is one notch too high.** The `ARM H2` fast-burst arm already in the tree is the right hedge.

### 2.3 ⚠⚠ THE ADDRESSING COLLISION IS REAL AND IS THE #1 HAZARD

**[M, mine]** `ALokiCharacter` carries **live, per-frame-written fields at the SAME displacements**
`+0x16B0..+0x16C7` and `+0x16C8`. I confirmed X2 directly: inside `ULokiCMC::PerformMovement`,
`0x055B8381 mov r15,[rcx+0x198]` (CharacterOwner) → `0x055B839D call 0x54f8c40` (cast) →
`0x055B860B mov byte [r15+0x16c8],0`.

**And there is an UNCONDITIONAL 24-byte READER of that character field**, `0x055A9A30`:
```
0x055A9A30 movups xmm0,[rcx+0x16b0] / mov rax,rdx / movsd xmm1,[rcx+0x16c0]
           movups [rdx],xmm0 / movsd [rdx+0x10],xmm1 / ret        ; NO +0x16C8 test
```
with **exactly 3 rel32 callers** (`0x5504032`, `0x5508351`, `0x550CA3B`), **and I settled its class
myself**: all three cast `rcx` through **`0x054F8C40`** first — the *same* helper
`ULokiCMC::PerformMovement` applies to `CharacterOwner` at `0x055B839D`. ⇒ **`0x055A9A30` is an
`ALokiCharacter` getter of `ALokiCharacter`'s own field, not a CMC method.**

⇒ **Two consequences.** (i) The CMC payload poke stays **inert** — no CMC-side consumer reads it
without the flag, and the flag is 0 between frames. (ii) **A probe or arm that resolves a PAWN where
it means a COMPONENT reads a plausible, changing, wrong value AND a 24-byte poke there corrupts real
character state.** The per-object poison (§4) is the control that catches this; it is mandatory.

---

## 3. THE VELOCITY HAZARD, SETTLED

### 3.1 Can anything overwrite or zero `CMC+0xE8` between our write and the snapshot? **YES.**

| writer | condition | grade |
|---|---|---|
| engine `PhysFalling 0x035ED9BB/C3` via `rsi=&Velocity` | gravity-space `SizeSq2D <= 1e-3` | **[M, mine]**, dominance proven |
| engine `CalcVelocity` — 5 ZeroVector store-pairs, incl. `0x035D6520/27` | the input-accel clamp `MaxInputSpeed < 1e-4` | [inherited L5/V5; `preds(0x035D6511) = {0x035D650F}` alone, V5-verified] |
| `ULokiCMC::PhysFalling 0x055B8FBE` | gated on `CMC+0x1678 >= 0`, reset to `-1.0f` at `0x055B9063` | [inherited L5], **[I]** inert |

**⇒ The Velocity sentinel is self-erasing in exactly the "YES" world.** It cannot be the primary
receipt. That is the §1 headline.

### 3.2 Is `0.0009765625` physically inert? **NO — it trips at least one branch.**

**[M, mine]** In `ULokiCMC::PerformMovement`:
```
0x055B873B cmp byte [rsi+0x1308], 0 / 0x055B8769 jne 0x55b8865      ; block gate, byte NEVER READ [I]
0x055B877D..0x055B879B   xmm1 := Velocity.Y^2 + Velocity.X^2        ; SizeSq2D
0x055B879F..0x055B87AB   ucomisd xmm1, 1.0 (rdata 0x0768C4C8) / jne
0x055B87E4 comisd xmm1, [rip→0x076A5918] = 9.99999993922529e-09 / jae 0x55b880f  ; NORMALISE
   else -> 0x055B87EE loads ZeroVector (.data 0x099C86A0)
```
`2^-10` ⇒ SizeSq2D `= 9.5367431640625e-07` = **95.4× the 1e-8 tolerance** ⇒ the branch **flips** from
the ZeroVector arm to the normalise arm, and the result is stored (L2: `LastNonZeroDirection2D
@ CMC+0x12F0`). ⚠ **Whether the write fires is [I], not [M]** — the whole block is behind the unread
byte `[CMC+0x1308] == 0`. L2's headline stated it as fact; its own §3.3 grades it [I]. **Use the [I].**

**Inertness threshold [M]:** SizeSq2D < 1e-8 ⟺ `|V_xy| < 1e-4`.

### 3.3 FINAL SENTINEL RECOMMENDATION

| field | BOT | PLAYER | why |
|---|---|---|---|
| **payload `+0x16B0/B8/C0`** (PRIMARY) | `(-9876.5, -8765.25, -7654.125)` | `(-1234.5, -2345.25, -3456.125)` | already shipped in `tutorial_launch.cpp:15730-31`. Exactly representable, wildly implausible as a velocity, mutually distinct ⇒ two-sided addressing control. **KEEP AS IS.** |
| **`+0x3DC`** (NEW, PRIMARY #2) | `0x7FFFFFF0` | `0x7FFFFFF0` | dominates the `0x720` call; dispatch-independent; restrictive `jge` arm if it survives |
| **`Velocity +0xE8`** (SECONDARY) | `(9.5367431640625e-07, 0, 0)` = **`2^-20`** | **DO NOT WRITE** | SizeSq2D `9.09e-13`, **11,000× below** the 1e-8 gate ⇒ inert on the one gate we can name. `2^-10` is **not**. |

**⚠ CHANGE REQUIRED: `KSHSENTX` currently defaults to `0.0009765625`
(`tutorial_launch.cpp:15738`). Set it to `9.5367431640625e-07`.** (`2^-31` also works; `2^-20` keeps
the value visible in a `%.6g` print without denormal-adjacent surprises. Either is fine; `2^-10` is
not.)

**⚠ Irreducible residue, stated honestly:** L2 identifies **5 CMC-based exact
`ucomisd 0, [CMC+0xE8/F0/F8]`** sites that flip for **any** non-zero value. No sentinel avoids them.
That is a further reason the Velocity write is SECONDARY and the payload poison is PRIMARY.

### 3.4 ASSESSMENT OF THE TWO-SENTINEL (BOT vs PLAYER) DESIGN — **ADOPT IT, on the PAYLOAD only**

- ✅ **It is the right control and it is the only one that can catch the §2.3 collision.** Distinct
  per-object poisons make "the bot's slot holds the player's poison" a *detectable, named* failure
  rather than a plausible reading.
- ✅ **It doubles the science for free:** it answers "does `StartNewPhysics` run on the PLAYER?",
  which is the population question S139 raised and could not answer.
- ✅ **L6's objection — "do not sentinel the PLAYER while ARM G is armed, it destroys ARM G's only
  specificity control" — is REJECTED for the payload, ACCEPTED for Velocity.** ARM G's specificity
  control is `AttributeSetStorage @+0xF08` / `Acceleration @+0x328` on an untreated player. A payload
  poke touches neither. A **Velocity** poke on the player would contaminate a field ARM G's
  Acceleration story sits next to — so **write Velocity on the BOT only**, which is exactly what the
  shipped code does (`kShPlrVel` defaults to all-zero, `KSHPLRX/KSHPLRY` = 0.0).
- ⚠ **The design is inert for CMC consumers [M]** (§2.3) but **NOT inert if the resolution is wrong**
  — see §7 P2 / R1.

---

## 4. THE OUTCOME TABLE (PRE-REGISTER THIS, VERBATIM)

Three observables per object, read ≥3 frames after the poke:
**P** = payload `+0x16B0..C7`; **V** = `Velocity +0xE8..FF`; **J** = `+0x3DC`.
`own` = this object's poison, `other` = the sibling's poison, `S` = the Velocity sentinel.

**GUARD ROW — evaluate FIRST, in this order. Any hit stops interpretation for that object.**

| # | condition | verdict | grade |
|---|---|---|---|
| G1 | `P == other` | **VOID — the CMC resolution is WRONG.** Nothing else in the run may be read. | [M] |
| G2 | poison readback at arm time failed | **UNINTERPRETABLE, not a null.** | [M] |
| G3 | `vptr != BASE+0x088F8570` | **VOID** — this object is not a `ULokiCMC`; nothing writes `0x16xx`. | [M] |
| G4 | `+0x12B0` frozen on **both** objects across all 5 samples | **VOID — no evidence frames passed.** (see §5) | [M] |

**MAIN TABLE (bot; the J-axis is the new one):**

| # | P | V | J | VERDICT | grade |
|---|---|---|---|---|---|
| **C1** | `own` | `S` | `0x7FFFFFF0` | **`PerformMovement` never reached `0x035EB130`.** It bails at one of the six exits, or the CMC never ticked. `StartNewPhysics` NOT entered. Strongest negative; the next question is *which exit*. | **[M]** |
| **C2** | `own` | `S` | reset | ★★★ **CONTRADICTION-BY-DESIGN, AND THE MOST INFORMATIVE CELL.** The block containing the call ran (J dominates the call) but the payload was untouched. ⇒ the `[rax+0x720]` dispatch did **not** land in `0x055C2430`, or landed with `Iterations != 0`. Re-read the vptr and the slot at `vptr+0x720` **in the same pass**. | **[M]** for the disjunction |
| **C3** | `own` | `≠S` | any | **`StartNewPhysics` NOT entered, AND a non-`StartNewPhysics` writer of `Velocity` exists.** Informative, **not void** — it names a new writer. | **[M]** |
| **C4** | `S` | `S` | reset | ★★★★★ **`ULokiCMC::StartNewPhysics` WAS ENTERED with `Iterations == 0`, and it read OUR Velocity.** Strongest positive: the payload holds a value only `0x055C244F` could have put there. Additionally: nothing consumed `Velocity` ⇒ the engine step bailed at one of its four gates, or `PhysFalling` was not dispatched. | **[M]** |
| **C5** | `S` | `≠S` (e.g. `0`) | reset | ★★★★★ **ENTERED, AND THE STEP CONSUMED VELOCITY WITHIN THE LAST FRAME.** The snapshot predates the consumption. **This is the "everything downstream is live" cell** — and the linear rule in the handoff calls it VOID. | **[M]** |
| **C6** | `0` (exact) | any | reset | **ENTERED** — the poison was overwritten and the snapshot is a zero Velocity. Weaker than C4/C5 (any payload writer produces it), so it is the cell `ARM H2` exists to harden. | **[M] entered / [I, strong] that the writer is W1** |
| **C7** | `0` | any | `0x7FFFFFF0` | ⚠ **GENUINELY AMBIGUOUS — NAME IT.** Payload zeroed while the dominating store never ran. Either an unknown non-`StartNewPhysics` payload writer (the FLOOR biting), or an instrument fault. **Report raw hex; do not adjudicate.** | **AMBIGUOUS** |
| **C8** | anything else | any | any | **UNMODELLED. Report the raw 24 bytes; do not interpret.** | — |

**PLAYER rows:** identical, minus every `S` cell (no Velocity is written there). So the player yields
exactly `{C1-analogue, C6, C7}` — which is sufficient, because on the player the question is only
*"does its `StartNewPhysics` run?"*.

**The genuinely ambiguous cells are C7 and — one notch down — C6.** Everything else is decidable.

**⚠ Adjudication of the L1-vs-V1 dispute on Tier 1 §5:** L1 called the third clause "BACKWARDS";
V1 downgraded that to "the three clauses are mutually inconsistent and Tier 1 does not state
precedence". **V1 is right.** Tier 1's clauses read as an ordered list whose unconditional clause 1
fires first, so under first-match-wins a C5-shaped positive survives. Grade the criticism **[I]**,
not [M] — but **the fix is required either way**, because the table above shows Tier 1's clause 3
has no correct reading at all: *`+0xE8` changing is the signature of success, not of instrument
failure.* The instrument-failure test is the **immediate readback at poke time**, not a later
comparison.

---

## 5. THE ARM DESIGN, SETTLED

### **DECISION: WORKER-THREAD SAMPLER. Not a multi-hit state machine. Not a `CreateThread` from a hit.**

**The hit-count evidence, adjudicated from the raw markers (I read them myself):**

| run | `[FS] cfg` | at t+8 s | at t+15 s |
|---|---|---|---|
| bot ladder `fk24-stage-s137f4-1-gft.txt` | `KFUNCSWAP=1 max=0 name='' … swapped=17563` | `hitsGT=1 allThreadCalls=1` **(~0/s)** | `hitsGT=1 called=0 allThreadCalls=207` |
| `fk24-s128-poolspawn-RESULT.txt` | **character-identical cfg**, `swapped=17563` | `hitsGT=588 allThreadCalls=588` **(~73/s)** | `hitsGT=588 called=587 allThreadCalls=588` |

**Adjudication between L6 and its verifier:**
- **L6's §2 is HALF RIGHT, and V6's N1 is the correct support.** `g_hitsGT` is incremented *after*
  the `g_done||g_inHook` early-out, so in a one-shot ladder it **cannot exceed 1** — L6 is right that
  the number is self-inflicted. **But `allThreadCalls` (`g_fsCalls`, incremented on `FsThunk`'s
  first line, before every guard) is UNGATED, and it reads 1 vs 588 on the same config.** So the
  *world* really is quiet during the bot ladder's profile window — L6's conclusion ("one hit is all
  this world delivers" is an artifact) needs the *occupancy* argument, not the gating one.
  **Cite `allThreadCalls`, never `hitsGT`.** [M, mine, from the marker files]
- **Cause: our own census occupies the game thread.** `[BS] ---- A0` precedes `[FS] arm:` in 3/3 bot
  markers and A0 runs 3609–4391 ms, covering the entire 4000 ms profile window. `called=0` at t+15 s
  means `DoBotSpawn` had not yet returned, so the 207 are our own nested dispatches, not free frames.
  [M for the counts; **[I, strong]** for the attribution of the 207 — no per-call attribution exists.]
- ⇒ **A multi-hit state machine is only viable after the three ~4 s `BsScanWorld` censuses move off
  the game thread. That is a bigger change than this flight needs. REJECT for S141.**
- ⇒ **The worker sampler between `FsDisarm()` and `BsFinalReport()` is correct and is already
  implemented** (`tutorial_launch.cpp:17894-17896`, `ShSampleLoop`). The game thread is provably
  released there, `FsThunk` forwards unconditionally so frames flow, and `[BS] done` stays last.
- ✅ **L6's §3 thread-safety table stays LIVE** because the sampler runs on the Worker:
  **`FaultStr()`/`DP_FAULT` must NOT be used inside it** (`static char b[160]` at
  `tutorial_launch.cpp:1005` + a process-global fault record written by any faulting thread).
  The shipped code already avoids it and says why — **keep that.**

### EXACT ORDERING

```
GAME THREAD (inside the single OnPI hit; frames are stopped, which is fine -- all writes, no motion reads):
  1. resolve BOT pawn -> CMC        (BY NAME: the CharacterMovement UPROPERTY, not a hardcoded offset)
  2. resolve PLAYER pawn -> CMC     (same)
  3. GATE: for each, vptr == BASE+0x088F8570 ; else REFUSE that side and say why
  4. GATE: [cmc+0x198] (CharacterOwner) == the pawn ; else REFUSE that side
  5. RECORD RAW: payload 24 B, Velocity 24 B, +0x3DC, +0x16C8, +0x12B0, +0xC0, +0xB8, +0x28,
                 +0x3E0, +0x3E4, +0x3E8, +0x3D0, +0x290, +0x231, +0x1308, +0x1678
  6. WRITE  BOT payload := kShBotPoison        -> readback, record
     WRITE  PLR payload := kShPlrPoison        -> readback, record
     WRITE  BOT +0x3DC  := 0x7FFFFFF0          -> readback, record
     WRITE  PLR +0x3DC  := 0x7FFFFFF0          -> readback, record
     WRITE  BOT Velocity := kShSentinel(2^-20) -> readback, record      [BOT ONLY]
  7. record t0 of +0x12B0 on BOTH
WORKER (after FsDisarm, game thread released):
  8. sample at +250 / 750 / 2000 / 5000 / 10000 ms: RAW payload, RAW Velocity, +0x3DC, +0x12B0, loc
  9. VERDICT: guards G1..G4 first, then the C1..C8 table
 10. RESTORE: BOT Velocity := (0,0,0)   [payload and +0x3DC are scratch; leave them, they self-heal]
```

### REFUSAL CONDITIONS (each prints WHY and aborts that side; never silently proceeds)

| R | condition | action |
|---|---|---|
| R1 | `vptr != BASE+0x088F8570` | **REFUSE — do not write.** Writing 24 B at `+0x16B0` of an `ALokiCharacter` corrupts a live field (§2.3). |
| R2 | `[cmc+0x198] != pawn` | REFUSE that side |
| R3 | any poison readback ≠ what we wrote | REFUSE that side; report **UNINTERPRETABLE**, not a null |
| R4 | `+0x3DC` readback ≠ `0x7FFFFFF0` | drop the J-axis for that side; the P/V axes still stand |
| R5 | `+0x12B0` frozen on **both** objects across **all 5** samples | **RUN VOID** — no evidence frames passed |
| R6 | a sample faults | record it, keep earlier samples, mark later ones untrusted (already implemented) |
| R7 | `g_shArmed == 0` | sampler prints SKIPPED (already implemented) |

**⚠ On R5 — the frame-witness grade, adjudicating L6 vs V6.** V6 is right: `+0x12B0` is **not a
frame clock** and `delta == 0` has ≥3 causes (no frames / HitStop zeroed dt / the component stopped
ticking). It is nevertheless a **sound one-sided witness**: `delta > 0` ⇒ `ULokiCMC::PerformMovement`
ran with dt>0 ⇒ frames passed **[M]**. Use it only in that direction: **advance ⇒ frames passed;
frozen ⇒ VOID, never "did not run".** It is **not circular here** — both `+0x12B0` writers are
upstream of the `0x720` dispatch (`0x055B840C` in Loki `PerformMovement`; `0x055C2483` on the
`Iterations != 0` arm, which the outer call never takes).

---

## 6. THE THREE FREE READS

| # | offset | field | grade | CONTROL | **DOES IT SETTLE WHAT IT IS FOR?** |
|---|---|---|---|---|---|
| **F1** | `CMC+0xC0` | `UActorComponent::WorldPrivate` | **[M]** offset; **[M]** the code path | two-sided: read on BOT and PLAYER; a PLAYER null would itself be a red flag | ⚠⚠ **ONE-SIDED ONLY. Non-null ⇒ exit 2 PASSES [M]. NULL settles NOTHING.** [M, mine] `0x035E9EEE mov r13,[rcx+0xc0]` / `test` / `jne 0x35e9f11` / **`0x035E9F05 e8 call 0x035AFC40`** — a **DIRECT, non-virtual** fallback (`GetWorld_Uncached`), which reads `+0xB8` (Owner) and `+0x28` (Outer) and **never re-reads `+0xC0`**. Exit 2 is `0x035E9F25 test r13,r13 / 0x035E9F28 je 0x35eb1a7` on the *result*. ⇒ **on NULL you must also read `+0xB8` and `+0x28`.** |
| **F2** | `CMC+0x3E4` | `MaxSimulationIterations` (Int32) | **[M]** offset (UHT rec `.rdata 0x07FB0840`, [inherited L3/V4, agreed twice]); **[M]** the gate | `+0x3E0` should read `0.05f` and `+0x3E8` should read `2` — a 3-field consistency control from one base ctor | ✅ **YES, for the outer call.** [M, mine] `0x036009B5 cmp r8d,[rcx+0x3e4] / 0x036009BC jge 0x3600be6` with `r8d == 0` ⇒ bails **iff `+0x3E4 <= 0`**. Expect `8`. A `0` here would be a complete, single-value explanation. |
| **F3** | `CMC+0x3D0` | `AnalogInputModifier` (float) | **[M]** offset (UHT `0x07FB07D0`, [inherited]); **[M]** the write | the **untreated PLAYER** is the within-run control | ✅ **YES — and it is the best pre-registerable prediction in this pass** (§8 PR1). [M, mine] `0x035DCD6B movups [rsi+0x328],xmm0` (Acceleration) → `0x035DCD82 call [rax+0x660]` → `0x035DCD8F movss [rsi+0x3d0],xmm0`, **straight line, no branch**. |

**⚠ F1 is the one that does NOT settle its target in one direction, and the shipped probe currently
mis-states it — see §7 P3.** F2 and F3 settle theirs.

**Bonus free reads, take them all — they cost nothing:** `+0x3E0`, `+0x3E8`, `+0x290`
(`MinAnalogWalkSpeed`), `+0x231` (`MovementMode`), `+0x1BB` on `UpdatedComponent` (`Mobility`),
`+0x160` on `CharacterOwner` (`Role`), `+0x1678` (Loki `PhysFalling`'s speed cap, expect `-1.0f`),
`+0x1308` (the unread gate byte behind §3.2 — **nobody has ever read it**), and `vptr+0x720` (the C2
disambiguator).

**The six exits of engine `PerformMovement`, re-measured by me** (`|R| = 1075`, 2 backward edges,
**neither in R**, 1 `ret` — reproducing Tier 1 exactly):

| exit | site | condition | status |
|---|---|---|---|
| 1 | `0x035E9F1F je` | `[CMC_vt+0x6B8]() HasValidData` FALSE | measured passing |
| **2** | `0x035E9F28 je` | `WorldPrivate` **or** `GetWorld_Uncached()` NULL | **F1, one-sided** |
| 3 | `0x035E9F97 je` | `MovementMode == 0` (`cmp byte [rbx+0x231], r15b`, `r15b = 0`) | measured `3` ⇒ passes |
| 4 | `0x035E9FA4 jne` | `UpdatedComponent->Mobility != 2` (`cmp byte [rcx+0x1bb], 2`) | measured `2` ⇒ passes |
| 5 | `0x035E9FBD jne` | `[UpdatedComponent_vt+0x4C0]() IsSimulatingPhysics` TRUE | measured `bSimulatePhysics=0` ⇒ passes |
| 6 | `0x035EA25D je` | a redundant 2nd `HasValidData`; **does NOT dominate** | — |

---

## 7. PROBE CHANGES (`tools/re/cmc_earlyout_readout.py`, currently 538 lines)

| # | line | defect | fix | severity |
|---|---|---|---|---|
| **P1** | 425 | `if not lp(plr): print("… RUN IS VOID"); return` — **discards the entire BOT sentinel result** when the player is not found | print the warning, set `B = {"void": …}`, **continue** | ⛔ **HIGH — can destroy the flight** |
| **P2** | 381-382 vs 458-484 | `S140.vptr is ULokiCMC` is **computed and printed after** the payload verdict; **it gates nothing** | move the vptr check **above** the recogniser; a mismatch prints `*** VOID ***` **instead of** a verdict | ⛔ **HIGH** |
| **P3** | 489-492 | `"*** NULL -- EXIT 2 WOULD BAIL ***"` — **unsound**, per §6 F1 | on NULL print `UNDECIDED -- read OwnerPrivate@0xB8 and OuterPrivate@0x28`; **add both reads** | ⛔ **HIGH — emits a false claim** |
| **P4** | 515-522 | the `--watch` `READ IT AS` table still keys on `latch 1` / `dt FROZEN`; **all three cells unreachable** (Tier 1 §4) | replace with `dt ADVANCING ⇒ frames passed [M]` / `dt FROZEN ⇒ UNINTERPRETABLE (≥3 causes), the window is VOID` | HIGH |
| **P5** | 303-311 | `CTRL.tickTarget==cmc` computed, printed as a row, **gates nothing** (only `CharacterOwner==pawn` gates) | add it to the gate, or delete it — a control that cannot fail is not a control | MED |
| **P6** | 263-280 | `find_actors` is **last-match-wins**, silent, no count, no break | print every candidate + count; add `--cmc <hex>` / `--pawn <hex>` pinning | MED |
| **P7** | 275 | bot predicate is `LokiBotController` only ⇒ a plain-`AIController` bot reads VOID (S136's `BsClassify` defect) | accept `BotController` **or** `AIController` | MED |
| **P8** | 408-413 | `fmt` prints vectors `%.3f` — hides a signed zero and renders `2^-20` as `0.000` | vectors: print RAW hex **and** `%+.17g` per component | MED |
| **P9** | — | **no liveness check anywhere**; a dead-but-handle-openable PID, a wrong BASE and a decode defect all print the same string | copy `tools/re/item_watch.py:172-175` (`GetExitCodeProcess`, `STILL_ACTIVE == 259`); add an MZ canary at BASE; name **FK-32** on exit code `0x0000DEAD` | ⛔ **HIGH** |
| **P10** | — | no `+0x3DC` poke-receipt column | add `S140.JumpApex@0x3DC` to the read set and to the verdict as the **J** axis | HIGH (new) |
| **P11** | `chain()` | per-object, unmemoised ⇒ ~10⁷ RPM syscalls | `lru_cache` on `chain(cls)`; resolve pointers **before** the poke | MED |
| **P12** | `--watch` | uses `-1.00` as the unreadable sentinel and ignores `void` | print `UNREADABLE`, never a number | LOW |
| **P13** | `movementmode_readout.py:52-53` | carries **stock** `EMovementMode`; wrong at ≥6 for this build (`MOVE_Dashing=6`, `MOVE_Custom=7`) | port the corrected table from `cmc_earlyout_readout.py` | MED |

**Shim changes (`tools/sigbypass-mod/tutorial_launch.cpp`):**
- **S1** `:15738` `#define KSHSENTX 0.0009765625` → **`9.5367431640625e-07`** (§3.3). ⛔ REQUIRED.
- **S2** add the `+0x3DC := 0x7FFFFFF0` poke + readback beside the poison, and the `+0x3DC` read to
  `ShDump`. HIGH (new).
- **S3** add `+0x12B0` to every `ShDump` line and implement R5 (both-frozen ⇒ VOID). ⛔ REQUIRED.
- **S4** ARM H is correctly behind `#if (KBSPSARMS & 0x200)` with **no `#else`** — so no skip literal
  and no new knob. **L6's §7d "the ONLY safe pattern is a NEW `KBSPSH` knob" is REFUTED**, and its
  "add a `gasattr-sentinel` variant" is moot (it already exists, `build.ps1:642`). **Do not add
  `KBSPSH`.**

**Regression gates — re-record before the flight.** [inherited V6, and it was **confirmed by
prediction**] `driverecompute` now rebuilds to `4465ebc4d7168c03`, **`.text`-identical to
`gasattr-ctrl`** ⇒ CLAUDE.md's `driverecompute a2a952babfed256b` is **dead**, and that pair is a live
"A/B against a copy of itself" hazard. `lokibot` reads `e123816b65d68e5e`, not the recorded
`3119d75ae2ca1859`. **Re-record or delete; do not fly either as a control.** `botai
5e47c13cf7f0a158` and `gasattr 2fcc2536e21f18e3` are **MEASURED UNCHANGED** after ARM H, with a
passing cached-build control (two new DLLs produced in the same batch).

---

## 8. DOWNSTREAM SEED — RANKED TIER 3 TARGETS

> ⚠⚠ **FIRST, THE ADJUDICATION THAT REORDERS THIS WHOLE LIST: L5's HEADLINE IS REFUTED. V5 IS
> RIGHT, AND I RE-DERIVED IT.**
> L5 claims `CalcVelocity`'s `MaxInputSpeed < 1e-4` clamp (`0x035D64F2 comisd` /
> `0x035D650F jae` → `0x035D6520 movups [rbx+0xe8], ZeroVector`) is "a complete mechanical account
> of S139 flight 4". **It cannot be.** [M, mine]:
> - `ULokiCMC::GetMaxAcceleration 0x055AC910`: `movzx eax,[rcx+0x231]` / `cmp al,1` / `jne 0x55ac97a`
>   → `0x055AC97A cmp al,3 / je 0x55ac982` ⇒ **`MOVE_Falling(3)` DOES take the `+0xC00` path**, at
>   `0x055AC9A0 call qword [rax+0xc00]`, with `0x055AC9AC jne` — **zero ⇒ `0x055AC9AE xorps xmm0,xmm0; ret` = 0.0f.**
> - `ULokiCMC::GetMaxSpeed 0x055ACB90`: for `MovementMode != 7`, `0x055ACBE6 jmp qword [rax+0xc00]`
>   — a **tail-call to the SAME slot on the SAME owner**.
> ⇒ S139 flight 4 **measured `GetMaxAcceleration() == 50000`**, which requires that slot to have
> returned **non-zero**; therefore `GetMaxSpeed()` returned that same non-zero value, and
> `MaxInputSpeed >> 1e-4`. **The clamp did not fire.** L5's own §4.5 P5/P6 predict exactly this and
> the headline was never reconciled — a digest carrying an un-re-derived claim, **inside one document.**

| # | target | address | why | cost |
|---|---|---|---|---|
| **T1** | the `StartNewPhysics` gate set on a live treated bot | `+0x3E4`, `+0x3E0`, `+0xC0`, `+0xB8`, `+0x28` | if §4 lands on C4/C5/C6, these are the only remaining single-value explanations of "entered but no velocity" | free reads, same pass |
| **T2** | `ULokiCMC::PhysFalling 0x055B89F0` + engine `PhysFalling 0x035EC850` | 370 / 1482 ins, both fully lit | the `1e-3` zeroing (§3.1) is **already [M]** and is the leading candidate for "Velocity resets to 0 every frame". **Transcribe the path from the `0x830` dispatch to `0x035ED98E`.** | offline |
| **T3** | `CalcVelocity 0x035D5D20` — the **braking** path, not the clamp | `ApplyVelocityBraking 0x035D4810` (untranscribed) | with the clamp refuted, braking/friction is the next candidate for Velocity → 0 | offline |
| **T4** | `[Owner_vt+0xC00]` → `0x055AC9F0` | `[Char+0xF08] AttributeSetStorage` → `0x055266E0 minss(leaf(+0xF0), leaf(+0x100))`, `0x01F62B10 = movss xmm0,[rcx+0xC]` | the shared GAS gate for **both** `GetMaxSpeed` and `GetMaxAcceleration`; corroborates the ARM-G recipe from a second direction | offline (mostly done) |
| **T5** | `CMC+0x1308` | the unread byte gating §3.2's whole block | never read by anyone; one byte | free read |
| **T6** | `CMC+0x1678` | Loki `PhysFalling`'s speed cap, reset `-1.0f` at `0x055B9063` | never read live | free read |

### ★ PRE-REGISTERABLE PREDICTIONS — write these down BEFORE the flight

| # | prediction | basis | falsifier |
|---|---|---|---|
| **PR1** | **`AnalogInputModifier @CMC+0x3D0` reads ≈ 1.0 (non-zero) on the TREATED BOT and 0.0 on the UNTREATED PLAYER.** | [M, mine] `0x035DCD6B` Accel store → `0x035DCD82 call [rax+0x660]` → `0x035DCD8F` store to `+0x3D0`, **straight line, no branch**; `ComputeAnalogInputModifier` (disp `0x660 = 0x035DB6F0`, **not Loki-overridden**) returns `clamp(|Accel|/GetMaxAcceleration())`, and flight 4 measured both at 50000. | bot reads 0.0 ⇒ either `ControlledCharacterMove` did not run this frame, or `GetMaxAcceleration` regressed. **Either is a major finding.** |
| **PR2** | `MaxSimulationIterations @+0x3E4` reads **8**, `MaxSimulationTimeStep @+0x3E0` reads **0.05**, `+0x3E8` reads **2** — on BOTH objects. | base ctor writes `0x035CF90C/17/21` [inherited L3/V3, agreed] | any of the three off ⇒ someone overrode them and F2 becomes a live explanation |
| **PR3** | `MinAnalogWalkSpeed @+0x290` reads **≥ 1e-4** ⇒ the `max()` in `CalcVelocity` cannot fall below `1e-4` ⇒ **the input clamp is structurally unreachable**, independently of PR1. | [inherited L5] `GetMinAnalogSpeed 0x035E3D20` returns `[rcx+0x290]` for `MovementMode ∈ {1,2,3}` | reads `0.0` ⇒ the clamp is back on the table and PR1 becomes the sole discriminator |
| **PR4** | `WorldPrivate @+0xC0` is **non-null on both** ⇒ exit 2 passes. | [I, strong] — the CMC is registered and ticking | null on either ⇒ **read `+0xB8` and `+0x28` before concluding anything** (§6 F1) |
| **PR5** | `+0x3DC` is **reset** on both objects (J-axis), i.e. the flight lands in C2/C4/C5/C6, not C1. | [I] — the six exits are all measured passing | C1 ⇒ the wall is one of the six exits and F1/F2 name it |

---

## 9. WHAT IS STILL NOT ESTABLISHED OFFLINE — RANKED, EACH WITH THE EXACT LIVE READ

| # | open question | exact live read | why it cannot be closed offline |
|---|---|---|---|
| **1** | **Does `ULokiCMC::StartNewPhysics` run?** | the §4 table | this is the flight |
| **2** | `CMC+0xC0 WorldPrivate` — exit 2's input | `read u64 @ cmc+0xC0` (+ `+0xB8`, `+0x28` on null) | never read live by anyone; Tier 1 §1.6 flags it. **Grade exit 2 [I, strong], not [M].** |
| **3** | `CMC+0x3E4` | `read u32 @ cmc+0x3E4` | a `0` is a complete single-value explanation and has never been excluded |
| **4** | `CMC+0x3D0 AnalogInputModifier` **on a TREATED bot** | `read f32 @ cmc+0x3D0` | CLAUDE.md's recorded `0` is an **UNTREATED flight-1 sample**; PR1 |
| **5** | `CMC+0x1308` — the gate on §3.2's whole block | `read u8 @ cmc+0x1308` | decides whether the Velocity sentinel perturbs `LastNonZeroDirection2D` at all |
| **6** | Is `IsSimulatingPhysics` **still** false on the **BOT**? | `read u8 @ capsule+0x3F0` (+ `WeldParent @capsule+0x5F0`) | S139 measured it on the **hero capsule** in a **different sitting**. **[I, strong], not [M].** |
| **7** | Does the `[rax+0x720]` slot on the live bot CMC actually hold `0x055C2430`? | `read u64 @ vptr+0x720`, compare `BASE+0x055C2430` | this is exactly cell **C2**'s disambiguator and costs one read |
| **8** | Live `LogCharacterMovement` verbosity | `read u8 @ BASE+0x09F85E68` | offline `merged13` `.data` reads `05 00 05 07` from **one seed**; ⚠ its payoff is **conditional** — silence is only a real negative *given* the payload shows SNP was entered (V3's D4) |
| **9** | Whether a non-`StartNewPhysics` writer of `+0x16B0` exists | `ARM H2` fast burst | the census is a 55.48 % FLOOR, blind to `memcpy`/computed addresses |
| **10** | Whether external `WriteProcessMemory` is an FK-32 hazard | a matched no-write sitting | n=1, confounded (S138). **ARM H is in-shim, which sidesteps it entirely — keep it that way.** |

---

## 10. CORRECTIONS

### 10.1 `docs/s140-tier1-cfg.md` §5 — the decision rule (⛔ REQUIRED)

**STALE (verbatim, `:603-605`):**
> - `+0x16B0` holds the sentinel ⇒ **`StartNewPhysics` ran with `Iterations == 0`** [M].
> - `+0x16B0` still `(0,0,0)` **while `+0xE8` still holds the sentinel** ⇒ it did not run [M].
> - `+0xE8` no longer holds the sentinel ⇒ the probe's own control failed; the run is void.

**REPLACEMENT:**
> ⚠⚠⚠ **SUPERSEDED (S140 Tier 2). THE VELOCITY-SENTINEL FORM HAS A FALSE NEGATIVE IN THE WORLD
> WHERE THE ANSWER IS YES, and clause 3 is not merely under-specified — it is backwards.**
> **[M] The payload is REFRESHED EVERY FRAME**: engine `PerformMovement` contains exactly ONE
> `call [rax+0x720]` (`0x035EB13A`), and the payload write `0x055C244F` is unconditional on the
> `Iterations == 0` path. **[M] engine `PhysFalling` ZEROES `Velocity`** when gravity-space
> `SizeSq2D <= 1e-3` (`0x035ED98E comisd [rip→0x077F5180 = 0.0009999999747378752]` /
> `0x035ED996 ja`; the fall-through writes through `rsi`, and `0x035EC9AC lea rsi,[rdi+0xe8]` is the
> sole defining `lea` and DOMINATES both writes). Any physically-inert sentinel is ~1000× below that
> threshold ⇒ it is erased, and the next frame re-snapshots the zero.
> ⇒ **`+0xE8` losing the sentinel is the SIGNATURE OF SUCCESS, not of instrument failure.** The
> instrument control is the **immediate readback at poke time**, never a later comparison.
> **REPLACE WITH: poison the PAYLOAD with a per-object distinctive constant, add the
> dispatch-independent `+0x3DC` receipt (`0x035EB130 mov [rbx+0x3dc],r15d` DOMINATES the `0x720`
> call — proven by predecessor census and node removal), and adjudicate with the 8-cell table in
> `scratchpad/s140t2/ADJUDICATION.md` §4.**
> ⚠ **And SCOPE row 1:** a payload hit proves `ULokiCMC::StartNewPhysics` was **ENTERED**, nothing
> more. All four engine gates are downstream of the payload write.

### 10.2 `docs/s140-tier1-cfg.md` §5 — the sentinel value

**STALE:** *"write `(0.0009765625, 0, 0)` (exactly representable, physically inert)"*
**REPLACEMENT:** ⚠ **NOT INERT [M].** `2^-10` gives `SizeSq2D = 9.5367431640625e-07`, **95×** the
`9.99999993922529e-09` tolerance at `0x055B87E4` in `ULokiCMC::PerformMovement`, flipping that branch
from its ZeroVector arm to the normalise arm. **Use `2^-20 = 9.5367431640625e-07` per component**
(SizeSq `9.09e-13`, 11,000× below). ⚠ Five exact-zero comparisons remain and flip for *any* non-zero
value — which is why the Velocity write is SECONDARY and the payload poison is PRIMARY.

### 10.3 `docs/s140-tier1-cfg.md` §4.6 — the writer-set grade

**STALE:** the `+0x16B0` writer census stated as **[M]**.
**REPLACEMENT:** **[M] for the two positives (`0x055C244F`, `0x055C245E` — Tier 1 names only the
first; `0x055C245E` writes Z at `+0x16C0`, inside the range the sentinel reads); [I, strong] for the
EXCLUSION of every other writer.** The census is a **55.48 % FLOOR** and is blind to computed
pointers, indexed forms and register-sized `memcpy`. Four independently written censuses agree, which
is what earns the *strong*.

### 10.4 `CLAUDE.md` — the S141 next-step line (⛔ REQUIRED)

**STALE (verbatim):**
> ★ **NEXT (S141), and it is one experiment:** **THE VELOCITY-SENTINEL TEST.** Write a small
> distinctive sentinel (e.g. `(0.0009765625, 0, 0)` — exactly representable, negligible speed) into
> `Velocity @CMC+0xE8/F0/F8`, wait ≥3 frames, then read `CMC+0x16B0..+0x16C7` and re-read `+0xE8` as
> the probe's own control. **Sentinel present in the payload ⇒ `ULokiCMC::StartNewPhysics` ran with
> `Iterations == 0` [M]. Payload still `(0,0,0)` while `+0xE8` holds the sentinel ⇒ it did not [M].**

**REPLACEMENT:**
> ★★★★★ **NEXT (S141) — THE PAYLOAD-POISON TEST (S140 Tier 2 revised the velocity form; do NOT fly
> it as written above).** ⚠⚠ **[M] The payload is REFRESHED EVERY FRAME** (exactly one
> `call [rax+0x720]` at `0x035EB13A` per `PerformMovement`; the write `0x055C244F` is unconditional
> on the `Iterations==0` path) **and engine `PhysFalling` ZEROES `Velocity`** below a `1e-3`
> gravity-space `SizeSq2D` (`0x035ED98E`, writing via a dominating `lea rsi,[rdi+0xe8]` at
> `0x035EC9AC`). ⇒ *"poke Velocity, wait ≥3 frames"* **returns a false negative in exactly the world
> where `StartNewPhysics` runs.**
> **THE ARM: poison `CMC+0x16B0..0x16C7` with a per-object distinctive constant** (bot and player get
> DIFFERENT poisons — that is the two-sided addressing control, and it is mandatory because
> **`ALokiCharacter` has its OWN live fields at `+0x16B0` and `+0x16C8`** [M:
> `0x055B860B mov byte [r15+0x16c8],0` with `r15 = CharacterOwner`, plus an unconditional 24-byte
> getter `0x055A9A30` with 3 live callers, all casting through `0x054F8C40`]). **Poison changed ⇒
> `ULokiCMC::StartNewPhysics` was ENTERED with `Iterations==0`. Poison intact after 10 s of frames ⇒
> it was not.**
> ★★ **AND ADD THE DISPATCH-INDEPENDENT RECEIPT: `0x035EB130 mov dword [rbx+0x3dc], r15d` DOMINATES
> the `call [rax+0x720]`** (each of `0x035EB126/129/12C/130/137/13A` has exactly ONE in-edge; the
> call is unreachable with `0x035EB130` banned). **Poke `CMC+0x3DC = 0x7FFFFFF0`; if it is reset,
> the basic block containing the dispatch RAN — without trusting the vtable.** `+0x3DC` is read only
> at `0x035ECE5D` inside engine `PhysFalling`, downstream, so the poke is inert; use a **positive**
> value (a negative one takes the permissive `jge` arm).
> ⚠ **`+0xE8` losing the sentinel is SUCCESS, not a void run.** Full 8-cell table:
> `scratchpad/s140t2/ADJUDICATION.md` §4. ⚠ **The frame witness is `+0x12B0` ADVANCING** — frozen is
> UNINTERPRETABLE (≥3 causes), so both-frozen ⇒ **VOID**, never "did not run".

### 10.5 `CLAUDE.md` — the `driverecompute` regression gate

**STALE:** *"Regression gates `botai 5e47c13cf7f0a158` and `driverecompute a2a952babfed256b`
**UNCHANGED**"*
**REPLACEMENT:** ⚠⚠ **`driverecompute a2a952babfed256b` IS DEAD [M, confirmed by prediction].** A
rebuild from HEAD yields **`4465ebc4d7168c03`**, `.text`-identical to `gasattr-ctrl` ⇒ the two are a
**live degenerate pair** and an A/B between them settles nothing. `lokibot` reads
**`e123816b65d68e5e`**, not the recorded `3119d75ae2ca1859`; `driverecompute-ctrl 2a91f0aa7f3d521b`
and `lokibot` are currently two builds from two different source generations (**stale, which is worse
than degenerate**). **Re-record all three before using any as a gate.**

### 10.6 `CLAUDE.md` — the `MOVE_Dashing` / `MOVE_Custom` note

**No change; re-confirmed independently.** My own read of the 8-entry table at `.text 0x03600BF8`
bounded by `cmp esi,7`: case 6 → disp `0xCC8`, case 7 → disp `0x990`. ★ **One addition:**
disp `0xCC8` resolves to `0x035EB870` in **BOTH** vtables ⇒ `PhysDashing` lives in the **engine**
class — **Loki forked the engine `UCharacterMovementComponent`, it did not merely subclass it.**
That reframes every "engine `UCMC` is stock" assumption.

### 10.7 `docs/s140-tier1-cfg.md` §4.2 — the transcription

**Add the two omissions:** `0x055C2466 0f28ca movaps xmm1,xmm2`, and the **second `+0x12B0`
accumulator** on the `Iterations > 0` arm (`0x055C2483 addss xmm0,[rcx+0x12b0]` /
`0x055C248B movss`), gated on `Iterations > 0 && MovementMode == 3`. ⇒ **`+0x12B0` has TWO writers,
not one**; it can witness dt>0 but cannot name a function.

### 10.8 `docs/s140-tier1-cfg.md` §2 — the engine-`StartNewPhysics` `.pdata` claim (via L3)

**STALE (L3 §2, carried forward from Tier 1 `:772`):** *"no `.pdata` row covers it"* — stated of
engine `StartNewPhysics 0x03600990`.
**REPLACEMENT:** **FALSE for the engine function** — three chained rows cover
`0x03600990..0x03600A57..0x03600BD3..0x03600C18` (`seen_in_dumps=76` each) [inherited V3, with two
passing controls in the same query]. **The true fact belongs to the LOKI functions**
(`0x055C2430`, `0x0530ABF0`, `0x0530AC10`, `0x0530C7E0` — `0x055C2430` genuinely has no row, nearest
starts `0x055C24A0`), which is what Tier 1 `:772` says. Do not transpose it.

---

## 11. INSTRUMENT DEFECTS FOUND THIS PASS

| id | defect | how it presented | how it was caught | generalises to |
|---|---|---|---|---|
| **S140t2-a** | **A lane's own headline can carry an un-re-derived claim its own body refutes.** L5 §0 states the `CalcVelocity 1e-4` clamp is "a complete mechanical account of S139 flight 4" while L5 §4.5 P5/P6 predict the clamp **does not fire**. | a confident [M]-shaped headline | V5, then me from the bytes (`0x055AC97A cmp al,3 / je`) | **"a digest is an instrument" one level down — inside a single document.** Re-derive your own headline against your own §N before publishing. |
| **S140t2-b** | **A base-register distribution attached to the wrong population.** L1 §3.2 prints an rbp/rbx/rcx/… table under an "83 TRUE writes" heading that **sums to 142** (its pre-filter count over a wider range); its owner-function count reads 29 / 21 / 15 in three places for one quantity. | a plausible, precise-looking table | V1's independent census | **A count is only meaningful with its filter quoted.** V1 got 166/110/86/80 for the same range under four different validity filters. |
| **S140t2-c** | **capstone `operands[0].type == MEM` over-reports.** The mandated write rule counts `cmp`/`test`/`ucomisd` as writes. | inflated write censuses | L1 flagged it; I excluded those mnemonics explicitly | The S140 rule needs a rider: `operands[0].type == MEM` **AND** the mnemonic is not a comparison. |
| **S140t2-d** | **A `.pdata` negative transposed from one function to another.** L3: "no `.pdata` row covers engine `StartNewPhysics`". Three chained rows exist; the true fact belongs to the **Loki** functions, and Tier 1 `:772` says so. | an [M]-shaped negative | V3 | **Carrying a digest's claim onto a neighbouring address without re-deriving it.** Same family as S140t2-a. |
| **S140t2-e** | **A linear disassembly sweep is not a CFG, and it desyncs *in the exact regions under dispute*.** My own sweep at `0x035DCD60` decoded `xchg ebx,eax / or al,[rax]`; at `0x0559EA20` `add byte [rcx-0x77],al`; at `0x035EC960` a `hlt`. All three regions hold real, load-bearing instructions. | "those bytes do not exist" | CFG-anchored re-read | Already recorded at S140; **it recurred three times in one adjudication pass.** Never re-check a quoted byte string with a linear sweep. |
| **S140t2-f** | **An off-by-one in a displacement-census guard silently drops the very instruction under test.** V1's first guard was `if a + ins.size <= pos + 4: continue` (correct: `>=`), dropping every instruction whose displacement is its **last field** — i.e. exactly `0f 11 81 b0 16 00 00 movups [rcx+0x16b0], xmm0`. It returned a clean, plausible "10 writes, none on a CMC" and **missed both known-true writers.** | a clean negative | a **pre-registered** positive control (`0x55C244F in writes`) | **Pre-register the known-true rows of any census as mandatory positives before running it.** |
| **S140t2-g** | **A backward-decode anchor length is part of the instrument.** V3's `back=3` silently misses `c7 83 <disp32> <imm32>` (hid 2 of 6 base-ctor default writes); a `back=12` variant manufactures plausible mid-instruction `adc`/`sub` decodes. | missing and phantom instructions | CFG cross-check | Anchor-and-decode-backwards always needs a CFG cross-check. |
| **S140t2-h** | **A displacement resolved against an unverified receiver names nothing.** V5 resolved `call [rax+0x970]` in engine `PhysFalling` against the CMC vtable and got `PhysWalking`, where the receiver is `CharacterOwner`. Self-declared. | a confidently wrong callee name | the lane's own two-`+0x4C0` warning, applied to itself | Same offset is a different method in every hierarchy — CLAUDE.md records this and it recurred. |
| **S140t2-i** | **`grep -rl` over `docs/` timing out and its partial output read as a negative** (recorded S136) — and **`strings` is not installed on this machine**, returning silence for every token. | false ABSENTs | exit-code check / a positive control | Scope your greps, check the exit code, always include a positive control. |
| **S140t2-j** | **A lane reviewed a `.bak`, not the shipped file.** L4 audited the 452-line `cmc_earlyout_readout.py.bak`; the shipped file was 524 lines (now 538). Every `:NNN` past ~line 103 is off by up to +72, and 5 of its 10 "REQUIRED EDITS" were implemented by a sibling lane 48 s before it wrote. `git status` was **silent** (the tracked file matched HEAD). | a correct audit pointing at wrong lines | V4 diffing mtimes | **In a parallel-lane session the tree moves under you. Record the file's mtime and line count in the report header.** All seven L4 defects DO reproduce in the shipped file — the analysis was right, the map was stale. |
| **S140t2-k** | **A "positive control" that cannot fail for the reason that matters.** L6's byte-scan control was `KERNEL32 == 1`, which proves the file opened, not that a shim-authored literal would be found. A two-sided shim-literal control (`ARM F: drive Update…` = 1 in three builds, 0 in two) sat **unlabelled in the lane's own table**. | an earned-feeling negative | V6 | **A positive control validates the mechanism it exercises, not the question you are asking** (recorded S140; recurred). |
| **S140t2-l** | **An adjudication that averages opinions instead of measuring produces the wrong answer.** On L5-vs-V5 my *first* reading of `GetMaxAcceleration 0x055AC910` stopped at `cmp al,1 / jne` and concluded V5 was wrong; the very next instruction block (`0x055AC97A cmp al,3 / je`) reverses it. | a confident refutation of the correct verifier | reading eight more bytes | **Read the branch target, not just the branch.** |

---

## APPENDIX — MY OWN CONTROL LEDGER (reproduce before trusting anything above)

```
PE flat .................................. True
ImageBase ................................ 0x7FF608F40000
.text decrypted .......................... 16800/30281 pages = 55.48 %   (FLOOR)
DARK control 0x5A6AC40 page .............. 0 / 4096 non-zero            PASS
vtable disps (18, two-sided) ............. 12 OVERRIDE / 6 identical    PASS
unique-ptr census (4) .................... exactly 1 each, at base+disp PASS
engine PerformMovement CFG ............... 1461 ins / 148 calls / 0 indirect jmp / 1 ret
  |reach_back(0x035EB13A)| ............... 1075
  exit edges leaving R ................... 6  (+ the call's own fallthrough)
  backward edges in fn / in R ............ 2 / 0
call [rax+0x720] sites ................... 1  (0x035EB13A)
call [rax+0xa50] sites ................... 1  (0x035EB569)
preds of 0x035EB126/129/12C/130/137/13A .. 1 each, linear fallthrough
call reachable avoiding 0x035EB130 ....... False        <- DOMINANCE
engine PhysFalling CFG ................... 1482 ins
  rsi defs in body ....................... 1 (0x035EC9AC lea rsi,[rdi+0xe8]) + 1 epilogue restore
  0x035ED9BB / 0x035ED9C3 reachable
    avoiding that lea .................... False / False <- DOMINANCE
1e-3 constant @ .rdata 0x077F5180 ........ 0.0009999999747378752
1e-8 constant @ .rdata 0x076A5918 ........ 9.99999993922529e-09
MIN_TICK_TIME @ .rdata 0x076B8E74 ........ 9.999999974752427e-07 (f32)
1.0 constant  @ .rdata 0x0768C4C8 ........ 1.0
0x055A9A30 callers ....................... 3, ALL cast via 0x054F8C40 (= the CharacterOwner cast
                                           used at ULokiCMC::PerformMovement 0x055B839D)
allThreadCalls, bot ladder vs s128 ....... 1 vs 588 on a character-identical [FS] cfg
```

**Tools:** `scratchpad/s140t2/ADJ/adj.py` (independent PE reader + recursive-descent CFG;
imports nothing from `tools/` or any lane).
