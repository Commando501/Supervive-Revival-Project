# SUPERVIVE Revival Project

Community effort to bring **SUPERVIVE** (Theorycraft Games) back online with a
self-hosted, open-source backend after the official servers were shut down.

The game uses **AccelByte Gaming Services** for identity/login plus Theorycraft's
own **"project Loki"** services (client-config + post-auth) for service discovery,
versioning, and onboarding. All of these are dead. This project stands up a local
Go server that impersonates them, redirects the client to it, and — combined with
a set of client-side native shims — has brought the whole front-end menu online:
login, the hunter roster, the store, cosmetics, and the missions page all render
live. Work is now pushing into the match-setup layer (launching into a map).

## Status

**✅ Milestone 1 — past the login screen.** Steam login → AccelByte token →
service discovery → version check → postauth/reconcile → onboarding skip → menu.

**✅ Milestone 2 — error-free rendered menu.** Validity model for client-config
locked down, `serviceHostnames` populated, lobby WebSocket reachable. The menu
renders without spinners or error banners.

**✅ Milestone 3 — the menu is *functional*.** Every front-end system that was
empty now populates live (see below). Achieved with a backend feed **plus** a
handful of client-side native shims; the pure-backend route alone could not do it.

- **✅ ALL HUNTERS roster** renders the full hunter grid; clicking a hunter
  updates the HUNTERS preview *and* the main-menu center live.
- **✅ STORE** — BUNDLES, SKINS, FEATURED, and SUPPORTER PACKS all render with
  real tiles and art. (Prices are still unavailable — a separate deeper fix.)
- **✅ COSMETICS** browser populated (all owned cosmetics render).
- **✅ MISSIONS** modal renders the full page — ONBOARDING / DAILIES / WEEKLIES /
  SEASONAL tabs with real descriptions, XP rewards, and working progress bars —
  entirely client-side. Per-account progress is served by the backend and can be
  driven by (currently simulated) match results.
- **✅ Customization persistence** — equipped skins/emotes/titles survive
  leave-and-return and relaunch (loadout write-back wired server-side).

**🚧 Milestone 4 — get into a match.** The tutorial map now force-launches and
renders (`open LVL_Tutorial?game=BP_GameMode_BasicTraining` via the native-call
primitive), but it isn't yet *playable*: no `PlayerStart`, no drop-in spawn, no
hero. The remaining work is the match-setup layer (game state + spawn + hero).
See the [tutorial-launch memory](memory/supervive-tutorial-launch-status.md).

### Two exploratory routes (partial / parked)

- **Dedicated-server stub** (`unreal-stub/`). The menu-load crash was solved and
  `LokiPlayerState_Missions` replication was built and live-verified — the class
  binds by path and replicates cleanly. But a dedicated server can't render a
  *visible* menu modal (the menu is GameMode-driven and the stub only supplies
  stock classes), so the missions work was **pivoted to the client-side shim**.
  Still the foundation for a future "server-as-activation-layer" design. See
  [docs/dedicated-server-stub.md](docs/dedicated-server-stub.md).

## The breakthrough: a game-thread native-call primitive

The single unlock behind the roster refresh, the missions page, and tutorial
launch is a **reusable primitive that calls any native `UFunction` on the game
thread from an injected DLL**. Hook `ProcessInternal` (`base+0x13454A0`), capture
a live `FFrame`, then build your own frame and call the function's native thunk
(`UFunction.Func @ +0xE0`) **directly**. The direct thunk call has no guards, so
it works where `ProcessEvent` silently no-ops for native functions. Parameter
passing, OUT params (`FFrame.OutParms @ +0x80`), and async primary-asset loads
have all been RE'd on top of it. This is the keystone technique for driving the
game's own systems from outside. Detail in
[docs/session-55-native-call-primitive.txt](docs/session-55-native-call-primitive.txt)
and the `missions_nativecall_probe*.cpp` / `tools/re/*.py` families.

## Backend admin panel

A web GUI + JSON API for manually adjusting what the backend feeds the client:
hunter unlocks, store/ownership SKU lists, wallet balances, per-SKU prices (surface
only for now), mission progress, and per-account player state. Runs on its own
loopback-only listener (`-admin`, default `http://127.0.0.1:9210/`) with its own
mux, outside the capture middleware, so it can never collide with an impersonated
client route. Config edits persist to `state/menu-config.json` and survive the
launch script's rebuild+restart. See [docs/admin-panel.md](docs/admin-panel.md).

## How the redirect works

The game (UE 5.4.3, libcurl, build `release2.4.live-156430-shipping`, Steam appid
1283700) is redirected two ways:

1. **AccelByte + PostAuth** services use config-driven base URLs, redirected to
   `http://localhost:8080` (HTTP, no TLS) via UE `-ini:` command-line overrides.
2. **Theorycraft hosts** (`accounts.projectloki…`, `client-config-jx-prod…`) are
   hardcoded HTTPS hostnames, redirected via the **hosts file** to our `:443`
   listener, which presents a **Root→Leaf TLS cert** whose root is appended to the
   game's libcurl CA bundle (`Loki/Content/Certificates/cacert.pem`).

The login → menu path crosses five gates (full detail in [docs/findings.md](docs/findings.md)):

| Gate | Solved by |
|---|---|
| Steam login | `POST /iam/v4/oauth/platforms/steam/token` → signed JWT |
| Service discovery | `GET /configuration/public` returns a `ClientConfiguration` (needs `eTag`+`lastUpdated` to *apply*) |
| Version check | `clientVersions` array including the client build |
| postauth/reconcile | service registry resolves `postauth` → `POST /postauth/reconcileRoles` |
| Onboarding skip | `unique_display_name` JWT claim → auth state `Authorized` (skips "Choose Display Name") |

## How the modals were populated (client-side shims)

The empty ALL HUNTERS / STORE / COSMETICS / MISSIONS modals were falsely
attributed for many sessions to a backend enumeration gap. The **actual** root
causes turned out to be client-side and were fixed with injected native shims:

- **Roster / store / cosmetics** — the grid-builder was gated off by a single
  un-set catalog-ready sub-flag (`CatMgr+0x354`). `catalog_store_fix.dll` opens
  that gate with a self-restoring `jz`-NOP that dodges the ~3–5 min code-integrity
  check, runs the AssetManager scan, and pokes `CatalogEntry` purchasable/owned
  flags. STORE tiles additionally required the backend to mark every cosmetic
  `IsOwned` (`handleInventory`), since `CatalogEntry.CanUse` derives from ownership.
- **Missions** — built entirely from the native-call primitive:
  `AsyncLoadPrimaryAssets` (the mission DAs are *registered* but not *loaded*) →
  `CreateMissionModelFromFinalProgress` → swap into `ProgMgr.MissionsModel`.
  Packaged as `missions_fix.dll`, which on menu load fetches per-account progress
  from the backend, builds the model with real progress bars, and re-applies on a
  poll. Inject with `launch-redirect.ps1 -Missions`.

The living logs are [docs/hero-roster-attempts.md](docs/hero-roster-attempts.md)
(roster/store/cosmetics) and the `docs/session-52…59` files (missions).

## Layout

```
server/      Go backend (module supervive-revival/server, zero external deps)
  cmd/ags                  entrypoint: HTTP :8080 + HTTPS :443, admin :9210, capture
  internal/iam             AccelByte IAM (v3/v4): token, jwks, users/me, validations
  internal/loki            Theorycraft client-config + postauth
  internal/menu            menu/onboarding endpoints + validity model + config persist
  internal/interactive     write-back: clientprofile, store, loadout, missions
  internal/admin           loopback admin panel (JSON API + embedded GUI)
  internal/lobby           lobbyplatform persistence
  internal/ws              lobby WebSocket
  internal/token           RS256 JWT signer + JWKS
  internal/tlscert         Root→Leaf cert generation
  internal/capture         request logging + empty-success catch-all

tools/       Reverse-engineering toolbox
  extractor/               .NET 9 / CUE4Parse — enumerate, names, dump, raw,
                           schema, assetregistry, bpdump subcommands
  usmap/                   usmap library
  usmapdump/               native RPM tool: strings, xref, disasm, peek, threads,
                           findgametid, assetmgr (no injection)
  inject/                  manual mapper + DLL injector (no-throw payloads only —
                           packer's vectored exception filter eats C++ unwinds)
  sigbypass-mod/           native shims: catalog_store_fix (roster/store), missions_fix,
                           mainmenu_refresh_pi8 (pick→center), loadout_fix, tutorial_launch,
                           and the missions_nativecall_probe* RE series
  re/                      Python RPM probes driving the native-call primitive

unreal-stub/ Dedicated-server module (LokiPlayerState_Missions replication) — parked
configs/     launch-redirect.ps1 — admin script: hosts + cert + server + game + shim inject
docs/        endpoints.md, findings.md, r2-findings.md, game-map.md, admin-panel.md,
             hero-roster-attempts.md, missions-progression-hookup.md, dedicated-server-stub.md,
             trackb-notes.md, trackb-assetregistry-route.md, session-*.txt handoffs
memory/      project memory files loaded on demand
```

## Quick start

**Steam must be running first**, or login dies with `Auth Failure 14005`
(SteamAPI init fails). Don't launch from Steam — Steam runs the exe without our
`-ini:` overrides, so the redirect doesn't apply.

From an **elevated PowerShell**:

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1           # redirect + server + game; auto-injects catalog_store_fix.dll
.\configs\launch-redirect.ps1 -Missions # also inject the durable missions shim (missions_fix.dll)
.\configs\launch-redirect.ps1 -NoHook   # clean RE run, no shim injection
.\configs\launch-redirect.ps1 -Revert   # undo hosts + cacert + Engine.ini changes
```

By default the launcher injects `catalog_store_fix.dll` (roster + store + cosmetics)
plus the pick→center refresh shim. `-Missions` swaps the refresh shim for
`missions_fix.dll` — the two can't coexist because both hook `ProcessInternal`.

Watch live log at `C:\Users\<you>\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`.
HTTP traffic is captured to `docs/capture.log`. The log starts fresh on every
server launch and is capped at 256 MB (`-log-max-mb`); in both cases the prior
contents rotate to `docs/capture.log.prev`. The server's catch-all returns
`{}` so the client keeps progressing and reveals its next call. The admin panel is
at `http://127.0.0.1:9210/` while the server is running.

## Key gotchas (learned the hard way)

- **Steam-running prerequisite** above — easy to miss, costs an hour.
- **The empty-modal root cause was NOT the backend.** ~13 sessions of
  backend/enum/AR-patch hypotheses were falsified. The real gate was a single
  client-side catalog-ready sub-flag (`CatMgr+0x354`); the durable fix is a native
  shim, not a server change. Don't re-grind the backend hypotheses.
- **`.text` patches trip the ~3–5 min code-integrity check.** Any raw `jz`-NOP
  must be self-restoring (patch, let the builder run, restore) — a permanent patch
  gets caught and the process dies. `catalog_store_fix.dll` does this.
- **Direct native-thunk calls work; `ProcessEvent` doesn't** for native functions
  in this build (slot-56 `ProcessEvent` is effectively a no-op). Use the
  native-call primitive (call `UFunction.Func @ +0xE0` directly from the
  `ProcessInternal` hook) to drive the game's own functions.
- **Only one `ProcessInternal` hook at a time.** The pick→center refresh shim and
  the missions shim both hook it and cannot be injected together — that's why
  `-Missions` is a distinct mode.
- **Missions DAs are *registered* but not *loaded*.** `GetLokiDataAsset` returning
  null means not-loaded, not not-registered — `AsyncLoadPrimaryAssets` first, then
  poll until non-null before building the model.
- **Loose AR.bin is inert** in this IoStore build. A valid AssetRegistry.bin
  dropped into the loose-file tree is ignored; deploying a patched AR needs an
  IoStore mod-pak overlay. See [docs/trackb-assetregistry-route.md](docs/trackb-assetregistry-route.md).
- **Non-standard UObjectBase layout** in this build: `nameOff=0x20`,
  `classOff=0x18`. Stock CUE4Parse / UAssetGUI offsets are wrong here.
- **UE's `JsonObjectStringToUStruct` ignores unknown JSON keys** and only rejects
  the doc when a *matched* key has the wrong type. Speculative fields are safe;
  wrong-typed matched fields kill the whole document. Two distinct
  `LogLokiPlatformQuery` errors mean different things:
  `"Invalid response received"` = required top-level field absent;
  `"Deserialization failure"` = JSON parsed but container type mismatched target.
- **Every loadout write must bump `loadoutVersion`** or `ULoadoutReconciler`
  ignores the echo and the equip reverts.
- **The usmap has been wrong repeatedly** on replicated container types — verify
  struct/array shapes against live RPM, not the extracted map (this cost the DS
  missions work several passes).
- **Client-config only applies if it looks newer** (`eTag` / `lastUpdated`);
  without them it parses but is silently dropped.
- **Root→Leaf cert chain required** — a self-signed cert presented as the leaf
  trips OpenSSL even when trusted. After rebuilding/swapping `ags`, re-append
  `certs/root.crt` to the game's `cacert.pem`.
- **PowerShell `Start-Process -ArgumentList @(...)` doesn't quote array
  elements**; the repo path has spaces, which silently truncated server flags.
  Pass one quoted string.
- **No C++-exception-using payloads** for injection — three canary variants
  tested; the packer's vectored exception filter kills the process even with
  `__CxxFrameHandler3` properly imported.
- **`ScanPrimaryAssetTypesFromConfig` is not a viable shim target** —
  `__report_gsfailure`s mid-call regardless of thread context (verified via
  off-thread call, thread-hijack with fresh stack, thread-hijack with own stack,
  and APC on the real game thread).

## Legal / intent

A non-commercial game-preservation project so the community can keep playing a
title whose servers were retired. No game assets are redistributed — you must own
and supply your own copy of SUPERVIVE.
