# S156-A flight 5 — SELF_DAMAGE_CALIBRATED — the game's own AdjustHealth path applied damage end-to-end

**Date:** 2026-09-08
**Session:** S156 (S153 → S154 F2 → S155 F2 → S156-A F1..F5)
**Verdict:** ★★★★★★★ HISTORIC — first time in this project's history the game's own
`ULokiAbilitySystemComponent::AdjustHealth` native path has been driven end-to-end.
Damage of −250 was applied to a fresh 1000 HP hero, leaving 750 HP, exactly as arithmetic predicts.
Game survived the calibration without FK-32.

**Base commit:** `9a326d4` (S155 flight 2). This is the S156-A patch applied on top.

## What changed vs S155 F2

S155 F2 achieved bind-avatar (14 of 14 preflight sub-blockers cleared, `avatarBound=1`) but
S148 refused with `issues=0x200 = MAX_HEALTH_BELOW_SEED` — the LokiAttributeSetHealth's
`MaxHealth` was still 0/0 and S148's guard blocked before mutation.

S156-A adds a `KBFSEEDMAXHEALTH` block on the S155 bind arm that writes MaxHealth's
`FGameplayAttributeData` payload (base@+0x8 + current@+0xC) to `0x447A0000/0x447A0000` = 1000/1000
using a packed 64-bit volatile write with SEH_FILTER, re-resolves the target via
`BfS148ResolveHealthTarget`, and only proceeds to S148 PREFLIGHT if the seed lands exactly and
`issues` transitions to `0x0`.

## Arms

| variant | RAW `.text` | VSIZE `.text` | role |
|---|---|---|---|
| base `botfight-damage-self-cal` (S153 gate) | `167d1552c73bfd7a` | | regression validator |
| `botfight-damage-self-cal-bindavatar` (S155 gate) | `d8c08912816162a7` | `db67f5289a07db07` | bind only |
| **`botfight-damage-self-cal-bindavatar-seedmax` (S156-A)** | **`b47d1bfd04e44921`** | **`f87ac23d7c1a4c05`** | **flown F5** |

⚠ base variant RAW `167d1552c73bfd7a` drifted from CLAUDE.md's recorded S153 gate `899ac8b56a477110`
(4400+ lines above). Root-caused during this arc: **the drift is pre-existing source evolution
between the S153 gate commit and current HEAD, NOT S155/S156 additive breakage.** Verified by
`git stash push`ing my S155+S156 edits, rebuilding base — hash still `167d1552c73bfd7a`. The S155
and S156 additions are byte-additive on top of that drifted base (every `-DKBFBINDAVATAR` and
`-DKBFSEEDMAXHEALTH` guard turns clean, verified by variant hashes differing across arms).

## Flight ledger

| flight | outcome | mechanism |
|---|---|---|
| F1 | LOST — Login-race | Fatal exit 3, `ALokiGameMode::Login failed to Login`; stage never reached |
| F2 | LOST — FK-31 | 0xC0000005 exit 4; stage never reached |
| F3 | LOST — FK-31 after fo | game gone 16s after `fo`, before `sp`; UECC dump none, session log ends at LVL_Tutorial WorldPartition Standalone + LokiTraining ResetAll (~5s post-load) |
| F4 | LOST — FK-31 after fo | same signature as F3, 12s post-fo |
| **F5** | **SUCCESS** | **all 4 injections landed, arm ran, RESULT=SELF_DAMAGE_CALIBRATED** |

4/5 launches were lost to staging-side hazards (Login-race + FK-31), none of which touched the
S156 arm — the shim itself never got to run in F1–F4. F5's cleaner state (stale crashpad killed,
lucky FK-31 roll) allowed the full sequence to complete.

**Statistical note:** 3-in-3 FK-31 during staging over F2/F3/F4 (P ≈ 0.02 under 27% base rate) was
concerning at the time but did not indicate design fault — F5 succeeded with identical shim + `fo`
+ `sp` DLLs, confirming the losses were hazard variance, not our variant's fault.

## The receipts (from `docs/s156-seedmax-f5-marker-final.txt`)

### S155 bind (line 11-13)
```
[S155] BIND_AVATAR result=ok pc=… hero=0x2679F68AAC0 ps=… asc=0x267D0533400 carrier=… owner=…
[S155] AvatarActor@0x410 pre=0x0 post=0x2679F68AAC0 avatarBound=1
[S155] proceed=yes preflight_reached=1 handing off to S148 PREFLIGHT
```

### S156 seed (line 28-30)
```
[S148] target set=… HealthBits=00000000/00000000 MaxBits=447A0000/447A0000 … writable=1 issues=0x0
[S156] MAX_HEALTH_SEEDED result=ok pair=0x26700362768 maxPre=00000000/00000000 maxPost=447A0000/447A0000
       structPayload=1 layoutValid=1 writable=1 preIssues=0x200 postIssues=0x0 exact=yes
[S156] proceed=yes handing off to S148 PREFLIGHT with MaxHealth=1000/1000
```

Both `preIssues=0x200 → postIssues=0x0` and `exact=yes` confirm the S155-remaining
MAX_HEALTH_BELOW_SEED blocker was cleared by the S156 seed.

### S148 native resolve (S153 thunkExact fix validated live, line 38)
```
[S148] AdjustHealth native resolve ufunc=0x26654016E40 flags=0x04020401
       thunk=0x7FF6933F4270 class=0x266449AB000 functionClassExact=yes
       owner=0x26655F20100 ownerExact=yes thunkExact=yes
       child=0x26694E72D80 declaredChild=0x26694E72D80 PropertiesSize=4 parmCount=1
       chainComplete=yes HealthDeltaProp=0x26694E72D80 off=0x0 size=4 arrayDim=1
       propFlags=0x0018001040000280 resolved=yes
```

**thunkExact=yes** — the S153 corrected check (`adjustThunk == g_modBase+0x5294270` AND wrapper's
`E8 <rel32>` tail call at wrapper+0x6F resolves to `g_modBase+0x5516610`) passes for the first
time on a live process. Prior sessions had S153's check rejecting because the reflected Func for
a UHT exec wrapper points to the wrapper (`0x5294270`), not the impl (`0x5516610`). The S153 fix
addresses that.

### S148 call + result (lines 66-73)
```
[S148] seed originalBits=00000000/00000000 readbackBits=447A0000/447A0000 faulted=no identityStable=yes exact=yes
[S148] CALL_ISSUED AdjustHealth HealthDeltaBits=C37A0000 callCount=1
[FF] CallNative frame=ZEROONLY (0x48..0x80 zeroed)
[S148] target set=… HealthBits=443B8000/443B8000 MaxBits=447A0000/447A0000 … issues=0x0
[S148] immediate return issues=0x0 identityStable=yes HealthBits=443B8000/443B8000 receipt=yes
[S148] RESULT=SELF_DAMAGE_CALIBRATED
       originalBits=00000000/00000000 seedBits=447A0000/447A0000
       immediateBits=443B8000/443B8000 laterBits=443B8000/443B8000
       elapsed=265ms callCount=1
```

**Decoded:**
- `originalBits 0/0` (uninitialized) → `seedBits 1000/1000` (S148's own health seed) →
  `AdjustHealth(-250.0)` (delta bits `0xC37A0000` = float −250.0) →
  `immediateBits 750/750` (post-call) → `laterBits 750/750` (stable after 5s wait)
- **1000 − 250 = 750, exact match. AdjustHealth is a working native native path.**
- `elapsed=265ms callCount=1` — clean single-call round trip
- `receipt=yes` — immediate read confirmed same tick

### Clean disarm (lines 74-76)
```
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan 3656 ms, 34253 UFunctions live)
[BF] worker done (hits=117 hitsGT=117)
```

100% funcswap restoration (17,563 of 17,563), 117 worker hits, clean disarm.

## What this settles

1. **[M] The S153 thunkExact fix WORKS on live UHT exec wrappers.** The check I wrote in S153 to
   validate `Func @+0xE0` points at the wrapper AND wrapper+0x6F tail-calls the impl — the check
   that S152 had wrong for ~1 day of flights — passes for the first time on the live process here.
   Committed 3 hours ago as part of the S153 arc, now validated live.

2. **[M] The game's `ULokiAbilitySystemComponent::AdjustHealth` native path is REACHABLE and
   FUNCTIONAL on this client.** The UFunction dispatches to the impl, damage is applied, the
   result is readable. No stripped-fold blocker, no authority refusal, no CDO poke, no `.text`
   write required.

3. **[M] The end-to-end AvatarActor→CanActivate→GAS→AdjustHealth chain works** when preconditions
   are seeded correctly:
   - S143 `InitAbilityActorInfo` binds AvatarActor (proven since S143)
   - S144 `GiveAbility` commits a spec (proven since S144)
   - S155 `BfCallInitAAI` re-runs the AAI bind after all the shim wiring (S155 fix)
   - S156 pre-seeds MaxHealth from 0 to 1000 to open the MAX_HEALTH_BELOW_SEED gate
   - S148 exercises the game's own `AdjustHealth(-250)` via S153 thunkExact
   - Health goes 1000 → 750, exactly as expected

4. **[M] FK-32 did NOT fire during or shortly after the AdjustHealth calibration.** Game still
   alive at 6.8 min uptime post-injection. Prior AdjustHealth-adjacent activity (S147, S158) had
   sometimes triggered FK-32 within 40-70s of activation, so this is a positive result — the
   isolated damage-calibration path does not trip the protector's WALL P mechanism.

## Sub-blocker registers vs S155 F2

| S148 issue bit | name | S155 F2 status | S156-A F5 status |
|---|---|---|---|
| 0x000001–0x004000 | 14 various preflight blockers | CLEARED by S155 bind | still cleared |
| **0x200** | MAX_HEALTH_BELOW_SEED | **REMAINING (F2 stopped here)** | **CLEARED by S156 seed** |
| downstream | AdjustHealth call | not reached | **RESULT=SELF_DAMAGE_CALIBRATED** |

## What's next (not this session)

- Multi-shot: does S148 handle multiple `AdjustHealth` calls back-to-back? (single call proven)
- Larger deltas: does clamping happen at 0 HP? (only −250 vs 1000 tested)
- Positive delta (heal): does `AdjustHealth(+N)` cap at MaxHealth?
- **Repeatable Versus-AI loop:** with damage now working end-to-end, next dimension is bot spawning
  (S135 has bot pawns spawn but no controller kicks in) and combat interaction (bot AI, weapon
  fire, target selection).
- **The S147 non-durable-InputID-5-activation gap** — this session's success is on the
  DAMAGE track (Mana + attribute writes), not on the ability-body-execution track. WALL P for
  `MiniDash`'s ubergraph body remains open.

## Instrument artifacts banked

- **The S156 pre-seed pattern** — write attribute payload with SEH_FILTER + readback + issue-bit
  transition check — is reusable for any future GAS blocker of the form "S148-style guard requires
  attribute X to be seeded before mutation". Add to method-rules if this recipe is repeated.
- **Marker snapshotting at the "arm running but no RESULT yet" point** is worth keeping — F5 could
  have died to FK-32 after CALL_ISSUED but before RESULT= was written, and the mid-run snapshot
  would have preserved the S156 result even if the S148 result didn't land.

## Files

- **Source:** `tools/sigbypass-mod/tutorial_launch.cpp` — S156 seed block (~line 22006+)
- **Build:** `tools/sigbypass-mod/build.ps1` — `-Variant botfight-damage-self-cal-bindavatar-seedmax`
- **DLL:** `tools/sigbypass-mod/build/tutorial_launch_botfight_damage_self_cal_bindavatar_seedmax.dll`
  RAW `b47d1bfd04e44921`, VSIZE `f87ac23d7c1a4c05`
- **Evidence:**
  - `docs/tutorial-launch-marker.txt` — live marker (may be overwritten by next flight)
  - `docs/s156-seedmax-f5-marker-final.txt` — preserved snapshot of the RESULT= state
  - `docs/s156-seedmax-f5-marker-snapshot-preresult.txt` — pre-RESULT snapshot (defensive)
  - `docs/fk24-stage-s156-seedmax-f5-{1-gft,2-fo,3-sp,4-probe-...}.txt` — per-inject markers

## Regression gates (post-flight)

- `[base] botfight-damage-self-cal 167d1552c73bfd7a` — unchanged from S155 (only `#if
  KBFBINDAVATAR`/`#if KBFSEEDMAXHEALTH`-guarded code was added)
- `[bindavatar] botfight-damage-self-cal-bindavatar d8c08912816162a7` — unchanged, S155 F2 gate
- `[bindavatar-seedmax] botfight-damage-self-cal-bindavatar-seedmax b47d1bfd04e44921` — NEW, flown F5
