# FK-8 · Dimension 4 — THE CRASHPAD CLASS, MINED AS A POPULATION

**Date:** 2026-08-05 · offline analysis only (no launch, no injection, no backend).
**Corpus:** `docs/fk8-crash-corpus.csv` / `.json` (92 UECC rows + 47 crashpad rows) plus direct
re-reads of every raw artifact quoted here. Everything below is tagged **MEASURED** (observed
directly, with the file it came from), **INFERRED** (reasoning on top) or **SPECULATIVE**.
Every negative is scoped to the artifact class it was searched in.

---

## 0. Headline

**MEASURED — all 22 distinct crashpad reports are protector control-flow, and none of them is a
game-code crash.** Sixteen are `runtime.dll + 1` (DEP-execute on the PE header of the manually
mapped protector image) and six are `<64 KB-aligned hidden mapping> + 0x205D` (read from an
unmapped address). The faulting thread is **unnamed in 22/22**, carries **zero
`SUPERVIVE-Win64-Shipping` pointers in the first 4 KB of its stack in 16/16 family-A cases**, and
in those 16 its return address is byte-identical (`KERNEL32.DLL+0x17374`, the
`BaseThreadInitThunk` frame) — i.e. a freshly created thread whose *start address* is
`runtime.dll+1`.

Consequences, in order of how much they change the project's picture:

1. **Every crashpad-class death on the tutorial route (11 of 11) is a protector kill, not FK-7.**
   Runs labelled `tut1` `tut4` `tuta1` `tuta3` `tutr1` `tutr3` `s110itemwatch` `phase2b-void`
   `animref-SUCCESS` all died this way.
2. **The UECC tree was not biasing FK-7 timing after all** — but for a reason nobody had
   established. Adding the crashpad class moves the tutorial-route median from 198 s to 263 s
   (+33 %); removing the packer families from *both* classes puts it back to **198 s (n = 20)**.
3. **★ The command line was never lost.** `CrashContext.runtime-xml` on disk says
   `CommandLineRemoved`, but the **minidump carries a second, un-scrubbed copy of the whole crash
   context in user stream `0x10000`, and it has the real command line — in 84/84 UECC dumps.**
   The corpus's note that "the crashpad class recovers the command line the UECC class strips" is
   therefore **half wrong**: launch provenance exists for **106/106** deaths, not 22.
4. The `handing control over to crashpad` ⇔ no-`UECC-*` anti-correlation, previously 6/6, now holds
   at **0/85 vs 22/22** with a passing positive control (Sentry was armed in 77 of the 85 UECC
   sessions and the death *still* went to CrashReportClient).

---

## A. What the crashpad class actually is

### A.1 Population (MEASURED, re-counted on disk this session)

| quantity | value | note |
|---|---:|---|
| `dumps/crashpad-*` archives on disk | **45** | the brief said 44; a 45th appeared mid-session. The corpus is **live** — re-count, never cite |
| archives containing >= 1 `reports/*.dmp` | **45 / 45** | **there are no empty pre/post-launch sweeps today.** The class the brief anticipated is currently empty |
| `.dmp` files across all archives | **47** | 43 archives hold 1, 2 archives hold 2 (`metadata` `num_records = 2` in exactly those two) |
| **distinct report UUIDs** | **22** | ← the only honest denominator |
| archives per distinct report | 1×1, 18×2, 2×3, 1×4 | filter `report_is_primary == 1` |

**Why the doubling.** Every archive's `ARCHIVE-INFO.txt` says
`trigger : archive-crashdumps.ps1 (pre-launch sweep)` — **45/45**. That string is **hardcoded** at
`configs/archive-crashdumps.ps1:221` and is *not* evidence of how the script was invoked. The real
pattern is visible in the names: a hand-run `-Label <tag>` archive, then an unlabelled one 5–10 s
later from `launch-redirect.ps1`'s automatic sweep of the next launch (`launch-redirect.ps1:307`).
⇒ **`archive_trigger` is inert as a discriminator. Do not use it.**

### A.2 The `-DEATH` label is not a crash key (MEASURED — confirms the corpus gotcha)

7 of the 22 distinct reports sit in an archive whose own label lacks `-DEATH`:
`s109-positive-control`, `tut3-NOSTAGE`, `` (unlabelled), `s110itemwatch`, `phase2-nostage`,
`phase2b-void`, `animref-SUCCESS`. **Filter on the presence of a report, never on the label.**

### A.3 `settings.dat` — 40 B, identical in 45/45

Re-parsed with the correct offsets (`options@8`, `last_upload_attempt_time@16`, `client_id@24`;
S109's `client_id` reading was right, and my first pass at `options` was wrong until I checked it
against the known client id):

```
magic 'sdPC'   version 1   options 0x00000001  (= uploads_enabled TRUE)   padding 0
client_id 38329c00-8411-4469-88c1-3864d94e25db     <- identical in all 45 archives
last_upload_attempt_time = 22 distinct values, each = crash + ~2 s
```

### A.4 `metadata` — 150 B / `num_records = 1` in 43 archives, 284 B / `num_records = 2` in 2

Header: `44 41 50 43 01 00 00 00 <n:u32> …` (`'DAPC'`, version 1). The corpus reports
`crashpad_state = pending` and `upload_attempts = 1` for **22/22**.

⚠ **The S109 hedge stands and I am not lifting it.** `state = 2 ⇒ Pending` remains **UNVERIFIED
for this build**. I looked for an enum-free corroboration and the obvious one is **invalid**:
"there is no `completed/` directory in any archive" proves nothing, because
`archive-crashdumps.ps1` copies `<db>\*` recursively (line 167) *only when `reports/` is non-empty*,
and a `completed/` directory does not exist in the **live** database either
(`…\Loki\.sentry-native` currently holds only `metadata`, `settings.dat`, one `.run` dir and its
lock). That is weak evidence at best. **What is MEASURED and enum-independent:** exactly one upload
was attempted, ~2 s after each crash, in 22/22, and the report survived to be archived every time.

### A.5 `__sentry-event` (MessagePack, not JSON — the brief is wrong on that)

Per report: `event_id`, `timestamp` (UTC, ms), `level = fatal` (22/22), `release Loki@1.0.0.0`,
`environment Release`, `sdk sentry.native.unreal/0.7.6` with `integrations: [crashpad]`, full
`tags` (BuildCL `156430`, BuildTime `2025-12-12T18:46:46Z`, GPU/CPU/OS), `contexts` (`Unreal
Engine`, `gpu`, `device`, `os`, `Security`, **`Crash Info`**), and a `breadcrumbs` array.
`Crash Info` carries `Crash Type`, `IsEnsure/IsStall/IsAssert`, `Crash GUID`, `Process Id`,
`Seconds Since Start`, `Base Dir`, and the **847–905-char command line**.

### A.6 ★ The `.envelope` — nobody has read it, and it is a free session clock

`<runid>.run/00000000-0000-0000-0000-000000000000.envelope`, 317–332 B, three NDJSON lines:

```
{"dsn":"https://149a7ac2a7914150b87ce714fd4d6444@o566896.ingest.sentry.io/5710262"}
{"type":"session","length":205}
{"init":true,"sid":"2669d655-f9e7-4f60-460d-b78726f278c1","status":"crashed","errors":1,
 "started":"2026-08-05T23:14:21.816000Z","duration":321.56,
 "attrs":{"release":"Loki@1.0.0.0","environment":"Release"}}
```

MEASURED across 45 archives: `status = crashed, errors = 1` in **43**; `status = abnormal,
errors = 0, duration = 0` in **2** (both copies of `shimrun2-DEATH`, whose
`Seconds Since Start` is also 0 — the one death where Sentry's session record was never updated).
`duration` is exact: `last_crash − started = 321.56 s` to the millisecond.
⇒ **`duration` is Sentry-init-relative wall time; `Seconds Since Start` is process-relative.**
The two differ by the ~14 s of engine init before Sentry starts.

### A.7 `last_crash` — 27 B, one ISO-8601 UTC timestamp, = the crash + 20–35 ms.

### A.8 `__sentry-breadcrumb1` / `__sentry-breadcrumb2` — **0 bytes in 184/184 files**

Across all 45 archives, both in `<runid>.run/` and in `attachments/<uuid>/`. **NEGATIVE, scoped to
the crashpad archive class:** the ring-buffer breadcrumb files are empty here. The breadcrumbs that
*do* exist live inside `__sentry-event`'s `breadcrumbs` array and are exclusively
`PostLoadMapWithWorld` map transitions (3 per tutorial-route death:
`LVL_Login` → `LVL_LobbyV2_Persistent` → `LVL_Tutorial`, each with a UTC timestamp).

---

## B. Overlap or disjoint — the anti-correlation holds, and it got much stronger

### B.1 Crash-GUID join: **0 / 22**

All 22 `__sentry-event` records carry a `Crash GUID` of the form `UECC-Windows-<32 hex>`.
**None of the 22 has a matching directory** among the 92 in the UECC tree.

**Positive control (mandatory, and it passes):** the same key type self-joins the UECC key set
**92/92**, so the joiner works. The zero is a property of the corpus, not of the join.

### B.2 Wall-clock: the nearest cross-class neighbour is **48 seconds**, and it is a different death

| | crashpad `shimrun2-DEATH` | UECC `4BC8B969…` |
|---|---|---|
| crash (UTC) | 2026-08-04 23:18:59.834 | 2026-08-04 23:18:10.211 |
| PID | 4388 | 37620 |
| ProcessCreateTime (minidump MiscInfo) | 23:18:36 | 23:17:12 |
| Crash GUID | `…8122CEAE46859077EF153FAB46767887` | `…4BC8B9694F2C1A6A188CB8A9E01956AB` |
| log window | 23:18:43 → 23:18:59 | 23:17:59 → 23:18:04 |

Distinct PIDs, distinct GUIDs, distinct process-create times, non-overlapping logs.
⇒ **MEASURED: no single death is represented in both classes.** The corpus is **84 + 22 = 106**
distinct deaths.

### B.3 The log discriminator, at N = 85 vs 22

| key | UECC logs | crashpad session logs (primaries) |
|---|---:|---:|
| `Sentry HandleBeforeCrash Begin` | **0 / 85** | **22 / 22** |
| `handing control over to crashpad` | **0 / 85** | 20 / 22 |
| `=== Critical error ===` | 0 / 85 | 0 / 22 |
| `LogWindows: Error:` + `Fatal error` | 24 / 85 | 0 / 22 |

`HandleBeforeCrash Begin` is the better key (the two crashpad misses are logs cut off mid-flush:
`tutr1-DEATH` and `animref-SUCCESS`, both of which end on
`LogSentrySdk: Verbose: serializing envelope into buffer`).

### B.4 ★ Positive control — this is NOT "Sentry was switched off in the UECC era"

**MEASURED, whole-file scan of all 85 UECC logs (chunked 4 MiB with a 64-byte overlap; total
996 MB):**

```
started crashpad client handler                    77 / 85
Sentry initialization completed                    77 / 85
Using Sentry: Yes                                  77 / 85     ("Using Sentry: No" 0 / 85)
LogSentrySubsystem: Add crash reporter callback    77 / 85
```

The 8 without Sentry are all 50–87 KB logs — the process died before Sentry init (~t+3.5 s).
⇒ **In 77 UECC deaths, Sentry was fully armed with a live crashpad handler, and the death still
went to UE's CrashReportClient.** The anti-correlation is a property of the *death*, not of the era
or the configuration.

### B.5 ★★ The two classes interleave within a single experiment series

MEASURED, 2026-08-05, tutorial route, same day, same recipe:

```
07:23:49 UTC   crashpad  tuta1-DEATH        pid 42216   295 s
07:28:34 UTC   UECC      C13252F5…          pid 49792   258 s   <- "tuta2": no crashpad report
07:33:10 UTC   crashpad  tuta3-DEATH        pid 42192   263 s
```

The UECC session's log runs 07:26:14 → 07:28:27, fits exactly in the gap, contains
`started crashpad client handler`, and contains **no** Sentry crash path.
⇒ **Class membership is decided per death.** Nothing about the build, the flags or the date
predicts it.

### B.6 What *does* predict it (MEASURED, and it is new)

| | UECC real (N=84) | crashpad (N=22) |
|---|---:|---:|
| `CrashType = Assert` | **24** | **0** |
| exception code | `0xC0000005` ×83, `0x80000004` ×1 | `0xC0000005` ×22 |
| fault PC resolves inside `SUPERVIVE-Win64-Shipping.exe` | **46** | **0** |
| fault PC resolves inside `KERNELBASE.dll` (the assert `RaiseException`) | **24** | 0 |
| fault PC in **no** loaded module | **14** | **22** |

**INFERRED mechanism:** UE's assert path (`FDebug::AssertFailed`) and its own SEH filter reach
CrashReportClient without ever handing to crashpad; crashpad's handler wins only for the deaths
where the faulting thread is one UE never created and whose stack UE cannot walk. This is
consistent with every row but is **not** directly demonstrated — I have not read the two handlers'
registration order.

---

## C. Timing — and the bias, quantified twice

### C.1 A uniform, instrument-independent clock now exists for BOTH classes

The minidump **MiscInfo stream (id 15)** carries `ProcessCreateTime`, `ProcessUserTime` and
`ProcessKernelTime`, and it is present in **84/84 UECC dumps and 22/22 crashpad dumps**.
`elapsed = crash_time_utc − ProcessCreateTime` therefore covers **106/106 deaths**.

**Cross-check against the reported `SecondsSinceStart` (n = 97 rows where it is non-zero):**
median difference **+4.1 s**, range +1.4 … +55.3 s — the expected constant offset between process
creation and `GStartTime`. **It also rescues 9 rows where `SecondsSinceStart` reads 0** (7 UECC
os-only rows and crashpad `shimrun2` / `sub-NoMissions-3`), e.g. `shimrun2` = **24 s**, not 0.

Third independent signal for the crashpad class: the envelope's `duration` (§A.6).

### C.2 Distributions (elapsed, seconds)

| route | UECC | crashpad | COMBINED |
|---|---|---|---|
| all | n=84 med **62** (p25 33, p75 263, max 42401) | n=22 med **169** (p25 37, p75 298, max 526) | n=106 med 74 |
| **tutorial** | n=20 med **198** (63 … 3338) | n=11 med **298** (170 … 526) | n=31 med **263** |
| tutorial-attempted | n=18 med 104 | n=2 med 155 | n=20 med 127 |
| menu-login | n=25 med **29** | n=6 med **30** | n=31 med 29 |
| menu-lobby | n=14 med 261 | n=2 med 41 | n=16 med 169 |

**MEASURED bias, stated two ways:**

* Naively — the UECC tree alone reports a tutorial-route median of **198 s**; the artifact-bearing
  population's median is **263 s**. The UECC-only figure understates it by **65 s (−25 %)** and
  misses **11 of 31 (35 %)** tutorial-route deaths.
* Correctly — see §C.3. The naive correction is the wrong one.

### C.3 ★ The bias reverses once the deaths are classified

All 11 tutorial-route crashpad deaths and both tutorial-attempted ones are **family A protector
kills** (§E.5). None of the 7 packer-family UECC rows is on the tutorial route (all 7 are
`route = unknown`, elapsed 6–58 s). Therefore, restricted to **game-code** deaths:

```
tutorial-route, packer families excluded from BOTH classes:
   UECC      n = 20   median 198 s
   crashpad  n =  0
   COMBINED  n = 20   median 198 s      <- unchanged
```

⇒ **MEASURED: every timing conclusion FK-7 drew from the UECC tree is unbiased by the crashpad
class — not because the classes agree, but because the crashpad class contains no game deaths at
all.** Anyone who "fixes the bias" by pooling the two classes will inflate the tutorial-route
median by 65 s with protector kills.

### C.4 A free by-product: CPU time

MiscInfo also gives user/kernel CPU seconds, never before extracted. Example
(`s110itemwatch`, 433 s wall): **user 1201 s, kernel 441 s**. A run that hangs rather than crashes
will show this flat — a cheap hang/spin discriminator for future sittings.

---

## D. The third class — deaths with no artifact at all

### D.1 What the project record actually says (both prior claims are RETRACTED)

* `docs/fk7-crash-settled.md` §4.4 — *"9 tutorial sessions, 4 produced a crash dump, 5 dumpless …
  a second failure mode invisible to every conclusion"* — is marked **❌ RETRACTED IN FULL
  (2026-07-29, S106e)**: 3 of the 5 ran `RM_SPAWNPOSSESS` to `[SP] done step=4` and were shut down
  3–9 s before the commit carrying their own marker; 2 died before the antecedent. Residue split
  out as **FK-25**, an instrument gap.
* `docs/s108-fk24-instrument-corrected.md` R2 — **FK-26** (*"the force-open dies silently ~2 of 3
  times, leaving no UE dump"*) is **REFUTED**: "no `UECC-*` directory" was the instrument's blind
  spot; the dump was in the crashpad database. FK-26 merged into FK-25.

⇒ **The project's best-supported figure before this session is ZERO confirmed artifact-less
deaths.** Both claimed populations were instrument artifacts, and the second was created by the
very gap this dimension exists to close.

### D.2 A new MEASURED window — and it is not reassuring

UE keeps a rolling set of rotated session logs. **MEASURED** on the 10 currently retained
`Loki-backup-*.log` (2026-08-05 19:20 UTC → 2026-08-06 00:02 UTC):

| rotated log (UTC) | bytes | `HandleBeforeCrash` | exit markers | artifact |
|---|---:|---:|---:|---|
| 19.20.31 | 555,708 | 0 | 0 | **none** |
| 19.28.10 | 17,139,870 | 1 | 0 | crashpad `s110itemwatch` |
| 22.34.54 | 277,359 | 1 | 0 | crashpad `phase2-nostage` |
| 22.43.18 | 2,437,171 | 1 | 0 | crashpad `phase2b-void` |
| 22.51.36 | 3,808,985 | 0 | 0 | **none** |
| 22.57.46 | 18,011,541 | 0 | 0 | **none** |
| 23.04.21 | 22,784,215 | 0 | 0 | **none** |
| 23.19.44 | 3,131,236 | 1 | 0 | crashpad `animref-SUCCESS` |
| 23.51.16 | 9,769,702 | 0 | 0 | **none** (ends mid-token: `…[553]L`) |
| 00.02.34 | 304,998 | 0 | 0 | **none** |

**Positive control for "exit markers":** `Loki_2.log`, a known clean quit, ends
`LogExit: Exiting.` + `Log file closed, 07/19/26 02:05:47` — 8 matches. The detector fires. **None
of the 10 rotated logs has a single exit marker.**

**They are not merely un-archived.** MEASURED, read-only, right now: the live crashpad database
`…\Loki\.sentry-native` has **`metadata` = 16 bytes, `num_records = 0`, and no `reports/`
directory at all.** Nothing is pending.

⇒ **6 of 10 recent session terminations produced no artifact in either class.**

### D.3 ⚠ What that number is NOT

**"No crash handler ran" is not the same as "the process crashed."** `configs/phase0-server.ps1`
(lines 79–86) force-kills `SUPERVIVE-Win64-Shipping` under `-KillClient`, and the tutorial workflow
requires killing the game between runs. A `Stop-Process -Force` produces exactly this signature: no
Sentry path, no UE banner, no exit marker, log truncated mid-line.

**This is the third time this inference has been available and the first two times it was wrong.**
I am therefore reporting it as a **bound, not an estimate**:

* **upper bound (MEASURED): 6 of 10** terminations in this window carried no artifact — so at most
  ~60 % of terminations are invisible to the 106-death corpus.
* **lower bound: 0** — every one of the 6 could be a deliberate kill.
* **best estimate: NOT DETERMINED by the available evidence.** (SPECULATIVE, if forced: the
  22.51 / 22.57 / 23.04 trio are 3.8 / 18 / 22.8 MB logs consistent with long sittings, which the
  operator would normally let run, so some are probably real deaths; the 305 KB 00.02.34 log ends
  on `LogPlatformStorefront: Wallet balance` at the menu, which is where a deliberate restart would
  land.)

**The discriminator is cheap and nobody has built it:** have the launcher / `fk24-stage.ps1` write
a one-line `operator-initiated kill at <UTC>` marker before every `Stop-Process`. That converts
this bound into a number, permanently. It is the same fix FK-25 already asks for, applied to the
other end of the session.

⚠ **Denominator caveat:** N = 10 is the *entire* retained window; UE has overwritten every earlier
backup. This cannot be back-computed for the 106-death corpus, and the 10 logs all come from one
evening of one experiment series.

---

## E. What else is in these artifacts that nobody has read

Ordered by how directly each answers an open project question.

### E.1 ★★★ The minidump carries a SECOND, UN-SCRUBBED crash context — user stream `0x10000`

**MEASURED: present in 84/84 UECC minidumps**, 266,240 bytes, UTF-16LE, a complete
`<FGenericCrashContext>` XML (~47,900 chars vs the 42,700 on disk). It is **not** identical to
`CrashContext.runtime-xml`:

```
                     on disk                     embedded in the minidump
CommandLine          "CommandLineRemoved"        " -ini:Engine:[...AccelByteSettings]:BaseUrl=http://localhost:8080 …"
UserName             "None"                      ""
```

⇒ **The real command line is recoverable for 84/84 UECC deaths.** Extracted and clustered, there
are **exactly 3 distinct command lines**:

| SHA1(8) | count | difference from baseline |
|---|---:|---|
| `6f7bd3e9` | **79** | baseline, 847 chars, the standard `launch-redirect.ps1` redirect set ending `-log` |
| `d729dcef` | **4** | + ` 127.0.0.1:7777` before `-log` — the **dedicated-server join** runs (`7AE9830F`, `A84A3CA0`, `CD25F035`, `D06CC55E`) |
| `3b421e70` | **1** | + ` -ExecCmds="net.IgnoreNetworkChecksumMismatch 1"` (`F42EF322`) |

This **corrects the corpus's own gotcha** ("the crashpad class RECOVERS THE COMMAND LINE the UECC
class strips … genuine launch provenance the project believed it did not have"): it is available
for **106/106** deaths, and the UECC copy additionally tags 5 deaths to the DS workstream.

### E.2 ★★ `Threads` in the UECC XML — 4,880 per-thread callstacks nobody has mined

**MEASURED:** 4,880 `<Thread>` elements over 92 crashes (median 54/crash), 4,972 `<CallStack>`
elements of which 4,818 are non-empty, each with `ThreadID`, `ThreadName`, `IsCrashed` and a
module+RVA frame list. Exactly one `IsCrashed = true` per crash.

Crashed-thread names over the 84 real UECC deaths — **an axis the census does not expose**:

```
GameThread 46 · RHIThread 9 · Foreground Worker #1 8 · (unnamed) 7 · FAsyncLoadingThread 5
Foreground Worker #0 4 · Background Worker #5 2 · RenderThread 0 1 · Background Worker #10 1 · HttpManagerThread 1
```

⇒ **38 of 84 UECC deaths are NOT on the GameThread**, including 8 of the 20 tutorial-route ones.
Concrete example — `UECC-Windows-C13252F5…` (the "tuta2" death, tutorial, 258 s), crashed thread
**`Foreground Worker #0`**, 22 frames, 15 distinct `SUPERVIVE-Win64-Shipping` RVAs:

```
0x1153803  0x755524E  0x349596D  0x3405F13  0x3691A72  0x3691704  0x367B462  0xF84697
0xF873B3   0xF8B2BE   0xF9D9BC   0xF87040   0x100C334  0x115ED67  0x115C4B1
```
(then `KERNEL32+0x17374` = the thread entry). **NEGATIVE, scoped:** the sibling `<Registers>`
element is present 4,880 times and **empty 4,880 times** — no register state per thread here; use
the minidump's `ThreadListStream` for that.

### E.3 ★★ `MemoryInfoList` (stream 16) in 22/22 crashpad dumps — the packer's VAD map, offline

44,543 regions in `animref-SUCCESS` alone. This is what resolved the recurring fault address
without a live process:

```
0x7FFD3B400001 -> region base 0x7FFD3B400000  size 0x7000  state COMMIT
                  AllocationProtect EXECUTE_WRITECOPY   Protect READONLY   Type IMAGE
                  and in NO loaded module and NO unloaded module
```

i.e. a **mapped PE image the loader does not know about**, faulted at `base + 1` (its DOS header),
`ExceptionInformation[0] = 8` = a **DEP execute** violation.

⇒ **Open project question this answers:** `deobfimports` currently requires the source process
**alive** to recover the packer's hidden mappings. `MemoryInfoList` in an archived crashpad dump
gives the same region map, with protections, **offline** — 22 snapshots of it already sit in
`dumps/`. UECC dumps do **not** carry stream 16 (0/84), so this is crashpad-only.

### E.4 ★★ `ThreadNames` (stream 24) — present in BOTH classes, and it names the killer

**MEASURED, 22/22 crashpad dumps:** 73–91 named threads per dump; **the faulting thread is
UNNAMED in 22/22**.
**Positive control on the same dump** (`animref-SUCCESS`, 137 threads, 74 named):
`GameThread` = 45588, `RenderThread 0` = 39732, `RHIThread` = 28696,
`FAsyncLoadingThread` = 31740, `Foreground Worker #0` = 50352 — the detector resolves every UE
thread it should. The faulting tid 21080 is simply not in the list.
(63 of 137 threads are unnamed, so "unnamed" alone is weak; combined with §E.5 it is not.)

### E.5 ★★★ The exception records — the whole crashpad class in one table

**MEASURED, all 22 read straight from `MINIDUMP_EXCEPTION_STREAM`:**

| family | n | fault PC | `ExceptionInformation[0]` | stack `[rsp]` | SUPERVIVE ptrs in first 4 KB of stack |
|---|---:|---|---|---|---:|
| **A — `runtime.dll + 1`** | **16** | `0x7FFD3B400001` in **all 16** | `8` = EXECUTE (DEP) | `KERNEL32.DLL+0x17374` in **all 16** | **0** in all 16 |
| **B — hidden mapping `+ 0x205D`** | **6** | `0x…205D`, `PC − 0x205D` 64 KB-aligned in all 6 | `0` = READ | `KERNEL32+0x1BFB0` ×1, a stack address ×5 | 1–2 |

The identical `[rsp]` return address in family A is `BaseThreadInitThunk` — **these are freshly
created threads whose start address is `runtime.dll+1`**. The constant PC across 16 launches over
two days is explained by Windows' per-boot image-base randomisation (the machine was not rebooted);
family A in the older UECC rows shows different bases (`0x7FF8F0400001`, `0x7FF90E000001`,
`0x7FFB9EE00001`).

**Identification is direct, not inferred:** the UECC XML `Modules` list names
`runtime_7ff8f0400000` in `UECC-Windows-61C55551…`, whose `ErrorMessage` is
`EXCEPTION_ACCESS_VIOLATION 0x00007ff8f0400001`. `runtime.dll` is
`Loki/Binaries/Win64/runtime.dll`, 67,511,496 B — the protector.

**Combined packer census (this session; supersedes S109 §11's "11 of 87 = 12.6 %"):**

| class | family A | family B | other |
|---|---:|---:|---|
| crashpad (N=22) | **16** | **6** | 0 |
| UECC real, walked (N=84) | 2 | 5 | 46 game / 24 assert / 6 unmapped-other / 1 exec@NULL |
| UECC degenerate (N=8), from `ErrorMessage`/`frame0_abs` only | 3 | 4 | 1 unclassified |
| **total** | **21** | **15** | — |

⇒ **36 of the 114 artifacts (31.6 %), or 29 of the 106 distinct deaths (27.4 %), are protector
control flow.** That is ~2.5× the previously recorded share, and **all of it on the tutorial route
is in the crashpad class**.

⚠ **Instrument note, corroborating S109's `frame0mod` warning:** `runtime.dll` appears **165 times
across 84 UECC XML `Modules` lists** and in **0 of 22 crashpad minidump module lists** (loaded or
unloaded). Minidump module lists are loader-based and cannot see a manually mapped image — which is
also exactly why 0/106 dumps list any of our shims. `runtime.dll` is a **known-present positive
control for that blind spot**: the zero is the instrument, not the absence.

### E.6 ★ `ProcessVmCounters` (stream 22) and `SystemMemoryInfo` (stream 21) — UECC-only, 84/84

The corpus notes `MemoryStats.*` is populated in exactly the 24 `Assert` rows and 0 in the 60
`Crash` rows. **Those rows are not memory-less** — the numbers are in the dump. From
`UECC-Windows-C13252F5…` (whose XML `MemoryStats.UsedPhysical` is 0):

```
PageFaultCount        4,797,411
PeakWorkingSetSize    5,914,112,000   (5.91 GB)
WorkingSetSize        5,412,958,208   (5.41 GB)
```

⚠ **Scope of confidence:** the header + first three fields are pinned; the tail of the record
(`PrivateUsage` decoded as 87.6 GB) is **implausible, so my field offsets past
`PeakPagefileUsage` are wrong** — `MINIDUMP_PROCESS_VM_COUNTERS_2` has more fields than I laid out
(the record is 152 B). Treat only the three values above as MEASURED. Crashpad dumps carry neither
stream (0/22).

### E.7 `UnloadedModuleList` (stream 14) — crashpad-only, 22/22, 22 entries each

`dxilconv.dll` (4× per dump), `nvwgf2umx` / `NvMessageBus` / `nvgpucomp64` / `NvMemMapStoragex` /
`nvldumdx` (2× each), plus `d3d10warp`, `MDMRegistration`, `omadmapi`, `msvcp110_win`,
`DMCmnUtils`, `tbs`, `OnDemandConnRouteHelper`, `resourcepolicyclient`, `avrt` (10/22). Routine
D3D/driver churn — **no project question is answered by it**, but it is the place to look if a shim
is ever suspected of being unloaded.

### E.8 `crashpad_info` (stream `0x43500001`) — 64 B, and it is EMPTY of annotations

```
version 1   report_id 2432183f-…   client_id 38329c00-…
simple_annotations: size 0, rva 0      <- NO annotations
module_list: size 16
```
**NEGATIVE, scoped to this build's crashpad integration:** there are no crashpad key/value
annotations to mine. Don't look here.

### E.9 `__sentry` / `__sdksentry` inside the UECC XML — 77/92, and NOT what you'd hope

`__sdksentry` = `0.19.1`. `__sentry` is a Sentry context JSON with `contexts` (`Unreal Engine`,
`gpu`, `device`, `Security`) and rich `tags` — `gpu.driverversion.internal 32.0.16.1047`,
`gpu.memory 24142MB`, `gpu.featurelevel SM6`, `ErrorMessage`, `ComputerName ALEXDESKTOP`.
**It carries no `Crash Info` and no command line (0/77)** — §E.1 is the route to that.
**NEGATIVE, scoped:** `BPScriptStack = "None"` in **70/70** non-empty values — no Blueprint VM
frame in any UECC death.

### E.10 `RHI.Breadcrumbs` / `RHI.DRED` — flags, not data (and a trap)

`RHI.Breadcrumbs`, `RHI.DRED`, `RHI.DREDContext`, `RHI.Aftermath` are the literal string `false` in
**84/84**; `RHI.DREDMarkersOnly` is `true` in 84/84. **These are configuration flags. GPU
breadcrumbs and DRED are disabled in this build** — a `grep` that finds them is finding the word
`false`. Real breadcrumb data exists only as **12 `Breadcrumbs_RHIThread_*.txt` files across 10
directories**, all menu-route, and each is at most 4 lines:

```
Breadcrumbs 'RHIThread'
Context 1/2
	00 FRDGBuilder_Execute
	01 Scene
	02 Scene
```

### E.11 ⚠ My own instrument artifact, caught and corrected: `EngineData` / `GameData` are NOT empty

An `ElementTree` element census reported `EngineData` and `GameData` "present 92, non-empty 0".
**That is wrong and it is my parser.** `.text` on an element with children returns only the leading
whitespace node. Both are **containers**: `EngineData` holds `MatchingDPStatus` and the whole
`RHI.*` block; `GameData` holds `__sentry` and `__sdksentry`. Anyone reading a leaf value out of
them will see nothing.

### E.12 Other corrections to the corpus's stated gotchas

* `Misc.IsStuck = true` in **6** dirs with a distinct `Misc.StuckThreadId` each (65204, 30972,
  78216, 95740, …) — a hitch/stall detector nobody has used.
* `NumClients = 0` in 30 dirs; `ReplicationModel = Generic` in 16 — present only for the
  networked/DS-route deaths.
* `CrashReporterMessage` appears **184 times over 92 files** (93 empty + 91 `Attended`) — confirms
  the corpus's first-match-regex warning.
* `MatchingDPStatus = "WindowsClientNo errors"` in 85/85 — inert.

---

## F. What this dimension does NOT establish

* **It does not attribute FK-7.** It removes 22 deaths from the FK-7 candidate pool and adds a
  crashed-thread axis (§E.2); it explains nothing about the remaining 46 in-game faults.
* **It does not prove the routing mechanism.** §B.6 is a perfect correlation across 106 deaths and
  a plausible story; the two handlers' registration order was not read.
* **It does not settle the third class.** §D.2 gives a bound of 0–6 out of 10 in a one-evening
  window with an unknown number of deliberate kills, and the discriminator that would settle it
  does not exist yet.
* **It says nothing about why the minidump upload fails.** Related MEASURED datum that *narrows* it
  and contradicts the "dead project / revoked key" guesses in `s109-fk9-capture-durable.md` §5:
  the session-start envelope POST to the same DSN gets **`HTTP/1.1 200 OK`** from
  `o566896.ingest.sentry.io` (`UECC-Windows-C13252F5…/Loki.log:1110-1123`, `request handled in
  423 ms`). **The project is alive and the key is valid.** The `/minidump/` endpoint is a different
  endpoint and was not tested. ⚠ This raises the residual risk in that document's §5: capture
  depends on the *minidump* upload failing, and the *envelope* upload demonstrably succeeds.

---

## G. Reproduction

Everything here is offline and read-only. Nothing under `Saved\Crashes` or `.sentry-native` was
written, moved or deleted; every file was opened `'rb'`.

* corpus: `tools/crashtri/fk8_corpus.py`, `docs/fk8-crash-corpus.{csv,json}`
* minidump exception / context: `tools/crashtri/mdctx.py`
* one-off parsers written this session (module list incl. unloaded, `MemoryInfoList`,
  `ThreadNames`, `MiscInfo`, `ProcessVmCounters`, user stream `0x10000`, `crashpad_info`,
  `settings.dat`, `metadata`, `.envelope`) — each is ~40 lines and its output is reproduced inline
  above where the numbers matter.

Two layout gotchas that cost time and will cost the next person the same:

* `MINIDUMP_UNLOADED_MODULE_LIST` has a **three**-field header (`SizeOfHeader`, `SizeOfEntry`,
  `NumberOfEntries`) and its name RVA is at **+20**, not +16.
* `MINIDUMP_THREAD_NAME_LIST` is a **u32** count followed by **12-byte** entries
  (`u32 ThreadId`, `u64 RvaOfThreadName`), not 8- or 16-byte ones.
