# Next session kickoff — Milestone 3 Track B (AssetRegistry repack route)

> Paste the fenced block below into a new session to continue. The older usmap-route
> prompt (kept below for history) is no longer relevant.

---

```
We're picking up the AssetRegistry.bin repack route to unblock missions/hunters/store/
cosmetics in SUPERVIVE. Project root: G:\git\Supervive Revival Project. The game install
backup is at G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\.

READ FIRST: docs/trackb-assetregistry-route.md — full plan, format facts, host-side
workflow, kill criteria. Also docs/trackb-notes.md ("Update 2026-06-28") for the
history of why we're here.

Why this route: LokiAssetManager (UAssetManager subclass) registers primary assets
ONLY from the content-service manifest's 11 named maps and never runs the standard
config-driven directory scan. Baked primary assets (Mission/MissionPool/Hero/StoreOffer/
Item/HeroCosmetic/SlotCosmetic) therefore never register — same root cause behind
empty Missions modal, Hunters grid, Store, Cosmetics. The native scan-call shim
(tools/inject/shim/scan_shim.cpp) crashes in __report_gsfailure inside the scan
function even with empty configs — closed route, not to be re-attempted.

The cooked Loki/AssetRegistry.bin (36 MB, extracted to tools/extractor/out/
AssetRegistry.bin) already contains every asset with its full class info, path, tags,
and bundles. Grep confirms DA_MissionPoolDailyChallenge, LokiDataAsset_MissionPool,
LokiDataAsset_Mission, BP_HeroAsset_Assault, etc. Smallest viable proof = one daily
mission visible in the Missions modal after a relaunch.

TOOLING ALREADY IN PLACE (built last session, untested):
- tools/extractor/extractor/Program.cs gained an `assetregistry` mode with five
  subcommands: stats, classes, inspect <needle>, candidates <classNeedle>, namemap.
  Standalone — no paks, no .usmap, no Oodle. CUE4Parse-based read path on UE5.4.
- Default ar.bin path: tools/extractor/out/AssetRegistry.bin. Override by passing
  an explicit path as args[2].

START BY (diagnostic — answers which patch variant we need):
  cd tools\extractor\extractor
  & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry stats
  & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry classes
  & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry candidates LokiDataAsset_Mission
  & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- assetregistry inspect DA_MissionPoolDailyChallenge

Smoking-gun output: `stats` prints a tag-key histogram. If PrimaryAssetType /
PrimaryAssetName appear, the cook ALREADY baked the metadata onto FAssetData entries
and the route shifts to SURGICAL: flip one entry's class FName index or rewrite its
tag-pair pointer. If those keys are absent, the cook stripped them and the route
shifts to GROWING the FStore (add new strings + new pair) — a much bigger edit.

Read the JSON outputs (tools/extractor/out/assetregistry_*.json), decide the patch
variant, then implement `assetregistry apply-patch`. Back up Loki/AssetRegistry.bin
before any write to it; the launch script configs/launch-redirect.ps1 needs admin
(elevated shell already, no UAC). Memory file is the canonical state record —
update it as findings land.

The legacy usmap-route prompt below is OBSOLETE — kept only for history.
```

---

```
We're continuing the SUPERVIVE Revival Project (G:\git\Supervive Revival Project) —
reviving the shut-down game with a self-hosted zero-dep Go backend. Build the server with
  & "$env:ProgramFiles\Go\bin\go.exe" build -o ags.exe ./cmd/ags   (run from server\)
Milestones 1 (reach the menu) and 2 (populate the menu) are DONE: the client loads into a
fully rendered, broadly-alive main menu. Milestone 3 = make menu SYSTEMS actually WORK,
before gameplay. Two tracks: A = IoStore extraction (the content catalog), B = interactive
backend flows. We are leading with Track A.

READ FIRST (hold everything learned; the supervive-milestone3-status memory also auto-loads):
- docs/findings.md — full RE journey incl. the "Track A" section (paks unencrypted; packed
  exe; usmap story; binary-RE technique).
- docs/endpoints.md — every endpoint's status + the "Invalid response received" validity model.
- server/internal/menu/menu.go — current handlers incl. handleContentManifest (probe #1) and
  handleHeroes (25 lowercase codenames).
- tools/extractor/README.md — the CUE4Parse extractor (how to run, the usmap requirement).

THE BREAKTHROUGH THAT DEFINES THIS SESSION: MANUAL MAPPING WORKS. The shipping exe is a
PACKED binary (PE imports only preloader.dll; preloader+runtime.dll unpack the real UE5.4
engine at runtime), so UE4SS's dwmapi proxy never loads and a simple LoadLibrary injector
(tools/inject/) is blocked by the process's DLL-signature mitigation. BUT the user has
CONFIRMED a manual mapper bypasses this. There is NO EasyAntiCheat (verified). So we can
finally get a real .usmap, which unblocks Track A cleanly.

IMMEDIATE PLAN (Track A, the high-leverage path):
1. usmap: user injects UE4SS (the experimental build, already deployed at
   "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\", with the
   ue4ss\ subfolder; ConsoleEnabled=1) via the working MANUAL MAPPER, reaches the menu, and
   presses Ctrl+NumPad6 (UE4SS "DumpUSMAP" keybind, confirmed in
   ue4ss\Mods\Keybinds\Scripts\main.lua). UE4SS writes Mappings.usmap to the Win64 folder.
2. Copy Mappings.usmap into tools\extractor\ (the extractor auto-loads any *.usmap; DELETE the
   placeholder tools\extractor\empty.usmap first so the real one is used).
3. With the real usmap, run the extractor in `dump` mode to read EXACT structured JSON for:
   - the ContentManifest model + its ContentServicePrimaryAsset entry shape (so we stop
     guessing the manifest field/types),
   - the cosmetic definition assets (BP_<Hero>_DefaultCosmeticsBundle etc.) to get each hero's
     real PrimaryAssetId (Type:Name),
   - DA_ArmoryTables_S1 / DT_* / store-offer BPs for prices and structured relationships.
4. Build GET /content-service/manifest/{version} (handleContentManifest) correctly — it is THE
   master catalog and the lever for HUNTERS / STORE / cosmetics (see "architecture" below).
   Then wire /storefront/heroes, /inventory ownership, and the store offers using the real SKUs
   + PrimaryAssetIds. Then move to Track B (equip cosmetic, etc.).

PROVEN METHOD (unchanged):
- Go server listens HTTP :8080 (AccelByte + PostAuth via -ini: URL overrides) + HTTPS :443
  (Theorycraft hosts via hosts-file redirect). Logs every request to docs\capture.log (WS
  frames as WS <- / WS ->).
- I (agent) CANNOT launch the game. The user runs .\configs\launch-redirect.ps1 (elevated;
  rebuilds from source; GameRoot defaults to the backup) and reports back / sends screenshots.
- Recon: %LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki.log (UTC, OVERWRITTEN per launch — cross-check
  docs\capture.log, the HTTP ground truth). LogPlatformStorefront / LogPlatformInventory /
  LogAssetManager / LogStringTable are the readback channels.
- Binary RE: static string scans of the shipping exe WORK (the packer only stripped imports;
  the UE FName reflection pool is intact, roughly offsets 124M–146M). Use Python to scan ASCII
  + UTF-16LE and cluster names by offset (a struct's UNIQUE fields cluster near its type name;
  SHARED/pooled fields live elsewhere — use the decode-probe loop when clustering isn't enough).

TOOLS BUILT THIS PROJECT:
- tools/extractor/ — headless CUE4Parse (.NET 9) reader of the UE5.4 paks at
  "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Content\Paks". Paks are NOT
  encrypted (no AES key) and keep their directory index. Run from tools\extractor\extractor:
    & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release                      (enumerate -> out\)
    ... run -c Release -- names <pkgpath...>            (dump a package NameMap)
    ... run -c Release -- namesall <substr> <outfile>   (union NameMaps of all matching .uasset)
    ... run -c Release -- dump  <pkgpath...>            (FULL exports as JSON — needs real usmap)
  Oodle auto-fetched (OodleHelper.DownloadOodleDllFromOodleUEAsync; the plain DownloadOodleDll
  URL is dead). With empty.usmap, only NameMap reads work; with a REAL usmap, `dump` works.
- tools/inject/ — a verifying CreateRemoteThread+LoadLibraryW injector (kept for reference;
  insufficient here — use the manual mapper instead).

WHAT WE ALREADY EXTRACTED / KNOW (so you don't re-derive):
- 107,123 files mounted keyless. Content is all baked into the shipped paks (NOT
  content-service-delivered). The "missing" string tables exist (ST_Cosmetics_Categories/_Names,
  ST_Storefront, ST_MainMenu, ST_Currencies, ST_Items, …) — the client resolves display strings
  from its OWN packed tables, so the backend only needs to send the right SKU KEYS.
- 25 hero codenames: Alchemist Assault BacklineHealer Beebo BountyHunter BurstCaster Earthtank
  FarShot FireFox Flex Freeze Gunner HookGuy Huntress Reaper ResHealer RocketJumper Ronin
  ShieldBot Sniper Stalker Storm Succubus Void Wukong. /storefront/heroes accepted all 25 as
  LOWERCASE codenames ("Unlockable heroes fetched: 25").
- Full storefront catalog SKUs harvested offline -> tools/extractor/out/storeoffers.names.txt:
  currency vp10..vp480 / tp475..tp11000 (+*token); cosmetics AVATAR_* GLIDER_* WISP_* SPRAY_*,
  skin codes (WukongCYBER, HuntressGODQU…), PlayerTitle, LobbyPlatform, Emote; bundle IDs
  (CyberpunkWukongPack, starter2024…). Store offers live at Loki/Content/Loki/Core/StoreOffer/
  BP_StoreOffer_*. Each hero's default skin asset = BP_<Hero>_DefaultCosmeticsBundle.

THE ARCHITECTURE (recovered via binary RE — this is the key mental model):
- GET /content-service/manifest/{version}  = MASTER CATALOG (what EXISTS). We stubbed {} and it
  retried 264x/run. Model = ContentManifest: TMap<FString SKU, ContentServicePrimaryAsset> for
  Heroes, Items, Emotes, PlayerTitles, HeroCosmeticsBundles, StoreOffers, SlotCosmetics, Minions,
  GameAugments, Equipment, Powers; plus scalar CurrentPatchVersion + PatchVersions. Entry =
  ContentServicePrimaryAsset (fields incl. PrimaryAssetName / AssetPath / DisplayName — pooled,
  exact types unconfirmed → the usmap will confirm). Event OnContentManifestUpdated.
  -> The "ALL HUNTERS" grid, STORE, and cosmetics ALL populate from this manifest.
- GET /storefront/heroes  = the UNLOCKABLE (purchasable) subset.
- GET /inventory/players/{id}  = the OWNED subset (model LokiPlatformInventory { AssetEntries:
  [ LokiAssetEntry ] }). Heroes/cosmetics resolve via UE AssetManager PrimaryAssetId (Type:Name),
  NOT plain SKUs — an inventory probe of 25 lowercase codenames produced
  "LogAssetManager: Invalid Primary Asset Type" and rendered nothing (since reverted to empty).
  Registered cosmetic primary-asset types include HeroCosmetic / SlotCosmetic / LokiHero /
  LokiCosmetic.

CURRENT menu.go STATE:
- handleHeroes -> 25 lowercase codenames (harmless; correct unlockable subset).
- handleContentManifest -> PROBE #1: all 11 maps present, Heroes populated with {PrimaryAssetName}
  only, scalars set. NOT yet relaunch-tested. With the real usmap, REPLACE this guess with the
  exact ContentServicePrimaryAsset shape + real PrimaryAssetIds/AssetPaths.
- handleInventory -> empty (the probe was reverted).

TRACK B request shapes already spotted in the exe (for later): SetClientProfileRequest,
SetLuxeSkinChromaPreferenceRequest, LokiPlatformCurrencyExchangeRequest,
SetLobbyPlatformPreferenceRequest, LobbyPlatformAssetID.

CRITICAL GOTCHAS (don't re-learn):
- List/object endpoints want the required field PRESENT, else "Invalid response received".
- UE's JsonObjectStringToUStruct IGNORES JSON keys matching no UPROPERTY and ONLY rejects the
  whole doc when a MATCHED key has the wrong TYPE — so probe liberally with safe string/int/array
  values; omit fields whose type you're unsure of (esp. FText/FSoftObjectPath/bool).
- Service name in serviceHostnames has NO hyphen (contentservice); the URL path DOES
  (/content-service). Same for coregame -> /core-game.
- The server runs elevated; my non-elevated shell can't kill it — the launch script restarts it.
- tools/extractor auto-loads any *.usmap in tools\extractor\ (and the build dir). DELETE
  empty.usmap once the real Mappings.usmap is in place.

START BY: confirming the user has Mappings.usmap from the manual-mapped UE4SS dump (Ctrl+NumPad6).
Once it's in tools\extractor\, run `dump` on the ContentManifest-bearing assets + a couple cosmetic
bundles to read exact types, then build /content-service/manifest correctly and iterate via
relaunch. If the usmap isn't ready yet, you can still relaunch-test handleContentManifest probe #1
(watch capture.log for the 264x retry collapsing and Loki.log for OnContentManifestUpdated).
```

---

## Why this framing
- The packed exe killed the proxy + simple-injection usmap routes; the user's confirmed
  manual mapper reopens the clean usmap path, which is far faster than blind-probing the
  nested ContentManifest TMaps.
- Everything needed to act fast is captured: the architecture, the extractor + how to run it,
  the harvested SKUs, the recovered models, and the exact current menu.go state.
