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

## UPDATE 2026-07-08 — first attempt didn't persist; root cause refined + envelope fix

Live repro (user equipped Succubus skin + a glider, left, returned → reverted).
Traced the real client traffic and the game log:

- **Write path is CORRECT and persists.** Real client writes captured:
  - skin: `PUT /personalization/players/{id}/cosmeticsbundle/Hero:Succubus`
    body `{"assetId":"HeroCosmeticsBundle:SuccubusSISTE_GLO"}` (hero in PATH —
    confirms the trailing-slash guess; bundle in body under `assetId`).
  - glider: `POST .../slotcosmetics` body `{"slot":"Glider","asset":"SlotCosmetics:GLIDER_BoneKite"}`.
  `state/interactive.json` shows both stored (slotCosmetics + heroCosmeticsBundles).
- **Equip applies live** (Loki.log: `SK_Succubus_SISTE` skeletal mesh loads on equip).
- **The readback never populates the client loadout model.** Loki.log MENUSPAWNER
  renders `HeroCosmeticsBundle:SuccubusDefault` (the DEFAULT), not the equipped
  SISTE. The client reads the loadout **exactly once, at login**, via
  `GET /personalization/players/{id}` (User-Agent Loki) and **never re-GETs on
  page navigation** (an ags hot-swap RECONNECT does not re-fetch it either — only
  a full relaunch/login does). So:
  - within-session leave/return persistence depends on the client MERGING the
    equip WRITE's response (it doesn't re-read), and
  - cross-relaunch persistence depends on the login GET response.
  Both were returning a BARE loadout object that the reconciler didn't parse.

**Fix shipped:** `loadoutResponse()` now returns the loadout in three envelopes at
once — bare fields, `{"data":<loadout>}` (the confirmed-working convention on the
sibling `/clientprofile` endpoint), and `{"loadout":<loadout>}` — applied to BOTH
the login GET and every write response. Per the validity model this is strictly
safe (UE ignores unmatched top-level keys; no wrong-typed matched keys). Built,
unit-tested, hot-swapped live; `GET /personalization/players/{id}` verified to
serve all three forms carrying the persisted SISTE skin + glider.

**Validation (pending user relaunch):** because the equips are already persisted,
a fresh relaunch should show them ALREADY equipped in CUSTOMIZATION without
re-equipping — IF the reconciler parses one of the three envelopes. If it still
shows default, the envelope/route hypothesis is wrong and the next step is to
disassemble the GET-response deserialize callback (the loadout member is gated by
a has-loadout bool at manager+0x198; log site "No current loadout" @ mod-RVA
0x586723C) to read the exact expected shape. Diagnostics to grep after relaunch:
Loki.log `LogLokiPlatformQuery` result for the personalization query
(Invalid response received / Deserialization failure / silent success) and
MENUSPAWNER `SetHero` cosmetic (SISTE vs SuccubusDefault).

## UPDATE 2026-07-08 (part 2) — envelope hedge FAILED; blocker precisely localized

Relaunch test after the 3-envelope hedge: still shows default. Deep dive:

- Client DID fetch `GET /personalization/players/{id}` at login (twice, Loki UA),
  received our hedged response (5 heap copies of the JSON confirmed via RPM), and
  the loadout stayed empty. **No `LogLokiPlatformQuery` error** for that query
  (battlepass + core-game errored; personalization did not) → the response was
  ACCEPTED but did not populate the loadout model.
- **Even the clean array field (glider / `slotCosmeticsEntries`) failed** to
  populate, not just the maps → this is a WHOLE-loadout parse failure, not a
  per-field type issue.
- WS traffic carries only friends/presence — loadout is HTTP-only.
- Live RPM schema (ground truth, corrects the usmap):
  `FPersonalizationLoadout : FPersonalizationLoadoutPlatform`; fetched by
  `UPersonalizationManager::RefreshCurrentLoadoutOperation` (a `LokiOperation`);
  `GetCurrentLoadout` returns `FPersonalizationLoadout`. `EmoteIds` is actually
  `Array<PrimaryAssetId>` (usmap said Byte); `SlotCosmeticsEntries` inner is
  `SlotCosmeticsEntry{Slot:Name, Asset:PrimaryAssetId}` (write body matches).
- **Why guessing stalled:** the equip WRITES use API-specific JSON keys
  (`slotcosmetics`→`{slot,asset}`, `cosmeticsbundle`→`{assetId}`), so the READ
  response almost certainly uses API-specific keys / an envelope that are NOT the
  UStruct field names — and unmatched keys are silently ignored (no error). The
  exact shape is only in the client's parser (or a real-server response).
- **Tooling wall:** `usmapdump xrefstr` finds 0 refs to the loadout route/stat
  strings — this code references strings via FName/pointer indirection, not direct
  rip-rel LEA — so the parser can't be located by string-xref. Locating it needs
  GUObjectArray-walk tooling (find `FPersonalizationLoadout::StaticStruct` callers
  → the deserialize site) or a captured real-server response (servers are dead).

Backend state deployed and harmless (writes persist; response is a benign
superset). Next step is a fork — see the session summary / decision.

## UPDATE 2026-07-08 (part 3) — NATIVE SHIM built + applies cleanly (user chose shim route)

Reused the s55/s59 Avenue-A native-call primitive (ProcessInternal hook + hand-built
FFrame + call UFunction thunk @+0xE0 on the game thread) from
`missions_nativecall_probe18.cpp`. New shim `tools/sigbypass-mod/loadout_fix.cpp`:
- Resolves the live `LokiAssetManager` + `PersonalizationManager` instances and the
  native UFunctions `PrimaryAssetIDFromString`, `SetHeroCosmeticsBundlePreference`,
  `SetSlotCosmetic`, `SetLuxeSkinChromaPreference` (via class-chain walk).
- `PrimaryAssetIDFromString(str)` returns a full FPrimaryAssetId in the result buffer
  — also the trick for the FName slot: `PrimaryAssetIDFromString("Slot:Glider").name`
  = `FName("Glider")` (solves the "how do I make an FName" problem).
- Fetches `GET /revival/loadout` (new ags endpoint, interactive.loadout.go +
  store.primaryLoadout) and replays each saved equip by calling the game's own setter
  on the game thread — the game builds the TMap/TArray + fires OnUpdated itself.
- Param offsets read from each UFunction's child-property chain (ParamOffsets), so
  struct/FName args land where the thunk reads them.

LIVE (PID 80596, injected via `inject.exe mmap`): resolved everything, fetched
ok=1 (1 bundle + 3 slots), and `applied 4 equip(s)` with **NO crash / no VEH**
(marker `docs/loadout-fix-marker.txt`). Backend feed confirmed serving the real
equips (Succubus skin + Glider AngelicForce / Spray Dumpling3 / Wisp BeatUpRadish).

Build:  `clang++ -shared -O2 loadout_fix.cpp -o loadout_fix.dll -lkernel32 -lwininet`
Inject: `tools/inject/inject.exe mmap <PID> tools/sigbypass-mod/loadout_fix.dll`

PENDING: (1) user visual confirm in CUSTOMIZATION (equips show + persist on
leave/return); (2) wire auto-inject into launch-redirect.ps1 (secondary injector,
after login) so it runs every launch; (3) PI-hook coexistence — loadout_fix hooks
ProcessInternal like mainmenu_refresh_pi8/missions_fix; if run together, share the
`Local\SuperviveMissionsPIHook` mutex (currently standalone). NOTE loadout_fix
applies ONCE ~4s after gameTid; if a late login loadout-refresh overwrites it, add a
re-apply loop.

## UPDATE 2026-07-08 (part 4) — slots CONFIRMED persist; skin diagnosed; auto-inject wired

Live test (user): **glider + wisp + spray persisted** across leave/return — the shim
approach works. Skin appeared not to persist, but the diagnosis is subtler:
- Probe added to the shim: after `SetHeroCosmeticsBundlePreference`, call the game's
  own `GetHeroCosmeticsBundlePreference(Hero:Succubus)` back → it returned the value we
  set. So the setter **does populate the local map** (not server-only, unlike a first
  guess). Marker: `[probe] ... out='SuccubusDefault_MAS'`.
- The only skin value in the backend this session was `SuccubusDefault_MAS` (the
  captured `cosmeticsbundle` PUTs were ALL `SuccubusDefault_MAS` — the user never saved
  a distinctive skin this session; "Eva" in the Overview is Succubus's default look).
  So "reverts to default" == "default is what's saved" — the skin test was inconclusive,
  NOT a proven failure.
- To validate: seeded a DISTINCTIVE skin `HeroCosmeticsBundle:SuccubusSISTE` into the
  store (via the real client route). `GET /revival/loadout` confirms it. A relaunch with
  auto-inject will replay it → if Succubus shows SISTE, skins work; if default, the skin
  DISPLAY reads a source other than the preference map (next step: RE the customization
  skin-tab / preview read path — likely the party-member cosmetic, session 48/50).

Coexistence + durability shipped:
- `loadout_fix.cpp` now shares the `Local\SuperviveMissionsPIHook` mutex (same as pi8 /
  missions_fix): captures the original PI prologue + installs/uninstalls its one-shot hook
  under the lock, so it never races pi8's SafeWrite. Rebuilt.
- `configs/inject-secondaries.ps1` now injects `loadout_fix.dll` last (after pi8 +
  catalog_pick_fix). So a NORMAL `launch-redirect.ps1` (default mode, elevated)
  auto-applies saved equips every launch — no manual inject.

GOTCHAS surfaced: (1) manual `inject.exe mmap` started returning "OpenProcess: Access is
denied" after a couple of injects — use the elevated launch auto-inject instead of manual.
(2) live testing churn (repeated injects re-firing setters + hero switch to RONIN) cleared
the persisted slots; not a real-use bug (re-equip re-saves). (3) the shim re-firing native
setters also re-PUTs to ags (harmless — re-saves the same values).

NEXT: user relaunches normally → verify (a) the auto-inject runs (docs/loadout-fix-marker.txt
+ inject-secondaries.log), (b) the SISTE skin shows on Succubus and persists. If skin still
default, RE the skin-tab display read path.

## UPDATE 2026-07-08 (part 5) — DEFINITIVE: slots persist, skins don't (display reads elsewhere)

Auto-inject via the launch loop landed a stable run (loadout_fix injected the seeded
distinctive skin `SuccubusSISTE`; probe: `GetHeroCosmeticsBundlePreference(Hero:Succubus)
out='SuccubusSISTE'` — the local preference map DOES hold it). User then verified in-game:
**everything persisted EXCEPT skins.** So conclusively:
- `SetSlotCosmetic` → `SlotCosmeticsEntries` → the customization display READS it → slots
  (glider/wisp/spray) persist. ✓ DONE.
- `SetHeroCosmeticsBundlePreference` → populates `HeroCosmeticsBundlePreferences` (probe-
  confirmed) BUT the skin DISPLAY does NOT read that map → still shows default. ✗
  ⇒ the equipped-skin display reads a DIFFERENT source than the preference map. Matches
  sessions 48/50: the hunter/main-menu preview = `Comp_MainMenu_PartySlotSubject.
  DetermineCosmeticToShow → ResolveCosmeticsBundleForHero`, which uses the PARTY-MEMBER
  cosmetic and falls back to `DefaultCosmeticsBundle` when it's empty — it does NOT consult
  `HeroCosmeticsBundlePreferences`.

NEXT (skin fix) — set the source the display actually reads, in addition to the preference:
  1. Find the `PartyMemberModel` cosmetic field offset (near HeroAssetID@+0x78) and write
     the saved bundle there for the selected hero, OR
  2. Call the native `TryPickMyHeroAndCosmetics(hero, cosmetics)` (session 48/50, impl
     +0x58467E0) which sets BOTH hero + cosmetic on the member, OR
  3. Try `SetCosmeticBundle(const FPrimaryAssetId&)` (a separate native — resolve its owner
     object; may be the active-equip vs the preference).
  Then re-check the customization skin display + the 3D preview. The loadout_fix shim + the
  native-call primitive are the delivery vehicle; only the TARGET for skins needs to change.

Also: 2 D3D12 menu-load crashes (documented intermittent, session-40; crash callstack is
pure d3d12/D3D12Core/nvldumdx — NOT the shims) before a clean run — added a 6-attempt
auto-relaunch loop pattern (docs/relaunch-loop.log) that retries until loadout_fix applies
and the menu survives.

## UPDATE 2026-07-08 (part 6) — TryPick ALSO doesn't fix the skin display

Extended loadout_fix to also call native `TryPickMyHeroAndCosmetics(hero, cosmetics)` on the
PartyManager (resolved live: party=0x…, tryPick thunk found; applied "Succubus + SuccubusSISTE",
NO crash/hang — the hang the user saw was a separate D3D12 menu-load hang on a failed relaunch
attempt, loadout_fix wasn't even injected there). USER RESULT: customization skin STILL does not
persist; everything else (slots) does.

So THREE cosmetic states now ruled out as the skin-tab's source:
  1. HeroCosmeticsBundlePreferences (SetHeroCosmeticsBundlePreference) — probe-confirmed populated, NOT read by skin tab.
  2. Party-member cosmetic (TryPickMyHeroAndCosmetics) — set, NOT reflected in the skin tab.
  (Slots DO persist because the glider/wisp/spray tabs read SlotCosmeticsEntries, which SetSlotCosmetic populates.)

⇒ The customization SKIN tab reads a DIFFERENT "equipped skin" source than both the loadout
preference map and the party pick. Candidates to investigate (bytecode/live RE of the SKIN tab
widget, NOT the shared CosmeticSelector): a per-hero "equipped/active bundle" possibly on the
CatalogManager/CatalogEntry (the store/roster work lives there), or `SetCosmeticBundle(FPrimaryAssetId)`
(a still-untried native — resolve its owner + semantics). NEXT: bpdump the SKIN-tab widget (offline,
reads paks) to find the exact "equipped skin for hero X" read, then set THAT via the shim. The
delivery vehicle (loadout_fix + native-call primitive + /revival/loadout) is done; only the skin
target is unknown. Everything-but-skins is COMPLETE + auto-injecting.

## UPDATE 2026-07-08 (part 7) — backend member-cosmetic REVERTED (it locked skins); final state

Live (computer-use screenshots of the customization page) + user confirm: the backend
member-cosmetic fix (buildSoloParty serving cosmeticsAssetId) DID make the skin persist, but
it LOCKED skin selection — the customization skin tab syncs to the party member, and the ~1s
/party poll re-asserted the saved skin, so clicking a different skin snapped back. User: "Stuck
— can't change it." REVERTED buildSoloParty to NOT serve the member cosmetic (hot-swapped ags;
verified /party no longer returns cosmeticsAssetId). Skins are changeable again but not
persistent (the pre-fix baseline). selectedCosmetic() kept but unused.

NEW insight from the screenshots: distinctive skins DO render in customization (saw
"Strawberry Bomb" equipped on a hunter, glider "Skylands", spray "Diamond"). So the per-hero
equipped-skin DISPLAY works; the unsolved part is where that per-hero "equipped skin" is
STORED/read such that we can persist it without the poll fighting selection. It is NOT:
HeroCosmeticsBundlePreferences (shim populated it, display ignored it), NOT the party-member
CosmeticsAssetID (locks selection). Likely a per-hero equipped-cosmetic on the CatalogManager /
hero runtime object (the store/roster equipped-state lives there). NEXT (future focused effort):
RE the per-hero skin read in WBP_UI_Loadout_StyleScreen's SetEquipped / SetSelectedAsset /
"Change Hunter" path (bpdump those functions), find the per-hero equipped store, set it via the
loadout_fix native-call primitive on menu load (idempotent, no poll fight).

BUILD NOTE: had to fix a concurrent in-progress edit to compile ags — internal/menu/config.go
Apply(): `publish(cp)` → `publish(&cp)` (copyConfig returns Config value; publish takes *Config).
Reconcile with the admin-panel refactor if intended differently.

## FINAL STATE (this session)
- Gliders / wisps / sprays / emotes / titles / chromas: PERSIST, auto-inject on launch (loadout_fix
  in inject-secondaries.ps1). USER-CONFIRMED for glider/wisp/spray. **DONE.**
- Hunter skins: NOT persistent (reverted the locking fix). Changeable in-session. Needs the
  per-hero equipped-skin RE above.
- Infra built + reusable: loadout_fix.cpp (native-call replay of equips), GET /revival/loadout feed,
  extractor `schema` KeyValuePair fix, 6-try D3D12 auto-relaunch loop pattern.

## Still open — needs one in-game pass (client not driven this session)
1. Equip a cosmetic in CUSTOMIZATION, leave + re-enter the page → confirm it
   stays selected (readback path). This is the user-reported repro.
2. Relaunch → confirm it survives (disk persistence via `state/interactive.json`).
3. For `emotes/titles/cosmeticsbundle/luxechromas`, capture a real click in
   `capture.log` to confirm/trim the best-guess request shapes (they no-op if the
   guess is wrong, so no regression meanwhile). `slotcosmetics` is already
   capture-confirmed.

## UPDATE 2026-07-09 — SKIN backend route DEFINITIVELY CLOSED (Loki.log render proof) + member-PUT wire CONFIRMED

Drove the client live (computer-use) to capture the SKIN-tab equip flow, then RE'd
`WBP_UI_Loadout_StyleScreen` bytecode + the live inventory + the game's own render log.
Full mechanism now nailed:

**1. The member-write route is CAPTURE-CONFIRMED (was a best-guess since s48).** A skin
click in CUSTOMIZATION→SKIN fires, within ms:
```
PUT /party/parties/party-<id>/members/<id>
{"iD":"<id>","heroAssetId":"Hero:Alchemist",
 "cosmeticsAssetId":"HeroCosmeticsBundle:AlchemistDefault_MAS","luxeSkinChroma":"",
 "ownedCosmeticsFeatures":[],"isReady":true,"customGameTeamId":0,"isPremiumSession":false}
```
then ~5s later `PUT /personalization/players/<id>/cosmeticsbundle/Hero:<name>`
`{"assetId":"HeroCosmeticsBundle:..."}` (the debounced per-hero preference).

**2. Equip mechanism (StyleScreen ubergraph stmt 154-166):**
`GetCatalogEntry(selectedSkin).CanUse()` [OWNERSHIP GATE — unowned skin => equip skipped]
→ if owned & changed: `Get Current Party Assets` → `TryPick(partyAssets.HeroAssetId, selectedSkin)`
→ `SetEquipped(local CurrentEquipped)` → `Refresh Preview Indicators`.
The TryPick HERO arg = the **party member's** hero (Alchemist auto-pick), NOT the previewed
hunter. "Change Hunter" in customization only changes the PREVIEW, not the party pick
(confirmed: after Change Hunter→Mercury, every member PUT stayed Hero:Alchemist).

**3. Ownership is tiny.** `server/internal/menu/data/skins.txt` = 391 entries; for Alchemist
ONLY `AlchemistDefault`, `AlchemistDefault_MAS` (display "Mastery"), `AlchemistDefault_STR`
(display "Strawberry Bomb") are owned. **Mercury (and most hunters) own ZERO skins** → their
tiles are un-equippable (CanUse=false). So the user's Mercury test was doomed twice over.

**4. THE BACKEND ECHO IS INERT (the headline).** Tried persisting+serving the picked
`cosmeticsAssetId` on the party member (poll echoes the client's own pick, so no s53-part-7
lock). Live test: equipped Mastery → member PUT `AlchemistDefault_MAS` → server stored+echoed
MAS. Yet **Loki.log** (current timestamp) shows the party slot loading:
```
PartySlot_C_0: Skipping SetHero because CosmeticsAssetId ... match (HeroCosmeticsBundle:AlchemistDefault_STR - true)
```
i.e. the client rebuilds the party member from the /party GET each poll, reads **only
heroAssetId**, never the cosmetic → member cosmetic goes empty → `Get Current Party Assets`
falls to its ELSE branch `GetDefaultCosmeticsBundleIdForHeroId(Alchemist)` = `AlchemistDefault_STR`
= "Strawberry Bomb". **That default fallback is the eternal "reverts to Strawberry Bomb".**
Hunters persist because heroAssetId IS read back; skins cannot be driven from the backend.

**REVERTED** the inert change (interactive.go buildSoloParty no longer serves the member
cosmetic; store.go SelectedCosmeticAssetId removed; selectedCosmetic back to the preference
map; tests reverted). Kept only the confirmed-wire-shape documentation in the handler comment.

**THE ONE REMAINING PATH (client-side, well-scoped now):** both the SKIN tab AND the party
slot fall back to the SAME native `GetDefaultCosmeticsBundleIdForHeroId(FPrimaryAssetId Hero)`
when the member cosmetic is empty (which it always is). Redirect THAT per-hero to the saved
skin from a menu-load shim (hook it, or make it return the saved bundle) and BOTH surfaces show
the saved skin persistently — no poll fight (the poll's own fallback becomes the saved skin).
This is a much cleaner target than fighting the member cosmetic. NEXT: resolve
`GetDefaultCosmeticsBundleIdForHeroId` (it's a CallMath/native on the CatalogManager or a
cosmetics library — visible in the StyleScreen ubergraph as StackNode
`GetDefaultCosmeticsBundleIdForHeroId`), find its owner + signature, then hook/redirect it in
loadout_fix.cpp keyed by the /revival/loadout `heroCosmeticsBundles` map. Owning more skins
(expand skins.txt) is orthogonal but needed for non-default/Mercury skins to be equippable at all.

## UPDATE 2026-07-09 (part 2) — target RESOLVED; inline .text detour CRASHED (anti-tamper); pivot to a non-.text hook

Reverse-engineered the redirect target fully and built the redirect, but the inline detour tripped the game's `.text` integrity check.

**Function located (usmapdump RPM on the live game):**
- FName `GetDefaultCosmeticsBundleIdForHeroId` = id `0x00586579` (native `CosmeticsBundleId` function-
  library family; siblings incl. `GetHeroIdForCosmeticsBundleId`).
- ANSI name @ RVA `0x888E9C0`. StaticRegisterNatives exec-thunk table @ RVA `0x9BA7F58` → exec thunk.
- **Exec thunk** = RVA **`0x52B3400`** (reads the FPrimaryAssetId hero param from the FFrame, calls the
  impl, `movups` the 16-byte result into the FFrame Result).
- **Native impl** = RVA **`0x55899C0`**, clean C ABI:
  `FPrimaryAssetId* fn(FPrimaryAssetId* out /*rcx*/, const FPrimaryAssetId* hero /*rdx*/)` — zeroes
  `*out`, validates the hero, delegates to a manager virtual call for the per-hero default, writes 16
  bytes to `*out`, returns `out`. Prologue `40 55 53 57 41 57` (6 stealable bytes). FPrimaryAssetId:
  `[+0]` type FName, `[+8]` name FName.

**Inline detour built + installed (loadout_fix.cpp; preserved as loadout_fix_detour.dll):** 6-byte JMP
on the impl prologue → OnGdcb, which matches the queried hero by name against the saved
/revival/loadout `heroCosmeticsBundles` and memcpy's the saved bundle's precomputed 16-byte PAID into
`*out` (else forwards to the original via a trampoline). Install marker CONFIRMED:
`[5] GDCB skin-redirect INSTALLED (persistent) @impl=0x7FF6BAA799C0` (Alchemist→AlchemistDefault_MAS,
Succubus→SuccubusSISTE).

**RESULT: game CRASHED ~2 min after install** (Sentry/crashpad, NO `[VEH]` from the shim's AV handler).
Clean-crashpad exit + ~2 min timing matches the documented `.text` integrity check (the catalog `jz`
patch "trips the ~3-5min integrity check"). Detour logic looks correct (no VEH AV) ⇒ most likely
anti-tamper caught the modified `.text` bytes. **A persistent inline `.text` patch is not a durable
delivery vehicle here.**

**PIVOT (next) = non-`.text` hook: swap the UFunction.Func pointer (heap write, invisible to a `.text`
checksum).** The UFunction for GetDefaultCosmeticsBundleIdForHeroId has Func @ +0xE0 = the exec thunk
(base+0x52B3400). Scan GUObjectArray for it (verify Func==base+0x52B3400), set Func=&MyThunk (8-byte
ALIGNED atomic write — no thread-suspend). MyThunk calls the original exec thunk (fills Result with the
DEFAULT bundle), then post-processes: read the default bundle name FName → string ("AlchemistDefault_STR"),
prefix-match the hero codename ("Alchemist") against the saved-skin table, overwrite Result with the
saved bundle PAID if matched. Avoids ALL FFrame param parsing AND `.text` patches.
**VERIFY FIRST** (disasm the EX_CallMath VM handler on the live game): does CallMath read the runtime
UFunction.Func @+0xE0 at call time (→ swap works) or use a bytecode-cached native pointer (→ swap
inert)? Session 49's Func-swap was inert but blamed on CommonUI widget POOLING (a different cause);
this fn is called fresh each refresh. If cached, fall back to (a) data-patch the manager's per-hero
default map (find via the impl's delegated virtual call) or (b) locate/defeat the integrity check.
Deployed loadout_fix.dll reverted to the stable pre-detour build for a clean relaunch; detour build =
loadout_fix_detour.dll; source retains the GDCB code.

## UPDATE 2026-07-09 (part 3) — Func-swap redirect WORKS + STABLE, but only fixes the SKIN-tab INDICATOR, NOT the 3D render

**Func-swap SUCCESS (persistence, user-verified):** swapped the UFunction.Func of GetDefaultCosmeticsBundleIdForHeroId
(heap write, no .text patch) → MyGdcbThunk (calls original, prefix-matches the default bundle name to a saved hero, overwrites
Result with the saved bundle PAID). STABLE >2.5min (dodges the .text integrity check that crashed the inline detour). The SKIN
tab equipped-checkmark shows the saved skin (Mastery) instead of the default — computer-use screenshot confirmed. Impl in
loadout_fix.cpp (InstallGdcbFuncSwap + MyGdcbThunk; UFunction found by Func@+0xE0 == base+0x52B3400). CHANGEABILITY added
(bg poller RefreshThread + lazy PAIDFromString re-convert in MyGdcbThunk + backend records member-PUT cosmetic into
HeroCosmeticsBundles immediately) — deployed, but see the caveat below.

**THE GAP (user-reported): the 3D RENDER doesn't follow the skin — only the checkmark does.** Two DISTINCT cosmetic-resolution
paths, confirmed by bpdump:
  1. SKIN-tab equipped INDICATOR (checkmark) <- Get Current Party Assets -> else-branch `GetDefaultCosmeticsBundleIdForHeroId`
     (native) = MY REDIRECT. Fixed.
  2. 3D RENDER (main-menu center hunter + customization pedestal) <- `Comp_MainMenu_PartySlotSubject.DetermineCosmeticToShow`
     -> `BPFL_Cosmetics."Resolve Cosmetics Bundle For Hero"(member.HeroAssetID, member.CosmeticsAssetID)`:
        - if member.CosmeticsAssetID IsValidPrimaryAssetId -> use it (the member cosmetic).
        - else (empty, always) -> GetHeroAssetFromPrimaryAssetId(hero) -> read the hero asset's **`DefaultCosmeticsBundle`**
          property (a per-hero HeroCosmeticsBundle ref = plain "AlchemistDefault"). NOT GetDefaultCosmeticsBundleIdForHeroId.
     Loki.log proof: the party slot renders "HeroCosmeticsBundle:AlchemistDefault" (plain, no _MAS/_STR) and ZERO renders carry
     my redirect's _MAS/_STR suffix => my Func-swap never touches the render. `BPFL_Cosmetics` +
     `Comp_MainMenu_PartySlotSubject` are BLUEPRINTS (Func-swap N/A - their Func is the BP interpreter).

**NEXT - fix the render (both levers are heap/data, non-.text):**
  (A) **PATCH the hero asset's `DefaultCosmeticsBundle` field** to the saved skin (the shared fallback the render reads). Find the
      loaded hero-asset object (BP_HeroAsset_<Hero> / CDO) + the DefaultCosmeticsBundle field offset + type (the DefaultCosmeticsBundle
      FName hits are asset names like BP_Alchemist_DefaultCosmeticsBundle, so the field is likely a HeroCosmeticsBundle soft/hard
      OBJECT ref, not a PAID - writing it needs the right type). Then trigger a re-render (OnCosmeticUpdated / navigate). Unifies
      render + indicator.
  (B) keep member.CosmeticsAssetID VALID (= saved skin) so Resolve uses the member directly - but the ~1s /party poll wipes it and
      the render is event-driven (OnCosmeticUpdated), so a memory-write race can't reliably re-render. (A) is preferred.

**ALSO (changeability chain, this session): the member PUT did NOT fire from SKIN clicks** (capture.log: 0 member/cosmeticsbundle
writes during the test; saved skin stayed _MAS). So "the selection sticks" the user saw was LOCAL click state, not the backend
chain. The member PUT fired in earlier sessions (00:13/00:16) but not post-redirect - INVESTIGATE whether my redirect changed the
equip flow's "CurrentEquipped == CurrentSelectedCosmetic -> skip TryPick" check (SetEquipped now seeds CurrentEquipped=saved skin
on entry, so clicking the saved skin no-ops; clicking a DIFFERENT owned skin should still fire - verify with a live capture +
Loki.log of the equip path). Render fix (A) is higher priority; changeability follows.

## UPDATE 2026-07-09 (part 4) — RENDER FIX partially lands: pedestal renders the saved skin; main-menu + switching still gapped

Implemented the DefaultCosmeticsBundle data-patch (loadout_fix.cpp PatchHeroDefaultBundles).
- **LokiHeroAsset.DefaultCosmeticsBundle offset = 0x68** (StructProperty PrimaryAssetId, 16B). The per-hero assets are the CDOs
  `Default__BP_HeroAsset_<Hero>_C` (class-identity found only the empty base CDO Default__LokiHeroAsset; found the real ones by
  DATA: scan all objects for a "HeroCosmeticsBundle" PAID at 0x68 + require the class name to contain "HeroAsset" so unrelated
  objects like "OverlaySlot" — a false positive in the first pass — are excluded). Overwrite the 16B PAID with the saved bundle.
- **Must run OFF the game thread:** the ~500k-object scan in the PI hook (game thread) STALLED and CRASHED the game. Moved to
  the RefreshThread (background) via a g_gdcbRepatch flag (set by ApplyLoadout + the changeability dirty re-convert). Clean.
- **USER-VERIFIED WIN:** the CUSTOMIZATION PEDESTAL renders the saved skin (Beast Slayer). Markers [5]/[6]/[7] all fire; the
  data-scan matched exactly the 3 hero CDOs (Alchemist->_MAS, Ronin->BeastSlayer, Succubus->SISTE), no false positive.

**GAP 1 — main-menu center hunter stays default:** the party slot (BP_MainMenuSpawner_MainMenu_PartySlot) renders ONCE at menu
load and caches (Loki.log: zero SetHero re-renders on navigation). The patch applies ~15s later, so that slot never re-reads it.
Needs a forced re-render (fire member OnCosmeticUpdated / party-slot Refresh) OR patching before the initial render (shim isn't
ready that early). The party slot only re-renders on a member cosmetic CHANGE — which never happens (member stays empty).

**GAP 2 — switching reverts to the patched skin:** the fallback is now a FIXED per-hero value, so a new pick shows briefly then
reverts after the ~1s member wipe. Re-applying the new pick needs a string->FPrimaryAssetId conversion (PAIDFromString = GAME
THREAD) gated behind MyGdcbThunk being called (unreliable). NOTE: the pick DOES reach the backend (Ronin->Ronin_StreetInferno
is saved in /revival/loadout via the cosmeticsbundle PUT), so half the chain works.

**NEXT (clean unified fix):** (a) an off-thread string->FName via an FNamePool search (reverse of GetFNameStr) so the poller can
re-convert + re-patch DefaultCosmeticsBundle without the game thread — fixes GAP 2's timing; AND (b) a party-slot re-render
trigger for GAP 1. OR the deeper unification: keep the party-member CosmeticsAssetID VALID (the single source every path reads
AND the re-render trigger), which the ~1s /party poll fights — would need to redirect/suppress the poll's member-cosmetic wipe.
Deployed loadout_fix.dll = the render build (Func-swap + poller + off-thread DefaultCosmeticsBundle patch). Intermittent gotchas
this session: one D3D12 menu-load crash + one transient injection hang (loader lock; not the DLL — it injected fine other times).

## UPDATE 2026-07-09 (part 5) — re-render TRIGGER works, but render still resolves to DEFAULT (two deeper blockers)

Wired a re-render trigger: backend /revival/loadout now serves "selectedHero"; the shim calls native
TryPickMyHeroAndCosmetics(selectedHero, savedSkin) after the CDO patch (PI-hook state machine: apply -> off-thread CDO patch
-> TryPick, ordered so the fallback is patched before the poll wipe). Runs on the game thread; STABLE (no crash) — TryPick is
the game's own setter, safe to call from the PI hook. On a CLEAN launch: all 3 CDOs patched (Alchemist->_MAS, Succubus->SISTE,
Ronin->Ronin_StreetInferno), TryPick(RONIN, Ronin_StreetInferno) fired, Func-swap + poller up.

**RESULT: the party slot STILL renders `HeroCosmeticsBundle:RoninDefault` (SK_Ronin_Default) — the DEFAULT, not the saved skin.**
Two compounding blockers, both deeper than the CDO patch:
1. **TryPick is ASYNC + validates.** It doesn't synchronously set the member cosmetic to my value (it queues a validated pick
   with an OnTryPickComplete callback, which I pass empty). The completed set doesn't land, so the member stays default and the
   re-render reads default.
2. **The render reads a DIFFERENT hero-asset object than the patched CDO.** `GetHeroAssetFromPrimaryAssetId(Ronin)` returns an
   object whose DefaultCosmeticsBundle is still "RoninDefault"; my patched `Default__BP_HeroAsset_Ronin_C` CDO (set to
   Ronin_StreetInferno) is NOT what the party slot reads. (The earlier "pedestal shows Beast Slayer" was likely the previewed/
   active cosmetic, not the CDO patch — the CDO patch may be inert for the render.) The data-scan finds only the CDOs (3), so the
   object the render actually reads (a loaded INSTANCE?) isn't being found/patched.

**Honest assessment:** the render fix is a STACK of compounding sub-problems — (a) find the exact hero-asset object
GetHeroAssetFromPrimaryAssetId returns and patch THAT (not the CDO); (b) make TryPick's async pick actually complete (supply a
real OnTryPickComplete delegate, or set the member cosmetic by raw write + fire OnCosmeticUpdated directly); (c) ownership
(TryPick/CanUse may reject non-owned skins → default); (d) render caching (party slot renders once; needs the trigger). Each is
its own RE effort; this is a multi-session problem, not a single fix. Deployed build does all of the above (harmless where inert):
Func-swap (checkmark persists) + poller (changeability plumbing) + off-thread CDO patch + TryPick re-render trigger. Backend adds
selectedHero to /revival/loadout + records member-PUT cosmetic. NEXT: RE `GetHeroAssetFromPrimaryAssetId` to find the true render
object; OR abandon the fallback-patch route and make the party-member cosmetic itself stick (raw write + a real re-render fire),
which unifies all surfaces but needs the member offsets + a delegate-fire primitive.

## UPDATE 2026-07-10 (part 6) — ★★★ MAIN-MENU 3D RENDER SOLVED (Loki-confirmed + user-visual-confirmed) ★★★

Part 5's two "compounding blockers" were re-tested and one was WRONG; the real fix was a missing re-render.

**Diagnostic 1 — the CDO *is* the right object (part 5's "different object" theory FALSIFIED).** `GetHeroAssetFromPrimaryAssetId`
is NATIVE (its ANSI name is in the exe .rdata, sibling of `GetPrimaryAssetIdFromHeroAsset`/`GetMissionPoolFromPrimaryAssetId` —
the LokiAssetManager family). Added a call of it via the primitive (loadout_fix `CallGetHeroAsset`/`PatchRenderHeroAssets`): it
RESOLVED (thunk RVA 0x52AA550) but **returns NULL** for every hero when called from the PI hook (asset-not-loaded-from-that-path /
context — moot). Crucially, the data-scan finds **exactly 4** objects with a `HeroCosmeticsBundle:<Codename>Default*` PAID at
+0x68 AND a "HeroAsset" class name — the 4 CDOs `Default__BP_HeroAsset_<Hero>_C`. **There is no hidden loaded instance.** So the
render DOES read the CDO; patching it is correct.

**Diagnostic 2 — the real blocker was GAP 1 (re-render), not the object.** Loki.log proof: the main-menu party slot
(`BP_MainMenuSpawner_MainMenu_PartySlot_C_0`) renders `SetHero ... RocketJumperDefault` ONCE at menu load (frame ~155), ~22s
BEFORE loadout_fix applies, then CACHES and never re-renders — the ~1s poll does NOT re-run `DetermineCosmeticToShow`. TryPick
did **not** trigger a re-render (zero post-patch `SetHero`). So the CDO patch lands but the cached slot never re-reads it.

**THE FIX — fire `Comp_MainMenu_PartySlotSubject.Refresh()` after the CDO patch.** Reused pi8's Option-B BP-call primitive
(`InvokeBP`: build an FFrame from the captured template with Node=UFunc, Object=this, Code=UFunc.Script.Data@+0x68, Locals=buf,
call the ORIGINAL ProcessInternal via the trampoline). loadout_fix now: (1) resolves the `Comp_MainMenu_PartySlotSubject_C` class
+ its live instances (named `Comp_MainMenu_PartySubject`) + the `Refresh` UFunction (name "Refresh", Outer==subjClass); (2) after
the off-thread CDO patch (`g_cdoDone`), the OnPI state machine fires `RefreshSubjects()` ~5× over ~1s (tick-gated). Refresh
re-runs `DetermineCosmeticToShow` → reads the patched fallback CDO → **fresh `SetHero`**. TryPick REMOVED (ineffective + risked
setting the member cosmetic to a default, which would take the `if valid` branch and render the wrong thing).

**RESULT — VERIFIED (2026-07-10):**
- Loki.log: after Refresh fires, `PartySlot_C_0: SetHero is setting target cosmetic HeroCosmeticsBundle:RocketJumperKnockOut`
  (the saved skin) and the ONLY skeletal mesh loaded is `SK_RocketJumper_KnockOut` (×2–4), **`SK_RocketJumper_Default` = 0 loads**.
- USER SCREENSHOT: the main-menu center hunter (RocketJumper, selectedHero) visibly wears the **KnockOut** skin (KO bomb-glove,
  KO shirt logo, red boosters). ✅ **DoD item #1 (main-menu center) DONE.**
- Stable, no crash/VEH; reproduced across two clean relaunches. Heap-only writes (CDO field + UFunction.Func) → no .text
  integrity trip.

**pi8 coexistence + multi-hunter/nav for free:** pi8 (already injected) fires the SAME `Refresh` on HERO switches + on leaving the
HUNTERS page, and its Refresh reads the same patched CDO — so switching hunters on the main menu, and returning from HUNTERS,
re-render each hero's saved skin automatically. loadout_fix's Refresh is a one-shot under the shared `Local\SuperviveMissionsPIHook`
mutex (install→apply→CDO-patch→refresh→uninstall), so it never clobbers pi8.

**Long-session artifact NOTE:** after ~23h idle uptime the game trimmed its working set (5.5GB→0.77GB) and the CUSTOMIZATION→SKIN
tab went empty ("MISSING STRING TABLE ENTRY" / "ITEM NAME" placeholders / empty pedestal) — a catalog/asset-UNLOAD artifact of
the marathon session (catalog_store_fix domain), NOT the render fix (the main-menu center still rendered KnockOut from its cached
mesh). A clean relaunch restores it. Always test on a fresh launch.

**REMAINING to reach "perfect":** (a) confirm the SKIN-tab pedestal/preview + equipped checkmark on a FRESH instance (part-4 had
the pedestal working; re-verify post-Refresh); (b) live changeability of the main-menu center on a same-hero skin CHANGE without
nav (pi8 covers hero-switch/HUNTERS-nav, but not an in-place skin swap) — add a RefreshThread re-arm of the one-shot Refresh when
the CDO is re-patched; (c) multi-hunter visual pass (Ronin→BeastSlayer, Succubus→SISTE, Alchemist→_MAS). New shim code:
`CallGetHeroAsset`/`PatchRenderHeroAssets` (diagnostic, currently NULL/no-op), `InvokeBP`/`ResolveSubjects`/`RefreshSubjects`,
OnPI Refresh state machine. Markers: `[2b] subjects/refreshFn`, `[renderR] Refresh fired`, `[4] ... Refresh call(s)`.

## UPDATE 2026-07-10 (part 7) — CHANGEABILITY: the CDO patch FIGHTS new picks -> pivot to the member-cosmetic write (lever #B)

**User test of the part-6 build revealed the changeability gap.** All FOUR render surfaces show the saved skin
on load (user screenshots: RocketJumper KnockOut on the main-menu center, the customization pedestal, the SKIN-tab
preview, and the equipped checkmark — every surface ✅). BUT clicking a *different* variant (Maverick) showed it
briefly then **snapped back** to the hard-set skin on the next nav/refresh, and other hunters stayed default. Root
cause: the CDO patch is a FIXED value — `DetermineCosmeticToShow` falls back to it every time the ~1s poll wipes the
member cosmetic, so it OVERRIDES the new pick. The user's own workaround (hover other cosmetics to force preview
refreshes) eventually loaded the right skin, confirming the render is refresh-gated + the shim's forced value fights.

**capture.log proved the data flow:** a skin click fires `PUT /party/.../members/<id>` with the new
`cosmeticsAssetId` in MILLISECONDS (handleSetPartyMember records it into HeroCosmeticsBundles immediately), then a
debounced `PUT /personalization/.../cosmeticsbundle/Hero:<h>` ~5s later. So the live selection is available fast.

**THE FIX (lever #B) — keep `member.CosmeticsAssetID` = the selection.** The render checks the member cosmetic
FIRST (the `if IsValidPrimaryAssetId` branch) BEFORE the CDO fallback. So if the member always holds the saved/
selected skin, every surface follows it — no CDO fight. New shim `MemberWriterThread` (120ms): reads the current
hero from `member.HeroAssetID@0x78`, finds its saved bundle, and BACKFILLS `member.CosmeticsAssetID` ONLY when the
field isn't a valid HeroCosmeticsBundle PAID (i.e. empty/None after the poll wipe). While the client holds a live
pick (non-empty) we leave it, so new picks show; after the poll wipes it we restore the latest saved skin.

**member.CosmeticsAssetID offset RE'd from LIVE REFLECTION (usmap-independent):** loadout_fix resolves the
`PartyMemberModel` instance (like pi8) + walks its class ChildProperties (`FindPropOffset`) + dumps the full layout
to the marker. RESULT (`[member]` lines): **CosmeticsAssetID @ 0x98** (FPrimaryAssetId 16B), HeroAssetID @ 0x78,
**OnCosmeticsAssetIDChanged @ 0xA8** (the delegate — a clean future re-render trigger), PersonalizationLoadout @
0x190. Writer wired ON (`[9]` marker). Keeps the CDO patch + Func-swap as belt-and-suspenders backup.

**VERIFIED (log-level):** on relaunch, `member.CosmeticsAssetID` holds `RocketJumperSpeedDemon` (the user's last
pick from the prior session — persisted across relaunch), the party slot renders SpeedDemon consistently
(`Entering SetHero ... (RocketJumperSpeedDemon - true)` / `Skipping ... match`), no default reversion, no VEH/crash,
game stable. Also added a re-arm (`ReArmRefresh` in `RefreshThread`, gated on `g_centerDirty`) that re-fires the
main-menu Refresh when a skin changes + the subjects are live. Markers: `[member]` prop dump, `[2b] member/cosmeticOff`,
`[9] writer ON`. PENDING user visual: does a NEW pick now STICK (not snap back), and does Change-Hunter→Ronin render
Beast Slayer. NOTE: the ~1s poll fires OnCosmeticsAssetIDChanged on wipe; the 120ms backfill wins the race in the log
(no empty SetHero), but if a visible flicker appears, tighten the writer interval or suppress the poll wipe via the
+0xA8 delegate. Two intermittent D3D12 menu-load crashes this session (documented, pure d3d12 — just relaunch).

## UPDATE 2026-07-10 (part 8) — member write was fixed-value (still fought picks) + cross-hero bug -> CACHE-AND-RESTORE

**User test of the part-7 (fixed-value backfill) build found 2 problems:** (2) a skin CHANGE still didn't lock in
(the SKIN tab showed it selected but OVERVIEW reverted) — because the writer backfilled the LOAD-TIME saved skin
(g_gdcbBundle), which lags the new pick, so it still fought changes (same flaw as the CDO, just relocated); and (3)
a NEW BUG — selecting a DIFFERENT hunter (Brall, no saved skin) rendered the RocketJumper MODEL in the preview. Root
cause: a HeroCosmeticsBundle PAID encodes BOTH hero + skin, and my writer left a stale RocketJumper bundle on the
member when the member hero switched to Brall (Brall has no saved skin -> writer did nothing -> stale value lingered
-> the preview resolved RocketJumperSpeedDemon -> RocketJumper model).

**FIX = CACHE-AND-RESTORE (loadout_fix MemberWriterThread rewrite).** Instead of writing a fixed value, we track the
client's ACTUAL live pick: every 100ms read member.CosmeticsAssetID@0x98 —
  * if it's a valid HeroCosmeticsBundle whose name PREFIX-matches the current member hero (HeroAssetID name @0x80),
    CACHE those exact 16 bytes per-hero (g_mc[]) — the client's real pick, no conversion, no lag;
  * if it's a bundle that does NOT match the current hero (stale cross-hero), CLEAR it (write empty) so a previewed
    hunter shows ITS OWN default, never another's skin (fixes the Brall bug);
  * if it's empty (the ~1s poll wiped it), RESTORE this hero's cached pick so the render follows the selection.
Seeded from /revival/loadout on load (`SeedMemberCache` from g_gdcbCode+g_gdcbBundle) so the saved skin shows on
load. This makes changeability track the client's own pick (sticks) and is hero-consistent by construction.

**VERIFIED (log-level, 2026-07-10):** `[9b] member cache seeded with 5 hero(es)`, writer ON, game stable, main-menu
center renders the saved skin (RocketJumperKnockOut). PENDING user interactive re-test: (a) selecting Brall now shows
Brall (not RocketJumper), (b) a RocketJumper skin change now STICKS. New shim: `struct McCache`/`g_mc`/`McFind`/
`SeedMemberCache`, MemberWriterThread cache-restore. Markers `[9]/[9b]`. NOTE: the OVERVIEW summary THUMBNAIL (a 2D
tile, not a render surface) reads the game's own equipped-skin state and may still differ — separate from the 3D
render DoD. Kept CDO patch + Func-swap + Refresh + ReArm as backups; the member cache is now the primary lever.

## UPDATE 2026-07-10 (part 9) — CHANGEABILITY is gated by client OWNERSHIP (not the render shim); member writer DISABLED

**User test of the cache-restore build surfaced the real changeability blocker.** (1) A within-hunter skin change
still didn't stick, and (2) all hunters showed LOCKED. Traced end-to-end:
- The RENDER + MULTI-HUNTER is SOLVED: Loki.log loaded `SK_Ronin_BeastSlayer`, `SK_RocketJumper_KnockOut`,
  `SK_Succubus_SISTE` and rendered each on hunter-switch. NOT the problem.
- capture.log: a RONIN skin change PREVIEWED (mesh loaded) but the member PUT fired ONLY for BeastSlayer —
  StreetInferno/Default NEVER committed (no member PUT, no cosmeticsbundle PUT). ⇒ the equip was SKIPPED by the
  OWNERSHIP gate (`GetCatalogEntry(skin).CanUse()==false`). A pick that can't commit can't stick — and the same
  CanUse=false is why hunters show locked. **Both symptoms are one root cause: client-side CanUse/ownership.**
- **The BACKEND is CORRECT**: `GET /inventory/players/{id}` serves **977 AssetEntries ALL IsOwned=true** (incl.
  `Ronin_StreetInferno`) + **25 Hero: entries all IsOwned=true**. So ownership is granted; the client CatalogManager
  just isn't deriving CanUse from it this session. This is the catalog_store_fix / roster domain
  (docs/hero-roster-attempts.md), a SEPARATE (previously-solved) system — NOT the loadout_fix render work.
- **Environmental flakiness this session:** ~5 D3D12 menu-load crashes + an injection RACE — on a fast startup the
  detached inject-secondaries fired ~4s post-launch into a process without ntdll loaded, so
  `catalog_pick_fix.dll` FAILED (`resolve RtlAddFunctionTable: ntdll.dll not loaded in target`). catalog_pick_fix
  is the shim that makes owned clicks COMMIT — its failure directly breaks equip. The many rapid crash-relaunches
  degraded the catalog activation. (Infra fix worth doing: inject-secondaries should wait for ntdll / a minimum
  process age before injecting.)

**DECISION — reverted the deployed shim to the PROVEN-GOOD render-only build (member writer DISABLED by default,
`#define MEMBER_WRITER_ENABLED 0`).** The hunter-lock first appeared with the part-8 cache-restore build; not proven
to be the aggressive 100ms member writer/clear vs. the catalog flakiness, but un-isolatable tonight (D3D12 crashes),
so default OFF to guarantee the known-good state: Refresh + CDO + Func-swap = saved skin renders on ALL surfaces +
multi-hunter + persist + hunters NOT locked. Backup `loadout_fix_renderonly.dll`. The cache-restore code + the RE'd
offsets (member.CosmeticsAssetID@0x98, HeroAssetID@0x78, OnCosmeticsAssetIDChanged@0x98… @0xA8) are preserved for
re-test.

**NEXT SESSION (to finish changeability, on a STABLE launch — Steam up, ONE clean launch, no rapid relaunch):**
1. First confirm hunters UNLOCK on a clean launch (catalog ownership applies) — if not, it's a catalog_store_fix/
   roster regression to chase in that domain, and changeability is blocked until it's fixed (unowned skins can't
   commit). Verify hunters unlock BEFORE loadout_fix applies (~20s) vs after, to isolate whether the member writer
   is implicated.
2. With ownership working, re-enable MEMBER_WRITER_ENABLED=1 and test: a new pick should commit (member PUT fires)
   → the client sets member.CosmeticsAssetID → the cache-restore observes+caches it → sticks. If the member writer
   locks hunters, use OnCosmeticsAssetIDChanged@0xA8 to suppress only the poll wipe instead of a 100ms poller.
3. Fix the inject-secondaries ntdll race (min process-age / ntdll-loaded check) so catalog_pick_fix stops failing.

## UPDATE 2026-07-10 (part 10) — MEMBER-WRITER was the hunter-lock; CHANGEABILITY works after a CDO-repatch matcher fix

Two decisive findings on a CLEAN launch (render-only build, member writer OFF):

**1. The member writer WAS the hunter-lock (isolation confirmed).** With `MEMBER_WRITER_ENABLED 0`, the user's
screenshot shows the ALL HUNTERS grid FULLY UNLOCKED + Brall renders as Brall (no cross-hero). So the aggressive
100ms member writer/clear was what locked the roster (mechanism unclear — likely the constant clear/write churned the
catalog/party eval). **Do NOT re-enable the raw member writer.** The render works fine without it (CDO + Func-swap +
Refresh). Ownership/commit also work on a clean launch (catalog_pick_fix injected OK; skin picks COMMIT — member PUT
fires; /revival/loadout updates).

**2. Live changeability was broken by a CDO-repatch matcher bug — FIXED.** After a live skin change the backend
committed (RONIN→RoninONI) and `[8]`/`[8b]` fired, but the main-menu center did NOT re-render. Root cause:
`PatchHeroDefaultBundles` matched a hero CDO by the FIELD VALUE prefix (`<Codename>Default*`), but after the first
patch the field is already a skin (`RoninBeastSlayer`), so the repatch couldn't FIND the CDO to UPDATE it to the new
pick. FIX: match by the hero-asset's STABLE OBJECT NAME (`Default__BP_HeroAsset_<Codename>_C` contains the codename,
via new `StrIContains`) instead of the mutable value. Now the CDO updates on every change → the ReArmRefresh
re-render shows the new skin.

**RESULT — USER-VERIFIED (2026-07-10):** load render shows the saved skin (`SK_Ronin_ONI` loaded, SetHero RoninONI);
a live skin change (ONI→BeastSlayer) now UPDATES the **main-menu center** (SetHero follows) AND the **SKIN-tab
preview** (instant), STICKS + persists, hunters stay unlocked. ONE minor gap remains: the CUSTOMIZATION **OVERVIEW
pedestal** is a SEPARATE preview actor from the main-menu `Comp_MainMenu_PartySlotSubject` subjects, so it doesn't
re-render the instant you pick — it updates on ANY interaction (nav to main-menu+back, or hover-cosmetic-then-back)
which makes it re-read the now-updated CDO. To make it instant: find the customization/OVERVIEW preview subject +
fire its Refresh from RefreshThread on a skin change (same InvokeBP mechanism, different actor). Deployed shim =
render-only + CDO-repatch-by-object-name (`loadout_fix.dll`; backup `loadout_fix_renderonly.dll` is the pre-matcher-
fix version). New: `StrIContains`; PatchHeroDefaultBundles matches by object name.

## UPDATE 2026-07-10 (part 11) — OVERVIEW-pedestal instant-refresh: actor found, but its mesh-reload path resists

Chased the one remaining nicety (the CUSTOMIZATION OVERVIEW pedestal not re-rendering the INSTANT you pick — it
updates on nav/hover). Added a diagnostic (`DumpSubjectClasses`) that logs every `*Subject/*Preview/*Loadout/*Style`
class + its refresh-like function names as the user navigates. Identified the customization screen actor:
**`WBP_UI_Loadout_CustomizationScreen_C`** with **`PreviewCurrentSkin`** (+ `PreviewAsset`,
`SelectTabFromContentPreviewType`); the SKIN tab is `WBP_UI_Loadout_StyleScreen_C` (`Show Preview`,
`Refresh Preview Indicators`, `Clear Previewed Cosmetics`); the 2D tiles are `WBP_UI_Asset_Preview_*_C`
(`RefreshVisuals`); the 3D preview base is `BP_LokiHeroSelectPreview_C` + `BPFL_MainMenu_ContentPreview_C`
(`Content Preview Set Scene Tag`).

Wired `PreviewCurrentSkin()` to fire on a skin change (loadout_fix `ResolveCustomization`/`RefreshCustomization`;
ReArmRefresh now fires when EITHER the main-menu subjects OR the customization screen is live; OnPI calls both
RefreshSubjects + RefreshCustomization). LIVE RESULT: `[custR] PreviewCurrentSkin fired on 2 customization
screen(s)` (5×) + CDO repatched to the new skin + main-menu center updates — but the **OVERVIEW pedestal still
shows the OLD skin**. So `PreviewCurrentSkin` runs but does NOT reload the pedestal mesh: it reads a "current skin"
source that isn't the new pick, whereas the working hover ("hover another customization slot, then back to the
skin") drives a per-SLOT hover-preview that reads the tile's value + forces a mesh reload. The pedestal appears to
RESET to the customization-entry skin on tab switch and only mesh-reloads via that per-slot preview path.

**STATE:** everything else is user-verified PERFECT (all render surfaces show the saved skin; a skin change updates
the main-menu center + SKIN-tab preview instantly + sticks + persists; hunters unlocked; multi-hunter; cross-hero
fixed). The OVERVIEW pedestal updates on ANY interaction (nav / hover-then-back), just not the instant of the pick.
**NEXT for a focused session (diminishing returns tonight):** RE the per-slot hover-preview the OVERVIEW uses —
likely `WBP_UI_LoadoutOverviewButton_C` OnHovered -> `WBP_UI_Loadout_CustomizationScreen_C.PreviewAsset(<assetId>)`
(pass the skin bundle PAID) OR a "clear-then-preview" sequence (`WBP_UI_Loadout_StyleScreen_C.Clear Previewed
Cosmetics` then `Show Preview`), OR fire the ContentPreview scene-tag rebuild. `PreviewCurrentSkin` alone is
insufficient. Diagnostic `DumpSubjectClasses` retired from the RefreshThread loop but kept in source.

## UPDATE 2026-07-10 (part 12) — OVERVIEW-pedestal instant-refresh SOLVED via PreviewAsset + latency/stability tuning

Finished the last nicety (the CUSTOMIZATION OVERVIEW pedestal not re-rendering on a skin change). User-accepted final
state: single switches snappy (<1s) + correct; the OVERVIEW pedestal updates on its own; rapid clicking is stable
(catches up to the final pick); everything from parts 6–10 intact (all render surfaces, persist, multi-hunter,
hunters unlocked).

**THE MECHANISM.** `PreviewCurrentSkin()` fired but read `GetCurrentHeroAssets.CurrentCosmeticAsset` (empty) → no
mesh reload. The working per-slot hover-preview is **`WBP_UI_Loadout_CustomizationScreen_C.PreviewAsset(FPrimaryAssetId
Asset @0x0, bool 2D @0x10)`** — param shape RE'd via a one-time `[param]` dump (walk the UFunction ChildProperties:
FField.Name@+0x20, Offset_Internal@+0x44, Flags@+0x38 [CPF_Parm=0x80], FFieldClass@+0x8→Name@0 = type). loadout_fix
now calls it with the skin bundle PAID explicitly + `2D=false` via a new **`InvokeBPLocals`** (same Option-B
ProcessInternal-trampoline BP call, but with a caller-provided Locals buffer holding the input params). `RefreshCustomization`
converts the current /revival/loadout skin fresh (PAIDFromString, game thread), fast-repatches the CDO, then fires
PreviewAsset on each live `WBP_UI_Loadout_CustomizationScreen_C` instance.

**LATENCY (was 3-12s → <1s).** Per-phase timing (`[8b] latency=…[resolve/lockwait/install/refreshwait]`) exposed
two bottlenecks, both eliminated: (1) the object-array **re-scans ran every refresh** (2-4s) → gated on staleness
(`CustStale`/`SubjStale` — skip the scan while the user stays in customization; also skip the main-menu subject scan
while in customization); (2) a **redundant full-scan CDO repatch** (`PatchHeroDefaultBundles` via g_gdcbRepatch, 2-4s)
ran between detect and refresh → removed (the instant `FastRepatchCDO` — a cached per-hero CDO-field write with a
strict object-name guard — handles it). Also: OnPI fires RefreshCustomization BEFORE RefreshSubjects (so the main-menu
Refresh reads the just-repatched CDO), poll 300ms, refresh tick 60ms, wait cap 1.5s.

**STABILITY.** Three real regressions surfaced + fixed: (a) firing BP calls into a surface mid-rebuild during
navigation raced the hunter-pick ("ISSUE SELECTING HUNTER") → **only refresh a LIVE+SETTLED surface** (RefreshCustomization
only when a customization screen is open; RefreshSubjects only when `!SubjStale()`). (b) PreviewAsset previewing an
intermediate skin during rapid switching overrode the newest pick ("reverts to previous") → **250ms debounce** (only
refresh once the selection settles). (c) **rapid re-arming of the ProcessInternal hook crashed the game** (thread-
suspending install/uninstall churn) → **1200ms cooldown** on ReArmRefresh (rapid clicking just catches up to the final
pick once/1.2s instead of churning the hook). A nav-skip attempt to kill the last occasional double-refresh caused a
single-switch revert regression + a 4s nav delay → REVERTED (the occasional double-refresh on OVERVIEW-nav is accepted).

**NEW shim code (loadout_fix.cpp):** `InvokeBPLocals`, `ResolveCustomization`/`RefreshCustomization` (PreviewAsset),
`CustStale`, `FastRepatchCDO` + `g_cdoCache`, OnPI live-surface gating, RefreshThread debounce+cooldown, `[8b]`
per-phase timing + `[param]`/`[custR]` diagnostics. Offsets/names: `WBP_UI_Loadout_CustomizationScreen_C.PreviewAsset`
(Asset FPrimaryAssetId @locals+0x0, 2D bool @locals+0x10), `PreviewCurrentSkin` (parameterless, reads
GetCurrentHeroAssets — insufficient). Deployed `loadout_fix.dll` = this build. **KNOWN small residuals (accepted):**
occasional slight delay switching from the previous skin; occasional double-refresh on OVERVIEW-nav; the very first
skin change per session pays a one-time ~5s class-find scan (then cached). D3D12 menu-load crashes + occasional
catalog_store_fix `catMgr=0x0` / catalog_pick_fix ntdll-race remain environmental launch flakiness (just relaunch).
