# Continue: SUPERVIVE Missions — Session 59 pickup (progress bars → real tracking)

Paste into a fresh Claude session in `G:\git\Supervive Revival Project` (branch `dedicated-server-stub`).
Authoritative detail lives in **`docs/session-55-native-call-primitive.txt`**,
**`docs/session-56-param-passing-and-factory.txt`**, and **`docs/session-57-da-resolution.txt`**
(read the S58 sections at the bottom of session-57 — they cover the whole missions build). Memory:
`supervive-missions-page-status`, `supervive-dedicated-server-status`.

---

## TL;DR — the Missions page is DONE; now make the progress bars real

Across sessions 55–58 the entire client-side missions path was solved and the **Missions modal now renders
the full page**: 4 category tabs (ONBOARDING / DAILIES / WEEKLIES / SEASONAL), each populated with the real
missions, descriptions, and XP rewards, built from all 330 registered missions. **Verified live (computer-use).**

The ONE remaining thing is the progress bars: every mission shows a placeholder **`10/20`**. Your job is two
options, IN ORDER:

- **OPTION 1 (do first): correct DISPLAY** — make every bar show its real "not started" state (`0 / real-max`)
  instead of the fake `10/20`. Client-side. When this is confirmed working on-screen, move to Option 2.
- **OPTION 2 (after #1 confirmed): real TRACKING** — the backend (`ags`) stores per-account mission-objective
  progress, the client reads it, and it fills as you play + persists. Larger, server-side.

Everything is committed (branch `dedicated-server-stub`, latest commits `S58: ...`). The reusable native-call
toolkit below is the foundation for both.

---

## WHAT'S DONE — the full client-side missions pipeline (all reusable, all live-verified)

The keystone was a **game-thread native-UFunction-call primitive**. With it, the whole page is populated
client-side by a single injected shim (`missions_nativecall_probe15.cpp`). The pipeline:

1. **Avenue A primitive (s55):** hook `ProcessInternal @base+0x13454A0`, capture a live `FFrame` (memcpy 0x180),
   then call a native UFunction's THUNK directly: `UFunction.Func @+0xE0`, x64 `(rcx=Context, rdx=&FFrame,
   r8=&Result)`. For a no-param fn set `FFrame.Code(+0x20)=NULL` (P_FINISH no-derefs). Bypasses ProcessEvent's
   guards (which no-op for native).
2. **Parameters (s56):** build a params frame (Locals); write each value at its `FProperty.Offset_Internal
   (+0x44)`; FFrame: `Code=NULL`, `Locals(+0x28)=frame`, `PropertyChainForCompiledIn(+0x88)=Function.
   ChildProperties (*(UFunc+0x58))`, clear `+0x30/+0x38/+0x40`; return → r8.
3. **OUT params (s58) — the tricky one:** `StepExplicitProperty` reads `FFrame.OutParms @ +0x80` and walks a
   `FOutParmRec` list `{Property@0, PropAddr@8, NextOutParm@16}` matching by Property ptr. Build one rec per
   CPF_OutParm(0x100)-and-not-CPF_ReturnParm(0x400) param with `PropAddr=Locals+Offset`, set `FFrame+0x80=&head`.
   (Leaving +0x80 garbage was the real cause of the earlier "anti-tamper" crashes — a bug in my setup.)
4. **Enumerate:** `PrimaryAssetIDFromString("Mission:x")`→Mission type FName; `KismetSystemLibrary::
   GetPrimaryAssetIdList(type, OUT TArray<FPrimaryAssetId>)` → all 330 mission ids (and 16 pools). FName
   indices are PER-PROCESS — resolve live each run.
5. **Map** each mission to a pool by NAME PREFIX (missions/pools decode to short names like "Tournament",
   "ArmoryDaily", "Alchemist", pools "Tournament"/"DailyChallenge"/"HunterMissions"/…). ~309 are hero/class
   missions (12 × ~24 hunters) → HunterMissions pool; the ~21 non-hero missions fill the modal tabs.
6. **Load:** `LokiAssetManager::AsyncLoadPrimaryAssets(WorldContext=ProgMgr, TArray<FPrimaryAssetId>, empty
   delegate)` — missions are REGISTERED but not LOADED; poll `GetLokiDataAsset(id)` until non-null. (params:
   WorldContext@0, Assets(TArray)@8, delegate@24, ret@40 — all IN, no OUT.)
7. **Build the model:** `MissionsModel::CreateMissionModelFromFinalProgress(TArray<FMissionProgress>)` — a
   static factory; feed FMissionProgress with `AssetId=mission id`, `PoolId=mapped pool id`, DISTINCT FString
   `ID` (the Missions map is ID-keyed — empty IDs dedupe to 1), valid dates. Returns a populated `MissionsModel`.
8. **Swap:** RPM-write `ProgressionManager.MissionsModel @ ProgMgr+0x3B8 = the new model` (roots it via the
   UPROPERTY). `GetMissionsModel()` now returns it. Reopen the modal (widgets read it on Construct).

Working shim = `tools/sigbypass-mod/missions_nativecall_probe15.cpp` (all 330) — copy it as your base.
(probe4=primitive proof, probe7=params, probe11=OUT-param fix, probe12=factory works, probe13=swap,
probe14=load+distinct-IDs, probe16=ObjectiveProgress-doesn't-drive-the-bar test.)

---

## KEY RE FACTS (this exe build)

- base (ASLR) has been `0x7FF6B54F0000` recently — **re-read each launch** (GetModuleHandle in the shim; for
  python tools pass BASE-hex).
- `ProcessInternal @base+0x13454A0`, `GGameThreadId @base+0x9D49158`, `GUObjectArray @base+0x9E38930`,
  `FNamePool @base+0x9D81450`. UObject `Class@+0x18 Name@+0x20 Outer@+0x28`. UClass `Children@+0x50,
  ChildProperties@+0x58`. UField `Next@+0x30`. UFunction `Script.Num@+0x70, Func@+0xE0`.
- FField `FFieldClass@+0x08 Next@+0x18 Name@+0x20 Flags(u64)@+0x38`. FProperty `Offset_Internal@+0x44,
  ElementSize@+0x34`. FStructProperty.Struct@+0x70, FArrayProperty.Inner@+0x78. FObjectProperty.PropertyClass@+0x70.
- `ProgressionManager.MissionsModel @+0x3B8`. `FPrimaryAssetId = {FName Type@+0, FName Name@+8}` (16B).
  `FName = {u32 index, u32 number}`. `FString = {Data, Num(incl null), Max}`. `TArray = {Data@0, Num@8, Max@12}`.
- **`FMissionProgress` (0x60):** ID(FString)@0x00, AssetId(FPrimaryAssetId)@0x10, PoolId@0x20, Complete(bool)@0x30,
  Failed@0x31, **ObjectiveProgress(TArray<FMissionObjectiveProgress>)@0x38**, MillisUntilExpiry(i64)@0x48,
  Expiry(FDateTime i64)@0x50, GrantedAt@0x58.
- **`FMissionObjectiveProgress` (0x38):** ObjectiveName(FName)@0x00, Progress(float)@0x08, MaxProgress(float)@0x0C,
  Context(TArray<FString>)@0x10, InitialArmoryContext(TArray<FPrimaryAssetId>)@0x20, StartingProgress(float)@0x30,
  Complete(bool)@0x34, Failed@0x35.
- **`UMissionModel` class fields (the per-mission model the widget reads — DUMPED s58):**
  ID(str)@0x30, MissionAssetId(struct)@0x40, PoolId(struct)@0x50, XPReward(int)@0x60,
  **Objectives(MapProperty)@0x68 ← the progress bar reads THIS**, Completed(bool)@0xB8, bHasClaimableReward@0xB9,
  OnCompleted@0xC0, OnUpdated@0xD0, MissionAsset(Object*)@0xE0, OnAssetLoaded@0xE8, IsDebugOnly@0xF8,
  GrantedAt@0x100, BaseMission(Object*)@0x108, AssetHandle@0x110.

---

## ★ OPTION 1 (DO FIRST): make the progress bars show real "not started" (0 / real-max)

**Root cause of the `10/20`:** the bar is drawn from `MissionModel.Objectives` (Map @+0x68), which the factory
builds from the mission **DA** (its objective definitions carry placeholder `10/20`). `FMissionProgress.
ObjectiveProgress` is applied ONLY when its `ObjectiveName` MATCHES the DA objective's unique name — probe16 set
it with `ObjectiveName=None` and it was ignored (bars stayed `10/20`).

Two approaches (pick after a quick investigation):

**(A) Matched ObjectiveName (clean, uses the game's own path).** For each mission, discover the real objective
name(s), then set `FMissionProgress.ObjectiveProgress = [{ObjectiveName=<match>, Progress=0, MaxProgress=<real>}]`
and rebuild + swap. Where to get name+max:
  - Read the already-built `MissionModel.Objectives` (Map @+0x68) — its KEYS are the objective names, its VALUES
    hold current/max. (Requires walking a UE `TMap`/`TSet`: sparse-array data + allocation bitmask; each element
    is `TPair<Key,Value>` + hash int. RE the value layout to find current(0x?)/max(0x?).) OR
  - Read `MissionModel.BaseMission (@+0x108)` → its `Objectives` (TArray<FLokiMissionObjective>); FLokiMissionObjective
    has `UniqueName(FName)@0` + a MaxProgress field (s54 noted the 16-field struct). OR
  - Read the loaded mission DA (`GetLokiDataAsset(id)`) objective definition.

**(B) Direct write (simplest if the value layout is known).** The model is already built with Objectives holding
`10/20`. Just walk each `MissionModel.Objectives` map and RPM-write the current-progress field of each value to 0
(leave max). No rebuild. First: dump one MissionModel's Objectives map to find the value struct + the offset of
the "current progress" field (look for the int/float `10`, and `20` = max, inside the value). Then zero all currents.

**FIRST STEP either way — dump the Objectives map of a live MissionModel** to see the value structure and confirm
where `10` and `20` live. Get a MissionModel: `ProgMgr+0x3B8` = MissionsModel; its `Missions` map @+0x30 (s52)
holds `FString→UMissionModel*`; or call `MissionsModel::GetMissions()` (return-by-value `TArray<MissionModel*>`,
already proven) and read element[0]. Then hexdump `MissionModel+0x68` (the Objectives TMap header) and follow it.

**Verify:** reopen the modal (close ⊗ then reopen) → the DAILIES/WEEKLIES/etc. tabs should show empty bars at
each mission's true max (`0/N`). The user is at the machine and will send screenshots on request (computer-use
here is flaky — ask them to close+reopen the modal and screenshot a tab). **When bars read `0/<real max>` and the
user confirms, Option 1 is DONE — proceed to Option 2.**

Notes: after a model swap the OPEN modal keeps the old widgets — either close+reopen, OR broadcast
`MissionModel.OnUpdated`/`MissionsModel` update delegate so widgets rebuild in place (nicer; find the delegate and
invoke it via the primitive). Progress persistence isn't needed for Option 1 (display only).

---

## OPTION 2 (AFTER Option 1 is confirmed): real progress TRACKING via the backend

Goal: bars fill as the player completes objectives, and persist per account. This needs the **`ags` server**
(`server/cmd/ags`, Go) to own mission-objective progress, plus a client path to read it. Sketch:

1. **Determine the read path.** Does the client pull mission progress from the backend today? The live capture
   (`docs/capture.log`) shows `GET /progression/players/{id}` (+`/tracks`) — AccelByte progression stats, not
   missions (s52: no `/mission` calls ever). So there is NO existing HTTP mission-progress feed; the client's
   Objectives come from the DA. Options: (a) extend `ags` with a mission-progress store + a new endpoint, and have
   the client-side shim FETCH it and write it into `FMissionProgress.ObjectiveProgress` (matched names, Option-1
   machinery) each menu load; or (b) reuse the DS/replication schema (s54 `LokiPlayerState_Missions` +
   `FMissionProgress`) — but that route hit the main-menu-HUD wall, so the shim-reads-backend path (a) is cleaner.
2. **Store + serve (ags).** Add a per-account mission-progress table (missionId → per-objective current). Serve it
   (e.g., `GET /loki/missions/{playerId}` returning the granted set + progress). Seed/rotate a daily/weekly set.
3. **Increment (the hard part).** Progress must go UP when the player does the objective (get knocks, play a game,
   etc.). Real SUPERVIVE did this server-side from match results. For the revival: either (a) parse match-end
   results the client already reports to `ags` and increment matching objectives, or (b) a coarser heuristic
   (per-game increments). Persist.
4. **Apply on the client.** The menu shim (Option-1 machinery) fetches the player's progress from `ags` and builds
   the model with matched `ObjectiveProgress` = real values → bars reflect reality; `Completed`/`bHasClaimableReward`
   drive the claim UI (`MissionModel::ClaimReward` exists).
5. **Durable packaging.** Fold the whole thing into a shim that runs from the ProcessInternal hook on menu load
   (like `catalog_store_fix`) instead of manual injection, so it "just works" on launch.

---

## RECIPE (elevated PowerShell; Steam running first, else Auth Failure 14005)

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -Hook "G:\git\Supervive Revival Project\tools\sigbypass-mod\catalog_store_fix.dll"
```
Explicit `-Hook` => catalog_store_fix ONLY (full menu, no pi8 secondaries) so your PI-hooking shim is the sole one.
Wait for `HUD BeginPlay - BP_MainMenuHUD_C` + `TryUIReady SUCCESS` in the client Loki.log
(`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`) and for `docs/catalog-store-fix-marker.txt` to show
`jz=1/1 unhook=1` (settled). Menu reaches in ~20s. Then:
```
tools\inject\inject.exe mmap <PID> tools\sigbypass-mod\<your-probe>.dll
```
Build shims: `clang++ -shared -O2 <f>.cpp -o <f>.dll -lkernel32`
(clang++ at `C:\Users\eastr\AppData\Local\Programs\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`).
RE tools (python, read-only RPM): `tools/re/{sig_enum,param_probe,struct_layout,find_func,func_enum}.py <PID> <BASE>`.

## GOTCHAS
- **base changes each launch** — re-read it. **FName indices are per-process** — resolve live (never hardcode
  across launches).
- The model swap is TRANSIENT (reverts on relaunch). Durable = do it from the hook on menu load (Option 2 step 5).
- Copy a marker path when copying a probe (probe15/16 initially wrote to the wrong marker — cosmetic).
- catalog_store_fix must settle before you inject (thread-suspend races). Steam up first.
- Computer-use for the game window is flaky/denied in-session — the user (at the machine) sends screenshots on
  request. Ask them to close+reopen the Missions modal and screenshot a tab to verify.
- The prefix→pool mapping in probe15 has a greedy-substring quirk ("ArmoryOnboarding" matched "Onboarding" first) —
  tighten `FindPoolSub`/rules if a mission lands in the wrong tab. Non-hero missions land in the modal tabs;
  the 309 hero missions go to HunterMissions (a per-hunter surface, not these tabs).

## FILES
- Shims: `tools/sigbypass-mod/missions_nativecall_probe{4,7,11,12,13,14,15,16}.cpp` (probe15 = full page; copy it).
- RE tools: `tools/re/{sig_enum,param_probe,struct_layout,find_func}.py`.
- Docs: `docs/session-55-native-call-primitive.txt`, `docs/session-56-param-passing-and-factory.txt`,
  `docs/session-57-da-resolution.txt` (S58 sections = the missions build + modal-render proof).
- Catalog: `tools/extractor/out/catalog/missions_catalog.json` (346 entries: 330 missions + 16 pools; fields
  Name/Parent/Desc/XP/Pool(None)/Hide/Hero — no objective/max data, so read those live from the DA/model).

## FIRST MOVES (Session 59)
1. Read the S58 sections of `docs/session-57-da-resolution.txt` + the two memory files.
2. Relaunch (recipe above), get PID + base. Rebuild the full page (copy probe15) to confirm it still renders.
3. OPTION 1: dump a live `MissionModel.Objectives` (Map @+0x68) to find where current(=10)/max(=20) live, then
   zero the currents (direct write) or rebuild with matched `ObjectiveName`+Progress=0. Have the user close+reopen
   the modal and screenshot a tab; confirm bars read `0/<real max>`.
4. When confirmed, OPTION 2: extend `ags` to store/serve mission progress + have the menu shim fetch and apply it,
   then wire increments from match results. Package as a durable menu-load shim.
