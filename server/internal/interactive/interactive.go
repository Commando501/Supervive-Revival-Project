package interactive

import (
	"encoding/base64"
	"encoding/json"
	"encoding/hex"
	"crypto/sha256"
	"fmt"
	"hash/fnv"
	"io"
	"log"
	"net/http"
	"os"
	"sort"
	"strings"
	"sync"
	"time"
)

// Service holds the interactive (write-back) state for menu actions.
type Service struct {
	store *store
	// partyDirty, if set, is called with a player id after a loadout-affecting write
	// so the lobby service can drop that player's messenger socket and force a prompt
	// party re-apply (the S85 avatar-switch latency fix â€” see lobby.MarkDirty). nil in
	// tests / when no lobby service is wired.
	partyDirty func(id string)
}

// New constructs the service, loading any persisted player state from
// state/interactive.json (relative to the server's working dir).
func New() *Service {
	return &Service{store: newStore("state/interactive.json")}
}

// SetPartyDirtyNotifier wires the callback invoked after a loadout write (typically
// lobby.Service.MarkDirty). Called once at startup from cmd/ags.
func (s *Service) SetPartyDirtyNotifier(fn func(id string)) { s.partyDirty = fn }

// PartyVersion exposes the monotonic party version for the lobby's targeted
// per-resource resync (FK-15 probe #3). The messenger's refetch gate is
// "pushed version > cached version", so it needs the same counter the party
// document is served with, not an ad-hoc one.
func (s *Service) PartyVersion() int64 { return s.store.partyVersion() }

// markLoadoutDirty signals that id's loadout changed, so the client can be nudged to
// re-apply its party promptly. No-op if no notifier is wired.
func (s *Service) markLoadoutDirty(id string) {
	if s.partyDirty != nil {
		s.partyDirty(id)
	}
}

// Register wires the interactive routes. These all previously fell through to the
// {} catch-all; registering them lets writes round-trip. Patterns are more
// specific than the catch-all "/" in cmd/ags, so they take precedence, and none
// collide with package menu's routes (menu owns /progression/players/{id}/tracks;
// we own /progression/players/{id} and .../mission â€” distinct patterns).
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

	// ---- Personalization: player root = the PersonalizationLoadout readback ----
	// 2026-07-06: no longer a blind probe. The exe's route-fragment table +
	// usmap schemas (see loadout.go) identify this GET as the loadout fetch the
	// customization page repopulates from (ULoadoutReconciler). We answer with
	// the full loadout doc built from persisted equips; the original probe keys
	// are kept alongside (unmatched keys are ignored â€” zero regression).
	mux.HandleFunc("GET /personalization/players/{id}", s.handleGetPersonalizationPlayer)

	// ---- Personalization: customization equips (slot cosmetics, emotes, titles,
	// hero skin bundles, luxe chromas) â€” see loadout.go for the recovered models.
	s.registerLoadout(mux)

	// ---- Progression ----
	// GET /progression/players/{id} logged "Invalid response received" on {} â€” it
	// wants the standard AccelByte data/paging wrapper (model
	// FAccelByteModelsListUserProgressionInfoPagingSlicedResult). PUT .../mission
	// claims/tracks a mission; no request body is captured (likely query/empty), so
	// we return a typed ack the client can consume.
	mux.HandleFunc("GET /progression/players/{id}", s.handleGetProgression)
	mux.HandleFunc("PUT /progression/players/{id}/mission", s.handlePutMission)
	// POST /progression/players/{id}/hero/rewards/claim — the hero-mastery reward claim. The URL,
	// verb and body were traced from the shipped binary (literal L"/hero/rewards/claim" at
	// .rdata 0x08B4D3A0, builder .text 0x05827DA0); see heromastery.go's block comment.
	s.registerHeroMastery(mux)

	// ---- Match history ----
	// Previously fell through to the {} catch-all. See handleMatchHistory: this is
	// the FIRST of the two gates in front of the lobby banner carousel.
	mux.HandleFunc("GET /match-history/players/{id}", s.handleMatchHistory)

	// ---- Missions (Option 2: real progress tracking) â€” see missions.go ----
	// Revival-only endpoints (NOT an impersonated client route): the client-side
	// missions shim fetches per-objective progress here on menu load and applies it
	// to the modal's bars; match-end hooks increment it. Persisted per objective
	// unique-name (GetUniqueObjectiveName) in the shared store.
	s.registerMissions(mux)

	// ---- Party (solo auto-party â€” the tutorial/match launch gate) ----
	// The client polls GET /party/players/{id}?defaultQueue=tutorialNew to fetch (and
	// lazily create) its party. With the {} stub the client's PartyManager believes
	// "player not in party" (Loki.log warns exactly that), so clicking a tutorial /
	// FIND MATCH is a silent client-side no-op â€” it never even sends a start request.
	// We synthesize a valid SOLO party (the player as JOINED leader) so the launch
	// flow unblocks. Model is AccelByte's V2 session-based party (PartyMembers, member
	// status JOINED/CONNECTED, PartyReservation) wrapped by Theorycraft's /party
	// service; exact JSON shape is unconfirmed (no response body was ever captured), so
	// this is a superset probe â€” UE ignores unmatched keys and matches case-insensitively.
	mux.HandleFunc("GET /party/players/{id}", s.handleGetParty)

	// The detailed party object. After GET /party/players/{id} tells the client its
	// partyId, the client polls GET /party/parties/{partyId} for the full party (members,
	// queue state, â€¦). This is what populates the PARTY panel slots; the {} stub leaves
	// them empty. Same Theorycraft model as /party/players; player id is derived from the
	// partyId ("party-<playerId>") we minted, falling back to the JWT.
	mux.HandleFunc("GET /party/parties/{partyId}", s.handleGetPartyDetail)

	// ---- Party: set my member (hero/cosmetics selection â€” the selected-hunter flow) ----
	// Picking an owned hunter in the ALL HUNTERS roster calls TryPickMyHeroAndCosmetics on
	// the native PartyManager (traced from WBP_UI_PartyHeroSelect bytecode: OnHeroSelected ->
	// TryPick -> PartyManager.TryPickMyHeroAndCosmetics(HeroAssetId, CosmeticsAssetId)). That
	// sets the local PartyMemberModel.HeroAssetID (firing OnHeroAssetIDChanged -> the center
	// preview re-renders) AND writes the member to the /party service. The member op hangs off
	// /party/parties/{partyId}/ (the one captured party write was POST .../{partyId}/setIsOpen/True),
	// so the hero set is the /members/ operation seen in the exe's party endpoint table
	// (model SetPartyMemberRequest{ID, HeroAssetID, CosmeticsAssetID, ...}). We persist the
	// posted HeroAssetID so the subsequent GET /party/parties poll echoes it back (otherwise
	// the ~1s poll would reset the member to the default and the pick would visibly revert).
	//
	// PROBE: the exact verb+path for the member write was never captured (heroes only became
	// selectable this session), so we register the best-guess POST/PUT on the members subpath.
	// If the real path differs, this simply never fires (the write falls through to {} as
	// before â€” no regression); the seed default still renders a hunter. Confirm/trim the path
	// from a live capture of a hero click, then narrow this.
	mux.HandleFunc("POST /party/parties/{partyId}/members/{memberId}", s.handleSetPartyMember)
	mux.HandleFunc("PUT /party/parties/{partyId}/members/{memberId}", s.handleSetPartyMember)

	// POST /party/parties/{partyId}/startSoloMode?mode=&hero=&soloModeStartPosition= is the REAL
	// tutorial/practice launch call (S61: reached after cracking the native login gate [GameMode
	// vtable slot 285] + the native TryStartSoloMode party-state gate [PartyModel+0x558+0x18 mode
	// string == "default"/"Matchmaking"]). Previously fell through to the {} catch-all (200, silently
	// accepted -> bSuccess=true, no travel). We record the solo-start so /core-game/players can report
	// the (local) tutorial match, and echo the party as a clean success body.
	mux.HandleFunc("POST /party/parties/{partyId}/startSoloMode", s.handleStartSoloMode)

	// ---- Party: matchmaking (available queues â€” unlocks the ActivityPicker tiles) ----
	// The play menu is WBP_ActivityPickerScreen; its InitializeQueues builds each activity
	// tile ONLY if the tile's queue id is present in PartyModel.GetQueues() (traced from
	// bytecode: GetPartyManager->GetPartyModel->GetQueues, then per-tile FindQueueByID +
	// Set_Contains). A tile whose queue isn't in that set renders "locked" â€” it shows a hover
	// highlight but a CLICK can't latch a selection (the selected state is derived from the
	// party's TargetQueueID, and the queue must resolve first), so FIND MATCH stays a no-op.
	// That set is populated from GET /party/matchmaking/info, which deserializes into QueueInfo
	// (usmap QueueInfo: Queues []string, ETag string, LastUpdated DateTime). With the {} stub
	// the list is empty -> every tile locked -> the exact silent no-op the user hit.
	// We advertise the full known queue-id set â€” the string constants InitializeQueues checks:
	//   default deathmatch practice dropin customgame bots tutorialNew training
	//   armorydeathmath tournament   ("armorydeathmath" is the game's own misspelling, verbatim).
	// customGameModes is the sibling list for the custom-game screen -> CustomGameModeInfo
	// (Modes []string, ETag, LastUpdated); a typed empty stops the {} stub from tripping a
	// deserialize error. STAGED: unlocking the tile is step 1; making a click PERSIST the
	// selection (party TargetQueueID) + FIND MATCH launch are the follow-ups.
	mux.HandleFunc("GET /party/matchmaking/info", s.handleMatchmakingInfo)
	mux.HandleFunc("GET /party/matchmaking/customGameModes", s.handleMatchmakingCustomGameModes)

	// ---- Core-game (match lifecycle / region ping) ----
	// GET /core-game/players/{id} is the "do I have an active match to rejoin?" heartbeat
	// (rapid-polled while a solo-start allocates â€” ~17/s in S61). GROUND TRUTH (usmap
	// CoreGamePlayer, 4 props): { ID, MatchID, Version, CanDisassociate }. The client
	// watches for a non-empty MatchID, then fetches the full match (MatchInfo) from the
	// match route below and travels. GET /core-game/regions feeds the region latency ping
	// (the menu's "??? - ms" + the missing ST_ServerLocations). The upstream hero-asset gate
	// that used to block this (every hunter UnknownHero) is now solved (roster fix), and the
	// native solo-start walls are down (S61: login vtable slot 285 + TryStartSoloMode party-
	// state gate), so this is the live travel channel â€” see handleCoreGamePlayer.
	mux.HandleFunc("GET /core-game/players/{id}", s.handleCoreGamePlayer)
	mux.HandleFunc("GET /core-game/regions", s.handleCoreGameRegions)

	// GET /core-game/matches/{matchId} â€” the match-details fetch (S62 PROBE). Once
	// /core-game/players reports a non-empty MatchID (real CoreGamePlayer model), the
	// client's CoreGameManager fetches the full match to populate CoreGameMatchModel
	// (MatchInfo/MatchState) and fire OnMatchStarted -> travel. The exact route was never
	// captured (MatchID had always been empty until now), so this is the best-guess path;
	// if the client actually uses a different route it falls through to the {} catch-all
	// and shows up in docs/capture.log (which reveals the true path for the follow-up).
	// Returns a tutorial MatchInfo (usmap model) â€” see buildTutorialMatchInfo.
	mux.HandleFunc("GET /core-game/matches/{matchId}", s.handleCoreGameMatch)

	// ---- Mailbox ----
	// GET /mailbox/config/version logged "Invalid response received" on {}. Field
	// recovered from the exe FName pool: MailboxConfigVersion. Probe a small typed
	// shape so LogMailbox can fetch a config version; the relaunch confirms the key.
	mux.HandleFunc("GET /mailbox/config/version", s.handleMailboxConfigVersion)

	// ---- Leaderboards (S121) ----
	// Only ever observed on the wire AFTER the `leaderboards` UI feature toggle started binding
	// (the Config["enabled"] fix, 5e40475) — before that the page never rendered, so the client
	// never called this. See leaderboard.go; the response MUST echo the request or it is parsed
	// and then silently discarded.
	mux.HandleFunc("GET /player-stats/leaderboard", s.handleLeaderboard)
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
			// The backdrop is part of the PersonalizationLoadout
			// (lobbyPlatformPreference), so this write must advance the loadout
			// version too or the reconciler ignores the change (see loadout.go).
			st.LoadoutVersion++
		})
	}
	// Echo the accepted preference back as a typed ack, plus the full updated
	// loadout in every envelope the reconciler might parse (set-then-return; the
	// client merges this write response â€” see loadoutResponse).
	resp := s.loadoutResponse(r.PathValue("id"))
	resp["lobbyPlatformAssetId"] = req.LobbyPlatformAssetId
	writeJSON(w, resp)
}

// handleGetPersonalizationPlayer answers the personalization root GET with the
// full PersonalizationLoadout doc (see loadout.go â€” this is the readback the
// customization page rebuilds from). The pre-2026-07-06 probe keys for the
// backdrop are kept alongside; they were never observed to hurt and removing
// them would change two variables at once.
func (s *Service) handleGetPersonalizationPlayer(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	resp := s.loadoutResponse(id)
	if st := s.store.get(id); st.LobbyPlatformAssetId != "" {
		resp["lobbyPlatformAssetId"] = st.LobbyPlatformAssetId
		resp["equippedLobbyPlatform"] = st.LobbyPlatformAssetId
	}
	writeJSON(w, resp)
}

// progressionVersion backs the FPlayerProgression.Version field served by
// handleGetProgression. The client-side ingester (game RVA 0x585A570) adopts a response only
// when its Version is STRICTLY greater than the adopted value at ProgressionManager+0xA0
// (+585A594 cmp / +585A597 jle bail). Starts at 3 (live PM+0xA0 = -1, so the first served
// value just has to be >= 0) and bumps on EVERY request, because the client re-polls this
// route every ~61s and a constant would be adopted once and then permanently ignored.
// CONFIRMED LIVE 2026-07-18 (S83): serving this made the ingester adopt â€” PM+0xA0 went -1 -> 4,
// PM+0x17C (Level) 0 -> 12, PM+0x180 (XP) 0 -> 1500, PM+0x388 -> 1, and Loki.log's Progress Notif
// went {currentTierIndex:0,currentXP:0,requiredXP:2000} -> {12, 1500, requiredXP:22000} (the client
// RECOMPUTED requiredXP for tier 12 from the packed CDO ladder, i.e. it is really consuming this).
//
// Version bumps ONLY when the served content changes. The gate is strict (>), so an unchanged
// Version is simply not re-adopted â€” which is what we want: bumping every request re-Broadcast the
// PM+0x48 delegate (CheckAccountPassChanges/CheckMastery/CheckLoginReward/CheckEventProgression)
// on the client's ~61s poll forever, i.e. a permanent fan-out for no new data.
// progressionState tracks the served FPlayerProgression.Version PER PLAYER. It must be
// per-player, not a single counter: the version is compared against the CLIENT's adopted
// value, so two accounts with different progress sharing one counter would each bump the
// other's version and re-broadcast on every poll.
var progressionState struct {
	mu sync.Mutex
	by map[string]*progressionVer
}

type progressionVer struct {
	ver  int64
	last string
}

// progressionVersionFor returns the version to serve to one player for the given AccountPass
// content, incrementing only when that content differs from what was last served to them.
func progressionVersionFor(id, content string) int64 {
	progressionState.mu.Lock()
	defer progressionState.mu.Unlock()
	if progressionState.by == nil {
		progressionState.by = map[string]*progressionVer{}
	}
	pv := progressionState.by[id]
	if pv == nil {
		// Seed from wall-clock seconds, NOT from a small constant. The client's adopted value
		// (ProgressionManager+0xA0) SURVIVES an ags restart, but a process-local counter does not:
		// restarting ags would then serve a version <= the adopted one, and the strict `jle` gate
		// would silently drop every subsequent change (indistinguishable from "the route broke").
		// Wall-clock is monotonic across restarts and comfortably fits the DWORD the gate compares.
		pv = &progressionVer{ver: time.Now().Unix()}
		progressionState.by[id] = pv
	}
	if content != pv.last {
		pv.last = content
		pv.ver++
	}
	return pv.ver
}

func (s *Service) handleGetProgression(w http.ResponseWriter, r *http.Request) {
	// "Invalid response received" on {} => wants the data/paging wrapper. Empty
	// (no per-player progression yet) is valid and quiets the retry.
	//
	// 2026-07-18 (S82) â€” LEVER A for the PASSES account pass ("Hunter's Journey").
	// RE of BattlepassViewManager::CheckAccountPassChanges (offline disasm, adversarially
	// verified) showed the account pass is gated by the ProgressionManager, NOT the
	// battlepass storefront progressiontracks: GetAccountTrack (game RVA 0x5840700) returns
	// false unless a flag at ProgressionManager+0x208 is set + the account-track struct at
	// +0x90 is populated, and the track's CurrentTierIndex (@track+0xEC) must be != -1
	// (predicate 0x584B920). Those are populated by the deserialized /progression response.
	// The HuntersJourney correlation itself is client-side (the published-pass class's
	// FPrimaryAssetId string is the VM lookup key); the account VM is FOUND (not built) here,
	// so lever A alone may only pass the GATE (setting +0x208/+0x90) without rendering the
	// tab if the VM isn't pre-built â€” but it also DEMAND-DECRYPTS the account-VM builder
	// branch so it can be RE'd. Model = FAccelByteModelsListUserProgressionInfoPagingSlicedResult
	// { Data:[FAccelByteModelsListUserProgressionInfo], Paging, Total }. Each entry's fields
	// are Str/Int/Bool/enum-Str/nested-struct â€” none can wrong-type-reject the doc (DateTime
	// fields OMITTED to avoid any format risk; absent is safe per the validity model).
	// ProgressionType enum = EAccelByteProgressionTrackType (PROGRESSION_TRACK=2, the
	// NON-season type â€” distinct from the SEASON_PASS storefront track). Not "-ranked".
	// See memory supervive-passes-battlepass-status (S82 part 3).
	id := r.PathValue("id")
	track := map[string]any{
		"ID":              "supervive-hunters-journey",
		"NameSpace":       "supervive",
		"Name":            "HuntersJourney",
		"ProgressionType": "PROGRESSION_TRACK",
		"Status":          "PUBLISHED",
		"Active":          true,
	}
	entry := map[string]any{
		"ID":               "hunters-journey-" + id,
		"NameSpace":        "supervive",
		"UserId":           id,
		"ProgressionId":    "HuntersJourney",
		"CurrentTierIndex": 3, // distinctive vs /tracks(=5) & default(-1): fresh-login probe of PM+0x17C tells which endpoint drives the tier
		"LastTierIndex":    3,
		"RequiredExp":      1000,
		"CurrentExp":       150,
		"Cleared":          false,
		"ProgressionTrack": track,
		"Active":           true,
	}
	// 2026-07-18 (S83) â€” ROUTE A: the ACCOUNT-PASS PROGRESS lever. Strict SUPERSET of the
	// response above: every existing key is untouched, we only ADD three top-level keys.
	// Unknown keys are ignored, so if the wire model is still the AccelByte envelope this is
	// byte-equivalent to before and CANNOT regress.
	//
	// WHY THIS ROUTE: offline RE (byte-verified, 3 independent reviewers) traced this endpoint's
	// OnSuccess delegate to the ONLY writer of the account track:
	//   +58618B2 call 0x58454A0 (dispatcher) -> +58454D2 lea rdx -> 0x8B4D0D0 L"/progression/players/"
	//   OnSuccess 0x585C460 -> +585C48C jmp 0x585A570  (the ingester)
	// 0x585A570 copy-constructs FPlayerProgression into PM+0x90 via 0x58061A0 (writes
	// track+0xEC @+5806363), sets PM+0x208 and PM+0x388, then Broadcasts PM+0x48 â€” to which
	// CheckAccountPassChanges & friends are AddDynamic-bound. So one accepted response does the
	// whole refresh natively; we never fabricate a struct or force-call anything.
	//
	// THE MODEL (recovered, NOT invented): the ingester takes FPlayerProgression (size 0x178;
	// live UStruct reflection walk + the mappings.usmap name table) = { ID, Version(int),
	// AccountPass: FProgressionTrackLevel (size 0x60) { Level, XP, Cleared, UnclaimedRewards } }.
	// Only the scalar leaves are served here: a MATCHED key with a wrong CONTAINER type rejects
	// the WHOLE document (and would look identical to "no effect"), so Matches/MissionInfo/
	// HeroMastery/LoginReward/EventProgression/UnclaimedRewards are deliberately OMITTED â€”
	// absent is safe. Name matching is case-insensitive (the camelCase in Loki.log is
	// FJsonObjectConverter's OUTPUT convention, not an input requirement).
	//
	// VERSION MUST BE MONOTONIC PER REQUEST. The ingester's gate is
	//   +585A594 cmp dword[src+0x10], dword[PM+0xA0] ; +585A597 jle bail
	// i.e. STRICT >. Live PM+0xA0 = -1 (signed), so any Version >= 0 passes the first time â€” but
	// a CONSTANT would then be <= the adopted value and re-deadlock on the client's ~61s poll.
	// That is exactly the "worked once then stopped" signature, so bump every request.
	//
	// DISCRIMINATOR (tools/re/battlepass_pm_probe.py): dword[PM+0xA0] moves off -1 to the served
	// Version, and dword[PM+0x17C] (AccountPass.Level) becomes the served Level. byte[PM+0x388]
	// flipping to 1 here is a LEGITIMATE side effect (the ingester archives PM+0x90 -> PM+0x210
	// first) â€” categorically different from poking that byte by hand, which arms a wild free.
	// NB the sibling route /progression/players/{id}/tracks is a PROVEN dead end for this
	// (see menu.go handlePlayerProgressionTracks) â€” it feeds a different manager entirely.
	//
	// The values come from PERSISTED PER-PLAYER STATE, editable live from the admin panel
	// (PUT /api/progression/{id}); a fresh account reads the zero value = tier 0 / no XP.
	ap := s.AccountPass(id)
	mi, miDigest := s.missionInfo(time.Now().UTC())
	// HERO MASTERY (S120) — FPlayerProgression.HeroMastery @0x148, TArray<FHeroMasteryProgress>.
	// Returns (nil, "") unless AGS_SERVE_HEROMASTERY is set, in which case the key below is
	// omitted and this document is byte-identical to the pre-S120 one. See heromastery.go for
	// the measured schema, the two candidate HeroId type prefixes, and why this is knob-gated.
	hm, hmDigest := s.heroMasteryEntries(id)
	resp := map[string]any{
		"data":   []any{entry},
		"paging": map[string]any{"previous": "", "next": ""},
		"total":  1,

		"ID": id,
		// The mission digest joins the version key so a mission/progress change bumps Version
		// too; without it the strict `>` gate below would silently drop the new document. The
		// digest covers mission content only, never the per-request timestamps.
		// The hero-mastery digest joins it for the same reason — including the knob's own mode,
		// so ARMING the knob is itself a content change that moves Version. Without that, a
		// client that had already adopted this Version would ignore the newly-added key and the
		// experiment would read as "serving HeroMastery does nothing".
		"Version": progressionVersionFor(id, fmt.Sprintf("%d/%d/%t|%s|%s", ap.Level, ap.XP, ap.Cleared, miDigest, hmDigest)),
		"AccountPass": map[string]any{
			"Level":   ap.Level,
			"XP":      ap.XP,
			"Cleared": ap.Cleared,
		},
		"MissionInfo": mi,
	}
	if hm != nil {
		resp["HeroMastery"] = hm
	}
	writeJSON(w, resp)
}

// handleMatchHistory serves FMatchHistory. This is the FIRST of the two gates in front of
// the lobby news/announcement banner carousel, and it had never been served at all — the
// route fell through to the {} catch-all (200, 2 bytes).
//
// THE GATE (decoded from blueprint bytecode, WBP_UI_PlayScreen_LobbyV2::ExecuteUbergraph):
//
//	[ 7] EX_JumpIfNot( IsMatchHistoryLoaded )      <-- THIS. Jumps past the whole block.
//	[10] EX_JumpIfNot( GetMissionsModel()->bAllMissionLoaded )
//	[11] InitializeBanners()   -> GetTodaysBannerConfig -> carousel SetupFromConfig
//
// Gate [10] is now OPEN natively (see missionInfo() above — MEASURED: Missions.Num=1,
// bAllMissionLoaded=1, and the missions page renders with no shim). Gate [7] is what
// remains, and it is a pure data test.
//
// WHY THIS SHAPE. UMatchHistoryManager reflects only 3 UPROPERTYs (OnUpdatedMatchHistory,
// MatchHistoryService, RefreshOperation), so the fields the gate reads are NON-reflected
// natives. MEASURED live (PID 42112): +0x60 = 0, +0x68 = -2 (0xFFFFFFFFFFFFFFFE), and
// MatchHistoryManager::IsMatchHistoryLoaded (thunk rva 0x54A6340, fold multiplicity 1) is
// literally `cmp qword ptr [rcx+0x68], -1 ; setge al`, i.e.
//
//	IsMatchHistoryLoaded  ==  ( [this+0x68] >= -1 )
//
// That lines up exactly with an FMatchHistory stored INLINE on the manager:
//
//	+0x48  OnUpdatedMatchHistory  (multicast delegate, 16 B)
//	+0x58  FMatchHistory.ID       (FString — +0x60 reading Num=0/Max=0 is an EMPTY string)
//	+0x68  FMatchHistory.Version  (int64)   <-- the gate's field; -2 = never loaded
//	+0x70  FMatchHistory.Matches  (TArray<FMatchHistoryEntry>)
//
// [INFERRED, not proven: the +0x58/+0x70 attribution. What IS measured is the predicate,
// the -2, and the empty-FString-shaped +0x60.] So -2 is the never-loaded sentinel and ANY
// document carrying Version >= -1 should flip the gate.
//
// THE MODEL (reflection, names/scalars trustworthy; FK-14 only taints container INNERS):
//
//	FMatchHistory { ID FString; Version int64; Matches TArray<FMatchHistoryEntry> }
//
// Matches is served EMPTY and that is deliberate on two counts: an empty history is
// authentic for this account, and it keeps the probe single-variable — the gate needs
// Version, not entries. FMatchHistoryEntry is a 15-field struct (DateTimes, an
// FPrimaryAssetId HeroAssetID, nested FMatchHistoryTeamInfo / FLokiPlayerMatchStats, an
// ERank enum); every one of those is a chance to wrong-type a MATCHED key and reject the
// WHOLE document, which would look identical to "the gate does not work". Populate it only
// after the gate is confirmed. ⚠ FK-21 also warns that an authentic empty and a broken
// deserialization are observationally identical here — the discriminator is the LIVE
// +0x68 read, not the Career UI.
//
// VERSION: monotonic per player, seeded from wall-clock so it survives an ags restart
// (same reasoning as progressionVersionFor, which this reuses under a namespaced key).
// ⚠ When pushing this resource over the messenger to force a refetch, pass THIS EXACT
// value — push.go documents both failure modes: too low is silently ignored, too high
// causes an UNBOUNDED REFETCH LOOP (46 fetches in 4 s, measured).
func (s *Service) handleMatchHistory(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	writeJSON(w, map[string]any{
		"ID":      id,
		"Version": MatchHistoryVersion(id),
		"Matches": []any{},
	})
}

// MatchHistoryVersion returns the Version handleMatchHistory will serve for this player.
// Exported so a push can name the same number the document carries.
func MatchHistoryVersion(id string) int64 {
	// Namespaced key: progressionVersionFor is keyed by id, so "mh:"+id gives this
	// resource its own independent counter without a second map.
	return progressionVersionFor("mh:"+id, "mh1-empty")
}

// missionInfo builds FPlayerProgression.MissionInfo — the native mission payload.
//
// WHY THIS EXISTS (2026-08-13). The lobby gates BOTH the missions surface and the
// news/announcement banner carousel behind UMissionsModel::bAllMissionLoaded, and that
// flag is only written by UMissionsModel::OnMissionAssetLoaded (impl base+0x56F3ED0,
// fold 1) once every UMissionModel in the model has a non-null MissionAsset. The DESIGNED
// feed for that is replication: ALokiPlayerState_Missions is an Actor whose Missions and
// FinalMissionProgress are both CPF_Net|CPF_RepNotify, and MEASURED live in the lobby there
// are ZERO instances of it (only the CDO) — so at the menu that path can never start.
//
// The HTTP door is this key. MEASURED (UHT FStructParams/FPropertyParams tables in
// dumps/tutorial-hero, .rdata 100% readable): FMissionInfo appears as a UPROPERTY in exactly
// THREE places image-wide — a UFunction parameter (ALokiPlayerState_Missions::SetMissionProgress,
// which is Final|Native|Public|BlueprintCallable with NO Net flags, i.e. locally callable,
// unlike its sibling ServerAddMissionProgress which IS a server RPC), FPlayerProgressionGameServer,
// and FPlayerProgression::MissionInfo at offset 0x68 — a top-level member of the document THIS
// handler already serves. The ingester at 0x585A570 copy-constructs the whole 0x178-byte
// FPlayerProgression into PM+0x90, MissionInfo included, by the same code path S83 already proved
// end-to-end for AccountPass. So this key rides an ingest that is MEASURED working; it was
// omitted until now only because its container types were unknown (see the comment above at the
// "Matches/MissionInfo/HeroMastery/... deliberately OMITTED" line, which this supersedes).
//
// ⚠ OPEN, and the honest limit of this probe: whether anything downstream hands
// PM+0x90.MissionInfo to SetMissionProgress is COVERAGE-BLOCKED — those .text pages read as
// zeros (undecrypted) in both available dumps. That is unknown, NOT negative.
//
// THE SCHEMA IS MEASURED, not guessed (UHT; sizeof closes exactly at 0x80):
//
//	FMissionInfo (4 props, SizeOf 0x80)
//	    MissionData       TArray<FMissionProgress>              @0x00
//	    Pools             TArray<FMissionPool>                  @0x10
//	    Completions       TMap<FPrimaryAssetId, int32>          @0x20
//	    MissionClaimData  TArray<FMissionClaimData>             @0x70
//	FMissionProgress  { ID FString; AssetId/PoolId FPrimaryAssetId; Complete/Failed bool;
//	                    ObjectiveProgress TArray<FMissionObjectiveProgress>;
//	                    MillisUntilExpiry int64; Expiry/GrantedAt FDateTime }
//	FMissionObjectiveProgress { ObjectiveName FName; Progress/MaxProgress/StartingProgress float;
//	                    Context TArray<FString>; InitialArmoryContext TArray<FPrimaryAssetId>;
//	                    Complete/Failed bool }
//	FMissionPool      { PoolId FPrimaryAssetId; MillisUntilNewMission int64; NewMissionTime FDateTime }
//
// ⚠⚠ THE ASSET IDs BELOW ARE THE REAL ONES, AND handlePutMission's ARE NOT.
// FPrimaryAssetId serializes as "Type:Name". The NAME is NOT the package name — these data
// assets override GetPrimaryAssetId() with a short name. GROUND TRUTH is missions_fix's own
// AssetManager enumeration: it calls GetPrimaryAssetIdList(Mission|MissionPool) and reads the
// FName straight out of each FPrimaryAssetId (missions_fix.cpp:181-186 TypeFromPAFS +
// GetFNameStr), then writes it verbatim into the manifest it POSTs us. Live readback of
// GET /revival/missions/manifest (330 entries):
//
//	{"mission":"ArmoryDaily_PlayAGame","objective":"PlayAGame","max":1,"pool":"DailyChallenge"}
//
// So the correct ids are Mission:ArmoryDaily_PlayAGame and MissionPool:DailyChallenge.
// handlePutMission below still sends "Mission:DA_Mission_ArmoryDaily_PlayAGame" and
// "MissionPool:DA_MissionPoolDailyEasy" — BOTH names are wrong (spurious DA_Mission_/
// DA_MissionPool prefix, and DailyEasy is not even this mission's pool), which is a strong
// candidate for why that route has never moved anything. Deliberately NOT fixed in the same
// build: single-variable changes only.
//
// Completions and MissionClaimData are OMITTED. Their types are known now, but absent is safe
// under the validity model (UE ignores unknown keys; only a MATCHED key with a WRONG type
// rejects the whole document) and omitting them keeps the surface minimal.
// missionInfo builds FPlayerProgression.MissionInfo from the OFFLINE MISSION CATALOG
// (missions_catalog.go), which is derived from the game's own mission data assets. The
// shim-supplied manifest is NO LONGER USED here — see missions_catalog.go for the measured
// reasons it was dropped. The manifest endpoints still exist for the shim and the admin
// panel; they simply no longer feed this document.
//
// Progress still comes from the same per-objective composite store the shim used
// ("<mission>/<objective>"), so any progress already recorded keeps applying wherever the
// catalog's names agree with it.
//
// See the block comment on handleGetProgression for WHY this key matters: it is the HTTP
// door that populates the native mission model, opens UMissionsModel::bAllMissionLoaded,
// and with it the lobby banner carousel — all with no shim and no .text write.
func (s *Service) missionInfo(now time.Time) (map[string]any, string) {
	const dayMillis = int64(24 * 3600 * 1000)
	expiry := now.Add(24 * time.Hour)
	expiryStr := expiry.Format(time.RFC3339)
	grantedStr := now.Format(time.RFC3339)

	progress := s.missionObjectives()

	// AGS_MISSION_POOLS — comma-separated pool allowlist; empty (the default) serves every
	// pool. DIAGNOSTIC ONLY: it exists so a run can be narrowed to a known-good subset when
	// the client accepts fewer missions than we serve. Leave it UNSET in normal operation.
	var keepPool map[string]bool
	if allow := strings.TrimSpace(os.Getenv("AGS_MISSION_POOLS")); allow != "" {
		keepPool = map[string]bool{}
		for _, p := range strings.Split(allow, ",") {
			if p = strings.TrimSpace(p); p != "" {
				keepPool[p] = true
			}
		}
		log.Printf("missions: AGS_MISSION_POOLS=%q active — serving only those pools", allow)
	}

	missionData := make([]any, 0, len(missionCatalog))
	poolSeen := map[string]bool{}
	var poolOrder []string
	// digest covers ONLY stable content (missions, objectives, maxes, pools, progress) —
	// deliberately NOT the timestamps below, which change every request and would otherwise
	// bump Version on every poll and re-trigger the ingester forever.
	h := fnv.New64a()

	for _, name := range catalogMissionNames() {
		c := missionCatalog[name]
		if c.Debug {
			continue // UMissionModel.IsDebugOnly exists; don't hand the client debug content
		}
		if keepPool != nil && !keepPool[c.Pool] {
			continue
		}

		objs := make([]any, 0, len(c.Objectives))
		allDone := len(c.Objectives) > 0
		for _, o := range c.Objectives {
			max := o.Max
			if max <= 0 {
				max = 1
			}
			prog := progress[compositeKey(name, o.Name)]
			if prog > max {
				prog = max
			}
			done := prog >= max
			if !done {
				allDone = false
			}
			objs = append(objs, map[string]any{
				"ObjectiveName":    o.Name,
				"Progress":         prog,
				"MaxProgress":      max,
				"StartingProgress": 0.0,
				"Complete":         done,
				"Failed":           false,
				// Context / InitialArmoryContext omitted — absent is safe.
			})
			fmt.Fprintf(h, "%s/%s=%g/%g;", name, o.Name, prog, max)
		}

		md := map[string]any{
			"ID":                "revival-" + name,
			"AssetId":           "Mission:" + name,
			"Complete":          allDone,
			"Failed":            false,
			"ObjectiveProgress": objs,
			"MillisUntilExpiry": dayMillis,
			// FDateTime imports ISO-8601. Verified live on this client: the banner probe's
			// "2020-01-01T00:00:00Z" read back as ticks 637134336000000000.
			"Expiry":    expiryStr,
			"GrantedAt": grantedStr,
		}
		// AGS_MISSION_NO_POOLID=1 — DIAGNOSTIC: omit PoolId from every MissionData entry while
		// leaving Pools[] intact. Tests whether serving a PoolId for a pool the client does not
		// consider grantable is what causes rejection. MEASURED motivation: of 105 missions that
		// carry a declared PoolId only 11 are accepted, and those 11 are exactly the ones whose
		// pool has a PoolGroupId (daily/weekly); the 218 missions we serve WITHOUT a PoolId are
		// accepted at 53%. Leave UNSET in normal operation — it breaks the modal's grouping.
		if c.Pool != "" && os.Getenv("AGS_MISSION_NO_POOLID") != "1" {
			md["PoolId"] = "MissionPool:" + c.Pool
			if !poolSeen[c.Pool] {
				poolSeen[c.Pool] = true
				poolOrder = append(poolOrder, c.Pool)
			}
		} else if c.Pool != "" {
			// still advertise the pool in Pools[] so only the per-mission PoolId varies
			if !poolSeen[c.Pool] {
				poolSeen[c.Pool] = true
				poolOrder = append(poolOrder, c.Pool)
			}
		}
		missionData = append(missionData, md)
	}

	sort.Strings(poolOrder)
	pools := make([]any, 0, len(poolOrder))
	for _, p := range poolOrder {
		pools = append(pools, map[string]any{
			"PoolId":                "MissionPool:" + p,
			"MillisUntilNewMission": dayMillis,
			"NewMissionTime":        expiryStr,
		})
		fmt.Fprintf(h, "pool:%s;", p)
	}

	digest := fmt.Sprintf("mi3-%d-%d-%x", len(missionData), len(pools), h.Sum64())
	return map[string]any{"MissionData": missionData, "Pools": pools}, digest
}

func (s *Service) handlePutMission(w http.ResponseWriter, r *http.Request) {
	// The PUT carries an EMPTY body (Content-Length 0) â€” it is a fire-and-forget
	// "reconcile my mission progress" trigger (exe: ServerAddMissionProgress /
	// SetMissionProgress), not a claim with a payload.
	//
	// Response model = `MissionData` (exe FName cluster, block 96). The OLD note
	// here said the Missions modal blocker was the AssetManager Track A gate â€” that
	// was based on the prior session's hypothesis. END-OF-2026-06-29 RE chain
	// proved otherwise: AddDynamicAsset registrations don't move the modal. The
	// real chain is:
	//   modal categories iterate PoolAsset[] -> GetPrimaryAssetIdFromClass(P) ->
	//     UMissionsModel.GetActive/GetClaimableMissionModel(id)
	//   which iterates a TSet at UMissionsModel+0x30 holding UMissionModel* with
	//     PoolId field at +0x40. findptr on UMissionModel CDO vtable returns
	//     ONLY the CDO â€” NO live UMissionModel UObjects exist anywhere in the
	//     process. The pipeline waits for the server to populate them.
	//   OnPSMissionsUpdated (FName 0x0058FF4F) fires when server pushes the data;
	//   CreateMissionModelFromFinalProgress (0x0058FEE1) is the factory.
	//
	// Hypothesis: this PUT's response (or a sibling endpoint we haven't found)
	// carries the per-pool mission data the client deserializes into
	// UMissionModels. The MissionData struct's NamePool-clustered field names
	// (around the struct's own FName id 0x006002E0 in block 96 / 98) include:
	//   Completions / Completions_Key (TMap)
	//   TrackIDToClaimableRewards / _Key (TMap)
	//   Pools (TArray or TMap â€” type unconfirmed)
	//   NewMissionTime (DateTime â€” the "year 0" warning source)
	//   MillisUntilNewMission (int64)
	//   PoolId (FPrimaryAssetId, per-pool field)
	//   GrantedAt / Expiry / MillisUntilExpiry (DateTime, int64)
	//   Progress / MaxProgress / StartingProgress (int)
	//   Failed / Complete (bool)
	//   ObjectiveProgress / ObjectiveName (TMap, string)
	//   InitialArmoryContext
	//
	// The validity rule still applies: an absent field is safe; a wrong-typed
	// matched field rejects the whole doc. We add fields in dependency order,
	// most-confident-types first, and observe Loki.log on each rebuild for
	// "Deserialization failure" / "Invalid response received". One pool entry
	// for DA_MissionPoolDailyEasy is the smoke-test target â€” if the Dailies
	// category renders ANYTHING on the next modal open, the chain is correct
	// and we iterate to add the other 12 pools.
	now := time.Now().UTC()
	nextRefresh := now.Add(24 * time.Hour)
	expiry := now.Add(7 * 24 * time.Hour)
	// FPrimaryAssetId in UE5 JSON serializes as "Type:Name" string.
	poolEntry := map[string]any{
		"PoolId":            "MissionPool:DA_MissionPoolDailyEasy",
		"MissionAssetId":    "Mission:DA_Mission_ArmoryDaily_PlayAGame",
		"GrantedAt":         now.Format(time.RFC3339),
		"Expiry":            expiry.Format(time.RFC3339),
		"MillisUntilExpiry": int64(7 * 24 * 3600 * 1000),
		"Progress":          0,
		"MaxProgress":       1,
		"StartingProgress":  0,
		"Failed":            false,
		"Complete":          false,
		"ObjectiveProgress": map[string]any{},
	}
	writeJSON(w, map[string]any{
		"Completions":               map[string]any{},
		"TrackIDToClaimableRewards": map[string]any{},
		"NewMissionTime":            nextRefresh.Format(time.RFC3339),
		"MillisUntilNewMission":     int64(24 * 3600 * 1000),
		// Pools FProperty has 5 hits across classes with ElementSizes 0x10, 0x18,
		// 0x28, 0x50, 0x50 â€” the 0x50 ones are full TMap headers. On MissionData
		// the field type is unconfirmed; we send a TMap<FPrimaryAssetId, PoolData>
		// shape (UE5 JSON encodes TMap<FName-keyed> as a JSON object). If the
		// actual type is TArray UE will silently ignore this Pools key (unknown
		// field â†’ no error). If wrong-typed match, the whole doc rejects with
		// "Deserialization failure" in Loki.log.
		"Pools": map[string]any{
			"MissionPool:DA_MissionPoolDailyEasy": poolEntry,
		},
	})
}

// tutorialMatchState is the ECoreGameMatchState reported in the served MatchInfo
// (MatchInfo.State / .StateEnum). This is the PRIMARY sweep knob for S62: if
// "InProgress" doesn't make the client travel to the local tutorial, flip to
// another state and rebuild ags â€” the client is already rapid-polling, so it
// picks up the new match/state on its next poll (no re-click needed as long as
// the same solo-start session is live).
//
// Valid values (usmap ECoreGameMatchState, ground truth):
//
//	PreHeroSelect HeroSelect Preallocate Allocating AwaitingReady InProgress
//	Deallocating Closing Unknown
//
// For a solo/local tutorial the plausible "travel now" states are HeroSelect,
// AwaitingReady, or InProgress. S53 walked Allocating/AwaitingReady with the
// (then-wrong) CoreGamePlayer shape and saw nothing; with the corrected shape
// this becomes a live variable again.
const tutorialMatchState = "InProgress"

// forceTutorialMatch, when true, reports the phantom tutorial match on
// /core-game/players even without a live solo-start. Normally FALSE â€” the match
// is armed by the client's own POST /startSoloMode (sets playerState.SoloMode).
// Flip to true only to probe the endpoint out of the solo-start flow (S53 showed
// that's inert out of flow), OR to keep an already-entered match reported across
// an ags hot-swap (SoloMode is transient and clears on restart). S62 ADDRESS
// PROBE: was true to keep the client pinned in the pre-game lobby across hot-swaps,
// but the client fires its travel/connect attempt ONCE at match ENTRY (using the
// address present then) and never re-fires from a polled update â€” so a fresh entry
// with the address already served is required. Back to FALSE: with SoloMode also
// transient (cleared on restart), this releases the client from the dead empty-
// address match back to the menu, ready for a clean START -> fresh entry that
// gets address 127.0.0.1:7777 on its very first match fetch.
// S65 PATH-1 HYBRID: TRUE so the idle client (which polls /core-game/players ~1/min) auto-fetches the match
// and its OWN parser builds a complete, self-consistent CoreGameMatchModel (bIsValid + MatchInfo) â€” far more
// robust than hand-writing the 1496-byte embedded MatchInfo struct. Paired with an EMPTY ConnectionDetails.address
// (below) so the client parks LOCALLY in the pre-game lobby (no DS connect/timeout), keeping the model valid;
// then the force-open shim opens LVL_Tutorial with the model already populated. (Revert to false for normal runs.)
// â˜… S108 (2026-08-04) â€” TRUE, for the FK-24 / FK-7 probe sittings. This is the S65/S90/S91 FORCE-OPEN
// config (TRUE + EMPTY ConnectionDetails.address), and it is set here for a reason worth recording:
// it removes the HUMAN from the run loop. The S107 recipe reaches the parked pre-game lobby via
// PLAY -> TUTORIALS -> BASIC TRAINING -> START, whose only backend effect is POST /startSoloMode
// setting playerState.SoloMode -- and handleCoreGamePlayer's gate is
// `forceTutorialMatch || SoloMode != ""`, so the flag substitutes for the button press exactly.
// MEASURED 2026-08-04: SoloMode has no other reader in the codebase (store.go:66 + this gate), so
// nothing else changes. The client's own ~1/min /core-game/players poll then arms the match, it
// fetches the match doc, builds a valid CoreGameMatchModel and parks locally on the loading screen --
// which is precisely the state tutorial_launch_fo.dll force-opens into. Set back to false to restore
// the plain interactive menu (a manual START then arms the match exactly as before).
// âš  LEFT AT false so a normal launch still gets the plain interactive main menu. Flip to TRUE for any
// FK-24 / FK-7 tutorial sitting -- configs\fk24-stage.ps1 pre-flights this exact value and refuses to
// run with a helpful message if it is false, so the tooling will point you back here.
const forceTutorialMatch = false // BASELINE (fully functional main menu, no DS connect). Set TRUE + EMPTY ConnectionDetails.address below for the FORCE-OPEN tutorial route (S91-S93 deploy/objective work). "127.0.0.1:7777" = DS route. S91 used the FORCE-OPEN tutorial route: set TRUE and pair with an EMPTY ConnectionDetails.address below (client parks locally; tutorial_launch_fo.dll opens LVL_Tutorial with the real gamemode). "127.0.0.1:7777" (baseline) = the DS/stub route. S91 spawned the TrainingQuest_Basics_* actors + built the BP-call primitive + started training via GameStateTryStartTraining; see docs/session-91-quest-spawn-bpcall.md + docs/tutorial-playability-plan.md.

// tutorialMatchID derives the (stable, greppable) match id for a player's phantom
// tutorial match. The match-details route recovers the player id back off it.
func tutorialMatchID(id string) string { return "match-" + id }

// matchStateVersion is the Version reported for the phantom match (CoreGamePlayer.Version
// and MatchInfo.Version). Computed once per ags process start, so EVERY hot-swap yields a
// higher value than the client last cached -> the client treats the match as "updated" and
// re-evaluates it (re-fetches + re-attempts travel with the CURRENT ConnectionDetails.address).
// S62: a constant Version:1 made the client latch the match once (with the then-empty address)
// and never re-travel when we later served a real address; a per-start bump fixes that without
// thrashing within a run (stable across the ~1/min polls of a single ags instance).
var matchStateVersion = time.Now().Unix()

// handleCoreGamePlayer answers GET /core-game/players/{id} â€” the "do I have an
// active match to rejoin?" heartbeat (rapid-polled while the client waits for a
// solo-start to allocate). GROUND TRUTH (usmap CoreGamePlayer, 4 props):
//
//	CoreGamePlayer { ID StrProperty; MatchID StrProperty; Version Int64Property;
//	                 CanDisassociate BoolProperty }
//
// There is NO nested MatchParticipant/MatchInfo/State/Address here (the S53
// "binary scan" model was wrong â€” those are separate structs). The client watches
// this endpoint for a NON-EMPTY MatchID; on transition it fetches the full match
// (MatchInfo) from the match route and travels. So the whole job here is: report
// an empty MatchID when idle, and a real MatchID (+ bumped Version) once a match
// is armed (POST /startSoloMode set SoloMode). This corrects the pre-S62 handler,
// which returned an invented blob where only CanDisassociate matched -> the client
// always parsed MatchID="" -> "no match" -> never escalated (the missing travel).
func (s *Service) handleCoreGamePlayer(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	st := s.store.get(id)
	active := forceTutorialMatch || (st != nil && st.SoloMode != "")

	resp := map[string]any{
		"ID":      id,
		"MatchID": "",
		"Version": 0,
		// CanDisassociate gates whether the client is ALLOWED to leave/abandon the
		// match. S62: returning false made the in-match "back to lobby" no-op (the
		// client believed it couldn't disassociate), pinning it on the pre-game screen.
		// true lets the player leave a match back to the menu.
		"CanDisassociate": true,
	}
	if active {
		// Non-empty MatchID + a non-zero Version signals "you have a match" so the
		// client escalates to fetch the match details (see handleCoreGameMatch). The
		// Version bumps each ags start so a hot-swap re-triggers the client's re-eval.
		resp["MatchID"] = tutorialMatchID(id)
		resp["Version"] = matchStateVersion
	}
	writeJSON(w, resp)
}

// handleCoreGameMatch answers GET /core-game/matches/{matchId} â€” the S62 PROBE for
// the match-details fetch the client makes once /core-game/players reports a
// MatchID. Returns the usmap MatchInfo model for a LOCAL solo tutorial. Route is a
// best guess (see the Register comment); if wrong it never fires and capture.log
// shows the real route.
func (s *Service) handleCoreGameMatch(w http.ResponseWriter, r *http.Request) {
	matchID := r.PathValue("matchId")
	id := strings.TrimPrefix(matchID, "match-")
	if id == matchID { // not our prefix â€” fall back to the JWT subject
		if sub := subjectFromBearer(r.Header.Get("Authorization")); sub != "" {
			id = sub
		}
	}
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildTutorialMatchInfo(matchID, id, display, s.selectedHero(id)))
}

// tutorialMapName is the map the client should load for the tutorial. The
// force-open route used the full package path; matchmaking configs may use a
// short name instead â€” if the client travels to the wrong/no map, this is the
// first field to adjust (watch Loki.log "Browse"/"LoadMap").
const tutorialMapName = "/Game/Loki/Maps/Tutorial/LVL_Tutorial"

// buildTutorialMatchInfo builds the usmap MatchInfo (19 props) for a LOCAL solo
// tutorial match. KEY for local (non-DS) travel: ConnectionDetails.address is
// EMPTY â€” there is no dedicated server for the tutorial, so an empty address
// should signal a local map load rather than a NetConnection (the client made
// ZERO NetConnection attempts in S61, favoring local travel). GameConfig carries
// the map/mode/solo-start-position; StateEnum/State carry the lifecycle state
// (tutorialMatchState). Field names/types per usmap MatchInfo + CoreGameMatchGameConfig
// + CoreGameServerInfo; unmatched keys are ignored, a wrong-typed matched key trips
// "Deserialization failure" (LogJson names it) â€” kept minimal to reduce that surface.
func buildTutorialMatchInfo(matchID, id, display, heroAssetId string) map[string]any {
	now := time.Now().UTC().Format(time.RFC3339)
	gameConfig := map[string]any{
		"MapName":               tutorialMapName,
		"GameMode":              "tutorialNew",
		"ServerCulture":         "en",
		"CanAlwaysDisassociate": true,
		"MaxHeroDuplicates":     1,
		"RequiresDropLeader":    false,
		"MaxTeamSize":           1,
		"SoloModeStartLocation": 0,
	}
	// MatchParticipant (usmap, 17 props) â€” the local player's entry (PlayerInfo).
	playerInfo := map[string]any{
		"ID":           id,
		"TeamID":       0,
		"PartyId":      "party-" + id,
		"PickOrder":    0,
		"DisplayName":  display,
		"HeroAssetID":  heroAssetId,
		"LockedIn":     true,
		"IsDropLeader": true,
		"IsRanked":     false,
		"AccountLevel": 1,
	}
	// CoreGameServerInfo (usmap, 6 props). S62 ADDRESS PROBE: empty address parked
	// the client in the pre-game lobby ("Attempting to travel to Match: Address:''")
	// â€” the menu route travels by CONNECTING to a server, not a local map load. So
	// serve a loopback DS address and watch whether the client fires a real
	// NetConnection to it (LogNet/StatelessConnect). Nothing is listening on 7777
	// yet â€” the connect ATTEMPT is the diagnostic; a working DS is the follow-up.
	connectionDetails := map[string]any{
		// S65 PATH-1 HYBRID used EMPTY address (client builds the model but parks locally â€” no DS connect).
		// S74 B2: back to the HYBRID empty address for the force-open route (client builds a valid
		// CoreGameMatchModel + parks locally in the pre-game lobby; force-open then travels to LVL_Tutorial
		// with that valid model in place â†’ no revert, gamemode fully inits). Set to "127.0.0.1:7777" for the DS route.
		// S76: reverted to the menu/force-open baseline (empty) after the DS cheat-lever experiment
		// concluded (docs/session-76-ds-cheat-lever.md). Set to "127.0.0.1:7777" to re-run the DS route.
		// S76 Route D (spectator free-cam of the live tutorial world) â€” working-tree experiment config.
		// S90: EMPTY for the FORCE-OPEN route (the only route that can complete tutorial objectives â€”
		// TrainingQuest_Basics_Base.OnObjectiveComplete is FUNC_BlueprintAuthorityOnly, so the client must be
		// the authority; see docs/tutorial-playability-plan.md). Client builds a valid CoreGameMatchModel and
		// parks locally; tutorial_launch_fo.dll then opens LVL_Tutorial with the real gamemode.
		// Set back to "127.0.0.1:7777" for the DS/stub route.
		// â˜… S107 (2026-07-27) â€” EMPTY for the FORCE-OPEN route. MEASURED this session:
		// after the FParty.State fix above unblocked the START button, the client POSTed
		// /startSoloMode ONCE (capture.log #1980, 22:26:22) â€” the backend armed a MatchID,
		// the client fetched this match doc, and then tried to travel to a DS on
		// 127.0.0.1:7777 that is NOT RUNNING. It never got there, but /core-game/players
		// now reports a non-empty MatchID forever, so the client believes it is ALREADY IN
		// A MATCH and every subsequent START is a silent no-op (zero egress, zero log).
		// An empty address is what makes the client build a valid CoreGameMatchModel and
		// PARK LOCALLY instead (docs/endpoints.md:50 "Local tutorial = EMPTY address"),
		// which is the state tutorial_launch_fo.dll then force-opens into.
		// Set back to "127.0.0.1:7777" ONLY for the DS/stub route.
		"address":      "",
		"ServerID":     "revival-tutorial-ds-0001",
		"MachineID":    "revival-local",
		"RegionID":     "na",
		"FleetID":      "revival-fleet-0001",
		"RoutingToken": "",
	}
	return map[string]any{
		"ID":                matchID,
		"Version":           matchStateVersion,
		"Created":           now,
		"GameConfig":        gameConfig,
		"State":             tutorialMatchState,
		"StateEnum":         tutorialMatchState,
		"GameVersion":       "release2.4.live-156430-shipping",
		"PlayerInfo":        playerInfo,
		"QueueID":           "tutorialNew",
		"Region":            "na",
		"ConnectionDetails": connectionDetails,
		"OwnerID":           id,
	}
}

// handleCoreGameRegions returns the region list the latency manager pings (fixes the menu's
// "??? - ms" + missing ST_ServerLocations). STAGED probe: one region pointed at the local
// backend so the ping can resolve. Fields are the confirmed model names (RegionName/RouteName)
// plus a superset of plausible host/port/display keys (UE ignores unmatched, matches
// case-insensitively).
//
// 2026-06-29 â€” PROBE #2: object-envelope. Live readback (Loki.log):
//
//	LogJson: Warning: JsonObjectStringToUStruct - Unable to parse json=[[{"Address":...}]]
//	LogLokiPlatformQuery: Error: Deserialization failure on Query: GET .../core-game/regions
//
// UE's warning format is literally `json=[%s]` (outer brackets are part of the log format,
// not the body) so the body the server emitted was the single-wrapped bare array
// `[{...}]\n`. Per the validity model documented at the top of menu.go ("a bare [] hits
// Deserialization failure â€” array vs. object struct"), the target UStruct is an object,
// so a bare TArray top-level fails. PROBE #1's "returned as a bare array" comment was
// wrong about what the call site expects. Flipping to an object envelope with the obvious
// field name (`Regions`, matching `GetRegions`'s return). If "Regions" is the wrong field
// name the symptom will flip from Deserialization failure â†’ Invalid response received
// (predicate fails), which would name the next probe.
// ★★★★★ 2026-08-15 (S121) — THE PAYLOAD ABOVE WAS FLAT AND THE MODEL IS NESTED. FIXED.
//
// FK-5 reverse-engineered this end to end on 2026-07-27 (`docs/fk5-latency-subsystem-re.md`) and
// the fix was never shipped. From the game's own `Binds.Cache` bind table — real C++ decls, so
// they settle container types that `schema.txt`/the usmap render wrong:
//
//	struct FRegionHostList { TArray<FRegionHost> Regions; FString ETag; };            // 32 B
//	struct FRegionHost     { FString Name; FString Addr; int Port; bool CanExclude;
//	                         TMap<FString, FRegionRoute> Routes; };                   // 0x78 B
//	struct FRegionRoute    { bool Enabled; bool IsAccelerator; FString Host; int Port;
//	                         FString PingHost; int PingPort; bool RequiresToken; };   // 0x38 B
//
// ⚠⚠ **`PingHost`/`PingPort` live inside `FRegionRoute`, which lives inside `FRegionHost.Routes` —
// a TMap we had NEVER SENT.** Our flat body parsed fine into ONE region with an EMPTY Routes map,
// and the measurer-creation loop iterates `Routes`. Zero routes ⇒ zero `ULatencyMeasurer`s ⇒ zero
// pings ⇒ the `??? — ms` row and the `ST_ServerLocations['']` lookup. Confirmed independently in
// the disassembly: the loop at `fn 0x57DDCA0` advances regions with `add rbx,0x78`
// (= sizeof FRegionHost) and indexes routes at stride 0x50 (= TPair<FString,FRegionRoute>).
//
// ⇒ This is the same failure shape as the old `RegionName`/`RouteName` guesswork: the field names
// were plausible and the NESTING was wrong, so nothing errored — it just silently produced an
// empty container. **A parse that succeeds is not a parse that populated anything.**
//
// ★ HOW IT RESURFACED, which is the interesting part: the S121 feature-toggle sweep left two keys
// (`ServerSelectRegionRoutes`, `ServerSelectNetworkAcceleration`) reading "never evaluated". Their
// widget `WBP_UI_RegionSelect_Entry` is the PER-ROUTE row, and with zero routes no row is ever
// constructed — so the region-select modal opens EMPTY (screenshot-confirmed) and those gates can
// never run. The toggle readout pointed straight at a two-session-old unshipped backend fix.
//
// ⚠ Scope, stated honestly: creating routes creates MEASURERS, and FK-5 §7 records that "measurers
// are what the UI and any AllMeasurersReported gate actually read". The ping itself is a **UDP
// echo** (not ICMP — a port is specified, and UE's own diagnostics say ICMP takes no port) with a
// 5 s timeout, and we run **no UDP echo responder**, so a real latency NUMBER is NOT expected yet.
// Rows appearing is the prediction; `??? — ms` becoming a value is NOT.
//
// Knob: AGS_REGIONS_FLAT=1 restores the pre-S121 flat payload for a single-variable A/B.
func (s *Service) handleCoreGameRegions(w http.ResponseWriter, r *http.Request) {
	if os.Getenv("AGS_REGIONS_FLAT") == "1" {
		// The measured-broken control arm. Kept executable so the fix stays falsifiable.
		writeJSON(w, map[string]any{"Regions": []any{map[string]any{
			"RegionName": "na", "RouteName": "na", "DisplayName": "Local",
			"Host": "127.0.0.1", "PingHost": "127.0.0.1", "Address": "127.0.0.1",
			"Port": 443, "Enabled": true,
		}}})
		return
	}

	// One route, keyed by route name. The TMap key is what the UI shows as the route and what
	// GetRegionRoute(Region, Route) looks up; FMemberServerLatency carries Region + Route back.
	route := map[string]any{
		"Enabled":       true,
		"IsAccelerator": false,
		"Host":          "127.0.0.1",
		"Port":          443,
		"PingHost":      "127.0.0.1",
		"PingPort":      443,
		"RequiresToken": false,
	}
	// ★ `Name` IS THE ST_ServerLocations STRING-TABLE KEY, and that table is keyed by AWS REGION
	// CODES — not by free text. MEASURED from the shipped asset
	// (`tools/extractor/out/catalog/st/ST_ServerLocations.json`, TableNamespace ST_ServerLocations,
	// **38 keys**): us-east-1 "NA East (Virginia)", us-west-2 "NA West (Oregon)",
	// eu-west-1 "EU West (Ireland)", ap-northeast-2 "Asia Pacific (Seoul)", local-cluster (CJK), …
	//
	// Serving "na" got the region all the way to the UI — FK-5's P1 receipt fired
	// (`LogStringTable … ST_ServerLocations 'na'` instead of the historical '') — but the row then
	// rendered as **<MISSING STRING TABLE ENTRY>** because no such key exists. ⇒ the name must come
	// from the table's own vocabulary. Same lesson as the missions `InternalName` fix: the client
	// looks names up in a registry it already ships, so read the registry instead of inventing a key.
	//
	// Knob: AGS_REGION_NAME picks a different one (must be a real key from that asset).
	region := map[string]any{
		"Name": envOrDefault("AGS_REGION_NAME", "us-east-1"),
		"Addr": "127.0.0.1",
		"Port": 443,
		// ⚠⚠⚠ MUST BE TRUE. `CanExclude` is NOT advisory — it is a HARD INCLUSION GATE on the
		// measurer-creation loop. FK-5 decoded it at instruction level (`fn 0x57DDCA0`, gate at
		// `0x57DE016`) and called it "a hard gate nobody had seen":
		//
		//     for each FRegionHost R:
		//         if (R.CanExclude == 0) continue;      <-- skips the ENTIRE region
		//         for each (RouteName, Rt) in R.Routes: CreateMeasurer(...)
		//
		// S121 first served `false` — reading the name as "may the player exclude this region?"
		// and answering "no, it's our only one". The client reads it as "is this region eligible
		// for measurement?", so the whole region was skipped: correct payload, fully bound
		// (Regions.Num=1, Routes.Num=1, our own ETag echoed back), and STILL zero measurers.
		// ⇒ Another parse-succeeds-populates-nothing failure, and the third distinct one on this
		// single endpoint after the flat/nested bug. **Nothing in the log says a word about it.**
		"CanExclude": true,
		"Routes":     map[string]any{"default": route},
	}
	// ⚠⚠ THE ETAG MUST BE DERIVED FROM THE CONTENT, NOT A CONSTANT.
	// `FRegionHostList` carries its own `FString ETag`, and a constant one means a CHANGED payload
	// arrives under an UNCHANGED tag — the classic silent no-op. S121 hit this twice in one day:
	// once on client-config (fixed by folding the served extras into that eTag) and then AGAIN
	// here, within the hour, by hand-writing "supervive-revival-regions-1" and later editing
	// CanExclude underneath it. Hashing the body removes the failure mode instead of relying on
	// remembering to bump a literal.
	regions := []any{region}
	body, _ := json.Marshal(regions)
	sum := sha256.Sum256(body)
	writeJSON(w, map[string]any{
		"Regions": regions,
		"ETag":    "supervive-revival-regions-" + hex.EncodeToString(sum[:6]),
	})
}

func (s *Service) handleMailboxConfigVersion(w http.ResponseWriter, r *http.Request) {
	// Field recovered from exe FName pool: MailboxConfigVersion. Probe the common
	// camelCase spellings as ints (safe â€” a matched int key deserializes, unmatched
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
// emit a superset of plausible field names (PascalCase â€” UE matches case-insensitively)
// covering both the AccelByte-style fields (PartyId/LeaderId/Members/Invited/
// CrossplayEnabled/CreatedAt) and the Theorycraft reservation-style ones (PartyMembers/
// RemovedPartyMembers/TeamNum). Unmatched keys are ignored; the player appears as the
// sole JOINED leader/member. Relaunch readback (LogPartyManager â€” the "player not in
// party" warning clearing, and whether the tutorial button now acts) tells us which
// fields landed and what to trim.
func (s *Service) handleGetParty(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	// Seed the selected activity from the client's own ?defaultQueue=<q> hint (only if the
	// player hasn't picked one yet) so the party always carries a target queue â€” the
	// "must always have one activity selected" invariant. Falls back to "default" below.
	if dq := r.URL.Query().Get("defaultQueue"); dq != "" && s.store.get(id).SelectedQueueID == "" {
		s.store.update(id, func(st *playerState) { st.SelectedQueueID = dq })
	}
	writeJSON(w, buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id), s.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion()))
}

// selectedQueue returns the player's persisted selected matchmaking activity/queue id,
// falling back to "default" so the party always carries a non-empty TargetQueueID (the
// client's Comp_MainMenu_QueueController refuses to modify activity when none is selected).
func (s *Service) selectedQueue(id string) string {
	if q := s.store.get(id).SelectedQueueID; q != "" {
		return q
	}
	return "default"
}

// defaultHeroAssetId is the hunter the party slot renders before the player has
// picked one â€” the same default (owned) hero the inventory marks IsDefault
// ("alchemist"). Seeding it means the center shows a real hunter instead of the
// "?" placeholder on first login; a subsequent pick overrides it (persisted).
const defaultHeroAssetId = "Hero:alchemist"

// selectedHero returns the player's persisted selected hunter PrimaryAssetId,
// falling back to the default owned hero so the party-slot preview always has a
// valid, owned id to render (never the UnknownHero "?").
func (s *Service) selectedHero(id string) string {
	if h := s.store.get(id).SelectedHeroAssetId; h != "" {
		return h
	}
	return defaultHeroAssetId
}

// selectedCosmetic returns the saved skin bundle ("HeroCosmeticsBundle:<name>") for the
// player's currently-selected hero, or "" if none. It is NO LONGER served on the party
// member (proven inert 2026-07-09 â€” see handleSetPartyMember): the client ignores the
// echoed member cosmetic. Retained only so buildSoloParty's signature is unchanged and a
// future client-side shim can reuse the resolution; buildSoloParty discards the value.
func (s *Service) selectedCosmetic(id string) string {
	// heroCosmetic looks up the map UNDER THE LOCK â€” a live read here raced update()
	// (concurrent map read/write, the crash class that took down ags in loadoutDoc).
	return s.store.heroCosmetic(id, s.selectedHero(id))
}

// handleGetPartyDetail answers GET /party/parties/{partyId} â€” the full party object the
// client polls (380Ã—/session) after learning its partyId. Hitting the {} stub leaves the
// PARTY panel slots empty. We rebuild the same solo party; the player id is recovered from
// the minted partyId ("party-<playerId>"), falling back to the JWT sub.
func (s *Service) handleGetPartyDetail(w http.ResponseWriter, r *http.Request) {
	partyID := r.PathValue("partyId")
	id := strings.TrimPrefix(partyID, "party-")
	if id == partyID { // not our prefix â€” fall back to the JWT subject
		if sub := subjectFromBearer(r.Header.Get("Authorization")); sub != "" {
			id = sub
		}
	}
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id), s.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion()))
}

// handleStartSoloMode answers POST /party/parties/{partyId}/startSoloMode?mode=&hero=&soloModeStartPosition=.
// S61: this is the actual tutorial launch call, reached only after the client-side native walls are down
// (login GameMode-vtable slot 285, and the TryStartSoloMode party-state gate). The client's
// Comp_MainMenu_QueueController.OnStartSoloModeComplete(bSuccess, MessageID, QueryContext) fires on this
// response: an empty {} is ACCEPTED (bSuccess=true, no deserialize error) but the TRAVEL is downstream
// (OnJoinQueueSuccess -> match-connect), so a clean 200 alone doesn't travel. We record SoloMode=<mode> on
// the player (so /core-game/players can report the local tutorial match to drive the travel â€” the next probe)
// and echo the party as the success body.
//
// NOTE (durable follow-ups): (1) the gate that gets us here needs PartyModel+0x558+0x18 == "default"/
// "Matchmaking"; currently satisfied by a live memory poke â€” the durable fix is populating that party JSON
// field (key not yet mapped). (2) The travel mechanism after solo-start is now via /core-game/players: it
// reports the real usmap CoreGamePlayer with a non-empty MatchID (S62), which should make the client fetch
// the match (handleCoreGameMatch) and travel locally. S61 saw no travel because that endpoint served an
// invented shape (empty MatchID); the corrected shape is the current single-variable probe.
func (s *Service) handleStartSoloMode(w http.ResponseWriter, r *http.Request) {
	partyID := r.PathValue("partyId")
	id := strings.TrimPrefix(partyID, "party-")
	if id == partyID { // not our prefix â€” fall back to the JWT subject
		if sub := subjectFromBearer(r.Header.Get("Authorization")); sub != "" {
			id = sub
		}
	}
	mode := r.URL.Query().Get("mode")
	hero := r.URL.Query().Get("hero")
	pos := r.URL.Query().Get("soloModeStartPosition")
	log.Printf("interactive: startSoloMode player=%s mode=%q hero=%q pos=%q", id, mode, hero, pos)
	s.store.update(id, func(st *playerState) { st.SoloMode = mode })
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id), s.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion()))
}

// queueIDs is the set of matchmaking queue ids we advertise to the client. The full known
// set (from WBP_ActivityPickerScreen.InitializeQueues' string constants) is:
//
//	default deathmatch practice dropin customgame bots tutorialNew training
//	armorydeathmath tournament
//
// DIAGNOSTIC TRIM (S60): Comp_MainMenu_QueueController.CanControlQueue loops over the current
// queues calling GetLevelGameFeatureUnlocked; with the served account level = 0, any level-gated
// queue (tournament/deathmatch/ranked) fails that loop -> CanControlQueue false -> every activity
// click errors "Unable to modify activity". Trim to the new-player / level-0 set (tutorials +
// practice + co-op) to test whether removing gated queues clears the modify block. If it does,
// the real fix is serving a high account level (unlocks all features) so the full set can return.
var queueIDs = []string{
	"tutorialNew", "training", "practice", "bots",
}

// matchmakingLastUpdated is a fixed, valid ISO8601 timestamp for the QueueInfo
// LastUpdated (FDateTime) field. Fixed (not time.Now) so the body is byte-stable across
// the ~1/s poll and the ETag honestly represents the content; a real date avoids the
// client's "DateTime in bad format (year 0)" parse warning.
const matchmakingLastUpdated = "2026-07-08T00:00:00Z"
const matchmakingETag = "revival-queues-v1"

// buildQueueDetails returns the QueueInfo.Queues array as QueueDetails structs.
//
// GROUND TRUTH CORRECTS THE USMAP: usmap QueueInfo lists Queues as ArrayProperty<StrProperty>,
// but the LIVE client rejected a string array with:
//
//	ImportText (Queues): Missing opening parenthesis: default
//	JsonValueToUProperty - Unable to import JSON string into QueueDetails property Queues
//	-> Deserialization failure on GET /party/matchmaking/info
//
// i.e. Queues is really ArrayProperty<StructProperty QueueDetails>. Each element is a
// QueueDetails{ID, IsRanked, IsSpecial, Config:QueueConfig} (usmap struct defs). Config
// carries the party-size limits the client validates the (solo) party against â€” MaxPartySize
// must be >=1 or the tile re-locks after resolving. Field names/types per usmap QueueDetails
// + QueueConfig; RankedSchedule (Map) / RankedRestrictionsSchedule (struct) are omitted and
// left at UE defaults (unmatched keys are ignored). Uniform config across queues is enough to
// unlock/select; per-queue tuning (ranked flags, real sizes) can follow if a mode needs it.
func buildQueueDetails() []map[string]any {
	out := make([]map[string]any, 0, len(queueIDs))
	for _, id := range queueIDs {
		out = append(out, map[string]any{
			"ID":        id,
			"IsRanked":  false,
			"IsSpecial": false,
			"Config": map[string]any{
				"MaxTeamSize":       3,
				"MaxPartySize":      3,
				"MaxHeroDuplicates": 1,
				"FillParties":       false,
				"RegionOverride":    "",
				"Priority":          0,
				"AllowNoFill":       true,
			},
		})
	}
	return out
}

// handleMatchmakingInfo answers GET /party/matchmaking/info with the QueueInfo model
// (Queues []QueueDetails, ETag string, LastUpdated DateTime). This list is what
// PartyModel.GetQueues() is built from; without it the ActivityPicker tiles stay locked
// and clicking a tutorial/mode is a silent no-op. See the route comment for the full trace.
func (s *Service) handleMatchmakingInfo(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"Queues":      buildQueueDetails(),
		"ETag":        matchmakingETag,
		"LastUpdated": matchmakingLastUpdated,
	})
}

// handleMatchmakingCustomGameModes answers GET /party/matchmaking/customGameModes with the
// CustomGameModeInfo model (usmap: Modes []string, ETag, LastUpdated) â€” the custom-game
// sibling of QueueInfo. Empty Modes is fine (no custom modes advertised); the typed shape
// just keeps the {} stub from tripping a deserialize error.
func (s *Service) handleMatchmakingCustomGameModes(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"Modes":       []string{},
		"ETag":        matchmakingETag,
		"LastUpdated": matchmakingLastUpdated,
	})
}

// handleSetPartyMember persists the hunter the player picked and echoes the updated
// solo party. Body is a SetPartyMemberRequest{ID, HeroAssetID, CosmeticsAssetID,
// LuxeSkinChroma, ...}. The player id is recovered from the minted partyId
// ("party-<playerId>"), falling back to the memberId path value / JWT sub.
//
// CAPTURE-CONFIRMED 2026-07-09 (this was a best-guess route since s48): clicking a skin
// in CUSTOMIZATIONâ†’SKIN fires
//
//	PUT /party/parties/party-<id>/members/<id>
//	{"iD":"<id>","heroAssetId":"Hero:Alchemist",
//	 "cosmeticsAssetId":"HeroCosmeticsBundle:AlchemistDefault_MAS","luxeSkinChroma":"",
//	 "ownedCosmeticsFeatures":[],"isReady":true,"customGameTeamId":0,"isPremiumSession":false}
//
// followed ~5s later by PUT /personalization/players/<id>/cosmeticsbundle/Hero:<name>
// (the debounced per-hero preference write, loadout.go).
//
// SKIN PERSISTENCE â€” BACKEND ROUTE CONCLUSIVELY CLOSED (2026-07-09). We tried persisting
// + serving the picked cosmeticsAssetId back on the party member. It is INERT: the client
// rebuilds the party member from the /party GET every poll and reads only heroAssetId,
// never the cosmetic. Direct proof in Loki.log â€” after equipping Mastery (member PUT
// carried AlchemistDefault_MAS, server echoed it), the party slot STILL loaded
// "HeroCosmeticsBundle:AlchemistDefault_STR": the GetDefaultCosmeticsBundleIdForHeroId
// fallback that both the party slot and the SKIN tab use whenever the member cosmetic is
// empty. That STR default is exactly why the SKIN tab always reverts to "Strawberry Bomb".
// Hunters persist because heroAssetId IS read back; skins cannot be driven from here. The
// working path is client-side: loadout_fix redirects GetDefaultCosmeticsBundleIdForHeroId (the
// shared fallback) to the saved skin (SOLVED 2026-07-09, docs/session-53-customization-persistence.md).
// So below we persist heroAssetId, and we ALSO record the body's cosmeticsAssetId into the per-hero
// preference map â€” NOT to echo it on the party member (inert), but to feed GET /revival/loadout
// immediately so the shim can flip its redirect to a freshly-picked skin without waiting on the
// ~5s-debounced cosmeticsbundle PUT.
func (s *Service) handleSetPartyMember(w http.ResponseWriter, r *http.Request) {
	// Resolve the player id (partyId is "party-<id>" for our solo party).
	id := strings.TrimPrefix(r.PathValue("partyId"), "party-")
	if id == r.PathValue("partyId") { // not our prefix
		if m := r.PathValue("memberId"); m != "" {
			id = m
		} else if sub := subjectFromBearer(r.Header.Get("Authorization")); sub != "" {
			id = sub
		}
	}

	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	hero := heroAssetIDFromBody(body)
	cosmetic := cosmeticAssetIDFromBody(body)
	if hero != "" || cosmetic != "" {
		s.store.update(id, func(st *playerState) {
			if hero != "" {
				st.SelectedHeroAssetId = hero
			}
			// Seed the per-hero skin preference (feeds GET /revival/loadout, which the loadout_fix
			// shim polls to keep its GetDefaultCosmeticsBundleIdForHeroId redirect in sync).
			//
			// SEED-ONLY (2026-07-19): never OVERWRITE an established per-hero skin from this member
			// sync. The member body carries the client's *equipped* cosmetic, which is STALE for any
			// hunter whose client-side equip is broken â€” precisely the hunters the shim exists to fix
			// (Brall/Eluna). This PUT fires on every click, ~0.2s AFTER the shim's authoritative
			// POST /revival/loadout/cosmetic; when it overwrote, it reverted the just-picked skin back
			// to the old one, so "skins wouldn't switch / didn't carry over" for the stuck hunters.
			// The authoritative writers are the shim POST (the user's real widget selection) and the
			// client's explicit cosmeticsbundle PUT; the member sync may only seed a hero that has no
			// preference yet (so a fresh account still shows a skin before the first real pick).
			if hero != "" && cosmetic != "" {
				if st.HeroCosmeticsBundles == nil {
					st.HeroCosmeticsBundles = map[string]string{}
				}
				if _, set := st.HeroCosmeticsBundles[hero]; !set {
					st.HeroCosmeticsBundles[hero] = cosmetic
					st.LoadoutVersion++
				}
			}
		})
	}

	// Echo the updated party so the client's optimistic pick is confirmed by the server
	// state (and matches what the next GET /party/parties poll will return).
	display := displayNameFromBearer(r.Header.Get("Authorization"))
	writeJSON(w, buildSoloParty(id, display, s.selectedHero(id), s.selectedCosmetic(id), s.selectedQueue(id), s.loadoutDoc(id), s.store.partyVersion()))
}

// heroAssetIDFromBody extracts the selected hero as a "Hero:<name>" PrimaryAssetId string
// from a SetPartyMemberRequest body, tolerating both the string form ("Hero:xxx") and the
// UE struct-object form the client may serialize a PrimaryAssetId as
// ({"PrimaryAssetType":{"Name":"Hero"},"PrimaryAssetName":"xxx"} or {"type":"Hero","name":"xxx"}).
// Returns "" if no usable hero id is present (so a body without one is a no-op, not a wipe).
func heroAssetIDFromBody(body []byte) string {
	if len(body) == 0 {
		return ""
	}
	// Probe the field under either spelling; capture as raw so we can accept string|object.
	var req struct {
		HeroAssetID  json.RawMessage `json:"heroAssetId"`
		HeroAssetID2 json.RawMessage `json:"HeroAssetID"`
	}
	if json.Unmarshal(body, &req) != nil {
		return ""
	}
	for _, raw := range []json.RawMessage{req.HeroAssetID, req.HeroAssetID2} {
		if id := primaryAssetIDString(raw); id != "" {
			return id
		}
	}
	return ""
}

// cosmeticAssetIDFromBody extracts the picked skin bundle as a "HeroCosmeticsBundle:<name>"
// PrimaryAssetId string from a SetPartyMemberRequest body (wire key cosmeticsAssetId,
// capture-confirmed 2026-07-09), tolerating the same string|object forms as the hero.
// Used to feed the /revival/loadout redirect (see handleSetPartyMember) â€” NOT to echo the
// cosmetic on the party member. Returns "" when absent/empty.
func cosmeticAssetIDFromBody(body []byte) string {
	if len(body) == 0 {
		return ""
	}
	var req struct {
		CosmeticsAssetID  json.RawMessage `json:"cosmeticsAssetId"`
		CosmeticsAssetID2 json.RawMessage `json:"CosmeticsAssetID"`
	}
	if json.Unmarshal(body, &req) != nil {
		return ""
	}
	for _, raw := range []json.RawMessage{req.CosmeticsAssetID, req.CosmeticsAssetID2} {
		if id := primaryAssetIDString(raw); id != "" {
			return id
		}
	}
	return ""
}

// primaryAssetIDString normalizes a JSON PrimaryAssetId (string "Type:Name" or an object
// with type/name fields) to the "Type:Name" string form. Returns "" when the value carries
// no name (an empty PrimaryAssetId, which must NOT overwrite a real selection).
func primaryAssetIDString(raw json.RawMessage) string {
	if len(raw) == 0 {
		return ""
	}
	// String form: "Hero:alchemist".
	var str string
	if json.Unmarshal(raw, &str) == nil {
		if str = strings.TrimSpace(str); strings.Contains(str, ":") {
			return str
		}
		return ""
	}
	// Object form: tolerate the common UE PrimaryAssetId serializations.
	var obj struct {
		Type             string `json:"type"`
		Name             string `json:"name"`
		PrimaryAssetName string `json:"PrimaryAssetName"`
		PrimaryAssetType struct {
			Name string `json:"Name"`
		} `json:"PrimaryAssetType"`
	}
	if json.Unmarshal(raw, &obj) != nil {
		return ""
	}
	typ := obj.Type
	if typ == "" {
		typ = obj.PrimaryAssetType.Name
	}
	name := obj.Name
	if name == "" {
		name = obj.PrimaryAssetName
	}
	if typ == "" || name == "" {
		return ""
	}
	return typ + ":" + name
}

// buildSoloParty constructs the CUSTOM Theorycraft party model (NOT AccelByte V2). Probes
// #1 (flat superset) and #2 (faithful AccelByte V2 session) both deserialized cleanly but
// were NOT adopted - wrong field family. The UTF-16 endpoint table in the exe proves /party
// is a bespoke Theorycraft surface (/party/players/, /party/parties/, /joinQueue,
// /startSoloMode, /setTargetQueues, /reconcile, ...) under UPartyManager. Confirmed party
// JSON fields (FName pool, camelCase): partyId, leader, members, invitees, invitationToken;
// member fields: userId/memberId/id, displayName, inQueue, ready, region. This validated
// live: with it, "player not in party" dropped 1002->2 and the PARTY panel renders.
//
// heroAssetId is the member's SELECTED hunter (a "Hero:<codename>" PrimaryAssetId). The
// client deserializes the member into a PartyMemberModel whose HeroAssetID drives the
// main-menu party-slot / center preview actor: an empty/invalid id shows the "?" placeholder
// (BP_LokiHeroSelectPreview_UnknownHero), a valid owned id renders that hunter. Field name is
// camelCase heroAssetId (UStruct field HeroAssetID; UE matches JSON keys case-insensitively);
// PrimaryAssetId accepts the "Type:Name" string form (proven by the owned-inventory AssetIds).
// loadout is the member's PersonalizationLoadout (the loadoutDoc from loadout.go). See the
// AVATAR RENDER block below for why it is served here; pass nil to omit it.
func buildSoloParty(id, display, heroAssetId, cosmeticsAssetId, targetQueue string, loadout map[string]any, partyVersion int64) map[string]any {
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
		// The selected hunter. Both key spellings are supplied as a superset probe
		// (UE ignores unmatched keys, matches matched ones case-insensitively) so the
		// member's HeroAssetID populates regardless of which the client reads.
		"heroAssetId": heroAssetId,
		"heroAssetID": heroAssetId,
	}
	// The member's CosmeticsAssetID is intentionally NOT served. CONCLUSIVELY INERT
	// 2026-07-09 (see handleSetPartyMember): the client rebuilds the member from this GET
	// each poll and never reads the cosmetic back, so Loki.log shows the party slot loading
	// the GetDefaultCosmeticsBundleIdForHeroId fallback (AlchemistDefault_STR = "Strawberry
	// Bomb") regardless of what we echo. Serving it can't help the skin display and only
	// risks the 2026-07-08 lock, so we drop it. Skin persistence needs a client-side shim.
	_ = cosmeticsAssetId

	// ---- AVATAR RENDER (2026-07-19) ----
	// The equipped AVATAR selects fine but its image never draws on any player-card surface
	// (party row, top-right card, the picker's preview card). Selection was proven healthy
	// first, so this is purely a render gap:
	//   - the click fires POST /personalization/players/{id}/slotcosmetics {"slot":"Avatar",...}
	//   - the store persists it, and the CLIENT'S OWN presence blob carries
	//     "avId":"SlotCosmetics:AVATAR_AboveItAll" and tracks clicks live (docs/capture.log
	//     ~02:22:29-02:22:36). So the id is correct in the PersonalizationManager.
	//
	// Root cause (RE'd 2026-07-19, live read-only RPM against the running client):
	// the avatar widgets never read the PersonalizationManager. WBP_UI_Social_PlayerAvatarIconV2_C
	// gates on IsValidSoftClassReference(TargetAvatarAsset) and, when it fails, deliberately calls
	// Image_Avatar.SetBrushResourceObject(TX_Transparent) â€” the blank we see is painted on purpose.
	// TargetAvatarAsset is filled by BPFL_Social_C::DetermineSocialInfoForPlatformPlayer, which for
	// a valid+online party member reads
	//     PartyMember.PersonalizationLoadout.SlotCosmeticsEntries
	//   -> PersonalizationManager::FindSlotCosmeticEntry(entries, GetAvatarSlotName())
	// i.e. the card sources the avatar from the PARTY MEMBER's loadout, not the personalization
	// manager. We never served that field, so it was zeroed. Confirmed live on both
	// PartyMemberModel instances: PersonalizationLoadout (+0x0190) all-zero, Version = -1,
	// SlotCosmeticsEntries Num=0.
	//
	// NOT a re-run of the closed skin experiment above: that one was scoped to the member's
	// CosmeticsAssetID (hero skins). PersonalizationLoadout is a DIFFERENT field and had never
	// been served. Reuses loadoutDoc() so the wire shape stays in one place; its layout was
	// independently confirmed against live RPM (ScriptStruct PersonalizationLoadout @0x145E5806A60:
	// ID@0x00, Version@0x10, EmoteIds@0x18, TitleIds@0x28, SlotCosmeticsEntries@0x38, ...) â€” one of
	// the rare cases where the extracted usmap matched.
	//
	// TYPE SAFETY: SlotCosmeticsEntries is an ARRAY of {slot, asset} structs. Per the validity model
	// (internal/menu/menu.go) an unmatched key is ignored but a MATCHED key with the wrong container
	// type rejects the whole doc â€” which here would break the party panel, not just the avatar. The
	// shape below comes from loadoutDoc(), which already emits the array form.
	if loadout != nil {
		member["personalizationLoadout"] = loadout
	}

	return map[string]any{
		"partyId":  "party-" + id,
		"id":       "party-" + id,
		"leader":   id,
		"leaderId": id,
		"ownerId":  id,
		// The selected matchmaking activity. The client's Comp_MainMenu_QueueController
		// requires the party to always carry a non-empty target queue (usmap Party.TargetQueueID
		// / .TargetQueueIDs) â€” otherwise IsPartyOwner/CanControlQueue-gated modifies fail with
		// "Unable to modify activity. You must always have one activity selected." Seeded from
		// the client's own GET /party/players/{id}?defaultQueue=<q> and updated on switch.
		"targetQueueId":   targetQueue,
		"targetQueueIds":  []any{targetQueue},
		"members":         []any{member},
		"invitees":        []any{},
		"invitationToken": "",
		"joinSecret":      "",
		"inQueue":         false,
		"isOpen":          false,
		"fillTeam":        false,
		"createdAt":       now,
		// â˜… S107 (2026-07-27) â€” FParty.State, the gate behind TryStartSoloMode.
		//
		// SYMPTOM that motivated this: at the TUTORIALS tab with BASIC TRAINING selected,
		// pressing START did NOTHING â€” zero new HTTP requests in capture.log and zero new
		// lines in Loki.log (the client log after the click is idle GC only). An inert click
		// with no egress means the handler bails BEFORE any network call, so this was never
		// a missing endpoint.
		//
		// MECHANISM: Comp_MainMenu_QueueController -> PartyManager.TryStartSoloMode(Mode, ...)
		// reads the party's State at PartyModel+0x558+0x18. `FParty` prop 2 is a plain
		// FString State (offset 0x18, MEASURED from Binds.Cache), and we never served it, so
		// it read empty and the call bailed. The exe's enum entries are
		// EPartyState::{Default,Matchmaking,CustomGame,Unknown} (.rdata 0x08ABD2A8..0x08ABD390),
		// so "Default" is the idle/startable value. The same field is what the client's
		// 'skipping set latencies, party state: %s' guard reads (see docs/fk5-battle-gate-settled.md).
		//
		// This durably replaces the live memory poke the tutorial route had been using to
		// clear the same gate (docs/coverage-audit-s101.md:160).
		//
		// TYPE SAFETY: both keys below are Str props, and the validity model
		// (internal/menu/menu.go) only rejects a doc on a MATCHED key with the WRONG TYPE â€”
		// so a wrong *value* here can change the state machine but cannot break the party
		// document. If "Default" proves wrong, "default" is the other candidate.
		"state": "Default",
		// FParty.ClientVersion â€” PartyManager.cpp logs 'Client version not valid, leaving
		// matchmaking' when this mismatches. Value is the client's own X-Theorycraft-Clientversion.
		"clientVersion": "release2.4.live-156430-shipping",
		// â˜… LOAD-BEARING â€” must strictly advance or the client discards the WHOLE
		// document. UPartyModel::SetParty (base+0x587BE90) bails on
		// `jge` against its cached FParty.Version. This was pinned to 1 until
		// 2026-07-19, which meant the party applied exactly once at launch and no
		// later poll ever landed â€” avatars, displayName and everything else only
		// refreshed on relaunch. See store.partyVersion() for the full disassembly.
		"version": partyVersion,
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
