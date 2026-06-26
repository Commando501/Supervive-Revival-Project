package interactive

import (
	"encoding/json"
	"io"
	"net/http"
)

// Service holds the interactive (write-back) state for menu actions.
type Service struct {
	store *store
}

// New constructs the service, loading any persisted player state from
// state/interactive.json (relative to the server's working dir).
func New() *Service {
	return &Service{store: newStore("state/interactive.json")}
}

// Register wires the interactive routes. These all previously fell through to the
// {} catch-all; registering them lets writes round-trip. Patterns are more
// specific than the catch-all "/" in cmd/ags, so they take precedence, and none
// collide with package menu's routes (menu owns /progression/players/{id}/tracks;
// we own /progression/players/{id} and .../mission — distinct patterns).
func (s *Service) Register(mux *http.ServeMux) {
	// ---- Personalization: client profile (the most visible round-trip) ----
	// The client SAVES preferences/visibility tracking here (SetClientProfileRequest,
	// body {"data":{...}}) and reads them back on GET. Model: ClientProfileData,
	// carrying clientVisibilityTracking (+ loadout/cosmetic preferences the client
	// edits elsewhere). We store the posted `data` verbatim and echo {"data": ...}
	// so the "NEW" badges (quests/storefront/armory/collection) stop reappearing.
	mux.HandleFunc("GET /personalization/players/{id}/clientprofile", s.handleGetClientProfile)
	mux.HandleFunc("POST /personalization/players/{id}/clientprofile", s.handleSetClientProfile)

	// ---- Personalization: equipped lobby platform (menu backdrop) ----
	// SetLobbyPlatformPreferenceRequest, body {"lobbyPlatformAssetId":"LobbyPlatform:Base"}.
	// Fired many times as the player browses backdrops. Persist + echo the ack.
	mux.HandleFunc("PUT /personalization/players/{id}/lobbyplatforms", s.handleSetLobbyPlatform)

	// ---- Personalization: player root ----
	// GET /personalization/players/{id} did NOT error on {} (no strict validity
	// predicate), so this is a probe to discover where the equipped lobby platform
	// is read back: we surface the stored lobbyPlatformAssetId here. Unmatched keys
	// are ignored by UE, so a wrong guess is harmless; the relaunch tells us if the
	// backdrop persists from this path.
	mux.HandleFunc("GET /personalization/players/{id}", s.handleGetPersonalizationPlayer)

	// ---- Progression ----
	// GET /progression/players/{id} logged "Invalid response received" on {} — it
	// wants the standard AccelByte data/paging wrapper (model
	// FAccelByteModelsListUserProgressionInfoPagingSlicedResult). PUT .../mission
	// claims/tracks a mission; no request body is captured (likely query/empty), so
	// we return a typed ack the client can consume.
	mux.HandleFunc("GET /progression/players/{id}", s.handleGetProgression)
	mux.HandleFunc("PUT /progression/players/{id}/mission", s.handlePutMission)

	// ---- Mailbox ----
	// GET /mailbox/config/version logged "Invalid response received" on {}. Field
	// recovered from the exe FName pool: MailboxConfigVersion. Probe a small typed
	// shape so LogMailbox can fetch a config version; the relaunch confirms the key.
	mux.HandleFunc("GET /mailbox/config/version", s.handleMailboxConfigVersion)
}

// defaultClientProfile is returned (under {"data": ...}) before the client has
// POSTed anything, matching the exact shape/zero-values the client itself sends
// so the read deserializes cleanly into ClientProfileData.
var defaultClientProfile = map[string]any{
	"clientVisibilityTracking": map[string]any{
		"lastBattlepassIdSeen":           "",
		"lastHuntersJourneyMaxLevelSeen": 0,
		"lastHuntersReleaseSeen":         "",
		"lastQuestsSeen":                 "0001-01-01T00:00:00.000Z",
		"lastStorefrontSeen":             "0001-01-01T00:00:00.000Z",
		"lastEventsSeen":                 map[string]any{},
		"unseenCollectionItems":          []any{},
		"lastSeenAccountLevel":           0,
		"lastSeenArmoryItemsForSeason":   "",
	},
}

func (s *Service) handleGetClientProfile(w http.ResponseWriter, r *http.Request) {
	st := s.store.get(r.PathValue("id"))
	var data any
	if len(st.ClientProfile) > 0 {
		data = json.RawMessage(st.ClientProfile)
	} else {
		data = defaultClientProfile
	}
	writeJSON(w, map[string]any{"data": data})
}

func (s *Service) handleSetClientProfile(w http.ResponseWriter, r *http.Request) {
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))

	// Body is {"data":{...ClientProfileData...}}. Persist the inner `data` verbatim
	// so the subsequent GET echoes precisely what the client saved. If parsing
	// fails, fall back to storing the whole body's `data` if present, else ignore.
	var envelope struct {
		Data json.RawMessage `json:"data"`
	}
	if json.Unmarshal(body, &envelope) == nil && len(envelope.Data) > 0 {
		s.store.update(r.PathValue("id"), func(st *playerState) {
			st.ClientProfile = envelope.Data
		})
	}

	// Echo the stored profile back (AccelByte set-then-return convention) so the
	// client's OnSetClientProfileOpComplete sees the persisted state.
	st := s.store.get(r.PathValue("id"))
	var data any = defaultClientProfile
	if len(st.ClientProfile) > 0 {
		data = json.RawMessage(st.ClientProfile)
	}
	writeJSON(w, map[string]any{"data": data})
}

func (s *Service) handleSetLobbyPlatform(w http.ResponseWriter, r *http.Request) {
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req struct {
		LobbyPlatformAssetId string `json:"lobbyPlatformAssetId"`
	}
	_ = json.Unmarshal(body, &req)
	if req.LobbyPlatformAssetId != "" {
		s.store.update(r.PathValue("id"), func(st *playerState) {
			st.LobbyPlatformAssetId = req.LobbyPlatformAssetId
		})
	}
	// Echo the accepted preference back as a typed ack.
	writeJSON(w, map[string]any{"lobbyPlatformAssetId": req.LobbyPlatformAssetId})
}

func (s *Service) handleGetPersonalizationPlayer(w http.ResponseWriter, r *http.Request) {
	st := s.store.get(r.PathValue("id"))
	resp := map[string]any{}
	if st.LobbyPlatformAssetId != "" {
		// Probe both likely key spellings for where the menu reads the equipped
		// backdrop. Both are plain strings, so an unmatched/extra key is ignored
		// and a matched string key deserializes cleanly.
		resp["lobbyPlatformAssetId"] = st.LobbyPlatformAssetId
		resp["equippedLobbyPlatform"] = st.LobbyPlatformAssetId
	}
	writeJSON(w, resp)
}

func (s *Service) handleGetProgression(w http.ResponseWriter, r *http.Request) {
	// "Invalid response received" on {} => wants the data/paging wrapper. Empty
	// (no per-player progression yet) is valid and quiets the retry.
	writeJSON(w, map[string]any{
		"data":   []any{},
		"paging": map[string]any{"previous": "", "next": ""},
	})
}

func (s *Service) handlePutMission(w http.ResponseWriter, r *http.Request) {
	// The PUT carries an EMPTY body (Content-Length 0) — it is a fire-and-forget
	// "reconcile my mission progress" trigger (exe: ServerAddMissionProgress /
	// SetMissionProgress), not a claim with a payload. Real mission *progress* is
	// added server-side during matches, so in the menu there is nothing per-player
	// to persist here.
	//
	// Response is the player's mission/progression state — model MissionData (exe
	// FName cluster). We return only its two TMap fields, each confirmed a map by a
	// `_Key` companion (Completions, TrackIDToClaimableRewards), as empty objects.
	// The sibling fields ClaimableProgressionTrackClaimData /
	// ClaimableProgressionTrackRewards have no `_Key` (array-or-struct, type
	// unconfirmed) so are omitted per the validity rule — an absent field defaults
	// safely; a wrong-typed present one would reject the whole doc.
	//
	// NOTE: the Missions modal stays empty regardless of this response — that is the
	// AssetManager "Invalid Primary Asset Type" gate (mission pools are UE Primary
	// Assets the client loads locally once the content-service manifest declares
	// their asset type). That is Track A's content manifest, not this endpoint.
	writeJSON(w, map[string]any{
		"Completions":               map[string]any{},
		"TrackIDToClaimableRewards": map[string]any{},
	})
}

func (s *Service) handleMailboxConfigVersion(w http.ResponseWriter, r *http.Request) {
	// Field recovered from exe FName pool: MailboxConfigVersion. Probe the common
	// camelCase spellings as ints (safe — a matched int key deserializes, unmatched
	// keys are ignored). Relaunch readback (LogMailbox) confirms which key lands.
	writeJSON(w, map[string]any{
		"version":              0,
		"configVersion":        0,
		"mailboxConfigVersion": 0,
	})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(v)
}
