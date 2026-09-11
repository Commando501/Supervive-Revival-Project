# Sessions 83–84 — PASSES brought fully online; DS hero route re-scoped

Date: 2026-07-18/19. Branch: `dedicated-server-stub`.
Deep detail: `session-83-passes-tier-grid-solved.txt`, `session-84-hero-mirror-scope.txt`.

---

## 1. PASSES / Hunter's Journey — SOLVED end to end (S83)

The PASSES section went from an empty screen with a 15/s endpoint tight-loop to a fully rendering
account pass with live progress. Three separate problems, each with a different root cause.

### 1a. The tier grid — a VM MAP-KEY MISMATCH
`CheckAccountPassChanges` (`0x5794480`) finds the view model by
`P->GetPrimaryAssetId()` (vtbl **+0x1D0**) → `ToString` (`0x12F4230`) → `FindVM` (`0x57AB180`),
i.e. it looks for **`ProgressionTrack:HuntersJourney`**. Our shim keyed the VM by the track's
`ProgressionTrackID` = bare `HuntersJourney`, so the find missed and the populate was skipped.
**Fix:** resolve that key at runtime and adopt with `ProgressionTrackID = K`. A TMap find HASHES the
key, so patching the stored string in place does NOT work — the game must INSERT under the right key.
Once keyed correctly the game populated everything itself: `LevelsToDisplay` 0→85, `Levels` 0→**86**.

**Two traps recorded, both of which cost live runs:**
* `VM.Levels`(+0xC8) is `TArray<UObject*>`, NOT `TArray<FPrimaryAssetId>` (usmap/older notes were
  wrong). Elements are per-reward `BP_BattlepassLevelViewModel_<Kind>_C` objects, tier XP at +0x338.
  The populate **constructs** objects ⇒ **never force-call `0x57DF4B0`** (that was the S82 crash).
* The old note "P = S[+0x238]" is WRONG. Live: `0x562BC70` → LokiAssetLoader, `0x562BED0` → **P =
  `HuntersJourney_C` itself**. `S[+0x238]` is a red herring that cost a shim iteration.

Bonus: the `<MISSING STRING TABLE ENTRY>` header fixed ITSELF — the widget keys `<VM.ID>-header`, so
the corrected ID resolved it.

### 1b. Progress — PURELY FROM THE BACKEND (kills "the backend route is exhausted")
`GET /progression/players/{id}` served as a strict SUPERSET (existing AccelByte envelope untouched,
three keys ADDED) makes the native ingester `0x585A570` adopt:

```json
{ "...existing data/paging/total...",
  "ID": "<playerId>", "Version": <monotonic>,
  "AccountPass": { "Level": 12, "XP": 1500, "Cleared": false } }
```

Field names RECOVERED from live UStruct reflection (`FPlayerProgression` 0x178 /
`FProgressionTrackLevel` 0x60), not invented. **OMIT** `Matches`/`MissionInfo`/`HeroMastery`/
`LoginReward`/`EventProgression`/`UnclaimedRewards` — a MATCHED key with a wrong CONTAINER type
rejects the WHOLE document and looks identical to "no effect".

**`Version` is load-bearing** (gate is a strict `jle`). Two traps, both hit: a CONSTANT adopts once
then is ignored forever on the ~61s poll; and a process-local counter RESETS on an ags restart while
the client's adopted value SURVIVES, silently dropping every later change. Fix: bump only on content
change, seeded from `time.Now().Unix()`.

**⚠ "Gate C" (`byte[PM+0x388]`) was NEVER a gate** and poking it is HARMFUL — it is
`TOptional::bIsSet` for the struct at `PM+0x210`; setting it by hand disarms a guard so the next
ingest runs `~FPlayerProgression` over 288 bytes of raw zeros. The populate always ran; it was fed
zeros. The ingester sets that byte itself, correctly.

### 1c. Admin + gameplay wiring
* Per-account `AccountPass{Level,XP,Cleared}` persisted in `state/interactive.json`;
  `GET/PUT 127.0.0.1:9210/api/progression/{id}`; editor block + player-list column in the GUI.
  Live round-trip: PUT tier 34 → client adopted ~22s later, `requiredXP` recomputed to 41000.
* Pass XP is EARNED from match results (`interactive/passxp.go`). **The SERVER must own levelling** —
  the client only draws a bar and never advances a tier — so passxp.go carries the 85-value XP ladder
  dumped from the live CDO and verified against the client's own `requiredXP` at tiers 0/12/34.
  **The ladder is NON-MONOTONIC** (dips at 20/30/40/55), so levelling subtracts tier by tier; there is
  no closed form. Credit goes to the Bearer-token subject on the real path; ambiguous cases are
  SKIPPED, not guessed. 10 tests in `passxp_test.go`.

### 1d. Seasonal — tested and PARKED
Adopting a 2nd track with `bIsSeasonalPass` DOES build `SeasonalPassViewModel`, but **no seasonal tab
appears** ⇒ tab visibility is NOT gated on that VM. And a seasonal ladder is structurally impossible
on that path (the non-account branch's copier `0x57B9C00` zeroes Levels and never calls Init
`0x57BB560`). Shim default `kArmSeasonal=false`. The real blocker is whatever drives the tab strip.

---

## 2. Dedicated-server hero route (S84) — re-scoped, two answers, one open loop

**Corrected S81's sizing.** "LokiCharacter ~182 props + CMC ~218 props, a LARGE multi-session
reconstruction" counted TOTAL properties. The `CPF_Net` subset is tiny:
`LokiCharacter` = 2 props + 14 RPCs (all debug/cosmetic); **`LokiCharacterMovementComponent` = 0 and
0** (movement rides `ACharacter`'s stock engine path). The mirror already existed from S73.

**Pinned `UClass::ClassFlags = +0xDC`** differentially (two offsets survived the abstract/concrete
filter; engine ground truth killed `+0xFC`, which calls `Controller`/`Info` concrete). Result:
`LokiCharacter` and `LokiHeroCharacter` are **ABSTRACT** (so the client can never instantiate a
replica — the S77 movement AV), **`LokiMinionCharacter` is CONCRETE** — the only possessable
Loki-typed character. Added `ALokiMinionCharacter` (3 props + 1 RPC) and wired the GameMode to it.

**LIVE RESULT — two real wins and one open loop:**
* ✅ **Server-side spawn + possess of a Loki-typed character SUCCEEDS** (`spawned + possessed
  ALokiMinionCharacter` + `Join succeeded`), twice.
* ✅ The `ClassFlags@+0xDC` derivation is confirmed empirically.
* ❌ Then `ReceivedBunch: Invalid replicated field 32 in LokiMinionCharacter` → channel closed.
  Two attempted fixes FAILED: the `CustomAnimationState` enum width (rebuilt to the client's 3 values
  — keep it, it is correct, but it was not this bug) and the skipped `LokiActor` tier (0 reps/0 funcs,
  shifts nothing).

**★ The mistake to not repeat:** the "field 32 diff" was never a diff. Only the STUB's index space was
computed (`Actor 11/0 | Pawn 3/0 | Character 10/7 | LokiCharacter 2/14 @base 31` ⇒ idx32 =
`CustomAnimationState`); the CLIENT's was assumed to match. "Invalid replicated field 32" MEANS the
two spaces disagree, so naming the stub's field 32 cannot identify the mismatch.
**NEXT: build the CLIENT's cumulative index space** (per level: own ClassReps, then own name-sorted
NetFields) and find the FIRST level whose counts differ. Inherited tiers were never captured —
suspects are the CHARACTER tier (stub: 10 reps + 7 funcs after stripping `RepRootMotion`) and the
ACTOR tier (stub reports NetFields=0).

**Tooling gotcha that cost two blind runs:** UE's `-abslog` needs an **absolute, space-free** path.
A spaced absolute path AND a relative name are both silently ignored, and an invalid `-abslog` also
suppresses the default `Saved/Logs` file. Use `-abslog=C:\Temp\DsS84.log`. Also: verify the stub is up
via the **bound UDP port**, not by finding a log.

---

## 3. State left for a normal menu session

* `forceTutorialMatch = false` — a normal launch sits at the fully functional MAIN MENU.
* DS stub NOT running; `ags` running from `server/ags.exe`.
* `battlepass_adopt_fix.dll` added to `configs/inject-secondaries.ps1`, so **`launch-redirect.ps1`
  with no flags now gives the whole working menu including PASSES**. New `-NoPasses` switch to trim it.
* Stub still has `ALokiMinionCharacter` wired (WIP). One-line revert to the stable S77/S81
  spectator baseline: `ALokiMinionCharacter` → `ADefaultPawn` in `LokiStubGameMode`.
