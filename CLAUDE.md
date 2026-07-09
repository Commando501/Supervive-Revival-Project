# SUPERVIVE Revival — project rules for Claude

This is a reverse-engineering project to revive a Steam-launched UE5.4 game whose
official backends are dead. We've redirected the client to a local Go server
(`server/cmd/ags`) over hosts-file + HTTPS-with-self-signed-cert. The work spans
backend RE, IoStore extraction, native shim injection, and asset-registry patching.
Lots of dead ends. Honor the prior-work docs.

The whole front-end menu is now ONLINE: login, the ALL HUNTERS roster (+ click-to-
refresh), the STORE, COSMETICS, and the full MISSIONS page (with working progress
bars) all render live. That was achieved with the backend feed **plus** a set of
client-side native shims built on a reusable game-thread native-call primitive (see
below). Current frontier = the match-setup layer (launching into a playable map).

## Before doing anything else

### If the user mentions hero/roster/grid/hunters/store/cosmetics/missions modal
**These are SOLVED — they render live.** Do NOT re-open the closed hypotheses.
- **Roster / store / cosmetics** — root cause was one un-set client-side
  catalog-ready sub-flag (`CatMgr+0x354`), NOT the backend, NOT enumeration, NOT
  LokiAssetManager bypass (all falsified over ~13 sessions). Fix = the native shim
  `tools/sigbypass-mod/catalog_store_fix.dll` (self-restoring `jz`-NOP that dodges
  the ~3–5 min integrity check + AssetManager scan + CatalogEntry poke). STORE
  tiles also need the backend to mark cosmetics `IsOwned` (`handleInventory`).
  Living log: `docs/hero-roster-attempts.md`; memory `supervive-hero-roster-blocker`
  + `supervive-store-status`.
- **Missions** — the full page renders client-side via the native-call primitive
  (`AsyncLoadPrimaryAssets` → `CreateMissionModelFromFinalProgress` → swap
  `ProgMgr.MissionsModel`), packaged as `tools/sigbypass-mod/missions_fix.dll`
  (`launch-redirect.ps1 -Missions`). Per-account progress served by the backend.
  Read `docs/session-59-progress-bars.txt` + `docs/missions-progression-hookup.md`;
  memory `supervive-missions-page-status`.

Before RE-touching any of these, READ the relevant doc above first — the value is
the trial-and-error history, and the corrected root causes are easy to regress on.

### Before touching anything menu-shaped
Skim `docs/trackb-notes.md` (Track B endpoint surface + ClientProfileData model)
and `docs/endpoints.md` (every endpoint the client hits + handler status).

### Before touching anything extraction-shaped
Skim `docs/findings.md` and `docs/r2-findings.md` (IoStore catalog + usmap RE +
the non-standard UObjectBase layout in this build: nameOff=0x20, classOff=0x18,
NOT the stock 0x18/0x10). `docs/game-map.md` has the full 68,228-asset catalog.

### Before touching anything AR-bin-shaped
Read `docs/trackb-assetregistry-route.md`. The `assetregistry apply-patch`
extractor subcommand works end-to-end; loose-file AR.bin deployment has been
proven INERT in this IoStore build (UE ignores the loose file even when valid).
Deployment requires an IoStore mod-pak overlay — non-trivial.

### Before touching anything native-shim-shaped
The keystone technique is a **game-thread native-call primitive**: hook
`ProcessInternal` (`base+0x13454A0`), capture a live `FFrame`, then call the target
`UFunction`'s native thunk (`UFunction.Func @ +0xE0`) **directly**. The direct call
has no guards, so it works where slot-56 `ProcessEvent` no-ops for native functions.
Param passing, OUT params (`FFrame.OutParms @ +0x80`), and `AsyncLoadPrimaryAssets`
are all RE'd on top of it. Read `docs/session-55-native-call-primitive.txt` (+ s56/
s57/s58/s59) and the `missions_nativecall_probe*.cpp` / `tools/re/*.py` families
before building a new shim. Memory: `supervive-missions-page-status`.

Two `ProcessInternal` hooks can NOT coexist (they race) — that's why the pick→center
refresh shim (`mainmenu_refresh_pi8`) and the missions shim are mutually exclusive
launch modes.

## Launch / run procedure

From an **ELEVATED PowerShell**:
```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1            # redirect + server + game; auto-injects catalog_store_fix.dll
.\configs\launch-redirect.ps1 -Missions  # also inject missions_fix.dll (swaps out the pick/refresh shim)
.\configs\launch-redirect.ps1 -NoHook    # clean RE run, no shim injection
```

By default the launcher injects `catalog_store_fix.dll` (roster + store + cosmetics)
plus the pick→center refresh shim. `-Missions` swaps the refresh shim for
`missions_fix.dll` (both hook `ProcessInternal`, so only one at a time).

**Steam must be running first**, or login dies with `Auth Failure 14005` (SteamAPI
init fails). Easy to miss; surface this gotcha if you see Steam not running.

The script blocks until the game exits. Read live `Loki.log` at
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` (NOT `docs/` — that's
the backend `capture.log` for HTTP traffic). The loopback admin panel is at
`http://127.0.0.1:9210/` while `ags` runs (hunter unlocks, store/ownership, wallet,
mission progress, per-account state; see `docs/admin-panel.md`).

For iterative server-only restarts (game already running at menu, want to swap
backend behavior): kill `ags`, rebuild with
`& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`,
restart manually (regen certs + re-append to cacert.pem if you want a clean cert
chain). See `docs/hero-roster-attempts.md` "How to reproduce" for the exact recipe.

## Code conventions for this project

- Backend handlers live in `server/internal/<package>/<name>.go`. Each handler's
  comment block should record what was tried + what worked + what didn't, with
  dates. The trial-and-error history is the value.
- Probe-driven backend work: prefer **single-variable changes**. Bundled tests
  (10 changes at once) have repeatedly produced ambiguous results that wasted
  cycles. If a hypothesis fails, REVERT the probe before testing the next one.
- Validity model for endpoints: UE's `JsonObjectStringToUStruct` IGNORES unknown
  JSON keys and only rejects the whole doc when a key that DOES match has a wrong
  type. So adding speculative fields is safe; sending wrong-typed matched fields
  is not. See the comment at the top of `server/internal/menu/menu.go` for the
  full validity model.
- The two distinct LogLokiPlatformQuery error strings mean different things:
  `"Invalid response received"` = a required top-level field is absent.
  `"Deserialization failure"` = JSON parsed but container type mismatched target struct.

## Tooling shortcuts

- **Extractor:** `tools/extractor/` — .NET 9 / CUE4Parse-based. Subcommands:
  `enumerate`, `names`, `namesall`, `dump`, `raw`, `schema`, `assetregistry`.
  Build/run with
  `& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release` from `tools/extractor/extractor`.
- **usmap regeneration:** `tools/usmapdump/usmapdump.exe extract <exe-path>`
  produces `mappings.usmap`. Needed when game updates.
- **usmapdump RE commands:** `strings`, `wstrings`, `xref`, `disasm`, `peek`,
  `threads`, `findgametid`, `assetmgr` — read-only RPM, no injection.
- **Manual mapper / DLL injector:** `tools/inject/` — for no-throw payloads only
  (C++ exception unwinding gets eaten by the packer's vectored exception filter).
- **Native shims:** `tools/sigbypass-mod/` — `catalog_store_fix` (roster/store/
  cosmetics), `missions_fix` (durable missions page), `mainmenu_refresh_pi8`
  (pick→center refresh), `loadout_fix`, `tutorial_launch`, plus the
  `missions_nativecall_probe*` RE series that built the native-call primitive.
- **RPM probes:** `tools/re/*.py` — Python probes driving the native-call primitive
  (struct/field/rep-layout walkers, param/OUT-param builders, mission-model dumps).
- **Admin panel:** loopback JSON API + embedded GUI in `server/internal/admin/`
  (`-admin`, default `http://127.0.0.1:9210/`). See `docs/admin-panel.md`.

## What NOT to do

- Don't run `launch-redirect.ps1 -Revert` casually — that strips the hosts entries
  + cacert mods. Only when the user explicitly asks to clean up.
- Don't use Steam to launch the game for testing the redirect — Steam launches the
  exe with no `-ini:` overrides, so the backend redirects don't apply.
- Don't kill the `SUPERVIVE-Win64-Shipping` process without warning — the user may
  be mid-test.
- Don't propose another C++-exception-using payload for injection. We tested
  three canary variants; the packer's exception handler kills the process even
  with `__CxxFrameHandler3` properly imported.
- Don't propose `ScanPrimaryAssetTypesFromConfig` as a shim target again — the
  function `__report_gsfailure`s mid-call regardless of thread context (verified
  via off-thread call, thread-hijack with fresh stack, thread-hijack with own
  stack, and APC on the real game thread).
- Don't leave a permanent `.text` patch in place — the ~3–5 min code-integrity
  check catches it and kills the process. Any raw `jz`-NOP must be self-restoring
  (patch → let the builder run → restore), the way `catalog_store_fix.dll` does.
- Don't inject two `ProcessInternal`-hooking shims at once — they race. The pick/
  refresh shim and the missions shim are separate launch modes for this reason.
- Don't trust the extracted usmap for replicated container types — it has been
  wrong repeatedly (DS missions work cost several passes). Verify struct/array
  shapes against live RPM.

## Memory layout

`memory/MEMORY.md` is the auto-loaded index. Project memory files (loaded on
demand when topics come up):
- `supervive-revival-overview` — goals, stack, redirect approach
- `supervive-milestone{1,2,3}-status` — chronological milestones
- `supervive-milestone3-trackb-status` — interactive write-back endpoints
- `supervive-hero-roster-blocker` — SOLVED; roster/store/cosmetics root cause + fix
- `supervive-store-status` — STORE online (bundles/skins/featured/supporter packs)
- `supervive-missions-page-status` — missions page + the native-call primitive
- `supervive-customization-persistence` — loadout write-back / equip persistence
- `supervive-dedicated-server-status` — DS stub + missions replication (parked)
- `supervive-tutorial-launch-status` — tutorial force-launch (not yet playable)
- `supervive-rpc-signature-solved` — ServerVerifyViewTarget 40-param signature
- `supervive-ags-cert-rebuild-gotcha` — re-append root.crt to cacert.pem on rebuild
