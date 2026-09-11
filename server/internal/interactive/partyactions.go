package interactive

import (
	"io"
	"log"
	"net/http"
	"strings"
)

// partyactions.go — POST .../setIsOpen/{value} and POST .../emote/{...}
// S133, 2026-08-20. Both discovered the same way `joinQueue` was: by DRIVING the control
// during an FK-20 decryption run, not by a capture sweep.
//
// [M] On the wire (User-Agent Loki/UE5-CL-0), both previously fell to main.go's "/"
// catch-all and returned 200 {}:
//
//	POST /party/parties/party-<id>/setIsOpen/True    x1   <- party privacy toggle
//	POST /party/parties/party-<id>/emote/            x5   <- lobby emote
//
// Both are on `UPartyManager` page 0x5879000 (TrySetIsOpen 0x5879C30, TrySendEmote
// 0x5879040), which those clicks decrypted — see docs/s133-joinqueue-find-match.md §7.
//
// ⚠ NOTE THE URL SHAPE, IT IS NOT THE JSON-BODY STYLE THE REST OF THIS BACKEND USES:
// the value rides in the PATH (`setIsOpen/True`), and `emote/` ends in a bare trailing
// slash — i.e. the client sent an EMPTY final segment. Content-Type on both is
// `application/x-www-form-urlencoded`, and docs/capture.log does not record bodies, so
// the emote payload shape is UNKNOWN. That is why handleEmote logs the raw body: one
// click will tell us, and guessing a shape we could have measured would be the exact
// mistake this project keeps writing rules about.

// handlePartySetIsOpen answers the party privacy toggle.
//
// `isOpen` is already a plain bool in buildSoloParty's document, so this is the same
// type-safe class of change as the `inQueue` probe — no enum risk. It is persisted and
// echoed so the next /party poll cannot snap it back (the handleSetTargetQueues defect).
//
// ⚠ The client sends "True"/"False" CAPITALISED (UE's bool-to-string), not Go's
// "true"/"false", so the parse is case-insensitive. A case-sensitive compare here would
// silently read every value as false and look exactly like "the toggle does nothing".
func (s *Service) handlePartySetIsOpen(w http.ResponseWriter, r *http.Request) {
	id := partyPathPlayerID(r)
	raw := r.PathValue("value")
	open := strings.EqualFold(strings.TrimSpace(raw), "true")
	log.Printf("interactive: setIsOpen player=%s raw=%q -> %v", id, raw, open)
	s.store.update(id, func(st *playerState) { st.PartyIsOpen = open })
	s.writeParty(w, r, id)
}

// handlePartyEmote answers a lobby emote. SHAPE NOW MEASURED [M]:
//
//	POST /party/parties/{p}/emote/Emote:Fingerwag        body: EMPTY (bodylen=0)
//	POST /party/parties/{p}/emote/Emote:SeraphMurder     body: EMPTY
//	POST /party/parties/{p}/emote/Emote:YouThinkImBoosted
//
// ⇒ the emote id is the PATH TAIL, as a full `PrimaryAssetId` string ("Emote:<Name>"),
// and the body is always empty.
//
// ★★ THE INSTRUMENT EARNED ITS KEEP, AND IT CORRECTED THE PREMISE IT WAS BUILT ON.
// This handler was written as a body-logger because the first six POSTs arrived as bare
// `/emote/` with an empty body, and the working assumption was "the id must be in the
// body, which capture.log does not record". THAT WAS WRONG. The id was always in the
// path; the segment was empty because the ACCOUNT OWNED NO EMOTES, so the client had
// nothing to name. The same log line that recorded six empty bodies recorded the real
// id the moment ownership was fixed — because it logged the TAIL as well as the body.
// ⇒ Log every input channel, not the one your hypothesis names. The cheap extra field is
// what turns "my guess was wrong" into "here is the answer".
//
// ⚠ STILL CHANGES NO STATE, deliberately. Emotes visibly play in the lobby with the party
// document echoed unchanged, so nothing here is known to be needed. FParty names `Emotes`
// and `Emotes_Played` and a multi-member party may require a broadcast — but that is
// UNTESTED (this backend only ever serves a solo party), and inventing a field for an
// unobserved case is how uninterpretable nulls get made.
//
// ★ Echoing the party (rather than 200 {}) is not a no-op: it is the shape every other
// party verb returns, it advances the Version, and if the emote path expects an FParty
// back the way joinQueue did, this alone may be sufficient.
func (s *Service) handlePartyEmote(w http.ResponseWriter, r *http.Request) {
	id := partyPathPlayerID(r)

	// The route is registered as a subtree ("…/emote/"), so PathValue is not available for
	// the tail; take it off the URL directly. It carries "Emote:<Name>" when one is equipped,
	// and is EMPTY when the account owns none — both observed.
	tail := ""
	if i := strings.LastIndex(r.URL.Path, "/emote/"); i >= 0 {
		tail = r.URL.Path[i+len("/emote/"):]
	}

	body, _ := io.ReadAll(io.LimitReader(r.Body, 8192))
	log.Printf("interactive: emote player=%s tail=%q ctype=%q query=%q bodylen=%d body=%q",
		id, tail, r.Header.Get("Content-Type"), r.URL.RawQuery, len(body), string(body))

	s.writeParty(w, r, id)
}
