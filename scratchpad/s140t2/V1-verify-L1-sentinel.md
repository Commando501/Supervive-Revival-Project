# S140 TIER 2 — ADVERSARIAL VERIFICATION OF LANE 1 (`L1-sentinel-mechanism.md`)

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game process.**
Image `dumps/merged13.dump.exe`, ImageBase `0x7FF608F40000`, RVA == file offset (re-verified, V0).
All tooling written from scratch for this lane in `scratchpad/s140t2/V1tools/`
(`vpe.py`, `vcfg.py`, `vcensus.py`) — a **seventh** independent instrument. It imports neither
`tools/cfg.py`, nor `scratchpad/s140/*`, nor any of L1's `L1tools/*`. I did not run L1's scripts.

---

## VERDICT UP FRONT

**L1's three headline verdicts on claims (a), (b) and (c) are CONFIRMED. I could not refute any of
them, and I reproduced every load-bearing byte.** What I refute is smaller and what I add is bigger:

| L1 item | my verdict |
|---|---|
| (a) the `Iterations==0` snapshot block, incl. the two Tier-1 listing defects | **CONFIRMED byte-exact** |
| (b) `Iterations == 0` at `0x035EB13A`, via predecessor census + node-removal dominance | **CONFIRMED** |
| (c) exactly TWO CMC-side payload writers (`0x055C244F` X/Y, `0x055C245E` Z) | **CONFIRMED in substance** |
| L1's headline: *"Tier 1 §5's third decision clause is BACKWARDS"* | **DOWNGRADED — over-stated. It is AMBIGUOUS, not backwards.** [I], not [M] |
| L1's `83` writes / `142`-row base distribution / `29` vs `21` owners / `100` r8 sites | **four count-and-unit defects, all reproduced as defects** |

### AND THE THING BOTH DOCUMENTS MISSED, WHILE LOOKING STRAIGHT AT IT

**[M] THE PAYLOAD IS REFRESHED EVERY FRAME. It is not a write-once receipt.**
Tier 1 and L1 both reason from *"the payload is durable — the `0xA50` override clears only the flag
byte, never the payload."* That is true and it is **not the property the experiment needs**. The
payload is durable against the **CLEAR**; it is **not** durable against the **NEXT FRAME'S SET**.

=> the shipped instruction — *"poke Velocity, **wait >= 3 frames**, then read `+0x16B0`"*
(Tier 1 §5, L1 §4.4 step 2, and `CLAUDE.md`'s S141 line) — **has a FALSE-NEGATIVE MODE in exactly
the world where the answer is YES.** See §4. L1 found a weaker form of this hazard (`+0xE8` gets
clobbered) and stopped one step short of the damaging one.

**The fix is cheaper, safer and one-sided: poke the PAYLOAD, never Velocity.** See §5. It is
provably inert, needs no `+0xE8` write at all, and removes the perturbation Tier 1 itself warned
about.

---

## V0. MY OWN CONTROLS (run before any analysis, my own code)

| control | result |
|---|---|
| PE flat (all 10 sections `VirtualAddress == PointerToRawData`) | **True** |
| ImageBase from optional header | **`0x7FF608F40000`** |
| `.text` pages non-zero | **16800 / 30281 = 55.48 %** — matches brief and L1 exactly |
| Known-DARK control `ULokiRespawnComponent::Respawn 0x5A6AC40` page | **0 / 4096** PASS |
| Five fold constants (`c20000`/`33c0c3`/`32c0c3`/`b001c3`/`0f57c0c3`) | **5 / 5 PASS** |
| `ULokiCMC` vtable `.rdata 0x088F8570`, 8 displacements | **8 / 8 PASS** |
| engine `UCMC` vtable `.rdata 0x07FBED58`, 6 displacements (two-sided) | **6 / 6 PASS** |
| every function under analysis LIT | page nz **3129–3883**, 10 / 10 PASS |
| census positive controls (`0x55C244F`, `0x55C245E` must appear) | **2 / 2 PASS** — *after* fixing my own defect, see V0.1 |

**Independent CFG of engine `PerformMovement 0x035E9EC0`** (7th instrument):
`1461` instructions · `148` calls (**115 direct / 33 indirect**) · **0 indirect jumps** ·
**0 decode failures** · span `6538` / covered `6538` / **gaps 0** · **1 `ret` at `0x035EB1CA`** ·
`|reach_backward(0x035EB13A)| = 1075`. **Identical to all five prior instruments.**

**FLOOR CAVEAT, as required:** every image-wide census below runs over `.text` that is
**55.48 % decrypted**. All counts are **FLOORS**. Dark pages are all-zero and cannot match a byte
pattern, so the census silently under-reports rather than erroring — self-filtering, not
self-correcting.

### V0.1 MY OWN INSTRUMENT DEFECT, CAUGHT BY A PRE-REGISTERED POSITIVE CONTROL

My first census guard was `if a + ins.size <= pos + 4: continue` (the displacement must lie inside
the instruction). The correct predicate is `>= pos + 4`. The `<=` form **silently drops every
instruction whose displacement is its LAST field** — which is exactly
`0f 11 81 b0 16 00 00  movups [rcx+0x16b0], xmm0`. It returned **10 writes** and **missed both
known-true writers**, and it looked like a clean, plausible result.

It cost one run because I had pre-registered `0x55C244F in writes` and `0x55C245E in writes` as
mandatory controls. Without them I would have published *"only 10 writes to the payload range, none
on a CMC"* — an instrument blind spot recorded as a property of the game, in the very lane convened
to catch that. **Recorded as an S140 instrument defect.**

---

## 1. CLAIM (a) — CONFIRMED BYTE-EXACT

Raw bytes, my own read:

```
0x55C2430 0f 28 d1 45 85 c0 75 3d 44 38 81 c8 16 00 00 74
0x55C2440 07 44 88 81 c8 16 00 00 0f 10 81 e8 00 00 00 0f
0x55C2450 11 81 b0 16 00 00 f2 0f 10 89 f8 00 00 00 f2 0f
0x55C2460 11 89 c0 16 00 00 0f 28 ca c6 81 c8 16 00 00 01
0x55C2470 e9 1b e5 03 fe 7e 1c 80 b9 31 02 00 00 03 75 13
0x55C2480 0f 28 c2 f3 0f 58 81 b0 12 00 00 f3 0f 11 81 b0
0x55C2490 12 00 00 0f 28 ca e9 f5 e4 03 fe 41 56 53 56 57
```

My disassembly is **identical, instruction for instruction, to L1's**, including:

- **[M] `0x055C2466 0f28ca movaps xmm1, xmm2` IS PRESENT** — Tier 1 §4.2's listing does omit it.
  L1's defect #1 is real.
- **[M] the `Iterations != 0` path DOES contain a second `+0x12B0` accumulator** —
  `0x055C2483 addss xmm0,[rcx+0x12b0]` / `0x055C248B movss [rcx+0x12b0],xmm0`, guarded by
  `0x055C2475 jle 0x55C2493` and `0x055C2477 cmp byte [rcx+0x231],3 / jne`. L1's defect #2 is real.
  Branch semantics re-derived: `jne` does not touch flags, so the `jle` at `0x055C2475` still reads
  `test r8d,r8d`'s flags with `ZF=0` => taken iff `r8d < 0`. **L1's "Iterations < 0" label is
  correct.** The accumulator therefore fires on `Iterations > 0 && MovementMode == 3`.
- **[M] function extent `0x055C2430 .. 0x055C249B` = 107 bytes**; a new frame
  (`41 56 53 56 57` = `push r14/rbx/rsi/rdi`) begins at `0x055C249B`.
- **[M] both paths tail-`jmp 0x3600990`; there is no `ret` and no path that skips the engine body.**

**NEW, and it is load-bearing for §5:** I proved by **node removal** that the payload write
**DOMINATES** the flag set inside this function —
`reach_fwd(0x55C2438, banned={0x55C244F})` does **not** contain `0x55C2469`.
=> the flag can never be `1` while the payload holds a value the snapshot did not write.
That is what makes the payload poke in §5 provably inert.

### ONE DOWNGRADE ON L1's DEFECT #2

L1 argues *"if this second site also fired every frame, `+0x12B0` would advance faster than 1.0x
real time; it does not"*, graded [I]. The grade is right, but its **premise is ungraded**: the
argument presupposes `StartNewPhysics` is re-entered with `Iterations > 0`.
**[M] I found NO such re-entry from either falling implementation** —
`ULokiCMC::PhysFalling 0x055B89F0` has **zero** `call [reg+0x720]` and **zero** direct calls to
`0x3600990` / `0x055C2430`; the engine's `0x035EC850` likewise. (Scope caveat: my CFG for
`0x055B89F0` covers 370 instructions and does not follow its far tail-`jmp` to the Super, so this is
a **floor**.) **The recursion the [I] reasons about has not been shown to exist at all.**

---

## 2. CLAIM (b) — CONFIRMED, and L1's strengthening is real

Raw bytes and disassembly reproduce exactly (`0x35EB120 ff 90 08 0a 00 00 48 8b 03 45 33 c0 ...`).

**TEST 1 — predecessor census, from my own 1461-node CFG:**
```
0x35EB126 preds: [('0x35eb120','fall')]     0x35EB130 preds: [('0x35eb12c','fall')]
0x35EB129 preds: [('0x35eb126','fall')]     0x35EB137 preds: [('0x35eb130','fall')]
0x35EB12C preds: [('0x35eb129','fall')]     0x35EB13A preds: [('0x35eb137','fall')]
```
**[M] every node in the sequence has exactly ONE in-edge, and it is the linear fallthrough.**
No branch anywhere in the function targets the interior.

**TEST 2 — dominance by node removal (different algorithm):**
```
call reachable from entry normally    : True
call reachable with 0x35EB129 BANNED  : False   => xor r8d,r8d DOMINATES the call
```

**TEST 3 — r8-family destination writes, whole function:** the three nearest sites are
`0x035EAFD0 mov r8,r12`, `0x035EB05A mov r8,[rbx+0x198]` (both **before** the xor) and
`0x035EB2CA lea r8,[rbp-0x20]` (**after** the call).
**Strictly between `0x035EB129` and `0x035EB13A`: ZERO writers and ZERO calls** — with `cmp`/`test`
included *or* excluded.

=> **[M] `Iterations == 0` at `0x035EB13A`.** L1's criticism of Tier 1's argument is fair: "no
writers between" alone does not exclude an in-edge, and Tier 1 did not test for one. L1 did, and so
did I, independently.

---

## 3. CLAIM (c) — CONFIRMED IN SUBSTANCE; FOUR COUNT DEFECTS IN L1's SUPPORT

### 3.1 My census (different method from L1's)

For each 4-byte LE occurrence of each displacement in `0x16B0..0x16C7` inside `.text`, decode at
every start 1..15 bytes back; accept iff the decode has a `MEM` operand with a **base register** and
exactly that displacement **and** the displacement bytes lie inside the instruction. Classify writes
by **`operands[0].type == MEM`**, then drop `cmp`/`test`.
**I never used `regs_access` for write classification** (the recorded S140 capstone defect).
Validity filter: a self-synchronising **linear-sweep vote** from 64 backward starts.

```
accepted decodes in [0x16B0,0x16C7]            : 336
WRITES (operands[0]==MEM, cmp/test excluded)   : 166   (no validity filter)
  with vote >= 1                               : 110
  with vote >= 8  and vote >= 16               :  86
  with vote >= 32                              :  80
CONTROL votes on the two known-real writes     : 0x55C244F = 54 , 0x55C245E = 53
base regs of the 86-set: rbp 47, rbx 17, rsp 9, rdi 6, rcx 5, r14 2   (sums to 86)
```

### 3.2 THE CONCLUSION HOLDS

Of the 86, only **four** sit anywhere in the Loki character/CMC code region:

```
0x0559EA2F  410f1186b0160000  movups [r14+0x16b0], xmm0
0x0559EA3F  f2410f1186c01600  movsd  [r14+0x16c0], xmm0
0x055C244F  0f1181b0160000    movups [rcx+0x16b0], xmm0   *** ULokiCMC ***
0x055C245E  f20f1189c0160000  movsd  [rcx+0x16c0], xmm1   *** ULokiCMC ***
```

and the `r14` pair is adjudicated by **vtable install**, which I reproduce independently:

```
fn 0x0559E180 : 0x0559E1DC lea rax,[rip] -> .rdata 0x088E5CA8   (pawn VT; +0x8C0 = 0x03BBF3C0
                                                                 APawn::SpawnDefaultController)
fn 0x0559F580 : 0x0559F5AC lea rax,[rip] -> .rdata 0x088F8570   (the ULokiCMC VT)
```

=> **[M] `0x0559EA2F`/`0x0559EA3F` are `ALokiCharacter` writes; `0x055C244F`/`0x055C245E` are the
only `ULokiCMC` payload writers.** Tier 1 §4.6's adjudication and L1's reproduction of it both
survive a third independent derivation. **Tier 1's "the only CMC-side writer is `0x055C244F`" is
incomplete exactly as L1 says: `0x055C245E` writes Z at `+0x16C0`, inside the payload the sentinel
test reads.**

Corroborating, all mine: `0x055C2430` has **exactly 1 aligned qword pointer image-wide**
(`0x088F8C90 = LokiVT + 0x720`) and **0 direct `e8 rel32` callers** over decrypted `.text` (floor);
engine `PerformMovement` contains **exactly one** `call [.+0x720]` (`0x035EB13A`) and **exactly
one** `call [.+0xA50]` (`0x035EB569`).

### 3.3 FOUR DEFECTS IN L1's NUMBERS (none changes the conclusion)

1. **The `83` is METHOD-DEPENDENT and is presented as a bare `[M]` count.** The same question
   answers **166 / 110 / 86 / 80** depending on the validity filter. My best-matched setting gives
   **86**, not 83. **Quote the filter with the number or do not quote the number.**
2. **L1 §3.2's base-register distribution does not belong to the `83`.**
   `rbp 63 + rbx 30 + rcx 14 + rdi 13 + rsp 12 + r14 5 + rsi 3 + rax 1 + r15 1 = 142` — which is
   L1's own §3.2 count of writes over the **wider** range `[0x16B0,0x16CF]` **before** the
   `cmp`/`test` exclusion. It is printed under the heading *"TRUE writes to +0x16B0..+0x16C7 : 83"*.
   **A distribution mis-attached to a different population.** (Mine sums to its own count exactly.)
3. **`29` vs `21` owner functions.** §3.2 says *"across 29 distinct containing functions"*; §3.3(i)
   says *"Of the 21 owner functions"* and §3.3(iv) *"for all 21 owners"*, while §3.3(i)'s visible
   table lists **15**. Three numbers for one quantity.
4. **`100` r8-family writer sites.** **[M] 100 is the count INCLUDING `cmp`/`test`; excluding them
   it is 87** — and it is quoted in the same paragraph in which L1 states it excluded those two
   mnemonics "everywhere below". Harmless here (the between-region count is 0 either way) but it is
   a definition quoted without its unit.

### 3.4 The exclusion grade

L1 grades its own exclusion of the other owners **[M] for the 7 provable stack cases and
[I, strong] for the rest**, and criticises Tier 1 for grading the whole thing [M]. **I agree, and
that self-downgrade is correct.** "Not in the `ULokiCMC` vtable and not called from one" does not
exclude a non-virtual `ULokiCMC` member. **On top of that the whole census is a 55.48 % floor.** The
honest grade for *"nothing else in this image writes `CMC+0x16B0`"* is **[I, strong], never [M].**

---

## 4. THE REFUTATION THAT MATTERS: THE PAYLOAD IS REFRESHED EVERY FRAME

### 4.1 The mechanism, all [M], all mine

1. The payload write is **unconditional** on the `Iterations == 0` path — both arms of the
   conditional `Reset` at `0x055C243F/41` converge on `0x055C2448`, and node removal shows the write
   **dominates** the flag set (§1).
2. Engine `PerformMovement` calls the disp-`0x720` slot **exactly once** — one site, `0x035EB13A`.
3. `Iterations == 0` there (§2).

=> **[M] every engine `PerformMovement` call that reaches `0x035EB13A` overwrites
`CMC+0x16B0..+0x16C7` with the CURRENT `Velocity`.** The payload therefore always holds **the most
recent frame's pre-step Velocity**, not the first one ever taken.

### 4.2 What that does to the shipped decision rule

Tier 1 §5 and L1 §4.4 both instruct: poke `+0xE8` with a sentinel, **wait >= 3 frames**, read
`+0x16B0`. Enumerate the worlds:

| world | `+0x16B0` at N+3 | `+0xE8` at N+3 | Tier 1 says | L1 says | TRUTH |
|---|---|---|---|---|---|
| SNP never runs | pre-poke value | sentinel | did not run | did not run | **correct** |
| SNP runs, engine bails at one of its 4 gates, nothing writes Velocity | **sentinel** | sentinel | ran | ran | **correct** |
| **SNP runs, `PhysFalling` fires and returns Velocity to `(0,0,0)`** | **`(0,0,0)`** | `(0,0,0)` | **VOID** | **UNINTERPRETABLE** | **IT RAN** |

**Row 3 is a FALSE NEGATIVE, and it is the world in which the physics step actually works.** The
measured steady state is `Velocity == (0,0,0)` and translation `0.00 uu` (S139), so row 3 is not a
corner case — it is the leading alternative hypothesis.

L1 found the `+0xE8` half of this and named the right culprit (`PhysFalling`, dispatched by
`StartNewPhysics` case 3 — which I reproduce exactly from the jump table below). It then **kept
"Wait at least 3 frames" in its own recommended fix** and routed row 3 to UNINTERPRETABLE. That is
better than VOID, but it still discards the positive.

**Jump table, re-read by me at `.text 0x03600BF8`** (`cmp esi,7` at `0x03600A7B`, `jmp rcx` at
`0x03600A95`) — every case, every displacement, identical to L1:
```
case 0 @0x3600BA8 (no vcall)      case 4 @0x3600AF3 disp 0x988 -> 0x035EF1D0
case 1 @0x3600A97 disp 0x970      case 5 @0x3600ADC disp 0x980 -> 0x035EE5A0
case 2 @0x3600AAE disp 0x978      case 6 @0x3600B0A disp 0xCC8 -> 0x035EB870   (MOVE_Dashing)
case 3 @0x3600AC5 disp 0x830 -> LokiVT 0x055B89F0  *** ULokiCMC::PhysFalling ***
case 7 @0x3600B21 disp 0x990 -> LokiVT 0x055B88E0  (MOVE_Custom)
```
and `ULokiCMC::PhysFalling`'s **7** writes to `+0xE8`/`+0xF8` with `rbx = rcx = this`
(only two `rbx` definitions: `0x055B8A28 mov rbx,rcx`, `0x055B909E mov rbx,[r11+0x38]`), against
the two-sided control that engine `PerformMovement`'s two `+0xE8`/`+0xF8` writes are **`rbp`-based
stack** (`rbp = 0x035E9EC5 lea rbp,[rsp-0x860]`) and `ULokiCMC::PerformMovement` has **zero**.
All reproduced.

### 4.3 DOWNGRADE OF L1's HEADLINE

L1 states as its lead finding: *"Tier 1 section 5's third decision clause is **BACKWARDS** and would
discard a correct positive result."* **Over-stated.** Tier 1's three clauses are an **ordered**
list, and clause 1 (*"`+0x16B0` holds the sentinel => it ran"*) is stated **unconditionally on
`+0xE8`** and comes first. Under first-match-wins the positive is kept.

**Defensible form:** the three clauses are **mutually inconsistent** for the state
(`+0x16B0` = sentinel, `+0xE8` != sentinel), and Tier 1 does not say which wins.
**Grade "would discard a correct positive" as [I], not [M].**
L1's substantive worry is right; its stated mechanism is the weaker one and its grade is too strong.

---

## 5. THE REPLACEMENT EXPERIMENT — POKE THE PAYLOAD, NEVER VELOCITY

**Pre-write a sentinel into `CMC+0x16B0..+0x16C7`. Do not touch `+0xE8` at all.**

| step | action |
|---|---|
| 1 | read `+0x16B0..+0x16C7` and `+0xE8..+0xFF` **raw**, record both |
| 2 | write sentinel (e.g. `(1234.5, 6789.25, -4242.125)` — **safe here**, see below) to `+0x16B0/B8/C0` |
| 3 | read `+0x16B0` back **immediately**, before yielding — *this* is the "did my write land" control |
| 4 | wait >= 3 frames; read `+0x16B0..+0x16C7` **and** `+0xE8..+0xFF`; record raw |

| `+0x16B0` at step 4 | conclusion |
|---|---|
| **!= sentinel** | **[M] `ULokiCMC::StartNewPhysics` was ENTERED with `Iterations == 0`** — the only CMC-side writer overwrote it |
| **== sentinel** | **[M] it was not entered** in the observation window |
| step-3 readback != sentinel | run void (probe fault) |

**Why this is strictly better than the Velocity poke:**

- **It is one-sided and has no false-negative mode.** Under §4.1 the payload is refreshed every
  frame, so "was it overwritten?" is exactly the question, and the answer does not depend on what
  `PhysFalling`, `CalcVelocity` or anything else downstream does.
- **[M] IT IS PROVABLY INERT — it cannot perturb the system under test.** The only consumer of the
  payload is `GetRecentVelocity` (`.data 0x09BC9AD0 = {"GetRecentVelocity", thunk 0x0530C7E0,
  impl 0x0530AC10}` — name and both addresses re-read by me from the record), and its body is
  `cmp byte [rcx+0x16c8],0 ; mov eax,0x16b0 ; mov r8d,0xe8 ; cmove eax,r8d` => **flag == 0 returns
  `Velocity`, not the snapshot.** The flag is `0` between frames (Tier 1 §4.3's `0xA50` clear, which
  I confirm), and inside the call the payload write **dominates** the set (§1), so there is **no
  reachable state in which a consumer reads a poked sentinel as a velocity.**
  => Tier 1's warning *"do not use `(1234.5, ...)`, it launches the pawn"* applies to the
  **Velocity** poke and **does not apply here** — a large, unmistakable sentinel is now the better
  choice, because it cannot be confused with any real Velocity value.
- **It does not write `Velocity`**, so it does not change the input to the very step being tested.
- Same `WriteProcessMemory` hazard class as the Tier 1 arm (S138, unresolved, n=1, confounded) —
  24 bytes either way, no change in risk; still pair with a matched no-write sitting.

**Mandatory pre-registration:** the `ULokiCMC` constructor `0x0559F580` writes the **flag**
(`0x0559FDF4`) and **does not initialise the payload** — it is absent from my census
(**[I, strong]**, floor-bounded, not [M]). So `+0x16B0` may hold allocator garbage at step 1.
**Record the step-1 raw value.** If it already differs from `(0,0,0)` that is expected and is not
evidence of anything.

---

## 6. SCOPE CORRECTION BOTH DOCUMENTS NEED: WHICH `StartNewPhysics`?

**[M] The payload write is at the TOP of the Loki override, before its tail `jmp 0x3600990`.**
Engine `StartNewPhysics 0x3600990` then applies **four** early-outs of its own, **all downstream of
the payload write**:

```
0x036009A8 comiss xmm6,[rip+..] / 0x036009AF jb  0x3600BE6   ; MIN_TICK_TIME
0x036009B5 cmp r8d,[rcx+0x3e4]  / 0x036009BC jge 0x3600BE6   ; MaxSimulationIterations
0x036009C5 call [rax+0x6b8]     / 0x036009CD je  0x3600BE6   ; HasValidData()  (a THIRD one)
0x036009E4 call [rax+0x4c0]     / 0x036009EC je  0x3600A57   ; IsSimulatingPhysics()
```

=> **a sentinel hit proves ONLY that `ULokiCMC::StartNewPhysics` was ENTERED.** It does **not**
prove the engine body ran, does **not** prove the mode was dispatched, and does **not** prove
`PhysFalling` fired.

Tier 1's decision row 1 reads *"`StartNewPhysics` ran with `Iterations == 0` [M]"* **without naming
which function** — the same cross-function-boundary over-read S139 already had to retract once
(*"do not read `PerformMovement` runs as the ENGINE's `PerformMovement` runs"*). L1 scopes its own
row 1 correctly (`ULokiCMC::StartNewPhysics`) and then builds its §4.3 `PhysFalling` argument on the
unscoped version. **Write the scoped form into any successor doc.**

---

## 7. SUMMARY TABLE

| # | item | grade |
|---|---|---|
| 1 | L1 claim (a) — byte-exact listing incl. both Tier-1 defects | **CONFIRMED [M]**, 3rd derivation |
| 2 | L1 claim (b) — predecessor census + node-removal dominance + 0 writers/0 calls between | **CONFIRMED [M]** |
| 3 | L1 claim (c) — exactly 2 CMC-side payload writers, `0x055C244F` + `0x055C245E` | **CONFIRMED [M]** (exclusion of the rest **[I, strong]**, floor) |
| 4 | vtable adjudication `0x0559E180` (pawn) vs `0x0559F580` (CMC) | **CONFIRMED [M]** |
| 5 | jump table / `PhysFalling` case 3 disp `0x830` / 7 Velocity writes / rbp-stack control | **CONFIRMED [M]** |
| 6 | engine `PerformMovement` CFG 1461/148/0/0/6538-6538-0/1 ret/1075 | **CONFIRMED [M]**, 7th instrument |
| 7 | L1 headline "third clause is BACKWARDS ... would discard a correct positive" | **DOWNGRADED to [I]** — ambiguous, not backwards |
| 8 | L1 `83` writes | **method-dependent**; 166/110/86/80 by filter. Not a bare [M] |
| 9 | L1 base-register distribution under the "83" heading | **REFUTED** — sums to 142, belongs to a different population/range |
| 10 | L1 `29` vs `21` (vs 15 shown) containing functions | **REFUTED** — three numbers, one quantity |
| 11 | L1 `100` r8 sites | **unit defect** — 100 includes `cmp`/`test`; 87 excludes |
| 12 | L1 §1.3's [I] on the 2nd `+0x12B0` accumulator | **premise ungraded** — no re-entry into SNP found from either `PhysFalling` (floor) |
| 13 | **NEW: the payload is REFRESHED EVERY FRAME; "durable against the clear" != "durable"** | **[M]** |
| 14 | **NEW: "wait >=3 frames then read `+0x16B0`" has a false-negative mode in the YES world** | **[M]** mechanism, **[I]** that row 3 obtains |
| 15 | **NEW: poke the PAYLOAD, not Velocity — one-sided and provably inert** | **[M]** for inertness |
| 16 | **NEW: a payload hit scopes to `ULokiCMC::StartNewPhysics` ENTERED, not the engine step** | **[M]** |
| 17 | my own off-by-one census guard, caught by a pre-registered positive control | **instrument defect, recorded** |

**Bottom line: L1 is a good lane. Every one of its three verdicts survives independent
re-derivation, and its four count defects are cosmetic. Its headline finding is over-graded, and it
stopped one step short of the finding that actually breaks the experiment.**
