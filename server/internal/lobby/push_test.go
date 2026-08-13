package lobby

import (
	"bufio"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// FK-15 push console tests.
//
// The load-bearing one is TestPushLargeFrameReachesClientIntact. Before this
// existed, "our 1.5 KB phantom frames left the server correctly" was an
// eyeball read of ws.WriteFrame's length encoding, not a measurement — and the
// suspicious split in the evidence (short solicited responses appear to work,
// long unsolicited pushes appear to vanish) is EXACTLY what a broken extended
// payload-length path would look like. That hypothesis is cheap to test
// offline and expensive to leave open, since it would silently void all five
// probes. This test settles it by reading our own frames back with an
// independent strict RFC 6455 decoder.
// ---------------------------------------------------------------------------

// ---- a deliberately independent client-side frame decoder ------------------
// Written from RFC 6455 §5.2 rather than reusing ws.ReadFrame, so a bug shared
// between our reader and our writer cannot hide from this test (two instruments
// with the same blind spot are not corroboration — docs/method-rules.md §1).

type clientFrame struct {
	fin    bool
	opcode byte
	masked bool
	body   []byte
}

func readClientFrame(br *bufio.Reader) (clientFrame, error) {
	var h [2]byte
	if _, err := io.ReadFull(br, h[:]); err != nil {
		return clientFrame{}, err
	}
	f := clientFrame{
		fin:    h[0]&0x80 != 0,
		opcode: h[0] & 0x0f,
		masked: h[1]&0x80 != 0,
	}
	n := uint64(h[1] & 0x7f)
	switch n {
	case 126:
		var e [2]byte
		if _, err := io.ReadFull(br, e[:]); err != nil {
			return clientFrame{}, err
		}
		n = uint64(binary.BigEndian.Uint16(e[:]))
		if n < 126 {
			return clientFrame{}, fmt.Errorf("RFC 6455 §5.2: 16-bit length %d must not be minimally encodable", n)
		}
	case 127:
		var e [8]byte
		if _, err := io.ReadFull(br, e[:]); err != nil {
			return clientFrame{}, err
		}
		n = binary.BigEndian.Uint64(e[:])
		if n < 1<<16 {
			return clientFrame{}, fmt.Errorf("RFC 6455 §5.2: 64-bit length %d must not be minimally encodable", n)
		}
	}
	if f.masked {
		return clientFrame{}, fmt.Errorf("RFC 6455 §5.1: server->client frames MUST NOT be masked")
	}
	f.body = make([]byte, n)
	if _, err := io.ReadFull(br, f.body); err != nil {
		return clientFrame{}, err
	}
	return f, nil
}

// liveSocket stands up the real lobby.Handle over a real TCP socket, completes
// a real WebSocket handshake, and returns a reader positioned on the first
// server frame. This exercises the entire production path: net/http hijack,
// ws.Upgrade, the registry, and ws.WriteFrame.
func liveSocket(t *testing.T, path string) (*Service, *bufio.Reader, net.Conn) {
	t.Helper()

	svc := New(nil)
	srv := httptest.NewServer(http.HandlerFunc(svc.Handle))
	t.Cleanup(srv.Close)

	host := strings.TrimPrefix(srv.URL, "http://")
	c, err := net.Dial("tcp", host)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	t.Cleanup(func() { c.Close() })

	var keyRaw [16]byte
	if _, err := rand.Read(keyRaw[:]); err != nil {
		t.Fatalf("rand: %v", err)
	}
	key := base64.StdEncoding.EncodeToString(keyRaw[:])
	req := "GET " + path + " HTTP/1.1\r\nHost: " + host + "\r\n" +
		"Upgrade: websocket\r\nConnection: Upgrade\r\n" +
		"Sec-WebSocket-Key: " + key + "\r\nSec-WebSocket-Version: 13\r\n\r\n"
	if _, err := c.Write([]byte(req)); err != nil {
		t.Fatalf("write handshake: %v", err)
	}

	br := bufio.NewReader(c)
	resp, err := http.ReadResponse(br, nil)
	if err != nil {
		t.Fatalf("read handshake response: %v", err)
	}
	if resp.StatusCode != http.StatusSwitchingProtocols {
		t.Fatalf("handshake status = %d, want 101", resp.StatusCode)
	}

	// Wait for the socket to appear in the registry before returning, so a
	// push can't race registration.
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if len(svc.Sockets()) > 0 {
			return svc, br, c
		}
		time.Sleep(2 * time.Millisecond)
	}
	t.Fatalf("socket never registered")
	return nil, nil, nil
}

// TestPushLargeFrameReachesClientIntact is the transport exoneration test.
//
// It pushes bodies that straddle every RFC 6455 payload-length boundary,
// including 1,462 bytes — the size class of the five phantom matchmakingNotif
// probes, which is squarely in the 16-bit extended-length path that the short
// working frames (an `hb` echo is 2 bytes, `listOfFriendsResponse` ~60) never
// touch. If the extended path were wrong, every probe would have been dropped
// by the client's WS layer before any application code saw it, and all five
// negatives would be void.
func TestPushLargeFrameReachesClientIntact(t *testing.T) {
	sizes := []int{
		1,     // trivial
		2,     // the "hb" heartbeat token
		60,    // a real listOfFriendsResponse
		125,   // last 7-bit length
		126,   // first 16-bit length
		127,   // just past the boundary
		1462,  // the phantom matchmakingNotif size class
		65535, // last 16-bit length
		65536, // first 64-bit length
	}
	for _, n := range sizes {
		t.Run(fmt.Sprintf("%dB", n), func(t *testing.T) {
			svc, br, _ := liveSocket(t, "/lobby")

			body := make([]byte, n)
			for i := range body {
				body[i] = byte('A' + i%26)
			}

			h := svc.Sockets()[0].Handle
			if _, err := svc.Push(PushRequest{
				Socket: h,
				Raw:    string(body),
				Label:  "transport-check",
			}); err != nil {
				t.Fatalf("push: %v", err)
			}

			f, err := readClientFrame(br)
			if err != nil {
				t.Fatalf("client decode: %v", err)
			}
			if !f.fin {
				t.Errorf("FIN not set")
			}
			if f.opcode != 0x1 {
				t.Errorf("opcode = 0x%x, want 0x1 (text)", f.opcode)
			}
			if len(f.body) != n {
				t.Fatalf("payload length = %d, want %d", len(f.body), n)
			}
			if string(f.body) != string(body) {
				t.Errorf("payload corrupted in transit")
			}
		})
	}
}

// TestBuildPayloadIsExactlyWhatWasAsked pins the single-variable guarantee: the
// builder adds nothing, drops nothing, and preserves field order. The original
// probes' 20+ bundled fields are why their negatives cannot name a cause; a
// builder that quietly injected an extra line would reintroduce that defect
// invisibly.
func TestBuildPayloadIsExactlyWhatWasAsked(t *testing.T) {
	got, err := BuildPayload(PushRequest{
		Type: "partyInviteNotif",
		Fields: []Field{
			{Key: "partyId", Value: "p-1"},
			{Key: "from", Value: "u-1"},
		},
		Label: "x",
	})
	if err != nil {
		t.Fatalf("build: %v", err)
	}
	want := "type: partyInviteNotif\npartyId: p-1\nfrom: u-1"
	if string(got) != want {
		t.Fatalf("built %q, want %q", got, want)
	}

	// No `id:` line unless one was supplied — an auto-generated id would be an
	// uncontrolled variable, and an unsolicited notif may be expected to carry
	// none at all. This is the deliberate asymmetry with buildLobby().
	if strings.Contains(string(got), "id:") {
		t.Errorf("builder injected an id: line that the operator did not ask for")
	}
}

// TestBuildPayloadOrderIsStable: the same request must produce byte-identical
// output every time, or a "one variable changed" claim is unfalsifiable.
func TestBuildPayloadOrderIsStable(t *testing.T) {
	req := PushRequest{
		Type: "t",
		ID:   "i",
		Fields: []Field{
			{Key: "z", Value: "1"}, {Key: "a", Value: "2"}, {Key: "m", Value: "3"},
		},
	}
	first, err := BuildPayload(req)
	if err != nil {
		t.Fatalf("build: %v", err)
	}
	for i := 0; i < 50; i++ {
		again, err := BuildPayload(req)
		if err != nil {
			t.Fatalf("build: %v", err)
		}
		if string(again) != string(first) {
			t.Fatalf("payload not deterministic: %q vs %q", again, first)
		}
	}
	if string(first) != "type: t\nid: i\nz: 1\na: 2\nm: 3" {
		t.Fatalf("unexpected payload %q", first)
	}
}

// TestPushRequiresLabel: an unlabelled probe cannot be found in the capture log
// afterwards, which is precisely why the 5 original probes are hard to
// reconstruct. Refuse it at the door.
func TestPushRequiresLabel(t *testing.T) {
	svc, _, _ := liveSocket(t, "/lobby")
	_, err := svc.Push(PushRequest{Socket: svc.Sockets()[0].Handle, Raw: "hi"})
	if err == nil {
		t.Fatal("expected an unlabelled push to be rejected")
	}
	if !strings.Contains(err.Error(), "label") {
		t.Fatalf("error should name the label requirement, got %v", err)
	}
}

// TestPushRejectsAmbiguousBody: raw and type+fields together is operator error,
// not something to guess at.
func TestPushRejectsAmbiguousBody(t *testing.T) {
	if _, err := BuildPayload(PushRequest{Raw: "x", Type: "y"}); err == nil {
		t.Fatal("expected raw+type to be rejected")
	}
	if _, err := BuildPayload(PushRequest{}); err == nil {
		t.Fatal("expected an empty body to be rejected")
	}
}

// TestPushNoLiveSocketIsAnError: pushing into the void must fail loudly. A
// silent success here is the delivery-vs-effect confusion that FK-11 records
// as a repeat offender — the operator would score a null result against a
// frame that never left the building.
func TestPushNoLiveSocketIsAnError(t *testing.T) {
	svc := New(nil)
	if _, err := svc.Push(PushRequest{Path: "/lobby", Raw: "x", Label: "l"}); err == nil {
		t.Fatal("expected an error when no socket is live")
	}
}

// TestHexBodyDecodes covers the messenger's binary channel, whose only known
// token today is "hb" (0x68 0x62).
func TestHexBodyDecodes(t *testing.T) {
	got, err := BuildPayload(PushRequest{Raw: "68 62", HexBody: true})
	if err != nil {
		t.Fatalf("build: %v", err)
	}
	if string(got) != "hb" {
		t.Fatalf("decoded %q, want %q", got, "hb")
	}
	if _, err := BuildPayload(PushRequest{Raw: "abc", HexBody: true}); err == nil {
		t.Fatal("expected odd-length hex to be rejected")
	}
}

// TestSocketsListsBothChannels: the messenger socket must be addressable too.
// Its exclusion from the probe surface was an accident of where the first probe
// happened to be written, and it is the channel already proven to drive client
// behaviour (S85).
func TestSocketsListsBothChannels(t *testing.T) {
	svc, _, _ := liveSocket(t, "/notifications/players/abc123")
	socks := svc.Sockets()
	if len(socks) != 1 {
		t.Fatalf("got %d sockets, want 1", len(socks))
	}
	if socks[0].Kind != "messenger" {
		t.Errorf("kind = %q, want messenger", socks[0].Kind)
	}
	if socks[0].PlayerID != "abc123" {
		t.Errorf("playerId = %q, want abc123", socks[0].PlayerID)
	}
}

// TestSocketUnregistersOnClose: a stale handle must not linger, or an operator
// pushes at a socket the client already replaced and scores the null against
// the wrong thing.
func TestSocketUnregistersOnClose(t *testing.T) {
	svc, _, c := liveSocket(t, "/lobby")
	if len(svc.Sockets()) != 1 {
		t.Fatalf("expected 1 socket")
	}
	c.Close()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if len(svc.Sockets()) == 0 {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatal("socket handle leaked after close")
}

// TestConcurrentPushesDoNotInterleave: writes must stay frame-aligned under
// concurrency, or a probe's payload is silently corrupted by the read loop's
// heartbeat echo and the resulting null is meaningless.
func TestConcurrentPushesDoNotInterleave(t *testing.T) {
	svc, br, _ := liveSocket(t, "/lobby")
	h := svc.Sockets()[0].Handle

	const n = 40
	body := strings.Repeat("Z", 300)
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = svc.Push(PushRequest{Socket: h, Raw: body, Label: "concurrent"})
		}()
	}
	wg.Wait()

	for i := 0; i < n; i++ {
		f, err := readClientFrame(br)
		if err != nil {
			t.Fatalf("frame %d: %v", i, err)
		}
		if string(f.body) != body {
			t.Fatalf("frame %d corrupted: len=%d", i, len(f.body))
		}
	}
}

// TestSweepWalksVocabulary: a sweep must push one frame per type, in order,
// each individually labelled so a reaction can be attributed to a frame.
func TestSweepWalksVocabulary(t *testing.T) {
	svc, br, _ := liveSocket(t, "/lobby")
	h := svc.Sockets()[0].Handle

	types := []string{"partyInviteNotif", "dsNotif", "userStatusNotif"}
	res, err := svc.Sweep(SweepRequest{Socket: h, Types: types, GapMs: 1, Label: "sweep1"})
	if err != nil {
		t.Fatalf("sweep: %v", err)
	}
	if len(res) != len(types) {
		t.Fatalf("pushed %d frames, want %d", len(res), len(types))
	}
	for i, want := range types {
		got, err := readClientFrame(br)
		if err != nil {
			t.Fatalf("frame %d: %v", i, err)
		}
		if string(got.body) != "type: "+want {
			t.Fatalf("frame %d = %q, want %q", i, got.body, "type: "+want)
		}
	}
}

// TestSweepDefaultsToFullVocabulary and skips what was already probed, so a
// launch is not spent re-confirming a known null.
func TestSweepSkipsProbed(t *testing.T) {
	svc, br, _ := liveSocket(t, "/lobby")
	h := svc.Sockets()[0].Handle

	go func() {
		// Drain so the sweep's writes never block on a full socket buffer.
		for {
			if _, err := readClientFrame(br); err != nil {
				return
			}
		}
	}()

	res, err := svc.Sweep(SweepRequest{Socket: h, GapMs: 1, Label: "full", Skip: true})
	if err != nil {
		t.Fatalf("sweep: %v", err)
	}
	if want := len(LobbyNotifTypes) - len(AlreadyProbed); len(res) != want {
		t.Fatalf("pushed %d, want %d (vocabulary minus already-probed)", len(res), want)
	}
	// Compare the WHOLE payload, not a substring: `rematchmakingNotif` contains
	// `matchmakingNotif`, so a Contains() assertion here fails on a correct
	// implementation. That is the same substring-vs-token trap that made a naive
	// scan report `dsNotif` 10 times when it occurs once (see vocabulary.go) —
	// worth keeping the note, since it caught this test rather than the code.
	for _, r := range res {
		if r.Payload == "type: matchmakingNotif" {
			t.Error("skipProbed should have excluded matchmakingNotif")
		}
	}
}

// TestSweepAbortsOnDeadSocket: everything after a dead socket would be pushed
// into the void and score as a false null, so the sweep must stop and say where.
func TestSweepAbortsOnDeadSocket(t *testing.T) {
	svc, _, c := liveSocket(t, "/lobby")
	h := svc.Sockets()[0].Handle
	c.Close()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) && len(svc.Sockets()) > 0 {
		time.Sleep(5 * time.Millisecond)
	}
	_, err := svc.Sweep(SweepRequest{Socket: h, GapMs: 1, Label: "dead"})
	if err == nil {
		t.Fatal("sweep into a dead socket must error")
	}
	if !strings.Contains(err.Error(), "aborted at") {
		t.Fatalf("error should name where it aborted, got %v", err)
	}
}

// TestVocabularyIntegrity guards the recovered table against silent edits: the
// count and two load-bearing members are pinned, since the whole FK-15 re-open
// rests on dsNotif being present and on matchmakingNotif being 1 of 32.
func TestVocabularyIntegrity(t *testing.T) {
	// 33, tied to the 33-entry jump table at .text 0x04B04978 — not to a regex.
	// A endswith("Notif") filter yields 32 by dropping the two *Notification cases.
	if len(LobbyNotifTypes) != 33 {
		t.Fatalf("vocabulary has %d types, want 33", len(LobbyNotifTypes))
	}
	seen := map[string]bool{}
	for _, tp := range LobbyNotifTypes {
		if seen[tp] {
			t.Errorf("duplicate type %q", tp)
		}
		seen[tp] = true
		if !strings.HasSuffix(tp, "Notif") && !strings.HasSuffix(tp, "Notification") {
			t.Errorf("%q is not a notification type", tp)
		}
	}
	for _, must := range []string{"dsNotif", "matchmakingNotif", "partyInviteNotif",
		// The two the suffix filter drops, and the v2 envelope with its own handler.
		"userBannedNotification", "userUnbannedNotification", "messageSessionNotif"} {
		if !seen[must] {
			t.Errorf("vocabulary is missing %q", must)
		}
	}
	if seen["dsNotice"] {
		t.Error("dsNotice is NOT the AccelByte token and is absent from the image")
	}
	// Sits inside the Request block at 0x86018F8, outside the 33-case dispatch
	// sub-block. Including it is how a too-wide scan window reaches a wrong 33.
	if seen["signalingP2PNotif"] {
		t.Error("signalingP2PNotif is not one of the 33 dispatch cases")
	}
}

// ---- probe #2: the TEXT heartbeat reply ------------------------------------

// TestMessengerHeartbeatSendsTextReply: on the client's binary "hb", the server
// must emit a TEXT frame whose JSON carries Resource=="hb". That is the ONLY
// thing measured to clear the client's 5 s watchdog; the binary echo cannot,
// because binary frames never reach UMessengerManager::OnMessage.
func TestMessengerHeartbeatSendsTextReply(t *testing.T) {
	svc, br, c := liveSocket(t, "/notifications/players/abc123")
	_ = svc
	writeMaskedFrame(t, c, 0x2, []byte("hb")) // client->server frames are masked

	var sawBinaryEcho, sawTextReply bool
	for i := 0; i < 2; i++ {
		f, err := readClientFrame(br)
		if err != nil {
			t.Fatalf("frame %d: %v", i, err)
		}
		switch f.opcode {
		case 0x2:
			if string(f.body) == "hb" {
				sawBinaryEcho = true
			}
		case 0x1:
			if string(f.body) != messengerHeartbeatText {
				t.Fatalf("TEXT reply = %q, want %q", f.body, messengerHeartbeatText)
			}
			sawTextReply = true
		}
	}
	if !sawTextReply {
		t.Error("no TEXT heartbeat reply — the watchdog cannot be cleared")
	}
	if !sawBinaryEcho {
		t.Error("binary echo disappeared; this change was supposed to be additive")
	}
}

// TestHeartbeatTextIsValidNotificationMessage pins the wire shape against the
// client's struct. Resource is the discriminator; a typo here is a silent
// no-op that would read as "the fix didn't work".
func TestHeartbeatTextIsValidNotificationMessage(t *testing.T) {
	var msg struct {
		Resource string `json:"Resource"`
		Version  int64  `json:"Version"`
		Payload  string `json:"Payload"`
	}
	if err := json.Unmarshal([]byte(messengerHeartbeatText), &msg); err != nil {
		t.Fatalf("heartbeat frame is not valid JSON: %v", err)
	}
	if msg.Resource != "hb" {
		t.Fatalf("Resource = %q, want exactly \"hb\"", msg.Resource)
	}
}

// TestLobbySocketGetsNoTextHeartbeat: /lobby speaks a different protocol, where
// this frame would just be an unparseable message. Scope the fix to the socket
// it was measured on.
func TestLobbySocketGetsNoTextHeartbeat(t *testing.T) {
	_, br, c := liveSocket(t, "/lobby")
	writeMaskedFrame(t, c, 0x2, []byte("hb"))

	f, err := readClientFrame(br)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	if f.opcode != 0x2 {
		t.Fatalf("first reply opcode = 0x%x, want 0x2 (binary echo only)", f.opcode)
	}
	// Nothing further should arrive.
	c.SetReadDeadline(time.Now().Add(300 * time.Millisecond))
	if f2, err := readClientFrame(br); err == nil {
		t.Fatalf("unexpected extra frame on /lobby: opcode 0x%x %q", f2.opcode, f2.body)
	}
}

// writeMaskedFrame sends a client->server frame with the mandatory mask (RFC 6455
// §5.3). Using an unmasked frame here would exercise a path the real client never
// takes.
func writeMaskedFrame(t *testing.T, c net.Conn, opcode byte, payload []byte) {
	t.Helper()
	if len(payload) >= 126 {
		t.Fatalf("helper only handles short frames")
	}
	mask := [4]byte{0xAA, 0xBB, 0xCC, 0xDD}
	buf := []byte{0x80 | opcode, 0x80 | byte(len(payload))}
	buf = append(buf, mask[:]...)
	for i, b := range payload {
		buf = append(buf, b^mask[i%4])
	}
	if _, err := c.Write(buf); err != nil {
		t.Fatalf("write masked frame: %v", err)
	}
}

// ---- probe #3: targeted per-resource resync ---------------------------------

// TestNotifyResourceWireShape pins the frame against FNotificationMessage. The
// client's refetch gate is "Version > cached"; a malformed field name here is a
// silent no-op that reads as "the client ignored it".
func TestNotifyResourceWireShape(t *testing.T) {
	svc, br, _ := liveSocket(t, "/notifications/players/p42")
	if err := svc.NotifyResource("p42", "/match-history/players/p42", 7, "t"); err != nil {
		t.Fatalf("notify: %v", err)
	}
	f, err := readClientFrame(br)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	if f.opcode != 0x1 {
		t.Fatalf("opcode = 0x%x, want TEXT", f.opcode)
	}
	var msg struct {
		Resource string
		Version  int64
		Payload  string
	}
	if err := json.Unmarshal(f.body, &msg); err != nil {
		t.Fatalf("frame is not valid JSON: %v (%q)", err, f.body)
	}
	if msg.Resource != "/match-history/players/p42" || msg.Version != 7 {
		t.Fatalf("got %+v", msg)
	}
}

// TestNotifyResourceQuotesResource: a resource containing a quote must not be
// able to break out of the JSON string and forge extra fields.
func TestNotifyResourceQuotesResource(t *testing.T) {
	svc, br, _ := liveSocket(t, "/notifications/players/p1")
	if err := svc.NotifyResource("p1", `/x","Version":999,"z":"`, 1, "t"); err != nil {
		t.Fatalf("notify: %v", err)
	}
	f, _ := readClientFrame(br)
	var msg struct {
		Resource string
		Version  int64
	}
	if err := json.Unmarshal(f.body, &msg); err != nil {
		t.Fatalf("not valid JSON: %v", err)
	}
	if msg.Version != 1 {
		t.Fatalf("injection changed Version to %d", msg.Version)
	}
}

// TestNotifyResourceNoSocketIsAnError: pushing at an absent player must fail
// loudly. A silent no-op would be indistinguishable from a client that received
// the frame and ignored it — the exact confusion FK-15 was built on.
func TestNotifyResourceNoSocketIsAnError(t *testing.T) {
	svc := New(nil)
	if err := svc.NotifyResource("ghost", "/party/players/ghost", 1, "t"); err == nil {
		t.Fatal("expected an error for a player with no messenger")
	}
}

// TestTargetedResyncDefaultsOff guards the deliberate default: probe #3 proved
// the client REFETCHES on a version bump, not that it APPLIES the result. Until
// an avatar switch is verified end-to-end, MarkDirty must keep dropping.
func TestTargetedResyncFlagIsDeliberate(t *testing.T) {
	// This asserted the flag was OFF until the apply was demonstrated. It was
	// turned ON on 2026-08-13 after a controlled live round-trip proved the
	// client REFETCHES **and APPLIES** on a targeted push, with no socket
	// teardown (docs/fk15-probe3-live-result-20260813.txt: podium
	// blue -> gold -> blue on command, drops 0, connects 1).
	//
	// Kept as a marker so the flag can never change silently: whoever turns it
	// off must record why, because the alternative (S85's socket drop) costs a
	// full reconnect and refetches everything.
	if !enableTargetedResync {
		t.Log("targeted resync is OFF — MarkDirty falls back to the S85 socket drop; " +
			"say why in this test, the apply was proven live on 2026-08-13")
	}
}

// TestNotifyPartyResourcesNeedsVersionSource: with no version provider the
// targeted path must decline, so MarkDirty falls back to the drop rather than
// silently doing nothing.
func TestNotifyPartyResourcesNeedsVersionSource(t *testing.T) {
	svc, _, _ := liveSocket(t, "/notifications/players/p7")
	if svc.notifyPartyResources("p7") {
		t.Fatal("targeted resync claimed success with no version source")
	}
	svc.SetPartyVersionFunc(func() int64 { return 42 })
	if !svc.notifyPartyResources("p7") {
		t.Fatal("targeted resync failed with a version source and a live socket")
	}
}
