# Missions — wiring REAL match progress when matches come back

Forward-looking handoff. As of Session 59 the whole missions **display + tracking pipeline works**, but
progress is advanced by a **simulated/manual** match-result POST, not by real gameplay — because matches don't
launch yet and, in the real game, match results are reported by the **dedicated server**, not the client (every
match/mission endpoint the client hits is a GET). This doc is the map for closing that last link once matches run.

Cross-refs: `docs/session-59-progress-bars.txt` (the full build), `docs/trackb-notes.md` (the client's
progression/mission HTTP surface), `docs/session-54-ds-missions-replication.txt` +
`docs/session-55-native-call-primitive.txt` (the native ingestion functions + the DS-replication attempt).

---

## What already works (the machine that's waiting for a real signal)

**Server (`ags`, `server/internal/interactive/missions.go` + `store.go`):**
- Per-account, **per-mission** objective progress, keyed `"<missionInternalName>/<objectiveUniqueName>"`
  (composite → two missions sharing an objective name track independently). Persisted in `state/interactive.json`
  under the fixed `"local"` key (single-account revival; key by JWT `sub` for multi-account).
- HTTP surface (revival-only, NOT impersonated client routes):
  - `GET  /revival/missions/progress` — the shim reads this on menu load.
  - `POST /revival/missions/progress` (set) / `.../add` (increment) — explicit composite-key edits.
  - `POST /revival/missions/manifest` — the shim registers the full mission→objective list (`{mission,objective,max}`)
    so the engine can fan out per-mission.
  - `POST /revival/missions/match-result` — **the increment engine.** Takes a match stat summary, maps it to
    objective-name deltas via `objectiveRules`, and fans each out to every mission that has the objective.
- `objectiveRules` (in `missions.go`) is the stat→objective mapping table. `matchResult` is the stat schema.

**Client (`tools/sigbypass-mod/missions_fix.dll`, auto-injected by `launch-redirect.ps1 -Missions`):**
- On menu load: registers the manifest, fetches progress, builds the mission model with each objective's
  `Progress` set from the composite key, swaps it into `ProgMgr.MissionsModel`. Polls every 30s and re-applies on
  change. The game's own BP then renders the bars (`ObjectiveModel.CurrentProgress / Objective.TotalProgress`).

So: **anything that lands in the `ags` store shows up on the bars.** The only missing piece is a *real* match
result reaching `/revival/missions/match-result` (or the store directly).

---

## The candidate real-match signals (where match-end data could come from)

Investigate these once a match can actually run and be captured (`docs/capture.log`, `docs/endpoints.md`):

1. **`PUT /progression/players/{id}/mission`** — the client's *"reconcile mission progress"* trigger (exe:
   `ServerAddMissionProgress` / `SetMissionProgress`). Fired ~21×/session but with an **empty body** — it's a
   *"something changed, refetch"* SIGNAL, not the data. In the real game the DS added the progress server-side and
   this just told the client to refresh. **Use it as a "refresh now" hook**, not a data source. (Handled today as
   fire-and-forget in `interactive.go:handlePutMission`.)
2. **`GET /core-game/players/{id}`** — match lifecycle (`ECoreGameMatchState`: …InProgress → Closing/Deallocating).
   A state transition to a terminal state = a match just ended → a good moment to compute/record a result.
3. **`GET /match-history/players/{id}`** — post-match history. **The most likely carrier of real per-match stats**
   (kills/knocks/placement/gameMode/hero). Capture its real response shape once matches run; it may be enough to
   derive the objective deltas directly.
4. **The game's OWN native ingestion** (server-side path in the real game), RE'd in s54/s55:
   - `LokiPlayerState_Missions.ServerAddMissionProgress(MissionID:str, ObjectiveName:str, Progress:float)`
   - `LokiPlayerState_Missions.SetMissionProgress(OUT MissionInfo)` / `GetMissionProgress(OUT TArray<MissionProgress>)`
   - `UProgressionManager.AddProgressToMission(...)`
   These are what a **dedicated server** would call. Needs a LIVE `LokiPlayerState_Missions` (CDO-only at the menu).

---

## Two integration strategies

### (A) Backend-driven — RECOMMENDED for the client-shim revival (extends what's built)
The current architecture. When a match ends, get its stats into `ags` and POST them; the shim already does the rest.

1. **Capture the real match-end report.** Run a real match (once the launch path is un-gated) and watch
   `docs/capture.log` for what the client/DS sends at match end — which endpoint, what JSON. Prime suspects:
   `/match-history/players/{id}`, a `/core-game` transition, or a stats/telemetry POST.
2. **Reconcile the stat schema.** `matchResult` in `missions.go` (win, placement, knocks, assists, teamWipes,
   minionKills, bossKills, chestsOpened, vaultsOpened, bonfiresCaptured, sunrises, purchases, uniqueHeroes,
   gameMode) is a **placeholder I invented** — remap it to the real match-end fields, or add a small translator
   from the captured shape into `matchResult`.
3. **Extend `objectiveRules`.** It currently maps ~18 objectives (Tournament / Dailies / Weeklies / Onboarding).
   The **309 hero missions** (per-hunter, HunterMissions pool) are **UNMAPPED** — they need hero-ability-event
   stats (e.g. "Alchemist heals with Q", "Beebo Q-knocks"). The **full 91 distinct objective unique-names** are
   dumpable live from the model's Objectives-map keys (this session's `tools/re` scripts read
   `MissionModel.MissionAsset.InternalName` + the objective names; see session-59). Map each to a stat.
4. **Drive it from the real handler.** Instead of a manual `curl … /match-result`, have the ags match-end handler
   (new, on whatever endpoint carries the report) call `applyMatchResult` (in `missions.go`). The shim's 30s poll
   (or a `PUT …/mission`-triggered refresh, signal #1) then updates the bars.

### (B) Native-driven — faithful, heavier (the DS-replication path)
Call the game's own `ServerAddMissionProgress(MissionID, ObjectiveName, Progress)` on a **live**
`LokiPlayerState_Missions` from match results, so the game's native missions system tracks + replicates it. This is
the `docs/session-54-ds-missions-replication.txt` route — semantically correct, but it hit the **main-menu-HUD wall**
on the dedicated-server stub (the DS couldn't produce a visible modal). Prefer (A) unless a real DS is running the
match and you want the game to own progression natively.

---

## Now server-side (2026-07-10) — mechanism built, needs the shim to send the extra fields

The server no longer knows only raw progress; it now computes COMPLETION and can rotate. See
`missions.go` (`missionStatuses`, `handleGetMissionStatus`, `handleRotateMissions`) + `missions_test.go`.

- **Per-mission completion + XP earned** — `GET /revival/missions/status` returns each mission's
  `{complete, objectives:[{objective,progress,max,done}]}` plus a summary `{total,complete,xpEarned}`,
  computed from the manifest maxes + stored progress. Completion needs NO new data (max is already in the
  manifest). **XP-earned needs the shim to send per-mission `xp`** in the manifest (see below).
- **Daily/weekly rotation** — `POST /revival/missions/rotate {"pool":"Dailies"}` (or `{"missions":[...]}`)
  clears that scope's composite progress — the reset the accumulate-forever store lacked. **Needs the shim
  to send each entry's `pool`** so a pool can be targeted (mission-name lists work without it).
- **Manifest read-back** — `GET /revival/missions/manifest` (was write-only) for the admin panel / a
  future thinner shim.
- **Coverage report** — `GET /revival/missions/coverage` cross-references the registered manifest against
  `objectiveRules`: per-mission `full/partial/none`, plus the two lists that drive step 3 below —
  `unmappedObjectives` (objectives with no rule → the 309 hero missions surface here) and `unusedRules`
  (rule names matching no manifest objective → usually a name typo like the space in `"BR_Capture Bonfires"`).
  Run it after a launch (once the shim has POSTed the manifest) to see exactly which rules to add/fix.
- **Admin panel** — `GET /api/missions` now also returns the computed `status` + `coverage` blocks.

**SHIM ENRICHMENT — `pool` DONE + deployed; `xp` DRAFTED (gated) (2026-07-10, both pending a validation launch).**
`ManifestEntry` accepts optional `pool` + `xp` (backward compatible). `missions_fix.cpp`'s `AppendManifest`
now sends **`pool`**: `BuildObjectivesForMission` derives the pool name via
`GetFNameStr(g_missPool[i][1] & 0xFFFFFFFF)` — the same proven op that builds `g_poolNames` — and passes it
in; empty pool ⇒ the field is omitted. Compiled (clang, exit 0), manifest JSON format verified well-formed,
deployed `missions_fix.dll` rebuilt. **Validate on the next launch:** open the menu once with the missions
shim (default set), then `GET /revival/missions/coverage` — each mission should now carry a `pool`, and
`POST /revival/missions/rotate {"pool":"<name>"}` should clear that pool. Low-risk / graceful: pool only
affects the server-side manifest POST; the missions-page RENDER is unaffected (pool is written to the model
element independently), and `-NoMissions` isolates it.
**`xp` — DRAFTED behind `#ifdef MISSIONS_XP_DRAFT` (NOT in the default deployed DLL).** `MissionModel.XPReward`
is at `+0x60` on the OUTPUT model (post-factory), not on the input `FMissionProgress` the manifest is built from,
so the draft reads it from the array `GetMissions()` already returned (no extra native call), correlates each
output mission to an input one by `MissionAssetId@+0x40` (a unique key — both offsets are RE'd s58/s59, not
guessed), then re-serializes the manifest with `xp` (`FillXPFromModel` + `RebuildManifestWithXP` in
`missions_fix.cpp`). Fully `SafeReadable`-guarded: any bad read leaves that mission's XP at 0 → the field is
omitted, never a crash or a misassigned value.
- **Why gated, not deployed:** the default build is byte-identical to the pool-only version (XP compiled out),
  so the deployed DLL carries ZERO regression risk to the working manifest path; the rebuild-with-xp only runs
  under the flag. Both builds compiled clean (clang, exit 0); the `xp` JSON format is verified well-formed
  (present when >0, omitted otherwise, independent of `pool`).
- **To validate on a launch:** build with the flag —
  `clang++ -DMISSIONS_XP_DRAFT -shared -O2 missions_fix.cpp -o missions_fix.dll -lkernel32 -lwininet` — then
  open the menu with the missions shim and `GET /revival/missions/status`: `summary.xpEarned` should sum the
  completed missions' rewards, and each mission's `xp` should appear in `/coverage`/`/manifest`. If it reads 0
  everywhere, the `+0x60`/`+0x40` offsets or the `GetMissions()` array shape need re-confirming live (RPM), and
  the default (pool-only) DLL is unaffected in the meantime.

## Still not implemented (do these too, when wiring real progress)

- **Reward CLAIM flow (XP/entitlement grant).** Completion is now computed server-side, but *claiming* is
  still untouched: `MissionModel.Completed`@+0xB8, `bHasClaimableReward`@+0xB9, `MissionModel.ClaimReward`
  (BP), and the `PUT /progression/players/{id}/mission` reconcile/claim trigger whose `MissionData` response
  carries `Completions` / `TrackIDToClaimableRewards` TMaps (see `interactive.go:handlePutMission`). Granting
  the account-level XP + wiring the claim UI is the remaining piece.
- **Rotation cadence/expiry.** The rotate MECHANISM exists; a *policy* (a timer, or the client's own
  daily-reset signal, driving `/rotate`) + real `FMissionProgress` `Expiry`/`GrantedAt` values (shim sets
  placeholders today) are still needed for authentic timed dailies/weeklies.
- **Multi-account.** Everything is under the fixed `"local"` key; key by the JWT `sub` for real per-account.

---

## Quick reference

- Engine + schema + rules: `server/internal/interactive/missions.go` (`matchResult`, `objectiveRules`,
  `mappedNameDeltas`, `applyMatchResult`, `handleMatchResult`, `handleSetManifest`/`handleGetManifest`,
  `missionStatuses`/`handleGetMissionStatus`, `handleRotateMissions`). Composite key = `"<mission>/<objective>"`.
- Store: `server/internal/interactive/store.go` (`MissionObjectives`, `MissionManifest`), `state/interactive.json`.
- Shim: `tools/sigbypass-mod/missions_fix.cpp` (fetch/build/swap + manifest POST + poll). Offsets:
  `DA.InternalName`@+0x40, `DA.Objectives`@+0x88 (`LokiMissionObjectiveData`[0x30], `TotalProgress`@+0x10),
  `MissionModel.Objectives`(map)@+0x68, `MissionObjectiveModel.{Name@0x30,CurrentProgress@0x38}`,
  `ProgMgr.MissionsModel`@+0x3B8. Native `LokiAssetStatics::GetUniqueObjectiveName(LokiMissionObjectiveData)->FName`.
- Native ingestion (strategy B): `LokiPlayerState_Missions.ServerAddMissionProgress(str,str,float)` etc. — s54/s55.
- Live smoke test today: `curl -X POST http://127.0.0.1:8080/revival/missions/match-result -d '{"win":true,"placement":1,"knocks":8,"gameMode":"tournament"}'` → reopen the modal.
