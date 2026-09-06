# Session 37 — Option A exhausted, all three variants failed

Session 36 diagnosed the client-initiated close as an `FClassNetCache`
divergence: our stub's stock UE 5.4 `APlayerController` has different
replicated properties than SUPERVIVE's client-patched version, so any
outbound state replication contains a field the client rejects with
"Invalid replicated field 0". Session 36 recommended Option A first —
suppress outbound replication cheaply. Session 37 tried three variants of
Option A. None worked. Documenting here so session 38+ doesn't retread.

## Variant A: strip `CPF_Net` from every FProperty on APlayerController

Approach: at `OnPostEngineInit`, iterate `APlayerController`'s FProperties
and clear `CPF_Net`. Also cleared `ClassReps` in the first attempt.

Result: **crashed the stub with an assertion when the client connected.**

```
Assertion failed: (Index >= 0) & (Index < ArrayNum)
[File:Array.h] [Line: 758]
Array index out of bounds: 0 into an array of size 0
```

- Emptying `ClassReps` broke downstream RepLayout invariants.
- Removing that call and just clearing `CPF_Net` on the properties CRASHED
  in a different code path during initial replication build.
- Cannot call `PCClass->StaticLink(true)` to re-link — Class.cpp:4908
  asserts against relinking CLASS_Intrinsic classes.

Verdict: **runtime property-flag stripping is not viable.** RepLayout tables
built from ClassReps assume specific invariants (>= 1 entry, matching
Cmds structure) that stripping violates.

## Variant A': `PostLogin` → `SetNetDormancy(DORM_DormantAll)`

Approach: override `ALokiStubGameMode::PostLogin`, set the PC's
`NetDormancy = DORM_DormantAll` when it's freshly spawned.

Result: **client still rejects with "Invalid replicated field 0".**

Timing shows `PostLogin` runs during `Welcomed → ReceivedJoin` transition,
but the initial actor bunch (with the offending property data) is already
in flight by then. Dormancy takes effect on the NEXT replication cycle,
which never happens because the client tears down after the initial bunch.

## Variant A'': modify CDO — `APlayerController::CDO->NetDormancy = DORM_DormantAll`

Approach: set the class default object's `NetDormancy` at
`OnPostEngineInit` so every newly-spawned PC starts dormant. Was expected
to affect the very first bunch since `SpawnActor` copies CDO values to the
instance.

Result: **same "Invalid replicated field 0" error.**

`NetDormancy` docs claim it suppresses replication, but the initial actor
bunch (which contains the initial property values) fires regardless. The
dormancy flag only prevents SUBSEQUENT update cycles. The first bunch is
required to establish the actor on the client side and always carries the
initial state block.

## Why no variant of A could work

The `FClassNetCache` divergence exists at the initial replication bunch —
which UE treats as fundamental to establishing an actor channel on the
client. There's no runtime knob that says "open the channel but don't
serialize any properties in the initial bunch."

The initial bunch has two logical parts:
1. Actor identity (class, spawn info, NetGUID) — required for client
   spawning a replica
2. Initial property values — this is what has the bad field

UE bundles them. Without native-level modification of ReplicateActor's
inner loop, we can't send (1) without (2).

## Path forward: Option B or a native intercept

**Option B**: inject FProperty entries onto APlayerController's replicated
set that match SUPERVIVE's expected class-net-cache layout. Substantial
engineering. Sessions 27–32 already established the injection primitives;
this extends them from RPC params to top-level UProperties.

**Native ReplicateActor override**: subclass UActorChannel to intercept
`ReplicateActor` and either
- craft a hand-rolled initial bunch with no property block, OR
- skip the initial bunch entirely (client's local PC exists regardless of
  server replication — may be enough for the RPC path).

Recommendation for session 38: try the native ReplicateActor override
first — it's a smaller change than reverse-engineering SUPERVIVE's class
layout. In `ULokiActorChannel`, override `ReplicateActor()` to return 0
when `Actor->IsA<APlayerController>()`. Test whether the client tolerates
an actor channel with no bunches sent from server — if yes, RPCs still
route because the client's local PC has its own NetGUID handle.

## What Session 37 leaves in place

- `LokiStubGameMode::PostLogin` override present but no-op (kept as a
  documented hook site).
- No CDO changes.
- No property-flag changes.
- `Loki.cpp`'s `InjectServerVerifyViewTargetFStringParam` unchanged from
  session 35: still injects the 40-param signature and runs
  `SelfReplayCapturedRPC`.

Repo state is safe — no dangling behavior changes. All negative results
documented here for future reference.
