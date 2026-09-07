# S179 — F10 mechanism SETTLED via KFOVERBOSE re-fly: game-thread ProcessInternal starvation

**Live-measured 2026-09-06 with `tutorial_launch_fo_verbose.dll` (S179 KFOVERBOSE
instrumentation, commit `4824c77`).** One flight, one process, one marker file. The finding
demolishes every prior hypothesis (H1/H2/H3/H4 from `docs/next-session-prompt-s179.md`, plus the
S179 CFG-walk workflow's Ranks 1/2/3) and reframes what the F10 3-line marker actually meant.

## Headline

★★★★★ **[M] for TODAY's flight** — fo-verbose in the S177 F9 antecedent state runs to completion,
installs its PI hook cleanly, then times out at `[4] TIMEOUT no game-thread PI in 8s (hitsGT=0)`
and cleanly restores the vtable. **[I, strong] transfer to F10 specifically** — no direct F10
marker exists showing `[4] TIMEOUT` (F10's live marker was overwritten by subsequent launches).
The transfer rests on three identity assumptions: (1) [M] source semantics of fo ≡ fo-verbose
modulo `#if KFOVERBOSE` Marker calls, (2) [M with caveat] `.text` byte-identity of F10 fo and
today fo (Sep 3 deployed fo and Sep 5 build fo both `RAW=31d4e4dc0b9c9b5e` — but see the S176
hash reconciliation caveat below), (3) [I, strong] F10's F9 antecedent state ≡ today's recreated
state. ⇒ **The F10 mystery is not "why did fo bail" — it is "why did the game thread stop
dispatching ProcessInternal reflection calls after the S177 F9 antecedent sequence".** That
question is the same regardless of whether the [4] TIMEOUT is what stock fo hit on F10 or is
merely the mechanism fo mechanically CAN hit under recreated F9 state.

## The 3-line F10 marker was a snapshot artifact, not a bail state

`fk24-stage.ps1`'s `Stage-Inject` at line 918 sleeps ONLY 2 seconds after injecting a shim, then
copies the marker to `docs/fk24-stage-<label>-<n>-<tag>.txt`. Our fo-verbose marker at t=2s shows
**6 lines** (up through `[0v] entering Resolve polling loop`). Stock fo (without KFOVERBOSE)
emits NO lines between `[0] command` and `[2] worldCtx=...` — a silent 2.9-second interval
covering LoadCommand tail, GetModuleHandleA, AddVectoredExceptionHandler, WaitTid, and one
Resolve() iteration. At t=2s, stock fo would still be inside Resolve — which is EXACTLY the state
F10's marker (`[0] started + [0] command`) captured.

**⇒ The F10 marker was never evidence of a hang. It was consistent with a WORKING fo, snapshotted
before `[2] worldCtx=` had time to fire.** All the S179 mechanism-hunting rested on the false
premise that the 3-line marker was a final state.

## What was flown

**Recipe** (single continuous session, ~4 minutes elapsed):
1. `configs\launch-redirect.ps1 -NoHook -CompanionWatch` — game up, watcher armed
2. Wait for menu-ready: `TryUIReady SUCCESS` + `core-game/matches` fetch + 90s uptime → 94s
3. `py scratchpad\s176\hwbp_movei.py` — DR install on 138 threads:
   - DR0 = runtime.dll HIGH kill @ `0x7FFCA1C0F7F0`
   - DR1 = ntdll!NtTerminateProcess @ `0x7FFCA10CDB80`
4. Wait for companion kill: runtime.dll spawns at t+146.26s, watcher kills at t+146.30s, child exits t+146.40s. **Game stays alive.**
5. `fk24-stage.ps1 -Fo tools\sigbypass-mod\build\tutorial_launch_fo_verbose.dll -Probe tools\sigbypass-mod\build\tutorial_launch_fo.dll -SkipProbe -Label s179-f10-verbose`

**Stager result**: exit code 4 at 180s LoadMap timeout — reproducing F10 exactly at the STAGER
level. Then read the LIVE marker while game was still alive (no next-shim truncation).

## The measured marker (17 lines)

Preserved at [docs/s179-f10-verbose-fullmarker.txt](docs/s179-f10-verbose-fullmarker.txt):

```
[0] tutorial_launch (force-open LVL_Tutorial via ExecuteConsoleCommand) started
[0] command (default fallback): 'open LVL_Tutorial?game=/Game/Loki/Core/GameModes/BP_LokiGameMode_Tutorial.BP_LokiGameMode_Tutorial_C'
[0v] module OK; installing AVEH
[0v] AVEH installed handle=0x0 modBase=0x7FF721420000; entering WaitTid budget=120s     ← ⚠ VEH REGISTRATION FAILED
[0v] WaitTid ok gameTid=36516; skipping RM_X branches for kRunMode=0 (0=RM_FORCEOPEN)
[0v] entering Resolve polling loop budget=120s
[0v] Resolve iter=0 worldCtx=0x1AE3AF57A20 kslCDO=0x1AE3F18D050 eccThunk=0x7FF724D7D790 eccChild=0x1AE7FF2B400 offCmd=0x8 offWCO=0x0 offSP=0x18
[0v] Resolve loop exited after iter=1 totalMs=2922 (worldCtx=0x1AE3AF57A20 eccThunk=0x7FF724D7D790 eccChild=0x1AE7FF2B400 offCmd=0x8)
[2] worldCtx=0x1AE3AF57A20 kslCDO=0x1AE3F18D050 eccThunk=0x7FF724D7D790(rva 0x395D790) child=0x1AE7FF2B400 offWCO=0x0 offCmd=0x8 offSP=0x18 gameTid=36516 cmd='open LVL_Tutorial?game=...'
[3] hook built; issuing ExecuteConsoleCommand('open LVL_Tutorial') on the game thread...
[VT] custom-login INSTALL: 5 vtables slot285, stockLogin=0x7FF724C00C50 tramp=0x1AF18752820
[PIM] PI hook mutex acquired (clean)
[PIM] PI hook mutex released
[4] TIMEOUT no game-thread PI in 8s (hitsGT=0)          ← ★★★ THE ACTUAL F10 MECHANISM
[VT] custom-login restore: 5 vtables slot285, stockLogin=0x7FF724C00C50 tramp=0x1AF18752820
[5] done (vtable restored)
[6] NearAlloc region freed at 00007FF721410000 (vf=1)
```

## Three concrete findings from the 17 lines

### 1. Game thread stops dispatching ProcessInternal [M]

`[4] TIMEOUT no game-thread PI in 8s (hitsGT=0)` — Fo installed its PI hook on `ProcessInternal`
via BuildHook + InstallHook, took the `Local\SuperviveMissionsPIHook` mutex CLEAN (no other
PI-hooker contending), waited 8 seconds for a single game-thread dispatch to fire, and **got
zero**. In a healthy menu-parked game, ProcessInternal is dispatched hundreds of times per second
for reflection calls (widgets, delegates, ticks). Zero hits in 8 seconds is a definitive stall of
the reflection dispatch loop on the game thread.

This is **the reason LoadMap never fires**: fo's `ExecuteConsoleCommand('open LVL_Tutorial')`
needs a game-thread PI dispatch to run its hook, which then invokes the console command. No PI
dispatch → no console command → no LoadMap → no `Load map complete /Game/Loki/Maps/Tutorial/
LVL_Tutorial` in Loki.log → stager Wait-For times out at 180s. F10 is EXPLAINED end-to-end.

### 2. AddVectoredExceptionHandler returned NULL — reproduces R-S176-k for the 4th time [M]

`AVEH installed handle=0x0`. This is NOT a novel signal — it reproduces the S176 finding
[**R-S176-k**](docs/s175-s176-synthesis.md) already banked as an [M] observation across three
prior flights (**S175-f1**, **S176-f1**, **S176-f2**, all 2026-09-03). Cumulative n≥4 with
consistent signal.

R-S176-k as banked: *"`AddVectoredExceptionHandler` returns NULL when called from a manually-
mapped DLL body (verified via missing marker line)."* The mechanism is a **base property of the
shim's manual-map body**, INDEPENDENT of DR install, companion kill, or any F9 antecedent.
Whether it's (a) ProcessInstrumentationCallback denying VEH registration for manually-mapped
bodies, or (b) Windows treating manually-mapped RWX regions specially, remains UNDETERMINED —
same status as S176-f1, unchanged by S179.

⇒ **This observation is NOT diagnostic of F9 state divergence.** S179 initially mis-read it as
a "novel corruption signal" — a false claim caught by adversarial verification before commit.
See §S179-d for the lesson.

### 3. Fo is architecturally sound [M]

The last three lines show fo's clean shutdown path: `[4] TIMEOUT` → uninstall trampolines
(`[VT] custom-login restore`) → `[5] done (vtable restored)` → `[6] NearAlloc region freed`. No
crash, no leaked state, no hung threads. The Worker function returned normally. **Fo does not
need to be "fixed" for F10** — fo's job is to install a PI hook and wait for a dispatch, and it
did that correctly. What broke was the game thread it was hooked into.

## Every prior hypothesis and CFG-walk candidate — REFUTED

| Hypothesis | Predicted phenotype | Measured phenotype | Verdict |
|---|---|---|---|
| **H1** (fo needs live companion for LoadMap) | No `[2] worldCtx=`, no `[3] hook built` | Both fired | **REFUTED** |
| **H2** (protector soft-fail from kill event) | Silent Resolve failure OR downstream refuse | Resolve first-iter success; PI hook installed | **REFUTED** |
| **H3** (FK-31 fired and suppressed) | Any crashpad artifact / stack unwind | Fo Worker returned normally, no exceptions | **REFUTED** |
| **H4** (fo silently no-op'd on precondition failure) | Bail before `[2]` | `[2]` fired at t≈3s | **REFUTED** |
| **CFG Rank 1** (Resolve hangs on runtime.dll page) | Loop times out at 120s with `[2] FAIL resolve` | Loop exits after iter=1 in 2922ms | **REFUTED** |
| **CFG Rank 2** (WaitTid unbounded internal wait) | Fo stuck in WaitTid; no `WaitTid ok` | `WaitTid ok gameTid=36516` fired | **REFUTED** |
| **CFG Rank 3** (CrashVEH re-fault loop from stale DR) | Any `[NULL] (via VEH)` output OR infinite marker growth | AVEH failed to install (handle=0x0) so CrashVEH is unreachable; no `[NULL]` output | **REFUTED** |

## S179 reusable rules banked

### S179-a: Stager marker snapshot timing can create false bail signals [M]

`fk24-stage.ps1`'s Stage-Inject at [line 918](configs/fk24-stage.ps1:918) sleeps only 2 seconds
between injection and marker copy. A shim whose Worker takes >2 seconds to reach its next Marker
emit will have its marker snapshot captured MID-EXECUTION. Reading the snapshot as a bail state is
the trap. **Any "the marker stopped at line N" claim must first verify that line N is emitted by
t=2s post-injection in a WORKING run.**

Applied here: F10's 3-line marker read as a bail state. My H4 explanation, the S179 CFG-walk
workflow's Ranks 1/2/3, and the S179 top-level workflow all rested on that reading. All were
wrong. The fix is one KFOVERBOSE flag revealing that fo actually reaches `[6] done` in ~15
seconds — F10 just never saw those later emits because the STAGER copied at t=2s and F10 had no
subsequent copy after fo completed.

### S179-b: `hitsGT` in fo's marker is the true fo receipt, not `[2] worldCtx=` [M]

`[2] worldCtx=` proves Resolve succeeded — one internal step, not the whole shim. Fo's actual
success gate is whether the PI hook DISPATCHES on the game thread. `[4] TIMEOUT no game-thread
PI in 8s (hitsGT=0)` is a hard fail signal that means fo's ExecuteConsoleCommand never ran, even
though every earlier step succeeded. **Any future fo diagnostic must check hitsGT, not `[2]`.**

### S179-c: Before claiming a signal is a "first-time observation", grep docs/ for the API name and the value [M]

S179's initial write-up claimed `AVEH installed handle=0x0` was a "novel corruption signal
[I,strong]". This was materially FALSE. The same signal had been banked as **R-S176-k** across
four docs (`docs/s176-flight1-nearalloc-fix-refuted.md:15-21` and `:95-99`,
`docs/s175-s176-synthesis.md:35` and `:158-163`) three days earlier — 3 prior flights
(S175-f1, S176-f1, S176-f2) had measured the same NULL return with the same mechanism
attribution. S179 missed all four citations.

**The remedy is one grep before writing "novel"**: `grep -r "AVEH.*NULL\|handle=0x0" docs/` would
have surfaced R-S176-k in seconds. This banks as instrument-artifact register instance #137
(the pattern is: promoting a re-observed signal to "novel" because the write-up author didn't
grep before publishing).

Two known VEH-suppression mechanisms exist on this build, both intrinsic protector-plus-Windows
behaviors present since S170/S175/S176 and requiring no F9 antecedent: (a) AVEH returns NULL for
manually-mapped shim bodies (**R-S176-k**, [M] observation, mechanism unresolved); (b) VEH
callbacks are never invoked on FK-31 kills even when AVEH returned non-null (**S170**, [M]).

### S179-d: Adversarial verification before commit is what caught the workflow's hallucinations [M]

The S179 offline analysis workflow (`wf_7f899fdc-61d`, 7 agents, 2.27M tokens) synthesized three
ranked bail candidates without reading the actual source of CrashVEH, WaitTid, or Resolve. All
three candidates were mechanistically impossible given the source. Direct source reads refuted
them in minutes. Then adding instrumentation and re-flying refuted ALL H1/H2/H3/H4 candidates in
one measurement. **Workflow subagents speculating about function behavior without reading the
function is a specific failure mode. The remedy is to read the source before believing the
synthesis.** [Applied and banked in `docs/method-rules.md` §1 pattern-catalog.]

## What is now open

1. **What breaks game-thread ProcessInternal dispatch after F9?** The S177 F9 recipe was designed
   to defeat FK-32 by killing the runtime.dll companion. It works — the game stays alive. But
   this measurement shows it also stops the game thread from dispatching reflection calls. That
   makes F9 not a safe defeat for anything that needs subsequent reflection work (staging, force-
   open, shim callbacks). Understanding the mechanism is the next question.

2. ~~What broke AddVectoredExceptionHandler?~~ ★ REMOVED after adversarial review: this question
   is already banked as answered-mechanism-unknown-but-repeatable in **R-S176-k**. It requires
   no F9 antecedent and reproduces on every manual-map inject of this shim. The open S176
   sub-question — *"whether ProcessInstrumentationCallback denies VEH registration for manually-
   mapped bodies, or whether Windows treats manually-mapped RWX regions specially"* — is
   unchanged by S179.

3. **Does the ProcessInternal starvation reverse itself?** Fo waited 8 seconds. What if the halt
   is transient? Re-fly with a larger `KPIWATCHMS` (fo's PI wait budget) — 60s, 300s. If PI
   dispatch resumes eventually, the finding is "reflection stalls for N seconds after F9". If it
   never resumes, it's a permanent halt.

4. **Practical: can any variant of fo work post-F9?** Options: (a) use KFUNCSWAP instead of the
   PI-hook route (heap `UFunction.Func` swap, no `.text` write, doesn't need PI dispatch to fire
   — S112's shipping default for `play`); (b) use S55 direct-thunk primitive to call
   `ExecuteConsoleCommand` explicitly rather than waiting for a natural dispatch; (c) find and
   fix the ProcessInternal dispatch halt itself.

## Caveats surviving adversarial verification

- **State-recreation identity between F10 and today's flight is APPROXIMATE, not measured.**
  Today's DR-install (`hwbp_movei.py`) reproduced the S177 F9 recipe but no measurement
  established that the resulting process state is byte-equivalent to F10's. The
  `AVEH installed handle=0x0` return is NOT evidence of state equivalence (it's a shim-body
  intrinsic per R-S176-k) — and neither does it evidence state divergence. This is the load-
  bearing gap in the `[M]→F10` transfer.

- **CLAUDE.md S176 fo hash reconciliation is UN-AUDITED.** CLAUDE.md's S176 line records the
  deployed fo hash moving `CFB1B0B5EF37E910 → 51E56E00341A218A`. Direct measurement today shows
  Sep 3 deployed fo and Sep 5 build fo both have `.text` RAW `31d4e4dc0b9c9b5e` — neither S176
  hash matches. This does NOT refute the Sep 3-vs-Sep 5 byte-identity used in the transfer
  argument, but the internal inconsistency in CLAUDE.md's own S176 record needs an audit.
  Either the S176 line is stale, or there was an undocumented intermediate worktree state
  transition between S176 and Sep 3.

- **No direct F10 marker exists showing lines past `[0] command`.** F10's live marker file was
  overwritten by subsequent `tutorial_launch_*.dll` injections (Worker line 23757 CREATE_ALWAYS
  truncates on every fo/sp/probe inject). The 3-line snapshot at
  [docs/fk24-stage-s177-flight10-2-fo.txt](docs/fk24-stage-s177-flight10-2-fo.txt) is the ONLY
  F10 fo evidence, and it matches every other `fk24-stage-*-2-fo.txt` file byte-for-byte at the
  same 3-line shape (verified: s177-i3-2-fo, wallp-s158-2-fo, testact1-2-fo, wp2r1-1-fo all
  identical). ⇒ the 3-line snapshot proves fo was injected and got past `[0] command` on F10.
  It does NOT prove fo reached `[4] TIMEOUT` on F10 specifically. The transfer to F10 rests on
  the identity assumptions above, not on direct F10 measurement.

## Files preserved

- `docs/s179-f10-verbose-fullmarker.txt` — the full 17-line diagnostic marker
- `docs/fk24-stage-s179-f10-verbose-1-gft.txt` — gft stage marker (stale content from prior session, not F10)
- `docs/fk24-stage-s179-f10-verbose-2-fo.txt` — fo 2s snapshot (6 lines, matches F10-shape when stripped of `[0v]`)
- `docs/companion-watch.20260906-132240.log` — surgical watcher log showing runtime.dll kill at t+146s (F9 defeat working)

## The `fo-verbose` variant is committed

Instrumentation code is behind `#if KFOVERBOSE` guards; the default `fo` build's `.text` sha256
is byte-identical to pre-edit (`31d4e4dc0b9c9b5e`). Commit `4824c77`. Rebuild fo-verbose with
`build.ps1 -Name tutorial_launch -Variant fo-verbose` any time this diagnostic path is needed
again.
