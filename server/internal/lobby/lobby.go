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
	"os"
	"strings"
	"sync"
	"time"

	"supervive-revival/server/internal/ws"
)

// ---- LEGACY probe constants (probes #3 and #5) ----------------------------
//
// SUPERSEDED 2026-08-13 by the FK-15 push console in push.go + the admin
// panel's "WS Push" tab, which pushes operator-authored frames at runtime.
// Prefer it: these constants require a source edit, an ags rebuild and a fresh
// launch per variant, which is why this question has sat at N=5 for ~40
// sessions. They are also the two frames whose 20+ bundled speculative fields
// make their own negative results unattributable.
//
// Kept (disabled) because the trial-and-error history is the value — see the
// project's code conventions — and because they document the exact wire shapes
// already tried, which the console should not waste a launch repeating.
//
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
const phantomMatchmakingSequence = false

// Timing for probe #5's start→done sequence.
//   - phantomMmStartDelay: wait this long after WS connect before pushing
//     status=start. Gives the client's lobby subsystem time to finish handling
//     friends/status traffic (those land in the first ~2s post-connect).
//   - phantomMmDoneDelay: wait this long after status=start before pushing
//     status=done. Simulates the natural matchmaking duration; some clients
//     gate the done-handler behind "must have been start for at least N ms".
const phantomMmStartDelay = 3 * time.Second
const phantomMmDoneDelay = 2 * time.Second

// ⚠⚠ SUPERSEDED BY MEASUREMENT (S117, 2026-08-13) — docs/fk15-ws-push-audit.md §3.5.
// THIS PUSH HAS NEVER REACHED THE CLIENT'S HANDLER, and tuning the interval below
// cannot help. `UMessengerManager::OnMessage` (.text 0x57C8F00) parses each **TEXT**
// frame as ONE JSON object into FNotificationMessage{Resource,Version,Payload}, and
// only `Resource == "hb"` clears the 5 s watchdog. A BINARY frame never gets there:
// the messenger binds no binary delegate.
//
// The evidence was in every log the whole time. Over 1,419 connections (re-confirmed
// on a second, later log at 23/22/0/0):
//     Messenger connection established     1419
//     heartbeat not received in 5 seconds  1418   <- Warning: the category IS emitting
//     Messenger recieved message              0
//     Messenger recieved unexpected message   0   <- ALSO Warning; would have fired 1418x
// `recieved unexpected message` logs at Warning on a JSON parse failure, so our binary
// "hb" would have logged every single time. Zero, in a log carrying 1,418 Warnings from
// the same category ⇒ a CLEAN NEGATIVE, not a muted channel.
//
// Measured consequence: connect→kill median 60.0 s, EXACTLY ONE heartbeat per
// connection — the send period exceeds the connection's own lifetime, which is why no
// amount of interval tuning ever worked.
//
// FIX (untested live, ranked probe #2): on receiving the client's binary "hb", reply
// with a TEXT frame `{"Resource":"hb","Version":0,"Payload":""}`.
// ⚠ It also removes the free periodic resync the client currently gets from
// reconnecting — re-verify S85 avatar latency afterwards. The explicit Conn.Drop()
// lever (MarkDirty) is unaffected, and a per-resource version-bump push is a strictly
// better replacement for it: it refetches ONE resource with no teardown, which retires
// the "~1s reconnect floor is not backend-controllable" note below.
//
// ---- original note, kept for the trial-and-error record ----
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

// ---- probe #2: the TEXT heartbeat reply (S117, 2026-08-13) -----------------
//
// THE FIX for the ~60 s messenger reconnect churn, derived from the RE above and
// from probe #1's live confirmation that this socket delivers TEXT frames to the
// application layer (docs/fk15-probe1-live-result-20260813.txt).
//
// `UMessengerManager::OnMessage` parses each TEXT frame as ONE JSON object into
// FNotificationMessage{Resource,Version,Payload}. Only `Resource == "hb"` finds
// and clears the 5 s watchdog timer. Our BINARY echo cannot do it — binary frames
// never reach the handler at all (0 `recieved unexpected message` across 1,419
// connections, in logs carrying 1,418 same-category Warnings).
//
// SINGLE VARIABLE, deliberately. This change ADDS one TEXT write on receipt of the
// client's binary "hb" and touches nothing else:
//   - the existing BINARY echo stays (it is measured-inert, so leaving it cannot
//     affect the outcome, and removing it would be a second variable). Drop it in
//     a follow-up once this is confirmed.
//   - the proactive keepalive above stays BINARY, i.e. still inert. It is not
//     needed: the client's watchdog is armed by ITS OWN send, so a reply is
//     sufficient. Also a follow-up.
//
// Set enableTextHeartbeatReply = false to revert to exactly the prior behaviour.
//
// ⚠ EXPECTED SIDE EFFECT — check this before calling it a win. The ~60 s
// reconnect cycle is what currently gives the client a FREE periodic state
// resync, and S85's avatar fix piggybacks on that cycle. S85's explicit
// `Conn.Drop()` (MarkDirty) is UNAFFECTED — it is a deliberate drop, not the
// watchdog — so avatar switching should still work. What disappears is the
// implicit resync every ~60 s. Re-verify avatar latency after this lands, and
// watch for anything else that silently depended on the churn.
const enableTextHeartbeatReply = true

// messengerHeartbeatText is the exact frame the client's parser accepts. Field
// names match FNotificationMessage (schema.txt:37963) exactly; UE's JSON→UStruct
// matches case-insensitively and ignores unknown keys, but there is no reason to
// rely on either here.
const messengerHeartbeatText = `{"Resource":"hb","Version":0,"Payload":""}`

// ---- messenger-drop lever (S85 avatar-switch latency fix, 2026-07-21) ----
//
// The client APPLIES the party model (its avatar-card data source: the party
// member's PersonalizationLoadout) ONLY during the state-resync it runs on each
// LokiPlatformMessenger (/notifications) RECONNECT — not on the ~3.2s HTTP party
// polls, and not on any version bump. RE'd live (S85 ws-push workflow): a switch
// flipped 417ms after a reconnect resync fetch while ~9 intervening polls carried
// the identical fresh loadout and did NOT apply it. So the ~30s latency is just the
// time to the next reconnect in the ~63s heartbeat-watchdog cycle.
//
// Lever: when the loadout changes, DROP the player's messenger socket. The client
// reconnects in ~0.5-1.5s and its resync re-fetches GET /party/parties (which already
// carries personalizationLoadout via buildSoloParty) and re-applies it — collapsing
// ~30s to ~1-3s. Backend-only, no shim.
const enableMessengerDrop = true

// messengerDropDebounce coalesces rapid loadout writes (clicking through avatars) into
// at most one drop per window, so we never cause a reconnect storm. The reconnect's
// resync fetches CURRENT server state, so a coalesced burst still lands on the latest
// avatar. Must exceed the reconnect+resync time (~1.5s) so a drop can't interrupt the
// reconnect it just caused.
const messengerDropDebounce = 2 * time.Second

// EventLogger records frame activity to the capture log.
type EventLogger interface {
	Event(format string, args ...any)
}

// logf is the package's single logging path, nil-safe because New(nil) is a
// supported construction (the package's own tests use it, and MarkDirty is
// documented nil-safe). Handle previously called s.log.Event directly and
// panicked on a nil logger while dropMessenger nil-checked — an inconsistency
// found by the FK-15 push-console tests, not by production, since cmd/ags
// always passes a real capture logger.
func (s *Service) logf(format string, args ...any) {
	if s == nil || s.log == nil {
		return
	}
	s.log.Event(format, args...)
}

type Service struct {
	log EventLogger

	// mu guards the messenger registry + debounce clock.
	mu sync.Mutex
	// messengers maps a player id to that player's live /notifications messenger
	// conn, so MarkDirty can drop it on a loadout change. One entry per connected
	// player (single-account revival ⇒ realistically one).
	messengers map[string]*ws.Conn
	// lastDrop debounces MarkDirty per player.
	lastDrop map[string]time.Time
	// dropPending marks that a trailing drop is already scheduled for this player.
	dropPending map[string]bool

	// sockets is the FK-15 push console's registry of every live WS connection
	// (both /lobby and the messenger), keyed by a short stable handle. See push.go.
	sockets  map[string]*socket
	socketNo int
	// partyVersion supplies the monotonic party version for the targeted-resync
	// path (enableTargetedResync). Set once at startup; nil disables that path.
	partyVersion func() int64
}

// enableTargetedResync makes MarkDirty push a per-resource version bump instead
// of dropping the socket.
//
// ★★★ PROVEN END-TO-END LIVE, 2026-08-13 — REFETCH **AND APPLY**, NO TEARDOWN.
// docs/fk15-probe3-live-result-20260813.txt.
//
// The apply was demonstrated with a controlled round-trip on the lobby platform
// (the podium under the hunter), chosen because `loadout_fix.cpp` — which polls
// /revival/loadout every ~175 ms and would otherwise mask any result — contains
// ZERO lobby-platform code, while loadout.go:411 carries lobbyPlatformPreference
// inside the party document. So the podium is party-doc-driven and shim-blind.
//
//	A  backend already Collector, NO push  -> podium unchanged (client unaware)
//	B  push fired                          -> podium GOLD   (refetched + applied)
//	C  reverted to Starter + push          -> podium BLUE   (applied in reverse)
//
// Throughout: messenger DROP 0, connects 1, socket uptime continuous.
//
// ⇒ S85's socket drop is RETIRED as the primary lever. It remains the fallback
// (see dropMessenger) for when there is no version source or no live messenger,
// so a loadout change can never end up with no mechanism at all.
// ⇒ lobby.go's old note that the "~1 s reconnect floor is not backend-
// controllable" is OBSOLETE: there is no reconnect any more.
//
// Set false to revert to the drop.
const enableTargetedResync = true

func New(log EventLogger) *Service {
	return &Service{
		log:         log,
		messengers:  map[string]*ws.Conn{},
		lastDrop:    map[string]time.Time{},
		dropPending: map[string]bool{},
		sockets:     map[string]*socket{},
	}
}

// registerMessenger records a player's live messenger conn (called on upgrade).
func (s *Service) registerMessenger(id string, c *ws.Conn) {
	if id == "" {
		return
	}
	s.mu.Lock()
	s.messengers[id] = c
	s.mu.Unlock()
}

// unregisterMessenger drops the registry entry ONLY if it still points at this
// conn (a newer reconnect may have replaced it). Called from Handle's defer.
func (s *Service) unregisterMessenger(id string, c *ws.Conn) {
	if id == "" {
		return
	}
	s.mu.Lock()
	if s.messengers[id] == c {
		delete(s.messengers, id)
	}
	s.mu.Unlock()
}

// MarkDirty forces player id's client to re-apply its party promptly by dropping its
// messenger socket (see enableMessengerDrop). Safe to call from any goroutine (the
// interactive package calls it after a loadout write) and nil-safe on a nil *Service so
// callers need no lobby dependency in tests.
//
// Debounce is LEADING + TRAILING: the first change in an idle window drops immediately
// (fast single switch), and further changes within the window schedule ONE trailing drop
// at the window's end. The trailing drop matters because the reconnect's resync fetches
// CURRENT server state — so coalescing a rapid click-through of avatars into (at most) a
// leading drop + a trailing drop still lands the FINAL selection, without a reconnect
// storm. The window must exceed the reconnect time so a drop never interrupts the
// reconnect it just caused.
func (s *Service) MarkDirty(id string) {
	if s == nil || !enableMessengerDrop || id == "" {
		return
	}
	s.mu.Lock()
	elapsed := time.Since(s.lastDrop[id])
	if elapsed >= messengerDropDebounce {
		// Leading edge: drop now.
		s.lastDrop[id] = time.Now()
		c := s.messengers[id]
		s.mu.Unlock()
		s.dropMessenger(id, c)
		return
	}
	// Inside the window: ensure exactly one trailing drop is scheduled for its end.
	if !s.dropPending[id] {
		s.dropPending[id] = true
		delay := messengerDropDebounce - elapsed
		time.AfterFunc(delay, func() {
			s.mu.Lock()
			s.dropPending[id] = false
			s.lastDrop[id] = time.Now()
			c := s.messengers[id]
			s.mu.Unlock()
			s.dropMessenger(id, c)
		})
	}
	s.mu.Unlock()
}

// dropMessenger makes player id's client re-read its party.
//
// Two mechanisms, selected by enableTargetedResync:
//   - targeted (probe #3): push a per-resource version bump. The client
//     refetches just that resource and the socket stays up. MEASURED to trigger
//     a refetch in 491 ms with no reconnect — but see the flag's comment for why
//     it is not the default yet.
//   - drop (S85, default): ungracefully close the socket. The client reconnects
//     in ~0.7-1.5 s and its resync re-reads everything. Heavier, but it is the
//     path with a measured end-to-end avatar-apply result.
//
// The targeted path FALLS BACK to the drop if it cannot push (no version source,
// or no live messenger), so enabling the flag can never leave a loadout change
// with no mechanism at all.
func (s *Service) dropMessenger(id string, c *ws.Conn) {
	if enableTargetedResync && s.notifyPartyResources(id) {
		s.logf("messenger TARGETED RESYNC for %s (loadout changed -> per-resource version bump, socket kept)", id)
		return
	}
	if c == nil {
		return
	}
	if s.log != nil {
		s.logf("messenger DROP for %s (loadout changed -> force reconnect+resync)", id)
	}
	_ = c.Drop() // ungraceful: unblocks the read loop, which returns + cleans up
}

// messengerPlayerID extracts the player id from a /notifications/players/{id} path.
func messengerPlayerID(path string) string {
	const p = "/notifications/players/"
	if !strings.HasPrefix(path, p) {
		return ""
	}
	rest := strings.TrimPrefix(path, p)
	if i := strings.IndexByte(rest, '/'); i >= 0 {
		rest = rest[:i]
	}
	return rest
}

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
		s.logf("WS upgrade FAILED %s: %v", r.URL.Path, err)
		return
	}
	s.logf("WS connected %s (subproto=%q) envelope=[%q..%q]", r.URL.Path,
		r.Header.Get("Sec-WebSocket-Protocol"), conn.EnvelopeStart, conn.EnvelopeEnd)
	defer func() {
		conn.Close()
		s.logf("WS closed %s", r.URL.Path)
	}()

	// FK-15 push console: register every live socket so the admin panel can
	// address it by handle and push a single, operator-authored frame at it.
	// Registration is unconditional (both /lobby and the messenger) because the
	// whole point is that only ONE of the two channels has ever been probed.
	handle := s.registerSocket(r.URL.Path, conn)
	defer s.unregisterSocket(handle)

	isMessenger := strings.HasPrefix(r.URL.Path, "/notifications/players/")
	if isMessenger {
		// Register this messenger conn so MarkDirty can drop it on a loadout change
		// (see the messenger-drop lever above). Unregister on exit.
		id := messengerPlayerID(r.URL.Path)
		s.registerMessenger(id, conn)
		defer s.unregisterMessenger(id, conn)
	}

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
					s.logf("WS -> %s BINARY hb (proactive %s keepalive)", r.URL.Path, messengerHeartbeatInterval)
					if werr := conn.WriteFrame(ws.OpBinary, []byte("hb")); werr != nil {
						s.logf("WS proactive hb write FAILED %s: %v", r.URL.Path, werr)
						return
					}
					continue
				}
			}
			s.logf("WS read end %s: %v", r.URL.Path, err)
			return
		}
		switch f.Opcode {
		case ws.OpText:
			s.logf("WS <- %s TEXT %q", r.URL.Path, string(f.Payload))
			if reply := s.respondText(f.Payload); reply != "" {
				s.logf("WS -> %s TEXT %q", r.URL.Path, reply)
				_ = conn.WriteText(reply)
			}
		case ws.OpBinary:
			s.logf("WS <- %s BINARY (%d bytes) %x", r.URL.Path, len(f.Payload), f.Payload)
			// AccelByte notification/lobby heartbeat is the binary token "hb";
			// echo it back. Kept alongside the proactive push above: the echo
			// is what stopped the initial ~5s close-cycle in an earlier
			// session, and a client probe should still get a reply.
			if string(f.Payload) == "hb" {
				if werr := conn.WriteFrame(ws.OpBinary, []byte("hb")); werr != nil {
					s.logf("WS hb echo write FAILED %s: %v", r.URL.Path, werr)
				}
				// Probe #2: the reply that can actually clear the client's 5 s
				// watchdog. Messenger only — /lobby is a different protocol and
				// would just log this as an unparseable message.
				if isMessenger && enableTextHeartbeatReply {
					s.logf("WS -> %s TEXT hb reply %s", r.URL.Path, messengerHeartbeatText)
					if werr := conn.WriteText(messengerHeartbeatText); werr != nil {
						s.logf("WS hb TEXT reply FAILED %s: %v", r.URL.Path, werr)
					}
				}
			}
		case ws.OpPing:
			s.logf("WS <- %s PING", r.URL.Path)
			_ = conn.Pong(f.Payload)
		case ws.OpPong:
			// ignore
		case ws.OpClose:
			s.logf("WS <- %s CLOSE", r.URL.Path)
			return
		default:
			s.logf("WS <- %s op=0x%x (%d bytes) %x", r.URL.Path, f.Opcode, len(f.Payload), f.Payload)
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
		return buildLobby("listOfFriendsResponse", id, "code: 0", probeFriendsID())
	case "listIncomingFriendsRequest":
		return buildLobby("listIncomingFriendsResponse", id, "code: 0", probeIDList("AGS_PROBE_INCOMING"))
	case "listOutgoingFriendsRequest":
		return buildLobby("listOutgoingFriendsResponse", id, "code: 0", probeIDList("AGS_PROBE_OUTGOING"))
	case "setUserStatusRequest":
		return buildLobby("setUserStatusResponse", id, "code: 0")
	default:
		return ""
	}
}

// probeFriendsID renders the `friendsId` line of listOfFriendsResponse. It is
// EMPTY by default, so a normal sitting is byte-identical to one taken before
// this existed; set `AGS_PROBE_FRIEND=<userId>` to inject one synthetic friend.
//
// WHY THIS EXISTS (S118, 2026-08-13). `userStatusNotif` is one of the 7 notif
// types whose client delegate has a subscriber (`docs/fk15-bound-delegate-map-20260813.md`),
// but pushing it produced no observable effect — because with `friendsId: []`
// the client has NO ROW to render a presence update into. That null was
// uninterpretable, not negative: exactly the method-rule-11 trap ("what would
// have to be true for this indicator to change at all, and is it true now?").
// Injecting a friend gives presence something to attach to, so ONLINE/OFFLINE
// can be driven back and forth as a round trip rather than argued from one
// before/after pair.
//
// ⚠ Deliberately does NOT also answer `friendsStatusRequest` (which the client
// sends to ask for friends' presence, and which we still do not handle). That
// keeps the experiment single-variable: with no status response, the ONLY way
// the friend can appear online is our pushed `userStatusNotif`.
func probeFriendsID() string { return probeIDList("AGS_PROBE_FRIEND") }

// probeIDList renders a `friendsId` line from an env knob, empty by default.
//
// AGS_PROBE_FRIEND    -> listOfFriendsResponse         (established friends)
// AGS_PROBE_INCOMING  -> listIncomingFriendsResponse   (requests TO us)
// AGS_PROBE_OUTGOING  -> listOutgoingFriendsResponse   (requests FROM us)
//
// The incoming/outgoing knobs exist for the same reason as the first
// (S118): `cancelFriendsNotif` and `rejectFriendsNotif` act on the PENDING
// request lists, so with both served empty there is nothing for them to
// remove and their nulls would be uninterpretable rather than negative.
//
// ⚠ `cancelFriendsNotif` needed no knob — an incoming request can be created
// with a push (`requestFriendsNotif`), which is strictly better because the
// precondition is then built by the same mechanism under test. `rejectFriends`
// has no such push: it acts on the OUTGOING list, which only the client can
// populate (via `requestFriendsRequest`, which we do not answer). Hence this.
func probeIDList(env string) string {
	if id := os.Getenv(env); id != "" {
		return "friendsId: [" + id + "]"
	}
	return "friendsId: []"
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

	s.logf("WS -> %s TEXT %q (phantom matchmakingNotif push)", path, notif)
	if err := conn.WriteText(notif); err != nil {
		s.logf("WS phantom matchmakingNotif push FAILED %s: %v", path, err)
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
	s.logf("WS -> %s TEXT %q (phantom matchmakingNotif status=start, probe #5 stage 1)", path, start)
	if err := conn.WriteText(start); err != nil {
		s.logf("WS phantom mm start push FAILED %s: %v", path, err)
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
	s.logf("WS -> %s TEXT %q (phantom matchmakingNotif status=done, probe #5 stage 2)", path, done)
	if err := conn.WriteText(done); err != nil {
		s.logf("WS phantom mm done push FAILED %s: %v", path, err)
	}
}
