# S140 Tier 2 — LANE 6: ARM H design and hazard audit

**Scope:** source-level audit of `tools/sigbypass-mod/tutorial_launch.cpp` + `build.ps1`, plus the
shipped marker corpus in `docs/` and the built DLLs in `tools/sigbypass-mod/build/`.
No binary RE, no live process, no launches. Every claim graded [M]/[I]/[S].

**HEADLINE — the proposed ARM H design should NOT be built as specified. Three findings, in order
of importance:**

1. ★★★★★ **The `[M]` that motivates the worker thread — "one hit is all this world state
   delivers (flight 1: hitsGT=1, hot list EMPTY)" (`tutorial_launch.cpp:15883-15885`) — is an
   INSTRUMENT ARTIFACT of the one-shot ladder itself.** The ladder occupies the game thread for the
   *entire* profiling window, so both numbers are self-inflicted. A multi-hit state machine is very
   likely viable and is strictly better than a worker thread.
2. ★★★★ **A worker thread that `Sleep()`s does NOT guarantee frames pass.** The ladder still holds
   the game thread for ~4.4–5.2 s *after* `BsPsExperiment()` returns (trailing `Sleep(750)` + the A2
   census). A sampler spawned inside ARM G/H would take its first several samples while zero frames
   pass, and read `(0,0,0)` — **a false "StartNewPhysics did not run"**, which is precisely the
   S139/S140 failure this Tier exists to correct.
3. ★★★★ **No thread is needed at all.** `RM_DROPPLANE` already ships the exact pattern:
   `DpFinalReport()` (`:6884-6893`) "Runs on the WORKER thread after FsDisarm + a settle". Put the
   sentinel *write* at the end of ARM H on the game thread and the *sampling* between `FsDisarm()`
   and `BsFinalReport()` on the already-existing Worker thread. Zero new threads, an existing
   precedent, a guaranteed-released game thread, and `[BS] done` stays last in the marker.

---

## 1. Premise CONFIRMED: `BsLadderStep` runs on the game thread; a `Sleep()` there stops frames

**[M], from source. The path, quoted:**

- `FsThunk` (`:1707-1723`) is installed as `UFunction.Func` on 17,563 BP UFunctions. It is entered
  from `UFunction::Invoke`'s `call [rax]` — i.e. on **whatever thread dispatches the BP function**,
  which for `ReceiveTick*` is the game thread. It calls `OnPI(ctx,frame,result)` and only then
  forwards to the real `ProcessInternal`.
- `OnPI` (`:1234-1238`):
  ```
  if(g_done || g_inHook) return;
  if(GetCurrentThreadId()!=g_gameTid) return;      <- the body runs ONLY on the game thread
  if(!LooksLikePtr((uintptr_t)frame)) return;
  InterlockedIncrement(&g_hitsGT); g_inHook=1;
  ```
- `:1274` `if(kRunMode==RM_BOTSPAWN){ DoBotSpawn(); ... }` → `DoBotSpawn` (`:16007`) →
  `BsLadderStep()` (`:15892`).

⇒ every `Sleep()` and every `BsScanWorld()` inside `BsLadderStep` executes **on the game thread,
inside a BP dispatch, before `ProcessInternal` has even been called for that function.** Frames
cannot advance. **CONFIRMED, [M].**

### 1a. Are the existing controls vacuous? — PARTLY, and one is worse than "vacuous"

**A0 → A1 "STABILITY CONTROL" (`:15910-15919`): substantially vacuous, and the header oversells it.**
The whole A0→A1 window is game-thread-blocked: A0's census, the `Sleep(KBSSETTLEMS=750)`, and A1's
census are all on the game thread. **[M]** from the shipped markers — the census prints its own
elapsed time:

| file | A0 census | settle | A1 census | window blocked |
|---|---|---|---|---|
| `docs/fk24-stage-s140f1-a1-1-gft.txt` | 4046 ms | 750 ms | 3625 ms | ≈ 8.4 s |
| `docs/fk24-stage-s139f4-a1-1-gft.txt` | 4391 ms | 750 ms | 3844 ms | ≈ 9.0 s |
| `docs/fk24-stage-s137f4-1-gft.txt`    | 3609 ms | 750 ms | — | — |

Actor spawning in UE is game-thread-only [I, strong — stock engine], so **the control cannot see the
class of activity it most needs to exclude.** What it *does* still test: (a) instrument determinism
(the census returns the same number twice), (b) object creation on non-game threads (async
loading / streaming).
⇒ **Downgrade the A1 control's claim.** `A0==A1` is *not* evidence that no actor spawned during the
window; it is evidence that the census is repeatable and that nothing off-thread created objects.

**Post-call `Sleep(KBSSETTLEMS)` "Give a spawned actor a tick to register before counting it"
(`:15997`): GENUINELY VACUOUS, and its stated reason is FALSE.** No tick can occur — the game thread
is asleep inside our own frame. The census works anyway because `GUObjectArray` registration is
**synchronous** inside `StaticConstructObject_Internal` / `SpawnActor`, which we call synchronously.
**Empirical confirmation [M]:** `dCtl=3 dHero=3` in `docs/fk24-stage-s139f4-a1-1-gft.txt:175` and
`s140f1:175` — the census *did* see the newly spawned objects. So the sleep is harmless but useless.

⚠⚠ **The dangerous corollary a successor will trip on: anything that genuinely needs a TICK has NOT
happened when this ladder reads it.** That includes deferred `BeginPlay` on some paths, the component
registration queue, `AGameStateBase::AddPlayerState` reaching `PlayerArray`, and — directly relevant
to S140/S141 — **any movement simulation whatsoever**. S137 flight 4's BehaviorTree / Blackboard reads
were valid only because `RunBehaviorTree` is synchronous inside `OnPossess`, not because a tick ran.
**Fix the comment; it is an instrument-artifact generator.**

---

## 2. ★★★★★ THE MOTIVATING `[M]` IS AN ARTIFACT — `hot: 0` / `hitsGT=1` ARE SELF-INFLICTED

`tutorial_launch.cpp:15883-15885` says:
> "★ ONE-SHOT LADDER. Everything happens in a SINGLE game-thread hit, because **[M]** one hit is all
> this world state delivers (flight 1: hitsGT=1 at t=+15 s, hot list EMPTY)."

**REFUTED — both observations are produced by the ladder, not by the world.**

**(a) `hitsGT=1` is structural, not a rate. [M], from source.** `OnPI` increments `g_hitsGT` *after*
the `if(g_done||g_inHook) return;` early-out (`:1234` vs `:1238`). There is exactly one game thread,
so while the ladder is inside `OnPI` it cannot re-enter, and after the ladder sets `g_done=1`
(`:16003`) every later dispatch returns before the increment.
**`hitsGT` can never exceed 1 in a one-shot ladder, whatever the dispatch rate.**

**(b) `hot: 0 in the first 4000 ms` was measured while our own A0 census held the game thread. [M].**
Marker writes are append-ordered, so file order is temporal order. In **3 of 3** bot-lineage markers
the game thread's `[BS] ---- A0` line appears **BEFORE** the worker's `[FS] arm:` line (the first hit
landed *during* `FsScan`, which swaps incrementally), and the A0 census then ran 3609–4391 ms —
covering the whole `KFSPROFILEMS=4000` window:

```
docs/fk24-stage-s140f1-a1-1-gft.txt
  12 [FS] cfg ... name='' profileMs=4000 ...            <- worker
  13 [BS] ---- A0: BASELINE WORLD SCAN ----             <- GAME THREAD, already in the hit
  14 [FS] arm: swapped=17563 ... (scan 3125 ms ...)     <- worker; FsHold t0 starts here
  18 [BS] census A0 ... 4046 ms                         <- game thread blocked 4046 ms
  22 [FS] hot: 0 distinct UFunctions ... first 4000 ms  <- the window it "measured"
```
Reproduced identically in `s139f4-a1-1-gft.txt` (13/14/17/25) and `s137f4-1-gft.txt` (13/14/20/25).

**(c) THE DECISIVE CONTROL: the identical `KFSNAME=""` config in a different sitting delivered 73
dispatches/s.** `docs/fk24-s128-poolspawn-RESULT.txt`:
```
147 [FS] cfg KFUNCSWAP=1 max=0 name='' profileMs=4000 ...   (IDENTICAL flags)
157 [FS] arm: swapped=17563 BP UFunctions                    (IDENTICAL count)
181 [FS] hot: 14 distinct UFunctions dispatched on the GAME THREAD in the first 4000 ms
      hot[03] hits=41  BP_LokiHeroCharacter_C::ReceiveTickClient
      hot[02] hits=41  BP_HERO_Ronin_C::ReceiveTick
      hot[01] hits=41  BP_LokiPlayerController_C::ReceiveTick
198 [FS] *** ARMED AND LIVE: hitsGT=588 allThreadCalls=588 after 8016 ms (~73 game-thread dispatches/s)
200 [FS] t=+15s hitsGT=588 called=587 ...
```
`RM_POOLSPAWN` runs its heavy census on the **worker** thread *before* arming (its `[DP] P0-BEFORE`
block is lines 10–146, before `[FS] cfg` at 147) and is a **paced** ladder, so the game thread stays
free — and the same world staging (a possessed `BP_HERO_Ronin_C` + `BP_LokiPlayerController_C`)
delivers **41 BP ticks per 4 s ≈ 10/s.**

⇒ **[M] `KFSNAME=""` is not the limiting factor; game-thread occupancy is.**
⇒ **[I, strong] a multi-hit state machine will get its hits.** NOT [M]: no bot-lineage sitting has
ever released the game thread and then counted, and the s128 sitting used a different injection
sequence (`dropplane_b1only` + `droppod` staged first).

**Corroborating raw number:** `[FS] t=+15s hitsGT=1 called=0 allThreadCalls=207` — identical in
`s137f4`, `s139f4` and `s140f1`. `called=0` with `allThreadCalls=207` is CLAUDE.md's own documented
discriminator: *"`allThreadCalls>0 && called<allThreadCalls` means we are inside our own step"*. The
206 extra calls are our own nested BP dispatches from `SpawnAIFromClass` → `SpawnDefaultController`
→ constructors, re-entering `FsThunk` and bouncing off `g_inHook`. **Not background activity, and not
a dispatch-rate measurement either.**

---

## 3. Is a worker thread safe here? (mechanics)

| item | verdict | evidence |
|---|---|---|
| `Marker()` `:405` | **THREAD-SAFE** | `CreateFileA(FILE_APPEND_DATA, FILE_SHARE_READ\|FILE_SHARE_WRITE, OPEN_ALWAYS)`, one `WriteFile`, `CloseHandle`. `FILE_APPEND_DATA`-only access makes each `WriteFile` an atomic append; two threads cannot interleave *within* a write. No statics. |
| `Markerf()` `:406` | **REENTRANT** | `char b[512]` is a **stack** buffer; `_vsnprintf_s` then `Marker`. |
| `SafeReadable()` `:407` | thread-safe, **TOCTOU** | `VirtualQuery` + arithmetic, no statics. ⚠ The page can be decommitted between query and read; that race is *higher* off the game thread. Keep every off-thread read inside SEH. |
| `SafeWritable()` `:1552` | thread-safe | same shape; the `KWPROBE==2` exemption is compiled out (`KWPROBE` defaults **0**, `:557`). |
| `LooksLikePtr()` `:428` | thread-safe | pure arithmetic. |
| `GetFNameStr` / `NameId` / `ClassOf` | thread-safe | caller-supplied buffers. |
| `PropOffsetSuper()` `:2027` | thread-safe | no statics. |
| `PhChainHas` / `PhChainHasExact` `:5518` / `:5540` | thread-safe | caller-supplied `chainOut`. |
| **`FaultStr()` / `DP_FAULT`** `:1004` | ⛔ **NOT THREAD-SAFE** | `static char b[160]`, and it reads process-global `g_fltCode/g_fltRip/g_fltAddr` written by `SehCap` (`:988`) from **any** faulting thread. **A worker-thread fault silently overwrites the game thread's fault record and can corrupt a concurrently-formatting `FaultStr()`.** |
| `GcAlive` / `GcFindItem` `:1979` / `:1848` | thread-safe but **SLOW** | full `GUObjectArray` walk. Never on a sampling cadence. |
| `FindObjExact` / `FindClassExact` `:1434` / `:1445` | thread-safe, slow | full walk. |

**CreateThread precedents:** `Worker` (from `DllMain`, `:17715`), `WpThread` / `WpSelfWatch` (from
`Worker`, `:16890-16891`), `PhWatchdog` (from `Worker`, `:17155` — with a stop flag and a
`WaitForSingleObject(wd,5000)` join at `:17161`). **[M] all four are created from `DllMain` or the
Worker thread. There is ZERO precedent for `CreateThread` from inside a game-thread hit**, which is
what ARM H proposes. It is legal (no loader lock held), but it is a novel shape here and the new
thread inherits none of the existing stop/join discipline.

**Module lifetime is NOT a problem [M, source]:** the manual mapper (`tools/inject/mmap.go`) never
calls `VirtualFreeEx`/`MEM_RELEASE` on the mapped image, and there is no `FreeLibrary` anywhere in
`tools/inject/`. A thread outliving `Worker` will not execute freed code.

---

## 4. The lifetime / ordering problem — where the samples land

**Exact sequence (RM_BOTSPAWN, `:17539-17575`):**
```
worker:  FsArm()  ->  FsHold(KPDMODEHOLDMS=120000)      // while(!g_done && el<ms) Sleep(20)
game:    FsThunk -> OnPI -> DoBotSpawn -> BsLadderStep -> ... -> BsPsExperiment()   [ARM H here]
game:                              ... Sleep(750); A2 census (~3.6-4.4 s); g_bsStep=4; g_done=1
worker:  FsHold returns (<=20 ms) -> FsDisarm()  [g_done=1; FsScan restore over 155k objs, 1-3.6 s]
worker:  BsFinalReport()  ->  Markerf("[BS] done ...")  ->  return 0 or 9
```

**Answers:**
- After `g_done=1` **nothing tears the DLL down.** `Worker` just returns; the image stays mapped.
  A sampler thread **would still be running 5 s later** — safely, but unsupervised and unjoined.
- **Its `Marker()` writes would interleave with, and can land AFTER, `BsFinalReport()` and
  `[BS] done`.** Cover from the spawn point to `[BS] done` ≈ `Sleep(750)` + A2 (~4 s) + FsDisarm
  (~1–3.6 s) + report ≈ **6–8 s**. A shorter sampler lands *inside* the A2/report block
  (interleaved and confusing); a longer one lands *after* `[BS] done`, which is the line every stage
  script and prior write-up treats as the terminator.
- ⛔ **And the first ~4.7 s of samples are taken with ZERO frames passing** (trailing `Sleep(750)` +
  A2 census both hold the game thread). This is the fatal defect: it manufactures exactly the false
  negative S141 is trying to avoid.

**CLEANEST ORDERING — no new thread (RECOMMENDED):**
```
game thread, end of ARM H:  read + record RAW +0x16B0..+0x16C7 and +0xE8 BEFORE
                            write the sentinel to CMC+0xE8/F0/F8, readback-verify
                            latch g_snCMC / g_snPawn / g_snArmed=1;  RETURN (no Sleep)
worker thread, RM_BOTSPAWN block, BETWEEN FsDisarm() and BsFinalReport():
                            BsSentinelSample();     // all Sleeps are on the WORKER
worker:                     BsFinalReport();  "[BS] done"
```
This is the **documented `RM_DROPPLANE` B4 precedent verbatim** (`:6884` — *"Runs on the WORKER
thread after FsDisarm + a settle, so neither heavy sweep is a game-thread frame hitch, and so a
deferred spawn has time to exist"*). It guarantees the game thread is released before the first
sample, keeps `[BS] done` last, and needs no `CreateThread`, no stop flag and no join.

---

## 5. Does the arm need `g_done` for frames to pass? — NO

**[M] from `FsThunk` (`:1707-1723`): frames pass whether or not `g_done` is set.** `FsThunk`
*always* tail-calls the real `ProcessInternal` (`if(g_fsPi) ((PFN_THUNK)g_fsPi)(ctx,frame,result);`).
Before `g_done`, `OnPI` runs the ladder then returns and dispatch continues; after `g_done`, `OnPI`
returns at its first line and dispatch continues with a few ns of overhead.
**The ONLY thing that stops frames is game-thread OCCUPANCY by our own code.**

After `g_done` the swapped `Func` pointers still point at `FsThunk` until `FsDisarm()` restores them
(`:1832-1840`), which raises `g_done` again first "so OnPI stops doing work instantly". Between
`g_done` and the end of `FsDisarm` the swap is a pure pass-through.

⚠ **Consequence for instrumentation: `g_hitsGT` is DEAD as a frame clock after `g_done`** (the
increment sits after the early-out). Do not use it to prove frames passed during sampling.

---

## 6. ★★★★★ Better in-process design — and the frame clock this design is missing

### 6a. Multi-hit state machine — VIABLE, and better than a thread
Given §2, the recorded reason for the one-shot ladder is gone. `RM_PHASELADDER`, `RM_DROPPLANE` and
`RM_POOLSPAWN` are all paced ("ONE arm per game-thread hit"), and `FsHold` gives them
`KPDMODEHOLDMS = 120000 ms` (`:7921`) of budget. **A paced ARM H is strictly better than a worker
thread**: samples are taken *on* the game thread between real frames, so "a frame passed" is proven
by construction rather than assumed.

But it is **[I, strong], not [M]**, and it has one hard prerequisite:
⚠ **Move the three `BsScanWorld` censuses OFF the game thread** (3.6–4.4 s each). Copy
`RM_POOLSPAWN`: A0 on the worker *before* `FsArm()`, A2 on the worker after `FsDisarm()`. Otherwise
the ladder still eats ~12 s of frames and the pacing buys little.
⚠ If hits genuinely do not arrive, the existing `if(g_bsStep<N) return 9` guard (`:17570`) catches it
and `FsHold`'s own +8 s verdict line names it. That failure mode is safe and already instrumented.

### 6b. THE MISSING INGREDIENT — a FRAME CLOCK, in-run, already measured
Whichever design is chosen, **every sample must carry proof that frames passed between it and the
previous one**, or a `(0,0,0)` payload is uninterpretable.

**Use `CMC+0x12B0` (`TimeSinceFallingStart`).** S139 measured it advancing at **1.0× real time on
both the bot and the player** (bot 33.14 → 43.34 over 10.2 s). Read-only, already validated, one
4-byte read per sample.
- `Δ(+0x12B0) ≈ Δwall` ⇒ frames passed; the sample is interpretable.
- `Δ(+0x12B0) == 0` ⇒ **NO FRAMES PASSED; the sample is VOID, not negative.** Print it as VOID.

This single field converts the whole hazard in §4 into a detected, labelled condition. Without it the
proposed design cannot distinguish "StartNewPhysics did not run" from "we were holding the game
thread". **Make it mandatory.**

---

## 7. Bit 9 (0x200) and the regression gates — one gate is ALREADY BROKEN

### 7a. Bit 9 is free
**[M]** `KBSPSARMS` bit usage, `:14179-14183` + `:15679-15738`: bit0 `0x01` control spawn · bit1
`0x02` poke+treatment · bit2 `0x04` restore · bit3 `0x08` ARM B · bit4 `0x10` ARM C · bit5 `0x20`
ARM D · bit6 `0x40` ARM E · bit7 `0x80` ARM F · bit8 `0x100` ARM G.
**Highest bit used = `0x100`. Bit 9 (`0x200`) is UNUSED.**
`0x3A0 = ARM H | ARM G | ARM F | ARM D` — the `gasattr` set (`0x1A0`) plus bit 9. Correct.

### 7b. How the existing arms keep `.text` stable — MEASURED, with a positive control
Byte-scan of the shipped DLLs (`strings` is not installed on this machine — recorded S136 defect — so
this is a Python byte count, **with `KERNEL32` as a passing positive control on every file**):

| dll | `[GASX]` | `ARM G: port the DS GAS recipe` | `ARM G SKIPPED by KBSPSARMS bit8` | `ARM F: drive Update...` | `KERNEL32` |
|---|---|---|---|---|---|
| `botai` | 0 | 0 | **0** | 0 | 1 |
| `driverecompute` | 0 | 0 | **0** | 1 | 1 |
| `driverecompute_ctrl` | 0 | 0 | 0 | 0 | 1 |
| `gasattr` | 22 | 1 | **0** | 1 | 1 |
| `gasattr_ctrl` | 0 | 0 | **1** | 1 | 1 |
| `lokibot` | 0 | 0 | 0 | 0 | 1 |

⇒ **[M] the `if(KBSPSARMS&bit) BsPsX(); else Marker("...SKIPPED...")` idiom DOES fully dead-code-
eliminate the arm body when the bit is clear** (`gasattr_ctrl`: `[GASX]` = 0) — **but it leaves the
~40-byte skip literal in `.text`.** That literal is what moves every `KBSPS` build's digest when a
new arm is added.

### 7c. ⚠⚠ `driverecompute a2a952babfed256b` IS NOT A VALID REGRESSION GATE TODAY
`build.ps1:625` `driverecompute` = `-DKBSPSARMS=0xA0`; `build.ps1:635` `gasattr-ctrl` =
`-DKBSPSARMS=0x0A0`. **Every other flag is identical and `0xA0 == 0x0A0`** ⇒ from one source tree
they compile to identical `.text`. They do not:

```
python tools/sigbypass-mod/text_digest.py tools/sigbypass-mod/build/*.dll
tutorial_launch_botai.dll                RAW=5e47c13cf7f0a158  rawsize=111104   (mtime Aug 23 19:30)
tutorial_launch_driverecompute.dll       RAW=a2a952babfed256b  rawsize=134144   (mtime Aug 23 02:43)
tutorial_launch_driverecompute_ctrl.dll  RAW=2a91f0aa7f3d521b  rawsize=131584   (mtime Aug 23 02:43)
tutorial_launch_gasattr.dll              RAW=2fcc2536e21f18e3  rawsize=137728   (mtime Aug 23 19:30)
tutorial_launch_gasattr_ctrl.dll         RAW=4465ebc4d7168c03  rawsize=134656   (mtime Aug 23 19:30)
tutorial_launch_lokibot.dll              RAW=e123816b65d68e5e  rawsize=131072   (mtime Aug 23 01:00)
```
`driverecompute` has **0** occurrences of `ARM G SKIPPED by KBSPSARMS bit8` while `gasattr_ctrl`
(same flags) has 1 ⇒ **[M] `driverecompute` on disk predates ARM G and does not reproduce from HEAD.**
A rebuild today yields `4465ebc4d7168c03`.

⇒ **CLAUDE.md's "Regression gates `botai 5e47c13cf7f0a158` and `driverecompute a2a952babfed256b`
UNCHANGED" (S139 flight 4) is FALSE for `driverecompute`** — it was quoted from the stale on-disk
artifact, not rebuilt. `botai` (rebuilt 19:30 in the same batch as `gasattr`) genuinely does
reproduce `5e47c13cf7f0a158`.

⚠ **Same shape twice more.** `driverecompute-ctrl` and `lokibot` also share `-DKBSPSARMS=0x20`
(`build.ps1:629` even says *"== lokibot's flags"*) and read **`2a91f0aa7f3d521b` vs
`e123816b65d68e5e`** — a second degenerate pair whose recorded digests disagree for the same reason.
And CLAUDE.md records `lokibot 3119d75ae2ca1859` (S137), which matches neither.
**Re-record all four before using any of them as a gate.**

### 7d. HOW TO KEEP THE FOUR NAMED ARTIFACTS BYTE-IDENTICAL

- **`botai` (`5e47c13cf7f0a158`) — SAFE UNCONDITIONALLY, provided ARM H lives inside `#if KBSPS`.**
  `botai` is built with `-DKBSAI=1` and **no** `-DKBSPS`, so `KBSPS` defaults to 0 (`:14176`) and the
  entire `#if KBSPS … #endif` region (`:14186`–`:15742`) is preprocessed away. **[M]** confirmed by
  §7b: `botai` contains zero ARM F **and** zero ARM G literals, including the skip strings.
- **`driverecompute` (`a2a952babfed256b`) — cannot be preserved, and is already broken (§7c).**
  Do not claim it. Re-record as `4465ebc4d7168c03` (== `gasattr-ctrl`), or delete the duplicate
  variant.
- **`gasattr` (`2fcc2536e21f18e3`) and `gasattr-ctrl` (`4465ebc4d7168c03`) — a bare runtime bit test
  WILL MOVE BOTH**, because the `else Marker("---- ARM H SKIPPED by KBSPSARMS bit9 ----")` literal is
  emitted even when bit 9 is clear (§7b: `gasattr_ctrl` carries ARM G's skip string).

**⇒ THE ONLY SAFE PATTERN: put ARM H behind a NEW compile-time knob defaulting to 0, so the
preprocessor removes the skip literal too.**
```c
#ifndef KBSPSH
#define KBSPSH 0      // S141 ARM H (velocity sentinel). 0 => not compiled at all, so every
                      // pre-S141 variant's .text is byte-identical. Same discipline as
                      // KBSSBCALL (:14206) and KFRAMEINIT.
#endif
...
#if KBSPSH
    if(KBSPSARMS&0x200) BsPsSentinel();
    else Marker("[SNT] ---- ARM H SKIPPED by KBSPSARMS bit9 ----\r\n");
#endif
```
`build.ps1`:
```
'gasattr-sentinel'      = @(...same as gasattr..., '-DKBSPSH=1','-DKBSPSARMS=0x3A0')
'gasattr-sentinel-ctrl' = @(...same as gasattr..., '-DKBSPSH=1','-DKBSPSARMS=0x1A0')  # ARM H out, ARM G in
```
⚠ **Verify, don't assume:** after the edit, rebuild `botai`, `gasattr`, `gasattr-ctrl` and diff their
RAW digests against §7c's table **in the same command**. An edit that does not move `.text` is
ambiguous between "cached build" and "semantic no-op" (recorded S136) — so also confirm the new
`gasattr-sentinel` differs from `gasattr` **and** from `gasattr-sentinel-ctrl`.
**An A/B against a copy of itself has burned a live run in this project.**

---

## 8. Adversarial pass — other ways this design produces a FALSE RESULT

1. ⛔ **Record `+0x16B0..+0x16C7` BEFORE the sentinel write.** If it already holds a stale non-zero
   value, "the sentinel is not there" and "it was never written" are indistinguishable. Print the raw
   24 bytes before and after. Pre-register **all four cells** of the 2×2
   {payload == sentinel / payload == 0 / payload == something else / unreadable} ×
   {`+0xE8` still holds the sentinel / `+0xE8` was overwritten}. Only *(payload == sentinel)* is a
   clean positive; *(payload == 0 AND `+0xE8` still sentinel AND the frame clock advanced)* is the
   clean negative. **Everything else is VOID.**
2. ⛔ **`+0xE8` is a live game field.** If the game writes `Velocity`, the sentinel vanishes from
   `+0xE8` and the control read is destroyed — informative, but only if recorded. Sample `+0xE8` on
   **every** pass, not just at the end.
3. ⚠ **`(0.0009765625, 0, 0)` = 2⁻¹⁰ is well chosen** — exactly representable, and ~0.001 uu/s cannot
   perturb the system. Keep it small; do NOT "make it obvious" with a large value.
4. ⛔ **DO NOT also poke the PLAYER's `Velocity` while ARM G is armed in the same binary.**
   `KBSPSARMS=0x3A0` has bit8 set, so ARM G runs, and ARM G's *entire* specificity control is that
   "the PLAYER hero is deliberately UNTREATED" (`:15379-15380`). A second sentinel on the player
   would be a genuinely valuable two-sided control (S139/S140 measured the two CMCs structurally
   identical) — but it must go in a **separate arm/build with ARM G compiled out**, or it destroys
   ARM G's control.
5. ⛔ **Never call `FaultStr()` / `DP_FAULT` off the game thread** (§3): `static char b[160]` plus
   process-global fault state. If a sampler must report a fault, capture the code into a local and
   format it locally.
6. ⚠ **Identity + DECODE control on the CMC, or a zero means nothing.** Required refusals:
   (a) `g_psLbCtl[1]` is a live `LokiBotController`; (b) `pawn = [ctl+0x3F8]` is the *same pointer*
   ARM D/F/G operated on; (c) the CMC is resolved **by name** (`CharacterMovement` UPROPERTY off the
   pawn's class), never by a hardcoded offset — S138 recorded a probe that hardcoded `+0xE0` for
   `Velocity` when it is `+0xE8`; (d) a **two-sided decode control** on the resolved CMC, e.g.
   `MaxAcceleration == 50000.0` (ARM G wrote it) **and** `MovementMode == 3`. Without (d) a wrong CMC
   pointer reads zeros forever and prints "no simulation".
7. ⚠ **Torn reads.** `+0x16B0` is 24 bytes written by the game thread; a worker-thread read can tear.
   A partial sentinel match is detectable — **report the raw 24 bytes and let the reader adjudicate;
   never report only a boolean.** (Recorded S139/S140 defect: a `set()` that collapsed signed zeros,
   and a verdict line whose terms were all always-true.)
8. ⚠ **Re-injection truncates the marker (FK-25).** `Worker` opens `kMarkerPath` with `CREATE_ALWAYS`
   (`:16879`). Anything injected while a sampler is still running destroys the samples. Gate further
   staging on the sampler's own completion line.
9. ⚠ **`KFSREARMMS=60000` re-arm inside `FsHold`** re-walks `GUObjectArray` mid-hold — another ~1–3 s
   of worker CPU that will jitter a worker-thread cadence. Drive the cadence off `GetTickCount()`
   deltas, not off loop count.
10. ⚠ **The exit-code threshold moves with the ladder.** `:17570` `if(g_bsStep<4) return 9`. If ARM H
    adds a step, this must move with it — the lesson the file itself records as "the RM_PHASELADDER
    lesson, re-learned by RM_RIDEABLE and again by RM_DISMOUNT".
11. ⚠ **`Sleep()` on a sampler is not a frame guarantee even after `g_done`.** Nothing in this shim
    stops the game thread after `g_done`, but a hitch, a level-streaming stall or a GC pass can. The
    §6b frame clock covers all of them; a wall-clock `Sleep` covers none.

---

## 9. RECOMMENDATION (concrete)

1. **Do not spawn a thread.** Split ARM H: the **write** at the end of `BsPsExperiment` on the game
   thread (record raw before-values, write, readback-verify, latch pointers, return immediately with
   no `Sleep`); the **sampling** in a new `BsSentinelSample()` called on the Worker thread **between
   `FsDisarm()` and `BsFinalReport()`** at `:17553`. This is the `DpFinalReport` precedent (`:6884`)
   and it guarantees the game thread is released.
2. **Make `CMC+0x12B0` a mandatory per-sample frame clock.** No advance ⇒ print the sample as
   **VOID**, never as a negative.
3. **Compile ARM H behind a new `KBSPSH` knob defaulting to 0** (§7d), so `botai`, `gasattr` and
   `gasattr-ctrl` stay byte-identical. Verify with `text_digest.py` in one command after the edit.
4. **Re-record `driverecompute` / `driverecompute-ctrl` / `lokibot` digests, or delete the duplicate
   variants** (§7c). Three of the four recorded gates in this family do not reproduce.
5. **Fix two comments that are actively generating instrument artifacts:** the one-shot rationale at
   `:15883-15885` (§2) and the "give a spawned actor a tick to register" sleep at `:15997` (§1a).
6. **Consider converting the ladder to paced** (§6a) with the censuses moved to the worker. That is
   the durable fix and it makes multi-hit sampling free; it is a bigger change and need not block
   S141.

---

## 10. What this lane did NOT establish
- **[I, strong], not [M]:** that the bot-lineage world will deliver ~10 BP ticks/s once released.
  The s128 counter-example has a different injection sequence (`dropplane_b1only` + `droppod` staged
  first). One paced flight — or simply reading `hitsGT` after moving the A0 census off the game
  thread — settles it.
- Nothing here was measured against a live process. All evidence is source, shipped markers, and the
  built DLLs on disk.
- No claim about whether the sentinel test itself answers the physics question; that is another
  lane's scope.
- The byte-scan in §7b is over 6 DLLs only, chosen because they are the named gates. It is not a
  survey of all 174 DLLs in `tools/sigbypass-mod/build/`.
