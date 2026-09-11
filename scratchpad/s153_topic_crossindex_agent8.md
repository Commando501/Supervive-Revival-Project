## AGGREGATE

**38 STRIPPED stubs** across 10 distinct fold thunks are on this topic's critical path (mission progression, XP grant, stat write/read, gold grant, gameplay-tag reporting). Stat writers dominate (11 `Add*Stat` on 0x52FD8F0); stat getters return zero via two folds (0x5436E40 int, 0x5349FB0 float, 10 total).

## TOP-10 HIGHEST-IMPACT

- **ALokiMissionObjective::AddProgress  thunk=0x52FD620**
  blocks: server-authority increment of an objective counter — this is the NATIVE sibling to CLAUDEmd's Blueprint-gated `ProgressObjective` wall (S92/S93/S134). in_fk1_register: no · icf_share: 9-way (AuthCheatSetHealth sibling) · bypass_status: **GENUINELY_BLOCKING**

- **ALokiPlayerState_Missions::OnMissionDone  thunk=0x5254180**
  blocks: server-side completion callback that would fire mission-done UI/reward events. no · 92-way · **GENUINELY_BLOCKING**

- **ALokiPlayerState_XP::SetFinalXPCategories  thunk=0x5254180**
  blocks: end-of-game XP category finalization → no post-match XP delta ever computed client-side. no · 92-way · **GENUINELY_BLOCKING**

- **ALokiCharacter::AuthGrantLevel  thunk=0x52FD8F0**
  blocks: character level grant — CLAUDEmd already records this stripped ("BotLevel is a MEASURED NO-OP via SetBotToLevelX → AuthGrantLevel"). no · shared (14+ way on 0x52FD8F0) · **GENUINELY_BLOCKING**

- **ALokiCharacter::AuthInitializeExperience  thunk=0x52FD8F0**  +  **ALokiPlayerCheats::CheatSetXP  thunk=0x52FD8F0**
  blocks: character XP initialization and cheat setter. no (either) · shared · **GENUINELY_BLOCKING**

- **ALokiPlayerState::Add{Kill,Deaths,Assist,Knocks,Knocked,Revives,Revived,Resurrects,Resurrected,SpikeKills,SpikeDeaths}Stat  thunk=0x52FD8F0**
  blocks: eleven per-event stat writers; nothing on the client mutates the local `LokiPlayerState_Stats` counters. no · shared · **PROVEN_ALT_CALL_PATH** (S121: CAREER→STATS renders from backend `/player-stats/players/{id}` — the client never needed these to write).

- **ALokiPlayerState::Get{Kills,Deaths,CreepScore,CurrentKillStreak,Knocked}  thunk=0x5436E40** + **Get{DamageDone,HealingGiven,HeroDamageDone,HeroDamageTaken}  thunk=0x5349FB0** + **AuthGetTeamSurvivalTime  thunk=0x5349FB0**
  blocks: client stat getters return 0/0.0f. Any HUD that read these directly (vs served backend stats) shows zeros. no · shared int/float folds · **PROVEN_ALT_CALL_PATH** for served surfaces; **UNKNOWN** for HUD paths not measured.

- **ULokiBlueprintLibrary::AuthGrantGoldToActor  thunk=0x52E0890**  +  **AuthGrantGoldToTeam  thunk=0x52E0AC0**
  blocks: in-match gold grant to actor or team → no combat/objective/mission gold economy on this client. no · unshared each · **GENUINELY_BLOCKING**

- **ALokiMinionCharacter::SetMajorReward  thunk=0x54064F0**
  blocks: sets the "big minion" bounty flag consumed by kill-reward payout. no · unshared · **GENUINELY_BLOCKING**

- **ALokiPlayerController::SendGameplayTagsReport  thunk=0x5254180**  +  **ABarkManager::CheatRequestGameplayTag  thunk=0x52540A0**
  blocks: server-authority gameplay-tag mutation and telemetry. no · 92-way / 92-way · **GENUINELY_BLOCKING** for authoritative tag application.

- **ABaseMission::OnObjectiveAssetsLoaded  thunk=0x5254180** · **ALokiMissionObjective::{ClearContext,FailMission}  thunk=0x5254180**
  blocks: server-side objective lifecycle callbacks. no · 92-way each · **CANDIDATE_ALT_CALL** — S119's native missions ingest already loads assets and rebuilds models via a different path (`AsyncLoadPrimaryAssets` + `MakeMissionModel`); these callbacks are inert but not required for the render path CLAUDEmd already proved working.

## NEW-INFO ASSESSMENT

Of 38 hits: **~10 were already known** — CLAUDEmd explicitly names `AuthGrantLevel` (SetBotToLevelX no-op), `AuthGetTeamSurvivalTime`, and the FK-1 register's 9-way `AuthCheatSetHealth` sibling reveals `AuthCheatSetMana`/`AddProgress` share the same fold; S152's `Auth*/Server*/*Cheat*` filter would have caught `AuthAddAbilityPoints`, `AuthInitializeExperience`, `AuthGrantGold*`, `CheatExperience`, `CheatSetXP`, `CheatRequestGameplayTag`. **~28 are genuinely new** to the register/hunts — all 11 `Add*Stat` writers (start with `Add`, not the S152 filter), all 5 mission/objective callbacks (`On*`, `Add*`, `Clear*`, `Fail*`), `SetFinalXPCategories`, `SetMajorReward`, `SendGameplayTagsReport`, and the 10 zero-return stat getters.

## BLOCKS-WHAT SUMMARY

Local mission progress, in-match XP/level grant, in-match gold economy, per-event stat writes, and authoritative gameplay-tag reports are ALL server-authority-stripped on this client — the entire "match generates progression" pipeline is a no-op locally. What survives works: post-match progression PRESENTATION (S119 missions, S120 mastery, S121 stats, S122 rank) is fed by backend HTTP echoing pre-computed state to already-real ingest/render paths, and mastery claims auto-fire via `UnclaimedRewards` (S120). Delivering a real progression LOOP (bot-fight kill → stat write → mission progress → XP grant → level up → claimed reward) requires the same class of intervention as FK-1's four drop-phase stubs: either data-poke the fields these stubs would have written (S130 `bCanEverReplicate` / S131 `PlayersAttached` precedent) or serve the deltas from `ags` and let the existing HTTP push paths adopt them.