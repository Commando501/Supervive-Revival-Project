# SUPERVIVE Revival Project

Community effort to bring **SUPERVIVE** (Theorycraft Games) back online with a
self-hosted, open-source backend after the official servers were shut down.

The game uses **AccelByte Gaming Services** for identity/login plus Theorycraft's
own **"project Loki"** services (client-config + post-auth) for service discovery,
versioning, and onboarding. All of these are dead. This project stands up a local
Go server that impersonates them, and redirects the client to it.

## Status

**✅ Milestone 1 — past the login screen — COMPLETE.** A Steam login now carries the
client all the way through authentication, service discovery, version check, and
onboarding into the **main menu**.

**⏳ Milestone 2 — make the menu fully populate** (battlepass, personalization, lobby
websocket), then matchmaking and in-game. See [docs/endpoints.md](docs/endpoints.md)
for the current endpoint map and what's stubbed vs implemented.

## How it works

The game (UE 5.4.3, libcurl, build `release2.4.live-156430-shipping`, Steam appid
1283700) is redirected to our server two ways:

1. **AccelByte + PostAuth** services use config-driven base URLs, redirected to
   `http://localhost:8080` (HTTP, no TLS) via UE `-ini:` command-line overrides.
2. **Theorycraft hosts** (`accounts.projectloki…`, `client-config-jx-prod…`) are
   hardcoded HTTPS hostnames, redirected via the **hosts file** to our `:443`
   listener, which presents a **Root→Leaf TLS cert** whose root is appended to the
   game's libcurl CA bundle (`Loki/Content/Certificates/cacert.pem`).

The login → menu path crosses five gates, each satisfied by one piece of our server
(full detail in [docs/findings.md](docs/findings.md)):

| Gate | Solved by |
|---|---|
| Steam login | `POST /iam/v4/oauth/platforms/steam/token` → signed JWT |
| Service discovery | `GET /configuration/public` returns a `ClientConfiguration` (needs `eTag`+`lastUpdated` to *apply*) |
| Version check | `clientVersions` array including the client build |
| postauth/reconcile | service registry resolves `postauth` → `POST /postauth/reconcileRoles` |
| Onboarding skip | `unique_display_name` JWT claim → auth state `Authorized` (skips "Choose Display Name") |

## Layout

```
server/    Go backend (module supervive-revival/server, zero external deps)
  cmd/ags                 entrypoint: HTTP :8080 + HTTPS :443, request capture
  internal/iam            AccelByte IAM (v3/v4): token, jwks, users/me, validations
  internal/loki           Theorycraft services: client-config + postauth
  internal/token          RS256 JWT signer + JWKS
  internal/tlscert        Root→Leaf cert generation
  internal/capture        request logging + empty-success stub
configs/   launch-redirect.ps1 — admin script: hosts + cert + server + game launch
docs/      endpoints.md (live map), findings.md (RE journey), capture.log (runtime)
```

## Quick start

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1          # elevates; sets up redirect, starts server, launches game
.\configs\launch-redirect.ps1 -Revert  # undo hosts + cacert + Engine.ini changes
```

Watch `docs/capture.log` to see exactly what the client requests; implement/stub the
next endpoint and relaunch. The server's catch-all returns `{}` so the client keeps
progressing and reveals its next call.

## Key gotchas (learned the hard way — see docs/findings.md)

- PowerShell `Start-Process -ArgumentList @(...)` doesn't quote array elements; the
  repo path has spaces, which silently truncated server flags. Pass one quoted string.
- UE rejects the **whole** client-config document if any present field has a wrong
  type — send only fields you're sure of.
- The client-config only **applies** if it looks newer (`eTag`/`lastUpdated`); without
  them it parses but is dropped (no error).
- A self-signed cert presented as the leaf trips OpenSSL even when trusted — use a
  Root→Leaf chain.

## Legal / intent

A non-commercial game-preservation project so the community can keep playing a title
whose servers were retired. No game assets are redistributed — you must own and supply
your own copy of SUPERVIVE.
