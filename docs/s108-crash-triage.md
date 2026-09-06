# S108 — triage of the S107 crash `UECC-Windows-166396E24F5A36C5727032B196D739EA_0000`

**Date:** 2026-08-04 · **Scope:** offline only (no game touched, no injection, no live process).
**Tools:** `tools/crashtri/{mdctx,ptrhunt,harvest}.py`, `tools/strxref/{strxref,vtables}.py`,
`tools/strxref/index/pdata_union.csv`, `dumps/merged.dump.exe`, `docs/symbols.csv`, capstone 5.x.

Every claim below is tagged **MEASURED** (read out of a dump / binary / log / source) or
**INFERRED**. Every negative carries the instrument's blind spot next to it. Positive controls are
run and shown before any absence is believed.

---

## ★ HEADLINE — read this before anything else

**This crash is the FK-24 watchpoint probe killing the process with its own hardware breakpoint.
It is an INSTRUMENT ARTIFACT, not a game bug, and not FK-7.**

The faulting PC is **inside our own manually-mapped shim image**, and the instruction that raised the
exception is, byte for byte, `WpSelfTestTick()` phase 0's *idempotent 8-byte store* —
`tools/sigbypass-mod/tutorial_launch.cpp:1567–1578`. The exception is `STATUS_SINGLE_STEP`
(`0x80000004`), Dr6 reports **B0+B1**, Dr0/Dr1 hold **exactly** `&ViewTarget.Target` and `+1`, and Dr7
is **exactly** the probe's own `g_wpDr7Val = 0x00110005` (plus the architectural always-set bit 10).
Nothing in the game wrote anything wrong. The probe wrote back the value it had just read, its own
watchpoint trapped, and **no exception handler claimed the trap**, so it propagated to
`LaunchWindowsStartup`'s `__except` and became a crash report.

Three second-order consequences, all of them load-bearing for S108:

1. **The S107 verdict "the watchpoint is VOID on the game thread" is FALSIFIED.** 127 of the 128
   thread contexts in this dump carry the probe's watchpoint, *including the GameThread*, and the
   GameThread's DR **did** fire. The DR path is not defeated by the packer. What failed was the
   probe's **selftest liveness window** (8 s), not the watchpoint. **The `wprobe → wprobe2` escalation
   in `next-session-prompt-s108.md` §1 rests on a premise this dump contradicts.**
2. **The probe's failure mode is fatal, not silent.** A trap that `WpHandle` declines kills the
   process. Any future `wprobe` launch must fix that before it is run again (§7).
3. **The prompt's own 15-RVA frame list is a truncated tail.** The real chain is **23** game frames;
   the 8 innermost were missing, and they are the entire diagnosis (§1, §3).

---

## 0. What the prompt said vs. what the dump says

| prompt (S107 first look) | this triage | status |
|---|---|---|
| `RVAs: 35aa803 … 751ef62` (15) | the game chain is **23** frames; `feca12 1225fd6 13453a5 341721b 36a1aa3 36a1bdc 36a412b 36a339a` precede them (MEASURED, `CrashContext.runtime-xml` `<PCallStack>`) | **CORRECTED** |
| "shares only the tail frame `37f8b8c` with the GameThread family" | shares **7** frames with both camera sub-families — but all 7 are the generic engine-boot tail present in **40+** of the 87 dumps, so they carry ~zero discriminating power (MEASURED) | **CORRECTED, and the corrected version is still not family evidence** |
| "nothing with the worker family" | confirmed: **0** frames shared with the 4 ANIM/worker dumps (MEASURED) | **CONFIRMED** |
| "`3c5dc52` and `3c5d255` ABSENT ⇒ the FK-7 camera signature did not recur" | confirmed absent (MEASURED) — but see §5: absence here proves nothing about the guard | **CONFIRMED (fact), MISLEADING (inference)** |
| "~90 s after the probe's init completed" | the shim's one-time post-body-build block ran at **T+2529 s** and the crash is at **T+2550 s** ⇒ **≈11–21 s** after it. The ~90 s figure matches the *injection* (gft marker rewritten 22:47:37, crash 22:49:20 ≈ 103 s) not the init (MEASURED) | **CORRECTED** |
| "first crash on the fixed build" | true, and the build also carries **`KWPROBE=1`** — an extra, un-named variable that turns out to be the cause | **INCOMPLETE** |

**The truncation is itself the instrument-artifact pattern.** `harvest.py` records the *full* chain in
`crash_census.csv`; the 15-RVA list in the prompt dropped the 8 frames nearest the fault. Had the
triage been run against that list alone, the ProcessEvent / skeletal-mesh-tick context — the only
frames that identify anything — would never have appeared.

---

## 1. Named frames

Base `0x7FF6EAA10000`; SUPERVIVE image size `0xA9E1000` (MEASURED, minidump module list).
Frame 0 = innermost. Frames are **return addresses** except frame 0 (the trap RIP).
`.pdata` extents are EXACT and come from the 70-minidump union (`pdata_union.csv`, 382,282 functions)
— independent of `.text` decryption.

**Positive control for the resolver, run first:** `0x3C5DC52` → entry `0x3C5DC45`, extent
`0x3C5DC45..0x3C5DC60` (27 B), `slotof 0x3C5DBC0` → *slot 312 of `0x07EC5B88 APlayerCameraManager`* —
reproduces `docs/fk24-writer-probe.md` §6 verbatim. **Every tool used below is therefore known-good on
this corpus.**

**Decryption blind spot, stated up front and then measured away:** `.text` is only 52.29 % decrypted in
`merged.dump.exe`, so ~47.7 % of arbitrary RVAs land in an all-zero page. **For this dump that
blind spot did not bite: all 23 game frames' pages are decrypted** (3,657–3,906 non-zero bytes per
4,096-byte page, MEASURED). Not one frame is unresolvable for decryption reasons.

### 1.1 Frames 0–2 — INSIDE OUR OWN SHIM (this is the crash)

The minidump has **`MZ` at `0x1A4A4690000`** (MEASURED) — a manually-mapped PE with no LDR entry, which
is why UE's symboliser mislabels these frames `mdnsNSP` (it picks the nearest preceding *registered*
module base and then prints the absolute address as the "offset"; the printed `0x6D910000 + 1a436d8c1a3`
is a formatting artifact, not an address).

| # | absolute | shim RVA | identity | confidence |
|---|---|---|---|---|
| 0 | `0x1A4A469C1A3` | `shim+0xC1A3` | **trap RIP.** The instruction *ending* at it is `shim+0xC1A0: 4C 89 33  mov qword ptr [rbx], r14` = `WpSelfTestTick` phase 0's `*(volatile uintptr_t*)slot = v` | **CERTAIN** |
| 1 | `0x1A4A4695F41` | `shim+0x5F41` | `WpSelfTestTick`'s caller — `VtGuard()` (`tutorial_launch.cpp:1596`, "Runs on the GAME THREAD, once per hook hit, ahead of the camera tick") | HIGH (position + the only caller in source) |
| 2 | `0x1A4A4691076` | `shim+0x1076` | `VtGuard`'s caller — the `ProcessInternal` hook body | MED-HIGH |

**Why frame 0 is certain — five independent agreements, all MEASURED:**

```
shim+0xC195  B8 01 00 00 00        mov  eax, 1
shim+0xC19A  87 05 CC 33 03 00     xchg dword ptr [shim+0xF56C], eax      ; g_wpSelfStore = 1
shim+0xC1A0  4C 89 33              mov  qword ptr [rbx], r14              ; *slot = v   <-- #DB fires here
shim+0xC1A3  31 C0                 xor  eax, eax                          ; <-- RIP
shim+0xC1A5  87 05 C1 33 03 00     xchg dword ptr [shim+0xF56C], eax      ; g_wpSelfStore = 0
shim+0xC1AB  B8 01 00 00 00        mov  eax, 1
shim+0xC1B0  87 05 B2 33 03 00     xchg dword ptr [shim+0xF568], eax      ; g_wpSelfPhase = 1
shim+0xC1B6  E9 DD F8 FF FF        jmp  ...
```

1. The two `xchg` sites resolve to the **same** address `shim+0xF56C` (`0xC1A0+0x333CC` and
   `0xC1AB+0x333C1`) — i.e. one variable set to 1 immediately before the store and 0 immediately
   after. That is `InterlockedExchange(&g_wpSelfStore,1) … InterlockedExchange(&g_wpSelfStore,0)`
   bracketing `*(volatile uintptr_t*)slot = v`, line for line.
2. The next `xchg` targets `shim+0xF568` — `g_wpSelfPhase = 1`, the very next source statement.
3. `rbx == 0x1A47A192F00 == Dr0` (the watched address) — the store is *to the watchpoint*.
4. `r14 == 0x1A48D01D560`, and `[watched] == r14` in the dump — the store is **idempotent**, exactly as
   the source comment promises ("Both stores write back the value they just read").
5. The code immediately above frame 0 is `VtValid()`: `VirtualQuery(rcx, buf, 0x30)` → test
   `MBI.State & MEM_COMMIT` (`byte[rsp+0x71] & 0x10`) → test `MBI.Protect & (PAGE_NOACCESS|PAGE_GUARD)`
   (`word[rsp+0x74] & 0x101`) → `test r14b,7` (alignment) → `mov rax,[r14]; sub rax,[module base];
   cmp rax,0xB000001` (is the vtable inside the 0xA9E1000-byte game image). That is `VtValid` /
   `SafeReadable`, not engine code.

`r14` is a genuine live `UObject`: `[r14+0x00]` = vtable `SUPERVIVE+0x89A6DA0`, `[r14+0x10]` =
InternalIndex `0x15164`, `[r14+0x18]` = UClass `0x1A409406A60` (== `rbp`/`r9`), `[r14+0x28]` = Outer —
the exact `vtable@0x00 / InternalIndex@0x10 / UClass*@0x18 / FName@0x20 / Outer@0x28` layout `deadobj.py`
documents for this build. **Nothing was corrupt.**

### 1.2 Frames 3–7 — STACK-WALKER ARTIFACT, not a call chain

| # | absolute | why it is junk |
|---|---|---|
| 3 | `0x7FF6EA9D0036` | `0x3FFCA` **below** the game base — a private allocation, not the module |
| 4 | `0x1A4807DB440` | heap |
| 5 | `0x1A4915324A0` | heap |
| 6 | `0x2D5F9DE960` | **on the GameThread's own stack** (`rsp = 0x2D5F9DE4D0`) — a stack address cannot be a return address |
| 7 | `SUPERVIVE+0xFECA12` | a *real* return address (the instruction after `call 0xFAB490` in the 43-byte scalar-deleting destructor at `0xFEC9F0`, `.pdata` EXACT) but it cannot lie between a UFunction thunk and our hook — a **stale** value the scanner picked up |

**Cause (INFERRED, but forced):** the manually-mapped shim has no registered `RUNTIME_FUNCTION` table,
so `RtlLookupFunctionEntry` returns nothing for frames 0–2, UE's walker falls back to scanning the
stack, and emits whatever looks like a return address until it re-synchronises. It re-synchronises at
frame 8. **Do not read frames 3–7 as a call path in any future triage of a shim-side fault.**

### 1.3 Frames 8–30 — the genuine UE call path (this is where the hook was entered)

| # | RVA | `.pdata` extent (EXACT) | name | evidence | conf. |
|---|---|---|---|---|---|
| 8 | `0x1225FD6` | `0x1225FB8..0x1225FF6` (62 B) — a **chained fragment** of the function entered at `0x1225F30` | **`UFunction::Invoke` / `ProcessLocalScriptFunction`** — it *is* the `call qword ptr [r14+0xE0]` site, i.e. `UFunction.Func @ +0xE0`, the project's own documented native-thunk offset | disassembled: `mov [rsi+0x90],r14; mov rcx,rbp; mov rdx,rsi; mov r8,r12; call [r14+0xE0]` | **HIGH** |
| 9 | `0x13453A5` | `0x1344E10..0x1345491` (1665 B) | **`UObject::ProcessEvent`** | (a) immediately precedes the *known* `ProcessInternal` at `0x13454A0` (`symbols.csv`, ENTRY-OK) with only padding between; (b) `vtables.py slotof` → **slot 78 of 3,651 vtables**, i.e. a UObject-level virtual almost nothing overrides; (c) it directly calls `0x1225F30`, the thunk-dispatch above | **HIGH** |
| 10 | `0x341721B` | `0x341704B..0x3417313` (712 B) | the **direct caller of the `ProcessEvent` virtual** on the anim path (a Blueprint/anim-notify event dispatch). Name not recovered | it calls `ProcessEvent` *indirectly* (virtual), and calls `0x32BB650` which touches `UEngine`/`/Script/Engine`/`Engine` | role HIGH, **name LOW** |
| 11 | `0x36A1AA3` | `0x36A1A00..0x36A1B47` (327 B) | skeletal-mesh anim dispatch helper (unnamed) | calls the `Cast<>` type-check `0x2D971C0` (`Mismatch NumStructBasesInChainMinusOne: …`, i.e. `FStructBaseChain`) | role MED |
| 12 | `0x36A1BDC` | `0x36A1B50..0x36A1C27` (215 B) | ditto; calls frame 11 | same Cast helper | role MED |
| 13 | `0x36A412B` | `0x36A3F30..0x36A419D` (621 B) | **`USkeletalMeshComponent::TickComponent`** | `vtables.py slotof` → **slot 353 of `0x07FF3C88 USkeletalMeshComponent`**; touches the anim-tick literal `'%d Ticked %d NotTicked'` (via ptr-table `0x07FF9750`, an *indirect* reference — weaker than a `lea`) | class **HIGH**, method MED-HIGH |
| 14 | `0x36A339A` | `0x36A3388..0x36A33B8` (48 B) | the `ExecuteTickHelper<…>` lambda that invokes `TickComponent` | 48 B, non-virtual, in the SkeletalMeshComponent TU, sole callee = frame 13 | MED-HIGH |
| 15 | `0x35AA803` | `0x35AA752..0x35AA808` (182 B) | **`FActorComponentTickFunction::ExecuteTick`** | called directly by `FTickFunctionTask::DoTask` (frame 16, named by string); calls frame 14 | MED-HIGH |
| 16 | `0x3ED1A7F` | `0x3ED19DC..0x3ED1B48` (364 B) | **`FTickFunctionTask::DoTask`** | `lea` → `U'FTickFunctionTask'` at `+0x11F` **and** `U'LIGHTWEIGHT_TIME_GUARD: %s - %s took %.2fms!'` at `+0x12F` — the exact pair emitted by `LIGHTWEIGHT_TIME_GUARD_BEGIN/END(FTickFunctionTask,…)` around `Target->ExecuteTick()` | **CERTAIN** |
| 17 | `0x3ED8642` | `0x3ED8610..0x3ED8736` (294 B) | **`TGraphTask<FTickFunctionTask>::ExecuteTask`** | slot **1** of vtable `0x082426F8`, which sits 0x28 bytes after the `'FTickFunctionTask'` literal at `0x082426D0`; sole relevant callee = frame 16 | HIGH |
| 18 | `0xF96A8E` | `0xF96980..0xF96ADB` (347 B) | task-graph task execution (`FBaseGraphTask::Execute` family) | slot 6 of task-graph vtable `0x07689288` | MED |
| 19 | `0xF9CE6A` | `0xF9CC50..0xF9D039` (1001 B) | **`FTaskGraphImplementation` / `FNamedTaskThread` named-thread pump** | touches `U'Recursive waits are not allowed in single threaded mode.'` (TaskGraph.cpp); slot 12 of vtable `0x07689640` | HIGH |
| 20 | `0x3EEEDD4` | `0x3EEED7B..0x3EEEEC7` (332 B) | tick-group dispatch / `FTickTaskSequencer::ReleaseTickGroup` | position between `UGameEngine::Tick` and the task graph | MED |
| 21 | `0x3EF3E65` | `0x3EF3E40..0x3EF3E71` (49 B) | 49-byte virtual thunk, slot 5 of vtable `0x08242B10` (same `.rdata` neighbourhood as `FTickFunctionTask`) | — | LOW |
| 22 | `0x39C76C6` | `0x39C6E70..0x39C7D21` (3761 B) | **`UGameEngine::Tick`** | `lea` → `U'ConnectionFailed'`, `U'Your connection to the host has been lost.'`, `U'TickInGamePerfTrackersRT'`, `U'Media'` — all `UGameEngine::Tick` | **CERTAIN** |
| 23 | `0x37F8B8C` | `0x37F89C8..0x37F9152` (1930 B) | **`FEngineLoop::Tick`** | `lea` → `U'causeevent='`, `A'CAUSEEVENT '`, `U'Issuing initial cause event passed from URL: %s'`, `U'SubmitAndBlockUntilGPUIdle_MinimizedRealtime'` | **CERTAIN** |
| 24 | `0x4028924` | `0x402887B..0x40289E7` (364 B) | `EngineTick()` wrapper (no literals of its own — a genuine leaf-of-strings, not a decryption gap: page has 3,738 non-zero bytes) | position | MED |
| 25 | `0x403005F` | `0x402FD90..0x40300B9` (809 B) | **`GuardedMain`** | `lea` → `U'Starting'`, `A'DefaultMain'`, `U'unreal-v%i-%s.dmp'`, `U'Initializing'` | HIGH |
| 26 | `0x40300DA` | `0x40300C0..0x40300F4` (52 B) | `GuardedMainWrapper` | 52-byte pass-through calling frame 25 | MED-HIGH |
| 27 | `0x4030F6C` | `0x4030E50..0x4030FD2` (386 B) | **`LaunchWindowsStartup`** | `lea` → `U'unattended'`, `U'messagebox'`, `A'waiting'`, `U'crashreports'` — the `-unattended` / `-messagebox` / `-waitforattach` / `crashreports` parse block in Launch.cpp | **HIGH — and this is the family discriminator, see §2.3** |
| 28 | `0x4039696` | `0x4039680..0x4039755` (213 B) | `WinMain` / launch shutdown wrapper | touches `U'Exiting.'` | MED-HIGH |
| 29 | `0x751EF62` | `0x751EE5C..0x751EFCD` (369 B) | statically-linked CRT entry (`__scrt_common_main_seh`) | called directly by `KERNEL32!BaseThreadInitThunk` | HIGH |
| 30 | `KERNEL32+0x17374` | — | `BaseThreadInitThunk` | module list | CERTAIN |

**Frames with no name, and WHY (never left blank):** frames 10, 11, 12, 18, 20, 21, 24 have EXACT
`.pdata` extents and **fully decrypted** pages, appear in **no** vtable or in an unnamed one, and have
**zero string literals in range**. That is the documented `strxref` failure mode for *leaf / literal-free
functions*, not a coverage gap — `strxref.py` itself prints "either the function touches no literals, or
its body is in a non-decrypted page", and the page census settles which. Naming them needs a caller-side
xref sweep or UE source matching, not a better dump.

### 1.4 What the chain means

Reading outermost → innermost, the game was doing exactly this:

```
BaseThreadInitThunk → CRT → WinMain → LaunchWindowsStartup → GuardedMainWrapper → GuardedMain
  → EngineTick → FEngineLoop::Tick → UGameEngine::Tick → [tick-group release] → task graph
  → TGraphTask<FTickFunctionTask>::ExecuteTask → FTickFunctionTask::DoTask
  → FActorComponentTickFunction::ExecuteTick → ExecuteTickHelper
  → USkeletalMeshComponent::TickComponent → [anim dispatch ×3]
  → UObject::ProcessEvent → call [UFunction+0xE0]   ← this is ProcessInternal for a script UFunction
  → OUR ProcessInternal HOOK → VtGuard → WpSelfTestTick → *slot = v   ← #DB
```

That is the shim's own documented entry path: the PI hook fires on a script call made during the
skeletal-mesh tick, `VtGuard` runs "once per hook hit, ahead of the camera tick", and the pending
selftest finally found `VtValid(v) == true` and issued its store.

---

## 2. The exception itself

### 2.1 Exception record (MEASURED, `mdctx.py` + raw stream 6)

| field | value |
|---|---|
| `ExceptionCode` | **`0x80000004` = `STATUS_SINGLE_STEP`** (not an access violation) |
| `ExceptionAddress` | `0x1A4A469C1A3` = **shim+0xC1A3**, *not* in any registered module |
| `NumberParameters` | **0** — single-step carries no access-type/address operands, so "access type" and "faulting address" do not exist for this exception |
| `ThreadId` | **23640** |
| `<ErrorMessage>` | `Unhandled Exception: 0x80000004` — **the only one of 87 dumps with this code** (histogram: 62 × `EXCEPTION_ACCESS_VIOLATION`, 24 × `Fatal error:`, 1 × `0x80000004`) |
| `SecondsSinceStart` | **2550** |
| `ProcessId` | **38832** — matches `docs/fk24-stage-run2.log` (`[stage] game PID=38832`) |

### 2.2 Full `CONTEXT_AMD64` of the faulting thread

```
ContextFlags = 0x0010005F   (CONTEXT_AMD64 | CONTROL|INTEGER|SEGMENTS|FLOATING_POINT|DEBUG_REGISTERS)
rax = 0x0000000000000000     rcx = 0x000001A48D020000     rdx = 0x0000000000000000
rbx = 0x000001A47A192F00  <-- == Dr0, the watched &ViewTarget.Target
rsp = 0x0000002D5F9DE4D0     rbp = 0x000001A409406A60  <-- == [r14+0x18], the UClass
rsi = 0x0000000000000000     rdi = 0x000001A4D3B5D8A0
r8  = 0x0000002D5F9DE488     r9  = 0x000001A409406A60
r10 = 0x0000000000000000     r11 = 0x0000000000000246
r12 = 0x000001A47A192F08  <-- watched+8 (the POV that follows Target in FTViewTarget)
r13 = 0x0000FFFFFFFEFFFF     r14 = 0x000001A48D01D560  <-- the live UObject being stored back
r15 = 0x0000FFFFFFFF0000     rip = 0x000001A4A469C1A3
EFlags = 0x00000206   -> TF(bit 8) = 0, IF = 1, RF = 0
MxCsr  = 0x00001FBF   SegCs = 0x0033  SegSs = 0x002B
xmm1.f32 = 0.0        xmm6.f32 = 0.0
Dr0 = 0x000001A47A192F00     Dr1 = 0x000001A47A192F01
Dr2 = 0                      Dr3 = 0
Dr6 = 0x00000000FFFF0FF3     Dr7 = 0x0000000000110405
```

**Debug-register decode (MEASURED):**
- `Dr6` low nibble `0x3` ⇒ **B0 = 1 and B1 = 1** — both breakpoints hit. `BS` (bit 14) = **0** and
  `EFlags.TF` = **0** ⇒ this is a *data* breakpoint trap, **not** a trap-flag single-step.
- `Dr7 = 0x110405`: `L0 = L1 = 1`; `R/W0 = R/W1 = 01` (**write-only**); `LEN0 = LEN1 = 00` (**1 byte**).
  Strip the architecturally-always-set bit 10 and you get **`0x110005` — literally
  `g_wpDr7Val = 0x00110005ULL` from `tutorial_launch.cpp:576`.**
- `Dr0/Dr1` = `g_wpAddr` and `g_wpAddr+1`, matching `ctx.Dr0 = g_wpAddr; ctx.Dr1 = g_wpAddr+1;`
  (`:1743`).
- **B0+B1 together = a store WIDER than one byte** — the probe's own discriminator (`:1583`, "8-byte
  store → expect B0|B1; 1-byte store → expect B0 only"). It read out correctly. The instrument's
  discriminator works; it was simply never harvested because the run died.

### 2.3 Which thread — and which discriminator was actually usable

**GameThread**, tid 23640. Three independent MEASURED confirmations:

1. Minidump stream 24 (ThreadNames) maps tid 23640 → `"GameThread"`.
2. `CrashContext.runtime-xml` `<Thread><ThreadName>GameThread</ThreadName><IsCrashed>true</IsCrashed>`.
3. **The structural form of FK-7's own discriminator:** the outermost SEH frame in the chain is
   `LaunchWindowsStartup` (frame 27, named by its `'unattended' / 'messagebox' / 'crashreports'`
   literals) — i.e. `LaunchWindowsStartup.ExceptionHandler`, which `fk7-crash-settled.md` §0.2 defines
   as the **game-thread** side. There is no `FRunnableThreadWin::GuardedRun` anywhere in the chain.

> ### ⚠ The log-based discriminator is UNAVAILABLE, and that is a property of the instrument
>
> `fk7-crash-settled.md` §0.2 offers the `RequestExit` reason string as a "zero-cost discriminator".
> **It does not exist in the `Loki.log` bundled inside a crash folder.**
>
> **Positive control, run before believing the absence** — case-insensitive grep for `RequestExit`,
> `GuardedRun`, `LaunchWindowsStartup` over the crash-folder `Loki.log` of five dumps:
>
> | dump | family | `RequestExit` | `GuardedRun` | `LaunchWindowsStartup` |
> |---|---|---|---|---|
> | `7E6FDF97` | CAMERA (FK-7's own 2/2 evidence) | 0 | 0 | 0 |
> | `BE345EC2` | CAMERA | 0 | 0 | 0 |
> | `B61ED1A7` | CAMERA | 0 | 0 | 0 |
> | `FF9CF623` | ANIM/worker | 0 | 0 | 0 |
> | `166396E2` | this one | 0 | 0 | 0 |
>
> **0/5 including two known-CAMERA dumps ⇒ the file cannot carry the signal at all.** The crash-folder
> `Loki.log` is snapshotted at the instant of the fault, *before* `RequestExit` is logged; the string
> must have been read from the live session log, not the bundled copy. **The 0 hits here are a
> statement about the file, not about the crash.** Blind spot fully stated: grep was
> case-insensitive, exact-token, whole-file, on the *bundled* copy only.
>
> The **screenshot-count** discriminator is likewise unusable: `Saved/Screenshots/WindowsClient` holds
> nothing newer than **2026-07-26 04:14**, and a repo-wide `find Saved -name '*.png' -newermt 2026-08-01`
> returns **zero files**. So this run wrote 0 PNGs — but `KSHOT` defaults to `1`, so 0 PNGs here is an
> unexplained discrepancy (see §7 open items), not the "0 PNGs ⇒ CAMERA at +0.15 s" mapping, which was
> calibrated on a different artifact vintage and a different clock.

### 2.4 Why the trap was not claimed — NOT ESTABLISHED, and I will not guess

`WpHandle` (`tutorial_launch.cpp:674`) would have claimed this trap: `code == STATUS_SINGLE_STEP` ✔,
`ContextFlags & CONTEXT_DEBUG_REGISTERS` present ✔ (`0x10` is set), `Dr6 & (bit0|bit1) != 0` ✔,
`EFlags.TF == 0` so the TF-decline path is not taken ✔. The **only** remaining gate is
`g_wpArmed != 0`, and `WpSelfTestTick` itself checks that gate at entry two instructions earlier
(`:1569`).

`CrashVEH` is registered with `AddVectoredExceptionHandler(1, CrashVEH)` at `:6033`.

Candidate explanations, none confirmed:

- **(a) Two shim images, split ownership.** `docs/fk24-stage-run2.log` records four manual maps at
  bases `0x1A478360000 / 0x1A478BE0000 / 0x1A47F120000 / 0x1A4838A0000`. **The crashing image's base is
  `0x1A4A4690000`** (MZ verified) — *none of those four*, and higher than all of them ⇒ a **later,
  unlogged injection**, consistent with `docs/gft-ready-marker.txt` being rewritten at 22:47:37, ~93 s
  before the crash. So **≥2 `tutorial_launch_play_wprobe*` images were resident**, each with its own
  `g_wpArmed`, its own `CrashVEH`, and both arming the *same* `Dr0`. A hardware/flag ownership split
  between them is the cleanest fit.
- **(b) `WpDisarm` partially ran.** Argues against: `WpDisarm` clears hardware *first*, yet **127 of 128
  threads are still armed** (§2.5) — so no disarm completed for whichever image owns the hardware.
- **(c) The packer displaced or unregistered our VEH.** Untestable from this dump: the VEH chain lives
  in ntdll data and the dump carries only 6.88 MB of register-directed memory.

**What would distinguish them:** the probe's own `[WP] census … traps=… self=…` and `[WP] cfg` lines —
which went to `docs/tutorial-launch-marker.txt` and were **destroyed**. That file's mtime is
**2026-08-04 01:45:05**, ~3 h *after* the crash, and its contents are from a different process
(`gameTid=14944`, a different module base). `Marker()` opens `CREATE_ALWAYS` (`:4919`), so every later
injection truncates it. **This is a live, S107-dated instance of FK-25** — the run's own instrument
record was overwritten by the next injection, and it is the single missing measurement in this triage.

### 2.5 The watchpoint was armed process-wide — and the GameThread's DR *did* fire

Across **all 128** thread contexts in the dump (MEASURED; **0** contexts lacked
`CONTEXT_DEBUG_REGISTERS`, so this census has no blind spot):

| Dr7 | threads | meaning |
|---|---:|---|
| `0x110005` | 100 | the probe's value exactly as `SetThreadContext` wrote it |
| `0x110405` | 27 | the same, as the CPU reports it (bit 10 always set) |
| `0` | **1** | one unarmed thread |

**127 / 128 threads carry `Dr0 = 0x1A47A192F00`, `Dr1 = 0x1A47A192F01`** — including `GameThread`,
`RenderThread 0`, `RHIThread`, `FAsyncLoadingThread`, all `Background Worker #n`, `HttpManagerThread`,
`FAsyncPurge`, and the Chromium/CEF pool. Twenty-seven threads additionally show `Dr6 = 0xFFFF0FF0`
(cleared low nibble — they have run with the DRs loaded).

⇒ **RETRACTION of the S107 reading.** `[WP] selftest *** FAIL: no trap 8000 ms after arming
(selfPhase=0) -- the watchpoint is VOID on the game thread ***` measured **the selftest's 8-second
liveness window**, not the watchpoint. The watchpoint was live, on the game thread, and fired. The
correct reading of `selfPhase = 0` at +8 s is *"`VtGuard` had not yet re-entered with a `VtValid`
slot"* — which is precisely the alternative the source itself names at `:2071`
(*"vtHits … 0 => VtGuard never re-entered after arming (raise KWPSELFWAITMS…)"*). The escalation rule
in `fk7-crash-settled.md` §0.6 / `next-session-prompt-s108.md` §1 says escalate to `wprobe2` **on a
VOID verdict**; this dump shows the verdict was **not** VOID. `KWPSELFWAITMS` is already 90,000 ms in
source (`:494`), so the 8,000 ms figure in the S107 log came from an older build or a different
constant — worth checking before the next run.

---

## 3. Family classification

### 3.1 Verdict: **a NEW family — and it is not a game-side crash at all**

| criterion | this dump | Family A (ANIM/worker) | Family B (CAMERA/game-thread) |
|---|---|---|---|
| exception code | **`0x80000004` STATUS_SINGLE_STEP** (1 of 87) | `0xC0000005` | `0xC0000005` |
| faulting PC | **outside every module** (our shim, MZ @ `0x1A4A4690000`) | in-module | in-module |
| thread | GameThread | worker | GameThread |
| `3c5dc52` / `3c5d255` / `12c7e2d` | absent | absent | present |
| `3495973 3405f13 3691a72` | absent | present | absent |
| shared frames | 7 (generic boot tail) | **0** | 7 (generic boot tail) |
| `SecondsSinceStart` | 2550 | 194–201 | 173–194 |

### 3.2 The 7 "shared" frames are not evidence — measured, not asserted

`37f8b8c 4028924 403005f 40300da 4030f6c 4039696 751ef62` = `FEngineLoop::Tick`, `EngineTick`,
`GuardedMain`, `GuardedMainWrapper`, `LaunchWindowsStartup`, `WinMain`, CRT-entry. They appear in
**40 of the 87 dumps**, including 24 `Fatal error: Couldn't spawn player` reports that have nothing
to do with either family. Any game-thread crash after engine start shares them. **Overlap on this set
must never be reported as family similarity** — that was the shape of the prompt's "shares only the
tail frame `37f8b8c`" statement, and with the full chain it becomes 7 frames without becoming any more
informative.

### 3.3 The genuinely interesting match: an existing 6-dump cluster

Six other dumps share **all 23** of this dump's game frames:

| dump | secs | `ErrorMessage` | head frames absent from ours |
|---|---:|---|---|
| `471B4885` | 60 | AV reading `0x0` | `1345ff8 534c16e` |
| `10CF9C87` | 84 | AV reading `0x0` | `13455d0 1345511` |
| `838C7D98` | 259 | AV reading `0x0` | `1345ff8 534c16e` |
| `DC4A30AB` | 659 | AV reading `0x0` | `1345ff8 37fefe3` |
| `E7323D14` | 677 | AV reading `0x0` | — |
| `A15041E9` | 3334 | AV reading `0x0` | `13455d0 1345511` |

`0x1345511` lies **inside** the known `ProcessInternal` extent `0x13454A0..0x1345591`. So all six are
`ProcessInternal`-depth faults reached through the *same* skeletal-mesh tick path — i.e. the same path
our PI hook is entered on. **INFERRED:** this 23-frame tail is simply "how the hook gets called", and
it will appear under *every* shim-side fault taken from `VtGuard`. It is a signature of the
instrument's entry point, not of a bug. **It is not FK-7 Family A or B.**

---

## 4. The `0x3000000003` fault (the non-fatal, SEH-survived one)

```
[NULL] fatal 0xC0000005 RIP=0x7FF6EB9F2420 rva=0xFE2420 access=READ addr=0x3000000003
       RAX=3000000000 RBX=3000000030 RDX=3000000030
[ANIM] PlayAnimation(A_Ronin_Cosmetic_HeroSelect_Breathe, loop) FAULTED -> anim swapping DISABLED
```

### 4.1 What the code at `0xFE2420` is — **`FMallocBinned2::Realloc`** (MEASURED)

`.pdata` EXACT `0xFE2390..0xFE25A1` (529 B), page decrypted (3,683 non-zero/4,096), `vtables.py` →
slot 7 of a 25-slot vtable at `0x076A0370` (an `FMalloc`-shaped vtable). Disassembled from
`merged.dump.exe`:

```
0xFE23B2  mov  rbx, rdx                 ; Ptr        (arg 2)
0xFE23AF  mov  rdi, r8                  ; NewSize    (arg 3)
0xFE23B8  cmp  r8, 0x7FF0               ; > BINNED2_MAX_SMALL_POOL_SIZE -> large path
0xFE23C5  cmp  r9d, 0x10                ; > BINNED2_MINIMUM_ALIGNMENT   -> fallback
...
0xFE2417  mov  rax, rbx
0xFE241A  and  rax, 0xFFFFFFFFFFFF0000  ; GetPoolHeaderFromPointer(Ptr): round to the 64 KB block
0xFE2420  cmp  byte ptr [rax + 3], 0xE3 ; <<< THE FAULTING READ — FFreeBlock::Canary == 0xE3
0xFE2424  movzx ebp,  word ptr [rax]    ;     FFreeBlock::BlockSize  (uint16 @ +0)
0xFE2427  movzx r14d, byte ptr [rax+2]  ;     FFreeBlock::PoolIndex  (uint8  @ +2)
```

`0xE3` is FMallocBinned2's canary — the same constant the corpus prints in
`FMallocBinned2 Attempt to realloc an unrecognized block … canary == 0x0 != 0xe3` (5 dumps). The field
layout `{uint16 BlockSize @0, uint8 PoolIndex @2, uint8 Canary @3}` matches `FFreeBlock` exactly.

**The arithmetic closes on the reported registers with no slack:**
`RBX = RDX = 0x3000000030` (the `Ptr` argument) → `RAX = RBX & ~0xFFFF = 0x3000000000` ✔ (= the reported
RAX) → fault address `RAX + 3 = 0x3000000003` ✔ (= the reported address), a **READ** ✔.

⇒ **The engine called `FMallocBinned2::Realloc` with `Ptr = 0x3000000030`**, which is not a heap
pointer, and the canary probe faulted. Nothing was overwritten; a wrong *value* was passed in.

### 4.2 Is `0x3000000000` a tag or shift of a real pointer? **No.**

- **Shift/tag test:** live heap pointers in this process are `0x1A4…` (45-bit). `0x3000000000` is not
  `0x1A4…` shifted, rotated, masked, or sign-extended by any power of two. No candidate reproduces it.
- **`ptrhunt.py` (with a positive control first).** Control: hunting `0x1A48D01D560` (`r14`, known
  present) returns **14** 8-aligned slots across stack and heap — the tool works on this dump.
  Then:
  - `0x3000000030` → **1** 8-aligned slot, at `0x1A355A93B18`. Reading its context shows
    `… 01 00 38 00 30 00 38 00 | 30 00 00 00 30 00 00 00 …` — it is **inside UTF-16 text** (the
    characters `8`,`0`,`8`,`0`,`0`…, i.e. the backend port string). **A byte coincidence, not a
    pointer slot.**
  - `0x3000000000` → **0** 8-aligned slots, 51 unaligned.
  - **Blind spot, stated:** the dump carries only **6.88 MB** across 4,263 register-directed ranges out
    of a multi-GB address space, and — decisively — **this dump is not a snapshot of that fault**. The
    `[NULL]` event was caught by SEH and survived at an unknown earlier time. So a hunt here can only
    ever find residue; "0 hits" is close to uninformative and must not be read as "the value never
    existed elsewhere".
- **What it actually is (INFERRED, strongly):** `0x3000000030` = `{ lo = 0x30, hi = 0x30 }` — an
  **`int32` pair read as a 64-bit pointer**. That is the exact bit pattern of a `TArray`'s
  `{ ArrayNum = 48, ArrayMax = 48 }` (or an `FString`'s `Len/Max`) when a caller reads the container
  **8 bytes past** its `Data` pointer. `Num == Max` is the ordinary exact-fit case, which is why both
  halves are equal. This is a **struct-offset / type-confusion at a call boundary**, not memory
  corruption.
- **Corroborating shape in the corpus (MEASURED):** dump `0AA94D3D` (`secs=56`) is
  `AV reading address 0x0000000300000b33` — the same `{small int32 | int32}`-as-pointer shape. Its
  faulting site is *different* (`0xFA4A53`: `mov rax,[rcx]; call [rax+0x60]`, a virtual call through
  the bad pointer, extent `0xFA4A34..0xFA4A75`), on a different build (base `0x7FF6B54F0000`). So the
  **shape** recurs (2 of 87); the **bug** does not.

### 4.3 Does it share a mechanism class with the `0x01` byte at `PCM+0x420`? **No.**

| | `PCM+0x420` (FK-7 / FK-24) | `0x3000000003` |
|---|---|---|
| side | **write** | **read / argument pass** |
| width | **exactly 1 byte** (measured: 290 of the surrounding offsets byte-identical in 4/4 dumps) | **8 bytes**, and nothing was written at all |
| value | the literal `0x01`, in 4/4 | a plausible `{int32,int32}` container header |
| target | a **live, otherwise-intact** object's field | no target — a bogus argument consumed by the allocator |
| collateral | zero | zero |
| repeatability | same byte of the same object across 4 launches with different heap bases | one occurrence, one site |

Calling these "the same class" requires generalising to *"a bad pointer appeared"*, which is exactly
the over-generalisation `memory/supervive-instrument-artifact-pattern.md` warns about. **They are
different mechanisms.** The honest link is weaker and more useful: *both are pointer-shaped values
that are wrong at a **known field offset**, so both are cheaply testable by fixing the offset rather
than by hunting a writer.*

### 4.4 A real hazard this creates, worth recording

`CallNativeGuarded` handles this fault with `EXCEPTION_EXECUTE_HANDLER` (`SehDump`, `:833`). That
unwinds out of the middle of `FMallocBinned2::Realloc` — **potentially holding a binned-allocator lock
or leaving pool bookkeeping half-updated**. Surviving the fault is not free: any later
allocator-adjacent crash in the same session is suspect. (INFERRED, from the unwind semantics; not
measured here.) Note that the innermost *plausible* stale frame in the fatal crash's stack
(`0xFEC9F0`, a scalar deleting destructor calling `operator delete` at `0xFAB490`) is allocator-side —
suggestive only, since §1.2 classifies that frame as a walker artifact.

---

## 5. Did the vtguard PREVENT Family B, or was it merely NOT EXERCISED?

### **Plainly: NOT EXERCISED. This run contains no evidence either way, and one dump could not have proved prevention even if it had.**

**MEASURED facts:**
- `3c5dc52`, `3c5d255`, `12c7e2d` are absent from the chain.
- The build is `tutorial_launch_play_wprobe_v66.dll` (`build.ps1` `'play-wprobe-v66' =
  RM_PLAY, KWPROBE=1, KPUPYAW=-90`) with source defaults `KVTGUARD 1` (`:1472`), `KGCROOT 1` (`:1169`),
  `KXFORMFIX 1` (`:167`), `KTESTACTOR 0` (`:3959`), `KCAMPITCH -66.0` (`:3634`) — so yes, the guard was
  compiled in.
- `LogChaosCloth` count in this run's `Loki.log` = **0**; `FlushAsyncLoading` count = **9**.

**Why prevention is not shown:**
1. **The guard's own detection line is the gate, and it is unreadable.** `fk7-crash-settled.md` §0.5
   makes every read conditional on `[VTG] *** ViewTarget.Target INVALID … lowbyte=0x01`. That line
   lives in `docs/tutorial-launch-marker.txt`, which was truncated ~3 h later. **We cannot tell whether
   the guard ever detected anything.** A quiet run without the detection line is explicitly classified
   VOID, not a pass.
2. **The corruption is conditional at ~1-in-3 to 1-in-2 per launch** (§0.2 of FK-7). One quiet run has
   a 50–80 % chance of being quiet with a guard that does nothing.
3. **The run died at T+2550 s for an unrelated reason** — its own instrument. Whatever window it was in
   was cut short by the probe, so "it survived" is not even a fair sample.
4. **Positive evidence that the antecedent may not have occurred at all:** `LogChaosCloth = 0` in this
   session, whereas it fires exactly **1×** in each of the four crashing FK-7 sessions and **0×** in
   each of the five non-crashing ones. On FK-7's own reading that is the *non-crashing* profile. It is
   at least as likely that the camera bug's precondition never arose as that the guard suppressed it.

**What would distinguish "prevented" from "not exercised"** — unchanged from `fk7-crash-settled.md`
§0.5, and this dump adds nothing to it:
- **Runs 1–2, `play_novtguard`, held to T+220 s.** Until the *candidate vintage* is shown to reproduce
  the crash at all, a quiet `play` run is uninterpretable. (The 4 camera dumps span 3 build vintages,
  none of them this one.)
- **Runs 3–4, `play`, gated on `[VTG] *** INVALID` appearing in the marker.** Detection present +
  survival = the strongest available close. Detection absent = VOID.
- **And now, additionally: the marker file must be copied off after every injection**, or the gate is
  unreadable exactly as it was here.

---

## 6. Timeline

All times UTC as logged; local = UTC−5. Process **PID 38832**.

| wall (UTC) | T+ | event | source |
|---|---:|---|---|
| 03:06:20 | 0 | `Log file open, 08/03/26 22:06:20` (local) | crash `Loki.log` line 1 |
| ~03:08:01 | ~101 s | `[stage] ready: uptime=101s uiready=2`; manual-map of `tutorial_launch_fo` (`0x1A478360000`), `gft_ready_fix` (`0x1A478BE0000`), `tutorial_launch_sp` (`0x1A47F120000`), **`build/tutorial_launch_play_wprobe_v66.dll` (`0x1A4838A0000`)** | `docs/fk24-stage-run2.log` (mtime 22:08:50 local) |
| 03:47:20 | 2460 s | `LVL_Tutorial` world live — navoctree population, `BP_BotNavLink_C`, generated-level static meshes | crash `Loki.log` :6039–6136 |
| ~03:47:37 | ~2477 s | `gft_ready_fix` **re-injected** (`base=0x7FF6EAA10000`, matching this process) | `docs/gft-ready-marker.txt` mtime 22:47:37 local |
| ~03:47:40 (INFERRED) | ~2480 s | a **second** wprobe-family image mapped at **`0x1A4A4690000`** — MZ verified in-dump, base absent from the stage log, `[WP]`/`[VTG]`/`[PL]` format strings present at `shim+0x2C862 / +0x2F97C / +0x2F99B` | minidump memory |
| 03:49:09.744 | 2529 s | `ComponentEncroachesBlockingGeometry_WithAdjustment … StaticMeshActor_2147456273` | crash `Loki.log` :22724 |
| 03:49:09.746 | 2529 s | `Calling SetStaticMesh on … StaticMeshActor_2147456273 … but Mobility is Static` — **the shim's one-time `KSMACTOR` post-body-build block** | crash `Loki.log` :22725 (last line) |
| ~03:49:20 | **2550 s** | **CRASH** — `WpSelfTestTick` phase-0 store → unclaimed `#DB` | `SecondsSinceStart`, folder mtime 22:49:20 local |

**Relative to the historic FK-7 camera window (T+173…194 s): far OUTSIDE — by a factor of ~13.**

But that comparison is close to meaningless here, and saying only "outside" would be misleading. The
T+173…194 s figures come from sessions where the shim was injected **at launch**, so
`SecondsSinceStart` and "time since body build" nearly coincide. In this run the tutorial world was
not entered until **T+2460 s**, so the comparable clock is *time since the shim's post-build block*:
**≈11–21 s**. That happens to overlap the ANIM family's ~20 s offset — **coincidence, not evidence**,
since the faulting instruction is identified byte-for-byte and is ours.

**Unresolvable from this dump:** the exact moment `[PL] *** init complete` printed, and where in the
window the `[ANIM]`/`[NULL]` fault landed. Both lived in `docs/tutorial-launch-marker.txt`, truncated
2026-08-04 01:45:05 (FK-25).

---

## 7. Consequences, and what to fix before the next `wprobe` launch

1. **`wprobe` as shipped can kill the process.** A `#DB` that `WpHandle` declines becomes an unhandled
   `STATUS_SINGLE_STEP`. The source anticipates this in three places (`:677` D3 grace, `:1896` D3 fix,
   `:1854` D1 fix) and it still happened. Before another launch, add a **terminal fallback**: if the
   exception is `STATUS_SINGLE_STEP` **and** `Dr6` names our slots **and** `Dr0` equals `g_wpAddr`,
   swallow it with `EXCEPTION_CONTINUE_EXECUTION` regardless of `g_wpArmed` — an unowned step that
   provably names our address can only be ours, and declining it is strictly worse than a stale
   record.
2. **Never map two `wprobe`-family images into one process.** Two `CrashVEH`s, two `g_wpArmed`s, one
   set of debug registers. `inject.exe` should refuse (or the shim should detect a sibling by scanning
   for its own signature and stand down).
3. **Do not escalate to `wprobe2` on the S107 evidence.** §2.5 shows the DR path was live process-wide
   and the game thread's DR fired. The escalation criterion ("VOID verdict") was not met. Fix the
   liveness window / the handler instead. (Also check the `8000 ms` in the S107 log against
   `KWPSELFWAITMS = 90000` at `:494` — they disagree.)
4. **Copy `docs/tutorial-launch-marker.txt` off after every single injection** (FK-25). This triage's
   one irreducible gap — *why the handler declined* — is exactly the thing that file recorded.
5. **Open discrepancy: zero screenshots.** `KSHOT` defaults to 1 with shots at 3/8/14/22.5 s after the
   body build, the post-build block demonstrably ran at T+2529 s, and the crash was ~11–21 s later —
   yet **no PNG anywhere under `Saved/` is newer than 2026-07-26**. Either the body build did not
   complete, or the shot path failed, or shots go somewhere I did not search. Worth one cheap check;
   until then, do not use the screenshot-count discriminator on any run of this vintage.
6. **Fix the `{int32,int32}`-as-pointer bug behind `[ANIM] PlayAnimation … FAULTED`** by auditing the
   param-buffer offsets around `PlayAnimOn` (`:4218`) — `g_oPaAnim` / `g_oPaLoop` come from
   `ParamOffset(...)` with silent fallback to previous values when the lookup returns `0xFFFFFFFF`.
   That silent fallback is the same failure shape as the value in the fault.

---

## 8. Reproduce this triage

```powershell
$D = "$env:LOCALAPPDATA\SUPERVIVE\Saved\Crashes\UECC-Windows-166396E24F5A36C5727032B196D739EA_0000\UEMinidump.dmp"
cd "G:\git\Supervive Revival Project\tools\crashtri"
python mdctx.py  $D                       # exception record + GPRs  (Dr0-Dr7 need the snippet in §2.2)
python ptrhunt.py $D 0x1A48D01D560        # POSITIVE CONTROL first
python ptrhunt.py $D 0x3000000030 0x3000000000
cd "..\strxref"
python strxref.py func 0x3C5DC52          # POSITIVE CONTROL for the resolver
python strxref.py func 0x3ED1A7F          # -> 'FTickFunctionTask' + LIGHTWEIGHT_TIME_GUARD
python vtables.py slotof 0x36A3F30        # -> slot 353 of USkeletalMeshComponent
```
The Dr0–Dr7 read, the 128-thread Dr7 census, the shim-image disassembly and the `0xFE2390`
disassembly are short `mdctx.MD` / capstone snippets over `dumps/merged.dump.exe`
(file offset == RVA); all are reproduced inline in §1, §2.2, §2.5 and §4.1.

**Nothing in `%LOCALAPPDATA%\SUPERVIVE\Saved\Crashes` was written. No file outside `docs/` was
modified.** (`docs/symbols.csv` was regenerated in passing by `name_addrs.py` — a 2-line
non-deterministic tie-break — and immediately restored with `git checkout`.)
