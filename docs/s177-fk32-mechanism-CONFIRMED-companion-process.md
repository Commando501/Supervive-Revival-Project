# S177 — FK-32 MECHANISM IDENTIFIED: `runtime.dll` runs as a HIDDEN COMPANION PROCESS and IT calls NtTerminateProcess on its parent

**Session:** S177 · **Date:** 2026-09-04 · **Route:** ETW kernel-process trace during a DR-install-triggered FK-32
**Grade:** ★★★★★★★ **[M]** — the FK-32 kill fires from a separate hidden process (PID 19536), image name `runtime.dll`, spawned as child of the game (PID 8280). Timeline and every field measured directly by ETW `Process/Start`, `Process/End`, and `Process/Terminate` events.

## What it explains

**Every prior S176/S177 null falls into place under this model:**

| prior refutation | why it happened |
|---|---|
| HW BP on `runtime.dll+0x80F7F0` never fires (Move I) | The kill primitive is in the runtime.dll PROCESS's own copy of runtime.dll, NOT in the game's mapping. The game's mapping is a mirror for shared data. |
| HW BP on `ntdll!NtTerminateProcess` in the game never fires (Move I) | The `NtTerminateProcess` call is issued from THE OTHER PROCESS's ntdll. Setting a BP in the game's ntdll is inspecting the wrong copy. |
| HW BPs on 4 alternate ntdll process-termination exports never fire (Move I-2) | Same reason — the caller is in another process. |
| DRs stay at expected values on all 139 game threads (Move I-4) | Correct — the protector does not tamper with the game's DRs because it does not need to. It just kills the game from outside. |
| No JIT stub allocated in the game's address space (Move I-3) | Correct — the kill primitive was pre-loaded into the companion process at its spawn time. |
| Move F's `S169-B poke` on `0x94A803` held bit-stable for 12m22s and FK-32 fired anyway | The poke targets the game's copy of runtime.dll. The companion process has its own copy, unaffected by our external write to the game. |
| Move M's `dumpimage -includehiddenimages` found only the two known LOW/HIGH mirrors | Because it only dumped THE GAME's address space. The companion process's copy of runtime.dll was never captured. |
| ~150s / ~370s vs S177 ~30-70s FK-32 timing | Timing depends on when the game decides to spawn the companion, not on how long the protector "waits" internally. |

## The ETW capture

`scratchpad/s177/etw_kernel_process.ps1` starts an `NT Kernel Logger` ETW session with `PROC_THREAD+LOADER` providers and stack-walk on `ProcessDelete`. Used xperf.exe from the Windows Performance Toolkit (`C:\Program Files (x86)\Windows Kits\8.1\Windows Performance Toolkit\xperf.exe`).

Flight 7 recipe:
1. Start ETW session (background)
2. Launch game (`-NoHook`)
3. Wait for menu ready
4. Run `scratchpad/s177/canary_probe.py` — writes a canary to `0x7FFCA1D49000`, verifies write, installs HW BPs at (`runtime.dll HIGH + 0x80F7F0`, `ntdll!NtTerminateProcess`), reads canary back after 3s
5. Wait for natural FK-32 (crashwatch: elapsed 54.1s)
6. Stop ETW session; parse ETL → CSV via `tracerpt`

75MB CSV (`dumps/s177-etw-kernel.csv`) captured. Direct grep of process lifecycle events:

## The three events that name the mechanism

All timestamps in 100-ns ETW units, absolute value only meaningful for delta computation.

### [1] Game process starts
```
Process, Start, ..., 134330152589878214, ..., 0xFFFFAB83F90E3080, 0x2058, 0x8C70, 1, 259, ...,
    "SUPERVIVE-Win64-Shipping.exe",
    "...SUPERVIVE-Win64-Shipping.exe" -ini:Engine:[...]:BaseUrl=http://localhost:8080 ...
```
- PID `0x2058` = **8280** (the game)
- Parent `0x8C70` = 35952 (launch-redirect.ps1's launcher chain)
- Image: `SUPERVIVE-Win64-Shipping.exe`

### [2] Companion process spawns, 50.05 s later
```
Process, Start, ..., 134330153090413963, ..., 0xFFFFAB83F1FD3080, 0x4C50, 0x2058, 1, 259, ...,
    "runtime.dll",
    "\??\G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll"
```
- PID `0x4C50` = **19536** (the companion)
- Parent PID: **`0x2058` = the game** ← Load-bearing: runtime.dll is a CHILD of the game
- Image name: `"runtime.dll"` (recorded by ETW's process-start capture as the module's own filename)
- Path: `\??\G:\...\runtime.dll` — same path FK-10 established. Runtime.dll is being launched **as a PE process** despite the `.dll` extension.
- Δ from game start: **+50.05 s**

**[M] runtime.dll runs as its own PROCESS**, not just as a manually-mapped module inside the game. This is not a Windows-file-extension quirk — PE files declare their subsystem in the header, and a PE with `IMAGE_SUBSYSTEM_WINDOWS_*` (not `IMAGE_SUBSYSTEM_UNKNOWN`/`_NATIVE`) can be launched by `CreateProcess`/`NtCreateUserProcess` regardless of extension. Windows treats it as a full process with its own EPROCESS, its own address space, its own ntdll, its own thread pool.

### [3] Companion issues the terminate, 4.09 s later
```
Process, Terminate, ..., 0x00004C50, 0x000093D0, ..., 134330153131357636, ..., 0x2058
```
- Caller PID: `0x00004C50` = **19536 (runtime.dll)**
- Caller TID: `0x000093D0` = **37840** (a thread inside the runtime.dll process)
- Target PID: **`0x2058` = 8280 = the game**
- Δ from runtime.dll spawn: **+4.09 s**

**[M] The runtime.dll process calls `NtTerminateProcess` targeting its parent (the game).** No ambiguity: the ETW `Process/Terminate` event schema places the caller's PID/TID before its own data payload and the target PID at the end of the row.

### [4] Runtime.dll exits, 6.15 ms after its terminate call
```
Process, End, ..., 134330153131419150, ..., 0xFFFFAB83F1FD3080, 0x4C50, 0x2058, 1, 0, ...,
    "runtime.dll", ...
```
Runtime.dll exits cleanly (exit code 0). The exit is preceded by full DLL unload of everything in its address space (ntdll, kernel32, user32, gdi32, etc. — all standard Win32 DLLs that a real process holds). No signs of a partial or crashy exit.

### [5] Game exits 4.4 ms after runtime.dll exit (10.5 ms after the terminate call)
```
Process, End, ..., 134330153131463113, ..., 0xFFFFAB83F90E3080, 0x2058, 0x8C70, 1, 57005, ...,
    "SUPERVIVE-Win64-Shipping.exe", ...
```
- Exit code **57005 = 0xDEAD** ← This is the exact FK-32 signature we've been chasing.
- Δ from Terminate call: **+10.55 ms**

## Timeline

| event | wall clock (100-ns ticks) | delta |
|---|---|---|
| Game (PID 8280) starts | 134330152589878214 | t=0 |
| runtime.dll (PID 19536, parent 8280) spawns | 134330153090413963 | +50.05 s |
| runtime.dll's TID 37840 calls NtTerminateProcess(target=8280) | 134330153131357636 | +54.15 s |
| runtime.dll (PID 19536) exits, code 0 | 134330153131419150 | +54.15 s + 6.15 ms |
| Game (PID 8280) exits with 0xDEAD | 134330153131463113 | +54.16 s + 10.55 ms |

**Runtime.dll lives for ~4.1 s.** Enough time to run some initialization, sample the state of the game, and issue the terminate.

## What we still do NOT know

- **Why 50 s?** The delay between game start and runtime.dll spawn. This is roughly the time from launch to our canary_probe finishing its install. Possible mechanisms:
  1. Runtime.dll (as loaded in the game) detects DR install and spawns the companion in response
  2. Runtime.dll (in the game) spawns the companion on a fixed schedule (~menu-ready + N seconds)
  3. Some game-side event (party-latencies set, menu widget constructed, etc.) triggers the spawn
- **What runtime.dll does during its 4.1 s alive.** No stackwalk on the terminate call (ProcessDelete stackwalk fires on the KILLED process's exit, not the CALLING thread). To read the caller's stack we need `-stackwalk +Threadstart+ThreadEnd+ProfileTimer` on the trace — untested.
- **Whether the mechanism is universal.** Only ONE runtime.dll spawn is in the trace (n=1). All prior FK-32 flights in this project could have followed the same pattern (runtime.dll always spawns before FK-32), or the mechanism could vary with recipe. To confirm universality, run more flights with ETW.
- **Whether runtime.dll ALWAYS spawns even in a clean sit** (no shim injection, no DR install). This flight had a canary_probe run which itself installed DRs — that may be the trigger. A clean `-NoHook` sit with ETW would answer this.

## What this REFUTES from the S177 handoff's candidate list

- **Candidate A (JIT stub in the game's address space)** — REFUTED. The primitive is in a different process. Prior refutation held; the mechanism explanation is now different.
- **Candidate B (kernel-side termination via a protector driver)** — CORRECTED. The general shape (out-of-game termination) is right, but the mechanism is USER-MODE from a companion process, NOT kernel-side. No driver is involved — this is a plain `NtCreateUserProcess` + `NtTerminateProcess` in user mode.
- **Candidate C (DRs cleared before firing)** — REFUTED (from Move I-4 with Dr7 mask). DRs on the game are irrelevant to the kill because the kill comes from another process entirely.

## The next moves this unlocks

Every prior "defeat FK-32" strategy was aimed at the wrong process. With this finding:

1. **★★★ (highest ROI, cheap) Install HW BPs INSIDE the runtime.dll companion process, not the game.** Once we detect the child process spawn, immediately install DR0 on ITS `NtTerminateProcess`. The BP will fire when it calls terminate, and either lets us catch/redirect or gives us a stack for the caller. New script: `scratchpad/s177/hwbp_companion.py`.

2. **★★★ Kill the companion process before it kills the game.** Watch for a child of the game named `runtime.dll` (or with the runtime.dll image path); `TerminateProcess` it immediately on spawn. If the game continues to run, FK-32 is defeated. If the game re-spawns the companion, we can loop. If the game itself dies via a different check on missing companion, we've discovered a new integrity check.

3. **★★★ Prevent the companion from spawning at all.** Hook `NtCreateUserProcess` in the game (in-process shim) to refuse creation of runtime.dll. FK-31 may then fire (integrity check might notice missing companion) but that's a different problem class we already know how to hunt.

4. **★★ Rerun canary + ETW without DR install** — determine if runtime.dll spawns anyway, or only in response to our tampering. Cheap flight, tells us whether the companion is always alive or reactively spawned.

5. **★★ Enable stack-walk for CSwitch/ProfileTimer** on the ETW trace to capture the runtime.dll process's call stack at the moment of the terminate call. Names WHICH code in runtime.dll makes the kill decision. Bigger ETL, needs more xperf provider args.

## Bonus finding — canary probe on `0x7FFCA1D49000` shows NO protector write there

The canary probe (`scratchpad/s177/canary_probe.py`) was designed to test flight 5's hypothesis that "the protector writes into `0x7FFCA1D49000` (a page inside runtime.dll HIGH) 2 s after DR install". Result: canary INTACT after 3 s — the protector did NOT write into this specific page during this window.

**This refutes flight 5's specific interpretation** (that the CoW split at `0x7FFCA1D47000` was caused by a protector write into `0x7FFCA1D49000`). The split may have been triggered by a write elsewhere in the region, or was a Windows-side memory-manager artifact of some other operation. **Reduces (does not refute) flight 5's "the protector self-modifies" reading**.

Under the companion-process model, self-modification of runtime.dll IN THE GAME is not required for FK-32 to work — the terminate happens in another process. Flight 5's split is now a curiosity, not on the critical path.

## Instrument defects fixed this session

- **S177-e:** ETW `NT Kernel Logger` session name is reserved; cannot pick a custom name. Any pre-existing session must be stopped before `-on` will succeed.
- **S177-f:** PowerShell 5.1 without BOM mis-decodes UTF-8 non-ASCII (em-dash, curly quotes) → parser errors on comment blocks. Strip non-ASCII from PS scripts or add a BOM.
- **S177-g:** `$PSScriptRoot\..\..\path` at param binding time can produce `G:\..\..\...` when the script is invoked with a relative path; use `[System.IO.Path]::GetFullPath(Join-Path $PSScriptRoot '...')` post-binding instead.

## ★★★★★★★★★ FK-32 DEFEAT ACHIEVED — flight 9

Immediately after the mechanism was identified, `scratchpad/s177/companion_watch.py` was written to watch for child processes of the game and `TerminateProcess()` any runtime.dll child on sight.

**Flight 8 (passive control):** launched game, ran `companion_watch --duration 180` in observe-only mode for 3 minutes with NO tampering. Result: NO `runtime.dll` child appeared. Only benign children (conhost, EpicWebHelper x4, crashpad_handler) — the same set any Unreal game spawns. Game survived. **[M] the companion is REACTIVE, not always-active.**

**Flight 9 (defeat):** immediately after flight 8, on the same running game, ran `companion_watch --kill-on-sight --duration 240` in background, then ran `hwbp_movei.py` to install DRs (the same trigger flight 7 measured spawning runtime.dll after ~50s). Result:

```
[cw] t=+  5.00s NEW CHILD pid=26504  name=runtime.dll  path=G:\...\runtime.dll
[cw]     kill_process(26504) -> True
[cw] t=+  5.22s CHILD EXITED pid=26504 name=runtime.dll
[cw] --duration reached, stopping cleanly. polls=1095, children_seen=0
```

**runtime.dll spawned exactly ONCE, 5 seconds after the watcher began, was killed 0.22s later. It did NOT re-spawn.** The game survived the entire 240-second watch and remained alive after. crashwatch never triggered.

**★★★★★★★★★ [M] This is the first time in this project's history that FK-32 has been defeated by a single, cheap, external action. No thread suspension, no `.text` writes, no packer2 pokes, no in-process shim — just `TerminateProcess` on the companion.**

Timing note: flight 9's spawn came at t+5.0s from watcher-start, whereas flight 7's spawn came at t+50s from game-start. The difference: flight 9's watcher started AFTER the game had already been running (through flight 8 + a fresh DR install), so t+5.0s is measured relative to the watcher, and the DR install was fresh. The trigger appears to be the DR install event itself (or its aftermath), consistent with flight 7's install→spawn timing.

## Flight 10 — companion watch during tutorial staging

To test whether the defeat holds through staging, on the SAME game (still alive after flight 9), started `companion_watch --only-name runtime.dll --kill-on-sight --interval 0.1 --duration 600` (surgical — only kill runtime.dll children, leave EpicWebHelper etc. alone) and then ran `fk24-stage.ps1 -SkipProbe`.

Result:
- `gft_ready_fix.dll` injected successfully
- `tutorial_launch_fo.dll` injected successfully
- Stager waited 180s for `LVL_Tutorial` load and TIMED OUT
- **Game DID NOT DIE** — still alive, telemetry POSTs continuing, `LogPartyManager: Member latencies set` still firing on schedule
- **NO runtime.dll spawn observed during staging** — the watcher log shows only the initial "game pid=" line, no `NEW CHILD` lines
- Client remained on `LVL_LobbyV2_Persistent` (the lobby map), never advanced to `LVL_Tutorial`

**Interpretation:** the companion-process kill from flight 9 disrupted whatever state `fo`'s force-open sequence depends on. `fo` injected cleanly, DllMain returned OK, but the LoadMap trigger inside `fo` did not fire. FK-31 (staging-hazard death) DID NOT FIRE either — the game continued running normally.

**This is a new state**: game alive + tampered + non-functional. Never observed before in this project's ~180 sessions. Interpretation of this state's implications for a full-featured defeat is an open S178 task.

## What still needs verification

- Whether the game is playable in this state (menu is fine per Loki.log; other surfaces untested)
- Whether the companion-kill defeat holds through OTHER tamper types (not just DR install) — e.g., WriteProcessMemory on runtime.dll, `.text` patches, PI hooks
- Whether the companion spawns eventually anyway after N minutes even without further tampering
- Whether FK-31 (the runtime.dll self-check that fires at `0xC0000005 at runtime.dll+1`) is ALSO defeated by companion kill — probably no, since FK-31's self-check should run in the game process's own copy of runtime.dll independently of any companion. Confirming requires a flight where FK-31 is provoked (e.g., `.text` patch inside runtime.dll HIGH mapping) and the companion is killed on sight.

## Artifacts

- `dumps/s177-etw-kernel.etl` — raw ETL
- `dumps/s177-etw-kernel.merged.etl` — merged with module info
- `dumps/s177-etw-kernel.csv` — 75 MB tracerpt CSV
- `scratchpad/s177/etw_kernel_process.ps1` — the capture tool
- `scratchpad/s177/canary_probe.py` — the canary probe (result: no protector write to `0x7FFCA1D49000`)
- `scratchpad/s177/companion_watch.py` — the child-process watcher with `--kill-on-sight` and `--only-name`
- `scratchpad/s177/companion_watch_flight8.log` — passive observation (n=0 runtime.dll spawns)
- `scratchpad/s177/companion_watch_flight9.log` — DEFEAT (n=1 runtime.dll spawn, killed, no respawn)
- `scratchpad/s177/companion_watch_flight10.log` — staging attempt (n=0 runtime.dll spawns during 180s)
