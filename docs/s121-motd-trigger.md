# S121 — the MOTD chain, traced ⇒ ⚠⚠ **HEADLINE RETRACTED: IT DOES FIRE**

> ## ⚠⚠⚠ READ THIS FIRST — THE TITLE AND §§1–5 BELOW ARE WRONG ABOUT THE CONCLUSION
>
> This file was written arguing "the MOTD never fires because `Try Show MOTD` is never called."
> **A live read of the Blueprint's persistent `UberGraphFrame` (`tools/re/bpframe_readout.py`,
> built after §5) refutes that outright** [M]:
>
> ```
> +0x0C55  CallFunc_BooleanAND_ReturnValue            = True    <- BooleanAND_9, the gate at 4668
> +0x0970  CallFunc_Try_Show_MOTD_Widget              = 0x2692C618DF0
> +0x0978  CallFunc_Try_Show_MOTD_bWasShown           = True    <- ★ THE PROMPT WAS SHOWN
> +0x0000  EntryPoint                                 = 3358    <- Try Start Onboarding Flow
> ```
>
> And every term of the predicate reads TRUE on the live client — `IsValid`,
> `IsConfigurationLoaded`, `IsMatchHistoryLoaded`, `NOT GetMatchInfo`, `IsPartyValid`,
> `GetCurrentPlayerProgression`, `Array_IsNotEmpty(MissionInfo.MissionData)` — with
> `BooleanOR_2` satisfied via `Not_PreBool_3` (the toggle `Map_Find` misses ⇒ NOT ⇒ true).
> `CallFunc_Try_Show_MOTD_Widget` is the **same address** as the live
> `WBP_UI_Menus_MessageOfTheDay_C` found independently by `obj_by_class.py`.
>
> ⇒ **The backend payload, the gates, the chain and `PushPrompt` all work.** What remains is a
> DISPLAY question — the prompt was pushed and reported shown, yet the operator never saw it and
> `MessageOfTheDayLastSeen` is still empty (that field is presumably written on acknowledge, not
> on show).
>
> ### The widget is built but never PRESENTED [M]
>
> Live read of `WBP_UI_Menus_MessageOfTheDay_C` @ `0x2692C618DF0`:
>
> | property | value |
> |---|---|
> | `Visibility` | **0 = Visible** |
> | `bIsEnabled` | True |
> | `WidgetTree` | valid (`0x2692C5E1BE0`) |
> | **`Slot`** | **null** |
>
> ⇒ constructed, enabled, marked Visible — and **not parented into any panel**. Corroborated by
> absence: `WBP_UI_Menus_MessageOfTheDay` has **never** appeared in the `leaf-most node` UI-focus
> log across this session, and the operator confirms a clean lobby by screenshot.
>
> ⚠ `Slot == null` was flagged as suggestive-not-proof, and the viewport check was then RUN.
>
> ### ✅ NOT IN THE VIEWPORT — now [M] (`tools/re/widget_inviewport.py`)
>
> UE's own rule (`UWidget::IsInViewport`, `Private/Components/Widget.cpp:338`):
> `if (!bIsManagedByGameViewportSubsystem) return false;` — so that one flag is decisive in the
> negative. It is a **non-reflected bitfield**, declared immediately after the reflected
> `bIsVolatile:1`, so it is derivable: `bIsVolatile` resolves to byte **+0xE1 mask 0x10**, making
> the target **+0xE1 mask 0x20**.
>
> ★★ **CALIBRATED BEFORE USE — the bit is set on exactly 2 of 5064 live widgets:**
> `WBP_UI_MainMenu_RootV2_C` (the menu root) and `WBP_WidgetHighlighter_C` (a full-screen overlay)
> — precisely the two you would expect to be `AddToViewport`'d. A mis-derived bit would have given
> 0, thousands, or a random scatter; 2-of-5064 landing on exactly the right widgets is the control.
>
> **MOTD widget → `bIsManagedByGameViewportSubsystem = False` ⇒ `IsInViewport() == false`.**
>
> ⇒ The prompt is constructed, `Visible`, enabled — and not added **directly to the viewport**.
>
> ### ⚠⚠⚠ AND THAT CONCLUSION IS ALSO WRONG — CORRECTED AGAIN
>
> `PushPrompt`'s real body (`WBP_UI_MainMenu_NormalMainMenu::PushPrompt`, reached via
> `MenuRootV2::PushPrompt` → `MainMenu_NormalV2`) is:
>
> ```
> [0] Active = PromptStack->GetActiveWidget()
> [2] cond   = ReplacePrompt AND IsValid(Active)      <- ReplacePrompt is the literal `false`
> [3] JumpIfNot(cond) -> skip
> [5] PromptStack->RemoveWidget(Active)               (only when replacing)
> [6] Prompt = PromptStack->BP_AddWidget(WidgetClass) <- ALWAYS runs
> ```
>
> **The widget is added to a `PromptStack`, not to the viewport.** For a container-managed widget,
> `bIsManagedByGameViewportSubsystem == false` and `Slot == null` are both **expected and normal** —
> the STACK is the thing in the viewport, its children are not. ⇒ **Neither reading supports "never
> presented", and the viewport probe answered a question that does not apply here.**
>
> ⚠ The probe itself is fine and stays (`tools/re/widget_inviewport.py`, calibrated 2-of-5064). What
> was wrong is what I concluded from it: *"not added directly to the viewport"* is not *"not on
> screen"* for a stack child. **A correctly calibrated instrument pointed at the wrong question
> still yields a false conclusion** — arguably the more dangerous failure, because the calibration
> makes it feel earned.
>
> ★ **The RIGHT measurement, not yet run:** is the MOTD widget the **active** widget of
> `PromptStack`? A CommonActivatable-style stack presents only its top entry. Read
> `PromptStack->GetActiveWidget()` on the live `WBP_UI_MainMenu_NormalMainMenu` and compare against
> `0x2692C618DF0`, and/or enumerate the stack's entry list. That distinguishes "queued behind
> another prompt" from "on screen but invisible" from "added then immediately removed".
>
> ⚠ Also note `bWasShown` is **a hardcoded `EX_True`** written unconditionally after the call
> (`Try Show MOTD` `[27]`), *not* a result. Earlier text reading it as "the prompt was shown" was
> over-reading a constant: it proves the code path ran, nothing more.
>
> ### ★ LEAD: there is a SECOND pusher competing for the same slot
>
> [M] A catalog-wide scan finds `PushPrompt` referenced in exactly **6** assets. Five are the
> host/forwarder chain (`WBP_UI_MainMenu_MenuRootV2`, `WBP_UI_MainMenu_NormalMainMenu`,
> `WBP_UI_HUD_ROOT`, `WBP_UI_HUD_Gameflow_Root`, `WBP_UI_CombatRoot`, `WBP_UI_Login_Screen_Default`).
> The callers are **`Comp_MainMenu_Onboarding`** (ours) and **`Comp_MainMenu_VersionUpdate`**.
>
> [M] `Comp_MainMenu_VersionUpdate_C` has a **real live instance** (`0x269A190A340`, plus its
> archetype). ⇒ **A second component that pushes prompts to the same stack is active at the lobby**,
> and MOTD is pushed with `ReplacePrompt = false`, so it will **not** displace an existing active
> prompt. That is a concrete, testable candidate for "queued behind another prompt".
> ⚠ **Not established** — nothing yet shows `VersionUpdate` actually pushed anything this session.
>
> ### ✅ THE ACTIVE-WIDGET READ — THE STACK IS EMPTY [M] (`tools/re/promptstack_readout.py`)
>
> ```
> ALL WBP_UI_MainMenu_NormalMainMenu_C instances:
>    0x26A8DCF5160  Default__…                (CDO)
>    0x26A8DCF29B0  MainMenu_NormalV2   PromptStack -> NULL
>    0x26A6835C870  MainMenu_NormalV2   PromptStack -> 0x26A84B4CD00 CommonActivatableWidgetStack
>                                         WidgetList      Num = 0
>                                         DisplayedWidget = NULL
>                                         Slot            = CanvasPanelSlot   (the stack IS parented)
> ```
>
> ⇒ **The MOTD widget is NOT in the prompt stack, and the stack has never held anything.** The stack
> itself is real and parented, so "there is no prompt host" is excluded.
>
> ★★ **AND THERE ARE TWO `MainMenu_NormalV2` INSTANCES — one with a NULL `PromptStack`.**
> `MenuRootV2::PushPrompt` forwards to its own `MainMenu_NormalV2` variable; if that reference is
> the NULL-stack instance, then `PromptStack->GetActiveWidget()` and `PromptStack->BP_AddWidget()`
> are both **Blueprint no-ops on a null object** and the prompt is silently never created.
> **That is the leading hypothesis and it is testable:** read `MenuRootV2`'s `MainMenu_NormalV2`
> property and see which of the two addresses it holds.
>
> ⚠ It also casts doubt on an earlier reading: `CallFunc_Try_Show_MOTD_Widget = 0x2692C618DF0` was
> taken as "a widget was created". That object's NAME is exactly `WBP_UI_Menus_MessageOfTheDay_C` —
> the bare class name, not the `_C_2147…` form a runtime-spawned widget gets — so it may be a
> **template/archetype** rather than a live instance. Given `BP_AddWidget` on a null stack returns
> null, the non-null value in the frame needs re-explaining. **Do not treat "the widget exists" as
> settled.**
>
> ⚠ Instrument note: searching live classes for `PromptStack` returns **0**, which is meaningless —
> `PromptStack` is a **variable name**, not a class (the class is a CommonActivatable-style
> container). Do not read that zero as "no prompt stack exists".
>
> [I] **Working reading:** `PushPrompt(..., false)` enqueues the prompt on the main-menu prompt host
> and returns "shown", but the host never drains the queue at the lobby — so the MOTD sits built and
> invisible. The second argument to `PushPrompt` (literal `false` in the bytecode) is the obvious
> suspect and has not been identified.
>
> ★ **How the wrong conclusion happened, because it is the instructive part:** §§1–5 reasoned
> entirely from *static bytecode* plus *absence* (no prompt seen, empty ini) and never read the
> running state. The predicate trace was correct — every term of it survives — but the verdict
> attached to it was an inference, and it was backwards. **The frame was readable the whole time;
> the readout agent had even reported that the persistent-frame locals exist.** I noted that and
> then spent an hour inferring instead of reading.
>
> §§1–4b are kept because the *mechanism* they document is accurate and hard-won. Only the
> conclusion is void.

---

# (original, conclusion superseded) why the MOTD never fires: it is the tail of an ONBOARDING prompt chain

Follow-up to `docs/s121-toggle-fix-confirmed.md`. We serve `motd` with the full
`{enabled, default, key, title, text}` body, the client adopts the config, and **no prompt appears.**
This traces why. **[M]** measured / **[I]** inferred / **[S]** speculative.

## 1. The payload is NOT the problem — the last gate is provably OPEN

`Try Show MOTD` (`Comp_MainMenu_Onboarding_C`) is a five-gate chain [M, bpdump]:

```
[1]  IsFeatureEnabled("motd", false)                  -> bail
[6]  Map_Find(cfg.FeatureToggles, "motd")             -> bail
[13] Map_Find(entry.Config, "key")                    -> bail
[19] lastSeen = GetLokiGameUserSettings()->GetMessageOfTheDayLastSeen()
[23] NotEqual_StriStri(Config["key"], lastSeen)       -> bail
[25] MainMenuWidget->PushPrompt(WBP_UI_Menus_MessageOfTheDay_C, false)
```

★★ **[M] `MessageOfTheDayLastSeen=` is EMPTY** — read straight off disk from
`%LOCALAPPDATA%\SUPERVIVE\Saved\Config\WindowsClient\GameUserSettings.ini:79`. So gate [23]
(`"supervive-revival-motd-1" != ""`) **PASSES**, and the prompt has **never been shown on this
machine** — the "shows once per key" caveat is not what is happening here.

⇒ **All five gates should pass with what we already serve.** The failure is upstream: the function
is not being CALLED.

★ Free instrument for later: that ini line is a **persistent receipt**. The moment the prompt ever
displays, `MessageOfTheDayLastSeen` becomes non-empty. Watching one ini line beats watching the
screen, and it survives the process.

## 2. Both objects exist at runtime [M]

`tools/re/obj_by_class.py` against the live menu:

| class | live instances |
|---|---|
| `Comp_MainMenu_Onboarding_C` | **2** (`…_GEN_VARIABLE` archetype + a real `Comp_MainMenu_Onboarding`) |
| `WBP_UI_Menus_MessageOfTheDay_C` | **1** |

So neither "the component doesn't exist" nor "the widget class was stripped" explains it.
⚠ The widget exposes only `ToolTipText` as a reflected string — it sets its child text blocks
directly — so **its properties cannot be used to check whether our title/text reached it.**

## 3. ★ THE FINDING: MOTD is the tail of a sequential prompt chain

[M] In `ExecuteUbergraph_Comp_MainMenu_Onboarding`, `Try Show MOTD` is statement **[34]**, and the
statements immediately before it are:

```
[24] … HighlighterWidget                                  <- onboarding highlight machinery
[25] Hide Highlight
[26] Try Show Voice Chat Settings Confirmation(&Widget, &bWasShown)
[29] Temp_bool_IsClosed = True
[31] JumpIfNot(Temp_bool_IsClosed) -> 1318
[33] Temp_bool_IsClosed = True
[34] Try Show MOTD(&Widget, &bWasShown)
[35] JumpIfNot(bWasShown) -> 1440
[36] BindDelegate "On MOTD Deactivated"
```

⇒ **MOTD is the SECOND prompt in an onboarding sequence**, reached only as a continuation after
`Try Show Voice Chat Settings Confirmation` resolves, and that sequence sits downstream of the
onboarding **widget-highlight** flow (`Highlight Widget` / `Hide Highlight`).

[I] So the MOTD prompt is **new-player onboarding content**, not a lobby announcement banner. It
fires at the end of a first-run flow this account has presumably already passed or never qualified
for — which is why a perfectly-formed payload produces nothing.

## 4. THE 34-FUNCTION SWEEP — and the gate it found

All 34 UFunctions were dumped and their `ExecuteUbergraph(N)` entry constants recorded. **Twenty
have one; twelve are leaf helpers with none** (`Should*`, `Is*Ready`, `Try Show MOTD` itself, …).

★ **No entry offset lands in 1220–1440** — the lowest is `ReceiveBeginPlay` at **1491**, *above* the
whole MOTD chain. A clean negative, and the informative kind: it proves the chain is **not a jump
target at all**. Max `StatementIndex` is **6955**, so entry offsets and statement indices share one
numbering space and the comparison is valid.

⇒ The chain is a **queued continuation**. [M] `[41] EX_PushExecutionFlow → PushingAddress 1303`
(itself at statement 1455) is what arms it, and the only things that reach 1455 are:

| jump | at statement | meaning |
|---|---|---|
| `[158] EX_Jump → 1455` | **4677** | **starts the chain** |
| `[159] EX_Jump → 1440` | 4682 | = `On MOTD Deactivated`'s entry — the chain advancing itself |

★★ **THE GATE, immediately before the start jump** [M]:

```
[154] BooleanOR_1  = BooleanAND_8 OR NOT PreBool_3
[155] BooleanOR_2  = BooleanOR_1  OR NOT PreBool_1
[156] BooleanAND_9 = BooleanAND_5 AND BooleanOR_2
[157] EX_PopExecutionFlowIfNot(BooleanAND_9)     stmt 4668  <- FALSE here ABORTS
[158] EX_Jump -> 1455                            stmt 4677  <- starts the MOTD chain
```

**`Try Show MOTD` runs iff `BooleanAND_9` is true.** That is the precondition, and it is a compound
of four earlier booleans computed in the same block.

⚠⚠ **CORRECTION TO §3 OF THIS FILE, written an hour earlier.** It said *"`Try Start Onboarding Flow`
is NOT that entry point … Do not assume the obviously-named function is the caller — it is
measurably not."* **That was too strong.** What was measured is only that it does not enter at the
chain's own offset. Its entry (**3358**) and `On Client Config Updated`'s (**3353**) are the two
nearest below the predicate block at 4553–4677, so [I] that block is very likely their tail — i.e.
the obviously-named function probably *is* the origin, reaching the chain by falling through a long
predicate and then jumping. **The narrow claim (not a direct jump target) stands; the broad one
(not the caller) was unsupported and is withdrawn.**

## 4b. ★★ THE PREDICATE, FULLY TRACED [M]

Every term resolved from the bytecode:

```
BooleanAND    = IsValid(ClientConfigManager) AND IsConfigurationLoaded
BooleanAND_1  = BooleanAND   AND IsMatchHistoryLoaded
BooleanAND_2  = BooleanAND_1 AND NOT GetMatchInfo          (i.e. not already in a match)
BooleanAND_3  = BooleanAND_2 AND PartyModel->IsPartyValid
BooleanAND_4  = BooleanAND_3 AND GetCurrentPlayerProgression
BooleanAND_5  = BooleanAND_4 AND Array_IsNotEmpty(OutPlayer.MissionInfo.MissionData)

BooleanAND_8  = PartyManager->GetInitialExcludedRegionsSet AND (Map_Find_Value_3 == …)
Not_PreBool_3 = NOT Map_Find(GetFeatureToggle_FeatureToggle, <string>)
Not_PreBool_1 = NOT ShouldLaunchTutorialMatch
BooleanOR_1   = BooleanAND_8 OR Not_PreBool_3
BooleanOR_2   = BooleanOR_1  OR Not_PreBool_1
BooleanAND_9  = BooleanAND_5 AND BooleanOR_2               <- gates the jump at 4668
```

⚠ **The array is `MissionInfo.MissionData`, NOT `Matches`.** Reached by nested
`EX_StructMemberContext` (`MissionData` inside `MissionInfo` inside the progression struct). An
early guess here was "`Matches`, which we serve empty — that's the bug"; it was **wrong**, and
reading the two `Property:` names instead of assuming the obvious field is what caught it. We serve
**330 missions**, so this term is **TRUE**.

★ **This CONFIRMS the §4 retraction.** `[128]` sits at statement ~3400, immediately after the
entries `On Client Config Updated` (**3353**) and `Try Start Onboarding Flow` (**3358**) — so the
predicate block really is their tail. The obviously-named function *is* the origin.
⇒ And since we push client config every ~30 s, **`On Client Config Updated` re-evaluates this
predicate continuously** — the chain gets many chances, not one.

### ⚠ THE AWKWARD RESULT: every term looks TRUE

| term | expected on our stack |
|---|---|
| `IsValid` / `IsConfigurationLoaded` | TRUE — client config is served and adopted (eTag confirmed) |
| `IsMatchHistoryLoaded` | TRUE — FK-17 opened exactly this gate with `FMatchHistory{…,Matches:[]}` |
| `NOT GetMatchInfo` | TRUE — sitting at the menu |
| `IsPartyValid` | TRUE — solo party served since S85 |
| `GetCurrentPlayerProgression` | TRUE — `/progression` served and ingested |
| `Array_IsNotEmpty(MissionInfo.MissionData)` | **TRUE — 330 missions** |
| `BooleanOR_2` | TRUE via `NOT ShouldLaunchTutorialMatch` alone (no tutorial forced) |

**So `BooleanAND_9` should be TRUE and the chain should run — and it does not.** That is a real
tension, not a resolution, and it is recorded as such rather than smoothed over.

Two candidates, and they are distinguishable:
1. **One term is false in fact.** `IsConfigurationLoaded` and `IsMatchHistoryLoaded` are the two
   nobody has ever read directly; both are native getters, both plausible.
2. **The chain DOES run and `Try Show MOTD` bails at its own gate [1]** —
   `IsFeatureEnabled("motd", false)`. ⚠ **Which `Config` sub-key the NATIVE
   `UClientConfigManager::IsFeatureEnabled` reads has never been measured** — it is flagged **[S]**
   in `SURFACES.md`. The declarative widget's `"enabled"` was measured; the native function's key
   was only assumed to match. If it reads a third spelling, everything above passes and the very
   first gate still fails.

★ **Candidate 2 is cheap to settle and would generalise:** it is the same missing readout as A-14,
but for the *bytecode* keys. `toggle_readout.py` cannot see them (no widget), so the native call
needs its own probe.

## 5. What is left

Resolve `BooleanAND_5`, `BooleanAND_8`, `Not_PreBool_1`, `Not_PreBool_3` back to the function calls
that produce them (all in statements < 4553 of the same block). The component's leaf helpers are the
obvious candidates and are already dumped: `ShouldRunPlayMenuOnboarding`,
`ShouldRedirectToOnboardingScreen`, `ShouldBypassNewTutorialAndOnboardingScreen`,
`Should Show Returning Player Modal`, `Should Launch Tutorial Match`, `Get Number of Games Played`.
[S] A "games played == 0 / new account" style condition would explain everything observed.
⚠ Note `BypassTutorialAndOnboarding` is a served-toggle name we deliberately WITHHOLD — if it feeds
this predicate, the withholding is load-bearing and must not be casually changed.

## 6. Honest status

**Not** "serving MOTD does nothing." Measured: the payload is complete, every documented gate in
`Try Show MOTD` would pass (including `key != lastSeen`, since `lastSeen` is empty), both objects
exist, and the function is not reached because a **named compound predicate at statement 4668 gates
the jump that starts its chain**. The question has moved from "why doesn't it fire" to "which of
four booleans is false" — fully offline from here.
