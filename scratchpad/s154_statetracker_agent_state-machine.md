I have the access map. Building the state-machine model from the 4 auto-fire consumers (0x5679D50/DF7/E80/F2C), the two small setters (0x5679E60/F98) and two probes (0x5679DD0/F00), the BEGIN fn 0x5515C55, the tick/init fn 0x56777B0, and the terminator at 0x5525360.

**Byte-role reclassification:** `[+0xC0D]` is the master authority gate — checked by ALL 4 consumers, written only by BEGIN (0x5515D48) and cleared by the terminator (0x5525360). `[+0xBEC]` is a re-entrancy LATCH inside handlers DF7/F2C (set 1 on entry at 0x5679E1A/F52, cleared 0 on exit at 0x5679E53/F8B), not a phase. That leaves four true phase bytes: `0xBFC`, `0xBF4`, `0xC04`, `0xC0C`.

**Consumer bodies (verified against the access map):**
- `0x5679D50` — gate BFC (0x5679D56 cmp!=0), predicate C0D (0x5679D62), read BF8 (0x5679D6B), clear BFC=0 (0x5679D74), advance BF4=1 (0x5679DB8).
- `0x5679E80` — gate BF4 (0x5679E86 cmp!=0), predicate C0D (0x5679E92), clear BFC=0 & BF4=0, read BF8 (0x5679EE5), re-arm BFC=1 (0x5679EEB). Cyclic back-edge.
- `0x5679DF7` — LATCH BEC=1, predicate C0D, clear C0C=0 (0x5679E28) & C04=0 (0x5679E2F), release BEC=0. Called after probe 0x5679DD0 (cmp C0C!=0).
- `0x5679F2C` — LATCH BEC=1, predicate C0D, clear C0C=0 (0x5679F60) & C04=0 (0x5679F67), release BEC=0. Called after probe 0x5679F00 (cmp C04!=0).

**Setters:** `0x5679E60` (0x5679E68 WRITE C04=1), `0x5679F98` (0x5679FA0 WRITE C0C=1). These are the external "advance to Invoke/Cooldown" triggers.

**Initiator [M]:** fn 0x56777B0..0x5677EE2 (0x732 B) — the tick/init — writes FIVE bytes in one pass: BEC, BF4, BF8, BFC, C04 (0x5677A32/BDE/BE4/BEA/BF6). Missing C0C + C0D confirms it's a state-machine RESETTER, not the authority-writer. BEGIN 0x5515C55 owns C0D; setter 0x5679F98 owns C0C.

**State-machine table (educated guess mapping):**

| Phase (my guess) | Active byte | Initiator | Handler | Timing float | Fires auto-broadcast? |
|---|---|---|---|---|---|
| **Warmup** | `0xBFC` | 0x56777B0 init / 0x5679EEB re-arm | **0x5679D50** | `0xBF8` (0x5679D6B) | via 0x5679D50 → advance to BF4 |
| **Channel** | `0xBF4` | 0x5679DB8 (from Warmup) / 0x56777B0 init | **0x5679E80** | `0xBF8` (0x5679EE5) | via 0x5679E80 → cyclic back to BFC |
| **Invoke** | `0xC04` | **0x5679E60/E68 setter** / 0x56777B0 init | **0x5679F2C** (via probe 0x5679F00) | — | clears both C04+C0C |
| **Cooldown** | `0xC0C` | **0x5679F98/FA0 setter** | **0x5679DF7** (via probe 0x5679DD0) | — | clears both C04+C0C |

**Basis for Warmup↔Channel = BFC↔BF4:** they share the timing float 0xBF8 (only 0xBFC/BF4 handlers touch it), they form the earliest oscillating pair in address order, and init 0x56777B0 preloads both (spell begins with Warmup preloaded). Handler-0x5679E80's cyclic back-write BFC=1 is consistent with Channel-completion re-triggering next tick, which matches UE `FSpellCastingStateSpecification` where Warmup/Channel are the paced sub-phases with per-tick fire-schedule state.

**Basis for Invoke=C04 / Cooldown=C0C:** these are one-shot latches (small setters flip them, consumers clear BOTH). Invoke fires first (per FSpellCastingStateSpecification field order), and 0x5679E60 (setter for C04) sits at a LOWER address than 0x5679F98 (setter for C0C) — matching Invoke-before-Cooldown call order. The BEC re-entrancy latch wraps only the C04/C0C consumers, consistent with Invoke/Cooldown fire-once semantics that must be idempotent under re-entrant tick.

**Untested prediction:** `0x5679E60` invoked externally with authority set (C0D=1) drives an Invoke fire; `0x5679F98` drives a Cooldown fire. Both go through 0x56A5370 auto-broadcast per S153's finding since the consumers gate on C0D==0 to permit it.