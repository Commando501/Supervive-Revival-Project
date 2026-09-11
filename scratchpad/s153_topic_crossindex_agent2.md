**AGGREGATE:** ~12 STRIPPED stubs are on the netcode/RPC/replication critical path (out of 318 total STRIPPED). The wider "server-authority gameplay" set is much larger but belongs to other topics.

**TOP-10 HIGHEST-IMPACT hits**

- **UAuthManager::TryLoginWithNexon  thunk=0x5249D40** (also `TryLoginWithNexonLauncher`, and `ULoginManager` mirrors)
  blocks: Nexon SSO login RPC path (returns `LokiIsServer FALSE` universally).
  in_fk1_register: no · icf_share: other (4-way with Login mirrors) · bypass_status: PROVEN_ALT_CALL_PATH (Steam login via `ags` is the shipping route; Nexon path is dead by design).

- **UChatManager::DebugSendDirectMessageToPlayer  thunk=0x5254180**
  blocks: server-side direct-message dispatch to another player.
  in_fk1_register: no · icf_share: 92-way (universal `execFoo` void_ret) · bypass_status: CANDIDATE_ALT_CALL (chat frames actually route through the `/lobby` WebSocket; FK-15 settled dispatch — `UChatManager` isn't the RPC surface the game uses).

- **ULokiAbilitySystemComponent::AuthExecuteLocalGameplayCueOnClient  thunk=0x5294660**
  blocks: server→client gameplay-cue push (VFX/SFX activation without a real GAS server).
  in_fk1_register: no · icf_share: other (small fold family) · bypass_status: CANDIDATE_DATA_POKE (cues are locally executable via ASC's own cue manager; a direct call on the ASC with a poked FGameplayCueParameters is untested).

- **ULokiAbilitySystemComponent::ServerSetAbilityToLevel  thunk=0x5296B80**
  blocks: leveling an ability spec via the server.
  in_fk1_register: no · icf_share: unshared · bypass_status: CANDIDATE_DATA_POKE (poke `FGameplayAbilitySpec.Level` on the live `ActivatableAbilities` array; S145 already reads/writes ASC state directly).

- **ALokiPlayerState::ServerSetHeroClass  thunk=0x5438720**
  blocks: server RPC to bind a hero class to a PlayerState; part of the SpawnBot handoff.
  in_fk1_register: no (but named as a stripped fold in the S138 WALL C block) · icf_share: unshared · bypass_status: GENUINELY_BLOCKING for SpawnBot's full path; PROVEN_ALT_CALL_PATH for standalone pawn spawn (S135/S137 bypass via `SpawnAIFromClass` + direct PlayerState link).

- **ALokiGameState::SetPlayerTeam  thunk=0x538AA70**
  blocks: team assignment RPC (returns `LokiIsServer FALSE`).
  in_fk1_register: no · icf_share: unshared · bypass_status: CANDIDATE_DATA_POKE (write `TeamIndex` on PlayerState directly; S131 `KBSTEAM` already does this offline for BotSpawner).

- **ALokiCharacter::GatherServerLocationMovement  thunk=0x5254180**
  blocks: server-side snapshot of a character's location for replication.
  in_fk1_register: no · icf_share: 92-way · bypass_status: GENUINELY_BLOCKING (this is a server-role internal helper; irrelevant on a standalone client where movement is authoritative locally — `GetNetMode() == NM_Standalone`, S137).

- **ALokiTower::OnRep_ServerAimingVector  thunk=0x5254180**
  blocks: RepNotify handler for a tower's aim vector.
  in_fk1_register: no · icf_share: 92-way · bypass_status: GENUINELY_BLOCKING but low-impact (no towers in menu/tutorial).

- **ULokiServerAuthConfig::AuthSetGameFeatureToggle  thunk=0x5463470**
  blocks: server-side runtime toggle mutation.
  in_fk1_register: no · icf_share: unshared · bypass_status: PROVEN_ALT_CALL_PATH (the client already reads toggles via `UClientConfigManager::IsFeatureEnabled` from our `handleClientConfig` payload; S121 shipped it).

- **UDiscordActivityManager::OnLoginStateChanged  thunk=0x5254180**
  blocks: Discord Rich Presence login-state callback.
  in_fk1_register: no · icf_share: 92-way · bypass_status: GENUINELY_BLOCKING but cosmetic (Discord backend is externally-dead; presence never populated regardless).

**NEW-INFO ASSESSMENT**
FK-1 register overlap: **0 of 12** (FK-1's five are SpawnPlayer/AuthSetSpawnTeamLeader/SetDropLeader/OverridePlaneLocations/AuthCheatSetHealth — none in this topic). S152 batch-hunt overlap: **~5** (ServerSetHeroClass, SetPlayerTeam, and the ASC `Auth*` cluster were already flagged there per CLAUDE.md's S152 block). S153 exec sweep overlap: **~2** (`AuthCheatSetHealth` sibling folds are S153-native). **Genuinely new to this topic: ~5** — Nexon login mirrors (4 rows on one thunk), `AuthExecuteLocalGameplayCueOnClient`, `GatherServerLocationMovement`, `OnRep_ServerAimingVector`, `AuthSetGameFeatureToggle`, `OnLoginStateChanged`.

**BLOCKS-WHAT SUMMARY**
CAN deliver: everything the client already does via `ags` HTTP + `/lobby`+`/notifications` WebSockets — login (Steam path), party, presence, friends, missions, mastery, leaderboards, queue-arming, chat routing at the socket level. All were built by simulating the backend, not by fixing these stubs. CANNOT deliver via these RPCs: any true server→client GAS/gameplay-cue push, server-authoritative movement replication, or in-engine RPC-based team/hero assignment. The stripped netcode surface is largely IRRELEVANT because `GetNetMode() == NM_Standalone` (S137) — the client is its own authority and does not need these RPCs to receive backend state; where genuine gameplay effects are needed (hero class, team, ability level), the working pattern is a direct data poke on the reflected UPROPERTY, not resurrecting the RPC.