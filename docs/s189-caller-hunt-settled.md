# S189 — the 293-byte GFrameCounter helper's caller chain is FULLY MAPPED; and the helper is [M] FPreLoadScreenManager, NOT the 30 Hz driver [M]

**Offline 2026-09-08**, disassembly against `dumps/merged14.dump.exe`, zero live flights.
Two multi-agent workflows (`wf_81017226-276` caller hunt + `wf_eeaf0460-b51` caveat-2 resolution)
converging over 10 subagent instruments.

> **Read the caveat-2 doc alongside this one:**
> [docs/s189-caveat2-second-gfc-site-settled.md](s189-caveat2-second-gfc-site-settled.md).
> This doc contains the primary chain map + the FPreLoadScreenManager identification. The caveat-2
> doc contains the decisive refutation that this helper's GFrameCounter++ is the per-frame driver.
> Both are load-bearing; reading only this one produces a wrong picture of what the gate does.

## Headline

★★★★★★★ **[M] The 293-byte helper at `0x29EF3D3` is the middle chained-unwind region of a
351-byte composite function whose REAL entry is `0x29EF3A0`** (per R-S184-a widen-backward from
the mid-shape pdata row). The composite has **3 rel32 callers** — versus 0 at the mid-shape
address that S188 first tried. The load-bearing caller `0x29F3DB0` has exactly **3 rel32 callers,
all inside the FEngineLoop family**:

| caller site | containing function | role |
|---|---|---|
| `0x4027D9D` | `0x4027850` = FEngineLoop::**Init** | one-shot init-time call |
| `0x4028960` | `0x4028110` = FEngineLoop::**Tick** (real) | per-Tick call (gated) |
| `0x402F4D8` | `0x402F470` = FEngineLoop::Exit-family | one-shot shutdown call |

★★★★★★ **[M] The composite helper is FPreLoadScreenManager's per-tick advance
(EarlyPlayFrameTick / preload-loop counter).** Seven independent instruments in the caveat-2
sweep confirm the identification; see §"FPreLoadScreenManager identification" below and
[the caveat-2 doc](s189-caveat2-second-gfc-site-settled.md) §"Lane C".

★★★★★★★ **[M] The helper does NOT fire per gameplay frame — the 30 Hz driver S187 measured is
the INLINE site at RVA `0x4029349-0x4029353` inside real FEngineLoop::Tick's end-of-frame chained
extent.** During gameplay no `EngineLoadingScreen`-type IPreLoadScreen is registered, so the
gate predicate `0x29F0A30` returns FALSE every frame and the composite helper is not called.

⇒ **The S189-caveat2 hunt is what settled which of two GFrameCounter++ sites drives the counter
during gameplay.** This doc's `[M]` mapping of the caller chain STANDS as a correct offline
identification; the gate localization to `0x29F0940` / `0x29F0A30` is IRRELEVANT to the S187
post-companion-kill freeze phenomenon (it gates a different, subsystem-conditional path).

## The full caller chain [M]

```
GuardedMain-like 0x402FD90
  └── call 0x403005A → FEngineLoop::Tick 0x4028110  [~5.7 KiB, 15 chained pdata rows]
        └── call 0x402893C → 0x29F0A30(arg=2)   [outer predicate: walks PreLoadScreens[]]
             call 0x402894F → 0x29F0940(arg=2)  [inner predicate: same array, index [+0x40]]
              └── call 0x4028960 → 0x29F3DB0    [walker; virtual-calls [vt+0x50] on entries]
                    └── call 0x29F3E22 → composite 0x29EF3A0  [51 B entry + 293 B body + 6 B tail]
                          └── (falls through into body at 0x29EF3D3)
                                inc qword [rip+0x7359C4A] at RVA 0x29EF4E7 → GFrameCounter @ .data:0x9D49138
```

Every hop is byte-verified. Every one of the 3 rel32 caller sites in the top table above is
confirmed by strxref rel32 sweep on the composite's real entry `0x29EF3A0` (0 rel32 hits at
`0x29EF3D3`; 3 at `0x29EF3A0`).

The two predicates gating the composite call in Tick both walk the FPreLoadScreenManager singleton's
`PreLoadScreens[]` TArray (fields at `[singleton+0x30]` = Data, `[+0x38]` = Num, `[+0x40]` =
ActivePreLoadScreenIndex sentinel = -1 when idle) and virtual-call `[vt+0x50]` on each entry,
comparing the returned byte to `dl=2` = **`EPreLoadScreenTypes::EngineLoadingScreen`**. Both return
FALSE during gameplay ⇒ helper not called.

## FPreLoadScreenManager identification [M] — seven independent instruments

Caveat-2 Lane C, all against `dumps/merged14.dump.exe`, independently converge on the same
identification:

| # | instrument | evidence |
|---|---|---|
| 1 | **Six `FPreLoadScreenManager::*` method-name strings clustered at .rdata:0x7BB4120..0x7BB4245** | `HandleEarlyStartupPlay`, `EarlyPlayFrameTick`, `HandleCustomSplashScreenPlay`, `PassLoadingScreen` (wide-char), `Create` (at .rdata:0x82B09D8), `PostInitEngine - FPreLoadScreenManager::Get()->Initialize` (at .rdata:0x82B0B19) |
| 2 | **Constructor at `0x29ED8B0` mallocs exactly 0xA8 = 168 bytes** | matches stock UE sizeof(FPreLoadScreenManager) exactly |
| 3 | **`[obj+0x40] = 0xFFFFFFFF`** initialized by ctor | int32 `ActivePreLoadScreenIndex = -1` sentinel, stock UE |
| 4 | **`[obj+0x10] = 2` and `[obj+0x28] = 2`** initialized by ctor | type-tag constants matching `EPreLoadScreenTypes::EngineLoadingScreen` (=2) defaults |
| 5 | **`[+0x30]/[+0x38]` layout with 16-byte stride** | matches `TArray<TSharedPtr<IPreLoadScreen>>` (sizeof `TSharedPtr` = 16 bytes) |
| 6 | **Destructor at `0x29EE500` iterates the same array calling `[vt+0x48]`** | `IPreLoadScreen::CleanUp()`, one slot before `[vt+0x50] GetPreLoadScreenType()`, matching stock UE IPreLoadScreen slot ordering |
| 7 | **Destructor tears down `[rbp+0x88]` via helper `0x29EE690`** | FPreLoadScreenSlateSynchMechanism-shaped spinlock teardown, then NULLs the singleton at `0x29EE629` |

**Singleton address correction** (an S188 handoff typo — noted here so it doesn't propagate
again): the singleton pointer lives at **`.data:0x9F327E0`**, not `0xA7327E0`. The typo was
carried from the S189 caveat-2 shared context in [`wf_eeaf0460-b51`]; Lane C caught it via
arithmetic: leaf `0x29EF500 = mov rax,[rip+0x75432D9]; ret` at ip after mov = `0x29EF507`;
`0x29EF507 + 0x75432D9 = 0x9F327E0`. That address reads NULL in `merged14` (menu-era snapshot,
consistent with stock UE's `FPreLoadScreenManager::Cleanup()` after
`WaitForEngineLoadingScreenToFinish`).

## The 4-part chain-walk that settled the caller identification [M]

Following R-S184-a on the composite's mid-shape address `0x29EF3D3`:

1. **`0x29EF3D3` mid-chain pdata**: `[.pdata EXACT]` unwind `0x95BC0E0`, flags=`0x04`
   (`UNW_FLAG_CHAININFO`), parent `0x29EF3A0` unw=`0x9465830`. **0 rel32 callers** at this
   address.
2. **Widen backward to `0x29EF3A0`**: `[.pdata EXACT]` unwind `0x9465830` is ROOT (flags=`0x00`),
   51 B preamble `push rbx; sub rsp,0x30; movsxd rax,[rcx+0x40]; …` with three JCC bailouts
   (js/jge/je at `0x29EF3AF/B8/CD`) that jump forward to the shared epilogue at `0x29EF4F8`
   (skipping the GFrameCounter++). **3 rel32 callers.**
3. **The tail is a THIRD chained row**: `0x29EF4F8..0x29EF4FE` (6 B), unwind `0x95BC0F8`
   CHAINED to the same root `0x29EF3A0`. Contains `add rsp,0x30; pop rbx; ret`. Confirms
   composite extent = `0x29EF3A0..0x29EF4FE` (351 B total).
4. **Chain-walk each of the 3 rel32 callers back to its own real root** via UNW_FLAG_CHAININFO:
   - `0x29F0122` in chained row `0x29F0113` → parent `0x29EFEE9` → parent `0x29EFEC3` → **ROOT
     `0x29EFE60`** (99 B, flags=`0x00`)
   - `0x29F03D2` in chained row `0x29F03C3` → parent `0x29F01E7` → parent `0x29F01A1` →
     **ROOT `0x29F0170`** (49 B, flags=`0x00`)
   - `0x29F3E22` in chained row `0x29F3DF8` → **ROOT `0x29F3DB0`** (72 B, flags=`0x00`)

## The 293-byte body's structural elements [M] (from Lane C of the primary hunt)

| element | RVA | evidence |
|---|---|---|
| Signed int32 index load from `[this+0x40]` | `0x29EF3A6` | `movsxd rax, [rcx+0x40]` |
| Bail if index<0 | `0x29EF3AF` | `js 0x29EF4F8` |
| Bail if index >= count `[this+0x38]` | `0x29EF3B5..3B8` | `cmp eax,[rcx+0x38] / jge 0x29EF4F8` |
| Array base load from `[this+0x30]` | `0x29EF3C1` | `mov rax, [rbx+0x30]` |
| Stride-16 index doubling | `0x29EF3C5` | `add rcx, rcx` |
| Bail if array slot NULL | `0x29EF3C8..3CD` | `cmp qword [rax+rcx*8], 0 / je 0x29EF4F8` |
| Load array element pointer | `0x29EF3D8` | `mov rdi, [rax+rcx*8]` |
| Virtual call `[vt+0x18]` on element (float return) | `0x29EF3E7` | `call [rax+0x18]` |
| `QueryPerformanceCounter` indirect call | `0x29EF3FC` | `call [rip+0x4C5B036]` → .data:0x764A438 = QPC fptr |
| Delta = now - `[rbx+0x48]`; store now back | `0x29EF41F, 0x29EF424` | `subsd`, `movsd` |
| Delta cap at 5.0f | `0x29EF42D` | `minss xmm6, [rip+0x4CE668B]` → .rdata:0x76D5AC0 = 5.0f |
| Virtual call `[vt+0x10]` on element with `xmm1=delta` | `0x29EF46F` | `call [rax+0x10]` — canonical UE `Tick(float)` slot |
| TSharedPtr obj+ctrl load | `0x29EF491, 0x29EF49B` | `mov rbx,[rip+0x744CD30]` → .data:0x9E621C8 (ctrl); `mov rcx,[rip+0x744CD1E]` → .data:0x9E621C0 (obj) |
| Strong-refcount AddRef | `0x29EF4A7` | `lock inc dword [rbx+8]` |
| Virtual call `[vt+0x30]` on shared object with `xmm1=delta` | `0x29EF4AE` | `call [rax+0x30]` |
| Strong-refcount Release, destroy if 1 | `0x29EF4B8..4C8` | `lock xadd; cmp; je; call [rax]` (vtable slot 0) |
| Weak-refcount Release, destroy if 1 | `0x29EF4CA..4DC` | `lock xadd; cmp; je; call [rax+8]` (vtable slot 1) |
| **GFrameCounter++** | **`0x29EF4E7`** | **`inc qword [rip+0x7359C4A]` → .data:0x9D49138 = GFrameCounter** |
| Restore xmm6, rdi | `0x29EF4EE..4F3` | `movaps xmm6,[rsp+0x20]; mov rdi,[rsp+0x48]` |
| Shared epilogue (also reached by the 3 front-door bails) | `0x29EF4F8..4FD` | `add rsp,0x30; pop rbx; ret` |

The three front-door bails at the composite's entry (`0x29EF3AF`, `0x29EF3B8`, `0x29EF3CD`) all
skip the GFrameCounter++ at `0x29EF4E7` by jumping directly to the shared 6-byte epilogue.

## What this composite helper is, and what it isn't

**IS**: FPreLoadScreenManager's per-tick advance function — called during preload / early-startup
/ engine-loading-screen / shutdown lifecycle phases. The two predicates (`0x29F0940`,
`0x29F0A30`) test whether an `EngineLoadingScreen`-type screen is registered before invoking the
composite. The counter increment inside the composite is the preload-loop's frame counter.

**IS NOT**: the 30 Hz gameplay frame counter driver. During gameplay the FPreLoadScreenManager
singleton is either destroyed (Cleanup after `WaitForEngineLoadingScreenToFinish`) OR its
`PreLoadScreens[]` array contains no `EngineLoadingScreen`-type entries. Either way, the outer
predicate `0x29F0A30` returns FALSE every frame and the composite never executes.

The real 30 Hz driver during gameplay is the inline `mov [rip+X], rbx` at RVA `0x4029353` inside
real FEngineLoop::Tick's end-of-frame chained extent — see [the caveat-2 doc](s189-caveat2-second-gfc-site-settled.md).

## Corrections to prior sessions

**S188 mislabeled 0x4027850 as FEngineLoop::Tick — that function is FEngineLoop::Init.** [M]
Evidence from Lane B/D of both S189 workflows:

- `0x4027850` (2228 B, chained through `0x4027874` and `0x4027BBF`) contains strings
  `"Engine is initialized. Leaving FEngineLoop::Init()"`, `"FCoreDelegates::OnFEngineLoopInitComplete.Broadcast()"`,
  `"GEngine->Start()"`, `"WaitForEngineLoadingScreenToFinish"`, `"WaitForMovieToFinish"`
  — all FEngineLoop::Init markers.
- Real FEngineLoop::Tick is at `0x4028110` (~5.7 KiB, 15 chained pdata rows through `0x4029797`)
  and contains strings `"Replicated properties changed during Slate tick!"`,
  `"WaitForOutstandingTasksOnly_for_DelaySceneRenderCompletion"`, `"FScene_EndFrame"`,
  `"FEngineLoop::Tick.Benchmarking"`, `"FScene_StartFrame"`, `"ResetDeferredUpdates"`,
  `"FrameCounter"`, `"EndFrame"` — all Tick markers.
- Both are called from GuardedMain-like `0x402FD90`: Init at `0x402FF8F` (before the
  `"(Engine Initialization) Total time"` LEA), Tick at `0x403005A` (after the `"Tick loop starting"`
  LEA at +0x283).

**S188's substantive claim "no early-exit paths inside FEngineLoop::Tick" survives the
correction.** Applied to the correct function (0x4028110): recursive-descent CFG over the full
5.7 KiB chained extent decodes 1340 instructions, 16 chained regions, **1 ret in the entire body**
(same structural property S188 measured on Init). All 133 conditional branches on the dominator
chain to the primary GFrameCounter++ site at `0x4029353` are diamonds. The mechanism-level
finding was correct; only the label needed fixing.

## What is now open

1. **Localize the actual halt gate UPSTREAM of FEngineLoop::Tick.** Candidates from Lane B of the
   caveat-2 workflow:
   - The `while(!byte[.data:0x9d29104]) Tick()` loop's exit byte flipping non-zero
     post-companion-kill.
   - A Tick callee never returning (blocking the loop in-flight).
   - The game thread itself blocked / sleeping / deadlocked before re-entering GuardedMain's
     next iteration.
   S190's task.
2. **Offline CFG on GuardedMain-like 0x402FD90 and its outer caller.** Enumerate every dominator
   of the `call 0x4028110` at `0x403005A`. Cite each candidate's `.data` state address and the
   byte it tests. Cross-check `.data:0x9d29104` against S181/S186's `IsRequestingExit`-like
   byte candidate.
3. **Enumerate Tick callees that could block the game thread indefinitely.** Rank by
   sync-dispatch shape + known-blocking primitives (`WaitForSingleObject`,
   `EnterCriticalSection`, spin-loops on volatile state). Focus on callees decrypted only during
   gameplay (LIT in merged14 but NOT in menu-era captures) since these are the ones added past
   startup.

## Files preserved

- `docs/s189-caller-hunt-settled.md` — this doc (primary chain map + FPreLoadScreenManager
  identification)
- [`docs/s189-caveat2-second-gfc-site-settled.md`](s189-caveat2-second-gfc-site-settled.md) —
  the caveat-2 resolution (which of the two GFrameCounter++ sites drives per-frame)
- Workflow transcripts:
  `.claude/.../subagents/workflows/wf_81017226-276/journal.jsonl` (primary caller hunt)
  and `wf_eeaf0460-b51/journal.jsonl` (caveat-2 resolution)
- Source: `dumps/merged14.dump.exe`

## What S189 did NOT do

- Not identify the actual companion-liveness gate (redirected to S190; see caveat-2 doc §"What
  is now open").
- Not read `.data:0x9d29104` from a post-companion-kill snapshot (no such snapshot exists;
  requires live probe).
- Not walk GuardedMain-like 0x402FD90's outer caller chain (WinMain / platform-abstraction
  entry).
- Not enumerate Tick's per-frame callees for blocking primitives.
