# Next session (S75) — chase HERO MOVEMENT (WASD) on the force-open tutorial hero

## TL;DR of the S74 breakthrough (what's DONE)
We broke the S68/S72 spawn+possess wall and got a **spawned, possessed, controllable, world-placed hero with a
proper top-down camera** in the live force-open tutorial. Working, user-confirmed:
- Spawn `BP_HERO_Ronin_C` via GameplayStatics + Possess (was crashing pre-S74; unblocked by the **S58 OUT/ref-param
  marshalling** now ported into `tutorial_launch.cpp`'s `CallNative` — `BuildOutParms` builds the `FFrame.OutParms`
  chain for `CPF_OutParm` params). `PC->Pawn` = the hero.
- Input engaged: **aim** (targeting ring tracks cursor) + **jump** (space) work.
- Camera: lifting the hero (gravity off + `K2_SetActorLocation` teleport up) pulls the camera above the terrain into
  the real SUPERVIVE top-down field view.
- Cosmetics: injected `CosmeticsAssetID = {HeroCosmeticsBundle, RoninDefault}` @hero+0x1FF0 + fired
  `OnRep_CosmeticsAssetID` → async-built `BP_Ronin_DefaultCosmeticsController_C`.

## What's NOT done / uncertain
1. **WASD movement does NOT work** (jump + aim DO). THIS SESSION'S GOAL.
2. **Ronin mesh not confirmed visible** — user saw the field but no clear character (the lift left the hero hovering
   at Z=1818, decoupled from clean framing). The cosmetics *controller* built, but verify the skeletal mesh is
   actually attached to the hero + reframe before trusting it renders.

## The recipe (how to reproduce)
Game already force-opened into LVL_Tutorial (PID was 55928, base 0x7FF6B54F0000 — RE-CHECK, may have changed).
- Build: `cd tools/sigbypass-mod && clang++ -shared -O2 -DKRUNMODE=RM_SPAWNPOSSESS tutorial_launch.cpp -o tutorial_launch.dll -lkernel32`
- Inject: `tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/tutorial_launch.dll`
- Marker log: `docs/tutorial-launch-marker.txt`. RM_SPAWNPOSSESS does spawn+sweep+possess+cosmetics+camera+lift.
- If the game isn't running: `.\configs\launch-redirect.ps1 -NoHook` (elevated, Steam up), then inject the force-open
  build (`-DKRUNMODE=RM_FORCEOPEN`) to reach LVL_Tutorial first, THEN the RM_SPAWNPOSSESS build.

## MOVEMENT INVESTIGATION PLAN (start here)
Leading hypothesis: movement is gated on SUPERVIVE's **feature-toggle / deploy locomotion flow**. Evidence: the
console spams `ULokiGameFeatureToggles::Get FudgeMantlingSouth / CursorCharacterAim / AttachAudioListenerToHero called
when feature toggles were not ready` continuously; jump/aim aren't gated the same way but ground movement is.
Steps:
1. **RE the movement input path**: disasm what WASD/move-input does on LokiHeroCharacter / LokiCharacterMovementComponent.
   Use `tools/re/class_funcs.py <PID> <BASE> LokiCharacterMovementComponent` + `... LokiHeroCharacter` filtered for
   move/input/locomotion/mantel/mantle. Find where it early-outs (like the S74 cheat/SpawnPlayer disasm method:
   `usmapdump disasm SUPERVIVE-Win64-Shipping.exe <thunk>` → find impl → find the gate).
2. **Feature-toggle readiness**: `ULokiGameFeatureToggles` is a STATIC store (NOT a UObject — 0 instances, per S73).
   Find the "are toggles ready" flag it checks + whether it's a settable global. If movement gates on it, flip it.
   (S73 DS work: toggles are round-gated — the server applies the match toggle set at round-start. Client-side force
   requires finding the static readiness flag.)
3. Note: the hero currently has **gravity OFF** (GravityScale=0 @CMC+0x1A0, set for the lift) and is hovering at
   Z=1818 — restore gravity + a clean on-ground spawn when testing real movement (the lift was a visibility hack).

## Key addresses / offsets (this build, base 0x7FF6B54F0000 — reverify)
- ProcessInternal hook: base+0x13454A0. Native-call primitive + BuildOutParms: in tutorial_launch.cpp.
- PC layout: PlayerState@+0x3C0, Pawn@+0x3F8, SpectatorPawn@+0x7D8, state@+0x160 & +0x3F0, DropPlaneComp@+0xC38,
  FinishDropPhaseHiding flag@+0xF28. Hero: CosmeticsAssetID@+0x1FF0, Mesh(ACharacter)@+0x450(NULL — mesh is cosmetic-driven).
  CMC GravityScale@+0x1A0.
- State machine: SwitchToPlayingState(idx 0x140, thunk 0x7FF6BA918600), IsSpectating (returns FALSE — no spectator gate).
- FNames: HeroCosmeticsBundle=0x1A572, RoninDefault=0xA12AB (id = block<<16 | off>>1).
- Default Ronin skin bundle name = `RoninDefault` (server/internal/menu/data/skins.txt:265).

## Memory: read [[supervive-tutorial-launch-status]] (S74 entries) + [[supervive-cheat-surface-inventory]] (the
## OUT-param marshalling origin) + [[supervive-dedicated-server-status]] (the DS route — the spawn+possess technique
## ports there via ds_hybrid.cpp, which already has the marshalling fix).

## Uncommitted code state: tools/sigbypass-mod/tutorial_launch.cpp has ALL the S74 work (RM_SPAWNPOSSESS build) +
## ds_hybrid.cpp has the ported marshalling fix + tools/re/cheat_enum.py + docs/session-74-cheat-enum-dump.txt.
## Consider committing before the fresh session so it's a clean checkpoint.
