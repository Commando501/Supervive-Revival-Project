# S182 Rank 4 — the companion-kill halt mechanism is NOT a wedged thread [M]

**Live-flown 2026-09-07 in ONE game process (PID 9672).** Direct-observation refutation of
the S181 handoff's leading mechanism candidate (H4a-primary: "companion kill strands game
thread on missing sync object"). Preserved as `docs/s182-*.log`.

## Headline

★★★★★★★ **[M] NO thread in the SUPERVIVE process is wedged in a companion-related wait state
after the companion is killed.** Sampling all 137 threads once post-kill shows: 122 in
healthy ntdll wait states (WaitForSingleObject / MultipleObjects / AlertByThreadId /
WorkViaWorkerFactory / DelayExecution / IoCompletion), 4 in win32u.dll GDI syscalls, and 7
in normal protector `runtime.dll` code execution. **This is what a HEALTHY UE process looks
like.** The game thread specifically ticks at 29 ms `NtDelayExecution` intervals in
BOTH baseline and post-kill conditions.

⇒ **The S181 [M] finding (companion kill halts PI dispatch) stands, but its mechanism
CANNOT be "a thread stranded on a dead-owner sync object". The halt is a GATED-EXECUTION
mechanism**: a per-tick check that reads companion liveness state and skips PI-dispatching
work when the companion is dead, rather than a wait-blockage mechanism.

## The three-checkpoint measurement

Single game process (PID 9672), single continuous session:

| checkpoint | when | probe | game-thread RIP | RSP change | interpretation |
|---|---|---|---|---|---|
| **A** | baseline, PRE-F9 | 3× sample | 1× game code, 2× `NtDelayExecution+0x14` @ same RSP | RSP varies (1 sample in game code) | healthy tick-and-sleep cycle |
| **B** | POST-companion-kill, PRE-fo | 6× sample @ 3s intervals | 6× `NtDelayExecution+0x14` @ IDENTICAL RSP=`0x4ec29df2c8` | RSP frozen | "always in Sleep at this rate" — 29 ms delay means P(catch Sleep) ≈ 97% per random sample |
| **B2** | same, DR readback + delay decode | 4× sample | same as B; DRs=(dr0=runtime.dll+0x80F7F0, dr1=NtTerminateProcess, dr7=0x405); delay = **29.0 ms relative** | RSP frozen | game thread wakes every 29 ms — not stuck |
| **C** | DURING fo-verbose's 60s wait | 10× sample @ 3s intervals | same as B | RSP frozen | fo's presence does NOT change game thread state; identical to B |

**Key insight**: RSP is "frozen" in the sense that we always catch the thread inside the
same Sleep call. But `delay = 29.0 ms relative` tells us the thread wakes 34 times per
second and does work between wakes. It is NOT stuck in a blocking wait.

Sample identity check: Baseline sample 1 caught a DIFFERENT RSP (`0x4ec29de770`) with
RIP in game code — proving the game thread does exit the Sleep site periodically, at least
in baseline. That we caught NO such wake in 16 combined post-kill samples is consistent
with the same 29 ms Sleep + short game work loop; the 60s S181 measurement of hitsAny=0
proves the game-work portion doesn't dispatch PI, not that the thread is stuck.

## All-threads snapshot: no companion-wait wedge exists

Sampled all 137 threads once post-companion-kill
([docs/s182-rank4-all-threads-post-kill.log](docs/s182-rank4-all-threads-post-kill.log)):

| wait state | thread count | interpretation |
|---|---|---|
| `NtWaitForSingleObject` | 59 | event / mutex / semaphore / thread waits — normal UE |
| `NtWaitForMultipleObjects` | 25 | net/IO/task-manager waits — normal UE |
| `NtWaitForAlertByThreadId` | 18 | APC/lock waits — Win10+ synchronization — normal UE |
| `NtWaitForWorkViaWorkerFactory` | 10 | thread-pool workers idle for work — normal UE |
| `NtDelayExecution` | 9 | Sleep loops (includes game thread) — normal UE |
| `NtRemoveIoCompletion(Ex)` | 5 | I/O completion port workers — normal UE |
| `win32u.dll` | 4 | GDI/USER syscall — normal UE |
| unattributed RIPs (all in `runtime.dll` `0x7FFCA1400000..0x7FFCA5466000`) | 7 | protector integrity/check workers actively running — expected |

**137 threads accounted for. NONE is in a wait state that could reasonably be a companion
sync-object.** No pipe-read hang, no named-event-never-signaled hang, no mutex-owner-dead
hang. The distribution is what a healthy 137-thread UE process idle-parks like.

**DR install verification**: 30 threads have `dr7=0x405` (L0+L1+LE) and 37 threads have
`dr7=0x005` (L0+L1) — both have DR0/DR1 armed. ~70 threads have dr7=0 because they were
created AFTER `hwbp_movei.py` ran. That's expected — the script snapshots the thread list
at install time, and new threads inherit dr7=0.

## What this settles

**H4a-primary (thread stranded on dead-owner sync object) — [REFUTED] [M].** No thread is
in a state that matches this mechanism. If a mutex/event owned by the companion existed
and the game thread waited on it, that thread's RIP would be in `NtWaitForSingleObject`
with a specific object handle in rcx. Instead the game thread is in `NtDelayExecution` at
a 29 ms interval, which is a plain Sleep call, no cross-process object involved.

**H5-derivative (whole process reflection halt caused by ALL threads being stuck) —
[REFUTED] [M].** 137 threads, all in healthy states, none blocked on companion.

## What survives, refined

**S181's [M] finding stands: companion kill halts PI dispatch process-wide.** But the
mechanism is now [I,strong] one of:

- **H4a-refined**: A per-tick check inside game code reads companion liveness (a shared-
  memory flag, a periodic named-event acquire with 0-timeout, an APC status check, or a
  `ProcessInstrumentationCallback` return value) and if the companion is dead, the check
  path skips all reflection work — return early from the tick delegate, or skip the
  PI-dispatching sub-routines. Threads are not blocked; they run their normal loop, but
  the reflection-dispatching branch is not taken.

- **H4b**: The PI dispatches counted in the healthy baseline (S181 Rank 5: hitsAny=27
  over 60 s) originated from a mechanism EXTERNAL to the game process (e.g. companion
  fires APCs / ProcessInstrumentationCallbacks that dispatch reflection into the game
  process), and when the companion dies, that external source stops. From the game
  process's perspective, its own threads never called PI at any rate close to hitsAny=27;
  the 27 hits were companion-driven. No in-process branch skips anything; the companion
  simply is no longer causing PI to fire.

Both variants are consistent with S181's [M] + S182's [M]. Discriminating them requires
either:
- Reading the ProcessInstrumentationCallback state (needs `NtQueryInformationProcess`
  with `ProcessInstrumentationCallback` = class 40), OR
- Instrumenting fo-verbose to record the CALLER of each PI dispatch in baseline conditions
  (add caller-RIP capture inside OnPI), which would show whether callers are inside the
  game exe or inside runtime.dll / a jump-thunk-region owned by the protector.

## S182 rules banked

### S182-a: A "same RSP across multiple samples" observation is only strong evidence of a wedge if the LARGE_INTEGER Sleep interval (or wait timeout) is also LARGE. A 29 ms Sleep with a 3-second sample interval gives P(catch Sleep) ≈ 97% per sample, so 6 same-RSP samples in a row is entirely consistent with a HEALTHY ticking thread. Always decode the interval before concluding "frozen thread". [M]

Applied here: Checkpoint B initially read as "game thread frozen for 18 seconds" because
6 samples caught the same RSP. Adding the LARGE_INTEGER decode (single 8-byte RPM read at
[rdx]) revealed the interval is 29 ms — the thread is waking 34 times/sec, not once. The
frozen-thread interpretation would have been wrong. **Never conclude "wedged" from RIP+RSP
identity alone — read the wait interval.**

### S182-b: A whole-process wait-state census refutes the wedge class of hypothesis in ONE PID-scoped call. If 137 threads all sit in canonical Win32 wait states (WaitForSingleObject / WaitForMultipleObjects / AlertByThreadId / etc.) with no unattributed non-syscall RIPs in game-owned code, no single-thread wait-on-companion story can be the mechanism. This is cheaper than iteratively inspecting each thread. [M]

Applied here: One `all_threads.py` run categorized 137 threads by RIP-in-syscall vs
RIP-in-runtime.dll-code vs RIP-in-game-code. All 137 fell into normal categories. That
one snapshot eliminated an entire hypothesis family in one measurement.

### S182-c: When a stale marker file is left over from a prior session, a probe that reads it can silently use a dead TID. Always prefer live RPM reads of the game's own state field over a marker parse; fall back to the marker only when RPM fails. [M]

Applied here: `gt_inspect.py`'s first version defaulted to reading gameTid from
`docs/tutorial-launch-marker.txt`, which contained a TID from a previous session's dead
PID. `OpenThread` on that TID would have failed silently. The fix reorders the fallbacks
to RPM-first and reports the source in the marker.

### S182-d: `GetThreadContext` populates only the fields declared in ContextFlags. Missing `CONTEXT_DEBUG_REGISTERS` (0x10) from ContextFlags returns DR0-DR7 as uninitialized memory (typically zero, matching the caller's initial memset), which reads as "no DRs armed" — the exact false negative that would refute the CORRECT presence of DR install. [M]

Applied here: First Checkpoint B pass showed `dr0=0 dr1=0 dr7=0` and I initially treated
that as "the DRs were not installed on the game thread". The fix (adding 0x10 to the
context flags) revealed the true values: `dr0=runtime.dll kill primitive`,
`dr1=NtTerminateProcess`, `dr7=0x405` — DR install is correct and present.

## What is now open

1. **Discriminate H4a-refined vs H4b**: instrument fo-verbose to capture the caller-RIP
   of each ProcessInternal invocation. In baseline (Rank 5 conditions), if the 27 caller-
   RIPs are mostly inside game-exe code, then H4a-refined wins (the game itself calls PI
   and stops after companion kill). If they are inside `runtime.dll` code or in a heap
   region owned by the protector, H4b wins (companion / external source is what dispatches).

2. **What is the shared-memory / callback / IPC mechanism the game reads to check companion
   liveness?** If H4a-refined, find the per-tick check. If H4b, find where the companion
   used to inject APCs / callback returns. Both require identifying a very specific address
   the game reads or the companion writes to.

3. **Practical: with the mechanism narrowed away from thread-wedge, could the fk24 stager
   work if fo is injected BEFORE the companion spawns (~t+146s)?** Baseline showed fo works
   fine when companion is alive. If we inject at t=~30s (well before companion spawn), the
   game's own tick body dispatches PI (Rank 5 measured hitsAny=27 / hitsGT=1 in a similar
   window). This is the cheapest shipping path — no mechanism identification needed if the
   timing is reliable.

## Files preserved

- `docs/s182-rank4-checkpointA-baseline.log` — 3 samples, PRE-F9, showing game code + 2 sleeps
- `docs/s182-rank4-checkpointB-postCompanionKill-noFo.log` — 6 samples, POST-kill, PRE-fo (initial pass, DR bug)
- `docs/s182-rank4-checkpointB2-postCompanionKill-noFo.log` — 4 samples with DR + delay decode
- `docs/s182-rank4-checkpointC-duringFoWait.log` — 10 samples during fo's 60s wait
- `docs/s182-rank4-all-threads-post-kill.log` — the 137-thread snapshot
- `scratchpad/s182/gt_inspect.py` — single-thread inspector with DR + Sleep decode
- `scratchpad/s182/all_threads.py` — whole-process wait-state census

## What S182 did NOT do

- **No source edits to `tutorial_launch.cpp` or `build.ps1`** — Rank 4 was purely
  read-only external probes. Zero risk to game state.
- **No H4a-refined / H4b discriminator** — that needs fo-verbose Rank 6 (caller-RIP
  capture in OnPI), which is a rebuild. Recommended as the next flight.
- **No commit yet** — evidence + probe + doc bundled for the next commit.
