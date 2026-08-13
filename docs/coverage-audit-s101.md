# SUPERVIVE Revival — Coverage Audit

**Produced:** 2026-07-26 · **Repo HEAD at audit time:** `f6a7985` (S102) · **364 commits · 726 tracked files · 364 docs entries · 956 KB memory (untracked)**

**Method:** eleven independent domain audits, each adversarially re-verified by a second pass. Where an auditor and its verifier disagreed, **the verifier's corrected number is used** and the disagreement is recorded. Every number below is either reproduced from an artifact or attributed to the pass that measured it.

**Question this answers:** *How much of the game do we currently have mapped out — what do we know, what don't we know, and where should effort go to complete the picture?*

---

## 1. Executive Summary

### The honest headline

There is no single coverage number, and any attempt to give one is misleading. The project is **seven distinct layers stacked on top of each other, and their coverage differs by a factor of four.**

> **The backend is nearly finished. The content catalog is broad but shallow. The runtime/gameplay layer is thin.**

Concretely:

- **Service-impersonation layer (the Go backend): ~72%.** Of 40 distinct endpoints the client actually calls, **25 return real data, 6 are typed/proven-inert stubs, 9 fall to the `{}` catch-all** — and the live client logs **zero** validity or deserialization errors. This layer is close to done for menu use. What's missing is the *write* half (27 of ~33 party operations), the WebSocket vocabulary (~~**4 of 16**~~ **4 of 43** declared lobby request types answered — the "16" was a scan artifact, see `docs/fk15-ws-push-audit.md` §3.4), and everything a real match would touch.
- **Front-end menu layer: ~65%.** Of **44 enumerated surfaces, 24 are fully LIVE**, 8 partial, 5 defective, **7 never opened in ~100 sessions**. Six of the 24 live surfaces depend on injected shims — and the full six-shim launch set is recorded as **crashing** (S85) and has never been re-tested.
- **Content catalog layer: ~55%.** Path enumeration is **100% (107,123 files)**. Structural decode is **88% of `.uasset` but 0% of 7,300 `.umap`**. Semantic decode is far lower: **0 of 481 items have a display name, 4 of 2,429 GameplayEffects record Modifiers, 0 of 60 curve tables are extracted.**
- **Game-design layer (what the game *is*): ~37%.** We have a near-complete **name index** (25 heroes, 40 queues, 34 POIs, 330 missions, 871 gameplay tags) and almost no **tuning data** — not one hero's health, not one ability's damage, not one circle timing.
- **Binary/runtime map: ~20%.** ~**617 distinct code addresses known against an estimated 120,000+ function entry points (~0.5%)**, and only ~254 with any name. Offsetting that: the *live-reflection* tooling is excellent, and the game's own reflection data functions as a substitute symbol table.
- **Playable-game route (tutorial force-open): ~53%.** Presentation and traversal are genuinely **proven** — real gamemode/gamestate, spawned + possessed + **visible** + **animated** hero, WASD movement, top-down camera, completable objectives, exit to menu. Simulation is **unmapped** — 0 abilities ever granted, 0 damage ever dealt, 5 of 30 lessons driven.
- **Netcode / dedicated-server route: ~57% (parked, but far higher than "parked" implies).** The connect → join → possess → spectate half of SUPERVIVE's network protocol is solved and shipped in a building UE 5.4 stub (17 mirrored classes, 72 replicated properties, 83 index-aligned net functions). The server-side *game model* is ~5% and is blocked on a binary that does not exist.

### The one-sentence version

**We have thoroughly mapped how to *talk to* the game and how to *decorate* it; we have barely begun mapping how the game *works*.**

### The structural reason for the gap

Every solved system was solved by one of two moves: (a) serve the client a document it already knows how to parse, or (b) call a function the client already knows how to run. Both operate on the **presentation** surface. Neither requires understanding the simulation. The remaining work — abilities, combat, items, maps, match rules — has no such shortcut: it requires knowing what the game's own data *means*, and that is exactly the layer we have not decoded.

### The single highest-leverage finding in this audit

The extractor **does not serialize Blueprint CDO default overrides in this build**. This one defect — documented since S61 (2026-07-10) and never generalized — is the shared root cause of *seven* separately-filed gaps: hero ability slots, GameplayEffect modifiers, game-mode tuning, item stats, mission objective names, Armory tables, and the 9 empty `BP_HeroAsset` dumps. It is currently being treated as seven independent extraction chores. **It is one bug.**

---

## 2. Coverage Scorecard

| # | Domain | Auditor % | Verifier verdict | **Corrected %** | Confidence | Trend |
|---|---|---|---|---|---|---|
| 1 | Native shims (injection layer) | 85 | OVERSTATED | **78** | verified | flat |
| 2 | Backend HTTP / WS endpoints | 78 | OVERSTATED | **72** | verified | flat (untouched 5 days) |
| 3 | Tooling & instrumentation | 82 | OVERSTATED | **72** | verified | rising |
| 4 | Knowledge-base integrity | 80 | OVERSTATED | **72** | mixed | **falling** (summaries lag) |
| 5 | Front-end menu surfaces | 70 | OVERSTATED | **65** | documented | flat / at-risk |
| 6 | Operational reproducibility | 80 | OVERSTATED | **65** | verified | **falling** |
| 7 | Dedicated-server / netcode | 52 | UNDERSTATED | **57** | verified | parked |
| 8 | Asset extraction / catalog | 45 | UNDERSTATED | **55** | verified | flat |
| 9 | Playable tutorial route | 45 | UNDERSTATED | **53** | verified | **rising fast** |
| 10 | Game systems & design | 34 | UNDERSTATED | **37** | verified | flat |
| 11 | Binary RE (offsets/functions) | 15 | UNDERSTATED | **20** | verified | rising |

**Reading the verdicts.** The pattern is not random. Every domain that scores its own *tooling and process* came back **OVERSTATED** (shims, backend, tooling, hygiene, repro, menu). Every domain that scores its own *knowledge of the game* came back **UNDERSTATED** (extraction, tutorial, DS, game systems, binary). The project is systematically **over-confident about its machinery and under-confident about what it has actually learned** — chiefly because a large body of solved work is buried in commit bodies, un-merged dumps, and cross-route source files nobody re-reads.

**Layer roll-up (the shape that matters):**

```
Service impersonation  ████████████████████░░░░░  72%   nearly complete
Front-end menu         ██████████████████░░░░░░░  65%   complete-but-fragile
Netcode / DS           ████████████████░░░░░░░░░  57%   solved half, parked
Content catalog        ███████████████░░░░░░░░░░  55%   broad, very shallow
Playable route         ███████████████░░░░░░░░░░  53%   presentation yes, simulation no
Game design semantics  ██████████░░░░░░░░░░░░░░░  37%   names yes, numbers no
Binary / runtime map   █████░░░░░░░░░░░░░░░░░░░░  20%   0.5% static, strong live
```

---

## 3. Per-Domain Detail

### 3.1 Backend HTTP / WebSocket — **72%**

**What we KNOW**

| Metric | Value |
|---|---|
| Distinct endpoints the client calls (2 latest captures, 6,726 requests) | **40** |
| — served with real data | **25** |
| — typed / proven-inert stubs | **6** |
| — falling to the `{}` catch-all | **9** |
| Registered route handlers in `server/` | 115 (44 IAM, of which only **5** are ever exercised) |
| Client-side validity errors in 11 live logs | **0** |
| HTTP responses that are not 200 | 7 (all WS 101 upgrades) |
| Go tests | 40 in 8 files, all passing; **0 external dependencies** (`go.mod` is 2 lines) |
| Content served | 25 heroes, 25 bundles, 19 currency packs, 5 featured, 391 skins, 536 slot cosmetics, **977 assets marked IsOwned** |

The architecture is genuinely good: one mux, a catch-all that returns empty-success **and logs the request** so the client reveals its next call, and a codified validity model (UE ignores unknown JSON keys; it rejects only a *matched* key with a wrong type). Login, party, store, inventory, missions, progression, personalization and the account pass all round-trip and persist.

**What we DON'T**

- **The write half of the party surface: 6 of ~33 declared operations.** `/joinQueue`, `/setTargetQueues`, `/sendInvite`, `/setIsOpen`, `/leave`, `/refreshRanks` and 21 more fall to the catch-all. Any real queue or multiplayer flow walks straight into them.
- ~~**The WebSocket vocabulary: 4 of 16.** … and server→client push is **measured non-functional** (5 negative probes).~~
  ⚠⚠ **RETRACTED S117, 2026-08-13 — BOTH HALVES ARE FALSE. See `docs/fk15-ws-push-audit.md`.**
  (a) **Push works, and the measurement already existed:** with `LogAccelByte` raised, the client logs
  `AccelByteWebSocket::OnMessageReceived` **4 times for the 4 frames our backend sends** [M], and one
  `/lobby` socket held **3 h 43 min** with zero closes. The 5 probes all predate FK-11's verbosity fix
  by **41 days**, so every detector they named was pinned to `Warning` — and **2 of the 6
  (`LogPlatformLobby`, `LogPlatformQuery`) do not exist in the binary at all**, occurring nowhere in
  this repo except the sentence asserting their silence.
  (b) **The "16" is a hand-picked scan list, not an enumeration.** The client's message-type table
  (contiguous, RVA `0x86011D0`–`0x8602828`) holds **119 tokens — 43 Request / 43 Response / 32 real
  Notif** [M]. Two of the 16 are not message types; the list **omits two of its own numerator's four
  items**. The honest ratio is **4 of 43** requests answered, and **1 of 32** notif types ever pushed.
- **The `/notifications` messenger socket still dies every ~60-70 s.** Four client-initiated closes in 5 minutes, each 5.0 s after the client's own heartbeat. The proactive 30 s keepalive is *proven delivered* (logged 6× in the capture) and still fails — so this is a **format** problem, not a delivery problem. The S85 avatar-latency fix *exploits* this reconnect cycle, which hides the bug.
- **No model for any of the 9 catch-all endpoints** — `/mmr/*`, `/match-history/*`, `/player-stats/*`, `/referral/*`, `/party/*/voice`. They currently tolerate `{}` only because the account has no data; the moment a real match completes, Career→History and Stats have nowhere to get anything.
- **Egress outside the redirect is structurally invisible.** Only 2 hostnames are in the hosts file; everything else reaches us via the 25 `ServiceHostnames` we hand the client. Anything the client addresses by hard-coded hostname bypasses the entire census. Live proof: **Vivox (23 requests)** and **`o566896.ingest.sentry.io` (2 requests)** — the latter recorded *nowhere* in the repo as a live outbound endpoint.
- **`/storefront/battlepass/progressiontracks` is still 95% of all HTTP traffic** at ~10.5–13.5 req/s. (Auditor said 99% / 14.7 req/s; verifier re-measured 95.4% / 10.5 req/s and 96.2% / 13.5 req/s.) The mechanism is fully RE'd (S82: version-adoption gate at `OnSuccess 0x57C8130`) — it is simply never satisfied by HTTP.

**Structurally blocked:** the Vivox voice token requires Theorycraft's HS256 shared secret and Vivox validates server-side. Confirmed live this session (`20127: Access Token Service Unavailable`). This one is genuinely unfixable from the backend.

---

### 3.2 Native shims (the injection layer) — **78%**

**What we KNOW**

| Metric | Value |
|---|---|
| Shim sources / built DLLs | **63 `.cpp` / 135 `.dll`** (72 are `-DKMODE=` variants of 3 monoliths) |
| Production shims in the default launch set | **6** (catalog_store_fix, catalog_pick_fix, mainmenu_refresh_pi8, loadout_fix, missions_fix, battlepass_adopt_fix) |
| Manually-injected actives | 3 (tutorial_launch, gft_ready_fix, ds_hybrid) |
| Dead / superseded RE probes | **54 of 63 (86%)** |
| Sources hardcoding `ProcessInternal` RVA `0x13454A0` | 34 |
| Shared C++ headers | **0** — every shim is a self-contained translation unit |
| Distinct hardcoded module RVAs across all shims | **179** (97 in the 6 production shims) |
| Shims that locate anything by byte-pattern scan | **0** (13 do runtime *memory* scanning, but against hardcoded vtable addresses) |
| Build scripts / makefiles | **0** |

The keystone technique is excellent and well-documented: hook `ProcessInternal`, capture a live `FFrame`, call a `UFunction`'s native thunk (`+0xE0`) directly — which works where slot-56 `ProcessEvent` is a proven no-op in this build. On top of it sit param passing, OUT-params (`FFrame.OutParms @ +0x80`), and the Blueprint-bytecode variant `CallBPGuarded`. Four PI-hookers coexist via a shared named mutex with transient install.

**What we DON'T / what's broken**

- **`battlepass_adopt_fix` hooks ProcessInternal and does NOT take the shared mutex** — holding the hook for up to **10 seconds** — while `inject-secondaries.ps1:59` asserts in a comment that it does not hook PI at all. The default set runs **four** PI-hookers, not the three every doc claims.
- **The primary-readiness gate fires on a stale marker.** `docs/inject-secondaries.log` logs "game process is up" and "primary installed+unhooked — safe to inject secondaries" **in the same second**. The gate regex-matches `[unhook]` in a marker file nothing clears between launches. So in the one recorded full-set launch, all five secondaries were injected *during* the primary's thread-suspending `SafeWrite` — precisely the condition the gate exists to prevent. **This is a stronger explanation for the S85 crash than the 4th-PI-hooker hypothesis.**
- **`inject.exe` resolves by process *name*, first match** — not newest-by-StartTime. Any lingering game process silently redirects the whole secondary set into the wrong target while logging five clean successes.
- **No double-injection guard and no build-version guard in any of 63 shims.** A second manual-map creates a second image with its own worker thread; `catalog_store_fix`'s patch-then-restore is not idempotent under concurrency.
- **Build reproducibility is better than first reported but booby-trapped.** All 6 production shims carry a `// Build: clang++ …` line in their headers — but **two name the wrong file**: `catalog_store_fix.cpp` says `-o catalog_ready_fix.dll` and `mainmenu_refresh_pi8.cpp` says `-o mainmenu_refresh_pi2.dll`. Following them literally rebuilds a superseded shim and leaves the production DLL untouched.
- **`configs/shim-status.ps1` monitors 5 of 6.** `battlepass_adopt_fix` — in the default set since S83 — has no row, so a silent PASSES failure reads as all-green. *(Confirmed by direct read this session.)*
- **23 of 25 `tutorial_launch_*.dll` variants on disk predate their own source** — the exact stale-DLL trap that cost most of S99.

---

### 3.3 Front-end menu — **65%**

**LIVE (24 of 44):** login/Steam auth, main-menu nav, party panel, avatar card + callsign (~1.5 s switching), ALL HUNTERS grid (25), hero pick → center refresh, hero 3D preview, STORE featured / supporter / bundles / skins / accessories, COSMETICS browser, CUSTOMIZATION skin switch + persistence, slot cosmetics + titles, MISSIONS page (4 tabs, real progress bars), missions backend engine, PASSES / Hunter's Journey 85-tier ladder, pass progress + match XP, Vive Points wallet, CAREER stats/ranked/history (authentic empties), client-profile "NEW" badges, Discord client connection, admin panel, string tables.

**PARTIAL / DEFECTIVE (13):** store prices (`UNAVAILABLE` — cost comes from packed `CatalogEntry.GetOffers()`, a live probe proved backend `Costs` is inert); Theorycraft Coins (91 wallet keys tested, none moves it); hero-token counter (3 warnings/run, comes from battlepass claim state nothing populates); PASSES reward **claiming** (`TrackIDToClaimableRewards` is served as `{}`); seasonal pass tab (VM builds, tab never appears — driver unknown); region latency (`??? — ms`); emote/title/lobby-platform persistence (the HTTP readback route was **falsified**; `loadout_fix` replays only bundles/slots/chromas — emotes and titles have **no** application path); friends panel (permanently empty); PLAY tiles.

**NEVER OPENED (7):** ARMORY, Leaderboard, News/Announcements, Event Hub, Referral, Capsules/RewardRoll, Top-Up modal.

**Two corrections the verifier made that matter:**

1. **The queue list is diagnostically trimmed and was never restored.** `interactive.go:867` is `var queueIDs = []string{"tutorialNew","training","practice","bots"}` — **four**, not the ten the auditor read out of the comment above it. BATTLE and PRACTICE tiles are therefore **actively degraded right now**, with a documented single-variable fix (serve a high account level so `GetLevelGameFeatureUnlocked` passes, then restore the list).
2. **PLAY→FIND MATCH is far more solved than reported.** Tile latch is live-verified ("BASIC TRAINING now LATCHES, pink border holds"); `POST /startSoloMode` fires; a MatchID is served; the client connects to the stub and travels to `LVL_Tutorial`. The genuinely open piece is narrower and named: **BATTLE/PRACTICE need an AccelByte QoS UDP ping responder** (no `qos` key in ServiceHostnames; client fetches zero QoS endpoints).

> ### ⛔ RETRACTED — S105, 2026-07-27 → **`docs/fk5-battle-gate-settled.md`** (FK-5)
> **Both numbered items above are wrong; original text preserved.**
> **(1)** The trim is real, but its stated fix is not: **no account level is required.**
> `CanControlQueue` loops `GetCurrentQueues` (**×25**), never `GetQueues` (**×0**), so advertising ids
> cannot enter that loop; and its `GetLevelGameFeatureUnlocked` call sits behind
> `PopExecutionFlowIfNot(q.bIsRanked)` with a **hardcoded** `PrimaryAssetId{GameFeature, Ranked}`
> whose result only formats a `level` argument for an error string. Real per-queue restrictions live
> in the `QueueToGameFeature` CDO map: **exactly 3 rows** — `deathmatch`, `customgame`, `custom`.
> Also, **"BATTLE *and PRACTICE*" is half wrong**: `practice` **is** in the served list. PRACTICE is
> not queue-list-blocked — it is blocked at the same `TryStartSoloMode` `Party.State` gate the
> tutorial clears with a live memory poke (`FParty` prop 2 = `FString State` ⇒ offset `0x18`,
> MEASURED from `Binds.Cache`). BATTLE is blocked because `default` is absent ⇒
> `IsQueueAvailable("default")` false ⇒ the Breach tile is `SetVisibility(Collapsed)` — **not drawn**.
> **(2)** *"BATTLE/PRACTICE need an AccelByte QoS UDP ping responder"* is a **false-known**. QoS is
> not on this path at all; the populated machinery is Theorycraft's `ULatencyManager` + UE's ICMP-module
> **UDP echo**, and **no measurer has ever been created** (`LatencyManager.cpp:315`, verbosity
> **Display**, 0 hits in 14 logs; the echo impl `0x1F8CFC0` is a 100 % zero page).
> ⚠ Do **not** substitute a new culprit: what blocks BATTLE *past the tile* is **UNKNOWN** —
> `TryJoinQueue`'s page `0x5875000` is 100 % zero in every dump. **★ The settling experiment costs
> zero backend change**: `bots` is already served and is **not** special, so BOTS → FIND MATCH
> dispatches into the real `TryJoinQueue` today.

**Blast radius if a shim fails:** roster + store + cosmetics (catalog_store_fix), pick-commit (catalog_pick_fix), center portrait (pi8), skin persistence (loadout_fix), missions page (missions_fix), passes tier grid (battlepass_adopt_fix). **Five of six of these cannot currently be co-validated in one launch**, because the full set crashes.

**Also true and uncomfortable:** every live client log from 2026-07-26 is a *tutorial* run with **no front-end shims injected** (`catalog-store-fix-marker.txt` is frozen at 2026-07-20). The front end has had **zero code changes in 18 commits / 5 days**. Every "LIVE" claim above is confirmed against the record, not against a running game.

---

### 3.4 Content catalog / IoStore extraction — **55%**

| Layer | Coverage | Detail |
|---|---|---|
| Path enumeration | **100%** | 107,123 pak entries in `allfiles.txt` |
| Structural decode | **80.6%** of packages | 68,301 JSON dumps = 88.1% of unique `.uasset`; **0 of 7,300 `.umap`** |
| Semantic decode | **~35%** | see below |
| Runtime addressability | **~65%** (capability), ~8 paths in actual use | four independent resolution mechanisms exist |

**What we KNOW:** the paks are unencrypted (`EncryptionKeyGuid = 0`), mount keyless, and the catalog physically exists — **68,301 files, 0.73 GB, 43 categories**, matching `game-map.md` for 41 of 42. 25 hero codenames, 353 cosmetic bundles with hero+skin resolved, 233 avatars with real texture paths, 64 StringTables fully decoded (1,780 keys), 56 StoreOffers, 346 missions. The usmap pipeline works (11,347 UStructs, 43,296 properties). `bpdump` — offline Blueprint bytecode — has driven several breakthroughs and has 198 output artifacts.

**What we DON'T:**

- **0 of 7,300 level packages.** No geometry, no actor placement, no spawn points, no POI coordinates. `SkylandsBreach` alone is 2,723 `.umap`. Exactly one map has ever been dumped (`LVL_Tutorial.json`).
- **9,259 unique `.uasset` outside the catalog**, 5,836 of them `BP_*` gameplay Blueprints — plus 159 `MPC_`, 137 `PHYS_`, **60 `CT_` curve tables**, 54 `ControlRig_`, 34 behavior trees. *(Confirmed: 60 `CT_*.uasset` in the pak, no `catalog/ct` category.)* `game-map.md`'s explanation that the gap is "duplicate-basename overwrites" is wrong by an order of magnitude — duplicates account for 722.
- **The index CSVs are semantically hollow.** Every `display` column that exists is **0% populated** (0/2429 GameplayEffects, 0/659 titles, 0/494 data assets); `items_index.csv` has *every* non-id column blank for all 481 rows. Root-caused by the verifier: `index_catalog.go:194` runs every extractor against `dump[0]`, which for BP-backed categories is the class wrapper with no Properties block. **One indexer bug, ~10 symptom gaps** — except for titles, where the cooked FText is genuinely blank and only locres can recover it.
- **The catalog is git-ignored.** `git ls-files tools/extractor/out` = **0**. 0.73 GB and ~2 hours of pipeline exist on one disk.
- **Zero binary asset export.** JSON only — no pixels, no audio samples, no vertices. 13,089 textures and 8,716 audio events are metadata shells.
- **12 shipped locres languages, none extracted.** `en/Game.locres` is very likely the fix for 912 unnamed cosmetics and several unnamed heroes.
- **The AssetRegistry is an unexploited offline oracle.** It parses 103,841 `FAssetData` entries and **already carries the real runtime `PrimaryAssetName`** — `BP_StoreOffer_100VivePoints → vp100`, `BP_StoreOffer_1000TheorycraftCoins → tp1000`. That is exactly the mapping `menu.go` says had to be recovered by live RPM. Divergence measured offline: StoreOffer **136/136**, missions **617/693**. Nobody has ever materialized the obvious 103,841-row table.
- **The AR *deployment* route is moot**, not merely blocked. `supervive-hero-roster-blocker.md:909-919` established the live `UAssetRegistryImpl` map already holds **Num = 103,841** — the client loads the full, correctly-tagged registry. Patching the file on disk cannot add information the client already has. Every downstream deployment gap (loose-file, mod-pak, signing bypass, IoStore overlay) is downstream of a dead route.

---

### 3.5 Game systems & design — **37%**

This is the "do we know what the game *is*" question, and it is the weakest layer relative to how much it matters.

| Area | Coverage | What "mapped" means here |
|---|---|---|
| Heroes | ~40% | 25 enumerated, 16 display names, full art pipeline indexed — **0 stat sheets, 0 ability slot assignments** |
| Abilities / GAS | ~35% | 663 UFunctions dumped with live thunks; **0 abilities ever granted or activated**; ability abstraction is `GameplaySpell` (596), not `GameplayAbility` (9) |
| Items / economy | ~35% | 481 items taxonomized by prefix; **0 display names, 0 prices, 0 stats**; rarity ladder + currency naming fully decoded |
| Maps / levels | ~25% | 23 map dirs, 91 `LVL_*`, 32 biomes, **34 named POIs with mechanic descriptions** — 0 geometry, 3 maps ever loaded |
| Match rules | ~45% | 3 state enums fully decoded, 43 game-mode classes, 40 queues named — **0 numeric values for any rule** |
| Missions / progression | ~60% | 330 missions, 16 pools, 85-tier XP ladder verified against the client — **17 of 85 objective rules; 0/330 objective names decode offline** |
| Audio / localization | ~30% | 8,716 events + 1,780 string keys indexed — **0 bytes of audio, 0 of 12 languages extracted** |

**The pattern is stark:** the *identity* layer is ~85% mapped and the *tuning* layer is ~5%. We can name every hero, queue, POI, biome and mission; we cannot state one hero's health, one ability's damage, one item's cost, or one circle's shrink time.

**Highest-value single unlock in this domain:** the **60 `CT_*` curve tables** (43 of them per-hero `CT_<Hero>Attributes`, plus `CT_LokiCharacterAttributes`, `CT_PrimaryAttackSpeeds`, `CT_Equipment_Attributes_V2`). These are almost certainly the actual balance data, they sit in the pak, and they are plain data assets rather than BP CDOs — so they should extract cleanly *even before* the CDO bug is fixed.

**Also unexploited and free:** `Loki/Config/*.ini` — 10 plain-text files in the pak including `DefaultGameplayTags.ini` (the authoritative tag tree, currently reconstructed the hard way by regexing 3,252 cue assets) and `DefaultInput.ini`. No usmap, no CUE4Parse, nothing. Never read.

---

### 3.6 Playable route (client-side tutorial force-open) — **53%**

**Capability ledger — current truth:**

| Capability | State | Settled by |
|---|---|---|
| World loads (`LVL_Tutorial` force-open) | **PROVEN** | S62/S65 |
| Real gamemode + gamestate (not stubs) | **PROVEN** | S63/S65 |
| Initializer Stage 0→3 Finished | **PROVEN** | S65/S66 |
| Round-phase progression (`GoToPhase`) | **PROVEN** | S74 |
| Hero spawn (`BP_HERO_Ronin_C`) | **PROVEN** | S74 |
| Possession | **PROVEN** (does not reliably *hold*) | S74 / S99b guard |
| Hero VISIBILITY | **PROVEN** — root cause was zero/flattened `Scale3D` | **S98** |
| Idle animation | **PROVEN** (3 independent live witnesses) | S99b |
| Run animation | **PARTIAL** (one call-succeeded log) | S99b |
| WASD movement | **PARTIAL** — velocity puppet works. ⚠ "stock input path dead" **RETRACTED S104**: never tested with a validated instrument (S75's forced `AddMovementInput` and its `ControlInputVector` sample never co-occurred, and the offsets are unvalidated). 186 actions + 16 axes exist on disk — `docs/fk2-input-settled.md`, `docs/input-map.csv` | S75 / S104 |
| Top-down camera | **PROVEN** (must re-assert each frame) | S93 |
| Weapon / sword | **PARTIAL** — no socket needed; pose is the fix | S99 |
| Objective completion | **PARTIAL** — synthetic (field poke + ungated `OnRep`) | S93 |
| Lesson chain | **PARTIAL** — **5 of 30** driven | S93 |
| Exit to menu | **PROVEN** | — |
| Abilities / GAS | **OPEN** — 0 granted, gate located | **S102** |
| Combat / damage | **OPEN** — never attempted | — |
| Enemies / minions | **OPEN** — record self-contradictory, unmeasured since S68 | — |
| Items / pickups | **OPEN** | — |
| Tutorial completion | **OPEN** — never reached | — |
| Drop-in / DropPlane | **FALSIFIED as reachable** — `SpawnPlane` faults on absent level markers | S93 |
| Stability | **PARTIAL** — `RM_PLAY` holds 10 min; **~2 of 3 launches die on the first shim** | S99b |

> ⚠ **RETRACTED 2026-07-27 (S106) — "~2 of 3 launches die on the first shim" is FALSE as a mechanism.**
> The row above is preserved as written. The crashes are **deterministic, not stochastic**: 68% of
> chained crashes in the 86-dump corpus are exact repeats of another crash, and all 10 crashes in the
> FK-7 window fall in a 28-second band (173–201 s) across just **two** stack families — a worker-thread
> animation use-after-free and a GameThread camera-pointer corruption. Both are shim-caused and both
> have compiled fixes. **Also corrected:** the crash corpus explains **at most half** the observed
> failure rate — 5 of 9 tutorial sessions died with no crash dump at all (a separate, still-open
> failure mode). Do not "budget retries"; stack the experiments. → **`docs/fk7-crash-settled.md`**

**The current frontier is one field.** S102 (`f6a7985`, HEAD) disassembled `TryUpdateAbilitySystem`, **falsified** the RPC-dispatch-stub theory (the `+0xE0` thunk is a textbook exec-thunk tail-jumping to `0x56CE5F0`; `ServerSetHeroClass` does not even have `FUNC_Net` set), and located the real gate: an embedded interface subobject at `PlayerState+0x470` whose accessor (`0x56BA9E0`) reads **`PlayerState+0x4F8`, measured live as NULL**, returning `[that+0x3E8]` — which is the ASC offset on the `LokiPlayerState_HeroAffiliated` CDO.

**The single most actionable finding across all eleven audits:** the DS route **already solved this**, and nobody has ported it. Commits `349c250 / 0f9ac7b / 5b13f81 / 6a7bbda` (Jul 16–17) established that spawning the carrier client-side **crashes the process**, then solved the problem *without* the carrier by borrowing the CDO's default subobjects into the hero's three storage slots (`+0xF00/+0xF08/+0xF10`) and writing the attribute block directly. That code is live in `ds_hybrid.cpp:2370-2430` with named offsets, and it was **live-proven**: `GetMaxSpeed()` 0 → 500, `GetMaxAcceleration()` 0 → 50000, and the hero physically translated through the world **via the stock engine chain** (`AddMovementInput → ControlInputVector → CMC → CalcVelocity`).

Force-open has what the DS run lacked (standalone authority, a 10-minute hold, a visible animated hero). The DS run has what force-open lacks (a working GAS recipe). **Nobody has combined them.**

---

### 3.7 Dedicated server / netcode — **57%**

Parked as a strategy, but the water mark is much higher than "parked" suggests.

| Sub-area | Coverage |
|---|---|
| Transport / handshake framing | ~100% — every wrapper byte decoded, live handshake completes |
| Control channel / login / travel / WP visibility | ~95% |
| Property replication schema | ~70% (complete for the 16 tiers on the join path; the *general solver* exists) |
| RPC layer | ~45% — index space 100% aligned (83 net functions), but **only 5 of 83 carry real parameter signatures** |
| Subobject content-block framing | ~65% — header solved empirically (11 bits); payload is a proven fixed-offset wall; **the RPC route bypasses it and reads cleanly** |
| Server-side game model | **~5–8%** |
| DS-route world reveal | ~80% — `ds_hybrid MODE_SPECTATOR_CAM` collapses the overlay, user-confirmed |

**Proven:** custom UDP framing, network-version override, `AActor` differs from stock by exactly **one** replicated property (`ServerState`), a 43-property `ALokiGameState` mirror that live-verifies, login→join→**server-authoritative possession** of a Loki-typed character holding 3+ minutes, `ServerVerifyViewTarget`'s 40-parameter / 2,298-bit signature, and the reusable **by-path NetGUID class-binding trick** (naming the stub module `Loki` makes `/Script/Loki.LokiGameState` bind to the client's own native class — no mod-pak needed).

**The blocking wall is an artifact, not a technique:** there is no SUPERVIVE **Server-target binary**. `IsRunningDedicatedServer()` is `FORCEINLINE` over compile-time literals, folding to constant `false` at hundreds of inlined sites — so the client build cannot be coerced. That is an *acquisition* question, not an engineering one.

**Structural ceiling worth recording:** `ALokiMinionCharacter` is the only possessable mirror, because `LokiCharacter` and `LokiHeroCharacter` are both `CLASS_Abstract` and the real playable classes are Blueprints the stub cannot instantiate. And the DS route can **never** complete a tutorial objective (`OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`).

---

### 3.8 Binary RE — **20%**

| Metric | Value |
|---|---|
| Distinct `.text` RVAs known anywhere | **617** |
| — with any name attached | ~254 |
| — declared as callable constants in shim/probe source | **31** |
| Estimated function entry points in the exe | **~120,000+** (59,095 high-confidence in just the decrypted 48%) |
| **Static map coverage** | **~0.5%** |
| Struct field offsets recorded | 736 pairs / 382 owners; ~18 classes substantially mapped |
| Reflected types ever mentioned anywhere | **488 of 11,344 (4.3%)**; Loki-prefixed **102 of 825 (12.4%)** |
| Named UFunction→thunk pairs recorded in docs | **1,057** — but with **no module base recorded**, so none convert to RVAs |
| `.pdata` (unwind/function table) | **0 of 6,283,264 bytes** readable in memory; encrypted garbage on disk |
| Ghidra | 1 program (`SUPERVIVE-deobf.exe`), 2.1 GB, **0 recovered symbol names**, untracked |

**Defeated:** the import protection (⚠ NOT VMProtect — REFUTED, `docs/fk10-protector-identified.md`) — `deobfimports` emulates each obfuscated trampoline against the live process and rebuilds a real import table, **1,107/1,107 slots, 0 off-target**, independently confirmed by parsing the output PE.

**Worked around, not defeated:** the ~3–5 minute code-integrity check (dodged by never leaving a standing `.text` patch), the packer's VEH (no C++ exceptions in payloads), CIG (manual mapping).

**Two facts that reframe this domain:**

1. **The merged cold dump is stale, and the fix is one command.** `merged.dump.exe` was built 2026-07-17 15:46 from five dumps captured 15:22–15:26 *the same afternoon* — five near-identical **menu** substates. The genuinely different states (`toggles` = in-match, `vmbuild`, `accountpass`) were captured later and **never merged**. Measured by the verifier: merging them adds **2,044,822 new `.text` bytes**, lifting union 48.05% → 49.70%. The auditor's headline conclusion — "the multi-state strategy is falsified, the ceiling is structural" — is wrong; the strategy was simply never executed. *(Confirmed: 9 dump dirs on disk, merged output dated Jul 17.)*
2. **`.rdata` union is capped at 63.12% and IS structural** — 0 new bytes from any later state. ~13.9 MB of vtables, RTTI and string literals are permanently unreadable by RPM, which genuinely caps the vtable-dump and string-xref techniques.

> ## ❌ RETRACTED — S104, 2026-07-26 → **`docs/fk3-fk4-settled.md`**
> **Point 2 immediately above is FALSE (certain).** It is false-known **FK-3**. `.rdata` is
> **99.64% readable** — measured independently twice: **33 of 9,085** 4 KiB pages are entirely
> zero. The "63.12%" counts **non-zero BYTES**, so vtable null slots and string padding read as
> gaps; this file's own source manifest carries that disclaimer, and all nine
> `dumps/*/…dump.txt` manifests report `.rdata … (100.0%) READABLE`. The metric is sound for
> `.text` (48.05% non-zero vs 52.29% readable — they agree, because demand-decrypt zeroes whole
> pages) and meaningless for `.rdata`. The "~13.9 MB permanently unreadable" is null padding.
>
> **Both retired techniques are alive.** String-xref: 517,515 `.text` LEAs → 106,800 distinct
> `.rdata` targets; **55,473 of 85,677 UTF-16 strings resolved (64.7%)**. Vtable dumping:
> **3,599 named vtables, 5,061 / 5,077 classes**, validated 8/8 against a live June capture.
> Combined symbol yield: **32,066 reflection RVAs + 3,599 vtables**, offline, no running game.
>
> ⚠ **The retraction does NOT mean "no limit."** The real cap is **`.text` demand-decrypt at
> 52.29%** (14,448 of 30,281 pages zero) — and unlike the claimed one it is **not structural**:
> it is monotone in what the game has executed. **34.89% of `.text` (41 MB) has never been
> decrypted in any process we hold a record of.** Lifting it needs a capture from a runtime
> state, not more offline work — see §8 of the new doc for the priced plan (one in-match dump ≈
> **+3,430 pages**, 5.7× the gain from re-merging all nine existing dumps).
>
> Two clauses of point 2 DO survive: **RTTI is effectively stripped** (0 UE classes carry a type
> descriptor — the 691 `.?AV`/`.?AU` names in `.data` are third-party EH residue, e.g.
> `UObject@icu_64`), and the in-image **`.pdata` is 100% zero**. Their real consequences, and the
> recovery of 382,282 exact function bounds from crash-minidump stream 13, are in §3 of the new doc.

**Anti-knowledge — never touched:** the renderer beyond a handful of offsets, audio, physics/Chaos, the animation runtime, the client-side matchmaking state machine, the packer's own code, and `runtime.dll` (67 MB, characterized as packed but never disassembled).

---

### 3.9 Tooling — **72%**

**Instruments we have (better than the docs claim):** `usmapdump` (Go, **20** subcommands — not C#), the .NET/CUE4Parse extractor (**9** subcommands + default), **99 Python RPM probes**, a manual-mapper injector (7 modes), 6 orchestration PowerShell scripts, a loopback admin panel (11 routes), a self-rotating capture log that doubles as a protocol-discovery engine.

Three instruments deserve special mention because **no summary document names them**:

- **A live Blueprint bytecode disassembler** (`ubergraph_dump.py`, 53 opcodes, announces unknown opcodes loudly) plus an offline twin (`extractor bpdump`).
- **A live game-thread sampling profiler** (`gt_sampler.py` + `sample_analyze.py` + `gt_stall.py`) — this is what overturned the "client disconnects after 2 min" claim.
- **A one-pass GAS state inspector** (`gas_recon.py`) with a built-in control (section F samples a healthy reference ASC).

**What's missing / broken:**

- **No shared library.** 75 of 87 probes re-implement `ReadProcessMemory` and restate this build's non-standard `UObject` offsets. **Zero `.h` files** across 63 shims. *(Mitigating: I checked — the duplicated RVA constants have **not** diverged. `kPiRva` is `0x13454A0` in all 34, `GUObjectArray` `0x9E38930` in all 41. This is preventive maintenance, not a live bug.)*
- **16 probes hardcode a fixed ASLR base across four different values** — silent-garbage hazard in the *real* instruments.
- **Three documented `usmapdump` subcommands do not exist** (`threads`, `findgametid`, `assetmgr`) — and `docs/hero-roster-attempts.md` cites `findgametid` as a reproduction step. One documented extractor subcommand (`raw`) doesn't exist either, while three real ones (`wherefile`, `mkpak`, `peekpak`) are documented nowhere.
- **Zero tests anywhere in `tools/`.** All 40 tests in the repo are backend Go. The toolchain that produces every ground truth the project reasons from has no coverage — in a project with **146 recorded retractions**, at least one of which (S95/S97) was itself a measurement-method error.
- **Missing instruments, ranked by what they'd unlock:** a live object-graph browser (the compensating behavior — ever-larger single-shot mega-probes — is visible in `gas_recon.py`'s own header); a widget/view-model tree dumper (the S83 keystone bug was a VM **map-key mismatch**, exactly what a binding dumper finds in one shot); a shim regression suite; automated visual verification; a symbol database; a cross-layer log correlator.

---

### 3.10 Knowledge-base integrity — **72%**

**The strongest asset in the project.** 38 of 364 commit subjects (10.4%) explicitly retract, overturn, falsify or correct an earlier claim, usually self-attributed. The project maintains its own fake-wall tally (`8 investigated walls → 8 measurement errors, 0 real`) and codifies the rule: *question your own tools before calling a wall definitive.* Append-in-place supersession banners are used (`⚠⚠ S96 CORRECTIONS — read before trusting the S95 block above`). Commit bodies average ~1,973 characters and are frequently the most complete account that exists.

**The weakness is the navigation layer, not the reasoning layer.**

- **CLAUDE.md is 17 sessions behind** (highest reference: **S85**; HEAD is S102). *(Confirmed this session.)*
- **Its flagship pointer is poisoned.** CLAUDE.md names `docs/hero-roster-attempts.md` as the roster/store "Living log." That file was last committed **2026-06-28** — five days *before* the solve — contains **zero** occurrences of `0x354`, `CatMgr`, `catalog_store_fix` or `SOLVED`, still lists ALL HUNTERS / STORE / COSMETICS / MISSIONS as **blocked**, still asserts the falsified LokiAssetManager root cause, and **recommends a `ScanPrimaryAssetTypesFromConfig` shim that CLAUDE.md's own "What NOT to do" explicitly bans.** *(All confirmed by direct read this session.)*
- **`MEMORY.md` — the auto-loaded index — has degenerated into a 16 KB second copy** of the topic files, is 8 sessions behind on the tutorial entry, and its cheat-surface bullet presents a **definitively closed route as a live lead**.
- **`README.md` is 43 sessions behind** and teaches two retracted models (mutually-exclusive PI hooks; "the tutorial isn't playable — no hero").
- **`docs/dedicated-server-stub.md`** — the largest prose doc at 252 KB — stops at S39/S40, ~50 sessions behind the route's end state.
- **50.8% of `docs/` files (97.8% of its bytes) are regenerable runtime junk** — 111 `.log`, 60 markers, 12 crash dumps. The two largest tracked files in the repo are a **64 MB** and a **20 MB** raw launcher stdout log.
- **No session index exists**; 28+ session numbers have no dedicated file.

---

### 3.11 Operational reproducibility — **65%**

**Reproducible:** the Go backend (zero external modules, 40 passing tests, built by the launcher itself), the launch pipeline (every external assumption is explicit in script text), TLS chain generation (self-contained; the cacert re-append **is** automated on the full-launch path via a pristine `.supervive-bak`), the capture-dump pipeline (enforces its own ImageBase constraint).

**Not reproducible:**

- **0 of 135 shim DLLs are in git** (`*.dll` in `.gitignore`) and there is **no build script**. Recoverable — the build lines are in the headers — but two of six point at the wrong output file.
- **956 KB / 19 memory files live entirely outside version control** and outside any backup. This includes the three largest knowledge artifacts in the project (229 KB DS, 208 KB roster, 170 KB tutorial). `README.md:43` links `memory/…` as if it were in-repo — a broken link that *hides* the gap.
- **~19 GB of single-copy anchors:** the 15 GB game backup (a delisted title — re-acquisition is not obviously possible), `dumps/` (2.1 GB), `Ghidra/` (2.1 GB, holding every manual rename and struct definition).
- **No build fingerprint.** All 179 RVAs are valid only against the 2025-12-17 / changelist-156430 exe. The build string appears in prose in exactly two places; **no hash of the exe or paks is recorded anywhere**, and no shim carries a version guard.
- **`-NoPasses` is silently dropped on self-elevation.** Declared at `launch-redirect.ps1:66`, honored at :127, **not forwarded** in the elevation block at :93-106 (which forwards 8 other switches). Anyone running it from a non-elevated shell gets the passes shim injected anyway — defeating the exact bisection the flag exists for. *(Confirmed by direct read.)*
- **Two divergent `interactive.json` files.** `state/interactive.json` (tracked, 546 B, Jul 4) is a fossil; `server/state/interactive.json` (git-ignored, 48 KB) is live. Restoring "the state file" from git would silently roll the account back three weeks.
- **`store.load()` swallows its unmarshal error** — a corrupt or shape-changed file yields an empty store and the next write overwrites it. No schema version, no migration, no backup rotation.
- **A private TLS key is committed** to a GitHub-remoted repo (low practical risk — regenerated every launch — but it means the history is a stream of keys).

---

## 4. The Three Tiers: Cataloged vs Understood vs Controllable

This is the distinction that explains why "68,228 assets indexed" and "the game is barely mapped" are both true.

### Tier 1 — CATALOGED (we have the bytes)

| Artifact | Count | Coverage |
|---|---|---|
| Pak entries enumerated | 107,123 | **100%** |
| Asset JSON dumps | 68,301 | 88% of `.uasset`, **0% of `.umap`** |
| AssetRegistry `FAssetData` parsed | 103,841 | 100% (but **0** DependsNode, **0** PackageData) |
| Reflected types / properties / enums | 11,347 / 43,296 / 2,226 | 100% enumerable |
| Audio events indexed | 8,716 | 100% by name, **0 bytes of audio** |
| String-table keys | 1,780 | 100% (English only; 12 locres languages untouched) |
| Named UFunction thunks recorded | 1,057 | recorded, **unusable** (no base) |

### Tier 2 — UNDERSTOOD (we know what it means)

| Thing | Understood | Total | % |
|---|---|---|---|
| Reflected types ever examined | 488 | 11,344 | **4.3%** |
| Loki-prefixed types examined | 102 | 825 | **12.4%** |
| Item display names | 0 | 481 | **0%** |
| GameplayEffects with Modifiers decoded | 4 | 2,429 | **0.2%** |
| Per-hero curve tables extracted | 0 | 60 | **0%** |
| Hero pawn CDOs with ability slots read | 0 | 25 | **0%** |
| Mission objective names decodable offline | 0 | 330 | **0%** |
| Match-stat → objective rules | 17 | 85 | **20%** |
| Net UFunctions with real signatures | 5 | 83 | **6%** |
| Code addresses with a name | ~254 | ~120,000 | **~0.2%** |
| Numeric values for any match rule | 0 | — | **0%** |

### Tier 3 — CONTROLLABLE (we can make the game do it)

| Capability | State |
|---|---|
| Menu surfaces we can drive | 24 of 44 |
| Production shims | 6 of 63 sources |
| `/Game/` asset paths resolved at runtime | **8** |
| Heroes selectable in menu | 25 |
| Heroes rendered in-world | **1** (Ronin) |
| Abilities ever granted | **0** |
| Damage ever dealt | **0** |
| Maps ever loaded | **3** of 91 (`LVL_Login`, `LVL_LobbyV2_Persistent`, `LVL_Tutorial`) |
| Tutorial lessons driven | **5** of 30 |
| Match results ever POSTed | **0** |

### What the tiers tell you

**Tier 1 → Tier 2 is where the project is stuck, and it is stuck for a mechanical reason, not a conceptual one.** The catalog contains the bytes for hero stats, ability numbers, item values and match rules — they simply are not being *serialized*, because the extractor drops BP CDO default overrides and the indexer reads the wrong object. Two bugs stand between "we have 68,301 files" and "we know what the game does."

**Tier 2 → Tier 3 has a different shape.** Everything we understand well, we can control — the correlation is near-perfect. Roster, store, missions, passes, avatars all went from understood to controllable within one or two sessions of the root cause being found. There is **no evidence of a control barrier**; there is only a comprehension barrier.

**Corollary:** effort spent on Tier 1 (extracting more bytes) has near-zero marginal value — we already have 100% of the paths and 88% of the assets. Effort spent on Tier 2 (making the bytes mean something) converts almost directly into Tier 3.

---

## 5. Biggest Blind Spots, Ranked

**1. The in-match simulation layer (abilities, combat, damage, items, enemies).**
0 abilities ever granted. 0 damage ever dealt. All three hero GAS storage fields NULL. The carrier (`LokiPlayerState_HeroAffiliated`) does not exist in-session and spawning it client-side is a **live-proven crash**. This gates 25 of 30 tutorial lessons, every hero-mission objective, the entire item system, and any notion of "playing." *Mitigating: the gate is now a single measured field (`PlayerState+0x4F8 == NULL`), and a working workaround exists on the sibling route.*

**2. Levels and world data — 0 of 7,300 `.umap`.**
No geometry, no spawn points, no POI coordinates, no streaming layout. 1 of 91 `LVL_*` ever force-opened; the BR world (`Skylands_WP`, 2,216 packages) has never been loaded. This is the layer the DropPlane descent faults against and the reason "playable map" means "the one tutorial map."

**3. The extractor's CDO-default blindness — one bug, seven gaps.**
Documented since S61 and never generalized. Blocks hero ability slots, GE modifiers/durations, game-mode tuning, item stats, mission objectives, Armory tables, and 9 hero identity records. Every one of these is currently filed as an independent extraction chore.

**4. Match lifecycle and result reporting.**
Nothing POSTs a match result. No capture of a real match session exists (the newest capture *is* an in-tutorial run — and informatively, it emitted **zero new endpoints**). The 9 catch-all Career endpoints have no model. Missions and pass XP both have working engines with no gameplay input.

**5. Reproducibility single points of failure.**
956 KB of memory outside git; ~19 GB of single-copy anchors (game backup, dumps, Ghidra project); 0 shim DLLs in git with 2 of 6 build lines wrong; no build fingerprint for the exe every offset depends on.

**6. Knowledge-navigation staleness.**
CLAUDE.md 17 sessions behind and pointing at a doc that asserts a falsified root cause *and* a banned plan. MEMORY.md presenting a closed route as a live lead. README 43 sessions behind. The reasoning record is trustworthy; the map to it is not.

**7. The verification vacuum.**
The default 6-shim launch is recorded as **crashing** (S85, with PID-level controls) and has never been re-tested — 17 sessions later, with CLAUDE.md still presenting it as the recommended path. 0 tests in `tools/`. No visual regression. Marker `READY` proves a shim *ran*, not that a surface *works*. Five of six shim-dependent surfaces cannot currently be co-validated.

**8. Binary static map + a stale merged dump.**
~0.5% of functions named. No `.pdata`, so Ghidra recovers every boundary heuristically. **2 MB of gameplay `.text` is sitting on disk unmerged.** 1,057 recorded name→thunk pairs are unusable because no probe prints the module base.

**9. The party/queue write surface and the lobby protocol.**
6 of ~33 party operations, ~~4 of 16 lobby message types, server→client push measured non-functional~~ (**both RETRACTED S117 — 4 of 43, and push is MEASURED WORKING; see `docs/fk15-ws-push-audit.md`**), messenger binary framing unknown beyond a 2-byte token. Plus a diagnostic queue trim that was never reverted, actively degrading the BATTLE and PRACTICE tabs today.

**10. Egress outside the redirect.**
The endpoint census can structurally only see traffic that arrives at our mux. Two live outbound hosts are proven (Vivox, Sentry) and one of them appears nowhere in the repo as an outbound endpoint. We do not know what else the client talks to.

---

## 6. The "Do Not Re-Open" Register

Claims that were asserted, then **falsified or overturned by later measurement**. Later sources win. Re-opening any of these has already cost the project sessions.

### Roster / store / catalog family

| Retracted claim | Current truth |
|---|---|
| "Empty grid = LokiAssetManager enumeration / asset-resolution failure" (~13 sessions) | One un-set client flag `CatMgr+0x354` gated the grid builder. 30 types *are* registered live. |
| "Server-trigger hypothesis" (S45) · "IsHidden hypothesis" (S47) · "grid doesn't use GetHeroAssetFromPrimaryAssetId" (S46) | All falsified in S45/S47. |
| "The baked AssetRegistry mis-tags heroes" | The baked AR already tags them correctly (`PrimaryAssetType=Hero` on all 25). |
| "Prices come from the backend" | Cost is client-side via `CatalogEntry.GetOffers()`; a live probe sending Costs was **inert**. |
| "Loose-file `AR.bin` deployment works" | Proven **INERT** — the pak shadows it (confirmed by a 0xDEADBEEF truncate kill-test). |
| "Patching the AR would help" | **Moot.** The live `UAssetRegistryImpl` map already holds all 103,841 correctly-tagged entries. |
| "`assetregistry classes` proves the parser is broken / Mission canary FAILS" (S80l) | The query heuristic filters on `AssetClass`; the data lives in the `PrimaryAssetType` **tag** (Mission=660). Parser is fine. |

### Native-call / injection family

| Retracted claim | Current truth |
|---|---|
| "`ProcessEvent` (vtable slot 56) is the BP invoke path" | Uniform **no-op** for injected calls. Dispatch is `ProcessInternal` direct. |
| "OUT-param crashes are anti-tamper" | A bug. `FFrame.OutParms` is at `+0x80` (S58). |
| "The deploy-context wall" | **Retracted 2026-07-16** — never existed; BP deploy functions never ran because ProcessEvent is neutered. |
| "The IAT holds resolved system-DLL pointers" | Wrong — it is import-protected, hence `deobfimports`. ⚠ The "VMProtect" label is REFUTED (`docs/fk10-protector-identified.md`). |
| "FName indices are stable across launches" | **Not stable.** |
| "The usmap is authoritative for replicated containers" | Wrong repeatedly (`ObjectiveProgress`, `Missions`, `GameFeatureToggles`). Verify against live RPM. |
| "`ScanPrimaryAssetTypesFromConfig` is a viable shim target" | `__report_gsfailure`s regardless of thread context — tested 4 ways. **Banned.** |
| "C++ exception-using payloads can work" | 3 canaries; the packer's VEH kills the process regardless. **Banned.** |

### DS / tutorial / hero family

| Retracted claim | Current truth |
|---|---|
| "The client must use a stock PlayerController" | Overturned by the by-path NetGUID technique (S70). |
| "The client disconnects ~2 min after every join" | **False.** A clean session held 17+ min; the drop is caused by MODE_PLAYABLE's per-frame movement blocking the CMC tick. |
| "S68: four spawn methods failed, the route has a ceiling" | Overturned — S74 spawn+possess works. |
| "The hero has no spring arm" (S79) | Wrong — `TargetArmLength` was already 3020. |
| "SUPERVIVE uses Enhanced Input mapping contexts / the missing IMC is the gap" | **Retracted 4×.** Custom Loki input system, legacy FName events, WASD is an **axis**. |
| "A visible hero needs the dedicated-server binary" | Overturned S93 — `AddComponentByClass` + `SetSkeletalMeshAsset`. |
| "Everything we spawn is invisible to the renderer / `+0x2B0` == SceneProxy" (S95) | **Retracted S97** — 12 offsets non-null on 400/400 including ours. |
| "`FinishSpawningActor` silently fails" (S95) | **Falsified S96** by live logging (non-null return). |
| "Every hypothesis for the invisible hero is eliminated; no remaining lever" (S97) | **Broken one commit later (S98)** — root cause was zero/flattened `Scale3D`. |
| "The S90 loading-screen regression" | Falsified by a 7-config bisection. No regression; the exe is unchanged. The reveal was always the shim hiding `WBP_UI_MatchTransition`. |
| "GAS cannot be initialised outside deploy" | **Dead.** 424 live ASCs in the world, 344 with `InitAbilityActorInfo` run, in level actors, with no server. |
| "The cheat surface is a shortcut to a playable hero" | **Closed 3× independently** — bodies compiled out (`xor al,al; ret`), no live instance. ⚠ MEMORY.md still presents this as a live lead. |
| "Run the real exe as a dedicated server" | **Closed.** `IsRunningDedicatedServer()` folds to a compile-time constant at hundreds of inlined sites. |
| "The DS route can deliver a completable tutorial" | **Structurally impossible** — `OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly`. |

### Passes / customization / avatar family

| Retracted claim | Current truth |
|---|---|
| "The backend route for the battlepass is exhausted" | **Falsified 3/3.** The native ingester `0x585A570` exists; progress is now served purely from the backend. |
| "`byte[PM+0x388]` (Gate C) gates the populate" | **Never a gate**, and poking it is **harmful** (it is `TOptional::bIsSet` and arms a destructor over raw zeros). |
| "`P = S[+0x238]`" | Red herring — `S` *is* `HuntersJourney_C`. |
| "`Levels` is `TArray<PrimaryAssetId>`" | Wrong — `TArray<UObject*>`. Never force-call the populate `0x57DF4B0` (it constructs objects — the S82 crash). |
| "Skin-switch failure is ownership / empty-member" | Both falsified live (all 1,340 entries `CanUse=1`). |
| "The HTTP loadout readback repopulates the client" | **Falsified 2026-07-08** across three envelope shapes. Persistence is client-side replay via `loadout_fix`. |
| "No backend lever exists for avatar latency" | Wrong — it only ruled out a WS push. The lever is dropping the `/notifications` socket. |

### Corrections made *by this audit's verifiers*

| Auditor claim | Verifier correction |
|---|---|
| "Multi-state dumping is falsified; the .text ceiling is structural" | **False.** The merge only ever ran on five same-afternoon menu states. Adding the later dumps yields **+2,044,822 bytes**. One command. |
| "There is no mechanism for continuous game-thread execution without a .text patch" | **False.** S78 **shipped** the heap vtable-pointer swap — ~720 ticks/sec for 15 min, zero crashes, does not trip the integrity check. |
| "The GAS gate has never been read" | **False as of S102** — the gate is `PlayerState+0x4F8 == NULL`, measured live. |
| "Where attribute values come from is unknown" | `K2_InitStats(Class, DataTable*)` was identified in S100b; and the DS route already wrote the attribute block directly and moved the hero. |
| "Zero of 25 `BP_HERO_*` extracted" | One is (`bpdump_BP_HERO_Ronin_PROPS.txt`) — and it proves the CDO bug, since the ability slots come back empty. |
| "S96's findings exist in no docs file" | **False** — `next-session-prompt-s95.md` carries a full `⚠⚠ S96 CORRECTIONS` block plus the S97 retraction. |
| "The catalog JSON has no package path" | **False** — every dump carries `ClassDefaultObject.ObjectPath`. |
| "The shim build method is documented only by a stray error log" | **False** — all 6 production shims carry `// Build: clang++ …` headers (2 name the wrong output file). |
| "There is no launch ledger" | `docs/inject-secondaries.log` is one — tracked, timestamped, per-DLL results. It records injection, not outcome, and is overwritten each launch. |

---

## 7. Contradictions & Stale Knowledge To Fix

Ordered by how likely each is to cost a future session.

1. **CLAUDE.md → `docs/hero-roster-attempts.md`.** The "Living log" for the solved roster/store system asserts the falsified root cause, lists all six surfaces as blocked, and recommends a plan CLAUDE.md itself bans. **Fix: dated header block, or repoint to `session-51-readygate-storefront-flag.txt`.** *(Highest-severity single defect found.)*
2. **CLAUDE.md's "VALIDATION PENDING (2026-07-10)" note.** It says the triple-PI-hooker default "has not yet had a confirmation launch" and is "N-way safe by construction." S85 ran it and it **crashed**, with controls, and recommended the single-shim fallback — recorded in the same commit that last edited CLAUDE.md. **Fix: state the crash, give the fallback, record the open bisect.**
3. **MEMORY.md cheat-surface bullet** presents a definitively-closed route as `NEXT:`. It is the auto-loaded file.
4. **MEMORY.md is 8 sessions behind** its own tutorial topic file (S94 vs S102) and has become a 16 KB duplicate rather than an index.
5. **The queue-ID diagnostic trim** (`interactive.go:867` = 4 ids) was never reverted; comments above it describe the full 10. BATTLE/PRACTICE are degraded today.
6. **`configs/shim-status.ps1` monitors 5 of 6** default shims; `inject-secondaries.ps1`'s own header comment also lists only 4 secondaries while line 63 adds a 5th.
7. **`-NoPasses` dropped on elevation** (`launch-redirect.ps1:93-106`), and `inject-secondaries.ps1`'s log line omits its state — so you cannot even tell after the fact whether the passes shim was in a run.
8. **README.md** teaches mutually-exclusive PI hooks and "the tutorial isn't playable."
9. **`docs/endpoints.md`** misclassifies ≥8 endpoints (it marks `/configuration/client` as catch-all when it has a full handler; `/progression/players/{id}` as unknown when it is the account-pass ingest). *Note: the "under-documents by a quarter" claim is a measurement artifact — the doc uses collapsed multi-path notation. Real drift is ~10 routes.*
10. **`docs/trackb-notes.md`** still says the HTTP loadout readback is the repopulation path (falsified) and that missions are blocked by the AssetManager gate (overturned).
11. **`docs/dedicated-server-stub.md`** (252 KB) stops ~50 sessions short of the route's end state; `unreal-stub/` itself has **zero** `.md` files.
12. **`docs/game-map.md`** claims "every gameplay-defining asset" and explains a ~9,259-asset gap as duplicate basenames (真 count: 722). It also directs readers to index columns that are 0% populated.
13. **`docs/admin-panel.md`** documents 9 API routes; the code has 11.
14. **The handoff chain broke at S99.** S100, S100b, S101 and S102 produced substantial findings and no handoff prompt — breaking a 40-file ritual that the never-bank directive makes load-bearing.
15. **Two divergent `interactive.json` files**; the tracked one is a 3-week-old fossil.
16. **`tools/re/s87/run_ghidra.bat`** points at a `Downloads` Ghidra while `docs/ghidra-install.md` documents `E:\Tools\ghidra`.
17. **Three documented `usmapdump` subcommands and one extractor subcommand do not exist**; four real ones are undocumented.

---

## 8. Prioritized Focus Plan

Ordered by **(coverage unlocked) ÷ (effort)**, with the concrete first measurable step for each.

### Tier 0 — Hours each. Do these first; several are one command.

| # | Action | First measurable step | Unlocks |
|---|---|---|---|
| 0.1 | **Back up `memory/` into the repo** | `cp -r` the 19 files into `memory/`, commit, push. Verify `git ls-files memory \| wc -l` = 19. | Removes the single largest knowledge SPOF (956 KB, currently one disk) |
| 0.2 | **Re-run `mergedumps`** with `toggles`, `vmbuild`, `accountpass` | `usmapdump mergedumps dumps/merged.dump.exe dumps` → re-read the coverage line; expect 48.05% → **49.70%** | +2.04 MB of **gameplay** `.text` for every static-analysis question; then re-import into Ghidra |
| 0.3 | **Fix the CLAUDE.md → hero-roster-attempts.md pointer** | Append a dated SOLVED header (`CatMgr+0x354`, `catalog_store_fix.dll`, falsified list) *and* repoint CLAUDE.md | Kills the highest-severity knowledge defect |
| 0.4 | **Extract `Loki/Config/*.ini`** (10 plain-text files) | `extractor dump` on the 10 paths; read `DefaultGameplayTags.ini` + `DefaultInput.ini` | Authoritative gameplay-tag tree (currently reconstructed by regexing 3,252 cue assets) + real input bindings. **No usmap needed.** |
| 0.5 | **Record the module base in probe output** | One line in `gas_recon.py` / `cheat_enum.py` / `class_funcs.py` | Converts **1,057** recorded name→thunk pairs into importable Ghidra symbols |
| 0.6 | **Fix `-NoPasses` elevation forwarding + add the 6th `shim-status` row + fix the 2 wrong Build lines** | `launch-redirect.ps1:104`, `shim-status.ps1:43`, two `.cpp` headers | Makes shim bisection possible and the dashboard honest |
| 0.7 | **Write `tools/sigbypass-mod/build.ps1`** | Build all 6 production shims from their (corrected) header lines; assert output mtime > source mtime | Reproducibility + kills the recurring stale-DLL trap |
| 0.8 | **Record a build fingerprint** | SHA-256 of the exe + each `.utoc` into `docs/build-fingerprint.md`; add a size/hash check to the launcher | Detects the one event that invalidates all 179 RVAs |

### Tier 1 — One session each. Highest coverage-per-session in the project.

| # | Action | First measurable step | Unlocks |
|---|---|---|---|
| 1.1 | **★ Port the DS GAS recipe to force-open** | Copy the CDO-borrow from `ds_hybrid.cpp:2370-2430` into `tutorial_launch`'s `sp` shim (borrow `Default__LokiPlayerState_HeroAffiliated`'s `+0x3E8/+0x3F0/+0x3F8` into hero `+0xF00/+0xF08/+0xF10`, write the attribute block). Read `GetMaxSpeed()` before/after — expect **0 → 500**. | Abilities, attributes, health, real WASD via the stock chain, and plausibly combat. **Does not require solving `PlayerState+0x4F8`.** Single highest-value experiment available. |
| 1.2 | **★ Fix the extractor's CDO-default serialization** | Re-dump `BP_HERO_Ronin`; assert `Ability1/2/3/AbilityDodgeRoll` appear | **One fix, seven gaps**: hero kits, GE modifiers/durations, mode tuning, item stats, mission objectives, Armory tables, 9 hero identities |
| 1.3 | **★ Materialize the AssetRegistry oracle** | Emit a 103,841-row CSV: `PackageName, PackagePath, AssetName, NativeParentClass, PrimaryAssetType, PrimaryAssetName`. Offline; no game, no usmap. | Closes 4 gaps simultaneously: package-path resolution, catalog-id ↔ runtime-name divergence, cosmetics taxonomy reconciliation, and a shim-side basename→path resolver |
| 1.4 | **Extract the 60 `CT_*` curve tables** | `batch_dump.sh` on the 60 paths → `catalog/ct/`; verify one known value (Ronin `MoveSpeed`) against a live RPM read | The **first actual balance data in the project** — 43 per-hero attribute tables |
| 1.5 | **One clean full-shim validation launch** | Default set + `shim-status.ps1 -Watch` in a second terminal; record READY/FAIL per shim; bisect with `-NoMissions`/`-NoLoadout`/`-NoPasses` if it crashes | Closes the S85 question (open 17 sessions) and re-baselines all 6 front-end surfaces. **Fix the stale primary-readiness gate first** (delete the marker pre-launch, or gate on mtime ≥ process start). |
| 1.6 | **Fix `index_catalog.go:194`** | Make the extractors walk subobjects, not `dump[0]`; assert `ge_index.csv` `display` goes 0/2429 → non-zero | Turns ~10 hollow index columns into a usable design reference |
| 1.7 | **Identify what writes `PlayerState+0x4F8`** | Is it a reflected UPROPERTY on `BP_LokiPlayerState_C`? Try writing it directly with a borrowed CDO subobject and re-run `TryUpdateAbilitySystem` | The native path to a real ability system (complements 1.1) |
| 1.8 | **Extract `en/Game.locres`** | Add a `locres` subcommand (CUE4Parse `FTextLocalizationResource`); join by the FText Key GUIDs already in the dumps | 912 unnamed cosmetics + likely the remaining hero display names + ability tooltips for the 18 uncovered heroes |
| 1.9 | **Restore the queue list behind a served account level** | Serve a high `lastSeenAccountLevel`, restore the 10 ids, click a BATTLE tile | Un-degrades half the PLAY menu |
| 1.10 | **Write `docs/RETRACTIONS.md` + `docs/SESSIONS.md`** | Seed from §6 of this document + `git log --format='%ad %h %s'` | Stops the project re-opening closed routes; makes the 28 session-number holes legible |

> ### ⛔ RETRACTED — item 1.9 · S105, 2026-07-27 → **`docs/fk5-battle-gate-settled.md`** (FK-5)
> **Original row preserved above. It is over-specified, and bundling its two halves would make the
> probe ambiguous — the exact failure mode CLAUDE.md warns about.**
> **The account-level half is provably unnecessary.** `CanControlQueue` loops
> `PartyModel.GetCurrentQueues()` (**×25** in `bpdump_CanControlQueue.txt`), never `GetQueues()`
> (**×0**), so advertising ids cannot enter that loop; its `GetLevelGameFeatureUnlocked` call sits
> behind `PopExecutionFlowIfNot(q.bIsRanked)` (we serve `IsRanked:false`) and takes a **hardcoded**
> `PrimaryAssetId{GameFeature, Ranked}` whose result only formats a `level` argument for an error
> string. Real per-queue restrictions live in `IsQueueIDPremadeOrOverQueueLevel` → the
> `QueueToGameFeature` CDO map, which has **3 rows**: `deathmatch`, `customgame`, `custom`.
> Separately, `lastSeenAccountLevel` is **client-written display state** (`clientVisibilityTracking`,
> the client POSTs it *to us*), not a backend-owned level.
> **Corrected item 1.9:** restore the 10 ids **alone**, bump `matchmakingETag`, change nothing else.
> **And it is no longer the cheapest first step** — see the item 2.3 banner below.

### Tier 2 — Multi-session. Real research.

| # | Action | First measurable step | Note |
|---|---|---|---|
| 2.1 | **Levels: get world data** | Dump the `_Generated_` cells for `LVL_Tutorial` (68 packages) — **not** the persistent maps, which yield only cell metadata. Cross-check against `actor_locs.py` live output. | Prerequisite for DropPlane, real spawns, and any map beyond the tutorial |
| 2.2 | **Match-result reporting** | Have the tutorial route (or the DS stub at teardown) POST a match result; add tutorial objective names to `objectiveRules` | Closes the *shared* gap that missions, pass XP and Career all have |
| 2.3 | **The party/queue write surface** | Click FIND MATCH / change queue with a fresh `capture.log`; diff against the exe route table; implement in call order starting with `/setTargetQueues` | 27 of 33 party ops; note the QoS UDP responder is the named upstream blocker for BATTLE/PRACTICE |
| 2.4 | **Combat and damage** | After 1.1: call `GetHealth`/`GetMaxHealth` on the possessed hero; then `BP_AuthGiveAbilityWithInputID` + `TryActivateAbilityByInputID`; watch for a gameplay cue | Zero working references exist — genuinely new ground |
| 2.5 | **Egress audit** | Netstat/wildcard-hosts sweep during one launch; enumerate every remote host the client contacts | The census is structurally blind to hostname-addressed traffic (Sentry proves it) |
| 2.6 | **The messenger heartbeat** | A/B the reply *form* — binary `hb` vs TEXT `hb` vs an AccelByte `type: heartbeat` frame. Delivery is already proven; this is a format problem. | Stops a socket dying every ~60 s under a latency fix that depends on it |
| 2.7 | **Bulk-recover the 83 net UFunction signatures** | Run `ufunc_params.py` over all 83 in one pass and back-fill the stub headers | Replaces the current one-crash-at-a-time loop |
| 2.8 | **Load a second map** | Force-open `LVL_Training` (small) with its gamemode; watch for the initializer `Finished` marker | Converts "the technique works for one map" into "the technique works" |
| 2.9 | **Render a second hero** | Repeat S98/S99b on Beebo or ShieldBot; check `bRecentlyRendered` + `AnimScriptInstance` | Same — converts a sample of one into a method |

> ### ⛔ RETRACTED — item 2.3's Note · S105, 2026-07-27 → **`docs/fk5-battle-gate-settled.md`** (FK-5)
> **Original row preserved above.** *"the QoS UDP responder is the named upstream blocker for
> BATTLE/PRACTICE"* is a **false-known**. There is no AccelByte QoS on this path: `QosManagerServerUrl=`
> is empty in all 12 environments, and the populated machinery is Theorycraft's `ULatencyManager`
> driving **UE's own ICMP-module UDP echo** against a host *we* advertise. Decisive, at instruction
> level: **no `ULatencyMeasurer` has ever been created** — `Creating new latency measurer` is
> `LatencyManager.cpp:315` at verbosity **Display** (prints by default) and has **0 hits in all 14
> Loki logs** — and the UDP-echo implementation `0x1F8CFC0` is a **100 % zero page**. No captured
> session ever got far enough for the client to want a QoS endpoint.
>
> **⚠ Do not substitute a replacement culprit.** "Not QoS" is *not* "the `/core-game/regions` payload
> is the gate" — that payload is a real measured defect of the **`??? — ms` latency display**
> (`PingHost`/`PingPort` belong to `FRegionRoute` inside `FRegionHost.Routes`, which we never send;
> and `CanExclude` defaults `false`, which `0x57DE016` uses to skip the region before the route loop),
> but nothing measured puts it on the BATTLE path. **What blocks BATTLE past the tile is genuinely
> UNKNOWN**: `TryJoinQueue`'s implementation page `0x5875000` is 100 % zero in every dump we own.
>
> **★ The rest of item 2.3 is sound and is now cheaper than written.** The first click costs **zero
> backend change**: `bots` is already served, is **not** in the native `IsSpecialQueue` set
> (`{practice, customgame, dropin, tutorialNew, training}`), and is unrestricted — so **BOTS → FIND
> MATCH dispatches into the real `UPartyManager::TryJoinQueue` today**, and `capture.log` names the
> first unserved route for free. Also: **do not pre-register `POST …/latencies`** — the catch-all
> already logs the full body, so the first call hands over the ground-truth request shape and the true
> route; registering early destroys that. Ordered probe: `docs/fk5-battle-gate-settled.md` §7.

### Explicitly NOT recommended

- **Do not pursue AssetRegistry deployment** (loose-file, mod-pak, signing bypass, IoStore overlay). The route is *moot*: the client already loads the full, correctly-tagged 103,841-entry registry into memory.
- **Do not re-open the DS route for tutorial playability.** `OnObjectiveComplete` is `FUNC_BlueprintAuthorityOnly` — structural.
- **Do not chase the Vivox token.** Vivox validates server-side against Theorycraft's secret.
- ~~**Do not spawn `LokiPlayerState_HeroAffiliated` client-side.** Live-proven instant crash, uncatchable.~~
  ⚠ **CORRECTED S105, 2026-07-27 — this prohibition is STALE and over-generalised.** The crash is
  **S80, on the DS route, direct spawn**. **S103 falsified it on the force-open route:**
  `docs/tutorial-launch-marker.txt:33` records
  `[QST] LokiPlayerState_HeroAffiliated FinishSpawning -> res=0x20076AF12C0`, its constructor built
  the ASC (`@0x3E8 = 0x1FEAA34E680`), `K2_InitStats` created both attribute sets, and the run reached
  `[SP] done`. *Not* measured: whether it destabilises later. Scope the ban to the DS route.
  (Found while settling FK-6 — the exact generalisation FK-6 exists to stop, forming inside the list
  we use to prevent it. See `docs/fk6-cheat-surface-settled.md` §6.5.)
- **Do not take more menu-state image dumps.** Five already exist and contribute ~1 KB between them; merge what you have (0.2) instead.
- **Do not speculatively catalog more assets.** Tier 1 is at 88–100%; the bottleneck is Tier 2.

---

## 9. Appendix — Methodology & Provenance

### How this was produced

Eleven domain audits ran independently against the repo, the 364-file `docs/` tree, the 19-file memory tree, live client logs, and on-disk artifacts. Each was then re-verified by a second adversarial pass instructed to check every gap claim, look for missed gaps, and challenge overstated "known" items. **Where the two disagreed, the verifier's number is used**, and the disagreement is recorded (§6, "Corrections made by this audit's verifiers").

### Spot-checks performed during synthesis

To ground the headline numbers against the *current* HEAD, the following were re-measured directly:

| Check | Result |
|---|---|
| `git log --oneline -1` | `f6a7985` — **S102**, one commit newer than the newest domain audit assumed |
| `git rev-list --count HEAD` / `git ls-files \| wc -l` | 364 commits / 726 tracked files |
| `ls -1 docs \| wc -l` | 364 |
| memory tree | 19 `.md`, 956 KB, newest `supervive-tutorial-launch-status.md` (Jul 26 04:55) |
| `git status -sb` | branch **14 commits ahead** of origin |
| Production shim `// Build:` lines | Present in all 6; **`catalog_store_fix` names `catalog_ready_fix.dll`**, **`mainmenu_refresh_pi8` names `mainmenu_refresh_pi2.dll`** |
| `dumps/` | 9 state dirs; `merged.dump.exe` dated **Jul 17 15:46** (stale vs `toggles`/`vmbuild`/`accountpass`/`rcb`) |
| `docs/hero-roster-attempts.md` | last commit **2026-06-28**; `grep -ciE '0x354\|CatMgr\|catalog_store_fix\|SOLVED'` = **0** |
| CLAUDE.md highest session reference | **S85** (17 behind HEAD) |
| `-NoPasses` in `launch-redirect.ps1` | declared :66, honored :127, **absent from the elevation block :93-106** |
| `configs/shim-status.ps1` `$shims` | **5 rows**; `battlepass_adopt_fix` absent |
| `inject-secondaries.ps1` DLL set | 5 secondaries incl. `battlepass_adopt_fix` (:63); header comment lists only 4 |
| `CT_*.uasset` in pak vs catalog | **60** in `allfiles.txt`; **no `catalog/ct` category** |

Every one confirmed the verifier's position over the auditor's where they differed.

### Where the numbers came from

- **Endpoint counts** — normalized request lines from `docs/capture.log` + `capture.log.prev` (6,726 requests across two runs), matched against 115 `HandleFunc` registrations.
- **Asset counts** — per-directory counts under `tools/extractor/out/catalog/`, extension histogram over `allfiles.txt` (107,123 lines), `comm` diff of unique basenames.
- **Type counts** — parsed from `schema.txt` (11,347 UStructs, 43,296 properties, 2,226 enums) and intersected against every 4+-char identifier in `docs/`, `tools/`, `unreal-stub/` and `memory/`.
- **Address counts** — regex census of `.text`-window literals across docs, shims, probes and memory, deduplicated.
- **Function-count denominator** — linear `0xE8` call-target scan over `dumps/merged.dump.exe`: 90,073 distinct in-range targets, 59,095 high-confidence, in only ~48% of `.text`.
- **Shim counts** — `ls` of `tools/sigbypass-mod/`, reconciled against the DLL names in `launch-redirect.ps1` + `inject-secondaries.ps1`.
- **Test counts** — `grep -c '^func Test'` over `*_test.go` (40 in 8 files) and `find tools -name '*_test.go'` (zero).

### Known limits of this audit

- **Read-only.** No launch, no injection, no game execution. Every "LIVE" and "SOLVED" claim is confirmed against the record and against artifacts, **not** against a running client. Given that the front end has had zero code changes in 18 commits and the full shim set is recorded as crashing, this is a real limitation — see focus item **1.5**.
- **Not exhaustive on prose.** 115 session logs (1.73 MB) were sampled strategically, not read end-to-end; retractions phrased without the keyword set are under-counted.
- **Two monolith shims** (`ds_hybrid.cpp` 3,584 lines, `tutorial_launch.cpp` 4,493 lines — 7,877 of ~13,400 total shim lines) had their mode enums, hook sites and headers read, but not their bodies. Their internal correctness is documented-only.
- **The Ghidra project (2.1 GB) was not opened**; its function count and analysis completeness remain unmeasured — though its imported program is confirmed to be `SUPERVIVE-deobf.exe` (the IAT-reconstructed dump), so the `deobfimports` work is not going unused.

---

*Generated as a synthesis of eleven verified domain audits. Later measurements supersede earlier ones throughout. When this document and a session doc disagree, check the date — and prefer the measurement over the inference.*
