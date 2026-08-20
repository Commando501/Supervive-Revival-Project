# PRE-REGISTRATION — RM_RIDEABLE: call the FIFTH WALL directly, with a NON-NULL PlayerState

**Written 2026-08-20, BEFORE the DLL was injected.** The client from the Route-E flight is still
alive (PID 34348, ~30 min, world staged, an initialised pod present), so this costs **no launch**.

## Why

S131's Route-E flight *appeared* to test the rider handoff. It did not:
`AuthPlayerEnterWorldAttachedToRidable` was handed `v38 = GetTeamDropLeader(...) = null`, and impl
`0x55CD510` opens `test rdx,rdx ; je -> ret` — **it returned on instruction #1**. The zero in
`grep "failed to get the round game mode"` is therefore **UNINTERPRETABLE**.

⚠ And the obvious fix is blocked at its precondition. **MEASURED read-only this session: ZERO live
instances of any class containing `TeamOnly`, and the only `TeamState`-named live object is
`Comp_TeamState_GlobalShop_GEN_VARIABLE`, a template.** There is no TeamState actor to poke, so
routing through `GetTeamDropLeader` depends on an object this world does not contain.

⇒ Call the wall directly. Both arguments are live and resolvable BY NAME: the pod's own
`LokiRideable` component (`BP_DropPod_C.LokiRideable`, MEASURED non-null at `+0x6C8`,
`cls=LokiRideableComponent`) and `BP_LokiPlayerState_C`. This is a **fair** test because the recorded
claim is that the failure is *unconditional*.

## Predictions

| # | prediction | grade | what falsifies it |
|---|---|---|---|
| P1 | `R0c ContainsPlayer(PlayerState)` returns **false (0)** without faulting | [I] | a fault, or `USED=-1` ⇒ **SITTING VOID**: the primitive is not demonstrated on this component and R1 is unattributable |
| P2 | the PlayerState's `ObjectFlags>>30` IsValid test **PASSES** | [I] | a FAIL means the wall bails at `0x55CD548`, silently, and says nothing |
| P3 | `R1` returns **without fault** | [I] | a fault localises to the wall's body |
| **P4** | **`Loki.log` gains `AuthPlayerEnterWorldAttachedToRidable failed to get the round game mode`** — baseline count verified **0** | [I] | absence ⇒ it bailed EARLIER (`0x55CD548` IsValid or the predicate at `0x55CD54E`); read P2 to separate them. **Absence is NOT "the wall held".** |
| P5 | `R2 ContainsPlayer` still **false** | [I] | `false -> true` would **REFUTE** the always-fail grade of `0x55CD510` and is the biggest possible result here |

**P4 is the headline.** Present ⇒ the fifth wall moves from an offline grade to **[M]**, measured, for
the first time. ★ The emit is [M] **not** stripped: it dispatches through `0x106B650`, a logger with
22 other call sites, two of whose messages appear verbatim in the log corpus as `LogLokiGameMode:
Display: …`.

## Void conditions, fixed in advance

1. `R0c` does not return a value ⇒ **VOID** (the arm prints this verdict itself).
2. The resolver finds ≠1 live `ALokiPlayerState`, or no pod with `PodTeamIndex == 0` ⇒ it **REFUSES
   to guess** and makes no call. That is a resolve statement, not a result.
3. A fault inside the ladder ⇒ halt; the marker names the step.

## Safety

Between instruction #1 and the bail the body only READS: an IsValid bit test, one predicate call, a
cached-world fetch, and the stripped `0xF7EB50` getter. The arm performs **no `.text` write, no PI
hook and no memory poke** — two direct `UFunction.Func` calls through the S55 primitive plus guarded
reads. `KFUNCSWAP=0` is a compile-time refusal.

**Artifact:** `tutorial_launch_rideable.dll`, `.text` **`3cba72ec28e769b6`** (113,664 B).
`play` re-verified **UNCHANGED** at `9bc10a4552c596e1`.

**Baseline, verified before injecting:** `grep -c "failed to get the round game mode" Loki.log` = **0**.

---

## AMENDMENT 1 -- written BEFORE the second injection

The first build REFUSED: it found **2** live ALokiPlayerStates (`LokiPlayerState_HeroAffiliated` 0x2BDCFA012C0 and `BP_LokiPlayerState_C` 0x2BDBC6199A0) and would not guess. That is the right default but it wastes a live armed window, so the arm now calls the wall **ONCE PER CANDIDATE**, each labelled. The question is whether the body EVER gets past its guards; any candidate that produces the log line answers it, and each call stays attributable to a NAMED PlayerState.

Unchanged predictions P1-P5. **P4 now reads: the log line appears for AT LEAST ONE candidate.** If it appears for neither, read the per-candidate IsValid lines to separate 'bailed at 0x55CD548' from 'bailed at the 0x55CD54E predicate' -- neither is 'the wall held'.

**Artifact: `tutorial_launch_rideable.dll` .text `e221e4e415834067` (114,688 B).** Baseline `grep -c 'failed to get the round game mode'` re-verified 0.

? Free finding already banked from the refused run: **pod-cand[3] (the never-finished DEFERRED pooled spawn) has `LokiRideable = 0x0`** -- a second, independent confirmation that such a pod has NO components at all, on a different property from the null RootComponent.
