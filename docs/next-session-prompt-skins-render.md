# Continue: SUPERVIVE hunter-skin persistence — MAKE THE 3D RENDER PERFECT (fresh-session pickup)

Paste this into a fresh Claude session in `G:\git\Supervive Revival Project` (branch
`dedicated-server-stub`).

## ⚠️ MISSION — DO NOT STOP UNTIL IT IS PERFECT

We are continuing this until **hunter skins work PERFECTLY in ALL aspects**, with no
remaining gaps. "Perfect" means, for EVERY hunter and EVERY owned skin:

1. **Persistence** — the saved skin survives navigation and relaunch.
2. **3D render everywhere** — the actual hunter model wears the saved skin on the
   **main-menu center**, the **customization pedestal**, the **SKIN-tab preview**, AND
   in-match (verify the loaded `SK_<Hero>_<Skin>` mesh, not `SK_<Hero>_Default`).
3. **Changeable** — picking a *different* owned skin updates the render immediately and
   makes the new pick the persisted one (no revert, no "stuck").
4. **The equipped indicator (checkmark)** matches the rendered skin.

Do **not** declare victory on a partial result. Do **not** stop at "the checkmark works"
or "the pedestal works" — the previous session already reached those and they are NOT
enough. Keep going through every blocker below until all four criteria hold, user-verified
via computer-use screenshots. Treat "it renders the default" as a hard failure to fix, not
a limitation to document.

---

## READ FIRST (authoritative detail — don't re-derive)
- **`docs/session-53-customization-persistence.md`** — read the whole file, especially the
  **UPDATE 2026-07-09 parts 1–5**. Part 5 is the current frontier.
- Memory **`supervive-customization-persistence`** — the condensed status + all RE facts.
- Project rules: `CLAUDE.md`. Hero/store/roster context: `docs/hero-roster-attempts.md`,
  memory `supervive-store-status`, `supervive-hero-roster-blocker`.

## TL;DR — what's DONE vs BROKEN
**DONE + verified:** the SKIN-tab **checkmark** shows/persists the saved skin (via a
`UFunction.Func` pointer swap on `GetDefaultCosmeticsBundleIdForHeroId`). Gliders/wisps/
sprays/emotes/titles/chromas persist (native setters). All auto-inject on launch.

**BROKEN (the whole remaining job):** the **3D hunter model still renders the DEFAULT skin**
(`SK_Ronin_Default`, `HeroCosmeticsBundle:RoninDefault`) on the main menu, even after all
our fixes fire cleanly. The checkmark is a lie relative to the model.

---

## THE EXACT RENDER PATH (bytecode-confirmed) — this is what must be defeated

Both the main-menu hunter and the pedestal resolve the skin here:
```
Comp_MainMenu_PartySlotSubject.DetermineCosmeticToShow
  -> BPFL_Cosmetics."Resolve Cosmetics Bundle For Hero"(member.HeroAssetID, member.CosmeticsAssetID)
       if IsValidPrimaryAssetId(member.CosmeticsAssetID) -> USE IT (the party-member cosmetic)
       else (empty — the client wipes it every ~1s poll) ->
           GetHeroAssetFromPrimaryAssetId(HeroAssetID) -> read hero_asset.DefaultCosmeticsBundle
```
- The SKIN-tab **checkmark** uses a *different* path (`Get Current Party Assets` else-branch
  -> native `GetDefaultCosmeticsBundleIdForHeroId`, which our Func-swap already redirects).
- So there are TWO resolvers; we fixed the checkmark one, NOT the render one.

## THE TWO CONFIRMED BLOCKERS ON THE RENDER (part 5)
1. **The party-member cosmetic is empty** (client rebuilds the member from GET /party each
   ~1s poll and never reads back `cosmeticsAssetId` — proven inert). So the render always
   takes the `else` fallback.
2. **The fallback reads a hero-asset object we are NOT patching.**
   - `LokiHeroAsset.DefaultCosmeticsBundle` is at offset **0x68** (StructProperty
     PrimaryAssetId, 16 bytes).
   - We data-scan the ObjectArray and patch the CDOs `Default__BP_HeroAsset_<Hero>_C`
     (found by: field@0x68 type-FName == "HeroCosmeticsBundle" AND class-name contains
     "HeroAsset"). We DID patch Ronin's CDO to `Ronin_StreetInferno`.
   - **But `GetHeroAssetFromPrimaryAssetId(Ronin)` returns an object whose
     `DefaultCosmeticsBundle` is STILL `RoninDefault`** — i.e. NOT our patched CDO. The
     render reads that other object (likely a loaded *instance*, or a different CDO/archetype).
   - Corollary: the earlier "pedestal showed Beast Slayer" was probably the *active/previewed*
     cosmetic, not our CDO patch. **Assume the CDO patch is currently INERT for the render
     until proven otherwise.**
3. **`TryPickMyHeroAndCosmetics` is async + validates.** We call it (game thread, resolved,
   stable, fires the re-render trigger correctly) but pass an **empty** OnTryPickComplete
   delegate, so the member-cosmetic set never lands → member stays default. Also it likely
   **validates ownership** (CanUse) and defaults non-owned skins.

## NEXT STEPS (pick the winning lever — likely #A or #B; do the RE, don't guess)

**#A — Patch the REAL render object.** RE `GetHeroAssetFromPrimaryAssetId` (search its FName;
find it native vs BP). If native, CALL it via the game-thread native-call primitive with the
hero PAID to get the exact returned object pointer; read its DefaultCosmeticsBundle @0x68 to
confirm it equals what the party slot renders; then patch THAT object (not the CDO). It may be
a loaded instance that appears/disappears — you may need to broaden the data-scan (it currently
finds only the 3 CDOs) or hook the load. **Then still force a re-render** (see #C).

**#B — The UNIFIED member-cosmetic route (probably the cleanest "perfect" answer).** Keep
`member.CosmeticsAssetID` VALID = the saved/selected skin. Every surface reads the member
first, so this fixes main-menu + pedestal + checkmark + changeability in ONE lever, and the
member is also the re-render trigger.
   - Find the party-member object. Session-49 disasm: `PartyManager+0xF8` = members container;
     `member.HeroAssetID` written at ~`member+0x110`; `CosmeticsAssetID` is the adjacent
     FPrimaryAssetId (probe it — read offsets 0x100–0x140 for a `Hero:` PAID then the
     `HeroCosmeticsBundle:` PAID right after). Confirm live (read-only) before writing.
   - Raw-write `member.CosmeticsAssetID` = saved-skin PAID (memory write, ANY thread, no
     validation — bypasses TryPick's ownership check).
   - Fire the re-render: the member setter's delegate `OnCosmeticUpdated` must fire, else the
     party slot won't re-read. Options: (i) call the game's member cosmetic setter (fires the
     delegate) rather than raw-write; (ii) supply a real OnTryPickComplete delegate to TryPick
     and let IT set + fire; (iii) find and directly broadcast the OnCosmeticUpdated multicast
     delegate. The write must survive the ~1s poll wipe — re-write it from the poller (~200ms,
     off-thread memory write) so it's essentially always valid.

**#C — Force the re-render (needed for #A, and for changeability everywhere).** The party slot
renders ONCE at menu load and only re-renders on a member-cosmetic CHANGE (OnCosmeticUpdated).
Our TryPick DID fire it (party slot re-rendered) — so the trigger mechanism is solved; the
problem was WHAT it rendered. Whatever data lever you pick (#A/#B), pair it with a reliable
OnCosmeticUpdated fire on menu load AND on every pick.

**#D — Ownership.** Verify each saved skin is marked owned so CanUse/TryPick don't default it.
`server/internal/menu/data/skins.txt` (391 entries) drives owned inventory; Ronin_StreetInferno
etc. must be present. **Expand skins.txt to ALL hero skins** (currently most hunters own 0 — see
`supervive-store-status`) — required for non-default/Mercury skins to be equippable/renderable
at all. This is a prerequisite for "perfect for EVERY skin".

**#E — Changeability end-to-end.** Pick reaches the backend already (member PUT records into
HeroCosmeticsBundles immediately; the ~5s cosmeticsbundle PUT also saves — both in `/revival/loadout`).
The shim poller (RefreshThread, 1s) detects changes. Make the render lever re-apply on change:
if you go the member route (#B) it's automatic; if you keep the fallback-patch route, note the
string→PAID conversion currently needs the game thread (via `MyGdcbThunk`, unreliable) — instead
read the picked skin's PAID directly off the member (it briefly holds it after a pick), or do an
off-thread FNamePool reverse-lookup (reverse of `GetFNameStr`).

---

## REUSABLE PRIMITIVES / RE FACTS (all in `tools/sigbypass-mod/loadout_fix.cpp`)
- **Game-thread native-call primitive** (`Call`/`PAIDFromString`/`CallSet2PAID`, s55/s59):
  hook ProcessInternal @`base+0x13454A0`, capture a live FFrame, call a native UFunction thunk
  @`UFunction+0xE0`. Off-thread ObjectArray SCAN is fine (loadout_fix's `Resolve`/`PatchHeroDefaultBundles`
  do it); native CALLS need the game thread.
- **`UFunction.Func` pointer swap** (heap, NON-.text — dodges the integrity check): UE5.4
  `execCallMathFunction` reads Func @+0xE0 at call time, so swapping it redirects EX_CallMath.
  `MyGdcbThunk` = call original exec thunk, then prefix-match the default bundle name → overwrite Result.
- **`GetDefaultCosmeticsBundleIdForHeroId`** (checkmark resolver, ALREADY redirected): FName
  0x00586579; ANSI @RVA 0x888E9C0; StaticRegisterNatives table @RVA 0x9BA7F58; exec thunk
  @RVA 0x52B3400; native impl @RVA 0x55899C0 (C ABI `FPrimaryAssetId* fn(out /*rcx*/, hero /*rdx*/)`).
- **Offsets (this build — non-standard layout):** GUObjectArray `base+0x9E38930`, FNamePool
  `base+0x9D81450`, GGameThreadId `base+0x9D49158`, ProcessInternal `base+0x13454A0`. UObject
  Class@0x18 Name@0x20 Outer@0x28. UStruct Super@0x40 Children@0x50 ChildProperties@0x58.
  UFunction Func@0xE0 ChildProps@0x58. FField Next@0x18 Name@0x20 Flags@0x38 Offset_Internal@0x44.
  FPrimaryAssetId = 16B: [+0] type FName, [+8] name FName. **LokiHeroAsset.DefaultCosmeticsBundle @0x68.**
- **Resolved instances/fns in the shim:** `g_lam` (LokiAssetManager), `g_pm` (PersonalizationManager),
  `g_party` (PartyManager) + `g_tryPick` (TryPickMyHeroAndCosmetics), `g_pafs` (PrimaryAssetIDFromString),
  `g_setBundle/g_setSlot/g_setChroma/g_getBundle`.

## BACKEND (Go, `server/internal/interactive/`)
- `GET /revival/loadout` serves `{heroCosmeticsBundles, slotCosmetics, luxeChromas, selectedHero}`
  (loadout.go + store.primaryLoadout/primarySelectedHero).
- `handleSetPartyMember` (interactive.go) records the member-PUT `cosmeticsAssetId` into
  HeroCosmeticsBundles immediately (feeds the shim fast) but does NOT serve it on the party
  member (inert). `buildSoloParty` does NOT serve the member cosmetic (proven inert/locking).
- Skin persistence is in `HeroCosmeticsBundles` (from the `cosmeticsbundle` PUT). `SelectedHeroAssetId`
  from the member-PUT hero.

## BUILD / RUN / TEST
- **Launch (elevated PS; self-elevates; Steam MUST be running first or Auth 14005):**
  `.\configs\launch-redirect.ps1` — rebuilds ags, sets hosts/certs, launches, auto-injects
  catalog_store_fix → pi8 + catalog_pick_fix + loadout_fix.
- **Shim build:** `clang++ -shared -O2 loadout_fix.cpp -o loadout_fix.dll -lkernel32 -lwininet`
  (in tools/sigbypass-mod). Marker: `docs/loadout-fix-marker.txt` (stages [0]–[8], [render], [VEH]).
- **ags build/hot-swap:** `& "$env:ProgramFiles\Go\bin\go.exe" build -C server -o server\ags.exe ./cmd/ags`,
  then kill `ags`, restart `-http :8080 -https :443 -log docs\capture.log -certs certs` -WorkingDirectory server.
  Certs reused if present.
- **Manual inject (game up):** `tools\inject\inject.exe mmap <PID> tools\sigbypass-mod\loadout_fix.dll`.
  NOTE: a re-inject can't re-swap Func (already swapped) — the render/TryPick parts still run, but
  **CLEAN tests need a relaunch** (re-inject state is degenerate: CDOs unload, patches undone).
- **usmapdump RE (read-only RPM):** `tools\usmapdump\usmapdump.exe {info,nameid,strings,findptr,peek,disasm}
  "SUPERVIVE-Win64-Shipping.exe" ...` (NEEDS the `.exe` suffix; base was 0x7FF6B54F0000 this build but
  ASLR — always recompute from `info`).
- **bpdump Kismet:** `cd tools/extractor/extractor; & "$env:ProgramFiles\dotnet\dotnet.exe" run -c Release --
  bpdump "<asset-substr>" "<fn|*|@props>"`.
- **Verify feed:** `curl -s http://127.0.0.1:8080/revival/loadout`.
- **Loki.log** `C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Logs\Loki.log` — grep
  `"SetHero is setting target cosmetic"` for the party-slot rendered bundle; `SK_<Hero>_` for the
  loaded mesh (the ground-truth signal — `SK_Ronin_Default` == FAIL, `SK_Ronin_StreetInferno` == WIN).
- **capture.log** `docs/capture.log` — HTTP; grep member/`cosmeticsbundle` PUTs.
- **Drive the client with computer-use** to verify visually (request_access "SUPERVIVE"). Test with a
  DISTINCTIVE skin (Strawberry Bomb, Street Inferno, Beast Slayer, SuccubusSISTE) — NOT `Default_*`.

## GOTCHAS (cost real time — don't repeat)
- **The ObjectArray scan (~500k objects) MUST run OFF the game thread** — running it in the PI
  hook stalled + crashed the game. Memory reads/writes are any-thread; native CALLS need the game thread.
- **Persistent inline `.text` patch trips the ~3-5min integrity check** (the inline GDCB detour crashed
  at ~2min). Use heap/data patches (UFunction.Func swap, field writes), never a persistent code-byte patch.
- **D3D12 menu-load crash is intermittent** (~50%; pure d3d12/nvldumdx, NOT the shims) — just relaunch.
- **inject.exe hangs intermittently** (loader lock, WININET remote-load) — kill it + retry, or relaunch.
- **CDOs / hero assets load & unload** — a data-patch may be undone or (proven) target an object the
  render doesn't read. Verify against Loki.log `SK_<Hero>_` every time.
- **NEVER edit `server/state/interactive.json` with PowerShell Out-File** (UTF-8 BOM breaks Go's
  json.Unmarshal → whole file dropped). Seed via ags HTTP routes.
- **The client auto-picks a default hero (Alchemist) on load** and equips its default skin; the active
  hero ≠ any hero you seeded. Use `/revival/loadout`'s `selectedHero` to know the real one.

## DLL VARIANTS in `tools/sigbypass-mod/` (current deployed = full build)
- `loadout_fix.dll` = current (Func-swap + poller + CDO patch + TryPick trigger + selectedHero).
- `loadout_fix_funcswap.dll` = persistence-only (checkmark). `loadout_fix_detour.dll` = the CRASHING
  inline .text version (cautionary reference — do not deploy). `loadout_fix_prev.dll` = pre-GDCB.

## DEFINITION OF DONE (all must be user-verified via computer-use, on a CLEAN relaunch)
- [ ] Main-menu center hunter renders the saved skin (Loki.log loads `SK_<Hero>_<Skin>`, not `_Default`).
- [ ] Customization pedestal + SKIN-tab preview render the saved skin.
- [ ] Checkmark matches the rendered skin.
- [ ] Picking a different owned skin updates ALL of the above immediately and persists (change again → also works).
- [ ] Survives a full relaunch (skin already applied on load, no re-equip).
- [ ] Works for multiple hunters (test at least 2–3, e.g. Alchemist, Ronin, Succubus) and for
      non-default skins (expand skins.txt ownership as needed).
- Keep iterating until every box is checked. This is not done until it is perfect.
