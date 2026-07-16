# Session 79 — the client-side hero moonshot: plan + Phase-1 probe

Date: 2026-07-15. Goal (user-chosen): a **playable first tutorial mission** — the player's hero spawns and is
controllable, and the mission objectives trigger in order — via a **client-side reimplementation of match-entry**
inside the DS session. This is the "moonshot" the user picked over banking the S70/S78 spectator ceiling.

## FIRST: the S79 handoff's recommended Step 1 was already closed — do NOT rebuild it
`docs/next-session-prompt-s79.md` recommends "Step 1 — spawn a controllable hero via the game's own cheat
primitives (`ULokiPlayerCheats`)." That path is **already exhausted**, closed twice from the strongest position:
- **S74 (disasm):** the cheat function *bodies* are compiled out of shipping. `ServerCheatSpawnActor_Impl` = `ret`;
  `AreHotkeyCheatsEnabled_Impl` = `xor al,al; ret` (hardcoded false, no flag exists). Reflection metadata is kept
  (so calls resolve + never crash) but the bodies are empty — route/authority-independent. See
  `supervive-cheat-surface-inventory` "DEFINITIVE CLOSE".
- **S76 (the exact DS-session test the handoff proposes):** with a valid `LokiGameState` + a real Loki-typed local
  PC + fixed marshalling all at once, `GetLocalLokiPlayerCheatsBP` returned NULL (the cheat obj is a server-spawned
  replicated sub-object the stub never spawns), the drop-in fns resolved to 0x0 (the DS client's local PC is the
  *native* `LokiPlayerController`, not `BP_LokiPlayerController_Dev_C`), and `BP_HERO_Ronin_C` = 0x0 (not loaded).

The S78 vtable hook is a better *execution* primitive but doesn't change *what* a call does — it does not reopen the
cheat path. **The moonshot below routes AROUND the cheats entirely: manual asset-load + spawn + swap-in + possess.**

## What's de-risked / working (build on this)
- DS session → client in the **live LVL_Tutorial** with a valid replicated `ALokiGameState` (S70) + real Loki-typed
  local PC (S73) + smooth mouse-steered spectator fly-cam (S78, committed).
- **Native-call primitive** (S55–74): hook `ProcessInternal` (`base+0x13454A0`), capture a live FFrame, call a
  UFunction thunk (`+0xE0`) directly; params + OUT/ref-params (`BuildOutParms` → `FFrame.OutParms@+0x80`) + struct
  params solved. In `ds_hybrid.cpp` (`CallNative`).
- **Client-side actor SPAWN works** (S78: `GameplayStatics::BeginDeferredActorSpawnFromClass` + `FinishSpawningActor`
  spawned an `ACameraActor` clean — the S72 crash was the struct-param ABI, fixed by `BuildOutParms`).
- **Anti-tamper understood + dodged**: `preloader.dll` + the packed-exe `.text` integrity check. NEVER hold a
  standing `.text` hook (caught reliably, S77) — use the transient-per-fire or the S78 heap vtable hook.

## The known walls this moonshot must beat (each is real; ordered)
1. **Assets not loaded** — heroes + `BP_LokiPlayerController_Dev_C` are 0x0 in a spectator's memory (S76). But the
   CLIENT has them cooked into its own paks (unlike the stub). → **Phase 1: prove they load in-process.**
2. **Local PC is the wrong class** — the DS client's networked PC is the *native* `LokiPlayerController` (stub
   by-path mirror), NOT `BP_LokiPlayerController_Dev_C`, which carries the drop-in machinery
   (`DropPlaneComponentSetup`, `UpdateIsInDropPod`, `FinishDropPhaseHiding@PC+0xF28`) and the
   `GameEventRouterComponent` that clears the loading overlay (S77). → **Phase 2/3: spawn a local BP_Dev PC and make
   it the active controller, against a fighting networked session.**
3. **The game fights client-side overrides** — S78: a spawned camera as view-target gets reverted to the DefaultPawn
   every frame; the game will not relinquish its spectator camera. Concrete evidence the swap-in (Phase 3) is the
   deep-uncertainty step.
4. **Possess exec-wrapper no-ops for native** (S54/S72): `ClientRestart`/`Possess` via the thunk route through
   ProcessEvent; need the C++ `_Implementation` (call it directly, or drive the possession via the BP_Dev PC path).
5. **Drop-in + objective state machine** — normally gamemode-driven (`Comp_GameMode_DropPlane_Tutorial`), which the
   real `BP_LokiGameMode_Tutorial` (server-native, not possessed) runs. S74 found the drop-in *completion* is a local
   PC flag (`FinishDropPhaseHiding` sets `PC+0xF28=1`, no server check) — but only on the BP_Dev PC (Phase 2 gate).

## Phased plan (each phase is kill-criteria-gated — bank if a gate fails)

### Phase 1 — asset load census  ← ★ RAN LIVE S79, GATE **PASSED** (client PID 48788, ~65min DS session)
**Live result (2026-07-15, 2 clean injections, no crash):** the key moonshot assets are ALREADY RESIDENT in the DS
spectator client (overturns S76's "heroes not cooked into a spectator's memory" — the 60min session loaded them):
- `heroPawnClass = BP_HERO_Assault_C` (0x28694503340) — a real spawnable hero pawn class, LOADED.
- `BP_LokiPlayerController_Dev_C` (0x28694506670) — the BP_Dev PC class (drop-in machinery, wall #2), LOADED — but
  **0 live instances** (`BP_Dev PC live instance=0x0`).
- Hero `PrimaryAssetType` = **"Hero"** (tid=0x1A568, 25 assets); `AsyncLoadPrimaryAssets` fired clean (valid handle).
  (Candidates `LokiHeroData`/`LokiHero`/`HeroData` returned 0 ids — the type string is bare **"Hero"**.)
- ★ Local PC = **`LokiPlayerController` (native, 0x285752F50B0) possessing a `DefaultPawn`** (0x285F06D0080) at
  `AController::Pawn @ PC+0x3F8` — the spectator pawn, NOT a hero. No live `LokiHeroCharacter` (inst=0x0).
- The `LokiCharacter*` census hits were POOLED components/HUD widgets (CharMoveComp, CollisionProfileManager,
  SpringArm, FastTarget, WBP_UI_Character_Resource_*) — the S70 primed gameplay pools; my `SuperChainHas("LokiCharacter")`
  filter was too broad (substring) and capped at 24 on components before reaching any actor. Next probe: filter to
  ACTOR instances with exact class == LokiCharacter / LokiHeroCharacter / BP_HERO_*_C to confirm no live hero actor.
⇒ **Phase 2 is SPAWN, not "possess existing"**: there's no ready hero to possess; the local PC drives a DefaultPawn.
The BP_HERO_Assault_C + BP_LokiPlayerController_Dev_C classes are resident (live ptrs above) → spawnable now.
Reusable: `ds_hybrid.cpp` MODE_LOAD_CENSUS (+`LcCensusDeep`); `ds_hybrid_loadcensus.dll`; hero type "Hero"; PC Pawn@+0x3F8.

#### (original Phase-1 design)
Force-load hero primary assets in-process and re-census. Reuses the PROVEN missions load primitive
(`PrimaryAssetIDFromString` → `GetPrimaryAssetIdList` → `AsyncLoadPrimaryAssets` on the `LokiAssetManager`). The hero
`PrimaryAssetType` is **discovered** (a candidate list; keep whichever returns ids — no blind single-string guess).
- **GO** = after the load + 8s settle, `heroPawnClass` / `BP_HERO_*_C` become non-0x0 (and ideally
  `LokiHeroCharacter`/`LokiCharacter` instances appear). → proceed to Phase 2.
- **NO-GO (bank)** = no candidate type returns ids (extend `kCand` once from the log, then), OR the load fires but no
  hero class ever resolves → the client-side spawn path is dead; bank the S70/S78 spectator ceiling.
- Open uncertainties to read off the marker: (a) does the primary asset load the DA/definition only, or the pawn BP
  class too (may need a bundle spec or a follow-on class load); (b) is `BP_LokiPlayerController_Dev_C` a primary
  asset (the probe also reports whether it's present) — its load mechanism (likely a class/object path load, not a
  primary asset) is scoped in Phase 2.

### Phase 2 — spawn a local BP_Dev PC + a hero, wire them (no swap yet)
Once assets load: spawn a local `BP_LokiPlayerController_Dev_C` + a `BP_HERO_*_C` via the working deferred-spawn path
(`BuildOutParms` fixed the struct-param crash). Confirm the BP_Dev PC exposes the drop-in fns (S74: they exist on
BP_Dev, absent on native). Confirm `TryGetLocalLokiController` still resolves. **Gate:** if the BP_Dev PC can't be
spawned/constructed client-side (BP/GAS/component construction crash, à la the S72 hero-spawn), bank.

#### ★ BUILT (ready to fire — NOT yet run live) — `ds_hybrid.cpp` MODE_SPAWN_P2
New mode `MODE_SPAWN_P2` (`enum Mode`, value 7) — deliverable DLL `tools/sigbypass-mod/ds_hybrid_spawnp2.dll`. It:
- Resolves `BP_LokiPlayerController_Dev_C` + `BP_HERO_Assault_C` **by name** each launch (VAs are ASLR'd — never
  hardcode the Phase-1 pointers), the GameplayStatics `BeginDeferredActorSpawnFromClass`/`FinishSpawningActor` thunks,
  and a valid in-world spawn point read from the DefaultPawn (`K2_GetActorLocation`, falls back to `(0,0,1000)`).
- Fires on the game thread via the **S77 transient-per-fire hook** (no standing `.text` hook → dodges the anti-tamper,
  same dodge the Phase-1 load-census used cleanly).
- Spawns the **BP_Dev PC first** (the wall-#2 class = the crash gate; the marker is flushed per line, so an uncatchable
  hero-spawn crash still leaves the PC result on disk). If it survives, resolves the drop-in fns on the spawned PC's
  class (`DropPlaneComponentSetup` / `UpdateIsInDropPod` / `FinishDropPhaseHiding` / `TryGetLocalLokiController` /
  `ClientRestart` / `Possess`). Then spawns the hero and reports `GetAbilitySystemComponent`. **No swap/possess** (Phase 3/4).
- Every spawn call is `CallGuarded` (catches catchable faults + logs) and the VEH logs an uncatchable `__fastfail` RIP.

Build: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_SPAWN_P2 ds_hybrid.cpp -o ds_hybrid_spawnp2.dll -lkernel32 -luser32`
(default `ds_hybrid.dll` = MODE_SPECTATOR_CAM, unchanged). Inject (needs the user's elevated PS + the game live):
`tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\ds_hybrid_spawnp2.dll`. Read `docs/ds-hybrid-marker.txt`:
- `[P2] <<< BP_Dev PC SPAWNED … construction SURVIVED!` + the `[FN]` drop-in-fn lines resolving = **GATE PASSED** →
  proceed to Phase 3 (swap-in).
- `[P2] BP_Dev PC spawn FAILED` / `[VEH] fatal …` / the client dies = **GATE FAILED** (BP/GAS construction wall) → bank.

**Firing is a WRITE with crash risk to the live session — checkpoint with the user first (they drive the inject).**

#### ★ RAN LIVE (2026-07-16) — Phase-2 GATE **PASSED** (client PID 48788, still up; no crash)
Injected `ds_hybrid_spawnp2.dll` via `inject.exe mmap 48788` (clean manual-map, DllMain OK). Marker result:
- `BP_LokiPlayerController_Dev_C` **SPAWNED** (obj `0x2868B5ED8A0`) — construction SURVIVED. Drop-in fns resolve on
  the spawned instance's class: `DropPlaneComponentSetup` (thunk `0x7FF6B44245C0`, childProps=0), `UpdateIsInDropPod`
  (`0x7FF6B4428890`, has params), `FinishDropPhaseHiding` (`0x7FF6B4424710`, childProps=0 — the S74 `PC+0xF28` setter),
  `ClientRestart` (`0x7FF6B2C5F990`), `Possess` (`0x7FF6B2702740`).
- `BP_HERO_Assault_C` **SPAWNED** (obj `0x2861791AAC0`) — hero BP/GAS/component construction SURVIVED (overturns the
  S72 fear that hero construction was the crash — `BuildOutParms` fixed the ABI, confirmed on a real hero now).
- Spawn point read from the DefaultPawn: `(-3510,-3380,1256)`. Hook never held standing (anti-tamper dodged). No `[VEH]`.
- Non-load-bearing NOT-FOUNDs: `TryGetLocalLokiController` (static helper, not a PC method — S73 already proved it
  succeeds at the engine level), `GetAbilitySystemComponent`/`BeginPlay` (ASC is a component; C++ BeginPlay isn't a UFunction).
⇒ **Wall #1 (assets) AND the BP/GAS construction crash-risk are both DOWN.** Phase 3 (swap-in) is the remaining wall.

Per-launch VAs captured this run (re-resolve by NAME next launch — base ASLR'd): devPcCls `0x28694506670`,
heroCls `0x28694503340`, world(ProgressionManager) `0x28501C27A20`, gsCDO `0x285050BA140`, native local PC
`0x285752F50B0`→ (re-resolve), DefaultPawn `0x285F06D0080`.

### Phase 3 — swap the local BP_Dev PC in as the active controller  ← the deep-uncertainty step
Make the spawned BP_Dev PC the client's active/local controller (displacing the server's authoritative native PC for
LOCAL purposes: input, camera, HUD), register its `GameEventRouterComponent`, re-fire
`GameEvent_SpectatorStateChanged` (S77's identified overlay-dismiss trigger). **Gate:** if the networked session
reverts the swap every frame (like the S78 camera view-target revert), the game won't relinquish control → bank.

#### ★ Phase 3a swap-surface census — DONE (2026-07-16, `ds_hybrid_swapcensus.dll`, read-only, no crash)
The two engine offsets the swap needs (neither a reflected UPROPERTY — found by pointer-equality scan against the live
LocalPlayer + native PC):
- `LocalPlayer` = stock `LocalPlayer` (this run `0x28541940E00`); local PC = native `LokiPlayerController`
  (`0x285752F50B0`); `GameInstance` = `BP_LokiGameInstance_C` (`0x285410D6340`). (VAs per-launch — re-resolve by name.)
- **`ULocalPlayer->PlayerController` @ +0x38** (single hit — matches stock `UPlayer::PlayerController`).
- **`APlayerController->Player` @ +0x458** (single hit).
- GameInstance holds no direct pointer to either in `[0,0x600)` (its LocalPlayers TArray data is heap-elsewhere; not
  needed for the swap).
⇒ The swap WRITE is `*(uintptr_t*)(L+0x38) = spawnedDevPC` + `*(uintptr_t*)(spawnedDevPC+0x458) = L` (and null the old
PC's `+0x458` so the engine doesn't think the native PC still owns the local player). RISK: a freshly-spawned BP_Dev PC
is not wired as a local PC (no viewport/HUD/camera-manager/input/NetConnection), so the game thread's next
`LocalPlayer->PlayerController->…` deref may crash — the swap likely needs the PC's local-player init run first, or a
careful minimal init. This is the deep-uncertainty, likely-to-crash step.

#### ★★★ Phase 3 minimal swap — RAN LIVE (2026-07-16, `ds_hybrid_swap.dll`): THE SWAP HELD, NO CRASH, NO REVERT
Spawned a fresh `BP_LokiPlayerController_Dev_C` (`0x28690832770`) at the DefaultPawn's loc `(-3510,-3380,1256)`, then on
the game thread set `L+0x38 = devPC` (was the native PC `0x285752F50B0`), `devPC+0x458 = L`, `oldPC+0x458 = 0`. Monitored
`L->PlayerController` for 10s: **stayed == our devPC for all 20 ticks — "STILL OURS (swap holding)"**, client alive, no
`[VEH]`. This OVERTURNS the record's prediction that the fighting networked session would revert the swap every frame
(the S78 camera-revert was a per-frame view-target re-assert; the controller pointer is NOT re-asserted the same way).
**CAVEATS (be honest):** pointer-held ≠ control works. The 10s window only proves the swap wasn't rejected + didn't
immediately crash. UNKNOWN yet: (a) whether anything VISIBLE changed (camera/input/HUD — the BP_Dev PC is not wired as a
local player: no viewport/camera-mgr/HUD/input component), (b) longer-term stability (a later path may deref the
under-wired PC), (c) whether this translates to actual control (that's Phase 4: possess a spawned hero + drive drop-in).
⇒ Phase-3 gate PASSED for the controller pointer; NEXT = Phase 4 (possess + drop-in) to see if it becomes controllable.
Per-launch: devPC `0x28690832770`, L `0x28541940E00`, oldPC `0x285752F50B0`, lpcOff 0x38, pcPlayerOff 0x458.

### Phase 4 — possess + drive drop-in
Possess the hero via the C++ `_Implementation` (not the exec thunk), then drive the local drop-in flags
(`FinishDropPhaseHiding` → `PC+0xF28=1`, `UpdateIsInDropPod(false)`, `DropPlaneComponentSetup`) to flip
spectator→control. **Gate:** movement/control round-trips (the Loki-PC net-cache reconstruction — add
LokiPlayerController's 60 own net UFUNCTIONs + 1 rep prop as same-named stubs so ServerMove aligns — is the S73 scoped
fix if control is one-directional).

#### ★★★ Phase 4 — RAN LIVE (2026-07-16, `ds_hybrid_possess.dll`): HERO POSSESSED on the swapped-in PC, held 10s, no crash
On the persisted swapped-in `BP_LokiPlayerController_Dev_C` (`0x28690832770`, still L->PlayerController): spawned a
`BP_HERO_Assault_C` (`0x28577E6D560`) at `(-3510,-3380,1256)`, called `Possess(PC, hero)` (exec thunk `0x7FF6B2702740`
— locally-spawned actors have local authority, so OnPossess runs), then drove `FinishDropPhaseHiding` (`0x7FF6B4424710`),
`UpdateIsInDropPod(false)` (`0x7FF6B4428890`), `DropPlaneComponentSetup` (`0x7FF6B44245C0`). **`PC->Pawn`@+0x3F8 went
`0x0` → the hero, and stayed == the hero for all 20 monitor ticks (10s), client alive, no `[VEH]`.** So the whole moonshot
chain (assets → spawn → controller-swap → hero-possess + drop-in) passed MECHANICALLY end to end.
**STILL UNCONFIRMED (the real gate): VISIBLE, CONTROLLABLE hero.** `PC->Pawn == hero` + no crash ≠ playable. Unknown:
does the camera follow the hero, does the HUD show, does WASD/mouse actually move it (SUPERVIVE's input/ability pipeline
may need the input component bound / enabled, a camera-manager view-target set to the hero, and the deploy state the real
gamemode drives). The next probe depends on what the user sees on screen + whether the hero moves.

#### Phase 4b/4c — RAN LIVE (2026-07-16): hero is on the ground but the RENDER/INPUT pipeline didn't follow the swap
- **4b (`ds_hybrid_deploy.dll`):** the possessed hero (`0x28577E6D560`) is at `(-3588,-3380,2)` — it fell to the
  ground (Z=2). The camera manager is at `(-3510,-3380,1256)` — still the spectator/DefaultPawn height, ~1254 above the
  hero. `SetActorHiddenInGame(false)` + `EnableInput(PC)` fired clean. ★ Recon surfaced the real SUPERVIVE mesh gate:
  `LokiHeroCharacter::SetPredropHidden` (`0x7FF6B439E670`) + `OnRep_HeroPredropHidden`/`CheckHeroHidden`/
  `AuthSetMeshVisibility` — the hero mesh is **pre-drop-hidden** (the game thinks it's still in the drop phase).
- **4c (`ds_hybrid_unhide.dll`):** `SetPredropHidden(false)` + `SetViewTargetWithBlend(hero)` both fired clean, client
  alive. ★ BUT the rendered camera manager (`0x2868A8B5580`) stayed targeting the **DefaultPawn** for the full 8s
  monitor — `SetViewTargetWithBlend(hero)` on our swapped-in PC did NOT redirect the rendered view. So the viewport is
  still rendering via the **native PC's camera** (the DefaultPawn spectator view), NOT our swapped-in BP_Dev PC.
⇒ **THE WALL (reframed):** the `L->PlayerController` pointer swap (Phase 3) + possession (Phase 4) wired the OBJECT
graph, but the engine's **local-player render/input pipeline did not follow the pointer** — the viewport still renders
the native PC's camera (locked on the DefaultPawn, the S78 "won't relinquish the spectator camera" behavior) and WASD
still routes to the native PC (mouse-look works, movement doesn't reach the hero). Our BP_Dev PC likely has no
`PlayerCameraManager` (freshly GameplayStatics-spawned, never ran normal PC init), so the swap redirected the pointer
but not the rendering. The hero mesh is now un-hidden + on the ground, but the camera won't look at it.
CANDIDATE NEXT LEVERS (untried, each uncertain): (a) set the view target on the NATIVE PC / the rendering camera manager
directly (not our BP_Dev PC) — but S78 found that camera reverts every frame; (b) spawn/attach a PlayerCameraManager on
our BP_Dev PC + force the local player's viewport to use our PC's camera; (c) run the BP_Dev PC's local-player init
(SpawnPlayerCameraManager / InitInputSystem) so the swap carries the render+input state; (d) drive movement via the
native PC (which the pipeline still follows) onto a possessed hero instead of swapping controllers. This is the deep
render/input-pipeline reconstruction the record predicted as the wall.

#### ★★★ Phase 4d — RAN LIVE (2026-07-16, `ds_hybrid_npossess.dll`): the RENDERING camera is now on the hero, held 12s
Reframe worked. Restored `L->PlayerController` = native PC (`0x285752F50B0`), then handed it the hero (`0x28577E6D560`):
`Possess()` **no-op'd** (confirming the networked proxy PC is authority-gated — `PC->Pawn` unchanged after the call), so
the fallback **raw-wired** `nativePC->Pawn@+0x3F8 = hero` + `hero->Controller@+0x400 = nativePC` + cleared the BP_Dev
PC's pawn. Then `SetPredropHidden(false)` + `SetViewTargetWithBlend(nativePC, hero)`. ★ RESULT: the RENDERING camera
manager (`0x2868A8B5580` — the native PC's, the one that actually renders) view target `@+0x420` became the **HERO and
held for all 24 monitor ticks (12s), NO revert to the DefaultPawn** (unlike Phase 4c, because now `nativePC->Pawn` IS
the hero, so the camera's auto-managed target follows it). Client alive, no crash. So the S78 camera-revert wall is
beaten by owning the pawn on the PC the pipeline follows. Offsets this build: `PC->Pawn @+0x3F8`, `Pawn->Controller
@+0x400`, `camMgr view target @+0x420`. REMAINING: whether the hero is now VISIBLE on screen (mesh un-hidden + camera on
it) and CONTROLLABLE (WASD → movement; the native PC drives input, PC->Pawn is the hero, but SUPERVIVE movement is
Enhanced-Input/ability-driven — may need more binding). Awaiting the user's screen check.

**4d SCREEN CHECK (user, 2026-07-16):** the camera moved DOWN to the hero's ground location — grass fills the frame, the
void shows through the island gap, and dark angular mesh shapes lower-left = the hero's model with the camera clipping
into it at its root. So camera-follows-hero is CONFIRMED visually. MISSING: the SUPERVIVE top-down camera RIG (a
spring-arm pull-up/back so the hunter is framed), HUD, and confirmed WASD control. ⇒ next lever = the hero's camera
component / spring-arm (pull the view up+back), then input binding, then HUD — open-ended deploy-rig reconstruction.

#### Phase 4e/4f/4g — RAN LIVE (2026-07-16): camera/input/HUD are deploy-gated custom systems; ran the bypassed setup
- **4e (`ds_hybrid_camfix.dll`, component census):** the hero has NO USpringArmComponent (my TargetArmLength write was a
  no-op) but DOES have a `CameraComponent` (`0x28679DE4B60`), an `EnhancedInputComponent` (`PawnInputComponent0`), HUD
  widget components (`HealthBarWidget`, Emote), 4× `SceneCaptureComponent2D`, an `OverrideSpringArmCurve` TimelineComponent,
  MapView/MapIcon, and ~48 components total. ⇒ camera is driven by the custom `LokiPlayerCameraManager` + timelines (not a
  spring-arm); input is Enhanced-Input (needs the mapping context applied); HUD is widget components — all **deploy-gated**.
- **4f (`ds_hybrid_deployrecon.dll`):** the client-side setup we BYPASSED (by raw-wiring PC->Pawn) = native PC's
  `OnRep_Pawn` (`0x7FF6B2702560`, the C++ pawn-change handler → camera+input for a new pawn), `ClientRestart`
  (`0x7FF6B2C5F990`), `ClientSetHUD` (`0x7FF6B2C60080`), + drop-in fns. On the hero: `OnLanded`/`ReceiveRestarted` (BP-folded).
- **4g (`ds_hybrid_crestart.dll`):** called `OnRep_Pawn` + `ClientRestart(hero)` on the native PC — both fired CLEAN (no
  fault), pawn + camera target held on the hero for 10s, client alive. Visible effect = user screen check (pending): did the
  hero frame properly / did WASD start working?

#### ★ Phase 4h — camera-rig control WORKS; hero MESH is the final deploy-gated wall (S79 ceiling)
- **`ds_hybrid_camframe.dll` (MODE_CAMFRAME):** drove the hero's `CameraComponent` (`0x28679DE4B60`) via
  `K2_SetWorldLocationAndRotation` (relative-space was ambiguous — the hero's local frame is flipped, gave an
  upside-down/under-island view; WORLD-space is unambiguous), re-applied ~40×/run to hold vs per-frame reset. The camera
  manager DOES render from the hero's CameraComponent, so this WORKS: got a clean top-down of the live tutorial world at
  the authentic SUPERVIVE range (camera at hero_world + (0,0,~3500), pitch −89). Camera-rig control = solved + drivable.
- **★ BUT the hero has NO VISIBLE MESH.** The camera follows the hero's real location (it's a functional actor — location,
  possession, camera-tracking all hold) but the hero renders as an INVISIBLE point. `SetActorHiddenInGame(false)` +
  `SetPredropHidden(false)` don't make it appear because the hero's mesh visibility is enforced EVERY FRAME by the deploy
  state machine (`LokiMeshManagerComponent` + `AuthSetMeshVisibility` [BP-folded, not directly callable] +
  `UpdateComponentVisibilityForLivingState`). The (physics-enabled) hero also drifted off the island edge over the void.

### ★★★ S79 FINAL STATE (2026-07-16) — LANDMARK reached; the wall is the deploy state machine
**Achieved live, far past the documented ~40-session ceiling** — the full client-side match-entry chain works at the
object level: force-load hero assets → spawn `BP_LokiPlayerController_Dev_C` + `BP_HERO_Assault_C` (BP/GAS construction
does NOT crash — the S72 fear is dead) → swap `LocalPlayer->PlayerController` → hand the hero to the NATIVE PC (the one
the render/input pipeline follows) → the rendering camera follows the possessed hero (beat the S78 camera-revert wall) →
drive a top-down camera rig at the authentic range. All stable, no crash, ~13 clean injections into one live session.
**The remaining wall (precisely mapped):** a VISIBLE + CONTROLLABLE hero needs SUPERVIVE's **deploy sequence**, which
gates (all confirmed live) — (1) MESH rendering (`LokiMeshManagerComponent`/`AuthSetMeshVisibility`, per-frame enforced);
(2) MOVEMENT (Enhanced-Input `PawnInputComponent0` — mouse-look reaches the camera but WASD doesn't reach movement, the
mapping context isn't applied); (3) HUD (widget components not created). These are deploy-state/gamemode-driven custom
systems; reconstructing the deploy sequence is a genuine multi-session effort, not one more shim call. Key live offsets
(per-launch, re-resolve by name): `LocalPlayer->PlayerController @+0x38`, `PC->Pawn @+0x3F8`, `Pawn->Controller @+0x400`,
`camMgr view target @+0x420`; the hero's `CameraComponent` drives the render (world-space transform).
NEXT (if resumed): RE + drive the deploy sequence — the mesh-visibility enforcer + the Enhanced-Input mapping-context add
+ the HUD-create — likely a single "deploy/landed" entry point on `LokiHeroCharacter`/the gamemode that fires all three.

### ★ DEPLOY-SEQUENCE RECONSTRUCTION — started (2026-07-16, post-S79). New ds_hybrid modes: STATERECON/LIVINGSTATE/MESHDIAG
The deploy control surface is now fully mapped (live, read-only `MODE_STATERECON`) and the mesh gate is precisely
diagnosed. Findings:
- **LivingState IS the visibility gate + it's drivable.** `LokiCharacter::LivingState @+0x1090` (uint8 enum); a raw
  hand-spawned hero has `LivingState = 0` (None/undeployed) → that's why the mesh is hidden. `MODE_LIVINGSTATE` set it to
  `1` (Alive) and it HELD (8s), firing `OnRep_LivingState`+`OnCharacterVisibilityUpdated` (native; `OnNewLivingState`
  faulted — likely wants the prev-state param). Enum: {0=None, 1=Alive, …; `LivingStateAlive/Dead/Knocked` effects
  confirm Alive/Knocked/Dead}. Native handles: `GetLivingState`(0x…300620), `OnRep_LivingState`(0x…302780),
  `OnNewLivingState`(0x…3025A0), `OnCharacterVisibilityUpdated`(0x…39E070). Other fields: `HeroPredropHidden @+0x1BE8`,
  `bIsOnGround @+0x1B20`/`bIsMidAir @+0x1B21`, `VisibilityState @+0xD38`, `LivingStateMachine @+0xD40`.
- **★ BUT LivingState=Alive did NOT reveal a mesh — because the character mesh DOESN'T EXIST yet** (`MODE_MESHDIAG`): the
  only mesh component under the hero is a `WispDirectionalIndicator` StaticMesh (UI plane). There is NO character
  SkeletalMeshComponent — it's created/attached by `LokiMeshManagerComponent` (`0x286A3034000` this launch) during the
  **cosmetics/deploy setup**, which never ran on a raw GameplayStatics-spawned hero. So the mesh gate is "not created,"
  not "hidden."
⇒ REMAINING deploy steps (each a BP-driven setup that needs a ProcessEvent capability + proper context, crash-prone
out-of-context): (1) MESH — run the cosmetics/mesh-manager setup (`BP_PostSetupCosmetics` / `ClientInitialComponentSetup`
[BP] or a native `LokiMeshManagerComponent` setup fn — recon that next) so `LokiMeshManagerComponent` builds the
character mesh; (2) INPUT — `TryLocalControlSetup` [BP] (Enhanced-Input mapping context); (3) HUD — widget creation.
NEXT: add ProcessEvent (`base+0x12C5A10`, S54-validated) to call the BP deploy fns, OR recon `LokiMeshManagerComponent`
for a native mesh-create. This is a multi-session effort; the control-surface map above is the hard part banked.

**★ MESH ROOT CAUSE FOUND (2026-07-16, `MODE_MESHMGRRECON` + `MODE_COSMETICS`).** `LokiMeshManagerComponent` only handles
the WISP mesh (StartAttachingWispMeshToActor…), NOT the character body. The native character-mesh builder is
**`LokiHeroCharacter::RefreshCosmetics`** (`0x…39E420`, directly callable) — but calling it built NOTHING because ★★
**the hero's `CosmeticsAssetID` is `0x0` (unset)**: a raw GameplayStatics-spawned hero has no cosmetics/character asset
(normally set from the player's loadout/PlayerState at deploy). `RefreshCosmetics` with a null asset → no skeletal mesh
(skeletal-mesh count 0 → 0, no crash). So the MESH dependency chain is: **character mesh ← `RefreshCosmetics` ← a valid
`CosmeticsAssetID` (null now) ← loadout / PlayerState**. Native cosmetics handles: `RefreshCosmetics`(0x…39E420),
`GetCosmeticsAssetID`(0x…39C770), `OnRep_CosmeticsAssetID`(0x…39E220), `GetCosmeticsController`(0x…39C7A0),
`GetOverrideCosmeticsAssetID`(0x…39D460). NEXT: find a valid Assault character `CosmeticsAssetID` (enumerate the cosmetics
PrimaryAssetType via the S79-Phase-1 `GetPrimaryAssetIdList` primitive, or read one off a real loadout/PlayerState), write
it to the hero's CosmeticsAssetID field + call `RefreshCosmetics` → the character mesh should build. THEN input
(`TryLocalControlSetup`, BP) + HUD. New reusable `ds_hybrid.cpp` modes: STATERECON, LIVINGSTATE, MESHDIAG, MESHMGRRECON,
COSMETICS (all `-DKMODE=`).

### Phase 5 — the mission objective trigger chain
Only reachable with a controllable hero in the simulated world. RE how the FIRST tutorial mission drives its
objectives (state machine + trigger order). Determine whether objectives are (a) gameplay-event-driven (fire from
player actions once the hero + world sim run), (b) drivable via the progression surface, or (c) hard-gated on the
missing server gamemode. NB the mission-PAGE replication (S54, FMissionProgress) is SEPARATE from in-match objectives.

## Live-test recipe for Phase 1 (elevated PS, Steam UP first — else Auth Failure 14005)
Reach the live tutorial world (the S76 autonomous DS repro), then inject the probe:
1. `ags` `server/internal/interactive/interactive.go`: `ConnectionDetails.address="127.0.0.1:7777"`,
   `forceTutorialMatch=true` (already on disk).
2. Build stub (KILL `UnrealEditor-Cmd` first — LNK1104): `Build.bat LokiEditor Win64 Development
   -Project="…\unreal-stub\Loki.uproject"`; run the stub on `LVL_Tutorial` / `Entry?listen` seeded EGP_SpawnSelect
   (S70), wait "listening on port 7777".
3. Client: `configs\launch-redirect.ps1 -NoHook`. Wait for connect + LVL_Tutorial + `LokiPlayerController_<n>` in
   `Loki.log` (the S73 Loki PC), i.e. the dead-spectator "DROP IN… LOADING" state.
4. Find the live pid (`Get-Process SUPERVIVE-Win64-Shipping`), then inject the PROBE:
   `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\ds_hybrid_loadcensus.dll`
5. Read `docs/ds-hybrid-marker.txt`. Interpret:
   - `[LOAD] type '<T>' -> tid=0x.. ids=N` — which hero PrimaryAssetType matched (N>0). If ALL are 0, extend `kCand`.
   - `[LOAD] class census (PRE-load)` vs `(POST-load)` — did `heroPawnClass` / `BP_HERO_*_C` go 0x0 → non-0x0? That's
     the GO signal.
   - `[LOAD] AsyncLoadPrimaryAssets FAULTED` — the load-call ABI needs one live iteration (unlikely; it's a faithful
     port of the working missions call).

Build the probe: `clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKMODE=MODE_LOAD_CENSUS ds_hybrid.cpp -o
ds_hybrid_loadcensus.dll -lkernel32 -luser32` (already built + committed alongside `ds_hybrid.cpp`). The shipped
spectator-cam build (`ds_hybrid.dll`, default `-DKMODE` = MODE_SPECTATOR_CAM) is unchanged.

## Honest odds
The record (S72/73/74/76) repeatedly reaffirms the reasonable-effort ceiling is the spectator fly-cam and a playable
hero needs SUPERVIVE's dedicated-server-target binary (not in our possession). This moonshot's most likely outcome is
that Phase 1 succeeds (the client has the content) but Phase 3 (swap-in against the fighting networked session)
confirms the wall — the S78 camera-revert is direct evidence. The value of the phased plan is that each gate fails
CHEAPLY and tells us exactly where the wall is, from the strongest-ever position.
