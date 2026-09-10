# S191 E4T-A4 Flight 1 — Warmup GE ADDED but phase-check refuses Invoke [M] — 2026-09-10

★★★★★ **PARTIAL WIN: `BP_AuthBeginWarmup` via ProcessEvent DID EXECUTE REAL CODE — it added a real
GameplayEffect (`GE_GlideSuppressd_CallerScale_C`) to the ASC. But calling `Invoke` 150ms later STILL
triggered MiniDash's `"Attempted to dash outside of Invoke, Channeling and Warmup phase"` refusal.
The phase-state check reads a DIFFERENT VARIABLE than what `BP_AuthBeginWarmup` sets.** Read this file
before designing E4T-A5.

## Setup

- Arm: `-Variant e4-t-a4` (KBFE4T_SEQUENCE=1, added this session; RAW: `tutorial_launch_e4_t_a4.dll`
  231,424 bytes)
- Injection: `inject.exe mmap 54416` into the already-staged PID 54416 (5th inject on same PID)
- Ability3 granted again: Items.Num 4 → 5, outHandle=5 (a 5th spec of MiniDash on same ASC)
- Target instance: `0x1EC0263AAB0` class `GS_Ronin_MiniDash_Charges_C` Handle=4 (reused from A3)
- Target minion: HP 100/100 (re-spawned + re-seeded — E4 spawn+seed re-ran this arm)

## The sequence

Same 17-candidate scan as A3 found the same 7 MiniDash BP surfaces. Sequence dispatch:

```
[E4T-A4] SEQUENCE mode: Warmup=0x1EB8A616F00 Invoke=0x1EB8A616700 DashHit=0x1EB8A616C00
[E4T-A4] hpStart=100.00
[E4T-A4] STEP1_CALL BP_AuthBeginWarmup fn=0x1EB8A616F00
[E4T-A4] STEP1_RESULT fault=no elapsedMs=0 hpAfter=100.00 dHP=+0.00      ← Warmup called, no HP change
[E4T-A4] STEP2_CALL Invoke fn=0x1EB8A616700                              ← 150ms later
[E4T-A4] STEP2_RESULT fault=no elapsedMs=0 hpAfter=100.00 dHP=+0.00
[E4T-A4] STEP3_CALL DashHit fn=0x1EB8A616C00 (zero-parm, may fault)      ← 200ms later
[E4T-A4] STEP3_RESULT fault=no elapsedMs=0 hpAfter=100.00 dHP=+0.00
[E4T-A4] E4T_A4_COMPLETE hpStart=100.00 hpEnd=100.00 dHPtot=+0.00 clean-return sequence, no HP change
```

## What Loki.log revealed [M]

```
22.28.47:867  LogAbilitySystem: Verbose: Added GE: Default__GE_GlideSuppressd_CallerScale_C.
              ReplicationID: 1. Key: 0. PredictionKey: 0
22.28.47:867  LogAbilitySystem: Verbose: InternalOnActiveGameplayEffectAdded: Auth: TRUE Handle: 0
              Def: Default__GE_GlideSuppressd_CallerScale_C
22.28.48:017  LogLokiGameplaySpell: Verbose:
              [BP_HERO_Ronin_C_2147471315][GS_Ronin_MiniDash_Charges_C_2147471106]
              Attempted to dash outside of Invoke, Channeling and Warmup phase
22.28.52:815  LogAbilitySystem: Verbose: InternalRemoveActiveGameplayEffect ... GE_GlideSuppressd_...
22.28.52:816  LogAbilitySystem: Verbose: DecrementLock decrementing a pending remove ...
```

- **22.28.47:867** — STEP1 `BP_AuthBeginWarmup` DID SUCCEED. Real GE `GE_GlideSuppressd_CallerScale_C`
  added via `InternalOnActiveGameplayEffectAdded` (Auth=TRUE). This is a "GlideSuppressed" GE that
  MiniDash applies for the duration of Warmup — proof that the warmup logic ran.
- **22.28.48:017** — exactly 150ms after (matches our `Sleep(150)`), STEP2 `Invoke` fired and
  triggered the phase-check refusal. The BP body checked its phase flags, saw NOT_IN_PHASE, and bailed.
- **22.28.52:815** — 4.8s after Warmup started, `GE_GlideSuppressd` was removed. This matches
  MiniDash's natural Warmup duration — the Warmup timer completed but NO channel transition fired
  (because our arm didn't drive it, or because the timer's completion callback needed the
  Warmup phase flag to be set).

## Rules banked [M]

**R-S191-E4T-A4-a [M]:** `BP_AuthBeginWarmup` on `GS_Ronin_MiniDash_Charges_C` via ProcessEvent
zero-parm SUCCEEDS at adding a Warmup GE (`GE_GlideSuppressd_CallerScale_C`). It is a real BP function
that runs real code with zero-parm invocation.

**R-S191-E4T-A4-b [M]:** MiniDash's BP-level phase-check (`"Attempted to dash outside of Invoke,
Channeling and Warmup phase"`) reads a phase-flag that is **NOT set by `BP_AuthBeginWarmup` alone**.
The Warmup GE presence and the phase flag are decoupled variables. Either (a) the flag is set by a
downstream timer or a different function, (b) the flag lives on a different object (e.g. the ASC's
ability-spec instead of the ability-instance), or (c) `BP_AuthBeginWarmup` needs a valid `WarmupInfo`
struct arg to actually engage the state machine.

**R-S191-E4T-A4-c [I,strong]:** The Warmup timer completing (22.28.52:815) without triggering a
Channel transition suggests the phase-flag on the ability instance is what gates the transition too
— so the flag was never set to Warmup in the first place, meaning `BP_AuthBeginWarmup` engaged the GE
side effects but not the state-machine side effects.

## What survives from E4T-A3

- ProcessEvent slot 78 REACHES BP body (A3 finding, RE-CONFIRMED here — Warmup GE add proves it).
- MiniDash's chain does NOT include `UGASGameplayAbility` (no `K2_ActivateAbility`).
- MiniDash's BP-level phase enforcement is real and consistent across two flights.

## Next arm design — E4T-A5: FIND THE PHASE BYTE, THEN POKE IT

The phase check reads a byte or bitfield somewhere on the ability-instance or spec. Candidates:

- `[UGameplayAbility+0x3B0]` = `CurrentSpecHandle` (Loki-specific offset from S191 E4N recon) — this
  is already correct (reads Handle=4 matching our grant), so it's not the phase byte.
- `[UGameplayAbility+0x628]` = `OwningASC` — also correct.
- Somewhere in `+0x3B4..+0x400` there is likely an enum byte for CurrentPhase
  (Idle=0/Warmup=1/Channeling=2/Invoke=3/Cooldown=4/etc).

**E4T-A5 recipe:**
1. Read `+0x3B0..+0x500` on the ability instance BEFORE STEP1.
2. Call STEP1 (`BP_AuthBeginWarmup`).
3. Re-read the same range 150ms later. Diff bytes to find "the byte that flipped when Warmup engaged".
   If no byte flipped, R-S191-E4T-A4-c is confirmed — the phase flag isn't touched by
   `BP_AuthBeginWarmup` at all.
4. If a byte DID flip, that's the phase byte. Then in E4T-A6 poke it directly to Warmup value BEFORE
   calling Invoke — that bypasses the whole state machine.

Alternative: `Invoke` may need a real params buffer (e.g. an FVector target location) — a zero-parm
call to a BP that has non-zero PropsSize would silently exit early on validation. `Invoke`'s
PropsSize wasn't printed by A4 — A3 recorded ScriptNum=18, PropsSize=0 for Invoke, so zero-parm
should be fine.

Alternative 2: Call `BP_AuthBeginWarmup` with a real `WarmupInfo` struct pointer. Its PropsSize
wasn't logged either. If it needs an FVector location + FRotator direction + timing floats, our
zero-parm call may have hit a "no target set" early-exit that SKIPS the state-flag write but still
executes the GE add via a different path (unconditional).

## Cost

- 0 launches lost this arm (5th inject into PID 54416, uptime 22.3min at write time).
- 0 FK-32 in this arc.
- Loki.log's evidence is the whole finding — the shim's own markers were insufficient by themselves.

## Handoff

E4T-A5 (memory-diff to find phase byte) is CHEAP and OFFLINE-safe (read-only RPM). It should be the
next arm. If the phase byte is identified, E4T-A6 (poke + Invoke) will settle the WALL P question in
one more inject: if HP drops, WALL P DEFEATED; if not, MiniDash's actual damage path needs a target
parameter to `DashHit`/`Character Hit`.

Full evidence: `docs/s191-e4t-a4-flight1-marker.log` (marker) + this doc + Loki.log tail preserved
inline above.
