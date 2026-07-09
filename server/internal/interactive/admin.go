package interactive

// Admin accessors (2026-07-08) — the exported surface internal/admin drives.
// These bypass HTTP and operate on the same store the game-facing handlers use,
// so an admin edit is visible to the client on its next poll/fetch (party polls
// ~1s; loadout re-applies when LoadoutVersion advances; mission progress is read
// by the client shim on menu load + its change poll).

import (
	"bytes"
	"encoding/json"
	"fmt"
	"sort"
)

// PlayerIDs lists every persisted player id, sorted, EXCLUDING the "local"
// missions bucket (missions are exposed via the Missions* accessors instead).
func (s *Service) PlayerIDs() []string {
	s.store.mu.Lock()
	defer s.store.mu.Unlock()
	ids := make([]string, 0, len(s.store.players))
	for id := range s.store.players {
		if id != missionsLocalKey {
			ids = append(ids, id)
		}
	}
	sort.Strings(ids)
	return ids
}

// PlayerStateJSON returns the persisted state doc for one player (the same shape
// stored in state/interactive.json). ok=false when the id has no state yet.
func (s *Service) PlayerStateJSON(id string) ([]byte, bool) {
	s.store.mu.Lock()
	st := s.store.players[id]
	s.store.mu.Unlock()
	if st == nil {
		return nil, false
	}
	b, err := json.Marshal(st)
	if err != nil {
		return nil, false
	}
	return b, true
}

// SetPlayerStateJSON replaces a player's state with the posted doc (the admin
// GUI round-trips PlayerStateJSON output). Unknown fields are rejected so a
// typo'd key fails loudly instead of silently dropping an edit. LoadoutVersion
// is force-advanced past the previous value: the client's ULoadoutReconciler
// ignores any loadout doc whose version didn't move (see store.go), so without
// the bump an admin equip edit would look like a no-op in-game.
func (s *Service) SetPlayerStateJSON(id string, raw []byte) error {
	if id == "" {
		return fmt.Errorf("empty player id")
	}
	var st playerState
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&st); err != nil {
		return fmt.Errorf("player state parse: %w", err)
	}
	s.store.update(id, func(cur *playerState) {
		if st.LoadoutVersion <= cur.LoadoutVersion {
			st.LoadoutVersion = cur.LoadoutVersion + 1
		}
		*cur = st
	})
	return nil
}

// DeletePlayer removes a player's persisted state entirely (account reset — the
// next client login starts from the built-in defaults).
func (s *Service) DeletePlayer(id string) {
	s.store.mu.Lock()
	defer s.store.mu.Unlock()
	delete(s.store.players, id)
	s.store.saveLocked()
}

// MissionManifest returns the mission->objective structure the client shim
// registered on the last menu load (empty until the shim has run once).
func (s *Service) MissionManifest() []ManifestEntry {
	return append([]ManifestEntry(nil), s.store.get(missionsLocalKey).MissionManifest...)
}

// MissionObjectives returns a copy of the per-objective progress map (composite
// "<mission>/<objective>" keys).
func (s *Service) MissionObjectives() map[string]float64 {
	s.store.mu.Lock()
	defer s.store.mu.Unlock()
	st := s.store.players[missionsLocalKey]
	out := map[string]float64{}
	if st != nil {
		for k, v := range st.MissionObjectives {
			out[k] = v
		}
	}
	return out
}

// SetMissionObjectives merge-sets absolute progress values; replace=true wipes
// the map first (full reset when the posted map is empty). Returns the updated map.
func (s *Service) SetMissionObjectives(vals map[string]float64, replace bool) map[string]float64 {
	s.store.update(missionsLocalKey, func(st *playerState) {
		if replace || st.MissionObjectives == nil {
			st.MissionObjectives = map[string]float64{}
		}
		for k, v := range vals {
			st.MissionObjectives[k] = v
		}
	})
	return s.MissionObjectives()
}

// ApplyMatchResultJSON runs the match-result -> objective-increment engine on a
// raw matchResult doc (the same body POST /revival/missions/match-result takes).
func (s *Service) ApplyMatchResultJSON(raw []byte) (applied, objectives map[string]float64, err error) {
	var m matchResult
	if e := json.Unmarshal(raw, &m); e != nil {
		return nil, nil, fmt.Errorf("match result parse: %w", e)
	}
	applied = s.applyMatchResult(m)
	return applied, s.MissionObjectives(), nil
}
