# S180 Next-Session Prompt — why does the game thread stop dispatching ProcessInternal after S177 F9?

**Fresh-session paste-ready prompt.**
**Date written:** 2026-09-07
**Previous session:** S179 — see `docs/s179-f10-mechanism-settled.md` for the settled write-up. Two commits landed and pushed to `dedicated-server-stub`: `4824c77` (fo-verbose instrumentation, byte-identical `fo`), `1dde57d` (F10 mechanism settled + evidence).

---

## Paste this as the opening message

Continuing SUPERVIVE Revival Project. Last session (S179) settled the F10 mystery by adding `KFOVERBOSE` instrumentation to fo, re-flying under the S177 F9 antecedent state, and measuring what fo actually did. The workflow's Ranks 1/2/3 candidates and every prior hypothesis (H1/H2/H3/H4) were REFUTED. The measured mechanism reframes the whole problem: **fo is architecturally sound. The game thread stopped dispatching `ProcessInternal` reflection calls after the F9 sequence.**

Your task: **understand why**. Fo installed its PI hook cleanly, took the `Local\SuperviveMissionsPIHook` mutex, then waited 8 seconds for a game-thread `ProcessInternal` dispatch and got zero (`hitsGT=0`). A healthy menu-parked game dispatches PI hundreds of times per second. Zero in 8 seconds is a hard stall of the reflection dispatch loop on the game thread. This is what makes `LoadMap` never fire under `-CompanionWatch` staging.

Recipe + branching discriminators below. Read the top 3 docs I name before flying.

## Read first, in order

1. **[docs/s179-f10-mechanism-settled.md](s179-f10-mechanism-settled.md)** — the settled write-up. §Headline, §"The measured marker (17 lines)", and §"Three concrete findings" are the load-bearing sections. Read the §Caveats block too — the [M]→F10 transfer is [I, strong], not [M], because F10's live marker was overwritten.
2. **[docs/s179-f10-verbose-fullmarker.txt](s179-f10-verbose-fullmarker.txt)** — the 17-line diagnostic marker itself. Read it line by line; every claim in the doc lives here.
3. **[docs/s175-s176-synthesis.md](s175-s176-synthesis.md)** §"R-S176-k" — the AVEH-returns-NULL rule S179 initially mis-read as novel. This is a base property of manual-mapped shim bodies, not a signal about F9. Reading this saves you from re-committing the same mistake.

Then skim:
- `tools/sigbypass-mod/tutorial_launch.cpp` lines 23756-24680 — the Worker function and the RM_FORCEOPEN code path. Note where `[4] TIMEOUT` emits: it's the FsHold budget on the funcswap arm, or the InstallHook + Sleep loop on the PI-hook arm.
- `configs/launch-redirect.ps1` — the `-CompanionWatch` block (~line 380). Nothing S180-specific here; just orient.
- `scratchpad/s176/hwbp_movei.py` — the DR-install trigger. This is what starts the S177 F9 sequence.
- CLAUDE.md's S177/S178 tonight-blocks describing FK-32 defeat mechanism.

**Do NOT re-read**: the full S179 CFG-walk workflow output (60 KB) or the initial S179 offline synthesis. Both were refuted by the fo-verbose flight. The settled doc supersedes them.

## What's known [M] (updated from S179's opening)

- **FK-32 mechanism**: `runtime.dll` companion spawn + `NtTerminateProcess(0xDEAD)`. Killable within ~220ms via the watcher.
- **FK-32 defeat [M]**: `-CompanionWatch` kills the companion, game stays alive 24+ hours (S179 flight confirmed the game process survives ≥23h53m after F9 defeat holds).
- **`-CompanionWatch` filter is surgical [M]**: `--only-name runtime.dll` — ignores conhost/EpicWebHelper/crashpad_handler.
- **FK-31 is orthogonal to `-CompanionWatch` [M]**: in-process self-check, watcher doesn't defeat it.
- ★★★★★ **F10 fo does NOT hang** [M for today's flight; [I, strong] transfer to F10]: fo runs to completion — DllMain → LoadCommand → GetModuleHandleA → AVEH install (NULL, per R-S176-k) → WaitTid → Resolve(1 iter, 2922ms) → `[2] worldCtx=` → `[3] hook built` → PI mutex acquired → **`[4] TIMEOUT no game-thread PI in 8s (hitsGT=0)`** → clean vtable restore → `[5] done` → `[6] freed`.
- ★★★★★ **The F10 3-line marker was a stager t=2s snapshot artifact** [M]: fk24-stage.ps1's Stage-Inject sleeps only 2s before copying the marker. Fo's silent interval between `[0] command` and `[2] worldCtx=` spans ~3 seconds. Every `fk24-stage-*-2-fo.txt` file has the same 3-line shape by design.
- ★★★★★ **AVEH returns NULL for manually-mapped shim DLL bodies [M]**: R-S176-k, banked 2026-09-03 across 3 prior flights, S179 F10 is the 4th measurement. Mechanism unresolved (either ProcessInstrumentationCallback denies VEH registration, or Windows treats RWX-mapped bodies specially). Independent of DR install, companion kill, or F9 antecedent. **Not a signal about F9 state.**

## The mystery (S180)

**Question**: What specifically about the S177 F9 sequence — `hwbp_movei.py` DR install on all game threads + runtime.dll companion spawn + watcher kill — stops the game thread from dispatching `ProcessInternal` reflection calls?

**Direct measurement (S179 F10 flight, docs/s179-f10-verbose-fullmarker.txt)**:
- Fo's PI hook was installed cleanly at `0x7FF724D7D790` (rva `0x395D790`, ExecuteConsoleCommand thunk)
- `Local\SuperviveMissionsPIHook` mutex acquired CLEAN — no other PI-hooker contending
- 8 second wait: `hitsGT=0` — ZERO game-thread dispatches through ProcessInternal
- Fo cleanly restored the vtable and exited

**Constraint**: the game process stayed ALIVE (24 hours uptime by session end) and continued running telemetry POSTs and party-latency updates. So it's not that the game thread crashed or was suspended — it's that the reflection-call dispatch loop is somehow bypassing fo's PI hook OR nothing on the game thread is calling any BP UFunction during the 8s window.

**Three top hypotheses** (grade [I,strong] each based on S179 evidence; measure to promote to [M]):

**H1 — DR breakpoints stall reflection dispatch.** `hwbp_movei.py` installs DR0/DR1 on `runtime.dll HIGH kill @ 0x7FFCA1C0F7F0` and `ntdll!NtTerminateProcess @ 0x7FFCA10CDB80`. Any thread hitting those addresses raises `STATUS_SINGLE_STEP`. The game thread may be repeatedly hitting them (or the exception dispatch path they trigger), stalling in an OS unhandled-exception loop.

Refute path (offline): read `hwbp_movei.py` — does it CLEAR the DRs after the companion kill? If not, they persist across the whole flight. Refute path (live): fly the S177 F9 recipe, then IMMEDIATELY use SetThreadContext to clear DR0-DR3 on all threads BEFORE injecting fo. If PI dispatch resumes, H1 is [M].

**H2 — Something in `ProcessInternal`'s own `.text` was disrupted.** Fo hooks ProcessInternal via a 5-byte `0xE9` jmp at `kPiRva`. That patch is transient (fo installs, waits, uninstalls). But if the protector's self-check has re-patched `ProcessInternal` back to a different state, or if DR install triggered a `.text` decrypt/re-encrypt cycle, the game's PI callers might be dispatching through a corrupted path that never reaches fo's hook.

Refute path: RPM-read `ProcessInternal`'s first 16 bytes at `kPiRva` (from `tutorial_launch.cpp`) BEFORE fo injection and AFTER fo installs its hook. Compare against the pre-DR-install baseline. Any byte difference outside fo's own 5-byte jmp is diagnostic.

**H3 — The game thread became a "no reflection" thread.** Fo hooks the ProcessInternal dispatched from a specific `g_gameTid`. If the DR install perturbed the thread scheduler such that the identified `g_gameTid` is no longer the thread actually dispatching PI, fo's hook is on the wrong thread. Fo counts hitsGT via a game-thread ID match at hook entry.

Refute path (offline): read fo's `OnPI` at `tutorial_launch.cpp` — how does it identify "the game thread"? Read `WaitTid` at line 1637 — what memory location does it poll for `g_gameTid`? If that field can be stale, H3 is plausible. Refute path (live): instrument fo-verbose to count PI dispatches on ALL threads, not just `g_gameTid` — if PI is still dispatching but on a different TID, H3 is [M].

## Ranked flights to run (offline-first, per S179's method-rules banking)

**Flight 1 (OFFLINE, highest yield)** — Read `scratchpad/s176/hwbp_movei.py` for DR cleanup. If it never clears DRs after companion kill, H1's precondition is satisfied and a live discriminator becomes cheap.

**Flight 2 (OFFLINE)** — Read `tutorial_launch.cpp` `OnPI` and `WaitTid`. How does fo identify "the game thread"? Is `g_gameTid` a single field polled once, or does fo track thread migrations? Answer determines whether H3 is even mechanically possible.

**Flight 3 (LIVE, cheapest live discriminator)** — Instrument fo-verbose further: add a per-thread PI hit counter (small map `TID → hits`) reported at `[4] TIMEOUT` if `hitsGT=0`. If a NON-`g_gameTid` thread got hits, H3 is confirmed and fo's hook needs re-targeting. If ALL threads showed 0 hits, PI is genuinely not dispatching — H1 or H2 wins.

**Flight 4 (LIVE, discriminates H1 vs H2)** — After F9, before injecting fo: RPM-read `ProcessInternal` bytes at `kPiRva` and compare to a fresh-boot baseline. Also clear DR0-DR3 on all threads via SetThreadContext. Inject fo. If PI dispatch resumes → H1. If bytes differ → H2.

**Flight 5 (LIVE, practical workaround)** — Build a fo variant that uses S55 direct-thunk primitive to call `ExecuteConsoleCommand` explicitly, bypassing the PI dispatch entirely. If it works, F10 is engineering-solvable independent of understanding the root cause. This is the fastest path to `LVL_Tutorial` under `-CompanionWatch`, and it lets a successor iterate on other shims that need staging while the H1/H2/H3 question remains open.

## What NOT to do

- **Don't re-fly stock fo expecting a different result.** F10 is not going to reproduce differently without a controlled variable change. The KFOVERBOSE instrumentation already answered "what does fo do post-F9"; the question now is upstream.
- **Don't add more Marker() calls to fo hoping to see something new.** The 17-line marker is the complete Worker trace. What we don't see is game-thread activity — that requires RPM reads or a game-thread-side probe.
- **Don't claim any signal is "novel" without grepping docs/** first. S179 lost a full workflow-verification pass to this exact failure mode. See S179-c in the settled doc for the register instance.
- **Don't remove `-CompanionWatch`'s "do not combine with staging" warning yet.** Even if you solve F10 via Flight 5, the LoadMap-under-companion-watch path is not proven safe until measured, and CLAUDE.md's line is protection.
- **Don't rebuild fo-verbose without also verifying `.text` byte-identity of `fo`**. The `#if KFOVERBOSE` guards make this the reference gate for any future fo edits. Digest: `31d4e4dc0b9c9b5e` (RAW recipe).

## Rules to bank

Two new S179 rules already banked in the settled doc, worth carrying into method-rules if not yet folded:

- **S179-a**: Stager marker snapshots at t=2s can create false bail signals. Any "the marker stopped at line N" claim must first verify that line N is emitted by t=2s post-injection in a WORKING run. Applied here: F10's 3-line marker read as a bail. Wasn't.
- **S179-c**: Before claiming a signal is a "first-time observation", grep `docs/` for the API name and the value being reported. Applied here: `AVEH handle=0x0` was banked as R-S176-k three days earlier; S179's initial write-up called it novel and only adversarial verification caught it.

Also worth banking (from S179's workflow experience):

- **S179-d** (already in settled doc): Workflow subagents speculating about function behavior without reading the function is a specific failure mode. All three CFG-walk Ranks 1/2/3 were fabricated from source they didn't read. Direct source reads refuted them in minutes. Always seed function-behavior questions with the actual source, not "here's the function name, what does it do".

## Session ledger (S179)

- 2 commits pushed to `dedicated-server-stub`: `4824c77` (fo-verbose byte-identity verified) + `1dde57d` (F10 mechanism settled, 7 files, 319 lines)
- 1 live flight (fo-verbose in F9 antecedent state), ~4 minutes elapsed, game survived 24+ hours post-flight
- 2 workflows (`wf_7f899fdc-61d` offline CFG walk — REFUTED by source reads; `wf_e4607476-497` adversarial verification of the settled doc — CAUGHT the "novel" mis-claim)
- 1 new build variant: `tutorial_launch_fo-verbose.dll` (`.text` digest `0334fba2a0b13c4f`, +1024 bytes vs `fo`)
- Every open question about the F10 3-line marker is settled
- Only remaining question on this wall: **what breaks game-thread PI dispatch after F9**

## Artifacts to consult

- `docs/s179-f10-mechanism-settled.md` — the settled write-up
- `docs/s179-f10-verbose-fullmarker.txt` — the 17-line diagnostic marker (F10 mechanism evidence)
- `docs/fk24-stage-s179-f10-verbose-2-fo.txt` — the stager t=2s snapshot (6 lines vs F10's stock 3)
- `docs/companion-watch.20260906-132240.log` — F9 defeat evidence (runtime.dll kill at t+146s)
- `tools/sigbypass-mod/build/tutorial_launch_fo_verbose.dll` — the instrumented shim (rebuild with `build.ps1 -Name tutorial_launch -Variant fo-verbose`)

## Success criterion

A single line in the S180 evidence doc that reads:

**[M] The mechanism halting game-thread ProcessInternal dispatch after S177 F9 is X**, where X is one of:
- a named DR-triggered exception loop on the game thread
- a named `.text` corruption in `ProcessInternal` or its downstream
- a named thread-migration event moving PI dispatch off the identified `g_gameTid`
- other-mechanism (specify)

Corroborated across 2+ flights with a clean control that ISOLATES the F9 sub-step (DR install alone vs companion spawn alone vs kill alone vs kill on-a-different-companion).

If the mechanism turns out to be unfixable at the shim level (e.g. permanent OS-level thread state change), Flight 5 (S55 direct-thunk fo variant) becomes the shipping path — F10 becomes "avoid PI-hook route under `-CompanionWatch`, use direct thunk instead".
