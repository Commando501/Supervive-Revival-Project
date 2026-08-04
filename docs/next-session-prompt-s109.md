# S109 — FK-9: make the invisible deaths visible, and open the one you already have

**Read this whole file before touching anything.** Everything below was measured live on 2026-08-04
(S108) and is committed on `dedicated-server-stub` (`7ef26c0`..`df8bc12`, all pushed).

**Subagent cap: 3 for the session.** Guidance in §6.

---

## 0. Why FK-9, and why now

FK-9 is not interesting for its own sake. It is interesting because **it is the instrument that is
blocking FK-7 and FK-24.** Both are stuck on the same sentence: *the tutorial run dies within ~1–5
minutes and we cannot say why.* S108 established that those deaths are not silent at all — they
produce a **full minidump plus their own `Loki.log`**, in a directory nobody in ~108 sessions has
looked at. The project's entire crash-forensics instrument (`tools/crashtri/harvest.py` and every
hand-rolled `Get-ChildItem Saved\Crashes`) enumerates `UECC-*` directories and is **structurally
blind** to them.

Consequence, and it is load-bearing: **every claim in the record of the form "N of 87 dumps show X"
has a denominator that excludes this entire failure mode.**

Current FK-9 text: `docs/ignorance-map-s101.md` (the entry carries an S108 banner — read it).
Governing evidence: `docs/s108-skeptic-review.md` §"POSITIVE CONTROL".

---

## 1. ★ TASK ONE — an unattributed crash dump is ALREADY PRESERVED for you. Open it.

**S108 preserved it at the end of the session** (it was 54 minutes old and still live, so it was not
worth gambling on it surviving until you started):

```
dumps\s109-sentry-20260804-1410\           <- YOUR COPY. SHA-256 verified against the source.
  reports\41cdafa3-ceff-4d83-8d11-69fa9b75b54a.dmp            43,804,912 B
  attachments\41cdafa3-…\Loki.log                              7,409,557 B   <- the run's OWN log
  attachments\41cdafa3-…\__sentry-event                            3,041 B
  <uuid>.run\…envelope, metadata, settings.dat, last_crash
```

Source of truth it came from (may be gone by now — check, the answer is itself a Task-Two datum):
`G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\.sentry-native\`.
`last_crash` = `2026-08-04T19:10:26.633000Z` (14:10:26 local).

⚠ **`/dumps/` is git-ignored**, so this copy exists on **this machine only** and is not recoverable
from the remote. Do not delete it. If you need it elsewhere, move it deliberately.

⚠ **`__sentry-event` is MessagePack, not JSON, and it carries NO stack trace.** MEASURED: it holds
event id, `level=fatal`, and tags/contexts — `BuildVersion=release2.4.live-156430-shipping`,
`BuildCL=156430`, CPU/GPU/OS, `Configuration=Shipping`, `Is game=True`. That is genuinely useful for
**attributing the dump to a build and run**, and useless for frames. **The frames must come from the
`.dmp`.** (Sentry renders stacks server-side from the minidump, so do not go looking for one here.)

### What this dump IS — and this is the point

It is **the death of the `nostatictest` bisect arm**, the run that lived longest (>301 s) and that
`docs/s108b-ksmactor-bisect.md` §2 explicitly records as **unattributed**. It is a death of the
**current candidate build** on the **current tutorial route**. Nothing else in the corpus is.

⚠ It is **13.7 MB larger** than a `UEMinidump.dmp` (43.8 MB vs ~13 MB), so do not assume
`tools/crashtri/*.py` will parse it identically — they were written against the UE ones. Check
stream presence before trusting any output. `__sentry-event` is ~3 KB of JSON and may hand you the
exception and a stack **with no tooling at all** — read it first, it is the cheapest thing here.

**Deliverable:** name the frames, name the faulting thread, and state whether this death is
(a) FK-7 Family A or B, (b) the S108 "new family" (`f96a8e f9ce6a 3eeedd4 3ef3e65 39c76c6 37f8b8c
4028924 403005f 40300da 4030f6c 4039696 751ef62`), or (c) something else. Then say plainly whether
it attributes the ~1–5 min tutorial death or not.

---

## 2. TASK TWO — make the capture durable, and prefer the fix that needs no watcher

Two competing observations, and **resolving which is true is the task**:

| observation | source |
|---|---|
| a dump was uploaded-and-deleted within **~3 minutes** | S108 skeptic, MEASURED at 02:17:16 |
| a dump survived **54 minutes** untouched | this file, MEASURED at 15:04 |

**INFERRED (test it, do not assume):** retention is **upload-conditional**, not time-based — the
first was deleted *because its upload succeeded*, the second persisted *because its upload did not*.
If that is right, the whole problem is solvable without any watcher.

Three candidate fixes, cheapest first. **Prefer the one that removes the race rather than winning it:**

1. **Break the upload.** If the DSN host is unreachable, crashpad keeps the report forever. The
   project already owns the hosts file (`launch-redirect.ps1`) and already redirects two domains.
   Find the Sentry DSN host — `__sentry-event` and `.sentry-native\settings.dat` are the obvious
   places, and the packaged `tools/extractor/out/DefaultEngine.ini` is where `[/Script/Sentry.*]`
   settings would live (**MEASURED: `Loki\Config\*.ini` contains ZERO `Sentry` hits**, so it is not
   there). Add it to the hosts block. ⚠ Verify this does not stall the crash path — a blocking
   upload attempt to a dead host could add a timeout to every death.
2. **Disable Sentry entirely so UE's own handler writes a `UECC-*` dir again.** This is the *best*
   outcome if it works: it converts these deaths into ordinary corpus members with callstacks in
   `Loki.log`, and every existing tool works unchanged. The launcher already passes `-ini:` overrides,
   so this is a one-flag experiment. ⚠ **Unknown whether UE's handler takes over or the crash simply
   goes unreported** — that is the thing to measure, and a negative here is cheap.
3. **A watcher** (`FileSystemWatcher` or a 5 s poll on `reports\`) that copies dumps out immediately.
   Robust, but it is winning a race rather than removing it. Do it only if 1 and 2 both fail.

**Whatever you choose, prove it with a positive control:** cause a death, then show the artifact is
still on disk five minutes later. Do not ship "it should work now."

---

## 3. TASK THREE — recompute the denominator

Once capture is durable, the corpus statistics need re-deriving, because they were all computed on a
biased sample.

- **MEASURED, and it is the free part:** `handing control over to crashpad` in a session's `Loki.log`
  is **anti-correlated 6/6** with the existence of a `UECC-*` directory. So you can classify **every
  archived session** offline, right now, with one grep over
  `%LOCALAPPDATA%\SUPERVIVE\Saved\Logs\Loki-backup-*.log` plus the `Loki.log` inside each of the 87
  `UECC-*` dirs. That yields the true count of crashpad-only deaths in the record.
- Then state, in one table: total deaths, UECC deaths, crashpad-only deaths, deaths with neither
  (if any survive — that class may be empty, which would itself close a long-running loose end).
- **Re-check every "N of 87" claim that steers something.** The ones that matter live in
  `docs/fk7-crash-settled.md` §0 (the 1-in-3-to-1-in-2 base rate, the 5-dumpless-deaths analysis,
  the "only 5 of 86 dumps capture an `APlayerCameraManager`" negative control) and
  `tools/crashtri/crash_census.csv`.
- ⚠ **Two dumps must be EXCLUDED from any FK-7 tally**: `166396E2` and `FED1F952` are the FK-24 probe
  killing its own host, not game crashes (`docs/s108-crash-triage.md`, `docs/s108-fk24-instrument-corrected.md`).

**Do not** rebuild `harvest.py` into a general tool before knowing whether the answer changes
anything. Compute the numbers first.

---

## 4. If capture works, the payoff is immediate — spend it

FK-7 and FK-24 are both one attributed death away from moving. If Task 1 or Task 2 yields frames:

- **FK-7:** the run plan is in `docs/s108-fk7-verification-attempt.md` §5. ⚠ **Hold to T+220–250 s,
  NOT T+300 s** — the integrity kill lands at ~285 s and would masquerade as the outcome. The
  `play_novtguard` positive control is **mandatory** and **≥3 controls** are needed; a quiet control
  means the sitting is VOID, not a pass.
- **FK-24:** the writer is still unnamed. **Do not escalate watchpoint modes** — S108 proved the
  `wprobe`→`wprobe2` escalation was triggered by a non-event. The real blocker is that the positive
  control never fires; the fix is to sample `vtHits`/`selfPhase` from the **30 s census** rather than
  the one-shot 8 s line, and to get the selftest to run at all.

---

## 5. The launch recipe has changed — read `CLAUDE.md` → "Tutorial sittings"

Sittings are **hands-free** now. Short version:

```powershell
# server/internal/interactive/interactive.go -> const forceTutorialMatch = true, then rebuild ags
.\configs\launch-redirect.ps1 -NoHook
.\configs\fk24-stage.ps1 -Probe tools\sigbypass-mod\build\tutorial_launch_play.dll -Label s109r1
```

**Set `forceTutorialMatch` back to `false` when done.** Traps, all paid for with dead runs:
`-Hook <play dll>` **cannot** work (`RM_PLAY` is a continuation mode); `gft_ready_fix` goes **before**
the force-open; gate on `Load map complete /Game/…/LVL_Tutorial`, not the bare string; wait for
`[SP] done step=4`. **Only ~2 of 4 launches reach the armed window** — budget on armed windows, not
launches. ⚠ `a67239a0d83d9300` is **no longer** `play` (S108b flipped `KSTATICTEST`); `play` is now
`ae532866e15fd8ac` and `a67239a0` is the `play-statictest` control.

---

## 6. Subagents — cap of 3

Live work (launching, injecting, reading markers) is **serial and stays on the main thread** — one
game process, one marker file. Spend the three on offline work that runs while a launch is in flight.

| # | Use it for | Not for |
|---|---|---|
| 1 | **Open the preserved dump** (Task 1) — parse it, name the frames, classify the family | anything touching the running game |
| 2 | **The denominator re-audit** (Task 3) — it is pure log/CSV work over ~87 dumps + all archived logs | producing the conclusion agent 3 will check |
| 3 | **Adversarial verification** of whatever Tasks 1–3 conclude — the highest-value slot | speculative exploration |

Do **not** spend an agent re-deriving what is written down. `docs/s108-*.md`, the six `fk*-settled.md`
files, `docs/coverage-audit-s101.md` and `docs/ignorance-map-s101.md` exist so nobody re-does that.

---

## 7. ★ The rule that matters most

FK-9 exists **because a census tool's blind spot became a fact about the game.** S108 then added
three more instances of the identical error — two of them inside the document written to catalogue
it, and one is the reason this session exists at all: I searched `%LOCALAPPDATA%\SUPERVIVE` and
`%APPDATA%\SUPERVIVE` for crash artifacts, found none, and reported "no dump was written." **The
dumps were in the GAME directory.** The search was correct and the conclusion was false.

So, non-negotiably:

- **Write the instrument's blind spot next to every negative result.** "No dumps" means nothing
  without "searched these two roots, these extensions, >1 MB."
- **Run a positive control before believing an absence.** The 43.8 MB dump in §1 is what a positive
  control looks like: it turned "no dump exists" into "I was looking in the wrong place."
- **A true statement about one artifact is not a statement about a technique.**
- **Fix causes, not displays.** S108 clamped a census timestamp's *printed value* while leaving the
  *trigger* underflowing, which hid the symptom and preserved the bug.
- **When a census returns a suspiciously round or small number, question the key you grepped for.**

`memory/supervive-instrument-artifact-pattern.md` now carries eight confirmed instances. Read it.

---

## 8. Housekeeping

- Branch `dedicated-server-stub`, everything pushed through `df8bc12`.
- `certs/` is now git-ignored; `ags` regenerates the chain on first run. Don't re-add it.
- **`ags` must be running** for any live work. Steam must be running before the game, or login dies
  with `Auth Failure 14005`.
- Restarting `ags` manually (not via the launcher) preserves the certs; the launcher wipes them.
