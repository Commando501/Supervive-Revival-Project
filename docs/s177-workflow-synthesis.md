# S177 Runtime.dll Companion Process — Six-Way Synthesis

Consolidates six parallel offline analyses (pe_headers, etw_mining, spawn_caller, kill_caller, fk31_reanalysis, companion_ipc) into one operational picture of the S177 companion-process discovery. Every analysis produced usable data; two returned PARTIAL verdicts on specific sub-claims and those downgrades are folded in below rather than repeated in a separate section.

---

## 1. The unified picture

- **`runtime.dll` is an EXECUTABLE mis-extensioned as a DLL, not a DLL that Windows happens to spawn as a process.** [pe_headers] measured PE Characteristics=0x22 at file offset 0x8E with `IMAGE_FILE_DLL` (0x2000) CLEAR and `IMAGE_FILE_EXECUTABLE_IMAGE` (0x0002) SET, Subsystem=2 (WINDOWS_GUI), ImageBase=0x200000000, SizeOfImage=0x4066000, AddressOfEntryPoint=RVA 0x855440. Export Directory is RVA=0 size=0 (a DLL exports nothing has no purpose). Bit-exactly matches the mapping FK-10 §168 and S131 measured live at `0x7FFCA1400000`. [kill_caller] independently confirmed the same bytes and additionally read the AoEP body: bytes at RVA 0x855440 (`e9 4a cf b3 00`) are a 5-byte E9 rel32 to RVA 0x139238F in packer30, which begins with a real MSVC `main()` prologue (push rbp/r15/r14/r13/r12/rsi/rdi/rbx; sub rsp,0x78 — 8 GPR pushes + 120-byte frame, incompatible with DllMain's `BOOL(HINSTANCE,DWORD,LPVOID)` shape). **The 67.5 MB file at `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll` was linked as an EXE by MSVC 2015+ (MajorLinkerVersion=14) and the .dll extension is concealment.**

- **The spawn is initiated by code inside the game process using an obfuscated `ZwCreateUserProcess` pointer resolved by `preloader.dll`, not by any statically-imported spawn API in the game exe or in runtime.dll itself.** [spawn_caller] enumerated all imports of all three binaries: game exe imports EXACTLY 1 symbol (`preloader.dll!preloader_link_func` at RVA 0x24f0, a naked `0xC3 ret` whose only job is to force preloader.dll to load); runtime.dll's static import table is a 17-function decoy across 6 DLLs with ZERO process-creation APIs and its only ntdll import is `RtlPcToFileHeader`; **preloader.dll (26,824 B, signed "Theorycraft Games Inc.", ImageBase 0x180000000) is the sole binary in the address space that statically imports process-creation primitives** — `ZwCreateUserProcess` at IAT RVA 0x4208, `RtlCreateProcessParametersEx` at 0x41b0, plus 13 more Zw/Rtl file/env APIs. But preloader NEVER CALLS its own `ZwCreateUserProcess` slot: at .text RVA 0x21df it executes `mov rax, [rip+0x2022]` (loading the IAT slot value) followed by `mov [rip+0x2F03], rax` (storing to `.data 0x50f0`), then at .text 0x22bb does `call qword ptr [rip+0x2DAF]` → `.data 0x5070` (an indirect call into a runtime.dll entry point via a slot populated earlier by `LdrGetProcedureAddress` at .text 0x163d/0x16b4). **This is the preloader→runtime handoff: preloader stashes 15 spawn/env/file API pointers into a shared table at preloader `.data 0x50c0..0x50f8`, then hands control to runtime.dll code which reads those pointers to issue the actual `ZwCreateUserProcess`.** [pe_headers]'s finding that runtime.dll's static imports contain zero spawn APIs is not a contradiction — it is the explanation of why the dispatch is invisible to conventional import-table analysis.

- **The child process is spawned via the object-manager NT namespace form, with NO command-line arguments passed.** [etw_mining] captured the Process.Start row at Clock-Time `134330153090413963`: field [27] `ImageName` = `runtime.dll`, field [28] `ImageFullPath` = `\??\G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll`, **field [29] `CommandLine` = empty string**. The `\??\` prefix is the NT object-manager form (consistent with `NtCreateUserProcess` / `RtlCreateProcessParametersEx` being called directly, not Win32 `CreateProcessW`). [companion_ipc]'s adversarial re-verification of the same CSV row confirmed: aggregated across 148 Process.Start events, only 10 have non-empty CommandLine (all EpicWebHelper.exe with numeric tokens or updater.exe); **the runtime.dll killer spawn's CommandLine is measurably empty, not absent-because-unmeasured.** This refuted [companion_ipc]'s own [M]-graded fact #9 that "there is no commandline in the ETW Process Start payload" — the CSV rows have 31 columns not 20, and the finder's parser stopped reading at column 20.

- **The companion runs for exactly 4.09 seconds, does bespoke HTTPS + minidump work, then kills the game with `NtTerminateProcess(hGame, 0xDEAD)`.** [etw_mining] reconstructed 4 phases from 46 Image.Load rows: (Phase 1 t=0–90ms) 21 standard Win32 DLLs plus `winhttp.dll` at t+3.294ms, `wtsapi32.dll` at t+3.334ms, `dbgcore.dll` at t+30.813ms, `dbghelp.dll` at t+32.389ms (minidump-writer support). Initial thread TID 0x93D0 starts at `0x7FF7B2095440` = ImageBase 0x7FF7B1840000 + RVA 0x855440 (the confirmed AoEP). (Phase 2 t~1.67s) dbghelp/advapi32/psapi UNLOAD (dbghelp job complete), then the winsock+TLS stack loads t=1671–1756ms: ws2_32, webio, mswsock, IPHLPAPI, DNS, Bonjour LSP, sspicli, FWPUCLNT, schannel, mskeyprotect, ncrypt/sslp, bcryptprimitives, crypt32, msasn1. Kernel-initiated thread TID 0x55C0 appears at +1674.5ms with SYSTEM PID 4 TID 0x24 as parent (WinHTTP I/O completion worker). (Phase 3 t~2.34s silence) threads blocked on WinHTTP recv. (Phase 4 t+4094.4ms) `dpapi.dll` loads at t+4093.4ms — **exactly 1ms before the fatal call** — then TID 0x93D0 executes `NtTerminateProcess(0x2058, 0xDEAD)` at Clock-Time `134330153131357636` (t+4094.373ms) and `NtTerminateProcess(0x4C50, self)` at `134330153131364164` (t+4095.021ms), a 0.648ms gap consistent with `TerminateProcess(hGame,0xDEAD); ExitProcess()`. Every non-runtime.dll module load is Microsoft-signed System32 code (only exception is Bonjour mdnsNSP, a system-wide Winsock LSP). ZERO EAC, ZERO Steam, ZERO EOSSDK, ZERO unsigned drivers.

- **The kill primitive at `runtime.dll` RVA 0x80F7F0 has ZERO conventional callers image-wide; dispatch is Windows SEH scope-filter via `__C_specific_handler`.** [kill_caller] confirmed FK-10's 5-slot vtable at packer0 RVA 0x1831C0 byte-exact (slots `[0..4]` = 0x871030, 0x8D9480, 0x8B8B60, 0x8131D0=NtCreateThreadEx obfuscated syscall, 0x80F7F0=KILL). Kill bytes match S168 exactly: `4c 8b 51 10 4d 85 d2 74 1b [obfuscated syscall# via XOR against packer2 RVA 0x94A800 per S169] ba ad de 00 00 0f 05 c3 31 c0 c3`. But **exhaustive byte-level searches over the full 67 MB image return ZERO hits for every conventional caller pattern targeting kill (0x80F7F0) OR constructor (0x7F86F0)**: 0 direct E8 CALLs, 0 E9 tail JMPs, 0 FF-15 indirect CALLs, 0 FF-25 indirect JMPs, 0 MOVABS r64,imm64 loading the absolute VA, 0 MOVABS with the negated VA (the MBA polynomial-tail-jmp form), 0 LEA r64,[rip+disp32] to either. Kill's absolute VA `0x20080F7F0` appears exactly ONCE as an 8-byte qword anywhere: at packer0 RVA 0x1831E0 = vtable slot 4 itself. **The actual dispatch mechanism is measured in packer42**: at 16-byte alignment offset 12, `44,464` well-formed SCOPE_TABLE records (68.8% of raw slots — matches S162's game-side count of ~46,364 within alignment noise); **16 of them have `HandlerAddress = 0x80F7F0` and `JumpTarget = 0`, guarding 5–45 byte code ranges inside packer30**; 19 more have `HandlerAddress = 0x7F86F0` (the constructor) guarding 5–21 byte ranges in packer30. The chain: integrity check in one of 16 packer30 sites deliberately faults inside its guarded range → `KiUserExceptionDispatcher` in companion's ntdll → walks the loader function table at packer40 RVA `0x14D8758` (18,580 RUNTIME_FUNCTION entries; ctor is entry [238] with Begin=0x7F86F0 End=0x7F873A UnwindInfo=0x7C9F9C, matching bit-for-bit) → resolves `__C_specific_handler` → walks inline SCOPE_TABLE → matches HandlerAddress=0x80F7F0 → invokes 0x80F7F0 with rcx=`EXCEPTION_POINTERS*` (which is why the kill reads `[rcx+0x10]` as the process handle) → syscall = `NtTerminateProcess(handle, 0xDEAD)`.

- **The companion's own runtime.dll uses handle inheritance to receive the game's PROCESS_TERMINATE handle, not `OpenProcess` or IPC.** [companion_ipc] enumerated runtime.dll's full static+delay import surface: 17 functions across 6 DLLs, ZERO of the requested candidates present (no `OpenProcess`, no `ReadProcessMemory`, no `NtReadVirtualMemory`, no `CreateFileMapping*`, no `MapViewOfFile`, no `CreateNamedPipe*`, no `CreateEvent*`, no `SetEvent`, no `WaitForSingleObject`). The lone handle-related plaintext import is `kernel32!CloseHandle` in isolation, meaning **the companion HAS a handle it needs to release but did not open via any statically-imported API** — consistent with inheritance from parent (or opening via packer2 obfuscated syscall, though the four-second single-shot lifetime with no bidirectional exchange favors inheritance). The empty CommandLine measured in bullet 3 rules out "target PID passed via argv"; the empty CommandLine ALSO rules out "handle number passed via argv". Companion emits zero ETW-visible WPM/RPM/section-map/pipe/event activity during its 4-second life (though the trace's PROC_THREAD+LOADER-only providers cannot POSITIVELY exclude memory ops — instrument blind spot).

- **`FK-31` (0xC0000005 at `runtime.dll+1`) is IN-PROCESS from the game's HIGH mapping of runtime.dll, distinct from FK-32's companion-driven kill.** [fk31_reanalysis] carried a `PARTIAL` verdict but the central claim survives: S168 already directly measured that a 1-byte `.text` patch at runtime.dll RVA 0x80F7F7 (je→jmp) applied via `VirtualProtectEx` + `WPM` + `FlushInstructionCache` with readback verification produced `0xC0000005` at `0x7FFCA1400001` within ~3 minutes with no shim injected, no game state mutated. Companion cannot be involved because its own kill produces `0xDEAD` not `0xC0000005`, produces no minidump, and has ~5s trigger-to-spawn latency vs FK-31's ~10s post-fo firing. **FK-31 always produces a Sentry crashpad minidump (fault RIP == runtime.dll+1, EXECUTE flag); FK-32 never produces one (exit code 0xDEAD). This is a free retroactive discriminator over the entire crashpad corpus.**

- **The FK-31/FK-32 split is now mechanistically clean: two integrity check populations, one runtime.dll codebase, two execution modes.** [kill_caller] and [fk31_reanalysis] converge: `runtime.dll` runs in TWO places — (a) manually-mapped inside the game process at `0x7FFCA1400000` (46 MB `MEM_IMAGE` hidden from module list per FK-10/S131), which hosts the FK-31 self-integrity check that produces AV at base+1 via S131/S132's MBA-flattened computed tail-jmp pattern; (b) as a standalone process spawned via the preloader→runtime handoff, which hosts the FK-32 anti-tamper watchdog that terminates the game via SEH-scope-dispatch through the kill primitive at RVA 0x80F7F0. **Both instances execute the same on-disk bytes but with different runtime patches (S169 measured the packer2 XOR-key patch at RVA 0x94A803) and different execution contexts.** This explains why CLAUDE.md's S166 game-side poke of the 16 kill scope entries in packer42 did nothing: the poke went to the game's mapping, but the SEH dispatch that fires the kill lives in the COMPANION's mapping.

- **The companion is a Sentry-style HTTPS uploader with kill authority.** [etw_mining] flagged the module-load fingerprint as diagnostic (winhttp early + dbghelp/dbgcore for minidump + schannel/crypt32 for TLS + dpapi 1ms before kill for token decrypt + no third-party components). This shape matches FK-10's recorded packer/3.3.1 Sentry client DSN embedded in runtime.dll pointing at the same Sentry endpoint (`o566896.ingest.sentry.io`, `sentry_key=149a7ac2a7914150b87ce714fd4d6444`) that the game's own `crashpad_handler.exe` (spawned at T+5.96s) uses. The Sentry infrastructure is dual-used: game crashes upload via `crashpad_handler.exe` with `sentry_client=sentry.native.unreal/0.7.6`; anti-tamper reports upload via the runtime.dll companion with `sentry_client=packer/3.3.1`.

- **The trigger for the companion spawn is DR install (S177 flight 9), latency ~5s trigger-to-spawn.** [fk31_reanalysis]'s verifier corrected its own timing argument: the finding cited "~50s spawn latency" from S177 flight 7 which measured game-start-to-companion-start, but S177 flight 9 measured trigger-to-spawn at ~5s after a fresh DR install. This is the operationally relevant latency for defeat strategies. `companion_watch --kill-on-sight` (with ~220ms kill window per S177) can beat the 5s latency for the companion but does nothing for FK-31 which fires ~10s post-fo without any companion spawn.

---

## 2. What contradicts what

### 2.1 Companion causation of FK-31 — [fk31_reanalysis] verdict PARTIAL, two [I_strong] downgrades

The finding claimed companion-mediated FK-31 was ruled out by (a) timing incompatibility (~50s companion latency vs ~10s FK-31 firing) and (b) absence of WPM behavior in ETW. Verifier refuted both supporting arguments while preserving the central conclusion:

- **Timing argument DOWNGRADED to [I]:** the "~50s companion latency" comes from S177 flight 7's game-start-to-companion-start, but S177 flight 9 measured the actual trigger-to-spawn latency at ~5s after DR install. Companion can in principle spawn within FK-31's ~10s window. The finding-as-written was over-confident; corrected finding: timing alone does not exclude companion mediation, only makes it tight.
- **"No WPM behavior observed" DOWNGRADED to [I]:** the ETW trace's enabled providers were PROC_THREAD + LOADER only — blind by design to VirtualAlloc, VirtualProtect, WriteProcessMemory, NtWriteVirtualMemory, SetThreadContext. Absence-of-evidence is not evidence-of-absence when the instrument cannot capture the event class. Classic instrument-blind-spot pattern (CLAUDE.md method-rules §1).

**Winner:** the central claim (FK-31 is in-process, not companion-driven) survives on **S168's direct measurement alone** (`docs/s168-runtime-dll-self-checks-fk31-fk32-are-different.md`): a 1-byte runtime.dll .text patch produced 0xC0000005 at runtime.dll+1 within 3 minutes with no shim injected. That measurement is [M] and does not depend on the two downgraded supporting arguments. **Preserve the conclusion; drop the two weak supports; run the definitive experiment named in §4.**

### 2.2 CommandLine unverifiability — [companion_ipc] Fact #9 REFUTED

The finding claimed [M] that "there is NO commandline in the ETW Process Start payload for any process in this trace, so 'game passes its PID via cmdline' cannot be tested." Verifier refuted: the CSV rows have 31 columns, not the 20 the finder's parser stopped at; the killer runtime.dll spawn's field [29] `CommandLine` is measurably EMPTY (`""`) and field [28] `ImageFullPath` is the full NT-prefixed path. Aggregated: 10 of 148 Start events have non-empty CommandLine (EpicWebHelper.exe with numeric tokens; updater.exe with `0x278`/`0x27c`).

**Winner:** the verifier. This actually STRENGTHENS the overall picture — we now have a positive measurement that the game does NOT pass a PID or handle number via argv to the killer, which further supports handle-inheritance as the leading IPC mechanism (bullet 6 in §1). The finding's next-move item recommending re-instrumentation is now unnecessary; the data was already in the trace.

### 2.3 S166's SCOPE-poke refutation — reinterpretation, not contradiction

CLAUDE.md's S166 recorded that WPM-poking `HandlerAddress = 0xFFFFFFFF` on all 16 packer42 kill-scope entries × 2 mappings did NOT prevent FK-32 (kill still fired at t+69.6s), which was used to REFUTE the SEH-scope-dispatch model. [kill_caller] proposes this refutation is scope-limited: **S166 poked the GAME's mapping of runtime.dll; S177 discovered FK-32 fires from a COMPANION process running a separate mapping of the same bytes.** The game-side poke never touched the mapping that actually dispatches. This is not a two-sided contradiction — S166's measurement is preserved, only its scope is narrowed.

**Winner:** consistent with [kill_caller]'s reading, pending the definitive experiment in §4 (poke the SCOPE entries in the COMPANION's packer42 mapping).

### 2.4 SCOPE record count — 44,464 vs 44,465

Trivial: [kill_caller] finding reported 44,465 well-formed SCOPE records at alignment 12; verifier measured 44,464 (single-record boundary difference, 0.002%). Not material — the 16 kill-scope + 19 ctor-scope histograms hold identically. Winner: neither, it's rounding noise on a boundary check.

### 2.5 Kill-guarded scope BeginAddress transcription

Trivial: [kill_caller] evidence list included `0x140080A` as the 16th kill-guarded BeginAddress but verifier measured `0x134080A` — likely a single-character typo in transcription (digit `3` mistyped as `4`). Other 15 addresses match exactly. All 16 addresses are inside packer30 as claimed. Not material to any conclusion.

---

## 3. What we still don't know

- **What specific runtime.dll RVA dereferences `preloader.dll` `.data 0x50f0` to issue `ZwCreateUserProcess`?** [spawn_caller] identified the preloader-side pointer stash but the runtime.dll consumer call-site is invisible to static analysis: runtime.dll is 46.6 MB of MBA-obfuscated code (~45% still undecrypted in a typical game process snapshot) and the pointer is passed at runtime (not compile-time rel32). `merged14.dump.exe` holds the game exe's live-decrypted PE, not runtime.dll (which is manually-mapped and module-list-hidden — capturing its live decryption requires the S164 `dumpimage -includehiddenimages` patch applied to the COMPANION process, not the game).

- **Which specific integrity check inside packer30 detonates the kill?** [kill_caller] enumerated 16 kill-guarded BeginAddress RVAs (all in packer30 range `0x1322000..0x1434000`, ~1.1 MB, likely 1–3 large functions), but the actual check-function that faults into those ranges is unidentified. Same open question as CLAUDE.md's S162/S163: which of the 11 packer30 orchestrator functions contains all 16 kill sites?

- **Does the companion inherit its process handle to the game, or does it open one via a packer2-obfuscated `NtOpenProcess` syscall stub?** [companion_ipc] identifies handle inheritance as the leading hypothesis but cannot distinguish from an obfuscated-syscall open. The static import table's isolation of `CloseHandle` (with no `OpenProcess`) is diagnostic but not decisive — the packer2 obfuscated stubs hide ~160 syscalls per Move K.

- **Does the runtime.dll bytes loaded by the companion process match the on-disk bytes verbatim, or does the companion apply runtime patches beyond S169's packer2 XOR-key patch?** The S169 patch is documented; other patches may exist. A companion-side `dumpimage -includehiddenimages` would settle this.

- **What triggers the companion spawn other than DR install?** S177 flight 9 established DR install as one trigger with ~5s latency. Passive 3-minute flights showed NO spawn. Enumerating other triggers (integrity check failure? memory-write to specific regions? timer?) is open.

- **What is the WinHTTP endpoint the companion contacts during its 2.34-second silent phase (t~1.76s to t~4.09s)?** [etw_mining] observed the winsock/TLS stack loads at t=1671–1756ms and worker threads blocked with no ETW events until Terminate. Loading `dpapi.dll` 1ms before Terminate strongly suggests a stored-token decrypt after receiving a network response. Endpoint unknown; the FK-10-recorded `sentry_client=packer/3.3.1&sentry_key=149a7ac2...` at `o566896.ingest.sentry.io` is the leading hypothesis but not measured on this trace.

- **Does the companion's WinHTTP response CONTENT govern whether it fires the kill, or is the kill decision made locally with the network call being telemetry-only?** The 2.34s gap between last thread creation and Terminate suggests blocked recv; the response payload that unblocked it is invisible here.

- **User-mode call stack at the moment TID 0x93D0 invokes `NtTerminateProcess` in the companion.** Not answerable from S177's trace — no user-mode StackWalks were captured for TID 0x93D0. The 10 StackWalks in the companion window are all kernel thread-teardown traces from unrelated processes; the one attributed to PID 0x4C50 is TID 0x628 at t+4100.5ms (post-Process.End cleanup).

- **User-mode call stack of the game code that issues `ZwCreateUserProcess` on the game side.** Not answerable — Process.Start carries emitter PID/TID (game 0x2058/0x6540, a generic thread-pool worker) but no user-mode stack. The specific CreateProcess call-site inside the game (or inside a runtime.dll routine loaded into the game) is unresolved.

- **Is the kill primitive's `[rcx+0x10]` field always the game process's handle at kill time, or does it sometimes resolve to a different handle?** Requires HW BP on 0x80F7F0 in the COMPANION process (S176 Move I targeted the game's mapping, which is now known-wrong per §2.3).

- **What is `preloader.dll`'s ONE hash-named export beyond `preloader_link_func`?** Peripheral, but relevant to understanding whether the handoff at preloader `.text 0x22bb` (`call [.data 0x5070]`) passes the preloader base pointer to runtime.dll as an argument or via a persistent handle.

---

## 4. Ranked next moves

### Tier A — Offline, decisive (do these FIRST, cost measured in minutes)

**A1. Batch-classify the FK-31 minidump corpus with the offline 4-rule predictor.**
- Experiment: run `tools/crashtri/mdctx.py` on all ~22+ FK-31 minidumps on disk (per `docs/fk31-fk32-successors.md` + `dumps/crashpad-20260820-143225` + `dumps/crashpad-20260903-142535-s168-patch`). Apply [fk31_reanalysis]'s 4-rule predictor: (1) exit `0x0000DEAD` + no dump → FK-32 companion; (2) exit `0xC0000005` + minidump + `ExceptionInformation[0]==8` + RIP==runtime.dll_base+1 → FK-31 in-process; (3) other RIPs → different bug class; (4) RIP in `MEM_PRIVATE RWX` region or on stack → SUSPECT companion-mediated FK-31.
- Discriminator: any Rule 4 match would refute the in-process attribution of FK-31 and implicate companion; expected 100% Rule 2.
- Closes: open question §3 bullet "does companion mediate FK-31?".
- Live game required? NO.
- Cost: ~30 minutes of parsing.

**A2. Enumerate the ONE call/fault-generating instruction inside each of the 16 kill-guarded packer30 ranges.**
- Experiment: disassemble each 5–45 byte range at BeginAddress RVAs `{0x13FCF43, 0x13FAE47, 0x14311EB, 0x140F684, 0x1429C2F, 0x13FEEF9, 0x1434041, 0x142C588, 0x142259F, 0x1324329, 0x133E803, 0x1346B87, 0x1322341, 0x13421BC, 0x132E211, 0x134080A}` from [kill_caller] (16th corrected per §2.5). Each range should contain a single call or memory-access instruction whose target/argument is the specific integrity check.
- Discriminator: the callee list identifies the specific packer30 check functions.
- Closes: open question §3 bullet "which specific integrity check detonates the kill?".
- Live game required? NO — on-disk runtime.dll suffices.
- Cost: ~1 hour of disassembly.

**A3. Grep the game's decrypted `.text` (`dumps/merged14.dump.exe`) and preloader.dll for cross-process handle-inheritance patterns.**
- Experiment: search for byte patterns consistent with `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` setup (`0x00020002` attribute value marker), `DuplicateHandle` call sequences, or `bInheritHandles=TRUE` argument shapes to `CreateProcessW`/`NtCreateUserProcess`. Also search for the string `runtime.dll` in the game exe or in loaded shims (it MUST be somewhere to be passed to `NtCreateUserProcess`).
- Discriminator: locating the parent-side handle-inheritance code identifies who prepared the target handle.
- Closes: open question §3 bullet "handle inherited or obfuscated-open?".
- Live game required? NO.
- Cost: ~30 minutes.

**A4. Rerun `scratchpad/s133/tools/regrade_blocked.py` and CLAUDE.md's stale-claim scan against `merged14.dump.exe` for anything that references runtime.dll's kill/ctor/vtable — the companion discovery changes what "COVERAGE-BLOCKED" means for anti-tamper code.**
- Discriminator: docs still asserting game-side runtime.dll paths need updating to distinguish game-mapping vs companion-mapping.
- Closes: instrument-artifact housekeeping.
- Cost: ~15 minutes.

**A5. Reproduce the preloader→runtime handoff call trace: fully disassemble the runtime.dll entry-point body at RVA 0x139238F onward until it consumes any of preloader's 15 `.data 0x50c0..0x50f8` pointer slots.**
- Discriminator: names the runtime.dll RVA that dereferences `.data 0x50f0` (`ZwCreateUserProcess`) — the missing call-site attribution.
- Closes: open question §3 bullet "what runtime.dll RVA issues ZwCreateUserProcess?".
- Live game required? NO — FK-10 established runtime.dll code is plaintext.
- Cost: ~2 hours; feasible offline entirely.

### Tier B — Live, single-flight, high signal

**B1. Definitive companion-non-involvement test for FK-31: one ETW-instrumented staging launch.**
- Experiment: attach the S177 ETW harness (PROC_THREAD + LOADER providers) to a normal tutorial staging attempt. Base rate is 27% per launch = one FK-31 death per ~4 staging attempts.
- Discriminator: no companion `Process/Start` event with `parent = game PID` during the FK-31 window promotes attribution to [M]; any observed spawn refutes.
- Closes: open question §3 bullet "does companion mediate FK-31?" (upgrades [fk31_reanalysis]'s central claim to [M]).
- Live game required? YES.
- Cost: 1 launch, ~2–4 attempts expected.

**B2. Live handle-table snapshot of the companion at spawn.**
- Experiment: on companion `Process.Start`, before its TID 0x93D0 has run more than a few ms, call `NtQuerySystemInformation(SystemHandleInformation)` or `handle64.exe -p 0x4C50` to enumerate the companion's handle table. If a handle to the game PID with `PROCESS_TERMINATE` access exists BEFORE the companion has had time to call `NtOpenProcess`, the handle was inherited.
- Discriminator: presence of the parent handle in the companion's initial table proves inheritance.
- Closes: open question §3 bullet "handle inherited or obfuscated-open?".
- Live game required? YES + coordinated tooling.
- Cost: 1 flight + a small harness (~1 day).

**B3. Poke the 16 kill-scope entries in the COMPANION process's packer42 mapping.**
- Experiment: capture companion on spawn (S177 already does), pause with `NtSuspendProcess`, `OpenProcess(PROCESS_VM_WRITE)`, `VirtualProtectEx` + `WriteProcessMemory` HandlerAddress=0xFFFFFFFF on each of 16 packer42 scope entries (RVAs enumerated in [kill_caller]), `FlushInstructionCache` (though this is data, not code), resume. Let the integrity check fire.
- Discriminator: if `0xDEAD` never fires, SEH-scope-dispatch is CONFIRMED as the FK-32 mechanism in the companion (upgrades [kill_caller]'s [I_strong] to [M]). If it still fires, the actual dispatch is elsewhere.
- Closes: open question — settles the S166 refutation vs [kill_caller] reinterpretation debate.
- Live game required? YES + companion-attach tooling.
- Cost: 1 flight + ~1 day tooling.

**B4. Extended ETW capture with Kernel-Audit-API-Calls + Kernel-File + Kernel-Registry providers.**
- Experiment: rerun the S177 harness with the Microsoft-Windows-Kernel-Audit-API-Calls provider (`{ed54dff8-c409-4cf6-bf83-05e1e61a09c4}`, keywords for `PsOpenProcess` (event 4) and `PsTerminateProcess` (event 3)) plus Kernel-File and Kernel-Registry providers enabled.
- Discriminator: per-call User Data includes target PID and requested access mask, DIRECTLY revealing whether companion calls `NtOpenProcess(0x2058, PROCESS_TERMINATE)` (no inheritance) or uses an inherited handle (no `NtOpenProcess` call visible). Also captures companion file/registry/pipe IPC that [companion_ipc]'s original trace was blind to.
- Discriminator #2: enables direct measurement of whether companion does any `NtWriteVirtualMemory` or `NtOpenProcess` against the game — the ETW blind spot [fk31_reanalysis] flagged.
- Closes: multiple open questions on companion behavior + companion-IPC mechanism.
- Live game required? YES.
- Cost: 1 flight.

**B5. HW BP on preloader `.data 0x50f0` (the `ZwCreateUserProcess` pointer slot).**
- Experiment: install Dr0-Dr3 break-on-read on `.data 0x50f0` in the game process BEFORE triggering DR install. When the reactive spawn fires, the DR fault handler names the exact runtime.dll RVA that dereferences the pointer.
- Discriminator: DR fault RIP = the runtime.dll RVA that issues `ZwCreateUserProcess`.
- Closes: open question §3 bullet "what runtime.dll RVA issues ZwCreateUserProcess?".
- Live game required? YES.
- Cost: 1 flight.

### Tier C — Follow-up refinement (after A/B produce results)

**C1. `usmapdump deobfimports` on the LIVE companion process.**
- Experiment: use a small harness to spawn runtime.dll as a standalone (bypassing the game trigger — or use the S177 kill-on-sight tool to snapshot companion BEFORE it fires terminate) and run FK-10's `deobfimports` (1107/1107 slots recovered elsewhere on this image family) against it to enumerate the FULL DYNAMIC import surface. This names every packer2-obfuscated API resolution.
- Discriminator: presence of `NtOpenProcess`, `NtDuplicateObject`, `NtCreateSection`, `NtMapViewOfSection`, `NtCreateNamedPipeFile` in the resolved list distinguishes IPC mechanisms.
- Closes: definitive answer on what the companion is CAPABLE of, not just what it did in one trace.
- Live game required? Companion running required; not necessarily the game.
- Cost: 1 flight + tooling.

**C2. WRITE-poke preloader `.data 0x50f0` to NULL, then trigger reactive spawn.**
- Experiment: after B5 identifies the runtime.dll consumer, WRITE-poke the slot to NULL (or to a harmless stub) BEFORE the trigger. If the reactive spawn stops, that pointer is on the critical path. If it still fires, iterate over the other 14 slots at `.data 0x50c0..0x50f8` to find the actual consumer.
- Discriminator: which of 15 slots is on the spawn path.
- Closes: precise map of the spawn's data dependencies.
- Live game required? YES.
- Cost: 1–3 flights.

**C3. Enumerate other spawn triggers via multi-flight matrix.**
- Experiment: vary trigger classes (DR install, integrity check failure, WPM to specific runtime.dll regions, `.text` patch, hardware/software breakpoint, kernel driver load) with S177 harness attached to each. Passive baseline confirmed NO spawn per S177 3-min flights.
- Discriminator: trigger→spawn latency map identifies the detection classes.
- Closes: open question §3 bullet "what triggers the companion spawn other than DR install?".
- Cost: N flights (N = number of triggers tested).

### Operational NOW: kill-on-sight of the companion is a proven working defeat for FK-32

Per CLAUDE.md S177: `TerminateProcess()` the companion within 220ms of spawn → game survives 240+s. This is not a next-move — it's the current operational defeat for FK-32. However, it does NOT close FK-31 (in-process, no companion involved). If FK-31 mortality (~27% per launch) is the current biggest blocker, address it separately via S168's understood mechanism, not via kill-on-sight.

---

## 5. Instrument defects banked

### 5.1 ETW CSV parser column-count off-by-11

Instance: [companion_ipc]'s finding-side parser stopped at column 20 of the S177 ETW CSV, missing columns [20]–[30] which include child PID, parent PID, session/token, user, ImageName, ImagePath, CommandLine, PackageFullName. The parser was calibrated on the header row (20 columns) but data rows for `Process/Start` and `Process/End` events carry an ADDITIONAL 11 fields of event-specific User Data. Verifier caught it by reading row length not header length.

**Rule:** any ETW CSV consumer must count row length dynamically, not trust the header count. Windows Kernel Process ETW schema-specific User Data is appended past the generic columns; the exact count varies by event type. Fixed action: `dumps/s177-etw-kernel.csv` parsers must be re-audited before any future analysis quotes field absences.

### 5.2 `merged*.dump.exe` does not contain runtime.dll bytes

Instance: [kill_caller] measured that `merged14.dump.exe` (55.53% of the game exe's `.text` decrypted) does NOT contain runtime.dll — game exe's section layout is 10 sections `.text/.rdata/.data/.pdata/.msvcjmc/CPADinfo/.rodata/_RDATA/.rsrc/.reloc`; runtime.dll's is 11 sections with the distinctive `packer0/packer1/packer2/packer30/packer40/packer31/packer42` names. `merged14` is game-only, always was.

**Rule:** analyses of runtime.dll must use the on-disk file at `G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Binaries\Win64\runtime.dll` (67,511,496 B, plaintext code per FK-10) OR live captures via S164's `dumpimage -includehiddenimages` patch. `merged*` is off-limits for runtime.dll questions. Section-name signature is diagnostic — check before assuming what an image contains.

### 5.3 Trigger→spawn latency vs game-start→spawn latency confusion

Instance: [fk31_reanalysis]'s timing argument used "~50s companion latency" from S177 flight 7's game-start-to-companion-start figure to argue timing incompatibility with FK-31's ~10s post-fo firing. Verifier caught: S177 flight 9 explicitly records trigger-to-spawn latency at ~5s after fresh DR install, not 50s. The 50s figure was for a spontaneous spawn, not a triggered one.

**Rule:** when discussing companion spawn latency for defeat/analysis, always distinguish (a) game-start-to-companion-spawn (varies widely by trigger absence), (b) trigger-to-spawn (~5s, operationally relevant), (c) companion-start-to-companion-terminate (4.09s, invariant). Cite which. Grade any argument that quotes only one figure as [I], not [I_strong].

### 5.4 ETW provider selection determines question answerability

Instance: [companion_ipc] Fact #5 claimed "no WPM behavior observed" as [I_strong] evidence of companion incapability, but the S177 trace used PROC_THREAD + LOADER providers only — blind by design to VirtualAlloc/VirtualProtect/WriteProcessMemory/NtWriteVirtualMemory/SetThreadContext. Absence-of-events under an ETW provider not enabled for those event classes is not evidence-of-absence.

**Rule:** every ETW-based negative claim must state which providers were enabled and whether the claimed-absent event class is capturable by that provider set. Classic instrument-blind-spot pattern per CLAUDE.md method-rules §1. Fixed action: an ETW capture explicitly listing enabled providers should accompany every claim of the form "no X events for PID Y observed."

### 5.5 Fold-detection classifier misses `__security_check_cookie` idiom

Instance: [kill_caller]'s per-image fold classifier (byte-scan for `E8`/`E9`/`C3` opcodes) worked for the on-disk runtime.dll but the finding notes a general classifier defect in scoring UFunctions (see also CLAUDE.md's S153 v1 → v2 fix). Any classifier picking "last E8 call before ret" as the tail-fold target must ignore MSVC's `__security_check_cookie` wrapper.

**Rule:** UFunction/fold classifiers must specifically ignore `__security_check_cookie` (and other MSVC-inserted epilogue helpers) when picking `last_call` for fold detection. `IGNORED_TAIL_TARGETS = {0x751DEB0}` in `scratchpad/s153_native_ufunction_sweep.py` per CLAUDE.md. This applies to any similar classifier applied to runtime.dll's protector code.

### 5.6 Instruction-walker window size for tail-jmp detection

Instance: [kill_caller] notes that `OverridePlaneLocations`'s tail call sits at wrapper+0xD8 (S153 caveats); a 128-byte scan window misclassifies it. Applies equally to runtime.dll analysis: any scan looking for tail-jmps into fold targets must extend the scan window to ≥0x400 (1 KiB).

**Rule:** minimum instruction-walker scan window for tail-fold detection is 1 KiB, and must distinguish internal control-flow branches from genuine tail-jmps (target outside wrapper byte range).

### 5.7 SCOPE_TABLE record count is boundary-sensitive

Instance: [kill_caller] finding reported 44,465 well-formed SCOPE records at packer42 alignment 12; verifier measured 44,464 (0.002% difference, single-record boundary). Rule not new — CLAUDE.md's tabulated-register rules already say to re-derive counts rather than retype them — but reinforces that any density scan over a section with a header/footer must report boundary-edge behavior.

**Rule:** density-scan tools should report count ± 1 (or state assumption about first/last valid record) when scanning near a section boundary. Cite the alignment offset AND the boundary policy.

### 5.8 Static `deobfimports` cannot see per-launch runtime patches

Instance: [companion_ipc] and [spawn_caller] both note that runtime.dll's 17-function static import table is a decoy and the real APIs resolve via packer2's XOR-obfuscated syscall stubs (S169 measured the runtime XOR-key patch at packer2 RVA 0x94A803 changes byte 0x10 → 0xAA per boot to activate syscall# 0x2C = NtTerminateProcess). Static offline analysis of runtime.dll CANNOT enumerate the dynamically-resolved API list without emulating the packer2 stubs — this is exactly what FK-10's `deobfimports` tool does, but it needs a LIVE runtime.dll process (game or companion) to run against.

**Rule:** any claim of the form "runtime.dll cannot call API X" based on static import analysis must explicitly qualify "…via a statically-imported name; dynamically-resolved via packer2 syscall stub is not excluded." Move [companion_ipc]-style enumeration to a live `deobfimports` run against the companion when tooling exists.

### 5.9 Sentry crashpad vs UECC minidump discrimination

Instance: [fk31_reanalysis]'s 4-rule offline predictor works only if the parser handles both Sentry crashpad minidumps (in `<GameRoot>\Loki\.sentry-native\`, 43.8 MB, contain full memory + module list including runtime.dll) AND UECC minidumps (in `Saved\Crashes\UECC-*`, contain `.rdata` only, 13,824 B of `.text` across 98 dumps). CLAUDE.md already documents this trap but any FK-31 corpus classification must apply it.

**Rule:** any minidump-corpus census must enumerate BOTH minidump families and record which family each dump came from; ExceptionRecord + ModuleList are only reliable from Sentry crashpad, not UECC.

### 5.10 Instrument-artifact self-check for tallied counts

Instance: multiple findings (see [fk31_reanalysis] verifier notes on downgrades, CLAUDE.md's tabulated-register method-rules §1 pattern) illustrate that a tally quoted in prose without periodic re-derivation drifts. Applies here: whenever an S177-lineage doc cites "16 kill-scope entries", "44,465 SCOPE records", "5-second trigger-to-spawn latency", or "17 imports from 6 DLLs", re-derive the number against the current artifacts.

**Rule:** every load-bearing count in any published finding on this topic must carry the artifact hash or file mtime it was measured against; a stale count against a superseded artifact reads as fact and produces cascade errors. Enforce with tool-embedded re-derivation commands (as CLAUDE.md's method-rules already do for the instrument-artifact register itself).

---

*Every claim above cites specific evidence in the six source analyses; where multiple analyses converge the strongest evidence chain is quoted. Cross-refs to CLAUDE.md's FK-10, S131, S132, S162, S166, S168, S169, S177 blocks preserve the S177 discovery's continuity with prior offline evidence.*