# S191 E4A FLIGHT 1 — R-S191-h CONFIRMED LIVE; TryActivateAbilityByInputID NON-LETHAL (2026-09-10)

★★★★★★★ **DEFINITIVE MEASUREMENT [M]**: our K_GRANT (plain native `GiveAbility` via
BfBuildSpec + ASC-vtable+0x778) registers the spec in the ASC's `Items` TArray with
`InputID @+0x24 = 3` BUT does NOT populate the separate InputID→spec map that
`GetAbilityByInputID` / `TryActivateAbilityByInputID` consult. **R-S191-h confirmed on the
live game**, exactly as predicted by the offline mapping in
`docs/s191-lmb-input-binding-mapped.md`. Path forward: swap K_GRANT to
`BP_AuthGiveAbilityWithInputID` (Option B), which is the InputID-aware grant that populates
BOTH structures.

★★★★★ **AND `TryActivateAbilityByInputID(3)` DID NOT KILL THE PROCESS** — a shim-originated
call to `ULokiAbilitySystemComponent::TryActivateAbilityByInputID` at `base+0x52971A0`
returned `false` cleanly (fault=no, no 0xDEAD), then FsDisarm restored 17563/17563
funcswaps, and the game continued alive. **A distinct WALL-P surface point from
S147/S158**: `TryActivateAbilityByClass` from a shim → 0xDEAD; `TryActivateAbilityByInputID`
from a shim → clean false-return. The InputID activation surface is safe for shim calls.

## The receipts (verbatim, from `docs/s191-e4a-flight1-marker.log`)

```
[E4] hero loc=(0.0,0.0,13240.0) rot(P/Y/R)=(0.0,-49.7,0.0) haveRot=yes forward=(0.647,-0.763) -> target loc=(129.4,-152.5,13240.0) (200 uu forward)
[E4] selected target class = BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C @0x1BC7AA43B20
[E4] TARGET_SPAWNED minion=0x1BC8C1F0010(BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C) loc=(129.4,-152.5,13240.0) dxyFromHero=(129.4,-152.5)
[E4] minion PlayerState=0x0 MinionTeamID=100 (100 => enemy of the player; do NOT poke -- WALL E [M] favorable)
[E4] minion ASC(minion+AbilitySystemComponentStorage)=0x1BC8C719A00(LokiAbilitySystemComponent)
[E4] InitAbilityActorInfo ok ; netsim@+0x800 0->0 ; AvatarActor@+0x410=0x1BC8C1F0010 == minion (BOUND)
[E4] TARGET_SEEDED result=ok seedBits=42C80000 Health=42C80000/42C80000 Max=42C80000/42C80000 wr(h=1,m=1) exact=yes
[E4A] pre-activate: pASC=0x1BC937BB380(LokiAbilitySystemComponent) minionPreHP=100.00
[E4A] E4A_GETBYID  faulted=no return=0x0(NULL) (NULL -> R-S191-h confirmed: plain GiveAbility did NOT populate the InputID→spec map)
[E4A] E4A_CALL_ISSUE: calling ASC.TryActivateAbilityByInputID(Ability1=3) ; target=base+0x52971A0
[E4A] E4A_RESULT   faulted=no retBool=0 minPreHP=100.00 minPostHP=100.00 minPostBits=42C80000/42C80000 dHP=+0.00  return=false (activation refused: either InputID map missing our spec, or a downstream gate)
[E4] E4_COMPLETE RESULT=TARGET_READY
[FS] disarm: restored=17563 of 17563 swapped (scan 3828 ms, 34394 UFunctions live)
```

Game continued alive at 237s uptime (well past the ~285s FK-32 base rate; killed cleanly
by Stop-Process after evidence preservation).

## Six [M] results in ONE flight (no launches lost to FK-31)

1. **[M] R-S191-h CONFIRMED LIVE.** `GetAbilityByInputID(Ability1=3)` returns NULL despite
   our K_GRANT'd spec being at `Handle=1`, `Ability=Default__GS_Ronin_LMB_Selector_C`,
   `InputID @+0x24=3` in the ASC's Items TArray. The InputID→spec map is a SEPARATE
   structure that plain `GiveAbility` does not populate. My offline hypothesis (docs/
   s191-lmb-input-binding-mapped.md) is now a live measurement.
2. **[M] `TryActivateAbilityByInputID(3)` returned `false` cleanly.** Non-lethal. The
   call reached impl `0x52971A0` (S153-graded REAL), did the map lookup, got null,
   returned false. This is a distinct WALL P datum: not every shim-originated ability
   activation call trips the S147/S158 death (which was on
   `TryActivateAbilityByClass`).
3. **[M] The minion Health is unchanged** (100.00→100.00 exact bits) — no side effect
   fired. As expected when the activation is refused pre-body.
4. **[M] The E4 arm's hardening fixes all continue to fire correctly**: rotation-read
   facing (Yaw −49.7° → forward (0.647,−0.763) placed the minion at (129.4,−152.5)),
   AvatarActor readback confirmed the bind, SpawnedAttributes registration verified.
5. **[M] `Comp_PlayerController_Abilities.HandleAbilityActivation(3)` and Option C's
   pathway are UNTESTED here** — the E4A block calls the ASC directly, not the BP
   dispatcher. Whether the BP dispatcher fires when the InputID map is empty is a
   separate question (Option C).
6. **[M] Fully clean disarm**: 17563/17563 restored, no FK-32, no crashpad, game alive
   throughout. First-try flight success (no launches lost).

## What is now the definitive path forward

**Option B (as designed in `docs/s191-lmb-input-binding-mapped.md`):** swap K_GRANT from
plain `GiveAbility` to `BP_AuthGiveAbilityWithInputID(GS_Ronin_LMB_Selector_C, Level=1,
LokiAbilityInputID=Ability1(3), hero, InputIDPriority=0)` — the InputID-aware grant at
impl `0x5294B50` (S153-graded REAL). This should populate the InputID→spec map that
Option A revealed to be empty. Post-Option-B, THREE tests become possible from ONE arm:

1. Re-run E4A's `GetAbilityByInputID(3)` → should return our spec pointer (not NULL).
2. Re-run E4A's `TryActivateAbilityByInputID(3)` → **if returns true and minion HP
   drops, WALL P is DEFEATED on the InputID pathway and the E4 predicate is met from
   a direct shim call** (no OS input needed).
3. Send OS LMB (send-lmb.ps1) after disarm → should now route to our spec via
   `HandleAbilityActivation → GetAbilityByInputID(3) → TryActivateAbility`.

The `false`-return in flight 1 could STILL be caused by a downstream gate even if
Option B populates the map — the message deliberately allows for that: `return=false
(activation refused: either InputID map missing our spec, or a downstream gate)`. So
Option B settles the "InputID map missing" branch definitively; if it still returns
false with the map populated, we've localized the wall further to a specific gate
(CanActivate, cost, cooldown, tag requirement, IsAbilityInputBlocked).

## Cost

- **1 launch**, first-try success (no FK-31 death, no FK-32 during the flight).
- 0 collateral: the game continued alive at 237s, cleanly killed post-flight.
- Zero source changes needed for the offline design vs the live measurement — my
  R-S191-h prediction was exactly correct.

## Regression gates + digests

- `botai b620e0ff3279e673` — UNCHANGED (master regression validator)
- `e4-a RAW=2d7efa4cde249f2e` — the flown build; verify_dll PASS, KERNEL32-only
- `--dupes` clean (no accidental byte-identical arms across the E4 family)
- All new code behind `#if KBFE4A`, no `#else`; policy `#error` guards (`KBFE4A`
  requires `KBFE4=1`, KBFE4A is a bool 0/1)

## Rules banked (extension of R-S191-h)

- **R-S191-h1** [now [M], upgraded from offline [I,strong]]: plain native
  `UAbilitySystemComponent::GiveAbility` populates the `Items` TArray but NOT the
  InputID→spec map. `GetAbilityByInputID` / `TryActivateAbilityByInputID` will not see
  a spec granted this way. Use `BP_AuthGiveAbilityWithInputID` for any InputID-aware
  activation pathway.
- **R-S191-j** [new [M]]: `ULokiAbilitySystemComponent::TryActivateAbilityByInputID` at
  `0x52971A0` is safe to call from a shim — returns cleanly with `false` when the
  InputID map has no matching spec. Distinct WALL P surface from S147/S158's
  `TryActivateAbilityByClass`-fatal shim-originated call.
- **R-S191-k** [new [M]]: single-flight adversarial-preregistered diagnostic (pre-read
  `GetAbilityByInputID` + call `TryActivateAbilityByInputID` + read minion HP delta +
  log the disjunction "InputID map missing our spec, or a downstream gate") is a
  reusable pattern for any GAS-activation investigation — gives 3 independent data
  points from ONE reflected call each.

## Files

- `docs/s191-e4a-flight1-marker.log` — shim marker (all [BF]+[E4]+[E4A]+[FS] receipts)
- `docs/s191-e4a-flight1-loki.log` — game log (~1.5 MB)
- `docs/s191-lmb-input-binding-mapped.md` — parent offline investigation (R-S191-h)
- `docs/s191-e4-flight3-RESULT.md` — parent E4 flight result (KE4DIRECTGE-killed a minion)
- `tools/sigbypass-mod/tutorial_launch.cpp` — `#if KBFE4A` block in BfE4SpawnSeedTarget
- `tools/sigbypass-mod/build.ps1` — `e4-a` variant

## Next step: Option B

Extend E4 with a new `KBFE4_GRANT_BY_INPUTID` knob (bool). When 1, replace the K_GRANT
step's plain-`GiveAbility` path with a reflected `BP_AuthGiveAbilityWithInputID` call
that takes the ability class + `Ability1=3`. Then re-run E4A's activation probe (which
can stay as-is) to confirm the InputID map is populated AND to test whether
`TryActivateAbilityByInputID(3)` now returns `true` + drops the minion's HP.

If Option B's flight shows `TryActivateAbilityByInputID(3)` returning `true` and the
minion HP dropping — the E4 predicate is met from a direct shim call, bypassing OS input
entirely. If it returns `true` but HP doesn't drop — the activation body ran but the
damage GE didn't land (targeting filter or PostGameplayEffectExecute gate). If it
returns `false` — a downstream activation gate (CanActivate/cost/cooldown/tag) is the
next wall to localize.
