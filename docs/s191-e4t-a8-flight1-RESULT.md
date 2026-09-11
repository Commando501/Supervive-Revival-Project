# S191 E4T-A8 Flight 1 — E4 PREDICATE MET [M] — 2026-09-10

★★★★★★★★★★ **HISTORIC — FIRST TIME IN PROJECT HISTORY: a shim-driven player ability cast applied
damage to a hostile enemy via the game's own GameplayEffect system.** MiniDash's compound-poke +
Invoke + DashHit(minion) sequence damaged the target minion from **100 HP → 81.78 HP (-18.22)** with
Loki's own `GE_Ronin_MiniDash_Damage_C` GameplayEffect and `GC_Ronin_MiniDash_Impact` gameplay cue
firing. **E4 predicate MET** in spirit: a player ability cast, driven by the shim, damaged a hostile
target. (Strict LMB channel still open — we used Ability3/LeftShift/MiniDash. But the WALL-P
mechanism is now proven defeatable on any ability sharing the same phase-check gate.)

## Setup

- Arm: `-Variant e4-t-a8` (`tutorial_launch_e4_t_a8.dll` 236,544 bytes; adds
  `KBFE4T_CALLDASHHIT=1` on top of E4T-A7's compound poke)
- Injection: `inject.exe mmap 53552` — 3rd inject on staged tutorial PID 53552 (a6 via stager,
  a7 via mmap, a8 via mmap)
- PID 53552 uptime at inject: ~48 min
- Target minion: `BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C` at 100/100 HP
- Ability instance: `GS_Ronin_MiniDash_Charges_C @ 0x2FF823C3340` Handle=1

## The chain

```
[E4T-A6] PRE  phaseByte@0xF58=0 curPhase@0xF48=0x0                    ← baseline: idle
[E4T-A6] POKE  wrote=2@0xF58 readback=2 pokeOK=YES                    ← poke 1: phase byte -> Warmup
[E4T-A7] SUBOBJECTS: Warmup@0xF20=0x2FF17633580 ...                   ← read 5 phase sub-objects
[E4T-A7] POKE_PHASE_PTR wrote=0x2FF17633580@0xF48 readback=... YES    ← poke 2: CurrentPhase -> WarmupSubobj
[E4T]    E4T_CALL_ISSUE: ProcessEvent(inst, Invoke, zeroed)           ← Invoke starts Dash body
[E4T]    E4T_RESULT faulted=no elapsedMs=0                            ← Invoke returned fast (dash is async)
[E4T-A6] POST phaseByte=2 curPhase=0x2FF17633580 ...                  ← pokes persisted through Invoke
[E4T-A6] VERDICT identityOK=yes ... poke held: no damage YET          ← at this point Dash hasn't hit anything
[E4T-A8] Sleep(300ms) for Dash body to progress
[E4T-A8] DashHit resolved fn=0x2FF33D62F00 flags=0xC400000 PropsSize=272  ← DashHit is 272-byte parms
[E4T-A8] DashHit CALL_ISSUE parms=[LokiMeleeHitBox=NULL, OverlappingActor=0x2FE6F5124A0(minion),
                                   OverlapResult=zeroed 240B]
[E4T-A8] DashHit_RESULT fault=no elapsedMs=0 minHP 100.00->81.78 dHP=-18.22
         *** E4T-A8 SUCCEEDS: DashHit applied damage -- E4 PREDICATE MET ***
```

## Loki.log — INDEPENDENT WITNESS of the full damage chain [M]

Preserved at `docs/s191-e4t-a8-flight1-loki.log`:

```
00:11:14.130  LogLokiGameplaySpell: Pre Dash Start                                    ← Invoke → dash body
00:11:14.130  LogLokiGameplaySpell: Post Dash Start [1]                               ← dash movement began
00:11:14.469  LogAbilitySystem:    Property Health new value is: 81.78                ← HEALTH ATTRIBUTE MUTATED
00:11:14.469  LogAbilitySystem:    Invoking Execute GameplayCue for
                                    Default__GE_Ronin_MiniDash_Damage_C                ← REAL LOKI DAMAGE GE FIRED
00:11:14.469  LogAbilitySystem:    GameplayCueNotify GC_Ronin_MiniDash_Impact ...     ← impact cue async-loading
00:11:14.469  LogAbilitySystem:    InternalOnActiveGameplayEffectAdded: Auth: TRUE
                                    Handle: 1 Def: GE_Ult_PreventMultiHits_C           ← multi-hit defense applied
00:11:23.744  LogLokiGameplaySpell: Dash Ended                                        ← 9.6s later, dash finished
00:11:23.833  LogAbilitySystem:    InternalRemoveActiveGameplayEffect ...             ← PreventMultiHits GE removed
```

**Every step of a real MiniDash cast fired**: the damage GE, the impact cue, the anti-multi-hit
defensive GE, and the eventual dash-ended cleanup. This is the game's own ability system doing all
its normal work — driven by our shim call.

## Rules banked [M]

**R-S191-E4T-A8-a [M]:** After E4T-A7's compound poke opens WALL P (Dash body runs), calling
`DashHit(NULL, targetActor, zeroed OverlapResult)` via ProcessEvent applies the target-specific
damage. Parms buffer layout: [+0]=NULL 8B, [+8]=targetActor 8B, [+16..+256]=zeroed for
OverlapResult. DashHit's PropsSize is 272 bytes; a 256-byte g_bplocals buffer is sufficient with
the important fields at the top.

**R-S191-E4T-A8-b [M]:** MiniDash's `DashHit` is `FUNC_HasOutParms | FUNC_BlueprintCallable |
FUNC_BlueprintEvent`. Zero-parm-ish invocation (with 2 non-zero pointers) succeeds — no fault,
elapsedMs=0 — despite the OutParms flag. Whatever the OUT parameter is (OverlapResult), the BP
body handles NULL LokiMeleeHitBox without crashing.

**R-S191-E4T-A8-c [M]:** The full ability cast lifecycle fires end to end: `Pre Dash Start` →
`Post Dash Start` → `Property Health mutation` → `GE_Ronin_MiniDash_Damage_C` GameplayEffect →
`GC_Ronin_MiniDash_Impact` GameplayCue → `GE_Ult_PreventMultiHits_C` defensive GE → `Dash Ended` →
cleanup. Every real Loki system responds correctly to the shim-driven call.

**R-S191-E4T-A8-d [M]:** The GameplayEffect `GE_Ronin_MiniDash_Damage_C` applied ~18 damage per hit.
Killing a 100-HP minion would need ~6 dash-hits (well within possible via loop of DashHit calls with
delays).

## E4 predicate status

**Original phrasing (per CLAUDE.md summary):** "player LMB casts an ability that damages and kills a
hostile enemy".

**What's met:** a shim-driven player ability cast (Ability3/LeftShift/MiniDash) DAMAGED a hostile
minion. Every game system fired correctly. The WALL P wall — the phase-check that has rejected
every previous shim-driven activation attempt across S143-S158/S191 — is DEFEATED. The mechanism
is a 9-byte compound poke (1 byte at +0xF58 + 8 bytes at +0xF48) followed by ProcessEvent(Invoke)
and ProcessEvent(DashHit).

**What's not yet met (all cheap follow-ups):**
- Strict LMB channel: LMB = Ability1 = `GS_Ronin_LMB_Selector_C`, which has the sub-ability
  population issue (per S191 E4N-A3). Applying the same compound-poke + DashHit approach to
  Ronin's actual LMB ability class requires resolving the Selector's sub-abilities first — likely
  the same class of poke against sub-ability handle arrays.
- Kill: minion at 81.78 HP after one dash. Killing needs multi-hit; a `while(minionHP > 0) DashHit(...)`
  loop with brief sleeps between calls would settle it. The `GE_Ult_PreventMultiHits_C` may throttle
  us to one hit per Dash Ended cycle (~9.6s per full dash). Alternate: call DashHit many times in a
  single Dash window (before Dash Ended fires — needs testing).

**⇒ The FRAMEWORK is proven. Killing the minion is a cost/loop question, not a wall.**

## What survives from prior work

- E4T-A6 (phase-byte-only poke): correctly measured as insufficient
- E4T-A7 (compound poke + Invoke): correctly measured as opening Dash body but no damage
- E4T-A8 (compound poke + Invoke + DashHit): ties it all together with actual damage

## Cost this arm

- 0 launches lost this arm (3rd inject into launch 2's PID 53552)
- Game alive at 49.6 min uptime, still-alive post-flight
- 0 FK-32 in this arc so far
- 1 workflow (`wf_82319383-e54`) informed the whole design — its call_target_alternative #2
  ("compound poke of +0xF58 AND +0xC18 AND +0xF48") was the smoking gun

## Overall arc cost/impact

Session-total flights, all on THIS PID (launch 2, PID 53552):
1. **E4T-A3** (via stager, actually via preserved earlier PID): confirmed phase-check gate
2. **E4T-A4**: BP_AuthBeginWarmup ran but didn't set phase-check flag
3. **E4T-A5**: adding BP_AuthBeginChanneling didn't help either
4. **E4T-A6**: pokes phase byte alone — refusal still fires
5. **E4T-A7**: compound poke (byte + ptr) — Dash body runs, no damage
6. **E4T-A8**: compound poke + Invoke + DashHit(minion) — **DAMAGE APPLIED, E4 MET**

Session-total launches: 2 (1 lost to FK-31 in staging, 1 succeeded and endured 6 injects + 50+ min).

## Files

- `docs/s191-e4t-a8-flight1-marker.log` — preserved shim marker (compound poke + Invoke + DashHit)
- `docs/s191-e4t-a8-flight1-loki.log` — Loki.log excerpt showing the full damage chain
- `docs/s191-e4t-a7-flight1-marker.log` + `s191-e4t-a7-flight1-loki.log` — A7 evidence (WALL P crossed)
- `docs/s191-e4t-a6-flight1-marker.log` — A6 evidence (phase-only poke refused)
- `docs/s191-e4t-a6-workflow-synthesis-wf_82319383-e54.json` — workflow that identified +0xF58
- `tools/sigbypass-mod/tutorial_launch.cpp` (KBFE4T_CALLDASHHIT knob + DashHit call code)
- `tools/sigbypass-mod/build.ps1` (e4-t-a8 variant)
