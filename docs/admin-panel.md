# Backend admin panel (2026-07-08)

A web GUI + JSON API for manually adjusting what the ags backend feeds the
client: hunter unlocks, store/ownership SKU lists, wallet balances, per-SKU
prices, mission progress, and per-account player state.

## Where it lives

- **Panel:** `http://127.0.0.1:9210/` once ags is running (flag `-admin`,
  default `127.0.0.1:9210`; empty string disables).
- **Own mux + listener** — nothing shares the game-facing :8080/:443 muxes, so
  no admin route can ever collide with an impersonated client route. Runs
  OUTSIDE the capture middleware (panel traffic never pollutes capture.log).
- **Loopback-only twice over:** bound to 127.0.0.1 AND `admin.Guard` rejects
  non-loopback peers even if `-admin` is rebound wide.
- Code: `server/internal/admin/` (API in `admin.go`, GUI embedded from
  `static/index.html`); wiring in `cmd/ags/main.go`.

## What each tab controls, and whether it actually reaches the client

| Tab | Backing state | Client effect |
|---|---|---|
| Hunters | `menu` config `heroes` list | REAL — inventory feed marks listed heroes IsOwned (unlisted = locked tile); first entry is the IsDefault starter. Applies on menu re-entry/relaunch. |
| Store | `store.{bundles,currency,featured,skins,accessories}` | REAL — drives BOTH storefront advertising AND ownership (`handleInventory` marks every listed asset IsOwned). Unchecking a skin locks it in COSMETICS too. |
| Wallet | `wallet` map | REAL for `vp` (Vive Points, purple counter). The gold counter (Theorycraft Coins) is NOT wallet-driven (battlepass claim state) — no key here can set it. |
| Prices | `prices` map | **INERT for now** — client renders prices from packed CatalogEntry offers; backend Costs proven ignored (2026-07-05 probe). Stored/persisted so the surface is ready if the native cost bridge lands. |
| Missions | `state/interactive.json` `"local"` bucket | REAL via the client-side missions shim (menu-load fetch + poll). Progress only — requirements/maxes/text are client-side DAs. Manifest rows appear after one menu load with `-Missions`. |
| Players | `state/interactive.json` per-id docs | REAL — party poll (~1s) picks up selected hunter immediately; loadout edits auto-bump `loadoutVersion` so ULoadoutReconciler adopts them (a non-bumped write looks like a no-op, see store.go). |

## Config persistence (semantics changed 2026-07-08)

- With no `-config` flag, ags now loads/saves `state/menu-config.json`
  (relative to cwd = `server/` under launch-redirect.ps1 — same place as
  `state/interactive.json`). Panel edits therefore survive the launch script's
  rebuild+restart with no script change.
- **File semantics:** an ABSENT field falls back to the built-in default; a
  PRESENT field is authoritative even when empty (this is how "zero heroes
  unlocked" is expressible — pre-2026-07-08, empty and absent were conflated).
  Implemented via pointer-field parsing (`fileConfig` in menu/config.go). Old
  partial configs that merely omit fields behave exactly as before.
- Runtime safety: handlers read immutable published snapshots
  (`menu.current()`); `menu.Apply` swaps the snapshot and persists. Gotcha
  caught by test: an empty list must persist as `[]` not `null` (`null` reads
  back as "absent" → silently reverts to defaults) — `copyList` keeps empty
  slices non-nil.

## API (all under the admin listener)

```
GET  /api/config                    -> {config, defaults, path}
PUT  /api/config                    -> full-replace apply + persist (unknown fields rejected)
GET  /api/players                   -> {players:[{id,state}]}
GET  /api/players/{id}              -> state doc
PUT  /api/players/{id}              -> replace doc (unknown fields rejected; loadoutVersion auto-bumped)
DELETE /api/players/{id}            -> full account-state reset
GET  /api/missions                  -> {manifest, objectives}
PUT  /api/missions/progress         -> {objectives:{k:v}, replace?} absolute set; replace+empty = reset all
POST /api/missions/match-result     -> same body/engine as /revival/missions/match-result
```

Smoke-tested end-to-end 2026-07-08 (isolated instance, alt ports): config
PUT → live `/storefront/heroes` + wallet reflection + persisted file →
reload-after-restart; match-result fan-out (shared `PlayAGame` advanced both
missions independently); player edit → party poll reflected the new hunter
immediately; unknown-field PUTs rejected 400; GUI driven headless (tabs,
unlock-all, save, match simulator).

## Gotcha found while smoke-testing (not a bug)

The party member's `cosmeticsAssetId` is DELIBERATELY not served (reverted in
interactive.go `buildSoloParty`, dated note 2026-07-08): serving it made the
~1s party poll fight new skin selections. Admin skin edits go to
`heroCosmeticsBundles` (the loadout path) and do NOT surface in the party doc —
expected.
