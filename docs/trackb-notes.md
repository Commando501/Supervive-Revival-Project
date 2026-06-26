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
