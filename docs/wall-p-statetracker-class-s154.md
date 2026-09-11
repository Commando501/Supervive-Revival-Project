# WALL P state-tracker class + semantic map (S154, 2026-09-02)

Follow-up on the S153 auto-fire mechanism hunt. Identifies the class of the
subobject at `[validated_object + 0x400]` that receives the propagated
`bManuallyCallSpellCompleteEvent` flag, and maps its state-byte layout.
Uses a 4-angle workflow (`wf_4b66ad0b-994`, 5/5 agents done, 1.5M subagent
tokens, 8.7 min wall) with adversarial verification against CLAUDE.md's
own documented offsets.

**Bottom line:** the state-tracker is `ALokiPlayerController` (MEASURED via
vtable-identity + cross-check against CLAUDE.md's `[pawn+0x400]=Controller`
finding). The 8 state bytes decompose into 4 phases (Warmup/Channel/Invoke/
Cooldown), 1 authority gate, 1 re-entrancy latch, and 2 timing floats.
`0x56A5370` (previously called "the auto-fire broadcast") is NOT a broadcast
— it's a 2-D target-vector commit helper. **The actual `OnGameplaySpellEnded`
broadcast lives downstream inside the 4 sibling handlers, not inside
`0x56A5370`. WALL P's block relocates again.**

## Class identification: `ALokiPlayerController` [MEASURED]

Two independent evidence lines converge:

**(1) Vtable identity (Angle 0):** The tick/init function at `0x56777B0`
opens with `call 0x559790` (base ctor) then `lea rax, [rip + 0x33a36f6]` →
vtable RVA **`0x8A1AEE0`** stored at `[rdi+0]`. That exact RVA is what
`tools/sigbypass-mod/tutorial_launch.cpp:23624` reads live from
`Default__BP_LokiPlayerController_Dev_C`'s CDO across 30+ stage markers
recorded over months (`docs/fk24-stage-*-gft.txt`: `lokiCDO=... (vt rva
0x8A1AEE0)`), against the stock `Default__PlayerController` vt at
`0x81A82F8`. BP classes inherit the C++ base's vtable ⇒ **the C++ class
whose ctor writes `0x8A1AEE0` is `ALokiPlayerController`**.

**(2) Chain evidence (Angle 3 reinterpreted):** The BEGIN function `0x5515C55`
computes `r14 = [validated_object + 0x400]`. Per CLAUDE.md lines 1225/1282/
1339 (S135/S136 disassembly of `APawn::SpawnDefaultController`), **`[APawn +
0x400] = APawn::Controller`** — literally stated as `cmp qword [rcx+0x400],0
/ jne` in the pawn's ctor-controller-check. Since `validated_object` was
gated as `IsChildOfUsingStructArray("LokiHeroCharacter")` (a pawn), the
`[+0x400]` deref lands on the pawn's Controller — which for a Loki hero is
a `BP_LokiPlayerController_Dev_C` instance whose C++ base is
`ALokiPlayerController`.

**⚠ SYNTHESIZER'S "CMC" VERDICT WAS INCORRECT.** The workflow synthesizer
picked `ULokiCharacterMovementComponent` based on Angle 3's citation of
`docs/symbols.csv:515` labeling `0x5512380` as a "LokiCharacterMovementComp
onent helper". Verified: that row is real, but the label carries confidence
`LOW` and the evidence field reads `NO-NAME-EVIDENCE`; `0x5512380`'s error
string is `"Mismatch NumStructBasesInChainMinusOne"` = a **GENERIC** UE
`IsChildOfUsingStructArray` diagnostic, not CMC-specific. Multi-agent
workflows can produce over-confident synthesis; per R-S153-g, this session
demonstrated the same failure mode (verify synthesizer conclusions against
CLAUDE.md's own documented facts before believing them).

**Anti-candidates ruled out:**
- Stock `APlayerController` — vtable is `0x81A82F8`, not `0x8A1AEE0`
- `ALokiBotController` — different vtable (S137 measured `ALokiBotController::OnPossess 0x5565470`)
- `ALokiHeroCharacter` — this is the *pawn* validated as `validated_object`, not `[+0x400]`
- A UActorComponent subobject — vtable installed by the ctor is bound to the CDO's `+0` position, not any component slot

## State-machine table

Re-classified from Angle 1's byte-role analysis. `+0xC0D` is the master
**authority gate** (checked by ALL 4 consumers as a predicate; written only
by BEGIN `0x5515D48` from spell's `+0xC76`, cleared by terminator
`0x5525360`). `+0xBEC` is a **re-entrancy latch** (set on entry to Invoke/
Cooldown handlers, cleared on exit). That leaves 4 true phase bytes:

| Phase (guess) | Byte | Owned by | Timing float | Notes |
|---|---|---|---|---|
| **Warmup** | `0xBFC` | Handler `0x5679D50` | `0xBF8` | Init preloads; advance sets `0xBF4=1` |
| **Channel** | `0xBF4` | Handler `0x5679E80` | `0xBF8` | Cyclic back-write `0xBFC=1` on completion |
| **Invoke** | `0xC04` | Handler `0x5679F2C` (probe `0x5679F00`) | — | One-shot; setter `0x5679E60` writes `C04=1` |
| **Cooldown** | `0xC0C` | Handler `0x5679DF7` (probe `0x5679DD0`) | — | One-shot; setter `0x5679F98` writes `C0C=1` |

| Support | Byte | Role |
|---|---|---|
| **Auth gate** | `0xC0D` | ALL 4 handlers predicate on `[+0xC0D] == 0` for auto-fire. Written by BEGIN and terminator only. |
| **Reentry latch** | `0xBEC` | Wraps only Invoke/Cooldown handlers (`0x5679DF7`, `0x5679F2C`). Set 1 on entry (`+0xE1A/+0xF52`), cleared 0 on exit (`+0xE53/+0xF8B`). Idempotent-fire discipline. |
| **Timing A** | `0xBF8` | Shared pace timer for Warmup+Channel (only their handlers read it) |
| **Timing B** | `0xBF0` | Init-only in `0x56777B0`; secondary timer, un-consumed by observed handlers |

Init `0x56777B0` preloads BEC/BF4/BF8/BFC/C04 in one pass — a state
**RESETTER**, not the authority-writer. BEGIN (`0x5515C55`) owns `0xC0D`;
setters `0x5679E60`/`0x5679F98` own `0xC04`/`0xC0C`. **The tick/init
function that writes multiple state bytes but MISSES the master gate byte
is a resetter, not the owner (R-S154-a).**

## Auto-fire broadcast verdict [MEASURED]

**`0x56A5370` does NOT broadcast `OnGameplaySpellEnded`.** Angle 2's full
trace: chained `.pdata` extends the function to `0x56A5370..0x56A5564`
(501 B across 3 rows). It's a **2-D target-vector commit helper** — reads
two doubles from `rdx`, thresholds `|v|` vs `[this+0xB48]`, commits to
`[this+0xB88..0xBBC]`, reads a world-time float via indirect `[r8+0x380]`.
**Zero references** to state-tracker offsets (`0xBEC`/`0xBF4`/`0xBFC`/`0xC0C`)
inside its 501 B — different subsystem on the same object.

**No fold tail-call.** All 6 direct callees (`0x338C990`, `0x569FE70`,
`0x567EB90`, `0x424E650`, `0x5695B50`, `0x423BF70`) are REAL; none match the
5 known folds.

**⇒ WALL P block relocates AGAIN.** The `OnGameplaySpellEnded` broadcast is
downstream of `0x56A5370` **within its sibling handlers** — i.e. the 4
sibling handlers do MORE than just call `0x56A5370`; they presumably also
broadcast the delegate somewhere in the tail. Re-tracing `0x5679DF7` and
`0x5679F2C` past their `call 0x56A5370` is the next offline task.

## Fourth WALL P relocation this session

Session progression:
1. **Cross-index (workflow-1)** — "CallSpellCompleteEvent is stripped, the block" [proposed]
2. **Deep dive** — refuted for MiniDash specifically; 96% of spells use auto-fire
3. **Auto-fire hunt** — auto-fire mechanism is REAL; block at state-byte layer
4. **State-tracker profile (workflow-2, this doc)** — class is `ALokiPlayerController`; `0x56A5370` is NOT the broadcast — block is downstream of it within the sibling handlers

Each relocation moves the search space one hop deeper, and every one so far
has been offline-decisive. **The block is now known to be either:**
- (a) In the tail of the 4 sibling handlers (post `call 0x56A5370`)
- (b) A downstream callee of `0x56A5370`'s 6 callees (all REAL, some unread)
- (c) The propagation itself failed (`[Controller+0xC0D]` never got the value)

## Updated live-read preregistration for the next MiniDash session

**Target subobject:** `pawn->Controller` = `[pawn + 0x400]` = an
`ALokiPlayerController` instance (verified vtable `0x8A1AEE0`).

**RPM probe design** (read-only, no injection):
```
target: pawn->Controller       ; where pawn is the possessed hero
class:  ALokiPlayerController   ; [MEASURED via vtable 0x8A1AEE0]

reads (byte-precise from access map):
  pc+0xBEC (u8)   reentry_latch       — MUST be 0 outside handler entry
  pc+0xBF0 (f32)  timing_B            — secondary timer
  pc+0xBF4 (u8)   phase_channel       — 1 = in Channel
  pc+0xBF8 (f32)  timing_A_shared     — Warmup/Channel pace timer
  pc+0xBFC (u8)   phase_warmup        — 1 = in Warmup
  pc+0xC04 (u8)   phase_invoke        — 1 = Invoke pending
  pc+0xC0C (u8)   phase_cooldown      — 1 = Cooldown pending
  pc+0xC0D (u8)   authority_gate      — MUST be 1 for handlers to advance
```

**Sanity gates BEFORE trusting the reads:**
1. Verify `[pc + 0]` == vtable VA `IMAGE_BASE + 0x8A1AEE0`. If not, `[pawn+0x400]`
   deref went somewhere unexpected — DO NOT trust the byte reads.
2. Verify at least one of `[pc+0xBFC]`/`[pc+0xBF4]`/`[pc+0xC04]`/`[pc+0xC0C]`
   is non-zero at cast-start. If all four are zero, the state machine never
   initialized — block is upstream of `0x5515C55`.

**Discriminator table:**

| observation post-cast | verdict | next investigation |
|---|---|---|
| `[+0xC0D] == 0` (auth gate unset) | **Propagation failed.** BEGIN `0x5515C55`'s 4-gate validation refused MiniDash's chain. | Instrument the 4 gates (`0x44556A0`, `0x4453EC0`, `0x54F8DC0`, `0x5512380`) — find the rejecter. |
| `[+0xC0D] == 1` and `[+0xBFC]/[+0xBF4]/[+0xC04]/[+0xC0C]` all zero | **Auth gate open but no phase active.** State machine idle. Handlers can never fire without a phase to consume. | Look at where phases get set — Warmup `[+0xBFC]=1` is set by BEGIN or by Channel handler's cyclic back-write. |
| `[+0xC0D] == 1`, a phase byte was 1 and is now 0 (cleared post-cast) | **Handler fired but no visible completion.** Either `0x56A5370` did its geometric commit and the delegate broadcast (post-`0x56A5370` in the handler) is stripped/blocked. | Disassemble the 4 handler tails past their `call 0x56A5370` — find the delegate broadcast site. |
| `[+0xC0D] == 1`, phase byte still 1 (never cleared) | **Handler never fired.** State-active but consumer path not reached. | Handler entry has an internal `cmp [phase],0; je exit` — the phase must be non-zero AT the call site. Something is calling the handlers speculatively. |

## Reusable rules banked

- **R-S154-a:** A tick/init function that writes multiple state bytes but MISSES
  the master authority byte is a state RESETTER, not the state owner. Find the
  writer of the MISSING byte — that's the BEGIN/authority owner.
- **R-S154-b:** `[pawn + 0x400]` is `APawn::Controller` in this build (per
  CLAUDE.md S135/S136 disassembly of `SpawnDefaultController`). Any deref-then-
  validate chain landing there is looking at the controller, not CMC or another
  component. Bank alongside `+0xF00` (ASC), `+0x3D0` (AIControllerClass), `+0x160`
  (ROLE_Authority) as this build's stable Character-family offsets.
- **R-S154-c:** A "broadcast" function must have one of: `FMulticastScriptDelegate`
  walk, invocation-list iteration, or a call to a delegate `Broadcast` helper.
  Absence of ALL THREE + presence of geometric arithmetic (`|v|` compare,
  coordinate stores) = compute helper, NOT delegate. Do not label an auto-fire
  branch target "broadcast" until one of those three shows.
- **R-S154-d:** When a byte is written by ALL consumers as a predicate but by
  ONLY the outermost function as a value, it's a gate, not a phase. Re-classify
  before building a state diagram.
- **R-S154-e:** Multi-agent workflow synthesizers can produce over-confident
  synthesis that reverses the correct verdict when adversarial verification
  is weak (a LOW-confidence label being cited as decisive). VERIFY every
  synthesizer verdict against CLAUDE.md's own documented facts before believing
  it. Demonstrated when this doc's workflow synthesizer chose "ULokiCMC" over
  "ALokiPlayerController" via a docs/symbols.csv row whose confidence was LOW
  and whose evidence field was NO-NAME-EVIDENCE. Corollary of R-S153-k.

## Files

- `scratchpad/s154_statetracker_enum.py` — the enumeration tool that produced the access map
- `scratchpad/s154_statetracker_access_map.md` — full 8-offset access map (205 functions)
- `scratchpad/s154_statetracker_access_map.csv` — machine-readable
- `scratchpad/s154_statetracker_agent_{class-id,state-machine,broadcast-downstream,size-alloc,synthesize}.md`
  — per-agent workflow findings preserved verbatim
- `docs/wall-p-callspellcomplete-deep-dive-s153.md` — the CallSpellCompleteEvent deep dive (parent doc)
- `docs/wall-p-autofire-mechanism-s153.md` — the auto-fire hunt (parent doc)
- `docs/next-session-prompt-s154.md` — the session handoff (this doc's live-read recipe should be integrated there)
