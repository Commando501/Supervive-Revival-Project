# S189-caveat2 — the primary 30 Hz GFrameCounter driver is `0x4029353` inside real FEngineLoop::Tick, NOT the 293-byte helper [M]

**Offline 2026-09-08**, disassembly against `dumps/merged14.dump.exe`, zero live flights.
Multi-agent workflow `wf_eeaf0460-b51` — 4 parallel investigation lanes + 1 adjudicator, 5/5 done,
0 errors, ~1.86M subagent tokens.

> **Companion doc**: [docs/s189-caller-hunt-settled.md](s189-caller-hunt-settled.md) — the primary
> caller-chain map + FPreLoadScreenManager identification. Read that first; this doc is the
> follow-up that resolves which of two GFrameCounter++ sites is the per-frame gameplay driver.

## Headline

★★★★★★★ **[M] Caveat-2 is CONFIRMED.** All four analysis lanes converge byte-for-byte, zero
cross-lane disagreements:

- **Primary 30 Hz driver = the inline site at `0x4029349-0x4029353`** inside real
  FEngineLoop::Tick's end-of-frame chained extent (row `0x4029312..0x40295D2`).
- **The 293-byte helper at `0x29EF3D3` is FPreLoadScreenManager per-tick advance** —
  subsystem-conditional, does NOT fire per gameplay frame.
- **S189's [M] gate attribution to `0x29F0940` / `0x29F0A30` is IRRELEVANT to the S187
  post-companion-kill freeze.** Both gates guard the FPreLoadScreenManager path only;
  during gameplay both return FALSE every frame regardless of companion state.
- **The real halt gate lives UPSTREAM of FEngineLoop::Tick** — in the GuardedMain-like caller
  chain at `0x402FD90` / `0x403005A`, or in a Tick callee that blocks the game thread
  indefinitely. **S190's task.**

★★★★★★ **Consequences**:
- S186/S187/S188 findings are all preserved: "halt is upstream of Tick" was already the
  trajectory (S186 [M+I,strong], S188 [M]). Only S189's initial [M] attribution to the
  FPreLoadScreenManager predicates needed correction.
- R-S186-a **independently refutes** the S189 gate attribution: a shared-downstream halt of
  AActor + UAnimInstance + UUserWidget cannot be explained by FPreLoadScreenManager freezing,
  because FPreLoadScreenManager isn't in any of those subsystems' downstream. Doubly refuted.
- S190 redirects from "instrument the FPreLoadScreenManager helper's dispatch chain" to
  "instrument the GuardedMain-like caller chain + the shutdown byte at `.data:0x9d29104` +
  the Tick-callee-blocking hypothesis".

## The four converging lanes

### Lane A — byte-verified the inline site's identity and pdata containment [M]

The bytes at `0x4029349-0x4029353`:

```
0x4029349  48 8b 1d e8 fd d1 05    mov rbx, [rip+0x5d1fde8]   ; LOAD GFrameCounter
0x4029350  48 ff c3                inc rbx                     ; increment
0x4029353  48 89 1d de fd d1 05    mov [rip+0x5d1fdde], rbx    ; STORE GFrameCounter
```

Both disp32 operands resolve **exactly** to RVA `0x9d49138` (arithmetic double-checked, matches
GFrameCounter's known address).

Pdata row containing the site: **`0x4029312..0x40295D2` (704 B, EXACT via minidump stream 13,
seen in 76 of 76 dumps).** Unwind `0x96F42A8` has flags=`0x4` (`UNW_FLAG_CHAININFO`), parent
chain: `0x4029312 → 0x402813A → 0x4028136 → 0x4028110 ROOT` (real FEngineLoop::Tick, flags=`0x3`
`EHANDLER + UHANDLER`).

The row contains string LEAs at `0x40293D8 → "FrameCounter"` (utf16 at .rdata:0x81E5748) and
`0x4029507 → "EndFrame"` (utf16 at .rdata:0x7FA9A90) — canonical
`ENQUEUE_RENDER_COMMAND(FrameCounter)` / `ENQUEUE_RENDER_COMMAND(EndFrame)` idiom for UE's
end-of-frame block.

Row entry `0x4029312` is reached via **fallthrough NOT-TAKEN** of `jg 0x4029639` at
`0x402930C` in the prior chained row `0x4029242..0x4029312` (which is also inside real Tick).
The `jg` target is one of the four MSVC `_Init_thread` dispatches (see Lane B) that jmp back
to the main flow.

Also detected: linear-sweep false-positives at `0x402934A` and `0x4029354` (offset-by-1 `mov ebx`
shadows of the REX.W-prefixed 7-byte instruction). Correctly excluded from the reachable set by
recursive-descent CFG (R-S140-T1-c applied).

### Lane B — recursive-descent CFG proved unconditional reach + refuted the "early-exit candidate" [M]

Recursive-descent CFG over real FEngineLoop::Tick (`0x4028110..0x4029797`, 16 chained pdata
regions covering ~5.7 KiB total). Stats:

- **1340 instructions decoded**, 0 decode errors, 1340 basic blocks
- **1 ret** in the entire function (at the natural epilogue) — same structural property S188
  measured on Init, now confirmed on the correct Tick function
- **133 conditional branches on the dominator chain** to target `0x4029349`, **every one is a
  diamond** (both taken and fall-through paths converge back onto the path to target)
- **0 real gates** — no branch has a successor that fails to reach target
- **1177 predecessor nodes** on backward reachability from target

The four apparent "early-exit branches" (`jg` to `0x402967c`, `0x40296eb`, `0x402972d`, `0x4029639`)
are **all MSVC `_Init_thread_header/_Init_thread_footer` one-time thread-safe static-local
initializer dispatches**. Their targets sit in the chained continuation `0x4029639..0x4029797`,
do initializer work, then `jmp` back into the main flow (`0x4029312` / `0x40287f0` / `0x402927b`
/ `0x402928b`). Both the fast path (init already done, `jg` not taken) and the slow path (init
needed, `jg` taken, run initializer, `jmp` back) reach target.

**S189 Lane D's cited "early-exit candidate" at `0x402817A` is REFUTED as a gate**:
- `0x402817A: cmp byte [rip+0x5f26d59], 0` (byte at .data:`0x9f4eeda`)
- `0x4028181: jne 0x4028192`
- **Both fall-through (`0x4028183`) and jne-target (`0x4028192`) reach TARGET.** The `jne` merely
  skips 15 bytes of setup code; both paths merge at `0x4028192`. The byte is part of an init-flag
  cluster (`0x9f4eed9` / `0x9f4eedc` tested elsewhere on the same path), not a gate for TARGET.

Two dominating READS of GFrameCounter itself exist on the dominator chain, both as diamonds:
- `0x4028234`: `cmp qword [rip+0x5d20f1d], rax` → 0x9d49138 = GFrameCounter (first read; startup /
  initial-frame check)
- `0x4029240`: `cmp qword [rip+0x5d1ff0a], 5` → 0x9d49138 (second read; "first-5-frames-are-special"
  bootstrap pattern per stock UE)

Both diamonds; both branches reach TARGET.

**External-caller scan of the entire 118 MB `.text`**: exactly **1 external CALL into the
`0x4028110..0x40295D2` span**, at `0x403005A` inside a GuardedMain-like main loop with the shape
`while(!byte[.data:0x9d29104]) Tick()`. That is the canonical UE `while (!GIsRequestingExit)
FEngineLoop::Tick()` idiom.

### Lane C — [M] FPreLoadScreenManager identification via 7 independent instruments

Full details in [the companion doc](s189-caller-hunt-settled.md) §"FPreLoadScreenManager
identification". Summary:

- 6 `FPreLoadScreenManager::*` method-name strings clustered at .rdata:`0x7BB4120..0x7BB4245`
- Constructor mallocs exactly `0xA8` bytes = stock UE sizeof(FPreLoadScreenManager)
- `[obj+0x40] = 0xFFFFFFFF` = `ActivePreLoadScreenIndex = -1` sentinel
- `[obj+0x10] = 2` and `[obj+0x28] = 2` = `EPreLoadScreenTypes::EngineLoadingScreen` type-tag
- `[+0x30]/[+0x38]/[+0x40]` = `TArray<TSharedPtr<IPreLoadScreen>>` Data/Num/Index
- Destructor iterates same array calling `[vt+0x48]` (IPreLoadScreen::CleanUp)
- FPreLoadScreenSlateSynchMechanism-shaped spinlock teardown

**Predicates**:
- `0x29F0940` (inner, 75 B): walks ONE entry at `[singleton+0x40]` index, calls `[vt+0x50]`,
  compares to `dl`, returns bool.
- `0x29F0A30` (outer, chained 46+57+25 = 128 B): walks the WHOLE `PreLoadScreens[]` array, calls
  `[vt+0x50]` on each entry, compares to `dl`, returns bool (true iff any entry matches).

**`[vt+0x50]` semantics** [I,strong]: `IPreLoadScreen::GetPreLoadScreenType() const` returning
`EPreLoadScreenTypes` as uint8. `dl=2` at the Tick call site matches
`EPreLoadScreenTypes::EngineLoadingScreen = 2` (stock UE enum: `CustomSplashScreen=0`,
`EarlyStartupScreen=1`, `EngineLoadingScreen=2`, `Manual=3`). Not promoted to [M] because the
exact slot layout on IPreLoadScreen's vtable wasn't walked from a concrete derived class in
`.rdata`; this qualification does not affect the verdict.

**During gameplay**: FPreLoadScreenManager is either destroyed (stock UE calls
`FPreLoadScreenManager::Cleanup()` after `WaitForEngineLoadingScreenToFinish`; the singleton at
`.data:0x9F327E0` reads NULL in the menu-era merged14 snapshot, consistent) OR no
`EngineLoadingScreen`-type IPreLoadScreen is registered in `PreLoadScreens[]` (that screen type
is specifically for the pre-map-load window). Either way, outer predicate `0x29F0A30` returns
FALSE and the composite helper does not execute.

### Lane D — writer census + cadence reconciliation [M/I,strong]

Complete GFrameCounter writer enumeration (independent verification, matches the S189-primary
census byte-for-byte):

| # | site RVA | containing function | classification | grade |
|---|---|---|---|---|
| 1 | `0x29EF4E7` | composite helper `0x29EF3A0` (FPreLoadScreenManager) | subsystem-conditional; NOT per-frame in gameplay steady state | [I,strong] |
| 2 | `0x3EDE826` | `0x3EDE7F0..0x3EDE9A2` (HighResScreenshot path) | on-demand (screenshot capture); NOT per-frame | [M] |
| 3 | **`0x4029353`** | **`0x4029312..0x40295D2` (real FEngineLoop::Tick end-of-frame block)** | **PER-FRAME — the ~30 Hz driver** | **[M]** |
| 4 | `0x48F06A9` | `0x48F0680..0x48F06CE` (78 B) | statically unreached (0 rel32 callers, 0 qword pointers, 0 movabs refs); scratch-buffer use | [M] |
| 5 | `0x48F06C1` | same 78 B function as #4 | scratch-buffer restore (pairs with #4) | [M] |

Sites 4+5 form a save→clobber-with-int32-return-from-indirect-call→spin-while-equal→restore
pattern that temporarily uses GFrameCounter's storage location as a scratch buffer. Statically
unreachable — either dead code or reached via a mechanism no static analysis can see (TLS callback
/ exception filter / runtime-generated jump). Not a per-frame driver either way.

**Cadence math**: If both Site 1 (helper) AND Site 3 (inline) fired once per frame in steady
state, GFrameCounter would advance at 2× FPS Hz. S187 measured ~30 Hz baseline (30 predicted
counts × 35 s = 1050, 0 observed post-kill). Menu FPS in this build is 30–60 (v-synced menu is
typically 30). **30 Hz counter × 1 increment/frame at 30 FPS matches Site 3 alone.** 30 Hz counter
× 2 increments/frame would require 15 FPS, unusually low for menu, and no 60 Hz counter
observation is on record. ⇒ **[I,strong] Site 3 alone accounts for the 30 Hz baseline.**

Correction to the S189-primary handoff estimate: **real Tick chained extent is ~5.7 KiB across
15 contiguous pdata rows (`0x4028085..0x4029797`), NOT the ~4402 B first stated.** The extent
INCLUDES row `0x4029312..0x40295D2` where Site 3 lives, plus additional continuations at
`0x40295D2` / `0x40295F5` / `0x402960A` / `0x4029639` / `0x402967C` / `0x40296EB` / `0x4029797`.

### Adjudicator — [M] SECOND-SITE-IS-DRIVER, caveat-2 confirmed

Zero cross-lane disagreements. Two minor clarifications (not contradictions):
- Lane B initially cited a string LEA at `0x40293D8 → 0x81E5748` as "FPreLoadScreenManager::Get()"
  but Lane C's `.rdata` cluster analysis identifies it as one of the `FPreLoadScreenManager::*`
  method names — irrelevant to either verdict.
- Lane A cites the LEA at +0xC6 → `"FrameCounter"` as an FScopedNamedEvent scope name; Lane D
  cites it as `ENQUEUE_RENDER_COMMAND(FrameCounter)`. Both readings are consistent with UE's
  FScopedNamedEvent-plus-render-command idiom; no contradiction.

## What this means for the halt gate hunt

The S189-primary [M] gate localization to `0x29F0940` / `0x29F0A30` is **CORRECTLY IDENTIFIED as
the gate for the FPreLoadScreenManager helper**, but it is **IRRELEVANT to the S187 post-companion-
kill freeze phenomenon**. During gameplay both gates return FALSE every frame regardless of
companion state — the freeze cannot be attributed to them.

The real gate must satisfy all of:
1. Consistent with S186 [M+I,strong]: halt is UPSTREAM of `UObject::ProcessEvent`.
2. Consistent with S186 R-S186-a: halt spans AActor + UAnimInstance + UUserWidget (shared
   downstream = UE frame pump).
3. Consistent with S187 [M]: GFrameCounter (advanced by Site 3 inside Tick) is frozen post-kill.
4. Consistent with S188 [M]: halt gate is NOT inside FEngineLoop::Tick body (correctly measured
   on Init, structurally re-confirmed on the correct Tick function here — 1 ret in 1340 blocks,
   all conditionals diamonds).
5. Consistent with Lane B [M]: Site 3 fires UNCONDITIONALLY per Tick call.

Together, (3) + (4) + (5) imply: **Tick is not being CALLED post-kill.** Not "Tick runs and
skips Site 3" (impossible per Lane B) and not "Tick runs to completion but its callees do
nothing observable" (Site 3 IS in Tick's body, would run). Something upstream of the Tick call
at `0x403005A` is preventing the next iteration of GuardedMain's while-loop.

**Three candidates for that upstream gate**, all offline-decidable except (b) which needs live
measurement:

**(a) The shutdown byte at `.data:0x9d29104` flips non-zero post-companion-kill.** The
GuardedMain-like loop at `0x402FD90..0x40300B9` tests `while(!byte[0x9d29104]) Tick()`; if the
byte flips, the loop exits and the process would presumably continue past the tick loop into
FEngineLoop::Exit. Testable OFFLINE by (i) enumerating every writer of `.data:0x9d29104` in the
image, and (ii) determining whether any of them lie on a companion-kill-triggered code path.

**(b) A Tick callee never returns and blocks the game thread indefinitely.** Tick has ~148 direct
calls in its body. Blocking primitives (`WaitForSingleObject`, `EnterCriticalSection`,
spin-loops on volatile state) reachable from any of them would produce the observed freeze
without exiting the loop. Testable OFFLINE by enumeration; requires LIVE probe to confirm which
callee is blocked at the moment of freeze (thread stack sample).

**(c) The game thread itself is blocked / sleeping / deadlocked BEFORE re-entering GuardedMain's
next iteration.** Requires LIVE probe (thread stack sample post-kill). S182 [M] already showed
137 threads in canonical Win32 waits post-kill; a game-thread wait for a mutex/event held by a
killed thread would fit.

## Rules banked (new)

### R-S189-a: A byte-verified GFrameCounter writer site is a FLOOR, not a semantic role. Always enumerate the complete writer set AND match cadence against measured counter frequency before attributing "the driver" to any one site.

Applied here: S189 caveat (2) was surfaced because Lane B of the primary hunt happened to notice
a second writer at `0x4029353` inline in Tick's chain. Neither S187 (which measured GFrameCounter
freeze) nor the S189-primary attribution (helper at `0x29EF4E7`) enumerated ALL 5 writer sites
first. Had they, the FPreLoadScreenManager helper's subsystem-conditional role would have been
obvious immediately from the cadence mismatch (2 per-frame writers → counter at 2× FPS, refuted
by S187's 30 Hz baseline).

**The check is one strxref query + a linear disp32 scan of `.text` for the target VA.** Under
10 minutes offline. Do it BEFORE ranking any single site as "the driver" for a global counter.

### R-S189-b: A `TArray<TSharedPtr<T>>` + sentinel-index-of-`-1` singleton shape identification promotes from [I,strong] to [M] via .rdata method-name-string clustering near the singleton's constructor.

Applied here: Lane D of the S189-primary hunt inferred the composite helper matched
`FTicker`/`FCoreDelegates` shape from `TArray<TFunction*>` iteration + `TSharedPtr` cycle +
per-tick GFrameCounter++, grade [I,strong]. Lane C of the caveat-2 hunt promoted to [M] via seven
independent instruments **including** the six `FPreLoadScreenManager::*` method-name strings
clustered at .rdata:`0x7BB4120..0x7BB4245`.

The .rdata method-name cluster is the discriminator. `FTicker` and `FCoreDelegates` do NOT ship
per-method `__FUNCTION__` strings in stock UE 5.4 (they're lambda-driven); `FPreLoadScreenManager`
does (six method markers). **When two UE-family shape hypotheses fit the structural evidence
equally, check .rdata for method-name-string clustering — it names the class.**

Corollary: the enum value in a comparison (`dl=2` = EngineLoadingScreen) requires
cross-referencing to a stock UE enum table to distinguish from a boolean or a same-arity constant
on a competing type. Both must be checked, not just one.

## What is now open

Same as the S189-primary "what is now open" section. Redirected to S190 offline task list:

1. Enumerate `.data:0x9d29104` writers image-wide.
2. Full CFG on GuardedMain-like `0x402FD90` + its outer caller.
3. Rank Tick's ~148 direct callees by blocking-primitive risk.
4. Prepare a live-probe design if offline can't close the gap.

See [docs/next-session-prompt-s190.md](next-session-prompt-s190.md).

## Files preserved

- `docs/s189-caveat2-second-gfc-site-settled.md` — this doc
- `docs/s189-caller-hunt-settled.md` — the primary caller-chain map
- Workflow transcript:
  `.claude/.../subagents/workflows/wf_eeaf0460-b51/journal.jsonl`
- Source: `dumps/merged14.dump.exe`
