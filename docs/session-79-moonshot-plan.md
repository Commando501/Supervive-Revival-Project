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

**★ CosmeticsAssetID CHASED (2026-07-16, `MODE_COSMENUM`/`MODE_SETCOSMETIC`) — set a valid skin, mesh STILL not built →
next gate = the cosmetics CONTROLLER (BP deploy setup).** The character-skin `PrimaryAssetType` = **`HeroCosmeticsBundle`**
(391 assets; source `server/internal/menu/cosmetics.go` + `data/skins.txt`; `SlotCosmetics` = accessories). Default Assault
skin = **`AssaultDefault`**. `PrimaryAssetIDFromString("HeroCosmeticsBundle:AssaultDefault")` = {type 0x1A572, name 0x38FE89}.
Found the hero fields **`CosmeticsAssetID @+0x1FF0`** + **`OverrideCosmeticsAssetID @+0x2000`**, wrote the valid ID to both,
async-loaded the skin, called `RefreshCosmetics` (re-fired 13× over 12s). ★ BUT skeletal-mesh count stayed 0 → a valid ID
is NECESSARY BUT NOT SUFFICIENT: `RefreshCosmetics` builds the mesh THROUGH the cosmetics controller
(`GetCosmeticsController`, 0x…39C7A0), which a raw GameplayStatics-spawned hero lacks — it's created by the BP deploy
setup (`ClientInitialComponentSetup` / `BP_PostSetupCosmetics`) that never ran. ⇒ REVISED MESH chain: `mesh ←
RefreshCosmetics ← cosmetics CONTROLLER (missing) ← BP deploy setup (ClientInitialComponentSetup/BP_PostSetupCosmetics)`.
NEXT: add a **ProcessEvent capability** (`base+0x12C5A10`, S54-validated) to call those BP setup fns (crash-prone
out-of-context — guard + expect iteration), which should create the controller so `RefreshCosmetics` (with the ID now set)
builds the mesh. Modes added: COSMENUM, SETCOSMETIC.

**★ ProcessEvent CAPABILITY ADDED + the BP deploy setup FAULTS out-of-context (2026-07-16, `MODE_BPDEPLOY`).** Added
`CallGuardedBP(obj, ufunc)` = guarded `ProcessEvent(base+0x12C5A10)(obj, UFunction*, params)` — the correct path for
BP-folded fns (their Func == ProcessInternal, un-callable by the direct-thunk primitive). Reusable. Findings driving it:
- ★ The cosmetics **CONTROLLER ALREADY EXISTS** (`GetCosmeticsController` → `0x…C4173C0`, non-null) — overturns the prior
  "controller missing" hypothesis. So the mesh block is NOT a missing controller.
- ★ **`ClientInitialComponentSetup` and `BP_PostSetupCosmetics` both FAULT via ProcessEvent** (guard-caught, no process
  crash) — they deref deploy context (PlayerState / match-init state / controller relationships) a hand-assembled hero
  lacks. Skeletal-mesh count stayed 0. So the character BODY mesh component (which `ClientInitialComponentSetup` creates
  and `RefreshCosmetics` assigns the skeletal mesh to) never gets built.
⇒ **THE DEEP WALL (now demonstrated, not just predicted):** the remaining deploy setup is a chain of BP functions that
expect the FULL server-driven match-init context; called piecemeal out-of-context they fault. Advancing further needs
reconstructing that CONTEXT (a valid PlayerState + match/deploy state the BP setup reads), which cascades — the
characteristic shape of why a client-side deploy reconstruction is a large, uncertain effort. What IS banked: the entire
deploy control-surface map + LivingState drive + the cosmetics-asset chain + a reusable ProcessEvent capability. Mode added:
BPDEPLOY. Honest status: piecemeal client-side deploy reconstruction has reached the context-dependency wall; a visible/
controllable hero from here needs the match-init context (large) — the reasonable-effort ceiling remains the S79 landmark
(possessed, camera-followed hero in the live world).

**★★★ CONTEXT RECONSTRUCTION PUSHED → DEFINITIVE WALL (2026-07-16, `MODE_CONTEXT`/`MODE_DEPLOYEVT`).** Pushed into the
match-init context per the plan. (1) **Gave the hero a real PlayerState:** the native PC has a valid replicated
`LokiPlayerState` (`0x…AAC040 @ PC+0x3C0`); set it on the hero (`PlayerState @+0x3D8` + `LocalPlayerState @+0x2860`) +
`OnRep_PlayerState` (clean). **`ClientInitialComponentSetup`/`BP_PostSetupCosmetics` STILL FAULT** → PlayerState is not the
(only) missing piece. (2) **Tried the game's own deploy ORCHESTRATOR events** (higher-level entries that run the init in
order): `ReceiveRestarted`, `OnLocalPlayer_CharacterSpawned`, `RefreshLocalControl`, `TryLocalControlSetup` — **ALL FOUR
FAULT** via ProcessEvent, PlayerState set or not; skeletal mesh stayed 0; controller unchanged. ⇒ **DEFINITIVE:** EVERY BP
deploy function faults when driven out-of-context via ProcessEvent — individual setup steps AND the orchestrators. The
client deploy init is entangled with the game's ordered lifecycle + native context in a way a piecemeal injected driver
cannot satisfy; providing single context pieces (PlayerState) doesn't unblock it. Reconstructing it fully = replaying the
entire ordered client match-entry with all native prerequisites ≈ reimplementing the client's deploy, a large research
effort, not a probe. **HONEST CEILING (now empirically demonstrated, not just predicted): the S79 landmark — a possessed,
camera-followed hero in the live tutorial world; the character MESH/input/HUD are deploy-gated and the deploy cannot be
driven client-side out-of-context.** Fully banked + reusable: the deploy control-surface map, LivingState drive, cosmetics
asset chain (`HeroCosmeticsBundle:AssaultDefault`, fields @+0x1FF0/+0x2000), PlayerState offsets (PC+0x3C0, hero+0x3D8/
+0x2860), and the ProcessEvent capability — everything a future server-target-binary or different-technique attempt needs.
Modes added: CONTEXT, DEPLOYEVT.

**★★★ WALL REOPENED (2026-07-16) — the "BP deploy faults = context wall" was likely a FALSE WALL: ProcessEvent BP calls
themselves fault. QUESTION-THE-TOOL win.** New validation modes VTDUMP / BPTEST / BPTEST2:
- **ProcessEvent RVA is CORRECT** (`MODE_VTDUMP`): vtable **slot 56** = `base+0x12C5A10` on hero, PC, AND GameState (all
  match) — so the address is right.
- **BUT a BP call THROUGH ProcessEvent faults** (`MODE_BPTEST`): `GetBaseCosmeticsController` (BP) via ProcessEvent →
  fault, ret=0; while the native `GetCosmeticsController` (direct-thunk primitive) returns the controller `0x…C4173C0`
  fine on the SAME object. So native-thunk calls work; ProcessEvent calls fault.
- **NOT PI-hook re-entrancy** (`MODE_BPTEST2`): raw-removed the ProcessInternal hook, THEN called ProcessEvent → STILL
  faults. So it isn't the hook.
⇒ **The earlier conclusion that the BP DEPLOY functions "fault out-of-context" was almost certainly wrong** — it was the
ProcessEvent *call mechanism* faulting, masquerading as a context wall. This REOPENS the deploy reconstruction: if we can
call BP functions correctly, `ClientInitialComponentSetup` / `BP_PostSetupCosmetics` / the orchestrators may run fine and
build the mesh. **NEXT (fresh session):** (1) isolate hero-specific vs ProcessEvent-general — call a BP function via
ProcessEvent on a KNOWN-GOOD game-initialized BP object (a WBP_ HUD widget, `Comp_PlayerController_Cheats_C`, or a fresh
un-mangled BP_HERO_Assault_C spawned + tested immediately); (2) our current hero (`0x28577E6D560`) is heavily hand-mangled
+ drifted over the void — spawn a FRESH one for clean tests; (3) try calling ProcessEvent from the S78 VTABLE-HOOK tick
(game thread, NOT inside a ProcessInternal call) rather than the PI hook; (4) check ProcessEvent's exact fault (is the
`Parms` buffer sized wrong? does it need `FFrame`/FMemStack state our context lacks? is the UFunction ptr from ResolveFunc
correct for ProcessEvent's class check?); (5) consider that BP calls may need the object's BP VM fully initialized. New
modes: VTDUMP, BPTEST, BPTEST2 (+ reusable `CallGuardedBPP(obj,ufunc,params)` + `RawUnhook()`). This is the live frontier.

**★★★ RESOLVED (2026-07-16, `MODE_BPTEST3`) — ProcessEvent is NEUTERED; the "deploy context wall" NEVER EXISTED.** Called a
NATIVE member (`GetCosmeticsController`) via ProcessEvent AND via the direct-thunk primitive on the same hero:
direct-thunk = `0x…C4173C0` (correct); ProcessEvent = **fault / ret 0**. So ProcessEvent fails to dispatch EVEN A NATIVE
function — it's a broken/neutered path in this build (RECONFIRMS the S54 finding: ProcessEvent no-ops/doesn't execute, which
is the whole reason the direct-thunk native-call primitive was built). ⇒ **EVERY `[BD]/[CX]/[DE] … FAULTED` line earlier
was ProcessEvent failing to dispatch, NOT the BP deploy logic hitting a context wall.** The BP deploy functions
(`ClientInitialComponentSetup`/`BP_PostSetupCosmetics`/`ReceiveRestarted`/…) were NEVER ACTUALLY CALLED. The "deploy needs
match-init context" conclusion is UNPROVEN — we never ran the code. ★ REAL PATH FORWARD: call BP-folded functions by
**building a correct `FFrame` and calling `ProcessInternal` (`base+0x13454A0`) directly** (ProcessEvent's core, minus the
neutering) — set `FFrame.Node=UFunction`, `Object=ctx`, `Code=UFunction->Script.GetData()`, `Locals=alloca(UStruct->
PropertiesSize)` zeroed + params copied, call ProcessInternal **with the PI hook raw-removed** (RawUnhook) so it doesn't
re-enter our hook. Need two offsets (find via a UFunction field walk): `UFunction::Script` (TArray<uint8>) and
`UStruct::PropertiesSize` (int32). Once BP calls actually EXECUTE, retry the deploy setup — the mesh/input/HUD may just work,
or the REAL context gaps (if any) finally show. This is the live frontier; the earlier "definitive wall" is retracted.
New mode: BPTEST3.

**★★★★★ S80 — THE WALL NEVER EXISTED. BP invoker BUILT + LIVE-VALIDATED; the deploy fns RAN for the first time
(`MODE_BPCALL`, 2026-07-16, client PID 48788, no crash).** Two INDEPENDENT tool bugs — not one context wall — produced
every "FAULTED" line in the BPDEPLOY/CONTEXT/DEPLOYEVT runs. Both are now fixed and the S79 "definitive wall" is
formally RETRACTED (as is the S80-prep "ProcessEvent is neutered" claim, which was also wrong):
- **BUG 1 (the real one): `CallNative` hardcodes `FFrame.Code=0`.** Harmless for a native thunk (it ignores Code) — but a
  BP-folded fn's `Func` **IS** `ProcessInternal`, which executes bytecode from `*Stack.Code`. So `Code=0` = a NULL DEREF
  on every BP call. The primitive was already calling the right function; it just handed it a null instruction pointer.
  **FIX = one line:** `Code = UFunction->Script.GetData()@+0x68`, `Locals =` a zeroed `PropertiesSize@+0x60` buffer.
  No new call target needed. New `CallBP(obj,ufunc,args,len)` in ds_hybrid.cpp (RawUnhook() first — the thunk IS our
  hooked address). `CallNative` left untouched (single-variable change; ~30 modes depend on the native path).
- **BUG 2: `base+0x12C5A10` is NOT ProcessEvent** (live capstone disasm, `tools/re/` pattern → scratch `disasm_live.py`).
  Its prologue saves only `rcx→rdi` and `rdx→r14` and **never touches `r8`**, then clobbers r8 at its first `call` ⇒ it's
  a **2-arg fn that ignores the Parms buffer entirely** (it guards recursion on `this` via a TLS list at `TLS+0xa20`,
  lazy-inits a TLS thread-context at `TLS+0xf60`, and tail-calls vtable **slot 58** `[rax+0x1d0]`). The S54 "slot 56 =
  ProcessEvent" identification is WRONG — that's why routing calls through it faulted even for a NATIVE member
  (MODE_BPTEST3) and looked "neutered". ⇒ **The real ProcessEvent is still unidentified — but is NOT NEEDED**, since
  BP fns' Func is already ProcessInternal. Don't rebuild a ProcessEvent path; use `CallBP`.
- **BUG 3 (why the "orchestrators" all faulted):** `Pawn::ReceiveRestarted` is an **EMPTY** BlueprintImplementableEvent
  stub (Script=0, PropertiesSize=0, EventGraphFunction=0) that `BP_LokiHeroCharacter_C` never overrides — calling it is a
  no-op BY DESIGN, not a context fault. The S80-prep "ubergraph wrinkle" worry is moot: the REAL deploy fns carry their
  own bytecode (a Script=18 fn is exactly an `EX_LocalFinalFunction ExecuteUbergraph(EntryPoint)` thunk — the ubergraph
  jump is IN the bytecode, so a correct FFrame runs it; `EventGraphFunction`/`CallOffset` fast-path is unused here).
- ★ **Live UFunction survey (read-only RPM, no injection — scratch `ufunc_survey.py`, worth re-creating):** dumps every
  UFunction on a class chain with `Func` (native-vs-ProcessInternal), `Script.Num`, `PropertiesSize`, `ParmsSize`,
  `ReturnValueOffset`, `EventGraphFunction`, flags. On `BP_LokiHeroCharacter_C`: `ClientInitialComponentSetup`
  (Script=88, PropSz=2), `GetBaseCosmeticsController` (121/25), `BP_PostSetupCosmetics` / `TryLocalControlSetup` /
  `RefreshLocalControl` (18/0), `OnLocalPlayer_CharacterSpawned` (36/8, takes a param). **Always check Script.Num>0
  before concluding a call "faulted" — an empty stub is a no-op, not a wall.**
- **★ LIVE RESULT (the gate is self-checking):** `GetBaseCosmeticsController`'s own bytecode calls the NATIVE
  `GetCosmeticsController` into local `CallFunc_..._ReturnValue@+0x8`, so that local MUST equal the direct-thunk value.
  It did: `fault=0 out@+0x0=0x2868C4173C0 CallFunc@+0x8=0x2868C4173C0` == ground truth `0x2868C4173C0`. **BP bytecode
  executes.** Then, gated on that pass, all four deploy fns **RAN clean (fault=0)** — the first time they have ever
  actually executed: `ClientInitialComponentSetup`, `BP_PostSetupCosmetics`, `TryLocalControlSetup`, `RefreshLocalControl`.
- **★ HONEST REMAINING GAP: `skeletal meshes AFTER = 0` — the mesh STILL did not build.** The deploy fns ran cleanly and
  produced no character mesh, and `RefreshCosmetics` (native, fault=0) still built nothing. This is now a REAL finding
  (code executed) rather than an artifact. It does NOT re-establish the S79 wall — nothing here says "needs match-init
  context"; the fns ran without complaint. Most likely: they internally early-out on a predicate a hand-assembled hero
  fails (e.g. `IsLocallyControlled`/authority/`HasAuthority`, a null PlayerState-derived loadout, or the async
  `HeroCosmeticsBundle:AssaultDefault` load not being RESIDENT when RefreshCosmetics ran).
  **NEXT (highest value, in order):** (1) ★ the tool now exists to see INSIDE — read `ClientInitialComponentSetup`'s 88
  bytes of bytecode (`Script.Data` via RPM, disassemble the UE VM opcodes) and `BP_PostSetupCosmetics`' 18 → find which
  ubergraph entry/predicate they hit and what they need; (2) call `OnLocalPlayer_CharacterSpawned` (Script=36) — it takes
  an 8-byte param (the local player?) and is the "character spawned" entry the game itself uses; (3) verify the cosmetics
  bundle is actually LOADED (not just ID-set) before `RefreshCosmetics`; (4) re-run on a FRESH hero (the current
  `0x28577E6D560` is hand-mangled + drifted over the void). New mode: BPCALL. `CallBP` is reusable for ALL future BP work.

**★★★★★ S80b — READ THE BYTECODE: `ClientInitialComponentSetup` DOESN'T BUILD THE MESH. The whole S79 mesh chain was
a GUESS about what that fn does, and the guess was wrong.** With `CallBP` working we could finally look INSIDE. New tool
`tools/re/script_dump.py` (read-only RPM) dumps a BP UFunction's `Script` bytecode and resolves embedded UObject*/FName
operands to names. `ClientInitialComponentSetup` (88 bytes) decodes EXACTLY (every jump offset lands on an opcode
boundary, total 88 ✓):
```
+0   CallMath  LokiBlueprintLibrary::ClientOnly(Self) -> CallFunc_ClientOnly_OutputExecs
+20  LetBool   bool_local = KismetMathLibrary::NotEqual_ByteByte(OutputExecs, ByteConst 0)
+51  JumpIfNot(70) bool_local        // OutputExecs == 0  -> goto 70
+65  Jump(85)                        // OutputExecs != 0  -> return, do nothing
+70  LocalVirtualFunction 'SetCastRangeVisibility'(False)
+85  Return / Nothing / EndOfScript
```
⇒ **its ENTIRE body is `if (ClientOnly()) SetCastRangeVisibility(false)`** — a cast-range DECAL toggle. It never touches
the character mesh, never creates a component, never calls cosmetics. **The S79 chain "mesh <- RefreshCosmetics <-
cosmetics CONTROLLER <- ClientInitialComponentSetup / BP_PostSetupCosmetics" was never verified — it was inferred from
function NAMES.** (The controller was ALSO already non-null, which should have been the tell.) So `skeletal AFTER = 0` is
fully explained: none of the four fns we ran builds a mesh. Nothing here is a context wall.
**METHOD LESSON (this session's theme, twice over): verify what a function DOES before theorizing about why it "fails."
Read the bytecode (`script_dump.py`) / check `Script.Num>0` (`ufunc_survey.py`) FIRST.** Both are read-only, need no
injection, and cost seconds.
**NEXT — find the REAL character-mesh builder (the hypothesis space is now open, so re-derive, don't guess):**
(1) `BP_PostSetupCosmetics` (18 B) is an `ExecuteUbergraph_BP_LokiHeroCharacter(EntryPoint)` thunk — dump the UBERGRAPH
    bytecode at that EntryPoint (that's where real BP work lives; `script_dump.py` + the fn ptr/int operands give it).
(2) A hero with a working mesh EXISTS in-game normally — find the builder empirically: on a REAL hero, what creates the
    SkeletalMeshComponent? Look for native `USkeletalMeshComponent` creation on `LokiHeroCharacter` /
    `LokiCosmeticsController` (`0x2868C4173C0`, class already known) — `ufunc_survey.py` that controller's class chain.
(3) `RefreshCosmetics` (native, fault=0, built nothing) — disassemble it (`tools/re/disasm_live.py` on its thunk
    `0x7FF6B439E420`) to see its early-outs; that's the one fn we KNOW is the native cosmetics entry.
(4) The cosmetics bundle may not be RESIDENT (ID set != loaded).

**★★★★★ S80c — THE MESH WALL NEVER EXISTED EITHER: the hero HAS a mesh, it is VISIBLE, and it is RENDERING.
`CountHeroSkeletals()` is a BROKEN MEASUREMENT — the 4th tool bug this session, and the one that invented the problem.**
Dumping the ubergraph (new tool `tools/re/ubergraph_dump.py`, operand-aware, read-only) at BP_PostSetupCosmetics'
EntryPoint showed `CreateProxyObjectForPlayMontage(**InstanceVariable Mesh**, ...)` — i.e. the BP itself references a
`Mesh` var. That's stock `ACharacter::Mesh`, created in C++ in the constructor. So a spawned hero ALWAYS had one. Live RPM:
```
hero->Mesh @+0x450 = 0x286E0753B20   name='CharacterMesh0'  class=BP_Assault_DefaultSKMeshComponent_C
   SkeletalMesh/SkinnedAsset @+0x728/+0x730 -> SK_Assault_Default_LOD1  [SkeletalMesh]   (ASSIGNED)
   bVisible=True  bHiddenInGame=False  bOwnerNoSee=False  bOnlyOwnerSee=False  bRenderInMainPass=True
   ★ bRecentlyRendered=TRUE  (the renderer DREW it)
hero: bHidden=False  HeroPredropHidden=False  LivingState=1 (Alive)
```
★ **THE BUG:** `CountHeroSkeletals()` filters `strstr(cn,"SkeletalMeshComponent")||strstr(cn,"SkinnedMeshComponent")`, but
the component's class is `BP_Assault_Default`**`SKMesh`**`Component_C` — **"SKMeshComponent" never matches "SkeletalMeshComponent"**.
It has been reporting 0 for a component that exists, has a real skeletal asset, and is on screen.
⇒ **EVERYTHING built on `skeletal==0` COLLAPSES:** S79's MESHDIAG "there is NO character SkeletalMeshComponent"; the whole
cosmetics chase (MESHMGRRECON/COSMETICS/COSMENUM/SETCOSMETIC); "RefreshCosmetics built nothing"; "mesh <- RefreshCosmetics
<- CosmeticsAssetID <- loadout/PlayerState"; "the cosmetics CONTROLLER is missing"; "the BP deploy setup must create the
mesh"; and the S79 "DEFINITIVE deploy-context WALL". None of it was ever measured — it was one broken substring.
★ **The record even CONTRADICTED itself and it was missed:** the Phase-4d SCREEN CHECK has the USER SEEING THE HERO —
"dark angular mesh shapes lower-left = the hero's model with the camera clipping into it at its root". The mesh was
rendering at 4d. 4h's "the hero renders as an INVISIBLE point" came from the counter, not from the screen. **When a live
observation contradicts a tool, believe the observation.**
⇒ **WHAT IS ACTUALLY LEFT for a playable hero** (much smaller than the record claims — mesh/cosmetics/deploy-context are
all OFF the list): (1) **POSITION** — the physics-enabled hero DRIFTED OFF the island over the void (S79 4h); teleport it
back onto LVL_Tutorial ground (`K2_SetActorLocation`, native, already proven). (2) **INPUT** — the one genuinely
unaddressed gap: Enhanced-Input `PawnInputComponent0` needs its mapping context applied (mouse-look already reaches the
camera; WASD doesn't reach movement). `TryLocalControlSetup` now RUNS (S80) — dump ITS ubergraph entry to see what local
control actually requires. (3) **HUD** — widget components. (4) Camera rig = already solved + drivable (S79 4h).
**METHOD (the whole lesson of S80): before believing ANY "X is missing/broken" claim, verify the MEASUREMENT. Four walls
this session — BP calls fault / ProcessEvent neutered / deploy needs match-init context / the hero has no mesh — were ALL
tool bugs. Read-only tools that cost seconds and need no injection: `ufunc_survey.py` (is it runnable?), `script_dump.py`
(what does it DO?), `ubergraph_dump.py` (what does the BP graph DO?), `disasm_live.py` (what does the native fn DO?).**

**★★★★★ S80d — `TryLocalControlSetup`'s ubergraph DECODED + a 5th tool bug caught BEFORE it faked a wall (FFrame::FlowStack).**
`TryLocalControlSetup` (18 B) -> `ExecuteUbergraph_BP_LokiHeroCharacter(31634)`; entry 31634 is just `Jump -> 29873`
(everything printed linearly after 31639 is UNRELATED graph that merely follows in memory — always FOLLOW THE JUMP).
Real body @29873:
```
29873  CallMath ClientOnly [LokiBlueprintLibrary] (Self) -> OutputExecs
29924  JumpIfNot -> 29939 ; 29938 PopExecutionFlow          // bail if OutputExecs != 0 (not a client)
29939  LocalVirtualFunction 'RefreshLocalControl' ()
29953  LetBool CallFunc_IsLocallyControlled_ReturnValue = VirtualFunction 'IsLocallyControlled' ()
29977  ★ PopExecutionFlowIfNot IsLocallyControlled          // <<<< THE GATE
29987  PushExecutionFlow -> 30032
30058  AkGameplayStatics::SetState('InEOGScreen-False'), SetState('CelebrationScreen-None')
30140  BindDelegate 'Brush Tracker Entered' / 'Brush Tracker Exited' (Self)
30186  SetArray [BP_Brush_C, BP_Brush_Prop_C, BP_BrushTall_C] ; 30374 Let Ally ...
```
★ **`TryLocalControlSetup` is NOT the Enhanced-Input mapping-context setup** — it does audio states, brush-tracker
delegates, MPC scalar params and Ally setup. That was ANOTHER name-based assumption, wrong again. The input binding is
elsewhere; find it by DUMPING, not by naming.
★ **THE GATE = `APawn::IsLocallyControlled()` = `Controller && Controller->IsLocalController()`. LIVE-VERIFIED IT SHOULD
PASS:** `hero->Controller @+0x400 = 0x285752F50B0` (native `LokiPlayerController`, still wired from S79 4d),
`controller->Pawn == hero`, controller `Role=AutonomousProxy(2)` (on a client an AutonomousProxy PC IS the local
controller), hero `Role=Authority(3)`. So both gates pass.
★★★ **BUG 5 (MINE, caught by dumping rather than by a failure): `CallBP` inherited a STALE `FFrame::FlowStack`.**
Ubergraphs are full of `EX_PushExecutionFlow`/`EX_PopExecutionFlow`, which operate on `FFrame::FlowStack`. `CallBP`
copied the captured template frame and never reset it, so the graph's bail paths (`PopExecutionFlow` @29938, 29977)
popped a GARBAGE offset from whatever call we piggybacked and jumped into arbitrary bytecode — while still reporting
`fault=0`. **A BP call MUST start with an EMPTY FlowStack** ("empty == return" is what the bail paths rely on).
**FIXED:** `memset(frame+0x48,0,0x30); Max=8; PreviousFrame=0; CurrentNativeFunction=0`.
**Layout (confirmed by ARITHMETIC, not guessed):** UE5 FFrame `MostRecentPropertyContainer@0x40`, **`FlowStack@0x48`**
(`TArray<CodeSkipSizeType,TInlineAllocator<8>>` = Inline[32]@+0x00, Secondary@+0x20, Num@+0x28, Max@+0x2C = 0x30 bytes),
`PreviousFrame@0x78`, `OutParms@0x80`, `PropChain@0x88`, `CurrentNativeFunction@0x90` — and `0x48+0x30 = 0x78/0x80/0x88`
matches this project's long-established `FF_OUTPARMS=0x80`/`FF_PROPCHAIN=0x88` EXACTLY.
★ Re-ran with the fix (live, PID 48788, no crash): all four deploy fns RAN clean on a proper empty flow stack, and the
honest in-process mesh report confirms the RPM finding:
`hero->Mesh @+0x450 = 0x286E0753B20 [BP_Assault_DefaultSKMeshComponent_C] SkeletalMesh='SK_Assault_Default_LOD1'`.
`CountHeroSkeletals()` is now loudly documented as BROKEN in-source (filter widened to "MeshComponent") — do not use it
to conclude "no mesh"; read `ACharacter::Mesh` by reflection instead.

**★ S80e — `RefreshLocalControl`'s ubergraph: it's TINY and it is NOT input either.** (18 B) ->
`ExecuteUbergraph_BP_LokiHeroCharacter(31477)`; 31477 = `ClientOnly` gate + `JumpIfNot -> 30964` (again: FOLLOW THE
JUMP — 31543+ is an unrelated chunk, and 31634 is TryLocalControlSetup's entry). Real body @30964:
```
30964  LocalVirtualFunction 'RefreshViewFinder' ()
30978  Context: Default__AkGameplayStatics -> SetState('BeingExecuted-False')
31019  PopExecutionFlow                                  // end of chunk -- that's the WHOLE function
```
⇒ `RefreshLocalControl` = a view-finder refresh + one audio state. **No Enhanced-Input mapping-context anywhere.**
⇒ **NEITHER `TryLocalControlSetup` NOR `RefreshLocalControl` binds input** — three name-based assumptions have now been
falsified by dumping (the S79 mesh chain, TryLocalControlSetup, RefreshLocalControl). **Stop picking promising-sounding
function names.**
★ **BONUS (a genuinely useful chunk found next door, @31020 — `BP_OnRep_PlayerState`):** `ClientOnly` gate ->
`CallMulticastDelegate OnClientPlayerStateUpdated` -> `TrySetEmoteAudioActor()` -> `BP_AimingVisComponentV2 ->
InitOnLocalASC()` -> `LetObj LocalPlayerState = <event param>` -> `PopExecutionFlowIfNot IsValid(PlayerState)` ->
`AbilitySystemBlueprintLibrary::GetAbilitySystemComponent(PlayerState)` -> `OnLocalPlayerState_ASCInitialized()`.
**That's the ASC/GAS local-init path** — the thing abilities/input actually hang off, and it's driven by
`BP_OnRep_PlayerState` (a `LocalFinalFunction` on `LokiHeroCharacter`, i.e. directly callable via `CallBP`). S79's
MODE_CONTEXT already set the hero's `PlayerState @+0x3D8` + `LocalPlayerState @+0x2860` from the native PC's replicated
`LokiPlayerState`, so this path is plausibly runnable NOW.
★ **NEXT (find input by SEARCHING, not naming):** scan the whole 42271-byte `ExecuteUbergraph_BP_LokiHeroCharacter`
Script (and the native PC's class chain) for operand pointers whose names contain `MappingContext` / `EnhancedInput` /
`InputAction` — `ubergraph_dump.py`'s `ofull()` already resolves every operand, so a scan is trivial. Also check the
NATIVE side: UE binds Enhanced Input in `APawn::SetupPlayerInputComponent` / `PawnClientRestart` and
`UEnhancedInputLocalPlayerSubsystem::AddMappingContext` (usually from the PC). NB S79 4d RAW-WIRED `nativePC->Pawn`/
`hero->Controller`, which BYPASSED `AController::Possess`/`PossessedBy` -> `PawnClientRestart` -> input setup; 4g called
`ClientRestart` and it "fired clean", but that was never verified to have bound anything.
★ Also worth a look: @31553 the graph references `InstanceVariable SpringArmComponent` (`CameraLagSpeed` @0x41900000=18.0,
`CameraLagMaxDistance` @0x437A0000=250.0) — S79 4e's census concluded "the hero has NO USpringArmComponent". Given the
CountHeroSkeletals precedent, **that census deserves the same re-verification** (read the property by reflection).

**S80f -- 6th TOOL BUG: the S79 4e census "the hero has NO USpringArmComponent" is WRONG. The hero has a FULLY
CONFIGURED camera rig, and S79 Phase 4h spent the session FIGHTING IT.** Re-verified by REFLECTION (new tool
`tools/re/comp_census.py`, read-only -- walks the class chain's ChildProperties and reads each ObjectProperty; EXACT,
cannot cap out or miss on a name filter, unlike the GUObjectArray + substring + outer-chain scans that produced this bug
AND the CountHeroSkeletals one):
```
SpringArmComponent  @+0x1990 = 0x28615E8C870  class=LokiCharacterSpringArmComponent
   ancestry: LokiCharacterSpringArmComponent <- SpringArmComponent <- SceneComponent <- ActorComponent <- Object
   TargetArmLength=3020   bEnableCameraLag=True   CameraLagSpeed=18   CameraLagMaxDistance=250  bDoCollisionTest=False
Camera              @+0x22D8 = 0x28679DE4B60  class=CameraComponent
InputComponent      @+0x170  = 0x28600E813C0  class=EnhancedInputComponent   [declared on Actor]
Mesh                @+0x450  = 0x286E0753B20  class=BP_Assault_DefaultSKMeshComponent_C
```
- **`TargetArmLength` was ALREADY 3020** -- the authentic SUPERVIVE top-down distance. S79 4h hand-tuned "authentic
  top-down ~= 3000-4000 up" and was REDISCOVERING a value the component already held. 4e's "my TargetArmLength write was
  a no-op" was a write to the WRONG ADDRESS, not an absent component.
- `CameraLagSpeed=18` / `CameraLagMaxDistance=250` are EXACTLY the constants the ubergraph writes at 31543
  (`0x41900000`=18.0, `0x437A0000`=250.0) -- independent confirmation this is the real, live rig.
- **THIS REFRAMES ALL THE S79 CAMERA WORK.** 4h drove the hero's `CameraComponent` world transform and re-applied it
  **~40x/run "to hold vs per-frame reset"** -- that per-frame reset WAS THE SPRING ARM DOING ITS JOB. The
  "camera-rig control = solved + drivable" result is a hack fighting a correctly-configured rig that already framed the
  hero at 3020. **Don't drive the CameraComponent -- let the spring arm drive it** (that is what the game does). If
  framing is wrong, fix it through the spring arm's own properties / the `OverrideSpringArmCurve` TimelineComponent
  @+0x22F8.
- **`AActor::InputComponent @+0x170` is a live `EnhancedInputComponent`** -- created by `APawn::PawnClientRestart` ->
  `SetupPlayerInputComponent`, so input setup DID run at some point (S79 4g's `ClientRestart` plausibly did it). So
  "input is unbound" is ALSO not established. The remaining input question is narrower: **is a mapping context added?**
  That is `UEnhancedInputLocalPlayerSubsystem::AddMappingContext` -- a LOCAL PLAYER subsystem, NOT on the hero. Look
  there, not on the pawn.
- Other notables from the 41-component reflection census: `CharacterMovement` (`LokiCharacterMovementComponent` @+0x458),
  `RootComponent`/`CapsuleComponent` @+0x1B0/+0x460, `VisibilityState` @+0xD38, `TeamComponent` @+0xD28,
  `BP_AimingVisComponentV2` @+0x2220 (the `InitOnLocalASC` target), `CastRangeDecal`/`CastRangeToggleDecal`
  @+0x2258/+0x2250 (what `ClientInitialComponentSetup` actually toggles), `MapView`/`MapIconHero`, `LokiHeroUsable`,
  `LazyMovementRoot` @+0x1998, and 8 TimelineComponents.

**RUNNING TALLY OF FAKE WALLS THIS SESSION: 6.** (1) BP calls "fault" = `FFrame.Code=0`; (2) ProcessEvent "neutered" =
a misidentified 2-arg fn at slot 56; (3) deploy "needs match-init context" = the fns never ran; (4) hero "has no mesh" =
a broken substring filter; (5) `CallBP`'s stale FlowStack (mine -- caught by dumping, before it faked anything); (6) hero
"has no spring arm" = a broken census. **EVERY ONE was a tool or measurement bug. NOT ONE was the game.** The record's
"honest ceiling", "definitive wall" and "reasonable-effort ceiling" language across S72-S79 was measuring the tools.
**METHOD: read state by REFLECTION (`comp_census.py`), read behaviour by DISASSEMBLY (`ubergraph_dump.py`/`script_dump.py`
/`disasm_live.py`), check runnability first (`ufunc_survey.py`). All read-only, no injection, seconds each.**

**S80g -- THE FIRST *REAL* GAP OF THE SESSION: no Enhanced Input MAPPING CONTEXT is applied, and SUPERVIVE adds them
from NATIVE code, not Blueprint.** Every prior "wall" this session dissolved into a tool bug; this one survived
re-verification, so treat it as real (but keep verifying).
```
LocalPlayer 0x28541940E00 -> PlayerController 0x285752F50B0 (LokiPlayerController)
PC->PlayerInput @+0x530 = 0x285F0307720   class=EnhancedPlayerInput
PlayerInput->AppliedInputContexts @+0x560 [MapProperty]  ->  Data=0x0 Num=0 Max=0   *** EMPTY ***
EnhancedInputLocalPlayerSubsystem  = 0x285C4460200   (EXISTS)
EnhancedInputSubsystemInterface::AddMappingContext = 0x28504E423A0  (NATIVE UFunction, Script=0)
```
Findings, each re-verified rather than assumed:
- **`AppliedInputContexts` is EMPTY** (TMap Data/Num/Max all 0) -> **no mapping context applied**. That is why WASD does
  not reach movement, while mouse-look (which is not IMC-gated) does.
- **ZERO `InputMappingContext` ASSETS are loaded** -- and this was re-checked with a SUBSTRING scan over all 175,914
  live objects (not the exact-match that faked walls 4 and 6): only CDOs (`Default__InputMappingContext`) exist. The
  `InputMappingContext` UClass IS loaded (0x2857FB7DA80), so the type is present; the assets are not.
- **No IMC-typed property** on the hero's or the PC's class chain.
- ★★★ **GLOBAL BYTECODE SCAN: of 14,921 loaded BP functions WITH bytecode, NOT ONE calls `AddMappingContext`.** So
  SUPERVIVE does **not** add mapping contexts from Blueprint at all -- it must do so from **native C++** (a
  `LokiPlayerController::SetupInputComponent` / custom keybind-settings path). That also independently re-confirms the
  S80d/e result that no hero BP fn (`TryLocalControlSetup`/`RefreshLocalControl`/etc.) binds input.
- Consistent with the whole DS session: it never deployed into a match, so the native path that loads + adds the IMCs
  never ran.
**⇒ NEXT (concrete, and the pieces are already in hand):** `AddMappingContext` is a **NATIVE** UFunction, so the existing
direct-thunk primitive (`CallNative`) can call it, and the subsystem object already exists (0x285C4460200). The ONLY
missing piece is an actual **IMC asset**. To find one:
  1. **The asset catalog: `docs/game-map.md` is only 8.7 KB -- it is a 42-CATEGORY INDEX, NOT the 68,228-asset list.**
     A grep over it returning 0 proves NOTHING about whether IMC assets exist (this nearly became fake wall #7). Get the
     real list from the extractor: `tools/extractor/` -> `enumerate` / `names` / `namesall`, then grep for
     `InputMappingContext` / `IMC_`.
  2. Then load it (the PROVEN missions/S79-Phase-1 load primitive: `PrimaryAssetIDFromString` ->
     `GetPrimaryAssetIdList` -> `AsyncLoadPrimaryAssets`, or a direct object/class path load), and call
     `AddMappingContext(subsystem, imc, priority, options)` via `CallNative`. NB the 3rd param is a
     `FModifyContextOptions` STRUCT -> use `BuildOutParms` (the S72/S74 struct-param ABI fix).
  3. Cross-check the native side for the real load+add site: `usmapdump disasm` / `callxref` around
     `LokiPlayerController::SetupInputComponent`, or `tools/re/disasm_live.py` on `AddMappingContext`'s exec thunk.
  4. Alternative worth a look: the 3 live `EnhancedPlayerInput` objects (0x285F0307720 / 0x28684C21BE0 / 0x2868F09E4A0)
     -- check whether ANY of them has a non-empty `AppliedInputContexts` (one may belong to a differently-initialised
     player), which would name the exact IMC asset the game uses.

**S80h -- the cheap shortcut is DEAD (useful negative): ALL THREE live `EnhancedPlayerInput` objects have an EMPTY
`AppliedInputContexts`.** Substring-scanned every live `*PlayerInput*` object (not exact-match):
```
0x285F0307720  outer=LokiPlayerController           (the native/ACTIVE PC)      AppliedInputContexts@+0x560 Num=0  EMPTY
0x28684C21BE0  outer=BP_LokiPlayerController_Dev_C  (OUR S79 Phase-2/3 spawn)   AppliedInputContexts@+0x560 Num=0  EMPTY
0x2868F09E4A0  outer=BP_LokiPlayerController_Dev_C  (OUR S79 Phase-2/3 spawn)   AppliedInputContexts@+0x560 Num=0  EMPTY
```
The two non-active ones are the `BP_LokiPlayerController_Dev_C` instances **we spawned ourselves** (S79 Phase 2 =
0x2868B5ED8A0, Phase 3 = 0x28690832770) -- never initialised by the game, so their emptiness is expected and tells us
nothing new about the game's IMC. ⇒ No live object NAMES an IMC asset; the shortcut is closed.
★ **But it CORROBORATES S80g from a 4th independent angle:** NOT ONE `PlayerInput` in the entire process has EVER had a
mapping context applied. Combined with (a) zero IMC assets loaded, (b) zero of 14,921 BP fns calling AddMappingContext,
and (c) no IMC-typed property on hero/PC -- the native load+add path never ran ANYWHERE in this session. Exactly what you
expect from a client that never deployed into a match. **The S80g gap is real and now quadruply confirmed.**
⇒ **The catalog route is the ONLY route left** (and the pieces are in hand: `AddMappingContext` @0x28504E423A0 is NATIVE
so `CallNative` can call it; subsystem 0x285C4460200 exists). Get the IMC asset path from **`tools/extractor`**
(`enumerate`/`names`/`namesall`) -- NOT from `docs/game-map.md` (8.7 KB, a 42-category INDEX, not the 68,228-asset list;
grepping it returns 0 and proves nothing). Then load + `AddMappingContext(subsystem, imc, priority, options)` with
`BuildOutParms` for the `FModifyContextOptions` struct param. Secondary: `tools/re/disasm_live.py` on
`AddMappingContext`'s exec thunk + `usmapdump callxref` to find the NATIVE add-site (which would also reveal how the game
picks the IMC).

**S80i -- IMC asset hunt: INCONCLUSIVE (and I nearly published fake wall #7 TWICE doing it). Do NOT conclude "SUPERVIVE
has no IMC assets" from what follows -- the searches are not trustworthy for this question yet.**
What was tried, and why each negative is WEAK:
1. `extractor wherefile IMC_ InputMappingContext MappingContext` -> **0 hits. MEANINGLESS.** `wherefile` searches
   virtual PATHS, and a path contains the asset's NAME, not its CLASS. An IMC named `Loki_Input_Default` would never
   match "InputMappingContext". **Never search for a TYPE in a PATH.**
2. `extractor assetregistry candidates InputMappingContext` -> 0 of 103,841 FAssetData. Search is CLASS-based and the
   tool provably WORKS (`candidates Blueprint` -> 36,625; `candidates SkeletalMesh` -> 351). **BUT `candidates Mission`
   -> 0 as well**, and (a) the extractor's OWN usage text gives `Mission`/`LokiDataAsset_Mission` as its worked example,
   and (b) this project has a fully working missions page built on exactly those assets. **A search that resolves engine
   classes but returns 0 for a class we KNOW ships means this AR.bin's class coverage does NOT extend to custom/plugin
   classes.** (Also note it loads "103,841 FAssetData / **0 DependsNode / 0 PackageData**" -- partial.) So its 0 for
   InputMappingContext (an EnhancedInput *plugin* class) proves nothing.
**What IS solid from the live process (all re-verified, S80g/h):** `AppliedInputContexts` EMPTY on all 3
`EnhancedPlayerInput` objects; `EnhancedActionMappings` (the flattened list UEnhancedPlayerInput REBUILDS from applied
IMCs) EMPTY @+0x5B0; `DebugExecBindings` @+0x1A8 Num=16 NON-empty (proves the property walk reaches UPlayerInput, so the
empties are real); **legacy `UPlayerInput::ActionMappings`/`AxisMappings` are ABSENT from the class entirely** (UE5 moved
them behind WITH_EDITORONLY_DATA -> stripped from shipping). ⇒ **there is no legacy input path, so SUPERVIVE MUST drive
Enhanced Input from IMCs** -- which means the IMC assets DO exist somewhere and the searches above simply failed to find
them. 0 of 14,921 loaded BP fns call `AddMappingContext` ⇒ the load+add is **NATIVE**.
**NEXT (in confidence order):**
1. ★ **Find the NATIVE add-site instead of hunting the asset** -- it will NAME the asset for us.
   `tools/re/disasm_live.py` on `AddMappingContext`'s exec thunk (UFunction 0x28504E423A0, read `Func@+0xE0` for the
   thunk), then `usmapdump callxref <native AddMappingContext impl>` to find `LokiPlayerController::SetupInputComponent`
   / the keybind-settings path that calls it. Follow its operands to the IMC (a SoftObjectPath / DataAsset / config).
2. Re-run the class search against a BETTER asset registry: the live game's in-memory AR, or regenerate
   `out/AssetRegistry.bin` (the current one is partial: 0 DependsNode / 0 PackageData). Cross-check by first confirming
   `candidates Mission` returns hits -- **that is the canary; until Mission works, an Input 0 means nothing.**
3. Cheap: `extractor namesall InputMappingContext` (harvests NameMap vocabulary across assets -- finds the type even when
   no path/class search does), and `usmapdump wstrings/strings SUPERVIVE-Win64-Shipping.exe MappingContext`.
4. Once an IMC is in hand: it is loadable + `AddMappingContext` @0x28504E423A0 is NATIVE ⇒ `CallNative(subsystem=
   0x285C4460200, imc, priority, options)`, with `BuildOutParms` for the `FModifyContextOptions` struct param.

**S80j -- native add-site hunt: PARTIAL. The KEY structural fact is found (the call is VIRTUAL, so callxref cannot work
as planned), but the add-site is NOT yet located. Nothing here is a wall.**
- **`execAddMappingContext` = `base+0x4BFA590`** (= `AddMappingContext` UFunction 0x28504E423A0, `Func@+0xE0`;
  ParmsSize=13 = IMC ptr(8) + Priority int32(4) + packed options(1)). Its body is the standard FFrame param-unpack
  (`base+0x1345FB0`/`0x1345FE0` = FFrame::Step helpers), then:
```
+0x4BFA667  mov rax,[rbx+0x38]      ; rbx = FFrame
+0x4BFA66B  lea r9,[rsp+0x40]       ; &Options (FModifyContextOptions)
+0x4BFA670  mov r8d,[rsp+0x48]      ; Priority (int32)
+0x4BFA678  mov rdx,[rsp+0x58]      ; the InputMappingContext*
+0x4BFA67D  mov rcx,rsi             ; this (interface-adjusted Context)
+0x4BFA696  mov rax,[rsi]           ; vtable
+0x4BFA699  call qword ptr [rax+0x98]   ; <<<< VIRTUAL, slot 19 (0x98/8)
```
- ★★★ **`AddMappingContext` is a VIRTUAL interface call (`IEnhancedInputSubsystemInterface`, vtable slot 19).** ⇒ **the
  planned `usmapdump callxref <AddMappingContext>` CANNOT find the add-site** -- native callers dispatch through the
  vtable, not a fixed address. This retires that plan; it is a fact about the target, not a wall.
- **Candidate concrete impl: `base+0xB9E1F0`** = slot 19 of the vtable at `subsystem+0x00` (subsystem 0x285C4460200).
  ★ **UNVERIFIED -- DO NOT TRUST IT YET.** `UEnhancedInputLocalPlayerSubsystem : ULocalPlayerSubsystem,
  IEnhancedInputSubsystemInterface` is MULTIPLE INHERITANCE, so the INTERFACE vptr is at some obj+N, NOT necessarily
  +0x00. Slot 19 of the *UObject* vtable is a completely different function. **This is exactly the shape of the S54
  "slot 56 = ProcessEvent" error that faked wall #2 -- verify before building on it.** To verify: scan obj+0x00..+0x60
  for all vptrs, and confirm which vtable's slot 19 disassembles as an AddMappingContext impl (it should touch
  `AppliedInputContexts`/rebuild `EnhancedActionMappings`), or find the interface vptr by matching against
  `Default__EnhancedInputLocalPlayerSubsystem`.
- **String hunt for the IMC asset: negative but WEAK.** `usmapdump strings IMC_` -> **0 hits**. `usmapdump wstrings
  MappingContext` -> 12 hits, but ALL are heap FName/reflection metadata (`"InputMappingContext"` as a type name,
  outside the main module), NOT asset paths. Neither rules out IMC assets: a `FSoftObjectPath` may be stored in a
  cooked asset/config rather than as an exe literal, and the assets need not be named `IMC_*`.
**NEXT:** (1) verify the interface vptr offset + slot-19 impl (above), THEN `usmapdump callxref <verified impl>` for the
native add-site -- it will NAME the IMC. (2) In parallel, regenerate a COMPLETE `AssetRegistry.bin` (the current one is
partial: 0 DependsNode / 0 PackageData) and re-run `assetregistry candidates InputMappingContext`, **using
`candidates Mission` as the canary -- until Mission returns hits, an Input 0 means nothing.** (3) `extractor namesall
InputMappingContext` harvests NameMap vocabulary across assets and can find the type where path/class searches fail.

**S80k -- interface vptr VERIFIED; the S80j candidate was REFUTED (it would have been fake wall #8). Impl disasm is
BLOCKED BY DEMAND-DECRYPT, not by logic.**
- ★★★ **`base+0xB9E1F0` (the S80j slot-19 candidate) is DEFINITIVELY NOT AddMappingContext.** Discriminator: slot 19 of
  the *primary* vtable is identical on the hero (`BP_HERO_Assault_C`), the `LocalPlayer`, AND the `PlayerInput` --
  `base+0xB9E1F0` on all three ⇒ it is a **generic UObject virtual shared by every UObject**. Trusting it would have
  repeated the S54 "slot 56 = ProcessEvent" error EXACTLY (that error faked wall #2 and cost ~3 sessions). **The
  refusal to build on an unverified vtable slot was correct; ALWAYS discriminate a candidate slot against unrelated
  objects' vtables before believing it.**
- ★ **VERIFIED: the `IEnhancedInputSubsystemInterface` vptr is at `subsystem+0x38`** (multiple inheritance:
  `UEnhancedInputLocalPlayerSubsystem : ULocalPlayerSubsystem, IEnhancedInputSubsystemInterface`). Only two vptrs exist
  in `[0,0x100)`: `obj+0x00` -> vtable base+0x865C950 (primary/UObject; slot19 = the generic base+0xB9E1F0) and
  **`obj+0x38` -> vtable base+0x865CC30, slot19 = `base+0x4BDC3C0` (UNIQUE)**. Consistent with the exec thunk calling
  `[vtable+0x98]` on the interface-adjusted `this`. ⇒ **`AddMappingContext` impl = `base+0x4BDC3C0`** (strong, by
  construction + uniqueness), subsystem = `0x285C4460200`, interface ptr = `subsystem+0x38`.
- ⚠ **Disasm confirmation of `base+0x4BDC3C0` is BLOCKED: the page is NOT demand-decrypted (RPM/peek both fail).** This
  is NOT a tool artifact -- controls read fine on the SAME process: `execAddMappingContext` (base+0x4BFA590) and
  `ProcessInternal` (base+0x13454A0) both peek cleanly. Per the known anti-tamper behaviour (`.text` demand-decrypts on
  EXECUTION), an unreadable code page = **that code has never run this session** ⇒ a **5th independent corroboration of
  S80g** (the native add-site never executed). Chicken-and-egg: the page only decrypts once the code runs, which is the
  thing we are trying to cause. So the impl address stands on the vtable evidence, unconfirmed by disassembly -- **do not
  upgrade it to "verified by disasm" without a re-peek from a state where input HAS been set up.**
- ★★★ **PRACTICAL: the impl address is NOT NEEDED to CALL AddMappingContext.** The direct-thunk primitive calls
  `UFunction.Func` = the **exec thunk** `base+0x4BFA590`, which IS readable and is the normal path. The impl was only
  wanted for `callxref` (finding the add-site) -- and since the call is VIRTUAL (S80j), callxref cannot find
  vtable-dispatched callers anyway, AND the callers' own pages are likely still encrypted too. **⇒ Drop the callxref
  route. To find the IMC, use `usmapdump findptr <base+0x4BDC3C0>` (locate the vtables) or -- better -- go back to the
  ASSET side (regenerate a complete AssetRegistry.bin; `candidates Mission` is the canary), or simply TRY calling
  `AddMappingContext` once an IMC is loaded.**

**S80l -- "REGENERATE THE AR" IS IMPOSSIBLE AND WAS A FALSE PREMISE (mine, S80i/j/k). The Mission canary FAILS, and the
diagnosis is the extractor's AR PARSER (or cooked-AR class stripping) -- NOT a missing/partial file.**
- ★ **`extractor wherefile AssetRegistry` -> there is EXACTLY ONE `AssetRegistry.bin` in the whole game:**
  `Loki/AssetRegistry.bin`, **36,505,474 bytes**, in `pakchunk0-WindowsClient.pak` (unencrypted). That is byte-for-byte
  the file already at `out/AssetRegistry.bin`. ⇒ **It cannot be "regenerated more completely" -- it IS the game's own
  registry, extracted verbatim.** My S80i/j/k "regenerate a complete AssetRegistry.bin" plan was based on a false
  premise; DO NOT retry it. (The only other hit is an unrelated editor .uplugin descriptor.) My "GameFeature plugins
  ship their own ARs" hypothesis is also WRONG for this build -- there are no per-plugin ARs in the paks (even though
  `LokiGameFeatureData` assets exist).
- **`assetregistry classes` -> only 98 unique AssetClass values across 103,841 FAssetData.** They are almost entirely
  ENGINE asset types (Texture2D/StaticMesh/SkeletalMesh/SoundWave/Blueprint/Material/World/WidgetBlueprint/Anim*/Niagara/
  Ak*...) plus just **7 custom**: `LokiGameFeatureData`, `LokiMapIconDataAsset`, `LokiPhysicalMaterial`,
  `LokiSpellBlueprint`, `LokiSpellBlueprintGeneratedClass`, `BP_BiomeLighting_Data_C`, `BP_PaginatedModalData_C`.
  **There is NO generic `DataAsset`/`PrimaryDataAsset` family, NO `LokiDataAsset_Mission`, NO `InputMappingContext`.**
- ★★★ **THE CANARY FAILS, CONFIRMED:** `LokiDataAsset_Mission` is absent from the 98 -- yet missions demonstrably WORK in
  this project (`docs/missions-progression-hookup.md`, the whole missions page renders from those assets). So the AR (as
  our extractor reads it) is provably missing an asset family we KNOW ships. **⇒ Any `candidates InputMappingContext` /
  `candidates Input` = 0 from this AR is UNINFORMATIVE. The AR route for finding the IMC is CLOSED until the parser is
  fixed.** Corroborating parser smell: it reports **"103,841 FAssetData / 0 DependsNode / 0 PackageData"** -- it does not
  read the DependsNode/PackageData sections at all, so its coverage of the FAssetData class field is also suspect.
  Likely causes to investigate (in `tools/extractor/extractor/Program.cs`, the `assetregistry` reader): (a) the cooked AR
  stores DataAsset entries in a section/format the reader skips; (b) UE5.4 AR version handling; (c) cooked-AR class
  stripping (Epic strips FAssetData for classes not in the AR write allowlist -- if so the data is genuinely NOT in the
  file and NO parser fix helps).
**⇒ ROUTE RE-RANK for finding the IMC (the AR route is out):**
1. ★ **`extractor namesall InputMappingContext`** -- harvests the combined unique NameMap vocabulary across assets; finds
   a TYPE even where path- and class-searches fail. Cheapest untried option.
2. ★ **The LIVE game's in-memory AssetRegistry / AssetManager** -- the client HAS the real registry loaded. Walk it via
   RPM (the `LokiAssetManager` work + `GetPrimaryAssetIdList` primitive already exist, S79 Phase 1 / missions), and ask
   IT for Input-ish primary assets. Bypasses the broken offline parser entirely.
3. Fix the extractor's AR parser (only worth it if (c) above is false).
4. Pragmatic: an IMC may not be a PRIMARY asset at all -- it may be a hard reference inside `BP_LokiPlayerController_Dev_C`
   or a settings/config object. `ubergraph_dump.py` the BP_Dev PC's graph (we have TWO live instances we spawned:
   0x2868B5ED8A0 / 0x28690832770) and look for `InputMappingContext` operands -- the S80g global BP scan only proved
   nobody CALLS AddMappingContext, NOT that nobody REFERENCES an IMC asset.

**S80m -- ★★★ S80g IS NOW DOUBTFUL AND MAY BE FAKE WALL #7 (MINE). Evidence now points to SUPERVIVE NOT USING MAPPING
CONTEXTS AT ALL -- in which case "AppliedInputContexts is EMPTY" is the NORMAL state, not a gap.** Retract S80g's
confidence; do NOT build on it.
- **Live FNamePool query** (`usmapdump nameid`, read-only -- the pool holds every FName the process ever made, incl. AR
  vocabulary): `MappingContext` -> 20 hits, **ALL of them ENGINE/EnhancedInput reflection identifiers**
  (`/Script/InputMappingContext`, `MappingContexts`, `RegisteredMappingContexts`, `DefaultMappingContexts`,
  `bEnableDefaultMappingContexts`, `DefaultWorldSubsystemMappingContexts`, `MappingContextRedirects`,
  `MappingContextRegisteredWithSettings__DelegateSignature`) -- **not one SUPERVIVE/Loki asset name**. (`nameid IMC` ->
  20 hits, ALL false positives: case-insensitive substring inside `NiagaraS-imC-ache`/`NDIMemoryBuffer...`. Ignore.)
- ★ **`UEnhancedInputDeveloperSettings` (the engine's auto-apply route) is EMPTY:** the sole instance is the CDO
  `Default__EnhancedInputDeveloperSettings` (0x28505198BE0): `DefaultMappingContexts @+0x40 Num=0`,
  `DefaultWorldSubsystemMappingContexts @+0x50 Num=0`, `bEnableDefaultMappingContexts @+0xE8 = True` (enabled, but with
  NOTHING to apply), `bEnableUserSettings=False`, `bEnableWorldSubsystem=False`. ⇒ the engine's default-IMC add-site
  never had anything to add.
- ★★★ **THE CONVERGING READ: SUPERVIVE probably does not use IMCs AT ALL.** Every independent probe says the same:
  0 IMC assets loaded; 0 IMC assets found by ANY search; 0 of 14,921 BP fns call `AddMappingContext`;
  `DefaultMappingContexts` empty; no IMC-typed property on hero/PC; and `AddMappingContext`'s impl page has NEVER been
  demand-decrypted (S80k) i.e. **that code has never executed in this process**. A game with a custom keybind UI
  plausibly uses `UEnhancedInputComponent` ONLY as the component class and drives input through a bespoke Loki system
  (direct `BindAction` with `UInputAction`s, or a fully custom key->ability map).
  **⇒ If so, "AppliedInputContexts EMPTY" is the NORMAL state for this game and is NOT why WASD fails. S80g would be
  FAKE WALL #7 -- authored by me -- and the S80h/i/j/k/l chase after an IMC asset was chasing a thing that does not
  exist.** I am flagging this rather than leaving S80g standing as "the one real gap".
- ⚠ **UNRESOLVED / DO NOT GUESS:** what DOES drive SUPERVIVE input is now genuinely UNKNOWN. Counter-evidence to the
  "custom system" read: `EnhancedActionMappings @+0x5B0` (the flattened list `UEnhancedPlayerInput` rebuilds FROM
  applied IMCs) is ALSO empty -- consistent with either story.
**NEXT (identify the mechanism -- do NOT assume IMC):**
1. ★ `usmapdump nameid SUPERVIVE-Win64-Shipping.exe InputAction` / `IA_` / `InputConfig` / `Keybind` / `LokiInput` --
   if `UInputAction` assets exist, they use Enhanced Input actions (bound WITHOUT contexts); if none, it is fully custom.
2. ★ Census the LIVE `EnhancedInputComponent` on the hero (`0x28600E813C0`) / the PC's (`PC_InputComponent0`): read
   `UInputComponent`'s binding arrays (`ActionBindings`/`AxisBindings`) and `UEnhancedInputComponent`'s
   `EnhancedActionEventBindings` -- **if bindings EXIST but no IMC, the mechanism is BindAction-direct and the missing
   piece is a key->action source, not a context.** Use `tools/re/comp_census.py`-style reflection. Cheap, read-only.
3. Only after the mechanism is IDENTIFIED, decide what to drive. **The real question was never "which IMC" -- it is
   "how does this game turn a keypress into a hero action". Answer THAT first.**

**S80n -- ★ INPUT BINDINGS EXIST on the hero's EnhancedInputComponent (while AppliedInputContexts is EMPTY). The
mechanism question is now SHARP and one read from an answer.**
NB **reflection CANNOT see these**: `UInputComponent::ActionBindings` and `UEnhancedInputComponent::
EnhancedActionEventBindings` are **plain C++ TArrays, NOT UPROPERTYs** -- a reflection census returns NOTHING and that
silence must NOT be read as "no bindings" (that is the exact shape of fake walls #4 and #6). Method used instead: read
the UClass's `PropertiesSize@+0x60` (= 400/0x190 for `EnhancedInputComponent`) and scan the object's raw bytes for
TArray-shaped fields `{Data*, int32 Num, int32 Max}` with plausible values:
```
HERO PawnInputComponent0  0x28600E813C0  class=EnhancedInputComponent  PropertiesSize=400 (0x190)
  +0x130  TArray{Data=0x286A3F021C0 Num=1  Max=4 }
  +0x140  TArray{Data=0x28537065F00 Num=2  Max=4 }
a PC_InputComponent0      0x28601743340  same class
  +0xF0   TArray{Data=0x286802A8BC0 Num=8  Max=26}
  +0x130  TArray{Data=0x2868ACB1780 Num=10 Max=24}
  +0x140  TArray{Data=0x28603A34A00 Num=1  Max=4 }
```
`UEnhancedInputComponent`'s tail is `EnhancedActionEventBindings` / `EnhancedActionValueBindings` / `DebugKeyBindings`
⇒ **+0x130/+0x140 are the binding arrays and they are POPULATED.** So `SetupPlayerInputComponent` DID run and DID bind
actions on the hero -- more evidence that S79 4g's `ClientRestart` did real work.
★★★ **THE MECHANISM IS STILL UNRESOLVED -- DO NOT GUESS. Two readings BOTH survive this evidence:**
- **(a) Custom key source:** SUPERVIVE binds actions directly and maps keys via a bespoke Loki system; no IMC is ever
  used ⇒ **"AppliedInputContexts EMPTY" is NORMAL and S80g IS fake wall #7 (mine).**
- **(b) Stock Enhanced Input:** bindings without an applied IMC never FIRE (nothing maps key -> action) ⇒ the IMC really
  is missing and S80g stands.
**⇒ THE DECIDING READ (do this FIRST next session -- it is cheap, read-only, and settles S80g either way):**
dereference the `+0x130` / `+0x140` entries on the hero's IC (`0x28600E813C0`).
`FEnhancedInputActionValueBinding` / `FEnhancedInputActionEventBinding` each hold a `const UInputAction* Action`
(the event array is `TArray<TUniquePtr<...>>` so entries are POINTERS to heap bindings -- deref once more).
Read each entry's `UInputAction*` and take its **class name**:
- class == `InputAction` (or a Loki subclass of it) ⇒ stock Enhanced Input ⇒ reading (b) ⇒ hunt the key source
  (an IMC, or whatever Loki uses to feed `EnhancedPlayerInput::InputKey`).
- class == some Loki-custom type / not an InputAction ⇒ reading (a) ⇒ **S80g retracted; input is NOT IMC-gated** and the
  real question becomes what feeds those bindings.
Also cheap + decisive in the same pass: `usmapdump nameid SUPERVIVE-Win64-Shipping.exe InputAction` -- if `UInputAction`
ASSETS exist in the FNamePool, reading (b) gains a lot; if there are none at all, (a) does.
**Ground truth for the whole input thread: `AppliedInputContexts` EMPTY on all 3 EnhancedPlayerInputs; 0 IMC assets
anywhere; 0/14,921 BP fns call AddMappingContext; DefaultMappingContexts EMPTY; AddMappingContext's impl page never
demand-decrypted (never executed); BUT the hero's EnhancedInputComponent HAS bindings.**

**S80o -- ★ RETRACTION OF S80n (my own false positive, caught one turn later). "The hero's EnhancedInputComponent HAS
bindings" is NOT ESTABLISHED. The deref found NO `UInputAction`.**
- Dereferenced the hero IC (`0x28600E813C0`) arrays `+0x130` (Data=0x286A3F021C0, Num=1) and `+0x140`
  (Data=0x28537065F00, Num=2), plus one level of indirection, scanning for anything resolving to a UObject
  (in-module vtable + a class ptr @+0x18 whose FName resolves): **NOTHING resolved. No `UInputAction`. No UObject at
  all.** The only hit anywhere was on the PC IC (`+0x28 -> ByteProperty, class=None`) which is an **FField false
  positive** (FFields also have a vtable and a ptr at +0x18), not a binding.
- ★★★ **WHY S80n WAS WRONG (the method failure, worth remembering): I found byte patterns shaped like
  `{ptr, int32 Num, int32 Max}` and INFERRED from UE layout knowledge that `+0x130`/`+0x140` were
  `EnhancedActionEventBindings`/`EnhancedActionValueBindings`. ANY struct with a pointer followed by two ints matches
  that shape.** The "TArray-shaped scan" identifies a SHAPE, never a FIELD. I reported the inference as fact. ⇒ **The
  offsets are unverified; the arrays may not be binding arrays at all.** This is the same error class as the six tool
  bugs this session -- only this time it produced a false POSITIVE ("bindings exist") instead of a false wall.
- **Honest status of the whole input thread: UNRESOLVED, and BOTH S80g (the "real gap") and S80n ("bindings exist") are
  now UNVERIFIED.** What still stands on solid, multiply-confirmed measurement: `AppliedInputContexts` EMPTY on all 3
  `EnhancedPlayerInput`s; `EnhancedActionMappings` EMPTY; 0 IMC assets anywhere (loaded, AR, FNamePool);
  0/14,921 BP fns call `AddMappingContext`; `DefaultMappingContexts` EMPTY; `AddMappingContext`'s impl page NEVER
  demand-decrypted (never executed). Everything BEYOND that -- what the game uses instead, and whether anything is
  actually missing -- is **unknown**.
**⇒ NEXT, and do it PROPERLY this time (no layout guessing):**
1. ★ **Get the REAL `UEnhancedInputComponent` layout instead of guessing offsets.** Options: (a) `usmapdump extract` /
   the `mappings.usmap` -- but NB it only carries UPROPERTY-reflected fields and these bindings are PLAIN C++ members,
   so it will NOT have them; (b) **disassemble `UEnhancedInputComponent::BindAction`/`GetActionValue` (find via
   `usmapdump nameid`/vtable) and read the offsets IT uses** -- that is ground truth and immune to layout guessing;
   (c) find a KNOWN-GOOD reference: bind something and diff, or inspect a stock UE 5.4 build's layout.
2. ★ Independently: `usmapdump nameid SUPERVIVE-Win64-Shipping.exe InputAction` / `IA_` -- **if there are no
   `UInputAction` assets ANYWHERE, then Enhanced Input actions are not used at all**, which settles the mechanism
   question from the asset side without needing any component layout.
3. Only once the mechanism is IDENTIFIED (not inferred), decide what to drive. **The question remains "how does this
   game turn a keypress into a hero action" -- and after S80g/S80n, the answer must come from a MEASUREMENT (a
   disassembled offset, a resolved class name), never from a plausible-looking byte pattern.**

**S80p -- ★★★ MECHANISM FOUND (directionally): SUPERVIVE HAS A CUSTOM LOKI INPUT SYSTEM. S80g ("no mapping context" =
the one real gap) is almost certainly FAKE WALL #7 -- MINE -- and is hereby RETRACTED.**
`usmapdump nameid SUPERVIVE-Win64-Shipping.exe InputAction` (live FNamePool, read-only) -> 40 hits in 3 clean groups:
- ★★★ **LOKI-CUSTOM (the finding):** `LokiInputActionIdentifier`, `LokiUniqueInputActionRule`, **`ListenForInputAction`,
  `StopListeningForInputAction`, `IsListeningForInputAction`, `StopListeningForAllInputActions`,
  `SetInputActionPriority`, `SetInputActionBlocking`** -- a bespoke **listener / priority / blocking API**. This is NOT
  Enhanced Input's `BindAction` model.
- **CommonUI (menus):** `CommonInputActionDataBase`, `UIInputAction`, `CommonInputActionDomain`,
  `CommonInputActionDomainTable`, and the ONLY real asset path in the whole pool:
  **`/Game/Loki/UI/Input/DT_InputActionData_Menus`** (a **DataTable**, CommonUI-style input action data -- note: MENUS,
  so a gameplay equivalent likely exists elsewhere).
- **Engine EnhancedInput:** only reflection vocabulary (`InputAction`, `EnhancedInputActionValueBinding`,
  `Conv_InputActionValueTo*`, `MakeInputActionValue`, ...) -- the TYPE NAMES existing, nothing more.
- **NO `IA_*` assets. NO IMC assets.** (Consistent with every other probe.)
⇒ **CONCLUSION: input is driven by a Loki-custom system (identifiers + DataTables + a Listen/Priority/Blocking API), NOT
by IMC/BindAction. Therefore `AppliedInputContexts` EMPTY is the NORMAL, EXPECTED state for this game and is NOT why
WASD fails.** S80g's "first real gap" was me mis-reading a normal state as a missing step, then spending S80h-S80o
chasing an IMC asset **that does not exist**. **RETRACTED. Do not resume the IMC hunt.**
⇒ **REVISED TALLY: 7 investigated "walls" -> 7 measurement/tool errors, 0 game-imposed limits** (6 inherited from the
S72-S79 record + S80g authored by me), plus S80n (a false POSITIVE, retracted in S80o).
**NEXT (a real, concrete lead at last -- and MEASURE, do not infer):**
1. ★ **Find the class that owns `ListenForInputAction` / `SetInputActionPriority`** -- that is the entry point to
   SUPERVIVE's actual input system. Use `tools/re/find_func.py` (scans GUObjectArray for UFunctions by substring, prints
   the owning class + BP/native) or `tools/re/ufunc_survey.py` on the hero/PC class chains with needle `InputAction`.
   Cheap, read-only, no injection. **That class is the thing to drive -- not `AddMappingContext`.**
2. Then `ubergraph_dump.py` / `disasm_live.py` whatever registers the gameplay listeners, and find the gameplay
   counterpart of `DT_InputActionData_Menus` (try `nameid DT_InputAction` / `nameid InputActionData`).
3. Only then decide what to call. Remember S80n: **a byte pattern is not a field, and a plausible name is not a
   mechanism.** Confirm by resolved class name or a disassembled offset.

**S80q -- ★★★★★ THE INPUT MECHANISM, FOR REAL THIS TIME (measured, not inferred): SUPERVIVE uses LEGACY FName-based
InputAction events, and they live ONLY on the BP PlayerController classes -- the DS client's ACTIVE PC (native
`LokiPlayerController`) has ZERO of them. This is S79's wall #2, confirmed from the input side, and it precisely
characterizes the Phase-3/4 tension.**
- **First: S80p was WRONG and is CORRECTED.** `ListenForInputAction`/`SetInputActionPriority`/`SetInputActionBlocking`/
  `StopListeningForInputAction` are **stock engine `UUserWidget` UMG functions** (legacy FName input), NOT a bespoke
  Loki API -- `find_func.py` shows them owned by `UserWidget`. I saw them in the same `nameid` block as the Loki names
  and misattributed them. (`LokiInputActionIdentifier` / `LokiUniqueInputActionRule` ARE real, but they are merely
  `ScriptStruct`s in `/Script/Loki` -- data types, not an entry point.)
- ★★★ **MEASURED (`find_func.py 48788 <base> inputaction` -> 137 matches). Owner tally:**
```
  39  BP_LokiPlayerController_C        <- InpActEvt_*_K2Node_InputActionEvent
  25  BP_LokiSpectator_C
  24  Comp_PlayerController_Emotes_C
  13  CommonButtonBase                 (UI)
   8  EnhancedInputLibrary             (engine lib -- reflection only)
   6  UserWidget                       (engine UMG)
   6  BP_LokiPlayerController_Code_C
   3  CommonActionWidget               (UI)
  --  LokiPlayerController (NATIVE)    <- ***ABSENT ENTIRELY: ZERO input events***
```
  The events are `InpActEvt_<Name>_K2Node_InputActionEvent`: Sprint, Ping, Recall, Use, ZoomCameraIn/Out, Toggle Map,
  ToggleScoreboard, ToggleHUD, ToggleAbilityOverlay, SmartZoom, OptionalAbility, PlaceSpray, OpenGlobalShop,
  LookAtCapturePoint, ShowCheats, ShowVOPlayer, UseUtilitySlot1/2, UpgradeSpell_{Main,Secondary,Ultimate,Dash,DodgeRoll},
  UpgradeEquipment{1,2,4,5,Boots}, ...
- ★★★ **`K2Node_InputActionEvent` is the LEGACY UE input node** -- FName-based `InputAction` events bound via
  `UInputComponent::BindAction(FName, ...)`, keys mapped from config. **NOT Enhanced Input. NOT IMCs.** ⇒ **This is WHY
  there are no IMC assets: the game never needed any.** The `EnhancedInputComponent`/`EnhancedPlayerInput` classes are
  present because UE5.4 defaults to them, but SUPERVIVE drives gameplay input through the legacy action path.
  **S80g is now conclusively dead** (fake wall #7, mine) -- and so is the entire S80h-S80o IMC hunt.
- ★★★★★ **THE STRUCTURAL RESULT (this is REAL -- not an artifact):**
  * **RENDER/CAMERA follows the NATIVE PC** (S79 4d: the view target only held once `nativePC->Pawn == hero`).
  * **INPUT EVENTS exist ONLY on the BP PC** (`BP_LokiPlayerController_C` 39 + `_Code_C` 6 + Emotes comp 24).
  * S79 4d picked the native PC ⇒ **got the camera, lost input.** S79 Phase 3/4 used `BP_LokiPlayerController_Dev_C`
    (inherits the 39 events) ⇒ **would have input, but no camera.**
  ⇒ **The two halves of a playable hero currently live on DIFFERENT PlayerController objects.** That is not a wall; it is
  a coherent trade-off with an untried resolution -- **S79's own candidate lever (c): run the BP_Dev PC's local-player
  init (`SpawnPlayerCameraManager` / `InitInputSystem`) so the swap carries the RENDER state too**, then swap
  `LocalPlayer->PlayerController` to the BP_Dev PC (the S79 Phase-3 swap ALREADY HELD for 10s with no revert) and
  hand it the hero.
**NEXT:** (1) verify the PC class chain (`LokiPlayerController` -> `BP_LokiPlayerController_Code_C` ->
`BP_LokiPlayerController_C` -> `BP_LokiPlayerController_Dev_C`?) with `comp_census.py`/`ufunc_survey.py` -- confirm
`BP_Dev` really inherits the 39 events. (2) On the S79-spawned BP_Dev PC (0x28690832770), find + call the local-player
init natives (`SpawnPlayerCameraManager`, `InitInputSystem`, `SetupInputComponent`) via `CallNative`/`CallBP`. (3) Re-do
the Phase-3 swap and check BOTH camera AND WASD. **The pieces are all built; this is an assembly problem now.**

**S80r -- ★★★★★ THE WHOLE THREAD RESOLVES: `APlayerController::SetPlayer()` is the ONE lever, and S79 Phase 3 BYPASSED
it. The BP_Dev PC inherits all 45 input events; the active native PC inherits ZERO. This is an assembly problem now.**
- ★ **CLASS CHAIN VERIFIED (live):**
```
BP_LokiPlayerController_Dev_C            <- the class S79 Phase 2/3 SPAWNED and SWAPPED IN
  <- BP_LokiPlayerController_C           <- ***39 InpActEvt_*_K2Node_InputActionEvent***
  <- BP_LokiPlayerController_Code_C      <- ***6 more***
  <- LokiPlayerController_AS             (NB "_AS" => likely Unreal ANGELSCRIPT -- worth knowing, parked)
  <- LokiPlayerController                <- ***THE ACTIVE DS-CLIENT PC: ZERO input events***
  <- LokiBaseController <- PlayerController <- Controller <- LokiActor <- Actor <- Object
```
  ⇒ **`BP_LokiPlayerController_Dev_C` INHERITS all 45 input events. The active native PC sits 4 levels BELOW them and
  inherits none.** Both S79-spawned BP_Dev PCs are STILL ALIVE this session: **0x2868B5ED8A0** (Phase 2) and
  **0x28690832770** (Phase 3). Native PC = 0x285752F50B0.
- ★★★ **THE LEVER — `APlayerController::SetPlayer(UPlayer*)`** runs the ENTIRE local-player init in one call:
  `InitPlayerState()` -> **`SpawnPlayerCameraManager()`** -> `ResetCameraMode()` -> **`InitInputSystem()`** ->
  `UpdateStateInputs()` -> `ReceivedPlayer()`. **S79 Phase 3 raw-wired `L+0x38 = devPC` + `devPC+0x458 = L` and thereby
  BYPASSED `SetPlayer()` COMPLETELY.** ⇒ **That is EXACTLY why S79 4b/4c observed "the pointer swap held but the
  render/input pipeline did not follow"**: the swapped-in PC never got a `PlayerCameraManager` (no camera) and never had
  `InitInputSystem()` run (no input). The S79 doc even guessed this ("our BP_Dev PC likely has no PlayerCameraManager
  ... never ran normal PC init" -- candidate lever (c)); it is now CONFIRMED as the mechanism, not a guess.
- ⚠ **`SetPlayer`/`InitInputSystem`/`SpawnPlayerCameraManager`/`SetupInputComponent` are PLAIN C++ VIRTUALS, NOT
  UFUNCTIONs** -- `ufunc_survey.py` on the BP_Dev PC finds ONLY `ClientRestart` (native+0x3C5F990) and
  `ClientRetryClientRestart` (native+0x3C5FA20). **Their absence from reflection does NOT mean they don't exist** (the
  walls-#4/#6 trap). ⇒ They need NATIVE addresses: get them from `APlayerController`'s vtable (discriminate the slot
  against unrelated objects -- the S80k lesson), or by disassembling `ULocalPlayer::SpawnPlayActor` /
  `ULocalPlayer::SwitchController` which call `SetPlayer`.
**⇒ THE PLAN (all pieces already exist; this is ASSEMBLY, not research):**
1. Resolve `APlayerController::SetPlayer` natively (vtable slot on the PC, verified by discrimination + disasm --
   `disasm_live.py`; NB pages may be encrypted until executed, per S80k).
2. Call `SetPlayer(devPC, LocalPlayer)` on the S79 BP_Dev PC (0x28690832770) via the direct-thunk primitive / a raw
   native call. Expect it to spawn a PlayerCameraManager + run InitInputSystem on a PC that ALREADY has the 45 events.
3. Redo the Phase-3 swap (`L->PlayerController = devPC`) -- **it ALREADY HELD 10s with no revert** (S79 Phase 3) -- and
   hand it the hero (S79 Phase 4 `Possess` worked on the BP_Dev PC: `PC->Pawn` held 10s).
4. Check BOTH camera AND WASD. The hero already: exists, is possessed-able, is Alive, has a MESH
   (`SK_Assault_Default_LOD1`, rendering), and has a fully-configured SPRING ARM (`TargetArmLength=3020`).
5. Reposition it first -- it drifted off the island over the void (S79 4h).
**HONEST NOTE ON THE INPUT DETOUR:** S80g->S80o (the "no mapping context" gap + the IMC hunt) was ALL WRONG -- SUPERVIVE
uses LEGACY FName input, so IMCs never existed. The correct question was "which class owns the input events", answerable
in ONE `find_func.py` call. Fake wall #7 was mine.

**S80s -- `SetPlayer` vtable slot: NOT RESOLVED (honest negative). Two candidates found and BOTH REFUTED by disasm.
NOTHING was called. Do not build on either address.**
Method (reusable): `APlayerController::Player @ +0x458` is known (S79 3a), so `SetPlayer` MUST write it -> scan the
native PC's vtable (`PC 0x285752F50B0` -> vtable **base+0x8A1AEE0**; hero/Actor vtable base+0x89A6DA0 used to discard
slots SHARED with a plain Actor), disassemble each PC-specific slot and look for a WRITE to `[reg+0x458]`.
- **Slot 183 (base+0x3C33230)** -- `lea rbx,[rcx+0x458]` then `cmp [rbx],0`: only READS Player, takes no `rdx`/InPlayer,
  and operates on `[rbx+0x13c8]`/`[rbx+0x140]`. **REFUTED** -- the `lea` was just taking the address to test it.
- **Slot 153 (base+0x3C421D0)** -- the ONLY slot in 280 that WRITES `qword ptr [reg+0x458]`. **REFUTED by reading it:**
```
  mov rdi,rdx                 ; rdi = InPlayer
  mov [rip+0x635d44c],rdi     ; stash InPlayer in a GLOBAL
  xor edi,edi                 ; *** rdi = 0 ***
  mov rax,[rbx+0x458]         ; old Player
    mov rcx,[rax+0x38]        ; oldPlayer->PlayerController (matches S79 3a's +0x38)
    cmp rcx,rbx / sete cl
    mov [rax+0x38],rdi        ; oldPlayer->PlayerController = 0
  mov [rbx+0x458],rdi         ; *** this->Player = 0  -- writes ZERO, not InPlayer ***
  mov [rbx+0x640],rdi         ; another field = 0
```
  ⇒ a **TEARDOWN** path (`OnNetCleanup`/`Destroyed`-shaped), NOT `SetPlayer`. It only matched the filter because `rdi`
  was zeroed before the write. **(Useful bycatch: this CONFIRMS `Player@+0x458` and `ULocalPlayer->PlayerController@+0x38`
  from a second, independent direction -- the S79 3a offsets are solid.)**
⇒ **CONCLUSION: `SetPlayer` is NOT among the first 280 vtable slots as a direct `[reg+0x458]` writer.** Possible reasons
(untested, do NOT assume): (a) the `TObjectPtr<UPlayer>` assignment goes through a helper CALL rather than an inline
`mov`; (b) `SetPlayer` is beyond slot 280; (c) it is not virtual / got inlined in this build; (d) it writes via a
different register form my filter missed (e.g. a 32-bit or `lea`+`mov [rbx],`).
**NEXT (better approach -- find it by its CALLER, not by pattern-matching the vtable):**
1. ★ `ULocalPlayer::SwitchController(APlayerController*)` and `ULocalPlayer::SpawnPlayActor(...)` both call
   `PC->SetPlayer(this)`. Locate either (`usmapdump nameid`/`strings` for `SwitchController`, or find `ULocalPlayer`'s
   vtable via the live LocalPlayer **0x28541940E00**), disassemble it, and **read the virtual call it makes on the PC**
   -- that gives SetPlayer's slot directly and unambiguously.
2. Or widen the slot scan past 280 AND accept indirect writes (match any `call` after `lea reg,[rcx+0x458]`).
3. **Then VERIFY by disasm before calling** (SetPlayer must: take rdx=InPlayer, write it to +0x458, and call several
   things incl. a `SpawnPlayerCameraManager`-ish and an `InitInputSystem`-ish). **Two candidates already looked right
   and were both wrong -- the pattern match is necessary but NOT sufficient.**
**Status: nothing was called; the live session is untouched by this step.**

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
