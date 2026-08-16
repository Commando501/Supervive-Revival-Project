# S121 — why the MOTD never fires: it is the tail of an ONBOARDING prompt chain

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
