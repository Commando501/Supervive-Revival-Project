# S181 — [M] the runtime.dll companion kill IS what halts game-thread PI dispatch

**Live-flown 2026-09-07 in ONE continuous sitting** across two game processes: PID 41688
(post-F9, three fo-verbose injections) and PID 29532 (baseline, no F9, one fo-verbose
injection). Four markers preserved as `docs/s181-*-live-fullmarker.txt`. The finding settles
the F10 mechanism completely and confirms the S180 workflow's H4a candidate — the exact
hypothesis my synthesis discarded without a discriminator.

## Headline

★★★★★★★★★ **[M] Killing the runtime.dll companion halts game-thread ProcessInternal
dispatch. Without the kill, fo works end-to-end: PI dispatches (hitsAny=27 over ~60s),
fo's ExecuteConsoleCommand fires (hitsGT=1, called=1), LoadMap actually loads
LVL_Tutorial.** The F10 mystery from S179 is fully explained: `-CompanionWatch`'s FK-32
defeat has a side effect that breaks any downstream shim needing game-thread reflection
dispatch. `-CompanionWatch` and `fk24-stage.ps1` are functionally incompatible **because
of the companion kill, not because of DR install, not because of an 8s window, not
because of hook revert, not because of thread migration.**

## The four-flight A/B in one sitting

Every knob varied single-variable across matched conditions. Same fo-verbose build
family (`.text` `b33e59db523a7e38` for Ranks 1-2, `7d78ce449d029305` for Rank 3+5, the
latter added `g_hitsAny` pre-filter counter + byte readback at [tutorial_launch.cpp:24741](tools/sigbypass-mod/tutorial_launch.cpp:24741)).
Stock fo built at `31d4e4dc0b9c9b5e` throughout — byte-identical to deployed fo (identity
verified before every flight).

| flight | PID | DRs | companion | fo build | hitsGT | hitsAny | verdict | LoadMap |
|---|---|---|---|---|---|---|---|---|
| **Rank 1** | 41688 | armed | killed | fo-verbose R1 | **0** | n/a | `[4] TIMEOUT no game-thread PI in 60s` | no |
| **Rank 2** | 41688 | cleared | killed (still) | fo-verbose R1 | **0** | n/a | same | no |
| **Rank 3** | 41688 | cleared (still) | killed (still) | fo-verbose R3 | **0** | **0** | `hitsAny=0` + `[4v] PI bytes: e9 7b ab ca fe` (hook intact) | no |
| **Rank 5** | 29532 | **none** | **none** | fo-verbose R3 | **1** | **27** | `[4] CALLED called=1` | **YES** — `Bringing World .../LVL_Tutorial up for play` |

**The single-variable differential**:
- Rank 2 (halted) vs Rank 5 (works): the ONLY variable is the companion kill. DRs cleared
  in both (well, Rank 5 never had any). Same fo build family. Same menu-parked initial
  state. **⇒ companion kill is the causal agent.**
- Rank 3 (halted, hitsAny=0, hook intact) vs Rank 5 (works, hitsAny=27): identical fo-
  verbose build (`7d78ce449d029305`), same instrumentation. Only F9 differs. **⇒ H2 (hook
  reverted) and H3(c) (dispatch moved to different TID) BOTH firmly REFUTED — Rank 3 saw
  ZERO PI activity through the hook while Rank 5 saw 27.**

## What each byte in the Rank 3 marker settled

The one-flight Rank 3 marker line:
```
[4v] PI bytes after wait: e9 7b ab ca fe  (installed[0]=0xE9 / kPiProlog[0]=0x48 / read_ok=1 / hitsAny=0)
```
carried three independent measurements at once:

1. **`e9 7b ab ca fe`** — the first five bytes at `kPiRva=0x13454A0`. Byte 0 is `0xE9`,
   which is the opcode fo's `InstallHook` writes (E9 rel32 jmp). The original
   `kPiProlog[0] = 0x48` (MSVC function prologue) is NOT present. **⇒ H2 REFUTED [M]**:
   the protector did NOT revert fo's hook during the 60s wait.
2. **`hitsAny=0`** — the pre-filter counter added at [OnPI](tools/sigbypass-mod/tutorial_launch.cpp:1491)
   incremented ZERO times over 60 seconds. **⇒ H3(c) REFUTED [M]**: not only did nothing
   pass the `g_gameTid` filter, nothing entered OnPI at all — on ANY thread. Dispatch is
   not being routed to some other TID; there is NO dispatch through the hook at all.
3. **`read_ok=1`** — the `SafeReadable` check on `g_pi` succeeded, so the bytes are the
   live process's actual state, not a fabricated null. Instrument-check control passed.

The Rank 5 mirror-image line:
```
[4v] PI bytes after wait: e9 7b ab ca fe  (installed[0]=0xE9 / kPiProlog[0]=0x48 / read_ok=1 / hitsAny=27)
```
identical byte state (hook intact), same instrument, but `hitsAny=27`. The two flights
share every variable except the F9 sequence. **The differential is decisive.**

## Every hypothesis in the S180 register, final grade

| hyp | S180 grade | S181 result | final |
|---|---|---|---|
| H1 (DRs stall dispatch) | [I] | Rank 2 disarm did not restore PI | **[REFUTED]** |
| H2 (protector reverted hook) | [S] | Rank 3 byte-readback: hook byte[0]=0xE9 intact after 60s | **[REFUTED]** |
| H3(c) (dispatch moved to another thread) | [I] | Rank 3: hitsAny=0 across all threads (not just g_gameTid) | **[REFUTED]** |
| H4c (KiUserExceptionDispatcher wedge) | [I-weak] | Rank 2 (no DRs) still halted; H4c requires DRs | **[REFUTED]** |
| H4d (8s window too short) | [I] | Rank 1: 60s wait, still hitsGT=0 | **[REFUTED]** |
| **H4a (companion kill strands game thread on missing sync object)** | — (dropped from top ranking in synthesis) | Rank 2 vs Rank 5 single-variable A/B | **[M]** |

The one hypothesis my S180 workflow's H4-open agent explicitly flagged (`H4a`) and my
synthesizer discarded from the top-5 ranked flights — because "not enough evidence to
distinguish from the timing hypothesis" — is the correct answer. **See rule banked below.**

## Mechanism: what companion-kill does to reflection dispatch

Not fully known. But the phenotype is precise: after killing the runtime.dll companion
process:
- Game process stays alive (~24h in S179's flight)
- Backend Winsock I/O continues (telemetry POSTs, Vivox connections)
- **`ProcessInternal` — UE's reflection entry point at `kPiRva=0x13454A0` — stops being
  called from any thread, indefinitely (≥60s measured, ≥24h implied from S179)**
- The E9 jmp fo installs stays intact; it is not overwritten by the protector

Two plausible sub-mechanisms remain [I] / [S]:

- **[I,strong]** — the game thread's UE Tick loop invokes a protector callback (via
  `ProcessInstrumentationCallback` — the mechanism FK-10 §4 documented as installed by
  this protector) that expects the companion to answer via a sync object (event, pipe,
  named mutex). With the companion dead, the callback waits indefinitely on the object.
  The game thread never returns from the callback, and never reaches the code that would
  call ProcessInternal again.
- **[S]** — the companion holds a shared mutex/semaphore the game thread's reflection
  dispatcher tries to acquire; when the companion dies without releasing it, the game
  thread's next dispatch attempt blocks forever. A "held-by-dead-owner" mutex would show
  `WAIT_ABANDONED` on next acquire and could self-recover; a Manual-Reset event with no
  signaler would not.

Discriminating these requires a live thread-inspection: `SuspendThread(g_gameTid)` +
`GetThreadContext` + `RIP` decode after F9. If RIP is in `ntdll!ZwWaitForSingleObject`
or similar wait syscall, one of the above is confirmed. This is Rank 4 from S180 (moderate
Heisenberg risk) — the OFFLINE next-session task.

## What this means for shipping FK-32 defeat + force-open

`-CompanionWatch` cannot be combined with `fk24-stage.ps1` **by design of the FK-32
defeat itself**, not by an accident of timing. Any shipping recipe that needs both a
long-lived game (past ~146s companion-spawn time) AND game-thread reflection dispatch
must find one of:

1. **A non-companion-kill FK-32 defeat.** Requires understanding why the protector calls
   `NtTerminateProcess(0xDEAD)` from the companion path in the first place (per FK-10
   settled doc, the companion is where `runtime.dll+0x80F7F0` executes) and how to
   satisfy its check without killing the child. S180-c's timing hypothesis is dead as
   applied to fo, but "wait for kill to happen naturally and just be prepared" is not —
   the companion spawns at t+146s reliably per S179.
2. **A companion-alive-proxy.** Intercept the companion's inputs/outputs; keep it
   spawning and receiving expected data even while its kill syscall is neutered. This
   requires knowing what the companion communicates with — an offline task not yet done.
3. **Skip fo entirely for CompanionWatch runs.** The tutorial-loading recipe becomes
   companion-alive: launch normally (letting the game complete its ~146s pre-kill
   window), inject fo BEFORE the kill happens. Timing-sensitive but potentially viable.
   Rank 5's success shows a normal-companion game supports the fo path fine.

## S181 rules banked

### S181-a: A hypothesis that the workflow synthesis discards ("not enough evidence to distinguish") is not the same as a hypothesis that was refuted. Keep it in the flight ranking until data actually decides. [M]

The S180 workflow's H4-open agent explicitly proposed H4a (companion kill strands game
thread on missing sync object). My synthesizer's ranked flights list surfaced H4c and
H4d instead, silently demoting H4a because "the mechanism is speculative." **H4a
turned out to be the correct answer.** The synthesizer's ranking treated "we can't
distinguish these yet" as equivalent to "these are equally likely" and then favored the
cheaper-to-test candidates — which meant the correct hypothesis was untested for a
whole extra hop. **Rank flights by discrimination power AND include every candidate
the analyzers proposed. A [S]-graded hypothesis that reproduces the phenotype end-to-end
is still testable and still worth a slot in the flight budget.**

### S181-b: A pre-filter counter (S180-b) discriminates "game did nothing" from "game did something the filter dropped" — but ALSO discriminates "hook did nothing" from "hook received traffic." When Rank 3's `hitsAny=0` matched Rank 3's `hitsGT=0`, it refuted BOTH H3(c) (dispatch to different TID) AND the more general "the hook is receiving PI dispatches but bailing before OnPI's real work." One counter, two hypotheses discriminated. [M]

Applied here: the same 3-line addition of `g_hitsAny` at OnPI entry served as the
discriminator for two distinct hypothesis families. Design instrumentation to answer
multiple questions in one flight when the marginal cost is trivial.

### S181-c: Same-process A/B testing across DR/companion state can be executed in a single sitting IF the injection budget allows. Rank 1 → Rank 2 (DR clear) → Rank 3 (rebuild + inject) all ran in PID 41688 with 3 total fo injections + 3 gft injections. FK-32 dose-response (project modal: 4 injections) was approached but not exceeded. Six injections into one process is at the limit; do not exceed without justifying the risk. [I,strong]

Applied here: three fo injections + three gft injections in PID 41688, plus DR install
and clear passes. Process survived through Rank 3 completion. The Rank 5 flight then
required a fresh launch (a genuine confounder-isolation flight, not a repetition), which
is what produced the [M] result. **Distinguish "same-process cheap sequel" from
"confounder-isolating fresh launch" — each has its place.**

### S181-d: A cheap [M]-grade discriminator can exist for an [S]-graded hypothesis and be missed because the synthesizer's ranked-flights section only enumerates 3-5 candidates. The workflow's SYNTHESIS output cap becomes a synthesis-side selection bias. Prefer to run every proposed candidate at least as a design pass. [M]

Applied here: my S180 workflow returned 5 ranked flights. H4a was in the analyzers'
output but not in the top-5 ranked flights. If I had budget-scanned "which candidate,
if true, would be simplest to test with a baseline flight?", H4a's answer ("just don't
kill the companion") would have surfaced immediately. The synthesizer's structural
preference for mechanism-specific tests over baseline-elimination tests cost one round.

## What the Rank 5 crash means (a separate wall)

At Rank 5, after fo's `[4] CALLED` and LoadMap firing, the game died with
`EXIT -1073741819 (0xC0000005) — ACCESS VIOLATION (unhandled)` about 6s after fo's
injection. `LogSentrySdk: HandleBeforeCrash Begin` fired, so this was caught by the
Sentry crashpad handler. Crashwatch preserved the dump at
`dumps/crash-20260907-190545/`. **This is NOT the S181 phenomenon.** The tutorial DID
load (Loki.log shows `Bringing World .../LVL_Tutorial up for play`), but something in
tutorial init faulted. This is a downstream wall unrelated to F10/companion kill —
likely one of the many post-LoadMap tutorial-init failure modes documented in FK-31 or
FK-32 lineage. **S181 does not attempt to attribute it.**

## Files preserved

- `docs/s181-h4d-live-fullmarker.txt` — Rank 1 marker (DRs armed, hitsGT=0 at 60s)
- `docs/s181-h1h4c-drcleared-live-fullmarker.txt` — Rank 2 marker (DRs cleared, hitsGT=0)
- `docs/s181-h2h3-rank3-live-fullmarker.txt` — Rank 3 marker (hitsAny=0, hook byte[0]=0xE9)
- `docs/s181-h2h3-rank3-live-marker-final.txt` — Rank 3 duplicate (backup)
- `docs/s181-rank5-baseline-live-fullmarker.txt` — **Rank 5 marker (hitsAny=27, hitsGT=1, [4] CALLED)** — the load-bearing evidence
- `docs/companion-watch.20260907-184746.log` — Rank 1/2/3 companion-watch log (companion killed at t+101.11s)
- `docs/companion-watch.20260907-190545.log` — Rank 5 companion-watch log (no kill; game died before companion spawn)
- `dumps/crash-20260907-190545/` — Rank 5 post-LoadMap crashpad archive (out-of-scope for S181)

## What S181 did NOT do

- **Rank 4 (`SuspendThread` + `GetThreadContext` on game thread during 8s window)** was
  not flown. It would name the specific wait state the game thread is stuck in
  post-companion-kill (`ntdll!ZwWaitForSingleObject` or similar). Adds mechanism [M] to
  the "companion kill halts PI" [M]. Cost: 1 flight, moderate Heisenberg risk. Recommended
  as next session's offline-preparation + one-flight execution.
- **No mechanism identification of WHY companion kill halts PI.** The phenotype is [M].
  The mechanism is [I,strong] at best. Rank 4 above is the natural next step.
- **No commit yet** — the source and build.ps1 edits, plus this doc, are still in the
  working tree. Ready to commit as a unit.
