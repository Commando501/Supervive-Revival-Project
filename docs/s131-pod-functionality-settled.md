# S131 — THE DROP POD IS FUNCTIONAL. IT IS INITIALISED, ALIVE, AND FLYING — IN THE WRONG DIRECTION.

**2026-08-20.** One armed window, one client. Backend-plus-shim, **zero `.text` writes, zero PI hooks**;
the only write in the whole sitting is S130's three-byte CDO poke, readback-verified.

Read `docs/next-session-prompt-s131.md` for the question, then this. Primary evidence:
`scratchpad/s131/evidence/` — `PREREG-s131-pod-functionality.md` (written before any launch),
`RESULT-poolspawn-s131-live.txt`, `RESULT-routeE-E1-s131-live.txt`,
`RESULT-dropplane-b1only-s131.txt`, `Loki-s131-armed-window.log`.

★★★★★ **FORWARD POINTER — THE RECIPE §14.1/§14.3 PROPOSED WAS FLOWN THE SAME DAY, AND IT WORKS.
THE DROP-POD DISMOUNT RUNS AND IS USABLE. Read `docs/s132-dismount-settled.md`.**
Appending the PlayerState to `ULokiRideableComponent::PlayersAttached` (`+0x130` Data / `+0x138` Num /
`+0x13C` Max) using the game's own `ResizeGrow` at **`0x00F988D0`** — the exact function the fifth
wall's own tail calls at `0x55CD75B` — and then calling `AuthPlayerDetachPlayerFromRidable`
(impl **`0x55CCCB0`**, exec thunk `0x5456100`) through the S55 direct `UFunction.Func` thunk takes the
hero **out of the pod**, un-hides it, restores its collision and movement, and places it at a chosen
landing actor. **Risk class DATA; zero `.text` writes, zero PI hooks, zero CDO pokes.** Four dismounts
in one armed window, then two further flights that landed the hero at a chosen `LokiPlayerStart`, each
against a within-run negative control (same detach, same component, same primitive, `PlayersAttached`
EMPTY) that never moved the hero.
⇒ **Three things in this file are annotated in place by that flight** — §10.2 P5 (`ContainsPlayer`
reads the WRONG array), §12.1 (why both player arrays are empty), and §14.1 ("expect a partial
dismount" was too pessimistic). Everything else here stands.

---

## 0. THE ANSWER

S130 measured `SpawnDropPodForTeam` returning `true` with a DropPod census delta of `+2` and stopped
there. **The census counts objects.** S131 built the readout that looks at what the object IS.

**[M] `InitializeDropPod` ran and all three of its discriminating writes landed**, against a
**within-run, same-class, same-instrument negative control of three other pods** that all read class
defaults in the same dump:

| field | class default | E1 pod | 3 control pods | source of the offset |
|---|---|---|---|---|
| `PodTeamIndex` | `-1` | **`0`** | `-1`, `-1`, `-1` | by name `@0x460` · AS bytecode `0x460` **AGREE** |
| `CurrPodDestination` | `(0,0,0)` | **`(-3206.4, 5070.5, 100.0)`** | `(0,0,0)` ×3 | by name `@0x478` · AS `0x478` **AGREE** |
| `bIsTeamLeaderPod` | `False` | **`true`** | `false` ×3 | by name `@0x45D` · AS `0x45D` **AGREE** |
| `LeaderPod` | `None` | `null` | `null` ×3 | **NON-DISCRIMINATING, a trap; not counted** |

★★ **`CurrPodDestination` is a payload fingerprint, and that matters more than the census ever did.**
It holds the exact `LandingLocation` this arm computed and passed — `(-3206.4, 5070.5, 100.0)`, the
value printed in the arm's own `E1 POSITIONS USED` line. **No other code path in the process has that
number.** So the pod is attributed to *our* call by its contents, not by a count and not by a timing
correlation. (See §6 — this is what rescues the result from the standing E0c control gap.)

**And the pod is not inert. It is flying.**

## 1. THE POD IS ALIVE AND MOVING — 20,000 uu/s, AND EVERY DIGIT IS ACCOUNTED FOR

In-arm samples of the E1 pod (`0x2BDA97A0200`), root `RelativeLocation`, resolved BY NAME:

| t | location | Δ vs first |
|---|---|---|
| 0 s | `(-3206.4, 5070.5, 20100.0)` | first sample, `attach=none` |
| +5.3 s | `(84837.9, 5070.5, 20100.0)` | `(+88044.3, 0, 0)` |
| +9.8 s | `(172846.5, 5070.5, 20100.0)` | `(+176052.8, 0, 0)` |
| +23.6 s | `(448933.8, 5070.5, 20100.0)` | `(+452140.1, 0, 0)` |

Then, by external read-only RPM on the still-live process, a two-sample velocity measurement over
8.023 s across all four pods:

```
pod                     X @ t0      X @ t1        dX        uu/s
0x2BD2B2DA8B0                -           -         -   (no root component)
0x2BD2B2DB0A0            -3206       -3206       0.0         0.0
0x2BD375119D0            -2776       -2776       0.0         0.0
0x2BDA97A0200          2769301     2928657  159356.0     19862.4
```

**[M] Only the E1 pod moves. The three controls are exactly stationary in the same measurement.**

★★★ **And the driver is named, from the shipped asset, to the digit.** A raw read of the E1 pod's
root component gives `ComponentVelocity = (20000.0, 0.0, 0.0)` — an exact round number — and
`bpdump BP_DropPod @props` says:

```
## [UActorComponent] ProjectileMovement_GEN_VARIABLE  (ExportType=ProjectileMovementComponent)
   - InitialSpeed           = 20000
   - MaxSpeed               = 20000
   - ProjectileGravityScale = 0
```

`InitialSpeed = MaxSpeed = 20000` explains the speed; `ProjectileGravityScale = 0` explains why Z is
**exactly** constant; local-forward `+X` explains the direction. Measured 19,862 uu/s vs declared
20,000 is 0.7 % — sampling jitter.

⚠⚠ **A NEAR-MISS WORTH RECORDING: `20000` is also this shim's `KPDSPAWNZ`** (the pod is spawned
20,000 uu above the landing point). Attributing the velocity to the shim's own knob would have been
effortless and completely wrong. **The cooked asset is what settles it** — method rule #2, read the
shipped artifacts. Check every suspiciously round number against the data before against your own code.

## 2. ⇒ THE POD IS FLYING *BECAUSE* `StartPodGameplay` NEVER RAN

Measured on the E1 pod, live: `bHasStartedGameplay = 0` · `PodMeshComponent = null` ·
`PodStateEvent.DropPodState = 0 (None)` · `bIsLocalPlayerPilot = 0` · `bSteeringEnabled = 0` ·
`bPilotHasPodControl = 0`. **`StartPodGameplay()` did not run** — every one of its writes is at its
default.

And `StartPodGameplay`'s **first act on the movement component is `Deactivate()`**
(`LokiDropPod.as:896`). The `ProjectileMovementComponent` is auto-active from spawn; the game turns
it OFF during the intro sequence and back on only via `SetDropPodState(Descending)` →
`StartPodMovement()`.

The reason it never runs is [M] and it is a **stripped stub**:

* `Loki::LokiIsServer()` impl is **`0x0F7EB60` = `xor al,al; ret` — it returns FALSE.**
  (`LokiIsClient` impl is `0x0B9E1F0` = `mov al,1; ret` — always TRUE.)
* In the AOT-compiled `ALokiDropPod::LokiBeginPlay_Implementation`, `0x596A3F9 call 0xF7EB60` is
  followed by `test eax,eax / jne` — so the whole block is skipped, and with it
  `0x596A495 call 0x56FBCF0` = `LokiTeam::SetTeamForActor` (which has exactly **one** caller
  image-wide, and that is how the function is identified).
* No team index ⇒ `OnTeamIndexChanged` never fires ⇒ `StartPodGameplay` is never called ⇒ nothing
  ever deactivates the movement component.

⇒ **[M] The pod is doing exactly what an un-managed drop pod would do: it flies off along its local
+X at its cooked cruise speed, at constant altitude, forever.** By the last read it was ~2.9 million
uu (≈29 km) from the origin and still accelerating toward its 20,000 cap.

⚠ **This falsifies the pre-registration.** PREREG §2.4 predicted *stationary*, and named the right
mechanism (`StartPodGameplay` gates the movement) but drew the sign backwards: `StartPodGameplay`
turns the mover **off**, not on. **Not running it leaves the pod moving.** Recorded as a falsified
prediction, not quietly reinterpreted.

## 3. AN INDEPENDENT ENGINE-LEVEL RECEIPT — the game's own log says the pod is a live actor

```
LogNiagara: Warning: NiagaraComponent(... BP_DropPod_Tutorial_C_2147471134.NS_Drop_CloudTunnel
   - NiagaraSystem .../NS_Drop_CloudTunnel) required LWC tile recache and wa[s ...]
```
Three of them, one per VFX system — `NS_Drop_CloudTunnel`, `NS_Drop_Clouds`,
`Niagara Thruster System`. **"required LWC tile recache" is UE5 reporting that a component travelled
far enough to need its Large-World-Coordinates tile re-based.**

⇒ the pod is a fully constructed actor whose **drop VFX are instantiated and ticking**, and the engine
independently confirms it moved a long way. That is a completely different instrument from our RPM
reads and from the census. ★ Exactly one `BP_DropPod_Tutorial_C_<n>` name appears in the whole log —
`_2147471134`, the E1 pod. The three control pods never log.

## 4. THE FOUR PODS SEPARATE THREE WAYS — and one of them is a new fact about deferred spawns

| pod | how spawned | `RootComponent` | `InitializeDropPod`? | motion |
|---|---|---|---|---|
| `0x2BD2B2DA8B0` | `SpawnPoolableActorFromClassDeferred` (**never finished**) | **`0x0` — NONE** | no | unreadable |
| `0x2BD2B2DB0A0` | `SpawnPoolableActorFromClass` (non-deferred) | present | no | stationary, 31.7 s |
| `0x2BD375119D0` | `BeginDeferredActorSpawnFromClass` + `FinishSpawningActor` | present | no | one 364.5 uu displacement, then stationary for 31.7 s |
| **`0x2BDA97A0200`** | **`SpawnDropPodForTeam`** | present | **YES** | **flying, 19,862 uu/s** |

★★ **[M] A pooled DEFERRED spawn that is never `FinishSpawningActor`'d has a NULL `RootComponent`.**
The probe printed `location: UNREADABLE (root=0x0 RelativeLocation@0xFFFFFFFF) -- instrument, not a
zero`, and the *same class* resolved `RelLoc@0x158 (by name)` on the three other pods **in the same
dump** — so the class-level resolution demonstrably works and `root=0x0` is a statement about the
instance. That is a positive control living inside the negative result.

⚠ The P3 pod's single 364.5 uu displacement is **[I]**: consistent with its own projectile component
firing briefly and stopping on contact (it spawned at Z=468, near the ground, while E1 spawned at
Z=20,100 with nothing to hit), but **no impact was observed**. Do not write it up as measured.

## 5. THE FIFTH WALL WAS **NOT** TESTED — and the zero that says so is a trap the pre-registration caught

`SpawnDropPodForTeam` calls `AuthPlayerEnterWorldAttachedToRidable` inside
`if (ULokiRideableComponent::Get(pod) != null)`. That precondition **is satisfied**: the pod ships a
`LokiRideable_GEN_VARIABLE` of type `LokiRideableComponent` (cooked asset), and the in-arm rideable
census rose **20 → 21** exactly when the E1 pod spawned, one per pod, every time.

So the call was made. **And it did nothing, for a reason that has nothing to do with the wall:**

```
0x55CD510  test rdx,rdx      ; rdx = PlayerState
           je   <return>     ; <-- returns SILENTLY on instruction #1
```

`PilotPlayerState` on the E1 pod reads **null** [M], because `GetTeamDropLeader()` returns null,
because the only writer of the team-state field it reads —
`ALokiTeamState_TeamOnly::SetDropLeader` — is one of **FK-1's four empty stubs** (impl `0x0F7EC20 =
ret 0`), as is `ALokiPlayerState::AuthSetSpawnTeamLeader`.

⇒ `grep "failed to get the round game mode"` returns **0**, and **that zero is UNINTERPRETABLE**: the
function returned before it could ever reach the round-game-mode lookup. Recording it as "the fifth
wall was confirmed" would have been a textbook instrument artifact — PREREG §2.6 pre-committed to
exactly this reading, and §5's own offline grade is what supplied the `test rdx,rdx` that makes it
provable rather than merely suspected.

★ **The emit is NOT stripped** (it dispatches through `0x106B650`, a live logger with 22 other call
sites, two of whose messages appear verbatim in the log corpus as `LogLokiGameMode: Display: …`), so
the grep *would* have worked had the branch been reached. The blocker is the null argument, not the
instrument.

⇒ **NEXT LEVER, and it is one data poke:** `ALokiPlayerState::IsSpawnTeamLeader` (impl `0x56C2060`,
real, decrypted in all three images) is a **pure read** of `[TeamState+0x688]`. Poking that field on a
live `ALokiTeamState_TeamOnly` gives `GetTeamDropLeader` a non-null answer without calling either
stub — and then `SpawnDropPodForTeam` exercises the rider handoff for real. Same write class as the
CDO poke: one aligned heap field, readback-verifiable, no module image touched.

## 6. THE E0c CONTROL GAP IS STILL OPEN — and this result does not depend on it

The arm again printed `E-VERDICT: E1 RAN BUT IS NOT ATTRIBUTABLE`, because E0c — the only control for
the `[UFunctionVtable+0x378]` marshaller that E1's dispatch takes — has no callable candidate on this
class chain. **That caveat is about the DISPATCH MECHANISM and it is unchanged from S130**, so it
cancels in any S130-vs-S131 comparison.

★★ **But the pod-state readout does not rest on it at all.** The census delta needed the control
because a `+2` could in principle come from anywhere. A pod carrying `CurrPodDestination =
(-3206.4, 5070.5, 100.0)` — the exact vector this arm computed and passed — cannot. **A payload
fingerprint attributes a result where a count cannot**, and that is the reusable lesson: when a
control is unavailable, look for a field whose *value* is unique to your call.

## 7. THE INSTRUMENT, AND ITS OWN CONTROLS

`PdPodDump()` in `tools/sigbypass-mod/tutorial_launch.cpp` (RM_DROPPOD **and** RM_POOLSPAWN). Pure
guarded reads. It costs **no extra `GUObjectArray` sweep** — the pod-actor set is latched during the
census that already runs, because one sweep costs 1.2–2.6 s of game thread here.

Controls, all measured in-arm:

* ★ **By-name calibration: PASS on every dump.** `bCanEverReplicate` resolved by name → `0x6C` vs
  S130's independently measured `0x6C`; `bEnablePooling` → `0x2D3` vs `0x2D3`. Two instruments,
  agreeing, on the live class.
* ★★ **AS-bytecode vs live FProperty offsets: 76 agree, 0 DISAGREE** across the E1 arm (and 36/0 in
  the poolspawn arm). The Angelscript `ADDSi`/`LoadThisR` operand really is a byte offset from `this`
  — S131 lane 1 raised that from [I] to **[M]** offline (a 50/50 ordered-identical match against the
  AOT-compiled x86 constructor, replicated **12/12 classes / 214 pairs**), and the live run then
  agreed with it on every cross-checked field.
* ★ **`NOT RESOLVED BY NAME` is a distinct printed state**, never a value. `bHasStartedGameplay` has
  **no UPROPERTY** (predicted offline by lane 1), so it fails name resolution every time and the probe
  says so in words before falling back to the AS offset with an explicit label. A missing property and
  a `0` are the same bytes; this is what keeps them apart.
* ★ The three poolspawn pods are the **negative arm**, taken with the same code on the same objects in
  the same dumps.

⚠⚠ **AND THE VERDICT TOOL ITSELF SHIPPED THE PROJECT'S DOMINANT DEFECT.**
`scratchpad/s131/tools/pod_verdict.py`'s field regex had a **single literal space** where the probe
prints `@0x%-4X` — two spaces for a short offset. It matched nothing and reported
**`UNINTERPRETABLE (nothing resolved)` for pods whose values are plainly in the log.** Caught only by
reading the raw marker next to the tool's output. **An analysis script is an instrument too.** Fixed,
with the defect documented in-file.

## 8. WHAT IS NOW TRUE, AND WHAT IS NOT

**Settled [M]:**
1. `InitializeDropPod` runs and its writes land — 3/3 discriminators, 3-pod within-run control.
2. The pod is a fully constructed actor: components instantiated, a rideable component, Niagara VFX
   live and ticking, and the engine logging LWC recaches for it.
3. It moves at its cooked `InitialSpeed` of 20,000 uu/s along local +X with zero gravity scale.
4. It moves **because** `StartPodGameplay` never ran, and that is because `LokiIsServer()` is a
   stripped `return false`.
5. A deferred pooled spawn that is never finished has a null `RootComponent`.
6. The pooled-spawn NULL is gone: `Failed to spawn actor of type` count is **0**, with the pool still
   reporting `PrimePools : Feature is not enabled, skipping` — S130 §25 confirmed again, live.

**Not settled:**
* **The fifth wall is UNTESTED** (§5) — blocked by a null drop leader, not by the wall.
* `C8`/`C9` still never fired; unexercised, not excluded.
* The E0c marshaller control still has no candidate (§6).
* Whether a pod that is *properly* managed would descend correctly is untouched — nothing in this
  sitting drove `SetDropPodState`, and `SetDropDodState`'s own `LokiIsClient` early-return forecloses
  it on this client anyway [M, lane 1].

## 9. COST, AND THE STAGING HAZARD

**Two launches for one armed window.**

* **Launch 1** died 15 s after `fo` — FK-31, the staging hazard. Exit `0xC0000005`, crashpad dump
  preserved (`dumps/crashpad-20260820-021954`). See `scratchpad/s131/evidence/FK31-kill-address-is-constant.md`,
  which turns that death into a result: **the kill jumps to one fixed address per boot session, the
  same address across every launch and across FK-7 and FK-31 alike** (31 minidumps, 3 boot eras), and
  it is not an offset from any loaded module. That gives FK-31 a cheap new experiment for the first
  time — map an executable page there and read the caller off the stack.
* **Launch 2** first failed to force-open because the **lobby map took 146 s to load** and `fo`'s
  console command fired mid-`LoadMap` and was swallowed. **The process was healthy**; re-running
  `fk24-stage.ps1` against the same live PID recovered it and produced the whole result.
  ⇒ ★ **A stager abort is not a dead launch. Check whether the process is alive before spending another
  one** — `LVL_Tutorial load complete -> TIMEOUT` with the game still running is a recoverable state.

★ The armed window lasted **>25 minutes** and the client was still alive at the end — long enough to
take external RPM reads, dump the decrypted image, and merge it. S130's "assume the client will not
survive" held for the *staging*, not for the armed window.

★ **Free bonus:** `usmapdump dumpimage` on the live drop-pod process contributed **+43 `.text` pages
(157,916 bytes), 0 overlap conflicts** to a new `dumps/merged3.dump.exe` — code the drop path had
never decrypted before. Driving a path forces decryption; do this every armed window.

---

# 10. ★★★★★ ADDENDUM — THE FIFTH WALL IS NOW CONFIRMED [M]. IT COST ZERO EXTRA LAUNCHES.

§5 closed with "the fifth wall was NOT tested" and named the blocker. Rather than bank that, the
**same live client** — still up at ~40 min with the world staged and the initialised pod present —
was used to test it directly. **No new launch, no `.text` write, no PI hook, no memory poke.**

Pre-registration: `scratchpad/s131/evidence/PREREG-rideable-direct-call.md` (+ Amendment 1, both
written before their injections). Evidence: `RESULT-rideable-s131-live.txt`,
`Loki-s131-rideable-confirmed.log`.

## 10.1 Why a direct call, and why the obvious lever was abandoned

§5's proposed lever was "poke `[TeamState+0x688]` so `GetTeamDropLeader` returns non-null". A
read-only enumeration killed it in one call:

> **[M] ZERO live instances of any class containing `TeamOnly`; the only `TeamState`-named live
> object is `Comp_TeamState_GlobalShop_GEN_VARIABLE`, a template.**

**There is no TeamState actor in the staged tutorial world to poke.** Routing through
`GetTeamDropLeader` depends on an object this world does not contain. ⇒ ★ **checking a lever's
precondition with a read-only pass before building the arm cost one command and saved a session.**

So `RM_RIDEABLE` (enum 29) calls the wall **directly**, with both arguments resolved live and BY
NAME: the pod's own `LokiRideable` component (`BP_DropPod_C.LokiRideable @0x6C8`) and a live
`ALokiPlayerState`. That is a fair test, because the recorded claim is that the failure is
*unconditional*.

## 10.2 The result — every pre-registered prediction landed

| # | prediction | outcome |
|---|---|---|
| P1 | `R0c ContainsPlayer(PlayerState)` returns false, no fault | **`fault=no USED=0`** ✓ — the primitive demonstrably reaches this component |
| P2 | the wall's own `IsValid` test passes | **PASSES** on both PlayerStates and on the component ✓ |
| P3 | `R1` returns without fault | **`fault=no`**, both candidates ✓ |
| **P4** | **the log line appears** (baseline **0**) | ★★★★★ **APPEARED, count 0 → 2 — exactly one per call** ✓ |
| P5 | `R2 ContainsPlayer` still false | **still 0** — no rider attached ✓ |

⚠⚠ **P5 IS WEAKER THAN IT LOOKS — S132 CORRECTION (2026-08-20).** **[M] `ContainsPlayer`
(impl `0x55D0270`) scans `PlayersInside` (`+0x120`), NOT `PlayersAttached` (`+0x130`).** So it only
ever tested one of this component's two player arrays, and a rider attached the way the wall's own
success tail attaches one — by appending to `PlayersAttached` — would leave it reading **false**.
P5's *conclusion* is still true here (the wall bailed before any attach, so nothing was in either
array), but the **reasoning does not generalise**: ⚠ **using `ContainsPlayer` as the receipt for an
append to `PlayersAttached` manufactures a false negative on a working append.** S132 hit exactly
that and had to switch receipts. ★ The receipt that does work is free and log-independent:
`PlayersAttached.Remove(PS)` (`0x55CCE23`) runs on every path past the detach's GATE 4, so `Num`
staying 1 vs dropping to 0 separates "bailed at a gate" from "ran past GATE 4" with no log
dependence — which matters, because the detach has ZERO log strings in its 440-byte extent.
⇒ `docs/s132-dismount-settled.md`.

```
[2026.08.20-07.56.47:371][874]LogLokiRideable: Error: ULokiRideableComponent::
      AuthPlayerEnterWorldAttachedToRidable failed to get the round game mode
[2026.08.20-07.56.47:372][874]  (identical, 1 ms later)
```

⇒ **[M] `AuthPlayerEnterWorldAttachedToRidable` reaches `0x55CD572`, gets 0 from the stripped
round-game-mode getter (`0xF7EB50`), and takes its failure branch — with a VALID, non-null
PlayerState and a valid component.** The S130/§lane-4 offline grade "REAL body, ALWAYS-FAIL" is now
**measured**, not inferred.

**What makes it a measurement and not a look:**
* a **positive control on the same object through the same primitive** (`R0c`), so a silent R1 could
  not have been confused with "the primitive never dispatched here";
* **both IsValid preconditions read out and PASSING**, so an absent log line would have been
  attributable to a named earlier bail instead of to the wall;
* **two independent PlayerStates** (`LokiPlayerState_HeroAffiliated`, `BP_LokiPlayerState_C`) — the
  arm refused to guess between them on its first build, and was changed to call once per candidate
  rather than pick;
* a **verified baseline of 0** and an exact per-call count (2 calls → 2 lines).

## 10.3 ★ A free by-product: the log category is now NAMED

S131 lane 4 recorded this Error's category `0x0A035E80` as **COVERAGE-BLOCKED / unnamed** — its
`FLogCategory` constructor sits on a page that has never been demand-decrypted, so the name could not
be read statically. Driving the path printed it: **`LogLokiRideable`**.

⇒ the S118 method pays out again — **push the code path, then read what the game says**. A category
that static analysis cannot name will name itself the moment its first message is emitted.

## 10.4 A second free by-product, from the run that REFUSED

The first build declined to guess between two PlayerStates and made no call. That "failed" run still
produced a measurement: its pod table shows

```
pod-cand[3] 0x2BD2B2DA8B0 ... PodTeamIndex=-1  LokiRideable@0x6C8 = 0x0 (-)
```

⇒ the never-finished DEFERRED pooled pod has **no rideable component either** — a second, independent
confirmation of §4's null-`RootComponent` finding, on a different property. ★ **A refusal that prints
its candidate table is not a wasted run.**

## 10.5 Where the drop path now stands

```
SpawnDropPodForTeam           RETURNS TRUE, pod spawns              S130
  InitializeDropPod           RAN, 3/3 writes landed                S131 §0
  FinishSpawningActor         components instantiated, VFX ticking  S131 §3
  the pod                     ALIVE and FLYING at 20,000 uu/s       S131 §1-2
  RemovePlayerFromPlane       empty stub                            FK-1
  AuthPlayerEnterWorld...     ** REACHED, AND FAILS ** [M]          S131 §10   <-- CONFIRMED
       -> the round-game-mode getter is a stripped `xor eax,eax; ret`
  MulticastOnDropPodLaunched  never reached (guarded on the drop leader)
```

**The wall is no longer a suspicion.** The blocker is now precisely stated: a *stripped server-side
getter*, in the same family as FK-1's four empty stubs, sitting between a fully working pod spawn and
a rider ever boarding it. ⇒ the next question is not "does the handoff work" but **"what does
`0xF7EB50` replace, and is there any other route to a round game mode object on this client"** —
which is an offline question, and free.

**Artifacts:** `tutorial_launch_rideable.dll` `.text` **`e221e4e415834067`** (the flown build;
`3cba72ec28e769b6` was the refusing first build). `play` re-verified **UNCHANGED** at
`9bc10a4552c596e1`. Build with `build.ps1 -Name tutorial_launch -Variant rideable`.

---

# 11. THE WALL IS SHARED, NOT ONE FUNCTION'S BUG — and `AuthPlayerEnterWorld` is a NAMED GAP

Same live client (47 min), third injection, still zero launches. Pre-registration: Amendment 2 of
`scratchpad/s131/evidence/PREREG-rideable-direct-call.md`, written with exact baselines before
injecting. Evidence: `RESULT-rideable-v3-siblings.txt`, `Loki-s131-rideable-v3.log`.

Two `ULokiRideableComponent` entry points that **nothing this project runs had ever called** were
called, each once per PlayerState candidate.

## 11.1 ★★ R3 — the round-game-mode wall is a SHARED dependency [M]

`AuthPlayerPreSpawnOnAddToPlane` (impl `0x55CD800`, REAL) has its **own distinct bail string**
(`.rdata 0x8B1CE28`), so the log separates it from the attached variant with no ambiguity.

| counter | baseline | after | predicted |
|---|---|---|---|
| `AuthPlayerPreSpawnOnAddToPlane failed to get the round game mode` | **0** | **2** | 2 ✓ |

⇒ **[M] two different `ULokiRideableComponent` entry points, called with valid arguments, both fail on
the same stripped round-game-mode getter.** The wall is not one function's defect — it is a shared,
systemic dependency, in the same family as FK-1's four empty server-authority stubs. That materially
changes what "fix the wall" would mean: one getter, not one function.

⚠⚠ **P7 AS WRITTEN WAS FALSIFIED, BY MY OWN ARM'S DESIGN.** I registered "the `AttachedToRidable`
count must stay at 2" as a cross-contamination control. It went **2 → 4** — because `KRDARMS` bit 1
was still set, so **the v3 arm re-ran R1 as well**. The prediction was wrong; the *separation* it was
meant to establish holds anyway, on two independent grounds: the two functions emit **different
strings**, and R3's pair lands **1.3 s after** R1's pair (08:07:51.667 vs 08:07:52.933). ★ A control
must be checked against what the arm actually does, not against what the previous arm did.

## 11.2 ⚠ R4 — `AuthPlayerEnterWorld` is UNINTERPRETABLE, and that is the recorded result

`AuthPlayerEnterWorld` (impl `0x55CCE70`, REAL, large body with a security cookie) was called twice —
`(PlayerState, Location=(-3206.4, 5070.5, 100.0), EffectClass=null, bRepositionPlayer=1)`, all four
slots bound from the live FProperty chain.

| readout | before | after |
|---|---|---|
| fault | — | **no**, both candidates |
| hero `BP_HERO_Ronin_C` location | `(0, 0, 13240.0)` | **`(0, 0, 13240.0)`** — unmoved |
| `PlayersInsideCount` (by name, `@0x11C`) | 0 | 0 |
| `bCanExit` | 0 | 0 |
| any new `LogLokiRideable` line | — | **none** |

**Pre-registered reading rule, applied:** *"hero does not move AND no new line ⇒ UNINTERPRETABLE
without more work. Do NOT record it as 'R4 does nothing'."*

⇒ **That is the record.** What IS established: it is REAL, it dispatched (same primitive, same object,
thunk present, no fault), and **it did not hit the round-game-mode wall** — no such line appeared for
it, while R1 and R3's did in the same run. So it bailed through one of its **own** guards, before any
logging point.

★ That is progress with a name attached: `AuthPlayerEnterWorld` is the one entry point on this
component NOT blocked by the shared getter, and the only thing standing between it and an effect is a
guard nobody has read yet. **Transcribing `0x55CCE70`'s prologue guards is the next offline task, and
it is free.**

⚠ Its silence is also a limit of the instrument: nothing in this arm proves R4's *effects* would have
been visible if it had produced any. `bRepositionPlayer=1` and the hero-location sampling were chosen
precisely so a success would be unmissable, but a **partial** success (state written, no reposition)
would read as this same null.

## 11.3 The instrument held up

`PlayersInsideCount` resolved **by name** at `@0x11C` and was printed on every state line, so "0" is a
read value rather than an absent one. The hero resolved as exactly **1** live `BP_HERO_Ronin_C`, was
printed by address, and `RdState` is written to say **UNAVAILABLE** rather than print a zero if it ever
fails to resolve — so "the hero did not move" cannot be manufactured by a missing hero.

**Artifact:** `tutorial_launch_rideable.dll` `.text` **`dd2281adce965add`**, `KRDARMS=0x3F`,
`KRDREPOS=1`. `play` `9bc10a4552c596e1` and `dropplane_b1only` `5b4467b0105dec1a` re-verified UNCHANGED.

---

# 12. §11.2's GAP IS CLOSED — R4's null is NAMED, and `AuthPlayerEnterWorld` is NOT a way round the wall

§11.2 recorded R4 as UNINTERPRETABLE per the pre-registered rule. Ten minutes of offline
disassembly against `dumps/merged4.dump.exe` — the image that now contains these pages *because*
R4 executed — plus one read-only pass closed it. **[M], and it removes a lever rather than adding one.**

## 12.1 Blocker (a): R4 bails on an EMPTY `PlayersInside` array

`AuthPlayerEnterWorld` impl `0x55CCE70`, prologue guards transcribed:

```
0x055CCEA1  mov  eax,[rdx+0xc] ; shr 0x1e ; not al ; test al,1
0x055CCEBC  je   0x55CD4E7                 ; PlayerState IsValid fail -> SILENT
0x055CCEC2  mov    rcx,[rcx+0x120]         ; PlayersInside.Data
0x055CCEC9  movsxd rax,dword [rdi+0x128]   ; PlayersInside.Num
0x055CCED0  lea    rdx,[rcx+rax*8]
0x055CCED4  cmp    rcx,rdx
0x055CCED7  je     0x55CD4E7               ; ARRAY EMPTY   -> SILENT BAIL
0x055CCEE0  cmp    [rcx],r12               ; *it == PlayerState ?
0x055CCEE3  je     0x55CCEF3               ; found -> continue
0x055CCEE5  add    rcx,8 ; cmp rcx,rdx ; jne 0x55CCEE0
0x055CCEEE  jmp    0x55CD4E7               ; NOT FOUND     -> SILENT BAIL
```

⇒ **`AuthPlayerEnterWorld` requires the PlayerState to ALREADY BE IN the component's `PlayersInside`
array.** Confirmed BY NAME against live reflection on the actual component
(`scratchpad/s131/tools/rideable_state.py`): `PlayersInsideCount` **IntProperty @0x11C**,
`PlayersInside` **ArrayProperty @0x120 size 16** — exactly the `Data@0x120 / Num@0x128 / Max@0x12C`
the guard reads. And live: **`Data = 0x0, Num = 0, Max = 0`**, with **neither** PlayerState present.

★ **S132 NAMED THE CAUSE OF THAT EMPTY ARRAY — [M, strong]: the only reflected writers of EITHER
player array are EMPTY STUBS in this client.** `AuthAddPlayer` (thunk `0x2C2CE30` ⚠ **23-way ICF, NON-IDENTIFYING**, impl `0x0F7EC20`),
`AuthRemovePlayer` (same thunk, same impl) and `AuthSetCanJump` (thunk `0x5296F30`, impl `0x0F7EC20`) join the
already-known `AuthPlayerEnterWorldNew` — **four empty `Auth*` stubs on `ULokiRideableComponent`, not
one.** ⇒ both `PlayersInside` (`+0x120`) and `PlayersAttached` (`+0x130`) read `Data=0 Num=0 Max=0`
in a fully staged world **BY CONSTRUCTION**, and a data poke is the only route to populating either.
★ The obvious shortcut — "just call `AuthAddPlayer` instead of poking" — was CHECKED, not assumed.
REAL on the same class, for contrast: `AuthPlayerDetachPlayerFromRidable` `0x55CCCB0` ·
`AuthPlayerEnterWorld` `0x55CCE70` · `AuthPlayerEnterWorldAttachedToRidable` `0x55CD510` (REAL but
ALWAYS-FAILS — §10) ·
`AuthPlayerPreSpawnOnAddToPlane` `0x55CD800` · `ContainsPlayer` `0x55D0270` ·
`GetLandingTeleportLocation` `0x55D89F0` · `HasEverContainedPlayer` `0x55DCAA0` ·
`GetRidePosition` `0x55DAB50`. ⇒ `docs/s132-dismount-settled.md`.

⇒ **[M] R4 bailed at `0x55CCED7`.** §11.2's null is explained, and the explanation was reachable
offline for free. ★ The pre-registered "UNINTERPRETABLE" was the right *record*; it was not the right
*stopping point*.

## 12.2 ⛔ Blocker (b) — and it removes the lever: R4 calls the SAME stripped getter

The obvious next move was a poke: point `PlayersInside.Data` at a buffer holding the PlayerState, set
`Num=1`, call, restore. **Reading the success path first killed it:**

```
0x055CCEF3  mov  rax,[rdi+0xc0]        ; cached world (fallback getter 0x35AFC40)
0x055CCF22  call 0xF7EB50              ; <== THE SAME STRIPPED `xor eax,eax; ret`  (RVA recomputed
0x055CCF37  mov  rbx,rax               ;     with a machine, and 0xF7EB50 re-disassembled: 33 c0 c3)
```

**`AuthPlayerEnterWorld` fetches the round game mode from the same stripped getter.** It differs from
the attached variant only in *not immediately gating on it* — it carries the 0 forward
(`[rsp+0x50]`, `rbx`) and proceeds to a virtual call through `[PlayerState+0x470]`.

⇒ **It is NOT a way round the wall.** Getting past the array guard would land in code that has
already received a null round game mode. ★ **The poke was not run, and that is the result of the
analysis rather than caution:** its payoff collapsed once (b) was known, while its risk was real —
pointing a `TArray.Data` at a non-game-heap buffer means any `Empty()`/`RemoveAt()` on the success
path calls the allocator on a foreign pointer.

## 12.3 What this settles

* **[M] The round-game-mode getter is the single shared blocker across all THREE
  `ULokiRideableComponent` entry points examined** — `AuthPlayerEnterWorldAttachedToRidable`
  (§10, gates on it), `AuthPlayerPreSpawnOnAddToPlane` (§11.1, gates on it), and
  `AuthPlayerEnterWorld` (here, consumes it un-gated). One getter, three consumers.
* ⇒ The next-session task named in §10.5 is now the **only** task on this surface: identify what
  `0xF7EB50` replaced, and find any other route to a round game mode on this client. There is no
  sibling to try instead — that was worth checking, and it is now checked.
* ★ **Method note worth keeping: driving the path is what made this readable.** These pages entered
  `merged4.dump.exe` only because R4 executed them. The analysis that closed the gap was possible
  *because* the "uninterpretable" call was made.

---

# 13. ⚠⚠ A LANE'S HEADLINE FIND, REFUTED BY ONE LIVE READ — and why it mattered

The offline follow-up's lane A billed this as *"the lane's most consequential find"*:

> `0x55CE140` (`ULokiRideableComponent` vtable override) reads `World->AuthorityGameMode`,
> `IsA<ALokiRoundGameMode>`-checks it, and **caches it at `Component+0xE0`** ⇒ a free live readback:
> read `[RideableComponent + 0xE0]`; non-null means the only thing between us and the success path
> is the fold.

**It is wrong, and following it would have had S132 reading a delegate and drawing a conclusion.**

## 13.1 The refutation — live reflection, read BY NAME

`scratchpad/s131/tools/rideable_state.py` on the actual component:

```
OnCanExitChanged             0xD0   16  MulticastInlineDelegateProperty
OnPlayersInsideCountChanged  0xE0   16  MulticastInlineDelegateProperty   <== NOT a game-mode cache
OnPlayerEntered              0xF0   16  MulticastInlineDelegateProperty
```

⇒ **[M] `ULokiRideableComponent + 0xE0` is `OnPlayersInsideCountChanged`, a 16-byte multicast
delegate** — the same offset lane E independently assigned it from `OnRep_PlayersInsideCount`
(`0x55E0FC6`). And a raw read of `+0xD8..+0xF0` on **all three** live rideable components returns
**all zeros**, so the proposed readback would have returned null on every one of them.

## 13.2 Where it went wrong — and lane A's own caveat already said so

`0x55CE140` really does do what lane A describes: `rbx = rcx = this`, `[rbx+0xC0]` (a
`UActorComponent::WorldPrivate` read), `[rax+0x250]` = `World->AuthorityGameMode`,
`IsA<ALokiRoundGameMode>`, then `mov [rbx+0xE0], rdi`. **The disassembly is right. The CLASS
ATTRIBUTION is not.**

Lane A reached `ULokiRideableComponent` from a vtable-boundary walk it flagged in the same paragraph:

> *"The exact vtable slot index is **UNRESOLVED** — adjacent vtables are contiguous in `.rdata` and my
> boundary walk overruns (it reported 3142 slots, which is nonsense) … [I, strong], not [M]."*

⇒ ⚠⚠ **The report graded the class attribution `[I, strong]` and then stated the consequence as
`[M]`.** That is a grade silently upgrading across one inference step — the exact failure the brief
asked verifiers to catch, committed by the lane that was carrying the best news.

## 13.3 What survives, and it is still worth something

The *mechanism* is real and is a **corroboration**, not a lever:

* **[M] some unstripped `UActorComponent` lifecycle override resolves `World->AuthorityGameMode`,
  `IsA<ALokiRoundGameMode>`-checks it, and caches the result.** That independently confirms lane E's
  `UWorld::AuthorityGameMode @ UWorld+0x250` and shows the type check is not stripped.
* ⛔ **It cannot help the wall.** The wall calls a getter that is `xor eax,eax; ret` with **zero memory
  operands** — no cached value anywhere can be injected into it. §12.2's conclusion is unchanged.
* ★ **Cheap open follow-up:** identify which component class that is (find the live class with an
  ObjectProperty at `+0xE0` whose vtable contains `0x55CE140`). If it is resident in a staged world,
  `[thatComponent + 0xE0]` is a free live pointer to the round game mode. **Useful for any future call
  site that actually consumes one — which this wall does not.**

## 13.4 The method point

Two lanes were given the same region and **disagreed about one offset**. The disagreement was visible
only because both reported the offset explicitly, and it was settled in one command by a third
instrument — live reflection read by name — rather than by preferring the more confident write-up.
★ **Ask two agents the same structural question and compare their offsets; a silent agreement is worth
much less than a caught contradiction.**

## 13.5 ★★★★★ AND THE OTHER LANE HAD THE CLASS RIGHT — CONFIRMED LIVE, WITH A BONUS

A second lane independently attributed `0x55CE140` to **`ULokiGameModeDropPlaneComponent`**, not the
rideable component. **One live read settles it, and delivers more than the dispute was about:**

```
Comp_GameMode_DropPlane_Tutorial  0x2BDBAA38680   (the live one, not the _GEN_VARIABLE template)
  +0xC0 WorldPrivate               = 0x2BCD33540C0  'LVL_Tutorial'
  World+0x250 AuthorityGameMode    = 0x2BD2D0BC020  'BP_LokiGameMode_Tutorial_C'
  World+0x258 GameState            = 0x2BDB251D030  'BP_LokiGameState_Tutorial_C'   <= control
  +0xE0                            = 0x2BD2D0BC020  'BP_LokiGameMode_Tutorial_C'    <= IDENTICAL
```

**[M] four things at once:**

1. **The class attribution is `ULokiGameModeDropPlaneComponent`.** `+0xE0` on *that* class caches the
   round game mode; on `ULokiRideableComponent` the same offset is a delegate (§13.1). Two lanes, one
   offset, opposite answers — arbitrated by a third instrument in one command.
2. **`UWorld::AuthorityGameMode @ UWorld+0x250` is confirmed live**, with `+0x258 = GameState` as the
   positive control in the same read, reproducing CLAUDE.md's recorded `UWorld+0x258`.
3. **The round game mode object EXISTS, is live, and is reachable** — `BP_LokiGameMode_Tutorial_C` at
   `0x2BD2D0BC020`, the same object S124 flew `GoToPhase` on.
4. ★★★ **AND `BP_LokiGameMode_Tutorial_C` PASSES `IsA<ALokiRoundGameMode>`** — because the caching
   code writes `+0xE0` *only* on the success side of that exact check (`0x55CE172 call 0x55C7DD0`,
   the **same helper** the wall calls at `0x55CD583`), and `+0xE0` is non-null. **That was never
   measured before.**

⇒ **If the stripped getter had returned this object, the wall's own `IsA` check would also have
passed.** The obstacle is the getter and nothing else on that stretch: the object is right there, of
the right type, already resolved by unstripped code on a sibling component.

⛔ It still cannot be *injected* — `0xF7EB50` has zero memory operands (§12.2). What changes is the
picture: this is not "the round game mode is unavailable on a client", it is "one accessor was
deleted while the object and the type check survive".

★ **And lane A's proposed free readback is real after all — on the right object.**
`Comp_GameMode_DropPlane_Tutorial + 0xE0` is a live, verified `ALokiRoundGameMode*`, available for
any future call site that genuinely consumes one.

---

# 14. ⚠⚠ CORRECTIONS TO §§10–13, FROM THE ADVERSARIAL VERIFIERS — one of my published claims is WRONG

All ten workflow agents finished (5 lanes + 5 verifiers, 0 errors). The verifiers refuted several
things, **including claims I had already committed**. Each is re-derived below with my own uncapped
rel32 scanner (`scratchpad/s131/tools/foldcalls.py`, every target machine-computed) and arbitrated
against `tools/strxref/index/pdata_union.csv`.

## 14.1 ⛔ WRONG, AND IT WEAKENS THE HEADLINE LEVER: the dismount is NOT fold-free

I wrote, in `CLAUDE.md` and the S132 handoff, that `AuthPlayerDetachPlayerFromRidable` has
**"ZERO folds"**. **That is false.**

```
range 0x55CCCB0 .. 0x55CCE68  (440 bytes -- 9 chained .pdata rows, extent confirmed)
  -> 0x0F7EC20  ret 0 (c2 00 00)   2 site(s)
       call at 0x55CCD5B
       call at 0x55CCE4E
```

**[M] two `ret 0` calls inside the detach.** `0x55CCD5B` takes `rcx = rdi` = the hero character,
immediately after the `IsA(ALokiHeroCharacter)` gate — i.e. a **stripped method on the character**,
not the benign "stripped diagnostic reporter" shape seen at `0x55CD7E4` (which marshals an FString).

⇒ **The true claim is "zero `0xF7EB50`", which is narrower than the headline it was supporting.**
Lever #1 (append to `PlayersAttached`, then call the detach) is still the best route, but
**"fully implemented and unstripped" is not supported** — two of its own calls do nothing, and what
they were supposed to do on the hero is unknown. Expect a partial dismount, and treat any null as
locating one of those two rather than as a failure of the append.

⚠⚠ **SUPERSEDED IN PART, 2026-08-20 (S132) — THE TWO-FOLD *FINDING* STANDS; THE *CONSEQUENCE* DRAWN
FROM IT DOES NOT.** The count above is correct and was re-confirmed in flight. What was wrong is
"expect a partial dismount": **[M] both folds are `0xF7EC20`, and their return values are NEVER TESTED
by the surrounding code, so neither gates anything.** Everything the detach does past its six gates is
a REAL body — `SetActorEnableCollision(true)` `0x339A550`, `SetPredropHidden(false)` `0x5599040`,
`GetLokiCharacterMovement` `0x55AC8E0` then `vt[+0x3E0](true)` and `[mv+0x1A0]=1.0f`,
`GetLandingTeleportLocation` `0x55D89F0` (963 B, REAL), the `SetActorLocation` teleport,
`MulticastOnPlayerEnteredWorld` `0x54537C0`, and `PlayersAttached.Remove` `0x11F3860`.
**Flown: the hero leaves the pod, un-hides, regains collision and movement, and lands where told.**
⇒ Lever #1 was the right route and the dismount is **usable, not partial**.
★ The forecast that DID hold: "treat any null as locating one of those two rather than as a failure
of the append" is still the right reading discipline — there was simply no null to locate.
⚠ Correct the shorthand while you are here: **`0xF7EC20` is `c2 00 00` = `ret imm16 0`, a VOID
return — it does NOT zero `eax`.** This repo's long-standing "ret 0" gloss reads as "returns zero",
which is a different claim, and it is part of what made these two calls look like they might gate
something. ⇒ `docs/s132-dismount-settled.md`.

★ A sibling lane had already flagged this and the final report dropped it. **When two lanes disagree,
the one that reports MORE stripped calls is the one to check first.**

## 14.2 ✔ NOT WRONG: `AuthPlayerEnterWorld` really does call the fold 3× — the verifier truncated the extent

A verifier refuted my "3 `0xF7EB50` calls" with "**it is 1**", over extent `0x55CCE70–0x55CD07D`
(525 B, "3 chained rows"). **The `.pdata` chain settles it:**

```
AuthPlayerEnterWorld   rows=6   extent 0x55CCE70..0x55CD506 = 1686 bytes
  0x55CCE70-0x55CCEFA  0x55CCEFA-0x55CCF0A  0x55CCF0A-0x55CD07D
  0x55CD07D-0x55CD464  0x55CD464-0x55CD4E7  0x55CD4E7-0x55CD506
```

`0x55CD07D` **is** a row boundary — so the verifier stopped somewhere that looks legitimate — but the
chain continues for three more rows. My scan over each candidate extent:

| extent | fold calls |
|---|---|
| `0x55CCE70..0x55CD07D` (525 B, truncated) | **1** — `0x55CCF22` |
| `0x55CCE70..0x55CD506` (1686 B, full chain) | **3** — `0x55CCF22`, `0x55CD405`, `0x55CD4C7` |

⇒ **the published "3" stands.** ★ And this is the *third* time this session that "extent" was the real
disagreement rather than the count — `strxref`'s per-row extent trap, restated: **chain the rows, and
print the extent next to any count derived from it, so a disagreement is visible rather than silent.**

## 14.3 Other corrections adopted

* ⚠ **"the wall's ONLY persistent output is one TArray append" is too strong.** It also stamps
  `movss [hero+0x1C10], xmm0` (`GetServerTime`) and **moves the character** — `LokiTeleportActor`
  (`0x56680F0`) then `SpawnAndMoveLokiCharacter_MoveStep` (`0x55C1B20`), with collision toggled on and
  off around them. **Actor position is not transient.** The append is the only *component*-state
  output; the rest is real world state.
  ★ **S132 FLEW IT, AND THE APPEND ALONE IS SUFFICIENT [M]:** poking only `PlayersAttached`
  (`+0x130` Data / `+0x138` Num / `+0x13C` Max) — none of the other outputs above — passes the
  detach's GATE 3 (array non-empty) and GATE 4 (PlayerState present), and the dismount runs. The
  append must use the game's own `ResizeGrow` `0x00F988D0` so the buffer belongs to the game's
  allocator; the predicted `NewMax = 4` is exactly what the arm logged (`AFTER … Num=1 Max=4`).
  ⚠ The **32-byte** request size is the offline derivation (`NewMax * 8`), NOT a logged value.
  It is an ARM, not
  an RPM write — `0x00F988D0` is not a UFunction, so the S55 primitive does not apply to it.
  ⚠ `TArray::Remove` (`0x11F3860`) writes ONLY `Num` — no free, no realloc — so a poked buffer is
  never freed by the detach and survives across repeated calls.
  ⚠ `PlayersAttached` is **NOT replicated** (no `CPF_Net`) [M, two disjoint instruments], which makes
  this write SAFER than an early S132 draft described, not riskier.
  ⚠⚠ **ORDERING TRAP:** do NOT also poke `PlayersInside` (`+0x120`). It makes `HasEverContainedPlayer`
  true, which turns the fifth wall itself into a SILENT no-op and destroys the error-line receipt.
  ⇒ `docs/s132-dismount-settled.md`.
* ⚠ **`SpawnAndMoveLokiCharacter_MoveStep` has NO record and NO exec thunk** — it is a raw native
  address, a different dispatch and risk class from the three reflected calls beside it, and it
  carries 2 `0xF7EC20` calls of its own.
* ⚠ **`LokiTeleportActor` (`0x56680F0`) is COVERAGE-BLOCKED** — its page is all-zero in `merged4`. Not
  a known fold, but its body is unread. **Do not call it REAL.**
* The fifth fold `0x00FC6CF0` has **7** distinct exec thunks, not 5.
* `Auth*`-but-not-`BlueprintAuthorityOnly` is **44/108 = 40.7 %** gradeable, not 32.8 % (the published
  denominator mixed gradeable with all-records). **This strengthens the `Auth*` finding.**
* The two bails log to **different categories** (`0xA036AC0` line 327 vs `0xA035E80` line 299), and the
  line that actually printed live is emitted at `0x55CD7C9` via `call 0x106B650`; the `call 0xF7EC20`
  at `0x55CD7E4` is a *second, separate* stripped call. My §10 write-up did not distinguish them.

## 14.4 What survives untouched

Every core claim of §§10–13 was re-derived and **CONFIRMED** by independent verifiers with their own
PE parsers and capstone: the fold is `33 c0 c3` with zero memory operands (6/6 images); the
round-game-mode pointer is a **pure guard**, dead after the two checks; the wall's extent is 746 B
over 5 chained rows; the log records decode to `LokiRideableComponent.cpp:299/327`; and `+0xE0` on the
rideable component is **not** a game-mode cache.
★ One verifier added the control I should have asked for and did not: **the success path
`0x55CD590–0x55CD767` contains ZERO calls to any fold** — which is what rules out "the later use of
the game mode was itself stripped, leaving an orphan guard over a gutted body".
