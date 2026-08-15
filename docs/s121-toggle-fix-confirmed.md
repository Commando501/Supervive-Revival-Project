# S121 — the feature-toggle ConfigKey fix is CONFIRMED, twice over (2026-08-15)

Ignorance-map **A-14**. Status: **SETTLED AND FLOWN.** The declarative UI-gate channel works
end to end from the backend, with no shim and no `.text` write.

Claims are labelled **[M]** measured / **[I]** inferred / **[S]** speculative.

---

## 1. The result

S120 found that `WBP_UI_ClientConfigVisbilityToggleWidget_C` reads
`FeatureToggles[FeatureKey].Config[ConfigKey]` with a CDO default `ConfigKey` of **`"enabled"`**,
while this project had written `Config["default"]` since S73. `5e40475` began sending both sub-keys.
**That fix is now confirmed.**

[M] Measured on a cold launch (run 2, pid 66772, 2026-08-15 16:13:46), client config applied —
`LogClientConfig: VeryVerbose: Fetched client configuration: ETag supervive-revival-5-configkey-enabled`,
observed 6+ times.

### The STORE nav bar — three pre-registered predictions, three matches

| nav button | FeatureKey | `IsEnabledByDefault` | predicted | observed |
|---|---|---|---|---|
| SUPPORTER PACKS | `supporterpacks` | **true** | visible (control) | **visible** [M] |
| REDEEM | `redeemcode` | **true** | visible (control) | **visible** [M] |
| **STORAGE** | `exchangetokens` | absent → false | **appears** | **appears** [M] |

[M] Observed left-to-right: `FEATURED · BUNDLES · SKINS · ACCESSORIES · SUPPORTER PACKS ·
STORAGE · REDEEM`. STORAGE sits between SUPPORTER PACKS and REDEEM, exactly as
`docs/s120-feature-toggles.md` §5 predicted.

★ **The two `IsEnabledByDefault=true` controls both HELD.** That is the load-bearing safety check:
it rules out "we are now writing a value that turns things OFF". No revert was needed.

★ **STORAGE is not a dead label.** [M] The page renders its own content: a `STORAGE` heading,
`No items in storage.`, a shipped Korean purchase-confirmation disclaimer, and a
`CONFIRM ALL PURCHASES` button. So the gate reveals a real, populated screen.

### Second, independent confirmation: DEBUG BATTLEPASS

[M] `DEBUG BATTLEPASS` now renders on the main-menu rail, below CAREER
(`HUNTERS · ARMORY · PASSES · CUSTOMIZATION · STORE · CAREER · DEBUG BATTLEPASS`). It was absent
before this change.

⇒ **A different key (`DebugBattlepass`), on a different screen, through the same mechanism.** Two
independent surfaces from one payload change is materially stronger than one: a single hit is
consistent with a coincidence in the storefront's own state, two is not.

### The visual harvest — 4 served keys produced a visible surface [M]

⚠ **COUNT CORRECTION: the served UI set is 16 keys, not 17.** `docs/s120-feature-toggles.md:174` says
17 and this file repeated it. Machine-counted from `handleClientConfig`'s literal list: **16**, and
16 + the 5 original enum-vocabulary keys = **21**, which matches the 21 entries measured on the wire.
The 17 was never reconciled against the payload. **State the unit and count with a machine.**

| key | surface | where | verdict |
|---|---|---|---|
| `exchangetokens` | **STORAGE** nav tab + a populated page | STORE | **full surface** |
| `leaderboards` | **LEADERBOARDS** nav tab + a full functional page | CAREER | **full surface, and it calls the backend** |
| `discord` | **DISCORD** button under `JOIN THE COMMUNITY!` | ESC / pause menu | **full surface** |
| `DebugBattlepass` | **DEBUG BATTLEPASS** main-menu rail entry | main menu | **button only — see below** |

★ **LEADERBOARDS is the richest of the four.** [M] It renders HUNTER / STAT / QUEUE dropdowns,
DAILY / WEEKLY / FRIENDS / RANKED side tabs, `RANK · SCORE · PLAYER` columns, a REFRESH button and a
live `RESET IN 00:00:55` countdown.

⚠ **`DebugBattlepass` renders the button but clicking it does NOTHING** [M, operator-observed]. No new
`leaf-most node`, no error, no HTTP request. [I] Either the destination screen was stripped from the
shipping build, or the button's action has a companion condition. ⚠ **This is a weak negative**: the
`leaf-most node` log only fires when a screen takes input-config focus, so a screen that opened
without focus would not appear. Do not record "the debug battlepass screen does not exist."
⇒ It is still a **positive** for the toggle mechanism — the gate revealed the widget. Gate ≠ destination.

---

## 2. ★★★★★ UNANTICIPATED: the toggles are an ENDPOINT-DISCOVERY INSTRUMENT

Turning a gated surface on makes the client call endpoints it otherwise **never** calls. [M] These
appeared in `docs/capture.log` for the first time, all with `User-Agent: Loki/UE5-CL-0` (checked —
the `User-Agent` trap has fired twice in this project):

    GET  /player-stats/leaderboard?queueId=tutorialNew&period=daily&statCode=wins
                                  &heroId=Hero:All&start=1&end=25        (5 calls)
    GET  /mmr/leaderboard?start=1&end=50&queueId=tutorialNew&region=      (2 calls)
    GET  /player-stats/players/{playerId}                                 (3 calls)
    POST /discord-api/account/token                                       (1 call)

[M] **All four return `200 {}`** — they hit a catch-all; there is no handler for any of them
(`grep -rn "leaderboard" server/ --include=*.go` → 0 hits outside the toggle list). So the page is a
fully-built UI idling on a response we simply never wrote.

★★ **The query string is a self-describing API contract.** Every parameter maps one-to-one onto a
visible control: `queueId=tutorialNew` ← QUEUE "BASIC TRAINING"; `period=daily` ← the DAILY side tab;
`statCode=wins` ← STAT "TOTAL WINS"; `heroId=Hero:All` ← HUNTER "ALL HUNTERS"; `start/end` ← paging.
⇒ **The UI hands us the vocabulary for free.** Changing a dropdown and re-reading `capture.log`
enumerates the rest of it at zero RE cost.

⇒ **Generalise the method: a feature toggle is a cheap probe for hidden BACKEND surface, not just
hidden UI.** Each of the remaining dark keys may reveal further endpoints the client has never been
observed to call.

---

## 3. What this unlocks

The declarative vocabulary is **50 distinct `FeatureKey` values** [M, S120] and they are now
backend-controllable with a one-line JSON change — no shim, no injection, no `.text` write. This is
the cheapest lever this project has found in a long time.

Currently served (**16** dark keys + the original 5 = 21 map entries, verified on the wire) — see `handleClientConfig` in
`server/internal/loki/loki.go`. Confirmed to produce a surface so far: `exchangetokens`,
`DebugBattlepass`.

---

## 3b. ★★★★★ THE MISSING READOUT NOW EXISTS — `tools/re/toggle_readout.py`

The S121 handoff said the highest-value thing to build was a way to **observe an `IsFeatureEnabled`
result**, because without one a dark surface is ambiguous between "flag off" and "companion condition
unmet". **It exists, it is read-only RPM, and it needed no injection and no `.text` write.**

**Mechanism [M]:** `UClientConfigManager::IsFeatureEnabled` logs nothing — 0 `BasicLog` call sites in
its 265-byte body (240/265 bytes non-zero, i.e. decrypted, so this is a real negative and not an
undecrypted page), against a same-TU control with 1. **No log verbosity can ever see it.** But the
declarative widget **stores its computed answer** in a reflected instance UPROPERTY.

Measured live property layout on `WBP_UI_ClientConfigVisbilityToggleWidget_C`:

    FeatureKey          +0x0450 StrProperty
    ConfigKey           +0x0460 StrProperty
    IsEnabledByDefault  +0x0470 BoolProperty
    EnabledVisibility   +0x0471 EnumProperty
    DisabledVisibility  +0x0472 EnumProperty
    Is Content Enabled  +0x0473 BoolProperty      <-- the answer

★ **The decisive predicate:** `IsEnabledByDefault == false` **and** `Is Content Enabled == true` is
reachable by **no path other than** `FeatureToggles[FeatureKey]` hit → `entry.Config[ConfigKey]` hit
→ `ToBool == true`. That is a direct measurement that **our served value was read**.

**[M] LIVE RESULT — 133 instances, `summary: total=133 served-value-read=14 gate-off=85
on-by-default=34`.** ⚠ Parse that summary line; do not count rows.

★★ **`ConfigKey` reads `"enabled"` on all 133 live instances** — the fix's premise, now measured on
the running client rather than inferred from the CDO.

### Both controls passed IN THE SAME RUN

| control | expectation | observed |
|---|---|---|
| **positive** — keys with `IsEnabledByDefault=true` | read enabled | `supporterpacks`, `redeemcode`, `DebugNav`, `GameVersion`, `ChatLobby`, `EventHub`, `RankedDisplay`, `XPBoosts`, `party.fill`, `OBSButton` all **on by default** ✓ |
| **negative** — keys we DELIBERATELY WITHHELD, default false | read OFF | `SeasonalBattlepass` **8/8 OFF**, `chuseokboostui` 2/2, `prisma_boost` 2/2, `lobby_survey_menu` 2/2 ✓ |
| **cross-instrument** | agree with screenshots | 4 of the 8 positive keys independently confirmed visually ✓ |

⇒ The readout reads TRUE for exactly the keys we serve, FALSE for exactly the ones we withhold, and
agrees with every screenshot. **That is a discriminating instrument, not a coincidence.**

### Per-key verdict [M]

**8 keys measured as SERVED VALUE READ:** `exchangetokens`, `leaderboards`, `discord`,
`storefrontcheats`, `DebugBattlepass`, `ArmoryItemProgression`, `CosmeticEffectsOverride`,
`NeLobbyEventBtn`.

★★ **This DOUBLES the visual result (4 → 8) and resolves the ambiguity the handoff named:**
- `storefrontcheats` → now measured ON; it gates the **TOP UP** button (visible in the STORE shot).
- `CosmeticEffectsOverride` → ON, never visually checked.
- ★★★ **`NeLobbyEventBtn` → gate is ON and the button is still not visible.** That is precisely the
  case that used to be uninterpretable. **It is NOT a flag problem** — a companion condition is
  unmet ([I] the button self-hides with no event data). Before today this would have been written
  down as "serving the key did nothing."

**Keys with zero served-reads, and the honest reason for each:**
- `motd`, `LobbyRewards`, `ArmoryOnboarding` — **0 widget instances.** These are *bytecode* keys, not
  declarative ones, so **this instrument structurally cannot see them.** Not a negative result.
- `mastery` — 6 instances, 3 **on by default**. ⇒ it was **already lit without us**; it was
  mis-classified as a dark key. Serving it is a no-op (and serving it `false` would REMOVE the S120
  mastery surfaces).
- `DropScreenTitles` — 1 instance, OFF. In-match widget; not evaluated at the lobby.
- `ServerSelectRegionRoutes` / `ServerSelectNetworkAcceleration` — 1 instance each, OFF. Consistent
  with the SETTINGS screenshot showing no region controls. ⚠ **Ambiguous**: with a single instance
  each it cannot be separated from an unevaluated archetype. Do not record as a measured negative.

⚠⚠ **READING RULE — a False row next to a True row is NOT a failure.** Most keys have BOTH, because
the widget-tree template/archetype coexists with the live instance and **unevaluated objects read
`false`** (the CDO `Default__WBP_UI_ClientConfigVisbilityToggleWidget` reads False/False, which is the
control for this). **Per key, ANY `SERVED VALUE READ` row is the positive signal.**

⚠ `class_props.py` CANNOT resolve this class — it requires the class-of-class to be `"Class"`, and a
Blueprint class's is `BlueprintGeneratedClass`, so it prints a misleading
`not found (map not loaded yet?)`. `toggle_readout.py` resolves the class from a **live instance**
(`obj+0x18`) instead. **This is a THIRD member of the class-lookup blind-spot family** CLAUDE.md
already records for `obj_by_class.py` (substring) and `cheat_reach_probe.py` (endswith).

---

## 3c. ★★★★★ THE LEADERBOARD IS LIVE — a new surface, found AND filled in one session

`GET /player-stats/leaderboard` is implemented (`server/internal/interactive/leaderboard.go`) and the
page renders real rows. **Backend-only: no shim, no injection, no `.text` write.**

★ **Method validation first:** the schema was derived by a method that was validated before use —
`FPlayerProgression`, `FHeroMasteryProgress`, `FMissionInfo` and `FMatchHistory` re-derived blind,
**4/4 exact**, including the `Version` int32-vs-int64 split between two of them.

⚠⚠ **THE TRAP: THE RESPONSE MUST ECHO THE REQUEST.** [M]
`WBP_UI_LeaderboardScreen_C::"Current Leaderboard Is Stale"` computes
`HeroName != heroId.PrimaryAssetName || StatCode != statKey || QueueID != queueKey || age > 60s`,
and a stale response is **parsed perfectly and then silently discarded**. ⇒ a schema-correct reply
with a wrong echo is **indistinguishable from a parse failure**. Note the asymmetry: the request
sends `heroId=Hero:All` but the check compares `PrimaryAssetName`, so we must echo the **bare `All`**.
`Period`/`Start`/`End` are not compared. [M] No envelope — the callback (`0x5809760`) has ZERO
instructions between `GetContentAsString` and `JsonObjectStringToUStruct<FLokiPlayerStatsLeaderboard>`;
control = an envelope detector over all 152 `JsonObjectToUStruct` sites fires on exactly 1
(AccelByte's `"payload"`) and 0 for the four Loki structs.

**Pre-registered prediction, written before the screenshot — all five matched [M]:**

| predicted | observed |
|---|---|
| RANK 1 | `#1.` |
| SCORE 42 | `42` |
| a row renders | `Reviver#6612` — the client **resolved the display name** (better than predicted) |
| `RESET IN` ≈ 01:00:00 from `ExpirationTimeSeconds: 3600` | `01:00:24` |
| "No one has claimed a spot…yet" disappears | gone |

★ **`HeroCounts` confirmed exactly:** it is a `TMap` rendered as **one hero portrait per key**. We
sent two keys (`ghost`, `brall`) and **exactly two icons appeared**, drawn as `?` because those are
invented names with no matching hero. A precise, quantitative confirmation of the container type.

⚠ Minor unexplained: we serve `3600` and the UI displays `01:00:24` (3,624 s), a **+24 s**
discrepancy. Not investigated. Do not write it up as "3600 ⇒ 01:00:00" — that is not what was seen.

**Required for rows to draw** [M]: `StatCode`, `QueueID`, `HeroName` (all echoed) and a **non-empty**
`Entries` — the else-arm of the length test is literally the "No one has claimed a spot" widget.
Everything else is optional. Other measured behaviours: `Value` is `FCeil`'d; row order is **array
index, not `Rank`** (sort server-side); an unresolved `PlayerID` still renders a row; a second fetch
while one is in flight is silently dropped.

**Vocabulary** [M]: `statCode ∈ {kills, wins, damage, healing}` (from `ST_Leaderboard_Stats`,
complete); `period ∈ {daily, weekly}` for this endpoint — the **FRIENDS** and **RANKED** side tabs
are a different widget hitting `/mmr/leaderboard[/friends]`. `queueId` is whatever we serve via
`GetQueueInfo()`.

Still `{}`: `/mmr/leaderboard` → `FLeaderboard` (⚠ its `Rank` is an **`ERank` enum string** such as
`"Gold1"`, not an int) and `/player-stats/players/{id}` → `FPlayerStats`. Both top-level, no
validation. Knob: `AGS_LEADERBOARD=0` restores the `{}` catch-all with no rebuild.

★ **The client survived an `ags` restart** and re-fetched everything including `/configuration/client`
— so backend iteration works inside one live session. At a ~25–30 % launch-death rate that is a large
saving over relaunching per change.
⚠ **`capture.log` had reached 55 MB and `ags` truncates it on restart** — backed up first
(`docs/capture-s121-run2-preLB.log`). This is the documented trap and it would have destroyed the
whole run's evidence.

---

## 3d. ★★★★★ THE DECLARATIVE SWEEP IS COMPLETE — and widgets re-evaluate LIVE

### First: the vocabulary closes exactly, and "33 keys remain" was WRONG

A live census (`toggle_readout.py`) + the catalog scan partition all **50** declarative keys with
no remainder:

| bucket | count |
|---|---|
| served | 12 |
| `IsEnabledByDefault=true` somewhere ⇒ **NEVER SERVE** | 33 |
| withheld: `BypassTutorialAndOnboarding` (REMOVES a surface) | 1 |
| **actual candidates** | **4** |
| **total** | **50** ✓ |

⚠ **CORRECTION:** an earlier note in this session said "33 declarative keys remain unswept."
The real number was **4**. 33 is the **never-serve** count — the same number in a different role,
which is exactly the kind of coincidence that propagates if nobody re-derives it.
⚠ Also: 46 of the 50 have live instances at the menu. Of the 4 that do not, `KeybindCheats` and
`lobby_survey` are default-true (never serve), `BypassTutorialAndOnboarding` is withheld, and the
"fourth" is an artifact of **my own diff** — `.strip()` collapsed the trailing-space
`"ArmoryItemProgression "` onto the clean key. Both spellings are served; there is no gap.

### ★★★ THE OPEN QUESTION IS ANSWERED: no relaunch is needed

Batch A (`chuseokboostui`, `prisma_boost`, `lobby_survey_menu`) was flown by restarting **`ags` only**,
with the game running continuously (68 min uptime at the time).

**Pre-registered, then measured:**

| | predicted | observed |
|---|---|---|
| treatment keys flip | yes | **yes — exactly the 3, 0→1 each** |
| control (43 other keys) | unchanged | **all 43 unchanged** |
| `served-value-read` | 14 → 20 | **14 → 17** |

⇒ **[M] Toggle widgets DO re-evaluate on `OnClientConfigUpdated`. A config change lands in ~30 s
with no relaunch.** At this project's ~25–30 % per-launch death rate that changes the economics of
every future toggle question.

⚠ **My count prediction was WRONG and the error is instructive.** I predicted +6 (3 keys × 2
instances). The answer is **+3** — one per key — because the second instance of each is the
widget-tree **archetype**, which never evaluates. That is the reading rule recorded in §3b of this
same document, written an hour earlier and then not applied to my own prediction. **The direction
was right and the arithmetic was wrong; record both.**

### Batch B — `SeasonalBattlepass`, alone, and the feared hard error did NOT occur

Flown by itself via `AGS_UI_TOGGLES_EXTRA`, with error canaries sampled before and after:

    BASELINE  Error=8  Fatal=0  LogJson-Unable=0
    AFTER     Error=8  Fatal=0  LogJson-Unable=0     game alive

`served-value-read` 17 → **21**, **+4 exactly as predicted**, and **only `SeasonalBattlepass` moved**
(45 of 46 keys unchanged).

⚠ **This does NOT clear the key.** CLAUDE.md's concern is that there is no packed
`LokiDataAsset_Season`, and the surface it gates is the **end-of-game** seasonal pass — a path we
cannot reach from the menu. So the measurement is "no error AT THE MENU", which is a much weaker
claim than "safe". **It is therefore deliberately NOT in the default served list** and stays an
env-only opt-in (`AGS_UI_TOGGLES_EXTRA=SeasonalBattlepass`). Re-test it at EoG before promoting.

### Final state: 12 of 15 served declarative keys read our value

    OK  ArmoryItemProgression 4/12 · CosmeticEffectsOverride 2/3 · discord 2/5 · leaderboards 2/4
        SeasonalBattlepass 4/8 · DebugBattlepass 1/2 · exchangetokens 1/2 · storefrontcheats 1/2
        NeLobbyEventBtn 1/2 · chuseokboostui 1/2 · prisma_boost 1/2 · lobby_survey_menu 1/2
    --  DropScreenTitles 0/1 · ServerSelectRegionRoutes 0/1 · ServerSelectNetworkAcceleration 0/1

★ **The three non-hits have a STRUCTURAL explanation, not a failure:** every key that reads our
value has **≥2** instances (archetype + live); all three that do not have **exactly 1**. A clean
12/12 vs 3/3 split on instance count ⇒ [I] that lone instance is the archetype and no live copy is
constructed at the menu — `DropScreenTitles` is a pre-drop screen and both `ServerSelect*` live on a
settings sub-screen. **Do not record these as measured negatives on the flag.** To settle them,
re-read while that screen is open.

### ⚠ A knob that would have been a trap, fixed before use

`AGS_UI_TOGGLES_EXTRA` changes the payload **at runtime**, so there is no code edit at which to
hand-bump the eTag — it would have silently reproduced the stale-eTag-over-changed-content failure
this very file documents. The eTag now folds the extras in automatically
(`…-8-sweep-batchA+x-SeasonalBattlepass`), sorted so map iteration order cannot leak into it.

---

## 4. ★ A free instrument, already switched on

[M] `LogClientConfig` is pinned to **VeryVerbose** in the user `Engine.ini`, and it emits a matched
pair on a **~30 s poll**:

    LogClientConfig: VeryVerbose: Refreshing client configuration
    LogClientConfig: VeryVerbose: Fetched client configuration: ETag <etag>

⇒ **Config changes do not need a relaunch to be picked up.** Given this project's ~25–30 % per-launch
death rate, iterating inside one live session instead of one-launch-per-batch is a large saving.
⚠ Still unverified [S]: whether an already-CONSTRUCTED toggle widget re-evaluates on the refresh, or
only on rebuild. The S120 prediction was that it re-binds via `OnClientConfigUpdated`. Test it before
relying on it — and rebuild the page (navigate away and back) before reading anything off it, per the
standing stale-widget-generation trap.

---

## 5. ⚠ Run 1 died at T+81 s — NOT our payload, and a NEW fault family

[M] The first launch (pid 19620, 16:08:01) died at **T+81.2 s** with `EXIT 0xC0000005`. Crashwatch
(`b54ebc4`) fired for the first time and captured `dumps/crash-20260815-160759`; the crashpad
minidump was preserved as `dumps/crashpad-20260815-161345`.

★ **Our config change is EXCLUDED as a cause** [M]: `docs/capture.log` for that run contains exactly
**one** request line — the launcher's own `GET /revival/missions/progress` probe at 16:07:59 — and
**zero** requests from the game. The client never received the payload it would have had to be
killed by.

[M] Triage (`tools/crashtri/mdctx.py`):

    EXCEPTION 0xC0000005  parms=['0x8', '0x7ffa42600001']   -> EXECUTE fault
    rip = 0x00007FFA42600001   -> in NONE of the 182 loaded modules
    rax/rsi/r12-r15 = 0 ; rdx/rbx/r8/r9/r10/r11 = high-entropy garbage
    stack top = 0x00007FFA415B7374 (a return address)

⚠ **This is a DIFFERENT family from the two S120 deaths** described in
`docs/next-session-prompt-s121.md`, which were **READ** faults at `SUPERVIVE base + 0x1000` with
`0x1000`-stride registers (the `catalog_store_fix` image-scan family). This one is an **EXECUTE**
fault to an unmapped address with obfuscated register state. Do not pool them.
[I] The register pattern is consistent with the protector's MBA-obfuscated code (FK-10 measured
`not`/`and`/`imul` ≈ 43 % of instructions in `runtime.dll`), or with an import-stub resolution
landing on a bad target — but `runtime.dll` is **absent from this dump's module list**, so the
canonical `RIP == runtime.dll base + 1` signature could not be evaluated. **Unattributed. N=1.**

⚠ Crashwatch's own pre-registered prediction is **not yet evaluated**: it expects a crash-era image
near **18,900** non-zero `.text` pages (~15,700 would falsify the crash-path hypothesis). The dump
reports `52.81 % of image readable`, which is `dumpimage`'s **readable-byte** metric and is **NOT**
the non-zero-`.text`-page metric the prediction is stated in. **Do not compare the two** — that is
the exact conflation FK-18 retracted. Evaluate it properly with `mergedumps` before scoring.

---

## 6. Method notes

★ **The natural positive control carried the whole experiment.** Because two nav buttons default to
`true` and one defaults to `false`, a single screenshot tested the mechanism AND its failure mode at
once. Look for a surface that already contains its own control before building one.

⚠ **`RD` is a PowerShell alias for `Remove-Item`** and it shadows a same-named function. A shared-read
helper called `Read-Shared` is in the session scratchpad; a helper called `RD` silently becomes a
delete attempt on the file you meant to read. (No files were harmed — the calls failed on the lock.)
