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
//   - The shim, on menu load, GETs /revival/missions/progress and, for each
//     FMissionObjectiveProgress it builds, sets Progress = objectives[ObjectiveName]
//     (matched by the GetUniqueObjectiveName key). Missing/zero => a "not started"
//     0/max bar (the Option-1 baseline).
//   - Match-end hooks (or manual testing) POST /revival/missions/progress/add to
//     increment objectives; the store persists to state/interactive.json.
//
// Objective keys are the UNIQUE names from LokiAssetStatics::GetUniqueObjectiveName
// (globally unique per objective, e.g. "PlayAGame", "BR_Knocks_Assists"), so a flat
// map suffices. Single-account revival => everything is stored under one fixed key.

import (
	"encoding/json"
	"io"
	"net/http"
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
