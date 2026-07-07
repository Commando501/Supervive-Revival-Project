# Session 53 — customization equip persistence (2026-07-06)

## Symptom
In CUSTOMIZATION, selecting any hunter cosmetic (or any other customization
option) shows as selected in the moment, but navigating away and back to the
customization page shows it was NOT actually persisted — the selection reverts.

## Root cause
The equip WRITES landed on `/personalization/players/{id}/<thing>` routes that
were never registered in `internal/interactive`, so they fell through to the
`{}` catch-all (`capture.StubHandler`). Nothing was stored, and the readback GET
returned an empty doc, so on re-entry the page had nothing to repopulate from.

## Recovery (three converging sources, one session)

1. **Live capture** (`docs/capture.log`, this session ~15:07): clicking a glider
   fired
   ```
   POST /personalization/players/{id}/slotcosmetics
   body {"slot":"Glider","asset":"SlotCosmetics:GLIDER_AngelicForce"}
   ```
   (fired twice — the second click was the user re-trying after it didn't stick).

2. **Exe route-fragment table** (`usmapdump wstrings SUPERVIVE… "/personalization/"`
   then `peek` around the hit at live mod-RVA `0x8B4C7C8`): the fragments cluster
   as `"/personalization/players/"` + `/cosmeticsbundle/` `/luxechromas/`
   `/emotes` `/titles` `/slotcosmetics` `/lobbyplatforms` `/privacy`
   `/clientprofile`, sitting right next to `&ULoadoutReconciler::ReconcileLoadout`
   and `"No current loadout"`.

3. **usmap schemas** (`tools/extractor … schema …`). The schema printer had a bug
   — it only unwrapped `DictionaryEntry`, but this CUE4Parse build stores props as
   `KeyValuePair<,>`, so every field printed as `? ?`. Fixed the printer
   (`Program.cs`, KeyValuePair unwrap) and got:
   ```
   struct PersonalizationLoadoutPlatform {
     Str ID; Int64 Version; Array<Byte> EmoteIds; Array<Name> TitleIds;
     Array<SlotCosmeticsEntry> SlotCosmeticsEntries; Bool IsAnonymous; Str Token;
   }
   struct PersonalizationLoadout : PersonalizationLoadoutPlatform {
     Map HeroCosmeticsBundlePreferences; Map LuxeSkinChromaPreferences;
     PrimaryAssetId LobbyPlatformPreference;
   }
   struct SlotCosmeticsEntry { Name Slot; PrimaryAssetId Asset; }   // == captured body
   struct SetEmotesRequest  { Array<Str> Emotes; }
   struct SetTitlesRequest  { Array Titles; }
   struct SetLuxeSkinChromaPreferenceRequest { PrimaryAssetId LuxeAssetID, ChromaAssetID; }
   ```
   No request struct exists for `/cosmeticsbundle/` — its route fragment ends in
   `/`, so the hero id rides in the PATH (handler parses path/query/body).

## The load-bearing model detail
The readback the customization page rebuilds from is `GET /personalization/
players/{id}` (the personalization ROOT — the only GET on this surface, and the
one that already tolerated `{}`). The client reconciles it via
`ULoadoutReconciler`, which **only re-applies a loadout doc whose `Version`
advanced past its `LastLoadoutVersion`**. So a write that stores the equip but
doesn't bump the version is invisible to the client. Every write handler bumps
`playerState.LoadoutVersion`; `lobbyplatforms` now bumps it too (the backdrop is
`LobbyPlatformPreference`, a loadout field).

## Implementation
- `server/internal/interactive/loadout.go` — `registerLoadout()` +
  `handleSetSlotCosmetic` / `handleSetEmotes` / `handleSetTitles` /
  `handleSetCosmeticsBundle` / `handleSetLuxeChroma`, and `loadoutDoc()` which
  builds the PersonalizationLoadout echo/readback.
- `store.go` — new persisted fields: `LoadoutVersion`, `SlotCosmetics` (slot→id),
  `HeroCosmeticsBundles` (Hero→bundle), `LuxeChromas` (luxe→chroma), `EmoteIds`,
  `TitleIds` (raw JSON, verbatim).
- `interactive.go` — `handleGetPersonalizationPlayer` now returns the full
  loadout doc (legacy backdrop probe keys kept alongside — unmatched, harmless);
  `handleSetLobbyPlatform` bumps the version and echoes the loadout superset;
  `Register` calls `registerLoadout`.
- Empty-asset writes UNEQUIP that one slot/luxe (entry removed) rather than
  wiping the whole map; requests with no usable id are a no-op (never a wipe).

## Validation
- `go test ./internal/interactive/` — pass (`loadout_test.go`: slot round-trip +
  unequip + no-op, emotes/titles verbatim, cosmeticsbundle tolerant-parse across
  body/path/query/object forms, luxe round-trip, lobbyplatform-in-loadout).
- Hot-swapped `ags` under the running game (PID 75172; killed old, rebuilt,
  restarted reusing the existing `certs/` chain — no relaunch, game reconnected
  clean). Live HTTP round-trip confirmed: POST `slotcosmetics` → readback carries
  the entry, `version` increments 0→1. Test injection then unequipped so the
  user's own picks drive state (persisted `loadoutVersion` left at 2, monotonic).

## Still open — needs one in-game pass (client not driven this session)
1. Equip a cosmetic in CUSTOMIZATION, leave + re-enter the page → confirm it
   stays selected (readback path). This is the user-reported repro.
2. Relaunch → confirm it survives (disk persistence via `state/interactive.json`).
3. For `emotes/titles/cosmeticsbundle/luxechromas`, capture a real click in
   `capture.log` to confirm/trim the best-guess request shapes (they no-op if the
   guess is wrong, so no regression meanwhile). `slotcosmetics` is already
   capture-confirmed.
