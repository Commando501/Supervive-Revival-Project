# S191 — LMB → Ability1 INPUT BINDING PATHWAY FULLY MAPPED (2026-09-10, offline)

Follow-up to `docs/s191-e4-flight3-RESULT.md`. E4 flight 3 killed a hostile enemy minion
via the direct-write fallback (`KE4DIRECTGE`) but the natural LMB tap fired NO ability
activation lines in Loki.log. This doc traces the game's actual LMB→Ability1 dispatch
chain end to end (zero launches, all offline via `bpdump` + asdump) and identifies THREE
concrete, REFLECTED, REAL (S153-graded) primitives any of which unlocks the natural-cast
half of the E4 predicate.

## The FULL LMB dispatch chain [M]

Traced via `bpdump ExecuteUbergraph_BP_LokiPlayerController` (8225 lines, 717
ScriptBytecode entries). The LMB action fires a K2Node_InputActionEvent (legacy
`UInputComponent::BindAction` mechanism, NOT Enhanced Input for gameplay — 0 hits for
`BindAbilityActivationToInputComponent`, `SetupPlayerInputComponent`, `FInputActionBinding`
in the runtime binary; only `EnhancedInputAction` / `InputMappingContext` for UI/menus
per the ASCII+UTF16 census). The handler at Ubergraph statements 8109–8173:

```
[319] EX_PopExecutionFlowIfNot   BooleanExpression: !IsAnySpellTargeting()
[320] EX_CallMulticastDelegate   StackNode: LMBPressed__DelegateSignature
                                  Delegate: OnLMBPressed
[321] EX_Context Comp_PlayerController_Abilities.HandleAbilityActivation(byte 3)  ← THE ACTIVATION
[322] EX_PopExecutionFlow
```

The `byte 3` value passed to `HandleAbilityActivation` is `LokiAbilityInputID::Ability1`
— **[M] confirms my Ability1=3 inference** (S147 already pinned Ability3=5; the ordinals
are the consecutive `None/Confirm/Cancel/Ability1..4/DodgeRoll` prefix layout).

## The abilities component's activation body [M]

`bpdump Comp_PlayerController_Abilities HandleAbilityActivation` = a 4-entry BP-event
wrapper that immediately calls `ExecuteUbergraph_Comp_PlayerController_Abilities(591)`.
The ubergraph at index 591 does:

- **Entry 28**: `Self.Can Upgrade Ability(AbilityID, out bCanUpgrade)` — level-up gate
- **Entry 29**: `Self.IsLevelAbilityModifierPressed(out KeyPressed)` — modifier check
- **Entry 30/31**: `bCanUpgrade AND KeyPressed` → JumpIfNot skip
- **Entry 32**: `Self.ServerAddAbilityLevel(AbilityID)` — level up path
- ... continues down to the activation path, calls:
  - `Self.TryActivateAbility(AbilityID)` (LocalVirtualFunction at bytecode entry 37 in
    ubergraph — the component's own virtual)
  - `ASC.TryActivateAbilityByInputID(AbilityID)` (entry 24) — the SAME
    `ULokiAbilitySystemComponent::TryActivateAbilityByInputID(LokiAbilityInputID)`
    method 54 that is REAL @ `0x52971A0` [M, S153]

## Three REFLECTED, REAL primitives that ANY of which closes E4 [M]

All three grades = REAL from `scratchpad/s153_native_ufunction_sweep_v2.csv`
(byte-verified impl bytes, not stripped folds):

| callable | impl | signature | pathway |
|---|---|---|---|
| `ULokiAbilitySystemComponent::TryActivateAbilityByInputID` | `0x52971A0` REAL | `bool(LokiAbilityInputID)` | ASC method 54 — directly resolves InputID→spec→activate |
| `ULokiAbilitySystemComponent::BP_AuthGiveAbilityWithInputID` | `0x5294B50` REAL | `FGameplayAbilitySpecHandle(TSubclassOf, int Level, LokiAbilityInputID, UObject Source, int Priority=0)` | ASC method 10 — grant that WIRES the InputID→spec mapping |
| `Comp_PlayerController_Abilities::HandleAbilityActivation` | BP-event | `void(byte AbilityID)` | mimics the exact BP dispatcher the LMB uses (level-up check + TryActivate) |
| `ULokiAbilitySystemComponent::TryActivateAbilityBySourceObject` | `0x5297230` REAL | `bool(UObject Source, bool AllowRemote=true, TSubclassOf=nullptr)` | ASC method 55 — activates by matching spec.SourceObject |

**The likely root cause of E4 flight 3's null:** our K_GRANT called plain native
`GiveAbility` (via `BfBuildSpec` + the ASC vtable+0x778 grant virtual). That registers a
spec with `spec.InputID @+0x24 = 3` in the ASC's Items TArray, but **may not populate
the separate InputID→spec MAP** that `GetAbilityByInputID` / `TryActivateAbilityByInputID`
consult. `BP_AuthGiveAbilityWithInputID` is specifically designed to wire that mapping.

## Concrete follow-up design (next session)

**Option A — Cheapest, tests the ASC's InputID map directly:**
Extend the E4 arm's phase-0 to add ONE step after K_GRANT: call
`ASC.TryActivateAbilityByInputID(3)` via the existing S55 direct-thunk primitive.
- If returns `true`: WALL P is DEAD for LMB; predicate met.
- If returns `false`: our GiveAbility-registered spec isn't visible to
  `GetAbilityByInputID` — Option B is needed.
- If dies with `0xDEAD`: WALL P proper hit on the InputID pathway too — need a
  post-disarm mechanism (Option C).

**Option B — Fix the grant path:**
Swap K_GRANT to call `BP_AuthGiveAbilityWithInputID(GS_Ronin_LMB_Selector_C, 1, 3, hero,
0)` instead of plain `GiveAbility`. This uses the game's own InputID-aware grant, which
presumably populates the InputID→spec map. Then re-test with either OS LMB tap OR
`TryActivateAbilityByInputID(3)`.

**Option C — Mimic the BP dispatcher exactly:**
Call `Comp_PlayerController_Abilities::HandleAbilityActivation(3)` via S55 on the LIVE
abilities component on the PC. This runs the entire BP activation dispatcher including
the level-up check + TryActivate — closest replica of what LMB → K2Node_InputAction →
handler does, minus the OS-input hop.

**Option D — Test whether OS LMB events even reach the K2Node_InputAction:**
Add an in-shim RPM watch on the abilities component's `LastAbilityActivationTime` (or
similar timestamped state) around a `send-lmb.ps1` tap. If the timestamp moves, OS LMB
IS reaching the BP handler but our spec resolution fails downstream; if the timestamp
never moves, OS LMB isn't reaching the handler at all (menu widget consuming it, etc.).

**All four flyable in ONE armed session** — extend `RM_BOTFIGHT`'s `#if KBFE4` block:

```
#if KBFE4B  // new bit: use BP_AuthGiveAbilityWithInputID grant (Option B)
    replace BfBuildSpec+BfGiveAbilityNative with BP_AuthGiveAbilityWithInputID call
#endif
#if KBFE4C  // new bit: call HandleAbilityActivation post-spawn+seed (Option C)
    ResolveFuncSuper(PC.Comp_PlayerController_Abilities.Class, "HandleAbilityActivation")
    CallNativeGuarded with byte 3
#endif
#if KBFE4A  // new bit: call TryActivateAbilityByInputID(3) direct (Option A)
    ResolveFuncSuper(ASC.Class, "TryActivateAbilityByInputID")
    CallNativeGuarded with LokiAbilityInputID 3
#endif
```

Each option gated separately so a single flight tests one variable at a time. Priority
order: A → C → B (A is the simplest single call; C is the closest BP-mimic; B needs
the most source changes).

## Live diagnostics to do BEFORE flying (cheap, no game restart if PID alive)

1. **RPM read `PC → Comp_PlayerController_Abilities`** (find the component on the live
   PlayerController by property name). Is it present? If not, the whole BP dispatcher
   is unreachable and we need to spawn/attach it first.
2. **RPM walk `ASC.Items` array** — confirm our K_GRANT'd spec is at Handle 1 with
   InputID=3 and Ability=`Default__GS_Ronin_LMB_Selector_C`. The E4 flight 3 marker
   already logged this (`spec built=ok Ability@+0x10=0x1E92B5BB890(== CDO) Handle@+0xC=1
   Level@+0x20=1 InputID@+0x24=3`), so this is already [M].
3. **Live grep test for `IsAnySpellTargeting()`** — if the parked-tutorial hero has
   any spell in targeting phase (e.g. an auto-loaded targeting reticle), the
   `[319] EX_PopExecutionFlowIfNot` bails BEFORE HandleAbilityActivation ever runs.
   The BP condition is `!IsAnySpellTargeting`, so if a spell is in Targeting, all
   LMB taps become no-ops. This is a plausible parked-state gotcha.

## What is REFUTED by this investigation

- **"The game uses Enhanced Input for gameplay ability activation"** — REFUTED. The
  runtime binary has 11 `EnhancedInputAction` and 5 `InputMappingContext` hits, but
  0 hits for `BindAbilityActivationToInputComponent`. `EnhancedInputAction` is used
  for UI/menus (per `DT_InputActionData_Menus`); gameplay LMB→ability uses LEGACY
  `UInputComponent::BindAction` via `K2Node_InputActionEvent` in the BP ubergraph.
- **"Our K_GRANT registers the spec fully but somehow the OS input isn't wired"** —
  REFUTED as too vague. The actual issue is architectural: `GiveAbility` populates
  the Items TArray but not the InputID→spec map that `TryActivateAbilityByInputID`
  consults. `BP_AuthGiveAbilityWithInputID` is the InputID-aware grant.
- **"We need to call `BindAbilityActivationToInputComponent`"** — REFUTED. That
  legacy GAS pathway isn't used here. The Loki-specific dispatcher is
  `Comp_PlayerController_Abilities::HandleAbilityActivation`.

## Rules banked

- **R-S191-g:** the game's LMB→ability pathway is a BP-authored dispatcher
  (`Comp_PlayerController_Abilities::HandleAbilityActivation`), NOT stock GAS
  `BindAbilityActivationToInputComponent`. Any input-binding investigation must
  start from `bpdump ExecuteUbergraph_BP_LokiPlayerController`, not from the
  UE GAS source assumptions.
- **R-S191-h:** GAS has TWO parallel registration structures for granted abilities:
  the Items TArray (populated by plain `GiveAbility`) and the InputID→spec map
  (populated by `BP_AuthGiveAbilityWithInputID`). A spec that's in Items but not
  in the InputID map is invisible to `TryActivateAbilityByInputID` /
  `GetAbilityByInputID`. Any InputID-based activation shim must use the InputID-
  aware grant.
- **R-S191-i:** binary string census is the fast disambiguator between "the game
  uses Enhanced Input" vs "the game uses legacy Input". 5 patterns queried:
  `BindAbilityActivationToInputComponent` (0), `SetupPlayerInputComponent` (0),
  `EnhancedInputAction` (11), `InputMappingContext` (5), `K2Node_InputActionEvent`
  (54+ in the PC's ubergraph). Any nonzero on the enhanced side + any zero on the
  legacy strings = the CODE uses enhanced (menus), the BP uses legacy (gameplay).

## Cost

- 0 launches. Pure offline investigation via `bpdump` on already-extracted assets.
- 8225-line PC ubergraph + 2683-line abilities-component ubergraph + 135-line
  PC_Code ubergraph = ~11 KLOC of BP bytecode read.
- 4 REAL activation primitives identified.
- 3 concrete follow-up options (A/B/C/D) each with a specific null/success outcome.

## Files

- `tools/extractor/out/bpdump_ExecuteUbergraph_BP_LokiPlayerController.txt`
- `tools/extractor/out/bpdump_HandleAbilityActivation.txt`
- `tools/extractor/out/bpdump_ExecuteUbergraph_Comp_PlayerController_Abilities.txt`
- `tools/asdump/out/binds_members.csv` (for the ASC methods 10/54/55)
- `scratchpad/s153_native_ufunction_sweep_v2.csv` (for REAL/STRIPPED grades)
- `docs/s191-e4-flight3-RESULT.md` (the parent E4 flight result)
- `dumps/merged14.dump.exe` (the runtime binary scanned for input strings)
