# Hero-visibility synthesis — ranked plan (S95+)

## Bottom line

Six angles produced one genuinely new, independently-verifiable finding and one genuinely new methodological finding, and almost everything else is either a re-tread or rests on a control that turned out to be invalid. **The new finding:** the engine's PSO-precache proxy-creation gate is *armed* in this build — I disassembled `GetPSOPrecacheProxyCreationStrategy` at `dumps/merged.dump.exe` file-offset `0x3C94530` myself and confirmed `[base+0x9ADD3A0] == 1` and `[base+0x9FA9934] == 0`, which makes it return **1**, which is exactly the value both `CreateSceneProxy` call sites (`base+0x3E67096` static, `base+0x3676EAB` skinned) test with `cmp al,1 / jne` before returning `nullptr`. **The methodological finding:** every "it's not the hero, nothing we spawn renders" control ever run is invalid — the `CameraActor` control is retracted in the shim's own comments, the `StaticMeshActor` control called `SetStaticMesh` on a Static-mobility registered root (silent early-return, logged as "ok"), and `KSTATICTEST`/`KTESTACTOR` **never ran at all** (I confirmed: `docs/tutorial-launch-marker.txt` has `[SMA]` but no `[SMT]` and no `[PL] TEST actor=`, despite their guards being satisfied — that build was compiled with them off). So the search space is wider than the eliminated list claims, and the top five items below are all cheap enough to ship in **one binary and one launch**, which is the only sane way to spend a ~5-minute, ~2/3-crash-rate, ~200-second-window session.

---

## Ranked table

| # | Item | Effort | Conf. as *cause* | Info gained | Ships in build |
|---|------|--------|------------------|-------------|----------------|
| 1 | PSO-precache gate: disarm `r.PSOPrecache.ProxyCreationWhenPSOReady` (4-byte `.data` write) **+** raise `LogStaticMesh` / `LogSkinnedMeshComp` verbosity to 6 (two 1-byte writes) so the engine names its own bail reason | tiny | medium | **very high** | A |
| 2 | Derive the *real* `SceneProxy` offset (visible-component `SetVisibility(false)` qword delta), then read it on our body vs a proven-visible component | small | n/a (measurement) | **decisive branch selector** | A |
| 3 | Write `Scale3D = 1.0` in `DoSpawnPossess` + log the pre-fix spawn Scale3D and live root `RelativeScale3D` | tiny (3 lines) | medium | high | A |
| 4 | A *valid* positive control: spawn `BP_Ping_Arrow_C` via the game's own bytecode recipe; re-enable `KSTATICTEST`/`KTESTACTOR` with a `Mobility` log | small | n/a (control) | **very high** | A |
| 5 | Free bundled reads: hero `VisibilityStateComponent` stacks, `LokiMeshManagerComponent.HeroMeshComponent`, body-component material-slot FNames, and the **red-decal ownership test** | small | low | medium | A |
| 6 | `DelayStrategy = 1` (strategy 2 = default-material proxy) — separates "no proxy" from "proxy with unusable materials" | tiny | low | medium | A (flag, fire only if #2 says proxy NULL and #1 didn't fix it) |
| 7 | `poke_toggles.py <pid> <base> 151` — 2-minute rider, read the array back with RPM (do **not** trust the log spam as a signal) | tiny | very low | low | rider |
| 8 | `Comp_BP_BotSpawner_C::SpawnSoftClassBotAtLoc` — game's own hero-bot factory, tests the *cosmetics* branch specifically | medium | low-med | medium | B (only if A is inconclusive) |
| 9 | `OnPlayerSpawned_BP` + `GrantStarterItems` on the already-possessed hero (Stage A only) | medium | low | medium | B |
| 10 | Beacon `SK_ResBeacon_Main_Default_01` mesh swap | medium | low | medium | C (late contingency only) |

Ranks 1–6 are **one build, one launch**. Do not split them.

---

## Top 5 in detail

### 1. Disarm the PSO-precache proxy-creation gate, and make the engine log its own bail reason

**What to do.** At shim init, before `BuildHeroBody` runs (the gate is evaluated at render-state creation, so order matters):
- write `int32 0` to `base+0x9ADD3A0` (`GPSOPrecacheProxyCreationWhenPSOReady`), or equivalently `ExecuteConsoleCommand("r.PSOPrecache.ProxyCreationWhenPSOReady 0")` — the shim already has that primitive wired (`tutorial_launch.cpp` lines 84 / 441 / 3302);
- write `byte 6` to `base+0x9FB7A60` (`LogStaticMesh.Verbosity`) and `base+0x9F87808` (`LogSkinnedMeshComp.Verbosity`).

**Why I believe the disassembly.** I decoded it independently rather than trusting the angle:
- `0x3C94530`: `83 3d 69 8e e4 05 01` → `cmp dword [base+0x9ADD3A0], 1`; `74 03 / 32 c0 / c3` → return 0 unless it equals 1; then `8b 0d f2 53 31 06` → `mov ecx,[base+0x9FA9934]`; `ecx==0 → al=1`, `ecx==1 → al=2`.
- `0x3E67096`: `mov rcx,rdi; call 0x3623520` (IsPSOPrecaching) `; test al,al; je skip; call 0x3C94530; cmp al,1; jne skip; cmp byte [base+0x9FB7A60],6; jb skip` — and `skip` at `0x3E670FB` is `33 c0` = `xor eax,eax` = **return nullptr**.
- Live `.data` in both dumps: `[0x9ADD3A0] = 01 00 00 00`, `[0x9FA9934] = 00 00 00 00` → strategy = **1** = the bail value. `[0x9FB7A60] = 05` and `[0x9F87808] = 05` → the log is compiled in (CompileTimeVerbosity 7) and suppressed at runtime by exactly one byte. `LogStaticMesh` already writes to `Loki.log` today at Log level, so raising it demonstrably lands in the file we already read.

**Confirms:** body appears with the poke active. Or: `Loki.log` gains a `Skipping CreateSceneProxy … PSOs are still compiling` line correlated by timestamp with the shim's `docs/tutorial-launch-marker.txt` writes.
**Kills:** a bail line naming a *different* reason (`RenderData is null` / `not initialized` / LOD) redirects to that reason. No bail lines at all **and** SceneProxy non-null (item 2) means proxy creation was never the wall and this whole family closes.

**Honest caveat, and it is the reason confidence is medium not high.** This gate is a *delay with a built-in cure*: the same `IsPSOPrecaching` at `base+0x3623520` does `lea rcx,[rbx+0x2B0]; call 0x3C7F830` then `or byte [rbx+0x2AA],0x40` — it schedules a render-state recreate for when precaching finishes, and clears `[rbx+0x2C0]` on completion. For this to explain a body invisible for an entire session, that recreate must *also* be failing. That is a second, unstated hypothesis. The gate being armed is a fact; the gate being *the* cause is not. Also: nobody has ever validated that this build's anti-tamper ignores `.data` writes — reasonable assumption, not a proven one.

Two corrections carried forward: the `PSOPrecachingState: Missed` blocks in the log are **neutral**, not supporting (they're logged from the draw path, i.e. for primitives that *did* render), and `[comp+0x2C0]` is **self-clearing**, so reading NULL there falsifies nothing — probe `[comp+0x2AA] & 0x40`, which is set once and never cleared in that function.

---

### 2. Derive the true `SceneProxy` offset, then read it

**What to do.** Pick a component you can *see* on screen (island geometry, drop pod). Snapshot every qword in `[comp+0x100 .. comp+0x780]` via RPM; call `SetVisibility(false)` on it through the existing native-call primitive (already wired at `tutorial_launch.cpp:2827`); re-snapshot; the qword that goes non-null → null **is** `SceneProxy`, derived by construction. Offline cross-check: `"AddPrimitiveCommand"` @ `0x7AF2AC8` has lea-xrefs at `base+0x26877C9` / `base+0x2687F35`; `"FRemovePrimitiveCommand"` @ `0x7AF2BE0` at `base+0x26889FE` / `base+0x2688DAE`. Then dump, side by side for our invisible body and the proven-visible reference: `SceneProxy`, `[+0x2AA]&0x40`, `[+0x2B0]`, `[+0x2C0]`, and for the skeletal body `[+0x970]` (MeshObject) and the int32 at `[+0x91C]` (LOD index — `CreateSceneProxy` bails on `js` / `>= [rsi+8]`).

**Why this is rank 2 and not rank 6.** The S97 "decisive render test" scored offsets by *non-null on 400/400 level StaticMeshComponents*. That criterion **structurally excludes** `SceneProxy` — a scene proxy is null for every non-rendering, hidden, or World-Partition-unloaded component, so it can never score 400/400 and could never have appeared among the twelve winning offsets `0x408–0x6F8`. **Eliminated-hypothesis #3 does not say what the eliminated list claims it says.** And the marker's `proxy(root)=null` / `proxy(root)=SET` lines read `+0x2B0`, which S97 already retracted — and which this disassembly shows is inside the *PSO precache request* block, not the proxy pointer. Every one of those lines is uninterpretable.

**Confirms / kills, symmetrically:** SceneProxy **non-null** on the invisible body → the entire `CreateSceneProxy`-bail family (items 1 and 6) is dead in one measurement and the wall moves downstream into scene/culling/relevance. SceneProxy **null** → the family is confirmed and the log line from item 1 names which branch.

---

### 3. Write `Scale3D = 1.0` in `DoSpawnPossess`

**What to do.** In `tools/sigbypass-mod/tutorial_launch.cpp`, `DoSpawnPossess` at ~L2973 does `memset(g_xform,0,...)`, then fills the transform from `GetActorTransform(g_startSpot)` with a zero-check that scans **only bytes 0..0x38** — rotation and translation, never Scale3D at `0x38/0x40/0x48`. Both later location fixes (camera viewpoint, start spot) write only Translation `@0x20` and quat W `@0x18`. Add, immediately after the transform block, the same three lines `ResolveSpawnSeq` already has at L1062:
```
*(double*)(g_xform+0x38)=1.0; *(double*)(g_xform+0x40)=1.0; *(double*)(g_xform+0x48)=1.0;
```
Ship it *with* instrumentation: extend the `[GS] xform T=` marker to print Scale3D, and add the live root's `RelativeScale3D` to the `[DIAG]` block. That way the run is self-proving — the marker tells you what the scale *was*, the screen tells you whether fixing it was sufficient.

**Verified.** I confirmed `grep -n "SetActorScale|SetWorldScale|SetRelativeScale"` returns **zero** hits across the 4104-line file — nothing downstream repairs it. `ResolveSpawnSeq` (L1062), the quest-spawn path (L2024), `KSMACTOR` (L2760, scale 3.0) and `KTESTACTOR` (L2778) all set scale explicitly; `DoSpawnPossess` alone does not. And `docs/tutorial-playability-plan.md:394` records verbatim: *"FIX APPLIED: set FTransform Scale3D (@0x38/0x40/0x48) to 1.0 — DoSpawnPossess leaves it 0 (zero-scale actors)"* — this project already found this bug once, fixed it in the other spawn path, and never back-ported it.

A zero-scale actor reproduces the whole profile with no leftovers: correct world coordinates, working possession, working CMC velocity puppet, camera follows, `bHiddenInGame=0`, every one of the twelve 400/400 pointer offsets set, nothing drawn at ground level *or* at Z=2200. `BuildHeroBody` sets the child's *relative* scale to 1, which under a zero-scale parent still yields world scale 0.

**Two things it is not.** (a) `TransformScaleMethod=1` does **not** fix this — UE's `MultiplyWithRoot` computes `RootDefaultScale × UserScale`, so 0 stays 0. Write the scale; leave the param alone. (b) `KBODYZ` is `0.0`, so the marker's `comp world == hero world` is *not* evidence for zero parent scale either — I checked, so nobody wastes a cycle on it.

**Kills:** the new marker reports the pre-fix spawn Scale3D as `(1,1,1)` and live root `RelativeScale3D` as `(1,1,1)`. Cost of being wrong: three lines that should be there anyway.

---

### 4. A control that is actually valid

**What to do.** Three arms, one frame:
- **`BP_Ping_Arrow_C`** via the game's own recipe, copied out of `bpdump_ExecuteUbergraph_TrainingQuest_Basics_WASD.txt` [91]–[98]: `BeginDeferredActorSpawnFromClass(worldCtx, cls, xform w/ Scale3D=1, CollisionHandlingOverride=1, Owner=null, TransformScaleMethod=1)` → `SetVectorPropertyByName(actor,"StartPoint"/"EndPoint")` → `FinishSpawningActor(actor, xform, 1)`. Place it ~400 units from the hero. It is a SceneComponent root + two plain `UStaticMeshComponent`s, no Niagara/decal/widget. **It carries a Timeline and `Timeline__FinishedFunc`, so it may self-destruct after a few seconds** — log liveness on every PI hit and screenshot immediately, or a lifetime artifact will be misread as an invisibility result.
- **Re-enable `-DKSTATICTEST=1 -DKTESTACTOR=1`** — they were compiled out of the last DLL. Add a `Mobility` log before and after every `SetStaticMesh`: `UStaticMeshComponent::SetStaticMesh` early-returns when `!AreDynamicDataChangesAllowed() && IsRegistered()`, and `CallNativeGuarded` only detects SEH faults, which is exactly how `[SMA] SetStaticMesh … ok` got logged for a call that did nothing. A component created via `AddComponentByClass` inherits `USceneComponent`'s `Movable` default, so *our* component is a valid target where the `AStaticMeshActor` root was not — that asymmetry is the whole point of the arm.
- Swap the `KTESTACTOR` host off `g_tcCamCls = FindClassExact("CameraActor")` (invalid — the shim's own S95 comment retracts it) onto the ping-arrow class or any class whose SCS root is a visible primitive.

**Why it matters.** Six sessions have asked "why is the hero invisible" and none has answered "can our shim make *anything* known-visible appear". The only human-confirmed rendering event on this route — the S91 movement chevrons and objective rings — came from `GameStateTryStartTraining` driving the tutorial's *own* registered objective; `docs/session-91-quest-spawn-bpcall.md:111-113` says our S91-spawned quests were orphans that spawned nothing. And `tutorial-playability-plan.md:22` says the quest's `OBJARROW` resolves to a *live pre-existing* capsule, so the chevrons may have been *revealed*, not spawned. So the identification of the chevrons as `BP_Ping_Arrow_C` is an inference; it remains the best candidate because its geometry is plain static meshes, not because anyone saw it.

**This proposal cannot be "false"** — both outcomes are decisive. Arrow visible → our spawn path is fine, the fault is hero-specific (items 1/3 hold the answer). Arrow invisible → the fault is our spawn *call*, and the 3-way bisect (`TransformScaleMethod`, `CollisionHandlingOverride`, `WorldContextObject = g_gm2` vs an in-world actor) is a short binary search against a known-good target. Ping-arrow visible **+** our runtime `StaticMeshComponent` carrying a level mesh invisible → runtime `AddComponentByClass` primitives genuinely never draw.

---

### 5. Free bundled reads (zero extra launches)

Additive logging inside the same build / additions to `tools/re/probe_comp.py`:
- **The red-decal ownership test.** `docs/next-session-prompt-s95.md:181` records the hero owning **3 DecalComponents**, and the ground ring tracks the hero and vanished at Z=2200 (no surface to project on). Write `DecalColor` = pure red through the existing reflected-offset path (`DecalComponent` is `UClass:SceneComponent`, `schema.txt:13998`, `DecalColor` at `:14006` — a plain `StructProperty`, no UFunction needed) and look. **Red ring = a component on an actor we spawned already renders**, which localizes the failure to *mesh primitives specifically* and permanently retires the "nothing of ours renders" framing. Unchanged ring = the ring is game-side and our hero renders literally nothing.
- **`VisibilityStateComponent`**: `HiddenStacks` / `VisibilityStacks` / `SourcedVisibilityStates` (`schema.txt:53575-53578`) off `LokiCharacter.VisibilityState` (`:23731`), plus a null check. Genuinely not eliminated-hypothesis #8 (that disabled the two *world-level* fog-of-war producer actors). But the causal story is weak: both of the game's hero hide/show paths (`AuthSetMeshVisibility` ubergraph 24626 and `CheckHeroHidden` ubergraph 34470) route through `GetBaseCosmeticsController()`, which is **null** in force-open, so the layer has no effector; and the shim already re-asserts `SetActorHiddenInGame(false)` + `SetVisibility(true)` every PI hit. **Read only — do not poke `HiddenStacks`.** A stack counter poked outside `RequestVisibility` is as likely to desync as to reveal, and this project has been burned by exactly that (`byte[PM+0x388]`).
- **`LokiMeshManagerComponent.HeroMeshComponent`** (`schema.txt:26570`) — read it as a SoftObjectProperty pair (`FWeakObjectPtr@0x0` + `FSoftObjectPath@0x8`), never a raw pointer at `+0x0`.
- **Body-component `OverrideMaterials` element FNames** — closes "a slot resolves to `M_Hidden`" by observation instead of argument. (Note the null-material theory is already dead on engine behavior: null slots substitute `GEngine->DefaultMaterial` and draw **grey**, not invisible.)
- Also raise `LogLokiFogOfWarMeshComponents` / `LogLokiVisibilityReceiver` verbosity in the same poke list as item 1 — zero marginal cost.

---

## Do NOT attempt

- **The cosmetics-controller construction family** (`SetCosmeticBundleClass` → `TryLoadInitialData` → `RefreshCosmetics`, force-feeding `Data.MeshComponentClass`, adopting `CosmeticsController.Mesh`). Three independent kills: (a) the named class `BP_Ronin_DefaultCosmeticsController_C` is reached via **`MenuCosmeticsControllerClass`**, not `CosmeticsControllerClass` — all 14 hero bundle JSONs serialize only the menu one; (b) `Data.MeshComponentClass` is set **nowhere** in our dumps (the base controller CDO's `Data` holds only `DedicatedServerMeshComponentClass` and `HUDPortrait`), so "the game builds Mesh its own way, right socket, right materials" has no game-authored input and would trip its own `"Empty mesh class specified"` log; (c) S79/S80 already ran `ClientInitialComponentSetup` / `BP_PostSetupCosmetics` / `TryLocalControlSetup` / `RefreshLocalControl` **clean** with skeletal-mesh count 0 after, and S93 force-open got `controller=0, Mesh=0` from the same set. Above all it is hero-specific and cannot explain a bare `StaticMeshActor` being equally invisible. *(One free rider is worth keeping: re-run the controller census with the exact class name `LokiHeroCosmeticsControllerComponent` — S93 wrote "LokiCosmeticsController", so "0 instances" may be a name-matching artifact.)*
- **`RestartPlayerAtTransform` (Stage B)** — spawns a *second* pawn and `SetPawn()`s it onto the controller. It can orphan the currently-possessed, moving hero, which is the one thing this route has actually achieved. `Loki.log:2340` also shows `FindPlayerStart: PATHS NOT DEFINED`, so the ChoosePlayerStart variant is dead on arrival anyway.
- **The beacon `SK_ResBeacon_Main_Default_01` mesh swap, as an early move.** It is a `_UAID_` World-Partition actor (can be unloaded — "never streamed out" is false), it carries `bIsRuined: true` (its main mesh may be switched off, making a null result uninterpretable), and it mutates a live tutorial level actor with a mismatched-skeleton asset mid-session. Late contingency only, and only after you've *seen* the beacon drawing.
- **Screen-space UMG "avatar" and the in-world `WidgetComponent` variant.** The first changes the deliverable (a HUD marker is not a body); the second is a `MeshComponent`, i.e. the exact primitive path that has failed every test.
- **Poking the Loki visibility layer / anything in the fog-of-war neighbourhood as a *cause*.** Its supporting datum ("no xrefs in `.text` in either dump") is a non-sequitur — neither dump was captured in a force-open session, so undecrypted pages are the expected state. Read-only, bundled, is the most it's worth.
- **`AuthSetGameFeatureToggle` shim work.** Redundant — `tools/re/poke_toggles.py` (S89) already sets the readiness bit and fills all 151 values via plain RPM, and `schema.txt:61484` already carries the full `ELokiGameFeatureToggle (151 values)` table, so no FName-pool archaeology is needed. And "the toggles-not-ready spam stops" is an **invalid** success signal — S94 recorded the spam persisting in a run that injected `gft_ready_fix` (47,608 occurrences). Keep only as the 2-minute rider at rank 7.
- **The shopkeeper spawn as a render oracle.** `SpawnBasecampShopkeep`'s spawn transform is a *function local* with a baked default inherited from the base battle-royale component (the tutorial overrides only `BasecampShopkeepClass` and `SpawnForgeShop`), so it can materialize at BR-map coordinates and produce an inconclusive result read as an elimination. The ping-arrow control is strictly better. *(Its Stage 0 is still worth 30 seconds: `tools/re/obj_by_class.py <pid> <base> DropPod` — a `_UAID_` suffix means the visible pod is a level actor; a plain `_C_<n>` means the game already runtime-spawns a visible actor in force-open, answering the oracle for free.)*
- **`TransformScaleMethod = 1` as a scale remedy** — mathematically inert against a zeroed Scale3D.
- **`DelayStrategy = 1` as its own launch** — it's a knob on item 1, not a proposal.
- **Anything on the dedicated-server / `unreal-stub` route** — `TrainingQuest_Basics_Base.OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`; that trade gives up a working tutorial for a body.

---

## Operational constraints the plan must respect

- `FindInstByClass` (`tutorial_launch.cpp:549`) matches a class-name **substring** and skips only names starting with `Default__`. SCS templates are named `Comp_*_GEN_VARIABLE` — not `Default__`-prefixed — so it will happily return an **archetype**. Any new instance lookup needs a `GEN_VARIABLE` reject-guard or an `Outer == live gamemode` check.
- `CallBPGuarded(func, context, resultBuf)` takes **no params argument** — arguments go into the file-static `g_bplocals` at each `ParamOffset`, and it refuses any function with `PropertiesSize > 0x800`.
- Sessions die at ~230–260s and the S94 shim already burned ~18 full 188k-object GUObjectArray scans (trimmed to ~197s). **Cache every resolved pointer after the first scan** or the new build will not reach a screenshot.
- Marker bytes `bHidden=112` / `bVisible=99` are raw **bitfield bytes read whole** — neither number tells you whether the relevant bit is set. Fix the prints while you're in there.

---

## If all of these fail

**Is a visible hero achievable on this route at all? Honestly: unknown, and I'd put it around 50/50 — but the odds are better than the last two sessions suggest, because the evidence base was worse than it looked.** Three of the load-bearing eliminations turned out to be invalid controls, one ("our primitives are not missing a scene proxy") was derived from a scan that structurally could not have measured a scene proxy, and every `proxy(root)=` line ever logged reads a retracted offset. That is a lot of "settled" ground that isn't.

Against that: items 1 and 3 both have a real counter-argument (the PSO gate is self-healing by design; a zero-scale actor should arguably have broken the capsule more visibly), and items 2, 4 and 5 are diagnostics, not fixes. It is entirely possible the honest outcome of this session is "we now know exactly which layer refuses to draw" and no pixels.

**The branch that would genuinely close the route:** item 2 returns `SceneProxy` **non-null** on the invisible body, item 4's ping arrow **does** render, and item 1's verbosity log prints **nothing**. That combination means a proxy exists, our spawns render, and `CreateSceneProxy` never bailed — which puts the wall in scene relevance / view / culling, a layer this project has no primitive to reach (no `RegisterComponent`, no `MarkRenderStateDirty`, no console, anti-tamper on `.text`). At that point I would call it and stop.

**Fallbacks, in the order I'd take them:**
1. **Ship the tutorial without a hero body.** This is the honest default and it is not a small thing — objectives complete, the lesson chain walks WASD→LMB→Dash→Jump, the hero moves, the camera follows, the world renders. That is a *playable* tutorial with an invisible protagonist. Document it as such and bank the win.
2. **A ground-decal avatar** as an explicit consolation prize — *only* if item 5's red-decal test proves the hero's own `DecalComponent`s render. Under the existing `-DKCAMPITCH=-58` top-down camera a `DecalSize`-scaled silhouette reads as a body-shaped marker. It is a hack, it has no depth or perspective, and it should never be described as "the hero is visible" — but it gives the player something to track. It is worth ~1 session, not more.
3. **The game-built-character route** (item 8, `SpawnSoftClassBotAtLoc`) as the last real attempt — its unique value is that it may reach a *cosmetics* entry point the orchestrators we've already driven do not. Low confidence, medium cost, and its rationale collapsed under review (the current hero already comes from the gamemode's own native `SpawnDefaultPawnFor`, so "let the game spawn it" is already done and already invisible). Only if items 1–6 come back clean.

I would not spend more than two more sessions on visibility. The tutorial works; the body is polish.