#!/usr/bin/env python3
"""S133 documentation sweep: propagate this session's results into every doc that
carries a now-stale claim. Method rule 9: grep for the claim, don't fix one instance."""
import io

# ─────────────────────────────────────────────────────────────────────────────
# 1. docs/endpoints.md — the party ACTION verbs. None of them were listed, and
#    setTargetQueues (S122) was missing too.
# ─────────────────────────────────────────────────────────────────────────────
P = 'docs/endpoints.md'
s = io.open(P, encoding='utf-8').read()
anchor = "### Cascade revealed by populating progressiontracks"
new = """### Party ACTION verbs — the interaction-triggered surface (S122 + S133)

⚠⚠ **THESE ARE INVISIBLE TO A PASSIVE CAPTURE-DIFF.** S122's sweep parsed a 74-minute
capture and reported "56 client routes, 8 unserved". Every row below was missing from it,
because the endpoints only fire when a HUMAN CLICKS the control: nobody clicked an activity
tile (`setTargetQueues`), FIND MATCH (`joinQueue`), cancel (`leaveQueue`), the privacy
toggle (`setIsOpen`) or an emote (`emote`) during that capture.
⇒ **A capture-diff enumerates what the client HAPPENED to exercise, not what it can call.
Drive the interaction, THEN diff. Re-running the sweep for longer does not help.**

★ Note the URL shape: these put their value in the **PATH**, not a JSON body, unlike the
rest of this backend. `emote/` arrives with an EMPTY tail when the account owns no emote.

★ **Free receipt: the client RETRIES an unaccepted party verb** (`joinQueue` was POSTed
twice, ~10–35 s apart, until the response was accepted; once accepted it fires exactly
ONCE). A repeating verb in `capture.log` means your response is being rejected.

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/party/parties/{partyId}/setTargetQueues` | ✅ | **Activity-tile selection** (S122). Body `{"queueIds":["<id>"]}`. Unserved it fell to the catch-all and the next `/party` poll re-served the old `targetQueueId`, snapping the selection back — the observed grey/un-grey. Persists + echoes the party. |
| POST | `/party/parties/{partyId}/joinQueue` | ✅ | **FIND MATCH** (S133). Empty body. ★★ **The response must be an `FParty` under an ADVANCED `Version`** — read from the decrypted `UPartyManager::TryJoinQueue` (`0x5875E90`), whose callback `0x5859E10` calls `UPartyModel::SetParty` (`0x587BE90`, the S85 monotonic-Version gate). ★★ **The field that drives the queued UI is `state = "Matchmaking"`** (`EPartyState = {Default, Matchmaking, CustomGame, Unknown}`), **NOT `inQueue`** — serving `inQueue:true` alone was MEASURED insufficient (SetParty ran, `LogJson` silent, UI unmoved). ⚠ Nothing matches the player: no matchmaker answers the queue, and `matchmakingNotif` is UNBOUND (FK-15/S118) so a match-found signal has to be HTTP. Knob `AGS_JOIN_QUEUE=0`. |
| POST | `/party/parties/{partyId}/leaveQueue` | ✅ | **Cancel** (S133). Registered speculatively alongside `cancelQueue`; the client uses `leaveQueue`, confirmed on the wire. |
| POST | `/party/parties/{partyId}/setIsOpen/{value}` | ✅ | **Party privacy toggle** (S133). Value in the PATH. ⚠ The client sends **capitalised `True`/`False`** — parse case-insensitively or every value reads as false and it looks exactly like "the toggle does nothing". |
| POST | `/party/parties/{partyId}/emote/{Emote:Name}` | 🧪 | **Lobby emote** (S133). [M] the id is the **PATH TAIL as a full PrimaryAssetId** (`Emote:Fingerwag`) and the **body is always empty**. Emotes play with the party document echoed UNCHANGED, so no new field is known to be needed — `FParty` names `Emotes`/`Emotes_Played` but a multi-member broadcast is UNTESTED (this backend only serves a solo party). |
| POST | `/party/parties/{p}/members/{id}/latencies` | 🟡 | client→server upload, no surface |
| POST | `/party/parties/{p}/refreshRanks` | ❓ | revealed by serving `FPlayerRank` (S122); still unserved |
| POST | `/party/parties/{p}/members/{id}/refreshMastery` | ❓ | called at login; untraced |

### Cascade revealed by populating progressiontracks"""
assert anchor in s
s = s.replace(anchor, new, 1)
io.open(P, 'w', encoding='utf-8').write(s)
print('endpoints.md: party action verbs added')

# ─────────────────────────────────────────────────────────────────────────────
# 2. server/internal/menu/cosmetics.go:13 — the wrong claim, fixed IN PLACE
# ─────────────────────────────────────────────────────────────────────────────
P = 'server/internal/menu/cosmetics.go'
s = io.open(P, encoding='utf-8').read()
a = '//   - ACCESSORIES keeps type == "SlotCosmetics" (Gliders/Emotes/Wisps/Sprays/Avatars)'
b = """//   - ACCESSORIES keeps type == "SlotCosmetics" (Gliders/Wisps/Sprays/Avatars/SpikeVFX)
//
// ⚠⚠ CORRECTED S133: this line used to read "Gliders/Emotes/Wisps/Sprays/Avatars".
// EMOTES ARE NOT SlotCosmetics. MEASURED: the 536-name SlotCosmeticsAssets map captured
// live from the client contains ZERO emotes — its slot prefixes are AVATAR(225),
// SPRAY(146), GLIDER(115), WISP(40), SPIKEVFX(2). `Emote` is its OWN PrimaryAssetType,
// confirmed three ways: the shipped hero-mastery reward DAs use "SKU":"Emote:SeraphHi";
// the picker widget WBP_UI_Loadout_Customization_Emotes's own asset name table contains
// bare `Emote`; and its ubergraph calls
// WBP_GenericCatalogPicker.SetContentTypeAndPrefix(prefix="", <"Primary Asset Type">).
// See emotegrant.go. ⚠ ULokiAssetLoader has NO EmoteAssets map (it has HeroAssets,
// HeroCosmeticsBundleAssets, SlotCosmeticsAssets, StoreOfferAssets, LoginRewardAssets,
// MissionPoolAssets, EquipmentAssets, PowerAssets) — which is exactly why emotes need
// catalog_store_fix.dll's AssetManager scan while these tabs populate without any shim."""
assert a in s
io.open(P, 'w', encoding='utf-8').write(s.replace(a, b))
print('cosmetics.go: Emotes-as-SlotCosmetics claim corrected in place')

# ─────────────────────────────────────────────────────────────────────────────
# 3. docs/fk5-battle-gate-settled.md — the [M] that this session refuted
# ─────────────────────────────────────────────────────────────────────────────
P = 'docs/fk5-battle-gate-settled.md'
s = io.open(P, encoding='utf-8').read()
banner = """> ⚠⚠ **CORRECTION (S133, 2026-08-20) — ONE `[M]` IN THIS FILE IS REFUTED. READ THIS FIRST.**
>
> This file states, graded `[M]`, that *"`0x1F8CFC0` is an all-zero page, so **the packet
> format is unreadable offline**"* (§6.4 rationale; the same page is cited at :58, :180,
> :190, :444, :915), and builds a verbatim-echo + hexdump responder plan around recovering
> the format empirically.
>
> **`0x1F8CFC0` IS A ~300-BYTE WRAPPER.** Disassembled, it reads `[Ping] StackSize` from the
> ini, names a thread from the ANSI literal `"LokiPing"` (`.rdata 0x79C6E80` — the very
> string this file flags `[SI]`), allocates an 0x80-byte object and tail-calls the real
> worker at **`0x1F8BE90`**.
>
> **[M] `0x1F8BE90` is LIT in `dumps/merged.dump.exe`, in `merged2`, in `menu`, in
> `tutorial-hero` — in EVERY image this project has ever taken.** The packet-building code
> was never dark, so the claim was false on the day it was written, and not for a coverage
> reason. ⇒ **the UDP-echo packet format can be read offline TODAY** from `0x1F8BE90` and
> its siblings `0x1F8BB50` / `0x1F8B870` / `0x1F8B4F0`.
>
> ★ **The rule: before recording "this page is dark, therefore X is unreadable", CHECK THE
> CALLEE.** A zero wrapper says nothing about the function it calls. ⚠ This is
> `fk22-dropphase-reachability.md:675` recommitted in a different file — there,
> `ULokiPreloadComponent::OnRoundPhaseChanged` was filed COVERAGE-BLOCKED on a zero *thunk*
> whose impl was decrypted. Same family, second instance.
>
> ★ Separately: the wrapper itself went dark→lit on 2026-08-15 (S121, the session that
> created the first `ULatencyMeasurer`), and nobody re-graded. See
> `docs/fk20-coverage-settled.md` §5.1. The rest of this file stands.

"""
if 'CORRECTION (S133' not in s:
    i = s.index('\n', s.index('#'))  # after the first heading line
    s = s[:i + 1] + '\n' + banner + s[i + 1:]
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fk5-battle-gate-settled.md: correction banner added')

# ─────────────────────────────────────────────────────────────────────────────
# 4. docs/fk22-dropphase-reachability.md — 0x5456000 is no longer coverage-blocked
# ─────────────────────────────────────────────────────────────────────────────
P = 'docs/fk22-dropphase-reachability.md'
s = io.open(P, encoding='utf-8').read()
banner2 = """> ★★ **COVERAGE UPDATE (S133, 2026-08-20).** This file files 16 `(class, func)` keys as
> **COVERAGE-BLOCKED**, most of them on `.text` page **`0x5456000`** (the five
> `AuthPlayer*` entry points and `GetLandingTeleportLocation`'s thunk `0x5456C80`).
>
> **[M] `0x5456000` IS NOW DECRYPTED — 3,860 / 4,096 non-zero in `dumps/merged10.dump.exe`.**
> S131/S132's rideable and dismount flights lit it. `0x5456C80` likewise went dark→lit from
> `s131-rideable-live` onward.
>
> ⇒ **The §2.5 re-grade this file calls "free, offline and unstarted" is now also
> UNBLOCKED**, and should be run against `dumps/merged10.dump.exe` (16,755 / 30,281 pages,
> 55.33 %) rather than the 18-image corpus those verdicts were measured on.
> ⚠ Still dark and still genuinely blocked: `0x560EE70` (the BR phase-4 body) and
> `0x55A34E0`. See `docs/fk20-coverage-settled.md` §5.2.

"""
if 'COVERAGE UPDATE (S133' not in s:
    i = s.index('\n', s.index('#'))
    s = s[:i + 1] + '\n' + banner2 + s[i + 1:]
    io.open(P, 'w', encoding='utf-8').write(s)
    print('fk22-dropphase-reachability.md: coverage update banner added')
