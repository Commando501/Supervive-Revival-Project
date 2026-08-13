# The 7 notif types that can actually move this client

**S118, 2026-08-13.** Completes the FK-15 chain. S117 proved the `/lobby` receive path
works end to end and that `dsNotif`'s delegate is unbound. This maps **every** one of the
33 dispatch cases to its delegate and to that delegate's live bound/unbound state, so the
next push is chosen from evidence instead of a string table.

## ★★★ THE ANSWER — 7 of 33

| enum | case | delegate | type | subscriber |
|---:|---:|---|---|---|
| 2 | 1 | `Lobby+0x228` | **`disconnectNotif`** | `SocialManager` `+0x5856490` |
| 16 | 15 | `Lobby+0x12d0` | **`userStatusNotif`** | `SocialManager` `+0x585a500` |
| 25 | 24 | `Lobby+0x1630` | **`acceptFriendsNotif`** | `SocialManager` `+0x58564b0` |
| 26 | 25 | `Lobby+0x1640` | **`requestFriendsNotif`** | `SocialManager` `+0x5857080` |
| 27 | 26 | `Lobby+0x1650` | **`unfriendNotif`** | `SocialManager` `+0x5856800` |
| 28 | 27 | `Lobby+0x1660` | **`cancelFriendsNotif`** | `SocialManager` `+0x58574e0` |
| 29 | 28 | `Lobby+0x1670` | **`rejectFriendsNotif`** | `SocialManager` `+0x5859700` |

**The other 26 types broadcast into a delegate with no subscriber** — including `dsNotif`,
`matchmakingNotif` and every `party*` type. They parse, route, deserialize and broadcast
correctly, and then nothing happens. That is not a bug in our push; it is the client's
subscription surface.

★ **Why this set and no other:** 21 of the 23 bound delegates belong to **one
`USocialManager` instance**, 1 to `UMyActivityManager`, and 2 are raw-method delegates
Lobby binds to itself. The reachable notif surface is therefore exactly the
**friends/presence family**. The result explains itself, which is the main reason to
believe it.

★★ The five friends types occupy **contiguous cases 24–28** and **contiguous delegates
`+0x1630..+0x1670` at a perfect `0x10` stride** — a structural corroboration independent
of any name ordering.

## The live window (why this was cheap)

The S117 process was **still running**: PID 29856, up since 15:16:57, module base
**`0x7FF7C7EF0000`** — byte-identical to the S117 record, and `dumps/lobby-dispatch-decrypted/`
was taken from this same instance at 16:13. So every ASLR-dependent address was still
valid and the demand-decrypted `.text` pages were live.

★ **Reusable: before re-deriving an ASLR-dependent address, check whether the process that
produced it is still alive.** The handoff said "re-derive per launch"; one `Get-Process`
made the whole live route free.

Positive control before any reading — `Lobby = 0x1D251AA1C80`, on four offsets that were
not part of any search: `+0x88` Num=**19**, `+0x98` Num=**17**, `+0xA8`=`"LbS"`,
`+0xB8`=`"LbE"`. All ✓. Re-read 7 min later: byte-identical, so nothing here is a transient.

## The delegate record is SINGLE-CAST — "entries=3" was never a subscriber count

The 16-byte slot is UE's `FDelegateBase`:

```
+0x00  void* DelegateAllocation
+0x08  int32 DelegateSize      <- allocation size in 16-byte units
+0x0C  int32 padding           <- stale heap garbage
```

`DelegateSize == 3` on **every** bound slot ⇒ a 33–48 byte instance, which is exactly
`vtable(8) + FDelegateHandle(8) + TWeakObjectPtr(8) + member-fn-ptr(16)` = 40 B. The
uniform "3" is one instance *shape*, not three subscribers. Evidence: the allocation is a
single object (read as 3×16 B, "entry 1" is `0xFE3`, not a pointer); the instance vtable's
own accessors return the handle from `+0x10` and the fn ptr from `+0x20`; and the client
tests boundness as `cmp dword[rdi+off+8], 0` then a **virtual call** — `ExecuteIfBound`,
with no invocation-list iteration anywhere.

⚠ `+0xC` reads `0x1D2` — the high dword of this process's heap addresses — **on unbound
slots too**. A `TArray` with null Data cannot have `Max=466`. That garbage is what made the
record look like `{Data, Num, Max}`.

## The bound set: 23 slots, enumerated at 8-BYTE stride

```
+0x1f8  +0x208  +0x228  +0x238  +0x248
+0x12c0 +0x12d0 +0x12e0
+0x1570 +0x1590 +0x15a0 +0x15c0 +0x15d0 +0x15f0 +0x1600 +0x1610
+0x1630 +0x1640 +0x1650 +0x1660 +0x1670
+0x1a00 +0x1a20
```

Confirmed instance-by-instance live: a real delegate allocation **begins with a
module-address vtable**. 23 of 50 candidates passed; controls were a known delegate
(accepted) and the `"LbS"` FString buffer (rejected — it decodes as `0x530062004C`).

The 16 bound slots that **no** notif case broadcasts are response / socket-lifecycle
delegates: `+0x1f8 +0x208 +0x238 +0x248 +0x12c0 +0x12e0 +0x1570 +0x1590 +0x15a0 +0x15c0
+0x15d0 +0x15f0 +0x1600 +0x1610 +0x1a00 +0x1a20`.

## The enum→name map is MEASURED, and it corrects the shipped list

Read straight out of the live `TMap<FString,uint8>` at `.data` RVA `0x9FFE2D0`
(`Elements.Data=0x1D230AF9280`, **ArrayNum=33**, Max=36, dense, `FirstFreeIndex=-1`).
That is the exact byte `HandleNotif` dispatches on:

```
0x4B02CFA  add rcx, qword[rip -> 0x9FFE2D0]   ; element base
0x4B02CF6  shl rcx, 5                         ; stride 32
0x4B02D01  lea rcx, [rcx+0x10]                ; value byte
0x4B02D0E  movzx r15d, byte[rcx]              ; enum
0x4B02D2A  mov ecx, dword[rdx+rax*4+0x4b04978] ; jump index = enum-1
```

The 33 value bytes are a **perfect permutation of 1..33**, and map slot order ≠ enum order
(slot 9 carries enum 12), so this is demonstrably a value field and not a slot index.

**Verdict: `.rdata` name order is CONFIRMED for enum 1–31 and REFUTED at 32–33.**

| position | `vocabulary.go` said | MEASURED |
|---|---|---|
| enum 32 | `errorNotif` | **`signalingP2PNotif`** |
| enum 33 | `messageSessionNotif` | **`errorNotif`** |
| — | "`signalingP2PNotif` is NOT a dispatch case" | **it IS — enum 32** |
| — | `messageSessionNotif` is one of the 33 | **absent from the v1 map entirely** |

Verified independently a second time by reading the three key buffers back verbatim:
enum 24 → `"dsNotif"`, enum 32 → `"signalingP2PNotif"` (Num=18 → 17 chars), enum 33 →
`"errorNotif"` (Num=11 → 10 chars). `messageSessionNotif` would need Num=20.

⚠ `messageSessionNotif` being absent from **this** map does not make it undispatchable —
it is simply not a v1 enum member; prior RE puts it on a separate exact-match handler at
`.text 0x4B07E80`, **not re-verified here**.

★★ **`idx 23 == dsNotif` is now MEASURED, not inferred** — the shape-A "descriptor" is a
plain `FString` whose buffer *is* the type name (`0x9FFE6F0`→`"dsNotif"`,
`0x9FFE810`→`"partyDataUpdateNotif"`, `0x9FFE860`→`"matchmakingNotif"`). CLAUDE.md's
"INFERRED from `.rdata` order" caveat can be dropped. **S117's unbound finding is
unaffected — it was about the right case.**

### Root cause of the tail error: two boundary mistakes that CANCELLED into a plausible 33

The window `0x8601A20..0x8602730` **excluded** `signalingP2PNotif` (`0x86018F8`, 0x128
bytes below the lower bound — structurally uncatchable, and the exclusion was then written
up as a property of the game) and **included** `messageSessionNotif` (`0x8602730`, exactly
the upper bound, i.e. the first string *after* the block, pulled in by an inclusive
endpoint). The block also contains `partySendNotifResponse`, a Response — so it only ever
held 32 real types. Two errors in opposite directions summed to the expected count.

⚠⚠ **`vocabulary.go`'s own comment warned about exactly this failure mode** ("two mistakes
produce 32 — a plausible-looking count that is wrong in both directions at once") and then
committed a *different* pair of the same shape. And `push_test.go:510` asserted
`signalingP2PNotif` was absent — **the test that would have caught the error had ingested
the error** (method rule 9). Both are fixed.

## Payload structs for the 7 (from `schema.txt`; FK-14 rules applied)

| type | struct | fields |
|---|---|---|
| `disconnectNotif` | `FAccelByteModelsDisconnectNotif` | Message:Str |
| `userStatusNotif` | `FAccelByteModelsUsersPresenceNotice` | UserId:Str, **Availability:Enum[T]**, Activity:Str, Platform:Str, LastSeenAt:DateTime |
| `acceptFriendsNotif` | `FAccelByteModelsAcceptFriendsNotif` | **FriendId**:Str |
| `requestFriendsNotif` | `FAccelByteModelsRequestFriendsNotif` | **FriendId**:Str |
| `unfriendNotif` | `FAccelByteModelsUnfriendNotif` | **FriendId**:Str |
| `cancelFriendsNotif` | `FAccelByteModelsCancelFriendsNotif` | **UserId**:Str |
| `rejectFriendsNotif` | `FAccelByteModelsRejectFriendsNotif` | **UserId**:Str |

⚠ **The friends family splits its field name**: accept/request/unfriend use `FriendId`;
cancel/reject use `UserId`. Getting it wrong is SILENT — UE's `JsonObjectStringToUStruct`
ignores unknown keys, so the payload arrives empty and the null looks like "no listener".
⚠ `[T]` = type-unverified per FK-14 (container inner + enum underlying types are ~70 %
wrong in any usmap this project has produced). Field names and scalar types are trustworthy.
⚠ The type→struct mapping is `[I]` (SDK naming convention); the field lists are `[M]`.

## Instrument artifacts caught this session — four, three of them mine

1. **A hand-computed VA, one page low.** `base + 0x9FFE2D0` was added by hand with a
   dropped carry → `0x7FF7D1EED2D0` instead of `0x7FF7D1EEE2D0`. The memory one page down
   decodes as plausible UObjects (vtable, flags `0x41`, consecutive InternalIndex), so it
   read as a real anomaly and was briefly written up as "the map points at UObjects". It
   also sent a subagent chasing it. ⇒ **the "recompute, never retype an RVA" rule is not
   enough — recompute with a machine.** Hand arithmetic is an instrument too.
2. **RVA by digit-stripping.** `call 0x7ff7c8e904f0` was recorded as RVA `0x8E904F0` by
   dropping leading digits instead of subtracting the base; the real RVAs are `0xFA04F0`
   (hash) and `0xFE6520` (Find). The captured "Find disassembly" in
   `scratchpad/s118/map-and-find.txt` is therefore `.rdata` garbage — **do not use it.**
3. **Pool adjacency used as a type discriminator.** `Lobby+0x1a00`'s allocation sits
   beside the `+0x88`/`+0x98` FString buffers, so it was called a string. It is a
   **raw-method delegate bound to Lobby itself** (`+0x18` = `0x1D251AA1C80`). Adjacency
   says nothing about type; **the vtable does.** ⚠ This was committed *in the same
   sentence as a rule about how to bound the table correctly* — method rule 13's shape,
   again.
4. **A 16-byte stride that could not see half the lattice.** Several members sit at
   offsets ≡ 8 (mod 16) — the same alignment that puts LbS/LbE at `+0xA8`/`+0xB8`. The
   0x10-stride scan structurally could not see `+0x228`, and `+0x228` is
   **`disconnectNotif`** ⇒ the miss changed a conclusion (6 types, not 7), not just a
   tally. Both the S117 scan and the first S118 scan had it.

★ And one inherited: **the S117 bound list was truncated at 12 of 16 and ended in a literal
`...`**. Four of the hidden offsets (`+0x1640/+0x1650/+0x1660/+0x1670`) are four of the
seven answers. Joining against the truncated list yields **2** hits. **Never join against a
list that ends in an ellipsis.**

## Reusable technique

★★ **Drive the code path from the backend to force `.text` decryption, then dump** (S117)
— and **then keep the process alive**. Holding that one process open is what made S118
almost entirely free: same ASLR, same heap, decrypted pages, live sockets, and a
still-connected `/lobby` push channel to test against.

## Status of the push channel at time of writing

`/lobby` socket up 7171 s, 36 pushes; messenger up 7171 s with **0** reconnect churn (the
S117 TEXT heartbeat reply is holding). `Loki.log`: `Type:` 41, `Raw Lobby Response` 61.

⚠ `server/ags.exe` on disk was built **15:50 local**, one commit behind `b926d8f` (16:02).
The envelope fix (`1f2b06e`) is present and empirically working, but **rebuild before
drawing any server-side conclusion from HEAD source.**

## ★★★★★ FLOWN THE SAME SESSION — A PUSHED NOTIF DROVE THE CLIENT, FIRST TIME EVER

The map was tested against the live process it was derived from. **Pre-registered signal**
(chosen before the push, baseline 0): push a bound type carrying a **fabricated user id that
exists nowhere else**, and watch for the client to go resolve it — an observable in OUR OWN
`capture.log`, independent of client log verbosity.

```
18:14:58.828  WS PUSH[s118-boundprobe-requestFriends] -> /lobby TEXT (68 bytes)
              "type: requestFriendsNotif\nfriendId: f15118aaaaaaaaaaaaaaaaaaaaaaaaaa"
18:14:59.104  GET /iam/v4/public/namespaces/supervive/users/f15118aaaaaaaaaaaaaaaaaaaaaaaaaa
```

**+276 ms.** The client took an id that appears nowhere but in our frame and fetched that
user's profile — `USocialManager` resolving the requester of an incoming friend request.
⇒ **receive → envelope-strip → parse → route → deserialize → broadcast → SUBSCRIBER ACTS.**
The chain is closed end to end for the first time in this project's history.

### Three arms, one socket, one session — binding and payload isolated separately

| arm | type | delegate | payload | client action |
|---|---|---|---|---|
| 1 | `requestFriendsNotif` | **BOUND** `+0x1640` | real `friendId` | **GET at +276 ms** |
| 2 | `requestFriendsNotif` | **BOUND** `+0x1640` | *no fields* (S117 sweep, 20:58:56Z) | **none** |
| 3 | `dsNotif` | **UNBOUND** `+0x1550` | full 11 fields, 190 B | **none** |

- **Arm 1 vs 3 isolates BINDING**: arm 3 carried the *richer* payload on the same socket with
  the same envelope and produced nothing; its `MatchID` (`fk15-match-0001`) occurs **exactly
  once** in the whole capture — our own push line. The client never referenced it.
- **Arm 1 vs 2 isolates PAYLOAD**: the same bound type with an empty `FriendId` did nothing,
  which is why the S117 33-type sweep looked inert even on types that *do* have a listener.
  ⚠ **A sweep of bare `{"type":X}` frames cannot detect a live handler.** Do not read the
  S117 sweep's silence as evidence about any type.
- **Denominator:** `GET /iam/v4/public/namespaces/supervive/users/` appears **1 time in the
  entire 7 MB capture log**, so the hit cannot be background traffic.

★ **The model is now PREDICTIVE, not just descriptive**: it said 7 types can move the client
and 26 cannot, and the one bound type tested moved it while the unbound one didn't.

## What this unlocks, and what is still open

- **Push a friends notif and watch `USocialManager` react.** That is the first push in this
  project's history aimed at a delegate known to have a listener. Start with
  `requestFriendsNotif {FriendId: <id>}` — one field, and an incoming friend request is a
  visible UI event.
- **`disconnectNotif` is reachable and destructive-ish** (it likely tears down the socket
  view) — useful as a *positive control that the channel moves the client at all*, but do
  not lead with it.
- **Open:** `+0x1570` and `+0x15c0` share method `+0x5854a60`; fold multiplicity not
  measured, so that RVA is not identifying.
- **Open:** what the 16 non-notif bound delegates are (response surface).
- **Open:** anything past `Lobby+0x2000` is unscanned in both S117 and S118.
- **Unverified:** `messageSessionNotif`'s separate v2 handler at `.text 0x4B07E80`.
