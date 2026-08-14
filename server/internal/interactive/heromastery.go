package interactive

// HERO MASTERY — FPlayerProgression.HeroMastery (S120, 2026-08-14).
//
// WHY THIS EXISTS. The Hero Mastery page is a SPLIT surface, and conflating the two halves
// is the trap that kept it opaque:
//
//   (1) the ROW LIST (which missions, their titles, descriptions, icons, tier maxes) comes
//       100% from shipped data assets with ZERO backend involvement. WBP_HeroMastery_Screen_v2
//       reads LokiDataAsset_HeroMastery (25 shipped assets, /Game/Loki/Core/HeroMastery/) whose
//       CDO carries MissionSets: Array<MissionSet{ Missions: Array<FPrimaryAssetId> }>, and
//       creates one WBP_HeroMastery_MissionSet_v2 per set. MEASURED: uniformly 3 sets x 3
//       missions across all 25 heroes = 225 distinct mission ids.
//   (2) PROGRESS / COMPLETION / ACTIVE-TIER comes from the SAME UMissionsModel we already
//       populate via MissionInfo (GetProgressionManager -> GetMissionsModel ->
//       GetCurrentAndTotalProgress / CompletionCounts / GetActiveMissionModel).
//   (3) the per-hero LEVEL / XP / REWARD TRACK is THIS field, and it was the one missing feed.
//
// ⚠ There is NO pool filter on this surface — grep "Pool" returns 0 across the Hero Mastery
// bytecode dumps (control token "MissionSets" returns 6 in the same file). That is precisely
// why hunter missions render here and can NEVER render in the missions modal, whose categories
// are a hardcoded PoolAsset[] allowlist that omits DA_MissionPoolHunterMissions. Do not go
// looking for a mastery pool allowlist; it does not exist.
// ⚠ Hero Mastery also does NOT gate on bAllMissionLoaded (measured absent across all seven
// Hero Mastery bpdump files, against a 17-hit GetMissionsModel control) — unlike the missions
// modal and the news banner. Do not reason from that flag here.
//
// THE SCHEMA IS MEASURED, NOT GUESSED, and it closes exactly (UHT FStructParams/FPropertyParams
// over dumps/tutorial-hero, .rdata 100% readable; positive control = re-deriving FMissionInfo's
// 4 properties at their 4 known offsets before trusting the decoder):
//
//	FPlayerProgression (8 props, SizeOf 0x178) — ID @0x0, Version @0x10,
//	    Matches @0x18 TMap<FString,FPlayerProgressionMatchXP>, MissionInfo @0x68 FMissionInfo,
//	    AccountPass @0xe8 FProgressionTrackLevel, HeroMastery @0x148 TArray<FHeroMasteryProgress>,
//	    LoginReward @0x158, EventProgression @0x168.  max(off+size) == 0x178, zero slack.
//	FHeroMasteryProgress : FProgressionTrackLevel (SizeOf 0x70)
//	    Level @0x04 int32, XP @0x08 int32, Cleared @0x0C bool,
//	    UnclaimedRewards @0x10 TMap<int32,FHeroMasteryRewardClaimData>,
//	    HeroId @0x60 FPrimaryAssetId   <- the ONLY property the struct declares itself.
//
// Corroborated three independent ways: the UHT decode; tools/asdump/out/binds_members.csv (a
// different pipeline entirely — AngelScript binds — agreeing on all 8 properties and all 5
// flattened members INCLUDING container inner types); and disassembly of
// UProgressionManager::GetHeroMastery (impl base+0x5841D70), which reads [PM+0x90+0x148]/+0x150
// and does `imul rdx,rax,0x70`. Note the usmap was NOT used for any container inner type (FK-14:
// usmap inner types are ~70% wrong).
//
// SO IT RIDES AN INGEST THAT IS ALREADY PROVEN. The native ingester at base+0x585A570
// copy-constructs the whole 0x178-byte FPlayerProgression into ProgressionManager+0x90 —
// HeroMastery included, at no extra cost — then broadcasts PM+0x48.
// UBattlepassViewManager::CheckMasteryChanges (exec thunk 0x5254220 -> impl 0x5795510, the
// mastery twin of the account-pass CheckAccountPassChanges impl 0x5794480 that S83 solved,
// 0x1090 away in the same translation unit) then walks the array and runs the same
// FindVM (0x57AB180) -> Init (0x57BB560) -> populate (0x57DF4B0) chain. We never force-call
// populate — that was the S82 crash; the client calls it itself off the ingest.
// NO SHIM, NO .text WRITE.
//
// MEASURED LIVE BEFORE THIS CHANGE (game PID 64368): ProgressionManager @0x2601FB97A20,
// PM+0x90+0x148 = PM+0x1D8 read Data=0 Num=0 Max=0 — the array was EMPTY because we omitted it,
// and CheckMasteryChanges' `cmp rdi,rsi; je` skips the entire loop body when Num==0. The offset
// arithmetic was controlled in the same pass: the same chain read MissionData Num=323 at PM+0xF8
// and Pools Num=9 at PM+0x108 — the exact values we serve.
//
// ⚠⚠ BLAST RADIUS IS THREE SURFACES, NOT ONE. FJsonObjectConverter returns false for the WHOLE
// struct on the first MATCHED key it cannot import, so a wrong-typed HeroMastery would close the
// missions page, the Hunter's Journey pass AND news-banner gate 2 at once — and it would look
// exactly like "no effect". That is why this is behind an env knob (below): the arm is one
// variable and reverting needs no rebuild.
// ⚠ FREE, EXACT INSTRUMENT — USE IT, DO NOT INFER: LogJson names the failing property verbatim
// (`JsonObjectToUStruct - Unable to import JSON value into property HeroMastery`, and
// `Unable to import Array element N for property HeroMastery`). Same class of per-item readout as
// `Invalid asset path for Mission:`. Grep for it BEFORE any statistical inference.

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
)

// ---- HERO MASTERY REWARDS + THE CLAIM ROUTE (S120, 2026-08-14) ----------------------------
//
// THE ENDPOINT IS MEASURED, not guessed:
//
//	POST {progressionBase}/progression/players/{userId}/hero/rewards/claim
//
// Traced exactly the way handleGetProgression's chain was, with the same method re-finding
// L"/progression/players/" at .rdata 0x08B4D0D0 as a passing positive control first:
//   - literal L"/hero/rewards/claim" (UTF-16LE) at .rdata 0x08B4D3A0
//   - its ONE rip-relative xref: `lea r8,[rip+0x3325588]` at .text 0x05827E11
//   - enclosing builder 0x05827DA0: "/progression/players/" + UserId, + "/hero/rewards/claim",
//     then base = GetServiceAddress(key L"progression") — the same key used at all 11 progression
//     call sites, and the client's real GET has no path prefix, so base is scheme+host only
//   - verb POST (`lea rdx,[0x8600824 ansi="POST"]` at 0x05827F24)
//   - dispatch `call 0x057EC800` at 0x05827F60
//
// REQUEST: FClaimHeroMasteryRewardsRequest (UHT FStructParams 0x09C42048, SizeOf 0x20, 2 props)
//   HeroID FPrimaryAssetId @0x00 ; ClaimIDs TArray<FString> @0x10
// Key casing is FJsonObjectConverter::StandardizeCase — proven from a real client POST in
// docs/capture.log #479 (UA Loki/UE5-CL-0): LastBattlepassIDSeen -> "lastBattlepassIdSeen".
// So HeroID -> "heroId". [I] ClaimIDs -> "claimIds" is that rule applied to "IDs" and has never
// been seen on the wire, so the handler accepts every casing rather than betting on one letter.
//
// RESPONSE: no ClaimHeroMasteryRewardsResponse type exists; the shared sender 0x057EC800 has
// exactly two callers (this and /accountpass/rewards/claim), and FClaimProgressionTrackRewardsResponse
// and FClaimMissionRewardsResponse are both SizeOf 0x20 with identical fields
// {SuccessfulClaimIDs, UnclaimedClaimIDs} — so the JSON is the same whichever is instantiated.
//
// ⚠⚠ WHAT IS **NOT** ESTABLISHED, AND IT GOVERNS THE EXPECTATION:
// 1. `UnclaimedRewards` is NOT read by the claimable getter. MEASURED by disassembling
//    UClaimableRewardManager::GetAllClaimableHeroMasteryRewards (thunk 0x5269160 -> impl
//    0x583F1F0, fold 1): it converts the FPrimaryAssetId, ToString (0x12F4230), FindVM
//    (0x57AB180 — the SAME FindVM the S83 account-pass fix used), and on a hit calls
//    0x57ABCC0, which walks the VIEW MODEL's Levels array at [VM+0xC8]/[VM+0xD0] and bails
//    immediately when empty. So claimables come from the per-hero BattlepassViewModel, and
//    UnclaimedRewards can only reach it via CheckMasteryChanges (impl 0x5795510) -> populate.
//    That hop is INFERRED, not measured.
//    ★ Encouraging: the per-hero VMs exist and are populated — MEASURED live, 4 BP_BattlepassViewModel_C
//    with Levels Num = 86 (Hunter's Journey), 11, 9, 9; the 9s match WBP_HeroMastery_LevelIcon's
//    [0,8] clamp exactly. They are created lazily per viewed hero.
// 2. NO BLUEPRINT reaches the hero claim. A controlled census over all 69,142 extracted assets
//    returned ClaimHeroMasteryRewards 0 / ClaimIDs 0 / GetAllClaimableHeroMasteryRewards 0 against
//    passing positive controls ClaimReward 24 / HasClaimableMission 2. The Claim button on
//    WBP_HeroMastery_Mission_v2 is the MISSION claim (-> /mission/rewards/claim), NOT this one.
//    ⇒ do NOT use that button as the success criterion for this route.
// 3. What natively triggers builder 0x05827DA0 is UNKNOWN — no caller is visible in the ~52%
//    of .text that is decrypted. The likely user-reachable path is the lobby multi-claim
//    (BulkClaimAllProgressionTrackRewards, thunk 0x5268FB0).
//
// ★ FREE, EXACT RECEIPT: the shared sender 0x057EC800 is PAGE_NOACCESS in the live process,
// i.e. NO claim POST of either kind has ever been issued this session. If it ever flips to
// EXECUTE_READ, a claim was really dispatched. Zero-cost detector; valid while the PID lives.

// masteryRewards is hero InternalName -> level ("0".."6") -> reward FPrimaryAssetId "Type:Name",
// built offline from the 25 shipped LokiDataAsset_HeroMastery LevelRewards maps.
// Regenerate with tools/re/gen_mastery_rewards.py.
//
//go:embed mastery_rewards.json
var masteryRewardsJSON []byte

var masteryRewards = func() map[string]map[string]string {
	m := map[string]map[string]string{}
	if err := json.Unmarshal(masteryRewardsJSON, &m); err != nil {
		// Loud: silently empty rewards would look exactly like "the client ignored them".
		log.Printf("mastery: mastery_rewards.json failed to parse (%v) — no rewards will be served", err)
		return map[string]map[string]string{}
	}
	return m
}()

// masteryClaimID is the ClaimID we mint for one (hero, level). It is OUR identifier — the client
// echoes it back verbatim in ClaimIDs, so its only requirements are stability and uniqueness.
func masteryClaimID(hero string, level int) string {
	return fmt.Sprintf("hm:%s:%d", strings.ToLower(hero), level)
}

// parseMasteryClaimID reverses masteryClaimID. Returns ok=false for anything we did not mint.
func parseMasteryClaimID(id string) (hero string, level int, ok bool) {
	p := strings.Split(id, ":")
	if len(p) != 3 || p[0] != "hm" {
		return "", 0, false
	}
	n, err := strconv.Atoi(p[2])
	if err != nil || n < 0 {
		return "", 0, false
	}
	return p[1], n, true
}

// heroFromAssetID accepts "Hero:Alchemist", "HeroMastery:Alchemist" or a bare "Alchemist".
// Both prefixes are accepted deliberately: the request is built CLIENT-side and which id it
// carries is [I], while ULokiAssetStatics::GetHeroIdForHeroMasteryId / GetHeroMasteryIdForHeroId
// existing at all proves the two are distinct and mutually convertible. Matching is
// case-insensitive (FName semantics).
func heroFromAssetID(s string) string {
	if i := strings.LastIndex(s, ":"); i >= 0 {
		s = s[i+1:]
	}
	for h := range masteryRewards {
		if strings.EqualFold(h, s) {
			return h
		}
	}
	return ""
}

// heroMasteryIDs is the InternalName of every shipped LokiDataAsset_HeroMastery.
//
// MEASURED from the 25 shipped assets (tools/extractor/out/*Mastery_uasset.json): for all 25,
// InternalName == Hero.PrimaryAssetName exactly, so the NAME half of the FPrimaryAssetId is
// unambiguous whichever type prefix turns out to be right. Casing is as-shipped and deliberately
// preserved; FName matching is case-insensitive (the rule that was worth 41 of 126 mission
// matches in S119), so it does not matter — but copying the shipped casing keeps this list
// diffable against the assets.
var heroMasteryIDs = []string{
	"Alchemist", "assault", "BacklineHealer", "beebo", "BountyHunter",
	"BurstCaster", "Earthtank", "FarShot", "firefox", "flex",
	"freeze", "gunner", "hookguy", "Huntress", "Reaper",
	"reshealer", "rocketjumper", "RONIN", "SHIELDBOT", "sniper",
	"stalker", "Storm", "Succubus", "void", "Wukong",
}

// HeroMasteryProgress is one hero's mastery track. Mirrors FProgressionTrackLevel's scalar
// leaves; UnclaimedRewards is deliberately NOT modeled here (see heroMasteryEntries).
type HeroMasteryProgress struct {
	Level   int  `json:"level"`
	XP      int  `json:"xp"`
	Cleared bool `json:"cleared"`
}

// HeroMastery returns a player's stored per-hero mastery progress, keyed by the hero's
// InternalName. A player with nothing stored reads as all-zero, which is the correct
// fresh-account state (level 0, no XP) — not an error.
func (s *Service) HeroMastery(id string) map[string]HeroMasteryProgress {
	st := s.store.get(id)
	out := make(map[string]HeroMasteryProgress, len(heroMasteryIDs))
	for _, h := range heroMasteryIDs {
		out[h] = st.HeroMastery[h] // zero value when absent
	}
	return out
}

// SetHeroMastery writes one hero's mastery progress and returns the stored result.
// Like SetAccountPass this has REAL EFFECT with no relaunch: the value is served on
// GET /progression/players/{id}, the served Version advances because heroMasteryDigest
// feeds progressionVersionFor, and the client's native ingester adopts it on its ~61s poll.
func (s *Service) SetHeroMastery(id, hero string, p HeroMasteryProgress) HeroMasteryProgress {
	if p.Level < 0 {
		p.Level = 0
	}
	if p.XP < 0 {
		p.XP = 0
	}
	s.store.update(id, func(st *playerState) {
		if st.HeroMastery == nil {
			st.HeroMastery = map[string]HeroMasteryProgress{}
		}
		st.HeroMastery[hero] = p
	})
	return p
}

// masteryClaimed returns the set of mastery levels this player has already claimed for one hero.
func (s *Service) masteryClaimed(playerID, hero string) map[int]bool {
	st := s.store.get(playerID)
	out := map[int]bool{}
	for _, lv := range st.MasteryClaimed[strings.ToLower(hero)] {
		out[lv] = true
	}
	return out
}

// registerHeroMastery wires the measured claim route. See the block comment at the top of this
// file for how the URL, verb and body were traced.
//
// ⚠ The client builds the FULL url as base + "/progression/players/" + id + "/hero/rewards/claim",
// so the path we register must match that suffix exactly.
func (s *Service) registerHeroMastery(mux *http.ServeMux) {
	mux.HandleFunc("POST /progression/players/{id}/hero/rewards/claim", s.handleClaimHeroMasteryRewards)
}

// handleClaimHeroMasteryRewards services the mastery reward claim.
//
// Request  {"heroId":"Hero:reshealer","claimIds":["hm:reshealer:0"]}
// Response {"successfulClaimIds":["hm:reshealer:0"],"unclaimedClaimIds":[]}
//
// Every key is accepted in any casing. The response field names follow the same
// FJsonObjectConverter::StandardizeCase rule the client uses on the way out
// (SuccessfulClaimIDs -> successfulClaimIds), and UE ignores unknown keys, so the PascalCase
// aliases are emitted too — absent is safe, wrong-typed is not, and duplicating a correct value
// under two names cannot wrong-type anything.
func (s *Service) handleClaimHeroMasteryRewards(w http.ResponseWriter, r *http.Request) {
	playerID := r.PathValue("id")
	raw, _ := io.ReadAll(io.LimitReader(r.Body, 1<<20))

	// Decode into a case-insensitive bag: Go's encoding/json already matches field names
	// case-insensitively, which covers heroId/heroID/HeroID and claimIds/claimIDs/ClaimIDs.
	var body struct {
		HeroID   string   `json:"heroId"`
		ClaimIDs []string `json:"claimIds"`
	}
	_ = json.Unmarshal(raw, &body)

	hero := heroFromAssetID(body.HeroID)
	ok := make([]string, 0, len(body.ClaimIDs))
	bad := make([]string, 0)

	for _, cid := range body.ClaimIDs {
		h, lv, parsed := parseMasteryClaimID(cid)
		// A claim is honoured only if it is one we could have offered: our id format, the hero
		// the request names (when it named one), a level the asset actually rewards, and not
		// already claimed. Anything else goes back as unclaimed rather than being silently
		// swallowed — the client has a field for exactly that.
		if !parsed || (hero != "" && !strings.EqualFold(h, hero)) {
			bad = append(bad, cid)
			continue
		}
		target := hero
		if target == "" {
			target = heroFromAssetID(h)
		}
		if target == "" || masteryRewards[target][strconv.Itoa(lv)] == "" || s.masteryClaimed(playerID, target)[lv] {
			bad = append(bad, cid)
			continue
		}
		s.store.update(playerID, func(st *playerState) {
			if st.MasteryClaimed == nil {
				st.MasteryClaimed = map[string][]int{}
			}
			k := strings.ToLower(target)
			st.MasteryClaimed[k] = append(st.MasteryClaimed[k], lv)
		})
		ok = append(ok, cid)
	}
	log.Printf("mastery claim: player=%s hero=%q requested=%d granted=%d rejected=%d",
		playerID, body.HeroID, len(body.ClaimIDs), len(ok), len(bad))

	writeJSON(w, map[string]any{
		"successfulClaimIds": ok,
		"unclaimedClaimIds":  bad,
		"SuccessfulClaimIDs": ok,
		"UnclaimedClaimIDs":  bad,
	})
}

// heroMasteryMode reads the AGS_SERVE_HEROMASTERY knob.
//
// OFF BY DEFAULT, deliberately. Serving this key is the single riskiest edit to a document that
// currently drives three working surfaces (see the blast-radius warning above), so it must be
// armed explicitly and disarmed without a rebuild.
//
//	(unset) / "0" / "off"  -> omit the key entirely; byte-identical to the pre-S120 document.
//	"hero"                 -> HeroId = "Hero:<name>"
//	"mastery"              -> HeroId = "HeroMastery:<name>"
//	"both"                 -> both forms in one array (see below)
//
// ⚠ WHICH TYPE PREFIX IS CORRECT IS THE ONE OPEN QUESTION, and the two instruments disagree,
// so do not pick by taste:
//   - "Hero:" is supported by disassembly — the caller at base+0x57B856E does
//     `movups xmm0,[MasteryDA+0xC0]`, and 0xC0 is where UHT places
//     ULokiDataAsset_HeroMastery::Hero, then hands it to GetHeroMastery, which compares it
//     against elem+0x60. The field is also literally named HeroId.
//   - "HeroMastery:" is supported by the client's own log line
//     `Progress Notif: {"progressionTrackId":"HeroMastery:reshealer",...}` and by
//     ULokiAssetStatics::GetHeroIdForHeroMasteryId / GetHeroMasteryIdForHeroId existing at all,
//     which proves the two ids are DISTINCT and mutually convertible.
//     ⚠ But that log line is the PROGRESSION TRACK id (the mastery asset's own PrimaryAssetId),
//     which is not necessarily what the HeroId FIELD holds. Weaker evidence, on a different thing.
//
// "both" resolves it in ONE launch instead of two. It is safe: GetHeroMastery does a linear
// FIRST-MATCH scan, and CheckMasteryChanges silently skips any entry whose FindVM lookup misses,
// so surplus entries cannot break either consumer. Set AGS_HEROMASTERY_PROBE_DELTA to a nonzero
// integer to offset the "HeroMastery:"-typed duplicate's Level, which makes the flight
// SELF-DISCRIMINATING — whichever Level the UI draws names the winning key. Leave the delta at 0
// (the default) when you just want it to work.
func heroMasteryMode() string {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("AGS_SERVE_HEROMASTERY"))) {
	case "hero":
		return "hero"
	case "mastery":
		return "mastery"
	case "both", "1", "true", "yes":
		return "both"
	default:
		return "" // off
	}
}

// heroMasteryEntries builds FPlayerProgression.HeroMastery, plus a digest for the Version gate.
// Returns (nil, "") when the knob is off, so the emitted document is byte-identical to before.
//
// UnclaimedRewards is OMITTED on purpose. Absent is safe under the validity model (UE ignores
// unknown keys; only a MATCHED key with a WRONG type rejects the whole document), while a
// TMap<int32,...> sent as a JSON array instead of an object is exactly the kind of matched-but-
// wrong-typed key that would silently kill all three surfaces. Its shape is known when we want it:
// {"3":{"ClaimID":"...","SKU":"PlayerTitle:..."}} — a JSON OBJECT whose keys parse as integers,
// with SKUs coming from each mastery DA's own 7-entry LevelRewards map (keys "0".."6").
func (s *Service) heroMasteryEntries(id string) ([]any, string) {
	mode := heroMasteryMode()
	if mode == "" {
		return nil, ""
	}

	delta := 0
	if d, err := strconv.Atoi(strings.TrimSpace(os.Getenv("AGS_HEROMASTERY_PROBE_DELTA"))); err == nil {
		delta = d
	}
	// AGS_HEROMASTERY_BASE_LEVEL — DIAGNOSTIC floor applied to every hero with no stored
	// progress. Default 0 = the honest fresh-account value; leave it UNSET in normal operation.
	//
	// WHY IT EXISTS. The probe delta above is only a discriminator if BOTH forms are visibly
	// distinct from "nothing happened". On a fresh account every hero is Level 0, so the
	// "Hero:"-typed entries render as 0 — which is EXACTLY what an unrendered / unconsumed track
	// also looks like. That makes a 0 on screen uninterpretable, not negative: the classic
	// instrument-artifact shape this project keeps re-learning. Setting a nonzero floor makes the
	// reading total:
	//     screen shows <base>          -> the client consumed "Hero:<name>"
	//     screen shows <base>+<delta>  -> the client consumed "HeroMastery:<name>"
	//     screen shows 0 / nothing     -> it consumed NEITHER
	base := 0
	if b, err := strconv.Atoi(strings.TrimSpace(os.Getenv("AGS_HEROMASTERY_BASE_LEVEL"))); err == nil && b > 0 {
		base = b
	}

	prog := s.HeroMastery(id)
	names := make([]string, 0, len(prog))
	for h := range prog {
		names = append(names, h)
	}
	sort.Strings(names) // stable order => stable digest => Version only moves on real change

	entries := make([]any, 0, len(names)*2)
	var sb strings.Builder
	for _, name := range names {
		p := prog[name]
		lvl := p.Level
		if lvl < base {
			lvl = base // diagnostic floor; a stored value always wins
		}
		unclaimed, uDigest := s.unclaimedRewardsFor(id, name, lvl)
		if mode == "hero" || mode == "both" {
			e := map[string]any{
				"HeroId":  "Hero:" + name,
				"Level":   lvl,
				"XP":      p.XP,
				"Cleared": p.Cleared,
			}
			if unclaimed != nil {
				e["UnclaimedRewards"] = unclaimed
			}
			entries = append(entries, e)
		}
		if mode == "mastery" || mode == "both" {
			ml := lvl
			if mode == "both" {
				ml += delta // 0 unless the self-discriminating probe is armed
			}
			e := map[string]any{
				"HeroId":  "HeroMastery:" + name,
				"Level":   ml,
				"XP":      p.XP,
				"Cleared": p.Cleared,
			}
			if unclaimed != nil {
				e["UnclaimedRewards"] = unclaimed
			}
			entries = append(entries, e)
		}
		fmt.Fprintf(&sb, "%s=%d/%d/%t/%s;", name, p.Level, p.XP, p.Cleared, uDigest)
	}
	// The mode, delta AND base join the digest: flipping any knob must move Version, or the strict
	// `>` adoption gate at +585A594 silently drops the new document and the run reads as "the knob
	// does nothing". ⚠ `base` is easy to forget here because the per-hero digest above records the
	// STORED level, not the floored one — an earlier revision of this function omitted it and the
	// diagnostic floor would have been invisible to the client. The per-hero unclaimed digest is
	// folded in above for the same reason: a claim must move Version or the client keeps the old
	// document and the reward appears un-claimed forever.
	return entries, fmt.Sprintf("hm2-%s-d%d-b%d-r%s-%d-%s",
		mode, delta, base, os.Getenv("AGS_SERVE_MASTERY_REWARDS"), len(entries), sb.String())
}

// unclaimedRewardsFor builds one hero's FHeroMasteryProgress.UnclaimedRewards, plus a digest.
// Returns (nil, "") when the knob is off, so the served entry is byte-identical to before.
//
// ⚠⚠ THE SHAPE IS THE WHOLE RISK. UnclaimedRewards is TMap<int32, FHeroMasteryRewardClaimData>,
// and UE's FJsonObjectConverter needs a JSON **OBJECT whose keys parse as integers** — NOT an
// array. A wrong-typed MATCHED key makes it reject the ENTIRE FPlayerProgression, which closes
// the missions page, the Hunter's Journey pass AND news-banner gate 2 at once and looks exactly
// like "no effect". Hence its own env gate, off by default:
//
//	{"0": {"ClaimID": "hm:reshealer:0", "SKU": "Emote:SeraphHi"}}
//
// ★ Free discriminator if it IS wrong: LogJson names the property verbatim —
// `JsonObjectToUStruct - Unable to import JSON value into property HeroMastery`. Grep for it
// before inferring anything, and check DAILIES still renders 3/3 as the blast-radius canary.
//
// WHICH LEVELS ARE OFFERED: every level the player has reached (0..Level) that has a reward in the
// asset and has not been claimed. A fresh account at Level 0 therefore gets exactly ONE unclaimed
// reward per hero, which is conveniently the minimal single-entry probe.
// ⚠ [I] "reward key == mastery level index" is the natural reading but is NOT settled — there are
// 7 rewards (0..6), 8 XPAmounts, and a [0,8] icon clamp (live VM Levels Num = 9). A level above 6
// simply has no reward; nothing is synthesised for it.
func (s *Service) unclaimedRewardsFor(playerID, hero string, level int) (map[string]any, string) {
	if strings.TrimSpace(os.Getenv("AGS_SERVE_MASTERY_REWARDS")) == "" {
		return nil, ""
	}
	rewards := masteryRewards[hero]
	if len(rewards) == 0 {
		return nil, ""
	}
	claimed := s.masteryClaimed(playerID, hero)

	out := map[string]any{}
	var sb strings.Builder
	for lv := 0; lv <= level; lv++ {
		key := strconv.Itoa(lv)
		sku, ok := rewards[key]
		if !ok || claimed[lv] {
			continue
		}
		out[key] = map[string]any{
			"ClaimID": masteryClaimID(hero, lv),
			"SKU":     sku,
		}
		fmt.Fprintf(&sb, "%d,", lv)
	}
	if len(out) == 0 {
		// Serve the key as an empty object rather than omitting it: an explicitly empty TMap is
		// a meaningful "nothing to claim", and it keeps the shape identical across states so a
		// parse failure cannot be blamed on the key appearing only sometimes.
		return map[string]any{}, "none"
	}
	return out, sb.String()
}
