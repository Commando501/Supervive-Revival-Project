# S122 handoff — the toggle channel is open; pick a surface and feed it

Written 2026-08-15 at the end of S121. **HEAD is `d90e6fd` on `dedicated-server-stub`, pushed.**
Working tree clean apart from `docs/inject-*.log` (already dirty when S121 started).
Both the game and `ags` are **DOWN** unless S121's session is somehow still alive.

---

## What changed, in one paragraph

`ConfigKey` is **`"enabled"`**, not `"default"`. That one word had made every feature toggle this
project served **inert since S73**. Fixing it opened **14 of 15** served declarative gates and, more
importantly, turned the toggle map into a **probe for hidden backend surface**: enabling
`leaderboards` made the client call three endpoints it had never been observed to call. Four new
surfaces now render live and screenshot-confirmed — **STORAGE**, **LEADERBOARDS** (daily/weekly *and*
ranked), **PLAYER STATS**, and the **region selector** — plus the **latency pipeline runs from login
with zero ping failures** after a three-week-old FK-5 fix was finally shipped.

Read `docs/s121-toggle-fix-confirmed.md` first. It is the spine of the session.

---

## Start here — the ranked options

### 1. ★ Feed the surfaces you just switched on (highest value, lowest risk)

All four new pages render **placeholder data**. They become real when match results exist:
- `/player-stats/leaderboard` — rows are one fabricated entry (`server/internal/interactive/leaderboard.go`)
- `/mmr/leaderboard` — one entry, `Rank: "Gold1"`
- `/player-stats/players/{id}` — one hero, invented numbers
- These are all **already wired and confirmed rendering**; only the data source is missing.

⚠ Before touching any of them read the traps in that file: the **echo requirement** on
`/player-stats/leaderboard` (a non-echoing reply parses fine and is silently discarded), `Rank`
being an **`ERank` enum string**, and `Placements` being **zero-indexed** (key 0 = 1st place, [M] by
prediction).

### 2. The remaining dark keys

The declarative vocabulary **closes with no remainder**: 50 = 12 served + 33
`IsEnabledByDefault=true` (**never send** — they are already on and sending them can only turn things
off) + 1 withheld + 4 candidates, all four flown. So the *declarative* sweep is done.
**The 10 BYTECODE keys are the frontier** — and `tools/re/bpframe_readout.py` can now read their
results, which nothing could before.

### 3. `DropScreenTitles` — do NOT re-attempt as a toggle task

It is blocked behind the **drop phase** (FK-1's four empty server-authority stubs), not behind the
toggle system. `BP_DropPod` is only ever *registered as poolable*; the drop phase has never run in
842 logs and the tutorial cannot produce one.

---

## ⚠ The instruments are the real inheritance — use them BEFORE inferring

S121 built **eight** read-only RPM probes. **Every single one contradicted something that had been
inferred first.** If you find yourself reasoning about what the client "must" be doing, stop and read
it instead.

| tool | answers |
|---|---|
| `tools/re/toggle_readout.py` | did a DECLARATIVE gate read our value? (`Is Content Enabled` @ +0x473) |
| `tools/re/bpframe_readout.py` | **any Blueprint's live ubergraph locals** (persistent `UberGraphFrame`) — covers the bytecode keys |
| `tools/re/regions_readout.py` | the client's parsed `FRegionHostList` (ETag = free positive control) |
| `tools/re/obj_props_dump.py` | every reflected object/array property of any object, with target class names |
| `tools/re/promptstack_readout.py` | a prompt stack's `WidgetList` / `DisplayedWidget` |
| `tools/re/motd_chain_readout.py` | Onboarding → MainMenuWidget → MenuRootV2 → NormalMainMenu → PromptStack |
| `tools/re/class_derivation.py` | a live object's super chain (⚠ under-enumerates functions; **positives only**) |
| `tools/re/widget_inviewport.py` | is a widget added to the viewport (calibrated 2-of-5064) |
| `tools/re/exec_regions.py` | classify an address: module / private-manual-map / unmapped |

⚠ **Several carry warnings in their own output. Read them.** `toggle_readout`'s
`never-evaluated` vs `ambiguous-off` split matters; `class_derivation`'s absence proves nothing.

---

## Open, with honest status

**`motd` — SOLVED as far as the backend goes; do not re-open it as a backend task.** [M] The payload
is correct and delivered, all five `Try Show MOTD` gates pass, the predicate at 4668 is TRUE,
`PushPrompt` runs, and the widget **is in `CommonActivatableWidgetStack_Prompts` as `WidgetList[0]`**
— but the stack's `DisplayedWidget` is NULL. It is queued and never activated. Purely client-side
from here. `docs/s121-motd-trigger.md`.

**The menu-idle crash family** — reproducible, `~T+80 s`, EXECUTE fault at `0x7FFA42600001` with a
`KERNEL32+0x17374` frame beneath it. **[M] NOT one of our shims** (our manual maps are heap-range and
move with ASLR; the fault is in no committed exec region; the injector never unmaps). [I] a
protector-created thread. 2 in 5 launches — consistent with the recorded hazard, **not** a
regression. `docs/s121-menu-crash-family.md`.

**Per-icon attribution for the three lobby boost icons** is still **[I]** — three keys on, three
icons up. The single-variable test (drop one key, wait the ~30 s poll, see which icon leaves) is
cheap and deliberately un-run.

---

## Practical notes that will save you a launch

- **Config changes need NO relaunch.** [M] Restart `ags` only; the client re-adopts within its ~30 s
  poll and toggle widgets re-evaluate. Verified single-variable (3 treatment keys flipped, all 43
  controls unchanged). ⚠ **Bump the eTag or the change is a silent no-op** — the client-config and
  regions eTags are both content-derived now, so this is handled, but any NEW endpoint you add needs
  the same discipline.
- **`ags` truncates `docs/capture.log` on restart.** Back it up first; it reached **55 MB** in one
  S121 run.
- **Filter `capture.log` by `User-Agent` before counting anything.** The game is `Loki/UE5-CL-0`.
  S121 tagged its own probes `s121-verify-NOT-the-game`, and that is the only reason two
  "zero complaints" readings were correctly called **uninterpretable** rather than passes.
- **Launch hazard ran ~2 in 5 this session.** Budget on armed windows, not launches.

---

## The method note S121 would most want carried forward

Every wrong conclusion this session came from **inferring from static analysis plus absence of
evidence**; every correction came from **reading live state**. Two new failure modes were recorded
that the register had not seen before:

1. **A correctly calibrated instrument pointed at the wrong question** still yields a false answer —
   and the calibration makes it *feel* earned.
2. **Over-correction**: after a run of retractions, sound evidence started getting discounted.
   Distrust should track the evidence, not your recent error rate.

⚠ And the uncomfortable one: a stale-eTag bug was shipped **one hour after fixing that same class of
bug and writing it up**. Where possible, fix the failure mode (content-derived eTags, counters that
print nulls and empties) rather than relying on remembering the rule.
