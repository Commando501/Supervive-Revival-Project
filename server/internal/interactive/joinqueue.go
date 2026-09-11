package interactive

import (
	"log"
	"net/http"
	"strings"
)

// joinqueue.go — POST /party/parties/{partyId}/joinQueue, THE "FIND MATCH" BUTTON.
// S133, 2026-08-20.
//
// ── HOW THIS WAS FOUND ────────────────────────────────────────────────────────
// Not by a capture sweep. It was found by DRIVING the UI during an FK-20 decryption
// experiment: the session clicked PRACTICE → CO-OP VS. AI → FIND MATCH in order to
// decrypt `UPartyManager::TryJoinQueue` (impl 0x5875E90), whose 4 KiB page 0x5875000
// had been all-zero in all 26 image captures this project owns.
//
// [M] The click produced, on the wire (User-Agent Loki/UE5-CL-0):
//
//	POST /party/parties/party-<id>/setTargetQueues  {"queueIds":["bots"]}   <- tile select
//	POST /party/parties/party-<id>/joinQueue                                <- FIND MATCH
//	POST /party/parties/party-<id>/joinQueue                                <- retry, +10.4 s
//
// There was NO handler, so it fell to main.go's "/" catch-all and returned 200 {}. The
// client never entered a queued state, FIND MATCH did nothing visible, and it retried.
//
// ⚠⚠ THIS IS THE SECOND CORRECTION TO THE S122 UNSERVED-ROUTE SWEEP, AND IT IS THE SAME
// BLIND SPOT handleSetTargetQueues already names: a capture-diff enumerates the endpoints
// the client HAPPENED TO EXERCISE, not the ones it can call. `setTargetQueues` was missed
// because nobody clicked a tile; `joinQueue` was missed because nobody clicked FIND MATCH.
// ⇒ The rule is not "re-run the sweep for longer". It is "drive the interaction, THEN
// diff". Two endpoints, one cause, two sessions apart.
//
// ── WHAT THE CLIENT DOES WITH THE RESPONSE (read from the decrypted function) ──
// The experiment that found the gap also supplied the fix, because it decrypted the code:
//
//	TryJoinQueue 0x5875E90 ... 0x5875F8F  lea r9, [0x5859E10]      <- response callback
//	callback     0x5859E10 ... 0x5859E51  mov rcx,[rbx+0xf8]
//	                                       mov rdx, rdi
//	                                       call 0x587BE90          <- UPartyModel::SetParty
//
// [M] 0x587BE90 is `UPartyModel::SetParty`, which this project already characterised in
// S85: it gates the WHOLE party document on a strict monotonic `FParty.Version`
// (`cmp [PartyModel+0x568]; jge bail`).
//
// ⇒ joinQueue's response IS an FParty document, fed straight into SetParty. So the handler
// must (a) echo the party, and (b) advance the version — which is why it goes through
// store.update() exactly like handleSetTargetQueues. A response under a non-advancing
// version is accepted by us and DISCARDED by the client, the same silent staleness class
// as FPlayerRank.Version and the client-config/regions eTags.
//
// ── WHICH FIELDS, AND THE BISECT THAT GOT THERE ───────────────────────────────
// PROBE 1 — `inQueue` alone (party + member booleans). MEASURED INSUFFICIENT.
// It was the right first probe (plain bools, no enum risk) and it produced a clean,
// interpretable null because the alternative had been pre-registered:
//   * the response WAS adopted — UPartyModel::SetParty ran and the party-slot widgets
//     rebuilt (LogBlueprintUserMessages "MENUSPAWNER … Entering SetHero") at the exact
//     joinQueue timestamp, so the monotonic Version gate passed;
//   * LogJson at Verbose logged ZERO import failures, so the document typed cleanly;
//   * the UI still did not enter a searching state and the client re-POSTed 35 s later.
//   ⇒ WRONG FIELD, not a dead route. That distinction was written down BEFORE the flight,
//     which is the only reason the null was worth anything.
//
// PROBE 2 — `state = "Matchmaking"`. EPartyState = { Default, Matchmaking, CustomGame,
// Unknown }, read from the usmap's enum VALUE table (FK-14: value tables are the part of a
// usmap that can be trusted; container-inner and underlying types are not).
//
// ⚠ `state` is the enum-valued failure class that sank ELokiActivityState (S118) and ERank
// (S121) — a value outside the table rejects the WHOLE struct and looks exactly like "no
// effect". Two things make it an acceptable risk here rather than a coin flip: the value is
// taken verbatim from the shipped enum, and PROBE 1 established LogJson as a DEMONSTRATED
// detector on this exact document (it was silent on an accepted one, so a complaint now is
// signal). Still a single-variable change: nothing else moved between probe 1 and probe 2.
//
// ⚠ There is no matchmaking PUSH route available as a fallback: FK-15's bound-delegate map
// (S118) measured `matchmakingNotif` as one of the 26 UNBOUND notif types — broadcast into
// a delegate with no subscriber. So HTTP is the only door here, which is why the response
// shape has to be right.
//
// Knob: AGS_JOIN_QUEUE=0 disables the handler (falls back to the catch-all, i.e. exactly
// the pre-S133 behaviour) so the change can be A-B-A'd without a rebuild.

// handleJoinQueue answers the FIND MATCH click by marking the player queued and echoing
// the party document under an advanced version.
func (s *Service) handleJoinQueue(w http.ResponseWriter, r *http.Request) {
	id := partyPathPlayerID(r)
	log.Printf("interactive: joinQueue player=%s queue=%q", id, s.selectedQueue(id))
	s.store.update(id, func(st *playerState) { st.InQueue = true })
	// S135: nothing else in this server ever reads InQueue, so without this the player
	// sits in a real, timed, cancellable queue forever. No-op unless AGS_ARM_QUEUE is
	// set AND the queue is in AGS_ARM_QUEUE_QUEUES (default `bots`). See armqueue.go.
	s.scheduleArm(id, s.selectedQueue(id))
	s.writeParty(w, r, id)
}

// handleLeaveQueue answers the CANCEL click. Not yet observed on the wire — the client
// could not reach a cancellable state before joinQueue was served — so the route is
// registered speculatively under the two spellings the party API uses elsewhere.
// ⚠ If neither is ever hit, that is not evidence the client cannot cancel; it is evidence
// we have not yet driven the interaction. Check capture.log for the real verb.
func (s *Service) handleLeaveQueue(w http.ResponseWriter, r *http.Request) {
	id := partyPathPlayerID(r)
	log.Printf("interactive: leaveQueue player=%s", id)
	s.store.update(id, func(st *playerState) { st.InQueue = false })
	// Drop any pending or armed match so CANCEL is a real cancel and the next FIND MATCH
	// starts clean. Without this the S107 failure recurs: once /core-game/players reports
	// a MatchID it does so forever and every later START is a silent no-op.
	s.cancelArm(id)
	s.writeParty(w, r, id)
}

// partyPathPlayerID extracts the player id from a /party/parties/{partyId}/... route,
// falling back to the JWT subject when the path is not our "party-<id>" shape. Lifted
// verbatim from handleSetTargetQueues so the two cannot drift.
func partyPathPlayerID(r *http.Request) string {
	partyID := r.PathValue("partyId")
	id := strings.TrimPrefix(partyID, "party-")
	if id == partyID {
		if sub := subjectFromBearer(r.Header.Get("Authorization")); sub != "" {
			id = sub
		}
	}
	return id
}

// writeParty echoes the solo party document with the queue flag applied.
func (s *Service) writeParty(w http.ResponseWriter, r *http.Request, id string) {
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	party := buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id),
		s.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion())
	applyQueueState(party, s.inQueue(id))
	if s.partyIsOpen(id) {
		party["isOpen"] = true
	}
	writeJSON(w, party)
}

// applyQueueState stamps the party-level and member-level `inQueue` booleans.
//
// It MUTATES a party map built by buildSoloParty rather than adding a parameter to that
// function, deliberately: buildSoloParty has five production call sites and four test call
// sites, and threading an eighth positional bool through all nine would be a larger and
// more error-prone diff than one explicit post-step. The party poll GET must apply this
// too — otherwise the next /party read serves inQueue:false and the client snaps back,
// which is precisely the defect handleSetTargetQueues was written to remove.
func applyQueueState(party map[string]any, inQueue bool) {
	if !inQueue {
		return // buildSoloParty already emits false; leave the document byte-identical
	}
	// ⚠⚠ DEAD KEY, MEASURED (S135). FParty has SIXTEEN properties and none is `inQueue`
	// (UHT bind table, tools/asdump/out/binds_members.csv: ID, Version, State,
	// ClientVersion, IsOpen, FillTeam, OwnerID, DiscordJoinSecret, Members,
	// TargetQueueIDs, ExcludedRegions, Requests, CustomGameDetails, QueueJoinTime,
	// TargetQueueID, IsRanked). JsonObjectStringToUStruct ignores unknown keys silently,
	// so this write and the member-level one below have NEVER done anything, and
	// `state` below is doing 100% of the work. That is independent confirmation of this
	// file's own PROBE 1 null at :53. Left in place because an unknown key is inert;
	// annotated so it is not re-believed. ⚠ Do NOT read a `state` null as "the document
	// was rejected": FParty.State is an FString (property 2), not an enum, so a wrong
	// value changes the state machine but cannot sink the document.
	party["inQueue"] = true
	// EPartyState = { Default, Matchmaking, CustomGame, Unknown } -- read from the usmap's
	// enum value table (FK-14 confirmed enum VALUE tables are the trustworthy part of a
	// usmap; it is the container-inner and underlying types that are not).
	//
	// [M] WHY THIS WAS NEEDED: serving `inQueue:true` ALONE was measured insufficient.
	// The response WAS adopted -- UPartyModel::SetParty ran and the party-slot widgets
	// rebuilt (LogBlueprintUserMessages "MENUSPAWNER ... Entering SetHero" at the exact
	// joinQueue timestamp), and LogJson at Verbose logged ZERO import failures -- but the
	// UI never entered a searching state and the client re-POSTed 35 s later.
	// => wrong FIELD, not a dead route. That distinction was pre-registered before the
	// flight precisely so this null would be interpretable.
	//
	// ⚠ `state` is ENUM-VALUED, the failure class that sank ELokiActivityState (S118) and
	// ERank (S121): a value outside the table rejects the WHOLE struct on import and looks
	// exactly like "no effect". "Matchmaking" is taken verbatim from the shipped enum, and
	// LogJson (Verbose, and demonstrated silent on the accepted document above) is the
	// detector if it is still wrong.
	party["state"] = "Matchmaking"
	// ⚠ DELIBERATELY NOT SERVED YET: `queueJoinTime` and `millisInQueue`, both named in
	// FParty's field block beside TargetQueueID. They are the queue TIMER, i.e. cosmetic,
	// and their UE types are unconfirmed (FDateTime-as-string vs int64). Sending a
	// wrong-typed matched key would sink the entire document and make `state` untestable
	// too -- an uninterpretable null instead of a measurement. Add them as a SEPARATE
	// probe once "Matchmaking" is confirmed to drive the UI.
	if members, ok := party["members"].([]any); ok {
		for _, m := range members {
			if mm, ok := m.(map[string]any); ok {
				mm["inQueue"] = true
			}
		}
	}
}
