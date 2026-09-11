# `dsNotif` payload probe — ground truth fields, and what still does not happen

**S117, 2026-08-13 21:05 UTC.** With the envelope fix live, `dsNotif` reaches the
dispatcher. This probes the PAYLOAD rather than the routing.

## The field list is ground truth, not guesswork

`AccelByteModelsDsNotice` is a reflected struct, so the usmap has it exactly
(`tools/usmapdump/schema.txt:1309`, 12 props):

| field | type | note |
|---|---|---|
| `Status` | Str | |
| `MatchID` | Str | |
| `PodName` | Str | |
| `Ip` | Str | |
| `ImageVersion` | Str | |
| `ServerVersion` | Str | |
| **`Port`** | **Int** | ⚠ the lobby's key:value→JSON converter emits everything QUOTED — we observed `"port":"7777"` — so a matched key arrives with the wrong JSON type |
| `Message` | Str | |
| **`IsOK`** | **Str** | ⚠ a STRING, not a bool |
| `Region` | Str | |
| `Ports` | Map | ⚠ FK-14: container inner types in the usmap are untrustworthy; do not infer the element type from it |
| `CustomAttribute` | Str | |

★ This is method rule 2 doing the work: the shipped artifact already carried the
answer, and the 2026-06-29 probes' ~35 invented field names were never necessary.

## Result: parsed and routed, still no action

A full-fidelity frame carrying 11 of the 12 fields with the exact reflected names:

```
JSON Version: {"type":"dsNotif","Status":"READY","MatchID":"fk15-match-0001",
               "PodName":"fk15-pod","Ip":"127.0.0.1","ImageVersion":"1.0.0", ...}
Type: dsNotif
```

- `Failed to Deserialize` : **0** — UE did not reject the document, including the
  quoted `Port` against an `IntProperty`.
- No `LogNet`, no `NetConnection`, no connect attempt to 127.0.0.1:7777.
- Session unaffected.

## ⚠ What this can and cannot say — the detector problem

`Type: %s` is logged **BEFORE the handler lookup**. Proof: a bogus type
(`dsNotice-PLACEHOLDER`, absent from the binary) produced the identical trace
including `Type: dsNotice-PLACEHOLDER`. And the two `Error; Detected of type ...`
strings are **not plain UE_LOGs** — they are `Printf`'d through a virtual on
`Lobby+0x218` — so their absence proves nothing either.

⇒ **We currently have NO instrument that distinguishes "reached a bound handler
case and did nothing" from "fell to the default and was discarded."** Every
payload conclusion below is bounded by that.

## What to do next, in order of decisiveness

1. **Get a handler-level detector before probing more payloads.** Options:
   (a) find what `Lobby+0x218`'s sink is and whether it can be made to log;
   (b) read `Lobby::HandleNotif`'s jump-table entry for `dsNotif` statically and
   check whether its case body is a real function or a fold to a default;
   (c) watch the delegate the case broadcasts (`Lobby+0x1C0/0x228/...` shape seen
   in cases 1-6) for a bound target. **Without one of these, more payload
   variants generate uninterpretable nulls — the exact failure this whole
   investigation exists to correct.**
2. Only then vary the payload — `Port` as an unquoted int is the obvious first
   variant, which needs a converter change or a raw JSON frame, not a key:value one.

## Standing note

The AccelByte `*Notice` structs for every other high-value type are in the same
place and equally exact, e.g. `AccelByteModelsMatchmakingNotice` (10 props, and
note `Status` is an ENUM and `Joinable` a real Bool) and
`AccelByteModelsPartyGetInvitedNotice` (`From`, `PartyId`, `InvitationToken`).
**Read the struct before authoring any future frame.**
