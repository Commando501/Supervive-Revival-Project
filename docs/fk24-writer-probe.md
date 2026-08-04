# FK-24 — the writer probe

**Question:** *what writes `0x01` into the low byte of `APlayerCameraManager->ViewTarget.Target`?*

Split out of FK-7 on 2026-07-29 (S106e). Governing evidence: `docs/fk7-crash-settled.md` §0.
Ignorance-map entry: `docs/ignorance-map-s101.md` → FK-24.

Every claim below is tagged **MEASURED** (read out of a dump, the source, or a binary) or **INFERRED**.

---

## 1. Status

> ## ✅ READY — 2026-08-03 (S107)
>
> **`tutorial_launch_play_wprobe.dll` (DR mode) is the build to run.** It compiles clean, verifies clean
> (zero C++ exception machinery, KERNEL32+USER32 only, no CRT), reproduces byte-for-byte from this tree,
> and leaves `tutorial_launch_play.dll` **byte-identical** — that last point is measured, not asserted
> (§3).
>
> **`tutorial_launch_play_wprobe2.dll` (page mode) is now also READY.** It was **NOT-READY** at review
> time: two crash-shaped defects (D1, D2) could have left a `PAGE_READONLY` page armed with the handler
> switched off, which kills the process in a way that reads exactly like FK-7. **Both are fixed and the
> DLL is rebuilt.** It remains the *fallback*: do not run it until the DR build returns a VOID verdict.
>
> **Governing reason for READY:** every way this probe can fail to work is *self-announcing in its own
> log*, and each announcement says in words whether it is a **VOID** (the instrument did not run) or a
> **measurement**. The instrument carries an in-session positive control aimed at the exact address in
> question, so "nothing fired" can never be silently recorded as "nothing wrote it".

**Nine defects were found in review and fixed before shipping** (D1–D9, tabulated in
`tools/sigbypass-mod/BUILD.md`). Two were blockers, three were moderate, four minor. The `.text` hashes
in §3 are the **post-fix** set; the earlier `28aa024e…` / `22f37ca8…` / `0ee9f6bb…` artifacts are
superseded and **must not be injected**.

**What is NOT ready / NOT claimed:**

- Zero live runs of this probe exist. Everything below about what it *will* report is INFERRED from the
  source; only the build-time facts are MEASURED.
- The probe does not fix FK-7. It names a writer. `KVTGUARD=1` stays on in every probe variant so the
  session survives the corruption and keeps logging.
- It is not yet known that this build vintage reproduces FK-7 **at all** — the four camera dumps predate
  `KXFORMFIX` (`fk7-crash-settled.md` §0.2a). Run `play-novtguard` once per sitting as that control.

---

## 2. What the probe does

### 2.1 The measurement

`&PCM->ViewTarget.Target` is resolved **by reflection** at runtime
(`PropOffsetSuper(ClassOf(pc),"PlayerCameraManager")` → `"ViewTarget"`, `VtResolve`,
`tutorial_launch.cpp:1055`), with `KVTOFFFALLBACK 0x420` only as a logged fallback. The probe puts a
**1-byte write watchpoint on that address** and reports, for every store that lands on it:

| captured | why it is the answer and not a restatement of the question |
|---|---|
| `tid` (+ is it the game thread?) | the write is MEASURED to happen **outside the camera chain**, so the writing thread is itself unknown |
| `Rip` → **`module + RVA`** | the attribution key; feeds `strxref func` / `vtables.py slotof` offline (§6) |
| **64 bytes at `Rip-64`, 16 at `Rip`** | the writer's page **must** be decrypted at the instant it traps (the CPU just executed it) — so the instruction is recoverable even when it sits in the 47.7 % of `.text` no dump has ever captured |
| **all 16 GP registers, and `reg − PCM` for each** | ★ the other half of attribution: `delta == 0` on some register ⇒ **the store was aimed at this PlayerCameraManager** and `0x420` is the real field displacement; no match ⇒ a computed/indexed address, or a *different* object whose layout puts a byte there (type confusion), in which case the encoded displacement is **not** `0x420` |
| return-address scan (`[rsp .. +512 qwords]`, call-shaped filter) | labelled `HEURISTIC, NOT an unwind`; drops straight into the `crash_census.csv` RVA-chain vocabulary |
| DR0 vs DR0+DR1 | the **hardware** width discriminator (§2.3) |

### 2.2 ★ The retracted `+0x3F` trap is structurally excluded

The previous instrumentation logged `delta = live − corrupt` and read `+0x3F` as confirming "a writer
aimed at this field". That is **arithmetically forced** whenever byte 0 is replaced by `0x01` (the live
low byte is `0x40` in 3/3 observations, *including the clean control*), so it confirmed nothing — an
instrument's artifact built into the instrument meant to settle the question.

**Nothing in this probe reports a property of the written value as evidence of who wrote it.** The
attribution chain is entirely `tid → Rip → RVA → instruction bytes → containing function → which
register held the PCM`. The value at `&Target` is used for exactly **one** purpose — to say *which* trap
was the corrupting one — and the log line says so in-line:

```
*** THIS IS THE CORRUPTING STORE (value used ONLY to pick the trap, never as attribution) ***
```

The `[VTG] … delta=+0x3F` line is left exactly as it is, retained as the **signature match** ("same bug,
not a new one") that FK-7 §0.2 preserved it for.

### 2.3 The replacement discriminator is hardware

`DR0 = &Target`, `DR1 = &Target + 1`, both 1-byte write watches (`DR7 = 0x00110005`: L0+L1, R/W=`01`
write, LEN=`00` one byte — LEN=1 imposes no alignment requirement).

- **DR0 alone fires** ⇒ a **one-byte** store at offset 0 — the measured FK-7 shape.
- **DR0 and DR1 both fire** ⇒ an 8-byte pointer store whose low byte merely happens to be `0x01`.

That is a property of the **writing instruction**, not of the written value, which is exactly what the
retraction demands. **And it is validated against ground truth in-session** (§2.4), so it is never
merely asserted. The summary prints `width-discriminator: VALIDATED` or
`*** NOT VALIDATED -- do NOT read B0/B1 width attribution as measured this run ***`.

### 2.4 ★ The in-session positive control — the single most important design element

A watchpoint that never fires is precisely this project's dominant error mode: an instrument's blind
spot recorded as a property of the game. So the probe proves itself, every launch:

1. **`KWPSELFTEST` (default ON).** Right after arming, `VtGuard` — already on the game thread, already
   reading the slot — issues **two idempotent stores** through it: an **8-byte** store of the value
   already there (expect `B0|B1`), then a **1-byte** store of the byte already there (expect `B0` only).
   Both write back exactly what they read, so neither can perturb the game. Each store is **labelled**
   with a latch consumed by the handler, so a selftest trap is distinguishable from `VtGuard`'s own
   repair store — that labelling is what makes the width discriminator verifiable rather than assumed.
   `WpSelfWatch` declares PASS or FAIL within 8 s of arming.
   *Limitation, stated so it is not over-read:* this proves liveness **on the game thread only**. For
   every other thread the per-thread `Dr7` readback is the only evidence, and it is weaker.
2. **A second control aimed at the exact address, on a known cadence.** MEASURED: `DoPlay` calls
   `DoTopDownCam()` unconditionally on every hook hit (`tutorial_launch.cpp:4951`), and `DoTopDownCam`
   re-asserts the view target via `SetViewTargetWithBlend` **every 3rd hit** (`:3615`) because "the
   manager reverts it each frame" (proven S78/S93). INFERRED: `&Target` should therefore be written on
   a steady cadence in RM_PLAY, giving `nonSelfAtTarget > 0` in a healthy run. The probe **measures**
   this rather than assuming it — that counter is what separates ROW8 from ROW7.

### 2.5 Primary vs fallback, and why

| | **`wprobe` — DR0/DR1 (PRIMARY)** | **`wprobe2` — `PAGE_READONLY` (FALLBACK)** |
|---|---|---|
| Thread coverage | per-thread; **121–140 threads** to arm (MEASURED from the crash dumps' `ThreadList`), re-swept every 250 ms | **process-wide** (it is a VAD property) — every thread, including future ones, zero per-thread work |
| Reads trap too? | no — hardware filters to writes | no (`PAGE_READONLY` faults only on write) |
| Granularity | **exactly 1 byte** | 4 KB page, filtered in software |
| Cost | ~free when it does not fire; ~10–20 ms of background sweep per 250 ms | **not derivable offline** — the PCM is *not* page-aligned (offsets `0x040 … 0xAE0`, MEASURED in 5/5 dumps), so the page carries unrelated allocations |
| Perturbs the experiment? | no | **yes** — it changes frame timing, i.e. the timing of the race being measured |
| Failure mode | **self-announcing**: per-thread `Dr7` readback, re-read every sweep | needs the `SafeWritable` exemption and a trap-storm panic valve |
| Proven in this process? | enumeration + suspend + `GetThreadContext` **yes** (`SafeWrite`, `:538`, does it every launch); `SetThreadContext` on DRs **no** | `VirtualProtect` used ~8× already **yes** |

**Decision: DR primary.** Its failure degrades to a *declared* VOID, never to a false negative. The page
build costs an unknown amount and alters the timing of the very race under study.

**`PAGE_GUARD` is rejected outright, and this is not a preference.** `SafeReadable`
(`tutorial_launch.cpp:321`) returns `false` when `m.Protect & PAGE_GUARD`. Arming `PAGE_GUARD` on the
PCM page would therefore **silently disable `VtGuard` itself** — it would stop reading, stop repairing,
and stop emitting the `[VTG] INVALID` line that the correlation evidence is gated on. The instrument
would destroy the evidence it exists to collect. `PAGE_GUARD` is also one-shot, so it needs the same TF
re-arm dance anyway and buys nothing. The fallback uses `PAGE_READONLY`, and `SafeWritable` (`:745`)
carries an explicit `#if KWPROBE==2` exemption for the probe's own page so `VtGuard`'s repair store is
not skipped while armed.

### 2.6 When it arms, and the one hole

`KWPARMAT=0` (default): the instant `VtResolve()` **first succeeds** — the earliest moment
`&PCM->ViewTarget.Target` exists. A hardware watchpoint costs nothing when it does not fire, so early
arming has no price.

**INFERRED, and load-bearing:** FK-24's original wording said "arm after the body build". That would arm
at the **exit** of the window the writer runs in — `g_plBodyDone` (`:3830`) is the *last* statement of
the one-shot `!g_plInit` block that opens at `:3669`, and the corruption is MEASURED at ~0.15 s after
that block. `KWPARMAT=2` preserves the original wording but is **not recommended**; `KWPARMAT=1` arms at
the top of that block.

**The hole, stated plainly:** arming is asynchronous (a request flag set on the game thread, serviced by
a background thread) and costs ~15–40 ms — a `Sleep` tick plus a Toolhelp snapshot plus ~140 thread
arms. `VtResolve` is reachable only from `VtGuard`, which is gated on hero resolution, so the first
~15–40 ms after the first resolve is unarmed. It cannot be closed without a code change. **It is
self-announcing:** the 2 ms poller reports the first tick the low byte becomes `0x01`, relative to both
the arm and the body build. If the poller sees the corruption *before* the arm, rebuild with
`-DKWPARMAT=1`.

### 2.7 Constraints, all satisfied by construction

- **No C++ exception machinery** — SEH (`__try/__except`) and VEH only. **Verified**: zero
  `__CxxFrameHandler3/4`, `_CxxThrowException`, `__std_terminate`, `_Unwind_Resume`; no CRT import.
- **No `.text` patch** — debug registers and page protection are **data-only**. The ~3–5 min integrity
  check has nothing to find. This is precisely why the probe is viable at all.
- **`ProcessInternal` hook untouched** — still transient, still serialised on
  `Local\SuperviveMissionsPIHook`.
- **Game thread never blocked** — the handler adds a few µs on the faulting thread; sweeps, drain and
  poller run on two dedicated background threads. S81's failure was a **20-second** block, four orders
  of magnitude away.
- **All 23 `RunMode`s preserved** — `RM_FORCEOPEN=0 … RM_PLAY=22`, contiguous (MEASURED at
  `tutorial_launch.cpp:93`). `KWPROBE` defaults to 0, so `play` is unaffected.
- **No file I/O on the trap path** — the handler writes fixed-size records into a lock-free ring
  (1024 entries); a background thread drains and formats at ~4 Hz. The single exception is the
  corrupting event, written **synchronously through a handle pre-opened at arm time** so it survives a
  death that follows it.

---

## 3. Artifact matrix

All under `G:\git\Supervive Revival Project\tools\sigbypass-mod\build\`. Built with clang++ 21.1.6
(`…\Swift\Toolchains\6.3.2+Asserts\usr\bin\clang++.exe`), 0 failures, 0 errors, 0 new warnings at
`-Wall -Wextra` (KWPROBE = 0 / 1 / 2 all checked).

| DLL | Δ vs `play` | mechanism / what it isolates | size | `.text` len | `.text` sha256[:16] | `[WP]` strings | imports vs `play` |
|---|---|---|---:|---:|---|---:|---|
| `tutorial_launch_play.dll` | — | the CANDIDATE, no instrument | 236,544 | 162,816 | `a67239a0d83d9300` | 0 | — |
| **`…_play_wprobe.dll`** | `-DKWPROBE=1` | **PRIMARY.** DR0/DR1 hardware 1-byte write watchpoint, swept over every thread | 256,512 | 174,080 | **`6da63dc0ab9fafed`** | 46 | **+`SetThreadContext`, +`GetSystemInfo`** |
| `…_play_wprobe2.dll` | `-DKWPROBE=2` | **FALLBACK.** `PAGE_READONLY` process-wide write trap on the page holding `&Target` | 254,976 | 174,080 | `0ec5a66b7028623a` | 39 | +`GetSystemInfo` only |
| `…_play_wprobe_noxformfix.dll` | `-DKWPROBE=1 -DKXFORMFIX=0` | DR, on the build vintage that actually crashed (the 4 camera dumps predate `KXFORMFIX`) | 256,512 | 174,080 | `d65fb5f0067a9e1c` | 46 | as `wprobe` |
| `…_play_novtguard.dll` | `-DKVTGUARD=0` | the FK-7 reproduction control (not a probe build) | 232,448 | 159,744 | `7bb7c67e371f3f1e` | 0 | — |

**How to tell them apart** — `.text` sha256, which ignores the embedded filename that made three earlier
"controls" identical to each other:

```bash
python - <<'EOF'
import struct,hashlib,glob
for p in sorted(glob.glob("build/tutorial_launch_play*.dll")):
    d=open(p,'rb').read(); e=struct.unpack_from('<I',d,0x3c)[0]
    n=struct.unpack_from('<H',d,e+6)[0]; sh=e+24+struct.unpack_from('<H',d,e+20)[0]
    for i in range(n):
        o=sh+i*40
        if d[o:o+8].rstrip(b'\0')==b'.text':
            vs,va,rs,ro=struct.unpack_from('<IIII',d,o+8)
            print(f"{p:52s} {rs:7d}  {hashlib.sha256(d[ro:ro+rs]).hexdigest()[:16]}")
EOF
```

**Verified facts about this set (all MEASURED):**

- **`play` is byte-unchanged.** Rebuilding `play` from the probe-carrying source yields `.text` =
  162,816 bytes, sha256 `a67239a0d83d9300` — identical to the pre-probe build. Every probe edit is
  inside a `#if KWPROBE` region.
- **The build is deterministic.** Rebuilding `play-wprobe` reproduces `6da63dc0ab9fafed` byte for byte,
  so the DLL on disk is provably this source.
- **`SetThreadContext` appears only in the DR builds** — an independent, single-dimension confirmation
  that the page build genuinely never touches debug registers.
- **`verify_dll.py` → `VERDICT: PASS`** on all four; imports are `KERNEL32.dll` + `USER32.dll` only.
- All four `.text` hashes are distinct from `play` and from each other.

> ⚠ **Never combine a probe build with `KVTGUARD=0`.** `KVTGUARD=0` compiles out `VtGuard`'s body, so
> `VtResolve` never runs, the arm request never fires, and the probe **never arms and never self-tests,
> silently**. MEASURED: `tutorial_launch_play_novtguard.dll` contains 0 `[VTG]` strings. No such variant
> is registered, and none should be added.

---

## 4. The run procedure

### 4.1 Build and verify (optional — the artifacts already exist and reproduce)

```powershell
cd "G:\git\Supervive Revival Project\tools\sigbypass-mod"
.\build.ps1 -Name tutorial_launch -Variant play-wprobe            # PRIMARY  (DR)
python .\verify_dll.py .\build\tutorial_launch_play_wprobe.dll    # must print  VERDICT: PASS
```

### 4.2 Run

**Steam must already be running**, or login dies with `Auth Failure 14005`.
**ELEVATED PowerShell**, from the repo root:

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\launch-redirect.ps1 -Hook tools\sigbypass-mod\build\tutorial_launch_play_wprobe.dll
```

`-Hook <path>` injects exactly that one DLL and no secondaries. The script blocks until the game exits.

**Second terminal** (read-only, safe any time):

```powershell
cd "G:\git\Supervive Revival Project"
.\configs\shim-status.ps1 -Watch
```

### 4.3 Timing — what to expect and how long to wait

| | |
|---|---|
| arm | automatic, at the first successful `VtResolve()`. No key to press, no wall clock. |
| selftest verdict | within **8 s** of arming — `[WP] selftest *** PASS ***` or `*** FAIL ***` |
| the event of interest | ~0.15 s after the body build; historically **T+173…194 s** from launch (MEASURED across the 4 camera dumps) |
| hold | `KWPHOLDMS=0` = stay armed for the whole RM_PLAY hold (**600,000 ms**, `tutorial_launch.cpp:6195`) |
| census | a `[WP] census t=+Ns …` line every 30 s — this is your fallback if the process dies |
| when to stop | let it run past T+200 s at minimum. Exiting before then wastes the launch. |

### 4.4 The marker file — ★ copy it off after every launch

`G:\git\Supervive Revival Project\docs\tutorial-launch-marker.txt`

`Marker()` opens with **`CREATE_ALWAYS`** (`tutorial_launch.cpp:22`, `:4919`), so **every injection
truncates it**. That is FK-25, and it has already cost one multi-agent investigation. Copy the file
after each launch or the run is unattributable:

```powershell
Copy-Item "G:\git\Supervive Revival Project\docs\tutorial-launch-marker.txt" `
          "G:\git\Supervive Revival Project\docs\fk24-run-$(Get-Date -f yyyyMMdd-HHmmss).txt"
```

### 4.5 ★ Read the instrument BEFORE the result

In this order. Steps 1–4 decide whether the run is worth reading at all.

1. **`[WP] FK-24 … COMPILED IN (KWPROBE=1)`** — present? If not, you injected the wrong DLL.
2. **`[WP] target &VT.Target=0x… (pcm=0x… +0x420 reflection)`** — the word `reflection`. A
   `FALLBACK-CONSTANT` here invalidates **every** offset-derived conclusion in the run.
3. **`[WP] arm sweep#1 … dr7ReadbackZero=`** — non-zero ⇒ **W1 VOID**, the DR write did not stick on
   those threads. Also read `busySkipped=` (threads we deliberately did not clobber) and
   `preexistingDR=`.
4. **`[WP] selftest *** PASS ***`** — **no PASS ⇒ ROW6, the whole sitting is VOID. Stop and fix the
   instrument; do not spend launches.**
5. **`[WP] POLL saw the corrupt shape … t=+Nms after arm`** — a small `N` means the arm was late;
   rebuild with `-DKWPARMAT=1`.
6. **`[WP] *** TRAP … *** THIS IS THE CORRUPTING STORE ***`** — the answer. Run the `wpattrib.py`
   command line the record prints (§6). Check `width: B0 ONLY` (the measured FK-7 one-byte shape) and
   `base-match` (`delta 0` ⇒ the writer held a `PCM*`).
7. **`[WP] VERDICT:` / `[WP] NEXT:`** — the one-line reading, and the specific next action.
8. **If the log ends with no `[WP] SUMMARY`**, the process died: read the last `[WP] census` line and
   the death timestamp. **A death shortly after `arm sweep#1` is the packer reacting to debug
   registers, not FK-7** (§7).

### 4.6 How many launches — ★ a quiet launch is NOT evidence

**MEASURED:** the camera bug fires roughly **1-in-2 to 1-in-3 per launch** (`fk7-crash-settled.md`
§0.2). So `P(all quiet | N) = (1 − 0.33)^N`:

| N launches | 3 | 4 | **6** | 8 |
|---|---|---|---|---|
| P(never reproduces) | 30 % | 20 % | **9 %** | 4 % |

> ### Budget **≥ 6 launches**.
> A single quiet run proves nothing about the bug. But **every** launch — quiet or not — emits the
> selftest and the trap census, so every launch is informative *about the instrument*. That is the whole
> point of building the positive control into the mechanism instead of asserting it.

Also run **`play-novtguard` once** during the sitting, to establish that this build vintage reproduces
FK-7 at all. Run **`play-wprobe-noxformfix`** only after `play-wprobe` has produced instrument-valid
launches.

**Escalate to `play-wprobe2` only on a VOID verdict — never on a clean negative.**

---

## 5. Outcome interpretation — every possible log ending

Rows are ordered by evidential strength. The `[VTG] *** INVALID` line is the gate: per FK-7 §0.7, no
criterion may rest on the absence of a bad outcome.

`nonSelfAtTarget` = traps at `&Target` whose RIP was **not** inside this DLL. It appears in the
`[WP] SUMMARY` line and is what the rows key on.

| # | verdict line | selftest | `[VTG] INVALID` | trap | what it means | confidence | next |
|---|---|---|---|---|---|---|---|
| **1** | `ROW1 ANSWER` | PASS | YES | **corrupting store trapped** | ★ **THE ANSWER.** The writer is named: RVA + instruction bytes + which register held the PCM. | **MEASURED** | §6 on the printed RVA. Then re-run once to confirm the RVA **repeats** — a one-shot RVA is a lead, not a cause. |
| **2** | `ROW5 VOID-MISSED (subsumes ROW2 SELF-ONLY)` | PASS | YES | traps, but **`nonSelfAtTarget == 0`** | ★ **VOID, NOT A NEGATIVE — the important row.** The instrument is *proven live on the game thread*, the corruption happened, and not one non-self store to `&Target` was trapped. | strongest possible negative-shaped result | 1) `voidTids>0` / `busySkipped>0` / a `W2` line ⇒ the DR path is partially defeated → **`-DKWPROBE=2`**. 2) else `-DKWPSWEEPMS=50` and re-run once. 3) if it repeats with full coverage, the write was not a user-mode CPU store from an armed thread — the `[WP] POLL` line still bounds *when* it happened. |
| **3** | `ROW1` with `tid != gameTid` | PASS | YES | corrupting, **on a worker thread** | Consistent with the MEASURED "the write happens outside the camera chain". A worker writing a game-thread-owned camera field is itself a finding — likely an async task on a stale or mis-typed pointer. **This is the outcome the evidence most predicts**, and it is why the per-thread sweep is mandatory rather than a nicety. | **MEASURED** | As row 1, plus: cross-check the `ret-scan` chain against `tools/crashtri/crash_census.csv`'s ANIM-family chains. A match ties FK-24 to the worker-thread family. |
| **4** | `ROW4 TRAPS-BUT-UNCORRELATED` | PASS | YES | non-self traps at `&Target`, none corrupting | Traps fired; none carried the `0x40 → 0x01` transition. The corrupting store was missed. | weak | Re-read each trap's `target-before` / `target-now`; the corrupting one is where the low byte becomes `0x01`. If none shows it, treat exactly as row 2. |
| **5** | `ROW6 VOID-INSTRUMENT` | **FAIL** | any | any | **VOID — the instrument never worked.** Says nothing whatsoever about the writer. | none | Read `dr7ReadbackZero` per sweep. All zero ⇒ the packer clears DR (the anticipated failure) → `-DKWPROBE=2`. Non-zero but no selftest trap ⇒ the VEH is not seeing `0x80000004`: check `CrashVEH` is still registered first (`:4924`). |
| **6** | `ROW8 CLEAN-BASELINE` | PASS | **NO** | `nonSelfAtTarget > 0` | **The launch did not reproduce the bug.** Healthy: the watchpoint works and `&Target` was written only by legitimate writers. | **MEASURED** about the *baseline* | Record those RVAs as the **control set** — they are what makes a future RVA "novel". **RE-LAUNCH.** |
| **7** | `ROW7 NO-REPRO` | PASS | NO | nothing but our own stores | No corruption, and no legitimate non-self writer seen either. Not evidence about the writer, the fix, or the probe. | none | RE-LAUNCH. If this repeats across the sitting, the second positive control (§2.4 item 2) is not firing — worth investigating on its own. |
| **8** | any, with `origin=OUT-OF-MODULE` | any | any | trap outside the game module | The writer is in another DLL, in **our own shim**, or in a packer-hidden private exec region. ★ Self-suspicion is free here and has never been tested. | **MEASURED** | `wpattrib.py` prints "NOT in .text". `usmapdump dumpimage` already dumps private exec regions outside the module, so even packer code is capturable. |
| **9** | — | any | `[VTG]` fires in **bursts of hundreds** | any | Not a stray store: either the writer re-corrupts every frame, or `VtGuard` is writing into a torn-down PCM. | — | FK-7 §0.5 stop rule: **revert to `novtguard` and stop.** Do not interpret probe output from a burst run. |
| **10** | — | any | any | death at a fixed unmapped RIP in the `0x7FF90E000001` family | **Integrity kill — run VOID.** RM_PLAY holds its PI patch for 600,000 ms against a ~285 s observed kill latency. | — | Shorten the hold to ~T+220 s and re-run. Do not reinterpret. |

### 5.1 VOID detectors — each says in words that it is a VOID

Every line below is emitted verbatim by the shim. None of them can be mistaken for a measurement.

```
[WP] *** W1 VOID: N/M threads read Dr7 back as ZERO -- the DR write did NOT stick on them.
     A zero readback is VOID, NOT a negative. Escalate to -DKWPROBE=2. ***
[WP] *** W2: N thread(s) had our Dr7 bits CLEARED BY SOMETHING ELSE since the last sweep
     (the packer polls DR). Coverage for that window is VOID, not negative. ***
[WP] *** N thread(s) were ALREADY using our DR slot pair for something else -> NOT armed
     (we never clobber). Those threads are UNWATCHED: a quiet result is VOID for them. ***
[WP] *** W5 CAVEAT: the sweep immediately before the corruption armed N NEW thread(s) --
     coverage was not established at that instant ... ***
[WP]   correlate: *** NO CORRUPTING TRAP recorded before this [VTG] INVALID (val=0x…)
     -- THE PROBE MISSED THE WRITER (VOID, not a negative) ***
[WP] selftest *** FAIL: no trap 8000 ms after arming -- the watchpoint is VOID on the game
     thread. READ NOTHING ELSE IN THIS RUN AS A NEGATIVE. ***
[WP] *** INSTRUMENT SUSPECT: N trap(s) arrived with CONTEXT_DEBUG_REGISTERS ABSENT ... ***
[WP] width-discriminator: *** NOT VALIDATED -- do NOT read B0/B1 width attribution as
     measured this run ***
[WP] arm PAGE_READONLY *** V1 VOID -- NEVER ARMED (protection restored) ***      (page mode)
[WP] *** V4: page protection at DISARM reads 0x… -- coverage for part of the window is UNKNOWN ***
[WP] *** TRAP STORM N/s > 200000 -> DISARMED (V6: the write window may not have been covered) ***
```

### 5.2 ★ An outcome the table has no row for: an Angelscript writer

If the writer is **Angelscript**, `Rip` lands inside the AS bytecode interpreter — the RVA names the VM,
not the culprit, and `ret-scan` shows VM frames. Given that drop phase, respawn and bot spawning are
known to be script (`memory/supervive-angelscript-layer`), this is live. `base-match` would still be
informative. **An RVA that resolves to the AS interpreter is a redirect, not a dead end:** pivot to
`tools/asdump` and grep `docs/angelscript-*.md` for camera / view-target boolean writes.

---

## 6. Resolving the captured RVA to a function name, offline

The trap record **prints the exact command line**, so nothing has to be reconstructed:

```powershell
python "G:\git\Supervive Revival Project\tools\crashtri\wpattrib.py" 0x<rva> --conv after `
       --bytes-at 0x<rva-64> --bytes "<the 64 bytes the probe logged>"
```

`--conv` is **required and has no default**, because getting it backwards misnames the writer by one
instruction. The probe prints the matching token on every trap line:

| mode | exception | `Rip` points at | token |
|---|---|---|---|
| DR (`wprobe`) | `STATUS_SINGLE_STEP` — a **trap**, the store has retired | the **next** instruction | `conv=RIP-IS-AFTER` → `--conv after` |
| page (`wprobe2`) | `0xC0000005` — a **fault**, the store has not executed | the **faulting** instruction | `conv=RIP-IS-AT` → `--conv at` |

`wpattrib.py` runs the whole chain in one call. Verified working this session (both a negative control
on `0x3C5DC52`, the known *consumer*, and a synthetic positive control that recovered
`C6 83 20 04 00 00 01  mov byte ptr [rbx+0x420], 1` exactly).

The individual steps, if you want them separately:

```powershell
cd "G:\git\Supervive Revival Project\tools\strxref"
python strxref.py func 0x<rva>          # exact .pdata extent + every string literal the function touches
python vtables.py slotof 0x<entry>      # is it a virtual, and of what class
```

Verified live this session:

```
$ python strxref.py func 0x3C5DC52
entry   0x3C5DC45   [.pdata EXACT]
extent  0x3C5DC45 .. 0x3C5DC60 (27 bytes) -- EXACT (minidump stream 13, 70 tables)

$ python vtables.py slotof 0x3C5DBC0
slot 312  of 0x07EC5B88  APlayerCameraManager
```

Then check `docs/symbols.csv` (683 rows) for a prior recorded name at that extent.

### 6.1 ★ If the RVA is in the 47.7 % of `.text` that never decrypted

**INFERRED, directly from the demand-decrypt model:** the writer's page **must** be decrypted at the
instant it traps, because the CPU just fetched and executed that instruction. So:

1. **The probe's 64-byte live capture is guaranteed to succeed** even for a page that is all-zero in
   every dump we own. That is why the bytes are in the record: it converts "an address in a zero page"
   into "the writer's machine code, in the log file". Pass them with `--bytes`.
2. A fresh `usmapdump dumpimage` **from that same game state** would now decrypt the page, and
   `mergedumps` folds it into `merged.dump.exe` permanently — so the *next* run of this probe gets full
   naming for free. Constraint: `mergedumps` rejects a different-ASLR-base dump, so it must be the same
   launch's base.
3. Even with no bytes and no fresh dump: an arbitrary `.text` RVA still has **55.3 %** odds of an exact
   `.pdata` extent (MEASURED, sampled 4,000 random RVAs), and **6.4 % of `.text` has exact bounds but no
   bytes** — bounds usually survive when bytes do not, because they come from minidump stream 13 across
   70 crash processes, a source independent of decryption.

**Honest failure modes, which `wpattrib.py` prints on every run:** `slotof` returns "appears in NO
vtable" for non-virtual functions, and `func` returns "no string references" for leaf functions.
**Neither is a negative result** — at 52.29 % decryption a zero-xref answer never proves absence.

---

## 7. Risks, abort, rollback

| risk | rating | mitigation / how it shows up |
|---|---|---|
| Suspending ~140 threads 4×/sec for a whole session | **LOW** | One thread at a time; between `SuspendThread` and `ResumeThread` the only calls are `Get`/`SetThreadContext` — kernel calls taking no user-mode lock. Precedent: `SafeWrite` (`:538`) already mass-suspends in this process every launch. |
| **The packer *terminates* on non-zero debug registers** (rather than merely clearing them) | **MODERATE — the one genuinely unbounded risk** | Not mitigable; it is why the page fallback exists. **Distinguishable by timing:** the run would die shortly after `[WP] arm sweep#1`, ~150 s *before* the FK-7 band. Stated in advance so an early death is not misread as FK-7. → `-DKWPROBE=2`. |
| VEH `CONTINUE_EXECUTION` on a path that is not ours | **LOW** (was MODERATE) | Fixed in review: D3 (disarm ordering + 2 s grace window) and D4 (`EFlags.TF` discriminator when `Dr6` is unreadable, residue counted and declared instrument-suspect). |
| Page armed with handler off (page mode) | **was HIGH, now fixed** | D1/D2. The arm flag and pend table now precede `VirtualProtect`; a failed readback **restores protection** before giving up; the readback tests *coverage*, so a coalesced region is a valid arm, not a spurious VOID. |
| Added frame cost | **LOW** (`wprobe`) / **UNKNOWN** (`wprobe2`) | DR: only `&Target` writes trap, ~5–10 µs each on the faulting thread — far below any perceptible cost, and four orders of magnitude off S81's 20 s block. Page: not derivable offline (the PCM is not page-aligned), which is why `KWPMAXTPS` exists and why the panic valve is mandatory. |
| Integrity check vs `VirtualProtect` | **LOW** | The page is a heap page (the PCM's own allocation), not `.text`. Data-only; no code patch to find. |
| Trap storm degrading the game | **LOW** | `KWPMAXTPS=200000` / `KWPMAXTRAPS=5000000` panic valve → immediate disarm + `[WP] *** TRAP STORM …` line. Page mode only, correctly. |
| Losing the answer to a process death | **LOW** | The corrupting event is written **synchronously through a pre-opened handle** and survives a following death; plus a `[WP] census` line every 30 s. |

### 7.1 Abort

- **In-run, by design:** the panic valve disarms automatically and says so. `KWPHOLDMS=<ms>` auto-disarms
  and prints the verdict early. Both restore all state.
- **In-run, by hand:** close the game. `WpShutdown` disarms (hardware first, flag last, 2 s grace) and
  prints `[WP] SUMMARY(final)` + `[WP] VERDICT:`. If the process is killed instead, DR registers die
  with their threads and page protection dies with the address space — **nothing persists** either way.

### 7.2 Rollback

The probe is **additive and compile-time gated**. There is nothing to undo:

- Inject `tools\sigbypass-mod\build\tutorial_launch_play.dll` instead — MEASURED byte-identical `.text`
  to the pre-probe candidate (`a67239a0d83d9300`).
- Nothing is written to disk except the marker file. No hosts/cert changes. No `.text` patch anywhere,
  ever — that is the design constraint the whole probe is built around.
- `git checkout -- tools/sigbypass-mod/tutorial_launch.cpp tools/sigbypass-mod/build.ps1
  tools/sigbypass-mod/BUILD.md` removes the source changes; `play` rebuilds to the same hash either way.

### 7.3 A free pre-step before spending any launch

**~20 min, zero launches:** differential thread-stack analysis across the 4 camera dumps versus the
clean control `FF9CF623`, using `tools/crashtri/mdctx.py`. The prior census counted threads and RIPs but
never **diffed the stacks**. A frame present in 4/4 camera dumps and absent from the control names a
candidate subsystem. Weak — the write precedes the fault by ~0.15 s, so the writer may have moved on —
so it is a lead generator, not an answer. Also grep `docs/angelscript-*.md` for view-target / camera
boolean writes (§5.2).

---

## 8. Files

| | |
|---|---|
| shim source | `G:\git\Supervive Revival Project\tools\sigbypass-mod\tutorial_launch.cpp` |
| build | `…\tools\sigbypass-mod\build.ps1` · `BUILD.md` · `verify_dll.py` |
| artifacts | `…\tools\sigbypass-mod\build\tutorial_launch_play_wprobe*.dll` |
| offline attribution | `…\tools\crashtri\wpattrib.py` · `…\tools\strxref\strxref.py` · `…\tools\strxref\vtables.py` |
| governing evidence | `…\docs\fk7-crash-settled.md` (§0) |
| ignorance map | `…\docs\ignorance-map-s101.md` → FK-24 |
| marker output | `…\docs\tutorial-launch-marker.txt` (⚠ truncated on every injection — FK-25) |
