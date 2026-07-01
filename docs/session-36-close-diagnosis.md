# Session 36 — Diagnosis of client-initiated close

Session 35 got a real client bunch to the stub and validated the route-around.
The connection closed immediately after — session 35 noted "client-initiated
close, orthogonal to our work". Session 36 traced the actual cause.

## Client-side smoking gun

At 18:09:54.528 (client clock, ~16ms before our RPC arrives on server clock):

```
LogRep: Error: ReceivedBunch: Invalid replicated field 0 in
  PlayerController /Game/Loki/Maps/LobbyV2/LVL_LobbyV2_Persistent.
    LVL_LobbyV2_Persistent:PersistentLevel.PlayerController_2147481890
```

## What that error means (UE 5.4 stock source)

`FObjectReplicator::ReceivedBunch`, DataReplication.cpp:1182 — the ELSE branch
after successive checks for `FStructProperty` and `UFunction`:

```cpp
// Handle property
if (FStructProperty* ReplicatedProp = CastField<FStructProperty>(FieldCache->Field.ToField())) { ... }
// Handle function call
else if (Cast<UFunction>(FieldCache->Field.ToUObject())) { ... }
else
{
    UE_LOG(LogRep, Error, TEXT("ReceivedBunch: Invalid replicated field %i in %s"), ...);
    return false;
}
```

The client received a bunch with a field header whose `NetFieldExportHandle`
resolves in the client's `FClassNetCache` for `APlayerController` to something
that is neither an `FStructProperty` (custom delta) nor a `UFunction` (RPC).

`FClassNetCache` is built from a class's replicated properties + RPCs, sorted
into a stable index space. Both ends must agree on the exact NetIndex → field
mapping, or reads fail.

## Root cause: stock UE 5.4 PlayerController ≠ SUPERVIVE's

Our stub uses stock `APlayerController` (per session 26 revert — subclass with
different name was UHT-rejected). SUPERVIVE's client uses their own patched
`APlayerController` with (session 22 confirmed) engine-level modifications.
The two `FClassNetCache`s differ:

- Different set of replicated properties.
- Different set of RPCs (SUPERVIVE has at minimum modified
  `ServerVerifyViewTarget`, which sessions 25–35 already established).
- Therefore different NetIndex mappings for the same abstract fields.

Our stub's normal replication of the PlayerController's state sends field
NetIndex 0 (whatever the stock UE class has at position 0 in its sorted list —
probably `AcknowledgedPawn` or one of the alphabetically-earliest replicated
members). On the client side, NetIndex 0 in SUPERVIVE's cache is something
different — evidently not a custom-delta struct or a UFunction — hence the
"Invalid replicated field 0" error.

Once the replicator returns `false`, the bunch is flagged
`ObjectReplicatorReceivedBunchFail` and the connection closes.

## Why session 25 didn't hit this

Session 25 also failed the connection, but on a different error:
`ReceivedRPC: ReceivePropertiesForRPC - Mismatch read` — the server's
`ServerVerifyViewTarget` had 0 params and the client's bunch had 2298 bits
leftover.

That RPC error fired FIRST because the RPC arrives on the same channel-3
bunch — the client's own property-replication rejection was probably
happening in prior sessions too, just eclipsed by the RPC failure. Sessions
30–35 fixed the RPC path, exposing the underlying property-replication
divergence.

## The path forward

Three levels of fix, in increasing complexity:

**A. Suppress outbound property replication for the PC** (quickest).
Override `AActor::PreReplication` or set `bAlwaysRelevant=false` +
`NetUpdateFrequency=0` so we never send state to the client. The client sees
the actor channel open but no property updates flow. Might satisfy the client
if it just needs an actor exists on that channel; might not if it expects
specific replicated state (Pawn, PlayerState, ViewTarget) to hydrate its UI.

**B. Match the class net cache by pruning + faking replicated fields**
on our stub-side `APlayerController`. Requires injecting FProperties with
matching NetIndex ordering to match SUPERVIVE's expected layout. Similar
runtime injection to session 27–32 but for regular replicated properties
rather than RPC params.

**C. Native patch of the client's or server's cache-build logic** to
guarantee compatible indexes regardless of underlying class differences.
Most invasive, most robust.

Recommendation: try **A** first. If the client tolerates a channel with no
property replication, we buy time to focus on menu-data replication (the
chapter's original goal). If not, escalate to B.

## What is NOT the issue

- Has-value bit divergence: irrelevant for state replication (has-value bits
  are RPC-specific).
- Route-around: worked perfectly. Consumed the target bunch, skipped Super,
  channel state stayed consistent from the transport perspective (the close
  was because of the earlier field-0 rejection, not because of our skip).
- Our injected `ServerVerifyViewTarget`: the client received our bunch (we
  didn't send that; we RECEIVED the client's RPC).

## Files touched this session

- `docs/session-36-close-diagnosis.md` — this analysis.
