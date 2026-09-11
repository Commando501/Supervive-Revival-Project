# S179 Next-Session Prompt — understand why `-CompanionWatch` breaks tutorial staging (F10 mystery)

**Fresh-session paste-ready prompt.**
**Date written:** 2026-09-05
**Previous session:** S177/S178 — see `docs/s177-fk32-mechanism-CONFIRMED-companion-process.md` and the `docs/s178-*.md` family for full context.

---

## Paste this as the opening message

Continuing SUPERVIVE Revival Project. Last session (S177/S178) identified the FK-32 mechanism end-to-end and shipped a working defeat via `configs/launch-redirect.ps1 -CompanionWatch`. Six evidence docs at `docs/s177-*.md` and `docs/s178-*.md`. Commit history since S155: `9234169` S177-S178 FK-32 mechanism + defeat shipped; `237e61a` defeat generality across 5 trigger classes; `3655133` fo-alone control confirming FK-31 orthogonal.

**Your task**: understand why the shipped `-CompanionWatch` breaks tutorial staging. S177 Flight 10 measured: with watcher armed AND fo shim injected, `LVL_Tutorial` DID NOT LOAD and the game did not die — a new state we've never observed. The natural next step (a combined staging + FK-32-defeat launcher) is blocked on this. Recipe + branching discriminators below. Read the top 3 docs I name before flying.

## Read first, in order

1. **[docs/s177-fk32-mechanism-CONFIRMED-companion-process.md](s177-fk32-mechanism-CONFIRMED-companion-process.md)** §"Flight 10 — companion watch during tutorial staging" — the one paragraph describing what happened. Two-minute read.
2. **[docs/s178-defeat-generality-across-triggers.md](s178-defeat-generality-across-triggers.md)** — 5-trigger generality result. Establishes that companion-watch is surgical (kills only runtime.dll children, not benign siblings) and that the trigger surface is narrow. Grounds the F10 puzzle: companion spawn during staging is either uncorrelated with fo's LoadMap OR its behaviour changes the game state that fo depends on.
3. **[docs/s178-fo-alone-control-t5-anomaly.md](s178-fo-alone-control-t5-anomaly.md)** — fresh fo-alone controls establish fo fires FK-31 within 10s. F10's game DID NOT die at all. So fo's usual FK-31 was suppressed AND its LoadMap didn't fire. Both anomalies coexist in F10.

Then skim:
- `configs/launch-redirect.ps1` — read the new `-CompanionWatch` block (~line 380) and its documented incompatibility warning.
- `scratchpad/s177/companion_watch.py` — the tool. `--only-name`, `--kill-on-sight`, `--wait-for-game` — understand what it does and doesn't do.
- CLAUDE.md's "Before touching anything drop- / deploy- / DropPlane- / DropPod- / dismount- / ..." block — reminds you the drop chain (which staging IS about) exists.

**Do NOT re-read**: the full S177 workflow synthesis (39KB) or the A2/A3/A4/A5 findings unless you need them for a specific question. The 3 docs above cover the F10 mystery fully.

## What's known [M]

- **FK-32 mechanism**: `runtime.dll` spawned as a hidden companion process (parent = game PID). Companion runs ~4.5s: loads 21 Win32 DLLs → WinHTTP+TLS phone-home → DPAPI decode → SHA-256 integrity check (via Intel ISA-L hasher at RVA 0x920C10) → `NtOpenProcess(game, TERMINATE)` at t+37ms → `NtTerminateProcess(game, 0xDEAD)` at t~4.5s.
- **FK-32 defeat [M]**: `TerminateProcess()` on the companion within ~220ms of its Process/Start keeps the game alive 240+ s.
- **`-CompanionWatch` filter is surgical [M]**: `--only-name runtime.dll` — ignores conhost, EpicWebHelper, crashpad_handler correctly. No collateral kills in 4 flights.
- **FK-32 trigger is narrow [M]**: DR install triggers it in ~5-58s. WPM to game memory, benign DLL injection, and re-arming already-set DRs do NOT trigger it.
- **FK-31 (0xC0000005 at runtime.dll+1) is orthogonal [M]** to companion-watch: in-process self-check, not companion-mediated. `-CompanionWatch` does not defeat it (measured directly in fo-alone Control 2).

## The mystery (F10)

**Setup**: game running at menu, DR install applied (triggered a companion spawn which was killed by watcher, S177 F9 recipe worked), then `fk24-stage.ps1 -SkipProbe` was run.

**Observations from S177 F10**:
- `gft_ready_fix.dll` injected successfully (DllMain returned OK, MZ verified)
- `tutorial_launch_fo.dll` injected successfully (DllMain returned OK, MZ verified)
- Stager waited 180s for `Load map complete /Game/Loki/Maps/Tutorial/LVL_Tutorial` marker in `Loki.log`
- **Marker never appeared** — stager TIMED OUT
- **Game DID NOT DIE**: no FK-31 (0xC0000005), no FK-32 (0xDEAD), telemetry POSTs continuing, `LogPartyManager: Member latencies set` still firing on schedule
- **Companion watcher observed NO runtime.dll spawn during staging** — its log has only the initial `[cw] game pid=` line, no NEW CHILD lines
- Client remained on `LVL_LobbyV2_Persistent` (the lobby map), never advanced to `LVL_Tutorial`

**The puzzle**: `-CompanionWatch` broke fo's LoadMap trigger. But since NO runtime.dll spawn happened during staging, the WATCHER never actively did anything — it was passive. So the issue isn't that the watcher killed something during staging; it's that something in the PRIOR sequence (defeat + DR install artifacts + game state) put the game in a mode where fo can't LoadMap.

**Three top hypotheses** (grade [S] each; measure to promote):

**H1 — fo needs a live companion to complete LoadMap.** fo's job is to force `UEngine::Browse` into `LVL_Tutorial`. Maybe some check inside fo's LoadMap path expects the companion to have written a token / IPC value / shared state that the game side reads before accepting the browse. If we killed the companion in a prior trigger cycle, that state was cleared and fo can't complete.

Refute path: repro F10 without a prior companion spawn (i.e. don't do DR install first — just launch, wait to menu, run stager). If LoadMap still fails, H1 is refuted; if it works, H1 is supported.

**H2 — the game is in a "compromised" post-companion-kill state.** The game learns "our companion was killed" and enters a soft-fail mode: silently refuses risky operations like map load, but doesn't die outright.

Refute path: same as H1 (skip the prior DR install / companion spawn cycle). Also: any sign of state change in the game process's OWN memory after a companion kill? Compare a snapshot BEFORE the companion spawn to one AFTER the kill — is there a game-side flag flip?

**H3 — fo's usual failure (FK-31 within 10s) was silently caught somewhere but the game is now in an inconsistent state.** fo's inject wrote its transient `.text` prologue patch, triggered FK-31's self-check, but somehow the crash was suppressed AND the game state got corrupted enough that LoadMap can't proceed.

Refute path: check `Loki.log` for `LogWorld`, `LogPartyManager`, `UEngine::Browse` errors or unusual entries between fo inject and the 180s timeout. Also check for any exception handlers firing (Sentry breadcrumbs).

## Ranked flights to run

### Flight 1 (cheapest) — repro F10 with NO prior DR install

Isolates whether H1/H2/H3 depend on the prior companion spawn/kill cycle.

```powershell
# fresh state
Stop-Process -Name ags,SUPERVIVE-Win64-Shipping -Force -ErrorAction SilentlyContinue

# launch with -CompanionWatch, wait for menu, then IMMEDIATELY stage (no DR install)
.\configs\launch-redirect.ps1 -NoHook -CompanionWatch

# wait for menu-ready (docs/next-session-prompt-s179.md has the polling loop)

# stage directly (no hwbp_movei call first!)
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_fo.dll -SkipProbe -Label s179-f10-repro -AllowStale
```

**Outcomes**:
- Stager succeeds (map loads, `[SP] done step=4` fires) → **H1/H2/H3 are all downgraded**; the companion-watch shipping default may in fact be safe for staging when no prior tampering is present.
- Stager fails same as F10 (map never loads, game stays alive on lobby) → **H1 or H2 supported**; the mere PRESENCE of companion-watch is toxic to staging even without prior kill activity.
- Stager fails via FK-31 during fo inject → **H3 supported OR unrelated**; consistent with fo's Control 1 (fresh boot + fo alone = FK-31 in 9-12s).

### Flight 2 — repro F10 exactly to confirm original observation

If Flight 1 outcome is anything but "same as F10", we need to know F10 is reproducible.

```powershell
# same launch as Flight 1
.\configs\launch-redirect.ps1 -NoHook -CompanionWatch

# wait for menu, install DRs to trigger + kill companion (S177 F9 recipe)
python scratchpad/s176/hwbp_movei.py

# wait ~90s for companion to spawn + be killed (log should show `kill_process(...) -> True`)

# NOW stage
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_fo.dll -SkipProbe -Label s179-f10-b -AllowStale
```

**Outcomes**: expect F10 result (map never loads, game alive). If reproduces, H1/H2 have a real target. If DOESN'T reproduce (staging succeeds this time), F10 was a one-off — pattern narrows.

### Flight 3 — Loki.log deep-dive during a F10-style flight

Add heavy log verbosity BEFORE the F10 repro. Look for what `Loki.log` says AFTER fo injection when LoadMap doesn't fire.

Add to user `Engine.ini` `[Core.Log]`:
```
LogWorld=VeryVerbose
LogWorldPartition=VeryVerbose
LogLoad=VeryVerbose
LogUObjectGlobals=VeryVerbose
LogEngine=Verbose
LogAccelByte=Verbose
```

Then repro F10 (Flight 2 recipe). Grep `Loki.log` for `Browse`, `LoadMap`, `LVL_Tutorial`, `Fatal`, `Warning:`, `Error:`, and anything the fo shim's expected code path would log.

Compare against a WORKING staging run (fresh boot, no `-CompanionWatch`, run stager normally — should complete in ~180s per historical data).

Discriminator: any line in the F10 log that DOESN'T appear in the working log names the branch that got skipped. Any line in the WORKING log that doesn't appear in F10 names what fo needed to do but couldn't.

### Flight 4 — timed companion-watch (only if F1..F3 haven't answered)

Modify companion_watch to kill the companion at t+N ms instead of on-sight. Run staging with the watcher armed but with kill delayed. If kill at t+3s (mid-lifetime, after companion has done its network round-trip but before terminate) lets staging succeed → the companion's ACTIONS during those 3s are what fo needs, and the companion's TERMINATION is what fo would tolerate.

This is a bigger tool change (~30-60 min). Only do if Flights 1-3 don't converge.

## Discriminator table (across the 3 flights)

| F1 outcome | F2 outcome | F3 diff | interpretation |
|---|---|---|---|
| stage succeeds | stage fails | (F3 not run) | **H2 supported**: prior companion kill puts game in soft-fail mode. Companion-watch is safe for staging AS LONG AS no prior trigger fired. |
| stage fails | stage fails | Fatal/Error log line in F10 | one of the log lines names the check. Fix that check, ship. |
| stage fails | stage fails | log identical to working run | fo's failure is silent (post-return / async). Try Flight 4 (timed kill) OR investigate fo's own code for what it depends on. |
| stage succeeds via FK-31 | (n/a) | (n/a) | Flight 1's outcome is what SHOULD happen if watcher is truly passive; F10 was a one-off. Companion-watch is safe. |

## What NOT to do

- **Do NOT try to run `fk24-stage.ps1` on a game that has NO `-CompanionWatch` armed AS the discriminator.** That's the S177 baseline and it produces staging success OR FK-31 death (28% per S111). Not comparing apples to apples with the F10 question.
- **Do NOT run more DR install / canary / manual-map trigger flights.** S178 generality already characterized all of those. New moves need to touch the SPECIFIC question of staging interaction.
- **Do NOT commit any `-Hook` shim flag with `-CompanionWatch`** until Flight 1/2's outcome is known. The current shipping doc says "Do NOT combine with fk24-stage.ps1" — respect that.
- **Do NOT try to bisect fo's source code.** It's the exact same file that used to work; the change is in RUNTIME state, not fo.

## Rules to bank (banked in docs/method-rules.md if any are new)

Two rules from S178 that are worth carrying:

- **S178-a**: `regrade_blocked.py` matches on citation text regardless of whether the citation is inside an EXPLICITLY-REFUTED historical quote. Any docs claim of the form "X was previously said to be Y" — even inside a "This is wrong because…" paragraph — still trips the tool. Adjudicate each hit by reading its surrounding paragraph; the flag alone is a floor, not a truth.
- **S178-b** (from ETW work): ETW CSV parsers must count row length dynamically, not trust the header column count. Windows Kernel-Process ETW schema-specific User Data is appended past the generic columns; exact count varies by event type. Fix your parser BEFORE quoting "no OpenProcess events observed."
- **S178-c** (from fo-alone control): T5's non-death in the generality flight was sequence-dependent (fo's usual FK-31 was suppressed by prior tampering). Any test that runs a trigger AFTER OTHER TRIGGERS must be corroborated with a fresh-launch control before publishing "trigger X does not fire."

## Session ledger (S177+S178)

- 9 live flights, 5 kills (2 FK-32 defeated by watcher, 2 controls FK-31, 1 baseline FK-32)
- 3 workflows (25 subagents, ~15M subagent tokens)
- 12 evidence docs + 6 tools + 4 commits pushed to `origin/dedicated-server-stub`
- Every open question about FK-32 mechanism is [M]
- FK-32 defeat [M] and shipped as `-CompanionWatch` opt-in flag on launch-redirect.ps1
- Only remaining engineering task on the FK-32 wall: the F10 mystery this doc asks you to close

## Artifacts you'll want

- `configs/launch-redirect.ps1` — the shipped defeat (search for `CompanionWatch` block)
- `scratchpad/s177/companion_watch.py` — the tool
- `scratchpad/s176/hwbp_movei.py` — the DR install trigger
- `configs/fk24-stage.ps1` — the staging harness (has its own defect handling — read its header)
- `dumps/s178-etw-openproc.csv` (75 MB) — Move #1's ETW capture; grep for PID 4940 (companion) events targeting PID 1664 (game)
- `dumps/s177-etw-kernel.csv` (75 MB) — S177's classic-kernel-logger capture with Process/Start/Stop for companion

## Success criterion

A single line in the S179 evidence doc that reads:

> **[M] F10's staging failure is caused by X**, where X is one of {companion-kill-side-effect, watcher-presence-signal, fo-shim-precondition-broken-by-Y, other-named-mechanism}. Reproduced twice with the same X in place, absent when X is removed.

If X turns out to be trivial (e.g. "prior companion kill sets game-side flag Z; unset Z before staging to restore"), the shipping followup is small — companion_watch adds an `--unset-flag-Z-before-detach` flag or the launcher does a warm-up staging attempt before arming.

If X is architectural (e.g. "fo's LoadMap fundamentally depends on companion state and no game-side workaround exists"), the shipping doc's "Do NOT combine with fk24-stage.ps1" warning is permanent and the FK-32 defeat + full staging combo needs a different approach entirely (a shim that IMPERSONATES the companion, perhaps).
