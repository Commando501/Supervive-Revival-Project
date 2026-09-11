# S74 B2 — force-open round-advance (LEAD A) recon: GoToPhase + SpawnPlayer found (untried by S68)

User directed: push B2 (force-open) until fully exhausted. S68 exhausted LEAD B's direct spawn
via `SpawnDefaultPawnFor` (4 methods, all failed). This session re-attacked LEAD A (advance the
round past `EGP_BeginInit`) with a full native-UFunction enumeration (new tool `tools/re/class_funcs.py`
— lists ALL UFunctions across a class's super chain, not just net fns), and surfaced concrete callable
native leads S68 never tried.

## Setup (reproducible, all autonomous — no clicks)
- ags: `forceTutorialMatch=true` + `ConnectionDetails.address=""` (S65 HYBRID — interactive.go; the empty
  address makes the client build a valid CoreGameMatchModel + park locally in the pre-game lobby).
- `launch-redirect.ps1 -NoLaunch` (hosts+cacert+ags) then launch the exe detached with the AccelByte
  `-ini:` overrides. Client auto-arms (~1min, "Attempting to travel to Match: Address:''").
- Inject `tutorial_launch_fo.dll` (mmap) → force-open to LVL_Tutorial. **Note: the force-open crash is
  still intermittent** — first attempt this session crashed ~1.7s after "Bringing World LVL_Tutorial up
  for play" (during login/PC-spawn, no "failed to Login" — the S64/S66 intermittent crash). Relaunch+retry.
- Game base (stable): `0x7FF6B54F0000`. RE via `tools/re/*.py` (RPM; take PID + base).

## The round-phase enum (schema.txt ERoundPhase, 12 vals)
`EGP_ServerStartup=0, EGP_BeginInit=1, EGP_Pre=2, EGP_FinishInit=3, EGP_SpawnSelect=4, EGP_SpawnReveal=5,
EGP_Lineup=6, EGP_Combat=7, EGP_Post=8, EGP_Shutdown=9`. Force-open is STUCK at EGP_BeginInit(1); the real
round would step 1→2→3→4→5→6→7. Drop-in/deploy happens somewhere across SpawnSelect..Lineup→Combat.

## ★ Callable native leads (all on the live BP_LokiGameMode_Tutorial_C via inheritance; native thunks @UFunc+0xE0)
Captured live (PID 57360, base 0x7FF6B54F0000) via class_funcs.py + funcparam_dump.py. UFunc/thunk
addresses are per-run (re-capture); signatures are stable.

**LokiRoundGameMode:**
- `GoToPhase(ERoundPhase NextPhase)`  [Native,BPCallable]  — NextPhase = EnumProperty size=1 (1 byte).
  THE phase-transition entry point. Call GoToPhase(4=SpawnSelect) … GoToPhase(7=Combat) to force the
  round to advance through the REAL native transition logic (OnNewPhase side effects, deploy, drop-in) —
  vs S64's raw phase-field poke (which bypasses side effects). ← PRIMARY EXPERIMENT.
- `CheckForRoundComplete`, `CompleteRound`, `RestartRound`, `OnNewPhase`, `ModeSupportsDropPlane`,
  `GetLineupPhaseDuration`, `SetPlayerDisassociationFromPhase` — supporting.

**LokiGameMode:**
- `SpawnPlayer(LokiPlayerState* PlayerState, Transform& SpawnTransform[OUT], Actor* StartSpot,
  bool bEnsurePositionIsValid) -> LokiCharacter* [RET]`  [Native,BPCallable].
  ★ The REAL SUPERVIVE hero-spawn — returns a **LokiCharacter** (the hero), NOT a DefaultPawn. S68 only
  tried the engine `SpawnDefaultPawnFor` (returned null: BP GetDefaultPawnClassForController needs round
  context). SpawnPlayer resolves the hero from the PlayerState's HeroClass. ← SECONDARY EXPERIMENT
  (if GoToPhase alone doesn't drop a hero): call SpawnPlayer(localPC->PlayerState, &xform, StartSpot,
  true) then Controller::Possess(PC, returned LokiCharacter).

**AGameModeBase (inherited):**
- `RestartPlayer(Controller*)`, `RestartPlayerAtTransform(Controller*, Transform&)`,
  `RestartPlayerAtPlayerStart(Controller*, Actor*)` [all Native,BPCallable], `HasMatchStarted`,
  `HasMatchEnded`, `StartPlay`, `HandleStartingNewPlayer`, `PlayerCanRestart`. Standard UE spawn+possess
  fallbacks (RestartPlayer spawns the default pawn + possesses — the engine path S68 didn't call directly).

## Plan (the experiments to exhaust LEAD A)
1. GoToPhase sweep: force-open → call GoToPhase(EGP_SpawnSelect=4), observe (OnNewPhase fires? deploy/drop
   actors? hero spawn? DeadSpectator spam stop?); then step →5→6→7. If the round's real advance triggers
   the drop-in that spawns+possesses the hero → PLAYABLE (the thing S66-68 couldn't force).
2. If phases advance but no hero drops: call SpawnPlayer(localPS,&xform,StartSpot,true)->LokiCharacter,
   then Possess. The real hero-spawn (untried).
3. If SpawnPlayer returns null / the round won't hold the advance: that + S68's spawn failures = LEAD A
   exhausted; B2 fully done.

Build: extend tutorial_launch.cpp's native-call primitive (already calls ExecuteConsoleCommand /
DoSpawnPossess on the game thread via the ProcessInternal hook @base+0x13454A0, thunk@UFunc+0xE0,
params via FFrame) to call GoToPhase (trivial 1-byte param) then SpawnPlayer. New tool this session:
tools/re/class_funcs.py.

## ★ EXPERIMENT 1 RESULT (RAN LIVE) — GoToPhase WORKS; advances BeginInit→SpawnSelect, then crashes in the native deploy setup.
Built tutorial_launch_phase.dll (RM_GOTOPHASE: steps GoToPhase(2..7), one per ~450ms). Sequence:
launch (ags hybrid empty-address) → auto-arm → inject tutorial_launch_fo.dll (force-open; **1st attempt
crashed at login, 2nd stuck** — still intermittent) → round at EGP_BeginInit, "Client is ready to play",
ALIVE → inject tutorial_launch_phase.dll. Marker: resolved gm=0x17079D48960 GoToPhase thunk=0x7FF6BA947200
NextPhase@0x0; `called GoToPhase(2)`, `called GoToPhase(3)`. Loki.log CONFIRMS the round ADVANCED:
`Setting Phase to 2 (Pre)` → `Setting Phase to 3 (FinishInit)` → `Setting Phase to 4 (SpawnSelect)` +
`Transitioning ... to phase (ERoundPhase::EGP_SpawnSelect)`. **THEN CRASH** on entering SpawnSelect:
`Unhandled Exception: EXCEPTION_ACCESS_VIOLATION reading address 0x0` — callstack top frames rva ~0x560F8AE/
0x560F210/0x560F27C reached via the GoToPhase thunk (0x7FF6BA947270, +0x70 into the resolved thunk) from the
shim (0x1709BA111A4 = phase.dll). So the CRASH IS INSIDE the native SpawnSelect-transition logic — it derefs a
NULL (the drop-plane / spawn-select manager / player-deploy state the force-open CLIENT-AUTHORITY round never
set up; the feature-toggle "CursorCharacterAim/AttachAudioListenerToHero not ready" spam right before confirms
the dead-spectator/no-hero state). ★ NET: the phase machinery ADVANCES fine via GoToPhase (BeginInit→Pre→
FinishInit→SpawnSelect all register) — the wall is the DEPLOY setup at SpawnSelect, exactly the
server-authoritative drop-in the DS/force-open routes both identified. GoToPhase is a real, working lever up to
the deploy phase.

## REMAINING LEAD-A EXPERIMENTS (to fully exhaust B2)
2. **Skip the crashing SpawnSelect deploy:** GoToPhase 2→3 then jump 6 (Lineup) / 7 (Combat), skipping
   SpawnSelect(4)+SpawnReveal(5). If a later phase doesn't deref the missing deploy state, the round may reach
   Combat "playing" — then a hero may be spawnable/possessable. (Quick: change the phase sequence + rebuild.)
3. **Bypass deploy via SpawnPlayer:** advance to FinishInit(3) (works), then call
   SpawnPlayer(localPC->PlayerState, &xform, StartSpot, true)->LokiCharacter, then Controller::Possess.
   The real hero-spawn (untried by S68). If it returns a hero + possession engages control → PLAYABLE; if it
   also null-derefs on missing round/deploy state → that + the SpawnSelect crash = LEAD A exhausted, B2 done.

## ★ EXPERIMENT 2 RESULT (RAN LIVE) — skipping the deploy phases reaches Combat, STABLE, but dead-spectator.
Phase list {2,3,6,7} (skip SpawnSelect(4)+SpawnReveal(5)). Force-open → inject phase.dll: the round advanced
`Setting Phase to 2 (Pre)` → `3 (FinishInit)` → `6 (Lineup)` → `7 (Combat)`, ALL clean, **NO CRASH, game alive
in EGP_Combat**. So the deploy-phase crash (exp1) is specific to SpawnSelect/SpawnReveal (the drop-plane/
spawn-select setup); Lineup+Combat transition fine. BUT the player is still a DEAD SPECTATOR in Combat: the
"ULokiGameFeatureToggles::Get DeadSpectatorCameraLock/CursorCharacterAim/AttachAudioListenerToHero not ready"
spam CONTINUES (199/200 lines), no hero, no drop-in — because we skipped the deploy that spawns+deploys the hero.
=> reaching Combat by skipping deploy does NOT produce a hero.

## ★ EXPERIMENT 3 RESULT (RAN LIVE) — SpawnPlayer (the real hero-spawn) CRASHES on missing state, like every other spawn path.
Injected RM_SPAWNPLAYER into the live Combat session (no re-force-open). Resolve was PERFECT: gm/pc found,
localPS=BP_LokiPlayerState_C (PC->PlayerState @0x3C0), startSpot found, SpawnPlayer thunk=0x7FF6BA83C070,
Possess thunk=0x7FF6B8BF2740, param offsets PS@0x0 Xf@0x10 SS@0x70 Ensure@0x78 Ret@0x80 InPawn@0x0. **But the
CallNative(SpawnPlayer) CRASHED** — EXCEPTION_ACCESS_VIOLATION reading 0x0, callstack deep in native code
(rva ~0x36A1xxx, a DIFFERENT spot than the SpawnSelect crash) → SpawnPlayer null-derefs on the missing
round/deploy/hero-setup state a client-authority force-open never has. (Tested: Combat phase, bEnsure=true,
with startSpot.)

## ★★★ CONCLUSION — B2 IS FULLY EXHAUSTED. ★★★
The round-phase MACHINERY is drivable (GoToPhase advances phases cleanly, incl. to Combat), but **actually
DEPLOYING/SPAWNING A HERO is impossible on the client-only force-open** — it null-derefs on server-authoritative
state every way we try it. Across ~7 spawn/deploy attempts now (S68: BP-SpawnDefaultPawnFor crash, native-
SpawnDefaultPawnFor null, poke-DefaultPawnClass null, GameplayStatics-BeginDeferred crash; S74: SpawnSelect
deploy-transition null-deref, SpawnPlayer null-deref) the root cause is IDENTICAL: the hero drop-in requires the
drop-plane / spawn-select / deploy context the real SERVER builds, which a client-authority round lacks. This is
the SAME server-authoritative round-start/drop-in wall all routes converge on (DS: needs the BP+Angelscript
gamemode/hero; content-overlay: Angelscript+native parents absent; real-exe-as-server: compile-time gated). ★
The honest ceiling stands: DS route = client stable in the LIVE tutorial world w/ full mirrored Loki net stack
(S70/S73 spectator); force-open route = the real tutorial gamemode fully initializes + the round advances via
GoToPhase, but the deploy/hero is unreachable client-side. A playable tutorial needs SUPERVIVE's dedicated-server
binary/source. NEW reusable: tools/re/class_funcs.py; tutorial_launch.cpp RM_GOTOPHASE (GoToPhase driver) +
RM_SPAWNPLAYER (SpawnPlayer+Possess) + PropOffsetSuper.
