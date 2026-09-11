# S191 E4 Option F — Flight 1 [M] STRUCTURAL FINDING (Outcome E-fast) — 2026-09-10

★★★★★★★ **THIRD activation surface CHARACTERIZED [M]. E4F predicate REFUTED with a NAMED CAUSE.
Independent witness in Loki.log confirms the shim call reached the game's ability system and was
refused at a Handle-resolution step, NOT at a permission check.**

Flight 1 was a first-try success (no launches lost to FK-31, no faults, clean disarm). Every part
of the workflow-adjudicated design landed as specified. Grade against the pre-registered
discriminator table in `docs/s191-e4f-DESIGN.md`: **Outcome E-fast** (retBool=0, elapsedMs≈0, dHP=0)
— **grade POSITIVE / STRUCTURAL FINDING**.

## The result, verbatim

`docs/s191-e4f-flight1-marker.log`:

```
[E4F] pre-activate: pASC=0x2D90A103400(LokiAbilitySystemComponent) hero.Ability1=0x2D8F8E96A60(GS_Ronin_LMB_Selector_C) minionPreHP=100.00
[E4F] E4F_CALL_ISSUE: calling ASC.TryActivateAbilityBySourceObject(Source=hero=0x2D9165A5580,bAllowRemote=1,Class=0x2D8F8E96A60(GS_Ronin_LMB_Selector_C)) ; target=base+0x5297230 ; param offsets SO=0x0 BR=0x8 AC=0x10 RV=0x18 ; tStart=648001562
[E4F] E4F_RESULT   faulted=no retBool=0 elapsedMs=0 minPreHP=100.00 minPostHP=100.00 minPostBits=42C80000/42C80000 dHP=+0.00  return=false FAST (<100ms): possible pre-downstream early-out — STRUCTURAL FINDING, BySourceObject-analogue of R-S191-h
```

## Independent witness (Loki.log)

`docs/s191-e4f-flight1-loki.log` (line 5866 at `17:44:11:298`, `147 ms` after E4F_CALL_ISSUE's
`tStart=648001562`):

```
LogAbilitySystem: Warning: TryActivateAbility called with invalid Handle
```

This is the game's own `LogAbilitySystem` category emitting a Warning in direct response to our
E4F call. Zero occurrences of this string in the entire log preceding the CALL_ISSUE. Zero
spell-state transitions (`going from nullptr`, `Warmup`, `Channeling`, `LightAttack`, `Fireblast`
searches all return empty for the E4F window) — the call was refused BEFORE any activation body
ran. ⇒ **`TryActivateAbilityBySourceObject` internally converts (SourceObject, AbilityClass) →
Handle → activation, and the (hero, `GS_Ronin_LMB_Selector_C`) pair resolves to a Handle the
game considers invalid.** The refusal is at the handle-resolution / spec-lookup layer, upstream
of anything WALL-P related.

## Three-surface WALL-P + activation matrix

| surface                              | impl RVA      | shim-call verdict                                    | discriminator                                    |
|--------------------------------------|---------------|------------------------------------------------------|--------------------------------------------------|
| `TryActivateAbilityByClass`          | (S147 target) | **LETHAL 0xDEAD** at ~50-70s post-call               | S147 measured on MiniDash                        |
| `TryActivateAbilityByInputID`        | `0x52971A0`   | NON-lethal clean-false; InputID map empty (R-S191-h) | S191 E4A F1                                      |
| **`TryActivateAbilityBySourceObject`** | **`0x5297230`** | **NON-lethal clean-false-FAST (<100ms, elapsedMs≈0); `invalid Handle` warning in game log** | **S191 E4F F1 (this flight)**                    |

⇒ **[M] Three distinct activation surfaces with three distinct WALL-P profiles.** ByClass is the
only one that produces the protector kill. ByInputID and BySourceObject both refuse early and
return cleanly. The safe-shim-callable subset is now the two ByX variants — but neither of them
activates because both fail at a pre-activation resolution step (missing InputID map entry for
ByInputID; invalid Handle for BySourceObject).

## Rules banked

**R-S191-p** [M] (activation-surface characterization): `ULokiAbilitySystemComponent::TryActivateAbilityBySourceObject`
(wrapper @ `0x5297230`, S153 REAL) is non-lethal from a shim and returns `false` in <100ms with the
game's `LogAbilitySystem` emitting `TryActivateAbility called with invalid Handle`. The internal
(SourceObject, AbilityClass) → Handle resolution fails on our K_GRANT'd spec even though
`spec.SourceObject == hero` is measured set. Third distinct entry in the WALL-P three-surface
matrix.

**R-S191-q** [M] (workflow-adjudicated design method): a pre-build strxref recon of the target
impl (30s, 0 launches) grades WALL-P lethality risk BEFORE committing to a launch. For E4F,
`strxref func 0x5297230` showed BySourceObject tail-calls `0x5544FB0`→`0x44280E0`, a different
downstream than ByClass's `0x4480B30` InternalTryActivateAbility — MISS on the shared-downstream
discriminator, so the workflow downgraded WALL-P prior from [I,strong] to [I], predicted Outcome
C prior would rise to ~30% and Outcome E-fast to ~10-15%. The flight landed in Outcome E-fast
exactly. **Pre-build recon per shim-callable activation surface is a reusable ~30s cost.**

**R-S191-r** [I,strong] (game-log independent witness): a `LogAbilitySystem: Warning:` line at the
exact timestamp of a shim CALL_ISSUE is stronger evidence than the marker's retBool alone — it
proves the game's ability system ran and refused, ruling out "shim call never reached the game".
Reusable: pin `LogAbilitySystem=Log` in the user Engine.ini (already on) and grep for
`Warning:` lines in the ~500ms window around each E4x_CALL_ISSUE.

## What this settles for the E4 predicate

**Refuted**: two of the three shim-callable activation surfaces do not activate on our K_GRANT'd
spec (ByInputID fails on empty InputID map; BySourceObject fails on invalid Handle). The natural-
cast half of E4 via a direct shim call is not reachable through the reflected ASC verbs alone —
the game's activation stack requires state (InputID→spec map entry OR a valid Handle) that plain
`GiveAbility` does not construct.

**Not refuted**: the two remaining paths per the E4B RESULT doc's decision:
- **Option C** — `Comp_PlayerController_Abilities.HandleAbilityActivation(3)`: BP dispatcher on the
  PlayerController; BP-authored (not stripped-stub class); has `TryActivateAbilityByClass` and
  `TryActivateAbilityBySourceObject` branches downstream. **Untested from a shim.**
- **Option E** — direct offset write to populate the InputID→spec map: needs offline read of
  `GetAbilityByInputID` impl `0x5295330` (S153 REAL) to identify the map field. After the write,
  re-fly E4A: if the map is populated AND E4A's `retBool==1` + minion HP drops, the E4 predicate is
  met.

Option C is a BP dispatcher call so it may have different WALL-P semantics than the ASC's own
`TryActivate*` family — worth trying. Option E is riskier (unresolved offset) but doesn't need a
shim ability call at all.

## Cost + gates

- 1 launch, 0 losses to FK-31 (first-try staging success)
- 0 collateral damage: game alive 385s+ post-CALL, past both the Outcome A window (T+50-70s) AND
  the ambient FK-32 window (~285-293s uptime signature per S190). Killed cleanly post-`dumpimage`.
- Clean disarm: `restored=17563 of 17563` funcswaps
- Regression gates unchanged: `botai b620e0ff3279e673`, `play 31af7667355f39d1`, `e4 69197ce6e9e38dda`,
  `e4-a 2d7efa4cde249f2e`, `e4-b 39f1ae3c41fbc1ad`, `e4-b2 5827bc3863157d25`, `e4-directge
  404ad6c7cdf44a8c` (all BYTE-IDENTICAL to pre-flight — `KBFE4F=0` truly dead-strips)
- Flown arm: `e4-f RAW=1f51942a2b8d164a` VSIZE=`c80e8991454c3dcf` VERIFY_DLL PASS KERNEL32-only
  `--dupes` clean

## Files

- `docs/s191-e4f-flight1-marker.log` — the E4F chain verbatim (117 lines)
- `docs/s191-e4f-flight1-loki.log` — game log with the `invalid Handle` witness at `17:44:11:298`
- `dumps/s191-e4f-flight1/SUPERVIVE-Win64-Shipping.dump.exe` — post-flight image dump (67.63%
  readable) for offline analysis of any newly-decrypted pages the E4F call exercised
- `tools/sigbypass-mod/tutorial_launch.cpp` — KBFE4F knob + 12 policy #errors + `#if KBFE4F` block
  (committed at `a4d1b27`)
- `tools/sigbypass-mod/build.ps1` — `e4-f` variant (committed at `a4d1b27`)
- `docs/s191-e4f-DESIGN.md` — workflow-adjudicated design + pre-flight recon (committed at `a4d1b27`)

## Session-total tally after this commit (S191 arc)

| flight | outcome | grade |
|---|---|---|
| S191 E4 F3 | minion killed via KE4DIRECTGE; natural LMB cast REFUTED (input binding) | [M] |
| S191 E4A F1 | ByInputID clean-false NON-lethal; R-S191-h confirmed live | [M] |
| S191 E4B F1+F2 | BP_AuthGiveAbilityWithInputID impl is 9-byte stripped stub; new FK-1 register entry | [M] |
| **S191 E4F F1** | **BySourceObject clean-false-fast NON-lethal; `invalid Handle` witness** | **[M]** |

Total S191 launches: 5 flown, 3 lost to FK-31 (~37% cluster; within the ~27-40% documented rate).
No shim ever triggered a FK-32 kill in the S191 arc.
