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
	"sort"
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
	mux.HandleFunc("GET /revival/missions/manifest", s.handleGetManifest)
	// Server-computed completion/XP from the manifest maxes + stored progress (ags is authoritative
	// for what's "done", not just raw progress) and daily/weekly rotation (reset a pool's composites).
	mux.HandleFunc("GET /revival/missions/status", s.handleGetMissionStatus)
	mux.HandleFunc("POST /revival/missions/rotate", s.handleRotateMissions)
	// Which registered missions will actually advance from a match result (objectiveRules coverage).
	mux.HandleFunc("GET /revival/missions/coverage", s.handleGetMissionCoverage)
	// Option 2c: record a match result -> map its stats to per-objective increments.
	mux.HandleFunc("POST /revival/missions/match-result", s.handleMatchResult)
}

// ManifestEntry is one (mission, objective, max) triple the shim knows from the mission DAs. The
// composite progress key is compositeKey(Mission, Objective) = "<mission>/<objective>".
//
// Pool and XP are OPTIONAL enrichment (omitempty; a shim that doesn't send them still parses — UE's
// and Go's unmarshalers both ignore absent keys). When present they let ags compute completion,
// XP-earned, and daily/weekly rotation server-side (see missionStatuses / handleRotateMissions),
// moving those decisions off the client. Pool = the mission's pool id (e.g. "Dailies","Weeklies",
// "Seasonal","HunterMissions"); XP = the mission's total XP reward (MissionModel.XPReward@+0x60).
type ManifestEntry struct {
	Mission   string  `json:"mission"`
	Objective string  `json:"objective"`
	Max       float64 `json:"max"`
	Pool      string  `json:"pool,omitempty"`
	XP        float64 `json:"xp,omitempty"`
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

// handleGetManifest returns the stored mission->objective manifest (the structure the shim last
// registered). The manifest used to be write-only; exposing it lets the admin panel, tests, and a
// future thinner shim READ the structure the server knows instead of re-deriving it from the DAs.
func (s *Service) handleGetManifest(w http.ResponseWriter, r *http.Request) {
	entries := s.store.get(missionsLocalKey).MissionManifest
	if entries == nil {
		entries = []ManifestEntry{}
	}
	writeJSON(w, map[string]any{"entries": entries})
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

// ---- Server-computed completion / XP -------------------------------------------------------------
//
// The client render derives a bar's fill from CurrentProgress/TotalProgress and implicitly flips a
// mission "done" at progress==max, but ags never knew completion — only raw per-objective progress.
// missionStatuses moves that decision server-side: from the registered manifest (objective maxes) +
// the stored composite progress it computes, per mission, which objectives are done and whether the
// whole mission is complete. That's the authoritative basis for XP-earned, reward-claim, and rotation.

// ObjectiveStatus is one objective's computed progress vs its manifest max.
type ObjectiveStatus struct {
	Objective string  `json:"objective"`
	Progress  float64 `json:"progress"`
	Max       float64 `json:"max"`
	Done      bool    `json:"done"`
}

// MissionStatus is one mission's server-computed completion state.
type MissionStatus struct {
	Mission    string            `json:"mission"`
	Pool       string            `json:"pool,omitempty"`
	XP         float64           `json:"xp,omitempty"`
	Complete   bool              `json:"complete"`
	Objectives []ObjectiveStatus `json:"objectives"`
}

// missionStatuses groups the manifest by mission and computes completion from stored progress. A
// mission is complete when every one of its objectives has progress >= a positive max (an objective
// with an unknown/zero max can't complete, so neither can its mission). Order follows first-seen
// manifest order for stable output. Missions with no manifest entry are unknown and omitted.
func (s *Service) missionStatuses() []MissionStatus {
	st := s.store.get(missionsLocalKey)
	prog := st.MissionObjectives
	order := []string{}
	byMission := map[string]*MissionStatus{}
	for _, e := range st.MissionManifest {
		ms := byMission[e.Mission]
		if ms == nil {
			ms = &MissionStatus{Mission: e.Mission, Pool: e.Pool, XP: e.XP, Complete: true}
			byMission[e.Mission] = ms
			order = append(order, e.Mission)
		}
		if ms.Pool == "" {
			ms.Pool = e.Pool
		}
		if ms.XP == 0 {
			ms.XP = e.XP
		}
		p := prog[compositeKey(e.Mission, e.Objective)]
		done := e.Max > 0 && p >= e.Max
		if !done {
			ms.Complete = false
		}
		ms.Objectives = append(ms.Objectives, ObjectiveStatus{Objective: e.Objective, Progress: p, Max: e.Max, Done: done})
	}
	out := make([]MissionStatus, 0, len(order))
	for _, m := range order {
		out = append(out, *byMission[m])
	}
	return out
}

// StatusSummary rolls up completion across all registered missions. XP earned sums only completed
// missions and is only meaningful once the manifest carries per-mission XP.
type StatusSummary struct {
	Total    int     `json:"total"`
	Complete int     `json:"complete"`
	XPEarned float64 `json:"xpEarned"`
}

// StatusReport is per-mission completion plus the summary — the single shape served by BOTH the
// /revival status endpoint and the admin panel (so a consumer never has to special-case which one).
type StatusReport struct {
	Missions []MissionStatus `json:"missions"`
	Summary  StatusSummary   `json:"summary"`
}

// missionStatusReport computes per-mission completion + the roll-up summary.
func (s *Service) missionStatusReport() StatusReport {
	ms := s.missionStatuses()
	sum := StatusSummary{Total: len(ms)}
	for _, m := range ms {
		if m.Complete {
			sum.Complete++
			sum.XPEarned += m.XP
		}
	}
	return StatusReport{Missions: ms, Summary: sum}
}

// MissionStatusReport is the exported accessor (admin panel / other packages).
func (s *Service) MissionStatusReport() StatusReport { return s.missionStatusReport() }

// handleGetMissionStatus returns per-mission completion plus a summary.
func (s *Service) handleGetMissionStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, s.missionStatusReport())
}

// ---- Daily / weekly rotation ---------------------------------------------------------------------

// handleRotateMissions clears the stored progress for a pool's missions (and/or an explicit mission
// list) — the daily/weekly reset the accumulate-forever store otherwise lacks. Scope is chosen from
// the registered manifest: any entry whose Pool matches body.pool, or whose Mission is in body.missions.
// Returns the composite keys that were cleared. (Real rotation cadence/expiry can drive this on a
// timer or from the client's own daily-reset signal; this is the mechanism.)
func (s *Service) handleRotateMissions(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Pool     string   `json:"pool"`
		Missions []string `json:"missions"`
	}
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	_ = json.Unmarshal(raw, &body)
	target := map[string]bool{}
	for _, m := range body.Missions {
		target[m] = true
	}
	cleared := []string{}
	s.store.update(missionsLocalKey, func(st *playerState) {
		if st.MissionObjectives == nil {
			return
		}
		inScope := map[string]bool{}
		for _, e := range st.MissionManifest {
			if (body.Pool != "" && e.Pool == body.Pool) || target[e.Mission] {
				inScope[e.Mission] = true
			}
		}
		for _, e := range st.MissionManifest {
			if !inScope[e.Mission] {
				continue
			}
			k := compositeKey(e.Mission, e.Objective)
			if _, ok := st.MissionObjectives[k]; ok {
				delete(st.MissionObjectives, k)
				cleared = append(cleared, k)
			}
		}
	})
	writeJSON(w, map[string]any{"cleared": cleared, "pool": body.Pool})
}

// ---- Match-result coverage -----------------------------------------------------------------------
//
// A registered mission only advances from a generic match result if one of its objectives' unique-names
// has a matching rule in objectiveRules (an explicit per-composite passthrough can still advance anything,
// but that's caller-supplied). objectiveRules maps ~18 names; the manifest can carry 91 distinct objective
// names across 330 missions (the 309 hero missions are unmapped), so most missions won't move from a plain
// match. This report makes the gaps explicit — per-mission coverage plus, crucially, the two lists you act
// on: objectives with NO rule (add a rule), and rules matching NO manifest objective (usually a name typo,
// e.g. a stray space, or missions not registered yet).

// mappedObjectiveNames is the set of objective unique-names objectiveRules can advance.
func mappedObjectiveNames() map[string]bool {
	m := make(map[string]bool, len(objectiveRules))
	for _, r := range objectiveRules {
		m[r.Name] = true
	}
	return m
}

// ObjectiveCoverage is one objective and whether a rule can advance it.
type ObjectiveCoverage struct {
	Objective string `json:"objective"`
	Mapped    bool   `json:"mapped"`
}

// MissionCoverage is one mission's match-result trackability: "full" (all objectives mapped), "partial"
// (some), or "none" (won't advance from a generic match).
type MissionCoverage struct {
	Mission    string              `json:"mission"`
	Pool       string              `json:"pool,omitempty"`
	Coverage   string              `json:"coverage"`
	Objectives []ObjectiveCoverage `json:"objectives"`
}

// CoverageSummary is the roll-up over all registered missions.
type CoverageSummary struct {
	MissionsTotal          int `json:"missionsTotal"`
	MissionsFullyTrackable int `json:"missionsFullyTrackable"`
	MissionsPartial        int `json:"missionsPartial"`
	MissionsUntrackable    int `json:"missionsUntrackable"`
	ObjectivesTotal        int `json:"objectivesTotal"`
	ObjectivesMapped       int `json:"objectivesMapped"`
	ObjectivesUnmapped     int `json:"objectivesUnmapped"`
	RulesTotal             int `json:"rulesTotal"`
	RulesUnused            int `json:"rulesUnused"`
}

// CoverageReport is the full coverage response.
type CoverageReport struct {
	Summary            CoverageSummary   `json:"summary"`
	UnmappedObjectives []string          `json:"unmappedObjectives"`
	UnusedRules        []string          `json:"unusedRules"`
	Missions           []MissionCoverage `json:"missions"`
}

// missionCoverage cross-references the registered manifest against objectiveRules. Missions keep
// first-seen order; the two gap lists are sorted for stable output.
func (s *Service) missionCoverage() CoverageReport {
	mapped := mappedObjectiveNames()
	st := s.store.get(missionsLocalKey)

	order := []string{}
	byMission := map[string]*MissionCoverage{}
	distinctObj := map[string]bool{} // objective name -> is it mapped
	usedRule := map[string]bool{}    // rule name -> matched at least one manifest objective
	for _, e := range st.MissionManifest {
		mc := byMission[e.Mission]
		if mc == nil {
			mc = &MissionCoverage{Mission: e.Mission, Pool: e.Pool}
			byMission[e.Mission] = mc
			order = append(order, e.Mission)
		}
		if mc.Pool == "" {
			mc.Pool = e.Pool
		}
		isMapped := mapped[e.Objective]
		mc.Objectives = append(mc.Objectives, ObjectiveCoverage{Objective: e.Objective, Mapped: isMapped})
		distinctObj[e.Objective] = isMapped
		if isMapped {
			usedRule[e.Objective] = true
		}
	}

	missions := make([]MissionCoverage, 0, len(order))
	sum := CoverageSummary{RulesTotal: len(mapped)}
	for _, m := range order {
		mc := byMission[m]
		mappedCount := 0
		for _, o := range mc.Objectives {
			if o.Mapped {
				mappedCount++
			}
		}
		switch {
		case mappedCount == 0:
			mc.Coverage = "none"
			sum.MissionsUntrackable++
		case mappedCount == len(mc.Objectives):
			mc.Coverage = "full"
			sum.MissionsFullyTrackable++
		default:
			mc.Coverage = "partial"
			sum.MissionsPartial++
		}
		missions = append(missions, *mc)
	}
	sum.MissionsTotal = len(missions)

	unmapped := []string{}
	for o, isMapped := range distinctObj {
		if isMapped {
			sum.ObjectivesMapped++
		} else {
			unmapped = append(unmapped, o)
		}
	}
	sum.ObjectivesTotal = len(distinctObj)
	sum.ObjectivesUnmapped = len(unmapped)
	sort.Strings(unmapped)

	unused := []string{}
	for name := range mapped {
		if !usedRule[name] {
			unused = append(unused, name)
		}
	}
	sum.RulesUnused = len(unused)
	sort.Strings(unused)

	return CoverageReport{Summary: sum, UnmappedObjectives: unmapped, UnusedRules: unused, Missions: missions}
}

// MissionCoverageReport is the exported accessor (admin panel / other packages).
func (s *Service) MissionCoverageReport() CoverageReport { return s.missionCoverage() }

// handleGetMissionCoverage reports which registered missions will advance from a match result.
func (s *Service) handleGetMissionCoverage(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, s.missionCoverage())
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
