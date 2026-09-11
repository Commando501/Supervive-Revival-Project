# S190 — halt-gate hunt: mechanism (a) REFUTED [M], mechanism (b) has concrete candidate via MSVC `_Init_thread_header` SRW-leak [I,strong]; promoted to S191 live probe

**Offline 2026-09-08**, disassembly against `dumps/merged14.dump.exe`, zero live flights.
Multi-agent workflow `wf_7528337c-87e` — 4 parallel investigation lanes + 1 adjudicator, 5/5 done,
0 errors, ~2.01M subagent tokens. Plus follow-up inline offline analysis of the 4 Tick static-init
guards + all callers of `_Init_thread_header` image-wide.

> **Companion docs** (read alongside): [docs/s189-caller-hunt-settled.md](s189-caller-hunt-settled.md)
> and [docs/s189-caveat2-second-gfc-site-settled.md](s189-caveat2-second-gfc-site-settled.md).
> Those establish that the halt gate is UPSTREAM of FEngineLoop::Tick 0x4028110 (Site 3
> fires unconditionally per Tick invocation). This doc localizes the gate further.

## Headline

★★★★★★★ **[M] MECHANISM (a) AS ORIGINALLY FRAMED IS REFUTED (Lane B).** The GuardedMain-like
loop's shutdown byte at `.data:0x9d29104` is stock UE `GIsRequestingExit` (Lane A [I,strong], 3
writers enumerated: two `RequestEngineExit` variants at `0x10D736F`/`0x10D73C8`, plus one gated
helper at `0x10BC829` called from Tick itself). But flipping it causes **CLEAN PROCESS
TERMINATION** — loop exits → cleanup calls at `0x4030078`/`0x4030084` → GuardedMain returns →
WinMain calls `ExitProcess`. Not the observed "process alive, GFrameCounter frozen" pattern.

★★★★★★ **[I,strong] MECHANISM (b) HAS A CONCRETE CANDIDATE (Lane D).** MSVC `_Init_thread_header`
at RVA `0x751E240` is called FOUR TIMES directly from FEngineLoop::Tick's chained extent, and
invokes `SleepConditionVariableSRW(&srw, &cv, INFINITE, 0)` at RVA `0x751E275` when the paired
guard reads `-1`. **The refined mechanism is that the SHARED SRW at `.data:0x764A488` (or the
shared CondVar) is leaked by any dying thread mid-critical-section, blocking every subsequent
`_Init_thread_header`/`_Init_thread_footer` call from any thread — regardless of which specific
guard it's checking.**

## S190 offline follow-up: the 4 Tick guards decoded

Inline analysis of the 4 `_Init_thread_header` call sites' preceding `lea rcx, [rip+X]`
instructions yields the 4 guard addresses:

| Tick call site | LEA preamble @ | disp32 | Guard RVA | Guard VA | jne target (past-init) |
|---|---|---|---|---|---|
| `0x4029640` | `0x4029639` (`48 8d 0d 00 71 f9 05`) | `0x5F97100` | `0x9FC0740` | `0x7FF612F00740` | jne `0x4029312` |
| `0x4029683` | `0x402967C` (`48 8d 0d 75 70 f9 05`) | `0x5F97075` | `0x9FC06F8` | `0x7FF612F006F8` | jne `0x40287F0` |
| `0x40296F2` | `0x40296EB` (`48 8d 0d 2e 70 f9 05`) | `0x5F9702E` | `0x9FC0720` | `0x7FF612F00720` | jne `0x402927B` |
| `0x4029734` | `0x402972D` (`48 8d 0d fc 6f f9 05`) | `0x5F96FFC` | `0x9FC0730` | `0x7FF612F00730` | jne `0x402928B` |

**All 4 guards sit in a 0x48-byte cluster (0x9FC06F8..0x9FC0740)** in `.data` — canonical MSVC
grouping of C++11 threadsafe-static-local guards within a single translation unit's function.

### Guard values in menu-era merged14 (offline snapshot)

| Guard RVA | Value (raw) | As signed int32 | Interpretation |
|---|---|---|---|
| `0x9FC06F8` | `71 17 00 80` | `-2147477647` (0x80001771) | Initialized (positive epoch, not `-1` in-flight) |
| `0x9FC0720` | `ab 17 00 80` | `-2147477589` (0x800017AB) | Initialized |
| `0x9FC0730` | `ac 17 00 80` | `-2147477588` (0x800017AC) | Initialized |
| `0x9FC0740` | `b2 17 00 80` | `-2147477582` (0x800017B2) | Initialized |

**⚠ Menu-era, not gameplay-era.** The gameplay-era guard state cannot be settled offline; a live
RPM read of these 4 addresses is what step 3 of the S191 live probe does.

### Each guard has EXACTLY 1 header call + 1 footer call, both inside Tick

Full image-wide census of `LEA rcx, [rip+X]` referencing each guard:

| Guard | Ref count | Sites |
|---|---|---|
| `0x9FC06F8` | 2 | `0x402967C` (`_Init_thread_header` call), `0x40296D3` (paired `_Init_thread_footer`) |
| `0x9FC0720` | 2 | `0x40296EB` (header), `0x402971C` (footer) |
| `0x9FC0730` | 2 | `0x402972D` (header), `0x402977F` (footer) |
| `0x9FC0740` | 2 | `0x4029639` (header), `0x402966B` (footer) |

All 8 sites are inside Tick's chained extent (`0x4028110..0x4029797`). **No external code references
any of these 4 guards.** These are 4 MSVC C++11 threadsafe static locals declared in FEngineLoop::Tick's
end-of-frame block body — likely the four `FScopedNamedEvent`/`STAT_*` static registrations for the
`FrameCounter` / `EndFrame` / `FScene_EndFrame` / `ResetDeferredUpdates` scope labels S189-caveat2
Lane A found LEAs to at RVAs `0x40293D8`/`0x4029507`/etc.

### The `_Init_thread_header` reachability census image-wide

- **Total callers of `_Init_thread_header` (`0x751E240`): 9,448**
- **Distinct guards: 8,624**
- Only 1 caller has a non-standard preceding LEA (a false hit at `0x3754004` from linear byte
  overlap — capstone rejects it as non-instruction-boundary)
- Top guard by shared caller count: `0x9D1AC34` — 124 different call sites use `_Init_thread_header`
  on this one guard (widely-shared UE static)
- Top 10 guards by caller count: 12–124 callers each (all widely-shared UE statics; none of the 4
  Tick guards are in this top set — the 4 Tick guards are UNIQUE to Tick)

## Mechanism refinement: shared SRW leak, not per-guard corruption

The initial Lane D framing was:
> If any thread entered `_Init_thread_header` on one of these 4 guards and died before its paired
> `_Init_thread_footer` ran, every subsequent Tick invocation hits an unbounded condvar wait.

**S190 offline census REFINES that framing:** each of the 4 Tick guards has exactly 1 header
caller (the Tick body itself). For the mechanism to fire on THOSE specific guards, the game
thread would have to have entered `_Init_thread_header` on one of them, transitioned the guard
0 → -1, released the SRW, started the init body, and then died. But the game thread dying would
crash the process, contradicting the observed "process alive" pattern.

**⇒ The corrected mechanism is that the SHARED SRW at `.data:0x764A488` (or the shared CondVar,
also global) is leaked by a dying thread mid-critical-section, causing all subsequent
`_Init_thread_header`/`_Init_thread_footer` calls to block on `AcquireSRWLockExclusive` forever
— regardless of which of the 8,624 guards they're targeting.**

Windows SRWLocks are NOT automatically released when the owning thread dies. If `-CompanionWatch`'s
kill primitive terminates a companion thread inside `_Init_thread_header`'s AcquireSRW→check→
ReleaseSRW window (a few instructions long, but 9,448 total call sites means any of them is a
potential trigger), the SRW is leaked, and every subsequent `_Init_thread_header` call from ANY
thread (including the game thread's next Tick call) blocks forever.

This mechanism:
- Matches S187 [M]: GFrameCounter frozen (Tick never returns past the first `_Init_thread_header` it
  hits post-kill)
- Matches S188 [M] on real Tick: Tick has 1 ret + no early-exits (the block is inside a callee,
  not in Tick itself)
- Matches S189-caveat2 [M]: Site 3 fires unconditionally IF Tick runs, but Tick doesn't run to
  completion — it enters `_Init_thread_header` at any of the 4 call sites (which the CFG shows
  are reached via `jg` from earlier in Tick, and the guard being positive means "past-init" jne
  IS taken normally — but if AcquireSRW blocks, we never get to the CMP that checks the guard)
- Matches R-S186-a: a shared-downstream halt of AActor + UAnimInstance + UUserWidget cannot be
  explained by any per-subsystem gate, BUT the shared `_Init_thread` SRW is exactly the kind of
  shared upstream that fits — any subsystem's static-init could touch it
- Matches S181's F10 background: `-CompanionWatch` halts UE tick dispatch process-wide (any thread
  dying inside the `_Init_thread` critical section blocks the frame pump)

## Alternative surviving mechanisms

- **(a-alt) Cleanup-blocks** [Lane B]: byte `0x9d29104` flips, loop exits, but the post-loop
  cleanup call at `0x4030084` → fn `0x402F470` (AppPreExit-shaped: HotReload / AssetRegistry /
  UnloadModulesAtShutdown / WorldBrowser / StreamingSettings, 1114 B) blocks indefinitely. OR the
  DARK-page cleanup call at `0x4030078` → fn `0x4017380` (COVERAGE-BLOCKED in merged14) blocks.
  Discriminated by step 1 (byte read) of the S191 live probe: if byte is 1, this is on; if 0,
  refuted.
- **(b-alt) Per-object CS deadlock** [Lane C rank #1]: fn `0x2B7FD50` (498 B) is called 7×
  from Tick and has a per-object CS try-lock at `[rsi+0x28]`, with slow-path chain `0xF95730 →
  0xF9C930` (heavy, calls into obfuscated IAT). If the CS is held by a killed thread, Tick's next
  call to this callee blocks. Discriminated by step 2 (thread stack) of the S191 live probe.
- **(c) Game-thread suspended/deadlocked BEFORE re-entering Tick**: requires step 2 to show RIP
  in `SleepConditionVariableSRW`/`WaitForSingleObject` with NO Tick frame on stack.

## Live probe design (S191)

Pre-registered, ~15-30 seconds wall clock against a wedged process. Three steps:

### Step 1 (~1s, pure RPM): byte + guard read

```
OpenProcess(PROCESS_VM_READ, PID)
ReadProcessMemory(base + 0x9D29104, &b1, 1)      // GIsRequestingExit
ReadProcessMemory(base + 0x9D28B18, &b2, 1)      // HARD-DOWN gate
ReadProcessMemory(base + 0x9FC06F8, &g1, 4)      // Tick guard 1
ReadProcessMemory(base + 0x9FC0720, &g2, 4)      // Tick guard 2
ReadProcessMemory(base + 0x9FC0730, &g3, 4)      // Tick guard 3
ReadProcessMemory(base + 0x9FC0740, &g4, 4)      // Tick guard 4
```

### Step 2 (~5s): thread stack sample on the game thread

```
OpenThread(THREAD_ALL_ACCESS, ..., game_thread_TID)   // TID from S182 baseline or RIP grep
SuspendThread(hThread)
GetThreadContext(hThread, CONTEXT_FULL)
StackWalk64(...)                                       // walk N frames until _Init_thread_header
                                                       //   or Tick range or Sleep* observed
ResumeThread(hThread)
```

### Step 3 (~10s, conditional): lock/handle census

If step 2 shows RIP in `SleepConditionVariableSRW` or `AcquireSRWLockExclusive`:
```
ReadProcessMemory(base + 0x764A488, &srw, 8)          // shared SRW state
ReadProcessMemory(base + 0x764A488 + 8, &cv, 8)       // shared CondVar state (approx)
```
Enumerate `_Init_thread_header` callers to find which subsystem's static-init the companion held.

### Discriminator table (6 outcomes → mechanism)

| Observation | Mechanism | Next action |
|---|---|---|
| `b1==1 AND stack in 0x402F470/0x4017380/0x40396xx chain` | **(a-alt) [M]** — loop exited cleanly but shutdown-chain callee blocks | Recursive-descent CFG of the blocking callee for WaitForSingleObject / EnterCriticalSection / SleepEx / thread-join sites; live-decrypt DARK-page 0x4017380 via graceful-shutdown fire + re-dump |
| `b1==0 AND stack in 0x751E240..0x751E290 AND [SRW at 0x764A488 held with no valid owner]` | **(b) [M]** — shared SRW leaked by dying thread | Enumerate _Init_thread_header callers in companion-kill-reachable code; the killed thread's callee is the trigger site |
| `b1==0 AND stack in 0x751E240..0x751E290 AND [guard at rcx == 0xFFFFFFFF]` | **(b-variant) [M]** — specific guard stuck at -1 (requires the dying thread to have called _Init_thread_header on the same guard, unlikely for the 4 Tick-specific guards) | Identify guard's RVA from rcx; check which OTHER function set it -1 |
| `b1==0 AND stack in 0x2B7FD50 or slow-path 0xF95730/0xF9C930` | **(b-alt) [M]** — per-object CS deadlock (Lane C rank #1) | Decode obfuscated IAT slot at final indirect call in 0xF9C930 chain; enumerate callers holding [rsi+0x28] lock |
| `b1==0 AND stack in SleepConditionVariableSRW/WaitForSingleObject with NO Tick frame on stack` | **(c) [M]** — game thread suspended before Tick re-entry | S182-style full thread census; identify which handle/lock the game thread waits on; correlate with companion-kill code path |
| `b1==0 AND stack in Tick past GFrameCounter store (0x402935A..0x4029797)` | not any of (a)/(a-alt)/(b)/(c) | S189-caveat2 Site-3-unconditional claim needs re-verification; check GFrameCounter parity |
| `b2==1 AND process still alive` | novel external injection — HARD-DOWN gate has 0 in-.text writers per Lane A | Search for external writer surface (kernel driver, other module, WriteProcessMemory from companion) — separate investigation, not FEngineLoop-native |

## Full outer caller chain [M] (from Lane B)

```
WinMainCRTStartup       0x751EE5C  (369 B, CRT bootstrap)
  └── call 0x751EF5D → WinMain-like       0x4039680  (213 B, "Exiting." string ref)
        └── call 0x4039691 → CommonMain    0x4030E50  (386 B, SEH-vs-unattended dispatch)
              └── call 0x4030F67 → GuardedMainWrapper 0x40300C0  (53 B, MSVC __try SEH wrapper)
                    └── call 0x40300D5 → GuardedMain body        0x402FD90  (810 B, contains Tick loop)
                          └── loop @ 0x4030053:
                                call 0x403005A → FEngineLoop::Tick 0x4028110  (~5.7 KiB chained)
                                cmp byte [.data:0x9d29104], 0
                                je 0x4030053   (back to loop head)
```

Dominators of the `call 0x4028110`:
- `0x40300CC cmp byte [.data:0x9AEA788], 0` — launch-decision (SEH vs bypass); once-at-startup, does NOT gate per-tick
- `0x402FECB cmp byte [.data:0x9D29104], al` — early setup read; dominator but not a plausible gate
- `0x402FFD1 cmp byte [.data:0x9D28E78], 5` — setup log-verbosity threshold; dominator but not a gate
- `0x4030041 cmp byte [.data:0x9D28B18], 0` — **HARD-DOWN gate** (jne to shutdown 0x4030089); 0 writers in `.text` image-wide → could only be flipped by external injection
- `0x403004A cmp byte [.data:0x9D29104], 0` — **pre-tick GIsRequestingExit gate** (jne to cleanup 0x4030068); if non-zero → CLEAN TERMINATION not freeze
- `0x403005F cmp byte [.data:0x9D29104], 0` — post-tick loop-back test (je back to loop header)
- `0x4030068 cmp byte [.data:0x9D28B18], 0` — post-loop HARD-DOWN test (jne to shutdown)

No per-tick .data byte dominator exists that when flipped would leave the process alive but stop
reaching Tick. All gate-flips result in process termination. Hence mechanism (a) refuted.

## Rules banked (new)

### R-S190-a: A byte-pattern shape scan must compute `rip_after = ins_addr + FULL_ins_len` (prefix + modrm + disp32 + trailing_immediate). A reg-form positive control validates ONLY the reg-form sub-scanner and cannot detect an off-by-imm defect in the imm-form sub-scanner.

Applied here: Lane A's first-cut scan for writers of `.data:0x9d29104` computed
`rip_after = ins_addr + prefix_len + 4` (dropping the trailing `imm8` for `c6 05 disp32 imm8`
byte-move-immediate instructions), mis-attributing real writers to the address `0x9D29103` (off
by one). GFrameCounter's 5 writers use only imm-free `48 89 05` / `48 FF 05` shapes, so a positive
control on GFrameCounter would not detect the imm-form bug. **Always cross-verify at least one
imm-form site by direct disassembly** before running an imm-form scan at scale.

### R-S190-b: MSVC `_Init_thread_header` static-init guards are per-call-site, but the SRW and CondVar are SHARED GLOBALS. A dying thread that leaks the shared SRW mid-critical-section blocks EVERY subsequent `_Init_thread_header` call from ANY thread, regardless of which guard is being targeted. In any project where cross-thread state is being killed, `_Init_thread_header` callers reachable from the game thread's per-frame loop are a systematic halt-mechanism candidate.

Applied here: refined mechanism (b) uses the shared SRW at `.data:0x764A488` (identified in Lane
D as the argument to `SleepConditionVariableSRW` at `0x751E275`). All 9,448 `_Init_thread_header`
callers in the image potentially contend on this SRW. Any dying companion thread inside the
AcquireSRW→check→ReleaseSRW critical section leaks the SRW; the game thread's next Tick call
hangs forever on `AcquireSRWLockExclusive`.

Corollary: Windows SRWLocks are NOT automatically released when the owning thread dies (unlike
some kernel mutexes). This is the same class of mechanism as classic `EnterCriticalSection`
deadlocks from `TerminateThread`-style thread kills, but with a modern-UE code path.

## What is now open

Same as the S190-primary "what is now open" section — redirected to S191 live probe. Steps 1-3
of the probe are pre-registered above; the discriminator table maps each observation to a
specific next-action.

**Purely offline follow-ups still available before S191 fires**, in decreasing yield:

1. **Recursive-descent CFG on cleanup callee `0x402F470`** (AppPreExit-shaped, 1114 B) — enumerate
   its WaitForSingleObject / EnterCriticalSection / SleepEx / thread-join sites. If it hits any
   blocking primitive on the graceful-shutdown path, that reinforces mechanism (a-alt).
2. **Decrypt-and-transcribe DARK-page cleanup callee `0x4017380`** — requires firing the
   graceful-shutdown path in a live session and re-dumping the process (side-effect capture of
   the S118 driving-decrypts-pages technique).
3. **Enumerate `_Init_thread_header` callers that lie on `-CompanionWatch`'s companion-kill
   reachable code path** — if a specific subsystem's static-init is what the killed companion
   was running, S191 step 3 can pre-narrow which subsystem's SRW state to inspect.

None of these are strict prerequisites for S191; they narrow the discriminator table but the
live probe closes the question in any case.

## Files preserved

- `docs/s190-halt-gate-hunt-settled.md` — this doc
- Workflow transcript: `.claude/.../subagents/workflows/wf_7528337c-87e/journal.jsonl`
- Source: `dumps/merged14.dump.exe`

## What S190 did NOT do

- Not fire the live probe (see [docs/next-session-prompt-s191.md](next-session-prompt-s191.md))
- Not decrypt DARK-page cleanup callee `0x4017380` (needs live shutdown-path fire)
- Not enumerate every `_Init_thread_header` caller by subsystem (Lane D found the 3 depth-1
  wrappers reachable from Tick, but the full 9,448-caller subsystem attribution would take
  additional offline time)
- Not decode the obfuscated IAT slot at the final indirect call in the `0xF9C930` chain (Lane C
  rank #1 mechanism-b-alt candidate; needs `usmapdump deobfimports` against a live process)
