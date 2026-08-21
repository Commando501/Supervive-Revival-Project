#!/usr/bin/env python3
"""S133: record the measured emote payload shape and the working recipe."""
import io

# ---------- 1. handlePartyEmote: the shape is no longer unknown ----------
P = 'server/internal/interactive/partyactions.go'
s = io.open(P, encoding='utf-8').read()
old = """// handlePartyEmote answers a lobby emote.
//
// ⚠⚠ THIS HANDLER DELIBERATELY CHANGES NO STATE YET. The emote id is not in the path
// (the client sent `/emote/` with an empty final segment) and we have never seen the
// body. FParty's field block names `Emotes`, `Emotes_Played` and `EmoteID`, so there IS
// somewhere for an emote to live — but which of those the lobby reads, and in what shape,
// is UNMEASURED. Serving a guessed field is how you get an uninterpretable null.
//
// So this logs the method, the full path, the parsed trailing segment and the RAW BODY,
// then echoes the party unchanged. Its whole job right now is to MAKE THE SHAPE VISIBLE.
// ⇒ After the next emote click, read the ags log line and THEN decide what to serve."""
new = """// handlePartyEmote answers a lobby emote. SHAPE NOW MEASURED [M]:
//
//	POST /party/parties/{p}/emote/Emote:Fingerwag        body: EMPTY (bodylen=0)
//	POST /party/parties/{p}/emote/Emote:SeraphMurder     body: EMPTY
//	POST /party/parties/{p}/emote/Emote:YouThinkImBoosted
//
// ⇒ the emote id is the PATH TAIL, as a full `PrimaryAssetId` string ("Emote:<Name>"),
// and the body is always empty.
//
// ★★ THE INSTRUMENT EARNED ITS KEEP, AND IT CORRECTED THE PREMISE IT WAS BUILT ON.
// This handler was written as a body-logger because the first six POSTs arrived as bare
// `/emote/` with an empty body, and the working assumption was "the id must be in the
// body, which capture.log does not record". THAT WAS WRONG. The id was always in the
// path; the segment was empty because the ACCOUNT OWNED NO EMOTES, so the client had
// nothing to name. The same log line that recorded six empty bodies recorded the real
// id the moment ownership was fixed — because it logged the TAIL as well as the body.
// ⇒ Log every input channel, not the one your hypothesis names. The cheap extra field is
// what turns "my guess was wrong" into "here is the answer".
//
// ⚠ STILL CHANGES NO STATE, deliberately. Emotes visibly play in the lobby with the party
// document echoed unchanged, so nothing here is known to be needed. FParty names `Emotes`
// and `Emotes_Played` and a multi-member party may require a broadcast — but that is
// UNTESTED (this backend only ever serves a solo party), and inventing a field for an
// unobserved case is how uninterpretable nulls get made."""
assert old in s
s = s.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(s)
print('partyactions.go: emote shape recorded')

# ---------- 2. CLAUDE.md ----------
P = 'CLAUDE.md'
s = io.open(P, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, 'NOT FOUND: ' + a[:70]
    s = s.replace(a, b)


rep("""- ★★★★ **PHASE 2 ALSO LANDED""",
"""- ★★★★★ **EMOTES WORK — VISIBLE, EQUIPPABLE AND PLAYING IN THE LOBBY (S133).** The recipe is
  **BACKEND + THE EXISTING `catalog_store_fix.dll`**, and it took three refuted hypotheses to find:
  (1) `Emote:<Name>` inventory entries with `IsOwned=true`, (2) matching storefront ItemOffers
  (`Category: "Emotes"`), and (3) **the shim's AssetManager scan**. Knob **`AGS_GRANT_EMOTES`**
  (`1` = all 331; default empty = byte-identical to pre-S133). Names in
  `server/internal/menu/data/emotes.txt`, read LIVE from the client's own FNamePool by scanning
  interned `/Game/Loki/Personalization/Emotes/<Name>/` paths — the registry the game ships, not a
  guess (the missions `InternalName` lesson).
  ★★ **WHY THE SHIM IS REQUIRED HERE AND NOT FOR SKINS/GLIDERS/SPRAYS — the asymmetry is the whole
  answer:** `ULokiAssetLoader` has maps for `HeroAssets`, `HeroCosmeticsBundleAssets` (391),
  `SlotCosmeticsAssets` (536), `StoreOfferAssets`, `LoginRewardAssets`, `MissionPoolAssets`,
  `EquipmentAssets`, `PowerAssets` — and **NO `EmoteAssets` map.** So emotes are exactly the
  cosmetic type that cannot be enumerated without the AssetManager scan. Those other tabs populate
  fine on a `-NoHook` client; emotes never will.
  ⚠⚠ **AND THIS CORRECTS `cosmetics.go:13`,** which says the STORE's ACCESSORIES tab covers
  *"Gliders/**Emotes**/Wisps/Sprays/Avatars"* as type `SlotCosmetics`. **MEASURED: the live 536-name
  SlotCosmetics map contains ZERO emotes** (prefixes are AVATAR 225 / SPRAY 146 / GLIDER 115 /
  WISP 40 / SPIKEVFX 2). **`Emote` is its own PrimaryAssetType** — confirmed three ways: the shipped
  mastery-reward DAs use `"SKU":"Emote:SeraphHi"`, the picker widget
  `WBP_UI_Loadout_Customization_Emotes`'s own asset name table contains bare `Emote`, and its
  ubergraph calls `WBP_GenericCatalogPicker.SetContentTypeAndPrefix(prefix="", <"Primary Asset
  Type">)`.
  ★ **THREE HYPOTHESES WERE REFUTED BY MEASUREMENT before the right one:** inventory ownership alone
  (331 served, client refetched, picker empty); storefront offers as the missing half (served AND
  fetched **3×** by the game UA, still empty); the content manifest hiding them (it is queried
  `?nonEnabledOnly=true` and we return `Emotes: {}`, so they were already enabled). **Each null was
  interpretable only because the client was verified to have CONSUMED the document first.**
- ★★★★★ **THE LOBBY-EMOTE WIRE SHAPE [M]: `POST /party/parties/{p}/emote/Emote:<Name>` — the id is
  the PATH TAIL as a full PrimaryAssetId, and the BODY IS ALWAYS EMPTY.** Emotes play with the party
  document echoed unchanged, so no new field is needed for a solo party.
  ⚠⚠ **The six earlier POSTs that arrived as bare `/emote/` with an empty body were NOT a mystery
  payload — the account owned no emotes, so the client had nothing to name.** The handler was built
  as a *body*-logger on the wrong premise and still produced the answer, because it logged the TAIL
  too. ★ **Log every input channel, not the one your hypothesis names.**
- ★★★★ **PHASE 2 ALSO LANDED""")
io.open(P, 'w', encoding='utf-8').write(s)
print('CLAUDE.md: emote result recorded')
