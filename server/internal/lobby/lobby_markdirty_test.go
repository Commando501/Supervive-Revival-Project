package lobby

import (
	"sync"
	"testing"
	"time"
)

// TestMarkDirtyNilSafe: a nil *Service must be a no-op (the interactive package holds a
// nil notifier in tests / when no lobby service is wired).
func TestMarkDirtyNilSafe(t *testing.T) {
	var s *Service
	s.MarkDirty("p1") // must not panic
}

// TestMessengerPlayerID checks the /notifications path parse.
func TestMessengerPlayerID(t *testing.T) {
	cases := map[string]string{
		"/notifications/players/9b9d2c88":       "9b9d2c88",
		"/notifications/players/9b9d2c88/extra": "9b9d2c88",
		"/notifications/players/":               "",
		"/lobby":                                "",
	}
	for in, want := range cases {
		if got := messengerPlayerID(in); got != want {
			t.Fatalf("messengerPlayerID(%q) = %q, want %q", in, got, want)
		}
	}
}

// TestMarkDirtyUnknownPlayer: MarkDirty for an unregistered player is a no-op (no drop,
// no panic) — the debounce map still records the attempt but there is nothing to drop.
func TestMarkDirtyUnknownPlayer(t *testing.T) {
	s := New(nil)
	s.MarkDirty("nobody") // no registered conn -> no-op
}

// TestMarkDirtyDebounceLeadingTrailing verifies the drop semantics WITHOUT a real socket,
// by counting how often the registry lookup for a player would fire a drop. We stand in a
// fake conn via a sentinel and observe the lastDrop clock and dropPending scheduling.
func TestMarkDirtyDebounceLeadingTrailing(t *testing.T) {
	s := New(nil)

	// Register a sentinel so MarkDirty reaches the drop path. We can't easily fake
	// *ws.Conn.Drop(), so instead assert the debounce BOOKKEEPING: the first call stamps
	// lastDrop (leading), rapid follow-ups within the window do NOT re-stamp it immediately
	// but DO schedule a single trailing drop, and after the window the trailing drop stamps
	// lastDrop again.
	id := "p1"

	// Leading edge: first call stamps lastDrop.
	before := s.lastDrop[id]
	s.MarkDirty(id)
	s.mu.Lock()
	led := s.lastDrop[id]
	s.mu.Unlock()
	if !led.After(before) {
		t.Fatal("leading MarkDirty did not stamp lastDrop")
	}

	// Two rapid follow-ups inside the window: lastDrop must NOT advance yet, and exactly
	// one trailing drop must be pending.
	s.MarkDirty(id)
	s.MarkDirty(id)
	s.mu.Lock()
	stampedDuringWindow := s.lastDrop[id]
	pending := s.dropPending[id]
	s.mu.Unlock()
	if !stampedDuringWindow.Equal(led) {
		t.Fatal("lastDrop advanced during the debounce window (leading edge should hold it)")
	}
	if !pending {
		t.Fatal("a trailing drop should be scheduled after in-window changes")
	}

	// After the window, the trailing drop fires: lastDrop advances and pending clears.
	deadline := time.Now().Add(messengerDropDebounce + 500*time.Millisecond)
	for time.Now().Before(deadline) {
		s.mu.Lock()
		p := s.dropPending[id]
		adv := s.lastDrop[id].After(led)
		s.mu.Unlock()
		if !p && adv {
			return // trailing drop fired
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatal("trailing drop never fired")
}

// TestRegisterUnregisterConcurrent is a race-detector smoke test for the registry.
func TestRegisterUnregisterConcurrent(t *testing.T) {
	s := New(nil)
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			s.MarkDirty("p1")
			s.unregisterMessenger("p1", nil)
		}()
	}
	wg.Wait()
}
