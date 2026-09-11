# S190 next-session prompt — localize the halt gate UPSTREAM of FEngineLoop::Tick

Fresh-session paste-ready opener. Date written: 2026-09-08. Prior sessions: S189 caller hunt +
S189-caveat2 driver identification. Nine `[M]` commits on `dedicated-server-stub`
(`cd1759c`..most-recent) plus the S189/S189-caveat2 pair landing this session.

## Paste this as the opening message

Continuing the F10 mystery investigation. S189 chained the GFrameCounter++ mechanism end-to-end
and refuted the initial gate localization: the 293-byte helper at `0x29EF3D3` is
FPreLoadScreenManager (preload-only) and does NOT fire per gameplay frame. The **real** 30 Hz
driver is the inline site `0x4029349-0x4029353` inside real `FEngineLoop::Tick` at `0x4028110`.
That site fires UNCONDITIONALLY per Tick invocation (recursive-descent CFG, 1340 instructions,
1 ret, all 133 conditional branches diamonds).

⇒ **The halt gate lives UPSTREAM of `FEngineLoop::Tick`.** Not inside Tick's body (S188 [M] on
Init structurally re-confirmed on real Tick by S189-caveat2 Lane B). Not at the immediate call
site (unconditional). The gate is one of three specific mechanisms in the GuardedMain-like caller
chain at `0x402FD90` / `0x403005A`.

Your task: **S190 offline first, then live if needed** — localize the actual halt gate. This is
a two-phase task with a well-defined offline path that may close it before you need to relaunch.

## Read first, in this order

1. **[docs/s189-caveat2-second-gfc-site-settled.md](docs/s189-caveat2-second-gfc-site-settled.md)** — the direct prior; §"What this means for the halt gate hunt" is the load-bearing section. Three specific gate-mechanism candidates named there.
2. **[docs/s189-caller-hunt-settled.md](docs/s189-caller-hunt-settled.md)** — the caller chain map + the FPreLoadScreenManager identification. Load-bearing correction to S188 in §"Corrections to prior sessions".
3. **[docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md](docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md)** — the S188 settled doc. Its structural claim ("1 ret, no early-exit paths") is CORRECT even though the function label was Init not Tick — S189-caveat2 re-verified the same property on the real Tick function.
4. **[docs/s187-gframecounter-halt-frame-pump-settled.md](docs/s187-gframecounter-halt-frame-pump-settled.md)** — the live measurement (30 Hz baseline, 0/1050 predicted counts over 35 s post-kill).
5. **[docs/s186-processevent-stock-halt-upstream-settled.md](docs/s186-processevent-stock-halt-upstream-settled.md)** — rule R-S186-a (shared-downstream) that refutes per-subsystem-gate hypotheses AND that INDEPENDENTLY refutes any FPreLoadScreenManager-based gate.
6. Skim [docs/s181-companion-kill-halts-reflection-settled.md](docs/s181-companion-kill-halts-reflection-settled.md) for the F10 background.

## What's known [M] going in

- **[M] The halt is UPSTREAM of `FEngineLoop::Tick 0x4028110`.** Combining S186 (`ProcessEvent`
  is stock, no gate inside), S188 (Tick has 1 ret + no early-exits — re-verified on real Tick),
  S189-caveat2 (Site 3 unconditional per Tick call), S187 (GFrameCounter frozen post-kill):
  if Tick had run, Site 3 would have fired and the counter would have advanced. It didn't.
  So Tick was not called.
- **[M] The GuardedMain-like caller loop has this shape** (Lane B of S189-caveat2):
  ```
  0x402FD90 GuardedMain-like:
    ...
    loop: 0x4030040 test byte [rip+X], 0        ; X → .data:0x9d29104
          0x4030047 jne  <loop-exit>
          0x403005A call FEngineLoop::Tick       ; 0x4028110
          ...
          jmp loop
    loop-exit:
    call FEngineLoop::Exit
  ```
  (Exact offsets from Lane B's transcription; `0x403005A` is the ONLY external call into the
  entire `0x4028110..0x40295D2` Tick span.)
- **[M] `.data:0x9d29104` is the loop-exit byte.** Not yet confirmed as `GIsRequestingExit`
  itself, but shape matches stock UE's `while (!GIsRequestingExit) Tick()` idiom.
- **[M] The FPreLoadScreenManager path (predicates `0x29F0940` / `0x29F0A30`) is IRRELEVANT to
  the halt.** Both return FALSE every frame in gameplay regardless of companion state.
- **[M] S182**: 137 threads all in canonical Win32 waits post-kill, no companion-related wedge.

## The three candidate halt mechanisms (from S189-caveat2 §"What this means for the halt gate hunt")

**(a) Shutdown byte flip.** `.data:0x9d29104` flips non-zero post-companion-kill, so the
GuardedMain loop exits and the process would proceed to FEngineLoop::Exit. Testable OFFLINE by
enumerating every writer of `.data:0x9d29104` in the image and checking whether any lies on a
companion-kill-triggered code path. Testable LIVE by reading the byte in a post-kill snapshot.

**(b) Tick callee blocks the game thread indefinitely.** Real Tick has ~148 direct calls in its
body. Any blocking primitive (`WaitForSingleObject`, `EnterCriticalSection`, spin-loop on volatile
state) reachable from any callee would produce the observed freeze **without** exiting the loop.
Partly testable OFFLINE by ranking callees by blocking-primitive risk; requires LIVE probe (thread
stack sample post-kill) to identify WHICH callee.

**(c) Game thread blocked/sleeping/deadlocked BEFORE re-entering GuardedMain's next iteration.**
Requires LIVE probe (thread stack sample post-kill). S182 already showed 137 threads in canonical
waits; a game-thread wait for a mutex/event held by a killed thread would fit.

## The S190 offline task list (in order, each ~30 min offline)

### Task 1 — `.data:0x9d29104` writer enumeration [M-decisive if 0 writers on kill path]

1. Scan `.text` for every RIP-relative displacement that would target `0x9d29104` as a WRITE
   (`mov [rip+X], reg`, `inc/dec byte [rip+X]`, `and/or/xor byte [rip+X], imm`, etc.).
   Verify the ImageBase-relative arithmetic against a known control (e.g. GFrameCounter writes
   at S189-caveat2 Lane D's 5 sites).
2. For each writer, run `strxref func <site>` to identify the containing function root. Grep
   `.rdata` for LEA sites naming the containing function.
3. Classify each writer: startup-init / normal-shutdown / debug-flip / exception-handler /
   companion-kill-triggered. `RequestEngineExit()`, `FGenericPlatformMisc::RequestExit()`, and
   `RequestExitWithStatus()` are the stock UE names to look for in .rdata cluster.
4. If **NO writer lies on a companion-kill-triggered path**, mechanism (a) is refuted.
5. If **one writer is reached from `-CompanionWatch`'s kill primitive** (per S181's mechanism
   map), mechanism (a) is [I,strong] and settles with one LIVE byte-read post-kill.

**Positive control**: the same scan for a known-per-frame-write address (e.g. GFrameCounter's
own `.data:0x9d49138`) must return the 5 writers S189-caveat2 Lane D enumerated. Instrument
calibration.

### Task 2 — GuardedMain-like outer caller chain CFG

1. Full recursive-descent CFG on `0x402FD90` (already known extent per S188:
   `0x402FD90..0x40300B9`, 809 B).
2. Enumerate its rel32 callers via strxref. Follow chain to WinMain or the platform-abstraction
   entry (`FEngineLoop::PreInit` → `GuardedMain` → `WinMain` is stock UE; verify against
   `.rdata` strings).
3. Check every dominator of `call 0x4028110` at `0x403005A` for early-exit patterns and byte-gate
   reads. Report each candidate `.data` state address.
4. Cross-check `.data:0x9d29104` against S181/S186's `IsRequestingExit`-like byte candidate.

### Task 3 — Tick callee blocking-primitive census (partial offline, needs live to close)

1. From S189-caveat2 Lane B's CFG (available in the workflow journal), extract all ~148 direct
   call targets from real Tick's chained extent `0x4028110..0x4029797`.
2. For each callee, grep for imports of `WaitForSingleObject`, `WaitForMultipleObjects`,
   `EnterCriticalSection`, `SleepEx`, `WaitOnAddress`, `NtWaitFor*` (via any known ntdll import
   trampoline). Score each callee by (a) presence of blocking-primitive call, (b) whether
   argument is a specific handle (blockable) vs. a timeout-with-fallback pattern.
3. Rank callees by blocking-primitive risk. Focus on callees decrypted only during gameplay (LIT
   in merged14 but NOT in menu-era captures) — these are per-frame gameplay additions.
4. Cross-check against ULokiCharacterMovementComponent / ULokiAbilitySystemComponent / other
   Loki tick components since the WALL-P work has profiled some of them.

### Task 4 — S190 live probe design (only if Tasks 1-3 don't close offline)

Extend `scratchpad/s187/frame_probe.py` to sample:
- `.data:0x9d29104` value pre-kill and post-kill (one RPM byte read each; discriminates mechanism
  (a) decisively)
- Game-thread stack post-kill (identifies mechanism (c), and if the stack shows a specific Tick
  callee at the frame just below `FEngineLoop::Tick`, discriminates mechanism (b))
- Optional: hook `NtTerminateProcess`-adjacent probes if the companion kill is producing
  observable side effects on any specific `.data` byte within Tick's dominator scope.

Per FK-32 rules (companion-kill produces ~1 injection per staging), the S190 live probe design
should batch every check into ONE armed window rather than iterate.

## Traps and gotchas from prior sessions

Read `docs/method-rules.md` §1 first. New rules banked from S189 that apply directly here:

- **R-S189-a**: A byte-verified GFrameCounter writer site is a FLOOR, not a semantic role.
  Enumerate the complete writer set + match cadence. Same applies to `.data:0x9d29104` — if
  Task 1 finds only one writer, verify there aren't more via a second-instrument cross-check
  (e.g. `movabs r64, imm64` refs to the address itself in addition to RIP-relative disp32).
- **R-S189-b**: A `TArray<TSharedPtr<T>>` + sentinel-index-of--1 singleton identification
  promotes to [M] via .rdata method-name clustering. Same technique applies if S190 finds a
  new singleton-like data structure gating the halt.

Recurring rules that apply:

- **R-S184-a**: `strxref` `.pdata EXACT` at a mid-shape RVA (no prologue) means chained unwind
  region — widen disassembly backward for the real entry. Applied twice this session (found the
  composite helper's real entry at `0x29EF3A0`; found real Tick's chained extent at `0x4028110`).
- **R-S140-T1-c**: A linear disassembly sweep is NOT a CFG. Real Tick's linear sweep would miss
  ~30% of instructions and produce wrong reachability claims. Use recursive descent.
- **R-S140-T1-d**: Enumerating forward branches whose target is >= the call is structurally blind
  to bails that jump BACKWARD. Use backward reachability over the target node.
- **R-S186-a**: Shared-downstream refutes per-subsystem gate. The halt spans AActor +
  UAnimInstance + UUserWidget, which the FPreLoadScreenManager path cannot explain. Whatever
  S190 identifies must be consistent with this multi-subsystem observation.
- **R-S186-d**: For UObject virtuals, vtable qword-scan settles identity in one query. Not
  directly applicable to Task 1-2 (the loop-exit byte is not a virtual) but applies to Task 3
  if any Tick callee turns out to be a virtual with a specific override.

Working directory: `G:\git\Supervive Revival Project`. Branch: `dedicated-server-stub`.
Canonical live-image dump: `dumps/merged14.dump.exe`. ImageBase: `0x7ff608f40000`.

## What NOT to do

- Don't hunt for a gate inside FEngineLoop::Tick — S188 [M] on Init structurally re-confirmed on
  real Tick by S189-caveat2 (1 ret in 1340 blocks, all conditionals diamonds). Refuted.
- Don't hunt for a gate at the FEngineLoop::Tick call site (0x403005A) — S188 [M]: call is
  unconditional in its immediate scope. Any gate at that call must be an OUTER dominator.
- Don't chase the FPreLoadScreenManager path (`0x29F0940` / `0x29F0A30` / composite helper
  `0x29EF3A0`) — S189-caveat2 [M]: irrelevant to the halt, gates a preload-only subsystem.
- Don't hunt for per-subsystem gates (AActor::Tick, UAnimInstance::Tick individually) — R-S186-a
  dispositively refutes.
- Don't spend more than ~30 minutes offline on any single candidate. If Task 1 doesn't narrow
  the writer set decisively OR Task 2's CFG doesn't name a dominant byte-gate OR Task 3's
  blocking-primitive ranking is uninformative, move to Task 4 (live probe design) rather than
  running a 4th offline round.
- Don't relaunch the game unnecessarily. S190 is designed offline-first. The LIVE probe (Task 4)
  should only fire when Tasks 1-3 have narrowed to 2-3 discriminable candidates.

## Success criterion

One line in the S190 evidence doc that reads:

**[M] The halt gate is `<mechanism (a) | (b) | (c)>` at `<specific RVA / .data byte>`. Post-kill,
`<observable state change>` is what triggers it. Refuted candidates: `<list>`.**

If offline can't get there in ~2 hours, land at:

**[I,strong] The halt gate is `<candidate>` per Tasks 1-3 evidence, but requires ONE LIVE probe
`<specific measurement>` to promote to [M]. S190 live probe queued.**

## Session bookkeeping

- Commit as `S190 offline [M/I,strong]: <headline>` following the S181-S189 message shape.
- Every new rule bank as `R-S190-x` in `docs/method-rules.md` §1 tabulated register.
- Preserve any full-marker outputs as `docs/s190-*-live-fullmarker.txt` (the `-fullmarker.txt`
  suffix bypasses `.gitignore`'s `/docs/*-marker.txt` pattern per S181's rename).
- Update `docs/method-rules.md` §1 tabulated register if adding rules — cite the current count
  via the recorded re-derivation command:

    grep -cE '^\| \*\*[^|]*S[0-9]+[A-Za-z0-9]*-[a-z]+\*\*' docs/method-rules.md
