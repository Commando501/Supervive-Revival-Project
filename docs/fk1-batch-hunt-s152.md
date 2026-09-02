# FK-1 batch hunt — S152 addendum

**Date:** 2026-09-02
**Method:** live disassembly on PID 41816 (Move 4 process, 12.1h uptime)
**Scope (v1):** UFunctions matching `Auth*`, `Server*`, `*Cheat*`
**Scope (v2, extended same session):** adds `Grant*`, `Kick*`, `Ban*`, `Broadcast*`,
`Debug*`, and Loki-scoped `Init*`/`Force*`
**Tool:** `scratchpad/move4_fk1_batch_hunt.py`
**Result:** 95 STRIPPED entries confirmed live (83 v1 + 12 v2), out of 746 candidates.

## Method

Applies the S152 discovery pattern (external poke arc, `AuthCheatSetHealth`
disassembly finding):

1. Walk `GUObjectArray` on the live process, filter to `UFunction` objects
   whose name matches `Auth*`/`Server*`/`*Cheat*`.
2. For each match, read `Func @+0xE0` — the reflected native entry point.
3. Disassemble up to 128 instructions or the first `ret`.
4. Look for the last `call <known_fold>` before the ret. Known folds
   (from CLAUDE.md's FK-1 block + S131 census):
   - `0xF7EC20` void_ret (`c2 00 00`)
   - `0xF7EB50` xor eax,eax; ret (nullptr / false)
   - `0xF7EB60` xor al,al; ret (LokiIsServer HARDCODED FALSE)
   - `0xB9E1F0` mov al,1; ret (LokiIsClient HARDCODED TRUE)
   - `0xFC6CF0` xorps xmm0,xmm0; ret (0.0f)
5. Classify: STRIPPED if a fold-call is present in the body; REAL otherwise;
   UNREADABLE if the Func page is `PAGE_NOACCESS` (undecrypted, never
   executed).

## Summary

| verdict | count | %    |
|---------|------:|-----:|
| REAL    |   511 | 68.5 |
| STRIPPED |   95 | 12.7 |
| UNREADABLE | 140 | 18.8 |
| **total** | **746** | 100 |

Extended (v2) added 12 new STRIPPED entries beyond the v1 Auth*/Server*/*Cheat*
sweep, and 122 candidates (mostly REAL Init*/Grant*/Force* on stock UE classes
filtered by the Loki-scope check).

Fold-target distribution among the 95 STRIPPED:

| fold | count | meaning |
|------|------:|---------|
| `0xF7EC20` | 80 | void return / no-op setter |
| `0xF7EB60` | 12 | LokiIsServer hardcoded FALSE (predicate returns FALSE) |
| `0xF7EB50` |  2 | nullptr/false getter |
| `0xFC6CF0` |  1 | 0.0f float getter |

## Notable findings

### Confirms known FK-1 entries
- `AuthSetSpawnTeamLeader` (ULokiPlayerState) — matched entry #2 in FK-1
  register.
- `AuthCheatSetHealth` (ULokiCharacter) — matched S152's 5th entry.
- `ServerSetHeroClass` (ULokiPlayerState) — CLAUDE.md's FK-1 block cites
  this as `-> 0xF7EC20 void fold`; independently confirmed here.

### New entries connecting to open rideable/drop-phase work
- `AuthAddPlayer`, `AuthRemovePlayer`, `AuthSetCanJump` on
  `LokiRideableComponent` — the exact set S131 documented as blocking pod
  mount. Confirmed all three stripped.
- `AuthKnockedActorEnter`, `AuthKnockedActorExit` on `LokiHeroCharacter` —
  the "knock" state transitions.
- `AuthBeginGlideDiveFromDropPod` on `LokiCharacterMovementComponent` —
  the FK-22-cited pod dismount entry.

### New entries connecting to WALL E / bot work
- `AuthAnyVisibleEnemyHeroCharactersInRange` on `LokiMinionCharacter` —
  hostility predicate, stripped (returns FALSE).
- `AuthUpdateEnemyList`, `AuthUpdateNearbyVisibleEnemies` on
  `LokiMinionCharacter` — enemy tracking, stripped.
- `AuthReflectProjectile`, `AuthDetonate`, `AuthForceExplode`,
  `AuthFuseExpired`, `AuthStartFuseTimer`, `AuthAddDamageMultiplier` on
  `LokiProjectile` — no projectile combat behavior available client-side.

### Cheat verbs (all stripped)
- `LokiPlayerCheats`: `CheatAddMissionProgress`, `CheatSetRankedPoints`,
  `CheatSetXP`, `CheatTeleportCursor`, `CheatTravelToMainMenu`,
  `AreHotkeyCheatsEnabled`, `GetLocalLokiPlayerCheatsBP` (returns nullptr).
- `LokiCharacter`: `AuthCheatSetHealth`, `AuthCheatSetMana`, `CheatExperience`.
- `LokiGameMode`: `CheatCantEndGame`, `DevGameModeCheatsEnabled`,
  `GameModeCheat`.
- `LokiBlueprintLibrary`: `CheatsEnabled` (returns FALSE — corroborates FK-13's
  finding that `ULokiBlueprintLibrary::CheatsEnabled` is a stripped predicate).

### Sub-family: `LokiOpeningClosingProp` — fully stripped
All four `Auth*` verbs (`Pause`, `StartClosing`, `StartOpening`, `StartToggle`)
strip to `0xF7EC20`. Interactive props are non-actionable client-side.

### Sub-family: `LokiTower` — fully stripped
All four measured `Auth*` verbs strip to `0xF7EC20`.

### Sub-family: `LokiBaseItem` — 7 of ~7 Auth* stripped
Every visible `Auth*` movement/tracking verb on `LokiBaseItem` is stripped.

### Interesting singletons
- `AuthGetTeamSurvivalTime` on `LokiPlayerState` — a float getter that returns
  `0.0f` unconditionally. The only `0xFC6CF0` (float-zero return) hit in the
  sweep.
- `IsEasyAntiCheatEnabled` on `LokiGameInstance` — hardcoded FALSE
  (`xor al,al; ret`).
- `IsDebugCameraCheatsOnly` on `LokiPlayerState` — hardcoded FALSE.

## Instrument caveats

- **ICF folding at Func level**: many entries share the same Func RVA
  (e.g. `0x05254180` — the 91-way-folded 91-instance `execFoo` thunk
  documented in CLAUDE.md). These entries share ONE physical thunk on the
  live process but are registered on distinct `UFunction` objects. When
  applying to an FK-1 register, the fold identity is per-`UFunction`, not
  per-thunk RVA.
- **UNREADABLE = latent, not confirmed stripped**: 124 candidates live on
  `PAGE_NOACCESS` pages (never demand-decrypted by the packer in this
  process). They could be REAL (never run) or STRIPPED — cannot tell
  without executing them. Notably the entire `AbilitySystemComponent`
  Server*RPC surface is UNREADABLE on this menu-tutorial route.
- **Sweep is NOT exhaustive**: only Auth*/Server*/*Cheat*-prefixed names.
  Other stripped stubs exist under different naming (`Set*`, `Init*`,
  `Get*`, private impls named by their author).
- **Method rule S152**: the S152 core lesson holds — a prologue-signature
  check would classify 100% of these 83 stubs as "real" (they all have
  standard MSVC UHT exec-wrapper prologues). Only the tail-call analysis
  distinguishes them.

## Base-rate context

CLAUDE.md's FK-1 block cites "Empty-impl base rate in this image is
**1.2 %** (78/6,669)". This targeted sweep gives:
- STRIPPED rate on `Auth*`/`Server*`/`*Cheat*`: **13.3 %** (83/624)
- If we filter to LOKI classes only (excluding stock UE `APlayerController`
  Server* verbs, `AbilitySystemComponent` UNREADABLE entries, etc.), the
  effective rate on the auth-family Loki namespace is much higher —
  well over half. This confirms FK-1's observation:
  *"The enrichment is on `Auth*` naming, not on subsystem."*

## Impact per subsystem for future arms

| subsystem                                | walls this hunt names |
|-|-|
| Rideable / pod mount                     | AuthAddPlayer, AuthRemovePlayer, AuthSetCanJump |
| Drop phase                               | AuthStart (DropPlane), AuthBeginGlideDiveFromDropPod, AuthHandlePlayerPawnUpdated |
| Combat (bot pipeline)                    | AuthAnyVisibleEnemyHeroCharactersInRange, AuthUpdateEnemyList, AuthUpdateNearbyVisibleEnemies |
| Damage / hero state                      | AuthAddPreSpawnedEffect, AuthCombatActionEnded, AuthCombatActionInitiated, AuthKnockedActorEnter/Exit |
| Character progression / cheats           | AuthAddAbilityPoints, AuthGrantLevel, AuthInitializeExperience, AuthRemoveAbilityPoint, AuthRemoveLevel |
| Projectile behavior                      | AuthDetonate, AuthForceExplode, AuthFuseExpired, AuthReflectProjectile, AuthStartFuseTimer, AuthAddDamageMultiplier |
| Team state                               | AuthSetStashedTeamGems, AuthStashTeamGems, AuthHandlePlayerPawnUpdated |
| Interactive props                        | AuthPause, AuthStartClosing, AuthStartOpening, AuthStartToggle |
| Server config                            | AuthSetGameFeatureToggle |

Each named entry is a **guaranteed no-op if called via the S55 primitive
or reflection**. Any shim design that plans to call one of these instead
of poking equivalent state is a wasted injection.

## Full data

See `scratchpad/move4-fk1-batch-hunt.out.log` for the full 624-row
verdict table.

## Reusability

`scratchpad/move4_fk1_batch_hunt.py` is generic — it takes a PID and
enumerates all `Function`-class UObjects. The pattern filter is a single
regex constant. To extend the sweep:
- Change `NAME_PATTERNS` to match different verb families.
- Add new fold RVAs to the `FOLDS` dict as they're discovered.
- Run again live; new stripped hits will be classified automatically.

## v2 extended sweep — additional 12 STRIPPED entries

Same session, same live process, extended the pattern filter to
`Grant*|Kick*|Ban*|Broadcast*|Debug*|Init*|Force*` (Init/Force scoped to
Loki-family outer classes to reduce stock-UE false positives).

**New STRIPPED entries in v2 (not present in v1):**

| function | outer class | Func RVA | fold |
|-|-|-|-|
| `DebugMessage` | `LokiGameplayAbility` | `0x05256880` | `0xF7EC20` void |
| `DebugSendDirectMessageToPlayer` | `ChatManager` | `0x05254180` | `0xF7EC20` void |
| `DebugSetLevels` | `RewardTrackerViewModel` | `0x054DF940` | `0xF7EC20` void |
| `DebugTimelineAdvanceTime` | `LokiPlayerController` | `0x052FD620` | `0xF7EC20` void |
| `DebugTimelineReset` | `LokiTimelineManager` | `0x05254180` | `0xF7EC20` void |
| `DebugTimelineResetAndPause` | `LokiTimelineManager` | `0x05254180` | `0xF7EC20` void |
| `DebugTimelineResume` | `LokiTimelineManager` | `0x05254180` | `0xF7EC20` void |
| `DebugTimelineSetTime` | `LokiPlayerController` | `0x052FD620` | `0xF7EC20` void |
| `ForceComplexMovement` | `LokiProjectileMovementComponent` | `0x05254180` | `0xF7EC20` void |
| **`ForceDeath`** | **`LokiCharacter`** | `0x05289020` | `0xF7EC20` void |
| `ForceVisibleTagChangedCallback` | `LokiCharacter` | `0x052FF100` | `0xF7EC20` void |
| `GrantWalletCurrency` | `LokiPlayerState` | `0x05437BE0` | `0xF7EC20` void |

**Notable in v2:**
- **`LokiCharacter::ForceDeath` is stripped.** The "kill the character" verb
  does nothing when called via reflection. If a future arm wanted to test
  death handling by force-killing the hero, this route is a dead end. Combined
  with S152's death probe (writing `Health = 0` produced zero game-side
  reaction), the "kill hero" path is fully closed client-side.
- **Debug Timeline surface is entirely stripped** — 5 verbs across
  `LokiTimelineManager` and `LokiPlayerController`. Consistent with
  `LogTimelineManager` producing zero output on this route.
- **`GrantWalletCurrency` stripped** — mirrors the FK-13 finding about cheat
  bodies being real-wrapper stubs.

## Full data (both v1 + v2)

See `scratchpad/move4-fk1-batch-hunt-v2.out.log` for the full 746-row
verdict table (v2 supersedes v1's `move4-fk1-batch-hunt.out.log`, which is
also preserved).
