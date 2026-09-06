# Next-session handoff (S95) — the VISIBLE hero body (movement + camera are DONE)

> ⛔ **CORRECTION (final S94) — FOG OF WAR IS *NOT* THE GATE. Neither is occlusion. Read the "FINAL STATE" block at the
> bottom of this file FIRST; everything below this line is the hunt, and its conclusions were superseded by direct tests.**
>
> ★★★★ (superseded) ROOT CAUSE CANDIDATE — THE FOG-OF-WAR VISION SYSTEM CULLS THE HERO.
>
> **Live proof:** `IsFogOfWarVisibleToLocal(hero) == 0` (FALSE), and `RegisterFogOfWarPrimitive(comp)` executes fine
> but **returns 0 = rejected**. Everything else is proven good: the component sits at the hero's exact world position,
> the loaded mesh is healthy (valid Skeleton, **8 materials**, LODInfo, PhysicsAsset, bounds), visibility flags set,
> registered via `FinishAddComponent`, camera confirmed over the hero. A **standalone test actor** 500 units away
> (`-DKTESTACTOR=1`) with the SAME body also rendered nothing ⇒ not hero-hidden, not attachment. SUPERVIVE simply does
> not render character primitives the FOW system doesn't consider visible, and force-open has no team/vision context
> (matches S91's "TeamState = 0 instances"). That is why only the ground-decal ring + world geometry ever appeared.
>
> **FOW API (RE'd live, ufunc_params.py).** Both are `Native|Static|BlueprintCallable`, and ⚠ must be resolved
> **GLOBALLY by name** — they do NOT live on `LokiFogOfWarStatics`, so a class-scoped lookup returns thunk=0:
> - `Bool RegisterFogOfWarPrimitive(PrimitiveComponent Component@0x0) -> Bool@0x8` — owner **FogOfWarPrimitiveCollector**
> - `Bool IsFogOfWarVisibleToLocal(Actor Target@0x0) -> Bool@0x8` — owner **LokiBlueprintLibrary**
> New reusable shim helper `ResolveFuncGlobal(name, &fn,&thunk,&child,&ctxCDO)` (UFunction `Func@+0xE0`,
> `ChildProperties@+0x58`, `Outer@+0x28` → owning UClass → `Default__<Class>` CDO) — works for ANY global UFunction.
> Other live FOW surface: `FogOfWarSceneView`, `FogOfWarPrimitiveCollector`, `FogOfWarStaticMeshComponent`,
> `GetFogOfWarSceneView`, `GetFogOfWarPrimitives`, `UnregisterFogOfWarPrimitive`, `IsFogOfWarVisibleToTeam`,
> `Get/OnRep_FogOfWarRadius`, `GetFogOfWarAngle`.
>
> **S95 — two routes to the visible body (everything else is already built):**
> - **(B) DISABLE fog of war for the local view — likely the cheapest win.** Find the live `FogOfWarSceneView` /
>   collector instance and force reveal-all (or stub the visibility query).
> - **(A) Make the hero FOW-VISIBLE** — give it a vision source/team. Investigate why `RegisterFogOfWarPrimitive`
>   returns false (the collector probably needs a valid team/vision), plus `IsFogOfWarVisibleToTeam` and the hero's
>   `FogOfWarRadius`/`FogOfWarAngle` properties.
>
> ⚠ Bug fixed in passing: `bDisableClothSimulation` / `bOwnerNoSee` / `bOnlyOwnerSee` are **bitfield bools sharing one
> byte** — writing the whole byte clobbers neighbouring render flags. Never poke them raw.

> ★★★ UPDATE (end of S94, after this doc's original body) — ROUTE 1 IS SOLVED for the LOAD; the render is the wall.
> The real Ronin mesh **SK_Ronin_Default_LOD1** now LOADS with render data via `LoadMeshByPath` (KismetSystemLibrary
> `MakeSoftObjectPath` + `LoadAsset_Blocking`; the working shim is `tutorial_launch_play.dll` built with
> `-DKMESHTICK=1`) and the from-scratch component BUILDS with it (cloth disabled, tick on). **But it STILL DOES NOT
> RENDER** — user screenshot confirms only the drop-pod + the hero's selection ring, no body. probe_comp.py proved the
> component is perfect (SkeletalMeshComponent, mesh assigned, attached to hero root, visible, not hidden), and mem
> jumps ~4.9→5.5GB confirming the mesh + render data loaded — yet no draw. So the wall is NOT load, NOT cloth, NOT
> tick, NOT visibility, NOT attach. It is a SUPERVIVE-specific render-proxy issue.
>
> ★ S95 ROUTE 2 (now the most promising) — build the game's OWN configured component instead of a bare one:
> `LoadMeshByPath` the CLASS `/Game/Loki/Characters/Heroes/Ronin/Cosmetics/Default/BP_Ronin_DefaultSKMeshComponent.BP_Ronin_DefaultSKMeshComponent_C`
> (LoadAsset_Blocking returns the BlueprintGeneratedClass), then `AddComponentByClass(thatClass)` — its CDO already has
> SkeletalMesh=SK_Ronin_Default_LOD1 + materials + AnimClass configured, and it registers/renders through the normal
> path (where the bare component apparently doesn't). ⚠ it also carries the AnimBP + cloth that crashed the bare path,
> so disable those on it too. ★ OTHER SUSPECTS for the bare-component non-render: (a) NULL material slots — SUPERVIVE
> meshes get materials from the cosmetics system, so the raw SK_ asset's component material slots may be empty →
> invisible; load + `SetMaterial` a material (or read the mesh's default materials). (b) render state never created —
> try an explicit RegisterComponent / MarkRenderStateDirty / RecreateRenderState (find a BP-callable equivalent).
> The load mechanism (`LoadMeshByPath`) is DONE and reusable for both. Everything else (movement/camera/stability) works.


Branch `dedicated-server-stub`. Continues S94. **S94 delivered a MOVABLE hero with a working top-down camera in the
force-open tutorial world (user-confirmed "actual moveable gameplay").** The one remaining piece is a **visible body**:
the from-scratch mesh component is built + attached + visible correctly, but every mesh we can reach at force-open lacks
loaded GPU/skeleton render data, so nothing draws. This handoff has the exact next step.

Read first: (1) this file, (2) memory `supervive-tutorial-launch-status` (tail = S94 iter2-4 — the full detail),
(3) `docs/session-93-objectives-camera-deploy.md` for the S93/S94 shim architecture.

## WHAT WORKS (S94, all live + user-confirmed) — do NOT re-litigate

- **Movable hero**: `RM_PLAY=22` (`tutorial_launch_play.dll`) teleports the possessed hero to ground, drives WASD →
  CMC velocity, camera follows. Multidirectional, intuitive (`-DKPUPYAW=-90` aligns WASD to the camera).
- **Stable movement**: `SetMovementMode(MOVE_Flying=5)` in `DoPlay` init bypasses the Walking-mode ground-mantle chain
  that crashed movement on World-Partition cell-streaming (S81). ⚠ side effect: no gravity → the hero FLOATS at the
  teleport Z (cosmetic — add a periodic ground-snap, or find a crash-safe Walking variant).
- **Top-down camera**: `RM_TOPDOWNCAM` reused inside `RM_PLAY`; tuned closer (`-DKCAMUP=1000 -DKCAMBACK=550 -DKCAMPITCH=-58`).
- Inject sequence: `fo → gft_ready_fix → sp → play`. (fo crashes ~2/3 on inject — budget relaunches; my S94 streak was luck.)

## THE ONLY WALL LEFT — a mesh WITH render data (precisely characterized)

The from-scratch `SkeletalMeshComponent` (`BuildHeroBody`) is **provably correct** — `tools/re/probe_comp.py` showed it
class=SkeletalMeshComponent, mesh assigned, AttachParent = hero root capsule, RelativeLocation (0,0,0), bHiddenInGame=0,
visible. It renders NOTHING because the mesh has no render data. Four approaches, all same root cause:
1. Resident placeholders (`SK_KaijuCaster_Default` etc. — the only SK_* resident at force-open) are **header-only** (no
   GPU/skeleton data): tick-OFF → no render; tick-ON+`SetAnimationMode(SingleNode)` → still no render + CRASH (ticking an
   incomplete mesh faults). SingleNode DID avoid the S93 AnimBP crash — good — so the crash is the incomplete mesh.
2. **AsyncLoadPrimaryAssets(7 Ronin PAIDs)** (new `FireRoninLoad` in the shim) FIRED clean (all PAIDs resolved) but only
   made the cosmetics-bundle **PACKAGES** resident (`BP_HeroAsset_Ronin_C`, `BP_Ronin_Default_*_CosmeticsBundle`) — NOT
   the mesh. `SK_Ronin_Default` does not exist as a resident object. The Loki `AsyncLoadPrimaryAssets` has **NO
   LoadBundles param** (`WorldContextObject@0, Assets@8, OnLoadComplete@0x18, ReturnValue@0x28`), so it can't request the
   mesh bundle.

★ KEY (extractor): the Ronin body is delivered by a **component BP** `BP_Ronin_DefaultSKMeshComponent_C`
(`/Game/Loki/Characters/Heroes/Ronin/Cosmetics/Default/BP_Ronin_DefaultSKMeshComponent`), NOT a raw `SK_Ronin_Default`.

## S95 NEXT STEPS (two untested routes to a render-data mesh)

1. **Load the mesh by soft path.** Deep-dive `BP_Ronin_DefaultSKMeshComponent_C` (extractor `dump` its full path) to
   find the USkeletalMesh asset it references, then `UKismetSystemLibrary::LoadAsset_Blocking(TSoftObjectPtr)` on it.
   Build the FSoftObjectPath param: `{ FTopLevelAssetPath{PackageName FName, AssetName FName}, FString SubPathString }`.
   Once resident (verify with `find_named.py`), assign it (tick OFF — a valid mesh renders its ref pose without ticking).
2. **Create the game's own mesh-component BP.** `AddComponentByClass(BP_Ronin_DefaultSKMeshComponent_C)` on the hero —
   its BP defaults reference the mesh + materials and its construction may trigger the load. Check if the class is
   resident after the S94 async-load (the bundle package is), or async-load it first.

DON'T: re-open the resident-placeholder path (no render data), the game's cosmetics CONTROLLER (0 instances, deploy-
walled), or Walking-mode movement (crashes on streaming — S81).

## RECIPE (unchanged from S94)

```powershell
# 0) re-arm force-open: interactive.go forceTutorialMatch=true + ConnectionDetails.address="" ; rebuild ags.
# 1) fresh game (Steam first): delete Loki.log ; .\configs\launch-redirect.ps1 -NoHook  (background; new pid)
# 2) wait TryUIReady + uptime>=100s ; resolve newest pid
# 3) inject fo ; wait "world up" / no HandleBeforeCrash (retry whole launch if it dies ~2/3)
# 4) inject gft_ready_fix -> sp -> play ; read docs\tutorial-launch-marker.txt
# build a play variant:  clang++ -shared -O2 -D_CRT_SECURE_NO_WARNINGS -DKRUNMODE=RM_PLAY <flags> tutorial_launch.cpp -o tutorial_launch_play.dll -lkernel32 -luser32
#   flags used S94: -DKMESHTICK=0 -DKANIMMODE=1 -DKPUPYAW=-90 -DKCAMUP=1000 -DKCAMBACK=550 -DKCAMPITCH=-58
```

## ENV AT HANDOFF

- Config REVERTED to baseline (`forceTutorialMatch=false`, address `127.0.0.1:7777`). Nothing committed (all S87-94 work
  uncommitted). `tutorial_launch_play.dll` on disk = the S94 async-load build.
- New this session: `tools/re/probe_comp.py`; `FireRoninLoad`/`BuildHeroBody`/`RM_PLAY` in `tutorial_launch.cpp`; build
  flags `KMESHTICK/KANIMMODE/KFLYMODE/KLOADRONIN/KLOADWAITMS/KGROUNDX/Y/Z/KBODYZ`.
- The user supplies screenshots (computer-use denied). PowerShell tool (not Bash); `dangerouslyDisableSandbox:true` for
  launch/inject; `[System.IO.File]::Delete` for logs; `$pid` is read-only (use `$gpid`).

---

# ⛔ FINAL STATE (end of S94) — READ THIS FIRST; it supersedes everything above

**The added SkeletalMeshComponent renders NOWHERE.** Every hypothesis above was tested to conclusion with live
screenshots and eliminated. Do not re-open them.

## Eliminated by direct test (do NOT re-chase)

| Hypothesis | Test | Result |
|---|---|---|
| Wrong / unloaded mesh | `LoadAsset_Blocking` of `SK_Ronin_Default_LOD1`; `obj_fulldump` of the loaded asset | Loads fine — valid Skeleton, **8 materials**, LODInfo, PhysicsAsset, bounds |
| Bad component setup | Built it TWO ways: bare `SkeletalMeshComponent` + `SetSkeletalMeshAsset`, and the game's own `BP_Ronin_DefaultSKMeshComponent_C` (deferred + `FinishAddComponent` "ok") | Neither renders |
| Hero actor hidden | `SetActorHiddenInGame(false)` + re-assert every PI hit; **and** built the same body on a STANDALONE actor | Neither renders ⇒ not the hero |
| Wrong placement / occluded in the drop-pod | Teleported hero **and** standalone actor to **Z=2200 in open air**, camera Z=3400 over the whole island | **Nothing at altitude** (the selection ring vanished too — it's a ground DECAL, which is why it showed on the pod) |
| Cloth / anim / tick | cloth factory nulled, `SetAnimationMode(SingleNode)`, tick on **and** off | No change |
| **Fog of war** | `FogOfWarSceneView` + `FogOfWarPrimitiveCollector` instances both un-ticked + hidden | **Still no render** ⇒ `IsFogOfWarVisibleToLocal==0` was a SYMPTOM of missing deploy context, not the cause |
| FOW vision attributes (route A) | usmap: `FogOfWarRadius/Angle` are GAS attrs on `LokiAttributeSet`; scanned for the hero's attribute set | **`attributeSet == 0x0`** — force-open hero has NO GAS attribute set at all (deploy-gated) |

## THE ONE UNTESTED LAYER — start here

Whether the component ever gets a **render proxy** at all. `UPrimitiveComponent::SceneProxy`, `bRegistered`, and
`bRenderStateCreated` are **non-UPROPERTY C++ members**, so every reflection-based probe used so far was blind to them.

**Method:** find a primitive in the level that is *visibly rendering* (e.g. a level `StaticMeshComponent`), dump its raw
bytes next to our component's, and **diff** — that locates those offsets for this build and shows which one ours lacks.
- `SceneProxy == null` → render state was never created (component built off the normal spawn path) → drive
  `RegisterComponent` / `RecreateRenderState` / `MarkRenderStateDirty`.
- `SceneProxy != null` → the primitive exists but is filtered out of the view → investigate the view/relevance path.

## Capture-window gotcha (this blocked confirmation repeatedly)

Force-open sessions die at **~230-260s** uptime, and the body used to build at **~215s** — almost no window to look.
The shim's resolve did **~18 full 188k-object scans** on the game thread. Trimmed ~8 (dead placeholder sweep behind
`!KLOADRONIN`, GAS attr scan behind `KFOWATTR=0`) → **197s**. **Cut more scans before the next visual test** (cache
`FindInstByClass` results; the `[SEQ]` census is the next fattest). Screenshot via Win+Shift+S / Steam F12 — do NOT
alt-tab.

## Working build flags (S94 final)

```
-DKRUNMODE=RM_PLAY -DKMESHTICK=1 -DKANIMMODE=1 -DKPUPYAW=-90 -DKCAMUP=1200 -DKCAMBACK=600 -DKCAMPITCH=-50
-DKFOWKILL=1 -DKFOWATTR=0 [-DKGROUNDZ=2200 -DKTESTDX=1500 for the open-air test]
```

---

# ★★★★★ S95 RESULT — ROOT CAUSE FOUND: EVERYTHING WE SPAWN IS INVISIBLE TO THE RENDERER

This supersedes the whole "FINAL STATE" table above. The visible-body problem was never about meshes, components,
the hero, fog of war, or occlusion.

## The proof (3 live eliminations, read-only RPM)

1. **`proxy_census.py` on the hero** — every primitive component has `SceneProxy == NULL`, **including the game's own**
   (its CapsuleComponents, 3 DecalComponents, its own StaticMeshComponent, `BP_FogOfWarProceduralMeshComponent_C`,
   `LokiMeshManagerComponent`). The hero actor itself was never render-registered.
   ⚠ only trust rows marked `<-- primitive`; +0x2B0 on other classes is an unrelated field.
2. **Static-mesh discriminator (`KSTATICTEST`)** — took the `Sphere` mesh off a level SMC that IS rendering, put it on a
   plain StaticMeshComponent we created → invisible, proxy NULL. Not skeletal-specific.
3. **Spawn-vs-component discriminator (`KSMACTOR`)** — spawned a real **`StaticMeshActor`** and set that Sphere on the
   root component the **engine** built (3x scale, beside the hero) → invisible, proxy NULL.
   ⚠ the earlier "standalone actor" control was a **CameraActor**, which is hidden in game by default — that test was
   invalid and is why this took so long to isolate.

**⇒ Actors spawned by the GAME render; actors spawned by OUR shim never do.** The hero is one of ours (S74
GameplayStatics deferred spawn), which explains every observation this session.

## Key offsets / diff (this build)

- `UPrimitiveComponent`: SceneProxy triplet at **+0x2B0 / +0x2B8 / +0x2C0**.
- Our spawned `StaticMeshActor` vs a real level `StaticMeshActor_UAID_…`: **essentially identical**, only **+0x162**
  (ours 0x02 / ref 0x01) and **+0x169** (ours 0x0A / ref 0x00) differ — the AActor bitfield region
  (bActorInitialized / bHasFinishedSpawning / EActorBeginPlayState). The actor initialises fine; **component
  registration with the render scene is what never happens.**
- Prime suspect: `SpawnActorCls`'s `BeginDeferredActorSpawnFromClass` + **`FinishSpawningActor`** — if FinishSpawning
  returns null the code silently falls back to the UNFINISHED deferred actor (`act = def`), so PostActorConstruction →
  RegisterAllComponents never runs. **Log its actual return first — that confirms or kills this in one launch.**
- ⚠ No reflection fix available: this build exposes **no** `RegisterComponent` / `RegisterAllComponents` /
  `MarkRenderStateDirty` UFunction (only `PrimitiveComponent::SetRenderCustomDepth`).

## S96 — best lead: use the GAME'S OWN spawn path

`LokiPlayerCheats::ServerCheatSpawnActor(ClassToSpawn, Location)` and `ServerCheatChangeHero(HeroClass)` are already
RE'd (S74 cheat enum; memory `supervive-cheat-surface-inventory`) and already wired in **`RM_CHEATSPAWN`**
(`g_scsaThunk` / `g_schThunk`, via `GetLocalLokiPlayerCheatsBP`). Spawn a `StaticMeshActor` through the cheat RPC and
check its proxy with `proxy_census.py`:
- **proxy non-null** → that IS the fix; spawn/possess the hero via the cheat path and the body should simply appear.
- **proxy null too** → the render scene itself is rejecting runtime primitives; fall back to locating native
  `UActorComponent::RegisterComponent` and calling it directly (it is not a UFunction).

## Tools added

`tools/re/prim_diff.py` (byte-diff two objects; flags qwords that are pointers in one and null in the other),
`tools/re/proxy_census.py` (SceneProxy census over every component of an actor), `tools/re/find_owner.py`,
`tools/re/scan_strings.py`. Shim flags: `KSMACTOR`, `KSTATICTEST`, `KTESTACTOR`, `KFOWKILL`, `KFOWATTR`.

---

# ⚠⚠ S96 CORRECTIONS — read before trusting the S95 block above

**Two S95 claims did not survive further testing. Correcting them here so they don't mislead.**

1. **"+0x2B0 == SceneProxy" is UNVERIFIED (probably wrong).** It came from ONE reference — the DefaultPawn's
   StaticMeshComponent had a non-null qword there. But diffing our spawned `StaticMeshActor`'s root SMC against a
   **level** `StaticMeshActor`'s root SMC yielded **0 pointer-candidates**, i.e. the level component reads **NULL at
   +0x2B0 as well**. A rendering primitive must have a scene proxy, so either +0x2B0 is a different field, or that
   auto-picked "reference" was not actually rendering (`prim_diff.py` auto-pick takes the first StaticMeshComponent
   under a StaticMeshActor and does **not** verify visibility).
   **⇒ Re-derive the offset against a primitive that is provably on screen (e.g. the drop-pod's components) and confirm
   a known-rendering component reads NON-null, before reusing `proxy_census.py` conclusions.**
2. **"FinishSpawningActor silently fails" is FALSIFIED.** Logged live: `FinishSpawning -> res=0x2557…` (non-null) for
   both the StaticMeshActor and the camera actor — our spawn path completes and the `act=def` fallback never fires.
   The `proxy(root)=null` on that line is meaningless: it is read *before* `SetStaticMesh`, and an empty
   StaticMeshComponent legitimately has no proxy.

## Also closed this session

- **Cheat-spawn route is DEAD in force-open:** there is **no live `LokiPlayerCheats` instance**
  (`GetLocalLokiPlayerCheatsBP` → 0; `find_owner.py` shows only the classes, no instances), so
  `ServerCheatSpawnActor` / `ServerCheatChangeHero` cannot be called at all.
- **No registration UFunction exists** in this build — no `RegisterComponent`, `RegisterAllComponents`, or
  `MarkRenderStateDirty`; only `PrimitiveComponent::SetRenderCustomDepth`.

## What is still solid

Our created components **and** our spawned actors never render — under every condition tested: mesh loaded and healthy
(Skeleton + 8 materials + LODInfo), correct world transform, visibility set, cloth/anim/tick variations, hero owner or
standalone owner, on the ground or at Z=2200 in open air, fog of war on or off, bare component or the game's own
`BP_Ronin_DefaultSKMeshComponent_C`. The one real contrast: the **DefaultPawn** — spawned by the *game* during Login —
did read non-null at +0x2B0.

## S97 order of work

1. Re-derive the true SceneProxy offset against a provably-visible primitive; re-run `proxy_census.py` only after that.
   The entire "nothing we spawn is render-registered" framing depends on that number being correct.
2. If confirmed, locate native `UActorComponent::RegisterComponent` / `CreateRenderState_Concurrent` in
   `dumps/merged.dump.exe` and call it directly (they are not UFunctions).
3. Alternative framing worth one test: does the force-open world's renderer accept **any** runtime-added primitive?

---

# ★ S97 DECISIVE RENDER TEST — the "not render-registered" theory is DEAD

`tools/re/proxy_stats.py` derives the proxy offset **statistically** instead of trusting one hand-picked reference:
sample 400 live LEVEL `StaticMeshComponent`s and score every qword offset 0x100–0x700 by how often it holds a pointer.

**Result:** twelve offsets are non-null on **400/400 (100%)** — `+0x6F8 +0x6F0 +0x618 +0x5C8 +0x590 +0x578 +0x570
+0x520 +0x518 +0x440 +0x438 +0x408` — **and both components we created have every one of them SET**, same as the
game-spawned DefaultPawn's component.

⇒ **No structural differentiator exists between what we create and what the game creates.** Our primitives are not
missing registration or a scene proxy.

**This RETRACTS the S95 headline** ("everything we spawn is invisible to the renderer"). That was built on a single
reference (the DefaultPawn's non-null `+0x2B0`) and does not survive a proper sample. **`+0x2B0` is not SceneProxy.**

⚠ Caveat: the 400-component sample was not verified to be *currently rendering* (World Partition keeps unloaded actors
in GUObjectArray), and only pointer-like qwords in 0x100–0x700 were scored. A bitfield-only or out-of-range
differentiator could still exist.

## Where the visible body actually stands

Every externally-testable hypothesis is eliminated:

| Hypothesis | Status |
|---|---|
| Mesh / render data | ✅ loaded + healthy (Skeleton, 8 materials, LODInfo, bounds) |
| Component construction | ✅ bare component AND the game's own `BP_Ronin_DefaultSKMeshComponent_C` |
| Component registration | ✅ `FinishAddComponent` ok; no structural difference vs level components |
| Actor spawn | ✅ `FinishSpawningActor` returns a valid actor |
| Owner hidden | ✅ standalone actors fail identically |
| Placement / occlusion | ✅ nothing at Z=2200 in open air (the "ring" is a ground decal) |
| Fog of war | ✅ both FOW actors disabled → no change |
| GAS vision attrs | ✅ hero has no attribute set at all |
| Cheat spawn | ✅ no `LokiPlayerCheats` instance exists |

**There is no identified remaining lever for a visible hero on the client-side force-open route.**

## Do NOT switch to the DS / blueprint-stub route for this goal

`TrainingQuest_Basics_Base.OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly` — a networked client can never be
authority, so that route is **structurally incapable of completing objectives** (settled S90; see
`docs/tutorial-playability-plan.md`). It would trade a working tutorial for a visible body.

## What works and should be treated as the deliverable

Completable objectives + walkable lesson chain (WASD→LMB→Dash→Jump) + **movable hero** (WASD, camera-aligned) +
**stable movement** (`MOVE_Flying`) + **top-down camera**. The hero is invisible; everything else plays.
