# Continue: SUPERVIVE Missions page — Session 56 pickup

Paste into a fresh Claude session in `G:\git\Supervive Revival Project` (branch `dedicated-server-stub`).
Authoritative detail: **`docs/session-55-native-call-primitive.txt`** + **`docs/session-56-param-passing-and-factory.txt`**.
Memory: `supervive-missions-page-status`, `supervive-dedicated-server-status`.

> ⚠️ STATUS UPDATE (2026-07-07, end of s56) — parts of the "YOUR JOB" below are now DONE. Read
> `docs/session-56-param-passing-and-factory.txt` first. Summary of what changed:
> - **PARAM-PASSING via Avenue A is SOLVED + verified** (probe7: `GetMissionModel("Daily")` ran clean).
>   Recipe: params frame with each value at FProperty Offset_Internal @+0x44; FFrame Code=NULL,
>   Locals=frame, **PropertyChainForCompiledIn @+0x88 = Function.ChildProperties (*(UFunc+0x58))**, clear
>   +0x30/+0x38/+0x40; return→r8. FMissionProgress layout fully RE'd (tools/re/struct_layout.py).
> - **`CreateMissionModelFromFinalProgress` __fastfails (crash, no VEH) on empty (probe6) AND a 1-element
>   None-id array (probe8)** — inside the factory, NOT the param mechanism. ⇒ it needs REAL resolvable
>   mission DAs. **The modal is no longer blocked by the primitive — the wall is the missions DATA/ASSET
>   layer (s52's DA-resolution, native-only).**
> - **S57 DONE — mission-DA resolution ROOT-CAUSED** (docs/session-57-da-resolution.txt): probe9 chained
>   `PrimaryAssetIDFromString + GetLokiDataAsset` via the primitive. CONTROL `Hero:Alchemist` RESOLVED
>   (BP_HeroAsset_Alchemist_C — primitive + asset path proven); `Mission:ArmoryDaily_PlayAGame` id parses
>   but `GetLokiDataAsset → NULL`. ⇒ **missions are NOT registered as primary assets** (heroes are). The
>   reflected LokiAssetManager API can't register (raw-native-only).
> - **NEW #1 TARGET (s58): REGISTER the "Mission" primary asset type.** RAW C++ call (NO FFrame) to
>   `UAssetManager::ScanPathsForPrimaryAssets(FPrimaryAssetType, TArray<FString> Paths, UClass* BaseClass,
>   bHasBlueprintClasses, bIsEditorOnly, bForceSynchronousScan)` from the ProcessInternal game-thread hook:
>   rcx=LokiAssetManager singleton, rdx=&Type("Mission"), r8=&Paths(mission DA folder), r9=LokiDataAsset_Mission
>   UClass, stack=bools. Find the raw addr (usmapdump xref; near AsyncLoadPrimaryAssets), the mission DA folder
>   path (docs/game-map.md / catalog full paths), and the LokiDataAsset_Mission class. Then re-run probe9's
>   mission GetLokiDataAsset to confirm it resolves. Keep the VEH (scan is the historically crash-prone call,
>   but from a CLEAN game-thread context this time). THEN synthesize a granted-mission set, populate knownMM,
>   broadcast OnUpdated, open the modal (computer-use). (Alt: raw StaticLoadObject by the DA object path.)
> The material below is retained for the mechanism reference (offsets, recipe, signatures).

---

## TL;DR — the keystone is SOLVED; S56 = use it to populate + render the modal

**Session 55 got the game-thread native-call primitive working.** This was THE blocker for the
whole client-side missions path (and the user's "server-as-activation-layer, client shims do the
work" vision). It is DONE and live-verified.

**The primitive (Avenue A — direct native-thunk call):**
- Hook `ProcessInternal @base+0x13454A0` (the proven-reliable game-thread hook), capture a live
  `FFrame` (memcpy 0x180 — valid vtable + internals).
- Build `myframe` = that template with `Node(+0x10)=UFunction`, `Object(+0x18)=Context`,
  **`Code(+0x20)=NULL`** (for a no-param fn, P_FINISH does `Code += !!Code` = +0, no deref),
  `Locals(+0x28)=buf`.
- Call the thunk directly: `((void(*)(void*Ctx,void*FFrame,void*Res))(UFunction.Func@+0xE0))(Ctx,&frame,&res)`
  (x64 ABI rcx=Ctx, rdx=&frame, r8=&res). A direct thunk call has NO guards → works where
  ProcessEvent no-ops (probe2/s54).
- PROVEN: `ProgressionManager.GetMissionsModel()` returned exactly the RPM-read MissionsModel ptr,
  no crash (`tools/sigbypass-mod/missions_nativecall_probe4.cpp`). Return-by-value also proven with
  `MissionsModel.GetMissions()` (`missions_nativecall_probe5.cpp`) — returned a well-formed
  `TArray{Data=0, Num=0, Max=0}`, i.e. **baseline mission count = 0** (empty model at the menu,
  matches S52). So the S56 verification "watch GetMissions().Num go 0 → N" is validated.
- Avenue B (hook ProcessEvent itself, `probe3`) did NOT fire (peSeen=0) — moot; ignore.

## ★ RE-OPEN Session 52's ingestion "impossibilities" ★
S52 concluded the ingestion factory "rejects synthetic data" and mission DAs "don't resolve" — but
those tests ran through the ProcessEvent-from-hook primitive that S52 ITSELF proved is a uniform
NO-OP for native (the calls NEVER RAN). With Avenue A they must be RE-TESTED and may behave totally
differently. Treat nothing about the ingestion path as settled until re-run with the real primitive.

## YOUR JOB (S56): populate the live MissionsModel + render the modal

The category widgets read `ProgressionManager.GetMissionsModel()` (== the ProgMgr's OWN live model,
"knownMM" = ProgMgr+0x3B8) and subscribe to its `OnUpdated`. So the crux is getting mission data
INTO knownMM, then broadcasting. The real game path is: replicated `LokiPlayerState_Missions` →
`MissionsModel.OnPSMissionsUpdated()` rebuilds knownMM's Missions/Pools from its MissionsActor
(null on standalone). Steps, all now executable via Avenue A + verifiable via RPM (NO computer-use
until the final visual check):

1. **Extend the primitive to pass PARAMS.** For no-param fns Code=NULL suffices; for params you must
   feed the thunk. Cleanest: keep using the captured live FFrame but drive the param reads. Two
   sub-options to prototype: (a) assemble a minimal EX_ bytecode `Code` stream that pushes the params
   (the thunk calls `Stack.Step`/`StepExplicitProperty` to read each), or (b) for functions whose
   thunk reads params directly off the Locals/Parms area, point Locals at a filled params struct.
   Prove it on a SIMPLE one first: `ProgressionManager.AddProgressToMission(Objective:SoftClass,
   Progress:float)` or `LokiPlayerState_Missions.ServerAddMissionProgress(str,str,float)`.

2. **Re-test the factory (the #1 experiment):** call
   `MissionsModel.CreateMissionModelFromFinalProgress(TArray<FMissionProgress>&)` with a populated
   array (FMissionProgress layout is known cmd-for-cmd from s54: ID(str), AssetId/PoolId
   (FPrimaryAssetId), Complete/Failed(bool), ObjectiveProgress(TArray<FMissionObjectiveProgress>),
   MillisUntilExpiry(int64), Expiry/GrantedAt(FDateTime)). S52 got NULL here via a no-op — does it
   now return a non-null MissionsModel? If yes, inspect that model's `GetMissions().Num`.

3. **Wire it into knownMM** so the widgets see it. Options: assign the created model back to
   ProgMgr+0x3B8; or point knownMM.MissionsActor at a crafted/populated `LokiPlayerState_Missions`
   then call `MissionsModel.OnPSMissionsUpdated()` on knownMM (rebuilds from the actor).

4. **Verify data landed (autonomous, no computer-use):** call `MissionsModel.GetMissions()` (probe5
   pattern) and read `TArray.Num`. 0 → N means the model populated.

5. **Broadcast + VISUAL verify (computer-use, needs user):** the widgets rebuild on
   `GetMissionsModel().OnUpdated`; the ingestion natives should fire it (if not, broadcast via the
   primitive, or use pi8 to invoke a BP that rebuilds — S45 "dead delegate" gotcha: broadcast, don't
   just poke). Then open the Missions modal and confirm tiles.

## INGESTION-TARGET SIGNATURES (RE'd live S55, tools/re/sig_enum.py — all native)
```
ProgressionManager:  GetMissionsModel() -> MissionsModel*
                     AddProgressToMission(Objective:SoftClass, Progress:float)
                     GetCurrentPlayerProgression(OUT PlayerProgression) -> bool
MissionsModel:       GetMissions() -> TArray<MissionModel*>              [no-param; RPM-verify probe]
                     OnPSMissionsUpdated() -> void                       [rebuild-from-actor native]
                     CreateMissionsModel(PSMissions:LokiPlayerState_Missions*) -> MissionsModel*
                     CreateMissionModelFromFinalProgress(OUT TArray<MissionProgress>) -> MissionsModel*
                     GetMissionModel(ID:str) -> MissionModel*
LokiPlayerState_Missions: ServerAddMissionProgress(MissionID:str, ObjectiveName:str, Progress:float)
                     GetMissionProgress(OUT TArray<MissionProgress>) -> bool
                     GetMission(MissionClass:SoftClass) -> BaseMission*
```
Run `python tools/re/sig_enum.py <PID> <BASE-hex>` for the full live dump (re-read BASE each launch).

## KEY OFFSETS / RECIPE (this exe build)
- base this session = 0x7FF6B54F0000 (ASLR; re-read each launch). ProcessInternal @base+0x13454A0.
  ProcessEvent @base+0x12C5A10. GUObjectArray @base+0x9E38930. FNamePool @base+0x9D81450.
  GGameThreadId @base+0x9D49158.
- UObject Class@+0x18 Name@+0x20 Outer@+0x28. UClass Children(UField*)@+0x50, ChildProperties(FField*)@+0x58.
  UField Next@+0x30. UFunction Script.Num@+0x70, **Func(thunk)@+0xE0**. ProgressionManager.MissionsModel@+0x3B8.
- FField FFieldClass@+0x08 Next@+0x18 Name@+0x20 Flags(u64)@+0x38. FStructProperty.Struct@+0x70,
  FObjectProperty.PropertyClass@+0x70, FArrayProperty.Inner@+0x78. TArray = {Data@+0, Num@+8, Max@+12}.
- **Standalone recipe (elevated PS, Steam up):**
  `configs\launch-redirect.ps1 -Hook "...\tools\sigbypass-mod\catalog_store_fix.dll"` (explicit -Hook =>
  store fix ONLY, no pi8, so your PI-hooking probe is the sole one). Wait for
  `HUD BeginPlay - BP_MainMenuHUD_C` + `TryUIReady SUCCESS` in the client Loki.log
  (C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log), and `catalog-store-fix-marker.txt`
  showing `jz=1/1 unhook=1` (settled) before injecting (avoid racing its thread-suspending install).
  Launch reached the menu in ~20s this session — build→inject→observe cycles are cheap. Steam MUST be
  up first (else Auth Failure 14005). Inject: `tools\inject\inject.exe mmap <PID> <dll>`.
  Build shims: `clang++ -shared -O2 <f>.cpp -o <f>.dll -lkernel32`
  (clang++ at C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe).

## WHAT'S DONE (don't redo)
- Avenue A primitive: PROVEN (call native, no-param + return-by-value). probe4/probe5.
- Ingestion-target signatures: RE'd (sig_enum.py; table above).
- Avenue B (ProcessEvent-self-hook): didn't fire; abandoned. probe3.

## Gotchas
- ONE ProcessInternal-hooking shim per client (pi8 + probe4/5 all hook it). The standalone recipe's
  explicit -Hook keeps pi8 OUT, so your probe is the only PI hook.
- Direct thunk call w/ params is the unproven part — start on a SAFE/simple target, keep the VEH in the
  probe, and expect a possible crash→relaunch (cheap now).
- catalog_store_fix is FINE on standalone (its normal use). Steam up first.
- Everything committed; working tree is runtime churn (certs/markers/logs) — ignore.

## First moves
1. Read `docs/session-55-native-call-primitive.txt` + the two memory files.
2. Relaunch standalone (recipe above), get PID + base.
3. Prototype param-passing on `AddProgressToMission` or `ServerAddMissionProgress`; then re-test
   `CreateMissionModelFromFinalProgress`; verify via `GetMissions().Num`.
4. Wire into knownMM, broadcast, open the modal (computer-use) to confirm tiles.
