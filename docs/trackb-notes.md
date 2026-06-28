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

### Update 2026-06-28 — manifest route exhausted; AssetRegistry repack route opened

Further RE established that **LokiAssetManager (UAssetManager subclass) registers primary
assets ONLY from the content-service manifest's 11 named maps and never runs the standard
config-driven directory scan**. Same single root cause behind empty Missions modal,
Hunters grid, Store, and Cosmetics.

The native scan-call shim (tools/inject/shim/scan_shim.cpp) reached the real game
thread via QueueUserAPC but crashed in `__report_gsfailure` (stack-cookie) inside the
scan function even with empty config arrays. **Closed route.**

**New route:** modify `Loki/AssetRegistry.bin` so the missing primary-asset
registrations happen during the game's NORMAL startup. The cooked
`AssetRegistry.bin` (36 MB, extracted to `tools/extractor/out/AssetRegistry.bin`)
already contains every asset with its full class info and path — grep confirms
`DA_MissionPoolDailyChallenge`, `LokiDataAsset_MissionPool`, `LokiDataAsset_Mission`,
`BP_HeroAsset_Assault`, etc.

See **`docs/trackb-assetregistry-route.md`** for the full plan + format facts.
Read-only `assetregistry` subcommands (stats / classes / inspect / candidates /
namemap) implemented this session in `tools/extractor/extractor/Program.cs`;
diagnostic step runs next.

### Update 2026-06-28 (later) — AR repack route blocked at the packer

End-to-end exec proved the AR repack route's design is sound but the deployment
is blocked at a lower layer than expected. Full chain runs cleanly:

- `assetregistry apply-patch` flips entries; CUE4Parse re-parses; file length
  preserved (verified for 4 pool + 12 mission entries).
- `mkpak` writes a UE pak v11 with our patched AR.bin; `peekpak` round-trips
  to identical SHA1.
- Loose-file drop is INERT — UE always loads the pak-embedded AR even with
  a truncated/garbage loose `Loki\AssetRegistry.bin` (truncate kill-test
  confirmed: 32 bytes of `0xDEADBEEF` and the game still boots normally).
- Mod-pak deployment requires a valid `.sig` file (engine rejects unsigned
  paks with "Couldn't find pak signature file → Failed to mount"); we don't
  have the developer's RSA key.
- Sig-bypass attempt via injected DLL: full mechanism works (manual-map,
  WPM, marker confirms `mov al,1; ret` lands at `FPakSignatureFile::Load`
  entry, mod-RVA `0x2047EE0`) — BUT the patch always lands ~50ms AFTER the
  function has executed. The shipping exe's packer commits .text pages
  on-demand via a page-fault handler; the function bytes only appear when
  the engine first calls the function, and the commit → execute sequence is
  atomic from our perspective. UE4SS is installed but never loads either
  (exe's import directory is stripped — no proxy DLL path).

Tooling built this session and committed for any future fix:
`tools/usmapdump` (strings / wstrings / xrefstr / findptr / callxref / peek /
disasm), `tools/inject` (`mmap`, `launch`, `watch-now`, `probe`, `diag`),
`tools/sigbypass-mod` (UE4SS-style C++ patch DLL + race scripts).

Three remaining options, all multi-day RE work — see "Three remaining options"
section in `docs/trackb-assetregistry-route.md`. Until one is pursued, the
unified content unlock for missions / hunters / store / cosmetics remains gated.

## Deferred (need Track A catalog SKUs)

Cosmetic/skin EQUIP (loadout, `HeroCosmeticsBundlePreference`,
`SetLuxeSkinChromaPreferenceRequest` chroma), store orders
(`/storefront/orders`, `/storefront/steam/player/`, `/storefront/entitlements`),
`LokiPlatformCurrencyExchangeRequest` (token exchange) — revisit once the
content-service manifest lands resolvable SKUs.
