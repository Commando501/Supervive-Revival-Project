package lobby

// The client's AccelByte v1 classic-lobby message vocabulary, recovered
// 2026-08-13 from a CONTIGUOUS NUL-terminated UTF-16LE string table at
// RVA 0x86011D0..0x8602828 in `dumps\tutorial-hero\SUPERVIVE-Win64-Shipping.dump.exe`
// (the `.rdata`-100 % dump, per CLAUDE.md's standing rule — never merged.dump.exe,
// which is 63.1 %). The Response/Notif sub-block `0x8601A20`..`0x8602730` holds the
// **33 dispatchable notification type names** below. Controls: `listOfFriendsRequest` /
// `setUserStatusRequest` / `partyInviteNotif` all hit; `dsPhantomNotif` /
// `matchmakingBogusNotif` / `qqxxNotif` all miss.
//
// The bare token `"Notif"` at `0x8602828` is NOT a message type: it is the needle
// `Lobby::OnMessage` passes to `FString::Find` to decide notif-vs-response routing.
//
// WHY THIS MATTERS FOR FK-15
// --------------------------
// FK-15's "server→client push is measured non-functional" rests on 5 probes
// that pushed exactly ONE of these 33 notif types (`matchmakingNotif`), whose
// handler is the one most likely to be state-gated on a matchmaking ticket the
// client never issued. The other 32 have never been pushed.
//
// ⚠ TWO CORRECTIONS TO PRIOR RECORDS, both instrument artifacts (method-rules §1):
//
//  1. `docs\dedicated-server-stub.md:443` lists `dsNotice` as ABSENT and
//     concludes "the classic DS notice is absent — DS info is presumably
//     delivered inside one of the *Notif envelopes", which is WHY two probes
//     chose `matchmakingNotif`. The AccelByte v1 token is `dsNotif`, not
//     `dsNotice`, and it IS present — it is in this table. The absence was a
//     wrong-token artifact, and it selected the message type for two probes.
//
//  2. A naive substring count reports `dsNotif` 10 times. NINE of those are
//     matches INSIDE other tokens — "Frien(dsNotif)" in `acceptFriendsNotif`,
//     `requestFriendsNotif`, `cancelFriendsNotif`, `rejectFriendsNotif`,
//     `AccelByteModels*FriendsNotif`, plus `UpdateBoun(dsNotif)yStreaming...`.
//     As a STANDALONE token it occurs ONCE, exactly like `matchmakingNotif`
//     (whose naive count of 2 includes `rematchmakingNotif`). Do not repeat the
//     claim that `dsNotif` is "5× more present" — it is equally present, which
//     is all the argument needs. Count tokens, never substrings.
//
// ★ CORROBORATION (this is what makes the list trustworthy, not the scan alone):
// `Lobby::HandleNotif` (`.text 0x04B02C80`) dispatches via a `TMap<FString,uint8>` at
// `.data 0x9FFE2D0` into a **33-entry jump table at `.text 0x04B04978`** (decoded at
// 0x04B02CE0-0x04B02D34: hash(type) -> FindIndex -> enum = *(byte*)(data + idx*32 + 0x10),
// `if (enum-1 > 0x20) -> default`, i.e. values 1..33). The sub-block below holds **exactly
// 33** names. 33 == 33, so every name here has a dedicated dispatcher case — none is a
// string constant that only exists in a sender.
//
// ⚠⚠ TWO SCAN ERRORS THAT NEARLY CANCELLED — the reason this list is bounded by the
// jump-table count and not by a regex:
//   - A `endswith("Notif")` filter SILENTLY DROPS `userBannedNotification` and
//     `userUnbannedNotification`, which are dispatch cases.
//   - A window opened wider than the sub-block picks up `signalingP2PNotif`
//     (`0x86018F8`), which sits INSIDE the Request block, surrounded by `*Request`
//     names, and is NOT one of the 33 cases.
// Those two mistakes produce 32 — a plausible-looking count that is wrong in both
// directions at once. Always tie a recovered table to an independent count.
//
// ⚠ `signalingP2PNotif` is real and present; it is simply not in this dispatch block.
// Whether another path routes it is UNRESOLVED — do not add it here without evidence.
//
// The list is ordered as it appears in the image (`0x8601A20`..`0x8602730`).
var LobbyNotifTypes = []string{
	"connectNotif",
	"disconnectNotif",
	"partyLeaveNotif",
	"partyInviteNotif",
	"partyGetInvitedNotif",
	"partyJoinNotif",
	"partyRejectNotif",
	"partyKickNotif",
	"partyDataUpdateNotif",
	"partyConnectNotif",
	"partyDisconnectNotif",
	"partyNotif",
	"personalChatNotif",
	"partyChatNotif",
	"channelChatNotif",
	"userStatusNotif",
	"messageNotif",
	"userBannedNotification",   // ⚠ NOT a *Notif suffix — a endswith("Notif") filter drops it
	"userUnbannedNotification", // ⚠ likewise
	"matchmakingNotif",
	"setReadyConsentNotif",
	"setRejectConsentNotif",
	"rematchmakingNotif",
	"dsNotif",
	"acceptFriendsNotif",
	"requestFriendsNotif",
	"unfriendNotif",
	"cancelFriendsNotif",
	"rejectFriendsNotif",
	"blockPlayerNotif",
	"unblockPlayerNotif",
	"errorNotif",
	"messageSessionNotif",
}

// ---------------------------------------------------------------------------
// The MESSENGER channel (/notifications/players/{id}) — a SECOND, different
// protocol, RE'd S117. It is NOT AccelByte and NOT the key:value format above.
//
// Class is `UMessengerManager` (⚠ `LokiPlatformMessenger` does NOT exist in the
// binary — 0 hits both encodings; that name appears only in our own comments).
// `UMessengerManager::OnMessage` (.text 0x57C8F00) parses each TEXT frame as ONE
// JSON object into:
//
//	FNotificationMessage { Resource FString@0x00; Version int64@0x10; Payload FString@0x18 }
//
// (schema.txt:37963 — all scalar/Str types, i.e. FK-14's trustworthy class.)
//
// Dispatch: `Resource == "hb"` clears the heartbeat watchdog and returns;
// otherwise the 15 registered prefixes are matched by `StartsWith`, and the
// dominant effect is "resource X is at version N → if N beats my cache, re-issue
// the HTTP GET for X".
//
// ★★★ MEASURED, AND IT CHANGES WHAT WE THOUGHT: our 30 s proactive BINARY `hb`
// (lobby.go's messengerHeartbeatInterval) NEVER REACHES THIS HANDLER. Across
// 1,419 connections in one archived log — and re-confirmed independently on a
// second, later log (23/22/0/0) — the counts are:
//
//	Messenger connection established     1419
//	heartbeat not received in 5 seconds  1418   <- Warning, i.e. the category IS emitting
//	Messenger recieved message              0
//	Messenger recieved unexpected message   0   <- ALSO Warning. Should have fired 1418x.
//
// `Messenger recieved unexpected message: %s` logs at **Warning** on a JSON parse
// failure. If our binary `hb` had reached OnMessage it would have failed to parse
// and logged every single time. It logged zero times, in a log where the SAME
// category emits Warnings. ⇒ **a clean negative, not a muted channel**: binary
// frames are dropped before the handler (the messenger binds 4 WS delegates and
// OnRawMessage/OnBinaryMessage is not among them).
//
// ⇒ The messenger has never delivered a single frame to its application layer,
// and the ~60 s reconnect churn cannot be fixed by tuning our push interval.
// The fix is to reply in TEXT: {"Resource":"hb","Version":0,"Payload":""}.
//
// ⚠ The handler count 15 is a FLOOR. The first enumeration instrument found 7 and
// missed 8 that register via an inlined TSet::FindId rather than FindOrAdd; a
// third registration shape is not excluded.
// ---------------------------------------------------------------------------

// RecommendedProbe is a pre-authored frame for the FK-15 experiment, ranked.
//
// Channel is "lobby" (AccelByte key:value on /lobby) or "messenger" (JSON on
// /notifications/players/{id}). Raw, when set, is sent verbatim instead of
// Type+Fields — the messenger channel needs it, since its body is a JSON object
// and not a key:value document.
type RecommendedProbe struct {
	Rank     int     `json:"rank"`
	Channel  string  `json:"channel"`
	Name     string  `json:"name"`
	Type     string  `json:"type"`
	Fields   []Field `json:"fields"`
	Raw      string  `json:"raw"`
	Why      string  `json:"why"`
	Expect   string  `json:"expect"`
	NeedsIni bool    `json:"needsIni"`
}

// RecommendedProbes encodes the ranked shortlist from the S117 dispatch RE
// (`docs/fk15-ws-push-audit.md`), so the ordering survives contact with a live
// sitting instead of living only in prose.
//
// ★ The ordering is not arbitrary. Probes 1 and 2 are chosen because their
// diagnostic lines are emitted at **Warning**, which the shipped ini ALREADY
// allows — so they work with **no ini change at all** and settle the one
// question every other probe depends on: does our frame reach the client's
// lobby dispatcher? Every previous probe skipped straight past that.
var RecommendedProbes = []RecommendedProbe{
	{
		Rank:    1,
		Channel: "messenger",
		Name:    "★ Non-JSON sentinel on the messenger — the single best first probe",
		Raw:     "FK15-PROBE-FROM-AGS",
		Why: "The strongest experiment available, because its baseline is a MEASURED ZERO with " +
			"an in-log positive control. UMessengerManager::OnMessage (.text 0x57C8F00) parses " +
			"every TEXT frame as JSON into FNotificationMessage; a parse failure logs " +
			"`Messenger recieved unexpected message: %s` at **Warning** — visible at today's " +
			"shipped verbosity, no ini change. Across 1,419 archived connections that line " +
			"fired 0 times, while `heartbeat not received` fired 1,418 times in the SAME " +
			"category, so the zero is a clean negative rather than a muted channel. One line " +
			"appearing, echoing our own sentinel back, settles FK-15 outright.",
		Expect:   "LogMessenger: Warning: Messenger recieved unexpected message: FK15-PROBE-FROM-AGS",
		NeedsIni: false,
	},
	{
		Rank:    2,
		Channel: "messenger",
		Name:    "Heartbeat reply in TEXT — fixes the 60 s reconnect churn",
		Raw:     `{"Resource":"hb","Version":0,"Payload":""}`,
		Why: "The client sends a BINARY `hb` and starts a 5 s watchdog; only a TEXT frame whose " +
			"JSON has Resource==\"hb\" clears it. Our 30 s proactive BINARY push never reaches " +
			"the handler at all, which is why the socket has always died at ~60 s (measured: " +
			"median 60.0 s connect→kill, exactly one heartbeat per connection). Landing this " +
			"gives a stable socket and makes every later probe cheap. ⚠ It also removes the " +
			"free periodic resync the client gets from reconnecting — re-verify S85 avatar " +
			"latency afterwards (the explicit Conn.Drop() lever is unaffected).",
		Expect:   "`heartbeat not received in 5 seconds` STOPS; no more reconnect every ~61 s",
		NeedsIni: false,
	},
	{
		Rank:    3,
		Channel: "messenger",
		Name:    "Targeted resync via version bump — server-side-only observable",
		Raw:     `{"Resource":"/match-history/players/<playerId>","Version":7,"Payload":""}`,
		Why: "These handlers are ~seven instructions with NO resource equality check — the only " +
			"gate is Version > cached. Success shows up as a GET in our OWN capture.log: no " +
			"client log, no screenshot, no verbosity change needed. FLOWN 2026-08-13: the GET " +
			"landed 491 ms after the push with the messenger connect count UNCHANGED. " +
			"⚠⚠ VERSION: pass the version the HTTP document will CARRY, never more. This probe " +
			"uses /match-history (served as an empty catch-all, so its cache stays 0 and any " +
			"small positive value works). A version ABOVE what the document carries causes an " +
			"UNBOUNDED REFETCH LOOP — measured at 46 fetches in 4 s on /party/parties, cleared " +
			"only by restarting ags. The shipped MarkDirty path is safe by construction because " +
			"notifyPartyResources passes PartyVersion(), the same counter buildSoloParty serves.",
		Expect:   "a GET for that resource appears in docs/capture.log within a second",
		NeedsIni: false,
	},
	{
		Rank:    4,
		Channel: "lobby",
		Name:    "messageNotif with an undeserializable payload — the /lobby arrival test",
		Type:    "messageNotif",
		Fields: []Field{
			{Key: "topic", Value: "fk15-probe"},
			{Key: "payload", Value: `{"notAField":1}`},
		},
		Why: "Lobby::OnMessage routes `messageNotif` into CheckMissingNotification " +
			"(.text 0x04B0EB40) UNCONDITIONALLY — no ticket, no state, no id. That function " +
			"deserializes into FAccelByteModelsUserNotification and logs a Warning on failure. " +
			"This separates 'our frame never reached OnMessage' from 'it arrived and was " +
			"absorbed' — the distinction the whole five-probe corpus never made.",
		Expect: "LogAccelByteLobby: Warning: Cannot check missing notification, failed to " +
			"deserialize <...> to FAccelByteModelsUserNotification",
		NeedsIni: false,
	},
	{
		Rank:    5,
		Channel: "lobby",
		Name:    "messageSessionNotif with a bogus topic",
		Type:    "messageSessionNotif",
		Fields: []Field{
			{Key: "topic", Value: "fk15NotARealTopic"},
			{Key: "payload", Value: `{}`},
		},
		Why: "The v2 envelope has its own handler at .text 0x04B07E80, reached by an exact " +
			"type match before the generic Notif routing. An unknown topic falls to a default " +
			"that logs at Warning. Second no-ini-change arrival test, on a different code path.",
		Expect:   "an 'Unknown ... notification topic' / v2 default-branch Warning",
		NeedsIni: false,
	},
	{
		Rank:    6,
		Channel: "lobby",
		Name:    "dsNotif — the frame the whole conclusion was built on never sending",
		Type:    "dsNotif",
		Fields: []Field{
			{Key: "status", Value: "READY"},
			{Key: "ip", Value: "127.0.0.1"},
			{Key: "port", Value: "7777"},
		},
		Why: "The AccelByte v1 type that carries dedicated-server connection info. It has a " +
			"dispatcher case and reaches HandleNotif with NO precondition. It was recorded " +
			"ABSENT only because the prior scan searched `dsNotice`, a name this SDK does not " +
			"use — and that false absence is what redirected two probes onto matchmakingNotif.",
		Expect:   "LogNet / a NetConnection attempt against 127.0.0.1:7777 would be the win",
		NeedsIni: true,
	},
	{
		Rank:    7,
		Channel: "lobby",
		Name:    "matchmakingNotif re-run unchanged, with the dispatcher category raised",
		Type:    "matchmakingNotif",
		Fields: []Field{
			{Key: "status", Value: "done"},
		},
		Why: "Same type as probes #3/#5, but now with LogAccelByteLobby=VeryVerbose, whose " +
			"`Type: %s` line (site .text 0x04B0B12B) prints for EVERY routed frame. If it " +
			"prints, the 2026-06-29 'silent absorption' was a LOGGING null, not a routing " +
			"null. If it does not, the frame never reached OnMessage at all.",
		Expect:   "LogAccelByteLobby: VeryVerbose: Type: matchmakingNotif",
		NeedsIni: true,
	},
}

// AlreadyProbed records which notif types the project has already pushed, so a
// sweep does not spend a launch re-confirming a known null. Sourced from
// `docs\dedicated-server-stub.md` probes #3 and #5 (both 2026-06-29).
//
// ⚠ Their nulls are themselves of limited value: both fired 41 days before the
// project could see `LogAccelByte`, whose `OnMessageReceived` line is the only
// direct receipt for an inbound frame. Re-probing `matchmakingNotif` at raised
// verbosity is legitimate; it is a different measurement, not a repeat.
var AlreadyProbed = map[string]string{
	"matchmakingNotif": "probes #3 (single status=done) and #5 (status=start→done), 2026-06-29, " +
		"both ~35 bundled fields, both observed at shipped log verbosity (i.e. blind)",
}
