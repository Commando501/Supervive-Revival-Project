# Hero Roster / Cosmetics / Store enumeration — living attempt log

This document tracks every attempt to make the ALL HUNTERS grid, the hero 3D preview
model, the STORE catalog, and the COSMETICS browser populate with content. They all
share one root cause and one resolution path; this file is the running record of what
we've tried, how we tried it, and what happened.

Sister docs (deeper dives on specific tooling/routes):
- `docs/trackb-notes.md` — Track B endpoint-by-endpoint notes
- `docs/trackb-assetregistry-route.md` — AR.bin patch route details
- `docs/findings.md`, `docs/r2-findings.md` — IoStore catalog + usmap RE
- `docs/game-map.md` — full extracted asset catalog (68,228 assets)
- `docs/endpoints.md` — every endpoint the client hits + handler status

## TL;DR — current understanding (as of 2026-06-28)

**Symptom:** the ALL HUNTERS grid renders empty (no hero cards), the central 3D
preview shows the `BP_LokiHeroSelectPreview_UnknownHero` "?" placeholder, the STORE
FEATURED carousel spins forever, the COSMETICS browser shows no items. Right-side
hero detail panel works (FireFox name "Frontline Pyromaniac" + primary ability icon
+ 3-star difficulty + 20,000 purchase price) — that panel reads FireFox's data
directly from the local cooked paks, independent of backend.

**Root cause (high confidence as of session this doc tracks):** the menu's
roster/store/cosmetics enumeration goes through `UAssetManager::ScanPrimaryAssetTypesFromConfig`
(or a path that depends on its results), and `LokiAssetManager` (this build's
`UAssetManager` subclass, confirmed via `DefaultEngine.ini` `AssetManagerClassName=
/Script/Loki.LokiAssetManager`) deliberately bypasses it. The content-service manifest
registers primary assets *by ID lookup* (verified: `CurrentSeason=Hero:assault` loads
cleanly) but the menu's enumeration does NOT query that registration.

**Backend route is closed.** The fix has to be client-side. Two known approaches, both
substantial:

1. **AR.bin repack via IoStore mod-pak** — the cooked `AssetRegistry.bin` already has
   the data; a higher-priority `.utoc/.ucas` mod pak overlay containing a patched
   AR.bin would deploy it. Patch tool exists (`assetregistry apply-patch`); IoStore
   writer doesn't. ~1–2 days of new tooling, or pull `IoStore.exe` from a UE5.4 SDK.
2. **Native scan-call shim** — call `UAssetManager::ScanPrimaryAssetTypesFromConfig`
   directly. Manual mapper works, addresses are stable + found, APC + thread-hijack
   reach the real game thread, but the function `__report_gsfailure`s (stack-cookie)
   mid-call regardless of thread context. Days more RE to bypass.

## How to reproduce a clean test (procedure that finally worked, 2026-06-28)

1. **Steam MUST be running first** — otherwise SteamAPI init fails and login dies with
   `Auth Failure 14005`. We lost 30 min chasing this before noticing.
2. Elevated PowerShell, then either:
   - Full launch: `cd "G:\git\Supervive Revival Project"; .\configs\launch-redirect.ps1`
     (blocks until the game exits; rebuilds server, sets hosts redirect + cacert, sets
     `bVerifyPeer=false` in Engine.ini, launches exe with `-ini:` overrides)
   - Iterative server-only restart (when game is already in a known state):
     ```powershell
     Get-Process ags -ErrorAction SilentlyContinue | Stop-Process -Force
     $go = "$env:ProgramFiles\Go\bin\go.exe"
     & $go build -C "G:\git\Supervive Revival Project\server" -o "...\ags.exe" ./cmd/ags
     # then re-run the launch script if you need to regen certs/cacert
     ```
3. Hosts file occasionally throws `process cannot access the file` errors — known
   intermittent lock by Windows DNS Client / antivirus. Wait 3–5s and retry; the
   launch script doesn't auto-retry but the relevant section is small enough to run
   manually.
4. After launch: log lives at `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`.
   The signals to grep for: `Unlockable heroes fetched: N`, `Wallet fetched: N balances`,
   `Refreshed player inventory`, `LogAssetManager`, `Invalid Primary Asset`, `SetHero`,
   `UnknownHero`, `ChangeBundleState`. Backend traffic mirrors to `docs/capture.log`.

## Attempt log (chronological)

### Attempt 1 — Heroes map with lowercase codenames (PROBE #1, prior session)

**Hypothesis:** the client uses our /storefront/heroes 25 codenames as PrimaryAssetIds
of type `Hero:<codename>` to render the grid.

**Method:** populated `/storefront/heroes` with 25 lowercase codenames; populated
`/content-service/manifest/{v}.Heroes` with 25 entries each carrying only
`PrimaryAssetName: <codename>` (skipped other fields to minimize wrong-type rejection
risk). Other manifest maps left empty.

**Result:** `LogPlatformStorefront: Unlockable heroes fetched: 25 heroes` succeeded.
3338x manifest-retry loop dropped to 1 (manifest now accepted). Diagnostic
`CurrentSeason=Hero:assault` → asset loaded with no error → proves manifest
registration works for ID-based lookup. **But grid stayed empty.**

**Conclusion:** manifest registration ≠ grid enumeration. Grid uses a different query
path. (At the time we suspected we needed AssetPath; see Attempt 2.)

### Attempt 2 — Inventory ownership probes with various shapes (PROBE #1, prior session)

**Hypothesis:** the grid is gated on inventory ownership; populate ownership →
entries become visible.

**Method (bundled, ~10 simultaneous changes):** tried various inventory entry shapes
including IsOwned booleans, EntitlementIDs, PurchasedAt timestamps, and various ID
formats (lowercase codenames, Type:Name format).

**Result:** lowercase codenames triggered `LogAssetManager: Warning: Invalid Primary
Asset Type` — proving the inventory's ID field is parsed as a typed PrimaryAssetId,
NOT a plain SKU. No grid change with any shape tested.

**Conclusion:** bundled test, so any single change's contribution was confounded.
This eventually led to the AR-route theory but never decisively isolated whether
ownership alone would have moved things. (Attempt 8 below isolated this cleanly:
**ownership entries with correct Type:Name format also have no effect.**)

### Attempt 3 — MissionPool probe via Powers map (PROBE #1, 2026-06-28 early)

**Hypothesis:** if we put MissionPool entries into the manifest's Powers map (a
known-consumed map), they'll register and the Missions modal will populate.

**Method:** injected the 16 mission pools as MissionPool-typed entries into the
Powers map. CurrentSeason → `MissionPool:DA_MissionPoolDailyChallenge`.

**Result:** `LogAssetManager: Warning: Invalid Primary Asset Id
MissionPool:DA_MissionPoolDailyChallenge: ChangeBundleStateForPrimaryAssets failed to
find NameData`.

**Conclusion:** **the manifest consumer keys the registered type STRICTLY off the
MAP NAME, ignoring each entry's `PrimaryAssetType` field.** With no Missions/MissionPool
map in the `ContentServiceContentManifest` struct, the manifest cannot carry missions
at all. Same diagnosis applies to any other type not in the 11 known maps.

### Attempt 4 — MissionPool probe via Heroes map (PROBE #2, 2026-06-28 early)

**Hypothesis:** confound-control on #3 — try the PROVEN-CONSUMED Heroes map with a
per-entry MissionPool PrimaryAssetType.

**Method:** put a MissionPool entry inside the Heroes map (which we know the client
consumes). Per-entry `PrimaryAssetType: "MissionPool"`.

**Result:** identical "Invalid Primary Asset Id" error.

**Conclusion:** decisive. **Per-entry PrimaryAssetType field is ignored; only the map
name matters.** Missions cannot be carried by the manifest. **Backend route fully
exhausted for missions.** Same constraint propagates to anything else: only the 11
named maps' types are registerable.

### Attempt 5 — AR.bin loose-file drop (2026-06-28 mid)

**Hypothesis:** modifying `Loki/AssetRegistry.bin` to flip the AssetClass on
specific entries to `LokiDataAsset_Mission` / `LokiDataAsset_MissionPool` will make
the client's `ScanPathsForPrimaryAssets` register them on its own at startup.

**Method:** built `tools/extractor` subcommand
`assetregistry apply-patch --target <PkgNeedle> --to <Pkg>:<Asset>`. Walker mirrors
CUE4Parse byte-for-byte through the FAssetData array, records each entry's AssetClass
field offset, then does targeted 8-byte overwrites preserving file length. Validated
end-to-end: 16 entries patched cleanly (4 `DA_MissionPoolDailyChallenge` →
`LokiDataAsset_MissionPool`; 12 daily missions → `LokiDataAsset_Mission`). Dropped at
`<GameRoot>\Loki\AssetRegistry.bin` AND `<GameRoot>\Loki\Content\AssetRegistry.bin`.

**Result:** game launched, `LogAssetRegistry: Premade AssetRegistry loaded from
'../../../Loki/AssetRegistry.bin'` looked promising. But every metric matched
pre-patch baseline EXACTLY (same 2 Invalid Primary Asset count, same GameplayCue
warnings, same modal categories).

**Decisive kill-test:** overwrote both loose AR.bin paths with `0xDEADBEEF` repeated.
Game booted normally, zero errors, AR took 0.0008s to start up — **proving the loose
file is ignored entirely**. UE's "Premade loaded from" log message is just the
virtual UFS path; actual data source is the AR.bin embedded in the IoStore .ucas paks
(per-chunk; global cooked AR is in pakchunk0). **Loose-file deployment of AR.bin is
inert in this shipping build.**

**Conclusion:** patch tool works correctly; deployment route requires either an
IoStore mod-pak overlay (canonical UE5 approach, needs UE5.4 SDK + IoStore.exe, no
local install) or a custom CUE4Parse-based .utoc/.ucas writer (~1–2 days new tooling).

### Attempt 6 — Native scan-call shim via thread hijack (2026-06-28 mid-late)

**Hypothesis:** call `UAssetManager::ScanPrimaryAssetTypesFromConfig` directly on
the game's main thread via an injected DLL. The function exists at known RVA
0x34D0807 (located by xref to wide log string at RVA 0x7F70830 "Found multiple \"%s\"
Primary Asset Type entries in \"Primary Asset Types To Scan\" config..."). Signature
`void __fastcall(void* this)` — just needs `this`=AssetManager pointer.

**Method:** built `tools/inject/shim/scan_shim.cpp`. Scans MEM_PRIVATE committed
regions in-process for an object whose `[+0]` == `base+0x888CB78` (LokiAssetManager
vtable) AND `ObjectFlags(@+0x0C)&0x10==0` (excludes the CDO). Manually maps via
`tools/inject/inject.exe mmap` (proven for no-throw DLLs). Bypassed CIG (Code
Integrity Guard) and the packer's signature mitigation.

Iteration sequence:
1. Off-thread call → 0xC0000409 stack-cookie failure. Threads aren't the game thread.
2. Found `GGameThreadId` @ module RVA 0x9D49158 via `usmapdump findgametid` (scans
   .text for cmp/mov reg32 instructions against rip-relative slots, filters by
   "value is a live TID").
3. Thread-hijack on the game thread with fresh stack → 0xC0000409 (TEB stack bounds
   mismatch).
4. Thread-hijack with own-stack → 0xC0000409 (target thread held locks).
5. Off-thread call + impersonate GGameThreadId by patching slot → game survives (SEH
   `__try/__except` wraps the call), but scan AVs immediately downstream.
6. APC strategy — `QueueUserAPC` so the function runs on the real game thread when it
   next enters an alertable wait. APC DOES fire on the game thread (verified within
   30s). Scan still crashes the game.

**Result:** every path lands at `__report_gsfailure`. SEH context shows:
- exception address (RIP) == singleton's address (CPU jumped to data trying to
  execute vtable bytes)
- RCX = stack cookie shifted left 16 bits (0x15A2D9AFBF22 << 16 — matches
  `__security_cookie` at RVA 0x9CDA188)
- RAX = 0

This pattern is consistent with `__security_check_cookie` failing and dispatching to
a failure handler that jumps to a corrupted return address.

**Conclusion:** function entry IS correct (RVA confirmed by string-xref and disasm —
clean MSVC prologue, GetAssetRegistry call, the PrimaryAssetTypesToScan stride-0x1c
config-array iteration loop is right there). The crash happens in a path that
requires engine state we can't trivially marshal — most likely an
output-device/UE_LOG call inside the scan internals that hits uninitialized state and
corrupts the local stack frame. **Calling this function externally is not viable in
this build/state without significantly deeper RE.**

Untried alternatives within this route: (a) call `UAssetManager::ScanPathsForPrimaryAssets`
directly with marshalled args (lower-level, bypasses the config-iteration but requires
constructing `FPrimaryAssetType` + `TArray<FString>` + `UClass*` in memory). (b) patch
the LokiAssetManager subclass to enable the scan during normal init (requires
injection BEFORE LaunchEngineLoop — different injection vector entirely).
(c) hook `FCoreDelegates::OnPostEngineInit`. (d) patch a vtable slot to redirect
StartInitialLoading through the base class.

### Attempt 7 — Manifest HeroCosmeticsBundles populated, isolated (PROBE #2, 2026-06-28 evening)

**Hypothesis:** the grid's empty state is because we never populated cosmetics-bundle
registrations. Heroes map alone (Attempt 1) wasn't enough; the cards need the bundle
asset to render their 3D preview model. Per-entry PrimaryAssetType is ignored (per
Attempt 4), but the map name `HeroCosmeticsBundles` registers them as
`HeroCosmeticsBundle` type.

**Method:** edited [server/internal/menu/menu.go](server/internal/menu/menu.go)
`handleContentManifest` to populate the HeroCosmeticsBundles map with 25 entries:

```go
heroCosmeticsBundles[<Pascal>Default] = map[string]any{
    "PrimaryAssetType": "HeroCosmeticsBundle",
    "PrimaryAssetName": <Pascal>+"Default",
    "AssetPath": "/Game/Loki/Characters/Heroes/<Pascal>/Cosmetics/Default/BP_<Pascal>_Default_CosmeticsBundle",
}
```

PascalCase names recovered from extractor catalog (note: `Earthtank` lower-t,
`FireFox`, `ResHealer`, `RocketJumper`, `HookGuy`, `BountyHunter`, `BurstCaster`,
`BacklineHealer`, `ShieldBot`, `FarShot`). Asset paths verified against
`tools/extractor/out/catalog/bundles/BP_<Hero>_Default_CosmeticsBundle.json`. Other
maps unchanged. Inventory unchanged (empty AssetEntries).

Verified server response with a direct fetch: `GET /content-service/manifest/test`
returned 25 Heroes entries + 25 HeroCosmeticsBundles entries with all 3 fields
populated correctly (e.g. `FireFoxDefault.AssetPath = /Game/.../BP_FireFox_Default_CosmeticsBundle`).

**Result:** game launched, login succeeded, `LogPlatformStorefront: Unlockable heroes
fetched: 25 heroes`, `LogPlatformInventory: Refreshed player inventory`, manifest
consumed without error. **Grid still empty. "?" preview unchanged. Identical
screenshot to baseline. Zero `ChangeBundleStateForPrimaryAssets` activity for any of
the 25 registered `HeroCosmeticsBundle:*Default` IDs. Same two Invalid Primary Asset
warnings firing on empty type/id strings (i.e. the SetHero-with-empty-CosmeticsAssetId
path), unchanged.**

**Conclusion:** the grid populator does NOT enumerate via PrimaryAssetType =
HeroCosmeticsBundle registrations. The manifest entries are accepted and presumably
registered (the manifest consumer cleared the retry loop), but the menu's
list-building code never queries them. This rules out the "manifest needs bundle
data" hypothesis cleanly.

### Attempt 8 — Inventory ownership with typed PrimaryAssetIds (PROBE #3, 2026-06-28 evening)

**Hypothesis:** the grid is gated on ownership; with bundle registrations in place
(Attempt 7), adding typed ownership entries to inventory will unlock enumeration.
Matches user intuition: "Steam never updated → must be backend-fixable; previous
players had heroes via entitlements". The earlier ownership probe (Attempt 2) was
bundled with ~10 other changes; this isolates the variable.

**Method:** edited `handleInventory` to return 50 entries:
```go
{"AssetId": "Hero:<lower>"}
{"AssetId": "HeroCosmeticsBundle:<Pascal>Default"}
```
for each of the 25 heroes. Field shape minimal — just `AssetId` (FString) — so a
wrong field name silently skips entries (no regression risk vs. empty baseline).

**Result:** `LogPlatformInventory: Refreshed player inventory` succeeded — payload
accepted by parser. **Grid still empty. "?" preview unchanged. Identical screenshot
to baseline (third in a row). Same 2 Invalid Primary Asset warnings on empty
type/id. Zero new ChangeBundleState activity for any of the 50 registered AssetIds.**

**Conclusion:** ownership entries with correct Type:Name format also have no effect
on grid enumeration. The "ownership gates the grid" hypothesis is closed.
**Decisive verdict: backend route is exhausted.** Three single-variable tests
(Attempts 1, 7, 8) demonstrate the menu's enumeration doesn't read any of the
endpoints we control.

## Cross-attempt observations

- **The right-side hero detail panel works without backend involvement.** FireFox
  ("Frontline Pyromaniac", FireBolt primary, 3-star difficulty, 20,000 purchase
  price) is hardcoded as "RECOMMENDED FOR NEW PLAYERS" in cooked configs. The
  actor pool preloads `BP_HERO_FireFox` + its ability blueprints at startup
  (`LogActorPooling: Display: Adding /Game/Loki/Characters/Heroes/FireFox/...`).
  So at least one full hero is locally enumerable — we just can't trigger the
  enumeration that would surface the rest.
- **`SetHero` with empty `CosmeticsAssetId` is normal "no hero selected" state.**
  The 4 party-slot `SetHero is clearing TargetAssetId because incoming id was not
  valid` log lines fire on EMPTY strings — they're not failed lookups of our
  registered IDs, they're "the user hasn't selected anything yet" placeholders. We
  spent some time confusing this for an asset-resolution failure on `Hero:firefox`.
- **The two `LogAssetManager Invalid Primary Asset Type/Id` warnings per run also
  fire on empty type/id strings**, not on any of our registered IDs. So the
  AssetManager is being asked to resolve `""` somewhere (likely the `SetHero("")`
  path).
- **Capture surface: client only consults ONE ownership channel.** Full grep of
  capture.log shows the only ownership/inventory endpoints called are
  `/inventory/players/{id}` and `/inventory/free`. No `/storefront/entitlements`,
  no `/iam/v3/.../entitlements`, no `/platform/v3/...` — so additional AccelByte
  entitlements endpoints aren't a hidden lever.
- **The Steam version assumption.** Players in production had access to characters
  without per-hero client updates. That doesn't necessarily mean the mechanism was
  backend-driven on the same channels we control — production servers may have
  populated registration channels that depend on engine state that's now stale, or
  the production client behavior diverges from ours in ways we can't observe (e.g.
  online-only client patches via `/configuration/client` that altered widget
  bindings). Either way, the backend-fixable hypothesis is empirically closed in
  THIS build with THIS captured network surface.

## Routes still open

| Route | Effort | Risk | Likelihood of working |
|---|---|---|---|
| AR.bin patched + deployed via IoStore mod-pak overlay (requires UE5.4 SDK or custom .utoc/.ucas writer) | 1–2 days (find SDK or build writer) | Med — UE may still ignore mod-pak if signature/key checks are enforced | Med — the cooked AR.bin has the data; if loaded, the scan path's source has the entries |
| Native scan-call shim on `ScanPathsForPrimaryAssets` (lower-level than ScanPrimaryAssetTypesFromConfig) | 2–3 days RE + marshalling FPrimaryAssetType/TArray/UClass | High — even more engine state, more types to construct correctly | Low–med |
| Hook `FCoreDelegates::OnPostEngineInit` to invoke scan at the right engine-init point | 2+ days RE | Med — need to find the right registration point | Med |
| Patch `LokiAssetManager` vtable slot for `StartInitialLoading` to redirect through base class | 1–2 days RE | Med — base class may also bypass on this build | Low–med |
| Inject BEFORE LaunchEngineLoop (different vector — IFEO, DLL hijack via the packer's preloader, etc.) | 2–4 days RE | High — may trigger anti-debug | Med if it lands |

## What this affects (all share root cause)

| UI surface | Symptom | Status |
|---|---|---|
| ALL HUNTERS grid | empty | blocked |
| Hero 3D preview (party slot + main) | "?" placeholder | blocked |
| STORE FEATURED carousel | spinning, no offers | blocked |
| STORE BUNDLES/SKINS/ACCESSORIES/SUPPORTER PACKS tabs | empty | blocked |
| COSMETICS browser | empty | blocked |
| MISSIONS modal | 5 empty category tabs render, no missions | blocked (see Attempt 3–4) |
| ARMORY | unclear — needs visual verification | likely blocked |
| Right-side hero DETAIL panel | works for FireFox | works (local-only path) |
| Login/auth | works | done |
| Menu reads (battlepass tracks, wallet, party, progression) | work, error-free | done |
| Menu writes (clientprofile, lobby platform) | persist and round-trip | done |
| TUTORIAL launch from FIND MATCH | blocked on hero selection (which is blocked) | blocked |
