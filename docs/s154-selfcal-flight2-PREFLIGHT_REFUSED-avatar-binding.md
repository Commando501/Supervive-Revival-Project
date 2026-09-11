# S154 self-cal flight 2 — `PREFLIGHT_REFUSED issues=0x3EC13F` (Flight 4's AvatarActor==0 blocker reproduces exactly; S153 thunkExact fix STILL unvalidated live)

**Live 2026-09-08**, first live exercise of the S153-rebuilt `botfight-damage-self-cal` shim.
Two flights in one session; results below.

> **Companion docs**:
> [docs/s148-self-damage-flight4.md](s148-self-damage-flight4.md) — the Flight 4 blocker this reproduces.
> [docs/coop-vs-ai-roadmap-s142.md](coop-vs-ai-roadmap-s142.md) §3.3 Phase 1a — the flight predicate.

## Headline

★★★★★ **[M] FLIGHT 4's `PREFLIGHT_REFUSED issues=0x3EC13F` (AvatarActor==0 binding) REPRODUCES
EXACTLY under the S153-fixed shim.** Two flights, one FK-31 staging death (Flight 1, base-rate)
and one clean run to receipt (Flight 2). Flight 2's arm ran end-to-end without disruption:
17,563 UFunction Func-swaps installed and cleanly restored, no `.text` write, no PI hook, no
FK-32 kill, game survived past receipt.

★★★★★ **[M] The S153 FK-1 thunkExact fix was NOT tested live.** The shim's PREFLIGHT gate
refused UPSTREAM of the AdjustHealth call. `adjustResolved` was never evaluated because
`issues=0x3EC13F` fired first. **S153's live validity remains OPEN** — this flight tells us
Flight 4's blocker is still there, not that S153's fix regressed.

⭐ **[M] `ascOwned=1` but `avatarBound=0`** — the player's ASC IS found and validated
(`ASC=0x1A798D2CD00, class=0x1A634100100`), but its `AvatarActor@0x410 = 0x0`. Same shape as
Flight 4. The upstream wall is that the possessed hero pawn (`hero=0x1A83A868020, class=BP_HERO_Ronin_C`)
was never wired into the ASC as its avatar, despite `sp.dll`'s GAS init running to completion.

⭐ **[M] The next arm is the KBFARMS=0x02 bind-only alias** per Flight 4's "Ideal next route"
item 2 — a shim that BINDS AvatarActor before evaluating the PREFLIGHT gate. Design known,
build not yet.

## Flight 1 — FK-31 staging death (base-rate hazard)

**Flight artifact**: `docs/tutorial-launch-marker.s154-selfcal-flight1-FK31-STAGING-DEATH.txt`,
`docs/crashwatch.s154-selfcal-flight1-FK31.log`, `dumps/crash-20260908-170309/` (178 MB dump)

- Launch: 17:03:09 (PID 43724, via `launch-redirect.ps1 -NoHook`)
- Staged cleanly: gft → fo → sp all injected, `[SP] done step=4 (hero possessed)` at 17:05:XX
- Then: crashwatch trigger `flushing session and queue before crashpad handler` at T+166.3s
- Exit code **-1073741819 (0xC0000005)** — access violation, matches FK-31 signature
  (`runtime.dll+1` — CLAUDE.md documented base-rate hazard, ~22-27% of launches)
- Stager attempted probe injection AFTER the game had already begun crashing;
  `VirtualAllocEx(RWX) failed: Access is denied. (ACG on?)` — the "ACG on?" heuristic in the
  stager was misleading; the game was terminating, kernel refused the RWX allocation on a dying
  process
- Marker at time of death: full GAS init sequence recorded through
  `[GAS] AFTER  ASC 0x1108FEAB380 Owner@0x408=0x1108E0784D0(LokiPlayerState_HeroAffiliated) Avatar@0x410=0x0(NULL)`
  and `RESULT: initialised 0 -> 0 *** STILL NOT INITIALISED ***` — the same AvatarActor==NULL
  observation that Flight 2 would later encounter

## Flight 2 — probe injected cleanly; PREFLIGHT_REFUSED at AvatarActor

**Flight artifact**: `docs/tutorial-launch-marker.s154-selfcal-flight2-PREFLIGHT_REFUSED-avatar-binding.txt`,
`docs/crashwatch.s154-selfcal-flight2.log`, `docs/fk24-stage-s154-selfcal-f2.out.log`

### Timeline

- 17:08:57 — launch (PID 44184, via `launch-redirect.ps1 -NoHook`)
- 17:09:22 (approx) — lobby park, ags serving armed match `match-9b9d2c887e2524f918e383a895f2f1c2`
- 17:11:XX — stager: pre-flight OK, uptime=111s past the -MinUptimeSec 110 default
- gft → fo (LVL_Tutorial load complete +9s) → sp (`[SP] done step=4 (hero possessed) +12s`)
- **17:13:XX** — probe injected: `Manual-mapping ... into PID 44184; remote image base:
  0x1A786050000; exception table: 0x1B2 entries; DllMain remote-thread exit: 0x1 (OK);
  verify: MZ ✓; manual-map complete`
- **~17:13:XX + ~4s** — S148 arm ran end-to-end
- Game survived past receipt; killed cleanly by operator (no FK-32)

### The verbatim receipt

```
[S148] ===== isolated self-owned ASC damage calibration =====
[S148] policy KBFARMS=0 seedBits=447A0000/447A0000 delta=-250 expectedCurrent=443B8000 laterMin=250ms laterTimeoutGrace=5000ms
[S148] owner-census class-chain mode=CLASSIFY_ONLY directChecks=5
[FS] arm: swapped=17563 BP UFunctions  (scan 3250 ms over 161662 objects, 34253 UFunctions total) -- NO .text WRITE
[S148] local-owner candidate[0] GI=0x1A66E876340 LocalPlayers[0]=0x1A66DEB0E00 PC=0x1A783C9B140
[S148] active owner GI=0x1A66E876340 class=0x1A70B62E080 LocalPlayers@0x40 Data=0x1A700088340 Num=1 Max=4 memberIndex=0 membership=1 scanComplete=1
[S148] owner LocalPlayer=0x1A66DEB0E00 class=0x1A633352680 PC@0x38 candidates=1 PC=0x1A783C9B140 class=0x1A77A543340 Player@0x458 Pawn@0x3F8 hero=0x1A83A868020 class=0x1A781EC3F10 Controller@0x400 ASCStorage@0xF00 ASC=0x1A798D2CD00 class=0x1A634100100 AvatarActor@0x410=0x0 avatarBound=0 ascOwned=1
[S148] world identity PCLevel=0x1A777EC9000 HeroLevel=0x1A777EC9000 LevelClass=0x1A63005AB00 OwningWorld@0xC8 World=0x1A77A40B5A0 class=0x1A62FFB6F00 OwningGameInstance@0x2D0 valid=1
[S148] SpawnedAttributes@0x0 prop=0x0 inner=0x0 expectedOwner=AbilitySystemComponent type=ArrayProperty innerType=ObjectProperty<AttributeSet> provenance=0 memberTypes=0 Data=0x0 Num=0 Max=0 healthCandidates=0 candidateIndex=0
[S148] registration scan complete=0 count=0 selectedAscOwns=0 censusClosure=0 set=0x0 ASC=0x1A798D2CD00
[S148] target set=0x0 class=0x0 Health@0x0 MaxHealth@0x0 HealthOwner=- MaxOwner=- HealthStruct=- MaxStruct=- expected=GameplayAttributeData HealthStructPtr=0x0 MaxHealthStructPtr=0x0 structPayload=0 superPropertiesSize=0 setPropertiesSize=0 layoutValid=0 HealthBits=00000000/00000000 MaxBits=00000000/00000000 CDO=0(certain=0) CDOOuter=0(chainValid=0) writable=0 issues=0x3EC13F
[S148] PREFLIGHT_REFUSED RESULT=PREFLIGHT_REFUSED issues=0x3EC13F; no Health write and no AdjustHealth call
[S148] funcswap drain complete; no admitted FsThunk body/OnPI overlaps restoration; new/prefetched roots parked at gate
[FS] disarm: restored=17563 of 17563 swapped (scan 3391 ms, 34253 UFunctions live)
[BF] worker done (hits=1 hitsGT=1)
```

### Interpretation

**What worked**:
- Local-owner census resolved cleanly: `candidates=1`, `LocalPlayers[0]`, `PC`, `Pawn`, `hero`, `Controller`, `ASCStorage` all found (`scanComplete=1`)
- ASC identity confirmed: `ASC=0x1A798D2CD00 class=0x1A634100100`, `ascOwned=1`
- World identity valid: `World=0x1A77A40B5A0`, `OwningGameInstance valid=1`
- 17,563 UFunctions Func-swapped without incident, all restored cleanly on disarm
- Game survived the entire arm — no FK-32

**What failed** (the `issues=0x3EC13F` bitmask, all cascading from AvatarActor==0):
- `AvatarActor@0x410=0x0 avatarBound=0` — the ASC has no avatar
- `SpawnedAttributes@0x0 prop=0x0 inner=0x0` — no attribute-set property found (upstream of ASC scan)
- `registration scan complete=0 count=0` — the ASC registration scan yielded 0 attribute sets
- `target set=0x0 class=0x0 Health@0x0 MaxHealth@0x0` — no Health target attribute found
- `layoutValid=0 writable=0` — final gate refuses because layout can't validate

**Comparison to Flight 4 (docs/s148-self-damage-flight4.md)**:
- Same `issues=0x3EC13F` bitmask
- Same `AvatarActor==NULL` root cause
- Same `PREFLIGHT_REFUSED` at same code path (`no Health write and no AdjustHealth call`)
- ⇒ The blocker is a **stable, reproducible upstream wall**, not a flaky/intermittent condition

## What this changes vs prior status

**Status per the docs/coop-vs-ai-roadmap-s142.md Phase 1a acceptance predicate**:
- Blocker #1 (damage pipeline unproven) — STILL UNPROVEN; the S153 fix path was never exercised
- New sub-blocker identified as gating #1: **AvatarActor binding must be wired BEFORE PREFLIGHT
  can pass**

**What is now [M]**:
- Flight 4's blocker reproduces reliably under S153-fixed shim
- The shim's PREFLIGHT gate is functioning correctly and correctly refuses at the identified wall
- Cleanup discipline is clean (17,563/17,563 funcswap restore, no FK-32)

**What is still [I,strong] / unknown**:
- S153 FK-1 thunkExact fix's live validity (Flight 3+ needed with AvatarActor wired first)
- Whether wiring AvatarActor pre-flight resolves ALL of the `0x3EC13F` cascade bits, or only some

## Next moves

### Immediate (S155-bindonly): design + build KBFARMS=0x02 bind-only alias

Per Flight 4's "Ideal next route" item 2 (`docs/s148-self-damage-flight4.md`):

1. Add a `KBFARMS=0x02` bit meaning "wire AvatarActor, then re-run PREFLIGHT, then execute
   AdjustHealth on success". The wiring recipe is documented in CLAUDE.md's GAS/WALL P section:
   - After ASC identity confirmed and PlayerState located
   - Direct `ULokiAbilitySystemComponent::InitAbilityActorInfo(pawn)` call (S143 [M] recipe)
   - Verify `AvatarActor@0x410` transitioned from 0 to non-null
2. Build variant name: `botfight-damage-self-cal-bindavatar` (or reuse the base variant with a
   new `KBFARMS` value; check `tools/sigbypass-mod/build.ps1` for the correct semantic)
3. Verify with the existing contract test at `tools/sigbypass-mod/tests/s148_build_contract_test.ps1`
4. Fly under same staging recipe (`fk24-stage.ps1` with `-Label s155-bindavatar`)

Estimated wall clock: ~1-2 hr including source edits + contract test rebuild + one armed
window (budget 3-5 launches for FK-31 base rate).

### Follow-up questions banked

- Does `sp.dll`'s existing S143 `InitAbilityActorInfo` recipe (in the `[GAS]` section of its
  marker output) reach AvatarActor binding? Flight 1's marker showed
  `AFTER  ASC ... Avatar@0x410=0x0(NULL)` even AFTER sp ran — suggesting sp's binding did NOT
  land. If sp's `InitAbilityActorInfo` call is nominally happening but not producing an avatar
  binding, that's a separate offline investigation before designing bind-only.
- Alternative: maybe the S143 recipe is complete but there's a subsequent teardown that clears
  AvatarActor. Investigate the timeline between sp's `AFTER` observation and the S148 probe's
  observation to see if the ASC was ever bound at any point.

## Rules banked

### R-S154-a: "ACG on?" errors from `VirtualAllocEx` may actually be the target process DYING mid-call (kernel refuses new allocations on a terminating process, which manifests as ACCESS_DENIED). Do not diagnose as ACG activation without checking process state at the moment of the failure.

Applied here: Flight 1's `VirtualAllocEx(RWX) failed: Access is denied. (ACG on?)` was actually
the game process crashing (0xC0000005 FK-31) simultaneously with the stager's probe injection
attempt. Reading the crashwatch log at the same timestamp shows the crash trigger fired at
T+166.3s, right when the stager's 20s post-sp gap elapsed and it attempted VirtualAllocEx.
`tools/inject/main.go`'s heuristic is misleading in this context; consider updating it to
distinguish "process terminating" from "ACG active" via a `WaitForSingleObject(hProcess, 0)`
check with `STILL_ACTIVE` before the VirtualAllocEx.

## Files preserved

- `docs/s154-selfcal-flight2-PREFLIGHT_REFUSED-avatar-binding.md` — this doc
- `docs/tutorial-launch-marker.s154-selfcal-flight1-FK31-STAGING-DEATH.txt` (Flight 1 marker at death)
- `docs/tutorial-launch-marker.s154-selfcal-flight2-PREFLIGHT_REFUSED-avatar-binding.txt` (Flight 2 marker at receipt)
- `docs/crashwatch.s154-selfcal-flight1-FK31.log` (Flight 1 crashwatch)
- `docs/crashwatch.s154-selfcal-flight2.log` (Flight 2 crashwatch — game survived, so no crash trigger)
- `docs/fk24-stage-s154-selfcal.out.log` (Flight 1 stager log)
- `docs/fk24-stage-s154-selfcal-f2.out.log` (Flight 2 stager log)
- `docs/launch-redirect.s154-selfcal.out.log`, `docs/launch-redirect.s154-selfcal.flight2.out.log`
- `dumps/crash-20260908-170309/` (Flight 1 178 MB crashwatch dump)

## What S154 did NOT do

- Not exercise the S153 FK-1 thunkExact fix live (PREFLIGHT_REFUSED upstream)
- Not resolve WALL E (Blocker #2) — deferred to a subsequent flight with bind-only shim
- Not achieve `SELF_DAMAGE_CALIBRATED` — Phase 1a of the S142 roadmap remains INCOMPLETE
- Not modify CLAUDE.md's "S153 NOT FLOWN" caveat — the fix has still not been exercised live
