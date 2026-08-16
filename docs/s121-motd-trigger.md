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

⚠ **`Try Start Onboarding Flow` is NOT that entry point.** [M] It is 3 bytecodes long and jumps to
`ExecuteUbergraph(3358)`; the MOTD chain lives around statement **1220–1440**. Different region.
**Do not assume the obviously-named function is the caller** — it is measurably not.

## 4. What would settle it

The ubergraph is entered by `EX_ComputedJump` on an offset each event passes to
`ExecuteUbergraph(N)`. The component binds **`On HUD Created`, `On Match History Updated`,
`On Client Config Updated`, `On Core Game Match Info Updated`, `On Party Is Valid Updated`,
`On Party Excluded Regions Updated`** [M].

**Next step, well-scoped:** dump each of the component's **34** UFunctions and record its
`ExecuteUbergraph(N)` constant; the one whose `N` lands in **1220–1440** is the event that enters the
MOTD chain. That is a mechanical pass, entirely offline, and it converts "why doesn't it fire" into
"which precondition is unmet".

⚠ Note `On Client Config Updated` is among the bound delegates, so a config push *can* drive this
component — which is consistent with the chain being live but entered at a different offset.

## 5. Honest status

**Not** "serving MOTD does nothing." What is measured: the payload is complete, every documented
gate would pass, both objects exist, and the function is not reached because it is the tail of an
onboarding sequence. The entry condition is **identified as findable but not yet found.**
