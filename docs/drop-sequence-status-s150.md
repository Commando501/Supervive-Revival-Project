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

### 6.7 Mount-flight ARMED-WINDOW 1 (2026-09-01, 6 injections into ONE client, ~13 min uptime, survived)

**First staged attempt at the RM_MOUNT ride A/B. Result: the arm's safety design works; the staging
recipe does NOT produce a mountable pod on this world state; SpawnPlane still faults where fk22
thought it wouldn't. R3 (the decisive ride receipt) NOT MEASURED — no qualifying pod ever existed.**
Dump preserved at `dumps/s150-mount-flight-1/`; final marker at `docs/mount-flight-1-final-marker.txt`.

**Sequence flown** (evidence-gated + injection-gaps): staging `gft → fo → sp` clean; injection 4
`droppod-pe-cdopoke`; injection 5 `mount_ride`; injection 6 `dropplane-b1only`.

**Observed:**
- ✅ **Staging clean:** `[SP] done step=4 spawnedPawn=0x229E822D560 cls=BP_HERO_Ronin_C`; hero spawned
  + possessed in `LVL_Tutorial`.
- ⚠ **The staged world holds 2 pre-existing `DropPod` actors + 3 `DropPlane` actors + 0 `DropShip`**
  (droppod's BEFORE census, archetypes excluded). Nothing about "start from a fresh world" was true here.
- ⚠ **`droppod-pe-cdopoke` SITTING VOID [M]:** `ship=0x0 TeamDropPodClass=0x0` — the ship-picker
  found nothing, so both Route C and Route E refused. No new pod created.
- ✅ **`RM_MOUNT`'s safety design WORKS [M]:** `RdResolve` reported **"0 pod actor(s), 2 live
  ALokiPlayerState(s)"** and **"NO POD QUALIFIES: none has both PodTeamIndex==0 and a non-null
  LokiRideable. REFUSING to guess."** g_mtSetup=-1, nothing written, nothing called. The DATA-write
  arm is provably risk-controlled.
  ⚠ Note the population disagreement: droppod's census sees 2 DropPod actors; RdResolve sees 0. Same
  `DpClassVerdict` code, so the 2 the droppod arm counted have some non-actor property RdResolve
  additionally filters (likely bit for `DPV_ACTOR` — investigate offline before the next flight).
- ⚠ **`dropplane-b1only` — the S93 SpawnPlane fault REPRODUCED [M]:** B0c control (`GetAutoDropLocation`)
  PASSED cleanly (⇒ the FFrame primitive fix works, S93's confound is eliminated), then **B1
  `SpawnPlane` FAULTED**: `0xC0000005 READ addr=0x0 rip=0x7FF6B6DB95DD rva=0x13495DD`, with RCX
  naming the marker class **`PlaneCenteredLocation`**. SEH captured; game survived. ⇒ SpawnPlane's
  fault is NOT a marker-existence issue as fk22 argued — the marker class is visibly named at the
  fault RIP. Real cause is downstream of the marker lookup; needs re-RE against the fresh dump.
- ✅ **Game survived all 6 injections + 1 caught fault**, well past the FK-32 mode of 4 — a lucky
  window. Do NOT read this as "6 injections are safe" — the corpus median is 4.

**What this doesn't answer:** R3 (does a poke-appended rider co-move a flying pod). The world had no
mountable pod ⇒ the RM_MOUNT arm's setup never proceeded past resolve ⇒ nothing was written to
`PlayersAttached`, nothing was moved. That test is **still open**.

**What the next flight must fix (do OFFLINE first, before any launch):**
1. Investigate the RdResolve/droppod-census population disagreement (2 vs 0 pods) — one instrument
   is filtering more than the other. Cheap offline diff of the two class-verdict paths.
2. Investigate SpawnPlane's real fault at rva `0x13495DD`. The fresh dump `dumps/s150-mount-flight-1/`
   captures the just-executed page — read the fault site (`rip-24` bytes `8B C8 48 8B 08 48 83 C0 08
   48 89 42 20 …`) and trace what `PlaneCenteredLocation` context is being deref'd null.
3. Determine whether **`SpawnDropPodForTeam` can be reached WITHOUT a DropShip on this world** (e.g.
   pass a manufactured `FDropPodParams` directly, S131 route). If yes → we skip the plane chain
   entirely and rely on the existing 2 DropPod actors, initializing one of them ourselves to satisfy
   RdResolve.
4. Only then attempt a second flight with: `gft → fo → sp` (staging), then a REFINED arm that either
   fixes SpawnPlane or bypasses the plane entirely to produce a `PodTeamIndex==0` pod.

**⚠ Corrections banked:** the S131 recipe `gft → fo → sp → dropplane_b1only → droppod-pe-cdopoke →
rideable` DID NOT WORK on this world state (SpawnPlane faulted). Either (a) the world state has
changed since S131 was recorded and the recipe is now stale, or (b) there is a precondition S131 met
implicitly that this flight didn't. Do NOT re-fly the S131 recipe without diagnosing why B1 faulted.

### 6.8 RdResolve population disagreement — DIAGNOSED [M] + census fix + probe (2026-09-01, offline)

**Finding [M, verified]:** the discriminator is **`DPV_ACTOR`**. The census counter that prints
`DropPod=%ld` (`tutorial_launch.cpp:6891` before the fix) gated on `(v & DPV_POD)` alone — a
**substring** test on the derivation chain. `RdResolve`'s pod-selection gate (`tutorial_launch.cpp:13649`)
correctly gates on `(v & DPV_POD) && (v & DPV_ACTOR)`. The 2 pre-existing "DropPod" objects the census
counted are non-Actor UObjects whose class name contains "DropPod" — likely `ABP_DropPod_*_C`
(UAnimInstance), `WBP_UI_DropPod*` (UUserWidget), or `Comp_*DropPod*` (UActorComponent). `DPV_ACTOR`
tests exact `strcmp(n,"Actor")==0` (UHT strips the `A`), so only class chains that terminate through
AActor qualify.

**⚠⚠ This DOES NOT UNBLOCK RM_MOUNT.** `RdResolve` was right to refuse; there really is no pod
ACTOR in the staged world. Loosening its gate to match the census would be a heap-corruption
primitive (RM_MOUNT writes to `LokiRideable+0x130` on the resolved object — feeding a non-Actor
UObject there is UB). The fix is **metric-only**: the census printout now means what its label
implies. Flight 2 still needs a real pod-actor route (SpawnPlane fix, or `SpawnDropPodForTeam` bypass).

**Applied [M]:**
- `tutorial_launch.cpp:6734` — `DpCounts` grew `planeSubstr, podSubstr, shipSubstr` fields.
- `tutorial_launch.cpp:~6890-6900` — plane/pod/ship counters now conjoin `(v & DPV_ACTOR)`; the
  substring buckets track the pre-fix behaviour.
- `tutorial_launch.cpp:~6923` — summary prints `DropPlane(actor)=%ld DropPod(actor)=%ld
  DropShip(actor)=%ld`; a second line prints the substring/actor mismatch if it exists.
- `tutorial_launch.cpp:~13650` — **RdResolve probe:** on any `(v & DPV_POD) && !(v & DPV_ACTOR)` hit,
  print `[RD] non-actor DropPod hit obj=… '…' cls=… chain=…` (capped at 32 lines/run). `continue`
  after — zero downstream contamination. Ground truth on the 2 mystery objects arrives in one armed
  window with zero additional writes.

**Regression digests after the fix** (diff the HASH, never the size):
- ✅ `botai 5e47c13cf7f0a158` UNCHANGED (mount/census dead-strip clean).
- ✅ `play 9bc10a4552c596e1` UNCHANGED.
- ⚠ **`dropplane_b1only 5b4467b0105dec1a → dcb19157cf45f9aa`** MOVED. The diagnosis's "b1only's build
  flags don't compile the changed lines" was wrong: `DpCensus` is called by `RM_DROPPLANE` too, so
  the counter-line edits compile into b1only. **The move is metric-only** — the arm now prints
  honest `DropPlane(actor)=N` + a substring bucket; behaviour is preserved. **The CLAUDE.md line
  citing `5b4467b0105dec1a` as b1only's regression gate is now invalidated; the new gate is
  `dcb19157cf45f9aa`.**
- ✅ DROPPOD family moved as predicted: `droppod-pe-cdopoke bc1c1a5b1e66b54a → 283c1692a2135680`,
  `droppod-pe-cdoctrl 61fd0745c23e89f0 → f90890fabda0d3cb`, `poolspawn-cdopoke efe8db553bf511ba →
  564e9b86f5f89b65`, `poolspawn-cdoctrl 85f3cee44c31b1cd → ca4a82fc8c1754cd`.
- ✅ Mount digests moved (from the RdResolve probe addition): `mount-ride 3f2ca00cab62a3b6 →
  9b7f88af3210c438`, `mount-noride 9b298565ac45d1ca → 224654eaea08319d`. `--dupes` still clean
  (mount-ride ≠ mount-noride).

### 6.9 SpawnPlane FAULT — the "game bug" was OURS the whole time [M] (2026-09-01, offline; 2 lanes + verifier)

**★★★★★ PIVOTAL FINDING — the S93 SpawnPlane "fault" is a shim-primitive defect, not a game bug.
`rva 0x13495DD` was MIS-LABELED for months as `GetAllActorsWithTag`; it is really stock UE
`execLocalOutVariable` (`GNatives[0x9C]`, 75 B extent `0x13495C0..0x134960A`, dispatch via
`GNatives[0x9C]`, not covered by `.pdata`). The fault RIP is inside `mov rax,[rdx+0x80]` (load
`FFrame.OutParms` head) → `cmp [rax],rcx` (walk the `FOutParmRec` linked list) — RAX=0 because our
`CallBPGuarded` primitive memcpys a captured `FFrame` from a `ProcessInternal` hook and leaves
`FFrame+0x80` uninitialised. Same defect class as the recorded S128 `FlowStack/PreviousFrame`
issue at `FFrame+0x48..+0x78`, extended to a THIRD offset (`+0x80 OutParms`).**

**Which BP statement:** SpawnPlane statement **[10]** `EX_Let PlaneCenteredLocation =
CallFunc_K2_GetActorLocation_ReturnValue_2` — an OUT-parameter assignment, per
`bpdump_SpawnPlane.txt` statement index 269. Statements [6]..[9] (`GetAllActorsWithTag('TrainingStart')`
+ `Array_Get + K2_GetActorLocation`) MUST have executed to reach [10] — so **fk22:245-247's
"markers that don't exist outside the real deploy" is REFUTED [M]**: the tags DO exist, the
markers DID resolve, the fault sits inside a 75-byte VM opcode handler containing zero actor
iteration. **The `KFRAMEINIT=1` fix in fk22 (zeroes `0x48..0x78`) is real but incomplete** —
missed the `+0x80` sibling.

**Corrections landed:**
- `tools/strxref/index/symbols.json:5679-5698` — mis-label `GetAllActorsWithTag` → correct
  `execLocalOutVariable_equiv (GNatives[0x9C])`; sample_context rewritten with the S150-drop [M].
- Note (not yet applied to fk22.md itself): the "third step" prescription at fk22:245-247 was
  what our flight ran, and it doesn't include `+0x80` — extend that block when convenient.

**Grades:**
- `[M]` fault-function identity + 75-byte extent + `GNatives[0x9C]` dispatch (single stored
  pointer image-wide at `rva 0x9E374E0`).
- `[M]` root cause is the primitive's uninitialised `FFrame.OutParms`; SpawnPlane carries
  `FUNC_HasOutParms`; B0c `GetAutoDropLocation` (no OUT params) passes cleanly on the exact same
  primitive — the pattern predicts every `FUNC_HasOutParms` UFunction faults this way.
- `[I]` PlaneCenteredLocation is specifically the `CPF_OutParm` parameter (closable [M] with a
  5-min RPM sitting reading `FField.Name @+0x20` + `FProperty.PropertyFlags` over SpawnPlane's
  26 Children).

**Flight-2 route decision: BYPASS via `SpawnDropPodForTeam` DIRECT, not "fix SpawnPlane".**
- The acceptance predicate is a pod ACTOR with `PodTeamIndex==0` + non-null `LokiRideable` so
  RdResolve finds it — the visual plane is polish. `SpawnPlane`'s role for RM_MOUNT is to
  eventually call `SpawnDropPodForTeam`; we skip the plane entirely.
- `ALokiDropShip::SpawnDropPodForTeam` (S131: `0x597E730`) has "two bail points, NO marker query,
  two FVector args as the only spatial input" (CLAUDE.md). The DropShip is skippable:
  `InitializeDropPod` touches `DropShip` only inside `if (bIsTeamLeaderPod)`, and
  `QueueCrewForPodSpawn` null-guards.
- ⚠ Load-bearing caveat: `SpawnDropPodForTeam` is Angelscript ⇒ `Func @+0xE0 = 0` ⇒ **the S55
  direct-thunk primitive DOES NOT WORK** on it. Route via `ProcessEvent` slot 78 (disp `0x270`).
  Alternative: direct-call `InitializeDropPod` on a fresh pod actor (S131's `RM_DROPPOD` shape),
  sidestepping needing a DropShip entirely.
- Fixing the primitive (allocate an `FOutParmRec` chain naming each `CPF_OutParm` parameter with
  caller-owned `PropAddr` storage) is the right long-term fix, but flight 1's staging path stops
  before it — pursue after we've proved the pod route works.

**Flight-2 recipe (RM_S131REPLAY_MOUNT — all-proven parts, no new native surface):**
1. `gft → fo → sp` (staging, unchanged).
2. **Replay S131's `RM_DROPPOD` shape** to get a fresh `BP_DropPod_Tutorial_C` actor.
   Predicates: post-call GUObjectArray delta = +1 for `BP_DropPod_Tutorial_C`; `RootComponent
   != NULL`; `PodTeamIndex==0`; `CurrPodDestination != (0,0,0)`; `bIsTeamLeaderPod==true`;
   `LokiRideable_GEN_VARIABLE @+0x6C8 != NULL`. S131 flew this 3× with an in-run negative control.
   ⚠ **The specific droppod variant matters:** flight 1's `droppod-pe-cdopoke` reported SITTING
   VOID (ship=0x0). S130's `poolspawn-cdopoke` (Route F, pool-acquire) is the sibling to check —
   it may not need a DropShip. Grade offline before flying.
3. **RdResolve on the fresh pod** — the probe shipped in `2060cb8` (§6.8) will identify the 2
   pre-existing non-actor "DropPod" objects (likely CDOs / DEFERRED pool templates never
   `FinishSpawningActor`'d — S131 §7 note). The fresh actor from step 2 should pass
   RdResolve's `DPV_POD && DPV_ACTOR && PodTeamIndex==0 && LokiRideable!=NULL` filter over them.
4. **Existing `mount_ride`** — unmodified.
5. Pre-registered outcomes: (α) `PlayersAttached.Num 0→1` + reader R3 shows co-move → RIDE
   confirmed. (β) WALL 5 fires (`LogLokiRideable: failed to get the round game mode`) — a
   KNOWN wall, S131 §11; separately addressable via `[TeamState+0x688]` poke, not a failure of
   this arm. (γ) something else — DO NOT interpret without a named category.

**Open questions banked:**
1. Verify `poolspawn-cdopoke` works without a DropShip on this world state (S130 grading).
2. Read `PlaneCenteredLocation`'s `CPF_OutParm` flag live to close the [I]→[M].
3. Enumerate the full opcode renumbering (only `GNatives[0x9C]` confirmed reassigned) — bpdump
   currently doesn't distinguish it from stock local-read.

### 6.10 Flight-2 staging RE (2026-09-01, offline; 2 lanes + verifier + a REAL contradiction)

**Task 1 result: my "no ship needed" hypothesis is REFUTED [M].** Verifier caught a scope error I
had banked: S131's "ship can be skipped" refers to `InitializeDropPod`'s *internal* leader-branch
DropShip use (null-guarded), NOT to `SpawnDropPodForTeam`'s *dispatch* requirement (which needs a
live ship). Flight 1 failed exactly because of this: **wrong injection order** —
`droppod-pe-cdopoke` was injected BEFORE any ship existed, then `dropplane_b1only` was injected last
(when it should have been second).

**Both alternatives refuted:**
- **`poolspawn-cdopoke` alone (Lane 1):** IS ship-free by construction and DID produce +5 pod actors
  at S130 [M] — BUT those pods never went through `InitializeDropPod`, so `PodTeamIndex=-1` (class
  default) and `RdResolve` refuses. Lane 1 proposed a 3-poke arm (`droppod-poke3`) that **does not
  exist in the shim** — labeling this "flight-2 ready" conflates a proposal with a proven step.
- **Direct `InitializeDropPod` on a fresh SpawnActor'd pod (Lane 2):** FULLY REFUTED. No
  `UFUNCTION` decorator (`ALokiDropPod` has 0 UHT rows against base = 6 for `ALokiDropPodBase`), so
  the S55 primitive is dead (no UFunction to resolve), ProcessEvent slot 78 is dead (needs a
  UFunction*), and the SpawnActor+FProperty-poke substitute carries an unmeasured FK-1
  AS-registration precondition.

**Workflow's recommended recipe (S131 original order):**
```
gft → fo → sp → dropplane_b1only → droppod-pe-cdopoke → mount_ride
```

**⚠⚠⚠ MY IMPORTANT CAVEAT — the workflow's synthesis contains an INTERNAL CONTRADICTION about this
recipe that flight 1's own evidence resolves.** The synthesis claims *"`dropplane_b1only` avoids
`SpawnPlane` by construction (base BP path, not `SpawnPlane`), which is why S125 measured it
working."* This is **FALSE**: `dropplane_b1only`'s `KDPARMS=0x33` = `0x01|0x02|0x10|0x20` = B0 +
**B1** + B4 + B0c, and **B1 IS SpawnPlane** (per `tutorial_launch.cpp:6636`). Flight 1's marker
proves it: `[DP] --- B1 (HEADLINE): SpawnPlane() on the FFrame-REPAIRED primitive` … `[DP] B1
SpawnPlane AFTER: *** FAULTED (SEH-captured) ***  rva=0x13495DD`. The synthesis's story about
S125 avoiding SpawnPlane is unsupported.

**⇒ What flight 1 actually established, honestly:**
- Yes, we should have injected `dropplane_b1only` BEFORE `droppod-pe-cdopoke` (the order error).
- BUT `dropplane_b1only` DID fault on SpawnPlane at statement [10] on our primitive — same fault
  §6.9 diagnoses. Re-flying the S131 recipe in correct order will likely re-hit the same fault.
- **CRUCIAL UNKNOWN:** does SpawnPlane's fault at statement [10] happen BEFORE or AFTER the ship
  is spawned? Statement [10] is `EX_Let PlaneCenteredLocation = ...` — late in the function. Ship
  spawning likely runs earlier. **If the ship IS created before the fault, the recipe still
  works.** We never measured this in flight 1 (no DropShip census after `dropplane_b1only`).

**⇒ TWO ROUTES for flight 2, with an honest trade:**
- **ROUTE α (fast, uncertain):** re-fly the S131 recipe in correct order. Add a DropShip census
  after `dropplane_b1only` (before injecting `droppod-pe-cdopoke`) — if `DropShip 0→1` despite
  the SpawnPlane fault, proceed; if `DropShip 0→0`, escalate to ROUTE β. Cost: 1 armed window.
- **ROUTE β (slower, robust):** fix the CallBPGuarded primitive to initialise `FFrame+0x80`
  (allocate an `FOutParmRec` chain from the UFunction's `CPF_OutParm` children). This is the
  §6.9 root-cause fix and unblocks EVERY `FUNC_HasOutParms` UFunction on this project, not just
  SpawnPlane. Cost: real engineering + a new arm build.

**⇒ Recommend ROUTE α first — it's testable in 1 flight and settles the "SpawnPlane fault
prevents ship spawn" question with the DropShip census as the discriminating receipt.** If it
succeeds, we skip ROUTE β entirely. If it fails, we've localized the problem to "the fault also
prevents ship creation" and ROUTE β becomes mandatory.

**Pre-registered receipts (write BEFORE flight 2):**
- After `dropplane_b1only`: `LokiDropShip` census delta `0→1` (RESCUE) or `0→0` (ESCALATE).
  Also check `TeamDropPodClass @ ship+0x478` — non-null = precondition for step 5.
- After `droppod-pe-cdopoke`: fresh `BP_DropPod_Tutorial_C` with `PodTeamIndex==0`,
  `CurrPodDestination` = the FVector we passed (payload fingerprint), `bIsTeamLeaderPod==1`,
  `RootComponent!=NULL`, `LokiRideable_GEN_VARIABLE @+0x6C8 != NULL`.
- After `mount_ride`: `[RD] resolve: >=1 pod actor(s)`; RdResolve prints pick >=0; the "NO POD
  QUALIFIES" refusal MUST be ABSENT. Then R1/R3/PB from the reader.
- Reader R3 (the whole point): `mount-ride` shows hero X tracking pod X; `mount-noride` (control)
  shows a frozen hero.

**Injection budget:** flight 2 needs 6 injections (`gft, fo, sp, dropplane_b1only, droppod-pe-cdopoke,
mount_ride`). Same as flight 1's actual count, so the game survived it before — but FK-32 mode is 4
and flight 1 was already at the edge. **Take `dumpimage` early, right after `sp`, so evidence
survives a mid-arm death.**

**Corrections banked from this pass:**
- My "the ship can be skipped" restatement was over-broad; scope corrected.
- The workflow's "`dropplane_b1only` avoids `SpawnPlane`" claim CONTRADICTS flight 1's own marker
  evidence; do not cite it. `dropplane_b1only` DOES call SpawnPlane (B1 bit).
- `poolspawn-cdopoke` current digest is `564e9b86f5f89b65` (§6.8), superseding CLAUDE.md's older
  `efe8db553bf511ba` reference.
- Flight 1's true root cause: **wrong injection order** (`droppod` before the ship-producing arm),
  compounded by SpawnPlane's primitive-bug fault when `dropplane_b1only` finally ran.

### 6.11 ★★★★★ MOUNT-FLIGHT 2 — HISTORIC SUCCESS: A RIDER MOUNTED A FLYING POD [M] (2026-09-01)

**★★★★★ FIRST TIME IN THIS PROJECT'S HISTORY: a hero was mounted on a flying drop pod and stayed
with it during flight — the "real drop sequence" ride works end to end.** 6 injections into ONE
client, ~7.5 min uptime, terminated cleanly. Evidence: `docs/mount-flight-2-final-marker.txt` +
`dumps/s150-mount-flight-2-{early,success}/`.

**Sequence flown (evidence-gated):**
1. `gft` → `fo` → `sp` (staging clean; `[SP] done step=4 spawnedPawn=0x26494B68020 cls=BP_HERO_Ronin_C`).
2. `dumpimage` early (§6.10 recommendation — evidence survives mid-arm death).
3. `dropplane_b1only` — **DropShip 0→1 despite SpawnPlane faulting at statement [10]** (§6.9's
   predicted fault reproduced; ship creation completes BEFORE the fault). **Route α confirmed
   [M].** New actor: `BP_DropPlane_Straight_Tutorial_C @0x264FE4BC040`, chain includes `LokiDropShip`.
4. `droppod-pe-cdopoke` — ship-picker now finds the ship; `SpawnDropPodForTeam` resolves; fresh
   `BP_DropPod_Tutorial_C @0x26408D3D850` created with **ALL RdResolve preconditions met**:
   `PodTeamIndex=0`, `CurrPodDestination=(-3206.4,5070.5,100.0)` (matches S131 payload
   fingerprint exactly), `bIsTeamLeaderPod=true`, `RootComponent` non-null, `LokiRideable`
   present. Pod flying at **20,000 uu/s** (+167,689 uu on X in 8s).
5. `drop_ride_readout.py` reader started (background, 60s window).
6. `mount_ride` — the decisive treatment.

**★★★★★ THE R3 RECEIPT [M]:**
```
[RD] resolve: 1 pod actor(s), 2 live ALokiPlayerState(s)
[RD] resolve: pod=0x26408D3D850(BP_DropPod_Tutorial_C) comp=0x26488C45C00(LokiRideableComponent)
              ps=0x264915A12C0(LokiPlayerState_HeroAffiliated)
[MT] baseline: pod=(1123346.4,5070.5,20100.0) hero=(0.0,0.0,13240.0)
[MT] APPEND OK -- R1: PlayersAttached.Num 0 -> 1
[MT] SetPredropHidden(false) ok
[MT] SetActorEnableCollision(true) ok
[MT] POSITION-ONCE: pod=(1123346.4,5070.5,20100.0) hero->(1123346.4,5070.5,20220.0) AT-POD
[MT] setup done. POLL(ride)=ON
[MT] RIDE: pod=(1199748.3,5070.5,20100.0) hero->(1199748.3,5070.5,20220.0) AT-POD
[MT] RIDE: pod=(1199998.3,5070.5,20100.0) hero->(1199998.3,5070.5,20220.0) AT-POD
[MT] RIDE: pod=(1200248.3,5070.5,20100.0) hero->(1200248.3,5070.5,20220.0) AT-POD
... (40+ consecutive samples, pod X = hero X, Z offset = 120 uu KMTSEATZ, over ~10s) ...
[MT] RIDE: pod=(1208588.1,5070.5,20100.0) hero->(1208588.1,5070.5,20220.0) AT-POD
```

**All four pre-registered receipts landed [M]:**
- **R1** `PlayersAttached.Num 0→1` ✅
- **R3** hero X TRACKS pod X across 40+ samples ✅ (with the KMTSEATZ=120 uu seat offset on Z)
- **R2** pod cruising at ~20,000 uu/s toward `CurrPodDestination` ✅
- **PB** N/A (didn't inject `mount-descend`; pod cruised horizontally at fixed Z rather than
  descending — expected since `StartPodGameplay` was not called)

**Two-instrument disagreement (correction banked):** the external `drop_ride_readout.py` reader
reported R3 as "POD DID NOT FLY (moved 0 uu)" — but that is a **reader-tool defect**, not a game
null. The reader's `discover()` uses a simple `name.startswith("BP_DropPod")` filter and picked
one of the **§6.8 non-Actor "DropPod"-substring UObjects** (HSG read as 192 = 0xC0 = stale bytes;
static hero coord `(1208975, 5070, 20220)` matches the last [MT] pod X + continuing motion, so the
reader IS reading the *real* hero correctly — it just failed to read the *real* pod). ⇒ **Fix the
reader: apply the same RdResolve gate (DPV_ACTOR + PodTeamIndex==0 + non-null RootComponent).**
The shim's own [MT] markers are trustworthy because RM_MOUNT already uses that gate.

**Corrections banked from this flight:**
- `drop_ride_readout.py` picks the wrong pod when non-Actor "DropPod"-substring UObjects exist.
  Reader needs the same class-chain + PodTeamIndex + non-null Root filter RdResolve uses.
- Route α confirmed [M]: SpawnPlane's fault (§6.9's OutParms primitive bug) does NOT prevent ship
  creation. Statement [10] is late enough that the ship spawns before the fault. Fixing the
  primitive (§6.9 ROUTE β) remains valuable but is not required for the mount path.
- `bCanEverReplicate` on the fresh pod read `true` (class default) — indicating the CDO poke in
  `droppod-pe-cdopoke` either reverted or the pod was constructed before the poke took effect.
  Non-blocking for this flight (pod was created anyway) but worth diagnosing for durability.
- Injection budget survived: 6 injections + 1 SEH-caught fault in one ~8 min window is now
  demonstrated survivable on TWO flights (flight 1 also survived 6). FK-32 mode of 4 is real but
  not deterministic.

**What this proves:**
- The FULL drop chain (world → plane → pod → mount → ride) works end to end via diagnostic pokes.
- RM_MOUNT's design (data-poke append + direct-native positioning + per-hit reposition) is
  MEASURED CORRECT — this was §6.5's [I] prediction and it is now [M].
- The offline pre-flight's core call ("a poke rider does NOT co-move" the pod — §6.5) also holds:
  without POLL, the hero would stay at the initial position and the pod would fly off. POLL is
  what makes the ride real.

**What this does NOT prove:**
- Nothing about pod DESCENT — `StartPodGameplay` was not called (would require `mount-descend`
  variant). The pod cruised horizontally at constant Z=20100, not descending.
- Nothing about the game's OWN mount path — this is a DIAGNOSTIC pokey path, not a shipping fix.
- Nothing about the acceptance predicate's ultimate goal ("playable hero on real terrain via a
  driven drop") — that needs the descent path + landing + dismount + play. Each is a separate
  step from here.

**Next possible steps (offline, no launch needed):**
1. ~~Fix `drop_ride_readout.py` to use the RdResolve filter.~~ **DONE 2026-09-01** (commit `7f9e96b`).
2. Design a `mount-descend` flight to test descent (StartPodGameplay via ProcessEvent slot 78).
   **DONE 2026-09-01 — see §6.12 below.**
3. Chain toward the acceptance predicate: `mount-descend → dismount@landing (S132 existing) → play`.
4. Fix the CallBPGuarded primitive's `FFrame+0x80` OutParms miss (§6.9 ROUTE β) — unblocks every
   `FUNC_HasOutParms` UFunction in the project, not just SpawnPlane. Long-term win.

### 6.12 MOUNT-DESCEND flight design (2026-09-01, offline; ready to fly)

**Goal.** Does the pod-descent machinery run on this client and does the rider co-descend with it?
Flight 2 proved the mount + horizontal-cruise ride works ([MT] RIDE samples). Flight 3 tests
whether calling `StartPodGameplay` via ProcessEvent slot 78 (§6.9 recipe) makes the pod:
(a) deactivate its cruise mover immediately, (b) fire its ~6.5s IntroSequence timer, (c) re-
activate the mover with velocity aimed at `CurrPodDestination(-3206.4, 5070.5, 100.0)`, and
(d) descend from Z=20100 to Z=100 while the rider (POLL) stays with it.

**Arm chosen: `mount-descend`** (`KMTARMS=0x1F` = all five bits: APPEND + UNHIDE + POSITION-ONCE
+ POLL + PHASE-B). Just-rebuilt (**`.text RAW c26e8831f45d7548`**, VirtualSize `bcdba837886743bc`,
KERNEL32-only; superseded stale pre-2060cb8 `b6941b5929723a96`).

**Regression gates verified (2026-09-01, post-rebuild):** `botai 5e47c13cf7f0a158` UNCHANGED,
`play 9bc10a4552c596e1` UNCHANGED. `mount-phaseb` (isolation control) also rebuilt clean:
**`d69642beacc5e7a8`** (moved from stale `c144ccf255b2cc0b`). All four regression gates hold.

**Staging (identical to flight 2 — the proven recipe):**
```
gft → fo → sp → dumpimage-early → dropplane_b1only → droppod-pe-cdopoke → reader → mount_descend
```
- gft/fo/sp: standard staging via `configs/fk24-stage.ps1 -SkipProbe`
- dumpimage-early: preserve evidence RIGHT after sp completes (`[SP] done step=4`)
- dropplane_b1only: creates the DropShip (still faults at SpawnPlane statement [10] per §6.9,
  but ship spawn is EARLIER — census `DropShip 0→1` is the gate; flight 2 confirmed [M])
- droppod-pe-cdopoke: creates the pod actor with PodTeamIndex=0 + CurrPodDestination populated
- **reader started BEFORE mount_descend, --secs 120** (need 6.5s IntroSequence timer + descent
  time + margin; flight 2 used 60s for cruise-only test)
- mount_descend: the treatment

**Pre-registered receipts (write BEFORE the flight — a null is only interpretable against these):**

R1 (mount append) — inherited from flight 2:
- `[RD] resolve: 1 pod actor(s), 2 live ALokiPlayerState(s)` (RdResolve gate passes on the fresh pod)
- `[MT] APPEND OK -- R1: PlayersAttached.Num 0 -> 1`

R3 (ride) — inherited from flight 2:
- `[MT] RIDE:` samples continue firing throughout the descent (POLL is bit 0x08, on in 0x1F)

PB (Phase-B, the NEW receipts this flight tests) — from §6.9:
- **PB-a [call reached]:** `[MT] PHASE-B: RETURNED. RECEIPT bHasStartedGameplay 0 -> 1`
- **PB-b [immediate stop]:** pod `ComponentVelocity ~(0,0,0)` IMMEDIATELY after PHASE-B call —
  expected because StartPodGameplay's first act is `ProjectileMovement.Deactivate()`. A ZERO
  HERE IS NOT A FAILURE.
- **PB-c [state byte stays 0]:** pod `DropPodState @+0x540` stays 0 (or reads unchanged) —
  §6.9 caveat: `SetDropPodState` has `if(LokiIsClient) return`, so the state-write is skipped
  on this client. A ZERO HERE IS EXPECTED, NOT A FAILURE.
- **PB-d [DESCENT ONSET, ~6.5s later]:** pod `ComponentVelocity` re-populates with dominant
  NEGATIVE Z (pod at Z=20100, dest at Z=100). If PB-d holds: `StartPodMovement` re-activated
  the mover above the client-return gate, exactly as §6.9 predicts.
- **PB-e [Z trajectory]:** pod `ActorLocation.Z` decreases monotonically toward 100 uu.
  Descent to ground should take ~5-10s at InitialDropPodSpeed.
- **PB-f [arrival]:** pod hides (`SetActorHiddenInGame(true)`) on ground contact via
  `OnDropPodHit → StartDestroyPod`. Pod census -1 (or hidden flag set).

**R3-during-descent (the composed receipt):**
- `[MT] RIDE:` samples DURING descent should show hero_Z decreasing in lockstep with pod_Z.
  Reader R3 verdict should be a lateral+vertical co-movement.

**Named failure modes (pre-registered — a fault here is not a null):**
1. **Phase-B ProcessEvent FAULTS.** §6.9 says StartPodGameplay has 0 params → no OutParms
   involvement → the FFrame+0x80 primitive bug should NOT fire. But `MtStartPodGameplay`'s SEH
   catches faults. If `[MT] PHASE-B: ProcessEvent FAULTED` prints, we've hit a new primitive
   defect — grade offline and consider `mount-phaseb` isolation.
2. **PB-a fires but PB-d never comes.** `bHasStartedGameplay 0→1` but pod stays stopped.
   Means StartPodGameplay's body doesn't reach StartPodMovement — an untested gate exists.
   Fallback: `mount-phaseb` (KMTARMS=0x10, Phase-B only, no mount confound) to isolate.
3. **Hero de-syncs during descent.** POLL fires on every OnPI hit, but descent may be faster
   than OnPI's dispatch cadence. Some lag is expected; large de-sync (>1000 uu) means POLL
   isn't keeping up.
4. **`KickPlayersFromPod` fires and drops rider.** Per CLAUDE.md, has `if(LokiIsClient) return`
   — should NOT fire on this client, but worth watching.
5. **`bHasStartedGameplay` was already 1 before Phase-B call.** MtStartPodGameplay logs this as
   `⚠ non-zero -> body may no-op at its idempotency guard`. Would mean something ELSE started
   the pod before us — unexpected and diagnostic.

**Fallback flights if mount-descend fails, in priority order:**
- **F1: `mount-phaseb` (KMTARMS=0x10, `.text d69642beacc5e7a8`)** — Phase-B ONLY, no mount.
  Fresh pod, one Phase-B call, watch for PB-a..f. If pod descends here but not in mount-descend,
  the mount append/POLL is confounding Phase-B (unlikely but possible).
- **F2: `mount-ride` (`.text 9b7f88af3210c438`) again as sanity control** — same as flight 2,
  proves the arm+staging still work if the fresh session is misbehaving.
- **F3: adjust the KMTSEATZ offset if hero clips inside the pod during descent** — currently 120 uu
  above pod origin (matched pod diameter for the cruise flight). May need larger negative offset
  for a descending pod to sit correctly.

**Budget:** 6 injections identical to flight 2. Game survived 6 in flights 1 and 2, but FK-32
mode is 4 — not guaranteed. Take dumpimage EARLY (after sp) so evidence survives mid-arm death.
Extend reader window to `--secs 120` to catch the 6.5s IntroSequence timer + descent + margin.

**Success criterion:** if all of PB-a, PB-d, PB-e, and R3-during-descent land — pod descends AND
rider co-descends — we've proven the full drop-and-arrive chain works. This unblocks the S132
dismount-at-landing composition (§6.10 acceptance chain) — landing the hero on real terrain from
a driven drop, one flight away from "playable hero via a driven drop" per the operator's original ask.

**Not tested by this flight:** the ACTUAL landing (dismount → play). Even if descent works, the
hero still needs to be transferred to normal Pawn control (S132 dismount is the recorded route).
That's the NEXT flight after this one.

### 6.13 MOUNT-FLIGHT 3 RESULT — Phase-B works, descent does NOT auto-fire (2026-09-01)

**Substantial partial success + a new named blocker.** Flight 3 flew `mount-descend`
(`.text c26e8831f45d7548`, `KMTARMS=0x1F`, all five bits) after the identical proven staging
recipe. Game died at t=+37.6s in the reader — **user right-click input, unrelated to the arm**;
did not affect the receipts collected. Evidence at `docs/mount-flight-3-final-marker.txt` (29 KB)
+ `dumps/s150-mount-flight-3-early/`.

**Sequence flown (7 injections including droppod's own arm; game survived them all — right-click
crash was orthogonal):**
`gft → fo → sp → dumpimage-early → dropplane_b1only → droppod-pe-cdopoke → reader --secs 120 →
mount_descend`. Ship census `DropShip 0→1` (fault reproduced as expected, ship spawned anyway,
matching flight 2). Pod created with `PodTeamIndex=0`, `CurrPodDestination=(-3206.4,5070.5,100.0)`,
cruise at ~20k uu/s (pod X: 371939 → 375146 in a few s before Phase-B call).

**Pre-registered receipts — LANDED:**
- ✅ **PB-a (Phase-B call reached AS body):** Reader verdict `PB bHasStartedGameplay reached 1
  YES  (StartPodGameplay ran)`. Latch flipped 0→1. **[M]**
- ✅ **PB-b (immediate mover deactivation):** pod velocity read `(0,0,0)` all samples after
  Phase-B call, and pod position FROZE at `(970632.4, 5070.5, 20100.0)` — 40+ `[MT] RIDE:` samples
  show the exact same coord. `ProjectileMovement.Deactivate()` confirmed [M].
- ✅ **R1 (append):** `PlayersAttached.Num 0 → 1` (reader verdict). **[M]**
- ✅ **R3 (POLL keeps hero AT frozen pod):** all `[MT] RIDE:` samples show
  `pod=(970632.4,5070.5,20100.0) hero->(970632.4,5070.5,20220.0) AT-POD`. The per-hit reposition
  continues to work even when the pod is stationary. **[M]**

**Pre-registered receipts — DID NOT LAND (the new blocker):**
- ❌ **PB-d (descent onset after ~6.5s):** pod velocity never re-populated with negative Z during
  the ~30s observation window. Pod stayed FROZEN at `(970632.4, 5070.5, 20100.0)` for
  well past the expected `IntroSequenceTotalTime ≈ 6.5s`. **Descent DID NOT spontaneously
  occur after Phase-B call.**
- ❌ **PB-e (Z trajectory):** N/A — no descent to observe.
- ❌ **PB-f (arrival + hide):** N/A.
- ❌ **R3-during-descent:** N/A — no descent motion to co-track.

**★★★★★ NEW NAMED BLOCKER — the IntroSequence timer / `OnIntroSequenceFinished` path is NOT
auto-firing on this client.** §6.9's chain was:
`StartPodGameplay → arm SetTimer(OnIntroSequenceFinished, ~6.5s) → OnIntroSequenceFinished →
SetDropPodState(Descending=3) → StartPodMovement`. §6.9 established that `StartPodMovement`
runs ABOVE the `SetDropPodState`'s `if(LokiIsClient) return`. But flight 3 shows the chain
STOPS EARLIER — either the timer doesn't fire on the client, or `OnIntroSequenceFinished` has
its own gate that fails. Since `bHasStartedGameplay` LATCHED (proving StartPodGameplay's body
ran successfully), the failure is *between* StartPodGameplay's return and StartPodMovement's
Velocity write.

**Three hypotheses for where the chain breaks (all offline-gradeable):**
1. **H1 — timer never fires on client:** `System::SetTimer` may skip callbacks on
   `LokiIsClient==true`, or the timer is registered against a mode-specific timer manager that
   doesn't tick without full server context.
2. **H2 — `OnIntroSequenceFinished` has an unrecorded `LokiIsClient/HasAuthority` early-return:**
   §6.9 only transcribed the `SetDropPodState` client-return, not the timer callback's own
   guards. `OnIntroSequenceFinished` (LokiDropPod.as ~L4088-4104 per §6.9) has a leader-pod
   branch — that branch may have its own gate.
3. **H3 — `StartPodMovement` reads a state field that requires the client-skipped
   `PodStateEvent.DropPodState` write:** §6.9 said StartPodMovement runs "above" the gate, but
   "above" may mean "in a different function that gets called only if state==Descending". The
   state doesn't advance on the client because SetDropPodState client-returns before the write.

**Corrections banked from this flight:**
- §6.9's "StartPodMovement is called ABOVE the gate and reads CurrPodDestination directly" was
  **[I], not [M]**, and this flight is the first empirical test of it. **The claim is now
  REFUTED at the level of live observation:** either the reads happen but produce no Velocity,
  or the chain never reaches StartPodMovement. Grade §6.9's descent-still-works assertion as
  **[REFUTED] pending offline localization** of the three hypotheses above.
- The `mount-descend` arm's POLL correctly repositions the rider to a STATIONARY pod (unexpected
  bonus — proves the arm is robust to Phase-B's mover deactivation). This is a positive control:
  if the descent DID fire, POLL would ride the hero down with it.
- 7 injections + user-input crash. Game survived all 7 injections; only the right-click killed
  it. This suggests the FK-32 6-injection ceiling may be loosening (or we're seeing selection
  bias). Not a load-bearing conclusion.

**Route decision for flight 4:**
- **BEST NEXT STEP — offline first:** transcribe `OnIntroSequenceFinished`'s AS body (LokiDropPod.as
  around L4088-4104 per §6.9) end to end and enumerate ALL gates on the leader-pod branch. This
  localizes the H1/H2/H3 disjunction to one hypothesis. Then design the fix as another arm
  (poke-then-Phase-B, or direct-call StartPodMovement, or set the state byte manually).
- **Fallback if OnIntroSequenceFinished is a dead end:** direct-call `StartPodMovement` on the
  pod (bypassing the timer + state chain entirely). This is another ProcessEvent call if it's a
  reflected AS UFunction; another `MtStartPodGameplay`-style extension to the arm.
- **Compose forward** — even with the descent unresolved, the mount+static-ride path IS solid
  enough to consider chaining to the S132 dismount for a "cinematic flight-and-dismount" hybrid
  (per §6.10 fallback plan): the hero WOULD be visibly mounted on the horizontal cruise, dismount
  at any chosen landing actor, land on real terrain, and be `play`-drivable. This gets us to
  "playable hero via a driven drop" WITHOUT needing the descent to work.



### 6.6 Landing-SELECTION UI RE (2026-09-01, offline; 4 lanes + verifier + a widget re-run)

**The selection UI is a SPLIT problem, and stage 3 (the reticle) is COUPLED to stage 2 (the plane).**
- **The selection-open FLAG is shim-drivable [M]:** `ULokiPlayerDropPlaneComponent::OnSelectDropLocationStarted`
  (reflected BlueprintEvent, `ProcessEvent` slot 78) sets `bCanSelectDropLocation=true` +
  `SetComponentTickEnabled(true)`, gated only by `IsLocalClient()` (passes on this client).
- **The COMMIT path is mapped [M/I]:** `SetDropPodDestination` (slot 157) stores the chosen `FVector`
  at `component+0x118` (byte `+0x130 bDropLocationSelected`); `ServerSetDropPodDestination` is a
  **stripped** fold; `ServerLaunchDropPod` (slot 152) is **real-but-DARK** →
  `AuthLaunchDropPodForTeam(FDropPodParams{Destination}) → SpawnDropPodForTeam`. All native-reflected,
  CALL-ONLY. **No backend/HTTP route.** ⚠ The DARK bodies (`0x56FAE90`/`0x56FACE0`/`0x56FF1D0`) are
  `[I]` (undecrypted); only the getter `0x56EBA30` + gate `CanLaunchDropPod 0x56DEB00` are `[M]`.
- ★★★★★ **[M] THE RETICLE KEYS ON THE PLANE, NOT THE FLAG — the make-or-break, settled offline from
  the reticle's own `OnPaint` bytecode.** `WBP_UI_DropPlane_SpinningDonut::OnPaint` (minimap reticle;
  the fullscreen twin is `WBP_UI_DropPlane_Slices` in `WBP_UI_ExpandedMap`) draws only if ALL pass:
  `MapViewComp` valid · `GetLocalLokiPlayerState()` valid · the `LokiPlayerDropPlaneComponent` valid ·
  **`bDropLocationSelected == false`** · **`component.DropPlane` dynamic-casts to
  `BP_DropPlane_SpinningDonut_C`** (a live `ALokiDropPlane` actor). **`bCanSelectDropLocation` is read
  by the reticle ZERO times** (only the input-legend `WBP_UI_DropMap_ButtonInputs` reads it), and the
  AS `UpdateDropLocationCursor` tick is vestigial (computes into discarded locals, no member store).
  ⇒ **driving `OnSelectDropLocationStarted` alone will NOT render the reticle** — the reticle is
  blocked by the PLANE (`component.DropPlane` is null; `ALokiDropPlane::AuthStart` flight is a stripped
  `0xF7EC20` stub). **Stage 3 is a plane-substitution problem, not a flag flip.**
  ⇒ ★ **The container half IS client-drivable:** `WBP_UI_ExpandedMap`'s `Enable Drop Phase State`
  (plain client BlueprintCallable, no ServerOnly gate) switches `WidgetSwitcher_GamePhase →
  DropPhaseWidgets` on component presence — so the drop-map opens, but its reticle content stays empty
  without a plane.
- ⚠ **CORRECTION banked:** `WBP_UI_PredropScreen`/`_PlayerEntry` (the prior guess) is **NOT the
  reticle** — it's the champions/team-lineup grid. The reticle is `WBP_UI_DropPlane_SpinningDonut`
  (minimap) / `WBP_UI_DropPlane_Slices` (expanded map). `WBP_Minimap_DropPod_Aim_Indicator` /
  `WBP_UI_DropPodIndicator_Animated` is the **post-launch pod-aim crosshair**, not the pre-drop reticle.
- ⇒ ★★ **IMPLICATION FOR THE PLAN:** the selection reticle AND the plane flight are ONE blocker (a
  live `ALokiDropPlane` actor of the right BP class assigned to `component.DropPlane`, with geometry
  populated) — `SpawnPlane`'s caller is unresolved and `AuthStart` is stripped. **The POD-ride path
  (`RM_MOUNT`) is separate and further along, and pod PLACEMENT does not need selection** —
  `SpawnDropPodForTeam(LandingLocation)` (S131) sets `CurrPodDestination` directly. So the realistic
  route to "playable hero via a driven drop" is the pod path; the plane+selection is the authentic-BR
  polish and is gated on plane substitution (an open research problem). Do NOT fly the "flag-only"
  selection probe — it would predict a null (flag on, reticle blocked) that this RE already establishes.
  ⚠ Whether the tutorial's configured plane (`BP_DropPlane_Straight_Tutorial`) IS-A
  `BP_DropPlane_SpinningDonut_C` (the exact cast class) is `[S]` — check before any plane substitution.

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
