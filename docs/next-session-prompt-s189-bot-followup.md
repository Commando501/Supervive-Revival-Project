# Fresh session opening prompt — S189-BOT follow-up (dense bot 487-cap sample + both-walking overlap)

You are continuing the SUPERVIVE Revival Project. Read `CLAUDE.md` in full first.

## What landed last session (2026-09-09, all [M])

Read `docs/s189-bot-botplay-floor-RESULT.md` first. Three first-in-project results:
1. **A floor-spawned `SpawnAIFromClass` LokiBot comes up `MOVE_Walking`** at possess time (settles the
   S136-vs-S138 hover mystery: LokiBots hovered because they were spawned 13 km up in the air).
2. **The bot walked ~2135 uu under its own AI wander, no kick**, then off the island edge.
3. **The `+0xF08`-only K1-wired PLAYER walked under WASD at exactly its seeded 487 uu/s** (the design's
   biggest UNFLOWN `[S]` resolved; `+0xF00` left as the live KWIREGAS ASC).

⇒ THE FIRST VERSUS-AI STATE: a WASD-driven player and an AI-driven enemy both Walking on the tutorial
floor in the same world — but a few seconds apart, not simultaneously.

Arm `botplay-floor-tinykick` RAW `ec5317d71bc7bf90` (built, flown F1+F2). Commit `0327648` has the
pre-registration + source (5 new knob-gated variants, all 9 gates byte-identical). Design workflow output
at `scratchpad/s189-bot/evidence/0{1,2}-*`.

## Two gaps this session should close (both cheap; NO rebuild for #1)

**GAP 1 — the bot's peak velocity == 487 bit-exact was NOT densely sampled during Walking.** The on-floor
Walking window from (1356,-409) is only ~2 s; the worker sampler starts ~10 s post-arm and the external
auto-discovery watcher's `GUObjectArray` sweep starts ~2-4 s late. **The fix is coded and ready:** start
`scratchpad/s189-bot/tools/motion_watch_bot.py` with `--pawn <hex> --cmc <hex>` (skips discovery, samples
at 100 ms) the instant the `[SNP] BOT pawn=0x... CharacterMovement@0x... = 0x...` line appears in the live
marker — which is printed DURING the game-thread hold, before the bot ticks. The F3 orchestration in last
session's transcript does exactly this; it just never staged (3× FK-31). One clean staging catches it.
Success: a bot CSV row with `Mode=1` and `Vel2D` in the 487 band while `|Acc|=50000` rotates.

**GAP 2 — no strict both-walking overlap (P8).** The bot leaves the floor ~4 s before the player's
fall+slide arrives. A MORE CENTRAL bot spawn (deep in the player-proven-walkable box: X∈[-900,950],
Y∈[-2100,-250], Z=90.15 — the player walked (683,-716)→(953,-2108) and (147,-511)→(-776,-1472) all at
Z=90.15) gives a longer on-floor walk and a real overlap. Needs ONE build.ps1 line: a
`botplay-floor-central` variant identical to `botplay-floor-tinykick` but with e.g.
`-DKBSAILOC_X=0.0 -DKBSAILOC_Y=-1200.0 -DKBSAILOC_Z=90.15` (verify the point is floor first — pick one the
player CSV actually walked THROUGH at Z=90.15, e.g. (683,-1379,90.15) from F3). Combine with GAP 1's
direct-address watcher.

## The flight (same as last session's F3 orchestration, which is correct)

1. `launch-redirect.ps1 -NoHook`; wait for the game PID + base.
2. Start `scratchpad/s189-bot/tools/marker-shadow.ps1 -EvDir <ev> -Label s189bot-cN -Seconds 700` (FK-25).
3. `fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_botplay_floor_tinykick.dll -Label s189bot-cN`
   (or the `-central` variant). Budget ≥2 launches — FK-31 staging is ~27% and clusters (3 in a row last time).
4. At `[SP] done`: parse `spawnedPawn` + `[LIFT] gravity OFF (CMC=0x...)`; start `motion_watch_player.py`.
5. **At the `[SNP] BOT pawn=... CharacterMovement@... = ...` line (during the hold): start
   `motion_watch_bot.py <pid> <base> 120 --pawn <bot> --cmc <bcmc>` IMMEDIATELY** — this is the fix.
6. At `[FS] disarm: restored=...`: send WASD in-process (pre-warm the P/Invoke type first;
   `send-wasd.ps1 -Sequence w,w,w,d -HoldMs 3000 -InterKeyMs 5000 -SyncFile ...`).
7. dumpimage + `movementmode_readout.py <pid> <base>` early (probe+60 s) for a two-pawn snapshot.
8. FK-32 ~289 s after launch (probe+~120 s); capture as you go.

## Do NOT

- Do NOT poke the bot's GravityScale (it's 1.0 on a floor-spawned bot; leave it).
- Do NOT use `botplay-floor` (no player seed) as primary — the 1 uu/s `-tinykick` seed is what breaks the
  player's post-gravity hover inside the ~150 s window (unseeded hover was 115 s on ship-f1).
- Do NOT fly the `botwalk` (air spawn + kick) variant unless the floor spawn fails — it's the S140 shape
  and its bot attribution is indirect.
- Do NOT re-derive the K1-broke-input question — F1 [M] settled it (the +0xF08-only player walks under WASD).

## Ship path (after the dense sample lands)

A `botplay-floor` arm co-injected with `-mv-play` would make "player + walking enemy" a one-launch
observable — but ARM G is a process-wide CDO poke (a diagnosis, not a shipping fix). A shipping bot needs
its OWN spawned attribute set (not the shared CDO subobject) so a second bot doesn't share caps.

## Regression gates (current HEAD before-state — the CLAUDE.md-recorded values are STALE)

`botai b620e0ff3279e673`, `gasattr 29f0fa4efffd01da`, `gasattr-ctrl 4c0ede610baa4629`,
`play 31af7667355f39d1`, `armk 3ff3ba9f77ae1438`, `axisab 01593c0f8f73f1ae`, `sentinel_big 8347a0df17354239`,
`-seedmax b47d1bfd04e44921`, `-mv-play 87c764b6d235b7a3`. New: `botplay-floor a37b5a982e522e61`,
`botplay-floor-tinykick ec5317d71bc7bf90`, `botplay-floor-noai d476b0ab1c0c29af`,
`botplay-floor-5th 1dec9197251762fc`, `botwalk 2440b831eaf531af`.
