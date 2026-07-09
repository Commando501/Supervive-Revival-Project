// Package admin (2026-07-08) serves the operator control panel for the revival
// backend: an embedded single-page GUI (static/index.html) plus a JSON API that
// mutates the same state the game-facing handlers read — the menu/storefront
// config (heroes unlocked, store SKU lists, wallet, prices) and the interactive
// per-player store (selected hunter, loadout equips, mission progress).
//
// It registers on its OWN mux/listener (cmd/ags binds it to 127.0.0.1 only, flag
// -admin) so nothing here can collide with an impersonated client route, and the
// panel is never reachable from off-box. A loopback RemoteAddr check is kept as
// defense-in-depth in case the operator rebinds the flag to a wide address.
//
// What actually reaches the client (honesty notes, mirrored in the GUI):
//   - Heroes/store lists/wallet: real effect — the client refetches inventory/
//     storefront/wallet on menu entry, so edits apply on the next relaunch or
//     menu re-entry. Ownership and store advertising share the same lists.
//   - Prices: stored but INERT in-client for now (the client reads prices from
//     the packed CatalogEntry offers — see menu.OfferCost).
//   - Mission progress: real effect via the client-side missions shim (menu-load
//     fetch + change poll). Mission REQUIREMENTS (objectives, maxes, text) live
//     in client-side data assets and cannot be changed from the backend.
package admin

import (
	"bytes"
	"embed"
	"encoding/json"
	"io"
	"net"
	"net/http"

	"supervive-revival/server/internal/interactive"
	"supervive-revival/server/internal/menu"
)

//go:embed static/index.html
var staticFS embed.FS

// Service wires the admin API to the state it administers.
type Service struct {
	Interactive *interactive.Service
}

func New(inter *interactive.Service) *Service { return &Service{Interactive: inter} }

// Register attaches the GUI + API routes. Call on the dedicated admin mux.
func (s *Service) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /{$}", s.handleIndex)

	mux.HandleFunc("GET /api/config", s.handleGetConfig)
	mux.HandleFunc("PUT /api/config", s.handlePutConfig)

	mux.HandleFunc("GET /api/players", s.handleListPlayers)
	mux.HandleFunc("GET /api/players/{id}", s.handleGetPlayer)
	mux.HandleFunc("PUT /api/players/{id}", s.handlePutPlayer)
	mux.HandleFunc("DELETE /api/players/{id}", s.handleDeletePlayer)

	mux.HandleFunc("GET /api/missions", s.handleGetMissions)
	mux.HandleFunc("PUT /api/missions/progress", s.handlePutMissionProgress)
	mux.HandleFunc("POST /api/missions/match-result", s.handleMatchResult)
}

// Guard wraps the admin handler with a loopback-only check. The listener is
// already bound to 127.0.0.1 by default; this keeps the panel local even if an
// operator rebinds -admin to 0.0.0.0 without understanding the exposure.
func Guard(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host, _, err := net.SplitHostPort(r.RemoteAddr)
		if err != nil || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
			http.Error(w, "admin panel is loopback-only", http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *Service) handleIndex(w http.ResponseWriter, r *http.Request) {
	b, err := staticFS.ReadFile("static/index.html")
	if err != nil {
		http.Error(w, "embedded UI missing", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write(b)
}

// handleGetConfig returns the live config, the built-in defaults (the GUI's
// checklists render the full default lists with the live ones checked), and the
// persistence path.
func (s *Service) handleGetConfig(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"config":   menu.Snapshot(),
		"defaults": menu.Defaults(),
		"path":     menu.ConfigPath(),
	})
}

// handlePutConfig applies a full config doc. Unknown fields are rejected so a
// GUI/curl typo fails loudly. The new config is always published in-memory; a
// persistence failure is reported in the response but does not roll it back.
func (s *Service) handlePutConfig(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<22))
	var c menu.Config
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&c); err != nil {
		httpError(w, http.StatusBadRequest, "config parse: "+err.Error())
		return
	}
	saveErr := ""
	if err := menu.Apply(c); err != nil {
		saveErr = err.Error()
	}
	writeJSON(w, map[string]any{
		"config":    menu.Snapshot(),
		"saveError": saveErr,
	})
}

// handleListPlayers returns every persisted player with its full state doc (the
// revival is single-account in practice, so this stays tiny).
func (s *Service) handleListPlayers(w http.ResponseWriter, r *http.Request) {
	type entry struct {
		ID    string          `json:"id"`
		State json.RawMessage `json:"state"`
	}
	out := []entry{}
	for _, id := range s.Interactive.PlayerIDs() {
		if b, ok := s.Interactive.PlayerStateJSON(id); ok {
			out = append(out, entry{ID: id, State: b})
		}
	}
	writeJSON(w, map[string]any{"players": out})
}

func (s *Service) handleGetPlayer(w http.ResponseWriter, r *http.Request) {
	b, ok := s.Interactive.PlayerStateJSON(r.PathValue("id"))
	if !ok {
		httpError(w, http.StatusNotFound, "no state for player")
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}

func (s *Service) handlePutPlayer(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<22))
	id := r.PathValue("id")
	if err := s.Interactive.SetPlayerStateJSON(id, raw); err != nil {
		httpError(w, http.StatusBadRequest, err.Error())
		return
	}
	b, _ := s.Interactive.PlayerStateJSON(id)
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}

func (s *Service) handleDeletePlayer(w http.ResponseWriter, r *http.Request) {
	s.Interactive.DeletePlayer(r.PathValue("id"))
	writeJSON(w, map[string]any{"deleted": r.PathValue("id")})
}

// handleGetMissions returns the shim-registered manifest joined with the stored
// per-objective progress. The GUI derives each row's max from the manifest.
func (s *Service) handleGetMissions(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"manifest":   s.Interactive.MissionManifest(),
		"objectives": s.Interactive.MissionObjectives(),
	})
}

// handlePutMissionProgress sets absolute progress values; {"replace":true} wipes
// the map first (so an empty objectives doc = full reset).
func (s *Service) handlePutMissionProgress(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<22))
	var body struct {
		Objectives map[string]float64 `json:"objectives"`
		Replace    bool               `json:"replace"`
	}
	if err := json.Unmarshal(raw, &body); err != nil {
		httpError(w, http.StatusBadRequest, "progress parse: "+err.Error())
		return
	}
	writeJSON(w, map[string]any{
		"objectives": s.Interactive.SetMissionObjectives(body.Objectives, body.Replace),
	})
}

// handleMatchResult runs the same match-result -> objective-increment engine as
// the game-facing POST /revival/missions/match-result.
func (s *Service) handleMatchResult(w http.ResponseWriter, r *http.Request) {
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	applied, objectives, err := s.Interactive.ApplyMatchResultJSON(raw)
	if err != nil {
		httpError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, map[string]any{"applied": applied, "objectives": objectives})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func httpError(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
