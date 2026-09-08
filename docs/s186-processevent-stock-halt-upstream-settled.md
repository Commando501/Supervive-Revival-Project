# S186 — `UObject::ProcessEvent` is stock UE at 0x1344E10 with NO gate; halt is upstream at UE's per-frame pump [M+I,strong]

**Offline 2026-09-08**, disassembly against `dumps/merged14.dump.exe`, zero live flights.
Adversarially-verified via workflow `wf_d1c2cb4c-1a1` (5 agents, 1.58M subagent tokens).

## Headline

★★★★★★★ **[M] `UObject::ProcessEvent` sits at RVA `0x1344E10..0x1345491` (1665 bytes) —
confirmed via 3651 vtable qword references in `.rdata` (every UClass's vtable slot for
ProcessEvent points at this RVA). Full disassembly shows STOCK UE 5.4 code: /GS cookie
prologue, IsGarbage check (bit 30 of ObjectFlags @+0xC), FUNC_Native/net-dispatch branch,
property-copy loop, FFrame construction, and a clean handoff to
`UObject::CallFunction(0x1225F30)` at `0x13453A0`. NO global-flag check, NO conditional
branch on any protector state, NO patch anywhere in the function body.**

⇒ **[I,strong] The S181 halt gate is UPSTREAM of ProcessEvent** — at UE's per-frame pump
(`UGameEngine::Tick` or `FEngineLoop::Tick`) or the tick task graph
(`FTickTaskManager::RunTickGroup` / `FTickFunction::ExecuteTick`). The workflow's
shared-downstream rule (R-S186-a, banked here) is the deciding logic: the S185 halt-set
spans AActor (`ReceiveTick`), UAnimInstance (`BlueprintUpdateAnimation`), UUserWidget
(`Destruct` / `BP_OnDeactivated`), and input (`InpAxisKeyEvt_MouseWheelAxis`) — four
NATIVELY UNRELATED subsystems whose only common upstream is UE's frame pump.

## What was measured offline

Disassembled three windows of `UObject::ProcessEvent` in `merged14.dump.exe`:

**Prologue (`0x1344E10..0x1344EBA`)** — established S186 first-pass:
- /GS cookie: `mov rax, [rip+0x8995352]; xor rax, rbp; mov [rbp+0x130], rax`
- Arg saves: `mov r13, r8; mov rdi, rdx; mov r15, rcx`
- `test rcx, rcx; je fail` — null `this` guard
- `mov eax, [rcx+0xC]; shr eax, 0x1E; not al; test al, 1; je fail` — **IsGarbage check on bit 30 of ObjectFlags** (canonical UE `RF_MirroredGarbage` = `0x40000000`)
- `test dword ptr [rdx+0xB8], 0x410; je NON_NET_PATH` — Function-flags mask test. **Actual mask is `0x410`** (verified from raw bytes `f7 82 b8 00 00 00 10 04 00 00`), not `FUNC_Net (0x40) | FUNC_NetRequest (0x100)` as the initial annotation guessed. Decodes as `FUNC_Native (0x400) + bit 0x10`. Not the S185 gate — this is a routine flag branch, not a state check.
- Vtable dispatch at `[rax+0x278]` and `[rax+0x280]` for the net path — standard `CallRemoteFunction` two-step.

**Middle (`0x1344EBA..0x1345380`)** — S186 second-pass:
- More `[rdi+0xB8]`/`[rdi+0xBC]` UFunction flag reads
- FFrame construction on stack (`[rbp+0x10..0x50]`) — the standard FFrame layout
- Property property-flag masking (`and eax, 0x480; cmp rax, 0x80`) — standard `EX_LocalVariable`-style iteration
- Two calls to a small helper `0x100610` (probably `FFrame::Step` or an FOutParmRec initializer)
- Property/parameter loop copying from `Parms` buffer into FFrame local area
- **No global-flag reads.** All reads are of the passed-in objects.

**Tail with the CallFunction site (`0x1345380..0x1345491`)** — S186 third-pass:
```
0x134538C  lea r14, [rax + r13]
0x1345390  mov r9, r14                      ; r9 = UFunction*
0x1345393  lea r8, [rbp + 0x80]              ; r8 = FFrame*
0x134539A  mov rdx, r15                      ; rdx = RESULT_DECL
0x134539D  mov rcx, rdi                      ; rcx = UObject* this
0x13453A0  call 0x1225F30                    ; UObject::CallFunction (S184)
0x13453A5  cmp r12, 0
0x13453A9  jne EPILOGUE
0x13453AB  mov rbx, [rdi + 0x88]             ; UFunction property iterator
... standard out-parameter unwinding ...
0x1345468  mov rcx, [rbp+0x130]              ; /GS cookie check
0x134546F  xor rcx, rbp
0x1345472  call __security_check_cookie
```

**NO conditional branch preceding `call CallFunction` at `0x13453A0`.** The four-arg setup is a straight fall-through — no `test / je` on any global, no companion-liveness check, no vtable indirection that could be hijacked. ProcessEvent unconditionally calls CallFunction whenever the outer flag/property-flag path is taken.

## Class-identity confirmation from vtable-slot search

Independent [M] evidence, orthogonal to disassembly:

```
searching for qword 0x7ff60a284e10 (= ImageBase + 0x1344E10)...
  .rdata: 3651 qword hits
```

**3651 vtable slots in `.rdata` point at this RVA.** UE has ~3651 UClasses in this build (the count matches). Every UClass's vtable has a slot for `UObject::ProcessEvent` (a UObject virtual). If any protector had OVERRIDDEN this slot for AActor / UUserWidget / UAnimInstance, we'd see fewer than 3651 hits at this RVA plus additional hits at the override target. We see 3651 clean.

⇒ **[M]** ProcessEvent is identified AND the protector has NOT installed a vtable override on ProcessEvent for any UClass. The gate is not a vtable interception.

## rel32 caller of ProcessEvent: `0x33962ED` inside a 77-byte wrapper — dead code

Scanning for direct `call ProcessEvent` sites found ONE rel32 caller at `0x33962ED`,
inside a small (77-byte) function at `0x33962AA..0x33962F7` that has:
- A double global-flag check gating whether ProcessEvent fires:
  - `movzx esi, byte [.data:0x9d28b12]` at entry
  - `cmp byte [.data:0x9e1e44c], 0; jne SKIP` before the ProcessEvent call
- Both flag bytes read **all zeros in `merged14`** (16 bytes each, quad-aligned).
- Function has **0 rel32 callers** and **0 vtable qword references** anywhere in
  `merged14`'s decrypted sections.

⇒ **Dead/trace code, not the halt mechanism.** The gate-shape here is a red herring;
this wrapper is either called from a page that's still dark in merged14 (~45% of `.text`
is), OR it's dead debug code left over from a shipping strip. Either way, S183/S185
observed the CallFunction site 30 times but never observed this wrapper firing —
consistent with it being unreachable in normal execution.

**Instrument-artifact banked as R-S186-f**: a small function with an obvious global-flag
gate is not proof of the S181 halt mechanism unless you also verify it's actually reachable.

## What the halt mechanism CAN'T be (refuted candidates)

Given ProcessEvent is stock and the halt-set spans four unrelated subsystems (S185),
these candidates are REFUTED:

| candidate | why refuted |
|---|---|
| Gate inside ProcessEvent itself | [M] disassembly of 1665 bytes shows stock UE code, no global checks |
| Vtable override on ProcessEvent for any class | [M] 3651 vtable slots all point at stock 0x1344E10 |
| `AActor::TickActor` per-class gate | [M] UAnimInstance and UUserWidget aren't AActor — halt-set has both (R-S186-c) |
| Wrapper at `0x33962AA` | [M] 0 callers reachable in decrypted code + flags read 0 |
| Any per-subsystem gate (AnimComponent, UMG, InputStack independently) | [M] halt-set spans four DIFFERENT subsystems in lockstep — a shared common cause is required (R-S186-a) |
| Thread wedge / synchronization block (H4a-primary) | [M] refuted at S182 (all 137 threads in canonical waits) |

## What survives (the actual gate candidates)

**Ranked by likelihood after all rules applied:**

### #1 — `UGameEngine::Tick` (per-frame pump) [I,strong]
Every subsystem that reached ProcessEvent in baseline is downstream of `UGameEngine::Tick`.
This is the SINGLE shared common upstream. If gated, tick + anim + input + widget lifecycle
all halt in lockstep. Backend network I/O (`IHttpManager`) uses its own thread pool and
would NOT halt — consistent with S182's observation that backend telemetry continued
post-kill.

**Offline location hint**: Look for the string `"UGameEngine::Tick"` in `.rdata`, then
find its LEA site. Or find `UEngine`'s vtable and read slot ~11-12 (the Tick virtual).

### #2 — `FEngineLoop::Tick` (outer game-loop frame pump) [I]
One level above UGameEngine::Tick. If gated here, EVERYTHING pauses including the frame
counter. Would explain why `NtDelayExecution(29ms)` continues (Sleep is at the FEngineLoop
level) but nothing else runs.

### #3 — `FTickTaskManager::RunTickGroup` / `FTickFunction::ExecuteTick` [I]
The tick task graph. Gates all TG_* group execution. Would halt all Actor/Component ticks
including anim tick. But **wouldn't halt widget lifecycle or input events** — those go
through UGameEngine::Tick directly, not the task graph. Slightly weaker phenotype match
than #1.

### #4 — `UGameViewportClient::Tick` / `SlateApplication::Tick` [S]
UMG widget ticks and input dispatch flow through the viewport client's tick and Slate's
tick, both called from UGameEngine::Tick. Gating here alone wouldn't halt actor ticks
though. Doesn't cover the full halt-set on its own — but a shared parent function pointer
that both Slate and world tick go through IS a candidate.

## Rules banked (from the S186 workflow synthesis)

### R-S186-a: Shared-downstream rule. When a halt-set spans multiple unrelated native subsystems (tick task graph + animation + widget lifecycle + input events), the gate is in their SHARED downstream, not in any per-subsystem site. [M]

Applied here: the S185 halt-set spans four subsystems (AActor tick, UAnimInstance,
UUserWidget lifecycle, input events). Every per-subsystem candidate (AActor::TickActor,
UAnimInstance::NativeUpdateAnimation, UUserWidget::NativeTick, UPlayerInput::ProcessInputStack)
is REFUTED because it can't explain the OTHER halted subsystems. Only shared upstream
sites (UGameEngine::Tick, FEngineLoop::Tick) survive.

### R-S186-b: Instrument-granularity rule for gate localisation. An instrument at a leaf dispatch point (kPiRva=0x13454A0 ProcessInternal entry) cannot discriminate a gate AT the leaf from a gate anywhere UPSTREAM in its call chain — an upstream gate produces IDENTICAL readings. Requires a second instrument at a different level to discriminate. [M]

Applied here: S181's `hitsAny=0` reading is compatible with a gate at ProcessInternal, at
CallFunction, at ProcessEvent, at TickActor, or at UGameEngine::Tick — all produce the
same "no PI dispatch" observation. S185 narrowed by NAMING the UFunctions (only certain
categories fire); S186 narrowed further by confirming the leaf sites are stock.
Discriminating between UGameEngine::Tick and FEngineLoop::Tick requires yet another
instrument — a frame-counter probe.

### R-S186-c: Class-hierarchy positive-control for override candidates. When a halted-set item includes a UObject-derived class that is NOT AActor (e.g. UAnimInstance, UUserWidget, UActorComponent), any candidate positing an AActor-scoped override is dispositively REFUTED. Enumerate the classes in the halted set BEFORE hypothesising a per-class-family gate. [M]

Applied here: S185's UAnimInstance and UUserWidget hits refute AActor-scoped hypotheses
in one line. Would have saved considerable analysis time in the sessions to come.

### R-S186-d: Cheapest-identity-check-first rule for UObject virtuals. Before disassembling more of a function body to confirm its identity as a specific UObject virtual, do the vtable-slot check. UE virtuals live at known vtable slots documented in this project (fk22-dropphase-reachability.md:1774 records ProcessEvent at disp 0x270 = slot 78). One qword-search of `.rdata` for the function's VA counts references (offline) or one RPM read of a UObject's vtable slot (live) confirms identity. [M]

Applied here: I initially disassembled 336 bytes of ProcessEvent for identity checks
before running the vtable-slot qword search. The search returned 3651 matches — dispositive
[M] identity in one query. Doing the vtable search FIRST would have saved ~4 disassembly
rounds.

### R-S186-e: UFunction flag-mask sanity rule. A `test [Func+0xB8], immX` inside a suspected ProcessEvent-family function decodes a subset of EFunctionFlags. Stock UE 5.4: FUNC_Net=0x40, FUNC_NetRequest=0x100, FUNC_Native=0x400, FUNC_Exec=0x200, FUNC_Static=0x2000. Cross-check the mask against these values before annotating the branch's purpose. [M]

Applied here: S186 seed annotated `test [rdx+0xB8], 0x410` as `FUNC_Net | FUNC_NetRequest`,
which is wrong on both bits. The actual mask is `FUNC_Native (0x400) | bit 0x10`. The
initial annotation would have misled a successor about which branch handles net RPCs.

### R-S186-f: A visible gate is not evidence of the halt mechanism unless the gate is REACHABLE. A small function with an obvious global-flag check that has 0 callers in decrypted code is dead trace code, not the mechanism. [M]

Applied here: the 77-byte wrapper at `0x33962AA` looks like a textbook gate (two global-
byte reads, if-non-zero-skip-ProcessEvent structure). But it has 0 callers in `merged14`'s
decrypted `.text` — 45% of `.text` is dark, so a caller MIGHT exist there, but the wrapper's
ring-buffer never fired during S183's 60s observation window. That rules it out as the
S181 mechanism.

## What is now open

1. **Identify `UGameEngine::Tick` in `merged14`.** Cheap offline: search `.rdata` for the
   string literal `"UGameEngine"` or `"GameEngine.Tick"`, find LEA sites, then walk to
   the containing function.
2. **Check UEngine vtable slots.** UEngine is a small class; its vtable slot for Tick is
   documented in UE 5.4. Read that slot's target from any UEngine-derived vtable in `.rdata`.
3. **Live discriminator**: instrument the shim to sample a per-frame counter (e.g.
   `GFrameCounter` at a documented `.data` RVA) during baseline vs post-kill. If the
   counter advances at baseline rate but is frozen post-kill, the gate is at
   FEngineLoop::Tick. If it still advances but ticks are skipped, the gate is at
   UGameEngine::Tick.
4. **Practical**: if the gate turns out to be a compiled `if (!bGameActive) return;` check
   inside UGameEngine::Tick reading a specific `.data` byte, and that byte's writer is
   companion-related, then a data poke to hold the byte at "active" restores tick
   dispatch. Data poke = safest write class in this project.

## Files preserved

- `docs/s186-processevent-stock-halt-upstream-settled.md` — this doc
- Disassembly captured in-doc
- Workflow output: `C:\Users\eastr\AppData\Local\Temp\...\tasks\w55ikkhoj.output` (5 agents, 1.58M tokens)

## What S186 did NOT do

- No identification of the specific tick-pump or task-graph function where the gate
  actually lives (offline follow-up).
- No live discriminator between UGameEngine::Tick vs FEngineLoop::Tick vs task graph.
- No commit yet.
