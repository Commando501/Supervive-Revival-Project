# FK-15 — "Server→client WebSocket push is measured non-functional" is REFUTED

**Session S117, 2026-08-13. Offline audit + one new harness — then FLOWN AND CONFIRMED LIVE.**

> ## ✅ SETTLED BY DIRECT EXPERIMENT, 2026-08-13 08:48:54
>
> Probe 1 was pushed at a live client and **the client printed our sentinel back**:
>
> ```
> [2026.08.13-08.48.54:314][559]LogJson: Warning: JsonObjectStringToUStruct - Unable to parse json=[FK15-PROBE-FROM-AGS]
> [2026.08.13-08.48.54:317][559]LogMessenger: Warning: Messenger recieved unexpected message: FK15-PROBE-FROM-AGS
> ```
>
> One TEXT frame, 19 bytes, on `/notifications/players/{id}`. **Baseline captured immediately
> beforehand was 0**, against **393 same-category `Warning`s** in the same log — so the channel was
> demonstrably emitting and the zero was real. **Server→client WebSocket push works, and it reaches
> the client's application layer.** Full record: `docs/fk15-probe1-live-result-20260813.txt`.
>
> ## ✅ PROBE 2 ALSO FLOWN AND CONFIRMED — the ~60 s reconnect churn is FIXED
>
> Deployed 08:53:12 UTC. Before: the watchdog fired **once per ~61 s, like clockwork**
> (…08:49:09, 08:50:10, 08:51:11, 08:52:13). After: **zero fires**, and the messenger socket held
> **325 s and counting** against a prior maximum of ~61 s. Delivery was 1:1 — 5 client `hb`
> received, 5 TEXT replies sent. Record: `docs/fk15-probe2-live-result-20260813.txt`.
>
> **The flagged side effect was checked, not assumed:** an explicit `conn.Drop()` (the S85 avatar
> path) still forces reconnect + resync — dropped socket, client back in <6 s, and
> `GET /party/parties/…` + `GET /party/players/…` re-issued. **S85 is unaffected.**
>
> ⚠⚠ **TWO INSTRUMENT FAILURES WHILE MEASURING THIS, both nearly written down as results:**
> 1. A background watcher used `rg`, which is **not on PATH in the background shell** (it *is* in
>    the foreground one). Every count came back an empty string, `[ "" -gt "" ]` errored, and the
>    script fell through to printing **`RESULT: HELD`** — a **false PASS that agreed with the
>    hypothesis**.
> 2. The log timestamps are **UTC** while the deploy time was **local** (UTC = local + 5 h). A
>    by-minute histogram over `03.xx` therefore read a window **five hours before the change** and
>    showed the watchdog still firing — a **false FAIL**.
>
> A broken instrument produced first the answer I wanted and then its opposite. The lesson is the
> one this project already knows and keeps re-learning: **self-test the instrument inside the
> harness before trusting a single number it emits** — `command -v`, a positive control and a
> negative control, every time. The rewritten watcher aborts loudly if `curl`/`python` are missing
> or if the probe returns a non-numeric value.
>
> ★ **Two bonus findings from the same 3 ms:**
> 1. **`LogJson`'s silence was NEVER-RAN, not suppressed.** This document (and FK-11's own trap
>    list) treated `LogJson` as a dead detector on the strength of *0 lines in 326 logs*. It fired
>    here, at `Warning`, unprompted. **Nothing had ever handed it malformed JSON.** It is still the
>    wrong detector for the 2026-06-29 `/lobby` probes — that path uses a hand-rolled key:value→JSON
>    converter, not `FJsonSerializer` — but on the **messenger** it is a valid, working instrument.
>    A textbook never-ran-vs-suppressed case, caught live.
> 2. **The heartbeat defect reproduced on cue**: 15 s later, `heartbeat not received in 5 seconds`
>    → `disconnect` → `socket closed wasClean:1 Status: 1000`, exactly as characterised in §3.5.
>    Probe 2 was the fix — since flown and confirmed (see the block above).

> **Verdict: the belief is false as stated, and the evidence it rests on is void.**
> Server→client WebSocket push **demonstrably works** — the client's own SDK logs a receipt for
> every frame our backend sends. The five negative probes could not have detected a reaction
> because every diagnostic category they named was either pinned to `Warning` by the game's shipped
> ini or **does not exist in the binary**. Separately, the probes tested **1 of the client's 33
> server-pushable notification types**, chosen on the basis of a **wrong-token string search** —
> and on the *other* socket, the messenger, we have been sending a **binary** heartbeat that its
> handler provably never receives, across 1,419 connections.

Supersedes the WS-push conclusions in `docs/coverage-audit-s101.md:98` and
`docs/dedicated-server-stub.md:406-478`.

---

## 0. The claim under audit

`docs/coverage-audit-s101.md:98`:

> "The exe declares 16 lobby type-name strings … and server→client push is **measured
> non-functional** (5 negative probes)."

`docs/dedicated-server-stub.md:459-472` turns that into an architectural close:

> "SUPERVIVE's client matchmaking subsystem only acts on `matchmakingNotif` messages that match a
> `ticketId` from a previously-sent `startMatchmakingRequest`… So spoofing the matchmaking flow
> purely via server-pushed messages is **structurally blocked**."

Both are withdrawn below. The second was never measured — it is an inference from a silence that
the instrument could not have broken.

---

## 1. ★★★ Push works. This is measured, and the measurement already existed.

`docs/fk11-live-result-20260809.log`, a verbose menu launch flown 2026-08-09:

```
19.24.20:878 [25] LogAccelByte: Verbose: AccelByte::Api::Lobby::ListIncomingFriends
19.24.20:878 [25] LogAccelByte: Verbose: AccelByte::Api::Lobby::ListOutgoingFriends
19.24.20:878 [26] LogAccelByte: Verbose: AccelByte::Api::Lobby::LoadFriendsList
19.24.21:012 [29] LogAccelByte: Verbose: AccelByte::AccelByteWebSocket::OnMessageReceived
19.24.21:078 [31] LogAccelByte: Verbose: AccelByte::AccelByteWebSocket::OnMessageReceived
19.24.21:146 [33] LogAccelByte: Verbose: AccelByte::AccelByteWebSocket::OnMessageReceived
19.24.21:279 [37] LogAccelByte: Verbose: AccelByte::Api::Lobby::SendSetPresenceStatus
19.24.21:379 [40] LogAccelByte: Verbose: AccelByte::AccelByteWebSocket::OnMessageReceived
```

**`OnMessageReceived` occurs exactly 4 times in the whole run** (`rg -c` — verified independently
of the agent that first spotted it). Our `respondText` (`server/internal/lobby/lobby.go:317-332`)
answers exactly four request types: `listOfFriendsRequest`, `listIncomingFriendsRequest`,
`listOutgoingFriendsRequest`, `setUserStatusRequest`. The four receipts interleave with the four
corresponding client calls.

- **[M]** Four server→client TEXT frames were sent; four `OnMessageReceived` lines were logged.
- **[I, high confidence]** They are the same four. The 1:1 count, the interleaving, and the
  67-210 ms spacing all agree; nothing else was writing to that socket.

Supporting, from `docs/capture.log.prev` **[M]**:

- One `/lobby` socket held **3 h 43 min** — one connect, **zero** closes, zero reconnects. The
  ~60-70 s teardown documented at `coverage-audit-s101.md:99` is specific to `/notifications`,
  **not** to `/lobby`. The push channel is stable for hours.
- Each of the four requests is sent **exactly once** in that window. The client never re-asks —
  i.e. it accepted the answers. Its presence payload then advances
  (`{"a":"Offline",…}` → `{"a":"Menus","pId":"party-9b9d…","pQs":["tutorialNew"],…}`).

⇒ **Transport, framing, parse and SDK surfacing all work.** What has never been shown is that any
*unsolicited* frame produces a *visible* effect — a far narrower claim, and one that has never been
tested with a working instrument.

---

## 2. Why the five negatives are void

All five probes were flown **2026-06-29**, in one 47-minute window. FK-11's verbosity fix was flown
**2026-08-09** — **41 days later**. **[M, `git log`]**

### 2.1 Every detector was blind

The game ships this, in `tools/extractor/out/raw/Loki/Config/DefaultEngine.ini` **[M]**:

```ini
[Core.Log]
LogNet=Warning
LogAccelByteLobby=Warning      ; the lobby message dispatcher
LogAccelByte=Warning           ; the AccelByte WebSocket layer  <-- owns OnMessageReceived
LogOnline=Warning
```

FK-11 established that **ini is the last word** in this build (`fk11-log-verbosity-settled.md:178-186`).
`configs/set-log-verbosity.ps1` did not exist until **2026-08-10**.

Census over **326 archived client `Loki.log` copies** **[M]**:

| detector cited by the probes | lines | logs containing it |
|---|--:|--:|
| `LogJson:` | **0** | **0 / 326** |
| `LogAccelByteLobby:` | **0** | **0 / 326** |
| `LogNet:` | **0** | **0 / 326** |
| `LogPlatformLobby:` | **0** | **0 / 326** |
| `LogPlatformQuery:` | **0** | **0 / 326** |
| `LogAccelByte:` | 1,042 | 312 / 326 — **100 % of it three startup warnings** |
| *control* `LogMessenger:` | 6,027 | 297 / 326 |
| *control* `LogPartyManager:` | 291 | 291 / 326 |

The controls emit in ~90 % of logs, so the census works. **Not one detector the probes relied on
has ever produced a line in this project's entire client-log history.**

### 2.2 ★ Two of the six detector categories do not exist

Controlled UTF-16LE + ASCII scan of `dumps/tutorial-hero/SUPERVIVE-Win64-Shipping.dump.exe`
(`.rdata` 100 %) **[M]**:

| token | utf16 | ascii |
|---|--:|--:|
| `LogPlatformLobby` | **0** | 0 |
| `LogPlatformQuery` | **0** | 0 |
| `LogAccelByteLobby` (the real name) | 1 | 0 |
| `LogJson` | 1 | 0 |
| *pos control* `LogMessenger` | 1 | 0 |
| *neg control* `LogZzzNotARealCategory` | 0 | 0 |

`LogPlatformLobby` and `LogPlatformQuery` occur **exactly once in this entire repository — in
`docs/dedicated-server-stub.md:407`, the sentence asserting their silence.** Their zeros were
guaranteed by construction.

### 2.3 What the probes could and could not exclude

`Warning` still prints Warning/Error/Fatal, so the probes **did** exclude a loud, warning-level
rejection. They could **not** distinguish between:

- (a) the frame never reached the client's socket layer,
- (b) it arrived, parsed, dispatched, and was deliberately ignored,
- (c) it arrived and was dropped before dispatch.

Those three are exactly what FK-15's conclusion adjudicates between. The instrument was blind to
all three.

### 2.4 The probes were not single-variable, and the observation is gone

| probe | channel | payload | free variables |
|---|---|---|--:|
| #1 | HTTP `/core-game/players/{id}` | `hasActiveMatch` + `matchInfo{9}` + 4 wrappers | **14 keys** — incl. `hasActiveMatch`, later measured **absent from the exe** |
| #2 | HTTP | `Allocating`→`AwaitingReady` | **1** — the only clean step in the set |
| #3 | **WS `/lobby`** | `matchmakingNotif` status=done | **~35 field names**, incl. `dsInfo` replicated under 4 aliases |
| #4 | HTTP | `CoreGamePlayer` reshaped | **~27 keys**, shape *and* field set changed together |
| #5 | **WS `/lobby`** | 2-frame start→done | **≥4 design variables** + ~32 field names |

Against the project's own convention (`CLAUDE.md`, "Code conventions": *"Bundled tests (10 changes
at once) have repeatedly produced ambiguous results"*), 4 of 5 fail.

⚠ **The primary observation no longer exists.** `docs/capture.log` is **untracked** and rotates at a
size cap; the two survivors are dated 2026-08-13. Searching both for `phantom` and
`matchmakingNotif` returns **0**. No client `Loki.log` from 2026-06-29 survives. The doc's
*"capture.log shows the frames going out"* cannot be re-checked. **[M, absence]**

⚠ **Dwell time.** Commit #4 → #5 is **4 min 42 s**; #5 → the "probes exhausted" close is **5 min
43 s**. Each window had to contain a code edit, an `ags` rebuild, a full client launch to menu, a
3 s + 2 s push schedule, and reading the log. Not enough time to observe a delayed reaction even in
principle.

---

## 3. ★★★ The probes tested 1 of 33 notif types — and picked it via a wrong-token search

### 3.1 The real vocabulary — **33 types, every one with a bound dispatcher case**

The client's lobby message-type names live in **one contiguous NUL-terminated UTF-16LE table**
in the `.rdata`-complete dump. The Response/Notif sub-block **`0x8601A20`–`0x8602730`** holds
**exactly 33** notification names. **[M]**

★ **They are corroborated by an independent count.** `Lobby::HandleNotif` (`.text 0x04B02C80`)
dispatches through a `TMap<FString,uint8>` at `.data 0x9FFE2D0` into a **33-entry jump table at
`.text 0x04B04978`** — decoded at `0x04B02CE0`–`0x04B02D34` as `hash(type)` → `FindIndex` →
`enum = *(byte*)(data + idx*32 + 0x10)`, with `if (enum-1 > 0x20) → default`, i.e. values 1…33.
**33 names == 33 cases.** ⇒ **every one of these types, `dsNotif` and `matchmakingNotif` included,
has a dedicated dispatcher case.** None is a string that only exists in a sender. **[M]**

They are enumerated in `server/internal/lobby/vocabulary.go` and served at `GET /api/ws/vocabulary`.

⚠ **This document originally said 32, and that was wrong in two directions at once** — worth
recording because the wrong number looked entirely plausible:

- an `endswith("Notif")` filter **silently drops `userBannedNotification` and
  `userUnbannedNotification`**, which are real dispatch cases; and
- a scan window opened wider than the sub-block **adds `signalingP2PNotif`** (`0x86018F8`), which
  sits *inside the Request block* surrounded by `*Request` names and is **not** one of the 33.

The two errors nearly cancelled. The fix is not a better regex — it is **tying the recovered table
to an independent count** (the jump table), which is what makes 33 trustworthy.

**The five probes pushed exactly one of the 33: `matchmakingNotif`** — the single worst choice for
a cold-menu test, being the one plausibly gated on a ticket the client never issued. The project's
own architectural conclusion says exactly that, then generalises that one type's gate to the whole
push mechanism.

### 3.1b ★ The dispatch chain, and what it does NOT consult

| function | RVA | role |
|---|---|---|
| `Lobby::OnMessage` | `0x04B0ADB2`–`0x04B0B43B` | parse + top-level route |
| `Lobby::CheckMissingNotification` | `0x04B0EB40` | sequence / dedup gate |
| `Lobby::HandleMessageSessionNotif` (v2) | `0x04B07E80`–`0x04B084A0` | v2 envelope |
| `Lobby::HandleMMv2Notif` | `0x04B07CB0`–`0x04B07E73` | matchmaking-v2 topic switch |
| `Lobby::HandleNotif` (v1) | `0x04B02C80` | the 33-case switch |

`OnMessage` reads `type`, then: `== messageNotif` → sequence gate; `== messageSessionNotif` → v2
handler; contains `"Response"` → response switch; contains `"Notif"` → `HandleNotif`; else logs
*"Error cannot parse message. Neither a response nor a notif type."* **[M]**

⇒ **Any type containing `Notif` that is not `messageNotif`/`messageSessionNotif` reaches the
dispatcher with NO precondition** — no connection state, no id, no ticket, no sequence.

**The wire format is confirmed correct.** The binary carries its own templates:
`"type: %s\nid: %s"` (`0x08603340`), `"%stype: messageNotif\ntopic: %s\npayload: %s%s"`
(`0x08612430`), `"%stype: messageSessionNotif\ntopic: %s\npayload: %s%s"` (`0x08612490`). JSON
appears **only inside the `payload:` value**, never at top level. Our `buildLobby` already emits
exactly this shape — **the format was never the problem.**

### 3.1c ★★ The "ticket id" conclusion is refuted where the code is readable

`dedicated-server-stub.md:459-472` asserts the client acts only on `matchmakingNotif` matching a
ticket from a prior `startMatchmakingRequest`. Against disassembly **[M]**:

- `OnMessage` consults **no** ticket, matchmaking state, or session id — only `type` (and `id` for
  responses).
- `HandleNotif`'s dispatch consults **no** ticket — it is `hash(type)` → map → jump table.
- `HandleMMv2Notif` (451 B, fully decrypted, read end to end) has **no ticket gate at all**: it
  logs the topic, deserializes, calls the sequence gate, then switches on the topic enum.

★ **There IS a real gate — a different one.** `CheckMissingNotification` (`0x04B0EB40`)
deserializes into `FAccelByteModelsUserNotification` and enforces a
**`sequenceID` / `sequenceNumber` dedup** contract (`Notification has invalid sequence…`,
`Duplicate notification detected…`, `Missing notification detected…`). It applies **only to
`messageNotif`-shaped envelopes**, not to plain v1 `*Notif` frames — and it has nothing to do with
matchmaking tickets.

⚠ **Honest limit:** the per-case bodies for cases 8–31 sit on pages that are **all-zero in both
dumps** (`0x04B03000`, `0x04B05000`, `0x04B06000`) — demand-decrypt, never executed, because
nothing has ever pushed those notifs. SDK-side **routing** is proven; whether *Loki* binds the
delegates each case broadcasts is **coverage-blocked, not measured**.

### 3.1d ★ A v2 path exists, and a UTF-16-only scan cannot see it

The doc's ABSENT list also missed the entire AccelByte **v2** vocabulary, because those names are
stored **ASCII** (UHT enumerator names), not UTF-16 **[M]**:

- `messageSessionNotif` — present (`0x08602730`) **with a dedicated handler at `0x04B07E80`**.
- `EV2SessionNotifTopic` ships **21 enumerators** including **`OnDSStatusChanged`**
  (`0x0859F7B8`), `OnSessionJoined`, `OnGameSessionUpdated`; `EV2MatchmakingNotifTopic` ships 5
  (`OnMatchFound`, `OnMatchmakingStarted`, …).

So *"`sessionNotif`/`dsStatusChangedNotif` absent ⇒ no v2 path"* is false twice over: wrong token
spellings **and** an encoding the scan could not see.

### 3.2 ★ Why that type was chosen: `dsNotice` vs `dsNotif`

`docs/dedicated-server-stub.md:443-450` records:

> `ABSENT: dsNotice, dsClaimedNotif, serverClaimedNotif, …`
> "So … The `dsNotice` classic DS notice is absent — DS info is presumably delivered inside one of
> the `*Notif` envelopes (we tried matchmakingNotif …)"

**The AccelByte v1 token is `dsNotif`, not `dsNotice`.** `dsNotif` is present — it is a member of
the table above. `dsNotice` returns 0 because it is not a name this SDK uses. **[M]**

So the message type purpose-built to carry dedicated-server connection info **was in the binary the
whole time**, its absence was a search artifact, and that artifact is what redirected two probes
onto `matchmakingNotif`.

### 3.3 ⚠ Do not repeat the "10×" framing

A naive substring count reports `dsNotif` **10 times**, inviting "5× more present than
`matchmakingNotif`". **Nine of those ten are matches inside other tokens** — `acceptFriendsNotif`,
`requestFriendsNotif`, `cancelFriendsNotif`, `rejectFriendsNotif`, `AccelByteModels*FriendsNotif`
(all contain "Frien**dsNotif**"), plus `UpdateBoun**dsNotif**yStreamingRadiusChangeRatio`.

**As standalone tokens, `dsNotif` and `matchmakingNotif` occur once each** (the latter's naive
count of 2 includes `rematchmakingNotif`). They are *equally* present — which is all the argument
needs. **Count tokens, never substrings.**

This one is worth keeping in view: the same trap then caught a *test assertion* written during this
session (`strings.Contains(payload, "matchmakingNotif")` matches `type: rematchmakingNotif`). The
production code was correct; the instrument was not.

### 3.4 The "4 of 16" ratio

The **16** is a hand-picked scan list, not an enumeration, and it is wrong three ways **[M]**:

1. Two of the 16 are not message types (`LobbyMessage` is a class; `MMv2` a version token).
2. It **excludes two of its own numerator's four items** — we answer
   `listIncomingFriendsRequest` and `listOutgoingFriendsRequest`, neither of which is in the 16,
   though both are in the binary.
3. The real count is **119 message types / 43 requests**, so the served fraction is **4 of 43**.

---

## 3.5 ★★★ The OTHER socket: our heartbeat has never reached the client's handler

The messenger (`/notifications/players/{id}`) is a **second, entirely different protocol**, and it
turns out we have never delivered anything on it either — for a reason nobody had looked for.

⚠ **First, a name correction:** the class is **`UMessengerManager`**.
**`LokiPlatformMessenger` does not exist in the binary** (0 hits, both encodings) — it appears only
in this project's own comments. **[M]**

`UMessengerManager::OnMessage` (`.text 0x57C8F00`) parses each **TEXT** frame as **one JSON
object** into `FNotificationMessage` (`schema.txt:37963`, all scalar/Str types ⇒ FK-14's
trustworthy class) **[M]**:

```
FNotificationMessage { Resource FString@0x00; Version int64@0x10; Payload FString@0x18 }
```

Dispatch: `Resource == "hb"` clears the heartbeat watchdog; otherwise **15 registered prefixes**
are matched by `StartsWith`, and the dominant effect is *"resource X is at version N → if N beats
my cache, re-issue the HTTP GET for X"*. ⚠ 15 is a **floor** — the first enumeration instrument
found 7 and missed 8 registered through a different call shape.

### ★★ Our 30 s proactive binary `hb` never reaches the handler

Log census over 1,419 connections, **re-confirmed independently on a second, later log** (23 / 22 /
0 / 0) **[M]**:

| line | count |
|---|--:|
| `Messenger connection established` | 1419 |
| `heartbeat not received in 5 seconds` | 1418 |
| `Messenger recieved message` | **0** |
| `Messenger recieved unexpected message` | **0** |

`Messenger recieved unexpected message: %s` logs at **`Warning`** on a JSON parse failure. If our
binary `hb` had reached `OnMessage`, it would have failed to parse and logged **1,418 times**. It
logged **zero** — **in a log where the same category emits 1,418 Warnings.** That built-in positive
control is what makes this a *clean negative* rather than a muted channel: **binary frames are
dropped before the handler** (the messenger binds 4 WS delegates; `OnRawMessage`/`OnBinaryMessage`
is not among them).

⇒ **The messenger has never delivered a single frame to its application layer**, and the ~60 s
reconnect churn **cannot be fixed by tuning our push interval** — `lobby.go`'s
`messengerHeartbeatInterval` is invisible to the client by construction. Measured: connect→kill
median **60.0 s**, exactly **one** heartbeat per connection. The fix is to reply in **TEXT**:
`{"Resource":"hb","Version":0,"Payload":""}`.

⇒ `coverage-audit-s101.md:99`'s *"this is a **format** problem, not a delivery problem"* is **half
right, and the wrong half is load-bearing**. It is both, and **delivery fails first** — the project
has only ever sent binary, so format and delivery were never separable until now.

### ★ A better lever than S85's socket drop

Each of the 15 prefixes has its own **per-resource** refetch. A single
`{"Resource":"/party/parties/<id>","Version":n+1}` frame refetches **exactly one** resource — no
teardown, no reconnect backoff, no collateral refetch of the other 14. S85's *"the client applies
the party model only on messenger reconnect"* is a true observation about a client that **has never
received a message on this socket**; reconnect was the only trigger available because the real
trigger had never been exercised. If that lands, `lobby.go`'s recorded *"~1 s reconnect floor, not
backend-controllable"* stops being true.

### ⚠ The ignorance map's proposed experiment would have produced a guaranteed null

`ignorance-map-s101.md:1036` proposes pushing a `partyGetInvitedNotice` / `UserNotification_PartyInvite`
frame. **[M]** `partyGetInvitedNotice` has **0 hits** in either encoding (the real lobby token is
`partyGetInvitedNotif`), and `UserNotification_PartyInvite` is a **client-side `UObject` built by
`UUserNotificationManager` from local models — not a wire type at all.** The genuine invite path is
a messenger version-bump nudge → `GET /party/players/{id}` → `UPartyManager` → toast; **the invite
content never crosses the socket.** Do not spend a launch on the proposed frame — that is the third
wrong-token instance inside this one investigation.

---

## 4. The recorded blocker is obsolete

`dedicated-server-stub.md:468-472` explains the null as:

> "The client never sends `startMatchmakingRequest` from a fresh menu **because of the upstream
> hero-asset gate** (Track A; documented as exhausted…)"

That gate was **solved on 2026-07-05** (`c1eaf88`, the first `catalog_store_fix.cpp`) — **6 days
after the probes** — and the roster, store and party have been live ever since. The probes have
never been re-run. `startMatchmakingRequest` is still absent from the wire, but **the reason
recorded for its absence no longer holds.** **[M]**

---

## 5. Transport exonerated by measurement (a hypothesis killed, not confirmed)

The evidence has a suspicious split: short server→client frames (2 B `hb`, ~60 B friend responses)
work, while the ~1.5 KB phantom pushes appear to vanish. That is precisely what a broken RFC 6455
**extended payload-length** path would look like — and it would have silently voided all five
probes at the transport layer.

Tested rather than eyeballed. `server/internal/lobby/push_test.go` stands up the real
`lobby.Handle` over a real TCP socket, completes a real handshake, and reads our frames back with a
**deliberately independent** RFC 6455 decoder (so a bug shared between our reader and writer cannot
hide). Payload sizes 1, 2, 60, 125, 126, 127, **1462** (the phantom size class), 65535, 65536 —
every length boundary. **All pass**: FIN set, unmasked, exact byte-for-byte payload. **[M]**

⇒ **Our WebSocket transport is not the failure.** Recorded so nobody spends a session re-deriving it.

---

## 6. What was built

**`server/internal/lobby/push.go` + `server/internal/admin/ws.go` + the panel's "WS Push" tab.**

The reason FK-15 sat at N=5 for ~40 sessions is that each probe cost a source edit, an `ags`
rebuild and a full game launch. The console makes a probe cost a button press.

| endpoint | purpose |
|---|---|
| `GET /api/ws/sockets` | every live socket, by handle — **both** `/lobby` and the messenger |
| `POST /api/ws/preview` | assemble a frame and show the exact bytes, **with no game running** |
| `POST /api/ws/push` | send one operator-authored frame |
| `POST /api/ws/sweep` | one minimal frame per type, spaced — **one launch walks all 32** |
| `GET /api/ws/vocabulary` | the 33 notif types, flagged with what has already been probed |
| `POST /api/ws/drop/{handle}` | the **positive control** (see below) |

Properties chosen to stop this harness manufacturing its own false negatives:

- **Exactly what you asked for.** The builder adds no field, reorders nothing, and emits **no
  `id:` line unless you supply one** — deliberately unlike `buildLobby()`, since an auto-generated
  id is a 21st uncontrolled variable on an unsolicited notif.
- **A label is mandatory.** Every push is written to `capture.log` as `WS PUSH[label] -> …` with
  the full payload, **before** the write, so a frame that kills the socket is still on record. The
  original probes are hard to reconstruct precisely because they were not.
- **Pushing into the void is an error, never a cheerful 200** — delivery and effect must stay
  separable.
- **Unknown JSON fields are rejected**, so a typo fails loudly instead of shipping a frame missing
  the field you meant to test.
- **The Drop button is the positive control.** The messenger drop is the project's one demonstrated
  server→client control signal (S85's avatar resync). If a drop still causes its resync while your
  frame does nothing, the socket was alive and the null belongs to **the frame**.
- **Both channels are addressable.** The messenger has never had an application frame pushed at it
  — only binary `hb` — yet it is the channel already proven to drive client behaviour. Its
  exclusion was an accident of where the first probe happened to be written.

⚠ **A sweep is a scan, not an experiment.** Frames are individually minimal and individually
labelled, but not isolated from each other in time. **Any hit must be re-run as a single frame,
alone, before it is written down as a result.**

Covered by 19 tests (`push_test.go`, `ws_test.go`), including the transport matrix, builder
determinism, sweep abort-on-dead-socket, and vocabulary integrity. `PANEL_LIVE=1 go test
./internal/admin -run TestPanelLive` serves the real panel for UI work with no game running.

---

## 6b. ★★ `LogAccelByte` is NOT the dispatcher's category — and the dispatcher is still muted

This is the sharpest practical finding, and it would have silently wasted the next launch.

The lobby dispatcher logs to **`LogAccelByteLobby`**, a *different* category. Its live state, read
straight out of the dumped `.data` at **`0x9FFE2A0`**, is `03 00 03 07` ⇒
**Verbosity = Warning(3), DefaultVerbosity = Warning(3), CompileTimeVerbosity = VeryVerbose(7)** —
fully compiled in, deliberately muted. **[M]**

Discriminated against `LogAccelByte` in `docs/fk11-live-result-20260809.log` **[M, verified
independently]**: that run had `LogAccelByte=Verbose` and contains **52 `LogAccelByte:` lines
including 4 × `OnMessageReceived`** — so frames were provably arriving — and **zero
`LogAccelByteLobby:` lines and zero `Lobby.cpp` format strings** (`Type: %s`, `JSON Version: %s`,
`Sending request: %s`). ⇒ **raising `LogAccelByte` does not make the dispatcher talk.**

Every category in the new `-Preset Ws` was checked for existence before shipping (all present;
`LogPlatformLobby` / `LogPlatformQuery` deliberately excluded because they do not exist):

| category | why |
|---|---|
| `LogAccelByteLobby=VeryVerbose` | **the dispatcher.** `Type: %s` (site `0x04B0B12B`) needs VeryVerbose and prints the type of **every** routed frame |
| `LogAccelByteNotificationBuffer=VeryVerbose` | the real sequence/dedup gate |
| `LogAccelByte=Verbose` | `OnMessageReceived` — the receipt line + the free positive control |
| `LogAccelByteMessagingSystem`, `LogAccelByteWebsocket`, `LogNet`, `LogMessenger` | supporting / control |

---

## 7. What to do next

The seven probes below are pre-authored in `server/internal/lobby/vocabulary.go`
(`RecommendedProbes`) and loadable with one click in the panel, which also **auto-targets the right
socket** — a messenger frame sent on `/lobby` tests nothing.

**Probes 1–3 are on the MESSENGER and 1–5 need no ini change at all.**

> ✅ **STATUS 2026-08-13: probes 1, 2 and 3 are FLOWN AND CONFIRMED — do not re-fly them.**
> 1 settled FK-15 (sentinel echoed back), 2 shipped as `enableTextHeartbeatReply` (watchdog fires
> ~1/min → **0**), 3 shipped as `enableTargetedResync` (refetch **and apply**, no teardown).
> **Probes 4–7 remain open**, as does sweeping the other 30 notif types.

1. ★★★ **A non-JSON sentinel on the messenger — the single best probe available.** Send the literal
   text `FK15-PROBE-FROM-AGS`. `OnMessage` will fail to parse it as JSON and log
   `Messenger recieved unexpected message: FK15-PROBE-FROM-AGS` at **`Warning`** — visible today.
   Its baseline is a **measured zero across 1,419 connections**, in logs where the same category
   emits 1,418 Warnings. **One line, echoing our own sentinel back, settles FK-15 outright.**
2. ★★★ **Heartbeat reply in TEXT** — `{"Resource":"hb","Version":0,"Payload":""}` on receipt of the
   client's binary `hb`. Expected: the 60 s reconnect churn **stops**. Independently valuable, and
   it turns the ~55 s usable window per connection into an indefinite one.
   ⚠ Re-verify S85 avatar latency afterwards — it removes the free periodic resync.
3. ★★ **Targeted resync** — `{"Resource":"/progression/players/<id>","Version":<the version the
   document will carry>}`. That handler has **no resource equality check**; the only gate is
   `Version >` cache. Success appears in **our own `capture.log`** as a `GET` — no client log, no
   verbosity change, no screenshot.
   ⚠⚠ **This originally read `"Version":9999999`. DO NOT DO THAT — it was measured to cause an
   UNBOUNDED REFETCH LOOP** (46 fetches in 4 s, ~one per 70 ms, cleared only by restarting `ags`):
   the client caches the pushed version, refetches, receives a document with a LOWER version, still
   believes itself stale, and asks again forever. Pass the version the document will actually carry.
   For resources served as empty catch-alls (no version in the doc) any small positive value works —
   that is why the `/match-history` probe succeeded with `Version 7`.
4. ★★★ **`messageNotif` with an undeserializable payload — the `/lobby` arrival test, no ini change.**
   `type: messageNotif\ntopic: fk15-probe\npayload: {"notAField":1}`.
   `OnMessage` routes `messageNotif` into `CheckMissingNotification` **unconditionally**, which
   logs at **`Warning`** on a deserialize failure — a level the shipped ini already allows. This is
   the positive control the entire five-probe corpus never had: it separates *"our frame never
   reached `OnMessage`"* from *"it arrived and was absorbed."* **Run this first.**
5. ★★★ **`messageSessionNotif` with a bogus topic** — same no-ini-change arrival test on the v2
   code path, whose default branch also logs at `Warning`.
6. ★★ **`dsNotif`** (`status/ip/port`) — the v1 type that carries DS connection info, with a bound
   dispatcher case and no precondition. Never tried, because the doc grepped `dsNotice`.
7. ★★ **`matchmakingNotif` re-run unchanged, with `LogAccelByteLobby=VeryVerbose`.** `Type: %s`
   then prints for every routed frame: if it prints, 2026-06-29's "silent absorption" was a
   **logging** null, not a **routing** null. If it does not, the frame never reached `OnMessage`.

Then: **sweep the other 29 types** in one launch (~96 s), and re-run any hit as a single frame.

Also worth doing: **make `docs/capture.log` survivable.** The wire record of five probes was
destroyed by rotation on an untracked file — archive per-session captures the way
`archive-crashdumps.ps1` archives dumps.

---

## 8. Instrument-artifact instances for `docs/method-rules.md` §1

1. **Six detector categories, two of which do not exist in the binary and four of which have never
   emitted a line in 326 client logs**, recorded as a property of the game. The two non-existent
   names appear nowhere in the repo except the sentence asserting their silence.
2. **`dsNotice` searched instead of `dsNotif`** — a false ABSENT that selected the message type for
   two probes and produced the "DS info must be inside another envelope" inference.
3. **A "16-name vocabulary" hand-scan reported as a denominator** when the table holds 119 — and
   which omits two of its own numerator's four items.
4. **Substring counts reported as token frequency** (`dsNotif` "10×"). Caught twice in one session:
   once in an agent's finding, once in a test assertion written to check the fix.
5. **A stubbed API used to verify a UI** accepted a request body shape the real handler rejects
   (`{k,v}` vs `{key,value}`), and would have certified a console that 400s on every frame. *A
   verification instrument that is more permissive than the thing it verifies is worthless.*
6. **A UTF-16-only string scan** returned zero for the client's entire AccelByte **v2** vocabulary,
   which is stored **ASCII** as UHT enumerator names — producing "no v2 path exists" when
   `messageSessionNotif` ships with its own handler and `EV2SessionNotifTopic` has 21 enumerators
   including `OnDSStatusChanged`. **Always scan both encodings.**
7. **A suffix filter and a window boundary erring in opposite directions**, yielding a plausible
   count (32) that was wrong twice: `endswith("Notif")` dropped two `*Notification` dispatch cases,
   while a too-wide window added `signalingP2PNotif`, which is not one. **Tie a recovered table to
   an independent count** — here, the 33-entry jump table — rather than trusting the extraction.
8. **`LogAccelByte` used as a proxy for `LogAccelByteLobby`.** Raising the first produces 52 lines
   and 4 receipts while the dispatcher stays completely silent. Two categories sharing a prefix are
   not one instrument.
9. **A 30 s proactive BINARY heartbeat that the handler never receives**, its silence read for
   months as a *format* problem. The messenger binds no binary delegate, so the frames die below
   the application layer — and the distinguishing evidence (`recieved unexpected message`, at
   `Warning`, count 0 against 1,418 same-category Warnings) was in every log the whole time.
10. **`partyGetInvitedNotice` / `UserNotification_PartyInvite` proposed as the cheapest FK-15
    experiment** — the first token does not exist in any encoding, and the second is a client-side
    `UObject` built from local models, never a wire type. The proposed launch was a guaranteed null.
