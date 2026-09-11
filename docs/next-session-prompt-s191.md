# S191 next-session prompt — live probe: byte + guard + thread-stack sample to close the halt-gate mechanism

Fresh-session paste-ready opener. Date written: 2026-09-08. Prior sessions: S190 offline halt-gate
hunt (settled + committed). Ten `[M]` commits on `dedicated-server-stub` (`cd1759c`..most-recent)
including S189 pair, S190 pair.

## Paste this as the opening message

Continuing the F10 mystery investigation. S190 offline REFUTED [M] mechanism (a) as originally
framed (byte-flip → clean termination not freeze) and identified a concrete [I,strong] mechanism
(b) candidate: MSVC `_Init_thread_header` at RVA `0x751E240` is called 4× directly from Tick,
uses a SHARED SRW at `.data:0x764A488`, and any dying thread mid-critical-section leaks the SRW
and hangs the game thread's next `_Init_thread_header` call forever. Two other candidates
survive: (a-alt) shutdown-chain callee blocks after loop exit, (c) game thread suspended before
Tick re-entry.

Your task: **S191 LIVE PROBE** — ~15-30 seconds against a wedged post-companion-kill process,
3 steps, pre-registered discriminator table with 7 outcomes. Closes the mechanism question
decisively.

## Read first, in this order

1. **[docs/s190-halt-gate-hunt-settled.md](docs/s190-halt-gate-hunt-settled.md)** — the direct
   prior; §"Live probe design (S191)" and §"Discriminator table" are the load-bearing sections.
2. **[docs/s189-caveat2-second-gfc-site-settled.md](docs/s189-caveat2-second-gfc-site-settled.md)**
   — S189's re-attribution of the 30 Hz driver + refutation of the FPreLoadScreenManager gate
   hypothesis.
3. **[docs/s189-caller-hunt-settled.md](docs/s189-caller-hunt-settled.md)** — the caller chain
   map + FPreLoadScreenManager identification.
4. **[docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md](docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md)**
   — S188 settled prior; note that its function-labeling was corrected by S189 (Init at 0x4027850
   vs real Tick at 0x4028110) but the structural "1 ret + no early-exits" claim survives on
   real Tick.
5. **[docs/s187-gframecounter-halt-frame-pump-settled.md](docs/s187-gframecounter-halt-frame-pump-settled.md)**
   — the original live measurement (GFrameCounter frozen post-kill).
6. Skim [docs/s181-companion-kill-halts-reflection-settled.md](docs/s181-companion-kill-halts-reflection-settled.md)
   for the F10 background and CompanionWatch's kill primitive.

## Known [M] going in

- **[M]** Real FEngineLoop::Tick sits at `0x4028110`, ~5.7 KiB across 15-16 chained pdata rows
  through `0x4029797`. 1 ret in entire body, all conditional branches diamonds. (S189-caveat2)
- **[M]** Site 3 (`0x4029349-0x4029353`) is the 30 Hz GFrameCounter driver — fires unconditionally
  per Tick invocation IF Tick runs. Fell to a workflow with 4 converging lanes.
- **[M]** Mechanism (a) REFUTED: `.data:0x9d29104` is `GIsRequestingExit`; flipping it causes
  clean termination via loop exit → cleanup → WinMain → ExitProcess. NOT freeze. (S190 Lane B)
- **[I,strong]** MSVC `_Init_thread_header` at `0x751E240` is called 4× from Tick with
  `SleepConditionVariableSRW(shared_srw, shared_cv, INFINITE, 0)` at `0x751E275` when guard reads
  `-1`. Shared SRW at `.data:0x764A488` is a leak-hazard candidate. (S190 Lane D)
- **[M]** The 4 Tick static-init guards are at `.data:0x9FC06F8`, `0x9FC0720`, `0x9FC0730`,
  `0x9FC0740` (0x48-byte cluster). Each has 1 header caller + 1 footer caller, both inside Tick.
  Guards read positive/initialized values in menu-era merged14. (S190 offline follow-up)
- **[M]** 9,448 total `_Init_thread_header` callers image-wide, 8,624 distinct guards. Any dying
  thread inside any of the 9,448 callers is a potential SRW-leak trigger.

## The S191 live-probe recipe

### Step 1 (~1s, pure RPM, no injection): byte + guard read

```python
import ctypes, ctypes.wintypes as w

PROCESS_VM_READ = 0x10
kernel32 = ctypes.windll.kernel32
OpenProcess = kernel32.OpenProcess; OpenProcess.restype = w.HANDLE
RPM = kernel32.ReadProcessMemory

pid = 0xNNNN  # discover via Get-Process or the S189-caveat2 marker file
base = 0x7ff608f40000  # SUPERVIVE ImageBase — verify via VirtualQueryEx on process

hProc = OpenProcess(PROCESS_VM_READ, False, pid)

def read(addr, n):
    buf = (ctypes.c_ubyte * n)()
    read_n = ctypes.c_size_t()
    RPM(hProc, ctypes.c_void_p(addr), buf, n, ctypes.byref(read_n))
    return bytes(buf[:read_n.value])

b1 = read(base + 0x9D29104, 1)[0]   # GIsRequestingExit
b2 = read(base + 0x9D28B18, 1)[0]   # HARD-DOWN gate

# Tick's 4 static-init guards
guards = {}
for name, rva in [('T0', 0x9FC0740), ('T1', 0x9FC06F8), ('T2', 0x9FC0720), ('T3', 0x9FC0730)]:
    val = int.from_bytes(read(base + rva, 4), 'little', signed=True)
    guards[name] = val

# Shared SRW state
srw = int.from_bytes(read(base + 0x764A488, 8), 'little')
# (SRW format: bit 0 = locked, higher bits = wait queue head or shared count)

print(f'GIsRequestingExit: {b1}   HARD-DOWN: {b2}')
print(f'Guards: {guards}')
print(f'Shared SRW at 0x764A488: {hex(srw)}')
```

Interpretation:
- `b1 == 1` → **mechanism (a-alt)**: loop exited cleanly, some cleanup callee blocks. Proceed to step 2 to identify which.
- `b1 == 0 AND any guard == -1 (0xFFFFFFFF)` → the game thread is blocked inside `_Init_thread_header` on that specific guard. Very unlikely per S190 offline (only Tick body calls them), but a striking positive result if it happens.
- `srw != 0` → SRW is currently held. Combined with a game-thread stack in `AcquireSRWLockExclusive`, this is **mechanism (b) [M]**.
- `b2 == 1 AND process alive` → HARD-DOWN gate flipped externally (0 in-.text writers per S190 Lane A). Novel external injection surface — separate investigation.

### Step 2 (~5s): thread stack sample on the game thread

```python
import ctypes.wintypes as w
THREAD_ALL_ACCESS = 0x1F03FF
CONTEXT_FULL = 0x100007

kernel32 = ctypes.windll.kernel32
OpenThread = kernel32.OpenThread
SuspendThread = kernel32.SuspendThread
ResumeThread = kernel32.ResumeThread
GetThreadContext = kernel32.GetThreadContext

# Identify the game thread. Options:
# (a) Read from S182 baseline (if a TID mapping was preserved)
# (b) Enumerate all threads with CreateToolhelp32Snapshot + Thread32First/Next,
#     GetThreadContext on each, and pick the one whose RIP lies in FEngineLoop scope
#     (Tick 0x4028110..0x4029797, or GuardedMain 0x402FD90..0x40300B9)
# (c) The one blocked in _Init_thread_header (RIP in 0x751E240..0x751E290)

game_tid = discover_game_thread(hProc)
hThread = OpenThread(THREAD_ALL_ACCESS, False, game_tid)
SuspendThread(hThread)
ctx = get_context_full(hThread)  # struct CONTEXT (arch-dependent)
print(f'RIP: {hex(ctx.Rip)}   RBP: {hex(ctx.Rbp)}   RSP: {hex(ctx.Rsp)}   RCX: {hex(ctx.Rcx)}')

# Walk the stack ~30 frames — StackWalk64 or manual RBP unwind
frames = stack_walk(hProc, hThread, ctx)
for f in frames:
    print(f'  {hex(f.rip)}')

ResumeThread(hThread)
```

Discriminator lookup on `RIP` (from S190 §"Discriminator table"):
- `0x751E240..0x751E290` (or SleepConditionVariableSRW body): **mechanism (b) [M]** — game thread blocked in `_Init_thread_header`.
  - Check `rcx` — it holds the guard address. If it's one of the 4 Tick guards, that's the specific site.
  - Combined with a positive step-1 SRW-held observation, mechanism attribution is complete.
- `0x2B7FD50..0x2B7FF41` or slow-path `0xF95730` / `0xF9C930`: **mechanism (b-alt) [M]** — per-object CS deadlock (Lane C rank #1).
- `0x402F470..0x402F8CA` (AppPreExit-shaped, HotReload / AssetRegistry / etc.): **mechanism (a-alt) [M]** — cleanup-chain block. `b1==1` should confirm.
- `0x4017380..0x4017491`: **mechanism (a-alt) via DARK-page callee** — worth decrypting via `dumpimage` on the wedged process.
- `0x40396C3..0x403972F`: **mechanism (a-alt) via WinMain-cleanup**.
- `SleepConditionVariableSRW` / `WaitForSingleObject` with NO Tick frame on stack: **mechanism (c) [M]** — game thread suspended before Tick re-entry.
- `0x402935A..0x4029797` (past Site 3 in Tick tail): would **REFUTE S189-caveat2's Site-3-unconditional claim** — check GFrameCounter parity against pre-kill baseline.

### Step 3 (~10s, conditional): lock/handle census

If step 2 shows RIP in `SleepConditionVariableSRW`:
- Read the SRWLOCK at `ctx.Rcx` (or wherever the SRW arg was passed — trace back one stack frame)
- Read the CONDITION_VARIABLE at `ctx.Rdx`
- These structures are opaque but their bit 0 (locked) is meaningful

If step 2 shows RIP in `0x2B7FD50` chain:
- Read `byte [ctx.Rsi + 0x28]` — should be non-zero if lock held
- Dump 8 qwords starting at `ctx.Rsi` for object vtable ID

If step 2 shows AppPreExit chain (`0x402F470` etc.):
- Decode which specific block is running via inspecting stack return addresses
- Purely offline follow-up next session: recursive-descent CFG of `0x402F470` for blocking primitives

### Optional: `dumpimage` on the wedged process (S118 side-effect trick)

Before killing the wedged process, run `usmapdump dumpimage` to snapshot its live-decrypted
image. This may include the currently-DARK cleanup page `0x4017380` (only decrypted when the
graceful-shutdown path fires), giving the offline follow-ups on mechanism (a-alt) a starting
point.

## The wedge trigger

The wedge is reproduced by `-CompanionWatch` firing its kill primitive. Per S181, this happens
during a `configs/companion-watch.ps1` run. Standard preparation:

1. Launch the game via `configs/launch-redirect.ps1` and stage a match to the point where the
   companion is active (per S181's recipe).
2. Trigger companion kill via `-CompanionWatch`'s script (or wait for the natural kill event).
3. Confirm freeze by tailing `Loki.log` for GFrameCounter progression (should stop advancing).
4. Run the S191 probe against the wedged process while it's alive.
5. Save all probe output as `docs/s191-probe-fullmarker.txt` (the `-fullmarker.txt` suffix
   bypasses `.gitignore`'s `/docs/*-marker.txt` pattern per S181's convention).

## Success criterion

One line in the S191 evidence doc that reads:

**[M] The halt gate is mechanism `<(a-alt) | (b) | (b-variant) | (b-alt) | (c)>` at
`<specific RVA / .data byte>`. Post-kill state:
`<b1=X, b2=Y, guards=[G0,G1,G2,G3], SRW=S, thread RIP=R>`. Refuted candidates: `<list>`.**

If the probe hits an unclassified outcome (RIP in Tick tail past Site 3, or a stack pattern not
in the discriminator table), land at:

**[I,strong] Probe returned `<observation>`, which doesn't map to any of the 7 pre-registered
outcomes. New candidate mechanism: `<hypothesis>`. Next: `<offline follow-up>`.**

## What NOT to do

- **Don't run the probe on a HEALTHY (non-wedged) process.** The probe is designed to
  discriminate wedge causes; on a healthy process it will show normal advancing values and
  the RIP will be wherever Tick happens to be executing — useless for the question.
- **Don't inject anything into the wedged process.** Pure RPM only. `OpenProcess(PROCESS_VM_READ)`
  and `OpenThread(THREAD_ALL_ACCESS)`. No `VirtualAllocEx`/`WriteProcessMemory`.
- **Don't kill the wedged process before dumping.** Consider running `usmapdump dumpimage` first
  to capture live-decrypted `.text` for the S190 follow-ups.
- **Don't spend more than one probe run per session** unless the discriminator table's
  interpretation guide clearly says "iterate" — the wedge state may not be stable across long
  probe intervals if the protector kills the process on integrity-check trigger.
- **Don't skip Step 1.** If `b1==1`, the mechanism is (a-alt) and step 2's thread stack tells
  you WHICH cleanup callee blocks — this is a fast-path narrowing.
- **Don't try to modify the SRW state.** SRWs are opaque; writing to them from RPM will corrupt
  the process. Read-only.

## Traps and gotchas

Read `docs/method-rules.md` §1 first. Newly banked rules that apply directly here:

- **R-S190-a**: byte-pattern shape scans must include `imm_len` in `rip_after`. If you extend the
  S190 offline scan for more shutdown-byte writers, use this rule.
- **R-S190-b**: MSVC `_Init_thread_header` uses SHARED globals (SRW + CondVar) — a dying thread
  can leak them regardless of which guard it targeted. This is the primary mechanism (b)
  hypothesis and what step 3's SRW read directly tests.

Recurring rules:
- **R-S184-a**: `strxref .pdata EXACT` at a mid-shape RVA means chained unwind — widen backward.
- **R-S140-T1-c**: linear disassembly is not a CFG. Recursive descent only.
- **R-S186-a**: shared-downstream refutes per-subsystem gates. Mechanism (b) via shared SRW is
  EXACTLY the shared-upstream mechanism that satisfies R-S186-a.

Working directory: `G:\git\Supervive Revival Project`. Branch: `dedicated-server-stub`.
Canonical live-image dump: `dumps/merged14.dump.exe`. ImageBase: `0x7ff608f40000`.

## Session bookkeeping

- Commit as `S191 live [M/I,strong]: <headline>` following the S181-S190 message shape.
- Every new rule bank as `R-S191-x` in `docs/method-rules.md` §1 tabulated register.
- Preserve full probe output as `docs/s191-probe-fullmarker.txt` (bypasses `.gitignore`).
- Update the `docs/method-rules.md` §1 tally count via the recorded re-derivation command:

    grep -cE '^\| \*\*[^|]*S[0-9]+[A-Za-z0-9]*-[a-z]+\*\*' docs/method-rules.md
