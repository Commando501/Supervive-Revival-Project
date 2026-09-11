# S177 — Move I-3 (JIT stub) and Move I-4 (DR clearing) both REFUTED for early window; Candidate B (kernel-side) implicated

**Session:** S177 · **Date:** 2026-09-04 · **Route:** menu-only, no shim staging succeeded
**Verdict headline:**
- **[M]** Candidate C (protector clears DRs before firing FK-32) — REFUTED
- **[I, strong]** Candidate A (JIT-generated kill stub) — REFUTED for snapshots taken up to ~30 s post-DR-install; late-window (right before kill) UNTESTED due to snapshot/kill race
- **[I, strong]** Candidate B (kernel-side termination via protector driver) — remaining candidate by elimination; ETW subscription is the next-priority follow-up

## What was tested

Two S177 hypotheses from `docs/next-session-prompt-s177.md`:

- **Move I-3:** if the protector JIT-generates a `mov edx, 0xDEAD; syscall` stub in a fresh MEM_PRIVATE region at kill time, a `dumpimage` snapshot taken between "just before install" and "just before kill" should contain a new region with that byte signature.
- **Move I-4:** if the protector clears HW BPs on the FK-32 kill thread (targeted) or all threads (bulk) before firing, a periodic DR poll should observe `Dr0`/`Dr1` drift from the expected values before the kill.

Both were exercised on the same running client, `-NoHook` launches (no shim staging), no `.text` writes, no injection other than what S177's own `hwbp_movei.py` does (HW BP install via `SetThreadContext`).

## Flights

| # | purpose | kill class | elapsed | outcome |
|---|---|---|---|---|
| 1 | I-3, staged tutorial (`SkipProbe`) | FK-31 `0xC0000005` at `runtime.dll+1` | crashwatch: T+140.9 s after script arm | crashwatch dumped pre-death snapshot; 5 new PRIVATE RWX, zero DEAD bytes |
| 2 | I-3, staged tutorial (`SkipProbe`) | FK-31 `0xC0000005` | crashwatch T+~144 s | identical class as flight 1 — 5 new PRIVATE RWX, zero DEAD bytes |
| 3 | I-4, DR poll (unpatched script) | FK-32 `0x0000DEAD` | crashwatch: 60.9 s | 51/139 threads flagged as "drift" but the flag was Dr7 bit 10 = OS reserved-bit normalization, NOT tampering |
| 4 | I-4, DR poll (Dr7-mask patched) | FK-32 `0x0000DEAD` | crashwatch: ~30 s post-install | **139/139 threads clean at poll #1 (t+3 s); FK-32 fires anyway** |
| 5 | I-3 combined, snapshot t+2 s post-install | FK-32 `0x0000DEAD` | crashwatch: 72.3 s | Zero new PRIVATE RWX; 1 hidden-image RW page appeared (protector self-mod, not code); zero DEAD bytes |
| 6 | I-3, later-window snapshot (target t+30 s) | FK-32 `0x0000DEAD` | crashwatch: 67.8 s | Baseline OK; snapshot A raced against kill and lost — process gone at t=26 s |

Six live launches, all `-NoHook`, six process deaths — four FK-32 (`0x0000DEAD`), two FK-31 (`0xC0000005`).

## Move I-3 result — no JIT stub visible in early window

**Diff protocol:** take `dumpimage -includehiddenimages` before and after DR install, in the SAME process lifetime (ASLR base identical), diff by exact VA to identify NEW executable regions in the post-install snapshot. Scan any new region for the bytes `BA AD DE 00 00 0F 05` (`mov edx, 0xDEAD; syscall`) plus its 4 partial variants.

**Sampled windows:**

- FK-31 crashwatch snapshots (flights 1 & 2): capture happens ~2 s before actual kill. Both showed the same 5 new PRIVATE RWX regions and both scanned CLEAN:

  | VA | size | interpretation |
  |---|---|---|
  | `+shim_base` `0x25000` | 149 KB | our own `gft_ready_fix.dll` manual-map (matches stager log's `remote image base`) |
  | `+shim_base+0xC0000` `0x2C000` | 176 KB | our own `tutorial_launch_fo.dll` manual-map |
  | 3 × `0x1000` | 4 KB each | tiny Windows scratchpads (0 bigrams, 0 code bytes) |

  The tiny page at `exe_base − 0x10000` (`0x7FF67D450000` in both flights) appeared at a **fixed VA relative to the exe module base** across both flights — a static protector scratchpad tied to the exe module, not a JIT stub. Two agreeing lifetimes.

- Flight 5, t+2 s post-install: ZERO new PRIVATE regions of any protection; ONE new hidden-image page at `0x7FFCA1D49000` (`READWRITE`, no execute) — the region at `0x7FFCA1D47000` fragmented from `0x3000` → `0x2000` + new `0x1000` page. This IS a protector response to DR install (bytes changed in a mapped hidden-image page, forcing a CoW split), but it is DATA — no execute bit, and the scan found zero DEAD bytes in either fragment. **[M]** the protector wrote to itself within 2 s of our DR install; **[I,strong]** what it wrote was not the FK-32 kill primitive.

- Flight 6, attempted t+30 s snapshot: `dumpimage` failed with "process not found" — FK-32 fired between install (t+1 s) and the snapshot attempt (t+26 s), so the late-window snapshot is UNTESTED.

**⇒ Candidate A REFUTED for the 0–~5 s post-install window.** The 5-to-30 s window remains unsampled because of the snapshot/kill race. To close it, a successor needs either (a) a snapshot triggered on a shorter cadence than the FK-32 fire timing (challenging — timing is 30-70 s with variance across flights) or (b) an in-process snapshotter that runs inside the game (a shim, which changes the perturbation set).

## Move I-4 result — [M] no DR drift; Candidate C definitively refuted

Two DR-poll flights, both installing `Dr0 = runtime.dll HIGH + 0x80F7F0` (kill primitive) and `Dr1 = ntdll!NtTerminateProcess`, then polling `Dr0..Dr7` on every thread every 3 s.

**Flight 3 (unpatched):** 139/139 threads installed; poll #1 at t+3 s reported "51 drifted, 88 clean". Investigation of the drift lines revealed EVERY drift was `Dr7: expected 0x5 observed 0x405`. Bit 10 (`0x400`) of Dr7 is reserved-must-be-1 on x86-64 per AMD manual — Windows OR's it into any write to Dr7. **Not tampering.** Dr0 and Dr1 remained at expected values on all 139 threads. FK-32 fired at ~60.9 s.

**Flight 4 (Dr7-mask patched):** The `fmt_drift` function was updated to mask `DR7_RESERVED_MASK = 0x400` before comparing. Same install, same targets. Poll #1 at t+3 s reported **"139 clean, 0 drifted, 0 read-fail"** — every thread's `Dr0`, `Dr1`, and effective `Dr7` matched expected values. FK-32 fired at ~30 s. Session summary: `threads_clean: 139, threads_drifted: 0, drifted_tids_ever: 0`.

Combined with Move I / Move I-2 (S176) HW-BP no-fire on the same 2 addresses plus 4 alternate ntdll process-termination exports:

**⇒ [M] The protector does NOT clear DRs before firing FK-32. It also does not fire any of the 6 HW-BP-monitored kill paths.** Candidate C is refuted, and the "why did the BP not fire" question does NOT reduce to "DRs got cleared first" — Dr0 pointing at `runtime.dll+0x80F7F0` did NOT fire, and Dr0 was still pointing there at kill time.

## Bonus finding — the protector self-modifies within 2 s of DR install

Flight 5's diff exposed a specific self-write:

- **Baseline (0 s):** `0x7FFCA1D47000` `size 0x3000` `EXECUTE_WRITECOPY` (hidden-image page inside runtime.dll HIGH)
- **Pre-kill (2 s post-install):** same VA now `size 0x2000` + NEW `0x7FFCA1D49000 size 0x1000` `READWRITE`

The 12 KB region SPLIT into 8 KB + 4 KB, with the new 4 KB page carrying different (writable, non-executable) protection. This is a CoW split — a write into a `PAGE_WRITECOPY` page forces Windows to allocate a private copy for the modified page. The data content (all-zero on scan) suggests the protector cleared or zeroed a scratchpad; the DEAD-byte scan found nothing there.

**Interpretation:** the protector saw our DR install and modified its own state within 2 seconds. It did NOT allocate an executable stub. What it wrote is unknown, but the write location is stable and could be a target for a future data-write test (e.g., poke a canary into `0x7FFCA1D49000` before install and see what the protector does to it).

## FK-32 timing distribution (post-install)

Six data points, all `-NoHook` menu-only:

| flight | recipe | elapsed (crashwatch, total uptime) | approx post-install (my estimate) |
|---|---|---|---|
| 3 | DR install only | 60.9 s | ~60 s (poll caught alive at t+3 s, dead by t+33 s) |
| 4 | DR install only | ~30 s (measured by poll thread_count=0 at t+33 s) | ~30 s |
| 5 | DR install + 2 dumpimage snapshots | 72.3 s | ~70 s (snapshots done, then dead by later check) |
| 6 | DR install + baseline dumpimage + sleep | 67.8 s | ~24 s (game dead by the sleep 25 window's end) |

Range: 24–72 s post-install, **mean ~50 s, high variance**. This is inconsistent with Move I's earlier ~150 s and Move I-2's ~370 s — likely because S177 installs on ALL 139 threads simultaneously (highest-signal install pattern the protector would see), which the protector responds to faster than a slower/partial install.

**Rule to bank (S177-a):** *the FK-32 post-install timing is a function of install visibility. Bulk install on all threads → 30-70 s; single-target install → 150-370 s.* Whatever the protector's detection mechanism, it is at least partly rate-sensitive to the DR-install event rate.

## What this leaves for the FK-32 mechanism

Refuted (this session + prior):
- runtime.dll+0x80F7F0 kill primitive (Move F, Move I) — [M]
- ntdll!NtTerminateProcess (Move I) — [M-caveat, HW BP no-fire]
- ntdll!RtlExitUserProcess / NtRaiseException / NtRaiseHardError / RtlReportSilentProcessExit (Move I-2) — [M-caveat]
- Any byte-visible `mov edx, 0xDEAD` primitive in the process (Moves H, K, M) — [M]
- Protector clears DRs before firing (S177 Move I-4) — [M]
- JIT stub allocated in the 0–5 s post-install window (S177 Move I-3, flight 5) — [I, strong]

Still open:
- **Candidate A late-window:** JIT stub allocated in the 5-70 s window right before kill. UNTESTED. Snapshot-vs-kill race makes this hard.
- **Candidate B:** kernel-side termination via protector driver invoking `PsTerminateProcess` from ring 0. UNTESTED but IMPLICATED by elimination.
- **Candidate D (new this session):** protector uses the runtime.dll HIGH mapping's own self-modification path to trigger a kill via some indirect mechanism not observable from user mode. Flight 5's hidden-image self-write shows self-modification IS happening; whether it's causally connected to the kill is untested.

## Next moves, ranked

1. **ETW subscription for `Microsoft-Windows-Kernel-Process` events.** Discriminates Candidate B — if the FK-32 kill emits a `ProcessStop` event with `Terminator` naming a kernel-mode caller, B is confirmed. Requires an elevated ETW consumer and a small event-log daemon. Not offline.
2. **In-process snapshot shim.** Manually-mapped shim that pauses game threads and dumps its own process image via ReadProcessMemory in-process, triggered by an internal timer just before expected FK-32. Would give a late-window snapshot free of the external-snapshot race. Risk: injection itself changes the FK-32 timing.
3. **Data-write probe on `0x7FFCA1D49000`.** Write a canary before DR install; snapshot afterwards; see what protector overwrites it with. May reveal the mechanism behind the self-modification. Cheap, offline once the shim is written.

## Tools produced

- [scratchpad/s177/diff_snapshots.py](../scratchpad/s177/diff_snapshots.py) — parses two `dumpimage` manifests, classifies NEW regions into rank-1 (`MEM_PRIVATE|EXECUTE_READWRITE/WRITECOPY`), rank-2 (private-exec other), hidden-image, other. Warns on ASLR base mismatch. Writes `<parent>/s177_diff.txt` beside the pre-kill dir.
- [scratchpad/s177/scan_new_regions.py](../scratchpad/s177/scan_new_regions.py) — byte-scans specific `.bin` files for the 5-pattern DEAD set matching `scratchpad/s176/scan_hidden_for_dead.py`. Three modes: explicit filenames, `--auto BASELINE_DIR`, `--all`.
- [scratchpad/s177/hwbp_dr_poll.py](../scratchpad/s177/hwbp_dr_poll.py) — install DRs on all threads and poll `Dr0..Dr7` on every thread on `--interval` cadence. Log drift with `(elapsed, tid, register, expected, observed)`. `--reinstall` re-writes DRs after drift. **Dr7 reserved-bit-10 mask applied** (defect fixed after flight 3 caught the noise).

## Instrument defects fixed this session (banked for method-rules.md)

- **S177-a: Dr7 bit 10 reserved-normalize is not tampering.** Windows OR's `0x400` into Dr7 on write; comparing raw `Dr7` values without masking produces false-drift reports. Mask `DR7_RESERVED_MASK = 0x400` before comparing.
- **S177-b: the tail-of-Loki.log menu-ready detector is stale-signal-vulnerable.** `Get-Content -Tail 5` matches on a "party latencies set" line even from a prior session that got appended to. Gate the check on the current process's `StartTime` and only accept log timestamps that post-date it. (Fixed inline for flight 6 by parsing the log timestamp against `Get-Process StartTime`.)
- **S177-c: crashwatch's dumpimage-on-trigger requires a marker line and 0xDEAD produces none.** A pre-kill dumpimage must be taken by an external timer or in-process shim, not by crashwatch. Crashwatch's exit-code catch works but comes AFTER the kill.
- **S177-d: dumpimage races the game process's death.** A `dumpimage` started less than ~30 s before FK-32 may complete before the kill; started later, it hits "process not found". Any Move I-3-style flight must budget the snapshot inside the observed FK-32 timing distribution (24-72 s post-install, mean ~50 s, S177 measurement).

## Artifacts on disk

Dumps (in `dumps/`):
- `s177-baseline`, `s177-baseline2`, `s177-baseline4`, `s177-baseline5`, `s177-baseline6` — 5 baseline captures across the 6 flights
- `s177-prekill5` — the only successful post-DR-install snapshot (t+2 s, same lifetime as baseline5)
- `crash-20260904-110433`, `crash-20260904-110906` — the two FK-31 crashwatch pre-death snapshots

Logs:
- `scratchpad/s177/dr_poll_flight3.log` — unpatched DR poll, 51 spurious Dr7 drifts
- `scratchpad/s177/dr_poll_flight4.log` — patched DR poll, 139/139 clean, verdict `NO DR DRIFT`
- `docs/crashwatch.out.log` — running log of all crashwatch triggers (rolls per launch)
