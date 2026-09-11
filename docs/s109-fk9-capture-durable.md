# S109 — FK-9: crashpad capture made durable, and the "3-minute retention window" retracted

**Date:** 2026-08-04 · Session S109 · Task 2 of the S109 handoff.
Every claim tagged **MEASURED** (observed directly) or **INFERRED** (reasoning on top).

---

## 0. Result in one paragraph

Crash reports on the tutorial route are written by **Sentry's crashpad**, not by UE, into
`<GameRoot>\Loki\.sentry-native\`, with **no `UECC-*` directory**. They are **not** deleted on a
timer — MEASURED: one survived **65+ minutes**, unchanged, after its single upload attempt.
`crashpad_handler.exe` is a child of the game and dies with it, so between a death and the next
launch nothing is alive to touch the database at all.

**★ MEASURED (upgraded from INFERRED — see §7): the report is cleared by the next game launch.** The
experiment was run at 16:38 the same day. `reports/` went from one 43.8 MB report to **empty** and
`metadata` from 150 B / `num_records=1` to **16 B / `num_records=0`**, in the same second the new
`crashpad_handler.exe` started. The competing explanation (a delayed successful upload) is
**excluded**: the purge is synchronous with handler startup and empties the database wholesale rather
than transitioning one report to `Completed`.

**The "uploads and deletes it within ~3 minutes" figure is RETRACTED.** It was the interval between
two `ls` calls, and a relaunch fell inside it.

**The fix.** `launch-redirect.ps1` archives the database **immediately before launching** — once, and
only there. `archive-crashdumps.ps1` is `Copy-Item`-only (no `Remove-Item`, no `Move-Item`) and never
touches the source, so even a wrong rule would cost *yield*, never an original and never a broken
launch (confirmed by adversarial review, S109 skeptic T5). ⚠ A second "post-exit" call was tried and
**removed**: `& $exe` does not block, so it fired one second after the first. See §7.

---

## 1. What crashpad's own bookkeeping says — MEASURED

The database carries two binary files that answer the retention question outright. Decoded with
`struct` against crashpad's `Settings::Data` and `MetadataFileReportRecord` layouts:

`settings.dat` (40 bytes — exactly `Settings::Data`):

| field | value |
|---|---|
| magic / version | `sdPC` / 1 |
| **options** | `0x00000001` → **`uploads_enabled = TRUE`** |
| last_upload_attempt_time | 1785870629 = **2026-08-04 14:10:29 local** |

`metadata` (report index, `num_records=1`):

| field | value |
|---|---|
| uuid | `41cdafa3-ceff-4d83-8d11-69fa9b75b54a` |
| creation_time | 1785870627 = **14:10:27** (the crash) |
| last_upload_attempt_time | 1785870629 = **14:10:29** (crash + 2 s) |
| **upload_attempts** | **1** |
| **state** | **2** — see the caveat below |

⚠ **CORRECTED after adversarial review (S109 skeptic, T5).** The record layout is **56 bytes**, not
the 48 I first assumed; it is pinned independently by `id_index = 41` exactly equalling the first
string's byte length. The field values above survive that correction. But **`state = 2 ⇒ Pending` is
UNVERIFIED for this crashpad build** — `Completed` is at least as likely, and I asserted the enum
from upstream crashpad rather than from anything in this binary. Do not build on it.

⇒ **What is MEASURED, and does not depend on the enum:** one upload was attempted two seconds after
the crash, and the report **still sat on disk 65+ minutes later** (14:10 → 15:15, verified by `ls`
and by a byte-exact SHA-256 still matching the copy taken at 15:06). Whether that attempt succeeded
or failed, **the report was not deleted promptly either way** — which is the operationally important
fact and is enum-independent.

**INFERRED (mechanism):** no retry occurred because `crashpad_handler.exe` exits with its client.
Confirmed indirectly — MEASURED at 15:11 with the game not running: `crashpad_handler` process
count = **0**, while `ags` (started 14:02) was still alive. Nothing was left to retry.

---

## 2. The retraction — a ninth instance of the instrument-artifact pattern

`docs/s108-skeptic-review.md` records, correctly and as MEASURED:

```
02:17:16   report 1c5e7708-….dmp PRESENT (43,893,392 B)
02:20:11   reports/ and attachments/ EMPTY
```

and concluded the Sentry path *"uploads and deletes it within ~3 minutes"*. That conclusion does not
follow, and the session logs show why. Reconstructed from `Log file open` line-1 timestamps (local)
plus file mtimes — **MEASURED**:

```
02:12:15   session starts
02:17:15   session DIES        (log ends: handing control over to crashpad)
02:19:58   NEXT SESSION STARTS   <-- inside the skeptic's observation gap
02:22:30   that session dies
```

**The deletion window contains exactly one relaunch.** The "~3 minutes" was the gap between two `ls`
calls — the **observation interval mistaken for the phenomenon's timescale**. The retention window
is not 3 minutes; there is no retention window.

The full day's timeline is 5-for-5 consistent with launch-triggered clearing (**MEASURED**):

| session start (local) | died (UTC) | relaunch after? | report survived? |
|---|---|---|---|
| 02:07:09 | 07:10:53 | yes, 02:12:15 | no |
| 02:12:15 | 07:17:15 | yes, 02:19:58 | no |
| 02:19:58 | 07:22:30 | yes, 13:55:47 | no |
| 13:55:47 | 19:01:07 | yes, 14:02:15 | no |
| **14:02:15** | **19:10:26** | **NO** | **YES — 65+ min** |

The one surviving report is the last one, precisely because nothing was launched after it. This also
retires the competing "54 minutes" datum in the handoff: both observations are the same rule.

> Filed against `memory/supervive-instrument-artifact-pattern.md`. This one is unusual in that the
> instrument was a wall-clock `ls` schedule rather than a tool, and the artifact was a *number*
> rather than an absence — but the shape is identical: a property of the measurement was recorded
> as a property of the system.

---

## 3. Two corrected facts that will otherwise cost someone a session

**3.1 The classification key is NOT the last line of the log.** In the 19:10:26 death,
`handing control over to crashpad` is at **line 52508 of ~52510**, and two further lines follow it:

```
[2026.08.04-19.10.26:679][781]LogSentrySdk: handing control over to crashpad
[2026.08.04-19.10.26:685][781]LogTemp: Error: ULokiGameFeatureToggles::Get FudgeMantlingSouth …
[2026.08.04-19.10.26:685][781]LogTemp: Error: ULokiGameFeatureToggles::Get FudgeMantlingSouth …
```

Any `tail`-based classifier false-negatives on **exactly the one session that has a preserved dump**.
Scan the whole file.

**3.2 Bare `crashpad` is a useless grep key.** It also matches two lines present in **every** session,
including clean exits:

```
LogSentrySdk: Verbose: starting crashpad backend with handler "…\crashpad_handler.exe"
LogSentrySdk: started crashpad client handler
```

The discriminating key is the full string `handing control over to crashpad`. (Adjacent and also
reliable: `LogSentrySdk: flushing session and queue before crashpad handler`, ~106 ms earlier.)

**3.3 Log timestamps mix timezones.** Line 1 (`Log file open, MM/DD/YY HH:MM:SS`) is **local**; every
in-body `[YYYY.MM.DD-HH.MM.SS:mmm]` stamp and the `Loki-backup-<stamp>.log` filename are **UTC**.

---

## 4. The fix

**`configs/archive-crashdumps.ps1`** (new) — read-only w.r.t. the crashpad database; copies
`reports/`, `attachments/` (each run's own `Loki.log`), `metadata`, `settings.dat`, `last_crash` and
the `.run` dirs into `dumps\crashpad-<stamp>[-label]\`, SHA-256-verifies every `.dmp`, and drops an
`ARCHIVE-INFO.txt` recording provenance. It **never deletes the source** — crashpad owns that
directory, and a bad copy must not also mean a lost original. Failures warn but never abort a launch.

**`configs/launch-redirect.ps1`** — calls it **once**, immediately **before** `& $exe`. The launch is
what clears the database, so that placement is the deterministic capture. It also lands at the one
moment when `Saved\Logs\Loki.log` is still the **dead session's** log (UE rotates at game startup),
so the sweep archives the correct untruncated log for the death it is preserving.

⚠ A second call after `& $exe` was tried and **removed** — `& $exe` does not block (the shipping exe
detaches and returns in ~1 s), so it fired one second after the first, before the game had mounted
its paks. Making it wait would break the hands-free tutorial recipe, which needs this script to
return promptly. See §7.

Standalone use, safe at any time:

```bash
powershell -File configs/archive-crashdumps.ps1 -Label fk7run3
```

### Positive controls — all MEASURED, run before believing any of this

| control | expectation | result |
|---|---|---|
| pending report on disk | must find and verify it | **PASS** — found `41cdafa3…dmp` 43,804,912 B, `sha256=f97c584c…` |
| copy fidelity | source == S108 hand-copy == new copy | **PASS** — 3-way SHA-256 identical |
| source preserved | crashpad DB untouched after archiving | **PASS** — `.dmp` still present, same mtime |
| attachment captured | the run's own 7.4 MB `Loki.log` copied | **PASS** |
| empty `reports/` + log shows a death | must WARN, not reassure | **PASS** (tested against a synthetic GameRoot) |
| no database at all | must say so plainly | **PASS** |
| both scripts | parse clean | **PASS** — PS parser, 0 errors |

---

## 5. ⚠ Residual risk, stated because an instrument must declare its own blind spot

**This scheme depends on the upload FAILING.** Uploads are globally enabled (`options` bit 0 = 1) and
the DSN host is reachable — MEASURED: `o566896.ingest.sentry.io` → `34.160.81.0`, TCP 443
`TcpTestSucceeded=True`. **Why today's attempt failed is NOT established** (dead project, revoked
key, or a 4xx are all plausible and all untested). The DSN itself is in plaintext in the envelope:
`https://149a7ac2a7914150b87ce714fd4d6444@o566896.ingest.sentry.io/5710262`.

⚠ **RETRACTED after adversarial review (S109 skeptic, T5).** I originally wrote here that *"if an
upload ever succeeds, the report is deleted ~2 s after the crash"*. **That is unsupported and I had
it backwards.** The one thing this artifact settles is the opposite: an upload *was* attempted at
crash + 2 s and the report **survived 65+ minutes anyway**. So prompt deletion after a successful
upload is not something this evidence shows — and if `state = 2` turns out to mean `Completed`, this
artifact is a direct counter-example to it.

What remains true and worth guarding against: **a report can be cleared without our seeing it**, and
the clearing event has never been caught in the act. Whether that event is a successful upload, a
later prune, or the next launch's handler startup, the failure it produces looks identical from
outside — an empty `reports/` after a death.

**Mitigation implemented:** when the archiver finds no report, it does not print a reassuring
"nothing pending". It first checks the run's `Loki.log` for the crashpad handoff, and if a death
happened with no report it **warns loudly** that a dump was lost and names the fix.

**The fix, if that warning ever fires:** add `o566896.ingest.sentry.io` to `$HostsToRedirect` in
`launch-redirect.ps1`. Deliberately **not** enabled by default — it is unnecessary while uploads
fail, and it puts a new variable on the crash path. Note that a hosts redirect to `127.0.0.1` yields
connection-refused rather than a timeout, so the "a blocked upload could stall the crash path"
concern is probably unfounded; but it is untested, and today it buys nothing.

**Handoff option 2 (disable Sentry so UE's handler writes `UECC-*` again) was NOT tested.** It
remains the theoretically nicest outcome — it would convert these deaths into ordinary corpus
members that every existing tool understands — but it needs a live run to evaluate, and capture is
now durable without it. Cost of testing: one launch. Recorded as still open.

---

## 6. What this does NOT establish

* **It does not attribute any crash.** Capture is an instrument fix. See `docs/s109-dump-forensics.md`
  for the analysis of the preserved dump.
* ~~It does not prove the launch-clears-the-database rule by direct experiment.~~
  **✅ RESOLVED — the experiment was performed at 16:38 the same day. See §7.**
* **It says nothing about why the upload fails**, only that it does (once, at crash + 2 s).

---

## 7. ★ The rule is now MEASURED — the clearing event was caught in the act

**2026-08-04 16:38 local.** A `-NoHook` launch was performed with exactly one report pending. This
was free: the report was already archived twice, so nothing was at risk.

**Baseline, immediately before launch (MEASURED):**

```
reports/    1 file   41cdafa3-ceff-4d83-8d11-69fa9b75b54a.dmp   43,804,912 B
metadata    150 B    num_records = 1, uuid 41cdafa3-ceff-4d83-8d11-69fa9b75b54a
```

**Immediately after launch (MEASURED):**

```
reports/    EMPTY
attachments/ EMPTY
metadata    16 B     num_records = 0     (bare header: 44 41 50 43 01 00 00 00 00 00 00 00 00 00 00 00)
```

**Timing pins the actor.** `metadata` mtime = **16:38:51.536**. `crashpad_handler.exe` (pid 39524)
started at **16:38:51**. Same second. The game process itself started 13 s earlier, at 16:38:38.

⇒ **The clearing agent is the NEW `crashpad_handler.exe` starting and reprocessing the database** —
not the game process as such, and not a successful upload. The skeptic's competing explanation (a
delayed successful upload) is excluded: the purge is synchronous with handler startup, and the
database was emptied wholesale (`num_records → 0`) rather than one report transitioning to
`Completed`.

**The pre-launch sweep caught it.** Both archives hold the full 43,804,912 B at
`sha256 f97c584cba8d917a…`:

```
dumps\crashpad-20260804-163837\           <- pre-launch sweep, the one that matters
dumps\crashpad-20260804-163838-postexit\  <- see the wart below
```

⇒ **Status change: "the next launch clears it" moves from INFERRED to MEASURED.** §0 and §2 may now
be read at full strength. `state = 2` remains an unverified enum, and is now moot — the database was
purged wholesale regardless of what that field meant.

### ⚠ The same run exposed a wart in the fix, now corrected

The "post-exit" sweep fired **one second after** the pre-launch one, *before the game had mounted its
paks*. Cause: **`& $exe` does not block** — the shipping exe detaches and returns in ~1 s. The call
was pure duplication under a misleading name.

**Removed rather than repaired.** Blocking to wait for the game to exit would break CLAUDE.md's
hands-free tutorial recipe, which requires `launch-redirect.ps1` to return promptly so
`fk24-stage.ps1` can run in a second terminal. The pre-launch sweep is sufficient and provably so:
a launch is the only destroyer, and at pre-launch time `Saved\Logs\Loki.log` is **still the dead
session's log** (UE rotates at startup), so it captures the correct untruncated log for the death it
is archiving. To get a dump into `dumps\` without waiting for the next launch, run
`configs\archive-crashdumps.ps1 -Label <tag>` by hand.
