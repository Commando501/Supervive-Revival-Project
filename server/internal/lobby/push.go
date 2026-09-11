// FK-15 push console — operator-driven server→client WebSocket frames.
//
// WHY THIS EXISTS (2026-08-13)
// ---------------------------
// The project's standing belief is `docs\coverage-audit-s101.md:98`:
//
//	"server→client push is **measured non-functional** (5 negative probes)"
//
// That belief is carrying more weight than its evidence supports, in three
// distinct ways, and every one of them is a *harness* problem rather than a
// fact about the client:
//
//  1. ONE MESSAGE TYPE. All five probes pushed `matchmakingNotif` and nothing
//     else (`phantomDsPush` + `phantomMatchmakingFlow` in lobby.go). A single
//     type's handler being state-gated says nothing about the push MECHANISM.
//  2. TWENTY-PLUS FREE VARIABLES PER PROBE. Each frame bundled `ip`/`port`/
//     `Address`/`Port`/`HostName`/`ServerUrl`/`Url`/`dsInfo`/`DsInfo`/
//     `serverInfo`/`ServerInfo`/... in one shot, in direct violation of this
//     project's own single-variable convention (CLAUDE.md, "Code conventions").
//     A negative from a 20-variable frame cannot name its own cause — and if
//     ANY one matched field had the wrong type, UE rejects the WHOLE document
//     (the validity model in `server\internal\menu\menu.go`), so one bad
//     speculative field silently voids the other nineteen.
//  3. ONE PROBE PER LAUNCH. Each variant needed a source edit, an `ags`
//     rebuild and a fresh game launch. That is why this unknown has sat at
//     N=5 for ~40 sessions: the cost per data point was a whole sitting.
//
// This console fixes (3), which is what makes (1) and (2) affordable to fix.
// Frames are authored at runtime from the loopback admin panel and pushed at a
// named live socket, so ONE launch can walk dozens of single-variable frames
// instead of one blunderbuss. It changes NOTHING about the game's own traffic:
// nothing is pushed unless an operator asks for it.
//
// DESIGN RULES, each of which is a lesson this project already paid for:
//   - EXACTLY WHAT YOU ASKED FOR. The builder never adds a speculative field,
//     never reorders, never "helpfully" supplies an id. Field order is
//     preserved (hence []Field, not a map) so a frame is byte-reproducible.
//   - EVERY PUSH IS LABELLED AND LOGGED to the capture log with its label and
//     full payload, so the corpus can later be mined for exactly what was sent
//     and when — the thing the original 5 probes make nearly impossible to
//     reconstruct.
//   - BOTH CHANNELS ARE ADDRESSABLE. The messenger socket
//     (`/notifications/players/{id}`, Theorycraft's own LokiPlatformMessenger)
//     has never had an application frame pushed at it — only binary `hb`. It is
//     also the socket already PROVEN to drive client behaviour, since S85's
//     avatar fix works by dropping it. Excluding it from the probe surface was
//     never a decision, just an accident of where the first probe was written.
package lobby

import (
	"errors"
	"fmt"
	"strconv"
	"strings"
	"sync"
	"time"

	"supervive-revival/server/internal/ws"
)

// socket is one live WebSocket connection in the push registry.
type socket struct {
	handle      string
	path        string
	playerID    string
	conn        *ws.Conn
	connectedAt time.Time

	mu     sync.Mutex
	pushes int
	last   string
}

// SocketInfo is the admin-facing view of a live socket.
type SocketInfo struct {
	Handle      string `json:"handle"`
	Path        string `json:"path"`
	PlayerID    string `json:"playerId,omitempty"`
	Kind        string `json:"kind"` // "lobby" | "messenger" | "other"
	ConnectedAt string `json:"connectedAt"`
	UptimeSec   int    `json:"uptimeSec"`
	Pushes      int    `json:"pushes"`
	LastPush    string `json:"lastPush,omitempty"`
}

// Field is one `key: value` pair. A slice (not a map) because AccelByte v1
// lobby frames are ORDERED newline-separated lines, and because a reproducible
// byte-for-byte frame is a precondition for a single-variable experiment.
type Field struct {
	Key   string `json:"key"`
	Value string `json:"value"`
}

// PushRequest is one operator-authored frame.
//
// Exactly one of Raw or (Type + Fields) selects the body:
//   - Raw: sent verbatim, no interpretation whatsoever. Use this to test a
//     wire format we have NOT modelled (e.g. a JSON envelope on the messenger).
//   - Type + Fields: assembled as an AccelByte v1 classic-lobby frame,
//     `type: <Type>` then `id: <ID>` (only when ID is non-empty) then each
//     field in order, joined with "\n".
//
// Binary=true sends the body as an OpBinary frame instead of OpText; HexBody
// interprets Raw as hex bytes (for probing the messenger's binary protocol,
// whose only known token today is the two bytes "hb").
type PushRequest struct {
	Socket string `json:"socket"` // handle from Sockets(); or...
	Path   string `json:"path"`   // ...a path prefix selector (e.g. "/notifications/players/")

	Raw    string  `json:"raw"`
	Type   string  `json:"type"`
	ID     string  `json:"id"`
	Fields []Field `json:"fields"`

	Binary  bool `json:"binary"`
	HexBody bool `json:"hexBody"`

	// Label tags the capture-log line so a run's frames can be told apart
	// later. Required — an unlabelled probe is an unanalysable probe.
	Label string `json:"label"`
}

// PushResult reports what was actually put on the wire, per socket.
type PushResult struct {
	Handle  string `json:"handle"`
	Path    string `json:"path"`
	Bytes   int    `json:"bytes"`
	Opcode  string `json:"opcode"`
	Payload string `json:"payload"`
	Error   string `json:"error,omitempty"`
}

// registerSocket adds a live conn to the push registry and returns its handle.
func (s *Service) registerSocket(path string, c *ws.Conn) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.socketNo++
	h := "ws" + strconv.Itoa(s.socketNo)
	s.sockets[h] = &socket{
		handle:      h,
		path:        path,
		playerID:    messengerPlayerID(path),
		conn:        c,
		connectedAt: time.Now(),
	}
	return h
}

func (s *Service) unregisterSocket(handle string) {
	s.mu.Lock()
	delete(s.sockets, handle)
	s.mu.Unlock()
}

// Sockets lists every live WebSocket connection. Nil-safe so callers need no
// lobby dependency in tests.
func (s *Service) Sockets() []SocketInfo {
	if s == nil {
		return []SocketInfo{}
	}
	s.mu.Lock()
	entries := make([]*socket, 0, len(s.sockets))
	for _, e := range s.sockets {
		entries = append(entries, e)
	}
	s.mu.Unlock()

	out := make([]SocketInfo, 0, len(entries))
	for _, e := range entries {
		e.mu.Lock()
		pushes, last := e.pushes, e.last
		e.mu.Unlock()
		out = append(out, SocketInfo{
			Handle:      e.handle,
			Path:        e.path,
			PlayerID:    e.playerID,
			Kind:        socketKind(e.path),
			ConnectedAt: e.connectedAt.UTC().Format(time.RFC3339),
			UptimeSec:   int(time.Since(e.connectedAt).Seconds()),
			Pushes:      pushes,
			LastPush:    last,
		})
	}
	// Stable order: oldest handle first (handles are monotonic).
	for i := 1; i < len(out); i++ {
		for j := i; j > 0 && handleNum(out[j-1].Handle) > handleNum(out[j].Handle); j-- {
			out[j-1], out[j] = out[j], out[j-1]
		}
	}
	return out
}

func socketKind(path string) string {
	switch {
	case strings.HasPrefix(path, "/notifications/players/"):
		return "messenger"
	case strings.HasPrefix(path, "/lobby"):
		return "lobby"
	default:
		return "other"
	}
}

func handleNum(h string) int {
	n, _ := strconv.Atoi(strings.TrimPrefix(h, "ws"))
	return n
}

// BuildPayload assembles the frame body WITHOUT sending it. Exported so the
// admin panel can show the operator the exact bytes before committing a launch
// to them, and so tests can assert the wire shape offline.
func BuildPayload(req PushRequest) ([]byte, error) {
	if req.Raw != "" && req.Type != "" {
		return nil, errors.New("push: set either raw or type+fields, not both")
	}
	if req.Raw != "" {
		if req.HexBody {
			b, err := decodeHex(req.Raw)
			if err != nil {
				return nil, fmt.Errorf("push: hex body: %w", err)
			}
			return b, nil
		}
		return []byte(req.Raw), nil
	}
	if req.Type == "" {
		return nil, errors.New("push: need raw or type")
	}
	// AccelByte v1 classic lobby: ordered newline-separated `key: value`.
	// NOTE the deliberate asymmetry with buildLobby(): `id` is emitted only
	// when the operator supplies one. buildLobby always writes an `id:` line,
	// which for an unsolicited notif is a 21st uncontrolled variable — a
	// server-initiated notification may well be expected to carry no id at all.
	lines := []string{"type: " + req.Type}
	if req.ID != "" {
		lines = append(lines, "id: "+req.ID)
	}
	for _, f := range req.Fields {
		lines = append(lines, f.Key+": "+f.Value)
	}
	return []byte(strings.Join(lines, "\n")), nil
}

// Push sends one operator-authored frame to the selected socket(s) and returns
// what went on the wire. Selecting by Path pushes to EVERY matching live socket
// (normally one), which is what you want when the client has just reconnected
// and the handle has changed underneath you.
func (s *Service) Push(req PushRequest) ([]PushResult, error) {
	if s == nil {
		return nil, errors.New("push: no lobby service")
	}
	if strings.TrimSpace(req.Label) == "" {
		return nil, errors.New("push: label is required (an unlabelled probe is unanalysable)")
	}
	if req.Socket == "" && req.Path == "" {
		return nil, errors.New("push: need socket handle or path selector")
	}
	body, err := BuildPayload(req)
	if err != nil {
		return nil, err
	}

	s.mu.Lock()
	targets := []*socket{}
	for _, e := range s.sockets {
		if req.Socket != "" && e.handle == req.Socket {
			targets = append(targets, e)
			continue
		}
		if req.Socket == "" && req.Path != "" && strings.HasPrefix(e.path, req.Path) {
			targets = append(targets, e)
		}
	}
	s.mu.Unlock()

	if len(targets) == 0 {
		return nil, errors.New("push: no live socket matches (is the game connected?)")
	}

	opcode := byte(ws.OpText)
	opName := "TEXT"
	if req.Binary || req.HexBody {
		opcode, opName = ws.OpBinary, "BINARY"
	}

	out := make([]PushResult, 0, len(targets))
	for _, e := range targets {
		res := PushResult{
			Handle:  e.handle,
			Path:    e.path,
			Bytes:   len(body),
			Opcode:  opName,
			Payload: string(body),
		}
		// Log BEFORE the write: if the write kills the socket we still know
		// exactly what was on the wire when it died. (The reverse ordering is
		// how a probe becomes unreconstructable after the fact.)
		s.logf("WS PUSH[%s] -> %s %s (%d bytes) %q", req.Label, e.path, opName, len(body), string(body))
		var werr error
		if opcode == ws.OpText {
			werr = e.conn.WriteText(string(body)) // envelope-wrapped, like production
		} else {
			werr = e.conn.WriteFrame(opcode, body)
		}
		if err := werr; err != nil {
			res.Error = err.Error()
			s.logf("WS PUSH[%s] FAILED %s: %v", req.Label, e.path, err)
		} else {
			e.mu.Lock()
			e.pushes++
			e.last = req.Label
			e.mu.Unlock()
		}
		out = append(out, res)
	}
	return out, nil
}

// SweepRequest walks a list of message types, pushing one minimal frame per
// type, GapMs apart, each individually labelled.
type SweepRequest struct {
	Socket string   `json:"socket"`
	Types  []string `json:"types"`  // empty = the full LobbyNotifTypes vocabulary
	Fields []Field  `json:"fields"` // optional, applied to EVERY frame (keep tiny)
	GapMs  int      `json:"gapMs"`  // default 3000
	Label  string   `json:"label"`  // prefix; each frame gets "<label>-<type>"
	Skip   bool     `json:"skipProbed"`
}

// Sweep pushes one minimal frame per message type, spaced GapMs apart, so ONE
// launch can walk the entire 32-type notif vocabulary instead of 32 launches.
//
// ⚠ ON METHOD — read before scoring a sweep.
// A sweep is a SCAN, not a controlled experiment, and it is deliberately not
// the same thing as the single-variable probe the console's Push endpoint does:
//
//   - Each FRAME is minimal (type name plus whatever few fields you supply), so
//     an individual frame is still attributable. What a sweep gives up is
//     isolation BETWEEN frames: if the client reacts, the gap and the per-frame
//     label tell you which frame preceded the reaction, but a delayed or
//     cumulative effect could be mis-attributed to its neighbour.
//   - Therefore a sweep's job is ONLY to find candidates. Any hit MUST be
//     re-run as a single Push, alone, on a fresh socket, before it is written
//     down as a result. A sweep hit is a lead; a single-frame confirmation is
//     the measurement.
//   - Keep GapMs comfortably larger than the client's own reaction latency
//     (its solicited responses round-trip in 67-210 ms, measured), or the
//     attribution above stops holding.
//
// A type with no bound handler is expected to do nothing at all; that is the
// null this scan is designed to make cheap, not a finding.
func (s *Service) Sweep(req SweepRequest) ([]PushResult, error) {
	if s == nil {
		return nil, errors.New("sweep: no lobby service")
	}
	if strings.TrimSpace(req.Label) == "" {
		return nil, errors.New("sweep: label is required")
	}
	types := req.Types
	if len(types) == 0 {
		types = LobbyNotifTypes
	}
	if req.Skip {
		kept := types[:0:0]
		for _, t := range types {
			if _, probed := AlreadyProbed[t]; !probed {
				kept = append(kept, t)
			}
		}
		types = kept
	}
	if len(types) == 0 {
		return nil, errors.New("sweep: no types left to push")
	}
	gap := time.Duration(req.GapMs) * time.Millisecond
	if req.GapMs <= 0 {
		gap = 3 * time.Second
	}

	s.logf("WS SWEEP[%s] starting: %d types, %v gap, socket=%q", req.Label, len(types), gap, req.Socket)

	out := []PushResult{}
	for i, t := range types {
		if i > 0 {
			time.Sleep(gap)
		}
		res, err := s.Push(PushRequest{
			Socket: req.Socket,
			Type:   t,
			Fields: req.Fields,
			Label:  req.Label + "-" + t,
		})
		if err != nil {
			// A dead socket mid-sweep is important news: everything after it
			// would be pushed into the void and score as a false null.
			s.logf("WS SWEEP[%s] ABORTED at %s (%d/%d done): %v", req.Label, t, i, len(types), err)
			return out, fmt.Errorf("sweep aborted at %s after %d/%d: %w", t, i, len(types), err)
		}
		out = append(out, res...)
	}
	s.logf("WS SWEEP[%s] complete: %d frames pushed", req.Label, len(out))
	return out, nil
}

// ---------------------------------------------------------------------------
// Probe #3: targeted per-resource resync (S117, 2026-08-13) — CONFIRMED LIVE.
//
// `UMessengerManager` registers 15 resource prefixes, each matched by StartsWith
// on FNotificationMessage.Resource. The dominant client-side effect is:
//
//	"resource X is now at version N" -> if N beats my cached version, re-issue
//	the HTTP GET for X
//
// MEASURED (docs/fk15-probe3-live-result-20260813.txt): one pushed frame naming
// `/match-history/players/<id>` with Version 7 produced
// `GET /match-history/players/<id>` **491 ms later**, with the messenger connect
// count UNCHANGED — i.e. no reconnect, no teardown. Before that push, that
// resource had been fetched at exactly three moments, all of them resyncs.
//
// Why this matters beyond FK-15: it is a strictly better lever than S85's socket
// drop. A drop tears the connection down, costs a ~0.7-1.5 s reconnect, and
// refetches EVERYTHING; a push refetches exactly one resource and keeps the
// socket up.
// ---------------------------------------------------------------------------

// NotifyResource pushes a "resource X is at version N" frame to one player's
// messenger socket. Nil-safe; returns an error if that player has no live
// messenger (which is information, not an inconvenience — a silent no-op here
// would look exactly like a client that ignored the frame).
//
// ⚠⚠ VERSION IS A FOOTGUN — PASS THE VERSION THE HTTP DOCUMENT WILL CARRY,
// NEITHER MORE NOR LESS. Measured both failure modes live, 2026-08-13:
//
//   - TOO LOW → silently ignored. A push of Version 3 at `/party/parties/...`
//     did nothing, because the party doc's version is seeded from
//     `time.Now().UnixMilli()` (~1.76e12) and the client had already cached it.
//     The null looks exactly like "the client doesn't handle this resource".
//   - TOO HIGH → **UNBOUNDED REFETCH LOOP**. A push of Version = now-millis
//     (above what `buildSoloParty` serves) produced **46 fetches of
//     /party/parties in 4 seconds**, ~one per 70 ms, and it did not stop on its
//     own: the client caches the pushed version, refetches, receives a document
//     with a LOWER version, still believes itself stale, and asks again. It was
//     cleared only by restarting ags, which reseeds partyVer above the poisoned
//     value.
//
// So the correct source is the SAME counter the document is served with —
// `interactive.Service.PartyVersion()` for the party resources, which is exactly
// what notifyPartyResources passes. Do not invent a version, do not use a clock,
// and do not "add 1 to be safe".
//
// (Resources served as empty catch-alls carry no version, so their cache stays 0
// and any positive value works — that is why the /match-history probe succeeded
// with Version 7.)
//
// ⚠⚠ THE PARENTHETICAL ABOVE IS STALE FOR ITS OWN EXAMPLE (S123, 2026-08-15).
// /match-history STOPPED being a catch-all when interactive.handleMatchHistory was
// written: it now carries MatchHistoryVersion(id), seeded from wall-clock seconds
// (~1.79e9). A push of Version 7 today is the TOO-LOW case documented directly
// above — silently ignored, and indistinguishable from "the client does not handle
// this resource". Pass interactive.MatchHistoryVersion(id), which is exported for
// exactly this. The general rule still holds; only the example expired.
// ⇒ A worked example that names a specific endpoint ROTS when that endpoint is
// implemented. When you give a resource a real Version, grep for its name in the
// push/notify docs — the comment that taught you the mechanism is now the comment
// that will mislead you. See docs/fk21-career-panels-settled.md §7.
func (s *Service) NotifyResource(playerID, resource string, version int64, label string) error {
	if s == nil {
		return errors.New("notify: no lobby service")
	}
	if playerID == "" || resource == "" {
		return errors.New("notify: need playerID and resource")
	}
	s.mu.Lock()
	c := s.messengers[playerID]
	s.mu.Unlock()
	if c == nil {
		return fmt.Errorf("notify: player %s has no live messenger socket", playerID)
	}
	// Field names match FNotificationMessage (schema.txt:37963) exactly.
	body := fmt.Sprintf(`{"Resource":%q,"Version":%d,"Payload":""}`, resource, version)
	if label == "" {
		label = "notify"
	}
	s.logf("WS NOTIFY[%s] -> %s %s", label, resource, body)
	if err := c.WriteText(body); err != nil {
		s.logf("WS NOTIFY[%s] FAILED %s: %v", label, resource, err)
		return err
	}
	return nil
}

// SetPartyVersionFunc supplies the monotonic party version used by the targeted
// resync path (see enableTargetedResync). Wired once at startup from cmd/ags to
// interactive.Service.PartyVersion.
func (s *Service) SetPartyVersionFunc(fn func() int64) {
	if s == nil {
		return
	}
	s.mu.Lock()
	s.partyVersion = fn
	s.mu.Unlock()
}

// notifyPartyResources pushes version bumps for the two party resources the
// client refetches on a loadout change, instead of dropping the socket.
// Reports whether both pushes went out.
func (s *Service) notifyPartyResources(id string) bool {
	s.mu.Lock()
	fn := s.partyVersion
	s.mu.Unlock()
	if fn == nil {
		return false
	}
	v := fn()
	okA := s.NotifyResource(id, "/party/players/"+id, v, "party-dirty") == nil
	okB := s.NotifyResource(id, "/party/parties/party-"+id, v, "party-dirty") == nil
	return okA && okB
}

// DropSocket forces a reconnect on one socket by handle. Exposed because the
// messenger-drop path is this project's ONE demonstrated server→client control
// signal (S85), which makes it the natural positive control for any push probe:
// if a drop still produces its resync while a pushed frame produces nothing,
// the socket was alive and the null belongs to the frame, not the channel.
func (s *Service) DropSocket(handle string) error {
	if s == nil {
		return errors.New("drop: no lobby service")
	}
	s.mu.Lock()
	e := s.sockets[handle]
	s.mu.Unlock()
	if e == nil {
		return errors.New("drop: no such live socket")
	}
	s.logf("WS DROP %s (%s) requested by admin (push-console positive control)", e.path, handle)
	return e.conn.Drop()
}

func decodeHex(s string) ([]byte, error) {
	clean := strings.Map(func(r rune) rune {
		if r == ' ' || r == '\n' || r == '\r' || r == '\t' || r == ':' || r == '-' {
			return -1
		}
		return r
	}, s)
	if len(clean)%2 != 0 {
		return nil, errors.New("odd number of hex digits")
	}
	out := make([]byte, len(clean)/2)
	for i := 0; i < len(out); i++ {
		v, err := strconv.ParseUint(clean[i*2:i*2+2], 16, 8)
		if err != nil {
			return nil, err
		}
		out[i] = byte(v)
	}
	return out, nil
}
