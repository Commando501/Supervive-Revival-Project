# S154 WALL P state-tracker profile (2026-09-02)

## Class identification

**Best candidate: `ULokiCharacterMovementComponent`** (confidence: **STRONG_INFER**, one measurement away from MEASURED).

Two angles converged via different signals:

- **Angle 3 (allocation/deref chain)**: the initiator `0x5515C55` does `r14 = GetAvatarActorFromActorInfo(spell)` (0x4453EC0, MEASURED via census tsv row 6749), then `r14 = [r14 + 0x400]`, then validates via `0x5512380` — which `docs/symbols.csv:515` explicitly labels as a `LokiCharacterMovementComponent` helper. The post-deref validator's type-gate forces `r14` to be a `ULokiCMC`.
- **Angle 3 size floor**: highest offset touched is `0xC0D` ⇒ minimum size `0xC10` (3,088 B), consistent with ULokiCMC's documented ~5.9 KB layout (`+0x12B0`, `+0x16B0`, `+0x16C8` already recorded).

**Angle 0's `ALokiPlayerController` guess is REFUTED by Angle 3's chain evidence.** Angle 0 anchored on the vtable RVA `0x8A1AEE0` in the *tick/init* function `0x56777B0`, but that function only RESETS the state bytes — it does not own the class. The initiator's own `+0x400`-deref-then-LokiCMC-validate sequence is the load-bearing signal, and PlayerController does not sit at `[avatar+0x400]`.

**One measurement upgrades to MEASURED**: walk `ULokiCharacterMovementComponent`'s `FClassParams->PropPointers[]` in the UHT registration table (S136 methodology, `docs/s136-ai-controller-settled.md` §7) and confirm UPROPERTY offsets `0xBEC..0xC0D` are declared there. `binds_members.csv` cannot answer this (no Offset column).

## State-machine table

Reclassified from Angle 1: `+0xC0D` is the master **authority gate** (not a phase); `+0xBEC` is a **re-entrancy latch** (not a phase). True phase bytes = 4.

| Phase | Byte | Owned by | Timing float | Notes |
|---|---|---|---|---|
| **Warmup** | `0xBFC` | Handler `0x5679D50` | `0xBF8` | Init preloads; advance sets `0xBF4=1` |
| **Channel** | `0xBF4` | Handler `0x5679E80` | `0xBF8` | Cyclic re-arm of `0xBFC=1` |
| **Invoke** | `0xC04` | Handler `0x5679F2C` (probe `0x5679F00`) | — | One-shot; setter `0x5679E60` |
| **Cooldown** | `0xC0C` | Handler `0x5679DF7` (probe `0x5679DD0`) | — | One-shot; setter `0x5679F98` |
| **Auth gate** | `0xC0D` | BEGIN `0x5515D48` / terminator `0x5525360` | — | ALL 4 handlers predicate on it |
| **Reentry latch** | `0xBEC` | Wraps Invoke/Cooldown handlers | — | Idempotent-fire discipline |
| **Timing A** | `0xBF8` | Read by Warmup+Channel | — | Shared pace timer (`0.3`/`0.7` ctor defaults candidate) |
| **Timing B** | `0xBF0` | (init-only in 0x56777B0) | — | Secondary timer, un-consumed by handlers seen |

Init `0x56777B0` preloads BEC/BF4/BF8/BFC/C04 in one pass — a state RESETTER, confirming BEGIN (`0x5515C55`) owns the authority write, not init.

## Auto-fire broadcast verdict

**Angle 2: MEASURED — `0x56A5370` does NOT broadcast `OnGameplaySpellEnded`.** It is a **2-D target-vector commit helper** (501 B, three chained pdata rows, terminates at `0x56A5564`): reads two doubles from `rdx`, thresholds `|v|` vs `[this+0xB48]`, commits to `[this+0xB88..0xBBC]`, reads a world-time float via indirect `[r8+0x380]`. **Zero references to `0xBEC/0xBF4/0xBFC/0xC0C`** — different subsystem on the same object.

**No fold tail-call**: all 6 direct callees are REAL (0x338C990, 0x569FE70, 0x567EB90, 0x424E650, 0x5695B50, 0x423BF70); none match the five known folds (`0xF7EC20/0xF7EB50/0xF7EB60/0xB9E1F0/0xFC6CF0`).

⇒ **WALL P block relocates AGAIN.** The `OnGameplaySpellEnded` broadcast is downstream of `0x56A5370` *within its sibling handlers*, not inside it. Re-trace 0x5679DF7 and 0x5679F2C past their `call 0x56A5370` — the broadcast lives there or in a subsequent callee.

## Updated live-read preregistration for S154's WALL P discriminator

**RPM probe design** (read-only, no injection):

```
target: pawn->Controller->Pawn->CharacterMovement (via APawn+0x400 deref chain)
class:  ULokiCharacterMovementComponent  [STRONG_INFER; upgrade via UHT PropPointers walk]

reads (all sizes byte-precise from access map):
  cmc+0xBEC (u8)  reentry_latch      — MUST be 0 outside handler entry
  cmc+0xBF0 (f32) timing_B           — secondary timer
  cmc+0xBF4 (u8)  phase_channel      — 1 = in Channel
  cmc+0xBF8 (f32) timing_A_shared    — Warmup/Channel pace timer
  cmc+0xBFC (u8)  phase_warmup       — 1 = in Warmup
  cmc+0xC04 (u8)  phase_invoke       — 1 = Invoke pending
  cmc+0xC0C (u8)  phase_cooldown     — 1 = Cooldown pending
  cmc+0xC0D (u8)  authority_gate     — MUST be 1 for handlers to advance

positive control: fire MiniDash via canonical input (s151 Move 3 recipe).
  predicted trace: authority_gate 0→1, phase_warmup 1, timing_A advances,
                   phase_channel 1, phase_invoke transiently 1, phase_cooldown 1.
negative control: gate MiniDash CanActivate=false. authority_gate stays 0;
                   phases inert.
```

If `authority_gate == 0` on a MiniDash activation attempt: **BEGIN `0x5515C55` was not reached** — the wall is upstream (activation refusal). If `authority_gate == 1` and phases never advance: **the initiator ran but handlers are gated** — the wall is on `0xC0D` propagation from spell.

## Confidence + gaps

**MEASURED**: state-byte access map, handler ownership, 0x56A5370 downstream (not a broadcast, no fold tail), authority-gate/re-entry-latch role split, `0x4453EC0 = GetAvatarActorFromActorInfo`.

**STRONG_INFER**: class = ULokiCMC (Angle 3 chain), Warmup=BFC / Channel=BF4 pairing (shared timer + init preload), Invoke=C04 / Cooldown=C0C (one-shot setter shape).

**INFERRED**: UPROPERTY names for the 8 bytes.

**Single highest-value read**: UHT `PropPointers[]` walk on ULokiCMC's `FClassParams`. Names those 8 fields, confirms owning class, upgrades three STRONG_INFERs to MEASURED simultaneously.

## Reusable rules

- **R-S154-a**: A tick/init function that writes multiple state bytes but MISSES the master gate byte is a state RESETTER, not the state owner. Find the writer of the missing byte — that's the BEGIN/authority owner. (Corollary of "record the writer set, not just the write frequency".)
- **R-S154-b**: `[avatar+0x400]` is CharacterMovement in this Loki build. Any deref-then-validate chain landing there is talking to a ULokiCMC. Bank alongside `+0xF00` (ASC) and `+0x3D0` (AIControllerClass) as this build's stable Character-family offsets.
- **R-S154-c**: A broadcast function has a `Broadcast` prologue, `FMulticastScriptDelegate` walk, or invocation-list iteration. Absence of ALL THREE + presence of geometric arithmetic (`|v|` compare, coordinate stores) = compute helper, not delegate. Do not label an auto-fire branch target "broadcast" until one of those three shows.
- **R-S154-d**: When a byte is written by ALL consumers as a predicate but by ONLY the outermost function as a value, it's a gate, not a phase. Re-classify before building a state diagram.