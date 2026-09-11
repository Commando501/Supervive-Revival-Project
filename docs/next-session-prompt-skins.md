# Continue: SUPERVIVE customization persistence — HUNTER SKINS (fresh-session pickup)

Paste this into a fresh Claude session in `G:\git\Supervive Revival Project` (branch
`dedicated-server-stub`). Everything below is distilled; the authoritative detail is
**`docs/session-53-customization-persistence.md`** (read parts 1–7) and memory
**`supervive-customization-persistence`**.

---

## TL;DR — what's DONE and what's LEFT

**DONE (working + auto-injecting every launch):** persistence for GLIDER, WISP, SPRAY,
EMOTES, TITLES, CHROMAS. User-confirmed for glider/wisp/spray. Mechanism: a client-side
native shim (`tools/sigbypass-mod/loadout_fix.cpp`) replays the saved equips on menu load by
calling the game's own native setters via the s55 game-thread native-call primitive; it reads
the saved equips from a new ags feed `GET /revival/loadout`. Wired into
`configs/inject-secondaries.ps1` (injected last, shares the `Local\SuperviveMissionsPIHook`
mutex with pi8).

**LEFT: HUNTER SKINS do not persist.** Four approaches tried, all dead:
1. HTTP loadout readback (`GET /personalization/players/{id}`) — client receives it but does
   NOT parse it into the loadout (no error; even the clean glider array field stayed empty).
2. Shim `SetHeroCosmeticsBundlePreference(hero,bundle)` — probe-proven to populate the local
   `HeroCosmeticsBundlePreferences` map, but the SKIN tab does NOT read that map.
3. Backend `buildSoloParty` serving the party member `cosmeticsAssetId` — DID persist the skin
   BUT **locked selection** (the ~1s `/party` poll re-asserts it; the tab syncs to the member;
   clicking a new skin snaps back). **REVERTED** (see interactive.go buildSoloParty note).
4. Native `TryPickMyHeroAndCosmetics(hero,cosmetics)` — clobbered by the same poll.

Current skin state = pre-session baseline: **changeable in-session, NOT persistent.** Do not
re-serve the member cosmetic in `/party` — it locks skins.

---

## THE KEY LEAD (start here)

Skins DO render fine (computer-use screenshots showed "Strawberry Bomb" hunter skin + "Skylands"
glider + "Diamond" spray all equipped/displaying). So the per-hero equipped-skin DISPLAY works —
the missing piece is the per-hero **equipped-skin STORE** that the customization SKIN tab reads,
which is NEITHER of the two things we set:
- NOT `HeroCosmeticsBundlePreferences` (shim populated it; tab ignored it)
- NOT the party-member `CosmeticsAssetID` (setting it locks selection)

The SKIN tab is `WBP_UI_Loadout_StyleScreen` (skins = "styles"; the SLOT tabs that WORK are
`WBP_UI_Loadout_Customization_SlotCosmetic_Generic`). Its functions (from `bpdump ... "*"`):
`Get Current Party Assets`, `SetEquipped`, `SetSelected`, `SetSelectedAsset`, `TryPick`,
`OnPartyUpdated`, `Refresh Preview Indicators`, `GetBaseBundle`, `Is Cosmetics Selection Equal`,
`IsCosmeticsSelectionValid`, `Change Hunter` (button).

**NEXT STEP:** bpdump the per-hero equipped read/write path to find the real store:
```
cd tools/extractor/extractor
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- bpdump "Loadout/WBP_UI_Loadout_StyleScreen.uasset" "SetEquipped"
#   also: "SetSelectedAsset", "Refresh Preview Indicators", and the "Change Hunter" BndEvt.
# and the SLOT tab that WORKS, to compare its equipped read:
& "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release -- bpdump "SlotCosmetic_Generic" "*"
```
Hypothesis: the per-hero equipped cosmetic lives on the **CatalogManager / hero runtime object**
(same territory as the store/roster equipped-state — see `supervive-store-status`,
`supervive-hero-roster-blocker`). Confirm by RE, then SET it idempotently from `loadout_fix` on
menu load via the native-call primitive (idempotent = no fight with the user's live selection,
unlike the poll). If it's a native setter, call it exactly like the slot setters already do.

---

## HOW TO RUN / TEST (elevated PowerShell; the harness token is already elevated when the user says so)

- **Launch (auto-injects the shims incl. loadout_fix):** `.\configs\launch-redirect.ps1`
  (self-elevates; Steam MUST be running first or login dies Auth 14005). It rebuilds ags,
  regen certs, sets hosts, launches game, and `inject-secondaries.ps1` injects
  pi8 + catalog_pick_fix + loadout_fix once the primary settles.
- **D3D12 menu-load crash/hang is INTERMITTENT** (session-40; callstack is pure d3d12/nvldumdx,
  NOT the shims). Use the auto-relaunch loop pattern (a PS `for` loop that kills stale
  ags/go/game, launches, waits for `docs/loadout-fix-marker.txt` to hit `[4]` or the game to
  exit, retries up to ~6x; logs to `docs/relaunch-loop.log`). Full loop body is in the session
  doc / this conversation.
- **Server-only hot-swap (game already up):** rebuild `server\ags.exe`, kill `ags`, restart with
  `-http :8080 -https :443 -log docs\capture.log -certs certs` and `-WorkingDirectory server`.
  Certs are REUSED if `certs\{root,server}.crt`+`server.key` exist, so no cacert re-append needed.
- **loadout_fix build:** `clang++ -shared -O2 loadout_fix.cpp -o loadout_fix.dll -lkernel32 -lwininet`
  (in tools/sigbypass-mod). Marker: `docs/loadout-fix-marker.txt`.
- **Verify the feed:** `curl -s http://127.0.0.1:8080/revival/loadout`
- **Verify /party does NOT serve a cosmetic** (must stay reverted):
  `curl -s http://127.0.0.1:8080/party/parties/party-<playerId>` → member has NO `cosmeticsAssetId`.

## GOTCHAS (cost real time this session — don't repeat)
- **NEVER edit `server/state/interactive.json` with PowerShell `Out-File`/`ConvertTo-Json`** — it
  writes a UTF-8 BOM and Go's `json.Unmarshal` then silently drops the whole file (state lost).
  Seed via the ags HTTP routes instead, e.g.
  `curl -X PUT http://127.0.0.1:8080/personalization/players/<id>/cosmeticsbundle/Hero:Succubus -d '{"assetId":"HeroCosmeticsBundle:SuccubusSISTE"}'`.
- Manual `inject.exe mmap` starts returning **OpenProcess Access-denied** after a couple of
  injects — rely on the elevated launch auto-inject, or ensure the shell is elevated.
- The client **auto-picks a default hero** (Alchemist) on load and equips its default skin, so the
  active hero ≠ any hero you seeded; test the skin on whatever hero is active, or Change Hunter.
- `Default_STR` / `Default_MAS` are DEFAULT skin variants (look identical to default) — always test
  with an obviously DISTINCTIVE skin (e.g. Strawberry Bomb, Succubus SISTE) or you can't tell.

## RE primitives already built (reuse, don't rebuild)
- **Game-thread native-call primitive** (s55/s59): hook ProcessInternal @base+0x13454A0, capture a
  live FFrame, call the native UFunction thunk @UFunction+0xE0. Full impl copied into
  `tools/sigbypass-mod/loadout_fix.cpp` (`Call`, `ResolveFn`, `ResolveFnChain`, `FindClass`,
  `PAIDFromString`, `ParamOffsets`, `CallSet2PAID`) and `missions_nativecall_probe18.cpp`.
- `PrimaryAssetIDFromString(str)` returns a full FPrimaryAssetId in the result buffer AND yields any
  FName: `PrimaryAssetIDFromString("Slot:Glider").name` == FName("Glider").
- Live-schema dump (independent of usmap): `tools/usmapdump/usmapdump.exe extract <exe>` writes
  `schema.txt`; the extractor `bpdump <asset-substr> <fn|*|@props>` disassembles widget Kismet.
- Offsets: GUObjectArray @base+0x9E38930, FNamePool @base+0x9D81450, GGameThreadId @base+0x9D49158,
  UObject Class@+0x18/Name@+0x20/Outer@+0x28, UFunction Func@+0xE0/ChildProps@+0x58, UStruct
  Children@+0x50/Super@+0x40.

## Files touched this session (skin work)
- `server/internal/interactive/loadout.go` (equip routes + `GET /revival/loadout` feed + `loadoutResponse`)
- `server/internal/interactive/store.go` (loadout fields + `primaryLoadout`)
- `server/internal/interactive/interactive.go` (`selectedCosmetic` kept-unused; buildSoloParty cosmetic REVERTED)
- `tools/sigbypass-mod/loadout_fix.cpp` (the shim) + `configs/inject-secondaries.ps1` (auto-inject)
- `tools/extractor/extractor/Program.cs` (schema printer KeyValuePair unwrap fix)
- `server/internal/menu/config.go` (unrelated: fixed `publish(cp)`→`publish(&cp)` to compile ags —
  reconcile with the admin-panel refactor if intended otherwise)
