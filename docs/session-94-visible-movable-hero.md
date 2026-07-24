# Session 94 (2026-07-24) — a MOVABLE hero + camera in the force-open tutorial; the visible body characterized

Branch `dedicated-server-stub`, FORCE-OPEN tutorial route. Continues S93 (which proved the from-scratch mesh
*mechanism* but showed no clean on-screen body, no movement). This doc is the trial-and-error record; the paste-able
start prompt is `docs/next-session-prompt-s95.md`.

## TL;DR — result

**A movable hero now stands (well, floats) in the force-open tutorial world with a working top-down camera — the first
time this route produced actual playable movement.** USER-CONFIRMED live ("actual moveable gameplay"). The single
remaining gap is a VISIBLE body: the from-scratch `SkeletalMeshComponent` is built + attached + visible correctly, but
no mesh we can reach at force-open has loaded GPU/skeleton render data, so it draws nothing.

## The new shim: `RM_PLAY=22` (`tutorial_launch_play.dll`)

One PI-hooking shim that does the whole "visible + movable hero" pipeline (so there's no PI-hook contention with a
separate camera/puppet shim). New code in `tools/sigbypass-mod/tutorial_launch.cpp`: `ResolvePlay` / `DoPlay` /
`BuildHeroBody` / `FireRoninLoad`. Inject sequence: `fo → gft_ready_fix → sp → play`.

`DoPlay` (once): teleport the possessed hero to walkable ground (S75 CapturePoint `(-65,-1770,393)`, no `[SP]`
sky-lift) → `SetMovementMode(MOVE_Flying=5)` → fire the Ronin async-load → build the body when the mesh streams in.
`DoPlay` (each hit): `DoTopDownCam()` (camera follow, reused from S93) + `DoPuppet()` (WASD → CMC velocity, reused
from S75). Holds ~10 min so it's playable + screenshottable.

A 1-agent adversarial review of the new code PASSED all six checks (FTransform offset, buffer aliasing, `g_puppetInit`
suppression, global clobbering, null-guards, OOB) before the first launch.

## What got SOLVED (each user-confirmed live)

1. **Movement.** The S75 velocity-puppet moves the possessed hero. Confirmed multidirectional.
2. **Direction alignment.** The puppet writes WORLD-space velocity; the top-down camera is yawed −90°, so raw WASD felt
   misaligned / "single axis". Fix = `-DKPUPYAW=-90` rotates the WASD frame to the camera (W=−Y=screen-up, D=+X=right).
3. **Movement stability.** iter1 (Walking mode) crashed ~50s into movement: Sentry handler fired right on
   `UWorld::AddToWorld` for a new World-Partition cell — the S81 movement crash (CMC/mantle + cell-streaming). Fix =
   `SetMovementMode(MOVE_Flying=5)` in `DoPlay` init bypasses the Walking-mode ground-mantle chain. ⚠ Flying = no
   gravity, so the hero FLOATS at the teleport Z (cosmetic — a periodic ground-snap or a stability-safe Walking variant
   fixes it). The `FudgeMantling`/`CursorCharacterAim` "toggles not ready" spam PERSISTS in Flying (it isn't
   movement-mode-gated — the empty toggle-ARRAY wall, S88) but is now harmless.
4. **Camera.** `RM_TOPDOWNCAM` reused inside `RM_PLAY`; brought closer (`-DKCAMUP=1000 -DKCAMBACK=550 -DKCAMPITCH=-58`).
   Renders the tutorial island top-down and follows the hero.

## The VISIBLE BODY — four approaches, one root cause (no render-data mesh)

`tools/re/probe_comp.py` (new) proved the from-scratch component is perfect: class `SkeletalMeshComponent`, mesh
assigned (@0x728), `AttachParent` = the hero's root `CapsuleComponent`, `RelativeLocation` (0,0,0), `bHiddenInGame=0`,
visibility bit set. It renders nothing because the mesh has no render data.

- **Resident placeholders** (`SK_KaijuCaster_Default` / `SK_Base_Wisp` / `SK_HeroPlatform_Default` — the only SK_*
  resident at force-open) are **header-only** (no GPU/skeleton data). tick-OFF → no render (stable). tick-ON +
  `SetAnimationMode(SingleNode)` → still no render + CRASH (ticking an incomplete mesh faults). NOTE: SingleNode DID
  avoid the S93 AnimBP-on-wrong-skeleton crash — that hypothesis was right — so the crash is the incomplete mesh, not
  the AnimBP.
- **Async-load** (new `FireRoninLoad`): built the `AsyncLoadPrimaryAssets` primitive into the shim. Signature confirmed
  via `DumpParams`: `AsyncLoadPrimaryAssets(WorldContextObject@0, TArray<FPrimaryAssetId> Assets@8{Data@8,Num@0x10,
  Max@0x14}, FStreamableDelegate OnLoadComplete@0x18, ReturnValue@0x28)` — **NO LoadBundles param**. Fired 7 candidate
  Ronin PAIDs; all resolved to valid types; the load fired clean. `find_named.py` over the live GUObjectArray afterward:
  the load made the Ronin cosmetics-bundle **PACKAGES** resident (`BP_HeroAsset_Ronin_C`,
  `BP_Ronin_Default_*_CosmeticsBundle`, `TX_CS_Portrait_Ronin`, `BP_Bark_Stomp_Ronin`) but **NOT** the mesh —
  `SK_Ronin_Default` doesn't exist as a resident object at all.

★ WHY (extractor): the Ronin body is delivered by a COMPONENT BP `BP_Ronin_DefaultSKMeshComponent_C`
(`/Game/Loki/Characters/Heroes/Ronin/Cosmetics/Default/BP_Ronin_DefaultSKMeshComponent`), NOT a raw
`SK_Ronin_Default` asset. So the mesh name was wrong AND loading the bundle package (a BP) doesn't pull the mesh's
render data.

## S95 next (see `docs/next-session-prompt-s95.md`)

Route 1 (chosen): find the actual `USkeletalMesh` referenced inside `BP_Ronin_DefaultSKMeshComponent_C` and
`LoadAsset_Blocking` it by soft path. Route 2: create the game's own `BP_Ronin_DefaultSKMeshComponent_C` via
`AddComponentByClass`.

## GOTCHAS (S94)

- `fo` inject crashes ~2/3 (documented) — budget relaunches. An early 3-survival streak was luck; later I hit 3 crashes
  in a row.
- The menu memory varies wildly between launches (582 MB – 5 GB) with the same `-NoHook`; not predictive of anything.
  In-world memory drops to ~600–760 MB (World-Partition streaming reshuffle as the hero moves), NOT a teardown.
- The per-poll `FindObjExact` (full ~188k-object scan) on the game thread is heavy; the async-load poll likely
  contributed to a late crash. S95: poll less often / cache the scan.
- `$pid` is read-only in PowerShell (use `$gpid`); Steam relaunches the game under a new pid (resolve the newest).

## New tools / build flags

- `tools/re/probe_comp.py` — an added component's render/attach state (class, mesh, AttachParent, RelativeLocation,
  visibility) via read-only RPM.
- `tutorial_launch.cpp` build flags: `KGROUNDX/Y/Z`, `KBODYZ`, `KMESHTICK`, `KANIMMODE`, `KFLYMODE`, `KNOMESH/KNOMOVE/
  KNOTELE`, `KLOADRONIN`, `KLOADWAITMS`, plus reused `KPUPYAW/KPUPSPEED/KCAMUP/KCAMBACK/KCAMPITCH`.

## ENV AT HANDOFF

- Config REVERTED to baseline (`forceTutorialMatch=false`, address `127.0.0.1:7777`). Nothing committed. Game exited.

---

# S94 PART 2 (iter5-16) — the mesh LOADS and the component BUILDS, but renders NOWHERE

Part 1 (above) ended with "the resident placeholder meshes have no render data". That was **half right**: the load was
solvable, and it got solved — but a correctly-loaded mesh on a correctly-built component still does not draw.

## SOLVED: loading Ronin's real body mesh (reusable)

- The Ronin body is **`SK_Ronin_Default_LOD1`** at `/Game/Loki/Characters/Heroes/Ronin/Modeling/Default/` — a HARD ref
  inside the component BP `BP_Ronin_DefaultSKMeshComponent_C` (found via extractor dump). It is **not** named
  `SK_Ronin_Default` and it lives under `Modeling/`, not `Cosmetics/` — which is why every earlier `FindObjExact` missed it.
- **`LoadMeshByPath`** (new): `KismetSystemLibrary.MakeSoftObjectPath(FString) -> FSoftObjectPath` then
  `LoadAsset_Blocking(TSoftObjectPtr) -> UObject*`. Synchronous, returns the loaded `SkeletalMesh` (process mem
  ~4.9 → 5.5 GB). Two ABI bugs had to be fixed to get there:
  1. **Native struct returns land in the RESULT buffer**, not at the params' `ReturnValue` offset (reading
     `g_gsbuf+0x10` yielded an empty path).
  2. **`TSoftObjectPtr` is `FWeakObjectPtr WeakPtr@0x0` + `FSoftObjectPath ObjectID@0x8`** — writing the path at +0x0
     clobbers the weak cache and `LoadAsset_Blocking` returns null. The path must go at **+0x8**.
- `AsyncLoadPrimaryAssets` (Loki) has **no LoadBundles param** (`WorldContextObject@0, Assets@8, OnLoadComplete@0x18,
  ReturnValue@0x28`), so it loads the cosmetics-bundle *packages* but never the mesh — that route cannot work.
- Verified healthy after load (`obj_fulldump`): valid Skeleton, **Materials Num=8**, LODInfo, PhysicsAsset, bounds.

## SOLVED: building the component two different ways

- Route 1 — bare `SkeletalMeshComponent` + `SetSkeletalMeshAsset(mesh)`.
- Route 2 — the game's OWN `BP_Ronin_DefaultSKMeshComponent_C` (mesh + materials + AnimClass in its CDO), created with
  `AddComponentByClass(..., bDeferredFinish=1)` so cloth/AnimBP can be switched off before
  **`FinishAddComponent(hero, comp, false, xform)`** registers it. All markers "ok".
- `probe_comp.py` confirms: class correct, mesh assigned, `AttachParent` = hero root capsule, RelativeLocation (0,0,0),
  world position == hero position, `bHiddenInGame=0`, visibility set.

## ELIMINATED BY DIRECT TEST — every one confirmed with live screenshots

| Hypothesis | Test | Result |
|---|---|---|
| Hero actor hidden | `SetActorHiddenInGame(false)` re-asserted every PI hit; **and** the same body on a STANDALONE actor | Neither renders ⇒ not the hero |
| Occluded in the drop-pod | hero + standalone actor teleported to **Z=2200 open air**, camera Z=3400 over the island | **Nothing at altitude** — and the selection RING vanished too, proving it is a ground-projected DECAL (why it showed on the pod while the body never did) |
| Cloth / anim / tick | cloth factory nulled, `SetAnimationMode(SingleNode)`, tick ON and OFF | No change (SingleNode *does* fix the S93 AnimBP crash) |
| **Fog of war** | `FogOfWarSceneView` + `FogOfWarPrimitiveCollector` both un-ticked + hidden | **Still nothing** ⇒ `IsFogOfWarVisibleToLocal==0` was a SYMPTOM of no deploy context, NOT the cause |
| FOW vision attrs | usmap: `FogOfWarRadius/Angle` are GAS attrs on `LokiAttributeSet`; scanned for the hero's set | **`attributeSet == 0x0`** — the force-open hero has no GAS attribute set at all |

## THE UNTESTED LAYER (next session starts here)

Every probe so far was **reflection-based**, which is structurally blind to `UPrimitiveComponent::SceneProxy`,
`bRegistered` and `bRenderStateCreated` — plain C++ members, no UPROPERTY. That is exactly where "component looks
perfect but never draws" lives. **Method: byte-diff our component against a level primitive that IS visibly
rendering** to locate those offsets, then check which one ours lacks. Also worth one cheap discriminator: attach a
plain **StaticMeshComponent with a level mesh** — if that doesn't render either, the failure is component-creation-wide
rather than skeletal-specific.

## GOTCHAS added this part

- `bDisableClothSimulation` / `bOwnerNoSee` / `bOnlyOwnerSee` are **bitfield bools sharing one byte** — writing the
  whole byte clobbers neighbouring render flags. (A real bug I introduced and then removed.)
- FOW statics do **not** live on `LokiFogOfWarStatics`; a class-scoped lookup returns `thunk=0`. Resolve them
  **globally by name** — new helper `ResolveFuncGlobal` (UFunction `Func@+0xE0`, `ChildProperties@+0x58`,
  `Outer@+0x28` → owning UClass → `Default__<Class>` CDO). Owners: `RegisterFogOfWarPrimitive` →
  `FogOfWarPrimitiveCollector`; `IsFogOfWarVisibleToLocal` → `LokiBlueprintLibrary`; `GetFogOfWarRadius/Angle` →
  `LokiCharacter`; `OnRep_FogOfWar*` → `LokiAttributeSet`; `GetFogOfWarSceneView` → `LokiGameState`.
- **Capture window**: force-open sessions die ~230-260s and the body used to build at ~215s, so there was almost no time
  to look. The resolve did **~18 full 188k-object scans** on the game thread; trimming ~8 brought it to **197s**. Cut
  more before the next visual test. Screenshot with Win+Shift+S / Steam F12 — do not alt-tab.

## New tools (all read-only RPM unless noted)

`tools/re/probe_comp.py` (component render/attach state), `tools/re/find_owner.py` (class + Outer chain for
name-matched objects), `tools/re/scan_strings.py` (ASCII+UTF-16 pattern scan of an image dump — how the FOW surface was
found). Shim: `LoadMeshByPath`, `ResolveFuncGlobal`, `FowRegister`/`FowDisable`/`FowMakeVisionSource`,
`FindAttrSetFor`, `CallNoArgAuto`, `BuildHeroBody(..., deferred)`; flags `KUSEBPCOMP/KTESTACTOR/KTESTDX/KFOWKILL/
KFOWATTR/KMESHPATH/KLOADRONIN/KFIREBUNDLE`.
