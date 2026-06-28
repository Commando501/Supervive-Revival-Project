# Track B notes — interactive menu actions (Milestone 3)

Track B makes menu *writes* round-trip. Where `internal/menu` (Track A) answers the
client's reads with valid-but-empty shapes, `internal/interactive` captures what the
client POSTs/PUTs and echoes it back on the matching GET so selections "stick".

Wiring: one line in `cmd/ags/main.go` — `interactive.New().Register(mux)`. All routes
below previously fell through to the `{}` catch-all (`capture.StubHandler`).

Per-player state persists to `server/state/interactive.json` (gitignored), loaded on
start and rewritten on each write, so equipped selections survive a relaunch (the
launch script rebuilds + restarts, clearing memory).

## Models recovered from the shipping exe (FName pool)

Scanned `SUPERVIVE-Win64-Shipping.exe` (ASCII clustering around the model names):

- **`ClientProfileData`** is the client-profile model. `UPersonalizationManager` reads
  from it: `GetClientProfile`, `GetCurrentLoadout` (→ `Loadout`),
  `GetHeroCosmeticsBundlePreference` (→ `OutPreference`), `GetLuxeSkinChromaPreference`
  (→ `LuxeAssetID`), `FindSlotCosmeticEntry` (→ `OutAssetId`), `IsAssetEquipped`.
  So equipped cosmetics/loadout almost certainly live inside `ClientProfileData` too,
  but in `docs/capture.log` the client only ever POSTs `clientVisibilityTracking` — it
  never round-tripped a cosmetic equip in that capture, so those sub-fields' JSON
  names/types are still unconfirmed.
- **`ClientVisibilityTracking`** fields (struct PascalCase; client JSON is camelCase):
  `LastBattlepassIDSeen, LastHuntersJourneyMaxLevelSeen, LastHuntersReleaseSeen,
  LastQuestsSeen, LastStorefrontSeen, LastEventsSeen (+_Key ⇒ TMap),
  UnseenCollectionItems, LastSeenArmoryItemsForSeason` (+ `lastSeenAccountLevel` seen
  in the body). Matches the POST body exactly.
- **`SetClientProfileRequest`** — POST request model. Body shape: `{"data":{...ClientProfileData...}}`.
- **`SetLobbyPlatformPreferenceRequest`** / value type **`LobbyPlatformAssetID`** — PUT
  lobbyplatforms. Body: `{"lobbyPlatformAssetId":"LobbyPlatform:Base"}`.
- Events to watch in `Loki.log`: `OnClientProfileUpdated`, `OnSetClientProfileOpComplete`,
  `OnProgressUpdated`. Cheat helpers exist: `CheatResetClientProfile`.
- **`MailboxConfigVersion`** / `ConfigVersion` — the field behind `GET /mailbox/config/version`
  (`UMailboxManager`: `GetMailbox`, `GetMailboxModel`, `TryClaimMessageRewards`,
  `TryDeleteMessage`, `TryMarkMessageRead`).
- Progression: `FAccelByteModelsListUserProgressionInfo` + `...Paging` ⇒ standard
  data/paging wrapper.

## Endpoint status (Track B)

| Method | Path | Status | Notes |
|---|---|---|---|
| GET  | `/personalization/players/{id}/clientprofile` | ✅ echoes stored | default = full `clientVisibilityTracking` zero-values; `{}` already tolerated (no validity predicate) so zero-regression |
| POST | `/personalization/players/{id}/clientprofile` | ✅ persists `data` verbatim | echoes stored profile back (set-then-return) |
| PUT  | `/personalization/players/{id}/lobbyplatforms` | ✅ persists `lobbyPlatformAssetId` | echoes typed ack |
| GET  | `/personalization/players/{id}` | 🔎 probe | surfaces stored `lobbyPlatformAssetId` + `equippedLobbyPlatform` (both string) to find the backdrop readback path; `{}` did not error |
| GET  | `/progression/players/{id}` | 🔎 typed | `{}` logged "Invalid response received" → returns `{data:[],paging:{}}` |
| PUT  | `/progression/players/{id}/mission` | 🔎 ack | no request body captured (query/empty); returns data/paging ack |
| GET  | `/mailbox/config/version` | 🔎 probe | `{}` logged "Invalid response received" → probes `version`/`configVersion`/`mailboxConfigVersion` = 0 (int) |

## ✅ Relaunch validation (2026-06-26, build 156430)

All Track B endpoints validated against the real client:
- **clientprofile round-trip CONFIRMED.** `server/state/interactive.json` shows the
  client POSTed real visibility tracking (`lastQuestsSeen: 2026-06-26T07:33:45.882Z`,
  set when Missions/Quests were viewed) and it persisted + echoed back.
- **lobbyplatforms CONFIRMED.** Client PUT `lobbyPlatformAssetId: "LobbyPlatform:Base"`;
  persisted.
- **Zero `LogLokiPlatformQuery` errors this run** (previous run had "Invalid response
  received" on progression player / progression tracks / mailbox config / battlepass
  tracks). Both tracks together cleared every platform-query error.
- Mission modal opened cleanly (`WBP_UI_MissionModal_C`, `MissionModalCategory_Dailies_1`
  focused) — `GET /progression/players/{id}` + `PUT .../mission` accepted; panel is empty
  because progression data is empty (expected — no real mission catalog yet).
- `OnClientProfileUpdated` is a BP delegate (not log-emitting); functional proof is the
  persisted state + zero errors.

STILL OPEN: which lobby-platform readback key the menu actually consumes (the GET
`/personalization/players/{id}` probe sends both spellings but nothing in the log
confirms which lands), and whether the equipped backdrop visibly persists across
relaunch. Mailbox version key still ambiguous (no error either way now).

## What to confirm on the next relaunch (read `Loki.log`)

1. **clientprofile (primary):** `OnClientProfileUpdated` / `OnSetClientProfileOpComplete`
   fire, and the "NEW" badges on Quests/Storefront/Armory/Collection stop reappearing
   after being viewed (visibility tracking now sticks across navigation + relaunch).
2. **lobby platform:** equip a backdrop, leave & return / relaunch — does it persist?
   The `Loki.log` line + the visible backdrop tell us whether the readback path is
   `GET /personalization/players/{id}` (this probe) or `GET .../clientprofile` (then the
   `LobbyPlatformAssetID` field needs to move into `ClientProfileData`).
3. **mailbox:** does `LogMailbox: Failed to fetch mailbox config version` clear, and
   which of the three version keys lands? Narrow the probe afterward.
4. **progression:** does `GET /progression/players/{id}` stop logging "Invalid response
   received"? Then RE the `PUT .../mission` request/response for real claim/track.

## Tutorial / match launch flow (in progress 2026-06-26)

GOAL: make the Tutorials cards (Basic Training etc.) actually launch. The Tutorials
catalog *renders* (the maps are packaged + preloaded locally — Loki.log shows
`/Game/Loki/Core/GameModes/Objectives/Tutorial/Basics/BP_DropPod_Tutorial` added to the
actor pool at startup), so unlike PvP/Co-op these need **no dedicated server**.

**Confirmed blocker = the party.** Clicking Basic Training sends **no request at all** —
it is a silent **client-side** no-op. The client polls
`GET /party/players/{id}?defaultQueue=tutorialNew` and, with the `{}` stub, its
PartyManager believes the player is not in a party (`LogPartyManager: Warning: skipping
set referral code, player not in party`), so the launch button does nothing.

Fix (this iteration): `GET /party/players/{id}` now returns a valid **solo party** (the
player as the JOINED leader/member). Model = AccelByte V2 session party (member status
`JOINED`/`CONNECTED`, `PartyMembers`, `PartyReservation`, `RemovedPartyMembers`, `TeamNum`)
wrapped by Theorycraft's /party service. No response body was ever captured, so the JSON
is a **superset probe** (PascalCase keys, UE matches case-insensitively; unmatched keys
ignored). Queues recovered: `special practice customgame dropin tutorialNew training`.

Launch chain (for later steps): `GET /core-game/players/{id}` (110k polls — "active match
to rejoin?", model `CoreGameMatchModel` = MatchInfo/HeroSelectModel/Player/Region; still
`{}`, tolerated) and `GET /core-game/regions` (`GetRegions`, RegionName/RouteName) are the
next links once the party gate clears. Left unchanged this cycle to keep the experiment
single-variable.

PROBE #1 (flat field-superset, no `configuration`): client ACCEPTED it (no
deserialize/Invalid-response error in Loki.log) but did NOT adopt it — still "player not
in party", slots empty, tutorial click still a no-op. So the shape was semantically
insufficient.

PROBE #2 (current): faithful **AccelByte V2 party session** — confirmed the model is
`AccelByteModelsV2PartySession` (+ `V2SessionConfiguration` + `V2SessionUser`) in the exe.
The miss in #1 was the **`configuration` block**: a V2 session with no/invalid
configuration is treated as not-a-real-session. Now emits the full documented model
(camelCase) — id/namespace/isActive/isFull/leaderId/createdBy/version + a real
`configuration` (type NONE, joinability INVITE_ONLY, max 4) + `members:[{id,status:JOINED,
statusV2:JOINED,platformId,platformUserId}]` + invitees/code.

PROBE #2 result: ALSO not adopted (`player not in party` still logs 1002×, no error). The
client only sends friends + setUserStatus over WS (never a party frame), and never POSTs a
party — so the server is meant to hand back an auto-created party on the GET.

KEY DISCOVERY (UTF-16 endpoint table in exe): `/party` is a **bespoke Theorycraft REST
API**, NOT AccelByte V2. Operations: `/party/players/`, `/party/parties/`,
`d?defaultQueue=`, `/leave`, `/join?joinSecret=`, `/members/`, `/joinQueue`, `/leaveQueue`,
`/setTargetQueues`, `/setExcludedRegions`, `/setIsOpen/`, `/setFillTeam/`, `/latencies`,
`/referral`, **`/startSoloMode?mode=`**, `/reconcile`, `/owner`, `/voiceToken`,
`/sendInvite/`, `/requestInvite`, `/custom?custom=`, `/custom/start`, `/team/` … all under
`UPartyManager`/`UPartyModel`. **`/startSoloMode?mode=<queue>` is almost certainly the
tutorial/practice launch call.** Validity gated by `OnPartyValidChanged` ("Party in bad
state, reconciling").

PROBE #3 (current): confirmed Theorycraft party fields (FName pool, camelCase): party =
`{partyId, leader/leaderId, ownerId, members, invitees, invitationToken, joinSecret,
inQueue, isOpen, fillTeam, createdAt}`; member = `{id/userId/memberId, displayName, ready,
isReady, inQueue, region, leader}`. Solo party, player = sole ready leader.

NEXT RELAUNCH — watch: does `player not in party` clear / slots show the player? Then click
Basic Training: does it load the local map, or emit `/party/.../startSoloMode?mode=...` or
`/joinQueue` (capture it — that's the next link to build)?

✅ PROBE #3 WORKED. Live readback: `player not in party` dropped **1002 → 2** (only the 2
startup polls before the first fetch), and the PARTY panel now renders (header, Invite-to-
Party slots, Party Options, Friends). The confirmed Theorycraft field family was the fix.

NEXT LINK FOUND: once it has the partyId, the client polls `GET /party/parties/{partyId}`
(380×/session) for the full party — that was hitting the {} stub, leaving the panel's member
slots empty. Now implemented (`handleGetPartyDetail`, shares `buildSoloParty`; player id
recovered from the "party-<id>" partyId, JWT-sub fallback). This should put the player in
slot 1.

REMAINING for tutorial launch: with a valid populated party, clicking a tutorial should fire
`/party/.../startSoloMode?mode=<queue>` or `/joinQueue` + `/setTargetQueues` — none seen yet
(player hadn't clicked since the party started working). Capture those next, then wire
core-game to report the (local) match so the map loads.

The party/matchmaking system is still the largest remaining flow, but it is now yielding to
incremental endpoint-by-endpoint RE (no usmap needed so far).

✅ FULL PARTY FLOW WORKING: `/party/players/{id}` + `/party/parties/{partyId}` both serve the
solo party; the player shows as leader in slot 1, player card populates.

⛔ TUTORIAL LAUNCH NOW BLOCKED BY TRACK A (hero asset resolution). Evidence from the latest
run after clicking FIND MATCH:
- Every hunter renders as `BP_LokiHeroSelectPreview_UnknownHero_C` (the giant "?") because
  `SetHero is clearing TargetAssetId because incoming id was not valid` — the hero IDs we
  send (`/storefront/heroes` 25 lowercase codenames) do NOT resolve to valid PrimaryAssetIds
  (same AssetManager "Invalid Primary Asset Type" gate as the HUNTERS grid/missions).
- Hero panel shows `PURCHASE 20,000` — player OWNS no hunters (inventory empty).
- **FIND MATCH fires ZERO network calls** — hard client-side gate: no valid/owned/selected
  hunter ⇒ cannot queue. Even Basic Training must spawn its pre-assigned hero, whose asset
  also won't resolve.

⇒ The launch gate is hero asset resolution + ownership = **Track A** (content manifest must
declare hero PrimaryAssetTypes so AssetManager resolves them; inventory must grant ownership).
Track B's launch infra (party ✅) is done up to this gate. Remaining Track-B-only infra that
can be staged but won't visibly unblock until heroes resolve: `/core-game/regions` (region
ping; currently {} ⇒ `??? — ms`, missing `ST_ServerLocations`), `/core-game/players/{id}`
"no active match" shape (polled 837×), then `/startSoloMode`/`/joinQueue` once a hero is
selectable.

## Menu system buildout (usmap landed 2026-06-27)

The usmap is DONE — `tools/extractor` now `dump`s full property values. Roadmap: (1) hero
resolution [linchpin], (2) tutorial/match launch, (3) cosmetics/customization, (4) store,
(5) missions/progression, (6) mailbox/career.

### Phase 1 — hero resolution (content manifest), in progress
Extracted `BP_HeroAsset_<Hero>` for all 25 heroes: `InternalName` = lowercase codename (the
SKU), `HeroUniqueTag` = `Hero.<Codename>`, asset path `/Game/Loki/Characters/Heroes/<Folder>/
BP_HeroAsset_<Folder>`, plus portrait/cosmetics-bundle refs. The cosmetics-bundle ref dumped as
`PrimaryAssetType:{Name:"HeroCosmeticsBundle"}` / `PrimaryAssetName:"AssaultDefault"` — proving
Loki assets override GetPrimaryAssetId to a CLEAN name (so hero PrimaryAssetName = codename was
right; the gap was the missing TYPE).

Rebuilt `menu.go handleContentManifest` Heroes (PROBE #2): each entry now carries
`PrimaryAssetType:"HeroAsset"` (class LokiHeroAsset minus Loki, matching the HeroCosmeticsBundle
convention), `PrimaryAssetName:<codename>`, real `AssetPath`, `DisplayName`. PROBE #1 sent only
the name → "Invalid Primary Asset Type" (every hunter = UnknownHero "?"). Added `heroFolders`
(SKU→PascalCase folder). Builds clean.

PROBE #2 result: manifest DESERIALIZED FINE (no manifest error) but AssetManager still logged
`Invalid Primary Asset Type ... failed to find NameData` — so "HeroAsset" is NOT a registered
type. KEY INSIGHT: registered PrimaryAssetTypes = SINGULAR of the manifest map name (the
"HeroCosmeticsBundles" map's entries are type "HeroCosmeticsBundle"). So "Heroes" → type
**"Hero"**. PROBE #3 (current): PrimaryAssetType "Hero". Also fixed: staged `/core-game/regions`
returned a bare array → "Deserialization failure"; now wrapped in an object (regions/Regions/data
probe keys).

PROBE #3 ("Hero" flat string) result: SAME "failed to find NameData" — but the
`/core-game/regions` Deserialization failure CLEARED (object wrapper fix worked, confirming my
edits land). Loki.log: `AssetRegistry.bin` IS loaded; no startup primary-asset scan line.
ROOT CAUSE (probe #4): it was FIELD TYPES, not the value. The BP_HeroAsset dump shows its own
FPrimaryAssetType fields serialize `{"Name":...}` and FSoftObjectPath fields
`{"AssetPathName","SubPathString"}`. We sent flat strings → UE silently skips wrong-typed
fields → type+path registered EMPTY → "failed to find NameData" (and the manifest still
"deserialized fine" because skip≠fail). PROBE #4: PrimaryAssetType `{"Name":"Hero"}`, AssetPath
`{"AssetPathName":<path>,"SubPathString":""}`. Verified serialization.

PROBE #4 (nested forms) result: still "failed to find NameData". So I extracted the GROUND
TRUTH — added a `raw` mode to the extractor and pulled `Loki/Config/DefaultGame.ini`. The
[AssetManagerSettings] `PrimaryAssetTypesToScan` registry is now in `tools/extractor/out/
DefaultGame.ini` — the MASTER KEY for the whole menu. Hero entry:
`PrimaryAssetType="Hero", AssetBaseClass=/Script/Loki.LokiHeroAsset,
Directories=("/Game/Loki/Characters/Heroes")`. And `bShouldManagerDetermineTypeAndName=True`
⇒ the manager derives PrimaryAssetName from the asset SHORT NAME, not GetPrimaryAssetId — so the
real id is `Hero:BP_HeroAsset_Assault`, NOT `Hero:assault` (codename gave "Invalid Primary
Asset Id"). PROBE #5 (current, ground-truth): type {Name:"Hero"}, name "BP_HeroAsset_<Folder>",
AssetPath {AssetPathName,SubPathString}. Verified.

### The full PrimaryAssetType registry (from DefaultGame.ini) — drives EVERY menu category
Hero→LokiHeroAsset (/Game/Loki/Characters/Heroes); Item→LokiBaseItem (/Game/Loki/Items);
Emote→LokiDataAsset_Emote (/Personalization/Emotes); PlayerTitle (/Personalization);
Mission→LokiDataAsset_Mission (/Core/Missions); MissionPool→LokiDataAsset_MissionPool
(/Core/Missions/Pools); HeroCosmeticsBundle→LokiHeroCosmeticsBundle (/Characters/);
SlotCosmetics→LokiSlotCosmeticsAsset (/Personalization); LobbyPlatform→LokiLobbyPlatform_Asset
(/Personalization); StoreOffer→LokiDataAsset_StoreOffer (/Core/StoreOffer);
ExchangeToken (/Core/StoreOffer/ExchangeToken); Power→LokiDataAsset_Power
(/Items/ActiveItems/DataAssets); Equipment→LokiDataAsset_Equipment (/Items/Equipment/DataAssets);
GameAugment, HeroMastery, LoginReward, EventTrack, ProgressionTrack, Season, Capsule,
ArmoryCraftOffer, ArmoryTables, GameFeature, MapIcon, HeroAnimation, XPCategory.
ALL use bManagerDetermineName=True ⇒ PrimaryAssetName = asset short name.

PROBE #5 (nested forms, name BP_HeroAsset_Assault) result: STILL failed. So I dug to the
bottom: (a) the cooked `AssetRegistry.bin` (extracted via `raw`) has `PrimaryAssetType` only
ONCE in 36MB — i.e. NO baked primary-asset registry, so SUPERVIVE registers primary assets at
RUNTIME from the content-service manifest (the manifest IS the lever, confirmed). (b) Fixed the
extractor's `schema` mode (props are KeyValuePair<int,PropertyInfo>, not DictionaryEntry) and
dumped the EXACT struct:
```
ContentServicePrimaryAsset { Str PrimaryAssetType; Str PrimaryAssetName; Str AssetPath; Str Status; Bool IsDefault; }
```
ALL plain FStrings + one bool — so the nested {Name}/{AssetPathName} forms (probes #4/#5) were
wrong-typed and silently skipped (→ empty type → "failed to find NameData"). PROBE #6 (current,
schema-exact): flat "Hero" / "BP_HeroAsset_<Folder>" / flat path / Status "Released" / IsDefault
false. This flat+correct-name+all-5-fields combo was never tried. Verified serialization.

PROBE #6 (schema-exact entries) result: STILL failed — because the TOP-LEVEL manifest was
incomplete. The manifest fetch is `?nonEnabledOnly=true` retried **3338x** (reject/retry loop =
never processed). Dumped ContentServiceContentManifest schema:
```
{ Str ID; Str ETag; Int64 Version; Struct PrimaryAssetId CurrentSeason; Str CurrentPatchVersion;
  Array PatchVersions; Map Heroes; Map Items; ... }
```
We were omitting ID/ETag/Version/CurrentSeason. PROBE #7 (current): added all 4. CurrentSeason is
an FPrimaryAssetId (nested: {PrimaryAssetType:{Name:"Season"},PrimaryAssetName:"S2_Season"}).
Manifest is now COMPLETE at both levels (top + entry). Verified.

✅ PROBE #7 (complete top-level manifest) = BREAKTHROUGH. The 3338x retry loop dropped to 1 and
the generic "Invalid Primary Asset Type" was REPLACED by named errors — the client now CONSUMES
the manifest. Proof: it read my CurrentSeason and logged "Invalid Primary Asset Id Season:S2_Season"
(harmless — no Seasons map; cosmetic banner only). The missing ID/ETag/Version/CurrentSeason were
blocking ALL processing.

NEXT LAYER (current): hero "?" is now the COSMETICS, not the hero. Log shows
`Entering SetHero with CosmeticsAssetId ( - true)` = EMPTY — the hero MODEL is its default
cosmetics bundle, referenced by the hero asset as `HeroCosmeticsBundle:<Hero>Default` (e.g.
"AssaultDefault"). HeroCosmeticsBundles map was empty. Now populated for the 14 heroes with a
canonical BP_<Hero>_DefaultCosmeticsBundle (key+name="<Folder>Default", real AssetPath). The
other 11 (Alchemist, Beebo, BountyHunter, BurstCaster, Earthtank, FarShot, Reaper, ResHealer,
Stalker, Succubus, Wukong) use irregular bundle names — add after validating.

PROBE #8 (cosmetics map populated) result: still "?". Logs: cosmetic ASSETS load fine (actor
pooling), manifest IS consumed, but hero-preview CosmeticsAssetId stays EMPTY and `Hero:BP_HeroAsset_*`
is NEVER referenced — i.e. the client isn't resolving heroes via the manifest PrimaryAssetId for
the preview. Combined with the persistent "PURCHASE 20,000" (not-owned), the leading hypothesis is
now OWNERSHIP: an unowned hero shows the locked "?" placeholder.

PROBE #9 (current): granted OWNERSHIP via inventory. Got the exact model (usmap):
LokiPlatformInventory{ AssetEntries[], Int64 Version }; entry =
LokiPlatformInventoryAssetEntry{ PrimaryAssetId AssetId (nested), bool IsOwned/IsFree/IsDefault/
IsPremiumBenefit, EntitlementIDs[] }. handleInventory now returns all 25 heroes (Hero:BP_HeroAsset_<X>)
+ 14 cosmetics (HeroCosmeticsBundle:<X>Default) as IsOwned:true (39 entries).

PROBE #9 (codename ids) result: still "?" + PURCHASE. PROBE #10 = DIAGNOSTIC (pointed CurrentSeason
at Hero:assault, which IS in the Heroes map). RESULT = ✅ DEFINITIVE: NO "Invalid Primary Asset Id
Hero:assault" error (vs Season:S2_Season which DOES error). So the manifest's maps DO register
primary assets, and **"Hero:assault" (codename) is the correct, valid, registered hero id.**
Registration WORKS — the foundation is proven and this IS backend-fixable. Reverted CurrentSeason.

Remaining = downstream of registration:
- OWNERSHIP: inventory IS processed (LogPlatformInventory: Refreshed player inventory) but heroes
  still show PURCHASE 20,000. Ownership is via /inventory/players/{id} (no separate entitlements
  endpoint). IsOwned:true alone isn't flipping it — may need EntitlementIDs populated, or heroes
  use a separate unlock-state (LogBattlepassHeroUnlocker: "Failed to get hero token amount").
- RENDER: CosmeticsAssetId is EMPTY (not wrong) → "?". ClientProfileData only holds
  ClientVisibilityTracking (no cosmetics prefs), so the preview must derive the default from the
  loaded hero asset's DefaultCosmeticsBundle. Empty = chain breaks (hero not loaded for preview,
  or unowned-hero shows locked "?").

NEXT: user testing ASSAULT (confirmed SKU) in the running game — if it renders, pipeline proven +
just fix other heroes' SKUs; if "?", rendering is gated uniformly (ownership / hero-load chain).

## Progression / mission flow (analyzed 2026-06-26)

The only mission-related endpoints the client calls (whole capture.log): the battlepass
loop `GET /storefront/battlepass/progressiontracks` (Track A / menu), `GET
/progression/players/{id}` (174×), `GET /progression/players/{id}/tracks` (174×, menu),
and `PUT /progression/players/{id}/mission` (21×). **There is no missions-list endpoint.**

- `PUT .../mission` has an **empty body** (Content-Length 0) — a fire-and-forget
  "reconcile mission progress" trigger (exe: `ServerAddMissionProgress`,
  `SetMissionProgress`), not a claim with a payload. Real progress is added server-side
  during matches, so in the menu there is nothing per-player to persist. Response model
  = **`MissionData`**; we now return its two `_Key`-confirmed TMap fields
  (`Completions`, `TrackIDToClaimableRewards`) as empty objects (was a data/paging
  guess). The two non-map sibling fields (`ClaimableProgressionTrackClaimData`,
  `ClaimableProgressionTrackRewards`) are omitted (type unconfirmed).
- Related exe models: `ClaimMissionRewardsRequest/Response` (SuccessfulClaimIDs,
  UnclaimedClaimIDs), `ClaimableProgressionTrackRewardsResponse`,
  `GetAllClaimableMissionRewardsForPools`.

### ⛔ Why the Missions modal is empty — it's the Track A AssetManager gate, not Track B

Missions are **UE Primary Assets the client loads LOCALLY**, not backend list data. Exe
evidence: `GetMissionPoolFromPrimaryAssetId`, `GetMissionModelsForAssetID`,
`MissionPoolAssets` (TMap), `MissionPoolIDs`, `OnLocalMissionsInitialized`,
`bHasCheckedForNewMissions`, `MillisUntilNewMission`/`NewMissionTime` (daily rotation).
Latest `Loki.log` confirms the blocker:

```
LogAssetManager: Warning: Invalid Primary Asset Type :
  ChangeBundleStateForPrimaryAssets failed to find NameData
```

This is the **same gate as the HUNTERS grid**: the client's AssetManager can't resolve
the mission-pool primary asset type until the **content-service manifest (Track A)**
declares it. The progression/mission backend (this package) already responds error-free;
populating visible daily missions is **blocked on Track A**, not on these endpoints.

**Track A handoff:** `handleContentManifest` in `internal/menu/menu.go` has maps for
Heroes/Items/Emotes/… but **no MissionPool/Missions map** — that (plus the correct
`ContentServicePrimaryAsset` entry shape) is what `ChangeBundleStateForPrimaryAssets`
needs. Add a mission-pool asset type to the manifest to unblock the modal.

## Deferred (need Track A catalog SKUs)

Cosmetic/skin EQUIP (loadout, `HeroCosmeticsBundlePreference`,
`SetLuxeSkinChromaPreferenceRequest` chroma), store orders
(`/storefront/orders`, `/storefront/steam/player/`, `/storefront/entitlements`),
`LokiPlatformCurrencyExchangeRequest` (token exchange) — revisit once the
content-service manifest lands resolvable SKUs.
