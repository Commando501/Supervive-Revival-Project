# S191 E4T-A5 Flight 1 — Warmup+Channel+Invoke chain STILL refused [M] — 2026-09-10

★★★★ **NEGATIVE with a sharpening: chaining `BP_AuthBeginWarmup → BP_AuthBeginChanneling → Invoke →
DashHit` through ProcessEvent produces the SAME refusal as E4T-A4. The Warmup GE is added; then the
Channel + Invoke calls fire cleanly; the phase-check STILL says `"Attempted to dash outside of Invoke,
Channeling and Warmup phase"`. ⇒ zero-parm BP-event calls DO NOT flip the phase state that the
dash-precheck reads.**

## Setup

- Arm: `-Variant e4-t-a5` (KBFE4T_SEQUENCE=1 + KBFE4T_CHANNEL=1, both added this session; RAW:
  `tutorial_launch_e4_t_a5.dll` 231,936 bytes)
- Injection: `inject.exe mmap 54416` (6th inject on same PID; uptime 50.9 min at inject time)
- Instance: `0x1EC0263AAB0` class `GS_Ronin_MiniDash_Charges_C` Handle=4, target minion at 100 HP
- Grant OK: Items.Num 5 → 6 (6th MiniDash spec on same ASC — no rejection, K_GRANT tolerant)

## The chain

New in A5: `BP_AuthBeginChanneling` was FOUND on the instance's class chain at
`fn=0x1EA07CEE9B0` — this is the `ULokiGameplaySpell` base class's method (see
`binds_members.csv:4219 class ULokiGameplaySpell method 10`), NOT a MiniDash override.

```
[E4T-A4] SEQUENCE mode: Warmup=0x1EB8A616F00 Channel=0x1EA07CEE9B0 Invoke=0x1EB8A616700 DashHit=0x1EB8A616C00
[E4T-A4] hpStart=100.00
[E4T-A4] STEP1_CALL BP_AuthBeginWarmup     ; STEP1_RESULT fault=no elapsedMs=0 dHP=+0.00
[E4T-A4] STEP1.5_CALL BP_AuthBeginChanneling; STEP1.5_RESULT fault=no elapsedMs=0 dHP=+0.00
[E4T-A4] STEP2_CALL Invoke                  ; STEP2_RESULT fault=no elapsedMs=0 dHP=+0.00
[E4T-A4] STEP3_CALL DashHit                 ; STEP3_RESULT fault=no elapsedMs=0 dHP=+0.00
[E4T-A4] E4T_A4_COMPLETE hpStart=100.00 hpEnd=100.00 dHPtot=+0.00
```

## What Loki.log says [M]

```
22.59.23:137  LogAbilitySystem: Verbose: Added GE: Default__GE_GlideSuppressd_CallerScale_C
              ReplicationID: 2. Key: 0. PredictionKey: 0
22.59.23:137  LogAbilitySystem: Verbose: InternalOnActiveGameplayEffectAdded: Auth: TRUE Handle: 1
22.59.23:439  LogLokiGameplaySpell: Verbose:
              [BP_HERO_Ronin_C_2147471315][GS_Ronin_MiniDash_Charges_C_2147471106]
              Attempted to dash outside of Invoke, Channeling and Warmup phase
22.59.29:576  LogAbilitySystem: Verbose: InternalRemoveActiveGameplayEffect ...
```

Only the Warmup GE add fired real work. The Channel and Invoke and DashHit calls all returned in
0ms with no observable side effects. Then the same phase-check refusal fired 302ms after the GE add
(matches Invoke's timing after Warmup+150ms+Channel+150ms sleeps).

## Rules banked [M]

**R-S191-E4T-A5-a [M]:** `BP_AuthBeginChanneling` on `ULokiGameplaySpell` via ProcessEvent zero-parm
runs cleanly but produces no observable state change on the ability instance — no GE, no phase
transition, no Loki.log line.

**R-S191-E4T-A5-b [M]:** The chained sequence `BP_AuthBeginWarmup → BP_AuthBeginChanneling →
Invoke` does NOT advance MiniDash's phase-check state. Whatever the check reads is neither Warmup
GE presence nor whatever these three BP methods write.

**R-S191-E4T-A5-c [I,strong]:** The phase-check likely reads a sub-object `UWarmupPhase` /
`UChannelingPhase` / `UInvokePhase` (`ULokiGameplaySpell` properties 62-64 per binds_members.csv),
or a `ELokiSpellPhaseType CurrentPhaseType` field. `BP_Auth*` BP events are just events; the state-
change is done by a Loki C++ handler that catches them and needs a proper argument context.

## The phase-state architecture (deduced from binds_members.csv `ULokiGameplaySpell` class 4219)

Available on every ability instance:
- **Method: `GetCurrentPhaseType() const` returns `ELokiSpellPhaseType`** — enum. There IS a phase
  byte/enum somewhere.
- **Method: `AuthBeginWarmup / AuthBeginChanneling / AuthBeginWinddown / Invoke / EndInvoke`** —
  the transition ceremony (all BP-callable, zero args).
- **Method: `ShouldWarmupContinue()` returns bool** — a hook the state machine checks.
- **Method: `GetRemainingWarmupDuration(float& OutDuration)` / `GetWarmupDuration` /
  `GetInvokeDuration` / `GetMaxChargeDuration`** — read-side timers.
- **Property 61-65: UTargetingPhase, UWarmupPhase, UChannelingPhase, UInvokePhase, UWinddownPhase**
  — sub-object pointers. Each is a UObject that owns the state of that phase.
- **Property 19: bFullWarmupPrediction** (bool) · **Property 20: bFullInvokePrediction** ·
  **Property 22: bAllowClientPhaseTiming**.

## What E4T-A6 should do

Given zero-parm event calls don't advance state, two paths:

**Path A (poke-based): find `CurrentPhaseType` byte and poke it.**
Enumerate the ability instance memory `+0x400..+0x800` and diff against a known-idle instance to find
enum candidates. Then poke to `ELokiSpellPhaseType::Warmup` (value TBD, first-enumerate). Then call
`Invoke` — if the dash body runs and applies damage, WALL P defeated via one byte poke.

**Path B (sub-object dispatch): find `WarmupPhase` sub-object pointer, call its Start method.**
Read `[instance+?]` where `?` is one of properties 62-65 (offsets unknown; enumerate). Cast to
`UWarmupPhase` and call its own methods. This is more invasive; needs the sub-object's own
UFunction table.

**Path C (proper native call): call `AuthBeginWarmup` via the S55 primitive with the proper
FFrame context** so a real Loki authority handler can catch the event. `binds_members.csv` shows
these methods as `_,_` for AS binding, meaning they may need FFrame context beyond ProcessEvent.

## Cost this arm

- 0 launches lost (6th inject into PID 54416, uptime ~51min at inject time).
- 0 FK-32 in this arc still.
- The e4-t-a5 build is small (511 extra bytes vs e4-t-a4) and gated cleanly behind KBFE4T_CHANNEL.

## Handoff for E4T-A6

Workflow `wf_82319383-e54` (Analyze x 4 lanes + Synthesize) is running in background to identify
where `CurrentPhaseType` lives on the ability instance. When complete, its synthesis pins the byte
range for a memory-diff probe and/or names the sub-object offsets. Then build E4T-A6 with either
path A or path B based on which is cheaper.
