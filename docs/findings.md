# SUPERVIVE Revival — Reverse-Engineering Findings

Everything learned getting the client from a dead login screen into the main menu.
Written so the next session (or a new contributor) can continue without re-deriving.

## The client

- **Engine:** Unreal Engine **5.4.3**, IoStore-packed (`Loki/Content/Paks/*.utoc/.ucas`),
  internal project codename **"Loki"**.
- **Build:** `release2.4.live-156430-shipping` (changelist 156430). Sent in the
  `X-Theorycraft-Clientversion` header.
- **Platform:** Steam, appid **1283700**. Steam auth works locally (real app ticket).
- **HTTP stack:** libcurl 8.4.0 / OpenSSL 1.1.1t, `bVerifyPeer=true`. Loose CA bundle at
  `Loki/Content/Certificates/cacert.pem` (NOT packed — editable, and it IS the bundle
  libcurl uses).
- **Launcher:** `SUPERVIVE.exe` → `preloader.dll` + `runtime.dll` is a CEF/Electron shell.
  The in-engine login is UMG. We launch `SUPERVIVE-Win64-Shipping.exe` directly.
- **Anti-cheat:** EasyAntiCheat present but does not block launching the shipping exe directly.
- **Real AccelByte client_id:** `ba8fb59a34bb481abca08c46ba488025` (empty secret).

## Backends (all dead; all impersonated locally)

1. **AccelByte Gaming Services** — IAM (login/identity), platform, basic, lobby.
   Base URLs come from the `[/Script/AccelByteUe4Sdk.AccelByteSettings]` config,
   overridden via `-ini:` to `http://localhost:8080`. **The login uses AccelByte v4**
   (`/iam/v4/oauth/platforms/steam/token`), not the separate PostAuth host.
2. **Theorycraft "project Loki"** — two hardcoded HTTPS hosts:
   - `client-config-jx-prod.prodcluster.awsinfra.theorycraftgames.com` → client-config
   - `accounts.projectloki.theorycraftgames.com` → postauth (the Steam login also pings it)
   Redirected via hosts file to our `:443` TLS listener.

## Redirect mechanics

- **AccelByte / PostAuth URLs**: UE `-ini:` overrides applied at launch (read at login
  time, so the override sticks). See `configs/launch-redirect.ps1`.
- **Theorycraft hosts**: hosts file → 127.0.0.1, served over HTTPS. TLS trust via a
  **Root→Leaf chain** (root appended to the game's loose `cacert.pem`). A self-signed
  cert *as the leaf* fails OpenSSL (`X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT`) even when
  trusted — the separate root is required.
- Tried and rejected: `bVerifyPeer=false` via `-ini:` (applied too late for early curl
  init) and via user `Engine.ini` (didn't take). The cert chain is the working approach.

## The login → menu gate sequence

1. **Steam login** — `STEAM: Obtained steam authticket` → `POST /iam/v4/oauth/platforms/steam/token`
   with the real app ticket → we return a signed JWT (RS256, validated against our JWKS).
2. **users/me / time / inputValidations** — `GET /iam/v3/public/users/me`,
   `/basic/v1/public/misc/time`, `/iam/v3/public/inputValidations`.
3. **Client-config** — `GET /configuration/public?language=en` returns a `ClientConfiguration`:
   - `serviceHostnames` is **TMap<serviceName, FString url>** (plain string values; sending
     structs logs "Json Value of type 'Object' used as a 'String'"). Every service →
     `http://localhost:8080`. The game calls `{url}/{service}/{endpoint}`.
   - **Must include `eTag` + `lastUpdated`** or the config parses but is never *applied*
     (silently — no error, services stay unresolved). This was the single biggest unlock.
   - **Must include `clientVersions`** (array) containing the client build, else "UPDATE REQUIRED".
   - **Send ONLY known fields.** UE's `JsonObjectStringToUStruct` rejects the WHOLE document
     (`DESERIALIZE_ERROR`) if any *present* field has a wrong type. Known `ClientConfiguration`
     fields: `serviceHostnames`, `clientVersions`, `featureToggles`, `statusMessages`,
     `vendorConfigs`, `cohortConfigs`, `playtestEnabled`, `playtestWindows`,
     `inventoryFreeVersion`, `trySpectateMatch`, `bannerConfigs`, `eTag`, `lastUpdated`.
     (`DisplayNameTagValidation` is NOT one of them.)
4. **postauth/reconcile** — once `serviceHostnames["postauth"]` resolves, the game does
   `POST /postauth/reconcileRoles?steam=<id>`. Response is a `PostAuthReconcileResponse`
   (fields include `Unique_display_name`, `Other_display_name`).
5. **Onboarding skip** — after auth, `ELokiAuthState` → `AwaitingUniqueDisplayName` (the
   "CHOOSE DISPLAY NAME AND TAG" screen) UNLESS the account already has a unique display
   name. The `AuthManager` reads it from the **access-token JWT claim `unique_display_name`**
   (NOT users/me, NOT reconcile, NOT the screen's `DisplayNameTagValidation` limits — all
   tried, none worked). Setting `unique_display_name: "Reviver#0001"` in the token claims
   flips the state to `Authorized` → **menu**.

> The "Choose Display Name" screen's `0 and 0` limits come from `UAuthManager.DisplayNameTagValidation`
> (`DisplayNameMinSize/MaxSize/TagMinSize/TagMaxSize`). Its source was never found (not
> client-config, reconcile, users/me, or inputValidations). Skipping the screen via the
> token claim makes it moot, but if a future flow needs the screen, this is an open question.

## Auth state machine (`ELokiAuthState`)

`NoAuth → AttemptingAuth → [AwaitingLegal | AwaitingMFA | AwaitingLoginQueue |
AwaitingUniqueDisplayName] → Authorized` (or `AuthLost`).
Login errors: `ELokiLoginError::{AccountBanned, ClientVersionNotSupported,
InvalidCredentials, NoActivePlaytest, Unknown}`.

## Static recon technique

The values we needed live in the packed config (not extractable without IoStore tooling)
and as UE reflection strings in `SUPERVIVE-Win64-Shipping.exe`. We extracted struct/field
names by scanning the binary for ASCII **and** UTF-16LE strings and clustering by file
offset (UE registers a struct's properties contiguously). The game's own log at
`%LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log` was the best ground-truth source —
it logs every HTTP URL, JSON deserialize errors (with our payload), and auth-state warnings.

## Milestone 2 progress — reaching a rendered main menu

The client now reaches a **fully rendered, error-free main menu** (`ALokiBaseController::
TryUIReady SUCCESS`, all four `MainMenu_PartySlot` widgets spawned, Vivox voice enumerating
devices, zero `Error:` lines in `Loki.log`). What unlocked it this session:

1. **The "Invalid response received" validity model** (see endpoints.md for the full writeup).
   Two distinct LogLokiPlatformQuery errors: "Invalid response received" = required top-level
   field absent; "Deserialization failure" = wrong container type. Decoded by watching the
   error flip when we changed `{}`→`[]` on progressiontracks. The list endpoints want an
   **object wrapper** with its required field present, e.g. `{"data":[],"paging":{}}`.
2. **Missing service addresses.** `serviceHostnames` (in `/configuration/public`) was missing
   keys the client needs: `contentservice`, `discordapi`, `coregame` (→`http://localhost:8080`)
   and `messaging` (→`ws://localhost:8080`). Symptom: client logs "Could not find service
   address for service <name>", builds a host-less URL, libcurl errors "No host part in the
   URL". The client tells you the exact missing key — always grep that warning first.
   (Service NAME has no hyphen: `coregame`; the URL PATH segment does: `/core-game`.)
3. **WebSocket lobby.** Implemented a zero-dep RFC 6455 server (`internal/ws` via
   `http.Hijacker`; `internal/lobby`). Two sockets: `/lobby` and `/notifications/players/{id}`.
   - Returning **101 + keeping the socket open** stops the "ws upgrade response not 101"
     reconnect loop.
   - `/lobby` uses the **AccelByte lobby text protocol**: `type: <name>\nid: <reqId>\n<k>: <v>`.
     Client speaks first. We answer friend-list + setUserStatus requests with
     `…Response\nid:<echo>\ncode: 0\nfriendsId: []`. (No `connectNotif` strings in the binary —
     protocol learned from captured frames, NOT from static recon.)
   - `/notifications` sends a binary `hb` heartbeat (`0x68 0x62`); **echo `hb` back** or it
     closes + reconnects every ~5s.

## Open questions / next (Milestone 2 — populate the menu)

The menu renders but is **empty**; three background managers poll ~15/sec on empty state
(no errors, just unpopulated). Returning real/typed shapes should quiesce them and fill the UI:
- `/storefront/battlepass/progressiontracks` — deserialize fixed (empty wrapper), but the
  battlepass UI re-requests wanting a "current published track". Needs a populated
  `FAccelByteModelsListProgressionTrackInfo` element (field/type set partly recovered — see
  endpoints.md; `LogBattlepassHeroUnlocker: Failed to get hero token amount`).
- `/core-game/players/{id}` — `UCoreGameService`/`UCoreGameMatchModel`: "is there an active
  match to rejoin?". Empty → fast poll. Needs a "no active match" shape.
- `/party/players/{id}` — party state (solo). `LogPartyManager: skipping set referral code,
  player not in party`.
- `/personalization/players/{id}` + `/clientprofile` + `/lobbyplatforms`, `/player-stats/
  players/{id}` — profile/cosmetics/level; party slots show `ShowUnknownForEmpty` (no owned heroes).
- `/configuration/client` — still stubbed `{}`; no longer erroring.
- `DisplayNameTagValidation` source (only matters if onboarding can't be skipped).

## Milestone 3, Track A — IoStore extraction (tooling stood up)

Built a headless CUE4Parse (.NET 9) extractor at `tools/extractor/` (see its README).
Verified facts that de-risk the whole track:

- **Paks are NOT encrypted.** Decoded the UE5.4 `FIoStoreTocHeader` of
  `pakchunk0-WindowsClient.utoc`: `EncryptionKeyGuid` (offset 0x40) = all zeros;
  `ContainerFlags` (0x50) = `0x0D` = `Compressed|Signed|Indexed` — **Encrypted bit
  (0x02) not set**. `DirectoryIndexSize` non-zero ⇒ file paths intact. So everything
  mounts with **no AES key** and full filenames.
- **Content is all baked into the shipped paks** (not content-service-delivered):
  mounted **107,123 files** keyless. The string tables the client reports missing are
  present — `ST_Cosmetics_Categories`/`ST_Cosmetics_Names` at
  `Loki/Content/Loki/UI/Widgets/FrontEnd/MainMenu/Monetization/Shared/`, plus
  `ST_Storefront`, `ST_MainMenu`, `ST_Currencies`, `ST_Items`, `ST_Rarities`,
  `ST_ShopNames`, `ST_Armory`, … This reframes "extraction": the client already HAS the
  tables; what we extract is the **IDs/SKUs the backend must echo** so the lookups
  resolve.
- **25 heroes** (codenames, from `Characters/Heroes/<X>/` dirs): Alchemist Assault
  BacklineHealer Beebo BountyHunter BurstCaster Earthtank FarShot FireFox Flex Freeze
  Gunner HookGuy Huntress Reaper ResHealer RocketJumper Ronin ShieldBot Sniper Stalker
  Storm Succubus Void Wukong. Cosmetic skins are per-hero dirs
  (`.../Cosmetics/<SkinName>/`, e.g. Ronin → Default/ONI/StreetInferno/BeastSlayer).
  NB: codenames are probably NOT the backend SKU format (the grid resolves a packed
  catalog id) — need the catalog values, which need a usmap (below).
- **Oodle:** `.ucas` is Oodle-compressed; tool auto-fetches `oo2core_9_win64.dll` via
  `OodleHelper.DownloadOodleDllFromOodleUEAsync` (the sync `DownloadOodleDll` URL is
  dead). Working.

### THE ONE BLOCKER: a `.usmap` mappings file

This is a **shipping build with unversioned properties**. Reading any asset's *property
values* (DataTable rows, string-table key→value, prices, hero/cosmetic SKUs) requires a
`.usmap`. CUE4Parse's `IoPackage` ctor throws `Package has unversioned properties but
mapping file is missing` (in `get_CanDeserialize`) without one — even `NameMap` is
unreachable through it, and `UseLazyPackageSerialization = true` doesn't help (the ctor
checks before lazy bodies). Path enumeration is the only usmap-free capability.

A usmap is generated by a **runtime dumper injected into the live game** (UE4SS dumper,
or Dumper-7). **Anti-cheat risk here is ~nil**: official servers are dead, we run a
local fake backend, and the shipping exe is launched directly (EAC bootstrapper bypassed
⇒ EAC not enforcing; no live service to ban against). Once `mappings.usmap` sits beside
the extractor exe, `dump`/`names` modes read full structured JSON and Track A flows.

### usmap dumping is BLOCKED — and why it doesn't matter

The shipping exe is a **packed/protected binary**: its PE import table lists ONLY
`preloader.dll` (preloader + runtime.dll unpack the real UE engine at runtime). Verified
no EasyAntiCheat anywhere (no EAC files; preloader/runtime import nothing EAC-related).
Consequences:
- **UE4SS proxy method fails**: the exe never imports `dwmapi.dll`, so no proxy DLL of
  any name (dwmapi/xinput/version/…) is ever loaded → UE4SS never initializes (no
  `UE4SS.log`, no console). Confirmed across UE4SS v2.5.2 and v3.0.1-experimental.
- **DLL injection fails too**: a CreateRemoteThread+LoadLibraryW injector
  (`tools/inject/`, verifies load via the target's module list) could not load UE4SS.dll
  nor the renamed loader — the packed process blocks non-system DLL loads (signature
  mitigation / packer). So the usmap-dumper route is closed.

**The workaround that unblocks Track A anyway — read the NameMap with an empty usmap.**
CUE4Parse's `IoPackage` ctor only throws because `CanDeserialize` checks
`MappingsContainer != null`. Feed it a **hand-crafted empty `.usmap`** (24 bytes:
magic 0x30C4, v0, no compression, 0 names/enums/structs — `tools/extractor/empty.usmap`,
generated in the README) and the ctor completes, exposing `IoPackage.NameMap`. The name
map is the FName vocabulary of a package: asset references, FName-typed property values,
and (crucially) the **SKU identifiers**. We do NOT need the property *values* /
string-table contents, because the client resolves display strings from ITS OWN packed
string tables — the backend only needs to send SKU keys the client can look up.

What this recovered (fully offline, no game process — `extractor` `names`/`namesall`
modes): the **entire storefront catalog** from `Loki/Content/Loki/Core/StoreOffer/
BP_StoreOffer_*` (56 offers → `out/storeoffers.names.txt`):
- Currency offer SKUs: `vp10`…`vp480` (Vive Points), `tp475`…`tp11000` (+`*token`
  exchange variants).
- Cosmetic SKUs by type prefix: `AVATAR_*`, `GLIDER_*`, `WISP_*`, `SPRAY_*`, skin codes
  (`WukongCYBER`, `StalkerCYBER`, `HuntressGODQU`…), `PlayerTitle`, `LobbyPlatform`,
  `Emote`; bundle types `HeroCosmeticsBundle`/`SlotCosmetics`.
- Bundle/offer IDs: `CyberpunkWukongPack`, `DarkOrderSniperPack`, `starter2024`,
  `collector2024`, `supporter2024`, `earlybirdob`, …
- **Hero SKU format lead**: hero-pack offers reference heroes by **lowercase codename**
  (`assault`, `beebo`, `flex`, `freeze`, `gunner`, `rocketjumper`, `stalker`, `void`) —
  so `/storefront/heroes` likely wants lowercase codenames, not the PascalCase the
  Milestone-2 probe sent. `menu.go handleHeroes` now returns all 25 lowercase codenames
  to test this.

Still gated on a real usmap (or the probe-loop): the backend **response struct shapes**
(FLokiStorefrontPlayerStore item-offer fields, prices) — types we can't read from name
maps. Plan: use the proven decode-probe loop with these real SKUs (relaunch + LogPlatform
Storefront readback), exactly the Milestone-2 method.
