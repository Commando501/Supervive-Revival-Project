// Package interactive implements the menu *actions* the client SENDS once it is
// in the main menu (Milestone 3, Track B). Where package menu answers the client's
// reads with valid-but-empty shapes, this package makes WRITES round-trip: it
// captures what the client POSTs/PUTs (client profile, equipped lobby platform,
// mission progress) and echoes it back on the matching GET so selections "stick".
//
// All routes here previously fell through to capture.StubHandler ({}). Per the
// validity model (see internal/menu): GET /clientprofile already tolerated {}
// (no validity predicate), so echoing a present `data` object is zero-regression
// and the most visible round-trip; GET /progression/players/{id} and
// /mailbox/config/version DID log "Invalid response received" on {}, so those get
// typed wrappers (probes — see the per-handler notes).
package interactive

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
)

// playerState is everything we persist per player id. Fields are stored as raw
// JSON where we want to echo exactly what the client sent (so we never have to
// model a field whose UE type we haven't confirmed), and as typed values where
// we synthesize the shape ourselves.
type playerState struct {
	// ClientProfile is the `data` object from the last
	// POST /personalization/players/{id}/clientprofile, stored verbatim and
	// echoed under {"data": ...} on the matching GET.
	ClientProfile json.RawMessage `json:"clientProfile,omitempty"`
	// LobbyPlatformAssetId is the menu backdrop the player equipped via
	// PUT /personalization/players/{id}/lobbyplatforms.
	LobbyPlatformAssetId string `json:"lobbyPlatformAssetId,omitempty"`
}

// store is an in-memory player-state map with best-effort JSON-file persistence
// so equipped selections survive a relaunch (launch-redirect.ps1 rebuilds +
// restarts the process, clearing memory).
type store struct {
	mu      sync.Mutex
	path    string
	players map[string]*playerState
}

func newStore(path string) *store {
	s := &store{path: path, players: map[string]*playerState{}}
	s.load()
	return s
}

func (s *store) load() {
	b, err := os.ReadFile(s.path)
	if err != nil {
		return // first run / no state yet
	}
	var m map[string]*playerState
	if json.Unmarshal(b, &m) == nil && m != nil {
		s.players = m
	}
}

// saveLocked persists the whole map; callers must hold s.mu. Best-effort: a write
// failure (e.g. read-only working dir) must not break the request.
func (s *store) saveLocked() {
	if s.path == "" {
		return
	}
	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return
	}
	if b, err := json.MarshalIndent(s.players, "", "  "); err == nil {
		tmp := s.path + ".tmp"
		if os.WriteFile(tmp, b, 0o644) == nil {
			os.Rename(tmp, s.path)
		}
	}
}

// get returns a copy-safe handle to the player's state, creating an empty one on
// first access. The returned pointer is only mutated under update().
func (s *store) get(id string) *playerState {
	s.mu.Lock()
	defer s.mu.Unlock()
	st := s.players[id]
	if st == nil {
		st = &playerState{}
		s.players[id] = st
	}
	return st
}

// update mutates a player's state under lock and persists the result.
func (s *store) update(id string, fn func(*playerState)) *playerState {
	s.mu.Lock()
	defer s.mu.Unlock()
	st := s.players[id]
	if st == nil {
		st = &playerState{}
		s.players[id] = st
	}
	fn(st)
	s.saveLocked()
	return st
}
