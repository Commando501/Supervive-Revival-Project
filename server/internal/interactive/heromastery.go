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
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

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
		if mode == "hero" || mode == "both" {
			entries = append(entries, map[string]any{
				"HeroId":  "Hero:" + name,
				"Level":   lvl,
				"XP":      p.XP,
				"Cleared": p.Cleared,
			})
		}
		if mode == "mastery" || mode == "both" {
			ml := lvl
			if mode == "both" {
				ml += delta // 0 unless the self-discriminating probe is armed
			}
			entries = append(entries, map[string]any{
				"HeroId":  "HeroMastery:" + name,
				"Level":   ml,
				"XP":      p.XP,
				"Cleared": p.Cleared,
			})
		}
		fmt.Fprintf(&sb, "%s=%d/%d/%t;", name, p.Level, p.XP, p.Cleared)
	}
	// The mode, delta AND base join the digest: flipping any knob must move Version, or the strict
	// `>` adoption gate at +585A594 silently drops the new document and the run reads as "the knob
	// does nothing". ⚠ `base` is easy to forget here because the per-hero digest above records the
	// STORED level, not the floored one — an earlier revision of this function omitted it and the
	// diagnostic floor would have been invisible to the client.
	return entries, fmt.Sprintf("hm1-%s-d%d-b%d-%d-%s", mode, delta, base, len(entries), sb.String())
}
