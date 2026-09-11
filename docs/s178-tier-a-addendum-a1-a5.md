# S178 Tier-A Addendum: A1 and A5 Retries

**Session:** S178 (addendum to `docs/s178-tier-a-synthesis.md`)
**Date:** 2026-09-05
**Scope:** results of the A1 (minidump 4-rule classifier) and A5 (runtime.dll entry-function trace, narrowed to first 1024 bytes) retries after the original A4/A5 came back as placeholder submissions.
**Verification status:** both retries CONFIRMED by adversarial verifiers, byte-for-byte against on-disk artefacts.

⚠ **This addendum SUPERSEDES §2.1 and NARROWS §2.4 of `s178-tier-a-synthesis.md`.** Read the corrections below before quoting either of those sections.

---

## 1. A1 result — 4-rule minidump classifier on the entire on-disk corpus

### 1.1 Counts

Corpus: **437 minidumps** enumerated under `dumps/crash-*` and `dumps/crashpad-*` (max walk depth 4). Classifier: `scratchpad/classify_fk_dumps.py` (pre-existing tool, parses `MINIDUMP_EXCEPTION_STREAM` (6), `MINIDUMP_THREAD_LIST` (3), `MINIDUMP_MODULE_LIST` (4), `MINIDUMP_MEMORY_INFO_LIST_STREAM` (16) directly rather than shelling out to `mdctx.py`; ~2 s per full-corpus pass).

Per-file JSON at `scratchpad/classifications_final.json` (435 entries) for auditability.

| Rule | Meaning | Count | % of parsed |
|---|---|---:|---:|
| Rule 1 | FK-32 (exit `0x0000DEAD`, NO minidump) | n/a — no dump | — |
| Rule 2 | **FK-31 in-process** (0xC0000005 + EXECUTE + RIP≡1(mod 0x1000) + region MEM_IMAGE READONLY + AllocationBase == (RIP−1)&~0xFFF) | **403** | **92.6 %** |
| Rule 3 | Different fault class (all READ faults; RIP not on stack, not in MEM_PRIVATE RWX) | **32** | 7.4 % |
| Rule 4 | **SUSPECT companion-mediated FK-31** (RIP in MEM_PRIVATE RWX or on a thread stack) | **0** | **0.0 %** |
| — | Parse errors | 2 | — |

The 2 parse errors are the same corrupt file (`f053db6e-082f-4628-9cb9-759f9240d7fe.dmp`) present in two archived crashpad directories — not distinct crashes.

### 1.2 Rule-2 signature holds on every one of the 403

All 403 dumps pass every clause of the S131 signature independently (0 mismatches). Region reads come from `MINIDUMP_MEMORY_INFO_LIST_STREAM`, which carries per-region `State`/`Protect`/`Type`/`AllocationBase` — so "RIP lands in a manually-mapped `runtime.dll` DOS-header page" is a direct read, not an inference. Example region-block: `base=0x7FFA42600000 size=0x7000 protect=0x02 (READONLY) type=0x1000000 (MEM_IMAGE) alloc_base=0x7FFA42600000` with `RIP=0x7FFA42600001`. Matches the live-measured signature from `scratchpad/s131/tools/fk31_map_kill_page.py`.

### 1.3 Rule-3 breakdown — nothing FK-31, all shim-heap

The 32 Rule-3 dumps are **all READ faults** (`exc_info_0 == 0`). RIP low-16 distribution:

| RIP low-16 | Count | Attribution |
|---|---:|---|
| `0x205D` | 30 | S111 `catalog_store_fix.dll` heap-scan family (FK-8 family B, 2026-08-04→08-06 batch, per CLAUDE.md S133 §7) |
| `0x18E2` | 1 | Unclassified single-instance READ fault |
| `0x19F2` | 1 | Unclassified single-instance READ fault |

None are FK-31. The 30 at `0x205D` are our own shim's heap-scan defect — already fixed in S111 by dropping the `.text` `jz`-NOP.

### 1.4 Rule-4 tell — the falsification target — fired ZERO times

The classifier's Rule-4 test was **specifically designed** to detect a companion-mediated FK-31 shape: `region['type'] == MEM_PRIVATE (0x20000)` with `Protect & (PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)` (JIT-stub hypothesis), OR `md.rip_on_stack(rip)` against every parsed thread stack range from `MINIDUMP_THREAD` (stack-jmp hypothesis). Neither triggered on any of 435 parsable dumps.

⚠ Minor scope note (does not refute): the RWX mask (`0xC0`) misses a hypothetical JIT stub flipped to `PAGE_EXECUTE_READ` (`0x20`) before the fault, but no Rule-2 dump lands in **any** MEM_PRIVATE region regardless of protection, so this niche gap does not weaken the finding.

### 1.5 The 5 boot-era `runtime.dll` bases match the FK-31 kill-address register exactly

`runtime.dll` is manually mapped and hidden from `MINIDUMP_MODULE_LIST` (0 of 435 dumps report a module for its base). Every base below is INFERRED from the Rule-2 region signature. All 5 match the per-boot FK-31 kill-address register in this file (CLAUDE.md S131/S157):

| Base | Count | Source register entry |
|---|---:|---|
| `0x7FFA42600000` | 11 | S131 (n=4 originally, now n=11) |
| `0x7FFB57400000` | 31 | S131/S165/S167 (matches Aug 23-24 era) |
| `0x7FFCA1400000` | 15 | S154 (S169's HIGH view) |
| `0x7FFD3B400000` | 343 | S131 (heavy tail, matches 342 files / 99 distinct reports) |
| `0x7FFE9B600000` | 3 | **S157** (Sep-1-2026 era, previously n=1) |

This adds independent minidump-corpus corroboration for the two most-recent eras that S157's per-launch measurements first named.

### 1.6 Crashwatch corpus — FK-32 events left NO minidumps

Grep across 19 `docs/crashwatch*.log` files for `exit code` and `0x0000DEAD` recovered **4 confirmed FK-32 exit-code events**, all with **no crashpad minidump** on disk (matches Rule 1: silent kill via `NtTerminateProcess(target, 0xDEAD)` from the companion process does not produce a crashpad handoff):

| Session | File | Elapsed to kill |
|---|---|---:|
| s145 mana10 activate | `crashwatch.s145-mana10-activate-0xDEAD.log` | 196.6 s |
| s145 mana10 r2 | `crashwatch.s145-mana10-r2-activate-0xDEAD.log` | 198.3 s |
| s146 wallp3 native handle | `crashwatch.s146-wallp3-native-handle-0xDEAD.log` | 195.3 s |
| s147 natural input flight5 | `crashwatch.s147-natural-input-flight5-ACTIVATED-termination.log` | 290.5 s |

Plus 5 operator `TerminateProcess(-1)` cleanups and 1 clean exit (`0x00000000`). Consistent with S177's model.

### 1.7 Verdict — companion mediation of FK-31 is REFUTED at n=403

The 4-rule predictor was pre-registered with Rule 4 as the falsification target. It fired **0 times across 435 parsable dumps**. Combined with 403 clean Rule-2 hits carrying the full S131 signature, **the FK-31 death class is a self-fault in the game process's own manually-mapped `runtime.dll` DOS-header page** — companion mediation of FK-31 is refuted at this sample size.

The symmetric question "does the companion mediate FK-32?" is **not** addressed by this classifier — Rule 1 assumes it, and the 4 confirmed FK-32 exit codes are consistent with the S177 companion-process discovery but the corpus alone cannot prove companion causation for those.

---

## 2. A5 result — `runtime.dll` entry function `0x139238F`, first 1024 bytes

### 2.1 Prologue

`runtime.dll` file offset `0x138E98F` (RVA `0x139238F`, in `packer30`) opens with a heavy MSVC-style prologue, byte-verified end to end against the on-disk `runtime.dll` at `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll` (67,511,496 bytes, ImageBase `0x200000000`, `packer30` VA=`0x127C000` / RAW=`0x1278600`):

- 8 GPR pushes: `rbp, r15, r14, r13, r12, rsi, rdi, rbx`
- `sub rsp, 0x778` (~1.9 KB stack)
- `lea rbp, [rsp+0x80]` — frame base
- 10 XMM saves: `movdqa [rbp+0x6E0..+0x650], xmm15..xmm6`
- `and rsp, 0xFFFFFFFFFFFFFFC0` — 64-byte align
- `jmp 0x1392482` — forward-jump past ~122 bytes of opaque/junk bytes

Bytes end-to-end: `55 4157 4156 4155 4154 56 57 53 4881ec78070000 488dac2480000000 66440f7fbde0060000 [...] 4883e4c0 eb7a`.

### 2.2 First real basic block (at jump target `0x1392482`)

At RVA `0x1392482`: `mov rbx, rsp; mov [rbx+0x6c8], rbp; jmp 0x13924d5` — a second forward jump past another 73-byte junk block.

### 2.3 First real CALL — MBA-obfuscated indirect dispatch

At RVA `0x13924d5`: **`call 0x130A4A0`** (bytes `e8 c6 7f f7 ff`), immediately followed by **`jmp rax`** (bytes `ff e0`) at RVA `0x13924da`.

This is the canonical MBA-obfuscated indirect-dispatch idiom CLAUDE.md documents for `runtime.dll` (`docs/fk10-protector-identified.md`): a helper computes the real target into `rax`, and a tail-jump transfers.

⚠ **Callee `0x130A4A0` independently confirmed as an MBA-dispatch stub** — its own prologue is `eb ff` (anti-analysis `jmp -1` that traps linear disassemblers), then `lea rax, [rip+0x2bd5f3ba]; lea rax, [rax+0xd42a1830]; jmp rax`. This is stronger corroboration than the finding claimed: `0x130A4A0` **is** a real MBA-obfuscated indirect-jump helper. Any FK-32 defeat strategy that targets this dispatcher would affect every entry point that routes through it, not just the module-entry function.

### 2.4 No preloader-stash access in the first 1024 bytes

**Zero memory operands with displacement in the range `[0xC8, 0x138]` appear anywhere in the prologue or the first real basic block.** The prologue only touches `[rbp+0x6A0..+0x6E0]` (XMM save area) and the real body uses `[rbx+0x6C8]` to stash `rbp`. No `[rip+N]` displacement resolves to preloader `.data 0x50C8..0x5138`.

**Consequence for §2.4 of the synthesis:** the specific `runtime.dll` RVA that reads the preloader spawn-API pointer stash is **not** in the module-entry function's first 1024 bytes. If it is consumed, it happens deeper in the call graph — likely inside `0x130A4A0` or one of the downstream targets. **This narrows the search space but does not close the question.**

### 2.5 No FF-15 / FF-90 indirect calls in the first 1024 bytes

**No `FF 15 <disp32>` (call `[rip+disp]`) and no `FF 90 <disp32>` (call `[reg+disp32]`) opcodes appear anywhere in the initial byte window.** All indirect transfer is done via the `call rel32; jmp rax` pattern. One `FF D6` (`call rsi`) exists at RVA `0x13924FF`, reached via `jo 0x13924FF` at `0x13924FE` — inside the opaque region between the two forward jumps — so the narrower "no `FF 15`/`FF 90` in the first 1 KB" claim still holds, but "indirect transfers are done EXCLUSIVELY via `call rel32; jmp rax`" would be slightly overstated.

### 2.6 Subsequent direct-call rel32 targets

Beyond the first `call/jmp rax` dispatch, subsequent code reaches out via further forward jumps and rel32 calls landing in various packer1/packer30 addresses, plus repeated calls to `runtime.dll` low-address band `0x8148..0x81F0`. The `0x8148..0x81F0` band is verified as **pointer-array data** (LE qwords `0x8200/0x8216/0x8228/0x8236/0x8246`, spaced ~16-24 bytes apart, consistent with an import name/hint table adjacency). This supports the "call through IAT/import thunks" interpretation and is consistent with the packer0 name-pointer table A2 identified as the WinHTTP dispatch surface at slots `0x8148..0x8190`.

⚠ One earlier-claimed rel32 target, `call 0x7c6758`, actually lands on string data (`"CRL Sign\0\0"` bytes at packer0 file offset `0x7c5358`) — not code. Consistent with the finding's own caveat that bytes 148..244 (the region skipped by the prologue's `jmp 0x1392482`) are opaque/data. Do not read `0x7c6758` as a real callee.

---

## 3. Updated status of S177 open questions

### 3.1 §2.1 — Does companion mediate FK-31?

**PREVIOUS: STILL_OPEN.**
**NEW: REFUTED at n=403.**

A1's 4-rule classifier on 435 parsable minidumps produced 403 Rule-2 (in-process FK-31) hits and **0 Rule-4 (companion-mediated) hits**. The 4-rule predictor was pre-registered with Rule 4 as the falsification target and it fired 0 times. This makes FK-31 a **self-fault in the game process's own manually-mapped `runtime.dll` DOS-header page** at the level of the fault RIP.

Symmetric question "does companion mediate FK-32?" remains STILL_OPEN — Rule 1 assumes it, and while all 4 recovered `0x0000DEAD` exit codes are consistent with the S177 companion model, the crashwatch corpus alone cannot prove companion causation. The A2 synthesis's kill-primitive disassembly and A3's process-handle static evidence remain the strongest FK-32 corroboration; a live ETW `Microsoft-Windows-Kernel-Process/OpenProcess` filter on the companion PID would upgrade FK-32 mediation to [M].

### 3.2 §2.4 — Which runtime.dll RVA dereferences preloader stash?

**PREVIOUS: STILL_OPEN in the strong form.**
**NEW: NARROWED — not in the first 1024 bytes of the entry function.**

A5 confirms **zero** memory operands with displacement in `[0xC8, 0x138]` in the first 1024 bytes of entry `0x139238F`. Whatever runtime.dll code reads preloader `.data 0x50C8..0x5138` must be reached via the deferred call graph from `0x130A4A0` (the MBA-dispatch stub) or from later basic blocks. The static byte-scan approach could still work, but it must target **all** of `runtime.dll` for `[rip+N]` displacements resolving to the preloader base, not just the module entry.

⚠ The scan is complicated by:
- Preloader is manually mapped, so its runtime base varies per launch.
- Runtime.dll's dispatch is MBA-obfuscated (`lea; add; jmp rax` pattern), so a raw `[rip+N]` byte scan will miss any dispatch that computes the pointer via arithmetic on `rax` rather than a direct `rip+N` load.

**Practical next step:** a live-memory HW breakpoint on preloader `.data 0x50C8` (any one slot) that fires the first time runtime.dll reads it. Cheaper than scanning the whole 46 MB obfuscated `packer30` and gives the RVA directly.

### 3.3 §2.2 — Which packer30 integrity check detonates the kill?

Unchanged by A1/A5 — still narrowed to SHA-256 hasher `0x920C10` + WinHTTP phone-home, still open on the specific comparison site. A2's Move A3b (2-hop callee enumeration) and Move A4 (`.pdata SCOPE_TABLE` walk) remain the recommended closure.

### 3.4 §2.3 — Does companion inherit or dynamically open handle to game?

Unchanged. A3's static evidence still favours dynamic open; A1's minidump corpus cannot discriminate the two on the FK-32 side (Rule 1 dumps do not exist by construction).

---

## 4. New instrument defects encountered

### 4.1 A1 — `classifications_final.json` schema note

`scratchpad/classify_fk_dumps.py`'s Rule-3 output preserves the semantic distinction "other fault class, RIP is **neither** on stack **nor** in MEM_PRIVATE RWX" rather than the task-doc's shorthand "other RIPs (not runtime.dll+1)". This matters because Rule-3 hits at low-16 `0x205D` are still shim heap addresses (S111 catalog_store_fix); a naive reader of the task doc's Rule-3 description might not realise the classifier already excluded on-stack + RWX before deciding "other". Not a defect — a documentation gap in this addendum's task frame.

### 4.2 A1 — MinuteInfoListStream dependency

The classifier's Rule-4 detection assumes minidumps carry `MINIDUMP_MEMORY_INFO_LIST_STREAM` (type 16). 100 % of the 435 parsed dumps carry it. **If a future FK-32 death did produce a minidump without MEM_INFO, Rule-4 would degrade to on-stack-only detection.** No such dump has been observed, but the assumption should be verified before any single-instance FK-32 minidump is filed against the classifier.

### 4.3 A5 — Capstone linear-decode traps on MBA-obfuscated skipped blocks

Capstone 5.0.7 cleanly decoded only 29 real instructions in a linear sweep from `runtime.dll` file offset `0x138E98F` before hitting the opaque bytes skipped by the prologue's `jmp 0x1392482`. Recovering the real body required resuming disassembly at each forward-jump target. **A naive `capstone.disasm(bytes, base_addr, count=N)` call over the first 1 KB produces a mixture of real instructions and mid-block junk decodes**, and any tool that trusts a linear decode of `runtime.dll` will silently include garbage.

**Rule of thumb:** for any `runtime.dll` function, disassemble by following forward jumps from the entry point; do not linear-decode past a `jmp <forward>`.

### 4.4 A5 — Rel32-call-target validation is required

Verified during A5's adversarial re-parse: one of the rel32 call targets in the initial byte window (`call 0x7c6758`) lands on ASCII string data (`"CRL Sign\0\0"`), not on code. Any tool that grades call targets without checking whether the target is on a valid instruction boundary will produce false callee lists for `runtime.dll`. Cross-check every rel32 target against a disassembly of the target address before treating it as a callee.

---

## 5. Ranked next moves after A1/A5

Ordering after the two retries. **Move #1 is now cheapened by A1; Move #4 is now dominated by A1; a new Move #5 is added.**

### 5.1 (unchanged, top priority) — Live ETW `Kernel-Process/OpenProcess` on companion PID

Still the cheapest FK-32 mediation discriminator. Now benefits from a stronger baseline: FK-31 companion mediation is REFUTED (A1), so any positive ETW hit filtered to the companion PID during a `0xDEAD` death is unambiguously an FK-32 attribution rather than a possible FK-31 confound. Cost unchanged: one live session with `logman start` + `xperf`-style capture, ~1-line Python parse.

### 5.2 (new) — HW breakpoint on preloader `.data 0x50C8`

Direct closure of §2.4 without a 46 MB static scan. Set a data-access hardware breakpoint on preloader RVA `0x50C8` (or any of the 15 stash slots) during a normal game boot; the first fire gives the `runtime.dll` RVA that reads the stash slot, and its rip context names the specific callee. Cost: one attached-debugger session. Bounded to `HW BP install detection` risk (S169-lite saw an FK-32 4 s after DR install on `runtime.dll`; n=1, so grade [I]) — mitigate by installing the BP before game launch and detaching before the death window.

### 5.3 (unchanged) — A2 Move A3b (2-hop callee enumeration from the 5 SHA-reaching ranges)

Purely offline. Reads the 5 confirmed ranges' 2-hop callees and grades each against the `[0x8FFCD4..0x93E886]` FK-10 Wall #7 SHA-band. Cost: one Python parse over `merged14.dump.exe`. Closes §2.2 for the SHA family.

### 5.4 (dominated by A1) — Batch re-classification of any newly-captured minidumps

A1 already ran the full 4-rule predictor against the on-disk corpus. **Any future dump can be appended by running `scratchpad/classify_fk_dumps.py` on a single new file** — the classifier is idempotent and per-file JSON is preserved. The only unranked next move here is "keep the classifier running as a live gate on every new dump directory," which is trivial harness work.

### 5.5 (new) — Scan runtime.dll for `[rip+N]` displacements resolving to preloader base

Offline complement to Move #2 (HW BP). If Move #2 gives one RVA, this gives all 15 (one per stash slot). Complicated by MBA obfuscation, so it is a lower-precision instrument; grade the result as [I_strong] unless corroborated by live HW BP fires.

### 5.6 (unchanged) — Move A4 (`.pdata SCOPE_TABLE` walk over the 5 hasher-reaching ranges)

Purely offline. Closes §2.2 for the SHA family independently of Move #3.

### 5.7 (still open, no new leverage) — Full `runtime.dll` static import diff against Sentry crashpad

A2 established runtime.dll's static imports are 17 symbols total, dominated by WinHTTP and "close" verbs. §3.2's model ("runtime.dll is the companion") could be independently checked against Sentry's `crashpad_handler.exe` import table — if Sentry's crashpad has the WinHTTP subset but not the ntdll `Zw*` cross-process family, that dissociates the two.

---

## 6. Bottom-line net-change for §2 of the synthesis

| Question | Before | After |
|---|---|---|
| Does companion mediate **FK-31**? | STILL_OPEN | **REFUTED at n=403** (Rule-4 fired 0 times) |
| Which packer30 integrity check detonates? | NARROWED (SHA + WinHTTP) | Unchanged |
| Inherit vs dynamic-open handle? | NARROWED (favours dynamic open) | Unchanged |
| Which runtime.dll RVA reads preloader stash? | STILL_OPEN strong | **NARROWED — not in first 1 KB of entry `0x139238F`** |

Two orthogonal advances: FK-31 attribution consolidated to pure in-process, and the module-entry function's role narrowed to "MBA-dispatch stub that hands off to `0x130A4A0`, not itself a consumer of the preloader stash."

**FK-31 as an in-process fault remains cheap to prevent** (S170/S173/S174: thread suspension defers by 4-6×; S169-B poke of packer2 XOR constant does not defeat it; race approach still open). **FK-32 as a cross-process kill remains the harder wall** — A2's disassembly and A3's static evidence are the strongest handhold, and the ETW discriminator (Move #1) is the cheapest single-shot upgrade to [M].
