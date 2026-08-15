# S121 handoff — confirm the STORE / STORAGE tab, then exploit the toggle vocabulary

Written 2026-08-15 at the end of S120. **HEAD is `5e40475` on `dedicated-server-stub`, pushed.**
Working tree clean apart from two untracked run logs (`docs/inject-*.log`).
**Use a maximum of 3 subagents for this work.**

Both the game and `ags` are **DOWN**. You start cold.

---

## Start here — one screenshot decides the next few hours

**Relaunch, open the STORE tab, and look for a `STORAGE` nav button next to `REDEEM`.**

```powershell
cd "G:\git\Supervive Revival Project"
$env:AGS_SERVE_HEROMASTERY = "hero"; $env:AGS_SERVE_MASTERY_REWARDS = "1"
.\configs\launch-redirect.ps1        # ELEVATED. Steam must already be running.
```

Then ask the operator to open **STORE** and screenshot the nav bar.

### The pre-registered prediction

S120 found that the client's UI gates read `FeatureToggles[key].Config["enabled"]`, and that this
project has been writing `Config["default"]` since S73 — so **every feature toggle we have ever sent
has been silently ignored**. `handleClientConfig` now sends both sub-keys.

* **STORAGE appears** ⇒ the fix is confirmed and **50 declarative gated surfaces become
  backend-controllable in one stroke.** Go to "If it worked" below.
* **STORAGE still absent** ⇒ either the sub-key is still wrong, or the widget only evaluates at
  Construct. Distinguish by relaunching once more with the config already live (it is, at boot), and
  by checking `Loki.log` for the eTag `supervive-revival-5-configkey-enabled` being applied.

⚠ **You have a natural positive control in the same screenshot, and you must check it.** The nav bar
carries three toggle-gated buttons:

| component | FeatureKey | IsEnabledByDefault | expected |
|---|---|---|---|
| `PacksConfigToggle_1` | `supporterpacks` | **true** | SUPPORTER PACKS visible (was, before our change) |
| `RedeemConfigToggle_1` | `redeemcode` | **true** | REDEEM visible (was) |
| `StorageConfigToggle_1` | `exchangetokens` | *(absent → false)* | **STORAGE — the one under test** |

If SUPPORTER PACKS / REDEEM ever *vanish*, we have broken something — that is the failure mode to
watch for, because it would mean we are now writing a value that turns things OFF.

---

## What S120 established (do not re-derive)

Read `docs/s120-feature-toggles.md` first, then `docs/s120-hero-mastery.md`. Both are current.

### ★★★★★ The toggle mechanism [M]

The game gates UI on a reusable declarative widget, `WBP_UI_ClientConfigVisbilityToggleWidget_C`
(the typo is the game's):

```
entry = Map_Find(ClientConfiguration.FeatureToggles, FeatureKey)   // FeatureKey = ASSET PROPERTY
    if not found -> IsEnabledByDefault
value = Map_Find(entry.Config, ConfigKey)                          // ConfigKey  = ASSET PROPERTY,
    if not found -> IsEnabledByDefault                             //   CDO default = "enabled"
enabled = ToBool(value)
```

⚠⚠ **TWO TOGGLE SYSTEMS. Never confuse them:**
* `ULokiGameFeatureToggles::Get(ELokiGameFeatureToggle)` — **enum**-keyed; names are in the exe;
  readiness is per-PlayerController and set at round-start (S85). The 149-member list is
  `tools/re/out/game_feature_toggle_enum.txt`. **All five keys we served from S73 were from here.**
* `UClientConfigManager::IsFeatureEnabled(FString, bool)` — **string**-keyed, read from the map we
  serve. Its keys are Blueprint bytecode literals / asset properties, **absent from the exe**.

★ `bDefault` is the **second argument** — the value returned when the key is absent. Keys whose
default is already `true` (`EmoteSFX`, `KillStreakAsRomanNumeral`, `voicechat`, `ChatLobby`,
`CustomGameList`, `RankedDisplay`, `mailbox`, `EventHub`, `party.fill`, `XPBoosts`, …) are **already
on without us — sending them could only ever turn something OFF. Never send them.**

### The vocabulary [M]

* **10** bytecode `IsFeatureEnabled` keys — 30 call sites / 26 declared locals across 21 assets.
* **50** declarative `FeatureKey` values in the catalog (a plain JSON property scan; the bytecode
  census could not see these). Notables still dark: `leaderboards`, `storefrontcheats`,
  `DebugBattlepass`, `discord`, `mastery`, `CosmeticEffectsOverride`, `ServerSelect*`.
* ⚠ **GAME DATA BUG:** four sites declare `"ArmoryItemProgression "` **with a trailing space**. Both
  spellings are served. Do not "fix" it.

### Currently served (`AGS_UI_TOGGLES=0` reverts, no rebuild)

17 dark keys + the original 5, all as `{"config":{"enabled":"true","default":"true"}}`.
Withheld deliberately: `BypassTutorialAndOnboarding` (removes a surface), `SeasonalBattlepass` (no
packed `LokiDataAsset_Season` — **test alone**), `chuseokboostui`/`prisma_boost`/`lobby_survey_menu`
(no backing data), and every `IsEnabledByDefault=true` key.

### Hero Mastery is DONE [M]

Renders → unlocks → bars move → rewards offer → **the client AUTO-CLAIMS** (no widget, no user
action; the lobby progression tracker activating is the trigger) → we grant and persist. All
backend-only. `POST /progression/players/{id}/hero/rewards/claim` is implemented and was exercised by
the real client (`User-Agent: Loki/UE5-CL-0`). Evidence in `dumps/s120-claim-evidence/`.

---

## If it worked — the ranked follow-ups

1. **Sweep the 50 declarative keys for surfaces.** Each dark key is a candidate screen. Highest
   value: `leaderboards` (2 sites, `WBP_ProfileScreen`), `storefrontcheats`, `DebugBattlepass`,
   `discord`, `mastery`. Turn them on in small batches so a breakage is attributable.
2. **`motd`** — needs a Message-of-the-Day **body**, not just the toggle. We answer
   `/mailbox/config/version` but serve no message. Trace what `Get Message of the Day` reads.
3. **`SeasonalBattlepass`** — alone, with the missions/pass/banner canary watched, since there is no
   packed season asset.
4. **`LobbyRewards`** — necessary but not sufficient: AND-ed with `Rewards.Num > 0`, filled by
   `BeginMultiClaimRewardFlow`. Hero-mastery rewards bypass this widget entirely today.

## If it did not work

Build the readout that is missing. **Nothing in this project can observe an `IsFeatureEnabled`
result**, so a dark surface is equally consistent with "flag off" and "companion condition unmet".
A shim that logs the call (or a `.text`-free `Func`-swap on the widget's `OnClientConfigUpdated`)
would convert every future toggle question from inference into measurement. That is worth more than
guessing at the next key.

---

## ⚠ Traps that fired in S120 — read before trusting a number

1. **A "fresh" reading of an uncontrolled field is still uncontrolled.** `claimableRewards=[]` was
   published as a *controlled* negative because the notif was fresh. It is `[]` in **30 of 30**
   occurrences corpus-wide — no known-good case, so it cannot discriminate. Recency fixes staleness,
   not validity. **Demand a positive control for the FIELD.**
2. **Widgets bind to a STALE model generation.** Pushing data to an already-open page changes
   nothing. Rebuild it (switch hunters / relaunch) before reading anything off it. This
   mis-diagnosed two surfaces in one session.
3. **Filter `capture.log` by `User-Agent` before counting anyone's requests.** The game is
   `Loki/UE5-CL-0`; our own `curl`/PowerShell probes read identically. Fired twice.
4. **State the unit.** `ClaimReward 24` meant 24 *occurrences* / 9 *files*. `151 values` meant 149
   toggles + 2 sentinels. A control with an ambiguous unit cannot be re-checked by anyone else.
5. **A log detector can match the OLD log before rotation.** A "lobby reached" check fired on the
   previous session's content. Confirm the log is fresh (size/mtime) before believing a marker.
6. **`obj_by_class.py` caps its detail list at 60** — parse its `found N LIVE` line, never count
   rows. **`extractor wherefile` caps at 20.** Treat both caps as truncation, never a census.
7. **A promoted tool that parses is not a tool that works.** An operator-precedence slip wrote a
   header and dropped the entire body of two probes; they imported cleanly and did nothing. Run a
   promoted tool against known data before trusting it.

## Instruments worth reaching for

* `tools/re/image_diff_callers.py` + `image_diff_namepages.py` — **before/after decrypted-image
  diff**. `dumpimage`, perform the action, `dumpimage` again; `.text` decryption is monotone within
  a process lifetime, so pages zero-in-BEFORE and non-zero-in-AFTER are exactly the code that ran.
  Isolated the claim path to 20 pages / 80 KB and found a call site no static search could.
  ⚠ `dumpimage` wants the **process name with `.exe`**, not a PID.
* `tools/re/claim_page_probe.py` — `PAGE_NOACCESS` == never executed. Exact, zero-cost receipts.
* `extractor bpdump <asset-substr> <FunctionName>` — the only way to see Blueprint bytecode; the
  extracted `catalog/wbp/*.json` contain none. Find the function by grepping the asset JSON for
  `"Type": "Function", "Name": "..."`, or for which function declares the `CallFunc_*` local.
* `LogJson` names a failing property verbatim; `Invalid asset path for` names unresolvable ids.

## Standing rules

`docs/method-rules.md` governs. Label every claim **[M]/[I]/[S]**. Name the instrument and its
coverage before recording any negative, and run a positive control that must pass plus a negative
control that must fail. **Never let a subagent commit or push.** Prefer data/bytecode writes over
`.text` writes client-side.
