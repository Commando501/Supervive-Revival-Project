# The client-config feature toggles — the UI's own gate vocabulary (S120, 2026-08-15)

Ignorance-map **A-14**. Status: **the vocabulary is SETTLED and the payload is SHIPPED; the surfaces
did NOT appear.** That combination is the result, and the second half is not a failure of the
mechanism — it is a statement about companion conditions.

Everything below is **[M]** measured / **[I]** inferred / **[S]** speculative.

---

## 1. ⚠⚠ THE HEADLINE: we were serving the wrong vocabulary, into the right map

**There are TWO toggle systems and this project has only ever fed the one the UI does not read.**

| | `ULokiGameFeatureToggles::Get(ELokiGameFeatureToggle)` | `UClientConfigManager::IsFeatureEnabled(FString, bool)` |
|---|---|---|
| keyed by | **enum member** | **string** |
| names live in | the exe (UHT enum name table, `.rdata 0x0894B1C8`–`0x0894BE90`) | **Blueprint bytecode in the paks** |
| readiness | per-PlayerController, set at **round-start** (S85) | read straight from our served `featureToggles` |
| what we served, S73→S120 | **all five keys** | **nothing, ever** |

[M] All five keys `handleClientConfig` shipped — `CursorCharacterAim`, `AttachAudioListenerToHero`,
`DeadSpectatorCameraLock`, `WinterEvent`, `BonfireUAVs` — are `ELokiGameFeatureToggle` **enum member
names**, present in the exe's enum cluster. [M] `LobbyRewards` **does not appear in the binary at
all** — which is why no amount of binary scanning ever found these keys, and why
`WBP_UI_LobbyRewards` has logged **zero activations in this project's history**.

★ **Side effect: ignorance-map A-2 is answered.** The authoritative enum list is
`tools/re/out/game_feature_toggle_enum.txt` — **149 real members** (values 0–148). The declaration
reads `(151 values)` because it counts `Count=149` and `ELokiGameFeatureToggle_MAX=150`, which are
not features. ⚠ **State the unit: 149 toggles, 151 enum values.** Two sloppy extractions gave 176
(a binary window contaminated with neighbouring reflected names) and 155 (a parse that ran into the
next enum) before the assertion `len == 149` pinned it.

---

## 2. The complete string-key vocabulary [M]

Recovered by exhaustive `bpdump` over **every UFunction** of the 21 assets that call
`IsFeatureEnabled`. **UNIT: 30 bytecode call sites / 26 declared
`CallFunc_IsFeatureEnabled_ReturnValue` locals / 10 distinct keys.** (A local can back more than one
call site — that is the whole 30-vs-26 gap.)

★★ **`bDefault` IS THE SECOND ARGUMENT, and it decides whether serving a key can do anything at all:**

    bool UClientConfigManager::IsFeatureEnabled(FString ToggleKey, bool bDefault)
        (signature from tools/asdump/out/binds_members.csv:39080)

| key | bDefault | sites | gates | verdict |
|---|---|---|---|---|
| `motd` | false | 2 | Message of the Day (`Get Message of the Day`, `Try Show MOTD`) | lever |
| `LobbyRewards` | false | 1 | the multi-claim reward screen | lever, **AND-ed** |
| `exchangetokens` | false | 6 | storefront STORAGE nav + the three 2024 supporter packs + currency-tile predicate | lever |
| `ArmoryOnboarding` | false | 2 | armory FTUE highlight flow | lever |
| `ArmoryItemProgression` | false | 10 | star-level value picker; primer content switch | weak |
| `SeasonalBattlepass` | false | 1 | EoG seasonal pass | **risky** |
| `BypassTutorialAndOnboarding` | false | 1 | *skips* onboarding | not a surface |
| `EmoteSFX` | **true** | 2 | emote SFX | **never send** |
| `KillStreakAsRomanNumeral` | **true** | 1 | streak numerals | **never send** |
| `voicechat` | **true** | 1 | voice-chat settings confirm | **never send** |

⚠ **The three `bDefault=true` keys are already ON without us. Sending them can only ever turn
something OFF.** They are deliberately excluded from the served set.

⚠ `LobbyRewards` is AND-ed with `Array_Length(Rewards) > 0`; `Rewards` is filled by
`BeginMultiClaimRewardFlow`. The key is **necessary, not sufficient**.

⚠ `ArmoryItemProgression` is **two different things**: in
`Comp_PlayerController_ArmoryOnboardingNoProgression` it is **INVERTED** (true *suppresses*), and in
the four armory widgets it is not a visibility gate at all but a `SelectInt` value picker.

---

## 3. What shipped

`server/internal/loki/loki.go` `handleClientConfig` now also serves, as
`{"config":{"default":"true"}}`: **`motd`, `LobbyRewards`, `exchangetokens`, `ArmoryOnboarding`,
`ArmoryItemProgression`**. eTag bumped `supervive-revival-3-fk17banner` →
`supervive-revival-4-uitoggles` (the handler's own comment warns an unchanged eTag can be a silent
no-op). **Knob: `AGS_UI_TOGGLES=0` restores the pre-S120 payload exactly, no rebuild.**

Deliberately NOT sent: the three `bDefault=true` keys (above), `BypassTutorialAndOnboarding` (would
skip onboarding), and `SeasonalBattlepass` (CLAUDE.md records no packed `LokiDataAsset_Season`, so
switching it on invites a hard error rather than a new surface — test it alone if at all).

---

## 4. ⚠ THE RESULT: applied, but NO new surface appeared

[M] **The client fetched and applied the new config four times** in a fresh session
(`LogClientConfig: Fetched client configuration: ETag supervive-revival-4-uitoggles`). [M] Both a
**live re-poll** (~5 s after `ags` restarted, no relaunch) and a **cold relaunch** were tried.

[M] Leaf-most UI nodes after a cold relaunch to the menu are **identical to the baseline**:
`Login_Screen_Default`, `MainMenu_AwaitingIntro`, `MainMenu_MenuRootV2`,
`LobbyCarousel_LaunchBanner`, `ProgressionTrackerBaseV2`. `MessageOfTheDay` **0**, `MOTD` **0**,
`LobbyRewards` **0**, `RewardRoll` **0**, `Onboarding` **0**.

⚠⚠ **HONEST LIMIT — this is NOT a measured negative on the toggles.** There is **no readout that
`IsFeatureEnabled("motd")` returned true**; the only thing measured is that the document was applied.
A surface can be dark because the flag is off *or* because its companion condition is unmet, and
nothing here discriminates them. Do not record "serving the toggles does nothing" — record "serving
them changed no observable surface at the menu, cause unresolved."

**Plausible companion conditions, unresolved:**
- `motd` — `Try Show MOTD` likely needs actual MOTD content; we answer `/mailbox/config/version` but
  serve no message body.
- `LobbyRewards` — needs `Rewards.Num > 0`, filled by `BeginMultiClaimRewardFlow`. Hero-mastery
  rewards are currently **auto-claimed natively without this widget** (`docs/s120-hero-mastery.md`).
- `exchangetokens` — gates the STORE tab's STORAGE nav button and the supporter packs; that widget
  only builds when the STORE is opened, which needs navigation.
- `ArmoryOnboarding` — lives on a `Comp_PlayerController_*` component, and no extracted asset
  attaches either onboarding component to a PlayerController, so it may be in-match only.

**Cheapest next discriminators**, in order:
1. **Open the STORE tab** and look for a STORAGE nav button / 2024 supporter packs. One click, and
   `exchangetokens` is the least-conditional of the five (two of its six sites have no companion at
   all — a direct `SetVisibility`/`SetIsEnabled` pass-through).
2. Serve a MOTD body and re-check `motd`.
3. Build a readout: nothing in this project can currently observe a Blueprint `IsFeatureEnabled`
   result. A shim that logs the call would make every future toggle question a measurement instead
   of an inference.
