# tests — offline controls for the native shims

The project's first shim regression harness. `docs/ignorance-map-s101.md` gap F7 lists
"no shim regression harness" among the missing instruments; this is the start of one.

Everything here runs **standalone, offline, in its own process**. No game, no injection, no backend.
That is the point: a shim defect that can be reproduced without a live run costs minutes to fix
instead of a launch (and this project's expected yield is only ~2 armed windows per 4 launches).

## `scan_race_test.cpp` — the S111 `catalog_store_fix` scan fix

Reproduces the TOCTOU that crash-dump forensics attributed to `catalog_store_fix.dll`
(fault at `.text` RVA `0x205d`, ≥11 recorded process deaths — `docs/fk8-crash-timing-mined.md` §3.1).
A scan walks a `VirtualQuery` region snapshot while another thread decommits pages underneath it.

Both arms are compiled from **verbatim copies** of the real bodies — the pre-fix unguarded
`*(uintptr_t*)p` walk, and the post-fix `SafeCopy`/`ReadProcessMemory` chunked walk.

```bash
clang++ -O2 scan_race_test.cpp -o scan_race_test.exe -lkernel32

./scan_race_test.exe new norace    # control A
./scan_race_test.exe old norace    # control B
./scan_race_test.exe old race      # NEGATIVE CONTROL — must crash
./scan_race_test.exe new race      # the test
```

### Results, 2026-08-05 (S111)

| arm | race | outcome | reading |
|---|---|---|---|
| NEW | no | `SURVIVED … FOUND` | the fixed scan still finds the needle — "survived" is not "read nothing" |
| OLD | no | `SURVIVED … FOUND` | the harness is fair; both arms locate the same needle |
| **OLD** | **yes** | **`Segmentation fault`, exit 139** | **the negative control FIRES — the shipped code really does die on this** |
| NEW | yes | `SURVIVED, shredded=1` | the fix holds under the identical race |

⚠ **The negative control is the load-bearing arm.** The first version of this harness had the
needle placed where the scan found it before reaching the shredded pages, so the OLD arm survived
and the whole test read as a pass. By this project's own rule a quiet control means the run is
**VOID, not a pass** — the harness was rebuilt to coordinate the shredder against the scan
(`g_walking` publishes the region under walk) and to put the needle at the far end so the walk
cannot short-circuit. Re-check that arm still segfaults before trusting any future result here.

`found=0x0` in the NEW/race arm is correct, not a failure: the needle sits in the tail that was
genuinely decommitted, so there is nothing left to find. Control A is what proves it still finds.

### Cost of the fix (same harness, 512 MB region, avg of 3, includes process startup)

| chunk | time |
|---|---|
| old unguarded | 275 ms |
| 16 KB | 391 ms |
| 64 KB | 356 ms |
| **256 KB (shipped)** | **338 ms** |
| 1 MB | 329 ms |

256 KB is the knee — past it the gain is ~3 % for 4× the `.bss`. Net ~1.2×, on a background thread.

### What this harness does NOT establish

- It does **not** show the fix removes the crash family **in the game**. That needs a live run with
  the 11-death baseline to test against. Nothing here substitutes for it.
- It exercises the scan in isolation, not the shim's other paths (the `jz` patch/restore, the
  slot-110 hook, `PokeAllPurchasable`'s direct writes — the last of which is a documented,
  deliberate residual, see the comment in `catalog_store_fix.cpp`).

## S147/S148 focused controls

Run these from this directory. They are standalone controls; none launches or injects SUPERVIVE.

```powershell
clang++ -std=c++17 -O2 s147_natural_state_test.cpp -o s147_natural_state_test.exe
.\s147_natural_state_test.exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\s147_input_plan_test.ps1

clang++ -std=c++17 -O2 s148_damage_calibration_test.cpp -o s148_damage_calibration_test.exe
.\s148_damage_calibration_test.exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\s148_build_contract_test.ps1
```

Required terminal lines:

```text
PASS s147_natural_state_test
PASS s147_input_plan_test
PASS s148_damage_calibration_test
PASS s148_build_contract_test
```

The S147 controls exercise the natural-input state/receipt policy and the host input-plan contract.
The S148 C++ control exercises scalar preflight, owner-provenance facts, exact seed, and immediate/
delayed receipt policy. The S148 PowerShell control compiles the isolated alias, requires every
terminal marker and hardened source contract, and rejects legacy botfight-arm markers in the DLL.

These controls do not prove that a live reflected offset, UObject identity, native wrapper, input
dispatch, or damage pipeline behaves as expected in the game. Artifact verification, reproducible
canonical `.text` identity, legacy regression gates, and ultimately a fresh-process live receipt are
separate obligations.

## S150 capture-generation contract

Run from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/sigbypass-mod/tests/s150_capture_generation_test.ps1
```

This is an offline, temp-path-only contract for the S150 capture-generation helper and controlled
launcher seam. It archives both canonical capture segments without clobbering, keeps a fresh
canonical stream replacement-locked, accepts only the exact N-format generation token in the strict
creation window, and exercises exact fake-process success and cleanup. It also proves PID/start/path
drift is never stopped, every non-exact post-start inventory fails closed, and nonempty pre-start
`ags`/`go` inventories are refused before mutation without stopping anything. Real temporary-file
cases require strict, non-recursive certificate-directory clearing; revalidate the cleared root at
pre-start and the exact certificate triplet at admission; reject reparse-point roots and entries
without touching their targets; and reject locked/stale/unchanged certificate artifacts. Capture and
archive paths are pinned to ordinary bases, reject reparse source/parent/archive components before
mutation, and still reject non-file canonical sources. A guarded fake continuation also proves every
terminating controlled pre-game failure stops only the exact pinned backend.
