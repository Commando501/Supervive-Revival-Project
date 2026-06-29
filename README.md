# SUPERVIVE Revival Project

Community effort to bring **SUPERVIVE** (Theorycraft Games) back online with a
self-hosted, open-source backend after the official servers were shut down.

The game uses **AccelByte Gaming Services** for identity/login plus Theorycraft's
own **"project Loki"** services (client-config + post-auth) for service discovery,
versioning, and onboarding. All of these are dead. This project stands up a local
Go server that impersonates them, redirects the client to it, and is gradually
working through the menu → matchmaking → in-game path.

## Status

**✅ Milestone 1 — past the login screen.** Steam login → AccelByte token →
service discovery → version check → postauth/reconcile → onboarding skip → menu.

**✅ Milestone 2 — error-free rendered menu.** Validity model for client-config
locked down, `serviceHostnames` populated, lobby WebSocket reachable. The menu
renders without spinners or error banners.

**⏳ Milestone 3 — make the menu *functional*.** Two parallel tracks:

- **Track A — extraction & static knowledge.** `.NET 9` / CUE4Parse extractor
  built; usmap reverse-engineered from this build's non-standard UObjectBase
  layout (`nameOff=0x20`, `classOff=0x18`, NOT stock `0x18/0x10`); full 68,228-asset
  catalog produced. See [docs/findings.md](docs/findings.md), [docs/r2-findings.md](docs/r2-findings.md),
  [docs/game-map.md](docs/game-map.md).
- **Track B — interactive write-back.** `clientprofile` / `lobbyplatform`
  persistence, asset-registry patch plumbing. See [docs/trackb-notes.md](docs/trackb-notes.md),
  [docs/trackb-assetregistry-route.md](docs/trackb-assetregistry-route.md).

**🚧 Open blocker — the empty modals.** ALL HUNTERS grid, the "?" preview, STORE
carousel, COSMETICS browser, and MISSIONS modal all share **one root cause**:
`LokiAssetManager` bypasses UE's primary-asset enumeration scan, so server data
alone can't populate them. Eight backend/native/AR-patch hypotheses tested and
falsified. The backend route is conclusively closed (2026-06-28). Only two
client-side routes remain open: IoStore mod-pak overlay, or deeper native-shim RE.
Full living log: [docs/hero-roster-attempts.md](docs/hero-roster-attempts.md).

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

## Layout

```
server/      Go backend (module supervive-revival/server, zero external deps)
  cmd/ags                  entrypoint: HTTP :8080 + HTTPS :443, request capture
  internal/iam             AccelByte IAM (v3/v4): token, jwks, users/me, validations
  internal/loki            Theorycraft client-config + postauth
  internal/menu            menu/onboarding endpoints + validity model
  internal/interactive     write-back endpoints (clientprofile, store)
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
  sigbypass-mod/           signature-check bypass

configs/     launch-redirect.ps1 — admin script: hosts + cert + server + game launch
docs/        endpoints.md, findings.md, r2-findings.md, game-map.md,
             hero-roster-attempts.md, trackb-notes.md, trackb-assetregistry-route.md,
             lokiassetmanager-vtable-dump.md, capture.log
memory/      project memory files loaded on demand
```

## Quick start

**Steam must be running first**, or login dies with `Auth Failure 14005`
(SteamAPI init fails). Don't launch from Steam — Steam runs the exe without our
`-ini:` overrides, so the redirect doesn't apply.

From an **elevated PowerShell**:

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1          # elevates; sets up redirect, starts server, launches game
.\configs\launch-redirect.ps1 -Revert  # undo hosts + cacert + Engine.ini changes
```

Watch live log at `C:\Users\<you>\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log`.
HTTP traffic is captured to `docs/capture.log`. The server's catch-all returns
`{}` so the client keeps progressing and reveals its next call.

## Key gotchas (learned the hard way)

- **Steam-running prerequisite** above — easy to miss, costs an hour.
- **Loose AR.bin is inert** in this IoStore build. Even a perfectly valid
  AssetRegistry.bin dropped into the loose-file tree is ignored by UE. Deploying
  a patched AR requires an IoStore mod-pak overlay — non-trivial. See
  [docs/trackb-assetregistry-route.md](docs/trackb-assetregistry-route.md).
- **LokiAssetManager bypasses the enumeration scan** for primary asset types,
  which is why the ALL HUNTERS / STORE / COSMETICS / MISSIONS modals are all
  empty for one shared reason. Backend-only fixes cannot populate them.
- **Non-standard UObjectBase layout** in this build: `nameOff=0x20`,
  `classOff=0x18`. Stock CUE4Parse / UAssetGUI offsets are wrong here.
- **UE's `JsonObjectStringToUStruct` ignores unknown JSON keys** and only rejects
  the doc when a *matched* key has the wrong type. Speculative fields are safe;
  wrong-typed matched fields kill the whole document. Two distinct
  `LogLokiPlatformQuery` errors mean different things:
  `"Invalid response received"` = required top-level field absent;
  `"Deserialization failure"` = JSON parsed but container type mismatched target.
- **Client-config only applies if it looks newer** (`eTag` / `lastUpdated`);
  without them it parses but is silently dropped.
- **Root→Leaf cert chain required** — a self-signed cert presented as the leaf
  trips OpenSSL even when trusted.
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
