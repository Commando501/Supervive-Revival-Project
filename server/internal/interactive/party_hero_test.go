package interactive

import (
	"encoding/json"
	"testing"
)

// TestHeroAssetIDFromBody covers the tolerant SetPartyMemberRequest parsing: the client
// may serialize the PrimaryAssetId as a "Type:Name" string or as a struct object, under
// either key spelling. A body without a usable hero id must be a no-op (return "") so a
// partial update (e.g. only IsReady) never wipes the persisted selection.
func TestHeroAssetIDFromBody(t *testing.T) {
	cases := []struct {
		name string
		body string
		want string
	}{
		{"string camel", `{"id":"p","heroAssetId":"Hero:beebo"}`, "Hero:beebo"},
		{"string pascal", `{"ID":"p","HeroAssetID":"Hero:wukong"}`, "Hero:wukong"},
		{"object type/name", `{"heroAssetId":{"type":"Hero","name":"ronin"}}`, "Hero:ronin"},
		{"object UE struct", `{"HeroAssetID":{"PrimaryAssetType":{"Name":"Hero"},"PrimaryAssetName":"storm"}}`, "Hero:storm"},
		{"empty body", ``, ""},
		{"no hero field", `{"id":"p","isReady":true}`, ""},
		{"empty string id", `{"heroAssetId":""}`, ""},
		{"empty object id", `{"heroAssetId":{"type":"","name":""}}`, ""},
		{"bare name no type", `{"heroAssetId":"alchemist"}`, ""},
		{"malformed json", `{not json`, ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := heroAssetIDFromBody([]byte(c.body)); got != c.want {
				t.Fatalf("heroAssetIDFromBody(%q) = %q, want %q", c.body, got, c.want)
			}
		})
	}
}

// TestSelectedHeroSeedAndPersist verifies the two halves of the flow at the store level:
// an unset player falls back to the default owned hunter (so the party slot never shows
// the UnknownHero "?"), and a persisted pick is returned verbatim thereafter.
func TestSelectedHeroSeedAndPersist(t *testing.T) {
	s := &Service{store: &store{players: map[string]*playerState{}}}

	if got := s.selectedHero("p1"); got != defaultHeroAssetId {
		t.Fatalf("unset player: selectedHero = %q, want default %q", got, defaultHeroAssetId)
	}

	s.store.update("p1", func(st *playerState) { st.SelectedHeroAssetId = "Hero:ronin" })
	if got := s.selectedHero("p1"); got != "Hero:ronin" {
		t.Fatalf("after pick: selectedHero = %q, want %q", got, "Hero:ronin")
	}
	// A different player is unaffected (still the default).
	if got := s.selectedHero("p2"); got != defaultHeroAssetId {
		t.Fatalf("other player: selectedHero = %q, want default %q", got, defaultHeroAssetId)
	}
}

// TestBuildSoloPartyCarriesHero confirms the seeded hunter lands on the member entry under
// the key(s) the client reads (member.HeroAssetID), as a PrimaryAssetId string, and that the
// player appears as the sole leader (so PartyModel.GetSelf resolves "me").
func TestBuildSoloPartyCarriesHero(t *testing.T) {
	party := buildSoloParty("p1", "Player One", "Hero:beebo", "HeroCosmeticsBundle:BeeboCyber", "default", nil)
	members, ok := party["members"].([]any)
	if !ok || len(members) != 1 {
		t.Fatalf("expected exactly one member, got %v", party["members"])
	}
	m := members[0].(map[string]any)
	if m["id"] != "p1" {
		t.Fatalf("member id = %v, want p1 (GetSelf must match the login id)", m["id"])
	}
	if m["leader"] != true {
		t.Fatalf("member leader = %v, want true", m["leader"])
	}
	if m["heroAssetId"] != "Hero:beebo" {
		t.Fatalf("member heroAssetId = %v, want Hero:beebo", m["heroAssetId"])
	}
	// The member cosmetic is intentionally NOT served (proven inert 2026-07-09: the client
	// ignores the echoed member cosmetic and the party slot renders the default). It must
	// be absent regardless of the cosmetic argument.
	if _, present := m["cosmeticsAssetId"]; present {
		t.Fatalf("member cosmeticsAssetId should be absent (client ignores it; serving risks the s53 lock)")
	}
	// Round-trip through JSON as the client sees it (string PrimaryAssetId form).
	b, _ := json.Marshal(party)
	var back struct {
		Members []struct {
			HeroAssetId string `json:"heroAssetId"`
		} `json:"members"`
	}
	if json.Unmarshal(b, &back) != nil || len(back.Members) != 1 || back.Members[0].HeroAssetId != "Hero:beebo" {
		t.Fatalf("json round-trip lost heroAssetId: %s", b)
	}
}

// TestBuildSoloPartyCarriesPersonalizationLoadout covers the AVATAR RENDER fix (2026-07-19).
//
// The client's avatar widgets never read the PersonalizationManager: BPFL_Social_C::
// DetermineSocialInfoForPlatformPlayer resolves the avatar from
// PartyMember.PersonalizationLoadout.SlotCosmeticsEntries via FindSlotCosmeticEntry(Avatar slot).
// We never served that field, so the live PartyMemberModel had it all-zero (Version = -1,
// SlotCosmeticsEntries Num=0) and the widget painted TX_Transparent by design.
//
// The load-bearing assertion is the CONTAINER TYPE: slotCosmeticsEntries must marshal as a JSON
// ARRAY of {slot, asset} objects. Per the validity model (internal/menu/menu.go) UE ignores an
// unmatched key but rejects the WHOLE doc when a matched key has the wrong container type — so
// emitting this as a map would take out the entire party panel, not merely the avatar.
func TestBuildSoloPartyCarriesPersonalizationLoadout(t *testing.T) {
	loadout := map[string]any{
		"id":      "p1",
		"version": int64(940),
		"slotCosmeticsEntries": []any{
			map[string]any{"slot": "Avatar", "asset": "SlotCosmetics:AVATAR_AboveItAll"},
			map[string]any{"slot": "Glider", "asset": "SlotCosmetics:GLIDER_AngelicForce"},
		},
		"titleIds": json.RawMessage(`["PlayerTitle:APlus"]`),
	}
	party := buildSoloParty("p1", "Player One", "Hero:beebo", "", "default", loadout)
	m := party["members"].([]any)[0].(map[string]any)
	if _, ok := m["personalizationLoadout"]; !ok {
		t.Fatal("member is missing personalizationLoadout (the field the avatar widget reads)")
	}

	// Round-trip exactly as the client parses it, decoding into the live struct shape
	// (ScriptStruct PersonalizationLoadout @0x145E5806A60, confirmed via RPM).
	b, _ := json.Marshal(party)
	var back struct {
		Members []struct {
			PersonalizationLoadout struct {
				Version              int64 `json:"version"`
				SlotCosmeticsEntries []struct {
					Slot  string `json:"slot"`
					Asset string `json:"asset"`
				} `json:"slotCosmeticsEntries"`
			} `json:"personalizationLoadout"`
		} `json:"members"`
	}
	if err := json.Unmarshal(b, &back); err != nil {
		t.Fatalf("party doc does not deserialize into the live loadout shape: %v\n%s", err, b)
	}
	pl := back.Members[0].PersonalizationLoadout
	if len(pl.SlotCosmeticsEntries) != 2 {
		t.Fatalf("slotCosmeticsEntries = %d entries, want 2 (must be an ARRAY, not a map): %s", len(pl.SlotCosmeticsEntries), b)
	}
	var avatar string
	for _, e := range pl.SlotCosmeticsEntries {
		if e.Slot == "Avatar" {
			avatar = e.Asset
		}
	}
	if avatar != "SlotCosmetics:AVATAR_AboveItAll" {
		t.Fatalf("Avatar slot asset = %q, want SlotCosmetics:AVATAR_AboveItAll (FindSlotCosmeticEntry matches on the slot name)", avatar)
	}
	// Version must advance past the model's initial -1 or the client keeps its stale loadout.
	if pl.Version <= 0 {
		t.Fatalf("personalizationLoadout.version = %d, must be > 0 (live model initialises to -1)", pl.Version)
	}

	// nil loadout omits the key entirely (never emit a degenerate/empty struct).
	if _, present := buildSoloParty("p1", "n", "Hero:beebo", "", "default", nil)["members"].([]any)[0].(map[string]any)["personalizationLoadout"]; present {
		t.Fatal("nil loadout must omit personalizationLoadout rather than emit an empty struct")
	}
}
