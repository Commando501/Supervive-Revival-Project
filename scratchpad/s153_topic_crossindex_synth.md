# S153 FK-1 stub cross-index - which stripped stubs block which walls (2026-09-02)

## Summary table

| TOPIC | STRIPPED STUBS ON CRITICAL PATH | ALREADY-KNOWN (register/S152/S153-exec) | NEW-INFO |
|---|---:|---:|---:|
| WALL P (ability activation) | 29 | ~22 | **7** (all ULokiGameplaySpell + ULokiSpellSwapper) |
| WALL E (bot hostility, damage) | 30 | ~29 | **1** (EliminateTeam) |
| Drop chain | 18 | ~10 | **~8** (glide/parachute Gather*, plane Auth*) |
| Mount/dismount | 13 | ~7 | **~6** (DropPlane rider verbs, PlayerDropPlaneComponent) |
| Movement wall (CMC/GAS) | 9 | ~8 | **1** (EndFollowingActor + AuthBeginGlideDive bare) |
| Missions/XP/stats | 38 | ~10 | **~28** (11 Add*Stat writers, 10 stat getters, callbacks) |
| Match lifecycle | 21 | ~12 | **~9** (EliminateTeam, SetIsEliminated, SetPlayerTeam, etc.) |
| Netcode/RPC/replication | ~12 | ~7 | **~5** (Nexon login, cue push, gameplay-tag toggle) |
| **TOTAL** (with cross-topic overlap) | **~170 unique** | **~105** | **~65** |

## Cross-topic multi-blockers

Stubs appearing in ≥2 topic analyses — highest-leverage kills:

- **ALokiGameMode::SpawnPlayer** (0x534C070) — Drop chain, Match lifecycle. FK-1 register #1. Bypassed by S135/S137 `SpawnAIFromClass`.
- **ALokiTeamState_TeamOnly::SetDropLeader** (0x2C2CE30) — Drop chain, Mount, Match lifecycle. FK-1 register #3.
- **ALokiPlayerState::AuthSetSpawnTeamLeader** (0x5254180) — Drop chain, Match lifecycle. FK-1 register #2.
- **ALokiDropPlane::OverridePlaneLocations** (0x53372A0) — Drop chain, Mount. FK-1 register #4. GENUINELY_BLOCKING for dynamic paths.
- **ULokiRideableComponent::AuthAddPlayer / AuthRemovePlayer / AuthPlayerEnterWorldNew** — Drop chain, Mount. S132 data-poke bypass.
- **ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod** (0x530BFD0) — Drop chain, Mount, Movement.
- **ALokiPlayerState::ServerSetHeroClass** (0x5438720) — WALL E, Netcode. Bypassed by S135/S137.
- **ALokiGameState::SetPlayerTeam** (0x538AA70) — WALL E, Match lifecycle, Netcode. CANDIDATE_DATA_POKE.
- **ALokiGameState::SetNumTeams** (0x52FD8F0) — WALL E, Match lifecycle. GENUINELY_BLOCKING.
- **ALokiCharacter::AuthCheatSetHealth** (0x52FD620) — WALL E, Movement. FK-1 register #5. S153 thunkExact fix pending live test.
- **ALokiGameMode::EliminateTeam** (0x5349CB0) — WALL E, Match lifecycle. GENUINELY_BLOCKING for win conditions.
- **ALokiDropPlane::AddPlayerToPlane** (0x2C2CE30) — Drop chain, Mount.
- **ALokiMissionObjective::AddProgress** (0x52FD620) — Missions. Shares 9-way ICF with FK-1 #5.

## Top 20 highest-impact stripped stubs across all topics

| class::name | thunk_rva | blocks | in_fk1_register | icf_share | bypass_status |
|---|---|---|---|---|---|
| ALokiGameMode::SpawnPlayer | 0x534C070 | Real hero deploy through round mode | YES #1 | unshared | PROVEN_ALT (SpawnAIFromClass) |
| ALokiPlayerState::AuthSetSpawnTeamLeader | 0x5254180 | Team-leader designation for pod path | YES #2 | 92-way | CANDIDATE_DATA_POKE |
| ALokiTeamState_TeamOnly::SetDropLeader | 0x2C2CE30 | GetTeamDropLeader returns null | YES #3 | 23-way | CANDIDATE_DATA_POKE |
| ALokiDropPlane::OverridePlaneLocations | 0x53372A0 | Dynamic plane routing | YES #4 | unshared | GENUINELY_BLOCKING |
| ALokiCharacter::AuthCheatSetHealth | 0x52FD620 | Self-damage calibration + health writes | YES #5 | 9-way | PROVEN_ALT (S153 fix, unflown) |
| ULokiGameplaySpell::CallSpellCompleteEvent | 0x5254180 | Spell completion → cooldown/next-cast | no | 92-way | CANDIDATE_ALT_CALL |
| ULokiSpellSwapper::SwitchSpell | 0x52FD2D0 | Any hero with rotating kits | no | other | GENUINELY_BLOCKING |
| ALokiPlayerState::ServerSetHeroClass | 0x5438720 | Hero class RPC on PlayerState | no | unshared | PROVEN_ALT (S135/S137) |
| ALokiGameState::SetPlayerTeam | 0x538AA70 | Team assignment | no | unshared | CANDIDATE_DATA_POKE |
| ALokiGameState::SetNumTeams | 0x52FD8F0 | Initialize TeamStates array | no | shared 14+ | GENUINELY_BLOCKING |
| ALokiGameMode::EliminateTeam | 0x5349CB0 | Match-end trigger | no | unshared | GENUINELY_BLOCKING |
| ALokiMinionCharacter::AuthAnyVisibleEnemyHeroCharactersInRange | 0x5403AB0 | Hostility predicate | no | unshared | GENUINELY_BLOCKING |
| ALokiMinionCharacter::UpdateTargetEnemy | 0x54071C0 | Enemy actor selection | no | unshared | GENUINELY_BLOCKING |
| ULokiRideableComponent::AuthAddPlayer | 0x2C2CE30 | Rider attach | no | 23-way | PROVEN_DATA_POKE (S132) |
| ULokiRideableComponent::AuthRemovePlayer | 0x2C2CE30 | Rider detach | no | 23-way | PROVEN_ALT (S132 AuthPlayerDetach) |
| ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod | 0x530BFD0 | Pod→glide handoff | no | unshared | PROVEN_ALT (S150-drop) |
| ALokiMissionObjective::AddProgress | 0x52FD620 | Server objective increment | no | 9-way | GENUINELY_BLOCKING |
| ALokiCharacter::AuthGrantLevel | 0x52FD8F0 | In-match level grant | no | shared | GENUINELY_BLOCKING |
| ULokiAbilitySystemComponent::AuthExecuteLocalGameplayCueOnClient | 0x5294660 | VFX/SFX cue push | no | other | CANDIDATE_ALT_CALL |
| ULokiBlueprintLibrary::AuthGrantGoldToActor | 0x52E0890 | In-match gold economy | no | unshared | GENUINELY_BLOCKING |

## Per-topic capability summaries

- **WALL P** — CAN reach InitAbilityActorInfo bind, GiveAbility spec commit, Mana cost debit, CanActivate → InputID state transition (S143–S147). CANNOT deliver spell-completion events, spell-swap for rotating-kit heroes, local gameplay-cue VFX, or Ronin-dash cooldown overrides. CallSpellCompleteEvent is the most plausible "no durable body" mechanism.
- **WALL E** — CAN mount an authoritative bot fight via full data-substitution (TeamStates, enemy-list TArrays, per-projectile damage constants). CANNOT use any of the game's own server-authority paths: team identity, hostility perception, damage scaling, and win conditions are all void folds requiring poked state instead.
- **Drop chain** — CAN deliver full deploy via S150-drop bypasses (rider poke, procedural plane path, S131 pod ride, S132 dismount, S150 landing). CANNOT authentically source hero from SpawnPlayer, produce leader-designated pod crew, or execute the pod→glide→landing arc — all substituted with teleports.
- **Mount/dismount** — CAN complete full mount/ride/dismount cycle end-to-end (S150-drop 2026-09-01 landed a walking hero). CANNOT deliver dynamic plane routing, leader-pod formation, or any shipping-safe path — every recipe is diagnostic-only.
- **Movement wall** — CAN transition movement states via `MovementMode`+`Velocity` data pokes (S141 T3-B `PendingLaunchVelocity`). CANNOT reach S141-T3's open question via this stub set — the `CalcVelocity` clamp is stock UE, not on this list.
- **Missions/XP/stats** — CAN present post-match progression via backend HTTP + existing HTTP push (S119/S120/S121/S122). CANNOT execute any in-match progression loop; every stat writer, XP grant, gold grant, and objective increment is a void fold.
- **Match lifecycle** — CAN deliver pawn-in-world sitting with `GoToPhase`-driven cascade to `EGP_Combat` (FK-22/S124). CANNOT deliver authoritative match resolution — no team can be marked eliminated from the client.
- **Netcode/RPC** — CAN deliver everything the client already does via `ags` HTTP + WebSockets. CANNOT deliver true server→client GAS/gameplay-cue push or RPC-based team/hero assignment — but these are largely IRRELEVANT because `GetNetMode() == NM_Standalone` (S137).

## Gaps

- **Movement wall (9 hits, mostly known)** — the S141-T3 open question (what zeros the bot's `Velocity` from rest, what clamps `MaxInputSpeed`) is NOT in the stripped set. The relevant code is stock UE `PhysFalling` / `CalcVelocity`, which the protector doesn't strip. **Architectural**, not stub-driven.
- **Netcode (~12 hits)** — most netcode "gaps" are architectural: standalone netmode makes RPC surface irrelevant. The stubs enumerated here are cosmetic (Discord, Nexon) or already-replaced (`AuthSetGameFeatureToggle` via `handleClientConfig`).
- **WALL P Handle-1/INDEX_NONE asymmetry** — the S146 finding that valid-handle activation exits `0xDEAD` while `INDEX_NONE` returns cleanly is NOT explained by any stub on this list. Likely downstream of activation selection, protector-triggered kill, or the `runtime.dll+1` kill primitive (S131 §7).

## New-information roll-up

- **FK-1 register (5 entries):** All 5 covered by cross-index topics. No expansion candidates from register overlap alone.
- **S152 batch hunt (95 stubs):** ~80 of this cross-index's ~170 unique hits reconfirm S152. Independent third-instrument confirmation of the "Auth* naming convention is the enriched category" finding.
- **S153 exec sweep (32 exec verbs):** Largely disjoint from these Blueprint-callable stubs — the two sweeps complement rather than overlap.
- **Genuinely new to any register: ~65 stubs.** Highest-value expansion candidates for a future FK-1 register: the 5 ULokiSpellSwapper verbs, ULokiGameplaySpell::CallSpellCompleteEvent, all 11 ALokiPlayerState `Add*Stat` writers, ALokiMissionObjective::AddProgress, ALokiGameMode::EliminateTeam, ALokiTeamState::SetIsEliminated, and the 4 non-`Auth*` ALokiDropPlane rider verbs.

## Reusable-rule roll-up

Patterns worth banking as future rules:

1. **The entire ULokiSpellSwapper subsystem is gutted** — SwitchSpell, NextSpell, PreviousSpell, AddSubSpell, RemoveSubSpell all fold. Any hero routing through this class is dead by design. **[R-S153-a]**
2. **The 11-writer ALokiPlayerState `Add*Stat` family is uniformly void_ret** (all on 0x52FD8F0, shared 14+ ways). If a stat-writer name starts with `Add`, assume folded and check backend passthrough instead. **[R-S153-b]**
3. **10 stat-getter void folds on 0x5436E40 (int) and 0x5349FB0 (float) return zero universally** — any HUD reading these directly (vs backend-served) shows zeros. Sibling naming convention: `Get{Kills,Deaths,Damage*,Healing*}`. **[R-S153-c]**
4. **The 4-fold set is genuinely 5** — S131's `0x00FC6CF0 = xorps xmm0,xmm0; ret → 0.0f` fold caught 13 records including 6 ALokiPlayerState float getters. Any fold census must include it. **[R-S153-d, restated]**
5. **9-way ICF at 0x52FD620 is a "DebugTimeline / cheat setter" family** — AuthCheatSetHealth, AuthCheatSetMana, AuthAddDamageMultiplier, AddProgress, AuthStart all share it. A stub on this thunk is likely a cheat-verb or Auth-adjustment path. **[R-S153-e]**
6. **The Auth*/naming convention is the enrichment axis, not subsystem membership** — reconfirms S131 lane-d finding (Fisher p=1.6e-28). Drop-8 classes are not enriched vs the rest of the Loki table (14.6 % vs 9.83 %, p=0.11); server-authority naming is. **[R-S131, reconfirmed]**
7. **Bypass-status typology now stabilizes at 4 values:** PROVEN_ALT_CALL_PATH, PROVEN_DATA_POKE, CANDIDATE_DATA_POKE, GENUINELY_BLOCKING. UNKNOWN should collapse to CANDIDATE_* once downstream is measured. **[R-S153-f]**