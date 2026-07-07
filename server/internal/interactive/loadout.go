package interactive

// loadout.go — the customization/equip write-back surface (PersonalizationLoadout).
//
// RECOVERED 2026-07-06. The customization page's selections revert on re-entry
// because every equip write fell through to the {} catch-all and the readback
// doc never carried them. Two sources pinned the whole surface in one session:
//
//  1. Live capture (docs/capture.log, session of 2026-07-06 15:07): clicking a
//     glider in CUSTOMIZATION fired
//       POST /personalization/players/{id}/slotcosmetics
//       body {"slot":"Glider","asset":"SlotCosmetics:GLIDER_AngelicForce"}
//     (twice — the re-click after the first didn't stick).
//
//  2. Route-fragment table in the shipping exe (usmapdump wstrings/peek, live
//     RPM @ mod-RVA 0x8B4C7C8): "/personalization/players/" +
//       /cosmeticsbundle/  /luxechromas/  /emotes  /titles  /slotcosmetics
//       /lobbyplatforms    /privacy       /clientprofile
//     adjacent to "&ULoadoutReconciler::ReconcileLoadout" / "No current loadout".
//
//  3. usmap schemas (tools/extractor `schema`, printer KeyValuePair fix same day):
//       PersonalizationLoadoutPlatform { ID:Str, Version:Int64, EmoteIds:Array,
//         TitleIds:Array<Name>, SlotCosmeticsEntries:Array<SlotCosmeticsEntry>,
//         IsAnonymous:Bool, Token:Str }
//       PersonalizationLoadout : PersonalizationLoadoutPlatform {
//         HeroCosmeticsBundlePreferences:Map, LuxeSkinChromaPreferences:Map,
//         LobbyPlatformPreference:PrimaryAssetId }
//       SlotCosmeticsEntry { Slot:Name, Asset:PrimaryAssetId }   <- matches the
//         captured POST body byte-for-byte (camelCase on the wire)
//       SetEmotesRequest { Emotes:Array<Str> }
//       SetTitlesRequest { Titles:Array }
//       SetLuxeSkinChromaPreferenceRequest { LuxeAssetID, ChromaAssetID }
//     No request struct exists for /cosmeticsbundle/ — the trailing slash in the
//     route fragment says the hero rides in the PATH (and/or query/body); the
//     handler parses all three tolerantly and the next live click will pin it.
//
// Model: the client's UPersonalizationManager rebuilds its local Loadout from
// this doc via ULoadoutReconciler::ReconcileLoadout, which compares the doc's
// Version against LastLoadoutVersion — so every write here MUST bump Version or
// the client will ignore the echo and the page still won't repopulate. The GET
// that returns the doc is the personalization root (GET /personalization/
// players/{id} — the only read on the surface, and the one that tolerated {}).
// Write responses echo the full updated doc (set-then-return, same convention
// clientprofile validated); unknown/extra keys are ignored per the validity
// model in internal/menu.
//
// STATUS 2026-07-06: built + unit-tested; awaiting live validation (equip a
// glider, leave/re-enter CUSTOMIZATION, then relaunch). The cosmeticsbundle and
// luxechromas parsers are tolerant best-guesses until a live click captures
// their real request shapes.

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
)

// registerLoadout wires the equip-write routes. Every pattern here previously
// fell through to the {} catch-all, so registration is zero-regression; verbs
// are registered as POST+PUT supersets where the real verb is uncaptured (the
// unused one simply never fires). The suffixed-path variants ({rest...}) exist
// because the exe's route fragments for cosmeticsbundle/luxechromas end in "/",
// implying an id segment follows.
func (s *Service) registerLoadout(mux *http.ServeMux) {
	// Slot cosmetics (Glider/Emote-wheel-slot/Wisp/Spray/Avatar/Title slots…) —
	// the one write we have a live capture of. Verb confirmed POST.
	mux.HandleFunc("POST /personalization/players/{id}/slotcosmetics", s.handleSetSlotCosmetic)
	mux.HandleFunc("PUT /personalization/players/{id}/slotcosmetics", s.handleSetSlotCosmetic)

	// Emote wheel + player titles (SetEmotesRequest / SetTitlesRequest).
	mux.HandleFunc("POST /personalization/players/{id}/emotes", s.handleSetEmotes)
	mux.HandleFunc("PUT /personalization/players/{id}/emotes", s.handleSetEmotes)
	mux.HandleFunc("POST /personalization/players/{id}/titles", s.handleSetTitles)
	mux.HandleFunc("PUT /personalization/players/{id}/titles", s.handleSetTitles)

	// Per-hero skin bundle preference (no request struct in the usmap — parsed
	// tolerantly from path/query/body).
	mux.HandleFunc("POST /personalization/players/{id}/cosmeticsbundle", s.handleSetCosmeticsBundle)
	mux.HandleFunc("PUT /personalization/players/{id}/cosmeticsbundle", s.handleSetCosmeticsBundle)
	mux.HandleFunc("POST /personalization/players/{id}/cosmeticsbundle/{rest...}", s.handleSetCosmeticsBundle)
	mux.HandleFunc("PUT /personalization/players/{id}/cosmeticsbundle/{rest...}", s.handleSetCosmeticsBundle)

	// Luxe skin chroma preference (SetLuxeSkinChromaPreferenceRequest).
	mux.HandleFunc("POST /personalization/players/{id}/luxechromas", s.handleSetLuxeChroma)
	mux.HandleFunc("PUT /personalization/players/{id}/luxechromas", s.handleSetLuxeChroma)
	mux.HandleFunc("POST /personalization/players/{id}/luxechromas/{rest...}", s.handleSetLuxeChroma)
	mux.HandleFunc("PUT /personalization/players/{id}/luxechromas/{rest...}", s.handleSetLuxeChroma)
}

// handleSetSlotCosmetic persists one slot's equipped cosmetic. Body is a
// SlotCosmeticsEntry: {"slot":"Glider","asset":"SlotCosmetics:GLIDER_X"} — the
// asset is tolerated in string or UE-object PrimaryAssetId form. An empty/
// invalid asset for a known slot is treated as UNEQUIP (entry removed) rather
// than a wipe of the whole map; a body without a slot is a no-op.
func (s *Service) handleSetSlotCosmetic(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req struct {
		Slot  string          `json:"slot"`
		Asset json.RawMessage `json:"asset"`
	}
	_ = json.Unmarshal(body, &req)
	if req.Slot != "" {
		asset := primaryAssetIDString(req.Asset)
		s.store.update(id, func(st *playerState) {
			if st.SlotCosmetics == nil {
				st.SlotCosmetics = map[string]string{}
			}
			if asset == "" {
				delete(st.SlotCosmetics, req.Slot)
			} else {
				st.SlotCosmetics[req.Slot] = asset
			}
			st.LoadoutVersion++
		})
	}
	writeJSON(w, s.loadoutDoc(id))
}

// handleSetEmotes persists the emote-wheel selection. Request model is
// SetEmotesRequest{Emotes: Array<Str>}; the array is stored verbatim (raw JSON)
// and echoed as the loadout's emoteIds, so we never mis-model the element type.
func (s *Service) handleSetEmotes(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req struct {
		Emotes json.RawMessage `json:"emotes"`
	}
	if json.Unmarshal(body, &req) == nil && len(req.Emotes) > 0 {
		s.store.update(id, func(st *playerState) {
			st.EmoteIds = req.Emotes
			st.LoadoutVersion++
		})
	}
	writeJSON(w, s.loadoutDoc(id))
}

// handleSetTitles persists the equipped player title(s). Request model is
// SetTitlesRequest{Titles: Array} (element type unresolved in the usmap; the
// loadout's TitleIds is Array<Name> = strings) — stored verbatim like emotes.
func (s *Service) handleSetTitles(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req struct {
		Titles json.RawMessage `json:"titles"`
	}
	if json.Unmarshal(body, &req) == nil && len(req.Titles) > 0 {
		s.store.update(id, func(st *playerState) {
			st.TitleIds = req.Titles
			st.LoadoutVersion++
		})
	}
	writeJSON(w, s.loadoutDoc(id))
}

// handleSetCosmeticsBundle persists a per-hero skin-bundle preference. The exe
// has NO request struct for this route and its fragment ends in "/" (hero id in
// the path), so the shape is unconfirmed: we harvest PrimaryAssetId-shaped
// strings from the path remainder, the query string, and any string/object
// values in the body, then pair the "Hero:*" one with the
// "HeroCosmeticsBundle:*" one. Unpairable requests are a no-op (never a wipe) —
// and the raw request lands in capture.log either way, which is what will pin
// the real shape after the next live skin click.
func (s *Service) handleSetCosmeticsBundle(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))

	hero, bundle := "", ""
	for _, c := range assetIDCandidates(r, body) {
		switch {
		case strings.HasPrefix(c, "Hero:"):
			hero = c
		case strings.HasPrefix(c, "HeroCosmeticsBundle:"):
			bundle = c
		}
	}
	if hero != "" {
		s.store.update(id, func(st *playerState) {
			if st.HeroCosmeticsBundles == nil {
				st.HeroCosmeticsBundles = map[string]string{}
			}
			if bundle == "" {
				delete(st.HeroCosmeticsBundles, hero) // hero named, no bundle => unequip
			} else {
				st.HeroCosmeticsBundles[hero] = bundle
			}
			st.LoadoutVersion++
		})
	}
	writeJSON(w, s.loadoutDoc(id))
}

// handleSetLuxeChroma persists a luxe-skin chroma preference. Request model is
// SetLuxeSkinChromaPreferenceRequest{LuxeAssetID, ChromaAssetID} (encoding/json
// matches keys case-insensitively, so camelCase/PascalCase both land). A luxe
// with an empty chroma unequips that luxe's entry.
func (s *Service) handleSetLuxeChroma(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	var req struct {
		LuxeAssetID   json.RawMessage `json:"luxeAssetId"`
		ChromaAssetID json.RawMessage `json:"chromaAssetId"`
	}
	_ = json.Unmarshal(body, &req)
	luxe := primaryAssetIDString(req.LuxeAssetID)
	chroma := primaryAssetIDString(req.ChromaAssetID)
	if luxe != "" {
		s.store.update(id, func(st *playerState) {
			if st.LuxeChromas == nil {
				st.LuxeChromas = map[string]string{}
			}
			if chroma == "" {
				delete(st.LuxeChromas, luxe)
			} else {
				st.LuxeChromas[luxe] = chroma
			}
			st.LoadoutVersion++
		})
	}
	writeJSON(w, s.loadoutDoc(id))
}

// loadoutDoc builds the PersonalizationLoadout JSON doc — the readback the
// customization page repopulates from (and the set-then-return echo for every
// write above). Field names are the usmap property names camelCased, matching
// the wire casing the client itself uses (clientVisibilityTracking precedent);
// UE matches case-insensitively regardless. PrimaryAssetIds go in "Type:Name"
// string form (proven by inventory/party). Version MUST reflect every write —
// ULoadoutReconciler only re-applies the doc when it advances past
// LastLoadoutVersion.
func (s *Service) loadoutDoc(id string) map[string]any {
	st := s.store.get(id)

	// Slot entries, sorted by slot for a stable doc (diff-friendly captures).
	slots := make([]string, 0, len(st.SlotCosmetics))
	for slot := range st.SlotCosmetics {
		slots = append(slots, slot)
	}
	sort.Strings(slots)
	entries := make([]any, 0, len(slots))
	for _, slot := range slots {
		entries = append(entries, map[string]any{"slot": slot, "asset": st.SlotCosmetics[slot]})
	}

	emotes := json.RawMessage("[]")
	if len(st.EmoteIds) > 0 {
		emotes = st.EmoteIds
	}
	titles := json.RawMessage("[]")
	if len(st.TitleIds) > 0 {
		titles = st.TitleIds
	}
	bundles := st.HeroCosmeticsBundles
	if bundles == nil {
		bundles = map[string]string{}
	}
	chromas := st.LuxeChromas
	if chromas == nil {
		chromas = map[string]string{}
	}

	doc := map[string]any{
		// PersonalizationLoadoutPlatform
		"id":                   id,
		"version":              st.LoadoutVersion,
		"emoteIds":             emotes,
		"titleIds":             titles,
		"slotCosmeticsEntries": entries,
		"isAnonymous":          false,
		"token":                "",
		// PersonalizationLoadout
		"heroCosmeticsBundlePreferences": bundles,
		"luxeSkinChromaPreferences":      chromas,
	}
	// Omit the lobby platform when unset — an empty string is a degenerate
	// PrimaryAssetId; absent is always safe (unmatched keys are ignored).
	if st.LobbyPlatformAssetId != "" {
		doc["lobbyPlatformPreference"] = st.LobbyPlatformAssetId
	}
	return doc
}

// assetIDCandidates harvests every PrimaryAssetId-looking string ("Type:Name")
// reachable in a request: path remainder segments, query values, and the
// string/object values of a (flat) JSON body. Used by the tolerant handlers
// whose exact request shape is uncaptured.
func assetIDCandidates(r *http.Request, body []byte) []string {
	var out []string
	add := func(s string) {
		if strings.Contains(s, ":") {
			out = append(out, s)
		}
	}
	if rest := r.PathValue("rest"); rest != "" {
		for _, seg := range strings.Split(rest, "/") {
			if dec, err := url.PathUnescape(seg); err == nil {
				add(dec)
			} else {
				add(seg)
			}
		}
	}
	for _, vs := range r.URL.Query() {
		for _, v := range vs {
			add(v)
		}
	}
	var m map[string]any
	if json.Unmarshal(body, &m) == nil {
		// Sort keys so candidate order (and thus last-wins pairing) is stable.
		keys := make([]string, 0, len(m))
		for k := range m {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			switch v := m[k].(type) {
			case string:
				add(v)
			case map[string]any:
				if raw, err := json.Marshal(v); err == nil {
					if id := primaryAssetIDString(raw); id != "" {
						add(id)
					}
				}
			}
		}
	}
	return out
}
