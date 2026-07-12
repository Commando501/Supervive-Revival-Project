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
