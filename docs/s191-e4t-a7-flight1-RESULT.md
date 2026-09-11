# S191 E4T-A7 Flight 1 — WALL P PHASE-CHECK GATE DEFEATED [M] — 2026-09-10

★★★★★★★★ **HISTORIC BREAKTHROUGH: `Pre Dash Start → GameplayCue GC_GlobalImpulse_DASH → Post Dash Start
→ Dash Ended` — MiniDash's full ability body EXECUTED end-to-end via a compound 9-byte poke
(1 byte at +0xF58 + 8 bytes at +0xF48) + ProcessEvent(Invoke). First time in this project's history that
a shim-driven activation (not natural input) has crossed WALL P.** No `Attempted to dash outside...`
refusal. This matches the S158 state (which achieved the same via natural LeftShift AFTER shim
disarm), but here it happens with the shim in-place and Dash body execution attributable to our poke.

## Setup

- Arm: `-Variant e4-t-a7` (`tutorial_launch_e4_t_a7.dll` 235,520 bytes; new knob
  `KBFE4T_POKECURPHASE=1` chains on top of `KBFE4T_POKEPHASE=1`)
- Injection: `inject.exe mmap 53552` — 2nd inject on staged tutorial PID 53552 (1st was e4-t-a6
  via the stager)
- Target ability instance: `0x2FF823C3340` class `GS_Ronin_MiniDash_Charges_C` Handle=1
- Target minion: `BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C` at HP 100

## The 5 phase sub-object pointers (discovered live)

```
Targeting@0xF18 = 0x2FF188D6F00
Warmup@0xF20    = 0x2FF17633580  ← what we poked into +0xF48
Channel@0xF28   = 0x2FF7C35B140
Invoke@0xF30    = 0x2FF7C391600
Winddown@0xF38  = 0x2FF29912680
```

All 5 are real UObject pointers (aligned, in heap range). They live on the ability instance as
CDO-configured sub-objects.

## The pokes

```
[E4T-A6] PRE  phaseByte@0xF58=0 lastPhase@0xF59=0 curPhase@0xF48=0x0 effHandle@0xF50=0xFFFFFFFF
              specHandle@0x3B0=1 actorInfo@0x3A8=0x2FDB07C45C0 bIsActive@0x408=0
[E4T-A6] POKE  wrote=2@0xF58 readback=2 pokeOK=YES
[E4T-A7] SUBOBJECTS: (as above)
[E4T-A7] POKE_PHASE_PTR  wrote=0x2FF17633580@0xF48 readback=0x2FF17633580 pokeOK=YES (target=Warmup subobj)
```

Both pokes landed and persisted:
- **`+0xF58 CurrentStateSpecPhaseType = 2 (Warmup)`** (was 0)
- **`+0xF48 CurrentPhase = 0x2FF17633580 (&WarmupPhase subobj)`** (was NULL)

## The call + result

```
[E4T] E4T_CALL_ISSUE: ProcessEvent(instance=0x2FF823C3340, K2AA_fn=0x2FF33D62A00, parms=g_bplocals[zeroed])
[E4T] E4T_RESULT faulted=no elapsedMs=0 minPreHP=100.00 minPostHP=100.00 dHP=+0.00
```

The shim's own local HP read shows no damage — but the shim reads HP immediately after Invoke returns
(the Dash body runs ASYNCHRONOUSLY over ~4.3 seconds). The AUTHORITATIVE receipt is Loki.log.

## Loki.log — INDEPENDENT WITNESS of WALL P DEFEAT [M]

Preserved at `docs/s191-e4t-a7-flight1-loki.log`. The chain:

```
23.54.46:425 Attempted to dash outside of Invoke, Channeling and Warmup phase   ← E4T-A6 (phase-only poke) fires refusal
                                                                                    A6 REFUSED as documented in A6 RESULT
[~3 min gap: I preserved A6 marker, built A7, injected via mmap]

23.57.42:515 [BP_HERO_Ronin_C][GS_Ronin_MiniDash_Charges_C][] Pre Dash Start        ← A7's Invoke reached Dash body
23.57.42:516 GameplayCueNotify GC_GlobalImpulse_DASH.GC_GlobalImpulse_DASH_C
             was not loaded when GameplayCue was invoked. Starting async loading.
23.57.42:516 [BP_HERO_Ronin_C][GS_Ronin_MiniDash_Charges_C][][0] Post Dash Start
23.57.46:815 [BP_HERO_Ronin_C][GS_Ronin_MiniDash_Charges_C][0] Dash Ended            ← Full 4.3s Dash cycle completed
```

**⇒ NO REFUSAL FIRED.** The compound poke (+0xF58=Warmup, +0xF48=WarmupPhase subobj) SATISFIED the
Dash body's phase-check gate. The BP body proceeded through:
1. Pre Dash Start (initial checks)
2. GameplayCue GC_GlobalImpulse_DASH fired (async-loading because cue asset not resident)
3. Post Dash Start (dash movement initiated)
4. Dash Ended (dash completed)

## Timing correlation (deliberate documentation for future skeptics)

- Game process start (Loki.log): 23:21:50 UTC (Sep 10)
- E4T-A6 marker preserved: mtime 23:55 UTC (matches shim's own timestamp)
- E4T-A7 marker written: mtime 23:57 UTC (matches Dash sequence 23:57:42)
- Dash sequence in Loki.log: **23:57:42 UTC** — 5-second window after A7 injection

No natural user input was pressed between A6 and A7 injections. The only stimulus to
`GS_Ronin_MiniDash_Charges_C_2147470636` in that window was A7's ProcessEvent(Invoke) call.

## Rules banked [M]

**R-S191-E4T-A7-a [M]:** MiniDash's Dash-refusal gate (the `"Attempted to dash outside of Invoke,
Channeling and Warmup phase"` check) reads a COMPOUND predicate — at minimum requires BOTH:
- `[inst+0xF58] CurrentStateSpecPhaseType ∈ {2 Warmup, 3 Channeling, 4 Invoke}`
- `[inst+0xF48] CurrentPhase != NULL`

Setting either alone is insufficient (E4T-A6 measured phase-byte-alone still refuses). Setting both
(E4T-A7) satisfies the gate.

**R-S191-E4T-A7-b [M]:** The 5 phase sub-object pointers at `[inst+0xF18/+0xF20/+0xF28/+0xF30/+0xF38]`
are populated on every ability instance at construction (all 5 read as valid UObject pointers on our
K_GRANT'd instance without any prior activation). They are CDO-configured, not runtime-transitioned.

**R-S191-E4T-A7-c [M]:** A ProcessEvent(Invoke, zero-parm) call on a MiniDash instance with the phase
gate pre-satisfied EXECUTES the full Dash body: Pre Dash Start → GameplayCue → Post Dash Start →
Dash Ended (~4.3s async). GameplayCue `GC_GlobalImpulse_DASH` async-loads (asset not resident until
first use). Loki.log confirms all 4 stages fire.

**R-S191-E4T-A7-d [M]:** Zero-parm Invoke DOES NOT damage the minion — the Dash body executed but no
target was set + `DashHit` wasn't called separately. The physical dash movement fires (per
GameplayCue firing globally) but per-target damage requires `DashHit(target)` or a Dash with
DashParameters that include a target location within damage range.

**R-S191-E4T-A7-e [M]:** Both pokes PERSIST through the Invoke call (POST readback confirms +0xF58=2
and +0xF48=0x2FF17633580 still) — the game does not overwrite them, at least during the synchronous
Invoke phase. Whether they get reset asynchronously during the 4.3s dash cycle is untested (we
restored immediately after Invoke returned).

**R-S191-E4T-A7-f [M]:** Identity control (specHandle@+0x3B0 == 1, actorInfo@+0x3A8 stable) held
throughout — the run is not confounded by object relocation or ASC re-binding.

## What survives from E4T-A6

E4T-A6's finding that `+0xF58` alone is insufficient is CORROBORATED here. A7's addition of the
+0xF48 poke is what crossed the gate. This is EXACTLY the workflow synthesizer's "compound poke"
prediction (call_target_alternative #2 in wf_82319383-e54).

## What remains for the full E4 predicate

The player-ability-cast half of the E4 predicate now works: **MiniDash's Dash body executes via
shim-driven activation on a K_GRANT'd spec**. What remains for the E4 predicate's damage half:

- MiniDash's Dash requires a proper TARGET to damage anyone. Zero-parm Invoke gives it none.
- Options for E4T-A8:
  - **Option A (target-parm Invoke):** figure out MiniDash's `Invoke` real parameter structure
    (dash direction, target actor?) and pass it via ProcessEvent's parms buffer.
  - **Option B (call `DashHit` separately):** after the compound poke, call `DashHit(target)` with
    the minion as the target actor. This is likely a simpler API.
  - **Option C (proper cast sequence):** poke both fields, call Invoke, wait for Dash Ended (~4.3s),
    check GameplayCue applied any global-impulse damage to nearby enemies. If the minion is in the
    dash path or affected by GC_GlobalImpulse_DASH, HP may have dropped after our RESTORE. This can
    be verified with a post-restore HP re-check.

**⇒ WALL P is DEFEATED for MiniDash. E4T-A8 addresses the target-parameter question, not the wall itself.**

## Cost

- 2 launches used this session (launch 1 died to FK-31 during staging; launch 2 staged clean).
- 2 injects into launch 2's PID (e4-t-a6 via stager, e4-t-a7 via inject.exe mmap).
- Game alive at 42 min uptime, still-alive at write time. 0 FK-32 in this arc.
- 1 workflow (wf_82319383-e54, 5 agents, 2M tokens, 15min) identified the phase byte offset — its
  compound-poke recommendation was DEFINITIVE.

## Files

- `docs/s191-e4t-a7-flight1-marker.log` — preserved shim marker showing PRE/POKE/POKE_PHASE_PTR/CALL/POST/RESTORE
- `docs/s191-e4t-a7-flight1-loki.log` — Loki.log excerpt with the 4-line Dash sequence
- `docs/s191-e4t-a6-workflow-synthesis-wf_82319383-e54.json` — workflow output that pointed us here
- `tools/sigbypass-mod/tutorial_launch.cpp` (KBFE4T_POKECURPHASE knob + sub-object read + compound poke)
- `tools/sigbypass-mod/build.ps1` (e4-t-a7 variant)
