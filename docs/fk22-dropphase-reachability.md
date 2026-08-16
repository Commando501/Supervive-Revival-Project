# FK-22 — The falsification does not generalise: `SpawnPlane` is a per-variant Blueprint override, the markers exist, and the real blockers are a stalled phase machine plus empty server-authority C++ impls

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
