# S185 (Rank 7) — the halted subsystem is UE's tick chain [M]

**Live-flown 2026-09-08** in a fresh game process (PID 42924), NO F9 sequence,
fo-verbose R7 injected via `inject.exe mmap` alone. Extends S183 (caller-RIP) and S184
(function identification) with per-hit UFunction* capture. Preserved as
[docs/s185-rank7-baseline-ufuncs-live-fullmarker.txt](docs/s185-rank7-baseline-ufuncs-live-fullmarker.txt).

## Headline

★★★★★★★★★★★★★★ **[M] Every one of the 30 baseline PI dispatches was a
tick/anim/input BP function.** Named distribution:

| UFunction | count | instances |
|---|---|---|
| `ReceiveTick` | **23** | **6 distinct UObjects** |
| `BlueprintUpdateAnimation` | 2 | 2 (`UAnimInstance` subclasses) |
| `Tick` | 1 | 1 (`UActorComponent` subclass) |
| `Destruct` | 2 | 2 (widget teardown) |
| `BP_OnDeactivated` | 1 | 1 (menu widget lifecycle) |
| `InpAxisKeyEvt_MouseWheelAxis_K2Node_InputAxisKeyEvent` | 1 | 1 (mouse-scroll input handler) |

⇒ **This is UE's tick chain plus input dispatch.** `ReceiveTick` is the standard
Blueprint entry point that `AActor::Tick` and `UActorComponent::Tick` call. The 6
distinct `ReceiveTick` instances = 6 different tickable BP-defined actors/components
running per-frame BP logic on this menu.

⇒ **Post-companion-kill (S181), NONE of these fire (hitsAny=0 for 60s).** The gate is
at the tick-schedule / event-dispatch layer of UE — specifically, whatever calls
`Actor->ProcessEvent(FindFunction("ReceiveTick"), ...)` or the equivalent for
component ticks, anim updates, and input events. That single-point mechanism is what
`-CompanionWatch`'s FK-32 defeat kills.

## What the S184 handoff predicted vs what S185 measured

S184 said "the gate must live at what schedules bytecode execution — candidates: FEngineLoop::Tick,
UWorld::Tick, AActor::Tick, timer manager, UMG input dispatch". S185 measures that BOTH
**tick dispatch** (23 ReceiveTicks + 1 Tick + 2 anim) AND **input dispatch** (1 mouse-
axis event) AND **widget lifecycle** (2 Destructs + 1 OnDeactivated) all use PI. That
covers three of S184's five candidates. Their common shared entry is `UObject::ProcessEvent`
(which calls `ProcessInternal` for native → BP dispatch) — every entry in the table above
routes through it.

**⇒ The mechanism is [I,strong]: `UObject::ProcessEvent` has been intercepted somewhere
in its shared chain by a protector check that returns early when companion is dead.**
Not `FEngineLoop::Tick` (too broad — non-BP work continues per S182), not any specific
subsystem (input, animation, and tick all halt in lockstep — not consistent with a per-
subsystem gate).

## Wait — the caller-ring said 29 hits all from CallFunction, not from ProcessEvent

There's a technicality worth noting. S183's caller-ring showed 29 hits at
`SUPERVIVE.exe+0x1225fd6` (inside `UObject::CallFunction`). But S185's UFunction ring
shows 30 hits at ProcessInternal.

The reconciliation: **CallFunction is the shared inner dispatcher.** UE's tick path is:
```
AActor::TickActor
  -> ProcessEvent(FindFunction("ReceiveTick"), ...)
     -> ProcessInternal(this, Stack, Result)          // interprets the BP body opcode-by-opcode
        -> for each EX_FinalFunction opcode:
           -> CallFunction(this, Result, UFunction)   // <-- S183 caught 29 hits HERE
              -> [r14+0xE0]                            // = UFunction::Func = ProcessInternal for BP calls
                 -> ProcessInternal (nested)          // <-- S185 hooks HERE
```

So when a `ReceiveTick` runs, the OUTER ProcessEvent → ProcessInternal call fires (that's
1 hit). Then inside ProcessInternal, if the BP body has `EX_FinalFunction B` bytecode,
it calls CallFunction which enters ProcessInternal a second time (that's a nested hit,
caught at CallFunction site).

⇒ **The 29 CallFunction-site hits are NESTED BP→BP invocations from INSIDE the tick
bodies.** S185's UFunction ring shows the OUTERMOST BP being invoked. The 30 hits count
BOTH the outer ProcessEvent-triggered ProcessInternal calls AND the inner CallFunction-
triggered ones, hence the +1 discrepancy (30 vs 29): one more UFunction entry was seen
that wasn't nested through CallFunction (it was an outer ProcessEvent hit).

Both S183 and S185 are self-consistent: the workload is tick/anim/input bodies invoking
each other; every level of the tree calls ProcessInternal.

## What the halt must actually be

Given the UFunction ring shows outer ticks stopping, and S181/S183 established that
`ProcessInternal` itself (the interpreter entry) is not being called at all post-kill:

- **Option A**: `AActor::Tick` / `UActorComponent::Tick` (native functions) don't call
  `ProcessEvent` when companion is dead. Requires the native tick body to have been
  patched.
- **Option B**: `UObject::ProcessEvent` itself has an early-exit that reads companion
  state. Requires ProcessEvent to have been patched (either in-image or vtable override).
- **Option C**: The task graph that schedules tick functions doesn't enqueue BP-bearing
  ticks. Requires the task graph enqueue logic to check companion.

All three predict the exact observed phenotype. Discriminating them requires either:
1. **Offline**: byte-compare `AActor::Tick` / `UObject::ProcessEvent` / task graph
   enqueue between an ON-DISK exe copy and a live-dumped image, looking for post-load
   patches. If either is patched, that's the site.
2. **Live**: hook `ProcessEvent` itself (in addition to `ProcessInternal`) with a per-
   caller counter. If `ProcessEvent` fires at baseline rate but ProcessInternal is
   halted, it's Option B (early-out inside ProcessEvent). If ProcessEvent itself halts,
   it's Option A or C.

**Offline is cheaper** — one dumpimage diff against the on-disk game exe.

## Rules banked

### S185-a: Adding a second per-hit capture register (r14 for UFunction*, in addition to caller-RIP) is 17 bytes of ASM in the InstallHook stub and reads the UFunction from FFrame.Node via `[rdx+0x90]` (rdx = FFrame*, .Node = +0x90 in this build). Combined with a UFunction-pointer ring and NameId+GetFNameStr lookup at dump time, it enumerates WHICH bp bodies are being called at every hit. [M]

Applied here: 17 bytes added to BuildHook (`mov rax, [rsp+0x38]; mov rax, [rax+0x90];
mov [g_piLastUFunc], rax`), plus a parallel 128-slot ring in OnPI. The dump at `[4u]`
resolved 12 unique UFunction pointers to 6 distinct function-name shapes with counts,
identifying the workload's shape in one flight.

### S185-b: Read FFrame.Node from the FFrame*, not from the r14 register. FFrame.Node is set to the current UFunction by the caller before invocation and is unambiguously the currently-dispatching function. Reading r14 works when the caller is CallFunction (which passes UFunction* in r9/r14) but breaks for other paths (ProcessEvent, direct thunk calls). FFrame.Node is universal. [M]

Applied here: I initially considered reading `r14` (the UFunction* register in
CallFunction's convention). Read from FFrame.Node instead — captures the actual
UFunction regardless of the calling convention of the enclosing caller. Given the
mix of ReceiveTick (called from ProcessEvent) and inner BP→BP calls (called from
CallFunction), the FFrame.Node approach caught all 30 hits uniformly.

### S185-c: When a single-bucket caller-ring measures 29 hits and a UFunction ring measures 30 hits from what looks like the same window, the +1 discrepancy is the OUTERMOST ProcessEvent hit (whose caller is not CallFunction) — proof that at least one call path bypasses CallFunction and enters ProcessInternal directly via ProcessEvent. That in turn confirms the caller-ring's semantic (BP→BP via bytecode dispatchers only), and gives the ProcessEvent-direct call count as a free by-product. [M]

Applied here: caller-ring 29, UFunction ring 30 — the +1 is the outer ProcessEvent
invocation that the CallFunction site would never see. The magnitudes agree with the
expected ratio (nested BP→BP calls dominate over outer ProcessEvent entry points).

## Progression from S183 → S184 → S185

| session | new finding |
|---|---|
| S183 | mechanism narrowed to ONE RVA in SUPERVIVE.exe [M] |
| S184 | that RVA is `UObject::CallFunction`; 5 rel32 callers all in ScriptCore [M] |
| **S185** | **the workload is `ReceiveTick`/`BlueprintUpdateAnimation`/input events — UE's tick + input dispatch chain — and it stops entirely post-companion-kill [M]. Gate is at ProcessEvent (or upstream) in the tick-dispatch layer.** |

## What is now open

1. **Offline dumpimage diff of on-disk SUPERVIVE.exe vs live dump** at `UObject::ProcessEvent` and `AActor::Tick`/`UActorComponent::Tick`. If either has post-load patches (not present in the on-disk exe), that names the specific interception. Cheap, purely offline, one comparison.
2. **Identify the 6 tickable actor classes** — dedupe the ReceiveTick pointers by their OUTER (owning class) and print the class names. Currently `class='Function'` is the UFunction's OWN UCLASS; what we want is UFunction->Outer = the class that owns the tick body. ~5 lines of code to fix.
3. **Practical shipping path** if the mechanism is a vtable override on ProcessEvent: restoring the stock ProcessEvent slot in one vtable would restore tick dispatch. Same class of data poke as S123 (single aligned qword, readback-verifiable).

## Files preserved

- `docs/s185-rank7-baseline-ufuncs-live-fullmarker.txt` — the [4u] UFunctions dump
- fo-verbose R7 build: `.text` `1dd50b5baed38c5e`
- Stock fo `.text` still `31d4e4dc0b9c9b5e` — deployed byte-identity preserved

## What S185 did NOT do

- Not run the offline dumpimage diff on ProcessEvent / AActor::Tick.
- Not resolve UFunction->Outer to identify the 6 ticking classes.
- No commit yet.
