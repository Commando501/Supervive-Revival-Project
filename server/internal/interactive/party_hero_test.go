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
	party := buildSoloParty("p1", "Player One", "Hero:beebo")
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
