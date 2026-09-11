# NEXT SESSION (S154) — S153 saturated the FK-1 hunt offline; WALL P block relocated; S148 shim unblocked; three arms ready to fly

**One line:** S153 delivered 10 offline commits — fixed the S148 thunkExact bug (rebuilds cleanly, unflown), swept 15,129 native UFunctions (318 stripped, 4/5 register entries + 17 novel), page-clustered the 4,910 DARK entries for the next live decrypt, cross-indexed the stripped set against 8 open FK topics via multi-agent workflow, then DOUBLE-refuted the top-ranked WALL P hypothesis (`CallSpellCompleteEvent` is stripped BUT MiniDash doesn't call it AND the auto-fire alternative isn't stripped either — the block is at the state-byte layer). **Zero launches, zero injections.** Reproducible from commit `fbc85b4` (10 S153 commits `1941246`..`fbc85b4`, all pushed to `origin/dedicated-server-stub`).

## 0. What S153 did (2026-09-02)

Written 2026-09-02 at the end of S153. **Read these docs in order, they build on each other:**

1. **[S153 thunkExact fix](../CLAUDE.md#L3940)** (commit `1941246`) — CLAUDE.md FK-1 5th entry now notes the S148 shim rebuilds cleanly. Regression gates `play 9bc10a4552c596e1` + `botai 5e47c13cf7f0a158` reproduce exactly from source; new S148 DLL RAW `899ac8b56a477110`, deterministic, both s148 tests PASS. **Unflown.**

2. **[FK-1 exec sweep](fk1-exec-sweep-s153.md)** (commit `498f428`) — 32 stripped exec verbs identified offline against `merged14` via re-analysis of `exec_chain_grade.txt`. Disjoint from the FK-1 register (those are `FUNC_Net*`, not exec). Reused: coverage re-grade proved `SetGamepadAimSettings` mis-attributed since S114 (instrument limitation, not coverage gain).

3. **[FK-1 native sweep](fk1-native-sweep-s153.md)** (commits `18a5ac1`, `b48eb59`) — full sweep: 16,490 native UFunctions, **318 STRIPPED**, 66 distinct thunk RVAs. v2 closes the fk13natreg instrument gap using `exec_chain_grade`'s DATA-DIRECTED enumerator; capstone-based classifier with `__security_check_cookie` fix. All 5 FK-1 register entries confirmed. 17 novel stripped stubs.

4. **[DARK page-cluster analysis](fk1-dark-pageclusters-s153.md)** (commit `5716602`) — 4,910 DARK entries on 406 pages. Heavy stock-UE tail. Top Loki fire targets ranked for next live decrypt: page `0x05442000` (28 missions/XP verbs), `0x052B4/5000` (49 AttributeSet), `0x05422000` (16 ALokiPlayerCheats), `0x05483000` (21 TeamState_TeamOnly).

5. **[FK-1 topic cross-index](fk1-topic-crossindex-s153.md)** (commit `379db2c`) — multi-agent workflow `wf_d7a1c52f-50d`, 8 fan-out agents + synthesizer, cross-indexed the 318 stubs against 8 open FK topics. ~170 unique stubs identified as blockers, ~65 genuinely new. Highest-leverage multi-topic blockers enumerated. **11 new reusable rules** banked as R-S153-a..k.

6. **[WALL P CallSpellCompleteEvent deep dive](wall-p-callspellcomplete-deep-dive-s153.md)** (commit `c9766f7`) — partially REFUTED the cross-index's ranked-#1 claim. 26/596 spells use manual-fire (genuinely blocked); 570/596 use auto-fire (unaffected). **S147's actual target `GS_Ronin_MiniDash_Charges` is in the auto-fire majority** — the stub cannot be its blocker.

7. **[WALL P auto-fire mechanism hunt](wall-p-autofire-mechanism-s153.md)** (commit `fbc85b4`) — hunted the auto-fire path. **The mechanism is FULLY REAL.** UHT `SetBitFunc` disassembly → offset `[GameplaySpell + 0xC76]` → single reader at `0x5515D40` in a REAL BEGIN function → propagates to `[subobject + 0xC0D]` → 4 REAL sibling auto-fire handlers in `0x5679xxx` band → REAL broadcast at `0x56A5370`. **Block is at the state-byte read layer, not the broadcast layer.**

8. **[Stale-claim regrade](../scratchpad/s153_regrade_blocked.out.txt)** (commit `47faa39`) — 58 raw stale-coverage-claim hits vs `merged14` (up from S137's 43 as coverage advanced). CLAUDE.md itself CLEAN of true stale claims after adjudication (both raw hits are false-positive regex matches on correction text).

## 1. Recommended first live action — the WALL P discriminator read

The auto-fire mechanism hunt produced a concrete, preregistered live-read
recipe with clean discriminator outcomes. **This is the single highest-yield
first live action.**

**⚠ S154-refined (see `docs/wall-p-statetracker-class-s154.md`):** the
state-tracker subobject class is now IDENTIFIED as `ALokiPlayerController`
[MEASURED via vtable RVA `0x8A1AEE0`, cross-checked against CLAUDE.md's
`[pawn+0x400]=Controller` finding from S135/S136]. The state-machine model
is also refined: 4 phases (Warmup/Channel/Invoke/Cooldown) + 1 authority
gate + 1 re-entrancy latch + 2 timing floats. And `0x56A5370` is NOT the
delegate broadcast — it's a 2-D target-vector commit helper; the actual
`OnGameplaySpellEnded` broadcast lives downstream in the 4 sibling
handlers' tails.

**Setup:** launch the game, stage the tutorial world (`configs/fk24-stage.ps1`),
inject any spell-arming shim that produces a live MiniDash spec (S143/S144-era
`tutorial_launch` variants). See `configs/s148-move4.ps1` for the current
staging pattern.

**Post-cast reads (RPM, no injection):**
1. Get the possessed hero's `pawn->Controller` = `[pawn + 0x400]` — this is
   an `ALokiPlayerController` instance.
2. **Sanity gate:** verify `[pc + 0]` equals `IMAGE_BASE + 0x8A1AEE0`. If
   not, `[pawn+0x400]` deref went somewhere unexpected — DO NOT trust the
   byte reads below.
3. Read (all byte-precise from access map):
   - `[pc + 0xC0D]` — authority gate (`bManuallyCallSpellCompleteEvent`
     propagated from spell)
   - `[pc + 0xBEC]` — re-entrancy latch
   - `[pc + 0xBFC]` — phase_warmup (1 = in Warmup)
   - `[pc + 0xBF4]` — phase_channel
   - `[pc + 0xC04]` — phase_invoke
   - `[pc + 0xC0C]` — phase_cooldown
   - `[pc + 0xBF8]` — timing_A_shared (Warmup/Channel pace)
   - `[pc + 0xBF0]` — timing_B (secondary)

**Discriminator table** (S154-refined per `docs/wall-p-statetracker-class-s154.md`):

| observation post-cast | verdict | next investigation |
|---|---|---|
| `[pc+0xC0D] == 0` (auth gate unset) | **Propagation failed.** BEGIN `0x5515C55`'s 4-gate validation refused MiniDash's chain. | Instrument the 4 gates (`0x44556A0`, `0x4453EC0`, `0x54F8DC0`, `0x5512380`) — find the rejecter. |
| `[pc+0xC0D] == 1` and all four phase bytes `0` | **Auth gate open but no phase active.** State machine idle; handlers can never fire without a phase to consume. | Look at where phases get set — Warmup `[+0xBFC]=1` is set by BEGIN or by Channel handler's cyclic back-write. |
| `[pc+0xC0D] == 1`, a phase byte was 1 and is now 0 (cleared post-cast) | **Handler fired.** `0x56A5370` did its geometric commit but the delegate broadcast (elsewhere in the handler tail) may be stripped/blocked. | Disassemble the 4 handler tails past their `call 0x56A5370` — find the `OnGameplaySpellEnded` broadcast site. |
| `[pc+0xC0D] == 1`, phase byte still 1 (never cleared) | **Handler never fired.** State-active but consumer path not reached. | Handler entry has an internal `cmp [phase],0; je exit` — the phase must be non-zero AT the call site. Something is calling the handlers speculatively. |

All three outcomes are actionable and have concrete next steps. This is a real
step forward from S147's "no durable ability body" observation.

## 2. Unflown arms (inherited from S151, now S153-refined)

Read [next-session-prompt-s151.md](next-session-prompt-s151.md) for the original arm designs. What S153 changes:

| arm | S151 status | S153 refinement |
|---|---|---|
| **DLP** (drop-chain-in-one-injection) | ready `d2ebf30` | Still ready; page `0x05442000` fire would decrypt `ALokiPlayerState_Missions` family en route — free coverage gain. |
| **Move 3 BINDCENSUS** (WALL P discriminator) | ready `852fbfd` | **SUPERSEDED by the state-tracker byte read above.** The BINDCENSUS arm would still be useful for exposing input binding, but the state-byte read is a strictly higher-yield first move — it directly discriminates the three block layers whereas BINDCENSUS answers a specific H1/H2 question that only matters if propagation succeeded. |
| **Move 4 WALL E Phase 1a** (S148 + bind-only) | ready `0fe28f0` | **S148 shim's thunkExact bug FIXED S153.** The frozen S148 DLL from S152 flight 3 still ships the bug; the FIX is in the source tree at commit `1941246`. Rebuild S148 with `build.ps1 -Name tutorial_launch -Variant botfight-damage-self-cal` (deterministic 221,696 B, RAW `899ac8b56a477110`). Should now advance from `RESULT=ADJUST_UNRESOLVED` to either `HEALTH_APPLIED` or a downstream refusal that names the next wall. |

**Fly-order recommendation:** state-tracker read (WALL P) → S148 rebuild (WALL E) → DLP if bandwidth remains. The WALL P read is entirely non-mutating RPM and can be done in the same live session as either mutation arm.

## 3. New offline artifacts S153 produced

Every new file is committed and pushed. Key entries:

**Docs (evidence chain — read in order):**
- `docs/fk1-exec-sweep-s153.md`
- `docs/fk1-native-sweep-s153.md`
- `docs/fk1-dark-pageclusters-s153.md`
- `docs/fk1-topic-crossindex-s153.md`
- `docs/wall-p-callspellcomplete-deep-dive-s153.md`
- `docs/wall-p-autofire-mechanism-s153.md`

**Tools (reusable, invoke by re-running):**
- `scratchpad/s153_native_ufunction_sweep_v2.py` — the sweep tool. Change `DUMP = "..."` and re-run for a newer merged image. Takes ~14 sec.
- `scratchpad/s153_dark_pageclusters.py` — clusters DARK entries by page. ~1 sec.
- `scratchpad/s153_coverage_regrade.py` — re-grades the 18 previously-COVERAGE-BLOCKED exec entries against a chosen dump.
- `scratchpad/s133/tools/regrade_blocked.py` — the stale-claim regrade tool (existing, re-run gives the 58 count vs merged14).

**Data (query by grep/awk):**
- `scratchpad/s153_native_ufunction_sweep_v2.csv` — 16,490 rows: `class,name,thunk_rva,verdict,new_vs_v1,note`. Use for any "is FunctionX stripped?" query.
- `scratchpad/s153_native_ufunction_sweep_v2_delta.txt` — 83 classes fk13natreg missed entirely + 17 new stripped entries, class-grouped.
- `scratchpad/s153_dark_pageclusters.out.txt` — 663-line full page-cluster output.
- `scratchpad/s153_topic_crossindex_agent1..8.md` — per-agent findings preserved verbatim.
- `scratchpad/s153_topic_crossindex_synth.md` — synthesizer verbatim output.
- `scratchpad/s153_regrade_blocked.out.txt` — this session's stale-claim regrade snapshot.

**Workflow (resumable):**
- `wf_d7a1c52f-50d` = the cross-index workflow. Resume with `Workflow({scriptPath: "...s153-fk1-crossindex-wf_d7a1c52f-50d.js", resumeFromRunId: "wf_d7a1c52f-50d"})`. Unchanged agents replay from cache; edit prompts to re-run specific topics.

## 4. New reusable rules banked (R-S153-a..k, catalog is now 11 items)

Read the details in `docs/fk1-topic-crossindex-s153.md` §"Reusable-rule roll-up",
`docs/wall-p-callspellcomplete-deep-dive-s153.md` §"Reusable rules banked", and
`docs/wall-p-autofire-mechanism-s153.md` §"Reusable rules banked".

**Meta-heuristics (apply broadly):**
- **R-S153-g** — any stripped-stub hypothesis naming ONE UFunction as blocking a behaviour MUST be cross-checked against the shipping asset population that actually calls it. 96% of spells don't call `CallSpellCompleteEvent`.
- **R-S153-h** — a `b*` UPROPERTY named `bManually<Verb>` is a strong hint that a non-manual (auto) path exists elsewhere. Grep the shipping BP catalog for the value distribution.
- **R-S153-k** — a stripped-stub hypothesis's SECOND-order refutation is worth the same offline effort as the first-order. Each layer moves the search space one hop deeper.

**Offline-technique rules:**
- **R-S153-i** — UHT `SetBitFunc` disassembly is the offline oracle for a bool UPROPERTY's byte offset. Two instructions decode the layout.
- **R-S153-j** — a `[reg+disp32]` reader hunt across `.text` can be done by literal-searching for the 4-byte disp32 pattern then decoding backward 2-8 bytes. Cheap and offline-decisive when offset is uncommon.

**Subsystem-specific rules:**
- **R-S153-a** — the entire `ULokiSpellSwapper` subsystem is gutted (5 stripped stubs). Any hero routing through this class dead by design (but see counter-check opportunity in §6).
- **R-S153-b** — 11-writer `ALokiPlayerState::Add*Stat` family is uniformly `void_ret` on thunk `0x52FD8F0`. Assume folded, check backend passthrough.
- **R-S153-c** — 10 stat-getter void folds on `0x5436E40` (int) / `0x5349FB0` (float) return zero universally.
- **R-S153-d** — the fold set is genuinely 5 not 4 (`0xFC6CF0` = `xorps xmm0,xmm0; ret → 0.0f` was missing from CLAUDE.md's earlier register).
- **R-S153-e** (partially refuted per §5 above) — `CallSpellCompleteEvent` stripping blocks the 26 manual-fire spells only; NOT MiniDash.
- **R-S153-f** — bypass-status typology stabilizes at 4 values (PROVEN_ALT_CALL_PATH, PROVEN_DATA_POKE, CANDIDATE_DATA_POKE, GENUINELY_BLOCKING).

## 5. Cross-index per-topic snapshot

From `docs/fk1-topic-crossindex-s153.md`:

| topic | STRIPPED on critical path | already-known | NEW | note |
|---|---:|---:|---:|---|
| WALL P (ability activation) | 29 | ~22 | 7 | S147 block relocated to state-tracker layer per auto-fire hunt |
| WALL E (bot hostility) | 30 | ~29 | 1 (`EliminateTeam`) | S148 shim unblocked; unflown |
| Drop chain | 18 | ~10 | ~8 | S150-drop path substantially bypasses this |
| Mount/dismount | 13 | ~7 | ~6 | S131/S132 already have data-poke bypasses |
| Movement (CMC/GAS) | 9 | ~8 | 1 | **Gap: S141 T3's real block is stock UE `PhysFalling`/`CalcVelocity` — architectural, NOT stub-driven** |
| Missions/XP/stats | 38 | ~10 | ~28 | 11-writer `Add*Stat` family — check backend passthrough |
| Match lifecycle | 21 | ~12 | ~9 | Includes `EliminateTeam`, `SetIsEliminated`, etc. |
| Netcode/RPC | 12 | ~7 | ~5 | Largely IRRELEVANT because `GetNetMode() == NM_Standalone` (S137) |

## 6. Best offline follow-ups if the game stays dead longer

Each of these can be done offline in ~15-30 min:

1. **`ULokiSpellSwapper` counter-check (would settle R-S153-a)** — grep 596 GS blueprints + hero classes for SpellSwapper references. If Ronin/GreyFalcon/etc. bypass SpellSwapper for their core kits, R-S153-a is moot for gameplay. Directly parallels the R-S153-e refutation methodology.
2. **Identify the state-tracker subobject class** — the auto-fire hunt referenced `r14 = [validated_object + 0x400]` without naming the class. Find all writers of `[reg+0xC0D]` byte across `.text` — likely narrows to a specific class the offset lives on. Would name what to type-check in the live read.
3. **Missions backend passthrough check (would settle R-S153-b)** — check `server/internal/interactive/*.go` for stat handlers. If the backend delivers all 11 `Add*Stat` fields via `/progression/players/{id}`, R-S153-b doesn't affect shipping-quality gameplay.
4. **Consolidate S153's 11 rules into `docs/method-rules.md`** — the canonical rule file. Currently R-S153-a..k are scattered across four CLAUDE.md paragraphs and three evidence docs. Folding them in matches the S133-a..d / S130-c / S124-k patterns already there.

## 7. What NOT to do (S153-derived cautions)

- **Do NOT cite R-S153-e as MiniDash's blocker.** The deep-dive refuted that specifically for MiniDash; it holds only for the 26 manual-fire spells. Cite the auto-fire mechanism doc instead.
- **Do NOT rebuild S148 from the codex worktree.** The main-worktree fix (`1941246`) is the canonical form; the codex worktree at `C:\Users\eastr\.codex\worktrees\78d0\...` may have divergent history.
- **Do NOT edit doc bodies to remove stale-claim regex matches** without adjudication. Most of the 58 raw hits are corrections that quote the original claim; simple substitution would remove information. Per CLAUDE.md's existing note: run the tool as first-pass filter, then adjudicate.
- **Do NOT assume a stub is "the block" without checking the shipping call population** (R-S153-g). This trap fired at S152 (thunkExact) and again at S153 (CallSpellCompleteEvent).
- **Do NOT re-use the frozen S148 DLL from S152 flight 3.** It ships the thunkExact bug. Rebuild from source at commit `1941246` or later.

## 8. Sanity check reproducibility before flying

Before any live session, verify:
```bash
git log --oneline 02da3f1..HEAD  # should show 10 S153 commits, top: fbc85b4
git status --short               # non-S153 dirty files inherited from pre-session; ok
python tools/sigbypass-mod/text_digest.py tools/sigbypass-mod/build/tutorial_launch_play.dll
  # RAW=9bc10a4552c596e1  (regression gate)
python tools/sigbypass-mod/text_digest.py tools/sigbypass-mod/build/tutorial_launch_botai.dll
  # RAW=5e47c13cf7f0a158  (regression gate)
```

If any gate value differs from the recorded S153 canonical, DO NOT fly — the source tree has drifted and the S153-recorded behaviour may not reproduce.

## 9. Frontier state (2026-09-02)

- **WALL P** — state-tracker byte block; live discriminator read designed
- **WALL E** — S148 shim source-fixed, rebuildable, unflown
- **Movement** — S141 T3 block is stock UE, architectural, not in stripped set
- **Drop chain** — S150-drop lands hero on ground, works
- **Mount/dismount** — S131/S132 recipes hold
- **Missions** — R-S153-b noted; backend passthrough not yet checked
- **FK-1 hunt** — offline SATURATED at 318 stripped stubs; further gains require live decrypt of DARK pages
- **Instrument suite** — mature: capstone classifier, native sweep, page-cluster, cross-index workflow, stale-claim regrade — all reusable

Session-end commit: `fbc85b4` on `dedicated-server-stub`, pushed to origin.
