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
(abilities / combat) and the **staging hazard** — ~25 % of launches still die before the probe is
injected, with only `gft`+`fo` resident.
⚠⚠ **"the hero owns no ability system" WAS THE OLD TEXT HERE AND IT IS FALSE — killed by FK-30 at
S111, and this digest carried it for 22 sessions.** The ASC exists and is populated; what is NULL is
**`AvatarActor`**, and `ActivatableAbilities` is **0**. ⚠ And the ASC is **the SHIM'S OWN** — the game
wires nothing on this route, because the designed wiring is inside FK-1's stripped `SpawnPlayer`.
★★ **The bind function was FOUND and has NEVER BEEN CALLED:** `InitAbilityActorInfo` at
**`base+0x447F410`** `(rcx=ASC, rdx=Owner, r8=Avatar)`, with `AbilityActorInfo` at `ASC+0x418`
(`docs/s111-asc-census.md:568` §13; written up as **"TASK ONE"** at `docs/next-session-prompt-s111.md:15`).
**[M] `grep -rn "447F410\|InitAbilityActorInfo" tools/sigbypass-mod/` returns ZERO.**
⚠ The register's *"the BIND is not reachable"* (`ignorance-map-s101.md:1688`) is narrowly true (no
REFLECTED route) and **operationally obsolete** — plain direct calls to non-reflected natives became
standard at S123 (`AddToRoot 0x489F9B0`, `PrimePools 0x3356000`, `ResizeGrow 0x00F988D0`, flown x7 in
S132). That register row **never records the address**, so a reader of it alone concludes the bind is
unlocated. ⚠⚠ **CONFOUND — `#define KWIREGAS 1`** (`tutorial_launch.cpp:4869`) drives
`WireAbilitySystem(hero, pc)` on EVERY `RM_PLAY` init and `RM_SPAWNPOSSESS` completion: it spawns the
carrier, builds the ASC and two attribute sets, forces `ROLE_Authority` and writes `@0xF00`. That is
why `s111-asc-census.md` needed a retraction banner. **An ability-bind result read out of a shim
already doing all that is uninterpretable unless KWIREGAS is controlled for.**

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
★★★★★ **THE KILL JUMPS TO ONE FIXED ADDRESS, AND IT IS THE SAME ADDRESS EVERY LAUNCH (S131, 2026-08-20).
Read `scratchpad/s131/evidence/FK31-kill-address-is-constant.md`. Offline, from minidumps already on disk; zero launches.**
Over the crashpad minidumps matching {`0xC0000005`, `ExceptionInformation[0]==8` (EXECUTE), `addr & 0xFFF == 1`}, the
faulting address takes **exactly three values, one per boot session**.
⚠⚠ **THE COUNTS RECORDED HERE WERE A LARGE UNDERCOUNT — CORRECTED S133 (2026-08-20), reproduced twice by
independently written parsers.** This file said *"31 minidumps … 13 / 11 / 7"*. **MEASURED: 361 FILES /
108 DISTINCT REPORTS**, split `0x7FFD3B400001` **342 files / 99 reports** · `0x7FFA42600001` **11 / 4** ·
`0x7FFB57400001` **8 / 5**. Whole corpus: **393 exception streams, ALL `0xC0000005`**, `ExceptionInformation[0]`
= EXECUTE **361** / READ **32**. Eras 2 and 3 reproduce S131 exactly (11 vs 11, 8 vs 7 — the extra is
`crashpad-20260820-143225`, archived after its sweep); **era 1 does not — S131 saw 13 files from 08-08/08-09
and missed **310 files / 83 reports** dated 2026-08-04 → 08-07.** ⚠ "329" is `342 − 13` — *files S131
did not see* — relabelled as a date range; and era-1 files dated 08-08/08-09 number **32**, so 13 is
not "all of 08-08/09" either.
⇒ **The per-boot constancy finding is UNAFFECTED and STRENGTHENED** (the three values are exactly the three
S131 named, now at n=108 distinct reports). What changes is the SHAPE: the recorded 13/11/7 reads as
near-uniform; the truth is **99 / 4 / 5 by distinct crash — era 1 dominates by ~20×.**
⚠ Also *"two `0xC0000005` READ faults … correctly EXCLUDED"* undercounts: there are **32 READ faults by file /
16 by report**, of which **14 are `RIP & 0xFFFF == 0x205d`** (⚠ **`RIP`, not the faulting address** — the faulting
addresses are 16 distinct values and `0x205d` appears among them zero times; this file's own rule is
*"classify each death by `RIP & 0xFFFF`"*) — `catalog_store_fix.dll`'s own heap scan (FK-8
family B, all 2026-08-04→08-06, ending at the S111 fix). Still correctly excluded; the count was wrong.
★★ **AND THE "unevaluatable from a minidump" RULE IS FALSE FOR THE UECC CORPUS (S133).** A fresh
  T+9 s FK-31 death (menu route, during D3D12 RHI init) produced
  `UECC-Windows-D1834DBF…/UEMinidump.dmp` whose **ModuleList NAMES `runtime.dll` at
  `0x7FFB57400000`** while the fault is at `0x7FFB57400001` — **literally `base + 1`, directly
  evaluated.** The "no module entry (0 of 14)" measurement is true of the **SENTRY crashpad** corpus
  and does not generalise. Same scope error as the `.rdata` instrument mix-up.
⚠ **S131's evidence file calls `scratchpad/s131/tools/{ripfamily,ripdelta,modscan}.py` "read-only, re-runnable";
they DO NOT EXIST on disk**, which is why its glob could not be reproduced. Re-derive with
`scratchpad/s133/tools/verify_pagemap.py`-style parsers, and **quote FILES vs DISTINCT REPORTS** — the archiver
writes a `-DEATH` archive plus an untagged follow-up per crash, so files run ~3.3× reports here. **[M] Within a boot it is bit-identical across every launch** while `SUPERVIVE.exe` and
`preloader.dll` are re-based by ASLR every launch. **[M] It is NOT an offset from any loaded module** — `RIP - base`
takes 3 distinct values for ntdll / kernel32 / kernelbase / user32 / combase alike — and **no module and no
executable region covers it**. A corrupted pointer does not reproduce to the bit across 13 launches.
- ★★ **This UNIFIES three separately-tracked death classes**: FK-7's standing-`.text` kills, FK-31's staging-hazard
  deaths (`s127-fk31-staging-death`, `s128-fk31-longpark`, `s130-cdopoke-att1`, S131's launch-1) and the S114/S115
  menu-route deaths all land on their boot's one address. ⇒ **[M] one kill routine, not three.** ⚠ It says nothing
  about the TRIGGER — two detections can call one killer.
- ★★★★★ **AND THE TARGET IS NAMED: IT IS `runtime.dll + 1`, MEASURED LIVE.** One `VirtualQueryEx` on the
  live client (`scratchpad/s131/tools/fk31_map_kill_page.py`, read-only) reports the page as
  **`MEM_COMMIT / READONLY / MEM_IMAGE`, `AllocationBase == the address itself`**, and at that base sit
  **`4d 5a` = `MZ`**, a valid `PE`, `SizeOfImage 0x4066000`, and 11 sections named
  **`.pdata .rwx packer0 packer1 packer2 .rsrc .reloc packer30 packer40 packer31 packer42`** — exactly
  FK-10's recorded layout for `runtime.dll`. `(Get-Process).Modules` reports **no module at that base**
  ⇒ it is **MANUALLY MAPPED and hidden from the module list**, which is why it never appears in a minidump.
  ⇒ **THE KILL IS A DELIBERATE JUMP INTO THE PROTECTOR'S OWN READ-ONLY DOS HEADER** — a crash primitive,
  sibling of FK-10's measured `NtTerminateProcess(h, 0xDEAD)` at `runtime.dll` RVA `0x80f7f0`. The page
  being READONLY is exactly why the fault is an EXECUTE violation (`ExceptionInformation[0]==8`).
  ★ **This VINDICATES `RIP == runtime.dll base + 1`** and measures it live for the first time; it also
  explains the per-boot constancy (the protector maps itself at a per-boot-stable base, unlike the
  ASLR-rebased `preloader.dll` and game exe).
  ⛔ **The "map an executable page there" experiment is DEAD** — the page is already committed.
  ★ **BETTER REPLACEMENT LEAD, and it is purely OFFLINE:** FK-10 established `runtime.dll` is NOT packed
  (46.6 MB of plaintext x86-64, loader function table at RVA `0x14D8758`). **Search it for code that
  computes its own image base + 1 and jumps there** — that lands on the routine that decides to kill,
  which is what FK-10's Wall #7 has been hunting. Start in `packer30`.
  ⚠⚠ **RUN, AND LARGELY A DEAD END — S132, and BOTH halves of that instruction are refuted.**
  **(a) "Start in `packer30`" is wrong:** `packer30` holds **0 of the 4,769 computed tail jumps**. The
  protector's dispatch is a computed tail — `jmp <reg>` with the target carried as
  `movabs reg, -(ImageBase + RVA)` inside an MBA polynomial — and those live elsewhere.
  **(b) "search for the image-base + 1 constant" is confounded AT THE TARGET, not at the tool:**
  `ImageBase == 0x200000000 == 2^33`, so every such test is aliased with ordinary MBA arithmetic on
  bit 33. ⚠ Do NOT restate that as *"a constant search cannot be decisive"* — **that stronger form
  was itself REFUTED by adversarial verification**: the hits are individually adjudicable and the
  search **was** decisive.
  ★★ **IT PRODUCED A CONCRETE SUCCESSOR LEAD: `packer31 0x03C8EDF2` computes
  `variable + ImageBase + 1`, and the result is DEREFERENCED at `0x03C8EFF3`. READ IT.**
  ⚠ [S] on its role — it matches an MSVC inline-buffer idiom, so a biased pointer is likelier than
  the kill; that is a reason to read it, not to skip it.
  ★ Separately [M]: FK-10's kill primitive at RVA `0x80F7F0` has its **owning vtable at
  `packer0 RVA 0x1831C0`** and the **constructor that installs it at RVA `0x7F86F0`** — that table's
  only xref image-wide, and the next thing to read after `0x03C8EDF2`.
  ⚠⚠ **AND ONE GRADE CORRECTION THAT MATTERS: *"`0x80F7F0` IS `NtTerminateProcess(h, 0xDEAD)`"* is
  [I], NOT [M]** — the syscall number is computed at runtime and on disk evaluates to `0xFFFFFFFF`,
  which is not a valid service number. **The `0x0000DEAD` EXIT CODE is measured; the identity of the
  syscall that produces it is inferred.** This file and `docs/fk10-protector-identified.md` both
  carried it as [M].
  ⚠⚠ **AND THIS WAS A SELF-CORRECTION WITHIN THE SESSION.** The §1–§6 write-up said "no module covers it",
  from minidumps alone — an instrument blind to manually-mapped images BY DESIGN. **One query from a
  different instrument refuted it inside the hour**, and it was only run because a lever's precondition
  was being checked before building an arm. Read `scratchpad/s131/evidence/FK31-kill-address-is-constant.md`
  §7 — it governs the rest of that file.
- ⚠⚠ **A RECORDED RULE THAT CANNOT BE APPLIED AS WRITTEN.** This file says *detect the kill by `RIP == runtime.dll
  base + 1`*. **[M] `runtime.dll` has NO module entry in ANY crashpad minidump** (0 of 14 sampled; positive control
  `preloader.dll` present 14/14), so that half is unevaluatable from a minidump and a successor will read the
  missing module as "the family does not match". **Restate as: `ExceptionInformation[0]==8` + address == the boot
  session's constant kill address.**
- ★★★ **AND IT HANDS FK-31 ITS FIRST CHEAP EXPERIMENT.** The target is knowable in advance within a boot — read it
  off the last crash. **Map an executable page there before arming** (`VirtualAlloc(<addr & ~0xFFF>, 0x1000,
  MEM_COMMIT|MEM_RESERVE, PAGE_EXECUTE_READWRITE)`, `ret` at `+1`). If the jump returns instead of faulting, the
  process may survive **and the stack names the caller** — the protector code that decided to kill, which is what
  FK-10's Wall #7 has been hunting. One `VirtualAlloc` in an injected DLL; no `.text` write, no PI hook.
  ⚠ The address may already be RESERVED (then the alloc fails and the probe must say so); the jump may be a tail
  `jmp` rather than a `call` (then the stack top is the grandparent frame); returning mid-routine may crash
  elsewhere. **All three are observable and all three beat a silent process death.**
- ⚠ Count honestly: **31 is FILES**, and the archiver writes a `-DEATH` archive plus an untagged follow-up per crash,
  so distinct crashes are roughly half. The per-era constancy is unaffected. Two `0xC0000005` dumps in the corpus
  are READ faults at heap addresses and are correctly EXCLUDED, not folded in.
- ⚠ "Per boot" is **[I]** — the three groups line up with long date gaps, but no reboot timestamp was checked.

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
  ⚠⚠ **THAT POINTER WAS BROKEN FOR SESSIONS AND IT COST REAL WORK (fixed S136).** It used to read
  *"use `verify_dll.py` or the section-hash snippet in `docs/s109-dump-forensics.md` §23"* — [M]
  **`verify_dll.py` contains ZERO hash code** (0 matches for sha256/hashlib/md5/sha1) **and §23 of
  that doc contains no snippet** (1 hash mention in the whole file). Two sessions followed it, found
  nothing, and concluded no recipe existed on disk — which is how the S136 handoff came to call
  writing one "an outstanding task". **THE WORKING IMPLEMENTATIONS ARE:**
  • **`tools/sigbypass-mod/text_digest.py`** (S136; emits BOTH recipes) — use this.
  • `configs/fk7-ab-run.ps1:94 Get-TextHash` — RAW; **EMITS it at :131** and persists it to the A/B
    CSV column `probe_text_sha` (:117, :134). Its own comment already called it *"the ONLY safe way
    to tell two shim builds apart"*.
  • `configs/fk24-stage.ps1:77 Get-TextHash` — RAW; prints only inside a stale-shim abort.
  • `docs/method-rules.md:213` (S134-d) — the **VIRTUALSIZE** variant,
    `min(VirtualSize, SizeOfRawData)`, which is what produced the S135 bot gates.
  ⚠ **Two recipes are in concurrent use.** See the S136 digest block below before quoting any gate.
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

### Before touching anything GC- / rooting- / "my shim's object got collected"-shaped
★★★★★ **SETTLED (S123, 2026-08-15) — read `docs/fk27-successor-gc-rooting-settled.md`.** Offline
disassembly + read-only RPM, **zero launches, zero injections, zero `.text` writes.** FK-27 stays
closed; what it never had was the MECHANISM, and the mechanism comes with **a working rooting recipe
the project did not have.**
- ⚠⚠ **TWO UNRELATED REASONS AN OBJECT SURVIVES GC. Conflating them is the trap, and it is the trap
  S109/S110 fell into.**
  **(a) The disregard-for-GC pool — excluded by INDEX, no flag involved.** `GUObjectArray` is at
  **RVA `0x9E38920`**: `ObjFirstGCIndex@+0x00 = 39295`, `ObjLastNonGCIndex@+0x04 = 39294`,
  `MaxObjectsNotConsideredByGC@+0x08 = 45000`, `OpenForDisregardForGC@+0x0C = 0`. All three
  whole-array sweeps iterate `[ObjFirstGCIndex, NumElements)`, never from 0 (`0x01259162` START,
  `0x0125916D` END). **Nothing below 39,295 is ever traversed, marked, or freed.**
  **(b) Real roots — a REGISTRY; the flag is only bookkeeping.** `AddToRoot` (1) inserts the
  `InternalIndex` into a **`TSet<int32>` at `.data 0x99D3CA0`** under the critical section at
  `.data 0x9E23BF0`, then (2) ORs `0x40000000` into `FUObjectItem.Flags`. The gather
  (`.text 0x1259020`, `"GC.MarkRootObjectsAsReachable"`) copies that set to a `TArray<int32>` and
  `ParallelFor`s over the **indices**; the mark body `0x123E3B0` has **no bit-30 predicate**.
  ⇒ an `InterlockedOr` writes the mirror and never enters the gather. **That is FK-27's inertness,
  mechanically.** [M] the registry holds exactly **32** entries, **set-identical** (zero symmetric
  difference) to the 32 high-index bit-30 objects a full 200,475-object flag census finds.
- ⚠ **`RVA_OBJOBJECTS = 0x9E38930`** — the constant in `tutorial_launch.cpp:23`, `item_watch.py:60`
  and ~20 shim sources — is `FUObjectArray + 0x10`, the *inner* `ObjObjects`. Correct for its use,
  but it is **why nobody had the disregard fields: they sit 0x10 BELOW it.**
- ★★★★★ **AND INSERTING IS *SUFFICIENT*, NOT MERELY NECESSARY — `KeepFlags == 0`, so GC mark body B
  is DEAD and the registry is the ENTIRE root seed.** `CollectGarbage` parks `KeepFlags` in a static
  global at **`.data 0x9E25348`** (= `state->KeepFlags`, `state` at `0x9E252C0`, field `+0x88`).
  Four agreeing measurements: 8/8 `CollectGarbage` + 2/2 `TryCollectGarbage` sites `xor ecx,ecx`
  (tool control: the same tracer sees 12 distinct arg1 forms elsewhere, so it is not defaulting);
  zero stored pointers to either entry ⇒ no indirect caller; `0` in both cold images; and **[M] live
  `*(int32*)(base+0x9E25348) == 0`** with the control that 89/160 bytes of the surrounding state
  object are non-zero. Body B's inner test is `test [rax], ecx` with `[rax]==0` — dead either way.
- ★★★★★ **THE RECIPE (offline-derived + live-verified reads; NOT YET FLOWN). TWO LEVELS — do not
  conflate them:**
  **`UObject` level (use this):** `AddToRoot` **`.text +0x489F9B0`** · `RemoveFromRoot`
  **`+0x48B4BD0`** · `void __fastcall(UObject*)`.
  **`FUObjectItem` level (only if you hold the item):** `SetRootFlags` **`+0x129AC90`** ·
  `ClearRootFlags` **`+0x1243B50`** · `bool __fastcall(FUObjectItem*, uint32)`, flags in `edx`.
  All four **fold multiplicity 1**, byte-identical in both dump images; controlled against the
  91-way-folded `execFoo` thunk `0x5254180` which occurs **907×**.
  A **plain direct call** from an injected DLL — no `.text` write, no PI hook, no native-call
  primitive; it takes its own lock. No reflected route exists (18,325-function UHT scan: 1 hit, an
  unrelated `ALokiCharacter::IsRooted` movement effect).
- ⚠ **A fourth writer of the registry exists** — `0x0123E0E1`, opposite polarity, domain `[0,N)`
  including the pool — but it is the `'GC.OnDisregardForGCSetDisabled'` `ParallelFor` body and fires
  only when disregard-for-GC is DISABLED. This build has it enabled, so it has never run.
- ⚠⚠ **THE OLD POKE POISONS THE FIX.** `SetRootFlags` (`0x129AC90`) early-outs on
  `if (Flags & 0x4E100000) skip the insert`, so an object the shim already OR'd looks "already a
  root" and a subsequent CORRECT `AddToRoot` **silently does nothing**. ⇒ **`KGCROOT` now DEFAULTS
  TO 0** (S123). `play` `.text` moved `5151621d2154e454` → **`9bc10a4552c596e1`**; rollback is
  `build.ps1 -Variant play-gcroot`, **verified to reproduce `5151621d2154e454` exactly**, and the
  new default is byte-identical to the retired `play-nogcroot` control arm. Both directions measured.
- ★ **FREE RPM RECEIPT — use this, never `IsRooted`:**
  `*(int32*)(base+0x99D3CA8) - *(int32*)(base+0x99D3CD4)` (`ArrayNum - NumFreeIndices`) reads **32**
  and must move **+1 per rooted object**. `IsRooted` (`0x48B2200`) reads **only the flag**, so it
  returns true for exactly the failure being diagnosed.
- ★ **`KANIMREF` is RE-FRAMED, not replaced** — parking the asset in a real `UPROPERTY` is the *same*
  mechanism real roots use (be reachable by the traversal). It stays the default.
- ★ **FK-28's rotating bits 0/1/2 explained:** `.data 0x99D36A0/A4/A8` hold the
  Reachable/Unreachable/MaybeUnreachable **values**, rotated O(1) per pass (`0x01258F70` start,
  `0x012398C2`/`0x01239B76` end) — the population is not rewritten. Keep mask `0x4E100000` =
  `RootSet|AsyncLoading|Async|Native|LoaderImport`. Bit 24 `ClusterRoot` ⟺ `ClusterRootIndex < 0` at
  **100.000%** over 200,437 objects (0 FP, 0 FN) ⇒ stock `EInternalObjectFlags` numbering IS in
  force, which is what makes bit 30 = RootSet a measurement rather than a name-guess.
- **Readout: `tools/re/rootset_census.py`** (read-only RPM). ⚠ It had **10 defects**, found by
  adversarial review and fixed/annotated in-file. Two generalise:
  ★★ **recording a DERIVED BOOLEAN instead of the RAW FLAG WORD destroyed the evidence** — the
  tracker stored "carries the currently-dominant bit", and that comparator is a lagging majority vote
  whose polarity **inverts** during a mark ramp, so the same objects read 32/32 at a 0.4 s period and
  **0/32** at 0.5 s. **Record raw; derive afterwards.** And the first sample was counted as a
  rotation, inflating every run by one.
- ⛔ **DO NOT recycle two arguments that were REFUTED even though the conclusions held:**
  "zero free slots below the boundary, P≈1e-676" is **not** valid evidence (5,705 of 7,282 free slots
  are one contiguous run at the boundary, `[45000..169999]` also has zero holes and is not rooted,
  and "no holes below the first hole" is circular); and the 32/32-vs-40/40 marking statistic is void
  as stated. The boundary rests on `ObjFirstGCIndex` read directly plus the **20 live pool objects
  that lack bit 30 and are still never marked and never collected**.
- ⚠ **"Roots are marked first" is [I], n = 1 of 9 passes** (8 of 9 complete in under 0.4 s with no
  observable ramp). The one ramped pass gave roots 32/32 vs index-matched ordinary 17/32,
  Fisher p = 3.6e-6 — best available, still a single observation.
- ⚠⚠ **46th instrument-artifact instance, and it was mine — AND IT WILL RECUR ON ANY `TSet` IN THIS
  IMAGE.** I read the registry's `TSparseArray.ArrayNum` (**49,307**) as its member count, ignoring
  `NumFreeIndices` (49,275) **in the same hex dump**, derived three false conclusions, and challenged
  a correct offline result with them. `Num()` is `ArrayNum - NumFreeIndices` — the engine computes it
  at `0x011D44EE` (`sub edx,[rcx+0x34]`). **Two properties make the wrong read SELF-VALIDATING:** the
  inline `FF×16` bitmap is dead storage once `NumBits > 128` (`0x011D4533 cmove r10, rax`), so it
  reads "all allocated"; and a FREED slot passes every field-range check *by construction* (stale
  `Value`s are real former indices; the free-list link shares bytes with `HashNextId`). So "88% are
  live indices" and "every `HashIndex` < `HashSize`" both pass on garbage.
  **Always walk the allocation bitmap; never trust the slot array.**
- Open: **the recipe has not been flown.** Everything above is disassembly plus live-verified *reads*;
  the *call* is untested. One armed window with the +1 receipt settles it.

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

### Before touching anything queue- / FIND MATCH- / matchmaking-shaped
★★★★★ **FIND MATCH WORKS (S133, 2026-08-20) — read `docs/s133-joinqueue-find-match.md`.** The client
enters a real queued state with a running timer and a working cancel. Backend-only; no shim, no
injection, no `.text` write. `server/internal/interactive/joinqueue.go`, knob **`AGS_JOIN_QUEUE=0`**.
- **[M] TWO ENDPOINTS, BOTH PREVIOUSLY UNSERVED:** `POST /party/parties/{p}/joinQueue` (FIND MATCH)
  and `POST /party/parties/{p}/leaveQueue` (cancel — a correct speculative guess, confirmed on the
  wire). Both fell to the `/` catch-all, which is *why* FIND MATCH did nothing and why the client
  **re-POSTed every ~10–35 s**. ★ **The retry IS the rejection symptom** — once accepted, `joinQueue`
  fires exactly ONCE. Use that as a free receipt.
- ★★★★★ **THE RESPONSE MUST BE AN `FParty` UNDER AN ADVANCED `Version`.** Read from the function
  itself: `TryJoinQueue 0x5875E90` passes callback `0x5859E10`, whose third instruction is
  `call 0x587BE90` = **`UPartyModel::SetParty`** — the S85 monotonic-Version gate
  (`cmp [PartyModel+0x568]; jge bail`). So the handler echoes the party through `store.update()`
  exactly like `handleSetTargetQueues`.
- ★★ **THE FIELD IS `state`, NOT `inQueue`.** `EPartyState = { Default, `**`Matchmaking`**`,
  CustomGame, Unknown }` (usmap enum VALUE table — the trustworthy part, FK-14).
  ⚠⚠ **`inQueue: true` ALONE IS MEASURED INSUFFICIENT, and its null was only interpretable because
  the disjunction was pre-registered:** `SetParty` **ran** (party-slot widgets rebuilt —
  `LogBlueprintUserMessages: MENUSPAWNER … Entering SetHero` at the exact timestamp), `LogJson` at
  Verbose logged **ZERO** import failures, and the UI still did not move ⇒ **wrong FIELD, not a dead
  route.** Write that disjunction down BEFORE the flight or "nothing happened" means nothing.
- ★ **`QueueJoinTime` / `MillisInQueue` are NOT needed — the client times the queue LOCALLY.** They
  were deliberately withheld (unconfirmed UE types; a wrong-typed matched key sinks the whole document
  and would have made `state` untestable too). **The restraint cost nothing.**
- ⚠⚠ **THIS IS THE SECOND CORRECTION TO THE S122 UNSERVED-ROUTE SWEEP, SAME BLIND SPOT.**
  `setTargetQueues` was missed because nobody clicked a tile; `joinQueue` because nobody clicked FIND
  MATCH. ⇒ **A passive capture-diff enumerates what the client HAPPENED to exercise. Drive the
  interaction, THEN diff — do not just capture for longer.**
- ★★★★★ **S135 — THE QUEUE CAN NOW BE ANSWERED. `server/internal/interactive/armqueue.go`,
  knob `AGS_ARM_QUEUE=off|arm|empty` (default **off**, and off is byte-identical to pre-S135).**
  [M] The reason nothing could arm a `bots` match is structural, not a missing matchmaker:
  native `IsSpecialQueue` (`0x5854F5F`) puts `{practice,customgame,dropin,tutorialNew,training}`
  on the SOLO path (`POST /startSoloMode`, the ONLY writer of `SoloMode`) and
  `{default,deathmatch,bots,tournament,armorydeathmath}` on the QUEUE path (`POST /joinQueue`).
  `handleCoreGamePlayer` gated on `SoloMode != ""`, which a queued player can never set ⇒
  `MatchID` stayed `""` forever. The gate is now `SoloMode != "" || MatchID != ""`.
  ⚠⚠ **AND THE CLIENT DOES NOT POLL THAT ENDPOINT — `interactive.go`'s own comments claiming a
  ~1/min poll are REFUTED.** [M] `GET /core-game/players/{id}` is fetched **exactly ONCE per
  messenger connection**, within ~53–82 ms of connect (1:1 across 8 captures / 12 connections /
  12 fetches). In `capture-phase2.log` two `startSoloMode` calls land at 19:19:50/51 and the only
  players-fetch in the file is **23 minutes earlier, at login** — so even the SOLO path only ever
  worked because the write preceded the connection that read it. ⇒ **a MatchID written after login
  must be PUSHED** (`lobby.NotifyResource`, wired via `SetResourceNotifier`); `UCoreGameManager`'s
  init `0x57BD610` registers `/core-game/players/` as a messenger resource prefix.
  ★★★★★ **FLOWN AND CONFIRMED END TO END (2026-08-21). THE `bots` QUEUE PRODUCES A MATCH, AND
  `UTravelManager` FIRES. First time in this project's history that the MATCHMAKING path has armed
  anything.** Live client, **no relaunch, no injection, no `.text` write** — one `ags` restart with
  `AGS_ARM_QUEUE=arm`, then one FIND MATCH click. All seven pre-registered predictions hit:
      `00:45:25  POST .../joinQueue -> 200`                    (ONCE -- the retry-is-rejection receipt)
      `00:45:25  armqueue: will arm queue="bots" in 8s`
      `00:45:33  armqueue: ARMED matchID="match-9b9d..." version=1787291133`
      `00:45:33  armqueue: pushed /core-game/players/... version=1787291133`
      `00:45:33  WS NOTIFY[armqueue] -> {"Resource":"/core-game/players/...","Version":1787291133}`
      `          GET /core-game/players/9b9d...`   <- #3031  THE CLIENT REFETCHED
      `          GET /core-game/matches/match-9b9d...` <- #3033  AND ESCALATED
      `[05.45.33:416] LogTravelManager: Attempting to travel to Match: ID:"match-9b9d..." Address:""`
  ★★★★★ **[S] → [M]: `NotifyResource` DOES drive `/core-game/players/`.** Nobody had ever pushed this
  resource; the refetch was only [I, strong] by analogy with `/match-history/`. **Measured: fetches
  went 1 → 2 — EXACTLY ONE refetch**, which is the discriminating count. Zero would mean a dead push;
  an unbounded stream would mean the too-high-Version loop `push.go` warns about.
  ★★★★★ **AND THE SECOND [S] IS SETTLED TOO: the client ACCEPTS a positive push from a `Version: 0`
  baseline.** We serve `Version: 0` while idle, and whether the client caches 0 and adopts any
  positive push, or ignores the resource until it has a non-zero baseline, was untested and was the
  most likely cause of a false null. It adopted `1787291133` from a 0 baseline.
  ★ **The client's OWN log is the attribution** — `LogTravelManager` is in `Loki.log`, so the
  User-Agent trap (which has fired twice in this project) cannot apply. Canaries **0** `Fatal` /
  **0** `Deserialization failure` / **0** `Unable to import` / **0** `Invalid response received`;
  both processes alive afterwards.
  ⚠ **`Address:""` IS CORRECT, NOT A FAILURE.** The client parks locally rather than opening a
  NetConnection (S62), which is the precondition the force-open route needs. **No map loads from
  this** — the world still comes from `docs/tutorial-launch-cmd.txt`. ⇒ what is now proven is the
  MATCH-ARMING half; the WORLD half is still the force-open shim.
  ⚠ The evidence log is `docs/ags-armqueue-s135.out.log` (+ `.err.log`); `docs/capture.log` was
  backed up to `docs/capture.log.pre-armqueue-s135` (226 MB) BEFORE the restart, per the documented
  truncation hazard.
  ★ **`AGS_ARM_QUEUE=empty` IS THE CONTROLLED NEGATIVE** — a valid document with an ADVANCING
  Version and an EMPTY MatchID, i.e. it moves exactly ONE field vs `arm`. Reverting to `off`
  changes document and version together and is uninterpretable (the S122 `AGS_PLAYER_RANK=0`
  lesson). `armqueue_test.go` pins this and **was verified to FAIL when the invariant is broken**.
  ⚠ `AGS_ARM_QUEUE_QUEUES` defaults to **`bots` alone** so the knob cannot silently arm BREACH.
  ⚠⚠ **`GameConfig.MapName`/`GameMode` CANNOT SELECT THE CLIENT'S WORLD** [M] — the travel URL is
  built from `ConnectionDetails.Address` alone and the only `?game=` literal in the image belongs
  to MovieRenderPipeline. With an EMPTY address the client PARKS LOCALLY (S62) and the world comes
  from the force-open shim reading `docs/tutorial-launch-cmd.txt`. Those two fields are
  documentation of intent; **do not try to reach a different level by editing them.**
- ⚠⚠ **`bots` IS BREACH** [M]: `BP_LokiBattleRoyaleGameMode_Skylands_Bots_C` inherits
  `..._Skylands_Breach_C` and adds exactly ONE CDO property, `bUseObviousBotNames=true`. So making
  CO-OP VS. AI playable *through its own gamemode* is making BREACH playable — a 2,215-cell map
  never once loaded. ⇒ **the cheap route is not the queue's gamemode.** `Comp_BP_BotSpawner_C` is
  an SCS component on **`BP_LokiGameMode_Tutorial`** (`BP_LokiGameMode_Tutorial_C:Comp_BP_BotSpawner_GEN_VARIABLE`),
  i.e. resident on the world we already stage every session, and [M] it has **0** occurrences of
  `ServerOnly`/`ClientServerSplit`/`HasAuthority`/`SpawnPlayer` across its full dump AND its
  ubergraph, against a positive control of **8** in `BP_LokiGameMode_Tutorial`'s ubergraph ⇒ **the
  bot spawner is free of BOTH the FK-42 exec-pin gates and FK-1's stripped `SpawnPlayer`.**
  `SpawnClassBotAtLoc` is `Public|HasOutParms|HasDefaults|BlueprintCallable|BlueprintEvent` — no
  `FUNC_Net`, no `FUNC_BlueprintAuthorityOnly`. Roster at `[BotSpawner+0xD8]`, [M] from two disjoint
  functions: `GetSpawnableBots 0xFCCE40` = `48 8d 81 d8 00 00 00 c3` and `SetSpawnableBots
  0x52EC260` = `48 81 c1 d8 00 00 00 e9`. ~~`SpawnBot 0x556D910` is **DARK, not stripped**~~ ⚠ **STALE since `merged12` -- it is LIT (page
  `0x556D000` = 3,720/4,096) and S137 transcribed it in full (1,544 B, REAL, 43 call instructions =
  39 direct + 4 indirect, 28 distinct direct targets, 25 REAL / 2 FOLD / 1 DARK).** The line
  contradicted this file's own S135 and S137 blocks for two sessions. Full plan + traps: **`docs/coop-vs-ai-plan-s135.md`**.
  ★★★★★ **THE ARM IS BUILT (S135): `build.ps1 -Name tutorial_launch -Variant botspawn`.**
  `RM_BOTSPAWN` (enum 31) makes ONE `CallBPGuarded` into `Comp_BP_BotSpawner_C::SpawnClassBotAtLoc`
  on the live tutorial GameMode's own bot spawner. **Risk class: CALL-ONLY — no module-image write,
  no data poke, no PI hook**; it REFUSES to run under `KFUNCSWAP=0` (whose delivery path is the
  standing `.text` patch measured 10/10 lethal). `verify_dll.py` VERDICT **PASS**; imports
  `KERNEL32.dll` only, with `FlushInstructionCache`/`VirtualAlloc`/`WriteProcessMemory` **absent**.
  ⚠ `VirtualProtect` is still imported (other modes in the same TU use it), so the S112
  import-absence signature is SUGGESTIVE here, not a proof — the no-write property rests on the
  source path and the `KFUNCSWAP=0` refusal.
  `.text`: **`botspawn ae89d06b91164e5f`** · **`botspawn-readonly f5f9896feeac45dc`** (the read-only
  control clears the CALL bit, `KBSARMS=0x0B`; **the two are genuinely different builds — verified,
  because an A/B against a copy of itself has burned a live run in this project before**).
  Knobs: `-DKBSTEAM` (default −1 = auto, opposite the player's team) · `-DKBSHERO` · `-DKBSDIFF` ·
  `-DKBSLEVEL` · `-DKBSOFFSET` · `-DKBSARMS`.
  **Staging: `gft` → `fo` → `sp` → this. NO pod and NO plane are needed — this is not the drop chain.**
  ⚠⚠ **PRE-REGISTERED, AND IT IS THE WHOLE REASON THE ARM HAS TWO READOUTS: a NULL `CreatedBot` DOES
  NOT MEAN THE SPAWN FAILED.** From the bytecode: `SpawnBot`'s return is assigned to a local that is
  **never read again**, and `CreatedBot` is instead filled by a `GetPlayerStatesOnTeam` scan requiring
  `IsBotControlled ∧ ObjectIsA(HeroClassToSpawn)` **at that instant** — which a fully successful spawn
  also fails if the bot's PlayerState has not joined the team array yet, and which returns a
  PRE-EXISTING bot if one is already on that team. ⇒ **the verdict is the `GUObjectArray` CENSUS
  DELTA** (BotController-chain and LokiHeroCharacter-chain, counted by CLASS CHAIN and excluding CDOs
  and `_GEN_VARIABLE` archetypes), not the out-param.
  ★ **The baseline is a STRUCTURAL ZERO** — `SpawnBots`/`MakeNewBotController`/`TrySpawnTeam`/
  `SpawnBot`/`BotSpawner`/`AIController`/`SetSpawnableBots` occur in **0 of 1,126 log files**, against
  passing positive controls in the same sweep (`LogNavigation` 284, `BotNavLink` 174, `Recast` 191)
  ⇒ nothing measured after the call can be background activity. The arm also runs a **stability
  re-census with no call in between** and declares the sitting VOID if it moves.
  ⚠ `BotLevel` is a MEASURED NO-OP (`SetBotToLevelX` → `AuthGrantLevel`, impl `0x0F7EC20`, the void
  fold). ⛔ Do NOT use `"Spawn AI Hero Bot"` as the first arm — its location comes from a
  `BotSpawnStart`-tagged beacon and **`LVL_Tutorial` has ZERO of those** across the persistent level
  and all 67 WP cells, so the bot would spawn at world origin.
  ⚠ **"bots spawn" (S65/S66) is REFUTED** — `DumpPawns` counted *components*, and `asc_census`
  measured pawn-like = 2, both spectators, in the same world state. **No bot has ever spawned here.**
  ★ Navmesh is NOT a blocker: it builds in **191 of 202** `LVL_Tutorial` loads ~2 s after map load —
  which corrects this file's own earlier "~49 s after Combat" framing.
  ⚠ **CO-OP VS. AI is ALREADY selectable and FIND MATCH already works on it — zero backend or
  config changes are needed for ACCESSIBILITY.** ⚠ And **serving `queue.restrictions.bots` would be
  a REGRESSION**, moving it off its unconditional-TRUE arm onto an `AccountLevel` check we have
  never served. Keep `AGS_QUEUE_UNLOCK` empty for `bots`.
- ★★★★★ **S135 FLEW IT: BOT PAWNS SPAWN, AND THE ONE REMAINING GAP IS THE AI CONTROLLER. Read
  `docs/next-session-prompt-s136.md` (the flight procedure), then `docs/s135-queue-arms-a-match.md`
  (five addenda = the evidence).**
  **[M] What works:** `SpawnClassBotAtLoc` → **+1 hero at the exact passed location**;
  `SpawnBotTeamAtLoc` → **+3 heroes of 3 GAME-CHOSEN classes** (Sniper/Void/Storm) with
  `CreatedBotTeam.Num=3` — three agreeing readouts (out-param, in-shim census, `obj_by_class`), from a
  verified-stable A0==A1 baseline. Roster `SpawnableBots@+0xD8` reads **Num=13 Max=16** live, so
  `Initialize Bot Options` runs unconditionally on a non-BR gamemode.
  ★ **A staged tutorial world is now reachable with `forceTutorialMatch = FALSE`** — the queue-armed
  MatchID satisfies `fk24-stage.ps1:199`. The documented "set the flag and relaunch" step is obsolete.
  ⚠⚠ **BUT NO CONTROLLER IS EVER CREATED [M]** (two independent instruments: an in-shim class-CHAIN
  census and `obj_by_class` leaf-name, both **0** for `BotController` AND `AIController` over 192,337
  objects). **The cause is read end to end from the binary:**
      `SpawnBot 0x556D910` → `0x556DB23 call MakeNewBotController 0x5563660`
          → `0x55636BB call 0x0F7EB50` **STRIPPED → nullptr** → `0x55636C8 je` → EXIT
      → controller NULL → `0x556DD34 test rcx,rcx / je` → **`AController::Possess 0x36E2B60` (REAL) SKIPPED**
      → no PlayerState → `0x556DD73 je` skips `ServerSetHeroClass` + `SetPlayerTeam`
  **[I, strong] that stripped `F(UWorld*)→nullptr` is a FOURTH consumer of FK-22's "ONE GETTER, THREE
  CONSUMERS"** — so the drop-pod rider handoff and the AI bot are the SAME blocker. ⚠ NOT [M]: the
  fold has ~27,217 call sites and names nothing alone.
  ★★★★★ **THE GAME SHIPS ITS OWN BYPASS, AND THE BLUEPRINT LAYER HIDES IT [M]:**
      `SpawnBot(HeroClass, Location, TeamIndex, Difficulty=4, **AController PremadeBotController = nullptr**, BotName="")`
  `[rsp+0x70]` is written in exactly TWO places (`0x556D957` from that parameter, `0x556DB28` from
  `MakeNewBotController`) and read ONCE — at the `Possess` guard. A non-null premade controller
  **skips the stripped path and lands in the slot `Possess` reads.** ⇒ **the BP route can never work:
  `SpawnClassBotAtLoc` hardcodes `EX_NoObject` there.** `SpawnBot` is itself reflected, so the S55
  direct thunk reaches it with our own controller. ★ Found by READING THE DECLARATION
  (`binds_members.csv`), not by disassembly — method rule #2 applies to a UHT signature table too.
  **Arms** (⚠ `botspawn`/`botteam` share a `.text` SIZE of 182,272 — **diff the HASH**):
  `botai c55cb560cc602e31` (built, UNFLOWN — `SpawnAIFromClass 0x4631C50`, REAL, 2,133 B, **0 fold
  calls**, native+STATIC ⇒ `CallNativeGuarded` with context = the CDO) · `botspawn e48c90bc6cf17c93` ·
  `botteam 0c16652dc0338d33`. All CALL-ONLY: no module-image write, no data poke, refuse under
  `KFUNCSWAP=0`. ⚠⚠ **Those digests come from an INLINE hasher and do NOT reproduce the repo's
  recorded gates** — `build.ps1` emits no digest and `verify_dll.py` prints no section hash, so there
  is no canonical recipe on disk. **The only sound check is a BEFORE/AFTER differential inside ONE
  method** (S135 did that: `play`/`dismount` identical from HEAD-source and edited-source builds).
  **Writing the canonical digest recipe into a script is an open task.**
  ⚠ **DO NOT fly a `PremadeBotController` arm before `botai` succeeds** — the component has no
  controller-class property, so without a known-good controller source a null cannot separate "the
  bypass fails" from "we passed a bad controller".
  ⚠ **`MakeNewBotController`'s census row (`IMPL-PAGE-DARK`) is STALE** — our own flight decrypted it,
  along with `SpawnBot` and `FindValidPositionForCharacter`; all three are in **`dumps/merged11.dump.exe`**.
  ⚠ **Grade three-state: fold / REAL / DARK.** A two-state "is it a fold?" test printed a false
  "REAL CODE" for the all-zero `APawn::SpawnDefaultController 0x3BBF3C0`. DARK is neither stripped nor
  confirmed real. `AController::Possess 0x36E2B60` IS real (vtable slot 267 via `vtables.py name`).
  ⚠⚠ **Never sample a byte offset across unrelated vtables** (`+0x858` is a different method in every
  hierarchy), and remember **`.rdata` in a dumped image holds ABSOLUTE VAs, not RVAs** — forgetting
  `ImageBase` found "2 vtable candidates" in a 170 MB UE image; the real count is 7,830.
  ⚠⚠ **WAIT FOR `[BS] done` BEFORE READING THE MARKER.** S135 read it mid-run and manufactured a
  "game-thread starvation" diagnosis that an adversarial lane refuted from the same file. The
  discriminator is **`allThreadCalls`**, not `hitsGT`: `allThreadCalls>0 && called<allThreadCalls`
  means *we are inside our own step* — the OPPOSITE of starvation.
- ★★★★★ **S136 (2026-08-21) — AN AI-CONTROLLED HERO PAWN EXISTS. Read
  `docs/s136-ai-controller-settled.md`.** `UAIBlueprintHelperLibrary::SpawnAIFromClass` (`0x4631C50`)
  spawns the pawn and then tail-calls **`APawn::SpawnDefaultController` (vtable slot 280 =
  `0x3BBF3C0`)**, which constructs a controller and possesses it — bypassing
  `MakeNewBotController`'s stripped getter entirely. Reproduced 2× in ONE client, no relaunch,
  CALL-ONLY, 0 `Fatal`, 0 crashpad. Flight 3 hit **7/7 pre-registered predictions**, `dCtl=+1`.
  ⚠⚠⚠ **IT IS NOT A BOT, AND DO NOT WRITE THAT IT IS.** [M] `APawn::AIControllerClass @+0x3D0`
  reads the **engine default `AIController`** on the spawned pawns **and on the PLAYER hero too**;
  [M] `obj_by_chain BotController` = **0 LIVE** (the CDO is present as a passing search-term
  control). `MakeNewBotController → BotController → ServerSetHeroClass / SetPlayerTeam` is
  **UNTOUCHED and still blocked on FK-22's stripped getter.** Say *an AI-controlled hero pawn via
  the engine's default `AAIController`, with PlayerState / Brain / Blackboard / Perception all
  NULL* — never *"the bot spawner works"*.
  ⚠⚠⚠ **SUPERSEDED BY S137 ON BOTH HALVES — READ `docs/s137-playerstate-and-lokibot-settled.md`.**
  The AI pawn now HAS a real `BP_LokiPlayerState_C` on **both** sides (controller `+0x3C0` and pawn
  `+0x3D8`, equal), and **an `ALokiBotController` has been created and possesses a hero pawn** —
  the first `BotController`-derived object in this project's history, A-B-A'd and confirmed by two
  independently written instruments. See the S137 block below.
  ⚠⚠ **AND THE `obj_by_chain BotController` CITATION IS A DEGENERATE QUERY.** [M, S137] **no class
  in this hierarchy is NAMED `BotController`** — the Loki class is `ALokiBotController` (UHT-strips
  to `LokiBotController`) and its ancestors are `LokiAIController` / `AIController` / `Controller`.
  Run live **with a `LokiBotController` possessing a pawn in that very process**, `=BotController`
  returns **`found 0`** AND **`CDOs matched and EXCLUDED: 0`** — i.e. **it has no positive control
  either**; `=LokiBotController` returns `found 1`. The `'='` exact form that `obj_by_chain.py`'s
  own header tells you to PREFER is the WRONG instrument for this question. The S136 conclusion was
  right (no bot controller existed then), but its stated control cannot have passed in that form.
  **Use `=LokiBotController`, or the substring form.**
  **[M] The possession handshake is bidirectional:** controller `Pawn`/`Character`/`Instigator` ==
  the exact pointer `SpawnAIFromClass` returned; pawn `Controller`/`PreviousController`/`Owner` ==
  that controller. ★ **Positive control:** the player hero, possessed by a real
  `BP_LokiPlayerController_Dev_C`, shows the IDENTICAL triple ⇒ both sides of the offset set are
  validated on a known-good possession in this build.
  ★★★★★ **THE CONTROLLER WAS CREATED *AFTER* THE PAWN — [M], THREE WAYS, ALL FROM A POST-HOC
  SNAPSHOT.** (1) **`FName.Number` (obj+0x24) is a strictly-DECREASING runtime spawn counter** —
  6/6 monotone over known-order objects, AIC#1 `2147470967` < botpawn#1 `2147471035`, with a
  PRE-REGISTERED prediction on botpawn#2 that hit. (2) `AIC+0x198 Instigator = the pawn`, written
  only by `SpawnActor` from `FActorSpawnParameters` — `Possess`/`SetPawn` never write it, so a
  controller predating the pawn cannot carry it. (3) the call site `0x4631DD2 cmp [rax+0x400],rbx`
  / `0x4631DE1 call [rax+0x8c0]` is **guarded on `Controller == NULL`**, and `SpawnDefaultController`
  early-outs on the same test ⇒ a pre-existing controller is unreachable by this path.
  ★★ **`FName.Number` IS A FREE CREATION-ORDER ORACLE AND THE REPO'S TOOLS THROW IT AWAY** —
  `obj_by_chain.objname()` reads only the 4-byte ComparisonIndex and discards the Number, printing
  `AIController` for `AIController_2147470966`. **Read obj+0x24.**
  ⚠⚠ **`InternalIndex` IS NOT MONOTONE — REFUTED FROM INSIDE THIS CORPUS.** AIC#2 was created
  LATER (measured) and has index **172033 < 177838**. `GUObjectArray` reuses freed slots (S110).
  **Never use index adjacency for creation order.**
  ★★★★★ **P4: `APawn::SpawnDefaultController 0x3BBF3C0` DARK → DECRYPTED.** Page census, not a
  byte peek: `merged11` page `0x3BBF000` = **0/4096** non-zero, S136 image = **3714/4096** —
  **reproduced by two verifiers with independently written code**. Four controls (`Possess`,
  `SpawnAIFromClass`, both folds) lit in both. **[M] novelty: 53 of 55 images dark, INCLUDING
  `dumps/s135-botspawn`** ⇒ S135 spawned pawns and never reached this function.
  ⚠ **GRADE SPLIT:** bytes alone give **[I]** for *"it executed"* (4 KiB page granularity; the fn
  starts `0x3C0` into its page). **[M, strong]** only WITH the `call [rax+0x8c0]` call-site
  disassembly plus the live possessed pawn. **Cite both.**
  ⛔ **Do NOT quote `merged12`'s "51.85 % non-zero" beside a page delta** — wrong instrument; cite
  **`.text` 16,772 / 30,281 = 55.39 % PAGES**. ⛔ Do not carry `fn 0x3BBDFA0` (a `pdata_union`
  artifact, blind by construction on dark pages); the true start is `0x3BBF3C0`.
  ⚠ `SpawnBot 0x556D910` / `MakeNewBotController 0x5563660` read non-zero in `merged11` and zero in
  the fresh S136 image — correct union semantics (lit in exactly the 3 images containing
  `s135-botspawn`), NOT a bad read.
  ⚠⚠⚠ **THE SHIPPED `botai` ARM WAS STATICALLY INCAPABLE OF CALLING.** `BsResolve` does
  `#if KBSAI { BsResolveAI(hero); return; }`; `BsResolveAI` stores into `g_bsAiFn` and NEVER
  `g_bsFn`, so every `g_bsFn`/`g_bsComp` store sits **after an unconditional `return;`** (⚠ NOT
  removed by the preprocessor — that phrasing misleads). clang `-O2` folds the dispatch guard to
  constant TRUE and **dead-code-eliminates `BsCallAI()`**. [M] the 53-byte banner `THE CALL:
  UAIBlueprintHelperLibrary::SpawnAIFromClass` had **0** byte occurrences, with a **positive
  control** (a build with only the gate fix) returning 1.
  ⚠⚠ **THE MECHANISM IS NON-UNIQUE — EITHER guard term alone folds constant-true.** Build
  bisection: removing only `!g_bsFn`, or only `!LooksLikePtr(g_bsComp)`, left the branch dead both
  ways. Do not "fix" this by deleting one term.
  ★★ **[M] S135's recorded `botai c55cb560cc602e31` is `.text`-identical to that dead arm** ⇒ S135
  built, digested, documented and handed off as flight-ready **an arm containing no call site.**
  ⚠ Downgrades inside that finding: *"the KBSARMS-disabled banner did not print"* is **[S], NOT
  runtime evidence** — with `KBSARMS=0x0F` the test `if(!(0x0F&0x4))` is constant-folded, so the
  string is absent BY CONSTRUCTION (an instrument artifact committed while writing about them);
  *"+3072 proves `BsCallAI` was emitted"* is **[I], contaminated** (single-variable cost is
  **+2,560**); and **byte-absence is NOT a general string test** — `"SpawnAIFromClass"` is
  materialised as split, out-of-order `movabs` immediates. It is valid only for LONG strings
  passed as pointers to a non-inlined call. The flight-1 marker (`resolved=1 called=0`) is
  **NON-DISCRIMINATING** on its own.
  ⚠⚠ **AND THE CENSUS PREDICATE WAS BLIND TO EXACTLY THIS CONTROLLER.** `BsClassify` tested only
  `PhChainHas(cls,"BotController")`; the created object's chain is `AIController <- Controller <-
  LokiActor <- Actor <- Object`. Flight 2's `dCtl=0` was **UNINTERPRETABLE, not a null**. ★ Settled
  S135's own deferred blind spot: same world, same object, only the predicate changed ⇒ **0 vs 1**.
  Fixed to `BotController` OR `AIController` (deliberately narrow — a bare `"Controller"` also
  matches ~190 `Comp_PlayerController_*_C`). **The stale VERDICT string is fixed too**: it said
  *"A BOT SPAWNED / BotController +N / from a STRUCTURAL ZERO baseline"* while A0 read **1**.
  ⛔ **Refuted supports — do NOT repeat them:** `Z = 90.15` as a payload fingerprint (floor
  flatness; S132's number is at a different XY — the strong form is **bot2 resting ON bot1,
  ΔZ = 176.1008 = 2 × 88.0504 capsule half-heights**) · `Outer = PersistentLevel` (98.8 % of live
  actors) · "exactly 1 AIController" (**[M] at time T only** — it read 2 minutes later because a
  third arm flew; **TIMESTAMP every census**).
  ★★★ **FREE COROLLARY, NOW VERIFIED FROM THE BYTES (S136) — UE ITSELF DOES NOT THINK THIS CLIENT
  IS `NM_Client`.** `APawn::SpawnDefaultController` has exactly three early-outs before it spawns:
      `0x3BBF3DD cmp qword [rcx+0x400],0 / jne` → bail if `Controller != NULL`
      `0x3BBF3EE call <GetNetMode>` · **`0x3BBF3F3 cmp eax,3 / je`** → bail if **`NM_Client`**
      `0x3BBF404 mov rdi,[rbx+0x3d0] / test / je` → bail if `AIControllerClass == NULL`
  **[M] a controller WAS created ⇒ all three were passed ⇒ `GetNetMode() != 3`.**
  ★★ **THIS IS NOT THE SAME FACT AS `LokiIsServer` BEING HARDCODED FALSE, AND THE DIFFERENCE IS
  LOAD-BEARING.** `LokiIsClient`/`LokiIsServer` (`0x0B9E1F0` = `mov al,1; ret`, `0x0F7EB60` =
  `xor al,al; ret`) are **Loki's own stripped helpers**; `GetNetMode()` is **the engine's real
  netmode**, and it is measured NOT-client. ⇒ the FK-1 / FK-22 / FK-42 walls are *Loki's* authority
  stubs, **not** UE refusing authority to a client.
  ★★★★★ **ANSWERED (S137, 2026-08-21): IT IS `NM_Standalone`, AND IT HAS BEEN IN EVERY LOG THIS
  PROJECT EVER TOOK.** The old text here read *"WHICH mode it is (Standalone 0 / ListenServer 2) is
  NOT [measured] — nobody has read the return value. One read settles it."* The read is one grep:
      `LogWorldPartition: UWorldPartition::Initialize Context : World NetMode = Standalone,`
      `    IsServer = 0, IsDedicatedServer = 0, ...`
  It is the CLIENT WRITING ABOUT ITSELF (so the User-Agent attribution trap cannot apply), and the
  same line is in `docs/Loki-s124-phaseladder-SUCCESS.log`, `Loki-s125-b1only.log` and
  `Loki-s127-routeE.log`. **A textbook method-rule-#2 instance — the answer was in the shipped
  artifact for ~13 sessions.** Corroborated from the BYTES independently: `AActor::GetNetMode`
  (`0x338E750`) defaults to `xor eax,eax` = **0 = NM_Standalone** when there is no NetDriver.
  ⇒ [M] `AActor::AActor` writes `ROLE_Authority(3)` to `+0x160` (`0x338E38B c6 83 60 01 00 00 03`),
  and the live tutorial client prints `PlayerState Role@0x160=3` and `hero Role@0x160=3`
  ⇒ **engine-level `HasAuthority()` PASSES on this client.** `IsServer = 0` is CONSISTENT, not
  contradictory: stock `UWorldPartition::IsServer()` is true only for Dedicated/ListenServer.
  ⚠⚠ **DO NOT OVER-READ IT. This moves NO existing wall.** FK-1's four empty impls and the
  `ULokiBlueprintLibrary` exec-pin gates (`0x1311870 = C6 02 00 C3`) never consult UE's netmode at
  all. What it settles is the FRAMING that was already recorded as [I] above — the walls are *Loki's
  own authority stubs*, not UE refusing authority to a client — and it now rests on a measurement.
  ★★★★★ **AND S136 THEN SETTLED THE NEXT BLOCKER OFFLINE — IT IS **ONE CDO BIT**, NOT A STRIPPED
  STUB.** Read `docs/s136-ai-controller-settled.md` §7.
  **[M] `AController::InitPlayerState = 0x36DEE20`, `AController` vtable slot 273, REAL, 778 B, all
  14 callees REAL, ZERO folds.** Triple-confirmed by three parties via three routes: **it names
  itself** (`.rdata 0x8018A50` = *"AController::InitPlayerState: the PlayerStateClass of game mode
  %s is null…"*, record `0x8018A30` → `Controller.cpp:0x268`, **exactly one** LEA site at
  `0x36DEF82`); it reads `UWorld::AuthorityGameMode` at FK-22's `+0x250` and `PlayerStateClass` at
  **`AGameModeBase+0x3E0`**; it calls `UWorld::SpawnActor 0x39C5280`; and it **writes
  `[controller+0x3C0]`** — the only slot of 400 storing there via a non-frame base register.
  **[M] THE BLOCKER IS `bWantsPlayerState`:**
      `AAIController::PostInitializeComponents 0x45D6D10` (REAL)
        `0x45D6D1E  f6 83 88 04 00 00 20   test byte [rbx+0x488],0x20`   ← bWantsPlayerState
        `0x45D6D25  74 25                  je  0x45D6D4C`                ← **THE BLOCKER**
        `0x45D6D46  call qword [rax+0x888]`                              ← InitPlayerState (slot 273)
  The bit is `0x20` at `+0x488`, from its OWN UHT `SetBitFunc` **`0x45CFA10 = 83 89 88 04 00 00 20
  c3`** (`or dword [rcx+0x488],0x20; ret`), with the adjacent bit `0x45CFA20` writing `0x40` at the
  same offset as a PASSING CONTROL. ★ That is the correct instrument — `FBoolPropertyParams` carries
  no `ByteOffset`/`ByteMask` (S132's recorded trap). **It is explicitly CLEARED in the ctors:**
  `AAIController 0x45D19AD and ecx,~0x20` · `ALokiBotController 0x554B5A9 and dword [rdi+0x488],
  ~0x20` · `ALokiAIController` never touches it. ⇒ **NO STRIPPED STUB. The PlayerState is NULL
  because STOCK UE defaults `bWantsPlayerState = false` on AI controllers.**
  ★★ **THE ARM: poke `CDO(<pawn's AIControllerClass>) + 0x488 |= 0x20` before spawning, then run
  `botai` unchanged.** Ordering is why it works: `SpawnActor` runs `PostInitializeComponents`
  (→ `InitPlayerState`) **before** `SpawnDefaultController` calls `Possess`, and
  `APawn::SetPlayerState 0x3BBD9F0` (REAL) then copies `controller+0x3C0` → `pawn+0x3D8`.
  Risk class = **one aligned CDO write, readback-verifiable, class-default scope** — identical to
  S130's `bCanEverReplicate`. ⚠ It is a CLASS DEFAULT. ⚠⚠ **Read `pawn CDO + 0x3D0` LIVE first** to
  learn which controller CDO to poke: `APawn::APawn 0x3B809D0` zeroes `+0x3D0` then re-reads it
  **from the `APawn` CDO chain** (`0x3B80C0D` → `0x3BA4CE0` → `[rax+0x178]` → `[+0x3D0]`), **not**
  a hard-coded `AAIController::StaticClass()`.
  ⚠ **Alternative with no CDO write:** call `0x36DEE20` directly on `pawn->Controller` (`pawn+0x400`)
  as `void __fastcall(AController*)`. **NOT "CALL-ONLY"** — it does a `SpawnActor` (`RF_Transient`)
  and writes `controller+0x3C0`.
  ⚠⚠ **A SECOND WALL SITS PAST IT AND BOTH ARE REAL AND SEQUENTIAL.** Everything the PlayerState
  gate protects in `SpawnBot` is a `"bot%d"` name, one real virtual, and **two stripped folds**
  (`0x556DE43 → 0x0F7EC20` void, `0x556DE53 → 0x0F7EB60` false); the reflection table independently
  shows `ServerSetHeroClass` (thunk `0x5438720`) and `SetPlayerTeam` (thunk `0x538AA70`) stripped,
  with matching arg shapes. ⚠ **[I, strong] on the NAMING, [M] that both sites are folds** —
  `0x0F7EC20` has 165,789 stored-pointer occurrences, `0x0F7EB60` 106,924; a folded RVA names
  nothing. ⇒ **a PlayerState buys REACHABILITY of that branch, not hero-class or team assignment**
  (the pawn already spawns with the right hero class, S135; what is missing is the PlayerState-side
  record that `CreatedBot`'s `GetPlayerStatesOnTeam` scan reads).
  ⛔ **THERE IS NO "THIRD GATE" — refuted in review; do NOT pre-register one and do NOT zero
  `[PS+0x8C8]`.** `+0x8C0` is `ALokiPlayerState::PlatformPlayerID` (UHT rec `0x8A252D8`;
  `binds_members.csv:44578`), **not** the PlayerName — that is `APlayerState::PlayerNamePrivate
  @ +0x450`, which is where `InitPlayerState`'s tail writes (slot 257 `0x3CA9D10`, not overridden,
  ends `lea rcx,[rbx+0x450]`). So `[PS+0x8C8]` stays 0, the `jg` falls through, **the block RUNS**.
  ★ The lane inferred the field from the write it saw instead of from the property table it already
  had open; the correction is FAVOURABLE, which is why it had to be made rather than dropped.
  ⚠ **[M] measurement / [I] label:** `ALokiPlayerController`'s slot 273 IS the void fold while all
  five other controller classes carry the real `0x36DEE20`. But calling it "a new FK-1-family
  strip" is [I] — empty virtuals are ORDINARY here (`AController`'s own vtable: **62 of 289** fold
  slots — ⚠ **QUOTE THE FOLD SET WITH THAT NUMBER**: the per-fold breakdown is void `0xF7EC20`=42,
  false `0xF7EB60`=17, true `0xB9E1F0`=7, null `0xF7EB50`=3, 0.0f `0xFC6CF0`=0, so it is **62 under
  the FOUR-fold set and 69 under the FIVE-fold set**. S137 saw a lane report the 69 as a
  "discrepancy with the digest"; it is not one, and one line of arithmetic dissolves it),
  and `InitPlayerState` is **not reflected at all** (image-wide name census ascii 0 / wide 0
  against five passing positive controls), so FK-1's instrument cannot grade it. ★ The AI-controller
  chain keeps the real engine impl — that is the half that matters.
  ⚠⚠ **STALE-DOC FIX: `APawn::SpawnDefaultController 0x3BBF3C0` has NO `.pdata` row**, which is
  exactly why a pdata-based grader reports a wrong entry point for it (`pdataunion.py` drops size-1
  placeholders BY CONSTRUCTION). Reproduced live: `strxref.py func 0x3BBF3C0` answers
  `entry 0x3BBDFA0`. **[M] it is pawn vtable slot 280 in `APawn`/`ACharacter`/`ALokiCharacter`/
  `ALokiHeroCharacter` alike — none overrides it.**
  ⚠ **`.rdata` class literals are UHT PREFIX-STRIPPED** — the bytes at `0x899A832` / `0x8A2430A` /
  `0x81B4B9A` are `LokiHeroCharacter` / `LokiPlayerState` / `PlayerState`, NOT the `A`-prefixed
  forms. FK-13 already records this trap producing false ABSENTs.
  Arm: `botai` **`5e47c13cf7f0a158`** (raw recipe; guard + census + verdict fixed).
- ★★★★★ **S137 (2026-08-21) — THE AI PAWN HAS A PLAYERSTATE, AND A **LOKI BOT CONTROLLER** EXISTS.
  Read `docs/s137-playerstate-and-lokibot-settled.md`; its CORRECTIONS block governs.** Three
  injections into ONE client, one staged world, no relaunch. Zero `.text` writes, zero PI hooks.
  ⚠⚠ **THE S137 HANDOFF'S OWN PROPOSED FIX IS REFUTED. Do not re-fly it.** *"poke
  `CDO(AIControllerClass)+0x488 |= 0x20` before spawning … the same risk class as S130's
  `bCanEverReplicate`"* — **[M] the poke lands (readback OK, dword delta exactly `0x20`) and the
  spawned instance still reads the bit CLEAR.** Within-run control: two spawns milliseconds apart,
  same world, same instrument, the CDO bit the only difference.
  ★★ **AND AN OFFLINE LANE PREDICTED IT BEFORE THE FLIGHT, WITH THE MECHANISM.** The ORDER is fine
  (`StaticConstructObject_Internal` calls the ctor at `0x13740CD`, the `~FObjectInitializer` →
  `PostConstructInit` → `InitProperties` 8 bytes later at `0x13740D5`); the CONTENT is wrong —
  `InitProperties` branches at `0x1368231` into the **PostConstructLink** chain only, and
  `UStruct::Link` (`0x1226C80`) never puts a property **owned by a NATIVE class** into that chain.
  There is **no bulk memcpy of the CDO onto a new instance anywhere on the allocation path.**
  ⇒ ★★★★★ **THE REUSABLE RULE: a CDO poke reaches a new instance ONLY IF THE CONSUMER READS THE CDO
  DIRECTLY. It does NOT propagate via `InitProperties` for a native-owned property.** S130's
  `bCanEverReplicate` never established otherwise — its consumer read the CDO *directly*
  (`cmp byte [CDO+0x6C],0`). The handoff generalised that precedent to a case it does not cover.
  ★★★★★ **WHAT WORKS INSTEAD — three arms, all flown, all confirmed by a second instrument:**
  **ARM B** call `AController::InitPlayerState` (`0x36DEE20`) **directly**, dispatched THROUGH THE
  VTABLE and REFUSED unless `[[ctl]+0x888]` resolves to `0x36DEE20` (not ceremony: [M]
  `ALokiPlayerController`'s slot 273 is the void fold). [M] it **does not test `bWantsPlayerState`**
  — zero `[reg+0x488]` refs in its 180 instructions — so no poke and no propagation are needed.
  Result: `controller+0x3C0` = a real **`BP_LokiPlayerState_C`**. Reproduced **3×**.
  **ARM C** `APawn::SetPlayerState` (`0x3BBD9F0`, REAL, 210 B, **NON-VIRTUAL** — so the arm
  validates it by a **16-byte prologue signature** instead) links `pawn+0x3D8`. Both sides now equal,
  the identical shape the PLAYER's own possession prints in the same output (the positive control).
  ⚠ ARM B leaving `pawn+0x3D8` NULL is CORRECT, not a bug, and was PRE-REGISTERED: the copy is
  `SetPlayerState` **inlined into `APawn::PossessedBy`** (`0x3BB1C64` reads `[Controller+0x3C0]`,
  `0x3BB1CD5` writes `[pawn+0x3D8]`), and possession already happened.
  ★ **PlayerArray registration is automatic** — `APlayerState::PostInitializeComponents` calls
  `AGameStateBase::AddPlayerState`. ⚠ Neither arm is CALL-ONLY (ARM B does a `SpawnActor`).
  ★★★★★ **ARM D — ONE POINTER MAKES THE ENGINE BUILD A **LOKI** BOT CONTROLLER.**
  `APawn::SpawnDefaultController` hands `SpawnActor` the **pawn instance's** `[pawn+0x3D0]` [M], and
  `APawn::APawn` writes that field by reading a CDO **by hand**: `0x3B80BD3 call 0x3BA4CE0` (a lazy
  `StaticClass()`) → `0x3B80BF3 mov rbx,[rbx+0x178]` → **`0x3B80C0D mov rax,[rbx+0x3d0]`** →
  `0x3B80C14 mov [rsi],rax`. **Measured live: `Default__Pawn+0x3D0` = the `AIController` UClass every
  spawned pawn carries.** That is the S130 shape, so poking it WORKS — same idea as ARM A, opposite
  outcome, **and the difference is who reads the CDO.** Full A-B-A, three spawns:
      A baseline  → `AIController<-Controller<-LokiActor<-Actor<-Object`          BotController: no
      B treatment → `LokiBotController<-LokiAIController<-AIController<-...`      BotController: YES
      C reversal  → `AIController<-...` again        (pokeOK=1 restoreOK=1, all 6 predictions hit)
  **The third spawn is what makes the restore a measurement rather than a promise.** Confirmed
  externally: `obj_by_chain =LokiBotController` → `found 1 … obj=0x17443C931A0`, **the same pointer
  the shim reported**. Then ARM B + ARM C gave THAT controller a PlayerState on both sides.
  ⚠ **SCOPE: this pokes the ENGINE `APawn` CDO** — while it stands, every newly constructed pawn
  process-wide inherits it. Poke → one spawn → restore. **NOT a shipping fix.**
  ⚠ **STILL NOT A COMPLETE BOT:** `ServerSetHeroClass` (`0x556DE43 → 0xF7EC20`) and `SetPlayerTeam`
  (`0x556DE53 → 0xF7EB60`) remain stripped folds and nothing here went through `SpawnBot`.
  ★★★★★ **FLIGHT 4 — ARM D REPRODUCED IN A FRESH CLIENT, AND THE LOKI BOT HAS A BRAIN [M].** A
  second launch, second staged world, different ASLR: same A-B-A, `pokeOK=1 restoreOK=1`. And a
  **two-sided WITHIN-RUN control** on the components, read externally:
  | field | ctrl A `AIController` | **`LokiBotController`** | ctrl C `AIController` |
  |---|---|---|---|
  | `BrainComponent` +0x498 | **NULL** | **`BTComponent` (`BehaviorTreeComponent`)** | **NULL** |
  | `Blackboard` +0x4B0 | **NULL** | **`BlackboardComponent`** | **NULL** |
  | `PerceptionComponent` +0x4A0 | NULL | NULL | NULL |
  | `PathFollowingComponent` / `CachedGameplayTasksComponent` | present | present | present |
  The two plain controllers were spawned by the SAME code milliseconds either side of the treatment,
  into the same world; the last row is the shared-baseline control proving the probe reads these
  fields correctly. **We passed `BehaviorTree = null`, so `ALokiBotController` built its own.**
  And it is POPULATED, not a husk: `BehaviorTreeComponent.NodeInstances = **21**`
  (`DefaultBehaviorTreeAsset` NULL, so it was *started*, not defaulted), `BlackboardComp`/`AIOwner`
  cross-wired, and `BlackboardComponent.BlackboardAsset = a real BlackboardData` with
  `KeyInstances = **15**`. ⇒ **the Loki bot's AI machinery is NOT gutted.**
  ⚠⚠ **IT DOES NOT SHOW THE BOT ACTS.** 21 nodes + a live blackboard mean the tree was BUILT, not
  that it executes usefully, and **movement was never measured** — the read was attempted and failed
  for an INSTRUMENT reason (the client had already been FK-32'd and the throwaway probe had no
  RUN-IS-VOID check, so it printed `UNREADABLE`). `LogBehaviorTree`/`LogAIModule` = 0 **with no
  positive control** ⇒ UNINTERPRETABLE. **Movement is S138's first item.**
  ⚠⚠ **AND A SELF-CORRECTION MADE THE SAME SESSION:** on flight 3's death alone I wrote *"repeated
  injection appears to accumulate FK-32 risk"*. **Flight 4 refutes the phrasing** — it died at the
  **4th** manual-map after **334 s** vs flight 3's 6th after 1144 s. Across the three recorded
  `0xDEAD` kills the counts are **7 (S132) / 6 / 4** with unrelated elapsed times: **no dose-response,
  so "accumulates" is unsupported [I, weak].** All three were multi-injection tutorial sittings.
  ★★★★ **FREE BY-PRODUCT — DRIVING THE PATH DECRYPTED THE LOKI BOT CODE (the S118 method):**
  `ALokiBotController::OnPossess 0x5565470` **0/4096 → 3782/4096** and `::Tick 0x556E9F0`
  **0/4096 → 3509/4096**, with `OnUnPossess 0x55667F0` still 0/4096 (never unpossessed — a correct
  negative) and three known-lit controls unchanged. `OnPossess` was recorded as COVERAGE-BLOCKED with
  *no way to read it*; it is now readable offline forever, and `Tick` being lit means **the bot
  controller was actually ticking**. Banked in `dumps/s137-lokibot/` → **`dumps/merged13.dump.exe`**.
  ⚠⚠ **THREE GATES, NOT ONE — AND ONE WAS LOST IN COMPRESSION, NOT NEVER FOUND.**
  `AAIController::PostInitializeComponents` is stock UE's
  `if (bWantsPlayerState && !IsPendingKillPending() && GetNetMode()!=NM_Client)`. GATE 2 is
  `ObjectFlags(+0x0C)>>30` (bit 30 `RF_Garbage`) at `0x45D6D31`; GATE 3 is `GetNetMode()` at
  `0x45D6D36`/`cmp eax,3`. ★ **`docs/s136-ai-controller-settled.md:524` DOES record gate 3** —
  it was **DROPPED when that doc was compressed into `docs/next-session-prompt-s137.md`**, whose
  listing jumps straight from `0x45D6D25` to `0x45D6D46`. Only **gate 2** was never recorded
  anywhere. ⇒ **the digest is the instrument that lost it** — this repo's own "a digest is an
  instrument" pattern (S115-d) operating one level down, settled-doc → handoff, and a successor
  reading only the handoff (which is what a handoff is FOR) could not have known.
  ⚠ *"gates 2 and 3 are known to hold"* was **[I], not [M]** — the existing netmode measurement is
  on the PAWN, gate 3 tests the CONTROLLER. ARM B settles it from another direction:
  `InitPlayerState`'s own first branch is that same guard on the controller, and it ran 3×.
  ★★★★★ **AND THE NEWLY-LIT CODE WAS THEN READ (S137 follow-up, 64 CONFIRMED / 25 DOWNGRADE /
  10 REFUTED). `ALokiBotController::OnPossess` (`0x5565470`, 2,222 B, slot 269) IS NOT GUTTED:**
  27 distinct direct call targets, **26 REAL / 1 DARK / ZERO folds**. It chains Super, requires an
  `ALokiHeroCharacter`, pulls a process-wide bot-config CDO, **calls `RunBehaviorTree(Cfg->[0x240])`
  via vtable disp `0x940`** (which is what creates `BTComponent` + `BlackboardComponent`), binds
  `HandleLivingStateChanged`/`UpdateCharacterControllable` onto `hero+0xC38`/`+0xDF8`, applies the
  `UGameplayEffect`s in `Cfg->[0x320]` to `hero+0xF00` and grants 3 abilities. **It reads NO
  difficulty, team or hero class** — all of it comes from one global config CDO.
  ★★ **A BRANCH DEAD ONLY BECAUSE OF OUR ORDERING:** it broadcasts a delegate at
  `ALokiPlayerState+0x5B0` **only if PlayerState is non-null**, and ARM B installs the PlayerState
  *after* possession. **Install it BEFORE possessing and that branch lights up** — cheap S138 arm.
  ★ **`ALokiBotController::Tick` (`0x556E9F0`, 1,261 B, slot 170, zero folds): the ONLY motion
  driver is a RANDOM WANDER**; no targeting, no ability use, no combat. It gates on
  `Blackboard != NULL` **and** a blackboard bool key (`.data 0xA0348F0`).
  ⚠⚠ **TWO OF THE SESSION'S OWN LANES CONTRADICTED EACH OTHER AND THE LIVE READ SETTLED IT.** One
  concluded `OnPossess` *"calls neither `RunBehaviorTree` nor `UseBlackboard`"* and therefore that
  the bot ticks with a NULL Blackboard. **REFUTED three ways:** the bytes (`0x55655F6 call qword
  [rax+0x940]` — the dispatch is **INDIRECT**, and the components are created in the **CALLEE**, so a
  scan for a direct call / for direct writes to `+0x498`/`+0x4B0` inside `OnPossess` is blind BY
  CONSTRUCTION); the adversarial pass, unprompted; and the live component table above. ★ Naming
  closes from both ends — the disp-`0x940` callee loads the wide literal **`BTComponent`** and the
  live object is **literally named `BTComponent`**. ⚠ `0x3316AF0` is NOT `RunBehaviorTree`'s body but
  a **4-way ICF-folded dispatch shim**, so using it to NAME disp `0x940` is the folded-RVA error.
  ★ **`SpawnBot` (`0x556D910`, 1,544 B, REAL) SPEC, corrected by its own refuter:** 43 call
  instructions = 39 direct + 4 indirect, **28 distinct direct targets — 25 REAL / 2 FOLD / 1 DARK**.
  Call the **raw impl** with 7 native args (`comp, &heroClassCell, locXYZ, teamIndex, difficulty,
  premadeController, &botName`; stack at `[rsp+0x20/0x28/0x30]`); **it returns the spawned
  `ALokiHeroCharacter*` directly**, so the `CreatedBot` out-param trap does not apply to a direct
  call. ⚠⚠ **`BotName` MUST be a ZEROED 16-byte FString** — SpawnBot fills it and **frees it with the
  game's `FMemory::Free` (`0xFF9310`) on BOTH exit paths**, so a shim-CRT buffer there is heap
  corruption. ⚠⚠ **IT IS NOT CALL-ONLY** (the lane claimed it; its refuter REFUTED it): an exhaustive
  operand scan finds **7 non-stack writes across FOUR objects**.
  ★ Premade short-circuit confirmed from the bytes: `0x556DA4F mov rax,[rsp+0x70]` / `0x556DAA1 test`
  / `0x556DAA4 jne 0x556DB32` skips `0x556DAAA..0x556DB30`, whose only writes are three to SpawnBot's
  own stack frame ⇒ **`MakeNewBotController` is never called.**
  ⚠ The authority sweep's honest payoff is a **NEGATIVE**: `SpawnBot`, `MakeNewBotController`, the
  three `LokiRideable` `Auth*` entries, `OnPossess` and `Tick` — **not one** reads `Role` or calls
  `GetNetMode`. They die on Loki's own stubs and on folds. ⚠ *"`0xF7EB60` IS `LokiIsServer`"* is
  **[I, strong], not [M]** — 106,924 stored-pointer occurrences; **a folded RVA names nothing.**
  ⚠ **A SECOND READER of bit `0x20` exists at `0x45D5E55`** (in fn `0x45D5DD0`), found by adversarial
  review and absent from the handoff — any future arm that sets the bit moves **two** behaviours.
  ⚠ **The client died at the end by protector kill (`0x0000DEAD`, FK-32) ~8 s AFTER the last capture**,
  on the **6th** manual-map into one process; S132's own FK-32 came on the **7th**. n=2 across
  sessions: **suggestive that repeated injection accumulates FK-32 risk, not established.**
  ⚠ **`TerminateProcess`/`ExitProcess` ARE in every `tutorial_launch` DLL's import table** (0 in the
  source; they come from the clang/link.exe scaffolding). CLAUDE.md's *"no `TerminateProcess`/
  `ExitProcess` in any shim source"* is true of the SOURCE only — a successor re-deriving it from the
  binary will find them. The conclusion is unaffected and in fact strengthened (`play`/`dismount`
  carry them and never produced `0xDEAD`).
  ⚠ **An evidence file was destroyed by `| tee` re-running a probe after the client died**
  (`docs/s137-external-AFTER-flight3.txt`, now a labelled transcript reconstruction).
  **Do not `tee` over an evidence file.**
  **Arms** (RAW): `botps` `445fb5ce5b902bc3` · `botps-link` `e287d7ae8c5f4814` · `lokibot`
  `3119d75ae2ca1859` · `botps-readonly` `f860411a6ef7cb49` · `botps-arma` `623252907a68fd08` ·
  `botps-armb` `c574c8ce5c3ccf95`. All DISTINCT. Regression gate `botai` `5e47c13cf7f0a158`
  UNCHANGED across all three source patches (every edit is behind `#if KBSPS`). Readout:
  **`tools/re/playerstate_readout.py`** (read-only RPM; carries its own positive control — the
  player's real possession — and says so when that control fails).
- ★★★★★ **S138 (2026-08-23) — THE BOT'S AI RUNS END TO END, AND THE WALL MOVED TO THE
  MOVEMENT COMPONENT. Read `docs/next-session-prompt-s139.md`, then
  `docs/s138-flight9b-flymode-refuted.md`.** Nine flights; every result below is live and controlled.
  **[M] THE CHAIN:** nothing writes `LivingState=Alive` (offline: only TWO native writers of
  `ALokiCharacter::LivingState @ +0x1090`, and BOTH store 0) → every character reads **Dead**
  (6/6 live + 30/30 CDOs) → poke the byte and call `UpdateCharacterControllable` (impl
  **`0x5570B80`**) → **the gate `bCharacterControllable` (+0x6A0) OPENS 0→1** → `Tick`'s wander
  driver RUNS (**44 distinct horizontal unit directions, Z exactly 0, over 97 s / 194 samples**,
  matching the transcribed 2.0 s cadence) → `ControlInputVector` on the PAWN receives them in
  **193/194** samples → **and the pawn never moves one unit.**
  ★★ The controller→pawn motor chain is CONFIRMED IN FLIGHT, not inferred (different objects).
  ⚠⚠ **FOUR HYPOTHESES REFUTED — do not re-open:** (1) the gate / `LivingState` (it opens);
  (2) `MovementMode` is wrong — **bot and player are BOTH `MOVE_Falling`(3)**; (3) forcing
  `MOVE_Flying` (what `play` does) — poked, held 25 s, **no effect**; (4) the component is
  deactivated — `bIsActive=True` on both.
  ⚠⚠ **RETRACTED S139 — the old text here read "STANDING: the controller ticks, the CMC does not —
  `ControlInputVector` is never consumed, and stock UE zeroes it inside `TickComponent`". BOTH
  HALVES ARE WRONG.** [M] over all 194 samples in `docs/s138-f8-motion.txt`: `|ControlInputVector|`
  max **1.0001**, never once above 1.05, and exactly equal to `RandomMoveDirection` in 193/194. The
  write is `+=` (`APawn::Internal_AddMovementInput`), so an UNCONSUMED `+=` predicts |CIV| ≈ 5820 at
  a per-frame cadence or ≈ sqrt(44) = 6.6 at the 2 s cadence — **and in the latter case it would not
  equal the latest direction.** ⇒ **it IS consumed every frame ⇒ `TickComponent` IS entered**
  ([I, strong]: a second consumer exists, `APawn::ConsumeMovementInputVector 0x03B93470`, and an
  async arm at `0x036037AF` can skip the consume — the live observation excludes that arm, the
  claim as first written did not). ★ **The reconciliation: `ConsumeInputVector` is called FIRST, at
  `0x036037FE`, BEFORE both early-outs (`HasValidData 0x0360381D`, `ShouldSkipUpdate 0x03603834`) —
  so consumption does NOT imply simulation.** Three lanes + three verifiers agree on those bytes.
  ⚠⚠ **AND `play` IS NOT THE MOVING CONTROL THE OLD NEXT-STEP ASSUMED.** It moves the hero by
  **writing `CMC+0xE8` (Velocity) and `CMC+0x328` (Acceleration) every game-thread hit**
  (`tutorial_launch.cpp:3047`, `:12599`) — it does NOT fix an input path, and S75 measured *forced
  `AddMovementInput` → ZERO accel/velocity* on the **PLAYER** too (`tutorial_launch.cpp:364-366`).
  [M, source] `RM_PLAY` calls `DoPlay()` (`:1275`), whose init is teleport / `GravityScale=1` /
  `ResetIgnoreMoveInput` / `SetMovementMode(KFLYMODE)` / `SetActorHiddenInGame(false)` / body build —
  **`SetActive` + `SetComponentTickEnabled` + `SetActorTickEnabled` belong to `DoWakeMove` (`:2983`),
  which runs ONLY under `RM_WAKEMOVE` (`:1240`).** ⇒ `play` is not a tick fix, and the player is a
  **CONTAMINATED control on `+0xE8`/`+0x328` by construction**. Structural fields only.
  ★ **NEXT (S139): do NOT whole-struct diff a 0x19D0-byte component.** Read the 10 ranked fields via
  **`tools/re/cmc_earlyout_readout.py`**, led by **`CMC+0x16C8`** — `ULokiCMC::StartNewPhysics`'s
  **dt-INDEPENDENT** "PerformMovement reached me" latch (`mov byte [rcx+0x16C8],1` at `0x055C2469`,
  no DeltaTime test above it; the engine's MIN_TICK_TIME bail is downstream) — paired with
  **`CMC+0x12B0`** (`TimeSinceFallingStart`, dt-DEPENDENT). `1` + frozen ⇒ the DeltaTime kill;
  ~~`0` ⇒ an early-out at or above `PerformMovement`~~.
  ⚠⚠ **THE `0` BRANCH IS FALSE (S140) — `0` is the resting value in EVERY world**, because disp
  `0xA50` (`0x0530ABF0`) clears the byte at the tail of every completed `PerformMovement`. The `1`
  branch is still sound (a sampled `1` means "inside `PerformMovement` right now, past
  `StartNewPhysics`") but polling for it is hopeless — the window is microseconds of a 16 ms frame.
  **Use the payload `+0x16B0` with a poked sentinel instead.** See `docs/s140-tier1-cfg.md` §4-§5.
  ⚠⚠ **`UActorComponent::PrimaryComponentTick` IS A UPROPERTY, at `UActorComponent+0x40`** [M, S139]
  (UHT `PropPointers` array `.rdata 0x07F9EFC0` entry 1; the ctor also installs the
  `FActorComponentTickFunction` vtable `0x07E08B38` there). `AActor::PrimaryActorTick` is at
  `AActor+0x38`. **`FTickFunction` sizeof `0x28`**: TickGroup`+0x08`, EndTickGroup`+0x09`,
  flags`+0x0A` (`bTickEvenWhenPaused 0x01`, **`bCanEverTick 0x02`**, `bStartWithTickEnabled 0x04`,
  `bAllowTickOnDedicatedServer 0x08`, all four [M] from their UHT `SetBitFunc`s), TickState`+0x0B`
  (0=Disabled 1=Enabled), TickInterval`+0x0C`, **InternalData`+0x20`, and `InternalData == NULL`
  means NEVER REGISTERED**. Reader: `scratchpad/s139/ticksniff.py`. **The old line here said the
  opposite and foreclosed the read.**
  ⚠⚠ **`bCharacterControllable (+0x6A0)` IS ON THE *CONTROLLER*, NOT THE CHARACTER** [M, S139] — its
  UHT record's `SizeOfOuter` is **`0x6A8`** (vs `sizeof(ALokiCharacter)` = `0x1950`), its `SetBitFunc`
  is `.text 0x02D7A520`, and its writer `UpdateCharacterControllable 0x05570B80` also dereferences
  `[this+0x4B0]` Blackboard and `[this+0x498]` BrainComponent — `AAIController` fields.
  `docs/s138-flight9-movement-not-simulating.md` §2.2 already said so; **the digest dropped it.**
  ⚠⚠ **THIS BUILD'S `EMovementMode` IS MODIFIED: `MOVE_Dashing` is INSERTED at index 6, so
  `MOVE_Custom == 7` and `MOVE_MAX == 8`** [M, S139, three instruments: the `.rdata` enumerator run
  at `0x07E10660`; `StartNewPhysics`'s 8-entry jump table at `0x03600BF8` bounded by `cmp esi,7`,
  case 6 → disp `0xCC8` (PhysDashing) and case 7 → disp `0x990` (PhysCustom); and
  `IsDashing 0x035E6810 = cmp byte [rcx+0x231],6`]. **Any probe carrying stock UE's
  `MOVE_Custom == 6` mis-decodes Loki custom modes by one** — `movementmode_readout.py` does.
  ★ **SETTLED ON THE WAY:** `SpawnBot`'s premade path RUNS (ARM E — `MakeNewBotController`, and with
  it FK-22's stripped getter, is never called), and its early exit is **`0x556DE6A`** =
  `GetTeamState` NULL, measured by `[PS+0x8C8]` going 0→5 with the string `'bot0'`.
  **`TeamStates` can NEVER be non-empty on a client [M]** (`GetOrCreateTeamState` impl `0x5634BD0`
  returns nullptr unconditionally; `SetNumTeams` is the void fold) ⇒ anything past `0x556DE6A` is
  unreachable. **Do not chase it.**
  ⚠⚠ **RULE U2 IS REFUTED** — *"`0x5556D50` still dark ⇒ the PlayerState gate was not passed"* is a
  non-sequitur (all three gates rejoin UPSTREAM of that receipt) and was refuted empirically too.
  ⚠⚠ **`SpawnBot 0x556D910` is `PAGE_NOACCESS` in a live process until it has EXECUTED** — the
  protector decrypts on EXECUTE, so a prologue-signature READ can never pass on a cold page, and
  `merged1x` grading it LIT is a UNION across processes, not a live state. Inject `botspawn` first
  to decrypt it (6/6 pre-registered predictions, reproduced twice).
  ⚠ **A SIXTH STUB SHAPE defeats the fold test:** `sub rsp,0x28; call <GetWorld>; xor eax,eax; ret`
  grades **REAL** under a two-state test and is not DARK either. Only reading the instructions works.
  ⚠ **`ELivingState`: Dead=0 Alive=1 Knocked=2** (NOT `ELokiLivingState` — 0 occurrences in the
  image, against passing controls). A DIFFERENT enum `EPlayerLivingState` has **Alive=3** and is used
  by `ALokiPlayerState::GetLivingState` at `+0x3f8` — carrying "Alive==1" across is wrong by two.
  ⚠ **`botspawn`'s recorded digest was STALE by ~17 h of source drift** — current RAW
  **`b2203efd62161182`**; `e48c90bc6cf17c93` / `1a8fa5fe06f87019` no longer reproduce.
  ⚠ **A hardcoded offset that "agrees" with a by-name read is NOT corroboration when both can read
  zero** — `Velocity` is `CMC+0xE8`, not the `+0xE0` one probe hardcoded.
  **Arms** (RAW; archived `dumps/s138-arms-v3/`, `dumps/s138-arms-armf/`): `driverecompute`
  **`a2a952babfed256b`** (ARM D+F) · `driverecompute-ctrl` `2a91f0aa7f3d521b` (ARM F compiled out,
  the control) · `spawnbot_premade` `6cb296bbf3c8c696` · `botspawn` `b2203efd62161182` · regression
  gate `botai` **`5e47c13cf7f0a158` UNCHANGED across every S138 patch**.
  **Tools:** `tools/re/livingstate_sweep.py` · `movementmode_readout.py` · **`motion_watch.py`**
  (polls until the bot exists, THEN tight-samples — **start the reader BEFORE the injection**;
  flight 7 lost the key observation by polling afterwards) · `livingstate_poke.py` and
  `flymode_poke.py` (⚠ each WRITES one aligned byte, with A-B-A and an unpoked specificity control) ·
  **`configs/s138-autostage.ps1`** (launch→settle→arm→stage with retry; staged on attempt 1 in 4 of 5).
  ⚠⚠ **THE DRIVER'S OWN DEFECT, WORTH MORE THAN THE DRIVER:** its first version tested the marker
  for `[SP] done step=4` IMMEDIATELY after `fk24-stage.ps1` returned — but `stage complete` means
  "finished INJECTING sp", and sp writes its receipt **12 s later**. It `Stop-Process`'d **three
  clients that had staged perfectly**, and came one attempt from being written up as a fourth
  consecutive FK-31 death (p=0.005 — the threshold for calling FK-31 systematic). **A stage
  script's completion message means "I finished my step", NOT "the injected code finished its
  work." Gate on the payload's own receipt.**
  ⚠ **A VERDICT LINE CAN LIE:** `livingstate_poke.py` printed `P3 … YES` from a predicate whose
  terms were all always-true, while its own samples showed the opposite. **Read the samples, not the
  verdict**; both poke tools now compute verdicts from observed data.
  ⚠ **External `WriteProcessMemory` is UNRESOLVED as a hazard** — used for the first time in this
  project here; the client died ~44 s later with the FK-32 signature, but that is confounded by a
  very high base rate and n=1. Settling it needs a matched no-write sitting.
  ⚠ ~~Two tracked files are **UNCOMMITTED**~~ — committed as `7f7f3e2`.
  ⛔ **Still not a bot:** `ServerSetHeroClass` / `SetPlayerTeam` remain stripped folds, and none of
  this happens without pokes the game never performs itself.
- ★★★★★ **S139 (2026-08-23) — BOTH MOVEMENT HYPOTHESES ARE DEAD AND THE WALL IS DOWN TO A FEW
  HUNDRED BYTES: `PerformMovement` RUNS with a real DeltaTime; ~~`StartNewPhysics` NEVER RUNS~~.
  Read `docs/s139-flight1-the-bot-is-not-special.md`, then `docs/s139-movement-ladder.md`.**
  ⚠⚠⚠ **THE SECOND HALF OF THAT HEADLINE IS REFUTED, NOT MERELY RETRACTED — AND THE TRUTH IS THE
  OPPOSITE. `ULokiCMC::StartNewPhysics 0x055C2430` RUNS, on the bot AND the player, essentially
  every frame [M, S140 TIER 2]. Read `docs/s140-tier2-sentinel.md`.** S140 Tier 1 showed the
  `+0x16C8` latch is an invalid instrument (it reads 0 in every world), which made "never runs"
  UNGRADED; Tier 2 then MEASURED the answer with a **pre-poisoned payload**. The DeltaTime half
  stands and is now joined by the physics-step half.
  One staged client, ONE injection, read-only RPM; 6 offline RE lanes + 6 adversarial verifiers.
  ★★ **[M] THE BOT IS NOT SPECIALLY DISADVANTAGED — bot and player read IDENTICALLY on EVERY
  structural field**: `UpdatedComponent` (both non-null CapsuleComponent) · `Mobility` 2 ·
  **`Role` 3** · `RemoteRole` 1 · `Controller` non-null · `RF_Garbage` 0 · `MovementMode` 3 ·
  `MaxAcceleration` 50000 · `bCharacterMovementEnabled` 1 · `Acceleration` (0,0,0) ·
  `AnalogInputModifier` 0 · latch `+0x16C8` **0** · `bCanEverTick` 1 / `TickState` Enabled /
  `Prerequisites.Num` 1 / `InternalData` non-null / **`bRegistered` False** / `TaskPointer` 0 /
  `LastTickGameTimeSeconds` **-1.0** · `bIsActive` True · `AttributeSetStorage` **NULL**.
  The ONLY structural difference is `AbilitySystemComponentStorage@0xF00` (bot NULL, player non-null
  — `KWIREGAS` wires the player's). ⇒ **stop looking for a bot/player difference in the movement
  component; there isn't one.** ★ `Role@+0x160 == 3` on a `SpawnAIFromClass` pawn is the FIRST such
  measurement and kills ladder exits E6 and E7.
  ⇒ ★★★ **THE THIRD TIME THE QUESTION HAS BEEN MIS-FRAMED IN THE SAME SHAPE** (S138 `LivingState`:
  every character Dead; S138 `MovementMode`: both Falling; S139 the whole ladder: identical).
  **It is not "why does the BOT not move" — it is "why does NO character move on this route".**
  ★★★★★ **[M] S1 (the "HitStop DeltaTime kill") IS REFUTED, WITH A MECHANISM.** In
  `ULokiCMC::PerformMovement 0x055B8370`: `0x055B838D movaps xmm6,xmm1` (xmm6 = DeltaSeconds) …
  `0x055B83B5 call 0x56E7C10` (toggle 120 = HitStop, NULL context) … `0x055B83FA xorps xmm6,xmm6`
  (the kill) … `0x055B8409 movaps xmm0,xmm6` · `0x055B840C addss xmm0,[rsi+0x12b0]` ·
  `0x055B8414 movss [rsi+0x12b0],xmm0`. ⇒ **`+0x12B0` accumulates EXACTLY the register HitStop would
  zero.** MEASURED live: it advances at **1.0× real time on BOTH pawns** (bot 33.14→43.34 over
  10.2 s; player 380→390). ⇒ DeltaTime is real, HitStop did not fire, **and `PerformMovement` is
  running.**
  ⚠⚠⚠ **THE OLD TEXT HERE READ "[M] AND `ULokiCMC::StartNewPhysics 0x055C2430` HAS NEVER RUN ON
  EITHER COMPONENT … `+0x16C8` is a valid sticky 'ever reached' instrument, and it reads 0 on both."
  RETRACTED S140 (2026-08-23). `+0x16C8` IS NOT A STICKY LATCH AND `latch == 0` IS UNINTERPRETABLE.
  Read `docs/s140-tier1-cfg.md` §4.** [M] `ULokiCMC` vtable disp **`0xA50` = `0x0530ABF0`**
  (`80b9c816000000 / 7407 / c681c816000000 / e98bbb2cfe`) **CLEARS** the byte, and engine
  `PerformMovement` calls that slot at **`0x035EB569 ff90500a0000 call [rax+0xa50]`** with
  `rcx = rbx = this` — later in the same call, on a path the `StartNewPhysics` call site
  **DOMINATES**, and the clear **POST-DOMINATES** `0x035EB1CB`. ⇒ **an off-thread read sees `0`
  whether the step runs every frame or never runs at all.** Derived independently THREE times in one
  session (session lead, lane L4, lane L6) and re-verified by the adjudicator.
  ★★ **[M] THE FIELD IS NAMED, FROM ITS OWN CONSUMER — it is a per-frame `TOptional<FVector>`
  validity flag over the Velocity snapshot at `+0x16B0`.** `.data 0x09BC9AD0` =
  `{"GetRecentVelocity", thunk 0x0530C7E0, impl 0x0530AC10}`, and the impl is
  `cmp byte [rcx+0x16c8],0 / mov eax,0x16b0 / mov r8d,0xe8 / cmove eax,r8d` — i.e. return the
  **snapshot** if the flag is set, else **live `Velocity @+0xE8`**.
  ★ **THE DURABLE READOUT IS THE PAYLOAD `+0x16B0`, whose only CMC-side writer is `0x055C244F`
  inside `StartNewPhysics`** — but a resting `Velocity` of `(0,0,0)` makes a written snapshot
  indistinguishable from a never-written one, so it needs a **poked sentinel** to discriminate.
  ⚠ Only the **seventh bail** — `0x035EB146 call [rax+0x6b8]` (a SECOND `HasValidData`) →
  `0x035EB14E jne 0x35EB1CB`, fallthrough `0x035EB150` — leaves the byte at 1. [M] the clear is
  unreachable from `0x035EB150` and reachable from `0x035EB1CB`.
  ⚠ **VOID, it rested on the latch:** the old line *"It also explains with no extra assumption why a
  `MOVE_Falling` pawn with `GravityScale 1.000` does not fall"*. `PhysFalling` really is dispatched
  from `StartNewPhysics` (case 3 of the bounded 8-entry table at `.text 0x03600BF8`), but **nothing
  shows `StartNewPhysics` does not run**, so the no-fall observation is now an unexplained
  phenomenon, not a derived consequence. ⇒ ★ **the old "THE WALL IS BETWEEN `0x055B8414` AND
  `0x035EB13A`" framing is likewise VOID.**
  ⚠⚠ **RETRACTED WITHIN S139 — do not read "`PerformMovement` runs" as "the ENGINE's
  `PerformMovement` runs".** `+0x12B0` is accumulated at `0x055B840C`, **UPSTREAM of the Super call
  at `0x055B85C1`**, so its advance establishes only that **`ULokiCMC::PerformMovement`** ran with
  dt > 0 — nothing about how far the engine impl got. A mid-session write-up called "six engine exits
  all measured passing yet the call never happens" **a real contradiction; it is not one** — the
  engine may simply bail at one of its own gates. ★ The measurement was right; the inference crossed
  a function boundary. Full retraction: `docs/s139-flight2-gate-refuted.md` §3.
  ★★★★★ **AND THERE IS A GATE NOBODY HAD, WITH A FREE RECEIPT: engine
  `StartNewPhysics 0x03600990` carries its OWN `IsSimulatingPhysics` test**
  (`0x036009D3` → `0x036009E4 call [rax+0x4c0]` → `0x036009EC je`) that **LOGS**
  *"UCharacterMovementComponent::StartNewPhysics: UpdateComponent (%s) is simulating physics -
  aborting."* (`.rdata 0x07FC0670`, `CharacterMovementComponent.cpp:3477`, threshold 5 = `Log`).
  ⚠ Grepped: **0 occurrences — and `LogCharacterMovement` occurs 0 times in the whole log, so the
  category has NO positive control and that zero is UNINTERPRETABLE** (the Class-A-vs-never-ran
  trap). ⇒ **Pin `LogCharacterMovement=Log` in the USER `Engine.ini`** (FK-11's proven channel;
  `configs/set-log-verbosity.ps1`) **and the whole question becomes a per-frame log line.** That is
  S140's first move.
  ★ **[M] `bSimulatePhysics = 0` on the hero capsule** (`BodyInstance @+0x3F0`; decode control:
  `bEnableGravity` reads **1** from the SAME byte under a different mask) ⇒ the `PerformMovement`
  copy of that gate passes. ⚠ But `IsSimulatingPhysics` is called with **`bGetWelded = TRUE`**
  (`0x03C9B0A0`: `mov r8b,1` → `call [rax+0x810]` `GetBodyInstance`), so it can answer about a
  **weld parent** — the one gate where the measured input and the tested condition are provably
  different objects.
  ⚠ **POPULATION CONTROL — THE LATCH HALF IS VOID (S140).** The old text read *"37 movement
  components live, EVERY latch `+0x16C8` = 0, and exactly ONE is doing anything at all ⇒ there is no
  moving character anywhere in this world to diff against."* **37/37 zeros is equally expected under
  BOTH readings, so it never discriminated anything.** What survives is the *other* column of the
  same sweep — 36 of 37 read `TimeSinceFallingStart 0.000` and `MovementMode 0 (MOVE_None)`, i.e.
  pooled and inert. **"No moving character to diff against" stands on that, not on the latch.**
  ★ And it should have raised the alarm at the time: under the old reading, 37/37 means *nothing in
  the world can simulate movement at all* — the far less likely of the two explanations.
  ★ Also banked: **`[ALokiCharacter+0x7F0]` is NOT the ASC** — it is the `IAbilitySystemInterface`
  **secondary VTABLE pointer** (structure [M]; the interface NAME is [I, strong] — MSVC RTTI is
  stripped), whose slot `+0x10` (`0x055A9610 = mov rax,[rcx+0x710]; ret`) returns **`char+0xF00`**.
  Both Loki HitStop gates therefore consult the character's OWN ASC, and the **bot's `+0xF00` is
  measured NULL** ⇒ S1 is dead for the bot in ONE direction. ⚠ **Not "iff"** — a non-null `+0xF00`
  would still require `IsA<ULokiAbilitySystemComponent>` AND the `State.HitStop` tag true
  *continuously* for 97 s on a bot that was never damaged.
  ★ `0x055B2930` **IS `IsStunned`** [M, from the `.data` `{name, thunk, impl}` triple at
  `0x09BC5A48`, validated by four passing positive controls and one passing negative].
  ★★★★★ **S139 FLIGHT 3 — `ControlledCharacterMove` RUNS, AND THE INPUT WALL IS
  `GetMaxAcceleration() == 0`. Read `docs/s139-flight3-controlledcharactermove-runs.md`.**
  **[M] THE PROOF IS A SIGNED ZERO:** `Acceleration @CMC+0x328` carries `ControlInputVector`'s
  **SIGN** in **22 of 22** samples (44 sign bits) while the input churns — `(-0.0000, 0.0000, 0)`
  against `(-0.9650, 0.2622, 0)`, and so on. A never-written field is `+0.0` forever and **cannot
  track a sign** ⇒ the `ScaleInputAcceleration` store at `0x035DCD6B` **executed every frame** ⇒
  **`ControlledCharacterMove` RUNS and the whole tick ladder E1–E7 is PASSED. S2 IS REFUTED.**
  ⇒ `Acceleration = input × GetMaxAcceleration()`, and it is ZERO because **the getter is
  GAS-backed and `AttributeSetStorage @+0xF08` is NULL**.
  ★ **The BOT was REQUIRED for this and the player could not have given it:** the rival explanation
  is `ULokiCMC::ConstrainInputAcceleration 0x055A75B0` writing literal `ZeroVector` on its
  `IsStunned` arm — and `IsStunned 0x055B2930`'s first guard is *NULL ASC → false*, with the **bot's
  `+0xF00` measured NULL** (the player's is non-null; `KWIREGAS` wires only the player's). The arm is
  unreachable by construction on the bot.
  ⚠⚠ **MY OWN VERDICT LINE GOT IT WRONG — `distinct Acceleration values: 1`.** Python hashes
  `-0.0 == 0.0`, so a `set()` collapsed the signed zeros and hid the entire finding; the **printed
  samples** carried it. **Record raw, derive afterwards** — the second instance this session
  (`rootset_census.py` is the other). ⚠ The bit-level re-confirm **did NOT obtain** (client died; the
  probe self-voided) — `docs/s139-f3-signedzero.txt` is the harness, re-run it first next sitting.
  ⛔ **THE WELD HYPOTHESIS IS REFUTED** — `GetBodyInstance` is `[capsule vt+0x810] = 0x03C91C60`:
  `test r8b,r8b / je / mov rax,[rcx+0x5f0] / test / jne / lea rax,[rcx+0x3f0] / ret`, and **live
  `WeldParent @capsule+0x5F0 == NULL`** ⇒ it returns the capsule's own body ⇒ `bSimulatePhysics = 0`
  ⇒ the gate genuinely passes. (The `lea rax,[rcx+0x3f0]` independently confirms `BodyInstance @+0x3F0`.)
  ★★★★★ **AND THE FIX IS ALREADY IN THIS REPO, LIVE-PROVEN, AND WAS NEVER PORTED — a textbook
  method-rule-#2 instance.** `docs/coverage-audit-s101.md:283` (≈38 sessions old) records the DS route
  borrowing `Default__LokiPlayerState_HeroAffiliated`'s **default subobjects** into the hero's
  `+0xF00/+0xF08/+0xF10` and writing the attribute block: **measured `GetMaxSpeed()` 0 → 500,
  `GetMaxAcceleration()` 0 → 50000, and the hero physically translated through the world via the
  STOCK ENGINE CHAIN.** `:630` ranks porting it *"Single highest-value experiment available"*. Code:
  **`ds_hybrid.cpp:2370-2430`**. ⛔ **DO NOT SPAWN the carrier** (S80: instant client crash) — use the
  CDO's subobjects. ⚠⚠ **A PARTIAL PORT FAILS:** wiring `AttributeSetStorage` makes the Loki CMC read
  **every** movement value from attributes, so a set with only `MoveSpeed` gives `MaxAcceleration = 0`
  and still no movement (observed). Write the whole block (`MoveSpeed`, `MaxMoveSpeed`,
  `MaxAcceleration` 50000, `GroundFriction` 8, `BrakingDecelerationWalking` 2048, `Mass` 100) at
  `FGameplayAttributeData` `+0x8` **and** `+0xC`. ⚠ It writes a CDO default subobject — process-wide.
  ★ `tutorial_launch`'s `KWIREGAS` **deliberately writes only `+0xF00`** (`tutorial_launch.cpp:11899`)
  — exactly the gap, and every staged marker has printed `AttributeSetStorage @0xF08 = 0x0 (NULL)`.
  ★★★★★ **FLOWN AT S139 FLIGHT 4 — THE PORT WORKS, AND IT SPLIT THE WALL IN TWO. Read
  `docs/s139-flight4-gas-port-works.md`.** ARM G (`BsPsGasAttrs`, `KBSPSARMS` bit 8) borrows the CDO's
  default subobjects into the BOT's `+0xF00/+0xF08/+0xF10` and writes the whole block —
  **3/3 storages, 6/6 attributes, every one readback-verified.** Result, 20 live samples:
  **[M] `Acceleration = ControlInputVector × 50000`** — ratio min 49991.15 / max 50006.32 /
  **mean 49999.63** over all 40 components, i.e. `ScaleInputAcceleration = GetMaxAcceleration() ×
  input` with the getter returning exactly the `MaxAcceleration` we supplied.
  ★★ **PERFECT WITHIN-RUN SPECIFICITY CONTROL: the PLAYER was deliberately left UNTREATED**
  (`+0xF08` still NULL) and its `Acceleration` was non-zero in **0 of 20** samples, same process,
  same pass, same code. ⇒ **the input wall is CLOSED.**
  ⚠⚠ **BUT THE LATCH STAYED 0, `Velocity` stayed (0,0,0), and the pawn moved 0.00 uu ⇒ THE INPUT
  WALL AND THE PHYSICS-STEP WALL ARE *TWO* PROBLEMS.** That was pre-registered as P4 with BOTH
  branches written down and neither predicted, so it cannot be reinterpreted after the fact.
  ⚠⚠⚠ **THE "PHYSICS CONTRADICTION" DISSOLVED AT S140 — THERE WAS NO SEVENTH EXIT, THERE WAS AN
  INVALID INSTRUMENT.** The old text asked whether *"something bails for a reason none of the six
  accounts for, or a seventh path exists that the CFG walk's `target > call` predicate cannot see"*.
  **Both horns are dead** (`docs/s140-tier1-cfg.md`):
  **(a) [M] THE SIX IS COMPLETE AND EXACT.** Recursive-descent CFG over engine `PerformMovement`
  `0x035E9EC0`, reproduced by **four independently written instruments**: **1461 instructions**
  (a linear sweep gets 1074 and is unsound), **148 calls, 0 indirect jumps, 0 decode failures,
  0 coverage gaps (6538/6538 bytes), 1 `ret`, `|R| = 1075`**. Backward reachability from the call
  returns **exactly the six** — no additions, no false positives, **0 dead-ended nodes in `R`**, and
  **exactly 2 backward edges in the whole function, NEITHER in `R`**. ⇒ **there is no backward bail
  and no seventh path.** The `target > call` predicate happened to be right here, and now it is known
  *why* rather than assumed. ★ **Five of the six DOMINATE the call; `0x035EA25D` does not** (it is a
  redundant second `HasValidData` inside the optional root-motion block).
  ⚠ Keep the general lesson even though it did not bite here: a forward-address predicate is blind to
  backward bails **and to FALLTHROUGH edges leaving `R`** — engine `TickComponent 0x03603780` has
  three of the latter, so the trap is real, just not in this function.
  **(b) [M] "`StartNewPhysics` is never entered" WAS NEVER MEASURED** — its sole support was the
  `+0x16C8` latch, which reads `0` in every world (see the retraction above). It is now **UNGRADED**.
  ⇒ ★★ **THE QUESTION IS NO LONGER "why is the physics step never entered". IT IS "why does a
  correct `Acceleration` produce no `Velocity`"** — which points downstream, at
  `CalcVelocity` / `PhysFalling` (`0x055B89F0`, disp `0x830`), a function nobody has read.
  **Builds:** `gasattr` RAW **`2fcc2536e21f18e3`** · `gasattr-ctrl` RAW **`4465ebc4d7168c03`**
  (ARM G compiled out; **verified DISTINCT** — not an A/B against a copy of itself). Regression gates
  `botai` `5e47c13cf7f0a158` and `driverecompute` `a2a952babfed256b` **UNCHANGED**.
  ⚠ **NOT OBTAINED:** a re-read of the six gate inputs on a TREATED bot — the client died mid-probe
  and the script threw rather than printing partial values.
  ⚠ **One honest qualifier on `coverage-audit-s101.md:283`:** the DS route reported the hero
  **translating**; the identical recipe here produces acceleration and **no translation**, because
  the physics step is blocked by something the DS route did not have. **Do not read that line as
  promising movement on the force-open route.**
  ⚠⚠⚠ **THE OLD "RESIDUAL" LINE IS VOID (S140): it read "`StartNewPhysics` is STILL never entered
  (latch 0 on the bot, the player, and all 37 movement components)". THE LATCH CANNOT SUPPORT
  THAT.** What survives untouched is the *phenomenon*: `Velocity` stays `(0,0,0)`, the pawn
  translates **0.00 uu**, and a `MOVE_Falling` pawn with `GravityScale 1.000` does not fall — all
  from instruments unrelated to `+0x16C8`. **"A zero `Acceleration` does not stop GRAVITY" still
  stands, and the input wall and the movement wall are still two problems.** ⚠ But "fly the port and
  read the latch in the same pass" is now **the wrong experiment** — the latch would read 0 either
  way. Use the sentinel test below.
  ★★★★★ **AND S140 TIER 2 SETTLED IT: THE PHENOMENON SURVIVES BUT ITS CAUSE IS NAMED. `Velocity` is
  not merely never written — it is ACTIVELY COMPUTED AND WRITTEN TO ZERO EVERY FRAME [M].** Flight 2
  re-wrote a `Velocity` sentinel every ~2 ms for 400 iterations: the payload at `+0x16B0` held the
  sentinel **396/400** (`hitPoison=0`, `hitOther=0`), and `Velocity` had lost it by read time in
  **36 of 400** 2 ms windows — exactly the windows a physics step landed in.
  ⚠⚠ **A LINEAR DISASSEMBLY SWEEP IS NOT A CFG.** Over engine `PerformMovement` a linear sweep
  decoded **1,074** instructions where recursive descent finds **1,461** — it missed ~390. It
  happened to get the exit set right; do not rely on that. ⚠ And **"enumerate forward branches whose
  target is ≥ the call" is structurally blind to bails that jump BACKWARD** — use backward
  reachability over the call node.
  ⚠⚠⚠ **THE S139 "NEXT, and it is small" LIST IS REFUTED IN BOTH ITEMS (S140).** It read:
  *"(a) does Loki's `PerformMovement` reach its Super? two forward branches jump toward it —
  `0x055B845E test byte [CharacterOwner+0x580],8 / jne` and `0x055B846B mov ebp,[rsi+0x1988] /
  sub ebp,1 / js`; `[CharacterOwner+0x580] & 8` is an unread live byte. (b) if it does,
  `UpdatedComponent->IsSimulatingPhysics()` is the prime remaining engine gate and was NOT read."*
  **(a) [M] `ULokiCMC::PerformMovement` reaches its Super UNCONDITIONALLY** — 142 of 322
  instructions can reach `0x055B85C1` and **ZERO edges leave that set** (sound backward
  reachability). **And BOTH flagged branches target `0x055B85B4`, which is 13 bytes BEFORE the Super
  call and falls straight into it — they skip a LOOP, not the Super.** Reading
  `[CharacterOwner+0x580] & 8` live would have settled nothing. That was the handoff's #1 ranked move.
  **(b) [M] it HAS been read** — S139 flight 3 measured `bSimulatePhysics == 0` (with
  `bEnableGravity == 1` from the same byte as a two-sided decode control) and
  `WeldParent @capsule+0x5F0 == NULL`, and `docs/next-session-prompt-s140.md` §0b itself says
  "ASKED AND ANSWERED". **The gate passes.** ⚠ Also, the handoff said *"three gates"*; the measured
  count is **five mandatory plus a non-mandatory sixth**. A digest-is-an-instrument instance: the
  settled S139 docs were right and the compressed handoff line was stale.
  ★★★★★ **DONE AT S140 TIER 2 — AND THE HANDOFF’S RECIPE WOULD HAVE RETURNED A FALSE NEGATIVE.
  Read `docs/s140-tier2-sentinel.md`; its §3 and §5 govern.** Two staged clients, two injections.
  **[M] `ULokiCMC::StartNewPhysics 0x055C2430` RUNS on both components, essentially every frame.**
  ⚠⚠ **THE SENTINEL-ONLY DESIGN IS DEGENERATE and Tier 1 §7 says so** — with `Velocity` resting at
  `(0,0,0)` and `NewObject` zero-filling, "snapshotted a zero" and "never written" are THE SAME
  BYTES, which is why S139 already banked `R1.velsnap@0x16B0 (0.000,0.000,0.000)` and it means
  NOTHING. **The fix is to PRE-POISON the payload** with a distinctive value first: that breaks the
  degeneracy WITHOUT touching `Velocity`, and the poison is provably unreachable by any consumer
  (its only reader `GetRecentVelocity` returns it solely when the flag at `+0x16C8` is non-zero, and
  the only writer of `flag=1` overwrites the payload `0x1A` bytes earlier in the same block).
  MEASURED: both poisons overwritten within **250 ms**, on the bot AND on a **velocity-write-free**
  player arm; neither payload ever held the other object’s poison (a two-sided addressing control
  that could have failed). Flight 2’s 2 ms burst then caught the payload holding a `Velocity`
  sentinel **396/400**, refuting the one alternative (a non-`StartNewPhysics` writer of `+0x16B0`).
  ⚠⚠⚠ **AND IT NEEDED NO EXTERNAL `WriteProcessMemory`** — the write is in-process on the game
  thread, which sidesteps that hazard entirely. **But the READ CANNOT HAPPEN IN THE ARM: [M]
  `BsLadderStep` runs ON THE GAME THREAD inside `OnPI`, so every `Sleep()` in it BLOCKS THE GAME
  THREAD AND NO FRAMES PASS.** A write-Sleep-read there is *guaranteed* to read the un-updated
  payload and would have been written up as "StartNewPhysics does not run". ★ Sample on the
  **existing Worker thread between `FsDisarm()` and `BsFinalReport()`** (the `RM_DROPPLANE` B4
  precedent) — no `CreateThread`, and `[BS] done` stays last in the marker.
  ⚠⚠ **A worker thread spawned INSIDE the arm also fails**: the ladder holds the game thread for a
  further ~4.4-5.2 s after `BsPsExperiment()` returns (trailing `Sleep(750)` + the A2 census).
  ⚠⚠ **AND THE `[M]` THAT MOTIVATED ALL OF THIS IS AN INSTRUMENT ARTIFACT:**
  `tutorial_launch.cpp:15883`’s *"one hit is all this world state delivers (hitsGT=1)"* is
  self-inflicted — `OnPI` increments `g_hitsGT` AFTER its `if(g_done||g_inHook) return;`, so a
  one-shot ladder can never report more than 1 whatever the dispatch rate. Control:
  `docs/fk24-s128-poolspawn-RESULT.txt`, identical `KFSNAME=""` and identical `swapped=17563` but a
  PACED ladder — **`hitsGT=588`, ~73 dispatches/s.**
  ★★★★★ **AND THE WHOLE PER-EXIT GRADING EXERCISE IS SUPERSEDED, IN THE FAVOURABLE DIRECTION: all
  SIX exits of engine `PerformMovement` are now proven PASSED BY DIRECT OBSERVATION**, because the
  call they all guard demonstrably executes. That is strictly stronger than reading any individual
  gate input, and it does not depend on a single offset being right.
  ★★ **THE THREE FREE READS ARE ALL TAKEN, and reproduce across two clients [M]:**
  **`CMC+0xC0 WorldPrivate` is NON-NULL and names `LVL_Tutorial`** ⇒ engine `PerformMovement` exit 2
  moves **[I,strong] → [M]**; **`CMC+0x3E4 MaxSimulationIterations = 1`** (>0, so the fourth engine-
  `StartNewPhysics` early-out at `0x036009B5` does NOT bail) and **`CMC+0x3E0 MaxSimulationTimeStep
  = 0.2`** — ⚠ **NEITHER is the stock UE default (8 and 0.05); both are overridden in this build**,
  and a one-iteration substep budget is a real constraint recorded nowhere else; and the live
  **vptr == `base+0x088F8570`** on both ⇒ it really is a `ULokiCMC`, so disp `0x720` really is
  `0x055C2430`. ⚠ Had it been the engine base, disp `0x720` is `0x03600990` and nothing touches
  `+0x16C8`/`+0x16B0` — the whole test would have been void; the probe checks for exactly that.
  ★★★★★ **⇒ THE WALL IS NOW DOWNSTREAM.** ⚠⚠ **BUT QUALIFY THE SECOND HEADLINE: "`Velocity` is
  actively written to zero every frame" IS WEAKER THAN IT LOOKS.** Both flights put the sentinel
  there themselves, and an adversarial verifier established a mechanism by which **a small non-zero
  `Velocity` CONVERTS A NO-WRITE INTO A WRITE** — below tolerance the three `ucomisd` at
  `0x055B8838/3E/4A` all fall through to `je 0x55B8865` and **the write is SKIPPED**; and in engine
  `PhysFalling`, `2^-10` gives `SizeSq 9.54e-07` (`0x035ED9B3 call 0x035F4620`) after which
  **`0x035ED9BB movups [rsi],xmm0` + `0x035ED9C3 movsd [rsi+0x10],xmm1` write `Velocity`** on the
  `<= 1e-3` arm. ⇒ **[M] something writes the BOT `Velocity` once it holds a small non-zero value;
  NOT ESTABLISHED that anything writes it when it is EXACTLY ZERO.** The `StartNewPhysics` result
  is UNAFFECTED — it rests on the POISON being overwritten, and the PLAYER arm is entirely
  velocity-write-free. ★★ **This may make the standing null a FIXED POINT (zero ⇒ no write ⇒ stays
  zero), a much simpler wall than a routine that computes zero — and it NAMES A CANDIDATE SITE
  (`0x035ED9BB`/`0x035ED9C3`, engine `PhysFalling`).** ⚠ Whether `0x035ED98E` is reached on a given
  frame is NOT established.
  ⚠⚠⚠ **AND THE OBVIOUS CANDIDATE IS [S], WITH THE EVIDENCE LEANING AGAINST IT — do not lead with it.**
  An offline lane transcribed `CalcVelocity`'s input clamp: `0x035D64F2 comisd` vs **`1.0e-4`**
  (`.rdata 0x076B49E8`) → `0x035D6520 movups [rbx+0xe8], ZeroVector` + `0x035D6527 movsd [rbx+0xf8]`,
  writing **`Velocity := (0,0,0)` every frame whatever `Acceleration` is**. ★ The attribution is
  PROVEN — `preds(0x035D6511) = { 0x035D650F }`, exactly one predecessor, so that store is uniquely
  reached from the INPUT clamp (a second, nearly identical *requested* clamp exists at `0x035D668E`).
  **BUT ITS OWN ADVERSARIAL VERIFIER REFUTED THE APPLICATION [M, derived]:** `GetMaxAcceleration`
  (disp `0x7D0`) and `GetMaxSpeed` (disp `0x4C8`) are **both GAS-backed through the SAME `+0xC00`
  slot** (`0x055AC9F0`, base value `min(AttrSet+0xF0+0xC, AttrSet+0x100+0xC)`), behind the same
  guards; S139 flight 4 measured `GetMaxAcceleration() = 50000`, so that slot returned NON-ZERO and
  all three zero-guards passed ⇒ `GetMaxSpeed() != 0` ⇒ `MaxInputSpeed >> 1e-4` ⇒ **the clamp did
  NOT fire.** And `ComputeAnalogInputModifier` (disp `0x660` → `0x035DB6F0`, NOT Loki-overridden)
  returns ≈1.0 when `|Accel| ≈ MaxAccel` — **measured = 1 on the treated bot.**
  ⚠⚠ **THE VERIFIER'S OWN CONCLUSION IS SUPERSEDED TOO** — it inferred *"flight 4's null points
  upstream, at the step not running"* from S139's then-current belief, and **Tier 2 measured that
  the step DOES run.** ⇒ **EITHER (a) another `Velocity`-zeroing site exists on this path, OR (b)
  step 3 is wrong because the two getters pass DIFFERENT attribute selectors to `+0xC00`** — and
  (a) is likelier, since the two getters demonstrably return DIFFERENT numbers (50000 vs the 500
  ARM G wrote to `MoveSpeed`/`MaxMoveSpeed`) and so cannot be selecting the same attribute.
  ⚠⚠ **AND "the wall is ONE compare" IS WRONG ON THE COUNT: `CalcVelocity` is called up to FOUR
  times per `PhysFalling`** (`0x035ECB75`, `0x035ECBD8`, `0x035ED549`, `0x035ED5D5`) and
  `NewFallVelocity` (disp `0x7A0`) THREE times. ★ **[M] `ULokiCMC::PhysFalling 0x055B89F0` calls its
  engine Super UNCONDITIONALLY** (|R| = 14, entry in R, exit edges EMPTY) — which **REFUTES
  `docs/s140-tier1-cfg.md:622`**; **`CalcVelocity` is disp `0x7B0 = 0x035D5D20`, NOT Loki-overridden**;
  and **`GetGravityZ 0x055AB8C0` (disp `0x4C0`) and `NewFallVelocity 0x055B6AD0` ARE Loki overrides**
  — ★ **read `GetGravityZ` first**: a `MOVE_Falling` pawn with `GravityScale 1.000` that does not
  fall is a standing unexplained phenomenon, and a zero return would explain it and the zero
  `Velocity` together, in one function read.
  ★ **Everything on this path is LIT in `merged13` today** (verified S140 T2) ⇒ **no coverage
  blocker; MOVE 2 is entirely offline.**
  ⚠ **NOT OBTAINED: `CMC+0x290` was never read** — the probe was written and the client died (FK-32)
  before it ran. It is now wired into `tools/re/cmc_earlyout_readout.py`, so **S141’s first move is
  ONE READ-ONLY RPM RUN against a staged client, with NO injection at all.** The probe prints the
  disjunction rather than a verdict: **`MinAnalogWalkSpeed >= 1e-4` ⇒ the `max()` cannot fall below
  `1e-4`, so this clamp is NOT what zeroes `Velocity` and the lane’s headline is REFUTED;
  `< 1e-4` ⇒ the whole question reduces to what `GetMaxSpeed()` returns on a treated bot.**
  ⚠ **Both S140 T2 clients died of FK-32** (`0x0000DEAD`, no artifact) at **T+350.5 s** and
  **T+318.0 s**, both on the **4th** manual-map. The `0xDEAD` series is now **7 / 6 / 4 / 4 / 4**
  injections at 1144 / 334 / 350 / 318 s — **still no dose-response**, but 4 is now the modal count.
  ★ Nothing was lost to either death: every result was captured as produced. **Capture as you go.**
  **Arms** (RAW): `gasattr-sentinel` **`ce56fd715de835a1`** (flight 1) · `sentinel-burst`
  **`62b5423febd6f779`** (flight 2) · `sentinel-nogas` `f62d3a9cc4cf0562` (built, unflown).
  Regression gates `botai 5e47c13cf7f0a158`, `gasattr 2fcc2536e21f18e3`, `gasattr-ctrl
  4465ebc4d7168c03` **all reproduce EXACTLY** from the edited source.
  ⚠⚠ **`driverecompute a2a952babfed256b` IS NOT A VALID GATE.** `build.ps1` gives `driverecompute`
  `-DKBSPSARMS=0xA0` and `gasattr-ctrl` `-DKBSPSARMS=0x0A0` — the SAME VALUE — so from one source
  state they must be byte-identical, and today both build to `4465ebc4d7168c03`. The archived DLL
  has a different `.text` SIZE (134,144 vs 134,656) ⇒ it predates a source change and was never
  rebuilt. `text_digest.py --dupes` independently flags the pair as a HAZARD. Same pattern as
  `botspawn_readonly`.
  ⚠⚠ **AND AN `#else` "ARM H skipped" MARKER LINE MOVED `gasattr` `2fcc2536e21f18e3` →
  `6d81e34e675f97f1` WHILE LEAVING ITS `.text` SIZE AT 137,728 BYTES** — the repo’s own "diff the
  hash, never the size" rule demonstrating itself. **A skip message compiled into the CONTROL builds
  is not free.** Put arm code behind a PREPROCESSOR `#if`, with no `#else`.
  ⚠⚠ **`cmc_earlyout_readout.py`’s `RANK-1 VERDICT` block printed the RETRACTED latch inference**
  and would have handed a successor a confident wrong answer. **Fixed** — it now prints the
  retraction plus a payload recogniser, raw hex of both 24-byte ranges, and the free reads.
  ⛔ **The write-free variant is FORECLOSED:** `GetRecentVelocity` is reflected and the S55 primitive
  could call it with zero writes, but with `Velocity == (0,0,0)` **both arms of its `cmove` return
  `(0,0,0)`**, so it cannot discriminate.
  ⛔ **And there is NO free log receipt on this path** — [M] the only three `LogCharacterMovement`
  sites reachable here are the `IsSimulatingPhysics` abort (`.rdata` record `0x07FC0648` → string
  `0x07FC0670`, verbosity **5 = Log**, line 3477 — fires only when the gate FAILS, and it passes),
  an unsupported-movement-mode **Warning** (record `0x07FC0740`, line 3510 — mode 3 is in range), and
  a root-motion-only Log in `PerformMovement` (record `0x07FC0548`, line 2919). Engine/Loki
  `TickComponent`, `ControlledCharacterMove` and Loki `PerformMovement` contain **zero** `.rdata`
  references of any kind. **So S139's "pin `LogCharacterMovement=Log` and the whole question becomes
  a per-frame log line" does not work as stated.**
  ★★ **BUT the same work yields the positive control S139 correctly said was missing:** the
  `LogCharacterMovement` category object is at **`.data 0x9F85E68`** [M, two agreeing derivations —
  the gate `0x036009EE cmp byte [rip+0x6985473],5` and the logger call's own
  `0x03600A28 lea rcx,[rip+0x6985439]`], and `FLogCategoryBase.Verbosity` is at **offset 0**.
  ⇒ **one read-only RPM byte tells you whether the category is suppressed** — reusable for every
  "category X is silent" question in this project. ⚠ Read it live or from a single-state dump, never
  from `merged13`'s spliced `.data`.
  **Probe: `tools/re/cmc_earlyout_readout.py`** (read-only; 10 ranked fields, two mandatory identity
  controls). **New instrument: `scratchpad/s139/ticksniff.py`** — decodes `FTickFunction`
  (`UActorComponent::PrimaryComponentTick` **IS a UPROPERTY at +0x40**; `AActor::PrimaryActorTick`
  at `+0x38`), 22 passing offline controls.
  ⚠⚠ **TWO PROBE DEFECTS, EACH OF WHICH READ EXACTLY LIKE A GAME FACT:** `fname` read the FNamePool
  block table at `NAMEPOOL + 0x10 + 8*blk` (correct: **`NAMEPOOL + 8*blk`**) ⇒ every name decoded `?`
  ⇒ the probe printed **"NO PLAYER-CONTROLLED PAWN — RUN IS VOID"** on a healthy client; and
  `findprop` read an `FField`'s name at `+0x28` (correct: **`+0x20`**, same as a `UObject`) ⇒ every
  by-name lookup failed ⇒ **"no `CharacterMovement` UPROPERTY"**. ★ **Both were localised in minutes
  by running the known-good `tools/re/movementmode_readout.py` against the same live process as an
  INSTRUMENT CONTROL.** Keep a second, already-trusted instrument on hand.
  ⚠ The pre-registration (`docs/s139-f1-PREREGISTERED.txt`) is what kept this honest: P2 said a
  player latch of 0 makes the bisector **uninterpretable**, and it read 0 — so the bot's 0 was NOT
  taken as a result until the polarity was re-read from the bytes. Without P2 it would have been
  written up as "S2 confirmed", and S2 is false.
  ★★★★★ **AND S140 SHOWED P2 WAS RIGHT FOR A DEEPER REASON THAN ANYONE KNEW — the latch is
  uninterpretable in EVERY sitting, not just that one.** See the S140 block below.
- ★★★★★ **S140 (2026-08-23) — OFFLINE, ZERO LAUNCHES. THE PHYSICS-STEP "CONTRADICTION" DISSOLVED:
  THE SIX EXITS ARE COMPLETE AND EXACT, AND THE INSTRUMENT THAT POSED THE QUESTION IS INVALID.
  Read `docs/s140-tier1-cfg.md` (844 lines); its §4 and §5 govern.**
  13 agents (6 analysis lanes, 6 adversarial verifiers, 1 adjudicating synthesis) plus the session
  lead working the same image in parallel. **No launches, no injection, no `.text` writes, no live
  process touched.**
  ★★ **[M] THE SIX SURVIVE — exactly, no additions, no subtractions**, reproduced by FOUR
  independently written CFG instruments: 1461 instructions, 148 calls, **0 indirect jumps, 0 decode
  failures, 0 coverage gaps (6538/6538 bytes), exactly 2 backward edges and NEITHER in `R`**,
  `|R| = 1075`. **Five of the six DOMINATE the call.** The motivating worry — that the
  `target > call` predicate was blind to a backward bail — is measured moot here.
  ★★★★★ **[M] THE LATCH `CMC+0x16C8` IS NOT A LATCH.** Cleared at the tail of every completed
  `PerformMovement` by `ULokiCMC` vtable disp `0xA50` = `0x0530ABF0`, called at `0x035EB569`.
  **Named from its own consumer: `GetRecentVelocity` (`.data 0x09BC9AD0` → impl `0x0530AC10`) makes
  it a per-frame `TOptional<FVector>` validity flag over the Velocity snapshot at `+0x16B0`.**
  ⇒ every S139 conclusion resting on it is **UNGRADED, not negative**. Full retraction above.
  ★ **THE FULL CALL CHAIN IS NOW VERIFIED HOP BY HOP with sound exit analysis** — Loki `TickComponent`
  → engine `TickComponent` (**0 exits**) → `ControlledCharacterMove` (9, all proven passed by
  observation) → engine `ControlledCharacterMove` (**0 exits**) → `PerformMovement` (**exactly 1**
  exit, `CharacterOwner->Role(+0x160)==3`, measured 3 **on the provably same object**) → Super
  (**0 exits**) → `StartNewPhysics` (the six). **Every hop is unconditional or measured-passing.**
  ⚠ Note what the `Acceleration` signed-zero proof does NOT cover: the store at `0x035DCD6B` is
  **upstream** of the Role gate, so it proves the function ran to there, not that `PerformMovement`
  was called. The chain needs both facts, not one.
  ⚠ **NEW GAP nobody had noticed: `CMC+0xC0 WorldPrivate` — exit 2's input — has NEVER been read
  live.** Grade exit 2 **[I, strong]**, not [M].
  ⚠ **NEW: engine `StartNewPhysics` has a FOURTH early-out** `0x036009B5 cmp r8d,[rcx+0x3e4] / jge`
  (`MaxSimulationIterations`) and a **third** `HasValidData` at `0x036009C5` — in no prior document.
  ⚠ **INSTRUMENT DEFECT WORTH KEEPING: capstone 5.0.7 reports `movups` STORES as reads** via
  `regs_access`, silently hiding 16 CMC-field stores — including `0x055C244F`, the very payload
  receipt S141 is now told to use. **Classify writes from `operands[0].type == MEM`, never from
  `regs_access`.**
  ⚠ **A SECOND ONE, mine:** a scan for rip-relative `lea`s into `.rdata` returned **0** for engine
  `StartNewPhysics` **with a passing positive control**, and I nearly recorded "the log literal is
  never referenced". **UE `lea`s a LOG-RECORD STRUCT whose `+0x00` points at the string.** ★ The rule:
  *a positive control validates the mechanism it exercises, not the question you are asking.*
  ⚠ **`pdata_union.csv` has NO row covering `0x055C2430`**, so a pdata-seeded census misses
  `ULokiCMC::StartNewPhysics` entirely — my first `+0x16C8` census failed its own positive control
  for exactly that reason. Seed from the **vtable** as well.
- ★★★★★ **THERE ARE **TWO** `.text` DIGEST RECIPES ON DISK AND THE REPO USES BOTH (S136).**
  **RAW** = `sha256(.text[PointerToRawData, +SizeOfRawData))[:16]` — `configs/fk24-stage.ps1:77
  Get-TextHash` (prints only inside a stale-shim abort) and **`configs/fk7-ab-run.ps1:94`, which
  EMITS it at :131 into the A/B CSV column `probe_text_sha`**.
  **VIRTUALSIZE** = `sha256(.text[PointerToRawData : +min(VirtualSize, SizeOfRawData)])[:16]` —
  already written down at **`docs/method-rules.md:213` (S134-d)**, whose four quoted outputs
  recompute 4/4. They differ only in the file-alignment tail.
  ⚠⚠ **RETRACTION — S136 FIRST PUBLISHED *"the four S135 bot digests appear NOWHERE in the
  repo"*. THAT IS FALSE.** All four are recorded (this file, `docs/s135-queue-arms-a-match.md`,
  `docs/next-session-prompt-s136.md`), and **the VIRTUALSIZE recipe reproduces `botspawn
  e48c90bc6cf17c93` and `botteam 0c16652dc0338d33` EXACTLY** from today's binaries. The error came
  from a `grep -rl` over `docs/` that **TIMED OUT at 2 minutes**, whose partial output was then read
  as a negative — the instrument-artifact pattern again. **Scope your greps and check the exit
  code.**
  ★ **NEW [M]: `botspawn_readonly` matches NEITHER recipe today** (raw `319ac875af229f46`, minVS
  `d96480ad64c1a403`, recorded `f5f9896feeac45dc`) ⇒ **that artifact has changed since its gate was
  recorded.** Re-record it before using it as a control.
  ⛔ **"9/9 verbatim" WAS A SELECTION EFFECT.** Honest: **48/87** `tutorial_launch_*.dll` and
  **55/132** corpus tokens under RAW; **6** VirtualSize-only; **0** for whole-file sha256/md5/sha1.
  `cheatmgr`'s own table here matches **1 of 4**.
  ⚠ **"Canonical" is a DECISION, not a measurement.** ≥4 artifacts (`play`, `dismount`,
  `dropplane_b1only`, `droppod_pe_cdopoke`) have BOTH digests recorded in different files as the
  same gate, so declaring RAW canonical **silently invalidates six recorded gates — say which**.
  ⚠ **Degenerate case:** any DLL with `VirtualSize == SizeOfRawData` cannot discriminate the two
  recipes. Check per file before citing a match as recipe evidence.
  ★★★★★ **AND THE DUPLICATE SWEEP FOUND TWO DEGENERATE CONTROL ARMS — ARMS THAT MEASURE NOTHING
  (S136).** `python tools/sigbypass-mod/text_digest.py --dupes tools/sigbypass-mod/build` reports
  **0 unexplained-hazard duplicate groups** but flags **`play` ≡ `play_nopimutex` ≡
  `play_strictroot`** under BOTH recipes, and the cause is mechanical, each with a PASSING POSITIVE
  CONTROL:
  • **`play-nopimutex` has been inert since S112** — `KPIMUTEX` guards `HookLock()`, reachable only
    via `InstallHook()`, and RM_PLAY has not installed the PI hook since `KFUNCSWAP` became the
    default, so `InstallHook` is dead-stripped. Control: the literal `SuperviveMissionsPIHook` is
    present in exactly the **11 of 87** `tutorial_launch` variants whose run mode calls
    `InstallHook`, and absent from all three of these.
  • **`play-strictroot` has been inert since S123** — `KGCROOTSTRICT` selects between two arms of a
    function only reached when `KGCROOT != 0`, and `KGCROOT` has **defaulted to 0 since S123**.
    Control: the label literal `FREQ` is present in `play_gcroot` and absent from both.
  ⇒ **DO NOT FLY EITHER AS A CONTROL — they are byte-identical to `play` and settle nothing.**
  ⚠ Separately, several `*_cdoctrl` "control" arms are byte-identical to their plain build because
    the knob already DEFAULTS to the control value (`poolspawn` ≡ `poolspawn_cdoctrl`,
    `droppod_pe` ≡ `droppod_pe_cdoctrl`, `ds_hybrid` ≡ `ds_hybrid_spectator`). **The real A/B pair
    is `cdopoke` vs `cdoctrl`, which DO differ.** Expected, documented in `build.ps1` — but a
    successor reading only the arm NAME would think it flew a control.
  ⚠⚠ **THE DIGEST IS NOT AN ARTIFACT IDENTIFIER TODAY, AND THE "A/B AGAINST A COPY OF ITSELF"
  HAZARD IS LIVE:** `play` / `play_nopimutex` / `play_strictroot` share `9bc10a4552c596e1`;
  `poolspawn` / `poolspawn_cdoctrl` share `85f3cee44c31b1cd`; `droppod_pe` / `droppod_pe_cdoctrl`
  share `61fd0745c23e89f0`. **Any digest tool must flag duplicate digests across differently-named
  variants.** `tools/sigbypass-mod/text_digest.py` (new) implements both recipes.
  ⚠⚠ **ROOT CAUSE OF THE "no recipe on disk" ERROR IS A BROKEN POINTER IN THIS FILE** — it directs
  readers to *"`verify_dll.py` or the section-hash snippet in `docs/s109-dump-forensics.md` §23"*,
  and **`verify_dll.py` contains no hash code and §23 contains no snippet.** Two sessions followed
  it, found nothing, and concluded none existed. **Fix that line.**
  ⚠⚠ **AN EDIT THAT DOES NOT MOVE `.text` IS AMBIGUOUS** (cached build vs semantic no-op). Insert a
  deliberately observable marker string to separate them.
  ⚠⚠ **`strings` IS NOT INSTALLED ON THIS MACHINE.** It returns silence for every token in every
  file, which reads exactly like a negative. Use a python byte scan and **always include a positive
  control** (`KERNEL32` reading 0 is what exposed it).
  ⚠ **`build/` is gitignored and three S136 builds overwrote each other.** Only source-
  reproducibility (`git show HEAD:` + unmodified `build.ps1`) recovered the flight-1 artifact.
  **Archive every A/B arm before rebuilding.**
  ⚠ **`dumps/s133-phase2-{BASE,AFTER}` ARE MIS-NAMED — audited S136, and it is a FILENAME DEFECT
  ONLY.** The mtimes are inverted (AFTER `19:19:53` predates BASE `19:32:48`) and the CONTENT agrees:
  AFTER **15,459** non-zero `.text` pages vs BASE **15,512**, with **only-AFTER 0 / only-BASE 53 /
  0 byte conflicts** ⇒ AFTER is a strict SUBSET, so "BASE" is genuinely the later capture.
  ★ **But NO published S133 conclusion is wrong**: `0x5879000` is LIT in **both** images (3,861
  non-zero bytes each), so the S133 DARK→LIT headline cannot have come from this pair — it came from
  the CANCEL→phase2 diff (16 new, 0 lost). A named-direction diff on this pair yields **0 new /
  53 lost**, and `text_page_diff.py:54` does surface the `ONLY-BASE` column, so the loss is visible.
  ⚠ Do not restate this as "the before/after-diff method is threatened" — it is not; the labels are.
- ⚠ **Nothing matches the player**: the queue is answered by no matchmaker. And FK-15's S118 map
  measured **`matchmakingNotif` as UNBOUND**, so there is no push route — a match-found signal has to
  be HTTP.
- ★★★★★ **EMOTES WORK — VISIBLE, EQUIPPABLE AND PLAYING IN THE LOBBY (S133).** The recipe is
  **BACKEND + THE EXISTING `catalog_store_fix.dll`**, and it took three refuted hypotheses to find:
  (1) `Emote:<Name>` inventory entries with `IsOwned=true`, (2) matching storefront ItemOffers
  (`Category: "Emotes"`), and (3) **the shim's AssetManager scan**. Knob **`AGS_GRANT_EMOTES`**
  (`1` = all 331; default empty = byte-identical to pre-S133). Names in
  `server/internal/menu/data/emotes.txt`, read LIVE from the client's own FNamePool by scanning
  interned `/Game/Loki/Personalization/Emotes/<Name>/` paths — the registry the game ships, not a
  guess (the missions `InternalName` lesson).
  ★★ **WHY THE SHIM IS REQUIRED HERE AND NOT FOR SKINS/GLIDERS/SPRAYS — the asymmetry is the whole
  answer:** `ULokiAssetLoader` has maps for `HeroAssets`, `HeroCosmeticsBundleAssets` (391),
  `SlotCosmeticsAssets` (536), `StoreOfferAssets`, `LoginRewardAssets`, `MissionPoolAssets`,
  `EquipmentAssets`, `PowerAssets` — and **NO `EmoteAssets` map.** So emotes are exactly the
  cosmetic type that cannot be enumerated without the AssetManager scan. Those other tabs populate
  fine on a `-NoHook` client; emotes never will.
  ⚠⚠ **AND THIS CORRECTS `cosmetics.go:13`,** which says the STORE's ACCESSORIES tab covers
  *"Gliders/**Emotes**/Wisps/Sprays/Avatars"* as type `SlotCosmetics`. **MEASURED: the live 536-name
  SlotCosmetics map contains ZERO emotes** (prefixes are AVATAR 225 / SPRAY 146 / GLIDER 115 /
  WISP 40 / SPIKEVFX 2). **`Emote` is its own PrimaryAssetType** — confirmed three ways: the shipped
  mastery-reward DAs use `"SKU":"Emote:SeraphHi"`, the picker widget
  `WBP_UI_Loadout_Customization_Emotes`'s own asset name table contains bare `Emote`, and its
  ubergraph calls `WBP_GenericCatalogPicker.SetContentTypeAndPrefix(prefix="", <"Primary Asset
  Type">)`.
  ★ **THREE HYPOTHESES WERE REFUTED BY MEASUREMENT before the right one:** inventory ownership alone
  (331 served, client refetched, picker empty); storefront offers as the missing half (served AND
  fetched **3×** by the game UA, still empty); the content manifest hiding them (it is queried
  `?nonEnabledOnly=true` and we return `Emotes: {}`, so they were already enabled). **Each null was
  interpretable only because the client was verified to have CONSUMED the document first.**
- ★★★★★ **THE LOBBY-EMOTE WIRE SHAPE [M]: `POST /party/parties/{p}/emote/Emote:<Name>` — the id is
  the PATH TAIL as a full PrimaryAssetId, and the BODY IS ALWAYS EMPTY.** Emotes play with the party
  document echoed unchanged, so no new field is needed for a solo party.
  ⚠⚠ **The six earlier POSTs that arrived as bare `/emote/` with an empty body were NOT a mystery
  payload — the account owned no emotes, so the client had nothing to name.** The handler was built
  as a *body*-logger on the wrong premise and still produced the answer, because it logged the TAIL
  too. ★ **Log every input channel, not the one your hypothesis names.**
- ★★★★ **PHASE 2 ALSO LANDED — `0x5879000` DARK → LIT, and it found TWO MORE UNSERVED ENDPOINTS:**
  `POST /party/parties/{p}/emote/` (×5, **`TrySendEmote`**) and `POST /party/parties/{p}/setIsOpen/True`
  (×1, **`TrySetIsOpen`**), both still on the `/` catch-all. Note the value-in-path URL shape.
  ⇒ **THREE endpoints in one afternoon of driving the UI**, on a surface a passive sweep had declared
  mapped. ⚠ That phase's baseline was CONFOUNDED (an `ags` restart + `AGS_PROBE_FRIEND` sat between
  baseline and result); the page verdict survives only because **the wire attributes it by name** and
  7 plausible-alternative control pages stayed DARK. **13 of UPartyManager's 20 dark impls are now
  readable** (`merged7` 16,707 → `merged8` **16,714**, 55.20 %).
  ⚠ `TrySetFillPreference` / `TrySendInvite` / `TrySendRequest` / `TrySetIsReady` produced **no
  traffic** and are NOT shown to have run — no reachable affordance in a solo party.
- ⚠ **No CUSTOM GAME entry point exists on this client** (`customGameModes` is served and
  `CustomGameList` is `IsEnabledByDefault=true`, so it is NOT toggle-gated — the entry point is
  elsewhere and unidentified). `UPartyManager`'s 7 custom-game impls on `0x5873000`/`0x5874000` and
  ~~the 6 ready/fill/emote impls on `0x5879000` remain **DARK and unreached**~~ ⚠ **STALE since
  `merged10`: page `0x5879000` = 3,861/4,096 = LIT -- and it is contradicted 13 lines above in this
  same file (`0x5879000` DARK -> LIT). "Unreached" was never re-checked after the page lit.**

### Before touching anything coverage- / dump- / "that page is undecrypted"-shaped
★★★★★ **FK-20 IS SETTLED (S133, 2026-08-20) — read `docs/fk20-coverage-settled.md`.** Offline, zero
launches. FK-20 was recorded as *"9 menu captures and 0 gameplay captures"* with the prescription
*"capture hero select / drop / a live match / EoG."* **The capture side is SATURATED; the defect is
that COVERAGE IS EARNED AND NEVER SPENT.**
- ★★★★★ **BEFORE BELIEVING ANY "this page is dark / coverage-blocked / 100 % zero in every dump"
  CLAIM, RE-GRADE IT.** **31 such lines in `CLAUDE.md` + `docs/` name an address that is READABLE in
  `merged6` today — and ~29 were already stale against `merged2`.** They never needed a new capture,
  only someone to look. `python scratchpad/s133/tools/regrade_blocked.py` re-runs the audit; full
  list in `scratchpad/s133/evidence/dark_cited_functions.txt`.
  ★★ **RE-RUN AT S137 (against `merged13`): 43 adjudicated stale claim-instances across 15 files and
  14 distinct RVAs** (unit: file:line × RVA pairs, not files and not lines), independently
  reproduced row-for-row by an adversarial pass. **Only 3 first went stale in `merged13`; 29 have
  been stale since `merged10` and 6 since `merged2`** — i.e. the problem is almost never a new
  capture, it is that `regrade_blocked.py` HAS ALREADY BEEN EMITTING THESE AND NOBODY EDITS THEM.
  ⚠ A lane claimed three were "never flagged by any prior audit"; **REFUTED** — the S133 tool emits
  all three verbatim. **Four sat in `CLAUDE.md` itself, two contradicting this file elsewhere**;
  all four are now annotated in place (`0x556D910`, `0x5879000`, the `0x5873280`–`0x5879EE0` band,
  `0x5456000`). ⚠ The sweep is a **FLOOR**: 294 of 431 keyword lines carry no same-line address and
  were never graded at all.
- ⚠⚠★ **AND A COVERAGE NEGATIVE CONTROL IS ONLY VALID UNTIL SOMETHING ON ITS *PAGE* RUNS — WE KILLED
  ONE OURSELVES (S137).** `docs/fk22-dropphase-reachability.md` designated
  `ALokiGameState::AuthSetDeathCircle` impl `0x55653E0` as FK-22's coverage negative control
  ("0/4096 in 13/13 images"). It shares page `0x5565000` with `ALokiBotController::OnPossess`
  `0x5565470`, **0xB0 bytes away**, so S137's bot flight decrypted it as a side effect: it now
  reads **3,782/4,096** with a real `jmp 0x338C990` at its entry. Nothing about the drop path
  changed. ⇒ **choose a control on a page with no plausible neighbour, re-verify it before each
  use, and state which image you verified against.** ✅ Still-dark in `merged13` (measured
  2026-08-21): `ULokiRespawnComponent::Respawn 0x5A6AC40`. ⚠ A SECOND control was independently
  broken: `docs/fk-playability-audit-s134.md` offers `0x5A6AC40` **or** `0x556D910` — but
  `0x556D910` (SpawnBot) has been LIT since `merged12`. **Use `0x5A6AC40` alone.**
- ⚠⚠ **AND CHECK THE CALLEE BEFORE RECORDING COVERAGE BLINDNESS.** `docs/fk5-battle-gate-settled.md:664`
  states `[M]` *"`0x1F8CFC0` is an all-zero page, so **the packet format is unreadable offline**"* and
  builds a whole hexdump-responder plan around it. `0x1F8CFC0` is a ~300-byte **wrapper** that reads
  `[Ping] StackSize`, names a thread from the ANSI literal **`"LokiPing"` `0x79C6E80`** and tail-calls
  the real worker **`0x1F8BE90`** — **which is LIT in `merged.dump.exe`, `merged2`, `menu`,
  `tutorial-hero`, and every image this project has ever taken.** The packet-building code was never
  dark. ⇒ **the open task "a UDP echo responder on `PingHost:PingPort`" can read the format offline
  today** from `0x1F8BE90` + siblings `0x1F8BB50`/`0x1F8B870`/`0x1F8B4F0`, all LIT. Same failure as
  `fk22-dropphase-reachability.md:675` (COVERAGE-BLOCKED filed on a zero **thunk** whose impl was
  decrypted), recommitted in a different file.
- ★ **The wrapper itself went dark→lit on 2026-08-15 = S121**, the session that first created a
  `ULatencyMeasurer`. **Driving a path decrypts it (S118's steerable decryption); nobody re-graded.**
- ★★ **QUOTE THE PER-SUBSYSTEM BLINDNESS, NEVER THE IMAGE-WIDE 45 %.** In *functions*: **~9.4 %
  blind on shared engine/UI/core, 20.9 % on gameplay/net/AI, 54.7 % on Angelscript.** The image-wide
  number is dominated by code no state can reach and understates blindness where it matters.
- ★★★★★ **67.91 % OF THE DARK SET IS UNREACHABLE BY ANY GAME STATE** (9,231 of 13,592 pages,
  36.06 MiB): **UE's own Chaos ISPC-compiled collision kernels**, multi-ISA-target so ~2/3 is
  unreachable *on this CPU by construction* (26.6 % of dark, but only **0.4 % of dark FUNCTIONS** —
  quote the unit); editor/authoring modules with no entry point in a packaged client (PCG,
  MeshModelingTools, Sequencer, MovieRenderPipeline); and third-party libs (ICU 64, OpenEXR, OpenSSL,
  Oodle, libwebm, crashpad). **The reachable ceiling is 4,361 pages = 32.09 % of dark = 17.04 MiB**,
  and that assumes a match runs every line of every gameplay module.
  ⚠⚠ **A first draft of this line said "73.4 %, 9,984 pages, 39.0 MiB" — ARITHMETIC ERROR, and it
  flattered the conclusion.** `3613+2357+1845+1416 = 9231`; the two complementary shares as first
  stated summed to **105.54 %**. `9231 + 4361 = 13592` exactly. ★ **Two shares of one whole that do
  not sum to 100 % is a free self-check — run it before publishing either.**
  ★★ **"Region A" (`0x1000`–`0xB89000`) is NAMED [M], and calling it "not UE code" was false**:
  `ispc` occurs **16× ASCII** in `merged6`, in four copies of a block reading
  `Runtime/Experimental/Chaos/Private/Chaos/PerParticlePBDCollisionConstraint.ispc` (verified at
  `0x78087B9`). ⚠ The "no ISPC string exists" null came from `strxref.idx`, built on ONE image
  (`s129-poolgate`) that lights only **50 of Region A's 144** lit pages — **a string index built on
  one image is a floor.**
- ★★★ **AND THE FIRST TARGETED SWEEP CONFIRMS THE REFRAMING (S133):** the party/queue action sweep
  decrypted **183 pages in-process** but only **13 NEW TO THE CORPUS** (`merged6` 16,694 → `merged7`
  **16,707**). **13 pages is nothing as a percentage — and one of them, `0x5875000`, unblocked a
  shipped feature.** ⇒ **Stop measuring this work in coverage %. Target the specific dark function
  that blocks a specific question, then read it.** ★ 90 % of the newly-decrypted pages (129/144)
  carried no reflected UFunction — an independent re-confirmation of the ~86 % callee figure.
- ★★ **THE MEASURED EXCHANGE RATE: 216 pages (0.71 pp of `.text`) for EVERYTHING from S107 to S132**
  — tutorial world, hero walking, `GoToPhase`→`EGP_Combat`, navmesh, a pod flying at 20,000 uu/s, the
  rideable wall, the dismount. ⚠ And the **MENU family contributes MORE unique pages than the tutorial
  family** (437 vs 216), the opposite of the standing assumption. **Re-dumping an already-explored
  state is worth 0–5 pages** [M].
  ⚠ *"Crash-era `crashwatch` capture is worth 2 pages"* is **CONFOUNDED WITH ROUTE, grade [I]**:
  6 of the 7 crash images are tutorial-route processes differenced against an already-saturated
  tutorial corpus, and **no crashwatch capture exists from a driven MENU session**. It is a statement
  about crash-on-the-tutorial-route. ⚠⚠ And do **not** restate `CRASHWATCH-INFO.txt`'s
  *"~18,900 pages"* prediction as FALSIFIED — 18,911/18,980 are **pages-NAMED** (unwind entries →
  spanned pages) while 9,759–15,695 are **pages-NON-ZERO**; `fk18-fk19` §4 measures the gap at
  **3,117 named-but-byteless**. That is the "100 % readable vs 63.1 % non-zero" two-instrument
  failure again. Also the "best crash image" is the **T+141 s FK-31 staging death the repo already
  voids as unmatched**.
- ★ **The one concentrated reachable target: the Angelscript AOT band `0x59128B0`–`0x5A7F070`** —
  **239 of 366 pages dark (65.3 %)**, **2,058 of 3,760 function slots never decrypted in 76
  minidumps**. That is FK-1's drop/pod/respawn layer. The whole tutorial programme bought **+24** of
  those pages.
- ⚠ **12,831 dark pages (94.4 %) carry no reflected UFunction at all**, so the reflected-**ANCHOR**
  ceiling is ≤ 394 dark pages = **1.30 % of `.text`** (2.90 % of the DARK set — ⚠ quote the
  denominator; both this file and the settled doc first carried 2.9 % against `.text`, which is wrong).
  ⚠⚠ **That is NOT a ceiling on what driving reflected code decrypts — a reflected call decrypts its
  NON-REFLECTED callees, and ≈86 % of every page decrypted since S121 hosts no reflected function**
  (droppod 43 new / 6 with an impl · rideable 45 / 7 · dismount 44 / 6 · landstart 48 / 8 ·
  `merged6∖merged2` 56 / 8). **The real yield of any driver is its callees**, so the S55 primitive is
  not bounded by 394 — only its *anchors* are.
- ★ **Highest-value next captures are ZERO-RISK and need no relaunch or injection:** (1) a **party /
  queue / custom-game ACTION sweep** — `UPartyManager` has **20 dark impls at
  `0x5873280`–`0x5879EE0`** ⚠ **PARTLY STALE: 5 of that band's 7 pages are LIT as of `merged10` --
  `0x5875000` 3,896 · `0x5876000` 3,845 · `0x5877000` 3,275 · `0x5878000` 3,822 · `0x5879000` 3,861;
  only `0x5873000` and `0x5874000` are still 0/4,096. In particular `TryJoinQueue 0x5875E90` -- this
  file's "most-cited dark address, 11 citations" -- HAS BEEN READABLE SINCE `merged10`,** and `ignorance-map-s101.md:2270` already wrote the experiment down
  (**BOTS → FIND MATCH**, which S122 made work end to end); (2) a **FULL-PAYLOAD** `/lobby` notif
  sweep — S117's bare `{"type":X}` frames cannot reach a per-type deserializer; (3) a settings /
  renderer-permutation sweep. Ranked table in `docs/fk20-coverage-settled.md` §8.
- ★★★★★ **THE DECISIVE NUMBER: 125 CRASH LIFETIMES PLUS OUR 26 CAPTURES ONLY EVER REACHED
  55.27 %.** The crashpad `MemoryInfoListStream` is an exact per-page decryption map — on this build a
  `.text` page is `PAGE_NOACCESS` if never decrypted and `PAGE_EXECUTE_READ` if decrypted, and **only
  those two values ever appear** (6,757,306 + 5,173,408 = 11,930,714 = 394 × 30,281 page-observations
  exactly). Union over all crashes **16,434 (54.27 %)**; combined with `merged6` **16,735 = 55.27 %**;
  only **41** pages were ever decrypted at a crash and are zero in `merged6`.
  ⚠⚠ **QUOTE THE UNIT: 55.27 % is "pages KNOWN TO HAVE BEEN DECRYPTED at some moment", NOT "pages we
  hold BYTES for".** Those 41 pages exist nowhere as bytes — minidump memory inside the game image is
  **0 in 124/124**. **For offline RE the byte figure is `merged6`'s 16,694 = 55.13 %.**
  ⇒ **The dark 45 % is dark because THE GAME NEVER RAN IT, not because we failed to snapshot it.**
  ★★ **And this validates the whole page-bitmap method against an independent instrument:** pairing
  `dumpimage` non-zero pages against minidump `EXECUTE_READ` pages at the same ImageBase gives
  **5 exact equalities and 2 at +2, never fewer** — +2 being the direction monotone decryption predicts.
- ⚠ **FORECLOSED with positive controls, do not re-try:** Sentry crashpad minidumps hold **0 bytes**
  inside the game image — 396 files / 125 crashes / 10.57 GiB, 96.6 % thread stacks, `Memory64List` in
  **0/394**, and **the mechanism is named: header `Flags = 0x0` = `MiniDumpNormal`**, so no image bytes
  will ever be captured until Sentry's config changes. Discriminating control: the same parse finds
  **170 B of `ntdll.dll` per dump in 394/394** and 0 B of the game image. The 98 UECC crash minidumps
  hold **`.rdata` only** (520.9 MB of `.rdata` vs **13,824 bytes** of `.text` across all 98).
  ⚠ `merged6` is a **strict superset of every `.text`-bearing artifact on disk** (32 sources diffed at
  page granularity, ADDS = 0), including `tools/re/.exec_surface_cache/text_union.bin`, never examined.
  ★ **But UECC minidumps DO list `runtime.dll` in their ModuleList** (217–222 modules) and capture
  1.57 MB of it — **CLAUDE.md's "`runtime.dll` has NO module entry in ANY crashpad minidump (0 of
  14)" is true of the SENTRY corpus and does not generalise.** That is an offline n≈98 instrument for
  FK-31's per-boot kill-address claim, and it is unused.
- ⚠⚠ **`tools/strxref/index/pdata_union.csv` IS AN EXECUTION-TRACKING INSTRUMENT, NOT A FUNCTION
  MAP.** `pdataunion.py` keeps only slots with `End-Begin > 1`; a size-1 slot is the packer's
  placeholder for a function **not yet decrypted in that process**. So it is **blind by construction on
  exactly the dark pages you are asking about**, and any filter built on it can only ever admit LIT
  code. **Two independent agents built that filter and both were caught only by a positive control**
  (a known-dark address graded "not a function"). Placeholder `BeginAddress` is also **not stable
  across processes** (737,978 distinct values over 524,439 slots) — treat it as a ±1-page locator.
- ★★★★★ **BIGGEST BY-PRODUCT, AND IT BELONGS TO FK-10/FK-31: `dumpimage` HAS BEEN DISCARDING THE
  PROTECTOR, 52 TIMES.** `tools/usmapdump/dumpimage.go:239-240` does
  `case rg.typ != memPrivate: dumped = "(skip: Image — other module)"` — **every `MEM_IMAGE`
  executable region, by design**, on the false premise in its own comment that such a region is
  "other DLLs". A **manually mapped, module-list-hidden** `MEM_IMAGE` region is **the protector**.
  **[M] The protector signature (`SizeOfImage 0x4066000`, 48,136,192 exec bytes — both matching S131
  and FK-10) appears in 26/26 manifests, TWICE each = 52 mappings, every one skipped.** Confirmed here
  straight from the manifests: `0xFF767000 0x1000 Image` and `0xFFF2F000 0x170000 Image` are exactly
  LOW`+0x7000` and LOW`+0x7CF000` of the predicted region map.
  ★★★ **AND THE MANIFESTS CORROBORATE FK-31 FROM A NEW INSTRUMENT:** the HIGH bases group by era as
  `0x7FF90E000000` (9 dumps) · `0x7FFD3B400000` (1) · `0x7FFA42600000` (6) · `0x7FFB57400000` (10),
  summing to 26 — **the last three are exactly S131's three constant kill addresses minus 1**, plus a
  **FOURTH era base S131's minidump-only corpus could not see**. ★★ **`runtime.dll` is mapped TWICE and
  the LOW base is INVARIANT at `0xFF760000`** (26/26 manifests, 123/124 distinct crashes); the HIGH copy
  alone shows split `READWRITE`/`WRITECOPY` ⇒ [I, strong] HIGH is the executing view, consistent with the
  kill jumping to HIGH+1. ⚠⚠ **THE DOUBLE MAPPING AND THE SHADOW-EXE MAPPING BELOW ARE *NOT* NEW —
  `docs/s109-dump-forensics.md` §5 (2026-08-04/05) already tabulates all three hidden images**, with the
  same LOW/HIGH `EXECUTE_WRITECOPY` vs `EXECUTE_READ` distinction, re-verified at
  `docs/s109-skeptic-review.md:60-70` against UE's own `<CallStack>`. **What is new is only that the
  `dumpimage` MANIFESTS carry it too, 52 times, each marked skipped.** ★ *Grep before writing "NEW".*
  ⚠ **[M] 48,136,192 B (45.90 MiB) of protector executable content sat readable under RPM in every
  capture and none was written.** A draft said **96.3 MB** by summing both mappings — that
  **double-counts two `SEC_IMAGE` views of the same 67,511,496-byte file** (observed differentiation
  between views: **57,344 B**). Proposed patch (NOT applied — it adds ~96 MB per dump to an already-16 GB tree, so make it
  a flag): skip `MEM_IMAGE` only when `AllocationBase` resolves to a real module; otherwise DUMP IT.
  Pure RPM. It plausibly yields **plaintext `packer0`** (94.8 % encrypted on disk), where the kill
  vtable `packer0 RVA 0x1831C0` and its installer `RVA 0x7F86F0` live — FK-10 Wall #7's target.
- ★ **A THIRD hidden mapping, and it is a lottery ticket worth one command.** In **394/394** minidumps
  there is exactly one `MEM_IMAGE` allocation of `0xA9E1000` — **the game's own `SizeOfImage`** —
  `READONLY`, a **single** region with no per-section protections, at a heap address, **124** distinct
  bases. **0 bytes ever captured.** ⚠ Also recorded in `docs/s109-dump-forensics.md` §5 and never acted
  on — the lottery ticket has been on the table since 2026-08-04. Control: **the game's real module is `MEM_MAPPED`, not `MEM_IMAGE`
  (0/394)**, so this is a *second, hidden view of the exe*. [I, strong] a `SEC_IMAGE` raw view ⇒
  probably the encrypted on-disk bytes; **[S] it could be the plaintext master the fault handler
  decrypts from — in which case one read-only RPM read yields 100 % of `.text` in one shot.**
  **Settle it with one `VirtualQueryEx` + two 4 KB reads (base, and base+`0x751EFD0` = the OEP)
  compared against the on-disk exe and `merged6`. Not settleable offline.**
- **Process fix: `python tools/re/dump_coverage_ledger.py`** — reads bytes, not manifests; an image is
  an ORPHAN iff it holds ≥1 decrypted page the reference merge lacks; exit 1 on orphans. Validated
  both ways (0 orphans vs `merged6`, 6 vs `merged5`). ⚠ Its per-image column is **not additive**.

### Before touching anything READOUT- / "we can't see what the client is doing"-shaped
★★★★★ **S121 built EIGHT read-only RPM probes, and EVERY ONE contradicted something that had been
inferred first. Reach for them before reasoning about client state.** All are pure `ReadProcessMemory`
— no injection, no `.text` writes. Read `docs/next-session-prompt-s122.md` for the table.
`toggle_readout.py` (declarative gate results) · **`bpframe_readout.py` (ANY Blueprint's live
ubergraph locals, via the persistent `UberGraphFrame` — this is what finally sees the 10 BYTECODE
feature-toggle keys)** · `regions_readout.py` · `obj_props_dump.py` (every reflected object/array
property + target class names) · `promptstack_readout.py` · `motd_chain_readout.py` ·
`class_derivation.py` · `widget_inviewport.py` · `exec_regions.py`.
⚠ **Several print warnings about their own blind spots — read the output, not just the numbers.**
`toggle_readout`'s `never-evaluated` vs `ambiguous-off` split is load-bearing; `class_derivation`
UNDER-enumerates functions so only its POSITIVES count; a crashpad dump's coverage says nothing
about whether an address was mapped.
⚠⚠ **Two failure modes S121 added to the register (`FK-38`):** a **correctly calibrated instrument
aimed at the WRONG QUESTION** still gives a false answer, and the calibration makes it feel earned;
and **over-correction** — after a run of retractions, sound evidence starts getting discounted.

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
  is absent", so a zero is a real statement about our shape).
  ★★ **CONFIRMED RENDERED — CAREER → STATS draws every served field**: MATCHES 12, KILLS 40,
  MAX KILL STREAK 4, KNOCKS 55, MAX DAMAGE DEALT 21,400, MAX HEALING GIVEN 5,100, MAX DAMAGE
  TAKEN 19,800, TIME PLAYED 2h 20m 0s (= `TimePlayedSeconds: 8400`).
  `StatsByQueue["tutorialNew"]` lands on **BASIC TRAINING**, and TRAINING MODE / PRACTICE RANGE /
  CO-OP VS. AI render **all zeros** — a free negative control, since we serve only that one queue,
  so the queue keying is confirmed in BOTH directions.
  ★★★ **`Placements` IS ZERO-INDEXED (key 0 == 1st place) — [M], CONFIRMED BY PREDICTION.**
  Serving `{1:3,2:5,3:4}` gave `WINS 0` / `TOP 3 8`; 0-indexed predicts both
  (`WINS=P[0]`=absent=0, `TOP3=P[0]+P[1]+P[2]`=8) while 1-indexed predicts neither (3 and 12).
  The pre-registered test was then flown: `{0:3,1:5,2:4}` rendered **WINS 3 / TOP 3 12**, exactly
  as written down beforehand, **with all eight echoed tiles unchanged** (MATCHES 12, KILLS 40,
  STREAK 4, KNOCKS 55, 21,400 / 5,100 / 19,800, 2h 20m 0s) — two derived values moved, nothing
  else did, from one key edit.
  ⚠ **`FPlayerHeroStats` HAS NO `Wins` FIELD** — which is why WINS must be derived, and which
  independently confirms that those 22 fields are NOT the `statCode` namespace (`wins` is not
  among them; `ST_Leaderboard_Stats` is that vocabulary).
  ⚠ It is a **login-time** fetch and an admin socket drop does **not** trigger a refetch, so
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

### Before touching anything rank- / badge- / "which endpoints don't we serve?"-shaped
★★★★★ **THE UNSERVED-ENDPOINT SWEEP IS A FREE, OFFLINE, ONE-PASS MAP OF EVERYTHING THE CLIENT WANTS
AND WE IGNORE (S122, 2026-08-15). Read `docs/s122-player-rank-career-badge.md`.**
S121's lever was "flip a toggle, watch for new endpoints" — a search, one key at a time. **S122
inverted it: parse the conversation the client has ALREADY had and diff it against the mux.**
Tools: `tools/re/endpoint_surface.py` + `tools/re/unserved_routes.py`.
- **[M] 56 distinct client routes, 8 unserved** (falling to main.go's `/` catch-all `200 {}`). Three
  are client→server UPLOADS with no surface (party `latencies`, `game-telemetry` events, a Vivox
  `voice` token for an externally-dead service — `Access Token Service Unavailable`).
  **Still unserved with real UI behind them: `GET /referral/player/{id}` and `/points`.**
- ⚠⚠ **THE User-Agent FILTER IS LOAD-BEARING, NOT HYGIENE: 23,050 of 24,767 records were NOT the
  game** (23,047 = our own `supervive-loadout-shim`). Unfiltered every count is garbage.
  `endpoint_surface.py` prints the rejected count + UA breakdown so the filter is visible.
- ⚠ **Never infer cadence from a total.** `progressiontracks` reads "730 calls ⇒ a 6 s poll ⇒ a
  leak"; the real shape is a **~728-call burst over 54 s at menu init**, then 2 in the next hour.
★★★★★ **`GET /mmr/player-ratings/{id}/rank` IS IMPLEMENTED AND CONFIRMED LIVE — the CAREER nav-button
notification badge is now driven from the backend.** No shim, no injection, no `.text` write; **five
arms, zero launches**, all on one continuously-running client.
- **Why this target:** it comes with its OWN READOUT. `WBP_UI_MainMenu_NormalMainMenu`'s bytecode
  (stmts 156-158) does `HasRankedRewardsToClaim()` → `NavButtonMain_Career->ShowBadge(...)` **and the
  bool is an ubergraph local**, so it is RPM-readable. **A surface you cannot observe is a surface you
  cannot test — pick targets that carry their own instrument.**
- **Model [M]** (UHT oracle): `FPlayerRank{ID FString, Version int32, QueueRankRating
  TMap<FString,FQueueRankRating>, RewardsToClaim TMap<FString,FRankedReward>}` ·
  `FQueueRankRating{Rating i32, Rank ERank, Cost i32, Updates TArray<FMatchRankedRating>}` ·
  `FRankedReward{ID FString, Entitlement FPrimaryAssetId}`. Both maps are JSON **OBJECTS**;
  `Entitlement` **omitted** (unresolvable id = the missions `InternalName` failure); `Rank` reuses
  the measured-good `"Gold1"`.
- **[M] Arms** (bool · has-run · badge `Visibility`, 1=Collapsed 4=rendered):
  A unserved `False·61·—` → **B reward+high ver `True·62·4`** → C empty+higher ver `False·61·1` →
  **D reward+ver 1 `False·61·1`** → B-repeat `True·62·4`. Three sibling badges stayed `1` throughout;
  only the LIVE instance ever moved; canaries 0 (`Unable to import`/`Deserialization failure`/
  `Invalid response received`/`Fatal`).
  ⇒ **B vs C** (only the map differs) ⇒ `RewardsToClaim` drives the badge. **B vs D** (only `Version`
  differs) ⇒ ★★ **`FPlayerRank` IS BEHIND A MONOTONIC VERSION GATE [M]** — the same family as
  `FParty.Version`'s `jge bail`. We serve `int32(time.Now().Unix())`, so it self-advances.
- ⚠⚠ **`AGS_PLAYER_RANK=0` IS NOT A CONTROL — serving `{}` did NOT reverse the badge.** `{}` changes
  the document AND the version at once (`Version: 0`), so it is **uninterpretable, not negative**.
  ⇒ ★ **A revert knob that returns to a CATCH-ALL changes every field at once. Build the controlled
  negative alongside the feature** — `AGS_PLAYER_RANK_EMPTY=1` (valid struct, advancing version,
  empty map) is the real one; `AGS_PLAYER_RANK_VERSION=N` isolates the gate.
- ⚠ **NOT login-only:** an **`ags` restart alone** drops/re-establishes the client's WebSockets and
  the resync refetches this within ~40 s. (First draft said "probably needs a relaunch" by analogy
  with `/player-stats/players/{id}` — reasoning by similarity where a measurement was available.)
- ★ **Serving it revealed another endpoint:** `POST /party/parties/{p}/refreshRanks`, absent from all
  56 routes before this handler existed. Still unserved.
- ★★ **BOTH HALVES OF `FPlayerRank` RENDER — screenshot-confirmed.** The RANKED page draws **`GOLD I`**
  and **`1,850 RP`** from our `Rank`/`Rating`, and `tutorialNew` resolves to the label **BASIC
  TRAINING**. ⚠ **RETRACTED same session:** this file first said `QueueRankRating` was untested "and
  the key is likely wrong". Untested was true; *likely wrong* was editorialising an untested item
  into a prediction. **Record untested as untested.**
★★★★★ **THE RANKED QUEUE DROPDOWN IS GATED BY `IsRanked`, AND IT IS NOT A SEASON SELECTOR (S122).**
- ⚠ **Read the widget CLASS before trusting a screen-position reading.** The control beside
  `SEASON 2` looks like a season picker; it is `WBP_UI_Leaderboard_ComboBox_Queues_C`
  (`QueueSelector`/`UpdateSelectedQueue`/`InitQueueButtons`) reading
  `CallFunc_GetQueueInfo_ReturnValue` = our **`GET /party/matchmaking/info`**. `SEASON 2` is a
  SEPARATE static element (`SeasonHeader`). Two adjacent controls, two unrelated data sources.
- **[M] `buildQueueDetails` hardcoded `IsRanked:false` on all four queues** (`tutorialNew`,
  `training`, `practice`, `bots`) while the combobox carries a **`ShowOnlyRankedQueues`** flag — so
  the filtered list was empty and it fell back to the selected queue. CAREER→STATS renders all four,
  which is why "we advertise four" and "the dropdown shows one" were both true.
- **PRE-REGISTERED AND CONFIRMED [M]:** `AGS_RANKED_QUEUES="tutorialNew,training,practice"` with
  **`bots` deliberately EXCLUDED as the control** → dropdown shows **BASIC TRAINING · TRAINING MODE ·
  PRACTICE RANGE**, CO-OP VS. AI **absent**. 3 present / 1 absent, exactly as written down first.
  ★ The excluded queue is what makes it a measurement — "mark all, see all" would prove nothing.
  Knob defaults **empty** (byte-identical to pre-S122). ⚠ Same array feeds the PLAY activity picker.
- ⛔ **SEASONS ARE A DEAD END — do not chase a season list from the backend.** `SeasonHeader` casts to
  **`LokiDataAsset_Season`**, and [M] a 69k-asset catalog search finds seasonal *textures*,
  `DT_SeasonalBattlepassRichText` and `LT_ArmoryEquipment_Season2` but **no packed
  `LokiDataAsset_Season`** — the same missing asset this file already records as blocking the
  seasonal battlepass. The cast has nothing to land on.
★★★★★ **THE S60 QUEUE TRIM IS RETIRED, AND THE WORKAROUND WAS HIDING THE DEFECT (S122).** All 10
queues are the DEFAULT now; `UPartyModel.Queues` **4 → 10** [M], `Members` unchanged as control,
0 errors. Read `docs/s122-player-rank-career-badge.md` §10.
- ⚠⚠ **The trim's stated mechanism DOES NOT EXIST.** [M] `bpdump_CanControlQueue.txt` 181-185:
  `GetLevelGameFeatureUnlocked` is called **exactly once**, with a **hardcoded**
  `PrimaryAssetId{GameFeature,"Ranked"}`, behind `EX_PopExecutionFlowIfNot(Not(bIsRankedEligible))`,
  only to FORMAT the "you need level N" text. **No loop over queues, no per-queue feature lookup.**
- ⚠⚠ **AND "S120 serves AccountPass.Level = 10" IS FALSE — the live server serves `Level 0`.** S120
  *measured* that serving 10 removed the mastery lock; it never became the default (it comes from
  persisted per-player state). This file asserted it earlier in S122 and it was wrong.
  ⇒ ★ **Read a remembered measurement as a measurement, not as the shipped default. Check the wire.**
- ★★★★★ **REMOVING THE TRIM ALONE WAS NOT ENOUGH, and that is the reusable part.** Clicking a tile
  POSTs **`/party/parties/{p}/setTargetQueues {"queueIds":["…"]}`** — which had **NO HANDLER**, fell
  to the `/` catch-all, and the next `/party` poll re-served the old `targetQueueId`, snapping the
  selection back (the observed grey/un-grey). **Under the trim this was INVISIBLE — with one
  selectable activity there was nothing to switch to.** S60 saw "activities don't work", trimmed the
  list, and the trim removed the EVIDENCE rather than the cause.
  ⇒ ★ **A workaround makes the bug it hides unobservable, so the workaround looks correct forever.
  Removing it is how you find out.** Now implemented (persists + echoes the party; `store.update`
  bumps `partyVer` so the S85 monotonic `SetParty` gate accepts it). Operator-confirmed.
- ⚠⚠ **THE SWEEP METHOD'S BLIND SPOT, named by its own miss:** the §1 capture-diff reported "8
  unserved" and **missed `setTargetQueues`, because nobody clicked a tile during that capture.**
  ⇒ **A passive capture-diff is a LOWER BOUND on unserved surface, never a map.** Drive the UI
  through the interactions you care about, THEN re-run the diff.
- ⚠ **ARENA is still `LEVEL 13 🔒` and that is CORRECT** — `AccountPass.Level = 0`. [M] the tile
  `WBP_UI_PartyQueue_DropdownItem` reads `IsQueueIDPremadeOrOverQueueLevel` → {CanQueue, UnlockLevel,
  Reason} against `GetAccountPassViewModel`; `ST_Parties` holds
  `"Requires Hunter's Journey level {level}"`. Serving a locked queue is harmless (the client draws
  the lock). **Two levers, neither pulled:** raise `AccountPass.Level`, or the toggle key below.
- ★★★★★ **A THIRD CATEGORY OF FEATURE-TOGGLE KEY — DYNAMICALLY CONSTRUCTED, so NO static census can
  find it.** [M] `bpdump_IsQueueIDPremadeOrOverQueueLevel.txt` 6-11:
  `Concat_StrStr("queue.restrictions.", QueueID)` → `GetFeatureToggle(key)` →
  `Map_Find(Config,"Level")` → `Conv_StringToInt` → `SelectInt(parsed, fallback)`.
  ⇒ **`featureToggles["queue.restrictions.<queueId>"].Config["Level"]="<int>"`** sets a queue's
  required level from the backend. ⚠ `Config` is
  `TMap<FString,FString>` ⇒ `Map_Find` is case-**SENSITIVE**; `"Level"` exact. (The lowercase
  `level` nearby is the ST_Parties format-arg name, a different role — not a case ambiguity.)
  ★★★★★ **FLOWN AND CONFIRMED — [S] → [M], full A-B-A, operator-observed. Knob `AGS_QUEUE_UNLOCK`
  (default EMPTY).** Serving `Level:"0"` for `deathmatch`: ARENA's lock GONE, real description
  ("Fast-paced 4v4 in close quarters"), **FIND MATCH active**. Withdrawing it: lock BACK
  (`Requires Hunter's Journey level 13` · `LEVEL 13 🔒`), **FIND MATCH greyed**. eTag moved
  automatically both ways; `LogClientConfig` confirmed adoption in both arms; canaries 0.
  ★★★★★ **AND THE REVERSAL REPRODUCED THE S60 ERROR STRING VERBATIM —
  `"Unable to modify activity. Note: You must always have one activity selected."`** ⇒ its real
  trigger is **selecting a LEVEL-LOCKED queue**, NOT queue-list length. **S60's diagnosis was a
  CORRELATION**: trimming the list stopped the error only because it deleted the gated queues,
  leaving nothing lockable to click. ⇒ ★ **A workaround that removes the TRIGGER is
  indistinguishable from one that fixes the CAUSE, and stays convincing indefinitely.**
  ⚠ **The spatial control was empty** — TOURNAMENT turned out to be selectable, so ARENA may have
  been the only locked tile. **The temporal A-B-A carries this result, not the sibling control.**
  Designing a spatial control and finding it empty is normal; substituting the reversal is the fix.
  ⚠⚠ **S121 declared the toggle vocabulary CLOSED "with no remainder" at 50 declarative + 10
  bytecode keys. IT IS NOT CLOSED** — runtime-concatenated keys are invisible to both censuses, and
  other parameterized families may exist.
- ⚠ **"BASIC TRAINING is pre-selected" is ONBOARDING, not a stuck queue.** [M] live on
  `Comp_MainMenu_Onboarding` (has-run 59): `Get_Number_of_Games_Played = 0`,
  `Should_Launch_Tutorial_Match_bPlayMatch = True`. ★ Proof it is not the queue: on page open the
  client POSTs `{"queueIds":["default"]}` (= BREACH) while the UI highlights BASIC TRAINING.
  Exiting it needs a non-empty `FMatchHistory.Matches` — which FK-17 deliberately avoided, since
  `FMatchHistoryEntry` is 15 fields and a wrong-typed matched key sinks the document.
- Knob: `AGS_QUEUE_IDS` still overrides the list — now useful for **narrowing back** to the S60 four
  if a regression is ever suspected, the reverse of why it was added.
- ⚠⚠ **FOURTH stale-eTag instance, fixed in the same edit:** `matchmakingETag` was the constant
  `"revival-queues-v1"` while its body became env-dependent. Now `revival-queues-v1-<sha256[:6]>`.
  **When you make a payload env- or state-dependent, its eTag stops being a constant in THAT edit.**
⚠⚠ **TWO PROBE DEFECTS FOUND, BOTH FIXED — and both produced a false reading first:**
- **`bpframe_readout.py` PICKS THE WRONG INSTANCE. FOURTH member of the class-lookup blind-spot
  family** (after `obj_by_class.py` substring, `cheat_reach_probe.py` endswith, `class_props.py`
  class-of-class). Three objects share `WBP_UI_MainMenu_NormalMainMenu_C` — the CDO and **TWO both
  named `MainMenu_NormalV2`** — and it stops at the first non-`Default__`, whose frame is entirely
  default (**HAS-RUN 0 of 219**). It reported `False` for a graph that had **never run**, on a menu
  live 74 min, and it looked measured. ⚠ **Same NAME on both, so name matching cannot separate them —
  only the has-run control can.** ⇒ **use `tools/re/bpframe_all.py`** (enumerates every instance +
  per-instance has-run). Shared defect = *take the first match*; shared fix = *enumerate and show
  your work*.
- **`obj_props_dump.py` is blind to SCALARS and offers a DECOY.** It prints only object/array props,
  so `Visibility` / `ActiveWidgetIndex` are invisible — while `ActiveSequencePlayers = Num=2` on the
  badge reads like "animations running ⇒ visible". **The three COLLAPSED siblings read 2, 2, 1.**
  ⇒ **`tools/re/obj_scalars.py`** is the missing half. **Sibling controls killed the decoy in one
  call; read alone it would have been written up as confirmation.**
⚠⚠ **`Start-Process -ArgumentList` DOES NOT QUOTE PATHS WITH SPACES** — `-log "G:\git\Supervive
Revival Project\…"` truncated to `G:\git\Supervive`, so **`capture.log` went silent while the backend
was fully healthy** (and a stray `G:\git\Supervive` file appeared). Pass ONE argument string with
embedded quotes. ★ **What caught it was a second, independent instrument**: `Loki.log`'s
`LogClientConfig` 30 s receipts proved the client was fine. **Keep a client-side AND a server-side
view.** ⚠ Also: `ags` **APPENDED** to `capture.log` here, contradicting this file's "truncates on
restart" — back it up regardless, the recorded behaviour is unreliable in both directions.

### Before touching anything CAREER- / match-history- / "authentic empty"-shaped
★★★★★ **FK-21 IS SETTLED (S123, 2026-08-15) — read `docs/fk21-career-panels-settled.md`.** All three
CAREER panels are LIVE and backend-driven; **none of them was ever an "authentic empty"**. Each was
empty because we served nothing, and each renders the moment it is fed:
**Stats** S121 · **Ranked** S122 · **History** S123. Backend-only — no shim, no injection, no
`.text` write; four arms on ONE client up 3h15m with **no relaunch**, canaries 0/0/0/0.
- ⚠ **Be precise about which half was wrong.** S119 had ALREADY excluded "broken deserialization"
  for History (`MatchHistoryManager+0x68` reads back our exact served `Version`), and that stands —
  at baseline the manager held our player id with the gate open. **What was never shown for any of
  the three is that the panel is LIVE.** An empty panel fed by a parsing document is still
  consistent with "this surface is dead."
- ★ **Knob `AGS_MATCH_HISTORY=off|minimal|full`** (`server/internal/interactive/matchhistory.go`),
  default OFF and OFF is byte-identical to pre-S123 (`Matches: []`). Plus `_COUNT`, `_HERO`.
  ⚠ **Fly `minimal` before `full`** — minimal is scalars/strings/FDateTime only, so a blank panel is
  localisable; if `full` goes first a null cannot separate "does not render" from "one of the five
  risky fields sank the document", and this endpoint fails SILENTLY.
- ★★ **READOUT: `tools/re/matchhistory_readout.py`** (read-only RPM) reads the PARSED
  `FMatchHistory` off the live manager — `ID +0x58`, `Version +0x68`, `Matches +0x70`, and each
  entry's fields. It separates the four outcomes a screenshot cannot: rejected (`Version -2`),
  parsed-but-element-dropped (`Num 0`), parsed-and-landed (`Num N`), and instrument fault.
- ⚠⚠ **`TeamInfo.Placement` IS 1-INDEXED — THE OPPOSITE OF ITS SIBLING.** It renders `1/16` from
  `Placement: 1`, while `FPlayerHeroStats.Placements` on `/player-stats/players/{id}` is
  **ZERO**-indexed (S121, confirmed by prediction). **Two placement fields, one backend, opposite
  conventions — carry neither across.** Only discriminating because the flight served 1-of-**16**;
  1-of-1 renders identically under both.
- ★★ **THE DAMAGE TILES READ `Effective*`, NEVER THE RAW `Damage*` — 5/5 [M]** with deliberately
  distinct values (`TOTAL DAMAGE DEALT` 18,000 from `EffectiveDamageDone`, not 21,400 from
  `DamageDone`; same for both `HeroEffective*` and `ShieldMitigatedDamage`). The four raw fields have
  **no known consumer on this panel**. ★ The clue was that **healing rendered while damage read 0** —
  same struct, same float type — because healing is the one stat with no `Effective` variant.
  ⚠ Label ≠ field twice: `MINIONS KILLED`←`CreepKills`, `GOLD FROM MINIONS`←`GoldFromMonsters`.
- ⚠ **BLAST RADIUS: `Matches.Num()` is also `Comp_MainMenu_Onboarding`'s games-played count** [M]
  (`bpdump_Get Number of Games Played.txt`: a `Cheat.Onboarding.MatchHistoryCount` cvar override,
  else `GetMatchHistory().Matches.Num()`), and that component owns `Should Show Returning Player
  Modal`. Serving N rows makes the client believe it has played N games.
- ⚠⚠ **`push.go`'s "any positive value works" for this resource is STALE** — true when
  `/match-history` was an empty catch-all, false since `handleMatchHistory` gave it a wall-clock
  `Version` (~1.79e9). A push of `Version 7` is now the documented TOO-LOW case, silently ignored.
  Pass `interactive.MatchHistoryVersion(id)`.
- ⚠ **The usmap cannot answer this struct's array inner or its enum** (FK-14 reads both at
  `FField+0x80`, past the object). Read them live: `tools/re/struct_layout.py` +
  `scratchpad/enum_of_prop.py`. `StartingRank` is **`ERank`** [M], `Gold1` = index 12.
- ⚠ **Two instrument traps fired here, one NEW.** (a) the **archetype trap** — one live
  `WBP_UI_MatchHistoryEntry_C` with `Visibility = 4` was the widget-tree TEMPLATE, caught only by
  `MatchHistoryScreen` having **0** activations in the log ⇒ *prove the screen was ever built before
  reading a widget's state* (5th member of the class-lookup blind-spot family). (b) ★ **THE GREP
  WINDOW IS PART OF THE INSTRUMENT** — `grep -B2 -A3` paired a request with a NEIGHBOURING request's
  `User-Agent` and read as "the game never refetched"; `-A 12` gave the truth. **Pair each request
  with its OWN header block.** ★ Give verification curls an absurd UA (`fk21-verify-NOT-THE-GAME`).

### Before touching anything menu-shaped
Skim `docs/trackb-notes.md` (Track B endpoint surface + ClientProfileData model)
and `docs/endpoints.md` (every endpoint the client hits + handler status).
⚠ Its CAREER rows were `❓`/`🟡` long after those endpoints were served — **check the session number
on a row before trusting its status marker.**

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

### Before touching anything simulation- / objective- / "the Blueprint does nothing"-shaped
★★★★★ **THE BLUEPRINT EXEC-PIN GATES ALWAYS ANSWER "NOT SERVER", AND THAT IS THE SYSTEMIC CAUSE OF
"PRESENTATION WORKS, SIMULATION DOESN'T" (S134 audit, 2026-08-20). It is engine-wide, it has no FK
number, and it re-attributes at least three separately-recorded nulls to one byte.**
`ULokiBlueprintLibrary`'s four exec-pin gates are how a Blueprint asks *"am I the server?"*:

| gate | thunk → impl | bytes | selects on this client |
|---|---|---|---|
| `ServerOnly` | `0x52E12B0` → **`0x1311870`** | `C6 02 00 C3` = `mov byte [rdx],0; ret` | **Hidden** (Server=1) |
| `ClientOnly` | same (ICF-folded) | same | Client |
| `ClientServerSplit` | same (ICF-folded) | same | **Client** |
| `CheatsEnabledOnly` | `0x52E0D00` → `0x13852F0` | `C6 01 01 C3` = `mov byte [rcx],1; ret` | **Hidden** |

**[M]** `0x1311870 = C6 02 00 C3`, present and identical in **18 of 18** dump images, enum orders read
from the UHT enumerator records (`.rdata 0x88BF3E8`/`0x88BF3F8`) with `EClientOnlyExecPins` as the
control — `docs/fk22-dropphase-reachability.md:589`. Internal control: the two-param gates write `rdx`,
the one-param gate writes `rcx`, exactly as their `binds_members.csv` signatures predict.
★ It is coherent that `execServerOnly`/`execClientOnly` ICF-fold: on a client both compile to
"write 0" — Hidden = stop, Client = continue.
★★★★★ **DECISIVE FOR OBJECTIVE COUNTING, read straight from the shipped bytecode:**
`Comp_GameState_TrainingBase::ProgressObjective` → `ExecuteUbergraph(768)`, and at StatementIndex 768
`[31] ServerOnly → [32] NotEqual_ByteByte(OutputExecs,1) → [33] JumpIfNot → [34] Jump 1391 (EXIT)`,
with the increment at **offset 838**. `ServerOnly` writes **0** ⇒ `NotEqual(0,1)` is TRUE ⇒ the
`JumpIfNot` does not jump ⇒ control falls into the EXIT jump. **Offset 838 is unreachable on every
invocation path** ⇒ **`ProgressObjective(N)` can never move `CurrentObjectiveCount`, synthetic
`FFrame` or not.**
⚠⚠ **THREE RECORDED CAUSES FOR TUTORIAL NULLS ARE ALL WRONG, AND THIS IS THE REAL ONE:**
- S92 *"ProgressObjective did nothing because my quests are ORPHANS"* — no; the increment is behind the gate.
- S93 *"its ServerOnly branch skipped when called from the synthetic FFrame"* — no; it skips on EVERY path.
- S93 *"`box.OnActorBeginOverlap InvocationList Num=0` ⇒ needs the sequencer/TeamState lifecycle"* — no;
  in `bpdump_ExecuteUbergraph_TrainingQuest_Basics_WASD.txt` the `ClientServerSplit` is at `[50]`,
  `EX_BindDelegate OnWASDTriggerOverlap` at `[59]` and `IncrementObjectiveCount` at `[64]` — **the bind,
  the overlap test and the increment are all on the SERVER arm**; the client arm pushes four
  presentation flows and never touches the delegate. **The bind is never installed.**
★ **Blast radius** (tutorial bpdumps alone): `Comp_GameState_TrainingBase` x3 `ServerOnly`,
`BP_LokiGameMode_Tutorial` x2, `TrainingQuest_Basics_WASD` x1 `ClientServerSplit`,
`TrainingQuest_Basics_Base`, the quest sequencer, `Comp_GameMode_DropPlane_Tutorial`, and
`BP_LokiHeroCharacter` x13. **It is engine-wide, not tutorial-specific** — expect it on ANY mode.
★★ **THE LEVER, and it is in a measured-safe class:** `EX_CallMath` dispatches through
`UFunction.Func`, and the three write-0 gates are **distinct `UFunction` objects sharing one folded
target** — so a per-`UFunction` **heap `Func` swap** to a 4-byte stub writing the Server pin is
single-variable and touches no module image (`KFUNCSWAP`, measured **0/16 deaths at 600 s**). The
surgical alternative is a **Blueprint bytecode edit** of one gate (`EX_ByteConst 1` → `0`), the class
S111 arm J measured at **0/9**.
⛔ **DO NOT patch `0x1311870` in `.text`** — that is the standing-`.text` class, measured **7/8 lethal**.
⚠ Pre-registered readout for the first arm: call `ProgressObjective(1)` on the live
`Comp_GameState_TrainingBase_C` and read `CurrentObjectiveCount` **0 → 1**. That one call settles it.
⚠ It also explains FK-22's *"the DropPlane component is NOT a subscriber"* (S124) — the bind sits on a
`ServerOnly` arm. **But see `fk22:590`: two FURTHER bind sites of the same handler are UNGATED**
(`SpawnPlane` `[38]-[40]`, `OnDeathCircleSet` `[90]-[92]`), so **one of three bind sites is dead, not
the bind.**

### Before touching anything round-phase- / GoToPhase- / "the round never starts"-shaped
★★★★★ **THE ROUND PHASE IS DRIVABLE AND IT SELF-DRIVES TO `EGP_Combat` (S124, 2026-08-16, FLOWN).
Read `docs/fk22-dropphase-reachability.md` §14-§15.** Two flights on one staged tutorial world, **zero
`.text` writes, zero PI hooks, zero crashpad handoffs**, no relaunch between them.
- **[M] ONE CALL STARTS A CASCADE.** The shim called `GoToPhase` **exactly twice** (args 1 then 4) via
  the S55 direct-thunk primitive. The log shows **six** transitions: our `1` (the A1 control), our `4`,
  then **`5 (SpawnReveal)`, `6 (Lineup)`, `7 (Combat)` ~100 ms apart that we never called** — the game's
  own timer ladder, exactly as predicted offline from the four tail-jmp callers
  (`0x560A104/174/1A2/AA72`, constants 9/2/3/6) reached through `[vtable+0xB08] = OnNewPhase`.
  The game then printed **`Took 414.264048 seconds to go from EGP_Pre to EGP_Combat`** and, ~49 s later,
  began **mass navmesh generation** across `LVL_Tutorial`. ⇒ `GoToPhase` is **reachable and unguarded**.
- **[M] THE STORE IS DEAD — [I] → [M].** All six `Transitioning` lines read `from phase
  (EGP_ServerStartup)`, and a post-run RPM read gives `GameState+0xA44 = 0`. `GoToPhase`'s phase write
  really does land on the stripped `ret 0` fold `0xF7EC20`; **the stored byte never moves.**
- ★ **THE POSITIVE CONTROL IS THE WHOLE SITTING.** `GoToPhase` logs its ARGUMENT before the old==new
  test, so a reachable thunk **cannot** be silent. Baseline is **exactly one** `Setting Phase to 1
  (BeginInit)` per file across 193 files ⇒ **a SECOND occurrence in one file cannot come from the game.**
  A silent A1 means the sitting is VOID and nothing else may be interpreted.
  ⚠⚠ **AND THE RECEIPT SELF-CONTAMINATES:** once the cascade has run, `Setting Phase to 7 (Combat)` is
  already in the log, so **presence stops discriminating and only the COUNT does.** Record baseline
  counts BEFORE injecting anything on a second flight into the same process.
- ⚠⚠ **`GameState` IS AT `GameMode+0x418`, NOT `+0x258` — the docs' offset is REFUTED, measured.**
  On the live `BP_LokiGameMode_Tutorial_C` (`0x1B3857EA4C0`), `[+0x258] = 0x1B405BE1000` is **not a
  UObject** (heap "vtable" `0x1B2C4323C00`; a real one is in-module, this GameMode's is
  `0x7FF7A4A54C48`; bytes are a repeating `{ptr,0xFFFFFFFF,int}` array). A scan of the GameMode's first
  `0x1000` bytes finds the real GameState (`0x1B4021B60A0 BP_LokiGameState_Tutorial_C`) at **exactly one**
  offset: **`+0x418`**. The shim's `GcAlive` guard caught this and **aborted twice rather than poking a
  stranger.** ★ `+0x7C0 = 4` is also now confirmed LIVE ⇒ **the 3→4 gate is one term short
  (`CurrentPhase == 3`)**, exactly as predicted.
- **Builds:** `build.ps1 -Name tutorial_launch -Variant phaseladder|-any|-readonly|-nopoke|-a5`
  (`RM_PHASELADDER`, enum 24). ⚠⚠ **`-Variant X` WITHOUT `-Name tutorial_launch` SILENTLY BUILDS THE
  DEFAULT SET** and reports `11 built, 0 failed`, which reads like success — caught only by diffing
  `.text`. ⚠ `RM_GOTOPHASE` (enum 2) is **untouched and UNSAFE** — it arms with `InstallHook()`, a
  standing `ProcessInternal` `.text` patch (the 10/10-vs-3/36 hazard). Use `RM_PHASELADDER`.
- ⚠ The first flight's ladder **starved after A2** when `ReceiveTickClient` stopped being dispatched;
  `KFSNAME=""` (`-any`) fixed it (**508 game-thread hits**). Budget arms accordingly.

### Before touching anything drop- / deploy- / DropPlane- / DropPod- / dismount- / "SpawnPlane faults" shaped
★★★★★ **S132 (2026-08-20) — THE DISMOUNT RUNS. THE HERO LEAVES THE POD AND IS PLACED ON THE GROUND.
Read `docs/s132-dismount-settled.md`, then `docs/fk22-dropphase-reachability.md` §30.**
**SEVEN detach calls across FOUR launches; SIX moved the hero** (flight 1 ×4, flights 2 and 3 ×1 each)
— four of them against a target moving at 20,000 uu/s, one in flight 2 onto a chosen landing actor
where the hero **stands still on real terrain**. ⚠ **Scope the health claim:** the three clients that produced the six landings were alive throughout with **0 crashpad handoffs and 0 `Fatal`** — but a **fourth** launch died in staging (`0xC0000005`, FK-31, and it DID leave a 41 MB minidump at `dumps/crashpad-20260820-143225`) and a **fifth** was killed by the protector (`0x0000DEAD`, FK-32) during an unrelated `play-atlanding` init. Neither death was caused by the dismount; neither is a clean sheet either. Risk class **DATA** — two aligned `TArray`-header
writes plus one element store inside the game's own allocation. **Zero `.text` writes, zero PI hooks,
zero CDO pokes.** Builds: `-Variant dismount` (FLIGHT-1 artifact `.text 03d807ab6d397537`, reproduce
from commit `c2cdc56`; HEAD is `53483e6181bb3583` after the DxState pod-location print) and
`-Variant dismount-landstart` (FLIGHT-2 artifact `0d5fa554edac53c5`). Diff the hash, never the size.
- **THE RECIPE, and it is exactly what S131 predicted:** append the PlayerState to `PlayersAttached`
  (`+0x130` Data / `+0x138` Num / `+0x13C` Max) using the GAME'S OWN `ResizeGrow` at **`0x00F988D0`**,
  then call **`AuthPlayerDetachPlayerFromRidable`** (impl `0x55CCCB0`, thunk `0x5456100`) through the
  S55 direct `UFunction.Func` thunk with `(PlayerState, LandingLocationActor)`.
- ★★★★★ **[M] THE LANDING POINT IS A PAYLOAD FINGERPRINT.** The pod flies at a cooked 20,000 uu/s in
  +X with Y and Z exactly constant. Four calls landed the hero at X = **1,453,041.8 → 4,859,800.1 →
  11,648,502.8 → 14,428,083.3** — the target moved **12.98 million uu** across the four — each matching
  the pod's X at *its own* call time, and **run 2's hero Y is BIT-IDENTICAL to the pod's Y**
  (`5070.4768061953482`, verified by `==` on the raw doubles in a live read, not by a formatted print;
  run 1 is 1 ULP off). Z is **250.0** every time — the ground plane under a pod flying at Z = 20,100.
  **No static explanation survives.**
- ★★★★★ **THE NEGATIVE CONTROL RAN BEFORE EVERY ONE OF THE FOUR AND NEVER MOVED THE HERO** — the same
  detach, same component, same primitive, with `PlayersAttached` EMPTY. The prediction is printed by
  the shim *before* the call, so it cannot be reinterpreted after.
- ★★★ **[M] THE HERO IS HANDED BACK TO PHYSICS.** Before: motionless at `(0,0,13240)`. After:
  consecutive live reads 4.0 s apart give Z `-117,462.8` → `-121,560.9` with X and Y **frozen** — free
  fall, accelerating, no lateral drift. ⇒ `SetActorEnableCollision(true)`, `SetPredropHidden(false)`
  and the `GetLokiCharacterMovement` restore all took effect. ⚠ It falls because the pod had flown
  1.45 M uu off the island by then — a consequence of *when* we called, not a defect.
- ⚠⚠ **THE HANDOFF'S "expect a PARTIAL dismount" WAS TOO PESSIMISTIC.** The teleport
  (`GetLandingTeleportLocation` `0x55D89F0` REAL 963 B → `SetActorLocation`), the un-hide
  (`SetPredropHidden` `0x5599040`, byte `hero+0x1BE8`), the collision restore
  (`SetActorEnableCollision` `0x339A550`) and the movement restore (`GetLokiCharacterMovement`
  `0x55AC8E0`, `vt[+0x3E0](true)`, `[mv+0x1A0]=1.0f`) are **every one a real body**. The two `0xF7EC20`
  folds at `0x55CCD5B` (hero) and `0x55CCE4E` (PlayerState) are **void side effects whose returns are
  never tested**, so neither gates anything.
- **SIX GATES, ALL SILENT, ALL READ OUT BEFORE THE CALL:** 1 `PS != null` · 2 PS not garbage
  (`[PS+0xC]>>30`) · 3 `PlayersAttached` non-empty · 4 PS present in it · 5
  `PS->GetLokiCharacter() != null` · 6 that hero **`IsA(ALokiHeroCharacter)`** (`0x54F8DC0` is
  `IsChildOfUsingStructArray`; the class literal is `LokiHeroCharacter` at `.rdata 0x899A832`).
  The arm calls the reflected `GetLokiCharacter` read-only to measure 5 and walks the class chain for 6.
- ★★★★★ **FREE, LOG-FREE, THREE-WAY RECEIPT: `PlayersAttached.Num`.** `Remove(PS)` at `0x55CCE23` runs
  on **every** path past GATE 4, including the two that skip the hero body. Stays 1 ⇒ bailed at gate
  1/2/3/4. Drops to 0 ⇒ **the body definitively ran past GATE 4.** 0 + hero moved ⇒ full dismount.
  0 + hero did not move ⇒ gate 5 or 6 failed. **Observed 1 → 0 on all four runs.**
- ⚠⚠ **`ContainsPlayer` READS `PlayersInside` (+0x120), NOT `PlayersAttached` (+0x130)** — measured at
  `0x55D0270`. After a correct append it still reads **false**, and that false is EXPECTED. Using it as
  the append receipt manufactures a false negative on a working append. It is a *dispatch* control and
  nothing more; the shim turns the fact into the pre-registered prediction `D2c … MUST still be false`.
- ★★★★★ **THE OBVIOUS SHORTCUT IS DEAD, AND IT WAS CHECKED RATHER THAN ASSUMED [M, strong]:**
  `ULokiRideableComponent::AuthAddPlayer` (member 0) — which would replace the whole append — has impl
  **`0x0F7EC20`**, as do **`AuthRemovePlayer`** and **`AuthSetCanJump`** (plus the already-known
  `AuthPlayerEnterWorldNew`). ⇒ **the component has FOUR empty `Auth*` stubs, not one**, and **the only
  reflected writers of either player array do nothing in this client** — which is why both read
  `Data=0 Num=0 Max=0` in a fully staged world and why a data poke is the only route *by construction*.
  Found independently by the session lead and by an offline recon lane.
- ★ **BONUS [M]:** runs 1–2 passed `nullptr` (detach substitutes `[comp+0xB8]` at `0x55CCCE5`); runs
  3–4 passed the pod EXPLICITLY; all four behaved identically and the arm printed
  `[comp+0xB8] = 0x…870 cls=BP_DropPod_Tutorial_C` ⇒ **`UActorComponent`'s owner is at `+0xB8`** and
  the null-substitution works.
- ★ **The `ResizeGrow` prediction was written offline and confirmed in flight**: `Data=0 Num=0 Max=0`
  ⇒ the `Max==0` branch gives `eax=4`, `cmova` does not fire, `NewMax = 4`, 32 bytes. Logged as
  `AFTER Data=0x… Num=1 Max=4`. On runs 2–4 the arm prints **`Max already covers it -> no ResizeGrow
  needed`** — the run-1 buffer is still live and reused, an incidental confirmation that the allocation
  is the game's own and survives the detach's `Remove`.
  ⚠ Two recon lanes DISAGREED on the ordering (defer the `Num` publish vs increment-first-is-mandatory);
  the adversarial verifier and the session lead independently **refuted the "mandatory" grade** —
  `ResizeGrow` allocates `max(4,Num)` or `Num + 16 + 3*Num/8`, never exactly `Num`, so the +16 slack
  covers either order. **Both work; the shim mirrors the game's order, which is what makes "the ABI is
  correct by construction" an argument rather than an assumption.**
- ⚠ **The detach is SILENT — 0 log strings in its 440-byte extent**, and the flight confirms 0
  occurrences of its name, 0 `failed to get the round game mode`, 0 crashpad handoffs, 0 `Fatal`, and 7
  benign startup `Error`s. ⚠ But `LogLokiRideable` occurs **0** times all session, so the log has **no
  positive control for that category** — the silence is *predicted by the disassembly* and *consistent
  with* the log; the log alone cannot discriminate silent from suppressed.
- ★★★★★ **FLIGHT 2 CLOSED THE ONE OPEN QUESTION AND MADE THE DISMOUNT *USABLE* [M].**
  `GetLandingTeleportLocation` **DOES consume its `LandingLocationActor` argument**. A second launch,
  staged identically, injected `dismount-landstart` (`KDXLANDING=2`) right after Route E while the
  tutorial-start cell was still resident. The arm enumerated **1 candidate over 154,919 objects walked**
  (`BP_LokiPlayerStart_C_UAID_709CD165B93A7B4E02` at `(-3206.4, 5070.5, 100.0)`) and printed its
  prediction before calling. At that instant the two hypotheses were **1,488,146 uu apart** — the pod
  was at `(1428272.5, 5070.5, 20100.0)`. **The hero landed at `(-3206.4, 5070.5, 138.0)`: the
  PlayerStart, not the pod.**
  ★★ **AND IT STAYS THERE.** It settled to `Z = 90.15` (a capsule dropping onto the floor) and held
  `(-3206.4, 5070.5, 90.15)` **bit-for-bit across four samples over 9 s** while the pod flew another
  180,000 uu. `dX = 0.00 uu`, `dY = 1 ULP`, `dZ = -9.85 uu` from the marker. Contrast flight 1, where
  the same hero fell `-117,462 → -121,560` in 4 s because the landing point was over open air.
  ⇒ **the hero exits the pod, is un-hidden, gets collision and movement back, is placed at a chosen
  point on real terrain, and stands there.**
  ★ **Method: when the reference is MOVING, print the reference.** The discriminator exists only
  because the arm prints the pod's live position beside the hero's in every state sample; flight 1
  needed an external RPM read to establish the same thing after the fact.
  ⚠ *How* `GetLandingTeleportLocation` derives Z is still untranscribed (963 bytes); that it consumes
  the actor is measured, the -9.85 uu rest offset is the hero's own capsule settling.
  ⚠ Flight 1's attempt at this found **0 candidates over 143,130 objects** — the cell had streamed out
  by uptime ~860 s — and the arm **refused to substitute the pod silently**. Run this EARLY.
- ⛔ **`AuthPlayerEnterWorld` (`0x55CCE70`) is FORECLOSED as an alternative route [M]** — its two
  terminal actions are direct calls to the stripped `0xF7EB50`, and it performs **zero writes to any
  actor or component transform**. Satisfying its `PlayersInside` guard with a poke would move execution
  past the guards and change nothing about where the hero is.
- ★★ **AND THE DISMOUNTED HERO RUNS [M]** — `play` injected onto the flight-2 client:
  `*** init complete: body=BUILT; camera + WASD active ***`, `PlayAnimation(run, loop) ok`, hero
  **+2,945.7 uu**. ⇒ **the dismount leaves the hero in a state `play` handles normally.**
- ⚠⚠⚠ **BUT "IS THE HERO PLAYABLE *AT THE LANDING POINT*?" IS STILL OPEN, AND THE ARM THAT LOOKS
  LIKE IT ANSWERS IT IS DEGENERATE — MEASURED, NOT PREDICTED.** Two traps, both now closed:
  **(a)** `RM_PLAY`'s FIRST act is a hardcoded ground-teleport to `(-65,-1770,393)`
  (`tutorial_launch.cpp:4822-4830`, applied `:12315`) — **it moves the hero off the landing point
  before anything else happens.** `KNOTELE=1` already existed and skips it.
  **(b) ★★★★★ With the teleport skipped, `play-atlanding` (`0e816d359e5d09c5`) was flown as
  the CONTROL on a hero that had NOT been dismounted — and it moved 2,926 uu at CONSTANT
  Z = 13,240, i.e. 13 km IN THE AIR with nothing underneath it**, because `KFLYMODE` defaults to
  **5 = MOVE_Flying** (S75/S81, to bypass the Walking-mode ground-mantle chain). **It hovers; it
  passes anywhere.** Had it been flown as the treatment after a dismount it would have "walked" and
  meant nothing. ★ Corroboration: plain `play` moved +2,945.7 uu and this control +2,926 uu — the
  distance is a property of the auto-walk driver (~585 uu/s x 5 s), **not of the terrain**.
  ⇒ **only `play-atlanding-walk` (`944a27728053359e`, `-DKFLYMODE=1`) can answer it.** Design,
  pre-registration and the Walking-mode crash caveat: `docs/next-session-prompt-s133.md` §1.2.
- ⚠⚠ **AND A MEASURED DEFECT IN THE DISMOUNT ARM, TO FIX FIRST (one line).** When no PlayerState
  candidate passes GATE 5 the arm currently **proceeds anyway**, on the reasoning that the detach
  takes its REMOVE-only tail. **It faults instead** — `0xC0000005 READ 0xFFFFFFFFFFFFFFFF` at
  `rva 0x54F8C57`: **`GetLokiCharacter` FAULTS on a template PlayerState rather than returning null**,
  so GATE 5 is not a clean early-out for a bad argument. **Make the no-candidate branch REFUSE.**
  ★ The safety design held: SEH caught it, the client survived 428 s, and `D5` detected and removed
  the entry the aborted call had left in `PlayersAttached`.
- ★ **Three dismounts on three separate launches**, plus the four calls of flight 1. Two further
  deaths, both in known classes and neither caused by the dismount: one `0x0000DEAD` protector kill
  (**FK-32**) on the 7th injection into one process, one `0xC0000005` **FK-31 staging** death with only
  `gft`+`fo` resident — the latter DID yield a 41 MB crashpad minidump
  (`dumps/crashpad-20260820-143225`). ⚠ Its image reads `.text` **51.8 %** vs a healthy **53.0 %**,
  which looks like a refutation of *"a crash-era image holds MORE decrypted `.text`"* — **but the
  comparison is NOT matched** (it died at 141 s having exercised far less game code). It does not test
  that hypothesis.
- ⛔ **THIS IS A DIAGNOSIS, NOT A SHIPPING FIX.** It writes a live component's state array by hand
  and drives an authority-only entry point. **Do not add it to the default shim set.**
- ★ **What seven adversarially-verified offline lanes added** (`scratchpad/s132/lanes/`), agreeing
  with the session lead's independent transcription on every load-bearing claim:
  ⚠⚠ **`PlayersAttached` is NOT replicated** (no `CPF_Net`) — which CORRECTS this file's first
  draft and makes the write safer than described, not riskier ·
  ★★ **`0xF7EC20` is `c2 00 00` = `ret imm16 0`, a VOID no-op — it does NOT zero `eax`**; the
  repo's "ret 0" shorthand reads as "returns zero" and will mislead a future grader ·
  ★★★ **the game cannot produce a dismount on its own ⇒ every observable is at a structural
  baseline of 0**, so nothing measured here can be background activity. Its only caller is
  `ALokiDropPod::KickPlayersFromPod`, whose whole body is behind `if (LokiIsClient) return;` with
  `LokiIsClient` hardcoded TRUE. ⚠⚠ **Grade [M, bounded], NOT [M] — the lane's "exactly ONE
  caller" was REFUTED by its own verifier**: `KickPlayersFromPod`'s bytecode carries **TWO**
  `CALLSYS` sites and the rel32 scan found only the second, because the first sits on a page that
  is **all-zero in 30 of 30 images**. ★★ **A rel32 scan over a 55 %-decrypted `.text` is a
  FLOOR, always** — demonstrated here from INSIDE the result. What carries the baseline instead:
  a full-image qword scan finds **exactly one** stored pointer to the impl and one to the thunk
  (so no statically-stored indirect call), and a 69k-asset corpus grep for the name returns
  **zero** files against a **passing positive control**. Both extra callers are in the same dead
  function, so the conclusion survives — only its support changed ·
  ★ **`TArray::Remove` (`0x11F3860`) writes ONLY `Num`** — no free, no realloc — which is why
  runs 2–4 print `Max already covers it` and why a poked buffer is never freed by this function ·
  ⚠ **an unfired crash hazard**: `0x5586530`, called unconditionally on the hero, dereferences
  `hero+0x460 / +0x1978 / +0x1980` with **no null checks** (survived all seven calls on the staged
  `BP_HERO_Ronin_C`; read them first for any other hero) ·
  ⚠ the detach carries `FUNC_BlueprintAuthorityOnly` but its **exec thunk contains no authority
  check**, which is why the S55 thunk route works.
- ★ **Offsets confirmed by two disjoint instruments each** (lane 4): `PlayersInsideCount @0x11C` ·
  `PlayersInside @0x120` · `PlayersAttached @0x130/0x138/0x13C` · `bCanExit @0x118` ·
  `OnPlayersInsideCountChanged @0xE0` · inner = `ObjectProperty`, pointer size 8 · and
  `AActor::bHidden` → `0x68` mask `0x80`, `bAlwaysRelevant` → `0x68` mask `0x08` **exactly** as the
  S132 handoff predicted — so the two-sided bool control is well-founded.
  ⚠⚠ **BUT `FBoolPropertyParams` carries NO `ByteOffset`/`ByteMask`/`FieldMask` fields** — the
  engine derives them by calling the record's `SetBitFunc` on a zeroed buffer, so a decoder written
  against the assumed field list reads padding. The shim reads **live `FBoolProperty`** objects
  (`+0x70..+0x73`), which is the right route. ⚠ And `ALokiDropPod::LokiRideable @0x6C8` is a
  **Blueprint-generated** component property — no offline instrument can produce its offset; resolve
  it BY NAME on the live class (which the arm does).
- **Regression gates, verified after every edit:** `play` `9bc10a4552c596e1` · `dropplane_b1only`
  `5b4467b0105dec1a` · `droppod-pe-cdopoke` `249a3cd2190eb334`, and **`dismount` is byte-identical to
  the artifact that produced all four results** even after the `KDXLANDING=2` code was added.
  ⚠ `dismount` and `dismount-podland` share a `.text` **size** (126,976 B) — **diff the hash, never the size.**
- ⚠⚠ **`usmapdump dumpimage` NEEDS THE `.exe` SUFFIX.** Given `SUPERVIVE-Win64-Shipping` it prints
  `ERROR: process … not found (is the game running?)` **while the client is alive**; given a bare PID it
  prints `module "<pid>" not found in PID <pid>`. Both read as *the game is dead*. **Check
  `Get-Process` before believing either.**
- ⚠ **The stager's `-Probe` path is `tools\sigbypass-mod\build\…`, not `build\…`**, and `-AllowStale`
  is required for the deployed `fo`/`sp` pair.
★★★★★ **S131 (2026-08-20) — THE POD IS FUNCTIONAL. IT IS INITIALISED, ALIVE, AND FLYING — IN THE WRONG DIRECTION. Read `docs/s131-pod-functionality-settled.md`.**
The census counts OBJECTS; S131 built the in-arm readout that looks at what the object IS. One armed window, **zero `.text` writes**.
- ★★★★★ **[M] `InitializeDropPod` RAN and all three discriminating writes LANDED**, against a **within-run, same-class, same-instrument negative control of three other pods** that all read class defaults in the same dump: `PodTeamIndex` **-1 → 0** · `CurrPodDestination` **(0,0,0) → (-3206.4, 5070.5, 100.0)** · `bIsTeamLeaderPod` **False → true**. ⛔ `LeaderPod` is a TRAP (null→null) and is not a fourth check.
- ★★ **`CurrPodDestination` is a PAYLOAD FINGERPRINT and it is worth more than the census.** It holds the exact `LandingLocation` this arm computed and passed — no other code path in the process has that number. ⇒ **when a control is unavailable, look for a field whose VALUE is unique to your call.** That is what rescues the result from the standing E0c marshaller-control gap (unchanged since S130, so it cancels in the differential).
- ★★★★★ **THE POD FLIES AT EXACTLY 20,000 uu/s AND EVERY DIGIT IS ACCOUNTED FOR.** Live: `ComponentVelocity = (20000.0, 0, 0)`, Y and Z **exactly** constant, `attach=none`, measured 19,862 uu/s over 8.0 s while all three control pods read **0.0**. The cooked asset says `ProjectileMovement_GEN_VARIABLE: InitialSpeed = MaxSpeed = 20000, ProjectileGravityScale = 0`. ⚠⚠ **NEAR-MISS: 20000 is also this shim's `KPDSPAWNZ`.** Blaming our own knob would have been effortless and wrong — **the cooked asset is what settles it.**
- ★★★★★ **AND IT FLIES *BECAUSE* `StartPodGameplay` NEVER RAN** — whose FIRST act on the movement component is `Deactivate()`. [M] on the pod: `bHasStartedGameplay=0`, `PodMeshComponent=null`, `DropPodState=0(None)`, `bIsLocalPlayerPilot=0`, `bSteeringEnabled=0`. Root cause is a stripped stub: **`Loki::LokiIsServer()` impl `0x0F7EB60` = `xor al,al; ret` — always FALSE** (`LokiIsClient` impl `0x0B9E1F0` = `mov al,1; ret` — always TRUE). In `ALokiDropPod::LokiBeginPlay_Implementation`, `0x596A3F9 call 0xF7EB60` + `test/jne` skips `0x596A495 call 0x56FBCF0` = `LokiTeam::SetTeamForActor` ⇒ no team index ⇒ `OnTeamIndexChanged` never fires ⇒ `StartPodGameplay` never called ⇒ nothing deactivates the mover.
- ★★ **INDEPENDENT ENGINE RECEIPT:** `LogNiagara: Warning: NiagaraComponent(...BP_DropPod_Tutorial_C_2147471134.NS_Drop_CloudTunnel...) required LWC tile recache` ×3 (CloudTunnel / Clouds / Thruster). The pod's drop VFX are instantiated and TICKING, and UE independently reports it travelled far. Exactly one `BP_DropPod_Tutorial_C_<n>` appears in the whole log — the E1 pod.
- ★★★★★ **AND THEN THE FIFTH WALL WAS CONFIRMED [M] IN THE SAME SITTING, FOR ZERO EXTRA LAUNCHES.**
  Read `docs/s131-pod-functionality-settled.md` **§10**. The client was still up at ~40 min with the world
  staged, so a new mode **`RM_RIDEABLE` (enum 29)** called `AuthPlayerEnterWorldAttachedToRidable`
  **DIRECTLY** on the pod's own `LokiRideable` component with a **live, valid PlayerState**. Result, against
  a verified baseline of **0**:
      `LogLokiRideable: Error: ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable failed to get the round game mode`
  **count 0 → 2 — exactly one per call.** ⇒ the body REACHES `0x55CD572`, gets 0 from the stripped
  `0xF7EB50` round-game-mode getter, and takes its failure branch **with valid arguments**. S130's offline
  "REAL body, ALWAYS-FAIL" grade is now MEASURED.
  ★ What makes it a measurement: a **positive control on the same object through the same primitive**
  (`ContainsPlayer`, `fault=no`), **both of the wall's own IsValid preconditions read out and PASSING**,
  **two independent PlayerStates**, a verified zero baseline, and an exact per-call count.
  ★ **FREE BY-PRODUCT: the log CATEGORY is now named — `LogLokiRideable`.** S131 lane 4 had it as
  COVERAGE-BLOCKED (its `FLogCategory` ctor is on a never-decrypted page). **Driving the path named it** —
  the S118 method again: push the code path, then read what the game says.
  ⭐ **AND THE OBVIOUS LEVER WAS KILLED BY ONE READ-ONLY COMMAND BEFORE ANY ARM WAS BUILT:**
  “poke `[TeamState+0x688]`” is dead — **[M] ZERO live instances of any class containing `TeamOnly`**, and the
  only `TeamState`-named live object is `Comp_TeamState_GlobalShop_GEN_VARIABLE`, a template. **Check a
  lever's precondition with a read-only pass before building the arm.**
  ★ A refusal that prints its candidate table is not a wasted run: the first build declined to guess between
  2 PlayerStates and made no call, but its pod table still showed the never-finished DEFERRED pod has
  `LokiRideable = 0x0` — a second confirmation of the null-`RootComponent` finding on a different property.
  ⇒ **The blocker is now precisely stated:** a stripped server-side getter, same family as FK-1's four empty
  stubs, sitting between a fully working pod spawn and a rider ever boarding. Next question is OFFLINE and
  free: what does `0xF7EB50` replace here, and is there any other route to a round game mode on this client?
  Build: `build.ps1 -Name tutorial_launch -Variant rideable` — `.text` **`e221e4e415834067`**.
- ★★ **AND THE WALL IS SHARED, NOT ONE FUNCTION'S BUG [M]** (`docs/s131-pod-functionality-settled.md` §11).
  A third injection into the same client called two entry points nothing had ever called.
  **`AuthPlayerPreSpawnOnAddToPlane` (impl `0x55CD800`, REAL) fails the SAME WAY** — its own distinct bail
  string (`.rdata 0x8B1CE28`) went **0 → 2**, one per PlayerState. ⇒ two different entry points, valid
  arguments, one stripped round-game-mode getter. **Fixing "the wall" means fixing ONE GETTER, not one
  function** — same family as FK-1's four empty server-authority stubs.
- ⚠ **`AuthPlayerEnterWorld` (impl `0x55CCE70`, REAL) is a NAMED GAP, not a negative.** Called twice with
  all four slots bound (`PlayerState, Location, EffectClass=null, bRepositionPlayer=1`): **no fault, no log
  line, hero did not move** (`(0,0,13240)` before and after), `PlayersInsideCount` 0→0, `bCanExit` 0.
  The pre-registered rule was *"no movement AND no line ⇒ UNINTERPRETABLE"*, and that is the record.
  ★ What IS established: it dispatched, and **it did NOT hit the round-game-mode wall** — no such line
  appeared for it while R1's and R3's did in the same run. So it bails at one of its OWN guards, before
  any logging point. **Transcribing `0x55CCE70`'s prologue guards is the next offline task and it is free.**
- ⚠⚠ **A CONTROL I REGISTERED WAS FALSIFIED BY MY OWN ARM'S DESIGN.** I predicted the `AttachedToRidable`
  count would STAY at 2 as a cross-contamination control; it went **2 → 4**, because `KRDARMS` bit 1 was
  still set and **the arm re-ran R1**. The separation it was meant to test holds anyway (different strings,
  1.3 s apart). ★ **Check a control against what THIS arm does, not against what the previous arm did.**
  Build: `.text` **`dd2281adce965add`** (`KRDARMS=0x3F`, `KRDREPOS=1`) — the v3 arm with R3/R4.
- ★★★★★ **AND R4'S GAP WAS CLOSED OFFLINE THE SAME HOUR — IT REMOVES A LEVER (`§12`).** Two blockers, both [M]:
  **(a)** `AuthPlayerEnterWorld` requires the PlayerState to be ALREADY IN `PlayersInside`:
  `0x55CCEC2 mov rcx,[rcx+0x120]` / `0x55CCEC9 movsxd rax,[rdi+0x128]` / `0x55CCED7 je <bail>` on an
  empty array, then a linear `cmp [rcx],r12` search that `jmp`s to the same bail if not found — **both
  bails SILENT.** Confirmed BY NAME on the live component: `PlayersInsideCount` IntProperty **@0x11C**,
  `PlayersInside` ArrayProperty **@0x120 size 16**, and live it reads **Data=0, Num=0, Max=0** with
  neither PlayerState present. ⇒ R4 bailed at `0x55CCED7`; the null is NAMED, not uninterpretable.
  **(b) ⛔ IT CALLS THE SAME STRIPPED GETTER.** `0x55CCF22 call 0xF7EB50` (RVA recomputed with a machine;
  `0xF7EB50` re-disassembled as `33 c0 c3`). It differs from the attached variant only in NOT gating on
  the result — it carries the 0 forward and proceeds to a virtual call through `[PlayerState+0x470]`.
  ⇒ **`AuthPlayerEnterWorld` is NOT a way round the wall**, and the obvious poke (point
  `PlayersInside.Data` at a buffer, `Num=1`, call, restore) **was NOT run** — its payoff collapsed once
  (b) was known, and its risk is real (a `TArray.Data` pointing at non-game-heap memory means any
  `Empty()`/`RemoveAt()` on the success path frees a foreign pointer).
  ⇒ **[M] ONE GETTER, THREE CONSUMERS**: `AuthPlayerEnterWorldAttachedToRidable` (gates on it),
  `AuthPlayerPreSpawnOnAddToPlane` (gates on it), `AuthPlayerEnterWorld` (consumes it un-gated).
  **There is no sibling left to try** — that was worth checking and it is now checked.
  ★ **Method note: driving the path is what made this readable.** Those pages entered
  `dumps/merged4.dump.exe` only because R4 executed them; the analysis that closed the gap was possible
  BECAUSE the "uninterpretable" call was made.
- ★★★★★ **AND THE OFFLINE FOLLOW-UP FOUND A DATA-CLASS LEVER. Read `docs/next-session-prompt-s132.md`
  "THE REAL §1", then `scratchpad/s131/lanes2/`.** Two independent lanes agree.
  **[M] The wall is ONE CALL and the value it fetches is DEAD.** The function is 746 B, fully decrypted,
  and downstream of `0x55CD572` there are **11 call sites / 10 targets and ZERO folds**. Register-liveness
  over the fallthrough (every instruction, capstone `regs_access`) shows **ZERO reads of RAX** ⇒ the round
  game mode is a **PRECONDITION, not a data dependency**.
  ⛔ **No poke can ever satisfy the getter**: `0xF7EB50` is `33 c0 c3`, three bytes, **zero memory
  operands**. ⛔ A `Func` swap is dead too — thunk `0x5456380` has **0 direct callers** and the game's own
  AS callers reach the **impl by rel32**.
  ★★★ **THE ROUTE: the wall's only persistent COMPONENT-state output is `PlayersAttached.Add(PS)`**
  (⚠ corrected — it ALSO moves the character via `LokiTeleportActor` + `SpawnAndMoveLokiCharacter_
  MoveStep` and stamps `[hero+0x1C10]`; **actor position is not transient**) (`+0x130`/`+0x138`/
  `+0x13C`), and **`AuthPlayerDetachPlayerFromRidable` (impl `0x55CCCB0`, thunk `0x5456100`, 440 B) is gated ONLY
  on that array being non-empty.** ⚠⚠ **CORRECTED (§14.1): it is NOT fold-free — it carries TWO
  `0xF7EC20` (`ret 0`) calls at `0x55CCD5B` and `0x55CCE4E`**, the first on the HERO immediately after
  the `IsA(ALokiHeroCharacter)` gate. "zero `0xF7EB50`" is true and is NARROWER than the headline it
  was supporting. Expect a PARTIAL dismount, and read any null as locating one of those two. It
  un-hides the hero, resolves the landing location and places the character. **The dismount is one
  append away.** Recipe (risk class DATA, 0/22): mirror the wall's own tail using the GAME's own
  `ResizeGrow` `0xF988D0` so the buffer is the game's, then S55-call the detach. ⚠ MEASURED live:
  `PlayersAttached` reads `Data=0 Num=0 Max=0`, so `ResizeGrow` IS needed — it is an arm, not an RPM write,
  and `0xF988D0` is **not a UFunction** so the S55 primitive does not apply to it.
  ⚠⚠ **ORDERING TRAP:** do NOT poke `PlayersInside` (`+0x120`) first — it makes `HasEverContainedPlayer`
  true, which turns the wall itself into a SILENT no-op and destroys the error-line receipt.
  ⚠ **The pod will NEVER self-drive**: `LokiIsClient` impl `0x0B9E1F0` = `mov al,1; ret` (hardcoded TRUE)
  and `LokiIsServer` impl `0x0F7EB60` = `xor al,al; ret` (hardcoded FALSE), so
  `ALokiDropPod::KickPlayersFromPod` — the pod's own exit driver — returns immediately, always.
- ★★★★★ **AND THE STRIPPED-CODE POPULATION IS NOW MEASURED, 16,277 records, 12/12 controls passing**
  (`scratchpad/s131/lane-d-empty-impl-census.tsv`): **REAL 11,517 (70.8 %) · DARK 3,092 (19.0 %) ·
  FORWARDER 1,153 (7.1 %) · EMPTY 515 (3.16 %; 4.28 % of gradeable)**.
  ★★ **A FIFTH FOLD EXISTS: `0x00FC6CF0` = `0f 57 c0 c3` = `xorps xmm0,xmm0; ret` → 0.0f**, 13 records
  incl. six `ALokiPlayerState` float getters. **A census graded against only the four known folds
  under-counts. Add it to the fold table.**
  ⚠⚠ **FK-1's "1.2 % (78/6,669)" is a UNIT ARTIFACT, not an error** — it counted *distinct exec
  thunks*, which are heavily ICF-folded (`0x5254180` is the registered thunk of 92 records). Per record
  it is 3.16 %; in FK-1's own unit it is **170**, not 78. **FK-1's conclusion — an empty impl is
  informative, not ambient — STANDS.**
  ★★★ **THE ENRICHED CATEGORY IS `Auth*`, NOT "drop"**: `Auth*` gradeable **67/158 = 42.4 %** vs
  non-`Auth` Loki **8.30 %**, Fisher **p = 1.6e-28**, over 41 classes — and it is the NAMING CONVENTION,
  not the reflection flag. Against the FAIR control (the rest of the Loki table) the drop-8 classes are
  **14.6 % vs 9.83 %, p = 0.11, NOT SIGNIFICANT.** ⇒ **there was no decision to remove *deploy*; there
  was one decision to remove *server authority*, and deploy is inside it like everything else.**
  ⇒ **BOUNDED for deploy** (~23 stubs, enumerated, almost all pure state mutations a data poke can
  substitute for), **UNBOUNDED for gameplay** (~200 across 40+ classes). ⚠ The census is **blind to
  Angelscript entirely** — 0 records for `ALokiDropShip`/`ALokiDropPod` — so it says nothing about the
  half that actually works.
- ★★★★★ **THE ROUND GAME MODE EXISTS, IS LIVE, AND PASSES THE WALL'S OWN TYPE CHECK [M]** — measured on
  the staged client, and it reframes the whole blocker. `Comp_GameMode_DropPlane_Tutorial +0xE0` caches
  it, written by an UNSTRIPPED lifecycle override (`0x55CE140`, `ULokiGameModeDropPlaneComponent`) that
  reads `World->AuthorityGameMode` and `IsA<ALokiRoundGameMode>`-checks it with **the same helper
  `0x55C7DD0` the wall calls**. Live:
      `+0xC0 WorldPrivate = LVL_Tutorial` · `World+0x250 = BP_LokiGameMode_Tutorial_C` ·
      `World+0x258 = BP_LokiGameState_Tutorial_C` (control) · `+0xE0 = BP_LokiGameMode_Tutorial_C`
  ⇒ [M] **`UWorld::AuthorityGameMode @ UWorld+0x250`** (control `+0x258 = GameState` in the same read);
  the object is the one S124 flew `GoToPhase` on; and **it PASSES `IsA<ALokiRoundGameMode>`** — the
  cache is written only on that check's success side. **Never measured before.**
  ⇒ **If the stripped getter had returned it, the wall's own IsA would have passed too.** The framing
  is not "a client has no round game mode" — it is **"one accessor was deleted while the object and
  the type check survive"**. ⛔ Still not injectable (`0xF7EB50` has zero memory operands).
  ★ Free live pointer for any future call site that consumes one: `Comp_GameMode_DropPlane_Tutorial+0xE0`.
- ⚠⚠ **AND THAT SAME OFFSET WAS A LANE'S REFUTED HEADLINE** — see `docs/s131-pod-functionality-settled.md`
  §13. One lane claimed `ULokiRideableComponent+0xE0` caches it; **[M] on THAT class `+0xE0` is
  `OnPlayersInsideCountChanged`, a 16-byte delegate, and reads ZERO on all three live components.** It
  had the function and the mechanism right and the CLASS wrong, from a vtable walk it flagged in the
  same paragraph as UNRESOLVED ("3142 slots, which is nonsense") and graded [I, strong] — then stated
  the consequence as [M]. ★★ **Two agents given the same region disagreed about one offset, and it was
  only visible because BOTH PRINTED THE OFFSET. Diff their offsets; a silent agreement is worth much
  less than a caught contradiction.**
  ★ Free corrections: **`GetLandingTeleportLocation` is REAL** (`0x55D89F0`, 963 B, 0 folds — FK-22 §2.5
  has it COVERAGE-BLOCKED); **`UWorld::AuthorityGameMode @ UWorld+0x250`** [M] (control: `GetGameState`
  → `+0x258` in the same pass) — the round game mode object EXISTS, only the accessor was deleted.
- ⚠⚠ **THE FIFTH WALL WAS *NOT* TESTED, AND THE ZERO THAT LOOKS LIKE A TEST IS A TRAP.** The precondition IS met (the pod ships a `LokiRideable_GEN_VARIABLE`; the rideable census rises **+1 per pod**, 20→21 on E1), so `AuthPlayerEnterWorldAttachedToRidable` WAS called — but its impl `0x55CD510` opens `test rdx,rdx; je` on **`rdx = PlayerState`** and **returns SILENTLY on instruction #1** when it is null. `PilotPlayerState` reads null [M] because `GetTeamDropLeader` returns null because `ALokiTeamState_TeamOnly::SetDropLeader` is one of FK-1's four empty stubs. ⇒ `grep "failed to get the round game mode"` = **0 and UNINTERPRETABLE.** ★ The emit is NOT stripped (dispatches through the live logger `0x106B650`), so the grep would work if the branch were reached.
  ⇒ ★ **NEXT LEVER, ONE DATA POKE:** `ALokiPlayerState::IsSpawnTeamLeader` (impl `0x56C2060`, real) is a **pure read of `[TeamState+0x688]`**. Poke that on a live `ALokiTeamState_TeamOnly` and `GetTeamDropLeader` returns non-null without calling either stub — then the rider handoff runs for real.
- ★ **[M] A pooled DEFERRED spawn never `FinishSpawningActor`'d has a NULL `RootComponent`** (`root=0x0`), with the same class resolving `RelLoc@0x158` by name on three sibling pods in the same dump — a positive control living inside the negative result.
- ★ **[M] The pooled-spawn NULL is gone:** `Failed to spawn actor of type` = **0** while `PrimePools : Feature is not enabled, skipping` still prints — S130 §25 confirmed live, from the opposite direction.
- ★★★★★ **THE ANGELSCRIPT `ADDSi`/`LoadThisR` OPERAND IS A BYTE OFFSET FROM `this` — [I] → [M].** Offline: the AS ctor's 50-op operand sequence and the AOT-compiled x86 ctor's 50 `add rax,imm` sequence are **ORDERED-IDENTICAL, 50/50**, replicated **12/12 classes / 214 pairs**; 9,468 annotated ops over 312 files give **784 (typeid,member) pairs with ZERO offset conflicts**. Live, the probe then agreed with it **76 : 0** (agree : DISAGREE). ⇒ **the `.as.txt` listings are a free, reliable offset oracle for every Angelscript member**, including the ones UHT cannot see. ⚠ `propscan`/`boolscan` returning 0 on an AS name is **COVERAGE-BLOCKED, not absent** — AS member names have **0** byte occurrences in the image.
- ⚠ **`bHasStartedGameplay` has NO UPROPERTY**, so by-name resolution fails every time; the AS offset `0x4B8` is the only route. The probe prints `NOT RESOLVED BY NAME` as a distinct state and never as a value.
- **Offsets, all [M] this session:** `bPilotHasPodControl 0x45C` · `bIsTeamLeaderPod 0x45D` · `PodTeamIndex 0x460` · `bIsLocalPlayerPilot 0x464` · `ImpactIndicator 0x468` · `CurrPodDestination 0x478` · `AttachedCrewPods 0x490` · `bSteeringEnabled 0x4A0` · `LeaderPod 0x4B0` · `bHasStartedGameplay 0x4B8` · `PodStateEvent.DropPodState 0x540` · `PodMeshComponent 0x638` · `PilotPlayerState 0x3C0` (LokiDropPodBase, UHT) · `AActor::Owner 0x150` · `RootComponent 0x1B0` · `USceneComponent::RelativeLocation 0x158` · `ComponentVelocity 0x1A0`.
- **Instrument:** `PdPodDump()` in `tutorial_launch.cpp`, wired into RM_DROPPOD **and** RM_POOLSPAWN; pure guarded reads; **no extra `GUObjectArray` sweep** (the pod set is latched during the census that already runs — one sweep costs 1.2–2.6 s of game thread). Calibration `bCanEverReplicate→0x6C` / `bEnablePooling→0x2D3` **PASS on every dump**. Readers: `scratchpad/s131/tools/pod_live_read.py` (read-only RPM), `pod_verdict.py` (evaluates a marker against the pre-registration).
- ⚠⚠ **AND THE VERDICT TOOL SHIPPED THE PROJECT'S OWN DOMINANT DEFECT:** `pod_verdict.py`'s field regex had ONE literal space where the probe prints `@0x%-4X` (two spaces for a short offset), matched nothing, and printed **`UNINTERPRETABLE (nothing resolved)` for pods whose values are plainly in the log.** Caught only by reading the raw marker beside the tool's output. **An analysis script is an instrument too.**
- ⚠ **A stager abort is NOT a dead launch.** Launch 2's force-open was swallowed because the **lobby map took 146 s to load** and `fo` fired mid-`LoadMap`; the process was healthy and re-running `fk24-stage.ps1` on the same PID produced the entire result. **Check `Get-Process` before spending another launch.**
- ★ The armed window lasted **>25 min** with the client alive throughout — long enough for external RPM reads AND a `dumpimage`, which contributed **+43 `.text` pages / 157,916 bytes, 0 conflicts** to the new **`dumps/merged3.dump.exe`** (drop-path code never decrypted before). **Do this every armed window.**
- ⚠ Build arms moved: `droppod-pe-cdopoke` **`249a3cd2190eb334`** · `droppod-pe-cdoctrl` **`61fd0745c23e89f0`** · `poolspawn-cdopoke` **`efe8db553bf511ba`** · `poolspawn-cdoctrl` **`85f3cee44c31b1cd`**. `play` **`9bc10a4552c596e1`** and `dropplane_b1only` **`5b4467b0105dec1a`** are UNCHANGED — the new latches are gated on `kRunMode` for exactly that reason. ⚠⚠ An **ungated** `strstr` in the shared `DpEvalClass` moved `b1only`'s hash while leaving its `.text` **SIZE identical** (120,832 B both ways — it fitted in section padding). Caught only because the hash was compared.
- ⚠ Still open: **C8/C9 never fired** (unexercised, not excluded); the **E0c** marshaller control still has no candidate; and nothing drove `SetDropPodState`, whose own `LokiIsClient` early-return forecloses it on this client anyway [M].

★★★★★ **S130 (2026-08-20) — FK-22's BAIL 2 IS FIXED. ONE BYTE. THE DROP POD SPAWNS.**
**`SpawnDropPodForTeam` returns TRUE and the DropPod census moves +2** (S127 measured `false` / `+0`), and both pooled spawns return live `BP_DropPod_Tutorial_C` actors (`dP1 +1`, `dP2 +2`; S128 measured NULL / `+0`). **The lever is `CDO->bCanEverReplicate = 0` on the drop-pod CDOs** — one heap byte, readback-verified, **zero `.text` writes**. Read `docs/s130-actor-pool-gate-settled.md` §13 and `docs/fk22-dropphase-reachability.md` §28.
- ★★ **The leaf CDO is now MEASURED**: `Default__BP_DropPod_Tutorial_C` reads 1 in a staged world (it is NOT loaded at the menu, which is why §12 could only infer it). **Nothing in the chain is inferred any more.** Poke: 3 written, 3 readback-verified, root control `Default__Actor` untouched at 1, and **the poke persisted across two further DLL injections**.
- ★★ **THE POOL WAS STILL DISABLED THE WHOLE TIME** — `bSupportsActorPoolPriming` untouched, `PrimePools` never called — and the pooled spawn produced actors anyway. That confirms the §25 refutation **live**, from the opposite direction.
- ⚠ **Two verdicts, and both belong in the record.** The census attribution passed; the **E-VERDICT** says `E1 RAN BUT IS NOT ATTRIBUTABLE` because E0c — the control for the `[UFunctionVtable+0x378]` marshaller — is **unsatisfiable** on this class chain. That is about the **dispatch mechanism**, not about whether pods appeared, and **it was identical in S127, so it cancels in the differential.** ★ The `poolspawn` arm carries no such caveat at all (native static, S55 direct thunk, `P0c` STRONG PASS 0.00 uu on |ref|=8377, `0xA5` sentinel overwritten) — **that arm alone settles C7.** ⛔ Do not write “Route E is proven to marshal correctly.”
- ⛔ **THIS IS A DIAGNOSIS, NOT A SHIPPING FIX. Do NOT add it to the default shim set.** It mutates a **class default** for the process lifetime and may break the pod's replication — which is exactly what the flag exists to declare. ⚠ And **C8/C9 simply did not fire; they are unexercised, not excluded**, and nothing shows the spawned pods are functional.
- ⚠ **Cost: four launches for one armed result.** 1 died 9 s after `fo` (FK-31); 2 and 3 staged, armed and died **silently at the same ladder position** (artifact-less class, no dump). ★ **Re-reading S127's own census is what unstuck it** — its successful flight reads `DropShip=1` because it injected `dropplane_b1only` FIRST; mine read `DropShip=0`, so I had omitted a precondition. ★★ **And the better response was to stop needing it: `RM_POOLSPAWN` tests C7 with no ship, no plane and no ProcessEvent, and it was available the whole time.**
- Builds: `poolspawn-cdopoke` (`.text 8d4a81045820ebec`) / `poolspawn-cdoctrl` (`4e9c12ae866f5359`) · `droppod-pe-cdopoke` (`bc1c1a5b1e66b54a`) / `droppod-pe-cdoctrl` (`780da72fbf4d34e7`). ⚠ `PdCdoFlags`' single GUObjectArray pass costs **~2,000–2,300 ms on the game thread** (measured and printed) and runs twice per arm — budget for it. The first cut did FOUR passes; that was fixed before it ever flew.

★★★★★ **S130 — THE ACTOR POOL IS ***NOT*** THE BLOCKER, AND THE POOL GATE IS NAMED.
Read `docs/s130-actor-pool-gate-settled.md`, then `docs/fk22-dropphase-reachability.md` §25 — and §26, which SETTLES the NULL.**
★★★★★ **AND C7 IS SETTLED — OFFLINE, NO LAUNCH. THE NULL IS `bCanEverReplicate` (`docs/s130-...md` §11, `fk22-...md` §26).**
- **[M] `C7 @ 0x564820C`: `cmp byte ptr [CDO + 0x6C], 0 ; jne -> NULL`.** `UClass+0x178` = `ClassDefaultObject` [M, via `UGameplayStatics::GetClassDefaultObject` impl `0x589BB40`, an independent function]; **`AActor+0x6C` = `AActor::bCanEverReplicate`** [M, walked `AActor`'s own **114-entry** `PropPointers` array at `FClassParams 0x07F227E0` with per-type decoding, three controls passing — `bAlwaysRelevant`/`bHidden` `0x68`, `bEnablePooling` `0x2D3` — plus `binds_members.csv:21044` as a second instrument].
- **[M] `AActor::AActor` (`0x3371800`) sets it TRUE: `0x03371841 mov byte ptr [rdi+0x6c], 1`.** Neither `BP_DropPod_Tutorial` nor `BP_DropPod` overrides it (`bpdump @props`, populated dumps), and the cooked AssetRegistry effective value is `true`. ⇒ **the pooled spawn refuses the drop pod deterministically — primed or not, any machine, any world.**
- ★★ **AND THAT IS BAIL 2, END TO END:** `LokiDropShip.as:153` calls `SpawnPoolableActorFromClassDeferred(TeamDropPodClass, ...)` and wraps EVERYTHING in `if (v6 != null)` with **no else** ⇒ null → whole body skipped → `SpawnDropPodForTeam` returns false. **No reference to the actor pool is needed anywhere in the explanation.**
- ★★ **THE CONTROL THAT BROKE THE FIRST READING AND THEN CONFIRMED IT:** `BP_GemV2` — pooled in the log, and the ONE class Angelscript opts into pooling — **also reads `true`**, which would make pooling inert. The joint distribution over 36,625 Blueprints settled it: **pooling∧¬replicate = 80** · pooling∧replicate = 96 · ¬pooling∧replicate = 23. **The 80 are ALL cosmetic projectile visuals** (`*_ProjectileCosmetics`, `BP_Freeze_IceDart_*`, …), and `ALokiHeroHeightIndicator`'s ctor shows the idiom in one place: `mov byte [rbx+0x6c], dl` (dl=0) **and** `mov byte [rbx+0x2d3], 1`. ⇒ **the pooled API is for non-replicated cosmetics; a drop pod is not a legal argument to it.**
- ✅✅✅✅✅ **FLOWN — THE RUNTIME CDO BYTE **IS** THE COOKED DEFAULT, SO C7 FIRES AND THE LAST [I] IS NOW [M]** (`docs/s130-...md` §12, `fk22-...md` §27). **One clean `-NoHook` MENU launch, read-only RPM, zero injection, no tutorial staging.** `tools/re/cdo_flag_readout.py`, predictions written in BEFORE the run: **8/8 passed, 0 failures.** `Default__Actor` **1** · `LokiDropPodBase` **1** · `LokiDropPod` **1** · `BP_DropPod_C` **1** · `LokiGem` **1** · `BP_GemV2_C` **1** · `LokiHeroHeightIndicator` **0** · `BP_HeroHeightIndicator_C` **0**.
  ★★ **Two-sided control on `+0x6C`** (six read 1, two read 0, split exactly along the cooked value; the probe declares the run VOID if they all match). ★★ **`Default__Actor+0x6C = 1` is the disassembly and the live process meeting on ONE BYTE** — `AActor::AActor 0x03371841` predicted it. ★★ **An UNPREDICTED second two-sided control appeared:** `Default__Actor+0x2D3 = 0` while every poolable class reads 1, independently confirming `+0x2D3` is `bEnablePooling`.
- ⚠ **The LEAF was not read directly** — `Default__BP_DropPod_Tutorial_C` is **not loaded at the menu**. It rests on all three ancestors reading 1 live + [M] it overrides neither flag + the cooked→runtime mapping validated **3/3 in both polarities**. **[M] for the ancestors; the leaf is one inheritance hop of inference.** Only staging a tutorial world closes it outright.
- ★★ **AND A TRAP FELL OUT OF THE FAILED FIRST RUN: `LogActorPooling: Adding <X> to list of poolable actors` DOES NOT LOAD THE CLASS.** All 176 registrations are an **AssetRegistry query against cooked tags**; none of the four BP CDOs existed on the first probe, against **10,371 live CDOs**. ⇒ **“registered as poolable” is NOT evidence a class is loaded** — it would silently corrupt any census keyed on those log lines. Surfaced only because the probe printed `NOT LOADED (this is NOT a zero)` instead of reading offset `0x6C` of a null.
- ⚠ **Sharper, not solved:** gems read **1** too ⇒ the pooled spawn returns NULL for them as well. The gem call site is `LokiGem.as:168 `**`SpawnExtraGemWithTeam`** — an *extra*-gem spawner — but **whether the primary gem path uses it is UNESTABLISHED** (no survey done; the name is suggestive, not evidence). Moot for FK-22: the pod's only route is `SpawnDropPodForTeam`.
- ★ **REPAIR (the runtime read CONFIRMED 1): poke `CDO(BP_DropPod_C)+0x6C = 0`** — prefer `BP_DropPod_C` over the leaf, which may not be loaded when a shim runs (live at `0x241BA0290E0` on the S130 run; ASLR-dependent, re-derive) — one aligned byte on a CDO, the safest measured write class, free readback — then Route E `SpawnDropPodForTeam`. ⚠ It is a CLASS DEFAULT: it affects every pod for the process lifetime and may break replication. A→B→A with the DropPod census as readout; **not** a default-set shim.
- ⚠ **C8/C9 are now UNTESTED, not excluded** — C7 returns before either is reached. Expect the next wall there.
- ⚠ **`extractor bpdump <asset> @props` was gated behind the asset having UFunction exports**, so a DATA-ONLY Blueprint (exactly what `BP_DropPod_Tutorial` is) printed `No matching UFunction '@props' found` — which reads as “the asset has no such property” and is not. **Fixed** (`Program.cs:1137`); validated by re-dumping a known-good asset first.
Offline; zero launches, zero injections, zero `.text` writes. Six adversarially-verified lanes.
- ⚠⚠⚠ **§23.3's suspicion is REFUTED — an unprimed pool CANNOT return NULL [M].** The acquire's
  lookup `0x334E7A0` is a **`TMap::FindOrAdd`** (one `ret`, inserts on a miss, never null), and a pool
  miss falls to a **shipped fallback** — `.rdata 0x08B06440 'Failed to find an actor in the pool for
  %s, spawning a new instance from scratch.'` — then `0x5648E48 call 0x39C3DB0` = `UWorld::SpawnActor`
  and returns the fresh actor. ⚠ **That message's emit is STRIPPED** (`0x5648D6F` → the `ret 0` fold
  `0x00F7EC20`, 4,972 call sites), so **its absence from the logs is uninterpretable**, not negative.
- ★★ **THE GATE IS `ALokiGameState::bSupportsActorPoolPriming`, a `bool` at `ALokiGameState+0x898`
  [M].** `ULokiActorPoolManager` vtable slot 90 (`0x08877A80+0x2D0 → 0x56363F0`, multiplicity 1)
  returns `Cast<ALokiGameState>(GetWorld()->GameState)->bSupportsActorPoolPriming`. Named from the UHT
  `FBoolPropertyParams` at `.rdata 0x08983A50` whose **`SetBitFunc 0x053800D0` = `mov byte
  [rcx+0x898],1; ret`** (multiplicity 1); the **only** bool UPROPERTY at that offset image-wide
  (13,156 Bool records swept). **`UWorld+0x258 = UWorld::GameState` [M]** — confirmed by
  `UGameplayStatics::GetGameState` (`0x38047F0`), a third unrelated function.
- ★★ **AND THE CAUSE IS A SHIPPED ASSET, NOT CODE [M]:** the C++ ctor sets it TRUE
  (`0x05676F10 c6 87 98 08 00 00 01`), and `bpdump_BP_LokiGameState_Tutorial_PROPS.txt:52` serializes
  **`bSupportsActorPoolPriming = False`**. 3 of 6 GameState BPs override it and **all three to False**
  (`_Tutorial`, `_PvE_Holdout`, `_FFA`). ⇒ the pool is off in the tutorial **by design, in data**.
- ⛔ **NO INI ROUTE [M].** `CPF_Config` clear; **0 of 155** `ALokiGameState` properties are config;
  **`ActorPoolManagerPrimingConfig` is a USTRUCT with ZERO reflected properties and no UHT consumer**
  (the S129 handoff's “strongest lead” is INERT); neither pool-manager UCLASS is a config class.
  Turning pooling on = **DATA poke `GS+0x898=1` + raw direct call `PrimePools` (`0x3356000`)**, which
  is **not reflected**, has **one caller** (`ALokiGameState::BeginPlay`, vtable slot 119 — already run
  and skipped) and performs **zero module-image writes**. Handles: `GS+0x428` = cached manager,
  `+0x430` = its class. ⚠ **But that is not known to fix FK-22.**
- ★ **The pooled spawn never reads the gate [M]** (3 disjoint methods). Thunk `0x537EEE0` → impl
  **`0x566FF50`** → `0x5647F00` → acquire **`0x5648050`** (real extent `..0x5648EC6` = **3,702 B**, 3
  chained `.pdata` rows — ⚠ `strxref func` reports **per-ROW** extents, never function size).
  Deferred thunk `0x537F1A0` → impl `0x5670090` → acquire **directly**.
- ★★ **THE SURVIVING NULL CAUSES ARE C7/C8/C9, and a FREE RECEIPT already narrowed it [M]:** the
  non-deferred wrapper logs `Failed to spawn actor of type %s.` (`.rdata 0x08B06390`) on NULL, and it
  fired **twice** in S128 naming `BP_DropPod_Tutorial_C`. It is emitted strictly downstream of the
  outer preconditions ⇒ **World, GameState, `IsA(ALokiGameState)` and the manager fetch ALL PASSED.**
  Remaining: **C7 `CDO->byte@0x6C != 0`** (`0x5648210`) · **C8 `PoolMgr->GetWorld()==null`**
  (`0x5648D97`) · **C9 `SpawnActor` null / skipped at `0x5648E34`** (`0x5648E6F`).
  ★ **C7 is settleable with ONE read-only RPM read** of `CDO(BP_DropPod_Tutorial_C)+0x6C` — no launch.
  ⚠ [I] the **deferred** arm's null is **SILENT** (it bypasses the wrapper): 2 warnings ≈89 s apart =
  **one per injection**. Do not read "no warning" as a deferred-arm result.
  ★ **Grep `Failed to spawn actor of type` before any inference here** — `Feature is not enabled` is
  ambient (68 occurrences / 69 files); this one is per-attempt.
- ★ **S128's collision-confound elimination STANDS [M]** — the result files print `Collision=2
  (declared enum 'ESpawnActorCollisionHandlingMethod')`, `NumParms=8`, enum name read live off the
  FProperty. (A lane's inferred signature omitting a collision param is [I] and wrong.)
- ⚠⚠ **THE HAND-SPAWN BYPASS HAS A FIFTH WALL [M]:**
  `ULokiRideableComponent::AuthPlayerEnterWorldAttachedToRidable` (impl **`0x55CD510`**) is a REAL body
  that ALWAYS fails — `0x55CD572` calls the stripped fold `0xF7EB50` (`33 c0 c3`) and bails into
  *"failed to get the round game mode"*; its dead tail has **zero** external rel32 entries in three
  images. Same wall on `AuthPlayerPreSpawnOnAddToPlane` (`0x55CD800`); `AuthPlayerEnterWorldNew` is an
  empty fold. ⇒ **a hand-spawned pod gets a pod and no rider.**
  ⚠⚠ **STILL TRUE OF THE MOUNT, AND NO LONGER THE WHOLE STORY — S132.** The wall blocks getting a
  rider ON. It does **not** block getting one OFF: `AuthPlayerDetachPlayerFromRidable` (impl
  `0x55CCCB0`) is REAL, references no round game mode at all, and was **flown six times** — hero out of
  the pod, un-hidden, collision and movement restored, placed at a chosen landing actor on real terrain.
  ⇒ read this line as *"a pod and no rider **through the mount**"*. `docs/s132-dismount-settled.md`.
- ★★★ **FREE NEW INSTRUMENT, WORTH MORE THAN THE FINDING: the `.data` `{name_ptr, exec_thunk, impl}`
  record table gives a REAL/EMPTY verdict WITHOUT the code page being decrypted** (the fold addresses
  are known constants). ⇒ **§2.5's 16 COVERAGE-BLOCKED `(class,func)` keys are an instrument limit,
  not a fact**, for at least 6 of them (the five `AuthPlayer*` + `GetLandingTeleportLocation`, all on
  page `0x5456000`). Re-running it over all 100 keys is **free, offline and unstarted**.
  ⚠ Its negative control is **degenerate** — Angelscript names have **zero byte occurrences** in the
  image, so "AS functions have no record" is a fact about name storage, not about the record table.
- ⚠⚠ **REFUTED sub-claim:** `AuthSetSpawnTeamLeader`'s flag feeds **three** Angelscript readers, not
  one; one (`QueueCrewForPodSpawn`) is on the leader-pod path. "The bypass avoids FK-1's stubs" holds
  **only under `bIsTeamLeaderPod == false`** — and the route transcribed from `SpawnDropPodForTeam`
  passes `true`. Same incomplete-enumeration failure `fk22` already recorded **on this exact family**.
- ⚠ **`fkdis.py findptr` CAPS AT 200 ROWS** — a row count from it is a **floor, never a count**.
  Uncapped this session: `0x0F7EC20` **165,789** · `0x0B9E1F0` **26,444** · `0x0F7EB50` **27,217** ·
  `0x12C7260` **2,823**. And **`fkdis.py d` prints a BLANK result on a non-instruction-boundary rva**,
  which reads exactly like an undecrypted page and is not.

★★★★★ **THE BLOCKER MOVED TWICE ON 2026-08-16 AND BOTH MOVES ARE MEASURED. It is NOT the markers
(refuted) and NOT the phase (solved) — it is THE SUBSCRIPTION.** `docs/fk22-dropphase-reachability.md` §15.
- **[M] Reaching `EGP_Lineup(6)` is NOT sufficient.** The round drove all the way to `Combat` and the
  drop phase never fired: the only drop lines in the whole session are three **startup**
  `LogActorPooling` registrations (`BP_DropPod_Tutorial_C`, `BP_DropPod_C`, `BP_DropPod_Child_C`).
- **[M] `BP_AuthSetCurrentPhase(6)` broadcast into a 7-subscriber list and produced ZERO effect** —
  `Setting Phase to 7 (Combat)` stayed at **1**, `DropPod` at 3, `DropPlane` at 2. `Num=7` was re-read
  immediately before the call, so the "hard no-op" gate did not apply and the call really did run.
- ★★★★★ **AND THE REASON IS MEASURED, NOT INFERRED: the DropPlane component IS NOT SUBSCRIBED.**
  A read-only walk of the `FMulticastScriptDelegate` at `GS+0x590` (`Data=0x1B408640880`, `Num=7`,
  `FScriptDelegate` stride 16, indices resolved through `GUObjectArray`) lists 7 real objects —
  `[0] 0x1B361978F80 Comp_GameMode_ShopKeepers`, `[1] 0x1B3857EA4C0` **the GameMode itself**, and five
  others. **`Comp_GameMode_DropPlane_Tutorial` is `0x1B3771413C0` and is NOT among them.**
  ⇒ **A5's null is NOT a statement about the handler's behaviour** — it was never reachable.
  Recording it as "phase 6 does not drive the drop phase" would have been a textbook instrument artifact.
  ⇒ ★ This gives `§10.3`'s `ServerOnly` hypothesis its first live support: the *consequence* it predicts
  (no subscription on the client route) is measured.
- ⚠⚠ **A BROADCAST'S NULL IS UNINTERPRETABLE UNTIL YOU ENUMERATE THE SUBSCRIBERS.** `Num > 0` proves the
  list is non-empty, **not** that your target is in it. Walk the invocation list — it is one read-only RPM.
- **Next levers, ranked:** (1) make the bind happen — grade `ULokiBlueprintLibrary::ServerOnly`'s impl and
  read what it tests; if it reads a role/NetMode byte on a client-resident object, that is a DATA poke.
  (2) **Call the handler DIRECTLY** on the live component `0x1B3771413C0` (reflected UFunction, byte arg,
  S55 primitive) — separates "not subscribed" from "subscribed but inert". (3) **Call `SpawnPlane`
  directly**: §2.1 measured it branchless and §0/§7 measured its three markers PRESENT in `LVL_Tutorial`,
  so the S93 fault should not reproduce — and it needs no phase at all.
★★★★★ **FK-22 IS RESOLVED (S124, 2026-08-16) — read `docs/fk22-dropphase-reachability.md`.** Offline:
**zero launches, zero injections, zero `.text` writes.** The belief at `coverage-audit-s101.md:269`
(*"Drop-in / DropPlane — **FALSIFIED as reachable** — `SpawnPlane` faults on absent level markers"*)
is **FALSE AS WRITTEN**. ⚠ It does **NOT** flip to "reachable" — it becomes **OPEN with two measured
blockers, neither about markers.**
- ⚠⚠ **`SpawnPlane` IS NOT ONE FUNCTION. [M] The three `Comp_GameMode_DropPlane*` classes are
  SIBLINGS** — all three print `SuperStruct -> /Script/Loki.LokiGameModeDropPlaneComponent`, each
  defines its **own** `SpawnPlane` override, and there is **no BP-to-BP inheritance in the family.**
  ⇒ an S93 measurement on the `_Tutorial` override **cannot transfer to the general component by any
  mechanism.** This is the load-bearing structural fact and it is independent of reachability.
- ★★ **[M] The GENERAL variant queries no markers at all** — `Comp_GameMode_DropPlane_C::SpawnPlane`
  is **9 bytecode entries, 0 `GetAllActorsWithTag`**; the real spawn lives in **`OnDeathCircleSet`**
  (125 entries), which derives the plane path **procedurally from the death-circle radius** and also
  has 0 `GetAllActorsWithTag`. It does not even *have* `GetAutoDropLocation` — S93's second
  observation is about a function the general component does not own.
  ⚠ But **2 of 3 variants DO read markers**: `_PvE_Holdout`'s `SpawnPlane` is a **byte-twin** of
  `_Tutorial`'s (49 entries, same six `EX_NameConst`, differing in 2 diff hunks). The *general* one
  is the odd one out — do not restate this as "tutorial-only".
- ★★★★★ **[M] THE MARKERS EXIST IN `LVL_Tutorial`, AND `Skylands_WP` HAS NONE — the census returned
  the OPPOSITE of its expected answer.** `TrainingStart` → cell `D0E5AKNE…`, `PlaneStartPoint` →
  `8MF6M4K4…`, `PlaneEndPoint` → `4WUJ1QA2…`, three **separate** World Partition cells under
  `Maps/Tutorial/LVL_Tutorial/_Generated_/`, as literal `Actor.Tags` entries. `LVL_Holdout` carries
  all three; **`Skylands_WP` carries 0 in 2,216/2,216 parsed packages.** Denominator: **7,300 `.umap`
  packages** (unit: packages), 7,300 parsed / 0 failed. ⇒ **S93's stated reason — "markers that don't
  exist outside the real deploy" — is refuted on the very map it was measured on.**
  ⚠ **Present-in-map ≠ streamed-in at call time.** Only the first is established; cell load order was
  never measured, and that is now the natural successor hypothesis.
- ★★ **[I, strong] S93's observation is ALSO confounded at the instrument.** Its `FAULTED` is only the
  boolean returned from a bare SEH `__except` (`tutorial_launch.cpp:955`, `:4146`), and `CallBPGuarded`
  **memcpys a captured live `FFrame` without reinitialising `0x48..0x78`** (`FlowStack`/`PreviousFrame`).
  `SpawnPlane` is the **only** one of the three functions S93 compared that uses the flow stack —
  **3 push / 2 pop, vs 0/0 for both that "ran clean."** The confound tracks the result exactly and was
  never controlled. ⇒ *"null-deref reading `GetAllActorsWithTag` markers"* is an **attribution laid
  over an SEH catch**, not a measurement of a fault site.
- ⚠⚠ **THE TWO REAL BLOCKERS, both [M], neither about markers:**
  **(a) THE ROUND PHASE NEVER ADVANCES** — `Setting Phase to` occurs **193 times across 564 log files
  and all 193 read `1 (BeginInit)`**, while the drop needs phase ≥ 4 (`EGP_SpawnSelect`) and the
  component's handlers act on 5/6/7 (gate value **`EGP_Lineup = 6`**).
  ⚠⚠ **SHARPENED SAME DAY — do NOT restate this as "the phase machine never leaves BeginInit".**
  That over-reads the corpus. `Setting Phase to %d (%s)` prints **`GoToPhase`'s ARGUMENT**, emitted
  *before* the old==new test, and `GoToPhase` is its **sole emitter image-wide** (exactly one `lea`
  xref to the record at `0x8b20dc8`). ⇒ **193/193 measures that `GoToPhase` was only ever INVOKED
  with 1 — a fact about its SEVEN CALLERS**, not about the stored byte. Separately [M]: the only
  compiled store to `CurrentPhase` (`+0xA44`) in the decrypted `.text` is a **constructor init**
  (`0x56772CF`). ⚠ **Bounded — 45 % of `.text` is undecrypted and `CurrentPhase` is REPLICATED**, so
  the net serializer writes it by computed-offset memcpy that no literal-displacement scan can see.
  **The honest form is "no compiled runtime store exists in the decrypted image", never "the byte can
  never change".** ★ The corpus is therefore evidence about the **call sites** — `0x55f37a4`,
  `0x56146d5`, `0x560a104`, `0x560a174`, `0x560a1a2`, `0x560aa72`, `0x5613300` — and enumerating them
  is free and unstarted.
  **(b) 13 of 100 `(class, func)` keys** over the 8 drop classes are **empty C++ impls** (direct call
  to the universal fold `0xF7EC20 = c2 00 00 = ret 0`), sitting exactly at the player→plane
  (`ALokiDropPlane::AddPlayerToPlane`) and pod→hero (`AuthBeginGlideDiveFromDropPod`) handoffs.
  Full split: REAL 51 · BlueprintImplementableEvent 14 · EMPTY 13 · **COVERAGE-BLOCKED 16** · inlined 4
  · const-body 2. ⚠ **`ALokiDropPlane::AddPlayerToDropPlane` DOES NOT EXIST** — `AddPlayerToPlane`
  (plane, EMPTY) and `ULokiGameModeDropPlaneComponent::AddPlayerToDropPlane` (component, REAL) are
  different functions. S93 called the real one.
  ⚠⚠ **The 5 `AuthPlayerEnterWorld*` entry points are COVERAGE-BLOCKED, not absent** — all five sit on
  `.text` page `0x5456000` ⚠ **-- STALE since `merged10`: that page reads 3,860/4,096 = LIT, so all
  five are READABLE OFFLINE TODAY and "COVERAGE-BLOCKED" no longer applies** -- **together with plain getters**
  ⇒ the blocked/covered split there is a **page boundary, not a semantic one.** "No C++ route exists to
  put a player on a rideable" is **not-looked-at**, and reading it as absent would be an artifact.
- ★ **[M] `TeamDropPodClass` is satisfied from shipped data** — `Default__BP_DropPlane_Base_C` sets it
  to `BP_DropPod_C`, whose SuperStruct is `/Script/Angelscript.LokiDropPod`. And **[M]
  `SpawnDropPodForTeam` has exactly two bail points and NO marker query of any kind** — its two
  `FVector` args are the only spatial input. **[M] the dropship can be skipped**: `InitializeDropPod`
  touches `DropShip` only inside `if (bIsTeamLeaderPod)`, and `QueueCrewForPodSpawn` null-guards first.
  ★ **`BP_DropPlane_Straight_Tutorial_C` → `BP_DropPlane_Base_C` → `/Script/Angelscript.LokiDropShip`**
  closes the open question at `docs/angelscript-dropphase.md:961`.
- ★★★★★ **THE TWO PHASE-WRITE IMPLS ARE GRADED — BOTH REAL, NO AUTHORITY GUARD, AND NEITHER WRITES
  THE PHASE (S124, same day, `docs/fk22-dropphase-reachability.md` §8-§9).** Offline; two independent
  graders by disjoint routes, each adversarially verified, then every load-bearing byte re-read by the
  session lead with both gold polarities reproduced.
  `ALokiRoundGameMode::GoToPhase` thunk `0x5457200` (**fold 1**) → impl **`0x5601020`** (0x271 B,
  `40 55 53 56 57 41 57 …`) = **REAL**. `ALokiGameState::AuthSetCurrentPhase` (registered
  **`BP_AuthSetCurrentPhase`**) thunk `0x53878d0` (fold 1) → impl **`0x567a160`** =
  `48 81 c1 90 05 00 00 e9 …` = `add rcx,0x590; jmp 0x442B4C0` = **REAL**. Neither equals any fold
  (`0xF7EC20 c2 00 00` / `0xF7EB50 33 c0 c3` / `0xF7EB60 32 c0 c3`, all re-read in the same pass).
  Both are `Final|Native|Public|BlueprintCallable` with `FUNC_BlueprintAuthorityOnly` **clear**, and a
  full disassembly of `GoToPhase`'s 0x271 bytes accounts for every branch with **zero role / NetMode /
  HasAuthority reads** ⇒ **callable today by the S55 primitive, no `.text` write, no PI hook.**
  ⚠⚠ **BUT "REAL" IS NOT THE GREEN LIGHT — NEITHER FUNCTION WRITES `CurrentPhase`.** `GoToPhase`'s
  phase write is `0x56011CA: e8 51 da 97 fb` → **a DIRECT call to `0xF7EC20` = `ret 0`**, the stripped
  server setter (rel32 machine-resolved). `BP_AuthSetCurrentPhase` is
  **`OnRoundPhaseChanged.Broadcast(N)` and nothing else** — the `0x590` displacement is visible in the
  instruction itself, independently pinning the delegate. `GetCurrentPhase` = `movzx eax,[rcx+0xA44];
  ret` independently pins **`CurrentPhase` @ `ALokiGameState+0xA44`**.
  ⇒ **What is drivable is the NOTIFICATION half of a phase change, not the value.** Three levers:
  **(a)** `BP_AuthSetCurrentPhase(6)` broadcasts the delegate the Tutorial mode binds in
  `ReceiveBeginPlay` (handler tests `NewPhase == 6` → PlayerArray loop → `AddPlayerToDropPlane`);
  **(b)** `GoToPhase(N)` fires the `[vtable+0xb08]` virtual with `(new, old)` and — because
  `CurrentPhase` never advances — the `old != new` gate passes for **any** N, so it is **re-firable at
  will**; **(c)** the stored byte as a **DATA poke** at `+0xA44`, this project's safest write class
  (nothing 0/22 · bytecode 0/9 vs standing `.text` 7/8), with `GetCurrentPhase` as a free readback.
  ⚠⚠ **ORDERING IS LOAD-BEARING AND THE OBVIOUS RECIPE IS SELF-DEFEATING.** *"Poke `+0xA44`=N then
  call `GoToPhase(N)`"* is foreclosed by `GoToPhase`'s own `cmp r14b,dil; je` — with the poke applied
  it jumps to the epilogue having done **nothing** (no fold call, no logs, no virtual). **Correct
  order: poke `+0xA44`=N then `BP_AuthSetCurrentPhase(N)`** (no equality test), or `GoToPhase(N)`
  **first** and poke after.
- ★★★★★ **THE PHASE LADDER IS NOT A FLAT WALL — IT IS A SELF-DRIVING TIMER LADDER WITH TWO
  ALREADY-RUNNING NATIVE GATES, AND ONE BYTE IS THE WHOLE DIFFERENCE (S124, `…fk22…md` §10-§11).**
  `GoToPhase` has **7 non-thunk callers** (rel32 sweep reproduced **set-identical three times**:
  session lead + 2 agents; `0x545726B` is the exec thunk's own `P_FINISH`, not a caller):
  | site | containing fn | arg | status |
  |---|---|---|---|
  | `0x55F37A4` | `AActor` vtable slot 119 / disp `0x3B8` = **BeginPlay** | **1** BeginInit | **fires today — this IS the 193/193 corpus** |
  | `0x56146D5` | `0x5614690`, via `0x560AF10` | **2** Pre | **gated** |
  | `0x5613300` | `AActor` slot 170 / disp `0x550` = **Tick** | **4** SpawnSelect | **runs every frame, ONE condition unmet** |
  | `0x560A104/174/1A2/AA72` | timer bodies off `OnNewPhase` | 9 / 2 / 3 / 6 | never run |
  **[M] The two gates and exactly what is unmet:**
  **1→2** (`0x560AF10`): `MatchStartDetails` non-empty (FString @ **`GameState+0x738`**, RepNotify) ·
  `+0xA44 == 1` · `+0x790 == 0`. ★ A **REAL, fold-1, BlueprintCallable writer exists** —
  `ALokiGameState::SetSharedMatchStartDetails` thunk `0x538AB40` → impl **`0x56A0A40`**
  (`add rcx,0x738; call 0xFA2190`). ⚠ Its flags carry `FUNC_BlueprintAuthorityOnly`, which
  `ProcessEvent` enforces and a **direct `UFunction.Func` call does not** — [I], untested.
  **3→4** (Tick `0x5613200`): `GameMode+0x7C0 == 4` · `+0xA44 == 3`. ★★ **The non-phase half ALREADY
  SUCCEEDS in real runs** — `LogLokiGameModeInitializer` walks `Starting→…→Finished` **189–193 times**
  corpus-wide. ⇒ **the ONLY unmet condition for `GoToPhase(4)` is `CurrentPhase == 3`.**
  ⇒ **[M] the single byte at `GameState+0xA44` is the whole difference between a frozen ladder and a
  self-driving one** — one aligned data poke on a reflected property of a client-resident object, with
  `GetCurrentPhase` as a free readback.
  ★ **`ERoundPhase` read out of the binary** (10-dword table at `.text 0x56012B8` → `.rdata 0x8B20CB0`):
  **0 ServerStartup · 1 BeginInit · 2 Pre · 3 FinishInit · 4 SpawnSelect · 5 SpawnReveal · 6 Lineup ·
  7 Combat · 8 Post · 9 Shutdown.** ⚠ That table is indexed by phase VALUE; `OnNewPhase`'s own table is
  indexed by **phase−1**. Do not conflate them.
  ★ **And the early-out is passable for every `N ≠ 0`**: the ctor sets `+0xA44 = 0` (`0x56772CF`, and
  `0x5676B01 xor r12d,r12d` is the sole `r12` definition in that chained function), and corpus-wide
  `Setting Phase to 1 (BeginInit)` **and** `Transitioning from phase (…EGP_ServerStartup) to phase
  (…EGP_BeginInit).` each occur **193 times over the SAME 193 files, one each** — and **both gate on
  the same verbosity byte `0xA036D00` at the same threshold**, machine-verified at both sites, which is
  what makes the pair discriminating rather than a verbosity accident.
- ★★★★★ **`[vtable+0xB08]` IS `ALokiRoundGameMode::OnNewPhase` — RESOLVED [M], verified by the session
  lead from the artifact.** `.data` record **`0x9C1F328`** = `{name→"OnNewPhase", thunk `0x5457480`,
  impl `0x330C56C`}`, and the bytes **at** `0x330C56C` are `48 8b 01 ff a0 08 0b 00 00` =
  `mov rax,[rcx]; jmp qword ptr [rax+0xB08]`. Record layout validated on a known answer two slots
  earlier: **`0x9C1F298`** = `{"GoToPhase", 0x5457200, 0x5601020}`. ⇒ **lever (b) dispatches into real
  phase-handling code and is OPEN.** ⚠ Read these from a **single-state** dump (`dumps/tutorial-hero`),
  never `merged2` — `.data` is mutable and merged2 splices it.
  ⚠ Still UNRESOLVED: `[vtable+0xB00]` (called from `OnNewPhase`'s Lineup case when
  `ModeSupportsDropPlane()` is false) — no reflected UFunction of the class resolves to it.
- ⚠⚠ **`GoToPhase`'s extent is `0x5601020..0x56012E0` = `0x2C0` B across 3 chained `.pdata` rows.** The
  `0x271` figure recorded above is the distance to the first bail block, **not** the function size.
  Cite `tools/strxref/index/pdata_union.csv`; the dumps' own `.pdata` section is all zeros in every image.
  ⚠ **The rel32 caller sweep is NOT exhaustive** — it covers only the **16,638 of 30,281 `.text` pages
  (54.95 %)** decrypted in `merged2`. Demonstrated from inside the result: `0x5614690`, *one of the
  seven callers*, is a **zero page in 15 of the 16 single-state dumps** and survives only because
  `dumps/toggles` was merged. **For the dark 45 %: COVERAGE-BLOCKED, never ABSENT.**
  ⚠ **Two things to settle BEFORE spending a launch, both cheaper than one:** read `Num` at
  **`GameState+0x598`** (zero subscribers ⇒ lever (a) is inert — one read-only RPM), and
  `bpdump BP_LokiGameMode_Tutorial ExecuteUbergraph_BP_LokiGameMode_Tutorial` **offset 8046** (~40 s) —
  `ALokiTutorialGameMode` inherits the **base** `OnNewPhase` with **no phase-4 branch** (unlike BR's
  `cmp dl,4`), so on the tutorial route that Blueprint body **is** the entire payload of `GoToPhase(N)`
  above the timers, and it is currently unknown. Also **[I], unverified**: whether the Tutorial mode's
  delegate bind really sits behind `ULokiBlueprintLibrary::ServerOnly`.
  ★ **Pointer recipe for any of this:** GameMode from `World->AuthorityGameMode`; **GameState from
  `[GameMode+0x258]`** — the offset `OnNewPhase` itself uses at `0x5608FB8`.
  ⚠ **The callee at `0x56011CA` is UNIDENTIFIED** — its body is `ret 0` [M], but `0xF7EC20` has
  **5,095 direct call sites**, so the address identifies nothing, and it is **not** the registered
  `BP_AuthSetCurrentPhase` (whose impl `0x567a160` has exactly one caller: its own thunk). **Do not
  write it up as "`AuthSetCurrentPhase` is what `GoToPhase` calls."**
  ⚠ **This does NOT reopen FK-1** — `SpawnPlayer` and the four server-authority stubs are untouched;
  reaching `EGP_Lineup` *behaviour* still terminates at those empty impls for the pod/hero handoff.
  ⚠ `.rdata` ships the refusal `"We're ALokiRoundGameMode but aren't using an ALokiRoundGameMode!"` —
  verify the live object exists before calling; do not assume.
  ★ **Free receipts `GoToPhase` emits for you:** `Setting Phase to %d (%s)` and `Transitioning from
  phase (%s) to phase (%s).` — **no session has ever produced either with a value other than 1.**
- ⚠⚠ **FK-22's OWN ERROR WAS RE-COMMITTED THREE TIMES BY THE AGENTS AUDITING IT** — "exclusive to the
  Tutorial variant" (PvE_Holdout is a byte-twin), "those actors exist in `Skylands_WP`" (true of one
  class, false of the other), "precisely the actor-authority API" (three counter-examples in its own
  table). **Generalising from the variants you opened to the ones you did not does not stop being the
  failure mode when you are the one auditing it.** All three were caught by adversarial verification.
- ⚠ **`docs/angelscript-dropphase.md:895/:901` ALREADY SAID "the plane's path does not need level
  markers"** and "the S93 wall has a documented bypass" — while `coverage-audit-s101.md:269` still read
  FALSIFIED. The repo half-contained this answer and never propagated it. ⚠ Do not cite that bypass
  list unqualified: one entry, `ALokiDropPlane::OverridePlaneLocations`, is one of FK-1's four dead stubs.
- ⚠ **The ignorance map miscited the belief as `coverage-audit-s101.md:229` for ~23 sessions. It is
  `:269`.** Fixed 2026-08-16.
- ★ New instrument artifacts from this work are in `docs/method-rules.md` §1 (S124-a/b/c) — notably
  **never census a runtime behaviour over a corpus containing the binary that declares its vocabulary**
  (the enum table guarantees a hit for every value), and **an IoStore `.names.txt` is NOT a presence
  test for a serialized property — use `bpdump @props`.**

### Before touching anything Angelscript- / deploy- / respawn- / "the ceiling" shaped
★★★ **FK-1 IS SETTLED (S113, 2026-08-09) — read `docs/fk1-angelscript-settled.md`.** S74's
*"only 18 classes are Angelscript … the native deploy/round core is the irreducible blocker …
**accept the ceiling**"* (commit `19db6a2`) is **REFUTED**, and so is the ceiling.
- ★★ **The script layer is AOT-TRANSPILED TO C++ and compiled into the exe ("StaticJIT") — it is not
  interpreted.** 1463/1463 cache function Ids appear as `mov edx,imm32` registration-stub immediates
  (control 0/4000); a **1,459-row symbol table** (script fn → raw / `_VMEntry` / `_ParmsEntry` RVAs)
  was recovered; bodies live at `.text 0x059128B0–0x05A7F070`. ⇒ script UFunctions are CALLABLE.
  ⚠⚠ **BUT NOT BY THE S55 DIRECT-THUNK RECIPE — "callable by the existing S55 recipe, unchanged" was
  the old text here and it is MEASURED FALSE.** An Angelscript `UFunction` has **`Func @+0xE0 = 0x0`**
  (`docs/fk22-dropphase-reachability.md:1697`: `SpawnDropPodForTeam … Func @+0xE0 = 0x0 *** NULL ***`,
  against a same-run non-null control), so the direct thunk call dereferences null.
  ★ **The working route is `UObject::ProcessEvent`, vtable displacement `0x270` = SLOT 78**
  (`fk22:1774`, three agreeing instruments: 3,651 `.rdata` vtables hold it at `+0x270`; the UHT stub
  `0x54532B0` does `mov rbx,[[rcx]+0x270]`; 32 sampled classes all carry it at slot 78). Flown at
  `fk22 §21.2`. ⚠ Cite the DISPLACEMENT, not an RVA — `fk22` prints two different ProcessEvent RVAs
  (`0x1344E10` at `:1774`, `0x3396280` at `:2174`, different images/bases); `0x270` is the part both
  agree on. ⚠ **`Func != ProcessInternal`, so the PI hook
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
  **`dumps/merged10.dump.exe` (16,755 pages, 55.33 % — the current best; `merged8` 16,714 is one
  generation behind and `strxref.py`'s built-in default `merged2` is TWO)** or
  `dumps/tutorial-hero` (16,112, 53.21 % — best single image, and by itself 96.5 % of the union).
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
  is `NtCreateThreadEx`. ⚠ **INDEX-BASE AMBIGUITY, FLAGGED NOT RESOLVED (S132):** FK-10 describes the **4th entry** of the `packer0 0x1831C0` table as `NtCreateThreadEx`, while S132 describes the `0xDEAD` kill primitive as **slot 4** of the same 5-method table. Those reconcile only if one is 0-indexed and the other 1-indexed. **Neither source states its convention**, so do not build on either index until one is re-read from the bytes. Caught by an independent verifier, not by either author. `preloader.dll` is ELIMINATED (0 occurrences; control: 2 in runtime.dll).
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
has no guards, so it works where `ProcessEvent` no-ops for native functions.
⚠⚠ **"slot-56 `ProcessEvent`" was the old text here and is STALE — `ProcessEvent` is at vtable
displacement `0x270` = SLOT 78** (`docs/fk22-dropphase-reachability.md:1774`, three instruments).
⚠⚠ **AND THIS PRIMITIVE DOES NOT REACH ANGELSCRIPT UFUNCTIONS** — theirs have `Func @+0xE0 = 0x0`
(`fk22:1697`). Native UFunction → S55 direct thunk. **Angelscript UFunction → ProcessEvent slot 78.**
BP-bytecode UFunction → `CallBPGuarded`. Three routes; picking the wrong one reads as a dead function.
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
  ⚠⚠ **CANONICAL POINTER MOVED — `dumps/merged10.dump.exe` EXISTS AND IS AHEAD: `.text`
  **16,755 / 30,281 = 55.33 %** (its own manifest `dumps/merged10.dump.exe.txt:19`), and
  `docs/fk22-dropphase-reachability.md:7` already publishes it (`0x5456000` 3,860/4,096 non-zero
  there). `merged9` also exists. ~~**Use `merged10` for any new offline grading.**~~
  ★★ **SUPERSEDED TWICE: `merged12` (S136) and now `dumps/merged13.dump.exe` (S137). USE
  `merged13`:** 16,800 / 30,281 pages = **55.48 %**, VERIFIED STRICT SUPERSET of `merged12` before
  the default was moved — pages lost **0**, gained **+28**, byte conflicts on shared pages **0**.
  ⚠ **`mergedumps` printed "44 pages" for what it TOOK FROM DONORS; the coverage delta is +28.**
  Those are different quantities and only the second is a coverage claim.
  It is the ONLY image in which `ALokiBotController::OnPossess 0x5565470` (0/4096 → 3782/4096) and
  `::Tick 0x556E9F0` (0/4096 → 3509/4096) are decrypted — a run against `merged12` or earlier still
  grades both DARK. **`strxref.py`'s `DEFAULT_DUMP` was moved to `merged13` in S137** (it had been
  `merged12`, i.e. one generation behind, which is the recurring defect this line exists to catch).
  ⚠⚠ **AND `tools/strxref/strxref.py:66` STILL DEFAULTS TO `merged2` (54.95 %)** — so every
  un-flagged `strxref.py func` run in this project has been grading against an image ~1.7 pp behind
  HEAD, which is exactly how a LIT function reads as dark. **Pass the image explicitly, or fix the
  default.** ⇒ before believing ANY "this page is dark" claim, re-grade against `merged10`
  (S134 audit: **47 of 55** such claims re-grade stale, and `regrade_blocked.py`'s own DARK control
  `TryJoinQueue` now reads LIT — the re-grade protocol itself needs re-grading).
  ★★★★★ **THE (superseded) S133 POINTER: `dumps/merged8.dump.exe` — `.text` **16,714 / 30,281**
  decrypted pages (**55.20 %**), measured 2026-08-20, and it is EXACTLY the union of all 33 state
  images on disk (union∖merged6 = 0, merged6∖union = 0, byte-granular audit 0/0/0 defects).
  Ladder: `merged` 15,833 (52.29 %) → `merged2` 16,638 (54.95 %) → `merged3` 16,681 → `merged4`
  16,683 → `merged5` 16,689 → `merged6` 16,694 → `merged7` 16,707 → **`merged8` 16,714** (S133). Read `docs/fk20-coverage-settled.md` and
  `docs/fk18-fk19-multistate-merge-settled.md` before touching any of this.**
  ⚠⚠ **`merged2 = 16,625 / 54.90 %` vs `16,638 / 54.95 %` — BOTH ARE REAL, and calling either a
  typo is wrong.** `docs/fk18-fk19-multistate-merge-settled.md:16-18` states it explicitly: §1–§10
  are measured on the **11-input** union (**16,625**, and that pre-registration is bit-exact), then a
  still-running process was folded in (§11) taking the **artifact on disk** to a **12-input** merge at
  **16,638**. `strxref.py:855-856` ships both rows. ⚠ What IS stale is the ~14 **undecorated** copies
  elsewhere that quote 16,625 while pointing at the file. **Cite the artifact as 16,638 and say which
  input set you mean.**
  ⚠ **Ten captured images sat unmerged for six days** because manifests name donors by BASENAME
  only (`merged2.dump.exe.txt` lists `SUPERVIVE-Win64-Shipping.dump.exe` twelve times, which
  identifies nothing). **Run `python tools/re/dump_coverage_ledger.py` after every capture** — it
  reads bytes, not manifests, exits 1 on an orphan, and was validated in both directions.
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
   blind spot recorded as a property of the game. **103 tabulated instances as of S140 Tier 2** — ⚠ **re-derived by
   COUNTING THE TABLE ROWS, not retyped; the tally has now diverged three times, so re-derive it
   again before citing it** (`grep -cE '^\| \*\*[^|]*S[0-9]+-[a-z]+\*\*' docs/method-rules.md` — ⚠ **this command was itself
   defect S130-f**: the obvious form with `★+` in it under-counts by half, because `grep` quantifies
   the last BYTE of a multi-byte character. **Run it, do not just read it.**),
   each of which closed a
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
- **`docs/next-session-prompt-*.md`** — chronological handoffs. **Latest: `docs/next-session-prompt-s141.md`** (S140 Tier 2 -> S141): **`ULokiCMC::StartNewPhysics` RUNS** on both components, essentially every frame [M], measured with a pre-poisoned payload plus a 2 ms sentinel burst (396/400) -- S139's "never runs" is REFUTED. `Velocity` is ACTIVELY WRITTEN TO ZERO every frame. The wall is `CalcVelocity`'s `comisd`-against-`1.0e-4` clamp (`0x035D64F2` -> `0x035D6520 movups [rbx+0xe8], ZeroVector`), and **S141's first move is ONE READ-ONLY RPM RUN with no injection**: `MinAnalogWalkSpeed @CMC+0x290`, already wired into `tools/re/cmc_earlyout_readout.py`. ⚠ `docs/next-session-prompt-s140.md` is SUPERSEDED and its §1 sentinel recipe is DEGENERATE as written (see `docs/s140-tier2-sentinel.md` §4).
  ⚠ **Previous: `docs/next-session-prompt-s140.md`** (S139 → S140): the movement wall is down to **THREE INSTRUCTIONS**. `ULokiCMC::PerformMovement` RUNS with a real DeltaTime and reaches its Super unconditionally; the ENGINE `PerformMovement` then bails before `StartNewPhysics` (whose latch reads 0 on both pawns). Two of its three gates are measured passing (`MovementMode` 3, `Mobility` Movable); the third — **`UpdatedComponent->IsSimulatingPhysics()` at `0x035E9FB5`/`jne 0x035EB7CF`** — has never been read. **That one read is the whole next session.** ⚠ `docs/next-session-prompt-s139.md` is superseded and its §1 plan is REFUTED: `play` is **not** a moving control (it writes `CMC+0xE8`/`+0x328` directly and enables no tick), and the bot/player diff it proposed comes back **identical on every structural field** — the question was mis-framed for the third time in the same shape.
  ⚠ `docs/next-session-prompt-s137.md` is the PREVIOUS handoff and its §1.2 arm is the refuted one — keep it as the dated record, do not follow it.

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
