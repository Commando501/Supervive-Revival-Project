# S131 — THE DROP POD IS FUNCTIONAL. IT IS INITIALISED, ALIVE, AND FLYING — IN THE WRONG DIRECTION.

**2026-08-20.** One armed window, one client. Backend-plus-shim, **zero `.text` writes, zero PI hooks**;
the only write in the whole sitting is S130's three-byte CDO poke, readback-verified.

Read `docs/next-session-prompt-s131.md` for the question, then this. Primary evidence:
`scratchpad/s131/evidence/` — `PREREG-s131-pod-functionality.md` (written before any launch),
`RESULT-poolspawn-s131-live.txt`, `RESULT-routeE-E1-s131-live.txt`,
`RESULT-dropplane-b1only-s131.txt`, `Loki-s131-armed-window.log`.

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
