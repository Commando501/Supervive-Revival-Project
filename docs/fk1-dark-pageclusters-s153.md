# FK-1 DARK page-cluster analysis: which single live call unlocks the most (S153, 2026-09-02)

Companion to [S153 native sweep](fk1-native-sweep-s153.md). That sweep classified
15,129 native UFunctions and left **4,910 DARK** (thunk on a demand-decrypt page
that `merged14` hasn't captured yet). This analysis groups them by page so the
next live session can fire ONE UFunction per page to demand-decrypt it — then
re-run the sweep offline to get an updated FK-1 map.

## Distribution

- **4,910 DARK UFunctions on 406 distinct pages**
- Top 10% of pages (41) = 1,257 dark UFunctions (25.6%)
- Top 25% of pages (102) = 2,353 dark UFunctions (47.9%)
- Top 50% of pages (203) = 3,615 dark UFunctions (73.6%)

Heavy long-tail on the low end (60 pages with 2-4 verbs each, 115 with 5-9,
229 with 10+). The 229 pages with 10+ verbs are the natural target set — each
worth ≥10 verbs decrypted per single fired call.

## The stock-UE tax

**16 of the top 20 all-page DARK clusters are stock UE modules that will never
execute on the SUPERVIVE runtime:** `UMovieScene*` (cinematography editor), `UDiscord*`
(SDK), `UMedia*` (video), `UDynamicMesh*` (editor mesh tools), `UGroomAsset` (hair
grooming editor), `UCommonUI` widgets (partly used), `UAgones*` (K8s server SDK,
absent per FK-13), `UAccelByte*BlueprintsSettings` (BP-only config), `UOptimus*`
(compute shader graph editor), `USentry*` (crash reporter, mostly used via native
crashpad — see CLAUDE.md FK-9), etc. **Filter these out of any recommendation.**

## Top 20 Loki-only DARK pages (fire-target candidates)

| page | dark verbs | Loki classes on this page (representative) |
|---|---:|---|
| `0x052CB000` | **39** | `ALokiBaseItem` (single class dominates) |
| `0x0529E000` | 29 | `ALokiAirship`, `ALokiBaseItem`, `ALokiGameState`, `ALokiMinionCharacter`, `ULokiActorTracker` |
| `0x052CE000` | 28 | `ALokiBaseGameplayImportantEffect`, `ALokiBaseItem` |
| **`0x05442000`** | **28** | `ALokiPlayerState_Missions`, `ALokiPlayerState_Stats`, `ALokiPlayerState_XP`, `ALokiPre*` (⚠ mission/XP/stat writers — DIRECTLY relevant to CLAUDE.md missions block) |
| `0x052B5000` | 25 | `ULokiAttributeSet`, `ULokiAttributeSetHealth` (⚠ GAS attribute setters — S141 movement-wall class) |
| `0x052B4000` | 24 | `ULokiAttributeSet` |
| `0x053BB000` | 22 | `ULokiInventoryComponentComboItems`, `ULokiInventoryOperations`, `ULokiItemGlobals` |
| `0x05404000` | 22 | `ALokiMinionCharacter`, `ULokiMenuGlobals`, `ULokiMinimapVisionGranterRenderer` |
| **`0x052FE000`** | **21** | `ALokiCapturePoint`, `ALokiCharacter`, `ULokiCaptorInterface` (⚠ contains 2 of the 17 STILL-DARK entries from S153 coverage re-grade: `ALokiCharacter::CheatToggleCharacterDebugMode`, `DebugStatString`) |
| `0x05441000` | 21 | `ALokiProjectile`, `ALokiTeamState`, `ULokiPlayerStatePawnComponent` |
| **`0x05483000`** | **21** | `ALokiTeamState_TeamOnly`, `ALokiTimelineEvent`, `ALokiTrainingSkill`, `ULokiTeamVaultD*` (⚠ `TeamState_TeamOnly` is FK-1 register #3 — `SetDropLeader`'s class) |
| `0x053B1000` | 19 | `ULokiHUDStatsPanel`, `ULokiHyperlinkRichTextBlockDecorator`, `ULokiInputDisplayStati*` |
| `0x053BC000` | 19 | `ULokiInventoryComponentComboItems`, `ULokiInventoryContextLibrary` |
| `0x052D5000` | 16 | `ALokiBattleRoyaleSpawner`, `ALokiBiome`, `ALokiBiomeVolume` |
| `0x0540E000` | 16 | `ALokiOpeningClosingProp`, `ULokiMusicManagerSubsystem`, `ULokiNavLineRendererCompone*` |
| **`0x05422000`** | **16** | `ALokiPlayerCheats`, `ALokiPlayerController`, `ALokiPlayerState` (⚠ this is the same page S153 coverage re-grade already flagged as highest-yield for the 6 `ALokiPlayerCheats::Cheat*` STILL-DARK exec verbs) |
| `0x05423000` | 15 | `ALokiPlayerCheats`, `ALokiPlayerController` |
| `0x05351000` | 14 | `ALokiGameModeDefusal`, `ALokiGameModeLastManOnTheHill` |
| `0x052D6000` | 13 | `ALokiBasePersistentCue`, `ALokiBattleRoyaleSpawner`, `ALokiBiomeVolume` |
| `0x053C3000` | 12 / 14 | `ALokiLaneMinionManager`, `ALokiLaser`, `ULokiLaunchCharacterTask` |

## Recommendations for the next live session

**Fire targets ranked by strategic value** (not just count — factors in overlap with
open CLAUDE.md FK topics):

**1. Page `0x05442000` — 28 verbs, ALokiPlayerState_Missions/Stats/XP.** Directly
relevant to the mission-progression / stat-writer / XP-award surfaces (CLAUDE.md
Missions block, S119 native ingest). A getter on any of these classes decrypts
the page, letting the S153 sweep classify all 28 as REAL or STRIPPED.
- **Safe fire candidate:** any zero-arg getter on `ALokiPlayerState_Missions`
  or `ALokiPlayerState_Stats`. Read from the CSV (`awk -F, '$1=="ALokiPlayerState_Missions"' scratchpad/s153_native_ufunction_sweep.csv`).

**2. Page `0x052B5000` + `0x052B4000` — 49 verbs, ULokiAttributeSet family.**
Directly relevant to S141's movement wall investigation (`GetMaxSpeed`,
`GetMaxAcceleration`, `AnalogInputModifier`, etc. are on this class family).
Currently classified but many are DARK. Any GAS-related call in a live tutorial
session (which the shim already does via `KWIREGAS`) may already be decrypting
these — check the current `merged*.dump.exe` before flying.

**3. Page `0x05422000` — 16 verbs, ALokiPlayerCheats/Controller/State.** Same page
the S153 coverage re-grade already flagged as containing 6 `Cheat*` STILL-DARK
exec verbs. This is a two-birds-with-one-stone target: a live cheat manager
call (Route B is already shipped per FK-13) decrypts the page and simultaneously
resolves 6 exec-surface + 10 native-surface DARK entries.

**4. Page `0x05483000` — 21 verbs, ALokiTeamState_TeamOnly.** FK-1 register
entry #3 (`SetDropLeader`) lives on this class. Firing any `ALokiTeamState_TeamOnly`
getter unblocks the whole surrounding surface — potentially revealing more drop-
authority stubs.

## Workflow after firing

1. **Fire the chosen UFunction** in the live session (via S55 native-call
   primitive or CheatManager Route B, depending on the target).
2. **Dumpimage the process** — `usmapdump.exe dumpimage <PID> dumps/s154-<label>`.
3. **Merge into `merged15.dump.exe`** — `usmapdump.exe mergedumps dumps/merged15.dump.exe dumps/s154-<label>/...`.
4. **Update the sweep tool** — one line, change `DUMP = "dumps/merged14.dump.exe"` → `"dumps/merged15.dump.exe"` in `scratchpad/s153_native_ufunction_sweep.py`.
5. **Re-run** — `python scratchpad/s153_native_ufunction_sweep.py` — gives an updated FK-1 map in ~14 seconds.

Each round could reduce DARK by ~15-40 entries and add that many verdicts to the FK-1 census.

## What this does NOT establish

- **No live measurement of any fire target has been taken.** All recommendations
  are based on offline page-clustering; actual demand-decrypt behavior on a
  live process might differ from the naive "call any UFunction on the page" model.
- **The page-boundary heuristic assumes protector demand-decrypts at 4 KiB
  granularity.** This is measured true for the SUPERVIVE runtime (CLAUDE.md FK-9,
  and every S118/S135/S137 side-effect finding), but a hypothetical finer-grained
  protector would need per-function decryption.
- **A UFunction on a dark page might itself fault** (bytes never seen, prologue
  might be broken). The protector's demand-decrypt should handle this — but if
  ANY fire crashes the process, back off to a safer getter on the same class.
- **Some DARK entries may be genuinely never-callable in this build** — a fire
  attempt on them would produce nothing. Prefer classes that already show REAL
  entries in the CSV as candidates (proves *some* UFunctions on the class do
  execute).

## Files

- `scratchpad/s153_dark_pageclusters.py` — the clusterer tool
- `scratchpad/s153_dark_pageclusters.out.txt` — full output (all 406 pages, top-30 verbose)
- `scratchpad/s153_native_ufunction_sweep.csv` — source data
- `docs/fk1-native-sweep-s153.md` — the parent S153 native sweep
- `docs/fk1-exec-sweep-s153.md` — S153 exec-verb sweep (17 STILL-DARK, 7 pages listed)
