# S121 — the per-key SURFACE MAP for the 16 served client-config feature toggles

**Pure offline asset analysis.** No launch, no injection, no process attach. Every number below
comes from `tools/extractor/out` (69,178 JSON exports) or from `bpdump_*.txt` files already present
in `tools/extractor/out` from earlier sessions. Nothing outside `scratchpad/` was written.

Labels: **[M]** measured · **[I]** inferred · **[S]** speculative.

Scripts: `scan_toggles.py` (full-corpus instance census, writes `toggle_instances.json`),
`_detail.py`, `_vis.py`, `_xref.py`/`_xref2.py`/`_xref3.py`, `_countkeys.py`.

---

## 0. ⚠⚠ SAFETY — READ FIRST

### 0.1 ★★★★★ WE **ARE** TURNING THREE CURRENTLY-VISIBLE SURFACES OFF — and not via `IsEnabledByDefault`

[M] The hazard is **not** `IsEnabledByDefault:true`; it is a **per-instance inversion of
`EnabledVisibility` / `DisabledVisibility`**, which the S120 census never looked at. The CDO
default is `EnabledVisibility = SelfHitTestInvisible`, `DisabledVisibility = Collapsed`. **Three
instances of served keys ship those two values SWAPPED**, so `enabled == true` *collapses* them:

| asset | instance | key (served) | EnabledVis | DisabledVis | effect of serving `true` |
|---|---|---|---|---|---|
| `WBP_UI_ArmoryCardSmall_Base` | `ArmoryNoProgression` | `ArmoryItemProgression` | **Collapsed** | SelfHitTestInvisible | **HIDES** `ItemLockedLevel` (SizeBox) |
| `WBP_UI_Collection_ModalV2` | `ArmoryHeader` | `ArmoryItemProgression ` (trailing space) | **Collapsed** | SelfHitTestInvisible | **HIDES** the plain armory header `HorizontalBox` |
| `WBP_UI_GameItemTooltip` | `ArmoryHJUnlock` | `ArmoryItemProgression ` (trailing space) | **Collapsed** | SelfHitTestInvisible | **HIDES** `HJUnlockLevel` (CommonRichTextBlock) |

[I] Two of the three are **A/B pairs, not deletions**: `WBP_UI_Collection_ModalV2` also carries
`ArmoryHeaderWithProgression` (same key, *normal* polarity) wrapping `HorizontalBox_0`, so serving
`true` **swaps** which header renders rather than blanking the modal. `ArmoryNoProgression` /
`ArmoryHJUnlock` have no visible partner in their own asset, so those two look like genuine
removals of a currently-drawn element.

⇒ **This is a real behaviour change we are already shipping**, and it is invisible unless you know
to look. It is *probably* the designers' intent (the instances are literally named
`…NoProgression`), but it is not "reveal a dark surface" — it is "hide a lit one".
**If a screenshot of the armory/cosmetics modal or an item tooltip looks *poorer* than before, this
is why — not a regression elsewhere.**

For completeness, the same inversion exists on three **unserved** keys — `CustomGameList`
(`WBP_ActivityPickerScreen/ClientCustomGameListToggleOff`) and `BypassTutorialAndOnboarding`
(`WBP_UI_PracticeSettingsHunterPanel/ChallengeHubVisibilityToggle`), both `IsEnabledByDefault=true`
/ absent respectively. `party.fill` and `RankedDisplay` override only `DisabledVisibility`
(→ `Hidden` instead of `Collapsed`) — layout-preserving, polarity normal.

### 0.2 ★★ `mastery` IS MIS-CLASSIFIED AS A DARK KEY — 2 of its 3 sites were already lit

[M] `mastery` has **three** declarative sites and **two of them declare `IsEnabledByDefault: true`**:

| asset | instance | wraps | IsEnabledByDefault |
|---|---|---|---|
| `WBP_UI_HeroInfo_Party` | `WBP_UI_ClientConfigVisbilityToggleWidget` | `MasteryButton` (Button) | **true** |
| `WBP_UI_PartyHeroSelect` | `Mastery_ConfigToggle_1` | `NavButton_MasteryV2` | **true** |
| `WBP_UI_HeroPortrait` | `WBP_UI_ClientConfigVisbilityToggleWidget` | `WBP_HeroMastery_LevelIcon` | *absent → false* |

We serve `"true"`, so **nothing turns off today**. Two consequences:
1. **`mastery` cannot be confirmed by a dark→lit observation** at the MASTERY nav button or the
   party mastery button — those were visible *before* the fix (which is consistent with S120's
   screenshot-confirmed HUNTERS → MASTERY page). The **only** real lever is the hero-portrait
   level icon.
2. ⚠ **Latent hazard:** anyone who ever serves `mastery=false` (e.g. as an A/B control) will
   **remove the MASTERY nav button and the party mastery button** — i.e. it would look like the
   S120 hero-mastery work regressed. Do not use `mastery` as a knob.

### 0.3 No other served key has `IsEnabledByDefault: true` at any declarative site

[M] Across all **83** toggle instances, **49** declare `IsEnabledByDefault: true`. Intersected with
the 16 served keys, the *only* hits are the two `mastery` sites above. All other served keys are
absent-or-false at every site. ✅

### 0.4 ⚠ COUNT CORRECTION: the served UI set is **16 keys, not 17**

[M] `server/internal/loki/loki.go`, the `AGS_UI_TOGGLES` loop, contains **16** string literals
(machine-counted, `_countkeys.py`), plus **5** in the base `featureToggles` map = **21 map entries
served**. `docs/s120-feature-toggles.md` §5 says "17 dark keys + the original 5"; that 17 is wrong.
**UNIT: 16 keys in the loop / 21 total `featureToggles` entries / 50 distinct declarative
FeatureKeys corpus-wide / 83 declarative instances / 49 assets.**

---

## 1. Census, and the instrument note that matters

[M] **83 toggle instances** of `WBP_UI_ClientConfigVisbilityToggleWidget_C` across **49 assets**
(files scanned: 69,178; CDO of the toggle asset itself excluded). **82** override `FeatureKey`;
**50 distinct keys**.

⚠⚠ **INSTRUMENT ARTIFACT, caught here — a naive grep undercounts by 49×.** Serialized property
names in this extractor's JSON carry an **array-index suffix**: the key is `"FeatureKey[2]"`, not
`"FeatureKey"`. `rg -l '"FeatureKey"'` over the whole corpus returns **1 file** (the class asset,
whose `ChildProperties` name it unsuffixed) — it structurally cannot see a single instance.
Match by **prefix** (`FeatureKey[`), or grep the bare token. Also: `tools/extractor/out` is
git-ignored, so plain `rg` **skips it entirely** unless you pass `--no-ignore`; without that flag
every scan here returns zero and reads like a clean negative.

★ **[M] ZERO of the 83 instances override `ConfigKey`.** Every one inherits the CDO's `"enabled"`.
That is an independent, corpus-wide confirmation of S120 §5's fix: **`"enabled"` is the only
sub-key the declarative layer ever reads**, at every site, with no exceptions to hunt for.

[M] CDO of `WBP_UI_ClientConfigVisbilityToggleWidget_C`:
`ConfigKey="enabled"`, `EnabledVisibility=SelfHitTestInvisible`, `DisabledVisibility=Collapsed`,
`FeatureKey` **absent** (empty), `IsEnabledByDefault` **absent** (false), plus an
`OnEnabledChanged` multicast delegate and a single `NamedSlot`.

[M] The ubergraph binds `OnClientConfigUpdated` on `UClientConfigManager` (statements 3–5 of
`bpdump_ExecuteUbergraph_WBP_UI_ClientConfigVisbilityToggleWidget.txt`) ⇒ **live re-evaluation
without a relaunch**, confirming S120's pre-registered prediction is at least mechanically
possible.

★ **Dead-by-authoring:** `WBP_UI_Collection_ModalV2 / ArmoryWithProgressionHelper` has **no
FeatureKey at all** → `Map_Find(FeatureToggles, "")` always misses → falls back to absent
`IsEnabledByDefault` → its `Helper` Overlay is **permanently Collapsed** in every build. Not a
lever; do not chase it.

---

## 2. THE STORE NAV BAR — complete, verified, and predicted

### 2.1 S120 §5's three-row table is **correct but incomplete — there is a FOURTH toggle**

[M] `WBP_UI_Storefront_Root` contains **four** `WBP_UI_ClientConfigVisbilityToggleWidget_C`
instances, not three. The missing one is the default-named instance gating the cheat button:

| instance | FeatureKey | ConfigKey | IsEnabledByDefault | wraps | parent slot |
|---|---|---|---|---|---|
| `PacksConfigToggle_1` | `supporterpacks` | *(CDO `enabled`)* | **true** | `NavButton_PacksV2` | `HBox_NavButtons.HorizontalBoxSlot_1` |
| `RedeemConfigToggle_1` | `redeemcode` | *(CDO)* | **true** | `NavButton_RedeemV2` | `HBox_NavButtons.HorizontalBoxSlot_0` |
| `StorageConfigToggle_1` | `exchangetokens` | *(CDO)* | *absent → false* | `NavButton_StorageV2` | `HBox_NavButtons.HorizontalBoxSlot_5` |
| **`WBP_UI_ClientConfigVisbilityToggleWidget`** | **`storefrontcheats`** | *(CDO)* | *absent → false* | **`Cheat_TopUp`** (`WBP_UI_NavBar_Button_C`, text `TOP UP`) | **`Overlay_0.OverlaySlot_2`** — *not* the nav row |

S120's three rows are reproduced exactly. ✅ (Independent re-derivation, different script.)

### 2.2 ★★★★★ PREDICTED STORE NAV BAR, left → right

[M] Order is `HBox_NavButtons.Slots[]` in serialization order; [I] UMG lays a `UHorizontalBox` out
in `Slots[]` order left→right. [M] labels are the instances' `Text` `SourceString`; [M]
`WBP_UI_NavBar_ButtonSecondaryV2`'s `Text_Label` has
`TextTransformPolicy = ETextTransformPolicy::ToUpper`, so **every label renders UPPERCASE**.

| # | slot | widget | rendered label | target screen | gate | expected NOW (we serve `exchangetokens=true`) |
|---|---|---|---|---|---|---|
| 1 | `HorizontalBoxSlot_2` | `NavButton_StoreV2` | **FEATURED** | `WBP_UI_Storefront_Featured` | **none** | visible |
| 2 | `HorizontalBoxSlot_7` | `NavButton_Bundles` | **BUNDLES** | `WBP_UI_Storefront_SkinsBundles` (`Screen_Bundles`) | **none** | visible |
| 3 | `HorizontalBoxSlot_3` | `NavButton_Skins` | **SKINS** | `WBP_UI_Storefront_SkinsBundles` (`Screen_Skins`) | **none** | visible |
| 4 | `HorizontalBoxSlot_4` | `NavButton_Accessories` | **ACCESSORIES** | `WBP_UI_Storefront_Accessories` | **none** | visible |
| 5 | `HorizontalBoxSlot_1` | `PacksConfigToggle_1` → `NavButton_PacksV2` | **SUPPORTER PACKS** | `WBP_UI_Storefront_Packs` | `supporterpacks`, default **true** | visible (was already) |
| 6 | `HorizontalBoxSlot_5` | `StorageConfigToggle_1` → `NavButton_StorageV2` | **STORAGE** | `WBP_UI_Inventory_Storage` | `exchangetokens`, default **absent/false** | ★ **NEW — this is the one under test** |
| 7 | `HorizontalBoxSlot_0` | `RedeemConfigToggle_1` → `NavButton_RedeemV2` | **REDEEM** | `WBP_UI_Storefront_Redeem` | `redeemcode`, default **true** | visible (was already) |

**Off the rail, in the root Overlay:** `Cheat_TopUp`, label **TOP UP**, gated by `storefrontcheats`
(default absent → false). We serve it, so it should **also newly appear** — position is
`Overlay_0.OverlaySlot_2`, i.e. an overlay layer above the store body, **not** a 8th nav-bar entry.

⇒ **Prediction: the STORE nav bar reads
`FEATURED · BUNDLES · SKINS · ACCESSORIES · SUPPORTER PACKS · STORAGE · REDEEM`, seven entries,
with STORAGE newly present between SUPPORTER PACKS and REDEEM; plus a TOP UP button somewhere in
the store overlay.** Before the fix it was the same list **minus STORAGE and minus TOP UP** (five
nav entries + SUPPORTER PACKS + REDEEM = 6).

### 2.3 `exchangetokens` is the least-conditional key we serve — **four independent gates, all reading it, none AND-ed with anything we don't control**

[M] The declarative wrapper is only one of four. `bpdump_ExecuteUbergraph_WBP_UI_Storefront_Root.txt`
adds **three bytecode call sites**, all `IsFeatureEnabled("exchangetokens", /*bDefault=*/false)`:

| stmt | what it does | companion |
|---|---|---|
| [23]→[25] | `NavButton_StorageV2->SetVisibility(select(flag))` | **none** — direct pass-through |
| [27]→[28] | `NavButton_StorageV2->SetIsEnabled(flag)` | **none** — direct pass-through |
| [46]→[47]→[48] | `flag **OR** IsNexonEnabled()` → binds `OnUpdatedPlayerInventory`, then [52] `NavButton_StorageV2->SetVisibility(0 /*Visible*/)` + [53] `SetIsEnabled(true)`; else-branch [60]/[61] `SetVisibility(1 /*Collapsed*/)` + `SetIsEnabled(false)`, and [62] forces `NavButton_PacksV2` Visible | **OR**, not AND ⇒ our key alone suffices |

[M] `NavButton_RedeemV2` and `Cheat_TopUp` are **never touched by the ubergraph** — they are gated
by their declarative wrapper and nothing else. [M] `FEATURED / BUNDLES / SKINS / ACCESSORIES` are
touched by nothing: ungated in both the widget tree and the bytecode.

[M] Two further `exchangetokens` bytecode sites live one level down, both `flag OR IsNexonEnabled()`:
- `WBP_UI_Storefront_Packs` [23]–[26] → gates `SetOfferAsset` on `WBP_UI_Storefront_Pack`, `_1`, `_2`
  (the **three supporter packs**).
- `WBP_UI_Storefront_CurrencyOfferItem` [21]–[24] → gates a currency-tile predicate.

**Total `exchangetokens` footprint [M]: 1 declarative site + 5 bytecode call sites across 3 assets.**
(S120's "6 sites" is the bytecode count; it did not include the declarative wrapper. Unit matters.)

★ **Because slot 6 sits between two buttons that were already visible, the STORAGE button is a
high-contrast observable: its presence/absence changes the nav bar's arity from 6 to 7 without
moving anything else.** A screenshot answers it unambiguously.

---

## 3. The full per-key surface map

`clicks` = mouse clicks from the lobby main menu (the screen you land on after login) to make the
gated element *drawable*. `0` = it is on the lobby screen itself.

| key | asset(s) | widget instance | gated content | screen / where | clicks | IsEnabledByDefault | companion condition |
|---|---|---|---|---|---|---|---|
| **`exchangetokens`** | `WBP_UI_Storefront_Root` (+`_Packs`, +`_CurrencyOfferItem`) | `StorageConfigToggle_1` (+3 bytecode sites here, +2 below) | **STORAGE nav button** → `WBP_UI_Inventory_Storage`; the 3 supporter packs; currency tile | STORE | **1** (main nav → STORE) | absent → false | **none** on the nav button (2 direct pass-throughs); the other 3 sites are `OR IsNexonEnabled()` — an OR, so still sufficient |
| **`storefrontcheats`** | `WBP_UI_Storefront_Root` | `WBP_UI_ClientConfigVisbilityToggleWidget` | **TOP UP** button (`Cheat_TopUp`) in the store overlay | STORE | **1** | absent → false | **none** — declarative only, zero bytecode |
| **`DebugBattlepass`** | `WBP_UI_MainMenu_NormalMainMenu` | `WBP_UI_ClientConfigVisbilityToggleWidget_3` | `NavButtonMain_DebugBattlepass` (a primary nav button) | **lobby left nav, LAST entry** | **0** | absent → false | **none** |
| **`NeLobbyEventBtn`** | `WBP_UI_MainMenu_NormalMainMenu` | `WBP_UI_ClientConfigVisbilityToggleWidget` | `WBP_LobbyEventEntryBtn` | **lobby left nav, FIRST entry (above HUNTERS)** | **0** | absent → false | none in the tree; [S] the button may self-hide with no event data |
| **`leaderboards`** | `WBP_ProfileScreen` ×2 | `NavLeaderboard_ConfigToggle_1`; `LeaderboardScreen_ConfigToggle` | **LEADERBOARDS** nav button (4th) **and** the `WBP_Leaderboard_Screens` page it switches to | CAREER | **1** (main nav → CAREER) | absent → false ×2 | **none** |
| **`discord`** | `WBP_UI_SocialFriendsBar`; `WBP_UI_AccountSettingsPanel`; `WBP_UI_UserInterface_SettingsPanel` | `…_58`; `…`; `…_109` | `WBP_UI_Discord_AuthorizeButton`; `VerticalBox_Discord`; `Config_ChatAllHideDiscordFriendDirectMessages` switch | friends sidebar [I lobby-resident]; SETTINGS→ACCOUNT (tab 8/9); SETTINGS→UI (tab 7/9) | **0–1** / **2** / **2** | absent → false ×3 | **none** at any site |
| **`mastery`** | `WBP_UI_HeroPortrait`; `WBP_UI_HeroInfo_Party`; `WBP_UI_PartyHeroSelect` | `…`; `…`; `Mastery_ConfigToggle_1` | `WBP_HeroMastery_LevelIcon`; `MasteryButton`; `NavButton_MasteryV2` | HUNTERS / party hero-select | **1** | **false / TRUE / TRUE** | ⚠ see §0.2 — only the level icon is a lever |
| **`CosmeticEffectsOverride`** | `WBP_Loadout_StyleScreen_VariantPicker` | `WBP_UI_ClientConfigVisbilityToggleWidget` | `WBP_Loadout_VariantPicker_Luxe` (a variant row) | CUSTOMIZATION → hero → Style screen (also reachable from a store item-details preview) | **3** | absent → false | none in the tree; requires a hero **with a Luxe variant** selected [I] |
| **`ServerSelectRegionRoutes`** | `WBP_UI_RegionSelect_Entry` | `WBP_UI_ClientConfigVisbilityToggleWidget` | `VBox_RegionRoutes` | region-select modal, opened from the PLAY / activity-picker screen (`WBP_ActivityPickerScreen` references `WBP_UI_RegionSelect_C`) or the ESC dialog | **2–3** | absent → false | none in the tree; needs ≥1 region entry to render into |
| **`ServerSelectNetworkAcceleration`** | `WBP_UI_RegionSelect_Entry` | `…_89` | `UI_RegionSelect_Entry_NetworkAcceleration` | same modal | **2–3** | absent → false | same |
| **`ArmoryItemProgression`** | 7 assets | see §4 | mixed: gem button, prisma display, EOG gems, stat line, item-locked badge, armory nav | 2 lobby-side (behind the ARMORY nav) + 5 **in-match** | 2+ / ∞ | absent → false ×7 | ⚠ **one INVERTED site** (§0.1); lobby sites sit behind the ARMORY nav, which is gated by a *different* toggle family (`WBP_UI_ArmoryEnablement_VisibilityToggle_C`) |
| **`ArmoryItemProgression `** (trailing space) | 3 assets, 4 sites | `ArmoryHeader`, `ArmoryHeaderWithProgression`, `ArmoryHJUnlock`, `ArmoryForgeToggle` | cosmetics-modal header pair; tooltip HJ-unlock line; `BtnGoCraft` on the reward-roll screen | COSMETICS/Armory modal; in-match tooltip; reward-roll screen (pushed from `WBP_UI_MainMenu_MenuRootV2`) | 2+ | absent → false ×4 | ⚠ **two INVERTED sites** (§0.1) |
| **`DropScreenTitles`** | `WBP_UI_PredropScreen_PlayerEntry` | `CallSignVisibilityToggle` | `WBP_UI_Personalization_PlayerTitle` | **pre-drop screen, in-match only** (`…_PlayerEntry` → `WBP_PredropScreen_TeamEntry` → `WBP_UI_PredropScreen` → `WBP_UI_HUD_GameFlow_StateMachine`) | **unreachable from lobby** | absent → false | needs a served player TITLE to draw |
| **`motd`** | *(bytecode only — 0 declarative sites)* `Comp_MainMenu_Onboarding` (`Try Show MOTD`), `WBP_UI_Menus_MessageOfTheDay` (`Get Message of the Day`) | — | the MOTD prompt, `PushPrompt(WBP_UI_Menus_MessageOfTheDay_C)` | lobby, auto-pushed | **0** *if it fires* | n/a (`bDefault=false`) | ★★ **HARD companion — see §5. It needs three MORE `Config` sub-keys we do not serve.** |
| **`LobbyRewards`** | *(bytecode only)* `WBP_UI_LobbyRewards` (`ShouldShowLobbyRewards`) | — | the multi-claim reward screen | lobby (`WBP_UI_MainMenu_MenuRootV2`) | **0** *if it fires* | n/a | [M] `return Rewards.Num > 0 **AND** IsFeatureEnabled("LobbyRewards", false)` — **strict AND, cannot be confirmed dark** |
| **`ArmoryOnboarding`** | *(bytecode only)* `Comp_PlayerController_ArmoryOnboarding` ×2 sites | — | `Setup Highlighting` (FTUE highlight pass) | a **PlayerController component**; only static referrer of the class is `WBP_UI_MissionModal` | **in-match [I]** | n/a | none at the branch, but the component must be attached and running |

---

## 4. `ArmoryItemProgression` — all 11 sites, split by reachability

**Clean key (7 sites):**

| asset | instance | wraps | reachable |
|---|---|---|---|
| `WBP_UI_Collection_Screen` | `ArmoryWithProgressionNav` | `HorizontalBox` (nav) | lobby → ARMORY (behind ArmoryEnablement gate) |
| `WBP_UI_ArmoryCardSmall_Base` | `ArmoryNoProgression` ⚠**INVERTED** | `ItemLockedLevel` (SizeBox) | lobby → ARMORY → items grid; also in-match stash |
| `WBP_UI_SkylandsShop` | `PrismaShopToggle` | `PrismaDisplay` (HorizontalBox) | **in-match** (Skylands shop) |
| `WBP_UI_HUD_Currencies` | `ArmoryProgression` | `WBP_UI_GemButton` | **in-match** HUD top-right |
| `WBP_UI_PlayerStatLine` | `ArmoryProgressionToggle` | `TeamPrisma` (VerticalBox) | **in-match** HUD top-right |
| `WBP_UI_HUD_Screen_EOG_V3` | `ArmoryProgressionToggle` | `ARMORYONLY_WBP_UI_EoG_GemsGained` | **end-of-game only** |
| `WBP_UI_HUD_Screen_PlacementAnnounce_v2` | `ArmoryProgressionToggle` | `VerticalBox_757` | **in-match**, placement announce |

**Trailing-space key (4 sites):** `WBP_UI_Collection_ModalV2 / ArmoryHeader` ⚠**INVERTED**,
`WBP_UI_Collection_ModalV2 / ArmoryHeaderWithProgression`, `WBP_UI_GameItemTooltip / ArmoryHJUnlock`
⚠**INVERTED**, `WBP_UI_RewardRoll_Base / ArmoryForgeToggle` (`BtnGoCraft`).

[M] `Comp_PlayerController_ArmoryOnboardingNoProgression` adds **2 bytecode** sites on the *clean*
key, both `IsFeatureEnabled("ArmoryItemProgression", false)` → gate `HighlighterWidget` work. That
component's only static referrer is `WBP_UI_PendingArmoryItems`.

⇒ **`ArmoryItemProgression` is the worst key on the board to try to observe**: 11 declarative +
2 bytecode sites, three of them inverted, most in-match, and the lobby ones behind a second,
unrelated gate. Do not spend a screenshot on it.

---

## 5. ★★★★ `motd` — the exact recipe, recovered offline

[M] From `bpdump_Try Show MOTD.txt` (`Comp_MainMenu_Onboarding_C`), the chain is:

```
[1]  IsFeatureEnabled("motd", false)                      -> [2] JumpIfNot   (bail)
[6]  Map_Find(cfg.FeatureToggles, "motd")                 -> [7] JumpIfNot   (bail)
[13] Map_Find(entry.Config, "key")                        -> [14] JumpIfNot  (bail)   <-- ★
[19] lastSeen = GetLokiGameUserSettings()->GetMessageOfTheDayLastSeen()
[23] NotEqual_StriStri(Config["key"], lastSeen)           -> [24] JumpIfNot  (bail)
[25] MainMenuWidget->PushPrompt(WBP_UI_Menus_MessageOfTheDay_C, false)
```

⇒ ★★★ **`motd`'s `Config` map needs a `"key"` sub-key — a THIRD spelling we have never served.**
`"enabled"` alone gets past the first gate and then dies silently at `[14]`.

[M] `bpdump_Get Message of the Day.txt` reads three sub-keys off the same entry —
**`key`**, **`title`**, **`text`** — the last two through `Conv_StringToText`. So the full schema is:

```json
"motd": { "config": {
    "enabled": "true", "default": "true",
    "key":   "revival-motd-1",
    "title": "<headline>",
    "text":  "<body>"
} }
```

⚠ `Config["key"]` must differ from `GetMessageOfTheDayLastSeen()`, which the client persists in
`LokiGameUserSettings` — so **the same `key` shows the prompt exactly once per machine.** Bump the
`key` string to re-show it. That also means a null on a re-test is uninterpretable unless you
changed the key. [I] `bDefault` is `false` at both `motd` call sites, so we are not turning
anything off.

⇒ This closes S120 §4's open item #2 ("serve a MOTD body and re-check") with a measured schema
rather than a guess. **[S]** the native `UClientConfigManager::IsFeatureEnabled` presumably reads
`Config["enabled"]` too (we serve both `enabled` and `default`, so both plausible spellings are
covered), but that is not measured — it is native, not bytecode.

---

## 6. RANKING — cheapest to observe (excluding `exchangetokens`)

### Tier 0 — **zero clicks, visible on the lobby screen itself**

1. ★★★ **`DebugBattlepass`** — `NavButtonMain_DebugBattlepass` (label `Debug Battlepass`), the
   **last** entry of the lobby's main left nav (`VerticalBox_83`, child index 8). Zero companion
   conditions, one declarative wrapper, no bytecode. **This was the single cheapest key on the
   board, and it has since been confirmed live — see §8.**
2. ★ **`NeLobbyEventBtn`** — `WBP_LobbyEventEntryBtn`, the **first** entry of that same nav
   (child index 0, above HUNTERS). Free with any lobby screenshot. [S] risk: the event button may
   self-hide without event data — and §8 records that it did **not** appear in the run that
   confirmed `DebugBattlepass`, so this key now looks *companion-gated*, not free.

Full lobby left-nav order [M] (`WBP_UI_MainMenu_NormalMainMenu.VerticalBox_83`, top→bottom):
`[NeLobbyEventBtn toggle] · HUNTERS · [ArmoryEnablement toggle→ARMORY] · PASSES · CUSTOMIZATION ·
STORE · CAREER · [DebugNav toggle→DEBUG] · [DebugBattlepass toggle→DEBUG BATTLEPASS]`.

### Tier 1 — one click

3. ★★ **`leaderboards`** — main nav → **CAREER**. Nav bar there is
   `HISTORY · STATS · RANKED · [leaderboards]LEADERBOARDS` [M, `WBP_ProfileScreen.HorizontalBox`
   slot order]. Both the button *and* the page it switches to are wrapped, no companion condition
   anywhere. Clean 4-of-4 arity change, exactly like the STORE case.
4. **`storefrontcheats`** — same STORE screenshot you are already taking for `exchangetokens`:
   a **TOP UP** button in the store overlay. **Free** — costs zero extra clicks.
5. **`discord`** — the friends sidebar's Discord authorize button [I lobby-resident; if the
   sidebar needs opening, 1 click]. Its two settings-panel siblings are 2 clicks (ESC/settings →
   ACCOUNT tab 8, → UI tab 7). Settings tab order [M]: GAME, KEYBINDS, VIDEO, AUDIO, VOICE,
   CAMERA, UI, ACCOUNT, EMOTES.

### Tier 2+ / unreachable — do not spend screenshots

- `mastery` — 1 click but **2 of 3 sites were already lit** (§0.2); only the hero-portrait level
  icon discriminates, and it is small.
- `CosmeticEffectsOverride` — 3 clicks and needs a hero that *has* a Luxe variant.
- `ServerSelect*` ×2 — 2–3 clicks into the region modal, needs ≥1 region entry.
- `ArmoryItemProgression` (both spellings) — see §4; mostly in-match, three sites inverted, lobby
  sites behind a second gate.
- `DropScreenTitles` — **pre-drop screen, in-match only. Unreachable from the lobby.**
- `ArmoryOnboarding` — PlayerController component, in-match [I].
- `LobbyRewards` — **AND-ed with `Rewards.Num > 0`; a dark surface proves nothing.**
- `motd` — will stay dark until §5's `key`/`title`/`text` are served; today's null is
  uninterpretable, not negative.

**⇒ One screenshot of the lobby + one of the STORE + one of CAREER covers 5 of the 16 keys
(`DebugBattlepass`, `NeLobbyEventBtn`, `exchangetokens`, `storefrontcheats`, `leaderboards`) with
zero companion-condition ambiguity, and carries its own positive control (`DebugNav`).**

---

## 7. Method notes worth keeping

1. **Serialized property keys carry `[N]` suffixes** in this extractor's JSON. `"FeatureKey"` finds
   1 file; `FeatureKey` finds 50. A 49× undercount that returns a *plausible* answer.
2. **`rg` skips `tools/extractor/out` by default** — it is git-ignored. `--no-ignore` is mandatory
   for every scan of the extracted catalog. Without it, a full-corpus scan reports a clean zero.
3. **Visibility POLARITY is a per-instance property, not a constant.** The S120 census read
   `FeatureKey`/`ConfigKey`/`IsEnabledByDefault` and stopped; `EnabledVisibility`/
   `DisabledVisibility` are equally per-instance and three served sites invert them. **Any future
   "is it safe to serve X" check must read all five properties.**
4. **A `bDefault=true` bytecode key and an `IsEnabledByDefault=true` declarative site are different
   objects.** `mastery` is `true` declaratively at 2 of 3 sites and appears in neither of S120's
   "never send" lists — the two vocabularies were audited separately and the union was never taken.
5. `WBP_UI_ArmoryEnablement_VisibilityToggle_C` is a **second, parallel declarative toggle family**
   with the same shape (`EnabledVisibility`/`DisabledVisibility`/`OnEnabledChanged`/`NamedSlot`) but
   **no `FeatureKey`** — it is not client-config-driven. It gates the ARMORY main-nav entry and the
   armory screen wrapper. Do not confuse the two when reading a lobby screenshot.

---

## 8. Reconciliation with the live run (`docs/s121-toggle-fix-confirmed.md`, 2026-08-15 16:13)

Written *after* this map was derived; the map's §2.2 prediction was made from the assets alone.

### 8.1 ✅ The STORE nav-bar prediction MATCHED exactly

[M, theirs] Observed left→right: `FEATURED · BUNDLES · SKINS · ACCESSORIES · SUPPORTER PACKS ·
STORAGE · REDEEM`. That is §2.2 row-for-row, seven entries, STORAGE newly present between SUPPORTER
PACKS and REDEEM. Their `WBP_UI_Inventory_Storage` content readout (`STORAGE` heading,
`No items in storage.`, `CONFIRM ALL PURCHASES`) is the widget §2.2 names as slot 6's target. ✅

### 8.2 ✅ `DebugBattlepass` confirmed, at the predicted position

[M, theirs] `DEBUG BATTLEPASS` renders on the main rail **below CAREER** — child index 8 of
`VerticalBox_83`, exactly where §6 tier-0 #1 placed it.

### 8.3 ⚠⚠ TWO ANOMALIES IN THEIR OWN READING — DO NOT LET THESE PASS

Their observed rail is `HUNTERS · ARMORY · PASSES · CUSTOMIZATION · STORE · CAREER ·
DEBUG BATTLEPASS` — **seven items. The asset says there should be nine.** Two are missing:

- **`DEBUG MENU` is absent, and it should not be.** [M] `NavButtonMain_Debug` (label
  `DEBUG MENU`, `CultureInvariantString`) sits at child index **7**, immediately *above*
  DEBUG BATTLEPASS, wrapped by `WBP_UI_ClientConfigVisbilityToggleWidget_2` with FeatureKey
  **`DebugNav`** and **`IsEnabledByDefault = true`**. A default-true toggle needs no backend help.
  [M] The `NormalMainMenu` ubergraph contains **no suppression** of it — it appears only in the
  ordinary 9-element intro-animation arrays (statements [21], [27]) and an `InitIntro` call
  ([455]), identical in treatment to `NavButtonMain_DebugBattlepass` at [456].
  ⇒ Either the observer omitted it, **or a default-true declarative toggle is failing to render**,
  which would mean "IsEnabledByDefault=true ⇒ already visible" — the premise the entire
  never-send-these-keys safety argument rests on — is **not reliable**. ★ **This is one glance at
  an existing screenshot to settle, and it is worth it.**
- **`NeLobbyEventBtn` produced no surface.** We serve it `true`, yet no button appears above
  HUNTERS at child index 0. [I] Most likely `WBP_LobbyEventEntryBtn` self-hides with no event
  data (its instance overrides *nothing* — `Properties: {}`), i.e. a companion condition we cannot
  see in the widget tree. **Their run's null on this key is uninterpretable, not negative.**

⇒ ★ §6's claim that `DebugNav` is a *free positive control* is **withdrawn pending 8.3**. A control
that may itself be dark is not a control. `GameVersion` (`WBP_UI_ClientConfigVisbilityToggleWidget_80`
→ `ScaleBox_VersionInfo`, `IsEnabledByDefault = true`) is the substitute: the build-version label in
the lobby corner. If the version string is on screen, default-true toggles do render.

### 8.4 The three cheapest keys still unobserved

With `exchangetokens` and `DebugBattlepass` now confirmed, the remaining cheap, companion-free
observables are, in order: **`leaderboards`** (1 click, CAREER, 4th nav button, both button *and*
page wrapped, zero companions) · **`storefrontcheats`** (0 extra clicks — it is in the STORE
screenshot they already took; look for a **TOP UP** button in the store overlay) · **`discord`**
(the friends-sidebar authorize button, 0–1 clicks).

⚠ Their §2 repeats the "17 dark keys" figure. It is **16** — see §0.4.
