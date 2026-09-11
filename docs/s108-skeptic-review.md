# S108 — adversarial review of `s108-fk24-instrument-corrected.md` and `s108-crash-triage.md`

**Date:** 2026-08-04 · **Role:** adversarial skeptic (goal = refute, not confirm)
**Scope:** read-only. No game touched, no injection, no process killed, nothing under
`tools/sigbypass-mod/` or `server/` modified. Only this file was written.

Every claim is tagged **MEASURED** or **INFERRED**. Every negative carries the instrument's blind
spot. Positive controls are run before any absence is believed.

---

## Verdict table

| # | claim | verdict |
|---|---|---|
| C1 | S107's `selftest FAIL … the watchpoint is VOID` was wrong; the DR watchpoint was live | **SURVIVES in the weak form, REFUTED in the headline form** ("live *the whole time*") |
| C2 | force-open dies silently ~2 of 3, leaving **no UE dump** | **REFUTED** — on the dump, on the count, and on the phase |
| C3 | `forceTutorialMatch=true` substitutes for START **exactly** | sub-claim ("no other reader") **SURVIVES**; "exactly" **NOT ESTABLISHED** |
| C4 | `vtHits=1` proves VtGuard does not run post-init; falsifies the `DoTopDownCam` re-assert | **REFUTED OUTRIGHT** — and it is itself an instrument artifact |
| C5 | the S107 crash was our own instrument killing the game | **SURVIVES**, and is now confirmed by a second, independent mechanism |

---

## C4 first — it is the biggest error, and it is the pattern the doc claims to be fixing

### C4.1 The counter is narrow (the suspicion in the brief is correct)

`g_wpVtHits` is incremented at `tutorial_launch.cpp:1661`, i.e. inside `#if KVTGUARD`, **after**
`if(!VtResolve(pc)) return;` (`:1630`), **after** the 4 Hz `GcAlive` stand-down `return` (`:1652`),
**after** `if(!SafeReadable(slot,8)) return;` (`:1659`). (MEASURED, source.) So it counts *VtGuard
entries that reached the selftest call site*, not *VtGuard ran*, and it under-reports PI-hook cadence
by construction.

### C4.2 But the fatal defect is SAMPLING, not the counter

**MEASURED.** In both runs the *only* readings of `vtHits` are the one-shot
`[WP] selftest NOT-YET at 8000 ms` line and (DR mode only) a `census t=+0s` line.

* `docs/fk24-run-wp2r2-probe-retry.txt`: the NOT-YET line is at **line 89**;
  `[PL] *** init complete: body=BUILT; camera + WASD active ***` is at **line 128**.
* `docs/tutorial-launch-marker.txt` (run `wpDRr2`, 02:10): `census t=+0s … vtHits=1`, then the
  8000 ms line, then `[GC] …`, `[FOW] …`, `[PL] body built`, `[XF] …`, `[QST] …`, `[SMA] …`.

⇒ **every `vtHits` sample in the record was taken BEFORE the one-shot init finished.** There is no
post-init sample in either run. §2's *"MEASURED across two runs: after RM_PLAY's one-shot init
completes, `vtHits` did not advance past 1"* is therefore **not measured**: it is a pre-init reading
recorded as a post-init property of the game. That is the project's dominant error mode, in the
section written to correct it.

### C4.3 And the direct disproof was already in hand — twice

`WpSelfTestTick` has exactly one call site, `VtGuard:1662`, one line after the `vtHits` increment. So
**every entry into `WpSelfTestTick` increments `vtHits`.**

**Dump `FED1F952…` (MEASURED, and this is the *same run*, `wp2r2`, that §2 draws its conclusion from):**

| field | value | cross-check |
|---|---|---|
| `ErrorMessage` | `EXCEPTION_ACCESS_VIOLATION writing address 0x2bd733eaee0` | == `[WP] target &VT.Target=0x2BD733EAEE0` in that run's own marker |
| `rip` | `0x2BC61F9C09A` | inside that run's `self(this DLL)=0x2BC61F90000..0x2BC61FE8000` ⇒ **shim+0xC09A** |
| bytes @ rip | `4C 89 33 31 C0 87 05 8B 34 03 00 B8 01 00 00 00` | `mov [rbx],r14` / `xor eax,eax` / `xchg [g_wpSelfStore],eax` / `mov eax,1` = `WpSelfTestTick` phase 0 |
| `rbx` | `0x2BD733EAEE0` | == `g_wpAddr` — the store is *to the watchpoint* |
| `r14` | `0x2BD1EA5D560` | == the marker's `initialTarget=0x2BD1EA5D560` — the store is idempotent |
| frames 1,2 | `shim+0x5F41`, `shim+0x1076` | **byte-identical to `166396E2`** = `VtGuard`, then the PI-hook body |
| game tail | `UGameEngine::Tick → task graph → USkeletalMeshComponent::TickComponent → UObject::ProcessEvent → call [UFunction+0xE0] → our PI hook` | identical 23-frame chain |

The 8000 ms line printed `selfPhase=0` (store not yet executed); the store demonstrably executed
later. ⇒ **`vtHits` was ≥ 2.** `VtGuard` *did* re-enter after init, on the ordinary engine tick, with
a `VtValid` target. Dump `166396E2` shows the same thing in DR mode.

### C4.4 Consequences

* **FK-24a ("`VtGuard`/PI-hook does not run post-init … NEW, and it is the actual blocker") — REFUTED.**
* **FK-24c** — the "falsified pending re-measurement" verdict on `DoTopDownCam` re-asserting `&Target`
  must be **withdrawn**. `vtHits=1` never contradicted it.
* §2's *"The next fix is therefore not a new watchpoint mode. It is to drive `WpSelfTestTick` from a
  game-thread site that actually runs after init"* rests on the refuted premise. **The real blocker is
  that `WpHandle` does not claim the trap/fault and the probe kills its host — in BOTH modes.**
* **FK-24b ("`WpThread` stops in page mode") — NOT ESTABLISHED; two sufficient benign explanations:**
  1. the process was killed by its own probe, so a genuine +30 s census may simply never have been due;
  2. the S108 census fix clamped the **display** (`(now>=g_wpArmTick)?…:0`, `:2210`) but **not the
     trigger** (`now-g_wpLastCensus>=30000`, `:2203`). In DR mode `WpArm()` spends >1 s in the
     138-thread sweep, so `g_wpLastCensus` lands *after* the loop-top `now`, the subtraction underflows
     and a census fires immediately (hence `t=+0s` in `wpDRr2`). In page mode `WpArm()` is fast, no
     underflow, first census genuinely due at +30 s. **No stopped thread is required to explain either
     observation.** The underflow the doc says it fixed is still live in the trigger.

---

## C1 — the S107 VOID verdict

### C1.1 Ground (a) re-derived from source (MEASURED)

`WpSelfTestTick` (`:1596`): every early return — `g_wpSelfReq==0`, `!slot`, `!g_wpArmed`,
`!VtValid(v)` — is **above** the store. `g_wpSelfPhase` is set to 1 only at `:1607`, after the store
and after `g_wpSelfStore` is cleared. Call site is `VtGuard:1662`; the early returns above it are
listed in C4.1. So a live process reading `selfPhase==0` did not execute the store.

**But there IS a path the doc misses.** `WpArm()` `:1919` executes
`InterlockedExchange(&g_wpSelfPhase,0)` on **every** arm, and `WpThread:2149–2152` disarms and re-arms
on the *retarget* path whenever `g_vtPCM+g_vtOff != g_wpAddr` (which the S106c PCM-teardown stand-down
makes a real event). ⇒ `selfPhase==0` means **"the store has not executed since the last arm"**, not
"never executed". For S107 this is unfalsifiable — the marker was destroyed (FK-25). It does not
rescue the VOID verdict, but the doc's flat *"selfPhase=0 means the store never executed"* is
**overstated** and should read *"…not since the most recent arm"*.

### C1.2 Ground (b) re-verified independently (MEASURED)

I checked the arithmetic rather than the subagent's reading of it:

* `g_wpDr7Val = 0x00110005ULL` (`:579`). Dump `Dr7 = 0x110405`. `0x110405 = 0x110005 | 0x400`; bit 10
  is architecturally always set. Decode: `L0=L1=1`; `R/W0=R/W1=01` (write-only); `LEN0=LEN1=00`
  (1 byte). **Exact match.**
* `Dr6 = 0xFFFF0FF3` → low nibble `0x3` = `B0|B1`; bit 14 (`BS`) = 0; `EFlags = 0x206` → `TF` = 0.
  ⇒ a **data** breakpoint trap, not a trap-flag step. Correct as reported.
* `Dr0 = g_wpAddr`, `Dr1 = g_wpAddr+1`, matching `:1743`.

So the GameThread's DR did fire. **Independent, corroborating, not previously used:** the `wpDRr2`
marker (02:10) shows a clean DR arm on a *different* process —
`game-thread Dr7 before arming = 0x0`, `arm sweep#1 threads=138 armedOK=138 newly-armed=138
dr7ReadbackZero=0 failGet=0 failSet=0 openFail=0 preexistingDR=0 busySkipped=0 clearedSinceLast=0`.
DR viability on this build is not in question.

### C1.3 Are (a) and (b) independent, and how far do they reach?

They are independent *measurements* but not an independent *argument*. (b) is a snapshot at
**T+2550 s** in a process that took a later, unlogged shim injection at ~T+2480 s; it establishes the
DR was live **at that instant**, not at the +8 s FAIL. The same S107 run also printed
`W2: 1 thread(s) had our Dr7 bits CLEARED BY SOMETHING ELSE since the last sweep`. So:

* *"the S107 FAIL line asserted VOID while measuring something else"* — **SURVIVES** (both grounds).
* *"The DR watchpoint was live **the whole time**"* (§0 headline) — **REFUTED as written.** Not
  measured, and the run's own W2 line contradicts continuous coverage.

**Settling measurement if you want the strong form:** a run where `WpSelfWatch` prints
`selftest *** PASS ***` (i.e. `g_wpAnySelfTrap`) — which is exactly what the terminal-fallback fix now
prevents from ever being fatal, and exactly what no run has yet produced.

---

## C2 — "dies silently … leaving no UE dump"

### C2.1 The absence was measured with an instrument blind to the actual writer

**POSITIVE CONTROL, run before believing the absence.** At **2026-08-04 02:17:16** the Sentry crashpad
database held, for a crash that `Saved/Crashes` knows nothing about:

```
<GameDir>\Loki\.sentry-native\reports\1c5e7708-c575-4dc5-8e84-b8d4e6f47937.dmp     43,893,392 bytes
<GameDir>\Loki\.sentry-native\attachments\1c5e7708-…\Loki.log                       3,358,611 bytes
<GameDir>\Loki\.sentry-native\<uuid>.run\__sentry-event                                 3,041 bytes
```

By **02:20:11** `reports/` and `attachments/` were **empty** (MEASURED, two `ls` three minutes apart).
⇒ **"no UECC directory" is NOT "no dump".** The Sentry path writes a minidump **3.2× larger** than the
UE one, plus the log, and then **uploads and deletes it within ~3 minutes**. The dumps for the
"silent" deaths existed; nobody looked there, and by now they are gone.

### C2.2 The classification is clean, not mysterious — 6/6 anti-correlation

MEASURED across every crash on 2026-08-03/04 (`Saved/Logs/Loki-backup-*.log` vs `Saved/Crashes`):

| session (log backup) | `handing control over to crashpad` | `UECC-*` dir |
|---|---|---|
| 03.49.21 (S107) | **no** | **yes** — `166396E2` |
| 06.45.07 (`wp2r1`) | yes | no |
| 06.57.52 (`wp2r2`) | **no** | **yes** — `FED1F952` |
| 07.03.19 (`wpDRr1`) | yes | no |
| 07.10.53 (`wpDRr2`) | yes | no |
| 07.17.17 (live run) | yes | no (crashpad `.dmp` observed instead) |

The two crash handlers are **mutually exclusive**, and which one wins is a free, log-only
discriminator. The S107 session log also carries
`FPlatformMisc::RequestExit(1, LaunchWindowsStartup.ExceptionHandler)` at `03:49:21.024` — so the
triage's §2.3 conclusion ("the *bundled* `Loki.log` cannot carry the signal") is **correct and its
positive control was right**, and the fix is simply to read `Saved/Logs/Loki-backup-*.log` instead of
the crash-folder copy. That should replace "UNAVAILABLE" in the triage.

### C2.3 The count and the phase are both wrong

* **A fourth run exists that the doc omits.** `docs/fk24-stage-wpDRr2-{1..4}*.txt` (02:09–02:10) —
  gft → fo → sp → `tutorial_launch_play_wprobe.dll`. It **reached the world**, armed DR cleanly, and
  built the body (`tutorial-launch-marker.txt`, 02:10). It postdates the write-up (02:08) by ~2 min,
  so the doc is stale rather than wrong-at-time-of-writing — but the record now reads **2 of 4**, not
  1 of 3.
* **`wpDRr2` did not die "during LVL_Tutorial load".** Its last game-log line is
  `07:10:52.194 Calling SetStaticMesh … Mobility is Static` (the shim's `KSMACTOR` block) and death is
  **0.83 s later**, long after the world was up.
* **`wp2r2` did not "survive".** It crashed at 01:57:52 and produced `FED1F952` — killed by its own
  probe (C4.3). §3.3's row is wrong.
* ⇒ **4 of 4 (5 of 5 including the live run) force-open attempts on 2026-08-04 ended in a crash.**
  The doc's "~1 in 3 armed windows" run-budget arithmetic rests on a 3-row table with a mis-scored row.

### C2.4 Is FK-26 new? No — it duplicates a filed item

`fk7-crash-settled.md` §0.3 already records **5 dumpless deaths** and already makes the
denominator point ("`Marker()` opens `CREATE_ALWAYS` … Two sessions are now permanently
mode-unattributable. Split out as **FK-25**"). §0.3 dismissed those 5 *as FK-7 evidence* ("all 5 lack
the necessary antecedent — the mesh build"), which is a scope judgement, not a claim that dumpless
deaths do not happen. FK-26 **duplicates the observation and re-scopes it to run budgeting** — a
legitimate move, but it is **not NEW**, and calling it new re-opens a filed item under a second name.
Merge FK-26 into FK-25/§0.3 with the crashpad location and the 3-minute retention window attached.

### C2.5 §3.2's ordering fix has almost no discriminating evidence

MEASURED: `gft` **after** fo → 1 run (`wp2r1`), died at load. `gft` **before** fo → 3 runs
(`wpDRr1` died at load; `wp2r2` and `wpDRr2` reached the world). And the
`ULokiGameFeatureToggles::Get <X> called when feature toggles were not ready` errors that §3.2 uses as
its signature are present in **every** run right up to death, **including both runs that reached the
world**. So they are not the discriminator §3.2 treats them as. Keep the ordering (it is harmless and
principled) but drop the ★ and the "removes the race" wording.

---

## C3 — `forceTutorialMatch` vs the START button

**MEASURED (grep over `server/`, all files):** `SoloMode` is read in exactly **one** place —
`internal/interactive/interactive.go:588`, `active := forceTutorialMatch || (st != nil && st.SoloMode != "")`
— and written in exactly one place, `:872`. Declared at `store.go:66` with `json:"-"`. The only
non-`.go` hits are the compiled `ags*.exe` binaries. **The "no other reader" sub-claim SURVIVES.**
*(Blind spot: grep was literal-token `SoloMode`, case-sensitive, over `server/` only; a reader that
reconstructs the field by reflection or a different name would be invisible.)*

**"Substitutes … EXACTLY" is NOT ESTABLISHED.** Three differences, all MEASURED:

1. **A backend side effect the flag path does not have.** `handleStartSoloMode` calls
   `s.store.update(...)`, and `store.update` does `s.partyVer++` and `saveLocked()`, then the handler
   returns `buildSoloParty(… s.store.partyVersion())`. Per `CLAUDE.md`, `FParty.Version` is the strict
   monotonic gate on `UPartyModel::SetParty` — so the button press **publishes a new party version**
   and the flag does not.
2. **The whole client-side solo-start state machine is skipped.** The press runs
   `PartyManager.TryStartSoloMode` → `OnStartSoloModeComplete` → `OnJoinQueueSuccess`; the flag runs
   none of it. The same source file says so at `:848–850`.
3. **Sequencing differs materially.** With the flag, the match is reported **from login**:
   `06:48:07 LogTravelManager: Attempting to travel to Match` — **before** `06:48:11 Browse
   LVL_LobbyV2_Persistent`. The press can only occur after the lobby is up and a hero is picked. The
   doc's own observation that this is "far faster than the ~1/min poll the source comment predicts" is
   itself evidence the two paths are not identical.

Equivalent in one respect: the `mode` string (`tutorialNew`) is discarded on both paths, since `:588`
only tests non-empty. **Correct claim:** *`forceTutorialMatch` is **sufficient** to reach the parked
match state without a human; it is not identical to the press.*

---

## C5 — "our own instrument killing the game"

**SURVIVES.** `166396E2` is `STATUS_SINGLE_STEP` — an exception type that, at that RIP, only the
probe's own debug registers can produce — at the probe's own instruction, with the probe's own
`Dr7`/`Dr0`/`Dr1`, `Dr6=B0|B1`, `TF=0`, `rbx==Dr0`. There is no "incidental to a crash that was
happening anyway" reading available: the instruction is identified byte-for-byte and it is ours.

**The page-mode reproduction does NOT refute it — it confirms the class by a second mechanism.**
`FED1F952` (KWPROBE=2, no debug registers) is `0xC0000005 writing 0x2bd733eaee0` — the probe's own
`g_wpAddr` — at the **same** `WpSelfTestTick` phase-0 store, in the same function, reached through the
same `VtGuard` ← PI-hook frames. Different exception code because the trap mechanism differs
(PAGE_READONLY fault vs DR trap); same instrument, same instruction, same self-inflicted kill.

The shared 12-frame tail is exactly what the triage §3.3 **predicted** ("this 23-frame tail is simply
how the hook gets called, and it will appear under every shim-side fault taken from `VtGuard`"). The
reproduction is a confirmation of that prediction, not a counter-example.

### C5.1 Two corrections the triage and the write-up both need

1. **The "two shim images / split ownership" explanation (triage §2.4a, write-up D-S108-3) is not
   supported in the `FED1F952` case.** The faulting RIP is inside the *same* image that logged the arm
   (`self(this DLL)=0x2BC61F90000..0x2BC61FE8000`). A single-image probe self-kills too, so a second
   image cannot be the general cause.
2. **★ The D-S108-3 terminal fallback is `#if KWPROBE==1` only** (`tutorial_launch.cpp:686`).
   **Page mode has no terminal fallback at all.** So `tutorial_launch_play_wprobe2.dll` and
   `…_wprobe2_v66.dll` still carry the process-killing gap, and §4's ⚠ (which warns only about the two
   174,080-byte `wprobe*` builds) is incomplete. One of the wprobe2 builds demonstrably killed its host
   on 2026-08-04.
3. Related, and the real open question: in page mode the marker records **zero traps** while the page
   was `PAGE_READONLY` with `covered=1`, on a page the source itself says `ViewTarget.POV` is written
   to **every frame**. Either `CrashVEH`/`WpHandle` was never reached or it declined everything. That
   — not "`WpThread` stopped" — is what FK-24b should be re-filed as.

---

## Things neither document noticed

1. **A death signature shared by 3 of 3 runs that got past the body build.** The last game-log lines
   before death in `166396E2`, `wp2r2` and `wpDRr2` are identical in shape:
   `FlushAsyncLoading(2523)` → `ComponentEncroachesBlockingGeometry_WithAdjustment … StaticMeshActor_…`
   → `Calling SetStaticMesh … but Mobility is Static` — the shim's own `KSMACTOR` block — then 0.8–10 s
   of silence, then death. `fk7-crash-settled.md` §0.4 already warns that `KCHEATSPAWN` / `KSMACTOR` /
   `KSTATICTEST` are still ON in the candidate and execute in the +0.15 s window. Two of those three
   deaths are proven/strongly indicated to be the probe, so this may be coincidence — but it is the
   cheapest available bisect and it is free (`-DKSMACTOR=0`).
2. **The census-trigger underflow is still live** (C4.4 item 2). The S108 fix clamped the printed value
   only.
3. **`forceTutorialMatch` is still `true` on disk** (`interactive.go:555`), as §3.1 says it should be
   reverted after the sitting.
4. **Crashpad artifacts are transient (~3 min).** If a "dumpless death" is worth diagnosing, the
   capture window is *immediately* after the crash, at
   `<GameDir>\Loki\.sentry-native\reports\*.dmp` + `attachments\<uuid>\Loki.log`. A one-line
   copy-on-detect in `fk24-stage.ps1` would end FK-26 as an evidence problem.

---

## What I could not settle

* Whether the S107 run re-armed (and thus reset `selfPhase`) before its +8 s FAIL — the marker was
  truncated (FK-25). Unrecoverable.
* Whether `wp2r2` lived ≥30 s armed. The process died; that alone is sufficient to explain the missing
  census, so FK-24b needs no exotic cause, but the exact arm→crash interval is not recoverable from
  what survives.
* Why `WpHandle` declined in either mode. This remains the single most valuable missing measurement,
  exactly as the triage §2.4 says — and the fix for it is now the actual FK-24 blocker, not a new
  watchpoint mode and not a new selftest call site.
