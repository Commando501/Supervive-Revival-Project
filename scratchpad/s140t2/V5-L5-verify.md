# V5 — ADVERSARIAL VERIFICATION OF LANE 5 (`L5-downstream-seed.md`)

**2026-08-23. OFFLINE ONLY: zero launches, zero injections, zero writes to the game.**
Image `dumps/merged13.dump.exe`, ImageBase **`0x7FF608F40000`** (read from the optional header by my
own code), flat (10/10 sections `VirtualAddress == PointerToRawData`).
Instrument: `<scratchpad>/v5/vpe.py` — a from-scratch PE reader + capstone-5.0.7 recursive-descent CFG
written for this pass. **I did not run any L5 script and imported nothing from `scratchpad/s140t2/L5/`,
`scratchpad/s140/`, or `tools/`.**

**Write classification is from `operands[0].type == X86_OP_MEM` only. `regs_access` is never consulted**
(S140 recorded defect). `tools/strxref/index/pdata_union.csv` was not used.

⚠ **`.text` is 55.48 % decrypted in `merged13`. Every census below is a FLOOR and is labelled.**

---

## 0. VERDICT IN ONE LINE

**L5's disassembly is excellent and reproduces exactly — I re-derived every CFG count, every address
and every constant it quotes, independently, and found zero transcription errors.** Its problem is
entirely in *what it concludes from them*: **the HEADLINE asserts as an established account something
the lane's own §4.2 + §4.5 predict is FALSE**, and three supporting claims are graded above their
evidence.

---

## 1. WHAT REPRODUCED EXACTLY (my code, my reads) — [M]

| L5 claim | my independent value | verdict |
|---|---|---|
| ImageBase / flat | `0x7FF608F40000`, 10/10 flat | PASS |
| `ULokiCMC` vt `.rdata 0x088F8570`, engine vt `0x07FBED58` | both resolve; all 29 disps I sampled land in `.text` | PASS |
| disp `0x830` -> loki `0x055B89F0` / eng `0x035EC850` | identical | PASS |
| neighbour controls `+0x820/+0x828/+0x838/+0x840` identical in both vtables | identical (`0x03606180 / 0x03600C20 / 0x035E3490 / 0x035FC2C0`) | PASS, non-circular |
| Loki `PhysFalling` CFG | **370 ins, `0x055B89F0..0x055B90F1`, span/cov/gaps 1793/1793/0, 0 decode fails, 0 indirect jmp, 1 ret, 25 direct sites / 23 distinct, 2 indirect** | **digit-for-digit** |
| 23/23 direct targets not-a-fold | 23/23; **0** all-zero entry bytes; **0** sixth-stub-shape matches | PASS |
| Super call unconditional | `\|reach_backward(0x055B8A2B)\| = 14`, entry in R, **exit edges = [] (empty)** | **digit-for-digit** |
| engine `PhysFalling` CFG | **1482 ins, `0x035EC850..0x035EE593`, 7491/7491/0, 36 direct / 13 distinct, 43 indirect** | **digit-for-digit** |
| `CalcVelocity` CFG | **547 ins, `0x035D5D20..0x035D6786`, 2662/2662/0, 1 direct callee `0x03630250`, 11 indirect** | **digit-for-digit** |
| jump table `.text 0x03600BF8` raw 32 B | `a8 0b 60 03 / 97 0a 60 03 / ae 0a 60 03 / c5 0a 60 03 / f3 0a 60 03 / dc 0a 60 03 / 0a 0b 60 03 / 21 0b 60 03`, then `cc` x8 | byte-identical |
| table not in address order (idx 4 > idx 5) | confirmed | PASS |
| all 8 case bodies -> vt disps `-/0x970/0x978/0x830/0x988/0x980/0xCC8/0x990` | identical; `0xCC8` present in the ENGINE vtable too | PASS |
| `GetMaxSpeed` = disp `0x4C8` = `0x055ACB90`, tail `0x055ACBE6 jmp qword [rax+0xc00]`, else `0x055ACBFA jmp 0x35e3c20` | identical | PASS |
| `0x055AC9F0`: `[rcx+0xf08]` -> `je 0x55acb73`; `0x55b18e0` -> `jne`; `[rdi+0xb59]` -> `je`; `call 0x55266e0`; `[rdi+0x16f0]`/`[rdi+0x16f8]` stride `0x38`; `0x055ACB73 xorps xmm0,xmm0; ret` | identical | PASS |
| `0x055266E0 = minss(leaf(rbx+0xF0), leaf(rbx+0x100))`; `0x01F62B10 = f3 0f 10 41 0c c3` | identical | PASS |
| `GetMaxAcceleration 0x055AC910` mode-1 / mode-{3,6} / else structure, exits `0x055AC9AE` (0.0f) and `0x055AC9BC -> jmp 0x35e3ad0` | identical; engine `0x035E3AD0 = [vt+0xce0]() ? [rbx+0x1040] : [rbx+0x28c]` | PASS |
| `GetMinAnalogSpeed 0x035E3D20` returns `[rcx+0x290]` for modes {1,2,3}, else 0.0f | identical | PASS |
| the whole clamp block `0x035D643A..0x035D6527` | identical, instruction for instruction | PASS |
| `.rdata 0x076B49E8` = 1e-4 | **`9.999999747378752e-05`**, raw `000000e0e2361a3f` | PASS |
| `.rdata 0x076B8E74` = 1e-6 | **`9.999999974752427e-07`** | PASS |
| engine `StartNewPhysics` gates at `0x036009AF/BC/CD/EC` and verbosity byte `.data 0x09F85E68` | identical (recomputed the rip-relative myself) | PASS |
| `0x035EC967 mov eax,[rdi+0x3e4]` / `0x035EC979 cmp r12d,eax` / `0x035EC97C jge` | identical (CFG-anchored; a *linear* sweep at `0x035EC960` decodes garbage here) | PASS |
| `0x055B9063 mov dword [rbx+0x1678], 0xbf800000` (-1.0f) | identical | PASS |
| Loki `GetGravityZ 0x055AB8C0` / `NewFallVelocity 0x055B6AD0` are the `0x4C0` / `0x7A0` overrides | identical | PASS |
| the `CalcVelocity` bracket `mov [rdi+0xf8],r13` / `call [rax+0x7b0]` / `movsd [rdi+0xf8],xmm14` | identical at `0x035ECBD1 / 0x035ECBD8 / 0x035ECBDE` | PASS |

⇒ **Every load-bearing address, byte string and CFG count in L5 is CONFIRMED [M].** No transcription
defect found in 34 checks.

---

## 2. ★★★★★ REFUTED #1 — THE HEADLINE IS CONTRADICTED BY THE LANE'S OWN §4.2

L5 §0 states, **unconditionally and without a grade**:

> "`MaxInputSpeed < 1e-4` ⇒ **`Velocity` is written to exactly `(0,0,0)` every frame, whatever
> `Acceleration` is** … **That is a complete mechanical account of S139 flight 4**: `Acceleration =
> ControlInputVector x 50000` and `Velocity == (0,0,0)`."

**That account requires `MaxInputSpeed ≈ 0` in the TREATED (ARM G) state. It cannot have been.**
Proof, entirely from bytes I read plus one banked S139 measurement:

1. **[M, my read]** In `ULokiCMC::GetMaxAcceleration 0x055AC910`, `MovementMode == 3` routes to
   `0x055AC982`. The only exit from there that yields a non-zero value is
   `0x055AC9A0 call qword [rax+0xc00]` / `0x055AC9A6 xorps xmm1,xmm1` / `0x055AC9A9 ucomiss xmm0,xmm1`
   / **`0x055AC9AC jne 0x55ac9bc`** -> `0x055AC9C9 jmp 0x35e3ad0` (engine, returns `[CMC+0x28C]`).
   The fall-through is `0x055AC9AE xorps xmm0,xmm0 ... ret` = **0.0f**.
2. **[M, banked]** S139 flight 4 measured `Acceleration = ControlInputVector × 50000`, i.e.
   `GetMaxAcceleration()` returned **50000** on a `MOVE_Falling(3)` bot.
3. ⇒ **[M, derived]** the `jne` was taken ⇒ **`[Owner_vt+0xC00]()` returned NON-ZERO in flight 4**,
   and all three of `0x055AC9F0`'s zero-returning guards (`+0xF08` NULL, `0x055B18E0`, `[+0xB59]==0`)
   were passed.
4. **[M, my read]** `ULokiCMC::GetMaxSpeed 0x055ACB90` reaches the **same** slot on the **same** object
   behind the **same two** guards (`Owner = [rcx+0xb8]` non-null; class test `0x054F8C40`) and
   **tail-jumps** to it (`0x055ACBE6 jmp qword [rax+0xc00]`), returning its value directly.
   ⇒ **`GetMaxSpeed()` was NON-ZERO in flight 4.**
5. **[M, my read — a check L5 did not run]** `ComputeAnalogInputModifier` is **vtable disp `0x660` ->
   `0x035DB6F0`, and `ULokiCMC` does NOT override it** (loki == eng). Its body calls **disp `0x7D0`**
   (the *Loki* `GetMaxAcceleration`), tests `|Accel|^2 > 0` (`0x035DB731 comisd xmm3,xmm4 / jbe`) and
   `MaxAccel > 1e-8` (`0x035DB737 comiss xmm0,[.rdata 0x0769E370 = 9.99999993922529e-09] / jbe`), then
   returns `clamp(|Accel| * 1.0/MaxAccel, 0, 1)`. With `|Accel| ≈ MaxAccel ≈ 50000` this is **≈ 1.0**.

⇒ `MaxInputSpeed = max(GetMaxSpeed() × AnalogInputModifier, GetMinAnalogSpeed())` was **≫ 1e-4** in
flight 4 ⇒ **the clamp at `0x035D64F2` did NOT fire**, and it is **not** an account of flight 4.

**L5 already contains this refutation.** §4.5 P5/P6 say verbatim: *"≈ 500 ⇒ clamp does **not** fire"*
and *"**Velocity should be NON-ZERO**"*, and §4.5's ⚠ says *"§4 may already be **CLOSED** by ARM G"*.
**The headline was never corrected to match.** That is this project's second-named failure mode — a
digest carrying a claim nobody re-derived — occurring *inside one document, between §0 and §4.5*.

**Correct grade for the headline: [S], and its own analysis leans against it.**
The *mechanism* (§4.4, "with `MaxInputSpeed == 0`, `Velocity := (0,0,0)`") is **[M] and correct** — it
is only the **application to flight 4** that is refuted.

---

## 3. REFUTED #2 — §1.1's ATTRIBUTION IS NON-IDENTIFYING (and probably names the wrong function)

L5 §1.1 / correction #1: *"The `cmp byte [rcx+0x231], 7` the lead saw belongs to a **different
function** — `0x055ACB90`, which is `GetMaxSpeed`."*

**The refutation of Tier 1 is CONFIRMED [M]** — I read `0x055B89F0` and it opens
`mov [rsp+0x20],rbx / push rbp / push rsi / push rdi / lea rbp / sub rsp,0x2a0 / ...`, and
`docs/s140-tier1-cfg.md:622` does say *"its body opens `cmp byte [rcx+0x231], 7`"*. Tier 1 line 622 is
**REFUTED**.

**But the attribution is not evidence.** Byte-pattern census over the decrypted `.text`
(**unit: byte occurrences, not functions; FLOOR at 55.48 %**):

- `80 b9 31 02 00 00 07` (`cmp byte [rcx+0x231],7`) — **20 occurrences**
- `80 bb 31 02 00 00 07` (`rbx` form) — **27 occurrences**

At least **three** of the `rcx`-form hits are exactly **4 bytes into a `push reg / sub rsp,imm8`
prologue**, i.e. all three functions "open with" that compare in the sense Tier 1 used:

| entry | `cmp` site | what it is |
|---|---|---|
| `0x055ACB90` | `0x055ACB96` | `ULokiCMC::GetMaxSpeed` (vt disp `0x4C8`) — L5's candidate |
| `0x055AB8C0` | `0x055AB8CA` | `ULokiCMC::GetGravityZ` (vt disp `0x4C0`) |
| **`0x055B88E0`** | **`0x055B88E6`** | **`ULokiCMC::PhysCustom` (vt disp `0x990`) — the OTHER Loki `Phys*` override** |

`0x055B88E0` opens `push rbx / sub rsp,0x20 / cmp byte [rcx+0x231], 7 / mov rbx,rcx / jne ...` — the
*identical* three-instruction shape as `GetMaxSpeed`, **and it is a `Phys*` slot**. A lead hunting the
`PhysFalling` slot is far likelier to have landed on the sibling `Phys*` override than on a speed
getter three hundred slots away.

⇒ **Grade L5's attribution [S] and non-identifying.** This is the project's own "a folded/ambient RVA
names nothing" error class, transposed to a byte pattern. **The refutation stands; the story attached
to it does not.**

---

## 4. REFUTED #3 — §7's SELF-AUDIT IS EXACTLY BACKWARDS

L5 §7 closes: *"no **mutable global's value** is load-bearing in this file. The `.data` addresses cited
(`0x099C86A0`, `0x099C86B0`, `0x09F85E68`) are used as **addresses**, not values."*

**False.** §4.4's and §1.5's entire conclusion — `*** Velocity.XY := 0 ***` / `*** Velocity.Z := 0 ***`
— is true **only if** `[.data 0x099C86A0]` and `[.data 0x099C86B0]` are zero. `0x035D6511 movups xmm1,
[rip -> 0x099C86A0]` and `0x035D6518 movsd xmm2, [rip -> 0x099C86B0]` load **values**, and
`0x035D6520/27` store those values into `Velocity`.

I read them: **`0x099C86A0` = 24 bytes `00`, i.e. `(0.0, 0.0, 0.0)`; `0x099C86B0` = `0.0`** (its
following qwords are `1.0, 1.0`, so `FVector::ZeroVector` spans `0x099C86A0..0x099C86B7` and
`OneVector` follows). **The conclusion is SOUND** — but the *disclaimer* is wrong, and it is the kind
of wrong that tells a successor not to re-verify a value read. `merged13` is `.text`-only merged so its
`.data` is one coherent seed, which is why this is harmless here and would not be in a `-wholeimage`
merge.

⇒ **Verdict: the finding CONFIRMED, the self-audit REFUTED.**

---

## 5. REFUTED #4 — "THE ONLY KNOWN SINGLE VALUE THAT CLOSES BOTH PHENOMENA"

L5 §2 / correction #9 / §5 row 1: `CMC+0x3E4 MaxSimulationIterations` is *"the only known single value
that closes both phenomena"* (no velocity **and** no falling), and is therefore raised to joint-first.

**Trivially false as stated.** Every gate on engine `StartNewPhysics` closes both, because
`CalcVelocity` and the gravity integrator are **both** reached only *through* `PhysFalling`, which is
reached only *through* `StartNewPhysics`. My sound backward reachability from the dispatch
(`0x03600A95 jmp rcx`) gives **exactly five** exit edges — so there are at least four single values
with the same property:

```
0x036009AF jb  -> deltaTime < MIN_TICK_TIME
0x036009BC jge -> Iterations >= [CMC+0x3E4]        (L5's candidate)
0x036009CD je  -> HasValidData() == false          (vt disp 0x6B8, a THIRD one on this path)
0x036009EC je  -> fallthrough = IsSimulatingPhysics() TRUE
0x03600A7E ja  -> MovementMode > 7
```

plus Tier 1's newly-flagged `CMC+0xC0 WorldPrivate`, and `CMC+0x3E0 MaxSimulationTimeStep` (L5's own
row 6). `+0x3E4` remains a **good, free, unread** candidate — the *ranking* is fine. The **uniqueness
claim is [S] and wrong**, and it is what L5 used to promote the row to joint-first.

⚠ L5 also says `+0x3E4` *"skips `PhysFalling`'s loop at `0x035EC97C`"* as a second, corroborating
consequence. It is not corroboration — if `StartNewPhysics` already bailed at `0x036009BC`,
`PhysFalling` is never entered, so the second site is unreachable, not additive.

---

## 6. DOWNGRADES (claim survives, grade or form does not)

**D1 — §2's "Engine `StartNewPhysics` early-outs, complete [M]" is a SET MISMATCH.** My exit-edge
enumeration (above) is the sound version. L5's five-row list **includes `0x036009EE cmp byte
[.data 0x09F85E68], 5 / jb`**, which is **not in the backward-reachable set at all** — it sits
*downstream* of the `IsSimulatingPhysics` exit and is a log-suppression branch, not a gate on reaching
the dispatch — and **omits `0x03600A7E ja 0x3600b35`** (which L5 puts in §3 instead). The counts
coincidentally both read 5. **Read literally, L5's row 5 says `StartNewPhysics` bails whenever
`LogCharacterMovement` verbosity < 5** — which would mean it bails every frame. L5 knew better (§5's
"do NOT pin" row says the line fires only when `IsSimulatingPhysics()` is TRUE); the §2 list does not
say so. **Downgrade "complete [M]" -> "complete for the bail paths, but not the gate set."**

**D2 — the `ALokiCharacter` vtable identity is [I], inherited, not re-derived.** L5 writes
"`ALokiCharacter` vtable `+0xC00` -> `0x055AC9F0` (Tier 1 §4.6 already identified this vtable)". I found
by exhaustive `.rdata` qword scan that **exactly 2** vtables carry that VA, at `0x088E68A8` and
`0x089F9750` — i.e. **two classes**, not "the vtable" (singular), and **neither class NAME was verified
by L5 or by me.** The mechanism is unaffected (both implied vtable starts have `+0x0 -> .text` and
`+0x8 -> 0x00F7EC20`, a plausible UObject shape). **Grade [I].**

**D3 — §4.5 P1 ignores two of the three zero-returning guards.** P1 predicts the treated value is
"**500.0** (× the `[+0x16F0]` modifier stack; empty ⇒ ×1)". `0x055AC9F0` has **three** zero exits
(`+0xF08` NULL, `0x055B18E0(this)` true, `[+0xB59] == 0`), and P1 conditions only on the first. *In
this case the prediction is rescued by §2 above* (flight 4's 50000 proves all three were passed) — but
that argument is mine, not L5's, and as written P1 is [S], not a derivation.

**D4 — §4.3's "Early-outs, byte-exact, all four stock" drops a hop.** The real sequence is
`0x035D5D7C mov rax,[rbx+0x198]` / `0x035D5D83 test rax,rax` / **`0x035D5D86 je 0x35d5d9e`** (skip)
before the `Role` compare. L5's listing omits the `CharacterOwner` null check. Cosmetic — `Role == 3`
is measured, so the block is moot either way.

**D5 — §2's callee table UNDER-ENUMERATES two rows.** Engine `PhysFalling` has **four**
`call [rax+0x7B0]` (`CalcVelocity`) sites — `0x035ECB75`, `0x035ECBD8`, **`0x035ED549`**,
**`0x035ED5D5`** — where L5 lists two; and **three** `call [rax+0x7A0]` (`NewFallVelocity`) sites —
`0x035ECCEF`, **`0x035ED617`**, plus the one L5 names — where L5 lists one. Not load-bearing for the
mechanism, but it matters to "the wall is **one** compare against `1.0e-4`": the clamp is evaluated up
to four times per `PhysFalling` invocation.

**D6 — "23/23 REAL" rests on a WEAK two-state grade.** L5's control table grades REAL as "page
non-zero + not one of the five known folds". CLAUDE.md's own S137 lesson is that a page can be lit by a
neighbour `0xB0` away, and its S138 lesson is that a *sixth* stub shape grades REAL under a two-state
test. I re-ran both of L5's checks (0 fold-shape matches, 0 sixth-shape matches) **and added one L5 did
not**: none of the 23 has all-zero entry bytes. Still **not** "verified real code" for any of them.
State the grade as *"lit and not a known fold"*, not REAL.

---

## 7. NEW FACTS AND CONTROLS L5 DID NOT RUN

**N1 ★ — a control for §4.4's biggest attribution risk, and it PASSES.** L5 warns that *"two nearly
identical clamp blocks exist in this function; quoting the wrong one changes which variable is on
trial"* and says it read the wrong one first. It never proved it had the right one. I did:
**`preds(0x035D6511) = { 0x035D650F }` — exactly one predecessor**, the `jae` under
`0x035D64F2 comisd xmm8, xmm9`. ⇒ **the `ZeroVector` store at `0x035D6520` is uniquely reached from the
INPUT clamp.** The *requested* clamp has its own, separate pair (`0x035D668E comisd xmm7,xmm9` ->
`0x035D66A5/AC`). L5's attribution is now proven, not asserted.

**N2 ★ — `ComputeAnalogInputModifier` is vt disp `0x660` -> `0x035DB6F0`, and `ULokiCMC` does NOT
override it.** L5 asserts its stock semantics without ever locating or grading it. It is stock, and it
calls **disp `0x7D0`** — i.e. the **Loki** `GetMaxAcceleration`. Threshold constant
`.rdata 0x0769E370 = 9.99999993922529e-09` (1e-8 as f32), confirming L5's prose. **This is what makes
P4 well-founded — and is the same fact that refutes the headline (§2 above).**

**N3 ★ — `ControlledCharacterMove` IS Loki-overridden and L5 never checked.** `ULokiCMC` vt disp
`0x890` -> **`0x055A7680`** (engine `0x035DCD10`). The override (132 ins) **does** call the engine impl
and has **zero** stores to `+0x3D0` (classified by `operands[0].type == MEM`). ⇒ L5 correction #7
("its only `+0x3D0` store") **survives** — but it was made without checking the override that actually
runs on a `ULokiCMC`. Control passes; the lane got lucky.

**N4 ★ — the `Acceleration` -> `AnalogInputModifier` ordering is confirmed exactly.**
`0x035DCD6B movups [rsi+0x328], xmm0` (Acceleration) ... `0x035DCD82 call qword [rax+0x660]`
(ComputeAnalogInputModifier) ... `0x035DCD8F movss [rsi+0x3d0], xmm0`. Delta = **0x24 = 36 bytes**, same
function, same frame — exactly as L5's §4.5 ordering note claims.

**N5 — `CalcVelocity` writes `Velocity` at 15 distinct sites** (`operands[0].type == MEM`, disps
`0xE8/0xF0/0xF8`), of which **five** are `ZeroVector` pairs (`0x035D5E0F`, `0x035D620A`, `0x035D62E0`,
`0x035D6511`, `0x035D66A5`) and two (`0x035D65B0`, `0x035D6720`) are **identity copies** (load
`[rbx+0xe8]`, store it back). L5's §4.4 "two clamp blocks" framing understates the count; N1 shows the
attribution is nonetheless right.

**N6 — Loki `PhysFalling` has THREE `movups [rbx+0xe8]` stores**, not one: `0x055B8FBE` (the zeroing
one — preceded by `xorps xmm1,xmm1`, a **register** zero, not `.data`), `0x055B9032` (a computed
*scale*), `0x055B9052` (an **identity copy**). L5 quoted only the first and wrote "why **neither**
fires". The enumeration turns out complete; **it was never shown to be.**

**N7 ⚠ MY OWN INSTRUMENT ARTIFACT, recorded.** I resolved every `call [rax+disp]` in engine
`PhysFalling` against the **CMC** vtables. That is only valid where `rax = [rdi]` and `rdi` is the CMC.
For `0x035ECCC6 call [rax+0x970]` L5 says the receiver is `CharacterOwner` (`CheckJumpInput`); my
resolver reports `PhysWalking 0x035EF960` because I used the wrong hierarchy — **exactly the trap L5
itself names for the two `+0x4C0`s.** L5's row is right and my resolution of it is void. *A
displacement resolved against an unverified receiver names nothing.*

**N8 — a linear sweep decodes garbage in engine `PhysFalling`.** Starting a linear disassembly at
`0x035EC960` yields `add byte [rax+0x85885], cl` and a `hlt`; the CFG-anchored stream gives the real
`0x035EC967 mov eax,[rdi+0x3e4]`. L5's quoted bytes are right; **anyone re-checking them with a linear
sweep will conclude they do not exist.** (Same class as S140's recorded "a linear sweep is not a CFG".)

---

## 8. QUESTIONS I WAS ASKED, ANSWERED DIRECTLY

- **Does every negative have a positive control that could have failed?** Mostly yes. L5's §0 control
  table is genuinely two-sided (the engine-vtable row is the discriminating half, and the
  `+0x820/+0x828/+0x838/+0x840` neighbours could have differed and did not). **The exception is §4.4's
  attribution**, which had *no* control until N1. And L5's `.text`-floor disclaimer is stated but never
  operationalised — no census in the file is quantified as a floor with a number.
- **Is any control CIRCULAR?** No control in L5 is selected by the property it then reports. The
  closest is grading targets "REAL by page non-zero" — not circular, but weak (D6).
- **Is anything graded [M] whose support is an inference across a function boundary / a non-identifying
  address / a dark-page census?** **Yes, three:** the headline (inference across the ARM-G arm
  boundary, §2); §1.1's attribution (**non-identifying byte pattern, ≥20 occurrences**, §3); and
  correction #9's uniqueness claim (§5). D2 adds an inherited [I] stated flatly.
- **Did the lane classify writes from `regs_access`?** **No.** L5 explicitly states it used
  `operands[0].type == MEM` and its quoted `movups [rbx+0xe8], xmm1` stores are precisely the ones a
  `CS_AC_WRITE` filter drops — the correct check, correctly stated. I reproduced its write set with an
  independent `operands[0].type == MEM` classifier and found L5's stores present and correct (plus the
  extra sites in N5/N6 it did not enumerate).
- **Counts quoted without their UNIT?** A few. "20 occurrences" here = **byte occurrences in the
  decrypted `.text`**, not functions. L5's "**25 / 23**" for `PhysFalling` correctly separates *sites*
  from *distinct targets*; its "**36 direct call sites / 13 distinct targets**" likewise. But
  correction #7's *"its only `+0x3D0` store"* does not say whose scope "its" is (it is: within engine
  `ControlledCharacterMove`; N3 extends it to the Loki override), and §1.2's "23/23 REAL" quotes a
  grade whose unit is *pages*, not code (D6).

---

## 9. WHAT SURVIVES AND SHOULD BE CARRIED FORWARD

1. **[M]** `ULokiCMC::PhysFalling 0x055B89F0` calls the engine Super **unconditionally**
   (|R| = 14, entry in R, exit edges empty). Tier 1 line 622 is **REFUTED**.
2. **[M]** `CalcVelocity` is vt disp `0x7B0 = 0x035D5D20` and **is not overridden by `ULokiCMC`**.
3. **[M]** `GetMaxSpeed` (disp `0x4C8`) and `GetMaxAcceleration` (disp `0x7D0`) are **both GAS-backed
   through the same `+0xC00` slot** (`0x055AC9F0`), which returns `0.0f` when
   `Character+0xF08 == NULL`; base value is `min(AttrSet+0xF0+0xC, AttrSet+0x100+0xC)`.
4. **[M]** The input clamp exists and is `comisd` vs `.rdata 0x076B49E8 = 9.999999747378752e-05`, with
   the `ZeroVector` store at `0x035D6520` **uniquely** reached from it (N1).
5. **[M, derived]** **In S139 flight 4 the `+0xC00` slot returned NON-ZERO**, so `GetMaxSpeed() != 0`,
   so **the clamp did not fire.** ⇒ **§4 is already CLOSED by ARM G, and flight 4's null points
   upstream — at the step not running.** This is L5's own P4/P6 promoted from prediction to derivation,
   and it makes L5's §5 row 2 (`CMC+0x3D0` on a treated bot) a **confirmation read, not a
   discriminator**, and row 1 (`CMC+0x3E4`) **and the other four `StartNewPhysics` gates** the actual
   open question.
6. ⇒ **My ranking differs from L5's:** the free reads that matter are `CMC+0x3E4`, `CMC+0x3E0`,
   `CMC+0xC0` and the `HasValidData` inputs — i.e. **the `StartNewPhysics` gate set** — not the
   `CalcVelocity` terms. L5's own analysis supports this; its headline does not.

**Harness:** `<scratchpad>/v5/vpe.py`, read-only, offline, re-runnable. All `.rdata`/`.data` reads are
from `merged13`; **two `.data` VALUES are load-bearing above** (`0x099C86A0`, `0x099C86B0`, both read
as `0.0`) and I say so rather than claiming otherwise.
