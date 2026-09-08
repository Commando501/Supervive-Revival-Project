# S183 (Rank 6) — H4a-refined CONFIRMED [M]: game-exe RVA `+0x1225fd6` is the ONE PI-firing site

**Live-flown 2026-09-07** in a fresh game process (PID 5968), NO F9 sequence, fo-verbose R6
injected via `inject.exe mmap` (bypassing fk24's auto-sp chain so the caller-ring dump
survives). Result marker preserved as
[docs/s182-rank6-baseline-caller-ring-live-fullmarker.txt](docs/s182-rank6-baseline-caller-ring-live-fullmarker.txt).

## Headline

★★★★★★★★★★★★ **[M] Every single one of the 29 healthy-baseline ProcessInternal
dispatches originates from ONE identical caller: `SUPERVIVE-Win64-Shipping.exe + 0x1225fd6`
(raw `0x7ff6d83e5fd6`).** Zero callers in `runtime.dll` (protector). Zero callers in heap-
allocated thunk regions. **This settles the S182 open question**: **H4a-refined** (game's
own code calls PI, and companion kill stops that code path) is the mechanism. **H4b**
(external source — companion / APC / PIC — fires PI into the game) is [REFUTED] [M].

## The measurement

Same recipe as S181's Rank 5 baseline (fresh game, no F9), but with the R6 fo-verbose
build that adds a caller-RIP capture in the InstallHook stub. Injected with `inject.exe
mmap` directly (skipping fk24-stage.ps1's gft→fo→sp chain) so that no follow-up `sp`
injection would truncate fo's marker.

```
[0v] WaitTid ok gameTid=41552
[2] worldCtx=0x1D1071F7A20  eccThunk=... gameTid=41552
[3] hook built; issuing ExecuteConsoleCommand('open LVL_Tutorial') on the game thread...
[VT] custom-login INSTALL: 5 vtables slot285
[PIM] PI hook mutex acquired (clean)
[4v] PI bytes after wait: e9 7b ab ca fe  (installed[0]=0xE9 / hitsAny=29)
[4c] PI callers ring: total_hits=29 sampled=29 (unique callers below)
    [0] count=29  SUPERVIVE.exe + 0x1225fd6  (raw 0x7ff6d83e5fd6)
[4] CALLED (called=1 hitsGT=1) — de-override held; sampling tutorial state across travel...
[LOGIN1] gm=BP_LokiGameMode_Tutorial_C PCClass=BP_LokiPlayerController_Dev_C
[5] done (vtable restored)
```

**All 29 hits at identical RVA `+0x1225fd6`, one bucket in the caller-ring.**

## Three independent facts settled by this one flight

### 1. H4a-refined [M]: every PI dispatch in baseline comes from the game exe

The caller-ring's dedup logic collapsed 29 sampled hits into ONE bucket. If PI dispatches
came from multiple call sites (game tick + widget callback + delegate broadcast + …),
we'd see multiple buckets with varied counts. We see ONE. The dispatcher is a single
UE runtime function in the game exe at RVA `+0x1225fd6`.

### 2. H4b [REFUTED] [M]: no callers in the protector

FK-10's runtime.dll range is `0x7FFCA1400000..0x7FFCA5466000`. If the companion or a
`ProcessInstrumentationCallback` were firing PI into the game process, at least SOME
of the 29 hits would have RIPs in that range. The count is exactly 0. Whatever the
companion does for the protector, it does NOT dispatch UE reflection into the game.

### 3. The one site is called from MULTIPLE threads [M]

`hitsGT=1` while `hitsAny=29` means 28 of the 29 hits came from non-game-thread
callers — but every single one is at `+0x1225fd6`. So this specific game-exe function
is called by many threads, then serially reaches PI dispatch. Consistent with a
UE async task graph node or a delegate broadcast that fires per-tick on many workers.

## The single RVA now names the successor question

**`SUPERVIVE.exe+0x1225fd6`** — this is the ONE piece of game code whose behavior differs
between "companion alive" (fires ProcessInternal 29 times/60s across many threads) and
"companion dead" (fires 0 times / 60s). It has one of two shapes:

- **Shape A**: The function itself does not run when companion is dead. Something
  UPSTREAM of it (whatever schedules it — a tick delegate, a task graph node, a
  timer) reads companion liveness and cancels the work.
- **Shape B**: The function DOES run, but has an early-out that reads companion state
  and returns before reaching the `ProcessInternal` call.

Both are consistent with S181+S182+S183 findings. Discriminating them requires a
per-thread state census that catches WHERE those 28 non-game-thread callers were during
S181's post-kill window — but at S182 we already know they were all in canonical Win32
waits or in normal protector code. So the WORKER THREADS that used to call `+0x1225fd6`
either:
- (Shape A) never picked up the work item (task graph is empty of this node), or
- (Shape B) picked it up but its scheduler check said "don't run"

The next investigation is offline disassembly of `SUPERVIVE.exe+0x1225fd6` from a
lit dump (`merged14`) to identify the function and its immediate parents in the call
tree, then look for a branch that reads a companion-liveness variable.

## Rules banked

### S183-a: A caller-RIP capture is 15 bytes of ASM in the InstallHook stub and gives you the CALLING SITE for each hook fire, not the stub's return address. Combined with a bounded ring and dedup, it discriminates H4a-refined (single game caller) from H4b (multiple protector callers) in ONE flight. [M]

Applied here: BuildHook's stub now inserts `mov rax, [rsp+0x48]; mov [g_piLastCaller], rax`
after `sub rsp, 0x28` and before `mov rax, OnPI`. That's 15 bytes. `[rsp+0x48]` is the
game's return address that was pushed by its `call ProcessInternal` — computed from the
stub's known layout (4 pushed regs + 0x28 shadow = 0x48). OnPI then samples `g_piLastCaller`
into a 128-slot ring before any C++ work perturbs the stack. Cross-thread races are
acceptable for qualitative "distribution of callers" — 29 samples all landing in one bucket
is decisive regardless of a lost sample or two.

### S183-b: When the fk24-stage.ps1 auto-chain (gft → fo → sp → probe) would truncate the marker of the DLL you actually want to observe, bypass with `inject.exe mmap <pid> <dll>` directly. It's the same manual-map primitive the stager uses, minus the state machine. Perfect for one-off diagnostic injections. [M]

Applied here: R6 attempt 1 used fk24-stage.ps1 and successfully injected fo-verbose,
but sp then injected 20s later and truncated fo's marker (fo's caller-ring dump was
overwritten). R6 attempt 2 used `inject.exe mmap` directly — same manual-mapper, no
sp inject, marker preserved. Cost: nothing.

### S183-c: A single-bucket caller-ring output is a definitively STRONG signal — much stronger than "N hits distributed across M buckets". When multi-threaded code all funnels through one dispatcher, dedup naturally collapses to one entry. When independent sources fire the hook, you get many entries. Interpret the number of BUCKETS, not just the total count. [M]

Applied here: 29 hits → 1 bucket meant "one dispatcher, multiple thread schedulers".
If it had been 29 hits → 15 buckets (varied ring positions), that would have been
"many independent callers, likely external". The dedup step is what makes the caller-
ring a discriminating instrument rather than a raw counter.

## Progression from S180 → S183 — five sessions, hypothesis narrowed to one RVA

| session | grade change |
|---|---|
| S180 (offline) | 5 hypotheses all `[I]` or `[S]`; no discriminator |
| S181 (live A/B) | H1, H2, H3(c), H4c, H4d all `[REFUTED]` [M]; H4a promoted `[S]→[M]` |
| S182 (Rank 4 live) | H4a-primary (thread wedge) `[REFUTED]` [M]; mechanism narrowed to gated-execution [I,strong] with two sub-variants |
| **S183 (Rank 6 live)** | **H4a-refined `[M]`, H4b `[REFUTED]` [M], mechanism named to `SUPERVIVE.exe+0x1225fd6`** |

The remaining question is offline: what is `+0x1225fd6` and what upstream state governs
whether it runs.

## What is now open

1. **Identify `SUPERVIVE.exe+0x1225fd6`**. Offline task, dump-scan against `merged14`. If
   the function has reflected xrefs, use `strxref.py`. If it's part of the UE task graph
   dispatcher, look for FTaskGraphInterface / FBaseGraphTask references.
2. **Find the gate — what state does the scheduler read to skip this work?**  Requires
   disassembly of the function's PARENT (whoever calls `+0x1225fd6`). The parent's check
   is what makes the difference between baseline and post-kill.
3. **Practical shipping**: given the mechanism is IN-PROCESS (not external companion RPC),
   a patch that overrides the parent's gate check could restore PI dispatch even under
   `-CompanionWatch`. That's a data poke or a bytecode edit — this project's safest
   modification classes.

## Files preserved

- `docs/s182-rank6-baseline-caller-ring-live-fullmarker.txt` — the [4c] caller-ring dump
- `docs/companion-watch.20260907-194111.log` — this flight's companion watcher log
  (companion NOT killed — this was a baseline no-F9 flight)
- Fo-verbose R6 build: `.text` `9fef00ea7eadede7` (rebuild with
  `build.ps1 -Name tutorial_launch -Variant fo-verbose`)

## What S183 did NOT do

- **No identification of the function at `+0x1225fd6`**. Offline follow-up.
- **No investigation of what state governs the halt**. Requires disassembly of the
  parent site.
- **No commit yet** — evidence + source edits + doc bundled for the next commit.
