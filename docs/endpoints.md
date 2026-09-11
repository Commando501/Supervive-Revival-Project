# SUPERVIVE Revival — Endpoint Map

Status of every endpoint the client calls. `✅` = real response, `🟡` = stub `{}` (works
for now / not yet meaningful), `❓` = needs a real shape (Milestone 2). See
[findings.md](findings.md) for the login→menu gate sequence and the deserialize rules.

The server (`server/`) listens on **HTTP :8080** (AccelByte + PostAuth, via `-ini:` URL
overrides) and **HTTPS :443** (Theorycraft hosts, via hosts-file redirect). Catch-all
returns `{}` and every request is logged to `docs/capture.log`.

## AccelByte IAM — `internal/iam`

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/iam/v4/oauth/platforms/{platform}/token` | ✅ | **Steam login.** Real signed JWT incl. `unique_display_name` claim (skips onboarding) |
| POST | `/iam/v3` & `/iam/v4` `/oauth/token`, `/token/exchange`, `/authenticateWithLink` | ✅ | grant types: client_credentials / password / refresh / code |
| GET | `/iam/v3`,`/iam/v4`,`/v3`,`/v4` `/oauth/jwks` | ✅ | RS256 public key (token validation) |
| GET | `/iam/v3`,`/iam/v4` `/public/users/me`, `/public/namespaces/{ns}/users/me` | ✅ | synthetic user; `uniqueDisplayName` = `Name#tag` |
| GET | `/iam/v3/public/namespaces/{ns}` | ✅ | namespace info |
| GET | `/iam/v3/public/inputValidations` | ✅ | field rules (displayName/uniqueDisplayName/tag/username) |
| GET | `/iam/v3/public/namespaces/{ns}/users/availability` | ✅ | always available |
| PUT/PATCH | `/iam/v3`,`/iam/v4` `/public/namespaces/{ns}/users/me` | ✅ | save chosen display name |
| GET | `/basic/v1/public/misc/time`, `/iam/v3/public/misc/time`, `/v1/public/misc/time` | ✅ | server time |
| POST | `/iam/*/oauth/verify` | ✅ | always active |
| POST | `/iam/v3/logout` | 🟡 | catch-all |

## Theorycraft "project Loki" — `internal/loki`

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/configuration/public` | ✅ | **ClientConfiguration**: `serviceHostnames`, `clientVersions`, `eTag`, `lastUpdated`. Service-name keys now also include `contentservice`, `discordapi`, `coregame` (→http) and `messaging` (→`ws://`) — each added after the client logged "Could not find service address for service …" (host-less URL → libcurl "No host part in the URL"). `coregame`→path `/core-game` was a 3600+/run loop |
| POST | `/postauth/reconcileRoles`, `/reconcileRoles` | ✅ | returns `unique_display_name` etc. |
| GET | `/configuration/client` | 🟡 | seen at menu; shape unknown |

## Menu / lobby (Milestone 2 — mostly stubbed)

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/storefront/battlepass/progressiontracks` | ✅ | **Populated.** Returns `{"data":[{Id,Code,ProgressionType:"SEASON_PASS",Status:"PUBLISHED",RewardTrackCodes:[…]}],"paging":{…}}`. One `FAccelByteModelsListProgressionTrackInfo` element satisfied `GetCurrentPublishedProgressionTracks` → solo tight-loop dropped **~100/s → ~17/s** (now just the shared menu-refresh tick, no parse error). **This unblocked the whole menu-data cascade** — the client then began calling `/progression/players/{id}(/tracks)`, `/storefront/heroes`/`wallet`/`real/offers`, `/referral/player/{id}(/points)`, `/mmr/player-ratings/{id}/rank`, `/match-history/players/{id}`, `/core-game/regions`, `/party/matchmaking/info`/`customGameModes` (all new, all one-shot on `{}` catch-all, none looping). Key: UE *ignores* JSON keys matching no UPROPERTY; only wrong-typed *matched* keys reject the doc — so a populated element with confirmed/string-typed fields can't regress the parse |
| GET | `/content-service/manifest/{version}` | ❓ | was host-less ("No host part in URL") until `contentservice` added to serviceHostnames; now routes to us — shape TBD (object wrapper w/ required field) |
| POST | `/discord-api/account/token` | ❓ | was host-less until `discordapi` added; `LogLokiDiscord: Failed to refresh Discord token` — shape TBD. Safe-ish to leave failing (Discord integration) |
| WS | `/lobby` | 🧪 | **handshake + protocol partly implemented** (`internal/ws` RFC 6455 zero-dep; `internal/lobby`). Connection holds; client speaks first with AccelByte lobby text msgs (`type: <name>\nid: <reqId>\n<k>: <v>`). We now answer `listOfFriends`/`listIncomingFriends`/`listOutgoingFriends`Request → `…Response code:0 friendsId:[]`, and `setUserStatusRequest` → `setUserStatusResponse code:0`. Echo `id`. Empty TEXT frames every ~30s = client heartbeat (no reply needed) |
| WS | `/notifications/players/{id}` | 🧪 | messenger socket; sends binary `hb` heartbeat ~every 60s. Echo-on-receive (earlier session) stopped the ~5s close cycle but the watchdog still tripped at ~60s with "heartbeat not received in 5 seconds. Last heartbeat sent: <T>" + clean status-1000 close. **2026-06-29 probe:** server now also pushes a proactive binary `hb` every 30s on this path (read-deadline-driven, single goroutine — see `lobby.Handle`). Awaiting relaunch validation |
| GET | `/party/players/{id}/voice` | ⛔ | response model = `LokiVivoxToken { Token: FString }` (schema.txt:29070). Body shape is solved, but Vivox JWT mint requires Theorycraft's HS256 shared secret (issuer `theory0017`, env `lo18`, audience `mt2p.www.vivox.com/api2`). **2026-06-29:** no secret anywhere in `server/`, no env-var or config file; `VivoxRegistry` UStruct (54141) carries no signing key; the secret lives on Theorycraft's production backend and Vivox validates against it server-side, so even a structurally-perfect self-signed token gets the same `20127 Access Token Service Unavailable` from Vivox itself. **Blocker is structural — no fix without the real secret.** Reported but not patched (per "don't ship a no-op token that'll fail the same way" guardrail) |
| GET/PUT | `/personalization/players/{id}`, `/clientprofile`, `/lobbyplatforms` | ❓ | profile/cosmetics |
| GET | `/player-stats/players/{id}` | ✅ | **Served (S121), CAREER→STATS renders every field.** `FPlayerStats{ID, Version int32, StatsByQueue TMap}` → `FPlayerQueueStats{ID, StatsByHero TMap}` → `FPlayerHeroStats` (22 int32 + `Placements TMap<int32,int32>`). All three maps are JSON **objects**. ⚠ `Placements` is **ZERO-indexed** (key 0 == 1st place, confirmed by pre-registered prediction) — and note its sibling `FMatchHistoryTeamInfo.Placement` is **1-indexed**, so the convention does not carry across (FK-21). ⚠ `Version` is **int32** — a millisecond timestamp overflows it and rejects the whole struct. Login-time fetch; an admin socket drop does NOT refetch it. Knob `AGS_PLAYER_STATS=0` |
| POST | `/game-telemetry/v1/protected/events` | 🟡 | telemetry (safe to stub) |
| GET | `/party/players/{id}?defaultQueue=tutorialNew` | ❓ | **active poller** (~17/s lockstep). Response model `PartyPlayer` (fields seen: `Invites`, `ExcludedRegions`; `EPartyState`: Default/Matchmaking/CustomGame/Unknown). Solo = "player not in party" (`LogPartyManager`). Needs idle-solo shape to slow the loop |
| GET | `/core-game/players/{id}` | ✅ | **active poller** (~17/s). "Do I have a match to rejoin?" **usmap ground truth `CoreGamePlayer` (4 props): `ID`(str), `MatchID`(str), `Version`(int64), `CanDisassociate`(bool)** — NOT MatchParticipant/MatchInfo (the old binary-scan model was wrong; those are separate structs). Client waits for a non-empty `MatchID`, then fetches the match. Idle = empty MatchID; S62 sets a real MatchID when `SoloMode` is armed |
| GET | `/core-game/matches/{matchId}` | ❓ | S62 PROBE: match-details fetch after a MatchID appears. Returns usmap `MatchInfo` (19 props: `GameConfig`{`MapName`,`GameMode`,`SoloModeStartLocation`}, `State`/`StateEnum` `ECoreGameMatchState`, `ConnectionDetails`=`CoreGameServerInfo`{`address`…}, `PlayerInfo`=`MatchParticipant`, `QueueID`,`Region`,`OwnerID`). Local tutorial = EMPTY `address`. Route path is a best guess — confirm from capture.log |

### Party ACTION verbs — the interaction-triggered surface (S122 + S133)

⚠⚠ **THESE ARE INVISIBLE TO A PASSIVE CAPTURE-DIFF.** S122's sweep parsed a 74-minute
capture and reported "56 client routes, 8 unserved". Every row below was missing from it,
because the endpoints only fire when a HUMAN CLICKS the control: nobody clicked an activity
tile (`setTargetQueues`), FIND MATCH (`joinQueue`), cancel (`leaveQueue`), the privacy
toggle (`setIsOpen`) or an emote (`emote`) during that capture.
⇒ **A capture-diff enumerates what the client HAPPENED to exercise, not what it can call.
Drive the interaction, THEN diff. Re-running the sweep for longer does not help.**

★ Note the URL shape: these put their value in the **PATH**, not a JSON body, unlike the
rest of this backend. `emote/` arrives with an EMPTY tail when the account owns no emote.

★ **Free receipt: the client RETRIES an unaccepted party verb** (`joinQueue` was POSTed
twice, ~10–35 s apart, until the response was accepted; once accepted it fires exactly
ONCE). A repeating verb in `capture.log` means your response is being rejected.

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/party/parties/{partyId}/setTargetQueues` | ✅ | **Activity-tile selection** (S122). Body `{"queueIds":["<id>"]}`. Unserved it fell to the catch-all and the next `/party` poll re-served the old `targetQueueId`, snapping the selection back — the observed grey/un-grey. Persists + echoes the party. |
| POST | `/party/parties/{partyId}/joinQueue` | ✅ | **FIND MATCH** (S133). Empty body. ★★ **The response must be an `FParty` under an ADVANCED `Version`** — read from the decrypted `UPartyManager::TryJoinQueue` (`0x5875E90`), whose callback `0x5859E10` calls `UPartyModel::SetParty` (`0x587BE90`, the S85 monotonic-Version gate). ★★ **The field that drives the queued UI is `state = "Matchmaking"`** (`EPartyState = {Default, Matchmaking, CustomGame, Unknown}`), **NOT `inQueue`** — serving `inQueue:true` alone was MEASURED insufficient (SetParty ran, `LogJson` silent, UI unmoved). ⚠ Nothing matches the player: no matchmaker answers the queue, and `matchmakingNotif` is UNBOUND (FK-15/S118) so a match-found signal has to be HTTP. Knob `AGS_JOIN_QUEUE=0`. |
| POST | `/party/parties/{partyId}/leaveQueue` | ✅ | **Cancel** (S133). Registered speculatively alongside `cancelQueue`; the client uses `leaveQueue`, confirmed on the wire. |
| POST | `/party/parties/{partyId}/setIsOpen/{value}` | ✅ | **Party privacy toggle** (S133). Value in the PATH. ⚠ The client sends **capitalised `True`/`False`** — parse case-insensitively or every value reads as false and it looks exactly like "the toggle does nothing". |
| POST | `/party/parties/{partyId}/emote/{Emote:Name}` | 🧪 | **Lobby emote** (S133). [M] the id is the **PATH TAIL as a full PrimaryAssetId** (`Emote:Fingerwag`) and the **body is always empty**. Emotes play with the party document echoed UNCHANGED, so no new field is known to be needed — `FParty` names `Emotes`/`Emotes_Played` but a multi-member broadcast is UNTESTED (this backend only serves a solo party). |
| POST | `/party/parties/{p}/members/{id}/latencies` | 🟡 | client→server upload, no surface |
| POST | `/party/parties/{p}/refreshRanks` | ❓ | revealed by serving `FPlayerRank` (S122); still unserved |
| POST | `/party/parties/{p}/members/{id}/refreshMastery` | ❓ | called at login; untraced |

### Cascade revealed by populating progressiontracks (all new this session, `{}` catch-all, one-shot — not looping)

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/progression/players/{id}` , `/progression/players/{id}/tracks` | ❓ | player's progression/level — feeds party-slot level + battlepass progress |
| GET | `/storefront/heroes` | ❓ | hero roster/catalog (party slots show `ShowUnknownForEmpty` w/o it) |
| GET | `/storefront/wallet/{id}` | ✅ | **Solved.** `FLokiStorefrontPlayerWallet { Balances: TMap<FString,int> }`. Purple counter key = **`vp`** (Vive Points), decoded via sentinel-value probe. The GOLD counter = **Theorycraft Coins**, the real-money premium currency → a fresh account has **0 authentically** (not a virtual-wallet entry; 91 candidate keys confirmed it's not wallet-sourced). `LogPlatformStorefront: Wallet balance: <code>, <int>` logs every key sent = readback channel |
| GET | `/storefront/heroes` | 🧪 | `FLokiStorefrontHeroes` — array field = **`heroes`** (decoded via element-count probe → `Unlockable heroes fetched: %d`). Element type likely `TArray<FString>` (hero IDs): 12 object-elements counted but rendered nothing in the HUNTERS "ALL HUNTERS" grid. Probing string format (codename `ShieldBot` vs display `Bishop`). Real roster (from Armory dropdown + asset paths): Beebo, Bishop(=ShieldBot), Brall(=HookGuy), Carbine, Celeste, Crysta, Elluna, Eva, Felix, … codenames: Alchemist Assault BacklineHealer Beebo BountyHunter BurstCaster Earthtank FarShot FireFox Flex Freeze Gunner HookGuy Huntress Reaper ResHealer RocketJumper Ronin ShieldBot Sniper Storm Succubus Void Wukong |
| GET | `/inventory/players/{id}` , `/inventory/free` | 🟡 | `LokiPlatformInventory { AssetEntries: [...] }`; `LogPlatformInventory: Refreshed player inventory` on valid-empty. Owned heroes/cosmetics live here keyed by **packed-config SKUs** (not exe strings) → can't populate without IoStore catalog extraction. Returning valid-empty wrappers |
| GET | `/storefront/real/offers/{id}` | 🟡 | real-money store (drives STORE tab). Valid-empty `FLokiStorefrontPlayerStore`-shaped wrapper; real offers need packed item SKUs |
| GET | `/progression/players/{id}/tracks` | 🟡 | `FAccelByteModelsListUserProgressionInfoPagingSlicedResult` → valid-empty `{data:[],paging:{}}` |
| PUT | `/progression/players/{id}/mission` | ✅ | **empty body** — a *"reconcile mission progress"* fire-and-forget trigger (exe `ServerAddMissionProgress`/`SetMissionProgress`), NOT a data-carrying claim. Response = `MissionData` (`Completions`/`TrackIDToClaimableRewards` TMaps). In the real game the DS added progress server-side and this just told the client to refresh → treat as a **"refresh now" hook**, not a data source (see `missions-progression-hookup.md`) |

### Missions (revival-only HTTP surface — NOT client routes)

The client has **no missions-list/progress endpoint** (missions are built client-side; see `session-59-progress-bars.txt`). These `/revival/missions/*` routes are consumed only by the in-process missions shim (`missions_fix.dll`), served from `server/internal/interactive/missions.go`:

| Method | Path | Notes |
|---|---|---|
| GET | `/revival/missions/progress` | per-mission objective progress the shim applies to the bars (keyed `"<mission>/<objective>"`) |
| POST | `/revival/missions/progress` / `.../add` | set / increment composite keys |
| POST | `/revival/missions/manifest` | shim registers the mission→objective structure (`{mission,objective,max}`, +optional `pool`,`xp`) for per-mission fan-out |
| GET | `/revival/missions/manifest` | read back the registered manifest (admin / a thinner shim) |
| GET | `/revival/missions/status` | **server-computed completion** — per-mission `{complete,objectives[…]}` + summary `{total,complete,xpEarned}` from manifest maxes vs stored progress |
| POST | `/revival/missions/rotate` | daily/weekly reset — clears a pool's (`{"pool":…}`) or listed (`{"missions":[…]}`) composite progress |
| GET | `/revival/missions/coverage` | **which missions will actually advance** from a match — cross-refs the manifest objectives against `objectiveRules`; lists per-mission `full/partial/none`, unmapped objectives (need a rule), and unused rules (likely name typos) |
| POST | `/revival/missions/match-result` | **the increment engine** — maps a match stat summary → objective deltas, fans out per-mission |

**Wiring real match progress when matches launch:** see **`docs/missions-progression-hookup.md`** (candidate match-end signals, the backend-driven vs native-driven strategies, the unmapped 309 hero objectives, and the reward-claim/rotation gaps).

### Session-end status — backend-reachable ceiling

The menu is **broadly populated/alive**. What renders correctly now: nav, party slots, level/rank badges, Vive Points (`vp`=2004), Customization (local cosmetics + emote wheel + "0/331"), **Career→Stats** (authentic 0s), **Career→Ranked** (full Season-2 ladder, Bronze IV 0/200 RP), **Career→History** (empty = correct for new account), lobby/friends/voice.

> ⚠⚠ **CORRECTION (S123, 2026-08-15) — THE THREE CAREER PARENTHETICALS ABOVE ARE FALSE, AND THIS
> LINE IS THE HOME OF THE BELIEF FK-21 WAS OPENED AGAINST.** None of those panels was authentically
> empty; all three were empty because **we served nothing**, and each renders the moment it is fed:
> **Stats** S121 (`GET /player-stats/players/{id}` → MATCHES 12 / KILLS 40 / …), **Ranked** S122
> (`GET /mmr/player-ratings/{id}/rank` → `GOLD I`, `1,850 RP`), **History** S123
> (`GET /match-history/players/{id}` with a populated `Matches` → `VICTORY · Basic Training · 1/16`,
> hero portrait, ALLY row, full expanded stat panel — screenshot-confirmed). All backend-only, no
> shim. ⇒ **"authentic empty" was never measured here — it was inferred from "a new account has no
> history", and this account is not new.** See `docs/ignorance-map-s101.md` FK-21 and
> `server/internal/interactive/matchhistory.go`.

**Confirmed NOT backend-fixable** (need IoStore `.pak`/`.ucas` extraction, separate workstream):
- `<MISSING STRING TABLE ENTRY>`, "ITEM NAME", "TEXT BLOCK" placeholders = packed UI **string tables** failing to resolve (`LogStringTable: Failed to find ST_Cosmetics_Categories…`).
- HUNTERS "ALL HUNTERS" grid, STORE offers, owned cosmetics, PASSES tier detail = all keyed off **packed item/hero SKUs**.
- Hero-token count (`LogBattlepassHeroUnlocker: Failed to get hero token amount`) = comes from battlepass reward-track claim state (reward SKUs); confirmed NOT a wallet balance (`heroToken` parsed but ignored).
| GET | `/storefront/offers/{id}` | 🧪 | `FLokiStorefrontPlayerStore { RotatingOffers, FeaturedItemOffers, TypeOffers (arrays), NextRotation (FDateTime, omitted) }` — returns empty-valid wrapper; item-offer fields (`FLokiStorefrontItemOffer`, `…CurrencyAmount`, `…OfferingCost{IsVirtual}`) mostly pooled |
| GET | `/storefront/real/offers/{id}` | ❓ | real-money offers |
| GET | `/referral/player/{id}` , `/referral/player/{id}/points` | ❓ | referral state |
| GET | `/mmr/player-ratings/{id}/rank` | ✅ | **Served (S122).** Drives the CAREER nav-button notification badge **and** the RANKED page (`GOLD I`, `1,850 RP`). `FPlayerRank{ID, Version int32, QueueRankRating TMap, RewardsToClaim TMap}` — both maps are JSON **objects**. ⚠ Behind a **monotonic Version gate** [M]: a valid non-empty document at `Version 1` is ignored outright, so read a null here as "possibly version-rejected" until you have checked Version advanced. ⚠ `AGS_PLAYER_RANK=0` is **not** a controlled negative (it changes document and version at once); `AGS_PLAYER_RANK_EMPTY=1` is. `server/internal/interactive/playerrank.go` |
| GET | `/match-history/players/{id}` | ✅ | **Served (S119 gate, S123 populated).** Opens news-banner gate 1 via `IsMatchHistoryLoaded` == `[MatchHistoryManager+0x68] >= -1` (sentinel **-2** = never loaded), and with `AGS_MATCH_HISTORY=minimal\|full` renders CAREER→HISTORY end to end (`VICTORY · Basic Training · 1/16`, hero portrait, ALLY row, full stat panel). ⚠ `FMatchHistoryEntry` is 15 fields; the damage tiles read **`Effective*`, never the raw `Damage*`**. ⚠ `TeamInfo.Placement` is **1-indexed** (opposite of `FPlayerHeroStats.Placements`). Default off = `Matches: []`, byte-identical to pre-S123. `docs/fk21-career-panels-settled.md`, `server/internal/interactive/matchhistory.go` |
| GET | `/core-game/regions` | ✅ | **Served (S121)** — the latency pipeline runs for the first time. `FRegionHostList{Regions[], ETag}`; `PingHost`/`PingPort` live **inside** each region's `Routes` TMap, which is why a flat payload parsed into zero measurers for a year. ⚠ `CanExclude` must be **true** — it is a hard inclusion gate, not advice. ⚠ The ETag **gates re-processing** (now a sha256 of the body). `Name` is an `ST_ServerLocations` key (AWS region codes, e.g. `us-east-1`). ⚠ `— ms` is still not a number: the ping is a **UDP echo** and we run no responder |
| GET | `/party/matchmaking/info` , `/party/matchmaking/customGameModes` | ❓ | matchmaking queues / custom modes |

## The "Invalid response received" validity model (Milestone 2 key)

`LogLokiPlatformQuery: Error: Invalid response received. Query: GET: <url>` fires for
**every** endpoint we stub with `{}`: `/storefront/battlepass/progressiontracks`,
`/content-service/manifest/...`, `/discord-api/account/token`, `/party/players/{id}/voice`,
`/configuration/client`. There is a separate string "Request has an invalid response code",
so this is **not** an HTTP-status rejection — it's response-content validation.

There are **two distinct** error strings (confirmed in the binary), i.e. two code paths:
- `Invalid response received. Query: %s: %s` — a pre-deserialize **validity predicate**
  failed: a required top-level field is absent. (Our `{}` stub.)
- `Deserialization failure on Query: %s: %s.` — JSON parsed but its **container type**
  doesn't match the target UStruct. (A bare `[]` into an object struct.)

**Experiment that pinned it (progressiontracks):**
- `{}` → `Invalid response received` (missing required field).
- `[]` → flipped to `Deserialization failure` (array can't map to the object struct).
- ∴ the target is an **object wrapper** (`FAccelByteModelsListProgressionTrackInfoResult`)
  whose required field (`data`) must be present. Current build returns
  `{"data": [], "paging": {}}`: `data` present satisfies the predicate, object→object
  struct deserializes, both fields empty-but-typed (no wrong-type risk). Empty `data` =
  no battlepass shown but the loop should stop.
  - If it still errors as `Invalid response received` → predicate wants `data` **non-empty**;
    populate one well-typed `FAccelByteModelsListProgressionTrackInfo` element (omit any
    field whose type is unsure — UE rejects the whole doc on a wrong-typed *present* field).

**Generalizes to the other failing endpoints** (`content-service/manifest`,
`discord-api/account/token`, `party/.../voice`, `configuration/client`): each is an object
missing its required field. Their `{}` stubs all still log `Invalid response received`. Fix
each by returning its object wrapper with the required field present (shapes TBD per endpoint).
- Binary model names (for when we populate): `FAccelByteModelsListProgressionTrackInfo`
  (fields seen: `ProgressionType`, `RewardTrackCodes`), `…ListProgressionTrackInfoResult`,
  `…LocalizedProgressionTrackInfo` (`ExpItemId`, `RewardTracks`), `…ProgressionTrackTier`,
  `…ProgressionTrackRewardInfo`, `…ProgressionTrackRewardCurrency`,
  `…LocalizedRewardTrackInfo` (`ProgressionId`, `GrantLowerRewards`, `RewardTrackItemId`).

## Known service names (from client-config `serviceHostnames`)

postauth, clientconfig, iam, platform, basic, lobby, session, matchmaking, social,
cloudsave, telemetry, gateway, mmr, party, storefront, progression, mailbox, referral,
personalization, inventory, playerstats, matchhistory. All point at `http://localhost:8080`.

## Token / JWT shape

RS256, `kid=supervive-revival-key-1`. Claims: `namespace`, `sub` (32-hex uid),
`display_name`, **`unique_display_name`** (critical — skips onboarding), `client_id`,
`permissions` (wildcard NAMESPACE grants, Action=15), `bans:[]`, `iat`/`exp`/`nbf`,
`scope`, `is_comply:true`.
