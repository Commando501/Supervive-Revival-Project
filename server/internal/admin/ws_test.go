package admin

import (
	"bufio"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"supervive-revival/server/internal/lobby"
)

// End-to-end coverage for the FK-15 push console: an HTTP request to the
// loopback admin API must put exactly the intended bytes on a live client
// socket. Chain under test: admin route -> lobby.Push -> ws.WriteFrame -> wire.
//
// This exists because the console's entire value is that a null result can be
// trusted. If a push could silently not reach the wire, the console would
// manufacture false negatives faster than the old one-probe-per-launch harness
// did -- delivery and effect are different failures and must stay separable
// (the lesson FK-11 records).

// wsClient dials a real WebSocket against h and returns a reader on the frames.
func wsClient(t *testing.T, srvURL, path string) *bufio.Reader {
	t.Helper()
	host := strings.TrimPrefix(srvURL, "http://")
	c, err := net.Dial("tcp", host)
	if err != nil {
		t.Fatalf("dial: %v", err)
	}
	t.Cleanup(func() { c.Close() })

	var k [16]byte
	rand.Read(k[:])
	req := "GET " + path + " HTTP/1.1\r\nHost: " + host + "\r\nUpgrade: websocket\r\n" +
		"Connection: Upgrade\r\nSec-WebSocket-Key: " + base64.StdEncoding.EncodeToString(k[:]) +
		"\r\nSec-WebSocket-Version: 13\r\n\r\n"
	if _, err := c.Write([]byte(req)); err != nil {
		t.Fatalf("handshake write: %v", err)
	}
	br := bufio.NewReader(c)
	resp, err := http.ReadResponse(br, nil)
	if err != nil {
		t.Fatalf("handshake read: %v", err)
	}
	if resp.StatusCode != http.StatusSwitchingProtocols {
		t.Fatalf("status %d, want 101", resp.StatusCode)
	}
	return br
}

// readFrameBody decodes one unmasked server frame's payload.
func readFrameBody(t *testing.T, br *bufio.Reader) string {
	t.Helper()
	var h [2]byte
	if _, err := io.ReadFull(br, h[:]); err != nil {
		t.Fatalf("frame header: %v", err)
	}
	n := int(h[1] & 0x7f)
	if n == 126 {
		var e [2]byte
		io.ReadFull(br, e[:])
		n = int(e[0])<<8 | int(e[1])
	}
	body := make([]byte, n)
	if _, err := io.ReadFull(br, body); err != nil {
		t.Fatalf("frame body: %v", err)
	}
	return string(body)
}

func adminHarness(t *testing.T) (*httptest.Server, *httptest.Server) {
	t.Helper()
	lob := lobby.New(nil)

	game := httptest.NewServer(http.HandlerFunc(lob.Handle))
	t.Cleanup(game.Close)

	mux := http.NewServeMux()
	New(nil, lob).Register(mux)
	adm := httptest.NewServer(mux)
	t.Cleanup(adm.Close)

	return game, adm
}

func post(t *testing.T, url, body string) (int, map[string]any) {
	t.Helper()
	resp, err := http.Post(url, "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	var out map[string]any
	json.NewDecoder(resp.Body).Decode(&out)
	return resp.StatusCode, out
}

// TestAdminPushReachesTheWire is the whole point: the exact composed frame,
// and nothing else, arrives at the client.
func TestAdminPushReachesTheWire(t *testing.T) {
	game, adm := adminHarness(t)
	br := wsClient(t, game.URL, "/lobby")

	// Let registration settle.
	var handle string
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		resp, err := http.Get(adm.URL + "/api/ws/sockets")
		if err == nil {
			var out struct {
				Sockets []lobby.SocketInfo `json:"sockets"`
			}
			json.NewDecoder(resp.Body).Decode(&out)
			resp.Body.Close()
			if len(out.Sockets) == 1 {
				handle = out.Sockets[0].Handle
				if out.Sockets[0].Kind != "lobby" {
					t.Fatalf("kind = %q, want lobby", out.Sockets[0].Kind)
				}
				break
			}
		}
		time.Sleep(5 * time.Millisecond)
	}
	if handle == "" {
		t.Fatal("socket never appeared in /api/ws/sockets")
	}

	code, _ := post(t, adm.URL+"/api/ws/push", `{
		"socket": "`+handle+`",
		"label": "e2e",
		"type": "partyInviteNotif",
		"fields": [{"key":"partyId","value":"p-1"}]
	}`)
	if code != http.StatusOK {
		t.Fatalf("push status %d", code)
	}

	got := readFrameBody(t, br)
	want := "type: partyInviteNotif\npartyId: p-1"
	if got != want {
		t.Fatalf("wire payload %q, want %q", got, want)
	}
}

// TestAdminPushRejectsUnknownFields: a typo in a hand-written curl body must
// fail loudly. Silently ignoring it would push a frame that is missing the
// field the operator believes they are testing -- and the resulting null would
// be scored against the wrong hypothesis.
func TestAdminPushRejectsUnknownFields(t *testing.T) {
	_, adm := adminHarness(t)
	code, out := post(t, adm.URL+"/api/ws/push", `{"socket":"ws1","label":"x","typ":"oops"}`)
	if code != http.StatusBadRequest {
		t.Fatalf("status %d, want 400", code)
	}
	if !strings.Contains(out["error"].(string), "typ") {
		t.Errorf("error should name the offending field, got %v", out["error"])
	}
}

// TestAdminPreviewNeedsNoGame: composing and inspecting a frame must work with
// nothing running, so a sitting is never spent discovering a syntax error.
func TestAdminPreviewNeedsNoGame(t *testing.T) {
	_, adm := adminHarness(t)
	code, out := post(t, adm.URL+"/api/ws/preview", `{
		"label":"dry","type":"t","id":"i","fields":[{"key":"a","value":"1"}]}`)
	if code != http.StatusOK {
		t.Fatalf("status %d", code)
	}
	if out["payload"] != "type: t\nid: i\na: 1" {
		t.Fatalf("preview payload = %v", out["payload"])
	}
	if int(out["bytes"].(float64)) != len("type: t\nid: i\na: 1") {
		t.Fatalf("byte count wrong: %v", out["bytes"])
	}
}

// TestAdminPushWithNoSocketFails: pushing into the void must be an error, not
// a cheerful 200. A false "sent" is how a probe gets scored against a frame
// that never left the building.
func TestAdminPushWithNoSocketFails(t *testing.T) {
	_, adm := adminHarness(t)
	code, _ := post(t, adm.URL+"/api/ws/push", `{"socket":"ws99","label":"x","raw":"hi"}`)
	if code != http.StatusBadRequest {
		t.Fatalf("status %d, want 400", code)
	}
}

// TestPanelLive is not a test — it is an opt-in dev harness that serves the
// REAL admin panel (embedded HTML + real handlers) against a real lobby service
// with two fake live sockets, so the push-console UI can be exercised in a
// browser without touching the running game or ags.
//
//	PANEL_LIVE=1 go test ./internal/admin -run TestPanelLive -v -timeout 0
//	  -> http://127.0.0.1:9299/
//
// It must serve the real backend rather than a stub: a stubbed API silently
// accepted a request body whose field shape the real handler rejects (the UI
// sent {k,v} where the API takes {key,value}), and a lenient stub would have
// certified a console that 400s on every composed frame. A verification
// instrument that is more permissive than the thing it verifies is worthless.
func TestPanelLive(t *testing.T) {
	if os.Getenv("PANEL_LIVE") == "" {
		t.Skip("set PANEL_LIVE=1 to serve the panel for manual UI checks")
	}
	lob := lobby.New(nil)

	gameMux := http.NewServeMux()
	gameMux.HandleFunc("/", lob.Handle)
	gameLn, err := net.Listen("tcp", "127.0.0.1:9298")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	go http.Serve(gameLn, gameMux)

	for _, p := range []string{"/lobby", "/notifications/players/9b9d2c88"} {
		wsClient(t, "http://127.0.0.1:9298", p)
	}

	mux := http.NewServeMux()
	New(nil, lob).Register(mux)
	t.Log("panel serving on http://127.0.0.1:9299/ — Ctrl-C to stop")
	if err := http.ListenAndServe("127.0.0.1:9299", mux); err != nil {
		t.Fatalf("serve: %v", err)
	}
}

// TestAdminSocketsEmptyWithNilLobby: the panel must degrade, not panic, when no
// lobby service is wired.
func TestAdminSocketsEmptyWithNilLobby(t *testing.T) {
	mux := http.NewServeMux()
	New(nil, nil).Register(mux)
	srv := httptest.NewServer(mux)
	defer srv.Close()

	resp, err := http.Get(srv.URL + "/api/ws/sockets")
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d", resp.StatusCode)
	}
}
