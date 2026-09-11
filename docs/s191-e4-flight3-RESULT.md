# S191 E4 FLIGHT 3 — a HOSTILE ENEMY MINION KILLED BY SHIM-DRIVEN DAMAGE ON THE TUTORIAL WORLD (2026-09-10)

★★★★★★★ **[M] THE DAMAGE HALF OF THE E4 PREDICATE IS MET.** A resident tutorial minion
(`BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C`) was spawned in front of the possessed hero,
InitAAI'd, seeded to 100 HP, and driven to **exactly 0 HP by the game's own
`ULokiAbilitySystemComponent::AdjustHealth`** via the S153-validated wrapperExact path —
extending S190 Track D's LokiBot-kill precedent to a **new class of hostile target (minion,
not bot) on the tutorial route**. The game's own ability system emitted the receipt
`LogAbilitySystem: Property Health new value is: 0.00` for the seeded minion.

⚠ SCOPE: the DIRECT-WRITE (KE4DIRECTGE) fallback is what killed the minion. The **natural
LMB player cast** — the strict predicate — is REFUTED-with-a-named-cause for this staging chain
(see §5). This is the graded consolation the plan explicitly designed for, plus a diagnosis
of the remaining wall.

## 1. The chain, end to end (all [M])

Flight 3 of 3 (attempts 1+2 both died in staging with `0xC0000005` — the known ~27% FK-31
staging hazard, unrelated to the E4 arm). Flight 3 launched game PID 21096 at 10:58:47.
Staging completed exit 0; probe injected at uptime ~200s; game alive at 512s (well past the
usual ~285s FK-32 window). Preserved: `docs/s191-e4-flight3-marker.log` (10 KB shim marker)
+ `docs/s191-e4-flight3-loki.log` (1.5 MB game log).

Receipts (verbatim from the marker):

```
[BF] PC=0x1E929277630 hero=0x20D9AC78020(BP_HERO_Ronin_C) PlayerState=0x1E80E654450(BP_LokiPlayerState_C)
[BF] player ASC (hero+0xF00) = 0x1E890C8CD00 (present -- WireAbilitySystem already ran, e.g. via play)
[BF] player teamOff=0xE88 teamIndex=-1
[BF] hero.Ability1         @0x1F00 = 0x1E9F7C507F0 (GS_Ronin_LMB_Selector_C)
[BF] ---- K_BIND: WireAbilitySystem + InitAbilityActorInfo ----
[BF] InitAbilityActorInfo(ASC=0x1E890C8CD00, Owner=0x1E98E8CCDD0(LokiPlayerState_HeroAffiliated,mode=0), Avatar=hero=0x20D9AC78020)
[BF] InitAbilityActorInfo returned ok
[BF] ---- K_GRANT (native GiveAbility): ability=0x1E9F7C507F0(GS_Ronin_LMB_Selector_C) ----
[BF] spec built=ok Ability@+0x10=0x1E92B5BB890(== CDO) Handle@+0xC=1 Level@+0x20=1 InputID@+0x24=3 Source@+0x30=0x20D9AC78020
[BF] grant(native) ok ; ActivatableAbilities(Items.Num@0x540) 0 -> 1 ; outHandle=1 *** ABILITY GRANTED (engine GiveAbility, committed in-hook) ***
[BF] ---- K_ALIVE: hero LivingState@+0x1090 = 0 (0=Dead 1=Alive 2=Knocked) ----
[BF] K_ALIVE: poked hero LivingState 0x0 -> 1 (Alive) readback=1 OK
[BF] ---- K_GASATTR APPLY ---- (6/6 attrs OK: MoveSpeed 500, MaxMoveSpeed 500, MaxAcceleration 50000, ...)

[E4] ================ S191 E4: SPAWN + SEED THE HOSTILE TARGET MINION ================
[E4] hero loc=(0.0,0.0,13240.0) rot(P/Y/R)=(0.0,-167.5,0.0) haveRot=yes forward=(-0.976,-0.217) -> target loc=(-195.2,-43.4,13240.0) (200 uu forward)
[E4] target candidate BP_Minion_TargetBot_TTK_C                      -> not loaded
[E4] target candidate BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C    -> RESIDENT
[E4] target candidate BP_Minion_SquadLeader_C                        -> RESIDENT
[E4] target candidate BP_Minion_KaijuAxeLeader_C                     -> RESIDENT
[E4] target candidate BP_Minion_Ghost_C                              -> RESIDENT
[E4] target candidate BP_Minion_VaultGuardShooter_C                  -> RESIDENT
[E4] target candidate BP_Minion_C                                    -> RESIDENT
[E4] selected target class = BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C @0x20DFDE98DD0
[E4] TARGET_SPAWNED minion=0x20CC6396DC0(BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C) loc=(-195.2,-43.4,13240.0) dxyFromHero=(-195.2,-43.4)
[E4] minion PlayerState=0x0 MinionTeamID=100 (100 => enemy of the player; do NOT poke -- WALL E [M] favorable)
[E4] minion ASC(minion+AbilitySystemComponentStorage)=0x20D1FAF8080(LokiAbilitySystemComponent)
[E4] InitAbilityActorInfo ok ; netsim@+0x800 0->0 ; AvatarActor@+0x410=0x20CC6396DC0 == minion (BOUND)
[E4] TARGET_SET_RESOLVE set=0x20C3262E620(LokiAttributeSetHealth) healthOff=0x70 maxOff=0x80
[E4] TARGET_SET_REGISTER setInSpawned=yes spawnedNum=2 (constructor-registered; no append needed)
[E4] pre-seed Health(Base/Curr)=00000000/00000000 Max(Base/Curr)=00000000/00000000
[E4] TARGET_SEEDED result=ok seedBits=42C80000 Health=42C80000/42C80000 Max=42C80000/42C80000 wr(h=1,m=1) exact=yes
[E4] E4_DIRECTGE_RESOLVE adjustFn=0x20C2A286E40 thunk=0x7FF7B7D74270 wrapperExact=yes tailReachesImpl=yes deltaOff=0 ok=yes
[E4] E4_DIRECTGE_FIRE reqDelta=-250.00 preHP=100.00 postHP=0.00 postBits=00000000/00000000 faulted=no *** DIRECT-WRITE DAMAGE APPLIED (fallback, not the predicate) ***
[E4] E4_COMPLETE RESULT=TARGET_READY

[FS] disarm: restored=17563 of 17563 swapped (scan 3843 ms, 34396 UFunctions live)
```

## 2. What the GAME'S OWN log says (Loki.log, at [592]/[594]/[612])

`docs/s191-e4-flight3-loki.log`, tail:

```
[16.02.23:394][ 592] LogLokiCharacter: Verbose: [Client][BP_Minion_KaijuAxeLeader_Stagger_Tutorial_C_2147471215] Cleared ignored allies when moving
[16.02.23:411][ 592] LogAbilitySystem: Property Health new value is: 0.00
[16.02.27:994][ 594] LogAbilitySystem: Display: GameplayCueNotify /Game/Loki/Characters/Heroes/Ronin/Abilities/Passive/ExecuteHighlight/GC_Ronin_Execute_Highlight.GC_Ronin_Execute_Highlight_C was not loaded when GameplayCue was invoked. Starting async loading.
[16.02.28:185][ 612] LogAbilitySystem: VeryVerbose: GC_Ronin_Execute_Highlight_C_2147471178 - OnActive
```

Three co-located game-side events, in causal order:

1. **The spawned minion is recognized by the game's `ALokiCharacter` tick** and prints its
   own `Cleared ignored allies when moving` (`_2147471215` = the strictly-DECREASING FName
   Number spawn-order oracle S137 established).
2. **The game's ability system emits `Property Health new value is: 0.00`** for the seeded
   minion. This is the game's OWN setter-side receipt for our AdjustHealth call — it went
   through the real Health-attribute mutation path, not just our RPM write.
3. **The Ronin PASSIVE `GC_Ronin_Execute_Highlight` cue fires with `OnActive`**: the game's
   Ronin execute passive scanned the world, found a low-HP enemy (our minion), and
   highlighted it as an execute target. This is a REACTION to the low-HP minion, not a
   consequence of the LMB tap (which came later; see §5). But it independently confirms
   the minion is a HOSTILE ENEMY of the player as far as the game's own targeting is
   concerned — a live re-confirmation of the offline WALL E finding.

## 3. What's new here (beyond S190 Track D)

- **[M] Track D's `EnsureHeroAffiliatedCarrier` primitive generalizes from LokiBots to
  spawned MINIONS on the tutorial route.** Same AddComponentByClass-like path is NOT
  needed for minions — the minion ships a constructor-built ASC and pre-registers its
  HealthSet in SpawnedAttributes (S190 F3/F4's fault mode does not apply).
- **[M] WALL E is favorable, confirmed LIVE:** MinionTeamID=100 read directly off the
  spawned minion (no PlayerState, no team component poke) vs player team -1.
  Independently corroborated by the Ronin execute passive treating the minion as an
  execute-eligible enemy.
- **[M] The residency-candidate-list pattern is a robust primitive.** Refuted my initial
  guess (`BP_Minion_TargetBot_TTK_C` not loaded) and auto-selected the correct tutorial
  minion. Reusable for any future spawn-a-target flight; the census output is a free
  world-state readout.
- **[M] S153 thunkExact (base+0x5294270 → tail → 0x5516610) validates on a NEW target class**
  in a NEW process — the primitive is stable across ASLR and target actor class.

## 4. What was hardened in this arm (and why)

The workflow's adversarial verify pass (`wf_92a08166-2b3`, 11 agents, 4.4M tokens) refuted
the initial hardcoded-Y placement and raised 3 residency/binding concerns. All applied
before flight 3 and all fired correctly:

- **Rotation-read facing (haveRot=yes).** Hero rotation read via
  `RootComponent.RelativeRotation`; forward = `(cos yaw, sin yaw, 0)`. Flight 3's hero
  faced Yaw −167.5°, forward `(-0.976, -0.217)` — a hardcoded −Y would have put the
  minion nowhere near the LMB cone.
- **AvatarActor readback after InitAAI** (`AvatarActor@+0x410 == minion (BOUND)`) — proves
  the bind, distinguishes an InitAAI-faulted no-op (S190 F3/F4) from a successful bind.
- **SpawnedAttributes registration check** — flight 3 confirmed the constructor
  registered the HealthSet, so DxAppend was correctly skipped as a no-op. Would have
  DxAppend'd if missing (S132 DATA-class primitive).
- **`NO_HERO_LOC` fail-closed** — refuse rather than spawn at a stale TrainingVolume
  transform if the hero loc is unreadable.

## 5. Why the NATURAL LMB CAST DID NOT ACTIVATE THE ABILITY

After `[FS] disarm restored=17563/17563` (shim fully out of the way, per S158's proven
end-state), 5 LMB events were sent via P/Invoke `mouse_event` with the game window in
foreground (SwitchToThisWindow + AttachThreadInput confirmed focus):

- 2× short tap (150ms → below the 240ms threshold, so the melee cone should have fired)
- 1× long hold (800ms → should have fired the ranged fireblast projectile)
- 2× shorter tap (100ms + 150ms → cone again)

**Loki.log added ZERO `LightAttack`, ZERO `Warmup`, ZERO `Channeling`, ZERO
`going from nullptr`, ZERO `Fireblast`, ZERO `Ability.*Activated`** in the 30 seconds
following the sends. The 800ms hold — which under any working LMB→Ability1 binding would
fire either the melee cone or the ranged fireblast — produced **1 new line total** in
Loki.log (unrelated heartbeat).

**[I, strong]** the LMB input path from the OS/window to Ronin's Ability1 is **not wired**
by our shim's K_GRANT alone. Our K_GRANT registers the spec via the ASC's native
`GiveAbility` virtual (Items 0→1, valid Handle 1, InputID 3), but the game's real input
binding — `BindAbilityActivationToInputComponent` — was never invoked with our spec + the
LMB→InputID mapping. S147's proof of natural-input activation used **LeftShift→InputID 5
(Ability3)** because that keyboard binding is pre-wired via the KWIREGAS possession chain
for the pre-existing hero kit spec; our newly-granted LMB spec has no such pre-wiring.

⚠ Alternate hypotheses NOT ruled out (any could contribute):
- The parked-tutorial world doesn't consume game-side input until the tutorial state
  machine advances (e.g. player must move first to leave a "cinematic" idle).
- A UI/menu widget consumes LMB before it reaches game input.
- The mouse-event API path (SendInput vs mouse_event) doesn't produce the specific input
  the game's UInputComponent listens for.

⇒ **The natural-cast half of E4 is refuted-with-a-named-cause for this staging chain**,
not the game's ability system. A follow-up session should investigate: (a) whether the
hero's UInputComponent has any LMB→Ability1 binding after our K_GRANT (RPM read of
InputComponent's action mappings), (b) whether firing WASD or a movement input first
"wakes up" the input consumer.

## 6. The measured DAMAGE (via the fallback) is FIRST-IN-PROJECT for a HOSTILE MINION

Before S190 Track D (2026-09-09): no shim-driven kill of anything on this project.
After Track D: LokiBots (spawned via `SpawnBot`, WALL-E-bypassed) can be killed via
AdjustHealth on their built ASC.

**After S191 E4 flight 3 (this doc):**
- First shim-driven kill of a HOSTILE ENEMY MINION (`BP_Minion_KaijuAxeLeader_Stagger_
  Tutorial_C`, team 100, resident in the tutorial world by shipped design)
- First execution of the Ronin execute-passive cue triggered by shim-driven damage
  (indirect confirmation the game recognized our seeded low-HP minion as a real target)
- First live confirmation of WALL E favorability (team 100 vs player -1, no team poke)
- First live validation of the S153 thunkExact primitive on a new-class target

## 7. Rules banked

- **R-S191-a:** the residency-candidate-list pattern (try N candidate classes,
  auto-select the first RESIDENT one, log every candidate's residency) is a robust,
  self-documenting primitive for spawn-a-target flights. Insulates against unknown or
  world-state-dependent asset loading. Refuted this session's own initial guess
  (BP_Minion_TargetBot_TTK_C) without wasting the flight.
- **R-S191-b:** rotation-read hero facing (via `RelativeRotation` off `RootComponent`) is
  cheap and dispositive; hardcoded facing (e.g. −Y from a prior session's measurement) is
  a defect waiting to fire. Flight 3's hero faced Yaw −167.5° vs Flight 1's Yaw −4°.
- **R-S191-c:** AvatarActor readback (`ASC+0x410 == the intended actor`) after InitAAI is
  the definitive bind check. Distinguishes "InitAAI ran silently OK" from "InitAAI
  faulted → AvatarActor stayed null → downstream AdjustHealth silently no-ops" (S190
  F3/F4's failure mode).
- **R-S191-d:** an ability GRANTED via native `GiveAbility` (K_GRANT) is NOT sufficient
  for natural-input activation. The game's `BindAbilityActivationToInputComponent`
  pathway must ALSO wire OS-input→InputID→spec. S147's proof used a pre-wired LeftShift
  binding; a freshly-granted LMB spec has none.
- **R-S191-e:** the game's own `LogAbilitySystem: Property Health new value is: <N>`
  emission is a FREE receipt for any AdjustHealth-shaped damage — a Loki-side witness
  that complements the shim's own arithmetic readback. Reusable for any future
  damage-on-a-minion flight.
- **R-S191-f:** the Ronin Execute Highlight passive (`GC_Ronin_Execute_Highlight_C`)
  fires an OnActive cue when a nearby enemy drops below the execute-threshold %. Free
  live confirmation of (a) target is enemy, (b) target's HP dropped low, (c) game's
  own targeting sees the target — reusable as a live WALL-E-and-damage witness.

## 8. Cost

- 3 launches, 2 lost to FK-31 staging deaths (`0xC0000005` at fo/sp waits — the
  documented ~27% clustered hazard), 1 fully successful staging + [E4] chain + fallback
  kill + natural-cast investigation.
- Attempt 2 succeeded through phase-0 on the initial arm but had `TARGET_CLASS_MISSING`
  (BP_Minion_TargetBot_TTK_C not resident); the resulting candidate-list fix landed
  flight 3.
- Regression gates BYTE-IDENTICAL through all edits:
  `botai b620e0ff3279e673`, `play 31af7667355f39d1`,
  `botfight-damage-self-cal-bindavatar-seedmax b47d1bfd04e44921`,
  `botfight-damage-self-cal-bindavatar-seedmax-postshots1 1925e9e80646a4fb`.
- E4 arm digests: `e4 RAW=6cb523c770d92bc1`, `e4-directge RAW=377f263062790979`
  (distinct treatment pair, `--dupes` clean).

## 9. What is now the sole remaining critical-path item for the FULL predicate

**LMB→Ability1 input binding on the staged tutorial world.** Every other component of the
full predicate is now [M]:

- [M] Player ASC is wired (K_BIND).
- [M] Ability1 (GS_Ronin_LMB_Selector_C) is GRANTED at InputID 3 (K_GRANT).
- [M] Hero is Alive (K_ALIVE) and has the full movement GAS block (K_GASATTR).
- [M] A hostile enemy minion can be spawned resident in front of the hero (E4 spawn).
- [M] The minion has a real ASC and can be InitAAI'd (E4 bind).
- [M] The minion's Health can be seeded low and driven to 0 via the game's own
  AdjustHealth (KE4DIRECTGE + Loki.log receipt).
- [M] WALL E is favorable (team 100 vs player -1).
- ⚠ **[NEGATIVE] a granted-but-not-input-wired spec does not fire on OS LMB events.**

⇒ The next investigation is either: (a) call the game's own
`BindAbilityActivationToInputComponent` (or its Loki equivalent) with our spec + InputID
after K_GRANT; (b) grant Ability1 via a different pathway that also wires the input
(e.g. through the tutorial's real hero-kit initialization); or (c) test whether firing
Ability1 by direct class-lookup + the ability's own `TryActivateAbilityByClass` on the
disarmed environment works (S158-style) even without OS-input routing. Any single one
would close the full predicate.

## 10. Files

- `docs/s191-e4-flight3-marker.log` — shim marker (all `[BF]`+`[E4]`+`[FS]` receipts)
- `docs/s191-e4-flight3-loki.log` — game log (`Property Health = 0.00`, Ronin execute cue)
- `docs/fk24-stage-e4-directge-3-*.txt` — per-injection stage receipts
- `tools/sigbypass-mod/tutorial_launch.cpp` — `BfE4SpawnSeedTarget` (definition after
  ~L18497, call site in DoBotFight phase-0)
- `tools/sigbypass-mod/build.ps1` — `e4` and `e4-directge` variants
- `scratchpad/s190/tools/send-lmb.ps1` — LMB tap driver (used for the natural-cast test)
