package menu

import (
	_ "embed"
	"os"
	"strings"
)

// emotegrant.go — serve EMOTES as a cosmetic type: storefront ItemOffers + inventory
// ownership. S133, 2026-08-20. Knob: AGS_GRANT_EMOTES. Default EMPTY = byte-identical
// to the pre-S133 wire.
//
// ── WHY ───────────────────────────────────────────────────────────────────────
// S133 served POST /party/parties/{p}/emote/ (TrySendEmote, 0x5879040) and instrumented
// it to log the raw body, because the emote payload shape had never been observed.
//
// [M] THERE IS NO PAYLOAD: the client sends an EMPTY path tail AND an EMPTY body
// (`tail="" bodylen=0 body=""`), six times across two sittings, because the account owns
// no emotes. Operator-confirmed on screen. ⇒ the blocker was never the endpoint's shape;
// it is upstream ownership. Instrumenting harder would have produced six more empty bodies.
//
// ── WHERE THE NAMES COME FROM ─────────────────────────────────────────────────
// data/emotes.txt = 331 names read LIVE out of the running client's own FNamePool
// (`usmapdump nameid <proc> "Personalization/Emotes/"`), by taking the folder component of
// every `/Game/Loki/Personalization/Emotes/<Name>/...` path the client had interned.
// Cross-checked: `SeraphHi` appears both as a bare FName and as
// `/Game/Loki/Personalization/Emotes/SeraphHi/BP_Emote_SeraphHi_Animated`.
//
// That is the same discipline data/skins.txt and data/slots.txt were built with, and the
// same lesson as the missions `InternalName` episode: serve the registry the game ships,
// never a plausible guess — an unresolvable PrimaryAssetId is dropped SILENTLY.
//
// ⚠ It supersedes a WRONG first cut that scraped 50 `Emote:<Name>` SKUs out of
// mastery_rewards.json. Those 50 are real, but they are only the hero Hi/Bye pair per
// hero — 15 % of the 331 the client actually knows (AbsoluteCinema, Byeee, SussyBaka,
// Nuke, BlushyPeachy, Superviboogie …). Granting a strict subset of the registry is not
// wrong, but it is not the registry.
//
// ⚠⚠ AND IT CORRECTS cosmetics.go:13, WHICH IS MISLEADING. That comment says the STORE's
// ACCESSORIES tab covers "Gliders/Emotes/Wisps/Sprays/Avatars" as type SlotCosmetics.
// MEASURED: the 536-name SlotCosmeticsAssets map captured live from the client contains
// ZERO emotes — its slot prefixes are AVATAR(225)/SPRAY(146)/GLIDER(115)/WISP(40)/
// SPIKEVFX(2). Emotes are their OWN PrimaryAssetType, `Emote`, which is also the form the
// shipped hero-mastery reward DAs use (`"SKU":"Emote:SeraphHi"`).
//
// ── WHAT THIS SERVES, AND WHAT IS UNVERIFIED ──────────────────────────────────
// Inventory ownership ALONE was flown first and was MEASURED INSUFFICIENT: 50 entries
// served as `Emote:<n>` with IsOwned=true, client re-fetched /inventory/players/{id}
// (forced with the admin socket-drop, no relaunch), CUSTOMIZATION → EMOTES still empty.
// So this adds the OTHER half the working cosmetic tabs have and emotes did not:
// storefront ItemOffers, whose resolved PrimaryAssetType is what those tabs filter on.
//
// ⚠ UNVERIFIED [S]: that offers + ownership is sufficient. What is [M] is only that
// ownership alone is not, that the ids resolve, and that offers are the one structural
// asymmetry between emotes and the tabs that DO populate. If the picker stays empty this
// is still progress — it eliminates the asymmetry — but the next suspect is a separate
// per-type asset-loader map the client populates for emotes and not from our documents.
//
// Usage:
//
//	AGS_GRANT_EMOTES=1                    -> all 331
//	AGS_GRANT_EMOTES=SeraphHi,Byeee       -> just those (validated against the registry)

//go:embed data/emotes.txt
var emotesData string

// emoteNames returns the emote asset names to serve, or nil when the knob is unset.
// Returning nil (not an empty slice) keeps both documents byte-identical to the pre-S133
// wire, which is what makes this safe to leave in the tree.
func emoteNames() []string {
	v := strings.TrimSpace(os.Getenv("AGS_GRANT_EMOTES"))
	if v == "" || v == "0" {
		return nil
	}
	all := lines(emotesData)
	if v == "1" || strings.EqualFold(v, "all") {
		return all
	}
	// Explicit list, validated against the registry so a typo is LOUD rather than silently
	// serving an id the client cannot resolve.
	valid := make(map[string]string, len(all))
	for _, n := range all {
		valid[strings.ToLower(n)] = n
	}
	var out []string
	for _, want := range strings.Split(v, ",") {
		want = strings.TrimSpace(strings.TrimPrefix(want, "Emote:"))
		if want == "" {
			continue
		}
		if canonical, ok := valid[strings.ToLower(want)]; ok {
			out = append(out, canonical)
		}
	}
	return out
}

// emoteInventoryEntries marks every served emote owned (drives CatalogEntry.IsOwned=1).
func emoteInventoryEntries() []map[string]any {
	names := emoteNames()
	if len(names) == 0 {
		return nil
	}
	return ownedAssetEntries(names, "Emote")
}

// emoteOffers builds the storefront ItemOffers for emotes — the half that inventory
// ownership alone did not supply. Category "Emotes" mirrors the "Skins"/"Accessories"
// spelling used at menu.go:392-393.
func emoteOffers() []map[string]any {
	names := emoteNames()
	if len(names) == 0 {
		return nil
	}
	return cosmeticOffers(names, "Emote", "Emotes")
}
