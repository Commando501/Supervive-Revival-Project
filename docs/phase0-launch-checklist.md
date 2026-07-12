# S74 / B1 — Phase-0 launch checklist (the make-or-break server test)

**Question this answers:** does the shipping `SUPERVIVE-Win64-Shipping.exe` run as a **server**
at all? If yes (even one that then errors on Agones/AccelByte), the "real exe as the dedicated
server" route (B1) is ALIVE and we proceed to Phase 1. If it silently runs as a client / never
binds a listener / exits immediately, B1 is DEAD → fall back to B2 (force-open `EGP_BeginInit`) or bank.

Scoping/rationale: [session-74-b1-real-exe-as-server-scoping.md](session-74-b1-real-exe-as-server-scoping.md).
Needs an **elevated** shell and **Steam running** (project convention; login/auth dies otherwise).

---

## 0. Pre-flight (clear the field)

- [ ] **Steam is running** (SUPERVIVE requires it, or SteamAPI init fails — Auth Failure 14005).
- [ ] **Free port 7777.** The S73 DS stub (`UnrealEditor-Cmd`) is currently listening there and
      MUST be killed. The script does this; manually: `Stop-Process -Name UnrealEditor-Cmd -Force`.
- [ ] **Decide about the S73 client** (`SUPERVIVE-Win64-Shipping.exe`). Phase 0 doesn't need it, and
      the server instance uses a separate `-abslog`, so logs won't clash. If the OS/Steam refuses a
      2nd instance, close the client first (script: add `-KillClient`).
- [ ] **(Recommended) bring the backend up without the client** so the server's AccelByte/server-auth
      calls resolve instead of hanging on NXDOMAIN:
      ```powershell
      cd "G:\git\Supervive Revival Project"
      .\configs\launch-redirect.ps1 -NoLaunch      # hosts + cacert + ags(:8080/:443), NO client
      ```

## 1. Launch (the test)

**Easiest — the wrapper (kills the stub, launches, tails + classifies):**
```powershell
cd "G:\git\Supervive Revival Project"
.\configs\phase0-server.ps1                 # dedicated -server on :7777, separate log, live classifier
```
Variants if the first is inconclusive:
```powershell
.\configs\phase0-server.ps1 -Mode listen    # listen server (?listen) instead of headless -server
.\configs\phase0-server.ps1 -NoSteam        # a dedicated server usually needs no Steam client
.\configs\phase0-server.ps1 -NullRhi        # + -nullrhi -nosplash -unattended (standard DS args)
.\configs\phase0-server.ps1 -KillClient     # also close the running client first
```

**Manual equivalent (if you'd rather run the exe yourself):**
```powershell
$exe = "G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\SUPERVIVE-Win64-Shipping.exe"
$url = "/Game/Loki/Maps/Tutorial/LVL_Tutorial?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.BP_LokiGameMode_Tutorial_C"
& $exe $url -server -port=7777 -log -abslog="G:\git\Supervive Revival Project\docs\phase0-server.log"
```
Add `-ini:Engine:[/Script/AccelByteUe4Sdk.AccelByteSettings]:BaseUrl=http://localhost:8080` (and the
IAM/Platform/Basic/PostAuth overrides from `launch-redirect.ps1` L295-309) so server-auth hits ags.

## 2. Watch the log

Server instance log: **`docs\phase0-server.log`** (via `-abslog`). If `-abslog` was ignored, it falls
back to the shared client log `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (another
reason to have the client closed). Live-watch manually:
```powershell
Get-Content "G:\git\Supervive Revival Project\docs\phase0-server.log" -Wait -Tail 40
```

### Signal table

| Verdict | Look for (any of) | Meaning |
|---|---|---|
| **✅ GO** | `LogNet: ... IpNetDriver ... InitListen` / `listening on port 7777` / `Created socket` | Server bound a listener — it IS running as a server. |
| **✅ GO** | `NetMode ... NM_DedicatedServer` / "Dedicated server" / `LokiReplicationGraph` init | Engine came up in dedicated-server net mode. |
| **✅ GO** | `LokiServerPlatformInstance` constructed / `ServerAuthManager` / `ServerCoreGameManager` | `ULokiGameInstance` built the SERVER platform instance — the exact thing client-mode never did. |
| **✅ GO (via error)** | `Agones ... (connect/fail)` / `AccelByte ... server ... (fail/auth)` / **absence** of "failed to get ULokiServerPlatformInstance" | It got INTO server bootstrap and only tripped on the external deps we'll fake in Phase 1. This is success for Phase 0. |
| **❌ NO-GO** | Browses to `LVL_Login` / `LVL_LobbyV2` / spawns `BP_LoginHUD` / shows the menu | It ran as a **client**, not a server. |
| **❌ NO-GO** | Immediate `RequestExit` / `LogExit` with no listener / "server code not available" / instant exit | Server code stripped/disabled in this client-target build. |
| **⚠️ Investigate** | `Fatal error` / `Assertion failed` / Sentry crashpad early | Packer/anti-tamper (`preloader.dll`) rejecting the server role — try `-NoSteam`, `-NullRhi`, or `listen` mode. |

## 3. Decision

- **GO** (any ✅, including the error path) → B1 is alive. Next = **Phase 1**: stand up an Agones local
  SDK server (or fake `:9357/:9358`), add AccelByte server-side auth/session + Nexon endpoints to ags,
  get `ULokiServerPlatformInstance` fully built so the DS advances the round past `EGP_BeginInit`
  natively. Then Phase 2 = connect the client (S62 already lands it on :7777).
- **NO-GO** → the client-target build won't host. Fall back to **B2** (continue force-open, attack the
  `EGP_BeginInit` advance directly) or **bank** the S70/S73 spectator milestone.
- **Inconclusive** → sweep the variants (listen / -NoSteam / -NullRhi), then read `phase0-server.log`
  end-to-end grepping `NetMode`, `IpNetDriver`, `ServerPlatformInstance`, `GameInstance`.

## Gotchas
- **`-abslog` clobber:** two SUPERVIVE instances share `Loki.log` unless `-abslog` is honored. Keep the
  client closed for a clean read, or trust `docs\phase0-server.log`.
- **Steam 2nd-instance:** Steam is single-app-instance; a server instance alongside a running client may
  be refused → use `-NoSteam` and/or `-KillClient`.
- **Don't expect playable here.** Phase 0 only proves the server code path engages. Agones/auth errors
  after that are EXPECTED and are themselves the GO signal.
- **Revert nothing:** this test changes no game files (no hosts/cacert edits beyond what `-NoLaunch`
  already did). Closing the server instance leaves the box as it was.
```
