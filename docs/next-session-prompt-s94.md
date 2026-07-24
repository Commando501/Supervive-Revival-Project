# Next-session handoff (S94) — a VISIBLE + MOVABLE tutorial hero (recreate the body from scratch)

Branch `dedicated-server-stub`. Continues S93. The big S93 result: the "a visible hero needs SUPERVIVE's
dedicated-server binary" claim is **OVERTURNED** — we created a real `SkeletalMeshComponent` on the possessed hero
from scratch (`AddComponentByClass` + `SetSkeletalMeshAsset`). The mechanism works; S94 refines it into a cleanly
**visible + movable** hero. Read `docs/session-93-objectives-camera-deploy.md` for the full trial-and-error record and
`docs/tutorial-playability-plan.md` ("⚑ READ THIS FIRST" header — later sections win).

---

## PASTE-ABLE OPENING PROMPT

> Continue the SUPERVIVE tutorial work on branch `dedicated-server-stub`. Read first, in order:
> (1) `docs/next-session-prompt-s94.md` (this file), (2) `docs/session-93-objectives-camera-deploy.md` (full S93
> detail), (3) memory `supervive-tutorial-launch-status` (tail = S93).
>
> GOAL: get a VISIBLE, MOVABLE hero standing in the force-open tutorial world. S93 PROVED the hero body can be built
> from scratch (AddComponentByClass created a real SkeletalMeshComponent on the hero; SetSkeletalMeshAsset assigned a
> mesh) — the game's own cosmetics controller is NOT needed. S94 = refine that into a clean on-screen body + wire up
> movement (the S75 velocity puppet already moves the possessed hero).
>
> Do NOT re-open: the DS/stub route (server-binary-bounded), the game's cosmetics-controller path (0 controllers exist,
> never created outside real deploy), or the DropPlane SpawnPlane descent (faults reading absent level markers).
>
> Env: elevated PS, Steam first. Use the PowerShell tool (NOT Bash), `dangerouslyDisableSandbox: true` for
> launch/inject, `[System.IO.File]::Delete` to remove logs. ⚠ PowerShell `$pid` is read-only — use `$gpid`. Revert to
> baseline when done.

---

## 30-SECOND STATE

- **The hard part is done.** `RM_MAKEMESH=21` (`tutorial_launch_makemesh.dll`) creates a SkeletalMeshComponent on the
  hero via the NATIVE `AddComponentByClass` (call it via `CallNativeGuarded`, NOT the BP primitive — it's Script.Num=0),
  assigns a body mesh via `SetSkeletalMeshAsset`, and with `SetComponentTickEnabled(false)` doesn't crash on creation.
- **S93's visible test was CONFOUNDED** (no clean body shown): the hero was LIFTED into the sky by the `[SP]` shim
  (camera far above the island), the mesh used (`SK_KaijuCaster_Default`) is a DIFFERENT hero's mesh (skeleton won't
  bind to Ronin), and the game crashed later (force-open fragility).
- **Also DONE + reusable:** the objective-completion + chain-driver (lessons complete + WASD→LMB→Dash→Jump walk), the
  top-down camera fix (RM_TOPDOWNCAM=18), and the Blueprint-function-call primitive (`CallBPGuarded`).

## THE S94 TASK — refine to a visible + movable hero

1. **Spawn the hero ON THE GROUND (no lift).** The `[SP]` shim (`tutorial_launch_sp.dll`) lifts the hero to Z~14200.
   Either build a spawn+possess variant WITHOUT the lift, or after spawn teleport the hero to real walkable ground
   (S75: CapturePoint `(-65,-1770,353)` is solid; the training volume `(283,277,-250)` also works). Keep the camera
   close (tune `RM_TOPDOWNCAM` with `-DKCAMUP`/`-DKCAMBACK`/`-DKCAMPITCH`).
2. **Assign Ronin's ACTUAL body mesh.** `SK_KaijuCaster` won't bind to Ronin's skeleton. Load Ronin's skeletal mesh by
   path (async via the AssetManager `AsyncLoadPrimaryAssets` primitive we already have, or find the asset resident once
   a Ronin cosmetic loads), then `SetSkeletalMeshAsset` THAT. First keep tick/anim OFF (static reference pose = a
   visible body, no skeleton/AnimBP crash). If a body renders, add Ronin's AnimBP + re-enable tick for animation.
3. **gft_ready_fix FIRST, every run** (`gft_ready_fix.dll`) — quiets the `FudgeMantling`/toggle spam that crashed
   movement (S75) and coincided with the S93 mesh crash.
4. **Movement:** inject the S75 velocity puppet (`tutorial_launch_puppet.dll`) with gft_ready_fix loaded — S75 proved
   the CMC velocity poke moves the hero with real collision. Test on solid ground.
5. **Full loop:** with a visible+movable hero, the S93 objective/chain-driver (`tutorial_launch_drivechain.dll`) gives
   "start lesson → complete → next lesson"; then exit-to-menu; then credit `NewOnboarding_CompleteBasicTraining` in
   `server/internal/interactive/missions.go` `objectiveRules`.

## RECIPE (exact — force-open + the injection sequence)

```powershell
# 0) RE-ARM force-open: server/internal/interactive/interactive.go  forceTutorialMatch = true  AND  the ConnectionDetails
#    "address": "" (EMPTY). Then rebuild ags:  & "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags
# 1) fresh game (Steam MUST be running):
#    kill SUPERVIVE-Win64-Shipping ; [System.IO.File]::Delete("C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log")
& "G:\git\Supervive Revival Project\configs\launch-redirect.ps1" -NoHook   # (background; Steam relaunches under a NEW pid)
# 2) wait "TryUIReady SUCCESS" AND uptime >= 95s. Resolve the LIVE pid:
#    $gp = Get-Process SUPERVIVE-Win64-Shipping | Sort StartTime -Desc | Select -First 1 ; $gpid = $gp.Id
# 3) inject force-open, wait "to Finished" (retry the whole launch if the game dies — ~2 of 3 crash here):
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_fo.dll
# 4) gft_ready_fix -> spawn+possess hero -> (teleport to ground) -> make-mesh -> top-down cam:
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\gft_ready_fix.dll
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_sp.dll     # (spawns+possesses; ⚠ lifts hero — fix in S94)
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_makemesh.dll
tools\inject\inject.exe mmap $gpid tools\sigbypass-mod\tutorial_launch_topdowncam.dll
# marker: docs\tutorial-launch-marker.txt ; client log: C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log
# The USER supplies screenshots (computer-use is denied).
```

## KEY API / OFFSETS (this build, live-verified S93)

- `AActor::AddComponentByClass` (NATIVE) params: `Class`@0x0, `bManualAttachment`@0x8, `RelativeTransform`(FTransform,
  quatW@+0x18, Scale3D@+0x38/40/48)@0x10, `bDeferredFinish`@0x70, `ReturnValue`@0x78. Returns the component in the
  result buffer.
- `USkeletalMeshComponent::SetSkeletalMeshAsset(NewMesh)` (NATIVE), `SetComponentTickEnabled(bool)`, `SetVisibility(bool)`,
  `PauseAnims(bool)` — all native, call via `CallNativeGuarded`.
- Blueprint-call primitive `CallBPGuarded(func, ctx, resultBuf)`: FFrame.Code=UStruct.Script.Data(@+0x68), Locals=zeroed
  PropertiesSize(@+0x60) blob, same Func thunk. Native primitive = the S55 `CallNativeGuarded` (FFrame.Code=NULL).
- `ACharacter.Mesh`@0x450 stays 0 — SUPERVIVE builds NO base Mesh; the added component IS the body.
- Objective completion (ungated): on `Comp_GameState_TrainingBase_C`, RPM-set `TrainingSuccessful=1`+`CurrentObjectiveCount=1`+
  `TrainingActive=0`, then BP-call param-free `OnRep_TrainingActive()`.
- Loaded body meshes seen S93 (for a placeholder-only test): SK_KaijuCaster_Default, SK_Base_Wisp, SK_HeroPlatform_Default.

## DEAD ENDS — do not repeat (each measured this session)

- **Game's cosmetics controller** — 0 instances; GetBaseCosmeticsController=null; ClientInitialComponentSetup/
  BP_PostSetupCosmetics/RefreshCosmetics + the S79 orchestrators leave controller=0. It's only created in real deploy.
- **DropPlane SpawnPlane descent** — FAULTS (null-deref on absent `GetAllActorsWithTag` drop-path markers).
- **DS/stub route** — server-binary-bounded (S72/S73/S90).
- **The physical WASD overlap** — never bound on force-open (box.OnActorBeginOverlap Num=0); use the ungated closer.
- **Calling AddComponentByClass/SetSkeletalMeshAsset via the BP primitive** — they're NATIVE; it FAULTS. Use CallNativeGuarded.

## ENV AT HANDOFF

- Config = BASELINE (`forceTutorialMatch=false`, address `"127.0.0.1:7777"`, `kEnableServerAuthConfig=false`). ags builds
  clean. Game/editor killed. **Nothing committed.**
- Uncommitted (carries all S87-93 work): `tools/sigbypass-mod/tutorial_launch.cpp` (all RM_ modes + `CallBPGuarded`),
  `server/internal/interactive/interactive.go`, the `unreal-stub/Source/Loki/*` files, certs + marker/log files.
- Shims built on disk (see the session-93 doc's shim list). New tools: `tools/re/{obj_fulldump,read_role,read_overlap,
  read_camera,read_mesh,find_named}.py`.

## REVERT TO BASELINE WHEN DONE

`forceTutorialMatch=false` + `ConnectionDetails.address="127.0.0.1:7777"` + `kEnableServerAuthConfig=false` (already the
committed values); kill SUPERVIVE-Win64-Shipping / UnrealEditor-Cmd / ags. Leave hosts + cacert alone (no `-Revert`
without an explicit ask).
