# NEXT SESSION (S132) — the pod is alive, the FIFTH WALL is confirmed, and the blocker is one stripped getter.

**Written 2026-08-20 at the end of S131.** Read `docs/s131-pod-functionality-settled.md`, then
`docs/fk22-dropphase-reachability.md` §29. Evidence: `scratchpad/s131/evidence/`.

---

## 0. WHAT S131 DID

1. Built `PdPodDump()` — an **in-arm** pod-state readout (RM_DROPPOD + RM_POOLSPAWN), pure guarded
   reads, no extra `GUObjectArray` sweep, with a by-name calibration control and an
   Angelscript-offset cross-check printed beside every field.
2. **[M] `InitializeDropPod` ran and its three discriminating writes landed** — against a within-run,
   same-class negative control of three pods that all read class defaults in the same dump.
3. **[M] The pod is ALIVE and FLYING at its cooked `InitialSpeed` of 20,000 uu/s**, with Niagara drop
   VFX ticking and UE logging LWC tile recaches for it. It flies **because `StartPodGameplay` never
   ran** — and that is because `Loki::LokiIsServer()` is a stripped `return false`.
4. ⚠⚠ The fifth wall was NOT tested by the Route-E flight (null `PlayerState` -> silent return on
   instruction #1) — **but it WAS tested afterwards, on the same live client, and CONFIRMED. See §0.5.**
5. Free side result: **FK-31's kill jumps to one fixed address per boot session**, the same address
   across FK-7 and FK-31 alike — and that hands FK-31 its first cheap experiment (§3).

---

## 0.5 ★★★★★ SUPERSEDED SAME DAY — THE FIFTH WALL IS ALREADY CONFIRMED. §1 BELOW IS DEAD.

**Do not spend a launch on §1.** After writing it, S131 tested the wall directly on the *same live
client* and confirmed it. Read `docs/s131-pod-functionality-settled.md` §10.

* ⚠⚠ **§1's lever is BLOCKED AT ITS PRECONDITION and was killed by ONE read-only command:**
  **[M] ZERO live instances of any class containing `TeamOnly`**; the only `TeamState`-named live
  object is `Comp_TeamState_GlobalShop_GEN_VARIABLE`, a template. **There is no TeamState actor to
  poke.** ⭐ Check a lever's precondition with a read-only pass *before* building the arm.
* ★ Instead, **`RM_RIDEABLE` (enum 29)** calls `AuthPlayerEnterWorldAttachedToRidable` **directly**
  on the pod's own `LokiRideable` component with a live, valid PlayerState. Against a verified
  baseline of 0, `Loki.log` gained
  `LogLokiRideable: Error: ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable failed to
  get the round game mode` — **count 0 → 2, exactly one per call.**
* ⇒ **[M] the wall REACHES `0x55CD572`, gets 0 from the stripped `0xF7EB50` getter, and fails — with
  valid arguments.** Controls: `ContainsPlayer` on the same object through the same primitive
  (`fault=no`), both of the wall's own IsValid preconditions read out and PASSING, two independent
  PlayerStates, and an exact per-call count.
* ★ By-product: the log category, recorded COVERAGE-BLOCKED by lane 4, **named itself** the moment
  the path ran — **`LogLokiRideable`**.

### ⇒ THE REAL §1 FOR S132: what does `0xF7EB50` REPLACE, and is there another route?

The blocker is now precisely one stripped server-side getter, in the same family as FK-1's four empty
stubs, sitting between a fully working pod spawn and a rider ever boarding. **That is an OFFLINE
question and it is free:**

1. Identify the call at `0x55CD572` — which round-game-mode accessor was folded to `0xF7EB50`
   (`xor eax,eax; ret`)? ⚠ `0xF7EB50` is ICF-folded, so the address names a *behaviour*, not a
   function; identify it from the CALL SITE's surroundings, as lane 1 did for `LokiIsServer`.
2. Enumerate every other producer of an `ALokiRoundGameMode*` on the client. S124 established the
   tutorial already RUNS the round mode (`BP_LokiGameMode_Tutorial_C`), so a live round game mode
   plausibly EXISTS — the question is whether the getter the wall uses is the only route to it.
   ★ If another accessor is REAL, the wall may be one data poke away rather than a dead end.
3. Re-run the `.data` record sweep (`scratchpad/s131/tools/rectab.py`) over the round-game-mode
   accessor family, the way lane 4 did for `ULokiRideableComponent` — it grades REAL vs EMPTY
   **without the code page being decrypted**.

★ And `merged3.dump.exe` now contains drop-path pages that were never decrypted before, including
whatever `RM_RIDEABLE` just executed. Re-dump-and-merge after any future armed window.

---

## 1. ⛔ DEAD — KEPT ONLY AS THE RECORD OF A LEVER THAT WAS KILLED. See §0.5. Do not run this.

Everything downstream of the pod now hinges on one null:

```
v38 = this.GetTeamDropLeader(TeamIndex)          -> null
  -> SetPilotPlayerState(null) ; SetOwner(null)   (both null->null, no information)
  -> RemovePlayerFromPlane(null)                  (empty stub anyway)
  -> AuthPlayerEnterWorldAttachedToRidable(null, Landing)
        0x55CD510  test rdx,rdx ; je <ret>        <-- SILENT RETURN, instruction #1
  -> MulticastOnDropPodLaunched                   SKIPPED (guarded on v38 != null)
```

**Why it is null, [M]:** `GetTeamDropLeader` returns the first PlayerState on the team with
`IsSpawnTeamLeader()` true. `ALokiPlayerState::IsSpawnTeamLeader` (impl **`0x56C2060`**, real,
decrypted in all three images) is a **pure read**: `GetWorld()` → `edx = [this+0xE88]` (team id) →
`GetTeamState` (`0x56F02E0`) → `rcx = [TeamState+0x688]` → resolve (`0x3259330`) → `sete al` on
`== this`. **The only writer of `[TeamState+0x688]` is `ALokiTeamState_TeamOnly::SetDropLeader`,
which is one of FK-1's four EMPTY STUBS** (`impl 0x0F7EC20 = ret 0`), as is
`ALokiPlayerState::AuthSetSpawnTeamLeader`. **Nothing on this client can set a drop leader.**

### 1.1 THE LEVER

**Poke `[TeamState+0x688] = <a live ALokiPlayerState*>`** on the live `ALokiTeamState_TeamOnly`, then
call `SpawnDropPodForTeam` again.

* Same write class as S130's CDO poke: **one aligned heap field, readback-verifiable, no module image
  touched.** On this project's hazard ladder that is the safest change there is.
* It **bypasses both empty stubs** rather than trying to make them work.
* The hero's `ALokiPlayerState` already exists in a staged world (`sp` possesses a hero), so a valid
  pointer is available — resolve it BY NAME off the PlayerController, do not hardcode.

### 1.2 WHAT IT BUYS, AND HOW TO READ IT

With a non-null drop leader, ALL of these become live for the first time:

| what | receipt |
|---|---|
| `SetPilotPlayerState` / `SetOwner` | `PilotPlayerState @0x3C0` and `Owner @0x150` become **non-null** — two fields that were null→null in S131 and carried no information |
| **the FIFTH WALL** | `AuthPlayerEnterWorldAttachedToRidable` passes its `test rdx,rdx` and reaches the round-game-mode lookup. ★ **`grep "failed to get the round game mode"` becomes INTERPRETABLE** — the emit is [M] not stripped (dispatches through the live logger `0x106B650`) |
| `MulticastOnDropPodLaunched` | its `if (v38 != null)` guard opens |
| `QueueCrewForPodSpawn` | `AttachedCrewPods @0x490` `Num > 0` would mean `GetPlayerStatesOnTeam` returned live PlayerStates |

⚠ **Pre-register the reading of a null result.** If `PilotPlayerState` still reads null after the
poke, that says `GetTeamDropLeader`'s scan did not accept the poked value — read `[this+0xE88]` (the
PlayerState's team id) and confirm it matches the TeamState you poked. Do NOT record it as "the wall
held" without that check.

### 1.3 SMALL PROBE UPGRADES WORTH MAKING FIRST (cheap, offline)

1. ★★ **Add the two-sided bool control** the S131 audit asked for and I could not land in time:
   `bHidden` and `bAlwaysRelevant` must **both** resolve to `Offset_Internal 0x68` with **ByteMask
   `0x80` and `0x08`** respectively. Same offset, different mask ⇒ unfalsifiable by garbage, and it
   turns the `FBOOLPROP_*` layout from **[I]** to **[M]** in-arm. (S131 measured every bool as
   `fs=1 bo=0 bm=0x01 fm=0xFF`, which is consistent but has no two-sided check behind it.)
2. Add **`AttachedCrewPods` (0x490)** as an explicit named field — it is `QueueCrewForPodSpawn`'s
   receipt, i.e. the LAST thing `InitializeDropPod` does, and S131 only saw it via the sweep.
3. Add **`ComponentVelocity`** to the location line. S131 had to take it by external RPM afterwards;
   in-arm it is one more read and it is what named the mover.

---

## 2. THE OTHER HALF OF §28.5 — "or carries a player"

Even with a drop leader, the pod carrying a *hero* runs into
`ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable`'s **always-fail** body (S130 §26,
independently re-confirmed by S131 lane 4's `.data` record sweep: impl `0x55CD510`, REAL).

⚠ But S131 lane 4 also resolved the rest of that family for the first time, out of `.data`, **without
the code pages being decrypted** — and it found a NEW empty stub:

| key | impl | verdict |
|---|---|---|
| `AuthPlayerDetachPlayerFromRidable` | `0x55CCCB0` | REAL |
| `AuthPlayerEnterWorld` | `0x55CCE70` | **REAL** — large body, security cookie |
| `AuthPlayerEnterWorldAttachedToRidable` | `0x55CD510` | REAL (always-fail) |
| **`AuthPlayerEnterWorldNew`** | **`0x0F7EC20`** | **EMPTY — new, raises the drop-class empty count 13 → 14** |
| `AuthPlayerPreSpawnOnAddToPlane` | `0x55CD800` | REAL |
| `ContainsPlayer` | `0x55D0270` | REAL |
| `GetLandingTeleportLocation` | `0x55D89F0` | REAL |

★ **`AuthPlayerEnterWorld` (`0x55CCE70`) is REAL and has never been called.** It is the obvious
sibling to try if the attached-to-ridable variant stays foreclosed.

Full table: `scratchpad/s131/lane4-record-sweep.md` (**7/7 non-degenerate controls PASS**, 4 EMPTY +
3 REAL, separated correctly). ⚠ Its stated blind spot governs: **for a `Net` key the record's impl is
the UHT send stub, not the `_Implementation`** — never grade an RPC from that table alone.

---

## 3. FREE AND HIGH-VALUE: THE FK-31 KILL-ADDRESS EXPERIMENT

`scratchpad/s131/evidence/FK31-kill-address-is-constant.md`.

**[M] The kill jumps to one fixed address per boot session** — `0x7FFB57400001` in the current era,
bit-identical across every launch, not an offset from any loaded module, covered by no module and no
executable region. 31 minidumps, 3 eras. It unifies FK-7's `.text`-patch kills and FK-31's staging
deaths into **one kill routine**.

**The experiment: map an executable page there before arming.**
`VirtualAlloc(addr & ~0xFFF, 0x1000, MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE)`, write `ret` at
`+1`. Then:
* the process may **survive** the kill outright, and
* the **return address on the stack names the caller** — the protector code that decided to kill,
  which is what FK-10's Wall #7 has been hunting for sessions.

⚠ Read the address off the most recent crash **in the current boot session** — it changes across
reboots. ⚠ The page may already be RESERVED (then the alloc fails; the probe must SAY so, not
continue silently). ⚠ A tail `jmp` rather than a `call` means the stack top is the grandparent frame.
**All three outcomes are observable and all three beat a silent death.**

⚠⚠ **And fix the recorded detection rule while you are there.** `CLAUDE.md` says *detect by
`RIP == runtime.dll base + 1`* — **[M] `runtime.dll` has no module entry in ANY crashpad minidump**
(0 of 14 sampled; control `preloader.dll` 14/14). A successor applying that rule will find the module
missing and conclude the family does not match.

---

## 4. HOW TO RUN IT (S131's sequence, which worked)

1. `forceTutorialMatch = true` in `server/internal/interactive/interactive.go`, rebuild `ags`.
   **Set it back to `false` when done** — it is committed as `false`.
2. Back up `docs/capture.log` (its restart behaviour is recorded as both truncating and appending).
3. Elevated: `.\configs\launch-redirect.ps1 -NoHook`
4. `.\configs\fk24-stage.ps1 -Probe <arm> -Label <tag> -AllowStale`
   ⚠ **`-AllowStale` is REQUIRED.** The deployed `fo fa184b20934cc4b0` / `sp 4285c0dd22ae9976` in
   `tools/sigbypass-mod/` (NOT `build/`) are the known-good staging pair; both verified this session.
5. Into the SAME live PID, ≥20 s apart:
   `tools\inject\inject.exe mmap <pid> tools\sigbypass-mod\build\tutorial_launch_dropplane_b1only.dll`
   then your Route-E arm.
6. **Copy the marker off after every injection** — `RM_DROPPLANE` and each probe overwrite it.
7. ★ **While the client is still alive**: take external RPM reads
   (`scratchpad/s131/tools/pod_live_read.py`) and run `usmapdump dumpimage` — S131's dump added
   **+43 `.text` pages, 0 conflicts** to `dumps/merged3.dump.exe`.

⚠⚠ **A STAGER ABORT IS NOT A DEAD LAUNCH.** S131's launch 2 timed out on
`LVL_Tutorial load complete` because the **lobby map took 146 s to load** and `fo`'s console command
fired mid-`LoadMap`. The process was healthy; re-running `fk24-stage.ps1` on the same PID produced
the entire session's result. **Check `Get-Process` before spending another launch.**

⚠ Budget: S131 spent **2 launches for 1 armed window** (launch 1 died to FK-31 at `fo`+15 s). But the
armed window then lasted **>25 minutes** with the client alive throughout.

---

## 5. REPO STATE

- ✅ Tree clean, everything committed. `forceTutorialMatch` is committed as **`false`**.
- **Build arms (`.text` sha256; `-Name tutorial_launch` must be given explicitly — `-Variant X` alone
  silently builds the DEFAULT set and reports success):**

| variant | `.text` | note |
|---|---|---|
| `droppod-pe-cdopoke` | `249a3cd2190eb334` | Route E + poke — **what S131 flew** |
| `droppod-pe-cdoctrl` | `61fd0745c23e89f0` | same, read-only CDOs |
| `poolspawn-cdopoke` | `efe8db553bf511ba` | the negative-control population |
| `poolspawn-cdoctrl` | `85f3cee44c31b1cd` | same, read-only CDOs |
| `dropplane_b1only` | `5b4467b0105dec1a` | **UNCHANGED** — Route E's precondition |
| `play` | `9bc10a4552c596e1` | **UNCHANGED** — hard regression gate |

  ⚠ Each pair shares a `.text` **size**; only the hash separates them. Both verified DISTINCT.
  ⚠⚠ The new census latches are gated on `kRunMode` **precisely so the last two stay byte-identical**.
  An **ungated** `strstr` in the shared `DpEvalClass` moved `b1only`'s hash while leaving its `.text`
  size identical (120,832 B both ways — it fitted in section padding). **Diff the hash, never the size.**
- **New tools:** `scratchpad/s131/tools/` — `pod_live_read.py` (read-only RPM of a pod's fields),
  `pod_verdict.py` (evaluates a marker against the pre-registration), `rectab.py` / `lane4_sweep.py`
  (the `.data` record sweep).
  ⚠⚠ `pod_verdict.py` shipped a regex with ONE space where the probe prints `@0x%-4X` and reported
  **`UNINTERPRETABLE (nothing resolved)` for pods whose values were plainly in the log.** Fixed and
  documented in-file. **An analysis script is an instrument too — read the raw artifact beside it.**
- **New cold image:** `dumps/merged3.dump.exe` — strict superset of `merged2`, +43 `.text` pages from
  the live drop-pod process.
- 12 offline recon reports in `scratchpad/s131/lanes/` (6 lanes + 6 adversarial verifications).

---

## 6. WHERE FK-22 STANDS

```
markers        REFUTED  (S124)
phase          SOLVED   (S124)
subscription   DEAD     (S124)
SpawnPlane     FAULTS   (S124/S17) -- b1only still creates a live LokiDropShip
SpawnDropPodForTeam  ->  RETURNS TRUE, DropPod +2                      FIXED S130 §28
  |
  +- bail 2 was C7: AActor::bCanEverReplicate on the pod CDOs
  +- the pod is INITIALISED, ALIVE and FLYING at 20,000 uu/s           MEASURED S131 §29
  |    InitializeDropPod ran 3/3, VFX ticking, engine logs LWC recache
  |    it flies BECAUSE StartPodGameplay never ran (LokiIsServer is a stub)
  +- NEXT: the rider handoff, blocked by a NULL DROP LEADER            <-- YOU ARE HERE
  |    NOT by the fifth wall -- that was never reached this sitting
  |    lever = poke [TeamState+0x688], bypassing FK-1's two empty stubs
  +- then the FIFTH WALL for real (AuthPlayerEnterWorldAttachedToRidable)
  +- C8 / C9 still never fired: unexercised, NOT excluded
```
