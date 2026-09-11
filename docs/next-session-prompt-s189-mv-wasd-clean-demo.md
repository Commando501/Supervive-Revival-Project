# Fresh session opening prompt — S189-MV-WASD clean Walking-mode demo on the shipping arm

You are continuing work on the SUPERVIVE Revival Project. Read `CLAUDE.md` in full before doing
anything.

The last session (2026-09-09) landed a complete chain culminating in a playable player-hero:
1. **S189-MV-WASD F1** [M] — W drives Acceleration=(0,-50000,0) durably; `tutorial_launch.cpp:3817`
   REFUTED as instrument artifact.
2. **F2b** [M] — AnalogInputModifier=1.0 during W-hold; S141 T3's CalcVelocity clamp REFUTED.
3. **F3** [M] — THE PLAYER WALKED. 2300 uu at bit-exact 500 uu/s = seeded MoveSpeed cap.
4. **SHIPPING ARM BUILT** — `KBFPOKEGRAVITY` knob + `-mv-play` variant, all 10 prior gates
   BYTE-IDENTICAL, verify_dll PASS.
5. **SHIPPING ARM F1** [M] — fresh launch, 10/10 pre-registered predictions, all 9 receipt lines
   land, hero fell 13240→386. **FK-32 at t+342s prevented capturing the Walking-mode WASD half
   in this ONE flight** — but that ingredient was already [M] in F3.

Read `docs/s189-mv-wasd-ship-f1-SHIPPING_ARM_VALIDATED.md` first, then
`docs/s189-mv-wasd-f3-THE_PLAYER_WALKED.md`. Commits `2d0fca6` (ship f1), `051cc08` (ship build),
`8c33cde` (F3), `ae4a51e` (F2b), `8706f27` (F1) on branch `dedicated-server-stub`.

## Your task this session

Fly the **shipping arm** on a **fresh launch** and capture ALL SIX evidence bullets in ONE flight:
1. All 9 shim receipt lines land (S155 → S156 → S189-MV × 7 → POKEGRAVITY)
2. Hero falls 13240 → tutorial-floor Z=90.15 (not just to a ledge at Z=386)
3. MovementMode transitions 3 → 1 (Walking)
4. WASD via P/Invoke drives Acceleration + Velocity + Location displacement in Walking
5. Peak Velocity = exactly 500.000 uu/s (bit-exact MoveSpeed seed)
6. Total horizontal displacement > 1000 uu across the flight

**This is the FIRST-CLASS DEMO that closes the playability arc completely.** Everything is
individually proven; you're stitching them into one clean observation.

## Two known issues from the last shipping flight

Both are ORCHESTRATION defects, NOT arm defects. Fix both before flying:

**(a) WASD child-powershell + Add-Type takes ~35s to start.** The last flight's probe (18s
duration) finished BEFORE send-wasd's `keybd_event` fired the first KEYDOWN. Two fixes:
- **Increase probe duration to 60-90s** so it covers the whole `Add-Type` + focus grab + input
  window. Cost: bigger CSV, longer wait.
- OR **pre-warm send-wasd's C# type** by calling it against a dummy target (e.g. Notepad) BEFORE
  the main flight, so the second invocation reuses the compiled type.

**(b) Hero doesn't automatically fall to Z=90 after GravityScale=1 poke — it lands on a ledge
at Z=386.** F3 got past this by pressing W (which slid the hero off the ledge, causing further
fall to Z=90 and MovementMode transition). The shipping arm's shim-side poke has the same
problem. Options:
- **Wait 15-30s post-arm** for spontaneous physics engagement (F3 saw ~9.5s idle before the fall
  started; may vary). Then send WASD.
- **Poke MovementMode 3→1 directly** via external WPM (byte at CMC+0x231) — same class as
  GravityScale poke, DATA-class safe. But note the shim already knows the CMC address via
  PropOffsetSuper — a further extension `KBFPOKEWALKING` (default 0) could do this in-shim.
- **Fly WASD IMMEDIATELY after the shim's POKEGRAVITY receipt** — F3 showed W input slides hero
  off ledges even in Falling mode; the sliding also transitions Mode to Walking on final landing.

Recommend: increase probe duration to 60s + fly WASD 3-5s after the marker's POKEGRAVITY line
appears. That reproduces F3's timing exactly.

## Recipe

```powershell
# 1. Ensure Steam is running, PowerShell is ELEVATED, no game running
Stop-Process -Name SUPERVIVE-Win64-Shipping,ags -Force -ErrorAction SilentlyContinue

# 2. Fresh launch
cd 'G:\git\Supervive Revival Project'
.\configs\launch-redirect.ps1 -NoHook

# 3. Wait for boot (~40s), then stage
.\configs\fk24-stage.ps1 `
    -Probe 'tools\sigbypass-mod\build\tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax_mv_play.dll' `
    -Label 's189mv-wasd-ship-cleandemo'

# 4. WAIT for [S189-MV] POKEGRAVITY line to appear in docs/tutorial-launch-marker.txt
# 5. Note the LIVE addresses from the marker (hero, cmc from the [S148] owner line)
# 6. Optionally poke MovementMode=1 to skip the "hover ledge for 9.5s" wait
# 7. Start motion probe with LONG duration (60s):
python scratchpad/s189-mv/tools/motion_watch_player.py <PID> <HERO> <CMC> 60 > motion.csv 2>&1 &

# 8. Wait 3-5s (let probe get baseline), then send WASD (pre-warm optional)
powershell -File scratchpad/s189-mv/tools/send-wasd.ps1 -Sequence 'w,d,f13' -HoldMs 3000 -InterKeyMs 2000 -RepeatMs 33

# 9. Read motion.csv for the walk trajectory + peak Vel
```

## What settles the flight as done

- Peak `Vel_2d = 500.000` (bit-exact match to MoveSpeed seed)
- Location delta > 1000 uu horizontal
- Some sample with `MovementMode = 1` (Walking)
- All 3 arms (W, D, F13) fired via send-wasd log
- F13 arm shows all zeros (negative control)

## Do NOT

- Do NOT re-derive whether WASD reaches CIV. F1 [M] settled it — burst-read your CIV column.
- Do NOT poke AirControl or FallingLateralFriction — F3 [M] proved neither is the block.
- Do NOT retry F2's 5-arm sequence — the anomaly is unexplained and reproducing it isn't
  productive; single W-arm is enough.
- Do NOT skip the ELEVATED shell requirement — SetForegroundWindow is denied under UIPI mismatch.
- Do NOT re-run the "test AirControl offset discovery" work — F3 measured it at CMC+0x2B0.

## Beyond this flight

If clean demo lands: consider adding `-mv-play` to a **default variant set** delivered by
`launch-redirect.ps1` (currently `-mv-play` is a manual `-Probe`). A new run mode
`RM_MVPLAY_AUTO` could auto-fire the WASD sequence via an in-shim `SendInput` after POKEGRAVITY
lands, closing the whole loop in ONE inject.

Longer-term open items:
- Understand what triggers PhysFalling to start ticking when Vz=0 (~9.5s spontaneous delay both
  F3 external poke and shipping arm in-shim poke)
- Test D/A/S symmetries in Walking mode (F1 saw D=0 in Falling; unknown in Walking)
- Bot-pawn ARM G port for SpawnAIFromClass path (extends S189-MV to bots)
- Consider `KBFPOKEWALKING` knob (MovementMode 3→1 poke) to eliminate the ledge/hover wait

## Reusable rules banked (add to method-rules.md if you find a new one)

Already banked from this session in `docs/method-rules.md`:
- R-S189-MV-WASD-a: burst-read consumed-per-frame fields
- R-S189-MV-WASD-b: durable derivative beats race-y source
- R-S189-MV-WASD-c: SwitchToThisWindow + AttachThreadInput = focus-grab primitive
- R-S189-MV-WASD-d: auto-repeat @30Hz for keybd_event axis input
- R-S189-MV-WASD-e: shim source comment != measurement
- R-S189-MV-WASD-f: measure the leading hypothesis when it's cheap
- R-S189-MV-WASD-g: single-flight anomalies are not results — reproduce or discard
- R-S189-MV-WASD-h: a fall doesn't always land on the floor
- R-S189-MV-WASD-i: peak velocity = seeded value bit-exact is a discriminator
- R-S189-MV-WASD-j: single-arm test yields compound receipt
- R-S189-MV-WASD-k: shipping arm packages proven-live ingredients
- R-S189-MV-WASD-l: shipping arm validation via receipt + direct-effect fire (not compound downstream)
