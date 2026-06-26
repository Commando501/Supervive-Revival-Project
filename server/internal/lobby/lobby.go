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
	"net/http"
	"strings"

	"supervive-revival/server/internal/ws"
)

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

	for {
		f, err := conn.ReadFrame()
		if err != nil {
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
			// echo it back or the socket closes and reconnects every ~5s.
			if string(f.Payload) == "hb" {
				_ = conn.WriteFrame(ws.OpBinary, []byte("hb"))
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
