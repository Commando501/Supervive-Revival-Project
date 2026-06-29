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
