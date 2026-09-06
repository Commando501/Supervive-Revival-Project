## Trace of 0x56A5370 (auto-fire branch target)

### 1. Full function extent

Three chained `.pdata` rows form ONE function:

| RVA range | size | UNWIND |
|---|---|---|
| 0x56A5370 – 0x56A539B | 43 B | 0x94DF3A4 |
| 0x56A539B – 0x56A555A | 447 B | 0x9809148 |
| 0x56A555A – 0x56A5565 | 11 B | 0x980915C |

**Total: 0x56A5370 – 0x56A5565 = 501 B, terminates in `ret` at `0x56A5564`.** (Image base derived from disasm = `0x7FF608F40000`.)

### 2. VERDICT: does it broadcast `OnGameplaySpellEnded`?

**MEASURED: NO.** This is not a delegate/broadcast function. It is a **physics / target-position updater on the state-tracker object**. Evidence:

- Reads two `double`s from `rdx` (the caller's `pointer-to-two-doubles`), treats them as a 2-D vector, computes `|v|` and `|v|²`.
- Compares `|v|` to a threshold `[this + 0xB48]` (single-precision).
- On the small-distance path it writes:
  - `[this+0xB88]/[this+0xB90]` (2 doubles) — a live 2-D position
  - `[this+0xB98]/[this+0xBA0]` (2 doubles) — a snapshot/second point
  - `[this+0xBB8]/[this+0xBB9]/[this+0xBBA]` — three state bytes
  - `[this+0xBBC]` — a float populated from `[world+0x808]` (via `call [r8+0x380]`)
- The only indirect call `call qword [r8 + 0x380]` reads world state into `[rsp+0x20/0x28]`; it is NOT a delegate broadcast (no `Broadcast` prologue, no `FMulticastScriptDelegate` walk, no invocation-list iteration, no `[asc+delegate_offset]`, no ProcessEvent dispatch).
- Zero references to `[this+0xBEC]/0xBF4/0xBFC/0xC0C` (the S153 auto-fire state-tracker offsets are NOT touched). The offsets it uses (`0xB48/0xB88..0xBBC`) sit in a **lower band on the same object** — this is a sibling subsystem of the state tracker, not the tracker itself.

⇒ **Not a WALL P block.** Auto-fire's downstream is not reached through this function.

### 3. Fold-tail-call

**None.** Direct-call targets:

| callee RVA | pdata row | fold? |
|---|---|---|
| 0x338C990 | 136 B REAL | no |
| 0x569FE70 | 109 B REAL | no |
| 0x567EB90 | **1386 B REAL** (called twice) | no |
| 0x424E650 | (no pdata row — DARK-candidate) | no |
| 0x5695B50 | 111 B REAL | no |
| 0x423BF70 | (no pdata row — DARK-candidate) | no |
| `[r8+0x380]` indirect vtable call | — | (world/actor slot, not delegate) |

None match the five folds (`0xF7EC20 / 0xF7EB50 / 0xF7EB60 / 0xB9E1F0 / 0xFC6CF0`).

### 4. Downstream chain summary

Function is a **CalcAndCommit2DTargetPosition-style helper** on the state tracker, invoked by the four auto-fire sibling handlers to snap/threshold a target vector and store it plus a world-time float. It composes 6 REAL direct callees + one indirect vtable call reading a world-state float; no delegate broadcast, no fold tail-call, no touch of the S153 auto-fire tracker offsets.

**Implication for WALL P:** the "auto-fire branches call `0x56A5370`" edge is a shared **target-vector commit**, not an ability-lifecycle broadcast. The `OnGameplaySpellEnded` fan-out (if it exists on this path) must live in one of the sibling handlers themselves or in another callee, not here. Recommend re-tracing the sibling handlers past their call to `0x56A5370` — the broadcast is downstream of *that* call, not inside it.