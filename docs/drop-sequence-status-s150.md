# The REAL drop / deploy sequence — status & feasibility (2026-08-31)

**Scope of THIS doc.** The operator has set a target distinct from the
`docs/coop-vs-ai-roadmap-s142.md` "minimum bot-fight loop" (which explicitly deferred the
drop phase and just teleports a hero onto the ground). The target here is the **real in-game
deploy sequence**:

> load into `LVL_Tutorial` → a **drop-plane flight** occurs → the **player selects a landing
> location** on the map → the **pod descends** and the sequence completes → the hero **deploys,
> is playable and movable**.

**Produced by** a 7-lane adversarially-scoped documentation census (one lane per stage) + a
synthesis pass, then a 4-lane offline disassembly grading pass (mount getter, ServerOnly,
pod/plane mutators, coverage control) with adversarial verification. Zero launches, zero
injections. Grades: `[M]` measured / `[I]` inferred / `[S]` speculative.

⚠ This is a **feasibility/status census**, not a claim that anything new was flown. The active
gameplay proof on the wider project is still S147's non-durable ability activation state; the
drop chain has not been re-flown live since ~S124/S125.

---

## 0. The one-sentence answer

**Every stage of the real drop sequence has been attacked, but NOTHING has ever run as a
natural sequence** — each green mark below is a diagnostic poke in isolation or "works but
wrong." The whole chain is gated by a single root cause (Loki's server-authority strip).

**VERDICT (offline grading, §6): GO — conditional on ONE staged flight, no `.text` write at any
point.** The wall this doc first flagged as possibly make-or-break — getting a real rider *into*
the pod — is **beatable**: the game's own mount function can't run (its round-game-mode getter
is a stripped null fold that feeds two hard bails), **but the mount never needed that function.**
The getter's result is a *pure precondition* — never read on the success body — and the success
body's only component-state write is the **same `PlayersAttached` append S132 already flew**, plus
real, decrypted positioning callees. So the mount is reachable by S132-style direct replication
of the success writes (data-poke + direct native call), never by calling the gated function. The
ride-tracking question is now **settled offline (§6.5):** a poke-appended `PlayersAttached` rider
does **NOT** co-move with the flying pod — nothing repositions `PlayersAttached` riders, and the
game's own mount body does no attach and is unreachable on this client. ⇒ a *real* pod ride
requires the arm to **attach the hero itself** (`AttachToComponent`, or per-frame reposition to
`GetRidePosition`); the all-proven-parts **"cinematic flight, poked landing"** fallback needs no
ride at all. An address-level `RM_MOUNT` arm spec is now decision-ready (§6.5); the only item not
resolved offline is Phase-B `StartPodGameplay`'s call target.

---

## 1. The single structural root cause

**Loki's server-authority strip.** Measured live, the client is `NM_Standalone` /
`ROLE_Authority(3)` and the *engine* grants `HasAuthority()` (s137). It is **Loki's own code**
that refuses authority: `Loki::LokiIsServer()` is hardcoded `false` (`0x0F7EB60 = xor al,al;
ret`), `LokiIsClient()` hardcoded `true` (`0x00B9E1F0 = mov al,1; ret`), and the family of
server-authority functions the drop design routes through are constant-returning folds:

| fold impl | bytes | returns | drop-chain functions folded onto it |
|---|---|---|---|
| `0x0F7EB50` | `xor eax,eax; ret` | null | round-game-mode getter (**mount**), `SpawnPlayer` |
| `0x0F7EC20` | `ret` (imm16 0) | **void** (⚠ NOT "eax=0") | `AddPlayerToPlane`, `AuthSetSpawnTeamLeader`, `SetDropLeader`, pod rider-array writers, the `CurrentPhase` setter |
| `0x1311870` | `mov byte[rdx],0; ret` | writes "not-server" pin | `ULokiBlueprintLibrary::ServerOnly` exec-pin (the DropPlane phase bind never installs) |

`Auth*` functions are enriched for stripping (gradeable `Auth*` 42.4% EMPTY, Fisher p=1.6e-28,
`coverage-audit-s101.md §C`). So each drop stage must be **hand-reimplemented as the stripped
server function would have fired it.**

**Two stages are NOT Loki strips** — do not conflate them:
- **Pod spawn** — blocked by a genuine UE actor-pool replication gate (`bCanEverReplicate`),
  `docs/s130-actor-pool-gate-settled.md §11-§13`.
- **Plane spawn fault** — blocked by UE World-Partition marker streaming (markers exist in
  `LVL_Tutorial` but are not resident at call time), `docs/fk22-dropphase-reachability.md`.

---

## 2. Stage-by-stage status (in sequence order)

Status legend: **WORKS_NATURAL** (game's own code fires it) · **POKE** (proven only as a
diagnostic hand-poke/direct-call, never in sequence) · **PARTIAL** · **BLOCKED** · **UNKNOWN**.

| # | Stage | Status | Wall (grade) | Shim-substitutable? |
|---|---|---|---|---|
| 1 | Phase advance → SpawnSelect/Lineup | POKE | frozen `CurrentPhase@GameState+0xA44`; setter lands on fold `0xF7EC20`; game only ever calls `GoToPhase(1)`, 193/193 [M] — `fk22:406-411,432,1094-1124` | **yes** (direct `GoToPhase(4)` self-drives the notification ladder to Combat, S124) |
| 2 | Plane spawn + flight | POKE→BLOCKED | (a) `PlaneStartPoint`/`PlaneEndPoint` in `LVL_Tutorial` but not streamed in → null deref [M] `fk22:1301-1327`; (b) `AddPlayerToPlane` empty stub [M] `fk22:152,200`; flight (`AuthStart`) never attempted | (a) no (need marker residency or BR procedural variant); (b) no |
| 3 | **Landing-selection UI** (predrop reticle/map pick) | **BLOCKED (unexplored)** | never rendered on any route; script cursor code dead, real validity native+uncalled, commit is native Server RPCs [M/I] — `angelscript-dropphase.md:365-376,1147-1155`; `s121-toggle-fix:388-401` | unknown |
| 4 | Pod spawn | POKE | C7 pool-replication gate `cmp byte[CDO+0x6C]` [M] — genuine UE gate — `s130 §11-§13` | yes (CDO byte poke, **class-default → not shippable**) |
| 5 | Pod flight | WORKS_NATURAL (wrong) | flies at cooked 20,000 uu/s **horizontal** cruise (measured 19,862) *because* `StartPodGameplay` never ran to deactivate the mover [M] — `s131 §1-§3` | n/a |
| 6 | Pod gameplay / pilot / steering | BLOCKED | `StartPodGameplay` gated on `LokiIsServer` [M] — `s131 §2,§8` | unknown (direct-call test proposed) |
| 7 | **Mount (rider INTO pod)** | **BLOCKED (no known route)** | one stripped getter `0xF7EB50` — 3 bytes, zero memory operands (**un-pokable**), thunk 0 direct callers (**Func-swap dead**); "one getter, three consumers" [M] — `s131 §10-§13,:344-347,536-557` | **no** (pending §6) |
| 8 | Descend | BLOCKED | same `LokiIsServer` gate + `SetDropPodState` `if(LokiIsClient) return` early-return [M] — `s131 §8` | unknown |
| 9 | Dismount / landing placement | POKE (works) | natural trigger `KickPlayersFromPod` behind `LokiIsClient`; `PlayersAttached` empty by construction [M] — `s132:162-198,475-492` | **yes** — hand-append `PlayersAttached` + direct `AuthPlayerDetachPlayerFromRidable` → hero on real terrain (Z=90.15), stands, runs; **6 flown landings**, but always from a *fabricated* attached-rider precondition |
| 10 | Playable + movable hero | PARTIAL | mover chain runs [M] (player fell 23,189 uu with `GravityScale=1.0`, S141); but player movement today is a **velocity-poke puppet** in `MOVE_Flying`, the stock `AddMovementInput` chain is dead [M] `s141:643-648`; terrain-walk at a landing point built (`play-atlanding-walk`) but **never flown** `next-session-prompt-s133:71-83` | input→accel yes (GAS port); terrain-walk untested |

**Nothing above has ever run as one continuous sequence.**

---

## 3. The two make-or-break walls — RESOLVED (offline grading §6)

> **Both cleared without a `.text` write.** (1) Mount is beatable by *replicating* the success
> writes of `AuthPlayerEnterWorldAttachedToRidable` (getter is a pure precondition), not by
> calling it. (2) The empty `AddPlayerToPlane` stub is substitutable via the DropPlane's own
> `ULokiRideableComponent` (same class as the pod) using the S132 array recipe. The residual
> unknown is a single staged read (does the rider track the pod in flight, §6). The framing below
> is the *pre-grading* statement, retained for the record.

For the operator's goal, everything is buildable incrementally **on the existing force-open
world** (every proven mechanism — phase, pod spawn, dismount — already ran on that same staged
`LVL_Tutorial`, so no new entry class is needed) **except two links with no currently-known
substitute**:

1. **Mount (rider-on), stage 7** — getter `0xF7EB50` is un-pokable and Func-swap-dead. A
   natural rider handoff needs an *alternate route to the live round-mode object* (which exists
   at `Comp_GameMode_DropPlane_Tutorial+0xE0` and `UWorld+0x250`), reconstructing the deleted
   server logic as a shim, or a forbidden `.text` write. **This is the make-or-break.**
2. **Plane rider + empty `Auth*`/`AddPlayerToPlane` mutators, stage 2** — the internal state
   writes are unknown; needs the same hand-reimplementation approach as S132's dismount.

Both are **research-open, not engineering-scheduled.** §6 grades whether either is beatable.

---

## 4. Honestly UNEXPLORED vs "solved-as-a-poke, never-in-sequence"

**Never targeted at all (biggest blind spots):**
- **Landing-selection predrop UI** — never rendered on any route; script cursor tick
  (`UpdateDropLocationCursor`) is dead code; native validity uncalled; commit is native Server
  RPCs. Single largest unknown in the chain.
- **Mounting a real rider into the pod** — never worked (poke or natural); `PilotPlayerState`
  null because its writers are empty stubs; the `[TeamState+0x688]` poke is dead (zero live
  `TeamOnly` instances).
- **Plane flight itself** — `AuthStart`/`UpdatePlaneMovementAndCheckDone` bodies never graded.

**Solved as a diagnostic poke, but never as part of a sequence:**
- **Pod spawn** (CDO byte poke, +2 census) — isolated, class-default, not shippable; whether
  the shipped game even uses this pooled route is unestablished (gems fail C7 too).
- **Dismount / landing placement** (S132) — 6 flown landings, always from a fabricated
  attached-rider, never after a real mount/descent.
- **Phase notification cascade** (direct `GoToPhase`) — self-drives to Combat, but the stored
  byte never advances and the drop phase never fired.

---

## 5. Dependency-ordered plan (offline-first; ~1 injection per staging due to FK-32)

**FREE / OFFLINE (do first — may foreclose the hardest wall before spending a launch):**
1. Grade the mount getter `0xF7EB50`'s replacement + hunt any live route to a round-game-mode
   object (live at `Comp_GameMode_DropPlane_Tutorial+0xE0`). *Unblocks/caps stage 7.* → **§6**
2. Grade `ServerOnly`'s test — can a KFUNCSWAP (0/16 deaths) flip the DropPlane bind to install
   itself? *Unblocks stage 1→2 natural subscription.* → **§6**
3. Grade `StartPodGameplay` + `AddPlayerToPlane`/`Auth*` mutator bodies for the state they
   write. *Unblocks stages 6, 2-rider.* → **§6**
4. Re-verify the coverage negative control (use `ULokiRespawnComponent::Respawn 0x5A6AC40`; the
   old `AuthSetDeathCircle 0x55653E0` control is now decrypted/dead). → **§6**

**STAGED-FLIGHT (one injection each; budget on armed windows, ~2 of 4 launches):**
5. Direct-call the DropPlane phase handler (S55 primitive, byte arg 6) on the live
   `Comp_GameMode_DropPlane_Tutorial`; watch whether `SpawnPlane` runs — separates
   "not subscribed" from "subscribed but inert" (`fk22:1265-1274`).
6. Fly the built-never-flown Route D `dropmarkers` arm (poke markers resident / BR procedural
   variant), call `SpawnPlane`, check for no fault + non-null `SetDropPlane`.
7. Direct-dispatch `StartPodGameplay()` on an S131-initialized live pod; read
   `bHasStartedGameplay`/`DropPodState`/`bSteeringEnabled` (does the `LokiIsServer` gate bypass
   like `GoToPhase` did?).
8. First-ever selection-UI attempt — after phase + `SpawnPlane`, watch for
   `OnSelectDropLocationStarted` / `bCanSelectDropLocation` and `WBP_UI_PredropScreen` entering
   viewport.
9. Fly `play-atlanding-walk` (`KFLYMODE=1`, `.text 944a27728053359e`) on a freshly-dismounted
   hero vs a never-dismounted sky control — settles stage 10 walkability.

*Steps 1–4 gate 5–9: step 1 may foreclose the mount path entirely.*

---

## 6. OFFLINE GRADING RESULTS (2026-08-31, run `wf_fceb4c45-068`; 4 lanes + 2 adversarial verifiers)

Zero launches. Every lane calibrated its grader on the 5 ICF folds byte-exact
(`0xF7EB50=33c0c3`, `0xF7EC20=c20000` **VOID**, `0xF7EB60=32c0c3`, `0xB9E1F0=b001c3`,
`0xFC6CF0=0f57c0c3`) against a known-real control, recomputed every rel32 by machine, and
page-checked coverage so DARK was never read as absent.

### 6.1 GO / NO-GO — **GO, conditional on one staged flight; no `.text` write required.**

The load-bearing sub-verdict on the mount (L1, **V1 CONFIRMED**):

- `AuthPlayerEnterWorldAttachedToRidable` (`0x55CD510`) **cannot run to completion without a
  `.text` write** — its round-game-mode getter `call 0x0F7EB50` (`@0x55CD572`, the `33 c0 c3`
  null fold) feeds two bails: `test rax,rax; je` (`@0x55CD57A`) and `IsA<ALokiRoundGameMode>; je`
  (`@0x55CD583`). That door is shut. **[M]**
- **But the mount never needed it.** The getter is a **pure precondition** — its result is never
  read on the success body `0x55CD590..0x55CD793`, which uses only `rdi`=PlayerState /
  `rbx`=SpawnLocation / `rsi`=GetLokiCharacter. **[M, V1-confirmed]** The success body's only
  component-state write is one `PlayersAttached` append (`Data@+0x130 / Num@+0x138`, via
  `ResizeGrow 0xF988D0 @0x55CD75B`) — **the exact append S132 flew** — plus real, decrypted
  positioning callees (`SpawnAndMoveLokiCharacter_MoveStep 0x55C1B20`,
  `SetActorEnableCollision 0x339A550`, `GetLokiCharacter 0x56BE0D0`, `IsA 0x54F8DC0`).
- ⇒ **mount is reachable by S132-style direct replication of the success writes** (data-poke
  append + direct native positioning), never by calling the gated function — same risk class as
  the flown dismount.
- **The one genuine gap [I, unflown]:** whether the poke-attached, positioned rider **tracks the
  flying pod**. The success body positions once, shows no visible `AttachToComponent`/parenting,
  and the only attach-capable callee `LokiTeleportActor 0x56680F0` is **DARK/unread**. One staged
  measurement (hero X vs pod X during flight) decides it.

### 6.2 Per-wall grades

| Wall | Verdict | Grade | Offline route |
|---|---|---|---|
| Mount getter (`0x55CD510`; getter `0x0F7EB50`) | gate unbeatable by poke; **mount beatable by replicating success writes** — needs 1 staged test | [M] gate+precondition; [I] the ride | poke-append `PlayersAttached` (`+0x130/+0x138/+0x13C` via `ResizeGrow 0xF988D0`) + direct positioning (`0x55C1B20`, `0x339A550`). **Do NOT** call the reflected fn (bails), poke `+0xC0` (discarded getter `this`), Func-swap thunk `0x5456380` (0 callers), or use `AuthPlayerEnterWorldNew` (empty impl) |
| ServerOnly / DropPlane react-to-phase (`ServerOnly` impl `0x1311870 = c6 02 00 c3`) | **BEATABLE_OFFLINE** | [M] mechanism+route; [I] gate dispatch opcode | direct-call the reflected BP UFunction `OnRoundPhaseChanged(byte 6)` via **ProcessEvent slot 78 / disp 0x270** (or `CallBPGuarded`) — no ServerOnly rewrite. ⚠ **neither this nor a Func-swap makes the plane DEPLOY** — deploy terminates at FK-1 stripped `Auth` stubs; this drives the FLIGHT/UX half only |
| StartPodGameplay / descent | **BEATABLE_NEEDS_STAGED_TEST** — descent self-drives from one call | [M] body behaviour (AS source); **[I, strong]** that ProcessEvent reaches the AS VM body and self-drives (V3 downgrade) | ProcessEvent (slot 78) `StartPodGameplay` on a live pod — **not** the S55 direct thunk (AS `Func@+0xE0 == 0`). Mover `Deactivate` unconditional; `SetDropPodState`'s `if(LokiIsClient) return` forecloses only the replicated `PodStateEvent` broadcast; `StartPodMovement 0x1702` runs above the gate, toward `CurrPodDestination` (S131 `InitializeDropPod`) |
| AddPlayerToPlane vs AddPlayerToDropPlane | `ALokiDropPlane::AddPlayerToPlane` = **empty stub**; `ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` = **REAL** (`thunk 0x5350630 → impl 0x55CBB60`) but routes terminal handoff into the empty stub | [M] two distinct fns; [I] the routing | shim substitute: plane membership via `DropPlane->RideableComponent` (`ULokiRideableComponent`, same class as pod) `PlayersInside +0x120` / `PlayersAttached +0x130` — S132 recipe |
| Coverage control `ULokiRespawnComponent::Respawn 0x5A6AC40` | **DARK (0/4096) — valid never-executed control in merged14** | [M] | page `0x5a6a000` all zero, dark band `0x5a66000–0x5a6b000`, nearest lit `0x5a6c000` (2 pages away). Old control `AuthSetDeathCircle 0x55653E0` is now **LIT (3782/4096)** — disqualified |

### 6.3 Revised cheapest path (offline-first; ~1 injection per staging)

**Free OFFLINE pre-flight (moves grades before spending a launch):**
- Decrypt + read `LokiTeleportActor 0x56680F0` (the only attach-capable callee; DARK) → is the
  ride a real attach or a one-time position? Confirm the `SetActorLocation` substitute.
- Disassemble the DropPlane `ExecuteUbergraph` gate node → confirm dispatch opcode → moves the
  ServerOnly Func-swap grade [I]→[M] (the ProcessEvent route needs no such fix regardless).
- Transcribe `AddPlayerToDropPlane 0x55CBB60` full extent → confirm membership-itself vs
  routes-into-the-empty-stub [I]→[M].
- Transcribe `SpawnAndMoveLokiCharacter_MoveStep 0x55C1B20` null-guards before calling on any
  non-Ronin hero (S132 flagged a related crash hazard at `0x5586530`).

**STAGED-FLIGHT (each one injection):**
- **A — flight & selection:** reach `EGP_Lineup(6)` (S124 self-drives), then ProcessEvent
  `OnRoundPhaseChanged(6)` on the live DropPlane component → flight/UX half.
- **B — pod descent:** ProcessEvent `StartPodGameplay` (slot 78) on a live pod → self-drives
  `Deactivate → IntroSequence → StartPodMovement` toward `CurrPodDestination`.
- **C-primary — real mount (the decisive test):** RM_MOUNT arm — poke-append the hero
  `ALokiPlayerState` to `pod->RideableComponent->PlayersAttached` (mirror S132; **do NOT poke
  `PlayersInside +0x120`** — the S132 ordering trap silently no-ops the wall), drive
  `SpawnAndMoveLokiCharacter_MoveStep` with a pod-seat transform, then **read whether the hero X
  tracks pod X during flight.** That single read decides real-ride vs fallback.
- **C-fallback — cinematic drop, poked landing (all proven parts):** if the rider doesn't track,
  fly the pod empty, then place the hero at a landing actor via the flown
  `AuthPlayerDetachPlayerFromRidable 0x55CCCB0` (S132) → hero on real terrain, `play`-movable.
- **D — receipts (pre-register):** append `PlayersAttached.Num 0→1`; descent = mover velocity
  toward `CurrPodDestination` + Z-trajectory; ride = hero X tracks pod X; placement = hero at
  landing actor then `play` walks it.

**Confirmed DEAD offline (do not spend a flight):** calling the reflected mount (`0x55CD510`,
bails internally); poking `[component+0xC0]` (discarded getter `this`); Func-swap of getter
thunk `0x5456380` (0 callers); `AuthPlayerEnterWorldNew` (empty impl); `AuthPlayerPreSpawnOn
AddToPlane 0x55CD800` (getter result IS a data dependency there — `mov rsi,rax → call [r9+0xa48]`
`@0x55CD8E9`); `AuthPlayerEnterWorld 0x55CCE70` (upstream `PlayersInside`-membership blocker; flew
in S131, hero did not move).

### 6.4 Corrections banked (do-not-regress)

- **The S55 direct-thunk primitive does NOT apply to `OnRoundPhaseChanged` or `StartPodGameplay`**
  — they are BP-bytecode / Angelscript UFunctions (`Func@+0xE0 == 0` for AS; BP `Func` is the VM
  entry). Route them via **ProcessEvent (disp 0x270 = slot 78)** or `CallBPGuarded`, never the
  direct native thunk.
- **DARK ≠ absent/stub, and it is image-relative.** `LokiTeleportActor 0x56680F0` (page zero) is
  DARK, not a fold. `Respawn 0x5A6AC40` is a valid control **only in merged14** — coverage is
  monotone-increasing and its neighbour `0x5a6c000` is already lit; re-verify per image and state
  which image (the S137 side-decryption that lit the old control `0x55653E0` is exactly this trap).
- **Thunk/impl label fix (V1):** `AuthPlayerEnterWorldNew`'s `0x5456460` is the exec **thunk**
  (real code); its *impl* is the empty fold `0x0F7EC20`. Conclusion unaffected (it is a dead
  alternate entry); cite `0x5456460` as the thunk, never next to the fold bytes.
- **[I, strong] not [M] (V3):** "pod descent is drivable by one ProcessEvent call" — the AS body
  behaviour is [M]; that ProcessEvent reaches the AS VM body and self-drives is untested.
- **Every route here is a diagnosis, not a shipping fix** — it pokes live component TArrays and
  drives authority-only entries. The ServerOnly-react and pod-descent routes are `.text`-free but
  **neither deploys a rider through the game's own code** (deploy terminates at FK-1 stubs). Do
  not add to the default shim set.

---

### 6.5 Offline pre-flight → RM_MOUNT arm spec (2026-09-01, run `wf_4ed06004-b9a`; 4 lanes + 2 verifiers)

**Updated grades:**
- **Ride-tracking — RESOLVED_M (settled offline):** a poke-appended `PlayersAttached` rider does
  **NOT** track the flying pod. `PlayersAttached` is referenced by ZERO AS code except
  `KickPlayersFromPod`'s `.Contains` (client-early-returns); `UpdateCharacterLocations` moves only
  the pilot + `AttachedCrewPods` (gated `DropPodState==4`); `UpdateDropPhaseHiddenActors` iterates
  `PlayersInside(+0x120)`, not `+0x130`; the mount body does no `AttachToComponent` and is
  unreachable (null-fold bail `@0x55CD57A`). ⇒ **a real pod ride needs the arm to attach the hero
  itself.** ⚠ Residual: a non-reflected native `TickComponent` iterating `[rideable+0x130]` was
  not excluded by a full `.text` scan, so "nothing repositions riders" (unqualified) is [I,strong];
  the operative "a poke rider does not co-move" is [M].
- **Phase-A DropPlane react — RESOLVED_M:** `ProcessEvent` the component's own **`OnRoundPhaseChanged`
  (no spaces)**, 1-byte arg `6` (`EGP_Lineup`), on the live `Comp_GameMode_DropPlane_Tutorial_C`,
  via vtable **disp 0x270 / slot 78**. Reaches native `AddPlayerToDropPlane`. No ServerOnly fix
  needed (gate is on the subscription path, bypassed by the direct call). ⚠ Two handlers: no-spaces
  → ubergraph 1403 (drop reaction); spaces → ubergraph 545 (`GoToPhase` ladder). Resolve by
  ubergraph entry, not name.
- **`AddPlayerToDropPlane 0x55CBB60` — RESOLVED_M:** REAL 330-byte self-contained fn; does **not**
  route to the empty `AddPlayerToPlane` stub; plane `ULokiRideableComponent @ ALokiDropPlane+0x3c8`.
  Optional route (not on the minimum path). ⚠ plane-side `PlayersAttached@+0x130` is same-class
  inference [I,strong] (only `PlayersInside@+0x120` directly observed on the plane).
- **`MoveStep 0x55C1B20` — RESOLVED_M:** `void __fastcall(rcx=ALokiCharacter*, rdx=const FVector*)`,
  a finite-checked `AActor::SetActorLocation 0x339A7A0` wrapper. **Raw native (NOT reflected)** —
  S55 primitive does not apply; cast a plain fn pointer. **Hero-agnostic** — touches none of the
  S132 hazard offsets (`+0x460/+0x1978/+0x1980` live in a *different* mount callee `0x5586530`).
- **Phase-B `StartPodGameplay` — STILL_UNKNOWN:** call target/disp/args not resolved this pass.
  S131 recorded only that it never runs (`LokiIsServer` false) and its first act is
  `ProjectileMovement.Deactivate()`. Either derive offline next, or accept UNKNOWN into the flight.
- **`LokiTeleportActor 0x56680F0` — NEEDS_STAGED_DECRYPT (non-blocking):** DARK in all 74 on-disk
  images (page `0x5668000` = 0/4096). Only characterizes the game's own (unreachable) mount; a
  self-attaching arm never calls it. Carry a `dumpimage` on any flight to decrypt it.

**RM_MOUNT arm spec (address-level; risk class DATA + direct native call; no `.text` write):**
1. Resolve `pod->LokiRideable` **by name** (BP-generated `@pod+0x6C8`). Arrays on it:
   `PlayersInside` Data `+0x120` / Num `+0x128` / Max `+0x12C`; `PlayersAttached` Data `+0x130` /
   Num `+0x138` / Max `+0x13C` (inner = ObjectProperty, 8-byte elems).
2. **Append** the hero `ALokiPlayerState*` to `PlayersAttached`: read Num/Max; grow via game realloc
   **`ResizeGrow 0xF988D0`** (raw native) if needed; store at `Data[Num]`; `Num += 1`.
   ⚠⚠ **Do NOT poke `PlayersInside(+0x120)` first** — makes `ContainsPlayer` true, silently no-ops
   the wall and destroys receipts (S131/S132 ordering trap).
3. **Position + co-move (the game can't):** un-hide (`SetPredropHidden(false) 0x5599040`), bracket
   with `SetActorEnableCollision 0x339A550` off→on, then EITHER
   (P-attach) `AttachToComponent(hero, pod->RootComponent @pod+0x1B0, KeepRelativeTransform)` once,
   OR (P-poll) each frame `MoveStep(hero, &seat)` / `SetActorLocation` to `GetRidePosition 0x55DAB50`
   (pod root world loc; add a manual seat offset to avoid capsule interpenetration).
   `MoveStep` guards: rdx must be a valid readable **24-byte 3×f64**, all finite (NaN → logs + no
   move), and `hero+0x1B0` RootComponent non-null.
4. **Phase-A (flight/UX):** `ProcessEvent OnRoundPhaseChanged(byte 6)` as above.

**Pre-registered receipts:** R1 `PlayersAttached.Num 0→1` + `Data[0]`==poked PS · R2 pod
`ComponentVelocity` toward `CurrPodDestination` · R3 (decisive) hero X tracks pod X **only with an
arm-driven attach** (poke-only ⇒ frozen, confirming the offline verdict; poke-only tracking ⇒
reopen the ride grade) · R4 placement at the seat/landing FVector · R5 Phase-A effect on the
component plane handle.

**Corrections banked (do-not-regress):**
- ✗ **DELETE "`GetRidePosition 0x55DAB50` has zero callers"** — FALSE (two real callers
  `0x569F452`, `0x56A337C` + thunk `0x54570e9`). The correct claim is "nothing repositions
  **`PlayersAttached`** riders," not "nothing repositions riders." (Instrument artifact: rel32-scan
  silence recorded as fact.)
- **`strxref` extents are per-`.pdata`-row, not function size** — `AddPlayerToDropPlane` 81→330,
  `MoveStep` 120→495, `GoToPhase` 0x271→0x2C0. Diff by disasm to the single `ret` for
  chained-unwind (shrink-wrapped) functions.
- **Three call routes, pick right or it reads as a dead function:** `MoveStep`/`ResizeGrow` = raw
  native (plain fn ptr); `AddPlayerToDropPlane` = S55 real exec-thunk; `OnRoundPhaseChanged` /
  `StartPodGameplay` = BP/AS bytecode → ProcessEvent slot 78.
- **S132 hero hazard (`+0x460/+0x1978/+0x1980`) is in callee `0x5586530`, not in `MoveStep`** —
  `MoveStep` alone is hero-safe; a full mount-body replay is not.

**ARM BUILT (2026-09-01) — `RM_MOUNT` (enum 33), source arm `DoMount` in `tools/sigbypass-mod/tutorial_launch.cpp`.**
One source arm, KMTARMS-bit-gated, reusing the proven S132 `RdResolve`/`DxAppend`. Risk class DATA +
CALL-ONLY; KERNEL32-only imports. `.text` RAW digests (diff the HASH, never the size):

| variant | KMTARMS | `.text` RAW | role |
|---|---|---|---|
| `mount` | `0x00` | `51252a69afcf39a1` | recon only (resolve pod/comp/PS/hero, read arrays, no writes) |
| `mount-append` | `0x01` | `eb254544fd35248e` | `PlayersAttached` append only |
| `mount-noride` | `0x07` | `9b298565ac45d1ca` | append+unhide+position, **NO poll → poke-only CONTROL (frozen rider)** |
| `mount-ride` | `0x0F` | `3f2ca00cab62a3b6` | append+unhide+position+**POLL → the RIDE TREATMENT** |
| `mount-descend` | `0x1F` | `b6941b5929723a96` | ride + `StartPodGameplay` (descent) |
| `mount-phaseb` | `0x10` | `c144ccf255b2cc0b` | `StartPodGameplay` only (descent test, no mount) |

✅ Regression gates **byte-identical** after the edit: `botai 5e47c13cf7f0a158`, `play 9bc10a4552c596e1`
(the arm dead-strips out of every other variant). ✅ `text_digest.py --dupes` clean — `mount-ride` ≠
`mount-noride`, no A/B-against-a-copy hazard. **Staging (all offline until the flight):**
`gft → fo → sp → droppod-pe-cdopoke` (spawn+init a flying pod) → the mount variant. **Decisive receipt
R3 is external RPM:** `mount-ride` must show hero X track pod X; `mount-noride` must show a frozen rider.
⚠ Phase-B live descent is `[I,strong]`/NEEDS_STAGED_TEST (velocity is ~0 immediately; descent is
timer-deferred ~6.5s). ⚠ Diagnosis, not a shipping fix — do not add to the default shim set.

**PHASE-A arm (flight/UX half) — no new mode; `RM_DROPPLANE` already had it.** New clean variant
`dropplane-react` (`KDPARMS=0x35` = B0 + **B3a `OnRoundPhaseChanged` (no spaces)** + B4 census +
B0c control), `.text` RAW `cab0bff3ece90318` (distinct from `dropplane-handler f88918f0…` which
confounds it by also running the spaces-variant B3b). Calls `OnRoundPhaseChanged(NewPhase=6=Lineup)`
on the live DropPlane component via ProcessEvent — the drop reaction (ubergraph 1403), NOT the
`GoToPhase` ladder (spaces-variant, ubergraph 545). Sibling `dropplane-b1only` still reproduces its
recorded gate `5b4467b0105dec1a` (the existing dropplane arms are untouched).

**External flight reader — `tools/re/drop_ride_readout.py`** (read-only RPM, no injection). Start it
BEFORE the injection (motion_watch lesson: the window can be seconds and FK-32 can kill the client
right after). It auto-discovers the pod (`BP_DropPod*`) + hero (`BP_HERO_*`; pass `--pod`/`--hero`
from the arm's `[RD]` markers to disambiguate), tight-samples `pod loc / hero loc / |hero-pod|xy /
pod vel / bHasStartedGameplay / DropPodState / PlayersAttached.Num`, and computes the pre-registered
receipts from the OBSERVED samples: **R1** append landed, **R3** hero tracks pod (treatment) vs
frozen (control), **PB** StartPodGameplay ran. Offsets match `pod_live_read.py`/`motion_watch.py`.

---

## 7. Do-not-regress (stale / contradicted claims banked)

- ❌ *"Drop-in/DropPlane FALSIFIED as reachable — SpawnPlane faults on absent markers"*
  (`coverage-audit-s101.md:269`). **REFUTED** — markers exist in `LVL_Tutorial`, just not
  streamed in; S93's fault was an SEH catch through an uninitialised `FFrame.FlowStack`
  (`fk22:25-32,1333-1346`).
- ❌ *"The round-phase machine never leaves BeginInit(1)."* **SHARPENED** — 193/193 measures
  `GoToPhase`'s *argument*; a direct call self-drives to Combat; the byte never lands because
  the setter is a stripped fold (`fk22:432,498-513`).
- ❌ *"GameState from `[GameMode+0x258]`."* **REFUTED LIVE** — GameState is at `GameMode+0x418`;
  `+0x258` is not a UObject (`fk22:1145-1151`).
- ❌ *"The actor pool is FK-22's wall / pool-disabled returns NULL."* **REFUTED** — cause is C7
  `bCanEverReplicate` (`s130 §3,§13.4`).
- ❌ *"Expect a PARTIAL dismount."* **SUPERSEDED** — dismount fully runs; the 2× `0xF7EC20`
  folds are void side-effects whose returns are never tested (`s131 §14.1`; `s132`).
- ❌ *"`ContainsPlayer` is the attach receipt."* **WRONG ARRAY** — it reads
  `PlayersInside(+0x120)`, not `PlayersAttached(+0x130)` (`s131 §10.2`).
- ❌ *"The dismounted hero is playable at the landing point."* **RETRACTED** — RM_PLAY teleports
  it off the landing point first; `play-atlanding` hovers in `MOVE_Flying` (`s132:376-421`).
- ❌ *"`[mv+0x1A0]=1.0f` is a movement restore."* **CORRECTED** — it is `GravityScale=1.0`
  (`CMC+0x1A0`); the dismount performs no velocity write (`s132:89-94`, audit-S142).
- ❌ *"The hero is playable/movable" = real WASD.* **DO NOT** read it that way — it is a
  velocity-poke puppet; the stock `AddMovementInput` chain is dead for the player
  (`coop-vs-ai-roadmap-s142.md:60`).
- ⚠ *"ULokiRideableComponent+0xE0 caches the round game mode."* **REFUTED** — there `+0xE0` is
  `OnPlayersInsideCountChanged`; the cache is `Comp_GameMode_DropPlane_Tutorial+0xE0`
  (`s131 §13`).
- ⚠ `0xF7EC20` shorthand *"ret 0"* misleads — it is `ret imm16 0` = **VOID**, does NOT zero
  `eax` (`s132:471-474`).
- ⚠ DropPlane subscription live status is **as of S124/S125**; S134 is offline re-grade only.

---

## 8. Relationship to the existing roadmap

`docs/coop-vs-ai-roadmap-s142.md` remains the authority for the **minimum bot-fight loop**
(player casts → damages → kills a bot), which deliberately uses force-open + `sp` placement and
lists the drop sequence as OUT of scope. This doc tracks the **superset** target (the real
deploy sequence). The two share the same force-open `LVL_Tutorial` substrate and the same root
cause (§1), so work here does not invalidate the roadmap — it extends it toward the full round
lifecycle the roadmap deferred to §7.
