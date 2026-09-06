## AGGREGATE

**21 STRIPPED stubs total on the match-lifecycle critical path** (7 `ALokiGameMode` + 3 `ALokiGameState` + 5 `ALokiTeamState`/`_TeamOnly` + 3 respawn (`ALokiPlayerState::GetLastRespawnTime` + 2 `ALokiRespawnBeacon`) + 3 adjacent Character/Matchmaking `Auth*`/tick).

## TOP-10 HIGHEST-IMPACT

- **ALokiGameMode::SpawnPlayer  thunk=0x534C070**
  - blocks: server-side pawn spawn + GAS wiring for real hero deploy (the FK-1 keystone).
  - in_fk1_register: yes · icf_share: unshared · bypass_status: **PROVEN_ALT_CALL_PATH** (S135/S136 `SpawnAIFromClass` → engine `SpawnDefaultController` yields an AI-controlled hero pawn without touching this stub).

- **ALokiGameMode::EliminateTeam  thunk=0x5349CB0**
  - blocks: server-authored team elimination → match-end trigger for BR/Bots modes.
  - in_fk1_register: no · icf_share: unshared · bypass_status: **GENUINELY_BLOCKING** (no data mirror named; win condition lives here).

- **ALokiGameState::SetPlayerTeam  thunk=0x538AA70**
  - blocks: authoritative team assignment on GameState (LokiIsServer FALSE fold).
  - in_fk1_register: no · icf_share: unshared · bypass_status: **CANDIDATE_DATA_POKE** (write PlayerState team field directly; sibling of S137's `ServerSetHeroClass` gap on SpawnBot's DE53 branch).

- **ALokiGameState::AuthHandlePlayerPawnUpdated  thunk=0x2C2CE30**
  - blocks: GameState notification of pawn possession/repossession events.
  - in_fk1_register: no · icf_share: 23-way (shared with `SetDropLeader` FK-1) · bypass_status: **CANDIDATE_DATA_POKE** (broadcast delegate on GS, unmapped).

- **ALokiGameState::SetNumTeams  thunk=0x52FD8F0**
  - blocks: initializing `GameState.TeamStates` array (documented in CLAUDE.md FK-1 §GameState).
  - in_fk1_register: no · icf_share: unshared · bypass_status: **GENUINELY_BLOCKING** (CLAUDE.md: "TeamStates can NEVER be non-empty on a client [M]"; S131 `[TeamState+0x688]` poke is a distinct workaround, not a bypass of this).

- **ALokiTeamState_TeamOnly::SetDropLeader  thunk=0x2C2CE30**
  - blocks: leader-pod / drop-order assignment (S131 fifth-wall root cause).
  - in_fk1_register: yes · icf_share: 23-way · bypass_status: **CANDIDATE_DATA_POKE** (poke `[TeamState+0x688]` per S131 recipe; unflown).

- **ALokiTeamState::SetIsEliminated  thunk=0x5296F30**
  - blocks: per-team elimination bit → drives end-of-game UI + scoring.
  - in_fk1_register: no · icf_share: shared with `AuthSetRuinedState` · bypass_status: **CANDIDATE_DATA_POKE** (single reflected UPROPERTY).

- **ALokiGameMode::TickAFKChecking  thunk=0x5254180**
  - blocks: server AFK enforcement (kick loop).
  - in_fk1_register: no · icf_share: 92-way (universal execFoo thunk) · bypass_status: **PROVEN_ALT_CALL_PATH** (client doesn't run AFK — non-blocking for playability).

- **ALokiGameMode::GetAutomaticRespawnTimerAdditionalTime  thunk=0x5349FB0**
  - blocks: adds delta to base respawn timer (0.0f fold).
  - in_fk1_register: no · icf_share: shared with `ALokiPlayerState::GetLastRespawnTime` · bypass_status: **PROVEN_ALT_CALL_PATH** (returning 0.0 is a safe default — the base timer path is elsewhere).

- **ALokiGameMode::GameModeCheat  thunk=0x5349DC0**
  - blocks: dev cheat dispatcher (paired with `DevGameModeCheatsEnabled 0x51629C0` and `CheatCantEndGame 0x52FD980`).
  - in_fk1_register: no · icf_share: unshared · bypass_status: **PROVEN_ALT_CALL_PATH** (FK-13 Route B `UCheatManager` shim reaches 42 REAL exec verbs directly; this dev entry is redundant).

## NEW-INFO ASSESSMENT

- **Already in FK-1 register:** 2 of 21 (`SpawnPlayer`, `SetDropLeader`).
- **In S152 batch hunt (Auth*/Server*/*Cheat*):** ~10 (`AuthHandlePlayerPawnUpdated`, `AuthStashTeamGems`, `AuthSetStashedTeamGems`, `AuthSetRuinedState`, `AuthClearLockedOutTeams`, `AuthAddPreSpawnedEffect`, `AuthRemovePreSpawnedEffect`, `CheatCantEndGame`, `DevGameModeCheatsEnabled`, `GameModeCheat`).
- **In S153 exec-verb sweep (32):** 0 (exec-verb corpus is disjoint from these Blueprint-callable stubs).
- **Genuinely-new discoveries:** **~9** — the non-`Auth*` GameMode/GameState/TeamState/Respawn stubs (`EliminateTeam`, `SetPlayerTeam`, `SetNumTeams`, `SetIsEliminated`, `HeroRecallTargetStateChanged`, `TickAFKChecking`, `GetAutomaticRespawnTimerAdditionalTime`, `GetLastRespawnTime`, `AutomatchmakingTick`). `EliminateTeam` and `SetIsEliminated` are the sharpest additions — direct win/lose plumbing not previously tracked.

## BLOCKS-WHAT SUMMARY

This stub set makes **client-side match progression** (spawn/team-assign/eliminate/end) structurally unauthored: every write that would tick a match toward a win condition — `EliminateTeam`, `SetPlayerTeam`, `SetIsEliminated`, `SetNumTeams`, `SetDropLeader`, `AuthHandlePlayerPawnUpdated` — is a void/false fold. What **is** deliverable is a **pawn-in-world sitting**: S135–S137's `SpawnAIFromClass` + `InitPlayerState` chain routes around `SpawnPlayer`, and FK-22/S124 proves `GoToPhase`/`AuthSetCurrentPhase` self-drive phases to `EGP_Combat` via REAL functions. What is **not** deliverable is any authoritative match resolution: no team can be marked eliminated, no game-over transition can fire from the client, and team-scoped state (`TeamStates`) cannot be materialized without the S131 `[TeamState+0x688]` poke, which is itself still unflown.