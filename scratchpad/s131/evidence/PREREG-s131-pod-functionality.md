# PRE-REGISTRATION — S131: are the drop pods S130 spawned FUNCTIONAL?

**Written 2026-08-20, BEFORE any launch.** Everything below is a prediction, not a result.
Amendments are appended at the bottom, each dated, each written before the flight it governs.

---

## 0. The question, and why it needs a new instrument

S130 fixed FK-22's bail 2 (`AActor::bCanEverReplicate` on the drop-pod CDOs) and measured
`SpawnDropPodForTeam` returning **true** with a **DropPod census delta of +2**.

**The census counts OBJECTS.** It says a `BP_DropPod_Tutorial_C` and an `ABP_DropPod_C` appeared. It
says nothing about whether `InitializeDropPod`, `FinishSpawningActor` or the rider handoff did
anything. Nobody has looked.

⚠ And re-reading the S130 evidence sharpens the headline: the `+2` is **1 actor + 1 AnimInstance**,
not 2 actors. The census bucket is a substring match on the derivation chain, so it also counts
`ABP_DropPod_C` (an AnimInstance) and `WBP_UI_DropPod*` (widgets). The S131 readout counts pod
**ACTORS** only — `(DPV_POD && DPV_ACTOR)`, where DPV_ACTOR is an exact strcmp for the leaf class
FName `Actor`.

## 1. The instrument

`PdPodDump()` in `tools/sigbypass-mod/tutorial_launch.cpp`, wired into **both** RM_DROPPOD and
RM_POOLSPAWN. It is **pure guarded reads** — no `.text` write, no heap write, no UFunction call.

It prints **in the arm**, immediately after the call, because all three armed windows in S130 died
artifact-less (§13.7) and an external RPM pass afterwards has no process to attach to.

It reads each field **two ways**:
* **by name** off the live FProperty chain (the standing project rule), and
* at the byte offset the **shipped Angelscript bytecode** uses for the same member.

with an explicit `AGREE` / `*** DISAGREE ***` verdict per field, plus a separate `NOT RESOLVED BY
NAME` state that is never printed as a value.

### 1.1 The offline offsets, and why they are believable

From `tools/asdump/out/GameMode/DropPhase/LokiDropPod.as.txt` (`InitializeDropPod`, 30 instructions):

| bytecode | member | offset |
|---|---|---|
| `LoadThisR 1117` | `bIsTeamLeaderPod` | `0x45D` (WRTV1 — a whole byte, not a bitfield) |
| `LoadThisR 1120` | `PodTeamIndex` | `0x460` (WRTV4) |
| `ADDSi 1144` | `CurrPodDestination` | `0x478` |
| `ADDSi 1200` | `LeaderPod` | `0x4B0` |
| `LoadThisR 1208` | `bHasStartedGameplay` | `0x4B8` |

The claim "that operand is a byte offset from `this`" is **[I]**, on four legs:

1. `ALokiDropShip::TeamDropPodClass` is `ADDSi 1144`, and `0x478` is the offset RM_DROPPOD has been
   reading it at **live** for four sessions;
2. the five numbers are in the **same order** as the members are declared (`LokiDropPod.as:193-216`);
   a type id would not be;
3. they fit **one self-consistent C++ layout** with correct natural alignment and no overlap, and it
   accounts for every declared member in between with nothing left over:
   `bIsTeamLeaderPod 0x45D(1) · PodTeamIndex 0x460(4) · bIsLocalPlayerPilot 0x464(1) ·
   ImpactIndicator 0x468(8) · GroundLaserIndicator 0x470(8) · CurrPodDestination 0x478(24) ·
   AttachedCrewPods 0x490(16) · bSteeringEnabled 0x4A0(1) · SteeringStartTime 0x4A8(8) ·
   LeaderPod 0x4B0(8) · bHasStartedGameplay 0x4B8(1)`;
4. the **second** operand (`134230872` / `134230881`) differs between the two classes and is constant
   within each — so that is the type id, and the first operand is not.

It is still **[I], not [M]**. Which is exactly why it is printed *beside* the by-name read rather
than replacing it.

### 1.2 The calibration control

`AActor::bCanEverReplicate` is **[M] at 0x6C** and `bEnablePooling` **[M] at 0x2D3** (S130 §11, from
AActor's own 114-entry UHT `PropPointers` array, three controls passing). The readout resolves both
**by name** on the live pod class and compares.

* both match → the by-name path is calibrated against a **different instrument** → `PASS`
* either mismatches → `MISMATCH`, and **every field value in the dump is declared UNINTERPRETABLE**
* neither resolves → `UNAVAILABLE`, explicitly a **coverage limit of the control**, not a failure of
  the readout. (It is [I] that native UHT properties appear in the FField `ChildProperties` chain at
  all. If they do not, the AS-offset cross-check still stands on its own.)

---

## 2. THE PREDICTIONS

### 2.1 The three positive discriminators — on the E1 pod

| field | class default | predicted after E1 | grade |
|---|---|---|---|
| `PodTeamIndex` | `-1` | **`0`** | [I] from the AS source; `KPDTEAM` default is 0 |
| `CurrPodDestination` | `(0,0,0)` | **the LandingLocation the arm printed**, i.e. `≈(-3206.4, 5070.5, 100.0)` | [I] |
| `bIsTeamLeaderPod` | `False` | **`true`** | [I] — `SpawnDropPodForTeam` passes a literal `true` (`SetV1 v3 1` at bytecode 0x0108) |

**Reading rule, fixed in advance:**
* **all three changed** ⇒ `InitializeDropPod` ran and its writes landed → **[M]**;
* **all three at defaults** ⇒ the body did NOT run, and `SpawnDropPodForTeam`'s `true` came from
  somewhere else — a **major correction** to FK-22 §28;
* **a mixture** ⇒ read the write order (`CurrPodDestination` → `SetPilotPlayerState` →
  `bIsTeamLeaderPod` → `PodTeamIndex` → `LeaderPod` → `SetOwner` → `QueueCrewForPodSpawn`); it names
  where execution stopped.

⛔ **`LeaderPod` is a TRAP and is NOT a fourth check.** Its default is `None` and
`SpawnDropPodForTeam` passes `null`, so the line can only ever agree. It is printed and labelled
NON-DISCRIMINATING.

### 2.2 The fields that depend on there being a drop leader

`v38 = this.GetTeamDropLeader(TeamIndex)` feeds `SetPilotPlayerState(v38)` and then
`SetOwner(GetPilotPlayerState())`.

**Prediction: `PilotPlayerState` and `Owner` both read `null` [I]** — the staged tutorial world has
no player on a drop plane, so `GetTeamDropLeader` should return null.

⚠ **A null on these two is therefore NOT evidence that `SetPilotPlayerState` failed to run.** Both
"no drop leader exists" and "the setter never ran" produce the same bytes. They are printed with that
caveat attached to the line, and **they do not enter the verdict**.

### 2.3 Did the pod go LIVE? — predicted NO, with a named reason

`StartPodGameplay()` (`LokiDropPod.as:896`) is what assigns `PodMeshComponent`, sets
`bIsLocalPlayerPilot`, and starts the pod's own behaviour. **Nothing on the `SpawnDropPodForTeam`
path calls it.**

| field | predicted | why | grade |
|---|---|---|---|
| `bHasStartedGameplay` | `false` | `StartPodGameplay`'s own guard; nothing calls it here | [I] |
| `PodMeshComponent` | `null` | assigned inside `StartPodGameplay` (`:937`) | [I] |
| `bIsLocalPlayerPilot` | `false` | set inside `StartPodGameplay` | [I] |
| `bPilotHasPodControl` | `false` | steering, needs gameplay | [I] |

⇒ **The pre-registered expectation is a pod that is CONSTRUCTED AND INITIALISED BUT INERT.** That is
a real, publishable state and it is *different* from both "the spawn did nothing" and "the drop phase
works". Recording it requires distinguishing it, which is what §2.1 vs §2.3 do.

### 2.4 Movement — predicted STATIONARY, and the control is built in

Three-plus location samples per pod, ≥4 s apart (`KPDPODSAMPLEMS`, plus the `KPDSETTLEMS` worker
sample). Delta measured against each pod's own first sample; threshold 1 uu².

**Prediction: every pod reads `stationary` [I]**, because the movement driver is behind
`StartPodGameplay`, which §2.3 predicts never ran.

★ **A pod that MOVES would falsify §2.3 and would be the strongest possible evidence of
"functional".** That is the outcome worth watching for and it costs nothing to look.

### 2.5 `bCanEverReplicate` on the INSTANCE

**Prediction: `0` on the E1 pod [I]** — an actor inherits its CDO's value at construction, and the
CDO was poked to 0 before the spawn. That is a receipt that this instance was built **after** the
poke, which is independently useful for attributing the pod to this arm.

⚠ It is [I] that a pooled/deferred spawn copies the CDO byte in the ordinary way. If it reads `1`,
that is interesting, not a probe failure.

### 2.6 The fifth wall — and the precondition that decides whether it is even reachable

`SpawnDropPodForTeam` calls `AuthPlayerEnterWorldAttachedToRidable` **only inside**
`if (ULokiRideableComponent::Get(pod, NAME_None) != null)`.

⚠⚠ **If no rideable component exists, that branch never runs and the sitting says NOTHING about the
fifth wall.** "The rider handoff failed" and "the rider handoff never ran" would read identically —
the exact instrument artifact this project keeps committing.

So the readout prints a **rideable-component census** (latched free by the same census pass) BEFORE
anything else, and says in words what a zero means.

* **If ≥1 live rideable component exists on the pod** ⇒ the branch ran, and
  `AuthPlayerEnterWorldAttachedToRidable` (impl `0x55CD510`) is predicted to take its failure branch
  at `0x55CD572` (a call to the stripped fold `0xF7EB50`) and bail into *"failed to get the round
  game mode"*. **Predicted: no rider attached.** [I], from S130 §26.
  ⚠ Whether that bail's `UE_LOG` **emits at all** is unestablished — this image folds many emits to
  `0xF7EC20`. If the emit is stripped, **absence of the string from `Loki.log` is uninterpretable.**
  Grep for it, but do not treat a zero as a negative.
* **If zero** ⇒ record it as a PRECONDITION result. Do not write up the fifth wall either way.

### 2.7 The within-run negative control

RM_POOLSPAWN's P1/P2/P3 leave live `BP_DropPod_Tutorial_C` actors spawned by a **raw** pooled or
ordinary spawn that **never went through `InitializeDropPod`**.

**Prediction: every poolspawn pod reads the CLASS DEFAULTS on all of §2.1** (`PodTeamIndex -1`,
`CurrPodDestination (0,0,0)`, `bIsTeamLeaderPod false`) **while the E1 pod reads the written values**
— same instrument, same objects, same dump. That is what makes §2.1 a measurement rather than a look.

⚠ If the poolspawn pods read `0 / (landing) / true`, then either the readout is reading the wrong
object or something other than this arm wrote them, and **§2.1 is void**.

⚠ This control only exists if RM_POOLSPAWN is injected into the same process first (the S130
sequence). If only RM_DROPPOD is flown, the control is a **cross-arm** comparison, which is weaker
and must be labelled as such.

---

## 3. WHAT MAKES THE SITTING VOID

Fixed in advance, so a bad run cannot be reinterpreted afterwards:

1. **No `[PL]`/`[PD]` init lines** ⇒ the probe never armed ⇒ VOID.
2. **`[FS] ZERO TARGETS SWAPPED`** ⇒ the ladder never advances ⇒ VOID.
3. **`E1 never dispatched`** ⇒ nothing to attribute; the dump is skipped by design and says so.
4. **Calibration `MISMATCH`** ⇒ every field value is UNINTERPRETABLE.
5. **`AS ... *** DISAGREE ***` on any of the four cross-checked fields** ⇒ that field is
   uninterpretable; the offline offset model is wrong and must be fixed before it is cited again.
6. **`LATCH OVERFLOWED`** ⇒ the pod list is a subset; counts are lower bounds.

## 4. Artifacts under test

`.text` sha256 (computed after the build, `-Name tutorial_launch` given explicitly — the recorded
trap is that `-Variant X` alone silently builds the default set and reports success):

| variant | `.text` sha256 | note |
|---|---|---|
| `droppod-pe-cdopoke` | `249a3cd2190eb334` | Route E + the CDO poke — the headline arm |
| `droppod-pe-cdoctrl` | `61fd0745c23e89f0` | same, read-only CDOs |
| `poolspawn-cdopoke` | `efe8db553bf511ba` | the negative-control population |
| `poolspawn-cdoctrl` | `85f3cee44c31b1cd` | same, read-only CDOs |
| `dropplane_b1only` | `5b4467b0105dec1a` | **UNCHANGED** — byte-identical to the S130 known-good staging artifact |
| `play` | `9bc10a4552c596e1` | **UNCHANGED** — the hard regression gate held |

★ The two `droppod-pe-*` arms share a `.text` SIZE (173,568 B) and so do the two `poolspawn-*` arms
(162,816 B). **Only the hash separates them.** Both pairs verified DISTINCT.

⚠ Recorded during this build and worth keeping: an **ungated** `strstr(n,"Rideable")` inside the
shared `DpEvalClass` moved `dropplane_b1only`'s `.text` hash **while leaving its `.text` SIZE
identical** (120,832 B both ways — the addition fitted inside the section's 512-byte padding). Caught
only because the hash was actually compared. Both new latches and the strstr are now gated on
`kRunMode`, so every other variant is dead-code-eliminated back to byte-identity.

## 5. Flight plan (the S130 sequence, which is the one that worked)

1. `forceTutorialMatch = true` in `server/internal/interactive/interactive.go`, rebuild `ags`.
2. Back up `docs/capture.log` (ags's behaviour on restart is recorded as both truncating and
   appending — unreliable in both directions, so back it up regardless).
3. Elevated: `.\configs\launch-redirect.ps1 -NoHook`
4. `.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_poolspawn_cdopoke.dll -Label s131-pool -AllowStale`
5. Into the SAME process, ≥20 s apart:
   `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_dropplane_b1only.dll`
   then `... tutorial_launch_droppod_pe_cdopoke.dll`
6. Copy every marker off as it is produced. **Take live reads in-arm, not afterwards.**
7. Set `forceTutorialMatch` back to `false` when done.

⚠ Budget: S130 spent **4 launches for 1 armed result**, and **3 of 3 armed windows died
artifact-less**. Assume the client will not survive.
