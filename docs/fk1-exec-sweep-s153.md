# FK-1 exec-verb sweep — 32 stripped stubs identified offline (S153, 2026-09-02)

Companion to [S152's FK-1 batch hunt](fk1-batch-hunt-s152.md). This is a
**different surface** and a **different instrument**:

| | S152 batch hunt | S153 exec sweep |
|---|---|---|
| Source | live process (`GUObjectArray` walk) | `merged14.dump.exe` (pre-generated `tools/re/out/exec_chain_grade.txt`) |
| Requires | running game with FK-1 candidates loaded | nothing — the game is dead |
| Scope | 624–746 UFunctions by name pattern (`Auth*|Server*|…`) | all 142 `FUNC_Exec` UFunctions reachable from `UPlayer::Exec`'s chain |
| Method | body disassembly, tail-call to fold | thunk→impl resolution, impl compared against known folds |
| Confirmations | 95 STRIPPED (13.3%) | **32 STRIPPED (22.5%)** |
| Overlap with S152 | — | ≈0 (S152 hit `Auth*/Server*/*Cheat*` on ASCs & rideables; this hits `FUNC_Exec` on cheat managers) |

## Aggregate (142 exec verbs across 16 classes)

| verdict | count | means |
|---|---|---|
| REAL | 82 | thunk resolves to a real body |
| SMALL-REAL | 10 | small real body (usually a stock helper) |
| **FOLDED-STUB** | **32** | thunk resolves to a known fold — the FK-1 candidates |
| COVERAGE-BLOCKED | 18 | page never demand-decrypted in the source dump |

Combined REAL-family surface: 92/142 = 65% callable. Combined stripped: 32/142 =
22.5%, which is **7× the image-wide 3.16% empty-impl base rate** (S131 lane D).
The enrichment is not on subsystem; it's on **verb semantics** — every stripped
exec verb is either a cheat command, a debug/timeline manipulator, an authority
mutator, or a stock UE `Toggle*Debug*` helper.

## Cross-reference vs CLAUDE.md's FK-1 register

None of the FK-1 register's 5 entries (`SpawnPlayer`, `AuthSetSpawnTeamLeader`,
`SetDropLeader`, `OverridePlaneLocations`, `AuthCheatSetHealth`) appear on the
`FUNC_Exec` surface — they're authority-only network functions and reflected
natives, not exec verbs. ⇒ **all 32 finds below are disjoint from the register.**

⚠ `AuthCheatSetHealth` (S152's 5th FK-1 entry, Func RVA `0x52FD620`) is
independently corroborated at this surface: `exec_chain_grade.txt` lines 72/75
identify Func RVA `0x52FD620` as a **9-way ICF-shared** stripped thunk with two
of the finds below (`DebugTimelineAdvanceTime`, `DebugTimelineSetTime`). Spot-
check on `dumps/merged14.dump.exe`: bytes at Func+0x6F decode as
`E8 <rel32> → 0x0F7EC20` (universal void_ret fold) — matches S152's live
measurement exactly. `AuthCheatSetHealth` is one of the 9 ICF-shared functions
on this thunk; the other 8 are not enumerated in the grade output.

## The 32 stripped exec verbs

All 32 tail-call the same fold: **`0x0F7EC20` = `c2 00 00 = ret 0`** (universal
void_ret). None was previously in the FK-1 register.

### ALokiCharacter (8 stripped / 10 total = 80%)
`CheatExperience` · `InfiniteHealth` · `InfiniteMana` · `InfiniteStamina` ·
`ResetCooldowns` · `TeleportAlly` · `TeleportEnemy` · `TeleportNear`
(all thunk `0x5254180`, the **92-way ICF-shared** thunk documented in CLAUDE.md
FK-1 §2. Note the count: it was 91-way as of S131, now 92-way — one more
UFunction has been recognized on the shared thunk since.)

### ALokiPlayerCheats (6 stripped / 25 total = 24%)
`CheatAddMissionProgress` (thunk `0x5421d60`) ·
`CheatSetRankedPoints` (thunk `0x52fd8f0`) ·
`CheatSetXP` (thunk `0x52fd8f0`) ·
`CheatTravelToMainMenu` (thunk `0x5254180`, 92-way ICF) ·
`LogActorsAtWorldOrigin` (thunk `0x5254180`, 92-way ICF) ·
`LogActorsInRadiusNear` (thunk `0x5425800`)

### ALokiPlayerController (5 stripped / 8 total = 62%)
`DebugTimelineAdvanceTime` (thunk `0x52fd620`, 9-way ICF — shares with
`AuthCheatSetHealth`) ·
`DebugTimelineSetTime` (same thunk) ·
`ResetObjects` (thunk `0x5254180`, 92-way ICF) ·
`SendGameplayTagsReport` (same) ·
`SendNetStat` (same)

### ULokiTimelineManager (3 stripped / 5 total = 60%)
`DebugTimelineReset` · `DebugTimelineResetAndPause` · `DebugTimelineResume`
(all thunk `0x5254180`, 92-way ICF)

### UCheatManager (3 stripped / 50 total = 6%)
`TestCollisionDistance` (thunk `0x35ca5b0`) ·
`ToggleAILogging` (thunk `0x33aac90`, 2-way ICF) ·
`ToggleDebugCamera` (thunk `0x35ca5d0`)

### UGameInstance (2 stripped / 2 total = 100%)
`DebugCreatePlayer` (thunk `0x3801f60`) ·
`DebugRemovePlayer` (thunk `0x3801ff0`)

### UGameViewportClient (2 stripped / 3 total = 67%)
`SSSwapControllers` (thunk `0x326d280`) ·
`SetConsoleTarget` (thunk `0x3873640`)

### UAbilitySystemGlobals (2 stripped / 2 total = 100%)
`ToggleIgnoreAbilitySystemCooldowns` (thunk `0x35c7fd0`) ·
`ToggleIgnoreAbilitySystemCosts` (thunk `0x33ac230`)

### APlayerController (1 stripped / 14 total = 7%)
`SendToConsole` (thunk `0x3c652d0`)

## Corollary: Route B (constructing a live `UCheatManager`) is largely productive

CLAUDE.md's FK-13 block records Route B as shipped and proven at S114 —
constructing a `UCheatManager` via `UGameplayStatics::SpawnObject(pc->CheatClass,
pc)` and dispatching verbs through it. **UCheatManager's own breakdown** (from
this sweep, 50 exec verbs):

| verdict | count |
|---|---|
| REAL | 41 |
| SMALL-REAL | 3 |
| FOLDED-STUB | **3** |
| COVERAGE-BLOCKED | 3 |

**⇒ 44/50 = 88% of UCheatManager verbs REACH real bodies.** The 3 stripped are
`TestCollisionDistance`, `ToggleAILogging`, `ToggleDebugCamera` (unsurprising —
debug camera and AI-logging cheats are the standard set stripped in shipping).
This corroborates FK-13's `LogLoc` proof and extends it: Route B is a viable
channel for the whole `BugItGo`/`DamageTarget`/`Fly`/`Ghost`/`God`/`Slomo`/
`Summon`/`Teleport`/`Walk` family — 41 verbs' worth of behaviour.

## Corollary: Loki cheat surface (`ALokiCharacter`, `ALokiPlayerCheats`, `ALokiPlayerController`) is heavily stripped

Not a symmetric situation. Route B reaches `UCheatManager` verbs, but the
**Loki-specific** cheat verbs (which would be under a `ULokiClientPlayerCheats`
attachment) show much higher strip rates:

| class | REAL | STRIPPED | COVERAGE-BLOCKED | strip rate |
|---|---|---|---|---|
| UCheatManager | 41+3 | 3 | 3 | 6% |
| ULokiClientPlayerCheats | 5 | 0 | 0 | 0% (all 5 real, but the class is small) |
| ALokiPlayerCheats | 7 | 6 | 8 | 24% (STRIPPED / total gradeable = 6/13) |
| ALokiPlayerController | 1 | 5 | 1 | 62% |
| ALokiCharacter | 0 | 8 | 2 | 80% |

⇒ a shim that spawns `ULokiClientPlayerCheats` (5/5 REAL) or `ALokiPlayerCheats`
(7/25 REAL, 6 stripped, 8 dark) can unlock *some* Loki cheats but not the
`ALokiCharacter`-side verbs (`InfiniteHealth`, `InfiniteMana`, `Teleport*`,
etc.), which are all stripped. That family would need a different (data-poke)
approach.

⚠ `ULokiClientPlayerCheats` (5/5 REAL) is the highest-yield Loki cheat surface
in this sweep. Its verbs are not enumerated in the grade output body above —
they live under the `=== ULokiClientPlayerCheats (5 exec)` section of
`tools/re/out/exec_chain_grade.txt`.

## Zero-launch verification

This sweep required no launch, no injection, and no live process. The
underlying grade file was produced during S114 (FK-13, lane 3), and the
classification is stable — the input dump (`merged14.dump.exe`) hasn't
changed since S137, and the fold addresses (`0x0F7EC20`, `0x0F7EB50`,
`0x0F7EB60`, `0x0FC6CF0`, `0x0B9E1F0`) are compile-time constants.

Spot-check performed against `dumps/merged14.dump.exe` on 2026-09-02:
- `ALokiCharacter::InfiniteHealth` thunk `0x5254180`: bytes `48 8b 42 20 45 33
  c0 48 85 c0 41 0f 95 c0 4c 03` = the 92-way ICF-shared exec thunk shape ✓
- Fold `0x0F7EC20`: bytes `c2 00 00` = `ret 0` ✓
- `AuthCheatSetHealth` thunk `0x52FD620` +0x6F: `E8 <rel32>` decoding to
  `0x0F7EC20` — matches S152's live measurement exactly ✓

## What this does NOT establish

- **These are not the whole FK-1 population.** This sweep only covers the
  `FUNC_Exec` surface. The 5 CLAUDE.md-register FK-1 stubs are all
  `FUNC_Net*`/`FUNC_BlueprintCallable` and are absent from this list. S152's
  95-stub batch hunt was on `Auth*|Server*|Grant*|Kick*|Ban*|Force*|Debug*|
  Broadcast*|Init*|*Cheat*` name patterns — mostly disjoint from this again.
- **COVERAGE-BLOCKED entries could go either way.** The 18 dark entries here
  are unclassified — some may be REAL, some STRIPPED. A live session that
  drove those verbs would demand-decrypt their pages.
- **The 92-way ICF-shared thunk is not itself an impl.** It's the packed
  exec-wrapper prologue that unpacks FFrame args, then tail-calls the fold.
  This is exactly the S152 wrapper-hides-stub trap: a naive prologue check
  would grade it REAL. Only full-body disassembly to the tail call catches it.

## Instrument caveats worth carrying forward

- The grade file's `[thunk ICF-shared by N fns]` annotation is a **REVERSE
  count** — how many UFunctions share this thunk RVA. It does not enumerate
  them by name. To recover the other 6 UFunctions sharing `0x52fd620` with
  `AuthCheatSetHealth`/`DebugTimeline*`, walk `GUObjectArray` in a live
  process and filter by Func RVA (S152's batch-hunt tool template).
- The **92-way** count is one higher than CLAUDE.md's recorded **91-way**
  as of S131 — one more UFunction landed on the shared thunk since. Not
  material to any conclusion but worth noting: FK-1 register counts drift
  as tooling improves.
- The grade file uses `SMALL-REAL` for impls under a certain byte threshold
  where the tool can't confidently distinguish "real but tiny" from
  "unusual stub shape". Treat as REAL for FK-1 purposes; the S152
  wrapper-hides-stub trap doesn't apply here (a stripped stub always
  tail-calls a fold at a specific offset).

## Coverage re-grade of the 18 COVERAGE-BLOCKED entries (same session, offline)

The 18 COVERAGE-BLOCKED verdicts in `exec_chain_grade.txt` were computed against
`dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe` (S114 baseline). Since
then coverage has advanced through `merged13` (S137) and `merged14` (S152 +14
pages). Re-grading offline against `merged14`:

**Tool:** `scratchpad/s153_coverage_regrade.py` (read-only file-byte reader; two
mandatory positive controls — `UCheatManager::God` impl must classify REAL and
the known fold `0x0F7EC20` must classify FOLDED-STUB before any verdict emits).
Chases one level of `E9 <rel32>` JMP trampoline (which UHT/MSVC emits for
ICF-folded stubs) so a jmp-to-real-body doesn't misclassify as COVERAGE-BLOCKED
because the trampoline itself sits on a dark page.

**Result: 17/18 STILL-DARK, 1 REAL — and the 1 REAL is an instrument-limitation
finding, NOT a coverage gain.**

| entry | outcome | why |
|---|---|---|
| `ALokiPlayerCheats::SetGamepadAimSettings` | **REAL** | impl `0x55653E0` is a 5-byte `E9 <rel32>` JMP trampoline → `0x338C990`; page `0x5565000` (trampoline) went DARK→LIT via S137's side effect; page `0x338C000` (real body) was **already lit in tutorial-hero (3818/4096)**. exec_chain_grade doesn't chase JMP trampolines, so this verdict was COVERAGE-BLOCKED under S114's baseline for an instrument reason, not a coverage reason. Grade in the S114 baseline should be REAL. |
| 17 others | STILL-DARK | pages listed below still all-zero in `merged14` |

⚠ **The REAL promotion may have an ICF-attribution overlap.** `docs/fk22-drop
phase-reachability.md` designates `0x55653E0` as `ALokiGameState::AuthSetDeathCircle`'s
impl (FK-22 negative control until S137's side effect broke it). Both
`SetGamepadAimSettings` and `AuthSetDeathCircle` appear to resolve to
`0x55653E0` — either ICF has folded two disparate functions onto one JMP
trampoline (both then land at `0x338C990`), or one of the two tool
attributions is wrong. Not settled here; noted so a successor doesn't take
either attribution as ground truth without a second instrument.

**Instrument-limitation rule for exec_chain_grade:** its `impl RVA` field is
the tail-call target in the exec thunk, which for ICF-folded impls may be a
JMP trampoline sitting on a page that hasn't been demand-decrypted. A
COVERAGE-BLOCKED verdict on such an entry describes the trampoline's
page, not the real body's — the real body may be readable elsewhere.
Chase `E9 <rel32>` one level before believing a COVERAGE-BLOCKED verdict.

### The 7 distinct pages that gate the remaining 17

Any live session that FIRES one verb whose thunk sits on a page decrypts the
whole page and unblocks every verb on it (S118's "driving a path decrypts it"
method).

| page | # verbs | side | verbs |
|---|---|---|---|
| `0x05422000` | **6** | mixed | `ALokiPlayerCheats::CheatGetAllClientActorsByClassName`, `CheatMeasureCursor`, `CheatMuteAudio`, `CheatNoCooldowns`, `CheatSetEmote`, `CheatTeleportLocation` |
| `0x035C5000` | 3 | impl | `UCheatManager::ViewActor`, `ViewClass`, `ViewPlayer` |
| `0x0534B000` | 2 | thunk | `ALokiPlayerController::ServerDebugEnsureAllowRepeat`, `ALokiPlayerCheats::CheatChangeHero` (same ICF-shared thunk `0x534BE80`) |
| `0x052FE000` | 2 | thunk | `ALokiCharacter::CheatToggleCharacterDebugMode`, `DebugStatString` |
| `0x05483000` | 2 | thunk | `ULokiTimelineManager::DebugTimelineAddEvent`, `DebugTimelinePrintEvents` |
| `0x038AB000` | 1 | thunk | `AHUD::PreviousDebugTarget` |
| `0x03F44000` | 1 | thunk | `UPlayerInput::SetBind` (⚠ likely inert anyway — CLAUDE.md's FK-13 block records `DebugExecBindings` as never evaluated) |

### Highest-value target (offline):

If a live session eventually fires one Route B verb on the `ALokiPlayerCheats` carrier, it
would decrypt page `0x05422000` and expose the 6 `Cheat*` verbs on it for classification. That is
the highest single-page yield of any target in this table. Once decrypted, those
6 impls can be re-graded offline without any further live work.

### What this does NOT establish

- **The re-grade tells us nothing about the 17 STILL-DARK entries' actual
  status** — they could all be REAL, all STRIPPED, or any mix. No verdict
  is currently supportable for them.
- **The 1 REAL promotion may or may not correctly attribute the body to
  `SetGamepadAimSettings`** — see the ICF-attribution overlap note above.
- **The tool caveats are new to this project's record.** Two of them:
  (1) exec_chain_grade doesn't chase JMP trampolines and can misclassify
  ICF-folded targets as COVERAGE-BLOCKED; (2) a "COVERAGE-BLOCKED" entry
  with a resolved impl RVA is a statement about that one page, not about
  the underlying function — the underlying function may be reachable via
  a different route (a different call site with a different resolved impl).

## Files

- `tools/re/out/exec_chain_grade.txt` — the source data (S114, FK-13 lane 3)
- `dumps/merged14.dump.exe` — the underlying image
- `scratchpad/s153_coverage_regrade.py` — the re-grade tool (read-only, offline)
- `scratchpad/s153_coverage_regrade.out.txt` — this session's output
- CLAUDE.md FK-1 register — the 5 existing entries this sweep complements
- `docs/fk1-batch-hunt-s152.md` — the companion sweep on a different surface
