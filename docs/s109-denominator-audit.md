# S109 — the denominator audit: how many deaths are actually in the record?

**Date:** 2026-08-04 · **Scope:** OFFLINE ONLY. No game launched, no injection, no live process, no
file in `.sentry-native/` or `Saved/Crashes/` modified. Every command below is a read.

**Why:** the project's crash-forensics instrument (`tools/crashtri/harvest.py`, and every hand-rolled
`Get-ChildItem Saved\Crashes`) enumerates `UECC-*` directories. S108 found a second, entirely separate
death channel — Sentry's **crashpad** handler — that writes its minidump into the game directory and
**no `UECC-*` dir at all**. Consequence: every claim of the form *"N of 87 dumps show X"* has a
denominator that silently excludes a whole failure mode.

Every claim is tagged **MEASURED** / **INFERRED**. Every negative result carries the instrument's
blind spot next to it.

---

## ★ HEADLINE — four results, in order of how much they change

1. **MEASURED — the grep key works, but the corpus it can be applied to is 13 sessions, not 87.**
   The anti-correlation between `handing control over to crashpad` and the existence of a `UECC-*`
   dir is **perfect (0 off-diagonal) on every session where both are observable** — but that is only
   **12 deaths**, because UE purges its own archived session logs and only ~1 day of them survive.
   Fisher one-sided p = **0.152**: the *statistics* are weak at n=12. What carries the result is the
   *mechanism* (§1.4), not the count.

2. **★ MEASURED — grepping the `UECC-*` dirs' own `Loki.log` for the key is a VOID instrument, and
   its answer (0 of 80) is guaranteed by construction.** The `Loki.log` inside a crash dir is a
   **byte-exact PREFIX** of the full session log, truncated **before** the terminal block. Verified
   sha256-identical on 2 of 2 matched pairs. It contains neither terminal signature — not the
   crashpad handoff and not UE's own `=== Critical error: ===` (0 of 80, even for the dir whose
   full log has it). **Do not classify deaths from crash-dir logs.**

3. **★★ MEASURED — in the only window where both channels are observable (2026-08-03 21:52 →
   2026-08-04 14:10, 13 sessions), `Saved\Crashes` captured ONLY the instrument's own exceptions and
   NONE of the real game deaths.** 7 genuine tutorial-sitting deaths → crashpad, zero `UECC-*` dirs.
   The **only 2** `UECC-*` dirs produced in that entire window are `166396E2` and `FED1F952` — the
   two FK-24 watchpoint-probe self-kills that §4 says must be purged from any FK-7 tally.
   **This is not a universal regime** — the 07-26 FK-7 crashes demonstrably *did* produce `UECC-*`
   dirs. Something changed between 07-26 and 08-03 and it is **OPEN** (§5).

4. **★ MEASURED — two independent denominator defects in `crash_census.csv` itself**, both of which
   inflate every "N of 86/87" figure:
   - a **phantom row `_0000`** — a `CrashReportClient` crash, `ProcessId=0`, `SecondsSinceStart=0`,
     empty `EngineVersion`, **0-byte `UEMinidump.dmp`** — counted as a dump in every tally since
     2026-06-29;
   - **7 of the 88 crash dirs have no usable minidump at all** (0-byte or absent), so the true dump
     count is **81**, not 87.
   ⇒ **"5 of 86 dumps capture an `APlayerCameraManager`" should read "5 of 79".** The numerator 5 is
   independently **REPRODUCED** here (§3.3); only the denominator was wrong.

---

## 0. Exact instruments used, and their blind spots

| # | instrument | exact key / method | blind spot, stated up front |
|---|---|---|---|
| I1 | crashpad-death classifier | whole-file byte count of the literal `handing control over to crashpad` (Python `bytes.count`, **not** a `tail`/last-line check) | only applicable to a **full session log**; in the live `Loki.log` the key is at line 52508 of 52510 with two lines after it, so any tail-anchored check false-negatives on exactly the most important session |
| I2 | UE-crash-handler classifier | whole-file count of `=== Critical error: ===`, corroborated by `FPlatformMisc::RequestExit(1, LaunchWindowsStartup.ExceptionHandler)` | same |
| I3 | clean-exit classifier | `LogExit: Preparing to exit.` **and** `LogExit: Exiting.` **and** `Log file closed,` | a log copied mid-session has none of these and is **not** a death (§2.2) |
| I4 | session↔crash-dir matcher | line 1 of every UE log, `Log file open, MM/DD/YY HH:MM:SS` (**LOCAL** time; all in-body `[…]` timestamps are **UTC**) | second resolution; **coverage** failure of 97.7% (§1.3) — not a precision failure |
| I5 | crash-dir enumeration | `for d in Crashes/*` — **NOT** `UECC-*` | ★ my own first pass globbed `UECC-*` and missed the `_0000` dir. Recorded here because it is the identical blind spot this audit exists to clean up |
| I6 | minidump PCM scan | for each `UEMinidump.dmp`: parse the minidump ModuleListStream for the real image base, search the whole file for the qword `base + 0x07EC5B88`, then VA→file-map `+0x420` and `+0x460` via the Memory64List | finds only PCMs whose **first 8 bytes** are in a dumped range; does not prove absence of a PCM elsewhere in the process |

**★ The trap in the key itself.** `crashpad` on its own, case-insensitively, is a **useless** key: it
matches **3 times in every session including clean exits**, because Sentry logs
`starting crashpad backend with handler "…crashpad_handler.exe"` and `started crashpad client handler`
at startup. MEASURED: `cp_any` ≥ 3 in **16 of 16** logs scanned, including `Loki_2.log` (a clean exit)
and the 2026-06-27 logs. The discriminating key is the **full string** `handing control over to crashpad`.

**Positive control for the crashpad instrument, run before believing any absence.** Every one of the
16 logs — 2026-06-27 through 2026-08-04 — contains `starting crashpad backend` **and**
`started crashpad client handler`. ⇒ **crashpad was armed and running in 16 of 16 sessions.** An
absent handoff line therefore means "this death did not go through Sentry", not "Sentry was not there".

### 0.1 Commands

```bash
# corpus enumeration (note: * not UECC-*)
ls -1 "/c/Users/eastr/AppData/Local/SUPERVIVE/Saved/Crashes/" | wc -l            # 88
ls -1 "/c/Users/eastr/AppData/Local/SUPERVIVE/Saved/Logs/"                       # 26 entries, 16 Loki* logs

# the void instrument (see §1.2) — 0 hits, and the 0 is meaningless
cd "/c/Users/eastr/AppData/Local/SUPERVIVE/Saved/Crashes/"
for d in UECC-*; do grep -qa "handing control over to crashpad" "$d/Loki.log" && echo "HIT $d"; done

# proof the crash-dir log is a truncated byte-exact prefix
N=$(stat -c%s UECC-Windows-166396E2…/Loki.log)
head -c $N "…/Logs/Loki-backup-2026.08.04-03.49.21.log" | sha256sum   # == sha256sum of the snapshot
tail -c +$((N+1)) "…/Logs/Loki-backup-2026.08.04-03.49.21.log"        # <- the whole crash tail lives here
```

Python driver scripts (scratchpad, not committed): `audit.py` (whole-file key counts over every log),
`match.py` (I4 matching), `pcmscan.py` / `pcm7.py` (I6). Python
`F:\Program Files\Tools\Python313\python`.

---

## 1. DELIVERABLE A — verifying the grep key

### 1.1 The result, on the corpus where it can actually be evaluated

**MEASURED.** 16 `Loki*.log` / `.bak` files exist in `Saved\Logs`. After removing 1 duplicate
(the `.sentry-native` attachment is an earlier snapshot of the same session as the live `Loki.log`)
and 2 non-terminal mid-session copies (§2.2), **13 terminal session records** remain: 1 clean exit,
**12 deaths**.

**The 2×2 contingency, deaths only (n = 12):**

| | **`UECC-*` dir EXISTS** | **no `UECC-*` dir** | total |
|---|---:|---:|---:|
| **`handing control over to crashpad` PRESENT** | **0** | **7** | 7 |
| **key ABSENT** | **2** | **3** | 5 |
| total | 2 | 10 | 12 |

- **Off-diagonal count: 0.** No session ever produced both artifacts, and no session with the key
  produced a `UECC-*` dir. The S108 "6/6 anti-correlated" observation **holds and extends to 12/12.**
- **But the key is SUFFICIENT, not NECESSARY.** The bottom-left/bottom-right split is the important
  one: **key absent ⇏ `UECC-*` dir**. 3 of 12 deaths have *neither* artifact (§2.3). A classifier
  built on "no crashpad key ⇒ it made a dump" is **wrong 3 times in 5**.
- **Statistical strength, stated honestly:** Fisher exact one-sided
  p = C(5,2)/C(12,2) = 10/66 = **0.152**. At n = 12 the table alone is **not** significant. What makes
  the result trustworthy is §1.4 (the mechanism), not the count.

### 1.2 ★ The `UECC-*` dirs' own `Loki.log` CANNOT be used — the 0-of-80 is void

**MEASURED.** 80 of the 87 `UECC-*` dirs contain a `Loki.log`. **0 of 80** contain
`handing control over to crashpad`. **That number carries no information**, for a reason measured
directly:

- **0 of 80 also contain `=== Critical error: ===`** — UE's own crash block — although these are by
  definition UE-handler crashes and their full logs *do* contain it.
- On both matched pairs the crash-dir `Loki.log` is a **byte-exact prefix** of the full session log:
  - `166396E2`: snapshot 3,643,785 B, full log 3,649,136 B; `sha256(head -c 3643785 full) ==
    sha256(snapshot)` ✔. The 5,351 missing bytes are the `=== Critical error: ===` block and the
    `[Callstack]` dump.
  - `FED1F952`: snapshot 11,010,422 B, full log 11,015,824 B; sha256 ✔.
- The snapshot's last line predates the crash by ~11 s in both cases (last flushed page boundary).

⇒ **INFERRED (tightly): the crash-dir log snapshot is systematically truncated before any terminal
block.** Classifying deaths from it is measuring the flush boundary, not the game.
**This is the same shape as the error this audit is cleaning up**, one level down.

### 1.3 How sessions were matched to crash dirs, and the failure rate

**Method (I4):** exact string equality of line 1, `Log file open, MM/DD/YY HH:MM:SS`. **Verified**, not
assumed: both matches were confirmed by the byte-exact-prefix sha256 above.

| | |
|---|---|
| `UECC-*` dirs with a `Loki.log` | 80 of 87 |
| distinct `Log file open` keys among them | **80 of 80** (no collisions — the key is unique per session) |
| `UECC-*` dirs matched to a surviving **full** session log | **2 of 87 = 2.3 %** |
| terminal session logs matched to a `UECC-*` dir | 2 of 13 |
| **match failure rate** | **97.7 %**, and it is **entirely a coverage failure, not a precision failure** |

**The cause of the 97.7 %, and it is the real denominator problem.** UE keeps only ~1 day of archived
session logs. MEASURED: `Saved\Logs` holds **9** `Loki-backup-*.log`, **all dated 2026-08-04**, plus
`Loki.log`, `Loki_2/3/4.log` and 2 `.bak` copies. The crash corpus spans **2026-06-25 → 2026-08-04**.
⇒ **For 85 of 87 crash dirs no session log survives, so the crashpad channel is unmeasurable for them,
in either direction.** No amount of offline work recovers it.

### 1.4 Why the anti-correlation is a mechanism, not a coincidence

**MEASURED**, from the two terminal tails:

```
UE-handler death  (produces UECC-*, n=2/2)      crashpad death (no UECC-*, n=7/7)
──────────────────────────────────────────      ────────────────────────────────────────
LogSentrySdk: Start configuration of crash…     LogSentrySdk: flushing session and queue
LogWindows: Error: === Critical error: ===                     before crashpad handler
LogWindows: Error: Unhandled Exception: …       LogSentrySdk: Verbose: invoking `on_crash` hook
LogWindows: Error: [Callstack] 0x… × ~40        LogSentrySdk: Sentry HandleBeforeCrash Begin / End
LogWindows: FPlatformMisc::RequestExit(1,       LogSentrySdk: Screenshot attachment is disabled…
   LaunchWindowsStartup.ExceptionHandler)       LogSentrySdk: Verbose: serializing envelope…
LogCore: Engine exit requested (Win RequestExit) LogSentrySdk: handing control over to crashpad
```

`Sentry HandleBeforeCrash` count: **2 in every crashpad death, 0 in every UE-handler death** (7/7 and
2/2). `RequestExit`: **3 in every UE-handler death, 0 in every crashpad death.** The `UECC-*` dir is
written by the very handler whose signature is absent. **INFERRED: the two are mutually exclusive
terminal paths, so a `UECC-*` dir is positive proof that the death did NOT go through crashpad** —
which is why the historical `UECC-*` corpus is still valid *as far as it goes*. The blind spot is
exclusively about the sessions that left **no** dir.

---

## 2. DELIVERABLE B — the classification table

### 2.1 Definitions

- **Death** = a terminal session record that lacks the clean-exit signature.
- **Clean exit** (MEASURED signature, from the one instance in the corpus, `Loki_2.log`):
  `FPlatformMisc::RequestExit(**0**, UGameEngine::HandleExitCommand)` → `LogExit: Preparing to exit.`
  → `LogExit: Game engine shut down` → `LogExit: Exiting.` → `Log file closed, MM/DD/YY HH:MM:SS`.
  The exit **code** (`0` vs `1`) and the **reason string** are what discriminate — a crash also emits
  `RequestExit`, but with `1` and `…ExceptionHandler`.
- **Terminal record** = a log that was the process's last writer. The 2 `.bak` files are excluded:
  they are hand-made mid-session copies (their mtime equals their own last log line to the second, and
  they were made by project scripts before a modpak/patch), so they say nothing about how that session
  ended.

### 2.2 The table

| class | count | evidence | durability of the evidence |
|---|---:|---|---|
| **crash-report directories on disk** (all-time) | **88** | `Saved\Crashes\*` = 87 `UECC-*` + 1 `_0000` | durable, never purged |
|  ├ with a usable (non-empty) `UEMinidump.dmp` | **81** | file size > 0 | durable |
|  ├ with a 0-byte / absent minidump | **7** | 6 × `UECC-*` + `_0000` | durable but useless |
|  └ of which **FK-24 probe self-kills to be excluded** | **2** | `166396E2`, `FED1F952` (§4) | — |
| **crashpad-only deaths, observed** | **7** | `handing control over to crashpad`, all 2026-08-04 | ⚠ log purged in ~1 day; the `.dmp` survives until **the next launch** (see below) |
|  └ of which a minidump is still on disk | **1** | `41cdafa3-…dmp`, **43,804,912 B**, 2026-08-04 14:10 | ⚠ cleared by the next launch |
| **deaths with NEITHER artifact** | **3** | 2026-07-05 ×2 (`Loki_3`, `Loki_4`), 2026-08-03 ×1 | log only |
| **clean exits** | **1** | `Loki_2.log`, 2026-07-19 | log only |
| **non-terminal mid-session copies (excluded)** | 2 | `Loki.log.pre-patch.bak`, `.pre-modpak.bak` | — |
| **TOTAL process deaths with surviving evidence** | **≥ 97** (98 if `_0000` counts) | 87 `UECC-*` + 7 crashpad + 3 neither. ⚠ `_0000` excluded on the grounds that it is CrashReportClient's own crash — **that attribution is UNPROVEN** (skeptic T6): its 509-byte log is the game's pak/IoStore init and its fault address lies in the SUPERVIVE image range. If it is a game death the total is 98 | — |
| └ of which **genuine game deaths** | **≥ 95** | 97 − the 2 FK-24 probe self-kills | — |

### 2.3 The "neither artifact" class is **NOT empty** — and that is a *good* answer

The brief anticipated this class might be empty, closing a loose end. It is not. **MEASURED**, 3
instances, and all three share one signature:

| session (log open, local) | died (UTC) | duration | last line |
|---|---|---:|---|
| `Loki_3.log` 07/05 16:19:48 | 21:53:37 | 2029 s | `LogUIActionRouter: Cleaned out [0] inactive UI action bindings` |
| `Loki_4.log` 07/05 16:51:49 | 21:53:45 | 116 s | `VivoxCore: Warning: req_account_anonymous_login failed…` |
| `Loki-backup-…03.05.45` 08/03 21:52:42 | 03:05:45 | 783 s | `VivoxCore: Warning: req_account_anonymous_login failed…` |

All three have **`grep -c 'LogExit\|RequestExit\|Engine exit requested'` = 0** — zero handler ran, of
any kind. The log simply stops mid-frame.

**INFERRED (well-supported, not proven): these are external terminations, not uninstrumented crashes.**
`Loki_3` and `Loki_4` are two concurrent instances that stopped **8 s apart**; the 08-03 one is
followed by a fresh session **35 s later**. Both patterns match the project's own workflow
(`launch-redirect.ps1`, kill-and-relaunch between runs) far better than a crash.
**Blind spot:** an anti-cheat / code-integrity `TerminateProcess` would look byte-identical in the log.
Durations 116 / 783 / 2029 s do not cluster at the documented ~285 s integrity-kill latency, which
argues against it but does not exclude it.

⇒ **The loose end does not close, but it changes shape:** the third class exists, it is small, and its
best explanation is the operator's own hand, not a third failure mode of the game.

### 2.3a ⚠ Blind spot on the crashpad row — there is no historical cache to recover

**MEASURED.** A filesystem sweep for `.sentry-native` directories over `C:\Users\eastr\AppData` and
`G:\git` (`find … -maxdepth 6 -name .sentry-native -type d`) finds **exactly one belonging to
SUPERVIVE**: `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\.sentry-native`, holding
**exactly one report**. The other seven hits (`BET`, `fellowship`, `QZSim`, `R5`, `RSDragonwilds`,
`UnrealEngine\Common\Zen`, `cura`) are unrelated applications. Also searched: every `*.dmp` over 1 MB
under both roots — the only hits are the 81 `UEMinidump.dmp` files and `41cdafa3-…dmp`.

⇒ **Every crashpad-only death before 2026-08-04 14:10 is gone.** The count of 7 is derived **from
session logs alone**, and it is bounded above by log retention (~1 day), not by how often the channel
fires.

**Retention correction, and do not repeat the old figure.** The *"uploads and deletes it within
~3 minutes"* line in `CLAUDE.md` is **RETRACTED** — see `docs/s109-fk9-capture-durable.md`. MEASURED
there: crashpad attempts **exactly one** upload ~2 s after the crash; when it fails, the report sits in
`state = Pending` **indefinitely** (74+ min observed) because `crashpad_handler.exe` dies with the
game. **It is the NEXT LAUNCH that clears the database.** The capture rule is therefore
*"copy it off before you relaunch"*, not *"copy it off within 3 minutes"*.

### 2.4 The true all-time denominator is UNKNOWN, and cannot be estimated from this corpus

**Do not extrapolate the 7:2:1 split.** In the only window where both channels are observable, real
game deaths went to crashpad **7 of 7** — but on 2026-07-26 the FK-7 camera and anim crashes
**demonstrably produced `UECC-*` dirs with analysable minidumps**. The channel a death takes is
**regime-dependent and the regime changed** (§5). Multiplying 87 by anything is unsupported.

The defensible statement is: **all-time process deaths ≥ 97 (game deaths ≥ 95), of which the crashpad channel contributes an
unknown number that is 0 for any session with a `UECC-*` dir and unmeasurable for every session
without one whose log has been purged.**

---

## 3. DELIVERABLE C — re-checking the "N of 86/87" claims in `docs/fk7-crash-settled.md` §0

### 3.1 Claim (i) — *"the camera bug is CONDITIONAL, at roughly 1-in-3 to 1-in-2 per launch"*

> §0.2: *"Grouping the corpus by PID and local time: cohort 07-26 04:09–04:55 = **2 camera / 4**;
> cohort 07-26 01:44–02:24 = **1 camera / 5**. ⇒ `P(quiet camera outcome | guard does nothing) ≈
> 0.5–0.8`."*

**Numerators and cohort memberships REPRODUCED exactly** (MEASURED, from `crash_census.csv` mtimes):
cohort A = `EE95146A` 04:09, `154E12A5` 04:14, `BE345EC2` 04:29, `7E6FDF97` 04:39 → 4 dumps, 2 camera.
Cohort B = `AABE886D` 01:44, `FF9CF623` 01:50, `8F0E05BF` 02:11, `063228F6` 02:19, `0313276C` 02:24 →
5 dumps, 1 camera.

**The denominator is DUMPS, not launches.** The doc's own §0.3 records **5 further dumpless sessions**
on the same date. Any launch that (a) died via crashpad, (b) was killed externally, or (c) survived,
is absent from the denominator. Every such launch can only *lower* the rate:
P(camera | launch) = 3/N with N ≥ 9, vs the quoted 3/9.

| | |
|---|---|
| original | 1-in-3 to 1-in-2 **per launch** |
| corrected | **≤ 1-in-3 per launch**; 3/9 is the rate **per dump-producing death**, and it is a strict **upper bound** on the per-launch rate |
| verdict | **SURVIVES — and the operational conclusion is STRENGTHENED** |

The conclusion that hangs off it — *"a single quiet run is nearly uninformative; gate every read on
the `[VTG] INVALID` detection line, never on the absence of a crash"* — becomes **more** binding, not
less: the rarer the corruption per launch, the more launches a quiet result is compatible with.
**§0.5's detection-gated one-bit criteria need no change.**

### 3.2 Claim (ii) — *"the 5 dumpless deaths are a DENOMINATOR ERROR, not a failure mode. REMOVED."*

**Verdict: SPLIT. The specific sub-conclusion SURVIVES; the general claim is FALSIFIED.**

**FALSIFIED, and this is the whole reason this audit exists:** *"dumpless death is not a failure
mode"* is now measurably wrong. There **is** a distinct, real, previously uninstrumented death
channel — 7 instances observed on 2026-08-04, one with a preserved **43.8 MB** minidump. §0.2's
sentence *"Every alternative mechanism was excluded"* is **incomplete**: the enumeration
(`ConsoleCtrl`, `INTERRUPTED`, `fastfail`, `gsfailure`, `LowLevelFatalError`, hang) **never included
the crashpad handler**, and crashpad is exactly a mechanism that produces a death with no `UECC-*`
dir and no `LogExit` markers.

**SURVIVES, on evidence that does not depend on the dump channel:**
- 3 of the 5 were recovered from git (`docs/tutorial-launch-marker.txt`) as **RM_SPAWNPOSSESS** runs
  that reached `[SP] done step=4`, with the operator's commit landing **+3 s, +3 s, +9 s** after the
  session's last log line. That is the same external-kill signature as §2.3's three instances.
- The other 2 died at **T+148.5 s and T+165.9 s**, i.e. **before** the T+173.5 s mesh build that is
  the necessary antecedent of both FK-7 families. They are outside FK-7 by construction regardless of
  how they died.

**What is NOT recoverable, stated plainly:** the 2026-07-26 session logs have been purged, so it is
**permanently unknowable offline** whether those 2 were crashpad deaths. **Blind spot:** searched
`%LOCALAPPDATA%\SUPERVIVE\Saved\Logs\` (all `Loki*` `.log`/`.bak`, no size floor), the repo
(`git ls-files` + `find -iname '*.log'`), and the 87 crash dirs. No 2026-07-26 game session log
survives anywhere.

| | |
|---|---|
| original | *Blocker 2 REMOVED — a denominator error, not a failure mode* |
| corrected | Blocker 2's **FK-7 exclusion stands**. But *"not a failure mode"* is **false in general**: the crashpad channel is a real failure mode that was never enumerated, and 2 of the 5 remain unattributable forever |
| verdict | **WEAKENED** (sub-conclusion survives; the general claim is FALSIFIED) |

### 3.3 Claim (iii) — *"Only 5 of 86 dumps capture an `APlayerCameraManager` at all"*

**The numerator is REPRODUCED independently and exactly** (MEASURED, I6). Scanning all 81 non-empty
minidumps for the qword `image_base + 0x07EC5B88`:

| dump | `+0x420` (`ViewTarget.Target`) | low byte | `+0x460` (FOV/DesiredFOV/OrthoWidth) | verdict |
|---|---|---|---|---|
| `B61ED1A7` | `0x000001A4F94FD901` | `01` | 90.0 / 90.0 / 512.0 | camera crash |
| `AABE886D` | `0x000002640B5BF301` | `01` | 90.0 / 90.0 / 512.0 | camera crash |
| `BE345EC2` | `0x000001E79523F301` | `01` | 90.0 / 90.0 / 512.0 | camera crash |
| `7E6FDF97` | `0x0000023A9E318D01` | `01` | 90.0 / 90.0 / 512.0 | camera crash |
| `FF9CF623` | `0x000001CB9A088D40` | **`40`** | 90.0 / 90.0 / **1536.0** | ★ **the clean negative control** |
| `65F4745A` | — | — | not a `FMinimalViewInfo` | **NOT a PCM** — 3 *stack slots* at VA `0x3CA85FDD…` holding the vtable **address**; `+0x420` reads `0`/`0`/`0xFFFFFFFF`. `65F4745A` is a 2026-07-17 `FMallocBinned2 Attempt to realloc an unrecognized block` fatal, unrelated |

**5 objects, in 5 dumps.** The doc's `ViewTarget.Target = 0x1CB9A088D40` for `FF9CF623` is reproduced
byte-for-byte. **Positive control passed:** the instrument found all four known camera dumps before it
found anything else.

**The denominator was wrong twice over:**

| | |
|---|---|
| stated | 5 of **86** |
| 86 was actually | the **directory** count at 2026-07-29 (85 real `UECC-*` + the phantom `_0000`) |
| dirs with a usable minidump at 2026-07-29 | **79** (86 − 6 empty − the phantom) |
| corrected | **5 of 79 dumps** (6.3 %, vs the 5.8 % implied) |
| today's numbers, for future recomputation | 88 dirs · 81 non-empty dumps · minus the 2 probe dumps ⇒ **79 admissible FK-7 dumps** |

| | |
|---|---|
| verdict | **SURVIVES.** The claim is an **existence** result — a clean `APlayerCameraManager` in a session that reached 195 s — and existence is denominator-insensitive. The corrected fraction is 6.3 % rather than 5.8 %; nothing downstream moves. **Restate as "5 of 79", and say "UE minidumps", because a crashpad minidump has never been scanned for a PCM at all.** |

### 3.4 Two further defects found while re-checking

**★ The phantom row `_0000`.** (MEASURED.) `Saved\Crashes\_0000\` — a real directory, so `harvest.py`'s
un-filtered `os.listdir` ingests it, but: `ProcessId` **0**, `SecondsSinceStart` **0**, `EngineVersion`
**empty**, `UEMinidump.dmp` **0 bytes**, and its `Loki.log` is **509 bytes of the CrashReportClient's
own log** (no `Log file open` line, no timestamps). **It is a crash of the crash reporter, not of the
game**, and it has been inflating every denominator since 2026-06-29 (census mtime
`2026-06-29 18:45:55`). It is why the doc's "86" was really 85.

**★ For any FRAME-BASED claim the base is 74, not 86 or 87.** (MEASURED.) **13 of the 87 census rows
carry an empty `chain`** — and all 13 also carry `base=0x0`. Only **74 rows carry frames at all**. So
`§1.1`'s *"dumps in corpus 86 / dumps carrying a game-frame chain 73"* is right in spirit but the
denominator it sits next to is not the one the arithmetic uses: **68 % of *chained* crashes are exact
repeats** is `50/73`, computed on a base that was never stated as 73-of-86-minus-a-phantom. It is
unaffected in value; it just must not be quoted as *"68 % of the corpus"*.

**★ And `base=0x0` is NOT the same thing as a zero-byte dump.** (MEASURED — this one is a fresh
instrument artifact.) Only **7** of those 13 rows have a 0-byte `UEMinidump.dmp`. The other **6**
(`154E12A5`, `298DDD37`, `61C55551`, `8C3ECC71`, `A55704B3`, `B84A0661`) have **full, parseable
minidumps** — my §3.3 scan read the SUPERVIVE image base straight out of their `ModuleListStream`,
**81 of 81 non-empty dumps parsed**. So 6 dumps are being written off as contentless when they are
not. `154E12A5` is one of them — the doc's own *"no frames — Rip=0, EXECUTE @ 0"* ANIM crash.

> ## ⚠ DIAGNOSIS CORRECTED after adversarial review (S109 skeptic, T6) — and the correction matters
> I originally called `base=0x0` a **"`harvest.py` parse failure"**. **That is wrong.** Verified at
> source: `tools/crashtri/harvest.py:27-34` **never opens a minidump at all** — it reads
> `CrashContext.runtime-xml`, parses `<PCallStack>`, and sets
> `base = game[0][1] if game else 0`, where `game` is the subset of frames whose module name starts
> with `supervive`.
>
> ⇒ **`base=0x0` means "the OS-recorded callstack contains no SUPERVIVE frame at all."** That is a
> **semantic fact about the crash**, not a tooling defect, and `harvest.py` is reporting it correctly.
> My own error was the very thing this document is about: I inferred an instrument failure from a
> suspicious value without reading the instrument.
>
> **This is load-bearing, because "no SUPERVIVE frames" is the defining property of the
> `runtime.dll + 1` family** identified in `docs/s109-dump-forensics.md`. The 13 chainless rows are
> therefore *candidates for that family*, not junk — and 6 of them have walkable minidumps nobody has
> walked. **That is a concrete, free next step**, and it is the opposite of the "fix the parser"
> recommendation I gave in §5(c), which should not be actioned.

**★ The census is stale and internally inconsistent with the disk.** (MEASURED.)
`crash_census.csv` = 87 rows = 86 `UECC-*` + `_0000`. On disk: 87 `UECC-*` + `_0000` = 88.
**`FED1F952` is on disk but absent from the census.** So the census simultaneously **contains one
non-dump** and **omits one dump** — and the one it omits is a probe artifact while the one it contains
(`166396E2`) is *also* a probe artifact (§4).

---

## 4. DELIVERABLE D — the two probe dumps that must be excluded

`166396E2` and `FED1F952` are the FK-24 watchpoint probe killing its own host
(`docs/s108-crash-triage.md`, `docs/s108-fk24-instrument-corrected.md`). Their exception codes match
the two probe modes exactly — MEASURED, and this is independent confirmation of the S108 attribution:

| dump | `CrashType` / `ErrorMessage` | `SecondsSinceStart` | probe mode |
|---|---|---:|---|
| `166396E2` | `Unhandled Exception: 0x80000004` (`STATUS_SINGLE_STEP`) | 2550 | **DR** hardware watchpoint |
| `FED1F952` | `EXCEPTION_ACCESS_VIOLATION **writing** address 0x2BD733EAEE0` | 572 | **page** (`PAGE_READONLY` flip) |

**Are they already contaminating the numbers?**

| artifact | contains `166396E2` | contains `FED1F952` | verdict |
|---|---|---|---|
| `docs/fk7-crash-settled.md` §0 ("86 dumps") | **no** | **no** | ✅ **clean** — both dumps postdate the document (08-03 / 08-04 vs 07-29). The doc's error is the phantom `_0000` and the 6 empty dumps, **not** the probe dumps |
| `tools/crashtri/crash_census.csv` (current, 87 rows) | **YES — row 13** | no (absent from the file) | ⚠ **contaminated**. Any recount run on the census today must drop it |
| `Saved\Crashes` directory tree (today) | yes | yes | ⚠ any recount from disk must drop **both** |

**The admissible FK-7 dump corpus, computed:**

```
88  crash-report directories on disk        (87 UECC-* + 1 `_0000`)
−1  _0000              (phantom: 0-byte dump, pid 0, CrashReportClient's own crash)
−2  166396E2, FED1F952 (FK-24 probe self-kills, NOT game crashes)
──
85  genuine UECC game deaths                <-- use this for DEATH-COUNT claims
−6  UECC-* with a 0-byte / absent UEMinidump.dmp
──
79  admissible FK-7 dumps with real minidump content   <-- use this for DUMP-CONTENT claims
```

**For CHAIN / FAMILY claims the base is different again**, because it depends on the census rather than
on disk: `chain != ""` holds for **74 of the 87 census rows** (MEASURED). That 74 already excludes
`_0000` and the 6 empty dumps, still **includes** `166396E2`, and cannot include `FED1F952` (absent
from the file) ⇒ **a strictly clean chain base is 73**. Note the 74 is *lower* than it should be: 6 of
the 13 chainless rows have perfectly good minidumps and are `harvest.py` parse failures (§3.4), so a
fixed harvester would push the chain base to ~79.

**Recomputed with the corrected denominator: 5 of 79 (6.3 %) capture an `APlayerCameraManager`;
4 of 79 (5.1 %) are camera crashes.** Neither probe dump contains a PCM, so the numerators are
unchanged (MEASURED — §3.3's scan covered all 81).

---

## 5. ★ The one thing this audit could NOT settle, and it is the highest-value follow-up

**MEASURED:** on 2026-08-04, seven consecutive staged tutorial sittings died through crashpad and left
**zero** `UECC-*` dirs. On 2026-07-26, nine tutorial-sitting deaths left **nine** `UECC-*` dirs with
analysable minidumps (the whole FK-7 diagnosis rests on four of them). **Both regimes are real. The
switch is unexplained.**

Session-by-session, the entire observable window (all times LOCAL; staged-run labels recovered from
`docs/fk24-stage-*.txt` mtimes):

| # | session opens | dies | dur | terminal signature | artifact | run |
|---|---|---|---:|---|---|---|
| 1 | 08-03 21:52:42 | 22:05:45 | 783 s | *none* | **neither** | (pre-stage) |
| 2 | 08-03 22:06:20 | 22:49:21 | 2580 s | `=== Critical error: ===` | **`UECC 166396E2`** | S107 DR probe |
| 3 | 08-04 01:42:43 | 01:45:06 | 143 s | crashpad handoff | none | `wp2r1` |
| 4 | 08-04 01:47:56 | 01:57:52 | 596 s | `=== Critical error: ===` | **`UECC FED1F952`** | `wp2r2` (page probe) |
| 5 | 08-04 02:00:47 | 02:03:18 | 151 s | crashpad handoff | none | `wpDRr1` |
| 6 | 08-04 02:07:09 | 02:10:53 | 224 s | crashpad handoff | none | `wpDRr2` |
| 7 | 08-04 02:12:15 | 02:17:15 | 299 s | crashpad handoff | none | `novtg1` |
| 8 | 08-04 02:19:58 | 02:22:30 | 151 s | crashpad handoff | none | `testact1` |
| 9 | 08-04 13:55:47 | 14:01:07 | 319 s | crashpad handoff | none | `nodiag1` |
| 10 | 08-04 14:02:15 | 14:10:26 | 491 s | crashpad handoff | none → **`41cdafa3.dmp` 43.8 MB still on disk** | `nostat1` |

**Read row-by-row: the only two rows that produced a `UECC-*` dir are the two probe runs.** Every
non-probe death in this window is invisible to `harvest.py`. Durations 143–491 s do not cluster at the
~285 s integrity-kill latency, so these are not all integrity kills.

**Hypotheses, none tested, all cheap:** (a) the probe's own VEH changes which handler claims the
exception; (b) the crashing **thread** differs (UE's `__except` frames only cover
`LaunchWindowsStartup` and `FRunnableThreadWin::GuardedRun`); (c) a Sentry/plugin ordering change
between 07-26 and 08-03. **This is FK-26-adjacent and belongs in the ignorance map.**

---

## 6. What to change, concretely

1. **`docs/fk7-crash-settled.md` §0.2** — replace *"Only **5 of 86** dumps"* with
   *"Only **5 of 79** usable UE minidumps"*, and add the note that no crashpad minidump has ever been
   scanned for a PCM.
2. **`docs/fk7-crash-settled.md` §0.2** — restate the base rate as *"**≤** 1-in-3 per **launch**;
   3-of-9 is the rate per **dump-producing death** and is a strict upper bound"*. The §0.5 gating is
   unaffected.
3. **`docs/fk7-crash-settled.md` §0 Blocker 2** — keep *REMOVED* for the FK-7 exclusion, but strike
   *"Every alternative mechanism was excluded"*: the crashpad handler was never in the enumeration,
   and 2 of the 5 are permanently unattributable.
4. **`tools/crashtri/harvest.py`** — three small fixes, none of which is a rewrite: (a) skip anything
   that is not `UECC-*` (kills the `_0000` phantom); (b) skip 0-byte `UEMinidump.dmp` and say so;
   (c) **stop emitting `base=0x0` for dumps whose `ModuleListStream` parses fine** — 6 dumps are being
   discarded that are not empty (§3.4). Emit the admissible count separately from the directory count.
   **Do not** turn it into a general tool.
5. **The only durable fix for the real blind spot is a capture rule, not a tool.** A crashpad report
   survives until **the next launch** (not ~3 minutes — that figure is retracted, §2.3a). The
   operational consequence for the next tutorial sitting: after any death, **copy
   `…\Loki\.sentry-native\reports\*.dmp` + `attachments\<id>\Loki.log` + the live `Loki.log` aside
   BEFORE relaunching**, unconditionally, before looking at `Saved\Crashes` at all. `CLAUDE.md`'s
   "~3 minutes" wording needs updating to match.
6. **Raise UE's log retention** so this audit is possible next time — 9 backups covering ~1 day is why
   97.7 % of the corpus is unclassifiable.

---

## 7. Claim register

| # | claim | tag |
|---|---|---|
| 1 | 0 of 80 crash-dir `Loki.log` contain the crashpad key | MEASURED |
| 2 | …and that 0 is void: the crash-dir log is a byte-exact truncated prefix (sha256, 2/2) | MEASURED |
| 3 | Contingency over 12 observable deaths: 0/7 crashpad-key sessions have a `UECC-*` dir; 2/2 critical-error sessions do | MEASURED |
| 4 | Fisher one-sided p = 0.152 — the table alone is not significant at n=12 | MEASURED |
| 5 | The two terminal paths are mutually exclusive (`HandleBeforeCrash` 2/2/0 vs `RequestExit` 0/0/3) | MEASURED |
| 6 | ⇒ a `UECC-*` dir proves the death was not a crashpad death | INFERRED |
| 7 | crashpad was armed in 16 of 16 sessions (positive control) | MEASURED |
| 8 | bare `crashpad` matches 3× in every session incl. clean exits — useless key | MEASURED |
| 9 | 88 crash dirs; 81 non-empty minidumps; 7 unusable; `_0000` is a CrashReportClient crash | MEASURED |
| 10 | The fk7 doc's "86" = 85 real dirs + 1 phantom; usable dumps then = 79 | MEASURED |
| 11 | 5 dumps contain a real `APlayerCameraManager`; the 6th candidate `65F4745A` is stack slots | MEASURED |
| 12 | `FF9CF623` `ViewTarget.Target = 0x1CB9A088D40`, low byte `0x40` — negative control reproduced | MEASURED |
| 13 | 3 deaths have neither artifact; all 3 have zero `LogExit`/`RequestExit` | MEASURED |
| 14 | …and are best explained as external termination, not a third game failure mode | INFERRED |
| 15 | 85 of 87 crash dirs have no surviving session log. ⚠ CORRECTED wording: they are **not** "unclassifiable" — per §1.4 the *existence* of a `UECC-*` dir already proves the death was non-crashpad. What is lost is the reverse direction and the session context, i.e. a **missing-denominator** problem, not an unclassifiable numerator | MEASURED |
| 16 | On 08-03/08-04 the only 2 `UECC-*` dirs are the 2 FK-24 probe self-kills | MEASURED |
| 17 | The channel a death takes is regime-dependent and the regime change is unexplained | OPEN |
| 18 | All-time deaths **≥ 97** (game deaths ≥ 95); the true total is unknown and not estimable from this corpus. ⚠ CORRECTED from "≥ 98" — that contradicted §2.2/§2.4, which are right | MEASURED (lower bound) / OPEN (total) |
| 19 | 13 of 87 census rows have an empty `chain` and `base=0x0`; only 74 carry frames (73 excluding `166396E2`) | MEASURED |
| 20 | 6 of those 13 have **full parseable minidumps** (81/81 non-empty dumps parsed by an independent reader). ⚠ CORRECTED: `base=0x0` is **not** a parse failure — `harvest.py` never opens a dump, it reads `<PCallStack>`, so `base=0x0` means **no SUPERVIVE frame in the OS callstack** — the defining property of the `runtime.dll+1` family. The 6 walkable ones are unexamined candidates | MEASURED |
| 21 | Exactly one SUPERVIVE `.sentry-native` DB exists, holding one report; no historical crashpad cache survives anywhere | MEASURED |
| 22 | crashpad retention is "until the next launch", not ~3 min — the ~3 min figure is RETRACTED (`docs/s109-fk9-capture-durable.md`) | MEASURED (elsewhere), adopted here |
