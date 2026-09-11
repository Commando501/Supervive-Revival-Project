# Fresh session opening prompt — S189-MV WASD input hookup

**Paste this whole file into the fresh session as the opening user message.**

---

You are continuing work on the SUPERVIVE Revival Project. Read `CLAUDE.md` in full before doing anything. The last session (2026-09-09) flew **S189-MV** which unlocked the S141 T3 movement wall end-to-end via one seed + one pointer-poke. Full evidence: `docs/s189-mv-f1-MOVEMENT_UNLOCK.md`. Commit `3a9eb17` on branch `dedicated-server-stub`.

**Your task this session: fly the WASD input hookup — the direct test of whether the player MOVES on the live game with the S189-MV mechanism applied.** The S189-MV evidence doc's "Still open" section lists this as follow-up #2 (highest-value).

## Current live state (as of session close 2026-09-09 ~10:11)

- **Game IS STILL LIVE**: PID 1780 (verify with `Get-Process -Name SUPERVIVE-Win64-Shipping`). Uptime was 272s at close — should still be alive when you take over.
- **AGS backend running**: verify with `Get-Process -Name ags`.
- **S189-MV-wiref08 already staged into PID 1780**: `hero+0xF08` is currently wired at `spawnedSet0=0x19318915BC0`, and that set holds the seeded movement attrs (MoveSpeed=500, MaxMoveSpeed=500, MaxAcceleration=45000, GroundFriction=8, BrakingDecelerationWalking=2048, Mass=100). `GetMaxSpeed()` returns **500.0f** on this process (byte-verified in `docs/s189-mv-f1-marker-final.txt` line 43). `GetMaxAcceleration()` returns **50000.0f** (engine Super's stock CMC UPROPERTY, because MovementMode=3 MOVE_Falling takes the Super-bypass arm).
- All commits pushed to `dedicated-server-stub`. Working tree matches HEAD except for the standing dirty files documented in the S150 override block at the top of CLAUDE.md (unrelated to this work).

## The one question this flight answers

**With `GetMaxSpeed() = 500` and `GetMaxAcceleration() = 50000` both proved live on the KWIREGAS player hero, does driving WASD input via natural input (S158-style Tab/Tab/WASD via P/Invoke) make the player CHARACTER MOVE across the world?**

Three possible outcomes, pre-register these BEFORE flying:

1. **Branch A — PLAYER WALKS** ★★★★★: hero X/Y coordinates change under WASD input at a rate consistent with 500 uu/s cap. `Loki.log` shows nav/movement traces. This proves the seed-and-wire mechanism unlocks a fully drivable player mover on this build. Next arm becomes "port to bot" (SpawnAIFromClass pawn).

2. **Branch B — PLAYER STAYS PUT despite WASD input reaching the game** [I,strong risk]: input registers (Loki.log shows LookAt/InputAxis traces) but the mover produces no translation. Points at a downstream blocker after GetMaxSpeed/GetMaxAcceleration — likely `AnalogInputModifier=0` on the player (S141 T3 [M]) still causing `CalcVelocity`'s clamp to zero the input on the ACCELERATE branch. Cheapest follow-up: also seed `AnalogInputModifier@+0x??` on the CMC or on the attribute set — locate its offset first.

3. **Branch C — INPUT NEVER REACHES THE GAME**: WASD keystrokes don't produce any input-axis traces. Points at focus / window / IME issue, unrelated to the seed. Retry with S158's exact focus-race workaround (retry N times per keystroke).

## Recommended flight design

**Prerequisite: read `docs/s158-wallp-natinput-settled.md` in full** — it's the natural-input reference. Key mechanism: `scratchpad/s158/tools/s158-send-shift.ps1` uses P/Invoke `keybd_event` after `SetForegroundWindow` on the game HWND. Same primitive works for WASD.

**Recommended: reuse PID 1780 if alive.** The seed and wire are already applied. Skip staging entirely. Just send WASD. If the game died, restart from a clean launch + stage the `mv-obs-wiref08` DLL.

**Discriminator design (ULTRACODE — use a workflow):**

Author a `s189-mv-wasd-design` workflow with these Understand agents:
- (a) `s158-natural-input-mechanism`: extract S158's SendShift → keybd_event mechanism verbatim
- (b) `wasd-input-mapping`: what UE virtual keycode does WASD map to on this build? Grep bindings in the shipped inputs
- (c) `motion-observation`: how does the S141 T3 arm observe hero X/Y translation? `motion_watch.py`? `drop_ride_readout.py`? What's the correct read-only RPM probe for player-hero displacement over time?
- (d) `AnalogInputModifier-status`: is it a UPROPERTY on the attribute set (offset TBD) or on the CMC (offset TBD)? S141 T3 says `= 0 on PLAYER, 1 on BOT`. Locate the offset via `PropOffsetSuper` or CMC layout scan.
- (e) `WASD-observability`: what Loki.log categories/lines confirm WASD reaches the input axis? `LogInput`, `LogLokiPlayerController`, or per-frame accel/velocity traces?

Then Design + adversarial Verify (input-side + observation-side attacks).

**Then implement:**
- `scratchpad/s189-mv/tools/send-wasd.ps1` (P/Invoke primitive, hold-and-release, mirrors S158)
- `scratchpad/s189-mv/tools/motion-watch-player.py` (read-only RPM tight-sample of hero X/Y at 100ms cadence — 30s or 60s duration)
- No new shim needed if the mv-obs-wiref08 DLL is already in-process. If we need a fresh flight (game died), it's the same variant `botfight-damage-self-cal-bindavatar-seedmax-mv-obs-wiref08` (RAW `8623bb672d86a66d`, already built).

**Fly:**
1. Start motion-watch-player.py in the background BEFORE sending WASD (per motion-observation project rule).
2. Send W+D held for 3s via keybd_event.
3. Release keys.
4. Send S+A held for 3s.
5. Read motion samples. Interpret vs the 3-branch discriminator.

**Evidence + commit:**
- `docs/s189-mv-wasd-flight1-*.md` (PLAYER_WALKS or DIDNT_MOVE or NO_INPUT depending on outcome)
- Preserve motion-watch samples
- Update CLAUDE.md WALL P S156-B block with the WASD result
- Commit + push

## Ultracode

Ultracode is on. Author a workflow for the design phase. Do NOT skip adversarial verification — the last two flights (S189-SEED and S189-MV) BOTH caught real critical defects in the design via adversarial verifiers (s_seeded.asc bug caught by S189-SEED verify; MaxAcceleration 50000-stock-collision caught by S189-MV verify). Both defects would have burned a live flight if they'd reached the game.

## Key evidence to read first

1. `CLAUDE.md` (full digest, especially the WALL P S156-B block ending with the S189-MV entry).
2. `docs/s189-mv-f1-MOVEMENT_UNLOCK.md` (the flight that just closed the movement wall's "why 0?" question — the "Still open" section names your task).
3. `docs/s158-wallp-natinput-settled.md` (natural-input primitive template; the `scratchpad/s158/tools/s158-send-shift.ps1` is your P/Invoke starting point).
4. `docs/s141-tier3-settled.md` (movement-wall model — read §4 to understand what's downstream of GetMaxSpeed/GetMaxAcceleration; `CalcVelocity` MaxInputSpeed clamp is the leading Branch B candidate).
5. `docs/s189-seed-f3-MANASHOT_APPLIED.md` (immediate prior flight — establishes the direct-offset seed mechanism this depended on).

## Reusable rules banked

- **R-S189-MV-a**: pre-registered discriminator on stock-collision values — pick non-stock seed values that CANNOT be produced by any code path other than the seed. (Caught the 45000-vs-50000 case last flight.)
- **R-S189-MV-b**: validate vtable identity before direct dispatch.
- **R-S189-MV-c**: Loki override asymmetry across MovementMode arms — the same getter can have different read paths per mode.

Apply these to the WASD flight's motion-observation design.

## Do NOT

- ⚠ Do NOT re-run the S189-MV workflow — the design is settled and the DLL is already built + tested.
- ⚠ Do NOT relaunch the game if PID 1780 is still alive. The seed+wire is already applied and free reuse is worth ~2 min of staging + a fresh FK-31 hazard.
- ⚠ Do NOT poke `MovementMode` from 3→1 (Walking) before observing the Falling-arm behavior — that's a separate follow-up (evidence doc still-open #1). WASD-on-Falling is the primary interesting case (hovering-and-flying-around vs stuck).
- ⚠ Do NOT chase the CMC's own MaxAcceleration UPROPERTY offset (still-open #3) as the FIRST move — the WASD flight settles whether we NEED to.
- ⚠ Do NOT declare victory on Branch A without also confirming the player's Z coordinate stays roughly constant (walking should not fall through the world) AND that `Loki.log` shows no Fatal/crashpad within 90s.

## Session convention reminders

- Full session ledger in CLAUDE.md's WALL P S156-B block (adds top-down, latest at the top). Add the WASD entry after the S189-MV entry when you commit.
- Commit format: `S189-MV-WASD f1 [grade]: <headline>`.
- Sign off commits and PRs per CLAUDE.md attribution guidance (Co-Authored-By: Claude Opus 4.7).
- Read `docs/method-rules.md` if unsure whether to record an observation as [M] / [I,strong] / [I] / [S] — every prior "wait was this measured?" turned into a real learned rule.

## Session progress mission

This is the FOURTH consecutive flight in a chain (S189 mana f2 → S189-SEED f3 → S189-MV f1 → S189-MV-WASD f1) each of which produced [M]-grade forward motion on a wall that was open for months. Each flight cost 1-2 launches. Keep the momentum. If Branch A hits, immediately design the bot-pawn port arm (SpawnAIFromClass, DS-hybrid ARM G recipe — evidence doc still-open #4) as the next flight in the same session.

If context runs low, produce a fresh handoff prompt for the next session before you lose it.
