# S188 — `FEngineLoop::Tick` identified at 0x4027850; the halt gate is NOT inside it [M]

**Offline 2026-09-08**, disassembly against `dumps/merged14.dump.exe`, zero live flights.

## Headline

★★★★★★★ **[M] `FEngineLoop::Tick` sits at RVA `0x4027850..0x4028104` (2228 bytes)**, identified
via (a) reverse-scan of the epilogue-ending function containing the delta-time global store
`movsd [rip+X], xmm0` at 0x40280E3, (b) forward-scan of the prologue's `mov r11, rsp; push rbp;
push rsi; sub rsp, 0x278` (632-byte frame + /GS cookie), and (c) 1 rel32 caller at `0x402FF8F`
inside GuardedMain-like function at `0x402FD90` (references "Starting", "DefaultMain" strings).

★★★★★ **[M] There is NO companion-liveness gate inside FEngineLoop::Tick.** Full-body scan:
- Prologue: standard MSVC large-frame + /GS cookie, no global-byte reads
- Body: only 16 rip-relative reads/writes to `.data`; the two `cmp byte [.data:X]` sites are
  verbosity-logging checks (`.data:0x9D28B31` gated by `sil`=0 causing fallthrough, and
  `.data:0x9D28F18` checking log-verbosity >= 4). Neither gates the tick body.
- Epilogue: exactly **one `ret` instruction** at 0x4028103, preceded by the single
  `add rsp, 0x278; pop rsi; pop rbp` — **no early-exit paths.** Every entry into
  FEngineLoop::Tick runs to the same single exit.
- Caller (GuardedMain's tick loop) at `0x402FF8F` is UNCONDITIONAL: `lea rcx, [rip + X]; call
  FEngineLoop::Tick`. No pre-call gate.

★★★★★★ **[M] The GFrameCounter++ site is INSIDE A HELPER, not inside FEngineLoop::Tick.** The
`inc qword ptr [rip + 0x7359c4a]` at RVA `0x29EF4E7` lives inside a 293-byte function at
`0x29EF3D3..0x29EF4F8` that:
- Takes an array + index (`mov rdi, [rax+rcx*8]` at 0x29EF3D8)
- Calls a tick virtual on the array element (`call [rdi_vt+0x18]` returns xmm0=DeltaTime?)
- Reads/writes a double at `[rbx+0x48]` (likely a per-object frame-time global)
- Does refcount management on rbx
- **THEN** increments GFrameCounter

**This helper has 0 rel32 callers in `merged14`** — meaning its caller lives on one of the
~45% dark pages, OR it's dispatched via an indirect-call-through-function-pointer-table
mechanism (a FrameEnd delegate, a ticker registration, or a specific tick-manager scheme).

## What this settles

Combining S186 + S187 + S188:

| session | claim | grade |
|---|---|---|
| S186 | ProcessEvent is stock UE, no gate inside | [M] |
| S187 | GFrameCounter frozen post-companion-kill | [M] |
| S188 | FEngineLoop::Tick is stock UE with only 1 ret, no early-exit paths, no gate inside; GFrameCounter++ is in a helper called INDIRECTLY | [M] |

⇒ **[M] The halt gate is:**
- NOT inside `UObject::ProcessEvent` (S186)
- NOT inside `FEngineLoop::Tick` (S188)
- NOT at the call site FROM GuardedMain to FEngineLoop::Tick (S188 — call is unconditional)

⇒ **[I,strong] The gate is at the indirect-dispatch that calls the 293-byte GFrameCounter helper.**
Either:
- The tickable-object array (`[rax+rcx*8]`) is emptied of relevant objects post-companion-kill
  (making the helper's loop do zero iterations, so no counter++)
- The helper itself is called from a callback (delegate / ticker registration) that gets
  UN-registered post-kill

The 293-byte helper's `call [rdi_vt+0x18]` pattern (virtual on rdi) is textbook `FTickableGameObject::Tick`
or `FTicker::Tick`. Both are UE mechanisms for per-frame callbacks that register/unregister
dynamically.

## Two possible mechanisms (both consistent with S187)

**M1**: The array `[rax+rcx*8]` (of tickable objects) is emptied. Companion's death causes UE
to un-register all currently-ticking objects (via some UE code that calls
`FTickerBase::Remove()` for each of them). Post-kill, the helper's loop iterates 0 times,
GFrameCounter never gets incremented (or gets incremented 0 times per call).

**M2**: The 293-byte helper itself is stored as a function pointer in a table that gets
CLEARED post-kill. Its rel32-invisible caller reads `if (pFn) pFn();` — post-kill, `pFn = null`,
so the helper is never called and GFrameCounter never increments.

**M3**: The caller of the helper has a companion-liveness gate that skips the entire call
chain (visible only if we identify the caller — which lives on a dark page in merged14).

All three are consistent with S187 (GFrameCounter freezes) AND S188 (FEngineLoop::Tick body
has no early-exit — so it DOES run to its epilogue post-kill, but its intermediate helper
doesn't do anything).

## Where the gate is NOT (offline-refuted)

| location | refutation |
|---|---|
| ProcessEvent early-exit | S186 [M]: full disassembly shows stock UE, no gate |
| ProcessEvent vtable override | S186 [M]: 3651 vtable slots all point at stock 0x1344E10 |
| FEngineLoop::Tick early-exit | S188 [M]: 1 ret in 2228 bytes, only at natural epilogue |
| FEngineLoop::Tick top-of-body byte gate | S188 [M]: no cmp byte [rip+X], je epilogue pattern |
| Immediate caller of FEngineLoop::Tick | S188 [M]: unconditional call at 0x402FF8F |
| Per-subsystem tick gate (AActor::Tick etc.) | S186 [M] via R-S186-c: halted-set spans UAnimInstance + UUserWidget, refuting per-Actor gate |
| Thread wedge / sync-object wait | S182 [M]: 137 threads all in canonical waits, no companion-related wedge |

## Rules banked

### S188-a: One `ret` instruction in a function's entire body means NO EARLY-EXIT PATHS. Every entry produces the same exit. When investigating "halt inside function X", counting rets is a cheap test that refutes early-exit-based gate hypotheses in one scan. [M]

Applied here: FEngineLoop::Tick has 2228 bytes and 1 ret. Not "1 primary ret and several
`add rsp; ret` shortcuts" — literally one. This dispositively refutes the "companion-liveness
byte check causes ret at top of Tick" mechanism.

### S188-b: For a helper function with GFrameCounter++ at its end, if the helper has 0 rel32 callers, its caller is either on a dark page OR uses indirect dispatch (function pointer table, virtual, delegate). Prefer to identify the CALLER's indirection mechanism (qword scan for the helper's VA in `.data`/`.rdata`; or narrow down callers by finding the helper's registration site) BEFORE assuming the helper is dead. [M]

Applied here: the 293-byte GFrameCounter helper at 0x29EF3D3 has 0 rel32 callers, but it's
demonstrably called (baseline GFrameCounter advances at 30 Hz). It must be called via some
indirect mechanism, or from a dark caller. Assuming "0 callers = dead" is wrong.

### S188-c: When the immediate caller of a suspected gated function is unconditional (no pre-call `test/je`), the gate isn't there. Look higher (the ENTIRE parent function may have an early-exit that skips the whole tick section), OR lower (inside the callee body, past its prologue). [M]

Applied here: GuardedMain-like caller (0x402FD90) calls FEngineLoop::Tick unconditionally at
0x402FF8F. Combined with S188 [M] that FEngineLoop::Tick has no early-exit, the gate must
be in an even deeper indirect layer (per the 293-byte helper's indirect dispatch).

## What is now open

1. **Identify the caller of the 293-byte GFrameCounter helper.** Scan `.rdata` and `.data` for
   qword references to VA `0x29EF3D3` — a hit tells you which table stores it (potentially
   an FCoreTicker registration slot, an FTickableGameObject vtable entry, etc.).
2. **Live discriminator between M1/M2/M3**: run S187's frame_probe.py but ALSO sample the
   tickable-object array (a `.data` field near the 293-byte helper) or the helper's
   dispatch-slot (a function pointer in `.data`). If the array shrinks to 0 elements
   post-kill, M1 wins. If the function pointer becomes null, M2 wins.
3. **Practical**: if the mechanism is M1 (unregistration), re-registering the tickable
   restores frame dispatch. If M2 (function-pointer clear), restoring the function pointer
   via one `.data` qword poke restores dispatch. Both are safest-class writes.

## Files preserved

- `docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md` — this doc
- Disassembly captured in-doc
- Source: `dumps/merged14.dump.exe`

## What S188 did NOT do

- Not identify the caller of the 293-byte GFrameCounter helper
- Not discriminate M1/M2/M3
- No commit yet
