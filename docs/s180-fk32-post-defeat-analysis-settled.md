# S180 — Offline analysis: why does game-thread ProcessInternal stop dispatching after S177 F9?

⚠⚠⚠ **PARTIALLY SUPERSEDED by S181 (`docs/s181-companion-kill-halts-reflection-settled.md`)** —
S180's H1/H2/H3/H4c/H4d are all now `[REFUTED]` [M] via live flights in one sitting; the answer
is **H4a (companion kill halts PI dispatch), [M]**. Read S181 first. What of S180 survives:
Flights 1 and 2 (offline reads of `hwbp_movei.py` and `OnPI`/`WaitTid`), the four rules banked
(S180-a..d) which are all still valid, and the framing that "the 17-line marker cannot
discriminate H1/H2/H3/H4c/H4d." What S180 got wrong: the ranked-flights list did NOT include
Rank 5 (baseline: no F9) at the top, which is exactly the flight that produced the [M]. See
S181-a rule for the lesson banked from this synthesis defect.


**Offline-only 2026-09-07.** Zero live flights this session. Two direct source reads
(Flights 1 and 2, per the S179 handoff ranking) plus one adversarially-verified analysis workflow
(`wf_03ae0525-e0a`, 4 analyzers + 4 skeptics + 1 synthesizer, all seeded with verbatim source
excerpts per S179-d). Every finding below is [M] for the offline evidence and [I]/[S] for what
it implies about live behavior.

## Headline

★★★★★ **[M] the S179 phenotype has FIVE candidate mechanisms, NONE stronger than `[I]` from
offline evidence, and the 17-line marker cannot discriminate any of them.** Every candidate
predicts the exact observed phenotype (`hitsGT=0` for 8s, game alive 24h+). Any single-flight
discriminator requires added instrumentation, and one candidate — **H4d (8s window too short)** —
is a strictly Occam-simpler timing hypothesis that no prior session considered and that costs
literally one integer change (`8000` → `60000`) to test. It should be the S181 first flight.

## What was flown

Nothing live. Two offline flights per the S179 handoff:

**Flight 1** — Read [scratchpad/s176/hwbp_movei.py](scratchpad/s176/hwbp_movei.py) end to end
looking for DR cleanup semantics.

**Flight 2** — Read [tools/sigbypass-mod/tutorial_launch.cpp](tools/sigbypass-mod/tutorial_launch.cpp)
for `OnPI`, `WaitTid`, `InstallHook`, `kGGameTidRva`, and the RM_FORCEOPEN Worker path.

## Flight 1: hwbp_movei.py DR-cleanup behavior [M]

[scratchpad/s176/hwbp_movei.py:188-222](scratchpad/s176/hwbp_movei.py:188) — the `install_hwbp`
function. Three invocation modes:
- default: install `DR0=addr0, DR1=addr1, DR7=0x00000005` (L0|L1 execute-BP masks) on every
  thread, exit.
- `--watch <secs>`: install once, then poll every 2s for new threads (via
  `CreateToolhelp32Snapshot`), install the SAME DRs on any new ones. Loop exits at end of watch
  period.
- `--clear`: run install with `addr0=0, addr1=0` (writes zeros; DR7 dropped to 0), effectively
  disarming.

**[M] Neither default nor `--watch` clears DRs on exit.** The only path that clears is the
explicit `--clear` invocation. After S177 F9's step 3 (`py scratchpad\s176\hwbp_movei.py`), DR0
(runtime.dll HIGH kill primitive at `0x7FFCA1C0F7F0`) and DR1
(`ntdll!NtTerminateProcess` at `0x7FFCA10CDB80`) remain armed on every thread the script
touched — for the entire subsequent fo-verbose flight and (by extension) the 24+ hours the
game survived.

Precondition status: **H1 (DR breakpoints stall PI dispatch) requires the DRs to remain armed
during the fo flight; that requirement is satisfied.** No launch necessary to confirm.

Instrument-artifact note: the `try/finally: ResumeThread(th)` on
[hwbp_movei.py:220](scratchpad/s176/hwbp_movei.py:220) runs even when `SetThreadContext`
fails, so no thread can be left permanently suspended by the DR install. This retires the
"game thread got suspended" branch of H3 (see below).

## Flight 2: fo's OnPI, WaitTid, InstallHook mechanics [M]

Every load-bearing line cited below is verbatim from
[tools/sigbypass-mod/tutorial_launch.cpp](tools/sigbypass-mod/tutorial_launch.cpp).

**Line 43** — the fixed offsets fo depends on:
```
constexpr uintptr_t kPiRva=0x13454A0, kObjObjectsRva=0x9E38930,
                    kNamePoolRva=0x9D81450, kGGameTidRva=0x9D49158;
```

**Line 1665** — `WaitTid` is a one-shot polling read:
```
static DWORD WaitTid(DWORD to){
    uint32_t*s=(uint32_t*)(g_modBase+kGGameTidRva);   // ← FIXED game-binary field
    DWORD dl=GetTickCount()+to;
    while(GetTickCount()<dl){
        if(SafeReadable(s,4)){
            uint32_t v=0; memcpy(&v,s,4);
            if(v) return v;                            // first nonzero wins, returns immediately
        }
        Sleep(20);
    }
    return 0;
}
```
⇒ **`g_gameTid` is captured ONCE at fo init, read from a single fixed field the game itself
writes**. There is no refresh mechanism. If the game later reassigns which thread services
PI dispatch (unlikely per UE architecture), or if the field's value goes stale for any other
reason, fo has no way to notice.

**Line 1487-1515** — `OnPI` is a strict filter with a silent early-out:
```
extern "C" void OnPI(void* /*ctx*/, void* frame, void*){
    if(g_done) return;
    ...
    if(g_inHook) return;
    if(GetCurrentThreadId()!=g_gameTid) return;   // ← SILENT return, no counter
    if(!LooksLikePtr((uintptr_t)frame)) return;
    InterlockedIncrement(&g_hitsGT); g_inHook=1;  // hitsGT only counts AFTER the TID filter
    ...
    // fallthrough for RM_FORCEOPEN (kRunMode=0):
    CallNative(g_ecc,g_eccThunk,g_eccChild,(void*)g_kslCDO,g_pbuf,g_rbuf);  // ExecuteConsoleCommand
    g_done=1; g_inHook=0;
}
```
⇒ **`hitsGT` counts only game-thread PI dispatches. It says NOTHING about total PI activity
across other threads.** Non-game-thread PI dispatches return at line 1513 without touching any
counter. The 17-line S179 marker therefore cannot distinguish "no PI at all" from "PI dispatching
on the wrong TID". This observability gap is a shim-side defect, not a game-side finding.

**Line 1631** — `InstallHook` writes 5 bytes with no readback verification:
```
static bool InstallHook(){
    ...
    uint8_t p[5]={0xE9,(uint8_t)rel,(uint8_t)(rel>>8),(uint8_t)(rel>>16),(uint8_t)(rel>>24)};
    bool ok=SafeWrite(g_pi,p,5);   // 5-byte E9 rel32 jmp AT ProcessInternal
    if(!ok) HookUnlock();
    return ok;
}
```
⇒ After InstallHook returns success, there is no mechanism in fo to detect if the write was
subsequently overwritten (by the protector's integrity check or otherwise). The 17-line marker
would emit `[4] TIMEOUT hitsGT=0` in both "hook stayed intact but game was silent" and
"hook was reverted so no dispatch reached OnPI" cases.

**Line 24726-24731** — the RM_FORCEOPEN wait loop:
```
if(!InstallHook()){Marker("[3] FAIL InstallHook\r\n"); ... return 6;}
DWORD t0=GetTickCount(); while(!g_done && GetTickCount()-t0<8000) Sleep(20);
UninstallHook();
```
⇒ Fo holds the hook for EXACTLY 8 seconds. If no game-thread PI dispatch reaches OnPI in that
window, `g_done` never becomes 1 and the timeout emits `[4] TIMEOUT`.

## The five candidate mechanisms and their final grades

Every candidate is compatible with the exact S179 phenotype. The 17-line marker cannot
separate them. Grades below reflect offline-derivable priors only.

| # | Hypothesis | Grade | Load-bearing evidence |
|---|---|---|---|
| **H1** | DR breakpoints stall game-thread PI dispatch | **[I]** | Precondition confirmed (Flight 1: DRs stay armed). Sub-mech (a) direct execution is REFUTED by 24h+ survival; sub-mech (b) indirect via other threads is [S] (no STATUS_SINGLE_STEP evidence); sub-mech (c) DR-check anti-debug is the [I] survivor by analogy to FK-10 protector sophistication. |
| **H2** | Protector reverted fo's ProcessInternal E9 hook | **[S]** | Three strong priors AGAINST: (1) no documented precedent for silent revert in this project — every measured protector response is TERMINATION (FK-7 10/10, S111 11/12, S168 ~3min kill for packer1 .text); (2) 24h+ survival directly contradicts FK-7's kill response; (3) 8s window vs ~180-300s check period gives ~3-4% timing base rate. Preserved only because no direct byte-state readback exists. |
| **H3** | `g_gameTid` is stale; PI dispatches to another thread | **[I]** | Sub-mech (a) UE reassigns GGameThreadId mid-process is [S] (no known UE pattern); sub-mech (b) thread suspension is REFUTED by Flight 1's `finally: ResumeThread`; sub-mech (c) dispatch moved to another thread + silent filter discard is [I] — the observability gap at OnPI line 1513 is REAL and measured. |
| **H4c** | Game thread wedged in patched KiUserExceptionDispatcher after DR0 fired on protector kill routine | **[I-weak]** | Verifier revised analyzer's [I] to [I-weak]. Three unmeasured critical premises: (a) integrity check fires within 8s (S168's ~3min undermines this); (b) check runs on game thread not protector thread (pure speculation); (c) dispatcher patched to loop-on-DB (no source). Analyzer's own strongest refutation: DR0 fires on the `0xBA` byte BEFORE `mov edx,0xDEAD` commits and BEFORE syscall issues — meaning game survives trivially with NO wedge required. |
| **H4d** | 8s window is too short for any PI dispatch to reach OnPI | **[I]** | Verifier promoted this as the leading H4-family candidate. Under S168's measured ~3min integrity-check period, and given a menu-parked game may have PI-quiescent intervals, an 8s window may simply be too short to observe any PI dispatch that passes the `g_gameTid` filter. Cheapest test of all: rebuild fo with 60s poll and re-fly. Predicts identical phenotype to H1/H2/H3/H4c on the S179 marker. |

## Ranked S181 flights

**Rank 1 — `fo-verbose-60s-window` (targets H4d)**
- **Recipe**: Edit [tutorial_launch.cpp:24731](tools/sigbypass-mod/tutorial_launch.cpp:24731):
  change `GetTickCount()-t0<8000` to `<60000`. Rebuild fo-verbose.
  Run F9 recipe EXACTLY as S177 (DRs armed). Read marker.
- **Cost**: CHEAP — 1 rebuild + 1 game launch. Single-variable change to an existing well-
  understood knob.
- **Expected outcomes**:
  - `hitsGT>0` with time-to-first-hit in `[8s, 60s]` → **H4d CONFIRMED** [I]→[M]; PI is
    dispatching, just not in the S177 8s window. H1/H2/H4c all become moot for this phenotype.
  - `hitsGT=0` at 60s → H4d REFUTED; halt is durable > 60s, promoting H1/H2/H3/H4c into the
    primary suspect set.
- **Either outcome cheaply cuts the hypothesis space in half.** Run this first.

**Rank 2 — `fo-verbose-DR-clear-first` (targets H1 + H4c simultaneously)**
- **Recipe**: Launch game `-CompanionWatch`. Wait menu-ready. Run
  `py scratchpad\s176\hwbp_movei.py --clear` (Flight 1 confirms this mode disarms DR0+DR1).
  Then run F9 recipe from step 3 onward EXACTLY. Add a `GetThreadContext` readback of DR0/DR1
  on the game thread after `--clear` as a safety check (closes the "clear silently failed"
  instrument-artifact risk). Read marker.
- **Cost**: CHEAP — 1 game launch, no rebuild, one extra PS command.
- **Expected outcomes**:
  - `hitsGT>0` → **H1 AND/OR H4c CONFIRMED** — DRs were the cause. Design a shipping-safe
    DR-clear-before-InstallHook wrapper.
  - `hitsGT=0` → **H1 AND H4c both REFUTED**; halt cause lives in H2, H3, or H4d, which need
    different tests.
- **Eliminates TWO hypotheses at once.**

**Rank 3 — `fo-verbose-with-byte-readback-and-per-TID-counter` (targets H2 + H3(c))**
- **Recipe**: Modify fo-verbose:
  1. Add 4-line PI-bytes readback BEFORE `UninstallHook` at line 24732:
     ```cpp
     uint8_t nowBytes[5]={0};
     if(SafeReadable(g_pi,5)) memcpy(nowBytes, g_pi, 5);
     Markerf("[4v] PI bytes after 8s wait: %02x %02x %02x %02x %02x (E9=intact, %02x=kPiProlog[0]=reverted)\r\n",
             nowBytes[0], nowBytes[1], nowBytes[2], nowBytes[3], nowBytes[4], kPiProlog[0]);
     ```
  2. Add 64-slot hashed per-TID counter in `OnPI` BEFORE the `g_gameTid` filter (interlocked
     increment on `tid & 63`), dump non-zero rows at `[4] TIMEOUT`.
     Rebuild. Run F9 recipe. Read marker.
- **Cost**: MODERATE — ~40 lines added, 1 rebuild, 1 game launch. Both instruments are
  read-only additions; no perturbation of existing hook mechanics.
- **Expected outcomes**:
  - Byte readback: intact `0xE9`+rel32 REFUTES H2; restored `kPiProlog` promotes H2 to [M].
  - Per-TID counter: nonzero row on non-`g_gameTid` TID CONFIRMS H3(c) (dispatch moved);
    all zeros REFUTES H3(c) and points to H1/H2/H4c/H4d.
- **Discriminates two hypotheses in one flight with orthogonal signals.**

**Rank 4 — `fo-verbose-parallel-thread-inspect` (Recipe B for H4c)**
- **Recipe**: Launch F9 exactly. In a parallel PS window: enumerate SUPERVIVE threads,
  `SuspendThread` on `tid=g_gameTid` (read from fo's `[0v] WaitTid ok gameTid=NNNN` line),
  `GetThreadContext`, decode RIP. Do this DURING fo's 8s window.
- **Cost**: MODERATE — 1 game launch, requires precise timing of parallel PS session within
  the 8s fo window. Risk: `SuspendThread` on game thread may perturb the very state being
  measured (Heisenberg).
- **Expected outcomes**:
  - RIP in `ntdll!KiUserExceptionDispatcher` or `runtime.dll` near `0x80F7F0` →
    H4c CONFIRMED [I-weak]→[M-caveat].
  - RIP in normal game code → H4c REFUTED; game thread running fine but PI silent = H2 or H3.
  - RIP in fo's own stub → new hypothesis about hook self-recursion.

**Rank 5 — `fo-baseline-no-DR-install` (base rate for H4d + confound isolation)**
- **Recipe**: Launch game normally (NO F9 sequence, NO `hwbp_movei.py`). Stage fo-verbose
  alone with the SAME 8s window. Read marker.
- **Cost**: CHEAP — 1 game launch, no rebuild, no DR install. The cleanest possible control.
- **Expected outcomes**:
  - `hitsGT>0` → the F9 sequence (either DR install or companion kill) IS what causes PI
    silence; H1/H4c families gain support.
  - `hitsGT=0` → PI silence is NOT F9-caused; either menu-parked base rate is naturally quiet
    in 8s (H4d further supported) or something else in fo's own flight causes the halt
    independently.
- **Should be run in parallel with Rank 1 to double-cover H4d.**

## New rules banked

### S180-a: When a phenotype is a strict subset of what multiple hypotheses predict, do NOT grade a preferred hypothesis higher than [I] on that phenotype alone — even if the story feels most elegant. Every hypothesis compatible with the exact same evidence deserves the same grade until a discriminator is run. [M]

Applied here: H1/H2/H3/H4c/H4d all predict "`hitsGT=0` for 8s, game alive." The 17-line
marker cannot separate them. Grading any one above [I] without a discriminator would be
manufacturing a false verdict. Register instances 132–136 are variations on this failure
mode; S180 exposed it explicitly on FIVE co-equal candidates. **Instance #137.**

### S180-b: A silent-filter observability gap in a shim (e.g. OnPI's bare `return` at line 1513 without a counter) is itself a measurement of the shim, not of the game. Whenever a shim reports a null result derived from post-filter data, add a pre-filter counter in the same session's rebuild — the pre-filter/post-filter delta is the ONLY signal that discriminates "game did nothing" from "game did something the filter dropped." [M]

Applied here: fo's `if(GetCurrentThreadId()!=g_gameTid) return;` at
[tutorial_launch.cpp:1513](tools/sigbypass-mod/tutorial_launch.cpp:1513) makes H3(c)
(dispatch moved to another thread) permanently invisible in the current marker. This is a
shim-side failure, not a game-side finding. A per-TID pre-filter counter is a 5-line fix
that would have made H3 discriminable in S179 itself.

### S180-c: When choosing between a mechanism hypothesis (H4c: wedge in patched dispatcher) and a timing hypothesis (H4d: window too short), rank the timing hypothesis higher unless the mechanism hypothesis has direct evidence. Timing-only hypotheses require zero new machinery and are cheaper to falsify. A rebuild with a wider window is almost always cheaper than an SEH-chain trace. [M]

Applied here: S180 initially graded H4c at [I] and H4d as a mere alternative in the Risks
section. Verifier revised H4c to [I-weak] specifically because H4d has the SAME predicted
phenotype with strictly fewer unmeasured premises AND a cheaper single-flight test.
**Timing hypotheses deserve priority ranking when phenotypes overlap** — a specific
application of Occam's razor to live-flight budgeting.

### S180-d: When SEED cites a project rule (e.g. R-S176-k for VEH denial, FK-7 for standing-`.text` kill), verify the citation actually generalizes to the current context BEFORE using it as load-bearing. FK-7's kill response was measured on OUR `.text` writes at ProcessInternal — extending it to "therefore any tampering triggers kill" overreaches, and S168's split of runtime.dll self-check from FK-32 is the precedent for that overreach being wrong. [M]

Applied here: H2's [S] grade rests partly on FK-7's kill precedent, but S168 already showed
the sibling generalization (packer1 vs packer2 both trigger the check) required an
unexpected refinement. The analyzer honestly flagged this as a mechanism assumption.
**Extending measured behaviors across mechanism boundaries needs the same scrutiny as an
offline-to-live grade transfer.**

## Open questions remaining

1. Is `0x9D49158` actually UE's canonical `GGameThreadId`, or a Loki-specific TID cache that
   may point to render/task threads? A symbol-table cross-check against the game exe would
   settle it offline.
2. Does the protector's integrity check on ProcessInternal actually fire within 8s of a
   standing `.text` write, or is S168's ~3min the correct order of magnitude? A fo-verbose
   with variable poll windows (8s, 30s, 60s, 180s) would map the timing — the Rank 1 flight
   at 60s is one point on that curve.
3. Does the game's PI dispatch on a menu-parked client actually happen "hundreds of times/sec"
   as CLAUDE.md general lore claims, or is there a specific menu state (e.g. after companion
   kill at t+146s) where PI naturally quiesces? A no-DR-install baseline flight settles the
   base rate (Rank 5).
4. Do DR0/DR1 installed on **protector code** (kill primitive, `NtTerminateProcess`) provoke a
   fast integrity re-scan the way ordinary `.text` writes don't? No prior measurement covers
   DR-on-protector-code perturbation.
5. If Recipe A (Rank 2, `--clear` first) shows `hitsGT` still 0, is the wedge cause in fo's
   own state (stale `g_gameTid`, hook revert), in game state (dispatch relocated, thread
   died), or in some protector state carried over from F9 (VEH denial, PIC intercept)?
   Rank 3 (byte readback + per-TID counter) partitions the residual hypothesis space.

## Caveats

- **Every H1–H4 grade is offline-derived from source reads (Flights 1–2) plus SEED evidence.
  None has been LIVE-confirmed on a running game. A live flight can move any grade in either
  direction.**
- The 17-line S179 marker cannot discriminate H1/H2/H3/H4c/H4d — all five predict the exact
  observed phenotype. **This is what makes S180-a a real rule and not just a truism.**
- `n=1` for the S179 F9 phenotype itself. `hitsGT=0` could be stochastic (idle menu period
  with genuine PI silence for 8s) rather than a caused halt. Rank 5's no-DR-install baseline
  flight would settle the base rate — but has not been taken.
- The instrument-artifact register (~136 instances as of S155, +1 this session) predicts a
  material chance that a load-bearing offline precondition falls to re-derivation on live
  evidence. Session S168 refuted the sibling generalization of runtime.dll self-check for
  packer1 vs packer2 — an analogous refinement is a live possibility for S180's assumptions.
- The confounds are not independent: H2 (hook reverted) and H4c (protector wedge) both invoke
  the same integrity-check machinery; Rank 2 (`--clear`) would refute BOTH if `hitsGT` stays
  0, but a single flight cannot separate them if it succeeds.

## Files preserved

- `docs/s180-fk32-post-defeat-analysis-settled.md` — this file
- `C:\Users\eastr\AppData\Local\Temp\claude\...\tasks\wqgvl3ruv.output` — the full
  9-agent workflow output (2.85M tokens), preserving analyzer + verifier findings for each
  hypothesis
- No source or DLL edits this session — the fo-verbose variant at
  [tools/sigbypass-mod/build/tutorial_launch_fo_verbose.dll](tools/sigbypass-mod/build/tutorial_launch_fo_verbose.dll)
  is unchanged from S179. The S181 rebuild is prescribed in the Rank 1/3 flight recipes.

## What S180 did NOT do

- **No live flights.** Rank 1 (60s window) is the recommended first live test; it requires a
  1-line edit to [tutorial_launch.cpp:24731](tools/sigbypass-mod/tutorial_launch.cpp:24731)
  and a rebuild — reserved for the next live session per the "read shipped artifacts first"
  method rule.
- **No CLAUDE.md edits.** The S180 findings should be integrated after Rank 1 has been flown
  and one of H4d / other hypotheses has been promoted to `[M]` or refuted. Writing to CLAUDE.md
  before the discriminator is run would violate S180-a.
- **No commit.** Only new evidence doc; no source edits; no rebuild.
