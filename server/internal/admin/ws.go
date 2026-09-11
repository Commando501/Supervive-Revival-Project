// Admin API for the FK-15 server→client WebSocket push console (2026-08-13).
//
// See `server\internal\lobby\push.go` for why this exists. In short: the
// "server→client push is measured non-functional" belief rests on 5 probes of
// ONE message type, each bundling 20+ speculative fields, each costing a whole
// game launch. These routes make a probe cost a button press instead, so the
// experiment can finally be run the way this project's own conventions demand —
// one variable at a time, with a positive control.
//
// Loopback-only (admin.Guard) like the rest of the panel. Nothing here fires
// unless an operator asks for it, so a normal sitting is byte-identical to one
// taken before this file existed.
package admin

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"

	"supervive-revival/server/internal/lobby"
)

// registerWS attaches the push-console routes. Called from Register.
func (s *Service) registerWS(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/ws/sockets", s.handleListSockets)
	mux.HandleFunc("POST /api/ws/push", s.handleWSPush)
	mux.HandleFunc("POST /api/ws/preview", s.handleWSPreview)
	mux.HandleFunc("POST /api/ws/drop/{handle}", s.handleWSDrop)
	mux.HandleFunc("GET /api/ws/vocabulary", s.handleWSVocabulary)
	mux.HandleFunc("POST /api/ws/sweep", s.handleWSSweep)
}

// handleWSVocabulary returns the 32 server-pushable notif types recovered from
// the client's own message-type table, flagged with whether the project has
// already probed each. The project has probed exactly one of them.
func (s *Service) handleWSVocabulary(w http.ResponseWriter, r *http.Request) {
	type entry struct {
		Type   string `json:"type"`
		Probed string `json:"probed,omitempty"`
	}
	out := make([]entry, 0, len(lobby.LobbyNotifTypes))
	for _, t := range lobby.LobbyNotifTypes {
		out = append(out, entry{Type: t, Probed: lobby.AlreadyProbed[t]})
	}
	writeJSON(w, map[string]any{
		"notifTypes": out,
		"recommended": lobby.RecommendedProbes,
	})
}

// handleWSSweep walks the vocabulary, one minimal frame per type. Blocking by
// design: a sweep of 32 types at the default 3 s gap takes ~96 s, and the
// operator should be watching Loki.log for that whole window rather than firing
// and forgetting. See lobby.Sweep's method note — a sweep finds candidates, it
// does not produce results; any hit needs a single-frame confirmation.
func (s *Service) handleWSSweep(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req lobby.SweepRequest
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		httpError(w, http.StatusBadRequest, "sweep parse: "+err.Error())
		return
	}
	results, err := s.Lobby.Sweep(req)
	if err != nil {
		// Report the partial run too: knowing WHERE it aborted is what stops
		// the remaining types being scored as nulls they never earned.
		writeJSON(w, map[string]any{"pushed": results, "error": err.Error()})
		return
	}
	writeJSON(w, map[string]any{"pushed": results})
}

// handleListSockets reports every live WS connection the client currently
// holds, so the operator can see WHICH channels exist before pushing at one.
// A push at a handle that has since reconnected is a silent no-op otherwise —
// exactly the kind of undetected delivery failure FK-11 warns about (delivery
// and effect are different failures and must be distinguished).
func (s *Service) handleListSockets(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"sockets": s.Lobby.Sockets()})
}

// handleWSPreview assembles a frame and returns the exact bytes WITHOUT
// sending it. Cheap insurance: it lets the operator confirm the wire shape
// before spending the socket on it, and it works with no game running.
func (s *Service) handleWSPreview(w http.ResponseWriter, r *http.Request) {
	req, ok := decodePush(w, r)
	if !ok {
		return
	}
	body, err := lobby.BuildPayload(req)
	if err != nil {
		httpError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, map[string]any{
		"bytes":   len(body),
		"payload": string(body),
	})
}

// handleWSPush sends one operator-authored frame. The response echoes exactly
// what went on the wire per socket, and the same line is written to
// docs/capture.log tagged with the probe label, so the run is reconstructable
// afterwards — which the original 5 probes are not.
func (s *Service) handleWSPush(w http.ResponseWriter, r *http.Request) {
	req, ok := decodePush(w, r)
	if !ok {
		return
	}
	results, err := s.Lobby.Push(req)
	if err != nil {
		httpError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, map[string]any{"pushed": results})
}

// handleWSDrop ungracefully closes one socket. This is the push console's
// POSITIVE CONTROL, not a feature: the messenger drop is the project's one
// demonstrated server→client control signal (S85 avatar resync), so a run where
// the drop still works but a pushed frame does nothing has localised the null
// to the frame rather than to the channel or the socket's liveness.
func (s *Service) handleWSDrop(w http.ResponseWriter, r *http.Request) {
	h := r.PathValue("handle")
	if err := s.Lobby.DropSocket(h); err != nil {
		httpError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, map[string]any{"dropped": h})
}

// decodePush parses a PushRequest with unknown fields REJECTED, so a typo in a
// hand-written curl body fails loudly instead of silently pushing a frame that
// is missing the field the operator thought they were testing.
func decodePush(w http.ResponseWriter, r *http.Request) (lobby.PushRequest, bool) {
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req lobby.PushRequest
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		httpError(w, http.StatusBadRequest, "push parse: "+err.Error())
		return lobby.PushRequest{}, false
	}
	return req, true
}
