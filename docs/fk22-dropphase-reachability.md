# FK-22 — The falsification does not generalise: `SpawnPlane` is a per-variant Blueprint override, the markers exist, and the real blockers are a stalled phase machine plus empty server-authority C++ impls

> ★★ **COVERAGE UPDATE (S133, 2026-08-20).** This file files 16 `(class, func)` keys as
> **COVERAGE-BLOCKED**, most of them on `.text` page **`0x5456000`** (the five
> `AuthPlayer*` entry points and `GetLandingTeleportLocation`'s thunk `0x5456C80`).
>
> **[M] `0x5456000` IS NOW DECRYPTED — 3,860 / 4,096 non-zero in `dumps/merged10.dump.exe`.**
> S131/S132's rideable and dismount flights lit it. `0x5456C80` likewise went dark→lit from
> `s131-rideable-live` onward.
>
> ⇒ **The §2.5 re-grade this file calls "free, offline and unstarted" is now also
> UNBLOCKED**, and should be run against `dumps/merged10.dump.exe` (16,755 / 30,281 pages,
> 55.33 %) rather than the 18-image corpus those verdicts were measured on.
> ⚠ Still dark and still genuinely blocked: `0x560EE70` (the BR phase-4 body) and
> `0x55A34E0`. See `docs/fk20-coverage-settled.md` §5.2.


**Date:** 2026-08-16 — offline only, zero launches, zero injections, zero `.text` writes.
**Sources:** six independent investigation lines, each attacked by an adversarial verifier. Where a verifier refuted a line, the verifier governs.

---

## 0. Verdict

**The belief at `docs/coverage-audit-s101.md:269` is FALSE AS WRITTEN, and what replaces it is not "reachable" — it is a sharpened OPEN question with two different, measured blockers.**

Four things are settled:

1. **[M] `SpawnPlane` is not one function.** Three `Comp_GameMode_DropPlane*` Blueprint classes ship, all three are **siblings** deriving directly from native `ULokiGameModeDropPlaneComponent`, and each defines its **own** `SpawnPlane` override. There is no BP-to-BP inheritance in the family, so an S93 measurement on the `_Tutorial` override cannot transfer to the general component by any mechanism.
2. **[M] The general variant queries no markers at all.** `Comp_GameMode_DropPlane_C::SpawnPlane` is 9 bytecode entries with **zero** `GetAllActorsWithTag`; the general path's real spawn lives in `OnDeathCircleSet` (125 entries), which derives the plane path **procedurally from the death-circle radius** and also contains **zero** `GetAllActorsWithTag`. The stated fault mechanism does not exist on the general path.
3. **[M] S93's stated *reason* is refuted on its own map.** `TrainingStart`, `PlaneStartPoint` and `PlaneEndPoint` **do exist in `LVL_Tutorial`**, as literal `Tags` arrays on real actors, each in a different World Partition cell. "Markers that don't exist outside the real deploy" is false.
4. **[I, strong] S93's *observation* is confounded and was never a measurement of a null-deref.** `FAULTED` in `RM_DROPIN` is the boolean returned from a bare SEH `__except`, and the invocation primitive (`CallBPGuarded`) memcpys a captured live `FFrame` without reinitialising the region `0x48..0x78` — which holds `FlowStack` and `PreviousFrame`. `SpawnPlane` is the **only** one of the three functions S93 compared that uses the flow stack (3 push / 2 pop vs 0/0 for the two that "ran clean"). The confound tracks the result exactly and was never controlled.

But **"reachable" is NOT established**, and nothing here supports flipping the row to reachable. Two blockers are measured and neither is about markers:

- **[M] The round phase never advances.** `Setting Phase to` occurs **193 times across the log corpus and every one reads `1 (BeginInit)`**. The drop needs phase ≥ 4 (`EGP_SpawnSelect`); the component's own handlers act on 5/6/7.
  ⚠⚠ **SHARPENED BY §8.5 / §9.1 — do NOT restate this as "the phase machine never leaves BeginInit", which is how it was first written here.** That log line prints **`GoToPhase`'s ARGUMENT**, before the old==new test, and `GoToPhase` is its sole emitter image-wide ⇒ **193/193 measures that `GoToPhase` was only ever INVOKED with 1 — a fact about its seven callers.** Separately [M]: the only compiled store to `CurrentPhase` (`+0xA44`) in the decrypted `.text` is a constructor init. ⚠ Bounded: 45 % of `.text` is undecrypted and `CurrentPhase` is **replicated**, so the net serializer writes it by computed-offset memcpy no literal-displacement scan can see. **The honest form is "no compiled runtime store exists in the decrypted image", never "the byte can never change".**
- **[M] Empty server-authority C++ impls sit at the player→plane and pod→hero handoffs.** Over the 8 drop classes, **exactly 100 distinct (class, func) keys**: 51 REAL, 14 BlueprintImplementableEvent, **13 EMPTY** (11 by direct call to a universal fold + 2 via vtable), 16 coverage-blocked, 4 real-but-inlined, 2 constant-body.

**Edit the line.** Replacement wording for `docs/coverage-audit-s101.md:269`:

```
| Drop-in / DropPlane | **OPEN — the S93 falsification does NOT generalise (FK-22, 2026-08-16).**
`SpawnPlane` is a per-variant BP override; 3 sibling variants, no BP-to-BP inheritance. The GENERAL
variant queries no markers (9 stmts, 0 `GetAllActorsWithTag`; its spawn is in `OnDeathCircleSet`,
derived from the death circle). The Tutorial variant's 3 markers **DO exist** in `LVL_Tutorial`
(`Tags` arrays, 3 separate WP cells) — S93's stated reason is refuted; its fault was an SEH catch
through a primitive with an uninitialised `FFrame.FlowStack`. Measured blockers are elsewhere:
the round phase never leaves `EGP_BeginInit(1)` (193/193 logs) and the player→plane / pod→hero
handoffs are empty C++ impls. | S93 / FK-22 |
```

⚠ **The ignorance map's own citation is wrong**: `docs/ignorance-map-s101.md:1407` quotes the belief as `coverage-audit-s101.md:229`. It is **line 269**. Fix while editing.

---

## 1. What the belief was and where it came from

`docs/coverage-audit-s101.md:269`, verbatim (em-dash, not hyphen):

> `| Drop-in / DropPlane | **FALSIFIED as reachable** — `SpawnPlane` faults on absent level markers | S93 |`

Its source, `docs/session-93-objectives-camera-deploy.md:34-36`, verbatim:

> `**Drop-in descent (DropPlane)** — `Comp_GameMode_DropPlane_Tutorial.SpawnPlane` (BP event) **FAULTS** (null-deref reading `GetAllActorsWithTag` drop-path markers that don't exist outside the real deploy). `AddPlayerToDropPlane` (native) + `GetAutoDropLocation` run clean but no-op. The full descent needs the server round context. (RM_DROPIN=20)`

The source is scoped to one component variant on one map, invoked through one shim mode. The audit line drops the variant name, drops the map, drops the invocation, and promotes it to a subsystem-wide falsification. `docs/ignorance-map-s101.md:1413-1416` also records that S93 elsewhere describes the same call as *"fed WRONG arg types"* / *"faults on an empty param buffer"* — a second, instrument-side explanation that was never reconciled with the marker one.

⚠ The repo already half-contained the answer and never propagated it: `docs/angelscript-dropphase.md:895` opens **"The plane's path does not need level markers."** and `:901` closes with **"The S93 'SpawnPlane faults on absent level markers' wall has a documented bypass."** — while `coverage-audit-s101.md:269` still reads FALSIFIED. (⚠ One bypass on that list, `ALokiDropPlane::OverridePlaneLocations`, is one of FK-1's four empty stubs and is dead; the list should not be cited unqualified.)

---

## 2. The evidence, line by line

### 2.1 Line 1 — the tutorial `SpawnPlane` bytecode

**Confirmed [M]:**
- Three `GetAllActorsWithTag` **call nodes** (unit: bytecode nodes; the raw text shows 12 lines because of the `CallFunc_..._OutActors*` locals) with literal `EX_NameConst` tags `TrainingStart` (`bpdump_SpawnPlane_TUTORIAL.txt:90`), `PlaneStartPoint` (`:165`), `PlaneEndPoint` (`:238`). No property indirection — no CDO default to look up.
- Each `OutActors` is consumed by `Array_Get(arr, EX_IntConst 0)` (`:105-111`, `:180-186`, `:253-259`) feeding a non-fail-silent `EX_Context → K2_GetActorLocation`. **`EX_JumpIfNot` = 0, `Array_IsNotEmpty` = 0, `Array_Length` = 0, `IsValid` = 0** across the whole 49-node function. Properly controlled: the **same asset, same dumper** scores `EX_JumpIfNot 5 / Array_IsNotEmpty 4 / IsValid 4` on `GetAutoDropLocation`.
- The tail is a real hookup, not a stub: `SetDoublePropertyByName(AllowedJumpTime)` / `SetVectorPropertyByName(StartLocation, EndLocation)` (`:405-441`), `FinishSpawningActor` (`:471`), three `EX_BindDelegate` (`:494-593`), and `EX_FinalFunction StackNode: SetDropPlane` (`:645-651`). `SetDropPlane` is native — `binds_members.csv:42477` `void SetDropPlane(ALokiDropPlane DropPlane)`, owner `ULokiGameModeDropPlaneComponent`, offset `0x4aa77f`.
- **`BP_DropPlane_Straight_Tutorial_C` → `BP_DropPlane_Base_C` → `/Script/Angelscript.LokiDropShip`** (both `@imports` runs reproduced by the verifier). This **closes an explicitly-open question at `docs/angelscript-dropphase.md:961`** ("The exact BP that subclasses `ALokiDropShip` was not identified"). ⚠ Provenance correction: `SpawnDropPodForTeam` is **not** in `binds_members.csv` (0 hits); it is declared at `tools/asdump/out/GameMode/DropPhase/LokiDropShip.as.txt:123`.

**REFUTED — "the marker dependence is EXCLUSIVE to the Tutorial variant".** The verifier dumped `Comp_GameMode_DropPlane_PvE_Holdout_C::SpawnPlane`: **49 entries, the identical six `EX_NameConst` values, 3 `GetAllActorsWithTag`, 3 `Array_Get`, 0 guards**, differing from the Tutorial body in exactly **two diff hunks** — the `Outer class` header and one object constant (`BP_DropPlane_Straight_Tutorial_C` → `_Holdout_C`). The line's own open item (5) conceded PvE_Holdout was never examined and the claim was graded [M] with a universal quantifier anyway. ⇒ **2 of 3 variants read markers; the general one is the odd one out.** (A PvE Holdout mode reading a tag named `TrainingStart` is itself evidence this block is copy-paste boilerplate.)

**Downgraded [M] → [I] — "neither unguarded operation crashes; missing markers cannot prevent the spawn".** The string evidence reproduces exactly in `dumps/merged2.dump.exe` (UTF-16LE: `Attempted to access index %d from array` @ `0x80fc830`; `Accessed None trying to read property` @ `0x773ac80`; `Accessed None` @ `0x773ad00`; controls `LogScript` = 6, bogus token = 0), and the verifier strengthened it with the full `FBlueprintExceptionInfo` key table (`ArrayGetOutofBounds` @ `0x773a860`, `AccessNoneContext` @ `0x773ac58`, `AccessNoneNoContext` @ `0x773acd8`). **But no xref was taken from any string to a code path, no exception type was established, and the same block contains fatal-class entries** (`Assertion failed, line %i` @ `0x773a598`, `Execution beyond end of script` @ `0x773a540`) — co-presence in `.rdata` does not discriminate warn-from-fatal in *this* build. Two sub-clauses are also plainly false: `StartPos`/`EndPos` **are** read between the lookups and the spawn (node [23] `MakeTransform`, nodes [29]/[30] `SetVectorPropertyByName`), and they are **rewritten** at nodes [16]/[21] from the `K2_GetActorLocation` returns — so the pre-zeroing at [1]/[2] is not what produces the origin outcome.

**[I] The invocation confound.** `tools/sigbypass-mod/tutorial_launch.cpp:26` defines `FF_MRPC=0x40, FF_OUTPARMS=0x80` and **nothing in `0x48..0x78`**; `:88` `g_template[0x180]`; `:979` `memcpy(g_template, frame, sizeof(g_template))` inside the PI hook; `:945-951` copies the template and overwrites only 9 fields. Flow-stack counts: Tutorial `SpawnPlane` **3 push / 2 pop**; `GetAutoDropLocation` **0/0**; general `SpawnPlane` **0/0**. The verifier confirmed the unstated premise the argument needs — `tutorial_launch.cpp:4141-4147` calls `CallBPGuarded` on `SpawnPlane` and `:4162` on `GetAutoDropLocation`, so both went through the same primitive and the flow-stack asymmetry **is** the discriminating variable — and added the decisive one: **`FAULTED` at `:4146` is only the boolean returned from `__except(SehDump(...)){ return true; }` (`:955`, `SehDump` at `:884`).** ⇒ S93's "null-deref reading `GetAllActorsWithTag` markers" is an **attribution laid over a bare SEH catch**, not a measurement of the fault site. ⚠ Weakness that keeps this [I]: "FlowStack occupies `0x48..0x78`" is stock-UE5 layout inference, unverified in this build, and `PreviousFrame` is equally uninitialised in that range — so the confound is broader and less specific than stated.

**REFUTED — "`GetAutoDropLocation` returns with `RandomLocation` never written".** Node [27] (`:456-465`) is an **unconditional** `EX_Let` into `EX_LocalOutVariable RandomLocation`, inside the same unguarded run the claim itself identifies. The out-param **is** written (with the zero the skipped context left behind), so "no-op" survives in substance but the mechanism as written does not. What does survive and is load-bearing: node [26] (`:434-455`) is structurally identical to `SpawnPlane`'s nodes [9]/[15]/[20] — **the "runs clean" function contains the same unguarded null-`EX_Context` shape the "faulting" one was blamed for.**

### 2.2 Line 2 — the general component and the family

**Confirmed [M], independently re-run by the verifier:**
- **Exactly 3** `Comp_GameMode_DropPlane*` `.uasset` files ship (unit: files) — 34,130 / 27,526 / 27,681 B — plus a parallel 3-file `Comp_PlayerState_DropPlane*` family.
- **All three BlueprintGeneratedClasses print `SuperStruct -> name='LokiGameModeDropPlaneComponent' path='/Script/Loki.LokiGameModeDropPlaneComponent'`** — siblings, not a chain. Each exports its own `SpawnPlane` with `SuperStruct -> /Script/Loki.LokiGameModeDropPlaneComponent.SpawnPlane`. **This is the load-bearing structural fact of FK-22** and it is established without reference to reachability, so it is not circular.
- `Comp_GameMode_DropPlane_C::SpawnPlane`: 9 entries — `StartPos=(0,0,0)`, `EndPos=(0,0,0)`, `SelectedDropPlaneType=BP_DropPlane_Straight_C`, `EX_BindDelegate OnDeathCircleSet`, `EX_AddMulticastDelegate` onto `GetLokiGameState().OnDeathCircleSet`, `ReturnValue=DropPlaneVar`, return. `GetAllActorsWithTag` = 0, controlled against 12 matching lines in the Tutorial dump.
- **Function inventories differ by class, not by override**: `OnDeathCircleSet` exists **only** on the base (absent from both variants' 11-function export lists); `GetAutoDropLocation` and `OnGameEvent_OnBattleRoyalePlayerPhase_PlayerState` exist **only** on the two variants (absent from the base's 10). ⇒ **S93's second observation, "`GetAutoDropLocation` runs clean but no-ops", is about a function the general component does not have.** This is the sharpest single refutation of the audit line.
- `Comp_GameMode_DropPlane_C::OnDeathCircleSet` (125 entries, 1800 dump lines): `GetLokiDeathCircle → IsValid → EX_PopExecutionFlowIfNot`; `CircleRadius = DeathCircle.Radius`; `CircleStartingLocation = Array_Get(CirclePhases,0).TargetLocation`; offsets from `BPFL_Math_C::GetRandom2DVectorInRadius` (lines 912, 1020); `BeginDeferredActorSpawnFromClass` (1111) → `SetDoublePropertyByName`/`SetVectorPropertyByName` → `FinishSpawningActor` (1254) → `DropPlaneVar = LocDropPlane` → `SetDropPlane`. **`GetAllActorsWithTag` = 0.** Plane type is picked by a feature toggle: `GetFeatureToggleWithDefaultFallback(self, EX_ByteConst 146)` gating `BP_DropPlane_SpinningDonut_C`, else `GenerateFromClass(LT_DropPlanes_C, -1)`; enum 146 = `PieSlicePlane` (`tools/re/out/game_feature_toggle_enum.txt:165`).
- Native base `ULokiGameModeDropPlaneComponent` exposes `GeneratePlanePoints(OutStartPos, OutEndPos, CircleRadius=42000, Height=21000, MaxEndOffsetDeg=50)` plus `bUseOverrideLocations` / `OverrideStartAngleDeg` / `OverrideEndAngleDeg` (`binds_members.csv:42475-42486`; `binds_types.csv:9099` = 4 methods, 8 properties; usmap says 9 UPROPERTYs — the extra is `EarlyJoinControllers`). All inputs are scalars: a **marker-free procedural path generator**.
- **No Angelscript calls `SpawnPlane`** — 1 file corpus-wide (`binds_members.csv`), 0 under `modules/` (78 files). The verifier replaced the weak control (`DropShip` finds module files) with the right one: `FinishDropPhaseHiding`, a **bound C++ member name**, IS found at a call site in `LokiDropPod.as.txt`. Stronger than claimed: **none** of the component's 8 members appears anywhere in the AS modules tree.

**REFUTED — "`OnDeathCircleSet` early-outs on `IsValid(GetLokiDeathCircle())`".** The verifier traced the flow stack: statements [0]-[3] push 4061 / 2249 / 1459 / **314**; the `EX_PopExecutionFlowIfNot` at [6] pops **314**, which is statement [14] — **the same point execution reaches anyway** via the `EX_PopExecutionFlow` at [13]. The `IsValid` test guards only the radius/starting-location reads ([7]-[12]); the function **continues toward the spawn with those values at defaults**. Whether the spawn is actually reached on the false path was not traced (a second `EX_PopExecutionFlowIfNot` exists at [46]) — **not established.**

**Instrument caveat [M]:** `extractor wherefile` hard-caps at `.Take(20)` **before** computing `hits.Count` (`Program.cs:840-844`), so `'DropPlane': 20 hits` is saturated and uninterpretable. Only counts strictly below 20 are real. Same family as the documented `obj_by_class.py` cap-at-60. (A second, **unclamped** copy of the pattern exists at `Program.cs:809-810` in a different subcommand — the clamp is not a property of the file.)

### 2.3 Line 3 — the marker census

**Confirmed [M], and the verifier re-ran the whole census independently:**
- Denominator re-derived from `dumps/extractor-out-PREFIX14/allfiles.txt`: **7,300 `.umap` packages** (unit: packages), 7,300 distinct, 0 colliding basenames. All 7,300 parsed via `extractor names`, **7,300 OK / 0 FAIL**.
- **Exactly 9 packages** carry one of the three tags, across 5 maps: `LVL_Tutorial` (all three), `LVL_Holdout` (all three), `LVL_Battleships` (`PlaneStartPoint`), `LVL_Practice.umap` and `LVL_Tutorial_Gameplay.umap` (`TrainingStart`).
- **`Skylands_WP` carries NONE** — 0 hits in 2,216/2,216 parsed packages, exact-line and loose-substring. `LVL_SkylandsBreach` likewise. **This is the opposite of the outcome the question anticipated** ("BR map has them, tutorial doesn't").
- The actors are a **copied template**: `PlaneStartPoint` = `Actor_UAID_709CD165B93A5A6302_2139613882` byte-identically in Tutorial, Holdout **and** Battleships; `PlaneEndPoint` = `…5B6302_1084782059` in Tutorial and Holdout; and (unreported by the line, found by the verifier) `TrainingStart` = `BP_LokiPlayerStart_C_UAID_…7B4E02_1381150554` identically in Tutorial and Holdout. ⚠ The UAID identity is [M]; *"a copied level-design template rather than a tutorial peculiarity"* is [I] — identical UAIDs are equally consistent with a shared level-instance source.
- **The cells are `WorldPartitionLevelStreaming_*` streaming cells** — `LVL_Tutorial.umap.names.txt` contains all three by name alongside `WorldPartitionLevelStreamingPolicy`. **"Present in the shipped map" and "loaded when `SpawnPlane` ran" are different claims and only the first is established.** This self-limitation is what keeps the finding from being FK-22's error in mirror image.
- **The Angelscript layer references none of the three tags** — 0 of 331 files, with both controls firing on the identical corpus.

**Instrument artifact caught in-session [M]:** the first tag test searched 3,100 already-dumped `.umap` name tables and returned 0 for all three — but **0 of the 67 `LVL_Tutorial` cells were among those 3,100** (`comm -12` = 0 overlap). Pure coverage. After dumping all 67 the answer inverted to 3/3. Also: the **persistent** `LVL_Tutorial.umap` (693 names) lacks all three while containing live controls — **the persistent map alone is the wrong instrument for a World Partition level.**

**REFUTED — "`namesall Skylands_WP` reports '0 assets'".** The code half is right (`Program.cs:1072` filters `.EndsWith(".uasset")`, so `namesall` is structurally blind to `.umap`), but the *measurement* is false: `allfiles.txt` contains **121** paths matching `Skylands_WP*.uasset`, and `namesall` matches `f.Contains(substr)` over the whole path, so it would print `121 assets`. A statement graded [M], implying it was run, is contradicted by the shipped file listing.

**REFUTED — "`GetAutoDropLocation`'s targets exist in Skylands_WP but not LVL_Tutorial".** The `BP_BattleRoyaleSpawner_BossLocation_C` half holds (38 of 2,216 Skylands cells, 0 of 68 Tutorial packages). The **`LokiCapturePoint` half does not**: exact-line `LokiCapturePoint` occurs in **0 of 2,216** Skylands name maps. Worse, the method is structurally blind here — a native class's instances in a cooked map are Blueprint subclass objects named `BP_<X>_C_UAID_…`, and `LVL_Tutorial` **does** contain `BP_CapturePoint_Tutorial_C_UAID_60CF84A053C7077702`. Parentage could not be settled offline (a BPGC's native super is a script import resolved through the global object map, so its absence from the package name map is not decisive; control: `LokiCharacter` **does** appear in the same name map). ⇒ the second search may be non-empty on the tutorial map; **the map-specificity conclusion is not established.**

Minor: `2,559 packages` for `LVL_SkylandsBreach` is a `_Generated_`-subdirectory count presented as the map (the family has 2,723); `262,103 name rows` does not reproduce (verifier: 261,410). Neither changes the zero, which the 7,300-package sweep covers.

### 2.4 Line 4 — the Angelscript pod route

**Confirmed [M]:**
- `Default__BP_DropPlane_Base_C` serializes `TeamDropPodClass = BlueprintGeneratedClass'/Game/Loki/Environment/DropPlane/DropPod/BP_DropPod.BP_DropPod_C'` (`bpdump_BP_DropPlane_Base_PROPS.txt:33`, inside the CDO block). **Precondition #1 of `SpawnDropPodForTeam` is satisfied from shipped data.** ⚠ Restrict to `BP_DropPlane_Base_C` + `BP_DropPlane_Expanding_C` — the other variants were checked only with the name-table test that this same line disproves (see below), so they are **unchecked, not clear**.
- `BP_DropPod_C`'s SuperStruct is `Class'LokiDropPod'` at `/Script/Angelscript`; its CDO sets `CrewDropPodClass = BP_DropPod_Child_C`, `ImpactIndicatorClass = GIE_DropPod_Impact_WASDIndicator_C`, `GroundLaserIndicatorClass = BP_DropPodLaser_C`. **The shipped pod IS the Angelscript class.**
- **`SpawnDropPodForTeam` has exactly two bail points and no marker query of any kind** (`LokiDropShip.as.txt:178`, 150 dwords / 95 instructions): `+0x0034` `TSubclassOf::opEquals` → `+0x0050 SetV1 v3 0`; `+0x00CC CmpPtrNull v6` → `+0x00D8 SetV1 v3 0`; returns true at `+0x0248`. Every other conditional (`+0x0188`, `+0x01AC`, `+0x01D8`, `+0x0220`) skips a call rather than returning. **The two `FVector` arguments are the only spatial input.** This is the claim that most directly bears on FK-22 and it is measured.
- **The dropship can be skipped.** `InitializeDropPod` uses `DropShip` only inside `if (bIsTeamLeaderPod) QueueCrewForPodSpawn(DropShip)` (`+0x0098 JLowZ → L00B0`), and `QueueCrewForPodSpawn` tests `+0x00F8 CmpPtrNull v30 / +0x00FC JZ → L0118` before its only deref. `LokiDropPod.as.txt:3938` passes a literal `nullptr` DropShip. ⚠ Caveat that must travel with it: on that shipped path `bIsTeamLeader=false`, so the null-DropShip guard is **never exercised by shipped code** — the guard's existence carries the claim, the "shipped `nullptr`" rhetoric adds nothing.
- `ALokiDropPod::LokiBeginPlay` auto-starts: `+0x0074 CMPIi v2 0 / +0x007C JS → L0098 / +0x0088 CALLINTF StartPodGameplay`, else defers to `OnTeamIndexChanged`.
- **10 newly-recorded empty impls** (13 FOLD minus FK-1's 3 known) on this surface, on an instrument that reproduces all three of FK-1's recorded stubs at their exact addresses in one pass, with re-computed stride arithmetic (18.0 / 6.0 / 17.0 exact multiples of 0x48).
- **`ULokiGameModeDropPlaneComponent::SpawnPlane` is NOT registered as a native** — the class registers 3 natives (`SetDropPlane`, `AddPlayerToDropPlane`, `GeneratePlanePoints`) and `SpawnPlane` is not among them. Corroborated by a second, differently-failing instrument: `uht_funcflags_tuthero.csv` carries one `SpawnPlane` row with **no `Native` flag**.

**Downgraded / REFUTED:**
- **"`TeamDropPodClass` is declared on exactly one class in the entire game" → [I], scope wrong.** The greps re-derive, but the control shape was wrong (the stated control returned *method* rows, not property rows; the verifier had to build the real one: 13,734 property rows exist, and `ALokiDropPlane` itself has 12). And "the entire game" / "the real C++ bind table" is not what those files are — `binds_members.csv` is the **Angelscript bind** table and `as_schema_full.csv` the AS schema; a native UProperty never bound to script appears in neither. `BP_DropPlane_Base_C : ALokiDropShip` is an **inference from property ownership**; the SuperStruct was never read, though the line proves elsewhere that read is cheap and decisive.
- **"`BP_DropPod_C` carries EVERY component the script dereferences, so startup cannot fault" → [I].** Four unguarded deref sites confirmed; **no exhaustive census, and no control showing the method would find a missing component.** Also a citation slip: `+0x0148` is `PshVPtr v10`, not `CALLSYS Deactivate` — a byte string printed next to an address it did not come from, the exact defect `fk1-stub-claim-recheck.md` §5 exists to stop.
- **"A NULL drop leader is SAFE" → [I].** Two legs confirmed by disassembly (`0x055cd510` really does begin `test rdx,rdx / je`; `RemovePlayerFromPlane` impl `0x00f7ec20` = `c2 00 00` = `ret 0`, control `0x00f7eb50` = `33 c0 c3`). But `SetPilotPlayerState` (`0x055e59e0`) is **not** "a plain store" — it is four instructions ending in a **tail call** to `0x1e3ccd0` with `rdx` reloaded from `[rcx+0x30]`; the safety conclusion survives, but by a different and stronger argument than the one given. And a **fourth** unguarded use was missed (`InitializeDropPod` does `SetOwner(GetPilotPlayerState())`). Incomplete enumeration ⇒ synthesis is [I].
- **"NEW WALL: `AuthBeginGlideDiveFromDropPod` has no shipped path" → [I].** The measurement is [M] (`impl=0x00f7ec20 FOLD`; `EndGlideDive impl=0x055a8580 REAL 1296B`; `GetDropPlaneCustomMovementMode REAL 64B`). **"No shipped path" is a universal negative with no enumeration and no control** — the caller was never located, `grep -rn "GlideDive" tools/asdump/out/modules/` returns **zero** (so this handoff is not on the script path at all), and native/BP alternatives (e.g. `SetMovementMode(MOVE_Custom, GetDropPlaneCustomMovementMode())`) were never excluded. A 1,296-byte real `EndGlideDive` is affirmative evidence the state machine has *some* live entry.
- **"The pooled-spawn precondition is MAP-INDEPENDENT" → [I].** The log lines are exact (`fk11-live-result-20260809.log:1034/1037/1038` register three drop-pod classes poolable, 29.18 s before `:1443 LoadMap: LVL_Login`) and `SpawnPoolableActorFromClassDeferred`'s impl is a real 310 B function. **But registration of poolable classes says nothing about whether the spawn needs a `UWorld`**, and `0x338bd10` was never traced. Correctly-calibrated instrument, wrong question (FK-38). Also "on a plain `-NoHook` launch" is not readable from that log.

**★ The best instrument finding of the whole investigation [M]:** **an IoStore package's `.names.txt` is NOT a presence test for a serialized property.** `BP_DropPlane_Base.uasset.names.txt` has 267 names and **does not contain `TeamDropPodClass`**, while `bpdump @props` on the same asset shows the CDO setting it. Unversioned property serialization resolves names by usmap/schema index, so inherited property names need not enter the package name map. The line had even constructed a **false positive control** from `MaxDropPodDistance` being present. **Use `bpdump @props`, never a name-table grep, for "is this property set?"** — this belongs in `docs/method-rules.md` §1.

### 2.5 Line 5 — the native stub audit (the most rigorously verified line)

The verifier rebuilt the 18-image `.text` union independently (178,130,944 B images, `.text` 16,653 / 30,281 pages = 54.99 %, **0 page conflicts across 5 distinct ImageBases**) and re-disassembled every load-bearing thunk.

**Confirmed [M]:**
- **Exactly 100 distinct `(class, func)` keys** over the 8 drop classes: REAL 51 · BlueprintImplementableEvent 14 · EMPTY-STUB 11 · EMPTY-VIA-VTABLE 2 · COVBLOCKED-THUNK 11 · COVBLOCKED-IMPL 5 · REAL-INLINED 4 · CONST-BODY 2.
- The 13 empties, each verified to end its marshalling in a **direct** `call 0xf7ec20` (`= c2 00 00 = ret 0`): `ALokiDropPlane::{AddPlayerToPlane, RemovePlayerFromPlane, AuthStart, SetCanJump, OverridePlaneLocations}` · `ULokiRideableComponent::{AuthAddPlayer, AuthRemovePlayer, AuthSetCanJump}` · `ULokiPlayerDropPlaneComponent::{AuthSetCurrentRideable, OnPlayerExitedDropPod, ServerPassDropLeader, ServerSetDropPodDestination}` · `ALokiTeamState_TeamOnly::SetDropLeader`. Contrast control in the same run: `AddPlayerToDropPlane` and `AddTeamDropEvent` end in direct calls to real bodies, so the last-direct-call rule is not vacuous.
- The two RPC verdicts were taken through the **class vtable** because their `_Implementation` is virtual: `ULokiPlayerDropPlaneComponent` vtable `0x8a22520` — `+0x4c0 ServerLaunchDropPod = 0x56face0 REAL`, `+0x4c8 ServerPassDropLeader = 0xf7ec20`, `+0x4d0 = 0x56f26a0`, `+0x4d8 = 0x56df250`, `+0x4e0 ServerSetDropPodDestination = 0xf7ec20`, `+0x4e8 = 0x56fae90`. Identity control 3/3 against independently-derived impls, and the verifier added the control the line lacked: **each of those four impl addresses occurs exactly once in the whole 178 MB image**, all inside `0x8a22520` ⇒ no derived vtable copies them, the class is the C++ leaf, the slot IS the final `_Implementation`.
- **Name trap:** `ALokiDropPlane::AddPlayerToDropPlane` **does not exist**. `ALokiDropPlane::AddPlayerToPlane` is EMPTY; `ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` is REAL (impl `0x55cbb60`, five contiguous `.pdata` fragments totalling 331 B — label it a *merged* extent, not a `.pdata` entry size). S93 named the real one; the empty one is the plane-side call it would have to reach.
- **`ALokiServerAnalyticsManager::AddTeamDropEvent` is REAL** — impl `0x557eae0`, `.pdata` single entry 926 B, prologue `mov rax,rsp; mov [rax+0x10],rbx` — a falsified expectation, honestly reported. Server-side *analytics* is compiled in even though server-side *authority* is not.
- **`AuthPlayerEnterWorldAttachedToRidable` is COVERAGE-BLOCKED and the blocked/covered split is a `.text` PAGE BOUNDARY, not a semantic one.** Page `0x5456000` reads covered=0 in all 18 images and holds **7** thunks — the five `AuthPlayerEnterWorld*`/`AuthPlayerPreSpawn*`/`AuthPlayerDetach*` entry points **plus the plain getters `ContainsPlayer` and `GetLandingTeleportLocation`**. Reading "the Auth functions are blocked" as meaningful would be an instrument artifact. **This is the correctly-refused negative of the whole investigation and it is what constrains the stub conclusion.**

**Downgraded / REFUTED:**
- **"The 13 are *precisely* the actor-authority API" → [I].** Falsified by the line's own table: `ALokiDropPlane::AuthLaunchDropPodForTeam` is REAL (14 B tail call), `ULokiPlayerDropPlaneComponent::AuthEnterDropPlane` is REAL (8 B setter), `AuthSetDropComplete` is REAL-INLINED. The `Auth*` prefix neither implies nor is implied by emptiness.
- **"No C++ route exists to add a player to a rideable" → NOT ESTABLISHED**, per the page-boundary finding above. 16 of 100 keys are coverage-blocked and they include exactly the player-entry entry points.
- **The 9.9× enrichment → [I].** Arithmetic reproduces exactly (Fisher one-sided p = 0.00018657; rate ratio 9.92×; drop-path denominator re-derived independently as 68 with 5 empties). **But `78/6,669 = 1.2%` (S115) excludes coverage-blocked and inlined impls while `79/10,052` does not** — same numerator over two different populations is a numerator coincidence, not a rate reproduction. And the EMPTY predicate folds `0xF7EB60` (`32 c0 c3`, *return false*) in with `0xF7EC20`, so an unknown share of the image-wide 79 is "returns false by design" — the line's own open items concede `ALokiRoundGameMode::ModeSupportsDropPlane → 0xF7EB60` is a **BlueprintNativeEvent default, not a strip**.
- **The `FUNC_BlueprintAuthorityOnly` predictor → [I].** The `(class,func)` unit is sound (41/140 = 29.29 % vs 276/10,633 = 2.60 %). The **distinct-thunk sub-table is not a partition** — its EMPTY cells sum to 87 against 79 distinct empties image-wide, because ICF folding puts single thunks in multiple categories (`0x2c2ce30` is the registered thunk of 23 keys, `0x5254180` of 92). `WITH_SERVER_CODE` remains [I]; no build-configuration artifact was read.
- **REFUTED — the attack on FK-1's `.data` record instrument.** The verifier read all four gold records straight out of `dumps/tutorial-hero` at S115's documented offsets and got **4/4**, exactly as `docs/fk1-stub-claim-recheck.md:271-277` records (`0x9BDB230` `SpawnPlayer` +8=`0x534c070` +0x10=`0xf7eb50`; `0x9BD4B08` `OverridePlaneLocations`; `0x9C14FA0` `AuthSetSpawnTeamLeader`; `0x9C29F50` `SetDropLeader`). The gate failure belongs to the line's **re-implementation** (record detection / class attribution), and gate (b) scored against `impl_of` disassembly as ground truth — an instrument this same line establishes is defective, with the printed disagreements bearing that out. The evidence text also says "SpawnPlane not recovered" when the gold row is **SpawnPlayer** — the exact confusable pair the line's own name-trap finding exists to disambiguate. ⇒ **`fk1-stub-claim-recheck.md` §5.2 stands.**

**Two more instrument corrections [M], both real:**
- `tools/re/exec_chain_grade.py:363-369, 435-446` resolves indirect calls through `vtables.idx`; grading EMPTY off that inflates the image-wide count **79 → 464** distinct thunks (5.87×), because abstract interface bases legitimately hold return-false folds. **EMPTY must require a direct call/jmp to a fold, or a vtable read with a local identity control.**
- `impl_of` returns `ELIMINATED` for MSVC-inlined tiny members, which would have added **5 false stubs**. Verified byte-for-byte: `AuthSetDropComplete` ends `mov byte [rcx+0xd0],1; ret`; `GetDropComplete` `movzx eax,byte [rcx+0xd0]; mov [r8],al; ret`; `GetDropPod` `mov rax,[rcx+0x110]; mov [r8],rax; ret`; `CanExit` `movzx eax,byte [rcx+0x118]`; `GetDropPlaneCustomMovementMode` `mov byte [r8],4; ret`; and `BroadcastEventRouterReady`'s `0x56dd340` is `test rdx,rdx; jne 0x542b370; ret`.

### 2.6 Line 6 — callers and gating (the decisive line)

**Confirmed [M]:**
- **`BP_LokiGameMode_Tutorial_C` — the mode the tutorial actually runs (394 occurrences in the docs log corpus) — carries `Comp_GameMode_DropPlane_Tutorial`** as both a `GEN_VARIABLE` CDO subobject (`BP_LokiGameMode_Tutorial.json:650-651`) and an SCS node (`:4498-4509`), and overrides `ModeSupportsDropPlane` (`:47`, `:3093-3098`).
- **`BP_LokiGameMode_Tutorial_C::ModeSupportsDropPlane` returns hardcoded `EX_True`** (3 statements). The BR override is `BooleanAND(bModeSupportsDropPlane, Comp_GameMode_DropPlane.bModeSupportsDropPlane)` (4 statements) — which also independently confirms **the BR mode owns the *general* component**.
- **`ULokiGameModeDropPlaneComponent::SpawnPlane` flags `0x08080800` = `Event|Protected|BlueprintEvent`, no `Native` bit** (`uht_funcflags_tuthero.csv:11545`).
- The gate value is `EGP_Lineup = 6`. Tutorial `OnRoundPhaseChanged` (ubergraph@1403) tests `NotEqual_ByteByte(NewPhase, ByteConst 6)` → `JumpIfNot 1449` → PlayerArray loop → `EX_FinalFunction AddPlayerToDropPlane`. The BP event `On Round Phase Changed` (ubergraph@545) switches 5/6/7, with 6 → `LokiGameMode->GoToPhase(7)`.
- **★ THE PHASE MACHINE NEVER LEAVES `EGP_BeginInit(1)`.** Verifier's re-derivation: **193 log files** (104 distinct by md5); `Setting Phase to` = 193 × `1 (BeginInit)`; a whole-corpus grep for `ERoundPhase::EGP_` returns **193 occurrences, all BeginInit** — zero `SpawnSelect` / `Lineup` / `Combat` / `Pre` anywhere. The docs half is 1:1 (63 logs reach `Load map complete .*LVL_Tutorial`, 63 emit a transition, all `EGP_ServerStartup → EGP_BeginInit`). ⚠ The line's "128 runs" is a retyped, unre-derivable number (the dumps half is 130, not 65) and the unit is **log files**, not runs.
- **★ The markers are `Actor.Tags` entries** — this closes line 3's open item (2). In each cell's `*_umap.json` the string sits in an actor `"Tags": [ "..." ]` array; `D0E5AKNE…` additionally carries `"RespawnTag[8]": "TrainingStart"`. Tag source re-verified: the three `EX_NameConst` at dump lines 90 / 165 / 238.
- **Two backend-reachable phase write paths, both `Final|Native|Public|BlueprintCallable`**: `ALokiRoundGameMode,GoToPhase,0x04020401` (`:2593`) and `ALokiGameState,BP_AuthSetCurrentPhase,0x04020401` (`:1682`). ⚠ **Name trap: the C++ declaration is `AuthSetCurrentPhase`, the registered UFunction name is `BP_AuthSetCurrentPhase`** (`binds_members.csv:42742` shows both columns) — calling by the C++ name would fail.
- `ReceiveBeginPlay` performs real setup and subscribes the phase delegate behind `ULokiBlueprintLibrary::ServerOnly` (`NotEqual_ByteByte(OutputExecs, 1)` → `JumpIfNot 2273` → `BindDelegate OnRoundPhaseChanged` + `AddMulticastDelegate` onto the GameState).
- `BP_LokiBattleRoyaleGameMode_C::CheatAdvanceRoundPhase` documents the intended ladder — `GoToPhase` with `ByteConst` 4, 6, 2 — behind `CheatsEnabledOnly` (binds method **#18**, a *different* function from `CheatsEnabled` #17 that CLAUDE.md records as folding to `xor al,al; ret`; #18's fate was **not** verified).
- The client half is Angelscript we possess: `Comp_PlayerState_DropPlane_C : LokiDropPhase_PlayerStateComponent` (`/Script/Angelscript`, `module_index.txt:3992`, 19,536 bytes) over native `ULokiPlayerDropPlaneComponent`.

**Downgraded / REFUTED:**
- **"Therefore the caller is the native `ALokiRoundGameMode` phase machine" → [I].** The flags read is [M], but the **shipped Blueprint overrides both carry `FUNC_BlueprintCallable`** (visible in the bpdump headers), so a Blueprint *can* call `SpawnPlane`; the missing bit applies only to the native UHT entry. **No native caller was ever located** — no disassembly of `ALokiRoundGameMode` was performed. Plausible story, not a measurement.
- **REFUTED — "only 3 assets in the whole 68,303-file catalog mention `SpawnPlane`".** The catalog census **cannot see call sites**: `catalog/*.json` carries no `ScriptBytecode` (0 hits in both DropPlane catalog JSONs), and the decisive counter-control is that `GoToPhase` is called twice and `AddPlayerToDropPlane` once in the Tutorial component's own ubergraph while `grep -c` on its catalog JSON returns **0 for both**. The stated calibration ("the JSON contains SpawnPlane 5 times") counted **declaration/SuperStruct names** — a positive control on a different signal class than the test, which is the instrument-artifact pattern exactly. Second hole: **game-mode BPs are absent from the catalog entirely** (0 hits for `BP_LokiGameMode*`), so the census structurally excludes the assets most likely to call it. Third: the cited `rg` command is impossible — `rg` is not installed. **What survives** is a valid controlled negative over **two ubergraphs**: Tutorial (113 entries) and general (150 entries) both have `SpawnPlane` 0 / `GoToPhase` 2 / `AddPlayerToDropPlane` 1.
- **Mismatched control [I]** on the instrument-artifact finding: the quoted positive controls (`Actor`=112, `World`=77) are **substring** counts while the tag test used anchored `grep -ilx`, under which the same file gives `Actor`=0, `World`=0. A control run in a different matching mode than the test does not validate the test. (The conclusion survives because it was re-established independently.)
- Poolable-registration counts do not re-derive (98, not 93; `Load map complete` 290, not 242) and the corpus scope is unstated. The finding is also mislabelled `refutes-falsification` — "registered, never instantiated" is neutral corroboration.

---

## 3. What actually blocks the drop phase

Ordered by execution, each graded and classified. **Note that markers appear at position 3 and are satisfied.**

| # | Precondition | Status | Class |
|---|---|---|---|
| 1 | **Round phase must advance `EGP_BeginInit(1)` → `EGP_Pre(2)` → `EGP_SpawnSelect(4)`; component handlers act on 5/6/7.** | **[M] NEVER SATISFIED — 193/193 logs sit at BeginInit, zero transitions ever recorded.** The advancing condition is not named by anything read. | **UNKNOWN — the dominant blocker.** Two `BlueprintCallable` write paths exist (`GoToPhase`, `BP_AuthSetCurrentPhase`) but **their impls are UNGRADED**. |
| 2 | `ModeSupportsDropPlane()` true | **[M] SATISFIED** in the tutorial (hardcoded `EX_True`); BR is data-driven | satisfiable-offline |
| 3 | Tutorial/Holdout `SpawnPlane`: three tagged actors present **and streamed in** | **[M] present** (Tags arrays, 3 WP cells). **[S] streaming state at call time unmeasured.** | needs-a-map (loaded-state question only) |
| 3′ | General `SpawnPlane` path: a valid `GetLokiDeathCircle()` for `OnDeathCircleSet` | **[I] unmeasured**; the `IsValid` gate does **not** early-out (it pops to the same address flow reaches anyway) and the post-gate flow was not traced | needs-a-map |
| 4 | `TeamDropPodClass != nullptr` | **[M] SATISFIED** by `Default__BP_DropPlane_Base_C = BP_DropPod_C` (Base + Expanding read; other 9 unchecked) | satisfiable-offline |
| 5 | **Put a player on the plane** — `ALokiDropPlane::AddPlayerToPlane` | **[M] EMPTY** (`ret 0`) | **needs-a-stubbed-C++-fn** |
| 5′ | **Put a player on a rideable** — `ULokiRideableComponent::AuthPlayerEnterWorld{,New,AttachedToRidable}`, `AuthPlayerPreSpawnOnAddToPlane`, `AuthPlayerDetachPlayerFromRidable` | **[M] UNRESOLVABLE** — all five sit on `.text` page `0x5456000`, never demand-decrypted in any of 18 images. **Not absent; not-looked-at.** | UNKNOWN |
| 6 | Drop leader — `ALokiPlayerState::AuthSetSpawnTeamLeader`, `ALokiTeamState_TeamOnly::SetDropLeader` | **[M] both EMPTY** (FK-1 + this audit). **[I] a null leader is survivable at 3 of ≥4 known consumer sites** | needs-a-stubbed-C++-fn (but likely non-fatal) |
| 7 | Pod spawn — `ALokiDropShip::SpawnDropPodForTeam` | **[M] 2 bail points, both satisfiable; no marker query; two `FVector` args are the only spatial input** | satisfiable-offline (Angelscript, StaticJIT-compiled, callable by the S55 primitive per FK-1) |
| 7′ | **Plane bypass** — `InitializeDropPod` + `FinishSpawningActor` directly | **[M] the null-`DropShip` guard exists** (`CmpPtrNull v30 / JZ`); **[I] the sequence has never been executed** | satisfiable-offline |
| 8 | Pod → hero handoff — `ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod` and `AuthBeginGlideDive` | **[M] both EMPTY.** Caller unidentified; `GlideDive` = **0 hits** in the whole AS corpus; `EndGlideDive` is REAL 1296 B, so *some* entry exists. **Alternatives not excluded.** | needs-a-stubbed-C++-fn **or** an unidentified alternative |
| 9 | Hero spawn / GAS bind — `ALokiGameMode::SpawnPlayer` | **[M] EMPTY** (`xor eax,eax; ret`, FK-1) — the deeper wall FK-1 already named | needs-a-stubbed-C++-fn |

---

## 4. What this does NOT establish

- **It does not establish that the drop phase is reachable.** Nothing here executed anything. Every "satisfiable" above is a static reading.
- **It does not establish that `SpawnPlane` faults, or that it does not.** The bytecode does not obviously predict a hard crash, but that reasoning rests on **UE-source semantics never measured in this build** — no xref from `ArrayGetOutofBounds`/`AccessNoneContext` to a code path, no exception type, and the same `.rdata` block contains fatal-class messages. And S93's own report is an SEH catch, not a fault-site measurement.
- **It does not establish that the markers were absent at call time.** Present-in-map is [M]; loaded-in-world is [S]. The streaming hypothesis is the natural successor and **nothing was measured about cell load order**.
- **The `LokiCapturePoint` question is open in both directions.** `BP_CapturePoint_Tutorial_C` exists in `LVL_Tutorial` and its parentage could not be settled offline; a name-map search is structurally blind to BP subclasses of a native class.
- **16 of 100 drop-path keys are coverage-blocked, and they are exactly the player-entry points.** Any statement of the form "no route exists to put a player on a rideable" is **not-looked-at**, not absent.
- **The 9.9× stub enrichment has no controlled denominator** (S115's excludes coverage-blocked, this one does not) and its EMPTY predicate conflates `ret 0` with `return false`, some of which are legitimate BlueprintNativeEvent defaults.
- **`WITH_SERVER_CODE` is [I].** No build-configuration artifact was read by anyone.
- **`GoToPhase` and `BP_AuthSetCurrentPhase` impls were never graded** — only their UHT flags. If both are folds, the phase ladder is closed in C++ and item 1 above changes class.
- **Missing controls, named:** (a) no positive control that the bpdump emits `EX_Context_FailSilent` at all, so "non-fail-silent" is decorative; (b) no control that `binds_members.csv` would carry a *property* row (built post-hoc by a verifier); (c) no exhaustive census behind "every component the script dereferences"; (d) the marker-existence instrument had **no known-good case in the persistent map**, correctly discarded; (e) the catalog-census calibration measured declaration names, not call sites; (f) the `Actor`/`World` controls used substring matching while the test used anchored matching.
- **9 of 11 `BP_DropPlane_*` variants were checked only with the name-table test that line 4 itself disproves** — they are unchecked, not clear.
- **The general component's `SpawnPlane` returns `DropPlaneVar` and nothing establishes its value.** "Returns the (still-null) `DropPlaneVar`" is unsupported.

---

## 5. The cheapest next experiment

**Do this first — offline, minutes, and it re-classifies the dominant blocker.**

**Grade the two phase-write impls.** Both are `Final|Native|Public|BlueprintCallable` and both are the only known write paths to the value that gates everything downstream:

```
ALokiRoundGameMode::GoToPhase          uht_funcflags_tuthero.csv:2593
ALokiGameState::BP_AuthSetCurrentPhase uht_funcflags_tuthero.csv:1682
```

Use the instrument line 5's verifier validated: rebuild/reuse the 18-image page-granular `.text` union (`.text`-only merge, ImageBase-independent — 16,653 / 30,281 pages, 0 conflicts), resolve each exec thunk from `fk13natreg`-style registration records, disassemble to the **last direct call**, and read the target's bytes in `dumps/tutorial-hero`. The three universal folds are `0xF7EC20 = c2 00 00` (`ret 0`), `0xF7EB50 = 33 c0 c3`, `0xF7EB60 = 32 c0 c3`.

- **If both are REAL** ⇒ the phase ladder is drivable today by the existing S55 native-call primitive with **no `.text` write** (`BlueprintCallable` + `Native` is exactly the shape the primitive calls), and every precondition from #2 downward becomes testable in one armed window. That is the single highest-value outcome available.
- **If both are folds** ⇒ the ladder is closed in C++, item 1 becomes `needs-a-stubbed-C++-fn`, and the question moves to the Angelscript layer (`ALokiRoundGameMode` was ungraded by `fk13natreg` — `reg=- array=- count=None` — which is a **tool limitation**, so a null there is not a negative).
- **If one is real and one is a fold** ⇒ use the real one, and **remember the name trap**: the registered UFunction is `BP_AuthSetCurrentPhase`, not `AuthSetCurrentPhase`.

**Second, also offline, ~1 hour:** decrypt the blocked page. Line 5 established page `0x5456000` (all five `AuthPlayerEnterWorld*` entry points) has **never** been demand-decrypted in 18 images. S117 established that **driving a code path from the backend forces `.text` decryption**. So: any run that reaches a rideable, followed by `usmapdump dumpimage`, converts 5 UNKNOWNs into measurements for free. Bank the dump; do not spend a launch on it.

**Third, and only if a live window is spent anyway:** re-invoke `Comp_GameMode_DropPlane_Tutorial::SpawnPlane` through a primitive that **zeroes `FFrame` bytes `0x48..0x78`** instead of inheriting them from `g_template`. That is a ~3-line change in `CallBPGuarded` (`tutorial_launch.cpp:945-951`). Receipt: the marker file. Arms: (A) current primitive → expect the historical `FAULTED`; (B) zeroed-`FFrame` primitive → if it now returns a spawned `LocDropPlane` and reaches `SetDropPlane`, **S93's result is an artifact of its own invocation and the audit line was built on a tool defect.** Positive control that the arm ran at all: `GetAutoDropLocation` (0 push / 0 pop) must behave identically in both arms.

⚠ **Do NOT design a control on "does the drop-path marker exist" — that is settled.** And do not use `SpawnPlane` returning "ok" as a success criterion; only the spawned actor and `SetDropPlane` count.

---

## 6. Method notes

**New instrument artifacts, for `docs/method-rules.md` §1:**

1. **★ An IoStore package's `.names.txt` is not a presence test for a serialized property.** `BP_DropPlane_Base.uasset.names.txt` (267 names) lacks `TeamDropPodClass` while the CDO in that very asset sets it — unversioned serialization resolves inherited property names by usmap index. A false positive control had even been constructed from `MaxDropPodDistance` being present. **Use `bpdump @props`.**
2. **The catalog JSON has no bytecode.** `catalog/*.json` carries declarations and SuperStructs but zero `ScriptBytecode`, so a corpus grep for a function name **cannot find call sites** — and calibrating on declaration hits is a positive control on the wrong signal class. Game-mode BPs are additionally absent from the catalog entirely.
3. **`extractor wherefile` clamps at `.Take(20)` before counting** (`Program.cs:840-844`); any printed count of 20 is saturated. A second, unclamped copy at `Program.cs:809-810` means the clamp is not a file-wide property.
4. **`extractor namesall` filters `.EndsWith(".uasset")`** (`Program.cs:1072`) and is structurally blind to `.umap`. ⚠ But the illustrative measurement attached to this finding was **false** — `namesall Skylands_WP` would print `121 assets`, not 0. The structural point stands from the source line alone.
5. **`exec_chain_grade.impl_of` resolves indirect calls through the class vtable** (`:363-369`, `:435-446`), and enormous numbers of slots hold the universal fold. Grading EMPTY off that inflates the image-wide count **79 → 464**. Require a direct call/jmp, or a vtable read with a local identity control (and the strongest form of that control is: **scan the whole image for the impl address — one occurrence means no derived class overrides it**).
6. **`impl_of` returns `ELIMINATED` for MSVC-inlined tiny members** — 5 false stubs on this surface alone, all disproved by full disassembly.
7. **`docs/game-map.md` is a 229-line category summary, not an asset listing** — it returns 0 for `DropPlane`, `Comp_GameMode_DropPlane` **and** `DropPod`, all of which exist. The negative control fires; discard it as an existence oracle.
8. **The bpdump output filename is keyed only on the function name and the collision fired at least three times this investigation** — `tools/extractor/out/bpdump_SpawnPlane.txt` was successively the Tutorial, then the general, then the PvE_Holdout asset. **Always verify the `# Asset:` header before reading a byte, and copy to a private path immediately.**
9. **`_ALL` / `_PROPS` are not bpdump needles** — they are output-file suffixes. The real special needles are `*`, `@props`, `@imports` (`Program.cs:1136`, `:1140`, `:1350`). `@imports` is what resolves class hierarchies and is documented nowhere in the repo.
10. **The `Grep` tool respects `.gitignore`**, and `tools/extractor/.gitignore:9` ignores `out/` — it silently returned 2 of 3 known-matching files, a partial result that reads like an answer. Use bash `grep` with explicit directories there. (`rg` is **not installed** on this machine.)

**Recurring patterns this investigation re-instantiated:**

- **FK-22's own error, committed three more times by the lines investigating it:** "exclusive to the Tutorial variant" (PvE_Holdout is a byte-twin), "those actors exist in Skylands_WP" (true of one class, false of the other), "precisely the actor-authority API" (three counter-examples in the same table). **Generalising from the variants you opened to the ones you did not is the failure mode, and it does not stop being the failure mode when you are the one auditing it.**
- **A universal negative with no enumeration** — "no shipped path to glide-dive", "no C++ route exists to add a player to a rideable" — where the enumeration would have been cheap and, run, produced a different answer.
- **A correctly-calibrated instrument aimed at the wrong question** (FK-38): poolable-class registration timing answering "is the spawn map-independent?".
- **Numbers retyped rather than re-derived**: "128 runs" (193 files, 104 distinct), "93 occurrences" (98), "262,103 rows" (261,410), "2,559 packages" (a subdirectory count), "11 known descendants" (11 assets, not 11 classes), "over 100 UFunctions" (exactly 100), "nine empty impls" (ten). **Re-derive counts and state the unit.**
- **A citation error that would have propagated:** the ignorance map cites the belief at `coverage-audit-s101.md:229`; it is **line 269**. And `docs/angelscript-dropphase.md`'s bypass list is cited without noting that `OverridePlaneLocations` is one of FK-1's four dead stubs.
- **★ The best moment in the whole investigation was a refusal.** Line 3 found zero drop-path tags in `LVL_Tutorial`'s persistent name table, noticed the table contains **no tag-shaped name of any kind**, declared the result uninterpretable rather than negative — and the answer then inverted to 3/3 once the World Partition cells were dumped. That is the `claimableRewards=[]` rule applied correctly and prospectively, and it is what makes this document's central refutation possible.
---

## 7. Independent verification pass (session lead, post-synthesis)

Three load-bearing claims were re-derived from scratch, by hand, without reference to the agents'
commands. All three hold.

| # | Claim under test | Independent re-derivation | Verdict |
|---|---|---|---|
| 1 | The audit line is at `coverage-audit-s101.md:269`, and the ignorance map miscites it as `:229` | `grep -n "Drop-in / DropPlane" docs/coverage-audit-s101.md` → **269**; `ignorance-map-s101.md:1412` quotes `:229` | **[M] confirmed** |
| 2 | The round phase never leaves `EGP_BeginInit(1)` | `grep -rhoa "Setting Phase to.\{0,40\}" --include=*.log docs/ dumps/` over **564 log files** (unit: files) → **193 occurrences, 193 of them `Setting Phase to 1 (BeginInit)`**, zero other values | **[M] confirmed**, count reproduces exactly |
| 3 | `TrainingStart` / `PlaneStartPoint` / `PlaneEndPoint` exist in `LVL_Tutorial` | exact-line grep over the 7,300 `*.umap.names.txt` tables, then each hit resolved to a path via `dumps/extractor-out-PREFIX14/allfiles.txt` | **[M] confirmed** |

Claim 3 resolved cell-by-cell — the cell IDs are opaque, so the map attribution is the whole test:

```
TrainingStart    D0E5AKNEBU9HQIWM2J60FG8QT.umap -> Loki/Content/Loki/Maps/Tutorial/LVL_Tutorial/_Generated_/
PlaneStartPoint  8MF6M4K424YK5TUPV8O9UDXKR.umap -> Loki/Content/Loki/Maps/Tutorial/LVL_Tutorial/_Generated_/
PlaneEndPoint    4WUJ1QA2CHCV0DYIDGRGHED5B.umap -> Loki/Content/Loki/Maps/Tutorial/LVL_Tutorial/_Generated_/
```

Three markers, three **different** cells, all under `LVL_Tutorial`. `LVL_Holdout` independently
carries all three; `LVL_Battleships` carries `PlaneStartPoint`. ⇒ **S93's stated reason — "drop-path
markers that don't exist outside the real deploy" — is false about the very map it was measured on.**

### ⚠ 49th instrument-artifact instance, committed by the verifier and caught in the same pass

The first attempt at claim 2 swept `docs/` and `dumps/` for `ERoundPhase::EGP_[A-Za-z]*` and returned
**all ten phases** — `EGP_Combat` 42, `EGP_SpawnSelect` 33, `EGP_Lineup` 32 — which reads as a direct
refutation of the synthesis's headline. It is not. Two contaminants:

- `docs/*.md` **prose** (`angelscript-barracuda.md`, `angelscript-ffa-bots.md`, `angelscript-layer.md`
  all discuss `EGP_Combat` in body text);
- `dumps/**/SUPERVIVE-Win64-Shipping.dump.exe` — the **enum name table inside the binary**, which
  necessarily contains every member exactly once.

★ **The tell was in the numbers before the context was read:** seven distinct phases at *exactly* 32
occurrences is the signature of a per-file listing, not of runtime transitions, which would vary.
**A suspiciously flat distribution across categories is evidence you are counting a vocabulary, not
events.** Restricting to `--include=*.log` and to the transition line `Setting Phase to` inverted the
result to 193/193 and reproduced the agents' count exactly.

⇒ Two general rules, both already in this project's register and both re-earned here:
1. **Never census a runtime behaviour over a corpus containing the binary that declares its
   vocabulary.** The enum table guarantees a hit for every value and looks exactly like coverage.
2. **Challenging a finding does not exempt the challenge from controls.** The refutation was more
   exciting than the confirmation, which is precisely why it needed the harder check first.

### What the verification pass did NOT re-derive

- The three-sibling class hierarchy (§2.2) — accepted on the agents' `@imports` / SuperStruct reads,
  which the adversarial verifier independently re-ran. **[I] at this desk, [M] in the record.**
- The general variant's `0 GetAllActorsWithTag` — not re-run here.
- Any part of the native stub audit (§2.5). It is the most heavily verified line in the workflow but
  none of it was re-checked at this desk.
- **Nothing was executed.** No launch, no injection, no `.text` write.
## 8. The phase-write grading (follow-up experiment)

**Date:** 2026-08-16 · **Mode:** 100 % offline — zero launches, zero injections, zero `.text` writes.
**Design:** two independent graders attacked the same two functions by disjoint routes (A = `.data` native-registration record table; B = `.rdata` log-string anchor → nearest function start), each was then adversarially verified by a third party who re-read every byte itself. Both verifiers returned `GRADING-PARTLY-SOUND`; neither returned `GRADING-UNINTERPRETABLE`, so **both gradings contribute.**

### 8.1 Verdict table

| function | exec thunk (fold multiplicity) | impl | impl bytes | GRADE |
|---|---|---|---|---|
| `ALokiRoundGameMode::GoToPhase(ERoundPhase)` | `0x5457200` (**1**) [M] | `0x5601020` (0x271 B) | `40 55 53 56 57 41 57 48 8b ec 48 83 ec 40 0f b6 fa 4c 8b f9` | **REAL** [M] |
| `ALokiGameState::AuthSetCurrentPhase(ERoundPhase)` — registered `BP_AuthSetCurrentPhase` | `0x53878d0` (**1**) [M] | `0x567a160` (12 B adjustor) → tail `0x442b4c0` (23 B) | `48 81 c1 90 05 00 00 e9 54 13 db fe` → `48 83 ec 28 88 54 24 38 48 8d 54 24 38 e8 6e 6e f1 fc 48 83 c4 28 c3` | **REAL** [M] |
| *(companion)* `ALokiGameState::GetCurrentPhase` | `0x5388300` (**1**) [M] | `0x5384610` | `0f b6 81 44 0a 00 00 c3` | **REAL** [M] |

⚠ Every byte string above was read at the address printed, in **both** `dumps/merged2.dump.exe` and `dumps/tutorial-hero/…dump.exe`, by four parties (two graders, two verifiers) using three independently written readers. Zero misattributions were found on any of these rows.

**Fold multiplicity is [M] but NOT from either grader's own instrument** — see §8.5. Both verifiers independently counted qword pointers image-wide: both target thunks = 1, both impls = 1, with in-pass controls `0x5254180` = **92 pointer slots** and `0x2c2ce30` = **23**, reproducing CLAUDE.md's documented 91–92 / 23. (Pointer slots ≠ distinct registered names — `AuthSetDeathCircle`'s thunk occupies 2 slots — so "91 names / 92 slots" is the likely reconciliation of the long-standing 91-vs-92 wobble in this file. Not resolved here; do not re-type either number.)

Neither impl equals any of the three folds (`0xF7EC20 = c2 00 00`, `0xF7EB50 = 33 c0 c3`, `0xF7EB60 = 32 c0 c3`), all three of which were re-read in the same pass. The `0xF7EB60`/BlueprintNativeEvent ambiguity **does not arise**: flags on both targets are `0x04020401` = `Final|Native|Public|BlueprintCallable`, with `FUNC_BlueprintAuthorityOnly (0x4)` **clear** [M].

### 8.2 Do the two graders agree?

**Yes on every grade, and yes on the mechanism.** Independent routes, same answer:

- Grader A found `GoToPhase`'s impl through the `.data` record `0x9c1f298 {"GoToPhase", 0x5457200, 0x5601020}`, then cross-checked by disassembly.
- Grader B found it through the UTF-16LE literal `"Setting Phase to %d (%s)"` at `.rdata 0x8b20de8` — held by a pointer at `0x8b20dc8` whose **sole** `.text` xref is inside this function — then cross-checked against the record.
- Both then converged on the same thunk→impl edges, and both reproduced all four gold controls.

Where they differed, they differed on **detail, not verdict**, and one of them is right in each case (nothing is averaged):

| point | A | B | resolved |
|---|---|---|---|
| the single byte store to `+0xA44` | `0x56772CF` `44 88 a7 44 0a 00 00` = `mov byte [rdi+0xA44], r12b` | `0x56772d0` `88 a7 44 0a 00 00` = `mov [rdi+0xA44], ah` | **A is right.** B decoded one byte late and dropped the REX.R prefix. Both verifiers reproduced B's artifact on their own first pass and corrected it by linear disassembly. The *count* (exactly one store, in the constructor) is unaffected. |
| the virtual dispatch at the end of `GoToPhase` | omitted | found: `0x5601276 call qword ptr [rax+0xb08]` with `(new, old)` | **B is right, and it is material.** A's predicted outcome of a `GoToPhase(4)` call ("log fires, state does not move") is incomplete — arbitrary subclass-overridable work also runs. |
| `.pdata`-derived function sizes | quoted from `tools/strxref/index/pdata_union.csv` | reported `.pdata` all-zero in all 17 dumps, flagged FK-22 §2.5's sizes as unreproducible | **Both right; they answer each other.** The dumps' `.pdata` section *is* all zeros (S115-b); the sizes come from the pre-built union index, not from any image. **B's open item #5 is closed by A's method note.** |
| `0x442b4c0` call-site count | 26 (16 call / 10 jmp) | *(not counted)* | **A's number is not reproduced.** Both verifiers independently got **28 = 16 call + 12 jmp**. Byte-aligned scans over-count, so treat 28 as an upper bound; the qualitative claim (ICF-shared Broadcast helper, therefore non-identifying) is what carries. |
| `0xF7EC20` direct call sites | 4,971 | *(not counted)* | Both verifiers got **5,095 direct calls** (+77 tail-jmps). Use 5,095. The conclusion — the address identifies nothing — is unaffected. |

### 8.3 Controls — both polarities, same pass, all passed

| control | expected | got | result |
|---|---|---|---|
| **EMPTY gold** `ALokiGameMode::SpawnPlayer` | thunk `0x534C070` → impl `0x0F7EB50` | last **direct** call `0x534c228` → `0x0F7EB50` = `33 c0 c3` | ✅ both graders, both verifiers, both images |
| **EMPTY gold** `ALokiDropPlane::OverridePlaneLocations` | thunk `0x53372A0` → impl `0x0F7EC20` | last direct call `0x5337378` → `0x0F7EC20` = `c2 00 00` | ✅ ditto |
| **REAL gold** `ALokiServerAnalyticsManager::AddTeamDropEvent` | impl `0x557eae0`, 926 B | `48 8b c4 48 89 58 10 …`, pdata 926 B (exact) | ✅ |
| **REAL gold** `ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` | impl `0x55cbb60` | `40 56 57 48 83 ec 38 …`, pdata 81 B | ✅ |
| **COVERAGE negative control** `ALokiGameState::AuthSetDeathCircle` | must report separately, never as EMPTY | impl `0x55653e0`, page **0/4096 non-zero in 13/13 images** → reported `COVERAGE-BLOCKED`, ungraded | ✅ |
| **grader-defect control** (B) | naive "last direct call" must fail on gold | without excluding `__security_check_cookie` (`0x751deb0`), gold `SpawnPlayer` mis-grades to `0x751deb0` | ✅ defect demonstrated and fixed; fixed grader 6/6 |
| **vtable-defect avoidance** | require a DIRECT rel32 | `0x545726b: e8 b0 9d 1a 00` and `0x538793b: e8 20 28 2f 00` — both `E8` rel32, no indirect resolution anywhere | ✅ the `exec_chain_grade.py` `impl_of` defect is not present |
| **MSVC-inlined-tiny-member trap** | a 2–3 instruction body is REAL, not ELIMINATED | `GetCurrentPhase` (3 instr) and `BP_AuthSetCurrentPhase` (5 instr across 2 fragments) both graded **REAL** | ✅ trap avoided |
| **coverage of the targets** | must not be zero pages | `0x5601020` decrypted **18/18** images; `0x567a160` **17/18** (sole zero = `dumps/crash-20260815-160759`); `0x442b4c0` 18/18; first-16-bytes identical in every covered image | ✅ neither target is COVERAGE-BLOCKED |

Both polarities ran, both reproduced, in the same pass as the targets, in two images each, by four parties. **The grading is interpretable.**

### 8.4 The consequence, stated plainly

**BOTH REAL — and that is NOT the "the ladder is drivable today" green light the pre-registered outcome table anticipated. Grading them REAL without reading the bodies would have been exactly the false green light this brief warns about.**

**What is true [M]:**

1. Both are `Final|Native|Public|BlueprintCallable`, with real exec thunks (fold 1) and real impls in fully decrypted pages. They are the exact shape the **S55 native-call primitive** already calls (resolve the `UFunction`, call `UFunction.Func @ +0xE0` directly, one enum-byte param). **Callable today. No `.text` write, no PI hook, no `ExecuteConsoleCommand`.**
2. **NO AUTHORITY GUARD IN EITHER.** The full 0x271-byte `GoToPhase` body was disassembled and every branch accounted for: GameState-null, the `IsA` cast against `ALokiGameState::StaticClass` (`0x5380690`) via `0x12c7dd0`, three log-verbosity gates on `byte[0xA036D00]`, the 10-way phase-name jump table, and the old==new test. **Zero role / NetMode / HasAuthority reads.** `BP_AuthSetCurrentPhase` is five instructions total. `FUNC_BlueprintAuthorityOnly` is clear on both. This was checked by both verifiers; grader A never checked it, so the finding is the verifiers'.

**What is also true, and is the actual result [M]: NEITHER FUNCTION WRITES `ALokiGameState::CurrentPhase`.**

- `CurrentPhase` is the byte at **`ALokiGameState+0xA44`** [M], fixed three ways: `GetCurrentPhase` impl is literally `movzx eax, byte [rcx+0xA44]; ret`; the UHT `FPropertyParams` record at `.rdata 0x8984400` carries `0xA44` at `+0x32`; and `GoToPhase` reads it at `0x56011b2`. ⚠ Two `FPropertyParams` records point at the `"CurrentPhase"` string (`0x8968180` → `0xF48`, `0x8984400` → `0xA44`), so the params record **alone** is ambiguous — `GetCurrentPhase`'s impl is what disambiguates.
- **`GoToPhase(N)`**: logs `Setting Phase to %d (%s)`, reads the old phase, `cmp r14b,dil; je` early-out on no-change, then performs its phase write as `0x56011ca: e8 51 da 97 fb` = a **DIRECT call to `0xF7EC20` = `c2 00 00` (ret 0)** with `(ALokiGameState*, newPhase)` — the stripped server-authority setter. It then logs `Transitioning from phase (%s) to phase (%s).` and fires the virtual at `0x5601276 call qword ptr [rax+0xb08]` on the RoundGameMode with `(new, old)`.
- **`BP_AuthSetCurrentPhase(N)`** is `OnRoundPhaseChanged.Broadcast(N)` **and nothing else**. `rcx+0x590` is `FNewRoundPhase OnRoundPhaseChanged` [M — `FPropertyParams 0x8982770` reads `0x590` at `+0x32`; `binds_members.csv:42853`]; the shared tail `0x442b4c0` packs the byte and calls `0x1342340`, which reads `Num` at `[rcx+8]`, walks the invocation list and issues `call qword ptr [r9+0x270]` = the ProcessEvent slot. Corroborated by `OnRep_CurrentPhase_Internal` (impl `0x569ac50`, named by record `0x9bea738`) doing `movzx edx,[rbx+0xA44]; lea rcx,[rbx+0x590]; call 0x442b4c0`.
- Across the decrypted `.text` of `merged2` there is **exactly ONE byte store to displacement `+0xA44`**, at `0x56772CF` (`44 88 a7 44 0a 00 00` = `mov byte ptr [rdi+0xa44], r12b`), inside a constructor init run (`mov [rdi+0x5ac],-1`, `mov [rdi+0x5f0],-1`, `mov [rdi+0x630],0xbf800000`, `r12b` = the zero register). 9 byte *loads* exist. ⚠ Bounded: 45 % of `.text` is undecrypted, and `CurrentPhase` is replicated (an `OnRep_CurrentPhase` exists), so the net serializer writes it via computed-offset memcpy, which no literal-disp32 scan can see. The honest claim is **"no compiled runtime store exists in the decrypted image"**, not "the byte can never change".

**⇒ THE ANSWER: the round-phase VALUE is not settable from the client by either function. But both observable CONSEQUENCES of a phase change are separately drivable today, with no `.text` write — and they are two different levers.**

- **Lever (a) — `ALokiGameState::BP_AuthSetCurrentPhase(6)`** broadcasts `OnRoundPhaseChanged`, the very multicast delegate FK-22 §2.6 measured the Tutorial mode binding in `ReceiveBeginPlay`, whose handler tests `NotEqual_ByteByte(NewPhase, 6)` → PlayerArray loop → `AddPlayerToDropPlane`. One call, direct attempt at the Lineup handler.
- **Lever (b) — `ALokiRoundGameMode::GoToPhase(N)`** fires the `[vtable+0xb08]` virtual with `(N, old)`. Because `CurrentPhase` never advances, the `old != new` gate passes for **any** N ≠ the stuck value, so it is **re-firable at will** — 4, then 6, then 7.
- **Lever (c) — the store, as a DATA poke.** `+0xA44` is one byte on a reflected property of a client-resident object. Poking it is this project's cheapest and measurably safest write class (nothing 0/22 · bytecode 0/9 vs standing `.text` 7/8 at a 320 s hold), and `GetCurrentPhase` is a free readback.

⚠⚠ **ORDERING IS LOAD-BEARING, AND THE OBVIOUS RECIPE IS SELF-DEFEATING.** Grader A recommended "poke `+0xA44` = N, then call `GoToPhase(N)`". That is foreclosed by bytes grader A itself quoted: `GoToPhase` reads the live phase at `0x56011b2` and does `cmp r14b,dil; je 0x560127c` — with the poke already applied, it jumps straight to the epilogue having done **nothing**: no fold call, no log lines, no virtual dispatch. **The correct combination is: poke `+0xA44` = N, then call `BP_AuthSetCurrentPhase(N)`** — which has no equality test — giving store-and-notify with zero module-image bytes touched. Or call `GoToPhase(N)` **first** and poke after.

**Caveats that must travel with this result:**

1. Handlers keyed on the **argument** (the delegate/event parameter) will work. Handlers that re-read `GetCurrentPhase()` will see the stale value unless lever (c) is also applied. Expect a **partial ladder** and instrument for exactly that split.
2. **[I, from FK-22, not measured here]** the Tutorial mode binds `OnRoundPhaseChanged` behind `ULokiBlueprintLibrary::ServerOnly`. If that gate does not pass on the tutorial route, the delegate has **no subscribers** and lever (a) is inert. This is one read-only RPM of `Num` at `GameState+0x590+8` — the same single-cast `DelegateSize`/`Num` read FK-15 used. **Do it before spending a launch.**
3. **UNRESOLVED:** what sits in `[vtable+0xb08]`. Grader B calls it `OnNewPhase` on the strength of a forwarder at `0x330c56c` (`mov rax,[rcx]; jmp qword [rax+0xb08]`), but the verifier could find **no `.data` registration record naming it**, and on the tutorial route the mode is `BP_LokiGameMode_Tutorial_C`, whose override is unexamined. "GoToPhase fires OnNewPhase and that drives the BP `On Round Phase Changed` event" is **[I], not [M]**.
4. **UNRESOLVED:** the callee at `0x56011ca` is unidentified. Its *body* is `ret 0` [M], but `0xF7EC20` has **5,095 direct call sites** and is the impl of hundreds of registrations — the address identifies nothing. It is **not** the registered `BP_AuthSetCurrentPhase` (impl `0x567a160`, which has exactly one caller: its own thunk). So `ALokiGameState` has at least two byte-taking phase-ish members and only one is named. **Do not write it up as "AuthSetCurrentPhase is what GoToPhase calls."**
5. **This does not reopen FK-1.** `SpawnPlayer` and the four server-authority stubs are untouched. Reaching `EGP_Lineup` *behaviour* still terminates at those empty impls for the actual pod/hero handoff.
6. `ALokiRoundGameMode` liveness at call time is unverified offline — and the `.rdata` here ships the runtime refusal string `"We're ALokiRoundGameMode but aren't using an ALokiRoundGameMode!"`, so the client build has a failure mode for exactly this. Verify the live object exists before calling; do not assume.

### 8.5 Corrections to FK-22 and to prior claims

⚠⚠ **RETRACTED: "GoToPhase writing nothing explains the 193/193 `BeginInit` corpus."** Grader B advanced this in its conclusion, ungraded. It is **false as stated**. The `Setting Phase to %d (%s)` line is emitted **before** the old==new test and **prints the ARGUMENT, not the stored byte** [M — the `lea` at `0x5601189` is the sole `.text` xref to the record, and the log gate `cmp byte[0xA036D00],5` passes by default, so the receipt fires on every invocation]. ⇒ **193/193 reading `1 (BeginInit)` measures that `GoToPhase` was only ever INVOKED with 1.** That is a statement about the *callers*, not about a stripped writer. A stuck `CurrentPhase` could produce it via a caller that re-reads `GetCurrentPhase()`, but that is a hypothesis. **This makes §8.6 step 2 the highest-value offline follow-up: the corpus is now evidence about the call sites.**

★ **`GoToPhase` is FK-22's own instrument, and it is the SOLE emitter of the line FK-22 counted** [M — exactly one `lea` xref image-wide to the record at `0x8b20dc8`]. Jump-table calibration confirmed from the `.rdata` name table at `0x8b20cb0`: `ServerStartup, BeginInit, Pre, FinishInit, SpawnSelect, …` with case 4 = `SpawnSelect` and case 6 = `Lineup` — matching FK-22's numbering exactly, derived by a route independent of FK-22.

★ **B's open item #5 is closed:** the `.pdata`-derived sizes in FK-22 §2.5 come from `tools/strxref/index/pdata_union.csv`, a pre-built union index — **not** from any dump's `.pdata` section, which is all zeros in all 17–18 images on disk (S115-b). Cite the CSV, never the section.

### 8.6 Next step — offline where possible

1. **[OFFLINE, free, do first] Enumerate `GoToPhase`'s seven non-thunk callers.** Both verifiers reproduced the identical list: `0x55f37a4`, `0x56146d5`, `0x560a104`, `0x560a174`, `0x560a1a2`, `0x560aa72`, `0x5613300` (3 rel32 `call` + 5 tail-`jmp`, incl. the thunk). Grader B declared this **NOT-LOOKED-FOR**. Given the retraction above, this is now the direct route to *why the corpus is 193/193 BeginInit*: if any caller is an already-reachable native driver, the ladder may have an existing entry point that needs no injection at all.
2. **[OFFLINE] Resolve `[vtable+0xb08]`** on `ALokiRoundGameMode` and on `BP_LokiGameMode_Tutorial_C` — is it a real body, a fold, or a BP `ProcessEvent` dispatch? This decides whether lever (b) does anything. Use the class's vtable in a single-state dump plus `extractor bpdump` on the Tutorial mode.
3. **[OFFLINE] `bpdump` the Tutorial mode's `ReceiveBeginPlay`** to settle whether the `OnRoundPhaseChanged` bind really sits behind `ULokiBlueprintLibrary::ServerOnly` — FK-22 §2.6 has this as [I]. If it is gated and the gate fails, lever (a) is inert and only levers (b)+(c) remain.
4. **[LIVE, read-only RPM, ~1 minute, no launch of its own if a session is already up] Read `Num` at `GameState+0x590+8`.** Zero subscribers ⇒ lever (a) is a no-op. This is the single cheapest thing that makes or breaks the recommended experiment and it must precede any armed window.
5. **[LIVE, one armed window, only after 1–4] The pre-registered call.** Order matters: `GoToPhase(4)` → read `GetCurrentPhase` (predict **unchanged**, per §8.4) and grep `Loki.log` for the two receipts `Setting Phase to 4 (SpawnSelect)` + `Transitioning from phase (…) to phase (…)` — both of which the body emits for free and which no prior session has ever produced with a value other than 1. Then, as a separate single-variable arm, poke `+0xA44 = 6` → `BP_AuthSetCurrentPhase(6)` → watch for `AddPlayerToDropPlane`. **Do not combine the poke with `GoToPhase` — the equality early-out swallows it.**

### 8.7 New instrument artifacts found (register these)

1. ★★ **Unaligned byte-pattern scanning drops REX prefixes and prints an instruction at an address it did not start at.** This experiment reproduced the project's own worst-named defect **three times independently** — grader B's write-up (`0x56772d0 mov [rdi+0xA44],ah`) and both verifiers' first passes — against the true `0x56772CF` `44 88 a7 44 0a 00 00` = `mov byte [rdi+0xa44], r12b`. Note the failure mode: the wrong decode is *plausible* (same displacement, same apparent semantics, wrong source register) and self-validating. **Fix: linear-disassemble the region from a known instruction boundary; never decode from a mid-instruction byte match.** The previous instance of this family (S115-d) was caused by prose compression; this one is caused by a scanner, so the rule generalises beyond write-ups.
2. ★★ **A self-built registration-record table silently drops entries, so a fold multiplicity read off it is a LOWER BOUND, not a count.** Grader B's 6,307-record table read `0x5254180` = 64 and `0x2c2ce30` = 22 against true values 92 and 23 — a ~30 % undercount — while citing those very numbers as its calibration. Grader A's 16,269-record table read 91 vs the verifiers' 92 and claimed the match was "exact". **Fix: count qword pointers to the address image-wide.** Two verifiers did this independently and agreed on 92 / 23 / 1 / 1. ⇒ **a fold multiplicity must be measured on an instrument that does not depend on recognising the record shape.**
3. ★ **A blanket "identical across all N images" that silently covers addresses outside the N-image census.** Grader A wrote "all 13 agree byte-identically on every address below", but `OnRep_CurrentPhase_Internal` (`0x569ac50`) is decrypted in only **4 of 13**. The claim it supported survives; the coverage statement did not cover it. **State coverage per address, never as a blanket.**
4. ★ **The thunk→impl method has a fifth failure mode: MSVC inlines a tiny body INTO the exec thunk.** `GetCurrentPhase`'s thunk `0x5388300` contains **zero calls of any kind** — the `movzx eax,[rcx+0xA44]; mov [r8],al; ret` is inline. A "last direct call" grader returns nothing and would report `UNRESOLVED`/`ELIMINATED`. Grader A graded this row off the `.data` record alone with no independent disassembly cross-check, presented under the same method banner as the rows that had one. **Adds to the known list: (i) vtable resolution inflating EMPTY, (ii) `ELIMINATED` on inlined members, (iii) zero pages read as EMPTY, (iv) `__security_check_cookie` taken as the last direct call, (v) body inlined into the thunk.**
5. ★ **A behavioural log line that prints its ARGUMENT is not evidence about STATE.** See §8.5. `"Setting Phase to %d"` counted 193 times was read for a full investigation as evidence about the stored phase; it is evidence about the callers.
6. ★ **`__security_check_cookie` (`0x751deb0`) must be excluded from "last direct call"** — demonstrated, not assumed: with the exclusion removed, gold `SpawnPlayer` mis-grades to `0x751deb0`. Credit to grader B for building the control that exposed its own defect. Anyone re-running a thunk→impl grader in this image must carry the exclusion.

---

**Bottom line, one sentence:** both phase writers grade **REAL** and both are callable today by the S55 native-call primitive with no `.text` write and no authority guard [M] — but **neither writes `CurrentPhase`**, so what is drivable is the *notification* half of a phase change (an `OnRoundPhaseChanged` broadcast, and the `[vtable+0xb08]` virtual), with the stored byte reachable only as a separate data poke; whether that is sufficient to reach the drop hangs on one unread number — the subscriber count at `GameState+0x590` — and on what `[vtable+0xb08]` actually is, both of which are cheaper to settle than a launch.

---

## 9. Session-lead byte verification of §8 (independent, machine-checked)

Every load-bearing byte in §8 was re-read at the address it is attributed to, in
`dumps/merged2.dump.exe`, by a reader written for this check alone.

```
GoToPhase impl 0x5601020        40 55 53 56 57 41 57 48 8b ec 48 83 ec 40 0f b6 fa 4c 8b f9   REAL
BP_AuthSetCurrentPhase 0x567a160 48 81 c1 90 05 00 00 e9 54 13 db fe                            REAL (adjustor)
GetCurrentPhase impl 0x5384610  0f b6 81 44 0a 00 00 c3                                         REAL
FOLD 0xF7EC20                   c2 00 00                       (ret 0)
FOLD 0xF7EB50                   33 c0 c3                       (xor eax,eax; ret)
FOLD 0xF7EB60                   32 c0 c3                       (xor al,al; ret)
GOLD-EMPTY SpawnPlayer impl     33 c0 c3                       -> EMPTY, as recorded
GOLD-REAL AddTeamDropEvent      48 8b c4 48 89 58 10 ...       -> REAL, as recorded
```

Both gold polarities reproduce. **Neither target equals any fold** — confirmed [M].

Two rel32 edges resolved arithmetically **by machine**, not by hand:

```
0x56011CA: e8 51 da 97 fb   rel32 = -73,934,255  -> 0xF7EC20   (the ret-0 fold)   MATCH
0x567A167: e9 54 13 db fe   rel32 = -19,197,100  -> 0x442B4C0                     MATCH
           bytes at 0x442B4C0: 48 83 ec 28 88 54 24 38 48 8d 54 24 38 e8 6e 6e f1 fc 48 83 c4 28 c3
```

⇒ **`GoToPhase`'s phase write really does go to the stripped `ret 0` fold** [M], and
**`BP_AuthSetCurrentPhase` really is `add rcx,0x590; jmp <Broadcast>`** [M] — the `0x590` displacement
is visible **in the instruction itself**, which independently pins `OnRoundPhaseChanged` at `+0x590`
without recourse to any `FPropertyParams` record. `GetCurrentPhase` = `movzx eax,[rcx+0xA44]; ret`
independently pins `CurrentPhase` at `+0xA44`.

⚠ **My own hand arithmetic on the second edge was WRONG** (I computed `0x54174C0` and briefly doubted
a correct report). CLAUDE.md's rule *"hand arithmetic is an instrument — recompute with a machine"*
fired exactly as written. **The report was right and the challenge was wrong; verifying the challenge
is what settled it.**

### 9.1 Correction this forces on FK-22 §0 and on `CLAUDE.md`

§8.5's retraction is **accepted and propagated**. The wording published earlier today —
*"the round-phase machine never leaves `EGP_BeginInit(1)`"* — over-reads the corpus, because
`Setting Phase to %d (%s)` prints **`GoToPhase`'s ARGUMENT**, emitted *before* the old==new test.
The measurement is unchanged; its subject is not:

| | |
|---|---|
| **[M] still true** | `Setting Phase to` occurs **193 times across 564 log files** and all 193 read `1 (BeginInit)`. |
| **[M] what that measures** | **`GoToPhase` was only ever INVOKED with argument 1.** A statement about its **callers**. |
| **[M] separately** | The **only** compiled store to `+0xA44` in the decrypted `.text` is a constructor init (`0x56772CF`), and `GoToPhase`'s own write target is the `ret 0` fold. |
| **[I] the join** | Together these make a stuck `CurrentPhase` very likely — but *bounded*: 45 % of `.text` is undecrypted and `CurrentPhase` is replicated, so the net serializer writes it by computed-offset memcpy that **no literal-displacement scan can see**. |

⇒ **The honest form is "no compiled runtime store exists in the decrypted image", never "the byte can
never change".** The blocker for the drop route is unchanged in force and sharper in kind.

★ And the corpus is now **evidence about the seven call sites** (`0x55f37a4`, `0x56146d5`, `0x560a104`,
`0x560a174`, `0x560a1a2`, `0x560aa72`, `0x5613300`) rather than about a stripped writer — which is why
§8.6 step 1 is the highest-value free follow-up.
## 10. The phase callers, the vtable slot, the delegate gate, and the phase-free bypass

*Four offline lines (callers · vtable+0xB08 · delegate subscribers · phase-free bypass), each adversarially re-verified by an independent agent. Zero launches, zero injections, zero `.text` writes. Where finder and verifier disagree, the verifier's refutation governs and is called out inline.*

---

### 10.1 The caller table

`GoToPhase` impl **`0x5601020`**, fold **1** (exactly 1 stored qword pointer image-wide, its own registration record at `.data 0x9C1F2A8`); exec thunk **`0x5457200`**, fold **1**, 0 rel32 xrefs (pointer-reached from the registration table, as expected).

Two independent full-`.text` `E8`/`E9` sweeps of `dumps/merged2.dump.exe` returned **8 hits, set-identical**, and **all 8 were re-confirmed as genuine instruction boundaries** by linear disassembly from a `.pdata`-anchored or `lea`-confirmed function start. **Zero false positives** — the byte-aligned-scan over-count hazard did not bite. Every constant below is the last `edx`/`dl` write before the site, machine-decoded.

| site | containing fn | arg | reachable from | verdict |
|---|---|---|---|---|
| `0x545726B` call | exec thunk `0x5457200` itself (`0x5457256 movzx edx,[rsp+0x38]`) | **computed** (FFrame) | reflection / the S55 primitive | **NOT A CALLER** — the thunk's own P_FINISH call. This is the door lever (b) uses. |
| `0x55F37A4` call | `0x55F3740` — `AActor` vtable **slot 119 / disp `0x3B8` = BeginPlay** override (8 stored ptrs, all at that disp; Super `0x3378DC0`, 180 vtables) | **1** BeginInit | once per map load, **no authority/NetMode/role read anywhere in the body** | **RUNS TODAY [M site, I name]** — this is the 193/193 corpus |
| `0x56146D5` call | `0x5614690` (unnamed, **0 stored ptrs**, no rel32 xref) | **2** Pre | tail-jmp target of `0x560AF10` (vtable disp `0x8F0`, 8 ptrs) after its 3-condition gate | **GATED** — see below |
| `0x560A104` jmp | inside `0x560A090` (pdata fn, 272 B, **0 stored ptrs**) | **9** Shutdown | `lea` at `0x5609CE9`, OnNewPhase case Post(8) → `SetTimer` | **NEVER RUN** |
| `0x560A174` jmp | same fn `0x560A090` — the other epilogue arm | **2** Pre | same timer; branch on the `'ExitOnMatchEnd'` token (`.rdata 0x8B20F30`) = the **match-restart loop** | **NEVER RUN** |
| `0x560A1A2` jmp | `0x560A1A0`, **7-byte thunk, no `.pdata` row, 0 ptrs** (`mov dl,3; jmp`) | **3** FinishInit | `lea` at `0x56090C3` (OnNewPhase case Pre) and `0x56146F3` → `FTimerManager` | **NEVER RUN** |
| `0x560AA72` jmp | `0x560AA70`, same shape | **6** Lineup | `lea` at `0x56094A0` (OnNewPhase case SpawnReveal) → timer | **NEVER RUN** |
| `0x5613300` jmp | `0x5613200` — `AActor` **slot 170 / disp `0x550` = Tick** override (6 ptrs; Super `0x33A3C10`, 207 vtables) | **4** SpawnSelect | **every frame**, iff `CurrentPhase==3` **and** `byte[GameMode+0x7C0]==4` | **RUNS TODAY, one condition unmet** |

⇒ **7 non-thunk callers, 2 by `call` and 5 by tail-`jmp`. Six of the seven pass a value other than 1, and the corpus (193 occurrences across 193 files, exactly one per file, 100 % reading `1 (BeginInit)`) means those six have never been observed to fire.** [M for the constants; the "never run" inference is [I], because the log line is verbosity-gated.]

**Corrections this table forces on the brief:**

- **`GoToPhase`'s extent is `0x5601020..0x56012E0` = `0x2C0` bytes across 3 chained `.pdata` rows, not `0x271`.** `0x5601020+0x271 = 0x5601291` is the early-bail block, i.e. `0x271` is a body-to-first-bail measure. [M]
- **`ERoundPhase` is TEN values, read out of the binary rather than named:** the 10-dword table at `.text 0x56012B8` (base = ImageBase via `lea rdx,[rip-0x56010A6]`, `cmp edi,9; ja default`) leas literals at `.rdata 0x8B20CB0–0x8B20D10` plus `0x8645BF0` → **0 ServerStartup · 1 BeginInit · 2 Pre · 3 FinishInit · 4 SpawnSelect · 5 SpawnReveal · 6 Lineup · 7 Combat · 8 Post · 9 Shutdown.** [M, both agents, independently] ⚠ This table is indexed by the phase **value**; OnNewPhase's separate table (§10.2) is indexed by **phase−1**. Do not conflate them.

**The two gates, both already running:**

- **1→2** is `0x560AF10` (vtable disp `0x8F0`): `call 0x55FE680` → `cmp dword [rax+8],1; jle` (**`ALokiGameState::MatchStartDetails`**, FString @ **GameState+0x738**, RepNotify `OnRep_MatchStartDetails`, UHT record `.rdata 0x8983630` — must be non-empty) · `cmp byte [rdi+0xA44],1; jne` · `cmp qword [rbx+0x790],0; jne` → `mov byte [rbx+0x7B0],1` → `jmp 0x5614690` → `GoToPhase(2)`. [M] ★ A **real, non-stub, BlueprintCallable writer of that FString exists**: `ALokiGameState::SetSharedMatchStartDetails`, thunk `0x538AB40` (fold 1) → impl **`0x56A0A40`** = `add rcx,0x738; call 0xFA2190` + a TArray copy into `+0x748`. Flags `0x04420405` include `BlueprintAuthorityOnly`, which `ProcessEvent` enforces and a direct `UFunction.Func` call does not [I, untested].
- **3→4** is Tick `0x5613200`: `cmp byte [rbx+0x7C0],4` (the `FLokiGameModeInitializer` stage) and `movzx eax,[rdi+0xA44]; cmp al,3`. ★ **The non-phase half already succeeds in real runs** — corpus-wide `LogLokiGameModeInitializer` walks `Starting→Priming→MemoryReport→WaitingForClientsReady→Finished` **189–193 times** across the log corpus. **The ONLY unmet condition for `GoToPhase(4)` is `CurrentPhase == 3`.** [M]

**★ And `GoToPhase` does not early-out in the live game — this is now a receipt, not an inference.** The constructor initialises `CurrentPhase` to 0 (`0x56772CF mov byte [rdi+0xA44], r12b`, with `0x5676B01 xor r12d,r12d` the sole `r12` definition in the one chained function `0x5676AA0..0x5677405`), so old=0 ≠ new=1. Corpus-wide, `Setting Phase to 1 (BeginInit)` and `Transitioning from phase (ERoundPhase::EGP_ServerStartup) to phase (ERoundPhase::EGP_BeginInit).` each occur **193 times over the SAME 193 files, one each**. Both logs gate on the **same verbosity byte `0xA036D00` at the same threshold 5** (`0x5601076` and `0x56011CF`, both machine-resolved), so the pair is discriminating rather than a verbosity accident. [M] ⇒ with the store dead, **every** `GoToPhase(N≠0)` passes the `cmp r14b,dil; je` gate. [I — bounded by coverage and by replication.]

⚠⚠ **REFUTED — do not restate line 1's finding 9.** It claimed *"transitions 4→5, 6→7 and 7→8 have NO native caller anywhere in the image, so they can only originate in Blueprint."* That is a **universal negative asserted over a 45 %-dark image**: `merged2` `.text` is **16,638 decrypted of 30,281 pages = 54.95 %**. The verifier produced the concrete counterexample from inside the finding's own set — **`0x5614690`, one of the seven callers, is an all-zero page in 15 of the 16 single-state dumps** and is non-zero only in `dumps/toggles`; had that state not been merged, the "exhaustive" set would have been 7, not 8, and the `GoToPhase(2)` restart path would have been written up as having no native caller. Second, smaller gap: `0x5601020` is also address-taken by `lea rax,[rip+0x1AD560]` at **`0x5453AB9`** (the UHT registration builder), so *all rel32 call/jmp xrefs* ≠ *all references*. **The survivable claim is scoped:** *within the 54.95 % of `.text` decrypted in merged2, no call/jmp reaches `GoToPhase` with 5, 7 or 8.* Verdict for the dark remainder is **COVERAGE-BLOCKED, not ABSENT.**

---

### 10.2 What `[vtable+0xB08]` is — and lever (b) is **OPEN**

FK-22's UNRESOLVED #3 is answered, [M], by two agents on two independent routes.

**Slot `+0xB08` (index 353) is `ALokiRoundGameMode::OnNewPhase`, base impl `0x5608F20`.** The naming does not rest on a guess: the `.data` registration record at **`0x9C1F328`** = `{name→"OnNewPhase" @0x8A4EBD8, exec thunk 0x5457480 (fold 1), impl 0x330C56C}`, and the bytes **at** `0x330C56C` are `48 8B 01 FF A0 08 0B 00 00` = `mov rax,[rcx]; jmp qword [rax+0xB08]`. The record layout was validated on a known answer two slots earlier — `0x9C1F298` = `{"GoToPhase", 0x5457200, 0x5601020}`, reproducing this document's ground truth exactly — and the whole class block was enumerated (`GoToPhase`, `ModeSupportsDropPlane`, `OnNewPhase`, `CompleteRound`→`0xB10`, `OnRoundTimerExpired`→`0xB18`, `OnSuddenDeathTimerExpired`→`0xB20`, `RestartRound`→`0xAF8`, …). ⚠ **`0x330C56C` is fold 3** (`.data 0x9A492B0` "GetBeamSourceTangent", `0x9B69198` "SetColorOverrideMode", `0x9C1F338` "OnNewPhase") — **non-identifying on its own**; the fold-1 exec thunk `0x5457480` is the identifying field.

Vtable derived by name, not by pattern: `GetPrivateStaticClass 0x5453580` (sole `lea` to the literal `"LokiRoundGameMode"` @ `0x8A4F332`, `InSize = 0x7D8`) → `ClassConstructor 0x5452900` → ctor `0x55EECB0`, which stores **`0x8A52A98`** at `[rbx]`. `0x8A52A98+0xB08` reads `0x5608F20` in merged2, tutorial-hero and accountpass.

**It is REAL and it is a dispatcher.** 4,340 bytes (`0x5608F20..0x560A014`, **7** chained `.pdata` rows — head flags `0x3`, six follow-ons `0x4` UNW_FLAG_CHAININFO, so one function; ⚠ line 2 said "9 rows", which was the jump-table entry count leaking in). Body: `0x5609006 lea eax,[r14-1]` · `cmp eax,8; ja` · `mov ecx,[rdx+rax*4+0x5609FF0]; add rcx,rdx; jmp rcx`. Table at `0x5609FF0` = `{0x5609037, 0x5609066, 0x5609F32, 0x560915F, 0x560945F, 0x56096CE, 0x560997E, 0x5609CA2, 0x5609F05}` + `0xCC` padding. **Fold multiplicity: 6 stored pointers, all in `.rdata`, every one exactly `vtable+0xB08` of a family vtable and ZERO in `.data` — inheritance by 6 classes, not ICF.**

**★ The ladder is self-driving by timer once a phase actually lands** [M]: case **Pre(2)** → `SetTimer` → the 7-byte thunk `0x560A1A0` → `GoToPhase(3)`; case **SpawnReveal(5)** → timer → `0x560AA70` → `GoToPhase(6)`; case **Post(8)** → timer → `0x560A090`, which branches on the `'ExitOnMatchEnd'` token → `GoToPhase(9)` or `GoToPhase(2)`. ⚠ Case 9 is not a bare fall-through: it sets `byte[rdi+0x5E8]=1` and calls `[rax+0xA70]` first.

**★ The Lineup case sits directly on FK-22's target** [M]: `0x56096CE mov rcx,rdi` · `0x56096D1 call 0x5453730` = **`ALokiRoundGameMode::ModeSupportsDropPlane`** (thunk `0x5457380`, both fold 1, named from the `.data` triple `0x9C1F2E0`) · `test al,al; jne` · **`0x56096E0 call qword ptr [rax+0xB00]`**. The occupant of `+0xB00` is **UNNAMED** — no reflected UFunction of this class resolves to it, and the generic forwarder `0x330C560` is fold 2 with neither registration in this class's block.

**★ And there is a Blueprint hop, unconditional** [M]. OnNewPhase has exactly **one** `ret` (`0x5609F9C`), and a guaranteed tail at `0x5609F3A` reached by 12 enumerated branches. That tail does two things:

1. `0x5609F4D`: `movzx edx,[rbp-0x79]` (new) · `movzx r8d,r13b` (old) · `mov rcx,rdi` · `call 0x54532B0` — a UHT ProcessEvent stub (`mov rbx,[[rcx]+0x270]` → `FindFunctionChecked 0x1344150` → 2-byte Parms → `call rbx`), **0 stored pointers, exactly 1 rel32 caller**, for **`ALokiRoundGameMode::BP_OnNewPhase`, flags `0x08020800 = Event|Public|BlueprintEvent`** — a pure BlueprintImplementableEvent, and the **only multi-param BP event on the class** (UHT property array `0x8A4DC00` = `{UnderlyingType, NextPhase, UnderlyingType, LastPhase}`; the other two BP events have null arrays).
2. `0x5609F3A: mov rcx,r14; call 0x569AC50` — `OnRep_CurrentPhase_Internal`, which does `movzx edx,[rbx+0xA44]; lea rcx,[rbx+0x590]; call 0x442B4C0`.

**★★ The tutorial receives the event.** `ALokiTutorialGameMode` (`GetPrivateStaticClass 0x548C030`, sole `lea` to `"LokiTutorialGameMode"` @ `0x8A92CE2`; SuperClassFn `0x52D3630 = jmp 0x5453580`; ctor `0x548CB40` calls `0x55EECB0` then stores vtable `0x8A94C48`) **does not override slot 353** — `0x8A94C48+0xB08 = 0x5608F20` in all three images. `BP_LokiGameMode_Tutorial.json` gives `SuperStruct = Class'LokiTutorialGameMode'`, and `BP_LokiGameMode_Tutorial_C` **implements `BP_OnNewPhase(NextPhase, LastPhase)` → `ExecuteUbergraph_BP_LokiGameMode_Tutorial(8046)`** (bpdump header verified; the BP function's own `SuperStruct` is `Class'LokiRoundGameMode:BP_OnNewPhase'`). Across the whole 8-vtable family only two classes override the slot — `ALokiBattleRoyaleGameMode` `0x5608BD0` (`cmp dl,4` = SpawnSelect → `call 0x560EE70` → Super → `cmp bl,7` = Combat) and `ALokiGameModeDefusal` `0x5608EB0` (`cmp dil,6` = Lineup → `call 0x534F020` → Super) — **and both call the base**, so nothing in the family suppresses the event.

**⇒ Lever (b) does a great deal.** `GoToPhase(N)` reaches a real 4,340-byte per-phase dispatcher, arms the timers that self-drive 2→3 / 5→6 / 8→{9,2}, branches on `ModeSupportsDropPlane` at Lineup, and hands `(new, old)` to Blueprint on a path the tutorial implements — **all of it downstream of the dead store, none of it requiring the byte to move.**

⚠ **One qualification neither line stated plainly:** the tail's delegate broadcast reads the **STORED** byte, which is frozen at 0. So the *delegate* half of lever (b) is inert even though the *dispatch* half is live, and **nothing that polls `GetCurrentPhase` (`0x5384610 = movzx eax,[rcx+0xA44]; ret`) will ever see a change from `GoToPhase` alone.**

---

### 10.3 The `OnRoundPhaseChanged` subscriber path — and what lever (a) actually does

**The delegate is a DYNAMIC MULTICAST, not FK-15's single-cast `FDelegateBase`.** `0x442B4C0` (23 B, byte-identical in both images) packs one byte and calls `0x1342340`, which reads **`mov edi,[rcx+8]` … `test edi,edi; jle <return>`**, then `mov rbx,[rcx]`, walks at **stride 16**, and per entry dispatches `call qword ptr [r9+0x270]` (ProcessEvent). ⇒ layout **`GameState+0x590` = `FScriptDelegate* Data`, `+0x598` = `int32 Num`, `+0x59C` = `int32 Max`**, and **the broadcast is a hard no-op when `Num <= 0`.** [M] ⚠ `0x442B4C0` has **0 stored pointers and ~28 rel32 call sites** — non-identifying; it identifies nothing on its own.

Signature: `NewRoundPhase__DelegateSignature` (`FFunctionParams 0x9BE7800`) has `NumProperties = 2`, `StructureSize = 1`, properties `{UnderlyingType, NewPhase}` — **ONE byte-sized enum param**. `BP_AuthSetCurrentPhase` impl `0x567A160` = `add rcx,0x590; jmp 0x442B4C0` passes `dl` straight through. No signature mismatch anywhere. [M]

**★★ THE SYNTHESIS POINT NEITHER LINE MADE: there are two broadcast sites with two different sources.**

| site | source of the value | consequence |
|---|---|---|
| `0x569AC50` (OnNewPhase tail, native) | `movzx edx, byte [rbx+0xA44]` — the **STORED** byte | frozen at **0** forever; broadcasts `ServerStartup` no matter what phase was requested |
| `0x567A160` = **`BP_AuthSetCurrentPhase`** | `dl` — the **ARGUMENT** | broadcasts **any value you pass**, with no gate, no authority test and no dependence on the dead store |

⇒ **lever (a) is the only route in the image that can put a non-zero `ERoundPhase` value into that delegate.** [M]

**Who subscribes:**

- ⛔ **The DropPlane components' `ReceiveBeginPlay` subscription is unreachable dead code, in BOTH variants** [M]. `ULokiBlueprintLibrary::ServerOnly` — name/thunk pair `.data 0x9BBAFB8` → thunk `0x52E12B0`, whose last direct call after P_FINISH (cookie `0x751DEB0` excluded) is `0x52E1367 → 0x1311870`, and `0x1311870` = **`C6 02 00 C3` = `mov byte [rdx],0; ret`**, present and identical in **18 of 18** dump images. `EServerOnlyExecPins::Hidden = 0 / ::Server = 1`, read from the UHT enumerator records (`.rdata 0x88BF3E8/0x88BF3F8`), with the sibling `EClientOnlyExecPins` (Client=0, Hidden=1) as control. Both `Comp_GameMode_DropPlane_Tutorial_C` (`[91]-[97]`, gate `NotEqual_ByteByte(OutputExecs, ByteConst 1)` → bind at 2273) and `Comp_GameMode_DropPlane_C` (`[141]-[145]`, bind at 3545) bind **only when `OutputExecs == 1`**, and each bind block has exactly **one** inbound reference — the gate. ⇒ that bind can never execute. *(`execServerOnly` and `execClientOnly` are ICF-folded to the same thunk, which is coherent: on a client both compile to "write 0" — Hidden = stop, Client = continue.)*
- ⚠⚠ **BUT "both DropPlane subscriptions are dead" is REFUTED.** The verifier found **two further, UNGATED** binds of the same handler onto the same delegate, **from the finder's own corpus list**: `Comp_GameMode_DropPlane_Tutorial_C::SpawnPlane` (`[38]-[40]`, **zero** occurrences of `ServerOnly` in the whole function) and `Comp_GameMode_DropPlane_C::OnDeathCircleSet` (`[90]-[92]`, likewise zero, then `[95]` invokes the handler directly). ⇒ the drop-plane handler **is** reachable via the delegate; only one of its three bind sites is dead.
- ★★ **And the tutorial handler is a phase switch that calls `GoToPhase` back.** The tutorial component's `On Round Phase Changed` stub enters its ubergraph at **545**, where `[24]-[31]` chain `NotEqual_ByteByte(NewPhase, ByteConst 5 / 6 / 7)` and **the 6-arm reaches `[31] EX_Context{LokiGameMode} EX_FinalFunction GoToPhase(ByteConst 7)`**. The general variant's handler at ubergraph **1403** is FK-22 §2.6's `NewPhase==6 → PlayerArray loop → AddPlayerToDropPlane`. ⚠ Whether `SpawnPlane` / `OnDeathCircleSet` ever run on the tutorial route is **UNMEASURED** — neither is referenced from either ubergraph, so their callers are elsewhere.
- **`BP_LokiHeroCharacter_C` subscribes UNGATED** [M]: `BP_LokiBeginPlay` → `ExecuteUbergraph(34335)` → `[1302] EX_Jump 5269` → `[200]@5397 BindDelegate RoundPhaseChanged` → `[201] AddMulticastDelegate`. All **13** `ServerOnly` sites in that ubergraph were enumerated (offsets 1014…28810) and **none** brackets 5397; inbound refs: 34335→0 (entry), 5269→1. `BP_HERO_Ronin_C` (the tutorial hero) does **not** override `BP_LokiBeginPlay` (22 UFunction exports listed, absent) so the parent body is what runs [I — whether native `BeginPlay` invokes it on a client is undisassembled].
- **Angelscript** [I, lifted pseudo-source]: `ULokiPlayerRespawnComponent` binds **ungated** and its handler acts on `EGP_Combat(7)` → `CheckSetInitialRespawn` → `Unbind`; **and it first polls `GetCurrentPhase()`** — a consumer that lever (b) can never satisfy and lever (a)+poke can. `BarracudaMinionSpawner` binds behind a real `LokiIsServer` test. Corpus: 4 of 78 AS files mention `RoundPhase`.
- ⚠ **Line 3 mis-verdicted `ULokiPreloadComponent::OnRoundPhaseChanged` as COVERAGE-BLOCKED.** Its thunk `0x5442960` really is 32 zero bytes in 18/18 — but the **same `.data` triple** the finder used elsewhere gives impl **`0x56C58A0`**, whose bytes read `80 FA 07 / 0F 86 … / C3` = `cmp dl,7; jbe …; ret` — **a REAL body, present in 18/18.** It is gradeable today and it is real.

**⇒ Lever (a) is NOT inert, and the "it can only reach dead code" reading is withdrawn.** It is the only way to put a chosen phase value on the wire, it has at least four candidate subscriber routes, and on the tutorial DropPlane component the value **6** drives a Blueprint that calls `GoToPhase(7)`. What is **UNMEASURED** is whether `Num` at `GameState+0x598` is non-zero at the moment of the call — and that is a one-word RPM read.

---

### 10.4 The phase-free bypass: the sequence, and where it terminates

**Its documented entry point is not callable.** ⛔ **`ALokiDropPod::InitializeDropPod` carries NO `UFUNCTION` decorator** — three independent passes over `tools/asdump/out/modules/GameMode/DropPhase/LokiDropPod.as.txt` agree on **24 decorators against 99 trait-bearing signatures** (75 bare), with `InitializeDropPod` at `:843` blank-preceded and the known positives `StartPodGameplay :896`, `OnPodTeamIndexChanged :1153`, `FinishDestroyPod :2193` decorated. Second instrument: **`^ALokiDropPod,` = 0 rows** in the 18,325-row `uht_funcflags_tuthero.csv`, against positive control `^ALokiDropPodBase,` = **6 rows**. ⇒ the S55 name-resolving primitive cannot reach it. **`docs/angelscript-dropphase.md` §6.2's two-call recipe and FK-22 §3 row 7' are dead as written**, and 3 of the 10 functions §6.2 lists as "all `UFUNCTION(BlueprintCallable)` too" (`SetDropPodState :1420`, `SpawnImpactIndicator :4404`, `SpawnLaserIndicator :4520`) are not UFUNCTIONs either.

**The substitute, all REAL native UFunctions (each fold 1, each name→thunk re-derived from the `.rdata` pairs by both agents) plus reflected data pokes, no `.text` write:**

1. `ULokiGameplayStatics::SpawnActorFromClass` — thunk `0x537E8C0` → impl `0x566EB70` **REAL** (321 B) — spawn `BP_DropPod_C`
2. `ALokiDropPodBase::SetPilotPlayerState` — thunk `0x53375E0` → impl **`0x55E59E0`** = `mov [rcx+0x3C0],rdx; mov r8d,0xB; mov rdx,[rcx+0x30]; jmp 0x1E3CCD0` **REAL**
3. `AActor::SetOwner` — flags `0x04020402` `RequiredAPI|Native|Public|BlueprintCallable`; **impl UNGRADED** (natreg is blind to `AActor`)
4. poke the replicated script UPROPERTYs `CurrPodDestination` (FVector) / `bIsTeamLeaderPod` / `PodTeamIndex` / `LeaderPod`
5. `ULokiTeamStatics::SetTeamForActor(pod, TeamIndex >= 0)` — thunk `0x5485920` → impl `0x56FBCF0` **REAL** (220 B)
6. → the pod's own `OnPodTeamIndexChanged` (a `UFUNCTION(BlueprintCallable, CanOverrideEvent)`) fires on the first `<0 → >=0` transition and calls `StartPodGameplay()`; **`LokiBeginPlay` was written for exactly this late-start ordering** (`:504-556`: `CMPIi v2 0` / `JS 5 → L0098` / `CALLINTF StartPodGameplay` else `ADDSi 208 ; .OnTeamIndexChanged` / `CALLSYS AddUFunction`)
7. `StartPodGameplay()` is idempotent (`bHasStartedGameplay`) and arms `SetTimer(this, n"OnIntroSequenceFinished", …)`
8. → intro → `UpdateCharacterLocations` (gated `state == 4`) → `ULokiRideableComponent::GetLandingTeleportLocation` (**COVERAGE-BLOCKED**, thunk `0x5456C80` zero in 18/18) → `SetCharacterLanding`
9. `ALokiPlayerController::FinishDropPhaseHiding` — thunk `0x5424710` → impl `0x568EE50` **REAL**

**★ Where it terminates: a teleport the project already owns.** `SetCharacterLanding`'s entire body is `AActor::K2_SetActorLocation` (twice, with a `GetDropAboveAmount` pre-lift). **CONTROLLED NEGATIVE:** `GlideDive` appears in **0 of 78** AS module files against positive control `Glide` = **2**; `SetMovementMode` = **0**. ⇒ the shipped pod→hero handoff is a plain teleport onto an **already-spawned, already-possessed** hero — which S107/S108's shim already produces, walking, with locomotion. **The bypass buys a visual, not a capability.**

**Two further corrections it produced, both worth keeping:**

- ⚠ **FK-22's `EndGlideDive impl 0x055A8580 REAL 1296B` is wrong.** That impl is an **11-byte setter**, `C7 81 4C 12 00 00 00 00 80 BF C3` = `mov dword [rcx+0x124C], -1.0f; ret`, and it has **no `.pdata` row at all** (controls in the same lookup fire: `EndGlide 0x55A8470` = 257 B EXACT-START, `AuthBeginGlideDiveFromDropPod 0x530BFD0` = 274 B). FK-22's strongest affirmative argument for a live glide state machine is therefore much weaker than recorded — though the machine **is** still live, on four other consumers (the ULokiCMC ctor's `-1.0f` init at `0x559F73A`, the move pack `0x55C00C0`, the unpack `0x55A6A30`, the FSavedMove pair) that replace it.
- ⚠ **`SetMovementMode(MOVE_Custom, 4)` targets the wrong thing.** The custom-mode table, read from each getter's own `mov byte [r8],N`: **2 Mantling · 3 Grinding · 4 DropPlane · 5 Gliding · 6 FollowActor · 7 Floating**, Parachuting = 1; and `IsGlideDiving` (`0x55B17C0`) = `MovementMode==7 && CustomMovementMode==5 && float[CMC+0x124C] >= 0`, with `IsGliding 0x55B17F0` the identical predicate minus the `comiss`. **Glide dive is Gliding plus a timer, not mode 4.**

**And it carries a precondition the phase levers do not:** `ALokiDropPod` / `ALokiDropShip` have **0 UHT rows each** (control `ALokiDropPodBase` = 6), so every script step depends on the Angelscript module having registered its UClasses in the staged world — **measured false at the menu (FK-1), never measured in-world.**

⚠ **REFUTED sub-claim:** *"`PlayersInside` can never be populated, so `UpdateDropPhaseHiddenActors` is dead."* `AuthAddPlayer`/`AuthRemovePlayer` really are empty folds (thunk `0x2C2CE30`, **23** stored pointers, `call 0xF7EC20`), but that is a universal negative over precisely the functions the same finding declares unreadable — `AuthPlayerEnterWorld`, `AuthPlayerEnterWorldNew`, `AuthPlayerEnterWorldAttachedToRidable` and `AuthPlayerPreSpawnOnAddToPlane` all sit on the same all-zero page `0x5456000`. And `PlayersInside` is a plain member at offset **`0x120`** (`ADDSi 288`), i.e. directly pokeable by the very technique the report advocates elsewhere.

---

### 10.5 ★ THE DECISION

**Ranked, bluntly.**

> **1. `GoToPhase(N)` via its fold-1 exec thunk — lever (b).** The only lever measured to reach real, phase-dispatching native code, a self-driving timer ladder, `ModeSupportsDropPlane`, and a Blueprint hop the tutorial implements. Its early-out is passable for every `N ≠ 0` because the stored byte is frozen at 0. Costs one reflected call, no poke, no `.text`.
> **2. A one-byte poke of `GameState+0xA44`.** Not a lever on its own, but it is the *only* way to satisfy the two **already-running** native gates (`0x560AF10` needs `==1`; Tick `0x5613200` needs `==3` with its other condition already met) and the only way any `GetCurrentPhase` consumer — including the AS respawn component — can observe a phase.
> **3. `BP_AuthSetCurrentPhase(N)` — lever (a).** The sole route that puts a chosen value on `OnRoundPhaseChanged`. Ranks third only because its effect is invisible if `Num @ +0x598` is 0, and that has never been read.
> **4. The phase-free bypass. A distant last.** Entry point not callable, AS registration unmeasured in-world, terminal capability already owned.

**⚠ Two free offline steps come first, and neither costs a launch.**

- **(i) `bpdump BP_LokiGameMode_Tutorial ExecuteUbergraph_BP_LokiGameMode_Tutorial`, read offset 8046** (~40 s). `ALokiTutorialGameMode` inherits the **base** `OnNewPhase` with no phase-4 branch (unlike BR's `cmp dl,4`), so on the tutorial route **the entire payload of `GoToPhase(N)` above the timers is that Blueprint body, and it is currently UNKNOWN.** This does not block the flight — arm A3 below is worth a window on its own — but it decides what the receipts should say.
- **(ii) Bank a `usmapdump dumpimage` from the staged sitting as a rider.** Pages `0x560EE70` (BR phase-4 body), `0x5456000` (all five `AuthPlayerEnterWorld*` + `GetLandingTeleportLocation`), `0x55A3000` (`BeginGlide`/`BeginGrind`/`BeginMantle`/`BeginFollowingActor`) and `0x55A8000` are zero in **18 of 18** images today. One dump converts ~8 UNKNOWNs into measurements for free. ★ Per the S120 before/after-diff method, dump **before** the arms and **again after** — `.text` decryption is monotone within a lifetime, so the delta is exactly the code your calls just ran.

**PRE-REGISTERED ARMS — one staged tutorial window, strictly in this order.**
*Pointers: GameMode from `World->AuthorityGameMode`; **GameState from `[GameMode+0x258]`** (the offset `OnNewPhase` itself uses at `0x5608FB8`).*

| # | action | pre-registered receipt (grep `Loki.log`) | if the receipt is absent |
|---|---|---|---|
| **A0** | RPM only, no calls. Read `GameState+0xA44`, **`GameState+0x598` (delegate `Num`)**, `GameMode+0x7C0`, `GameMode+0x790`, `GameMode+0x7B0` | `+0xA44 == 0`; `+0x7C0 == 4`; record `Num`. Log contains **exactly one** `Setting Phase to 1 (BeginInit)` and **exactly one** `Transitioning from phase (ERoundPhase::EGP_ServerStartup) to phase (ERoundPhase::EGP_BeginInit).` | staging is wrong; abort |
| **A1** | **POSITIVE CONTROL** — call `GoToPhase(1)` | **the same pair appears a SECOND time in the same file.** Baseline is 193 files × exactly one occurrence, so a duplicate is unambiguous and cannot come from the game | **the sitting is VOID.** Interpret nothing else. Do **not** accept "the call returned ok" |
| **A2** | **TREATMENT** — call `GoToPhase(4)` | `LogLokiRoundGameMode: Setting Phase to 4 (SpawnSelect)` **and** `Transitioning from phase (ERoundPhase::EGP_ServerStartup) to phase (ERoundPhase::EGP_SpawnSelect).` — **neither string exists in any of the 193 corpus logs**. Plus whatever (i) predicts from ubergraph 8046 | dispatch reached the dead setter but not the second log ⇒ re-read the verbosity byte `0xA036D00` |
| **A3** | RPM: re-read `GameState+0xA44` | **still `0`.** This converts the offline [I] "the store is dead" into a live [M], and it is the cheapest [I]→[M] on the board | a non-zero value means a writer exists outside the decrypted 54.95 % — a major result either way |
| **A4** | poke `GameState+0xA44 = 3`, hold ~2 s, then poke `= 4` | Tick fires on its own: `Setting Phase to 4 (SpawnSelect)` with **`Transitioning from phase (ERoundPhase::EGP_FinishInit) to …`** — a *different* transition string from A2, proving the already-running native gate is what actuated | gate unmet ⇒ re-read `GameMode+0x7C0` |
| **A5** | **only if A0 read `Num > 0`** — call `BP_AuthSetCurrentPhase(6)` | on the DropPlane path, the tutorial handler's 6-arm calls `GoToPhase(7)` ⇒ expect `Setting Phase to 7 (Combat)` **with no `GoToPhase` call of ours** | if `Num == 0`, **do not run A5** — a broadcast into an empty invocation list is a hard no-op at `0x134236C`, so silence would be uninterpretable, not negative |

⚠ **ORDERING, and why:** `GoToPhase`'s gate is `cmp <arg>, [GameState+0xA44]; je bail`. **Poking the byte to `N` and then calling `GoToPhase(N)` is self-defeating — the early-out swallows it.** The correct orders are **`GoToPhase(N)` first, then poke** (A2 → A3 → A4), or **poke to `N−1`, then `GoToPhase(N)`**, which additionally hands `OnNewPhase`/`BP_OnNewPhase` a *correct* `LastPhase`.
⚠ **A4's loop hazard:** with the store dead, `+0xA44` stays 3 and Tick will re-fire `GoToPhase(4)` **every frame**. The trailing poke to `4` (which fails Tick's `cmp al,3`) is the stop, and it is part of the arm, not an afterthought.
⚠ **"The call returned ok" is not a success criterion.** Every receipt above is the verb's own log output or an RPM readback, and A1 exists solely so that a null in A2–A5 can be distinguished from a shim that never ran.

---

### 10.6 What remains UNRESOLVED

- **What `ExecuteUbergraph_BP_LokiGameMode_Tutorial(8046)` does.** The single highest-value ~40 s offline step; it is the tutorial-side payload of the entire phase lever.
- **The occupant of `[vtable+0xB00]`,** called from OnNewPhase's Lineup case when `ModeSupportsDropPlane()` returns false. No reflected UFunction of `ALokiRoundGameMode` resolves to it (the class block was fully enumerated); forwarder `0x330C560` is fold 2 with neither registration in this class.
- **Whether `ALokiGameState::MatchStartDetails` is non-empty on the tutorial route** — NOT-LOOKED-FOR. It is one third of the 1→2 gate and might already be satisfied. One RPM read of `GameState+0x738/+0x740`.
- **Whether a direct `UFunction.Func` call bypasses `FUNC_BlueprintAuthorityOnly`** on `SetSharedMatchStartDetails` — [I] from this project's own ProcessEvent model, never tested.
- **Whether `SpawnPlane` / `OnDeathCircleSet` ever run** — the two UNGATED delegate binds. Neither is referenced from either ubergraph; their callers are unlocated. Until this is settled, §10.3's DropPlane route is **[S]**, not [I].
- **`Num @ GameState+0x598` at any moment.** Never read. It gates the interpretability of every lever-(a) result.
- **Whether native `ALokiCharacter::BeginPlay` invokes `BP_LokiBeginPlay` on a client** — everything downstream of that call in the hero subscription is [M]; the call itself is [I].
- **`Comp_GameMode_DropPlane_PvE_Holdout`'s gate** — its ubergraph was never dumped. NOT-LOOKED-FOR.
- **Names for `0x5614690`, `0x560A090`, `0x560A1A0`, `0x560AA70`, `0x560AF10`** — none is a reflected UFunction, this build has no RTTI (`vtable[-1]` is not a COL), and vtable-displacement identification was **abandoned as non-identifying** (the `0x8F0` call sites pass three arguments while `0x560AF10` consumes only `rcx` — proof of cross-class displacement collision). `0x55F3740 = BeginPlay` and `0x5613200 = Tick` rest on Super-slot identity plus argument shape, not on a name string — **[I]**.
- **The `ELokiInitializationStage` index→name mapping (`Finished == 4`)** — [I] from five named transitions plus Tick's "advance while != 4" loop, not read from an enum table.
- **`ELokiDropPodState` value table** — `UpdateCharacterLocations`'s gate `v2 == 4` is *asserted* to be `OutroSequence`; unverified.
- **Whether `BP_DropPod_C`'s UClass is loaded in `LVL_Tutorial` at all**, and whether AS UClasses register in-world (FK-1 measured 0/15 at the menu, 3 native controls passing).
- **Impls of `AActor::SetOwner` / `K2_SetActorLocation` / `FinishSpawningActor`** — graded from UHT flags only; `natreg` is blind to `AActor`.
- **`ALokiPlayerController::DropPlaneComponentSetup`** resolved to `0x1342340` (CoreUObject region) — treated as a mis-resolution, reported UNRESOLVED rather than as a finding.
- **Coverage-blocked, denominator stated:** `0x560EE70`, `0x5456C80`, `0x55A34E0/37F0/3F50`, the five `AuthPlayerEnterWorld*`, `TryLaunchDropPod`, `SelectDropPodDestination`, `FindValidDropLocationInRadius`, `SetDropPlane` — **0 of 18** images, and the ULokiCMC control page is decrypted in only **3**. ⚠ Coverage is **not uniform per region** (`IsGlideDiving` non-zero in 4 images, `SetPilotPlayerState` in 7), so "denominator 3" is control-specific and must be re-measured per address.
- **`Num`, `MatchStartDetails`, `+0x790`, `+0x7B0`, `+0x7C0`** are all mutable globals/instance state — **never read them from `merged2`**; single-state dump or live RPM only.

---

### 10.7 New instrument artifacts (register: `docs/method-rules.md` §1)

1. **★★ A hand-written character class as a universal negative.** `grep 'Transitioning from phase \([A-Za-z]*\) to phase \([A-Za-z]*\)'` returned **0**, and the conclusion drafted from it was *"`GoToPhase` early-outs and `OnNewPhase` is never reached"* — the exact opposite of the truth. `%s` renders the **scoped** enum name `ERoundPhase::EGP_ServerStartup`; `[A-Za-z]*` cannot match `:` or `_`. The bare token returns **193 occurrences across 193 files**. Self-caught. **Rule: grep the bare token first, constrain afterwards. A zero from a hand-written regex is a statement about the regex.**
2. **★★ A universal negative asserted over a 45 %-dark image.** *"Transitions 4→5, 6→7, 7→8 have NO native caller anywhere"* — from an `E8`/`E9` sweep of a `.text` that is **16,638 of 30,281 pages decrypted (54.95 %)**. The brief's own instruction ("treat 8 as an upper bound") was inverted into an exhaustive lower bound. Demonstrated concretely: `0x5614690`, itself one of the seven callers, is a **zero page in 15 of the 16 single-state dumps**. **ABSENT ≠ COVERAGE-BLOCKED, again.**
3. **★★★ Writing down the lower-bound caveat and then reasoning past it.** Line 3 explicitly recorded *"the BP subscriber census is a LOWER BOUND, not a map"* — and in the same report claimed *"BOTH shipped DropPlane subscriptions are dead code."* **The two refuting files (`bpdump_SpawnPlane.txt`, `bpdump_OnDeathCircleSet.txt`) were named in its own corpus list and not followed.** Stating a caveat is not the same as honouring it.
4. **★ A `.pdata`-anchored scan is blind to functions with no `.pdata` row.** Line 4's two-stage disp32 scanner **missed `EndGlideDive` (`0x55A8580`) itself** — the very function it was correcting — because the address has no unwind entry. Disclosed by the finder; caught only because the address was already in hand from another route.
5. **★ Grading REAL under coverage blindness.** `BeginFollowingActor` was listed as REAL in the same paragraph that correctly listed its siblings as coverage-blocked; its impl `0x55A33F0` is a **zero page in 18 of 18** images. The strip enumeration around it is sound; one row of the control list is not.
6. **★ Fold multiplicity omitted beside a folded address.** `0x330C56C` was graded as the OnNewPhase forwarder without stating it is **fold 3**. The conclusion survives (it rests on the fold-1 thunk `0x5457480`), but the brief's own rule was broken inside the report that names the rule.
7. **★ A verdict that contradicts the reporter's own instrument.** `ULokiPreloadComponent::OnRoundPhaseChanged` was filed COVERAGE-BLOCKED on a zero **thunk**, while the identical `.data` triple the same agent used two claims earlier yields impl **`0x56C58A0`** = real bytes in 18/18. **Apply your own resolution method to your own negative before recording it.**
8. **★ The digest-compression artifact recurred.** Line 4's summary says the phase lever *"collapses to a single `BP_AuthSetCurrentPhase(4)` call … with zero pokes"* — which its own finding 13 refutes, since `0x567A160` provably does not write `+0xA44`. Same shape as the S115-d `exec thunk = impl` compression: a correct measurement flattened into prose that asserts more than the bytes do.
9. **★ Denominator correction, then over-generalisation.** "0/18 images" was correctly self-corrected to "0/3" (the control page is decrypted in only 3) — and then applied as if `.text` coverage were one unit, which it is not (`IsGlideDiving` 4, `SetPilotPlayerState` 7). **Measure the denominator per address, not per region.**
10. **★ REX-prefix drop, reproduced and caught.** A byte-pattern search for stores to displacement `0xA44` reported `0x56772D0`; linear decode corrected it to **`0x56772CF`** (`44 88 A7 …`, the REX byte). Exactly the defect the brief warns about, fired a fourth time, and caught by the mandated boundary check.
11. **★ Free control worth reusing:** the two `GoToPhase` log lines gate on the **same** verbosity byte `0xA036D00` at the same threshold, machine-verified at both sites. That is what makes "one present, the other absent" a discriminating test rather than a verbosity accident — **before treating a log pair as a control, prove they share a gate.**

---

## 11. Session-lead verification of §10 (independent)

The **naming instrument** — the `.data` registration triple `{name*, exec thunk, impl}` — is what every
identification in §10 rests on, so it was validated on a known answer and then applied to the open one.
Read from `dumps/tutorial-hero/…dump.exe` (a **single-state** image; `.data` is mutable and must never be
read from `merged2`). ImageBase derived from the record itself, not assumed: `0x7FF6505C0000`.

```
record 0x9C1F298 -> name 0x8A4E850 = 'GoToPhase'   thunk 0x5457200  impl 0x5601020
                    bytes at impl: 40 55 53 56 57 41 57 48 8b ec 48 83     (matches §8's read)
record 0x9C1F328 -> name 0x8A4EBD8 = 'OnNewPhase'  thunk 0x5457480  impl 0x330C56C
                    bytes at impl: 48 8b 01 ff a0 08 0b 00 00
                                 = mov rax,[rcx] ; jmp qword ptr [rax+0xB08]
```

⇒ **[M] `[vtable+0xB08]` IS `ALokiRoundGameMode::OnNewPhase`.** FK-22's UNRESOLVED #3 (§8.4 caveat 3)
is **closed**, and closed by the artifact rather than by inference: the forwarder's own bytes name the
slot, and the record layout is validated on `GoToPhase`, whose thunk and impl were independently
established in §8/§9 by two other routes. The earlier `[I]` reading ("it is probably `OnNewPhase`, but
no `.data` record names it") was **correct in substance and wrong about the evidence available** — the
record exists; it had not been looked for at the right address.

★ Note the shape of that miss: a prior agent searched for a record and concluded none existed, then
graded the claim `[I]`. **A record you did not find is NOT-LOOKED-FOR.** Grading it `[I]` rather than
`UNRESOLVED` understated how cheaply it could be settled — it was one 12-line script away.

### 11.1 Corrections carried back into §8/§9

- **`GoToPhase`'s extent is `0x5601020..0x56012E0` = `0x2C0` bytes across 3 chained `.pdata` rows.**
  §8's `0x271 B` is the distance to the first bail block, not the function size. Both numbers describe
  something real; only one is the extent. **Cite `tools/strxref/index/pdata_union.csv`.**
- The rel32 caller sweep is independently reproduced (session lead + two agents, three sweeps,
  **set-identical at 8 hits**), and `0x545726B` is confirmed to be `exec thunk 0x5457200 + 0x6B`, i.e.
  the thunk's own `P_FINISH` call rather than a caller ⇒ **7 non-thunk callers.**
- ⚠ **But the sweep is NOT exhaustive and §10.7's artifact #2 governs**: it covers only the
  **16,638 of 30,281 `.text` pages (54.95 %)** decrypted in `merged2`. The concrete demonstration is
  internal to the result — `0x5614690`, *one of the seven callers*, is a zero page in **15 of the 16**
  single-state dumps and survives only because `dumps/toggles` was merged. Had it not been, the
  `GoToPhase(2)` restart path would have been written up as having no native caller at all.
  **For the dark 45 %: COVERAGE-BLOCKED, never ABSENT.**

### 11.2 What changed about the drop route

The phase blocker is no longer a flat wall. It is a **ladder with two already-running native gates**,
and the measurements name exactly which condition is unmet at each:

| transition | actuator | conditions | unmet |
|---|---|---|---|
| 0 → 1 | `BeginPlay` `0x55F3740` | none | — **fires today, 193/193** |
| 1 → 2 | `0x560AF10` | `MatchStartDetails` non-empty · `+0xA44 == 1` · `+0x790 == 0` | the phase byte, and `MatchStartDetails` **NOT-LOOKED-FOR** |
| 3 → 4 | `Tick` `0x5613200` | `GameMode+0x7C0 == 4` · `+0xA44 == 3` | **only the phase byte** — the initializer half already reaches `Finished` in **189–193** real runs |

⇒ **the single byte at `GameState+0xA44` is the whole difference between a frozen ladder and a
self-driving one**, and it is one aligned data poke on a reflected property of a client-resident
object — this project's safest measured write class (nothing 0/22 · bytecode 0/9 vs standing `.text`
7/8 at a 320 s hold), with `GetCurrentPhase` as a free readback.

---

## 12. The tutorial's `OnNewPhase` payload — §10.5's step (i), run

§10.5 named one free offline step as gating what the flight's receipts should say: *what does
`ExecuteUbergraph_BP_LokiGameMode_Tutorial(8046)` do?* It was run (~2 min, `extractor bpdump`).

**[M] The chain, end to end:**

```
ALokiRoundGameMode::OnNewPhase          native, vtable +0xB08, impl 0x5608F20
  -> BP_OnNewPhase                      BPGC stub, FUNC_Event|Public|BlueprintEvent, 5 statements:
       [0] LetValueOnPersistentFrame  K2Node_Event_NextPhase = NextPhase
       [1] LetValueOnPersistentFrame  K2Node_Event_LastPhase = LastPhase
       [2] EX_LocalFinalFunction      ExecuteUbergraph_BP_LokiGameMode_Tutorial(8046)
       [3] EX_Return / [4] EX_EndOfScript
  -> ubergraph offset 8046, statement [264], and it is TWO statements long:
       [264] EX_LocalFinalFunction  StackNode: BP_OnNewPhase (K2Node_Event_NextPhase, K2Node_Event_LastPhase)
       [265] EX_PopExecutionFlow        <- end of the handler
```

**[M] Class facts that settle how to read statement [264]:**
- `BP_LokiGameMode_Tutorial_C`'s `SuperStruct` is **`Class'LokiTutorialGameMode'` @ `/Script/Loki`** —
  a **native** class. There is **no intermediate Blueprint** in this mode's chain.
- The BPGC's `BP_OnNewPhase` export carries `SuperStruct = Class'LokiRoundGameMode:BP_OnNewPhase'`
  ⇒ `BP_OnNewPhase` is a **BlueprintImplementableEvent declared on native `ALokiRoundGameMode`**, which
  the tutorial Blueprint **overrides**.

⇒ **[I] Statement [264] is a Call-Parent node, not recursion** — `EX_LocalFinalFunction` targeting the
parent's `BP_OnNewPhase`. A `BlueprintImplementableEvent` on a native class has **no Blueprint body**,
so the parent call is a no-op. **The tutorial's entire phase-change handler is "call parent, return".**

⚠ **Graded [I], not [M], and the reason is a real limit of the instrument:** `bpdump` prints
`StackNode: BP_OnNewPhase` **unqualified**, so self-call and parent-call render identically. The
Call-Parent reading rests on (a) the native super, (b) the parent-declared BIE, and (c) the fact that a
self-call would be unconditional infinite recursion in a function the game demonstrably runs 193 times.
That is strong but it is inference. **To make it [M]:** resolve statement [264]'s `StackNode`
`FPackageIndex` against the package's import/export map and read which class object it names.

### 12.1 What this changes about the ranking

§10.5 ranked lever (b) first partly on *"a Blueprint hop the tutorial implements."* **That clause is
now wrong for the tutorial route** — the hop exists and delivers **nothing**.

⇒ **On the tutorial route, the entire observable payload of `GoToPhase(N)` is whatever NATIVE
`ALokiRoundGameMode::OnNewPhase` (`0x5608F20`) does** — the timer ladder, the `ModeSupportsDropPlane`
branch and the `[vtable+0xB00]` call — and **not** any tutorial Blueprint body. This does not knock
lever (b) off the top spot, because the native side is where the timers and the DropPlane branch live
and `ModeSupportsDropPlane` is hardcoded `EX_True` on this mode. But it **removes a reason** that was
being counted in its favour, and it means the flight's receipts must be **native** ones (the two
`GoToPhase` log lines, the timer-driven follow-on transitions) rather than anything Blueprint-side.

★ **It also makes A2's prediction sharper.** The BR mode's `OnNewPhase` has a `cmp dl,4` phase-4 branch
that the tutorial's inherited base does not; combined with the empty BP hop, `GoToPhase(4)` on the
tutorial route should produce **the two log lines and the timer arming, and nothing else visible.**
An observation richer than that would mean the model is wrong somewhere — which makes it a genuine
test rather than a confirmation.

---

## 13. The phase experiment — probes built, pre-registered arms

**Status: READY TO FLY.** Both artifacts are built, compile-clean, adversarially reviewed, and the
review's BLOCKER and all three HIGH defects are **fixed and re-verified in this session**. Nothing
here has touched a running client — every `.text` hash, import table and regression control below is
measured; every claim about what the *game* will do is a prediction from §8–§12.

### 13.1 What was built

| artifact | path | what it is |
|---|---|---|
| RPM baseline probe | `G:\git\Supervive Revival Project\tools\re\phase_readout.py` | Arm A0. Pure `ReadProcessMemory`. Reads both gates' every term + the delegate count that gates A5. |
| offline harness | `G:\git\Supervive Revival Project\tools\re\fake_phase_target.py` | Synthetic UE object graph in its own process. Validates the probe's **success** path with the game shut down. Never touches the game. |
| shim run mode | `G:\git\Supervive Revival Project\tools\sigbypass-mod\tutorial_launch.cpp` → `RM_PHASELADDER` (enum 24) | Arms A0′…A5. New and additive; `RM_GOTOPHASE` (enum 2) is untouched. |
| build variants | `G:\git\Supervive Revival Project\tools\sigbypass-mod\build.ps1` `-Variant phaseladder[-any\|-readonly\|-nopoke]` | one armed window = one variant |

**Built DLLs — `.text` sha256. ⚠ DIFF `.text`, NEVER SIZE; two of these differ by 512 bytes:**

| variant | file | `.text` sha256 | use |
|---|---|---|---|
| `phaseladder` | `tools\sigbypass-mod\build\tutorial_launch_phaseladder.dll` | **`de08812f6cc173fd`** | ★ **THE CANDIDATE** — full A0′…A5, arms on `ReceiveTickClient` (in-world) |
| `phaseladder-any` | `tools\sigbypass-mod\build\tutorial_launch_phaseladder_any.dll` | `18b5d73ef08c02c1` | fallback: swaps **every** BP UFunction. Use only if the 8 s arm verdict reads `NO GAME-THREAD HITS` |
| `phaseladder-readonly` | `tools\sigbypass-mod\build\tutorial_launch_phaseladder_readonly.dll` | `39240e4b4a71f559` | A0′ only — zero calls, zero writes. The de-escalated staging control |
| `phaseladder-nopoke` | `tools\sigbypass-mod\build\tutorial_launch_phaseladder_nopoke.dll` | `9e8a6132ba7bf5b7` | A0′…A3 — both `GoToPhase` calls, **no** poke, **no** broadcast |

**Regression control, measured not asserted:** `build.ps1 -Variant play` rebuilt from the modified
source reproduces `.text` **`9bc10a4552c596e1`** — byte-identical to the shipping `play` this repo
documents. No existing mode's behaviour moved.

⚠ **A stale sibling artifact was found and neutralised.** `tools\sigbypass-mod\tutorial_launch_play.dll`
(the ROOT path — the one `CLAUDE.md`'s tutorial recipe names) held `5151621d2154e454`, the **pre-S123**
`play-gcroot` build, while `build\` held the current `9bc10a4552c596e1`. It has been archived as
`tutorial_launch_play_preS123_gcroot_ARCHIVED.dll` and the root copy refreshed, so both paths now serve
the same current artifact.

### 13.2 SAFETY STATEMENT

Everything in this design is subordinate to one measured property: a **standing `.text` patch** kills
the process — **10/10 armed windows dead vs 3/36 with no module-image write, Fisher p = 0.00000008**
(S112), and at a matched 600 s hold the heap form was **0/16**.

**Module-image writes: expected NONE, and measured NONE.**
Import-table receipt, **with a positive control from the same source file** — `SafeWrite` needs
`FlushInstructionCache`; `BuildHook`/`NearAlloc` need `VirtualAlloc`/`VirtualFree`:

| dll | FlushInstructionCache | VirtualAlloc | VirtualFree |
|---|---|---|---|
| `tutorial_launch_phaseladder.dll` | absent | absent | absent |
| `tutorial_launch_phaseladder_any.dll` | absent | absent | absent |
| `tutorial_launch_phaseladder_readonly.dll` | absent | absent | absent |
| `tutorial_launch_phaseladder_nopoke.dll` | absent | absent | absent |
| `tutorial_launch_play.dll` (shipping, S112-measured safe) | absent | absent | absent |
| **`tutorial_launch_fo.dll` — POSITIVE CONTROL, it *does* call `InstallHook`** | **PRESENT** | **PRESENT** | **PRESENT** |

`VirtualProtect` is imported (so is shipping `play`). Its only callers are `PatchLoginVtables`
(**zero call sites anywhere in the file**) and `InstallCustomLogin` (reachable only from the
`RM_FORCEOPEN` tail, which this mode's `return` can never reach). `verify_dll.py` = **PASS** on all
four: no `__CxxFrameHandler3/4`, no `_CxxThrowException`, no `_Unwind_Resume`, no CRT. SEH only.

**The mode's entire write set:** ONE byte at `GameState+0xA44` (a heap UObject field), written at most
twice, readback-verified both times — plus the 2 heap `UFunction.Func` qwords `FsArm` swaps and
`FsDisarm` restores. `phaseladder-readonly` writes nothing at all.

**PI hooks: expected NONE, and there are NONE.** Game-thread callbacks come from RM_PLAY's heap
`UFunction.Func` (+0xE0) swap (`FsArm`/`FsHold`/`FsDisarm`). `FsArm` refuses to arm if another shim has
already patched the `ProcessInternal` prologue. With `-DKFUNCSWAP=0` the mode **prints a refusal and
returns 7** rather than falling back to `InstallHook()`. It never takes the
`Local\SuperviveMissionsPIHook` mutex, because it never needs it.

**A4 runaway bounds.** While `GameState+0xA44 == 3` the game's own Tick (`0x5613200`) calls
`GoToPhase(4)` every frame, and because the phase store is the stripped fold `0xF7EC20 = ret 0` it
never self-clears. The trailing poke back to 4 — which fails Tick's `cmp al,3` — is **the STOP, and it
is part of the arm, not an afterthought.** Four independent stops, three of which do not need the game
thread to keep dispatching:

1. wall clock `>= KPLHOLDMS` (2000 ms) — ladder step 5;
2. game-thread hits `>= KPLHOLDHITS` (600) — clock-independent;
3. `PhWatchdog`, a plain worker thread polling every 100 ms, started **before** `FsArm` so the stop
   exists before anything can poke. It forces the STOP at hold+grace (7000 ms); it **retries a failed
   STOP immediately, every 100 ms, with no grace period**; and it drains for up to `KPLWDGRACEMS` at
   mode exit rather than trying once;
4. the `__except` handler around every ladder step, plus one unconditional call at mode exit.

**Ownership is claimed BEFORE the store** — `g_phPoke3Ms`, then `InterlockedExchange(&g_phPoked3,1)`,
then `PhPokePhase` — so there is no window in which the byte stands at 3 with nobody owing a restore.
`PhPokePhase` reports `attempted` separately from `verified`: a guard refusal releases the claim, a
failed readback **keeps** it. If the STOP never verifies, the mode prints an ALERT **and returns 10**
(non-zero); the reviewed code returned 0 while printing that same alert.

**Knob defaults — all safe, inside a mode unreachable without `-DKRUNMODE=RM_PHASELADDER`:**
`KPLARMS=0x3F` (the pre-registered ladder — trim it with a *variant*, never by editing the default),
`KPLHOLDMS=2000`, `KPLHOLDHITS=600`, `KPLWDGRACEMS=5000`, `KPLSTEPMS=400`, `KPLMODEHOLDMS=90000`.
Nothing enters the default injection set (`grep -rn phaseladder configs/` = 0 hits). No diagnostic is
default-ON.

**Ordering trap, respected and instrumented.** `GoToPhase`'s gate is `cmp <arg>,[GS+0xA44]; je bail`,
so poking to N and then calling `GoToPhase(N)` is self-defeating and *silent*. The ladder runs
GoToPhase FIRST (A1, A2), reads back (A3), and only then pokes (A4). `PhGoToPhase` reads the live byte
before every call and prints `*** WARNING: arg == live phase … uninterpretable, not negative ***` when
the early-out would swallow it.

**Defects fixed this session, all re-verified:**

* **BLOCKER** — `phase_readout.py` read `NumElements` at `FUObjectArray+0x14`, which is the *high dword
  of the Objects pointer*. It swept ~466 of ~200,000 slots and would have reported `NO LIVE GameMode`
  on a perfectly staged world, burning the armed window. Now `FUObjectArray+0x24` (== `ObjObjects+0x14`,
  what every sibling probe uses). The harness carried a **third** layout and therefore could not detect
  it — the test had ingested the error it exists to catch. Both are fixed in the same edit and the pair
  now agrees exactly (probe `swept=18`, harness `objects=18`). The sanity band is now a hard FAIL
  outside `(0, 8_000_000)`, matching `item_watch.py`.
* **HIGH** — the A4 ownership window, above.
* **HIGH** — a faulted `GoToPhase` no longer lets the ladder continue; A1 or A2 faulting halts at step 7
  before any further call or poke.
* **HIGH** — the `summary:` line now carries its own disqualifiers (`status=PC-FAIL` /
  `AMBIGUOUS-GAMEMODE` / `GAMESTATE-UNTRUSTED`, plus `gm_pick=` and `swept=`), so the tool's own
  instruction — "parse the summary, never count the rows" — can no longer launder a stated STOP
  condition into `status=OK`.
* **MEDIUM** — the shim's GameMode lookup was `FindInstByClass`'s first-substring-match, the fifth
  member of this repo's class-lookup blind-spot family. It now **enumerates every live `*GameMode`**,
  prints each with its derivation chain and its `[+0x258]`, prefers `World->AuthorityGameMode` (§10's
  own prescribed derivation), cross-checks `World->GameState` against `[GM+0x258]`, and **ABORTS on
  ambiguity or disagreement rather than guessing**. `RM_GOTOPHASE` keeps the old resolver, unchanged.
* **MEDIUM** — the probe's World cross-check is now a real check `(f)` that reaches `checks` and the
  summary; an absent World prints as **ABSENT**, never as a silent pass.
* **MEDIUM** — the delegate verdict quotes its denominator when `Num > 16` instead of claiming "every
  entry validated"; a read that was never attempted prints **SKIPPED**, not `UNREADABLE`.
* **MEDIUM/LOW** — the watchdog's retry text is now true of the code; `PhResolve` moved to the worker
  thread **before** `FsArm`, so its full sweep is not a game-thread hitch and a failed resolve aborts
  before anything is armed; bounds checks on both param-buffer indices; `--gamemode` argument guards
  that still emit a `summary: status=BAD-ARGS` line; A5's `-1` (unreadable) reported separately from
  `0` (measured empty), with the sampling arm named; the A4 STOP value falls back to the observed
  pre-poke byte instead of a fabricated 4 if A3 shows a live phase writer; the probe's per-object FName
  decode moved inside the candidate branch (the sweep is the thing you re-run under time pressure).

### 13.3 The exact operator sequence

Steps 2, 3 and 4 need an **ELEVATED** PowerShell (step 3 opens the game process for
`PROCESS_VM_READ`). **Steam must already be running**, or login dies with `Auth Failure 14005`.

```powershell
# --- (1) Elevation not required. Flip the tutorial auto-park, rebuild ags. ------------------------
#     Edit server\internal\interactive\interactive.go  ->  const forceTutorialMatch = true
cd "G:\git\Supervive Revival Project"
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags

# --- (2) ELEVATED PowerShell. Steam already running. Returns after launching; game keeps running. -
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -NoHook

# --- (3) ELEVATED, SECOND terminal, once the client has parked (~13 s after launch). --------------
#     READ-ONLY baseline (arm A0). Safe to re-run any number of times. RUN IT AGAIN just before (4).
cd "G:\git\Supervive Revival Project"
python tools\re\phase_readout.py
#     If it reports more than one qualified GameMode, re-run with the address it printed:
#         python tools\re\phase_readout.py --gamemode 0x<ADDR>
#     Parse the `summary:` line. Proceed ONLY on  status=OK  pc=PASS  gm_pick=unique|override.

# --- (4) ELEVATED. Stages gft_ready_fix -> tutorial_launch_fo -> tutorial_launch_sp -> the probe, --
#     gating each step on measured evidence. ONE VARIANT PER ARMED WINDOW.
cd "G:\git\Supervive Revival Project"
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_phaseladder.dll -Label s124-ladder

#     de-escalated arms, each its own armed window:
#     .\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_phaseladder_readonly.dll -Label s124-a0
#     .\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_phaseladder_nopoke.dll   -Label s124-nopoke
#     .\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_phaseladder_any.dll      -Label s124-any

# --- (5) AFTERWARDS: set forceTutorialMatch back to false and rebuild ags, or every normal launch --
#     auto-parks into the tutorial loading screen and looks broken.
```

**Where the evidence lands.** The shim's own trace goes to `docs\tutorial-launch-marker.txt`, which
`fk24-stage.ps1` copies off after each stage to
`docs\fk24-stage-s124-ladder-4-tutorial_launch_phaseladder.txt`. `Marker()` opens `CREATE_ALWAYS`, so
every injection truncates the live file — **read the copy.** The receipts themselves are in
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`, **not** the marker: "the call returned
ok" is never a success criterion.

### 13.4 PRE-REGISTERED PREDICTIONS — written down BEFORE the flight

Baseline for every log-string claim below: across the **193 corpus logs**, `Setting Phase to 1
(BeginInit)` occurs **exactly once per file**, and `Setting Phase to 4 (SpawnSelect)` occurs in
**zero** files.

| arm | action | CONFIRMS if… | FALSIFIES if… |
|---|---|---|---|
| **A0** — `phase_readout.py` | read only, no calls | `summary:` shows `status=OK pc=PASS`, `phase=0(ServerStartup)` or `1(BeginInit)`, `gm7C0=4`, `gate34=BLOCKED` with the phase byte as the sole unmet term | `pc=FAIL` (wrong attach — nothing below is interpretable) · `gm7C0` ≠ 4 (§11's 189/193 claim does not hold for this staging) · `gate12=OPEN` while the ladder is frozen (the gate list is incomplete) |
| **A0′** — shim step 0 | read only, on the game thread | the four `[PH] A0'` lines agree with step (3)'s A0 readout | any disagreement ⇒ one of the two derivations is wrong. **Stop and reconcile before A1.** |
| **A1 — POSITIVE CONTROL** | `GoToPhase(1)` | a **SECOND** `Setting Phase to 1 (BeginInit)` in this run's `Loki.log`, plus a `Transitioning from phase …` line. A duplicate cannot have come from the game | **silence ⇒ THE SITTING IS VOID.** See the box below. |
| **A2 — TREATMENT** | `GoToPhase(4)` | `Setting Phase to 4 (SpawnSelect)` **and** `Transitioning from phase (ERoundPhase::EGP_ServerStartup) to phase (ERoundPhase::EGP_SpawnSelect).` — neither string exists in any of the 193 corpus logs ⇒ **the exec thunk is reachable and unguarded** | A1 logged but A2 did not ⇒ an argument-dependent guard exists that §8's disassembly missed. An observation *richer* than the two lines plus the timer arming (§12) also falsifies the `OnNewPhase` model |
| **A3** | re-read `GS+0xA44` | reads **0** ⇒ the phase store really is the stripped fold `ret 0`; converts **[I] → [M]** | reads non-0 ⇒ **a writer exists outside the decrypted 54.90 % of `.text`. MAJOR RESULT** — and the shim automatically switches A4's STOP to the observed pre-poke byte rather than fabricating a 4 |
| **A4** | poke `+0xA44 = 3`, hold ~2 s, poke `= 4` (**the STOP**) | repeated `Setting Phase to 4 (SpawnSelect)` during the hold, each paired with `Transitioning from phase (ERoundPhase::EGP_FinishInit) to …` — a **different** transition string from A2's. That difference is what proves the already-running native Tick actuated it and not us | no `Setting Phase to 4` during the hold while `gm7C0 == 4` ⇒ the 3→4 Tick gate has a term §11 does not list. The marker must show `a4Poked=1 a4Restored=1` either way |
| **A5** | `BP_AuthSetCurrentPhase(6)` — **only if A0′ measured `Num > 0`** | `Setting Phase to 7 (Combat)` in `Loki.log` with **no `GoToPhase` call of ours in the marker** ⇒ a subscriber acted on the broadcast | `+0xA44` changing ⇒ the impl is not `add rcx,0x590; jmp Broadcast` as §10.3 reads it |

> ### ⚠ A SILENT A1 MEANS THE SITTING IS VOID. NOTHING ELSE MAY BE INTERPRETED.
> `GoToPhase` logs its **argument**, before the old==new test, so a live and reachable thunk **cannot**
> be silent. If A1 produces no second `Setting Phase to 1 (BeginInit)`, the call never reached the game
> — bad resolve, a swap that took no game-thread hits, or the wrong GameMode — and therefore **A2's
> silence, A3's 0 and A4's absence of `Setting Phase to 4` are all uninterpretable, not negative.**
> Record none of them. Discard the window and re-fly.
>
> Read `FsHold`'s own 8 s verdict *first*: `ARMED AND LIVE` versus `NO GAME-THREAD HITS after 8000 ms
> … swapped=2`. The second reads exactly like a dead surface and is not one — it means
> `ReceiveTickClient` was never dispatched. Re-fly with `phaseladder-any`.

**If `Num == 0`: DROP A5.** The shim already does — it skips with a named reason and does not call.
A broadcast into an empty invocation list is a **hard no-op** at `0x134236C`
(`test edi,edi; jle <return>`), so silence there would be **uninterpretable, not negative**, and must
not be written up as evidence about `BP_AuthSetCurrentPhase`. The marker distinguishes two skips:
`Num` **measured 0** (a real precondition failure, a fact about the game) versus `Num` **unreadable,
−1** (a broken instrument, a fact about us). Only the first is a statement about the game.
The precondition is not permanent: §10.3 has the tutorial mode binding `OnRoundPhaseChanged` inside
`ReceiveBeginPlay` behind `ULokiBlueprintLibrary::ServerOnly`, so re-run `phase_readout.py` at the
moment you intend to call, not once at staging.

### 13.5 Known failure modes OF THE SITTING — budget for these; they are not defects

* **Only ~2 of 4 launches reach an armed window. Budget on ARMED WINDOWS, never on launches.**
* **FK-31, the staging hazard: ~27 % (22/82) of launches die BEFORE the probe is injected**, with only
  `gft`+`fo` resident. Untouched by anything here and untouched by FK-7's fix. It is the dominant
  tutorial-route failure and it costs the launch outright.
* **FK-32: a ~3/36 residual exiting `0x0000DEAD`**, leaving no artifact of any kind. Not ours (no
  `TerminateProcess`/`ExitProcess` in any shim source; `Stop-Process` exits `0xFFFFFFFF`, measured).
  Harvest the exit code; do not spend windows chasing it.
* `[SP] gm=0x0 pc=0x0 startSpot=0x0 heroClass=0x0` means the world is gone. **Do not inject the probe.**
* `RM_PHASELADDER` is a **continuation** mode: it attaches to an already-staged tutorial. A lone
  `-Hook <dll>` cannot work; it must go through `fk24-stage.ps1` after `gft → fo → sp`.
* `ReceiveTickClient` is **measured not dispatched at the menu** (S114), so `phaseladder` is a silent
  no-op there. The mode is meaningless at the menu anyway — `PhResolve` aborts by name with a full
  candidate enumeration — but this is exactly why the 8 s arm verdict must be read before anything else.
* **`phaseladder-any` will usually stop A4 by the HIT CAP rather than the clock** (swapping ~17k
  UFunctions raises the callback rate far above `ReceiveTickClient`'s ~17/s), shortening the hold below
  2 s. It is logged explicitly as `stopped by HIT CAP (the clock did not get there first)`. Raise
  `KPLHOLDHITS` if a full 2 s hold matters on that arm.
* The `phase_readout.py` sweep is one RPM per object over ~200k objects — expect tens of seconds.

### 13.6 What is NOT ready, stated plainly

* **Nothing here has been flown.** The probe's success path is validated only against a synthetic
  harness; its first real run is also a test of the probe.
* **`SetSharedMatchStartDetails` — the 1→2 gate's other half — is NOT wired.** Its flags include
  `FUNC_BlueprintAuthorityOnly`, and whether a direct `UFunction.Func` call bypasses that is [I] and
  untested. A0′ reads `MatchStartDetails` so the next session knows whether that gate is already
  satisfied before anyone builds the arm.
* **`BP_AuthSetCurrentPhase`'s parameter NAME is unmeasured.** Five candidates are tried and the real
  chain is dumped beside the answer; offset 0 is the fallback — correct for a single byte-sized param,
  but a fallback, not a measurement. The first run's `[PH] BP_AuthSetCurrentPhase param[0] …` line
  settles it permanently.
* **`GM+0x790 / +0x7B0 / +0x7C0` are read as raw offsets**, with no by-name cross-check available (they
  are almost certainly not reflected UPROPERTYs). They are read-only in this mode, so a wrong offset
  yields a wrong log line, not a wrong write. The `+0x7C0` stage *names* are [I] from log order; only
  the number 4 is load-bearing.
* **Read the `[PH] A0'` versus A0 agreement first, right after the arm verdict.** Two independent
  derivations disagreeing is more informative than either one alone.

---

## 14. FLOWN -- THE ROUND PHASE ADVANCED TO `EGP_Combat`, AND THE LADDER SELF-DROVE

**Date:** 2026-08-16 - one staged tutorial sitting, PID 191748 - **zero `.text` writes, zero PI hooks,
zero pokes** (arms A4/A5 never ran). Evidence: `docs/fk24-s124-ladder-SUCCESS-marker.txt`,
`docs/Loki-s124-phaseladder-SUCCESS.log`.

### 14.1 The result

The shim called `GoToPhase` **exactly twice** -- argument 1, then argument 4. From `Loki.log`:

```
09.45.01:740  Setting Phase to 1 (BeginInit)      <- the GAME's own startup call (the 193-corpus baseline)
09.51.44:496  Setting Phase to 1 (BeginInit)      <- A1 POSITIVE CONTROL (ours)
09.51.44:929  Setting Phase to 4 (SpawnSelect)    <- A2 TREATMENT (ours)
09.51.45:038  Setting Phase to 5 (SpawnReveal)    <- +109 ms   NOT US
09.51.45:137  Setting Phase to 6 (Lineup)         <- + 99 ms   NOT US
09.51.45:238  Setting Phase to 7 (Combat)         <- +101 ms   NOT US
09.51.45:238  Display: Took 414.264048 seconds to go from EGP_Pre to EGP_Combat
```

- **[M] A1 fired.** A **second** `Setting Phase to 1 (BeginInit)` in one file. Baseline is exactly one
  per file across 193 files, so a duplicate cannot come from the game. **The sitting is VALID**, and
  everything below is therefore interpretable.
- **[M] A2 fired.** `Setting Phase to 4 (SpawnSelect)` exists in **zero** of the 193 corpus logs.
  => **`ALokiRoundGameMode::GoToPhase` is reachable and unguarded by a direct `UFunction.Func` call
  from an injected DLL, with no module-image write.** S8's "REAL, no authority guard" is now live [M].
- **[M] THE LADDER SELF-DROVE.** We never called 5, 6 or 7. They arrived ~100 ms apart on the game's
  own timers, exactly as S10.1 predicted from the four tail-jmp callers (`0x560A104/174/1A2/AA72`,
  constants 9/2/3/6) reached through `[vtable+0xB08] = OnNewPhase`.
  => **the phase machine is not merely pokeable -- ONE call starts a self-driving cascade to Combat.**
- **[M] The game emitted its own completion receipt**, `Took 414.264048 seconds to go from EGP_Pre to
  EGP_Combat` -- a line this project has never produced.
- **[M] Real gameplay consequences followed.** At `09.52.34`, ~49 s after Combat, the client began
  **mass navmesh generation** across `LVL_Tutorial` cells (hundreds of `LogNavigationDirtyArea`
  entries). Reaching Combat made the world start preparing for play.
- **[M] A3 CONFIRMED, [I] -> [M]:** all six `Transitioning` lines read `from phase
  (ERoundPhase::EGP_ServerStartup)`, and a post-experiment RPM read gives **`GameState+0xA44 = 0
  (ServerStartup)`**. => **`GoToPhase`'s phase write really does land on the stripped `ret 0` fold
  `0xF7EC20`; the stored byte never moves.** S8.4's central inference is now a live measurement.
- **[M] The process survived.** Zero `handing control over to crashpad`; client-config polling,
  party-manager latency and telemetry all still running afterwards.

### 14.2 What did NOT happen, stated plainly

- **The drop phase did NOT fire.** The only drop-related lines in the whole session are three
  **startup** `LogActorPooling` registrations at `09.42.49` (`BP_DropPod_Tutorial_C`, `BP_DropPod_C`,
  `BP_DropPod_Child_C`) -- the "registered, never instantiated" state already on record. Reaching
  `EGP_Lineup(6)` was **not sufficient**. => **FK-22's headline question is still OPEN**, now for a
  sharper reason: the phase *notification* reached Lineup while `CurrentPhase` stayed 0, and the
  DropPlane component's handler is bound to the **GameState delegate**, which `GoToPhase` does not
  broadcast. That is arm **A5**'s job.
- **A4 and A5 never ran.** The ladder stopped after A2 -- it starved of game-thread callbacks once the
  round state changed (`ReceiveTickClient` dispatch stopped). **Nothing was poked, nothing broadcast.**
  => every A4/A5 prediction is **UNTESTED, not negative.**
- **The 1->2 gate never fired:** `GameMode+0x7B0 = 0` post-experiment (the gate writes 1), and
  `MatchStartDetails` is `Num=0`. Two of its three terms are unmet.

### 14.3 Measured corrections to S10-S11 -- a docs claim REFUTED live

1. **`GameState` is at `GameMode+0x418`, NOT `+0x258`.** S10.5/S11 assert *"GameState from
   `[GameMode+0x258]` (the offset `OnNewPhase` itself uses at `0x5608FB8`)"*. **MEASURED:** on the live
   `BP_LokiGameMode_Tutorial_C` (`0x1B3857EA4C0`), `[+0x258] = 0x1B405BE1000`, which is **not a
   UObject** -- its "vtable" `0x1B2C4323C00` is a **heap** pointer (a real UObject's is in-module; this
   GameMode's is `0x7FF7A4A54C48`) and the bytes are a repeating `{ptr, 0xFFFFFFFF, int}` array
   pattern. A scan of the GameMode's first `0x1000` bytes finds the real GameState
   (`0x1B4021B60A0 BP_LokiGameState_Tutorial_C`, vtable in-module) at **exactly one** offset: **`+0x418`**.
   The shim's `GcAlive` guard **caught this** and aborted twice rather than poking a stranger.
2. **`+0x7C0 = 4` CONFIRMED live** (the 3->4 gate's initializer term), which S11 had only inferred from
   189-193 log transitions. => **the 3->4 gate is one term short -- `CurrentPhase == 3` -- exactly as
   predicted.** The delegate at `GS+0x590` reads **`Num = 7` subscribers**, so **A5 is runnable** and is
   the highest-value unspent arm.

### 14.4 Two probe defects found LIVE -- both caught by refusal-to-guess

**(a) The substring trap, committed in BOTH probes independently.** The GameMode selector accepted any
class whose derivation chain *contains* `"GameMode"` -- which matches every `Comp_GameMode_*`
**ActorComponent** -- then ranked by *"`[+0x258]` points at a live UObject"*. On the live world that
**rejected the one true `LokiRoundGameMode` and accepted `Comp_GameMode_DeathCircle` and
`Comp_GameMode_RoundReset`.** The C++ shim **refused to guess** and aborted, having armed nothing and
written nothing; the python probe silently picked `EndOfGameModel` and reported `gm7C0 = 0`, which
reads exactly like "the initializer never finished" but is a reading off the wrong object.
**Fix: require the class that DECLARES the function -- `LokiRoundGameMode` -- selecting 1 of 18.**
=> **sixth member of the class-lookup blind-spot family**, and the first caught *by the instrument's
own refusal* rather than after publication. Had it guessed, it would have driven a DeathCircle
component as the game mode.

**(b) `build.ps1 -Variant <v>` silently builds the DEFAULT SET unless `-Name tutorial_launch` is also
given.** S13.3's command omitted `-Name`, so the first "rebuild" produced 11 unrelated DLLs and **not**
the probe -- while reporting `11 built, 0 failed`, which reads like success. Caught only by diffing the
`.text` hash. **Diff `.text` after every rebuild; a build that succeeds is not a build of what you asked for.**

### 14.5 The next arm

**A5 -- `BP_AuthSetCurrentPhase(6)` -- targets the drop phase**, is measured runnable (`Num = 7`), and
was never spent. Pair it with a poke of `GS+0xA44` (the value the DropPlane handler reads back);
**poke first, then broadcast**, because `BP_AuthSetCurrentPhase` has no equality gate while
`GoToPhase` does. The ladder must survive to the arm: it starved after A2 when `ReceiveTickClient`
dispatch changed. Re-fly with `phaseladder-any` (swaps every BP UFunction), or re-order so A5 runs
before the round state moves.

---

## 15. A5 FLOWN -- the broadcast fired into a 7-subscriber list and did nothing, and the reason is MEASURED

**Date:** 2026-08-16, second flight, same live process (PID 191748, no relaunch) - build
`phaseladder-a5` (`.text ef0615e76343bce0`, `KPLARMS=0x21` = A0'+A5 only, `KFSNAME=""`).
Import table: `FlushInstructionCache`/`VirtualAlloc`/`VirtualFree` **absent** => no module-image write.
Marker: `docs/fk24-s124-A5-marker.txt`.

### 15.1 The arm ran, cleanly and single-variable

A1/A2 were deliberately **disabled** (already proven in S14; re-running them only burns the window and
contaminates receipts) and A3/A4 dropped, so the only question asked was: **does a BROADCAST alone
drive the DropPlane handler?** [M] `Num = 7` at A0' **and re-read as 7 immediately before the call**,
so the pre-registered "hard no-op" gate did not apply. `BP_AuthSetCurrentPhase(6=Lineup)` returned
without fault; `+0xA44` stayed `0` (it never stores, as designed); **508 game-thread hits**, so the
`KFSNAME=""` change fixed the starvation that stopped the first flight after A2.

### 15.2 The result: NO EFFECT [M]

Counts before -> after, on the append-only session log:

| token | before | after |
|---|---|---|
| `Setting Phase to 7 (Combat)` | 1 | **1** |
| `Setting Phase to 6 (Lineup)` | 1 | **1** |
| `Setting Phase to` (all) | 6 | **6** |
| `DropPod` | 3 | **3** |
| `DropPlane` | 2 | **2** |

(log grew 762,705 -> 764,832 B, entirely client-config polls and telemetry.)
=> **[M] `GoToPhase(7)` was NOT called by any subscriber**, which is the one clean negative available:
the predicted 6-arm receipt did not fire.
WARN Note the receipt hazard this run had to work around: `Setting Phase to 7 (Combat)` **already
occurred once** in this session from S14's self-driving cascade, so *presence* is not discriminating
here - only the COUNT is. Baseline counts were recorded BEFORE injecting for exactly this reason.

### 15.3 WHY -- and this is the finding, not the null

A null from a broadcast is uninterpretable unless you know **who was listening**. So the invocation
list was walked directly (read-only RPM; `FMulticastScriptDelegate` at `GS+0x590`,
`Data=0x1B408640880`, `Num=7`, `FScriptDelegate` stride 16, object index resolved through
`GUObjectArray` chunks at `0x1B22A7C99A0`, `NumElements=197204`):

```
[0] objIdx 119421 -> 0x1B361978F80   = Comp_GameMode_ShopKeepers
[1] objIdx 119423 -> 0x1B3857EA4C0   = BP_LokiGameMode_Tutorial_C   (the GameMode itself)
[2] objIdx 119359 -> 0x1B2DF65A880
[3] objIdx 119328 -> 0x1B37CDCD660
[4] objIdx 119321 -> 0x1B408462A00
[5] objIdx 119381 -> 0x1B37C842D00
[6] objIdx 196462 -> 0x1B37A2AAAC0
```

**[M] `Comp_GameMode_DropPlane_Tutorial` is `0x1B3771413C0` -- and it is NOT in that list.**
(Both identifications are cross-referenced against the shim's OWN independent `gm-cand` enumeration
from the same process, which named `0x1B361978F80` and `0x1B3857EA4C0` and `0x1B3771413C0`.)

=> **A5's null is NOT a statement about the DropPlane handler's behaviour. The handler was never
subscribed, so it could not have been reached by any broadcast.** Recording this as "phase 6 does not
drive the drop phase" would have been precisely the instrument-artifact error this project catalogues.

=> ★ **This gives S10.3's [I] its first live support**: the tutorial mode binds `OnRoundPhaseChanged`
inside `ReceiveBeginPlay` behind `ULokiBlueprintLibrary::ServerOnly`, and on this client route **that
bind did not happen**. The gate is [I] -> now **[I, corroborated]**: the *consequence* predicted by the
ServerOnly hypothesis (no subscription) is measured.

### 15.4 Where FK-22 stands after two flights

- **[M] The phase machine is fully drivable** and self-drives to `EGP_Combat` from one call (S14).
- **[M] The drop phase is NOT reachable through the phase channel**, for a mechanical reason that is
  now named: the DropPlane component **does not subscribe** to the delegate the phase channel
  broadcasts on.
- => **The blocker moved.** It is no longer "the phase is frozen" (solved) nor "the markers are
  missing" (refuted in S0-S3). It is **the subscription**: `Comp_GameMode_DropPlane_Tutorial::
  ReceiveBeginPlay` never binds its handler on the client route.

### 15.5 The next levers, ranked

1. ★ **Make the bind happen.** `ReceiveBeginPlay`'s `ServerOnly` gate is a Blueprint branch on
   `OutputExecs`. Grade `ULokiBlueprintLibrary::ServerOnly`'s impl (REAL vs fold) and read what it
   tests. If it reads a role/NetMode byte on a client-resident object, that byte is a DATA poke -- the
   safest write class this project has -- and flipping it before `ReceiveBeginPlay` runs would let the
   component subscribe itself, with no `.text` write.
2. **Call the handler DIRECTLY.** `Comp_GameMode_DropPlane_Tutorial`'s `OnRoundPhaseChanged` /
   `On Round Phase Changed` are reflected UFunctions on a live object (`0x1B3771413C0`) -- callable by
   the S55 primitive with a byte argument, bypassing the delegate entirely. This tests the HANDLER
   without needing the subscription, and cleanly separates "not subscribed" from "subscribed but inert".
   ⚠ Do BOTH readings in one flight: call it, then check whether `SpawnPlane` ran.
3. **`SpawnPlane` directly.** S2.1 measured it branchless with 3 unguarded `Array_Get(...,0)` and the
   markers PRESENT in `LVL_Tutorial` (S0/S7) -- so the S93 fault should not reproduce. That is the most
   direct test of FK-22's original question and it no longer depends on the phase at all.

---

## 17. FLOWN — `SpawnPlane` FAULTED **and** spawned a plane. The cause is measured: the markers are NOT STREAMED IN.

**Date:** 2026-08-17, PID 138796, staged `LVL_Tutorial`, build `tutorial_launch_dropplane_b1only.dll`
(`.text 5b4467b0105dec1a`, `KDPARMS=0x33`, `KFRAMEINIT=1`). Zero `.text` writes, zero PI hooks,
**zero crashpad handoffs** — the process survived the fault. Evidence:
`docs/fk24-s125-b1only-RESULT.txt`, `docs/Loki-s125-b1only.log`.

### 17.1 The control passed first, which is what makes the rest attributable

```
B0c  GetAutoDropLocation()  -> returned without fault   fault=-  res0=0x0
     VERDICT: control PASSED (B0c status 0), so B1's status 1 is attributable to SpawnPlane
```
`GetAutoDropLocation` is **0 push / 0 pop**, so it cannot be affected by the FFrame flow-stack window,
and it is **the exact call S93 recorded as "ran clean"**. Its success establishes that the BP-call
primitive dispatches correctly in this build — without it, B1's fault would be uninterpretable.

### 17.2 The headline: BOTH outcomes, simultaneously

```
B1  SpawnPlane()  ->  *** FAULTED (SEH-captured) ***
                      code=0xC0000005 READ addr=0x0  rip rva=0x13495DD   res0=0x0
census BEFORE  DropPlane=3 DropPod=2 DropShip=0  objects=5
census AFTER   DropPlane=4 DropPod=2 DropShip=1  objects=6   new=1
NEW: 0x2AD6F1F20E0 'BP_DropPlane_Straight_Tutorial_C'
     chain = BP_DropPlane_Straight_Tutorial_C <- BP_DropPlane_Base_C <- LokiDropShip <- LokiDropPlane <- Actor
```

- **[M] It faulted** — a null dereference (`READ addr=0x0`) at RVA `0x13495DD`, inside the script-VM
  region (`ProcessInternal` is `0x13454A0`). Exactly the shape of `Array_Get(empty,0)` -> null actor ->
  `K2_GetActorLocation`. ★ This fault report is ATTRIBUTABLE — code and faulting address — where S93
  had only a bare boolean. That is what `KFAULTINFO` was built for.
- **[M] AND A REAL DROP PLANE EXISTS THAT DID NOT BEFORE.** The deferred spawn ran. `B1 return
  value = 0x0` and `SetDropPlane` never executed, so the component never took ownership ⇒ the actor is
  **half-constructed**. The spawn machinery WORKS; what failed is the position computation feeding it.

### 17.3 ★★★★★ THE CAUSE, MEASURED: present-in-package ≠ streamed-in

```
marker scan: AActor.Tags @0x1F0 (resolved by name off a live actor class)
MARKER 'TrainingStart' FOUND on 0x2ADA4928040 'BP_LokiPlayerStart_C_UAID_709CD165B93A7B4E02'
summary: TrainingStart=1  PlaneStartPoint=0  PlaneEndPoint=0
         (actors scanned=2881, of which tagged=676)
```
**[M] Two of the three markers are not resident.** All three exist in `LVL_Tutorial`'s shipped packages
(S124, offline, three separate World Partition cells) — they are simply **not streamed in at call
time**. The first lookup (`TrainingStart`) succeeds; the second hits an empty array and derefs null.
★ The `676 tagged` figure is the built-in control: the scan CAN see tags, so the two zeros are a real
absence in the live world, not a broken instrument.

### 17.4 What this does to the FK-22 story — a correction to §0 and §14

⚠⚠ **RETRACTED, my own wording:** §0 said S93's stated reason was *"refuted on the very map it was
measured on"*. **That was too strong.** Sharper, and now measured in both directions:

| claim | verdict |
|---|---|
| S93's OBSERVATION — "`SpawnPlane` faults" | **CORRECT [M].** It reproduces on a repaired frame, with the control passing in the same run. |
| S93's stated REASON — "markers that don't exist outside the real deploy" | **HALF RIGHT.** They DO exist in the map (S124 [M]) — but they are **NOT STREAMED IN**, which produces the identical failure. The mechanism S93 named (unguarded empty-array deref) is exactly right. |
| The FFrame-confound hypothesis (§14.3, [I, strong]) | **REFUTED as the explanation [M].** The fault reproduces through a repaired frame; the 0-push/0-pop control passed. The confound was a REAL DEFECT in the primitive, but it was not what produced S93's result. |

⇒ ★ **The successor hypothesis flagged in §4 — "Present-in-map ≠ streamed-in at call time. Only the
first is established" — was the right one, and it is now the measured answer.** That line was written
before any of this was known; it is the single most load-bearing sentence in the document.

⚠ **Do not now over-correct into "S93 was right all along."** Its *generalisation* remains refuted:
the belief said the DROP PHASE is falsified as reachable, and what is measured is that ONE variant's
position-computation faults on a streaming condition, while the spawn machinery itself demonstrably
works. Three of FK-22's structural findings are untouched: the three sibling overrides, the general
variant's zero marker queries, and `OnDeathCircleSet`'s procedural path.

### 17.5 Where the blocker is now

Not the phase (solved, §14). Not the subscription alone (§15) — and note `ServerOnly` (§16) is real
code that unconditionally writes 0, so that bind is dead by construction. It is now **two positions**:
`SpawnPlane` needs `PlaneStartPoint`/`PlaneEndPoint` resident, and the pod route needs none of it.

★ **The most direct remaining route does not involve markers at all.** We now hold a live
`LokiDropShip`-derived actor, and `ALokiDropShip::SpawnDropPodForTeam(TeamIndex, SpawnLocation,
LandingLocation)` takes its positions **as parameters** with **no marker query** and exactly two bail
points, both of which §3 grades satisfiable. That is Route C in §18.

⚠ **State left behind:** a half-constructed `BP_DropPlane_Straight_Tutorial_C` is in that world, owned
by nobody. The process tolerated it (0 crashpad handoffs), but any later census in that same world must
account for it rather than assuming a clean baseline.

---

## 18. Route C and Route D — the two paths to a drop pod

*Written S126, 2026-08-17, by the finalizer, after adversarial review of both routes. Everything below
is **offline work plus a clean build**. **NOTHING IN THIS SECTION HAS BEEN FLOWN.** The predictions in
§18.4 are pre-registered; that is the whole point of writing them down before the launch.*

### 18.0 What the review changed, before anything else

Both routes came back **FIX-FIRST**, and the fixes were applied, rebuilt and re-verified — not merely
reported. One BLOCKER, two HIGH and six MEDIUM/LOW defects were repaired in
`tools/sigbypass-mod/tutorial_launch.cpp` and `tools/sigbypass-mod/build.ps1`.

| sev | defect | why it mattered |
|---|---|---|
| **BLOCKER** | `PdControl` (C0c) read `K2_GetActorLocation`'s `FVector` return **only from the params block**. `CallNative` passes `g_rbuf` as the thunk's third argument (`RESULT_DECL`); a native exec thunk writes `*(FVector*)Z_Param__Result`, never the params block. | The control would have read `(0,0,0)`, making `err` the ship's whole distance from the origin ⇒ **`SITTING VOID for Route C` on every run**, on a call that worked. The inverse is worse: a ship near the origin reads `MATCH` for a return never read. Fixed: read **both** sources, prefer the one the dispatch path actually writes, and **print which was used**. |
| **HIGH** | Same wrong-buffer read for the headline: `g_pdRetRaw` came only from the params slot, while the attribution branch keyed on it. | On a **successful** spawn the log would have asserted *"the return slot is 0 → the pooled spawn returned null"* — a fabricated negative narrative contradicting the census. Fixed: fold `g_rbuf[0]`, print the source, and decode the return as a live UObject + class name. |
| **HIGH** | `PdProbeLeader()` — a real `GetTeamDropLeader` UFunction call — ran **ungated**, so `droppod-readonly` made a call while `build.ps1` **and the shim's own marker line** both claimed *"ZERO UFunction calls"*. | A control that does the thing it is controlling for is not a control, and a log asserting a property the code does not have is this project's recorded failure mode. Fixed: new `KPDARMS` **bit6**; default `0x3F → 0x7F`; both read-only assertions now test `0x6A`, not `0x2A`. |
| MEDIUM | `DmRestore` stamped `v.oldId` into **both** victims unconditionally, but `DmApplyWrites` has five `continue` paths and only an aggregate `g_dmWritten = (okn>0)`. | If victim[0] wrote and victim[1] was skipped, restore wrote our stale id over a slot **the game owns** — the one write in Route D that is neither reversible nor attributable, on the path whose entire purpose is to leave the world as found. Fixed: per-victim `wrote` flag, **plus** a check that the slot still holds *our* value before putting the old one back. |
| MEDIUM | `DmGat` wrote three FProperty offsets into the 128-byte `g_pbuf` with no bounds check, while `DpCallBP` in the same file refuses out-of-range offsets on the stated grounds that *"a clamped write is still a wrong write"*. | A wrong offset would corrupt `g_rbuf` and the adjacent globals, and the resulting fault would be attributed to `GetAllActorsWithTag`. Fixed: refuse. |
| MEDIUM | `KPDSHIPCLASS` assigned `forced=obj` inside the enumeration loop, then claimed *"matched exactly one candidate class"* without checking. | S125's leftover plane and a fresh pre-spawn are the **same class** — exactly the shape that makes last-writer-wins fire, on the path added to disambiguate. Fixed: count matches; `>1` **REFUSES**; `0` says so and falls through to the normal rules. |
| MEDIUM | C3's pre-spawn calls `SpawnPlane` through the BP path, and the droppod variants did **not** set `KOUTPARMRET=1` — deliberately reproducing S125's `0xC0000005` at `rva 0x13495DD` and then running C0c and C1 on that same game thread. | Fixed: `-DKOUTPARMRET=1` on **all four** droppod variants. For this mode's three native callees the extra `FOutParmRec` is inert (an exec thunk reads its return through `RESULT_DECL` and never walks `OutParms`), so it is a fix for C3 and a no-op for C0c/C1/C2b. |
| MEDIUM | `droppod-readonly` (`KPDPRESPAWN=0`) returned **before** `PdFinalReport` when no `LokiDropShip` existed. | The arm whose entire job is the census's null-delta baseline could not produce one on a **freshly staged world** — the exact state it is meant to be flown in. Fixed: the AFTER census needs no ship, so C4 runs anyway and Route C is reported NOT-APPLICABLE. |
| LOW | Route D's gate was documented as a `0 → 1` **transition** and implemented as a **level** test (`post >= 1`). | If the World Partition cells carrying the real markers streamed in during the sitting, the gate would PASS and the mode would attribute **their** residency to our write. Fixed: GATE-1 and GATE-2 both require a **rise**, with an explicit warning line if `pre` was already non-zero, and an announced level-test fallback when `pre` was not measurable. |
| LOW | A comment claimed `PhChainHas` was an *"EXACT declaring base, not the substring"* test. It is `strstr`. | The `obj_by_class.py` substring blind spot restated as its opposite, in a comment that would defend a wrong pick. Fixed: the comment now says what the code does and names the full enumeration + refusal as what actually carries the pick. |

**Two review findings I deliberately did NOT change.** (a) The 16-slot candidate array still caps ship
enumeration — it now prints `⚠ MORE CANDIDATES THAN THE 16-SLOT ARRAY … LOWER BOUND`, and it still
refuses on ambiguity, so the cap is a reporting limit and can never produce a wrong pick. (b) Route D's
`GetAllActorsWithTag` leaks one small `OutActors` allocation per call (≤6 per sitting); freeing it means
calling an allocator we have not graded, which is a worse trade than the leak.

### 18.1 What was built

Source (both files are **uncommitted working-tree changes** — see §18.7):

- `tools/sigbypass-mod/tutorial_launch.cpp` — `RM_DROPPOD` (enum **26**, Route C) and `RM_DROPMARKERS`
  (enum **27**, Route D), plus the shared `KOUTPARMRET` `#if` in `BuildOutParms`.
- `tools/sigbypass-mod/build.ps1` — 11 new variants. `-Variant` without `-Name` still refuses.

`.text` sha256[:16], computed from the PE section table after the final rebuild. **58 built, 0 failed.
All 17 below are DISTINCT — no A/B can be run against a copy of itself.**

| variant | `.text` sha256 | `.text` B | file B | role |
|---|---|---:|---:|---|
| `play` | `9bc10a4552c596e1` | 163,328 | 238,080 | **REGRESSION GATE — unchanged** |
| `dropplane` | `a0f6f2e54b5ac01e` | 121,344 | 193,024 | unchanged |
| `dropplane_handler` | `f88918f0935d3f44` | 119,808 | 189,952 | unchanged — **B3a/B3b, still never flown** |
| `dropplane_b1only` | `5b4467b0105dec1a` | 120,832 | 191,488 | the S125 probe |
| `phaseladder` | `8d1821f8c0ddbd63` | 115,712 | 184,320 | unchanged |
| `cheatmgr` | `7f89f671592824ac` | 106,496 | 167,424 | unchanged |
| **`droppod`** | `76c86fe5c8843c9a` | 137,216 | 215,040 | **Route C candidate** (`KPDARMS=0x7F`) |
| `droppod-readonly` | `93495bb576dff9f8` | 119,296 | 187,392 | Route C null-delta control (`0x11`, zero calls) |
| `droppod-noprespawn` | `32fa55a033796213` | 128,512 | 200,704 | Route C, never pre-spawn (`0x77`) |
| `droppod-newest` | `091a7e657ef43cc9` | 137,216 | 215,040 | Route C, highest `InternalIndex` on ambiguity |
| **`dropmarkers`** | `d3c07c32f7a699eb` | 139,264 | 216,576 | **Route D headline** |
| `dropmarkers-readonly` | `74857749ef264d1e` | 124,416 | 195,072 | Route D staging + FName agreement, zero writes |
| `dropmarkers-gateonly` | `778990b2e3379ade` | 135,168 | 209,408 | Route D mechanism alone, no `SpawnPlane` |
| `dropmarkers-outparm` | `b80c7455acd8df51` | 130,048 | 203,264 | `KOUTPARMRET` alone — ⚠ **`KDMFORCE=1`, gate BYPASSED** |
| `dropmarkers-s125repro` | `3c00d10be6369382` | 139,264 | 216,576 | controlled reproduction (`KOUTPARMRET=0`) |
| `dropmarkers-norestore` | `7ac4bf24298c53d9` | 138,240 | 215,040 | leaves the tags in the world — contaminating |
| `dropmarkers-nogat` | `25ca6075bf015e84` | 135,168 | 210,432 | GATE-2 disabled |

⚠ **Route D's hashes moved from the values its designer reported** (`9669759b723a40b0` →
`d3c07c32f7a699eb`, and so on), and **Route C's moved twice**, because of the fixes above. Use the table
in this section; the design write-ups' hashes are stale. **Diff `.text`, never size** —
`droppod` and `droppod-newest` share a `.text` SIZE of 137,216 and differ only by hash.

### 18.2 Safety statement — checked mechanically, not asserted

- **No module-image write.** Both modes arm exclusively on the heap `UFunction.Func` (+0xE0) swap
  (`FsArm`/`FsHold`/`FsDisarm`). With `KFUNCSWAP=0` each **REFUSES to run** and prints the S112
  measurement (standing `.text` **10/10** armed windows died vs **3/36**, Fisher p = 0.00000008) rather
  than falling back to `InstallHook()`.
  **Import-table evidence, parsed from the PE import descriptors of the final artifacts:**
  `VirtualAlloc`, `VirtualFree` and `FlushInstructionCache` are **ABSENT from all 11 new DLLs and from
  `play`**. **Positive control: `tutorial_launch_fo.dll` has all three PRESENT**, because it calls
  `InstallHook` — so the check discriminates rather than always passing. `VirtualProtect` is imported by
  every DLL including the deployed `play`: baseline, not a regression.
  ⚠ The no-`.text`-write property rests on **source reading plus these three absences**, not on a
  complete import audit: all 11 import 82 KERNEL32 functions including `HeapAlloc`, `RaiseException`,
  `RtlUnwindEx` and `TerminateProcess`, identical to the already-flown `dropplane_b1only`. Do not
  re-derive FK-32 from an import scan.
- **No hardcoded ASLR addresses.** `0x2AD6F1F20E0`, `0x2ACBA707D80`, `0x1B3771413C0`, `0x1B3857EA4C0`
  and `0x1B4021B60A0` appear **only inside comments that say they are dead** (3 lines total). Zero code
  uses. Objects resolve through `GUObjectArray` + class chain; properties (`TeamDropPodClass`,
  `RootComponent`, `RelativeLocation`, `Tags`, and all three `GetAllActorsWithTag` params) by **name**;
  functions by exact `UFunction` name over the class+super chain; parameter offsets and element sizes
  from the live `FProperty` chain. Where a name lookup fails the mode prints **INSTRUMENT UNAVAILABLE**
  and refuses — there is no fallback constant anywhere in either mode.
- **No C++ exceptions.** SEH only. `python verify_dll.py` → **VERDICT: PASS on all 11** (no
  `__CxxFrameHandler3/4`, no `_CxxThrowException`, no `_Unwind_Resume`, no CRT import).
- **Runaway bounds.** Every loop is iteration-bounded: FName pool sweep `blocks<8192`, `off<0x20000`,
  entries `<4,000,000`, advance `>=4` per entry; script-blob harvest `snum<=0x40000`; victim enumeration
  `nc<256`; ship enumeration `nc<16` with an over-cap warning; `GetAllActorsWithTag` refuses
  `Num<0 || Num>65536`; every parameter write is bounds-checked against its buffer and **refuses rather
  than clamping**.
- **Knob defaults, all safe.** `KOUTPARMRET`=0 (a `#if`, not an `if`), `KDMRESTORE`=1, `KDMFORCE`=0,
  `KDMGAT`=1, `KPDPRESPAWN`=1 (Route C only), `KPDSHIPPICK`=0, `KPDFORCE`=0, `KPDARMS`=0x7F.
- **Proof `play` is byte-unchanged: `.text` sha256[:16] = `9bc10a4552c596e1`, the CLAUDE.md pin,
  reproduced after every edit round.** `dropplane` = `a0f6f2e54b5ac01e` and `dropplane_handler` =
  `f88918f0935d3f44` likewise. Since `kRunMode` is a compile-time `static const int`, an un-eliminated
  new code path — or its `.rdata` literals, which move RIP-relative displacements — would necessarily
  change `play`'s `.text`. It did not ⇒ **`RM_GOTOPHASE`(2), `RM_PHASELADDER`(24) and `RM_DROPPLANE`(25)
  are behaviourally untouched.**

### 18.3 Which route to fly FIRST — ranked, not hedged

**1. Route C (`droppod`). Fly it first.** It is the only route that can produce the thing the goal names
— a **drop pod**. It needs no level markers, no round phase, no subscription and no delegate: §3 graded
`SpawnDropPodForTeam` with exactly **two** bail points and **zero** marker queries, and both bail points
are read out before and after the call. If a `LokiDropShip` is resident it never touches `SpawnPlane` at
all, so it does not inherit the untested `KOUTPARMRET` hypothesis. And it carries the strongest control
built here: C0c does not merely "not fault" — it **cross-checks a struct return against a pure-RPM read
of the same actor**.

**2. Route D (`dropmarkers`).** Second, and it is not a competitor: it fixes a **correctness** defect on
a different actor. Its ceiling is a plane at real coordinates. **A plane is not a pod**, and the
plane→player handoff (`ALokiDropPlane::AddPlayerToPlane`) is one of FK-1's four empty impls, so Route D
cannot reach the goal on its own. Its real value is (a) `dropmarkers-outparm` settles whether S125's
fault was our own `BuildOutParms` — the single most load-bearing untested belief in this section — and
(b) `dropmarkers-gateonly` proves the tag-residency mechanism while leaving the world exactly as found.

**3. `dropplane-handler` (B3a/B3b).** Free — already built, `f88918f0935d3f44`, never flown. It is the
arm that separates *"not subscribed"* from *"subscribed but inert"* for §15. Fly it whenever a staged
world is going spare.

⚠ **Route C's FALLBACK path does inherit Route D's hypothesis.** If no ship is resident, C3 pre-spawns
one via `SpawnPlane`. That is now `KOUTPARMRET=1` so it should not fault — but *should not* is a
prediction, not a measurement. For Route C with **zero** untested dependencies, fly `droppod-noprespawn`
into a world that still holds S125's plane.

### 18.4 Pre-registered predictions, per arm

Read these as written. A result that is not on this list is a **new** finding and must be recorded as
one, not folded into whichever row it resembles.

**In every arm: "returned without fault" IS NOT A RESULT. Only the census delta is.** Call status is a
tristate: `-1` NOT CALLED, `0` called and no fault, `1` called and FAULTED. `-1` is never a clean run.

#### Arm 1 — `droppod-readonly` (Route C null-delta control)

- **Positive control that proves the arm ran:** `[PD] C0-BEFORE CENSUS summary:` **and** the C4 delta
  table both present, together with `[PD] KPDARMS selects NO calls -- this is the READ-ONLY ARM`.
- **Predicts:** every delta row **+0**; `ran: C0c=0 … C1=0`; no `[FLT]` line anywhere.
- **Confirms:** the census instrument is quiet, so any later variant's delta is real.
- **Falsifies / VOID:** a **non-zero DropPod delta** ⇒ the instrument is noisy and it **voids every
  other variant's delta this sitting**. Also VOID: no delta table at all (the ladder starved — read
  `FsHold`'s own 8 s verdict line before anything else, and re-fly with `KFSNAME=""`).

#### Arm 2 — `droppod` (**THE HEADLINE**)

- **Positive control:** `[PD] C0c AGREEMENT: |delta| = … -> MATCH`, i.e. `K2_GetActorLocation`'s return
  agrees with a pure-RPM read of the same ship's `RootComponent->RelativeLocation` to under 1.0 uu. The
  new `[PD] C0c return sources:` line must name a source that is not `none`.
- **Predicts:** ship enumeration finds **exactly one** live `LokiDropShip` candidate; C0c **MATCH**;
  `bail-point 1 pre-call` reads `TeamDropPodClass = <non-null> (BP_DropPod_C)`; `GetTeamDropLeader -> 0x0
  (NULL)`, **which is the expected reading**, not a failure; C1 dispatches **NATIVE**; **`DropPod` delta
  `+1`** with a `*** NEW ***` line naming a `BP_DropPod*_C`; `retUSED` decodes as a **live UObject**.
- **Confirms Route C:** DropPod delta ≥ +1. That is the result; the return value is corroboration.
- **Falsifies Route C:** delta **+0** *with* C0c MATCH *and* a non-null `TeamDropPodClass` *and* no
  fault ⇒ the pooled spawn refused, and the remaining graded bail is the only survivor. Record it as
  that, not as "the call did nothing".
- **VOID (do not interpret C1 at all):** C0c prints `MISMATCH`, `INCONCLUSIVE` or `NOT CALLED`; or the
  ship enumeration printed `AMBIGUOUS … REFUSING`; or the ladder did not reach step 5 (exit 9).
- ⚠ **Known instrument risk:** the 1.0 uu agreement threshold assumes the ship's root is not attached to
  a parent. If it is, `RelativeLocation` is not world location and C0c reads MISMATCH **for a benign
  reason**. That is the *control* being wrong, not the call — re-derive with a world transform, and
  conclude nothing about C1 from it.

#### Arm 3 — `dropmarkers-readonly` (Route D staging gate)

- **Positive control:** the negative control `ZZZ_NOT_A_REAL_TAG` must be **NOT FOUND by both**
  instruments (if it resolves, the mode aborts before arming and writes nothing); and
  `GATE-2 pre TrainingStart` must read **> 0**.
- **Predicts:** both markers print **AGREE** between instrument (A), a scan of `SpawnPlane`'s own
  `Script` blob, and instrument (B), the `FNamePool` sweep; `GATE-2 pre PlaneStartPoint = 0` and
  `PlaneEndPoint = 0`; zero writes; no `SpawnPlane`.
- **Confirms:** the FName ids are real and the world genuinely lacks the markers.
- **Falsifies / STOP:** anything other than AGREE for both. **Do not fly arms 4–7** — every one of them
  would then write a guessed FName, which finds nothing and reads exactly like the bug being fixed.
- ⚠ If `GATE-2 pre` is already non-zero for either marker, the new warning line fires: the cells
  streamed in on their own and Route D's premise has changed this sitting.

#### Arm 4 — `dropmarkers-outparm` (⚠ **KDMFORCE=1 — the gate is BYPASSED by design**)

- **Positive control:** `D3 GetAutoDropLocation` must not fault. ⚠ **It cannot detect a `KOUTPARMRET`
  regression** — it has an OutParm but **no ReturnValue**, so `BuildOutParms` emits a byte-identical
  chain in both arms. The control is invariant under the very variable it sits beside. What
  discriminates is the **pair** arm 4 vs arm 7.
- **Predicts:** **no fault**, a non-null `BP_DropPlane_Straight_Tutorial_C`, and a plane location of
  **(0,0,0)**.
- **Confirms:** S125's fault was **our own `BuildOutParms`**, not the missing markers ⇒ §17's stated
  cause is half wrong in the same way S93's was, and the missing markers cost coordinates, not a crash.
- **Falsifies:** a fault at `rva 0x13495DD, addr=0x0` again ⇒ `KOUTPARMRET` is not the mechanism. A
  fault at a **different** rva is informative and is a new finding, not a repeat.

#### Arm 5 — `dropmarkers-gateonly` (the mechanism, world left as found)

- **Positive control:** `GATE-2 control TrainingStart` **unchanged** across the write.
- **Predicts:** GATE-1 and GATE-2 both show `PlaneStartPoint 0 -> 1` and `PlaneEndPoint 0 -> 1`;
  `RESIDENCY GATE: PASS`; restore VERIFIED for both victims; **no `SpawnPlane`**; every census delta +0.
- **Confirms:** an in-place 4-byte FName overwrite makes a tag visible to the exact predicate
  `SpawnPlane` uses.
- **Falsifies:** GATE-1 passes and GATE-2 does not ⇒ the victim actors are not in the world's actor
  list; the readback is the weaker instrument and it is telling you so.
- **VOID:** the TrainingStart control moves ⇒ GATE-2 is unstable, treat it as UNAVAILABLE.

#### Arms 6 and 7 — `dropmarkers` (Route D headline) and `dropmarkers-s125repro`

- **6 predicts:** no fault, a non-null plane, and a plane location matching **victim[0]**, not (0,0,0).
- **7 predicts (fly LAST — it spawns a second plane):** a fault at `rva 0x13495DD, addr=0x0`, **after**
  spawning a plane, *with the markers resident* — i.e. residency does **not** prevent the fault. **That
  is the claim.** If arm 7 does not fault, the whole `KOUTPARMRET` story is wrong and arms 4 and 6 were
  measuring something else.

### 18.5 What each route leaves in the world, and what needs undoing

| arm | leaves behind | reversible? |
|---|---|---|
| `droppod-readonly` | nothing | n/a |
| `droppod` / `droppod-newest` | **a real `BP_DropPod*_C` actor**, plus a `BP_DropPlane_Straight_Tutorial_C` **if C3 pre-spawned** | **NO. Nothing is undone.** Recovery = restart the client. The shim says so in its own final line. |
| `droppod-noprespawn` | a drop pod only | NO |
| `dropmarkers-readonly` | nothing | n/a |
| `dropmarkers-gateonly` | **nothing** — both tags restored on the normal path, the SEH fault path and the final report, each readback-verified, and (new) only for victims we actually wrote whose slot still holds our value | yes, automatically |
| `dropmarkers` / `-outparm` / `-s125repro` | a plane; tags restored | plane: **NO**; tags: yes |
| `dropmarkers-norestore` | a plane **and two contaminated `Tags` arrays** | **NO — do not use it unless you are chaining a probe that needs the markers resident** |
| `dropplane-handler` | nothing (no `SpawnPlane`) | n/a |

⚠ **Any census in a world that has already taken one of these arms must tolerate the leftovers.** All
three modes latch a BEFORE set, diff against it, and exclude archetypes from every bucket, so a
pre-existing plane cannot be counted as new — but a **half-constructed** S125 plane is also a plausible
`AMBIGUOUS` trigger for Route C's ship enumeration. That is by design: it refuses rather than guessing.

### 18.6 The exact operator sequence

**Requires an ELEVATED PowerShell. Steam must already be running** — without it, login dies with
`Auth Failure 14005` and the sitting is wasted before it starts.

```powershell
# 0. Preconditions, once.
#    server/internal/interactive/interactive.go -> const forceTutorialMatch = true
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags

# 1. ELEVATED PowerShell, from the repo root. Steam already running.
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -NoHook          # returns after launching; the game keeps running

# 2. Stage the world and inject ONE arm. One arm per staged world.
#    Expect only ~2 of 4 launches to reach an armed window -- budget on ARMED WINDOWS, not launches.
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_droppod_readonly.dll -Label s126-c0
# ... re-stage ...
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_droppod.dll          -Label s126-c1

# 3. Read the marker. fk24-stage copies it off after every step; the probe's own copy is
#    docs\fk24-stage-<label>-4-probe-<dll>.txt        ([PD] / [DM] lines)
#    Loki.log is at %LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log
```

Recommended order across sittings, one variable per sitting:

1. `tutorial_launch_droppod_readonly.dll` — instrument check. Non-zero DropPod delta ⇒ **stop**.
2. `tutorial_launch_droppod.dll` — **the headline**.
3. `tutorial_launch_dropmarkers_readonly.dll` — Route D staging gate. No AGREE for both markers ⇒
   **stop**; nothing downstream is interpretable.
4. `tutorial_launch_dropmarkers_outparm.dll` — ⚠ calls `SpawnPlane` with the gate **deliberately failed**.
5. `tutorial_launch_dropmarkers_gateonly.dll` — the mechanism, world left as found.
6. `tutorial_launch_dropmarkers.dll` — Route D headline.
7. `tutorial_launch_dropmarkers_s125repro.dll` — the controlled reproduction. **Last**; second plane.
8. `tutorial_launch_dropplane_handler.dll` — B3a/B3b, free, whenever a world is going spare.

⚠ Do **not** use `-Hook <dll>` for any of these. Both are continuation modes and need the staged world
(`gft_ready_fix` → `tutorial_launch_fo` → `tutorial_launch_sp` → probe); a lone `-Hook` cannot work.
⚠ **Re-verify the `.text` sha256 and the import table against §18.1 immediately before each flight.**
The `build/` directory changed under the reviewer mid-review — another agent was building concurrently —
so a stale or foreign artifact is a live risk, and an A/B against a copy of itself burns a launch.

### 18.7 What is NOT ready — read this before claiming anything

- **Nothing here has been flown.** Every claim in §18.1–§18.2 is a build-time or offline measurement.
  Every claim in §18.4 is a **prediction**.
- **Route C's premise has four untested links**, all knowable from the first log, which is exactly why
  the signature dump and both bail-point readbacks are printed: (i) whether `SpawnDropPodForTeam`
  resolves at all on a live ship's chain — FK-1 measured AS UClasses unregistered **at the menu** (0/15)
  and nothing has ever measured a loaded map; (ii) whether its parameters really are
  `(int, FVector&, FVector&)` in declaration order, and whether the `const FVector&` flag set classifies
  as I predicted; (iii) whether `FVector` is 24 bytes here — the mode **measures** it and refuses any
  other width, but the measurement has not been taken; (iv) whether the chosen ship's
  `TeamDropPodClass` is non-null. If S125's actor really is half-constructed, that is the most likely
  null, and the log will name it.
- **`KOUTPARMRET=1` has never executed.** It is correct against `ProcessEvent`'s documented parameter
  loop and it is the only thing that explains the measured fault, but the first arm that turns it on is
  the first arm that exercises it — and it is now on **every** droppod variant as well.
- **A null drop leader is graded [I], not [M].** §3 grades it survivable at 3 of ≥4 known consumer
  sites. `GetTeamDropLeader` will return null (`AuthSetSpawnTeamLeader` is an empty fold); whether
  `SpawnDropPodForTeam` survives it is precisely what this arm tests. Log it; do not assume it.
- **Neither route delivers "a hero in a pod".** Route C delivers a pod. The pod→hero handoff
  (`AuthBeginGlideDiveFromDropPod`) and the plane→player handoff (`ALokiDropPlane::AddPlayerToPlane`)
  are both **FK-1 empty impls**, and nothing in this section touches them. **Say "a pod exists", never
  "the drop works".**
- **The DropPlane component is still not subscribed** to `GameState.OnRoundPhaseChanged` (§15). Route
  D's `SpawnPlane` reaching its node [40] `EX_AddMulticastDelegate` is the one plausible route to that
  subscription, and **the delegate receipt is resolved but not sampled around D4** — so this sitting
  cannot answer it. Wire `DpDelegateReport` into the Route D ladder before treating it as a test.
- **Route D option (iii) — forcing World Partition cells to stream in — is the mechanically correct fix
  and it is NOT implemented**, because no graded runtime mechanism could be named.
  `UWorldPartitionBlueprintLibrary::LoadActors` is editor-only. Route D makes the **tags** resident, not
  the **cells**; those are not the same thing, and the shim says so in its own output.
- **`RM_DROPPLANE` (S125), `RM_DROPPOD` and `RM_DROPMARKERS` are ALL uncommitted working-tree changes on
  `dedicated-server-stub` (HEAD `2c72d0e`, whose message covers only the phase ladder).** A `git stash`,
  `git checkout` or `git clean` destroys three sessions of shim work. **Commit before doing anything
  git-shaped.**

---

## 19. FLOWN — Route C is blocked by a NULL `UFunction.Func`, and that corrects FK-1

**Date:** 2026-08-17, PID 138796, the S125 world reused (no relaunch). Builds
`tutorial_launch_droppod_noprespawn.dll` `.text 32fa55a033796213` then, after a fix, `78629ae06c831d20`.
Zero `.text` writes, zero crashpad handoffs. Evidence: `docs/fk24-s126-routeC-RESULT.txt`,
`docs/fk24-s126-ABORT-elemsize.txt`.

### 19.1 The ship resolved, and the two bail points read clean

```
ship enumeration: 12 objects whose chain declares LokiDropShip (11 excluded as archetype/_GEN_VARIABLE),
                  1 live candidate
ship selection:   0x2AD6F1F20E0  reason: the ONLY live actor deriving from LokiDropShip
                  chain = BP_DropPlane_Straight_Tutorial_C <- BP_DropPlane_Base_C <- LokiDropShip <- ...
                  TeamDropPodClass@0x478 = BP_DropPod_Tutorial_C     <- bail point 1 SATISFIED [M]
```
★ The ship is S125's half-constructed plane — the artifact of the previous flight became the target of
this one. ★ **[M] Angelscript UClasses ARE registered in a loaded map**: `SpawnDropPodForTeam` resolved
on the live class with a full parameter chain. FK-1 measured 0 of 15 AS classes registered **at the
menu**; this is the in-world counterpart it called for, and it is positive.

### 19.2 ★★★★★ THE WALL: `UFunction.Func` IS NULL

```
C1: SpawnDropPodForTeam has no Func thunk -> NOT CALLED
```
Verified directly by RPM, with a control in the same read:
```
SpawnDropPodForTeam   UFunction 0x2ACBD0EDFD0   Func @+0xE0 = 0x0              *** NULL ***
K2_GetActorLocation   UFunction 0x2ACBC8F2F80   Func @+0xE0 = 0x7FF78664AE10   non-null
```
`K2_GetActorLocation` is not a hypothetical control — **it dispatched successfully in this very run**
(arm C0c). So `+0xE0` is the right field, a callable function has a non-null `Func`, and this one's is
genuinely empty.

⇒ **[M] THE S55 DIRECT-THUNK PRIMITIVE CANNOT CALL `SpawnDropPodForTeam`.** The primitive's whole
mechanism is "call `UFunction.Func` directly"; there is nothing to call.

⚠⚠ **THIS QUALIFIES FK-1 — and FK-1 flagged it first.** `docs/fk1-angelscript-settled.md` §4
concludes *"Callable by the existing S55 recipe unchanged"*, which **is false as stated** for this
function. But the very same sentence carries the hedge **"(mechanism named; the `Func` value itself
is INFERRED)"** — i.e. FK-1 named the exact quantity that S126 measured null. ★ **The headline
over-claimed; the parenthetical was right.** An earlier draft of this section said flatly "THIS
CORRECTS FK-1" without quoting the hedge, which is the kind of compression this project's own
S115-d artifact exists to prevent — a correct measurement flattened into prose that asserts more
than the source did. **Cite the hedge whenever citing this correction.** FK-1's underlying finding stands — AS is AOT-transpiled and the compiled bodies exist at
`.text 0x059128B0–0x05A7F070`, with a recovered **1,459-row symbol table** (script fn → raw /
`_VMEntry` / `_ParmsEntry` RVAs) — but **the reflected `UFunction` is not wired to that body.** The
code is compiled in; the reflection entry is a shell.
⚠ Scope honestly: measured on **one** AS function. Whether every AS `UFunction` has a null `Func`, or
only `CanOverrideEvent`/BlueprintCallable ones, or only this one, is **NOT established** — and it is a
cheap census (walk AS-owned UFunctions, read `+0xE0`, histogram).

### 19.3 The route that survives

The compiled body still exists and FK-1 already recovered its address. **Call the AOT body DIRECTLY**
at its raw RVA from `tools/asdump/out/` rather than through the UFunction — no reflection, no
`ProcessEvent`. That needs the calling convention worked out (`_ParmsEntry` suggests a params-struct
ABI), which is exactly what the symbol table's three columns are for.
Second option: `ProcessEvent` (slot 56), which for a script function may dispatch by a path that does
not read `Func`. ⚠ CLAUDE.md records slot-56 `ProcessEvent` **no-ops for native functions** — that is
about NATIVE functions and says nothing about this case; do not read it as a refusal.

### 19.4 ⚠ Two instrument defects found in this flight, one fixed mid-flight

**(a) `FPROP_ELEMSIZE` was `ArrayDim`, off by one field — FIXED.** The first injection printed
**`size=1` for EVERY parameter slot** (`IntProperty` 1, two `Vector` StructProperties 1,
`BoolProperty` 1) and the mode **REFUSED to call** ("ElementSize=1 is neither 24 nor 12"). `0x30` is
`ArrayDim`, which is 1 for every property that is not a C-array. Corrected to `0x34` — forced by
arithmetic from two long-proven constants (`FPROP_FLAGS=0x38` is a uint64 preceded by exactly two
int32s; `FPROP_OFFSET=0x44` closes the far side). After the fix: **`Int=4`, `Vector=24`, `Bool=1`.**
★ That also MEASURES what the mode was built to measure: **`FVector` in this build is 3 × double
(24 B, LWC)**, not floats. ★★ **The refusal is what made this diagnosable** — a mode that called with
a fabricated zero would have produced a fault or a null and blamed `SpawnDropPodForTeam`.

**(b) The C0c control "AGREED" at the ORIGIN, which is a weak pass — flagged, not fixed.**
`K2_GetActorLocation` returned `(0,0,0)` and the RPM cross-read of `RootComponent->RelativeLocation`
also returned `(0,0,0)`, so `|delta| = 0 -> MATCH`. But the ship is S125's half-constructed plane,
which never received a position — so **the agreement is between two zeros.** The reviewer named this
exact hazard before the flight ("a ship near the origin reads MATCH for a return never read"); the
mitigation shipped (read both sources, print which was used — it printed
`USED=g_rbuf/RESULT_DECL`) proves the right *buffer* was read, but the *value* cannot discriminate.
⇒ **On a ship at the origin, C0c proves the dispatch path and NOT the marshalling of a non-zero
struct.** Fly it against a positioned actor before treating a MATCH as a strong control.

**(c) The verdict line over-claims.** It printed *"control AGREED, so C1 (status -1, DropPod delta +0)
is attributable"* — but the same log defines `-1 = NOT CALLED` and adds *"-1 is NOT a clean run"*.
A never-dispatched call has nothing to attribute. The delta table is honest (`after-C1 census SKIPPED:
C1 never dispatched`); only the summary sentence is wrong. **Do not cite that line.**

## 20. Route E — dispatching a null-`Func` script UFunction

**Status: OFFLINE WORK COMPLETE, CODE BUILT AND VERIFIED, NOT FLOWN.** Zero launches, zero
injections, zero `.text` writes. Everything below the "what was built" heading is disassembly of
`dumps/merged2.dump.exe` (file offset == RVA) plus the on-disk `PrecompiledScript.Cache`. Not one
instruction of the new arm has executed against the game.

---

### 20.1 The offline answer: a null `Func` is **not** an accident, and `ProcessEvent` is the designed route

S126 measured `SpawnDropPodForTeam`'s `UFunction.Func` (`+0xE0`) as `0x0` while a native control
(`K2_GetActorLocation`) held a real thunk. The question this section answers is *what dispatches such
a function*, and the answer is a specific branch inside `ProcessEvent` that never reads `Func` at all.

**`UObject::ProcessEvent` = rva `0x1344E10`. Its vtable displacement is `0x270` = SLOT 78** — not the
"slot 56"/disp `0x1C0` recorded in `docs/next-session-prompt-s80.md`. Three independent instruments
agree: 3,651 `.rdata` vtables hold `0x1344E10` at exactly `+0x270`; the UHT stub at `0x54532B0` is
`mov rax,[rcx]; mov rbx,[rax+0x270]; call 0x1344150 (FindFunctionChecked); … call rbx`; and
ProcessEvent's own body reads the neighbouring slots `+0x278`/`+0x280` as
`GetFunctionCallspace`/`CallRemoteFunction`, the stock consecutive triple. The occupant of disp
`0x1C0` opens `mov rax, gs:[0x58]` and is not a dispatcher — which retro-explains
`tutorial_launch.cpp:3616` ("S80 falsified our ProcessEvent RVA").

**ProcessEvent has FOUR exits, and only one of them skips `Func`:**

| # | condition | what happens |
|---|---|---|
| A | `Func != 0`, bit 0x10 clear | normal path → `UFunction::Invoke` (`0x1225F30`) → `0x1225FCF call qword ptr [r14+0xE0]`. **There is no null test anywhere in `Invoke`** — for `Func == 0` this is an unconditional `call [0]`. |
| B | `(flags & 0x410) == 0` **and** `Script.Num (+0x70) == 0` | reject gate at `0x1344E69`/`0x1344EAA` returns immediately. Safe, and a **guaranteed silent no-op**. |
| C | **bit 0x10 SET** | `0x1344EB4 mov ecx,[rdi+0xB8]; test cl,0x10` → `0x1345089 call qword ptr [rax+0x378]` (Fn, Obj, Parms) and return. **`Func` is never read.** (With the sign bit / `FUNC_NetValidate` also set it first calls `[+0x380]` for a companion UFunction.) |
| D | the **callspace gate** — see §20.2 | returns having dispatched nothing, with no log and no fault. |

⇒ **Route E is the *designed* path for this function, not a workaround** — provided the live
UFunction carries bit 0x10. That is one dword, and it has never been read live. The shim's grade
prints it in the first three lines of `E-grade SpawnDropPodForTeam(E1)`.

**Bit 0x10 is this build's AngelScript marker — [M], four ways.**
1. `UFunction`'s own vtable is `.rdata 0x076FEB60`, 113 slots; **slot 111 (`+0x378`) = `0x0F7EC20`
   (`ret 0`) and slot 112 (`+0x380`) = `0x0F7EB50`** — both universal folds, and both the *last two*
   slots, the shape of fork-added virtuals. A non-fold occupant therefore *proves* the live object is
   a UFunction **subclass**.
2. 32 further 113-slot vtables sit back-to-back at `.rdata 0x0848A140..0x08490EB8` (stride `0x388`),
   installed from `.text 0x0469C2B9..0x0469C859`. Each matches `UFunction`'s vtable in 109 of 111 of
   slots 0..110 and all 32 carry slot 78 == `0x1344E10`. All 32 have distinct real slot-111 bodies in
   `0x048E6570..0x048E8D70`; all share slot 112 = `0x01D3B890` = `mov rax,[rcx+0xF0]; ret`.
3. Slot 111 (read at `0x048E6570`) is the **AngelScript context marshaller**: loads `[Fn+0xE8]`
   (`asCScriptFunction*`), **bails to a null return at `0x048E658E` if it is 0**, optionally
   re-resolves a virtual override via `[[Obj+0x18]+0x140]+0x1D8][idx]`, walks a parameter-descriptor
   array, calls `SetArg*`, tests `FunctionFlags & 0x2000` (`FUNC_Static`) before `SetObject`
   (`0x47E5CD0`), then `Execute` (`0x47814C0`). **No authority test, no net test, no `Func` read.**
4. The generator at `.text 0x048AA930..0x048ABAB8` does `0x048AAEF2 or dword [r14+0xB8],0x10`, sets
   `ReturnValueOffset(+0xC0) = 0xFFFF`, stores the script fn at `[r14+0xE8]`, and **never writes
   `+0xE0` (`Func`) nor `Script` (`+0x68`/`+0x70`)**.
   *Control:* bit 0x10 (and 0x20) occur in **0 of 18,325** UHT-registered native UFunctions
   (`tools/re/out/uht_funcflags_tuthero.csv`).

**The "3 `Script` bytes" question is void — the premise was wrong.** `UStruct::Script` is
`Data@+0x68 / Num@+0x70 / Max@+0x74` (ProcessEvent tests `[Fn+0x70]` as the reject-gate counter and
reads `[rdi+0x68]` as `FFrame.Code`). Script UFunctions have `Script.Num == 0`, which is *why* bit
0x10 had to be OR'd into the `0x410` reject mask. **There are no script bytes to decode.**
The `+0x108` "TArray Num=3 Max=4" observed live is **not** `Script` and **not** a read-past-the-object
artifact: it is a real member of the script-UFunction subclass — a `TArray` of **0x48-byte parameter
descriptors**, `Num` at `+0x110`, read as such by two independent sites (generator `0x048AB7A0`,
dispatcher `0x048E6620`). `Num = 3` is the three *inputs*; the ReturnValue FProperty is held
separately at `+0x130`.

**StaticJIT registration for this exact function, recovered from scratch.** FK-1's 1,459-row symbol
table is **not on disk** (`tools/asdump/out/symbols.csv` is 2,674 rows of a different thing and does
not contain `SpawnDropPodForTeam`). Recovered directly: cache **Id `0x01818A81`** via
`asdump.load_cache(...)` (`bIsUFunction=1`, `BlueprintCallable=1`, `BlueprintAuthorityOnly=0`,
3 params); that Id appears **exactly once** in `.text` as `mov edx,0x1818A81` inside the registration
stub at **rva `0x00F2D810`**, whose three rip-relative LEAs and stack arg resolve to:

| | RVA |
|---|---|
| **RAW** | `0x0597E730` |
| **`_ParmsEntry`** | `0x0597F670` |
| **`_VMEntry`** | `0x0597F7B0` |

All three lie inside FK-1's measured body range `0x059128B0..0x05A7F070`; the stub calls
`FStaticJITFunction::ctor` (`0x048FE510`).

`_ParmsEntry` yields the ABI `bool __fastcall RAW(FScriptExecution&, UObject*, int32 TeamIndex,
const FVector* SpawnLocation, const FVector* LandingLocation)` with flat-block offsets
**`0x00` / `0x08` / `0x20`, bool return at `0x38`** — **byte-identical to the live FProperty offsets
Route C read off the UFunction**, an independent confirmation of both readings and of
`FVector == 3 doubles (LWC)`.

**Route F (call RAW/`_VMEntry` directly) is deliberately NOT implemented.** `0x0597E730` reads as
16 zero bytes in **all 18 dump images on disk** — *COVERAGE-BLOCKED, never ABSENT*; its first
argument is a live VM object the shim cannot legitimately fabricate; and Route E reaches the same
compiled body *through* the engine. The RVAs are recorded as the named successor if Route E is ever
measured inert.

---

### 20.2 What the review caught, and what changed because of it

Three findings were load-bearing and each is now instrumented rather than assumed.

**(a) The callspace gate sits IN FRONT of the alt-dispatch branch — a fourth silent exit.**
Bit 0x10 is *inside* the `0x410` mask, so a script UFunction does **not** take the `je` at
`0x1344E73`. It falls into the net-routing block:

```
0x1344E69  test dword [rdx+0xB8], 0x410
0x1344E73  je   0x1344EAA                 ; NOT taken when bit 0x10 is set
0x1344E7B  call qword [rax+0x278]         ; GetFunctionCallspace
0x1344E83  test al, 1                     ; Remote -> CallRemoteFunction [rcx+0x280]  (a REAL side effect)
0x1344EA5  test bl, 2                     ; Local?
0x1344EAE  je   0x1345468                 ; RETURNS. No dispatch, no log, no fault.
0x1344EB4  ...                            ; only now the bit-0x10 branch
```

`AActor::GetFunctionCallspace` (`0x3388E40`) returns **Absorbed (0)** when
`byte[actor+0x160] (Role) < 3` **and** `FunctionFlags & 0x4` (`BlueprintAuthorityOnly`). The grade
now reads both inputs, prints the two vtable occupants with RVAs, and — when the Absorbed condition
holds — prints `PREDICTED **ABSORBED**` *before* the call. It does **not** call
`GetFunctionCallspace` itself; that would be an extra virtual call purely to instrument, and the
inputs are free.

**(b) The marshaller uses its OWN offset table, not the FProperty chain.**

```
0x048E6620  mov    rax, [rdi+0x108]           ; descriptor array
0x048E6627  movsxd rdx, dword [r14+rax+0x40]  ; <- the offset into Parms
0x048E662C  movzx  eax, byte  [r14+rax+0x44]  ; <- type tag
0x048E66B6  add    r14, 0x48                  ; stride
0x048E676A  cmp    qword [rdi+0x130], 0       ; return FProperty; 0 => no return written
0x048E6782  movsxd rbx, dword [rdi+0x170]     ; <- the RETURN's offset into Parms
```

They are *expected* to equal the FProperty offsets — the offline `_ParmsEntry` ABI matches the live
chain exactly — but "expected" is not measured. E1 now reads the marshaller table, prints it, and
**refuses** if the two tables disagree (`PDER_MARSHAL`), and reads the return from `[fn+0x170]`
rather than `Offset_Internal` when the SAFE-VIRTUAL path is the one being taken.

**(c) `ReturnValue == false` had three causes and one reading.** `Execute`'s result is *not* checked
at `0x048E6765`, so "the script ran and returned false", "`[fn+0xE8]` was null so slot 111 returned
at `0x048E658E` without executing anything", and "Prepare/Execute failed" all produced a zero byte.
The return slot is now pre-filled with the sentinel **`0xA5`**. An intact sentinel means **nothing
ever wrote a return**, and the marker says so in those words.

**(d) E0 was not a control for the path E1 takes.** `K2_GetActorLocation` has a non-null `Func`, so
it exercises exit **A**; E1 takes exit **C**. They share only ProcessEvent's prologue. A new control
**E0c** closes this: it scans the ship's own class chain for a UFunction with **bit 0x10 set,
`Func == 0`, zero non-return parameters, a declared ReturnValue, and a read-only-shaped name**
(`Get*`/`Is*`/`Has*`/`Can*`), calls it through the same ProcessEvent with the sentinel, and reports
**STRONG PASS iff the sentinel is overwritten**. Nothing is fabricated and nothing in the world is
mutated. If no candidate exists, it says so and declares E1 unattributable.

**(e) The verdict chain published an instrument statement as the project's conclusion.**
`g_pdE1Refused` was set by four unrelated causes and the headline printed *"ProcessEvent is not a
Func-free route for this UFunction … Route E dies on the same null Func that closed Route C"* for
**all** of them — including a live-FProperty read defect, exactly the class that made every slot read
`size=1` until `FPROP_ELEMSIZE` was corrected `0x30 → 0x34`. The refusal reason is now explicit
(`PDER_GRADE` / `PDER_LAYOUT` / `PDER_MARSHAL` / `PDER_PRECOND`) and only `PDER_GRADE` prints a
finding. Five abort paths that used to set neither `ran` nor `refused` — leaving the run's headline
section with **no verdict line at all** — now record a reason, and a terminal `else` declares the
section VOID if the combination is ever still reachable.

---

### 20.3 What was built

**File changed:** `G:\git\Supervive Revival Project\tools\sigbypass-mod\tutorial_launch.cpp`
(+ the three `droppod-pe*` variant rows already present in `tools\sigbypass-mod\build.ps1`).
New knob: `KPDPEALTCTRL` (default **1**, E0c on). Existing knobs `KPDPEDISP=0x270`,
`KPDPEDISPOLD=0x1C0`, `KPDPEFORCE=0`, `KPDARMS` bit7 = E0/E0c, bit8 = E1 — all defaults unchanged.

Build with `build.ps1 -Name tutorial_launch -Variant <v>` (it refuses `-Variant` without `-Name`; a
bare `-Variant` silently builds the default set and reports "11 built, 0 failed", which reads like
success).

| variant | `.text` sha256[:16] | bytes |
|---|---|---|
| **`play`** (regression gate) | **`9bc10a4552c596e1`** | 163,328 |
| `droppod` | `9e8148635b2ddcf5` | 137,728 |
| `droppod-readonly` | `9fd364cbc16f9aaf` | 119,808 |
| `droppod-noprespawn` | `a08f99d8632a88dd` | 129,536 |
| `droppod-newest` | `54445f1330ed2b4a` | 137,728 |
| **`droppod-pe-ctrl`** | **`ac5b4584066cd927`** | 148,480 |
| **`droppod-pe`** | **`e7771c1705141656`** | 159,744 |
| **`droppod-pe-force`** | **`d895bccb2ab8ba36`** | 159,744 |

**All eight distinct.** ⚠ `droppod`/`droppod-newest` share a `.text` *size*, and so do
`droppod-pe`/`droppod-pe-force` — only the hash separates them. **Diff `.text`, never size.**
⚠ These hashes **supersede** every earlier droppod figure in this session's notes; the whole family
was rebuilt after the fixes.

**Safety statement, checked rather than asserted.**
* **No module-image writes.** No `.text` write of any kind is added; arming is the heap
  `UFunction.Func` swap (`FsArm`/`FsHold`/`FsDisarm`), and the mode still *refuses* to run under
  `KFUNCSWAP=0` rather than falling back to `InstallHook()`.
  **Import-table evidence:** `FlushInstructionCache` / `VirtualAlloc` / `VirtualFree` are **ABSENT**
  from all three `droppod-pe*` DLLs (and from `play`), while the mandated positive control
  `tools\sigbypass-mod\build\tutorial_launch_fo.dll` has **all three PRESENT**. With
  `FlushInstructionCache` gone, `SafeWrite`/`InstallHook` are linker-eliminated, so the property
  holds at the artifact level.
  ⚠ `VirtualProtect` is present in **both** arms *and* in `fo.dll` — it backs `SafeWritable`
  probing and **does not discriminate**; it is not part of the signature.
* **No C++ exceptions.** SEH only. `verify_dll.py` **VERDICT: PASS** on all three (no
  `__CxxFrameHandler3/4`, no `_CxxThrowException`, no `_Unwind_Resume`, no CRT import, bare DllMain,
  82 KERNEL32 imports).
* **No hardcoded ASLR addresses.** ProcessEvent is read from the *target object's own vtable* at a
  knobbed displacement, with refusals for a heap "vtable" (the S124 `GameState+0x258` guard), an
  out-of-image target, and a universal-fold occupant. Every RVA in this section appears in comments
  and log strings only; the one numeric band (`PDPE_ASDISP_LO/HI`) is used to *classify* a printed
  RVA and is never dereferenced.
* **No memory pokes.** The only writes are into the shim's own 16-byte-aligned `g_pdpeparms[0x400]`,
  every one bounds-checked at the write site — so even `-DKPDFORCE=1` cannot write outside it.
* **Defaults unchanged; `play` is byte-identical.** During this work two edits to *shared* functions
  (`ActorLoc`, `FsArm`) moved `play` to `415386c1480eb870`. **The gate caught it and both were
  reverted.** `ActorLoc`'s diagnostic now lives in `PdActorLocProvenance()`, reachable only from
  RM_DROPPOD and therefore dead-code-eliminated out of every other variant; `FsArm`'s RM_PLAY-worded
  warning is **deliberately left wrong** and RM_DROPPOD prints its own mode-correct version in ladder
  step 0. A wrong log string is a smaller cost than re-qualifying the DLL that carries the measured
  0/16-vs-10/10 FK-7 result — and that trade is recorded here rather than hidden.

---

### 20.4 PRE-REGISTERED PREDICTIONS, per arm

Written before the flight. **The census delta is the result** — never a return value, never
"the call returned ok".

#### Arm 1 — `droppod-pe-ctrl` (`KPDARMS=0xB9`) — controls only, no script dispatch of the target

⚠ **This is not a call-free arm.** `0xB9` sets bit3 (C3 pre-spawn, which calls `SpawnPlane` and
**creates an actor**), bit5 (C0c direct-thunk `K2_GetActorLocation`) and bit7 (E0/E0c). It makes at
least three real UFunction calls and mutates the world. The call-free arm is `droppod-readonly`
(`0x11`, `KPDPRESPAWN=0`).

* **Positive control that proves the arm ran:** the marker reaches `[PD] done (step=8 …)`.
  Any `step < 8` means the ladder starved — read `FsHold`'s 8 s verdict first.
* **CONFIRMS the SAFE-INVOKE exit:** `E0 … STRONG PASS` against a **non-zero** reference.
* **CONFIRMS the ALT-DISPATCH exit:** `E0c: STRONG PASS -- the sentinel 0xA5 was overwritten`.
  This is the only line in the whole arm that says the marshaller can execute.
* **FALSIFIES the route:** `E0 … FAIL` (fault or MISMATCH against a sound reference), or
  `E0c: FAIL -- the sentinel is INTACT`.
* **VOID:** `E0 … WEAK CONTROL (origin)` **and** `E0b` unavailable — two zeros agreeing prove
  nothing (the S126 C0c lesson). Also VOID if `[FS] ZERO TARGETS SWAPPED` appears.
* **Uninterpretable, not negative:** `E0 … MISMATCH` where the same line reports
  `AttachParent = 0x…` non-zero or the RelativeLocation offset `GUESSED (0x158)` — the reference is
  not comparable and the arm says so.
* **`E0c: NO CANDIDATE`** is not a failure of the route; it means the alt-dispatch branch has **no
  positive control this sitting**, and E1 must therefore not be read as a game statement.

#### Arm 2 — `droppod-pe` (`KPDARMS=0x1FF`) — the headline

Fly **only** if arm 1 reached `E0 STRONG PASS` **and** `E0c STRONG PASS`.

* **Positive control:** the same `E0`/`E0c` lines re-run inside this arm, plus `done (step=8 …)`.
* **The three outcomes point at three different conclusions — this is the whole point of the arm:**

| observation | conclusion |
|---|---|
| **FAULT** (`E1 AFTER: fault=*** FAULTED ***`) with grade **WILL-FAULT** | the predicted `call [0]`. **Route E is closed for this function** and the successor is the StaticJIT triple in §20.1 or writing `Func` itself. |
| **FAULT** with grade **SAFE-VIRTUAL** | a fault *inside* the marshaller or the script body — a **new fact**, and the first one. Preserve the marker; this is not the predicted outcome. |
| **NO-OP** — no fault, sentinel `0xA5` **INTACT**, delta `+0` | **the script body did not complete.** Read `E-SUMMARY 5/7b`: `[fn+0xE8] == 0`, or the callspace gate absorbed the call (`absorbRisk=1`), or Prepare/Execute failed. **This is an INSTRUMENT reading, not "the pod did not spawn".** |
| **`ReturnValue == false`** — sentinel **overwritten**, byte 0, delta `+0` | the marshaller really executed and the script really returned false. **This IS a game statement**: `SpawnDropPodForTeam` ran and declined. Next question becomes *why it declined*, and the pre-call bail-point readout (`TeamDropPodClass`) is already in the marker. |
| **`ReturnValue == true`** with **DropPod delta `+1`** | Route E works and the drop pod exists. |
| **`ReturnValue == true`** with delta `+0` | contradiction — the function claims success and the census disagrees. Do not resolve it in favour of either; report both. |

* **VOID:** any of arm 1's VOID conditions, or `E-VERDICT: … NOT ATTRIBUTABLE` (E0c did not pass), or
  `E-VERDICT: … NO VERDICT REACHABLE` (an abort path returned without recording why — an instrument
  defect in this shim, and the run must be reported as such).
* **Explicitly NOT a result:** `refused=1` with reason `LAYOUT` / `MARSHALLER … DISAGREEMENT` /
  `PRECONDITION`. Those print *"THIS IS NOT A RESULT ABOUT ProcessEvent AND NOT A RESULT ABOUT THE
  DROP POD"*, and Route E is neither confirmed nor closed by such a run.

#### Arm 3 — `droppod-pe-force` (`KPDPEFORCE=1`) — last resort only

Fly **only** if arm 2 printed the `WILL-FAULT` refusal *and* the access violation is wanted as
evidence. It deliberately spends the game thread on a near-certain AV. An AV here is the
**predicted** outcome and therefore not a new fact; the only informative result is the *absence* of
one.

---

### 20.5 What the probe leaves in the world

* **Nothing is undone**, and the marker says so. Any DropPod that E1 spawns and any plane that C3
  pre-spawns stay in the world. **Recovery is a client restart.**
* The heap `UFunction.Func` swap is disarmed by `FsDisarm` on the way out (`restored N/N` in the
  marker); a mismatch there is itself a finding.
* No module image, no `.text`, no game data is modified. `g_pdpeparms` is shim-private.
* ⚠ A **half-constructed plane** may already exist from the S125 artifact. The census is taken
  before anything runs and re-baselined if C3 pre-spawns, so a pre-existing drop actor is tolerated
  rather than assumed away — but read `BEFORE=` before reading any delta.
* ⚠ Every injection truncates `docs\tutorial-launch-marker.txt` (FK-25); `fk24-stage.ps1` copies
  each stage off to `docs\fk24-stage-<label>-<n>-<shim>.txt`.

---

### 20.6 Correction note — what this does and does not say about FK-1

S19 of this document said the null `Func` "corrects FK-1". **That is too strong, and the softening
matters more than the headline.**

FK-1's *conclusion sentence* — that script UFunctions are "callable by the existing S55 recipe
unchanged" — did over-claim: the S55 direct-thunk primitive calls `UFunction.Func`, and for this
function that pointer is null, so the recipe as stated cannot work. But **FK-1 carried the hedge that
named exactly what was later measured false**, in the same breath:

> "(mechanism named; **the `Func` value itself is INFERRED**)"

It also recorded, correctly, that `_ParmsEntry` "reads args from a flat block using UE's
`Align(off, alignof(T)); off += sizeof(T)` packing and writes the return at `ReturnParmOffset` —
that is `ProcessEvent`'s contract and nothing else in UE has that shape", and that "the script corpus
itself dispatches a script UFUNCTION via `FindFunctionChecked` + `ProcessEvent`."

⇒ **FK-1 identified the correct dispatch mechanism and flagged its own weakest link.** What S126
measured is the flagged inference, not the analysis. The honest form is: *FK-1's mechanism stands and
its `Func` inference is refuted; the route it named — `ProcessEvent` with a flat params block — is
the one Route E takes.* Recording this as "FK-1 was wrong" would discard a correct hedge and the
correct successor it pointed to.

Two further corrections that fall out of the same read, both **[M]**:

* **`docs/next-session-prompt-s80.md` and `docs/coverage-audit-s101.md:529`** still give ProcessEvent
  as `base+0x12C5A10` / "slot 56" and describe it as a "uniform no-op for injected calls". The
  address is refuted (see §20.1), and the "ProcessEvent is neutered" corpus behind that claim was
  collected against a virtual that **is not ProcessEvent**. Those docs were deliberately **not**
  edited here — rewriting them belongs in a pass with the FK register open, not as a side effect of a
  code task.
* CLAUDE.md's *"the direct call has no guards, so it works where slot-56 `ProcessEvent` no-ops for
  native functions"* is about **native** functions and says nothing about a script function with a
  null `Func`. It is not a refusal of Route E — and it is not an endorsement either.

---

### 20.7 Operator sequence

The client is already booting, `forceTutorialMatch` is already `true`, and `ags` is rebuilt. So it is
just the stage-and-inject call, from an **ELEVATED PowerShell**:

```powershell
cd "G:\git\Supervive Revival Project"

# 1. CONTROLS FIRST -- no script dispatch of SpawnDropPodForTeam is attempted.
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_droppod_pe_ctrl.dll -Label s127-pe-ctrl

# 2. THE HEADLINE -- only if step 1 printed BOTH `E0 ... STRONG PASS` and `E0c: STRONG PASS`.
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_droppod_pe.dll -Label s127-pe

# 3. LAST RESORT -- only if step 2 printed the WILL-FAULT refusal and the AV is wanted as evidence.
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_droppod_pe_force.dll -Label s127-pe-force
```

Re-hash the three DLLs immediately before injecting (`.text`, not size) and do not build into
`tools\sigbypass-mod\build` while an arm is staged — during this session an artifact was rebuilt
underneath a review, and only a hash refuted the mtimes.

Expect roughly **2 of 4 launches** to reach the armed window; budget on *armed windows reached*,
never on launches.

---

### 20.8 Is it ready to fly? — blunt assessment

**Yes for arm 1 and arm 2, with two named caveats. No for arm 3 until arm 2 has spoken.**

What is genuinely settled: the dispatch mechanism, the vtable slot, the four exits, the marshaller's
offset table, the StaticJIT triple, and the artifact-level safety properties. The code builds, passes
`verify_dll.py`, holds the `play` regression gate byte-identically, and its import table matches the
no-module-image-write signature against a working positive control.

What is **not** settled, and could still make a sitting worthless:

1. **Nobody has read bit 0x10 on this UFunction.** The entire viability of Route E turns on one
   dword. The arm prints it and refuses if it is clear — so the sitting is not *wasted*, but the
   optimistic outcome is unproven.
2. **The callspace gate has never been observed on this object.** `Role` at `+0x160` and
   `BlueprintAuthorityOnly` are both free RPM reads and neither has been taken. If the ship is
   non-authority and the function is authority-only, **every arm returns a silent null** and the
   sitting produces nothing but an instrument reading. *This is one read-only RPM and it is cheaper
   than a launch — take it first if a readout probe is available.*
3. **`E0c` may find no candidate.** If the ship's class chain has no zero-input, ReturnValue-bearing,
   read-only-shaped script function, the alt-dispatch branch has no positive control and arm 2's
   result is unattributable by construction. The arm detects and announces this, but it cannot fix it.
4. **The `AActor::ProcessEvent` world gate** (`GetWorld()` + `AreActorsInitialized`, `0x3F4FFB0`) is
   `[I, strong]` from field shape only and has never been read on a staged tutorial world. A failure
   there is a fifth silent null. `E0` passing on the same object rules it out — which is why E0 must
   pass before E1 is read at all.

The single most valuable thing that can still be done *before* spending an armed window is item 2:
read `byte[ship+0x160]` and `FunctionFlags & 0x4`. It costs one `ReadProcessMemory` and it decides
whether arms 1 and 2 can produce anything at all.

---

## 21. FLOWN — Route E DISPATCHED. `SpawnDropPodForTeam` ran and returned **false**, and the prime suspect is that ACTOR POOLING IS DISABLED

**Date:** 2026-08-19/20, PID 13484 (fresh launch; the S125/S126 world was gone). Builds
`dropplane_b1only` then `droppod_pe_ctrl` then `droppod_pe`. Zero `.text` writes, zero crashpad
handoffs on this client. Evidence: `docs/fk24-s127-E1-RESULT.txt`, `docs/fk24-s127-E-controls.txt`,
`docs/fk24-s127-b1-shipcreated.txt`, `docs/Loki-s127-routeE.log`.

### 21.1 ★ S125 REPLICATED EXACTLY on an independent launch

Injecting `dropplane_b1only` into the fresh world reproduced S125 line for line:
```
marker scan: TrainingStart=1  PlaneStartPoint=0  PlaneEndPoint=0   (2,878 actors, 676 tagged)
B1 SpawnPlane AFTER: *** FAULTED *** 0xC0000005 READ addr=0x0  rva=0x13495DD     <- IDENTICAL RVA
after-B1 *** NEW *** BP_DropPlane_Straight_Tutorial_C  ... <- LokiDropShip <- LokiDropPlane <- Actor
census: DropPlane=4 DropPod=2 DropShip=1  new=1
```
⇒ **[M] the marker-residency finding is REPRODUCIBLE, not a one-off**: same two markers unstreamed,
same fault address, same plane created. (S125 tagged-actor count 676 = this run's 676.)

### 21.2 [M] `ProcessEvent` DISPATCHES A NULL-`Func` SCRIPT UFUNCTION — the mechanism question is answered

```
ProcessEvent = 0x7FF7BBA66280 (rva 0x3396280), vtable disp 0x270 = SLOT 78
E1 CALL:  ProcessEvent(obj=BP_DropPlane_Straight_Tutorial_C, fn=SpawnDropPodForTeam, parms=...)
E1 AFTER: fault = returned without fault
          grade = SAFE-VIRTUAL (bit 0x10, Func-free)
          marshaller desc Num=3  readSlots=3   offsets vs FProperty: AGREE
          RETURN-SLOT SENTINEL 0xA5 -> raw 0x00 : OVERWRITTEN, the marshaller wrote a real return
          ReturnValue @0x38 = false (0)
          DropPod census BEFORE=2  afterE1=2  ==> delta +0
params: TeamIndex@0x0 size4 | SpawnLocation@0x8 size24 | LandingLocation@0x20 size24 | Return@0x38 size1
positions: Spawn=(-3206.4,5070.5,20100.0)  Landing=(-3206.4,5070.5,100.0)  (origin = the TrainingStart actor)
```
⇒ **The S55 direct-thunk route is dead for AS functions (S19, `Func == 0`), but `ProcessEvent` slot 78
→ `[UFunctionVtable+0x378]` is a working call route.** The `0xA5` sentinel is what makes this a
measurement rather than a guess: something wrote that byte, and `readSlots=3` with offsets agreeing
against the independent FProperty chain is not reachable by a path that never marshalled.
★ **[M] THE CALLSPACE GATE IS OPEN** — `role(obj+0x160)=3 (Authority)`, `BlueprintAuthorityOnly=0`,
`Static=0`, `absorbRisk=0`. The pre-flight worry that every arm would be silently absorbed is
measured away.

⚠⚠ **THE PROBE REFUSES TO CALL THIS A GAME FINDING, AND THAT VERDICT IS RECORDED AS IT STANDS:**
*"E0/E0b passed on the SAFE-INVOKE exit, but E0c — the only control for the `[+0x378]` marshaller,
which is the branch E1 takes — is INCONCLUSIVE (no candidate). E0 and E1 share only ProcessEvent's
prologue, so a pass on one says nothing about the other. Record E1 as UNATTRIBUTABLE."*
**E0c is UNSATISFIABLE on this class chain** — of **206** UFunctions scanned, exactly **1** takes the
alt-dispatch exit and it is not blind-callable. So "wait for E0c" is waiting for something that cannot
arrive. The flight went ahead with that stated in advance: **a positive would be self-attributing via
the census delta; a null is weak.** We got a null. ⇒ **treat S21.2's mechanism claim as [M] on the
instrumentation (sentinel + readSlots + offset agreement) and [I] on "the marshaller genuinely
executed the script body".**

★ The controls did their job: **E0 on the ship was correctly refused as `WEAK CONTROL (origin)`**
("two zeros agree perfectly and prove nothing") — the S126 lesson encoded and honoured — and **E0b
STRONG PASS** on the `TrainingStart` actor with a reference magnitude of **8376.8**.

### 21.3 ★★ WHY `false` — the prime suspect, named and evidenced

The AS decompile gives `SpawnDropPodForTeam` exactly two bail points:
```
if (TeamDropPodClass == nullptr) return false;                       <- bail 1
pod = LokiGameplay::SpawnPoolableActorFromClassDeferred(...);
if (pod == nullptr) return false;                                    <- bail 2
```
**[M] Bail 1 is RULED OUT** — `ship.TeamDropPodClass @0x478` re-read *after* the call still holds
`BP_DropPod_Tutorial_C`. ⇒ by elimination the return came from **bail 2: the pooled spawn returned
null.**

★★ And the session log names a cause:
```
[00.37.23] LogActorPooling: Display: Adding .../BP_DropPod_Tutorial_C to list of poolable actors.   (x3 drop classes)
[00.39.36] LogActorPooling: Display: UActorPoolManager::PrimePools : Feature is not enabled, skipping.
```
⇒ **[M] the drop-pod classes ARE registered as poolable, and the pool manager's priming is SKIPPED
because the feature is not enabled.** Registration happened; priming did not.

⚠⚠ **GRADE THIS HONESTLY — IT IS A LEAD, NOT A CONCLUSION. [I], and the gap is specific:** nobody has
shown that `SpawnPoolableActorFromClassDeferred` *requires* the pool feature to be enabled. A
well-written helper falls back to a normal `SpawnActor` when pooling is off, in which case the
disabled pool is a red herring and bail 2 has some other cause. **The chain
"pooling disabled -> pooled spawn returns null -> SpawnDropPodForTeam returns false" is plausible and
unproven at its FIRST link.**

⚠ Also unmeasured: `GetTeamDropLeader` returns nullptr here (expected — `AuthSetSpawnTeamLeader` is an
empty fold), but that is read AFTER bail 2 in the decompile, so it cannot explain a `false`.

### 21.4 The cheapest next step, and it needs no launch if the world survives

**Call `LokiGameplay::SpawnPoolableActorFromClassDeferred` DIRECTLY** through the same ProcessEvent
route, with the same class (`BP_DropPod_Tutorial_C`) and transform, and read whether it returns null.
That converts S21.3's first link from [I] to [M] in one arm and localises the wall precisely:
 - **returns an actor** ⇒ pooling is a red herring; bail 2 has another cause; re-examine.
 - **returns null** ⇒ the pooled-spawn path is the wall, and the question becomes what enables the
   pool feature. Then chase the gate: it is **not** in the 44-entry `loki.*` cvar inventory
   (`tools/re/out/cvar_census_tuthero.txt`, 95 rows, **0** pooling entries) and **not** in the
   enum-toggle list (`game_feature_toggle_enum.txt`, 0 pooling hits), so it is something else —
   a config value, an ini, or a native default.
⚠ The static hunt for the gate stalled on coverage: the `PrimePools` / `Feature is not enabled`
UTF-16 literals exist at `.rdata 0x7F14B66` / `0x7F14B80` but have **zero `lea` xrefs and zero
pointer references** in `merged2` ⇒ **COVERAGE-BLOCKED, not absent.** Driving the path and re-dumping
(the S117 method) would decrypt it.

## 22. The pooled-spawn probe — is the disabled actor pool the wall?

**Date:** 2026-08-19. **BUILT, NOT FLOWN.** A client is booting for this experiment; nothing in this
section has touched a live process. Everything below is either a build fact (measured off the
artifacts) or a **pre-registered prediction**, and it is labelled as one or the other.

§21.4 asked for exactly one thing: convert §21.3's first link from [I] to [M] by calling
`ULokiGameplayStatics::SpawnPoolableActorFromClassDeferred` directly and reading whether it returns
null. This is that probe. **It answers one question and deliberately nothing else** — it does not
touch the phase, the plane, the ship, or any delegate, and it does not try to spawn a drop pod "for
real".

### 22.1 What was built

New run mode **`RM_POOLSPAWN` (enum 28)** in `tools/sigbypass-mod/tutorial_launch.cpp`, marker tag
**`[PS]`**. Variant table in `tools/sigbypass-mod/build.ps1`. Build with
`.\build.ps1 -Name tutorial_launch -Variant <v>` (the script refuses `-Variant` without `-Name`, and
a `-Variant` without it silently builds the default set while reporting success — S124's trap).

| variant | `.text` sha256 | `.text` size | `KSPARMS` | what it is |
|---|---|---|---|---|
| `poolspawn-readonly` | `68a369686870185a` | 129024 | 0x81 | **ZERO UFunction calls.** P0 resolve + BEFORE census + P4 AFTER census. The census's own null-delta control. **FLY FIRST.** |
| `poolspawn-ctrl` | `87e5fa023e0ec999` | 134656 | 0x181 | + P0c only. Answers "can this primitive dispatch on this thread and marshal a struct return", nothing about the pool. |
| `poolspawn-deferred` | `545cb94912e8c8fa` | 138752 | 0x187 | P1 alone (the headline) + control + censuses. One payload call. |
| `poolspawn-nondef` | `8f1e776f8e78558c` | 138240 | 0x199 | P2 alone (the non-deferred sibling). |
| `poolspawn-ref` | `151af52792cf9de8` | 144896 | 0x1E1 | P3 alone — establishes the class is spawnable in this world at all. |
| **`poolspawn`** | **`d3e1ffb9623f6352`** | 148992 | 0x1FF | **THE CANDIDATE.** Full ladder P0 + P0c + P1 + P2 + P3 + three mini-censuses + P4. |
| `poolspawn-collmatch` | `365fce2091dbddb0` | 148992 | 0x1FF, `KSPCOLLISION=2` | Confound-removal arm (see §22.5). |
| `poolspawn-compwco` | `6ed1a3c3d0165e13` | 148992 | 0x1FF, `KSPWCO=2` | WorldContextObject = the DropPlane component. ⚠ two-variable against P3 by construction. |

**All 8 `.text` hashes are DISTINCT.** ⚠ **Three of them (`poolspawn`, `-collmatch`, `-compwco`)
share the byte-identical `.text` SIZE 148992** — across the 14 artifacts rebuilt this session there
are **14 distinct hashes but only 12 distinct sizes.** A size comparison would have declared three of
these arms the same build. *Diff `.text`, never size.*

**Regression gate and neighbours, all rebuilt from the edited source and all reproducing their
pre-edit hashes byte for byte:**

| variant | `.text` sha256 | |
|---|---|---|
| `play` | `9bc10a4552c596e1` | **THE GATE — unchanged** |
| `droppod` | `9e8148635b2ddcf5` | unchanged |
| `dropmarkers` | `d3c07c32f7a699eb` | unchanged |
| `cheatmgr` | `7f89f671592824ac` | unchanged |
| `phaseladder` | `8d1821f8c0ddbd63` | unchanged |
| `dropplane` | `a0f6f2e54b5ac01e` | unchanged |

That `play` is byte-identical is also the empirical proof that the four insertions into shared
surfaces (the enum, the forward declaration, the `OnPI` branch and the Worker branch) are
dead-code-eliminated for every other mode.

Every variant carries `-DKFSNAME=\"\"` (swap **every** BP UFunction — `ReceiveTickClient` is not
dispatched everywhere; the first RM_PHASELADDER flight starved on exactly that), plus
`-DKFRAMEINIT=1 -DKFAULTINFO=1 -DKOUTPARMRET=1`. Other knobs: `KSPPODCLASS` (default
`BP_DropPod_Tutorial_C`), `KSPORIGIN`, `KSPWCO`, `KSPCOLLISION`, `KSPSCALEMETHOD`, `KSPFORCE`,
`KSPSTEPMS` / `KSPSETTLEMS` / `KSPMODEHOLDMS` / `KSPMINICENSUS`.

### 22.2 Safety statement — measured off the artifacts, not asserted

- **NO module-image write is reachable from this mode.** It arms exclusively on the heap
  `UFunction.Func` swap (`FsArm` / `FsHold` / `FsDisarm`). With `KFUNCSWAP=0` it prints a refusal and
  returns 7 rather than falling back to `InstallHook()` — the standing 5-byte `ProcessInternal`
  `.text` patch measured at **10/10 armed-window deaths vs 3/36 with no module-image write**
  (S112, Fisher p = 0.00000008).
- **Import-table evidence [M]:** `FlushInstructionCache`, `VirtualAlloc`, `VirtualFree` and
  `WriteProcessMemory` are **ABSENT from all 8 artifacts' import tables** ⇒ `SafeWrite` / `BuildHook`
  / `InstallHook` are linker-eliminated. **Positive control: `tools/sigbypass-mod/tutorial_launch_fo.dll`
  imports all three (`FlushInstructionCache`, `VirtualAlloc`, `VirtualFree`) — PRESENT.** So the
  absence is a property of these builds, not of the check.
  ⚠ `VirtualProtect` survives in all of them (it is reachable only from `PatchLoginVtables`, which has
  zero call sites file-wide, and from `KWPROBE`); it is present in the already-flown `droppod` and
  `dropplane` artifacts too, so the import profile is **byte-for-byte the same set** as builds this
  project has already flown safely — no new capability is introduced.
- **`verify_dll.py` PASS on all 8**: no `__CxxFrameHandler3/4`, no `_CxxThrowException`, no dynamic
  CRT. SEH only.
- **No memory pokes of any kind.** Every effect is a UFunction call.
- **No hardcoded ASLR addresses.** Class, CDO, both UFunctions, the pod UClass, the GameMode, the
  DropPlane component, the hero, the `TrainingStart`-tagged actor, `RootComponent`, `AttachParent`,
  `Tags`, and **every parameter offset, size and type** are resolved by name at runtime. Each
  resolver enumerates, prints every candidate, and **refuses on ambiguity** rather than taking the
  first match.
- **`poolspawn-readonly` genuinely makes ZERO UFunction calls**, re-verified after the fixes below:
  the only three call sites in the whole mode are P0c (`KSPARMS` bit 8), `SpCallPooled` (bits 1 and 3)
  and `SpawnActorCls` (bit 5) — mask **0x12A**, which is what the readonly build clears. Everything
  else on its path (`SpFindUnique`, `SpGradeFn`, `PdWalkParams`, `ParamOffset`, `PhPickGameMode`,
  `SpPickComp`, `PdFindOrigins`, `ActorLoc`, `SpRootAttached`, `GcAlive`) is pure `ReadProcessMemory`.
  ⚠ This is the claim S126 shipped falsely for `droppod-readonly` (bit 6 ran ungated while both the
  build script and the marker advertised zero calls), so it is re-derived here rather than inherited.

### 22.3 Fixes applied by the finalizer before any of this shipped

Seven defects were found in review and **all seven are fixed in the artifacts above** — the hashes in
§22.1 are post-fix. Two mattered:

1. **P3 asserted a property the code never checked.** `SpawnActorCls` passes its own `g_gm2`
   (`FindInstByClass("GameMode_Tutorial", …)` — a **substring** match that takes the **first** hit
   with no enumeration and no refusal: the class-lookup blind-spot family, sixth member) while P1/P2
   pass `g_spWco` (`PhPickGameMode`, enumerate-and-refuse). The two were never compared, yet the log
   printed *"the SAME object P1/P2 used"* — and on `poolspawn-compwco` that sentence is **false by
   construction**, because there `g_spWco` is the DropPlane *component*. Now: the two are compared,
   the result is printed as `sameWCOasP1P2=1|0|-1`, and **every verdict that leans on P3 carries an
   explicit QUALIFIED marker when they differ.**
2. **P3's parameter offsets were unverified hardcoded fallbacks.** `ResolveSpawnSeq` overwrites
   `g_oBWorld/g_oBClass/g_oBXform/g_oBColl/g_oBRet` and `g_oFActor/g_oFXform/g_oFRet` **only when
   `ParamOffset` succeeds**, so a *partial* resolve failure leaves stale constants and the arguments
   land at the wrong offsets. P3 would then produce nothing **for an instrument reason**, and the
   verdict chain would have read that as *"this class cannot spawn in this world"* — sending a
   successor to re-stage a world that was never the problem. All 8 borrowed offsets are now
   **re-derived by name and printed in a table**, and the arm **refuses** on any mismatch. (P1/P2
   already had the equivalent guard; P3 had none.)

The other five: the **abort reason is now latched** (five different `SpResolve` failures previously
collapsed into one generic verdict that named the wrong cause); a **P0c disagreement on an
attached root is reported as an instrument mismatch, not a control failure** (`K2_GetActorLocation`
returns the *world* location while the RPM reference reads `RelativeLocation` — equal only for an
unattached root — and the control-actor picker now *prefers* an unattached, non-origin actor and
prints `rootAttached` for whatever it picks); the **SANITY check uses one threshold** quoted in both
places (it tested `0x50`, claimed `0x60`, and refused at `0x58`); the **census-cost comment** now
states that three of the five ~200k-object sweeps run on the **game thread**, not just the two
worker-thread ones; and the mode was **retagged `[SP]` → `[PS]`** because `[SP]` already belongs to
`RM_SPAWNPOSSESS`, which is *step 3 of the very staging recipe this probe is injected into*.

### 22.4 PRE-REGISTERED PREDICTIONS — four outcomes, four different meanings

Written down before the flight. **The census delta is the result; a returned pointer is
corroboration.** "The call returned ok" is never a result (S114 got `console 'LogLoc' ok` from a call
that never reached a PlayerController).

| # | observation | what it means |
|---|---|---|
| **(a)** | **P1 returns a LIVE ACTOR** | **Pooling is a RED HERRING.** `SpawnPoolableActorFromClassDeferred` does **not** require the pool feature; `PrimePools : Feature is not enabled` does **not** explain S127's bail 2; **§21.3's chain is REFUTED at its first link** and bail 2 has another cause entirely. Re-open §21.3. |
| **(b)** | **P1 null + P2 (non-deferred) returns an actor** | The **DEFERRED PATH SPECIFICALLY** is the wall — same world, same class, same transform, same WorldContextObject. A pool that could serve neither would have sunk P2 too. The gate is not "the pool" as such. |
| **(c)** | **P1 and P2 both null + P3 spawns fine** | **THE POOL IS THE WALL.** The class *is* spawnable here, so the null belongs to the pooled path, and §21.3's chain is **SUPPORTED at its first link for the first time.** The target becomes *what enables the pool feature* — not a `loki.*` cvar (0 of 44) and not a `ELokiGameFeatureToggle` (0 hits), so a config value, an ini, or a native default. |
| **(d)** | **P3 also fails** | **NOTHING here is about pooling.** The class cannot spawn in this world at all right now; the pool is **neither implicated nor exonerated**. That is a STAGING statement — ⚠ *and only after* the P3 offset table and the P3 WorldContextObject line are read, because if P3 failed for an instrument reason it is not a statement about the world either. |

A fifth reading exists and is **not** in the table because it is not an outcome about the pool:

- **P1's return SENTINEL SURVIVES (`0xA5` intact in both the params slot and `RESULT_DECL`)** ⇒
  **nothing wrote a return; the callee did not complete.** This is NOT "the pooled spawn returned
  null" and says nothing about the pool. That distinction is what carried the entire S127 result, and
  both slots are pre-filled so it stays available here.

**THE POSITIVE CONTROL THAT PROVES THE ARM RAN: P0c must reach `STRONG PASS`.**
`K2_GetActorLocation()` on a **non-origin, unattached** actor, cross-checked against a pure-RPM read
of the same actor's `RootComponent->RelativeLocation`. Without it, *"the pooled spawn returned null"*
and *"the primitive never dispatched on this thread"* read identically.
⚠ **A `WEAK CONTROL (origin)` is NOT a pass** — two zeros agreeing prove nothing (S126's C0c made
exactly that error and printed AGREED for a call it never read).

**THE SITTING IS VOID IF:**
- `[FS]` prints **`ZERO TARGETS SWAPPED`** — the ladder never advances (ignore its RM_PLAY wording and
  its `play_hold300.dll` suggestion; for this mode it means nothing ran);
- **P0c does not reach `STRONG PASS`** (`verdict != 1`) — the mode says so itself and refuses to
  interpret P1;
- the **live-FProperty SANITY check fails** — an `ObjectProperty`/`ClassProperty` must read
  `ElementSize == 8` and the `FTransform` slot at least `0x58`. If a pointer reads **1**, `FPROP_ELEMSIZE`
  is reading `ArrayDim` again (the S126 defect) and **no arm dispatches**;
- **`poolspawn-readonly` reports a non-zero DropPod delta** — the instrument is noisy and **no other
  variant's delta means anything**;
- the ladder does not reach step 8 (**exit code 9**, and the marker says so).

### 22.5 Two STATED confounds — read these before blaming the pool

1. **Collision handling.** `SpawnActorCls` (P3) hardcodes `CollisionHandlingOverride = 2`
   (`AdjustIfPossibleButAlwaysSpawn`) and is **shared code compiled into `play`**, whose `.text` hash
   is a hard regression gate — so it is *not* edited. P1/P2 pass the functions' **declared default 0**
   (`Undefined`). ⇒ if outcome **(c)** appears, **re-fly `poolspawn-collmatch` (`KSPCOLLISION=2`)
   BEFORE concluding anything about the pool.** That arm removes the confound instead of arguing
   about it.
2. **WorldContextObject.** As above (§22.3 item 1). On the default `KSPWCO=0` the auto pick is the
   GameMode, so the two *should* agree — and if the log says they do not, then `PhPickGameMode` and
   `FindInstByClass` disagree about which GameMode is live, **which is itself the finding.** On
   `poolspawn-compwco` they differ by construction and the qualifier always fires.

### 22.6 What this probe leaves in the world — nothing is undone

⚠⚠ **This mode SPAWNS REAL ACTORS and does not clean up. There is no undo.** Each of P1, P2 and P3
can leave a live `BP_DropPod_Tutorial_C` in `LVL_Tutorial`; the full `poolspawn` ladder can leave up
to three. The marker says so on **every** exit path, including the abort paths. **Recovery = restart
the client.** No memory was poked and no module image was written, so there is nothing else to revert.

⚠ The staged world may **already** contain drop actors — a half-constructed
`BP_DropPlane_Straight_Tutorial_C` from a plane-creating probe (S125/S127 both produced one),
plus the pooled-actor registrations. `DpCensus` latches the BEFORE set and marks NEW objects, so a
non-zero baseline is **expected and tolerated**; only the DELTA is read. P3 runs **last** so it cannot
contaminate P1/P2's columns, and its census column is labelled separately.

⚠ P3 also makes the client believe an actor exists that the game did not create. That is inherent to
having a non-pooled reference at all, and it is why P3 is the last thing the ladder does.

### 22.7 Operator sequence

The client is already booting and `forceTutorialMatch` is `true`, so the world stages itself. From an
**ELEVATED PowerShell**:

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_poolspawn_readonly.dll -Label s128-F0 -AllowStale
# then, on a fresh staged world:
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_poolspawn.dll          -Label s128-F1 -AllowStale
```

⚠⚠ **`-AllowStale` IS REQUIRED, and it is not a shortcut.** Editing `tutorial_launch.cpp` moves
`fo`'s and `sp`'s `.text` too, because they are built from the same file. The **deployed** copies
(`tools/sigbypass-mod/tutorial_launch_fo.dll`, `tutorial_launch_sp.dll`) are the known-good ones that
have staged successfully all session. **Do NOT swap staging infrastructure mid-experiment** — the
staging chain is the control, and re-building it is a second variable in an experiment that is
supposed to have one.

⚠ Expected yield is **~2 armed windows per 4 launches** (FK-31: ~25 % of launches die during staging
with only `gft`+`fo` resident). **Budget on armed windows reached, never on launches.**

Read the marker at `docs/tutorial-launch-marker.txt` — but note that `Marker()` opens `CREATE_ALWAYS`,
so **every injection truncates it** (FK-25). `fk24-stage.ps1` copies it off after each stage into
`docs/fk24-stage-<label>-<n>-<shim>.txt`; the probe's own output is the `-4-probe-*` file.

### 22.8 Honest status

**READY TO FLY, NOT FLOWN.** The single most likely surprise is the one that closed Route C in S127:
`Func@+0xE0` reading `0x0`. This is a **native static**, so a real thunk is expected — but that is an
expectation, not a measurement. The mode **grades** the live `UFunction` and dispatches on what it
read (real native thunk → `CallNativeGuarded`; `Func == ProcessInternal` → `CallBPGuarded`; a
universal fold or NULL → **REFUSE**, with the reason named), so a null `Func` produces a clean
measurement rather than a fault — **and that refusal would itself be the headline.**

Known-unmeasured, carried forward:
- **`ESpawnActorScaleMethod == 1` (MultiplyWithRoot) is [I]**, from stock UE5 numbering. What is read
  *live* is the property's UEnum **name**, printed beside the value; a `-` there is an **instrument
  gap**, not agreement. A wrong byte cannot sink the call (flat params block, not a JSON enum string,
  so the S118 `ELokiActivityState` failure mode does not apply) but could change spawn scaling.
- **Parameter names are assumed to match `binds_members.csv`** (`WorldContextObject`, `ActorClass`,
  `SpawnTransform`, plus a name containing `collision` / `scalemethod`). A mismatch prints UNBOUND and
  the arm refuses — visible, not silent, but it costs the sitting. The bind lines are the readout.
- **P0c proves the primitive dispatches on an ACTOR instance, not on a CDO.** A static UFunction
  called on a CDO is a slightly different shape and there is no known-safe zero-input static on
  `ULokiGameplayStatics` to control it with. The return sentinel partially covers the gap.
- **A pooled spawn returning an actor does not by itself prove the pool was bypassed** — it could be
  serving from a pool populated some other way. Outcome (a)'s claim is deliberately scoped to *the
  first link*, nothing wider.

---

## 23. FLOWN — THE ACTOR POOL IS THE WALL. `SpawnPoolableActorFromClass{,Deferred}` return NULL while the SAME class spawns fine unpooled

**Date:** 2026-08-19/20, PID 32420, staged `LVL_Tutorial`. Builds `poolspawn` (`.text d3e1ffb9623f6352`)
then `poolspawn-collmatch` (`365fce2091dbddb0`). Zero `.text` writes, zero crashpad handoffs on this
client. Evidence: `docs/fk24-s128-poolspawn-RESULT.txt`, `docs/fk24-s128-collmatch-RESULT.txt`,
`docs/Loki-s128-poolspawn.log`.

### 23.1 The result

Both pooled entry points are **native statics with real thunks** — unlike the Angelscript
`SpawnDropPodForTeam` (S19, `Func == 0`), these dispatch through the S55 direct-`Func` primitive:
```
SpawnPoolableActorFromClass          Func@+0xE0 = 0x7FF7BDA4EEE0 (rva 0x537EEE0)  NATIVE
   FunctionFlags 0x04C22401 Static | PropertiesSize 144 | NumParms 8 | ReturnValueOffset 0x88
```
| arm | call | return | DropPod delta |
|---|---|---|---|
| **P0c** | `K2_GetActorLocation` on a NON-ORIGIN actor | `(-3206.4,5070.5,100.0)`, RPM ref identical | **STRONG PASS**, 0.00 uu on \|ref\|=8377 |
| **P1** | `SpawnPoolableActorFromClassDeferred` | **NULL** | **+0** |
| **P2** | `SpawnPoolableActorFromClass` (non-deferred) | **NULL** | **+0** |
| **P3** | ordinary `BeginDeferredActorSpawnFromClass` + `FinishSpawningActor`, SAME class | **actor `0x1EB8530C080` `BP_DropPod_Tutorial_C`** | **+2** |
```
bucket    BEFORE afterP1 afterP2 afterP3   AFTER     dP1     dP2     dP3
DropPod        2       2       2       4       4      +0      +0      +2
```
★ **The `0xA5` sentinel is what makes the nulls readable**: `paramsSlot 0xA5 INTACT, RESULT_DECL
OVERWRITTEN` ⇒ **a return really was written, and it is NULL** — not "nothing ran", not a fault.

### 23.2 ★ The pre-registered confound was flown and ELIMINATED

The probe declared its own confound *before* the flight: `SpawnActorCls` (P3) hardcodes
`CollisionHandlingOverride = 2 (AdjustIfPossibleButAlwaysSpawn)` while P1/P2 passed `0 (Undefined)`,
so "pooled vs unpooled" was confounded with "collision 0 vs 2", and it instructed:
*"re-fly `poolspawn-collmatch` (KSPCOLLISION=2) BEFORE blaming the pool."*
**Flown. With `collision=2` on P1/P2 — byte-identical to the value the working path uses — BOTH
POOLED SPAWNS STILL RETURN NULL.**
⇒ **[M] the only surviving difference between "spawns an actor" and "returns null" is POOLED vs NOT.**

### 23.3 What this settles, and what it does not

**[M] SETTLED — the first link of S21.3's chain, which was explicitly unproven:**
*"`SpawnPoolableActorFromClassDeferred` returns null in this world, while the same class spawns
normally."* S21.3 recorded that link as [I] and named it as the gap; it is now measured, with the
class-spawnability precondition (P3) and the collision confound both closed.
⇒ **`SpawnDropPodForTeam`'s `false` (S127) is bail 2, caused by the pooled spawn declining.**

**[I] STILL INFERRED — that `PrimePools : Feature is not enabled` is WHY.**
> ⚠⚠ **REFUTED BY S130 (2026-08-20) — see §25 and `docs/s130-actor-pool-gate-settled.md`.**
> An unprimed pool **cannot** produce this NULL: the acquire uses `TMap::FindOrAdd` (never null) and on a
> pool miss takes a shipped fallback to a normal `UWorld::SpawnActor`. The [I] grade was correct and the
> inference was wrong. Read §25 before using anything below this line.
 The log line and the null
are consistent and no other cause is in evidence, but nothing yet reads the pool manager's gate and
shows it is the branch taken. Two facts could still break it: the helper might decline for an
unrelated reason (no free pooled instance, a subsystem not initialised on a client), and the
`PrimePools` / `Feature is not enabled` UTF-16 literals at `.rdata 0x7F14B66`/`0x7F14B80` have **zero
`lea` xrefs and zero pointer references** in `merged2` ⇒ **COVERAGE-BLOCKED, not absent** — the gate
has not been read, only named.

**⇒ FK-22's blocker chain, current state:**
markers (refuted, S0-S3) → phase (solved, S14) → subscription (measured dead, S15/S16) →
`SpawnPlane` position computation (faults on unstreamed markers, S17/S21.1) →
**pooled spawn declines (MEASURED, here)** → *why the pool declines* (**the live frontier**).

### 23.4 Next

**Read the pool manager's gate.** `UActorPoolManager` is a live subsystem in this world; find its
instance, read the flag `PrimePools` tested, and identify what sets it. The gate is **not** in the
44-entry `loki.*` cvar inventory (`cvar_census_tuthero.txt`, 95 rows, 0 pooling hits) and **not** in
the enum-toggle list (`game_feature_toggle_enum.txt`, 0 pooling hits), so it is config, ini, or a
native default — and if it is any of the first two it is **backend/ini-drivable with no injection at
all**, which is this project's cheapest class of fix.
★ The literals are coverage-blocked, so **drive the path and re-dump** (the S117 method: executing code
forces `.text` decryption) to make the gate readable offline.
⚠ And keep P3 in mind as an independent lever: **the ordinary spawn path WORKS on this exact class**
(`dP3 = +2`). If the pool cannot be enabled, hand-spawning the pod and wiring it may bypass the pool
entirely — `InitializeDropPod` is a separate, already-graded call.

### 23.5 State left behind

The world contains **2 extra `BP_DropPod_Tutorial_C` actors** created by P3, plus whatever the
collmatch re-run added. There is **no undo**; recovery is a client restart. Any later census in that
world must not assume a clean baseline.

---

## 24. THE POOL GATE IS LOCATED — a virtual on `UActorPoolManager`, slot `0x2D0`

**Date:** 2026-08-20. Offline, against a fresh live dump (`dumps/s129-poolgate/`, `.text` 52.9 %
readable) taken from PID 32420 **while the pooling code was decrypted** — the S117 lever: driving a
path forces `.text` decryption, and `PrimePools` had run in that process at `01:59:37`.

### 24.1 The gate, machine-verified

`UActorPoolManager::PrimePools` = **`0x3356000`**, 1,284 B (extent from the recovered `.pdata`).
The disabled-path bytes, decoded from a known instruction boundary:
```
0x33560C5   49 8b 06              mov  rax,[r14]              ; r14 = this (UActorPoolManager)
            49 8b ce              mov  rcx,r14
            ff 90 d0 02 00 00     call qword ptr [rax+0x2D0]  ; <== THE GATE. virtual, slot 0x2D0 (index 90)
0x33560CB   84 c0                 test al,al
            75 25                 jne  +0x25                  ; TRUE  -> proceed with priming
            80 3d .. .. .. .. 04  cmp  byte ptr [rip+..],4     ; log verbosity
0x33560DC   48 8d 15 3d ea bb 04  lea  rdx,[rip+0x4BBEA3D]     -> 0x7F14B20
                                  [0x7F14B20] = 0x7FF7C05E4B40 -> rva 0x7F14B40
                                  = 'UActorPoolManager::PrimePools : Feature is not enabled, skipping.'
```
**[M] Every link machine-verified**: the `lea` displacement resolves to the pointer SLOT the xref
named, the slot dereferences to the string RVA, and that string is byte-for-byte the log line observed
live. ⇒ **the branch that produced our log line is `if (!this->vtable[0x2D0]()) { log; return; }`.**

⇒ **The pool feature is gated by a BOOLEAN VIRTUAL on `UActorPoolManager`, not by a cvar and not by a
feature-toggle key.** That is consistent with, and explains, the two earlier negatives: 0 pooling hits
in the 44-entry `loki.*` cvar inventory and 0 in the 149-member enum-toggle list.

### 24.2 ⚠ Two instrument artifacts, both MINE, both in this one hunt

**(a) I searched for the SUBSTRING's address instead of the enclosing STRING's start.** The literal
begins at `0x7F14B40`; I repeatedly scanned for `0x7F14B66`, where the word "PrimePools" happens to
start inside it, and got **zero xrefs three times** — from `merged2`, then from a fresh live dump, then
from a widened scan. I was one keystroke from recording "COVERAGE-BLOCKED" as a property of the game.
★★ **`strxref.py`'s own output had warned about the mirror-image of this defect in the same session**
(*"the 'feature toggles were not ready' RVA is 88 bytes INTO a longer string; an exact-start-only
lookup reports 0 refs, the enclosing-string lookup reports 4"*). I read that block, then committed the
inverse error. ⇒ **A reference points at a string's START. Search the enclosing string, never an
interior offset — and when a scan returns 0, suspect the QUERY before the coverage.**

**(b) My hand-rolled `lea` scan matched only `48 8D` (REX.W).** `UE_LOG` passes arguments in
`rcx/rdx/r8/r9`, and `lea r8,[rip+…]` encodes as **`4C 8D`**. Widening to `48/49/4C/4D` was necessary
but NOT sufficient — defect (a) was masking it — so **the widened scan still returned zero and looked
like confirmation of the wrong conclusion.** ⇒ **two independent blind spots in one instrument produce
a null that survives one fix and reads as corroboration.**
★ Both fell instantly to the project's OWN tool (`tools/strxref/strxref.py`, `--dump <new image>`,
`find` then `xref`), which found it as `refs=1` via a `ptr-tbl` slot — a reference class my byte scan
was never going to see, since the code `lea`s the SLOT, not the string.
⇒ **Use `strxref.py` for string→code work in this image. Hand-rolled scans have now failed on: interior
offsets, REX encodings, and pointer-table indirection.**

### 24.3 Where this leaves FK-22

markers (refuted) → phase (solved) → subscription (dead) → `SpawnPlane` position computation (faults
on unstreamed markers) → pooled spawn declines (measured, S23) → **the pool gate is a bool virtual at
`UActorPoolManager` vtable+0x2D0 (located, NOT yet read)**.

**Next, and it is now a small, bounded job:**
1. **Resolve slot `0x2D0`** on the live `UActorPoolManager`'s vtable and disassemble the target. It is
   a `bool(void)` — expect it to read a config value, a subsystem flag, or a member byte.
2. If it reads a **member byte**, that is a DATA poke on a live object — this project's safest measured
   write class (nothing 0/22 · bytecode 0/9 vs standing `.text` 7/8) — and `PrimePools` can then be
   called directly to prime the pools.
3. If it reads **config/ini**, it is drivable with **no injection at all**.
4. ⚠ Either way, priming is not obviously required for a *single* spawn: S23 measured the pooled
   helpers returning null, but nothing yet shows they consult the same gate. **Check whether the pooled
   spawn path calls slot `0x2D0` too**, or fails for want of a primed pool — those are different fixes.
★ And the independent lever from S23 still stands: **the ordinary spawn path WORKS on this exact class**
(`dP3 = +2`), so bypassing the pool entirely remains open.

### 24.4 Slot `0x2D0` — ATTEMPTED, NOT RESOLVED (be precise about which)

**What was established [M]:**
- **`PrimePools` is NOT virtual** — a full-image scan for qword pointers to `IB+0x3356000` returns
  **0**, so no vtable contains it. It is an ordinary method that calls a virtual on its own `this`.
  ⇒ the vtable cannot be recovered "for free" by finding PrimePools inside one.
- **There is a Loki subclass: `ULokiActorPoolManager`** (`.rdata 0x0886F320`, refs=1, registrar
  `0x52975D0`, 174 B), alongside engine `UActorPoolManager` (`0x07DDDB60`, registrar `0x32A8570`).
  ⇒ **slot `0x2D0` on the LIVE object is probably the Loki OVERRIDE, not the engine base.** Resolving
  the engine class's vtable and reading its slot 90 would answer the wrong question.
- ★★ **`ActorPoolManagerPrimingConfig`** exists (`.rdata 0x07DDCB20`, refs=1, registrar `0x32A7AC0`,
  55 B) — **a config class in the pooling module.** This is the strongest lead for what the gate reads:
  if it is a `UDeveloperSettings`-style config, the feature is **ini-drivable with no injection at all**,
  which is this project's cheapest fix class. **It has not been read.**
- The source path is in the image: `…\Engine\Source\Runtime\Engine\Classes\ActorPooling\ActorPoolManager.cpp`
  (`.rdata 0x07F14A40`) ⇒ pooling is **engine-layer with a Loki subclass**, not pure Loki.

**What FAILED, and why it is not a negative result:** the offline
class-name → `GetPrivateStaticClass` → `InternalConstructor` → `lea rax,[rip -> vtable]` route (the
S106b technique) did not land. `0x52975D0`'s code-`lea` targets are `0xF7EC20` (a universal fold, ×2),
`0x11A5FA0`, `0x32A8570` (the engine registrar) and `0x5299D00`; disassembling `0x5299D00` shows
`mov rcx,[rcx]; test rcx,rcx; jne …` repeated — a **thunk region containing several small functions**,
not a single constructor, so the expected vtable `lea` is not at its head. **This is a route not yet
walked correctly, NOT evidence that the vtable is unfindable.**
⚠ The live route — read `[obj]` off a live `ULokiActorPoolManager` and take `+0x2D0` — is unambiguous
and was prepared, but the client had **exited cleanly (0 crashpad handoffs)** before it could run.
**It needs one relaunch and about a minute.**

**Next, in order of cost:**
1. **Relaunch, stage, and read the vtable off the live object** (RPM only; identify the instance by
   walking `GUObjectArray` and matching the class name, or by any object whose vtable slot `0x2D0`
   is a short `bool()` in the pooling code band). Then disassemble that target — that IS the gate.
2. **In parallel, offline: read `ActorPoolManagerPrimingConfig`** (registrar `0x32A7AC0`). If it is a
   config object the gate consults, the enabling lever may need no injection at all.
3. ⚠ Still unchecked and it changes the fix: **does the pooled SPAWN path consult the same gate**, or
   does it merely fail for want of a primed pool? S23 measured the helpers returning null; nothing yet
   ties that to slot `0x2D0`. "Priming never ran" and "the helper declines" are different repairs.


---

## 25. S130 — THE POOL GATE IS NAMED, AND §23's SUSPICION IS REFUTED: THE POOL IS NOT THE BLOCKER

**Date:** 2026-08-20. Offline; zero launches, zero injections, zero `.text` writes.
**Primary evidence: `docs/s130-actor-pool-gate-settled.md`** — that file governs; this is the summary.
Six adversarially-verified decode lanes + a session-lead thread; raw JSON in `scratchpad/s130/`.

### 25.1 The gate, named [M]
`ULokiActorPoolManager` vtable slot 90 (`.rdata 0x08877A80 + 0x2D0 = 0x08877D50` → `0x56363F0`,
fold multiplicity **1**) returns
`Cast<ALokiGameState>(GetWorld()->GameState)->bSupportsActorPoolPriming` — a plain
`UPROPERTY(EditDefaultsOnly, AdvancedDisplay) bool` at **`ALokiGameState + 0x898`**.
Named from the UHT `FBoolPropertyParams` at `.rdata 0x08983A50` whose **`SetBitFunc 0x053800D0` is
`mov byte ptr [rcx+0x898], 1; ret`** (multiplicity 1), owned via `PropPointers` index **106 of 155**.
It is the **only** bool UPROPERTY at that offset image-wide (13,156 Bool records swept).
`UWorld+0x258 = UWorld::GameState` [M], from `UGameplayStatics::GetGameState` (`0x38047F0`).
The engine base's slot 90 is `0x0B9E1F0` = `mov al,1; ret` — a **26,444-way fold**, so the *slot*
returns true and the *address* names nothing.

### 25.2 Why it is false: a shipped Blueprint class default [M]
C++ ctor sets it TRUE (`.text 0x05676F10 c6 87 98 08 00 00 01`), and
`tools/extractor/out/bpdump_BP_LokiGameState_Tutorial_PROPS.txt:52` serializes
`bSupportsActorPoolPriming = False`. The tutorial world runs `BP_LokiGameState_Tutorial_C` (S124).
Family control: 3 of 6 GameState Blueprints override it and **all three override to False**
(`_Tutorial`, `_PvE_Holdout`, `_FFA`); the other three inherit `true`.
⇒ **the pool is off in the tutorial BY DESIGN, in data.**

### 25.3 ⚠⚠⚠ THE CORRECTION: an unprimed pool cannot return NULL [M]
* the pool lookup `0x334E7A0` is a **`TMap::FindOrAdd`** — one `ret`, every path returns
  `MapData + idx*0x28 + 8`, inserting on a miss. **Never null.**
* a pool miss falls to a shipped fallback — `.rdata 0x08B06440 U 'Failed to find an actor in the
  pool for %s, spawning a new instance from scratch.'` — then `0x5648E48 call 0x39C3DB0`
  = `UWorld::SpawnActor`, and returns the fresh actor.
⚠ the fallback's log **emit is stripped** (`0x5648D6F` targets the `ret 0` fold `0x00F7EC20`,
4,972 call sites), so **its absence from the logs proves nothing** — and indeed it occurs 0 times
in the 69-file corpus.
⇒ **`SpawnDropPodForTeam`'s bail 2 is NOT caused by the pool being disabled. §23.3's [I] is dead.**

### 25.4 The pooled spawn never reads the gate [M]
Chain: thunk `0x537EEE0` → impl **`0x566FF50`** → `0x5647F00` → acquire **`0x5648050`**;
deferred thunk `0x537F1A0` → impl **`0x5670090`** → acquire **directly**.
Zero `call qword ptr [reg+0x2D0]` and zero calls to `0x56363F0` anywhere in the family, established
three times by disjoint methods. The gate has **exactly one** call site image-wide in this family:
`0x33560C5`, inside `PrimePools`.

### 25.5 What can actually return NULL — and the free receipt that narrows it
Nine edges reach the acquire's null epilogue `0x5648EA1`. C1–C6 are class-validity and are all
excluded by the S128 control that the same class spawns fine unpooled. The survivors are
**C7 `CDO->byte@0x6C != 0`** (`0x5648210`), **C8 `PoolMgr->GetWorld()==null`** (`0x5648D97`),
**C9 `UWorld::SpawnActor` returned null / was skipped because `rbx==0` at `0x5648E34`** (`0x5648E6F`).
★ **The non-deferred wrapper logs on NULL** — `.rdata 0x08B06390 'Failed to spawn actor of type %s.'`
— and it fired **twice** in the S128 flight naming `BP_DropPod_Tutorial_C`. Because it is emitted
strictly downstream of the outer preconditions, **[M] the World, the GameState, the
`IsA(ALokiGameState)` test and the pool-manager fetch ALL PASSED live.** The NULL is C7, C8 or C9.
⚠ [I, strong] the **deferred** arm's null is **silent** (it bypasses the wrapper) — 2 warnings
≈89 s apart = **one per injection**, not two. Do not read "no warning" as a deferred-arm result.
★ **Grep `Failed to spawn actor of type` before any further inference here.** The
`Feature is not enabled` line is ambient (68 occurrences / 69 files); this one is per-attempt.
★ S128's collision-confound elimination **STANDS**: the result files print
`Collision=2 (declared enum 'ESpawnActorCollisionHandlingMethod')`, `NumParms=8`, the enum name read
live off the FProperty.

### 25.6 Repair classes
**No ini route [M]** — `CPF_Config` clear; 0 of 155 `ALokiGameState` properties are config;
`ActorPoolManagerPrimingConfig` is a **USTRUCT with zero reflected properties and no UHT consumer**;
neither pool-manager UCLASS is a config class. Turning pooling ON is a **one-byte DATA poke
(`GameState+0x898 = 1`) plus a raw direct call to `PrimePools` (`0x3356000`)** — `PrimePools` is
**not reflected**, has **one caller** (`ALokiGameState::BeginPlay`, vtable slot 119) which has already
run and skipped, and performs **zero module-image writes**. Handles: `GameState+0x428` = the cached
manager, `+0x430` = its class.
⚠ **But none of that is known to fix FK-22**, because of §25.3.

### 25.7 The bypass has a FIFTH wall [M]
`ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` (impl **`0x55CD510`**) is a REAL body
that always fails: `0x55CD572` calls the stripped fold `0xF7EB50` (`33 c0 c3`) and bails into a
*"failed to get the round game mode"* log; its dead tail has **zero** external rel32 entries in three
images. Same wall on `AuthPlayerPreSpawnOnAddToPlane` (`0x55CD800`); `AuthPlayerEnterWorldNew` is an
empty fold. ⇒ **hand-spawning a pod yields a pod and no rider.**
⚠⚠ **SCOPE CORRECTION — §30 (S132): this is a statement about the MOUNT, not about the ride.**
The same component's `AuthPlayerDetachPlayerFromRidable` (impl `0x55CCCB0`) is REAL, touches no round
game mode, and was flown **six times**: hero out of the pod, un-hidden, collision and movement restored,
teleported to a chosen landing actor. **The exit half of the ride is drivable today.** See §30.
★★ **NEW GENERAL INSTRUMENT:** the `.data` `{name_ptr, exec_thunk, impl}` record table gives a
REAL/EMPTY verdict **without the code page being decrypted**, because the fold addresses are known
constants. **§2.5's 16 COVERAGE-BLOCKED keys are an instrument limit, not a fact, for at least 6 of
them** (the five `AuthPlayer*` entry points + `GetLandingTeleportLocation`, all on page `0x5456000`).
Re-running it over all 100 keys is free and unstarted.
⚠ **REFUTED sub-claim:** `AuthSetSpawnTeamLeader`'s flag feeds **three** Angelscript readers, not
one, and one of them (`QueueCrewForPodSpawn`) is on the leader-pod path. "The bypass avoids FK-1's
stubs" holds **only under `bIsTeamLeaderPod == false`** — and the route as transcribed from
`SpawnDropPodForTeam` passes `true`. This is the incomplete-enumeration failure mode § this very file
already recorded against a previous agent **on this exact function family**; it recurred.

### 25.8 Where FK-22 stands now
markers (**refuted**) → phase (**solved**) → subscription (**dead by construction**) →
`SpawnPlane` (**faults on unstreamed markers**) → `SpawnDropPodForTeam` (**runs, returns false**) →
bail 2 = the pooled spawn returns NULL → **⚠ NOT because the pool is disabled (refuted here)** →
**C7 / C8 / C9 inside the acquire `0x5648050`** → ✅ **C7 IS SETTLED — SEE §26.** It is
`AActor::bCanEverReplicate`, true on the drop pod, and it needed **no launch at all**. C8/C9 are now
**untested rather than excluded** — C7 returns before either is reached.

---

## 26. C7 IS SETTLED — THE NULL IS `bCanEverReplicate`, AND BAIL 2 IS EXPLAINED END TO END

**Date:** 2026-08-20. Offline; zero launches, zero injections, zero `.text` writes.
**Primary evidence: `docs/s130-actor-pool-gate-settled.md` §11** — that section governs.

§25.5 left three candidates (C7/C8/C9) and said C7 would cost one read-only RPM read. **It cost none.**

### 26.1 The answer, in one block [M]

```
C7  .text 0x0564820C   44 38 70 6c        cmp byte ptr [rax + 0x6c], r14b   (r14b = 0)
    .text 0x05648210   0f 85 8b 0c 00 00  jne 0x5648EA1                     (NULL epilogue)
                                          0x5648210 + 6 + 0xC8B = 0x5648EA1

  rax   = UClass[0x178] = ClassDefaultObject   [M] via UGameplayStatics::GetClassDefaultObject
                                                   impl 0x589BB40 -- an INDEPENDENT function
  +0x6C = AActor::bCanEverReplicate            [M] via AActor's own 114-entry PropPointers array
                                                   (FClassParams 0x07F227E0), 3 controls passing:
                                                   bAlwaysRelevant 0x68 / bHidden 0x68 / bEnablePooling 0x2D3
                                                   + independent confirmation in binds_members.csv:21044
  default = TRUE                               [M] AActor::AActor (0x3371800, 723 B, reached as
                                                   InClassConstructor 0x33703A0) does
                                                   0x03371841  mov byte ptr [rdi + 0x6c], 1
```

**Neither `BP_DropPod_Tutorial` nor `BP_DropPod` overrides it** (`bpdump @props`, populated dumps of
83 and N lines, so the absences are real inherits), and the cooked AssetRegistry effective value is
`bCanEverReplicate = true`.

⇒ **`SpawnPoolableActorFromClass{,Deferred}` refuses any class that can replicate, and the drop pod
can. The NULL is deterministic — primed or unprimed, on any machine, in any world.**

### 26.2 And the caller has no fallback — this IS bail 2

`tools/asdump/out/a/GameMode.DropPhase.LokiDropShip.as.txt:153`, inside `SpawnDropPodForTeam`:

```
v6 = LokiGameplay::SpawnPoolableActorFromClassDeferred(__WorldContext, this.TeamDropPodClass, ...);
if (v6 != null) {
    GetTeamDropLeader / InitializeDropPod / FinishSpawningActor / RemovePlayerFromPlane
    / AuthPlayerEnterWorldAttachedToRidable / MulticastOnDropPodLaunched / AddTeamDropEvent
}
```

There is **no else**. `TeamDropPodClass` is `BP_DropPod_C` (replicated).
⇒ **C7 → NULL → the entire body is skipped → `SpawnDropPodForTeam` returns false.** That is exactly
S127's measured bail 2, now explained **with no reference to the actor pool at all**.

### 26.3 ★★ The control that broke the first reading, then confirmed it

`bCanEverReplicate = true` on the drop pod looked like an immediate answer. **A control killed it:**
`BP_GemV2` — registered as poolable in the log, and the one class Angelscript explicitly opts into
pooling (`LokiGem.as:1129 this.bEnablePooling = true`) — **also reads `true`**. If C7 were as read,
gems could not be pooled either, which would make the subsystem inert: a far stronger claim than the
evidence supported.

The joint distribution over the cooked registry settled it (36,625 Blueprint assets scanned):
**pooling∧¬replicate = 80 · pooling∧replicate = 96 · ¬pooling∧replicate = 23 · rest untagged 5,362.**
⇒ **80 classes carry exactly the combination C7 requires**, so the gate is real *and satisfiable* —
and **every one of the 80 sampled is a cosmetic projectile visual** (`*_ProjectileCosmetics`,
`BP_Freeze_IceDart_*`, `BP_Flex_Blaster_*`, …). `ALokiHeroHeightIndicator`'s ctor shows the same
idiom in one place: `mov byte [rbx+0x6c], dl` (dl=0) **and** `mov byte [rbx+0x2d3], 1`.
⇒ **the pooled-spawn API is for non-replicated cosmetics; a drop pod is not a legal argument to it.**

### 26.4 ⚠ WHAT THIS DOES NOT ESTABLISH — and the one read that would

`LokiGem.as:181` has the **identical** `if (x != null) {...} else {}` shape, so this is not
drop-pod-specific: on the cooked values, gems fail the same gate. The game shipped, so one of these
is true and **none is measured**: (1) the runtime CDO byte differs from the cooked class default;
(2) gems/pods never spawn through this path in real matches; (3) the path is genuinely inert for
replicated actors in this build.
★ **One read discriminates:** `byte[CDO(BP_GemV2_C) + 0x6C]` on any live client with a world.
⚠ Until then: **[M] for the COOKED value, [I, strong] for the RUNTIME value. Do not collapse them.**

### 26.5 The repair, and what it costs

If the runtime read confirms `1`: poke **`CDO(BP_DropPod_Tutorial_C) + 0x6C = 0`** — one aligned byte
on a class default object, the safest measured write class (nothing 0/22 · bytecode 0/9 vs transient
`.text` 4/12 · standing `.text` 7/8), with a free readback — then dispatch `SpawnDropPodForTeam` via
the existing Route E (ProcessEvent slot 78).
⚠ It mutates a **class default**, so it affects every drop pod for the process lifetime and may break
the pod's replication. A→B→A with the DropPod census as the readout; not a default-set shim.
⚠ **C8 and C9 are now untested rather than excluded** — C7 returns before either, so nothing
downstream has ever been reached. Expect the next wall there.

### 26.6 Blocker chain, current

```
markers        REFUTED   (S124)
phase          SOLVED    (S124 -- one GoToPhase call self-drives to EGP_Combat)
subscription   DEAD      (S124 -- ServerOnly; the component is not in the invocation list)
SpawnPlane     FAULTS    (S124/S17 -- unstreamed markers)
SpawnDropPodForTeam runs, returns false  = bail 2
  └─ the pooled spawn returns NULL
       └─ NOT because the pool is disabled          <-- REFUTED S130 §25
       └─ because C7 rejects bCanEverReplicate=true <-- SETTLED S130 §26  ** YOU ARE HERE **
            └─ next: one live read of byte[CDO(BP_GemV2_C)+0x6C], then the one-byte CDO poke
            └─ then C8/C9, which have never been reached
```

---

## 27. FLOWN — THE RUNTIME CDO EQUALS THE COOKED DEFAULT. C7 IS [M] END TO END.

**Date:** 2026-08-20. **One clean `-NoHook` MENU launch, read-only RPM, zero injection, zero writes,
no tutorial staging.** PID 17736, base `0x7FF7C4050000`, 190,085 UObjects / 10,371 CDOs.
Probe `tools/re/cdo_flag_readout.py` (predictions written in before the run); raw output preserved at
`scratchpad/s130/evidence/cdo_flag_readout-s130-live.txt`.
**Primary evidence: `docs/s130-actor-pool-gate-settled.md` §12.**

**8/8 pre-registered predictions passed, 0 failures:**
`Default__Actor` **1** · `Default__LokiDropPodBase` **1** · `Default__LokiDropPod` **1** ·
`Default__BP_DropPod_C` **1** · `Default__LokiGem` **1** · `Default__BP_GemV2_C` **1** ·
`Default__LokiHeroHeightIndicator` **0** · `Default__BP_HeroHeightIndicator_C` **0**.

★★ **Two-sided control on `+0x6C`** (six read 1, two read 0, split exactly along the cooked value —
the probe's own check prints *"targets differ"*, and would have declared the run VOID had they all
matched). ★★ **`Default__Actor+0x6C = 1` is the disassembly and the live process meeting on one
byte** (`AActor::AActor 0x03371841 mov byte ptr [rdi+0x6c],1` predicted it). ★★ **An unpredicted
SECOND two-sided control appeared:** `Default__Actor+0x2D3 = 0` while every poolable class reads 1,
independently confirming `+0x2D3` is `bEnablePooling`.

⇒ **§26.4's hypothesis (1) — "something clears the byte at class load" — is REFUTED. The runtime
CDO byte IS the cooked class default. C7 FIRES, and the last [I] in FK-22's chain is now [M].**

⚠ **The leaf class was not read directly:** `Default__BP_DropPod_Tutorial_C` is **not loaded at the
menu**. Its value rests on (a) all three ancestors reading 1 live, (b) [M] it overrides neither flag
(`bpdump @props`, populated dump), (c) the cooked→runtime mapping now validated **3/3 in both
polarities**. **[M] for the ancestors and the mapping; the leaf is one inheritance hop of inference,**
and only staging a tutorial world would close it outright.

★ **A finding from the failed first attempt:** none of the four Blueprint CDOs was found on the first
run, against 10,371 live CDOs ⇒ **`LogActorPooling: Adding <X> to list of poolable actors` does NOT
load the class** — it is an AssetRegistry query against cooked tags. **"Registered as poolable" is not
evidence a class is loaded.** The probe printed `NOT LOADED (this is NOT a zero)` instead of reading
offset `0x6C` of a null, which is the only reason this surfaced as a finding rather than as four
confident zeros.

⚠ **Sharper, not solved:** gems read **1** too, so `SpawnPoolableActorFromClassDeferred` returns NULL
for them as well. The gem call site is `LokiGem.as:168 SpawnExtraGemWithTeam` — an ***extra***-gem
spawner — but **whether the game's primary gem path uses it is UNESTABLISHED** (no survey was done;
the name is suggestive, not evidence). For FK-22 it is moot: the pod's only route is
`SpawnDropPodForTeam`, which bails on the null with no else.

★ **Repair, now measurement-backed:** poke `CDO(BP_DropPod_C) + 0x6C = 0` (live at `0x241BA0290E0`
this run — ASLR-dependent, re-derive per launch; prefer it over the leaf, which may not be loaded when
a shim runs), then dispatch `SpawnDropPodForTeam` via Route E. ⚠ It mutates a **class default**, and
**C8/C9 have still never been reached.**


---

## 28. FLOWN — ONE BYTE FIXES BAIL 2. THE DROP POD SPAWNS AND `SpawnDropPodForTeam` RETURNS TRUE.

**Date:** 2026-08-20. One staged tutorial world, PID 20024. **Zero `.text` writes** — the only write
in the whole experiment is ONE BYTE per CDO on the heap.
**Primary evidence: `docs/s130-actor-pool-gate-settled.md` §13.** Pre-registered (with two
amendments, all written before the flights they describe) in
`scratchpad/s130/evidence/PREREG-cdopoke-flight.md`; raw markers in the same directory.

### 28.1 The result

| | before (byte = 1) | after the poke (byte = 0) |
|---|---|---|
| `SpawnPoolableActorFromClassDeferred` | **NULL**, `dP1 = +0` (S128) | live `BP_DropPod_Tutorial_C`, **`dP1 = +1`** |
| `SpawnPoolableActorFromClass` | **NULL**, `dP2 = +0` (S128) | live `BP_DropPod_Tutorial_C`, **`dP2 = +2`** |
| `SpawnDropPodForTeam` via Route E | **`false`**, DropPod **`+0`** (S127) | **`true`**, DropPod **`+2`** |

⇒ **C7 was the entirety of bail 2. Clearing `AActor::bCanEverReplicate` on the drop-pod CDOs makes
the pooled spawn produce real actors and `SpawnDropPodForTeam` succeed.**

### 28.2 ★★ The leaf CDO is now MEASURED, so nothing in the chain is inferred
`Default__BP_DropPod_Tutorial_C` @`0x1D1957E90E0` read **`bCanEverReplicate = 1`** in the staged world
— the one value §27 could only infer from its ancestors, because the leaf is not loaded at the menu.
`Default__Actor + 0x2D3 = 0` while all three pod CDOs read 1 reproduced the unpredicted two-sided
control from the menu run, in a different process.
Poke: **3 written, 3 readback-verified**, root control `Default__Actor` untouched at 1 — and the poke
**persisted across two further DLL injections** (the Route E arm, built with `KPDCDOPOKE=0`, read all
three back as 0).

### 28.3 ⚠ What is attributable, and what the probe refuses to grade
The probe emits two verdicts about different things, and both belong in the record:
* `VERDICT: control AGREED, so C1 (status -1, DropPod delta +2) is attributable to SpawnDropPodForTeam.`
* `*** E-VERDICT: E1 RAN BUT IS NOT ATTRIBUTABLE … E0c — the only control for the
  [UFunctionVtable+0x378] marshaller, which is the branch E1 takes — is INCONCLUSIVE (no candidate)
  … Record E1 (fault=0, return-slot written=1, DropPod delta +2) as UNATTRIBUTABLE. ***`
⚠ The E-VERDICT is about the **dispatch mechanism**, not about whether pods appeared, and E0c is
*unsatisfiable* on this class chain (S127: of 206 UFunctions exactly 1 takes that exit, and it is not
blind-callable). **Do not write "Route E is proven to marshal correctly."**
★★ **But the claim that matters is a DIFFERENCE and survives it:** S127 ran the same E1 dispatch on
the same function with the same unsatisfiable caveat and got `false`/`+0`. **The limitation is
identical in both arms, so it cancels in the differential** — what changed is one byte.
★ And the `poolspawn` arm carries no such caveat: native static, S55 direct-`Func` thunk, `P0c`
**STRONG PASS** (0.00 uu on |ref|=8377), `0xA5` sentinel showing `RESULT_DECL OVERWRITTEN`.
**That arm alone settles C7.**

### 28.4 ★★ The pool was still DISABLED, which confirms §25 live
`bSupportsActorPoolPriming` was never touched and `PrimePools` was never called — the pool was off for
the entire run and the pooled spawn produced actors anyway. The probe's own S128-era verdict says it:
*"… with the pool feature disabled … the disabled pool is a RED HERRING."*
⇒ §25's offline refutation is now **independently confirmed live**.

### 28.5 ⚠ What this does NOT establish
1. **That the pods are functional.** The census counts objects; nothing shows a pod flies or carries a
   player. **C8/C9 simply did not fire — they remain unexercised, not excluded.**
2. **That this is the FIX rather than the DIAGNOSIS.** It mutates a class default for the process
   lifetime and may break the pod's replication — which is what the flag exists to declare.
   ⛔ **Do not add it to the default shim set.**
3. **A within-session A→B→A.** The control is cross-session (S127/S128). `poolspawn-cdoctrl`
   (`.text 4e9c12ae866f5359`) is byte-for-byte the S128 experiment plus a read-only print — flying it
   converts the cross-session control into a within-session one, and it is the single cheapest
   strengthening available.

### 28.6 Blocker chain, current
```
markers        REFUTED   (S124)
phase          SOLVED    (S124)
subscription   DEAD      (S124)
SpawnPlane     FAULTS    (S124/S17)  -- but dropplane_b1only still creates a live LokiDropShip
SpawnDropPodForTeam  ->  RETURNS TRUE, DropPod +2   <-- FIXED S130 §28
  |
  +- bail 2 was C7: AActor::bCanEverReplicate on the pod CDOs
  +- NEXT: are the spawned pods functional? InitializeDropPod / FinishSpawningActor ran inside
     the caller's `if (spawn != null)` body for the first time -- nothing has looked at what they did.
  +- AND the rider handoff is still the FIFTH wall
     (AuthPlayerEnterWorldAttachedToRidable, always fails on a stripped fold)
```

---

## 29. S131 — THE POD IS FUNCTIONAL. §28.5 ITEM 1 IS ANSWERED.

**2026-08-20, one armed window, zero `.text` writes.** Primary evidence:
`docs/s131-pod-functionality-settled.md` and `scratchpad/s131/evidence/`. §28.5 said *"the census
counts objects; nothing shows a pod flies or carries a player."* Half of that is now answered.

### 29.1 `InitializeDropPod` ran — 3/3 discriminators, with a 3-pod within-run control

| field | class default | E1 pod `0x2BDA97A0200` | 3 control pods, same dump |
|---|---|---|---|
| `PodTeamIndex` @0x460 | `-1` | **`0`** | `-1` ×3 |
| `CurrPodDestination` @0x478 | `(0,0,0)` | **`(-3206.4, 5070.5, 100.0)`** | `(0,0,0)` ×3 |
| `bIsTeamLeaderPod` @0x45D | `False` | **`true`** | `false` ×3 |

The controls are the three pods RM_POOLSPAWN left in the same world, spawned by raw pooled/ordinary
spawns that never call `InitializeDropPod`. Same class, same instrument, same dumps.
⛔ `LeaderPod` (null→null) is a TRAP and is not a fourth check.

★★ **`CurrPodDestination` is a payload fingerprint** — the exact `LandingLocation` this arm computed
and printed in its own `E1 POSITIONS USED` line. No other code path in the process holds that vector.
**That attributes the pod to our call by CONTENT, which a census delta can never do**, and it is why
the result survives the standing E0c gap (§29.5).

### 29.2 The pod is ALIVE and FLYING — and every digit is accounted for

`ComponentVelocity = (20000.0, 0.0, 0.0)`; measured 19,862 uu/s over 8.0 s; Y and Z **exactly**
constant; `attach=none`; the three control pods measured at **0.0 uu/s** in the same pass. Cooked
asset: `ProjectileMovement_GEN_VARIABLE: InitialSpeed = MaxSpeed = 20000, ProjectileGravityScale = 0`.

⚠⚠ `20000` is **also** this shim's `KPDSPAWNZ`. Attributing the velocity to our own knob would have
been effortless and wrong. **The cooked asset settles it.**

### 29.3 ⇒ It flies BECAUSE `StartPodGameplay` never ran

`StartPodGameplay`'s **first act on the movement component is `Deactivate()`**. On the E1 pod [M]:
`bHasStartedGameplay=0` · `PodMeshComponent=null` · `DropPodState=0 (None)` · `bIsLocalPlayerPilot=0`
· `bSteeringEnabled=0`.

Root cause, [M]: **`Loki::LokiIsServer()` impl `0x0F7EB60` = `xor al,al; ret` — always FALSE**
(`LokiIsClient` impl `0x0B9E1F0` = `mov al,1; ret` — always TRUE). In
`ALokiDropPod::LokiBeginPlay_Implementation`, `0x596A3F9 call 0xF7EB60` + `test/jne` skips
`0x596A495 call 0x56FBCF0` = `LokiTeam::SetTeamForActor` (one caller image-wide). No team index ⇒
`OnTeamIndexChanged` never fires ⇒ `StartPodGameplay` never called ⇒ nothing ever deactivates the mover.

★ Independent engine receipt: `LogNiagara: Warning: NiagaraComponent(...
BP_DropPod_Tutorial_C_2147471134.NS_Drop_CloudTunnel ...) required LWC tile recache` ×3 — the pod's
drop VFX are instantiated and ticking, and UE reports it travelled far enough to re-base its LWC tile.

### 29.4 The FIFTH WALL — not tested by the Route-E flight, then CONFIRMED [M] the same day (see 29.7)

The precondition **is** met — the pod ships a `LokiRideable_GEN_VARIABLE`, and the in-arm rideable
census rises **+1 per pod** (20 → 21 on E1) — so `AuthPlayerEnterWorldAttachedToRidable` WAS called.
But its impl `0x55CD510` opens `test rdx,rdx ; je` on **`rdx = PlayerState`** and **returns silently
on instruction #1** when it is null.

`PilotPlayerState` reads **null** [M], because `GetTeamDropLeader` returns null, because
`ALokiTeamState_TeamOnly::SetDropLeader` is one of FK-1's four empty stubs (`0x0F7EC20`), as is
`ALokiPlayerState::AuthSetSpawnTeamLeader`.

⇒ `grep "failed to get the round game mode"` = **0, and UNINTERPRETABLE.** ★ The emit is **not**
stripped — it dispatches through `0x106B650`, a live logger with 22 other call sites, two of whose
messages appear verbatim in the corpus as `LogLokiGameMode: Display: …` — so the grep would have
worked had the branch been reached. **The blocker is the null argument, not the wall.**

★ **NEXT LEVER, ONE DATA POKE.** `ALokiPlayerState::IsSpawnTeamLeader` (impl `0x56C2060`, real,
decrypted in all three images) is a **pure read** of `[TeamState+0x688]`. Poking that field on a live
`ALokiTeamState_TeamOnly` gives `GetTeamDropLeader` a non-null answer **without calling either empty
stub**, and then `SpawnDropPodForTeam` exercises the rider handoff for real. Same write class as the
CDO poke: one aligned heap field, readback-verifiable, no module image touched.

### 29.5 What is still open

* **C8/C9 never fired** — unexercised, not excluded (unchanged from §28.5).
* **E0c** still has no callable candidate on this class chain, so the *dispatch mechanism* remains
  uncontrolled. **Unchanged from S130, so it cancels in the differential** — and §29.1's payload
  fingerprint does not depend on it.
* Whether a *properly managed* pod would descend is untouched: nothing drove `SetDropPodState`, and
  its own `LokiIsClient` early-return forecloses it on this client [M].
* §28.5 item 2 stands unchanged: **this is a diagnosis, not a shipping fix.**

### 29.6 New [M] facts worth reusing

1. **The Angelscript `ADDSi`/`LoadThisR` operand is a byte offset from `this`** — [I] → [M]. The AS
   ctor's 50-op operand sequence and the AOT-compiled x86 ctor's 50 `add rax,imm` sequence are
   ordered-identical **50/50**, replicated **12/12 classes / 214 pairs**; 9,468 annotated ops over 312
   files give **784 (typeid,member) pairs with zero conflicts**. Live agreement in-arm: **76 : 0**.
   ⇒ the `.as.txt` listings are a free offset oracle for every Angelscript member.
   ⚠ `propscan`/`boolscan` returning 0 on an AS name is **COVERAGE-BLOCKED**: AS member names have
   **0** byte occurrences in the image.
2. **A pooled DEFERRED spawn never `FinishSpawningActor`'d has a NULL `RootComponent`** — with the
   same class resolving `RelLoc@0x158` by name on three sibling pods in the same dump.
3. `bHasStartedGameplay` has **no UPROPERTY**; the AS offset `0x4B8` is the only route.
4. **The pooled-spawn NULL is gone**: `Failed to spawn actor of type` = 0 while
   `PrimePools : Feature is not enabled, skipping` still prints — §25 confirmed live from the
   opposite direction.

### 29.7 ★★★★★ THE FIFTH WALL IS CONFIRMED [M] — same client, zero extra launches

§29.4 named the blocker instead of banking it, and the blocker was then removed **in the same
sitting**. Full account: `docs/s131-pod-functionality-settled.md` §10.

⚠⚠ **§29.4's own proposed lever died first, to ONE read-only command.** "Poke `[TeamState+0x688]`" is
impossible here: **[M] ZERO live instances of any class containing `TeamOnly`**, and the only
`TeamState`-named live object is `Comp_TeamState_GlobalShop_GEN_VARIABLE`, a template. ⇒ ★ **check a
lever's precondition with a read-only pass before building the arm.**

So `RM_RIDEABLE` (enum 29) calls `AuthPlayerEnterWorldAttachedToRidable` **directly** on the pod's own
`LokiRideable` component with a live, valid PlayerState. Against a verified baseline of **0**:

```
LogLokiRideable: Error: ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable
                        failed to get the round game mode        x2  (one per call)
```

⇒ **[M] the body REACHES `0x55CD572`, gets 0 from the stripped `0xF7EB50` round-game-mode getter, and
takes its failure branch — with valid arguments.** The offline "REAL body, ALWAYS-FAIL" grade is now
measured.

Controls that make it a measurement: `ContainsPlayer` on the **same object through the same
primitive** (`fault=no`, so a silent R1 could not be confused with "the primitive never dispatched
here"); **both of the wall's own IsValid preconditions read out and PASSING**; **two independent
PlayerStates**; a verified zero baseline; and an exact per-call count.

★ **By-product:** the Error's category — recorded COVERAGE-BLOCKED by the lane-4 sweep because its
`FLogCategory` ctor sits on a never-decrypted page — **named itself**: `LogLokiRideable`. Driving the
path is how you name a category static analysis cannot reach.

⇒ **The next question is OFFLINE and free:** what did `0xF7EB50` replace at `0x55CD572`, and is there
any other route to a round game mode on this client? S124 established the tutorial already RUNS the
round mode, so one plausibly exists — if a different accessor is REAL, the wall may be one data poke
away rather than a dead end.

---

## 30. S132 (2026-08-20) — THE DISMOUNT RUNS, AND IT IS USABLE. THE BLOCKER CHAIN MOVES AGAIN.

**Primary evidence: `docs/s132-dismount-settled.md`. Raw: `scratchpad/s132/evidence/`, offline recon
and its adversarial verification: `scratchpad/s132/lanes/`.**

§29 ended by pointing at the wall's stripped round-game-mode getter and asking whether another route
to it exists. **S132 did not answer that. It went round it instead** — from the other end of the ride.

### 30.1 The result

Appending the PlayerState to `ULokiRideableComponent::PlayersAttached` (`+0x130` Data / `+0x138` Num /
`+0x13C` Max) with the **game's own `ResizeGrow` at `0x00F988D0`** — the exact function the fifth
wall's own tail calls at `0x55CD75B`, so the ABI and element size are correct *by construction* — and
then calling **`AuthPlayerDetachPlayerFromRidable`** (impl `0x55CCCB0`, exec thunk `0x5456100`)
through the S55 direct `UFunction.Func` thunk **takes the hero out of the pod, un-hides it, restores
its collision and movement, and places it at a chosen landing actor.**

Risk class **DATA**: two aligned `TArray`-header writes plus one element store, inside the game's own
allocation. **Zero `.text` writes, zero PI hooks, zero CDO pokes.**

| flight | calls | outcome |
|---|---|---|
| 1 | 4 | hero X = 1,453,041.8 → 4,859,800.1 → 11,648,502.8 → 14,428,083.3, each matching the flying pod's X at its **own** call time; run 2's hero Y **bit-identical** to the pod's (`==` on raw doubles, live); Z = 250.0 every time under a pod at Z = 20,100 |
| 2 | 1 | `LokiPlayerStart` as `LandingLocationActor`, **1,488,146 uu** from the pod → hero landed **at the PlayerStart** `(-3206.4, 5070.5, 138.0)`, settled to Z = 90.15 and held **bit-for-bit for 9 s** |
| 3 | 1 | reproduced flight 2 exactly; pod at X = 1,256,845 |
| 5 | 1 | ⚠ **FAULTED, no move** — see §30.5. Not a failure of the recipe: no PlayerState candidate passed GATE 5 that run, and the arm proceeded anyway. |

**Tally, re-derived from the seven canonical markers in `scratchpad/s132/evidence/` rather than carried forward: SEVEN detach calls across FOUR launches, SIX of which moved the hero.**

**A within-run NEGATIVE CONTROL ran before every call** — the same detach, same component, same
primitive, with `PlayersAttached` **empty** — and never moved the hero. The prediction is printed by
the shim *before* each call, so it cannot be reinterpreted after.

⇒ **[M] `GetLandingTeleportLocation` CONSUMES its `LandingLocationActor` argument**, which is what
makes this a *deploy primitive* rather than a curiosity: the landing point is ours to choose.

### 30.2 ⚠⚠ §29's "expect a PARTIAL dismount" was TOO PESSIMISTIC

§29 and the S132 handoff both warned that `AuthPlayerDetachPlayerFromRidable` is **not fold-free** —
it carries two `0xF7EC20` calls at `0x55CCD5B` and `0x55CCE4E` — and told the successor to expect a
partial result and to read any null as locating one of them. **The fold observation is correct and
stands. The consequence drawn from it was wrong.**

Full transcription (§30.5): **neither fold's return is ever tested.** Fold 1 is followed by
`mov r8d, 1` with `eax` dead; fold 2 is followed by the epilogue of a `void` function. **No branch
depends on either.** Everything that matters — `SetActorEnableCollision(true)` (`0x339A550`),
`SetPredropHidden(false)` (`0x5599040`, byte `hero+0x1BE8`), `GetLokiCharacterMovement` (`0x55AC8E0`)
with `vt[+0x3E0](true)` and `[mv+0x1A0] = 1.0f`, `GetLandingTeleportLocation` (`0x55D89F0`, REAL,
963 B) and the `SetActorLocation` teleport — is **a real body**. The partiality is confined to two
unnamed void state-changes.

⇒ **the general lesson: a fold in a function body is only a blocker if its RETURN is consumed.**
Grading a function "not fold-free" is not the same as grading it partial.

### 30.3 ★★★★★ FOUR EMPTY `Auth*` STUBS ON THIS COMPONENT, NOT ONE — and it explains the empty arrays

`ULokiRideableComponent` declares `void AuthAddPlayer(ALokiPlayerState)` as member index 0. **If it
were real it would replace S132's entire hand-built append.** It is not:

| method | exec thunk | impl | verdict |
|---|---|---|---|
| `AuthAddPlayer` | `0x2C2CE30` (23-way ICF) | **`0x0F7EC20`** | **EMPTY** |
| `AuthRemovePlayer` | `0x2C2CE30` | **`0x0F7EC20`** | **EMPTY** |
| `AuthSetCanJump` | `0x5296F30` | **`0x0F7EC20`** | **EMPTY** |
| `AuthPlayerEnterWorldNew` | `0x5456460` | **`0x0F7EC20`** | EMPTY (already known, §26) |

⇒ **[M, strong] the ONLY reflected writers of `PlayersInside` and `PlayersAttached` do nothing in this
client.** That is *why* both arrays read `Data=0 Num=0 Max=0` in a fully staged world, and why a data
poke is the only route to a rider **by construction**, not by preference.
⚠ Grade note: the `.data` record table has no class column, so the rows are matched by name — but each
name occurs **exactly once** in the whole 16,277-record table, `ULokiRideableComponent` is the only
class declaring either, and the class's exec thunks are emitted **alphabetically** in one contiguous
UHT block (`0x5455F40` … `0x5457940`) where `AuthAddPlayer` would sort at ~`0x5456050` — real code,
not a thunk. Its thunk is absent from the block **because it was ICF-folded onto the shared
one-object-param stub `0x2C2CE30`**, which is exactly what a stripped impl does.
★ The shortcut was **checked, not assumed**, before a launch was spent on it.

### 30.4 ⚠⚠ THE TRAP ON THIS SURFACE: `ContainsPlayer` READS THE WRONG ARRAY

```
0x55D0270  mov rax,[rcx+0x120]      ; PlayersInside.Data
0x55D0277  movsxd rcx,[rcx+0x128]   ; PlayersInside.Num
```

It scans **`PlayersInside` (`+0x120`)**, not `PlayersAttached` (`+0x130`). After a *correct* append it
still reads **false**, and that false is EXPECTED. **Using it as the append receipt manufactures a
false negative on a working append.** It was disassembled before being trusted and turned into a
pre-registered prediction instead — `D2c ContainsPlayer(after append — MUST still be false)` — which
then confirmed the append had not landed in the wrong array.

★★ **And the receipt that DOES work is free and log-independent:** `PlayersAttached.Remove(PS)` at
`0x55CCE23` executes on **every** path past GATE 4, including the two that skip the hero body. So
`Num` staying 1 vs dropping to 0 separates "bailed at a gate" from "ran past GATE 4" with no log
dependence at all — on a function with **zero log strings in its 440-byte extent**. Observed
**1 → 0** on every successful run.

### 30.5 The six gates, all silent, all read out before the call

`0x55CCCB0..0x55CCE68`, 440 bytes, 9 chained `.pdata` rows, page `0x055CC000` decrypted.
Signature [M, UHT oracle]: `void AuthPlayerDetachPlayerFromRidable(ALokiPlayerState PlayerState,
const AActor LandingLocationActor)`.

1. `PlayerState != null` · 2. PS not garbage (`[PS+0xC] >> 30`) · 3. `PlayersAttached` non-empty ·
4. PS present in it · 5. `PS->GetLokiCharacter() != null` · 6. that hero `IsA(ALokiHeroCharacter)`
(`0x54F8DC0` is `IsChildOfUsingStructArray`; the class literal is `LokiHeroCharacter` at
`.rdata 0x899A832`).

The arm measures 5 by *calling* the reflected `GetLokiCharacter` read-only and 6 by walking the live
class chain, **before** it writes anything — which is what makes a null attributable.
⚠ **MEASURED DEFECT, worth carrying forward:** when *no* candidate passes GATE 5, proceeding anyway
**faults** — `GetLokiCharacter` faults on a template PlayerState (`0xC0000005 READ 0xFFFFFFFFFFFFFFFF`
at `rva 0x54F8C57`) rather than returning null. **GATE 5 is not a clean early-out for a bad
argument.** The no-candidate branch must REFUSE. ★ The safety design held: SEH caught it, the client
survived 428 s, and the arm's own restore step detected and removed the entry the aborted call had
left in `PlayersAttached`.

### 30.6 Other [M] facts worth reusing

- **`UActorComponent`'s owner is at `+0xB8`**: runs 1–2 passed `nullptr` (the detach substitutes
  `[comp+0xB8]` itself at `0x55CCCE5`) and runs 3–4 passed the pod **explicitly**; all four behaved
  identically, and the arm printed `[comp+0xB8] … cls=BP_DropPod_Tutorial_C`.
- **`PlayersAttached` is NOT replicated** (no `CPF_Net`), by two disjoint instruments. An earlier
  S132 write-up called it "a replicated array"; the correction makes the write **safer** than
  described, not riskier.
- **`TArray::Remove` (`0x11F3860`) writes ONLY `Num`** — no free, no realloc. So the run-1 allocation
  survived into runs 2–4 (`Max already covers it -> no ResizeGrow needed`), and **a poked buffer is
  never freed by this function.**
- **`0xF7EC20` is `c2 00 00` = `ret imm16 0`, a VOID no-op — it does NOT zero `eax`.** The repo's
  long-standing "ret 0" shorthand reads as "returns zero", which is a different claim.
- ⛔ **`AuthPlayerEnterWorld` (`0x55CCE70`) is FORECLOSED as an alternative route**: its two terminal
  actions are direct calls to the stripped `0xF7EB50` and it writes **no** actor or component
  transform. Satisfying its `PlayersInside` guard with a poke would move execution past the guards and
  change nothing about where the hero is.
- ⚠⚠ **A rel32 caller scan over `merged4` is a FLOOR even when uncapped** — 44.91 % of `.text` is
  all-zero and it cannot see a reflected/Blueprint caller at all. Demonstrated from inside the result:
  `KickPlayersFromPod`'s bytecode carries **two** `CALLSYS` sites and the scan found one, because the
  other's AOT body is on a page all-zero in 30 of 30 images.

### 30.7 Blocker chain, current

```
markers        REFUTED  (S124)
phase          SOLVED   (S124)
subscription   DEAD     (S124)
SpawnPlane     FAULTS   (S124/S17) -- b1only still creates a live LokiDropShip
SpawnDropPodForTeam -> RETURNS TRUE, pod spawns                        FIXED    S130
  |
  +- InitializeDropPod RAN, 3/3 discriminating writes landed           MEASURED S131
  +- the pod is ALIVE and FLYING at its cooked 20,000 uu/s             MEASURED S131
  +- the RIDER HANDOFF (mount) fails: one stripped round-game-mode
  |    getter, three consumers, no sibling left to try                 MEASURED S131
  +- THE DISMOUNT RUNS, AND IS USABLE: hero out of the pod, un-hidden,
  |    collided, gravity-affected, placed at a CHOSEN actor on real
  |    terrain, standing                                               MEASURED S132  <-- HERE
  +- NEXT (offline, free): transcribe SpawnAndMoveLokiCharacter_MoveStep
  |    (0x55C1B20) and hand-assemble the MOUNT the same way -- the
  |    wall's whole success tail is real and named except that one
  +- NEXT (one launch): is the hero PLAYABLE at the landing point?
  |    -> play-atlanding-walk (-DKFLYMODE=1). The flying-mode arm is
  |       DEGENERATE: its control moved 2,926 uu at constant Z=13,240
  +- C8 / C9 still never fired: unexercised, NOT excluded
```

### 30.8 What is still open here

- **Is the hero playable at the landing point?** Open. See `docs/next-session-prompt-s133.md` §1.2 —
  the arm is built and the readings are pre-registered, and the obvious arm is measured DEGENERATE.
- **The mount.** The wall's success tail is `LokiTeleportActor` (reflected) →
  `SetActorEnableCollision(true)` → `SpawnAndMoveLokiCharacter_MoveStep` →
  `SetActorEnableCollision(false)` → a `GetServerTime` stamp into `hero+0x1C10` → the append. S132
  proved the append; the rest is real and named **except** `MoveStep` (`0x55C1B20`), which is not
  reflected and carries two folds of its own. **Transcribe it before designing the arm.** Free.
- **`GetLandingTeleportLocation` (963 B) is untranscribed.** That it consumes the actor is [M]; *how*
  it derives the point is not — the −9.85 uu rest offset observed in flight 2 is the hero's own
  capsule settling, not necessarily the function's output.
- The two `0xF7EC20` folds are **unnamed** (`0xF7EC20` has ~165,789 call sites, so the address
  identifies nothing), and `0x5586530(hero)` is REAL and unnamed — ⚠ it dereferences `hero+0x460`,
  `hero+0x1978` and `hero+0x1980` with **no null checks**. It survived every S132 call on
  `BP_HERO_Ronin_C`; read the three pointers before arming on a differently-configured hero.
- ⛔ **None of this is a shipping fix.** It writes a live component's state array by hand and drives
  an authority-only entry point. Do not add it to the default shim set.
