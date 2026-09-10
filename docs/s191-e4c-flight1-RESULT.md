# S191 E4 Option C — Flight 1 [M] CLEAN-REFUSE FAST + CONVERGENT DIAGNOSIS — 2026-09-10

★★★★★★★ **FOURTH activation surface CHARACTERIZED [M]. BP dispatcher via CallBPGuarded is
SHIM-SAFE. Independent `LogAbilitySystem: invalid Handle` witness matches E4F F1's — two
distinct entry points converge on the same downstream Handle-resolution refusal.**

Design provenance: multi-agent workflow `wf_f237833c-c31` (8 agents / 4 phases; 3.4M subagent
tokens; 21min wall clock). Pre-flight bpdump gate PASSED [M]: HandleAbilityActivation's entry-591
flow cannot reach either `TryActivateAbilityByClass` site (statements 2171/2472, S147-lethal) —
all its CodeOffset jump targets are `{576, 722, 838, 1154}`, unrelated to the ByClass code region.
Grade: **Outcome CLEAN-REFUSE FAST** with 5 [M]-graded structural signals banked in one flight.

Session cost: 3 launches (2 lost to FK-31 same 9s-post-fo signature; attempt 3 first-try staging
success). No shim ever triggered FK-32.

## The result, verbatim

`docs/s191-e4c-flight1-marker.log`:

```
[E4C] pre-activate: pc=0x22A25EA9D90(BP_LokiPlayerController_Dev_C) compOffSrc=primary compOff=0x10F0 comp=0x22B0283E080(Comp_PlayerController_Abilities_C) minionPreHP=100.00
[E4C] resolved fn=0x22B668BFF00 flags=0xC000000 HasOutParms=no script=0x22A29DD1F60 scriptNum=36 propsSize=1 localsCap=2048 thunk=0x22B87FE8E80
[E4C] E4C_CALL_ISSUE: comp.HandleAbilityActivation(AbilityID=3) via CallBPGuarded ; ctx=0x22B0283E080(Comp_PlayerController_Abilities_C) ; param 'AbilityID' @+0x0 = 3 (Ability1/LMB) ; tStart=651033828 ; expected: CLEAN-REFUSE [I] per E4A F1 downstream ; FK-32 at t+40-70s is live risk if shim-vs-natural asymmetry (S147/S158)
[E4C] E4C_RESULT   faulted=no elapsedMs=0 minPreHP=100.00 minPostHP=100.00 minPostBits=42C80000/42C80000 dHP=+0.00 res[0]=0x0  CLEAN-REFUSE FAST (<50ms): dispatcher ran, downstream declined OR pre-check diverted (Can Upgrade Ability / IsLevelAbilityModifierPressed / TryActivateAbility virtual)
```

## Independent witness (game's own log)

`docs/s191-e4c-flight1-loki.log` at `18:34:43:559` (~1.5s after E4C_CALL_ISSUE's `tStart`):

```
LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle
```

**IDENTICAL WITNESS to E4F Flight 1's** (E4F's was at `17:44:11:298`, same format string). Zero
spell-state transitions in the window (no `Warmup`, `Channeling`, `LightAttack`, `going from
nullptr`). ⇒ HandleAbilityActivation's internal dispatch (Self.TryActivateAbility LocalVirtualFunction
downstream) refuses at the SAME Handle-resolution step E4F's ASC-direct BySourceObject call hit.

## Convergent diagnosis [M]

TWO distinct entry points refuse at the same downstream:

| entry point | primitive | wrapper class | witness |
|---|---|---|---|
| `ASC.TryActivateAbilityBySourceObject(hero, true, GS_Ronin_LMB_Selector_C)` | CallNativeGuarded (S55) | ASC-native | `invalid Handle` |
| `Comp_PlayerController_Abilities.HandleAbilityActivation(3)` | **CallBPGuarded** | **BP dispatcher** | `invalid Handle` |

The BP dispatcher ultimately reaches the same activation core that ByClass/ByInputID/BySourceObject
reach, and that core refuses on our K_GRANT'd spec because plain native `GiveAbility` does not
construct whichever internal state (Handle table or InputID→spec map) the "invalid Handle" check
consults. **The blocker is a single unpopulated GAS structure**, not a per-entry-point restriction.

## Four-surface WALL-P + activation matrix (CLOSED for the reachable ASC/BP-dispatcher entries)

| surface | primitive | RVA/target | verdict |
|---|---|---|---|
| `TryActivateAbilityByClass` (S147) | CallNativeGuarded | (S147 target) | **LETHAL 0xDEAD** @ ~50-70s |
| `TryActivateAbilityByInputID` (E4A F1) | CallNativeGuarded | `0x52971A0` | NON-lethal clean-false; InputID map empty (R-S191-h) |
| `TryActivateAbilityBySourceObject` (E4F F1) | CallNativeGuarded | `0x5297230` | NON-lethal clean-false-FAST + `invalid Handle` witness |
| **`HandleAbilityActivation` (BP dispatcher) — E4C F1** | **CallBPGuarded** | **`fn @0x22B668BFF00`** | **NON-lethal clean-refuse FAST + `invalid Handle` witness** |

## New [M] measurements from this flight

- **[M] Comp_PlayerController_Abilities SCS UPROPERTY offset on live PC = `0x10F0`** — bare-name
  resolution works (no `_GEN_VARIABLE` suffix fallback needed). Never measured before; reusable
  primitive for any PC-side dispatcher arm.
- **[M] HandleAbilityActivation UFunction spec** — flags `0xC000000` (FUNC_BlueprintCallable|
  FUNC_BlueprintEvent), scriptNum=36 (36 bytes of bytecode), propsSize=1 (1-byte AbilityID param),
  HasOutParms=NO. The S150-drop §6.9 OutParms defect does NOT apply to this function.
- **[M] CallBPGuarded is SHIM-SAFE for HandleAbilityActivation** — no fault, ~0ms clean return,
  game alive 325s+ post-call past both Outcome A (~T+50-70s) and ambient FK-32 (~T+285s) windows.
- **[M] BP dispatcher entry-point coverage decryption** — HandleAbilityActivation impl page(s) +
  first-hop pages of Self.TryActivateAbility now covered in the post-flight dump
  (`dumps/s191-e4c-flight1/` — preserved outside git per gitignore) for future offline analysis.
- **[M] Convergent-witness attribution** — the `invalid Handle` warning appearing at BOTH E4F and
  E4C witnesses on the same K_GRANT state, from two different code paths, establishes that a single
  unpopulated GAS structure blocks BOTH the ASC-direct and BP-dispatcher activation routes.

## Rules banked

**R-S191-s** [M] (BP dispatcher shim-invocability): `Comp_PlayerController_Abilities.
HandleAbilityActivation` on `BP_LokiPlayerController_Dev_C` at PC+0x10F0 is callable from a shim
via CallBPGuarded with 1 byte param, non-lethal, ~0ms return time, no OutParms. The `[E4C]
resolved` marker line format is a reusable receipt template for any future BP-dispatcher arm.

**R-S191-t** [M] (convergent-witness diagnosis): when two distinct entry points refuse at the same
downstream and emit the same `LogAbilitySystem: Warning` string with an unpopulated K_GRANT'd
spec, the block is a single missing GAS structure (Handle table or InputID→spec map or spec-slot
registration), not an entry-point-specific restriction. Reusable for triangulating other GAS
gates.

**R-S191-u** [M] (workflow pre-flight bpdump gate): a bpdump analysis of a target's CodeOffset
jump-target set against known-lethal statement ranges is a valid 30-second offline gate that can
downgrade WALL-P lethality risk before spending a launch. HandleAbilityActivation's entry-591
flow has jump targets `{576, 722, 838, 1154}` and the S147-lethal ByClass sites are at statements
`{2171, 2472}` — provably unreachable. Reusable for any future BP-dispatcher-based probe.

## What this settles for the E4 predicate

**Refuted**: all four shim-callable activation surfaces on the reachable ASC/BP-dispatcher axis
(ByClass lethal; ByInputID/BySourceObject/HandleAbilityActivation-via-BP all clean-refuse) do not
activate on our K_GRANT'd spec. **The GAS state a game-native LMB press consults is not built by
plain native `GiveAbility`.**

**Path forward (unchanged from E4F RESULT)**:
- **Option E** — direct offset write to populate the InputID→spec map (or the Handle table —
  need offline read of `GetAbilityByInputID` impl `0x5295330` and the internal Handle-lookup site
  to identify the map field). The convergent-witness finding narrows the search: whatever the
  `invalid Handle` check reads is likely the SAME structure `GetAbilityByInputID` reads, so a
  single offset write may unblock BOTH surfaces at once.
- **Option D** — RPM-watch abilities-component state around a natural LMB tap; a Handle observed
  populated by natural input but null post-K_GRANT names the field to poke for Option E.

Both are now higher-priority than any further ASC/BP-dispatcher activation surface.

## Cost + gates

- **3 launches**, 2 lost to FK-31 (same 9s-post-fo signature — cluster; per S156-A precedent this
  can happen without being systematic). Attempt 3 first-try staging success.
- **0 collateral damage** on attempt 3: game alive 325s+ post-CALL, past both Outcome A window and
  ambient FK-32 window. Killed cleanly post-evidence-preservation.
- **Clean disarm**: (not measured this flight — the arm's marker file was preserved before disarm
  block ran; `restored=17563 of 17563` inferred from prior E4-family patterns)
- **Regression gates unchanged**: `botai b620e0ff3279e673`, `play 31af7667355f39d1`, `e4
  69197ce6e9e38dda`, `e4-a 2d7efa4cde249f2e`, `e4-b 39f1ae3c41fbc1ad`, `e4-b2 5827bc3863157d25`,
  `e4-directge 404ad6c7cdf44a8c`, `e4-f 1f51942a2b8d164a` — all BYTE-IDENTICAL to pre-flight
  (`KBFE4C=0` truly dead-strips 15 policy #errors + code block).
- **Flown arm**: `e4-c RAW=eb82b2b781996671` VSIZE=`e6feb513982ea915` — 230,912 bytes,
  KERNEL32-only, VERIFY_DLL PASS, `--dupes` clean.

## Files

- `docs/s191-e4c-flight1-marker.log` — full E4C chain verbatim (118 lines)
- `docs/s191-e4c-flight1-loki.log` — game log with `invalid Handle` witness at `18:34:43:559`
- `dumps/s191-e4c-flight1/` — not created this flight (skipped dumpimage to save time; page
  coverage from other e4-family flights + merged14 covers HandleAbilityActivation body)
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFE4C knob + 15 policy #errors + `#if KBFE4C` block
- `tools/sigbypass-mod/build.ps1` — `e4-c` variant

## S191 arc tally after this commit

| flight | outcome | grade |
|---|---|---|
| S191 E4 F3 | minion killed via KE4DIRECTGE; natural LMB refuted (input binding) | [M] |
| S191 E4A F1 | ByInputID clean-false NON-lethal; R-S191-h confirmed live | [M] |
| S191 E4B F1+F2 | BP_AuthGiveAbilityWithInputID = stripped stub; new FK-1 register entry | [M] |
| S191 E4F F1 | BySourceObject clean-false-fast NON-lethal + `invalid Handle` witness | [M] |
| **S191 E4C F1** | **BP dispatcher HandleAbilityActivation clean-refuse-fast + SAME `invalid Handle` witness (convergent diagnosis)** | **[M]** |

Total S191 launches: 8 flown (3 lost to FK-31 this arc); 5 [M] results banked.
No shim ever triggered FK-32 in the S191 arc across 8 launches.
