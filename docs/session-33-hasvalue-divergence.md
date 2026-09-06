# Session 33 — SUPERVIVE has patched RPC serialization (has-value bit divergence)

## Discovery

Session 32 self-replay validated our 40-param `ServerVerifyViewTarget`
signature as a straight-through property walk that exactly consumes all
2298 bits of the captured RPC arg struct. Session 33 investigation of UE
5.4 source revealed that **stock UE would NOT produce this wire format**.

## UE 5.4 stock non-InternalAck RPC serialization

`FRepLayout::SendPropertiesForRPC` (called on the sender side for live
connections) walks each top-level param and:

```cpp
if (!CastField<FBoolProperty>(Parents[i].Property))
{
    // ...
    Writer.WriteBit(Send ? 1 : 0);       // <-- HAS-VALUE BIT (always written)
}

if (Send)
{
    SerializeProperties_r(Writer, ...);   // property payload, only if Send=true
}
```

- For `FBoolProperty` params: no has-value bit, always serialize the 1-bit value.
- For every other property (int, uint, byte, FString, ObjectProperty, etc.):
  1 bit "has-value" flag first, then the payload only if the flag is set.

The receiver (`FRepLayout::ReceivePropertiesForRPC`, non-InternalAck branch)
mirrors this: reads 1 has-value bit before each non-Bool param, only
deserializes the payload if the flag was set.

## The divergence

For our 40-param signature the counts are:

- Bool params (no has-value): 3 header + 21 element bools = 24 total
- Non-Bool params (1 has-value bit each): 1 ObjectProperty + 5 StrProperty + 5 UInt32Property + 5 ByteProperty = **16 has-value bits** total

If stock UE were producing this bunch, we'd expect **2298 + 16 = 2314** bits
of straight payload, OR the has-value bits would be interleaved and the
FString payloads would land at DIFFERENT bit positions than we observed.

## Empirical falsification (see `session-33-hasvalue-analysis.py`)

Running both interpretations against the captured 2298 bits:

### Hypothesis A — straight-through (no has-value bits)

```
Pos=   0 skip 18 bits (AActor* NetGUID)
Pos=  18 read bool PadBit1 = 1
Pos=  19 read bool PadBit2 = 0
Pos=  20 read bool PadBit3 = 0
Pos=  21 read FString.count = 46            "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_PartyMenu"
Pos= 421 read Map1_U32     = 0
Pos= 453 read Map1_U8      = 0
Pos= 461..465 read Map1_B0..B4 = 0,1,1,0,0  (value 6)
Pos= 466 read FString.count = 56            "/Game/Loki/Maps/LobbyV2/LVL_LobbyV2_HeroSelect_Skylands"
... etc.
END Pos=2298 Leftover=0
```

**PERFECT FIT.** All 5 FStrings decode as valid sub-level paths, every bit
accounted for.

### Hypothesis B — UE 5.4 stock non-InternalAck with has-value bits

```
Pos=   0 has-value(AActor*)   = 1
Pos=   1 read AActor* NetGUID (17 bits after has-value)
Pos=  19 read bool PadBit1 = 0
Pos=  20 read bool PadBit2 = 0
Pos=  21 read bool PadBit3 = 0
Pos=  22 has-value(Map1_Name) = 1
Pos=  23 read FString.count = 3,221,225,483  ← GARBAGE
```

**GARBAGE**. First FString count of ~3 billion. Would trigger
`FBitReader::SetOverflowed` immediately.

## Conclusion

SUPERVIVE's client has been patched to **serialize RPC params
straight-through — no has-value bits** — for at least
`ServerVerifyViewTarget` (and probably for all RPCs, but only this one is
in the captured evidence set).

## Implication for our stub

Even with our correct 40-param signature, when a live client's bunch
arrives at our (stock UE 5.4) stub server, the receive path fires:

```
UActorChannel::ProcessBunch
  → FObjectReplicator::ReceivedBunch (walks fields)
  → FObjectReplicator::ReceivedRPC   (for our RPC field)
  → FRepLayout::ReceivePropertiesForRPC
      (non-InternalAck branch — expects has-value bits)
      → misreads the payload
      → SetOverflowed or Mismatch read → returns false
  ← ObjectReplicatorReceivedBunchFail → connection close
```

To make our stub accept a real client's bunch, we need one of:

**A. Native code patch of `FRepLayout::ReceivePropertiesForRPC`** — like
`browse_hook.dll` patches `UEngine::Browse`. Overwrite the function's
prologue to jump to our own straight-through implementation. Robust but
requires disassembly work + Loki-module boot-time hook install.

**B. Custom parsing in `ULokiActorChannel::ReceivedBunch`** — before
`Super::ReceivedBunch` fires the doomed field-loop, we peek the bunch,
identify our target RPC's field by RepIndex, do our own straight-through
walk to log/consume the payload, then either (b1) advance the outer reader
past the RPC field so `Super`'s ProcessBunch sees no work, or (b2) skip
`Super` for bunches containing our RPC. Loses reliability of standard
channel state maintenance but avoids native patching.

**C. Rewrite the bunch in place to insert has-value bits** at the correct
positions before `Super`. Complex because `FInBunch` is bit-packed; every
byte after the insertion point shifts. Not attractive.

Recommendation: try **B** first for prototyping, move to **A** if the
channel state fallout gets unwieldy.

## Files

- `docs/session-33-hasvalue-analysis.py` — the empirical falsification script
- `docs/session-33-hasvalue-divergence.md` — this analysis
