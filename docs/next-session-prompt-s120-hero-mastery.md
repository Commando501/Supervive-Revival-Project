# S120 handoff — start at HERO MASTERY

Written 2026-08-14 at the end of S119. HEAD is `f1b88c3` on `dedicated-server-stub`, pushed.
Working tree clean. **Use a maximum of 3 subagents for this work.**

---

## Start here

**Check the HERO MASTERY surface.** We now serve 323 missions and the client accepts all 323, but
only ~30 of them can ever appear in the missions modal. The other **~293 are Hero Mastery content**
and nobody has looked at that surface yet.

Ask the operator to open a hunter's **Hero Mastery** page and screenshot it. That single screenshot
decides the next few hours of work:

* if mastery rows render — the mission work is finished end to end, and the next target is
  *progress* (making those bars move) rather than *presence*;
* if it is empty — there is a second gate on that surface, and it is worth finding because it is
  the last thing standing between us and a fully populated progression UI.

The widgets to read are already named: `WBP_HeroMastery_TooltipMissionList`,
`WBP_HeroMastery_MissionDifficulty`, `WBP_HeroMastery_TooltipMissionListItem`. Extract them with
`tools/extractor` `bpdump` before theorising — see "the two cheap instruments" below.

---

## What is already true (do not re-derive)

The whole missions + banner pipeline is **native and shim-free**. Read the Missions block and the
`news- / banner- / announcement- / CEF-shaped` block in `CLAUDE.md` first; both were rewritten this
session and are current.

* **`FPlayerProgression.MissionInfo`** on `GET /progression/players/{id}` is the HTTP door. The
  native ingester `0x585A570` copy-constructs it into `ProgressionManager+0x90`, which builds real
  `UMissionModel`/`UMissionPoolModel`s, async-loads each DA, then
  `UMissionsModel::OnMissionAssetLoaded` (`base+0x56F3ED0`) sets `bAllMissionLoaded` and broadcasts.
* **The mission name is the DA's `InternalName` property, not its filename.** That was the whole
  acceptance rule: 126/323 → 248/248 → **323/323** once the 75 `CLASS_Abstract` bases were served
  under their prefixed key `Mission:DA_Mission_<file>`. Set-identical, zero drops.
* **`missions_fix.dll` is RETIRED** from the default injection set (`-WithMissionsShim` restores it).
  That removed one manual-map and one transient `ProcessInternal` `.text` patch from every launch.
* **The lobby news banner** renders from `ClientConfiguration.BannerConfigs`, and clicking it opens
  our own page via `LaunchURL`. FK-17 is closed.
* **The missions modal's categories are a hardcoded `PoolAsset[]` allowlist** in
  `WBP_UI_MissionModal`. `DA_MissionPoolHunterMissions` is in none of them, which is *why* hunter
  missions must live on Hero Mastery.

Data flow, if you need to change what is served:
`tools/re/gen_missions_catalog.py` → `server/internal/interactive/missions_catalog.json` (embedded) →
`missionInfo()` in `server/internal/interactive/interactive.go`.

---

## State of the machine

* Game **PID 64368**, base `0x7FF7C7EF0000`, in the lobby, default shim set
  (`pi8 + catalog_pick_fix + loadout_fix + battlepass_adopt_fix`, **no** `missions_fix`).
  323 `UMissionModel` + 9 `UMissionPoolModel` live, `bAllMissionLoaded = 1`.
* `ags` **PID 53528**. No diagnostic env vars set.
* **Keep both alive if you can** — same ASLR, same heap, decrypted pages. Check `Get-Process` before
  re-deriving anything. Hero Mastery may be inspectable without relaunching at all.
* ⚠ Restarting `ags` truncates `docs/capture.log`. Back it up first.

---

## The two cheap instruments this session kept forgetting

Both would have saved hours. Reach for them **before** any statistical or structural inference.

1. **`grep "Invalid asset path for Mission:" Loki.log`** — the client names every `FPrimaryAssetId`
   it fails to resolve, one line each, plus `LogBaseMission: Warning: Mission object is null`. In the
   broken session that was 197 names, set-identical to the 197 rejected missions; it is 0 now. This
   generalises to **every** `FPrimaryAssetId` the backend serves, not just missions.
2. **Read the shipped asset.** The mission-modal category rule was sitting in
   `WBP_UI_MissionModal.json` as a plain `PoolAsset[]` array the entire time, after three wrong
   inferred rules. Extracted assets are in `tools/extractor/out/` and `out/catalog/`.

---

## ⚠ Four instrument artifacts bit in S119. Read these before trusting a number.

Every one produced a confident wrong claim; two reached commits.

1. **`tools/re/obj_by_class.py` caps its detail list at 60 rows.** `| grep -c "obj="` **saturates at
   60** — it reported 60 live objects where there were 126, and that 60 produced a whole false
   theory about pools being rejected. **Parse its `found N LIVE …` line; never `wc` its output.**
   (The tool now prints a DO-NOT-COUNT banner.) ★ Cross-check any object census by **pointer
   equality on the target `UClass`** — name-free and immune to FName-decode failure.
2. **The ingester MERGES into the existing model; it never replaces.** An in-place re-push can only
   *grow* the count, so a "no change" result is weak and a matching total can be coincidence — one
   reading looked like a clean 248/248 when the map held 205 new keys plus 43 stale ones.
   **Any acceptance measurement must be taken on a COLD client, and compared by SET IDENTITY, not
   by count.**
3. **The client caches banner images** to `Saved/ImageCaches`, so a rendered banner produces no HTTP
   request. Mitigated permanently: the banner URLs carry `?v=<bannerAssetNonce>` which changes once
   per `ags` start. **Do not remove the `?v=` — it is the instrument.**
4. **Our own `curl` verifications land in `docs/capture.log` looking exactly like client traffic.**
   Check `User-Agent` on every captured request: the game is `Loki/UE5-CL-0`, a `LaunchURL` click is
   `Mozilla/… Chrome/…`, ours is `curl/…`. This nearly became a fabricated headline result.

★ And the meta-lesson, which cost three retractions of one claim: **a conclusion drawn from data that
a known bug was silently filtering looks clean and survives review.** When you find an upstream
defect, **re-derive every conclusion built on the contaminated data** — do not patch the wording.
`PoolGroupId` was "gates acceptance", then "gates visibility", then not a gate at all.

---

## Open threads, ranked

1. **Hero Mastery renders?** — the start-here question above.
2. **Mission PROGRESS, not presence.** Bars currently show stored progress from the composite-key
   store (`<mission>/<objective>`). Nothing increments them without matches. `POST
   /revival/missions/match-result` and `objectiveRules` in `server/internal/interactive/missions.go`
   are the existing machinery.
3. **The objective-name derivation is weakly verified.** `ObjectiveClass` minus
   `BP_MissionObjective_`/`_C` reproduces only 10 of the old manifest's 187 pairs — mostly because
   the sources barely overlap, but it is not independently confirmed at scale. If a mastery row
   shows a wrong objective, suspect this first.
4. **`GET /match-history/players/{id}` serves `Matches: []`.** Serving one populated
   `FMatchHistoryEntry` would close **FK-21** (Career→History "authentic empties"). It is the
   riskiest struct we have touched — 15 fields incl. two `FDateTime`, an `FPrimaryAssetId`, nested
   `FMatchHistoryTeamInfo`/`FLokiPlayerMatchStats`, an `ERank` enum — so send it **alone**.
   The discriminator already exists: `MatchHistoryManager+0x68` reads back our served `Version`.
5. **`CLAUDE.md` lists a `usmapdump assetmgr` verb that does not exist.** Minor doc defect, unfixed.

---

## Standing rules

`docs/method-rules.md` governs. In particular: name the instrument and its coverage before recording
any negative; run a positive control that must pass and a negative control that must fail; label
every claim MEASURED / INFERRED / SPECULATIVE; and never let a subagent commit or push — one did
both this session (`2779f81`, 618k insertions of run logs, cleaned up in `c096fe5`).

Prefer **data or bytecode writes over `.text` writes** in anything client-side; the measured hazard
ladder at a 320 s hold is nothing 0/22 · bytecode 0/9 · transient `.text` 4/12 · standing `.text` 7/8.
