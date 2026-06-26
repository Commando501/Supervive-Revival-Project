// Package menu implements the post-login "main menu" services the client polls
// once it reaches the menu (Milestone 2). These run on the AccelByte HTTP base
// (:8080) because client-config's ServiceHostnames maps every service name —
// storefront, personalization, party, playerstats, etc. — to localhost:8080,
// and the game calls {base}/{service}/{endpoint}.
//
// Validity model (deduced from Loki.log — two distinct LogLokiPlatformQuery
// error strings, confirmed in the binary):
//   - "Invalid response received"  -> a pre-deserialize validity predicate failed
//     (a required top-level field is absent). Our {} stub hits this.
//   - "Deserialization failure"    -> the JSON parsed but its container type does
//     not match the target UStruct. A bare [] hits this (array vs. object struct).
//
// So the list endpoints expect a top-level JSON **object wrapper** (the AccelByte
// "...Result" model) whose required field (`data`) must be present. Returning
// {"data": [], "paging": {}} satisfies the predicate (data present) and
// deserializes cleanly (object -> object struct), both fields empty-but-typed so
// there is no wrong-type-rejects-whole-doc risk. Empty data == no battlepass
// shown, but the retry loop stops. The {}->[] transition is what proved this:
// {} gave "Invalid response received"; [] flipped it to "Deserialization failure".
package menu

import (
	"encoding/json"
	"net/http"
)

type Service struct{}

func New() *Service { return &Service{} }

func (s *Service) Register(mux *http.ServeMux) {
	// Battlepass progression tracks. Response model:
	// FAccelByteModelsListProgressionTrackInfoResult { Data: TArray<...>, Paging }.
	// See the validity-model note above for why this is an object wrapper, not a
	// bare array.
	mux.HandleFunc("GET /storefront/battlepass/progressiontracks", handleProgressionTracks)

	// Storefront commerce (UStorefrontManager / StorefrontOrderModel.cpp). Custom
	// Theorycraft "FLokiStorefront*" models, not stock AccelByte. These currently
	// accept the {} catch-all silently (no validity predicate, one-shot — they just
	// render empty), so populating them can't tight-loop; worst case a wrong-typed
	// *matched* field rejects the doc back to empty.
	mux.HandleFunc("GET /storefront/wallet/{id}", handleWallet)
	mux.HandleFunc("GET /storefront/offers/{id}", handlePlayerStore)
}

// handleWallet returns FLokiStorefrontPlayerWallet. Binary shows exactly one
// field on the struct: `Balances` with a `Balances_Key` companion => it is a
// TMap<FString, ?>. The map's VALUE type isn't visible statically, so this is a
// probe: we send int values. Relaunch outcomes pin it down via Loki.log —
//   - clean parse                          => value type is int (or number);
//     currency shows iff these codes are the ones the UI reads.
//   - "Deserialization failure" on
//     FLokiStorefrontPlayerWallet           => value is a struct, not int — switch
//     to FLokiStorefrontCurrencyAmount-shaped values next.
// Currency codes are not static strings in the exe (server/packed-config defined),
// so the keys here are best-guess and may need correction once the value type is
// confirmed.
func handleWallet(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"Balances": map[string]any{
			"hero_tokens":  100,
			"power_shards": 5000,
		},
	})
}

// handlePlayerStore returns FLokiStorefrontPlayerStore (the /storefront/offers/{id}
// response): RotatingOffers, FeaturedItemOffers, TypeOffers (arrays) + NextRotation
// (omitted — it's almost certainly an FDateTime and a bad string would reject the
// doc; an absent field safely defaults). Empty arrays = valid container, empty shop
// — no regression, and the correct shape to grow item offers into later.
func handlePlayerStore(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"RotatingOffers":     []any{},
		"FeaturedItemOffers": []any{},
		"TypeOffers":         []any{},
	})
}

func handleProgressionTracks(w http.ResponseWriter, r *http.Request) {
	// Empty data deserializes cleanly, but the battlepass managers then tight-loop
	// this endpoint (~100 req/s, silently — no per-request error in Loki.log)
	// because the consumer `UStorefront::GetCurrentPublishedProgressionTracks`
	// finds no *published* track to adopt and immediately re-queries.
	//
	// So we now return one populated FAccelByteModelsListProgressionTrackInfo
	// element. Field selection follows the validity rule (endpoints.md): UE's
	// JsonObjectStringToUStruct *ignores* JSON keys that match no UPROPERTY and
	// only rejects the whole doc when a key that DOES match has a wrong type. So
	// every field below is either confirmed on this struct by the binary's
	// FName cluster (ProgressionType, RewardTrackCodes) or — if present at all —
	// is an FString/enum-string (Id, Code, Status), which is the type AccelByte
	// uses for these. None are bool/int/struct, so a populated element cannot
	// regress the clean parse we already have.
	//
	//   ProgressionType  EAccelByteProgressionTrackType  -> "SEASON_PASS"
	//                    (enum values: NONE | SEASON_PASS | PROGRESSION_TRACK)
	//   Status           EAccelByteProgressionTrackStatus -> "PUBLISHED"
	//                    (enum values: NONE | DRAFT | PUBLISHED | RETIRED) — the
	//                    bet that quiets "current *published*" filter.
	//   RewardTrackCodes TArray<FString> — confirmed on this struct.
	//
	// If a relaunch shows the loop persists or a new "Invalid response"/
	// "Deserialization failure" appears, the log names the next field to add or
	// the wrong-typed one to drop.
	writeJSON(w, map[string]any{
		"data": []any{
			map[string]any{
				"Id":               "supervive-season-1",
				"Code":             "supervive-season-1",
				"ProgressionType":  "SEASON_PASS",
				"Status":           "PUBLISHED",
				"RewardTrackCodes": []string{"supervive-season-1-track"},
			},
		},
		"paging": map[string]any{"previous": "", "next": ""},
	})
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(v)
}
