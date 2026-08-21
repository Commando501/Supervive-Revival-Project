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
	"time"
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
	// SelectedHeroAssetId is the player's active/selected hunter as a PrimaryAssetId
	// string ("Hero:<codename>"). It drives the main-menu party-slot / center preview:
	// the client builds a PartyMemberModel from the /party member entry, and the
	// party-slot preview actor renders that member's HeroAssetID (an empty/invalid id
	// shows BP_LokiHeroSelectPreview_UnknownHero — the "?"). Persisted so the picked
	// hunter survives relaunch. Written by the party member-update endpoint
	// (TryPickMyHeroAndCosmetics on the native PartyManager); seeded into buildSoloParty.
	SelectedHeroAssetId string `json:"selectedHeroAssetId,omitempty"`

	// SelectedQueueID is the matchmaking queue/activity the player has selected in the
	// ActivityPicker (e.g. "tutorialNew","default","practice"). The client's
	// Comp_MainMenu_QueueController enforces a "you must always have one activity
	// selected" invariant: the party's TargetQueueID must be non-empty or every modify
	// fails with "Unable to modify activity". Seeded from the client's own
	// GET /party/players/{id}?defaultQueue=<q> param, then updated when the player
	// switches activities; echoed back as the party's targetQueueId(s) each poll.
	SelectedQueueID string `json:"selectedQueueId,omitempty"`

	// SoloMode is the mode of an in-progress solo-start (S61): set when the client POSTs
	// /party/parties/{id}/startSoloMode?mode=<q> (e.g. "tutorialNew"). Non-empty means the
	// player has launched a solo tutorial/practice and is awaiting the match/travel; ""
	// means idle. Drives whether /core-game/players reports the (local) tutorial match.
	//
	// TRANSIENT (json:"-", S62): deliberately NOT persisted. /core-game/players is the
	// "do I have a match to REJOIN?" heartbeat; now that the response carries a real
	// (usmap-correct) MatchID that actually drives the client to escalate/travel,
	// persisting SoloMode would make a FRESH boot immediately report a phantom match at
	// the login/menu and risk an unwanted auto-rejoin/travel loop (the tutorial travel
	// still hits the S61 session gate). Keeping it in-memory means a clean idle menu on
	// boot; the match is armed only by the live POST /startSoloMode. (Also auto-clears the
	// stale S61 "soloMode":"tutorialNew" left in state/interactive.json on next save.)
	SoloMode string `json:"-"`

	// InQueue is true between the FIND MATCH click (POST .../joinQueue) and a cancel.
	// Echoed as the party's and the member's `inQueue` boolean so the client's queued
	// state survives the next /party poll — without it the poll re-serves false and the
	// UI snaps back, exactly the defect handleSetTargetQueues exists to remove.
	//
	// TRANSIENT (json:"-"), for the same reason SoloMode is: a persisted "queued" flag
	// would make a FRESH boot claim the player is already searching for a match, with no
	// matchmaker to ever clear it. Queue state is a property of a live session.
	InQueue bool `json:"-"`

	// PartyIsOpen is the party privacy toggle (POST .../setIsOpen/{True|False}), echoed as
	// the party's `isOpen` boolean. Transient for the same reason as InQueue and SoloMode:
	// it is live-session state, and a persisted value would silently outlive the party.
	PartyIsOpen bool `json:"-"`

	// --- PersonalizationLoadout (customization equips) — see loadout.go ---
	// LoadoutVersion is bumped on EVERY loadout-affecting write (slot cosmetics,
	// emotes, titles, hero bundles, luxe chromas, lobby platform). The client's
	// ULoadoutReconciler only re-applies a loadout doc whose version advanced
	// past its LastLoadoutVersion, so a non-bumping write looks like a no-op.
	LoadoutVersion int64 `json:"loadoutVersion,omitempty"`
	// SlotCosmetics maps slot name -> equipped asset id, e.g.
	// "Glider" -> "SlotCosmetics:GLIDER_AngelicForce" (SlotCosmeticsEntry pairs).
	SlotCosmetics map[string]string `json:"slotCosmetics,omitempty"`
	// HeroCosmeticsBundles maps "Hero:<name>" -> "HeroCosmeticsBundle:<name>"
	// (the per-hero skin preference).
	HeroCosmeticsBundles map[string]string `json:"heroCosmeticsBundles,omitempty"`
	// LuxeChromas maps luxe asset id -> chroma asset id.
	LuxeChromas map[string]string `json:"luxeChromas,omitempty"`
	// EmoteIds / TitleIds are the client's arrays stored verbatim (raw JSON) so
	// the element types never need modeling; echoed as loadout emoteIds/titleIds.
	EmoteIds json.RawMessage `json:"emoteIds,omitempty"`
	TitleIds json.RawMessage `json:"titleIds,omitempty"`

	// --- Missions (Option 2: real progress tracking) — see missions.go ---
	// MissionObjectives maps a PER-MISSION objective key "<missionInternalName>/<objectiveUniqueName>"
	// (e.g. "Tournament_PlayAGame/PlayAGame", "ArmoryDaily_PlayAGame/PlayAGame") to the player's current
	// progress toward it. Keying by mission+objective (not just the objective's GetUniqueObjectiveName)
	// gives PER-MISSION granularity: two missions that share an objective name (e.g. "PlayAGame" on the
	// Tournament and a Daily) track independently. The client-side menu-load shim fetches this
	// (GET /revival/missions/progress) and writes each value into that mission's
	// FMissionProgress.ObjectiveProgress; the match-result engine fans a match's stat deltas out to every
	// mission that has the objective (via MissionManifest). Single-account revival: stored under "local".
	MissionObjectives map[string]float64 `json:"missionObjectives,omitempty"`
	// MissionManifest is the mission->objective structure the shim registers on menu load
	// (POST /revival/missions/manifest), so POST /revival/missions/match-result can fan an objective's
	// delta out to each mission's composite key. Persisted so match results work across ags restarts.
	MissionManifest []ManifestEntry `json:"missionManifest,omitempty"`

	// --- PASSES: Hunter's Journey account-pass progress (S83) — see handleGetProgression ---
	// These are served as FPlayerProgression.AccountPass { Level, XP, Cleared } on
	// GET /progression/players/{id}, which the client's native ingester (game RVA 0x585A570)
	// copy-constructs into ProgressionManager+0x90 and then broadcasts — so an admin edit shows up
	// on the PASSES tier ladder within the client's ~61s poll, no relaunch and no shim involved.
	// LIVE-VERIFIED: Level/XP land at PM+0x17C/+0x180 and the ladder renders the XP counter.
	// Zero values are the honest default for a fresh account (tier 0, no XP); the client treats
	// Level as a tier INDEX, and only Level >= 0 passes its tier predicate (game RVA 0x584B920).
	AccountPassLevel int `json:"accountPassLevel,omitempty"`
	AccountPassXP    int `json:"accountPassXP,omitempty"`
	// AccountPassCleared marks the whole track finished. No omitempty: false is a meaningful,
	// explicitly-set value here and the admin GUI round-trips the doc.
	AccountPassCleared bool `json:"accountPassCleared"`

	// --- HERO MASTERY: per-hero mastery track (S120) — see heromastery.go ---
	// Keyed by the hero's InternalName as declared by its LokiDataAsset_HeroMastery
	// ("Alchemist", "reshealer", "RONIN", ... — shipped casing, matched case-insensitively).
	// Served as FPlayerProgression.HeroMastery = TArray<FHeroMasteryProgress> @0x148 on
	// GET /progression/players/{id}, which rides the SAME native ingester (0x585A570) already
	// proven for AccountPass and MissionInfo. Absent/zero is the correct fresh-account state.
	// ⚠ Only emitted when AGS_SERVE_HEROMASTERY is set — see heroMasteryMode() for why that
	// knob exists (a wrong-typed key here rejects the WHOLE document and would silently close
	// the missions page, the account pass and the news banner together).
	HeroMastery map[string]HeroMasteryProgress `json:"heroMastery,omitempty"`
	// MasteryClaimed records which mastery LEVELS the player has already claimed, keyed by the
	// hero's lower-cased InternalName. Served as the complement of
	// FHeroMasteryProgress.UnclaimedRewards: a level is offered until it appears here.
	// Persisted so a claim survives an ags restart — otherwise every restart would re-offer
	// rewards the player already took, which is indistinguishable from the claim route not working.
	MasteryClaimed map[string][]int `json:"masteryClaimed,omitempty"`
}

// store is an in-memory player-state map with best-effort JSON-file persistence
// so equipped selections survive a relaunch (launch-redirect.ps1 rebuilds +
// restarts the process, clearing memory).
type store struct {
	mu      sync.Mutex
	path    string
	players map[string]*playerState

	// partyVer backs the party doc's "version" field. See partyVersion() — it is
	// LOAD-BEARING: the client discards the whole party document unless this
	// strictly advances.
	partyVer int64
}

func newStore(path string) *store {
	s := &store{path: path, players: map[string]*playerState{}}
	// Seed from wall-clock ms, NOT 0. UPartyModel::SetParty's gate compares against
	// the version the CLIENT already cached, and the client outlives an ags restart
	// (we restart the backend under a running game constantly). A process-local
	// counter restarting at 0 would sit BELOW the client's cached value and wedge the
	// party permanently. UnixMilli advances ~1000/sec while this counter advances at
	// most a few times/sec, so a restart always lands far above whatever we last
	// served. Same reasoning as the battlepass Version seed (memory:
	// supervive-passes-battlepass-status).
	s.partyVer = time.Now().UnixMilli()
	s.load()
	return s
}

// partyVersion returns the current party-document version.
//
// ★ LOAD-BEARING (2026-07-19, S85). UPartyModel::SetParty (base+0x587BE90) gates the
// ENTIRE party document on a strict monotonic version:
//
//	+0x587BEFF  mov rax,[r14+0x10]        ; incoming FParty.Version
//	+0x587BF03  cmp [r12+0x568],rax       ; cached PartyModel.Party.Version
//	+0x587BF0B  jge <epilogue>            ; cached >= incoming -> BAIL (does nothing)
//
// We previously pinned "version": 1, so the document applied exactly ONCE (0->1 at
// launch) and every later poll was discarded wholesale — nothing downstream ever
// refreshed: not the avatar/personalization loadout, not displayName, nothing. That
// is why equipping a different avatar only took effect after a relaunch.
//
// Incrementing once on every store write (see update/updatePrimary) means any real
// change re-opens the gate: the client applies the new party doc the next time it runs
// its party-apply cycle. An idle party keeps a CONSTANT version and is correctly a
// no-op, so we never force a pointless re-apply.
//
// It does NOT control switch LATENCY. The client runs SetParty on a fixed internal
// cadence (~30-40s at an idle menu), independent of how fast the version rises —
// live-measured: a one-shot bump, an 8s climbing window, and an every-poll climb all
// propagated in ~30-44s. So a higher version only needs to be PRESENT when that cycle
// fires; making it climb faster does nothing. Beating the ~30s floor needs an external
// trigger (a lobby-WS party/personalization notif that forces an immediate re-apply),
// not a version change — tracked separately.
//
// NOTE the member's PersonalizationLoadout has its OWN second gate at +0x587C676
// (incoming Loadout.Version > existing, else skip). loadoutDoc's "version" already
// satisfies it — but it is only ever REACHED when this outer gate passes.
func (s *store) partyVersion() int64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.partyVer
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

// primaryLocked returns the single real player's id and live state — the highest
// loadout-score entry, skipping the "local" missions bucket and any nil entry. The
// revival is single-account and the client-side shim carries no JWT, so this is how
// every revival-scoped read/write agrees on "the player": pick the entry that
// actually holds loadout data. Caller MUST hold s.mu (the returned *playerState is
// the LIVE pointer, only safe to touch under the lock). Returns "", nil when no such
// player exists yet. Centralizing the rule here keeps primaryLoadout /
// primarySelectedHero / primaryID / updatePrimary from drifting out of agreement.
func (s *store) primaryLocked() (string, *playerState) {
	var best *playerState
	bestID := ""
	bestScore := -1
	for id, st := range s.players {
		if id == missionsLocalKey || st == nil {
			continue
		}
		score := len(st.SlotCosmetics) + len(st.HeroCosmeticsBundles) + len(st.LuxeChromas)
		if st.SelectedHeroAssetId != "" {
			score++
		}
		if score > bestScore {
			bestScore, best, bestID = score, st, id
		}
	}
	return bestID, best
}

// primaryLoadout returns a snapshot of the single real player's persisted equips
// (slot cosmetics, hero skin bundles, luxe chromas) for the revival loadout feed
// the client-side shim reads. Maps are copied so callers never touch the live state
// under the lock. Returns empty maps if none.
func (s *store) primaryLoadout() (slots, bundles, chromas map[string]string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	slots, bundles, chromas = map[string]string{}, map[string]string{}, map[string]string{}
	if _, best := s.primaryLocked(); best != nil {
		for k, v := range best.SlotCosmetics {
			slots[k] = v
		}
		for k, v := range best.HeroCosmeticsBundles {
			bundles[k] = v
		}
		for k, v := range best.LuxeChromas {
			chromas[k] = v
		}
	}
	return slots, bundles, chromas
}

// primarySelectedHero returns the persisted selected hunter ("Hero:<name>") of the
// same best player primaryLoadout picks, or "" if none. The loadout_fix shim reads it
// to know which hero to re-pick (TryPick) so the 3D render refreshes to the saved skin.
func (s *store) primarySelectedHero() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, best := s.primaryLocked(); best != nil {
		return best.SelectedHeroAssetId
	}
	return ""
}

// primaryID returns just the id of the primary player (primaryLocked's pick), or ""
// if none exists yet. Used to key the loadout echo for revival-scoped writes.
func (s *store) primaryID() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	id, _ := s.primaryLocked()
	return id
}

// updatePrimary resolves the primary player and mutates it, then persists — all
// under ONE lock acquisition, so the resolve and the write cannot be interleaved by
// a concurrent update()/updatePrimary(). Returns the resolved id ("" = no player
// exists yet, in which case fn is NOT run). This is the write counterpart of
// primaryLoadout: both agree on the player via primaryLocked, so a revival write
// lands on exactly the entry the revival GET reads back.
func (s *store) updatePrimary(fn func(*playerState)) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	id, best := s.primaryLocked()
	if best == nil {
		return ""
	}
	fn(best)
	s.partyVer++ // re-open the SetParty version gate on change (see partyVersion)
	s.saveLocked()
	return id
}

// snapshotLoadout returns a value copy of the player's state with all mutable maps
// DEEP-COPIED under the lock. loadoutDoc marshals these maps (heroCosmeticsBundles,
// slotCosmetics, luxeChromas) into its JSON echo; without a snapshot, that marshal
// iterates the LIVE map while a concurrent update() writes it — Go's fatal
// "concurrent map read and map write" that crashed ags in handleSetCosmeticsBundle.
// Scalars and the immutable RawMessage/[]byte fields (EmoteIds/TitleIds — replaced,
// never mutated in place) are safe via the shallow struct copy. Returns a zero value
// (all nil maps) if the player has no state yet.
func (s *store) snapshotLoadout(id string) playerState {
	s.mu.Lock()
	defer s.mu.Unlock()
	st := s.players[id]
	if st == nil {
		return playerState{}
	}
	cp := *st // shallow: scalars + slice/map headers
	cp.SlotCosmetics = copyStrMap(st.SlotCosmetics)
	cp.HeroCosmeticsBundles = copyStrMap(st.HeroCosmeticsBundles)
	cp.LuxeChromas = copyStrMap(st.LuxeChromas)
	return cp
}

// heroCosmetic returns id's saved bundle for hero, looked up UNDER THE LOCK. A live
// map read (even a single-key lookup) concurrent with update()'s write is Go's fatal
// "concurrent map read and map write" — the same class of crash snapshotLoadout fixes,
// reachable here on every party poll via selectedCosmetic.
func (s *store) heroCosmetic(id, hero string) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	st := s.players[id]
	if st == nil {
		return ""
	}
	return st.HeroCosmeticsBundles[hero]
}

// copyStrMap returns a shallow copy of m (nil stays nil).
func copyStrMap(m map[string]string) map[string]string {
	if m == nil {
		return nil
	}
	c := make(map[string]string, len(m))
	for k, v := range m {
		c[k] = v
	}
	return c
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
	s.partyVer++ // re-open the SetParty version gate on change (see partyVersion)
	s.saveLocked()
	return st
}
