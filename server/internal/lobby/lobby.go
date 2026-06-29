// Package lobby handles the client's WebSocket connections (the AccelByte
// `lobby` service at ws://localhost:8080/lobby/ and the Theorycraft messenger).
//
// Right now it does the minimum to get past the "ws upgrade response not 101"
// reconnect loop: complete the handshake, keep the socket open, answer pings,
// and log every frame the client sends so the lobby application protocol can be
// reverse-engineered. We deliberately do NOT send anything proactively yet —
// first we observe whether the client speaks first (sends auth/requests) or
// waits for a server hello, which decides how the protocol is driven.
package lobby

import (
	"net"
	"net/http"
	"strings"
	"time"

	"supervive-revival/server/internal/ws"
)

// phantomDsPushDelay > 0 enables the dedicated-server-stub chapter's probe #3
// (legacy: single-frame matchmakingNotif push). Superseded by probe #5's
// start→done sequence (see phantomMatchmakingSequence below). Kept here as
// the single-frame fallback if start→done turns out to be the wrong model.
const phantomDsPushDelay = 0

// phantomDsPushPath restricts probe-pushes to one WS path. Empty matches any
// path; "/lobby" matches the AccelByte classic lobby; "/notifications/players/"
// (prefix match) matches the messenger.
const phantomDsPushPath = "/lobby"

// phantomMatchmakingSequence enables probe #5: walk the client through a fake
// matchmaking state machine via two server-pushed `matchmakingNotif` frames
// on /lobby. The hypothesis is that the client's matchmaking subsystem refuses
// to act on an unsolicited "match found" because its INTERNAL state isn't
// "in matchmaking" — probe #3's lone status=done frame was silently ignored
// for that reason. Pushing status=start first should flip the client into
// the matchmaking state so that the subsequent status=done WITH DS info
// triggers the connect path.
//
// Set false to disable. Timing: status=start fires at phantomMmStartDelay
// after the WS handshake; status=done fires phantomMmDoneDelay later.
const phantomMatchmakingSequence = true

// Timing for probe #5's start→done sequence.
//   - phantomMmStartDelay: wait this long after WS connect before pushing
//     status=start. Gives the client's lobby subsystem time to finish handling
//     friends/status traffic (those land in the first ~2s post-connect).
//   - phantomMmDoneDelay: wait this long after status=start before pushing
//     status=done. Simulates the natural matchmaking duration; some clients
//     gate the done-handler behind "must have been start for at least N ms".
const phantomMmStartDelay = 3 * time.Second
const phantomMmDoneDelay = 2 * time.Second

// messengerHeartbeatInterval is how often the server proactively pushes a
// binary "hb" frame on the Theorycraft messenger socket (path
// /notifications/players/{id}). The client's LogMessenger watchdog fires
// "heartbeat not received in 5 seconds. Last heartbeat sent: <T>" ~60s after
// connect and tears the socket down with a clean status-1000 close, even with
// our on-receive "hb" echo wired up. The on-receive echo races the watchdog
// trigger; pushing server-initiated frames before the watchdog's silence
// threshold is what other AccelByte/Theorycraft-style notification clients
// expect. 30s = ~half the observed 60s send-cycle, leaving slack for the 5s
// reply window.
const messengerHeartbeatInterval = 30 * time.Second

// EventLogger records frame activity to the capture log.
type EventLogger interface {
	Event(format string, args ...any)
}

type Service struct {
	log EventLogger
}

func New(log EventLogger) *Service { return &Service{log: log} }

// Handle upgrades a WebSocket request and serves the read loop. The caller
// should route here when ws.IsUpgrade(r) is true.
//
// 2026-06-29 — Messenger heartbeat probe. The Theorycraft LokiPlatformMessenger
// socket (path /notifications/players/{id}) was tearing down every ~60s with
// "LogMessenger: Warning: heartbeat not received in 5 seconds. Last heartbeat
// sent: <T>" followed by a clean status-1000 close. Wire-level capture showed
// the client sending one BINARY "hb" (0x68 0x62) every ~55-60s and closing
// 5.0s later; nothing else over the socket. Echoing "hb" on receive was
// insufficient (had improved the cycle from ~5s to ~60s in an earlier session
// but the watchdog still trips). Hypothesis: the watchdog model is "haven't
// received anything from server in N seconds → probe + close on no reply",
// and the on-receive echo races the watchdog. Fix: push proactive "hb" frames
// every 30s by setting a ReadFrame deadline and writing on timeout. Single
// goroutine, no write-mutex needed (reads and writes both happen on this
// goroutine). Only applied to the messenger path so the AccelByte /lobby
// socket — which works on TEXT heartbeats and has no watchdog — is unchanged.
func (s *Service) Handle(w http.ResponseWriter, r *http.Request) {
	conn, err := ws.Upgrade(w, r)
	if err != nil {
		s.log.Event("WS upgrade FAILED %s: %v", r.URL.Path, err)
		return
	}
	s.log.Event("WS connected %s (subproto=%q)", r.URL.Path, r.Header.Get("Sec-WebSocket-Protocol"))
	defer func() {
		conn.Close()
		s.log.Event("WS closed %s", r.URL.Path)
	}()

	isMessenger := strings.HasPrefix(r.URL.Path, "/notifications/players/")

	// Dedicated-server-stub probes #3 and #5: unsolicited server-pushed
	// notifications. Runs on a separate goroutine — writes are serialized
	// via ws.Conn.writeMu, so this is safe to race against the read loop's
	// hb echoes / reply text writes.
	if pathMatchesPushTarget(r.URL.Path) {
		if phantomDsPushDelay > 0 {
			go s.phantomDsPush(conn, r.URL.Path)
		}
		if phantomMatchmakingSequence {
			go s.phantomMatchmakingFlow(conn, r.URL.Path)
		}
	}

	for {
		if isMessenger {
			_ = conn.SetReadDeadline(time.Now().Add(messengerHeartbeatInterval))
		}
		f, err := conn.ReadFrame()
		if err != nil {
			if isMessenger {
				if ne, ok := err.(net.Error); ok && ne.Timeout() {
					s.log.Event("WS -> %s BINARY hb (proactive %s keepalive)", r.URL.Path, messengerHeartbeatInterval)
					if werr := conn.WriteFrame(ws.OpBinary, []byte("hb")); werr != nil {
						s.log.Event("WS proactive hb write FAILED %s: %v", r.URL.Path, werr)
						return
					}
					continue
				}
			}
			s.log.Event("WS read end %s: %v", r.URL.Path, err)
			return
		}
		switch f.Opcode {
		case ws.OpText:
			s.log.Event("WS <- %s TEXT %q", r.URL.Path, string(f.Payload))
			if reply := s.respondText(f.Payload); reply != "" {
				s.log.Event("WS -> %s TEXT %q", r.URL.Path, reply)
				_ = conn.WriteText(reply)
			}
		case ws.OpBinary:
			s.log.Event("WS <- %s BINARY (%d bytes) %x", r.URL.Path, len(f.Payload), f.Payload)
			// AccelByte notification/lobby heartbeat is the binary token "hb";
			// echo it back. Kept alongside the proactive push above: the echo
			// is what stopped the initial ~5s close-cycle in an earlier
			// session, and a client probe should still get a reply.
			if string(f.Payload) == "hb" {
				if werr := conn.WriteFrame(ws.OpBinary, []byte("hb")); werr != nil {
					s.log.Event("WS hb echo write FAILED %s: %v", r.URL.Path, werr)
				}
			}
		case ws.OpPing:
			s.log.Event("WS <- %s PING", r.URL.Path)
			_ = conn.Pong(f.Payload)
		case ws.OpPong:
			// ignore
		case ws.OpClose:
			s.log.Event("WS <- %s CLOSE", r.URL.Path)
			return
		default:
			s.log.Event("WS <- %s op=0x%x (%d bytes) %x", r.URL.Path, f.Opcode, len(f.Payload), f.Payload)
		}
	}
}

// respondText answers an AccelByte lobby text message. The wire format is
// newline-separated `key: value` lines; the first is `type: <name>` and `id`
// must be echoed in the response. We reply success (`code: 0`) with empty
// collections — no friends/parties yet, but it satisfies the client so the
// social UI resolves instead of spinning. Returns "" when no reply is warranted
// (heartbeats, notifications, unknown types — those are just logged).
func (s *Service) respondText(payload []byte) string {
	msg := parseLobby(payload)
	id := msg["id"]
	switch msg["type"] {
	case "listOfFriendsRequest":
		return buildLobby("listOfFriendsResponse", id, "code: 0", "friendsId: []")
	case "listIncomingFriendsRequest":
		return buildLobby("listIncomingFriendsResponse", id, "code: 0", "friendsId: []")
	case "listOutgoingFriendsRequest":
		return buildLobby("listOutgoingFriendsResponse", id, "code: 0", "friendsId: []")
	case "setUserStatusRequest":
		return buildLobby("setUserStatusResponse", id, "code: 0")
	default:
		return ""
	}
}

// parseLobby splits a lobby message into its key/value fields.
func parseLobby(payload []byte) map[string]string {
	out := map[string]string{}
	for _, line := range strings.Split(string(payload), "\n") {
		k, v, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		out[strings.TrimSpace(k)] = strings.TrimSpace(v)
	}
	return out
}

// buildLobby assembles a response: a `type:` line, an echoed `id:` line, then
// any extra `key: value` lines.
func buildLobby(msgType, id string, fields ...string) string {
	lines := []string{"type: " + msgType, "id: " + id}
	lines = append(lines, fields...)
	return strings.Join(lines, "\n")
}

// pathMatchesPushTarget reports whether the connection path is the one
// phantomDsPushPath selects (exact match, or prefix for /notifications/players/).
func pathMatchesPushTarget(path string) bool {
	if phantomDsPushPath == "" {
		return true
	}
	if strings.HasSuffix(phantomDsPushPath, "/") {
		return strings.HasPrefix(path, phantomDsPushPath)
	}
	return path == phantomDsPushPath
}

// phantomDsPush sleeps phantomDsPushDelay, then writes a single AccelByte v1
// `matchmakingNotif` text frame carrying phantom DS info. The notif is built as
// a SUPERSET probe of plausible field names (UE matches case-insensitively and
// silently ignores unmatched keys; a matched-but-wrong-typed field rejects the
// whole notif with a LogJson warning we'll see in Loki.log). Includes both
// inline IP/Port AND a JSON-encoded `dsInfo` field so a parser that wants
// either layout finds something.
//
// Expected outcomes (each diagnostic):
//   - Loki.log emits `LogNet*`/`NetConnection`/`Failed to connect` against
//     127.0.0.1:7777  -> the push IS the trigger; the wire shape is at least
//     close enough. Path C scaffolding begins next session.
//   - Loki.log emits `LogJson` deserialize warnings naming a specific field ->
//     field type is wrong; the warning names the field, we fix and re-push.
//   - Loki.log silent (no error, no NetConnection) -> the wrong notif type
//     name, the wrong push channel, or a missing precondition (e.g. client
//     must send startMatchmakingRequest first). Iterate by flipping
//     phantomDsPushPath to /notifications/... or trying messageNotif instead.
func (s *Service) phantomDsPush(conn *ws.Conn, path string) {
	time.Sleep(phantomDsPushDelay)

	// dsInfo is the inner JSON payload — AccelByte SDK convention is to nest
	// DS connection info under a `dsInfo` key for v1 matchmakingNotif. Field
	// names use camelCase (AccelByte JSON style) AND PascalCase variants
	// (since some Theorycraft layers prefer Pascal); UE will ignore whichever
	// it doesn't match.
	dsInfoJSON := `{"status":"READY","matchId":"phantom-match-0001","sessionId":"phantom-session-0001","ip":"127.0.0.1","port":7777,"podName":"phantom-pod","gameMode":"tutorialNew","region":"na","namespace":"supervive","serverId":"phantom-server-0001","deployment":"phantom","gameVersion":"release2.4.live-156430-shipping"}`

	notif := buildLobby(
		"matchmakingNotif",
		"phantom-notif-0001",
		"status: done",
		"matchId: phantom-match-0001",
		"sessionId: phantom-session-0001",
		"gameMode: tutorialNew",
		"clientVersion: release2.4.live-156430-shipping",
		"namespace: supervive",
		"region: na",
		"joinable: true",
		"queuedAt: "+time.Now().UTC().Format(time.RFC3339),
		"matchingAllies: []",
		"partyAttributes: {}",
		// Inline DS info (top-level — Pascal+camel variants):
		"ip: 127.0.0.1",
		"port: 7777",
		"Address: 127.0.0.1",
		"Port: 7777",
		"ServerUrl: 127.0.0.1:7777",
		"Url: 127.0.0.1:7777",
		"podName: phantom-pod",
		"serverId: phantom-server-0001",
		// Nested DS info — AccelByte convention:
		"dsInfo: "+dsInfoJSON,
		"DsInfo: "+dsInfoJSON,
		"serverInfo: "+dsInfoJSON,
		"ServerInfo: "+dsInfoJSON,
	)

	s.log.Event("WS -> %s TEXT %q (phantom matchmakingNotif push)", path, notif)
	if err := conn.WriteText(notif); err != nil {
		s.log.Event("WS phantom matchmakingNotif push FAILED %s: %v", path, err)
	}
}

// phantomMatchmakingFlow drives probe #5: a two-frame matchmakingNotif
// sequence that simulates the client walking through "start matchmaking" and
// then "match found" purely from server-pushed messages. Hypothesis: the
// client's matchmaking subsystem won't act on status=done unless its own
// internal state is "matchmaking in progress" — pushing status=start first
// flips it into that state so status=done is then accepted.
//
// Timing:
//
//	t=0                          WS handshake completes; this goroutine starts
//	t=phantomMmStartDelay         push status=start
//	t=start + phantomMmDoneDelay  push status=done WITH DS info at 127.0.0.1:7777
//
// Outcomes (mirror probe #3's diagnostic table):
//   - LogNet*/NetConnection against 127.0.0.1:7777 -> WIN, state-machine
//     bootstrap works, Path C scaffolding begins.
//   - LogJson "Deserialization failure" naming a field -> the warning names it.
//   - LogPlatformLobby acknowledging matchmakingNotif but no NetConnection ->
//     state changed but DS info field shape wrong; iterate the done payload.
//   - Silent (no LogNet, no warning, no menu change) -> the matchmakingNotif
//     type itself is gated behind something we don't have (e.g. requires a
//     matchmakingRequest reply with the same ticket id BEFORE the notif).
func (s *Service) phantomMatchmakingFlow(conn *ws.Conn, path string) {
	// --- Stage 1: matchmaking started ---
	time.Sleep(phantomMmStartDelay)
	start := buildLobby(
		"matchmakingNotif",
		"phantom-mm-start-0001",
		"status: start",
		"matchId: phantom-match-0001",
		"sessionId: phantom-session-0001",
		"namespace: supervive",
		"gameMode: tutorialNew",
		"clientVersion: release2.4.live-156430-shipping",
		"queuedAt: "+time.Now().UTC().Format(time.RFC3339),
		"partyAttributes: {}",
	)
	s.log.Event("WS -> %s TEXT %q (phantom matchmakingNotif status=start, probe #5 stage 1)", path, start)
	if err := conn.WriteText(start); err != nil {
		s.log.Event("WS phantom mm start push FAILED %s: %v", path, err)
		return
	}

	// --- Stage 2: match found, DS ready ---
	time.Sleep(phantomMmDoneDelay)
	dsInfoJSON := `{"status":"READY","matchId":"phantom-match-0001","sessionId":"phantom-session-0001","ip":"127.0.0.1","port":7777,"podName":"phantom-pod","gameMode":"tutorialNew","region":"na","namespace":"supervive","serverId":"phantom-server-0001","deployment":"phantom","gameVersion":"release2.4.live-156430-shipping"}`
	done := buildLobby(
		"matchmakingNotif",
		"phantom-mm-done-0001",
		"status: done",
		"matchId: phantom-match-0001",
		"sessionId: phantom-session-0001",
		"namespace: supervive",
		"gameMode: tutorialNew",
		"clientVersion: release2.4.live-156430-shipping",
		"region: na",
		"joinable: true",
		"queuedAt: "+time.Now().UTC().Format(time.RFC3339),
		"matchingAllies: []",
		"partyAttributes: {}",
		// Inline DS info — Pascal+camel variants for case-strict fields:
		"ip: 127.0.0.1",
		"port: 7777",
		"Address: 127.0.0.1",
		"Port: 7777",
		"HostName: 127.0.0.1",
		"ServerUrl: 127.0.0.1:7777",
		"Url: 127.0.0.1:7777",
		"podName: phantom-pod",
		"serverId: phantom-server-0001",
		// Nested DS info — AccelByte convention:
		"dsInfo: "+dsInfoJSON,
		"DsInfo: "+dsInfoJSON,
		"serverInfo: "+dsInfoJSON,
		"ServerInfo: "+dsInfoJSON,
	)
	s.log.Event("WS -> %s TEXT %q (phantom matchmakingNotif status=done, probe #5 stage 2)", path, done)
	if err := conn.WriteText(done); err != nil {
		s.log.Event("WS phantom mm done push FAILED %s: %v", path, err)
	}
}
