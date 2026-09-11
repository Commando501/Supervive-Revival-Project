# S192 — VS-AI PLAYABLE Handoff (2026-09-10)

★★★★★★★★ **PRECEDING SESSION S191 CLOSED THE E4 PREDICATE — WALL P IS DEFEATED for both
Ability3 (MiniDash) and Ability1 (LMB / Ronin's LightAttack1). READ FIRST:**
- `docs/s191-e4t-a9-flight1-RESULT.md` — MiniDash kill (100→0 in ~1.75s via 6 DashHit)
- `docs/s191-e4t-lmb-a9-flight1-RESULT.md` — LMB kill via LightAttack1 + MeleeHit
- `docs/s191-e4t-a7-flight1-RESULT.md` — WALL P defeat mechanism (compound poke)
- `docs/s191-e4t-a6-workflow-synthesis-wf_82319383-e54.json` — phase byte at +0xF58 (UHT)

★★ **THIS SESSION'S TASK: build + fly VSAI-A1 (bot damages target via WALL P mechanism).**

## Design ready in the repo

**Workflow synthesis:** `docs/s191-vsai-a1-workflow-synthesis-wf_368c3732-8e0.json` — 5-agent
workflow (2M tokens, ~13 min) produced a complete VSAI-A1 arm design with ~150-line C++ delta,
9 knobs, 4 build variants, 12 pre-registered null meanings.

## Mechanism (proven S191, transfers to bot)

The 9-byte + 3-ProcessEvent recipe (from S191 E4T-A9), applied to a BOT's ability instance
instead of the player's:

1. K_GRANT ability class on the bot's ASC (not player's) via `[botAsc.vtable+0x778]`
2. Read bot's ability instance from `botAsc.Items[?].Rep.Data[0]` at matching InputID
3. Poke `[inst+0xF58] = 2` (`ULokiGameplaySpell::CurrentStateSpecPhaseType` = Warmup)
4. Poke `[inst+0xF48] = *(inst+0xF20)` (`CurrentPhase` → WarmupPhase subobj)
5. `ProcessEvent(Invoke, zero-parm)` — bot's Dash/attack body starts
6. `Sleep(300ms)`
7. Loop N × `ProcessEvent(<HitVerb>, [NULL, &target, zeroed 240B])` @ 250ms intervals
8. Restore both pokes

**Target for FIRST flight: `g_bfE4Target` (the E4-spawned minion at TeamID=100)** — Lane 3
argues this is the ONLY safe first-flight choice because E4 F3 already provided a [M] positive
control for spawned-minion damage; player-target introduces unbounded collateral (death cam,
respawn, GameState phases). Player-target is a strict follow-up after minion works.

## Concrete arm structure (from workflow)

New function `BsVsaiPuppetCast()` gated behind `KBFVSAI=1`, placed after `BsTrackDKill` in
`tools/sigbypass-mod/tutorial_launch.cpp`. 9 stations:

1. Resolve bot + bot ASC (Track D cached at bot+0xF00)
2. Resolve target actor (minion or player per KBFVSAI_TARGET)
3. Resolve ability class from bot's ClassDefault via `PropOffsetSuper(botCls, KBFVSAI_ABIL)`
4. K_GRANT on bot ASC via `BfBuildSpec + BfGiveAbilityNative`
5. Iterate `botAsc.Items[]` for the ability instance at KBFVSAI_INPUTID
6. Compound poke on the bot instance (+0xF58 + +0xF48)
7. `ProcessEvent(Invoke, zero-parm)` via `vtable[78]` (disp 0x270)
8. Damage-verb loop (KBFVSAI_REPS × ProcessEvent(HitVerb, [NULL, &target, zeroed]))
9. Restore compound poke

## Knobs (9 total)

| Knob | Default | Purpose |
|---|---|---|
| `KBFVSAI` | 0 | Master gate. 0 = dead-strip (byte-identical to parent) |
| `KBFVSAI_ABIL` | `"Ability3"` | UPROPERTY name on hero class; matches E4T-A9 proven |
| `KBFVSAI_INPUTID` | 5 | InputID (Ability3=5, Ability1/LMB=3) |
| `KBFVSAI_TARGET` | 0 | 0=minion (safe), 1=player (follow-up) |
| `KBFVSAI_HITVERB` | `"DashHit"` | Pair with Ability3=DashHit / Ability1=MeleeHit |
| `KBFVSAI_REPS` | 0 | 0=readonly (proves setup), 4=mindash, 8=full kill |
| `KBFVSAI_INTERVAL_MS` | 250 | Per E4T-A9 |
| `KBFVSAI_INVOKE_DELAY_MS` | 300 | Per E4T-A9 |
| `KBFVSAI_POKEVALUE` | 2 | ELokiSpellPhaseType::Warmup |

## Preconditions (5 #error guards)

- `KBFVSAI` requires `KBSPS=1` (Track D builds bot ASC)
- `KBFVSAI` requires `KBFTRACKD=1`
- `KBFVSAI` and `KBFE4T` are MUTEX (both drive ability-instance layer)
- `KBFVSAI_TARGET=0` requires `KBFE4=1` (needs BfE4SpawnSeedTarget)
- `KBFVSAI` requires `KBFTRACKD_DELTABITS=0x00000000u` (no-op AdjustHealth so bot survives to cast)

## Build variants (fly in order)

1. **`vsai-a1-readonly`** — REPS=0, hazard-minimal, first flight. Proves bot ASC resolves,
   K_GRANT lands, instance builds, compound poke succeeds, Invoke fires — 6 of 7 open [S]
   questions in one flight with ZERO HP mutation.
2. **`vsai-a1-mindash`** — Ability3+DashHit+REPS=4. Matches E4T-A9 proven config with attacker
   swapped bot→player. Predicts minion 100→0.
3. **`vsai-a1`** — LMB (Ability1)+MeleeHit+REPS=8+TARGET=minion. Adds Selector sub-spell
   variable; if NO_INSTANCE, fall back to `-mindash` to isolate.
4. **`vsai-a1-player`** — TARGET=1 (player). Only after minion works. Watches FK-32 carefully.

## Globals to add (workflow references)

The workflow's design references `g_bfE4Target` and `g_bfHero` — these don't exist yet as
globals. To integrate:
- Add `static uintptr_t g_bfE4Target = 0;` near top of BF section
- Modify `BfE4SpawnSeedTarget` (line ~24430) to store `minion` into `g_bfE4Target` before returning
- Add `static uintptr_t g_bfHero = 0;` (or reuse `s_bfHero` at line 25946)
- Set `g_bfHero = hero` at the top of `DoBotFight` (or in the K_GRANT block)

## Expected success (from workflow)

```
[VSAI] STATION1 bot=0x... botAsc=0x... netsim=0
[VSAI] STATION2 target=0x... kind=minion
[VSAI] STATION3 abilCls=0x...(GS_Ronin_MiniDash_Charges_C) prop='Ability3'
[VSAI] STATION4 GRANT ok handle=1 Items 0->1
[VSAI] STATION5 inst=0x... (Items[1].Rep.Data[0])
[VSAI] STATION6 poke ok: phase 0->2 curPhase 0x0->0x<warmupSubobj>
[VSAI] STATION7 ProcessEvent(Invoke) ok
[VSAI] STATION8 hits applied=4 faulted=0 (of 4)
[VSAI] STATION9 restore=ok
[VSAI] ==== RESULT=HITS_ALL_APPLIED ==== hitsApplied=4 hitsFaulted=0 restore=ok
```

Loki.log corroboration expected:
```
LogAbilitySystem: Property Health new value is: 0.00  (or intermediate)
LogAbilitySystem: Invoking Execute GameplayCue for Default__GE_Ronin_MiniDash_Damage_C
```

## Pre-registered null meanings

Full 15-entry table in the workflow synthesis JSON. Key ones:
- `NO_BOT` → Track D didn't populate g_trackdBot
- `NO_BOT_ASC` → bot+0xF00 offset wrong for this build
- `NO_ABIL_CLASS` → bot's class chain doesn't inherit Ronin's hero class
- `GRANT_FAILED` → K_GRANT on bot ASC (untested — bot ASC vtable may differ)
- `NO_INSTANCE` → GiveAbility → CreateNewInstanceOfAbility doesn't populate Rep.Data[0] for bot
- `NO_WARMUP_SUBOBJ` → +0xF20 not populated on bot instance (would refute class-level invariant)
- `HIT_FAULTED` → damage verb has attacker-context assumptions that break for AAIController

## Cost budget

- Session S191 total: 2 launches (1 lost to FK-31 staging), 6 productive injects into 1 PID
- VSAI-A1 estimate: 1-2 launches (readonly is ~1 flight; if bot ASC quirks emerge, another for mindash)

## What survives from S191 (unchanged, byte-identical when KBFVSAI=0)

- KBFE4T_* stack (KBFE4T_POKEPHASE, KBFE4T_POKECURPHASE, KBFE4T_CALLDASHHIT, KBFE4T_DASHHIT_REPS,
  KBFE4T_DASHHIT_INTERVAL_MS, KBFE4T_HITVERB, KBFE4T_SEQUENCE, KBFE4T_CHANNEL)
- KBFABIL by-name FindObjExact fallback (enables direct sub-ability grant)
- e4-t through e4-t-a9-lmb-probe + e4-t-lmb-a9 build variants
- s_bfHero global (line 25946) — VSAI can reuse

## Files ready to reference

- `docs/s191-vsai-a1-workflow-synthesis-wf_368c3732-8e0.json` (425 lines — full design)
- `docs/s191-e4t-a9-flight1-RESULT.md` — MiniDash kill mechanism
- `docs/s191-e4t-lmb-a9-flight1-RESULT.md` — LMB kill mechanism
- Prior Track D docs: `docs/s190-trackd-bot-killed.md`

## Recommended session opening

1. Read this handoff + the S191 E4T RESULTs.
2. Read the workflow synthesis JSON for the full ~150-line code delta + preconditions.
3. Implement globals (`g_bfE4Target`, maybe `g_bfHero`) as prep.
4. Add BsVsaiPuppetCast (paste from synthesis, adapt SEH_FILTER macro shape:
   `SEH_FILTER(GetExceptionInformation())`).
5. Add invocation site in BsLadderStep after BsTrackDKill call.
6. Add 4 build variants to build.ps1.
7. Build `-readonly` first — verify parent-gate byte-identity via `text_digest.py --dupes`.
8. Launch + stage (gft/fo/sp) + inject `-readonly` — expect `RESULT=READONLY_INVOKE_OK`.
9. If OK, inject `-mindash` on same PID (or fresh) — expect `RESULT=HITS_ALL_APPLIED` + minion HP 100→0.
10. If OK, inject `vsai-a1` (LMB) then `vsai-a1-player` per progression.
