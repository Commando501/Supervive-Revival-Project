# S112 — FK-7 re-tested on the tutorial route. Results.

**2026-08-07.** Pre-registration: `docs/s112-fk7-ab-preregistration.md` (written before any launch).
Driver: `configs/fk7-ab-run.ps1` · campaign: `configs/fk7-ab-campaign.ps1` · analysis:
`tools/crashtri/fk7_ab_analyze.py`. Raw per-run artifacts: `docs/fk7ab/<label>/`.

> **Status: FK-7 CLOSED — cause measured, fix shipped and verified. Successors opened as FK-31 /
> FK-32 (`docs/fk31-fk32-successors.md`).** Originally complete at the pre-registered N = 10 armed
> windows per arm (41 campaign launches,
> 44 rows including the pilot and the four shakedown runs). Every claim is tagged MEASURED /
> INFERRED / OPEN, per project convention.

---

## 0a. ★★★ THE RESULT

| arm | probe | armed windows | died | rate |
|---|---|---:|---:|---:|
| **control** | 600 s standing `.text` patch at `ProcessInternal` (`433cf7d8f6a0770f`) | 10 | **10** | **100 %** |
| **treatment** | heap `UFunction.Func` swap, **no module-image write** (`badecc840bafee84`) | 10 | **2** | **20 %** |

**Fisher's exact, two-sided: p = 0.00071.**
Sensitivity (the one pre-arm death recounted as a death): 11/11 vs 2/10, **p = 0.00022**.

Pre-registered stopping rule honoured: the interim look at N=6/arm gave p = 0.061, which did **not**
meet the p < 0.005 boundary, so the campaign continued to N = 10/arm rather than stopping on a
p that happened to look good.

Positive control (`[PL] *** init complete ***`) fired on **10/12** control and **10/11** treatment
probe-injected launches — symmetric and healthy, so the eight treatment survivals are genuine armed
windows and not silent no-ops. This is the control that replaced the mandated 3x `play_novtguard`
gate, which fires on an ~8 % event and would have declared ~4 sittings in 5 VOID.

### Per-run detail

```
control      DIED  135  91  91  64 115  80 123 114 137  84   (s after probe injection)
             exit  0xC0000005 x9   (ctl-01 predates the exit-code instrument)
treatment    DIED  101 260 ; SURVIVED 331 x8
             exit  0x0000DEAD on the one instrumented death
```

Control deaths cluster at **64-137 s, median ~99 s**. Every treatment survival reached the full
331 s hold.

⇒ **ANSWER: FK-7 is substantially our own standing `.text` patch.** Removing it takes the
armed-window death rate from 100 % to 20 %, and it does not merely reduce the rate -- it **removes
the access-violation kill mode from the armed window entirely** (see §0b).

## 0b. ★★ The kill MODE differs by arm, not just the rate (MEASURED)

Recovered by holding an OS handle open across process exit — an instrument nothing in this project
had used, added mid-session precisely because "no dump" was otherwise indistinguishable from "we
raced crashpad's write".

| exit code | meaning | artifact left | seen in |
|---|---|---|---|
| `0xC0000005` | STATUS_ACCESS_VIOLATION — unhandled exception | crashpad minidump, `RIP == runtime.dll+1`, EXECUTE | **control deaths** |
| `0x0000DEAD` | a deliberate sentinel passed to TerminateProcess/ExitProcess | **none at all** | **treatment deaths** |

**`0xDEAD` is not ours.** `grep` over the shim sources finds it twice, both as *read* sentinels
(`catalog_probe.cpp:191`, `tutorial_launch.cpp:3370`), and there is **no `TerminateProcess` or
`ExitProcess` call anywhere in them**.

⇒ **INFERRED, and it reaches beyond this experiment:** the project's long-standing "artifact-less
death class" has been attributed to hangs, on the reasoning that `CrashReportClient.ini` sets
`Stall.RecordDump=false` so hangs are *configured* to leave nothing. At least some of those deaths
are **not hangs** — they are silent kills with a magic exit code, and the exit code recovers them.
That is a cheap, permanent instrument for a class that was previously pure absence-of-evidence.

## 0c. Fault-family census of this session (MEASURED)

Deduped by report uuid — mandatory, because a stale PENDING report survived 11+ launches and a new
`dumps\crashpad-*` directory is therefore **not** evidence of a death.

```
FINAL CENSUS: 28 distinct report uuids this session
  OURS/protector             28
```

**28 of 28.** (One, `94f62fec`, predates the session; 27 are this session's.) Every one is
`RIP == <runtime.dll base> + 1` = `0x7FFD3B400001` this boot, access EXECUTE,
`ExceptionInformation[0] == 8`.

**Zero dumps with a SUPERVIVE frame at the fault and no self-inflicted signature.** The dump that
would constitute the first real FK-7 evidence in the project still does not exist.

Note the internal consistency: every treatment *dump* in that census is a **staging** death (probe
never injected, `fo` the only module-image writer). The treatment **armed** deaths appear nowhere in
it, because they leave no dump — they are the `0x0000DEAD` silent kills of §0b.

## 0d. What did NOT happen

**No death in this session, in either arm, produced a dump with a SUPERVIVE frame at the fault and
no self-inflicted signature.** That is the dump that would constitute the first real FK-7 evidence
in the project, and it still does not exist -- now across 28 more reports and 41 more launches.

**A tutorial-specific game defect is therefore NOT supported by this experiment.** It is not
*excluded* either -- see the residual in section 8 -- but nothing here is evidence for one.

## 1. What was actually run

One variable: whether a standing `.text` patch is present during the armed window.

| arm | probe | `.text` sha256 |
|---|---|---|
| control | `build\tutorial_launch_play.dll` (RM_PLAY, 600 s standing `.text` patch at `ProcessInternal`) | `433cf7d8f6a0770f` |
| treatment | `build\tutorial_launch_play_funcswap.dll` (heap `UFunction.Func` swap; **no module-image write**) | `badecc840bafee84` |

Hold **330 s measured from probe injection** (staging-invariant). Arms **alternate on armed
windows, not launches**, because a launch that never injects the probe is arm-neutral and counting
it against an arm would silently unbalance the denominator.

## 2. ★ The control-build correction (MEASURED, and it invalidated the documented candidate)

`build\tutorial_launch_play.dll` shipped as `513c6277c3ae88f3` — the hash CLAUDE.md and the handoff
both name as the FK-7 candidate. **It is one commit behind its own source.** Rebuilding `play` from
HEAD produces `433cf7d8f6a0770f`; the intervening commit `5631d10` adds `PopulateHeroAscCache` /
`ReportAscActorInfo`, and **`KWIREGAS` defaults to `1`**, so that code is genuinely reachable from
RM_PLAY rather than dead.

⇒ Testing `play-funcswap` (built from HEAD) against the *deployed* candidate would have differed in
**two** dimensions. The control was rebuilt from HEAD and the historical artifact preserved as
`build\tutorial_launch_play_a827ef9_ARCHIVED.dll`. One earlier armed window that used `513c…` is
reported separately as a pilot and is **excluded** from the primary comparison.

## 3. ★ The treatment arm is real, not a silent no-op (MEASURED)

The single biggest risk in this design was that a non-`.text` callback mechanism would quietly get
no game-thread dispatches, RM_PLAY would do nothing, and the arm would "survive" for the wrong
reason — the project's dominant error mode. It does not happen:

```
[FS] arm: swapped=17126 BP UFunctions  (scan 3187 ms over 151350 objects, 33816 UFunctions total) -- NO .text WRITE
[FS] *** ARMED AND LIVE: hitsGT=1 allThreadCalls=5 after 8016 ms ***
[FS] t=+30s hitsGT=2269 called=2268 ...
[FS] t=+45s hitsGT=5857 called=5856 ...
```

≈ 240 game-thread dispatches/s once the world settles, and the arm-symmetric positive control
(`[PL] *** init complete ***`) fires in both arms. Binary-level corroboration that no `.text` write
path survives with `KFUNCSWAP=1`: `FlushInstructionCache`, `VirtualAlloc`, `VirtualFree` and the
mutex trio are **absent from the import table**, so `SafeWrite` — the only routine that maps a page
`PAGE_EXECUTE_READWRITE` — was linker-eliminated along with `InstallHook`/`UninstallHook`.

## 4. ★★ Protector kills occur BEFORE the probe exists (MEASURED — not anticipated)

| run | when it died | probe injected? | family |
|---|---|---|---|
| `s112c-ctl-03` | T+0.5 s after `Load map complete …/LVL_Tutorial` | no | OURS/protector |
| `s112c-ctl-04` | T+3.4 s after map load | no | OURS/protector |
| `s112c-ctl-05` | before map load (`route=menu`) | no | OURS/protector |
| `s112-trt-01` | before map load | no | OURS/protector |
| `s112-trt-02` | during deferred travel, `fo` vtable patch still standing | no | OURS/protector |

Only `gft_ready_fix` and `tutorial_launch_fo` were resident. `gft_ready_fix` writes **no module
image at all** (its only write is a heap flag), so the writer is `fo`:

- a **transient ≤8 s `.text`** prologue jmp at `ProcessInternal`, and
- a **≤25.5 s `.rdata`** slot-285 `CustomLogin` patch across 5 vtables.

`s112-trt-02`'s marker ends at `[4] CALLED (called=1 hitsGT=1)` with **no `[5] done (vtable
restored)`** — it died with the `.rdata` patch standing.

⇒ **INFERRED:** the handoff's open question — *"rows 2 and 5 are `.rdata`, not `.text`; S111
measured `.text`; the shim's assertion that `.rdata` is also caught is an S61-era inference that has
never been tested"* — now has evidence on it, and it points at `.rdata` being caught too. This is
**not** a controlled test (the transient `.text` write is confounded with the `.rdata` one in every
run), so it is a lead, not a result. It is also **arm-neutral** and therefore cannot manufacture or
mask a control-vs-treatment difference.

⇒ **This is the part the FK-7 framing did not predict.** "FK-7 is largely our own PI hook" is too
narrow even if the A/B comes out clean: a substantial share of tutorial-route deaths happen before
RM_PLAY's hook exists.

## 5. Instrument errors made and corrected THIS session

Recorded because the project's dominant failure mode is an instrument's blind spot being written
down as a property of the game, and three of these would have done exactly that.

1. **Archived crashpad the instant the PID vanished**, racing the ~44 MB minidump write. A normal
   protector death then reads as "artifact-less" — a different fault class entirely. Fixed: wait
   15 s. One treatment death (`s112c-trt-02`) was lost to this and is **unclassifiable**; it is
   reported as such rather than assigned a family.
2. **Migrated the results CSV while a run was appending to it.** Lost one row outright and blanked
   the `probe_receipt` / `gft_records` columns on six rows. The primary fields survived. The
   authoritative table is rebuilt from the append-only campaign log and per-run directories.
3. **Conflated staging deaths with staging aborts.** `STAGE_FAIL` now means "the force-open lost its
   8 s race, game still alive"; `STAGE_DEATH` means "the game died before the probe went in". They
   are different events and pooling them hid the §4 finding.
4. **`fk8_classify.py` dedupes UECC dumps on the constant `"UEMinidump"`**, so pointing it at the
   crash tree reports **1 distinct report for 105 directories**. Not used; a corrected triage script
   was used instead. (Its protector test is fine — it uses `endswith("runtime.dll")`, so the S111
   `VCRUNTIME140.dll` substring bug is not present.)
5. **A stale PENDING crashpad report survived 11+ launches**, contradicting `archive-crashdumps.ps1`'s
   premise that the next launch clears the database. A new `dumps\crashpad-*` directory is therefore
   **not** evidence of a death. Dedupe by report uuid.
6. **Archive labels confirmed non-authoritative in practice** — `f9a421b3` sits in a directory
   labelled `s112c-ctl-03`… and does in fact belong to `ctl-03`, but only because that run's death
   preceded its own archive call. The label is the *upcoming* run's, not the dump's.

## 6. Corrections to the inherited record

- **`0x3494B40` is animation code.** Verified independently: `strxref func 0x3495973` returns **four**
  literals, including `[PreviousMarker %s, NextMarker %s] : %0.2f` **twice**, plus
  `Ticking Group [%s] GroupLeader [%d]` and `Invalid position from Leader %d` — animation sync-group
  terms throughout. S111's rename to "the tick task-graph dispatcher" quoted 2 of 4 and is wrong;
  S106's `FAnimSync::TickAssetPlayerInstances` **stands**. Only S111's other claim survives:
  `0x3495973` and `0x349596D` are the same function.
- **The stale-marker footgun is real but its stated mechanism is wrong.** `Marker()` is
  `FILE_APPEND_DATA`/`OPEN_ALWAYS`; the truncation is a separate `CREATE_ALWAYS` at
  `tutorial_launch.cpp:6278`, the first statement of `Worker()`. So **`fo` wipes the stale text at
  stage 2**, and a failed `sp` does correctly time out at the stage-3 gate. The genuine hazard is one
  stage earlier: re-running the stager against an already-staged live process makes the world gate
  match the *previous* attempt's `Load map complete` line and sends the one-shot `sp` in blind.
- **`UECC-C13252F5` is not FK-7 evidence.** Independently re-classified: `RIP = SUPERVIVE+0x349596D`
  (`call [rax+0x2F8]`), READ AV at `0xFFFFFFFFFFFFFFFF`, worker thread, chain
  `349596D-3405F13-3691A72` — squarely the **ANIM family**, which S110 measured to be a shim-lifetime
  bug (an `UAnimationAsset` the shim loaded and never kept reachable). It passes every *signature*
  filter and fails a *mechanism* filter. Its "258 s" is the launch clock; anchored to map load it is
  **T+88.8 s**, unremarkable. ⇒ the handoff's "exactly one current-era survivor" does not survive.
- **`KPLAYHOLDMS` and `KNOLOGINVT` did not exist.** Both are named in the handoff as if they were
  `-D` flags. `KPLAYHOLDMS` has since been implemented (variant `play-hold300`); `KNOLOGINVT` has
  not.
- **`docs/inject-watch.out.log` cannot verify tutorial-route injection.** It is written only by
  `launch-redirect.ps1`'s `-Hook` watcher, which a `-NoHook` tutorial launch never runs. The
  injection receipt used instead is the probe's own `CREATE_ALWAYS` marker truncation plus the
  `[PL] init complete` line.

## 7. The residual, and what it is not

Two of ten treatment armed windows still died. **The `.text` patch is not the whole of FK-7.**

- `s112c-trt-10`, arm+260 s, exit `0x0000DEAD`, **no artifact**.
- `s112c-trt-02`, arm+101 s, no artifact (and it predates the exit-code instrument, so its mode is
  unknown -- reported as unknown, not assigned).

Neither is a protector access-violation kill, so neither is the S111 mechanism. What they are is
**OPEN**. Three candidates, none tested:

1. **The treatment's own footprint.** It swaps 17,126 `UFunction.Func` pointers and puts its stub on
   the hot path of all Blueprint execution. That is a large novel surface and it must be named as a
   live alternative explanation for its own residual -- exactly the trap this project keeps falling
   into. The `-DKFSNAME=<name>` knob (swap ONE function instead of thousands) is the cheap next test.
2. **A second protector kill mode** that uses `TerminateProcess(0xDEAD)` instead of corrupting
   execution, triggered by something other than a standing `.text` write.
3. **A genuine game defect.** Possible, and now the *only* remaining route to one -- but with no
   artifact there is nothing to classify, so no evidence either way.

⚠ **Do not read "20 %" as "the game's own FK-7 rate".** The treatment arm still injects four DLLs
and still carries the whole shared staging exposure. **No shim-free tutorial run has ever been made**
-- that was true before this session and is still true after it.

## 8. The arm-neutral staging hazard (MEASURED, and it is large)

**8 of 20 launches that never reached an armed window died during staging**, with only
`gft_ready_fix` + `tutorial_launch_fo` resident and the probe never injected. Every such death that
left a dump is `OURS/protector`. Three carry exit `0xC0000005`.

`gft_ready_fix` writes no module image at all, so the writer is `fo`: a transient <=8 s `.text`
prologue jmp, plus a <=25.5 s `.rdata` slot-285 `CustomLogin` patch across five vtables.
`s112-trt-02`'s marker ends at `[4] CALLED (called=1 hitsGT=1)` with **no `[5] done (vtable
restored)`** -- it died with the `.rdata` patch standing.

⇒ The handoff's open question -- *"rows 2 and 5 are `.rdata`, not `.text`; S111 measured `.text`;
the shim's assertion that `.rdata` is also caught is an S61-era inference never tested"* -- now has
evidence bearing on it. **It is a lead, not a result**: the transient `.text` write is confounded
with the `.rdata` one in every single run, so this does not isolate `.rdata`. The clean test is a
`-DKNOLOGINVT=1` build (which does **not** exist; the handoff cites it as though it were a flag).
That build risks a `Login` fatal during deferred travel, which is why it was not attempted here.

Because it is arm-neutral it cannot manufacture or mask the §0a result. But it does mean
**"FK-7 is our own PI hook" is too narrow**: a large share of tutorial-route deaths happen before
RM_PLAY's hook exists at all.

## 8b. PHASE 2 (2026-08-08) — one question answered, one still untested, one self-inflicted false alarm

### ★★ `KNOLOGINVT` FALSIFIED: the slot-285 `.rdata` patch is STILL LOAD-BEARING

The completion review named `fo`'s <=25.5 s `.rdata` slot-285 `CustomLogin` patch as the leading
suspect for the staging deaths, and the S111 handoff speculated it might be obsolete now that
S107/S108 made the world load reliably. **It is not.** Built `fo-nologinvt`
(`.text b834ff93827654aa`, and rebuilding `fo` reproduced `fa184b20934cc4b0` exactly, proving the
`KNOLOGINVT=0` path inert), then flew it alternating against stock `fo`:

| fo arm | launches | staging deaths | `Load map complete` |
|---|---:|---:|---:|
| `fo-nologinvt` (drops the `.rdata` write) | 4 | **4/4** | **0/4** |
| stock `fo` (keeps it) | 4 | 3/4 | — |

All four `fo-nologinvt` runs die with the **exact fatal the source comment predicted**:
`LogSpawn: Warning: Login failed: ALokiGameMode::Login failed to Login` →
`Couldn't spawn player`. Fisher vs the pooled `.rdata`-present baseline (13/51): **p = 0.0026**.

⇒ **S62's stated purpose stands and the handoff's "maybe it's obsolete now" is falsified.**
⇒ **The `.rdata`-is-also-caught question CANNOT be tested by removal** — the route breaks before the
question can be asked. A different design is needed (e.g. patch and immediately restore, so the
`.rdata` window shrinks without the semantics changing).

### ⚠ My own false alarm, recorded because it is the project's signature error

Phase 2's first 8 launches read **7/8 staging deaths vs phase 1's 8/41** and I called it a step
change. **It was not.** I had pooled two arms while varying one of them — the identical mistake
S111's own summary flags ("the outcome variable was never split by fault family"). Split:
`fo-nologinvt` **4/4** (a genuinely broken route) plus stock `fo` **3/4** (small-sample noise).
Stock `fo` + the repro + phase 1 pool to **13/51 ~ 25 %**, a flat baseline.

Ruled out along the way, each cheaply and each worth keeping:
- **environment** — `-NoHook`, no injection, **3/3 survived 320 s**, independently reproducing
  S111's 0/11 control;
- **the `fo` binary** — deployed vs `build/` differ in **6 bytes**, all PE `TimeDateStamp` /
  debug-directory; functionally identical, so the new `-Fo` plumbing is exonerated;
- **a new ASLR era** — base constant at `0x7FF6505C0000` across both phases;
- **resources** — 8.5 TB free, 23.9 GB RAM free, nothing exhausted.

### ★ Phase 1's primary result independently reproduced

Re-running the exact phase-1 configuration hours later, on a different part of the night:
**`play-funcswap` 4/6 SURVIVED the full 330 s hold, 2/6 lost to staging, 0 armed-window deaths.**
Phase 1's treatment arm was 8/10 survived. Consistent, and it adds 6 launches at an independent time.

### The one-function arm is still UNTESTED

`play-funcswap-one` (`.text 5151621d2154e454`) arms only the UFunctions named `ReceiveTickClient`,
selected from a MEASURED settled-world profile (`BP_LokiHeroCharacter_C::ReceiveTickClient`,
**1549 hits / 90 s ~ 17/s**, once per frame). Widening the attribution window from 4 s to 90 s is what
made a target selectable at all — at 4 s the profile only covers world load, where all candidates
read `hits=1`.

It got **exactly one** arming opportunity and lost it to an injection failure:
`FAILED: VirtualAllocEx(RWX) failed: Access is denied. (ACG on?)`. `Stage-Inject` discards
`inject.exe`'s exit code, so the stager still announced *"probe injected; armed window begins"* — and
**the positive control correctly recorded VOID_ARM rather than scoring it a pass.** That is the
control doing its job, and it is why a quiet control must never be read as a survival.

⇒ **The 2/10 residual remains OPEN and the footprint hypothesis remains untested.**

## 8c. PHASE 3 (2026-08-08) — the footprint arm, matched at 600 s

Both arms held **600 s** (not phase 1's 330 s) so FOOTPRINT is the only variable, and the campaign
alternated on armed windows. Arm labels were renamed (`fs17k` / `fs1`) because the arm name is the
analysis's pooling key and reusing `control`/`treatment` would have silently merged phase 3 into
phase 1's denominator.

| arm | probe | swapped pointers | launches | armed | died |
|---|---|---:|---:|---:|---:|
| `fs17k` | `play-funcswap` (`badecc840bafee84`) | 17,126 | 11 | 8 | **0** |
| `fs1` | `play-funcswap-one` (`5151621d2154e454`) | **2** | 11 | 8 | **0** |

**Fisher two-sided p = 1.0000.** 16 of 16 armed windows survived the full 600 s hold.

### ★★ The one-function arm works, and its footprint is 2 pointers

```
[FS] cfg KFUNCSWAP=1 max=0 name='ReceiveTickClient' ...
[FS] arm: swapped=2 BP UFunctions  (scan 3609 ms over 151330 objects, 33816 UFunctions total) -- NO .text WRITE
[FS] *** ARMED AND LIVE ***
```

**2 pointers, not 17,126** — an ~8,500x reduction — and RM_PLAY still armed, ran, and survived 8/8.
⇒ **This is the shippable form of the non-`.text` hook**, not merely an experimental control.

### ⚠ What this does and does not establish

- **It does NOT test the footprint hypothesis.** 0/8 vs 0/8 cannot discriminate: with zero deaths in
  either arm there is nothing to attribute. The honest statement is that **phase 3 could not
  reproduce the residual at all**, so "the 2/10 residual is the treatment's own footprint" remains
  **untested**, not refuted.
- **It DOES bound the residual far lower.** Pooled across every non-`.text` arm
  (`treatment` + `repro` + `fs17k` + `fs1`): **2/30 ~ 6.7 %**, and both of those two deaths came from
  phase 1's *shorter* 330 s hold. At the longer 600 s hold the count is **0/16**. A longer exposure
  producing fewer deaths is the opposite of a dose-response, which is why the phase-1 2/10 now looks
  like noise rather than a real hazard of the technique.

### ★★★ The primary result, restated on the full corpus

| condition | armed windows | died |
|---|---:|---:|
| **standing `.text` patch** (600 s, RM_PLAY's `ProcessInternal` jmp) | 10 | **10 (100 %)** |
| **no module-image write** (heap `UFunction.Func` swap, 330 s + 600 s) | 30 | **2 (6.7 %)** |

**Fisher's exact, two-sided: p = 0.00000008.**

⇒ The conclusion is unchanged and much stronger: **FK-7 is substantially our own standing `.text`
patch**, and expressing the same hook as a heap write removes essentially all of it — while running
**longer** holds than the ones that killed 10/10 controls.

### Unchanged by phase 3

The **staging hazard**: 6 of 22 phase-3 launches (27 %) died during staging before the probe was
injected, consistent with the ~25 % baseline. `KNOLOGINVT` cannot address it (section 8b), so this
remains the largest open item on the tutorial route.

## 8d. SHIPPED (2026-08-08)

The fix is no longer a build variant behind a flag. **`KFUNCSWAP` and `KFSNAME` now DEFAULT to the
heap swap**, so the tutorial route makes no module-image write at all.

| artifact | `.text` | is byte-identical to |
|---|---|---|
| `tutorial_launch_play.dll` (**new default**, deployed) | `5151621d2154e454` | the arm measured **8/8 SURVIVED at 600 s** |
| `tutorial_launch_play_textpatch.dll` (**rollback**) | `433cf7d8f6a0770f` | the A/B **control**, measured **10/10 DIED** |
| `tutorial_launch_play_funcswap.dll` | `badecc840bafee84` | the 17,126-pointer arm, **0/8 at 600 s** |

**Nothing shipped is a rebuild-and-hope** — each artifact hashes identically to a build that was
actually flown. The rollback being the measured control matters too: reverting lands on a known
quantity rather than an untested path.

### Structural guarantee, not just behavioural

The shipped DLL's import table has **no `FlushInstructionCache`, `VirtualAlloc`, `VirtualFree` or
mutex trio**. `SafeWrite` — the only routine in the file that maps a page `PAGE_EXECUTE_READWRITE`
and memcpys into it — was linker-eliminated along with `InstallHook`/`UninstallHook`. The binary has
no `.text`-patching machinery left to invoke. `verify_dll.py`: **PASS**, KERNEL32+USER32 only, zero
CRT, zero C++ EH.

### Live confirmation on the DEFAULT path

Everything before this measured *experimental* builds passed explicitly by path. The confirmation
runs the **deployed** `tools\sigbypass-mod	utorial_launch_play.dll` exactly as CLAUDE.md's
hands-free recipe reaches it — no `-Variant`, no experimental flag:

```
[FS] cfg KFUNCSWAP=1 max=0 name='ReceiveTickClient' ...
[FS] arm: swapped=2 BP UFunctions  (scan 3438 ms over 151377 objects) -- NO .text WRITE
[PL] *** init complete: body=BUILT; camera + WASD active ***
hero (-65,-1770,393) -> (2911,-1770,441)      SURVIVED 601 s
```

**10 launches, 6 armed windows: 5 SURVIVED the full 600 s, 1 died.**

### ⚠ The one shipped-build death, reported rather than buried

`s112ship-06`, arm+113 s, **`exit = 0x0000DEAD`, no crashpad report, no UECC dir**. The shim was
working normally right up to it (`swapped=2`, `[PL] init complete`, ~30 game-thread dispatches/s at
the last heartbeat). It is **not** a protector access-violation kill — it is the same artifact-less
residual class seen in phase 1.

★ **This takes the `0x0000DEAD` observation from N=1 to N=2** (`s112c-trt-10`, `s112ship-06`). Two
independent runs, weeks apart in experimental terms and on different builds, exiting with the same
non-random sentinel and leaving nothing behind. That is now a reproducible signature rather than a
single oddity — though still small, and still unexplained.

## 8e. THE FINAL FK-7 CORPUS

| condition | armed windows | died | rate |
|---|---:|---:|---:|
| **standing `.text` patch** | 10 | **10** | **100 %** |
| **no module-image write** (all arms pooled: `treatment` 2/10, `repro` 0/4, `fs17k` 0/8, `fs1` 0/8, `ship` 1/6) | 36 | **3** | **8 %** |

**Fisher's exact, two-sided: p = 0.00000007.**

Kill-mode split across the whole corpus: **27 deaths exit `0xC0000005`** (access violation, crashpad
dump, `runtime.dll+1`) — every one of them under a `.text` writer. **2 exit `0x0000DEAD`** (silent,
no artifact) — both under a non-`.text` build. Our own `Stop-Process` exits `0xFFFFFFFF`, measured as
an explicit control, so neither figure is contaminated by the harness.

### Housekeeping that prevents the next trap

`play-funcswap-one` and `play-funcswap-600` were **deleted** — with the defaults flipped they would be
byte-identical duplicates of `play`, and this project has burned live runs A/B-ing an artifact against
a copy of itself. `play-funcswap` now passes `-DKFSNAME=""` explicitly so it remains a genuine +1-dim
arm rather than silently collapsing onto the default.

⚠ **Scope: the MENU route is unconverted.** `mainmenu_refresh_pi8`, `loadout_fix` and `missions_fix`
still install transient `.text` prologue patches. `FsScan`/`FsThunk` in `tutorial_launch.cpp` is the
worked example to port.

## 8f. CLOSURE — no functional regression, and what "closed" means

The shipped build was checked against **CLAUDE.md's own documented success signature**, not just
"did the process stay alive". All five surviving confirmation runs:

```
[PL] *** init complete: body=BUILT; camera + WASD active ***   5/5
PlayAnimation(run, loop) ok / PlayAnimation(idle, loop) ok      5/5   (cycling)
[GCW] (the run AnimSequence garbage-collected)                  0/5   (KANIMREF still holding)
```

⇒ The fix removes the `.text` write **without costing any capability** — the hero still spawns, is
possessed, walks, and animates.

### FK-7 closed against the project's own three-part framing

| | verdict |
|---|---|
| **FK-7 the BELIEF** — "dies in 1–5 min, budget retries" | **CLOSED.** Cause attributed: our own standing `.text` patch. 10/10 vs 3/36, p = 0.00000007. |
| **FK-7 the FIX** — does the route survive? | **CLOSED.** Shipped as default, deployed, byte-identical to the measured arm, confirmed on the documented path, no regression. |
| **FK-7 as a GAME DEFECT** | **Not supported.** 0 qualifying dumps in 82 launches; 28/28 `OURS/protector`. Not *excludable* on this route — see below. |

### What was split out rather than left keeping FK-7 open

- **FK-31** — the staging hazard, 22/82 launches (27 %), now the dominant tutorial-route failure.
- **FK-32** — the `0x0000DEAD` artifact-less residual, 3/36.

Both have a different mechanism, lifecycle and window from FK-7. Keeping them under the FK-7 label
would repeat this project's own recorded error of pooling distinct mechanisms — the same mistake that
produced the phase-2 false alarm recorded in §8b.

### The one caveat that is NOT a task

**"No shim-free tutorial run has ever been made"** is a **structural property of the force-open
route**, not an outstanding item: the map only opens *because* `fo` force-opens it, so such a run
cannot exist here by construction. Consequence — **8 % is our floor, not the game's rate**, and a
tutorial-specific game defect stays unsupported *and* unexcludable on this route regardless of any
further work on FK-31/FK-32.

## 9. Open

- The primary 2×2 and its Fisher's exact p — pending campaign completion.
- Whether `fo`'s `.rdata` window is independently lethal. Testable with a `-DKNOLOGINVT=1` build;
  not built, and it risks a `Login` fatal that would kill the route.
- The treatment arm's own novel failure surface: it swaps 17,126 function pointers and puts its stub
  on the hot path of all Blueprint execution. If its deaths share control's fault family, the
  instrument is a live alternative explanation and must be stated as one.
