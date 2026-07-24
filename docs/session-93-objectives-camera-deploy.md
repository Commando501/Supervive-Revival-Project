# Session 93 (2026-07-24) — tutorial OBJECTIVES completable + chain-walkable, camera fixed, and the
# "visible hero needs the server" claim OVERTURNED (from-scratch mesh proven)

Branch `dedicated-server-stub`, FORCE-OPEN tutorial route. One very long live session (single game pid held ~130 min
before crashing; several force-open relaunches). All work UNCOMMITTED. This doc is the trial-and-error record; the
paste-able start prompt is `docs/next-session-prompt-s94.md`.

## TL;DR — five results, newest last

1. **Objective-completion mechanism CRACKED + a 6-agent workflow verified it.** The tutorial's registered objective is
   the live `Comp_GameState_TrainingBase_C` (NOT an orphan quest). Completion chain (read from BP bytecode):
   `hero enters TargetTriggerBox → OnWASDTriggerOverlap → Comp.ProgressObjective(1) [ServerOnly gate] →
   CurrentObjectiveCount += 1 → OnRep_CurrentObjectiveCount [ServerOnly gate] → (count>=ObjectiveTarget) → EndTraining()`.
   `EndTraining`/`OnRep_TrainingActive`/`CallTrainingCompletions` are **UNGATED**.
2. **NEW REUSABLE PRIMITIVE — the Blueprint-function-call primitive** (`CallBPGuarded`): set `FFrame.Code =
   UStruct.Script.Data` (@+0x68) + Locals = zeroed `PropertiesSize`(@+0x60) blob, call the same `Func` thunk (which
   for a BP func == ProcessInternal). Reaches ANY BP-bytecode UFunction (the S55 direct-thunk primitive could not).
   Self-verified. ⚠ For NATIVE functions (Script.Num=0) it FAULTS — use the S55 `CallNativeGuarded` instead.
3. **Lessons COMPLETE + the CHAIN walks.** WASD completed (`TrainingSuccessful=1`, `FinishedVolumes.Num=1`, OBJARROW
   marker cleared). The chain-driver walked LMB → Dash_Level → Dash_Use → Jump, each started via
   `GameStateTryStartTraining(vol)` and completed via the ungated closer. (USER-CONFIRMED earlier: `GameStateTryStartTraining`
   spawns the on-map movement arrows + objective rings.)
4. **Camera FIXED (top-down).** The manager computes POV = hero location directly, ignoring the hero's spring arm
   (spring-arm tick-enable didn't help). Fix = spawn a CameraActor at hero+(0,+1229,+2760) [SUPERVIVE's ~3020-back,
   -66° framing], re-assert it as the PC view target every few frames. LIVE-VERIFIED top-down + held.
5. **★ THE "VISIBLE HERO NEEDS THE SERVER BINARY" CLAIM IS OVERTURNED.** The game's OWN cosmetics controller won't
   build the mesh outside deploy — but we don't need it: `AActor::AddComponentByClass` (NATIVE) created a real
   `SkeletalMeshComponent` on the hero (0→1); `USkeletalMeshComponent::SetSkeletalMeshAsset` assigned a body mesh.
   The CREATION MECHANISM WORKS. Not yet shown as a clean on-screen body (confounds below) — a refinement, not a wall.

## Deploy — the walls that ARE real vs. the ones that are NOT

Deploy = the server-authoritative drop-in that normally activates the hero visual + movement + descent. What's real:
- **Drop-in descent (DropPlane)** — `Comp_GameMode_DropPlane_Tutorial.SpawnPlane` (BP event) **FAULTS** (null-deref
  reading `GetAllActorsWithTag` drop-path markers that don't exist outside the real deploy). `AddPlayerToDropPlane`
  (native) + `GetAutoDropLocation` run clean but no-op. The full descent needs the server round context. (RM_DROPIN=20)
- **Game's cosmetics cascade** — 0 `LokiCosmeticsController` instances exist anywhere; `GetBaseCosmeticsController`
  returns null; the S79 orchestrators (`ReceiveRestarted`/`OnLocalPlayer_CharacterSpawned`/`RefreshLocalControl`/
  `TryLocalControlSetup`) and this session's `ClientInitialComponentSetup`/`BP_PostSetupCosmetics`/`RefreshCosmetics`
  all leave `controller=0, Mesh=0`. The game won't build the body for us. (RM_MESHCAM=19)

What is NOT a wall (the correction the user pushed for):
- **A visible body from scratch** — bypass the cosmetics controller entirely: create our own `SkeletalMeshComponent`
  (`AddComponentByClass`) + assign a hero mesh (`SetSkeletalMeshAsset`). PROVEN to create. (RM_MAKEMESH=21)
- **Movement** — the S75 velocity-puppet already moved the possessed hero with real collision; it crashed on the
  mantle subsystem querying UNREADY feature toggles, and this session's `gft_ready_fix` sets that readiness bit. The
  puppet+gft_ready combination was never tried.

## The from-scratch mesh — exactly what happened (so the refinement is precise)

`RM_MAKEMESH` (`tutorial_launch_makemesh.dll`), one game-thread pass:
```
AddComponentByClass(SkeletalMeshComponent, bManualAttachment=false, identity xform, bDeferredFinish=false)  -> comp OK (hero SkeletalMeshComponents 0->1)
SetSkeletalMeshAsset(SK_KaijuCaster_Default)                                                                 -> OK
SetComponentTickEnabled(false) + SetVisibility(true)                                                         -> OK (anim-off = no anim-thread crash)
```
- ⚠ `AddComponentByClass` + `SetSkeletalMeshAsset` are **NATIVE** — the first build called them via the BP primitive
  and FAULTED; the fix was `CallNativeGuarded` (S55 direct-thunk). Params (this build): AddComponentByClass
  `Class`@0x0, `bManualAttachment`@0x8, `RelativeTransform`(FTransform)@0x10, `bDeferredFinish`@0x70, `ReturnValue`@0x78.
- First (crashing) run used no anim-off → crashed the anim thread amid `FudgeMantlingSouth` toggle spam (a mismatched
  skeleton with no AnimBP). Second run added `SetComponentTickEnabled(false)` → **no crash on creation**.
- NO clean body appeared on screen, but the test was CONFOUNDED: (1) the `[SP]` spawn shim LIFTS the hero to Z~14200
  (an old "lift-to-see" hack) → the top-down camera sat at Z~16960 with the island tiny far below and any body
  off-frame; (2) `SK_KaijuCaster` is a DIFFERENT hero's mesh (skeleton won't bind to Ronin); (3) the game crashed
  later (force-open fragility + accumulation).
- ⚠ `ACharacter.Mesh`@0x450 stays 0 — SUPERVIVE builds NO base Mesh; the body is cosmetics-attached skeletal comps.
  The component WE add IS the body; don't look at `hero.Mesh`.

## THE REFINEMENT PLAN for a VISIBLE + MOVABLE hero (next session — this is tractable)

1. **Hero on the GROUND, no lift.** Either spawn+possess without the `[SP]` lift, or after spawn teleport the hero to
   a real walkable spot (S75: CapturePoint (-65,-1770,353) is good ground; the volume (283,277,-250) works too).
   Frame the top-down camera close (tune `-DKCAMUP`/`-DKCAMBACK`/`-DKCAMPITCH`).
2. **Ronin's ACTUAL body mesh.** `SK_KaijuCaster` won't bind. Load Ronin's skeletal mesh by path (async via the
   AssetManager, or find it once cosmetics-adjacent assets are resident) and `SetSkeletalMeshAsset` THAT. Keep
   tick/anim off first (static reference pose = a visible body) — that removes the skeleton/AnimBP crash risk. Then,
   if a body renders, add Ronin's AnimBP + re-enable tick for animation.
3. **gft_ready_fix FIRST**, every run — it quiets the `FudgeMantling`/toggle spam that has crashed movement (S75) and
   coincided with the mesh crash.
4. **Movement** — inject the S75 velocity puppet (`tutorial_launch_puppet.dll`) with gft_ready_fix loaded; S75 proved
   the CMC velocity poke moves the hero with collision. Test on solid ground.
5. **Then** the objective-completion + chain-driver (below) give a full "start → play(ish) → complete → exit" once the
   hero is visible+movable.

## The objective/chain drive (DONE — reusable) — the ungated completion recipe

- The physical overlap CANNOT fire on force-open (box.OnActorBeginOverlap InvocationList Num=0 — the quest's authority
  bind branch never ran; needs the sequencer/TeamState lifecycle = 0 instances; the huge TargetTriggerBox has the hero
  already inside it). So DON'T rely on the overlap for completion.
- Completion that WORKS (RM_FIREOVERLAP=15 / RM_DRIVECHAIN=16): on the live `Comp_GameState_TrainingBase_C`
  (TrainingActive==1 or CurrentTrainingVolume!=0), RPM-set `TrainingSuccessful=1` + `CurrentObjectiveCount=1` +
  `TrainingActive=0`, then BP-call the PARAM-FREE ungated `OnRep_TrainingActive()` → CallTrainingCompletions →
  OnTrainingFinish (chain-advance) + LokiGameState.OnTrainingComplete + FinishedVolumes.AddUnique(volume tag).
- Chain walk: per lesson (follow WASD.NextQuestInChain: WASD→LMB→Dash_Level→Dash_Use→Jump→…) = clear FinishedVolumes →
  quest.OnTrainingVolume(vol) → GameStateTryStartTraining(vol) [TrainingActive 0→1] → the ungated closer. ONE volume
  is loaded (Move_V2) so each "next" reuses it; lesson identity is the active quest.
- ⚠ `ServerOnly` OutputExecs==1==authority==run-the-guarded-branch (cross-checked 4 sites). Poking count + calling
  `OnRep_CurrentObjectiveCount` did NOT complete (its ServerOnly branch skipped when called from the synthetic FFrame);
  the ungated `OnRep_TrainingActive` path sidesteps it. All actors are Role=Authority(3).

## The camera fix (DONE — reusable)

`RM_TOPDOWNCAM=18` (`tutorial_launch_topdowncam.dll`): spawn a CameraActor, SetActorLocation/Rotation to follow the
hero each PI hit at hero+(0,+1229,+2760) pitch -66/yaw -90, re-assert `SetViewTargetWithBlend(cam)` every 3rd hit
(the manager reverts a one-time set). Holds ~120s (no g_done). Tunable `-DKCAMUP`/`-DKCAMBACK`/`-DKCAMPITCH`.
`RM_MESHCAM=19` = mesh-build attempt (game's cosmetics fns) + the same cam; superseded by RM_MAKEMESH for the mesh.

## New shim modes in `tools/sigbypass-mod/tutorial_launch.cpp` (UNCOMMITTED)

`RM_OBJDRIVE=13, RM_OBJCOMPLETE=14, RM_FIREOVERLAP=15, RM_DRIVECHAIN=16, RM_CAMERA=17, RM_TOPDOWNCAM=18, RM_MESHCAM=19,
RM_DROPIN=20, RM_MAKEMESH=21` — plus the S91 `RM_SPAWNQUEST=10, RM_QUESTPLAY=11, RM_BPCALL=12` and the `CallBPGuarded`
BP-call primitive. Build any with `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKRUNMODE=<mode> tutorial_launch.cpp
-o <out>.dll -lkernel32 -luser32`. Built DLLs on disk this session: `tutorial_launch_{objdrive,objcomplete,fireoverlap,
drivechain,camera,topdowncam,meshcam,dropin,makemesh}.dll` + S91's `{quest,qplay,bpcall}` + prebuilt `{fo,sp,phase,
puppet}` + `gft_ready_fix.dll`.

## New RE tools (`tools/re/`, all read-only RPM)

`obj_fulldump.py` (instance full property tree + values + object-class resolution), `read_role.py` (AActor Role/RemoteRole),
`read_overlap.py` (box overlap-delegate bind + collision), `read_camera.py` (PlayerCameraManager POV + spring arm),
`read_mesh.py` (hero Mesh/cosmetics state), `find_named.py` (find UObjects/UFunctions by name substring).

## GOTCHAS (all hit this session)

- Native vs BP: `CallBPGuarded` (FFrame.Code=Script.Data) for BP-bytecode fns; `CallNativeGuarded` (FFrame.Code=NULL,
  direct thunk) for native fns (Script.Num=0). Using the wrong one FAULTS.
- PowerShell `$pid` is READ-ONLY (auto-var) — use a different name; a botched assignment silently injects into the
  wrong process.
- Steam relaunches the game under a NEW pid — always resolve the newest: `Get-Process SUPERVIVE-Win64-Shipping |
  Sort StartTime -Desc | Select -First 1`.
- Force-open crashes intermittently on the fo inject (~2 of 3); budget relaunches. Delete `Loki.log` before each run.
- Two PI-hooking `tutorial_launch` modes can't run at once (they hold the PI hook for their whole duration) — let one
  finish (or its 120s hold release) before injecting the next.
- The `[SP]` spawn shim LIFTS the hero into the sky — bad for viewing; teleport to ground for the visible test.

## ENV AT HANDOFF

- Config REVERTED to baseline: `forceTutorialMatch = false`, `ConnectionDetails.address = "127.0.0.1:7777"`,
  `kEnableServerAuthConfig = false`. ags/game killed (ags may still be running — harmless; kill if needed). Nothing committed.
- To resume: re-arm force-open (`forceTutorialMatch=true` + address `""`), rebuild ags, relaunch. Full recipe in
  `docs/next-session-prompt-s94.md`.
