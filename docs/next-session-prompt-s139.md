# NEXT SESSION (S139) — the bot thinks but does not move. Find out why, with a moving control.

**One line: the bot's AI runs end to end — behaviour tree → blackboard → wander → movement input,
all measured live — and the pawn never moves one unit. Four hypotheses are already refuted. The
next step is to run `play` (which DOES move the player on this route) and diff a MOVING movement
component against a NON-MOVING one.**

Written 2026-08-23 at the end of S138. Read `docs/s138-flight9b-flymode-refuted.md` first, then
`docs/s138-flight8-the-bot-thinks.md`. The CORRECTIONS blocks in
`docs/s138-flight2-arme-fired.md` §2b and §1 of `docs/s138-flight9b-flymode-refuted.md` govern.

**STATE AT HANDOFF:** no client running (the last died to FK-32 after the reads were taken, as every
S137/S138 sitting has). Nothing is lost — every result is on disk (§6). `ags` may still be up.
Two tracked files are modified and **uncommitted**: `tools/sigbypass-mod/tutorial_launch.cpp` and
`tools/sigbypass-mod/build.ps1`.

---

## 0. THE CHAIN AS IT STANDS — every link measured except the last

    nothing writes LivingState=Alive                                  [M] offline, 2 writers, both store 0
      -> every character reads Dead (6/6 live + 30/30 CDOs)           [M] live sweep
      -> poke LivingState=1, call UpdateCharacterControllable         [M] ARM F
      -> the gate bCharacterControllable (+0x6A0) OPENS 0 -> 1        [M] the game's own function
      -> Tick's wander driver RUNS: 44 fresh unit directions / 97 s   [M] 194 samples
      -> ControlInputVector receives them, 193/194 samples            [M] controller -> pawn
      -> ??? the movement component never consumes them; nothing moves

**REFUTED, in order — do not re-open any of these:**
1. ~~The gate / `LivingState`~~ — it opens, legitimately, and the AI runs behind it.
2. ~~`MovementMode` is wrong~~ — bot and player are **BOTH `MOVE_Falling` (3)**, identical.
3. ~~Force `MOVE_Flying` (what `play` does for the player)~~ — poked, held 25 s, **no effect**.
4. ~~The component is deactivated~~ — `bIsActive = True` and `bAutoActivate = True` on **both**.

**STANDING, and it is now precise:** `ALokiBotController::Tick` **is** running (only Tick
re-randomises the wander every ~2 s), but `ControlInputVector` is **never consumed** — and stock UE
zeroes it inside `UCharacterMovementComponent::TickComponent` every movement tick.
⇒ **the controller ticks; the character movement component does not.**

---

## 1. ★ START HERE — get a MOVING control, then diff

Every "why doesn't it move" hypothesis so far has failed for the same reason: **there has never
been a known-good positive control.** Both the bot and the player sit motionless in the bare staged
world, so "the bot doesn't move" has had nothing to be compared against.

**`play` moves the player hero on this exact route** — CLAUDE.md records `*** init complete: body=
BUILT; camera + WASD active ***`, `PlayAnimation(run, loop) ok`, and the hero moving **+2,945.7 uu**.
That is the control.

### 1.1 The plan, and it needs NO new offset

1. Stage a world (`configs\s138-autostage.ps1`, see §3).
2. Inject **`tutorial_launch_driverecompute.dll`** → ARM D makes the `LokiBotController`, ARM F
   opens the gate. Confirm `ARM F AFTER … GATE+0x6A0=1`.
3. Inject **`tutorial_launch_play.dll`** → the PLAYER hero starts moving.
4. **While the player is moving**, dump BOTH movement components and **DIFF them**:
   `python tools/re/obj_scalars.py <PID> <BASE> <botCMC>` and the same for the player CMC, plus
   `tools/re/obj_props_dump.py` for the object/array properties.
   **Whatever differs between a moving CMC and a non-moving one is the answer**, and this finds it
   without knowing in advance which field matters.
5. Sample both pawns' locations concurrently with `tools/re/motion_watch.py`-style reads so the
   claim "the player moved and the bot did not, in the same world at the same time" is measured
   rather than assumed.

⚠ **`play` is a CONTINUATION mode** — it attaches to a running tutorial and `return 0`s before the
force-open block, so it must go in AFTER the world is staged, never via `-Hook` alone.
⚠ **`play` teleports the hero to `(-65,-1770,393)` as its FIRST act** (`tutorial_launch.cpp:4822`).
`-DKNOTELE=1` skips that. Decide which you want before injecting: the teleport moves the player away
from the bot, which is fine for a CMC diff and bad for a same-place comparison.
⚠ **`play` sets `KFLYMODE=5` (`MOVE_Flying`)**. S138 flight 9b already poked the bot to `MOVE_Flying`
with **no effect**, so if the diff shows only the mode differing, that is a KNOWN non-answer — keep
looking.
⚠ `play`'s digest is **`9bc10a4552c596e1`** per CLAUDE.md. **Verify it before flying**
(`python tools/sigbypass-mod/text_digest.py`) — this session found `botspawn`'s recorded digest was
stale by ~17 hours of source drift.

### 1.2 If the diff shows nothing — the instrument that does not exist yet

`UActorComponent::PrimaryComponentTick` is an **`FTickFunction` struct member, NOT a UPROPERTY**, so
**none** of the reflection-based probes in `tools/re/` can see `bRegistered` / `bCanEverTick` /
`TickGroup`. That is a gap in the instrument, not in the evidence.
**Derive the offset offline first** (disassemble a known tick-registration path — e.g.
`UActorComponent::RegisterComponentTickFunctions` or `SetComponentTickEnabled` — and read the
displacement it uses), then one cheap live read on both components.
★ Do it with the player MOVING, so the read has a positive control on the very first attempt.

---

## 2. ⚠⚠ CORRECTIONS FROM S138 THAT GOVERN

**C1. Rule U2 from the ARM E pre-registration is REFUTED — do not apply it.** It said a dark
`0x5556D50` means execution did not pass the PlayerState gate. It is a non-sequitur (all three
PlayerState gates rejoin *upstream* of that receipt), and it was refuted empirically too: the gate
WAS passed and the page is still dark. The divert is **`0x556DE6A`** (`GetTeamState` NULL) — settled
by `[PS+0x8C8]` going 0 → 5 with the string `'bot0'`.

**C2. `TeamStates` can NEVER be non-empty on a client [M].** `GetOrCreateTeamState` (impl
`0x5634BD0`) is 16 bytes that call `GetWorld`, discard it, and `xor eax,eax; ret`. `SetNumTeams` is
the void fold. So anything past `0x556DE6A` in `SpawnBot` is unreachable. **Do not chase it.**

**C3. A SIXTH STUB SHAPE defeats the project's fold test:**
`sub rsp,0x28; call <GetWorld>; xor eax,eax; ret` (16 bytes, 5 sites, separately compiled). A
two-state "is it a fold?" test prints **REAL** for it and a page check prints ~3846/4096 so it is not
DARK either. **Only reading the instructions gets it right.**

**C4. `botspawn`'s recorded digest was STALE.** Its archived DLL was built ~17 h before HEAD.
Current: RAW **`b2203efd62161182`** / VSIZE `213e0010ed8fd003`. Anyone quoting
`e48c90bc6cf17c93` or `1a8fa5fe06f87019` is quoting a build that no longer reproduces.

**C5. A hardcoded offset that "agrees" with a by-name read is NOT corroboration if both can read
zero.** S138 flight 9 hardcoded `Velocity` at `CMC+0xE0`; the by-name resolve is **`+0xE8`**. The
conclusion survived (re-measured by name over 25 samples) but `docs/s138-f9-velocity.txt` carries a
wrong-offset column. **Resolve by name, or label the read unverified.**

**C6. `MovementMode` is a `TEnumAsByte`, i.e. a ByteProperty** — `FEnumProperty::Enum` (`*(+0x78)`)
does not apply and printing "enum unresolved" for it is EXPECTED, not a fault. Its value is
by-name-resolved at `CMC+0x231`; stock `EMovementMode` numbering is corroborated by CLAUDE.md's
`KFLYMODE=5 == MOVE_Flying`.

**C7. `ELivingState` (NOT `ELokiLivingState`, which occurs 0 times in the image):
`Dead=0, Alive=1, Knocked=2`.** ⚠ A *different* enum `EPlayerLivingState` also exists with
**`Alive=3`**, used by `ALokiPlayerState::GetLivingState` at `+0x3f8`. **Carrying "Alive==1" to a
PlayerState value is wrong by two.**

---

## 3. FLIGHT PROCEDURE — use the driver, it works

```powershell
# ELEVATED PowerShell. Steam must already be running.
cd "G:\git\Supervive Revival Project"
.\configs\s138-autostage.ps1 -MaxAttempts 6 -Label s139
```
It archives crash dumps, launches, waits for the settle gate, arms the `bots` queue, stages
(`gft → fo → sp`), **polls for `[SP] done step=4`**, and writes the PID/BASE to
`docs\s138-staged-pid.txt`. It injects **no** probe — staging stays decoupled from the injection
decision. Staged on attempt 1 in four of five uses.

⚠⚠ **THE DEFECT IT WAS BORN WITH, AND WHY THE POLL MATTERS.** Its first version tested the marker
for `done step=4` **immediately** after `fk24-stage.ps1` returned. But `stage complete` means
"finished INJECTING sp"; `sp` writes its receipt **12 s later** (measured). The check raced and
**`Stop-Process`'d three clients that had staged perfectly** — and I was one attempt from recording
that as a fourth consecutive FK-31 death, the exact p=0.005 threshold for calling FK-31 systematic.
**A completion message from a stage script means "I finished my step", not "the injected code
finished its work."** Gate on the payload's own receipt.

Then inject by hand into the staged client:
```
tools\inject\inject.exe mmap <PID> "G:\git\Supervive Revival Project\tools\sigbypass-mod\build\<dll>"
```

---

## 4. ARMS AND TOOLS

**Arms** (RAW digests; archived in `dumps/s138-arms-v3/` and `dumps/s138-arms-armf/`):

| arm | RAW | what |
|---|---|---|
| `driverecompute` | `a2a952babfed256b` | **ARM D + ARM F** — makes the bot, opens the gate |
| `driverecompute-ctrl` | `2a91f0aa7f3d521b` | ARM D only, ARM F compiled out — the control |
| `spawnbot_premade` | `6cb296bbf3c8c696` | ARM D + ARM E (SpawnBot premade path) |
| `spawnbot_readonly` | `64d55e27e5d99213` | same gates, call compiled out |
| `lokibot` | `e123816b65d68e5e` | ARM D only |
| `botspawn` | `b2203efd62161182` | BP route; **also decrypts `SpawnBot`'s page** (see §5) |
| **`botai`** | **`5e47c13cf7f0a158`** | **REGRESSION GATE — unchanged across every S138 patch** |

**New tools this session, all read-only unless noted:**

| tool | what |
|---|---|
| `tools/re/livingstate_sweep.py` | every `LokiCharacter`-chain object's `LivingState` + the live enum |
| `tools/re/movementmode_readout.py` | bot vs player CMC: mode, gravity, velocity, UpdatedComponent |
| `tools/re/motion_watch.py` | **polls until the bot appears, then tight-samples the motion chain** |
| `tools/re/livingstate_poke.py` | ⚠ WRITES one byte (`pawn+0x1090`), A-B-A + controls |
| `tools/re/flymode_poke.py` | ⚠ WRITES one byte (`CMC+0x231`), A-B-A + controls |
| `configs/s138-autostage.ps1` | the retry driver above |

★ **`motion_watch.py` embodies the ordering lesson: start the reader BEFORE the injection.**
Flight 7 reached the interesting state and lost it because it polled afterwards; flight 8 caught
194 samples over 97 s by having the watcher already running.

---

## 5. TRAPS

1. ⚠⚠ **`SpawnBot 0x556D910` is `PAGE_NOACCESS` in a live process until it has EXECUTED.** The
   protector demand-decrypts `.text` on **execute**; a READ can never trigger it. `merged12`/`merged13`
   grading it "LIT" is a UNION across processes, not a live state. **To read a never-executed
   function live, first drive any path that calls it** — injecting `botspawn` decrypts it (6/6
   pre-registered predictions, twice).
2. ⚠ **Wait for `[BS] done` before reading `called=` / census fields.** S138 flight 7's client died
   during the post-call census; ARM F's own sequential lines were still valid, but the summary was
   not. Know which half you are quoting.
3. ⚠ **Every injection truncates `docs/tutorial-launch-marker.txt`** (FK-25). Snapshot after each.
4. ⚠ **A verdict line can lie.** `livingstate_poke.py` printed `P3 … : YES` from a predicate whose
   terms were all always-true, while its own samples showed the opposite. **Read the samples, not
   the verdict** — and compute verdicts from observed data (both poke tools now do).
5. ⚠ **External `WriteProcessMemory` is UNRESOLVED as a hazard.** S138 used it for the first time in
   this project. The client died ~44 s later with the FK-32 signature, but that is confounded by a
   very high base rate and n=1. Settling it needs a matched no-write sitting compared on
   time-to-death. **Do not assume it is safe; do not assume it killed anything.**
6. ⚠ **Expect FK-32.** Every S137/S138 sitting ended in a silent `0x0000DEAD` kill after 4–7
   manual-maps. **Capture every result as you go**; do not batch reads to the end.

---

## 6. ARTIFACTS

| path | what |
|---|---|
| `docs/s138-flight9b-flymode-refuted.md` | **latest** — `MOVE_Flying` refuted, the `+0xE0`/`+0xE8` correction |
| `docs/s138-flight9-movement-not-simulating.md` | bot and player both `MOVE_Falling`, velocity zero |
| `docs/s138-flight8-the-bot-thinks.md` | **the AI runs end to end** — 194 samples |
| `docs/s138-flight7-recompute-drives-the-gate.md` | ARM F opens the gate |
| `docs/s138-flight6-livingstate-poke.md` | the byte pokes; the gate does not follow |
| `docs/s138-livingstate-writers-settled.md` | **nothing writes Alive; the bridge is a void fold** |
| `docs/s138-livingstate-sweep-settled.md` | every character is Dead |
| `docs/s138-flight3-divert-settled.md` | the `SpawnBot` divert = `0x556DE6A` |
| `docs/s138-flight2-arme-fired.md` | ARM E fired; **its §2b CORRECTIONS block governs** |
| `docs/s138-offline-followup.md` | FK-31 corpus (6 eras); TeamStates closed |
| `docs/s138-latch-fix-rebuild.md` | the `strstr` latch fix + the dedupe fix, with digests |
| `docs/s138-f*-PREREGISTERED.txt` | seven pre-registrations, all unedited |

**Uncommitted:** `tools/sigbypass-mod/tutorial_launch.cpp` (ARM F + both latch fixes) and
`tools/sigbypass-mod/build.ps1` (the two `driverecompute` variants). Nothing has been committed this
session — commit or discard deliberately.

---

## 7. SCOPE — say this correctly

⛔ **There is no working bot, and nothing here is a shipping fix.** `ServerSetHeroClass`
(`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam` (`0x556DE53 → 0xF7EB60`) are stripped folds; the bot has
no hero class and no team. Everything above requires pokes the game never performs by itself —
`LivingState` still has no writer that sets Alive. ARM F writes `+0x6A0` and touches the Blackboard;
it is **not call-only** and must never enter the default shim set.

Say: *"an `ALokiBotController` exists, possesses a hero pawn, has a PlayerState, runs its behaviour
tree, and produces movement input — which nothing consumes."* Never *"the bot works."*
