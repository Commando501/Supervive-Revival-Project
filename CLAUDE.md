# SUPERVIVE Revival — project rules for Claude

This is a reverse-engineering project to revive a Steam-launched UE5.4 game whose
official backends are dead. We've redirected the client to a local Go server
(`server/cmd/ags`) over hosts-file + HTTPS-with-self-signed-cert. The work spans
backend RE, IoStore extraction, native shim injection, and asset-registry patching.
Lots of dead ends. Honor the prior-work docs.

The whole front-end menu is now ONLINE: login, the ALL HUNTERS roster (+ click-to-
refresh), the STORE, COSMETICS, the full MISSIONS page (with working progress
bars), the PASSES / Hunter's Journey account pass (full 85-tier ladder), and the
AVATAR / CALLSIGN customization (render + live switching) all render live. That was
achieved with the backend feed **plus** a set of client-side native shims built on a
reusable game-thread native-call primitive (see below).

**Current frontier = the tutorial WORLD.** Getting in is solved (S107/S108): the client
loads `LVL_Tutorial`, the hero spawns, is possessed, moves, and **walks/runs with real
locomotion animation** (S108b). The whole sitting is now **hands-free** — no human at the
keyboard (see "Tutorial sittings" below). ★★ **STABILITY IS LARGELY SOLVED (S112, 2026-08-08):**
FK-7 — "the run dies within ~1–5 min" — was substantially **our own standing `.text` patch**, and the
shipped `tutorial_launch_play.dll` no longer makes one (10/10 armed windows died with it vs 2/30
without, Fisher p = 0.00000008; 16/16 survived a full 600 s hold). What is still open is *simulation*
(abilities / combat: the hero owns no ability system) and the **staging hazard** — ~25 % of launches
still die before the probe is injected, with only `gft`+`fo` resident.

## Before doing anything else

### If the user mentions hero/roster/grid/hunters/store/cosmetics/missions modal/passes/battlepass
**These are SOLVED — they render live.** Do NOT re-open the closed hypotheses.
- **Roster / store / cosmetics** — root cause was one un-set client-side
  catalog-ready sub-flag (`CatMgr+0x354`), NOT the backend, NOT enumeration, NOT
  LokiAssetManager bypass (all falsified over ~13 sessions). Fix = the native shim
  `tools/sigbypass-mod/catalog_store_fix.dll`. ★ **As of 2026-08-06 it contains NO `.text`
  patch at all** — the old self-restoring `jz`-NOP was MEASURED to be the protector-kill
  trigger (`docs/s111-bisect-jz-is-the-trigger.md`) and was dropped; the shim's existing
  **`[+0x354]` DATA poke** on the live CatalogManager is sufficient and the roster still
  renders (screenshot-verified, `docs/s111-jz-dropped-shipping.md`). It still does the
  AssetManager scan + CatalogEntry poke. Rollback: `build.ps1 -Variant jzpatch`.
  ⚠ The data poke must land BEFORE the user first opens HUNTERS — keep it early and
  continuous, or the grid can Construct-and-wait with an empty roster (S47). STORE
  tiles also need the backend to mark cosmetics `IsOwned` (`handleInventory`).
  Living log: `docs/hero-roster-attempts.md`.
- ★★★★★ **Missions — NOW FULLY NATIVE AND SHIM-FREE (S119, 2026-08-14).** `missions_fix.dll`
  is **RETIRED from the default set**; the page renders from the BACKEND alone. Serve
  `FPlayerProgression.MissionInfo` on `GET /progression/players/{id}` and the client's own
  native ingester (`0x585A570`) copy-constructs it into `ProgressionManager+0x90`, builds real
  `UMissionModel`/`UMissionPoolModel`s, async-loads each mission's DA, and then
  `UMissionsModel::OnMissionAssetLoaded` (impl `base+0x56F3ED0`, fold 1) sets `bAllMissionLoaded`
  and broadcasts. MEASURED on a clean `-NoHook` run: **DAILIES 3/3 + WEEKLIES 8/8** with correct
  localized titles, real progress bars, correct XP tiers (2500 daily / 15000 weekly) and a working
  CLAIMED state, **zero shims resident**. Rollback is one flag: `-WithMissionsShim`.
  ⚠ The OLD note ("renders client-side via the native-call primitive … packaged as
  `missions_fix.dll` … `-Missions`") described the SHIM workaround and is superseded.
  ⚠ `MissionsActor` stays NULL and that is FINE — the *designed* feed is replication
  (`ALokiPlayerState_Missions.Missions`/`.FinalMissionProgress` are `CPF_Net|CPF_RepNotify`, and
  ZERO instances of that actor exist at the menu), so the HTTP door is the only route and it works.
  ★ **The mission list comes from the GAME'S OWN DATA ASSETS, not from the shim's manifest** —
  `server/internal/interactive/missions_catalog.json`, regenerate with
  `python tools/re/gen_missions_catalog.py`. The manifest was measured unfit: 75 of its 330 rows
  carry no mission name, several `mission` values are OBJECTIVE names, its `pool` is a name-prefix
  GUESS inside `missions_fix.cpp:188-192` (it files `Armory_WeeklyWinGame` under `ArmoryOnboarding`
  when the DA says `WeeklyChallenges`), and only 23 of its 122 distinct names exist in the DA corpus.
  ★ **`PoolGroupId` governs UI VISIBILITY — a pool whose DA declares one (`daily`/`weekly`) gets a
  category in the modal; the rest are accepted into the model but have nowhere to render.** That is
  why the page shows only DAILIES + WEEKLIES.
  ★★★★★ **MISSION ACCEPTANCE IS SOLVED (2026-08-14). THE MISSION NAME IS THE DA's `InternalName`
  PROPERTY, NOT ITS FILE NAME.** The client registers every mission with the AssetManager under its
  own `InternalName`; serving the filename meant most missions named a `FPrimaryAssetId` that does
  not exist, and the client silently dropped every one. **Serving `InternalName` took uptake from
  126/323 to 248/248 — set-identical, zero dropped either way, measured on a COLD client.**
  Confirmed two independent ways before it was flown, then by exact prediction:
  a live walk of `UAssetManager.AssetTypeMap["Mission"].AssetMap` (330 registered entries — ALL
  missions are registered, so registration was never the differentiator, only the KEY), and an
  offline classification of the 323 then being served (TP 126, FP 0, FN 0). Both predicted 248, and
  248 is what landed.
  ★ **It is a REGISTRY, not per-file equality** — the shipped data contains a swap:
  `DA_Mission_Wukong_QKnocks_2` declares `InternalName "wukong_qknocks_3"` and `_3` declares
  `"wukong_qknocks_2"`. Per-file equality predicts both rejected; both were accepted.
  ★ **Matching is CASE-INSENSITIVE (FName semantics, not FString)** — 41 of the original 126 matched
  only after case folding (`DA_Mission_Earthtank_RMBAirDunk_3` declares `earthtank_rmbairdunk_3`).
  ★★ **THE MECHANISM, from disassembly (independent third confirmation):** the ingest loop over
  `FMissionInfo.MissionData` runs at `base+0x5700E13` (stride 0x60) and calls `MakeMissionModel`
  (`base+0x56F16F0`, fold 1). That returns nullptr when the model's `AssetHandle` is null, and the
  loop DROPS the element at `base+0x5700E8C`. The handle is null because
  `ULokiAssetManager::AsyncLoadPrimaryAssets` (`base+0x561C6B0`) tests
  `UAssetManager::GetPrimaryAssetPath(id)` (vtable disp `0x338`) for an EMPTY path at
  `base+0x561C7F4` and drops unresolvable ids from the load list. **The predicate is a
  PrimaryAssetId registry resolve and NOTHING else** — pool, expiry/GrantedAt/MillisUntilExpiry,
  `BaseMission`, `IsDebugOnly` and dedupe were each ELIMINATED from the disassembly (`IsDebugOnly`
  is passed a constant zero and never read; a dedupe hit goes to a MERGE branch, never a drop).
  ★★★★★ **AND IT IS LOGGED — THE CLIENT WAS TELLING US, 197 TIMES:**
      `LogLokiAssetManager: Error: Invalid asset path for Mission:<Name>`
      `LogBaseMission: Warning: Mission object is null`   (MissionsModel.cpp:366)
  In the broken session those appeared 591 = 3 x 197 times and the 197 distinct names were
  SET-IDENTICAL to the 197 rejected. After the fix both counts are **0** (verified). `LogBaseMission`
  is Verbosity=Log so a Warning always prints — the silence is meaningful, not suppressed.
  ⇒ **Grep the log for `Invalid asset path for` before doing ANY statistical inference about which
  ids the client accepted.** It is a free, exact, per-id readout and it generalises to every
  `FPrimaryAssetId` we serve, not just missions. This was found only after a long inference detour —
  method rule #2 (read the shipped artifacts first) would have gone straight to it.
  ⚠⚠ **CORRECTION to a long-standing repo belief:** `UMissionsModel::CreateMissionsModel`
  (`0x56E0600`), `CreateMissionModelFromFinalProgress` (`0x56E0560`) and `OnPSMissionsUpdated`
  (`0x56F51B0`) are **NOT on the native path** — all three are `PAGE_NOACCESS` (never demand-decrypted,
  i.e. never executed) in two independent live processes. They are decrypted only in `dumps/missions`,
  i.e. they ran ONLY when the retired `missions_fix` shim force-called them. The comment in
  `server/internal/interactive/interactive.go` calling `CreateMissionModelFromFinalProgress` "the
  factory" describes the SHIM's path, not the game's.
  ★ **75 DAs declare NO `InternalName` — exactly the `CLASS_Abstract` base templates**, and exactly
  the 75 bases-of-variant-families that never landed. That is the mechanism behind the old
  "bases never land (0/75)" observation. **They ARE registered — under their FULL asset FName
  INCLUDING the `DA_Mission_` prefix** (`da_mission_alchemist_healwithq`), which is why stripping the
  prefix made all 75 unresolvable. Serving them as `Mission:DA_Mission_<file>` works:
  **MEASURED 323/323 accepted, set-identical, zero drops, `Invalid asset path` count 0.**
  All 75 carry exactly one objective and sit in the `HunterMissions` pool, whose
  `UMissionPoolModel` now materialises (8 -> 9 pool models). They are marked `"abstract": true` in
  `missions_catalog.json` so a template is never mistaken for an authored mission.
  ⚠⚠ **RETRACTED, superseded by the above:** "11/11 grouped landed, 0 of 94 ungrouped landed, only
  60 of 323 land". The 60 was a clamped count (see the `obj_by_class.py` warning below) and the
  per-pool split it produced was noise — `PoolId` was separately DISPROVED as the filter by a
  single-variable probe (`AGS_MISSION_NO_POOLID=1`: PoolId omitted from all 323 entries, ingest
  confirmed via `PM+0xA0`, count unchanged at 126).
  ★★★★★ **THE MODAL'S CATEGORY LIST IS A HARDCODED ALLOWLIST — settled from the asset, 2026-08-14.**
  `WBP_UI_MissionModal` contains a fixed set of `WBP_UI_MissionModalCategory` widgets, each with an
  explicit **`PoolAsset[]`** array naming the pools it displays:
      Armory   -> ArmoryOnboarding                    Onboarding -> OnboardingPlanbee, Onboarding
      Dailies  -> DailyEasy, DailyChallenge           Weeklies   -> Weekly, WeeklyChallenge
      Seasonal -> Tournament                          PC Bang    -> DailyPCB, DailyPCB_Armory
  A category renders when its pools have accepted missions (which is why ONBOARDING and SEASONAL
  appeared once their missions resolved). **`DA_MissionPoolHunterMissions` is in NO category's
  `PoolAsset[]`, so hunter missions can NEVER appear in this modal** — MEASURED: 323/323 missions
  accepted, `HunterMissions` pool model live, and still no HUNTER MISSIONS category.
  ⇒ ★ **Hunter missions belong to HERO MASTERY, not the missions modal** (`WBP_HeroMastery_
  TooltipMissionList`, `WBP_HeroMastery_MissionDifficulty`). Since the 75 abstract bases AND the 218
  tier variants that inherit their pool are ALL `HunterMissions`, roughly **293 of the 323 we serve
  are Hero Mastery content** and only ~30 are modal content — which is exactly what renders.
  ⚠ So do NOT chase "why don't all 323 show in the modal": it is the wrong surface for most of them.
  ⚠⚠ **AND `PoolGroupId` IS NOT A GATE OF ANY KIND — RETRACTED TWICE, 2026-08-14.** It was first
  recorded as gating ACCEPTANCE, corrected to gating UI VISIBILITY, and BOTH are wrong: they were
  artifacts of the filename bug, because only the daily/weekly pools happened to contain missions
  whose filename matched their `InternalName`. **MEASURED after the fix: `Onboarding` and
  `Tournament` both declare `PoolGroupId = None` and BOTH now render as categories** (ONBOARDING and
  SEASONAL). The modal went from 2 categories to 4. ⇒ **The category rail is driven by the modal's hardcoded
  `PoolAsset[]` allowlist (see above), gated on those pools having ACCEPTED MISSIONS — not by
  `PoolGroupId`.** Prediction made before the screenshot — "the modal
  will look identical because the new missions are in ungrouped pools" — was FALSIFIED.
  ★ Also now rendering natively: the pool's **`MetaMission`** (`DA_MissionPoolDailyChallenge`
  declares `MetaMission: Armory_CompleteDailies`) appears as the **COMPLETE ALL DAILIES 0/3** header
  above the daily list, with its own 7500 XP reward.
  ★ **The `_1`/`_2`/`_3` suffixes are real TIER VARIANTS, not duplicates**: `Alchemist_HealWithQ`
  (max 10) / `_1` (7,500) / `_2` (75,000) / `_3` (300,000). **218 of 323 catalog names are suffixed,
  and they are exactly the 218 with no declared pool** — a variant inherits its base mission's pool
  and CUE4Parse omits inherited properties. That is the mechanism behind "partial pool coverage".
  ⚠ Open: the objective-name rule (`ObjectiveClass` minus `BP_MissionObjective_`/`_C`) is verified on
  only 10 overlapping pairs.
  ⚠⚠ **`tools/re/obj_by_class.py` CAPS ITS DETAIL LIST AT 60 — never count its output lines.**
  `obj_by_class.py … | grep -c "obj="` SATURATES at 60, so a class with 126 live instances reads as
  "60". The tool's own `found N …` line was correct the whole time. This produced the retraction
  above and reached a commit message before it was caught (2026-08-14; the tool now prints an
  explicit "… N more not shown" + "DO NOT COUNT THESE LINES" banner). **Parse `found N`, never `wc`.**
  ★ Cross-check any object census by POINTER EQUALITY on the target `UClass` — name-free, immune to
  FName-decode failures, and it is what settled this (127 objects share the `UMissionModel` UClass
  pointer: 126 map values + the CDO, with every map value found and zero unreadable).
  Read `docs/session-59-progress-bars.txt` + `docs/missions-progression-hookup.md` for the SHIM era.
- ★★★★★ **HERO MASTERY — SOLVED END TO END, SHIM-FREE, SCREENSHOT-CONFIRMED (S120, 2026-08-14).
  Read `docs/s120-hero-mastery.md` before touching it.** HUNTERS → MASTERY renders and is UNLOCKED.
  **It is a SPLIT surface and conflating the halves is the trap:** the row LIST comes 100% from the
  25 shipped `LokiDataAsset_HeroMastery` assets (`MissionSets: Array<MissionSet{Missions:
  Array<FPrimaryAssetId>}>`, uniformly 3x3 = **225** ids) with ZERO backend involvement; PROGRESS
  comes from the `UMissionsModel` we already fill; and the per-hero LEVEL/XP track comes from
  **`FPlayerProgression.HeroMastery`**, which we had been omitting — that was the only missing feed.
  ★ **There is NO pool filter here** (`grep "Pool"` = 0 across its bytecode vs a 6-hit `MissionSets`
  control), which is *why* hunter missions render here and never in the modal. ★ **It does NOT gate
  on `bAllMissionLoaded`** (absent across all 7 bpdumps vs a 17-hit `GetMissionsModel` control).
  **SCHEMA [M]** (UHT, positive control = re-deriving `FMissionInfo` first; agreed by
  `binds_members.csv` and by disasm of `GetHeroMastery` impl `base+0x5841D70`):
  `FPlayerProgression` SizeOf **0x178**, 8 props, closes exactly — `ID@0x0, Version@0x10,
  Matches@0x18, MissionInfo@0x68, AccountPass@0xe8, HeroMastery@0x148 TArray<FHeroMasteryProgress>,
  LoginReward@0x158, EventProgression@0x168`. `FHeroMasteryProgress : FProgressionTrackLevel` SizeOf
  **0x70** = `Level@0x04 i32, XP@0x08 i32, Cleared@0x0C bool, UnclaimedRewards@0x10
  TMap<int32,FHeroMasteryRewardClaimData>, HeroId@0x60 FPrimaryAssetId`. No enums/UObject*/FDateTime
  anywhere under it. Consumer = the ingester `0x585A570` we already prove daily, then
  `CheckMasteryChanges` (thunk `0x5254220` → **impl `0x5795510`**, the mastery twin of the
  account-pass `0x5794480`, same TU). **No shim, no `.text` write.**
  ★★ **`HeroId` IS `Hero:<name>`, NOT `HeroMastery:<name>` — MEASURED, not inferred.** Served both
  forms with different Levels in one flight; the UI drew the `Hero:` value ⇒ `GetHeroMastery`'s
  linear **first-match** scan wins. ⚠ Both forms emit a `Progress Notif` (that is
  `CheckMasteryChanges` iterating), so **notif order does NOT tell you which the UI used** — an
  earlier "last wins" reading from exactly that was wrong. `InternalName == Hero.PrimaryAssetName`
  for all 25 heroes, and FName matching is case-insensitive.
  ★★ **THE PAGE IS GATED BY THE ACCOUNT PASS:** `PlayerHasGameFeature = (AccountPass.Level + 1) >=
  GetLevelGameFeatureUnlocked(MasteryGameFeature)`, and **the required level is 10** — the UI prints
  it verbatim as `🔒 Hunter's Journey Level 10`. Serving `AccountPass.Level = 10` **removed the lock**
  (single-variable; every HeroMastery value held constant, which is what rules out the "10 == our
  served 10" coincidence). ★ Rows render **while still locked** — the gate covers the track, not the list.
  **Knobs** (`server/internal/interactive/heromastery.go`): `AGS_SERVE_HEROMASTERY=hero|mastery|both`
  (**unset = OFF, and OFF is byte-identical to pre-S120**), `AGS_HEROMASTERY_PROBE_DELTA`,
  `AGS_HEROMASTERY_BASE_LEVEL` (both diagnostic). Ship `hero`.
  ⚠⚠ **BLAST RADIUS IS THREE SURFACES:** `FJsonObjectConverter` rejects the WHOLE struct on the first
  matched key it cannot import, so a wrong-typed `HeroMastery` closes the missions page, the account
  pass AND news-banner gate 2 together — and looks exactly like "no effect". That is why it is
  knob-gated. `UnclaimedRewards` is deliberately OMITTED (a `TMap<int32,…>` sent as an array is
  exactly that failure).
  ★ **FREE INSTRUMENT: `LogJson` names the failing property verbatim**
  (`Unable to import JSON value into property HeroMastery`, and `Unable to import Array element N`).
  Same class of per-item readout as `Invalid asset path for Mission:`. Grep both before ANY inference.
  ★ **The 7-mission gap was OURS and is fixed:** `gen_missions_catalog.py` dropped DAs with no
  `Objectives`, but a `_1` tier that overrides nothing INHERITS them and CUE4Parse omits inherited
  properties. 330 DAs ship, 323 declare objectives, **exactly 7 do not, set-identical to the 7
  unserved mastery refs.** A `Super`-chain pass fixed it: **323 → 330 served, 0 existing entries
  changed, 225/225 mastery refs resolve, `Invalid asset path` still 0.**
  ⚠⚠ **`extractor bpdump` leaves `<Name>_uasset.json` copies in the flat `out/` dir.** A variant's
  copy collapses harmlessly onto its `InternalName` key, but an ABSTRACT base has none, so it is
  keyed by FILE NAME and a stray copy becomes a WHOLE EXTRA MISSION — measured: the catalog silently
  grew to **331**, the extra being an id registered nowhere. Caught ONLY because 331 missed a
  pre-registered prediction of 330. The generator now excludes `*_uasset.json`.
  ⚠⚠ **CORRECTS THIS FILE:** "roughly 293 of the 323 we serve are Hero Mastery content" is WRONG.
  The mastery assets name **225** ids; **none of the 75 abstract bases is referenced by any mastery
  set**, so serving them did nothing for this surface.
  ⚠⚠ **AND CORRECTS `interactive.go`: the client does NOT re-poll `/progression/players/{id}` every
  ~61 s.** MEASURED at the menu: **exactly ONE fetch per messenger connection**, then nothing for
  8 minutes while the served Version advanced. ★ **The lever is `POST /api/ws/drop/{handle}`** (admin)
  — S85's socket-drop generalises to `/progression`; refetch lands within ~3 s and needs no Version
  guesswork, unlike `NotifyResource`.
  ⚠⚠ **The `User-Agent` trap fired AGAIN (2nd recorded instance).** Evidence read as "the client
  fetched twice and refused to adopt" — all three fetches were our own `Invoke-WebRequest`.
  **Filter `capture.log` by `User-Agent` BEFORE counting anyone's requests** (`Loki/UE5-CL-0` = game).
  ★★★★★ **AND THE MISSION BARS MOVE — screenshot-confirmed.** `YOU CARRY THIS` renders
  **1,500 / 3,000** with per-tier segments filling independently, matching every served value.
  ⚠⚠ **BUT ONLY AFTER THE WIDGET IS REBUILT. Pushing progress to a page that is already open changes
  NOTHING on screen** — switch hunter and back (the screen dedupes on same-hero, so away-and-back is a
  real rebuild), or relaunch. [I] the ingester rebuilds the model objects on each adoption and older
  widgets keep pointers to the previous generation. **Two surfaces were mis-diagnosed as broken feeds
  because of this — rebuild the page before reading anything off it.**
  ★ **Progress plumbing had TWO name-space defects, both fixed (commit `87563a2`):** the match-result
  fan-out wrote SHIM-MANIFEST composite keys while `missionInfo` reads CATALOG ones (**overlap 7 of
  187** — 180 writes were unreachable), and `objectiveRules` was keyed by the shim's objective names
  too (**2 of 102** catalog objectives had a rule; `BR_Knocks`→`Knocks`, `a2winarenagames`→
  `A2_WinArenaGames`, `TopXWithFullArmory`→`TopXWithFullArmoryInventory`, …). Coverage **3 → 22**
  missions trackable, **2 → 20** objectives mapped. `catalogManifest()`/`fanoutManifest()` are now the
  single source; `TestMatchResultKeysAreServable` pins the invariant and was verified to FAIL when
  reverted (naming 33 unservable keys).
  ⚠ The **293 hero-mastery objectives are unmappable from a match summary** — per-ability events no
  match stat expresses. That is a property of the data, not a TODO. They move via
  `POST /revival/missions/progress` (composite `<mission>/<objective>` keys) or the match-result
  `objectives` passthrough.
  ★ **The row LABEL shows the LAST tier** because we serve all three tiers as simultaneously granted,
  so `ActiveIndex`'s gate (`IsValid(GetActiveMissionModel) || CompletionCounts>0`) never fails. The
  SEGMENTS are per-tier and correct regardless. Lever if it should track the current tier:
  `PrereqMissions` (161 of 330 DAs declare one). Not done — it changes a route measured at 330/330.
  ⚠⚠ **`WBP_UI_MissionObjectiveProgress` ships a design-time `10/20` in `ProgressTextv2`, and the
  MISSIONS MODAL shows it** because `GetCurrentProgress` bails on `IsValid(ObjectiveModel)`. **That
  placeholder is NOT our data and never was** — do not read modal numbers as a backend signal; the
  completion checkmarks ARE ours.
  ★★★★★ **THE CLAIM PATH IS CLOSED — THE REAL CLIENT CLAIMED (2026-08-14).** Evidence preserved in
  `dumps/s120-claim-evidence/`. The GAME (`User-Agent: Loki/UE5-CL-0`) sent three POSTs, one per level:
      `POST /progression/players/{id}/hero/rewards/claim`  -> 200
      `{"heroId":"Hero:reshealer","claimIds":["hm:reshealer:0"]}`
  ags granted all three and persisted `masteryClaimed={"reshealer":[0,1,2]}`.
  Traced offline first from literal `L"/hero/rewards/claim"` at `.rdata 0x08B4D3A0` (one xref
  `.text 0x05827E11`, builder `0x05827DA0`, verb POST, dispatch `0x057EC800`), and **every inference
  was confirmed by the client's own bytes** — including `claimIds`, which was flagged [I] as "one
  letter, never seen on the wire". ⇒ **Serving `FPlayerProgression.HeroMastery[].UnclaimedRewards` is
  SUFFICIENT** — no shim, no `.text` write. Shape is a JSON **object with int-parsable keys**:
  `{"0":{"ClaimID":"hm:<hero>:0","SKU":"Emote:SeraphHi"}}`; SKUs come from each mastery DA's 7-entry
  `LevelRewards` (offline catalog `mastery_rewards.json`, `tools/re/gen_mastery_rewards.py`,
  25 heroes x 7 = 175). Knob: `AGS_SERVE_MASTERY_REWARDS` (default OFF).
  ⚠⚠ **RETRACTED SAME DAY — "`claimableRewards=[]` proves it is not claimable" WAS NOT A CONTROLLED
  NEGATIVE.** That field is `[]` in **30 of 30** log occurrences corpus-wide (account pass included),
  so it has **no known-good case and cannot discriminate**. It was called controlled because the
  notif was FRESH — but recency fixes staleness, not VALIDITY. Decisive counter-evidence: the client
  fetched `/progression` exactly ONCE and never relaunched, so the very document measured as "not
  claimable" is the one it claimed from 11 hours later. **Demand a positive control for the FIELD,
  not just a recent sample.** (45th instrument-artifact instance, committed by the session that had
  just written the rule down twice.)
  ★ The disassembly still stands and was never in conflict: `GetAllClaimableHeroMasteryRewards`
  (thunk `0x5269160` -> impl `0x583F1F0`, fold 1) really does `FindVM` (`0x57AB180`) -> `0x57ABCC0`
  -> walk `VM.Levels` `[VM+0xC8]`/`[VM+0xD0]`. That is what the MANAGER API reads; it was never
  evidence about what the UI can offer, and reading it as a blocker was the over-read.
  ★★★★★ **NO WIDGET OFFERS IT — THE CLIENT AUTO-CLAIMS (2026-08-14, reproduced on a fresh launch).**
  **Serve `UnclaimedRewards` and do nothing else**; the player never has to open the mastery page or
  press anything. MEASURED twice: the lobby tracker activates
  (`leaf-most node [WBP_UI_ProgressionTrackerBaseV2]`) and the claim POSTs follow **1.5–4 s later**,
  one per reward. In BOTH sessions `WBP_UI_LobbyRewards` occurs **0** times and `HeroMastery_Screen`
  **0** times — the second run never opened the mastery page at all.
  **THE NATIVE CHAIN** (`UClaimableRewardManager::BulkClaimAllProgressionTrackRewards`,
  thunk `0x5268FB0` → impl `0x58267D0`): `+0x58267EC` FindVM `0x57AB180` · `+0x5826831` `0x57ABCC0`
  walks `VM.Levels` → `TArray<FClaimableReward>` (stride 0x58) · `+0x5826904` `0x5848A70`
  (account-pass sibling → builder `0x5827440`) · `+0x582691A` `0x5849790` → `0x5849A68` calls
  `0x5827DA0` (the `/hero/rewards/claim` URL builder) → `0x57EC800` (POST sender).
  ★★ **METHOD WORTH REUSING — BEFORE/AFTER DECRYPTED-IMAGE DIFF.** The caller was invisible in the
  52 %-decrypted image. `dumpimage` before the action and again after; `.text` decryption is MONOTONE
  within a process lifetime, so pages zero-in-BEFORE and non-zero-in-AFTER are exactly the code that
  just ran. Here that was **20 pages / 80 KB** — small enough to read directly, and it contained the
  previously-unfindable call site. (Function starts: find rel32 call TARGETS landing in the page —
  the int3-padding scan does not work on this build.)
  ★ **[M] The flow is pure native C++, not a reflected entry point:** a walk of all **35,148** live
  `UFunction` objects found ZERO whose `Func` lands in any newly-decrypted page — independently
  corroborating the full-corpus census over **69,178** assets: `BulkClaimAllProgressionTrackRewards`
  appears in exactly **1 file** (`WBP_UI_LobbyRewards`, which logged ZERO activations in both claim
  sessions), `GetAllClaimableProgressionTrackRewards` in **0**, against the positive control
  `ClaimReward` = **9 files / 24 occurrences**. ⚠ Quote the UNIT: an earlier write-up said
  "ClaimReward 24" without it, which reads as a file count and is off by 2.7x.
  ★ The `0x57EC800` receipt behaved exactly as designed — `never ran` at baseline, `EXECUTED` after,
  with both negative controls still `never ran` **in the same run** that produced the positive.
  ⚠ Open (cosmetic): what native code invokes `BulkClaimAllProgressionTrackRewards` on tracker
  activation is unnamed — its page was already decrypted at baseline, so the diff cannot isolate it.
  `POST /party/parties/{p}/members/{id}/refreshMastery` is called at login and still untraced; there
  is no admin route for per-hero mastery (`SetHeroMastery` exists in code only); mastery XP never
  moves without match results.
- **PASSES / Hunter's Journey (ACCOUNT pass)** — the page renders live with its full
  85-tier ladder (S83). Two client-side root causes, NOT the backend (that route was
  exhausted over ~9 probes): (1) `CheckAccountPassChanges` (`0x5794480`, the populate's
  real caller) bailed on its tier gate `dword[PM+0x90+0xEC] == -1`; (2) the keystone —
  a **VM map-key mismatch**: it finds the view model by `P->GetPrimaryAssetId()`
  (vtbl+0x1D0) → `ToString` (`0x12F4230`) → `FindVM` (`0x57AB180`), i.e.
  **`ProgressionTrack:HuntersJourney`**, while our track keyed it bare `HuntersJourney`.
  Fix = `tools/sigbypass-mod/battlepass_adopt_fix.dll` resolves that key at runtime and
  adopts with it (BUMP its `Version` on every re-inject). Two traps: `VM.Levels`(+0xC8)
  is `TArray<UObject*>` (NOT PrimaryAssetId) and the populate `0x57DF4B0` CONSTRUCTS
  objects — **never force-call it** (that was the S82 crash); and the old note
  "P = S[+0x238]" is WRONG (S *is* `HuntersJourney_C`).
  Read `docs/session-83-passes-tier-grid-solved.txt` (its POST-SESSION CORRECTIONS block is
  load-bearing — a later 21-agent RE pass showed the grid is built by the VM
  builder's Init `0x57BB560` ahead of both gates, so the map key is the SOLE
  verified cause, and it FALSIFIED "the backend route is exhausted": the native
  ingester `0x585A570` does exist). Still open: real PROGRESS (tiers draw but
  nothing is claimed — gated on `byte[PM+0x388]`) and the SEASONAL pass (same
  byte, plus no packed `LokiDataAsset_Season`).

- **AVATAR / CALLSIGN (player-card customization)** — SOLVED end-to-end, BACKEND-ONLY,
  no shim (S85, 2026-07-21). Three causes, none the render/enum: (1) the avatar CARD
  reads `PartyMember.PersonalizationLoadout` which we never served — fix = `buildSoloParty`
  serves `personalizationLoadout` on the party member; (2) switches wrote to the WRONG
  ACCOUNT — the client's `/oauth/token` grant fell to an ad-hoc `"player"` key
  (`b70b628c…`) while the Steam login + party used `platform:steam` (`9b9d…`); fix =
  `token.LocalPlayerKey`/`LocalPlayerID` canonicalizes every unidentified-user auth path;
  (3) `UPartyModel::SetParty` (`base+0x587BE90`) gates the whole party doc on a strict
  monotonic `FParty.Version` (`cmp [PartyModel+0x568]; jge bail`) — we pinned `1`; fix =
  `store.partyVersion()` bumps on each loadout write. LATENCY (~30-57s → ~1.5s): the client
  applies the party ONLY on its `/notifications` messenger-RECONNECT resync, so we DROP that
  socket on a loadout write (`ws.Conn.Drop()` + `lobby.MarkDirty`, wired via
  `interactive.SetPartyDirtyNotifier`). The ~1s floor is the client's own reconnect backoff
  (not backend-controllable); a native shim (write member loadout + broadcast
  `OnPersonalizationLoadoutChanged` `base+0x587C699`) would reach ~0.2s but adds a PI-hooker —
  parked. ⚠ `PartyModel` exposes NO reflected `Version` UProperty (absence of a UProperty ≠
  absence of the field). ⚠ the `avId:""` presence trap: sample presence AFTER an equip.
  Read `docs/session-85-avatar-render.md`.

Before RE-touching any of these, READ the relevant doc above first — the value is
the trial-and-error history, and the corrected root causes are easy to regress on.

### Before touching anything tutorial- / FK-7- / FK-24-shaped
Read `docs/s108-fk24-instrument-corrected.md` **including its RETRACTIONS block at the
top, which governs**, then `docs/s108b-ksmactor-bisect.md`, `docs/s108-crash-triage.md`,
`docs/s108-fk7-verification-attempt.md` and `docs/s108-skeptic-review.md`. Also
`docs/s108-fk24-instrument-corrected.md` and `docs/fk7-crash-settled.md` (SUPERSEDED banner).

★★★★★ **FK-7 IS CLOSED — fixed, shipped and verified (S112, 2026-08-08).**
**Do NOT re-open it.** `docs/fk7-crash-settled.md` §0 still reads "OPEN (do NOT close)"; that verdict
was correct when written, the experiment it demanded has now been run, and the file carries a
SUPERSEDED banner at the top. Read `docs/s112-fk7-ab-results.md` first.
**What still fails on the tutorial route was SPLIT OUT as FK-31 / FK-32 — see
`docs/fk31-fk32-successors.md`.** Neither is FK-7; each has a different mechanism and window, and
pooling them under FK-7 would repeat this project's own recorded error of merging distinct
mechanisms under one label.
- **FK-31 — the staging hazard (NOW THE DOMINANT FAILURE): 22/82 launches (27 %)** die before the
  probe is injected, with only `gft`+`fo` resident; all dumped ones are `OURS/protector`. `fo`'s
  ≤8 s `.text` prologue and ≤25.5 s `.rdata` slot-285 patch are CONFOUNDED in every run ever flown.
  ⚠ `KNOLOGINVT` is **FALSIFIED — do not re-run it** (4/4 died, 0/4 map loads, fatal
  `ALokiGameMode::Login failed to Login`, p = 0.0026). Next: patch-then-immediately-restore.
- **FK-32 — the `0x0000DEAD` residual: 3/36 armed windows**, no artifact of any kind, NOT a protector
  kill. `0xDEAD` is not ours (no `TerminateProcess`/`ExitProcess` in any shim source; our own
  `Stop-Process` exits `0xFFFFFFFF`, measured). ⚠ N=2 — suggestive, not established. The exit-code
  instrument is permanent, so **harvest it, don't spend launches on it.**

★★★★★ **FK-7 detail (S112, 2026-08-08).** Final corpus: **standing `.text`
patch 10/10 armed windows DIED vs no module-image write 3/36 (8 %) — Fisher p = 0.00000007.** The
shipped `tutorial_launch_play.dll` (`.text 5151621d2154e454`, DEPLOYED) arms on **2 heap pointers**
and writes no module image; confirmed on the default recipe path, **5 of 6 armed windows survived a
full 600 s**. Rollback = `-Variant play-textpatch` (`433cf7d8f6a0770f`), which IS the measured control.
⚠ **What remains is NOT FK-7:** the **staging hazard, 22/82 launches (27 %)**, which kills the game
before the probe is injected and is untouched by this fix — it is now the dominant tutorial-route
failure. And **no shim-free tutorial run has ever been made**, so a game defect is unsupported but
not excluded.
⚠ **The residual is 3/36 and unexplained.** All three left NO artifact; the two instrumented ones
exit **`0x0000DEAD`** (a silent TerminateProcess sentinel that is NOT ours — our `Stop-Process` exits
`0xFFFFFFFF`, measured as a control). N=2, reproducible, unattributed.

★★★★ **FK-7 WAS RE-TESTED AND LARGELY ANSWERED (S112, 2026-08-07). START AT
`docs/s112-fk7-fk8-completion-review.md`, then `docs/s112-fk7-ab-results.md`; the S111 handoff below
is now history, not a plan.** Review verdict: **FK-7 substantially answered, NOT closed; FK-8 closed
and independently re-confirmed.** Three review findings that govern:
- ★ the "treatment survived by doing LESS" objection is **FALSIFIED** — identical `[PL]` init, MORE
  shim work per second, and the hero walks the SAME path in both arms (treatment reaches `x≈2841`,
  control dies partway at `x≈1379`);
- ★ **FK-8 re-confirmed DIRECTLY against ground truth** (N=11, median delta −6.2 s) — but with a
  **systematic ~6 s undercount** and **one unexplained −48.8 s outlier**, so per-death
  `SecondsSinceStart` carries occasional tens-of-seconds error. **Do not lean on narrow bands.**
- ⚠ **the camera family occurred 0 times in 41 launches, which is NOT evidence `KXFORMFIX` worked**
  (denominator is the 21 armed windows; at ~8 % P(0) ≈ 0.17).
★★★ **PHASE 3 FLOWN (2026-08-08) — the result is now overwhelming.** Matched 600 s holds, footprint
the only variable: `play-funcswap` (17,126 pointers) **0/8 died** and `play-funcswap-one` (**2**
pointers) **0/8 died**, all 16 surviving the full 600 s. Pooled across every non-`.text` arm:
**2/30 (6.7 %) vs the standing-`.text` control's 10/10 — Fisher p = 0.00000008.**
- ★★ **`build.ps1 -Variant play-funcswap-one` (`5151621d2154e454`) is the SHIPPABLE form** — it arms
  on **`swapped=2` heap pointers**, not 17,126, and RM_PLAY runs normally for 600 s. Target
  `ReceiveTickClient` was picked from a MEASURED settled-world profile (`play-funcswap-profile`,
  90 s window: 1549 hits/90 s ≈ once per frame). The old 4 s window only profiles world load, where
  every candidate reads `hits=1` and none is selectable.
- ⚠ **The footprint hypothesis is UNTESTED, not refuted** — 0/8 vs 0/8 cannot discriminate. Phase 3
  simply could not reproduce the residual; the phase-1 2/10 now looks like noise, since the LONGER
  600 s hold produced **0/16** (the opposite of a dose-response).
- ⚠⚠ **`KNOLOGINVT` FALSIFIED — do not re-run it.** Dropping `fo`'s slot-285 `.rdata` patch kills the
  route: **4/4 launches, 0/4 map loads**, fatal `ALokiGameMode::Login failed to Login` (exactly what
  the S62 source comment predicts), p = 0.0026. S62's purpose STANDS. The `.rdata`-is-caught-too
  question **cannot be tested by removal**; it needs a patch-then-immediately-restore design.
- **The staging hazard is now the largest open item on the tutorial route** (~25 % of launches die
  before the probe is injected; 6/22 in phase 3).
A pre-registered one-variable A/B on the tutorial route, **N = 10 armed windows per arm**:
**control (RM_PLAY's 600 s standing `.text` patch) died 10/10; treatment (the same shim with the
hook expressed as a heap `UFunction.Func` swap, zero module-image writes) died 2/10. Fisher's exact
p = 0.00071.** ⇒ **FK-7 is substantially OUR OWN standing `.text` patch.** Build:
`build.ps1 -Variant play-funcswap` (`badecc840bafee84`); control rebuilt from HEAD is
`433cf7d8f6a0770f`.
- ★ **The kill MODE differs, not just the rate.** Control deaths exit **`0xC0000005`** and leave the
  `runtime.dll+1` crashpad dump; the treatment death exits **`0x0000DEAD`** and leaves **nothing**.
  `0xDEAD` is NOT ours (no `TerminateProcess`/`ExitProcess` anywhere in the shim sources). ⇒ the
  project's "artifact-less death class" is **not all hangs** — some are silent kills, and holding an
  OS handle open across process exit recovers the code for free. Do this in every future harness.
- ★ **28/28 dumps this session were `OURS/protector`. ZERO game-defect dumps.** The dump that would
  be the first real FK-7 evidence still does not exist.
- ⚠ **The residual is 2/10 and is OPEN** — not a protector kill, no artifact. Leading suspect is the
  treatment's OWN footprint (it swaps 17,126 `Func` pointers); `-DKFSNAME=<name>` swaps one instead.
- ⚠⚠ **8 of 20 non-arming launches DIED DURING STAGING**, with only `gft`+`fo` resident and the probe
  never injected — before RM_PLAY's patch exists. So **"FK-7 is our PI hook" is too narrow.** `fo`'s
  ≤25.5 s `.rdata` slot-285 vtable patch is the leading suspect and is still CONFOUNDED with its own
  transient `.text` write. `KNOLOGINVT` **does not exist** (the S111 handoff cites it as if it did);
  neither did `KPLAYHOLDMS` until S112 added it (`-Variant play-hold300`).
- ⚠ **`build\tutorial_launch_play.dll` was ONE COMMIT STALE** (`513c6277c3ae88f3` vs HEAD's
  `433cf7d8f6a0770f`); `KWIREGAS` defaults to **1**, so the gap was live code, not dead. Archived as
  `build\tutorial_launch_play_a827ef9_ARCHIVED.dll`. **Rebuild `play` before any A/B against it.**
- ★ **Positive control that actually works:** `[PL] *** init complete ***` (`tutorial_launch.cpp:5190`)
  — fires ~100 %, is arm-symmetric, and catches a silent no-op in a non-`.text` arm. **Do NOT use the
  mandated 3× `play_novtguard` gate**: it fires on an ~8 % event and voids ~4 sittings in 5.
- Harness: `configs/fk7-ab-run.ps1` (one armed window) + `configs/fk7-ab-campaign.ps1` (alternates on
  ARMED WINDOWS, not launches) + `tools/crashtri/fk7_ab_analyze.py`.
- ⚠ `tools/crashtri/fk8_classify.py` dedupes UECC dumps on the constant `"UEMinidump"` → reports
  **1 distinct report for 105 directories**. Do not point it at `Saved\Crashes`.

Historical (S111): `docs/s111-FK7-HANDOFF.md`, then `docs/NEXT-SESSION-PROMPT.md`. S111 (2026-08-07) measured that a **standing `.text` write is what
makes the protector kill the process** (patch standing 11/12 vs no patch 0/5, p = 0.00097; a
*permanent* heap-**bytecode** patch is free, 0/9). And **`tutorial_launch.cpp:6511-6513` (RM_PLAY)
holds a 5-byte `.text` patch at `ProcessInternal` for 600 s** — `g_done` is never set in RM_PLAY —
which is the exact condition measured at **~88 % lethal**, standing for the entire sitting and
bracketing the whole observed FK-7 death spread (87–524 s). ⇒ **The primary hypothesis is now that
FK-7 is largely OUR OWN PI hook.** Audited: only **11** death records survive every contamination
filter, **ten of them from one 15-hour stretch**, and **all are shim-mediated** —
`log_forceopen_tutorial_url == 2` in 15/15, i.e. **no shim-free tutorial run has ever been made.**
⚠ Also: the mandated 3× `play_novtguard` control gate would declare a sitting VOID ~4 times in 5
even when everything works (the camera family is ~8 % per staged launch) — fix the control before
spending launches.

The short version, because it has already cost two sessions:
- **The FK-24 watchpoint probe was killing the game**, and its crash was recorded as a
  game crash for a whole session. Dump `166396E2` (DR mode) and `FED1F952` (page mode) are
  both **the shim self-killing**, not FK-7. Do not feed them to `crash_census.csv` analysis.
- **S107's "the watchpoint is VOID → escalate `wprobe`→`wprobe2`" was unfounded.** The DR
  watchpoint fired fine (127/128 threads armed, GameThread among them). The writer of the
  `0x01` byte at `PCM+0x420` is **still NOT named**; FK-24 is OPEN.
- **FK-7 is OPEN.** Zero reproduce-then-repair runs exist. The `play_novtguard` positive
  control is MANDATORY and a **quiet control means the sitting is VOID, not a pass**.
  Hold to **T+220–250 s, NOT T+300 s.** ⚠ **The hold survives; the "~285 s" number does NOT** (S111,
  FK-8 corpus mining). MEASURED over 114 distinct death records: one late-kill mode is **240–295 s,
  N=15, median 264 s — only 4 of 15 are ≥283 s, and 4 of 15 are asserts** (asserts are not
  anti-tamper kills). ⚠ **That band describes ONE CLASS, not the population — do NOT hold to it**
  (S111 reconciliation, `docs/s111-fk8-s110-reconciliation.md`). On the **crashpad** class, tutorial
  route, N=13 — which contains every S110 sitting — deaths run **87–524 s, median 283, and 7 of 13
  fall OUTSIDE 240–295**, four of them above it (336 / 432 / 491 / 524 s). Two of those four are not
  S110 runs, so the tail was already in FK-8's own corpus. S110's own "budget ~330 s" is likewise too
  tight. ⇒ **No `T+<n>` rule survives; use the staging-invariant anchor below and the fault family.**
  (The two sessions' clocks were cross-checked and agree to 2–3 s, so this is a real spread, not a
  clock artifact.) Worse, `SecondsSinceStart` is the **launch** clock and therefore contains the
  operator's staging schedule, which moved **+33.0 s** between the July and August batches — so any
  `T+<n>` rule silently drifts when `-InjectGapSeconds` changes. **Prefer the staging-invariant form:
  hold ≲50 s past `Load map complete …/LVL_Tutorial`.** Detect the kill by **fault family**
  (`RIP == runtime.dll base + 1`, EXECUTE, `ExceptionInformation[0]==8`), never by elapsed time.
  See `docs/fk8-crash-timing-mined.md` §2.3.
- ⚠ **`play`'s `.text` hash has moved THREE times. Current: `513c6277c3ae88f3`** (S110 `KANIMREF`).
  `7bc4df9236ead0ac` was `play` only between S109 and S110; `ae532866e15fd8ac` only between S108b and
  S109; `a67239a0d83d9300` is `play-statictest`. Docs citing any of those as "the candidate" are stale.
  ⚠ `play-strictroot` / `play-noanimref` share a 161,792-byte `.text`; historically `play` /
  `play-earlywalk` shared identical whole-file AND `.text` SIZES (which is part of why earlywalk was
  DELETED in S110) — **only the hash separates such pairs. Diff `.text`, never size.** Use
  `tools/sigbypass-mod/verify_dll.py` or the section-hash snippet in `docs/s109-dump-forensics.md` §23.
- ⚠ **`KGCROOT` was silently INERT from S106 until S109.** Its root-bit corroboration used
  `AND(native classes) & ~OR(sampled ordinary objects)` on the false premise that ordinary objects are
  never rooted; **one** rooted sample in 64 vetoed the correct bit, so nothing was ever rooted. Fixed
  (frequency test; `-DKGCROOTSTRICT=1` restores the old one). ⚠ **Fixing it did NOT stop the asset
  collection** — the run AnimSequence is still collected with a verified `flags -> 40000004` readback,
  if anything sooner. So "rooting keeps it alive" is **not established in this build**.
  See `docs/s109-dump-forensics.md` §22-§24.
- ★★★ **THE ANIMATION THREAD IS SOLVED (S110) — read `docs/s110-item-watch-gc-mechanism.md` before
  re-opening any of it.** The run anim really IS garbage-collected (full `BeginDestroyed →
  FinishDestroyed → LowLevelRename(NAME_None) → FreeUObjectIndex`, slot reissued later), so "torn down
  out of band" is ELIMINATED. **The poked RootSet bit is INERT** — a phase-locked experiment (only the
  injection phase varied) gives leads of **0.15 s / 2.9 s / 33.1 s from poke to the next GC pass, and
  the asset died at that pass every time**; in the last it sat through six clean heartbeats and died
  708 ms after the flip, so it is not a race. **Do not "fix" this by rooting harder.**
  **THE FIX = `KANIMREF` (default ON in `play`)**: park the asset in the body component's unused
  `AnimationData.AnimToPlay` UPROPERTY so the traversal reaches it — offsets resolved BY NAME, write
  readback-verified. CONFIRMED: re-marked at **two** consecutive GC passes, zero `[GCW]` lines, and
  `PlayAnimation(run/idle, loop) ok` cycling **at the default `KAUTOWALKATMS=20000`** — so
  `play-earlywalk` (which only RACED the collection) was **deleted**; `-DKAUTOWALKATMS=<ms>` still
  works for a one-off. Control arm: `play-noanimref`.
  ⚠ Also: **"Unreachable" is not a sticky bit in this build.** Reachability is an alternating flag
  rotating through bits 0/1/2, flipped population-wide each GC pass — which is what S109's unexplained
  `flags=00000004` / "bit 1 on 81% of ordinary objects" actually was, and it gives a free read-only GC
  clock (`tools/re/item_watch.py --marker`, ~61.1 s period).

### Before touching anything WebSocket- / notification- / server-push-shaped
★★★★★ **THE `/lobby` ENVELOPE — EVERY FRAME WE EVER SENT THERE WAS SILENTLY DROPPED, NOW FIXED
(S117, 2026-08-13). Read `docs/fk15-lobby-fragment-defect-20260813.md` FIRST.**
The client asks for message delimiters in its WS handshake and we never honoured them:
`X-Ab-EnvelopeStart: LbS` / `X-Ab-EnvelopeEnd: LbE` (literals `.rdata 0x8604890` / `0x86048A8`).
It stores them as the FStrings at **`lobby+0xA8` / `+0xB8`**, and `Lobby::OnMessage`'s completeness
check (**`.text 0x4b35a80`**, gating the fragment log at `0x4b0adf8`) takes the no-framing fast path
**only when BOTH are empty**. MEASURED before the fix: **14 `Raw Lobby Response` → 14
`Message fragmented` → 0 dispatches.** `Type: %s` (`0x04B0B12B`) had **never fired**.
⇒ **Our `listOfFriendsResponse` / `setUserStatusResponse` etc. were NEVER parsed**, and all five
2026-06-29 probes were buffered the same way — that is the mechanism behind FK-15's "silent
absorption", and it was on OUR side.
★ **This is also why the messenger probes worked and the `/lobby` ones did not** — the messenger
negotiates **empty** markers (`envelope=[""..""]`), so it needs no envelope. The two channels were
never comparable.
**FIX:** `ws.Conn.WriteText` wraps with the socket's own negotiated markers (a no-op on the
messenger); `WriteTextRaw` keeps the unwrapped form for probes. **Result on reconnect: dispatch
0 → 4**, four responses parsed for the first time ever.
★★★ **THE FULL 33-TYPE SWEEP THEN RAN CLEAN — 33/33 RECEIVED, PARSED AND ROUTED**
(`docs/fk15-sweep-33-types-20260813.md`). Dispatch 5 → 38; **0** parse errors, **0** deserialize
failures, and `Message fragmented` did NOT grow. ⇒ **the `/lobby` receive channel is fully
functional for the first time in this project's history.**
⚠⚠ **CORRECTED same day — do NOT read this as "33/33 reached a bound handler case."** That claim
rested on the absence of `Error; Detected of type notif but no specific handler case assigned`,
and **that absence is not evidence**: those two error strings are **not plain `UE_LOG`s** — they are
`Printf`'d into an FString and pushed through a virtual on `Lobby+0x218`, so they may never reach
the log. **Disproof:** a bogus type (`dsNotice-PLACEHOLDER`, which exists nowhere in the binary)
produced the IDENTICAL trace including **`Type: dsNotice-PLACEHOLDER`** ⇒ **`Type: %s` is logged
BEFORE the handler lookup.** The 33==33 jump-table corroboration stands on its **static** evidence;
the sweep did not confirm it live.
★ **Free control, reuse it:** push a type that cannot exist. If your "handler found" detector reads
the same for the bogus type, it is not measuring what you think.
★★★ **SETTLED STATICALLY INSTEAD (`docs/fk15-handlenotif-jumptable-20260813.md`): ALL 33 CASES ARE
REAL.** `Lobby::HandleNotif`'s jump table (33 dword RVAs at `.text 0x4b04978`; index = `enum-1`,
default `0x4b048f9`) has **33/33 entries pointing into `.text` and ZERO equal to the default**
(32 distinct; idx 17/18 share the banned/unbanned pair). ⇒ **`dsNotif` reaches a real case body.**
A case = `{delegate, type descriptor}` handed to one shared deserialize+broadcast helper
(`0x4AD6020`); idx 23 verified live: `lea rdx,[rdi+0x1550]; lea rcx,[→0x9FFE6F0]; call 0x4AD6020`.
⚠ SUPERSEDED BY S118: the "one shared helper" is really **three** (`0x4AD6020`/`0x4AD6220`/`0x4AD6420`),
and "idx 23 = dsNotif" is **no longer inferred — it is MEASURED** (see the S118 block below).
★★★★ **AND THE SWEEP DECRYPTED THEM: 9/33 → 33/33 case bodies.** Those pages had NEVER executed in
any of the 68 prior dumps. ⇒ **driving a code path from the backend FORCES `.text` decryption for
offline RE** — a steerable version of "coverage rises with what the game has run". Banked in
`dumps/lobby-dispatch-decrypted/`. **Reuse this: push the messages, then `dumpimage`.**
★★★★★ **ANSWERED — THE DELEGATE IS UNBOUND. NOTHING LISTENS**
(`docs/fk15-delegate-binding-20260813.md`). The live `Lobby` object was found at
**`0x1D251AA1C80`** (this session; ASLR-dependent, re-derive per launch) via the structural
signature the ctor guarantees — an `FString` "LbS" with an `FString` "LbE" exactly 16 bytes later —
and **validated on four independent offsets that were not part of the search**: `+0x88` Num=**19**
(`"X-Ab-EnvelopeStart"`), `+0x98` Num=**17** (`"X-Ab-EnvelopeEnd"`), `+0xA8`=`"LbS"`,
`+0xB8`=`"LbE"`.
`+0x1550` (case 23) and `+0x1510` (case 19) are BOTH UNBOUND [M] — and so is `+0x11b0` (case 8).
⇒ **Pushing those notifs can never have an effect in this build. The route is closed at the client's
SUBSCRIPTION layer**, not at routing/parsing/deserialization, all of which were proven working.
⚠ That doc's "16 BOUND (entries=3), 46 UNBOUND" is **SUPERSEDED** — the count was truncated AND the
stride was wrong. See below.

★★★★★ **THE MAP IS DONE — 7 OF 33 TYPES CAN MOVE THIS CLIENT (S118, 2026-08-13). Read
`docs/fk15-bound-delegate-map-20260813.md`.**
| enum | case | delegate | type |
|---|---|---|---|
| 2 | 1 | `+0x228` | **`disconnectNotif`** |
| 16 | 15 | `+0x12d0` | **`userStatusNotif`** |
| 25-29 | 24-28 | `+0x1630`/`+0x1640`/`+0x1650`/`+0x1660`/`+0x1670` | **`accept`/`request`/`unfriend`/`cancel`/`rejectFriendsNotif`** |
★★★★★ **ALL 7 HAVE BEEN FLOWN AGAINST THE LIVE CLIENT — 6 produce VISIBLE UI changes**, 1
(`disconnectNotif`) is a controlled negative vs a matched bare-drop arm. The map is **predictive on
every type it named**: friends list, presence, and both pending-request lists are all drivable from
the backend. `requestFriendsNotif` → request card + IAM resolve (+276 ms) · `acceptFriendsNotif` →
friend added (+526 ms resolve) · `unfriendNotif` → row removed · `cancelFriendsNotif` → `INCOMING
1→0` · `rejectFriendsNotif` → `OUTGOING 1→0` · `userStatusNotif` → presence both ways.
★★ **THE BEST INSTRUMENT ON THIS SURFACE IS THE FRIEND REQUESTS MODAL** — it has explicit
`INCOMING`/`OUTGOING` **counters**, so it is countable, separates the two pending lists, and reads
out a precondition directly. Prefer it to the transient corner card.
★★ **The client MUTATES ITS OWN SOCIAL STATE from a notif; only a refetch re-imposes ours.** Shown
twice, in opposite directions: `acceptFriendsNotif` added a friend without any
`listOfFriendsRequest`, and a reconnect then wiped it; `rejectFriendsNotif` removed an outgoing
request **while we were still serving it**. ⇒ **pushed social changes are TRANSIENT unless the
backend also serves them** — build both halves (push for the event, response for durability).
★ **Staging knobs, all opt-in and empty by default** (`server/internal/lobby/lobby.go`):
`AGS_PROBE_FRIEND` / `AGS_PROBE_INCOMING` / `AGS_PROBE_OUTGOING`. ⚠ Prefer building a precondition
with a PUSH where possible (an incoming request comes free from `requestFriendsNotif`) — same
mechanism under test. Only `reject` needs a knob, because nothing but the client can populate the
outgoing list.
The other 26 broadcast into a delegate with **no subscriber** — incl. `dsNotif`, `matchmakingNotif`
and every `party*`. ★ **21 of the 23 bound delegates belong to ONE `USocialManager`** (1 to
`UMyActivityManager`, 2 raw-method to Lobby itself), which is *why* the reachable surface is exactly
the friends/presence family. `BoundNotifTypes` in `server/internal/lobby/vocabulary.go` is the list.
⚠ **A slot is SINGLE-CAST `FDelegateBase` `{void* Alloc; int32 DelegateSize; pad}` — "entries=3" was
NEVER a subscriber count**, it is an allocation size in 16-byte units, identical on every bound slot.
`+0xC` is padding holding stale heap garbage (reads `0x1D2` even when UNBOUND), which is what made
it look like a `TArray{Data,Num,Max}`. Boundness = `DelegateSize != 0` then a virtual call.
⚠⚠ **ENUMERATE AT 8-BYTE STRIDE.** Members sit at offsets ≡ 8 (mod 16) — the same alignment that
puts LbS/LbE at `+0xA8`/`+0xB8`. A 0x10-stride scan cannot see `+0x228`, which is **`disconnectNotif`**
⇒ the miss changed a conclusion (6 vs 7), not just a tally. Both S117 and the first S118 scan had it.
⚠ **Identify a delegate by its allocation starting with a module-address VTABLE, never by allocation-pool
adjacency** — that inference misread a real delegate (`+0x1a00`) as an FString. Controls: a known
delegate must be accepted AND a known FString buffer rejected.
⚠ **The S117 bound list was truncated at 12 of 16 and ended in a literal `…`.** Four hidden offsets
are four of the seven answers; joining against it yields 2 hits. **Never join against an ellipsis.**

★★★ **THE ENUM→NAME MAP IS MEASURED, and it CORRECTS the shipped vocabulary.** Read live from the
`TMap<FString,uint8>` at `.data 0x9FFE2D0` (`Elements.Data=0x1D230AF9280`, ArrayNum=**33**, dense) —
the exact byte `HandleNotif` dispatches on; the 33 values are a perfect permutation of 1..33.
**`.rdata` order is CONFIRMED for enum 1-31 and REFUTED at 32-33**: enum 32 = **`signalingP2PNotif`**
(not `errorNotif`), enum 33 = **`errorNotif`**, and **`messageSessionNotif` is ABSENT from the v1 map**
(it is not undispatchable — prior RE puts it on a separate handler at `.text 0x4B07E80`, unverified).
Root cause: two off-by-one window errors that **cancelled into a plausible 33** — `signalingP2PNotif`
sits 0x128 below the lower bound, `messageSessionNotif` exactly ON the upper bound.
⚠⚠ `vocabulary.go` warned about this exact failure mode and then committed a different pair of it,
**and `push_test.go` asserted the false claim** — the test that would catch the error had ingested it
(rule 9). Both fixed; `BoundNotifTypes` + a guard test added.
★★ **`idx 23 == dsNotif` is MEASURED** — the shape-A "descriptor" is a plain `FString` whose buffer
IS the type name (`0x9FFE6F0`→`"dsNotif"`). S117's unbound finding is unaffected.
⚠ **Hand arithmetic is an instrument.** "Recompute, never retype an RVA" is not enough: an
addition done by hand dropped a carry and read one page low, and the page below decoded as
*plausible* UObjects — briefly written up as a real anomaly. **Recompute with a machine.**
★ **Keep the process alive.** S118 was nearly free because the S117 process was still running (same
ASLR, same heap, decrypted pages, live `/lobby` socket). Check `Get-Process` before re-deriving.

★★★★★ **AND IT WAS FLOWN — A PUSHED NOTIF DROVE THE CLIENT, FIRST TIME IN THIS PROJECT.** Pushing
`requestFriendsNotif` with a **fabricated** `friendId` produced, **+276 ms later**,
`GET /iam/v4/public/namespaces/supervive/users/f15118aaaa…` — the client resolving a user that exists
only in our frame. ⇒ **receive → parse → route → deserialize → broadcast → SUBSCRIBER ACTS**, closed
end to end. Three arms on one socket: bound+payload → **GET**; bound+**no fields** (the S117 sweep) →
nothing; **unbound** `dsNotif` with a RICHER 11-field payload → nothing (its MatchID appears once in
the whole capture — our own push line). That endpoint is hit **1 time in the entire 7 MB capture**, so
it cannot be background traffic. ⇒ the bound/unbound model is **PREDICTIVE**.
⚠⚠ **A sweep of bare `{"type":X}` frames CANNOT detect a live handler** — arm 2 proves it. The S117
33-type sweep's silence is therefore evidence about NOTHING; do not cite it per-type.
⚠ Payload field names matter and fail SILENTLY (`JsonObjectStringToUStruct` ignores unknown keys):
accept/request/unfriend use **`FriendId`**, cancel/reject use **`UserId`**.
★★★★ **AND `userStatusNotif` DRIVES THE FRIENDS UI, BOTH DIRECTIONS** — a friend rendered
`ONLINE` and `OFFLINE` purely from pushes.
⚠⚠ **THE RECIPE DIFFERS PER DIRECTION, AND THIS IS THE WHOLE TRICK: `→ OFFLINE` REQUIRES OMITTING
`activity`.** MEASURED, single-variable: `offline` + a valid activity blob = **no change** (×2);
`offline` with `activity` **omitted** = **flips to OFFLINE**. ⇒ **the activity blob OVERRIDES
`availability`** ("has an activity ⇒ render online"). Sending both is self-contradictory and the
client believes the activity — a silent, inexplicable null if you don't know this.
⚠ History worth keeping: "both directions" was first published **unobserved** (asked for
confirmation, was redirected, wrote it up anyway — *a pending question is not a result*,
method-rules S118-g) and was RETRACTED. The retraction is what generated the hypothesis that found
the override rule. **Retracting beat defending.**
Precondition: the client needs a ROW to render into,
so serve the friend (`AGS_PROBE_FRIEND=<userId>` → `listOfFriendsResponse`); the first two pushes'
null was **uninterpretable, not negative** (rule 11). We still do NOT answer `friendsStatusRequest`,
which is what keeps it single-variable: the ONLY source of "online" is our push.
★★ **READ THE CLIENT'S OWN `setUserStatusRequest` FOR THE WIRE FORMAT — do not guess it:**
`availability: online` (**lowercase** enum name) and `activity` is **base64-encoded JSON**, not a
string: `{"a":"Menus","cV":"…","pId":"party-<id>","pQs":[],"pO":0,"pS":1,"mPS":3,"rk":0,"rkP":0,
"r":[],"avId":"","t":[],"dsId":""}`. `a` is an **`ELokiActivityState`** enum; a wrong value sinks the
whole activity struct and the update with it.
★★★ **FREE INSTRUMENT: `LogJson` echoes the REJECTED VALUE and names the property + enum**
(`Unable to import enum ELokiActivityState from string value S118PROBE for property A`). That is the
antidote to this surface's worst trap — unknown keys are ignored silently, so a mistyped field reads
as "dead handler". **Watch `LogJson` on every push.** ★ A failed parse is a STRONGER receipt than a
silent success: it proved the `SocialManager` subscriber runs by quoting our own data back, with zero
UI dependency.
⚠⚠ **`ags` TRUNCATES `docs/capture.log` on restart** (measured 7.87 MB → 66 KB). **Back it up before
restarting** or the run's evidence is destroyed. Cert continuity is safe: `EnsureCert` reuses
`certs/root.crt`, so the same `-certs` dir serves an identical cert and `cacert.pem` stays valid.

### Before touching anything news- / banner- / announcement- / CEF-shaped
★★★★★ **FK-17 IS SETTLED (S119, 2026-08-14). The lobby NEWS BANNER renders from our backend with
ZERO injection — and NO menu surface is a web page.**
- ⛔ **The render-path hypothesis is REFUTED. Do not re-open it.** Three independent instruments:
  exactly **1 of 68,303** shipped assets embeds a `WebBrowser` (`WBP_UI_Login_Screen_AwaitingLegal`,
  the login ToS modal) and its blueprint never sets a URL; a validated `GUObjectArray` walk over
  195,084 objects finds **one** `UWebBrowser` — the CDO; and `UWebBrowser` is the only browser-owning
  UClass in the whole reflection table. News / Event Hub / Referral are native UMG with live native
  managers. The `LogWebBrowser: Deleting browser for Url=.` line at every startup is that vestigial
  login modal, **not our fault and not a lead**.
- ★★ **The real lever is `ClientConfiguration.BannerConfigs`**, served by `handleClientConfig` in
  `server/internal/loki/loki.go`. Chain: `BannerConfigs` → `LokiClientBannerConfig.Configs`
  (`TArray<LokiTimespanBannerConfig>`) → `.Banners` (`TArray<LokiClientBannerData>`, 16 fields:
  text/colors/`SplashImageURL`/`IconURL`/`ActionType`/`ActionURL`). CONFIRMED live: our banner text,
  our colors, our splash image, and clicking it opened our own page in the OS browser
  (`ActionType: WebURL` → `UKismetSystemLibrary::LaunchURL` — the SYSTEM browser, never in-game).
- ★ `SplashImageURL` accepts an ABSOLUTE url: `BPFL_BannerConfig::"Get Content Service Asset URL from
  Path"` passes anything starting `http://`/`https://` through verbatim (`bRequiresAuth=false`);
  otherwise it prefixes `GetServiceAddress("contentservice") + "/content-service/assets/"`.
- ⚠⚠ **THE BANNER IS GATED BEHIND TWO GATES, BOTH IN `WBP_UI_PlayScreen_LobbyV2::ExecuteUbergraph`:**
  `[7] EX_JumpIfNot(IsMatchHistoryLoaded)` then `[10] EX_JumpIfNot(GetMissionsModel()->bAllMissionLoaded)`
  then `[11] InitializeBanners()`. Gate 1 is `[MatchHistoryManager+0x68] >= -1` (sentinel **-2** =
  never loaded) — opened by serving `FMatchHistory{ID,Version,Matches:[]}`; an EMPTY `Matches` is
  enough and keeps the risky 15-field `FMatchHistoryEntry` out of it. Gate 2 is the missions flag
  above. **Both are HTTP-openable; neither needs a shim.**
- ~~⚠ ORDER-DEPENDENT: `InitializeBanners` runs from `BP_OnActivated`; if the play screen activates
  before both gates open, nothing re-triggers it that launch.~~ **RETRACTED 2026-08-14 — FALSE, and it
  was never measured.** It was inferred from a missing splash fetch on a default launch, i.e. from the
  CACHED-IMAGE null described in the next bullet — the very artifact identified minutes earlier and
  then reasoned from anyway (instrument-artifact pattern, 44th instance). **MEASURED with the `?v=`
  nonce forcing a cache miss: on a plain default launch with `pushes=0` on both sockets and no manual
  intervention, the gates open at `00:42:43` and the client fetches the splash at `00:43:06` — 23 s
  later, unprompted.** The chain self-triggers; there is nothing to fix. ⇒ **Do not build a
  "re-trigger" push for this.**
- ⚠⚠ **INSTRUMENT TRAP — it produced BOTH a false "regression" AND a false finding.** The client
  CACHES downloaded banner images to `%LOCALAPPDATA%\SUPERVIVE\Saved\ImageCaches` (+
  `ImageCacheIndex.json`). After the first render the banner draws **with no HTTP request at all**, so
  "no splash.png fetch in `capture.log`" is UNINTERPRETABLE, not negative. It first read as a
  regression; then, uncaught, it became the fabricated "order-dependence" claim retracted above.
  ★ **FIXED PERMANENTLY — the banner image URLs now carry `?v=<bannerAssetNonce>`**
  (`server/internal/loki/loki.go`), a token that changes once per **ags start** and is constant within
  a run. Each run therefore takes exactly one cache miss per image, so a splash fetch is real positive
  evidence the carousel populated **and its absence is interpretable again**, while the client's cache
  still works normally inside the run. **Do not remove the `?v=` — it is the instrument.**
- ★★ **`NotifyResource` drives a refetch of ONE resource with no reconnect** — measured on
  `/progression/players/{id}` (client refetched 0.8 s later, `User-Agent: Loki/UE5-CL-0`). That
  endpoint is otherwise fetched ONCE per session, so this is how to iterate on it without relaunching.
  ⚠ Pass EXACTLY the version the document will carry: too low is ignored, too high causes an
  unbounded refetch loop (`server/internal/lobby/push.go`).
- ⚠ **ALWAYS CHECK `User-Agent` ON A CAPTURED REQUEST.** Our own `curl` verification calls land in
  `docs/capture.log` and read exactly like client traffic; the game is `Loki/UE5-CL-0`, an
  `ActionType: WebURL` click is `Mozilla/…Chrome/…`. This nearly produced a fabricated headline.

### Before touching anything feature-toggle- / UI-gate- / hidden-surface-shaped
★★★★★ **A-14 IS SETTLED AND FLOWN (S121, 2026-08-15). Read `docs/s121-toggle-fix-confirmed.md`,
then `docs/s120-feature-toggles.md`.** The declarative UI-gate channel works end to end from the
BACKEND — no shim, no injection, no `.text` write.
- ⚠⚠ **TWO TOGGLE SYSTEMS. Never confuse them.** `ULokiGameFeatureToggles::Get(ELokiGameFeatureToggle)`
  is **enum**-keyed, names live in the exe, readiness is per-PlayerController at round-start (S85);
  the 149-member list is `tools/re/out/game_feature_toggle_enum.txt` (**state the unit: 149 toggles,
  151 enum values** — `Count` and `_MAX` are not features). `UClientConfigManager::IsFeatureEnabled
  (FString, bool)` is **string**-keyed and read straight from the `featureToggles` map we serve; its
  keys are Blueprint bytecode literals / asset properties and are **ABSENT from the exe**, which is
  why no binary scan ever found them. **All five keys served S73→S120 were from the WRONG one.**
- ★★★★★ **THE BUG WAS ONE WORD: `ConfigKey` is `"enabled"`, not `"default"`.** The gate is a reusable
  declarative widget `WBP_UI_ClientConfigVisbilityToggleWidget_C` (the typo is the game's):
  `Map_Find(FeatureToggles, FeatureKey)` → `Map_Find(entry.Config, ConfigKey)` → `ToBool`, each miss
  falling back to the asset's own `IsEnabledByDefault`. We wrote `Config["default"]` from S73, so
  **every toggle this project ever sent missed and silently fell back.** Fix = send BOTH sub-keys
  (`FFeatureToggle.Config` is `TMap<FString,FString>`, so the extra entry is inert).
  ⚠ **Do NOT drop `"enabled"` to tidy up.**
- ★★ **CONFIRMED TWICE IN ONE FLIGHT [M]:** `exchangetokens` → the **STORAGE** tab appears in the
  STORE nav bar (`FEATURED · BUNDLES · SKINS · ACCESSORIES · SUPPORTER PACKS · STORAGE · REDEEM`) and
  renders a real page; `DebugBattlepass` → **DEBUG BATTLEPASS** appears on the main-menu rail. Two
  different keys, two different screens, one payload change.
- ★ **THE SAFETY CONTROL IS BUILT INTO THE STORE NAV BAR — use it every time.** `supporterpacks` and
  `redeemcode` have `IsEnabledByDefault=true`, so SUPPORTER PACKS and REDEEM must stay visible; if
  either vanishes you are writing a value that turns things OFF. Both held [M].
- ⚠ **`bDefault` / `IsEnabledByDefault` decides whether serving a key can do ANYTHING.** Keys that
  already default `true` (`EmoteSFX`, `KillStreakAsRomanNumeral`, `voicechat`, `ChatLobby`,
  `CustomGameList`, `RankedDisplay`, `mailbox`, `EventHub`, `party.fill`, `XPBoosts`, …) are on
  without us — **sending them could only ever turn something OFF. Never send them.**
- ★★★★★ **THE DECLARATIVE SWEEP IS COMPLETE (S121) AND THE VOCABULARY CLOSES WITH NO REMAINDER:
  50 keys = 12 served + 33 `IsEnabledByDefault=true` (NEVER SERVE) + 1 withheld
  (`BypassTutorialAndOnboarding`, which REMOVES a surface) + 4 candidates, all 4 now flown.**
  ⚠ **"33 keys remain unswept" is WRONG** — the remainder was **4**; 33 is the *never-serve* count,
  the same number in a different role. Re-derive counts, never carry them.
  **Final: 14 of 15 served declarative keys read our value** (`served-value-read=23`, instances
  133→136). The last two (`ServerSelect*`) were NOT a toggle problem — see the region block below.
  ★★ **The 3 that do not are NEVER-EVALUATED, not "off" — and a row with `IsEnabledByDefault=true`
  AND `enabled=false` is IMPOSSIBLE for an evaluated widget** (default true means both a missing
  FeatureKey and a missing ConfigKey fall back to true). That is a **free per-instance "this gate
  never ran" detector.** ⇒ **THE SIBLING TRICK:** a default-FALSE key reading disabled is ambiguous
  alone, but if the SAME ASSET hosts a default-TRUE toggle that also reads disabled, the whole asset
  never evaluated. MEASURED: `WBP_UI_RegionSelect_Entry` hosts `ServerSelectCheckbox` (default true,
  reads disabled) with `ServerSelectRegionRoutes`/`ServerSelectNetworkAcceleration` ⇒ the
  region-select screen was never built and those two are **[M] not a negative**.
  ⚠⚠ **The old `gate-off=78` contained ZERO demonstrated gate-offs** — it is 46 provably-never-
  evaluated + 32 ambiguous. `toggle_readout.py` used to print `GATE OFF` for all of them (the
  instrument carrying the defect it exists to detect); it now prints `NEVER EVALUATED` /
  `AMBIGUOUS`. **Re-read any older "gate off" claim against this split.**
  ⚠⚠ **`DropScreenTitles` IS NOT A TOGGLE QUESTION — do not re-attempt it as one.** Its widget
  (`WBP_UI_PredropScreen_PlayerEntry`) has no default-true sibling, and [M] the only drop-related
  lines in a full live session are `LogActorPooling` registering `BP_DropPod` as **poolable at
  startup** — registered, never instantiated. The drop phase never ran in 842 logs and the tutorial
  cannot produce one (`LVL_Tutorial` spawns the hero directly, no drop plane). ⇒ **not "expensive",
  NOT TESTABLE by any current route**; its precondition is the deploy/drop route (**FK-1**, the four
  empty server-authority stubs). Pick it up free if a real match with a drop phase is ever reached.
  ⚠ It is **not an FK** — nobody holds a false belief about it; an open unknown does not belong in
  the FALSE_KNOWN register.
- ★★★★★ **CONFIG CHANGES NEED NO RELAUNCH — MEASURED, pre-registered, single-variable.** Restarting
  **`ags` only**, with the game running continuously (68 min uptime), flipped exactly the 3 treatment
  keys while **all 43 control keys stayed unchanged**; the client re-adopts within its ~30 s poll.
  ⇒ **toggle widgets DO re-evaluate on `OnClientConfigUpdated`.** Sweep inside one live session
  instead of one launch per batch.
  ⚠ **Predict +1 per KEY, not per instance** — the second instance of each is the archetype and
  never evaluates. A +6 prediction came back +3 for exactly that reason.
- ⚠ **`SeasonalBattlepass` is env-only on purpose.** Flown alone: `Error` 8→8, `Fatal` 0, `LogJson` 0,
  game alive, `served-value-read` +4 — **so the feared hard error did NOT occur AT THE MENU.** But
  the surface it gates is the **end-of-game** pass, which the menu cannot reach, so that is a much
  weaker claim than "safe". Keep it out of the default set; opt in with
  `AGS_UI_TOGGLES_EXTRA=SeasonalBattlepass` and re-test at EoG before promoting.
- ★ **`AGS_UI_TOGGLES_EXTRA="a,b"` serves extra keys with no rebuild**, for flying a risky key in its
  own attributable batch. It folds the extras into the eTag automatically — a runtime payload change
  has no code edit at which to hand-bump it, so without that the knob would silently reproduce the
  stale-eTag trap.
- **Vocabulary [M]:** 10 bytecode keys (30 call sites / 26 locals / 21 assets) + **50 declarative
  `FeatureKey` values** (asset properties — a plain JSON scan, invisible to a bytecode census).
  ⚠ **GAME DATA BUG:** four sites declare `"ArmoryItemProgression "` **with a trailing space**. Both
  spellings are served. **Do not "fix" it** — the typo is in the shipped asset.
- ★★★★★ **AND IT REVEALED HIDDEN *BACKEND* SURFACE, NOT JUST UI — the biggest result of S121.**
  Enabling `leaderboards` made the client call **`GET /player-stats/leaderboard`**,
  **`GET /mmr/leaderboard`** and **`GET /player-stats/players/{id}`** — endpoints it had NEVER been
  observed to call in this project's history, all landing on a `{}` catch-all. ⇒ **treat every dark
  toggle as a probe for unseen endpoints.** ★ The query string is a **self-describing contract**:
  every parameter maps 1:1 to a visible dropdown, so changing a dropdown and re-reading
  `capture.log` enumerates the vocabulary at zero RE cost.
- ★★★★ **THE LEADERBOARD IS IMPLEMENTED AND RENDERS** (`server/internal/interactive/leaderboard.go`;
  knob `AGS_LEADERBOARD=0`). Screenshot-confirmed: `#1. · 42 · Reviver#6612`, `RESET IN 01:00:24`.
  ⚠⚠ **THE RESPONSE MUST ECHO THE REQUEST OR IT IS PARSED AND SILENTLY DISCARDED** —
  `"Current Leaderboard Is Stale"` tests
  `HeroName != heroId.PrimaryAssetName || StatCode != statKey || QueueID != queueKey || age > 60s`.
  **The request sends `heroId=Hero:All` but you must echo the BARE `All`.** A wrong echo is
  indistinguishable from a parse failure. No envelope (callback `0x5809760` has zero instructions
  before `JsonObjectStringToUStruct`). Required: `StatCode`, `QueueID`, `HeroName`, non-empty
  `Entries` (the else-arm IS the "No one has claimed a spot" widget). `Value` is `FCeil`'d; **row
  order is array index, not `Rank`**; an unresolved `PlayerID` still renders. `HeroCounts` is a
  `TMap` → **one hero portrait per key** (measured: 2 keys ⇒ exactly 2 icons).
  `statCode ∈ {kills,wins,damage,healing}`; `period ∈ {daily,weekly}` (FRIENDS/RANKED are a
  different widget on `/mmr/leaderboard[/friends]`).
- ★★★★ **`GET /mmr/leaderboard` IS ALSO IMPLEMENTED AND CONFIRMED LIVE (S121)** — the RANKED side
  tab renders `#1. · Reviver#6612 · 1,850 RP` from our `Placement`/`PlayerID`/`Rating`.
  Verified with UA discipline (`Loki/UE5-CL-0`, not our own probe), 0 `LogJson`, 0
  `Deserialization failure`. **A DIFFERENT struct from the daily/weekly board:** `FLeaderboard`
  (0x68) `Start·End·QueueID·Role·Entries[]·SelfEntry`, entries
  `PlayerID·Rank·Rating·Placement·Percentile·AvatarID`. Top-level, **no envelope and NO
  staleness/echo check** — unlike `/player-stats/leaderboard`. Paging is **1..50**, not 1..25.
  ⚠ **`Rank` is an `ERank` ENUM STRING** (`Unranked, Bronze4..1, Silver4..1, Gold4..1,
  Platinum4..1, Diamond4..1, Master4..1, GrandMaster, Legend`) — a wrong value is the S118
  `ELokiActivityState` failure and sinks the whole struct. `"Gold1"` is verified accepted.
  ⚠ `SelfEntry` is an **object**, not an array. `AvatarID` is an `FPrimaryAssetId` — **omitted**
  rather than guessed; omitting a field is always safe, an unresolvable id is not.
  Knob: `AGS_MMR_LEADERBOARD=0`.
- ★★ **`GET /player-stats/players/{id}` — FETCHED AND ACCEPTED on a cold boot (S121)** [M]:
  requested by `Loki/UE5-CL-0` at login with **0** `LogJson Unable`, **0** `Deserialization
  failure` and **0** `Invalid response received` (that last one means "a required top-level field
  is absent", so a zero is a real statement about our shape). ⚠ **Accepted ≠ rendered** — the
  CAREER → STATS surface has not been eyeballed, so treat rendering as unconfirmed.
  It is a **login-time** fetch and an admin socket drop does **not** trigger a refetch, so
  iterating on it needs a relaunch. `FPlayerStats{ID, Version int32, StatsByQueue TMap}` → `FPlayerQueueStats{ID,
  StatsByHero TMap}` → `FPlayerHeroStats` (22 int32s + `Placements TMap<int32,int32>`, SizeOf
  0xa8, names [M] from the UHT oracle). **All three maps are JSON OBJECTS**; `Placements` needs
  int-parsable STRING keys (the S120 `UnclaimedRewards` shape).
  ⚠⚠ **`Version` is int32.** A first cut passed `partyVersion()` — a millisecond timestamp
  (~1.79e12) against a 2.147e9 ceiling — which would have rejected the entire struct. Caught by
  reading the served JSON, not by a test. Knob: `AGS_PLAYER_STATS=0`.
- ★★ **`motd` IS THE ONE KEY WHOSE `Config` CARRIES MORE THAN THE FLAG** — that is why serving it
  like the others did nothing. `Try Show MOTD` bails at `Map_Find(Config,"key")` then requires
  `Config["key"] != GetMessageOfTheDayLastSeen()`; `Get Message of the Day` reads
  `key`/`title`/`text`. ⇒ **the sub-keys ARE the message; there is no MOTD endpoint to write.**
  ★ **Bump `key` to re-show it** — an unchanged key shows once per account, ever, so a later launch
  showing nothing is EXPECTED, not a regression. Knobs: `AGS_MOTD_KEY/_TITLE/_TEXT`, `AGS_MOTD=0`.
- ⚠ **A SAFETY PROPERTY THE CENSUS MISSED: per-instance `EnabledVisibility`/`DisabledVisibility` can
  be INVERTED** (Enabled=`Collapsed`), so serving `true` COLLAPSES that site. Three served sites ship
  it swapped: `ArmoryNoProgression`, `ArmoryHeader`, `ArmoryHJUnlock` (the last two on the
  trailing-space key). **Any "is this key safe to serve?" check must read all five properties, not
  three.** [I] two look like intended A/B header swaps; the ARMORY renders normally.
- ⚠ `LobbyRewards` is AND-ed with `Rewards.Num > 0`; `ArmoryItemProgression` is **INVERTED** in
  `Comp_PlayerController_ArmoryOnboardingNoProgression` and is a `SelectInt` value picker (not a
  visibility gate) in four armory widgets. A key can be necessary without being sufficient.
- Knob: **`AGS_UI_TOGGLES=0`** restores the pre-S120 payload exactly, no rebuild.
  Served set + reasons: `handleClientConfig`, `server/internal/loki/loki.go`.
- ★★ **FREE INSTRUMENT, ALREADY ON: `LogClientConfig` is pinned VeryVerbose in the user `Engine.ini`**
  and emits `Refreshing client configuration` → `Fetched client configuration: ETag <etag>` on a
  **~30 s poll** [M]. So the client re-reads config WITHOUT a relaunch — iterate inside one live
  session rather than one launch per batch. ⚠ **BUMP THE eTAG on every payload change.**
  ⚠ Whether an already-CONSTRUCTED toggle widget re-evaluates on that refresh is **[S], untested** —
  rebuild the page (navigate away and back) before reading anything off it.
- ★★★★★ **THE READOUT EXISTS NOW — `tools/re/toggle_readout.py` (read-only RPM, no injection).**
  `IsFeatureEnabled` itself logs NOTHING (**0** `BasicLog` sites in its 265-byte body, 240/265 bytes
  decrypted, vs a same-TU control with 1) so no log verbosity can see it — **but the declarative
  widget STORES its answer** in a reflected UPROPERTY. Live offsets on
  `WBP_UI_ClientConfigVisbilityToggleWidget_C`: `FeatureKey +0x450`, `ConfigKey +0x460`,
  `IsEnabledByDefault +0x470`, `EnabledVisibility +0x471`, `DisabledVisibility +0x472`,
  **`Is Content Enabled` +0x473**.
  ★ **The decisive predicate: `IsEnabledByDefault==false AND Is Content Enabled==true` is reachable
  by NO path except FeatureToggles hit → Config[ConfigKey] hit → ToBool true** ⇒ a direct measurement
  that our served value was read. **[M] 133 instances live; `ConfigKey` reads `"enabled"` on all of
  them.** Both controls passed in one run: default-true keys read on; the keys we DELIBERATELY
  WITHHELD read off (`SeasonalBattlepass` 8/8, `chuseokboostui`, `prisma_boost`, `lobby_survey_menu`).
  ⚠ **Parse the `summary:` line; never count rows.**
  ⚠⚠ **A False row beside a True row is NOT a failure** — the widget-tree archetype coexists with the
  live instance and unevaluated objects read false (the CDO reads False/False; that is the control).
  **Per key, ANY `SERVED VALUE READ` row is the positive signal.**
  ⚠ **It CANNOT see the 10 bytecode keys** (`motd`, `LobbyRewards`, `ArmoryOnboarding` have 0 widget
  instances) — that is a coverage limit, not a negative result.
  ⚠ `class_props.py` cannot resolve this class: it demands class-of-class `=="Class"` and a Blueprint
  class's is `BlueprintGeneratedClass`, so it prints a misleading `not found (map not loaded yet?)`.
  `toggle_readout.py` resolves the class from a LIVE INSTANCE (`obj+0x18`). **Third member of the
  class-lookup blind-spot family** alongside `obj_by_class.py` and `cheat_reach_probe.py`.
  ★ **It DISAMBIGUATED a real case immediately:** `NeLobbyEventBtn`'s gate is **ON** while its button
  stays invisible ⇒ companion condition unmet, **not** a flag problem. Pre-readout that would have
  been recorded as "serving the key did nothing."
  ★ It also showed **`mastery` was already lit** (`IsEnabledByDefault=true`), so it is a no-op to
  serve and would REMOVE the S120 mastery surfaces if ever served `false`.

### Before touching anything region- / latency- / ping- / "??? — ms"-shaped
★★★★★ **THE LATENCY PIPELINE RUNS (S121, 2026-08-15) — first time in this project's history.**
Read `docs/fk5-latency-subsystem-re.md` (the RE, 2026-07-27) then
`docs/s121-toggle-fix-confirmed.md` §3d (the shipping fix). FK-5 decoded this end to end and **the
fix was never shipped**; S121 shipped it and hit **three more silent failures on the same endpoint.**
- **The model is NESTED and we served it FLAT for a year.** `FRegionHostList{TArray<FRegionHost>
  Regions; FString ETag}` · `FRegionHost{FString Name; FString Addr; int Port; bool CanExclude;
  TMap<FString,FRegionRoute> Routes}` (0x78) · `FRegionRoute{bool Enabled; bool IsAccelerator;
  FString Host; int Port; FString PingHost; int PingPort; bool RequiresToken}` (0x38).
  **`PingHost`/`PingPort` live INSIDE `Routes`** — a TMap we had never sent, so the body parsed into
  one region with an empty map. Zero routes ⇒ zero measurers ⇒ zero pings ⇒ `??? — ms`.
- ⚠⚠⚠ **`CanExclude` MUST BE `true` — it is a HARD INCLUSION GATE, not advice.**
  `fn 0x57DDCA0`, gate at `0x57DE016`: `if (R.CanExclude == 0) continue;` skips the ENTIRE region.
  S121 served `false` (reading it as "may the player exclude this?") and got a fully-bound payload
  with **zero measurers**.
- ⚠⚠ **The regions ETag GATES RE-PROCESSING.** A changed payload under an unchanged `ETag` is
  ignored — measured: `CanExclude=true` did nothing for a minute across two `ags` restarts until the
  tag moved. It is now a **sha256 of the body** so it cannot go stale. (This was the SECOND
  stale-eTag bug shipped in one session, an hour after fixing the same class on client-config.)
- ★ **`Name` IS THE `ST_ServerLocations` STRING-TABLE KEY, and the table is keyed by AWS REGION
  CODES — 38 of them** (`tools/extractor/out/catalog/st/ST_ServerLocations.json`): `us-east-1`
  "NA East (Virginia)", `us-west-2` "NA West (Oregon)", `eu-west-1`, `ap-northeast-2`,
  `local-cluster` (CJK), … Serving `"na"` reached the UI (FK-5's P1 receipt fired:
  `ST_ServerLocations 'na'` instead of the historical `''`) but rendered
  **`<MISSING STRING TABLE ENTRY>`**. Default is now `us-east-1` → **"NA East (Virginia)"**,
  screenshot-confirmed. Knob `AGS_REGION_NAME`. **Same lesson as missions `InternalName`: read the
  registry the client already ships; do not invent a plausible key.**
- **Receipts [M]:** `LogLatencyManager: Display: Creating new latency measurer for us-east-1 default`
  and `obj_by_class LatencyMeasurer` = **1 LIVE** (was 0 in every prior measurement).
  ★ **Readout: `tools/re/regions_readout.py`** reads the parsed `UCoreGameManager.ValidRegions`
  (`+0x6F0`, resolved by name) — `Regions.Num`, per-region fields, and **`Routes.Num`**.
  ★★ **Its `ETag` field is a FREE POSITIVE CONTROL** — compare it to what `ags` served: matching
  ETag + empty array/map localises the fault INSIDE the struct instead of leaving "empty" ambiguous.
  That ambiguity is what let this bug survive from 2026-07-27.
- ⚠ **`— ms` is still not a number and that is EXPECTED, not a regression.** The ping is a **UDP
  echo** (not ICMP — a port is specified), `Could not ping target host: 127.0.0.1:443. Result: 4`,
  and we run **no responder**. **Next task: a UDP echo responder on `PingHost:PingPort`.**
- ⚠⚠ **THE WHOLE CHAIN FAILED SILENTLY AT EVERY LAYER** — six nested defects, zero errors logged.
  `LogJson`, `Deserialization failure` and `Invalid response received` are all blind to
  "parsed fine, populated nothing". **On this endpoint, read the parsed struct; do not trust silence.**

### Before touching anything menu-shaped
Skim `docs/trackb-notes.md` (Track B endpoint surface + ClientProfileData model)
and `docs/endpoints.md` (every endpoint the client hits + handler status).

### Before touching anything extraction-shaped
Skim `docs/findings.md` and `docs/r2-findings.md` (IoStore catalog + usmap RE +
the non-standard UObjectBase layout in this build: nameOff=0x20, classOff=0x18,
NOT the stock 0x18/0x10). `docs/game-map.md` has the full 68,228-asset catalog.
S110 calibrated the other two fields live (`tools/re/item_watch.py`, 400/400 and
100%/0% controls): **ObjectFlags@0x0C, InternalIndex@0x10** — so an object's
`FUObjectArray` slot can be read straight out of the object, no scan needed.

### Before touching anything AR-bin-shaped
Read `docs/trackb-assetregistry-route.md`. The `assetregistry apply-patch`
extractor subcommand works end-to-end; loose-file AR.bin deployment has been
proven INERT in this IoStore build (UE ignores the loose file even when valid).
Deployment requires an IoStore mod-pak overlay — non-trivial.

### Before touching anything Angelscript- / deploy- / respawn- / "the ceiling" shaped
★★★ **FK-1 IS SETTLED (S113, 2026-08-09) — read `docs/fk1-angelscript-settled.md`.** S74's
*"only 18 classes are Angelscript … the native deploy/round core is the irreducible blocker …
**accept the ceiling**"* (commit `19db6a2`) is **REFUTED**, and so is the ceiling.
- ★★ **The script layer is AOT-TRANSPILED TO C++ and compiled into the exe ("StaticJIT") — it is not
  interpreted.** 1463/1463 cache function Ids appear as `mov edx,imm32` registration-stub immediates
  (control 0/4000); a **1,459-row symbol table** (script fn → raw / `_VMEntry` / `_ParmsEntry` RVAs)
  was recovered; bodies live at `.text 0x059128B0–0x05A7F070`. ⇒ **script UFunctions are callable by
  the existing S55 native-call recipe, unchanged.** ⚠ **`Func != ProcessInternal`, so the PI hook
  NEVER fires for a script UFunction** — the ignorance map's proposed "print every PI-dispatched
  UFunction for 5 s" test returns **zero AS classes even when they are perfectly callable.** It is a
  TRAP; use it only as a negative control.
- ★★★ **THE REAL WALL: four server-authority C++ functions have EMPTY IMPLEMENTATIONS in the
  shipping client** (byte-level, coverage-guarded, controls; re-verified in BOTH dumps S115 —
  `docs/fk1-stub-claim-recheck.md`). ⚠ The exec THUNK and the IMPL are different addresses; the
  thunks are real code, the impls are folded stubs:
  `ALokiGameMode::SpawnPlayer` thunk `0x534C070` → impl **`0x0F7EB50` = `xor eax,eax; ret`** ·
  `ALokiPlayerState::AuthSetSpawnTeamLeader` thunk `0x5254180` (⚠ 91-way ICF-folded, NON-IDENTIFYING)
  → impl **`0x0F7EC20` = `ret 0`** ·
  `ALokiTeamState_TeamOnly::SetDropLeader` thunk `0x2C2CE30` (⚠ 23-way ICF) → impl **`0x0F7EC20`** ·
  `ALokiDropPlane::OverridePlaneLocations` thunk `0x53372A0` → impl **`0x0F7EC20`**.
  Empty-impl base rate in this image is **1.2 % (78/6,669)**, so this is informative, not ambient.
  Likely `WITH_SERVER_CODE`-stripped [I]. **This explains ~7 failed spawn attempts
  across S68/S74 and CLOSES `AvatarActor = NULL`:** the design routes the whole GAS bind through
  `SpawnPlayer` (disassembly-verified in `FFA/LokiRespawnComponent::Respawn`, which null-checks the
  character but NOT the ASC) and the client's `SpawnPlayer` returns nullptr.
  ⇒ ★ **But the SCRIPT authority functions ARE compiled in, and a direct `Func` call bypasses
  ProcessEvent's net routing** (22 `NetServer` script fns run locally regardless of authority). The
  deploy door is shut in C++ and possibly open in script: `ULokiRespawnComponent::Respawn`
  (`0x5A6AC40`), `ALokiDropShip::SpawnDropPodForTeam` (`0x597E730`), the `ALokiDropPod` steppers,
  `UFFABotSpawnerComponent::BeginPlay`.
- ✅ **THE FOUR-STUB CHALLENGE IS RESOLVED (S115, 2026-08-12) — `docs/fk1-stub-claim-recheck.md`.**
  S114 read `0x534C070` / `0x2C2CE30` / `0x53372A0` in TWO dumps as **large real functions with
  security cookies and parameter setup**. That reading was **CORRECT — and so was FK-1's.** They
  describe **different addresses**: those RVAs are the exec **THUNKS** (real code), and the empty
  bytes belong to each thunk's **IMPL**, an address FK-1's table never printed (see the corrected
  entry above). **Neither measurement was wrong, and there is no RVA/VA or image-base confusion
  anywhere** — both dumps are flat and byte-identical at every address involved.
  ⇒ **FK-1's "the real wall" and its closure of `AvatarActor = NULL` STAND; build on them.**
  Empty-impl base rate is **1.2 % (78/6,669)**, so the finding is informative, not ambient.
  ⚠ The false statement was manufactured **in this file** — a table headed
  `| function | exec thunk | body |` was compressed to prose, dropping the column label and
  substituting `=`. **Never print a byte string next to an address it did not come from.**
  ⚠ Scope note, now sharpened: `ALokiPlayerState::AuthSetSpawnTeamLeader` `0x5254180` was never in
  dispute, but the address is **91-way ICF-folded and NON-IDENTIFYING** — it is this image's shared
  zero-parameter `execFoo` thunk (**7 real instructions**, `P_FINISH; jmp 0x00F7EC20`), not itself a
  fold. It is the registered `Func` of **91** distinct UFunctions, so it can never identify one.
  Always print fold multiplicity next to a folded RVA.
- **The round mode IS native — but that is NOT a ceiling.** Every member is a named
  UFUNCTION/UPROPERTY reachable by the primitive, and **the phase lives on `ALokiGameState` with a
  public `AuthSetCurrentPhase` setter**, so the `EGP_Combat` gate has TWO write paths. The tutorial
  **already runs** the round mode (`BP_LokiGameMode_Tutorial_C`); native `ALokiTutorialGameMode` is
  vestigial. `LokiDropInGameMode` is a *referenced native base*, is **not** a round mode, and
  "DropIn" ≠ drop phase.
- ★ **The usmap gap is CLOSED.** `tools/asdump/out/usmap/mappings+as.usmap` adds the 110 AS types;
  base round-trips **bit-identically** (11,344/11,344 structs, 2,226/2,226 enums). **263 property
  values newly decoded** across 26 assets — `BP_GameMode_Barracuda` 27 → 65 props,
  `LaserSettings` `{}` → a full 14-field struct. ⚠ Only **`UPROPERTY()`** members are reflected
  (470 of 581) — measured by a 4-arm one-variable test with a reversed-order positive control.
  **FK-14 resolved:** the extractor loads `tools/extractor/mappings.usmap` (md5 `3892b937…`).
- ⚠ **Live RPM (S113): AS UClasses are NOT registered at the menu** — 0 of 15 sampled names, against
  3 passing native controls (`LokiGameMode` 72 fns, `LokiPlayerController` 151, `LokiPlayerCheats` 65).
  AS **enums and structs ARE** live. **So any callability test needs a LOADED MAP, not the menu.**
  Probe names: `tools/asdump/out/usmap/as_schema_full.csv`, column `ue_name` (66 AS UClasses).
- ⚠ **Two memory claims are now FALSE:** *"every drop-phase step is a `BlueprintCallable` UFUNCTION"*
  (`InitializeDropPod` is not a UFUNCTION at all; 3 of 10 listed are not BPCallable, so the
  "skip the plane" two-call recipe is **not executable**), and *"fix = `AuthSetSpawnTeamLeader()`
  before spawning"* (**no body**; and `SpawnDropPodForTeam` bails on `TeamDropPodClass == nullptr`
  first). Conversely **zero `BlueprintAuthorityOnly` anywhere** — the S90 gotcha does not recur.
- ★ **FK-6 re-grade:** `ALokiPlayerCheats_AS` is a **separate script-generated UClass** from the C++
  `ALokiPlayerCheats` that FK-6 closed on, and it has **32 UFUNCTIONs with compiled native bodies**
  (`AuthCheatGrantGold`, `AuthCheatUnlockFullArmory`, `AuthCheatExecuteUAV`). `Exec == 0` across all
  500 script UFUNCTIONs — the console cannot reach them, **but the thunk can.**
  ⚠ **S114 SCOPE CORRECTION:** that `Exec == 0` is **Angelscript-only** and was never a claim about
  native UFunctions. **138 NATIVE UFunctions carry `FUNC_Exec`** (`UCheatManager` 48,
  `ALokiPlayerCheats` 25, `APlayerController` 13, `ALokiCharacter` 10, …), and as of S114 a real
  `UCheatManager` is installable on the live PlayerController, so **42 of them ARE string-reachable
  today** — see the console/exec block above.
- ⚠ **Reading discipline for `tools/asdump` output:** the per-function **disassembly appendix is
  GROUND TRUTH; the pseudo-source is a reading aid.** The structurer can **silently invert a guard**
  (46 of 1,463 functions share the risk shape). Verify anything load-bearing against the disassembly.

### Before touching anything logging- / instrumentation- / "we can't see it" shaped
★★★ **FK-11 IS SETTLED (S113, 2026-08-09) — read `docs/fk11-log-verbosity-settled.md`.** Offline,
zero launches. **Verbose/VeryVerbose are NOT compiled out.** The old rule
(`next-session-prompt-s45.md:185`, *"this is a SHIPPING build; Verbose/VeryVerbose UE_LOG is
compiled out (confirmed)"*) is **FALSE** and its "(confirmed)" was attached to a session containing
no test. **This foreclosed the cheapest instrument the project could own for ~60 sessions.**
- **MEASURED:** global `COMPILED_IN_MINIMUM_VERBOSITY` = **`VeryVerbose` (7)**; `USE_LOGGING_IN_SHIPPING`
  = **1**; of 14,030 decoded `UE_LOG` call sites, **1,339 are Verbose and 513 VeryVerbose**;
  **98.0 %** of categories have `CompileTimeVerbosity ≥ Verbose`; and **109/109 Loki-dominant
  categories are VeryVerbose — zero capped at `Log`**. There are **71 Verbose/VeryVerbose call sites
  inside `\Loki\Source\`** across 35 categories.
- ⚠⚠ **DO NOT USE `-LogCmds` — it does not parse in this binary.** `logcmds` occurs exactly 3× in the
  178 MB image and **all three are help text** (`0x076B25E0`, `0x076B26B0`, `0x076B2860`); there is no
  standalone `LogCmds=` literal. Controls: peer switch literals `LOG=`, `ABSLOG=`,
  `logcategoryfiles=`, `NOCONSOLE`, `FORCELOGFLUSH` all DO exist; on-disk exe agrees; `.rdata` is
  99.64 % complete. **The help text is what a casual scan finds and it reads like proof the flag
  works.** FK-11's own "cheapest experiment" was this flag — it would have produced nothing and the
  nothing would have been recorded as "confirmed, Verbose is compiled out."
- ★ **USE `[Core.Log]` INSTEAD — it is triple-confirmed and ALREADY BINDING.** The binary states its
  own precedence at `0x076B1FA0`: *compiled-in → ini → command line*; stage three is missing, so
  **ini is the last word**. Across a 4.10 GB / 28.7 M-line log corpus, all 15 shipped `[Core.Log]`
  entries show **zero violations** — `LogAccelByte` (which drives the whole login/catalog/store/party
  flow) emits **3 lines** vs 244–422 for unpinned peers. **We have been reading a log that was
  deliberately turned down.**
- ★★★ **FLOWN AND CONFIRMED LIVE (2026-08-09, one `-NoHook` menu launch).** Scoreboard, all three
  mechanisms in one run, each on its own category:
  **A — user `Engine.ini` `[Core.Log]`: WORKS** (`LogAccelByte` 3 → **52** lines, **46 Verbose**).
  **B — `-ini:Engine:[Core.Log]:…`: FAILED**, clean control (`LogOnline` emitted 2 `Warning:` lines,
  so it ran, and stayed pinned) ⇒ **`-ini:` is applied too late for `[Core.Log]`; use the user ini.**
  **C — `-LogCmds`: inconclusive** — the category chosen had no positive control, so its zero cannot
  discriminate "ignored" from "never logs". Both B and C were verifiably **DELIVERED** (engine echo),
  so they are failures of effect, not delivery.
  **Whole log: Verbose 13 → 1,018; Error 100,618 → 2; size 14.1 MB → 1.4 MB.** The log is now **10×
  smaller and carries 78× more Verbose.** `LogTemp=Fatal` zeroed all 100,616 spam lines.
- ★★ **What it immediately revealed:** `LogAbilitySystem` 25 → **4,161 lines / 959 Verbose** on a plain
  menu launch — **137× `Initializing new default set for LokiAttributeSet[N]`**, plus a real per-hero
  data defect (`Unable to match Attribute from SneakSpeedMultiplier (row: <Hero>.LokiAttributeSet.
  SneakSpeedMultiplier)` for **every** hero). `LogAccelByte` now traces the whole backend
  conversation (SDK entry point + verb + full URL + status + request handle), including the
  previously invisible **`[AccelByte] Key for Cached Token can not be empty.`** And
  **`AccelByteWebSocket::OnMessageReceived` fires repeatedly** ⇒ frames ARE arriving on the client
  socket, which hands **FK-15** an instrument it never had.
- **Use the shipped tooling:** `configs/set-log-verbosity.ps1 [-Preset Mechanism|ClassA|Gas]`
  (backs up, clears ReadOnly, merges `[Core.Log]`, re-sets ReadOnly; `-Revert`, `-WhatIf`) and
  `configs/check-log-verbosity.ps1` (reads the log **live**, shares the handle, prints per-category
  line + Verbose counts against measured baselines). `launch-redirect.ps1` now takes **`-ExtraArgs`**
  for raw extra switches (forwarded across elevation).
- **Mechanism (precedent already in this repo):** append `[Core.Log]` to
  `%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\Engine.ini`, then re-set **ReadOnly**. That
  file already carries this project's own `[HTTP.Curl] bVerifyPeer=false` + `[SSL]` fix for the
  documented "`-ini:` applied too late" problem (`launch-redirect.ps1:279`).
- ★ **Two free instruments in every log:** `LogInit: Command Line:` echoes the **entire** command
  line verbatim (so any switch is verifiable as *delivered*, separately from whether it *worked*),
  and `LogConfig:` narrates config application.
- ⚠ **The dominant trap is NEVER-RAN vs SUPPRESSED.** 384 of 842 logs reach `LVL_Tutorial` but **none**
  contains combat, drop phase, bots, damage, XP or client replication. Raising verbosity on a
  never-run category changes nothing. **Class A** (owner provably ran, still silent — real
  suppression wins): `LogLokiHeroCharacter`, `LogLokiCharacter`, `LogLokiCharacterMovement`,
  `LogLokiPlayerController`, `LogGameFeatureToggles`, `LogLokiMenuActions`. **Class B** (loaded, path
  not exercised): the GAS family. **Class C** (never ran): all netcode, drop phase, inventory/damage.
- ★ **Fly `LogBlueprintLogLibrary` FIRST.** Loki's own `UBlueprintLogLibrary` exposes `Verbose` /
  `VeryVerbose` **static UFunctions** callable via the existing native-call primitive, and the
  category already emits (598 logs) — it proves the whole mechanism with **zero gameplay dependency**.
- ⚠ **Spam hazards:** `LogNetSerialization` (per-bit — it was in FK-11's own suggested line; **strike
  it**), `LogNetTraffic`, `LogRepTraffic`, `LogRepProperties`, `LogRepCompares`. **Special case:
  `LogGameFeatureToggles` is HIGH risk despite being silent** — the same subsystem already emits ~10⁵
  lines/run via `LogTemp`. Raise it to `Log` first, never straight to `Verbose`.
- **Two free wins:** `LogTemp` is **97.5 %** of the log (100,616 of 103,169 lines — the feature-toggle
  spam, at **`Error`**), so **`LogTemp=Fatal`** reclaims the whole budget (`Warning` will NOT work);
  and **`DFLLog=Fatal`** in the shipped ini mutes a real 33-method debug library — un-muting is free.
- **The Angelscript layer is silent by AUTHORSHIP, not gating** — 20 `Log::` functions exist but the
  shipped scripts call them **6 times in 4,963 syscalls (0.12 %)**. Raising verbosity cannot make
  script code talk; this downgrades the drop-phase route. The script API has no `Verbose` at all.
- ⚠ **`FLogCategoryBase` layout in this build: `Verbosity@0, DebugBreakOnLog@1, DefaultVerbosity@2,
  CompileTimeVerbosity@3, FName@4`** — FName is **LAST**. Ctor is `base+0x1063710` (**not**
  `0x1138F20`, which is `FName::FName`). Verbosities are passed as `mov r8b/r9b, imm8`, not `imm32`.

### Before touching anything console- / exec- / cheat-verb-shaped
★★★ **FK-13 IS SETTLED (S114, 2026-08-12) — read `docs/fk13-console-exec-settled.md`, then
`docs/fk13-live-run-2026-08-12.md`, then `docs/fk13-routeb-shipped.md` (its §6 corrections, §7 guards
and §9 end-to-end proof govern).** S3's *outcome* was right and **every reason it gave was wrong**;
S101's explanation of S3's error was also wrong (all 6 overturned tokens are readable in the shipped
on-disk exe with a plain ASCII search, so *"S3 scanned the packed binary"* does not explain the miss —
**do not propagate it**). And S3's operational conclusion — *"all cheap external paths are exhausted;
the remaining options require in-process code"* — is **FALSE**. That sentence is the founding
justification for the injection-only architecture.
- ⛔ **`ALLOW_CONSOLE == 0`: `~` CAN NEVER WORK, and no config, ini or command-line change alters
  that. Do not spend a launch re-testing it.** [M] via three independent instruments:
  `UGameViewportClient::Init` (`0x0384FB00`, 1,810 B, decrypted in BOTH dumps) has **zero** reads of
  `ConsoleClass` (`+0x120`) and **zero** stores to `ViewportConsole` (`+0x48`) while writing both
  neighbouring stock members; `Console.cpp` guard-exclusive literals score **8/8 controls vs 0/5
  markers** at `.rdata` **100 %**; and the gaps in `UEngine::Exec`'s literal pool are exactly the
  compile-guarded verbs. `UConsole` the CLASS *is* compiled and `ConsoleClass` IS resolved at startup —
  only the viewport never constructs one, so `GEngine->GameViewport->ViewportConsole` is NULL.
  `config-control-plane-s101.md` §5 levers **#1 and #4 are dead**; its probes **P1/P2/P4 are answered
  offline**. `ULokiGameViewportClient` does not re-add one (its vtable differs from the base in 4 of
  122 slots; neither `Init` nor `SetConsoleTarget` is among them).
- **FK-13 was THREE independent compile flags, not one** [M — UBT `TargetRules.cs:1368,1374,1429`,
  `UEBuildTarget.cs:5064,5073,5145`]: `bUseLoggingInShipping` (stock default 0, **this build 1** —
  FK-11), `bUseConsoleInShipping` (stock default 0, **this build 0**), `bUseExecCommandsInShipping`
  (**stock default 1**, this build **1**). **Never reason from one to another.** A fourth gate,
  `UE_WITH_CHEAT_MANAGER = (1 && !UE_BUILD_SHIPPING)`, is a plain `#define` with **no `Target.cs`
  escape** — that is what empties `AddCheats`.
- ★★ **THE EXEC MACHINERY IS ALIVE.** `UE_ALLOW_EXEC_COMMANDS == 1`; `UEngine::Exec` `0x3ED66C0`
  (2,521 B real body), `UGameViewportClient::Exec_Runtime`, `FSelfRegisteringExec::StaticExec`,
  `UObject::CallFunctionByNameWithArguments` `0x1343420`, and the whole IConsoleManager cvar channel
  are compiled. **138 native UFunctions carry `FUNC_Exec`** across 15 classes — `UCheatManager` 48,
  `ALokiPlayerCheats` 25, `APlayerController` 13, `ALokiCharacter` 10, `ALokiPlayerController` 8,
  `AHUD` 6, `UPlayerInput` 5, `ULokiClientPlayerCheats` 5, `ULokiTimelineManager` 5, … [M]
- ★ **The entry point is `UKismetSystemLibrary::ExecuteConsoleCommand`** (exec thunk `0x395D790`,
  flags `0x04022403` = `BlueprintCallable|Native|Static|Public`) — exactly the shape the S55
  native-call primitive already calls, **with no `.text` write**. ★★ **And this project has been
  driving that channel since ~S91 without naming it:** the force-open shim's
  `ExecuteConsoleCommand("open LVL_Tutorial?game=…")` fires at `rva 0x395D790`, and
  `Load map complete …/LVL_Tutorial` is its receipt across dozens of runs. ⇒ S3's
  `-ExecCmds="open …"` null was a **delivery** failure, not a verb failure.
  ⚠ **OPEN:** `OPEN` is *absent* from `UEngine::Exec`'s literal pool [M], so `open` must be serviced
  elsewhere on the chain (`UWorld` / `UGameInstance` / a Loki override). **Both facts are measured;
  the dispatch site is unresolved — do not write up "OPEN is compiled out."**
- ★★★★★ **ROUTE B IS SHIPPED AND PROVEN END-TO-END — a console string reached a cheat verb.**
  `APlayerController::CheatManager` (`+0x520`) was NULL in every measurement this project has ever
  taken. The new `RM_CHEATMGR` mode in `tools/sigbypass-mod/tutorial_launch.cpp` constructs one via
  `UGameplayStatics::SpawnObject(pc->CheatClass, pc)` and stores it in the reflected `CheatManager`
  UPROPERTY — **ONE aligned heap qword, readback-verified, ZERO module-image writes** (the `.text`
  arm is a compile-time REFUSAL that prints why). `CheatClass` (`+0x528`) was **already populated in
  BOTH the menu and the staged tutorial world**: the class selection was never stripped, only the
  body of `AddCheats`. **Proof:** `ExecuteConsoleCommand("LogLoc")` →
  `LogCheatManager: BugItGo 0.000000 …` in `Loki.log`, baseline 0, **both format literals confirmed
  present in the image BEFORE the run** (a pre-registered signal, not a post-hoc grep). 69 min
  uptime, 0 crashpad handoffs, Func-swap restored 18,223/18,223. **42 REAL exec verbs**
  (42 REAL / 3 FOLD / 3 COVERAGE-BLOCKED / 2 UNRESOLVED — *not* the "44" first stated).
  ★ `SpawnObject`, not `NewObject`, for a non-obvious reason: shipping has `DO_CHECK == 0`, so
  `NewObject`'s internal `ClassWithin` assert is compiled out and **a wrong Outer would be SILENT**;
  `SpawnObject`'s *runtime* Within test is the only one that survives shipping.

Builds (`tools/sigbypass-mod/build.ps1`; `.text` sha256 — **diff `.text`, never size**):

| variant | `.text` sha256 | use |
|---|---|---|
| `cheatmgr` | `750b83bf0f36e90e` | **in-world** (arms on `ReceiveTickClient`) |
| `cheatmgr-any` | `b551996df67f106b` | **menu** (`KFSNAME=""`, swaps all BP UFunctions) |
| `cheatmgr-any-verify` | `4507e376d099a3b5` | **the flown proof** — menu + executes `KCMVERIFYCMD` (default `LogLoc`) |
| `cheatmgr-verify` | `bc2abddf627bdeed` | in-world + verify — ⚠ **the on-disk build predates the R7/R8/R9 guards; REBUILD before use** |

Pre-guard builds were `a90e14dcde1dffa8` / `ef2fd89f87168871` — do not confuse them. ⚠ The S112
import-absence check (`FlushInstructionCache`/`VirtualAlloc` absent) does **NOT** verify this DLL —
it hosts other modes that legitimately import those. The no-`.text`-write property rests on source
reading plus the compiled-out refusal.

- ⚠⚠ **THREE TRAPS, EACH OF WHICH PRODUCED A FALSE RESULT BEFORE IT WAS CAUGHT**
  (`docs/fk13-routeb-shipped.md` §4 / §6 / §9.1):
  1. **`ReceiveTickClient` is never dispatched AT THE MENU** — `cheatmgr` is a silent no-op there.
     Its own watchdog said so (`NO GAME-THREAD HITS after 8000 ms … swapped=2`). Use `cheatmgr-any`
     at the menu, `cheatmgr` in-world.
  2. **`God` emits NO log line at all** — a silent instrument, so its null is uninterpretable.
     `KCMVERIFYCMD` defaults to **`LogLoc`**, whose `UCheatManager` body reaches
     `BugItStringCreator` → `UE_LOG(LogCheatManager, …)`.
  3. **A borrowed helper (`RunConsole`) read globals populated by a DIFFERENT run mode** and passed a
     null PC, so `ExecuteConsoleCommand` fell through to `GEngine->Exec(nullptr, …)` and branch 7
     never ran — while printing `console 'LogLoc' ok`. Fix = `RunConsoleOnPC(pc, cmd)` passes the PC
     as BOTH `WorldContextObject` and `SpecificPlayer`. **Check the provenance of every global a
     borrowed helper touches.**
  ⇒ ★★ **"THE CALL RETURNED OK" IS NEVER A SUCCESS CRITERION. Only the verb's OWN output is.**
  ⚠ `UPlayer::Exec`'s branches are `else if`-chained, so an earlier branch returning true swallows the
  command before branch 7 — **pick verbs that exist ONLY on `UCheatManager`.**
- **The 25 `ALokiPlayerCheats` verbs: THE ROAD IS BUILT, THE DESTINATION WAS NEVER CONSTRUCTED.**
  `ALokiPlayerController` **overrides** `ProcessConsoleExec` (`0x569BE50`, vtable slot 81 / disp
  `+0x288`): it calls `Super` first, then null-checks `[this+0xA30]` (the `LokiPlayerCheats`
  ObjectProperty) before forwarding. Routing: **YES**, offline-decisive. Instance: **NO** —
  `PC+0xA30` is NULL live in the menu *and* in the staged tutorial world (offset resolved BY NAME
  from live reflection), and `AddLokiPlayerCheats` / `FinishAddLokiPlayerCheats` are **empty folds**
  (`Func = 0x5254180`), confirmed LIVE. `ULokiGameInstance::LokiClientPlayerCheats` (`+0x298`) is
  likewise NULL, which kills the "cheapest win on the board". `ALokiGameState` and `ULokiGameInstance`
  have their own forwarders (TimelineManager / LokiClientPlayerCheats) with the same problem.
  ⚠ **OPEN:** whether spawning an `ALokiPlayerCheats` actor and writing `+0xA30` reaches those 25
  verbs has **not been tried.**
- ⚠ **DEAD — do not spend launches:** `DebugExecBindings` are config-loaded (exactly the 16 from
  `BaseInput.ini`, matching S80i's live `Num=16`) but **NEVER EVALUATED** — the whole evaluation path
  is `#if !UE_BUILD_SHIPPING`; measured as a clean `PlayerInput.cpp` literal-pool gap (6 same-file
  controls present; `NoDebugExecBindings` and `KEYBINDING` both **0**) plus **0** TArray-shaped
  accesses at displacement `0x1A8` in the PlayerInput region against a **925**-access control.
  **Do not press F9.** `-ExecCmds` **does not parse** (0 wide hits vs 5 same-class `FParse` switch
  controls that all resolve; on-disk exe agrees) — the **SECOND** non-functional UE switch after
  `-LogCmds`, so **treat every UE command-line switch as unverified until you locate its parse
  literal.** Loki's own data-driven debug menu is fully reflected but `Show/Hide/ToggleDebugMenu` are
  **empty bodies** (its `Ctrl+\` binding in `UserSettings.ini` means nothing);
  `ULokiBlueprintLibrary::CheatsEnabled` folds to `xor al,al; ret`; and `viewmode` ships the refusal
  string *"Debug viewmodes not allowed in Test or Shipping builds."*, so a null from it proves nothing.
- **cvars are a SHIM-FREE channel.** `ExecuteConsoleCommand` tries
  `IConsoleManager::ProcessUserConsoleInput()` FIRST — no instance, no pawn, no override — and cvars
  are additionally settable with **no injection at all** via `[ConsoleVariables]` in the USER
  `Engine.ini` (same file and mechanism as FK-11's `[Core.Log]`; `-ini:` is applied too late).
  44-entry `loki.*` inventory: `tools/re/out/cvar_census_tuthero.txt`. ⚠ **[I]** anything flagged
  `ECVF_Cheat` is excluded — `DISABLE_CHEAT_CVARS` is `(UE_BUILD_SHIPPING || …)`, a hard `#define`
  with no `Target.cs` escape; **which of the 44 carry that flag has not been enumerated.**
- ★ **FK-6 is RE-SCOPED, not contradicted.** Its *"console `Exec` == 0/500"* was measured over the
  **500 Angelscript** UFUNCTIONs and was never a claim about native ones. And its real closure — the
  CONSTRUCTOR (`AddCheats` = `ret 0` under `UE_WITH_CHEAT_MANAGER == 0`), not the bodies — is
  **CORRECT**; Route B is precisely the "constructing shim" the S105 retraction said would be such a fix.
- ★ **Method worth reusing: guard-exclusive marker strings.** Take `TEXT()` literals that occur ONLY
  inside a `#if` region (verified engine-wide across 24,864 UE source files) and control them with
  literals from the **SAME translation unit** outside the guard — single variable = guard membership.
  ⚠ The rule *"strings cannot decide `ALLOW_CONSOLE`"* is true only of **UHT-emitted** names and
  **FALSE** of guard-exclusive literals; recorded without that qualifier it forecloses a method that
  works. (UHT also strips the `F`/`U`/`A` prefix for reflected names, so probing `FKeyBind`/`UConsole`
  produces a false ABSENT.)
- ⚠⚠ **RETRACTED 2026-08-14 (S121, FK-18) — the old rule here read "run every `.rdata`
  presence/absence claim against `dumps/tutorial-hero/…` (`.rdata` 100.0 %), never
  `merged.dump.exe` alone (63.1 %)". That comparison is between TWO DIFFERENT INSTRUMENTS**:
  100.0 % is `dumpimage`'s **readable-byte** figure, 63.1 % is `mergedumps`' **non-zero-byte**
  figure. It is FK-3 re-committed under a new section name, three sessions after FK-3 settled.
  **MEASURED: `.rdata` completeness is IDENTICAL in every image on disk** — all 11 state dumps
  *and* `merged.dump.exe` have the **same 33 all-zero `.rdata` pages of 9,085, at the same RVAs**
  (symmetric difference **0**); merged's `.rdata` is byte-identical to its seed `dumps/loadout`.
  ⇒ **`.rdata` presence/absence is safe in ANY image** — the section is not demand-decrypted.
  ⚠ FK-13's conclusions are UNAFFECTED (its own table records both images agreeing 8/8 and 0/5 —
  that agreement is the control that falsifies the rule's stated reason, not the finding).
  ★ **What actually differs between images is `.text`.** For anything CODE-shaped use
  `dumps/merged2.dump.exe` (16,625 decrypted pages, **54.90 %** — the union of all 11 states) or
  `dumps/tutorial-hero` (16,112, 53.21 % — best single image).
  ⚠ `.rdata` **pointer values** DO differ across ImageBases (1,257,732 relocations; merged vs
  tutorial-hero differ by 2,518,801 bytes). Read pointers only from an image whose base you are using.

### Before touching anything protector- / anti-tamper- / packer-shaped
★★★ **FK-10 IS SETTLED (S113, 2026-08-09) — read `docs/fk10-protector-identified.md`.** All offline,
zero launches. **The protection is NOT VMProtect and NOT Themida** — refuted six independent ways.
It is a **bespoke stack that internally calls itself "Packer", version 3.3.1**, first-party
Theorycraft-signed. **Do not substitute a second vendor name**: the honest label is
*"bespoke protector, self-identifies as `packer/3.3.1`, vendor unidentified."* Replacing one guess
with another is the exact error FK-10 exists to correct.
- ★★ **`runtime.dll` is NOT PACKED. Its 46.6 MB of protector code is plaintext x86-64 and is
  disassemblable OFFLINE TODAY** — feed the disassembler the loader's function table at
  **RVA `0x14D8758`** (222,960 B, 18,580 entries), **NOT** the `.pdata` *section* (`0x1000`), which is
  vestigial and the loader never reads. Only the protector's *data* (`packer0`, 94.8 % of pages) and
  *resources* (`.rsrc`, 99.9 %) are encrypted; its instructions never are. It is *obfuscated*
  (MBA — `not`/`and`/`imul` ≈ 43 % of instructions), not packed. Start with `packer30` (2.2 MB,
  `call`-structured, holds the entry function and the 4 largest functions).
- ★ **The decisive ID:** at file offset `0x007C1BEC` (UTF-16) `runtime.dll` holds
  `/api/5710262/minidump/?sentry_client=packer/3.3.1&sentry_key=149a7ac2…` — **the same org, project
  and key as the game's own Sentry DSN**, differing only in `sentry_client`. A commercial packer does
  not embed the customer's private DSN.
- ★ **`deobfimports`' own 1107/1107, 0-undecodable result REFUTES the name**: its emulator supports
  21 opcodes with **no conditional branches, no `CALL`, no flags**, and `default: return 0,false`.
  A virtualized (VMProtect-style) stub would resolve **zero**. 100 % ⇒ every stub is branch-free
  arithmetic.
- ★ **The game exe is not "packed" either — it is SELECTIVELY ENCRYPTED IN PLACE** under a stock
  MSVC/UE5 section layout with **no packer sections** and its OEP (`0x751EFD0`) **inside `.text`**.
  `.text` 30,281/30,281 pages encrypted (100 %), `.pdata` 100 %, `.rdata` 28.1 %, **`.reloc` 0 %**.
  Every data directory the loader *reads* is plaintext; the **IAT**, which the loader only *writes*,
  is encrypted. ⇒ **22.8 MB of `.rdata` is plaintext ON DISK** (47 runs ≥64 KB from RVA `0x0764C000`)
  — static string work against the on-disk exe is viable there.
- ⚠ **Wall #7's "no string names the integrity check — CLEAN NEGATIVE, not coverage-blocked" is a
  SCOPE ERROR** (20th instrument-artifact instance). `tools/strxref/strxref.py:63` hardcodes
  `DEFAULT_DUMP = dumps\merged.dump.exe` — **the game exe**; `runtime.dll` appears **0 times** in
  either citing doc. The negative structurally excluded the protector.
- ⚠ **The "hunt xxHash" lead for Wall #7 is SPENT.** xxHash IS present (full XXH3 `kSecret` at RVA
  `0x9c00`) but its one-shot `0x8200f0` has exactly one caller, `0x8f9dd0`, which tests
  `(dword & 0xFFFFFFF0) == 0x184D2A50` ⇒ **it is Zstd's frame checksum, not the integrity hash.**
  **Successor lead:** SHA-256/SHA-1/MD5 tables in `packer2 0x942740–0x9467e0` (two back-to-back
  SHA-256 IVs = lane packing) tracing to a `.pdata`-free tail at **RVA `0x8ffcd4–0x93e886`, 251 KB**
  — **[I]** Intel ISA-L Crypto **multi-buffer** assembly (a BOM component the map missed). A 16-lane
  page hasher fits the dose-response *and* explains the negative Rayleigh result: a periodic timer
  sampling a SUBSET of pages gives aperiodic deaths. ⇒ the right claim is **not** "the check isn't
  periodic" but **"it doesn't verify all of `.text` every pass."**
- ★★ **FK-32 (`0x0000DEAD`) is CLOSED on mechanism:** `runtime.dll` RVA `0x80f7f0` is
  `mov edx,0xDEAD; syscall` = **`NtTerminateProcess(h, 0xDEAD)`** — the protector deliberately kills
  the process. Reached via a NULL-bounded 5-entry pointer table at `packer0 0x1831c0` whose 4th entry
  is `NtCreateThreadEx`. `preloader.dll` is ELIMINATED (0 occurrences; control: 2 in runtime.dll).
- ⚠ **The game exe's `IMAGE_DIRECTORY_ENTRY_EXCEPTION` is RVA=0 / size=0** while it ships a 6.28 MB
  *encrypted* `.pdata` (controls: runtime/tbb/steam_api64/preloader all read fine). So
  `RtlLookupFunctionEntry` finds nothing for the main image. **The "no C++-exception payloads" rule
  STANDS, but BOTH recorded mechanisms are now REFUTED (S121)** — there is **no protector VEH**
  (the only registered VEH is the exe's own heap-corruption handler; the protector hooks
  `KiUserExceptionDispatcher` through a **ProcessInstrumentationCallback**, leaving ntdll
  byte-identical), and **`RtlLookupFunctionEntry` DOES resolve for the main image** (a *dynamic*
  function table of **524,439 `RUNTIME_FUNCTION`s** is registered at runtime, with 29,688 language
  handlers). The no-C++-exceptions rule stands empirically with **no known mechanism**. A missing function
  table kills all three canaries identically. One probe settles it.
- Real BOM (`Loki/Binaries/Win64/thirdpartylicenses.txt`, 31,834 B): System Informer · xxHash ·
  constexpr-xxh3 · **Intel ISA-L Crypto** · MinHook · **HDE64** (`hde64_table` byte-exact at
  `packer0 0x7c6a10`) · Zstandard · mbedtls (its CA store is `.rsrc` RT_RCDATA 10001, a Zstd frame →
  579,410 B of DER — **this is what bypasses `cacert.pem`**) · tpm-tss · tiny-json · bscanf · embedded
  printf. **EAC is genuinely ABSENT**, so `-NoEAC`/`-NullEAC` are dead levers.
- ⚠ **Every behavioural string in these binaries is UTF-16LE.** An ASCII-only scan finds essentially
  nothing. `runtime.dll`'s 249,822 "ASCII strings" are dominated by 7,197 copies of `AWAVAUATVWUSH`
  — a **function prologue, not text**.

### Before touching anything native-shim-shaped
The keystone technique is a **game-thread native-call primitive**: hook
`ProcessInternal` (`base+0x13454A0`), capture a live `FFrame`, then call the target
`UFunction`'s native thunk (`UFunction.Func @ +0xE0`) **directly**. The direct call
has no guards, so it works where slot-56 `ProcessEvent` no-ops for native functions.
Param passing, OUT params (`FFrame.OutParms @ +0x80`), and `AsyncLoadPrimaryAssets`
are all RE'd on top of it. Read `docs/session-55-native-call-primitive.txt` (+ s56/
s57/s58/s59) and the `missions_nativecall_probe*.cpp` / `tools/re/*.py` families
before building a new shim. Also `docs/missions-progression-hookup.md`.

Two `ProcessInternal` hooks that stay PERMANENTLY installed race (they clobber each
other's prologue). The fix (S59): every PI-hooking shim (`mainmenu_refresh_pi8`,
`missions_fix`, `loadout_fix`) installs its 5-byte jmp only TRANSIENTLY — install →
piggyback one game-thread call → uninstall — serialized through a shared named mutex
`Local\SuperviveMissionsPIHook`, so only one has the hook installed at any instant.
That retired the old "mutually exclusive launch modes" split: all three now coexist and
inject together as the default set (see the launch procedure below).

## Launch / run procedure

From an **ELEVATED PowerShell**:
```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1                    # redirect + server + game; injects the default shim set
.\configs\launch-redirect.ps1 -NoLoadout         # everything EXCEPT loadout_fix (isolate non-customization surfaces)
.\configs\launch-redirect.ps1 -WithMissionsShim  # ROLLBACK: re-inject the retired missions_fix.dll
.\configs\launch-redirect.ps1 -NoHook            # clean RE run, no shim injection
```

By default the launcher injects the primary `catalog_store_fix.dll` (roster + store +
cosmetics) at launch, then `configs/inject-secondaries.ps1` injects the secondary
set once it settles: `mainmenu_refresh_pi8` (pick→center refresh), `catalog_pick_fix`
(pick-commit), `loadout_fix` (customization/skin persistence), and
`battlepass_adopt_fix` (PASSES / Hunter's Journey — S83).
One launch = every durable fix, together. `-NoLoadout` / `-NoPasses` trim individual
shims; `-Hook <path>` injects exactly one DLL and no secondaries.

★★ **`missions_fix` LEFT THE DEFAULT SET on 2026-08-14** — the missions page is served
natively by the backend now (see the Missions block above). That removes **one manual-map and
one transient `ProcessInternal` `.text` patch from every launch**, which on this project's own
measured hazard ladder (nothing 0/22 · bytecode 0/9 · transient `.text` 4/12 · standing `.text`
7/8 at a 320 s hold) is a real reduction, not tidiness. `-WithMissionsShim` restores it on either
script. `-NoMissions` and `-Missions` survive as documented no-op aliases so old invocations and
docs still run.

**★ THE SECONDARIES ARE NOW INJECTED 20 s APART, AND THE MENU TAKES ~100 s TO FULLY POPULATE.**
That is deliberate and is **not** a regression — do not "fix" it by lowering the gap. S109
(2026-08-05) measured that injecting them ~3 s apart is what kills the process: with the old
3 s gap the four secondaries landed in a ~13 s burst and the game died at **1 per 43 s**;
at ≥10 s gaps the hazard is **71× lower** (`P = 8.6e-5`). Gap sweep, treatment verified per run:

| gap | exposure | injections | deaths |
|---:|---:|---:|---:|
| 3 s (old default) | 129 s | 12 | **3** |
| 10 s | 1,210 s | 20 | 0 |
| **20 s (new default)** | 1,214 s | 20 | **0** |
| 30 s | 669 s | 12 | 2 |
| 60 s | 3,015 s | 25 | 0 |

`configs/inject-secondaries.ps1 -GapSeconds N` (or `launch-redirect.ps1 -InjectGapSeconds N`)
changes it; pass `3` to reproduce the old burst. ⚠ **MITIGATION, NOT A CURE** — residual is
~1 death per 3,054 s (~1-in-3.4 over a 15-min sitting), so keep archiving dumps and treat an
unexplained death as **possibly ours**. Full evidence: `docs/s109-dump-forensics.md` §12–§20
(§20 retracts an earlier "eliminates" claim; §16 retracts "the PI hook is the mechanism").

★★★ **S111 (2026-08-06): THE DEATHS ARE OURS — CAUSED BY INJECTION ITSELF.** MEASURED over 101
launches (`docs/s111-nohook-control.md`): a **`-NoHook` control, 11 launches × 320 s hold, produced
ZERO deaths**, against **25/90 (28 %) across all injected arms** (p = 0.036) and **9/30 (30 %)** for
a one-shim arm whose scan was disabled (p = 0.041). The comparison is clean because that one-shim arm
*also* leaves the roster/store unpopulated — so the discriminating variable is **the injected DLL,
not the workload**. Every `-NoHook` run survived **5.3× longer** than the window in which injected
runs were dying. So the ~30 % per-launch death rate is a property of **our injection**, not the game,
and it is an engineering problem rather than a hazard to budget around.
⚠ **WHICH aspect is still unknown** — manual-map vs the self-restoring `.text` jz-NOP vs the PI
prologue writes are still confounded. The cheap next step is a do-nothing DLL (`DllMain` returns
immediately), ~10 runs: if that already dies at ~30 %, manual mapping itself is the trigger.
⚠ Also MEASURED: the **~285 s code-integrity kill did not fire once in 11 runs that all crossed it** —
first direct support for "it catches a STANDING `.text` patch" (a `-NoHook` run leaves none), rather
than an inference from timing.

⚠⚠ **THE TABLE ABOVE IS UNDER RE-EXAMINATION (S111).** Do not delete it — but the outcome variable
was **never split by fault family**, and it does not survive that split. MEASURED: both deaths in the
30 s row (`knee-g30-2`, `knee-g30-3`) are `catalog_store_fix.dll`'s launch-time heap scan faulting at
`.text` RVA `0x205d` — a death the **primary** injector causes and that `-InjectGapSeconds` does not
touch at all. `sub-NoMissions-1/-2` and `sub-NoPasses-2` are the same family. So an unknown share of
the "hazard" being attributed to injection spacing is a fixed per-launch hazard from the primary
shim. Re-fit before trusting the 71× figure: classify each death by `RIP & 0xFFFF` first
(`docs/fk8-crash-timing-mined.md` §3.1, §7.2 item 3).

**★ `configs/fk24-stage.ps1` now enforces the same minimum gap** (`-InjectGapSeconds`, default
**20**). It was NOT a uniform burst — measured spacing was gft→fo **~5 s** (lethal regime),
fo→sp **19 s**, sp→probe **7–17 s** — so only the first gap was clearly bad. The gate is a
*minimum*: the existing evidence waits (world-load, `[SP] done step=4`) count toward it and only
the shortfall is slept, costing **~15–29 s** of staging rather than ~50 s. The probe now arms
around **T+175 s** instead of ~T+145 s, leaving ~110 s before the late-kill mode — so the
**T+220–250 s hold still fits, but the armed window is tighter**; budget accordingly.
⚠ Both numbers here are **staging-schedule-relative**, not properties of the game (S111): the launch
clock moved +33.0 s July→August, so re-anchor to `Load map complete …/LVL_Tutorial` when it matters.
⚠ **UNVALIDATED ON A LIVE TUTORIAL RUN.** The 71× reduction was measured on the *menu* route.
Whether it moves the ~1–5 min tutorial deaths is the open question — and it is now the single
highest-value experiment on the board.
⚠ Do NOT re-derive stage spacing from `docs/fk24-stage-*-N-*.txt` mtimes: `Copy-Item` preserves the
SOURCE's LastWriteTime, and step 1 copies a stale marker `gft` never writes, so that delta reads as
+210 s or even +41,742 s. Only steps 2–4 are real.

**RESOLVED (was VALIDATION PENDING since 2026-07-10):** the default set runs THREE PI-hookers
(`pi8` + `loadout_fix` + `missions_fix`) and the full triple now has many confirmation launches.
It is **not** the killer: S109 showed `-NoPasses` (both PI hookers present) is ~21× *safer* than
`-NoMissions` (one present), and `pi8` alone ran 90 min clean. The shared-mutex design is fine;
the injection **burst** was the problem. `-NoMissions` / `-NoLoadout` still isolate individual
shims. See `docs/s109-fk9-capture-durable.md` and `docs/fk8-crash-timing-mined.md`.

**Steam must be running first**, or login dies with `Auth Failure 14005` (SteamAPI
init fails). Easy to miss; surface this gotcha if you see Steam not running.

**Shim readiness:** the launcher fires the injectors detached then blocks on the game,
so for a consolidated "did every shim activate?" view run `.\configs\shim-status.ps1`
(or `-Watch`) in a SECOND terminal. It's read-only — reads each shim's `docs/*-marker.txt`
and classifies READY / running / FAILED / leftover (anchored to the game's start time so a
shim that finished and went quiet still reads READY, and a marker from a prior launch reads
`leftover`). Safe to run anytime, including while another session has the game open.

The script blocks until the game exits. Read live `Loki.log` at
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (NOT `docs/` — that's
the backend `capture.log` for HTTP traffic). The loopback admin panel is at
`http://127.0.0.1:9210/` while `ags` runs (hunter unlocks, store/ownership, wallet,
mission progress, per-account state; see `docs/admin-panel.md`).

### ★ Tutorial sittings (FK-7 / FK-24 / anything in `LVL_Tutorial`) — HANDS-FREE

**Do not improvise this, and do not use `-Hook <play dll>`.** `RM_PLAY` and
`RM_SPAWNPOSSESS` are **continuation** modes: they attach to an already-running tutorial
and `return 0` before the force-open block, so a lone `-Hook` **cannot work** (S107 wasted
a launch proving it).

The old recipe needed a human to press PLAY → TUTORIALS → BASIC TRAINING → START. It no
longer does. That press has exactly ONE backend effect — `POST /startSoloMode` sets
`playerState.SoloMode` — and `handleCoreGamePlayer` gates on
`forceTutorialMatch || SoloMode != ""`. So flip the flag instead:

```powershell
# 1. server/internal/interactive/interactive.go -> const forceTutorialMatch = true
& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o ags.exe ./cmd/ags

# 2. ELEVATED PowerShell. Steam must already be running.
.\configs\launch-redirect.ps1 -NoHook          # returns after launching; game keeps running

# 3. SECOND call, once the game is up — stages the world and injects the DLL under test:
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\tutorial_launch_play.dll -Label myrun
```

MEASURED: with the flag on, the client parks itself **~13 s** after launch. `fk24-stage.ps1`
pre-flights that `ags` is really arming a match and refuses to run otherwise, then injects
`gft_ready_fix` → `tutorial_launch_fo` → `tutorial_launch_sp` → your probe, **gating each
step on measured evidence** and copying the marker off after every injection.
**Set the flag back to `false` when done** — otherwise a normal launch auto-parks into the
tutorial loading screen and looks broken.

⚠ **Order is load-bearing, and each of these cost a dead run:**
- `gft_ready_fix` goes **BEFORE** the force-open. The old documented `fo → gft → sp` order
  only worked because S107 injected all four back-to-back and gft landed *during* the 5.7 s
  LoadMap. Gate between them and the run dies with the log full of
  `ULokiGameFeatureToggles::Get … called when feature toggles were not ready`.
- Wait for `Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial` — **not** the bare
  string `LVL_Tutorial`, which the force-open's own echoed console command also contains.
- Wait for sp's own `[SP] done step=4` before injecting the probe. `ResolveSpawnPossess`
  and `RM_PLAY`'s resolve are both **one-shot, no retry**; a fixed 5 s sleep is not enough
  and the probe aborts at `[PL] ResolveWakeMove failed … -> abort` having armed nothing.
- `[SP] gm=0x0 pc=0x0 startSpot=0x0 heroClass=0x0` = the world is gone. Do not proceed.

**Expected yield: only ~2 of 4 launches reach the armed window.** Budget on *armed windows
reached*, never on launches.

Success looks like this in `docs\tutorial-launch-marker.txt`:
```
[SP]   gm=0x… pc=0x… startSpot=0x… heroClass=0x…        <- ALL FOUR non-zero
[SP]   done step=4 spawnedPawn=0x… cls=BP_HERO_Ronin_C
[PL]   *** init complete: body=BUILT; camera + WASD active ***
[ANIM] PlayAnimation(run, loop) ok / PlayAnimation(idle, loop) ok   <- locomotion animating
```

For iterative server-only restarts (game already running at menu, want to swap
backend behavior): kill `ags`, rebuild with
`& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`,
restart manually (regen certs + re-append to cacert.pem if you want a clean cert
chain). See `docs/hero-roster-attempts.md` "How to reproduce" for the exact recipe.

## Code conventions for this project

- Backend handlers live in `server/internal/<package>/<name>.go`. Each handler's
  comment block should record what was tried + what worked + what didn't, with
  dates. The trial-and-error history is the value.
- Probe-driven backend work: prefer **single-variable changes**. Bundled tests
  (10 changes at once) have repeatedly produced ambiguous results that wasted
  cycles. If a hypothesis fails, REVERT the probe before testing the next one.
- Validity model for endpoints: UE's `JsonObjectStringToUStruct` IGNORES unknown
  JSON keys and only rejects the whole doc when a key that DOES match has a wrong
  type. So adding speculative fields is safe; sending wrong-typed matched fields
  is not. See the comment at the top of `server/internal/menu/menu.go` for the
  full validity model.
- The two distinct LogLokiPlatformQuery error strings mean different things:
  `"Invalid response received"` = a required top-level field is absent.
  `"Deserialization failure"` = JSON parsed but container type mismatched target struct.

## Tooling shortcuts

- **Extractor:** `tools/extractor/` — .NET 9 / CUE4Parse-based. ★ **TRUE subcommand list is TEN**
  (`Program.cs:22`, verified S116): `dump names namesall schema assetregistry wherefile mkpak peekpak
  bpdump rawfile`. ⚠ The old list here was wrong twice: **`raw` is really `rawfile`**, and
  **`enumerate` is not a subcommand at all** — it is the no-subcommand default mode, and
  `out/allassets.txt` is the preserved crash log of someone typing it
  (`Paks: enumerate` → `DirectoryNotFoundException`). `bpdump` drove several breakthroughs and was
  undocumented. (This also settles ignorance-map row (c).)
  ⚠ **`dump` has NO output-dir and NO usmap override** — it always writes the repo `out/`, and the
  usmap is resolved ambiently by search order with no md5 logged. Output is **flat by basename** with
  **586 colliding basenames** (last writer wins). A proposed `--usmap` / `--out` / `--list` patch
  (~20-line argv pre-pass, prints the loaded usmap's md5) is at
  `scratchpad/fk14-assets/PROPOSED-extractor-flags.diff`.
  **Timing [M]:** ~32.9 ms/asset marginal + 1,436 ms startup ⇒ full re-dump **~59 min** at the current
  80-path chunking (**20.7 min of that is pure process startup**, 865 processes), or **~38 min** with
  `--list`.
  Build/run with
  `& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release` from `tools/extractor/extractor`.
- **usmap regeneration:** `tools/usmapdump/usmapdump.exe extract <exe-path>`
  produces `mappings.usmap`. Needed when game updates.
- **usmapdump RE commands:** `strings`, `wstrings`, `xref`, `disasm`, `peek`,
  `threads`, `findgametid`, `assetmgr` — read-only RPM, no injection.
- **usmapdump dumpimage:** `usmapdump.exe dumpimage <proc> [outDir]` — snapshots the
  live UNPACKED image to a cold PE for offline Ghidra/IDA (file-offset==RVA, ImageBase
  set to the live base, so project `base+0x…` addresses map 1:1). Also dumps private
  exec regions outside the module + a coverage manifest. Pure RPM (safe). CAVEAT: the
  build demand-decrypts `.text` pages on execution, so a single dump only captures pages
  the game has RUN — ~50% of `.text` at a fresh menu. Coverage rises the more code the
  game exercises; re-dump from a richer state (in-game) for more. Also writes
  `<stem>.exports.txt` (addr→module!export map, captured live) so `reconstructiat` can
  rebuild imports OFFLINE later. Dumps land in `/dumps/` (git-ignored).
- **usmapdump mergedumps:** `usmapdump.exe mergedumps <outFile> <in.dump.exe…|dir>` —
  unions several `dumpimage` snapshots into one maximally-covered image (fills each dump's
  demand-decrypt `.text` gaps from the others). A directory arg recurses for `*.dump.exe`.
  ★★★★★ **THE CANONICAL COLD IMAGE IS NOW `dumps/merged2.dump.exe` — `.text` 16,625 / 30,281
  decrypted pages (54.90 %), a STRICT SUPERSET of `merged.dump.exe` (15,833, 52.29 %) with
  0 regressions. Read `docs/fk18-fk19-multistate-merge-settled.md` before touching any of this.**
  ⚠⚠ **THE OLD TEXT HERE WAS WRONG IN BOTH HALVES, AND THE TWO ERRORS SEALED EACH OTHER IN
  (S121, 2026-08-14).** It said (i) *"dump from DIFFERENT game states (login, hero grid, store,
  missions…)"* and (ii) *"CONSTRAINT: all inputs must share the same module base."*
  **(i) is spent advice:** MEASURED, `menu`/`store`/`roster`/`missions`/`loadout` contribute
  **0 pages each** — they were five snapshots of ONE process lifetime (PID 4080, 4 minutes), and
  `.text` decryption is **monotone within a lifetime**, so the five are strictly nested
  (`menu ⊂ store ⊂ roster ⊂ missions ≡ loadout`) and the whole 5-way merge bought **0 `.text`
  bytes**. **(ii) is measured false:** `.text` carries **0 of the image's 1,403,750 base
  relocations** (they are 1,257,732 `.rdata` + 146,018 `.data`), and `.text` is byte-identical
  across ImageBases on every page two dumps both decrypted — **0 differing bytes in 10 of 10
  pairwise comparisons**. ⇒ constraint (ii) forced every capture into one lifetime, where (i) is
  provably worthless. **Relaunching between captures is now PREFERRED.**
  ★ `mergedumps` now merges **`.text` only, page-granular, ignoring ImageBase**, and checks every
  donor against the accumulator on shared pages (must be 0 conflicts, else the donor is rejected).
  `-wholeimage` restores pre-S121 semantics; `-samebaseonly` restores the old rejection.
  ⚠ **NEVER READ A MUTABLE GLOBAL OUT OF A MERGED IMAGE'S `.data`.** Under `-wholeimage` the
  union splices writable globals from differently-timed snapshots into values that never
  simultaneously existed, and *which* value you get depends on the seed — i.e. on directory-walk
  order (MEASURED: 4,678 `.data` bytes change identity from seed choice alone; the historical
  `merged.dump.exe` carries 1,195 spliced bytes in 335 runs over RVA `0x099C859B`–`0x0A0A2D39`).
  The default `.text`-only mode fixes this: `merged2`'s `.rdata`/`.data` are byte-identical to its
  single seed and are a coherent snapshot. Read globals from a single-state dump or live RPM.
  ⚠ The manifest's per-section % is **non-zero bytes**, which is sound for `.text` and meaningless
  for `.rdata`/`.data` — the manifest now prints the page metric beside it. Never compare the two.
- **usmapdump reconstructiat:** `usmapdump.exe reconstructiat <dumpFile> [outFile]` —
  rebuilds a real import table so Ghidra/IDA name API calls instead of raw IAT thunks, when
  the dumped IAT holds DIRECT resolved export addresses (unprotected binaries, e.g.
  explorer). Maps each slot to `module!export` via the `<stem>.exports.txt` sidecar, appends
  an `.idata2` section (descriptors + INT + names), repoints the Import data-dir. Fully
  OFFLINE. Validated on explorer (1066/1066). For SUPERVIVE use `deobfimports` instead — its
  IAT is import-PROTECTED (see below), so reconstructiat resolves ~0 of its slots.
- **usmapdump deobfimports:** `usmapdump.exe deobfimports <proc> <dumpFile> [outFile]` — the
  SUPERVIVE path. Its imports are import-PROTECTED (⚠ **NOT VMProtect/Themida — that name is
  REFUTED, see `docs/fk10-protector-identified.md`**): each IAT slot points to an
  obfuscated trampoline in a packer-hidden region (NOT any registered module), computing the
  real API as `real = C2 ^ ROL64(C1 + M, 0x33)` (per-stub C1/C2 imm64; M = a per-launch data
  qword) then `jmp`-ing to it. deobfimports EMULATES each stub (x86asm decoder + tiny integer
  interpreter) against the LIVE process to recover the real target, VERIFIES it against the
  exports sidecar (exact match — a mis-emulation can only yield "unresolved", never a wrong
  name), then rebuilds the table like reconstructiat. Needs the SOURCE process ALIVE (stub
  code + M are read live; M encodes the ASLR-relocated target). Validated: **1107/1107 slots,
  0 undecodable, 0 off-target**; output parses in `debug/pe` (all 1107 named). `capture-dumps.ps1
  -Finalize` calls this automatically while the game runs.
- **Manual mapper / DLL injector:** `tools/inject/` — for no-throw payloads only.
  ⚠ The recorded mechanism ("C++ exception unwinding gets eaten by the packer's vectored exception
  filter") is now DOUBTED, though the rule stands: S113 measured the game exe's
  `IMAGE_DIRECTORY_ENTRY_EXCEPTION` as **RVA=0 / size=0** (4 control binaries read fine), so
  `RtlLookupFunctionEntry` resolves nothing for the main image — which kills all three canaries
  identically without any VEH involvement. See `docs/fk10-protector-identified.md` §4.
- **Native shims:** `tools/sigbypass-mod/` — `catalog_store_fix` (roster/store/
  cosmetics), `missions_fix` (durable missions page), `mainmenu_refresh_pi8`
  (pick→center refresh), `loadout_fix`, `tutorial_launch`, plus the
  `missions_nativecall_probe*` RE series that built the native-call primitive.
- **Tutorial sitting driver:** `configs/fk24-stage.ps1` — stages the tutorial world and
  injects a probe/candidate DLL hands-free. `-Probe <dll> [-Label <tag>] [-SkipProbe]`.
  Copies the marker off after each stage into `docs/fk24-stage-<label>-<n>-<shim>.txt`,
  because `Marker()` opens `CREATE_ALWAYS` so **every injection truncates
  `docs/tutorial-launch-marker.txt`** (FK-25). See the launch procedure above.
  ★ **S114 FIX — it was silently taxing every tutorial sitting.** The parked-state gate tail-read only
  the **last 200 KB** of `capture.log`, but the client fetches `/core-game/matches` **once, early**, so
  on any log-heavy run that evidence had already scrolled out of the window and the gate could never
  pass — the stager then burned its full 420 s `WaitParkedSec` and aborted, **wasting the launch**.
  MEASURED: one attempt passed by luck (fetch 70 KB from the end), the next had the identical fetch
  **1.1 MB out of window**. Now reads the file whole; the gate passes in ~0 s.
- **Crash-dump archiver:** `configs/archive-crashdumps.ps1` — preserves Sentry/crashpad crash
  reports (the 43.8 MB minidump + that run's own `Loki.log`) out of
  `<GameRoot>\Loki\.sentry-native\` into `dumps\crashpad-<stamp>\`, SHA-256 verified, source never
  deleted. `launch-redirect.ps1` calls it automatically before launching and after the game exits;
  safe to run by hand anytime (`-Label <tag>`). Parse a dump with
  `python tools/crashtri/mdctx.py <reports/*.dmp>` — there is no cdb/WinDbg on this machine.
- **RPM probes:** `tools/re/*.py` — Python probes driving the native-call primitive
  (struct/field/rep-layout walkers, param/OUT-param builders, mission-model dumps).
  ★ **S114 console/exec family** (mostly OFFLINE, static-image): `console_probe.py` (pure-RPM live
  console/exec state — `ViewportConsole`, `UConsole` instances, decoded `DebugExecBindings`; 6/6
  offline self-test), `console_census.py` (controlled wide+ASCII multi-image token census),
  `exec_surface_probe.py`, `exec_chain_grade.py` (grades every verb on the `UPlayer::Exec` chain),
  `uht_funcflags.py` (`FFunctionParams` decoder → the 138 `FUNC_Exec` table, output
  `out/uht_funcflags_tuthero.csv`), `cvar_census.py` (→ `out/cvar_census_tuthero.txt`, the 44
  `loki.*` cvars), `guard_markers.py` / `guard_test.py` (the guard-exclusive-literal method),
  `cheat_reach_probe.py` (cheat-object reachability), `read_field.py` (raw single-field read).
  Config-side: `configs/set-debug-execbindings.ps1` — ⚠ **largely moot**, since `DebugExecBindings`
  are never evaluated; keep it only as the untested probe of whether a user `Input.ini` is read at all.
  ⚠ **Class lookups share a blind spot:** `obj_by_class.py` matches by SUBSTRING and
  `cheat_reach_probe.py` by `endswith`, and **neither finds `PC_MainMenu_C`** — which is the live
  menu PlayerController. Using one as the "proven" cross-check for the other produced a false
  "there is no PlayerController at the menu" in S114. **Two instruments that fail the same way are
  not corroboration** — use a class-derivation walk. (`cheat_reach_probe.py`'s derivation walk was
  also broken — it reported `LokiGameInstance LIVE=0` on a running game — and was FIXED in S114;
  its own `[CTRL]` gate is what caught it.)
- **Admin panel:** loopback JSON API + embedded GUI in `server/internal/admin/`
  (`-admin`, default `http://127.0.0.1:9210/`). See `docs/admin-panel.md`.

## What NOT to do

- Don't run `launch-redirect.ps1 -Revert` casually — that strips the hosts entries
  + cacert mods. Only when the user explicitly asks to clean up.
- Don't use Steam to launch the game for testing the redirect — Steam launches the
  exe with no `-ini:` overrides, so the backend redirects don't apply.
- Don't kill the `SUPERVIVE-Win64-Shipping` process without warning — the user may
  be mid-test.
- Don't propose another C++-exception-using payload for injection. We tested
  three canary variants; the packer's exception handler kills the process even
  with `__CxxFrameHandler3` properly imported.
- Don't propose `ScanPrimaryAssetTypesFromConfig` as a shim target again — the
  function `__report_gsfailure`s mid-call regardless of thread context (verified
  via off-thread call, thread-hijack with fresh stack, thread-hijack with own
  stack, and APC on the real game thread).
- **Don't try to open the dev console, and don't re-test it.** `ALLOW_CONSOLE == 0`, measured three
  independent ways in S114: `~`, `ToggleConsole`, `ConsoleKeys`, an `EnableCheats`/`CheatManagerClass`
  ini knob and every command-line variant are all dead, and `ViewportConsole` is NULL **by
  construction** (the viewport never builds one). ⚠ Also dead: **`-ExecCmds`** and **`-LogCmds`** —
  neither has a parse literal anywhere in the image. The working channel is
  `UKismetSystemLibrary::ExecuteConsoleCommand` (thunk `0x395D790`) via the native-call primitive,
  which this project has been using since ~S91. See the console/exec block above.
- **Don't accept "the call returned ok" as evidence a verb ran.** S114 got
  `console 'LogLoc' ok` from a call that never reached a PlayerController at all. **Only the verb's
  OWN output counts** — and pick a verb that actually emits: **`God` prints nothing whatsoever**, so
  its silence is uninterpretable. `LogLoc` (→ `LogCheatManager: BugItGo …`) is the graded verifier.
- ★★★ **THE TUTORIAL ROUTE NO LONGER WRITES `.text` AT ALL (S112, shipped 2026-08-08).** RM_PLAY's
  `ProcessInternal` patch is gone: `KFUNCSWAP` and `KFSNAME` now DEFAULT to the heap
  `UFunction.Func` swap, so the shipped `tutorial_launch_play.dll` (`.text 5151621d2154e454`) arms on
  **`swapped=2` heap pointers** and touches no module image. MEASURED: standing `.text` **10/10 armed
  windows died** vs no module-image write **2/30**, Fisher **p = 0.00000008**; at a matched 600 s hold
  the heap form was **0/16**. `SafeWrite` is linker-eliminated from the shipped DLL — verifiable by
  `FlushInstructionCache` / `VirtualAlloc` / `VirtualFree` being ABSENT from its import table.
  Rollback = `build.ps1 -Variant play-textpatch` (`433cf7d8f6a0770f`), which is also the A/B's control
  arm, so the rollback is a measured quantity rather than an untested path.
  ⚠ The other PI-hookers (`mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix`) STILL patch `.text`
  transiently — the MENU route is unconverted. `tutorial_launch.cpp`'s `FsScan`/`FsThunk` is the
  worked example to copy.
- Don't leave a permanent `.text` patch in place — the ~3–5 min code-integrity
  check catches it and kills the process. ★★ **S111 MEASURED THIS, and it is far worse than
  "permanent" — even a SELF-RESTORING patch is lethal while it stands.** One-variable bisect at 1
  image / 320 s: patch standing **11/12** deaths vs no patch **0/5**, p = 0.00097
  (`docs/s111-bisect-jz-is-the-trigger.md`). Removing the VEH or the exec-stub/vtable hook changed
  nothing; removing the 2-byte `.text` write stopped every death. The whole ladder is explained by
  **how long a `.text` modification stands**: `-NoHook` 0 %, inert mapped DLL 0 %, production
  (patch restored ~6 s after catalog load, so standing ~5–45 s) **28 %**, controls that never
  restore ~90 %. ⇒ **the `.text` patch is the single biggest self-inflicted hazard in the project.**
  ★ `catalog_store_fix` NO LONGER PATCHES AT ALL (2026-08-06): `KNOJZ` defaults to 1, the shipping
  build contains no `.text` write, and the roster still renders because the shim's existing
  **`[+0x354]` DATA poke** is sufficient — screenshot-verified (`docs/s111-jz-dropped-shipping.md`).
  Rollback = `-Variant jzpatch`. **Prefer a data write over a `.text` write in every new shim.**
  ★★ **AND IT IS `.text` SPECIFICALLY, NOT CODE MODIFICATION** (S111 arm J,
  `docs/s111-armj-bytecode-vs-text.md` — predicted from source *before* running, then measured):
  `catalog_pick_fix` **permanently** patches UFunction **Script bytecode** (heap `TArray<uint8>`,
  `EX_Return`+jump, never restored) and is **0/9 deaths at a 320 s hold — identical to injecting
  nothing** — while a *self-restoring* 2-byte `.text` write is **7/8** (p = 0.00041). Ladder at
  320 s: nothing **0/22** · bytecode **0/9** · transient `.text` ×3 **4/12** · standing `.text`
  **7/8**. ⇒ **express shim effects as DATA or BYTECODE writes; never touch the module image.**
  ⚠ **The `-Hook` primary injection silently fails ~1 in 10** (S111 caught one with a treatment
  guard). Never assume "copied the file ⇒ injected" — verify via `docs/inject-watch.out.log`
  changing *and* naming the DLL, or via the shim's own marker stamp.
  ⚠ The other four shims (`mainmenu_refresh_pi8`, `loadout_fix`, `missions_fix`) still install
  `ProcessInternal` prologue patches — also `.text` writes, never bisected individually.
- Don't leave a `ProcessInternal` hook PERMANENTLY installed if another PI-hooking shim
  is present — they race on the prologue. Coexisting PI-hookers must install the jmp only
  TRANSIENTLY and serialize via the shared `Local\SuperviveMissionsPIHook` mutex (the way
  `mainmenu_refresh_pi8` / `missions_fix` / `loadout_fix` do). That's what lets all three
  inject together in the default set — any NEW PI-hooking shim must follow the same pattern.
- ★★★ **Don't trust the usmap's CONTAINER INNER or ENUM UNDERLYING types — they are ~70 % wrong,
  DETERMINISTICALLY, in every usmap this project has ever produced (FK-14 SETTLED, S116).** The old
  rule here ("wrong for *replicated* container types … verify against live RPM") was mis-scoped in
  BOTH directions and is replaced by: **container inner + enum underlying types are wrong regardless
  of replication; struct names, property names, super-struct links, `StructProperty` type names,
  scalar types and enum VALUE tables are identical across every extraction ever taken and CAN be
  trusted.** Root cause = `tools/usmapdump/extract.go:115` reads a container's inner **inline at
  `FField+0x80`**, which is past the end of the object, so it captures **whatever FField the allocator
  placed next** (`ArrayProperty+0x80` is 99.8 % pointer-ranged with only **39 distinct values** — it is
  literally the next FField's vtable). ⚠⚠ **The correct offsets are PER FAMILY — they do NOT share
  one** (each 100 % with a 0 % runner-up, two independent passes over 44,398 properties):
  `FArrayProperty::Inner` **`*(+0x78)`** · `FSetProperty::ElementProp` **`*(+0x70)`** ·
  `FOptionalProperty::ValueProperty` **`*(+0x70)`** · `FMapProperty::KeyProp` **`*(+0x70)`** /
  `ValueProp` **`*(+0x78)`** · `FEnumProperty::UnderlyingProp` **`*(+0x70)`** / `Enum` **`*(+0x78)`** ·
  type-carrying families (Struct/Object/Class/Soft*/Weak/Lazy/Interface/Byte) **`+0x70`**.
  ★ **`sizeof(FProperty) == 0x70` and the layout is essentially STOCK** — `+0x70` is uniformly the
  derived class's first member. The one deviant is **`FArrayProperty`, which has an 8-byte hole at
  `+0x70` (UNIDENTIFIED — not `ArrayFlags`) with `Inner` at `+0x78`.**
  ⚠⚠ **The aggregate "containers are at `+0x78`, 96.6 %" is an OVER-GENERALISATION that holds for 1 of
  5 families** — it decomposes exactly as Array 3,548 + Map *Value* 555 at `+0x78`, and Set 142 +
  Optional 2 + Map *Key* 555 at `+0x70`. **Calibrate per family AND per member, never pooled:** a
  pooled score blesses `+0x78` at 96.6 %, clears a 90 % gate, and ships a silently-broken
  Map/Set/Optional build **certified**.
  ⇒ **The extractor is DETERMINISTIC** (3 back-to-back runs byte-identical); FK-14's "non-deterministic"
  headline is REFUTED — the variance is **heap adjacency**, frozen within a process, different across
  launches. Never take an array **stride** from the usmap. Where an element type matters use
  `tools/asdump/out/binds_members.csv` or the UHT `FPropertyParams` oracle in
  `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`.
  ⚠ **`tools/extractor/out` (69,142 JSON / 1.3 GB) is invalidated for container + enum values** —
  confirmed in shipped output (`BP_StoreOffer_StarterPack.json` → `"AssetGrants": [0,5,0,3,10,0,0,0]`).
  Scalars and struct-typed properties are fine, so the **backend model work is largely SAFE**
  (`endpoints.md:49`'s `CoreGamePlayer` is 4 scalars — untouched by this).
  ⚠ **Two prior walls were built on this artifact:** `DefaultMappingContexts` is
  `TArray<FDefaultContextSetting>` (so **S79/S80's "measured as EMPTY" was read against a wrong inner
  type**), and `ScreenEffectCollections` is `TArray<UMaterialParameterCollection*>` — **NOT**
  `ELokiGameFeatureToggle`, so **the S88 toggle wall chased a `labelPtr` hit on adjacent heap.**
  ⚠ **`pipeline.go:214` silently overwrites the canonical `tools/extractor/mappings.usmap` on EVERY
  `usmapdump extract`, from any CWD** — that is how the canonical file became an orphan whose
  `schema.txt` is unrecoverable. Backup: `scratchpad/fk14-safety/`. Delete that write.
  ⚠ FK-1's recorded root cause (`usmap.go:325 writeInnerOrByte`) is a **downstream workaround**, not
  the cause; its "**unknown-typed**" filter has fired **ZERO** times and its cited `SpawnSelectEndTime`
  defect is **not a defect** (UHT says `Float` is correct). Read `docs/fk14-usmap-settled.md` first.
- **Don't read "no `UECC-*` directory in `Saved\Crashes`" as "the run died with no dump."**
  Sentry's **crashpad** writes a full minidump (43.8 MB) plus that run's own `Loki.log` into
  `<GameRoot>\Loki\.sentry-native\`. `harvest.py` and every hand-rolled census that enumerates
  `UECC-*` is blind to it. The clean tell in `Loki.log` is `handing control over to crashpad`.
  ⚠ That key is **NOT the last line** (two `LogTemp` lines follow it in the one death with a
  preserved dump) — scan the whole file, never `tail`. Bare `crashpad` is useless as a key: it
  matches two **startup** lines present in every session.
- **Don't rush to save a crashpad dump — and don't trust the retired "~60 seconds" advice.**
  RETRACTED S109: the old "uploads and DELETES it within ~3 minutes" was the gap between two `ls`
  calls with a relaunch inside it. MEASURED: crashpad tries **one** upload at crash+2 s, and on
  failure the report sits in `state=Pending` **indefinitely** (65+ min observed) because
  `crashpad_handler.exe` dies with the game and cannot retry. **The NEXT GAME LAUNCH is what
  clears it.** `launch-redirect.ps1` now archives the database automatically before launching and
  after the game exits (`configs/archive-crashdumps.ps1`, SHA-256 verified, never deletes the
  source); run it standalone anytime. ⚠ It depends on the upload failing — if the archiver ever
  warns "crashpad handoff but NO report on disk", uploads started succeeding and you must
  hosts-block `o566896.ingest.sentry.io`. See `docs/s109-fk9-capture-durable.md`.
- **Don't leave an S9x diagnostic switched on and then reason about the game.** This has now
  bitten twice: `KTESTACTOR` (S106) built a second degenerate body, and `KSTATICTEST` (S108b)
  called `PlayAnimation` on a `StaticMeshComponent`, faulting every run — SEH-caught, so it
  never crashed, it just printed `anim swapping DISABLED for the rest of the session` and
  **killed the hero's walk/run animation in every session for weeks**. Both defaulted to 1
  in shipped builds. When a shim behaves oddly, audit what the *shim* is doing before
  theorising about the game.
- **Don't A/B two DLLs without diffing their `.text` sha256.** Three artifacts have shipped
  identical-but-differently-named, and an A/B against a copy of itself burns a live run.
  When a `-D` default changes, DELETE the now-redundant variant rather than leaving a
  duplicate (S108b removed `play-nostatictest`/`play-nodiag` for exactly this).

## Working style

**Never bank, never treat any wall as final.** There is always another angle. Keep pushing
continuously; do NOT recommend stopping or "banking at the ceiling."

**Why:** this is a marathon reverse-engineering effort and the user wants relentless forward motion —
every "hard wall" in this project's history was eventually cracked by finding a new lever.

- Do NOT end a session by recommending "bank it" or presenting stop-vs-continue as the main choice.
  Keep generating and testing new hypotheses.
- When context is about to run out, THEN produce (a) a fresh-session handoff prompt and (b) updated
  documentation so a new session continues seamlessly (see the existing `docs/next-session-prompt-*.md`).
- Before declaring any wall "definitive," question your own assumptions and tools first — validate
  that the primitive you're using (a ProcessEvent RVA, an offset, a call convention) is actually
  correct. **A broken tool masquerades as a wall**, which is the whole subject of the method rules
  below.

## Method rules — read `docs/method-rules.md` first

Two standing rules that are not about any one subsystem, and that have overturned more walls here
than any single investigation:

1. **★★★ The instrument-artifact pattern** — the project's dominant error mode: an instrument's
   blind spot recorded as a property of the game. **43 confirmed instances**, each of which closed a
   technique, each of which fell in minutes. Read it before recording ANY negative result as a
   property of the game. Includes the nine "how to apply" rules — positive controls, naming the
   artifact you measured, and **rule 9: grep for the claim before correcting one instance of it.**
2. **★★ Read the shipped artifacts first** — check whether the game already ships the answer in
   plaintext before reaching for a debugger. Four multi-session walls fell to that alone.

## Where knowledge lives

Everything is in the repo, under version control — there is no separate memory store (the Claude
memory directory was migrated into `docs/` and removed on **2026-08-12**; it duplicated `CLAUDE.md`
and `docs/` at a fourth compression level, and its claims could not be `git blame`d or reverted,
which is a bad property for a project whose value is its retraction history).

- **`CLAUDE.md`** (this file) — the auto-loaded digest: current status per subsystem, closed
  hypotheses, and the "what NOT to do" list. ⚠ **A digest is an instrument** — S115-d is the
  instance where compressing a table into prose here manufactured a false claim that read as a hard
  measurement conflict for a full session. Never print a byte string next to an address it did not
  come from.
- **`docs/ignorance-map-s101.md`** — the living index: the FALSE_KNOWN register, the walls register,
  instrument blindness, and the ranked focus plan. Kept in lockstep with this file.
- **`docs/<fk-n>-*-settled.md`** — the primary evidence for each settled unknown, with the
  measurements and the controls. These are ground truth; this file is a summary of them.
- **`docs/method-rules.md`** — the two method rules above.
- **`docs/next-session-prompt-*.md`** — chronological handoffs.

⚠ **Historical handoffs still say things like "read memory `supervive-x`".** Those are dated
archives and were deliberately NOT rewritten — editing them would falsify the record of what a past
session was actually told. Successors for the names that appear:

| retired memory | now |
|---|---|
| `instrument-artifact-pattern` | `docs/method-rules.md` §1 |
| `read-the-shipped-artifacts-first` | `docs/method-rules.md` §2 |
| `never-bank-directive` | this file, "Working style" |
| `ags-cert-rebuild-gotcha` | `docs/ags-cert-rebuild-gotcha.md` |
| `angelscript-layer`, `fk1-*` | `docs/fk1-angelscript-settled.md`, `docs/fk1-stub-claim-recheck.md` |
| `cheat-surface-inventory` | `docs/fk6-cheat-surface-settled.md`, `docs/fk13-console-exec-settled.md` |
| `crashpad-capture-runtime-family` | `docs/s109-fk9-capture-durable.md`, `docs/fk8-crash-timing-mined.md` |
| `tutorial-crash-fk7` | `docs/fk7-crash-settled.md` (SUPERSEDED banner) → `docs/s112-fk7-ab-results.md` |
| `gc-reachability-mechanism` | `docs/s110-item-watch-gc-mechanism.md` |
| `input-mechanism-settled` | `docs/fk2-input-settled.md` |
| `protector-identified` | `docs/fk10-protector-identified.md` |
| `log-verbosity-available` | `docs/fk11-log-verbosity-settled.md` |
| `battle-gate-fk5` | `docs/fk5-battle-gate-settled.md` |
| `dedicated-server-status` | `docs/dedicated-server-stub.md` |
| `hero-roster-blocker`, `store-status` | `docs/hero-roster-attempts.md` + the roster block above |
| `missions-page-status` | `docs/missions-progression-hookup.md`, `docs/session-59-progress-bars.txt` |
| `passes-battlepass-status` | `docs/session-83-passes-tier-grid-solved.txt` |
| `avatar-render-status`, `customization-persistence` | `docs/session-85-avatar-render.md` |
| `tutorial-launch-status` | the `docs/s108-*` family + `docs/fk31-fk32-successors.md` |
| `milestone3-trackb-status` | `docs/trackb-notes.md`, `docs/endpoints.md` |
| `strxref-symbols` | `docs/strxref-{known-addresses,open-questions,state-coverage,vtables}.md` |
| `coverage-audit-s101` | `docs/coverage-audit-s101.md` ⚠ its known/unknown map is **stale** — FK-1/5/10/11/13 have all settled since; use `docs/ignorance-map-s101.md` |
