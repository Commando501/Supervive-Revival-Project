# FK-8 — clustering and the real denominator

**Session:** 2026-08-05 · **Dimension 2** of the FK-8 corpus work.
**Inputs:** `docs/fk8-crash-corpus.csv` (139 rows, built stage 1 this session), plus a fresh
read of every minidump in the corpus.
**New tool:** `tools/crashtri/mdexc.py` — a READ-ONLY *lean* minidump reader (header + stream
directory + ModuleList + ThreadList + ThreadNames + Exception only; never touches memory
ranges, so it sweeps 131 dumps totalling ~2 GB in ~2 min). Everything below is reproducible
from it.
**Discipline:** every claim is tagged MEASURED / INFERRED / SPECULATIVE. Every negative is
scoped to the artifact class it was searched in. Nothing under
`C:\Users\eastr\AppData\Local\SUPERVIVE\Saved\Crashes` was written, moved or modified;
every file was opened `'rb'`. Post-run the tree still holds 92 directories.

---

## 0. Headline

**MEASURED. 34 of the 114 distinct death records in this corpus — 30 % — are not the game
crashing.** 21 are the anti-tamper protector deliberately killing the process
(`runtime.dll+1`, an EXECUTE access violation on a poison jump), 11 are **our own
always-injected `catalog_store_fix` shim's heap scan racing a decommit**, and 2 are the
already-known FK-24 watchpoint probe. The genuine-game denominator is **75**, not 92, not
106, and not 114.

**MEASURED. The single biggest classification error in the corpus is the unwind-failed
bucket.** Both existing keys — `harvest.py`'s first-3-game-RVA chain *and* UE's own
`PCallStackHash` — collapse all 16 no-game-frame rows into one bucket. That bucket
actually contains **three unrelated mechanisms** (protector kill / shim scan / one
jump-to-null), and only the minidump exception record separates them. This is the
instrument-artifact pattern again: the blind spot of the stack-based key was recorded as
"a family of crashes".

---

## 1. Part A — clustering by `PCallStackHash`, and whether it agrees with the incumbent key

`PCallStackHash` is a field in every `CrashContext.runtime-xml`. **MEASURED: no tool in
`tools/` reads it** (`harvest.py` does not extract it; `crash_census.csv` has no such
column). This is its first use in the project.

### 1.1 Raw cluster counts (UECC class, N = 92; the crashpad class has no such field)

| key | distinct values over N=92 |
|---|---|
| `PCallStackHash` | **37** (36 real + 1 empty string) |
| `harvest.py` family = first-3 game RVAs | **35** (34 real + the `(no game frames)` bucket) |

Cluster sizes by `PCallStackHash`: 17, 15, 7, 5, 4, 4, 3, then 7 clusters of 2, then 23
singletons.

### 1.2 Do the two keys agree? Mostly — and where they don't, both are wrong in different places

**MEASURED, over the 76 rows whose unwind produced game frames (`unwind_status='ok'`):**

| key | distinct clusters over those 76 |
|---|---|
| faulting-PC site (frame 0 only, from the minidump) | 31 |
| `harvest.py` chain-3 family | 34 |
| `PCallStackHash` | 35 |

- **No `PCallStackHash` ever spans two chain-3 families** (0 of 35). The hash is a strict
  *refinement* of the incumbent key on this subset.
- **Exactly one family splits under the hash**: `fe0148 ff933e 32bcbee` (the
  `FMallocBinned2` assert) → 2 hashes; the 3-value split shown in §3 is over all 7 members
  including one that lands in a different family.
- Four frame-0 sites hold more than one hash — `…+0xfe1746` (3 hashes), `KERNELBASE+0x25369`
  (4), `…+0x1345ff8` (2), `…+0xfe24ee` (2) — so frame 0 alone is genuinely coarser than both.

**Where the incumbent key is coarser (and it matters):**
The `(no game frames)` bucket holds **16 of 92 rows**. `PCallStackHash` splits it only into
2 (the empty-string SHA-1 `DA39A3EE…` ×15, plus one row with a blank hash). The truth,
from the exception records, is **at least three mechanisms**: 5 protector kills, 10
shim-scan faults, 1 jump-to-null — see §4.

**Where `PCallStackHash` is coarser (a real defect of the hash):**
- **MEASURED.** Hash `D5ABA8A5…` has n = 17 and holds **two different fatal reasons**:
  `Couldn't spawn player: ALokiGameMode::Login failed to Login` (×11) and
  `Couldn't spawn player: PlayerState is null` (×6). Same file:line, same stack, different
  cause. For asserts, the *ErrorMessage* is the finer key and the hash must not be used alone.
- **MEASURED.** All 24 `CrashType=Assert` rows have their faulting PC at
  `KERNELBASE.dll+0x25369` (`RaiseException`), so any minidump-PC key collapses all asserts
  into one. Asserts must be keyed on `assert_file:assert_line` + ErrorMessage.

**Where `PCallStackHash` beats my own PC-site key:**
Hashes `F83BC9D2…` (n=3) and `94929174…` (n=2) each span 3 and 2 *sites*, because their
faulting PC lives in a per-run `VirtualAlloc`'d region whose base moves every launch. The
hash, built from game-frame return addresses, holds them together correctly.

> **Conclusion (INFERRED):** no single key dominates. The correct composite is
> `assert_file:line` for asserts, `PCallStackHash` where the unwinder produced game frames,
> and the **minidump exception record** where it did not. The project has been classifying
> on a key that is right for ~76 of 92 rows and structurally blind for the other 16 — and
> those 16 are where the non-game deaths hide.

---

## 2. Part B — the real denominator

### 2.1 From artifacts to distinct deaths

| step | N | derivation |
|---|---:|---|
| A. artifact rows in the corpus | **139** | 92 UECC dirs + 47 archived crashpad `.dmp` files |
| B. crashpad duplicate collapse | 47 → **22** | `archive-crashdumps.ps1` snapshots the DB both before *and* after a launch; one uuid appears in 4 archives |
| C. **distinct death records** | **114** | 92 + 22 |
| D. degenerate (CrashContext writer never finished) | −8 | zero-byte `UEMinidump.dmp` ∧ no `TimeOfCrash` ∧ no `Modules`, three signals agreeing |
| E. **analysable records** | **106** | independently reproduces the corpus's own 84 + 22 = 106, by a different route |

**CONTROL (MEASURED).** The two sources are disjoint: 92 distinct UECC crash GUIDs, 22
distinct crashpad crash GUIDs, **intersection 0**. Joining crashpad GUIDs against the UECC
*directory names* also yields 0. Positive control on the joiner: the same key self-joins
the UECC set 92/92. So the 0 is a property of the corpus (control went to crashpad
*instead of* CrashReportClient), not of the join.

### 2.2 Attribution of all 114 distinct records

| bucket | N | status |
|---|---:|---|
| **GAME — unattributed** | **75** | the real game-crash denominator |
| **PROTECTOR — anti-tamper kill** (`runtime.dll+1`, EXECUTE AV) | **21** | 18 MEASURED from dumps, 3 INFERRED from the ErrorMessage (degenerate, no dump) |
| **SELF — `catalog_store_fix` heap-scan TOCTOU** (`PRIVATE+0x205d`) | **11** | INFERRED-strong (§4.2); + **4 SPECULATIVE** dumpless rows with the same fault shape |
| **SELF — FK-24 watchpoint probe** | **2** | MEASURED; the two GUIDs CLAUDE.md already names |
| **DEGENERATE — unattributable** | **1** | `_0000`, no dump, fault address in the image band |

- **Non-game, measured or strongly inferred: 34 of 114 (30 %).**
- Counting the 4 speculative rows as self-inflicted too: 38 of 114 (33 %), game = 75.
- Prior work's corrected denominators (`85 / 79 / 74`, S109) were about the *UECC* class
  only and predate 4 new directories. Today's equivalents: **92 dirs · 84 non-empty dumps ·
  76 with game frames**. Adding the crashpad class and removing the non-game rows gives
  **75** as the genuine-game figure — the number that should be quoted from now on.

### 2.3 The named contamination — confirmed, and it is exactly 2 rows

**MEASURED.** CLAUDE.md names `166396E2` (DR mode) and `FED1F952` (page mode) as the FK-24
probe self-killing. Both exist in the corpus. Both carry **the same `PCallStackHash`
`9492917422986D86959FAEA393928B3CE784D2C8`**, and that hash has n = 2 — nothing else. So
`PCallStackHash` isolates the known contamination perfectly, and confirms no *third* row
belongs to it.

Their signatures also give the reusable discriminator used in §4:

| | `166396E2` | `FED1F952` |
|---|---|---|
| exception | `0x80000004` SINGLE_STEP | `0xC0000005` write AV |
| faulting PC | `0x1A4A469C1A3` | `0x2BC61F9C09A` |
| PC inside any loaded module? | **no** | **no** |
| thread | GameThread | GameThread |
| SecondsSinceStart | 2550 | 572 |

⚠ **Corpus correction (MEASURED).** For `166396E2` the CSV column `fault_address` reads
`0x80000004`. That is wrong — a SINGLE_STEP has no accessed address, and the corpus's
"last hex in ErrorMessage" regex captured the *exception code*. The minidump confirms
`parms=[]`. This is the only one of 84 UECC dumps where the CSV and the minidump disagree
(83/84 agree exactly on exception code, accessed address and crashed-thread name — that
agreement is the positive control for `mdexc.py`).

---

## 3. Part C — per-cluster profile (every cluster with n ≥ 2, over the 114 distinct records)

Key = frame-0 faulting PC for AVs, `assert_file:line` for asserts. `isGT` = was the
crashing thread the GameThread.

| n | cluster | src | exception / fault address | crashed thread | isGT | route | SecondsSinceStart | wall-clock span |
|--:|---|---|---|---|---|---|---|---|
| **21** | **`runtime.dll+0x1` — ANTI-TAMPER POISON JUMP** | 16 crashpad + 5 uecc | `0xC0000005` **execute** at `<runtime.dll base>+1` | unnamed, never GameThread | 0/18 | tutorial 11, tut-attempted 2, menu-login 2, unknown 3 | 51–524, median 275; 6 of 14 land in 250–300 s | 2026-07-10 → 2026-08-05 |
| **17** | **`ASSERT UnrealEngine.cpp:15551` — "Couldn't spawn player"** | uecc | fatal assert (no address) | GameThread | 17/17 | tutorial-attempted 16, tutorial 1 | 13–834, median 90 | 2026-07-09 → 2026-07-11 |
| **11** | **`PRIVATE+0x205d` — SHIM HEAP-SCAN TOCTOU** | 6 crashpad + 5 uecc | `0xC0000005` **read**, usually a page-aligned private-heap address | unnamed, never GameThread | 0/11 | menu-login 4, menu-lobby 2, unknown 5 | 16–43, median 32 | 2026-07-08 → 2026-08-05 |
| **7** | `SUPERVIVE+0x107d500` | uecc | `0xC0000005` read **0x0** | Foreground Worker #0/#1 | 0/7 | menu-lobby 7 | 251–42387, median 952 | 2026-06-25 → 2026-07-19 |
| **7** | `ASSERT MallocBinned2.cpp:1322` (realloc of an unrecognized block) | uecc | fatal assert | GameThread ×6, RenderThread ×1 | 6/7 | menu-login 6, tut-attempted 1 | 14–278, median 15 | 2026-06-29 → 2026-07-17 |
| **6** | `SUPERVIVE+0xfe1746` | uecc | read `0x1E3010020` (×4), `0x900000000` | FAsyncLoadingThread ×5, RHIThread ×1 | 0/6 | menu-login 6 | 24–45, median 30 | 2026-06-30 → 2026-07-01 |
| **5** | *(degenerate, no dump)* `AV reading address 0x…` | uecc | 4 page-aligned private reads + 1 image-band | — | — | — | 0 | no timestamp |
| **4** | `SUPERVIVE+0x207d11d` | uecc | **write** `0x7FF68A21C9E8` / `0x900000008` | **RHIThread** | 0/4 | menu-login 4 | 18–46, median 28 | 2026-06-30 → 2026-07-01 |
| **3** | *(degenerate, no dump)* `AV 0x…0001` | uecc | protector poison, see §4.1 | — | — | — | 0 | no timestamp |
| **2** | `SUPERVIVE+0x349596d` | uecc | read `0xFFFFFFFFFFFFFFFF` | Foreground Worker | 0/2 | tutorial 2 | 194, 258 | 2026-07-26 → 2026-08-05 |
| **2** | `SUPERVIVE+0x13455d0` | uecc | read `0x0` | GameThread | 2/2 | tutorial 2 | 84, 3334 | 2026-07-11 |
| **2** | `SUPERVIVE+0x296f591` | uecc | read `0x28` | **RHIThread** | 0/2 | menu-login 1, menu-lobby 1 | 29, 31 | 2026-07-01 → 2026-07-02 |
| **2** | `SUPERVIVE+0x560f8ae` | uecc | read `0x0` | GameThread | 2/2 | tutorial 2 | 60, 677 | 2026-07-12 |
| **2** | `SUPERVIVE+0x3c5dc52` | uecc | read `0x700` | GameThread | 2/2 | tutorial 2 | 173, 175 | 2026-07-26 |
| **2** | `SUPERVIVE+0x1345ff8` | uecc | read `0x0` | GameThread | 2/2 | tutorial 2 | 259, 659 | 2026-07-11 → 2026-07-12 |
| **2** | `SUPERVIVE+0xfe24ee` | uecc | read `0x900000000` | Background Worker #10, RHIThread | 0/2 | menu-login 2 | 17, 43 | 2026-06-30 → 2026-07-01 |
| **2** | `SUPERVIVE+0x12c7e2d` | uecc | read `0xFFFFFFFFFFFFFFFF`, `0x1000040` | GameThread | 2/2 | tutorial 2 | 185, 194 | 2026-07-24 → 2026-07-26 |
| **2** | `FK-24 probe` (`PRIVATE+0xc1a3` / `+0xc09a`) | uecc | SINGLE_STEP; write AV | GameThread | 2/2 | tutorial 2 | 572, 2550 | 2026-08-03 → 2026-08-04 |

**CROSS-CHECK against prior work (MEASURED).** `docs/fk7-crash-settled.md` line 717 records
the histogram *"FAsyncLoadingThread fe1746 ×5, worker 107d500 ×7, RHIThread ×6"*. My
independent clustering reproduces it: `107d500` = 7, RHIThread total across `207d11d`(4) +
`296f591`(2) = 6, `fe1746` = 6 of which 5 are FAsyncLoadingThread. The pipeline agrees with
the incumbent where the incumbent looked.

**Naming the clusters** (INFERRED from thread + route + timing; no symbolisation was done):

- **PROTECTOR-KILL** — `runtime.dll+0x1`. Not a game bug. §4.1.
- **SHIM-SCAN-TOCTOU** — `PRIVATE+0x205d`. Ours. §4.2.
- **LOGIN-SPAWN-ASSERT** — `UnrealEngine.cpp:15551`. The tutorial-attempt failure mode: 16 of
  17 on `tutorial-attempted` (i.e. the force-open never reached `LVL_Tutorial`).
- **BINNED2-REALLOC-ASSERT** — `MallocBinned2.cpp:1322`, all but one at 14–28 s on menu-login.
- **LOBBY-WORKER-NULL** — `+0x107d500`, 7 records, *all* menu-lobby, *all* Foreground Worker,
  *all* reading NULL, sessions from 4 min to 11.8 h. The most durable pure-game cluster in
  the corpus and the least examined (§5).
- **ASYNCLOAD-1E3010020** — `+0xfe1746`, menu-login, FAsyncLoadingThread, a *constant* fault
  address `0x1E3010020` in 4 of 6 → a fixed poisoned/stale pointer, not a random wild read.
- **RHI-WRITE** — `+0x207d11d`, RHIThread, writing into the image band `0x7FF68A21C9E8`.

---

## 4. Is any other cluster self-inflicted?

### 4.1 `runtime.dll+0x1` — the anti-tamper kill. 21 records. MEASURED.

The signature is an **EXECUTE** access violation (`ExceptionInformation[0] == 8`) whose
address is exactly `<module base> + 1` — a deliberate jump to a non-executable byte.

**The join that proves it (MEASURED).** In the 47 crashpad dumps the faulting PC is the
*identical constant* `0x7FFD3B400001` in all 16 poison records, spanning 2026-08-04 →
2026-08-05 and many launches. That looked impossible under ASLR — until the boot-session
fingerprint resolved it:

| ntdll.dll base (= boot session) | runtime.dll base in the UECC dumps of that session | poison PC observed |
|---|---|---|
| `0x7FFD3B150000` | `0x7FFD3B400000` | `0x7FFD3B400001` (crashpad ×16) |
| `0x7FF90DD90000` | `0x7FF90E000000` | `0x7FF90E000001` (UECC) |
| `0x7FF8F01D0000` | `0x7FF8F0400000` | `0x7FF8F0400001` (UECC ×3) |
| `0x7FFAE9750000` | `0x7FFAE9A00000` | — |
| (boot with no surviving dump) | — | `0x7FFB9EE00001` (UECC, degenerate) |

Windows randomises a DLL's image base **once per boot**, not per process, so the constant
is expected. The project's named "poison RIP `0x7FF90E000001`" is simply `runtime.dll+1`
for one particular boot; the general signature is `<protector base>+1`.

⚠ **INSTRUMENT ARTIFACT, named explicitly.** `runtime.dll` is **absent from the module list
of every crashpad minidump** and **present in every UECC minidump of the same boot
session**. The module is there in both cases; crashpad's enumeration simply misses it.
Reading "no runtime.dll in the module list" as "the protector was not loaded" would have
been a textbook instance of the project's dominant error mode. The absence is scoped:
*absent from the crashpad-class module lists*, not absent from the process.

Supporting, all MEASURED:
- **0 of 18** poison records crashed on the GameThread; the crashing thread is unnamed in
  the dump (a thread UE did not create).
- Timing: median 275 s, with 6 of 14 non-zero values in **250–300 s** — the ~285 s
  code-integrity kill CLAUDE.md documents.
- **0 of 34** deaths dated before 2026-07-03 are in this cluster; **18 of 72** after are.
  2026-07-03 is the commit that first shipped a self-restoring `.text` patch
  (`catalog_ready_fix.cpp`).

**This cluster is not a game bug and must be excluded from FK-7 / FK-8 crash reasoning.**

### 4.2 `PRIVATE+0x205d` — our own `catalog_store_fix` heap scan. 11 records. INFERRED-STRONG.

Five independent lines, all MEASURED except the final identification:

1. **Faulting PC in no registered module**, at the *identical low-16 offset* `0x205d` in all
   11 records across 4 weeks and 3 boot sessions → one binary, manually mapped (our injector
   never registers with the loader).
2. **Crashing thread is unnamed and never the GameThread (0/11)**; the XML `CallStack` is
   just `kernel32;ntdll` → a raw `CreateThread` whose frames bottom out at
   `BaseThreadInitThunk`. `catalog_store_fix.cpp:316` does exactly that in `DllMain`.
3. **The faulting instruction matches the shim's source.** Disassembling the dump bytes
   around RIP in `UECC-Windows-4BC8B969…`:
   ```
   lea  rax,[r12+8] ; add r12,0x10 ; cmp r12,r15 ; ja …      <- an 8-byte-stride scan, unrolled ×2
   mov  rax,[rsp+0x108]                                       <- reload the vtable value
   cmp  [r12],rax          <<< FAULT                          <- *(uintptr_t*)p == vtabAbs
   lea  rcx,[r12+0x60]                                        <- p + kMapOff
   mov  r8d,0x30 ; lea rdx,[rsp+0x110] ; call r14             <- VirtualQuery(.., sizeof(MBI)=0x30)
   ```
   against `tools/sigbypass-mod/catalog_store_fix.cpp:204-222`:
   ```cpp
   constexpr uintptr_t kMapOff = 0x60;
   … VirtualQuery((void*)addr,&m,sizeof(m)) …  if(ok && m.Type==MEM_PRIVATE){
        for(uintptr_t p=base; p+8<=end; p+=8){
            if(*(uintptr_t*)p==vtabAbs && SafeReadable((void*)(p+kMapOff),16)){ …
   ```
   `rax` at the fault holds `SUPERVIVE-Win64-Shipping.exe+0x8831758` — an image pointer, i.e.
   the vtable being searched for. `r12` holds the fault address.
4. **Timing.** The 6 crashpad instances (which, unlike the UECC ones, preserve
   `SecondsSinceStart`) are at **16, 17, 29, 34, 34, 43 s** on menu-login/menu-lobby — exactly
   the window in which `FindCatalogManagers_first` spins waiting for the catalog to load.
5. **Every crashpad instance sits in a shim-injection sweep archive** (`shimrun3-DEATH`,
   `sub-NoMissions-1/2-DEATH`, `sub-NoPasses-2-DEATH`, `knee-g30-2/3-DEATH`), and **0 of 34**
   pre-2026-07-03 deaths are in this cluster while **11 of 72** after are. The scan first
   shipped 2026-07-03; the earliest instance is 2026-07-08.

**Mechanism (INFERRED):** `VirtualQuery` returns a committed region, the loop walks it, and
the game frees/decommits a page inside that region before the loop reaches it. The read
faults on the first qword of the freed page (10 of 11 fault addresses are page-aligned).
`SafeReadable()` is only consulted *after* a vtable match, so the scan itself is unguarded.

**Consequence:** the default launch injects this shim in **every** run. Any unexplained death
at 15–45 s on a menu route is a candidate for *our* scan, not the game's. This is a
concrete, fixable defect — the scan needs a VEH/`__try` guard or a re-`VirtualQuery` per page.

### 4.3 Clusters checked and NOT found self-inflicted

- **`+0x107d500`, `+0xfe1746`, `+0x207d11d`, `+0x296f591`, `+0xfe24ee`** — faulting PC inside
  `SUPERVIVE-Win64-Shipping.exe`, on named UE threads, the bulk of them **before**
  2026-07-03. MEASURED: game code.
- **`F83BC9D2…` (n=3, EXECUTE at `PRIVATE+0xce00/+0xb200/+0xd400`, all 2026-07-26, 195–201 s,
  Foreground/Background Worker)** and **the jump-to-NULL row `154E12A5` (194 s, same evening)**
  — these *are* execute-faults at unregistered addresses, so they superficially resemble
  §4.1/§4.2. But the offsets differ per record (not one constant), the threads are named UE
  task threads, and the game-frame return addresses are real. **INFERRED: a wild indirect call
  from game code, not our injector.** They remain OPEN and are the 173–201 s family the
  project already tracks.
- **All 24 asserts** — UE's own `check()` path. Not instrumentation.

⚠ **What this analysis CANNOT do (scope of the negatives):** shim presence per run is
*unobservable* from both artifact classes — 0 of 114 minidumps list any shim DLL (they are
manual-mapped, never registered) and 0 of 130 `Loki.log` files contain any bracketed shim
marker (markers go to `docs/*-marker.txt` via `CreateFileA`, never `UE_LOG`; detector
positive control fires on `docs/fk24-run-nostatictest1.txt`). So "cluster X is not
shim-related" can never be asserted from absence of a shim in the record. Every attribution
above rests on the *faulting code itself*, not on shim presence.

---

## 5. Part D — fault-address taxonomy (all 114 distinct records)

Access type is `ExceptionInformation[0]` from the minidump (0 read / 1 write / 8 execute),
not inferred from the ErrorMessage text.

| n | class | reading |
|--:|---|---|
| 24 | *(assert — no fault address)* | UE `check()`; the address field is meaningless here |
| 18 | **module base + 1, EXECUTE** | **anti-tamper poison jump — NOT a game bug** (§4.1) |
| 17 | page-aligned private-heap **read** | 10 = the shim scan (§4.2), 4 = dumpless rows with the same shape (SPECULATIVE), 3 = game code that happened to read a page boundary |
| 16 | **NULL (0x0)** | a null `this`/handle dereferenced at offset 0 |
| 11 | wild / plausible heap pointer | genuine stale or corrupted pointers |
| 9 | inside the loaded-image band `0x7FFxxxxxxxxx` | writes into or reads from the image — includes the RHIThread write cluster |
| 9 | small offset from null (< 0x10000) | **field deref of a null object**: `0x28`, `0x700`, `0x20` etc. |
| 5 | EXECUTE at a non-code address | wild indirect call — the 2026-07-26 worker family + one GameThread case |
| 4 | all-ones `0xFFFFFFFFFFFFFFFF` | classic `-1` sentinel / freed-index poison |
| 1 | SINGLE_STEP, no address | the FK-24 DR-mode probe |

**Anti-tamper total: 18 measured + 3 inferred (dumpless) = 21 of 114 (18 %).** The project's
named `0x7FF90E000001` is one member of that class, not a unique dump.

---

## 6. Part E — clusters nobody has ever looked at

**Method.** Three independent probes per cluster against all 571 files in `docs/` +
`CLAUDE.md` + the whole `memory/` tree (58 MB): (1) any member's 8-hex crash-GUID prefix,
(2) the full `PCallStackHash`, (3) the full 3-RVA chain. A cluster is UNEXAMINED only if all
three miss. **POSITIVE CONTROL: the probe fires on `166396e2` (12 files) and `fed1f952`
(11 files)** — both named in CLAUDE.md, so the detector works.

**Baseline coverage (MEASURED):** only **37 of 92** UECC records and **8 of 22** distinct
crashpad records are named anywhere in the project's writing. **The corpus is 60 %
unexamined at the artifact level.**

### 6.1 Tier 1 — never named at all (no GUID, no hash, no RVA anywhere)

Highest-value rows in the corpus. All are `SUPERVIVE-Win64-Shipping.exe` faults, i.e.
genuine game code.

| n | cluster | thread | route | secs | notes |
|--:|---|---|---|---|---|
| **2** | `+0xfe24ee` read `0x900000000` | Background Worker #10; RHIThread | menu-login | 17, 43 | shares frame 0 with 2 different chains; the fault value `0x900000000` also appears at `+0xfe1746` and `+0x207d11d` — a **shared poison constant across three clusters**, unremarked anywhere |
| 1 | `+0x8085ee0` **EXECUTE** `0x7FF6BD575EE0` | GameThread | tutorial-attempted | 240 | the only GameThread wild-call in the corpus |
| 1 | `+0x5782f29` read `0x0` | GameThread | menu-lobby | 41 | |
| 1 | `+0x5784619` read `0x0` | GameThread | menu-login | 22 | sits 0x16F0 from the one above — same subsystem |
| 1 | `+0x3ec456a` read `0x0` | GameThread | menu-login | 25 | |
| 1 | `+0xfa2d31` read `0x0` | **HttpManagerThread** | menu-login | 21 | only HTTP-thread death in the corpus |
| 1 | `+0x16767a3` **write** `0x0` | GameThread | menu-login | 45 | only null-*write* in the corpus |
| 1 | `+0x203656a` read `0x0` | GameThread | menu-lobby | 80 | |
| 1 | `PRIVATE+0x0000` EXECUTE `0x7FF706BF0000` | GameThread | menu-lobby | 15 | jump to a page base; earliest execute-fault (2026-07-03) |

### 6.2 Tier 2 — tallied in a histogram, but no member artifact ever opened

These appear in prior docs **only as a count**. No GUID is named, no stack was analysed, no
dump was read.

| n | cluster | where it is merely counted | why it is worth opening |
|--:|---|---|---|
| **17** | `ASSERT UnrealEngine.cpp:15551` "Couldn't spawn player" | `docs/ignorance-map-s101.md:1002` ("11× ALokiGameMode::Login … 6× PlayerState is null"); `docs/s108-crash-triage.md:355` | **The single largest cluster in the corpus.** 16 of 17 on `tutorial-attempted` — this *is* the force-open failure mode, and it has a GameThread stack in every one of 17 dumps. Nothing has ever been unwound. ⚠ `s108-crash-triage.md` calls all **24** asserts "Couldn't spawn player"; the true split is 17 + 7 `MallocBinned2` |
| **7** | `+0x107d500` read NULL, Foreground Worker, menu-lobby | `docs/fk7-crash-settled.md:717` ("worker 107d500 ×7") | 7 records, 2026-06-25 → 2026-07-19, sessions of 251 s to **42,387 s (11.8 h)**. A pure-game, highly reproducible null deref on the async task pool that has never been symbolised |
| 1 | `+0x2044473` read `0xFFFF…` | RVA appears in `strxref-known-addresses.md` / `symbols.csv` as a *symbol*, never as a crash | a known function, an unexamined crash |
| 1 | `+0x34d693d` read `0x0` | RVA in `symbols.csv` only | 3,983 s session |

### 6.3 Crashpad reports never mentioned anywhere: 14 of 22

Including every tutorial-route death of 2026-08-05 (`tut1`, `tut3-NOSTAGE`, `tut4`, `tuta1`,
`tuta3`, `tutr1`, `tutr3`, `s110itemwatch`, `phase2-nostage`, `phase2b-void`,
`animref-SUCCESS`). **MEASURED: 11 of those 14 are `runtime.dll+0x1` — the anti-tamper kill.**
So the S110 tutorial sittings that "died at 1–5 min" were, in 11 recorded cases, the
protector killing the process, not FK-7. The remaining 3 are the shim-scan cluster.

> **This is the most consequential finding for the tutorial frontier.** Of the 14 crashpad
> deaths from the S109/S110 tutorial campaign that nobody has looked at, **not one is a game
> bug**. 11 are anti-tamper, 3 are our own catalog scan.

---

## 7. What is NOT established

- **No cluster was symbolised.** Every `SUPERVIVE+0x…` here is an RVA. Mapping them to
  functions needs `dumps/merged.dump.exe` + `strxref` and was out of scope.
- **The `catalog_store_fix` attribution is INFERRED, not MEASURED.** The disassembly matches
  that shim's source at four points, and two sibling shims (`catalog_ready_fix`,
  `catalog_purchasable_fix`) contain the *same* scan. Only `catalog_store_fix` is injected by
  default, so it is the most likely member — but any of the three would produce this
  signature. A definitive test: build the shim with a marker byte at a known offset and
  compare `RIP & 0xFFFF`.
- **The 4 dumpless page-aligned-read rows are SPECULATIVE**, not counted in the 34.
- **Whether the anti-tamper kill is provoked by a *specific* shim is unknown.** It correlates
  with the era in which `.text` patching began (0/34 before 2026-07-03, 18/72 after), but
  the corpus contains no `-NoHook` control run that reached 285 s.
- **The corpus is LIVE.** These counts are as of 2026-08-05 19:20 local. Re-run
  `tools/crashtri/fk8_corpus.py` and the commands in §8 rather than citing them.

---

## 8. Reproduce

```bash
# 1. rebuild the corpus (read-only)
python "tools/crashtri/fk8_corpus.py"

# 2. sweep every minidump for its exception record (read-only, ~2 min)
python "tools/crashtri/mdexc.py" <path-to.dmp>        # single dump, pretty-printed

# 3. the FK-24 contamination check, by hand
python tools/crashtri/mdctx.py \
  "C:/Users/eastr/AppData/Local/SUPERVIVE/Saved/Crashes/UECC-Windows-166396E24F5A36C5727032B196D739EA_0000/UEMinidump.dmp"

# 4. the shim-scan disassembly (bytes at the faulting PC)
python tools/crashtri/mdctx.py \
  "C:/Users/eastr/AppData/Local/SUPERVIVE/Saved/Crashes/UECC-Windows-4BC8B9694F2C1A6A188CB8A9E01956AB_0000/UEMinidump.dmp" \
  --read=1ed96b02040,64
```

Compare the output of step 4 against `tools/sigbypass-mod/catalog_store_fix.cpp:204-222`.
