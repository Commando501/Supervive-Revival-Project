# Tutorial mission end-to-end — architecture + plan (2026-07-23, S90)

GOAL: start the tutorial from the menu -> load in -> PLAY it, completing objectives through gameplay -> exit to menu.

> ## ⚑ READ THIS FIRST — how to navigate this doc
> This grew iteration-by-iteration across one long session, newest last. **Several early sections were later
> DISPROVEN by measurement and are explicitly marked `(superseded)` / `⚠ CORRECTION`. Always prefer the LATER
> section when two disagree.** The trustworthy summary is:
> 1. **Route is settled**: only the FORCE-OPEN route can ever complete objectives
>    (`OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`; the DS stub is a networked client and can never be
>    authority). Do not re-open the DS route for this goal.
> 2. **The tutorial's lesson chain is `TrainingQuest_Basics_*` + `BP_TutorialTrainingQuestSequencer`**
>    (under `Objectives/Tutorial/Basics/`). The `BP_TrainingManager` + `BP_TrainingSkill_*` family is a separate
>    **PRACTICE-mode** system (its `ValidStates` exclude the tutorial) — a proven DEAD END, do not chase it.
>    (An earlier section claims the opposite; it is marked as corrected.)
> 3. **Proven live**: force-open loads the real tutorial gamemode to initializer-Finished; heroes and arbitrary
>    level actors can be spawned via GameplayStatics; the sequencer actor itself was spawned successfully.
>
> ### ★★★ S91 UPDATE (2026-07-24) — the newest truth supersedes items 4-5 above. See `docs/session-91-quest-spawn-bpcall.md`.
> 4. **The `TrainingQuest_Basics_*` actors CAN be spawned directly** (S91): 32 classes are loaded; spawning
>    `TrainingQuest_Basics_WASD_C` via the GameplayStatics deferred path works and it **self-wires** (its
>    `TargetTriggerBox` resolves to a LIVE `TriggerBox`, `OBJARROW` to a live capsule).
> 5. **The quests are TEAM AUGMENTS**, and the SEQUENCER is a red herring for driving them on force-open (its
>    ubergraph casts to `BP_Loki_Team_State_Code` / reads `SoloAugmentPlayerState` — both 0 instances here). The
>    **real driver is `Comp_GameState_TrainingBase_C`**: `GameStateTryStartTraining(NewVolume)` STARTED training
>    (`TrainingActive` 0→1) this session, `ProgressObjective` advances it, `EndTraining` finishes it.
> 6. **NEW REUSABLE CAPABILITY — the Blueprint-function-call primitive** (`CallBPGuarded`): set `FFrame.Code =
>    UFunction.Script.Data` + Locals = zeroed `PropertiesSize` blob, call the same `Func` thunk. Reaches ANY
>    BP-bytecode UFunction (the tutorial chain is all bytecode; the S55 direct-thunk primitive could not). Self-verified.
> 7. **Current blocker**: after `GameStateTryStartTraining`, `TrainingActive=1` but no objective is counting and the
>    lesson overlay `WBP_BasicTutorialOverlay_Root` isn't instantiated. NEXT = objective registration +
>    `ProgressObjective`, spawn/show the overlay, and get the physical `OnWASDTriggerOverlap` to fire for
>    genuine-gameplay completion. Full detail + next steps in `docs/session-91-quest-spawn-bpcall.md`.
> 8. **Next action** is in `docs/next-session-prompt-s94.md` (S93 recap in `docs/session-93-objectives-camera-deploy.md`).
>
> ### ★★★ S93 UPDATE (2026-07-24) — objectives DONE, camera DONE, and the "visible hero" wall OVERTURNED.
> - **Objectives complete + the lesson chain walks** (WASD→LMB→Dash→Jump) via `GameStateTryStartTraining` + the
>   UNGATED `OnRep_TrainingActive` closer. The physical overlap can't fire on force-open (bind absent); use the closer.
> - **Camera fixed** to top-down (spawn a CameraActor + re-assert the view target).
> - **★ A visible hero does NOT need the server binary** (my earlier claim was wrong): `AddComponentByClass` (NATIVE)
>   created a real SkeletalMeshComponent on the hero + `SetSkeletalMeshAsset` assigned a body mesh — the game's
>   cosmetics controller is bypassed. Mechanism PROVEN; a clean on-screen body is a refinement (Ronin's actual mesh +
>   hero on the ground + stable game). NEW reusable primitive: the Blueprint-function-call primitive (`CallBPGuarded`).
> - Deploy walls that ARE real: the DropPlane `SpawnPlane` descent (faults on absent level markers) + the game's own
>   cosmetics cascade (0 controllers, never created outside real deploy). Full detail + refinement plan in the S93 doc.

## ★★★ THE ROUTE IS DECIDED BY A BLUEPRINT FLAG — force-open, not the DS stub

`TrainingQuest_Basics_Base.OnObjectiveComplete` is **`FUNC_BlueprintAuthorityOnly`**
(tools/extractor/out/bpdump_TrainingQuest_Basics_Base_ALL.txt). It executes ONLY where `Role == ROLE_Authority`.

- **DS route (unreal-stub):** the client is a networked CLIENT -> never authority -> `OnObjectiveComplete` can never
  fire -> objectives can NEVER complete. Corroborated: `Comp_PlayerController_TutorialObjectives`'s three action
  functions (`SendShopClosedEvents`, `SentAbilityOverlayClosedEvent`, `SpawnJouleBot`) are all
  **FUNC_Net | FUNC_NetServer** — server RPCs that our stub does not implement, so they vanish.
  ⇒ **The DS route is structurally incapable of a completable tutorial.** (It remains the better route for
  netcode/possession experiments and the S70 spectator milestone, but not for this goal.)
- **Force-open route:** the client runs the real `BP_LokiGameMode_Tutorial` standalone AS AUTHORITY, so
  `FUNC_BlueprintAuthorityOnly` bodies run and `NetServer` RPCs execute locally.
  ⇒ **Only force-open can deliver the objective + completion halves of the goal.**

## The tutorial mission architecture (all Blueprint, all shipped in the paks)

Driver actor: **`BP_TutorialTrainingQuestSequencer_C`** (placed actor; DefaultSceneRoot + SCS node)
  - `BP_LokiBeginPlay` -> starts the chain
  - `ReadyToFire` (28 bytecode entries; takes the quest FClassProperty + arrays/indices) -> arms the next quest
  - `OnGameEvent_Tutorial_QuestComplete` -> advances the chain
  - `ExecuteUbergraph` (59 entries) -> the state machine

Quest base: **`TrainingQuest_Basics_Base`**
  - `OnObjectiveComplete`  ← **FUNC_BlueprintAuthorityOnly** (the load-bearing flag above)
  - `OnCompleteClient`     ← client-side mirror
  - `OnTrainingVolume`     ← trigger entry point
  - `GetHeroCharacter`, `GetQuestChainInformation`, `SetBotBehavior`, `ResetCooldowns`, `OnTimeExpiration`

Support: `BP_TrainingVolume_Basics` (7 fns, the trigger volume), `Comp_PlayerController_TutorialObjectives` (5),
`Comp_PlayerController_TutorialHighlighting` (6), `BP_Tutorial_JouleBotManager` (17),
`BP_LokiSpawner_Basics_*` (bot spawners), `BP_ResetVolume_Training`.
UI: `WBP_BasicTutorialOverlay_Root`, `WBP_TutorialDialogueBox`, `WBP_InGameTutorialVideo`.

The actual mission steps (~30 `TrainingQuest_Basics_*` assets): WASD, Jump, LMB, RMB_Use, Q_Use, Dash_Use,
Ult_Level, Glide, CapturePoint, DefeatBots, DefeatSingleBot, ShopInteract, CloseShop, ShopViveBrew, ArmorPickup,
UseArmorPack, Brew, Ping, Recall, Sneak_Use, Stagger, Resurrect{AllyBox,AllyWisp,AtBeacon}, UpgradeAbilities,
AbilityOverlay_Use (+ bases `_Base`, `_Level_Base`, `_UseAbility_Base`). Advanced set: Boss + Vaults quests.

## What is ALREADY PROVEN on the force-open route (do NOT re-derive — see the commits)

- Force-open travel into LVL_Tutorial with the REAL gamemode (`tutorial_launch.cpp` ExecuteConsoleCommand `open`).
- `ALokiGameMode::Login` reject BEATEN — GameMode C++ vtable **slot 285** de-override (S63).
- "PlayerState is null" BEATEN durably while KEEPING the real Loki PC — PC vtable slots **260 + 273** (S63).
- "Client is ready to play" + TryUIReady SUCCESS reached (S63).
- The `ULokiServerPlatformInstance` revert BEATEN — via the ags hybrid (forceTutorialMatch=true + **EMPTY**
  ConnectionDetails.address); gamemode initializer runs Stage0 -> Stage3 **FINISHED**, no revert, **bots spawn** (S65/S66).
- Round phase machine drivable: native `GoToPhase` (thunk rva 0x560F200); {2,3,6,7} -> Combat stable (S74).
- ★ **HERO SPAWN + POSSESS WORKS** (S74) — BeginDeferredActorSpawnFromClass(BP_HERO_*_C) + FinishSpawningActor +
  Possess, unblocked by the S58 OUT-param marshalling. USER-CONFIRMED: view rotation, aim ring, jump.
  (This OVERTURNS S68's "four spawn methods failed" ceiling.)
- Hero movement works with real collision; WASD via the CMC velocity puppet (S75).
- Exit to menu works (net failure -> LVL_Login?closed -> LobbyV2 -> BP_MainMenuGameState_C).
- Prebuilt DLLs on disk: `tutorial_launch_fo.dll` (force-open), `tutorial_launch_sp.dll` (spawn+possess),
  `tutorial_launch_phase.dll` (GoToPhase), `tutorial_launch_puppet.dll` (WASD). Inject: `inject.exe mmap <PID> <dll>`.
  ⚠ `tutorial_launch.cpp`'s in-source default is `#define KRUNMODE RM_CHEATSPAWN` — a DEAD route; always pass
  `-DKRUNMODE=` explicitly when rebuilding.
- `gft_ready_fix.dll` flips the feature-toggle readiness bit (11/11) — did NOT exist when the S75 mantle/unready-toggle
  movement crash was measured, so that crash has never been retested with it loaded.

## ★★★ LIVE RESULT (S90, force-open run, pid 32040) — THE TUTORIAL MACHINERY RUNS ON THIS ROUTE

Config: `forceTutorialMatch=true` + `ConnectionDetails.address=""`; no DS stub. Injected (in order, all clean,
game stayed alive throughout): `tutorial_launch_fo.dll` -> `tutorial_launch_phase.dll` -> `tutorial_launch_sp.dll`.

Client log (this run):
```
Browse "/Game/Loki/Maps/Tutorial/LVL_Tutorial?game=/Game/Loki/Core/GameModes/B..."
Setting Phase to 1 (BeginInit)
Entering game state BP_LokiGameState_Tutorial_C_2147473089     <- the REAL tutorial GameState
Client is ready to play.
Initialization Stage 0 -> 1 -> 2 -> 3 -> Finished              <- no revert, no ServerPlatformInstance error
LogLokiTraining: ULokiTrainingManager::ResetAll Resetting all trainings
then via GoToPhase: Phase 2 (Pre) -> 3 (FinishInit) -> 4 (SpawnSelect)
```

LIVE census (tools/re/obj_by_class.py) — the tutorial system IS instantiated:
- `BP_TrainingManager_C`                      <- THE DRIVER
- `BP_TrainingSkill_SpikeEnemies_C`, `BP_TrainingSkill_LevelAbility_Specific_C`,
  `BP_TrainingSkill_ESCMenu_C`, `BP_TrainingSkill_Abyss_C`   <- THE LESSONS
- `Comp_GameState_TrainingBase_C` x2, `Comp_PlayerController_BasicTrainingText_C` x2
- `BP_TrainingVolume_Basics_C` = `BP_TrainingVolume_Move_V2_C_UAID_...` (level-placed, WorldPartition)
- `BP_ResetVolume_Training_C`
- `Comp_PlayerController_TutorialObjectives_C` = `NODE_AddComp_PlayerController_TutorialObjectives-0`
  (added at runtime by the gamemode BP graph — confirms the component DOES get created on this route)
- `BP_HERO_Ronin_C` (our spawned hero)

★ KEY CORRECTION: `LVL_Tutorial` drives its lessons via the **BP_TrainingManager + BP_TrainingSkill_*** family.
The `TrainingQuest_Basics_*` / `BP_TutorialTrainingQuestSequencer` assets belong to a DIFFERENT tutorial level and
show 0 instances here — do not chase them for LVL_Tutorial.

STILL MISSING: nothing has STARTED a lesson (only one `ResetAll`, no lesson-begin log, no quest objects).
Open questions for next session:
1. Enumerate `BP_TrainingManager_C` + `Comp_GameState_TrainingBase_C` + `BP_TrainingSkill_*` UFunctions
   (tools/re/func_enum.py / find_uclass.py / ufunc_params.py) to find the "begin/advance training" entry point,
   and the native `ULokiTrainingManager` (which owns ResetAll) alongside it.
2. Is the hero POSSESSED and is it anywhere near `BP_TrainingVolume_Move_V2`? The volume is an overlap trigger —
   the first lesson likely needs the player physically inside it (get its world location, teleport the hero there).
3. Does a lesson need a later round phase than SpawnSelect(4)? (GoToPhase to Combat(7) is documented stable.)

## ★★★ THE TUTORIAL DRIVER API — native `LokiTrainingManager` (live-enumerated S90, ufunc_survey.py)

Enumerated off the LIVE `BP_TrainingManager_C` @0x194971C8900 (force-open session). RVAs are `base+`:
```
SetActive                          0x548A790  PropSz16 Parms9   Native,Static,BPCallable   <- ACTIVATE A LESSON
StartTimers                        0x548AAC0  Parms 0           Native
ResetAll                           0x548A770  Parms 0           Native,BPCallable          <- already fired once
ChangeSkillPrompt                  0x5489F90  Parms 24          Native,BPCallable
AddActiveTrainingAugment           0x5489B00  Parms 8           Native,BPCallable
RemoveActiveTrainingAugment        0x548A6C0  Parms 8           Native,BPCallable
ContainsActiveTrainingAugment      0x548A120 / ...Soft 0x548A1D0
IsActiveSkill 0x548A450 / IsTestingSkill 0x548A5C0 / IsPromptSkill 0x548A520 / IsActive 0x548A3C0 (Static)
HasTrainingPrompt 0x548A390 / GetTrainingPrompt 0x548A340
BP_GetLokiTrainingManager          0x5489E60  Native,Static,BPPure                          <- the accessor
```
★ REAL SIGNATURES — recovered live by the RM_TRAINING probe (S90). My "SetActive(Skill,bool)" guess was WRONG:
```
SetActive(WorldContextObject @0x0, bActive @0x8)      <- GLOBAL toggle taking a WORLD CONTEXT, not a skill
IsActiveSkill(TargetSkill @0x0, ReturnValue @0x8)     <- per-skill query
AddPlayerToDropPlane(PlayerState @0x0)                <- wants a PLAYERSTATE, not a PlayerController
SpawnPlane(ReturnValue@0x0, PlaneCenteredLocation@0x8, SelectedDropPlaneType@0x20, EndPos@0x28,
           StartPos@0x40, LocDropPlane@0x58, + BP locals)   <- BP fn (dispatches via ProcessInternal), needs REAL params
```
PROBE RESULT (tutorial_launch_train.dll, `-DKRUNMODE=RM_TRAINING`): resolution perfect (mgr/drop/pc + 4 skills, all
thunks). `IsActiveSkill` = 0 for all four skills BEFORE **and AFTER**. `SetActive`/`StartTimers`/`AddPlayerToDropPlane`
returned fault-free but were fed WRONG arg types (skill-as-WorldContext, PC-as-PlayerState). `SpawnPlane` FAULTED
(null read @rva 0x13455D0 = ProcessInternal) because it was called with an EMPTY param buffer. Game SURVIVED (VEH).
ITER2 (arg fixes applied): `PC->PlayerState@0x3C0 = BP_LokiPlayerState_C`. ALL calls then ran FAULT-FREE —
`SetActive(worldCtx=PC,true)`, `AddActiveTrainingAugment(skill[0..3])`, `StartTimers()`,
`AddPlayerToDropPlane(PlayerState)`. **But NOTHING STUCK**: after all of it, every skill still reports
`IsActiveSkill=0` AND `ContainsAugment=0`. Why (from the recovered param names):
- `AddActiveTrainingAugment(**NewAugment**)` / `ContainsActiveTrainingAugment(**SearchAugment**)` — an AUGMENT is a
  DIFFERENT TYPE from a skill (live census: only `WBP_UI_GameAugment*` / `Comp_GameState_GameAugments_C` exist).
  Feeding a `BP_TrainingSkill_*` there silently no-ops. The augment list is NOT the lesson-activation path.
- `GetAutoDropLocation(**DropPlane**@0x0, RandomLocation@0x8 OUT, MaxRetries@0x20, NumRetries@0x24, …)` needs a
  DROP-PLANE ACTOR — and a live census shows **0 `BP_DropPlane*` actors exist**. That is why the drop never commits:
  there is no plane. `SpawnPlane` must create one first (it is the BP fn that faults on an empty param buffer).

## ★★★ THE LESSON LIFECYCLE API — native `LokiTrainingSkill` (live-enumerated, S90 iter2). THIS is the real path.
Activation is PER-SKILL on the skill object, NOT on the manager:
```
TryTestSkill        native+0x548AB20  Parms1 (ret bool)  Native,BPCallable   <- START a lesson
TryShowPrompt       native+0x52FD980  Parms1 (ret bool)  Native,BPCallable   <- show its prompt
MarkTestCompleted   native+0x548A680  Parms0             Native,BPCallable   <- COMPLETE it
CancelTest          native+0x5489F70  Parms0             Native,BPCallable
CanTestSkill        native+0x5489F40  Parms1 (ret)       Native              <- gate
ShouldTestSkill     native+0x548AA90  Parms1 (ret)       Native              <- gate
GetSkillState       native+0x44157D0  Parms1 (ret)       Native,BPCallable,BPPure  <- observable state
GetTrainingManager  native+0x5483C00 / IsDisabledForConfig native+0x548A4F0
events: BP_OnActiveBegin/End, BP_OnReadyBegin/End, BP_OnTestBegin/End, BP_OnPromptShown/Hidden,
        BP_TickWhenTested, BP_TickWhenShown
BP_TrainingSkill_C (BP layer) adds: TrainingComplete(Parms16), TrainingAugmentComplete(Parms8),
        HasCompletedQuest(Parms17), BindFinishedWhenAugmentBegins(Parms8), GetWASDInputs, Get Action Key,
        IsActorOfClassNearby / IsActorOfClassRecentlyRendered
```
### ITER3 RESULT — the API is REACHABLE but the SKILL'S OWN GATES ARE CLOSED (two runs, single-variable)
Called on each skill object (context = the skill). All thunks resolved, all calls FAULT-FREE, game survived:
```
TryShowPrompt -> 0    TryTestSkill -> 0    MarkTestCompleted -> 0
CanTestSkill = 0      ShouldTestSkill = 0  GetSkillState = 0     (all four skills, before AND after)
```
RUN A: clean session, Phase 1 (BeginInit), NO hero          -> all gates 0
RUN B: same session + GoToPhase->4 (SpawnSelect) + BP_HERO_Ronin_C spawned/possessed -> **all gates STILL 0**
⇒ **Neither a possessed hero nor the round phase is the gate.** `TryTestSkill` returns 0 because `CanTestSkill`
and `ShouldTestSkill` both refuse. HYPOTHESES RULED OUT so far: manager-level `SetActive`, the augment list,
hero presence, round phase.

★ KEY OBSERVATION for the next session: the only FOUR live skills are `SpikeEnemies`, `LevelAbility_Specific`,
`ESCMenu`, `Abyss` — these are CONTEXTUAL HINT prompts, NOT the tutorial's main lesson chain. The main chain's
trigger volume IS live (`BP_TrainingVolume_Move_V2`, class `BP_TrainingVolume_Basics_C`) but ZERO basics quest
objects are instantiated. That is consistent with the basics lessons being SPAWNED WHEN THE PLAYER ENTERS THE
VOLUME. So the most likely remaining lever is PHYSICAL: get the hero INTO that volume (read its world location,
teleport the hero there with K2_SetActorLocation — `tutorial_launch.cpp` already has that machinery in RM_WAKEMOVE).
Other untried leads: `IsDisabledForConfig` (native+0x548A4F0) may be returning true; `Comp_GameState_TrainingBase_C`
(3 live instances) may be the real orchestrator; disassemble `CanTestSkill` (native+0x5489F40) to read its gate.

### ITER4 — teleport into the volume: WORKS MECHANICALLY, still not the gate
`BP_TrainingVolume_Move_V2` is at **(283, 277, -250)**; the hero was at **(0,0,13240)** (drop-plane altitude — that
is why the camera sits so high). `K2_SetActorLocation(teleport)` moved it to (283,277,-100), verified by re-reading
RootComponent->RelativeLocation. 5s real-time settle = 6470 hook hits. Gates STILL `Can=0 Should=0 State=0`.
⇒ volume entry is NOT the trigger for these four (they are contextual hints, not the Move lesson).

### ★★★ ITER4 DISASSEMBLY — THE ACTUAL GATE IS FOUND
`CanTestSkill` (rva 0x5489F40) is a thin UFunction thunk (`mov rax,[rdx+0x20]` frame-advance, `call`, `mov [rbx],al`).
The REAL implementation is **base+0x58CE1B0**. Its gate chain (every failure jumps to 0x58CE2DA = return false):
```
call base+0x338C990  (rcx=skill)   -> if NULL: FAIL          ; context / world-or-owner lookup
call base+0x56BDF10  (rcx=result)  -> rdi; if NULL: FAIL     ; ★ resolves the LOCAL HERO / player
call base+0x58E3D10  (rcx=skill)   -> if al!=0: FAIL         ; the "disabled" check
call base+0x56BAA00  (rcx=rdi); cmp eax,0x1e ; if >=30 -> test byte[skill+0x393] -> if !=0 FAIL
byte[skill+0x390] / [skill+0x391] / [skill+0x393]            ; per-skill config selectors
(when [skill+0x390]!=0): call 0x338C990 -> 0x56F0290 -> rdi (NULL:FAIL);
                          0x54F8DC0 (al==0:FAIL); 0x55B13C0 (al==0:FAIL); byte[rdi+0x1BE8]!=0:FAIL
```
★ DIAGNOSIS: the 2nd call is a hard gate that must return a non-null LOCAL HERO before any lesson logic runs. Our
hero was made with `GameplayStatics::BeginDeferredActorSpawnFromClass` + a manual `Possess` — it exists and renders,
but was never registered through the game's OWN spawn path, so `PlayerState.HeroClass` / the controller's hero ref
do not point at it and the accessor returns null. That short-circuits EVERY skill's CanTestSkill to false, which is
exactly why all four report identical Can=0/Should=0/State=0 regardless of phase, possession, or volume position.
⇒ **NEXT LEVER (already built, never combined with this): use `RM_SPAWNPLAYER`** — the game's own
`LokiGameMode::SpawnPlayer(PlayerState, Transform&OUT, StartSpot, bEnsure)` (S74 wired it to read
PlayerState.HeroClass, thunk resolution in `ResolveSpawnPlayer`) — INSTEAD of RM_SPAWNPOSSESS/GameplayStatics, so the
hero is canonically registered; THEN re-run RM_TRAINING. Also worth confirming directly: disassemble base+0x56BDF10
to name the accessor, and check `IsDisabledForConfig` (base+0x548A4F0 thunk -> 0x58E3D10 impl).

### ITER5 — RM_SPAWNPLAYER (the game's OWN spawn) also REFUSES
FIRST, a real bug fixed in `ResolveSpawnPlayer`: it used `FindObjExact("BP_HERO_Ronin_C")`, but a SPAWNED hero
INSTANCE is also named `BP_HERO_Ronin_C`, so in any session with a hero it grabbed the ACTOR and wrote it into
`PlayerState.HeroClass` (a UClass* field). Now uses `FindClassExact` (what ResolveSpawnPossess already did).
Built `tutorial_launch_spawnplayer.dll` (`-DKRUNMODE=RM_SPAWNPLAYER`) and ran on a FRESH session (no pre-existing
hero, so nothing confounds the canonical spawn). Resolution PERFECT:
```
gm=…  pc=…  localPS=BP_LokiPlayerState_C (psOff@0x3C0)  startSpot=…  spawnThunk=…  possessThunk=…
offs PS@0x0 Xf@0x10 SS@0x70 Ensure@0x78 Ret@0x80 InPawn@0x0 | heroClass=<UCLASS> psHeroOff@0x620
set PlayerState.HeroClass@0x620: - -> BP_HERO_Ronin_C
calling SpawnPlayer...  ->  hero=0x0     <-- NULL
```
Retried after GoToPhase -> 4 (SpawnSelect): **still hero=0x0**, 0 live BP_HERO_ instances. Game survived both.
⇒ `LokiGameMode::SpawnPlayer` refuses regardless of round phase, even with PlayerState.HeroClass correctly set.
So the canonical-spawn route does not open the gate by itself either.

### ★★★ ITER6 — THE FULL `CanTestSkill` GATE CHAIN, DISASSEMBLED (rva 0x58CE1B0; 0x58CE2DA = return FALSE)
```
rbx = skill
call base+0x338C990 (rcx=skill)        -> rax ; NULL => FAIL          [world/outer getter]
call base+0x56BDF10 (rcx=rax)          -> rdi ; NULL => FAIL          [PlayerState accessor, below]
call base+0x58E3D10 (rcx=skill)        -> al  ; al!=0 => FAIL         [IsDisabledForConfig, below]
call base+0x56BAA00 (rcx=rdi)          -> eax ; if eax>=0x1E(30) AND byte[skill+0x393]!=0 => FAIL   [level gate]
cmp byte[skill+0x390],0 ; je -> 0x58CE25C  (else: 0x338C990 -> 0x56F0290 -> rdi; NULL=>FAIL;
                                            0x54F8DC0 al==0=>FAIL; 0x55B13C0 al==0=>FAIL; byte[rdi+0x1BE8]!=0=>FAIL)
cmp byte[skill+0x391],0 ; je -> 0x58CE2B7  (else: 0x338C990 -> 0x56F0290 -> rsi; NULL=>FAIL;
                                            rdi=[rsi+0x3D8]; if rdi: 0x54F8E40 al==0=>skip; 0x56BFA00 -> byte[rax+0x5D0]
                                            else 0x55B27F0(rsi); test al,al; jne => FAIL)
xorps xmm0,xmm0 ; comiss xmm0,[skill+0x3A8] ; jae => FAIL   ; float[skill+0x3A8] must be > 0.0
```
**base+0x56BDF10** (the "local player" accessor): `0x5693D20(rcx)` -> holder; `lea rbx,[holder+0x3C0]` (= PC->PlayerState);
null => FAIL; type-checks it against `LokiPlayerState::StaticClass()` (cached UClass* at base+0xA028B60, FName
confirmed = **LokiPlayerState**) via base+0x12C7DD0; returns the PlayerState.
**base+0x58E3D10** (`IsDisabledForConfig`): returns TRUE(disabled) ONLY when `byte[skill+0x3F0]==0` AND the inner
config call base+0x58414E0 returns 0. (`jne` on the byte => not disabled.)
**base+0x56BAA00** (the level getter): reads `dword[PlayerState+0xE88]`; when that field is **-1** it returns
**0x63 = 99** (a sentinel). 99 >= 30, so the level gate trips for any skill with `byte[skill+0x393]!=0`.

### VERIFIED LIVE (each of these gates PASSES — none of them is the blocker)
- PlayerState chain: `BP_LokiPlayerState_C -> LokiPlayerState -> PlayerState -> Info -> LokiActor -> Actor -> Object`
  ⇒ it DOES derive from LokiPlayerState, and `PC->PlayerState@0x3C0` is non-null ⇒ the type-check passes.
- `byte[skill+0x3F0]` was ALREADY **1** on all four skills ⇒ IsDisabledForConfig returns NOT-disabled.
- `float[skill+0x3A8]` was ALREADY positive (0.1 / 1.0 / 1.0 / 1.0) ⇒ the final comiss gate passes.
- Selector bytes: b390=0/1/0/1, b391=0/1/0/0, **b393=1 on ALL FOUR**.
- `dword[PlayerState+0xE88]` was **-1** (⇒ level getter returns 99). POKED to 1 and re-ran the probe:
  **gates STILL 0** (that session had no hero — SpawnPlayer had returned null — so the level poke is not yet a
  clean single-variable test; re-test it WITH a hero present).
- Skill Outer = `PersistentLevel` (class Level) ⇒ the world/outer lookup should resolve.

### ★★★★ ITER7 GATE TRACE — MEASURED. EVERY NATIVE GATE PASSES; THE REAL GATE IS **BLUEPRINT BYTECODE**.
Added a `GateTrace` step to RM_TRAINING that calls each gate DIRECTLY via raw function pointers (they are plain
native fns, not UFunctions), each SEH-guarded. Live measurement, all four skills, identical:
```
world=0x1C05E5E8B20  PS=0x1C1FAA86670(BP_LokiPlayerState_C)  disabled=0  level=0  PS+0xE88=1
f3A8=30.000  b390/b391 vary  b393=1  b3F0=1        ->  CanTest=0
```
⇒ gate1 (world) PASSES, gate2 (PlayerState accessor) PASSES, gate3 (IsDisabledForConfig) PASSES,
gate4 (level 0 < 30) PASSES — the PS+0xE88 poke DID work, the level getter went 99 -> 0 —
and the final `comiss` PASSES (30.0 > 0.0). **Yet CanTestSkill still returns 0.**

WHY: the chain does not END at the comiss. After it, CanTestSkill **TAIL-CALLS**:
```
+0x58CE2C3  mov rcx, rbx            ; skill
+0x58CE2D5  jmp base+0x5487B00      ; <-- the tail-call IS the return value
```
and `base+0x5487B00` is a **Blueprint-event dispatcher**:
```
rax=[rcx](vtable); rdx=[rip+0x4BA5669](cached UFunction*); byte[rsp+0x30]=0 (bool result, default FALSE)
rbx=[rax+0x270] (vtable slot = ProcessEvent); call base+0x1344150; r8=&result; rdx=func; rcx=skill
call rbx                      ; ProcessEvent(skill, BP_CanTestSkill, &result)
cmp byte[rsp+0x30],0 ; setne al ; ret
```
⇒ **`CanTestSkill` returns whatever the Blueprint event `BP_CanTestSkill` decides.** That matches the enumeration:
`BP_CanTestSkill` is Native,Event,BPEvent on LokiTrainingSkill, overridden with **1578 bytes of bytecode in
`BP_TrainingSkill_C`** (+80 more in BP_TrainingSkill_SpikeEnemies_C). NO amount of native field-poking can open this
gate — the decision is BP graph logic. This CLOSES the "which native flag is it" line of investigation for good.

### ★★★★★ ITER8 — `BP_CanTestSkill` DECOMPILED, AND **CanTestSkill RETURNED TRUE FOR THE FIRST TIME**
The extractor ALREADY has a full KismetExpression pretty-printer (`DumpExpr`, Program.cs ~1423) — it only runs when
you name a SPECIFIC function, not with `*`. So: `bpdump BP_TrainingSkill BP_CanTestSkill` ->
`out/bpdump_BP_CanTestSkill.txt` (784 lines, fully resolved names). The graph opens with:
```
[1] EX_JumpIfNot ( InstanceVariable: ShouldForceCanTestCheck )   ; if TRUE ->
[2]     ReturnValue = TRUE
[3]     Jump end
[4] CallFunc_GetLokiGameState_ReturnValue = GetLokiGameState(self)
[5] CallFunc_ActorIsOneOfSoft_ReturnValue = ActorIsOneOfSoft( GameState, ValidStates )   ; ★ THE REAL GATE
[6] EX_JumpIfNot( that ) -> 481                                   ; fail path
```
⇒ **The real gate is `ActorIsOneOfSoft(GetLokiGameState(), ValidStates)`** — the CURRENT GameState must be one of the
skill's `ValidStates` soft-class list — plus a developer override `ShouldForceCanTestCheck` that short-circuits TRUE.
LIVE OFFSETS (walked per skill class): **`ShouldForceCanTestCheck` @ +0x440 (bool)**, **`ValidStates` @ +0x428**.

★ RESULT OF SETTING IT: poked `ShouldForceCanTestCheck=1` on all four skills ->
`[GATE:pre] skill[0] ... CanTest=1` — **the first non-zero CanTestSkill in the entire investigation**. And then
`BP_TrainingSkill_SpikeEnemies_C` **DISAPPEARED from the object list** (consumed/destroyed) — the training system
ACTED on the opened gate. The flag is NOT reset by the game (verified stable =1 over 5s).
Also confirmed live: `gft_ready_fix.dll` works on the FORCE-OPEN route too (11 instances, GetFeatureTogglesReady
TRUE) — the toggle spam (`CursorCharacterAim ... not ready`) is present here as well; and the PS+0xE88 poke made the
game log `BP_LokiPlayerState reseting all trainings for **Very New Player**` (the level semantics are correct now).

WHY THE OTHER THREE STAY 0 (partially explained): `BP_TrainingSkill_ESCMenu_C` **OVERRIDES `BP_CanTestSkill`**
(confirmed by bpdump), so the base-class ShouldForceCanTestCheck shortcut never runs for it. But `Abyss` and
`LevelAbility_Specific` do NOT override it and still returned 0 — so the override story is incomplete. UNRESOLVED.

### ★★★★★ ITER9 — `ValidStates` READ. CONFIRMED: THE FOUR LIVE SKILLS ARE **PRACTICE-MODE HINTS**, NOT TUTORIAL.
`bpdump <skill> @props` reads ValidStates straight from the serialized defaults (no memory walking needed):
```
BP_TrainingSkill_Abyss        ValidStates = BP_LokiBattleRoyaleGameState_C, BP_LokiGameStateLastMan_C,
                                            BP_PracticeGameState_C, BP_LokiDevGameState_C
BP_TrainingSkill_SpikeEnemies ValidStates = BP_PracticeGameState_C
                              TrainingVolume = BP_TrainingVolumeSpiking_C   (.../Objectives/PRACTICE/Spike/...)
                              TestDurationSeconds = 1.4012E-41 (denormal ~ 0 => unset)
```
⇒ **NONE of them lists `BP_LokiGameState_Tutorial_C`.** They are Practice / BattleRoyale / LastMan / Dev hints and
they refuse inside the tutorial BY DESIGN. `ActorIsOneOfSoft(GameState, ValidStates)` correctly returns false.
⇒ Forcing `ShouldForceCanTestCheck` DID open the gate (SpikeEnemies returned CanTest=1 and was consumed) — but that
was forcing a PRACTICE hint to run in the tutorial. It is NOT progress toward the tutorial mission.

### ⚠⚠ CORRECTION TO AN EARLIER NOTE IN THIS DOC
An earlier iteration recorded "LVL_Tutorial drives its lessons via BP_TrainingManager + BP_TrainingSkill_*; the
TrainingQuest_Basics_* / sequencer assets belong to a different level — do not chase them." **THAT IS WRONG.**
The TrainingManager/TrainingSkill family is the **PRACTICE-mode** system (its skills live under
`Objectives/Practice/...` and their ValidStates exclude the tutorial); it is merely loaded in the process.
**The tutorial's real lesson chain IS the `TrainingQuest_Basics_*` + `BP_TutorialTrainingQuestSequencer` family**
(under `Objectives/Tutorial/Basics/`), triggered by `BP_TrainingVolume_Basics` — and `BP_TrainingVolume_Move_V2`
IS live in the world, which corroborates it.

### ITER10 — asset locations + the sequencer's own graph (both confirm the two-system split)
- The practice manager lives at `Loki/Content/Loki/Core/**TrainingSkills**/BP_TrainingManager.uasset` — a separate
  top-level folder from `Objectives/Tutorial`. Two distinct systems, confirmed by path as well as by ValidStates.
- `bpdump BP_TutorialTrainingQuestSequencer ReadyToFire` (28 entries) and
  `... ExecuteUbergraph_BP_TutorialTrainingQuestSequencer` (59 entries) both dumped to out/.
  The ubergraph casts collection items to **`Training_Quest_Basics_Base`** and reads their
  **`AssociatedTrainingVolume`**, alongside `BP_Loki_Team_State_Code` (TeamState), `SoloAugmentPlayerState`, `GetPawn`.
  ⇒ the SEQUENCER is what owns the TrainingQuest_Basics objects and binds each to its trigger volume. It is the
  single actor whose absence explains why 0 quests exist while the Move_V2 volume is live.

### ★★ ITER11 — RM_SPAWNSEQ: THE SEQUENCER **CAN** BE SPAWNED (new capability), BUT IT DOES NOT POPULATE THE CHAIN
New mode `RM_SPAWNSEQ` (`-DKRUNMODE=RM_SPAWNSEQ` -> `tutorial_launch_seq.dll`): spawns
`BP_TutorialTrainingQuestSequencer_C` via the S74-proven GameplayStatics deferred path
(BeginDeferredActorSpawnFromClass -> FinishSpawningActor), at the training volume's location, then censuses.
⚠ FIX APPLIED: set FTransform Scale3D (@0x38/0x40/0x48) to 1.0 — DoSpawnPossess leaves it 0 (zero-scale actors).
LIVE RESULT:
```
[SEQ] BEFORE: TrainingQuest=0  Sequencer=0
[SEQ] deferred=0x194653084D0 cls=BP_TutorialTrainingQuestSequencer_C
[SEQ] *** SPAWNED sequencer=0x194653084D0 ***                       <- spawn WORKS, game stays alive
[SEQ] AFTER: Sequencer=1   TrainingVolume=1 (BP_TrainingVolume_Basics_C)
precise census: Quest_Basics=0  TrainingQuest_Basics=0  Training_Quest=0  Quest_Advanced=0   <- NO quests
```
⚠ CENSUS TRAP: the substring "TrainingQuest" ALSO matches `BP_TutorialTrainingQuest**Sequencer**_C`, so a naive
count reads 1 and looks like success. Use `Quest_Basics` / `Training_Quest` to count REAL quest objects.
⇒ **Spawning the sequencer is NOT sufficient.** Its `BP_LokiBeginPlay`/`ReadyToFire` created nothing and produced no
LogLokiTraining activity. WHY (from the bytecode already dumped): `ReadyToFire` takes an **FClassProperty parameter**
— it is FED a quest class, it does not spawn one; and its ubergraph reads `TeamState` (BP_Loki_Team_State_Code),
`SoloAugmentPlayerState` and `GetPawn`, none of which exist in our session. It is a COORDINATOR, not a spawner.
⇒ NEXT: (a) call `ReadyToFire(<TrainingQuest_Basics_* class>)` explicitly on the spawned sequencer via the
native-call primitive (it is BPCallable; marshal the one class param — the RM_TRAINING probe already has param
dumping to get the offset); and/or (b) spawn the `TrainingQuest_Basics_*` actors DIRECTLY with the same
GameplayStatics path now proven to work, and let them bind to the live `BP_TrainingVolume_Move_V2`.
⚠ ALSO: the force-open crashed on 2 of 3 launches this round (dies ~1s after `Entering game state
BP_LokiGameState_Tutorial_C`) — the documented intermittent crash. Budget retries; a 90s pre-inject settle helped.

> ⚠ **RETRACTED 2026-07-27 (S106) — the paragraph above is preserved as written, but "intermittent"
> and "budget retries" are FALSE.** The crashes are **deterministic**. 86 crash minidumps exist (the
> project believed for ~60 sessions that none did — that was FK-8); 68% of chained crashes are exact
> repeats of another crash, and all 10 crashes in the FK-7 window sit in a 28-second band (173–201 s)
> across **two** stack families:
> - **Family A — worker thread:** use-after-free on a garbage-collected `UAnimationAsset` inside
>   `FAnimSync::TickAssetPlayerInstances`. Shim-caused (`LoadAsset_Blocking` results are invisible to
>   UE's GC; there is no `AddToRoot` in `tutorial_launch.cpp`).
> - **Family B — game thread:** `PlayerCameraManager->ViewTarget.Target` has its **low byte overwritten
>   with `0x01`**, then `APlayerCameraManager`'s per-frame tick dispatches through it. The view target
>   is positively identified as **the shim's own spawned camera actor**, via the shim-private constant
>   triple `KCAMPITCH -66.0 / -90.0 / 0.0` recovered from `ViewTarget.POV.Rotation` in crash memory.
>   It is **NOT** a use-after-free — the actor is alive and GC-reachable.
>
> Both have compiled fixes (`KVTGUARD`, `KGCROOT`), **neither yet live-verified**. **Also corrected:**
> the shared antecedent is the shim's **blocking mesh load**, not a GC (`LogGarbage` appears in **zero**
> log files); and the crash corpus explains **at most half** the failure rate — 5 of 9 tutorial sessions
> died with no dump at all. → **`docs/fk7-crash-settled.md`**

### ⇒ THE REAL REMAINING QUESTION
None of the tutorial lesson objects exist: 0 `TrainingQuest_*`, 0 `BP_TutorialTrainingQuestSequencer_C`.
The sequencer is a LEVEL-PLACED actor (it has DefaultSceneRoot + SimpleConstructionScript + SCS_Node), and the
Move_V2 volume that IS live carries a `_UAID_...` suffix (WorldPartition level-placed, streamed in). So some cells
stream and the sequencer's does not — or the sequencer lives in a sub-level/data-layer the force-open travel never
activates. NEXT: find why `BP_TutorialTrainingQuestSequencer_C` is never spawned (WorldPartition cell / data layer
/ level-instance streaming), or spawn it directly and let its `BP_LokiBeginPlay` -> `ReadyToFire` drive the chain.
That is the actual path to a playable tutorial mission; the skill-flag work is a closed dead end.

### (superseded) THE BIGGER REALIZATION — WE MAY BE POKING THE WRONG SKILLS ENTIRELY
The four live skills (SpikeEnemies, ESCMenu, Abyss, LevelAbility_Specific) are CONTEXTUAL HINTS. The real gate is
`ValidStates` — "is the current GameState one of the states this hint applies to". These four are almost certainly
hints for OTHER modes (BR/arena), which is why they legitimately refuse in `BP_LokiGameState_Tutorial_C`. The ACTUAL
tutorial lesson chain (the `Move_V2` volume's WASD/Jump/LMB progression) is simply **NOT INSTANTIATED** — 0
`TrainingQuest_*`, 0 sequencer objects, and only 4 hint skills exist.
⇒ NEXT (highest value, offline first): **read `ValidStates` (+0x428, a soft-class array) on each live skill** and
compare with `BP_LokiGameState_Tutorial_C` — that tells us definitively whether these four are even meant to run
here. Then find what SPAWNS the real lesson objects: `BP_TrainingManager_C` and the three
`Comp_GameState_TrainingBase_C` instances are the owners; bpdump them (`bpdump BP_TrainingManager *`,
`bpdump Comp_GameState_TrainingBase *`) and read what populates the skill list. Forcing per-skill flags is a
dead end if the lessons we want were never created.

RAN IT: `bpdump BP_TrainingSkill *` -> `out/bpdump_BP_TrainingSkill_ALL.txt`. `BP_CanTestSkill` = **67 bytecode
entries**, FUNC_Event|Protected|HasOutParms|HasDefaults|BlueprintCallable|BlueprintEvent, referencing several
FObjectProperty, an FSoftClassProperty, an FStructProperty, an FEnumProperty and many bools/ints.
⚠ LIMITATION FOUND: the extractor's bpdump lists the bytecode's REFERENCED PROPERTY TYPES, not the disassembled BP
opcodes — so it proves the graph is substantial but does NOT render the readable conditions. To actually read them:
(a) extend the extractor to disassemble BP bytecode (CUE4Parse can, ReadScriptData is already enabled), or
(b) EASIER — hook `ProcessEvent` (the shim already has the primitive) and trace the calls BP_CanTestSkill makes
    while it runs; the callee names ARE the conditions. `GetWASDInputs`(161 entries)/`IsActorOfClassNearby`(44)/
    `HasCompletedQuest`(6) on the same class are the kind of helpers it will be calling.

⇒ (original plan) dump the bytecode and read the conditions:
`dotnet run -c Release -- bpdump BP_TrainingSkill BP_CanTestSkill`  (and `... ExecuteUbergraph_BP_TrainingSkill`,
and the per-skill `BP_TrainingSkill_SpikeEnemies` override). The extractor already dumps BP bytecode
(`provider.ReadScriptData=true` for bpdump) and out/ already holds precedents like bpdump_AddNewObjective.txt.
Whatever conditions that graph tests (likely: a valid hero, an active quest/step, prior completion) are the REAL
prerequisites for a lesson to start — and they are readable statically, without another live session.

### (superseded) STOP GUESSING, MEASURE — `base+0x338C990`, `base+0x56BDF10`, `base+0x58E3D10`, `base+0x56BAA00` are PLAIN NATIVE
functions (not UFunctions), so the shim can call each one DIRECTLY through a raw function pointer with the skill /
its result in rcx and log every intermediate value. That pinpoints the failing gate in one run instead of poking
fields one at a time. Add this to RM_TRAINING as a "gate trace" step — it is a small, safe, read-only addition.

### WHERE TO GO NEXT (the disassembly technique is what has been working)
1. **Disassemble `SpawnPlayer`** (thunk `spawnThunk` -> its impl) to read WHY it returns null — same method that
   cracked CanTestSkill in one shot (tools/re/disasm_live.py <PID> <BASE> <RVA>; a UFunction thunk is a thin
   `mov rax,[rdx+0x20]` / `call <impl>` wrapper, so follow the inner call).
2. **Disassemble base+0x56BDF10** — the local-hero accessor that CanTestSkill hard-gates on. Naming exactly which
   field it reads may be BETTER than fixing the spawn: point that field at the hero we can already create with
   GameplayStatics (which renders and possesses fine), instead of making the game spawn one.
3. `IsDisabledForConfig` impl = base+0x58E3D10 (thunk base+0x548A4F0) — confirm it is not independently returning true.

OLD PLAN (superseded by the result above) — call ON EACH SKILL OBJECT (context = the skill, not the manager):
`GetSkillState` -> `CanTestSkill` / `ShouldTestSkill` -> `TryShowPrompt` -> **`TryTestSkill`** -> `GetSkillState` again;
then `MarkTestCompleted` to close the loop. This is the direct "start a lesson / complete an objective" path.
For the drop, separately: `SpawnPlane` needs real params to CREATE the missing plane before `GetAutoDropLocation` works.

Live lesson objects to pass to it (this session): `BP_TrainingSkill_SpikeEnemies_C` @0x1953F96B700,
`BP_TrainingSkill_LevelAbility_Specific_C` @0x194E5755770, `BP_TrainingSkill_ESCMenu_C` @0x1953F96CDD0,
`BP_TrainingSkill_Abyss_C` @0x19575F3D750. (Addresses are per-run; re-census each session.)

⇒ **NEXT ACTION: call `SetActive(<skill>, true)` (and/or `StartTimers()`) via the game-thread native-call primitive**
and watch for a lesson to begin (`LogLokiTraining`, the prompt UI, `Comp_PlayerController_BasicTrainingText`).
Nothing has ever called it — which is exactly why the system sits assembled and idle after its single `ResetAll`.

### Drop-in: what does NOT work (tested S90)
`ds_hybrid_dropin.dll` (MODE_DROPIN) fires cleanly on the force-open route — it resolves the real
`BP_LokiPlayerController_Dev_C`, and `UpdateIsInDropPod(false)` + `FinishDropPhaseHiding()` both return fault=0,
collapsing 5 MatchTransition widgets — **but the view does NOT change**: the camera stays at the SpawnSelect drop
altitude and the round stays at Phase 4. Those two natives govern pod/hiding state, NOT the descent/commit.
The commit path is the DROP-PLANE component, enumerated live (below).

## ★★★ THE DROP-IN API — `Comp_GameMode_DropPlane_Tutorial_C` (live-enumerated S90)

```
=== LokiGameModeDropPlaneComponent (native base) ===
AddPlayerToDropPlane      native+0x5350630  Parms 8    <- PUT THE PLAYER ON THE PLANE
SetDropPlane              native+0x5352F20  Parms 8
GeneratePlanePoints       native+0x5350BD0  Parms 64  HasOutParms
SpawnPlane                (Event/BPEvent, Parms 8)

=== Comp_GameMode_DropPlane_Tutorial_C (BP override) ===
SpawnPlane                    script 1551  Parms 8  Event,BPCallable,HasOutParms
GetAutoDropLocation           script 1085  Parms 32 HasOutParms   <- tutorial AUTO-picks the drop spot
PlaneDropLocationChanged      script  794  Parms 48
PlaneDropLocationChangedEvent script   54  Parms 48
On Round Phase Changed / OnRoundPhaseChanged   script 36  Parms 1
On Plane Reached End (18) / On Plane Destroyed (36)
OnGameEvent_OnBattleRoyalePlayerPhase_Player   script 72  Parms 40
```
⇒ Intended flow: `SpawnPlane()` -> `AddPlayerToDropPlane(<player>)` -> `GetAutoDropLocation()` -> descend ->
phase advances past SpawnSelect(4). Drive these with the game-thread native-call primitive (note the BP ones
dispatch through ProcessInternal, the native ones have direct thunks).

## Plan (ordered)

1. **Census a live force-open session** (read-only RPM, seconds): does `BP_TutorialTrainingQuestSequencer_C` /
   `TrainingQuest_Basics_*` / `BP_TrainingVolume_Basics` / `Comp_PlayerController_TutorialObjectives` actually
   instantiate? `python tools\re\obj_by_class.py <PID> <BASE> TrainingQuest` (also TutorialTrainingQuest,
   TrainingVolume, TutorialObjectives). ← THE decisive unknown; never attempted.
2. **Hero + movement with `gft_ready_fix` loaded** — the S75 blocker was the mantle subsystem querying UNREADY
   toggles; that fix now exists. This exact combination has never been run.
3. **Fire the first quest**: with a hero possessed, walk into `BP_TrainingVolume_Basics` / trigger
   `TrainingQuest_Basics_WASD`. Watch for `GameEvent_Tutorial_QuestComplete` and the sequencer advancing.
4. **Chain + completion**: verify `OnObjectiveComplete` (authority) fires and `ReadyToFire` arms the next quest.
5. **End of mission**: `Comp_GameMode_EoGFinisher` / ShouldGameEnd; capture whatever the client POSTs (ags catch-all).
6. **Exit to menu**: press the real in-match leave (CanDisassociate is served true); fall back to
   `CoreGameManager::TryStopMatch` / `TryDisassociateMatch` via the native-call primitive.
7. **Credit the menu missions**: add the real tutorial objective UniqueNames to `objectiveRules`
   (server/internal/interactive/missions.go L481-508) — currently only BR/Armory/Tournament stats are mapped, so
   `NewOnboarding_CompleteBasicTraining` / `CompleteAllTutorialMaps` would not advance even on a real completion.

## Config for the force-open route

`interactive.go`: `forceTutorialMatch = true` AND `ConnectionDetails.address = ""` (EMPTY — the client then parks
locally and builds a valid CoreGameMatchModel; "127.0.0.1:7777" is the DS route instead). Travel is ONE-SHOT at
match entry with whatever address is present THEN — hot-swapping later does not re-fire.
