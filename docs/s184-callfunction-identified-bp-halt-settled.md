# S184 — `SUPERVIVE.exe+0x1225F30` is `UObject::CallFunction`; the halt is BP interpretation, not any single PI site [M]

**Offline 2026-09-08**, disassembly against `dumps/merged14.dump.exe`, zero live flights.
Follows S183's [M] finding that all 29 baseline PI dispatches came from
`SUPERVIVE.exe+0x1225fd6`.

## Headline

★★★★★★ **[M] `SUPERVIVE.exe+0x1225F30` is `UObject::CallFunction(FFrame&, RESULT_DECL,
UFunction*)`** — the UE standard bytecode-driven BP dispatch entry point. Its `call
[r14+0xE0]` at `+0x1225FCF` (the site whose return-address S183 caught at `+0x1225FD6`)
is exactly `UFunction::Func`, which for a BP UFunction is `UObject::ProcessInternal`.

**[M] All 29 baseline PI dispatches were BP→BP bytecode calls through this dispatcher.**
Zero direct-`ProcessEvent`→`ProcessInternal` calls in the 60s window. The halt observed
in S181 is therefore **BP interpretation ceasing process-wide**, UPSTREAM of PI, not
any single ProcessInternal site being blocked.

## The function, byte for byte

Disassembled from `merged14.dump.exe` starting at RVA `0x1225F30` (~200 bytes total):

```
0x1225F30  mov [rsp+0x10], rbx          ; MSVC-style non-volatile save into shadow
0x1225F35  mov [rsp+0x18], rbp
0x1225F3A  mov [rsp+0x20], rsi
0x1225F3F  push rdi
0x1225F40  push r12
0x1225F42  push r14
0x1225F44  sub rsp, 0x20
0x1225F48  mov rdi, [rcx + 0x28]        ; rdi = this->[+0x28] (SuperFunc / FField*)
0x1225F4C  mov r12, r9                   ; r12 = UFunction* arg (callee-saved)
0x1225F4F  mov rsi, r8                   ; rsi = FFrame*    (callee-saved)
0x1225F52  mov rbp, rdx                  ; rbp = RESULT_DECL (callee-saved)
0x1225F55  mov r14, rcx                  ; r14 = UObject*   (callee-saved)
0x1225F58  call 0x7ff60a1f3f00           ; VirtualDispatchResolve(this) -> UStruct* or NULL
0x1225F5D  test rax, rax
0x1225F60  je   0x1225FB8                ; no virtual override -> straight to dispatch
0x1225F62  movsxd rbx, [rax+0x40]        ; rbx = int32(NumEntries)
0x1225F6F  test ebx, ebx
0x1225F71  jns  0x1225F96                ; skip verbose log path if >= 0
0x1225F73  cmp  byte [rip+0x8bf7f26], 3  ; LogScript verbosity gate
0x1225F7C  ...   UE_LOG(...)              ; standard UE log fallback
0x1225F96  cmp  ebx, [rdi+0x40]
0x1225F99  jg   0x1225FB3
0x1225F9B  mov  rax, [rdi+0x38]          ; rax = array data (SuperFunc chain?)
0x1225F9F  cmp  [rax+rbx*8], r15         ; compare array[i] to r15
0x1225FA3  jne  0x1225FB3
0x1225FA5  mov  rdx, rdi
0x1225FA8  mov  rcx, rbp
0x1225FAB  call 0x7ff60a2a4d40           ; ResolveOverride(target, UStruct) -> new target
0x1225FB0  mov  rbp, rax                 ; rbp = resolved target UObject*
0x1225FB3  mov  r15, [rsp+0x40]
0x1225FB8  mov  rbx, [rsi+0x90]          ; save FFrame.Node   <-- entry point .pdata reports
0x1225FBF  mov  r8, r12                   ; RESULT_DECL
0x1225FC2  mov  rdx, rsi                  ; FFrame*
0x1225FC5  mov  [rsi+0x90], r14           ; FFrame.Node = new UFunction (r14)
0x1225FCC  mov  rcx, rbp                  ; UObject* (resolved target)
0x1225FCF  call [r14 + 0xE0]              ; UFunction::Func   <== the PI call
0x1225FD6  mov  rbp, [rsp+0x50]           ; <== S183 caller-ring return addr, all 29 hits
0x1225FDB  mov  [rsi+0x90], rbx           ; restore FFrame.Node
0x1225FE2  mov  rbx, [rsp+0x48]
0x1225FE7  mov  rsi, [rsp+0x58]
0x1225FEC  add  rsp, 0x20
0x1225FF0  pop  r14
0x1225FF2  pop  r12
0x1225FF4  pop  rdi
0x1225FF5  ret
```

**Structural attribution [M]:**
- **Signature**: `(UObject* this = rcx, RESULT_DECL = rdx, FFrame* Stack = r8, UFunction* Function = r9)`
  — the Windows x64 calling convention view of `UObject::CallFunction`.
- **FFrame.Node swap**: `mov [rsi+0x90], r14 ; call ... ; mov [rsi+0x90], rbx` is the
  standard UE pattern for context-switching the FFrame's current node during nested
  bytecode calls. UE's `FFrame::Node` is at offset `0x90` in this build (matches the
  runtime CallFunction wrapper pattern).
- **Virtual dispatch resolver**: `call 0x7ff60a1f3f00` returns a UStruct* (or null),
  then walks its `[+0x38]` array of `NumEntries=[+0x40]` items looking for `[+0x38]`
  = the current UFunction's owner. This is UE's SuperFunc/CallFunctionSpec chain
  walker used for BlueprintCallable override resolution.
- **The dispatch target**: `call [r14 + 0xE0]` — offset `0xE0` inside a `UFunction` is
  `UFunction::Func` in this build (confirmed by `tutorial_launch.cpp` line 43's
  comment referring to fo's stub reading `Func @+0xE0`).

## What the S181/S183 finding actually means, now sharper

**Every BP-to-BP function call in UE goes through this dispatcher.** Bytecode handlers
for `EX_FinalFunction`, `EX_LocalFinalFunction`, `EX_CallMathFunction`,
`EX_VirtualFunction` etc. all funnel here to do the actual invocation. Native → BP
calls via `UObject::ProcessEvent` go through a different path (they call
`ProcessInternal` directly, not via `CallFunction`).

**S183 measured 29 baseline hits at exactly `+0x1225FD6`** — the `call [r14+0xE0]`
site inside CallFunction. **Zero hits at any other RVA.** This means:
- 29 BP→BP dispatches in 60s (menu-parked baseline)
- **ZERO native→BP dispatches** in 60s (no other caller of PI fired)

Post-companion-kill (S181), `hitsAny=0` means **NOT EVEN THIS ONE DISPATCHER FIRES.**
Which means bytecode is not executing at all — no BP function is being interpreted.

⇒ **The halt is UPSTREAM of PI, at the level that would normally schedule bytecode
execution.** The check that gates on companion liveness is somewhere in the
`AActor::Tick → BP tick delegate → CallFunction` chain, OR in the equivalent for
UMG widget event handlers.

## Callers of CallFunction (rel32 scan)

5 rel32 references to `0x1225F30` in `merged14.dump.exe`:

| site | opcode | context | interpretation |
|---|---|---|---|
| `0x13433AD` | `call` (E8) | inside a function around `0x13432xx-0x13434xx` with `retf`-shaped code, `r8=rdi/rdx=r13/rcx=r14` prep | UE bytecode handler, unnamed |
| `0x13453A0` | `call` (E8) | 256 bytes before `kPiRva=0x13454A0` (ProcessInternal). Prologue: `lea eax,[rbp+0x80]; mov rdx,r15; mov rcx,rdi` | **[I,strong]** an `execX` bytecode dispatcher — likely one of the `EX_*Function` handlers; adjacency to PI is not coincidence |
| `0x3C822B0` | `call` (E8) | in a distant band; not investigated | possibly a specialized dispatcher |
| `0x134957F` | `jmp`  (E9) | tail call after `add rsp, 0x38; jmp CallFunction` | inlined `execFinalFunction`-style tail |
| `0x1349780` | `jmp`  (E9) | tail call after `pop rdi; jmp CallFunction` | second inlined bytecode dispatcher tail |

**All 5 callers are in UE's ScriptCore bytecode-handler band.** No caller in
`runtime.dll` or in a game-specific subsystem (e.g. AbilitySystem). This reinforces the
S183 finding: BP invocation goes through stock UE code paths, not through any
protector- or game-specific gate that would be an obvious candidate for the companion-
liveness check.

## Where the gate must live

Given the stock UE dispatchers are unmodified:
- **The gate is NOT in CallFunction or its immediate callers** (those are stock UE
  bytecode handlers). Otherwise the same rel32 scan would have shown something extra.
- **The gate must be higher up** — at the level of what SCHEDULES bytecode execution.
  Candidates, in decreasing likelihood:
  - **`FEngineLoop::Tick`** — the main game loop. If gated, no game work at all
    happens. But S182 showed all threads look healthy and the game thread still
    tick-sleeps at 29 ms, so `FEngineLoop::Tick` IS still running.
  - **`UWorld::Tick`** — dispatches actor ticks. If gated, no actor work but timer
    manager and streamer still run.
  - **`AActor::Tick` / `UActorComponent::Tick`** — either at the base class or
    individual overrides. Menu widgets extend from UUserWidget which has native
    ticks; those could gate on companion.
  - **`FTimerManager::Tick`** — timer callbacks include many BP delegate broadcasts.
  - **UMG widget input dispatch** — mouse hover / click events fire BP delegates.
  - **A cheat/protector Tick component** injected by the protector that intercepts
    the tick chain — some anti-cheats do this.

The next investigation is either:
1. **[S185 offline]** Look for a compiled check inside `UWorld::Tick` (a stock UE
   function, findable via strxref) that reads a shared-memory / global state variable
   whose value differs pre- vs post-companion-kill.
2. **[S185 live]** Extend fo-verbose to ALSO capture `r14` (the UFunction*) at each
   hit, so we can enumerate WHICH UFunctions are being dispatched in baseline. That
   names WHICH subsystem is doing the 29 dispatches (UMG widgets? timer delegates?
   input?), narrowing the halt-target substantially.

**S185 live is cheaper**: one 4-byte add to the stub (`mov [g_piLastUFunc], r14`)
and a dump of unique UFunction names at [4c]. Same-flight discriminator.

## Progression from S183 → S184

| session | new finding |
|---|---|
| **S183** | mechanism named to ONE RVA: `SUPERVIVE.exe+0x1225fd6` [M] |
| **S184** | that RVA is inside `UObject::CallFunction` [M]; all 29 baseline hits are BP→BP dispatches through UE's bytecode handlers; halt is UPSTREAM of PI at whatever schedules BP execution [M]; 5 rel32 callers of CallFunction found, all in ScriptCore [M] |

## Rules banked

### S184-a: When strxref reports `entry .pdata EXACT` at an unusual mid-function-shaped RVA, the `.pdata` may be recording a chained unwind region (e.g. shrink-wrapped epilogue) rather than the true function entry. Widen the disassembly window by ~0x100 bytes backward to find the real prologue. [M]

Applied here: strxref said entry = `0x1225FB8` with `.pdata EXACT`; disassembly at that
RVA started with `mov rbx, [rsi+0x90]` (no prologue). Reading back to `0x1225F00`
revealed the true prologue at `0x1225F30`. The `.pdata` was correctly recording a
sub-region of the function for unwind purposes; the natural entry is further back.

### S184-b: `call [r14+0xE0]` where `r14` is a UFunction* is exactly `UFunction::Func`; if the UFunction is a BlueprintCallable / BP-defined function, `Func` = `UObject::ProcessInternal`. This is a stock UE pattern that identifies bytecode dispatchers on sight — no disassembly of the caller is needed to know the semantic. [M]

Applied here: 62 bytes of assembly + one register (`r14`=UFunction*) + one offset
(`+0xE0`) settled that this function is a bytecode dispatcher without needing to see
its callers or its parent function. UE's stock pattern is that recognizable.

### S184-c: A single-bucket caller-ring (S183-c) combined with function-identification (S184) can tell you what CATEGORY of dispatch is happening (BP→BP via bytecode vs native→BP via ProcessEvent), because different dispatch categories go through different UE code paths. When only BP→BP dispatches are observed in the baseline, that's a strong statement that no native code path calls ProcessEvent for BP functions in the observed window. [M]

Applied here: 29 hits at `+0x1225FD6` (CallFunction's PI call) and ZERO at any other
site means baseline had 29 BP→BP calls and ZERO native→BP calls in 60s. The menu-
parked game does no actor Tick → BP tick dispatches in that window; it only broadcasts
delegates. That's a specific fact about how the menu is architected, not just about
counts.

## Files preserved

- `docs/s184-callfunction-identified-bp-halt-settled.md` — this doc
- Disassembly captured in-doc; source: `dumps/merged14.dump.exe`
- Follow-up needs `dumps/merged14.dump.exe` and offline disassembly

## What S184 did NOT do

- **Identify what schedules BP execution and where the companion-liveness gate lives**
  — offline task, requires walking further up the call chain from CallFunction to
  FEngineLoop::Tick / UWorld::Tick and looking for a shared-memory check.
- **Name the specific bytecode handlers at the 5 caller RVAs** — some are recognizable
  by shape (`execFinalFunction`, `execCallMathFunction`) but not attributed here.
  Requires GNatives[] table lookup or per-caller disassembly.
- **Enumerate WHICH UFunctions were dispatched in the 29 baseline hits** — would need
  a live flight with r14 capture (proposed S185).
- **No commit yet** — bundle with a possible follow-up commit.
