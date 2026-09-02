**AGGREGATE:** **9 STRIPPED stubs** on the CMC/GAS-attribute critical path (5 direct CMC methods + 4 character health/mana attribute writers). One adjacent query (`IsAtOrAboveManaSoftCap`) makes 10 if counting readers.

**TOP-10 HIGHEST-IMPACT HITS:**

- **ULokiCharacterMovementComponent::AuthBeginGlideDiveFromDropPod  thunk=0x530BFD0**
  - blocks: server-side entry to the pod->hero dismount glide/dive transition on CMC (the S131/S132 dismount handoff)
  - in_fk1_register: no · icf_share: unshared (single-user of 0x530BFD0) · bypass_status: PROVEN_DATA_POKE (S132 detach + `GravityScale=1.0` reproduces landing)

- **ULokiCharacterMovementComponent::AuthBeginGlideDive  thunk=0x5254180**
  - blocks: authoritative glide-dive entry from any source (not just pod)
  - in_fk1_register: no · icf_share: 92-way (universal execFoo->void fold) · bypass_status: CANDIDATE_DATA_POKE (set `MovementMode` + kick `Velocity` per S141 T3)

- **ULokiCharacterMovementComponent::BeginParachuteDive  thunk=0x5254180**
  - blocks: parachute-phase dive transition on CMC
  - in_fk1_register: no · icf_share: 92-way · bypass_status: CANDIDATE_DATA_POKE

- **ULokiCharacterMovementComponent::BeginParachuteGlide  thunk=0x5254180**
  - blocks: parachute-phase glide state on CMC (drop-phase cinematic)
  - in_fk1_register: no · icf_share: 92-way · bypass_status: CANDIDATE_DATA_POKE

- **ULokiCharacterMovementComponent::EndFollowingActor  thunk=0x5296F30**
  - blocks: releasing a CMC-driven "follow actor" mode (used to detach from moving mounts)
  - in_fk1_register: no · icf_share: other (0x5296F30, non-92-way void) · bypass_status: CANDIDATE_DATA_POKE (clear follow-target ptr + restore mode)

- **ALokiCharacter::AuthCheatSetHealth  thunk=0x52FD620**
  - blocks: direct authoritative Health attribute write (the S148 self-damage calibration target)
  - in_fk1_register: **YES** (5th entry, S152) · icf_share: 9-way (DebugTimeline siblings) · bypass_status: CANDIDATE_ALT_CALL (S153 thunkExact fix pending live test)

- **ALokiCharacter::AuthCheatSetMana  thunk=0x52FD620**
  - blocks: direct authoritative Mana attribute write (WALL P activation-cost sibling)
  - in_fk1_register: no (but shares thunk with FK-1 entry #5) · icf_share: 9-way · bypass_status: CANDIDATE_ALT_CALL (same UHT-wrapper route)

- **ALokiCharacter::InfiniteHealth  thunk=0x5254180**
  - blocks: cheat toggle for health-drain immunity
  - in_fk1_register: no · icf_share: 92-way · bypass_status: CANDIDATE_DATA_POKE (matching bool flag on ASC)

- **ALokiCharacter::InfiniteMana  thunk=0x5254180**
  - blocks: cheat toggle for mana-cost immunity (relevant to WALL P ability spam)
  - in_fk1_register: no · icf_share: 92-way · bypass_status: CANDIDATE_DATA_POKE

- **ALokiHeroCharacter::IsAtOrAboveManaSoftCap  thunk=0x52FD980**
  - blocks: nothing writes/moves — it is a READER folded to `LokiIsServer FALSE` (always returns false on client). Downstream effect: any BP branch gated on soft-cap can never take the true arm.
  - in_fk1_register: no · icf_share: other · bypass_status: UNKNOWN (query, not a mover)

**NEW-INFO ASSESSMENT:** Of the 9 movement/GAS-attribute strips: **1 in FK-1 register** (`AuthCheatSetHealth`). **~7 of the remaining 8 are already known via S152 batch hunt** (CLAUDE.md explicitly cites `AuthBeginGlideDiveFromDropPod` matching the S131 dismount finding). `EndFollowingActor` (thunk 0x5296F30) is **the one genuinely-new discovery** — a non-92-way void fold on the CMC that has never been named in this project's docs. `AuthBeginGlideDive` (bare, no-pod variant) is also **newly enumerated** even though its sibling was known — it opens a non-drop entry to the same state.

**BLOCKS-WHAT SUMMARY:** These strips gut the **authoritative movement-state transitions** (glide/dive/parachute/follow) and the **cheat-verb GAS attribute writers** (Health, Mana, Infinite*), but they DO NOT reach the S141-T3 open question — nothing here zeros `Velocity` or clamps `MaxInputSpeed`, and the engine `PhysFalling`/`CalcVelocity` chain is stock UE (not on this list). CAN deliver: state-transition entry via CMC `MovementMode`+`Velocity` data pokes and per-frame `Velocity` kicks (S141 T3-B `PendingLaunchVelocity` path). CANNOT deliver: authoritative cheat health/mana adjustment through the reflected verb path until the S153 thunkExact fix is live-verified, and glide/parachute states cleanly (all four are void folds — no `.text` route exists, only data-poke substitution).