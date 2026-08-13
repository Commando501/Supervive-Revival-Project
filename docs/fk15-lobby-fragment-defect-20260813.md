# ★★★★★ `/lobby` frames have NEVER been dispatched — SOLVED: the AccelByte envelope

> ## ✅ ROOT CAUSE FOUND AND FIXED, 2026-08-13 20:50 UTC
>
> **The client asks for message delimiters in its WebSocket handshake and we never honoured them.**
> Measured on the live upgrade:
>
> ```
> WS connected /lobby      (subproto="wss") envelope=["LbS".."LbE"]
> WS connected /notifications/players/{id} (subproto="wss") envelope=[""..""]
> ```
>
> The client sends `X-Ab-EnvelopeStart: LbS` and `X-Ab-EnvelopeEnd: LbE` as request headers
> (literals at `.rdata 0x8604890` / `0x86048A8`), stores them as the FStrings at `lobby+0xA8` /
> `+0xB8`, and `Lobby::OnMessage`'s completeness check (`.text 0x4b35a80`) takes the no-framing
> fast path ONLY when both are empty. Every unwrapped frame we ever sent was therefore buffered
> as an incomplete fragment, forever.
>
> ★ **This is also why the messenger probes worked and the /lobby probes did not:** the messenger
> negotiates EMPTY markers, so it needs no envelope. The two channels were never comparable.
>
> **FIX** — `ws.Conn.WriteText` now wraps with the socket's own negotiated markers, which is
> automatically correct per-channel (a no-op on the messenger). `WriteTextRaw` keeps the unwrapped
> form for probes.
>
> **RESULT, immediately on reconnect** — four responses that had NEVER been parsed in this
> project's history:
> ```
> Type: listIncomingFriendsResponse
> Type: listOutgoingFriendsResponse
> Type: listOfFriendsResponse
> Type: setUserStatusResponse
> ```
> Dispatch count 0 -> 4, with `Message fragmented` no longer incrementing.
>
> ## ✅ AND `dsNotif` FINALLY LANDED
> ```
> Raw Lobby Response: LbStype: dsNotif ... port: 7777LbE
> JSON Version: {"type":"dsNotif","status":"READY","ip":"127.0.0.1","port":"7777"}
> Type: dsNotif
> ```
> The client parsed our key:value frame into JSON and routed it. ★ Note what did NOT appear:
> `"Error; Detected of type notif but no specific handler case assigned"` (`.rdata 0x86041F0`).
> Its absence means **dsNotif reached its dedicated handler case** — the 33-names == 33-jump-table
> -cases corroboration, confirmed live.
> **No NetConnection followed**, so the handler did not act on these fields. That is now a NARROW,
> well-instrumented question (what its delegate needs / who binds it) rather than a silence.


**S117, 2026-08-13. Found while re-pushing `dsNotif` with `-Preset Ws`.**
**This is OUR defect, and it is the mechanical explanation for FK-15's original null.**

## The measurement

With `LogAccelByteLobby=VeryVerbose` (new `-Preset Ws`), the client narrates its own
lobby receive path. Over a fresh session:

| line | count |
|---|--:|
| `Sending request` (client → us) | 9 |
| `Raw Lobby Response` (our frames arriving, content correct) | **14** |
| `Message fragmented, current content buffer` | **14** |
| **`Type: %s` — the DISPATCH line** | **0** |
| `Metadata found type %s, id %s, code %s` | **0** |

**1:1, without exception.** Every frame we send is logged as received, then logged as an
incomplete fragment, and is never dispatched. `Type: %s` (`.text 0x04B0B12B`) has never
fired in this project's history.

The content is not the problem — the client echoes it back correctly:

```
LogAccelByteLobby: Verbose: Raw Lobby Response
type: listIncomingFriendsResponse
id: friends-8617
code: 0
friendsId: []
LogAccelByteLobby: Verbose: Message fragmented, current content buffer
type: listIncomingFriendsResponse
...
```

## Consequences — this reframes FK-15's whole history

- **Our `/lobby` responses have never been parsed.** `listOfFriendsResponse`,
  `setUserStatusResponse` et al. are all buffered and dropped.
- ⚠ **An earlier inference in this very investigation is now WITHDRAWN:** "the client
  sends each friend request exactly once and never retries, i.e. it accepted our
  answers." It never retries *regardless*. Absence of a retry is not evidence of
  consumption.
- **All five 2026-06-29 probes would have been buffered the same way.** FK-15's "silent
  absorption" now has a concrete mechanism, and it is on our side of the wire.
- ⚠ It does **NOT** touch the messenger findings: probes 1-3 were on
  `/notifications/players/{id}`, a different class (`UMessengerManager`) with a different
  parser, and those results stand (sentinel echoed, heartbeat fixed, targeted resync
  proven to refetch and apply).

## The check, located

```
0x4b0ad90  lea rdx,[Raw Lobby Response]      ; log what arrived
0x4b0adca  mov byte ptr [rbp+0x6f], 0        ; out-flag := 0
0x4b0adef  call 0x4b35a80                    ; <-- THE COMPLETENESS CHECK
0x4b0adf4  cmp byte ptr [rbp+0x6f], r12b
0x4b0adf8  jne 0x4b0ae32                     ; flag != 0 => COMPLETE => dispatch
0x4b0ae1a  lea rdx,[Message fragmented]      ; fall-through => buffered
```

Inside `0x4b35a80`:

```
0x4b35b02  cmp dword ptr [r12+8], 1   ; r12 = FString @ lobby+0xA8
0x4b35b10  jg  ...
0x4b35b12  cmp dword ptr [r13+8], 1   ; r13 = FString @ lobby+0xB8
0x4b35b17  jg  ...
0x4b35b19  (both empty) -> plain copy, return
```

`[X+8]` is an `FString`'s `ArrayNum`, so `<= 1` means empty. The fragmenting path is taken
only when **at least one of the two FStrings at `lobby+0xA8` / `lobby+0xB8` is non-empty**.
Those two are the framing delimiters, and ours never match.

## ⚠ WHAT IS NOT ESTABLISHED — the terminator itself

Four framings were pushed and **all fragmented**:

| framing | result |
|---|---|
| no terminator (current `buildLobby`) | fragmented |
| trailing `\n` | fragmented |
| trailing `\n\n` | fragmented |
| `\r\n` fields + trailing `\r\n` | fragmented |

The CRLF attempt came from `0d 00 0a 00` sitting at the literal the check loads
(`0x768a7d4`); that is suggestive but **the address the `lea` actually targets is
`0x768a7d0`, four bytes earlier**, so the literal was not positively identified. Do not
record "the terminator is CRLF" — it is unidentified.

## NEXT STEP — one read, and it answers it outright

**Read the two FStrings at `lobby+0xA8` and `lobby+0xB8` on the live client.** They are
the delimiters by construction. `tools/usmapdump` RPM or `tools/re/read_field.py` can do
it with the game running; no launch needed. Then set `buildLobby`'s framing to match and
re-push — `Type: dsNotif` printing is the confirmation.

Only after that is a `dsNotif` result meaningful: **every `/lobby` push to date, including
today's, has been read by a parser that never dispatched it.**
