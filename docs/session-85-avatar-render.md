# S85 — Avatars: render + live switching, both SOLVED

Date: 2026-07-19. Branch: `dedicated-server-stub`.

## TL;DR

The equipped AVATAR **selects correctly end-to-end** — that half was never broken.
The image didn't draw because the card widgets resolve the avatar from the
**party member's `PersonalizationLoadout.SlotCosmeticsEntries`**, which was empty.
Serving that field on the party member **FIXES IT — verified live 2026-07-19**.

## What was NOT broken (falsified early, don't re-open)

Selection, persistence, and the client's own model are all healthy:

- Clicking a tile fires `POST /personalization/players/{id}/slotcosmetics`
  `{"slot":"Avatar","asset":"SlotCosmetics:AVATAR_AboveItAll"}`.
- The store persists it (`GET 127.0.0.1:9210/api/players`).
- The client's outbound WS presence blob carries
  `"avId":"SlotCosmetics:AVATAR_AboveItAll"` and **tracks clicks live**
  (observed flipping AlchemistHM → AboveItAll, `docs/capture.log` ~02:22:29–02:22:36).

⚠ TRAP: presence blobs sampled *before* the first equip of a session read
`"avId":""`. That is NOT evidence of a broken model — it cost this session a
full 5-lens workflow run on a false premise. Always sample a presence blob
AFTER an equip before concluding anything about `avId`.

## Root cause (RE'd 2026-07-19, 29-agent read-only sweep + live RPM)

The avatar widgets never consult the PersonalizationManager.

`WBP_UI_Social_PlayerAvatarIconV2_C` (UClass `0x1468DFBD260`) gates on
`IsValidSoftClassReference(TargetAvatarAsset)` (instance var, SoftClassProperty
`+0x0320`). On failure it **deliberately** calls
`Image_Avatar.SetBrushResourceObject(TX_Transparent)` and pops execution — the
blank we see is painted on purpose, not a missing texture.

`TargetAvatarAsset` is filled by `BPFL_Social_C::DetermineSocialInfoForPlatformPlayer`
(`@0x14698729F00`), a three-way branch. For a valid+online party member
(fallthrough `@188`) the avatar comes from `DetermineSocialInfo_FromPartyMemberOnly`
(`@0x1469872A000`), which reads:

```
PartyMember.PersonalizationLoadout.SlotCosmeticsEntries
  -> PersonalizationManager::FindSlotCosmeticEntry(entries, GetAvatarSlotName())
  -> OutAssetId -> Avatar Asset ID
```

Live confirmation (read-only RPM, both `PartyMemberModel` instances):
`PersonalizationLoadout` `+0x0190` all-zero, `Version` = −1,
`SlotCosmeticsEntries` `Num=0`. Probe:
`<scratchpad>/partymember_loadout.py`.

**Grid-vs-card delta (answers the central question):** the picker GRID resolves a
`PrimaryAssetId` itself (`GetSoftClassReferenceFromPrimaryAssetId` → `LoadAssetClass`
→ CDO → `ExtendedPortrait`), so it always works. The card does NOT resolve a
PrimaryAssetId at all — it expects a pre-resolved `TSoftClassPtr` pushed in by
BPFL_Social. Different contract, same id.

Live struct layout (`ScriptStruct PersonalizationLoadout @0x145E5806A60`) — one of
the rare cases the extracted usmap MATCHED:

```
+0x00 ID(Str)  +0x10 Version(Int64)  +0x18 EmoteIds(Array)  +0x28 TitleIds(Array)
+0x38 SlotCosmeticsEntries(Array)  +0x48 IsAnonymous  +0x50 Token(Str)
+0x60 HeroCosmeticsBundlePreferences(Map)  +0xB0 LuxeSkinChromaPreferences(Map)
+0x100 LobbyPlatformPreference(Struct)
```

## Fix landed

`buildSoloParty` (`server/internal/interactive/interactive.go`) now serves
`personalizationLoadout` on the party member, reusing `loadoutDoc()` so the wire
shape lives in one place. Guarded by
`TestBuildSoloPartyCarriesPersonalizationLoadout` — the load-bearing assertion is
the **container type**: `slotCosmeticsEntries` must marshal as an ARRAY of
`{slot, asset}`. Per the validity model a matched key with the wrong container
type rejects the WHOLE doc, which here would take out the party panel, not just
the avatar.

NOT a re-run of the closed skin experiment: that verdict was scoped to the
member's `CosmeticsAssetID` (hero skins). `PersonalizationLoadout` is a different
field that had never been served.

## VERIFIED FIXED (relaunch test, 2026-07-19 22:05)

Clean relaunch via `configs\launch-redirect.ps1` with slots populated server-side.

Party member model, live RPM (`<scratchpad>/partymember_loadout.py <pid>`):

```
SlotCosmeticsEntries: TArray Num=4
  [0] Slot=Avatar  Asset=SlotCosmetics:AVATAR_AlchemistHM
  [1] Slot=Glider  Asset=SlotCosmetics:GLIDER_AngelicForce
  [2] Slot=Spray   Asset=SlotCosmetics:SPRAY_Dumpling3
  [3] Slot=Wisp    Asset=SlotCosmetics:WISP_AngryNapaCabbage_CellShading
```
`TitleIds` Num=1 also populated. Version 1208.

Render gate, live RPM (`<scratchpad>/avatar_widget_check.py <pid>`):

```
BEFORE: 0/28 instances with a valid TargetAvatarAsset; all painting TX_Transparent
AFTER : 5/28 with TargetAvatarAsset =
        /Game/Loki/Personalization/Avatars/AlchemistHM/BP_Avatar_AlchemistHM
        brushes = TX_Avatar_AlchemistHM  and  TX_Avatar_AlchemistHM_Extended
```
The remaining zeros are empty party slots + pooled widgets — expected for a solo party.

### ★ CORRECTION — the source is the PARTY PAYLOAD, not a login fetch

An earlier draft of this doc inferred the member loadout came from a login-time
`GET /personalization/players/{id}` (reasoning from a stale `Version` 1168 seen in a
previous process). That is **WRONG**. In the verified launch there were **ZERO**
`GET /personalization/players/{id}` requests across 800 captured requests, yet the
model populated fully. The per-poll `GET /party/parties/{partyId}` payload is the
sole mechanism. The 1168 was simply a leftover value from the prior session.

Corollary: `buildSoloParty`'s `personalizationLoadout` field is **load-bearing**, not
redundant — do not drop it.

### Also falsified along the way

- "The client is stuck / my change broke login" — NO. A mid-load client polling
  `/party/parties` with no storefront traffic looks identical to a wedged one. It was
  simply still loading (SUPERVIVE takes ~3-4 min to menu here). Zero
  `Deserialization failure` / `Invalid response received` in Loki.log throughout.
- The `avId:""` presence trap (see above) — cost a full workflow run.

## PART 2 — SWITCHING (the party-level version gate)

After rendering worked, switching still required a relaunch: clicking a new avatar moved
the picker CHECKMARK but the card kept drawing the old one.

### Characterization (this is the part that pointed straight at the cause)

A probe served a changing marker into TWO known-read member fields (`displayName`,
`premadeRestrictionKey`) while the loadout also advanced. NOTHING propagated — not the
loadout, not even `displayName`. So the client was not skipping the loadout struct; it was
discarding the ENTIRE party document on every poll after the first.

### Root cause — `UPartyModel::SetParty` (base+0x587BE90)

```asm
+0x587BEFF  mov rax,[r14+0x10]        ; incoming FParty.Version (int64)
+0x587BF03  cmp [r12+0x568],rax       ; cached PartyModel.Party.Version
+0x587BF0B  jge <epilogue>            ; cached >= incoming -> BAIL, apply nothing
```

`buildSoloParty` pinned `"version": 1`, so the document applied exactly ONCE (0 -> 1 at
launch) and every later poll was discarded wholesale.

⚠ WHY THIS WAS ALMOST MISSED: `PartyModel` exposes NO reflected `Version` UProperty — a
property dump shows only `bIsRankedEligible` among its scalars. The gate is on the native
`FParty` struct field at `PartyModel+0x568`. **Absence of a UProperty does not mean absence
of the field.** An early property-dump led to "no version to gate on", which was wrong.

### Fix

`store.partyVersion()` + a `partyVer` counter bumped in `update()` / `updatePrimary()`,
emitted as the party doc's `version`. Seeded from `time.Now().UnixMilli()`, NOT 0 — the
client outlives an ags restart (we restart the backend under a running game constantly), so
a counter restarting at 0 would sit BELOW the client's cached value and wedge the party
permanently. UnixMilli advances ~1000/sec vs the counter's few/sec, so a restart always
lands far above whatever was last served. Guarded by `TestPartyVersionAdvancesOnWrite`.

### Verified live, no relaunch

- client cached `Party.Version` (`PartyModel+0x568`) tracks ours: `1784520647990`
- two consecutive switches propagated: loadout `1227 -> 1228 -> 1229`, avatar
  `AboveItAll -> AmusementPark -> AboveItAll`
- widgets followed: `TargetAvatarAsset` / brushes flipped to the new avatar

Second gate, for the record (member loadout, `+0x587C676`): incoming `Loadout.Version` must
exceed existing, else skip; `loadoutDoc`'s `version` already satisfies it — but it is only
ever REACHED once the outer party gate passes.

### Known remainder

Of 5 live avatar-icon widgets, 3 track switches live; 2 (`0x267EBF1E780`,
`0x267835C1C80`) stayed on the launch-time avatar across both switches. Likely hidden or
pooled instances that rebind on show — NOT confirmed. If a visible surface is ever stale
while the party model is current, this is the thread to pull: find what subscribes to
`OnPersonalizationLoadoutChanged` (broadcast at `+0x587C699`) and what those two instances
are parented to.

### Falsified along the way (do not re-open)

- H1 "loadout only assigned at member construction" — FALSE. The existing-member path at
  `+0x587C637..+0x587C699` re-assigns it and broadcasts `OnPersonalizationLoadoutChanged`.
- H2 "ULoadoutReconciler eats it" — FALSE. `ReconcileLoadout` (body `base+0x585E900`) touches
  only PersonalizationManager/CatalogManager and writes to NO `PartyMemberModel`. Also its
  own gate was already satisfied (LastLoadoutVersion tracked 1227 correctly).
- H3 "membership-set diff short-circuits" — FALSE. The diff runs AFTER the gate and only
  builds a removal list.
- H4 "HTTP dedupe (ETag/304)" — FALSE. Zero conditional-request headers across 221 logged
  party requests. And `createdAt` was always a no-op: `FParty` has no such property, so
  varying it did nothing.
- `/party/.../reconcile` as a refresh lever — the client never calls it, and it funnels
  through the same gate anyway.

## PART 3 — THE REAL SWITCHING BLOCKER: split identity (S85, 2026-07-20)

After PART 2 shipped, the USER reported switching STILL didn't work — a direct
contradiction of the RPM "verified" claim. It was right to trust the user: PART 2's
verification drove the flow with `curl` against player `9b9d…`, but the live client
had drifted onto a DIFFERENT account.

### The catch

`GET /party/parties/party-<id>` was polled for `9b9d2c887e2524f918e383a895f2f1c2`
(2231x) while the user's avatar clicks POSTed
`/personalization/players/b70b628c424e7431455e76e36408f8f4/slotcosmetics`. Two
different account ids, same physical player ("Reviver#0001" in both JWTs). Avatar
equips landed on an account the party never reads, so no switch could reach the card.

### Why two ids

`token.UserIDFor(key)` is deterministic (`sha256("supervive-revival:"+key)[:16]`).
Reversing the two ids:
  - `9b9d…` = `UserIDFor("platform:steam")` — the Steam platform-token login fallback
  - `b70b628c…` = `UserIDFor("player")` — `handleToken`'s ad-hoc fallback when the
    grant carried no username

The client authenticates through BOTH the Steam platform endpoint AND the plain
`/oauth/token` grant (and refreshes on a timer). The Steam path keyed `platform:steam`;
the `/oauth/token` grant, receiving no username, fell through to the ad-hoc `"player"`
key — a DIFFERENT id. Different subsystems latched onto different tokens. (A latent
sibling bug: `handleToken` also keyed on `code`, an opaque per-login value — that mints
a fresh id on every login.)

### Fix

One canonical identity for the single-account revival. `token.LocalPlayerKey =
"platform:steam"` (anchored so `LocalPlayerID()` == the id the party and all state
already use — zero migration). Every unidentified-user path resolves there:
`handleToken`'s fallback (and it no longer keys on `code`), `handleUsersMe`,
`handleUpdateMe`. A real username still gets its own id. Guarded by
`TestAuthPathsAgreeOnOneUserID` (iam) which drives the Steam + all three grant paths
and asserts one sub.

Requires a RELAUNCH: a running client keeps its cached split tokens; only a fresh
login picks up the unified id. Verified post-relaunch: every request carries `9b9d…`
only, `b70b628c…` gone.

### Also seen this session (separate, NOT yet fixed)

The client hammered `GET /storefront/battlepass/progressiontracks` ~15x/sec (1.3M
requests), crowding the party poll down to ~4 of every 200 requests — which by itself
would make switching feel dead (party refresh every ~50s instead of ~3s). Watch
whether the relaunch clears it; if not, it is its own investigation.

## PART 4 — latency + launch stability (S85, 2026-07-20)

### Switch latency: ~30s, CLIENT-BOUND (not fixable by the version)

With identity fixed, switches propagate but SLOWLY — live RPM measured 29s / 39s / 44s /
57s across trials: a fixed client-side apply cadence that our out-of-band POST phases
against randomly (avg ~30-40s).

I tested whether the served party `version` controls this. It does NOT:
  - one-shot bump per write:        ~39s
  - 8s window of climbing version:  ~29s
  - version climbing on EVERY poll:  ~44-57s  (no better, sometimes worse)
The client polls `/party/parties` every ~3.2s but only APPLIES the party (runs SetParty
→ updates the member PersonalizationLoadout) on a fixed internal cadence, independent of
how fast the version rises. The version only has to be HIGHER than the client's cached
value when that cadence next fires — so a single bump-on-write is the correct, simplest
design (shipped). Making it climb adds re-apply churn for zero latency benefit.

`mainmenu_refresh_pi8` does NOT help either — it refreshes the hero/center preview
(`Comp_MainMenu_PartySubject` / `BP_MainMenuSpawner_MainMenu_PartySlot`), not the avatar
card widget (`WBP_UI_Social_PlayerAvatarIcon*`).

A real UI avatar click fires ONLY `POST /slotcosmetics` (+ a local optimistic update that
moves the picker CHECKMARK instantly) — NO party-member PUT. So the checkmark is instant
but the preview card / party-panel avatar reconcile on the same ~30s party cadence as an
out-of-band POST. The ~30s is the genuine user-facing latency for those surfaces.

The ONLY backend lever that could beat it is a lobby-WS push that forces an immediate
party re-apply (AccelByte partyDataUpdateNotif-style). Whether this client parses such a
notif is under active RE (see the S85 ws-push workflow). If not, a minimal read-safe shim
(call the party model Refresh / write the member loadout + broadcast
OnPersonalizationLoadoutChanged) is the fallback.

### Launch stability — the full shim set CRASHES; catalog_store_fix alone is stable

The first full-set relaunch after the identity fix CRASHED (access violation) before
reaching the menu — the client polled party for 6 min and never fanned out. This is
NOT the backend: proven by isolation.

- `-NoHook` (no shims): reached menu in ~12s, clean fan-out, avatars render + switch. ✓
- `-Hook catalog_store_fix.dll` (primary only, no PI-hookers): reached menu, stable. ✓
- Full set (catalog + pi8 + catalog_pick + loadout + missions + battlepass): CRASHED. ✗

The full set runs THREE PI-hookers (pi8, loadout_fix, missions_fix) whose transient-
install race CLAUDE.md flags as "VALIDATION PENDING." This launch appears to be that
race biting. It is a PRE-EXISTING shim-stability issue, independent of the avatar work
(which is pure backend). A prior full-set launch (PID 1968) had held for 15+ min, so it
is intermittent.

RECOMMENDED stable launch for using the avatar fix now:
`launch-redirect.ps1 -Hook tools\sigbypass-mod\catalog_store_fix.dll`
(picker grid works via the catalog, backend does render+switch). To narrow the full-set
crash later, bisect the PI-hookers with `-NoMissions` / `-NoLoadout`.

## PART 5 — LATENCY SOLVED (backend messenger-drop lever, S85 2026-07-21)

The ~30s latency IS backend-fixable after all — the earlier "no backend lever" was
wrong (it only ruled out a WS-notif PUSH). A 21-agent RE workflow found the real
mechanism and lever.

### Mechanism (RE'd + live-confirmed)

The client APPLIES its party model — the avatar card's data source (member
PersonalizationLoadout) — ONLY during the state-resync it runs on each
LokiPlatformMessenger (`/notifications/players/{id}`) RECONNECT. NOT on the ~3.2s HTTP
party polls, NOT on any served-version change. A switch flips ~0.4s after a reconnect
resync fetch while ~9 intervening 3.2s polls carry the identical fresh loadout and do
NOT apply it. The ~30-57s latency was just the random time to the next reconnect in the
client's ~63s heartbeat-watchdog cycle.

### Lever (backend-only, no shim)

When the loadout changes, ungracefully DROP the player's messenger socket
(`ws.Conn.Drop()` = raw close, no WS close frame). The client sees a `1006` close,
reconnects after its own backoff, and its resync re-fetches `GET /party/parties` (which
already carries `personalizationLoadout`) and applies it.

Wiring: `lobby.Service` keeps a per-player messenger-conn registry + `MarkDirty(id)`
(leading+trailing debounce, `enableMessengerDrop`); `interactive` calls it after every
loadout write via a nil-safe `SetPartyDirtyNotifier` seam wired in `cmd/ags`; the ws
package gains `Conn.Drop()`. Tests: `lobby_markdirty_test.go`.

### Result — live-measured

**~30-57s → ~1.2s** (POST→member-model flip). Loki.log confirms the exact cycle:
`Messenger socket closed wasClean:0 Status: 1006` → `attempting to reconnect in ~1.0s`
→ `connection established` → resync `GET /party/parties` 60ms later → apply. Game
stays healthy across the reconnect cycles. This also RESOLVED the synthesis's one
unverified risk: a SERVER-initiated ungraceful close does trigger the fast
reconnect+resync (not a client backoff storm).

### The ~1s floor

The residual latency is the client's OWN reconnect backoff, live-observed varying
0.6-1.5s (random jitter), avg ~1.0s — not backend-controllable. So switches land
~0.8-1.8s, avg ~1.2s. Strict, reliable sub-1s would require a native shim that forces
the apply directly (write member PersonalizationLoadout + broadcast
OnPersonalizationLoadoutChanged, base+0x587C699, whose live subscribers were confirmed:
WBP_BattlepassSplash_PlayerTitle::UpdateAvatarOnPresenceUpdated,
WBP_UI_PartyMemberNameplate::"On Personalization Updated") — ~0.2s but adds a PI-hooker
(the full shim set already races/crashes), so it is a deliberate tradeoff, not shipped
by default.

## Second bug found (separate, real)

Slot cosmetics can go missing from the server state. Evidence:
`docs/loadout-fix-marker.txt:39` records the shim fetching
`bundles=9 slots=0 chromas=0` at launch, i.e. it never replays the Avatar/Glider/
Spray/Wisp equips. Persistence itself is fine (verified: a POST lands in
`server/state/interactive.json` immediately), so something clears the map.
Not root-caused. The four slots were restored by hand this session.

## Closed as WONTFIX

16 of 233 shipped avatars have **no `ExtendedPortrait` property at all** (incl.
`BP_Avatar_AssaultActivated`, the blank tile in the screenshot) — the grid tile
binds `ExtendedPortrait` (`LokiSlotCosmeticsAsset_Avatar +0x00C8`), so retail
rendered these blank too. Shipped-content gap, not a revival regression. Do NOT
prune them from `cfg.Store.Accessories` — they all have a valid `Portrait` and
render fine on any Portrait-binding surface.

## Ops notes

- `ags` was rebuilt and restarted; previous binary backed up at
  `server/ags-preavatar.exe` (rollback = swap it back and restart).
- `tlscert` REUSES existing certs when root/leaf/key all exist, so an ags restart
  needs no `cacert.pem` re-append and no game relaunch.
- `newStore("state/interactive.json")` is a RELATIVE path — it resolves against the
  process working directory. Restart ags with the working directory set to
  `server\` or it will load a different (stale) state file.
