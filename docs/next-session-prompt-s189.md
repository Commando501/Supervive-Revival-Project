# S189 next-session prompt — identify the caller of the 293-byte GFrameCounter helper (offline)

Fresh-session paste-ready opener. Date written: 2026-09-08. Prior session: S188 (see
[docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md](docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md)).

## Paste this as the opening message

Continuing the F10 mystery investigation. The S181–S188 chain has narrowed the mechanism from
"companion-kill halts UE process-wide" to "the gate is at the indirect-dispatch layer that
calls the 293-byte GFrameCounter helper at `SUPERVIVE.exe+0x29EF3D3`". Nine `[M]` commits
on `dedicated-server-stub` (`cd1759c`..`532e5e4`).

Your task: **S189 offline** — identify who calls that 293-byte helper. The helper has 0 rel32
callers in `merged14`'s decrypted `.text`, so its caller is either on a dark page OR uses
indirect dispatch through a `.rdata`/`.data` table. Find the table, name the caller, look for
a companion-liveness gate at that caller.

Purely offline. No live flights this session unless S189 offline fails to name the caller and
you need to move to a live probe (S190).

## Read first, in this order

1. **[docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md](docs/s188-fengineloop-tick-identified-gate-not-inside-settled.md)** — the settled prior. §"Headline" and §"What is now open" are load-bearing.
2. **[docs/s187-gframecounter-halt-frame-pump-settled.md](docs/s187-gframecounter-halt-frame-pump-settled.md)** — the live measurement that motivates the hunt. GFrameCounter freezes post-kill; helper contains the counter increment.
3. **[docs/s186-processevent-stock-halt-upstream-settled.md](docs/s186-processevent-stock-halt-upstream-settled.md)** — rules S186-a (shared-downstream) and S186-c (class-hierarchy control) that dispositively refute per-subsystem gate hypotheses.
4. Skim [docs/s181-companion-kill-halts-reflection-settled.md](docs/s181-companion-kill-halts-reflection-settled.md) for the F10 background.

## What's known [M] going in

- **[M]** `-CompanionWatch`'s runtime.dll companion kill halts UE tick dispatch process-wide (S181).
- **[M]** No thread wedge; all 137 threads in canonical Win32 waits post-kill (S182).
- **[M]** `SUPERVIVE.exe+0x1225F30` = `UObject::CallFunction` (bytecode dispatcher); S184 identified via 5 rel32 callers all in ScriptCore.
- **[M]** All 30 baseline PI dispatches are UE tick + input + widget lifecycle UFunctions (S185); halt-set spans AActor + UAnimInstance + UUserWidget = shared-downstream refutes per-subsystem gate.
- **[M]** `UObject::ProcessEvent` at `SUPERVIVE.exe+0x1344E10` (1665 bytes, 3651 vtable qword refs); stock UE, no gate inside (S186).
- **[M]** `FEngineLoop::Tick` at `SUPERVIVE.exe+0x4027850` (2228 bytes, 1 ret at natural epilogue, no early-exit paths); stock UE, no gate inside (S188).
- **[M]** `GFrameCounter` at `SUPERVIVE.exe+.data:0x9d49138` — advances at 30 Hz baseline, FROZEN post-kill (S187, 35s durability check, 0/1050 predicted counts).
- **[M]** The `inc qword [rip+X]` at `SUPERVIVE.exe+0x29EF4E7` (increments GFrameCounter) lives inside a 293-byte helper at `SUPERVIVE.exe+0x29EF3D3..0x29EF4F8`.
- **[M]** That helper has **ZERO rel32 callers** in `merged14`'s decrypted `.text` — dispatched indirectly.

## The S189 offline task (specific)

Find who calls `0x29EF3D3` (the 293-byte GFrameCounter helper). Try these in order:

### Step 1 — Qword scan of `.rdata` and `.data` for the helper's VA

```python
python -c "
import pefile
p = pefile.PE('dumps/merged14.dump.exe', fast_load=True)
p.parse_data_directories()
target = 0x29EF3D3
tgt_va = p.OPTIONAL_HEADER.ImageBase + target
qw = tgt_va.to_bytes(8, 'little')
for sect in p.sections:
    name = sect.Name.decode('ascii', errors='replace').rstrip('\x00')
    if name not in ('.rdata', '.data'): continue
    data = sect.get_data()
    idx = 0; hits = []
    while True:
        i = data.find(qw, idx)
        if i < 0: break
        hits.append(sect.VirtualAddress + i); idx = i + 1
    print(f'{name}: {len(hits)} qword refs to helper: {[hex(h) for h in hits[:20]]}')
"
```

**If it finds 1-few hits**: those RVAs are where the helper's pointer is stored (delegate slot,
vtable, ticker table). Read the 8 bytes at each hit, then find who READS that qword and CALLS it
via `call [rip+X]`. That's the caller.

**If it finds many hits (>20)**: the helper is a vtable entry on many classes (unlikely for
GFrameCounter-adjacent code, but possible for FTickableGameObject).

**If it finds 0 hits**: the helper's caller is on a dark `.text` page. Proceed to Step 2.

### Step 2 — If qword scan finds 0 hits: look at the helper's OWN code for its context

Re-disassemble the 293-byte helper at `0x29EF3D3`. Its body walks an array (`mov rdi, [rax+rcx*8]`),
calls a virtual on each element (`call [rdi_vt+0x18]`), reads/writes `[rbx+0x48]` (double time),
manages a refcount at `[rbx+8]`, and increments GFrameCounter at `0x29EF4E7`. That's textbook
`FCoreTicker::Tick` or `FTickableGameObject::TickAllTickables`.

- Search `.rdata` for the strings `"FTicker"`, `"FCoreTicker"`, `"FTickableGameObject"`,
  `"TickAllTickables"`, `"FCoreDelegates"`. Find LEA sites for each; the containing functions
  are candidates for the helper OR its caller. Cross-check by disassembling.
- The 293-byte helper's `[rbx+0x48]` and `[rbx+8]` refcount pattern strongly suggests it's an
  FTickable manager tick method. FTickableGameObject's manager has a static array of registered
  tickables — look for that array's base address in `.data`.

### Step 3 — Cross-check via strxref for the helper's containing function

```bash
python tools/strxref/strxref.py --dump dumps/merged14.dump.exe func 0x29EF3D3
```

Currently reports 0 string references in the extent. Widen backward per **R-S184-a** (chained
unwind regions) — the true function entry may be earlier than 0x29EF3D3.

### Step 4 — If offline is exhausted, prepare the S190 live probe

Fallback plan (LIVE, requires launch): extend `scratchpad/s187/frame_probe.py` to ALSO sample:
- The tickable-object array's count field (if identified in Step 2/3)
- The helper's dispatch-slot function pointer (if identified in Step 1)

Sample pre-F9 vs post-F9. Whichever changes IS the mechanism (M1 = array shrinks; M2 = pointer
cleared; M3 = neither changes → dark caller has the gate).

## Traps and gotchas from prior sessions

Read `docs/method-rules.md` §1 first if you haven't. Specific ones that recur:

- **R-S184-a**: `strxref` `.pdata EXACT` at a mid-shape RVA (no prologue) means chained unwind
  region — widen disassembly ~0x100 bytes backward for the real entry. This is how I found
  FEngineLoop::Tick (0x4028085 was the .pdata entry; real entry was ~0x800 bytes back at
  0x4027850).
- **R-S186-d**: For UObject virtuals, do the vtable qword-scan FIRST (one query settles identity)
  before disassembling for behavioral evidence. FEngineLoop::Tick isn't a virtual, so this
  doesn't directly apply — but the analogous move for tick helpers is: search `.data`/`.rdata`
  for the helper's VA before assuming rel32 callers are the only path.
- **S188-b**: 0 rel32 callers ≠ dead code. The helper is provably called (GFrameCounter
  advances 30 Hz baseline). Assume indirect dispatch and hunt for the storage site.
- Working directory: `G:\git\Supervive Revival Project`. Branch: `dedicated-server-stub`.
  Bash tool cwd persists between commands; PowerShell tool cwd does not. Use absolute paths
  in shell commands to be safe.
- The canonical live-image dump is `dumps/merged14.dump.exe` (55.53% .text coverage). ~45% of
  `.text` is still dark; if the helper's caller lives on a dark page, it's invisible to any
  rel32 scan against merged14.

## What NOT to do

- Don't hunt for a `cmp byte [rip+X]; je epilogue` gate inside `FEngineLoop::Tick` — S188
  ruled that out [M] with only-1-ret evidence. Waste of tokens.
- Don't hunt for a gate inside `UObject::ProcessEvent` — S186 ruled that out [M] with
  3651 vtable slots + no inline gate. Waste of tokens.
- Don't hunt for per-subsystem gates (AActor::Tick / UActorComponent::Tick / UUserWidget::Tick
  independently) — R-S186-a and R-S186-c dispositively refute those. The halt-set spans
  four unrelated native subsystems whose only shared upstream is UE's frame pump.
- Don't spend more than ~30 minutes of exploration on any single candidate. If Step 1 finds
  0 hits and Step 2's string search finds nothing decisive, move to S190 live.
- Don't relaunch the game unnecessarily. S189 is designed offline-only. If you have to go
  live, S190's scope is a lightweight RPM sampling probe — not a shim rebuild + injection.

## Success criterion

One line in the S189 evidence doc that reads:

**[M] The 293-byte helper at 0x29EF3D3 is called from `<function name>` at RVA
`<RVA>`, via `<direct rel32 / vtable slot / delegate registration>`. The
companion-liveness gate lives at `<specific RVA>`, and the state it reads is
at `.data:<RVA>`.**

If the offline hunt can't get there in ~30 min, land at:

**[I,strong] The helper's caller lives on a dark `.text` page and cannot be identified
offline. Preparing S190 live probe (extends frame_probe.py to sample the helper's
tickable-array + dispatch-slot) — expected outcome: one live A/B/C sitting names
the changed field.**

## Session bookkeeping

- Commit as `S189 offline [M/I,strong]: <headline>` following the S181-S188 message shape.
- Every new rule bank as `R-S189-x` in the settled doc.
- Preserve any full-marker outputs as `docs/s189-*-live-fullmarker.txt` (the `-fullmarker.txt`
  suffix bypasses `.gitignore`'s `/docs/*-marker.txt` pattern per S181's rename).
- Update `docs/method-rules.md` §1 tabulated register if adding rules — cite the current
  count via the recorded re-derivation command.
