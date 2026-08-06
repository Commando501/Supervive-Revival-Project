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
