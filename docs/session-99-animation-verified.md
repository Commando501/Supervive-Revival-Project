# Session 99b (2026-07-26) — idle animation VERIFIED (by measurement), run animation added, GAS gate re-scoped

Branch `dedicated-server-stub`, force-open tutorial route. Continues S98 (visible hero) / S99 (animation built but
never confirmed — that session died before anyone could look at the screen).

## TL;DR

- ✅ **The idle animation is playing on a body the renderer is actually drawing.** Proven by direct measurement,
  not by a picture: `bRecentlyRendered == 1` on 8/8 samples **and** the component's memory is re-posed every frame
  while the actor is stationary.
- ⚠️ **`tutorial_launch_sp.dll` on disk was STALE** — it predated the S98 zero-scale fix, so the shipped shim was
  still spawning the hero at `Scale3D (0,0,0)`. Rebuilt; the fix now fires live.
- ✅ **Run animation implemented** (velocity-driven idle↔run AnimSequence swap) and confirmed engaging live.
- ✅ **Self-screenshot capability added** — the game writes its own PNGs. Useful, but it **cannot photograph the
  hero** (see the trap below).
- ✅ **Two real crash bugs found and fixed** in the play shim.
- 📉 **The "abilities are GAS-gated" scope is smaller than S99 claimed** — see below.

---

## ★ Goal (a): is the idle animation actually playing?

Computer-use screen access was **denied by the user**, so there was no way to look at the screen. The question was
settled from process memory instead, with three independent witnesses:

| witness | result | what it rules out |
|---|---|---|
| `AnimScriptInstance` | `AnimSingleNodeInstance`, `CurrentAsset` = the loaded `A_Ronin_Cosmetic_HeroSelect_Breathe` | the asset never reached the instance |
| component memory over 2s (`tools/re/obj_diff_time.py`) | **34 dwords changed**, floats drifting smoothly (`3.04488 → 3.04639`, `3.15574 → 3.16043`) while the actor was **stationary** | a static bind/T-pose (that would change nothing) |
| **`bRecentlyRendered`** (`tools/re/render_witness.py`) | **1 on 8/8 samples** | the body not being drawn at all |

`bRecentlyRendered` is the decisive one and it is worth remembering: it is a reflected `BoolProperty` on
**`SkinnedMeshComponent`** — i.e. on the body component's own class chain — and the **renderer** is what sets it.
Every earlier "is the hero visible" argument in this project was indirect (screenshots, occlusion tests, scene-proxy
theories) and several were flat wrong. This is a direct read.

⇒ **Animation + visibility are both confirmed. Goal (a) is done.** The only thing not independently confirmed is
the aesthetic detail — whether the sword now sits in the hand — which needs a human eye (see "for the user" below).

### ⚠️ THE TRAP: `HighResShot` does NOT capture skinned meshes

The shim now makes the game screenshot itself (`ExecuteConsoleCommand("HighResShot 1")`, the same primitive that
force-opens the map). It works — real 2.7 MB PNGs land in
`%LOCALAPPDATA%\SUPERVIVE\Saved\Screenshots\WindowsClient\`, showing the tutorial world from the top-down camera.

**But the hero is absent from every one of them**, and that is a property of the capture path, not of the game:
each shot logs the hero and camera world positions, the geometry puts the hero within ~3° of the view centre, and
`bRecentlyRendered` was simultaneously `1`. Static world geometry captures fine; the skinned mesh does not.

**Do not read "no hero in the PNG" as "the hero is invisible".** That mistake would have re-opened the entire
S94–S97 dead end. Also note `Shot` / `Screenshot` are stripped in this shipping build — only `HighResShot` exists.

---

## ★ Goal (b): run animation

Real locomotion blending lives in the AnimBP, and the AnimBP collapses the pose to nothing in force-open (S99,
user-confirmed). So the shim stays in SingleNode and swaps whole AnimSequences off the CMC's velocity:

- idle: `A_Ronin_Cosmetic_HeroSelect_Breathe`
- run: `A_Ronin_Movement_OutOfCombat_N` (`-DKRUNANIMPATH` / `KRUNANIMNAME`)
- threshold `KRUNSPEED` (default 40) on `|velocity XY|` at `CMC+0xE8`

Because the shim cannot press W, `KAUTOWALKMS` / `KAUTOWALKATMS` drive the velocity themselves for one window so
the run animation can be exercised with nobody at the keyboard. Live result: `[ANIM] PlayAnimation(run, loop) ok`.

Player control is untouched outside that window — `DoPuppet` still owns WASD.

## ★ Two real crash bugs fixed in `DoPlay`

1. **Re-driving the anim instance every frame.** The first attempt retried the swap on every hit. When
   `PlayAnimation` failed it failed *repeatedly* — `RIP=0x0 access=EXEC addr=0x0` (a call through a null function
   pointer, `RDI=AnimSingleNodeInstance`) four times in a row until one escaped the SEH guard and killed the
   process. Fixed: the swap is **rate-limited (400 ms)** and **latches off permanently on the first fault**,
   keeping whatever pose is already on the skeleton.
2. **Poking a dead hero.** The tutorial's own logic can `UnPossess` (and destroy) the hero mid-hold; every per-hit
   call takes `g_wmHero`/`g_plComp` as a raw pointer, so afterwards they are calling natives on freed memory
   (observed: repeating `0xC0000005` reading `0xFFFF'FFFF'FFFF'FFFF` with `UnPossess` live in the fault context).
   `LooksLikePtr` cannot detect a freed object, but `PC->Pawn` can. `DoPlay` now compares `PC->Pawn` to the hero
   each hit and **stands down permanently** if they diverge.

## ★ The stale-DLL trap (cost most of a session in S99)

`tutorial_launch_sp.dll` was dated **Jul 24 17:41**; the S98 zero-scale fix landed in the source **Jul 26 00:45**.
S98 confirmed its fix by *poking a running process* (`poke_scale.py`), so the DLL was never rebuilt — the shim on
disk still spawned the hero at `Scale3D (0,0,0)`. After rebuilding, the marker reads:

```
[GS] Scale3D@0x40 was (0.000,0.000,0.000) -> now (1.0,1.0,1.0) *** ZERO-SCALE BUG FIXED ***
[DIAG] hero root RelativeScale3D=(1.000,1.000,1.000)  (ok)
```

**Rule: after any shim source change, rebuild every DLL variant that compiles that file, not just the one you are
iterating on.** `sp` and `play` come from the same `tutorial_launch.cpp`.

## ★ Goal (c): what "playable" can mean — the GAS gate is SMALLER than S99 claimed

> ⚠️ **READ THE S100 SECTION AT THE END OF THIS FILE BEFORE ACTING ON THIS ONE.** The conclusion below that the
> character "owns its ASC and both attribute sets" was reasoning from property names and is **WRONG** — measured
> live, all three are NULL. S100 has the corrected picture and the real owner.

S99 recorded "the force-open hero has **no AttributeSet at all**… GAS initialises during the server-authoritative
deploy this route cannot run… a large, uncertain effort comparable to the whole deploy problem."

A live census (`tools/re/gas_probe.py`) does not support the strong reading of that:

```
LokiAbilitySystemComponent      x421      LokiAttributeSetHealth   x417
LokiAttributeSet                x13       LokiAttributeSetAirship  x3
```

**The ability system is heavily instantiated in the force-open world** (the actor pool primes a hero — with its ASC
and health set — for every hero in the game; the log's `LogActorPooling: Adding …/BP_HERO_*` lines are these).
So GAS is *not* absent, and "GAS cannot be initialised outside deploy" is not established.

Structurally (`schema.txt`), `LokiCharacter` — the hero's own base class — declares:

```
AbilitySystemComponentStorage    ObjectProperty (UClass:LokiAbilitySystemComponent)
AttributeSetStorage              ObjectProperty (UClass:LokiAttributeSet)
AttributeSetHealthStorage        ObjectProperty (UClass:LokiAttributeSetHealth)
```

i.e. the character **owns** its ASC and both attribute sets. Combined with `LokiHeroCharacter`'s `Ability1/2/3` +
`AbilityDodgeRoll` class properties, the remaining work for abilities looks like a bounded list rather than a
rebuild of deploy:

1. read the hero's `AbilitySystemComponentStorage` / `AttributeSetStorage` / `AttributeSetHealthStorage`
   (**not yet done** — the probe needs the hero pointer and every attempt lost the session first);
2. `InitAbilityActorInfo(owner, avatar)` on that ASC;
3. grant `Ability1/2/3` / `AbilityDodgeRoll` — normally server-authoritative, but **force-open IS the authority**
   (that is exactly why objectives can complete here and cannot on the DS route);
4. apply the attribute-init effect / curve table so the attributes are non-zero.

⚠️ S94's `attributeSet == 0x0` came from `FindAttrSetFor(hero)`, which scans for an AttributeSet whose *Outer chain
reaches the hero*. Given the sets are `…Storage` members, that heuristic can miss them. **Re-derive by reading the
three properties directly before concluding anything.** Step 1 is the whole next move and it is cheap.

### Honest scope table

| goal | status |
|---|---|
| visible body | ✅ S98; re-confirmed here by `bRecentlyRendered` |
| WASD movement + camera + stability | ✅ S94 |
| objectives + lesson chain | ✅ S93 |
| idle animation | ✅ verified by measurement (S99b) |
| run animation | ✅ implemented + engages; swap is fault-latched |
| sword-in-hand (cosmetic) | ❓ needs one human screenshot |
| abilities / attacks | ⚠️ **re-scoped**: a concrete 4-step list above, not a deploy rebuild — but step 1 is unproven |

---

## Build flags added

`KRUNANIM` `KRUNANIMNAME` `KRUNANIMPATH` `KRUNSPEED` `KSHOT` `KSHOTMS` `KAUTOWALKATMS` `KAUTOWALKMS`

Current `play` build (note the ground offset — it moves the hero off the drop pod, which otherwise sits exactly at
the default teleport target and swallows the camera's whole frame):

```
-DKRUNMODE=RM_PLAY -DKANIMMODE=1 -DKPLAYANIM=1 -DKMESHTICK=1 -DKPUPYAW=-90
-DKGROUNDY=(-2600.0) -DKCAMUP=1200 -DKCAMBACK=650 -DKCAMPITCH=-58
-DKCHEATSPAWN=0 -DKSMACTOR=0 -DKSTATICTEST=0 -DKTESTACTOR=0 -DKFOWKILL=0 -DKFOWATTR=0
```

## New tools (all read-only RPM)

| tool | use |
|---|---|
| `tools/re/render_witness.py <PID> <compHex>` | **is it being DRAWN** — samples `bRecentlyRendered` (SkinnedMeshComponent), with the correct FBoolProperty **bit mask** |
| `tools/re/obj_diff_time.py <PID> <objHex> [bytes] [sec]` | reflection-free "is this object ticking" — diffs a raw window twice |
| `tools/re/anim_probe.py <PID> <BASE> <compHex>` | `AnimScriptInstance` / `AnimationData` / `CurrentAsset` |
| `tools/re/anim_trace.py <PID> <objHex> <offs> [n] [iv]` | trace floats over time (smooth trajectory vs noise) |
| `tools/re/gas_probe.py <PID> <BASE> [heroHex]` | hero's ability/attribute properties + a live census of every GAS object |

⚠️ Bool UPROPERTIes are **bitfields** — read the byte AND the `FBoolProperty` FieldMask (`+0x70`).
Reading the raw byte is what produced this project's meaningless `bHidden=112` / `bVisible=99` diagnostics.

## Injection order gotcha

Injecting `sp` and `play` back-to-back **fails**: `play`'s resolve runs before the hero is possessed, finds
`PC->Pawn` null and aborts (`[PL] resolve failed -> abort`). Wait for `[SP] done step=` in the marker first.
Sequence script: `scratchpad/inject_seq.ps1`. The `fo` inject still kills the game roughly 2 runs in 3 — budget
relaunches; 4 of 7 attempts this session died there.

## ENV AT HANDOFF

Config **reverted to baseline** (`forceTutorialMatch=false`, address `127.0.0.1:7777`); `ags` rebuilt clean.
Game and `ags` stopped. Shim DLLs on disk = the builds described above.

---

# ★★★ S100 (2026-07-26) — the GAS question, MEASURED. The hero owns no ability system; the CARRIER is missing.

Follow-up to the goal-(c) scoping above. Two independent live runs (different hero addresses, identical results)
with `tools/re/gas_recon.py`.

## The result — and it INVERTS the S99b lean

S99b guessed the hero's ability system was constructor-owned and merely uninitialised. **It is not.**

```
--- A. OWNERSHIP ---
   AbilitySystemComponentStorage    @0x0F00  NULL
   AttributeSetStorage              @0x0F08  NULL
   AttributeSetHealthStorage        @0x0F10  NULL
```

So the earlier "…Storage naming implies the constructor builds them" reasoning was wrong. `schema.txt` says why:
the real owner is **`LokiPlayerState_HeroAffiliated`** — a companion **Actor** (same pattern as
`LokiPlayerState_Missions` / `LokiPlayerState_Stats`) carrying:

```
AbilitySystemComponent   AttributeSet   AttributeSetHealth   PlayerInventory
```

`LokiCharacter`'s three `…Storage` fields are **caches** pointing at that actor's objects. And:

```
--- G. THE PLAYER'S GAS CARRIER ---
   NO LokiPlayerState_* companion actors exist at all
```

Not just `HeroAffiliated` — **none of the `LokiPlayerState_*` family exists** in the force-open session. The
carrier was never created, so there is nothing for the hero to cache.

⇒ This single fact explains several things previously logged as separate mysteries: S94's "hero has no
AttributeSet", the dead FOW vision route (`FogOfWarRadius`/`FogOfWarAngle` are attributes on `LokiAttributeSet`),
and the null `…Storage` caches. They are all one absence.

## ★ The genuinely GOOD news: GAS init is NOT deploy-gated

```
--- F. WORLD SWEEP ---
   live non-CDO AbilitySystemComponents : 424
   ...with OwnerActor or AvatarActor set: 344
      0x…(LokiAbilitySystemComponent)  Owner=…(BP_PineTree_ScavBay_C)  Avatar=…(BP_PineTree_ScavBay_C)
```

**344 fully-initialised ability systems are running in this exact world, with no deploy and no server.** They
belong to level actors (the ScavBay pine trees), which build and initialise their own ASCs during BeginPlay.
`OwnerActor`/`AvatarActor` are what `InitAbilityActorInfo(owner, avatar)` populates, so this is direct proof that
`LokiAbilitySystemComponent` construction **and** actor-info init both work in force-open.

⇒ **"GAS cannot be initialised outside deploy" is dead.** The blocker is a missing *carrier object*, not a
missing capability.

## ⚠ …but the template only covers HALF the job

```
--- H. TEMPLATE: a healthy, initialised ASC ---
        SpawnedAttributes          Num=1  -> [0] LokiAttributeSetHealth
        DefaultStartingData        Num=0
        ActiveStartupEffects       Num=0
        ActivatableAbilities       no populated inner TArray
```

The healthy ASCs carry **one attribute set and ZERO granted abilities**. So they are a working reference for
*construct + init*, and **no reference at all for granting/activating abilities** — nothing in this world has an
ability granted. Attribute defaults do not come from `DefaultStartingData` either (Num=0), so they arrive via a
curve table / GameplayEffect applied at runtime.

## Where that leaves the decision

| layer | status |
|---|---|
| the hero's 27 BP components (camera, capsules, decals, aim-vis, hit-confirm, LOS, team colour, stat auras, …) | ✅ **free** — instantiated by the real class at spawn (asset `_GEN_VARIABLE` templates + S95's live census) |
| the GAS carrier (`LokiPlayerState_HeroAffiliated` + ASC + 2 attribute sets) | ❌ **absent** — nothing creates it |
| ASC construction + `InitAbilityActorInfo` | ✅ **proven to work here** — 344 live examples |
| attribute *values* (init effect / curve table) | ❓ no in-world example |
| ability **granting / activation** | ❓ **no in-world example** — new ground |

So: **not "recreate everything"**, and **not "call one init function"** either. It is one well-named missing
object plus a wiring chain, where the first half has 344 working templates and the second half has none.

Every primitive needed for the first half already exists in this project: actor spawn
(`BeginDeferredActorSpawnFromClass`/`FinishSpawningActor`), `AddComponentByClass`, and the ProcessInternal
native-call primitive. **Force-open is also the authority**, which is why objectives can complete here and cannot
on the DS route — the same reason ability *granting* should be permitted.

## Next measurements (cheap, and they de-risk the whole path)

1. **Enumerate the UFunctions on `LokiCharacter` / `LokiPlayerState_HeroAffiliated` / `LokiAbilitySystemComponent`
   for a native "wire it up" entry point** — names like `SetupAbilitySystem`, `InitAbilitySystem`,
   `OnAbilitySystemInitialized`. `BP_HERO_Ronin_C` already has a UFunction literally called
   `AbilitySystemInitialized`, i.e. the hero is *waiting to be told*. If the game has its own native wiring
   function, calling it beats hand-building the carrier.
   ⚠ `gas_recon.py` section E produced **nothing** on both runs because it keyed off the hero's ASC *instance*,
   which is null — exactly the case where the API list matters most. **Fixed**: it now resolves the UClass by name.
   Re-run to get this list.
2. **Read a healthy tree's ASC field-by-field** against a fresh one to see precisely what init touched.
3. Only then decide between building the carrier and accepting movement-only.

---

# ★★★★ S100b — THE NATIVE WIRING ENTRY POINT EXISTS. We do NOT hand-build the ability system.

The S100 section closed with "find a native wire-it-up function before hand-building the carrier". **Found it.**

★ Done at the **plain baseline menu, no force-open, no crash risk** — these are all *native* classes registered at
module load, so their UFunction tables are readable without the tutorial world. Tool: the existing
`tools/re/class_funcs.py` + `tools/re/ufunc_params.py`. Full dump: `docs/session-100-gas-api-dump.txt`.
**Remember this**: class-level questions never need a force-open session.

## The chain

`LokiPlayerState` owns the ability-system lifecycle — not the character, and not us:

| function | class | signature | flags |
|---|---|---|---|
| **`TryUpdateAbilitySystem`** | `LokiPlayerState` | `void TryUpdateAbilitySystem()` | Native |
| `ServerSetHeroClass` | `LokiPlayerState` | `void ServerSetHeroClass(Class NewClass)` | Native, BPCallable |
| `OnRep_HeroClass` | `LokiPlayerState` | `void OnRep_HeroClass()` | Native, Event |
| `HeroAffiliatedEndPlay` | `LokiPlayerState` | — | Native, Event |

`HeroAffiliatedEndPlay` confirms the PlayerState is what owns/tears down the `LokiPlayerState_HeroAffiliated`
carrier, and `TryUpdateAbilitySystem` is **parameterless and native** — i.e. directly callable through the S55
primitive with the shim's existing `CallNoArgAuto`. Nothing to hand-assemble.

Verification side, on `LokiCharacter`:

```
Bool   IsAbilitySystemInitialized()                 [Native, BPCallable]   <- the pass/fail check
Object GetLokiAbilitySystem_BP() -> LokiAbilitySystemComponent*  [Native, BPCallable]
void   RemoveFromAbilitySystem()                    [Native, BPCallable]
void   AuthInitializeExperience()                   [Native, BPCallable]
```

`LokiHeroCharacter` also has `BP_OnRep_PlayerState`, and `BP_HERO_Ronin_C` has `AbilitySystemInitialized` — so the
hero reacts to the PlayerState hand-off. The whole design is: **set the hero class on the PlayerState → the
PlayerState builds the carrier → the character caches it and fires its event.**

## And the ability API itself is fully native + BlueprintCallable

`LokiAbilitySystemComponent` exposes 69 UFunctions of its own. The load-bearing ones:

```
Struct BP_AuthGiveAbilityWithInputID(Class AbilityClass, Int AbilityLevel,
                                     Enum LokiAbilityInputID, Object SourceObject,
                                     Int InputIDPriority) -> FGameplayAbilitySpecHandle
Bool   TryActivateAbilityByInputID(Enum AbilityID)
Bool   TryEndAbilityByInputID / TryEndAllAbilities
void   K2_InitStats(Class Attributes, DataTable* DataTable)      <- attribute defaults
void   ServerSetAbilityToLevel / LevelUpAbilityByInputID
void   AdjustHealth / AdjustMaxHealth / AdjustMana / AdjustStamina / AdjustArmor
Object GetLocalLokiAbilitySystemComponentBP / GetLokiAbilitySystemComponentFromActor
```

★ The grant functions are `Auth*` / **`FUNC_BlueprintAuthorityOnly`** — which is exactly the class of function
**force-open CAN call and the DS route CANNOT** (the same property that lets `OnObjectiveComplete` work here and
not there). The route we are on is the *only* one where ability granting is even permitted.

`K2_InitStats(Class Attributes, DataTable*)` also answers the S100 open question about where attribute defaults
come from: a DataTable, not `DefaultStartingData` (which read Num=0 on every healthy ASC).

## Revised answer to "do we have to recreate everything?"

**No — and we do not even hand-build the carrier.** Concretely:

1. `PlayerState.ServerSetHeroClass(BP_HERO_Ronin_C)` — or write `HeroClass` directly, which the shim already
   does (`g_psHeroOff`, S90).
2. `PlayerState.OnRep_HeroClass()`
3. **`PlayerState.TryUpdateAbilitySystem()`**
4. verify with `hero.IsAbilitySystemInitialized()` and `hero.GetLokiAbilitySystem_BP()`
5. then `K2_InitStats` for attribute values, and `BP_AuthGiveAbilityWithInputID` per ability.

Steps 1–4 use only primitives this project already has (native-call, param passing, OUT params). Every function is
native with a live thunk.

⚠ Remaining honest risk: `TryUpdateAbilitySystem` is native and **not** BlueprintCallable, so its internals are
unread — it may early-out on state we do not have (a valid `HeroAsset`, a team, a replicated PlayerState role).
`ServerSetHeroClass` is a Server RPC by name, so on a standalone authority it should execute locally, but that is
untested here. The measured facts are: the entry point exists, it is parameterless, it is native, and force-open is
the authority. Whether it *succeeds* is one live call away — and `IsAbilitySystemInitialized()` reports the answer
in one bit.

---

# ★★★ S101 — the wiring chain RUNS CLEANLY and the bit does NOT flip. Two hypotheses falsified.

Implemented `WireAbilitySystem()` in `tools/sigbypass-mod/tutorial_launch.cpp` (flag `KWIREGAS`) and drove the
S100b chain live, staged one call at a time with the witness bit read before and after.

## Result

```
[GAS] PlayerState @0x3C0 = 0x… (BP_LokiPlayerState_C)
[GAS] BEFORE AbilitySystemComponentStorage @0xF00 = NULL   (…Storage / …HealthStorage likewise)
[GAS] BEFORE IsAbilitySystemInitialized -> 0
[GAS] step1 ServerSetHeroClass ok
[GAS] step1 HeroClass@0x620 was NULL -> poked
[GAS] PlayerState Role@0x160=3 RemoteRole@0x72=1  (3=ROLE_Authority)
[GAS] hero Role@0x160=3
[GAS] GetHeroAsset -> 0x… (BP_HeroAsset_Ronin_C)
[FOW] GAS step2: OnRep_HeroClass (native) ok
[FOW] GAS step3: TryUpdateAbilitySystem (native) ok
[GAS] AFTER  …Storage = NULL (all three)
[GAS] AFTER  IsAbilitySystemInitialized -> 0
[GAS] GetLokiAbilitySystem_BP -> NULL
[GAS] ===== RESULT: initialised 0 -> 0  *** STILL NOT INITIALISED *** =====
```

**Every call succeeded. Nothing changed.** No faults, no exceptions — the keystone simply does nothing.

## What this rules OUT (both were my stated suspicions — both wrong)

1. **"The PlayerState is not authority."** ❌ `Role = 3 = ROLE_Authority` on **both** the PlayerState and the
   hero. The prime suspect from iter1 is dead.
2. **"There is no HeroAsset."** ❌ `GetHeroAsset()` returns a valid **`BP_HeroAsset_Ronin_C`**. The hero data the
   carrier build would need is present and resolvable.

So: authority ✅, hero asset ✅, `HeroClass` set ✅, `OnRep_HeroClass` fired ✅, `TryUpdateAbilitySystem` called ✅
→ and still no carrier. The gate is *inside* `TryUpdateAbilitySystem`, upstream of everything tested.

⚠ One unexplained sub-result worth chasing: **`ServerSetHeroClass` returned "ok" but did not set `HeroClass`**
(it had to be poked) — *even with `Role == ROLE_Authority`*. A Server RPC on an authority actor should execute its
body. That suggests the thunk being called is the RPC dispatch stub and the real work lives in a separate
`_Implementation`, with dispatch dropping the call when there is no NetDriver. If so, **the same trap may apply to
`TryUpdateAbilitySystem`** — we might be calling a dispatcher that no-ops rather than the implementation.
**That is the single best lead**, and it is checkable: disassemble the `TryUpdateAbilitySystem` thunk (its page is
committed now that it has run) and see whether it is a real body or a dispatch stub.

## Best next hypotheses, in order

1. **We are calling a dispatch stub, not the implementation** — see above. Disasm the thunk; if it is a stub, find
   and call `…_Implementation` directly (the project has done exactly this kind of thing before).
2. **`TryUpdate` means update-not-create.** The name, plus `HeroAffiliatedEndPlay` being an EndPlay *handler*,
   suggests `LokiPlayerState_HeroAffiliated` is a **separately spawned actor** whose lifetime the PlayerState
   manages but does not originate. Find who spawns it (GameMode? `LokiPlayerState::BeginPlay`?) — if so we spawn
   the carrier ourselves and *then* `TryUpdateAbilitySystem` has something to populate.
3. A GameState / match-phase gate, like several other systems on this route.

## Engineering notes from this iteration

- **The wiring now lives in the `sp` shim, not `play`** (`play` is built with `-DKWIREGAS=0`). Three consecutive
  attempts died inside `play`'s `ResolvePlay` — its many full 188k-object scans make it the most crash-prone part
  of the route — **before** `DoPlay` ever ran, so the measurement never happened. `sp` reported `[SP] done`
  cleanly in every one of those same runs. Putting an experiment behind the flakiest stage wastes launches; `sp`
  already holds the possessed hero and the PC, which is all `WireAbilitySystem` needs.
- `Role` and `RemoteRole` are reflected `ByteProperty (UEnum:ENetRole)` on `Actor`; `ROLE_Authority = 3`.
- Reused helpers: `CallNoArgAuto` (auto native-vs-BP dispatch) logs under a `[FOW]` prefix — grep for `GAS step`,
  not `\[GAS\]`, or the step-2/3 lines are invisible. That cost one round of confusion.

---

# ★★★★ S102 — the thunk is NOT a stub, and the real gate is located: `PlayerState+0x4F8 == NULL`

## 1. The S101 "RPC dispatch stub" lead is DEAD

`TryUpdateAbilitySystem`'s `Func@+0xE0` thunk (rva **0x5438C20**) decodes as a textbook UE exec-thunk for a
zero-parameter native UFunction — it advances `FFrame.Code` and **tail-jumps straight to the real body**:

```asm
mov   rax, [rdx+0x20]     ; FFrame.Code
xor   r8d, r8d
test  rax, rax
setne r8b
add   r8, rax
mov   [rdx+0x20], r8      ; Code += (Code != 0)
jmp   0x56CE5F0           ; <- the IMPLEMENTATION
```

`OnRep_HeroClass` (rva 0x5438450) has the byte-identical prologue. So our `CallNativeGuarded` **does** reach the
real implementation; there is no dispatcher swallowing the call. (Also note `ServerSetHeroClass`'s flags are
`[Native, BPCallable]` with **FUNC_Net NOT set** — despite the name it is not a network RPC at all, which already
undermined the S101 theory.)

★ Both thunks were decoded **offline from `dumps/merged.dump.exe`** (file-offset == RVA). Their *implementations*
read all-zero there — packer demand-decrypt gaps — so the impl needed a live process that had executed it.

## 2. The implementation, and its first gate

`usmapdump disasm SUPERVIVE-Win64-Shipping.exe +0x56CE5F0` (live, after the sp shim had called it):

```asm
mov  rbp, rcx                  ; rbp = the LokiPlayerState
add  rcx, 0x470                ; an EMBEDDED interface subobject (secondary vtable — MI layout)
mov  rax, [rcx]                ; its vptr  (= 0x7FF6F075E020 live)
call [rax+0x10]                ; virtual slot 2
test rax, rax
jz   bail                      ; <=== GATE 1
...  call <predicate>; jz bail ; GATE 2
mov  eax,[rdi+0xc]; shr 0x1e   ; GATE 3 — bit30 of the returned object's flags (pending-kill style check)
mov  rsi,[rdi+0xb8]; jz bail   ; GATE 4
call <predicate>; jz bail      ; GATE 5
test byte [rsi+0x6e], 0x20     ; GATE 6
```

That virtual (rva **0x56BA9E0**) is five instructions:

```asm
mov  rax, [rcx+0x88]     ; rcx = PlayerState+0x470  =>  reads PlayerState+0x4F8
test rax, rax
jz   ret_null
mov  rax, [rax+0x3e8]
ret
```

## ★ 3. The measurement

```
PlayerState = 0x2B67F3AAAB0
PlayerState+0x470 = 0x7FF6F075E020   (module range -> a secondary vtable, as predicted)
PlayerState+0x4F8 = 0x0              <=== NULL
```

**`TryUpdateAbilitySystem` returns immediately at GATE 1** because `PlayerState[0x4F8]` is null, so the accessor
returns null before it can even look at `[+0x3E8]`. Every call we made was real, reached real code, and hit a
first-instruction bail.

This is consistent with everything else measured: authority ✅, hero asset ✅, HeroClass ✅ — all irrelevant,
because the function never gets past its opening virtual call.

## Next

1. **Identify `PlayerState+0x4F8`.** It is a member of the embedded interface at +0x470 (offset +0x88 within it),
   and the accessor returns `that->[0x3E8]`. Walk the reflected property list of `BP_LokiPlayerState_C` for a
   property at 0x4F8, and check whether 0x4F8 is instead a NON-UPROPERTY back-pointer (in which case find who
   writes it — likely the same code that spawns the `LokiPlayerState_HeroAffiliated` carrier).
2. If it is a back-pointer to an owner (controller/pawn/carrier) we may be able to set it directly and re-run the
   keystone — the cheapest possible test, and `IsAbilitySystemInitialized()` still reports the answer in one bit.
3. Reference: the ScavBay trees have working ASCs, so a diff of *their* init path remains the fallback template.

⚠ Tool note: `usmapdump disasm|peek` take a **process NAME, not a PID** (`disasm SUPERVIVE-Win64-Shipping.exe
+0xRVA N`), and `peek`'s third arg is a decimal count — a hex `0x10` is rejected with "bad maxhits".
