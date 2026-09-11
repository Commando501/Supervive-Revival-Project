# Session 91 (2026-07-24) — quest actors spawned, the BP-call primitive built, training STARTED

Branch `dedicated-server-stub`, FORCE-OPEN tutorial route. Continues S90. Live-verified end-to-end in one
force-open session (pid 3232, force-open landed cleanly on the FIRST launch this time). All work is UNCOMMITTED.

## TL;DR — three concrete wins, one precisely-located remaining gap

1. **The S91 task is DONE**: the `TrainingQuest_Basics_*` actors spawn DIRECTLY via the S74 GameplayStatics
   deferred path, survive, and **self-wire** — a freshly spawned `TrainingQuest_Basics_WASD_C` came up with its
   `TargetTriggerBox` pointing at a LIVE `TriggerBox` and `OBJARROW` at a live
   `BP_GameplayEffectCapsule_Tutorial_OBJ_LOC_C`, i.e. its `ReceiveBeginPlay` ran and resolved level actors.
2. **NEW REUSABLE PRIMITIVE — the Blueprint-function-call primitive** (the missing half of the S55 native-call
   primitive). Self-verified. Lets the shim call ANY BP-bytecode UFunction, project-wide.
3. **Found + called the tutorial's REAL lesson driver**:
   `Comp_GameState_TrainingBase_C::GameStateTryStartTraining(NewVolume)` → **`TrainingActive` 0→1** and
   `CurrentTrainingVolume` 0→the live volume. This is the tutorial's own "start training at this volume" entry.
4. **Remaining gap**: after `GameStateTryStartTraining`, `TrainingActive=1` but no objective is counting yet and
   the lesson-display overlay (`WBP_BasicTutorialOverlay_Root`) is NOT instantiated (its child widgets
   `WBP_Augment_TutorialProgressTracker` + `WBP_TutorialDialogueBox` ARE). Next lever = objective registration +
   `ProgressObjective`, and/or the physical `OnWASDTriggerOverlap` for genuine-gameplay completion.

## The architecture, now fully mapped (live-confirmed)

The tutorial quests are **team augments**. Inheritance (from live `func_enum`):
```
TrainingQuest_Basics_WASD_C
  -> TrainingQuest_Basics_Base_C        (OnObjectiveComplete[BlueprintAuthorityOnly], OnTrainingVolume, ReceiveBeginPlay)
  -> BP_TeamAugment_Training_C          (UpdateAssociatedTrainingVolume, CanPing, AuthTutorialPing, OnTrainingFinished, ...)
  -> BP_TeamAugment_C                   (OnObjectiveComplete, SpawnReward*, GetQuestWeight, ...)
  -> native TeamAugment                 (ApplyEffectToTeam, IncrementObjectiveCount, AddObjectiveCount, AuthOnComplete — all NATIVE)
```
The per-quest fields (offsets from `BP_TeamAugment_Training_C` base): `AssociatedTrainingVolume`@0x688,
`AssociatedTrainingVolume`-setter `UpdateAssociatedTrainingVolume`; and on the WASD leaf:
`TargetTriggerBox`@0x820 (live TriggerBox), `OBJARROW`@0x848, `TargetLocation`@0x830, `CurrentMark`@0x808.

**The driver is NOT the generic augment manager.** `Comp_GameState_GameAugments_C` (native base
`LokiGameAugmentManager`, `SetGameAugmentClass`) is the roguelite GAME-augment picker — a red herring for the
tutorial. The tutorial's own driver is **`Comp_GameState_TrainingBase_C`** (3 live instances), whose functions are:
```
GameStateTryStartTraining   (454 bc)  <- START a lesson for a volume  ★ CALLED THIS SESSION -> TrainingActive 0->1
ProgressObjective           (36)       <- advance the objective count   ★ NEXT
EndTraining / CallTrainingCompletions / ResetTrainingStates / OnObjectiveCountUpdated / GameStateStartTimer
CurrentTrainingVolume / TrainingActive / CurrentObjectiveCount (rep'd fields)
```
Also live: `Comp_PlayerController_TutorialObjectives_C` (1, added at runtime by the gamemode BP — its 3 actions are
`FUNC_NetServer` RPCs, which on FORCE-OPEN the client-as-authority CAN run locally).
`SoloAugmentPlayerState` and `BP_Loki_Team_State_Code` = **0 instances** (the sequencer's ubergraph casts the quest's
`Quest` field to TeamState and reads `SoloAugmentPlayerState`; neither exists on force-open — so the SEQUENCER path
is inert, but the **TrainingBase-component path is not**).

## ★ THE BLUEPRINT-FUNCTION-CALL PRIMITIVE (new; the reusable deliverable)

The S55 native-call primitive calls a UFunction's `Func` thunk (@+0xE0) with `FFrame.Code = NULL`. That is correct
for a NATIVE thunk and **fatal for a BP function** — a BP UFunction's `Func` IS `ProcessInternal`, so `Code=NULL`
executes bytecode from address 0. That is exactly why every tutorial-quest function (all bytecode) was unreachable.

FIX = do what `UObject::ProcessEvent` does: set `FFrame.Code` to the function's OWN bytecode
(`UStruct.Script.Data`@+0x68) and `FFrame.Locals` to a zeroed blob of `UStruct.PropertiesSize`(@+0x60) bytes, then
call the SAME `Func` thunk (which for a BP func == ProcessInternal). **No new address to guess** — this sidesteps the
ProcessEvent-RVA question S80 falsified. Params/out-params marshal into the locals blob exactly as for natives
(reusing `BuildOutParms`). Implemented as `CallBPGuarded(func, context, resultBuf)` in `tutorial_launch.cpp`.

**Self-verified live**: `UpdateAssociatedTrainingVolume(vol)` on the WASD quest changed
`AssociatedTrainingVolume` 0x0 → the volume ptr — proving the bytecode really executed (not just "didn't crash").
Marker confirmed `func=base+0x13454A0` = ProcessInternal, exactly as theorized.
New UStruct offsets used (this build, stock UE5 order shifted +0x18): `PropertiesSize@0x60`, `Script.Data@0x68`,
`Script.Num@0x70`. ⚠ FField's TYPE class is at **FField+0x08** (`FFieldClass*`), NOT +0x18 — do not reuse UObject
`ClassOf` to read a property's type (my first type-name print was garbage because of this; the CALL was unaffected).

## What was run, in order (all clean, game stayed alive ~22 min)

| shim | mode | result |
|---|---|---|
| `tutorial_launch_fo.dll`    | force-open | LVL_Tutorial + real gamemode, initializer → **Finished** (1st try) |
| `tutorial_launch_quest.dll` | `RM_SPAWNQUEST` | discovered **32 loaded quest classes**; spawned WASD/Jump/LMB/Glide + sequencer; all self-wired; `AssociatedTrainingVolume` was null (poke to the volume worked as a data write) |
| `gft_ready_fix.dll` + `tutorial_launch_sp.dll` | — | hero `BP_HERO_Ronin_C` spawned + possessed |
| `tutorial_launch_qplay.dll` | `RM_QUESTPLAY` | teleported the possessed hero into the quest's `TargetTriggerBox` (-1392,-178,50) and the training volume (283,277,-250) — hero moved exactly, but **no overlap fired** (quest not active + force-open hero collision doesn't generate overlaps) |
| `tutorial_launch_bpcall.dll` | `RM_BPCALL` | BP-primitive self-test PASS; `OnTrainingVolume`/`ReadyToFire` ran clean but no-op; **`GameStateTryStartTraining(vol)` → TrainingActive 0→1, CurrentTrainingVolume set** |

## New shim modes added to `tools/sigbypass-mod/tutorial_launch.cpp` (UNCOMMITTED)

- `RM_SPAWNQUEST` (10) → `tutorial_launch_quest.dll`: discover-by-substring the loaded `TrainingQuest_Basics_*`
  UCLASSES (bases/CDOs/SKEL excluded), spawn the first `-DKQUESTMAX=N` in lesson order (WASD first) at the live
  volume with Scale3D=1, then spawn the sequencer, census, dump `AssociatedTrainingVolume`, and (phase 2) poke it.
- `RM_QUESTPLAY` (11) → `tutorial_launch_qplay.dll`: respawn a WASD quest with the hero present, resolve its
  `TargetTriggerBox` world loc, teleport the possessed hero there (retry: the training volume).
- `RM_BPCALL` (12) → `tutorial_launch_bpcall.dll`: the BP-call primitive + a staged sequence
  (CanPing → UpdateAssociatedTrainingVolume[self-verify] → OnTrainingVolume → ReadyToFire → **GameStateTryStartTraining**).
  Build any of them with `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKRUNMODE=<mode> tutorial_launch.cpp -o <out>.dll -lkernel32 -luser32`.

## ★ S92 CONTINUATION (same live session, pid 3232) — the lesson VISUALLY starts; completion is gated

**USER-CONFIRMED VISUAL WIN**: `GameStateTryStartTraining(volume)` did more than flip a flag — it spawned the WASD
lesson's on-map GUIDANCE: the directional MOVEMENT ARROWS (»»» chevrons) + objective notifier rings appeared in the
world with the possessed hero on the ground (user screenshots). The bytecode confirms why: it sets
`CurrentTrainingVolume`, resets `CurrentObjectiveCount`, sets `TrainingActive=true`, and fires
`OnRep_TrainingActive` + `OnRep_CurrentObjectiveCount` — those OnReps drive the client-side arrows/objective UI.
(Also seen: hero-spawn moves the camera to the drop-altitude sky; after possess the camera is a super-zoomed,
rotatable close-up on the hero — a separate cam-fix item, not blocking.)

**`ProgressObjective(int)` signature confirmed** (offline bpdump): sets `ProgressAmount` on the persistent frame →
`ExecuteUbergraph(768)`. `OnWASDTriggerOverlap(OverlappedActor, OtherActor)` just jumps to the ubergraph.

**RM_OBJDRIVE (mode 13 → `tutorial_launch_objdrive.dll`)** drove the active WASD objective FOUR ways on the live
session — ALL ran clean (no fault) but changed NOTHING (`CurrentObjectiveCount` stayed 0):
1. PHYSICAL teleport of the possessed hero onto the quest's `TargetTriggerBox` (-1392,-178,50) — no overlap fired.
2. `quest.OnWASDTriggerOverlap(box, hero)` via the BP primitive — ok, no-op.
3. `TrainingBase.ProgressObjective(1)` ×3 via the BP primitive — ok, no-op.
4. native `TeamAugment::IncrementObjectiveCount` + BP `quest.OnObjectiveComplete` (authority) — ok, no-op.

**ROOT CAUSE of the S92 no-ops**: the quest instances I spawned in S91 are **ORPHANS** — the one driven had
`CurrentMark=0` and `CurrentObjectiveCount=0`, i.e. it is NOT the quest the training system activated (the one
that spawned the arrows). `GameStateTryStartTraining` activated the tutorial's OWN registered objective internally;
my manually-spawned quests are not wired into the training component's active-objective slot, so poking their
completion functions does nothing, and `ProgressObjective` on the component no-ops because no MY-side objective is
its registered current one. **Completion is owned by the tutorial's real objective flow + player MOVEMENT INPUT**
(`GetWASDInputs`, 149 bc, detects W/A/S/D presses) — and that input path is the S75 deploy-gated wall (force-open
hero produces no `ControlInputVector`). So "complete WASD through gameplay" reduces to two sub-problems, both real:
(a) get a handle on the tutorial's REAL registered objective (not my orphan spawns), and (b) feed real movement
input past the S75 deploy gate (or find where `GetWASDInputs` reads and satisfy it).

**⇒ Corrected next-step priority (supersedes the S91 list below):**
1. **Don't spawn orphan quests.** Instead, enumerate what `GameStateTryStartTraining` registered as the CURRENT
   objective on `Comp_GameState_TrainingBase_C` (dump its objective-ref / array fields live; `class_props.py` +
   read the instance) and drive THAT object, not a hand-spawned one.
2. **Why do the completion fns no-op even on the right object?** Disassemble `ProgressObjective`'s
   `ExecuteUbergraph(768)` gate (likely `HasAuthority`/registered-objective-ref) — the S91 BP primitive can call it,
   but the bytecode may bail internally. Confirm the component's Role is authority on force-open.
3. **`GetWASDInputs` (149 bc)** — dump it: does it read raw key state, the input component, or the (dead) CMC? If
   raw key state, real WASD could complete it even un-deployed; if CMC, it's the S75 wall.

## (S91 list, partially superseded by S92 above) NEXT — turn TrainingActive into a countable, completable objective

1. **Register the quest as the active objective**, then `ProgressObjective` on `Comp_GameState_TrainingBase_C`
   (BP-callable now) and watch `CurrentObjectiveCount`. Read `bpdump Comp_GameState_TrainingBase ProgressObjective`
   + `... GameStateTryStartTraining` (already in out/) for what fields they set — `GameStateTryStartTraining` reads
   `NewVolume.VolumeTag`, so the volume must carry the tag the quest expects (check the WASD quest's expected tag).
2. **Show the lesson overlay**: `WBP_BasicTutorialOverlay_Root` has 0 instances; its children exist. Find who
   creates it (the TrainingBase component's `OnTrainingStart` delegate, or `Comp_PlayerController_TutorialObjectives`).
3. **Genuine-gameplay completion**: the WASD quest binds `OnWASDTriggerOverlap` to `TargetTriggerBox`. The teleport
   didn't fire it — check the force-open hero's collision (does its capsule generate overlap events?) and whether the
   quest must be the ACTIVE objective before the box arms. If overlap can be made to fire, real hero movement
   completes the objective "as intended" (the user's explicit ask).
4. **Completion → menu**: `OnObjectiveComplete` (authority; force-open IS authority) → `EndTraining` →
   `CallTrainingCompletions`; then the existing exit-to-menu path. Credit the menu mission
   (`NewOnboarding_CompleteBasicTraining`) via `objectiveRules` in `interactive/missions.go`.

## Env at handoff

Config REVERTED to baseline: `forceTutorialMatch = false`, `ConnectionDetails.address = "127.0.0.1:7777"`,
`kEnableServerAuthConfig = false`. Nothing committed. The S91 game (pid 3232) may still be up in the tutorial with
training active + a possessed hero + 5 quests spawned — kill it and start fresh for a new run.
Shims built this session: `tutorial_launch_quest.dll`, `tutorial_launch_qplay.dll`, `tutorial_launch_bpcall.dll`.
Recipe unchanged from S91 handoff (delete Loki.log first; resolve the live pid; inject fo → wait Finished → inject
the experiment). Force-open landed 1st try this session (the intermittent crash didn't recur).
