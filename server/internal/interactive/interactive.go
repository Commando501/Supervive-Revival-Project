package interactive

import (
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"
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

	// ---- Party (solo auto-party — the tutorial/match launch gate) ----
	// The client polls GET /party/players/{id}?defaultQueue=tutorialNew to fetch (and
	// lazily create) its party. With the {} stub the client's PartyManager believes
	// "player not in party" (Loki.log warns exactly that), so clicking a tutorial /
	// FIND MATCH is a silent client-side no-op — it never even sends a start request.
	// We synthesize a valid SOLO party (the player as JOINED leader) so the launch
	// flow unblocks. Model is AccelByte's V2 session-based party (PartyMembers, member
	// status JOINED/CONNECTED, PartyReservation) wrapped by Theorycraft's /party
	// service; exact JSON shape is unconfirmed (no response body was ever captured), so
	// this is a superset probe — UE ignores unmatched keys and matches case-insensitively.
	mux.HandleFunc("GET /party/players/{id}", s.handleGetParty)

	// The detailed party object. After GET /party/players/{id} tells the client its
	// partyId, the client polls GET /party/parties/{partyId} for the full party (members,
	// queue state, …). This is what populates the PARTY panel slots; the {} stub leaves
	// them empty. Same Theorycraft model as /party/players; player id is derived from the
	// partyId ("party-<playerId>") we minted, falling back to the JWT.
	mux.HandleFunc("GET /party/parties/{partyId}", s.handleGetPartyDetail)

	// ---- Core-game (match lifecycle / region ping) ----
	// GET /core-game/players/{id} is the "do I have an active match to rejoin?" heartbeat
	// (polled ~800x/session); a "no active match" shape keeps it quiet and is the slot we
	// populate when a match starts. GET /core-game/regions feeds the region latency ping
	// (the menu's "??? - ms" + the missing ST_ServerLocations) and is required before
	// matchmaking can pick a region. Both are STAGED probes: the tutorial/FIND MATCH path
	// is currently hard-gated upstream on hero asset resolution (Track A content manifest -
	// every hunter renders as UnknownHero), so these can only be validated once a hunter is
	// selectable. Models are PascalCase UPROPERTY (CoreGameMatchModel: MatchInfo/Player/
	// RegionName/RouteName; region: RegionName/RouteName) - exact JSON unconfirmed (no
	// usmap / no captured response body), hence superset/best-effort field names.
	mux.HandleFunc("GET /core-game/players/{id}", s.handleCoreGamePlayer)
	mux.HandleFunc("GET /core-game/regions", s.handleCoreGameRegions)

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

// handleCoreGamePlayer returns a "no active match" core-game state — the player is idle in
// the menu, not in/rejoining a match. STAGED probe: omits a MatchInfo/Player object entirely
// (an absent field defaults safely; a wrong-typed present one would reject), which is the
// correct "nothing to rejoin" signal. When a match starts, this is where the match + server
// connection info goes.
func (s *Service) handleCoreGamePlayer(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"hasActiveMatch": false,
		"matchInfo":      nil,
		"player":         nil,
	})
}

// handleCoreGameRegions returns the region list the latency manager pings (fixes the menu's
// "??? - ms" + missing ST_ServerLocations). A bare array gave "Deserialization failure on
// GET /core-game/regions" (the client wants an OBJECT, not a TArray at top level), so the
// regions are wrapped. Region keys are the confirmed model names (RegionName/RouteName) plus
// a superset of host/port/display keys; the wrapper key is probed (regions/data/Regions).
// STAGED: one region at the local backend so the ping can resolve.
func (s *Service) handleCoreGameRegions(w http.ResponseWriter, r *http.Request) {
	region := map[string]any{
		"RegionName":  "na",
		"RouteName":   "na",
		"DisplayName": "Local",
		"Host":        "127.0.0.1",
		"PingHost":    "127.0.0.1",
		"Address":     "127.0.0.1",
		"Port":        443,
		"Enabled":     true,
	}
	regions := []any{region}
	writeJSON(w, map[string]any{
		"regions": regions,
		"Regions": regions,
		"data":    regions,
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

// handleGetParty returns a valid SOLO party so the menu's launch flow (tutorials,
// FIND MATCH) is enabled. Without this the client treats the player as party-less and
// the launch buttons do nothing.
//
// PROBE: the /party response body was never captured, so the exact JSON shape is
// inferred from the exe (AccelByte V2 session party + Theorycraft party wrapper). We
// emit a superset of plausible field names (PascalCase — UE matches case-insensitively)
// covering both the AccelByte-style fields (PartyId/LeaderId/Members/Invited/
// CrossplayEnabled/CreatedAt) and the Theorycraft reservation-style ones (PartyMembers/
// RemovedPartyMembers/TeamNum). Unmatched keys are ignored; the player appears as the
// sole JOINED leader/member. Relaunch readback (LogPartyManager — the "player not in
// party" warning clearing, and whether the tutorial button now acts) tells us which
// fields landed and what to trim.
func (s *Service) handleGetParty(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildSoloParty(id, display))
}

// handleGetPartyDetail answers GET /party/parties/{partyId} — the full party object the
// client polls (380×/session) after learning its partyId. Hitting the {} stub leaves the
// PARTY panel slots empty. We rebuild the same solo party; the player id is recovered from
// the minted partyId ("party-<playerId>"), falling back to the JWT sub.
func (s *Service) handleGetPartyDetail(w http.ResponseWriter, r *http.Request) {
	partyID := r.PathValue("partyId")
	id := strings.TrimPrefix(partyID, "party-")
	if id == partyID { // not our prefix — fall back to the JWT subject
		if sub := subjectFromBearer(r.Header.Get("Authorization")); sub != "" {
			id = sub
		}
	}
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildSoloParty(id, display))
}

// buildSoloParty constructs the CUSTOM Theorycraft party model (NOT AccelByte V2). Probes
// #1 (flat superset) and #2 (faithful AccelByte V2 session) both deserialized cleanly but
// were NOT adopted - wrong field family. The UTF-16 endpoint table in the exe proves /party
// is a bespoke Theorycraft surface (/party/players/, /party/parties/, /joinQueue,
// /startSoloMode, /setTargetQueues, /reconcile, ...) under UPartyManager. Confirmed party
// JSON fields (FName pool, camelCase): partyId, leader, members, invitees, invitationToken;
// member fields: userId/memberId/id, displayName, inQueue, ready, region. This validated
// live: with it, "player not in party" dropped 1002->2 and the PARTY panel renders.
func buildSoloParty(id, display string) map[string]any {
	now := time.Now().UTC().Format(time.RFC3339)
	member := map[string]any{
		"id":          id,
		"userId":      id,
		"memberId":    id,
		"displayName": display,
		"ready":       true,
		"isReady":     true,
		"inQueue":     false,
		"region":      "",
		"leader":      true,
		"isLeader":    true,
	}
	return map[string]any{
		"partyId":         "party-" + id,
		"id":              "party-" + id,
		"leader":          id,
		"leaderId":        id,
		"ownerId":         id,
		"members":         []any{member},
		"invitees":        []any{},
		"invitationToken": "",
		"joinSecret":      "",
		"inQueue":         false,
		"isOpen":          false,
		"fillTeam":        false,
		"createdAt":       now,
		"version":         1,
	}
}

// displayNameFromBearer best-effort extracts the player's display name from the JWT in
// the Authorization header (claim display_name) so the party member renders correctly.
// Returns "" on any failure.
func displayNameFromBearer(authz string) string {
	parts := strings.Split(strings.TrimPrefix(authz, "Bearer "), ".")
	if len(parts) != 3 {
		return ""
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return ""
	}
	var claims struct {
		DisplayName       string `json:"display_name"`
		UniqueDisplayName string `json:"unique_display_name"`
	}
	if json.Unmarshal(payload, &claims) != nil {
		return ""
	}
	if claims.DisplayName != "" {
		return claims.DisplayName
	}
	return claims.UniqueDisplayName
}

// subjectFromBearer extracts the `sub` (player id) claim from the JWT. Returns "" on failure.
func subjectFromBearer(authz string) string {
	parts := strings.Split(strings.TrimPrefix(authz, "Bearer "), ".")
	if len(parts) != 3 {
		return ""
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return ""
	}
	var claims struct {
		Sub string `json:"sub"`
	}
	if json.Unmarshal(payload, &claims) != nil {
		return ""
	}
	return claims.Sub
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(v)
}
