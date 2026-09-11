# WALL P deep dive — `CallSpellCompleteEvent` refined (S153, 2026-09-02)

The S153 FK-1 topic cross-index (`docs/fk1-topic-crossindex-s153.md`) ranked
`ULokiGameplaySpell::CallSpellCompleteEvent` (thunk `0x5254180`, tail-jmp to
void_ret fold) as *"the most plausible mechanism for S147's 'no durable ability
body' phenomenon"* and recommended it as the S151 Move 3 BINDCENSUS priority
read. This deep dive refines that hypothesis with a specific test against
S147's actual target: **Ronin's MiniDash**.

**Bottom line:** the hypothesis is CORRECT for the 26 shipping spells that
manually call `CallSpellCompleteEvent`, and REFUTED for the 570 spells that use
the auto-fire path — INCLUDING MiniDash itself. WALL P's residual blocker in
S147 is not this stub.

## 1. The reflected surface

- **`ULokiGameplaySpell::CallSpellCompleteEvent`** — flags `0x04020401` =
  `Final|Native|Public|BlueprintCallable`. Signature `void()` (zero args).
  Thunk `0x5254180` (the 92-way ICF-shared universal `execFoo` zero-arg thunk
  with `jmp 0x0F7EC20` tail dispatch). **Body: STRIPPED — the wrapper unpacks
  the empty FFrame and tail-jumps to void_ret.**

- **`ULokiGameplaySpell::bManuallyCallSpellCompleteEvent`** — a **bool
  UPROPERTY** on the same class. Its very existence names the design intent:
  when TRUE, the ability must call `CallSpellCompleteEvent` manually from
  Blueprint; when FALSE (the default), some auto-fire path fires the
  completion event automatically.

- **`ULokiAbilitySystemComponent::OnGameplaySpellEnded`** — a
  `FGameplaySpellEnded` multicast delegate. This is the notification channel
  that whoever finishes the spell broadcasts on. `CallSpellCompleteEvent` was
  presumably (had it been implemented) the wrapper that broadcasts this.

## 2. Distribution across shipping spells

- **596 total `GS_*` gameplay-spell blueprints** in `tools/extractor/out/catalog/gs/`.
- **26 of 596 (4.4%)** set `bManuallyCallSpellCompleteEvent: true`. All 26 also
  reference `CallSpellCompleteEvent` somewhere in their bytecode → they are the
  MANUAL-FIRE population. These spells are **genuinely blocked** by the strip
  — their completion event will never fire because the function they call
  returns immediately.
- **570 of 596 (95.6%)** leave `bManuallyCallSpellCompleteEvent` at its default
  `false`, and none reference `CallSpellCompleteEvent`. These are the
  AUTO-FIRE population — their completion event fires from some OTHER code
  path when the state machine reaches an end state (montage-ended,
  channel-ended, dash-ended, etc.).

## 3. Which spells are in the manual-fire set?

All 26 of them (from `grep -l '"bManuallyCallSpellCompleteEvent": true'`):

| category | spells |
|---|---|
| AoE / positional | `GS_AirBlast`, `GS_AirBlast_Armory`, `GS_AoETeleport_ActivatePortals`, `GS_AoETeleport_Consumable_ActivatePortals`, `GS_AoETeleport_Consumable_CreatePortals`, `GS_AoETeleport_CreatePortals`, `GS_AoE_ManaCloud`, `GS_CreateAntiMobilityField`, `GS_TreePrison`, `GS_TreePrison_Armory` |
| Movement / mobility | `GS_BARRACUDAITEM_HoverWings`, `GS_HoverWings`, `GS_HoverWings_Armory`, `GS_Wukong_Leaping_Jump` |
| Projectile / bungee | `GS_BungeeShot`, `GS_BungeeShot_Armory`, `GS_BungeeShot_BattlegumS2` |
| Teleport / swap | `GS_Stalker_CloneSwap_TeleportCommand`, `GS_Replicate` |
| Utility / summon | `GS_CaptureBall_Active`, `GS_CreateTimeCube`, `GS_MoneyTree`, `GS_PlaceableFortress`, `GS_ManaCloak`, `GS_RescueGrenade_Starter`, `GS_BARRACUDAITEM_ShadowBlade` |

Common pattern: complex spells whose completion is a discrete event decided by
BP logic (portal linked, cube expires, tree destroyed, dash landed), not a
timer/montage-driven auto-complete.

## 4. S147's target: `GS_Ronin_MiniDash_Charges`

- **NOT in the manual-fire set.** `bManuallyCallSpellCompleteEvent` defaults
  to `false`; no reference to `CallSpellCompleteEvent` in its bytecode.
- Ronin's kit is 14 GS files (`GS_Ronin_*.json`); MiniDash is the Ability3
  slot per CLAUDE.md's WALL P history.
- MiniDash completes via the AUTO-fire path — probably montage-ended,
  dash-ended (via `HandleDashEnded`), or timer-expired.

**⇒ The synthesizer's hypothesis is FALSIFIED for S147's actual target.**
Stripping `CallSpellCompleteEvent` cannot explain MiniDash's "no durable
ability body" observation, because MiniDash never calls that function in the
first place. The blocker is somewhere else on the auto-fire path.

## 5. Auto-fire path — where to look next

The auto-fire path presumably reads `bManuallyCallSpellCompleteEvent == false`
in some native code, and — when the spell state machine reaches an end
condition — fires the completion event and broadcasts `OnGameplaySpellEnded`.
Candidate call sites on `ULokiGameplaySpell` (from `binds_members.csv`):

| function | flags | S153 verdict | note |
|---|---|---|---|
| `EndInvoke` | Native|BPCallable, void() | **DARK** (page 0x535F000) | Sibling zero-arg BPCallable — likely the state-end setter. UNKNOWN whether stripped or real. |
| `HandleDashEnded` | Native|Private, 2 args | **REAL** (0x5360BB0) | Dash completion callback. Follows the classic exec-wrapper shape; tail-calls the real handler at `0x552DF80`. |
| `OnMontageEnded` | Native|Private, unknown args | not enumerated | S153 sweep doesn't classify `Final|Native|Private` UFunctions that lack `StaticRegisterNatives` binding — instrument gap. |
| `OnAnimNotifyBeginPhaseCallback` | | DARK | Anim-driven completion trigger. |
| `OnRep_CurrentCharges` / `OnRep_ReplicatedPhaseData` | | DARK | Replicated state notifiers. |

**Highest-value next read** (offline, requires no live session): disassemble
`HandleDashEnded`'s ultimate impl at `0x552DF80` — a REAL body — to see the
completion pattern. If it broadcasts `OnGameplaySpellEnded` and clears state,
that's the auto-fire path in miniature. Replicating that pattern via
`SimulateInputReleasedForAI`-style direct injection may bypass whatever's
blocking MiniDash.

**Higher-value still, but LIVE-required**: fire MiniDash in a live tutorial
session, then read `EndInvoke`'s page `0x535F000` in the resulting dump — if
the page decrypts and reveals a real body, the auto-fire path executes
naturally and MiniDash's blocker is downstream (a delegate subscriber, a
cooldown timer, or a state-transition guard). If the page stays dark,
`EndInvoke` was never called on MiniDash, and its state machine is stalled
before reaching the invoke-end transition.

## 6. Preregistered live-read for the S151 Move 3 BINDCENSUS follow-up

After activating MiniDash, read (via RPM):
1. **`spec.bIsActive`** on the MiniDash `FGameplayAbilitySpec` (should be
   FALSE post-cast if auto-complete fired; TRUE if stalled).
2. **`spec.ActiveCount`** (should return to 0 if auto-complete fired).
3. **`ULokiAbilitySystemComponent+X.OnGameplaySpellEnded.InvocationList.Num`**
   — the count of subscribers on the delegate. If Num > 0 and yet no
   subscriber's callback fired in the live log, the delegate wasn't
   broadcast. If Num == 0, no listener exists and firing wouldn't matter.
4. **Page `0x535F000` readability in a post-cast `dumpimage`** — if lit,
   `EndInvoke` (or one of its sibling AuthAddCharge/AuthRemoveCharge functions)
   executed and the auto-fire path is at least PARTIALLY reachable; the block
   is downstream. If dark, the state machine never reached the invoke-end
   transition.

Discriminators:
- `bIsActive` TRUE post-cast + `OnGameplaySpellEnded` Num > 0 → **auto-fire
  handler is stripped/broken; delegate never fires** — try native call of
  `EndInvoke`'s impl (if newly-decrypted) to test.
- `bIsActive` TRUE post-cast + `OnGameplaySpellEnded` Num == 0 → **no
  subscriber; completion notification path was never wired up in this build**
  — the blocker is state-mutation-level, not notification-level.
- `bIsActive` FALSE post-cast → **auto-complete fired successfully** and the
  "no durable ability body" observation must be explained by something OTHER
  than completion — likely GAS effect application on the Invoke side, not the
  End side.

## 7. What this changes about the cross-index

| claim (cross-index R-S153-e / synth §3) | verdict after deep dive |
|---|---|
| `CallSpellCompleteEvent` is stripped | ✓ CONFIRMED, unchanged |
| It's the most plausible mechanism for S147's "no durable body" | **REFUTED** for MiniDash specifically (auto-fire); still holds for the 26 manual-fire spells |
| Priority read for S151 Move 3 BINDCENSUS | Read `bIsActive`/`ActiveCount`/`OnGameplaySpellEnded.Num` INSTEAD of assuming CallSpellCompleteEvent is the block; use the discriminators above |

The 5 `ULokiSpellSwapper` stripped stubs finding is **untouched** and remains
the strongest "entire subsystem gutted" claim from the cross-index. And the
26 manual-fire spells' blocker verdict is **untouched** — those really are
blocked by the CallSpellCompleteEvent strip.

## 8. Reusable rules banked

- **R-S153-g:** A stripped-stub cross-index hypothesis that names a specific
  UFunction as blocking a specific behaviour MUST be checked against the
  shipping asset population that actually calls that UFunction. `Call
  SpellCompleteEvent` looked like a smoking gun until we noticed that 96 % of
  spells (INCLUDING the S147 target) never call it.
- **R-S153-h:** A `b*` UPROPERTY named `bManually<Verb>` is a strong hint that
  a non-manual (auto) path exists elsewhere. Grep the shipping BP catalog for
  the value distribution before assuming the manual verb is the only path.

## Files

- `scratchpad/s153_topic_crossindex_agent1.md` — the WALL P fan-out that first
  identified `CallSpellCompleteEvent` as the hypothesis
- `scratchpad/s153_topic_crossindex_synth.md` — the synthesizer output that
  promoted it to R-S153-e
- `docs/fk1-topic-crossindex-s153.md` — the parent cross-index
- `docs/fk1-native-sweep-s153.md` — the S153 sweep
- `tools/extractor/out/catalog/gs/GS_Ronin_MiniDash_Charges.json` — S147 target,
  auto-fire path
- `tools/extractor/out/catalog/gs/GS_AirBlast.json` (+25 more) — the manual-fire population
