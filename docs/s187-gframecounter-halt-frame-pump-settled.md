# S187 — GFrameCounter (RVA `0x9d49138`) FROZEN post-companion-kill; the gate is at or above `FEngineLoop::Tick` [M]

**Live-flown 2026-09-08** in a fresh game process (PID 16840), same-session A/B/C:
baseline → F9 (DR install + companion kill) → +30s durability check. Preserved as
`docs/s187-checkpoint*.log`.

## Headline

★★★★★★★★★★★★★★★★ **[M] `GFrameCounter` at RVA `0x9d49138` advances at 30 Hz baseline
and FREEZES completely post-companion-kill.** Same PID, single session, three
checkpoints (all-RPM, no injection, no shim overhead):

| checkpoint | conditions | C2 (GFrameCounter) | delta rate | interpretation |
|---|---|---|---|---|
| **A** | menu-parked, PRE-F9, uptime ~102s | 2806 → 2941 | **+15 / 500ms = 30 Hz** | FEngineLoop::Tick running normally |
| **B** | POST-companion-kill, uptime ~140s | 3319 (constant across 10 samples over 5s) | **0 Hz** | Frame pump has stopped |
| **C** | +30s after B, uptime ~170s | 3319 (still) | **0 Hz** | Halt is DURABLE, not transient |

⇒ **[M] `FEngineLoop::Tick` (or something above it) is halted post-companion-kill.** This
promotes S186's [I,strong] "gate is at UE's per-frame pump" to [M] with a specific
localization: **the outer game loop, not just UGameEngine::Tick**, has stopped executing.

## Identifying GFrameCounter offline (rank the candidates by delta)

Offline hunt found 6 candidate qwords in `.data` incremented via `inc qword ptr
[rip+X]` in `.text`:

| # | .data RVA | containing fn size | baseline live delta |
|---|---|---|---|
| C1 | 0xa075ea8 | 164 B | 0 |
| **C2** | **0x9d49138** | **293 B** | **+15 per 500ms = 30 Hz** ← **GFrameCounter** |
| C3 | 0x9f527a0 | 841 B | 0 |
| C4 | 0x9f52790 | 1543 B (largest fn) | 0 |
| C5 | 0x9f85208 | 86 B | 0 |
| C6 | 0x9faa5b0 | 1070 B | 0 (static at 3081) |

**C2 is definitively GFrameCounter**: (1) monotonic +15/500ms rate matches menu-parked
UE's ~30 Hz target frame rate exactly, (2) the game thread's measured `NtDelayExecution
= 29ms` (S182) implies a ~34 Hz frame period, and 30 Hz observed is consistent with
"one increment per frame" at menu-idle throttled rate. Note the incrementor is in a
293-byte function — smaller than expected for `FEngineLoop::Tick` (which is 2000+ bytes)
but consistent with a lightweight per-frame helper called BY the tick pump (the actual
counter increment often lives in a small inlined helper). What matters is the RATE:
30 Hz baseline → 0 Hz post-kill.

R-S186-d applied: the workflow initially ranked C4 highest by containing-fn size (1543 B,
"most likely GFrameCounter"). LIVE measurement refuted that ranking dispositively — one
delta test settled identification in 5 seconds. **Static size heuristics do not beat one
live sample.**

⚠ **`0x9d49138` is 0x20 BEFORE `kGGameTidRva=0x9D49158`** (documented in
`tutorial_launch.cpp:43` as the game-thread-ID field). GFrameCounter and GGameThreadId
are adjacent in `.data` — both UE's Core-tier globals, close together.

## Discriminator power

Three sessions have compounded the evidence for the halt location:

- **S181**: `hitsAny=0` for ProcessInternal post-kill (leaf instrument)
- **S185**: All halted UFunctions are tick/anim/input (halt-set fingerprint)
- **S186**: ProcessEvent is stock UE (gate is upstream)
- **S187**: **GFrameCounter frozen** — gate is at or above `FEngineLoop::Tick`

⇒ Combined narrowing: The gate cannot be at `UGameEngine::Tick` alone (S186-a candidate #1)
because GFrameCounter is incremented BY FEngineLoop::Tick before it calls UGameEngine::Tick.
If UGameEngine::Tick were gated but FEngineLoop::Tick still ran, GFrameCounter would still
advance. It doesn't. **⇒ [M] gate is UPSTREAM of the counter increment inside FEngineLoop::Tick,
OR at whatever calls FEngineLoop::Tick from the game thread's main function.**

## Reconciling with S182: game thread ticks at 29 ms Sleep, but no frame advances

S182 measured the game thread at `NtDelayExecution+0x14` with a 29 ms delay, waking
34 times/second. S187 now shows the frame counter is FROZEN. Two hypotheses that
reconcile:

- **[I,strong]** The game thread's main loop is:
  ```
  while (!bRequestExit) {
      // WAIT ON SYNCHRONIZATION OBJECT
      Sleep(29);  // NtDelayExecution
      // CHECK "should tick?" flag
      if (!bSafeToTick) continue;   // ← gate here, added by protector, checks companion
      FEngineLoop::Tick();          // <- includes GFrameCounter++
      Present();
  }
  ```
  Companion alive → bSafeToTick=true → Tick fires → counter advances.
  Companion dead → bSafeToTick=false → thread loops Sleep(29ms) forever, counter frozen.

- **[S]** The game thread's Sleep is inside `FEngineLoop::Tick` itself (a rate-limiter),
  and the companion-liveness check is at the very top of `FEngineLoop::Tick` — so the
  Sleep runs but the counter-increment doesn't.

Both hypotheses predict the SAME S187 observation. Discriminating them requires reading
the game thread's exact call stack via `SuspendThread` (already done in S182 —
`NtDelayExecution+0x14` with 4 game-code stack frames above it), and identifying WHICH
of those game-code frames is `FEngineLoop::Tick`.

S182's stack frame `SUPERVIVE-Win64-Shipping.exe+0x13d8f8e` (Sleep caller) and
`+0xff984c` and `+0x3efea8c` are the parents of that Sleep. Identifying WHICH is
FEngineLoop::Tick is a small offline task — grep for `"FEngineLoop::Tick"` or the log
literal `"Requesting Exit"` (which is emitted from FEngineLoop::Tick's exit path).

## Rules banked

### S187-a: One 5-second RPM sampler at 0.5s intervals identifies a per-frame counter in a set of candidates. Static-size heuristics (largest containing function = most likely counter) do not survive a live delta test. Prefer the live sample. [M]

Applied here: workflow initial candidate ranking put C4 (largest fn) at top; live sample
showed C2 is the active counter, C4 is 0. Cost of live discriminator: <1 minute.

### S187-b: The frame counter is a first-class instrument for identifying where in the UE tick chain a halt lives. A stopped GFrameCounter means FEngineLoop::Tick isn't executing to its counter-increment site; an advancing GFrameCounter with stopped BP dispatch (S181) means the gate is inside UGameEngine::Tick or below. [M]

Applied here: S187 pinpointed the gate location to "at or above FEngineLoop::Tick" in
one live A/B/C. This class of discriminator generalizes to any layer-identification
question in a tick chain: probe a well-defined counter at each layer.

### S187-c: When a durability check (delta over ~30s of continued waiting post-halt) shows 0 additional change on a counter that was advancing at 30 Hz baseline, the halt is DEFINITELY not a transient slowdown — 30s of continued halt at 30 Hz would predict +900 counts, observed 0. Small-time-window observations of "zero delta" may be stochastic; extended durability observations promote [I,strong] to [M]. [M]

Applied here: Checkpoint B showed 0 change over 5s (150 counts predicted). Checkpoint
C showed 0 change over another 30s (900 counts predicted). Cumulative 0/1050 predicted
counts is P << 1e-100 against any "slow but progressing" hypothesis.

## What is now open

1. **Identify FEngineLoop::Tick's RVA offline** — grep `.rdata` for a distinctive string
   used only inside FEngineLoop::Tick (e.g. `"FEngineLoop::Tick"`, `"GT StartFrame"`,
   `"BeginFrame"` cycle counter names).
2. **Identify the specific gate site** — once FEngineLoop::Tick is located, disassemble
   its first ~256 bytes and look for a `cmp byte [rip+X], 0; je EXIT` pattern targeting
   a `.data` byte. That byte's write chain is the companion-liveness source.
3. **Practical**: if the gate is a compiled `cmp byte [rip+X], 0` inside
   FEngineLoop::Tick, patching the byte via one-qword `.data` poke restores frame
   dispatch. Data poke = safest write class (S123 lineage).

## Files preserved

- `docs/s187-checkpointA-baseline.log` — 10 samples PRE-F9, GFrameCounter +15/500ms
- `docs/s187-checkpointB-post-companion-kill.log` — 10 samples POST-kill, all frozen
- `docs/s187-checkpointC-post-kill-plus-30s.log` — 3 samples after +30s, still frozen
- `docs/companion-watch.20260908-114534.log` — companion kill at t+126s
- `scratchpad/s187/frame_probe.py` — the RPM sampler (128 lines, no injection required)

## What S187 did NOT do

- No identification of FEngineLoop::Tick's specific RVA
- No identification of the exact companion-liveness gate site
- No commit yet
