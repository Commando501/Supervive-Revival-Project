package interactive

// Missions — Option 2 (real progress tracking).
//
// The client never fetches mission progress over HTTP (the 13.5GB capture has zero
// /mission-progress reads; the modal's data is built entirely client-side from the
// mission DAs — see docs/session-52..59). So this is NOT an impersonated client
// route: it's a revival-only surface that the client-side missions shim
// (tools/sigbypass-mod/missions_nativecall_probe1x) calls in-process to fetch the
// per-objective progress it should write into the mission model.
//
// Flow:
//   - On menu load the shim POSTs /revival/missions/manifest (the full mission->objective list) and, for
//     each FMissionObjectiveProgress it builds, GETs /revival/missions/progress and sets Progress =
//     objectives["<missionInternalName>/<objectiveName>"]. Missing/zero => a "not started" 0/max bar.
//   - Match results POST /revival/missions/match-result; the engine maps stats to objective-name deltas
//     and FANS them out to each mission's composite key (via the manifest), so missions that share an
//     objective name track independently. The store persists to state/interactive.json.
//
// Progress keys are PER-MISSION composites "<missionInternalName>/<objectiveUniqueName>" (per-mission
// granularity). Single-account revival => everything is stored under one fixed key.

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"
)

// missionsLocalKey is the fixed player key mission progress is stored under. The
// revival is single-account and the in-process shim that reads this carries no JWT,
// so a global doc is correct; a multi-account variant would key by the JWT `sub`.
const missionsLocalKey = "local"

// registerMissions wires the revival-only mission-progress endpoints. Namespaced
// under /revival/ so they never collide with an impersonated client route (patterns
// are more specific than cmd/ags's "/" catch-all, so they take precedence).
func (s *Service) registerMissions(mux *http.ServeMux) {
	mux.HandleFunc("GET /revival/missions/progress", s.handleGetMissionProgress)
	mux.HandleFunc("POST /revival/missions/progress", s.handleSetMissionProgress)
	mux.HandleFunc("POST /revival/missions/progress/add", s.handleAddMissionProgress)
	// The shim registers the mission->objective structure on menu load so match results can
	// fan out to per-mission composite keys (per-mission granularity).
	mux.HandleFunc("POST /revival/missions/manifest", s.handleSetManifest)
	// Option 2c: record a match result -> map its stats to per-objective increments.
	mux.HandleFunc("POST /revival/missions/match-result", s.handleMatchResult)
}

// ManifestEntry is one (mission, objective, max) triple the shim knows from the mission DAs. The
// composite progress key is compositeKey(Mission, Objective) = "<mission>/<objective>".
type ManifestEntry struct {
	Mission   string  `json:"mission"`
	Objective string  `json:"objective"`
	Max       float64 `json:"max"`
}

// compositeKey is the per-mission progress key: "<missionInternalName>/<objectiveUniqueName>".
func compositeKey(mission, objective string) string { return mission + "/" + objective }

// handleSetManifest replaces the stored mission->objective manifest (the shim POSTs the full list on
// menu load). Echoes the count.
func (s *Service) handleSetManifest(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Entries []ManifestEntry `json:"entries"`
	}
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<22))
	_ = json.Unmarshal(raw, &body)
	s.store.update(missionsLocalKey, func(st *playerState) { st.MissionManifest = body.Entries })
	writeJSON(w, map[string]any{"entries": len(body.Entries)})
}

// missionProgressBody is the shared request/response payload: a map of objective
// unique-name -> progress value.
type missionProgressBody struct {
	Objectives map[string]float64 `json:"objectives"`
}

func (s *Service) missionObjectives() map[string]float64 {
	obj := s.store.get(missionsLocalKey).MissionObjectives
	if obj == nil {
		obj = map[string]float64{}
	}
	return obj
}

// handleGetMissionProgress returns the stored per-objective progress the shim applies.
func (s *Service) handleGetMissionProgress(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"objectives": s.missionObjectives()})
}

// handleSetMissionProgress merge-SETS each posted objective to an absolute value
// (keys absent from the body are left untouched). Used to seed/edit progress and as
// the shape a match-end reconcile can post as absolute totals. Echoes the full map.
func (s *Service) handleSetMissionProgress(w http.ResponseWriter, r *http.Request) {
	var body missionProgressBody
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	_ = json.Unmarshal(raw, &body)
	s.store.update(missionsLocalKey, func(st *playerState) {
		if st.MissionObjectives == nil {
			st.MissionObjectives = map[string]float64{}
		}
		for k, v := range body.Objectives {
			st.MissionObjectives[k] = v
		}
	})
	s.handleGetMissionProgress(w, r)
}

// handleAddMissionProgress INCREMENTS each posted objective by the given delta (the
// natural match-end-results hook; missing keys start at 0). Echoes the full map.
func (s *Service) handleAddMissionProgress(w http.ResponseWriter, r *http.Request) {
	var body missionProgressBody
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	_ = json.Unmarshal(raw, &body)
	s.store.update(missionsLocalKey, func(st *playerState) {
		if st.MissionObjectives == nil {
			st.MissionObjectives = map[string]float64{}
		}
		for k, v := range body.Objectives {
			st.MissionObjectives[k] += v
		}
	})
	s.handleGetMissionProgress(w, r)
}

// ---- Option 2c: match result -> objective increments --------------------------------------------
//
// A match's stats advance many objectives at once. In the LIVE game the dedicated server reports
// results to the backend (the client never POSTs them — every match endpoint the client hits is a
// GET), and matches are gated in the revival, so this endpoint is driven by a simulated/manual
// match-result POST for now; wire it to real match data if/when matches launch. The mapping below
// is keyed by the objective's UNIQUE name (LokiAssetStatics::GetUniqueObjectiveName), read live from
// the mission DAs (docs/session-59). Extend objectiveRules as more objective semantics are confirmed.
//
// Example (one tournament win with 8 knocks, 2 assists, top-1):
//   curl -X POST http://127.0.0.1:8080/revival/missions/match-result \
//     -d '{"win":true,"placement":1,"knocks":8,"assists":2,"gameMode":"tournament"}'

// matchResult is a per-match stat summary. All fields optional; unknown JSON keys are ignored.
type matchResult struct {
	Win              bool    `json:"win"`
	Placement        int     `json:"placement"` // 1 = 1st; 0/absent = unknown
	Knocks           float64 `json:"knocks"`
	Assists          float64 `json:"assists"`
	TeamWipes        float64 `json:"teamWipes"`
	MinionKills      float64 `json:"minionKills"`
	BossKills        float64 `json:"bossKills"` // meteor beasts / abyssal / baron / corrupted guardians
	ChestsOpened     float64 `json:"chestsOpened"`
	VaultsOpened     float64 `json:"vaultsOpened"`
	BonfiresCaptured float64 `json:"bonfiresCaptured"` // "base camps"
	Sunrises         float64 `json:"sunrises"`
	Purchases        float64 `json:"purchases"` // relics/grip/perks/equipment bought in-game
	UniqueHeroes     float64 `json:"uniqueHeroes"`
	GameMode         string  `json:"gameMode"` // "tournament" | "trios" | "coop" | "br" | ...
	// Objectives are explicit per-objective deltas applied ON TOP of the mapped ones, so callers can
	// advance objectives the table doesn't cover yet without editing the server.
	Objectives map[string]float64 `json:"objectives"`
}

func b2f(b bool) float64 { if b { return 1 }; return 0 }
func containsFold(s, sub string) bool { return strings.Contains(strings.ToLower(s), strings.ToLower(sub)) }

// objectiveRules maps a match result to a delta for a given objective unique-name. Names verified
// live from the mission DAs (Tournament / Dailies / Weeklies / Onboarding). "PlayAGame" is shared by
// the Tournament and Daily "play a game" missions, so a single +1 advances both (see the collision
// note in store.go / session-59).
var objectiveRules = []struct {
	Name  string
	Delta func(m matchResult) float64
}{
	// Any completed match.
	{"PlayAGame", func(m matchResult) float64 { return 1 }},
	// SEASONAL / Tournament.
	{"a2winarenagames", func(m matchResult) float64 { return b2f(m.Win) }},
	{"BR_3Top4", func(m matchResult) float64 { return b2f(m.Placement >= 1 && m.Placement <= 3) }},
	{"BR_Knocks_Assists", func(m matchResult) float64 { return m.Knocks + m.Assists }},
	// Dailies.
	{"BR_Knocks", func(m matchResult) float64 { return m.Knocks }},
	{"BR_Sunrises", func(m matchResult) float64 { return m.Sunrises }},
	{"ArmoryOnboarding_PurchaseEquipment", func(m matchResult) float64 { return m.Purchases }},
	// Weeklies.
	{"BR_WinABR", func(m matchResult) float64 { return b2f(m.Win) }},
	{"BR_KillBosses", func(m matchResult) float64 { return m.BossKills }},
	{"BR_Boxes", func(m matchResult) float64 { return m.ChestsOpened }},
	{"BR_Vaults", func(m matchResult) float64 { return m.VaultsOpened }},
	{"BR_Capture Bonfires", func(m matchResult) float64 { return m.BonfiresCaptured }},
	{"BR_Minions", func(m matchResult) float64 { return m.MinionKills }},
	{"BR_WipeTeams", func(m matchResult) float64 { return m.TeamWipes }},
	{"Armory_PlayUniqueHunters", func(m matchResult) float64 { return m.UniqueHeroes }},
	{"TopXWithFullArmory", func(m matchResult) float64 { return b2f(m.Placement >= 1 && m.Placement <= 6) }},
	// Onboarding (trios / coop-vs-AI).
	{"Onboarding_PlayTriosMatch", func(m matchResult) float64 { return b2f(containsFold(m.GameMode, "trios") || containsFold(m.GameMode, "coop")) }},
}

// mappedNameDeltas turns a match result into per-objective-NAME increments via objectiveRules. Zero
// deltas are dropped so an unrelated objective is never touched. These names are then fanned out to
// per-mission composite keys via the manifest.
func mappedNameDeltas(m matchResult) map[string]float64 {
	d := map[string]float64{}
	for _, r := range objectiveRules {
		if v := r.Delta(m); v != 0 {
			d[r.Name] += v
		}
	}
	return d
}

// handleMatchResult records a match via applyMatchResult. Echoes
// {"applied": <composite deltas>, "objectives": <full updated map>}.
func (s *Service) handleMatchResult(w http.ResponseWriter, r *http.Request) {
	var m matchResult
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	_ = json.Unmarshal(raw, &m)
	applied := s.applyMatchResult(m)
	writeJSON(w, map[string]any{"applied": applied, "objectives": s.missionObjectives()})
}

// applyMatchResult maps a match's stats to per-objective-name deltas, FANS them out to every
// mission that has the objective (via the registered manifest) so each mission's composite key
// advances independently, then applies the explicit per-composite `objectives` passthrough on
// top. Shared by the game-facing POST handler and the admin panel's match simulator
// (ApplyMatchResultJSON). Returns the composite deltas that were applied.
func (s *Service) applyMatchResult(m matchResult) map[string]float64 {
	nameDeltas := mappedNameDeltas(m)
	st0 := s.store.get(missionsLocalKey)

	// Fan each objective-name delta out to per-mission composite keys.
	applied := map[string]float64{}
	for _, e := range st0.MissionManifest {
		if d, ok := nameDeltas[e.Objective]; ok && d != 0 {
			applied[compositeKey(e.Mission, e.Objective)] += d
		}
	}
	// If no manifest was registered yet, fall back to the bare objective names so a match still records.
	if len(st0.MissionManifest) == 0 {
		for k, v := range nameDeltas {
			applied[k] += v
		}
	}
	// Explicit passthrough deltas are treated as composite keys and applied verbatim.
	for k, v := range m.Objectives {
		if v != 0 {
			applied[k] += v
		}
	}

	s.store.update(missionsLocalKey, func(st *playerState) {
		if st.MissionObjectives == nil {
			st.MissionObjectives = map[string]float64{}
		}
		for k, v := range applied {
			st.MissionObjectives[k] += v
		}
	})
	return applied
}
