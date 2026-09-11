## 1. AGGREGATE

**13 STRIPPED stubs on the mount/pod-rider-handoff critical path** (excluding `ALokiBaseItem::SetDropOnDeath` — same fold family, off-topic).

## 2. TOP-10 HIGHEST-IMPACT

- **ULokiRideableComponent::AuthPlayerEnterWorldNew  thunk=0x5456460**
  - blocks: server-side "player has entered a rideable" state install (the *new* variant of the S131 fifth-wall entry point)
  - in_fk1_register: no · icf_share: **unshared** · bypass_status: **PROVEN_DATA_POKE** (S131/S132: PlayersAttached append + `AuthPlayerDetachPlayerFromRidable` REAL)

- **ULokiRideableComponent::AuthAddPlayer  thunk=0x2C2CE30**
  - blocks: canonical add-rider path to any rideable (pod OR plane)
  - in_fk1_register: no · icf_share: **23-way** (with SetDropLeader) · bypass_status: **PROVEN_DATA_POKE** (S132 recipe)

- **ULokiRideableComponent::AuthRemovePlayer  thunk=0x2C2CE30**
  - blocks: canonical remove-rider path (bookkeeping half of dismount)
  - in_fk1_register: no · icf_share: **23-way** · bypass_status: **PROVEN_ALT_CALL_PATH** (`AuthPlayerDetachPlayerFromRidable 0x55CCCB0` REAL, six flown detaches)

- **ULokiRideableComponent::AuthSetCanJump  thunk=0x5296F30**
  - blocks: server toggle of rider-jump permission
  - in_fk1_register: no · icf_share: **11-way** · bypass_status: **CANDIDATE_DATA_POKE** (write the mirrored client bool; untested)

- **ALokiTeamState_TeamOnly::SetDropLeader  thunk=0x2C2CE30**
  - blocks: leader-pod selection precondition for `SpawnDropPodForTeam(bIsTeamLeaderPod=true)` — S131's named blocker for `GetTeamDropLeader() → null`
  - in_fk1_register: **YES** · icf_share: **23-way** · bypass_status: **CANDIDATE_DATA_POKE** (`IsSpawnTeamLeader` reads `[TeamState+0x688]` — poke it)

- **ALokiDropPlane::AddPlayerToPlane  thunk=0x2C2CE30**
  - blocks: server-side "add rider to drop-plane" (the plane-analog of AuthAddPlayer)
  - in_fk1_register: no · icf_share: **23-way** · bypass_status: **PROVEN_ALT_CALL_PATH** (component-side `AddPlayerToDropPlane 0x55CBB60` REAL, per CLAUDE.md drop block)

- **ALokiDropPlane::RemovePlayerFromPlane  thunk=0x2C2CE30**
  - blocks: server-side rider removal from drop-plane
  - in_fk1_register: no · icf_share: **23-way** · bypass_status: **CANDIDATE_ALT_CALL** (mirror the AddPlayer bypass; untested)

- **ALokiDropPlane::OverridePlaneLocations  thunk=0x53372A0**
  - blocks: dynamic plane path override (start/end waypoints)
  - in_fk1_register: **YES** · icf_share: **unshared** · bypass_status: **GENUINELY_BLOCKING** — `OnDeathCircleSet` derives path procedurally from radius; overriding it has no reachable substitute on the tutorial route

- **ULokiPlayerDropPlaneComponent::AuthSetCurrentRideable  thunk=0x2C2CE30**
  - blocks: PC-side "which rideable this player is on" write
  - in_fk1_register: no · icf_share: **23-way** · bypass_status: **CANDIDATE_DATA_POKE** (reflected mirror on the drop-plane component)

- **ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod  thunk=0x530BFD0**
  - blocks: server transition from pod-attached → free-fall glide/dive (the deploy end of the pod ride)
  - in_fk1_register: no · icf_share: **unshared** · bypass_status: **PROVEN_ALT_CALL_PATH** (S132 dismount + S150-drop `dismount-landstart` reproduces the hero-on-ground outcome without it)

Also-stripped on this critical path but below top-10: `ALokiDropPlane::AuthStart` (0x52FD620, 9-way — CANDIDATE_DATA_POKE via plane state field), `ALokiDropPlane::SetCanJump` (0x5296F30, 11-way), `ULokiPlayerDropPlaneComponent::OnPlayerExitedDropPod` (0x542E4A0, unshared).

## 3. NEW-INFO ASSESSMENT

- Already in **FK-1 register (5 total)**: **2 hits** (`SetDropLeader`, `OverridePlaneLocations`).
- Already in **S152 batch hunt (95)**: **~5** (the 3 Rideable `Auth*` + `AuthBeginGlideDiveFromDropPod` + `AuthPlayerEnterWorldNew` — CLAUDE.md's rideable/drop-phase block cites this cluster verbatim).
- **Genuinely new discoveries**: **~6** — the 4 `ALokiDropPlane` non-`OverridePlaneLocations` verbs (`AddPlayerToPlane`, `RemovePlayerFromPlane`, `SetCanJump`, `AuthStart`) plus both `ULokiPlayerDropPlaneComponent` entries (`AuthSetCurrentRideable`, `OnPlayerExitedDropPod`). None was previously enumerated as stripped.

## 4. BLOCKS-WHAT SUMMARY

**Can deliver:** full mount/ride/dismount cycle end-to-end — S150-drop (2026-09-01) flew the hero from a driven drop onto real terrain at `(-3206.4, 5070.5, 138)` and walked at ground level, using DATA pokes (`PlayersAttached` append, `bCanEverReplicate=0`) plus REAL calls (`AuthPlayerDetachPlayerFromRidable`, `AddPlayerToDropPlane`). **Cannot deliver via the game's own auth surface:** dynamic plane routing (`OverridePlaneLocations` is genuinely blocked — no substitute), leader-pod formation (`SetDropLeader` needs the `[TeamState+0x688]` poke to synthesize a leader), and any shipping-safe path — every recipe is a diagnostic that mutates class defaults or per-instance TArrays and none is a candidate for the default shim set.