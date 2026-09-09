# S189-BOT — **★★★★★★★ A FLOOR-SPAWNED LOKI BOT COMES UP WALKING AND WALKS UNDER ITS OWN AI; THE +0xF08-ONLY PLAYER WALKS UNDER WASD AT EXACTLY ITS SEED. BOTH ON THE TUTORIAL FLOOR IN ONE WORLD.**

**Date:** 2026-09-09 (~15:35–16:04). **Session:** S189-BOT bot-playability (the "vs AI" half of the mission).
**Design provenance:** workflow `wf_9b8a8446-b39` (6 Understand + 1 Design + 3 adversarial Verify + 1
Adjudicate; 5.76M subagent tokens, ~58 min). Full result preserved at
`scratchpad/s189-bot/evidence/01-workflow-wf_9b8a8446-b39.json` and `02-final-design.md`.
**Pre-registration:** `docs/s189-bot-botplay-floor-f1-PREREGISTERED.txt`, committed `0327648` BEFORE the flight.
**Arm:** `botplay-floor-tinykick` RAW `ec5317d71bc7bf90` VSIZE `0cbac5b523c2eb62`, verify_dll PASS (KERNEL32-only).

## HEADLINE

> **[M] THREE first-in-project results, two of them the whole point of the session:**
>
> **1. A floor-spawned `SpawnAIFromClass` LokiBot comes up `MOVE_Walking` at possess time.**
> `[SNP] BOT-before MovementMode@0x231=1 (MOVE_Walking)`, GravityScale 1.0, Velocity (0,0,0), at the
> spawn point (1356,-409,90.15). `[RCPT] GETTER_BOT_AFTER_G mode=1 MaxSpeed=43F38000(487)`. This
> **settles the S136-vs-S138 hover contradiction**: LokiBots hovered at (600,0,13240) since S138 because
> they were spawned in the AIR; spawned on the floor, `SetDefaultMovementMode`'s `FindFloor` succeeds and
> the bot is Walking before it ever ticks. The air-vs-floor spawn is the whole difference.
>
> **2. The bot walked ~2135 uu under its own AI wander, on the floor, with NO velocity kick.**
> `[SNP] BOT loc (-288.5,954.7,-541.0) moved 2227.685 uu` at the first worker sample, ~6-8 s after the
> game thread freed; `|Acc|=50000` rotating through many headings, `AnalogInputModifier=1`,
> `[SNP] FALLBACK NOT NEEDED at sample 8: bot max |Vxy| over samples 0..7 = 246.9 >= 5.0 with NO kick
> written -> AI-driven`. `fallbackFired=0`. Then it walked off the island edge and fell (the S140 behavior).
>
> **3. The `+0xF08`-only K1-wired PLAYER walked under WASD at EXACTLY its seeded 487 uu/s.** This is the
> UNFLOWN wiring the design graded `[S]` in advance — the player's `+0xF00` left as the live KWIREGAS ASC,
> only `+0xF08` pointed at the CDO attribute set. `[GASX] ARM K1 done: PLAYER storages written 1/3`,
> `MASKED OUT` for +0xF00/+0xF10. W drove `AccY=-50000`, the player slid off the ledge to the floor
> (Z 386 -> 90.15, Mode 3->1) and walked with `|Vxy|` pinned at **487.0** — 690 Walking samples,
> in-shim `[SNP] PLR ... atCap=BAND delta=0.000e+00`. **The K1-broke-input signature did NOT fire.**
>
> ⇒ **THE FIRST VERSUS-AI STATE: a player hero (WASD-driven) and an AI-controlled enemy hero
> (AI-wander-driven) both alive and MOBILE, both Walking on the tutorial floor, in the SAME world.**
> ⚠ They walked a few seconds apart, not at the identical instant (the bot left the floor ~4 s before the
> player's fall+slide put it on the floor). Strict simultaneity (P8) was NOT captured.

## Flight ledger

| flight | outcome |
|---|---|
| **F1** | ★★★★★★★ **SUCCESS.** Full receipt chain; bot Walking-at-spawn + AI walk; player walked at 487; both on the floor in one ~15 s window. FK-32 at 289 s (4th manual-map), everything captured. |
| **F2** | **SUCCESS (reproduction).** Same chain. The fixed external watcher (direct discovery) caught the bot already off-floor and falling (`(2166,-825,-204)` Mode 3, Vel2D 301 decaying) — confirming the bot walks off from (1356,-409) within ~2 s, faster than any sampler starts. Player fell in ~5 s (vs ship-f1's 115 s) thanks to the 1 uu/s tiny seed. FK-32 ~289 s. |
| F3 ×3 | FK-31 staging deaths (0xC0000005 after `fo`, only gft+fo resident) — base-rate ~27% hazard, three in a row. The `--pawn/--cmc` direct-address watcher (the fix for a dense on-floor bot sample) never got to run. Campaign stopped. |

## Regression gates (P0, MEASURED before the flight)

All nine re-baselined gates rebuilt **BYTE-IDENTICAL** after the source edit
(`scratchpad/s189-bot/evidence/00-before-state-digests.txt`):
`botai b620e0ff3279e673`, `gasattr 29f0fa4efffd01da`, `gasattr_ctrl 4c0ede610baa4629`,
`play 31af7667355f39d1`, `armk 3ff3ba9f77ae1438`, `axisab 01593c0f8f73f1ae`,
`sentinel_big 8347a0df17354239`, `-seedmax b47d1bfd04e44921`, `-mv-play 87c764b6d235b7a3`.
⚠ **The CLAUDE.md-recorded values (`botai 5e47c13cf7f0a158`, `gasattr 2fcc2536e21f18e3`,
`gasattr-ctrl 4465ebc4d7168c03`, `play 9bc10a4552c596e1`) DO NOT reproduce from HEAD `4e2f609` and were
stale BEFORE this session touched anything** — the shim source drifted (the S176 VEH-cleanup commit
`4824c77` touches the shared Worker-exit path in every variant). The above are today's HEAD before-state.
New variants (all distinct, no new `--dupes` group): `botplay-floor a37b5a982e522e61`,
`botplay-floor-tinykick ec5317d71bc7bf90` (flown), `botplay-floor-noai d476b0ab1c0c29af`,
`botplay-floor-5th 1dec9197251762fc`, `botwalk 2440b831eaf531af`. Literal control passes.

## Pre-registered predictions vs measured (Flight 1)

| # | prediction | measured | verdict |
|---|---|---|---|
| P0-BASELINE | 9 gates byte-identical; new variants distinct | ✅ all 9 identical, 5 new distinct | ✓ |
| P1-SPAWN | FLOOR OVERRIDE -> (1356,-409,90.15); dCtl=1 dHero=1; one bot | ✅ `spawnLoc (600,0,13240) -> (1356,-409,90.15)`, `census A2 BotOrAIController-chain=1 LokiHeroCharacter-chain 2->3`, `[BS] done ... dCtl=1 dHero=1` | ✓ |
| P2-WALKING-AT-SPAWN | [I~0.8] BOT-before Mode=1, Z~90.15, TSF=0 | ✅ **Mode=1 (MOVE_Walking), GravityScale 1.0, Velocity (0,0,0)** at the floor point | ✓ **[M] — the central new result** |
| P3-AI-FROM-REST | [I~0.5] AI drives the bot, no kick, rotating Acc | ✅ moved 2227 uu, `|Acc|=50000` rotating, AIM=1, `FALLBACK NOT NEEDED`, `fallbackFired=0` | ✓ (but the dense on-floor velocity was not sampled — see gap) |
| P4-BOT-CAP-IN-BAND | bot cap in the 487 band + [RCPT] MaxSpeed=43F38000 | ⚠ **PARTIAL**: `[RCPT] GETTER_BOT_AFTER_G MaxSpeed=43F38000(487)` (wire correct) + 2135 uu displacement, but the worker sampler started ~10 s post-arm and only caught the Falling-decay tail (peak 246.9). No dense Walking sample at 487. | ⚠ [M] wire, [I,strong] "walked at 487" |
| P5-PLAYER-WIRING | 1/3 masked, f00 unchanged KWIREGAS ASC, f08=CDO set, MaxSpeed=487 | ✅ `PLR ... MASKED OUT` for +0xF00/+0xF10, `written 1/3`; `[RCPT] GETTER_PLR_AFTER_K1 f00=0x21314BCCD00 (unchanged) f08=0x211965B1710 (==BOT's) MaxSpeed=43F38000` | ✓ |
| P6-PLAYER-SEED-AND-FALL | seed (0,-1,0) + K2 grav 0->1; player falls to the ledge | ✅ `ARM J: PLAYER Velocity=(0,-1,0)`, `ARM K2: GravityScale 0->1`; fell 13240 -> ledge 386 in ~5 s (F2: ~5 s; ship-f1 hover was 115 s) | ✓ **the 1 uu/s seed broke the hover** |
| P7-PLAYER-WALKS-UNDER-WASD | [S] UNFLOWN K1 wiring accepts WASD | ✅ **[M]** W -> `AccY=-50000`, slid off ledge, Mode 3->1, Z=90.15, `|Vxy|=487.000` (690 Walking rows, peak 487.0004, in-shim `[SNP] PLR atCap=BAND delta=0.000e+00`). **K1-broke-input did NOT fire.** | ✓ **the biggest [S] resolved** |
| P8-BOTH-WALKING | >=1 pair of rows within 0.2 s both Mode=1 |Vxy|>300 | ⚠ **NOT captured** — bot floor-walk ~15:38:43–51, player floor-walk from ~15:38:55; ~4 s apart. Both Walking in the same ~15 s window, not the same instant. | ⚠ |
| P9-HEALTH | no 0xDEAD before probe+120 s; canaries 0 | ✅ FK-32 at 289 s (probe+~120 s), 0 Fatal, 0 crashpad, A0==A1 | ✓ |

## The raw trajectories (Flight 1)

**Player (WASD), from the player-watcher CSV + the in-shim [SNP] PLR samples:**
```
t=26.8  grav 0->1, seed (0,-1,0)           Z=13240  Mode=3
t=32.2  fall begins  Vz=-637               Z=13102  Mode=3
t=36.3  landed on the ledge                Z= 387   Mode=3   (R-S189-MV-WASD-h: a fall lands on a ledge)
t=47.3  W-hold slides it off the ledge     Z= 386   Mode=7->3  AccY=-50000
t=48.4  landed on the tutorial FLOOR        Z= 90.150 Mode=1   V=(-0.01,-487.00,0)  <- 487 CAP, bit-exact
t=50.2  W walks +X                          Z= 90.150 Mode=1   V=(487.00,0,0)  A=(50000,0)
...     (487 in every axis: (487,0),(0,487),(-487,0),(-346,-342) diagonal ...)
end     (-1581,-2810,240) Mode=1   peak |Vxy| = 487.00043   690 Walking samples
in-shim [SNP] PLR i=12: |Vxy|=487 mode=1 Z=90.150 delta=0.000e+00 atCap=BAND   (bit-exact 487)
```
**Bot (AI wander), from the in-shim [SNP] BOT samples:**
```
BOT-before (game-thread hold): Mode=1 (Walking), GravityScale 1.0, Velocity (0,0,0)  at (1356,-409,90.15)
[RCPT] GETTER_BOT_AFTER_G: mode=1, f08=CDO set, MaxSpeed=43F38000(487)
sample 0 (~arm+10s): BOT loc (-288.5, 954.7, -541.0)  moved 2227.7 uu   (2135 uu HORIZONTAL walk + fell 631)
                     |Vxy|=246.9 (decay tail) mode=3  |Acc|=50000 rotating  AIM=1
FALLBACK NOT NEEDED at sample 8  (max |Vxy| over 0..7 = 246.9 >= 5.0 -> AI-driven, no kick)
```
**Flight 2 bot (direct external watcher, 100 ms, caught it after the walk-off):**
```
first sample (2166,-825,-204) Mode=3 Vel2D=301 decaying -> converges to (2522,-1007) horizontally,
falls to Z=-53000. Confirms the bot walked ~1200 uu off (1356,-409) before the watcher's slow
GUObjectArray discovery could start sampling.
```

## What this settles, and what it does not

**SETTLED [M]:**
1. **A floor-spawned LokiBot is Walking at possess time.** This closes the open question in every prior
   S138–S141 doc ("why do LokiBots hover at (600,0,13240) with V=0?"). Answer: they were spawned in the
   AIR. `SetDefaultMovementMode(DefaultLandMovementMode=Walking)` runs `FindFloor` at the spawn transform
   (engine `0x35F9B30`/`0x35E01D0`, both real, not Loki-overridden); over the tutorial floor it sets a
   MovementBase and does NOT revert to Falling. The design's spawnloc lane predicted this from the bytes
   and it landed exactly.
2. **The bot walks under its own AI on the floor with no kick.** Rotating `|Acc|=50000` + AIM=1 +
   `FALLBACK NOT NEEDED` + 2135 uu horizontal displacement. The velocity-gated fallback (ARM M) correctly
   printed AI-driven and wrote no kick.
3. **The `+0xF08`-only K1 player is WASD-drivable and movement-equivalent to the flown `-mv-play`
   spawnedSet0 wire.** The player walked at exactly 487, its `+0xF00` left as the live KWIREGAS ASC. This
   was the design's biggest `[S]` (UNFLOWN) and it is now `[M]`.
4. **The 1 uu/s tiny -Y player seed broke the post-GravityScale hover in ~5 s** (vs ship-f1's 115 s) — a
   velocity above the 2-D `SizeSq2D` gate makes `PhysFalling` integrate gravity promptly.

**NOT settled / gaps:**
- **The bot's peak velocity == 487 bit-exact was NOT directly sampled during Walking.** It is `[M]` for the
  wire (`[RCPT]=487`) and `[I,strong]` for "walked at 487" (2135 uu in ~6 s ≈ 355 uu/s average with peaks
  near the cap). The bot walks off (1356,-409) within ~2 s — faster than the worker sampler (starts ~10 s
  post-arm) or the external auto-discovery watcher (~2-4 s GUObjectArray sweep) can catch it. The fix (a
  direct-address `--pawn/--cmc` watcher started at the `[SNP] BOT` marker line, during the game-thread
  hold) is coded and ready but the three F3 attempts all died in FK-31 staging.
- **Strict both-walking simultaneity (P8) was not captured** — the bot left the floor ~4 s before the
  player arrived on it. Both were Walking on the tutorial floor in the same world in the same ~15 s window.

## Instrument findings (banked)

- **motion_watch_bot.py** had a format-string bug (17 tuple values vs 16 `%` tokens → "not all arguments
  converted", zero CSV rows on flight 1). Fixed (17 tokens). Compiles.
- **The bot's on-floor Walking window is ~2 s** from (1356,-409) — too short for either the in-shim worker
  sampler (starts ~10 s post-arm: A2 census 4.5 s + FsDisarm 3.8 s + first Sleep 1 s) or the external
  auto-discovery watcher (GUObjectArray sweep ~2-4 s). **To sample it: read the bot pawn/CMC from the
  `[SNP] BOT` marker line (printed DURING the game-thread hold) and start a direct-address watcher then.**
- **FK-31 staging is base-rate ~27% and clusters** (three F3 deaths in a row, ~2%). Budget ≥2 launches per
  intended armed window; a run of failures is variance, not a systematic change.

## Method rules to bank (R-S189-BOT-a..d)

- **R-S189-BOT-a:** a `SpawnAIFromClass` LokiBot spawned at a measured floor rest point comes up
  `MOVE_Walking` at possess time; spawned in the air it comes up `MOVE_Falling` and hovers with V=0. The
  air-vs-floor spawn is the whole difference behind the S138–S141 "the bot does not move" wall — the
  bot's AI and mover were never broken, it was spawned 13 km up.
- **R-S189-BOT-b:** wiring only `hero+0xF08` to a (CDO or spawned) `ULokiAttributeSet` with the six
  movement attributes is sufficient for WASD-driven walking at the seeded MoveSpeed; `+0xF00` (the ASC)
  need not be touched, and leaving it as the live bound ASC avoids orphaning it. The `-mv-play` spawnedSet0
  wire and this CDO-set wire are movement-equivalent.
- **R-S189-BOT-c:** a floor-spawned AI bot walks off the island edge within ~2 s under random wander, so
  the S140 "walks 13,000 uu" figure is dominated by the fall; the on-floor horizontal walk is ~2000 uu.
  To sample the bot at its cap, start a direct-address watcher at the `[SNP] BOT` marker line during the
  game-thread hold — auto-discovery and the worker sampler both start too late.
- **R-S189-BOT-d:** a 1 uu/s velocity seed above the `PhysFalling` 2-D `SizeSq2D` gate breaks a
  post-GravityScale rest hover in ~5 s; without it the hover can last 100+ s (ship-f1), longer than the
  ~150 s armed window.

## Files

- `docs/s189-bot-botplay-floor-f1-PREREGISTERED.txt` — the pre-registration (committed `0327648`)
- `scratchpad/s189-bot/evidence/s189bot-f1-marker-FINAL.txt` — the 631-line canonical receipt chain
- `scratchpad/s189-bot/evidence/s189bot-f1-player-motion.csv` — the player's 487 walk (1160 rows)
- `scratchpad/s189-bot/evidence/s189bot-f2-bot-motion.csv` — the external watcher's bot fall-decay trace
- `scratchpad/s189-bot/evidence/s189bot-f{1,2}-crashwatch.log` — FK-32 exit signatures
- `scratchpad/s189-bot/tools/motion_watch_bot.py` — the (fixed) bot watcher; `marker-shadow.ps1` — FK-25 defence
- `scratchpad/s189-bot/evidence/01-workflow-...json` / `02-final-design.md` — the design workflow output
- `dumps/s189bot-f1/`, `dumps/s189bot-f2/` — dumpimage snapshots (pure RPM, taken mid-flight)

## Still open — the next flight

1. **Dense bot 487-cap sample (P4):** re-fly `botplay-floor-tinykick` with the direct-address bot watcher
   started at the `[SNP] BOT` marker line (the code is ready; F3 never staged). One clean staging catches it.
2. **A more central bot spawn** (e.g. deep in the player-proven-walkable box X∈[-900,950] Y∈[-2100,-250]
   Z=90.15) would give a longer on-floor walk and a real both-walking overlap (P8). Needs a new
   `KBSAILOC_*` variant (one build.ps1 line).
3. **Ship path:** a `botplay-floor` default-set arm that spawns a walking bot alongside the `-mv-play`
   player would make "player + walking enemy" a one-launch observable — but it is a diagnosis (process-wide
   CDO poke), not a shipping fix.
