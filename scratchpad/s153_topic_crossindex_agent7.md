## AGGREGATE

**18 STRIPPED stubs** in the CSV lie on the drop-plane → drop-pod → hero-deploy critical path (excluding `ALokiAirship::ExitAirship`, an unrelated vehicle, and `ALokiBaseItem::SetDropOnDeath`, an item-drop verb).

## TOP-10 HIGHEST-IMPACT

- **ALokiGameMode::SpawnPlayer  thunk=0x534C070**
  blocks: the whole ALokiRoundGameMode player-spawn entry (nullptr fold `0xF7EB50`); the intended sink for hero + GAS bind after pod deploy.
  in_fk1_register: **yes** · icf_share: **unshared** · bypass_status: **PROVEN_ALT_CALL_PATH** (KWIREGAS wires GAS onto the hero directly; S143/S144)

- **ALokiPlayerState::AuthSetSpawnTeamLeader  thunk=0x5254180**
  blocks: marking a PlayerState as team drop leader, prerequisite to `GetTeamDropLeader` in the pod path.
  in_fk1_register: **yes** · icf_share: **92-way** · bypass_status: **CANDIDATE_DATA_POKE** (poke `[TeamState+0x688]`, S131 §12 lever)

- **ALokiTeamState_TeamOnly::SetDropLeader  thunk=0x2C2CE30**
  blocks: writing the team-state slot that `GetTeamDropLeader` reads (returns null today).
  in_fk1_register: **yes** · icf_share: **23-way** · bypass_status: **CANDIDATE_DATA_POKE**

- **ALokiDropPlane::OverridePlaneLocations  thunk=0x53372A0**
  blocks: authoritative override of plane path endpoints.
  in_fk1_register: **yes** · icf_share: **unshared** · bypass_status: **PROVEN_ALT_CALL_PATH** (general `SpawnPlane` derives path from death-circle radius, FK-22)

- **ALokiDropPlane::AddPlayerToPlane  thunk=0x2C2CE30**
  blocks: attaching a rider to the drop plane on the AUTHORITY side.
  in_fk1_register: no · icf_share: **23-way** · bypass_status: **PROVEN_ALT_CALL_PATH** (`ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` real, FK-22)

- **ULokiRideableComponent::AuthAddPlayer  thunk=0x2C2CE30**
  blocks: putting a rider onto the pod's rideable component (all 4 `Auth*` slots stripped, S130 §14.1).
  in_fk1_register: no · icf_share: **23-way** · bypass_status: **PROVEN_ALT_CALL_PATH** (S132 direct `PlayersAttached` TArray poke → detach flew 6×)

- **ULokiRideableComponent::AuthRemovePlayer  thunk=0x2C2CE30**
  blocks: authoritative removal path; mirror of AddPlayer.
  in_fk1_register: no · icf_share: **23-way** · bypass_status: **PROVEN_ALT_CALL_PATH** (same recipe)

- **ULokiRideableComponent::AuthPlayerEnterWorldNew  thunk=0x5456460**
  blocks: one of three "enter world attached to rideable" entry points (siblings hit the stripped round-game-mode getter).
  in_fk1_register: no · icf_share: **other** · bypass_status: **PROVEN_ALT_CALL_PATH** (S132 mount recipe substitutes)

- **ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod  thunk=0x530BFD0**
  blocks: the pod→glide handoff on the CMC.
  in_fk1_register: no · icf_share: **other** · bypass_status: **PROVEN_ALT_CALL_PATH** (S150-drop `dismount-landstart` teleports hero to PlayerStart, skipping the glide arc)

- **ULokiCharacterMovementComponent::AuthBeginGlideDive + ALokiCharacter::GatherGlide{Boost,Dive,Movement}  thunk=0x5254180**
  blocks: entire glide-physics accumulation path.
  in_fk1_register: no · icf_share: **92-way** · bypass_status: **PROVEN_ALT_CALL_PATH** (S150-drop substitutes ground teleport + `play` for the descend-and-glide arc)

## NEW-INFO ASSESSMENT

- **Already in FK-1 register (5 entries):** SpawnPlayer, AuthSetSpawnTeamLeader, SetDropLeader, OverridePlaneLocations = **4 of 18**.
- **Already surfaced in S152 batch-hunt** (CLAUDE.md names them explicitly): AuthAddPlayer, AuthRemovePlayer, AuthSetCanJump (Rideable), AuthBeginGlideDiveFromDropPod = **4 of 18**.
- **Documented anecdotally in CLAUDE.md but not in either formal register:** AuthPlayerEnterWorldNew, AddPlayerToPlane = **2 of 18**.
- **Genuinely-new to any register:** RemovePlayerFromPlane, DropPlane::AuthStart, DropPlane::SetCanJump, AuthBeginGlideDive, BeginParachuteGlide, GatherGlideBoost/Dive/Movement (×3), AuthSetCurrentRideable, OnPlayerExitedDropPod = **~8 of 18**.

## BLOCKS-WHAT SUMMARY

Every server-authoritative WRITER of drop-chain state — spawn-into-round-mode, team-leader designation, plane-path override, rider-add/remove on plane AND rideable, and the glide-dive CMC transition — is folded. **What the topic CAN deliver via bypass:** rider attach/detach (S132 data-poke), plane path (procedural via general SpawnPlane), pod flight (S131 real body), dismount-to-terrain (S150-drop flight-4b landed a walking hero). **What it CANNOT deliver from these stubs alone:** an authentic `SpawnPlayer`-sourced hero with server-issued PlayerState/TeamState wiring, an authentic team-leader-designated pod-crew grouping, or an authentic pod→glide→landing arc — all substituted with data-pokes or teleports. **Zero of the 18 are GENUINELY_BLOCKING** given the S132/S150-drop bypasses now on record.