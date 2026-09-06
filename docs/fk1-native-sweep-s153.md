# FK-1 native-UFunction sweep — 303 stripped stubs identified offline (S153, 2026-09-02)

Third and broadest sweep in the S153 offline FK-1 work.

| sweep | source | scope | STRIPPED found |
|---|---|---|---|
| S152 batch hunt | live process (`GUObjectArray`) | 624–746 UFunctions matching `Auth*|Server*|Grant*|Kick*|Ban*|Force*|Debug*|Broadcast*|Init*|*Cheat*` | 95 |
| S153 exec sweep | `exec_chain_grade.txt` (offline) | 142 `FUNC_Exec` UFunctions on the `UPlayer::Exec` chain | 32 |
| **S153 native sweep (THIS)** | `dumps/merged14.dump.exe` + `fk13natreg` (offline) | **15,129 native UFunctions across 1,514 classes** — every UHT-registered native | **303 across 66 distinct thunk RVAs** |

## Methodology

Enumerate every native UFunction via `tools/re/fk13natreg.py`, which walks each
class's `StaticRegisterNatives<Class>` array in `.data` (populated at startup,
preserved in `dumps/tutorial-hero` — the fk13img default seed). For each
(class, name, thunk_rva) triple, grade the thunk against `.text` bytes in
`dumps/merged14.dump.exe` (best `.text` coverage available: 16,816 pages =
55.53%).

**Classifier** (`scratchpad/s153_native_ufunction_sweep.py`, capstone-based):

- **DARK**: thunk's page all-zero in `merged14` (never demand-decrypted).
- **STRIPPED**: thunk body is either (a) a fold prologue (`c2 00 00`, `33 c0 c3`, etc.),
  (b) a 5-byte JMP trampoline (`E9 <rel32>`) whose ultimate target is a fold, or
  (c) a wrapper-hides-stub pattern — a real MSVC prologue whose tail dispatch
  (`call <fold>` or tail-`jmp <fold>`) targets a known fold. Capstone walks
  instructions properly, so internal branches (like `AuthCheatSetHealth`'s
  `jmp 0x52FD673` at wrapper+0x35) don't terminate the walk — only genuine
  tail-jmps (target outside the wrapper's byte range) or `ret` end it.
- **REAL**: none of the above.

**Two mandatory positive controls** before any verdict emits:
- `ULokiAbilitySystemComponent::AdjustHealth` wrapper `0x5294270` must grade REAL
- `ALokiCharacter::AuthCheatSetHealth` wrapper `0x52FD620` must grade STRIPPED
  (via tail-call to `0x0F7EC20` fold, S152's 5th FK-1 register entry)

Both controls passed; verdicts below emitted after that gate.

## Aggregate result

- **15,129 native UFunctions** enumerated across **1,514 classes** in **~14 seconds** offline.
- **303 STRIPPED (2.00%)** — the FK-1 candidates.
- 9,916 REAL (65.54%).
- 4,910 DARK (32.45%) — thunk on a demand-decrypt page; latent, could be REAL or STRIPPED.
- **66 distinct STRIPPED thunk RVAs** — many UFunctions ICF-fold onto shared thunks (e.g.
  92 UFunctions share `0x5254180`, 9 share `0x52FD620`).

The 2.00% strip rate over the FULL native population is close to (and independently
corroborates) the S131 lane-D image-wide empty-impl baseline of **3.16%**. This sweep
therefore represents the true FK-1 population, not an enrichment.

## Cross-reference vs prior FK-1 findings

**CLAUDE.md 5-entry FK-1 register:** 4/5 confirmed STRIPPED by this sweep; the 5th
(`ALokiGameMode::SpawnPlayer`) is not enumerated because `fk13natreg`'s
`registrar_of()` pattern doesn't match `ALokiGameMode`'s class-registration shape —
an instrument limitation, not a contradiction.

| register entry | this sweep |
|---|---|
| `ALokiGameMode::SpawnPlayer` `0x534C070` → `0x0F7EB50` | NOT enumerated (fk13natreg gap) |
| `ALokiPlayerState::AuthSetSpawnTeamLeader` `0x5254180` → `0x0F7EC20` | ✓ STRIPPED |
| `ALokiTeamState_TeamOnly::SetDropLeader` `0x2C2CE30` → `0x0F7EC20` | ✓ STRIPPED |
| `ALokiDropPlane::OverridePlaneLocations` `0x53372A0` → `0x0F7EC20` | ✓ STRIPPED |
| `ULokiCharacter::AuthCheatSetHealth` `0x52FD620` → `0x0F7EC20` | ✓ STRIPPED (corrects prefix: class is `A`LokiCharacter, not `U`LokiCharacter) |

**S152 batch hunt (95 STRIPPED):** every one this sweep enumerates and grades matches
S152's verdict (`InfiniteHealth`, `CheatExperience`, `TeleportAlly`, `AuthAnyVisible
EnemyHeroCharactersInRange`, `AuthAddPlayer`, `AuthBeginGlideDiveFromDropPod`, etc.
all confirmed).

**S153 exec sweep (32 STRIPPED):** disjoint surface (exec verbs vs the entire native
population); this sweep encompasses that set.

## Top classes by stripped count

The stripped set is heavily concentrated in specific class families:

| class | STRIPPED / total | notes |
|---|---|---|
| `ALokiPlayerState` | 36 / 130 (28%) | authority state mutations, stat writers |
| `ALokiCharacter` | 34 / 238 (14%) | full `InfiniteHealth`/`Teleport*`/`Cheat*` family + auth mutations |
| `ULokiTuningLibrary` | 29 / 29 (100%) | **entire class stripped** — dev-only tuning API |
| `ALokiBaseItem` | 14 / 167 (8%) | authority item mutations |
| `ALokiPlayerCheats` | 14 / 62 (23%) | dev cheat backend |
| `ALokiPlayerController` | 12 / 143 (8%) | client-side controller ops |
| `ULokiBlueprintLibrary` | 10 / 174 (6%) | includes `CheatsEnabled` (measured HARDCODED FALSE) |
| `ULokiReferenceGraph` | 10 / 11 (91%) | dev graph tool, near-fully stripped |
| `ALokiHeroCharacter` | 8 / 65 (12%) | hero-specific auth ops |
| `ALokiMinionCharacter` | 8 / 70 (11%) | **includes WALL E hostility mechanism** (`AuthAnyVisibleEnemyHeroCharactersInRange`, etc.) |
| `ALokiProjectile` | 7 / 56 (13%) | |
| `ALokiTower` | 7 / 17 (41%) | |
| `USkeletalMesh` | 6 / 30 (20%) | stock UE editor-only ops |
| `ULokiAbilitySystemComponent` | 5 / 69 (7%) | GAS authority mutations |
| `ULokiCharacterMovementComponent` | 5 / 43 (12%) | **includes `AuthBeginGlideDiveFromDropPod`** (S131 dismount block) |
| `ALokiDropPlane` | 5 / 21 (24%) | drop-plane authority — 4 of 5 shared with `ULokiRideableComponent` via ICF |
| `ULokiRideableComponent` | 4 / 18 (22%) | **rideable authority** (S131 mount block) — `AuthAddPlayer`, `AuthRemovePlayer`, `AuthSetCanJump`, `AuthPlayerEnterWorldNew` |
| `ALokiTeamState` | 4 / 74 (5%) | includes `SetDropLeader` (CLAUDE.md register entry) |
| `ALokiOpeningClosingProp` | 4 / 14 (29%) | |

Full data: `scratchpad/s153_native_ufunction_sweep.csv` (~15K rows) and
`scratchpad/s153_native_ufunction_sweep_stripped.txt` (STRIPPED-only, class-grouped).

## What this sweep changes about the FK-1 register

- **The register goes from 5 entries to a knowable ceiling of ~303 STRIPPED
  natives** (via fk13natreg's enumerable set). Every one of the 5 register
  entries that fk13natreg can see is confirmed STRIPPED — no register entries
  are contradicted.
- **The 4,910 DARK entries are potential FK-1 candidates awaiting demand-
  decryption.** A live sitting that fires any UFunction whose thunk sits on a
  currently-dark page will decrypt that page and unblock offline grading of
  every UFunction on it.
- **`ULokiTuningLibrary` and `ULokiReferenceGraph` are effectively 100%
  stripped** — dev/debug backends that shipped as empty stubs. Any shim design
  that plans to call one of these UFunctions is a wasted injection.
- **Rideable/DropPlane authority mutations remain the dominant WALL E and
  mount-chain blocker family** (S131). Nothing in this sweep changes that;
  it just widens the enumerated confirmation.

## What this does NOT establish

- **Not all native UFunctions are enumerated.** `fk13natreg.registrar_of()`
  uses a specific `<Class>::GetPrivateStaticClass` disassembly pattern; classes
  whose registration doesn't fit that pattern (like `ALokiGameMode`) are
  invisible to it. A separate instrument (e.g. UHT `FClassParams` static walker)
  would fill that gap.
- **The 4,910 DARK entries are not classified.** Some are REAL (bodies simply
  never executed), some are STRIPPED. Only demand-decryption via a live run
  would settle them.
- **The classifier can't detect stripped stubs whose fold isn't in the known
  5-fold set.** The 5 known folds (`0x0F7EC20`, `0x0F7EB50`, `0x0F7EB60`,
  `0x0B9E1F0`, `0x0FC6CF0`) cover every empty-impl seen in this project, but a
  hypothetical sixth fold shape would grade as REAL.
- **Nothing here is live-verified.** Every finding needs a call-and-observe
  pass on a running game before graduation to the FK-1 register.

## Instrument caveats (worth carrying forward)

- **A byte-scan for `E8`/`E9`/`C3` opcodes cannot detect stripped wrappers
  reliably.** Two failure modes hit during S153: (a) an early `E9` byte inside
  another instruction's data breaks the scan loop and steals `last_call`
  (`AuthBeginGlideDiveFromDropPod` false-REAL before capstone was added);
  (b) a real `jmp <fold>` tail-dispatch with no `call` at all is missed if the
  scan only tracks `E8` (the 92-way ICF-shared thunk `0x5254180` uses tail-jmp).
  **Use a proper instruction walker** (capstone or equivalent).
- **The scan window must be big enough to reach the tail call.** UHT wrappers
  for functions with many struct parameters can extend to ~300 bytes.
  `OverridePlaneLocations`'s tail call sits at wrapper+0xD8; a 128-byte window
  misclassified it as REAL. 1024 bytes (0x400) is comfortably above every
  wrapper size seen so far.
- **Distinguish internal branches from tail-jmps.** An unconditional `jmp`
  inside a wrapper is only a terminator if its target is OUTSIDE the wrapper's
  byte range. `AuthCheatSetHealth`'s `jmp 0x52FD673` at wrapper+0x35 is an
  internal if/else flow; treating it as a terminator misses the real tail call
  ~200 bytes later.
- **Sweep runtime is ~14 seconds** for the entire 15,129-UFunction population.
  This is offline, deterministic, and can be re-run after each `merged*.dump.exe`
  bump.

## v2 — closing the fk13natreg instrument gap (same session)

v1 above uses `fk13natreg`'s per-class walker, which requires each class to
have a `<Class>::GetPrivateStaticClass` shape that fk13natreg's disassembly
recognizes. That silently misses classes with a different registration
pattern. **CLAUDE.md's FK-1 register entry #1 (`ALokiGameMode::SpawnPlayer`,
thunk `0x534C070`, impl `0x0F7EB50`) was not in v1's output for this reason.**

**v2 replaces the enumerator with `tools/re/exec_chain_grade.py`'s
DATA-DIRECTED `FNameNativePtrPair` scanner.** Instead of walking per-class
registration functions, it scans all of `.data` + `.rdata` for consecutive
`{name*, thunk*}` pairs at 8-byte stride (filtering out `FClassFunctionLink
Info` phase-shift collisions via a ctor-call discriminator), groups into
constant-stride runs (16/24/32/48/72 bytes), and assigns runs to classes
via name-set overlap against `uht_funcflags_tuthero.csv`. It finds
**17,892 raw pairs → 16,490 (class, func) → thunk keys** — 1,596 more
UFunctions than v1's fk13natreg-based enumeration.

### v2 aggregate

- **16,490 native UFunctions** enumerated across a broader set of classes.
- **318 STRIPPED (1.93%)** — up from v1's 303.
- 11,105 REAL (67.34%).
- 5,067 DARK (30.73%).
- **+1,596 new entries** fk13natreg missed, of which **17 STRIPPED** are novel
  additions to the FK-1 map.

### FK-1 register — v2 covers all 5

| register entry | v1 (fk13natreg) | v2 (exec_chain_grade) |
|---|---|---|
| `ALokiGameMode::SpawnPlayer` `0x534C070` → `0x0F7EB50` | NOT enumerated | ✓ STRIPPED |
| `ALokiPlayerState::AuthSetSpawnTeamLeader` | ✓ STRIPPED | ✓ STRIPPED |
| `ALokiTeamState_TeamOnly::SetDropLeader` | ✓ STRIPPED | ✓ STRIPPED |
| `ALokiDropPlane::OverridePlaneLocations` | ✓ STRIPPED | ✓ STRIPPED |
| `ALokiCharacter::AuthCheatSetHealth` | ✓ STRIPPED | ✓ STRIPPED |

### 17 NEW STRIPPED entries (fk13natreg missed)

**`ALokiGameMode` — 7 stripped** (fk13natreg enumerated 0):
- `SpawnPlayer` `0x534C070` → `0x0F7EB50` (register #1)
- `CheatCantEndGame` `0x52FD980` → `0x0F7EB60` (LokiIsServer FALSE)
- `DevGameModeCheatsEnabled` `0x51629C0` → `0x0F7EB60`
- `EliminateTeam` `0x5349CB0` → `0x0F7EC20`
- `GameModeCheat` `0x5349DC0` → `0x0F7EC20`
- `GetAutomaticRespawnTimerAdditionalTime` `0x5349FB0` → `0x0FC6CF0` (0.0f)
- `TickAFKChecking` `0x5254180` → `0x0F7EC20`

**`ULokiSpellSwapper` — 5 stripped** (fk13natreg enumerated 0):
- `AddSubSpell`, `NextSpell`, `PreviousSpell`, `RemoveSubSpell`, `SwitchSpell`
  — the entire spell-swap subsystem is gutted.

**`ULokiGameplaySpell` — 2 stripped**:
- `CallSpellCompleteEvent`, `SimulateInputReleasedForAI`

**`ALandscapeProxy` — 3 stripped** (stock UE editor cheats, not gameplay-relevant):
- `EditorApplySpline`, `EditorSetLandscapeMaterial`, `LandscapeExportHeightmapToRenderTarget`

### Classifier: an additional defect fix

v2's classifier also fixed a subtle wrapper-classification bug uncovered by
`SpawnPlayer`. The v1 heuristic was "last E8 call before ret is the impl",
but MSVC inserts `call __security_check_cookie` before `ret` when the
wrapper has a stack cookie. SpawnPlayer's wrapper had:
- `+0x1B8 call 0x0F7EB50` (fold — the real semantic tail)
- `+0x1CB call 0x751DEB0` (`__security_check_cookie`, compiler bookkeeping)
- `+0x1DD ret`

v1 picked the cookie check as `last_call` and graded REAL. **Fix: define
`IGNORED_TAIL_TARGETS = {0x751DEB0}`** (identified by disassembling that
target: canonical `cmp rcx, [__security_cookie]; jne fail; rol rcx, 0x10;
test cx, 0xffff; jne fail; ret`) and skip it when picking `last_call`.
Alternative "any fold call anywhere in body wins" was rejected because it
false-positives on real functions that legitimately consume fold results
(e.g. `if (LokiIsClient()) ...`).

### 83 classes fk13natreg missed ENTIRELY

Most are stock UE (`AActor` 126 natives, `APlayerController` 163,
`UPrimitiveComponent` 150, `USkeletalMeshComponent` 105, etc.) — irrelevant
for FK-1 hunting but worth having in the census. **The Loki-relevant misses:**
- `ALokiGameMode` — 68 natives, 7 stripped
- `ULokiGameplaySpell` — 72 natives, 2 stripped
- `ULokiSpellSwapper` — most stripped
- `ALokiScoreboardRow` — 50 natives, 0 stripped
- `ALandscapeProxy` — 10 natives, 3 stripped (editor-only)

### Files (v2)

- `scratchpad/s153_native_ufunction_sweep_v2.py` — the improved sweep tool
- `scratchpad/s153_native_ufunction_sweep_v2.csv` — 16,490 rows, `new_vs_v1` column marks fk13natreg-missed entries
- `scratchpad/s153_native_ufunction_sweep_v2_delta.txt` — 83 missed classes + 17 new stripped entries, class-grouped
- `scratchpad/s153_native_ufunction_sweep_v2.out.txt` — full stdout

## Files

- `scratchpad/s153_native_ufunction_sweep.py` — the sweep tool
- `scratchpad/s153_native_ufunction_sweep.csv` — every native UFunction with verdict
- `scratchpad/s153_native_ufunction_sweep_stripped.txt` — STRIPPED-only, class-grouped
- `tools/re/fk13natreg.py` — the class enumeration API (`natives(class_name)`)
- `tools/re/fk13uht.py` — the class registration scanner (`UHT().scan_class_registrations()`)
- `tools/re/exec_chain_grade.py` — v2's enumerator source (`scan_native_pairs`, `build_thunk_map`)
- `dumps/merged14.dump.exe` — the `.text` source
- `dumps/tutorial-hero/…` — the `.data` source (native-registration arrays)
- `docs/fk1-exec-sweep-s153.md` — the earlier S153 exec-verb sweep (32 STRIPPED)
- `docs/fk1-batch-hunt-s152.md` — S152's live batch hunt (95 STRIPPED)
