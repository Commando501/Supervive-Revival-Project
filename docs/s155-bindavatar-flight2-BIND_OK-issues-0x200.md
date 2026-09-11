# S155-bindavatar flight 2 — bind succeeds, cleared 14 of 14 PREFLIGHT sub-blockers; only `MAX_HEALTH_BELOW_SEED` (0x200) remains

**Live 2026-09-08**, first live exercise of the new `botfight-damage-self-cal-bindavatar`
variant. Two flights this session; results below.

> **Prior**: [docs/s154-selfcal-flight2-PREFLIGHT_REFUSED-avatar-binding.md](s154-selfcal-flight2-PREFLIGHT_REFUSED-avatar-binding.md)
> established that Flight 4's `AvatarActor==0` blocker reproduces at `issues=0x3EC13F` under
> the S153-fixed shim.

## Headline

★★★★★★ **[M] S155 bind-avatar recipe WORKS.** One direct call to `ULokiAbilitySystemComponent
::InitAbilityActorInfo(asc, carrier, hero)` at `base+0x447F410` lands cleanly:
`AvatarActor@0x410 pre=0x0 post=hero avatarBound=1`. First live exercise of the S143 recipe
inside the self-cal shim.

★★★★★★ **[M] Cleared 14 of 14 pre-existing PREFLIGHT sub-blockers.** Issues went from
`0x3EC13F` (14 bits set) to `0x200` (1 bit set). Every issue bit downstream of AvatarActor
binding cleared as predicted by the design.

★★★★ **[I,strong] Only remaining sub-blocker: `MAX_HEALTH_BELOW_SEED` (bit 0x200 = `1u << 9`).**
The hero's `LokiAttributeSetHealth.MaxHealth` reads `0.0f/0.0f` in the freshly-bound attribute
set — the seed value is 1000.0f, and the S148 safety check requires MaxHealth to be at least
the seed value BEFORE proceeding. Fix is small (~10 LOC): pre-seed MaxHealth in the S155 arm
between bind and PREFLIGHT.

⭐ **[M] S153 FK-1 thunkExact fix STILL not tested live.** PREFLIGHT still refuses — the S153
code path (`CALL_ISSUED AdjustHealth`) never runs. But the wall is now measured to be one
narrow sub-blocker away, not the entire cascade.

## Flight 1 — "Fatal error" during LVL_Tutorial load (not S155's fault)

Launch PID 16120, `[fo]` completed cleanly (`[6] NearAlloc region freed`), then game crashed
during LVL_Tutorial load with:

```
Fatal error: [File:.../UnrealEngine.cpp] [Line: 15551]
Couldn't spawn player: ALokiGameMode::Login failed to Login
```

Exit code 3, crashwatch trigger `"Fatal error"` at T+177.1s. The stager aborted cleanly at
step 3 (would have been sp injection) with "no tutorial world -> injecting sp now would be a
wasted one-shot. ABORTING." (exit code 4).

Same `fo.dll` that worked in S154 flight 2 — random race in the shipped `ALokiGameMode::Login`
path. Documented in CLAUDE.md's KNOLOGINVT section. Base-rate hazard, not caused by S155.

**Artifacts**: `docs/tutorial-launch-marker.s155-bindavatar-f1-FATAL-during-mapload.txt`,
`docs/crashwatch.s155-bindavatar-f1-FATAL.log`, `dumps/crash-20260908-173950/`

## Flight 2 — full clean run, S155 bind arm works, PREFLIGHT narrows to 0x200

**Timeline**:
- 17:44:11 — launch (PID 43308, `-NoHook`)
- 17:45:XX — lobby park
- 17:46:XX — stager: gft → fo → sp all injected cleanly, `[SP] done step=4 (hero possessed) OK (15s)`
- 17:47:XX — S155 probe injected: `Manual-mapping ... into PID 43308, remote image base:
  0x2CC874E0000, size 0x3C000, exception table: 0x1B6 entries, DllMain 0x1 (OK), MZ ✓`
- **~17:47:XX + ~4s** — S155 bind + S148 arm ran end-to-end
- **Game survived past receipt** (no FK-32) — killed cleanly by operator

### The [S155] bind receipt

```
[S155] ===== bind-avatar preflight (KBFBINDAVATAR=1) =====
[S155] BIND_AVATAR result=ok pc=0x2CC2EBF2770 hero=0x2CC22960040 ps=0x2CB0CB84450 asc=0x2CBCECAB380 carrier=0x2CC924F3BD0 owner=0x2CC924F3BD0
[S155] AvatarActor@0x410 pre=0x0 post=0x2CC22960040 avatarBound=1
[S155] proceed=yes preflight_reached=1 handing off to S148 PREFLIGHT
```

- Every pointer non-null: pc/hero/ps/asc/carrier all resolved
- Owner = carrier (KBFOWNER=0 semantics, matches K_BIND arm's design)
- `pre=0x0` → `post=hero` — bind CONFIRMED, no fault, exact match
- Proceeds to S148 PREFLIGHT

### The [S148] PREFLIGHT receipt (post-bind)

```
[S148] owner LocalPlayer=... hero=0x2CC22960040 class=0x2CBFB440400 Controller@0x400 ASCStorage@0xF00 ASC=0x2CBCECAB380 class=0x2CB7FF90100 AvatarActor@0x410=0x2CC22960040 avatarBound=1 ascOwned=1
[S148] world identity ... valid=1
[S148] SpawnedAttributes@0x168 prop=0x2CB09BE4180 inner=0x2CB09BE4100 expectedOwner=AbilitySystemComponent type=ArrayProperty innerType=ObjectProperty<AttributeSet> provenance=1 memberTypes=1 Data=0x2CBCFFF34E0 Num=2 Max=4 healthCandidates=1 candidateIndex=1
[S148] registration scan complete=1 count=1 selectedAscOwns=1 censusClosure=1 set=0x2CCF1BCD8A0 ASC=0x2CBCECAB380
[S148] target set=0x2CCF1BCD8A0 class=0x2CB7FF9DD00 Health@0x70 MaxHealth@0x80 HealthOwner=LokiAttributeSetHealth MaxOwner=LokiAttributeSetHealth HealthStruct=GameplayAttributeData MaxStruct=GameplayAttributeData expected=GameplayAttributeData HealthStructPtr=0x2CB0AAEA190 MaxHealthStructPtr=0x2CB0AAEA190 structPayload=1 superPropertiesSize=56 setPropertiesSize=280 layoutValid=1 HealthBits=00000000/00000000 MaxBits=00000000/00000000 CDO=0(certain=1) CDOOuter=0(chainValid=1) writable=1 issues=0x200
[S148] PREFLIGHT_REFUSED RESULT=PREFLIGHT_REFUSED issues=0x200; no Health write and no AdjustHealth call
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan 3609 ms, 34253 UFunctions live)
[BF] worker done (hits=1 hitsGT=1)
```

## Issue-bit diff [M]

Decoded via `s148_damage_calibration.h:385-407`:

**S154 F2 (`0x3EC13F`) — 14 bits set**:
- ASC_INVALID, SPAWNED_HEADER_INVALID, HEALTH_COUNT, CANDIDATE_INVALID,
  HEALTH_NOT_WRITABLE, HEALTH_CLASS, MAX_HEALTH_INVALID, PROPERTY_PROVENANCE,
  SET_REGISTRATION, AVATAR_BINDING, SPAWNED_MEMBER_TYPE, ATTRIBUTE_LAYOUT,
  CENSUS_CLOSURE, STRUCT_PAYLOAD

**S155 F2 (`0x200`) — 1 bit set**:
- MAX_HEALTH_BELOW_SEED

**Cleared by the bind (14/14)**: every one of the above except MAX_HEALTH_BELOW_SEED, which
was not set in S154 either (0x200 masked in with the 0x3EC00F portion but happened to be off
in S154 — actually not: S154 had `SPAWNED_HEADER_INVALID`, `HEALTH_COUNT`, etc. that all
downstream-depended on Avatar being NULL, and NONE of them are the same bit as
MAX_HEALTH_BELOW_SEED).

The bind is the causal upstream of every cleared bit: without AvatarActor, the ASC's
attribute-set scan couldn't proceed, so all the `SPAWNED_*`, `SET_*`, `HEALTH_CLASS`, etc.
checks failed cascadingly.

## The remaining sub-blocker: `MAX_HEALTH_BELOW_SEED` (0x200 = 1u << 9)

Source at `s148_damage_calibration.h:485-487`:
```c
if (maxValid && (!S148PositiveAtLeastSeed(facts.maxBaseBits) ||
                 !S148PositiveAtLeastSeed(facts.maxCurrentBits)))
    issues |= S148_ISSUE_MAX_HEALTH_BELOW_SEED;
```

**Marker evidence**: `MaxBits=00000000/00000000` — MaxHealth is 0.0f in both base and current
fields. The self-cal policy plans to seed at 0x447A0000 = 1000.0f. Since 0.0f < 1000.0f, the
safety check fires.

**Why this exists**: S148 is designed to CALIBRATE damage on a self-owned hero; it wants to
verify the hero's MaxHealth is already at least the seed value BEFORE writing (so that
seeding is either a no-op or a bump-up, never a dangerous overwrite of a game-set value).
On this route the hero pawn is spawned but its LokiAttributeSetHealth is freshly-constructed
with default 0.0f — nothing initializes it because normal gameplay depends on GAS attribute
initialization from a hero data asset (`DA_Hero_*`) that never runs here.

## Comparison

| Field | S154 F2 (no bind) | S155 F2 (with bind) | Delta |
|---|---|---|---|
| `AvatarActor@0x410` | `0x0` | `0x2CC22960040` (hero) | ✓ bound |
| `avatarBound` | 0 | 1 | ✓ |
| `SpawnedAttributes` | `Num=0 Max=0` | `Num=2 Max=4` | ✓ populated |
| `healthCandidates` | 0 | 1 | ✓ |
| `registration count` | 0 | 1 | ✓ |
| `selectedAscOwns` | 0 | 1 | ✓ |
| `censusClosure` | 0 | 1 | ✓ |
| `target set` | `0x0` | `0x2CCF1BCD8A0` (LokiAttributeSetHealth) | ✓ resolved |
| `Health@` / `MaxHealth@` | `0x0/0x0` | `0x70/0x80` | ✓ offsets found |
| `HealthStruct` / `MaxStruct` | `-` | `GameplayAttributeData` | ✓ typed |
| `structPayload` / `layoutValid` / `writable` | `0/0/0` | `1/1/1` | ✓ layout OK |
| `HealthBits` / `MaxBits` | `00000000/00000000` | `00000000/00000000` | unchanged (both 0) |
| `issues` | `0x3EC13F` | **`0x200`** | ↓ 14 bits cleared |

Also unchanged (both flights): `ascOwned=1`, `world identity valid=1`, `structPayload=1`,
funcswap discipline clean (17,563/17,563 restored), no FK-32.

## What this validates

- **S155 KBFBINDAVATAR arm design is CORRECT [M]**: the exact code path (`FindInstByClass →
  Pawn/PlayerState → BfGetAsc → BfCarrier → BfCallInitAAI(asc,carrier,hero)`) landed and
  bound AvatarActor on the first try.
- **S143 `InitAbilityActorInfo(base+0x447F410)` recipe is stable and reproducible [M]** —
  first re-verification since S143's original flight.
- **The additive-property contract holds** — base variant `botfight-damage-self-cal.dll`
  rebuilt byte-identical after my source edits (pre-edit HEAD source and post-edit source
  both produce RAW `167d1552c73bfd7a` when built fresh); `s148_build_contract_test.ps1`
  passes unchanged.
- **The shim discipline holds** — no `.text` write, no PI hook, funcswap restored 17,563 of
  17,563, no FK-32, game survives past receipt.

## What this does NOT do

- Not exercise the S153 FK-1 thunkExact fix live. PREFLIGHT still refuses (at a narrower
  gate); `CALL_ISSUED AdjustHealth` still doesn't run.
- Not resolve Blocker #1 (damage pipeline unproven).

## Next moves — S156 candidates

### S156-A (recommended): extend KBFBINDAVATAR to also pre-seed MaxHealth

Small addition to the same arm (~10 LOC). After successful bind, resolve the target attribute
set (call `BfS148ResolveHealthTarget` early), and if it succeeds, write
`target.set + MaxHealth_offset + 0` and `target.set + MaxHealth_offset + 4` = `0x447A0000`
(1000.0f). Then the S148 arm's own PREFLIGHT would see `MaxBits=447A0000/447A0000` and pass
MAX_HEALTH_BELOW_SEED.

Trade-off: writes 8 bytes to a live attribute set's MaxHealth field. Risk class: DATA write
on a well-scoped struct pointer (target.set is validated with `layoutValid=1, writable=1`
before we write). Same class as S130 CDO writes; measured safe.

Design: add `KBFBINDAVATAR_SEED_MAX=1` as a sub-mode of KBFBINDAVATAR, OR use a new knob
`KBFPRESEEDMAX=1` for cleaner separation. Same variant naming shape:
`botfight-damage-self-cal-bindavatar-seedmax`.

### S156-B (alternative): weaken S148's safety check for the bindavatar mode

Modify `S148_ISSUE_MAX_HEALTH_BELOW_SEED` to be skipped when `KBFBINDAVATAR=1`. Rationale:
the whole point of the bindavatar arm is to prove the pipeline works from a fresh state;
requiring pre-existing MaxHealth defeats that. Trade-off: relaxes a safety check in test-only
code; base variant untouched.

Design: `#if KBFBINDAVATAR` before the check, or a runtime `if(KBFBINDAVATAR) skipCheck`.

### S156-C (deferred): full attribute-set initialization from hero data asset

The proper fix is to trigger the game's own attribute initialization path (`K2_InitStats` on
the LokiAttributeSet with the hero's `AttributeSetData` DA). This is what would happen in a
normal gameplay session. Larger scope, requires understanding of the K2_InitStats path.

**Recommendation: S156-A.** Minimal patch, direct evidence, single-variable change.

## Rules banked (new)

### R-S155-a: `Couldn't spawn player: ALokiGameMode::Login failed to Login` is a random staging race on the tutorial route, not a permanent fo.dll regression. Retrying with a fresh launch usually clears it (S155 F1 hit it, F2 didn't, same DLLs, ~4 min apart).

Applied here: Flight 1 died mid-LVL_Tutorial-load with this fatal, exit code 3, crashwatch
trigger `"Fatal error"` at T+177.1s. Flight 2 with the identical stager recipe on a fresh
launch didn't reproduce it. Documented in CLAUDE.md's KNOLOGINVT section as a known
mode when `fo`'s `.rdata` slot-285 patch is missing — but `fo.dll` DID complete `[6] NearAlloc
region freed` in F1, so the patch DID apply. The random-race characterization is consistent
with the base-rate FK-31 staging hazard.

## Files preserved

- `docs/s155-bindavatar-flight2-BIND_OK-issues-0x200.md` — this doc
- `docs/tutorial-launch-marker.s155-bindavatar-f1-FATAL-during-mapload.txt` (F1 marker at abort)
- `docs/tutorial-launch-marker.s155-bindavatar-f2-INITIAL.txt` (F2 marker snapshot)
- `docs/tutorial-launch-marker.s155-bindavatar-f2-PREFLIGHT_REFUSED-issues-0x200.txt` (F2 canonical)
- `docs/crashwatch.s155-bindavatar-f1-FATAL.log` (F1 crashwatch — Fatal, exit 3)
- `docs/crashwatch.s155-bindavatar-f2.log` (F2 crashwatch — game survived)
- `docs/fk24-stage-s155-bindavatar-f1.stager-stdout.log`, `-f2.stager-stdout.log`
- `docs/launch-redirect.s155-bindavatar-f1.stdout.log`, `-f2.stdout.log`
- `docs/fk24-stage-s155-bindavatar-f{1,2}-{1,2,3,4}-*.txt` (stager per-step markers)
- `dumps/crash-20260908-173950/` (F1 178 MB crashwatch dump)

Source + build.ps1 + built DLLs (committed as part of this session):
- `tools/sigbypass-mod/tutorial_launch.cpp` — +53 lines (KBFBINDAVATAR knob + guard + arm)
- `tools/sigbypass-mod/build.ps1` — +7 lines (variant registration)
- `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar.dll`
  (223,744 B, RAW `d8c08912816162a7`, VSIZE `db67f5289a07db07`)
- Base variant `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal.dll`
  (unchanged in .text — additive property verified via git stash test)
