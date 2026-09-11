# Session 78 — DS spectator fly-cam: the DURABLE vtable-hook mover shipped; mouse-relative steering shipped; the fast free-look rotation hit a WALL

Date: 2026-07-15. Continues S77 (moving spectator fly-cam over the live tutorial world via the DS stub).
Goal: polish the S77 fly-cam — (1) mouse-relative steering, (2) a durable per-frame mover (kill the input stalls),
(3) feel/timing. Emergent goal (from testing): tame the hyper-fast native free-look rotation.

## TL;DR
- ★★★ **Refinement #2 — the DATA/VTABLE hook — SHIPPED and is the session's big win.** The transient-per-step
  mover (S77) fired only on a game-thread `ProcessInternal` (a Blueprint script call), which is SPARSE when the
  user isn't rotating (native camera ticks are C++, not BP) → intermittent input stalls (proven: `fired=0` while
  `steps` climbed). FIX: swap the CameraManager's vtable POINTER (`obj@+0`, HEAP write — no `.text`, no
  thread-suspend) to a heap copy whose per-frame slot is our stub `OnVtableTick`. Runs the move EVERY frame,
  PI-independent. Live-verified: `fired`/`vtTicks` ~720/sec for 15 min, ZERO crash — the heap vtable swap does NOT
  trip the anti-tamper (which is a `.text` integrity check). User verdict: **"everything felt very smooth."**
- ★ **Refinement #1 — mouse-relative steering — SHIPPED.** `ControlRotation` is NOT a reflected UPROPERTY here and
  the view yaw isn't a plain FRotator/float/double/quat findable by a memory diff. The winning read is the
  `APlayerCameraManager::GetCameraRotation()` UFUNCTION, called on the game thread inside `OnVtableTick` (throttled)
  → the heading follows where you look (W flies toward the view). `yaw == viewYaw` live-verified.
- ★ **Refinement #3/#4 shipped:** world-location seed (`K2_GetActorLocation` — no origin teleport), dirty-flag move
  (only move when flying, not 720×/sec), Z clamp, gentler speed + Shift boost, poll-until-widgets-spawned.
- ★ **Transient overlay-hide (crash fix).** The one-shot overlay-hide held a ~20s STANDING `ProcessInternal` hook;
  by late session the anti-tamper caught it reliably (3 crashes in a row, even at 8s). Converted it to
  transient-per-hide (install → one `DoSpectatorCam` → uninstall, cycled) — the same µs-exposure dodge as movement.
  No standing `.text` hook is EVER held now; the overlay-hide crashes stopped.
- ✖ **THE WALL: the hyper-fast native free-look rotation is NOT tamable with available techniques.** User: "barely
  moving the cursor has you spinning multiple times." Three independent override attempts ALL failed:
  1. **Sensitivity fields** — enumerated every rotation/camera float field (`UserSettings.MouseSensitivity`,
     `MouseSensitivityADS`, `CameraOffsetSensitivity`, `CameraPanSpeed`, `SpectatorCameraDragScrollSpeed`,
     `SpectatorPawnMovement.TurningBoost=8.0`, …) and re-wrote them to 6% continuously. **ZERO effect.** The
     PlayerController has NO look-sensitivity field → the free-look scale is in the input system (Enhanced Input) or
     hardcoded.
  2. **Write the POV rotation directly** — the CameraCachePrivate region (`cam+0x14A8..`) is all-zeros (not the POV);
     the S77 memory diff never found any swinging FRotator/quat either. `GetCameraRotation` computes it — there's no
     single stored POV yaw to poke.
  3. **Own camera as view target** — spawned an `ACameraActor` + `SetViewTargetWithBlend` (spawn WORKS now, no
     crash), but the game's camera manager reverts the view target to the DefaultPawn EVERY frame
     (`viewTarget@cam+0x420 = DefaultPawn (reverted)`) even re-asserting it 4×/frame. The game will not relinquish
     its spectator camera.
  → The only remaining path is hooking the game's specific camera-update function to intercept/override the rotation
     it computes each frame — deep, uncertain, and out of scope after ~35 relaunches. **Honest ceiling: a smooth,
     reliable, mouse-STEERED fly-cam whose VIEW ROTATION is the game's fast native free-look.**

## What works (the shipped state; `ds_hybrid.cpp`, `kMode=MODE_SPECTATOR_CAM`, `kTakeoverCam=false`)
- Inject into the DS-connected client (`inject.exe mmap <pid> ds_hybrid.dll`). Flow: poll-until-widgets →
  resolve (camera / view yaw getter / K2_Get/SetActorLocation) → **transient overlay-hide** (reveals the world,
  captures the FFrame template) → **vtable sweep + install** on the CameraManager (per-frame slot ~276/277) →
  movement loop. `OnVtableTick` (per frame, game thread): seed pos from world loc once; refresh view yaw via
  `GetCameraRotation`; apply `K2_SetActorLocation` to the DefaultPawn when the worker flagged input (`g_moveDirty`).
  Worker (off-thread): poll WASD/Space/Ctrl/Shift + arrows; heading = view yaw; update `g_spX/Y/Z` + dirty.
- WASD flies where you look, Space/Ctrl up/down, Shift boost, Z-clamped, smooth, no stalls, stable.

## Reusable groundwork built this session (all working)
- **Vtable hook**: `FindPerFrameSlot` (counter-trampoline sweep → highest-count slot in a per-frame range),
  `BuildSweepVt` / `BuildVtStub` (save-regs → call-C → jmp-orig), `InstallVtableMove` (heap vtable copy + `obj@+0`
  swap), `RestoreVtable`. Pure-heap per-frame game-thread exec that dodges the `.text` anti-tamper.
- **Raw mouse capture**: `RawInputThread` (message-only window + `RIDEV_INPUTSINK` + `WM_INPUT`) — **works** (deltas
  captured even with the cursor locked / game focused). `[raw] events=1630 dx=627 dy=1798`. Ready for the day the
  rotation override is solved.
- **Sensitivity enumerator**: `EnumSensProps` / `ProbeSensitivity` (walk a class chain for rotation/camera float
  fields + continuous reduction). Confirmed the free-look scale is not among them.
- Camera take-over scaffolding: `ResolveTakeover` / `SpawnMyCamera` (spawn `ACameraActor` + `SetViewTargetWithBlend`
  + `K2_SetActorRotation`) — all resolve + call cleanly; blocked only by the view-target revert.

## NEXT (if the rotation is revisited)
Hook the game's per-frame camera-rotation writer and override the yaw/pitch it produces with a slow value driven by
the (already-working) raw mouse delta. Candidates: identify which CameraManager vtable slot is `UpdateCamera` /
`DoUpdateCamera` (the one that WRITES the POV), give its stub an AFTER-original callback (call orig → then overwrite
the POV rotation it just wrote), and set POV yaw/pitch from `g_camYaw/g_camPitch` accumulated from `g_mouseDX/DY`.
This is the one path not yet tried; it needs the exact POV-writing slot + the POV rotation offset (both un-found).

## Gotchas reconfirmed / new
- The overlay-hide must be transient now (standing hook = anti-tamper crash, reliably by late session).
- `GetCameraRotation` resolution VARIES per launch (which `FindInstClassSub("CameraManager")` instance is returned);
  when it resolves it's the yaw ground truth.
- `SpawnMyCamera` (ACameraActor via GameplayStatics BeginDeferred/FinishSpawning) works — the S72 spawn crash was
  hero/GAS-specific; a plain camera + the S74 `BuildOutParms` struct-param fix spawns clean.
- Vtable sweep picks slot 276 or 277 (per-frame camera virtuals, ~5×/frame) — both work as the mover host.
