package interactive

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// coreGamePlayer drives GET /core-game/players/{id} the way the mux does and returns the
// decoded document.
func coreGamePlayer(t *testing.T, s *Service, id string) map[string]any {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /core-game/players/{id}", s.handleCoreGamePlayer)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/core-game/players/"+id, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("decode: %v (body %s)", err, rec.Body.String())
	}
	return got
}

// TestArmQueueOffIsByteIdentical pins the knob's default. This is the invariant that
// makes the whole feature safe to ship: with AGS_ARM_QUEUE unset, /core-game/players is
// exactly what it was before armqueue.go existed.
//
// It also guards the specific regression the widened `active` gate could introduce —
// handleCoreGamePlayer now ORs in st.MatchID, and if anything ever writes MatchID
// without the knob, an idle player would start claiming a match.
func TestArmQueueOffIsByteIdentical(t *testing.T) {
	if forceTutorialMatch {
		t.Skip("forceTutorialMatch is on; this test describes the idle-menu default")
	}
	t.Setenv("AGS_ARM_QUEUE", "")
	s := &Service{store: &store{players: map[string]*playerState{}}}

	// A player who has clicked FIND MATCH and is sitting in the queue.
	s.store.update("p1", func(st *playerState) { st.InQueue = true })
	s.scheduleArm("p1", "bots")

	got := coreGamePlayer(t, s, "p1")
	if got["MatchID"] != "" {
		t.Errorf("MatchID = %q, want \"\" — the knob is OFF and nothing may arm", got["MatchID"])
	}
	if v, _ := got["Version"].(float64); v != 0 {
		t.Errorf("Version = %v, want 0", got["Version"])
	}
	if got["CanDisassociate"] != true {
		t.Errorf("CanDisassociate = %v, want true", got["CanDisassociate"])
	}
}

// TestArmQueueRespectsQueueAllowlist pins that enabling the knob cannot silently arm a
// queue nobody asked for. The default allowlist is `bots` alone, deliberately: `default`
// is BREACH, whose gamemode is a 2,215-cell Skylands battle royale this project has never
// loaded.
func TestArmQueueRespectsQueueAllowlist(t *testing.T) {
	t.Setenv("AGS_ARM_QUEUE", "arm")
	t.Setenv("AGS_ARM_QUEUE_DELAY", "0s")
	s := &Service{store: &store{players: map[string]*playerState{}}}

	s.armQueuedMatchIfAllowed(t, "p1", "default") // not in the default allowlist
	if got := coreGamePlayer(t, s, "p1"); got["MatchID"] != "" {
		t.Errorf("MatchID = %q for queue \"default\", want \"\" — not in AGS_ARM_QUEUE_QUEUES", got["MatchID"])
	}
	s.armQueuedMatchIfAllowed(t, "p2", "bots")
	if got := coreGamePlayer(t, s, "p2"); got["MatchID"] == "" {
		t.Error("MatchID is empty for queue \"bots\", want an armed match")
	}
}

// armQueuedMatchIfAllowed mirrors scheduleArm's gate without the timer, so the tests do
// not sleep.
func (s *Service) armQueuedMatchIfAllowed(t *testing.T, id, queue string) {
	t.Helper()
	if armQueueMode() == armOff || !armQueueAllowed(queue) {
		return
	}
	s.armQueuedMatch(id, queue, armQueueMode())
}

// TestArmQueueEmptyIsASingleVariableControl is the important one.
//
// AGS_ARM_QUEUE=empty must differ from =arm in EXACTLY ONE FIELD: MatchID. Both must
// advance Version and both must push. If `empty` also left Version at 0 it would change
// two things at once and be uninterpretable as a control — which is precisely the
// AGS_PLAYER_RANK=0 mistake S122 recorded ("a revert knob that returns to a catch-all
// changes every field at once").
func TestArmQueueEmptyIsASingleVariableControl(t *testing.T) {
	t.Setenv("AGS_ARM_QUEUE_DELAY", "0s")

	run := func(mode string) map[string]any {
		t.Setenv("AGS_ARM_QUEUE", mode)
		s := &Service{store: &store{players: map[string]*playerState{}}}
		s.armQueuedMatch("p1", "bots", armQueueMode())
		return coreGamePlayer(t, s, "p1")
	}
	armed, control := run("arm"), run("empty")

	if armed["MatchID"] == "" {
		t.Fatal("arm: MatchID is empty, want an armed match")
	}
	if control["MatchID"] != "" {
		t.Errorf("empty: MatchID = %q, want \"\" — the control must not arm", control["MatchID"])
	}

	av, _ := armed["Version"].(float64)
	cv, _ := control["Version"].(float64)
	if av <= 0 || cv <= 0 {
		t.Fatalf("both arms must advance Version; got arm=%v control=%v", armed["Version"], control["Version"])
	}

	// Every OTHER field must match, or the control is not single-variable.
	for k, want := range armed {
		if k == "MatchID" || k == "Version" {
			continue
		}
		if got := control[k]; got != want {
			t.Errorf("control differs from arm on %q: got %v, want %v — the control must move ONE field", k, got, want)
		}
	}
	if len(armed) != len(control) {
		t.Errorf("field count differs: arm=%d control=%d", len(armed), len(control))
	}
}

// TestArmQueueVersionIsStrictlyMonotonic pins the push contract. push.go's refetch gate
// is "pushed version > cached version", so a repeated or decreasing Version is silently
// ignored and the client never refetches — a null that looks exactly like a dead route.
func TestArmQueueVersionIsStrictlyMonotonic(t *testing.T) {
	t.Setenv("AGS_ARM_QUEUE", "arm")
	t.Setenv("AGS_ARM_QUEUE_DELAY", "0s")
	s := &Service{store: &store{players: map[string]*playerState{}}}

	var prev int64
	for i := 0; i < 5; i++ {
		s.armQueuedMatch("p1", "bots", armReal)
		v := s.CoreGamePlayerVersion("p1")
		if v <= prev {
			t.Fatalf("arm %d: version %d is not > previous %d", i, v, prev)
		}
		prev = v
		// A cancel must NOT reset the counter: the next arm's push would then be at or
		// below what the client already cached and would be ignored.
		s.cancelArm("p1")
		if got := s.store.get("p1").MatchVersion; got != v {
			t.Fatalf("cancel reset MatchVersion to %d, want it preserved at %d", got, v)
		}
	}
}

// TestCoreGamePlayerVersionMatchesTheServedDocument pins the contract that exists to
// stop the push and the document drifting apart. Anything calling NotifyResource must
// pass CoreGamePlayerVersion(id), so that value has to equal what the handler serves.
func TestCoreGamePlayerVersionMatchesTheServedDocument(t *testing.T) {
	t.Setenv("AGS_ARM_QUEUE", "arm")
	t.Setenv("AGS_ARM_QUEUE_DELAY", "0s")
	s := &Service{store: &store{players: map[string]*playerState{}}}
	s.armQueuedMatch("p1", "bots", armReal)

	served, _ := coreGamePlayer(t, s, "p1")["Version"].(float64)
	if int64(served) != s.CoreGamePlayerVersion("p1") {
		t.Errorf("served Version %v != CoreGamePlayerVersion %d — the push would use the wrong value",
			served, s.CoreGamePlayerVersion("p1"))
	}
}

// TestCancelArmClearsTheMatch pins the repeatable-loop property. S107's recorded failure
// is that once /core-game/players reports a MatchID it does so forever, so the client
// believes it is already in a match and every later START is a silent no-op.
func TestCancelArmClearsTheMatch(t *testing.T) {
	t.Setenv("AGS_ARM_QUEUE", "arm")
	t.Setenv("AGS_ARM_QUEUE_DELAY", "0s")
	s := &Service{store: &store{players: map[string]*playerState{}}}

	s.armQueuedMatch("p1", "bots", armReal)
	if coreGamePlayer(t, s, "p1")["MatchID"] == "" {
		t.Fatal("precondition: expected an armed match")
	}
	s.cancelArm("p1")
	if got := coreGamePlayer(t, s, "p1")["MatchID"]; got != "" {
		t.Errorf("after cancel MatchID = %q, want \"\"", got)
	}
}

// TestScheduleArmIsIdempotentUnderRetry pins that a joinQueue RETRY replaces the pending
// arm rather than stacking one. The retry is the client's documented rejection symptom
// and we may still see it for unrelated reasons; N retries must not produce N pushes.
func TestScheduleArmIsIdempotentUnderRetry(t *testing.T) {
	t.Setenv("AGS_ARM_QUEUE", "arm")
	t.Setenv("AGS_ARM_QUEUE_DELAY", "50ms")
	s := &Service{store: &store{players: map[string]*playerState{}}}

	pushes := 0
	s.SetResourceNotifier(func(string, string, int64, string) error { pushes++; return nil })

	for i := 0; i < 4; i++ {
		s.scheduleArm("p1", "bots")
	}
	time.Sleep(250 * time.Millisecond)

	if pushes != 1 {
		t.Errorf("pushes = %d after 4 scheduleArm calls, want 1", pushes)
	}
}
