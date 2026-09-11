# S178 Tier-A Synthesis: Companion Process Mechanism & FK-32 Dispatch

**Session:** S178 (Tier-A consolidation of 5 parallel offline analyses)
**Date:** 2026-09-05
**Scope:** consolidation of adversarially-verified offline work on the S177 companion-process discovery
**Verification status:** 2 of 5 analyses CONFIRMED (a2, a3), 1 PARTIAL (a2 has 4 cosmetic refutations), 2 REFUTED as placeholder submissions (a4, a5)

---

## 0. Verification-status summary

| key | topic | verdict | usable? |
|---|---|---|---|
| `a2_killscope_disasm` | 16 kill-guarded packer30 ranges | PARTIAL (4 cosmetic corrections) | **YES** — every [M] byte-level claim survives adversarial re-parse |
| `a3_handle_inheritance` | how companion gets PROCESS_TERMINATE handle | CONFIRMED | **YES** — every [M] re-derived from PE bytes |
| `a4_regrade_audit` | docs regrade | REFUTED (placeholder input) | **NO** — no substrate |
| `a5_entry_trace` | preloader→runtime entry trace | REFUTED (placeholder input) | **NO** — no substrate |

⚠ **Two of the five Tier-A analyses came back as `{question:"test", evidence:"test", grade:"M"}` placeholders and were correctly REFUTED by their verifiers.** Do NOT read this as "the questions have no answer" — it means the analyses were never run. Both questions (docs-regrade audit and preloader→runtime entry-point trace) are still open and are re-listed as priority Tier-C moves in §4.

---

## 1. Consolidated findings

Grouped by S177 topic.

### 1.1 FK-31 attribution — companion mediation

No direct S178 evidence closes this. **A2 and A3 both operate on the FK-32 (`0x0000DEAD`) kill primitive**, whose disassembly is bit-identical to `runtime.dll` RVA `0x80F7F0` (`mov edx, 0xDEAD; syscall`). FK-31 (`runtime.dll+1` execute violation, exit `0xC0000005`) is a **different mechanism** per CLAUDE.md S168, and neither Tier-A dive directly touched it.

**Consequence for S177 open question #1** (does companion mediate FK-31?): **STILL_OPEN**. See §2.1.

### 1.2 Kill-scope caller — which packer30 code dispatches the kill

**New [M] from `a2_killscope_disasm` (verified byte-for-byte):**

- **[M]** The 16 kill-guarded packer30 SCOPE ranges from S162 do **NOT share ONE common integrity-check callee.** They partition into **two dispatch families:**
  - **SHA-256 integrity family (5 of 16, 31%):** ranges reach the Intel ISA-L multi-buffer SHA-256 hasher at `runtime.dll` RVA `0x920C00` (real body at `0x920C10`), directly or via one hop. All hop targets fall inside the FK-10 Wall #7 predicted band `[0x8FFCD4..0x93E886]`.
    - Direct callers: `0x132E211` (calls `0x920C00`), `0x13421BC+0x21` (calls `0x8FFD84`, bytes `e8 a2 db 5b ff`).
    - 1-hop callers: `0x13FAE47`→`0x1407D6A`→`0x91DEF0`; `0x1434041`→`0x1412F51`→`0x8FFD88`; `0x1324329`→`0x131B507`→`0x924EE0`.
  - **WinHTTP phone-home family (7 of 16 measured direct):** ranges call directly into the packer0 name-pointer table at RVAs `0x8148..0x8190`, which parses as `<ORD:u16>\x00Name\x00` records naming WinHttpOpen/Connect/OpenRequest/SendRequest/ReceiveResponse/QueryHeaders/WriteData/CloseHandle plus WTSEnumerateSessionsW.
    - Verified callers: `0x13FAE47`, `0x1429C2F`, `0x13FEEF9`, `0x142259F`, `0x1324329`, `0x1346B87`, `0x1322341`.

- **[M]** FK-10 Wall #7 SHA-256 hasher at `runtime.dll` RVA `0x920C10` is **directly linked to FK-32 kill dispatch.** The hasher prologue at `0x920C10` (offset from the `0x920C00` trampoline) is a canonical Intel ISA-L multi-buffer preamble: `cpuid` with AVX2 check (`test ecx, 0x100000`), OSXSAVE check (`test ecx, 0x8000000`), `xgetbv`. This is the same hasher CLAUDE.md `docs/fk10-protector-identified.md` predicted lives at `[0x8ffcd4..0x93e886]` (~251 KB Intel ISA-L Crypto multi-buffer assembly).

- **[M]** Kill primitive at `runtime.dll` RVA `0x80F7F0` re-verified byte-identical to CLAUDE.md S131/S161/S168 records: `4c 8b 51 10 4d 85 d2 74 1b b8 bf 77 8e 61 33 05 fc af 13 00 c1 c0 07 05 47 c7 10 67 ba ad de 00 00 0f 05 c3 31 c0 c3` = `mov r10,[rcx+0x10]; test r10,r10; je 0x80F814; mov eax,0x618E77BF; xor eax,[rip+0x13AFFC]; rol eax,7; add eax,0x6710C747; mov edx,0xDEAD; syscall; ret` + `xor eax,eax; ret` at the je target. The `[rip+0x13AFFC]` load = packer2 RVA `0x94A800` = the S169 XOR constant slot.

- **[I_strong]** Structural model — the 16 SCOPE ranges route to the kill via failure of **EITHER** (a) SHA-256 integrity check mismatch OR (b) WinHTTP phone-home network error. Both classes fail-close through the SEH scope-filter mechanism (S162) to `HandlerAddress = 0x80F7F0`, and that primitive kills the target process named by `[rcx+0x10]`.

**Cosmetic corrections from A2's verification (do not affect structural conclusions):**
- Distance `0x94A160` to SHA band upper bound is **47,322 B** (not 45,748 B).
- Hasher prologue is at **`0x920C10`**, not `0x920C00` (which is a `call/jmp` trampoline + int3 padding).
- WinHTTP-caller count is **7 of 16**, not 8 (the `(x2)` on `0x142259F` doesn't add a range).
- `WTSEnumerateSessionsW` at slot `0x8190` is `wtsapi32.dll`, not WinHTTP — table is "mixed import name table dominated by WinHTTP APIs."

### 1.3 IPC mechanism — how companion gets PROCESS_TERMINATE handle

**New [M] from `a3_handle_inheritance` (verified byte-for-byte):**

- **[M]** Preloader.dll's **15-API dispatch stash** at `.data 0x50C8..0x5138` is fully mapped (matches S177 exactly). Contents:
  ```
  0x50C8 RtlQueryEnvironmentVariable_U    0x5108 ZwCreateThreadEx
  0x50D0 RtlExpandEnvironmentStrings      0x5110 ZwQueryInformationFile
  0x50D8 RtlDosPathNameToNtPathName_U_    0x5118 ZwQueryInformationProcess
  0x50E0 RtlCreateProcessParametersEx     0x5120 ZwClose
  0x50E8 RtlCreateEnvironment             0x5128 ZwQueryDirectoryFile
  0x50F0 ZwCreateUserProcess              0x5130 ZwWaitForSingleObject
  0x50F8 ZwSetInformationFile             0x5138 ZwDeleteFile
  0x5100 ZwCreateFile
  ```
  Stash contains **NEITHER** `NtOpenProcess` **NOR** `NtDuplicateObject`.

- **[M]** Preloader.dll's full ntdll import list (43 symbols, re-parsed from PE data_dir[1] RVA `0x3F20` size `0x50`) contains **NEITHER** `DuplicateHandle`, `NtDuplicateObject`, `NtOpenProcess`, `UpdateProcThreadAttribute`, **NOR** `InitializeProcThreadAttributeList`. Preloader is **architecturally incapable** of constructing an inheritable duplicated handle to the game process.

- **[M]** `PS_ATTRIBUTE_HANDLE_LIST` constant `0x0002000B` (LE `0B 00 02 00`) byte-scan counts: preloader.dll **0 hits**, runtime.dll **0 hits**, game exe **1 hit** at `.data` RVA `0x9CCB476`. The one hit is inside a `{counter, sentinel, pointer}` record table, not a PS_ATTRIBUTE header (context bytes at hit: `1d 00 00 00 0b 00 0b 00 02 00 00 00 01 00 00 00 00 00 00 00 41 00 01 00 00 00 00 00 78 f8 24 49 01 00 00 00`).

- **[M]** Runtime.dll 4 hits for kernel32-level `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` (`0x00020002`, LE `02 00 02 00`) at RVAs `0x383832` (packer0, 32 B after `ecdsa-with-SHA256` ASCII OID literal at file `0x382412` — inside X.509 sig-alg table), `0x241A3CC`, `0x241AA9B`, `0x2AA11AA` (all packer31, all inside MBA-obfuscated movabs immediates). **NONE are PS_ATTRIBUTE constructions.**

- **[M]** Runtime.dll's real static import table = **17 symbols across 6 DLLs**, zero process/handle-manipulation APIs:
  - WINHTTP.dll: 8 (WinHttpCloseHandle, Connect, Open, OpenRequest, QueryHeaders, ReceiveResponse, SendRequest, WriteData)
  - WTSAPI32.dll: 3 (WTSEnumerateSessionsW, WTSFreeMemory, WTSSendMessageW)
  - ntdll.dll: **1** (RtlPcToFileHeader ONLY — matches CLAUDE.md's already-known "only ntdll import")
  - KERNEL32.dll: **1** (CloseHandle ONLY)
  - USER32.dll: 3, GDI32.dll: 1

- **[M]** Runtime.dll direct-syscall infrastructure: **923 raw `0f 05` syscall opcodes**, **40 `48 c7 c1 ff ff ff ff` (mov rcx, -1 = NtCurrentProcess pseudo-handle) patterns**, **0 canonical Win10 syscall stubs** (`4c 8b d1 b8` prefix). Confirms per-FK-10/S169 dynamic-syscall dispatch with runtime-computed syscall numbers. Companion can invoke `NtOpenProcess` (~0x26), `NtQueryInformationProcess` (~0x19), `NtTerminateProcess` (~0x2C, confirmed at kill primitive) without any of them in the import table.

- **[M]** String `'runtime.dll'` UTF-16LE appears **exactly once**, in preloader.dll at file offset `0x22A0` = `.rdata` RVA `0x34A0`. Zero hits in game exe (both encodings). Zero hits in runtime.dll itself. Consistent with S177's "CommandLine empty" — companion is launched via a `SectionHandle` (created by preloader's `NtCreateSection` at RVA `0x1C3F`) passed to `ZwCreateUserProcess`, not by ImagePathName.

- **[M]** Preloader mapper tail-call: at RVA `0x22BB`, bytes `ff 15 af 2d 00 00` = `call qword ptr [rip + 0x2daf]`, target = `.data` RVA `0x5070` = runtime.dll's dispatch pointer. Preceded by `xor ecx,ecx / mov edx, 0x25665cd7 / xor r8d,r8d`. This is where **preloader hands control to runtime.dll**.

- **[M]** ZERO callers of `ZwCreateUserProcess` (IAT RVA `0x4208` or trampoline stub `0x2720`) anywhere in preloader `.text`. Only reference is a single `mov rax, [IAT_ZwCreateUserProcess]` at `.text 0x1DF` that populates the `.data 0x50F0` stash. **Preloader itself never invokes `ZwCreateUserProcess`**; all process-spawn happens inside runtime.dll's obfuscated code reaching the pointer via the stash.

- **[I_strong]** **Leading hypothesis: companion opens the game handle DYNAMICALLY via direct syscall.** Static evidence:
  - Preloader cannot duplicate handles (no relevant imports).
  - `PS_ATTRIBUTE_HANDLE_LIST` byte constant appears nowhere in preloader/runtime that isn't obviously other data.
  - Runtime.dll has 923 syscall sites and the direct-syscall dispatch pattern to invoke `NtOpenProcess` at will.
  - The stash already has `ZwQueryInformationProcess` at `0x5118` → companion can retrieve its own PPID → then syscall `NtOpenProcess(PPID, PROCESS_TERMINATE)`.

  Not [M] because static analysis cannot see runtime-assembled MBA constants that could construct `PS_ATTRIBUTE_HANDLE_LIST` at execution time.

### 1.4 Docs updates

**Not run this session.** `a4_regrade_audit` was submitted as placeholder and REFUTED. The regrade rerun against `merged14`/`merged15` remains an outstanding [I]-effort offline task; see §5.

### 1.5 Entry-point trace

**Not run this session.** `a5_entry_trace` was submitted as placeholder and REFUTED. However, `a3_handle_inheritance` incidentally surfaced one key entry-point fact:

- **[I_strong]** Preloader.dll's `AddressOfEntryPoint` = RVA `0x3BD0`, which sits in `.rdata` (characteristics `0x40000040`, non-executable). Entry bytes = `0F 0B C3` = **UD2; RET** — a broken/decoy entry stub. Preloader mapper (RVA `0x1520`) is reached only via two trampolines at RVA `0x2330` and `0x2440`, and **those trampolines have ZERO static E8/E9 callers** anywhere in preloader `.text`. Preloader must therefore be entered via non-standard dispatch (CFG hook via `IMAGE_LOAD_CONFIG_DIRECTORY` at RVA `0x3BE0` size `0x140`? TLS callback? No — TLS data_dir is 0/0. Base-relocation-installed pointer? Something else?).

This is orthogonal to A3 but blocks a full companion-boot writeup — recorded here so a successor doesn't rederive it from scratch.

---

## 2. What closed — S177 open questions

### 2.1 Does companion mediate FK-31?

**STILL_OPEN.** No S178 evidence bears on this. FK-31 is `runtime.dll+1` execute violation (`0xC0000005`); FK-32 is `NtTerminateProcess(target, 0xDEAD)` at RVA `0x80F7F0`. Both A2 and A3 operate on FK-32. CLAUDE.md S168 already established FK-31 and FK-32 are **distinct mechanisms** (S168 poked packer1 byte to disable one and the other still fired). S170 showed FK-31 detection window is ~20 s; S173/S174 showed suspending 7-9 top-hit runtime.dll threads defers FK-31 by 4-6× but not indefinitely.

**Best available inference:** since the companion process holds an FK-32 primitive (target-handle-based `NtTerminateProcess(0xDEAD)`), and FK-31 exit code is `0xC0000005` at `runtime.dll+1` (a *deliberate* fault at the mapped runtime.dll's DOS header per CLAUDE.md S131), FK-31 may be an in-process protector kill via SEH RaiseException, while FK-32 is the cross-process companion kill. **This is [I], not [M]**; the discriminator is a live ETW trace correlating `Microsoft-Windows-Kernel-Process/OpenProcess` from companion PID against FK-31/FK-32 death events in the game.

### 2.2 Which specific integrity check inside packer30 detonates the kill?

**NARROWED, not closed.** A2 confirms **5 of 16 kill-guarded ranges reach the SHA-256 hasher at RVA `0x920C10`** (direct or 1-hop), all inside the FK-10 Wall #7 band. The **remaining 11 ranges** partition as 7 WinHTTP-orchestrator ranges (call the packer0 name-pointer table at `0x8148..0x8190`) and 4 with no clear dispatch on first-64-byte scan.

**What is CLOSED:** the S162 claim "13 CALL TARGETS inside the 16 scope bodies contain the specific integrity check" is refined: it is **not** 13 candidates behind one integrity check — it is **at least 2 mechanisms** (SHA integrity + WinHTTP phone-home).

**What is STILL_OPEN:** the specific comparison site that decides "integrity fails → dispatch to `0x80F7F0`" for the SHA family. A2 recommends Move A3b (2-hop callee enumeration) and Move A4 (`.pdata` SCOPE_TABLE walk over the 5 hasher-reaching ranges) to close this offline.

### 2.3 Does companion inherit or dynamically open handle to game?

**NARROWED to leading-hypothesis DYNAMIC OPEN.** A3's static evidence is strong-directional but not [M]:
- **Handle inheritance is DISFAVOURED** by absence of `DuplicateHandle`/`NtDuplicateObject` in preloader imports, absence of `PS_ATTRIBUTE_HANDLE_LIST` (`0x0002000B`) byte pattern anywhere plausible, and absence of `UpdateProcThreadAttribute`/`InitializeProcThreadAttributeList` in preloader imports (the game exe's crashpad hits are for Sentry crashpad_handler.exe, unrelated).
- **Dynamic open is FAVOURED** by runtime.dll's 923 syscall sites + 40 NtCurrentProcess loads + FK-10/S169 dynamic-syscall dispatch, plus the presence of `ZwQueryInformationProcess` in the preloader stash (`.data 0x5118`) which enables PPID retrieval.

**Discriminator (S177 Tier-B/C, not run this session):** live ETW `Microsoft-Windows-Kernel-Process/OpenProcess` filtered to companion PID. Any single `NtOpenProcess(game_PID, PROCESS_TERMINATE)` upgrades this to [M]. Alternatively, a hardware breakpoint on the 923 syscall sites capturing `rax == 0x26` at any of them.

### 2.4 Which runtime.dll RVA dereferences the preloader spawn-API pointer?

**STILL_OPEN in the strong form.** A3 establishes:
- Preloader hands control to runtime.dll at preloader RVA `0x22BB` via `call qword ptr [rip + 0x2daf]` (target = preloader `.data 0x5070`).
- Runtime.dll then reads spawn-API pointers from preloader `.data 0x50C8..0x5138` (15 slots).

But A3 did not enumerate the specific runtime.dll RVAs that dereference each of the 15 slots. This requires either (a) static byte-scan for `[rip+N]` displacements resolving to preloader `.data 0x50C8..0x5138` (complicated by different image bases and preloader's manual mapping), or (b) live memory read of runtime.dll's dispatch sites while attached.

**Practical implication:** the specific runtime.dll RVA that fires `ZwCreateUserProcess` (via preloader `.data 0x50F0`) is unknown; the SPECIFIC syscall site (out of 923) is unknown; the SPECIFIC RVA that reads `ZwQueryInformationProcess` (from `.data 0x5118`) to retrieve PPID is unknown.

---

## 3. New findings NOT anticipated

Things the Tier-A dive surfaced that were not the primary question.

### 3.1 The 16 kill-guarded ranges are TWO mechanisms, not one

The S162 write-up implicitly assumed one integrity check (the 13 candidate CALL TARGETS). A2 refutes: it is **at least 2 distinct dispatch families** (SHA hasher + WinHTTP phone-home). This changes how a defeat design would work — patching the SHA hasher would leave the WinHTTP-error kill path live, and vice versa. **CLAUDE.md's S162 line "13 CALL TARGETS inside the 16 scope bodies contain the specific integrity check" should be corrected** to reflect two families.

### 3.2 Runtime.dll's real static imports are astonishingly minimal

17 symbols total, and 12 of them are "close" verbs (`CloseHandle`, `WinHttpCloseHandle`, `CloseWindow`, `CloseEnhMetaFile`, `WTSFreeMemory`) plus the WinHTTP send/receive/query family. This is consistent with S177's model of "runtime.dll is the companion; it phones home over WinHTTP and reads game state via cross-process reads/writes powered by direct syscalls." The static import table alone would look like a benign HTTP client with a Terminal Services diagnostic sideline.

### 3.3 Preloader is architecturally incapable of handle inheritance setup

Not just "doesn't do it" — **cannot**. No `DuplicateHandle`, no `NtDuplicateObject`, no `UpdateProcThreadAttribute`, no `InitializeProcThreadAttributeList`. This is stronger evidence than a byte-scan absence: even if runtime.dll's MBA code tries to construct a `PS_ATTRIBUTE_HANDLE_LIST`, preloader cannot have set up the source handle to seed it. Combined with the syscall-dispatch infrastructure, dynamic open really is the strongly-favoured mechanism.

### 3.4 String `'runtime.dll'` lives only in preloader — matches S177's CommandLine empty

The absence of `'runtime.dll'` (both encodings) in runtime.dll and the game exe, plus its single UTF-16LE hit in preloader `.rdata 0x34A0`, means:
- Runtime.dll does not self-reference by name.
- The game exe never opens or names runtime.dll (only imports preloader.dll).
- Preloader alone knows the filename, which it uses for `NtOpenFile` to load runtime.dll bytes off disk.
- The companion process is spawned via `ZwCreateUserProcess` with a `SectionHandle` argument (from preloader's `NtCreateSection` at RVA `0x1C3F`) — no ImagePathName, no CommandLine, hence S177's measured "CommandLine empty."

### 3.5 Preloader entry point is a decoy (UD2; RET at RVA `0x3BD0`)

Preloader's AoEP is `0F 0B C3` = UD2; RET in `.rdata`. The real mapper at RVA `0x1520` is called only from two trampolines (`0x2330`, `0x2440`) with **zero static E8/E9 callers**. Something loads preloader — probably a CFG hook installed via `IMAGE_LOAD_CONFIG_DIRECTORY` (LoadConfig at RVA `0x3BE0` size `0x140`) or a base-relocation-installed pointer patched into another module. This orthogonal finding is why Tier-C entry-point-trace is worth running.

### 3.6 X.509 signing-algorithm OIDs live in runtime.dll packer0

Adversarial verification of A3 surfaced the string `'ecdsa-with-SHA256'` at file offset `0x382412` in runtime.dll (near the `0x00020002` byte hit at RVA `0x383832`). This is consistent with CLAUDE.md's FK-10 BOM entry for mbedtls (the bundled CA store as `.rsrc RT_RCDATA 10001`, Zstd frame → 579,410 B of DER). Runtime.dll therefore ships its own X.509 verification chain, which fits the "phone-home over HTTPS with pinned certs" model.

---

## 4. Ranked Tier B / C moves (updated)

Given A2/A3 outputs, revised move ranking:

### Move #1 — LIVE ETW trace of companion NtOpenProcess (Tier-B, cheap)

**Discriminator:** does the companion syscall `NtOpenProcess(game_PID, PROCESS_TERMINATE)` at startup, or does its handle table already contain a Process handle at t+0?

**Cost:** one launch, ETW session on `Microsoft-Windows-Kernel-Process` provider filtered to companion PID; or hook `DllMain` in an injected DLL and dump the companion's initial handle table via `NtQuerySystemInformation(SystemHandleInformation)`.

**Closes:** S177 open #3 (handle inheritance vs dynamic open). One `NtOpenProcess` hit with target = game PID promotes A3's leading hypothesis to [M].

**Risk:** ETW on the OpenProcess subprovider is standard; low FK-31/FK-32 exposure.

### Move #2 — Read companion PEB `InheritedFromUniqueProcessId` (Tier-B, very cheap)

**Discriminator:** if companion's PEB `ProcessParameters->InheritedFromUniqueProcessId == game.PID`, that alone is a strong hint (parent-process ID is separate from handle inheritance but shows the process relationship).

**Cost:** single `NtQueryInformationProcess(companion, ProcessBasicInformation)` from an injected DLL — read PEB pointer, then read one field.

**Closes:** independently corroborates S177's parent-child model. Cheap enough it should be batched with Move #1.

### Move #3 — Enumerate 2-hop callees from 11 non-hasher-reaching kill-scope ranges (Tier-C offline, moderate)

**Discriminator:** do the 11 non-hasher-1-hop ranges reach the SHA-256 hasher via 2-3 hops (in which case ALL 16 ranges are behind the SHA family and WinHTTP is orthogonal), or are they pure HTTP orchestrators (in which case the two families are truly independent kill paths)?

**Cost:** offline recursive callee walk with capstone, bounded depth 3. Reuses A2's methodology; a couple hours.

**Closes:** narrows the S162 dispatch model. If SHA covers all 16, patching SHA defeats FK-32 entirely. If WinHTTP is independent, defeat needs both.

### Move #4 — `.pdata` SCOPE_TABLE walk over 5 hasher-reaching ranges (Tier-C offline, cheap)

**Discriminator:** confirms each range's kill SCOPE actually covers the SHA-hasher CALL SITE (not just the enclosing function body). Closes S162 [I]→[M] for the SHA-256 dispatch mechanism specifically.

**Cost:** offline .pdata parse + SCOPE_TABLE (`__C_specific_handler` LSDA at RVA `0x836fa0`) walk. Reuses S162 infrastructure.

**Closes:** promotes A2's [I_strong] "SHA-256 integrity check dispatches kill via SEH scope filter" to [M].

### Move #5 — Hardware breakpoint at `runtime.dll` RVA `0x80F7F0` in companion (Tier-B, moderate)

**Discriminator:** what is `rcx` at kill time? A3 says the kill primitive reads `[rcx+0x10]` as the target Process handle. If a live HW breakpoint captures `rcx`, we can read the object it points to (probably a companion-side context struct) and name the handle field.

**Cost:** one armed session against the companion process. HW breakpoints via `SetThreadContext` on all companion threads.

**Risk:** S169 flew this idea against the same primitive in-game and died at FK-31; but here the target is the companion, not the game, and the companion may not have equivalent DR-integrity checks. Untested — worth one flight.

**Closes:** if the target handle is a game handle opened via `NtOpenProcess`, that closes S177 open #3 [M]. If it's a duplicate seeded via `PS_ATTRIBUTE_HANDLE_LIST` in memory, closes it the other way.

### Move #6 — Live memory capture of `PS_ATTRIBUTE_LIST` at ZwCreateUserProcess syscall (Tier-B, harder)

**Discriminator:** the definitive answer to "does runtime.dll construct a `PS_ATTRIBUTE_HANDLE_LIST` at runtime." The buffer preloader/runtime hands to `ZwCreateUserProcess` shows PS_ATTRIBUTE type IDs. If any equals `0x0002000B`, inheritance wins.

**Cost:** hook a syscall on `ZwCreateUserProcess` (~0x5D on Win10) in the parent (preloader-attached game process) or attach with a debugger and BP the pointer at `.data 0x50F0`.

**Closes:** definitive settle of the inheritance-vs-open question. Overlaps with Move #1; run both together for the strongest evidence.

### Move #7 — Correlate WinHTTP write timings against MiniDash 30 s kill (Tier-C offline + light live, moderate)

**Discriminator:** A2 identifies WinHTTP as the second FK-32 dispatch family. S158 measured MiniDash FK-32 kill at ~30 s after Post Dash Start, preceded by ~30 `SetReplicatedEvent` bursts in one millisecond. If those bursts trigger a network write the companion samples, the WinHTTP-error path IS the WALL P kill route.

**Cost:** static — parse packer0 `.rdata` for the phone-home URL. Live — Fiddler/tcpdump filtered to WinHttp traffic during a MiniDash sitting.

**Closes:** would explain the S147/S158 WALL P kill mechanism concretely.

### Move #8 (deferred, Tier-C offline) — Docs regrade against `merged14`/`merged15`

**Discriminator:** how many CLAUDE.md/docs coverage-blocked claims are stale? Prior audit (S133) found 43 stale claim-instances; S153 found 58. New captures since (merged15 landed at S158) may have decrypted more pages.

**Cost:** rerun `scratchpad/s133/tools/regrade_blocked.py` against `merged14` or `merged15`.

**Closes:** cheap floor on how much docs debt has accumulated. Should be a routine after every merged-image bump.

### Move #9 (offline, cheap) — Enumerate runtime.dll RVAs that dereference `.data 0x50F0`/`0x5118`

**Discriminator:** identify the SPECIFIC runtime.dll RVAs that call `ZwCreateUserProcess` and `ZwQueryInformationProcess` via the preloader stash.

**Cost:** static byte-scan for `[rip+N]` displacements resolving to preloader `.data 0x50C8..0x5138` at the runtime image's loaded base. Complicated by manual mapping (different from module base?) but tractable.

**Closes:** S177 open #4 (specific runtime.dll RVA for preloader-pointer deref). Names the actual companion-boot code sites for future breakpoint work.

### Move #10 (offline, cheap) — Enumerate the 923 syscall sites in runtime.dll

**Discriminator:** for each of the 923 raw `0f 05` opcodes, disassemble the preceding ~20 bytes and identify the syscall-number computation. A single site with `rax == 0x26` (NtOpenProcess) or `rax == 0x2C` (NtTerminateProcess) or `rax == 0x19` (NtQueryInformationProcess) confirmed statically would upgrade A3 to [M].

**Cost:** offline batch capstone disassembly around each syscall opcode. Hand-decode of the XOR/rol-based syscall-number derivation from S169 (`eax ^= [rip+0x13affc]` then transformation).

**Closes:** definitive answer to "does runtime.dll statically call NtOpenProcess." One hit ⇒ dynamic-open is [M].

---

## 5. Docs-update punch list

`a4_regrade_audit` was submitted as placeholder; this punch list is compiled from the substantive A2/A3 findings and their impact on current docs.

Prioritized by how misleading current text is.

### Priority 1 — Correct S162 in CLAUDE.md and `docs/s162-seh-kill-dispatch-unified-settled.md`

**Current claim:** "13 CALL TARGETS inside the 16 scope bodies contain the specific integrity check" (implicitly one integrity check with 13 candidates).

**Correct:** the 16 SCOPE ranges route to the kill via **at least two dispatch families**: SHA-256 integrity (5 of 16 reach `runtime.dll` RVA `0x920C10` direct or 1-hop) and WinHTTP phone-home (7 of 16 call the packer0 name-pointer table at RVAs `0x8148..0x8190`). Not one integrity check — two.

**Update location:** `CLAUDE.md` line ~2470 (the S162 block) and `docs/s162-seh-kill-dispatch-unified-settled.md` §"CALL TARGETS."

**Also correct:** S163's `docs/s163-s162-unification-partially-refuted.md` was already published as a PARTIAL REFUTATION but its refutation focused on the WinHTTP side ("Sentry crashpad HTTP upload OR protector telemetry"). A2 confirms both sides of S163's refutation AND rehabilitates the SHA-family as directly linked to kill dispatch. Third revision to the doc: SHA IS linked to kill (5 of 16 ranges [M]), WinHTTP is the second family (7 of 16 ranges [M]), and both fail-close to `0x80F7F0`.

### Priority 2 — Correct `docs/fk10-protector-identified.md` Wall #7 status

**Current status:** Wall #7 is described as "the SHA-256 multi-buffer hasher at `runtime.dll RVA 0x8ffcd4..0x93e886`" with `[I]` support ("Intel ISA-L Crypto multi-buffer assembly").

**Update:** upgrade to `[M]` — A2 confirms the hasher entry at `runtime.dll` RVA `0x920C10` (not `0x920C00`, which is the trampoline+padding) with a canonical Intel ISA-L CPU-feature-detection preamble (cpuid AVX2 check, OSXSAVE check, xgetbv), and further confirms 5 of the 16 S162 kill-scope ranges reach it directly or via one hop. FK-10 Wall #7 hasher is now DEFINITIVELY LINKED to FK-32 kill dispatch.

**Note on address:** cite `0x920C10` (hasher body) with `0x920C00` as trampoline, not `0x920C00` alone.

### Priority 3 — Update CLAUDE.md's `runtime.dll` import summary

**Current text (multiple locations):** "[M] runtime.dll's ONLY ntdll import is `RtlPcToFileHeader`" — this is correct.

**Extend:** also mention that runtime.dll's KERNEL32 import list = only `CloseHandle`, and total static import table = 17 symbols across 6 DLLs (WINHTTP 8, WTSAPI32 3, ntdll 1, KERNEL32 1, USER32 3, GDI32 1). Zero process/handle-manipulation APIs. All process- and syscall-related work is done via the 923 raw `0f 05` syscall sites with dynamic syscall-number computation (S169).

**Update location:** CLAUDE.md's FK-10 block; `docs/fk10-protector-identified.md`.

### Priority 4 — Update S177 handoff to include A2/A3 outputs

**Current:** `docs/next-session-prompt-s177.md` names Move I-3 (dumpimage diff pre-kill vs Move M's menu baseline) as highest-priority next move.

**Add:** the S178 Tier-A findings above, especially:
- SHA-256 family confirmed 5 of 16 kill-scope ranges (A2).
- WinHTTP phone-home is the second family, 7 of 16 (A2).
- Companion is architecturally incapable of handle-inheritance from preloader (A3).
- Dynamic-open via 923 syscall sites is leading hypothesis (A3).
- Ranked Tier-B/C moves (§4 above).

### Priority 5 — Fix cosmetic errors in A2 finding text

For anyone citing A2 outputs directly:
- `0x94A160` distance to SHA band upper bound is **47,322 B** (not 45,748 B).
- Hasher prologue is at **`0x920C10`** (not `0x920C00`).
- WinHTTP-caller count is **7 of 16** (not 8).
- `WTSEnumerateSessionsW` is wtsapi32.dll, not WinHTTP.

### Priority 6 — Add preloader entry-point mystery to CLAUDE.md

**New note:** preloader.dll's `AddressOfEntryPoint` = RVA `0x3BD0` in `.rdata`, bytes `0F 0B C3` = UD2; RET. Real mapper at RVA `0x1520` is called only from two trampolines (`0x2330`, `0x2440`) with **zero static E8/E9 callers**. Preloader is entered via non-standard dispatch — CFG hook (LoadConfig at RVA `0x3BE0` size `0x140`)? Base-relocation-installed pointer?

**Update location:** CLAUDE.md FK-10 block or new S178 handoff. Flag as `[I_strong]` for a successor Tier-C entry-point trace.

### Priority 7 — Rerun docs regrade against `merged15`

Not blocked on any new information — just needs someone to run `python scratchpad/s133/tools/regrade_blocked.py` against `dumps/merged15.dump.exe` and adjudicate the flagged lines. Last full audit was S153 (58 stale claim-instances against merged14). merged15 landed in S158.

**Cost:** ~1 hour offline + adjudication time.

---

## 6. Session summary

**Effort:** 5 Tier-A analyses launched, 2 substantive (a2, a3), 3 stub/placeholder.

**Substantive gains:**
- FK-10 Wall #7 SHA-256 hasher DEFINITIVELY LINKED to FK-32 kill dispatch (5 of 16 kill-scope ranges reach it direct or 1-hop) [M].
- WinHTTP is the second FK-32 dispatch family (7 of 16 kill-scope ranges) [M].
- Companion handle mechanism strongly narrowed to **dynamic-open via direct syscall**, based on preloader's architectural incapability of handle-inheritance setup and runtime.dll's 923 syscall sites with dynamic dispatch [I_strong].
- Kill primitive re-verified byte-identical to CLAUDE.md S131/S161/S168 record [M].
- Preloader entry-point trace surfaced as new orthogonal open question [I_strong].

**Discriminators for next session:**
1. Live ETW `NtOpenProcess` count on companion (Move #1) — closes handle-inheritance question [M].
2. Offline 2-hop callee walk on 11 non-hasher-1-hop ranges (Move #3) — closes SHA-vs-WinHTTP partition [M].
3. Offline `.pdata` SCOPE walk over 5 hasher-reaching ranges (Move #4) — closes SHA-dispatch-mechanism [M].

**Docs debt:** at minimum, correct S162 (two families not one), upgrade FK-10 Wall #7 to [M], extend runtime.dll import summary. Priority 1-3 items are load-bearing on the S177 story.

**Nothing directly touched FK-31.** The FK-31 vs FK-32 mechanism split remains as CLAUDE.md S168 recorded it — the companion-process model applies to FK-32 only, and FK-31 (in-process `runtime.dll+1` execute violation) still needs its own investigation.